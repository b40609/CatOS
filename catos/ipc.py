"""Bounded, data-only protocol between the Supervisor and one strategy Worker.

Two checkpoint forms exist. v1 (the built-in SMA artifact) carries the last two
closes and the Supervisor recomputes them. v2 (an approved research deployment,
2026-11-12) carries only the sequence and the last bar time: a restarted Worker
is restored by re-feeding the ledger's committed bars as warm-up, which is valid
because only strategies whose state is the last ``lookback`` bars may deploy.
"""

import asyncio
from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation, localcontext
import json
import re
import struct

from catos import research, strategy_registry
from catos.research import AccountView, BacktestConfig, Candle, ContractSpec

VERSION = 1
MAX_FRAME = 65_536
MAX_DEPTH = 8
MAX_INTEGER = 2**63 - 1
# v1's only registered strategy id; identity is validated through the manifest
# registry, this constant is just the default alias.
STRATEGY_ID = "sma-trend"
# Wire schema marker of the strategy config block, not the artifact version.
STRATEGY_VERSION = 1
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_APPROVAL_ID = re.compile(r"[0-9a-f]{32}\Z")
# Restart history travels in one init frame: ~61 bytes a bar, so 512 bars stay
# near 32 KB, well inside MAX_FRAME. strategy_approvals.MAX_BOT_LOOKBACK matches.
MAX_BOT_LOOKBACK = 512


class ProtocolError(ValueError):
    pass


def exact(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise ProtocolError(f"expected object fields: {', '.join(names)}")
    return value


def integer(value, name, minimum=0):
    if type(value) is not int or not minimum <= value <= MAX_INTEGER:
        raise ProtocolError(f"invalid {name}: bounded integer required")
    return value


def token(value, name):
    if type(value) is not str or not _TOKEN.fullmatch(value):
        raise ProtocolError(f"invalid {name}")
    return value


def decimal_text(value, name, *, derived=False, positive=False):
    if type(value) is not str or len(value) > 192 or not _NUMBER.fullmatch(value):
        raise ProtocolError(f"{name} must be a bounded Decimal string")
    try:
        with localcontext(research._CONTEXT):
            result = Decimal(value)
            if derived:
                if (not result.is_finite() or len(result.as_tuple().digits) > 50
                        or result.as_tuple().exponent < -148 or result.adjusted() > 99):
                    raise ValueError("outside derived Decimal range")
            else:
                research._decimal(result, name, positive=positive)
    except (ValueError, InvalidOperation) as exc:
        raise ProtocolError(f"invalid {name}: {exc}") from exc
    return result


def _tree(value, depth=0):
    if depth > MAX_DEPTH or (depth == MAX_DEPTH and type(value) in (dict, list)):
        raise ProtocolError("JSON nesting limit exceeded")
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if not -MAX_INTEGER <= value <= MAX_INTEGER:
            raise ProtocolError("JSON integer limit exceeded")
    elif type(value) is str:
        if len(value) > MAX_FRAME:
            raise ProtocolError("JSON string limit exceeded")
    elif type(value) is list:
        for item in value:
            _tree(item, depth + 1)
    elif type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ProtocolError("JSON keys must be strings")
            _tree(key, depth + 1)
            _tree(item, depth + 1)
    else:
        raise ProtocolError("only JSON data types permitted; no Float")


def encode_frame(value):
    _tree(value)
    if type(value) is not dict:
        raise ProtocolError("message must be an object")
    try:
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")
    except (ValueError, UnicodeError) as exc:
        raise ProtocolError("invalid JSON text") from exc
    if not 0 < len(payload) <= MAX_FRAME:
        raise ProtocolError("frame size limit exceeded")
    return struct.pack("!I", len(payload)) + payload


def decode_payload(payload):
    if not 0 < len(payload) <= MAX_FRAME:
        raise ProtocolError("frame size limit exceeded")
    try:
        text = payload.decode("utf-8")
        # Bound nesting before calling the recursive JSON decoder.
        depth = 0
        quoted = escaped = False
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in "[{":
                depth += 1
                if depth > MAX_DEPTH:
                    raise ProtocolError("JSON nesting limit exceeded")
            elif char in "]}":
                depth -= 1

        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ProtocolError("duplicate JSON key")
                result[key] = value
            return result

        def number(raw):
            if len(raw.lstrip("-")) > 19:
                raise ProtocolError("JSON integer length exceeded")
            return int(raw)

        def forbidden(raw):
            raise ProtocolError("JSON Float and non-finite constants forbidden")

        value = json.loads(text, object_pairs_hook=pairs, parse_int=number,
                           parse_float=forbidden, parse_constant=forbidden)
        _tree(value)
        if type(value) is not dict:
            raise ProtocolError("message must be an object")
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolError("invalid UTF-8 JSON") from exc


def frame_size(header):
    size = struct.unpack("!I", header)[0]
    if not 0 < size <= MAX_FRAME:
        raise ProtocolError("frame size limit exceeded")
    return size


async def read_frame(reader):
    try:
        header = await reader.readexactly(4)
        return decode_payload(await reader.readexactly(frame_size(header)))
    except asyncio.IncompleteReadError as exc:
        raise ProtocolError("worker pipe EOF or truncated frame") from exc


def read_frame_sync(stream):
    def read_exact(size):
        chunks = bytearray()
        while len(chunks) < size:
            chunk = stream.read(size - len(chunks))
            if not chunk:
                raise ProtocolError("pipe EOF or truncated frame")
            chunks.extend(chunk)
        return bytes(chunks)

    return decode_payload(read_exact(frame_size(read_exact(4))))


def write_frame_sync(stream, message):
    remaining = memoryview(encode_frame(message))
    while remaining:
        count = stream.write(remaining)
        if count is None or count <= 0:
            raise ProtocolError("pipe write made no progress")
        remaining = remaining[count:]
    stream.flush()


def envelope(kind, generation, seq, payload):
    return dict(version=VERSION, kind=kind, generation=generation, seq=seq, payload=payload)


def check_envelope(message, kind, generation, seq):
    exact(message, ("version", "kind", "generation", "seq", "payload"))
    integer(message["version"], "version", 1)
    integer(message["seq"], "seq")
    token(message["generation"], "generation")
    if (message["version"] != VERSION or message["kind"] != kind
            or message["generation"] != generation or message["seq"] != seq):
        raise ProtocolError("wrong version, kind, generation or event sequence")
    return message["payload"]


@dataclass(frozen=True)
class Deployment:
    """An approved research deployment: the approval record and what it binds."""
    approval_id: str
    source_sha256: str
    manifest_sha256: str
    parameters: tuple  # ((name, int), ...) in the strategy's constructor order
    quantity: Decimal
    lookback: int

    def to_wire(self):
        return dict(approval_id=self.approval_id, source_sha256=self.source_sha256,
                    manifest_sha256=self.manifest_sha256,
                    parameters=[[name, value] for name, value in self.parameters],
                    quantity=str(self.quantity), lookback=self.lookback)

    @classmethod
    def from_wire(cls, value):
        exact(value, ("approval_id", "source_sha256", "manifest_sha256", "parameters", "quantity", "lookback"))
        if type(value["approval_id"]) is not str or not _APPROVAL_ID.fullmatch(value["approval_id"]):
            raise ProtocolError("invalid deployment approval id")
        for name in ("source_sha256", "manifest_sha256"):
            if type(value[name]) is not str or not _SHA256.fullmatch(value[name]):
                raise ProtocolError(f"invalid deployment {name}")
        items = value["parameters"]
        if type(items) is not list or not 1 <= len(items) <= 8:
            raise ProtocolError("invalid deployment parameters")
        parameters = []
        for item in items:
            if (type(item) is not list or len(item) != 2 or type(item[0]) is not str
                    or not _TOKEN.fullmatch(item[0]) or type(item[1]) is not int
                    or not 0 <= item[1] <= MAX_INTEGER):
                raise ProtocolError("invalid deployment parameter")
            parameters.append((item[0], item[1]))
        if len({name for name, _ in parameters}) != len(parameters):
            raise ProtocolError("duplicate deployment parameter")
        quantity = decimal_text(value["quantity"], "deployment quantity", positive=True)
        lookback = integer(value["lookback"], "deployment lookback", 1)
        if lookback > MAX_BOT_LOOKBACK:
            raise ProtocolError("deployment lookback above the restart history limit")
        return cls(value["approval_id"], value["source_sha256"], value["manifest_sha256"],
                   tuple(parameters), quantity, lookback)


@dataclass(frozen=True)
class WorkerConfig:
    contract: ContractSpec
    timeframe_ms: int
    warmup_bars: int
    strategy_artifact: str | None = None
    strategy_id: str = STRATEGY_ID
    # None: the built-in SMA artifact with a v1 checkpoint. Set: an approved
    # research deployment, checkpoint v2 (no strategy state on the wire).
    deployment: Deployment | None = None

    @property
    def checkpoint_version(self):
        return 1 if self.deployment is None else 2

    def to_wire(self):
        if not isinstance(self.contract, ContractSpec):
            raise ProtocolError("contract must be ContractSpec")
        value = dict(strategy_id=self.strategy_id, strategy_version=STRATEGY_VERSION,
                    contract={f.name: (str(getattr(self.contract, f.name))
                              if isinstance(getattr(self.contract, f.name), Decimal)
                              else getattr(self.contract, f.name)) for f in fields(ContractSpec)},
                    timeframe_ms=self.timeframe_ms, warmup_bars=self.warmup_bars)
        if self.strategy_artifact is not None:
            value["strategy_artifact"] = self.strategy_artifact
        if self.deployment is not None:
            if self.strategy_artifact is None:
                raise ProtocolError("a deployment names its artifact version")
            value["deployment"] = self.deployment.to_wire()
        return value

    @classmethod
    def from_wire(cls, value):
        keys = ("strategy_id", "strategy_version", "contract", "timeframe_ms", "warmup_bars")
        optional = tuple(name for name in ("strategy_artifact", "deployment")
                         if type(value) is dict and name in value)
        exact(value, (*keys, *optional))
        if "deployment" in value and "strategy_artifact" not in value:
            raise ProtocolError("a deployment names its artifact version")
        artifact = value.get("strategy_artifact")
        if "strategy_artifact" in value and type(artifact) is not str:
            raise ProtocolError("unsupported registered strategy artifact")
        strategy_id = value["strategy_id"]
        if (type(strategy_id) is not str or type(value["strategy_version"]) is not int
                or value["strategy_version"] != STRATEGY_VERSION):
            raise ProtocolError("unsupported inspected strategy artifact")
        deployment = None if "deployment" not in value else Deployment.from_wire(value["deployment"])
        spec = exact(value["contract"], tuple(f.name for f in fields(ContractSpec)))
        if type(spec["inst_id"]) is not str or len(spec["inst_id"]) > 64:
            raise ProtocolError("invalid contract label")
        contract = ContractSpec(spec["inst_id"], **{
            key: decimal_text(spec[key], key, positive=True) for key in spec if key != "inst_id"})
        result = cls(contract, integer(value["timeframe_ms"], "timeframe_ms", 60_000),
                     integer(value["warmup_bars"], "warmup_bars"), artifact, strategy_id, deployment)
        try:
            if deployment is None:
                # Identity must resolve to exactly one approved manifest (fail-closed).
                strategy_registry.resolve(strategy_id, artifact)
            else:
                # A research artifact resolves only through an active local approval
                # whose every bound field matches this config (fail-closed).
                strategy_registry.resolve_deployment(result)
        except strategy_registry.RegistryError as exc:
            raise ProtocolError(f"unregistered strategy: {exc}") from exc
        price = contract.tick_size
        result.validate_bar(Candle(0, price, price, price, price))
        return result

    def validate_bar(self, bar):
        cfg = BacktestConfig(self.contract, self.timeframe_ms, Decimal("1"),
                             Decimal("0"), Decimal("0"), ())
        try:
            research._call(research._validate, cfg, (bar,), 0)
            integer(bar.open_time_ms + self.timeframe_ms, "close_time_ms")
        except (ValueError, TypeError, InvalidOperation) as exc:
            raise ProtocolError(str(exc)) from exc


@dataclass(frozen=True)
class Checkpoint:
    config: WorkerConfig
    event_seq: int = 0
    last_open_time_ms: int | None = None
    closes: tuple[Decimal, ...] = ()

    def to_wire(self):
        if any(not isinstance(price, Decimal) for price in self.closes):
            raise ProtocolError("checkpoint closes must be Decimal")
        if self.config.checkpoint_version == 2:
            if self.closes:
                raise ProtocolError("v2 checkpoint carries no strategy state")
            return dict(config=self.config.to_wire(), event_seq=self.event_seq,
                        last_open_time_ms=self.last_open_time_ms)
        return dict(config=self.config.to_wire(), event_seq=self.event_seq,
                    last_open_time_ms=self.last_open_time_ms,
                    closes=[str(price) for price in self.closes])

    @classmethod
    def from_wire(cls, value, config):
        if config.checkpoint_version == 2:
            exact(value, ("config", "event_seq", "last_open_time_ms"))
        else:
            exact(value, ("config", "event_seq", "last_open_time_ms", "closes"))
        if WorkerConfig.from_wire(value["config"]) != config:
            raise ProtocolError("checkpoint artifact/config mismatch")
        seq = integer(value["event_seq"], "event_seq")
        if config.checkpoint_version == 2:
            last = value["last_open_time_ms"]
            if seq == 0:
                if last is not None:
                    raise ProtocolError("initial checkpoint cannot have a timestamp")
            else:
                integer(last, "last_open_time_ms")
                if last < (seq - 1) * config.timeframe_ms:
                    raise ProtocolError("checkpoint sequence exceeds elapsed bars")
                integer(last + config.timeframe_ms, "close_time_ms")
            return cls(config, seq, last, ())
        if type(value["closes"]) is not list or len(value["closes"]) != min(seq, 2):
            raise ProtocolError("invalid SMA checkpoint window")
        closes = tuple(decimal_text(p, "checkpoint close", positive=True) for p in value["closes"])
        last = value["last_open_time_ms"]
        if seq == 0:
            if last is not None:
                raise ProtocolError("initial checkpoint cannot have a timestamp")
        else:
            integer(last, "last_open_time_ms")
            if last < (seq - 1) * config.timeframe_ms:
                raise ProtocolError("checkpoint sequence exceeds elapsed bars")
            for price in closes:
                config.validate_bar(Candle(last, price, price, price, price))
        if seq and seq >= config.warmup_bars and len(closes) < 2:
            raise ProtocolError("checkpoint is not ready at evaluation boundary")
        return cls(config, seq, last, closes)


def bar_to_wire(bar):
    return {f.name: str(getattr(bar, f.name)) if isinstance(getattr(bar, f.name), Decimal)
            else getattr(bar, f.name) for f in fields(Candle)}


def account_to_wire(account):
    if account is None:
        return None
    return {f.name: str(getattr(account, f.name)) if isinstance(getattr(account, f.name), Decimal)
            else getattr(account, f.name) for f in fields(AccountView)}


def history_to_wire(bars):
    """Compact restart history: [open_time_ms, open, high, low, close] per bar."""
    return [[bar.open_time_ms, str(bar.open), str(bar.high), str(bar.low), str(bar.close)] for bar in bars]


def parse_history(value, checkpoint):
    """The committed bars a v2 Worker re-feeds as warm-up before its next event.

    Exactly the last min(event_seq, lookback) bars, contiguous and ending at the
    checkpoint's last bar; a v1 checkpoint takes no history.
    """
    config = checkpoint.config
    if config.checkpoint_version != 2:
        if value not in (None, []):
            raise ProtocolError("v1 checkpoint takes no restart history")
        return ()
    if type(value) is not list or len(value) != min(checkpoint.event_seq, config.deployment.lookback):
        raise ProtocolError("restart history must hold the last lookback committed bars")
    bars = []
    for item in value:
        if type(item) is not list or len(item) != 5:
            raise ProtocolError("invalid restart history bar")
        bar = Candle(integer(item[0], "history open_time_ms"),
                     *(decimal_text(price, "history price", positive=True) for price in item[1:]))
        config.validate_bar(bar)
        if bars and bar.open_time_ms != bars[-1].open_time_ms + config.timeframe_ms:
            raise ProtocolError("restart history must be contiguous")
        bars.append(bar)
    if bars and bars[-1].open_time_ms != checkpoint.last_open_time_ms:
        raise ProtocolError("restart history must end at the checkpoint bar")
    return tuple(bars)


def parse_event(payload, checkpoint):
    exact(payload, ("bar", "account"))
    value = exact(payload["bar"], tuple(f.name for f in fields(Candle)))
    if value["closed"] is not True:
        raise ProtocolError("only Closed Bar input permitted")
    bar = Candle(integer(value["open_time_ms"], "open_time_ms"), **{
        key: decimal_text(value[key], key, positive=True) for key in ("open", "high", "low", "close")})
    config = checkpoint.config
    config.validate_bar(bar)
    if (checkpoint.last_open_time_ms is not None
            and bar.open_time_ms != checkpoint.last_open_time_ms + config.timeframe_ms):
        raise ProtocolError("bars must be contiguous; no replay or gap in D session")
    seq = integer(checkpoint.event_seq + 1, "event_seq", 1)
    warmup = seq <= config.warmup_bars
    if warmup:
        if payload["account"] is not None:
            raise ProtocolError("warm-up input must omit the account view")
        account = None
    else:
        value = exact(payload["account"], tuple(f.name for f in fields(AccountView)))
        account = AccountView(integer(value["time_ms"], "account time_ms"), **{
            key: decimal_text(value[key], key, derived=True) for key in value if key != "time_ms"})
        if account.time_ms != bar.open_time_ms + config.timeframe_ms:
            raise ProtocolError("account view must belong to this bar close")
    return bar, account, warmup


@dataclass(frozen=True)
class EventResult:
    event_seq: int
    target_position: Decimal | None
    checkpoint: Checkpoint
    ready: bool


def parse_result(payload, previous, bar, account, warmup):
    exact(payload, ("target", "checkpoint", "ready"))
    checkpoint = Checkpoint.from_wire(payload["checkpoint"], previous.config)
    deployment = previous.config.deployment
    closes = () if deployment is not None else (*previous.closes, bar.close)[-2:]
    expected = Checkpoint(previous.config, previous.event_seq + 1, bar.open_time_ms, closes)
    if checkpoint != expected:
        raise ProtocolError("checkpoint does not correspond to the supplied event")
    ready = payload["ready"]
    # v1: ready once two closes are held. v2: ready exactly once lookback bars
    # were fed, which is also what a restart re-feed reproduces.
    expected_ready = (len(checkpoint.closes) == 2 if deployment is None
                      else checkpoint.event_seq >= deployment.lookback)
    if type(ready) is not bool or ready != expected_ready:
        raise ProtocolError("invalid readiness result")
    if (not warmup or checkpoint.event_seq == previous.config.warmup_bars) and not ready:
        raise ProtocolError("strategy not ready at evaluation boundary")
    target = payload["target"]
    if warmup and target is not None:
        raise ProtocolError("warm-up cannot produce an intent")
    if target is not None:
        target = decimal_text(target, "target_position")
        spec = previous.config.contract
        try:
            with localcontext(research._CONTEXT):
                research._multiple(target, spec.lot_size, "target_position")
                delta = target - account.position
                research._multiple(delta, spec.lot_size, "order quantity")
                if ((target != 0 and abs(target) < spec.min_size)
                        or (delta != 0 and abs(delta) < spec.min_size)):
                    raise ValueError("target or order quantity below min_size")
        except (ValueError, InvalidOperation) as exc:
            raise ProtocolError(str(exc)) from exc
    return EventResult(checkpoint.event_seq, target, checkpoint, ready)
