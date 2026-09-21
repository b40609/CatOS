"""Public-only market-intelligence collectors.

The module owns no credentials and performs no I/O at import time. Network I/O
is restricted to a fixed GET allowlist. Callers provide the observation time so
collection can be replayed deterministically in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import http.client
import json
import re
import ssl
from typing import Protocol
from urllib.parse import urlencode

from catos import ipc


OKX = "okx"
BINANCE = "binance"
BYBIT = "bybit"
GATE = "gate"
COINBASE = "coinbase"
BITGET = "bitget"
_OKX_HOST = "www.okx.com"
_BINANCE_HOST = "fapi.binance.com"
_BINANCE_SPOT_HOST = "api.binance.com"
_BYBIT_HOST = "api.bybit.com"
_GATE_HOST = "api.gateio.ws"
_COINBASE_HOST = "api.coinbase.com"
_BITGET_HOST = "api.bitget.com"
_SYMBOL = re.compile(r"[A-Z0-9]{1,32}-USDT-SWAP\Z")
_BINANCE_SYMBOL = re.compile(r"[A-Z0-9]{1,32}USDT\Z")


class MarketCollectionError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class Endpoint:
    alias: str
    venue: str
    host: str
    path: str
    allowed_params: frozenset[str]


ENDPOINTS = {
    "okx_instruments": Endpoint("okx_instruments", OKX, _OKX_HOST, "/api/v5/public/instruments",
                                frozenset(("instType",))),
    "okx_tickers": Endpoint("okx_tickers", OKX, _OKX_HOST, "/api/v5/market/tickers",
                            frozenset(("instType",))),
    "okx_ticker": Endpoint("okx_ticker", OKX, _OKX_HOST, "/api/v5/market/ticker",
                           frozenset(("instId",))),
    "okx_oi": Endpoint("okx_oi", OKX, _OKX_HOST, "/api/v5/public/open-interest",
                       frozenset(("instType", "instId"))),
    "okx_funding": Endpoint("okx_funding", OKX, _OKX_HOST, "/api/v5/public/funding-rate",
                            frozenset(("instId",))),
    "binance_exchange_info": Endpoint("binance_exchange_info", BINANCE, _BINANCE_HOST,
                                      "/fapi/v1/exchangeInfo", frozenset()),
    "binance_ticker": Endpoint("binance_ticker", BINANCE, _BINANCE_HOST, "/fapi/v1/ticker/24hr",
                               frozenset(("symbol",))),
    "binance_oi": Endpoint("binance_oi", BINANCE, _BINANCE_HOST, "/fapi/v1/openInterest",
                           frozenset(("symbol",))),
    "binance_premium": Endpoint("binance_premium", BINANCE, _BINANCE_HOST, "/fapi/v1/premiumIndex",
                                frozenset(("symbol",))),
    "binance_top_lsr": Endpoint("binance_top_lsr", BINANCE, _BINANCE_HOST,
                                "/futures/data/topLongShortPositionRatio",
                                frozenset(("symbol", "period", "limit"))),
    "binance_taker": Endpoint("binance_taker", BINANCE, _BINANCE_HOST,
                              "/futures/data/takerlongshortRatio",
                              frozenset(("symbol", "period", "limit"))),
    "okx_candles": Endpoint("okx_candles", OKX, _OKX_HOST, "/api/v5/market/candles",
                            frozenset(("instId", "bar", "limit"))),
    "binance_klines": Endpoint("binance_klines", BINANCE, _BINANCE_HOST, "/fapi/v1/klines",
                               frozenset(("symbol", "interval", "limit"))),
    "binance_agg_trades": Endpoint("binance_agg_trades", BINANCE, _BINANCE_HOST,
                                   "/fapi/v1/aggTrades", frozenset(("symbol", "limit"))),
    "okx_spot_books": Endpoint("okx_spot_books", OKX, _OKX_HOST, "/api/v5/market/books",
                               frozenset(("instId", "sz"))),
    "binance_spot_depth": Endpoint("binance_spot_depth", BINANCE, _BINANCE_SPOT_HOST,
                                   "/api/v3/depth", frozenset(("symbol", "limit"))),
    "bybit_spot_orderbook": Endpoint("bybit_spot_orderbook", BYBIT, _BYBIT_HOST,
                                     "/v5/market/orderbook",
                                     frozenset(("category", "symbol", "limit"))),
    "gate_spot_orderbook": Endpoint("gate_spot_orderbook", GATE, _GATE_HOST,
                                    "/api/v4/spot/order_book",
                                    frozenset(("currency_pair", "limit", "with_id"))),
    "coinbase_spot_orderbook": Endpoint("coinbase_spot_orderbook", COINBASE, _COINBASE_HOST,
                                        "/api/v3/brokerage/market/product_book",
                                        frozenset(("product_id", "limit"))),
    "bitget_spot_orderbook": Endpoint("bitget_spot_orderbook", BITGET, _BITGET_HOST,
                                      "/api/v2/spot/market/orderbook",
                                      frozenset(("symbol", "type", "limit"))),
}

_INTERVALS = {
    "5m": ("5m", "5m", 300_000),
    "15m": ("15m", "15m", 900_000),
    "1h": ("1H", "1h", 3_600_000),
    "4h": ("4H", "4h", 14_400_000),
}


@dataclass(frozen=True, slots=True)
class PublicRequest:
    endpoint: Endpoint
    params: tuple[tuple[str, str], ...] = ()
    timeout_ms: int = 5_000
    max_body_bytes: int = 2_000_000

    def __post_init__(self):
        if self.endpoint != ENDPOINTS.get(self.endpoint.alias):
            raise ValueError("invalid_endpoint")
        if type(self.params) is not tuple or len(dict(self.params)) != len(self.params):
            raise ValueError("invalid_params")
        for key, value in self.params:
            if key not in self.endpoint.allowed_params or type(value) is not str or not value or len(value) > 128:
                raise ValueError("invalid_params")
            if any(ord(char) < 33 or ord(char) > 126 for char in value):
                raise ValueError("invalid_params")
        if type(self.timeout_ms) is not int or not 1 <= self.timeout_ms <= 30_000:
            raise ValueError("invalid_timeout")
        if type(self.max_body_bytes) is not int or not 1 <= self.max_body_bytes <= 2_000_000:
            raise ValueError("invalid_body_limit")


class PublicTransport(Protocol):
    def fetch(self, request: PublicRequest):
        """Return decoded JSON for exactly one fixed public GET request."""


class HTTPSPublicTransport:
    """Direct verified-TLS transport with no auth, redirects, cookies or proxy use."""

    def fetch(self, request: PublicRequest):
        if not isinstance(request, PublicRequest):
            raise MarketCollectionError("invalid_request")
        target = request.endpoint.path
        if request.params:
            target += "?" + urlencode(request.params)
        connection = http.client.HTTPSConnection(
            request.endpoint.host, port=443, timeout=request.timeout_ms / 1000,
            context=ssl.create_default_context())
        response = None
        try:
            connection.request("GET", target, body=None,
                               headers={"Accept": "application/json", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status != 200:
                raise MarketCollectionError("http_error")
            encoding = response.getheader("Content-Encoding")
            if encoding and encoding.lower() != "identity":
                raise MarketCollectionError("unsupported_content_encoding")
            length = response.getheader("Content-Length")
            if length is not None:
                if not length.isascii() or not length.isdigit() or len(length) > 12:
                    raise MarketCollectionError("invalid_content_length")
                if int(length) > request.max_body_bytes:
                    raise MarketCollectionError("body_limit_exceeded")
            body = response.read(request.max_body_bytes + 1)
            if len(body) > request.max_body_bytes:
                raise MarketCollectionError("body_limit_exceeded")
            return _decode_json(body)
        except MarketCollectionError:
            raise
        except Exception:
            raise MarketCollectionError("transport_error") from None
        finally:
            if response is not None:
                response.close()
            connection.close()


@dataclass(frozen=True, slots=True)
class CollectorScope:
    symbol: str
    observed_at_ms: int

    def __post_init__(self):
        if type(self.symbol) is not str or not _SYMBOL.fullmatch(self.symbol):
            raise ValueError("invalid_symbol")
        ipc.integer(self.observed_at_ms, "observed_at_ms")

    @property
    def binance_symbol(self):
        result = self.symbol.removesuffix("-SWAP").replace("-", "")
        if not _BINANCE_SYMBOL.fullmatch(result):
            raise ValueError("invalid_binance_symbol")
        return result


@dataclass(frozen=True, slots=True)
class InstrumentRef:
    symbol: str
    venue: str
    venue_inst_id: str
    base: str
    quote: str
    active: bool


@dataclass(frozen=True, slots=True)
class VenueMarketSnapshot:
    venue: str
    symbol: str
    observed_at_ms: int
    source_ms: int | None
    price: Decimal
    volume_24h: Decimal | None
    volume_unit: str | None
    change_24h_pct: Decimal | None


@dataclass(frozen=True, slots=True)
class VenueDerivativeSnapshot:
    venue: str
    symbol: str
    observed_at_ms: int
    source_ms: int | None
    oi: Decimal | None
    oi_unit: str | None
    oi_notional_usd: Decimal | None
    funding: Decimal | None
    top_position_lsr: Decimal | None
    taker_buy_ratio: Decimal | None


@dataclass(frozen=True, slots=True)
class PublicMarketBatch:
    symbol: str
    observed_at_ms: int
    markets: tuple[VenueMarketSnapshot, ...]
    derivatives: tuple[VenueDerivativeSnapshot, ...]
    issues: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class MarketCandle:
    venue: str
    symbol: str
    interval: str
    open_time_ms: int
    timeframe_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    volume_unit: str | None
    closed: bool


@dataclass(frozen=True, slots=True)
class MarketTrade:
    venue: str
    symbol: str
    trade_id: str
    time_ms: int
    price: Decimal
    base_quantity: Decimal
    aggressor_side: str


@dataclass(frozen=True, slots=True)
class FeatureInputBatch:
    symbol: str
    observed_at_ms: int
    interval: str
    candles: tuple[MarketCandle, ...]
    candle_venue: str | None
    trade_tail: tuple[MarketTrade, ...]
    trade_venue: str | None
    trade_window_complete: bool
    issues: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class UniverseMarketCollection:
    instruments: tuple[InstrumentRef, ...]
    batches: tuple[PublicMarketBatch, ...]
    issues: tuple[tuple[str, str], ...]


def _decode_json(body):
    if type(body) is not bytes:
        raise MarketCollectionError("malformed_response")

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
        return json.loads(body.decode("utf-8"), object_pairs_hook=duplicate_guard,
                          parse_float=forbidden, parse_constant=forbidden)
    except (UnicodeError, ValueError, json.JSONDecodeError, RecursionError):
        raise MarketCollectionError("malformed_response") from None


def _decimal(value, name, *, positive=False):
    if type(value) is not str:
        raise MarketCollectionError("malformed_response")
    try:
        result = ipc.decimal_text(value, name, derived=True)
        if positive and result <= 0:
            raise ipc.ProtocolError(f"invalid {name}")
        return result
    except ipc.ProtocolError:
        raise MarketCollectionError("malformed_response") from None


def _integer(value, name):
    try:
        return ipc.integer(value, name)
    except ipc.ProtocolError:
        raise MarketCollectionError("malformed_response") from None


def _source_ms(value):
    if value in (None, ""):
        return None
    if type(value) is str and value.isascii() and value.isdigit() and len(value) <= 16:
        value = int(value)
    if type(value) is not int:
        raise MarketCollectionError("malformed_response")
    return _integer(value, "source_ms")


def _one_okx(payload):
    if type(payload) is not dict or payload.get("code") != "0" or type(payload.get("data")) is not list:
        raise MarketCollectionError("api_error")
    if len(payload["data"]) != 1 or type(payload["data"][0]) is not dict:
        raise MarketCollectionError("malformed_response")
    return payload["data"][0]


def _safe_change_pct(last, open_24h):
    if open_24h == 0:
        return None
    return (last - open_24h) * Decimal("100") / open_24h


def _okx_market_row(scope, row):
    if type(row) is not dict:
        raise MarketCollectionError("malformed_response")
    if row.get("instId") != scope.symbol:
        raise MarketCollectionError("scope_mismatch")
    last = _decimal(row.get("last"), "okx last", positive=True)
    opened = _decimal(row.get("open24h"), "okx open24h", positive=True)
    volume = _decimal(row.get("volCcy24h"), "okx volume24h")
    return VenueMarketSnapshot(OKX, scope.symbol, scope.observed_at_ms, _source_ms(row.get("ts")),
                               last, volume, "currency", _safe_change_pct(last, opened))


def _okx_market(scope, payload):
    return _okx_market_row(scope, _one_okx(payload))


def _okx_oi(scope, payload):
    row = _one_okx(payload)
    if row.get("instId") != scope.symbol:
        raise MarketCollectionError("scope_mismatch")
    return _decimal(row.get("oi"), "okx oi"), _decimal(row.get("oiUsd"), "okx oi usd"), _source_ms(row.get("ts"))


def _okx_funding(scope, payload):
    row = _one_okx(payload)
    if row.get("instId") != scope.symbol:
        raise MarketCollectionError("scope_mismatch")
    return _decimal(row.get("fundingRate"), "okx funding"), _source_ms(row.get("fundingTime"))


def _binance_market_row(scope, payload):
    if type(payload) is not dict or payload.get("symbol") != scope.binance_symbol:
        raise MarketCollectionError("scope_mismatch")
    return VenueMarketSnapshot(
        BINANCE, scope.symbol, scope.observed_at_ms, _source_ms(payload.get("closeTime")),
        _decimal(payload.get("lastPrice"), "binance last", positive=True),
        _decimal(payload.get("quoteVolume"), "binance quote volume"), "quote",
        _decimal(payload.get("priceChangePercent"), "binance change pct"))


def _binance_market(scope, payload):
    return _binance_market_row(scope, payload)


def _binance_oi(scope, payload):
    if type(payload) is not dict or payload.get("symbol") != scope.binance_symbol:
        raise MarketCollectionError("scope_mismatch")
    return _decimal(payload.get("openInterest"), "binance oi"), _source_ms(payload.get("time"))


def _binance_funding(scope, payload):
    if type(payload) is not dict or payload.get("symbol") != scope.binance_symbol:
        raise MarketCollectionError("scope_mismatch")
    return _decimal(payload.get("lastFundingRate"), "binance funding"), _source_ms(payload.get("time"))


def _latest_ratio(scope, payload, ratio_field):
    if type(payload) is not list or not payload:
        raise MarketCollectionError("malformed_response")
    row = payload[-1]
    if type(row) is not dict or row.get("symbol") != scope.binance_symbol:
        raise MarketCollectionError("scope_mismatch")
    return _decimal(row.get(ratio_field), "binance ratio"), _source_ms(row.get("timestamp"))


def _validate_ohlc(open_, high, low, close):
    if not low <= min(open_, close) <= max(open_, close) <= high:
        raise MarketCollectionError("malformed_response")


def _okx_candles(scope, payload, interval):
    if type(payload) is not dict or payload.get("code") != "0" or type(payload.get("data")) is not list:
        raise MarketCollectionError("api_error")
    _, _, timeframe_ms = _INTERVALS[interval]
    result = []
    for raw in payload["data"]:
        if type(raw) is not list or len(raw) < 9 or raw[8] not in ("0", "1"):
            raise MarketCollectionError("malformed_response")
        if raw[8] != "1":
            continue
        stamp = _source_ms(raw[0])
        open_ = _decimal(raw[1], "okx candle open", positive=True)
        high = _decimal(raw[2], "okx candle high", positive=True)
        low = _decimal(raw[3], "okx candle low", positive=True)
        close = _decimal(raw[4], "okx candle close", positive=True)
        volume = _decimal(raw[6], "okx candle volume")
        _validate_ohlc(open_, high, low, close)
        result.append(MarketCandle(OKX, scope.symbol, interval, stamp, timeframe_ms,
                                   open_, high, low, close, volume, "currency", True))
    result.sort(key=lambda item: item.open_time_ms)
    return tuple(result)


def _binance_candles(scope, payload, interval):
    if type(payload) is not list:
        raise MarketCollectionError("malformed_response")
    _, _, timeframe_ms = _INTERVALS[interval]
    result = []
    for raw in payload:
        if type(raw) is not list or len(raw) < 7:
            raise MarketCollectionError("malformed_response")
        stamp = _source_ms(raw[0])
        open_ = _decimal(raw[1], "binance candle open", positive=True)
        high = _decimal(raw[2], "binance candle high", positive=True)
        low = _decimal(raw[3], "binance candle low", positive=True)
        close = _decimal(raw[4], "binance candle close", positive=True)
        volume = _decimal(raw[5], "binance candle volume")
        close_time = _source_ms(raw[6])
        if close_time is None or close_time >= scope.observed_at_ms:
            continue
        _validate_ohlc(open_, high, low, close)
        result.append(MarketCandle(BINANCE, scope.symbol, interval, stamp, timeframe_ms,
                                   open_, high, low, close, volume, "base", True))
    result.sort(key=lambda item: item.open_time_ms)
    return tuple(result)


def _binance_trades(scope, payload):
    if type(payload) is not list:
        raise MarketCollectionError("malformed_response")
    result = []
    for row in payload:
        if type(row) is not dict:
            raise MarketCollectionError("malformed_response")
        trade_id = row.get("a")
        if type(trade_id) is int:
            trade_id = str(trade_id)
        if type(trade_id) is not str or not trade_id.isascii() or not trade_id.isdigit():
            raise MarketCollectionError("malformed_response")
        price = _decimal(row.get("p"), "binance trade price", positive=True)
        quantity = _decimal(row.get("q"), "binance trade quantity", positive=True)
        stamp = _source_ms(row.get("T"))
        buyer_is_maker = row.get("m")
        if type(buyer_is_maker) is not bool:
            raise MarketCollectionError("malformed_response")
        result.append(MarketTrade(BINANCE, scope.symbol, trade_id, stamp, price, quantity,
                                  "SELL" if buyer_is_maker else "BUY"))
    result.sort(key=lambda item: (item.time_ms, int(item.trade_id)))
    return tuple(result)


def _attempt(transport, request, issues):
    try:
        return transport.fetch(request)
    except MarketCollectionError as exc:
        issues.append((request.endpoint.alias, exc.code))
        return None
    except Exception:
        issues.append((request.endpoint.alias, "transport_error"))
        return None


def collect_symbol(scope: CollectorScope, transport: PublicTransport) -> PublicMarketBatch:
    """Collect one symbol from fixed public endpoints; missing sources stay missing."""
    if not isinstance(scope, CollectorScope) or not callable(getattr(transport, "fetch", None)):
        raise ValueError("invalid_collector_configuration")
    issues = []
    markets = []
    derivatives = []

    okx_ticker = _attempt(transport, PublicRequest(ENDPOINTS["okx_ticker"], (("instId", scope.symbol),)), issues)
    if okx_ticker is not None:
        try:
            markets.append(_okx_market(scope, okx_ticker))
        except MarketCollectionError as exc:
            issues.append(("okx_ticker", exc.code))

    okx_oi = _attempt(transport, PublicRequest(ENDPOINTS["okx_oi"],
                                              (("instType", "SWAP"), ("instId", scope.symbol))), issues)
    okx_funding = _attempt(transport, PublicRequest(ENDPOINTS["okx_funding"], (("instId", scope.symbol),)), issues)
    if okx_oi is not None or okx_funding is not None:
        oi = oi_usd = funding = None
        source_times = []
        if okx_oi is not None:
            try:
                oi, oi_usd, stamp = _okx_oi(scope, okx_oi)
                if stamp is not None:
                    source_times.append(stamp)
            except MarketCollectionError as exc:
                issues.append(("okx_oi", exc.code))
        if okx_funding is not None:
            try:
                funding, stamp = _okx_funding(scope, okx_funding)
                if stamp is not None:
                    source_times.append(stamp)
            except MarketCollectionError as exc:
                issues.append(("okx_funding", exc.code))
        if oi is not None or funding is not None:
            derivatives.append(VenueDerivativeSnapshot(
                OKX, scope.symbol, scope.observed_at_ms, max(source_times) if source_times else None,
                oi, "contracts" if oi is not None else None, oi_usd, funding, None, None))

    binance_symbol = scope.binance_symbol
    b_ticker = _attempt(transport, PublicRequest(ENDPOINTS["binance_ticker"], (("symbol", binance_symbol),)), issues)
    if b_ticker is not None:
        try:
            markets.append(_binance_market(scope, b_ticker))
        except MarketCollectionError as exc:
            issues.append(("binance_ticker", exc.code))

    b_oi = _attempt(transport, PublicRequest(ENDPOINTS["binance_oi"], (("symbol", binance_symbol),)), issues)
    b_funding = _attempt(transport, PublicRequest(ENDPOINTS["binance_premium"], (("symbol", binance_symbol),)), issues)
    b_lsr = _attempt(transport, PublicRequest(ENDPOINTS["binance_top_lsr"],
                                             (("symbol", binance_symbol), ("period", "5m"), ("limit", "2"))), issues)
    b_taker = _attempt(transport, PublicRequest(ENDPOINTS["binance_taker"],
                                               (("symbol", binance_symbol), ("period", "5m"), ("limit", "2"))), issues)
    oi = funding = top_lsr = taker_buy_ratio = None
    source_times = []
    if b_oi is not None:
        try:
            oi, stamp = _binance_oi(scope, b_oi)
            if stamp is not None:
                source_times.append(stamp)
        except MarketCollectionError as exc:
            issues.append(("binance_oi", exc.code))
    if b_funding is not None:
        try:
            funding, stamp = _binance_funding(scope, b_funding)
            if stamp is not None:
                source_times.append(stamp)
        except MarketCollectionError as exc:
            issues.append(("binance_premium", exc.code))
    if b_lsr is not None:
        try:
            top_lsr, stamp = _latest_ratio(scope, b_lsr, "longShortRatio")
            if stamp is not None:
                source_times.append(stamp)
        except MarketCollectionError as exc:
            issues.append(("binance_top_lsr", exc.code))
    if b_taker is not None:
        try:
            buy_sell, stamp = _latest_ratio(scope, b_taker, "buySellRatio")
            taker_buy_ratio = buy_sell / (Decimal("1") + buy_sell)
            if stamp is not None:
                source_times.append(stamp)
        except (MarketCollectionError, ArithmeticError) as exc:
            issues.append(("binance_taker", exc.code if isinstance(exc, MarketCollectionError) else "malformed_response"))
    if any(value is not None for value in (oi, funding, top_lsr, taker_buy_ratio)):
        derivatives.append(VenueDerivativeSnapshot(
            BINANCE, scope.symbol, scope.observed_at_ms, max(source_times) if source_times else None,
            oi, "base" if oi is not None else None, None, funding, top_lsr, taker_buy_ratio))

    if not markets:
        issues.append(("market", "no_market_source"))
    return PublicMarketBatch(scope.symbol, scope.observed_at_ms, tuple(markets), tuple(derivatives), tuple(issues))


def collect_oi_snapshot(scope: CollectorScope, transport: PublicTransport) -> PublicMarketBatch:
    """Collect a cadence-friendly OI snapshot with OKX-first bounded fallback.

    The normal symbol collector fans out to funding, top-trader and taker
    endpoints. OI cadence only needs one market price row plus one OI row so the
    existing persistence layer can derive same-venue 5m/1h/4h OI deltas. This
    path therefore uses two OKX public GETs on success and only falls back to
    the equivalent Binance ticker/OI endpoint when the corresponding OKX fact
    is unavailable.
    """
    if not isinstance(scope, CollectorScope) or not callable(getattr(transport, "fetch", None)):
        raise ValueError("invalid_collector_configuration")
    issues = []
    markets = []
    derivatives = []

    okx_ticker = _attempt(
        transport, PublicRequest(ENDPOINTS["okx_ticker"], (("instId", scope.symbol),)), issues)
    if okx_ticker is not None:
        try:
            markets.append(_okx_market(scope, okx_ticker))
        except MarketCollectionError as exc:
            issues.append(("okx_ticker", exc.code))

    okx_oi = _attempt(
        transport,
        PublicRequest(ENDPOINTS["okx_oi"], (("instType", "SWAP"), ("instId", scope.symbol))),
        issues,
    )
    if okx_oi is not None:
        try:
            oi, oi_usd, stamp = _okx_oi(scope, okx_oi)
            derivatives.append(VenueDerivativeSnapshot(
                OKX, scope.symbol, scope.observed_at_ms, stamp,
                oi, "contracts", oi_usd, None, None, None))
        except MarketCollectionError as exc:
            issues.append(("okx_oi", exc.code))

    if not markets:
        payload = _attempt(
            transport,
            PublicRequest(ENDPOINTS["binance_ticker"], (("symbol", scope.binance_symbol),)),
            issues,
        )
        if payload is not None:
            try:
                markets.append(_binance_market(scope, payload))
            except MarketCollectionError as exc:
                issues.append(("binance_ticker", exc.code))

    if not any(item.oi is not None for item in derivatives):
        payload = _attempt(
            transport,
            PublicRequest(ENDPOINTS["binance_oi"], (("symbol", scope.binance_symbol),)),
            issues,
        )
        if payload is not None:
            try:
                oi, stamp = _binance_oi(scope, payload)
                derivatives.append(VenueDerivativeSnapshot(
                    BINANCE, scope.symbol, scope.observed_at_ms, stamp,
                    oi, "base", None, None, None, None))
            except MarketCollectionError as exc:
                issues.append(("binance_oi", exc.code))

    if not markets:
        issues.append(("market", "no_market_source"))
    if not any(item.oi is not None for item in derivatives):
        issues.append(("oi", "no_oi_source"))
    return PublicMarketBatch(
        scope.symbol, scope.observed_at_ms, tuple(markets), tuple(derivatives), tuple(issues))


def collect_feature_inputs(scope: CollectorScope, transport: PublicTransport, *, interval="15m",
                           candle_limit=120, trade_limit=500) -> FeatureInputBatch:
    """Collect closed candle history plus a bounded Binance trade tail.

    Candle history prefers OKX and falls back to Binance. The REST trade result
    is deliberately marked incomplete: latest-N trades cannot prove coverage of
    a time interval on active markets and therefore must not be used as CVD.
    """
    if not isinstance(scope, CollectorScope) or not callable(getattr(transport, "fetch", None)):
        raise ValueError("invalid_collector_configuration")
    if interval not in _INTERVALS:
        raise ValueError("unsupported_interval")
    if type(candle_limit) is not int or not 20 <= candle_limit <= 300:
        raise ValueError("invalid_candle_limit")
    if type(trade_limit) is not int or not 1 <= trade_limit <= 1000:
        raise ValueError("invalid_trade_limit")
    okx_bar, binance_interval, _ = _INTERVALS[interval]
    issues = []
    candles = ()
    candle_venue = None

    payload = _attempt(transport, PublicRequest(ENDPOINTS["okx_candles"],
        (("instId", scope.symbol), ("bar", okx_bar), ("limit", str(candle_limit)))), issues)
    if payload is not None:
        try:
            candles = _okx_candles(scope, payload, interval)
            if candles:
                candle_venue = OKX
        except MarketCollectionError as exc:
            issues.append(("okx_candles", exc.code))
            candles = ()

    if not candles:
        payload = _attempt(transport, PublicRequest(ENDPOINTS["binance_klines"],
            (("symbol", scope.binance_symbol), ("interval", binance_interval),
             ("limit", str(candle_limit)))), issues)
        if payload is not None:
            try:
                candles = _binance_candles(scope, payload, interval)
                if candles:
                    candle_venue = BINANCE
            except MarketCollectionError as exc:
                issues.append(("binance_klines", exc.code))
                candles = ()

    trade_tail = ()
    trade_venue = None
    payload = _attempt(transport, PublicRequest(ENDPOINTS["binance_agg_trades"],
        (("symbol", scope.binance_symbol), ("limit", str(trade_limit)))), issues)
    if payload is not None:
        try:
            trade_tail = _binance_trades(scope, payload)
            if trade_tail:
                trade_venue = BINANCE
        except MarketCollectionError as exc:
            issues.append(("binance_agg_trades", exc.code))
            trade_tail = ()

    if not candles:
        issues.append(("candles", "no_closed_candle_source"))
    return FeatureInputBatch(scope.symbol, scope.observed_at_ms, interval, candles, candle_venue,
                             trade_tail, trade_venue, False, tuple(issues))


def collect_universe(transport: PublicTransport, observed_at_ms: int) -> tuple[InstrumentRef, ...]:
    """Return active USDT perpetual instruments exposed by OKX and Binance."""
    ipc.integer(observed_at_ms, "observed_at_ms")
    if not callable(getattr(transport, "fetch", None)):
        raise ValueError("invalid_collector_configuration")
    result = []
    okx = transport.fetch(PublicRequest(ENDPOINTS["okx_instruments"], (("instType", "SWAP"),)))
    if type(okx) is not dict or okx.get("code") != "0" or type(okx.get("data")) is not list:
        raise MarketCollectionError("api_error")
    for row in okx["data"]:
        if type(row) is not dict or row.get("settleCcy") != "USDT":
            continue
        inst_id = row.get("instId")
        base = row.get("ctValCcy") or row.get("baseCcy")
        if type(inst_id) is str and _SYMBOL.fullmatch(inst_id) and type(base) is str:
            result.append(InstrumentRef(inst_id, OKX, inst_id, base, "USDT", row.get("state") == "live"))

    binance = transport.fetch(PublicRequest(ENDPOINTS["binance_exchange_info"]))
    if type(binance) is not dict or type(binance.get("symbols")) is not list:
        raise MarketCollectionError("malformed_response")
    for row in binance["symbols"]:
        if (type(row) is not dict or row.get("quoteAsset") != "USDT"
                or row.get("contractType") != "PERPETUAL"):
            continue
        venue_symbol, base = row.get("symbol"), row.get("baseAsset")
        if type(venue_symbol) is str and _BINANCE_SYMBOL.fullmatch(venue_symbol) and type(base) is str:
            result.append(InstrumentRef(f"{base}-USDT-SWAP", BINANCE, venue_symbol, base, "USDT",
                                        row.get("status") == "TRADING"))
    return tuple(sorted(result, key=lambda item: (item.symbol, item.venue)))


def collect_universe_markets(transport: PublicTransport, observed_at_ms: int) -> UniverseMarketCollection:
    """Collect the full active USDT perpetual market with five bounded public GETs.

    Tickers plus Binance's bulk premium-index response provide market prices and
    funding without per-symbol fan-out. OI/LSR/taker remain missing unless another
    verified public source materializes them; missing values are never synthesized.
    """
    ipc.integer(observed_at_ms, "observed_at_ms")
    if not callable(getattr(transport, "fetch", None)):
        raise ValueError("invalid_collector_configuration")
    instruments = collect_universe(transport, observed_at_ms)
    active = tuple(item for item in instruments if item.active)
    markets: dict[str, list[VenueMarketSnapshot]] = {}
    derivatives: dict[str, list[VenueDerivativeSnapshot]] = {}
    per_symbol_issues: dict[str, list[tuple[str, str]]] = {}
    global_issues: list[tuple[str, str]] = []
    venue_symbols: dict[str, dict[str, str]] = {OKX: {}, BINANCE: {}}
    for item in active:
        venue_symbols[item.venue][item.venue_inst_id] = item.symbol
        markets.setdefault(item.symbol, [])
        derivatives.setdefault(item.symbol, [])
        per_symbol_issues.setdefault(item.symbol, [])

    okx_payload = _attempt(
        transport, PublicRequest(ENDPOINTS["okx_tickers"], (("instType", "SWAP"),)), global_issues)
    if okx_payload is not None:
        if (type(okx_payload) is not dict or okx_payload.get("code") != "0"
                or type(okx_payload.get("data")) is not list):
            global_issues.append(("okx_tickers", "malformed_response"))
        else:
            seen = set()
            for row in okx_payload["data"]:
                inst_id = row.get("instId") if type(row) is dict else None
                symbol = venue_symbols[OKX].get(inst_id)
                if symbol is None:
                    continue
                try:
                    markets[symbol].append(_okx_market_row(CollectorScope(symbol, observed_at_ms), row))
                    seen.add(symbol)
                except MarketCollectionError as exc:
                    per_symbol_issues[symbol].append(("okx_tickers", exc.code))
            for symbol in set(venue_symbols[OKX].values()) - seen:
                per_symbol_issues[symbol].append(("okx_tickers", "missing_symbol"))

    binance_payload = _attempt(
        transport, PublicRequest(ENDPOINTS["binance_ticker"]), global_issues)
    if binance_payload is not None:
        if type(binance_payload) is not list:
            global_issues.append(("binance_ticker", "malformed_response"))
        else:
            seen = set()
            for row in binance_payload:
                venue_inst_id = row.get("symbol") if type(row) is dict else None
                symbol = venue_symbols[BINANCE].get(venue_inst_id)
                if symbol is None:
                    continue
                try:
                    markets[symbol].append(_binance_market_row(CollectorScope(symbol, observed_at_ms), row))
                    seen.add(symbol)
                except MarketCollectionError as exc:
                    per_symbol_issues[symbol].append(("binance_ticker", exc.code))
            for symbol in set(venue_symbols[BINANCE].values()) - seen:
                per_symbol_issues[symbol].append(("binance_ticker", "missing_symbol"))

    premium_payload = _attempt(
        transport, PublicRequest(ENDPOINTS["binance_premium"]), global_issues)
    if premium_payload is not None:
        if type(premium_payload) is not list:
            global_issues.append(("binance_premium", "malformed_response"))
        else:
            seen = set()
            for row in premium_payload:
                venue_inst_id = row.get("symbol") if type(row) is dict else None
                symbol = venue_symbols[BINANCE].get(venue_inst_id)
                if symbol is None:
                    continue
                try:
                    scope = CollectorScope(symbol, observed_at_ms)
                    funding, stamp = _binance_funding(scope, row)
                    derivatives[symbol].append(VenueDerivativeSnapshot(
                        BINANCE, symbol, observed_at_ms, stamp,
                        None, None, None, funding, None, None))
                    seen.add(symbol)
                except MarketCollectionError as exc:
                    per_symbol_issues[symbol].append(("binance_premium", exc.code))
            for symbol in set(venue_symbols[BINANCE].values()) - seen:
                per_symbol_issues[symbol].append(("binance_premium", "missing_symbol"))

    batches = tuple(
        PublicMarketBatch(symbol, observed_at_ms, tuple(markets[symbol]), tuple(derivatives[symbol]),
                          tuple(per_symbol_issues[symbol]))
        for symbol in sorted(markets)
    )
    return UniverseMarketCollection(instruments, batches, tuple(global_issues))
