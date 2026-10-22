from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
import json
import unittest
from unittest.mock import Mock

from catos.optimization import IntRange
from catos.research import BacktestConfig, Candle, ContractSpec, FundingEvent, Strategy, backtest
from catos.research_regimes import (
    REGIMES, RegimeRule, classify_regimes, regime_backtest, regime_walk_forward, regimes_json,
)
from catos.research_validation import WalkForwardPlan, walk_forward


D = Decimal
STEP = 60_000
CONFIG = BacktestConfig(ContractSpec("BTC-USDT-SWAP", D(1), D("0.01"), D(1), D(1)),
                        STEP, D(10000), D(0), D(0), ())
RULE = RegimeRule(2, D("0.5"), D(200))


def candles(prices):
    return tuple(Candle(i*STEP, D(p), D(p), D(p), D(p)) for i, p in enumerate(prices))


BARS = candles((100, 101, 102, 105, 100, 97, 98, 104, 103, 105, 102, 99))


class Hold(Strategy):
    def __init__(self, size=D(1)):
        self.size = size

    def update_indicators(self, bar):
        pass

    def on_bar(self, bar, account):
        return self.size


def run(**changes):
    options = dict(strategy=Hold, candles=BARS, config=CONFIG, rule=RULE)
    options.update(changes)
    return regime_backtest(**options)


def rolling(**changes):
    options = dict(strategy_factory=lambda p: Hold(D(p["size"])),
                   search_space={"size": IntRange(1, 2)}, candles=BARS,
                   config=CONFIG, rule=RULE, score=lambda p: p.net_pnl,
                   score_name="synthetic net PnL", plan=WalkForwardPlan(4, 3, 2, 2),
                   max_candidates=2, max_runs=6)
    options.update(changes)
    return regime_walk_forward(**options)


class ClassificationTests(unittest.TestCase):
    def labels(self, prices, rule=RULE):
        return classify_regimes(candles=candles(prices), config=CONFIG, rule=rule)

    def test_initial_unknown_and_monotonic_directions(self):
        up = self.labels((100, 101, 102, 103))
        self.assertEqual([row.regime for row in up], ["UNKNOWN", "UNKNOWN", "UP_LOW", "UP_LOW"])
        self.assertEqual(up[0].reason, "insufficient_history")
        self.assertIsNone(up[1].efficiency)
        self.assertEqual(up[2].efficiency, D(1))
        self.assertEqual(up[2].close_time_ms, 3*STEP)
        self.assertEqual(self.labels((103, 102, 101))[-1].regime, "DOWN_LOW")

    def test_zero_path_and_round_trip_are_range(self):
        flat = self.labels((100, 100, 100))[-1]
        self.assertEqual((flat.regime, flat.efficiency, flat.volatility_bps), ("RANGE_LOW", D(0), D(0)))
        self.assertEqual(self.labels((100, 110, 100))[-1].regime, "RANGE_HIGH")

    def test_trend_threshold_is_inclusive_and_fixed(self):
        # Net change 2 / absolute path 4 = 0.5.
        labels = self.labels((100, 103, 102))
        self.assertEqual(labels[-1].efficiency, D("0.5"))
        self.assertTrue(labels[-1].regime.startswith("UP_"))
        stricter = self.labels((100, 103, 102), replace(RULE, trend_efficiency=D("0.5001")))
        self.assertTrue(stricter[-1].regime.startswith("RANGE_"))

    def test_volatility_threshold_inclusive_true_range_includes_gaps_and_wicks(self):
        rule = RegimeRule(1, D("0.5"), D(200))
        bars = (Candle(0, D(100), D(100), D(100), D(100)),
                Candle(STEP, D(101), D(102), D(100), D(101)))
        label = classify_regimes(candles=bars, config=CONFIG, rule=rule)[-1]
        self.assertEqual((label.volatility_bps, label.regime), (D(200), "UP_HIGH"))
        self.assertEqual(self.labels((100, 103), rule)[-1].volatility_bps, D(300))

    def test_prefix_is_unchanged_by_future_prices_or_longer_input(self):
        first = classify_regimes(candles=BARS, config=CONFIG, rule=RULE)
        prefix = classify_regimes(candles=BARS[:6], config=CONFIG, rule=RULE)
        changed = BARS[:6] + tuple(replace(b, open=D(900), high=D(900), low=D(900), close=D(900))
                                   for b in BARS[6:])
        second = classify_regimes(candles=changed, config=CONFIG, rule=RULE)
        self.assertEqual(first[:6], prefix)
        self.assertEqual(first[:6], second[:6])

    def test_rule_invalid_values_fail_before_strategy_runs(self):
        factory = Mock(side_effect=AssertionError("must not run"))
        rules = [None, replace(RULE, lookback_bars=True), replace(RULE, lookback_bars=0)]
        rules += [replace(RULE, trend_efficiency=v) for v in (0.5, D(0), D(-1), D("1.1"), D("NaN"))]
        rules += [replace(RULE, high_volatility_bps=v) for v in (10.0, D(0), D(-1), D("Infinity"))]
        for rule in rules:
            with self.subTest(rule=rule), self.assertRaises((TypeError, ValueError)):
                run(strategy=factory, rule=rule)
        factory.assert_not_called()

    def test_invalid_closed_bars_and_timeframe_are_rejected(self):
        cases = ({"candles": ()}, {"candles": BARS[:2] + BARS[3:]},
                 {"candles": (replace(BARS[0], closed=False),)},
                 {"config": replace(CONFIG, timeframe_ms=True)})
        for change in cases:
            with self.subTest(change=change), self.assertRaises((TypeError, ValueError)):
                run(**change)

    def test_classifier_and_rule_are_immutable(self):
        label = self.labels((100, 101, 102))[-1]
        with self.assertRaises(FrozenInstanceError):
            label.regime = "RANGE_LOW"
        with self.assertRaises(FrozenInstanceError):
            RULE.lookback_bars = 1


class AttributionTests(unittest.TestCase):
    def test_current_jump_cannot_label_its_own_pnl(self):
        result = run(candles=candles((100, 100, 100, 120, 120)))
        interval = result.evaluation.intervals[3]
        self.assertEqual(interval.net_pnl, D(20))
        self.assertEqual(interval.regime, "RANGE_LOW")
        self.assertEqual(result.labels[3].regime, "UP_HIGH")
        self.assertEqual(interval.classification_time_ms, interval.open_time_ms)

    def test_cross_regime_hold_allocates_once_without_exit(self):
        result = run()
        rows = result.evaluation.intervals
        self.assertGreater(len({r.regime for r in rows if r.net_pnl}), 2)
        self.assertEqual(sum((r.net_pnl for r in rows), D(0)), D(-2))
        self.assertEqual(result.evaluation.total.net_pnl, result.backtest.performance.net_pnl)
        self.assertEqual(result.evaluation.total.fill_count, 1)
        self.assertEqual(result.backtest.equity_curve[-1].position, D(1))
        self.assertTrue(result.evaluation.reconciled)
        self.assertEqual(result.evaluation.core_net_rounding_residual, D(0))

    def test_unknown_and_empty_regimes_are_retained_with_counts(self):
        result = run(rule=replace(RULE, lookback_bars=100))
        summary = result.evaluation.summaries
        self.assertEqual(tuple(s.regime for s in summary), REGIMES)
        self.assertEqual(summary[0].bar_count, len(BARS))
        self.assertTrue(all(s.bar_count == 0 and s.net_pnl == 0 for s in summary[1:]))
        self.assertEqual(result.evaluation.intervals[0].reason, "no_prior_closed_bar")
        self.assertEqual(result.evaluation.intervals[1].reason, "insufficient_history")
        for row in summary:
            self.assertEqual(row.bar_count, row.positive_bars + row.negative_bars + row.zero_bars)

    def test_warmup_only_provides_classifier_history_not_trades(self):
        result = run(warmup_bars=4)
        self.assertEqual(len(result.evaluation.intervals), 8)
        first = result.evaluation.intervals[0]
        self.assertEqual((first.open_time_ms, first.regime), (4*STEP, result.labels[3].regime))
        self.assertEqual(first.net_pnl, D(0))
        self.assertEqual(result.backtest.trades[0].time_ms, 5*STEP)

    def test_fee_funding_and_boundary_ownership_reconcile(self):
        events = tuple(FundingEvent(t, rate, D(100)) for t, rate in (
            (0, D("0.01")), (STEP, D("0.01")), (2*STEP, D("0.01")),
            (2*STEP+1, D("-0.02")), (len(BARS)*STEP, D("0.03"))))
        config = replace(CONFIG, fee_rate=D("0.001"), slippage_bps=D(10), funding_events=events)
        result = run(config=config)
        rows, total = result.evaluation.intervals, result.evaluation.total
        self.assertEqual([r.funding_payment_count for r in rows[:3]], [2, 1, 1])
        self.assertEqual(rows[0].funding_paid, D(0))
        self.assertEqual(rows[1].funding_paid, D(1))
        self.assertEqual(rows[2].funding_paid, D(-2))
        self.assertEqual(rows[-1].funding_paid, D(3))
        self.assertEqual(total.funding_paid, D(2))
        self.assertEqual(total.fees, result.backtest.performance.fees)
        self.assertGreater(total.fees, D(0))
        self.assertEqual(total.net_pnl + total.fees + total.funding_paid, total.gross_pnl)
        self.assertEqual(total.gross_pnl, D("-2.11"))  # Slippage is not added back.

    def test_reverse_add_reduce_and_close_match_direct_core(self):
        class Targets(Hold):
            def on_bar(self, bar, account):
                return D((1, 3, -2, -1, 0, 1)[(bar.open_time_ms // STEP) % 6])

        config = replace(CONFIG, fee_rate=D("0.0005"), slippage_bps=D(2))
        result = run(strategy=Targets, config=config)
        direct = backtest(strategy=Targets, candles=BARS, config=config)
        self.assertEqual(result.backtest, direct)
        self.assertEqual(result.evaluation.total.fill_count, len(direct.trades))
        self.assertEqual(result.evaluation.total.net_pnl, direct.performance.net_pnl)

    def test_single_bar_has_zero_pnl_and_pending_intent(self):
        result = run(candles=BARS[:1])
        self.assertEqual(result.evaluation.total.net_pnl, D(0))
        self.assertEqual(result.evaluation.total.fill_count, 0)
        self.assertIsNotNone(result.backtest.pending_intent)

    def test_extreme_scale_preserves_explicit_core_rounding_residual(self):
        config = replace(CONFIG, initial_balance=D("1e-18"),
                         contract=replace(CONFIG.contract, base_per_contract=D("1e18")))
        result = run(strategy=lambda: Hold(D("1e18")),
                     candles=candles((100, 100, 101)), config=config)
        evaluation = result.evaluation
        self.assertTrue(evaluation.reconciled)
        self.assertEqual(evaluation.core_net_rounding_residual, D("1e-18"))
        with localcontext() as context:
            context.prec = 80
            self.assertEqual(evaluation.total.net_pnl + evaluation.core_net_rounding_residual,
                             result.backtest.performance.net_pnl)
            self.assertEqual(sum((row.net_pnl for row in evaluation.summaries), D(0)),
                             evaluation.total.net_pnl)

    def test_hash_binds_ohlc_config_and_rule(self):
        original = run()
        alternatives = (run(rule=replace(RULE, high_volatility_bps=D(201))),
                        run(config=replace(CONFIG, fee_rate=D("0.001"))),
                        run(candles=(replace(BARS[0], high=D(101)),) + BARS[1:]))
        self.assertTrue(all(r.input_sha256 != original.input_sha256 for r in alternatives))

    def test_ambient_decimal_context_cannot_change_result_or_json(self):
        first = run(config=replace(CONFIG, fee_rate=D("0.0005"), slippage_bps=D(2)))
        with localcontext() as context:
            context.prec = 3
            second = run(config=replace(CONFIG, fee_rate=D("0.0005"), slippage_bps=D(2)))
        self.assertEqual(regimes_json(first), regimes_json(second))
        payload = json.loads(regimes_json(first))
        self.assertIsInstance(payload["evaluation"]["total"]["net_pnl"], str)
        self.assertIsInstance(payload["labels"][-1]["efficiency"], str)
        with self.assertRaises(TypeError):
            regimes_json(first.backtest)


class WalkForwardRegimeTests(unittest.TestCase):
    def test_oos_remains_identical_to_existing_validation(self):
        result = rolling()
        direct = walk_forward(strategy_factory=lambda p: Hold(D(p["size"])),
                              search_space={"size": IntRange(1, 2)}, candles=BARS,
                              config=CONFIG, score=lambda p: p.net_pnl,
                              score_name="synthetic net PnL", plan=WalkForwardPlan(4, 3, 2, 2),
                              max_candidates=2, max_runs=6)
        self.assertEqual(result.validation, direct)
        self.assertEqual(result.validation.attempted_runs, 6)
        for annotation, window in zip(result.windows, direct.windows):
            self.assertEqual(annotation.evaluation.total.net_pnl, window.out_of_sample.performance.net_pnl)
            self.assertEqual(annotation.evaluation.total.bar_count, 3)
            self.assertEqual(annotation.status, "COMPLETE")

    def test_different_regime_rules_do_not_change_selection_or_oos(self):
        first = rolling()
        second = rolling(rule=RegimeRule(100, D(1), D(9999)))
        self.assertEqual(first.validation, second.validation)
        self.assertNotEqual(first.windows[0].evaluation, second.windows[0].evaluation)

    def test_oos_classification_can_use_training_history_without_strategy_warmup(self):
        result = rolling(plan=WalkForwardPlan(4, 3, 2, 0))
        first = result.windows[0].evaluation.intervals[0]
        self.assertEqual(first.classification_time_ms, 4*STEP)
        self.assertNotEqual(first.regime, "UNKNOWN")
        self.assertEqual(first.net_pnl, D(0))
        self.assertEqual(result.validation.windows[0].out_of_sample.warmup_bars, 0)

    def test_no_selection_retains_failed_trials_and_null_evaluation(self):
        result = rolling(strategy_factory=Mock(side_effect=ValueError("synthetic candidate failed")))
        payload = json.loads(regimes_json(result))
        self.assertFalse(payload["complete"])
        self.assertTrue(all(w.status == "NO_SELECTION" and w.evaluation is None for w in result.windows))
        self.assertTrue(all(t.error for w in result.validation.windows for t in w.training.trials))
        self.assertEqual(payload["validation"]["windows"][0]["status"], "NO_SELECTION")

    def test_oos_failure_retained_and_later_window_runs(self):
        calls = 0

        def factory(params):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise ValueError("synthetic OOS failure")
            return Hold(D(params["size"]))

        result = rolling(strategy_factory=factory)
        self.assertEqual([w.status for w in result.windows], ["OOS_FAILED", "COMPLETE"])
        self.assertIn("synthetic OOS failure", result.windows[0].error)
        self.assertIsNone(result.windows[0].evaluation)
        self.assertTrue(result.windows[1].evaluation.reconciled)

    def test_future_perturbation_preserves_prior_window(self):
        result = rolling()
        changed = BARS[:9] + tuple(replace(b, open=D(900), high=D(900), low=D(900), close=D(900))
                                   for b in BARS[9:])
        altered = rolling(candles=changed)
        self.assertEqual(result.windows[0], altered.windows[0])
        self.assertEqual(result.validation.windows[0], altered.validation.windows[0])
        self.assertNotEqual(result.windows[1].evaluation, altered.windows[1].evaluation)

    def test_budget_still_rejects_before_any_strategy_call(self):
        factory = Mock(side_effect=AssertionError("must not run"))
        with self.assertRaises(ValueError):
            rolling(strategy_factory=factory, max_runs=5)
        factory.assert_not_called()

    def test_interrupt_is_not_hidden_as_missing_regime(self):
        with self.assertRaises(KeyboardInterrupt):
            rolling(strategy_factory=Mock(side_effect=KeyboardInterrupt()))


if __name__ == "__main__":
    unittest.main()
