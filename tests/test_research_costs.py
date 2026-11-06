"""Cost attribution, buy-and-hold baseline and the partial-funding scenario (offline)."""

from dataclasses import replace
from decimal import Decimal, localcontext
import json
import unittest

from catos import research, research_costs
from catos import research_datasets as datasets
from catos.research_catalog import execute_request, provenance, resolve_dataset
from test_research_datasets import (
    EIGHT_H, START, TF, DatasetFixture, make_bars, make_funding, request_for, write_fixture,
)

CONTRACT = research.ContractSpec("BTC-USDT-SWAP", Decimal("0.01"), Decimal("0.1"), Decimal("0.01"),
                                 Decimal("0.01"))


class Flip(research.Strategy):
    """Long, short, flat in turn every few bars: fills, reversals and funding on both sides."""

    def __init__(self, every=7, quantity=Decimal("2")):
        self.every, self.quantity, self.count = every, quantity, 0

    def update_indicators(self, bar):
        self.count += 1

    def on_bar(self, bar, account):
        if self.count % self.every:
            return None
        return (self.quantity, -self.quantity, Decimal(0))[(self.count // self.every) % 3]


def exact(compute):
    """Expected values in the research engine's 50-digit context."""
    with localcontext(research._CONTEXT):
        return compute()


def candles(count=240):
    return tuple(research.Candle(ms, *(Decimal(value) for value in row))
                 for ms, *row in make_bars(count))


def config(fee="0.0005", slippage="3", funding=()):
    return research.BacktestConfig(CONTRACT, TF, Decimal("10000"), Decimal(fee), Decimal(slippage), funding)


def real_funding(bars):
    opens = {bar.open_time_ms: bar.open for bar in bars}
    end = bars[-1].open_time_ms + TF
    return tuple(research.FundingEvent(ms, Decimal(rate), opens[ms]) for ms, rate, _ in make_funding(START, end))


class CostBreakdownTest(unittest.TestCase):
    def test_price_pnl_equals_an_independent_zero_cost_rerun(self):
        bars = candles()
        funding = real_funding(bars)
        costly = research.backtest(strategy=Flip, candles=bars, config=config(funding=funding), warmup_bars=3)
        free = research.backtest(strategy=Flip, candles=bars, config=config("0", "0", funding), warmup_bars=3)
        self.assertGreater(len(costly.trades), 20)
        self.assertEqual([t.position_after for t in costly.trades], [t.position_after for t in free.trades])
        costs = research_costs.cost_breakdown(costly, bars, Decimal("2"))
        # A zero-cost run fills exactly at the open, so its net plus funding is the price PnL.
        self.assertEqual(costs.price_pnl, free.performance.net_pnl + free.performance.funding_paid)
        self.assertEqual(costs.funding_paid, costly.performance.funding_paid)
        self.assertEqual(costs.net_pnl, costs.price_pnl - costs.fees - costs.slippage - costs.funding_paid)
        self.assertGreater(costs.slippage, 0)
        notional = sum(abs(t.quantity) * CONTRACT.base_per_contract * t.price for t in costly.trades)
        self.assertEqual(costs.traded_notional, notional)
        self.assertEqual(costs.cost_bps_per_side, exact(lambda: (costs.fees + costs.slippage) / notional * 10000))
        self.assertEqual(costs.break_even_bps_per_side,
                         exact(lambda: (costs.price_pnl - costs.funding_paid) / notional * 10000))
        self.assertIsNone(costs.funding_scenario)

    def test_buy_and_hold_uses_the_evaluation_window_only(self):
        bars = candles()
        result = research.backtest(strategy=Flip, candles=bars, config=config(), warmup_bars=5)
        hold = research_costs.cost_breakdown(result, bars, Decimal("2")).buy_hold
        self.assertEqual((hold.entry_open, hold.exit_close), (bars[5].open, bars[-1].close))
        self.assertEqual(hold.pnl, Decimal("2") * CONTRACT.base_per_contract * (bars[-1].close - bars[5].open))
        self.assertEqual(hold.underlying_return_pct, exact(lambda: (bars[-1].close / bars[5].open - 1) * 100))

    def test_scenario_matches_the_engine_charging_the_same_fixed_rate(self):
        bars = candles()
        rate = research_costs.ASSUMED_FUNDING_RATE
        events = tuple(research.FundingEvent(ms, rate, bar.open) for bar in bars
                       for ms in (bar.open_time_ms,) if ms % EIGHT_H == 0)
        plain = research.backtest(strategy=Flip, candles=bars, config=config(), warmup_bars=3)
        charged = research.backtest(strategy=Flip, candles=bars, config=config(funding=events), warmup_bars=3)
        end = bars[-1].open_time_ms + TF
        scenario = research_costs.cost_breakdown(plain, bars, Decimal("2"), end).funding_scenario
        self.assertEqual(scenario.events, len([e for e in charged.funding]))
        self.assertEqual(scenario.assumed_paid, charged.performance.funding_paid)
        self.assertEqual(scenario.net_pnl_with_assumption, charged.performance.net_pnl)
        self.assertNotEqual(scenario.assumed_paid, 0)

    def test_scenario_covers_only_times_before_real_funding_starts(self):
        bars = candles()
        result = research.backtest(strategy=Flip, candles=bars, config=config(), warmup_bars=3)
        start = result.evaluation_start_ms
        funding_from = START + 3 * EIGHT_H
        scenario = research_costs.cost_breakdown(result, bars, Decimal("2"), funding_from).funding_scenario
        expected = len(range(-(-start // EIGHT_H) * EIGHT_H, funding_from, EIGHT_H))
        self.assertEqual((scenario.events, scenario.uncovered_start_ms, scenario.uncovered_end_ms),
                         (expected, start, funding_from))
        self.assertIn("假設情境", scenario.notice)
        # Real funding from the evaluation start: nothing to assume.
        self.assertIsNone(research_costs.cost_breakdown(result, bars, Decimal("2"), start).funding_scenario)

    def test_total_sums_windows_and_recomputes_ratios(self):
        bars = candles()
        first = research.backtest(strategy=Flip, candles=bars[:120], config=config(), warmup_bars=3)
        second = research.backtest(strategy=Flip, candles=bars[120:], config=config(), warmup_bars=3)
        rows = [research_costs.cost_breakdown(first, bars, Decimal("2")),
                research_costs.cost_breakdown(second, bars, Decimal("2"))]
        total = research_costs.total([*rows, None])
        self.assertEqual(total["windows"], 2)
        self.assertEqual(total["net_pnl"], rows[0].net_pnl + rows[1].net_pnl)
        self.assertEqual(total["fill_count"], rows[0].fill_count + rows[1].fill_count)
        notional = rows[0].traded_notional + rows[1].traded_notional
        self.assertEqual(total["cost_bps_per_side"],
                         exact(lambda: (total["fees"] + total["slippage"]) / notional * 10000))
        self.assertIsNone(total["assumed_funding_paid"])
        self.assertIsNone(research_costs.total([None]))


class PartialFundingDatasetTest(DatasetFixture):
    def test_partial_funding_dataset_runs_with_disclosure_and_scenario(self):
        count = 192
        end = START + count * TF
        late = START + 3 * EIGHT_H
        target = write_fixture(self.root, funding=make_funding(late, end))
        manifest = json.loads((target / datasets.MANIFEST).read_text(encoding="utf-8"))
        self.assertFalse(manifest["funding"]["complete"])
        dataset = resolve_dataset(target.name)
        self.assertFalse(dataset.funding_complete)
        self.assertEqual(dataset.describe()["funding_coverage"]["from_ms"], late)
        payload, report = execute_request(request_for(target.name), provenance(target.name))
        self.assertEqual(payload["funding_coverage"]["complete"], False)
        scenario = payload["costs"]["funding_scenario"]
        start = payload["result"]["evaluation_start_ms"]
        self.assertEqual(scenario["events"], len(range(-(-start // EIGHT_H) * EIGHT_H, late, EIGHT_H)))
        self.assertEqual(Decimal(scenario["net_pnl_with_assumption"]),
                         Decimal(payload["result"]["performance"]["net_pnl"]) - Decimal(scenario["assumed_paid"]))
        self.assertIn("成本拆解", report)
        self.assertIn("假設說明", report)
        self.assertIn("之前的期間未計資金費", payload["data_notice"])

    def test_complete_funding_dataset_has_no_scenario(self):
        target = write_fixture(self.root)
        payload, _ = execute_request(request_for(target.name), provenance(target.name))
        self.assertTrue(payload["funding_coverage"]["complete"])
        self.assertIsNone(payload["costs"]["funding_scenario"])
        self.assertEqual(Decimal(payload["costs"]["net_pnl"]),
                         Decimal(payload["result"]["performance"]["net_pnl"]))

    def test_manifest_complete_flag_must_match_the_funding_file(self):
        end = START + 192 * TF
        target = write_fixture(self.root, funding=make_funding(START + 3 * EIGHT_H, end))
        path = target / datasets.MANIFEST
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["funding"]["complete"] = True
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        valid, rejected = datasets.list_datasets()
        self.assertEqual(valid, [])
        self.assertIn("funding_manifest_mismatch", rejected[0][1])


if __name__ == "__main__":
    unittest.main()
