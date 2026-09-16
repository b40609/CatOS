"""Synthetic tests for explicit study specs and Decimal Sharpe; no live data."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from decimal import Decimal as D, localcontext
from io import StringIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from catos import optuna_study as study
from catos.research import AccountView, ContractSpec, _CONTEXT

STEP = 3_600_000


def curve(values, step=STEP):
    return tuple(AccountView(i * step, D(0), D(0), D(value), D(0), D(0), D(value), D(0), D(0))
                 for i, value in enumerate(values))


class SharpeTests(unittest.TestCase):
    def test_decimal_matches_sample_formula(self):
        points = curve(("100", "110", "99", "118.8"))
        with localcontext(_CONTEXT):
            returns = (D("0.1"), D("-0.1"), D("0.2"))
            mean = sum(returns) / D(3)
            variance = sum((r - mean) ** 2 for r in returns) / D(2)
            expected = mean / variance.sqrt() * D(8760).sqrt()
        self.assertEqual(study.compute_annualized_sharpe(points), expected)

    def test_large_equity_small_changes_are_not_rounded_to_float_zero(self):
        points = curve(("1000000000000000000", "1000000000000000001",
                        "1000000000000000003", "1000000000000000002"))
        score = study.compute_annualized_sharpe(points)
        self.assertIsInstance(score, D)
        self.assertGreater(score, D(0))
        with localcontext() as context:
            context.prec = 6
            context.clear_flags()
            self.assertEqual(study.compute_annualized_sharpe(points), score)
            self.assertFalse(any(context.flags.values()))

    def test_nonhourly_annualization_uses_explicit_timeframe(self):
        values = ("100", "110", "99", "118.8")
        hourly = study.compute_annualized_sharpe(curve(values))
        quarter = study.compute_annualized_sharpe(curve(values, STEP // 4), timeframe_ms=STEP // 4)
        with localcontext(_CONTEXT):
            self.assertLess(abs(quarter - 2 * hourly), D("1e-45"))

    def test_insufficient_returns_and_zero_variance_are_unavailable(self):
        for points in ((), curve(("100",)), curve(("100", "110")),
                       curve(("100", "100", "100")), curve(("100", "110", "121"))):
            with self.subTest(points=points):
                self.assertIsNone(study.compute_annualized_sharpe(points))

    def test_bad_equity_is_not_silently_replaced_with_zero_return(self):
        points = curve(("100", "110", "99"))
        for bad in (D(0), D(-1), D("NaN"), D("Infinity"), 100.0):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                study.compute_annualized_sharpe((replace(points[0], equity=bad), *points[1:]))

    def test_invalid_or_nonuniform_timeframes_are_rejected(self):
        points = curve(("100", "110", "99"))
        for bad in (0, -1, True, 3_600_000.0):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                study.compute_annualized_sharpe(points, timeframe_ms=bad)
        with self.assertRaisesRegex(ValueError, "fixed timeframe"):
            study.compute_annualized_sharpe((points[0], points[1], replace(points[2], time_ms=3 * STEP)))


class StudySpecTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.csv = Path(temporary.name) / "synthetic.csv"
        self.csv.write_text("synthetic fixture: loader is mocked", encoding="utf-8")
        self.contract = ContractSpec("SYNTHETIC-USDT-SWAP", D("0.2"), D("0.01"), D("0.5"), D("0.5"))

    def test_missing_or_mismatched_specs_fail_before_search(self):
        for contract in (None, replace(self.contract, inst_id="OTHER-USDT-SWAP")):
            with self.subTest(contract=contract), patch.object(study, "optimize") as search:
                with self.assertRaisesRegex(ValueError, "explicit ContractSpec"):
                    study.run_study(str(self.csv), self.contract.inst_id, contract=contract)
                search.assert_not_called()

    def test_explicit_specs_and_timeframe_reach_search_unchanged(self):
        with patch.object(study, "load_candles_csv", return_value=()) as load, \
                patch.object(study, "optimize", return_value=SimpleNamespace(trials=())) as search, \
                redirect_stdout(StringIO()):
            study.run_study(str(self.csv), self.contract.inst_id, n_trials=1,
                            contract=self.contract, timeframe_ms=900_000)
        self.assertEqual(load.call_args.kwargs["config"].contract, self.contract)
        self.assertEqual(search.call_args.kwargs["config"].contract, self.contract)
        self.assertEqual(search.call_args.kwargs["config"].timeframe_ms, 900_000)
        self.assertEqual(search.call_args.kwargs["warmup_bars"], 80)

    def test_unavailable_sharpe_keeps_trial_performance_visible(self):
        unavailable = "N/A (insufficient returns or zero variance)"
        invalid = "N/A (equity or sampling does not support Sharpe)"
        cases = (
            (curve(("100", "110")), unavailable),
            (curve(("100", "100", "100")), unavailable),
            (curve(("100", "0", "0")), invalid),
            (curve(("100", "110", "99"), STEP // 4), invalid),
        )
        for points, expected_text in cases:
            with self.subTest(points=points):
                final_equity = points[-1].equity
                net_pnl = final_equity - D("100")
                performance = SimpleNamespace(
                    net_pnl=net_pnl, return_pct=net_pnl,
                    max_drawdown_pct=D("100") if final_equity == 0 else D("0"),
                    final_equity=final_equity, trade_count=0, fees=D("0"),
                )
                trial = SimpleNamespace(
                    state="COMPLETE", score_decimal=net_pnl, number=0,
                    params=(("fast", 3), ("slow", 10)), performance=performance,
                )
                output = StringIO()
                with patch.object(study, "load_candles_csv", return_value=()), \
                        patch.object(study, "optimize", return_value=SimpleNamespace(trials=(trial,))), \
                        patch.object(study, "backtest", return_value=SimpleNamespace(equity_curve=points)) as rerun, \
                        redirect_stdout(output):
                    study.run_study(str(self.csv), self.contract.inst_id, n_trials=1,
                                    contract=self.contract, timeframe_ms=STEP)
                text = output.getvalue()
                self.assertIn(expected_text, text)
                self.assertIn(f"{net_pnl} USDT ({net_pnl}%)", text)
                self.assertIn(f"{final_equity} USDT", text)
                self.assertIn("Trial #0", text)
                rerun.assert_called_once()
                self.assertEqual(rerun.call_args.kwargs["config"].contract, self.contract)
                self.assertEqual(rerun.call_args.kwargs["warmup_bars"], 80)

    def test_cli_forwards_all_spec_fields(self):
        with patch.object(study, "run_study") as run:
            self.assertEqual(study.main([
                "--csv", str(self.csv), "--symbol", self.contract.inst_id,
                "--base-per-contract", "0.2", "--tick-size", "0.01",
                "--lot-size", "0.5", "--min-size", "0.5", "--timeframe-ms", "900000",
            ]), 0)
        self.assertEqual(run.call_args.kwargs["contract"], self.contract)
        self.assertEqual(run.call_args.kwargs["timeframe_ms"], 900_000)
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            study.main(["--csv", str(self.csv)])
        self.assertEqual(error.exception.code, 2)

    def test_unknown_metric_does_not_silently_select_another_objective(self):
        with patch.object(study, "optimize") as search:
            with self.assertRaisesRegex(ValueError, "unsupported study metric"):
                study.run_study(str(self.csv), self.contract.inst_id, metric="typo", contract=self.contract)
            search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
