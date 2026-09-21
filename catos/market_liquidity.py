"""Public spot-orderbook liquidity facts for the YAOZI observation surface.

The module is deliberately source-explicit and observation-only. It computes
quote notional available from the current mid price to +/-2% only when the
returned book visibly crosses the requested boundary. Otherwise the observed
notional is retained as a lower bound and full-depth fields remain missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext

from catos import research
from catos.market_collectors import (
    BITGET,
    BINANCE,
    BYBIT,
    COINBASE,
    GATE,
    OKX,
    CollectorScope,
    ENDPOINTS,
    MarketCollectionError,
    PublicRequest,
)


_TWO_PCT = Decimal("0.02")
_ONE = Decimal("1")


@dataclass(frozen=True, slots=True)
class LiquiditySourceRun:
    source: str
    venue: str
    symbol: str
    pair: str
    observed_at_ms: int
    status: str
    coverage: dict
    issues: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LiquiditySnapshot:
    source: str
    venue: str
    symbol: str
    pair: str
    observed_at_ms: int
    source_ms: int | None
    quote_currency: str
    best_bid: Decimal
    best_ask: Decimal
    mid: Decimal
    down_2pct_cost: Decimal | None
    up_2pct_cost: Decimal | None
    down_2pct_lower_bound: Decimal
    up_2pct_lower_bound: Decimal
    asymmetry: Decimal | None
    bid_levels: int
    ask_levels: int
    coverage: dict


@dataclass(frozen=True, slots=True)
class LiquidityBatch:
    symbol: str
    observed_at_ms: int
    snapshots: tuple[LiquiditySnapshot, ...]
    source_runs: tuple[LiquiditySourceRun, ...]
    issues: tuple[tuple[str, str], ...]


def _decimal(value, name):
    if type(value) is not str:
        raise MarketCollectionError("malformed_response")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError):
        raise MarketCollectionError("malformed_response") from None
    if not result.is_finite() or result <= 0:
        raise MarketCollectionError("malformed_response")
    return result


def _integer_text(value):
    if type(value) is int and value >= 0:
        return value
    if type(value) is not str or not value.isascii() or not value.isdigit():
        raise MarketCollectionError("malformed_response")
    return int(value)


def _pairs(scope):
    base = scope.symbol.removesuffix("-USDT-SWAP")
    if not base or not base.isascii() or not base.isalnum():
        raise ValueError("invalid_symbol")
    return f"{base}-USDT", f"{base}USDT", f"{base}_USDT"


def _levels(rows, *, width):
    if type(rows) is not list or not rows:
        raise MarketCollectionError("malformed_response")
    result = []
    for row in rows:
        if type(row) is not list or len(row) < width:
            raise MarketCollectionError("malformed_response")
        result.append((_decimal(row[0], "price"), _decimal(row[1], "quantity")))
    return result


def _dict_levels(rows):
    if type(rows) is not list or not rows:
        raise MarketCollectionError("malformed_response")
    result = []
    for row in rows:
        if type(row) is not dict or "price" not in row or "size" not in row:
            raise MarketCollectionError("malformed_response")
        result.append((_decimal(row["price"], "price"), _decimal(row["size"], "quantity")))
    return result


def _snapshot(*, source, venue, scope, pair, source_ms, bids, asks):
    bids = sorted(bids, key=lambda item: item[0], reverse=True)
    asks = sorted(asks, key=lambda item: item[0])
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    if best_bid >= best_ask:
        raise MarketCollectionError("crossed_book")
    with localcontext(research._CONTEXT):
        mid = (best_bid + best_ask) / Decimal("2")
        down_boundary = mid * (_ONE - _TWO_PCT)
        up_boundary = mid * (_ONE + _TWO_PCT)
        down_observed = sum(
            (price * quantity for price, quantity in bids if price >= down_boundary),
            Decimal("0"),
        )
        up_observed = sum(
            (price * quantity for price, quantity in asks if price <= up_boundary),
            Decimal("0"),
        )
        down_complete = bids[-1][0] <= down_boundary
        up_complete = asks[-1][0] >= up_boundary
        down_cost = down_observed if down_complete else None
        up_cost = up_observed if up_complete else None
        asymmetry = None
        if down_cost is not None and up_cost is not None and down_cost + up_cost > 0:
            asymmetry = (down_cost - up_cost) / (down_cost + up_cost)
    coverage = {
        "contract": "catos-spot-depth-2pct-v1",
        "threshold_pct": "2",
        "down_boundary_text": str(down_boundary),
        "up_boundary_text": str(up_boundary),
        "down_boundary_reached": down_complete,
        "up_boundary_reached": up_complete,
        "status": (
            "complete_2pct" if down_complete and up_complete else
            "partial_boundary_coverage"
        ),
        "book_scope": "single_venue_spot_orderbook",
        "observation_only": True,
        "smf_eligible": False,
    }
    return LiquiditySnapshot(
        source=source,
        venue=venue,
        symbol=scope.symbol,
        pair=pair,
        observed_at_ms=scope.observed_at_ms,
        source_ms=source_ms,
        quote_currency="USDT",
        best_bid=best_bid,
        best_ask=best_ask,
        mid=mid,
        down_2pct_cost=down_cost,
        up_2pct_cost=up_cost,
        down_2pct_lower_bound=down_observed,
        up_2pct_lower_bound=up_observed,
        asymmetry=asymmetry,
        bid_levels=len(bids),
        ask_levels=len(asks),
        coverage=coverage,
    )


def _parse_okx(scope, payload, pair):
    if type(payload) is not dict or payload.get("code") != "0":
        raise MarketCollectionError("api_error")
    data = payload.get("data")
    if type(data) is not list or len(data) != 1 or type(data[0]) is not dict:
        raise MarketCollectionError("malformed_response")
    book = data[0]
    source_ms = None if book.get("ts") is None else _integer_text(book["ts"])
    return _snapshot(
        source="okx-spot-orderbook",
        venue=OKX,
        scope=scope,
        pair=pair,
        source_ms=source_ms,
        bids=_levels(book.get("bids"), width=4),
        asks=_levels(book.get("asks"), width=4),
    )


def _parse_binance(scope, payload, pair):
    if type(payload) is not dict:
        raise MarketCollectionError("malformed_response")
    return _snapshot(
        source="binance-spot-orderbook",
        venue=BINANCE,
        scope=scope,
        pair=pair,
        source_ms=None,
        bids=_levels(payload.get("bids"), width=2),
        asks=_levels(payload.get("asks"), width=2),
    )


def _parse_bybit(scope, payload, pair):
    if type(payload) is not dict or payload.get("retCode") != 0:
        raise MarketCollectionError("api_error")
    result = payload.get("result")
    if type(result) is not dict or result.get("s") != pair:
        raise MarketCollectionError("scope_mismatch")
    source_ms = None if result.get("ts") is None else _integer_text(result["ts"])
    return _snapshot(
        source="bybit-spot-orderbook",
        venue=BYBIT,
        scope=scope,
        pair=pair,
        source_ms=source_ms,
        bids=_levels(result.get("b"), width=2),
        asks=_levels(result.get("a"), width=2),
    )


def _parse_gate(scope, payload, pair):
    if type(payload) is not dict:
        raise MarketCollectionError("malformed_response")
    source_ms = None if payload.get("update") is None else _integer_text(payload["update"])
    return _snapshot(
        source="gate-spot-orderbook",
        venue=GATE,
        scope=scope,
        pair=pair,
        source_ms=source_ms,
        bids=_levels(payload.get("bids"), width=2),
        asks=_levels(payload.get("asks"), width=2),
    )


def _parse_coinbase(scope, payload, pair):
    if type(payload) is not dict:
        raise MarketCollectionError("malformed_response")
    pricebook = payload.get("pricebook")
    if type(pricebook) is not dict or pricebook.get("product_id") != pair:
        raise MarketCollectionError("scope_mismatch")
    return _snapshot(
        source="coinbase-spot-orderbook",
        venue=COINBASE,
        scope=scope,
        pair=pair,
        source_ms=None,
        bids=_dict_levels(pricebook.get("bids")),
        asks=_dict_levels(pricebook.get("asks")),
    )


def _parse_bitget(scope, payload, pair):
    if type(payload) is not dict or payload.get("code") != "00000":
        raise MarketCollectionError("api_error")
    data = payload.get("data")
    if type(data) is not dict:
        raise MarketCollectionError("malformed_response")
    source_ms = None if data.get("ts") is None else _integer_text(data["ts"])
    return _snapshot(
        source="bitget-spot-orderbook",
        venue=BITGET,
        scope=scope,
        pair=pair,
        source_ms=source_ms,
        bids=_levels(data.get("bids"), width=2),
        asks=_levels(data.get("asks"), width=2),
    )


def collect_spot_liquidity(scope: CollectorScope, transport) -> LiquidityBatch:
    if not isinstance(scope, CollectorScope) or not callable(getattr(transport, "fetch", None)):
        raise ValueError("invalid_liquidity_collector")
    okx_pair, compact_pair, gate_pair = _pairs(scope)
    configs = (
        (
            "okx-spot-orderbook",
            OKX,
            okx_pair,
            PublicRequest(ENDPOINTS["okx_spot_books"], (("instId", okx_pair), ("sz", "400"))),
            _parse_okx,
        ),
        (
            "binance-spot-orderbook",
            BINANCE,
            compact_pair,
            PublicRequest(ENDPOINTS["binance_spot_depth"], (("symbol", compact_pair), ("limit", "500"))),
            _parse_binance,
        ),
        (
            "bybit-spot-orderbook",
            BYBIT,
            compact_pair,
            PublicRequest(ENDPOINTS["bybit_spot_orderbook"],
                          (("category", "spot"), ("symbol", compact_pair), ("limit", "200"))),
            _parse_bybit,
        ),
        (
            "gate-spot-orderbook",
            GATE,
            gate_pair,
            PublicRequest(ENDPOINTS["gate_spot_orderbook"],
                          (("currency_pair", gate_pair), ("limit", "100"), ("with_id", "true"))),
            _parse_gate,
        ),
        (
            "coinbase-spot-orderbook",
            COINBASE,
            okx_pair,
            PublicRequest(ENDPOINTS["coinbase_spot_orderbook"],
                          (("product_id", okx_pair), ("limit", "100"))),
            _parse_coinbase,
        ),
        (
            "bitget-spot-orderbook",
            BITGET,
            compact_pair,
            PublicRequest(ENDPOINTS["bitget_spot_orderbook"],
                          (("symbol", compact_pair), ("type", "step0"), ("limit", "150"))),
            _parse_bitget,
        ),
    )
    snapshots = []
    runs = []
    issues = []
    for source, venue, pair, request, parser in configs:
        try:
            payload = transport.fetch(request)
            fact = parser(scope, payload, pair)
        except MarketCollectionError as exc:
            issues.append((source, exc.code))
            runs.append(LiquiditySourceRun(
                source=source,
                venue=venue,
                symbol=scope.symbol,
                pair=pair,
                observed_at_ms=scope.observed_at_ms,
                status="issues",
                coverage={
                    "contract": "catos-spot-depth-2pct-v1",
                    "threshold_pct": "2",
                    "status": "unavailable",
                    "observation_only": True,
                    "smf_eligible": False,
                },
                issues=(exc.code,),
            ))
            continue
        except Exception:
            issues.append((source, "transport_error"))
            runs.append(LiquiditySourceRun(
                source=source,
                venue=venue,
                symbol=scope.symbol,
                pair=pair,
                observed_at_ms=scope.observed_at_ms,
                status="issues",
                coverage={
                    "contract": "catos-spot-depth-2pct-v1",
                    "threshold_pct": "2",
                    "status": "unavailable",
                    "observation_only": True,
                    "smf_eligible": False,
                },
                issues=("transport_error",),
            ))
            continue
        snapshots.append(fact)
        runs.append(LiquiditySourceRun(
            source=source,
            venue=venue,
            symbol=scope.symbol,
            pair=pair,
            observed_at_ms=scope.observed_at_ms,
            status="ok",
            coverage=fact.coverage,
            issues=(),
        ))
    return LiquidityBatch(
        symbol=scope.symbol,
        observed_at_ms=scope.observed_at_ms,
        snapshots=tuple(snapshots),
        source_runs=tuple(runs),
        issues=tuple(issues),
    )
