"""Pure Decimal market-feature calculations for the Yaozi parity layer.

The module performs no network or database I/O. Closed candles and complete
trade windows are explicit inputs. A REST trade tail is not treated as a
complete window and therefore cannot silently produce CVD/taker features.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext

from catos import ipc, research
from catos.market_collectors import MarketCandle, MarketTrade


ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")
FEATURE_VERSION = "market-features-v1"


@dataclass(frozen=True, slots=True)
class FeatureConfig:
    atr_length: int = 14
    volatility_length: int = 20
    bb_length: int = 20
    bbwp_lookback: int = 100
    structure_lookback: int = 20

    def __post_init__(self):
        for name in ("atr_length", "volatility_length", "bb_length", "bbwp_lookback", "structure_lookback"):
            value = getattr(self, name)
            if type(value) is not int or not 2 <= value <= 1000:
                raise ValueError("invalid_feature_config")


@dataclass(frozen=True, slots=True)
class TradeWindow:
    start_ms: int
    end_ms: int
    trades: tuple[MarketTrade, ...]
    complete: bool

    def __post_init__(self):
        ipc.integer(self.start_ms, "trade start_ms")
        ipc.integer(self.end_ms, "trade end_ms")
        if self.end_ms <= self.start_ms or type(self.trades) is not tuple or type(self.complete) is not bool:
            raise ValueError("invalid_trade_window")
        previous = None
        for trade in self.trades:
            if not isinstance(trade, MarketTrade) or not self.start_ms <= trade.time_ms < self.end_ms:
                raise ValueError("invalid_trade_window")
            key = (trade.time_ms, len(trade.trade_id), trade.trade_id)
            if previous is not None and key <= previous:
                raise ValueError("invalid_trade_window")
            previous = key


@dataclass(frozen=True, slots=True)
class FeatureSet:
    symbol: str
    observed_at_ms: int
    timeframe_ms: int
    feature_version: str
    return_1h_pct: Decimal | None
    return_24h_pct: Decimal | None
    atr_pct: Decimal | None
    realized_vol_pct: Decimal | None
    bb_width_pct: Decimal | None
    bbwp_pct: Decimal | None
    range_position_pct: Decimal | None
    structure_state: str | None
    cvd_quote: Decimal | None
    taker_buy_ratio: Decimal | None
    trade_count: int | None
    oi_delta_5m_pct: Decimal | None
    oi_delta_1h_pct: Decimal | None
    oi_delta_4h_pct: Decimal | None
    issues: tuple[str, ...]


def _validate_candles(candles):
    if type(candles) is not tuple or not candles:
        raise ValueError("candles_required")
    first = candles[0]
    if not isinstance(first, MarketCandle) or first.closed is not True:
        raise ValueError("invalid_candles")
    symbol, timeframe = first.symbol, first.timeframe_ms
    previous = None
    for candle in candles:
        if (not isinstance(candle, MarketCandle) or candle.closed is not True or candle.symbol != symbol
                or candle.timeframe_ms != timeframe):
            raise ValueError("invalid_candles")
        if previous is not None and candle.open_time_ms != previous + timeframe:
            raise ValueError("candle_gap")
        if not candle.low <= min(candle.open, candle.close) <= max(candle.open, candle.close) <= candle.high:
            raise ValueError("invalid_candles")
        previous = candle.open_time_ms
    return symbol, timeframe


def _return_pct(candles, window_ms, timeframe):
    bars = window_ms // timeframe
    if window_ms % timeframe or len(candles) <= bars:
        return None
    reference = candles[-1 - bars].close
    if reference == ZERO:
        return None
    return (candles[-1].close - reference) * ONE_HUNDRED / reference


def _atr_pct(candles, length):
    if len(candles) < length + 1:
        return None
    ranges = []
    for previous, current in zip(candles[-length - 1:-1], candles[-length:]):
        ranges.append(max(current.high - current.low,
                          abs(current.high - previous.close),
                          abs(current.low - previous.close)))
    close = candles[-1].close
    return None if close == ZERO else sum(ranges, ZERO) / Decimal(length) * ONE_HUNDRED / close


def _realized_vol(candles, length):
    if len(candles) < length + 1:
        return None
    returns = []
    selected = candles[-length - 1:]
    for previous, current in zip(selected[:-1], selected[1:]):
        if previous.close == ZERO:
            return None
        returns.append((current.close - previous.close) * ONE_HUNDRED / previous.close)
    mean = sum(returns, ZERO) / Decimal(len(returns))
    variance = sum(((value - mean) ** 2 for value in returns), ZERO) / Decimal(len(returns))
    return variance.sqrt()


def _bb_width(closes, length):
    if len(closes) < length:
        return None
    selected = closes[-length:]
    mean = sum(selected, ZERO) / Decimal(length)
    if mean == ZERO:
        return None
    variance = sum(((value - mean) ** 2 for value in selected), ZERO) / Decimal(length)
    return Decimal("4") * variance.sqrt() * ONE_HUNDRED / mean


def _bbwp(candles, length, lookback):
    closes = [item.close for item in candles]
    current = _bb_width(closes, length)
    if current is None:
        return None, None
    historical = []
    start = max(length, len(closes) - lookback)
    for end in range(start, len(closes)):
        width = _bb_width(closes[:end], length)
        if width is not None:
            historical.append(width)
    if not historical:
        return current, None
    rank = Decimal(sum(1 for value in historical if value <= current)) * ONE_HUNDRED / Decimal(len(historical))
    return current, rank


def _structure(candles, lookback):
    if len(candles) < lookback + 1:
        return None, None
    prior = candles[-lookback - 1:-1]
    ceiling = max(item.high for item in prior)
    floor = min(item.low for item in prior)
    close = candles[-1].close
    if close > ceiling:
        state = "BREAKOUT_UP"
    elif close < floor:
        state = "BREAKOUT_DOWN"
    else:
        state = "RANGE"
    position = None if ceiling == floor else (close - floor) * ONE_HUNDRED / (ceiling - floor)
    return position, state


def _trade_features(window, symbol):
    if window is None:
        return None, None, None, "trade_window_missing"
    if not isinstance(window, TradeWindow):
        raise ValueError("invalid_trade_window")
    if not window.complete:
        return None, None, None, "trade_window_incomplete"
    buy = sell = ZERO
    for trade in window.trades:
        if trade.symbol != symbol or trade.aggressor_side not in ("BUY", "SELL"):
            raise ValueError("invalid_trade_window")
        notional = trade.price * trade.base_quantity
        if trade.aggressor_side == "BUY":
            buy += notional
        else:
            sell += notional
    total = buy + sell
    ratio = None if total == ZERO else buy / total
    return buy - sell, ratio, len(window.trades), None


def calculate_features(*, candles: tuple[MarketCandle, ...], observed_at_ms: int,
                       oi_delta_5m_pct: Decimal | None = None,
                       oi_delta_1h_pct: Decimal | None = None,
                       oi_delta_4h_pct: Decimal | None = None,
                       trade_window: TradeWindow | None = None,
                       config: FeatureConfig = FeatureConfig()) -> FeatureSet:
    symbol, timeframe = _validate_candles(candles)
    ipc.integer(observed_at_ms, "observed_at_ms")
    for value in (oi_delta_5m_pct, oi_delta_1h_pct, oi_delta_4h_pct):
        if value is not None and not isinstance(value, Decimal):
            raise ValueError("invalid_oi_delta")
    with localcontext(research._CONTEXT):
        bb_width, bbwp = _bbwp(candles, config.bb_length, config.bbwp_lookback)
        range_position, structure = _structure(candles, config.structure_lookback)
        cvd, taker, trade_count, trade_issue = _trade_features(trade_window, symbol)
        issues = () if trade_issue is None else (trade_issue,)
        return FeatureSet(
            symbol, observed_at_ms, timeframe, FEATURE_VERSION,
            _return_pct(candles, 3_600_000, timeframe),
            _return_pct(candles, 86_400_000, timeframe),
            _atr_pct(candles, config.atr_length),
            _realized_vol(candles, config.volatility_length),
            bb_width, bbwp, range_position, structure,
            cvd, taker, trade_count,
            oi_delta_5m_pct, oi_delta_1h_pct, oi_delta_4h_pct, issues)
