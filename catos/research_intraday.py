"""Research-only intraday DCM strategies, preregistered 2026-11-07 (docs/research-real-data-plan.md 工作包 F).

The rules follow the user's 2026-10-11 trader calibration (docs/dcm-research-plan.md):
fade a false breakdown below DL / breakout above DH on an intraday close, and buy
a pullback to DC in the days after a daily close above DH. Levels are the DCM
indicator's DH/DC/DL from the previous complete UTC day, without the Taiwan
price-limit clamp; nothing trades until a complete day has been seen. Every
decision uses the bar that just closed; the engine fills at the next open.
Money and prices are Decimal; quantity is the fixed contract size.
"""

from decimal import Decimal

from catos.research import Strategy

DAY_MS = 86_400_000
ZERO = Decimal(0)


def dcm_levels(high, low, close):
    """(DH, DC, DL) from one day's H/L/C (same formula as research_daily.dcm_levels)."""
    center = (high + low + close) / Decimal(3)
    typical = (Decimal(9) * high + Decimal(9) * low + Decimal(10) * close) / Decimal(28)
    expansion = (high - low) * Decimal("0.8065")
    return typical + expansion, center, typical - expansion


class _Session:
    """Current UTC day's running H/L/C and the levels for it (from the previous complete day)."""

    def __init__(self):
        self.start = None
        self.high = self.low = self.close = None
        self.from_midnight = False
        self.levels = None  # (DH, DC, DL) for the current day, None until a complete day is known
        self.timeframe = None
        self.previous_open = None
        self.new_day = False
        self.day_closed = False
        self.finished = None  # (high, low, close) of the day this bar closed

    def push(self, bar):
        if self.previous_open is not None and self.timeframe is None:
            self.timeframe = bar.open_time_ms - self.previous_open
        self.previous_open = bar.open_time_ms
        start = bar.open_time_ms - bar.open_time_ms % DAY_MS
        self.new_day = start != self.start
        if self.new_day:
            complete = self.start is not None and self.from_midnight and self.close is not None
            self.levels = dcm_levels(self.high, self.low, self.close) if complete and self._ended else None
            self.start, self.high, self.low = start, bar.high, bar.low
            self.from_midnight = bar.open_time_ms == start
            self._ended = False
        else:
            self.high, self.low = max(self.high, bar.high), min(self.low, bar.low)
        self.close = bar.close
        self.day_closed = self.timeframe is not None and (bar.open_time_ms + self.timeframe) % DAY_MS == 0
        self.finished = (self.high, self.low, self.close) if self.day_closed and self.from_midnight else None
        if self.day_closed:
            self._ended = True

    _ended = False


class DCMFade(Strategy):
    """F1: false breakdown below DL -> long, false breakout above DH -> short."""

    def __init__(self, exit_mode, quantity):
        if exit_mode not in (0, 1):
            raise ValueError("exit_mode must be 0 (opposite level) or 1 (daily close vs DC)")
        self.exit_mode, self.quantity = exit_mode, quantity
        self.session = _Session()
        self.breach_low = self.breach_high = None  # extreme since the breach, this day
        self.entered = {1: False, -1: False}
        self.trade = None  # (side, stop, target) frozen at entry

    @property
    def ready(self):
        return True  # it simply waits for a complete day before trading

    def update_indicators(self, bar):
        session = self.session
        session.push(bar)
        if session.new_day:
            self.breach_low = self.breach_high = None
            self.entered = {1: False, -1: False}
        if session.levels is None:
            return
        dh, _, dl = session.levels
        if self.breach_low is not None or bar.low < dl:
            self.breach_low = bar.low if self.breach_low is None else min(self.breach_low, bar.low)
        if self.breach_high is not None or bar.high > dh:
            self.breach_high = bar.high if self.breach_high is None else max(self.breach_high, bar.high)

    def on_bar(self, bar, account):
        session, position = self.session, account.position
        if position != ZERO and self.trade is not None:
            side, stop, target = self.trade
            exit_now = (bar.close < stop) if side > 0 else (bar.close > stop)
            if self.exit_mode == 0:
                exit_now = exit_now or (bar.close >= target if side > 0 else bar.close <= target)
            elif session.day_closed and session.levels is not None:
                dc = session.levels[1]
                exit_now = exit_now or (bar.close < dc if side > 0 else bar.close > dc)
            if exit_now:
                self.trade = None
                return ZERO
            return None
        if position != ZERO or session.levels is None:
            return None
        self.trade = None
        dh, _, dl = session.levels
        long_ok = self.breach_low is not None and bar.close > dl and not self.entered[1]
        short_ok = self.breach_high is not None and bar.close < dh and not self.entered[-1]
        if long_ok == short_ok:
            return None
        side = 1 if long_ok else -1
        self.entered[side] = True
        self.trade = (side, self.breach_low, dh) if side > 0 else (side, self.breach_high, dl)
        return self.quantity if side > 0 else -self.quantity


class DCMPullback(Strategy):
    """F2: after a daily close at or above DH, buy the first reclaim of the frozen DC."""

    def __init__(self, window_days, quantity):
        if not 1 <= window_days <= 5:
            raise ValueError("window_days must be in [1, 5]")
        self.window_days, self.quantity = window_days, quantity
        self.session = _Session()
        self.launch = None  # (frozen DH, DC, DL, window end ms)
        self.touched = False
        self.stop = None

    @property
    def ready(self):
        return True

    def update_indicators(self, bar):
        session = self.session
        session.push(bar)
        if self.launch is not None and bar.open_time_ms >= self.launch[3]:
            self.launch, self.touched = None, False
        if self.launch is not None and bar.low <= self.launch[1]:
            self.touched = True

    def on_bar(self, bar, account):
        session, position = self.session, account.position
        if position != ZERO:
            daily_exit = session.day_closed and session.levels is not None and bar.close < session.levels[1]
            if (self.stop is not None and bar.close < self.stop) or daily_exit:
                self.stop = None
                return ZERO
            decision = None
        else:
            decision = None
            if self.launch is not None and self.touched and bar.close > self.launch[1]:
                self.stop = self.launch[2]
                self.launch, self.touched = None, False
                decision = self.quantity
        # A daily close at or above that day's DH starts a new launch window.
        if (decision is None and position == ZERO and session.finished is not None
                and session.levels is not None and session.finished[2] >= session.levels[0]):
            day_end = bar.open_time_ms + session.timeframe
            self.launch = (*dcm_levels(*session.finished), day_end + self.window_days * DAY_MS)
            self.touched = False
        return decision
