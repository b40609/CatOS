"""Twelve synthetic trials; run: python -B -m examples.optuna_demo."""

from collections import deque
from decimal import Decimal

from catos.optimization import DecimalChoices, IntRange, optimize
from catos.research import BacktestConfig, Candle, ContractSpec, Strategy


class SearchSMA(Strategy):
    def __init__(self, params):
        self.closes = deque(maxlen=params["period"])
        self.quantity = params["quantity"]

    def update_indicators(self, bar):
        self.closes.append(bar.close)

    @property
    def ready(self):
        return len(self.closes) == self.closes.maxlen

    def on_bar(self, bar, account):
        average = sum(self.closes, Decimal("0")) / Decimal(len(self.closes))
        return self.quantity if bar.close > average else Decimal("0")


def main():
    prices = ("100", "101", "102", "103", "106", "108", "105", "101", "100", "102", "107", "109")
    bars = tuple(Candle(i * 900_000, Decimal(p), Decimal(p), Decimal(p), Decimal(p))
                 for i, p in enumerate(prices))
    config = BacktestConfig(
        ContractSpec("BTC-USDT-SWAP", Decimal("0.01"), Decimal("0.01"), Decimal("1"), Decimal("1")),
        900_000, Decimal("1000"), Decimal("0.0005"), Decimal("2"), (),
    )
    result = optimize(
        strategy_factory=SearchSMA, search_space={"period": IntRange(2, 4),
                                                "quantity": DecimalChoices(("1", "2", "3"))},
        candles=bars, config=config, score=lambda p: p.return_pct,
        score_name="net return percent = (final equity / initial equity - 1) * 100",
        n_trials=12, seed=7, warmup_bars=4,
    )
    print("Synthetic training data only; not out-of-sample evidence.")
    print(f"Optuna {result.optuna_version}; trials={len(result.trials)}; best={result.best_trial_number}")
    for trial in result.trials:
        print(trial.number, trial.state, dict(trial.params), "Decimal score:", trial.score_decimal,
              "search float:", trial.score_float, "error:", trial.error)


if __name__ == "__main__":
    main()
