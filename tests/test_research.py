"""Bounded synthetic scenarios for the closed-bar research module only."""

from dataclasses import asdict, replace
from decimal import Decimal, getcontext, localcontext
import unittest

from catos.research import (
    BacktestConfig, Candle, ContractSpec, FundingEvent, Strategy, backtest,
)


D = Decimal
STEP = 900_000  # 15-minute bars, never a supplemental 1m stream.


def candles(*prices):
    return tuple(Candle(i * STEP, D(p), D(p), D(p), D(p)) for i, p in enumerate(prices))


def config(**changes):
    base = BacktestConfig(
        contract=ContractSpec("BTC-USDT-SWAP", D("0.01"), D("0.25"), D("1"), D("1")),
        timeframe_ms=STEP, initial_balance=D("1000"), fee_rate=D("0"),
        slippage_bps=D("0"), funding_events=(),
    )
    return replace(base, **changes)


class Script(Strategy):
    def __init__(self, targets=None, ready_after=0):
        self.targets = targets or {}
        self.ready_after = ready_after
        self.updated = []
        self.decisions = []

    def update_indicators(self, bar):
        self.updated.append(bar)

    @property
    def ready(self):
        return len(self.updated) >= self.ready_after

    def on_bar(self, bar, account):
        self.decisions.append((bar.open_time_ms, tuple(self.updated), account))
        return self.targets.get(bar.open_time_ms // STEP)


def run(prices, targets=None, *, cfg=None, warmup=0):
    return backtest(strategy=lambda: Script(targets), candles=candles(*prices),
                    config=cfg or config(), warmup_bars=warmup)


class ResearchTests(unittest.TestCase):
    def test_warmup_only_updates_indicators_and_excludes_accounting(self):
        strategy = Script({0: D("99"), 1: D("99"), 2: D("2")}, ready_after=2)
        cfg = config(fee_rate=D("0.001"), funding_events=(FundingEvent(STEP, D("0.1"), D("110")),))
        result = backtest(strategy=lambda: strategy,
                          candles=candles("100", "110", "120", "130"), config=cfg, warmup_bars=2)
        self.assertEqual(len(strategy.updated), 4)
        self.assertEqual([d[0] for d in strategy.decisions], [2 * STEP, 3 * STEP])
        self.assertEqual(result.evaluation_start_ms, 2 * STEP)
        self.assertEqual([p.time_ms for p in result.equity_curve], [2 * STEP, 3 * STEP, 4 * STEP])
        self.assertEqual(result.funding, ())
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades[0].quantity, D("2"))
        self.assertEqual(result.trades[0].time_ms, 3 * STEP)
        self.assertEqual(result.trades[0].price, D("130"))
        self.assertEqual(result.equity_curve[1].fees, D("0"))
        self.assertEqual(result.performance.fees, D("0.0026"))

    def test_zero_warmup_first_signal_fills_only_at_next_open(self):
        result = run(("100", "110"), {0: D("2")})
        self.assertEqual(len(result.trades), 1)
        trade = result.trades[0]
        self.assertEqual((trade.decision_time_ms, trade.time_ms), (STEP, STEP))
        self.assertEqual(trade.price, D("110"))
        self.assertEqual(result.equity_curve[1].position, D("0"))

    def test_warmup_counts_and_readiness_fail_explicitly(self):
        for count in (-1, 1.5, True, 2, 3):
            with self.subTest(count=count), self.assertRaises((ValueError, TypeError)):
                run(("100", "100"), warmup=count)
        with self.assertRaisesRegex(ValueError, "not ready after warm-up"):
            backtest(strategy=lambda: Script(ready_after=3),
                     candles=candles("100", "100", "100"), config=config(), warmup_bars=2)
        with self.assertRaisesRegex(ValueError, "not ready for evaluation"):
            backtest(strategy=lambda: Script(ready_after=3),
                     candles=candles("100", "100"), config=config())

    def test_indicator_callback_cannot_return_a_warmup_intent(self):
        class BadIndicators(Script):
            def update_indicators(self, bar):
                return D("3")

        with self.assertRaisesRegex(ValueError, "never an intent"):
            backtest(strategy=BadIndicators, candles=candles("100", "100"),
                     config=config(), warmup_bars=1)

    def test_callbacks_observe_only_the_current_closed_prefix(self):
        strategy = Script()
        backtest(strategy=lambda: strategy, candles=candles("100", "110", "120"), config=config())
        for index, (time_ms, history, account) in enumerate(strategy.decisions):
            self.assertEqual(time_ms, index * STEP)
            self.assertEqual(len(history), index + 1)
            self.assertEqual(account.time_ms, (index + 1) * STEP)
            self.assertTrue(all(bar.open_time_ms <= time_ms for bar in history))
        before = run(("100", "110", "120"), {0: D("2")})
        after = run(("100", "110", "999"), {0: D("2")})
        self.assertEqual(before.equity_curve[:3], after.equity_curve[:3])
        self.assertEqual(before.trades, after.trades)

    def test_adverse_slippage_non_power_of_ten_tick_and_contract_fees(self):
        result = run(("100", "110", "100"), {0: D("2"), 1: D("0")},
                     cfg=config(fee_rate=D("0.001"), slippage_bps=D("10")))
        self.assertEqual([t.price for t in result.trades], [D("110.25"), D("99.75")])
        self.assertEqual([t.fee for t in result.trades], [D("0.002205"), D("0.001995")])
        self.assertEqual(result.performance.realized_pnl, D("-0.21"))
        self.assertEqual(result.performance.fees, D("0.0042"))
        self.assertEqual(result.performance.final_equity, D("999.7858"))
        self.assertEqual(result.performance.return_pct, D("-0.02142"))
        self.assertEqual(result.performance.max_drawdown_pct, D("0.02142"))

    def test_scale_reduce_reverse_and_flat_preserve_net_accounting(self):
        cfg = config(contract=replace(config().contract, base_per_contract=D("0.1")))
        result = run(("100", "100", "120", "130", "90", "80"),
                     {0: D("2"), 1: D("4"), 2: D("1"), 3: D("-2"), 4: D("0")}, cfg=cfg)
        self.assertEqual([t.quantity for t in result.trades], [D("2"), D("2"), D("-3"), D("-3"), D("2")])
        self.assertEqual([t.realized_pnl for t in result.trades], [D("0"), D("0"), D("6"), D("-2"), D("2")])
        self.assertEqual(result.equity_curve[3].average_entry, D("110"))
        self.assertEqual(result.equity_curve[4].average_entry, D("110"))
        self.assertEqual(result.equity_curve[5].average_entry, D("90"))
        self.assertEqual(result.equity_curve[-1].average_entry, D("0"))
        self.assertEqual(result.performance.net_pnl, D("6"))

    def test_short_to_long_realizes_only_the_closed_quantity(self):
        result = run(("100", "100", "80", "90"), {0: D("-2"), 1: D("1"), 2: D("0")})
        self.assertEqual([t.realized_pnl for t in result.trades], [D("0"), D("0.4"), D("0.1")])
        self.assertEqual(result.performance.final_equity, D("1000.5"))

    def test_repeated_target_is_not_repeated_buying(self):
        result = run(("100", "100", "100", "100"), {i: D("2") for i in range(4)})
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.equity_curve[-1].position, D("2"))
        self.assertIsNone(result.pending_intent)

    def test_last_signal_is_unfilled_and_open_position_is_not_forced_flat(self):
        one_bar = run(("100",), {0: D("2")})
        self.assertEqual(one_bar.trades, ())
        self.assertEqual(one_bar.pending_intent.target_position, D("2"))
        result = run(("100", "100", "120"), {0: D("2"), 2: D("0")})
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.pending_intent.target_position, D("0"))
        self.assertEqual(result.equity_curve[-1].position, D("2"))
        self.assertEqual(result.performance.realized_pnl, D("0"))
        self.assertEqual(result.performance.unrealized_pnl, D("0.4"))
        self.assertEqual(result.performance.final_equity, D("1000.4"))

    def test_funding_uses_signed_position_and_supplied_settlement_mark(self):
        events = (FundingEvent(STEP + 1, D("0.01"), D("200")),
                  FundingEvent(STEP + 2, D("-0.02"), D("150")))
        for quantity, expected in ((D("2"), D("-0.02")), (D("-2"), D("0.02"))):
            with self.subTest(quantity=quantity):
                result = run(("100", "100", "100"), {0: quantity}, cfg=config(funding_events=events))
                self.assertEqual(result.performance.funding_paid, expected)
                self.assertEqual(result.performance.final_equity, D("1000") - expected)
                self.assertEqual(result.funding[0].mark_price, D("200"))

    def test_boundary_funding_precedes_entry_and_exit_at_the_same_open(self):
        events = (FundingEvent(STEP, D("0.01"), D("200")),
                  FundingEvent(2 * STEP, D("0.01"), D("200")))
        result = run(("100", "100", "100"), {0: D("2"), 1: D("0")}, cfg=config(funding_events=events))
        self.assertEqual([f.position for f in result.funding], [D("0"), D("2")])
        self.assertEqual([f.amount_paid for f in result.funding], [D("0"), D("0.04")])
        self.assertEqual(result.equity_curve[-1].position, D("0"))
        self.assertEqual(result.performance.final_equity, D("999.96"))

    def test_invalid_market_data_is_rejected_before_strategy_creation(self):
        good = candles("100", "110")
        cases = (
            (), (replace(good[0], closed=False),),
            (replace(good[0], open=100.0),),
            (replace(good[0], close=D("NaN")),),
            (replace(good[0], high=D("99")),),
            (replace(good[0], open=D("100.1")),),
            (good[1], good[0]), (good[0], good[0]),
            (good[0], replace(good[1], open_time_ms=3 * STEP)),
        )
        for case in cases:
            with self.subTest(case=case), self.assertRaises((ValueError, TypeError)):
                backtest(strategy=lambda: self.fail("strategy ran before validation"),
                         candles=case, config=config())

    def test_float_nonfinite_off_lot_and_too_small_targets_are_rejected(self):
        for target in (1.0, D("Infinity"), D("0.5"), D("1e100"), D("1e-100")):
            with self.subTest(target=target), self.assertRaises((ValueError, TypeError)):
                run(("100", "100"), {0: target})
        with self.assertRaisesRegex(ValueError, "below min_size"):
            run(("100", "100"), {0: D("1")},
                cfg=config(contract=replace(config().contract, min_size=D("2"))))

    def test_invalid_config_and_funding_are_rejected(self):
        event = FundingEvent(STEP, D("0.01"), D("100"))
        cases = (
            config(initial_balance=1000.0), config(initial_balance=D("0")),
            config(fee_rate=D("NaN")), config(fee_rate=D("-0.001")),
            config(slippage_bps=D("10000")), config(timeframe_ms=True),
            config(funding_events=[]), config(funding_events=(event, event)),
            config(funding_events=(replace(event, time_ms=3 * STEP),)),
            config(funding_events=(replace(event, mark_price=100.0),)),
            config(contract=replace(config().contract, base_per_contract=D("0"))),
        )
        for cfg in cases:
            with self.subTest(cfg=cfg), self.assertRaises((ValueError, TypeError)):
                run(("100", "100"), cfg=cfg)

    def test_sell_tick_rounding_cannot_produce_zero_price(self):
        cfg = config(contract=replace(config().contract, tick_size=D("1")), slippage_bps=D("1"))
        with self.assertRaisesRegex(ValueError, "nonpositive fill"):
            run(("1", "1"), {0: D("-1")}, cfg=cfg)

    def test_repeated_runs_and_decimal_context_are_isolated(self):
        targets = {0: D("2"), 1: D("0")}

        class ChangesContext(Script):
            def on_bar(self, bar, account):
                getcontext().prec = 3
                return super().on_bar(bar, account)

        cfg = config(fee_rate=D("0.001"), slippage_bps=D("10"))
        expected = run(("100", "110", "100"), targets, cfg=cfg)
        with localcontext() as outer:
            outer.prec = 6
            actual = backtest(strategy=lambda: ChangesContext(targets),
                              candles=candles("100", "110", "100"), config=cfg)
            self.assertEqual(outer.prec, 6)
        self.assertEqual(actual, expected)
        self.assertEqual(run(("100", "110", "100"), targets, cfg=cfg), expected)

    def test_accounting_identity_and_all_outputs_remain_decimal(self):
        cfg = config(fee_rate=D("0.001"), funding_events=(FundingEvent(2 * STEP, D("0.01"), D("120")),))
        result = run(("100", "110", "120", "90"), {0: D("2"), 2: D("0")}, cfg=cfg)
        for view in result.equity_curve:
            self.assertEqual(view.balance, cfg.initial_balance + view.realized_pnl - view.fees - view.funding_paid)
            self.assertEqual(view.equity, view.balance + view.unrealized_pnl)
        self.assertEqual(result.performance.net_pnl,
                         result.performance.realized_pnl + result.performance.unrealized_pnl
                         - result.performance.fees - result.performance.funding_paid)

        def check(value):
            self.assertNotIsInstance(value, float)
            if isinstance(value, dict):
                for child in value.values():
                    check(child)
            elif isinstance(value, (tuple, list)):
                for child in value:
                    check(child)

        check(asdict(result))


if __name__ == "__main__":
    unittest.main()
