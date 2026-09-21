from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from catos.market_intel import MarketIntelError, MarketIntelStore
from catos.market_lifecycle import (
    EXIT,
    FALSE,
    HOLD,
    MISSING_DATA,
    RISK_COOLING,
    RISK_RESOLVED,
    TRUE,
    FlowComponents,
    MomentumExitInputs,
    ScanInputs,
    ScanState,
    adaptive_exit_floor_pct,
    evaluate_momentum_exit,
    make_smf_snapshot,
    smf_grade,
    transition_scan,
)


FIXTURE = Path(__file__).with_name("fixtures") / "yaozi_p0d.json"


def _d(value):
    return None if value is None else Decimal(value)


def _inputs(row):
    flow = [_d(value) for value in row["flow"]]
    return ScanInputs(
        symbol="BTC-USDT-SWAP",
        observed_at_ms=row["observed_at_ms"],
        smf_score=_d(row["smf_score"]),
        smf_model_version="fixture-smf-v1",
        flow_components=FlowComponents(*flow),
        opportunity_quality=_d(row["quality"]),
        risk_score=_d(row["risk"]),
    )


class SmfContractTests(unittest.TestCase):
    def test_grade_boundaries_and_missing(self):
        cases = (
            (None, None),
            ("50", "S"),
            ("49.999", "A"),
            ("20", "A"),
            ("19.999", "B"),
            ("-20", "B"),
            ("-20.001", "C"),
            ("-49.999", "C"),
            ("-50", "D"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                score = None if value is None else Decimal(value)
                self.assertEqual(smf_grade(score), expected)
        with self.assertRaisesRegex(ValueError, "smf_score_out_of_range"):
            smf_grade(Decimal("100.001"))

    def test_snapshot_accepts_external_score_without_computing_private_weights(self):
        snapshot = make_smf_snapshot(
            symbol="BTC-USDT-SWAP", observed_at_ms=123, score=Decimal("61.25"),
            model_version="external-fixture-v1", components=None, confidence=None,
        )
        self.assertEqual(snapshot.score, Decimal("61.25"))
        self.assertEqual(snapshot.grade, "S")
        self.assertIsNone(snapshot.components)


class FlowContractTests(unittest.TestCase):
    def test_published_coefficients_are_not_normalized(self):
        all_one = FlowComponents(*(Decimal("1") for _ in range(7)))
        self.assertEqual(all_one.score(), Decimal("105"))
        missing = replace(all_one, oi_speed=None)
        self.assertIsNone(missing.score())


class MomentumExitContractTests(unittest.TestCase):
    def test_adaptive_floor_clamps_published_atr_multiple(self):
        self.assertEqual(adaptive_exit_floor_pct(Decimal("0.5")), Decimal("8"))
        self.assertEqual(adaptive_exit_floor_pct(Decimal("2")), Decimal("16"))
        self.assertEqual(adaptive_exit_floor_pct(Decimal("5")), Decimal("22"))
        self.assertIsNone(adaptive_exit_floor_pct(None))
        with self.assertRaisesRegex(ValueError, "invalid_atr_pct"):
            adaptive_exit_floor_pct(Decimal("-0.1"))

    def test_leading_stale_and_hard_peak_are_decisive_exits(self):
        leading = evaluate_momentum_exit(MomentumExitInputs(leading_exit=True))
        self.assertEqual((leading.decision, leading.reason), (EXIT, "leading_signal"))

        stale = evaluate_momentum_exit(MomentumExitInputs(
            since_last_scan_ms=720 * 60 * 60 * 1000, leading_exit=False))
        self.assertEqual((stale.decision, stale.reason), (EXIT, "stale_dropped"))

        peak = evaluate_momentum_exit(MomentumExitInputs(
            drawdown_from_peak_pct=Decimal("-20"), healthy_pullback=True,
            market_risk_off=True, leading_exit=False, since_last_scan_ms=0))
        self.assertEqual((peak.decision, peak.reason), (EXIT, "peak_drawdown"))

    def test_adaptive_breach_and_healthy_pullback_exemption(self):
        base = dict(atr_pct=Decimal("2"), drawdown_from_peak_pct=Decimal("-16"),
                    since_last_scan_ms=0, market_risk_off=False, leading_exit=False)
        exit_ = evaluate_momentum_exit(MomentumExitInputs(healthy_pullback=False, **base))
        self.assertEqual((exit_.decision, exit_.reason), (EXIT, "mfe_drawdown"))
        hold = evaluate_momentum_exit(MomentumExitInputs(healthy_pullback=True, **base))
        self.assertEqual((hold.decision, hold.reason), (HOLD, None))

    def test_unpublished_risk_off_tightening_stays_missing(self):
        unknown = evaluate_momentum_exit(MomentumExitInputs(
            atr_pct=Decimal("2"), drawdown_from_peak_pct=Decimal("-10"),
            since_last_scan_ms=0, healthy_pullback=False, market_risk_off=True,
            leading_exit=False))
        self.assertEqual(unknown.decision, MISSING_DATA)
        self.assertEqual(unknown.reason, "risk_off_or_exit_evidence_unknown")

        hold = evaluate_momentum_exit(MomentumExitInputs(
            atr_pct=Decimal("2"), drawdown_from_peak_pct=Decimal("-10"),
            since_last_scan_ms=0, healthy_pullback=False, market_risk_off=False,
            leading_exit=False))
        self.assertEqual((hold.decision, hold.reason), (HOLD, None))


class LifecycleFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_sequence_and_missing_semantics(self):
        state = ScanState()
        transitions = []
        for row in self.rows:
            result = transition_scan(state, _inputs(row))
            expected = row["expected"]
            self.assertEqual(
                (result.flow.state, result.flow.consecutive_count,
                 result.opportunity.state, result.opportunity.consecutive_count,
                 result.risk.state, result.risk.consecutive_count),
                tuple(expected),
            )
            transitions.append(result)
            state = result.next_state

        missing = transitions[3]
        self.assertIsNone(missing.flow.score)
        self.assertIsNone(missing.opportunity.score)
        self.assertIsNone(missing.risk.score)
        self.assertEqual(dict(missing.flow.evidence)["fade_gate"], MISSING_DATA)
        self.assertEqual(dict(missing.opportunity.evidence)["entry_gate"], MISSING_DATA)
        self.assertEqual(dict(missing.opportunity.evidence)["risk_block_gate"], MISSING_DATA)
        self.assertEqual(dict(missing.risk.evidence)["watch_gate"], MISSING_DATA)

        blocked = transitions[7]
        self.assertEqual(dict(blocked.opportunity.evidence)["entry_gate"], TRUE)
        self.assertEqual(dict(blocked.opportunity.evidence)["risk_block_gate"], TRUE)
        entered = transitions[8]
        self.assertEqual(dict(entered.opportunity.evidence)["risk_block_gate"], FALSE)
        self.assertEqual(entered.opportunity.event, "opportunity_entered")

    def test_same_previous_and_same_input_is_deterministic(self):
        previous = ScanState()
        inputs = _inputs(self.rows[0])
        self.assertEqual(transition_scan(previous, inputs), transition_scan(previous, inputs))

    def test_risk_cooling_requires_prior_active_risk_and_resolves_after_two_sub_30_scans(self):
        base = _inputs(self.rows[0])
        high = transition_scan(ScanState(), replace(base, risk_score=Decimal("65")))
        self.assertEqual(high.risk.state, "high_risk")

        cooling = transition_scan(
            high.next_state,
            replace(base, observed_at_ms=2_000, risk_score=Decimal("40")),
        )
        self.assertEqual(cooling.risk.state, RISK_COOLING)
        self.assertEqual(cooling.risk.consecutive_count, 0)
        self.assertEqual(cooling.risk.event, "risk_cooling")

        low_one = transition_scan(
            cooling.next_state,
            replace(base, observed_at_ms=3_000, risk_score=Decimal("29.999")),
        )
        self.assertEqual(low_one.risk.state, RISK_COOLING)
        self.assertEqual(low_one.risk.consecutive_count, 1)

        low_two = transition_scan(
            low_one.next_state,
            replace(base, observed_at_ms=4_000, risk_score=Decimal("20")),
        )
        self.assertEqual(low_two.risk.state, RISK_RESOLVED)
        self.assertEqual(low_two.risk.consecutive_count, 2)
        self.assertEqual(low_two.risk.event, "risk_resolved")

        inactive_low = transition_scan(
            ScanState(), replace(base, observed_at_ms=5_000, risk_score=Decimal("20")))
        self.assertEqual(inactive_low.risk.state, "inactive")
        self.assertEqual(inactive_low.risk.consecutive_count, 0)

    def test_persistence_is_exact_replay_and_decimal_text(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        store = MarketIntelStore(Path(directory.name) / "intel.sqlite")
        self.addCleanup(store.close)

        result = transition_scan(ScanState(), _inputs(self.rows[0]))
        store.record_scan_transition(result)
        store.record_scan_transition(result)

        smf = store.connection.execute(
            "SELECT score_text,grade FROM smf_snapshot WHERE symbol=?",
            ("BTC-USDT-SWAP",),
        ).fetchone()
        self.assertEqual(tuple(smf), ("55", "S"))
        views = store.connection.execute(
            "SELECT view_name,state,score_text,consecutive_count FROM view_state ORDER BY view_name"
        ).fetchall()
        self.assertEqual(len(views), 3)
        self.assertTrue(all(row["score_text"] is None or isinstance(row["score_text"], str) for row in views))

        changed_inputs = replace(_inputs(self.rows[0]), smf_score=Decimal("56"))
        changed = transition_scan(ScanState(), changed_inputs)
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            store.record_scan_transition(changed)


if __name__ == "__main__":
    unittest.main()
