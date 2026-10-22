from dataclasses import replace
from decimal import Decimal, localcontext
import json
import unittest
from unittest.mock import Mock

from catos.optimization import DecimalChoices, IntRange
from catos.research import BacktestConfig, Candle, ContractSpec, FundingEvent, Strategy, backtest
from catos.research_validation import (
    WalkForwardPlan, parameter_stability, validation_json, walk_forward,
)


D = Decimal
STEP = 60_000
BARS = tuple(Candle(i * STEP, D(100 + i), D(100 + i), D(100 + i), D(100 + i))
             for i in range(16))
CONFIG = BacktestConfig(ContractSpec("BTC-USDT-SWAP", D("1"), D("0.01"), D("1"), D("1")),
                        STEP, D("10000"), D("0"), D("0"), ())


class Hold(Strategy):
    def __init__(self, params):
        self.size = D(params["size"])

    def update_indicators(self, bar):
        pass

    @property
    def ready(self):
        return True

    def on_bar(self, bar, account):
        return self.size


def stability(**changes):
    options = dict(strategy_factory=Hold, search_space={"size": IntRange(1, 7)},
                   candles=BARS[:4], config=CONFIG, score=lambda p: p.net_pnl,
                   score_name="net PnL", max_candidates=7)
    options.update(changes)
    return parameter_stability(**options)


def rolling(**changes):
    options = dict(strategy_factory=Hold, search_space={"size": IntRange(1, 2)},
                   candles=BARS[:12], config=CONFIG, score=lambda p: p.net_pnl,
                   score_name="net PnL", plan=WalkForwardPlan(4, 3, 2, 2),
                   max_candidates=2, max_runs=6)
    options.update(changes)
    return walk_forward(**options)


class StabilityTests(unittest.TestCase):
    def test_plateau_beats_isolated_peak_and_records_one_sided_edges(self):
        values = [D(v) for v in (0, 100, 0, 10, 10, 10, 10)]
        result = stability(score=lambda p: values[int(p.net_pnl / D(2)) - 1])
        self.assertEqual(result.selected_trial.strategy_params()["size"], 5)
        self.assertEqual(result.trials[1].score, D(100))
        self.assertEqual(result.neighborhoods[1].worst_score, D(0))
        self.assertEqual(result.neighborhoods[4].worst_score, D(10))
        self.assertEqual(result.neighborhoods[0].members, (0, 1))
        self.assertEqual(result.neighborhoods[-1].members, (6, 5))

    def test_minimize_uses_worst_loss_and_ties_use_grid_order(self):
        values = [D(v) for v in (0, -100, 0, -10, -10, -10, -10)]
        result = stability(score=lambda p: values[int(p.net_pnl / D(2)) - 1], direction="minimize")
        self.assertEqual(result.selected_trial.strategy_params()["size"], 5)
        tied = stability(score=lambda p: D(-1))
        self.assertEqual(tied.selected_trial_number, 0)
        self.assertLess(tied.selected_trial.score, D(0))  # Selection is not a profit gate.

    def test_failed_neighbor_is_not_silently_excluded(self):
        def factory(params):
            if params["size"] == 2:
                raise ValueError("bad candidate")
            return Hold(params)

        result = stability(strategy_factory=factory)
        self.assertIn("bad candidate", result.trials[1].error)
        self.assertTrue(all(not row.complete for row in result.neighborhoods[:3]))
        self.assertTrue(all(row.complete for row in result.neighborhoods[3:]))
        self.assertIsNone(result.neighborhoods[0].worst_score)

    def test_numeric_decimal_axes_and_immutable_factory_parameters(self):
        seen = []

        def factory(params):
            self.assertIsInstance(params["size"], D)
            with self.assertRaises(TypeError):
                params["size"] = D(99)
            seen.append(params["size"])
            return Hold(params)

        result = stability(strategy_factory=factory, search_space={
            "size": DecimalChoices(("10.00", "2.000", "1.00")), "unused": IntRange(1, 2)})
        self.assertEqual(result.axes[0][1], ("1.00", "2.000", "10.00"))
        self.assertEqual(seen, [D(1), D(1), D(2), D(2), D(10), D(10)])
        self.assertEqual(set(result.neighborhoods[2].members), {0, 2, 3, 4})
        self.assertNotIn(1, result.neighborhoods[2].members)  # No diagonal neighbor.
        self.assertEqual(dict(result.trials[0].params)["size"], "1.00")

    def test_decimal_context_determinism_and_direct_core_replay(self):
        config = replace(CONFIG, fee_rate=D("0.0005"), slippage_bps=D("2"))
        first = stability(config=config)
        with localcontext() as context:
            context.prec = 5
            second = stability(config=config)
        self.assertEqual(first, second)
        best = first.selected_trial
        replay = backtest(strategy=lambda: Hold(best.strategy_params()), candles=BARS[:4], config=config)
        self.assertEqual(best.performance, replay.performance)
        self.assertEqual(best.terminal_position, replay.equity_curve[-1].position)
        self.assertGreater(best.performance.fees, D(0))
        self.assertGreater(best.performance.unrealized_pnl, D(0))

    def test_invalid_scores_preserve_performance_but_cannot_be_selected(self):
        for value in (0.1, D("NaN"), D("Infinity"), D("1e1000"), D("1e-1000"),
                      D("1.12345678901234567890123456789012345678901234567890123456789")):
            with self.subTest(value=value):
                result = stability(score=lambda p: value)
                self.assertIsNone(result.selected_trial)
                self.assertTrue(all(row.error and row.score is None for row in result.trials))
                self.assertTrue(all(row.performance is not None for row in result.trials))

    def test_large_valid_scores_do_not_overflow_neighborhood_sum(self):
        result = stability(score=lambda p: D("9e99"))
        self.assertEqual(result.neighborhoods[1].mean_score, D("9e99"))
        self.assertEqual(result.selected_trial_number, 0)

    def test_preflight_rejects_invalid_grid_data_and_budget_without_strategy_calls(self):
        factory = Mock(side_effect=AssertionError("must not execute"))
        cases = (
            {"max_candidates": 6}, {"max_candidates": True}, {"score_name": " "},
            {"direction": "both"}, {"search_space": {}},
            {"search_space": {"size": IntRange(1, 1)}},
            {"search_space": {"size": IntRange(0, 2_000_000_000)}},
            {"search_space": {"size": DecimalChoices(("1", "1.0"))}},
            {"candles": (replace(BARS[0], closed=False),)},
            {"candles": (BARS[0], BARS[2])}, {"warmup_bars": 4}, {"warmup_bars": True},
        )
        for change in cases:
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                stability(strategy_factory=factory, **change)
        factory.assert_not_called()

    def test_interruptions_are_not_swallowed(self):
        with self.assertRaises(KeyboardInterrupt):
            stability(strategy_factory=Mock(side_effect=KeyboardInterrupt()))

    def test_json_is_decimal_exact_deterministic_and_hash_tracks_inputs(self):
        result = stability()
        self.assertEqual(validation_json(result), validation_json(stability()))
        payload = json.loads(validation_json(result))
        self.assertEqual(payload["trials"][0]["performance"]["net_pnl"], "2")
        self.assertEqual(payload["trials"][0]["score"], "2")
        self.assertTrue(payload["assumptions"])
        changed = stability(config=replace(CONFIG, fee_rate=D("0.001")))
        self.assertNotEqual(changed.input_sha256, result.input_sha256)
        with self.assertRaises(TypeError):
            validation_json("not a result")


class WalkForwardTests(unittest.TestCase):
    def test_explicit_rolling_ranges_and_run_budget(self):
        result = rolling(candles=BARS)
        self.assertTrue(result.complete)
        self.assertEqual((result.required_runs, result.attempted_runs, result.unused_bars), (6, 6, 4))
        self.assertEqual([(w.train_start_ms, w.train_end_ms, w.test_start_ms, w.test_end_ms)
                          for w in result.windows], [(2*STEP, 6*STEP, 6*STEP, 9*STEP),
                                                      (5*STEP, 9*STEP, 9*STEP, 12*STEP)])
        self.assertEqual(json.loads(validation_json(result))["windows"][0]["status"], "COMPLETE")

    def test_future_prices_cannot_change_earlier_training_selection_or_results(self):
        first = rolling()
        bars = list(BARS[:12])
        for i in range(9, 12):
            bars[i] = replace(bars[i], open=D(50), high=D(50), low=D(50), close=D(50))
        second = rolling(candles=bars)
        self.assertEqual(first.windows[0], second.windows[0])
        self.assertEqual(first.windows[1].training, second.windows[1].training)
        self.assertNotEqual(first.windows[1].out_of_sample.performance,
                            second.windows[1].out_of_sample.performance)
        self.assertNotEqual(first.input_sha256, second.input_sha256)

    def test_every_trial_is_fresh_and_oos_warmup_has_no_trades_or_carried_intents(self):
        strategies = []

        class Observed(Hold):
            def __init__(self, params):
                super().__init__(params)
                self.updates, self.decisions = [], []
                strategies.append(self)

            def update_indicators(self, bar):
                self.updates.append(bar.open_time_ms)

            def on_bar(self, bar, account):
                self.decisions.append((bar.open_time_ms, account.position))
                return super().on_bar(bar, account)

        result = rolling(strategy_factory=Observed)
        self.assertEqual(len(strategies), 6)
        for strategy in strategies:
            self.assertEqual(strategy.decisions[0][0], strategy.updates[2])
            self.assertEqual(strategy.decisions[0][1], D(0))
        for window, strategy in zip(result.windows, (strategies[2], strategies[5])):
            self.assertEqual(strategy.updates[0], window.test_start_ms - 2*STEP)
            self.assertEqual(window.out_of_sample.trades[0].time_ms, window.test_start_ms + STEP)
            self.assertEqual(window.out_of_sample.performance.initial_equity, CONFIG.initial_balance)

    def test_funding_fees_and_terminal_equity_match_direct_core_replays(self):
        events = tuple(FundingEvent(i*STEP, D("0.001"), D(100+i)) for i in (0, 6, 8, 9, 11, 12))
        config = replace(CONFIG, funding_events=events, fee_rate=D("0.0005"), slippage_bps=D(2))
        result = rolling(config=config)
        for window in result.windows:
            start, end = window.test_start_ms // STEP, window.test_end_ms // STEP
            subset = BARS[start-2:end]
            filtered = tuple(e for e in events if subset[0].open_time_ms <= e.time_ms <= end*STEP)
            replay = backtest(strategy=lambda: Hold(window.training.selected_trial.strategy_params()),
                              candles=subset, config=replace(config, funding_events=filtered), warmup_bars=2)
            self.assertEqual(window.out_of_sample, replay)
            self.assertGreater(replay.performance.funding_paid, D(0))
            self.assertGreater(replay.performance.fees, D(0))
            self.assertGreater(replay.performance.unrealized_pnl, D(0))
            self.assertTrue(all(e.time_ms >= window.test_start_ms for e in replay.funding))

    def test_no_selection_skips_oos_and_preserves_all_training_failures(self):
        factory = Mock(side_effect=ValueError("all candidates failed"))
        result = rolling(strategy_factory=factory)
        self.assertFalse(result.complete)
        self.assertEqual(result.attempted_runs, 4)
        self.assertEqual(factory.call_count, 4)
        self.assertTrue(all(w.status == "NO_SELECTION" and w.out_of_sample is None
                            for w in result.windows))
        self.assertTrue(all(t.error for w in result.windows for t in w.training.trials))

    def test_oos_failure_is_retained_when_same_bad_bar_enters_later_training(self):
        class FailOnTest(Hold):
            def on_bar(self, bar, account):
                if bar.open_time_ms == 6*STEP:
                    raise ValueError("OOS synthetic failure")
                return super().on_bar(bar, account)

        result = rolling(strategy_factory=FailOnTest)
        self.assertFalse(result.complete)
        self.assertEqual(result.windows[0].status, "OOS_FAILED")
        self.assertIn("OOS synthetic failure", result.windows[0].error)
        # That bar also enters later training, so failures remain explicit there.
        self.assertEqual(result.windows[1].status, "NO_SELECTION")
        self.assertEqual(result.attempted_runs, 5)

    def test_one_oos_factory_failure_does_not_stop_independent_later_window(self):
        calls = 0

        def factory(params):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RuntimeError("first OOS factory failed")
            return Hold(params)

        result = rolling(strategy_factory=factory)
        self.assertEqual([w.status for w in result.windows], ["OOS_FAILED", "COMPLETE"])
        self.assertEqual(result.attempted_runs, 6)
        self.assertFalse(result.complete)

    def test_first_oos_change_does_not_change_its_own_frozen_training_choice(self):
        first = rolling()
        bars = list(BARS[:12])
        for i in range(6, 9):
            bars[i] = replace(bars[i], open=D(50), high=D(50), low=D(50), close=D(50))
        second = rolling(candles=bars)
        self.assertEqual(first.windows[0].training, second.windows[0].training)
        self.assertNotEqual(first.windows[0].out_of_sample.performance,
                            second.windows[0].out_of_sample.performance)
        self.assertNotEqual(first.windows[1].training, second.windows[1].training)

    def test_entire_walk_forward_is_deterministic_under_ambient_decimal_context(self):
        first = rolling(config=replace(CONFIG, fee_rate=D("0.0005"), slippage_bps=D(2)))
        with localcontext() as context:
            context.prec = 4
            second = rolling(config=replace(CONFIG, fee_rate=D("0.0005"), slippage_bps=D(2)))
        self.assertEqual(validation_json(first), validation_json(second))

    def test_preflight_does_not_run_even_one_candidate(self):
        factory = Mock(side_effect=AssertionError("must not execute"))
        for change in ({"max_runs": 5}, {"max_runs": True}, {"max_candidates": 1},
                       {"plan": WalkForwardPlan(4, 3, True, 2)},
                       {"plan": WalkForwardPlan(4, 3, 2, -1)},
                       {"plan": WalkForwardPlan(4, 3, 2, True)},
                       {"plan": WalkForwardPlan(0, 3, 2)}, {"candles": BARS[:11]},
                       {"candles": BARS[:5] + BARS[6:13]}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                rolling(strategy_factory=factory, **change)
        factory.assert_not_called()

    def test_keyboard_interrupt_in_oos_propagates(self):
        calls = 0

        def factory(params):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise KeyboardInterrupt()
            return Hold(params)

        with self.assertRaises(KeyboardInterrupt):
            rolling(strategy_factory=factory)
        self.assertEqual(calls, 3)

    def test_one_bar_oos_is_explicitly_untraded_and_not_fabricated(self):
        result = rolling(plan=WalkForwardPlan(4, 1, 2, 2))
        self.assertTrue(result.complete)
        for window in result.windows:
            self.assertEqual(window.out_of_sample.trades, ())
            self.assertEqual(window.out_of_sample.performance.net_pnl, D(0))
            self.assertIsNotNone(window.out_of_sample.pending_intent)


if __name__ == "__main__":
    unittest.main()
