"""Round trips and win-rate statistics (offline)."""

from decimal import Decimal, localcontext
import unittest

from catos import research, research_trades as trades
from test_research_costs import CONTRACT, Flip, candles, config, real_funding

D = Decimal


class Script(research.Strategy):
    """Return a fixed target on chosen evaluation bars (1-based count of bars seen)."""

    def __init__(self, plan):
        self.plan, self.count = plan, 0

    def update_indicators(self, bar):
        self.count += 1

    def on_bar(self, bar, account):
        return self.plan.get(self.count)


def run(plan, bars, **cfg):
    return research.backtest(strategy=lambda: Script(plan), candles=bars, config=config(**cfg), warmup_bars=0)


class RoundTripTest(unittest.TestCase):
    def test_reversals_split_fees_and_trips_reconcile_with_net(self):
        bars = candles()
        result = research.backtest(strategy=Flip, candles=bars, config=config(funding=real_funding(bars)),
                                   warmup_bars=3)
        closed, open_trip = trades.round_trips(result)
        stats = trades.trade_stats(result)  # raises if the trips do not add up to net PnL
        self.assertEqual(stats["closed_trips"], len(closed))
        self.assertEqual(stats["wins"] + stats["losses"] + stats["breakeven"], len(closed))
        self.assertEqual(sum((t.fees for t in closed), D(0)) + (open_trip.fees if open_trip else 0),
                         result.performance.fees)
        self.assertEqual(sum((t.funding_paid for t in closed), D(0)) + (open_trip.funding_paid if open_trip else 0),
                         result.performance.funding_paid)
        self.assertTrue(any(t.side == -1 for t in closed) and any(t.side == 1 for t in closed))

    def test_hand_checked_long_win_and_short_loss(self):
        bars = candles(40)
        # Long 2 decided on bar 2 (filled at bar 3 open), flat on bar 6; short 2 on bar 10, flat on bar 14.
        result = run({2: D(2), 6: D(0), 10: D(-2), 14: D(0)}, bars, fee="0", slippage="0")
        closed, open_trip = trades.round_trips(result)
        self.assertIsNone(open_trip)
        self.assertEqual([t.side for t in closed], [1, -1])
        long_pnl = D(2) * D("0.01") * (bars[6].open - bars[2].open)
        short_pnl = D(2) * D("0.01") * (bars[10].open - bars[14].open)
        self.assertEqual([t.net_pnl for t in closed], [long_pnl, short_pnl])
        stats = trades.trade_stats(result)
        expected_wins = sum(p > 0 for p in (long_pnl, short_pnl))
        self.assertEqual(stats["wins"], expected_wins)
        self.assertEqual(stats["expectancy"], (long_pnl + short_pnl) / 2)
        self.assertEqual(stats["average_hold_hours"], D(4) * D(15) / D(60))  # four 15m bars each

    def test_open_trip_is_reported_apart_and_scaling_stays_in_one_trip(self):
        bars = candles(40)
        result = run({2: D(1), 4: D(3), 8: D(2)}, bars)  # scale in, scale out, never flat
        closed, open_trip = trades.round_trips(result)
        self.assertEqual(closed, [])
        self.assertEqual(open_trip.fills, 3)
        stats = trades.trade_stats(result)
        self.assertIsNone(stats["win_rate"])
        self.assertEqual(stats["open_trip"]["net_pnl_with_unrealized"], result.performance.net_pnl)

    def test_streaks_payoff_and_profit_factor(self):
        bars = candles(120)
        plan = {}
        for start in range(2, 100, 8):
            plan[start], plan[start + 4] = D(1), D(0)
        result = run(plan, bars)
        stats = trades.trade_stats(result)
        pnls = [t.net_pnl for t in trades.round_trips(result)[0]]
        wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p < 0]
        with localcontext(research._CONTEXT):  # the statistics use the engine's 50-digit context
            self.assertEqual(stats["win_rate"], D(len(wins)) / D(len(pnls)))
            if wins and losses:
                self.assertEqual(stats["profit_factor"], sum(wins) / -sum(losses))
                self.assertEqual(stats["payoff_ratio"], (sum(wins) / len(wins)) / -(sum(losses) / len(losses)))
        streak = longest = 0
        for p in pnls:
            streak = streak + 1 if p < 0 else 0
            longest = max(longest, streak)
        self.assertEqual(stats["max_consecutive_losses"], longest)


if __name__ == "__main__":
    unittest.main()


class ReconciliationTest(unittest.TestCase):
    """2026-11-07: equity-sized reversals and scale-ins reconcile within the reported residual."""

    def test_odd_sizes_reconcile_within_tolerance(self):
        bars = candles(160)
        plan = {3: D("3.17"), 9: D("-7.89"), 15: D("5.03"), 21: D("7.77"), 27: D("-1.11"), 33: D("2.29"),
                40: D("0"), 46: D("-4.41"), 52: D("3.33")}
        result = run(plan, bars)
        stats = trades.trade_stats(result)
        self.assertLessEqual(abs(stats["rounding_residual"]), trades.TOLERANCE)
        closed, open_trip = trades.round_trips(result)
        self.assertGreaterEqual(len(closed), 5)
