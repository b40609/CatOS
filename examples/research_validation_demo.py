"""Synthetic-only rolling validation; prints deterministic Decimal JSON to stdout.

Run: py -3 -B -m examples.research_validation_demo
No files, providers, databases, or accounts are accessed by this example.
"""

from decimal import Decimal

from catos.optimization import DecimalChoices, IntRange
from catos.research import BacktestConfig, Candle, ContractSpec, FundingEvent
from catos.research_validation import WalkForwardPlan, validation_json, walk_forward
from examples.optuna_demo import SearchSMA


def run_demo():
    prices = (100, 101, 103, 102, 104, 107, 105, 101,
              98, 96, 99, 102, 105, 108, 106, 103,
              100, 98, 101, 104, 108, 110, 107, 103)
    timeframe = 900_000
    bars = tuple(Candle(i * timeframe, Decimal(p), Decimal(p), Decimal(p), Decimal(p))
                 for i, p in enumerate(prices))
    config = BacktestConfig(
        ContractSpec("BTC-USDT-SWAP", Decimal("0.01"), Decimal("0.01"), Decimal(1), Decimal(1)),
        timeframe, Decimal(1000), Decimal("0.0005"), Decimal(2),
        tuple(FundingEvent(i * timeframe, Decimal("0.0001"), Decimal(prices[i]))
              for i in (8, 16)),
    )
    return walk_forward(
        strategy_factory=SearchSMA,
        search_space={"period": IntRange(2, 4), "quantity": DecimalChoices(("1", "2"))},
        candles=bars, config=config, score=lambda p: p.return_pct,
        score_name="synthetic net return percent; not a deployment gate",
        plan=WalkForwardPlan(train_bars=8, test_bars=4, windows=3, warmup_bars=4),
        max_candidates=6, max_runs=21,
    )


def main():
    print(validation_json(run_demo()))


if __name__ == "__main__":
    main()
