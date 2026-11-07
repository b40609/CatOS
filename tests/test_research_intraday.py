"""Package F intraday DCM strategies on hand-built 1H bars (offline)."""

from decimal import Decimal
import unittest

from catos import research, research_intraday as intraday
from catos.research_catalog import provenance, execute_request
from catos.strategy_registry import resolve as worker_resolve
from test_research_datasets import DatasetFixture, request_for, write_fixture

D = Decimal
H1 = 3_600_000
DAY = 86_400_000
START = 1_640_995_200_000  # 2022-01-01 00:00 UTC
CONTRACT = research.ContractSpec("BTC-USDT-SWAP", D("0.01"), D("0.1"), D("0.01"), D("0.01"))


def bar(index, o, h, low, c):
    return research.Candle(START + index * H1, D(o), D(h), D(low), D(c))


def flat_day(day, price="1000", spread="10"):
    """24 hourly bars: open = close = price, range +/- spread."""
    p, s = D(price), D(spread)
    return [bar(day * 24 + hour, p, p + s, p - s, p) for hour in range(24)]


class Account:
    def __init__(self, position="0"):
        self.position, self.equity = D(position), D("10000")


def levels_of(price="1000", spread="10"):
    p, s = D(price), D(spread)
    return intraday.dcm_levels(p + s, p - s, p)


def drive(strategy, bars, position="0"):
    """Feed bars; return [(index, target)] for non-None decisions at a fixed account position."""
    out = []
    for i, b in enumerate(bars):
        strategy.update_indicators(b)
        target = strategy.on_bar(b, Account(position))
        if target is not None:
            out.append((i, target))
    return out


class SessionTest(unittest.TestCase):
    def test_levels_need_a_complete_previous_day(self):
        session = intraday._Session()
        for b in flat_day(0)[5:]:  # day 0 starts mid-day: never complete
            session.push(b)
            self.assertIsNone(session.levels)
        for b in flat_day(1):
            session.push(b)
            self.assertIsNone(session.levels)  # day 0 was partial
        session.push(flat_day(2)[0])
        self.assertEqual(session.levels, levels_of())


class FadeTest(unittest.TestCase):
    def test_false_breakdown_long_with_stop_and_opposite_target(self):
        dh, dc, dl = levels_of()
        bars = flat_day(0) + flat_day(1)[:3]
        # Day 1, hour 3: wick below DL, close back above it (same bar).
        bars.append(bar(24 + 3, "1000", "1001", str(dl - 5), str(dl + 1)))
        strategy = intraday.DCMFade(0, D("10"))
        decisions = drive(strategy, bars)
        self.assertEqual(decisions, [(len(bars) - 1, D("10"))])
        self.assertEqual(strategy.trade, (1, dl - 5, dh))
        # Holding: a close above DL but below DH keeps the trade; a close at DH exits.
        hold = bar(24 + 4, str(dl + 1), str(dc), str(dl), str(dc))
        strategy.update_indicators(hold)
        self.assertIsNone(strategy.on_bar(hold, Account("10")))
        target = bar(24 + 5, str(dc), str(dh + 1), str(dc), str(dh))
        strategy.update_indicators(target)
        self.assertEqual(strategy.on_bar(target, Account("10")), D(0))

    def test_stop_is_the_breach_extreme_and_one_entry_per_side_per_day(self):
        dh, dc, dl = levels_of()
        strategy = intraday.DCMFade(0, D("10"))
        bars = flat_day(0) + [bar(24, "1000", "1000", str(dl - 3), str(dl - 1)),   # breach, close below
                               bar(25, str(dl - 1), "1000", str(dl - 8), str(dl + 2))]  # reclaim
        self.assertEqual(drive(strategy, bars)[-1], (25, D("10")))
        self.assertEqual(strategy.trade[1], dl - 8)  # lowest low from breach to entry
        stop = bar(26, str(dl + 2), str(dl + 2), str(dl - 9), str(dl - D("8.5")))
        strategy.update_indicators(stop)
        self.assertEqual(strategy.on_bar(stop, Account("10")), D(0))
        again = bar(27, str(dl - D("8.5")), str(dl + 3), str(dl - 9), str(dl + 3))
        strategy.update_indicators(again)
        self.assertIsNone(strategy.on_bar(again, Account("0")))  # long already used today

    def test_false_breakout_short_and_daily_dc_exit(self):
        dh, dc, dl = levels_of()
        strategy = intraday.DCMFade(1, D("10"))
        bars = flat_day(0) + [bar(24, "1000", str(dh + 4), "999", str(dh - 1))]
        self.assertEqual(drive(strategy, bars)[-1], (24, D("-10")))
        rest = [bar(25 + i, str(dh - 1), str(dh - 1), str(dc + 1), str(dc + 1)) for i in range(22)]
        for b in rest:
            strategy.update_indicators(b)
            self.assertIsNone(strategy.on_bar(b, Account("-10")))
        day_end = bar(47, str(dc + 1), str(dc + 2), str(dc), str(dc + 1))  # daily close above DC
        strategy.update_indicators(day_end)
        self.assertEqual(strategy.on_bar(day_end, Account("-10")), D(0))

    def test_no_entry_when_both_sides_fire_on_one_bar(self):
        dh, dc, dl = levels_of()
        strategy = intraday.DCMFade(0, D("10"))
        bars = flat_day(0) + [bar(24, "1000", str(dh + 5), str(dl - 5), "1000")]
        self.assertEqual(drive(strategy, bars), [])


class PullbackTest(unittest.TestCase):
    def test_launch_then_reclaim_of_the_frozen_dc(self):
        dh, dc, dl = levels_of()
        launch_close = (dh + 20).quantize(D("0.1"))
        day1 = flat_day(1)[:23] + [bar(47, "1000", str(launch_close + 1), "999", str(launch_close))]
        strategy = intraday.DCMPullback(3, D("10"))
        drive(strategy, flat_day(0) + day1)
        frozen = intraday.dcm_levels(max(b.high for b in day1), min(b.low for b in day1), launch_close)
        self.assertEqual(strategy.launch[:3], frozen)
        touch = bar(48, str(launch_close), str(launch_close), str(frozen[1] - 1), str(frozen[1] + 1))
        strategy.update_indicators(touch)
        self.assertEqual(strategy.on_bar(touch, Account("0")), D("10"))
        self.assertEqual(strategy.stop, frozen[2])
        crash = bar(49, str(frozen[1]), str(frozen[1]), str(frozen[2] - 5), str(frozen[2] - 1))
        strategy.update_indicators(crash)
        self.assertEqual(strategy.on_bar(crash, Account("10")), D(0))

    def test_the_window_expires(self):
        dh, dc, dl = levels_of()
        day1 = flat_day(1)[:23] + [bar(47, "1000", str(dh + 30), "999", str(dh + 20))]
        strategy = intraday.DCMPullback(1, D("10"))
        drive(strategy, flat_day(0) + day1 + flat_day(2, price=str(dh + 20)))
        self.assertIsNotNone(strategy.launch)  # still within one day after the launch
        late = bar(72, "900", "900", "800", "900")
        strategy.update_indicators(late)
        self.assertIsNone(strategy.launch)


class NoLookaheadTest(unittest.TestCase):
    def test_prefix_trades_do_not_change_when_later_bars_are_added(self):
        bars, price, seed = [], D("1000"), 11
        for i in range(24 * 40):
            seed = (seed * 1103515245 + 12345) % 2**31
            close = price + D((seed % 61) - 30)
            high, low = max(price, close) + D((seed >> 8) % 15), min(price, close) - D((seed >> 12) % 15)
            bars.append(research.Candle(START + i * H1, price, high, low, close))
            price = close
        config = research.BacktestConfig(CONTRACT, H1, D("10000"), D("0.0005"), D("2"), ())
        for name, factory in (("fade0", lambda: intraday.DCMFade(0, D("10"))),
                              ("fade1", lambda: intraday.DCMFade(1, D("10"))),
                              ("pullback", lambda: intraday.DCMPullback(3, D("10")))):
            with self.subTest(name):
                full = research.backtest(strategy=factory, candles=bars, config=config, warmup_bars=72)
                short = research.backtest(strategy=factory, candles=bars[:600], config=config, warmup_bars=72)
                self.assertEqual(list(short.trades), [t for t in full.trades if t.time_ms < bars[600].open_time_ms])
                if name != "pullback":
                    self.assertTrue(full.trades)


class CatalogTest(DatasetFixture):
    def test_research_only_and_backtest_payload_has_trade_stats(self):
        for strategy_id in ("dcm-fade", "dcm-pullback"):
            with self.assertRaises(ValueError):
                worker_resolve(strategy_id, f"{strategy_id}-preregistered-v1")
        target = write_fixture(self.root, count=96 * 6)
        payload, _ = execute_request(request_for(target.name, strategy_id="dcm-fade",
                                                 parameters={"exit_mode": 0, "quantity": "10"}, warmup_bars=288),
                                     provenance(target.name, "dcm-fade"))
        stats = payload["trade_stats"]
        self.assertEqual(stats["wins"] + stats["losses"] + stats["breakeven"], stats["closed_trips"])


if __name__ == "__main__":
    unittest.main()


class DelayedStateMachineTest(unittest.TestCase):
    """2026-11-07 fix: a delayed position-reading strategy must run the same logic, one bar later."""

    def test_delay_shifts_a_position_reading_strategy_without_changing_its_decisions(self):
        from catos import research_robustness as robust
        bars, price, seed = [], D("1000"), 5
        for i in range(24 * 30):
            seed = (seed * 1103515245 + 12345) % 2**31
            close = price + D((seed % 61) - 30)
            high, low = max(price, close) + D((seed >> 8) % 15), min(price, close) - D((seed >> 12) % 15)
            bars.append(research.Candle(START + i * H1, price, high, low, close))
            price = close
        config = research.BacktestConfig(CONTRACT, H1, D("10000"), D("0"), D("0"), ())
        for mode in (0, 1):
            with self.subTest(mode=mode):
                plain = research.backtest(strategy=lambda: intraday.DCMFade(mode, D("10")), candles=bars,
                                          config=config, warmup_bars=72)
                delayed = research.backtest(strategy=lambda: robust.Delayed(intraday.DCMFade(mode, D("10"))),
                                            candles=bars, config=config, warmup_bars=72)
                self.assertTrue(plain.trades)
                expected = [(t.decision_time_ms + H1, t.position_after) for t in plain.trades
                            if t.time_ms + H1 < bars[-1].open_time_ms + H1]
                self.assertEqual([(t.decision_time_ms, t.position_after) for t in delayed.trades], expected)
