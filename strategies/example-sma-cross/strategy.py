"""Example: moving-average crossover, long / short. Copy this folder to start a new strategy."""

from collections import deque
from decimal import Decimal

from catos.research import AccountView, Candle, Strategy


class SmaCross(Strategy):
    """Long while the fast average is above the slow one, short while it is below.

    The whole state is the last ``slow`` closes, so a Bot restarted from the last
    ``slow`` closed bars decides exactly as before (the restart-consistency check).
    """

    def __init__(self, fast: int, slow: int, quantity: Decimal):
        self.fast = fast
        self.closes = deque(maxlen=slow)
        self.quantity = quantity

    def update_indicators(self, bar: Candle) -> None:
        self.closes.append(bar.close)

    @property
    def ready(self) -> bool:
        return len(self.closes) == self.closes.maxlen

    def on_bar(self, bar: Candle, account: AccountView) -> Decimal | None:
        closes = list(self.closes)
        slow = sum(closes, Decimal("0")) / len(closes)
        fast = sum(closes[-self.fast:], Decimal("0")) / self.fast
        if fast > slow:
            return self.quantity
        if fast < slow:
            return -self.quantity
        return None
