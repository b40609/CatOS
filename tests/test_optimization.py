from dataclasses import replace
from decimal import Decimal, localcontext
import unittest
from unittest.mock import patch

import optuna

from catos.optimization import DecimalChoices, IntRange, optimize
from catos.research import BacktestConfig, Candle, ContractSpec, backtest
from examples.optuna_demo import SearchSMA


D = Decimal
BARS = tuple(Candle(i * 900_000, D(p), D(p), D(p), D(p))
             for i, p in enumerate(("100", "101", "102", "105", "107", "104", "100", "103")))
CONFIG = BacktestConfig(ContractSpec("BTC-USDT-SWAP", D("0.01"), D("0.01"), D("1"), D("1")),
                        900_000, D("1000"), D("0.0005"), D("2"), ())
SPACE = {"period": IntRange(2, 3), "quantity": DecimalChoices(("1", "2"))}


def search(**changes):
    options = dict(strategy_factory=SearchSMA, search_space=SPACE, candles=BARS,
                   config=CONFIG, score=lambda p: p.return_pct, score_name="net return percent",
                   n_trials=12, seed=7, warmup_bars=3)
    options.update(changes)
    return optimize(**options)


class OptimizationTests(unittest.TestCase):
    def setUp(self):
        self.verbosity = optuna.logging.get_verbosity()
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        self.addCleanup(optuna.logging.set_verbosity, self.verbosity)

    def test_same_inputs_seed_and_version_reproduce_including_tpe_trials(self):
        first = search()
        with localcontext() as context:
            context.prec = 5
            second = search(search_space=dict(reversed(list(SPACE.items()))))
        self.assertEqual(first, second)
        self.assertEqual(len(first.trials), 12)  # Includes two trials after TPE startup.
        self.assertEqual([r.number for r in first.trials], list(range(12)))
        self.assertTrue(all(r.state == "COMPLETE" for r in first.trials))

    def test_only_score_is_float_and_best_parameters_replay_original_performance(self):
        seen = []

        def factory(params):
            self.assertIs(type(params["period"]), int)
            self.assertIsInstance(params["quantity"], D)
            with self.assertRaises(TypeError):
                params["quantity"] = D("999")
            seen.append(params)
            return SearchSMA(params)

        result = search(strategy_factory=factory)
        self.assertEqual(len(seen), 12)
        for record in result.trials:
            self.assertIsInstance(record.score_decimal, D)
            self.assertIsInstance(record.score_float, float)
            self.assertIsInstance(record.performance.final_equity, D)
            self.assertIsInstance(record.performance.fees, D)
            self.assertIsInstance(dict(record.params)["quantity"], str)
            self.assertEqual(record.score_decimal, record.performance.return_pct)
        best = result.best_trial
        replay = backtest(strategy=lambda: SearchSMA(best.strategy_params()),
                          candles=BARS, config=CONFIG, warmup_bars=3)
        self.assertEqual(replay.performance, best.performance)
        self.assertEqual(best.score_float, max(r.score_float for r in result.trials))

    def test_float_nonfinite_overflow_and_underflow_scores_fail_without_ranking(self):
        for value in (0.1, D("NaN"), D("Infinity"), D("1e1000"), D("1e-1000")):
            with self.subTest(value=value):
                result = search(score=lambda p: value, n_trials=1)
                self.assertIsNone(result.best_trial)
                record = result.trials[0]
                self.assertEqual(record.state, "FAIL")
                self.assertIsNone(record.score_float)
                self.assertIsNotNone(record.error)
                self.assertIsInstance(record.performance.final_equity, D)

    def test_trial_failure_is_recorded_and_attempt_budget_is_not_retried(self):
        calls = 0

        def factory(params):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("synthetic strategy failure")
            return SearchSMA(params)

        result = search(strategy_factory=factory, n_trials=3)
        self.assertEqual(calls, 3)
        self.assertEqual([r.state for r in result.trials], ["FAIL", "COMPLETE", "COMPLETE"])
        self.assertIn("synthetic strategy failure", result.trials[0].error)
        self.assertIn(result.best_trial_number, (1, 2))

    def test_invalid_search_contracts_fail_before_a_study_is_created(self):
        changes = (
            {"n_trials": 0}, {"n_trials": True}, {"seed": -1}, {"seed": 2 ** 32},
            {"direction": "both"}, {"score_name": ""}, {"search_space": {}},
            {"search_space": {"p": IntRange(1, 4, 2)}},
            {"search_space": {"p": IntRange(1, 2, 0)}},
            {"search_space": {"p": IntRange(1.0, 2)}},
            {"search_space": {"p": DecimalChoices(("1.0", "1.00"))}},
            {"search_space": {"p": DecimalChoices((0.1,))}},
            {"search_space": {"p": DecimalChoices(("NaN",))}},
            {"candles": (replace(BARS[0], closed=False),)}, {"warmup_bars": len(BARS)},
        )
        with patch("catos.optimization.optuna.create_study") as create:
            for change in changes:
                with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                    search(**change)
            create.assert_not_called()

    def test_storage_is_memory_only_and_interrupted_trial_is_finished(self):
        studies = []
        real_create = optuna.create_study

        def create(**kwargs):
            self.assertIsInstance(kwargs["storage"], optuna.storages.InMemoryStorage)
            study = real_create(**kwargs)
            studies.append(study)
            return study

        def interrupt(params):
            raise KeyboardInterrupt()

        with patch("catos.optimization.optuna.create_study", side_effect=create):
            with self.assertRaises(KeyboardInterrupt):
                search(strategy_factory=interrupt)
        self.assertEqual(len(studies[0].trials), 1)
        self.assertEqual(studies[0].trials[0].state, optuna.trial.TrialState.FAIL)

    def test_integer_grid_and_decimal_candidates_remain_exact(self):
        space = {"period": IntRange(2, 4, 2), "quantity": DecimalChoices(("1.000000000000000001",))}
        # Exact non-lot Decimal must fail in core, not round to a legal quantity.
        result = search(search_space=space, n_trials=3, warmup_bars=4)
        for record in result.trials:
            self.assertIn(dict(record.params)["period"], (2, 4))
            self.assertEqual(record.strategy_params()["quantity"], D("1.000000000000000001"))
            self.assertEqual(record.state, "FAIL")
            self.assertIn("multiple", record.error)

    def test_minimize_and_float_ties_are_explicit(self):
        result = search(direction="minimize", n_trials=3)
        self.assertEqual(result.best_trial.score_float, min(r.score_float for r in result.trials))
        tied = search(score=lambda p: D("0"), n_trials=3)
        self.assertEqual(tied.best_trial_number, 0)


if __name__ == "__main__":
    unittest.main()
