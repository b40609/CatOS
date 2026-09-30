"""Bounded, data-only protocol for the first inspected SMA worker artifact."""

import asyncio
from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation, localcontext
import json
import re
import struct

from catos import research
from catos.research import AccountView, BacktestConfig, Candle, ContractSpec

VERSION = 1
MAX_FRAME = 65_536
MAX_DEPTH = 8
MAX_INTEGER = 2**63 - 1
STRATEGY_ID = "sma-trend"
STRATEGY_VERSION = 1
_NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


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
class WorkerConfig:
    contract: ContractSpec
    timeframe_ms: int
    warmup_bars: int
    strategy_artifact: str | None = None

    def to_wire(self):
        if not isinstance(self.contract, ContractSpec):
            raise ProtocolError("contract must be ContractSpec")
        value = dict(strategy_id=STRATEGY_ID, strategy_version=STRATEGY_VERSION,
                    contract={f.name: (str(getattr(self.contract, f.name))
                              if isinstance(getattr(self.contract, f.name), Decimal)
                              else getattr(self.contract, f.name)) for f in fields(ContractSpec)},
                    timeframe_ms=self.timeframe_ms, warmup_bars=self.warmup_bars)
        if self.strategy_artifact is not None:
            value["strategy_artifact"] = self.strategy_artifact
        return value

    @classmethod
    def from_wire(cls, value):
        keys = ("strategy_id", "strategy_version", "contract", "timeframe_ms", "warmup_bars")
        exact(value, (*keys, "strategy_artifact") if "strategy_artifact" in value else keys)
        artifact = value.get("strategy_artifact")
        if "strategy_artifact" in value and artifact != "sma-parameters-v1":
            raise ProtocolError("unsupported registered strategy artifact")
        if (value["strategy_id"] != STRATEGY_ID
                or type(value["strategy_version"]) is not int
                or value["strategy_version"] != STRATEGY_VERSION):
            raise ProtocolError("unsupported inspected strategy artifact")
        spec = exact(value["contract"], tuple(f.name for f in fields(ContractSpec)))
        if type(spec["inst_id"]) is not str or len(spec["inst_id"]) > 64:
            raise ProtocolError("invalid contract label")
        contract = ContractSpec(spec["inst_id"], **{
            key: decimal_text(spec[key], key, positive=True) for key in spec if key != "inst_id"})
        result = cls(contract, integer(value["timeframe_ms"], "timeframe_ms", 60_000),
                     integer(value["warmup_bars"], "warmup_bars"), artifact)
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
        return dict(config=self.config.to_wire(), event_seq=self.event_seq,
                    last_open_time_ms=self.last_open_time_ms,
                    closes=[str(price) for price in self.closes])

    @classmethod
    def from_wire(cls, value, config):
        exact(value, ("config", "event_seq", "last_open_time_ms", "closes"))
        if WorkerConfig.from_wire(value["config"]) != config:
            raise ProtocolError("checkpoint artifact/config mismatch")
        seq = integer(value["event_seq"], "event_seq")
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
    expected = Checkpoint(previous.config, previous.event_seq + 1, bar.open_time_ms,
                          (*previous.closes, bar.close)[-2:])
    if checkpoint != expected:
        raise ProtocolError("checkpoint does not correspond to the supplied event")
    ready = payload["ready"]
    if type(ready) is not bool or ready != (len(checkpoint.closes) == 2):
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
