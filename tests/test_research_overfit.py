"""DSR / PBO statistics and their wiring into optimization and walk-forward payloads (offline).

The formulas were also cross-checked outside the repo against fynance 2.13.1
(research.overfit.pbo, research.guards.deflated_sharpe_ratio) with scipy.stats;
these tests pin the same behavior without those dependencies.
"""

from dataclasses import replace
from decimal import Decimal
import random
import unittest

from catos import research, research_overfit as overfit, research_robustness as robust
from catos.optimization import IntRange, optimize
from catos.research_catalog import _wiped_out, provenance
from catos.research_optimization import execute_optimization, overfit_rows
from catos.research_validation_job import execute_validation
from test_research_costs import CONTRACT, Flip, candles, config
from test_research_datasets import DatasetFixture, request_for, write_fixture


class StatisticsTest(unittest.TestCase):
    def test_expected_max_matches_the_published_bracket(self):
        # N = 100 trials, unit variance: (1-g)·Φ⁻¹(0.99) + g·Φ⁻¹(1-1/(100e)) ≈ 2.531.
        self.assertAlmostEqual(overfit.expected_max_sharpe(1.0, 100), 2.5306, places=4)
        self.assertEqual(overfit.expected_max_sharpe(1.0, 1), 0.0)
        self.assertEqual(overfit.expected_max_sharpe(0.0, 50), 0.0)
        # More trials raise the bar for the same dispersion.
        self.assertGreater(overfit.expected_max_sharpe(1e-4, 40), overfit.expected_max_sharpe(1e-4, 4))

    def test_moments_of_a_hand_checked_series(self):
        stats = overfit.moments([1.0, 2.0, 3.0, 4.0, 10.0])
        self.assertAlmostEqual(stats.mean, 4.0)
        self.assertAlmostEqual(stats.std, 3.5355339059, places=9)  # sample std, ddof=1
        self.assertAlmostEqual(stats.skew, 1.1384199576, places=9)  # biased (population) skew
        # Deviations -3,-2,-1,0,6: m2 = 50/5 = 10, m4 = 1394/5 = 278.8, kurtosis = 278.8/100 (non-excess).
        self.assertAlmostEqual(stats.kurtosis, 2.788, places=9)
        flat = overfit.moments([0.0] * 10)
        self.assertEqual((flat.std, flat.kurtosis), (0.0, 3.0))
        with self.assertRaises(ValueError):
            overfit.moments([1.0, 2.0])

    def test_psr_and_dsr_move_the_right_way(self):
        rng = random.Random(3)
        returns = [rng.gauss(0.001, 0.01) for _ in range(2000)]
        stats = overfit.moments(returns)
        sr = stats.mean / stats.std
        psr = overfit.probabilistic_sharpe(sr, 0.0, stats)
        dsr = overfit.probabilistic_sharpe(sr, overfit.expected_max_sharpe(1e-3, 50), stats)
        self.assertGreater(psr, 0.99)
        self.assertLess(dsr, psr)
        self.assertAlmostEqual(overfit.probabilistic_sharpe(sr, sr, stats), 0.5)

    def test_average_ranks_handle_ties(self):
        self.assertEqual(overfit._average_ranks([3.0, 1.0, 3.0, 2.0]), [3.5, 1.0, 3.5, 2.0])

    def test_pbo_is_zero_for_a_dominant_candidate_and_high_for_noise(self):
        rng = random.Random(5)
        noise = [[rng.gauss(0.0, 0.01) for _ in range(1600)] for _ in range(10)]
        noisy = overfit.pbo_cscv(noise)
        self.assertEqual((noisy["splits"], noisy["blocks"], noisy["bars_per_block"]), (70, 8, 200))
        self.assertGreater(noisy["pbo"], 0.2)
        dominant = [row[:] for row in noise]
        dominant[4] = [value + 0.003 for value in dominant[4]]
        result = overfit.pbo_cscv(dominant)
        self.assertEqual(result["pbo"], 0.0)
        self.assertEqual(result["prob_oos_loss"], 0.0)
        # Too short for 8 blocks of 50 bars, or a single candidate: not computed.
        self.assertIsNone(overfit.pbo_cscv([row[:399] for row in noise]))
        self.assertIsNone(overfit.pbo_cscv(noise[:1]))

    def test_pbo_drops_only_the_leading_remainder(self):
        rng = random.Random(9)
        series = [[rng.gauss(0.0, 0.01) for _ in range(805)] for _ in range(4)]
        self.assertEqual(overfit.pbo_cscv(series), overfit.pbo_cscv([row[5:] for row in series]))

    def test_edge_selections_count_boundaries(self):
        space = {"entry_bars": {"low": 96, "high": 384, "step": 96}, "exit_bars": {"low": 24, "high": 72, "step": 24}}
        windows = [(0, [["entry_bars", 384], ["exit_bars", 48]]), (1, [["entry_bars", 192], ["exit_bars", 24]]),
                   (2, [["entry_bars", 192], ["exit_bars", 48]]), (3, None)]
        edges = overfit.edge_selections(windows, space)
        self.assertEqual((edges["windows_with_selection"], edges["windows_at_edge"]), (3, 2))
        self.assertEqual(edges["params"], {"entry_bars": {"at_low": 0, "at_high": 1},
                                           "exit_bars": {"at_low": 1, "at_high": 0}})


class OptimizerCallbackTest(unittest.TestCase):
    def test_on_result_sees_every_complete_trial_once_with_its_curve(self):
        bars = candles(200)
        seen = []
        result = optimize(
            strategy_factory=lambda params: Flip(params["every"]), search_space={"every": IntRange(3, 9, 2)},
            candles=bars, config=config(), score=lambda p: p.return_pct, score_name="return_pct",
            n_trials=6, seed=1, warmup_bars=3, on_result=lambda params, run: seen.append((params, run)))
        complete = [trial for trial in result.trials if trial.state == "COMPLETE"]
        self.assertEqual([params for params, _ in seen], [trial.params for trial in complete])
        for (_, run), trial in zip(seen, complete):
            self.assertIsInstance(run, research.BacktestResult)
            self.assertEqual(run.performance, trial.performance)


class PayloadTest(DatasetFixture):
    def test_optimization_payload_reports_dsr_and_pbo_for_distinct_trials(self):
        target = write_fixture(self.root, count=960)
        backtest = request_for(target.name, warmup_bars=8, parameters={"period": 2, "quantity": "2"})
        request = {"backtest": backtest, "search_space": {"period": {"low": 2, "high": 8, "step": 1}},
                   "n_trials": 10, "seed": 42}
        payload, report = execute_optimization(request, provenance(target.name))
        report_data = payload["overfitting"]
        distinct = {tuple(map(tuple, sorted(t["params"].items()))) for t in payload["trials"] if t["state"] == "COMPLETE"}
        self.assertEqual(report_data["distinct_trials"], len(distinct))
        self.assertEqual(len(report_data["trials"]), len(distinct))
        best = next(t for t in payload["trials"] if t["number"] == payload["best_trial_number"])
        self.assertEqual(dict(report_data["best"]["params"]), best["params"])
        for key in ("dsr", "psr_vs_zero", "trial_sharpe_variance", "expected_max_sharpe_per_bar"):
            self.assertRegex(report_data[key], r"^-?\d+\.\d+$")
        self.assertEqual(report_data["pbo"]["splits"], 70)
        self.assertIn("DSR", report_data["verdict"])
        self.assertIn("過擬合檢查", report)

    def test_validation_payload_flags_edge_selections(self):
        target = write_fixture(self.root, count=480)
        backtest = request_for(target.name, warmup_bars=4, parameters={"period": 2, "quantity": "2"})
        request = {"backtest": backtest, "search_space": {"period": {"low": 2, "high": 4, "step": 1}},
                   "plan": {"train_bars": 96, "test_bars": 64, "windows": 3},
                   "regime_rule": {"lookback_bars": 4, "trend_efficiency": "0.5", "high_volatility_bps": "250"},
                   "max_candidates": 3, "max_runs": 12}
        payload, report = execute_validation(request, provenance(target.name))
        edges = payload["selection_edges"]
        chosen = [row["training"]["trials"][row["training"]["selected_trial_number"]]["params"][0][1]
                  for row in payload["result"]["validation"]["windows"]
                  if row["training"]["selected_trial_number"] is not None]
        self.assertEqual(edges["windows_with_selection"], len(chosen))
        self.assertEqual(edges["params"]["period"], {"at_low": chosen.count(2), "at_high": chosen.count(4)})
        self.assertEqual(edges["windows_at_edge"], sum(value in (2, 4) for value in chosen))
        self.assertIn("選參落在搜尋範圍邊界", report)


if __name__ == "__main__":
    unittest.main()


class AcceptanceFollowUpTest(unittest.TestCase):
    """Package D/E acceptance observations O1 (coarse PBO) and O4 (switch parameters)."""

    def test_switch_parameters_are_not_counted_as_edge_choices(self):
        space = {"vol_scaling": {"low": 0, "high": 1, "step": 1}}
        edges = overfit.edge_selections([(0, [["vol_scaling", 1]]), (1, [["vol_scaling", 0]])], space)
        self.assertEqual((edges["windows_at_edge"], edges["params"], edges["excluded_switch_params"]),
                         (0, {}, ["vol_scaling"]))
        mixed = {**space, "period": {"low": 8, "high": 32, "step": 8}}
        edges = overfit.edge_selections([(0, [["period", 32], ["vol_scaling", 1]])], mixed)
        self.assertEqual((edges["windows_at_edge"], edges["params"]["period"]["at_high"]), (1, 1))

    def test_coarse_pbo_is_flagged_in_the_verdict(self):
        rng = random.Random(21)
        series = [[rng.gauss(0.0, 0.01) for _ in range(800)] for _ in range(4)]
        result = overfit.pbo_cscv(series)
        self.assertIn("logit_zero_share", result)
        self.assertTrue(0.0 <= result["logit_zero_share"] <= 1.0)
        self.assertIn("粒度很粗", overfit.verdict(0.7, result, trials=4))
        many = {**result, "logit_zero_share": 0.0}
        self.assertNotIn("粒度很粗", overfit.verdict(0.7, many, trials=40))
        self.assertIn("粒度很粗", overfit.verdict(0.7, {**many, "logit_zero_share": 0.2}, trials=40))
        # O1 (2026-11-08): name only the condition that fired.
        ties_only = overfit.verdict(0.7, {**many, "logit_zero_share": 0.2}, trials=40)
        self.assertIn("有 20% 的切法剛好落在中位數", ties_only)
        self.assertNotIn("只有 40 組", ties_only)
        few_only = overfit.verdict(0.7, many, trials=4)
        self.assertIn("只有 4 組參數", few_only)
        self.assertNotIn("0% 的切法", few_only)


class WipedOutTest(unittest.TestCase):
    """Equity <= 0 (no liquidation model): no ratio statistics for that run (F acceptance O5)."""

    def setUp(self):
        bars = candles(480)
        self.runs = {(("every", every),): research.backtest(strategy=lambda every=every: Flip(every), candles=bars,
                                                            config=config(), warmup_bars=3)
                     for every in (3, 5, 7, 9)}

    @staticmethod
    def wipe(run, at=200):
        curve = list(run.equity_curve)
        curve[at:] = [replace(point, equity=point.equity - Decimal("20000")) for point in curve[at:]]
        return replace(run, equity_curve=tuple(curve))

    def test_bar_returns_and_daily_returns_refuse_non_positive_equity(self):
        run = next(iter(self.runs.values()))
        self.assertIsNone(overfit.first_non_positive(run.equity_curve))
        wiped = self.wipe(run)
        self.assertEqual(overfit.first_non_positive(wiped.equity_curve), 200)
        with self.assertRaisesRegex(ValueError, "equity_not_positive"):
            overfit.bar_returns(wiped.equity_curve)
        with self.assertRaisesRegex(ValueError, "equity_not_positive"):
            robust.daily_returns(wiped)
        info = robust.wiped_out(wiped)
        self.assertEqual(info["time_ms"], wiped.equity_curve[200].time_ms)
        self.assertEqual(info["points_at_or_below_zero"], len(wiped.equity_curve) - 200)
        self.assertIsNone(robust.wiped_out(run))
        self.assertIsNone(_wiped_out(run))
        self.assertEqual(_wiped_out(wiped)["min_equity"], min(point.equity for point in wiped.equity_curve))

    def test_wiped_trial_counts_in_n_but_not_in_variance_or_pbo(self):
        names = list(self.runs)
        best = max(names[:3], key=lambda name: self.runs[name].performance.return_pct)
        alive = {name: self.runs[name] for name in names[:3]}
        mixed = {**alive, names[3]: self.wipe(self.runs[names[3]])}
        reference = overfit.search_report(alive, best, 900_000)
        report = overfit.search_report(mixed, best, 900_000)
        self.assertEqual((report["distinct_trials"], report["wiped_out_trials"]), (4, 1))
        self.assertEqual(report["trial_sharpe_variance"], reference["trial_sharpe_variance"])
        self.assertEqual(report["pbo"], reference["pbo"])
        variance = float(reference["trial_sharpe_variance"])
        self.assertEqual(report["expected_max_sharpe_per_bar"], f"{overfit.expected_max_sharpe(variance, 4):.6f}")
        self.assertEqual(report["trials"][3], {"params": [["every", 9]], "sharpe_annualized": None, "wiped_out": True})
        self.assertFalse(report["best"]["wiped_out"])
        self.assertIn("有 1 組參數權益跌破 0（爆倉）", report["verdict"])
        self.assertIn("爆倉", report["notice"])
        self.assertNotIn("爆倉", reference["verdict"] + reference["notice"])

    def test_wiped_best_has_no_dsr(self):
        names = list(self.runs)
        mixed = {**self.runs, names[0]: self.wipe(self.runs[names[0]])}
        report = overfit.search_report(mixed, names[0], 900_000)
        self.assertTrue(report["best"]["wiped_out"])
        self.assertEqual((report["dsr"], report["psr_vs_zero"], report["best"]["sharpe_annualized"]), (None, None, None))
        self.assertTrue(report["verdict"].startswith("最佳參數權益跌破 0（爆倉），無法計算 DSR。"))
        self.assertEqual(report["bars"], len(mixed[names[0]].equity_curve) - 1)
        rows = dict(overfit_rows(report))
        self.assertEqual((rows["最佳 Sharpe（年化）"], rows["權益跌破 0（爆倉）的參數組"]), ("爆倉，不計算", 1))
