# strategy_id: counter-python
# version: file-v1
# name: Counter Python Strategy
# description: Non-SMA short/flat counter with durable state
# warmup_bars: 2
# defaults: {"quantity": "-1", "hold": false}
from decimal import Decimal

class Strategy:
    def __init__(self, parameters):
        self.parameters = parameters
        self.n = 0
        self.decisions = 0

    def update_indicators(self, bar):
        self.n += 1

    @property
    def ready(self):
        return self.n >= 2

    def on_bar(self, bar, account):
        self.decisions += 1
        if self.parameters.get("hold") or self.n % 2:
            return Decimal(self.parameters["quantity"])
        return Decimal("0")

    def snapshot_state(self):
        return {"n": self.n, "decisions": self.decisions}

    def restore_state(self, state):
        self.n = state["n"]
        self.decisions = state["decisions"]
