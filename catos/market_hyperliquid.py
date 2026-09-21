"""Public-only Hyperliquid trade observations for P1-A market intelligence.

The module owns no credentials and performs no I/O at import time. Hyperliquid
public trades expose both counterparties, so one source trade is normalized
into a BUY observation for the buyer and a SELL observation for the seller.
No whale threshold or position direction is inferred here.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
import json
import re

from catos import ipc, research
from catos.market_collectors import CollectorScope, MarketCollectionError


HYPERLIQUID = "hyperliquid"
HYPERLIQUID_STREAM_URL = "wss://api.hyperliquid.xyz/ws"
_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}\Z")


@dataclass(frozen=True, slots=True)
class HyperliquidScope:
    symbol: str
    observed_at_ms: int

    def __post_init__(self):
        CollectorScope(self.symbol, self.observed_at_ms)

    @property
    def coin(self):
        return self.symbol.removesuffix("-USDT-SWAP")


@dataclass(frozen=True, slots=True)
class HyperliquidObservation:
    symbol: str
    observed_at_ms: int
    source_ms: int
    wallet_or_trader: str
    direction: str
    notional: Decimal
    notional_currency: str
    position_or_flow_type: str
    source: str
    source_id: str
    provenance: dict


@dataclass(frozen=True, slots=True)
class HyperliquidObservationBatch:
    symbol: str
    observed_at_ms: int
    observations: tuple[HyperliquidObservation, ...]
    issues: tuple[tuple[str, str], ...]


def issue_batch(scope: HyperliquidScope, code: str) -> HyperliquidObservationBatch:
    """Represent an unavailable source without fabricating numeric observations."""
    if not isinstance(scope, HyperliquidScope):
        raise ValueError("invalid_scope")
    try:
        ipc.token(code, "issue_code")
    except ipc.ProtocolError:
        raise ValueError("invalid_issue_code") from None
    return HyperliquidObservationBatch(
        scope.symbol, scope.observed_at_ms, (), (("hyperliquid_trades", code),))


def _decode_frame(frame, max_message_bytes):
    if isinstance(frame, str):
        raw = frame.encode("utf-8")
    elif isinstance(frame, bytes):
        raw = frame
    else:
        raise MarketCollectionError("malformed_stream_message")
    if len(raw) > max_message_bytes:
        raise MarketCollectionError("stream_message_too_large")

    def duplicate_guard(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result

    def forbidden(_):
        raise ValueError("float")

    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=duplicate_guard,
                          parse_float=forbidden, parse_constant=forbidden)
    except (UnicodeError, ValueError, json.JSONDecodeError, RecursionError):
        raise MarketCollectionError("malformed_stream_message") from None


def _positive_decimal(value, name):
    if type(value) is not str:
        raise MarketCollectionError(f"missing_{name}" if value is None else "malformed_trade")
    try:
        result = ipc.decimal_text(value, name, derived=True)
    except ipc.ProtocolError:
        raise MarketCollectionError("malformed_trade") from None
    if result <= 0:
        raise MarketCollectionError("malformed_trade")
    return result


def _bounded_integer(value, name):
    if value is None:
        raise MarketCollectionError("missing_identity")
    try:
        return ipc.integer(value, name)
    except ipc.ProtocolError:
        raise MarketCollectionError("malformed_trade") from None


def _wallets(value):
    if value is None:
        raise MarketCollectionError("missing_users")
    if type(value) is not list or len(value) != 2:
        raise MarketCollectionError("malformed_trade")
    result = []
    for item in value:
        if type(item) is not str or not _ADDRESS.fullmatch(item):
            raise MarketCollectionError("malformed_trade")
        result.append(item.lower())
    return tuple(result)


def _notional(price: Decimal, size: Decimal) -> Decimal:
    with localcontext(research._CONTEXT):
        result = price * size
    try:
        return ipc.decimal_text(str(result), "hyperliquid notional", derived=True)
    except ipc.ProtocolError:
        raise MarketCollectionError("malformed_trade") from None


def _trade_observations(scope, row):
    if type(row) is not dict:
        raise MarketCollectionError("malformed_trade")
    if row.get("coin") != scope.coin:
        raise MarketCollectionError("scope_mismatch")
    price = _positive_decimal(row.get("px"), "price")
    size = _positive_decimal(row.get("sz"), "size")
    source_ms = _bounded_integer(row.get("time"), "source_ms")
    tid = _bounded_integer(row.get("tid"), "trade_id")
    buyer, seller = _wallets(row.get("users"))
    if source_ms > scope.observed_at_ms:
        raise MarketCollectionError("source_time_after_observed")
    trade_hash = row.get("hash")
    if trade_hash is not None and type(trade_hash) is not str:
        raise MarketCollectionError("malformed_trade")
    source_side = row.get("side")
    if source_side is not None and type(source_side) is not str:
        raise MarketCollectionError("malformed_trade")
    notional = _notional(price, size)
    common = {
        "coin": scope.coin,
        "tid": tid,
        "hash": trade_hash,
        "source_side": source_side,
        "price_text": str(price),
        "size_text": str(size),
        "notional_currency": "USDC",
        "identity_rule": "time_coin_tid_plus_participant_role",
    }
    result = []
    for role, wallet, direction in (("buyer", buyer, "BUY"), ("seller", seller, "SELL")):
        provenance = dict(common)
        provenance["participant_role"] = role
        result.append(HyperliquidObservation(
            scope.symbol,
            scope.observed_at_ms,
            source_ms,
            wallet,
            direction,
            notional,
            "USDC",
            "PUBLIC_TRADE_PARTICIPANT",
            HYPERLIQUID,
            f"hyperliquid:{source_ms}:{scope.coin}:{tid}:{role}",
            provenance,
        ))
    return tuple(result)


def parse_hyperliquid_trades(scope: HyperliquidScope, frame,
                             *, max_message_bytes=262_144) -> HyperliquidObservationBatch:
    """Parse one public ``trades`` WebSocket message into replayable observations."""
    if not isinstance(scope, HyperliquidScope):
        raise ValueError("invalid_scope")
    if type(max_message_bytes) is not int or not 1_024 <= max_message_bytes <= 1_000_000:
        raise ValueError("invalid_message_limit")
    payload = _decode_frame(frame, max_message_bytes)
    if type(payload) is not dict or payload.get("channel") != "trades":
        raise MarketCollectionError("unexpected_stream_event")
    rows = payload.get("data")
    if type(rows) is not list:
        raise MarketCollectionError("malformed_stream_message")

    observations = []
    issues = []
    seen = {}
    for row in rows:
        try:
            pair = _trade_observations(scope, row)
        except MarketCollectionError as exc:
            if exc.code == "scope_mismatch":
                raise
            issues.append(("hyperliquid_trades", exc.code))
            continue
        for observation in pair:
            existing = seen.get(observation.source_id)
            if existing is None:
                seen[observation.source_id] = observation
                observations.append(observation)
            elif existing != observation:
                raise MarketCollectionError("trade_conflict")
    return HyperliquidObservationBatch(
        scope.symbol, scope.observed_at_ms, tuple(observations), tuple(issues))


class HyperliquidTradeStream:
    """Supervisor-owned fixed-host public stream adapter with no auth surface."""

    def __init__(self, scope: HyperliquidScope, *, open_timeout_s=5,
                 close_timeout_s=3, max_message_bytes=262_144, connector=None):
        if not isinstance(scope, HyperliquidScope):
            raise ValueError("invalid_scope")
        if type(open_timeout_s) not in (int, float) or not 0 < open_timeout_s <= 30:
            raise ValueError("invalid_open_timeout")
        if type(close_timeout_s) not in (int, float) or not 0 < close_timeout_s <= 30:
            raise ValueError("invalid_close_timeout")
        if type(max_message_bytes) is not int or not 1_024 <= max_message_bytes <= 1_000_000:
            raise ValueError("invalid_message_limit")
        self.scope = scope
        self.open_timeout_s = open_timeout_s
        self.close_timeout_s = close_timeout_s
        self.max_message_bytes = max_message_bytes
        self._connector = connector

    @property
    def url(self):
        return HYPERLIQUID_STREAM_URL

    @property
    def subscription_text(self):
        return json.dumps({
            "method": "subscribe",
            "subscription": {"type": "trades", "coin": self.scope.coin},
        }, separators=(",", ":"))

    def frames(self):
        connector = self._connector
        if connector is None:
            try:
                from websockets.sync.client import connect as connector
            except ImportError:
                raise MarketCollectionError("websockets_dependency_missing") from None
        try:
            connection = connector(
                self.url,
                open_timeout=self.open_timeout_s,
                close_timeout=self.close_timeout_s,
                max_size=self.max_message_bytes,
                max_queue=16,
                compression=None,
                proxy=None,
            )
            with connection as stream:
                stream.send(self.subscription_text)
                for frame in stream:
                    yield frame
        except MarketCollectionError:
            raise
        except Exception:
            raise MarketCollectionError("stream_transport_error") from None

    def bounded_frames(self, *, max_frames=20, recv_timeout_s=2):
        """Yield at most ``max_frames`` with a bounded wait for each frame."""
        if type(max_frames) is not int or not 1 <= max_frames <= 200:
            raise ValueError("invalid_max_frames")
        if type(recv_timeout_s) not in (int, float) or not 0 < recv_timeout_s <= 30:
            raise ValueError("invalid_recv_timeout")
        connector = self._connector
        if connector is None:
            try:
                from websockets.sync.client import connect as connector
            except ImportError:
                raise MarketCollectionError("websockets_dependency_missing") from None
        try:
            connection = connector(
                self.url,
                open_timeout=self.open_timeout_s,
                close_timeout=self.close_timeout_s,
                max_size=self.max_message_bytes,
                max_queue=16,
                compression=None,
                proxy=None,
            )
            with connection as stream:
                stream.send(self.subscription_text)
                for _ in range(max_frames):
                    try:
                        frame = stream.recv(timeout=recv_timeout_s)
                    except TimeoutError:
                        break
                    if frame is None:
                        break
                    yield frame
        except MarketCollectionError:
            raise
        except Exception:
            raise MarketCollectionError("stream_transport_error") from None


def collect_bounded_trades(scope: HyperliquidScope, *, stream=None,
                           max_frames=20, recv_timeout_s=2) -> HyperliquidObservationBatch:
    """Collect a bounded public-trade batch without inferring directional flow.

    ``scope.observed_at_ms`` is the collection-cycle start. Because trades may
    arrive during the bounded receive window, the persisted batch observation
    time is advanced to the latest valid trade source timestamp seen in those
    frames. The single-frame parser itself remains strict and still rejects a
    source timestamp after its supplied observation anchor.
    """
    if not isinstance(scope, HyperliquidScope):
        raise ValueError("invalid_scope")
    active_stream = HyperliquidTradeStream(scope) if stream is None else stream
    if getattr(active_stream, "scope", None) != scope or not callable(
            getattr(active_stream, "bounded_frames", None)):
        raise ValueError("invalid_stream")
    issues = []
    trade_frames = []
    latest_source_ms = scope.observed_at_ms
    try:
        frames = active_stream.bounded_frames(
            max_frames=max_frames, recv_timeout_s=recv_timeout_s)
        for frame in frames:
            try:
                payload = _decode_frame(frame, active_stream.max_message_bytes)
            except MarketCollectionError as exc:
                issues.append(("hyperliquid_trades", exc.code))
                continue
            if type(payload) is not dict or payload.get("channel") != "trades":
                continue
            trade_frames.append(frame)
            rows = payload.get("data")
            if type(rows) is list:
                for row in rows:
                    if type(row) is not dict:
                        continue
                    try:
                        source_ms = ipc.integer(row.get("time"), "source_ms")
                    except ipc.ProtocolError:
                        continue
                    latest_source_ms = max(latest_source_ms, source_ms)
    except MarketCollectionError as exc:
        return issue_batch(scope, exc.code)

    if not trade_frames:
        issues.append(("hyperliquid_trades", "no_trade_frame"))
        return HyperliquidObservationBatch(
            scope.symbol, scope.observed_at_ms, (), tuple(issues))

    effective_scope = HyperliquidScope(scope.symbol, latest_source_ms)
    observations = []
    seen = {}
    for frame in trade_frames:
        try:
            batch = parse_hyperliquid_trades(
                effective_scope, frame, max_message_bytes=active_stream.max_message_bytes)
        except MarketCollectionError as exc:
            issues.append(("hyperliquid_trades", exc.code))
            continue
        issues.extend(batch.issues)
        for observation in batch.observations:
            previous = seen.get(observation.source_id)
            if previous is None:
                seen[observation.source_id] = observation
                observations.append(observation)
            elif previous != observation:
                raise MarketCollectionError("trade_conflict")
    return HyperliquidObservationBatch(
        scope.symbol, effective_scope.observed_at_ms, tuple(observations), tuple(issues))
