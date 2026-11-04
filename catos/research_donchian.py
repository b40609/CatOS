"""Registered Donchian channel breakout for closed-bar research (long / short)."""

from collections import deque
from decimal import Decimal

from catos.research import AccountView, Candle, Strategy


class _Extreme:
    """Highest or lowest of the last ``size`` pushed values; O(1) amortized per push."""

    def __init__(self, size: int, highest: bool):
        self.size = size
        self.highest = highest
        self.items = deque()  # (index, value), values strictly monotonic from the front
        self.count = 0

    def push(self, value: Decimal) -> None:
        while self.items and (self.items[-1][1] <= value if self.highest
                              else self.items[-1][1] >= value):
            self.items.pop()
        self.items.append((self.count, value))
        self.count += 1
        while self.items[0][0] < self.count - self.size:
            self.items.popleft()

    @property
    def value(self) -> Decimal:
        return self.items[0][1]


class RegisteredDonchian(Strategy):
    """Channel breakout on closes; the channels never include the bar being decided.

    A close above the previous ``entry_bars`` highs targets +quantity and a close
    below their lows targets -quantity, reversing an opposite position. A long
    is flattened on a close below the previous ``exit_bars`` lows, a short on a
    close above their highs. Otherwise the position is left unchanged.
    """

    def __init__(self, entry_bars: int, exit_bars: int, quantity: Decimal):
        self.quantity = quantity
        self.entry = (_Extreme(entry_bars, True), _Extreme(entry_bars, False))
        self.exit = (_Extreme(exit_bars, True), _Extreme(exit_bars, False))
        self.channels = None  # (entry high, entry low, exit high, exit low) before the latest bar

    def update_indicators(self, bar: Candle) -> None:
        if self.ready:
            self.channels = (self.entry[0].value, self.entry[1].value,
                             self.exit[0].value, self.exit[1].value)
        for highs, lows in (self.entry, self.exit):
            highs.push(bar.high)
            lows.push(bar.low)

    @property
    def ready(self) -> bool:
        # The next bar can be decided once both channels hold their full history.
        return all(extreme.count >= extreme.size for extreme in (*self.entry, *self.exit))

    def on_bar(self, bar: Candle, account: AccountView) -> Decimal | None:
        if self.channels is None:
            return None
        entry_high, entry_low, exit_high, exit_low = self.channels
        if bar.close > entry_high:
            return self.quantity
        if bar.close < entry_low:
            return -self.quantity
        if account.position > 0 and bar.close < exit_low:
            return Decimal("0")
        if account.position < 0 and bar.close > exit_high:
            return Decimal("0")
        return None
