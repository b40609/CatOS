"""Local synthetic acceptance for the first fail-closed strategy loop.

This test deliberately uses only FakeExchange, a temporary SQLite database, and
synthetic formal-reconciliation evidence.  It does not represent production
Demo identity, exact-midnight E0 provenance, or permission for OKX writes.
"""

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catos import account_lock, demo_ledger_binding, risk
from catos.fake_exchange import FakeExchange, Fill, TAG
from catos.journal import Journal
from catos.supervisor import LocalSupervisor, SupervisorUnavailable
from catos.trade_authorization import DemoTradeGrant
from test_demo_reconciliation import (
    FORMAL_ACCOUNT_ALIAS,
    FakeClock,
    SYNTHETIC_FLOW_CLASSIFICATION,
    SequentialSyntheticTransport,
    authorized_formal_scope,
    base_formal_rows,
    btc_config,
    build_formal_collection_plan,
    run_formal_reconciliation,
    synthetic_day_ledger,
)
from test_execution import report
from test_ipc import STEP, account, bar
from test_journal import proof
from test_risk import snapshot


D = Decimal


class SafeStrategyLoopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "state.sqlite3"
        lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)

        self.clock = FakeClock(1_700_000_000_000)
        self.day_clock = FakeClock(3 * STEP)
        self.exchange = FakeExchange(FORMAL_ACCOUNT_ALIAS)

        journal = Journal(self.path, FORMAL_ACCOUNT_ALIAS, D("100"), risk.Limits(), True)
        journal.register("bot", btc_config())
        journal.reconcile("bot", proof(0))
        journal.close()
        self.expected_uid_sha256 = demo_ledger_binding.uid_digest("123456789")
        self.ledger_binding = demo_ledger_binding.make_binding(
            account_alias=FORMAL_ACCOUNT_ALIAS,
            expected_uid_sha256=self.expected_uid_sha256,
            database_path=self.path,
        )

        self.supervisor = self._make_supervisor()
        self.addAsyncCleanup(self._cleanup)
        await self.supervisor.start()

    def _make_supervisor(self):
        return LocalSupervisor(
            self.path,
            account_id=FORMAL_ACCOUNT_ALIAS,
            bot_id="bot",
            config=btc_config(),
            fixture_budget=D("100"),
            risk_limits=risk.Limits(),
            exchange=self.exchange,
            day_clock=self.day_clock,
            require_demo_trade_grant=True,
            demo_ledger_binding_proof=self.ledger_binding,
            expected_demo_uid_sha256=self.expected_uid_sha256,
        )

    async def _cleanup(self):
        if self.supervisor is not None:
            await self.supervisor.close()

    async def _formal_reconcile(self, rows):
        scope = authorized_formal_scope(self.clock.wall_ms() + 86_400_000)
        plan = build_formal_collection_plan(scope)
        rows = dict(rows)
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)
        return await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

    async def _grant(self, authorization_id="loop-grant"):
        state = await self.supervisor._io(self.supervisor._journal.snapshot, "bot")
        owner = state["owner"]
        return DemoTradeGrant(
            authorization_id=authorization_id,
            account_id=FORMAL_ACCOUNT_ALIAS,
            bot_id="bot",
            inst_id=btc_config().contract.inst_id,
            reconciliation_evidence_id=owner["evidence_id"],
            bot_revision=owner["reconciled_revision"],
            starts_at_ms=self.day_clock.wall_ms(),
            entry_cutoff_ms=self.day_clock.wall_ms() + STEP,
            max_entry_mark_notional_usdt=D("2"),
        )

    async def test_formal_reconcile_grant_entry_fill_restart_and_responsibility_reconcile(self):
        initial_gate = await self._formal_reconcile(base_formal_rows())
        self.assertTrue(initial_gate.reconciled)
        self.assertFalse(initial_gate.trade_authorized)
        self.assertEqual(initial_gate.blockers, ())

        self.supervisor.observe_risk(
            snapshot(1, 3 * STEP, valid_until_ms=10 * STEP, mark=D("100")))
        receipt = None
        for index in range(3):
            receipt = await self.supervisor.process_bar(
                index + 1,
                bar(index, "101" if index == 2 else "100"),
                None if index < 2 else account(index),
                expires_at_ms=(index + 2) * STEP,
                now_ms=(index + 1) * STEP,
            )
        self.assertIsNotNone(receipt)
        self.assertIsNotNone(receipt.intent_key)
        intent_key = receipt.intent_key

        with self.assertRaisesRegex(SupervisorUnavailable, "demo_trade_grant_required"):
            await self.supervisor.dispatch(intent_key, now_ms=3 * STEP)
        self.assertEqual(self.exchange.calls, [])

        grant = await self._grant()
        await self.supervisor.authorize_demo_trading(grant)
        self.exchange.enqueue(
            "submit",
            report(
                intent_key,
                status="FILLED",
                fills=(Fill("entry-fill", D("2"), D("100")),),
                complete=True,
            ),
        )
        result = await self.supervisor.dispatch(intent_key, now_ms=3 * STEP)
        self.assertEqual(result["state"], "FILLED")
        self.assertEqual(len(self.exchange.calls), 1)
        operation, payload = self.exchange.calls[0]
        self.assertEqual(operation, "submit")
        self.assertEqual(payload["tag"], TAG)
        self.assertFalse(payload["reduceOnly"])

        order = await self.supervisor._io(
            self.supervisor._journal.execution.order, intent_key)
        remote_order_id = order["exchange_id"]
        self.assertIsNotNone(remote_order_id)

        await self.supervisor.close()
        self.supervisor = self._make_supervisor()
        await self.supervisor.start()
        self.assertEqual(self.supervisor.health, "RECONCILING")
        self.assertIsNone(self.supervisor._demo_trade_grant)
        self.assertIn(grant.authorization_id, self.supervisor._demo_consumed_authorization_ids)

        rows = base_formal_rows()
        rows["positions"] = [dict(
            instType="SWAP",
            instId="BTC-USDT-SWAP",
            posId="remote-position",
            mgnMode="cross",
            posSide="net",
            pos="2",
            avgPx="100",
            uTime="1700000001500",
        )]
        rows["orders_history"] = [dict(
            instType="SWAP",
            instId="BTC-USDT-SWAP",
            ordId=remote_order_id,
            tdMode="cross",
            posSide="net",
            side="buy",
            state="filled",
            sz="2",
            accFillSz="2",
            uTime="1700000001500",
        )]
        rows["fills"] = [dict(
            instId="BTC-USDT-SWAP",
            tradeId="entry-fill",
            ordId=remote_order_id,
            fillSz="2",
            fillPx="100",
            fee="0",
            feeCcy="USDT",
            ts="1700000001500",
        )]

        restart_gate = await self._formal_reconcile(rows)
        self.assertTrue(restart_gate.reconciled)
        self.assertFalse(restart_gate.trade_authorized)
        self.assertEqual(restart_gate.blockers, ())
        state = await self.supervisor._io(self.supervisor._journal.snapshot, "bot")
        self.assertEqual(state["owner"]["position"], "2")
        self.assertEqual(state["owner"]["remote_pos_id"], "remote-position")
        self.assertEqual(state["owner"]["reconciled_revision"], restart_gate.bot_revision)
        self.assertIsNone(self.supervisor._demo_trade_grant)

        with self.assertRaisesRegex(SupervisorUnavailable, "grant_consumed"):
            await self.supervisor.authorize_demo_trading(grant)


if __name__ == "__main__":
    unittest.main()
