"""Registered research parameters around the inspected SMA example."""

from collections import deque
from decimal import Decimal

from examples.closed_bar_demo import SMATrend


class RegisteredSMA(SMATrend):
    """Retain the example's long/flat rule with explicit period and size."""

    def __init__(self, period: int, quantity: Decimal):
        super().__init__()
        self.closes = deque(maxlen=period)
        self.quantity = quantity

    def on_bar(self, bar, account):
        return self.quantity if super().on_bar(bar, account) > 0 else Decimal("0")
