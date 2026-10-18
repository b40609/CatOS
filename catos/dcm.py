"""Six causal DCM hypotheses. Offline research only; no I/O or trading clients.

Daily context is aggregated from the requested closed-bar timeframe. Display
arrows, today's final daily close, original score, and volume are not reused.
"""

from collections import deque
from dataclasses import dataclass
from decimal import Decimal, localcontext
from statistics import median

from catos.research import AccountView, Candle, Strategy, _CONTEXT, _decimal, _integer

D = Decimal
DAY = 86_400_000
HOUR = 3_600_000
CANDIDATES = {
    "A": "順勢直接突破", "B": "順勢突破後回踩", "C": "順勢成本回踩",
    "D": "突破失敗反轉", "E": "中性邊界回歸", "F": "收斂後順勢突破",
}


@dataclass(frozen=True)
class DCMParams:
    candidate: str
    timeframe_ms: int
    quantity: Decimal = D("1")
    capped: bool = True
    ma_days: int = 20
    short_days: int = 5
    atr_days: int = 14
    compression_days: int = 20
    trend_threshold: Decimal = D("0.03")
    strong_threshold: Decimal = D("0.15")
    compression_ratio: Decimal = D("0.75")
    tolerance_atr: Decimal = D("0.1")
    stop_buffer_atr: Decimal = D("0.2")
    trail_atr: Decimal = D("1.5")
    event_hours: int = 12
    hold_hours: int = 48

    def __post_init__(self):
        if self.candidate not in CANDIDATES:
            raise ValueError("unknown DCM candidate")
        _integer(self.timeframe_ms, "timeframe_ms", minimum=60_000)
        if DAY % self.timeframe_ms:
            raise ValueError("timeframe must divide a UTC day")
        if type(self.capped) is not bool:
            raise TypeError("capped must be bool")
        for name in ("ma_days", "short_days", "atr_days", "compression_days"):
            _integer(getattr(self, name), name, minimum=2)
            if getattr(self, name) > 60:
                raise ValueError("daily windows must be <=60")
        for name in ("event_hours", "hold_hours"):
            _integer(getattr(self, name), name, minimum=1)
        for name in ("quantity", "trend_threshold", "strong_threshold",
                     "compression_ratio", "tolerance_atr", "stop_buffer_atr", "trail_atr"):
            _decimal(getattr(self, name), name, positive=True)
        if self.strong_threshold < self.trend_threshold:
            raise ValueError("strong threshold must be >= trend threshold")

    @property
    def history_days(self):
        return max(self.ma_days, self.short_days, self.atr_days, self.compression_days) + 1


@dataclass(frozen=True)
class DailyBar:
    day_ms: int
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True)
class DCMFrame:
    day_ms: int
    reference_day_ms: int
    dh: Decimal
    dc: Decimal
    dl: Decimal
    ma: Decimal
    short_ma: Decimal
    atr: Decimal
    strength: Decimal
    regime: int
    compressed: bool


def levels(high: Decimal, low: Decimal, close: Decimal, capped: bool):
    """Preserve the source formulas, including the optional +/-9.5% cap."""
    with localcontext(_CONTEXT):
        dc = (high + low + close) / D(3)
        tc = (D(9) * high + D(9) * low + D(10) * close) / D(28)
        width = (high - low) * D("0.8065")
        dh, dl = tc + width, tc - width
        if capped:
            dh, dl = min(dh, close * D("1.095")), max(dl, close * D("0.905"))
        return dh, dc, dl


@dataclass
class _Event:
    direction: int
    time_ms: int
    frame: DCMFrame
    high: Decimal
    low: Decimal


class DCMStrategy(Strategy):
    """Trusted deterministic strategy; JSON-compatible decision evidence.

    Stops/trails/targets are CLOSED-BAR decisions, filled next open. They are
    deliberately not advertised as intrabar stop orders or account risk limits.
    """

    def __init__(self, params: DCMParams):
        self.params = params
        self.days = deque(maxlen=64)
        self.frame = None
        self._day = None
        self._complete = False
        self._high = self._low = self._close = None
        self._previous_time = None
        self.previous_close = None
        self.current_close = None
        self.event = None
        self._position = 0
        self._stop = self._target = self._best = self._atr = None
        self._entry_time = None
        self.trace = []

    @property
    def ready(self):
        return self.frame is not None

    def _make_frame(self, day):
        p, history = self.params, list(self.days)
        if len(history) < p.history_days:
            return None
        closes = [item.close for item in history]
        ma = sum(closes[-p.ma_days:], D(0)) / p.ma_days
        old_ma = sum(closes[-p.ma_days - 1:-1], D(0)) / p.ma_days
        short_ma = sum(closes[-p.short_days:], D(0)) / p.short_days
        trs = [max(current.high - current.low, abs(current.high - previous.close),
                   abs(current.low - previous.close))
               for previous, current in zip(history[:-1], history[1:])]
        atr = sum(trs[-p.atr_days:], D(0)) / p.atr_days
        # A flat but complete market is valid input. Keep indicators ready and
        # suppress new entries; it must not turn into an artificial data failure.
        strength = (ma - old_ma) / atr if atr > 0 else D(0)
        regime = 1 if strength >= p.trend_threshold else -1 if strength <= -p.trend_threshold else 0
        previous = history[-1]
        earlier_ranges = [item.high - item.low for item in history[-p.compression_days - 1:-1]]
        compressed = previous.high - previous.low < median(earlier_ranges) * p.compression_ratio
        return DCMFrame(day, previous.day_ms, *levels(previous.high, previous.low,
                        previous.close, p.capped), ma, short_ma, atr, strength, regime, compressed)

    def update_indicators(self, bar):
        p = self.params
        if not bar.closed or bar.open_time_ms % p.timeframe_ms:
            raise ValueError("DCM requires aligned closed bars")
        if self._previous_time is not None and bar.open_time_ms != self._previous_time + p.timeframe_ms:
            raise ValueError("DCM requires contiguous bars")
        day = bar.open_time_ms // DAY * DAY
        if day != self._day:
            self._day = day
            self._complete = bar.open_time_ms == day
            self._high, self._low = bar.high, bar.low
            self.frame = self._make_frame(day)
        else:
            self._high, self._low = max(self._high, bar.high), min(self._low, bar.low)
        self._close = bar.close
        self.previous_close, self.current_close = self.current_close, bar.close
        self._previous_time = bar.open_time_ms
        # Freeze today's frame BEFORE appending today's completed daily OHLC.
        if bar.open_time_ms + p.timeframe_ms == day + DAY and self._complete:
            self.days.append(DailyBar(day, self._high, self._low, self._close))
        # No events, position management, or trading intents during warm-up.

    def _record(self, bar, reason, target=None, frame=None):
        f = frame or self.frame
        item = {"decision_time_ms": bar.open_time_ms + self.params.timeframe_ms,
                "reason": reason, "target": str(target) if target is not None else None}
        if f is not None:
            item.update(reference_day_ms=f.reference_day_ms, dh=str(f.dh), dc=str(f.dc),
                        dl=str(f.dl), atr=str(f.atr), strength=str(f.strength), regime=f.regime)
        self.trace.append(item)

    def _enter(self, bar, direction, stop, target=None, frame=None):
        f = frame or self.frame
        self._position, self._stop, self._target = direction, stop, target
        self._atr, self._best = f.atr, bar.close
        self._entry_time = bar.open_time_ms + self.params.timeframe_ms
        self.event = None
        quantity = self.params.quantity * direction
        self._record(bar, "entry:" + self.params.candidate, quantity, f)
        return quantity

    def on_bar(self, bar: Candle, account: AccountView):
        f, p = self.frame, self.params
        if f is None or self.previous_close is None:
            return None
        now = bar.open_time_ms + p.timeframe_ms
        if account.position:
            direction = 1 if account.position > 0 else -1
            if self._position != direction or self._stop is None:
                raise ValueError("DCM position state does not match the fresh research instance")
            self._best = max(self._best, bar.close) if direction > 0 else min(self._best, bar.close)
            stop = self._stop
            if p.candidate in "ABCF":
                trail = self._best - direction * self._atr * p.trail_atr
                stop = max(stop, trail) if direction > 0 else min(stop, trail)
            reason = None
            if direction * (bar.close - stop) <= 0:
                reason = "exit:closed-bar-invalidated"
            elif self._target is not None and direction * (bar.close - self._target) >= 0:
                reason = "exit:DC-target"
            elif now - self._entry_time >= p.hold_hours * HOUR:
                reason = "exit:time-limit"
            if reason:
                self._record(bar, reason, D(0))
                self._position = 0
                return D(0)
            return None
        # An exit filled at this open; discard only old position state.
        self._position = 0
        if f.atr <= 0:
            if self.event is not None:
                self._record(bar, "event:zero-volatility-cancelled")
                self.event = None
            return None
        previous = self.previous_close
        cross = 1 if previous <= f.dh < bar.close else -1 if previous >= f.dl > bar.close else 0
        buffer = f.atr * p.stop_buffer_atr
        trend = f.regime if f.regime * (bar.close - f.ma) > 0 else 0
        if p.candidate in "BD":
            event = self.event
            if event:
                ef, direction = event.frame, event.direction
                boundary = ef.dh if direction > 0 else ef.dl
                if now - event.time_ms > p.event_hours * HOUR:
                    self._record(bar, "event:expired", frame=ef)
                    self.event = None
                else:
                    event.high, event.low = max(event.high, bar.high), min(event.low, bar.low)
                    if p.candidate == "B":
                        touched = bar.low <= boundary + ef.atr * p.tolerance_atr if direction > 0 else bar.high >= boundary - ef.atr * p.tolerance_atr
                        reclaim = direction * (bar.close - boundary) > 0
                        invalid = direction * (bar.close - boundary) < -ef.atr * p.stop_buffer_atr
                        if invalid:
                            self._record(bar, "event:retest-invalidated", frame=ef)
                            self.event = None
                        elif touched and reclaim:
                            stop = bar.low - ef.atr * p.stop_buffer_atr if direction > 0 else bar.high + ef.atr * p.stop_buffer_atr
                            return self._enter(bar, direction, stop, frame=ef)
                    elif direction * (bar.close - boundary) < 0:
                        reverse = -direction
                        if reverse * (ef.dc - bar.close) > 0:
                            stop = event.high + ef.atr * p.stop_buffer_atr if reverse < 0 else event.low - ef.atr * p.stop_buffer_atr
                            return self._enter(bar, reverse, stop, ef.dc, ef)
                        self._record(bar, "event:target-already-passed", frame=ef)
                        self.event = None
            if self.event is None and cross:
                eligible = (trend == cross if p.candidate == "B" else cross * f.strength < p.strong_threshold)
                if eligible:
                    self.event = _Event(cross, now, f, bar.high, bar.low)
                    self._record(bar, "event:breakout-frozen")
            return None
        if p.candidate in "AF" and cross and trend == cross:
            if p.candidate == "F" and not f.compressed:
                return None
            stop = f.dh - buffer if cross > 0 else f.dl + buffer
            return self._enter(bar, cross, stop)
        if p.candidate == "C" and trend:
            for cost in (f.dc, f.short_ma):
                touched = bar.low <= cost <= bar.close if trend > 0 else bar.close <= cost <= bar.high
                recovered = trend * (bar.close - previous) > 0
                if touched and recovered:
                    stop = bar.low - buffer if trend > 0 else bar.high + buffer
                    return self._enter(bar, trend, stop)
        if p.candidate == "E" and f.regime == 0:
            direction = 1 if bar.low <= f.dl < bar.close < f.dc else -1 if f.dc < bar.close < f.dh <= bar.high else 0
            if direction:
                stop = bar.low - buffer if direction > 0 else bar.high + buffer
                return self._enter(bar, direction, stop, f.dc)
        return None
