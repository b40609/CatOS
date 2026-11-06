"""Research-only daily strategies, preregistered 2026-11-06 before any run on real data.

Rules and parameters follow docs/research-real-data-plan.md (工作包 E); they are
not tuned on CatOS data. Every strategy builds complete UTC days from the closed
bars it is given, decides only on the bar that closes a day (00:00 UTC), and the
engine fills that target at the next bar's open. Money and sizes are Decimal.

- DonchianEnsemble: nine long-only Donchian sub-models (Zarattini, Pagani and
  Barbon 2025), weight = active share, optional 25% volatility target.
- TimeSeriesMomentum: sign of 30/91/365-day returns averaged (Hurst, Ooi and
  Pedersen 2017 style), long/short, optional 25% volatility target.
- DCMDaily: the user's DCM indicator levels from the previous complete day, the
  indicator's own arrow logic, optionally gated by its score without VWAP.
"""

from collections import deque
from decimal import ROUND_DOWN, Decimal

from catos.research import Strategy

DAY_MS = 86_400_000
ZERO, ONE, TWO = Decimal(0), Decimal(1), Decimal(2)
TARGET_VOLATILITY = Decimal("0.25")
MAX_LEVERAGE = TWO
REBALANCE_BAND = Decimal("0.2")
DAYS_PER_YEAR = Decimal(365)


class _Days:
    """Complete UTC days (start_ms, high, low, close) from consecutive closed bars."""

    def __init__(self, keep):
        self.days = deque(maxlen=keep)
        self.current = None  # [start, high, low, close, began_at_midnight]
        self.timeframe = None
        self.previous_open = None

    def push(self, bar):
        """Add one bar; True when it closes a complete day."""
        if self.previous_open is not None and self.timeframe is None:
            self.timeframe = bar.open_time_ms - self.previous_open
        self.previous_open = bar.open_time_ms
        start = bar.open_time_ms - bar.open_time_ms % DAY_MS
        if self.current is None or self.current[0] != start:
            self.current = [start, bar.high, bar.low, bar.close, bar.open_time_ms == start]
        else:
            self.current[1] = max(self.current[1], bar.high)
            self.current[2] = min(self.current[2], bar.low)
            self.current[3] = bar.close
        if self.timeframe is None or (bar.open_time_ms + self.timeframe) % DAY_MS:
            return False
        day, self.current = self.current, None
        if not day[4]:
            return False  # the first, partial day is never used
        self.days.append(tuple(day[:4]))
        return True

    def closes(self):
        return [day[3] for day in self.days]


def _contracts(notional, price, contract, cap):
    """Signed contracts toward zero on the lot grid, within +/-cap; below min size is flat."""
    raw = notional / (price * contract.base_per_contract)
    quantity = (raw / contract.lot_size).to_integral_value(rounding=ROUND_DOWN) * contract.lot_size
    quantity = max(-cap, min(cap, quantity))
    return ZERO if abs(quantity) < contract.min_size else quantity


def _rebalance(target, position):
    """New target only on entry, exit, reversal or a change above 20% of the position."""
    if target == position:
        return None
    if target == ZERO or position == ZERO or (target > ZERO) != (position > ZERO):
        return target
    return target if abs(target - position) > abs(position) * REBALANCE_BAND else None


def _sign(value):
    return ONE if value > ZERO else -ONE if value < ZERO else ZERO


class DonchianEnsemble(Strategy):
    LOOKBACKS = (5, 10, 20, 30, 60, 90, 150, 250, 360)
    VOL_DAYS = 90

    def __init__(self, vol_scaling, quantity, contract):
        if vol_scaling not in (0, 1):
            raise ValueError("vol_scaling must be 0 or 1")
        self.vol_scaling, self.cap, self.contract = bool(vol_scaling), quantity, contract
        self.days = _Days(max(self.LOOKBACKS) + 1)
        self.active = {n: False for n in self.LOOKBACKS}
        self.stops = {n: None for n in self.LOOKBACKS}
        self.decide = False

    @property
    def ready(self):
        return len(self.days.days) > max(self.LOOKBACKS)

    def update_indicators(self, bar):
        self.decide = self.days.push(bar)
        if not self.decide:
            return
        closes = self.days.closes()
        close = closes[-1]
        for n in self.LOOKBACKS:
            if len(closes) < n + 1:
                continue
            window = closes[-n:]
            middle = (max(window) + min(window)) / TWO
            if self.active[n]:
                if close < self.stops[n]:
                    self.active[n], self.stops[n] = False, None
                else:
                    self.stops[n] = max(self.stops[n], middle)
            elif close > max(closes[-n - 1:-1]):
                self.active[n], self.stops[n] = True, middle

    def leverage(self):
        if not self.vol_scaling:
            return ONE
        closes = self.days.closes()[-(self.VOL_DAYS + 1):]
        returns = [after / before - ONE for before, after in zip(closes, closes[1:])]
        mean = sum(returns, ZERO) / len(returns)
        variance = sum(((r - mean) ** 2 for r in returns), ZERO) / (len(returns) - 1)
        volatility = (variance * DAYS_PER_YEAR).sqrt()
        return MAX_LEVERAGE if volatility == ZERO else min(MAX_LEVERAGE, TARGET_VOLATILITY / volatility)

    def on_bar(self, bar, account):
        if not self.decide:
            return None
        weight = Decimal(sum(self.active.values())) / Decimal(len(self.LOOKBACKS))
        target = _contracts(account.equity * weight * self.leverage(), bar.close, self.contract, self.cap)
        return _rebalance(target, account.position)


class TimeSeriesMomentum(Strategy):
    HORIZONS = (30, 91, 365)
    CENTER_OF_MASS = 60

    def __init__(self, vol_scaling, quantity, contract):
        if vol_scaling not in (0, 1):
            raise ValueError("vol_scaling must be 0 or 1")
        self.vol_scaling, self.cap, self.contract = bool(vol_scaling), quantity, contract
        self.days = _Days(max(self.HORIZONS) + 1)
        self.decay = Decimal(self.CENTER_OF_MASS) / Decimal(self.CENTER_OF_MASS + 1)
        self.seed_returns = []
        self.variance = None
        self.decide = False

    @property
    def ready(self):
        return len(self.days.days) > max(self.HORIZONS) and self.variance is not None

    def update_indicators(self, bar):
        self.decide = self.days.push(bar)
        if not self.decide or len(self.days.days) < 2:
            return
        closes = self.days.closes()
        daily = closes[-1] / closes[-2] - ONE
        if self.variance is None:
            self.seed_returns.append(daily)
            if len(self.seed_returns) == self.CENTER_OF_MASS:
                mean = sum(self.seed_returns, ZERO) / len(self.seed_returns)
                self.variance = (sum(((r - mean) ** 2 for r in self.seed_returns), ZERO)
                                 / (len(self.seed_returns) - 1))
        else:
            self.variance = self.decay * self.variance + (ONE - self.decay) * daily * daily

    def leverage(self):
        if not self.vol_scaling:
            return ONE
        volatility = (self.variance * DAYS_PER_YEAR).sqrt()
        return MAX_LEVERAGE if volatility == ZERO else min(MAX_LEVERAGE, TARGET_VOLATILITY / volatility)

    def on_bar(self, bar, account):
        if not self.decide:
            return None
        closes = self.days.closes()
        score = sum((_sign(closes[-1] / closes[-k - 1] - ONE) for k in self.HORIZONS), ZERO) / Decimal(len(self.HORIZONS))
        target = _contracts(account.equity * score * self.leverage(), bar.close, self.contract, self.cap)
        return _rebalance(target, account.position)


def dcm_levels(high, low, close):
    """(DH, DC, DL) of the DCM indicator from one day's H/L/C, without the Taiwan price-limit clamp."""
    center = (high + low + close) / Decimal(3)
    typical = (Decimal(9) * high + Decimal(9) * low + Decimal(10) * close) / Decimal(28)
    expansion = (high - low) * Decimal("0.8065")
    return typical + expansion, center, typical - expansion


def ma_slope_score(slope_pct):
    for threshold, score in ((Decimal(3), 15), (ONE, 10)):
        if slope_pct >= threshold:
            return score
    if slope_pct > ZERO:
        return 5
    for threshold, score in ((Decimal(-3), -15), (-ONE, -10)):
        if slope_pct <= threshold:
            return score
    return -5 if slope_pct < ZERO else 0


class DCMDaily(Strategy):
    MA_DAYS = 20

    def __init__(self, score_filter, quantity):
        if score_filter not in (0, 1):
            raise ValueError("score_filter must be 0 or 1")
        self.score_filter, self.quantity = bool(score_filter), quantity
        self.days = _Days(self.MA_DAYS + 2)
        self.decide = False

    @property
    def ready(self):
        return len(self.days.days) >= self.MA_DAYS + 2

    def update_indicators(self, bar):
        self.decide = self.days.push(bar)

    def score(self, close, today, yesterday):
        closes = self.days.closes()
        ma_now = sum(closes[-self.MA_DAYS:], ZERO) / Decimal(self.MA_DAYS)
        ma_before = sum(closes[-self.MA_DAYS - 1:-1], ZERO) / Decimal(self.MA_DAYS)
        total = 50 + ma_slope_score((ma_now - ma_before) / ma_before * Decimal(100))
        dh, dc, dl = today
        total += 10 if close >= dh else 5 if close > dc else -10 if close <= dl else -5 if close < dc else 0
        if dh > yesterday[0] and dl > yesterday[2]:
            total += 10
        elif dh < yesterday[0] and dl < yesterday[2]:
            total -= 10
        return total

    def on_bar(self, bar, account):
        if not self.decide:
            return None
        days = self.days.days
        close = days[-1][3]
        today = dcm_levels(*days[-2][1:4])      # levels for this day come from the previous day
        yesterday = dcm_levels(*days[-3][1:4])
        bull, bear = close >= today[0], close < today[2]
        if not (bull or bear):
            return None
        side = ONE if bull else -ONE
        if self.score_filter:
            score = self.score(close, today, yesterday)
            allowed = score >= 60 if bull else score <= 40
            if not allowed:
                opposite = account.position * side < ZERO
                return ZERO if opposite else None
        return side * self.quantity
