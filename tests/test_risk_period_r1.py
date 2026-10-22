"""R1 offline integration: isolated SQLite, synthetic observations, no transport."""

import asyncio
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import json
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from catos import account_lock, ipc, okx_readonly, reconciliation_gate as gate, risk, risk_period
from catos.journal import Journal, JournalError
from catos.fake_exchange import FakeExchange
from catos.supervisor import LocalSupervisor, SupervisorUnavailable
from test_ipc import config
from test_journal import proof
from test_reconciliation_gate import BASE_TAIPEI_MS as MIDNIGHT, signed_report
from test_supervisor import wait_flag


CLASSIFICATIONS = okx_readonly.FlowClassification("r1-synthetic", (
    okx_readonly.FlowClassificationEntry("1", "1", "external", "fixture-deposit"),
    okx_readonly.FlowClassificationEntry("2", "2", "internal", "fixture-fee"),
    okx_readonly.FlowClassificationEntry("3", "3", "forbidden", "fixture-forbidden")), True)


def report_at(offset=36_000_000, *, value="1000", facts=(), issues=()):
    report = signed_report()
    report.update(account_alias="r1-fixture", environment="local-sim",
        started_ms=MIDNIGHT + offset + 1000, completed_ms=MIDNIGHT + offset + 1100,
        window_end_ms=MIDNIGHT + offset + 1100)
    for source in report["sources"]:
        source["started_ms"] += offset
        source["completed_ms"] += offset
        for page in source["pages"]:
            page["source_ms"] += offset
            page["received_ms"] += offset
        if source["window_request_evidence"]:
            source["window_request_evidence"]["end_ms"] = report["window_end_ms"]
    report["facts"] = [dict(kind="balance", details=[dict(ccy="USDT", eq=value, liab="0")]), *facts]
    report["discrepancies"].extend(issues)
    return risk_period.seal(report)


def bill(bid, stamp, amount="100", **extra):
    return dict(kind="bill", billId=bid, ts=stamp, type="1", subType="1", ccy="USDT", balChg=amount, **extra)


class Clock:
    def __init__(self, now):
        self.now = now

    def wall_ms(self):
        return self.now


class R1Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "r1.sqlite3"
        lock = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        lock.start()
        self.addCleanup(lock.stop)
        self.clock = Clock(report_at()["completed_ms"] + 50)
        self.supervisor = await self.open_supervisor()

    async def open_supervisor(self):
        supervisor = LocalSupervisor(self.path, account_id="r1-fixture", bot_id="bot",
            config=config(), fixture_budget=D("100"), risk_limits=risk.Limits(), day_clock=self.clock,
            exchange=FakeExchange("r1-fixture"))
        self.addAsyncCleanup(supervisor.close)
        await supervisor.start()
        # Explicit synthetic empty-account evidence; never an exchange read.
        if supervisor.revision == 0:
            await supervisor.reconcile(proof(0))
        return supervisor

    def qualification(self):
        return dict(classifications=CLASSIFICATIONS,
            freshness_policy=gate.FreshnessPolicy("fixture-r1", 100, 200, 50, 100, self.clock.now),
            freshness_evidence=gate.FreshnessEvidence(self.clock.now - 10, self.clock.now))

    async def prepare(self, report=None):
        return await self.supervisor.prepare_risk_period(report or report_at(), **self.qualification())

    async def observe(self, report, *, position=D("0")):
        snapshot = risk.Snapshot(self.supervisor.risk_state.seq + 1, self.clock.now,
            report["completed_ms"] + 1000, D("1"), D("1"), position, D("100"))
        return await self.supervisor.observe_risk_period(report, snapshot, **self.qualification())

    async def test_morning_commit_observe_report_and_restart_fixed_denominator(self):
        report = report_at()
        candidate = risk_period.candidate(report, "r1-fixture")
        with self.assertRaisesRegex(SupervisorUnavailable, "durably"):
            self.supervisor.observe_risk(risk.Snapshot(1, report["completed_ms"], self.clock.now + 100,
                D("1000"), D("1000"), D("0"), D("100"), basis=candidate))
        output, result = await self.observe(report)
        self.assertTrue(result.reconciled)
        self.assertFalse(result.trade_authorized)
        self.assertEqual(result.report_content_digest, output["content_digest"])
        self.assertEqual(self.supervisor.risk_state.health, "HEALTHY")
        self.assertEqual(output["risk_period_summary"]["label"], "風控期間損益")
        self.assertFalse(output["risk_period_summary"]["full_day"])
        self.assertEqual(output["risk_period_start_ms"], MIDNIGHT + 36_001_010)
        await self.supervisor.close()
        self.supervisor = await self.open_supervisor()
        self.assertEqual(self.supervisor.risk_state.basis, candidate)
        self.assertEqual(self.supervisor.risk_state.basis_established_day, candidate.day)
        self.clock.now += 1000
        later = report_at(36_001_000, value="900")
        await self.observe(later)
        self.assertEqual(self.supervisor.risk_state.basis.equity, D("1000"))
        self.assertEqual(self.supervisor.risk_state.mode, "NO_INCREASE")

    async def test_initial_failure_is_retryable_and_does_not_latch_entire_day(self):
        absent = risk.Snapshot(1, self.clock.now - 50, self.clock.now + 1000,
            D("1000"), D("1000"), D("0"), D("100"), valuation_known=False)
        self.supervisor.observe_risk(absent)
        await self.supervisor.persist_controls()
        self.assertIsNone(self.supervisor.risk_state.basis_blocked_day)
        self.assertIsNone(await risk_period.durable_ledger(self.supervisor, report_at(), CLASSIFICATIONS))
        with self.assertRaises(JournalError):
            await self.prepare(report_at(issues=("incomplete_collection",)))
        self.assertIsNone(await self.supervisor.load_day_basis(risk.taipei_day(self.clock.now)))
        self.assertTrue((await self.prepare())[2].reconciled)

    async def test_wrong_account_environment_old_day_and_stale_report_rejected(self):
        for changes in (dict(account_alias="other"), dict(environment="demo")):
            report = report_at()
            report.update(changes)
            with self.assertRaises(ValueError):
                await self.prepare(risk_period.seal(report))
        self.clock.now += risk.DAY_MS
        with self.assertRaises(JournalError):
            await self.prepare(report_at())
        self.clock.now -= risk.DAY_MS - 1000
        with self.assertRaisesRegex(JournalError, "snapshot_freshness"):
            await self.prepare()

    async def test_replacement_and_unqualified_direct_commit_are_rejected(self):
        basis = risk_period.candidate(report_at(), "r1-fixture")
        with self.assertRaisesRegex(JournalError, "qualified"):
            await self.supervisor.commit_day_basis(basis)
        await self.prepare()
        await self.supervisor.commit_day_basis(basis)  # Exact durable replay only.
        different = risk_period.candidate(report_at(value="1100"), "r1-fixture")
        with self.assertRaisesRegex(JournalError, "fixed"):
            await self.supervisor.commit_day_basis(different)

    async def test_missing_persisted_basis_marker_requires_recovery(self):
        await self.prepare()
        def corrupt():
            journal = self.supervisor._journal
            with journal._transaction():
                journal._write_risk(replace(journal.risk_state(), basis=None))
        await self.supervisor._io(corrupt)
        await self.supervisor.close()
        self.supervisor = await self.open_supervisor()
        with self.assertRaisesRegex(JournalError, "recovery"):
            await self.prepare()

    async def test_commit_rollback_never_exposes_success_and_can_retry(self):
        with patch.object(self.supervisor._journal, "_commit", side_effect=sqlite3.OperationalError("fixture disk failure")):
            with self.assertRaises(sqlite3.OperationalError):
                await self.prepare()
        self.assertIsNone(self.supervisor.risk_state.basis)
        self.assertIsNone(await self.supervisor._io(self.supervisor._journal.load_day_basis,
            risk.taipei_day(self.clock.now)))
        with self.assertRaises(SupervisorUnavailable):
            await self.prepare()
        await self.supervisor.close()
        self.supervisor = await self.open_supervisor()
        self.assertTrue((await self.prepare())[2].reconciled)

    async def test_commit_acknowledgement_loss_returns_no_success_restart_reuses_basis(self):
        real = self.supervisor._journal._commit
        entered, release = threading.Event(), threading.Event()
        def commit_then_fail():
            real()
            entered.set()
            if not release.wait(5):
                raise RuntimeError("fixture wait timeout")
            raise sqlite3.OperationalError("fixture lost commit acknowledgement")
        with patch.object(self.supervisor._journal, "_commit", side_effect=commit_then_fail):
            task = asyncio.create_task(self.prepare())
            await wait_flag(entered)
            self.supervisor.latch("manual_kill")
            release.set()
            with self.assertRaises(sqlite3.OperationalError):
                await task
        self.assertEqual(self.supervisor.risk_state.health, "DEGRADED")
        with self.assertRaises(SupervisorUnavailable):
            await self.prepare()
        await self.supervisor.close()
        self.supervisor = await self.open_supervisor()
        self.assertEqual(self.supervisor.risk_state.basis.equity, D("1000"))
        self.assertIn("manual_kill", self.supervisor.risk_state.reasons)
        self.assertTrue((await self.prepare())[2].reconciled)

    async def test_latch_arriving_while_commit_waits_is_preserved(self):
        entered, release = threading.Event(), threading.Event()
        real = self.supervisor._journal.commit_day_basis
        def delayed(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("fixture wait timeout")
            return real(*args)
        with patch.object(self.supervisor._journal, "commit_day_basis", side_effect=delayed):
            task = asyncio.create_task(self.prepare())
            await wait_flag(entered)
            self.supervisor.latch("manual_kill")
            release.set()
            await task
        self.assertEqual(self.supervisor.risk_state.mode, "FLAT")
        stored = await self.supervisor._io(self.supervisor._journal.risk_state)
        self.assertIn("manual_kill", stored.reasons)

    async def test_new_day_retries_preserves_all_latches_and_disallows_old_period(self):
        await self.observe(report_at())
        for reason in risk.HALTS:
            self.supervisor.latch(reason)
        await self.supervisor.persist_controls()
        old_basis = self.supervisor.risk_state.basis
        next_report = report_at(36_000_000 + risk.DAY_MS)
        self.clock.now = next_report["completed_ms"] + 50
        self.supervisor.risk_timer(self.clock.now)
        self.assertEqual(self.supervisor.risk_state.health, "DEGRADED")
        with self.assertRaises(JournalError):
            await self.prepare(report_at(36_000_000 + risk.DAY_MS, issues=("incomplete_collection",)))
        await self.observe(next_report)
        self.assertNotEqual(self.supervisor.risk_state.basis.day, old_basis.day)
        self.assertEqual(self.supervisor.risk_state.reasons, risk.HALTS)
        self.assertEqual(self.supervisor.risk_state.mode, "FLAT")

    async def test_period_flows_before_after_duplicates_deposit_does_not_reset_budget(self):
        await self.observe(report_at())
        start = self.supervisor.risk_state.basis.evidence.observed_at_ms
        post = bill("post", start + 500)
        later = report_at(36_001_000, value="1000", facts=(bill("before", start - 1, "300"), post, post))
        self.clock.now = later["completed_ms"] + 50
        output, result = await self.observe(later)
        self.assertTrue(result.reconciled)
        self.assertEqual(output["day_external_flow_usdt"], "100")
        self.assertEqual(output["risk_period_summary"]["pnl_usdt"], "-100")
        self.assertEqual(self.supervisor.risk_state.mode, "NO_INCREASE")
        provider = await risk_period.durable_ledger(self.supervisor, later, CLASSIFICATIONS)
        self.assertEqual(provider[1].external_flow_usdt, D("100"))

    async def test_boundary_bill_requires_exact_basis_reference(self):
        await self.prepare()
        basis = self.supervisor.risk_state.basis
        for timing, ref, expected in ((None, None, None), ("after_baseline", "wrong", None),
                ("prior_to_baseline", basis.evidence_id, "0"), ("after_baseline", basis.evidence_id, "100")):
            row = bill("edge", basis.evidence.observed_at_ms)
            if timing:
                row.update(timing_verified=timing, timing_evidence_id=ref)
            report = report_at(facts=(row,))
            projected, ledger, result = await self.prepare(report)
            self.assertEqual(projected["day_external_flow_usdt"], expected)
            self.assertEqual(result.reconciled, expected is not None)
        conflict = bill("edge", basis.evidence.observed_at_ms + 1)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            risk_period.project(report_at(facts=(conflict, conflict | {"ts": conflict["ts"] + 1})), basis, CLASSIFICATIONS)

    async def test_actual_gate_blockers_are_not_relaxed_by_r1_or_lot_reporting(self):
        await self.prepare()
        expected = {"foreign_order": "foreign_order", "local_unknown": "local_unknown",
            "fill_totals_unavailable": "fill_reconciliation_failed",
            "p6_triggered_not_reconciled": "p6_triggered_not_reconciled"}
        for issue, blocker in expected.items():
            result = (await self.prepare(report_at(issues=(issue,))))[2]
            self.assertFalse(result.reconciled)
            self.assertIn(blocker, result.blockers)
        report = report_at()
        report["lot_reporting"] = {"missing_fee": True}
        self.assertTrue((await self.prepare(risk_period.seal(report)))[2].reconciled)

    async def test_wrong_flow_period_keeps_risk_degraded_and_cannot_fake_loss(self):
        await self.observe(report_at())
        state = self.supervisor.risk_state
        bad = replace(state.snapshot, seq=state.seq + 1, equity=D("1"), flow_basis_id="wrong")
        result = self.supervisor.observe_risk(bad)
        self.assertEqual(result.health, "DEGRADED")
        self.assertEqual(result.reasons, frozenset())

    async def test_nonpositive_current_equity_triggers_hard_without_resetting_basis(self):
        await self.observe(report_at())
        for offset, value in ((36_001_000, "0"), (36_002_000, "-1")):
            report = report_at(offset, value=value)
            self.clock.now = report["completed_ms"] + 50
            output, result = await self.observe(report)
            self.assertTrue(result.reconciled)
            self.assertIn("hard_loss", self.supervisor.risk_state.reasons)
            self.assertEqual(self.supervisor.risk_state.mode, "FLAT")
            self.assertEqual(output["risk_period_summary"]["baseline_equity_usdt"], "1000")

    async def test_withdrawals_are_excluded_from_loss_only_after_period_start(self):
        await self.observe(report_at())
        start = self.supervisor.risk_state.basis.evidence.observed_at_ms
        report = report_at(36_001_000, value="850", facts=(
            bill("old-withdrawal", start - 1, "-250"), bill("withdrawal", start + 500, "-150")))
        self.clock.now = report["completed_ms"] + 50
        output, result = await self.observe(report)
        self.assertTrue(result.reconciled)
        self.assertEqual(output["day_external_flow_usdt"], "-150")
        self.assertEqual(output["risk_period_summary"]["pnl_usdt"], "0")
        self.assertEqual(self.supervisor.risk_state.health, "HEALTHY")
        self.assertEqual(self.supervisor.risk_state.reasons, frozenset())

    async def test_unknown_forbidden_and_non_usdt_flows_remain_blocking(self):
        await self.prepare()
        start = self.supervisor.risk_state.basis.evidence.observed_at_ms
        for changes in ({"type": "9"}, {"type": "3", "subType": "3"}, {"ccy": "BTC"}):
            # Unsupported activity also blocks when it precedes the new baseline.
            for stamp in (start - 1, start + 1):
                report = report_at(facts=(bill("unsupported", stamp) | changes,))
                self.assertFalse((await self.prepare(report))[2].reconciled)

    async def test_digest_tampering_and_incomplete_period_window_cannot_restore_health(self):
        await self.observe(report_at())
        report = report_at()
        report["facts"][0]["details"][0]["eq"] = "5000"
        with self.assertRaises(ValueError):
            await self.prepare(report)
        report = report_at()
        report["window_start_ms"] = self.supervisor.risk_state.basis.evidence.observed_at_ms + 1
        result = (await self.prepare(risk_period.seal(report)))[2]
        self.assertFalse(result.reconciled)
        self.assertEqual(self.supervisor.risk_state.health, "DEGRADED")

    async def test_legacy_same_day_execution_responsibility_cannot_create_fresh_basis(self):
        # A legacy/crash fixture lacks both the new marker and a basis.
        def seed_legacy_responsibility():
            journal = self.supervisor._journal
            with journal._transaction():
                journal.connection.execute("""INSERT INTO inputs
                    (bot_id,seq,input_json,input_hash,before_json,state) VALUES (?,?,?,?,?,'PENDING')""",
                    ("bot", 1, json.dumps({"payload": {"account": {"time_ms": self.clock.now}}}),
                     "fixture-hash", "{}"))
                journal.connection.execute("INSERT INTO intents VALUES (?,?,?,0,?,?,?,?)",
                    ("legacy", "bot", 1, "1", "RESERVED_SIMULATION", "fixture", 0))
        await self.supervisor._io(seed_legacy_responsibility)
        with self.assertRaisesRegex(JournalError, "execution responsibility"):
            await self.prepare()
        self.assertIsNone(self.supervisor.risk_state.basis)

    async def test_corrupt_existing_basis_is_rejected_instead_of_replaced(self):
        await self.prepare()
        def corrupt():
            journal = self.supervisor._journal
            with journal._transaction():
                state = journal.risk_state()
                journal._write_risk(replace(state, basis=replace(state.basis, digest="0" * 64)))
        await self.supervisor._io(corrupt)
        await self.supervisor.close()
        self.supervisor = await self.open_supervisor()
        with self.assertRaisesRegex(ValueError, "verified"):
            await self.prepare()

    async def test_held_position_across_midnight_requires_new_period_and_keeps_reductions(self):
        position = D("10")
        def seed_owned_position():
            # Pre-existing attributed local position, not permission to adopt a remote one.
            journal = self.supervisor._journal
            with journal._transaction():
                journal.connection.execute("UPDATE ownership SET position='10',remote_pos_id=? WHERE bot_id='bot'",
                    ("synthetic-position",))
        await self.supervisor._io(seed_owned_position)
        await self.supervisor.reconcile(proof(self.supervisor.revision,
            position=position, attributed_bot_id="bot"))
        facts = (dict(kind="position", instId=config().contract.inst_id,
                      posId="synthetic-position", pos="10"),)
        await self.observe(report_at(facts=facts), position=position)
        old_basis = self.supervisor.risk_state.basis
        self.assertTrue(risk.evaluate(self.supervisor.risk_state, risk.Limits(), config().contract,
            D("11"), position, self.clock.now, reconciled=True).accepted)
        next_report = report_at(36_000_000 + risk.DAY_MS, facts=facts)
        self.clock.now = next_report["completed_ms"] + 50
        self.supervisor.risk_timer(self.clock.now)
        current_position = replace(self.supervisor.risk_state.snapshot,
            seq=self.supervisor.risk_state.seq + 1, time_ms=self.clock.now,
            valid_until_ms=self.clock.now + 1000, basis=None, flow_basis_id=None, flow_start_ms=None)
        self.supervisor.observe_risk(current_position)
        for target, accepted in (("11", False), ("5", True), ("0", True)):
            verdict = risk.evaluate(self.supervisor.risk_state, risk.Limits(), config().contract,
                D(target), position, self.clock.now, reconciled=True)
            self.assertEqual(verdict.accepted, accepted)
        await self.observe(next_report, position=position)
        self.assertNotEqual(self.supervisor.risk_state.basis.day, old_basis.day)
        self.assertTrue(risk.evaluate(self.supervisor.risk_state, risk.Limits(), config().contract,
            D("11"), position, self.clock.now, reconciled=True).accepted)

    async def test_caller_mutation_during_commit_cannot_change_qualified_equity(self):
        report = report_at()
        entered, release = threading.Event(), threading.Event()
        real = self.supervisor._journal.commit_day_basis
        def delayed(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("fixture wait timeout")
            return real(*args)
        with patch.object(self.supervisor._journal, "commit_day_basis", side_effect=delayed):
            task = asyncio.create_task(self.observe(report))
            await wait_flag(entered)
            report["facts"][0]["details"][0]["eq"] = "5000"
            release.set()
            output, result = await task
        self.assertTrue(result.reconciled)
        self.assertEqual(result.report_content_digest, output["content_digest"])
        self.assertEqual(self.supervisor.risk_state.snapshot.equity, D("1000"))
        self.assertEqual(output["risk_period_summary"]["pnl_usdt"], "0")


if __name__ == "__main__":
    unittest.main()
