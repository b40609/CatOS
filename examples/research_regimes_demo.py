"""Synthetic-only OOS regime attribution; prints deterministic Decimal JSON.

Run: py -3 -B -m examples.research_regimes_demo
The explicit thresholds below illustrate arithmetic, not recommended settings.
"""

from decimal import Decimal

from catos.optimization import DecimalChoices, IntRange
from catos.research import BacktestConfig, Candle, ContractSpec, FundingEvent
from catos.research_regimes import RegimeRule, regime_walk_forward, regimes_json
from catos.research_validation import WalkForwardPlan
from examples.optuna_demo import SearchSMA


def run_demo():
    # Same synthetic scenario as research_validation_demo, for direct comparison.
    prices = (100, 101, 103, 102, 104, 107, 105, 101,
              98, 96, 99, 102, 105, 108, 106, 103,
              100, 98, 101, 104, 108, 110, 107, 103)
    timeframe = 900_000
    bars = tuple(Candle(i*timeframe, Decimal(p), Decimal(p), Decimal(p), Decimal(p))
                 for i, p in enumerate(prices))
    config = BacktestConfig(
        ContractSpec("BTC-USDT-SWAP", Decimal("0.01"), Decimal("0.01"), Decimal(1), Decimal(1)),
        timeframe, Decimal(1000), Decimal("0.0005"), Decimal(2),
        tuple(FundingEvent(i*timeframe, Decimal("0.0001"), Decimal(prices[i])) for i in (8, 16)),
    )
    return regime_walk_forward(
        strategy_factory=SearchSMA,
        search_space={"period": IntRange(2, 4), "quantity": DecimalChoices(("1", "2"))},
        candles=bars, config=config, rule=RegimeRule(3, Decimal("0.5"), Decimal(250)),
        score=lambda p: p.return_pct,
        score_name="synthetic net return percent; not a deployment gate",
        plan=WalkForwardPlan(8, 4, 3, 4), max_candidates=6, max_runs=21,
    )


def main():
    print(regimes_json(run_demo()))


if __name__ == "__main__":
    main()
