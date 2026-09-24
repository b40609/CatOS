from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from catos import market_signals as signals
from catos.market_intel import MarketIntelStore


D = Decimal


def base_inputs(**changes):
    values = dict(
        symbol="BTC-USDT-SWAP",
        observed_at_ms=1_000_000,
        return_1h_pct=D("1.5"),
        return_24h_pct=D("10"),
        volume_24h_usd=D("5000000"),
        market_cap_usd=D("299999999"),
        oi_delta_5m_pct=D("1.5"),
        oi_delta_1h_pct=D("3"),
        oi_delta_4h_pct=D("10"),
        volatility_percentile_15m=D("34.9"),
        funding_previous=D("0.0001"),
        funding_current=D("-0.0001"),
        trend_active=True,
        whale_exit_event=False,
        extreme_long_event=False,
        capital_flow_fomo_event=False,
        team_transfer_usd=D("500000"),
        team_transfer_non_exchange_to_exchange=True,
        team_distribution_cooldown_clear=True,
        volatility_high_1h=True,
        trend_strength=D("25"),
        trend_strength_falling=True,
        directional_force_confirmed=True,
        prior_bullish_support=False,
        distribution_behavior=False,
    )
    values.update(changes)
    return signals.SignalInputs(**values)


class L2SignalTests(unittest.TestCase):
    def test_public_momentum_absolute_return_boundary_and_missing(self):
        # Guide s-signals: ordinary momentum is inclusive at 10% in either
        # direction. These fixtures verify the rule, not live Yaozi agreement.
        for value, expected in (
            ("-10.001", signals.HIT), ("-10", signals.HIT),
            ("-9.999", signals.MISS), ("0", signals.MISS),
            ("9.999", signals.MISS), ("10", signals.HIT),
            ("10.001", signals.HIT), (None, signals.MISSING_DATA),
        ):
            with self.subTest(value=value):
                inputs = signals.SignalInputs(
                    symbol="BTC-USDT-SWAP", observed_at_ms=1_000_000,
                    return_24h_pct=None if value is None else D(value),
                )
                self.assertEqual(signals.evaluate(inputs).signal("MOMENTUM").status,
                                 expected)

    def test_momentum_uses_24h_not_one_hour_or_fomo(self):
        inputs = signals.SignalInputs(
            symbol="BTC-USDT-SWAP", observed_at_ms=1_000_000,
            return_1h_pct=D("30"), return_24h_pct=D("9.999"),
            capital_flow_fomo_event=True,
        )
        self.assertEqual(signals.evaluate(inputs).signal("MOMENTUM").status,
                         signals.MISS)

    def test_negative_momentum_is_not_positive_only_pure_momentum(self):
        bundle = signals.evaluate(base_inputs(return_24h_pct=D("-10")))
        self.assertEqual(bundle.signal("MOMENTUM").status, signals.HIT)
        self.assertEqual(bundle.signal("PURE_MOMENTUM").status, signals.MISS)

    def test_known_l2_boundaries_hit_and_unknown_thresholds_stay_disabled(self):
        bundle = signals.evaluate(base_inputs(return_24h_pct=D("25")))
        self.assertEqual(bundle.signal("MOMENTUM").status, signals.HIT)
        self.assertEqual(bundle.signal("STRONG_MOMENTUM").status, signals.HIT)
        self.assertEqual(bundle.signal("FUNDING_NEGATIVE_FLIP").status, signals.HIT)
        self.assertEqual(bundle.signal("TEAM_DISTRIBUTION").status, signals.HIT)
        self.assertEqual(bundle.signal("PURE_MOMENTUM").status, signals.HIT)
        for kind in ("HIT", "AMBUSH", "ACCUMULATION", "HEAT", "OI_SURGE",
                     "EXTREME_LONG", "WHALE_ENTRY", "WHALE_EXIT", "COIL_BREAKOUT_LIGHT"):
            self.assertEqual(bundle.signal(kind).status, signals.DISABLED_UNKNOWN_THRESHOLD)

    def test_pure_momentum_uses_strict_market_cap_and_missing_is_not_miss(self):
        at_cap = signals.evaluate(base_inputs(market_cap_usd=D("300000000")))
        self.assertEqual(at_cap.signal("PURE_MOMENTUM").status, signals.MISS)
        missing = signals.evaluate(base_inputs(market_cap_usd=None))
        self.assertEqual(missing.signal("PURE_MOMENTUM").status, signals.MISSING_DATA)

    def test_funding_flip_requires_positive_to_negative_and_rising_oi(self):
        self.assertEqual(signals.evaluate(base_inputs()).signal("FUNDING_NEGATIVE_FLIP").status, signals.HIT)
        flat = signals.evaluate(base_inputs(oi_delta_1h_pct=D("0")))
        self.assertEqual(flat.signal("FUNDING_NEGATIVE_FLIP").status, signals.MISS)
        missing = signals.evaluate(base_inputs(funding_previous=None))
        self.assertEqual(missing.signal("FUNDING_NEGATIVE_FLIP").status, signals.MISSING_DATA)


class PatternTests(unittest.TestCase):
    def test_short_squeeze_boundary(self):
        bundle = signals.evaluate(base_inputs(return_24h_pct=D("5")))
        self.assertEqual(bundle.pattern("SHORT_SQUEEZE_CANDIDATE").status, signals.HIT)

    def test_coil_breakout_uses_strict_p50_and_inclusive_price_range(self):
        hit = signals.evaluate(base_inputs(return_1h_pct=D("2"), volatility_percentile_15m=D("49.999")))
        self.assertEqual(hit.pattern("COIL_BREAKOUT").status, signals.HIT)
        miss = signals.evaluate(base_inputs(volatility_percentile_15m=D("50")))
        self.assertEqual(miss.pattern("COIL_BREAKOUT").status, signals.MISS)

    def test_preheat_uses_5m_speed_greater_than_1h_average(self):
        hit = signals.evaluate(base_inputs(oi_delta_5m_pct=D("1"), oi_delta_1h_pct=D("2"),
                                          return_1h_pct=D("1.5"), return_24h_pct=D("10")))
        self.assertEqual(hit.pattern("PREHEAT").status, signals.HIT)
        no_acceleration = signals.evaluate(base_inputs(oi_delta_5m_pct=D("1"), oi_delta_1h_pct=D("12")))
        self.assertEqual(no_acceleration.pattern("PREHEAT").status, signals.MISS)

    def test_ambush_boundary_and_missing_volatility_are_distinct(self):
        hit = signals.evaluate(base_inputs(return_1h_pct=D("1.49"), return_24h_pct=D("3"),
                                          volatility_percentile_15m=D("34.999")))
        self.assertEqual(hit.pattern("AMBUSH").status, signals.HIT)
        missing = signals.evaluate(base_inputs(return_1h_pct=D("1"), return_24h_pct=D("1"),
                                              volatility_percentile_15m=None))
        self.assertEqual(missing.pattern("AMBUSH").status, signals.MISSING_DATA)

    def test_fomo_accepts_either_confirmed_branch(self):
        price_volume = signals.evaluate(base_inputs(return_24h_pct=D("15"), volume_24h_usd=D("1000000"),
                                                   capital_flow_fomo_event=False))
        self.assertEqual(price_volume.pattern("FOMO").status, signals.HIT)
        event = signals.evaluate(base_inputs(return_24h_pct=None, volume_24h_usd=None,
                                            capital_flow_fomo_event=True))
        self.assertEqual(event.pattern("FOMO").status, signals.HIT)
        unknown = signals.evaluate(base_inputs(return_24h_pct=D("1"), volume_24h_usd=D("1"),
                                              capital_flow_fomo_event=None))
        self.assertEqual(unknown.pattern("FOMO").status, signals.MISSING_DATA)

    def test_trend_reversal_uses_only_published_numeric_threshold_and_caller_confirmed_conditions(self):
        hit = signals.evaluate(base_inputs(return_24h_pct=D("0.01"), trend_strength=D("25")))
        self.assertEqual(hit.pattern("TREND_REVERSAL").status, signals.HIT)
        self.assertEqual(dict(hit.pattern("TREND_REVERSAL").thresholds)["trend_strength_gte"], D("25"))
        supported = signals.evaluate(base_inputs(prior_bullish_support=True))
        self.assertEqual(supported.pattern("TREND_REVERSAL").status, signals.MISS)
        flat_24h = signals.evaluate(base_inputs(return_24h_pct=D("0")))
        self.assertEqual(flat_24h.pattern("TREND_REVERSAL").status, signals.MISS)
        missing_force = signals.evaluate(base_inputs(directional_force_confirmed=None))
        self.assertEqual(missing_force.pattern("TREND_REVERSAL").status, signals.MISSING_DATA)

    def test_distribution_accepts_whale_exit_or_confirmed_distribution_behavior(self):
        whale = signals.evaluate(base_inputs(whale_exit_event=True, distribution_behavior=False))
        self.assertEqual(whale.pattern("DISTRIBUTION").status, signals.HIT)
        behavior = signals.evaluate(base_inputs(whale_exit_event=False, distribution_behavior=True))
        self.assertEqual(behavior.pattern("DISTRIBUTION").status, signals.HIT)
        miss = signals.evaluate(base_inputs(whale_exit_event=False, distribution_behavior=False))
        self.assertEqual(miss.pattern("DISTRIBUTION").status, signals.MISS)
        missing = signals.evaluate(base_inputs(whale_exit_event=None, distribution_behavior=None))
        self.assertEqual(missing.pattern("DISTRIBUTION").status, signals.MISSING_DATA)


class CrossAxisSelectionTests(unittest.TestCase):
    def test_alpha_plus_and_alpha_follow_published_cross_axis_rules(self):
        plus = signals.evaluate_cross_axis(signals.CrossAxisInputs(D("75"), 3, True, "B"))
        self.assertEqual(plus.eligibility("ALPHA_PLUS").status, signals.HIT)
        self.assertEqual(plus.eligibility("ALPHA").status, signals.HIT)
        self.assertEqual(plus.selected, "ALPHA_PLUS")

        alpha = signals.evaluate_cross_axis(signals.CrossAxisInputs(D("75"), 3, True, "C"))
        self.assertEqual(alpha.eligibility("ALPHA_PLUS").status, signals.MISS)
        self.assertEqual(alpha.eligibility("ALPHA").status, signals.HIT)
        self.assertEqual(alpha.selected, "ALPHA")

        blocked = signals.evaluate_cross_axis(signals.CrossAxisInputs(D("100"), 10, True, "D"))
        self.assertEqual(blocked.eligibility("ALPHA_PLUS").status, signals.MISS)
        self.assertEqual(blocked.eligibility("ALPHA").status, signals.MISS)
        self.assertIsNone(blocked.selected)

    def test_cross_axis_missing_fact_stays_missing_and_smf_alias_is_not_used_as_selection(self):
        missing = signals.evaluate_cross_axis(signals.CrossAxisInputs(D("75"), 3, True, None))
        self.assertEqual(missing.eligibility("ALPHA_PLUS").status, signals.MISSING_DATA)
        self.assertEqual(missing.eligibility("ALPHA").status, signals.MISSING_DATA)
        self.assertIsNone(missing.selected)
        grade_s_but_weak_pattern = signals.evaluate_cross_axis(
            signals.CrossAxisInputs(D("59.999"), 3, True, "S"))
        self.assertEqual(grade_s_but_weak_pattern.eligibility("ALPHA_PLUS").status, signals.MISS)
        self.assertEqual(grade_s_but_weak_pattern.eligibility("ALPHA").status, signals.MISS)


class StatusLabelTests(unittest.TestCase):
    def test_status_labels_preserve_source_explicit_states(self):
        bundle = signals.evaluate_status_labels(
            signals.StatusLabelInputs(observe=True, dump_warning=False, new_candidate=None))
        self.assertEqual(bundle.label("OBSERVE").status, signals.HIT)
        self.assertEqual(bundle.label("DUMP_WARNING").status, signals.MISS)
        self.assertEqual(bundle.label("NEW_CANDIDATE").status, signals.MISSING_DATA)
        self.assertEqual(
            dict(bundle.label("OBSERVE").thresholds)["derivation"],
            "source_explicit",
        )

    def test_observe_derives_from_b_grade_and_no_detailed_pattern(self):
        hit = signals.evaluate_status_labels(
            signals.StatusLabelInputs(smf_grade="B", detailed_pattern_hit=False))
        self.assertEqual(hit.label("OBSERVE").status, signals.HIT)
        self.assertEqual(
            dict(hit.label("OBSERVE").evidence)["derivation_mode"],
            "official_guide_derivation",
        )
        pattern = signals.evaluate_status_labels(
            signals.StatusLabelInputs(smf_grade="B", detailed_pattern_hit=True))
        self.assertEqual(pattern.label("OBSERVE").status, signals.MISS)
        missing = signals.evaluate_status_labels(signals.StatusLabelInputs(smf_grade="B"))
        self.assertEqual(missing.label("OBSERVE").status, signals.MISSING_DATA)

    def test_dump_warning_published_branches_and_boundaries(self):
        grade_d = signals.evaluate_status_labels(signals.StatusLabelInputs(smf_grade="D"))
        self.assertEqual(grade_d.label("DUMP_WARNING").status, signals.HIT)

        chain = signals.evaluate_status_labels(signals.StatusLabelInputs(
            smf_grade="B", onchain_distribution_or_whale_exit=True,
            return_24h_pct=D("0"), distribution_behavior=False))
        self.assertEqual(chain.label("DUMP_WARNING").status, signals.HIT)

        crash = signals.evaluate_status_labels(signals.StatusLabelInputs(
            smf_grade="B", onchain_distribution_or_whale_exit=False,
            return_24h_pct=D("-10"), distribution_behavior=False))
        self.assertEqual(crash.label("DUMP_WARNING").status, signals.HIT)

        distribution = signals.evaluate_status_labels(signals.StatusLabelInputs(
            smf_grade="C", onchain_distribution_or_whale_exit=False,
            return_24h_pct=D("-5"), distribution_behavior=True))
        self.assertEqual(distribution.label("DUMP_WARNING").status, signals.HIT)

        miss = signals.evaluate_status_labels(signals.StatusLabelInputs(
            smf_grade="B", onchain_distribution_or_whale_exit=False,
            return_24h_pct=D("-5"), distribution_behavior=True))
        self.assertEqual(miss.label("DUMP_WARNING").status, signals.MISS)

    def test_new_candidate_requires_age_under_six_hours_and_no_other_label(self):
        six_hours_ms = 6 * 60 * 60 * 1000
        hit = signals.evaluate_status_labels(signals.StatusLabelInputs(
            first_pool_age_ms=six_hours_ms - 1, other_label_hit=False))
        self.assertEqual(hit.label("NEW_CANDIDATE").status, signals.HIT)
        boundary = signals.evaluate_status_labels(signals.StatusLabelInputs(
            first_pool_age_ms=six_hours_ms, other_label_hit=False))
        self.assertEqual(boundary.label("NEW_CANDIDATE").status, signals.MISS)
        occupied = signals.evaluate_status_labels(signals.StatusLabelInputs(
            first_pool_age_ms=1, other_label_hit=True))
        self.assertEqual(occupied.label("NEW_CANDIDATE").status, signals.MISS)
        missing = signals.evaluate_status_labels(signals.StatusLabelInputs(
            first_pool_age_ms=1, other_label_hit=None))
        self.assertEqual(missing.label("NEW_CANDIDATE").status, signals.MISSING_DATA)


class SignalPersistenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = MarketIntelStore(Path(directory.name) / "intel.sqlite")
        self.addCleanup(self.store.close)

    def test_hits_and_pattern_states_are_immutable_and_missing_is_explicit(self):
        bundle = signals.evaluate(base_inputs(return_1h_pct=D("1"), return_24h_pct=D("1"),
                                             volatility_percentile_15m=None))
        self.store.record_signal_bundle(bundle, source_snapshot_ids=("feature-1", "derivative-1"))
        self.store.record_signal_bundle(bundle, source_snapshot_ids=("feature-1", "derivative-1"))
        hit_types = {row[0] for row in self.store.connection.execute("SELECT signal_type FROM signal_hit")}
        self.assertEqual(hit_types, {"FUNDING_NEGATIVE_FLIP", "TEAM_DISTRIBUTION"})
        self.assertNotIn("OI_SURGE", hit_types)
        states = {row["signal_type"]: row["status"]
                  for row in self.store.connection.execute("SELECT * FROM signal_state")}
        self.assertEqual(len(states), 14)
        self.assertEqual(states["FUNDING_NEGATIVE_FLIP"], signals.HIT)
        self.assertEqual(states["MOMENTUM"], signals.MISS)
        self.assertEqual(states["OI_SURGE"], signals.DISABLED_UNKNOWN_THRESHOLD)
        rows = {row["pattern_type"]: row for row in self.store.connection.execute("SELECT * FROM pattern_hit")}
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows["AMBUSH"]["active"], 0)
        self.assertIn('"evaluation_status":"MISSING_DATA"', rows["AMBUSH"]["evidence_json"])
        self.assertEqual(rows["TREND_REVERSAL"]["active"], 1)
        self.assertEqual(rows["DISTRIBUTION"]["active"], 0)
        self.assertEqual(self.store.connection.execute("SELECT count(*) FROM pattern_hit").fetchone()[0], 7)


if __name__ == "__main__":
    unittest.main()
