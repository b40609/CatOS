"""Independent synthetic risk events while Worker or the one writer is waiting."""

import asyncio
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from catos import account_lock, risk
from catos.journal import FixtureDecision
from catos.supervisor import LocalSupervisor, SupervisorBusy, SupervisorUnavailable
from test_ipc import STEP, account, bar, config
from test_journal import proof
from test_risk import snapshot

D = Decimal


class RiskSupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state.sqlite3"
        self.lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", Path(directory.name) / "locks")
        self.lock_patch.start()
        self.addCleanup(self.lock_patch.stop)
        self.supervisor = self.make_supervisor()
        self.addAsyncCleanup(self.cleanup)
        await self.supervisor.start()
        await self.supervisor.reconcile(proof(0))
        self.observe()
        await self.supervisor.persist_controls()
        await self.event(0)
        await self.event(1)

    def make_supervisor(self):
        return LocalSupervisor(self.path, account_id="fake-account", bot_id="bot", config=config(),
                               fixture_budget=D("100"), risk_limits=risk.Limits())

    async def cleanup(self):
        if self.supervisor is not None:
            await self.supervisor.close()

    def observe(self, **changes):
        state = self.supervisor.risk_state
        return self.supervisor.observe_risk(snapshot(state.seq + 1, 3 * STEP, valid_until_ms=20 * STEP, **changes))

    async def event(self, index):
        return await self.supervisor.process_bar(index + 1, bar(index, "101" if index >= 2 else "100"),
            None if index < 2 else account(index), expires_at_ms=(index + 2) * STEP, now_ms=(index + 1) * STEP)

    async def test_real_worker_risk_receipt_and_fixture_bypass_rejected(self):
        receipt = await self.event(2)
        self.assertEqual((receipt.reason, receipt.reservation), ("exposure_reserved", D("2")))
        self.assertEqual(self.supervisor._worker.checkpoint.event_seq, 3)
        with self.assertRaisesRegex(SupervisorUnavailable, "bypass"):
            await self.supervisor.process_bar(4, bar(3), account(3), expires_at_ms=5 * STEP,
                now_ms=4 * STEP, fixture=FixtureDecision(True, D("1")))

    async def test_crossing_then_bounce_during_worker_wait_is_not_lost(self):
        worker = self.supervisor._worker
        original = worker.process_bar
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed(*args):
            entered.set()
            await release.wait()
            return await original(*args)

        with patch.object(worker, "process_bar", delayed):
            task = asyncio.create_task(self.event(2))
            try:
                await asyncio.wait_for(entered.wait(), 2)
                self.observe(equity=D("950"))
                op = self.supervisor.risk_state.flatten_id
                self.observe(equity=D("1100"))
                self.assertEqual(self.supervisor.risk_state.mode, "FLAT")
            finally:
                release.set()
            receipt = await asyncio.wait_for(task, 5)
        self.assertEqual(receipt.reason, "increase_gate_closed")
        self.assertEqual(self.supervisor.risk_state.flatten_id, op)
        await self.supervisor.close()
        self.supervisor = self.make_supervisor()
        await self.supervisor.start()
        self.assertEqual((self.supervisor.risk_state.mode, self.supervisor.risk_state.flatten_id), ("FLAT", op))
        self.assertIsNone(self.supervisor.risk_state.snapshot)

    async def test_kill_during_commit_invalidates_outbox_before_return_and_keeps_amount(self):
        entered, release = threading.Event(), threading.Event()
        original = self.supervisor._journal._commit

        def delayed():
            seq = self.supervisor._journal.connection.execute("SELECT consumed_seq FROM bots").fetchone()[0]
            if seq == 3 and not entered.is_set():
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test writer release timeout")
            original()

        with patch.object(self.supervisor._journal, "_commit", delayed):
            task = asyncio.create_task(self.event(2))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                self.assertEqual(self.supervisor.pending_reservation, D("2"))
                self.supervisor.latch("manual_kill")
                self.assertEqual(self.supervisor.risk_state.mode, "FLAT")
                with self.assertRaises(SupervisorBusy):
                    await self.event(3)
            finally:
                release.set()
            receipt = await asyncio.wait_for(task, 5)
        self.assertEqual(receipt.disposition, "RESERVED_SIMULATION")
        row = await self.supervisor._io(lambda: tuple(self.supervisor._journal.connection.execute("SELECT eligible FROM risk_orders").fetchone()))
        self.assertEqual(row, (0,))
        self.assertEqual(self.supervisor.total_reserved, D("2"))

    async def test_failed_control_commit_is_not_reported_durable(self):
        self.observe(equity=D("950"))
        old = self.supervisor._risk_persisted
        with patch.object(self.supervisor._journal, "_commit", side_effect=sqlite3.OperationalError("synthetic full disk")):
            with self.assertRaises(sqlite3.OperationalError):
                await self.supervisor.persist_controls()
        self.assertEqual(self.supervisor._risk_persisted, old)
        self.assertEqual((self.supervisor.risk_state.mode, self.supervisor.risk_state.health), ("FLAT", "DEGRADED"))
        self.assertIsNotNone(self.supervisor.failure)
        # Storage recovery permits close to persist the known latch, not re-arm.

    async def test_timer_degrades_without_new_bar_and_persists(self):
        self.supervisor.risk_timer(20 * STEP)
        self.assertEqual(self.supervisor.risk_state.health, "DEGRADED")
        await self.supervisor.persist_controls()
        stored = await self.supervisor._io(self.supervisor._journal.risk_state)
        self.assertEqual(stored.health, "DEGRADED")


if __name__ == "__main__":
    unittest.main()
