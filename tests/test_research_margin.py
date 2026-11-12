"""Backtest margin model: initial-margin rejection and liquidation (docs/research-margin-model.md).

Hand-computed cases on a 0.01 BTC contract, 0.1 tick and whole-contract lots.
Every expected number below is worked out in the comment next to it.
"""

from dataclasses import replace
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from catos import research, research_costs, research_trades
from catos import research_datasets as datasets

TF = 900_000
T0 = 1_790_726_400_000
SHA = "a" * 64
CONTRACT = research.ContractSpec("BTC-USDT-SWAP", D("0.01"), D("0.1"), D("1"), D("1"))
TIERS = (
    research.MarginTier(1, D("1000"), D("0.004"), D("0.01")),
    research.MarginTier(2, D("5000"), D("0.005"), D("0.015")),
    research.MarginTier(3, D("20000"), D("0.0075"), D("0.02")),
)
MODEL = research.MarginModel(TIERS, SHA)


def bar(index, o, h, low, c):
    return research.Candle(T0 + index * TF, D(o), D(h), D(low), D(c))


class Script(research.Strategy):
    """Returns targets[i] after bar i closes (None: leave the position); counts on_bar calls."""

    def __init__(self, targets):
        self.targets, self.index, self.calls = targets, -1, 0

    def update_indicators(self, candle):
        self.index += 1

    def on_bar(self, candle, account):
        self.calls += 1
        value = self.targets.get(self.index)
        return None if value is None else D(value)


def run(bars, targets, balance, *, margin=MODEL, fee="0.0005", funding=()):
    strategy = Script(targets)
    config = research.BacktestConfig(CONTRACT, TF, D(balance), D(fee), D("0"), tuple(funding), margin)
    result = research.backtest(strategy=lambda: strategy, candles=bars, config=config)
    return result, strategy


def reconcile(test, result, bars):
    """Ledger identity, round trips (raise on a residual) and cost attribution."""
    perf = result.performance
    with research.localcontext(research._CONTEXT):
        test.assertEqual(perf.final_equity, perf.initial_equity + perf.realized_pnl - perf.fees
                         - perf.funding_paid - perf.liquidation_cost + perf.unrealized_pnl)
        research_trades.trade_stats(result)
        costs = research_costs.cost_breakdown(result, bars, D("100"))
        test.assertEqual(costs.price_pnl, perf.net_pnl + perf.fees + costs.slippage + perf.funding_paid
                         + perf.liquidation_cost)
        test.assertEqual(costs.liquidation_cost, perf.liquidation_cost)


# Long 100 contracts (1 BTC) at 60000, fee 0.0005 -> entry fee 30. With balance
# 5277.5 the balance after entry is B = 5247.5 and, with m + f = 0.0045,
# P_liq = (60000 - 5247.5) / 0.9955 = 55000 exactly: equity(55000) = 247.5 = 55000 x 0.0045.
LONG_BALANCE = "5277.5"


def long_bars(second):
    return (bar(0, "60000", "60000", "60000", "60000"),
            bar(1, "60000", "60100", "59000", "59500"),
            second,
            bar(3, "56000", "57000", "55500", "56500"))


class LiquidationTest(unittest.TestCase):
    def test_long_equity_equal_to_maintenance_plus_fee_is_liquidated(self):
        bars = long_bars(bar(2, "59000", "59000", "55000", "56000"))
        result, strategy = run(bars, {0: "100", 1: "100", 2: "0", 3: "50"}, LONG_BALANCE)
        liq = result.liquidation
        self.assertIsNotNone(liq)
        self.assertEqual((liq.trigger, liq.trigger_price, liq.liquidation_price, liq.fill_price, liq.gapped),
                         ("adverse_extreme", D("55000"), D("55000"), D("55000"), False))
        self.assertEqual((liq.tier, liq.maintenance_rate, liq.balance_before), (1, D("0.004"), D("5247.5")))
        # realized -5000; notional 55000: liquidation fee 27.5, clearance 220; e = 247.5 = 27.5 + 220.
        self.assertEqual((liq.realized_pnl, liq.liquidation_fee, liq.clearance_fee), (D("-5000"), D("27.5"), D("220")))
        self.assertEqual((liq.fee_charged, liq.clearance_charged, liq.deficit_covered, liq.balance_after),
                         (D("27.5"), D("220"), D("0"), D("0")))
        last = result.trades[-1]
        self.assertEqual((last.time_ms, last.quantity, last.price, last.fee, last.position_after),
                         (bars[2].open_time_ms, D("-100"), D("55000"), D("27.5"), D("0")))
        # Stopped: on_bar ran after bars 0 and 1 only; the later targets never became intents.
        self.assertEqual(strategy.calls, 2)
        self.assertEqual(len(result.trades), 2)
        self.assertIsNone(result.pending_intent)
        self.assertEqual([p.equity for p in result.equity_curve[-2:]], [D("0"), D("0")])
        self.assertEqual(result.performance.liquidation_cost, D("220"))
        self.assertEqual(result.performance.final_equity, D("0"))
        self.assertIn("Single-contract cross margin", result.assumptions[0])
        reconcile(self, result, bars)

    def test_one_tick_above_the_boundary_is_not_liquidated(self):
        # equity(55000.1) = 247.6 > 55000.1 x 0.0045 = 247.50045
        result, strategy = run(long_bars(bar(2, "59000", "59000", "55000.1", "56000")),
                               {0: "100"}, LONG_BALANCE)
        self.assertIsNone(result.liquidation)
        self.assertEqual(strategy.calls, 4)

    def test_short_uses_the_high_and_rounds_the_fill_up(self):
        # Short 100 at 60000; B = 5322.5 - 30 = 5292.5; P_liq = (5292.5 + 60000) / 1.0045 = 65000.
        bars = (bar(0, "60000", "60000", "60000", "60000"),
                bar(1, "60000", "61000", "50000", "60500"),  # a deep low does not matter for a short
                bar(2, "61000", "65000", "60900", "64000"))
        result, _ = run(bars, {0: "-100"}, "5322.5")
        liq = result.liquidation
        self.assertEqual((liq.trigger_price, liq.fill_price, liq.position, liq.balance_after),
                         (D("65000"), D("65000"), D("-100"), D("0")))
        self.assertEqual(liq.bar_open_time_ms, bars[2].open_time_ms)
        reconcile(self, result, bars)
        # Balance 0.1 USDT larger: P_liq = 65292.6 / 1.0045 = 65000.099..., rounded up to 65000.1;
        # the high 65000 no longer reaches it.
        result, _ = run(bars, {0: "-100"}, "5322.6")
        self.assertIsNone(result.liquidation)

    def test_inexact_liquidation_price_rounds_against_the_trader_within_the_bar(self):
        # B = 5247.6: P_liq = 54752.4 / 0.9955 = 54999.899..., rounded down to 54999.8.
        bars = long_bars(bar(2, "59000", "59000", "54990", "56000"))
        result, _ = run(bars, {0: "100"}, "5277.6")
        liq = result.liquidation
        self.assertEqual((liq.liquidation_price, liq.fill_price), (D("54999.8"), D("54999.8")))
        self.assertTrue(bars[2].low <= liq.fill_price <= bars[2].open)
        # e = 5247.6 - 5000.2 = 247.4 < 27.4999 + 219.9992: the clearance takes what is left.
        self.assertEqual((liq.fee_charged, liq.clearance_charged, liq.deficit_covered, liq.balance_after),
                         (D("27.4999"), D("219.9001"), D("0"), D("0")))
        reconcile(self, result, bars)

    def test_gap_through_the_liquidation_price_fills_at_the_open_and_the_fund_covers_the_deficit(self):
        bars = long_bars(bar(2, "54000", "54500", "53900", "54200"))
        result, _ = run(bars, {0: "100"}, LONG_BALANCE)
        liq = result.liquidation
        self.assertEqual((liq.fill_price, liq.gapped, liq.liquidation_price), (D("54000"), True, D("55000")))
        # e = 5247.5 - 6000 = -752.5: nothing to charge, the fund covers 752.5.
        self.assertEqual((liq.fee_charged, liq.clearance_charged, liq.deficit_covered, liq.balance_after),
                         (D("0"), D("0"), D("752.5"), D("0")))
        perf = result.performance
        self.assertEqual((perf.final_equity, perf.liquidation_cost, perf.realized_pnl, perf.fees),
                         (D("0"), D("-752.5"), D("-6000"), D("30")))
        reconcile(self, result, bars)

    def test_close_time_funding_can_trigger_a_liquidation_at_the_close(self):
        # Bar 2 low 55100: equity 347.5 > 247.95. Funding at its close (rate 0.002, mark 55100)
        # costs 110.2, leaving equity 237.3 <= 247.95 at the close.
        bars = long_bars(bar(2, "59000", "59000", "55100", "55100"))
        funding = (research.FundingEvent(bars[3].open_time_ms, D("0.002"), D("55100")),)
        result, strategy = run(bars, {0: "100"}, LONG_BALANCE, funding=funding)
        liq = result.liquidation
        self.assertEqual((liq.trigger, liq.time_ms, liq.fill_price), ("after_funding", bars[3].open_time_ms,
                                                                       D("55100")))
        # e = 5137.3 - 4900 = 237.3: fee 27.55, then clearance 209.75 of 220.4.
        self.assertEqual((liq.fee_charged, liq.clearance_charged, liq.balance_after),
                         (D("27.55"), D("209.75"), D("0")))
        self.assertEqual(strategy.calls, 2)
        reconcile(self, result, bars)

    def test_regime_attribution_counts_a_liquidation_in_its_own_bar(self):
        from catos.research_regimes import RegimeRule, regime_backtest
        rule = RegimeRule(1, D("0.5"), D("200"))
        # After-funding liquidation on the last bar: its fill time is the evaluation end.
        bars = long_bars(bar(2, "59000", "59000", "55100", "55100"))[:3]
        funding = (research.FundingEvent(bars[2].open_time_ms + TF, D("0.002"), D("55100")),)
        for candles, events in ((bars, funding), (long_bars(bar(2, "54000", "54500", "53900", "54200")), ())):
            config = research.BacktestConfig(CONTRACT, TF, D(LONG_BALANCE), D("0.0005"), D("0"), events, MODEL)
            result = regime_backtest(strategy=lambda: Script({0: "100"}), candles=candles, config=config, rule=rule)
            self.assertIsNotNone(result.backtest.liquidation)
            self.assertEqual(result.evaluation.total.fill_count, 2)
            self.assertEqual(result.evaluation.intervals[2].fill_count, 1)

    def test_reversal_switches_the_checked_extreme(self):
        # Long 100, then reverse to short 100 at bar 2's open (same size: no initial-margin check).
        bars = (bar(0, "60000", "60000", "60000", "60000"),
                bar(1, "60000", "60000", "60000", "60000"),
                bar(2, "60000", "60000", "40000", "59000"),  # would liquidate the long, not the short
                bar(3, "59000", "59000", "58000", "58500"))
        result, _ = run(bars, {0: "100", 1: "-100"}, "2000")
        self.assertIsNone(result.liquidation)
        self.assertEqual(result.trades[-1].position_after, D("-100"))
        result, _ = run(bars, {0: "100"}, "2000")
        self.assertEqual(result.liquidation.position, D("100"))

    def test_tier_boundaries(self):
        self.assertEqual([MODEL.tier_for(D(n)).tier for n in ("1", "1000", "1001", "5000", "5001", "20000")],
                         [1, 1, 2, 2, 3, 3])
        self.assertIsNone(MODEL.tier_for(D("20001")))
        # 1001 contracts (10.01 BTC) use tier 2: mmr 0.005.
        bars = long_bars(bar(2, "59000", "59000", "1000", "56000"))
        result, _ = run(bars, {0: "1001"}, "100000")
        self.assertEqual((result.liquidation.tier, result.liquidation.maintenance_rate), (2, D("0.005")))
        result, _ = run(bars, {0: "1000"}, "100000")
        self.assertEqual((result.liquidation.tier, result.liquidation.maintenance_rate), (1, D("0.004")))

    def test_no_margin_model_keeps_the_original_engine(self):
        bars = long_bars(bar(2, "54000", "54500", "53900", "54200"))
        result, strategy = run(bars, {0: "100"}, LONG_BALANCE, margin=None)
        self.assertIsNone(result.liquidation)
        self.assertEqual(strategy.calls, 4)
        self.assertLess(result.equity_curve[-2].equity, 0)
        self.assertEqual(result.assumptions, research._ASSUMPTIONS)


class InitialMarginTest(unittest.TestCase):
    BARS = (bar(0, "60000", "60000", "60000", "60000"),
            bar(1, "60000", "60000", "60000", "60000"),
            bar(2, "60000", "60000", "60000", "60000"),
            bar(3, "60000", "60000", "60000", "60000"))

    def test_growth_beyond_equity_is_rejected_and_reductions_always_pass(self):
        # 100 contracts at 60000 need 60000 x 0.01 = 600; after the 30 fee equity is 610 - 30 = 580.
        result, _ = run(self.BARS, {0: "100"}, "610", fee="0.0005")
        self.assertEqual((result.margin_rejection_count, len(result.trades)), (1, 0))
        rejection = result.margin_rejections[0]
        self.assertEqual((rejection.reason, rejection.equity_after, rejection.required_initial_margin,
                          rejection.target_position), ("insufficient_initial_margin", D("580"), D("600"), D("100")))
        # Exactly enough (630 - 30 = 600) passes.
        result, _ = run(self.BARS, {0: "100"}, "630")
        self.assertEqual((result.margin_rejection_count, len(result.trades)), (0, 1))
        # From 100 long, a same-size reversal and a reduction pass even with no spare equity.
        result, _ = run(self.BARS, {0: "100", 1: "-100", 2: "-50"}, "630")
        self.assertEqual([t.position_after for t in result.trades], [D("100"), D("-100"), D("-50")])
        self.assertEqual(result.margin_rejection_count, 0)
        # A larger reversal is checked: -150 needs 900.
        result, _ = run(self.BARS, {0: "100", 1: "-150"}, "630")
        self.assertEqual(result.margin_rejection_count, 1)
        self.assertEqual(result.trades[-1].position_after, D("100"))

    def test_above_the_last_tier_and_leverage_setting(self):
        result, _ = run(self.BARS, {0: "20001"}, "100000000")
        self.assertEqual(result.margin_rejections[0].reason, "above_max_tier")
        # Leverage 20x: 1/20 = 5% > tier 1's 1%, so 100 contracts (60000 notional) need 3000.
        result, _ = run(self.BARS, {0: "100"}, "2000", margin=replace(MODEL, leverage=D("20")))
        self.assertEqual(result.margin_rejections[0].required_initial_margin, D("3000"))
        # Leverage 200x is above the tier maximum: the tier's 1% still applies (600).
        result, _ = run(self.BARS, {0: "100"}, "610", margin=replace(MODEL, leverage=D("200")))
        self.assertEqual(result.margin_rejections[0].required_initial_margin, D("600"))

    def test_rejections_keep_the_first_twenty_and_count_all(self):
        bars = tuple(bar(i, "60000", "60000", "60000", "60000") for i in range(30))
        result, _ = run(bars, {i: "100" for i in range(30)}, "10")
        self.assertEqual(result.margin_rejection_count, 29)
        self.assertEqual(len(result.margin_rejections), research.MAX_REJECTIONS_KEPT)

    def test_invalid_models_are_refused(self):
        for model, message in (
            (replace(MODEL, tiers_sha256="x"), "sha256"),
            (replace(MODEL, tiers=()), "non-empty"),
            (replace(MODEL, tiers=(TIERS[1], TIERS[0])), "numbered"),
            (replace(MODEL, tiers=(research.MarginTier(1, D("10"), D("0.02"), D("0.01")),)), "mmr < imr"),
            (replace(MODEL, leverage=D("0.5")), "leverage"),
        ):
            with self.assertRaisesRegex(ValueError, message):
                run(self.BARS, {}, "1000", margin=model)


RECORDS = [
    {"tier": "1", "instFamily": "BTC-USDT", "instId": "", "minSz": "0", "maxSz": "1000",
     "mmr": "0.004", "imr": "0.01", "maxLever": "100"},
    {"tier": "2", "instFamily": "BTC-USDT", "instId": "", "minSz": "1000.01", "maxSz": "5000",
     "mmr": "0.005", "imr": "0.015", "maxLever": "66.66"},
]


class TierSnapshotTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "okx"
        patcher = mock.patch.object(datasets, "DATA_ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, records=RECORDS, fetched=T0):
        return datasets.write_position_tiers(self.root, inst_id="BTC-USDT-SWAP", records=records,
                                             fetched_at_ms=fetched, requests=1)

    def test_round_trip_and_newest_snapshot_wins(self):
        first = self.write()
        loaded = datasets.load_position_tiers(first, self.root)
        self.assertEqual(loaded.tiers, (research.MarginTier(1, D("1000"), D("0.004"), D("0.01")),
                                        research.MarginTier(2, D("5000"), D("0.005"), D("0.015"))))
        self.assertEqual(loaded.sha256, datasets.sha256_file(first))
        second = self.write(fetched=T0 + 60_000)
        self.assertEqual(datasets.latest_position_tiers("BTC-USDT-SWAP", self.root).path, second)
        with self.assertRaises(FileExistsError):
            self.write()

    def test_unauthorized_or_malformed_snapshots_are_refused(self):
        with self.assertRaisesRegex(ValueError, "not_authorized"):
            datasets.write_position_tiers(self.root, inst_id="ETH-USDT-SWAP", records=RECORDS,
                                          fetched_at_ms=T0, requests=1)
        gap = [RECORDS[0], {**RECORDS[1], "minSz": "900"}]
        rates = [{**RECORDS[0], "mmr": "0.02"}]
        for records in (gap, rates, [], [{**RECORDS[0], "instFamily": "ETH-USDT"}]):
            with self.assertRaises(ValueError):
                self.write(records)
        path = self.write()
        value = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps({**value, "td_mode": "isolated"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "schema_mismatch"):
            datasets.latest_position_tiers("BTC-USDT-SWAP", self.root)

    def test_dataset_runs_with_the_margin_model_and_lists_the_snapshot(self):
        from test_research_datasets import request_for, write_fixture
        from catos.research_catalog import execute_request, provenance, resolve_dataset
        dataset_id = write_fixture(self.root).name
        off = resolve_dataset(dataset_id)
        self.assertEqual(off.margin_summary()["reason"], "no_position_tiers")
        self.assertIn("未啟用保證金與強平模型", off.notice)
        payload, _ = execute_request(request_for(dataset_id), provenance(dataset_id))
        self.assertFalse(payload["margin_model"]["enabled"])
        self.assertIsNone(payload["result"]["config"]["margin"])

        path = self.write()
        dataset = resolve_dataset(dataset_id)
        summary = dataset.margin_summary()
        self.assertEqual((summary["enabled"], summary["tiers_sha256"], summary["tiers"]),
                         (True, datasets.sha256_file(path), 2))
        source = provenance(dataset_id)
        self.assertEqual(source["dataset"]["files"][datasets.rel_path(path)], summary["tiers_sha256"])
        payload, report = execute_request(request_for(dataset_id), source)
        self.assertTrue(payload["margin_model"]["enabled"])
        self.assertEqual(payload["result"]["config"]["margin"],
                         {"tiers": 2, "tiers_sha256": summary["tiers_sha256"], "leverage": None})
        self.assertIsNone(payload["result"]["liquidation"])
        self.assertIn("保證金與強平", report)
        # A replaced snapshot changes the provenance, so an old expected source is refused.
        self.write(fetched=T0 + 60_000)
        with self.assertRaisesRegex(ValueError, "source_changed"):
            execute_request(request_for(dataset_id), source)

    def test_synthetic_fixture_stays_off(self):
        from catos.research_catalog import DATASET_ID, resolve_dataset
        self.write()
        self.assertEqual(resolve_dataset(DATASET_ID).margin_summary()["reason"], "synthetic_fixture")


if __name__ == "__main__":
    unittest.main()
