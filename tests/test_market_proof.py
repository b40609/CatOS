from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

from catos.market_intel import MarketIntelError, MarketIntelStore
from catos.market_lifecycle import FlowComponents, ScanInputs, ScanState, transition_scan
from catos.market_orchestrator import MarketScanOrchestrator, PushCandidate
from catos.market_proof import (
    CYCLE_END, CYCLE_NONE, CYCLE_OBSERVE, CYCLE_PUSH, CYCLE_START, HORIZON_24H_MS,
    HISTORY_FLAT_RULE_POST, HISTORY_FLAT_RULE_PRE,
    CycleDirective, PricePoint, evaluate_24h, freeze_push_snapshot,
    history_flat_rule_for_date, history_flat_rule_versions, transition_cycle,
)


def _scan_inputs(observed_at_ms):
    return ScanInputs(
        symbol="BTC-USDT-SWAP", observed_at_ms=observed_at_ms,
        smf_score=Decimal("55"), smf_model_version="fixture-smf-v1",
        flow_components=FlowComponents(*(Decimal("1") for _ in range(7))),
        opportunity_quality=Decimal("60"), risk_score=Decimal("20"),
    )


def _candidate():
    return PushCandidate(
        push_type="flow_ignition", active_l2=("MOMENTUM",),
        patterns={"PREHEAT": "HIT"},
        feature_version="feature-v1", signal_version="signal-v1",
        source_freshness={"okx": "fresh", "binance": "fresh"},
        market_regime={"structure": "RANGE"}, pre_entry_volatility=Decimal("2.5"),
    )


def _frozen_push(at_ms, cycle_id, price=Decimal("100")):
    return freeze_push_snapshot(
        symbol="BTC-USDT-SWAP", pushed_at_ms=at_ms, push_type="flow_ignition",
        cycle_id=cycle_id, price=price, active_l2=("MOMENTUM",),
        patterns={"PREHEAT": "HIT"}, smf={"score": Decimal("55"), "grade": "S"},
        views={"flow": "ignition", "opportunity": "active", "risk": "inactive"},
        feature_version="feature-v1", signal_version="signal-v1",
        source_freshness={"okx": "fresh", "binance": "fresh"},
        market_regime={"structure": "RANGE"}, pre_entry_volatility=Decimal("2.5"),
    )


class CycleTests(unittest.TestCase):
    def test_explicit_cycle_lifecycle_is_deterministic(self):
        start = transition_cycle(
            None, symbol="BTC-USDT-SWAP", observed_at_ms=1000, price=Decimal("100"),
            directive=CycleDirective(CYCLE_START, push_type="flow_ignition", view_name="flow"),
        )
        self.assertEqual(start.after.push_count, 1)
        self.assertEqual(start.event.event_type, "cycle_started")
        replay = transition_cycle(
            None, symbol="BTC-USDT-SWAP", observed_at_ms=1000, price=Decimal("100"),
            directive=CycleDirective(CYCLE_START, push_type="flow_ignition", view_name="flow"),
        )
        self.assertEqual(start, replay)

        observed = transition_cycle(
            start.after, symbol="BTC-USDT-SWAP", observed_at_ms=2000, price=Decimal("97"),
            directive=CycleDirective(CYCLE_OBSERVE),
        )
        self.assertEqual(observed.after.trough_price, Decimal("97"))
        self.assertEqual(observed.after.mae_pct, Decimal("-3"))
        pushed = transition_cycle(
            observed.after, symbol="BTC-USDT-SWAP", observed_at_ms=3000, price=Decimal("110"),
            directive=CycleDirective(CYCLE_PUSH, push_type="opportunity", view_name="opportunity"),
        )
        self.assertEqual((pushed.after.push_count, pushed.after.peak_price), (2, Decimal("110")))
        self.assertEqual(pushed.after.mfe_pct, Decimal("10"))
        ended = transition_cycle(
            pushed.after, symbol="BTC-USDT-SWAP", observed_at_ms=4000, price=Decimal("105"),
            directive=CycleDirective(CYCLE_END, view_name="flow", end_reason="flow_faded"),
        )
        self.assertEqual(ended.after.end_reason, "flow_faded")

    def test_private_cycle_start_gate_is_not_inferred(self):
        empty = transition_cycle(
            None, symbol="BTC-USDT-SWAP", observed_at_ms=500, price=Decimal("100"),
            directive=CycleDirective(CYCLE_NONE),
        )
        self.assertIsNone(empty.after)
        with self.assertRaisesRegex(ValueError, "active_cycle_required"):
            transition_cycle(
                None, symbol="BTC-USDT-SWAP", observed_at_ms=1000, price=Decimal("100"),
                directive=CycleDirective(CYCLE_OBSERVE),
            )


class HistoryRuleTests(unittest.TestCase):
    def test_flat_threshold_version_changes_on_2026_05_08_without_timestamp_timezone_guess(self):
        before = history_flat_rule_for_date(date(2026, 5, 7))
        after = history_flat_rule_for_date(date(2026, 5, 8))
        self.assertEqual((before.version, before.threshold_pct),
                         (HISTORY_FLAT_RULE_PRE, Decimal("3")))
        self.assertEqual((after.version, after.threshold_pct),
                         (HISTORY_FLAT_RULE_POST, Decimal("1")))
        versions = history_flat_rule_versions()
        self.assertEqual(versions, (before, after))
        with self.assertRaisesRegex(ValueError, "invalid_history_date"):
            history_flat_rule_for_date("2026-05-08")


class PushProofTests(unittest.TestCase):
    def test_24h_proof_uses_decimal_raw_excursions(self):
        cycle = transition_cycle(
            None, symbol="BTC-USDT-SWAP", observed_at_ms=1000, price=Decimal("100"),
            directive=CycleDirective(CYCLE_START, push_type="flow_ignition"),
        ).after
        push = _frozen_push(1000, cycle.cycle_id)
        result = evaluate_24h(
            push=push, measured_at_ms=1000 + HORIZON_24H_MS,
            terminal_price=Decimal("108"),
            path=(
                PricePoint(2000, Decimal("95")),
                PricePoint(3000, Decimal("112")),
                PricePoint(1000 + HORIZON_24H_MS, Decimal("108")),
            ),
            market_baseline_pct=Decimal("1.5"), vol_matched_baseline_pct=Decimal("2.0"),
        )
        self.assertEqual((result.return_pct, result.mfe_pct, result.mae_pct),
                         (Decimal("8"), Decimal("12"), Decimal("-5")))
        with self.assertRaisesRegex(ValueError, "proof_not_due"):
            evaluate_24h(
                push=push, measured_at_ms=999 + HORIZON_24H_MS,
                terminal_price=Decimal("108"), path=(PricePoint(2000, Decimal("108")),),
            )


class PersistenceAndOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = MarketIntelStore(Path(self.directory.name) / "intel.sqlite")
        self.addCleanup(self.store.close)

    def test_push_is_committed_before_notification_and_replay_is_exact(self):
        observed_at = 10_000
        notifications = []

        def notify(item):
            row = self.store.connection.execute(
                "SELECT push_id FROM push_snapshot WHERE push_id=?", (item.push_id,),
            ).fetchone()
            self.assertIsNotNone(row)
            notifications.append(item.push_id)

        runner = MarketScanOrchestrator(self.store, notify)
        result = runner.run(
            previous_scan=ScanState(), inputs=_scan_inputs(observed_at), previous_cycle=None,
            price=Decimal("100"),
            cycle_directive=CycleDirective(CYCLE_START, push_type="flow_ignition", view_name="flow"),
            push_candidate=_candidate(),
        )
        self.assertEqual(result.next_scan_at_ms, observed_at + 60_000)
        self.assertEqual(notifications, [result.push.push_id])
        self.assertEqual(self.store.connection.execute("SELECT COUNT(*) FROM cycle_event").fetchone()[0], 1)

        runner.run(
            previous_scan=ScanState(), inputs=_scan_inputs(observed_at), previous_cycle=None,
            price=Decimal("100"),
            cycle_directive=CycleDirective(CYCLE_START, push_type="flow_ignition", view_name="flow"),
            push_candidate=_candidate(),
        )
        self.assertEqual(self.store.connection.execute("SELECT COUNT(*) FROM push_snapshot").fetchone()[0], 1)
        self.assertEqual(notifications, [result.push.push_id])

    def test_changed_same_push_identity_conflicts(self):
        observed_at = 20_000
        runner = MarketScanOrchestrator(self.store)
        runner.run(
            previous_scan=ScanState(), inputs=_scan_inputs(observed_at), previous_cycle=None,
            price=Decimal("100"), cycle_directive=CycleDirective(CYCLE_START, push_type="flow_ignition"),
            push_candidate=_candidate(),
        )
        changed = replace(_candidate(), patterns={"PREHEAT": "MISS"})
        with self.assertRaisesRegex(MarketIntelError, "snapshot_conflict"):
            runner.run(
                previous_scan=ScanState(), inputs=_scan_inputs(observed_at), previous_cycle=None,
                price=Decimal("100"),
                cycle_directive=CycleDirective(CYCLE_START, push_type="flow_ignition"),
                push_candidate=changed,
            )

    def test_cycle_end_persists_timestamp_reason_and_range(self):
        start_at = 30_000
        start = transition_cycle(
            None, symbol="BTC-USDT-SWAP", observed_at_ms=start_at, price=Decimal("100"),
            directive=CycleDirective(CYCLE_START, push_type="flow_ignition"),
        )
        lifecycle = MarketScanOrchestrator(self.store).run(
            previous_scan=ScanState(), inputs=_scan_inputs(start_at), previous_cycle=None,
            price=Decimal("100"), cycle_directive=CycleDirective(CYCLE_START, push_type="flow_ignition"),
            push_candidate=_candidate(),
        )
        end_at = start_at + 60_000
        ended = transition_cycle(
            lifecycle.cycle.after, symbol="BTC-USDT-SWAP", observed_at_ms=end_at,
            price=Decimal("93"), directive=CycleDirective(CYCLE_END, end_reason="flow_faded"),
        )
        next_lifecycle = transition_scan(lifecycle.lifecycle.next_state, _scan_inputs(end_at))
        self.store.record_p0e_scan(next_lifecycle, ended)
        row = self.store.connection.execute(
            "SELECT ended_at_ms,end_reason,trough_price_text,mfe_text,mae_text FROM cycle WHERE cycle_id=?",
            (start.after.cycle_id,),
        ).fetchone()
        self.assertEqual(tuple(row), (end_at, "flow_faded", "93", "0", "-7"))

    def test_proof_persistence_is_decimal_text_and_immutable(self):
        run = MarketScanOrchestrator(self.store).run(
            previous_scan=ScanState(), inputs=_scan_inputs(1000), previous_cycle=None,
            price=Decimal("100"), cycle_directive=CycleDirective(CYCLE_START, push_type="flow_ignition"),
            push_candidate=_candidate(),
        )
        push = run.push
        result = evaluate_24h(
            push=push, measured_at_ms=1000 + HORIZON_24H_MS, terminal_price=Decimal("108"),
            path=(PricePoint(2000, Decimal("95")), PricePoint(3000, Decimal("112"))),
        )
        self.store.record_proof_result(result)
        self.store.record_proof_result(result)
        row = self.store.connection.execute(
            "SELECT return_text,mfe_text,mae_text FROM forward_return WHERE push_id=?", (push.push_id,),
        ).fetchone()
        self.assertEqual(tuple(row), ("8", "12", "-5"))

    def test_proof_requires_frozen_push(self):
        cycle = transition_cycle(
            None, symbol="BTC-USDT-SWAP", observed_at_ms=1000, price=Decimal("100"),
            directive=CycleDirective(CYCLE_START, push_type="flow_ignition"),
        ).after
        push = _frozen_push(1000, cycle.cycle_id)
        result = evaluate_24h(
            push=push, measured_at_ms=1000 + HORIZON_24H_MS, terminal_price=Decimal("100"),
            path=(PricePoint(2000, Decimal("100")),),
        )
        with self.assertRaisesRegex(MarketIntelError, "unknown_push"):
            self.store.record_proof_result(result)


if __name__ == "__main__":
    unittest.main()
