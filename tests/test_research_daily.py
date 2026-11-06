"""Package E daily strategies and robustness checks on synthetic 4H bars (offline)."""

from decimal import Decimal
import unittest

from catos import research, research_daily as daily, research_robustness as robust
from catos.research_catalog import (
    DAILY_WARMUP_DAYS, STRATEGIES, buy_hold_quantity, registered_factory, provenance, validate_request,
)
from catos.strategy_registry import resolve as worker_resolve
from test_research_datasets import DatasetFixture, request_for, write_fixture

D = Decimal
H4 = 14_400_000
DAY = 86_400_000
START = 1_640_995_200_000  # 2022-01-01 00:00 UTC
CONTRACT = research.ContractSpec("BTC-USDT-SWAP", D("0.01"), D("0.1"), D("0.01"), D("0.01"))


def bars_from_daily(closes, start=START, first_hour=0):
    """Six 4H bars per day walking linearly from the previous close to the day's close."""
    bars, previous = [], D(closes[0])
    for day, close in enumerate(map(D, closes)):
        for slot in range(6):
            open_ms = start + day * DAY + slot * H4
            if open_ms < start + first_hour * 3_600_000:
                continue
            step_open = previous + (close - previous) * D(slot) / D(6)
            step_close = previous + (close - previous) * D(slot + 1) / D(6)
            o, c = (value.quantize(D("0.1")) for value in (step_open, step_close))
            bars.append(research.Candle(open_ms, o, max(o, c) + D("5"), min(o, c) - D("5"), c))
        previous = close
    return tuple(bars)


def config(fee="0", slippage="0"):
    return research.BacktestConfig(CONTRACT, H4, D("10000"), D(fee), D(slippage), ())


class Account:
    def __init__(self, equity="10000", position="0"):
        self.equity, self.position = D(equity), D(position)


def feed(strategy, bars):
    """Run update_indicators over bars; return the bars that closed a day."""
    closed = []
    for bar in bars:
        strategy.update_indicators(bar)
        if strategy.decide:
            closed.append(bar)
    return closed


class DaysTest(unittest.TestCase):
    def test_partial_first_day_is_dropped_and_days_close_at_midnight(self):
        bars = bars_from_daily(["100", "110", "105"], first_hour=4)
        days = daily._Days(10)
        closing = [bar for bar in bars if days.push(bar)]
        self.assertEqual([bar.open_time_ms + H4 for bar in closing], [START + 2 * DAY, START + 3 * DAY])
        first = days.days[0]
        self.assertEqual(first[0], START + DAY)
        self.assertEqual(first[3], D("110.0"))
        self.assertEqual(first[1], max(bar.high for bar in bars if START + DAY <= bar.open_time_ms < START + 2 * DAY))


class DonchianEnsembleTest(unittest.TestCase):
    def test_breakout_activates_every_submodel_and_a_drop_below_the_stops_exits(self):
        strategy = daily.DonchianEnsemble(0, D("1000"), CONTRACT)
        feed(strategy, bars_from_daily(["1000"] * 362))
        self.assertTrue(strategy.ready)
        self.assertFalse(any(strategy.active.values()))
        feed(strategy, bars_from_daily(["1100"], start=START + 362 * DAY))
        self.assertTrue(all(strategy.active.values()))
        # Stop = midpoint of the N-day closes including today: (1100 + 1000) / 2 for every N.
        self.assertEqual(set(strategy.stops.values()), {D("1050")})
        target = strategy.on_bar(bars_from_daily(["1100"], start=START + 362 * DAY)[-1], Account())
        # Unscaled, full weight: 10000 / (1100 x 0.01) = 909.09... -> 909.09 contracts (lot 0.01).
        self.assertEqual(target, D("909.09"))
        feed(strategy, bars_from_daily(["1040"], start=START + 363 * DAY))
        self.assertFalse(any(strategy.active.values()))

    def test_vol_target_uses_ninety_day_volatility_capped_at_two(self):
        strategy = daily.DonchianEnsemble(1, D("1000"), CONTRACT)
        feed(strategy, bars_from_daily(["1000"] * 362 + ["1100"]))
        returns = [D(0)] * 89 + [D("0.1")]
        mean = sum(returns) / D(90)
        variance = sum((r - mean) ** 2 for r in returns) / D(89)
        expected = D("0.25") / (variance * D(365)).sqrt()
        self.assertEqual(strategy.leverage(), expected)  # about 1.24
        flat = daily.DonchianEnsemble(1, D("5"), CONTRACT)
        feed(flat, bars_from_daily(["1000"] * 363))
        self.assertEqual(flat.leverage(), D(2))  # zero volatility -> the 2x cap
        flat.active = {n: True for n in flat.LOOKBACKS}
        self.assertEqual(flat.on_bar(bars_from_daily(["1000"])[-1], Account()), D(5))  # quantity caps contracts


class MomentumTest(unittest.TestCase):
    def test_score_follows_the_three_horizons(self):
        rising = [str(1000 + day) for day in range(400)]
        strategy = daily.TimeSeriesMomentum(0, D("1000"), CONTRACT)
        last = feed(strategy, bars_from_daily(rising))[-1]
        self.assertTrue(strategy.ready)
        self.assertGreater(strategy.on_bar(last, Account()), 0)
        # Rose for a year, then eased 1 a day for 40 days: 365 up, 91 up, 30 down -> score 1/3.
        mixed = [str(1000 + day) for day in range(370)] + [str(1369 - day) for day in range(1, 41)]
        strategy = daily.TimeSeriesMomentum(0, D("1000"), CONTRACT)
        last = feed(strategy, bars_from_daily(mixed))[-1]
        price = last.close
        expected = (D("10000") / D(3) / (price * D("0.01")) / D("0.01")).to_integral_value(rounding="ROUND_DOWN") * D("0.01")
        self.assertEqual(strategy.on_bar(last, Account()), expected)


class DCMTest(unittest.TestCase):
    def test_levels_match_the_indicator_formula(self):
        dh, dc, dl = daily.dcm_levels(D("110"), D("90"), D("100"))
        typical = (D(9) * 110 + D(9) * 90 + D(10) * 100) / D(28)
        self.assertEqual(dc, D("100"))
        self.assertEqual(dh, typical + D(20) * D("0.8065"))
        self.assertEqual(dl, typical - D(20) * D("0.8065"))

    def test_arrow_logic_and_score_filter(self):
        calm = ["1000"] * 30
        strategy = daily.DCMDaily(0, D("10"))
        feed(strategy, bars_from_daily(calm))
        jump = bars_from_daily(["1200"], start=START + 30 * DAY)
        feed(strategy, jump)
        self.assertEqual(strategy.on_bar(jump[-1], Account()), D("10"))
        drop = bars_from_daily(["900"], start=START + 31 * DAY)
        feed(strategy, drop)
        self.assertEqual(strategy.on_bar(drop[-1], Account(position="10")), D("-10"))
        # Score after the drop: 50 + MA20 slope -5 (1005 vs 1010) + close <= DL -10 = 35.
        gated = daily.DCMDaily(1, D("10"))
        feed(gated, bars_from_daily(calm + ["1200"]))
        drop_bars = bars_from_daily(["900"], start=START + 31 * DAY)
        feed(gated, drop_bars)
        days = gated.days.days
        score = gated.score(days[-1][3], daily.dcm_levels(*days[-2][1:4]), daily.dcm_levels(*days[-3][1:4]))
        self.assertEqual(score, 35)
        self.assertEqual(gated.on_bar(drop_bars[-1], Account(position="10")), D("-10"))

    def test_score_gate_blocks_entries_and_only_closes_the_opposite_side(self):
        class Fixed(daily.DCMDaily):
            value = 50

            def score(self, close, today, yesterday):
                return self.value

        gated = Fixed(1, D("10"))
        feed(gated, bars_from_daily(["1000"] * 30))
        jump = bars_from_daily(["1200"], start=START + 30 * DAY)
        feed(gated, jump)
        self.assertEqual(gated.on_bar(jump[-1], Account(position="-10")), D(0))  # bull, score 50 < 60
        self.assertIsNone(gated.on_bar(jump[-1], Account(position="0")))
        gated.value = 60
        self.assertEqual(gated.on_bar(jump[-1], Account(position="0")), D("10"))

    def test_ma_slope_buckets(self):
        self.assertEqual([daily.ma_slope_score(D(v)) for v in ("3", "1", "0.1", "0", "-0.1", "-1", "-3")],
                         [15, 10, 5, 0, -5, -10, -15])


class NoLookaheadTest(unittest.TestCase):
    def test_trades_on_a_prefix_never_change_when_later_bars_are_added(self):
        closes = [str(1000 + (day * 37) % 211 - (day // 50) * 13) for day in range(420)]
        full = bars_from_daily(closes)
        factories = {
            "donchian": lambda: daily.DonchianEnsemble(1, D("1000"), CONTRACT),
            "tsmom": lambda: daily.TimeSeriesMomentum(1, D("1000"), CONTRACT),
            "dcm": lambda: daily.DCMDaily(1, D("10")),
        }
        for name, factory in factories.items():
            with self.subTest(name):
                warmup = 367 * 6
                short = research.backtest(strategy=factory, candles=full[:2400], config=config(), warmup_bars=warmup)
                long = research.backtest(strategy=factory, candles=full, config=config(), warmup_bars=warmup)
                prefix = [t for t in long.trades if t.time_ms < full[2400].open_time_ms]
                self.assertEqual(list(short.trades), prefix)

    def test_decisions_only_on_the_bar_that_closes_a_day(self):
        closes = [str(1000 + (day * 37) % 211) for day in range(420)]
        result = research.backtest(strategy=lambda: daily.DCMDaily(0, D("10")), candles=bars_from_daily(closes),
                                   config=config(), warmup_bars=367 * 6)
        self.assertTrue(result.trades)
        self.assertTrue(all(trade.decision_time_ms % DAY == 0 for trade in result.trades))
        self.assertTrue(all(trade.time_ms % DAY == 0 for trade in result.trades))


class RobustnessTest(unittest.TestCase):
    def setUp(self):
        closes = [str(1000 + (day * 37) % 211 + day) for day in range(800)]
        self.bars = bars_from_daily(closes)
        self.result = research.backtest(strategy=lambda: daily.DCMDaily(0, D("10")), candles=self.bars,
                                        config=config("0.0005", "2"), warmup_bars=367 * 6)

    def test_yearly_rows_add_up_to_the_total(self):
        rows = robust.yearly(self.result, self.bars, D("10"))
        self.assertEqual([row["year"] for row in rows], [2023, 2024])
        self.assertEqual(sum((row["net_pnl"] for row in rows), D(0)), self.result.performance.net_pnl)

    def test_delay_moves_every_fill_one_bar_later(self):
        plain = self.result
        delayed = research.backtest(strategy=lambda: robust.Delayed(daily.DCMDaily(0, D("10"))), candles=self.bars,
                                    config=config("0.0005", "2"), warmup_bars=367 * 6)
        shifted = [(t.time_ms + H4, t.position_after) for t in plain.trades if t.time_ms + H4 < self.bars[-1].open_time_ms]
        self.assertEqual([(t.time_ms, t.position_after) for t in delayed.trades][:len(shifted)], shifted)

    def test_daily_returns_and_bootstrap(self):
        returns = robust.daily_returns(self.result)
        self.assertEqual(len(returns), (self.result.evaluation_end_ms - self.result.evaluation_start_ms) // DAY)
        first = robust.block_bootstrap(returns)
        self.assertEqual(first, robust.block_bootstrap(returns))  # fixed seed
        self.assertLessEqual(float(first["ci95_low"]), float(first["mean_daily_return"]))
        self.assertLessEqual(float(first["mean_daily_return"]), float(first["ci95_high"]))
        self.assertIsNone(robust.block_bootstrap(returns[:30]))


class CatalogTest(DatasetFixture):
    def test_registration_warmup_and_sizing_rules(self):
        for strategy_id in ("donchian-ensemble", "tsmom-multi", "dcm-daily"):
            self.assertEqual(STRATEGIES[strategy_id].min_warmup_days, DAILY_WARMUP_DAYS)
            with self.assertRaises(ValueError):
                worker_resolve(strategy_id, STRATEGIES[strategy_id].version)  # research only
        with self.assertRaisesRegex(ValueError, "contract_required_for_vol_target"):
            registered_factory(provenance(strategy_id="tsmom-multi"), "tsmom-multi", D("10"))
        target = write_fixture(self.root, count=192)
        request = request_for(target.name, strategy_id="dcm-daily",
                              parameters={"score_filter": 0, "quantity": "10"}, warmup_bars=100)
        with self.assertRaisesRegex(ValueError, "at least 35232 bars"):
            validate_request(request)

    def test_buy_hold_quantity_is_one_x_notional_for_equity_sized_strategies(self):
        closes = [str(20000 + day) for day in range(400)]
        bars = bars_from_daily(closes)
        result = research.backtest(strategy=lambda: daily.DCMDaily(0, D("10")), candles=bars,
                                   config=config(), warmup_bars=367 * 6)
        first = bars[367 * 6]
        expected = (D("10000") / (first.open * D("0.01")) / D("0.01")).to_integral_value(rounding="ROUND_DOWN") * D("0.01")
        self.assertEqual(buy_hold_quantity("tsmom-multi", D("1000"), result, bars), expected)
        self.assertEqual(buy_hold_quantity("dcm-daily", D("10"), result, bars), D("10"))


if __name__ == "__main__":
    unittest.main()
