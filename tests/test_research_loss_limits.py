"""Daily-loss trigger diagnostic over a finished backtest (docs/research-loss-limits.md).

Contract of 1 base unit per contract, 0.1 tick, no fee or slippage, 4H bars whose
first bar opens at Taipei 00:00 (UTC 16:00), so six bars make one Taipei day.
"""

from decimal import Decimal as D
import unittest

from catos import research, research_loss_limits as limits, risk

TF = 14_400_000
DAY = 86_400_000
TAIPEI_DAY = 20_726  # 2026-09-30 in Taipei
T0 = TAIPEI_DAY * DAY - 28_800_000  # Taipei 00:00 = UTC 16:00 the day before
CONTRACT = research.ContractSpec("TEST-USDT-SWAP", D("1"), D("0.1"), D("1"), D("1"))


def flat(index, price="100"):
    return research.Candle(T0 + index * TF, D(price), D(price), D(price), D(price))


def candle(index, o, h, low, c):
    return research.Candle(T0 + index * TF, D(o), D(h), D(low), D(c))


class Script(research.Strategy):
    def __init__(self, targets):
        self.targets, self.index = targets, -1

    def update_indicators(self, bar):
        self.index += 1

    def on_bar(self, bar, account):
        value = self.targets.get(self.index)
        return None if value is None else D(value)


def run(bars, targets, balance="1000", margin=None):
    config = research.BacktestConfig(CONTRACT, TF, D(balance), D("0"), D("0"), (), margin)
    result = research.backtest(strategy=lambda: Script(targets), candles=bars, config=config)
    return result, limits.summary(result, bars)


def counts(value, key):
    item = next(entry for entry in value["thresholds"] if entry["key"] == key)
    return item["soft"]["days"], item["hard"]["days"]


class LossLimitTriggerTest(unittest.TestCase):
    def test_current_limits_come_from_risk_defaults(self):
        _, value = run([flat(i) for i in range(6)], {})
        current = next(entry for entry in value["thresholds"] if entry["key"] == "current")
        self.assertEqual(current["soft"]["limit_pct"], risk.Limits().soft_loss * 100)
        self.assertEqual(current["hard"]["limit_pct"], risk.Limits().hard_loss * 100)
        self.assertTrue(current["applied_to_risk"])
        self.assertEqual((risk.Limits().soft_loss, risk.Limits().hard_loss),
                         (D("0.05"), D("0.10")))
        legacy = next(entry for entry in value["thresholds"] if entry["key"] == "legacy")
        self.assertFalse(legacy["applied_to_risk"])
        self.assertIn("舊預設", legacy["label"])
        self.assertEqual(legacy["soft"]["limit_pct"], risk.LEGACY_LIMITS.soft_loss * 100)
        self.assertEqual(legacy["hard"]["limit_pct"], risk.LEGACY_LIMITS.hard_loss * 100)

    def test_exactly_at_limit_triggers(self):
        # Long 5 from bar 1's open at 100; bar 1 low 80: 1000 + 5 x (80 - 100) = 900, loss 10.00%.
        bars = [flat(0), candle(1, "100", "100", "80", "100"), *(flat(i) for i in range(2, 6))]
        _, value = run(bars, {0: "5"})
        self.assertEqual(counts(value, "legacy"), (1, 0))  # legacy: soft 10% hit exactly, hard 20% not
        self.assertEqual(counts(value, "current"), (1, 1))  # current: 5% and 10% (exactly)
        self.assertEqual(value["max_daily_loss"]["loss_pct"], D("10.0000"))
        self.assertEqual(value["max_daily_loss"]["day"], "2026-09-30")
        self.assertEqual(value["max_daily_loss"]["low_bar_open_ms"], T0 + TF)

    def test_just_below_limit_does_not_trigger(self):
        # low 80.1: 1000 - 5 x 19.9 = 900.5, loss 9.95%.
        bars = [flat(0), candle(1, "100", "100", "80.1", "100"), *(flat(i) for i in range(2, 6))]
        _, value = run(bars, {0: "5"})
        self.assertEqual(counts(value, "legacy"), (0, 0))
        self.assertEqual(counts(value, "current"), (1, 0))
        self.assertEqual(value["max_daily_loss"]["loss_pct"], D("9.9500"))

    def test_taipei_midnight_splits_days(self):
        # Bar 5 is Taipei 20:00-24:00 of day 1; bar 6 opens at Taipei 00:00 (UTC 16:00) of day 2.
        # Each dips 6% from a 1000 basis and recovers, so the current Soft 5% hits two Taipei days;
        # on UTC days both bars would fall on one day.
        bars = [*(flat(i) for i in range(5)), candle(5, "100", "100", "88", "100"),
                candle(6, "100", "100", "88", "100"), *(flat(i) for i in range(7, 12))]
        self.assertNotEqual(risk.taipei_day(bars[5].open_time_ms), risk.taipei_day(bars[6].open_time_ms))
        self.assertEqual((bars[5].open_time_ms // DAY), (bars[6].open_time_ms // DAY))  # same UTC day
        _, value = run(bars, {0: "5"})
        current = next(entry for entry in value["thresholds"] if entry["key"] == "current")
        self.assertEqual([entry["day"] for entry in current["soft"]["listed"]], ["2026-09-30", "2026-10-01"])
        self.assertEqual(current["soft"]["first_day"], "2026-09-30")
        self.assertEqual(value["days_evaluated"], 2)
        self.assertEqual(value["straddling_bars"], 0)

    def test_new_day_basis_is_equity_at_the_first_open(self):
        # Long 5 at 100; day 1 ends at 90 (equity 950, loss 5% exactly). Day 2 opens at 90:
        # basis 950; low 81 -> 905, loss 45/950 = 4.7368%, below the current Soft 5%.
        bars = [flat(0), candle(1, "100", "100", "90", "90"), *(flat(i, "90") for i in range(2, 6)),
                candle(6, "90", "90", "81", "90")]
        _, value = run(bars, {0: "5"})
        self.assertEqual(counts(value, "current"), (1, 0))
        self.assertEqual(value["max_daily_loss"]["day"], "2026-09-30")  # day 1 lost 5.0000%
        self.assertEqual(value["max_daily_loss"]["loss_pct"], D("5.0000"))
        day_two = limits.daily_lows(run(bars, {0: "5"})[0], bars)[0][1]
        self.assertEqual(day_two[1], D("950"))
        self.assertEqual(day_two[2], D("905"))

    def test_short_uses_the_high(self):
        # Short 5 at 100; bar 1 high 120, low 60: the high gives 1000 - 5 x 20 = 900 (10%).
        bars = [flat(0), candle(1, "100", "120", "60", "100"), *(flat(i) for i in range(2, 6))]
        _, value = run(bars, {0: "-5"})
        self.assertEqual(value["max_daily_loss"]["loss_pct"], D("10.0000"))
        self.assertEqual(counts(value, "legacy"), (1, 0))

    def test_liquidation_day_counts_and_stops(self):
        # 10x long with the margin model; bar 1 low 80 liquidates. Later days are not counted.
        tiers = (research.MarginTier(1, D("1000"), D("0.004"), D("0.01")),)
        model = research.MarginModel(tiers, "a" * 64)
        bars = [flat(0), candle(1, "100", "100", "80", "100"), *(flat(i) for i in range(2, 18))]
        result, value = run(bars, {0: "10"}, balance="100", margin=model)
        self.assertIsNotNone(result.liquidation)
        self.assertEqual(value["days_evaluated"], 1)
        self.assertEqual(value["stopped"], {"day": "2026-09-30", "reason": "liquidation"})
        self.assertEqual(counts(value, "legacy"), (1, 1))
        self.assertEqual(counts(value, "current"), (1, 1))
        self.assertEqual(value["max_daily_loss"]["loss_pct"], D("100.0000"))

    def test_equity_non_positive_without_margin_stops(self):
        # No margin model: 10 long on 100 balance, low 80 -> equity -100; the day counts and ends the count.
        bars = [flat(0), candle(1, "100", "100", "80", "100"), *(flat(i) for i in range(2, 18))]
        _, value = run(bars, {0: "10"}, balance="100")
        self.assertEqual(value["stopped"]["reason"], "equity_non_positive")
        self.assertEqual(value["days_evaluated"], 1)
        self.assertEqual(counts(value, "legacy"), (1, 1))

    def test_days_without_position(self):
        bars = [candle(i, "100", "150", "50", "100") for i in range(18)]
        _, value = run(bars, {})
        self.assertEqual(value["days_evaluated"], 3)
        self.assertEqual(counts(value, "legacy"), (0, 0))
        self.assertEqual(counts(value, "current"), (0, 0))
        self.assertEqual(value["max_daily_loss"]["loss_pct"], D("0.0000"))
        self.assertIsNone(value["stopped"])
        self.assertEqual(value["years"], D("0.01"))

    def test_per_year_and_listing_cap(self):
        # A 6% dip every day for 60 days: current Soft 5% hits every day, list capped at MAX_LISTED_DAYS.
        bars = [flat(0)]
        for i in range(1, 60 * 6):
            bars.append(candle(i, "100", "100", "88", "100") if i % 6 == 1 else flat(i))
        _, value = run(bars, {0: "5"})
        soft = next(entry for entry in value["thresholds"] if entry["key"] == "current")["soft"]
        self.assertEqual(soft["days"], 60)
        self.assertEqual(len(soft["listed"]), limits.MAX_LISTED_DAYS)
        self.assertTrue(soft["truncated"])
        self.assertEqual(soft["per_year"], D("365.00"))

    def test_close_funding_is_not_in_the_adverse_balance(self):
        # Funding of 50 debited at bar 1's close: the adverse point (low 90 -> 950) uses the balance
        # before it, the close (100 -> 1000 - 50 = 950) after it; the day low is 950, not 900.
        bars = [flat(0), candle(1, "100", "100", "90", "100"), *(flat(i) for i in range(2, 6))]
        event = research.FundingEvent(T0 + 2 * TF, D("0.1"), D("100"))
        config = research.BacktestConfig(CONTRACT, TF, D("1000"), D("0"), D("0"), (event,))
        result = research.backtest(strategy=lambda: Script({0: "5"}), candles=bars, config=config)
        self.assertEqual(result.funding[0].amount_paid, D("50.0"))
        (day,), _ = limits.daily_lows(result, bars)
        self.assertEqual(day[2], D("950"))

    def test_report_rows_render(self):
        bars = [flat(0), candle(1, "100", "100", "80", "100"), *(flat(i) for i in range(2, 6))]
        _, value = run(bars, {0: "5"})
        text = "".join(f"{label}{content}" for label, content in limits.report_rows(value))
        self.assertIn("最大單日虧損", text)
        self.assertIn("2026-09-30", text)
        self.assertIn("單幣曝險上限", text)


if __name__ == "__main__":
    unittest.main()
