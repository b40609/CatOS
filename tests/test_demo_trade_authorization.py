"""Local-only T1-A/T2-A/T3-A Demo write-grant acceptance tests."""

import asyncio
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catos import account_lock, risk
from catos.fake_exchange import FakeExchange, Fill
from catos.journal import canonical
from catos.supervisor import LocalSupervisor, SupervisorUnavailable
from catos.trade_authorization import DemoTradeGrant
from test_execution import report
from test_ipc import STEP, account, bar, config
from test_journal import proof
from test_risk import snapshot


D = Decimal


class FakeClock:
    def __init__(self, current_ms):
        self.current_ms = current_ms

    def wall_ms(self):
        return self.current_ms

    def advance(self, delta_ms):
        self.current_ms += delta_ms
        return self.current_ms


class DemoTradeAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state.sqlite3"
        lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", Path(directory.name) / "locks")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)
        self.exchange = FakeExchange("fake-account")
        self.clock = FakeClock(3 * STEP)
        self.s = self.make()
        self.addAsyncCleanup(self.cleanup)
        await self.s.start()
        await self.reconcile()
        self.observe()
        for index in range(3):
            receipt = await self.s.process_bar(
                index + 1,
                bar(index, "101" if index == 2 else "100"),
                None if index < 2 else account(index),
                expires_at_ms=(index + 2) * STEP,
                now_ms=(index + 1) * STEP,
            )
        self.key = receipt.intent_key

    def make(self):
        return LocalSupervisor(
            self.path,
            account_id="fake-account",
            bot_id="bot",
            config=config(),
            fixture_budget=D("100"),
            risk_limits=risk.Limits(),
            exchange=self.exchange,
            day_clock=self.clock,
            require_demo_trade_grant=True,
        )

    async def cleanup(self):
        if self.s is not None:
            await self.s.close()

    async def reconcile(self, **changes):
        await self.s.reconcile(proof(self.s.revision, **changes))

    def observe(self, **changes):
        return self.s.observe_risk(
            snapshot(self.s.risk_state.seq + 1, 3 * STEP, valid_until_ms=10 * STEP, **changes))

    async def grant(self, *, authorization_id="grant1", starts_at_ms=None,
                    entry_cutoff_ms=None, max_entry_mark_notional_usdt=D("100")):
        stored = await self.s._io(self.s._journal.snapshot, "bot")
        owner = stored["owner"]
        return DemoTradeGrant(
            authorization_id=authorization_id,
            account_id="fake-account",
            bot_id="bot",
            inst_id=config().contract.inst_id,
            reconciliation_evidence_id=owner["evidence_id"],
            bot_revision=owner["reconciled_revision"],
            starts_at_ms=self.clock.wall_ms() if starts_at_ms is None else starts_at_ms,
            entry_cutoff_ms=(self.clock.wall_ms() + STEP
                             if entry_cutoff_ms is None else entry_cutoff_ms),
            max_entry_mark_notional_usdt=max_entry_mark_notional_usdt,
        )

    async def test_reconciliation_without_grant_never_calls_exchange(self):
        with self.assertRaisesRegex(SupervisorUnavailable, "demo_trade_grant_required"):
            await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(self.exchange.calls, [])

    async def test_mark_notional_exact_limit_allows_existing_risk_approved_entry(self):
        await self.s.authorize_demo_trading(
            await self.grant(max_entry_mark_notional_usdt=D("2")))
        self.exchange.enqueue("submit", report(self.key))
        result = await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(result["state"], "LIVE")
        self.assertEqual([op for op, _ in self.exchange.calls], ["submit"])

    async def test_mark_notional_over_limit_rejects_before_transport(self):
        await self.s.authorize_demo_trading(
            await self.grant(max_entry_mark_notional_usdt=D("1.999999999999999999")))
        with self.assertRaisesRegex(SupervisorUnavailable, "limit_exceeded"):
            await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(self.exchange.calls, [])
        row = await self.s._io(self.s._journal.execution.order, self.key)
        self.assertEqual(row["state"], "ABORTED")

    async def test_new_mark_revalues_entry_instead_of_trusting_old_reservation(self):
        self.assertEqual(self.s.total_reserved, D("2"))
        await self.s.authorize_demo_trading(
            await self.grant(max_entry_mark_notional_usdt=D("3")))
        self.observe(mark=D("200"))
        with self.assertRaisesRegex(SupervisorUnavailable, "limit_exceeded"):
            await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(self.exchange.calls, [])
        row = await self.s._io(self.s._journal.execution.order, self.key)
        self.assertEqual(row["state"], "ABORTED")

    async def test_scope_stale_and_time_fail_closed_before_transport(self):
        bad_scope = await self.grant()
        bad_scope = DemoTradeGrant(
            authorization_id="scope1",
            account_id="other-account",
            bot_id=bad_scope.bot_id,
            inst_id=bad_scope.inst_id,
            reconciliation_evidence_id=bad_scope.reconciliation_evidence_id,
            bot_revision=bad_scope.bot_revision,
            starts_at_ms=bad_scope.starts_at_ms,
            entry_cutoff_ms=bad_scope.entry_cutoff_ms,
            max_entry_mark_notional_usdt=bad_scope.max_entry_mark_notional_usdt,
        )
        with self.assertRaisesRegex(SupervisorUnavailable, "scope_mismatch"):
            await self.s.authorize_demo_trading(bad_scope)

        good = await self.grant(authorization_id="exp1", entry_cutoff_ms=self.clock.wall_ms())
        await self.s.authorize_demo_trading(good)
        self.clock.advance(1)
        with self.assertRaisesRegex(SupervisorUnavailable, "expired"):
            await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(self.exchange.calls, [])

        self.clock.current_ms = 3 * STEP
        await self.reconcile(evidence_id="new-evidence")
        with self.assertRaisesRegex(SupervisorUnavailable, "stale_reconciliation"):
            await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(self.exchange.calls, [])

    async def test_entry_cutoff_does_not_block_reduce_only_flatten_cleanup(self):
        grant = await self.grant(entry_cutoff_ms=self.clock.wall_ms())
        await self.s.authorize_demo_trading(grant)
        self.exchange.enqueue(
            "submit",
            report(self.key, status="FILLED",
                   fills=(Fill("entry", D("2"), D("100")),), complete=True),
        )
        await self.s.dispatch(self.key, now_ms=3 * STEP)
        await self.reconcile(position=D("2"), attributed_bot_id="bot", remote_position_id="pos1")
        self.observe(position=D("2"), equity=D("800"))
        flatten_id = self.s.risk_state.flatten_id
        child = canonical(dict(
            kind="flatten", account_id="fake-account", bot_id="bot",
            flatten_id=flatten_id, child=0))
        self.clock.advance(1)
        self.exchange.enqueue(
            "submit",
            report(child, status="FILLED",
                   fills=(Fill("exit", D("2"), D("99")),), complete=True),
        )
        await self.s.flatten_step(now_ms=3 * STEP, expires_at_ms=4 * STEP)
        payloads = [payload for operation, payload in self.exchange.calls if operation == "submit"]
        self.assertEqual([payload["reduceOnly"] for payload in payloads], [False, True])

    async def test_cutoff_crossing_after_prepare_aborts_unsent_before_transport(self):
        await self.s.authorize_demo_trading(
            await self.grant(entry_cutoff_ms=self.clock.wall_ms()))
        original = self.s._journal.execution.prepare

        def prepare_then_expire(*args):
            request = original(*args)
            self.clock.advance(1)
            return request

        with patch.object(self.s._journal.execution, "prepare", side_effect=prepare_then_expire):
            with self.assertRaisesRegex(SupervisorUnavailable, "expired_or_changed"):
                await self.s.dispatch(self.key, now_ms=3 * STEP)
        row = await self.s._io(self.s._journal.execution.order, self.key)
        self.assertEqual(row["state"], "ABORTED")
        self.assertEqual(self.exchange.calls, [])
        self.assertEqual(self.s.total_reserved, D("0"))

    async def test_restart_never_restores_entry_permission(self):
        await self.s.authorize_demo_trading(await self.grant())
        await self.s.close()
        self.s = self.make()
        await self.s.start()
        await self.reconcile()
        self.observe()
        with self.assertRaisesRegex(SupervisorUnavailable, "demo_trade_grant_required"):
            await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(self.exchange.calls, [])

    async def test_expiry_during_handoff_scheduling_never_sends(self):
        await self.s.authorize_demo_trading(
            await self.grant(entry_cutoff_ms=self.clock.wall_ms()))
        self.exchange.enqueue("submit", report(self.key))
        original = asyncio.wait_for

        async def delayed_handoff(coro, *args, **kwargs):
            if getattr(coro, "__name__", "") == "handoff":
                self.clock.advance(1)
            return await original(coro, *args, **kwargs)

        with patch("catos.supervisor.asyncio.wait_for", side_effect=delayed_handoff):
            with self.assertRaisesRegex(SupervisorUnavailable, "expired_or_changed"):
                await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(self.exchange.calls, [])
        row = await self.s._io(self.s._journal.execution.order, self.key)
        self.assertEqual(row["state"], "ABORTED")

    async def test_risk_snapshot_change_during_handoff_aborts_without_consuming_grant(self):
        await self.s.authorize_demo_trading(
            await self.grant(max_entry_mark_notional_usdt=D("10")))
        original = asyncio.wait_for

        async def changed_handoff(coro, *args, **kwargs):
            if getattr(coro, "__name__", "") == "handoff":
                self.observe(mark=D("101"))
            return await original(coro, *args, **kwargs)

        with patch("catos.supervisor.asyncio.wait_for", side_effect=changed_handoff):
            with self.assertRaisesRegex(SupervisorUnavailable, "risk_snapshot_changed"):
                await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(self.exchange.calls, [])
        row = await self.s._io(self.s._journal.execution.order, self.key)
        self.assertEqual(row["state"], "ABORTED")
        self.assertNotIn("grant1", self.s._demo_consumed_authorization_ids)

        await self.reconcile()
        refreshed = await self.grant(
            authorization_id="grant1", max_entry_mark_notional_usdt=D("10"))
        await self.s.authorize_demo_trading(refreshed)
        self.assertEqual(self.s._demo_trade_grant, refreshed)

    async def test_revoke_while_prepare_waits_never_sends(self):
        await self.s.authorize_demo_trading(await self.grant())
        original = self.s._io
        reached, resume = asyncio.Event(), asyncio.Event()

        async def delayed_io(method, *args):
            result = await original(method, *args)
            if getattr(method, "__name__", "") == "prepare":
                reached.set()
                await resume.wait()
            return result

        with patch.object(self.s, "_io", side_effect=delayed_io):
            task = asyncio.create_task(self.s.dispatch(self.key, now_ms=3 * STEP))
            try:
                await asyncio.wait_for(reached.wait(), 3)
                await self.s.revoke_demo_trading()
            finally:
                resume.set()
                try:
                    await task
                except SupervisorUnavailable:
                    pass
        self.assertEqual(self.exchange.calls, [])
        row = await self.s._io(self.s._journal.execution.order, self.key)
        self.assertEqual(row["state"], "ABORTED")

    async def test_close_clears_grant_on_same_instance(self):
        await self.s.authorize_demo_trading(await self.grant())
        await self.s.close()
        self.assertIsNone(self.s._demo_trade_grant)

    async def test_rejected_transport_consumes_id_even_after_reconcile_and_revoke(self):
        await self.s.authorize_demo_trading(
            await self.grant(max_entry_mark_notional_usdt=D("2")))
        self.exchange.enqueue("submit", report(self.key, status="REJECTED", complete=True))
        result = await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(result["state"], "REJECTED")
        self.assertIn("grant1", self.s._demo_consumed_authorization_ids)

        await self.reconcile()
        replacement = await self.grant(
            authorization_id="grant1", max_entry_mark_notional_usdt=D("2"))
        await self.s.revoke_demo_trading()
        with self.assertRaisesRegex(SupervisorUnavailable, "grant_consumed"):
            await self.s.authorize_demo_trading(replacement)

    async def test_rejected_transport_consumed_id_survives_restart_without_restoring_grant(self):
        await self.s.authorize_demo_trading(
            await self.grant(max_entry_mark_notional_usdt=D("2")))
        self.exchange.enqueue("submit", report(self.key, status="REJECTED", complete=True))
        await self.s.dispatch(self.key, now_ms=3 * STEP)
        await self.s.close()

        self.s = self.make()
        await self.s.start()
        self.assertIsNone(self.s._demo_trade_grant)
        self.assertIn("grant1", self.s._demo_consumed_authorization_ids)
        await self.reconcile()
        self.observe()
        replacement = await self.grant(
            authorization_id="grant1", max_entry_mark_notional_usdt=D("2"))
        with self.assertRaisesRegex(SupervisorUnavailable, "grant_consumed"):
            await self.s.authorize_demo_trading(replacement)

    async def test_aborted_unsent_id_is_not_recovered_as_consumed_after_restart(self):
        await self.s.authorize_demo_trading(
            await self.grant(max_entry_mark_notional_usdt=D("1")))
        with self.assertRaisesRegex(SupervisorUnavailable, "limit_exceeded"):
            await self.s.dispatch(self.key, now_ms=3 * STEP)
        await self.s.close()

        self.s = self.make()
        await self.s.start()
        self.assertNotIn("grant1", self.s._demo_consumed_authorization_ids)
        await self.reconcile()
        self.observe()
        replacement = await self.grant(
            authorization_id="grant1", max_entry_mark_notional_usdt=D("2"))
        await self.s.authorize_demo_trading(replacement)
        self.assertEqual(self.s._demo_trade_grant, replacement)

    async def test_timeout_transport_consumes_id_and_revoke_does_not_restore_it(self):
        grant = await self.grant(max_entry_mark_notional_usdt=D("2"))
        await self.s.authorize_demo_trading(grant)
        result = await self.s.dispatch(self.key, now_ms=3 * STEP)
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertIn("grant1", self.s._demo_consumed_authorization_ids)

        await self.s.revoke_demo_trading()
        with self.assertRaisesRegex(SupervisorUnavailable, "grant_consumed"):
            await self.s.authorize_demo_trading(grant)

    async def test_revoke_during_authorization_cannot_reinstall_grant(self):
        grant = await self.grant()
        original = self.s._io

        async def revoke_after_read(method, *args):
            result = await original(method, *args)
            if getattr(method, "__name__", "") == "snapshot":
                await self.s.revoke_demo_trading()
            return result

        with patch.object(self.s, "_io", side_effect=revoke_after_read):
            with self.assertRaisesRegex(SupervisorUnavailable, "revoked_during_authorization"):
                await self.s.authorize_demo_trading(grant)
        self.assertIsNone(self.s._demo_trade_grant)


if __name__ == "__main__":
    unittest.main()
