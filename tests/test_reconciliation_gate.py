"""Offline reconciliation gate tests; temporary SQLite and synthetic evidence only."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from catos import risk
from catos.journal import Journal, Reconciliation, canonical
from catos.okx_collection import SNAPSHOT_SEMANTICS_CONTRACT, WINDOW_COVERAGE_CONTRACT
from catos.reconciliation_gate import (
    DayLedgerEvidence,
    FreshnessEvidence,
    FreshnessPolicy,
    evaluate,
)
from test_ipc import config


D = Decimal


def proof(revision):
    return Reconciliation(revision, "synthetic-gate-proof", D("0"), 0, 0, 0, True)


BASE_TAIPEI_MS = 57_600_000


def signed_report(*, facts=None, discrepancies=None, external_flow="0",
                  instrument="SYNTHETIC-USDT-SWAP"):
    aliases = ("balance", "positions", "orders_pending", "algo_pending", "fills", "bills")
    sources = []
    for index, alias in enumerate(aliases):
        started = BASE_TAIPEI_MS + 1_000 + index * 10
        completed = started + 10
        sources.append({
            "alias": alias,
            "started_ms": started,
            "completed_ms": completed,
            "requests": 1,
            "source_time_semantics": "transport_supplied_not_verified_snapshot",
            "record_time_semantics": ("event_ms" if alias in ("fills", "bills")
                                      else "last_update_or_reference_ms_not_snapshot"),
            "window_request_evidence": ({
                "contract_id": WINDOW_COVERAGE_CONTRACT,
                "begin_ms": BASE_TAIPEI_MS,
                "end_ms": BASE_TAIPEI_MS + 86_400_000,
                "event_time_field": "ts",
                "cursor_semantics": "after_bill_id",
                "filter_semantics": "exact_inclusive_begin_end",
            } if alias in ("fills", "bills") else None),
            "complete": True,
            "issue": "",
            "pages": [{"page_number": 1, "request_cursor": None, "next_cursor": None,
                       "source_ms": completed, "received_ms": completed, "digest": "synthetic"}],
        })
    report = {
        "version": "i-b-2.v1",
        "account_alias": "okx-demo",
        "environment": "demo",
        "instrument": instrument,
        "window_start_ms": BASE_TAIPEI_MS,
        "window_end_ms": BASE_TAIPEI_MS + 86_400_000,
        "started_ms": BASE_TAIPEI_MS + 1_000,
        "completed_ms": BASE_TAIPEI_MS + 1_100,
        "collection_complete": True,
        "reconciled": False,
        "trade_authorized": False,
        "snapshot_semantics": {
            "contract_id": SNAPSHOT_SEMANTICS_CONTRACT,
            "mode": "bounded_sequential_observation",
            "atomic_snapshot": False,
            "record_update_time_is_snapshot_fence": False,
            "transport_time_is_snapshot_fence": False,
        },
        "sources": sources,
        "facts": [] if facts is None else facts,
        "discrepancies": ["freshness_unverified", "window_coverage_unverified", "day_baseline_unverified"]
                         if discrepancies is None else discrepancies,
        "record_diagnostics": [],
        "observed_signed_fees_by_currency": {},
        "observed_external_flow_usdt": external_flow,
        "day_external_flow_usdt": external_flow,
        "flow_classification_id": "synthetic-flow-classification",
        "flow_classification_complete": True,
    }
    report["content_digest"] = hashlib.sha256(
        json.dumps(report, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return report


def explicit_policy():
    return FreshnessPolicy("synthetic-policy", 100, 200, 50, 100, BASE_TAIPEI_MS + 1_150)


def explicit_freshness():
    return FreshnessEvidence(BASE_TAIPEI_MS + 1_140, BASE_TAIPEI_MS + 1_150)


def explicit_day(*, flow=D("0"), unknown=0):
    return DayLedgerEvidence(BASE_TAIPEI_MS, D("1000"), "synthetic-baseline", flow,
                             "synthetic-flow-classification", unknown)


class _JournalFixture:
    def setUp(self):
        super().setUp()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state.sqlite3"
        self.j = Journal(self.path, "fake-account", D("100"), risk.Limits(), True)
        self.addCleanup(self.j.close)
        self.j.register("bot", config())
        self.j.reconcile("bot", proof(0))

    def insert_order(self, key, state, *, exchange_id=None, settled=0):
        with self.j._transaction():
            self.j.connection.execute("""INSERT INTO execution_orders
                (order_key,cl_ord_id,intent_key,bot_id,payload_json,quantity,filled,reservation,state,
                 cancel_pending,settled,deadline,epoch,exchange_id,report_revision,report_json)
                VALUES (?,?,NULL,'bot',?,'1','0','0',?,0,?,999999,0,?,0,NULL)""",
                (key, "client-" + key, canonical({"reduceOnly": False}), state, settled, exchange_id))


class ReconciliationSnapshotTests(_JournalFixture, unittest.TestCase):

    def test_snapshot_is_read_only_stable_and_report_attribution_is_explicit(self):
        before = self.j.connection.total_changes
        first = self.j.reconciliation_snapshot("bot")
        second = self.j.reconciliation_snapshot("bot")
        self.assertEqual(self.j.connection.total_changes, before)
        self.assertEqual(first, second)
        self.assertTrue(first.valid())
        self.assertEqual((first.bot_revision, first.local_position), (0, D("0")))
        self.assertEqual(first.report_attribution(), {
            "owned_order_ids": frozenset(), "owned_algo_ids": frozenset(),
            "owned_positions": {}, "unresolved_local_ids": frozenset()})

    def test_snapshot_uses_durable_remote_order_ids_and_preserves_unknown(self):
        self.insert_order("known", "LIVE", exchange_id="remote-order")
        self.insert_order("unknown", "UNKNOWN")
        snap = self.j.reconciliation_snapshot("bot")
        self.assertEqual(snap.owned_exchange_order_ids, ("remote-order",))
        self.assertEqual(snap.unresolved_local_ids, ("unknown",))
        self.assertEqual((snap.ordinary_open_count, snap.unknown_count), (1, 1))
        self.assertEqual(snap.report_attribution()["owned_order_ids"], frozenset(("remote-order",)))


class GateTests(_JournalFixture, unittest.TestCase):
    def complete(self, report, snap, **changes):
        args = dict(
            revision_before=snap.bot_revision,
            revision_after=snap.bot_revision,
            freshness_policy=explicit_policy(),
            freshness_evidence=explicit_freshness(),
            day_ledger=explicit_day(),
        )
        args.update(changes)
        return evaluate(report, snap, **args)

    def test_flat_snapshot_reaches_policy_blockers_and_never_authorizes_trade(self):
        snap = self.j.reconciliation_snapshot("bot")
        result = evaluate(signed_report(), snap, revision_before=0, revision_after=0)
        self.assertFalse(result.reconciled)
        self.assertFalse(result.trade_authorized)
        self.assertEqual(set(result.blockers), {
            "freshness_policy_unset", "snapshot_freshness_unverified",
            "day_baseline_unverified"})

    def test_explicit_synthetic_evidence_can_reconcile_but_not_authorize_trade(self):
        snap = self.j.reconciliation_snapshot("bot")
        result = self.complete(signed_report(), snap)
        self.assertTrue(result.reconciled)
        self.assertFalse(result.trade_authorized)
        self.assertEqual(result.blockers, ())

    def test_revision_race_and_foreign_responsibility_fail_closed(self):
        snap = self.j.reconciliation_snapshot("bot")
        report = signed_report(discrepancies=["foreign_order"])
        result = self.complete(report, snap, revision_after=1)
        self.assertIn("local_revision_changed", result.blockers)
        self.assertIn("foreign_order", result.blockers)
        self.assertFalse(result.reconciled)

    def test_unknown_local_order_blocks_even_with_other_evidence_complete(self):
        self.insert_order("unknown", "UNKNOWN")
        snap = self.j.reconciliation_snapshot("bot")
        result = self.complete(signed_report(), snap)
        self.assertIn("local_unknown", result.blockers)

    def test_missing_day_baseline_and_flow_evidence_remain_blockers(self):
        snap = self.j.reconciliation_snapshot("bot")
        report = signed_report(discrepancies=["external_flow_unavailable", "unknown_external_flow"],
                               external_flow=None)
        result = evaluate(report, snap, revision_before=0, revision_after=0,
                          freshness_policy=explicit_policy(), freshness_evidence=explicit_freshness())
        self.assertIn("day_baseline_unverified", result.blockers)
        self.assertIn("external_flow_unavailable", result.blockers)
        self.assertIn("unknown_external_flow", result.blockers)

    def test_window_coverage_is_derived_from_bound_request_and_page_evidence(self):
        snap = self.j.reconciliation_snapshot("bot")

        cases = (
            ("fill-request-evidence-missing",
             lambda report: next(source for source in report["sources"]
                                 if source["alias"] == "fills").update(window_request_evidence=None),
             {"window_coverage_unverified", "fill_window_coverage_unverified"}),
            ("bill-window-mismatch",
             lambda report: next(source for source in report["sources"]
                                 if source["alias"] == "bills")["window_request_evidence"].update(begin_ms=1),
             {"window_coverage_unverified", "bill_window_coverage_unverified"}),
            ("fill-chain-not-terminal",
             lambda report: next(source for source in report["sources"]
                                 if source["alias"] == "fills")["pages"][0].update(next_cursor="cursor_1"),
             {"window_coverage_unverified", "fill_window_coverage_unverified"}),
            ("fill-event-outside-window",
             lambda report: report["facts"].append({"kind": "fill", "ts": report["window_end_ms"] + 1}),
             {"window_coverage_unverified", "fill_window_coverage_unverified"}),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                report = signed_report()
                mutate(report)
                body = {k: v for k, v in report.items() if k != "content_digest"}
                report["content_digest"] = hashlib.sha256(
                    json.dumps(body, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
                result = self.complete(report, snap)
                self.assertFalse(result.reconciled)
                self.assertTrue(expected <= set(result.blockers))

    def test_window_coverage_accepts_inclusive_boundaries(self):
        snap = self.j.reconciliation_snapshot("bot")
        report = signed_report(facts=[
            {"kind": "fill", "ts": BASE_TAIPEI_MS},
            {"kind": "fill", "ts": BASE_TAIPEI_MS + 86_400_000},
            {"kind": "bill", "ts": BASE_TAIPEI_MS, "timing_verified": "after_baseline",
             "timing_evidence_id": "synthetic-baseline"},
            {"kind": "bill", "ts": BASE_TAIPEI_MS + 86_400_000},
        ])
        result = self.complete(report, snap)
        self.assertTrue(result.reconciled)

    def test_known_forbidden_blocks_even_with_complete_day_evidence(self):
        snap = self.j.reconciliation_snapshot("bot")
        result = self.complete(signed_report(discrepancies=["unsupported_account_activity"]), snap)
        self.assertIn("unsupported_account_activity", result.blockers)
        self.assertNotIn("unknown_external_flow", result.blockers)
        self.assertFalse(result.reconciled)
        self.assertFalse(result.trade_authorized)

    def test_flow_classification_id_mismatch_fails_closed(self):
        snap = self.j.reconciliation_snapshot("bot")
        report = signed_report()
        report["flow_classification_id"] = "different-flow-classification"
        report["content_digest"] = hashlib.sha256(
            json.dumps({k: v for k, v in report.items() if k != "content_digest"},
                       sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        result = self.complete(report, snap)
        self.assertFalse(result.reconciled)
        self.assertIn("external_flow_mismatch", result.blockers)

    def test_partial_catalog_allows_known_flows_but_keeps_actual_blockers(self):
        snap = self.j.reconciliation_snapshot("bot")
        for issues, complete, blocker in (
            ([], True, None),
            (["unknown_external_flow"], True, "unknown_external_flow"),
            (["unsupported_account_activity"], True, "unsupported_account_activity"),
            ([], False, "collection_incomplete"),
        ):
            report = signed_report(discrepancies=issues)
            report["flow_classification_complete"] = False
            report["collection_complete"] = complete
            report["content_digest"] = hashlib.sha256(
                json.dumps({k: v for k, v in report.items() if k != "content_digest"},
                           sort_keys=True, ensure_ascii=True).encode()).hexdigest()
            result = self.complete(report, snap)
            with self.subTest(blocker=blocker):
                self.assertEqual(result.reconciled, blocker is None)
                self.assertFalse(result.trade_authorized)
                if blocker:
                    self.assertIn(blocker, result.blockers)
                else:
                    self.assertNotIn("unknown_external_flow", result.blockers)

    def test_p6_obligation_without_remote_algo_identity_blocks(self):
        with self.j._transaction():
            state = self.j.protection.state("bot")
            state["config"]["ratio"] = "0.1"
            state["active"] = {"price": "90", "side": "sell", "trigger": "mark",
                               "payload": {"requestId": "local-only"}}
            self.j.connection.execute("UPDATE protection SET state_json=? WHERE bot_id='bot'",
                                      (canonical(state),))
        snap = self.j.reconciliation_snapshot("bot")
        result = self.complete(signed_report(), snap)
        self.assertIn("algo_identity_unavailable", result.blockers)
        self.assertIn("p6_protection_unverified", result.blockers)

    def test_snapshot_exposes_durable_protection_algo_identity(self):
        with self.j._transaction():
            state = self.j.protection.state("bot")
            state["config"]["ratio"] = "0.1"
            state["active"] = {"price": "90", "side": "sell", "trigger": "mark",
                               "algo_id": "remote-algo", "payload": {"requestId": "local-only"}}
            self.j.connection.execute("UPDATE protection SET state_json=? WHERE bot_id='bot'",
                                      (canonical(state),))
        snap = self.j.reconciliation_snapshot("bot")
        self.assertEqual(snap.owned_exchange_algo_ids, ("remote-algo",))
        result = self.complete(signed_report(), snap)
        self.assertNotIn("algo_identity_unavailable", result.blockers)

    def test_report_digest_tamper_is_detected(self):
        snap = self.j.reconciliation_snapshot("bot")
        report = signed_report()
        report["completed_ms"] = BASE_TAIPEI_MS + 1_101
        result = self.complete(report, snap)
        self.assertIn("evidence_integrity_failed", result.blockers)

    def test_freshness_boundary_contract_is_fail_closed(self):
        snap = self.j.reconciliation_snapshot("bot")
        report = signed_report()

        exact = FreshnessPolicy("boundary-policy", 50, 100, 50, 50, BASE_TAIPEI_MS + 1_150)
        result = self.complete(
            report, snap,
            freshness_policy=exact,
            freshness_evidence=FreshnessEvidence(BASE_TAIPEI_MS + 1_100, BASE_TAIPEI_MS + 1_100),
        )
        self.assertTrue(result.reconciled)

        cases = (
            (FreshnessPolicy("age-over", 49, 100, 50, 50, BASE_TAIPEI_MS + 1_150),
             FreshnessEvidence(BASE_TAIPEI_MS + 1_100, BASE_TAIPEI_MS + 1_100)),
            (FreshnessPolicy("span-over", 50, 99, 50, 50, BASE_TAIPEI_MS + 1_150),
             FreshnessEvidence(BASE_TAIPEI_MS + 1_100, BASE_TAIPEI_MS + 1_100)),
            (FreshnessPolicy("checked-before-complete", 50, 100, 50, 50, BASE_TAIPEI_MS + 1_099),
             FreshnessEvidence(BASE_TAIPEI_MS + 1_099, BASE_TAIPEI_MS + 1_099)),
            (FreshnessPolicy("server-skew-positive", 50, 100, 50, 50, BASE_TAIPEI_MS + 1_150),
             FreshnessEvidence(BASE_TAIPEI_MS + 1_049, BASE_TAIPEI_MS + 1_100)),
            (FreshnessPolicy("server-skew-negative", 50, 100, 50, 50, BASE_TAIPEI_MS + 1_150),
             FreshnessEvidence(BASE_TAIPEI_MS + 1_151, BASE_TAIPEI_MS + 1_100)),
            (FreshnessPolicy("clock-sample-age-over", 50, 100, 50, 49, BASE_TAIPEI_MS + 1_150),
             FreshnessEvidence(BASE_TAIPEI_MS + 1_100, BASE_TAIPEI_MS + 1_100)),
            (FreshnessPolicy("clock-sample-in-future", 50, 100, 50, 50, BASE_TAIPEI_MS + 1_150),
             FreshnessEvidence(BASE_TAIPEI_MS + 1_151, BASE_TAIPEI_MS + 1_151)),
        )
        for policy, freshness in cases:
            with self.subTest(policy=policy.policy_id):
                result = self.complete(
                    report, snap,
                    freshness_policy=policy,
                    freshness_evidence=freshness,
                )
                self.assertFalse(result.reconciled)
                self.assertIn("snapshot_freshness_unverified", result.blockers)

        tampered = signed_report()
        tampered["snapshot_semantics"]["record_update_time_is_snapshot_fence"] = True
        body = {k: v for k, v in tampered.items() if k != "content_digest"}
        tampered["content_digest"] = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
        result = self.complete(
            tampered, snap,
            freshness_policy=exact,
            freshness_evidence=FreshnessEvidence(1_100, 1_100),
        )
        self.assertFalse(result.reconciled)
        self.assertIn("snapshot_freshness_unverified", result.blockers)

    def test_snapshot_semantics_requires_complete_ordered_state_and_event_sources(self):
        snap = self.j.reconciliation_snapshot("bot")
        for mutate in (
            lambda report: report["sources"].pop(),
            lambda report: report["sources"].pop(4),
            lambda report: report["sources"].pop(1),
            lambda report: report["sources"][1].update(started_ms=1_005),
            lambda report: report["sources"][0].update(
                record_time_semantics="record_uTime_snapshot"),
            lambda report: report["sources"][0].update(
                source_time_semantics="receive_time_snapshot"),
        ):
            report = signed_report()
            mutate(report)
            body = {k: v for k, v in report.items() if k != "content_digest"}
            report["content_digest"] = hashlib.sha256(
                json.dumps(body, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
            result = self.complete(report, snap)
            self.assertFalse(result.reconciled)
            self.assertIn("snapshot_freshness_unverified", result.blockers)


if __name__ == "__main__":
    unittest.main()
