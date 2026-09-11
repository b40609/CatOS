"""Run from the project root: python -B -m examples.closed_bar_demo."""

from collections import deque
from dataclasses import asdict
from decimal import Decimal
import json

from catos.research import (
    AccountView, BacktestConfig, Candle, ContractSpec, FundingEvent, Strategy, backtest,
)


class SMATrend(Strategy):
    """A small long/flat example; warm-up and trading use the same indicator."""

    def __init__(self):
        self.closes = deque(maxlen=2)

    def update_indicators(self, bar: Candle) -> None:
        self.closes.append(bar.close)

    @property
    def ready(self) -> bool:
        return len(self.closes) == self.closes.maxlen

    def on_bar(self, bar: Candle, account: AccountView) -> Decimal:
        average = sum(self.closes, Decimal("0")) / Decimal(len(self.closes))
        return Decimal("2") if bar.close > average else Decimal("0")


def main() -> None:
    step = 900_000
    prices = tuple(map(Decimal, ("100", "101", "103", "102", "99", "98", "100", "102")))
    bars = tuple(Candle(i * step, price, price, price, price) for i, price in enumerate(prices))
    cfg = BacktestConfig(
        contract=ContractSpec("BTC-USDT-SWAP", Decimal("0.01"), Decimal("0.01"), Decimal("1"), Decimal("1")),
        timeframe_ms=step, initial_balance=Decimal("1000"),
        fee_rate=Decimal("0.0005"), slippage_bps=Decimal("2"),
        funding_events=(FundingEvent(3 * step + step // 2, Decimal("0.0001"), Decimal("102")),),
    )
    result = backtest(strategy=SMATrend, candles=bars, config=cfg, warmup_bars=2)

    def encode(value):
        if isinstance(value, Decimal):
            return str(value)
        raise TypeError(f"Cannot encode {type(value).__name__}")

    print(json.dumps({
        "data": "synthetic only; not a historical performance claim",
        "warmup_bars": result.warmup_bars,
        "evaluation_start_ms": result.evaluation_start_ms,
        "performance": asdict(result.performance),
        "trades": [asdict(trade) for trade in result.trades],
        "funding": [asdict(payment) for payment in result.funding],
        "pending_intent": asdict(result.pending_intent) if result.pending_intent else None,
        "assumptions": result.assumptions,
    }, default=encode, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
