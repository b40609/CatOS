"""G transport orchestration against memory-only scripted exchange."""

import asyncio
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from catos import account_lock, risk
from catos.fake_exchange import FakeExchange, Fill, Report, TAG
from catos.journal import JournalError, OwnershipError, canonical
from catos.supervisor import LocalSupervisor, SupervisorUnavailable
from test_ipc import STEP, account, bar, config
from test_journal import proof
from test_risk import snapshot
from test_execution import report

D = Decimal


class ExecutionSupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state.sqlite3"
        lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", Path(directory.name) / "locks")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)
        self.exchange = FakeExchange("fake-account")
        self.s = self.make()
        self.addAsyncCleanup(self.cleanup)
        await self.s.start()
        await self.reconcile()
        self.observe()
        for index in range(3):
            receipt = await self.s.process_bar(index + 1, bar(index, "101" if index == 2 else "100"),
                None if index < 2 else account(index), expires_at_ms=(index + 2) * STEP, now_ms=(index + 1) * STEP)
        self.key = receipt.intent_key

    def make(self, **kwargs):
        return LocalSupervisor(self.path, account_id="fake-account", bot_id="bot", config=config(),
            fixture_budget=D("100"), risk_limits=risk.Limits(), exchange=self.exchange, **kwargs)

    async def cleanup(self):
        if self.s is not None:
            await self.s.close()

    async def reconcile(self, **changes):
        await self.s.reconcile(proof(self.s.revision, **changes))

    def observe(self, **changes):
        return self.s.observe_risk(snapshot(self.s.risk_state.seq + 1, 3 * STEP, valid_until_ms=10 * STEP, **changes))

    async def test_rearm_does_not_revive_old_intent_and_new_intent_can_dispatch(self):
        self.observe(equity=D("900"))
        self.observe()
        await self.s.persist_controls()
        with self.assertRaises(SupervisorUnavailable):
            await self.s.rearm(now_ms=3 * STEP, actor="operator", evidence_id="blocked-held")
        # Explicit control tick retires never-sent work; re-arm cannot do that.
        await self.s.control_step(now_ms=3 * STEP, expires_at_ms=4 * STEP)
        await self.reconcile()
        await self.s.rearm(now_ms=3 * STEP, actor="operator", evidence_id="reconciled")
        self.assertIsNone(await self.s.dispatch(self.key, now_ms=3 * STEP))
        receipt = await self.s.process_bar(4, bar(3, "102"), account(3),
            expires_at_ms=5 * STEP, now_ms=4 * STEP)
        self.assertEqual(receipt.reason, "exposure_reserved")
        self.exchange.enqueue("submit", report(receipt.intent_key))
        await self.s.dispatch(receipt.intent_key, now_ms=4 * STEP)
        self.assertEqual(sum(op == "submit" for op, _ in self.exchange.calls), 1)

    async def test_ack_lost_query_fill_restart_and_no_resubmit(self):
        self.exchange.enqueue("submit", TimeoutError("accepted but ACK lost"))
        first = await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(first["state"], "UNKNOWN")
        self.assertEqual(self.s.total_reserved, D("2"))
        await self.s.close()
        self.s = self.make()
        await self.s.start()
        with self.assertRaises(OwnershipError):
            await self.reconcile()
        self.exchange.enqueue("query", report(self.key, status="FILLED", fills=(Fill("fill1", D("2"), D("101")),), complete=True))
        await self.s.query_order(self.key)
        await self.reconcile(position=D("2"), attributed_bot_id="bot")
        self.observe(position=D("2"))
        self.assertIsNone(await self.s.dispatch(self.key, now_ms=3 * STEP))
        self.assertEqual(sum(op == "submit" for op, _ in self.exchange.calls), 1)
        self.assertEqual(self.s.total_reserved, 0)

    async def test_kill_while_submit_commit_waits_never_calls_transport(self):
        entered, release = threading.Event(), threading.Event()
        original = self.s._journal._commit

        def delayed():
            has_order = self.s._journal.connection.execute("SELECT 1 FROM execution_orders").fetchone()
            if has_order and not entered.is_set():
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test release timeout")
            original()

        with patch.object(self.s._journal, "_commit", delayed):
            task = asyncio.create_task(self.s.dispatch(self.key, now_ms=3 * STEP))
            try:
                self.assertTrue(await asyncio.to_thread(entered.wait, 3))
                self.s.latch("manual_kill")
            finally:
                release.set()
            result = await asyncio.wait_for(task, 5)
        self.assertEqual(result["state"], "ABORTED")
        self.assertEqual(self.exchange.calls, [])
        self.assertEqual(self.s.total_reserved, 0)

    async def test_submit_commit_failure_never_calls_transport(self):
        await self.s.persist_controls()
        with patch.object(self.s._journal, "_commit", side_effect=sqlite3.OperationalError("synthetic disk failure")):
            with self.assertRaises(sqlite3.OperationalError):
                await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(self.exchange.calls, [])
        self.assertEqual(self.s.total_reserved, D("2"))

    async def test_kill_after_handoff_keeps_flatten_working_and_reservation(self):
        entered, release = asyncio.Event(), asyncio.Event()
        self.exchange.enqueue("submit", report(self.key))
        original = self.exchange.submit

        async def delayed(payload):
            reply = await original(payload)
            entered.set()
            await release.wait()
            return reply

        with patch.object(self.exchange, "submit", delayed):
            task = asyncio.create_task(self.s.dispatch(self.key, now_ms=3 * STEP))
            try:
                await asyncio.wait_for(entered.wait(), 3)
                self.s.latch("manual_kill")
            finally:
                release.set()
            await asyncio.wait_for(task, 5)
        self.assertEqual((self.s.risk_state.mode, self.s.risk_state.phase), ("FLAT", "WORKING"))
        stored = await self.s._io(self.s._journal.risk_state)
        self.assertEqual(stored, self.s.risk_state)
        self.assertEqual(self.s.total_reserved, D("2"))

    async def test_query_not_found_keeps_unknown_without_new_submit(self):
        await self.s.dispatch(self.key, now_ms=3 * STEP)
        row = await self.s._io(self.s._journal.execution.order, self.key)
        self.exchange.enqueue("query", Report(row["cl_ord_id"], None, 1, "NOT_FOUND"))
        result = await self.s.query_order(self.key)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(self.s.total_reserved, D("2"))
        self.assertIsNone(await self.s.dispatch(self.key, now_ms=3 * STEP))

    async def test_soft_control_tick_cancels_increase_and_keeps_latch(self):
        self.exchange.enqueue("submit", report(self.key))
        await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.observe(equity=D("900"))
        self.exchange.enqueue("cancel", report(self.key, 2, "CANCELED", complete=True))
        await self.s.control_step(now_ms=3 * STEP, expires_at_ms=4 * STEP)
        self.assertEqual(self.s.risk_state.mode, "NO_INCREASE")
        self.assertEqual(self.s.total_reserved, 0)
        self.assertEqual([op for op, _ in self.exchange.calls], ["submit", "cancel"])

    async def test_kill_entry_fill_reduce_and_verify_done(self):
        self.exchange.enqueue("submit", report(self.key, status="FILLED", fills=(Fill("entry", D("2"), D("100")),), complete=True))
        await self.s.dispatch(self.key, now_ms=3 * STEP)
        await self.reconcile(position=D("2"), attributed_bot_id="bot")
        self.observe(position=D("2"), equity=D("800"))
        op = self.s.risk_state.flatten_id
        child = canonical(dict(kind="flatten", account_id="fake-account", bot_id="bot", flatten_id=op, child=0))
        self.exchange.enqueue("submit", report(child, status="FILLED", fills=(Fill("exit", D("2"), D("99")),), complete=True))
        await self.s.flatten_step(now_ms=3 * STEP, expires_at_ms=4 * STEP)
        await self.reconcile()
        self.observe(equity=D("800"))
        await self.s.flatten_step(now_ms=3 * STEP, expires_at_ms=4 * STEP)
        await self.s.flatten_progress("DONE", now_ms=3 * STEP)
        self.assertEqual((self.s.risk_state.mode, self.s.risk_state.phase, self.s.risk_state.flatten_id), ("FLAT", "DONE", op))
        payloads = [payload for operation, payload in self.exchange.calls if operation == "submit"]
        self.assertEqual([p["reduceOnly"] for p in payloads], [False, True])
        self.assertTrue(all(p["tag"] == TAG for p in payloads))
        await self.s.release_contract()

    async def test_cannot_inject_live_client_or_disable_execution_on_restart(self):
        with self.assertRaises(SupervisorUnavailable):
            LocalSupervisor(self.path, account_id="fake-account", bot_id="bot", config=config(),
                fixture_budget=D("100"), risk_limits=risk.Limits(), exchange=object())
        await self.s.close()
        self.s = None
        disabled = LocalSupervisor(self.path, account_id="fake-account", bot_id="bot", config=config(),
                fixture_budget=D("100"), risk_limits=risk.Limits())
        with self.assertRaisesRegex(JournalError, "cannot be disabled"):
            await disabled.start()


if __name__ == "__main__":
    unittest.main()
