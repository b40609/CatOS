"""Bounded public Binance aggTrade WebSocket ingestion for P0 market intelligence.

Network access belongs to the Supervisor. The parser and coverage buffer are
deterministic and credential-free. A trade window is marked complete only when
one uninterrupted stream coverage segment spans the full requested interval;
reconnects, parser/order errors, or buffer truncation never become valid CVD.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import json

from catos import ipc
from catos.market_collectors import BINANCE, CollectorScope, MarketCollectionError, MarketTrade
from catos.market_features import TradeWindow


BINANCE_FUTURES_STREAM_BASE = "wss://fstream.binance.com/ws"


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


def _decimal(value, name):
    if type(value) is not str:
        raise MarketCollectionError("malformed_stream_message")
    try:
        result = ipc.decimal_text(value, name, derived=True)
    except ipc.ProtocolError:
        raise MarketCollectionError("malformed_stream_message") from None
    if result <= 0:
        raise MarketCollectionError("malformed_stream_message")
    return result


def _integer(value, name):
    try:
        return ipc.integer(value, name)
    except ipc.ProtocolError:
        raise MarketCollectionError("malformed_stream_message") from None


def parse_binance_agg_trade(scope: CollectorScope, frame,
                            *, max_message_bytes=65_536) -> MarketTrade:
    """Parse one raw USD-M Futures ``<symbol>@aggTrade`` event."""
    if not isinstance(scope, CollectorScope):
        raise ValueError("invalid_scope")
    if type(max_message_bytes) is not int or not 1_024 <= max_message_bytes <= 1_000_000:
        raise ValueError("invalid_message_limit")
    payload = _decode_frame(frame, max_message_bytes)
    if type(payload) is not dict or payload.get("e") != "aggTrade":
        raise MarketCollectionError("unexpected_stream_event")
    if payload.get("s") != scope.binance_symbol:
        raise MarketCollectionError("scope_mismatch")
    trade_id = payload.get("a")
    if type(trade_id) is int:
        if trade_id < 0:
            raise MarketCollectionError("malformed_stream_message")
        trade_id = str(trade_id)
    if type(trade_id) is not str or not trade_id.isascii() or not trade_id.isdigit():
        raise MarketCollectionError("malformed_stream_message")
    stamp = _integer(payload.get("T"), "trade_time_ms")
    buyer_is_maker = payload.get("m")
    if type(buyer_is_maker) is not bool:
        raise MarketCollectionError("malformed_stream_message")
    return MarketTrade(
        BINANCE,
        scope.symbol,
        trade_id,
        stamp,
        _decimal(payload.get("p"), "trade_price"),
        _decimal(payload.get("q"), "trade_quantity"),
        "SELL" if buyer_is_maker else "BUY",
    )


@dataclass(frozen=True, slots=True)
class CoverageSegment:
    start_ms: int
    end_ms: int | None
    valid: bool

    def __post_init__(self):
        ipc.integer(self.start_ms, "coverage_start_ms")
        if self.end_ms is not None:
            ipc.integer(self.end_ms, "coverage_end_ms")
            if self.end_ms < self.start_ms:
                raise ValueError("invalid_coverage_segment")
        if type(self.valid) is not bool:
            raise ValueError("invalid_coverage_segment")


class TradeStreamBuffer:
    """Bounded in-memory trade stream with explicit continuity evidence."""

    def __init__(self, scope: CollectorScope, *, max_trades=200_000,
                 retention_ms=300_000, max_message_bytes=65_536):
        if not isinstance(scope, CollectorScope):
            raise ValueError("invalid_scope")
        if type(max_trades) is not int or not 1 <= max_trades <= 1_000_000:
            raise ValueError("invalid_trade_limit")
        if type(retention_ms) is not int or not 60_000 <= retention_ms <= 3_600_000:
            raise ValueError("invalid_retention")
        if type(max_message_bytes) is not int or not 1_024 <= max_message_bytes <= 1_000_000:
            raise ValueError("invalid_message_limit")
        self.scope = scope
        self.max_trades = max_trades
        self.retention_ms = retention_ms
        self.max_message_bytes = max_message_bytes
        self._trades = deque()
        self._by_id = {}
        self._segments = deque(maxlen=64)
        self._connected_at_ms = None
        self._coverage_at_ms = None
        self._current_valid = True
        self._last_key = None
        self._dropped_through_ms = None

    @property
    def connected(self):
        return self._connected_at_ms is not None

    def connect(self, observed_at_ms: int):
        ipc.integer(observed_at_ms, "observed_at_ms")
        if self.connected:
            raise ValueError("stream_already_connected")
        self._connected_at_ms = observed_at_ms
        self._coverage_at_ms = observed_at_ms
        self._current_valid = True

    def advance_coverage(self, observed_at_ms: int):
        ipc.integer(observed_at_ms, "observed_at_ms")
        if not self.connected:
            raise ValueError("stream_not_connected")
        if observed_at_ms < self._coverage_at_ms:
            raise ValueError("coverage_time_regression")
        self._coverage_at_ms = observed_at_ms

    def disconnect(self, observed_at_ms: int, *, clean=True):
        ipc.integer(observed_at_ms, "observed_at_ms")
        if not self.connected:
            raise ValueError("stream_not_connected")
        if observed_at_ms < self._coverage_at_ms:
            raise ValueError("coverage_time_regression")
        confirmed_end_ms = observed_at_ms if clean else self._coverage_at_ms
        self._segments.append(CoverageSegment(
            self._connected_at_ms, confirmed_end_ms, self._current_valid))
        self._connected_at_ms = None
        self._coverage_at_ms = None
        self._current_valid = True

    def mark_gap(self):
        if not self.connected:
            raise ValueError("stream_not_connected")
        self._current_valid = False

    def ingest(self, frame) -> bool:
        if not self.connected:
            raise ValueError("stream_not_connected")
        try:
            trade = parse_binance_agg_trade(
                self.scope, frame, max_message_bytes=self.max_message_bytes)
        except MarketCollectionError:
            self._current_valid = False
            raise
        existing = self._by_id.get(trade.trade_id)
        if existing is not None:
            if existing == trade:
                return False
            self._current_valid = False
            raise MarketCollectionError("trade_conflict")
        key = (trade.time_ms, len(trade.trade_id), trade.trade_id)
        if self._last_key is not None and key <= self._last_key:
            self._current_valid = False
            raise MarketCollectionError("stream_order_violation")
        self._last_key = key
        self._trades.append(trade)
        self._by_id[trade.trade_id] = trade
        self._evict(trade.time_ms)
        return True

    def _evict(self, newest_trade_ms):
        cutoff = newest_trade_ms - self.retention_ms
        while self._trades and (len(self._trades) > self.max_trades
                                or self._trades[0].time_ms < cutoff):
            dropped = self._trades.popleft()
            self._by_id.pop(dropped.trade_id, None)
            if self._dropped_through_ms is None or dropped.time_ms > self._dropped_through_ms:
                self._dropped_through_ms = dropped.time_ms

    def _coverage_segments(self):
        result = list(self._segments)
        if self.connected:
            result.append(CoverageSegment(
                self._connected_at_ms, self._coverage_at_ms, self._current_valid))
        return result

    def window(self, start_ms: int, end_ms: int) -> TradeWindow:
        ipc.integer(start_ms, "trade_start_ms")
        ipc.integer(end_ms, "trade_end_ms")
        if end_ms <= start_ms:
            raise ValueError("invalid_trade_window")
        complete = any(
            segment.valid and segment.start_ms <= start_ms
            and segment.end_ms is not None and segment.end_ms >= end_ms
            for segment in self._coverage_segments()
        )
        if self._dropped_through_ms is not None and start_ms <= self._dropped_through_ms:
            complete = False
        trades = tuple(
            trade for trade in self._trades if start_ms <= trade.time_ms < end_ms)
        return TradeWindow(start_ms, end_ms, trades, complete)


class BinanceAggTradeStream:
    """Supervisor-owned fixed-host public stream adapter; no auth or user data."""

    def __init__(self, scope: CollectorScope, *, open_timeout_s=5,
                 close_timeout_s=3, max_message_bytes=65_536, connector=None):
        if not isinstance(scope, CollectorScope):
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
        return f"{BINANCE_FUTURES_STREAM_BASE}/{self.scope.binance_symbol.lower()}@aggTrade"

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
                for frame in stream:
                    yield frame
        except MarketCollectionError:
            raise
        except Exception:
            raise MarketCollectionError("stream_transport_error") from None
