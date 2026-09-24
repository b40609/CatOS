"""Formal Supervisor reconciliation wiring with synthetic in-memory evidence only."""

from contextlib import closing
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from catos import account_lock, account_report, okx_collection as collection, okx_readonly, risk
from catos.fake_exchange import FakeExchange, Fill
from catos.journal import Journal
from catos.reconciliation_gate import (DayLedgerEvidence, FreshnessEvidence,
                                       FreshnessPolicy)
from catos.supervisor import LocalSupervisor, SupervisorUnavailable
from test_execution import report as execution_report
from test_ipc import STEP, config
from test_journal import proof, prepare_and_commit
from test_risk import snapshot as risk_snapshot


D = Decimal
SYNTHETIC_FLOW_CLASSIFICATION = okx_readonly.FlowClassification("synthetic-flow-map", (), True)


def scope():
    return collection.RunScope("synthetic-demo", "demo", "SYNTHETIC-USDT-SWAP",
                               100, 200, 30, 5, 100, 5000)


def synthetic_rows():
    return {
        "account_config": [dict(uid="child", mainUid="parent", acctLv="2",
                                posMode="net_mode", roleType="0", perm="read_only")],
        "balance": [dict(totalEq="1000", adjEq="1000", uTime="150", details=[dict(
            ccy="USDT", eq="1000", liab="0", availEq="1000", ordFrozen="0", uTime="150")])],
        "positions": [],
        "orders_pending": [],
        "algo_pending": [],
        "account_instruments": [dict(instType="SWAP", instId="SYNTHETIC-USDT-SWAP",
                                     ctType="linear", settleCcy="USDT", ctValCcy="SYNTHETIC",
                                     state="live", ctVal="1", ctMult="1", tickSz="0.01",
                                     lotSz="0.01", minSz="0.01")],
        "fills": [],
        "bills": [],
    }


class SyntheticTransport:
    def __init__(self, rows, hook=None):
        self.rows = rows
        self.hook = hook

    def fetch(self, request):
        if self.hook is not None:
            self.hook(request)
        window_evidence = None
        if request.endpoint.alias in collection.WINDOWED_EVENT_ENDPOINTS:
            if request.endpoint.alias == "orders_history":
                window_evidence = collection.WindowRequestEvidence(
                    request.scope.window_start_ms, request.scope.window_end_ms,
                    "cTime", "after_order_id")
            else:
                window_evidence = collection.WindowRequestEvidence(
                    request.scope.window_start_ms, request.scope.window_end_ms)
        return collection.PageResponse(
            request.scope.account_alias, request.scope.environment, 200,
            {"code": "0", "data": self.rows[request.endpoint.alias]},
            window_evidence=window_evidence)


def plan_and_transport(hook=None):
    rows = synthetic_rows()
    return (collection.CollectionPlan(scope(), tuple(rows)),
            SyntheticTransport(rows, hook))



def plan_and_transport(hook=None):
    rows = synthetic_rows()
    return (collection.CollectionPlan(scope(), tuple(rows)),
            SyntheticTransport(rows, hook))


def collected():
    plan, transport = plan_and_transport()
    return collection.collect_plan(plan, transport)


def taipei_day_start_ms(time_ms):
    day = (time_ms + 28_800_000) // 86_400_000
    return day * 86_400_000 - 28_800_000


def evidence(result):
    completed = result.manifest.completed_ms
    day_start = taipei_day_start_ms(completed)
    return dict(
        classifications=SYNTHETIC_FLOW_CLASSIFICATION,
        freshness_policy=FreshnessPolicy(
            "synthetic-policy", 10_000, 10_000, 10_000, 10_000, completed),
        freshness_evidence=FreshnessEvidence(completed, completed),
        day_ledger=DayLedgerEvidence(day_start, D("1000"), "synthetic-baseline",
                                     D("0"), SYNTHETIC_FLOW_CLASSIFICATION.classification_id, 0),
    )


def orchestration_evidence(stamp=None):
    import time
    if stamp is None:
        stamp = time.time_ns() // 1_000_000
    day_start = taipei_day_start_ms(stamp)
    return dict(
        classifications=SYNTHETIC_FLOW_CLASSIFICATION,
        freshness_policy=FreshnessPolicy(
            "synthetic-orchestration-policy", 10_000, 10_000, 10_000, 10_000, stamp + 50),
        freshness_evidence=FreshnessEvidence(stamp, stamp),
        day_ledger=DayLedgerEvidence(day_start, D("1000"), "synthetic-baseline",
                                     D("0"), SYNTHETIC_FLOW_CLASSIFICATION.classification_id, 0),
    )


class SupervisorReconciliationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "state.sqlite3"
        lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)

        # Seed only durable local flat ownership. Reopening deliberately clears
        # reconciled_revision so the formal gate must establish this process's proof.
        journal = Journal(self.path, "fake-account", D("100"))
        journal.register("bot", config())
        journal.reconcile("bot", proof(0))
        journal.close()

        self.supervisor = LocalSupervisor(
            self.path, account_id="fake-account", bot_id="bot", config=config(),
            fixture_budget=D("100"))
        self.addAsyncCleanup(self.supervisor.close)
        await self.supervisor.start()
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def owner(self):
        state = await self.supervisor._io(self.supervisor._journal.snapshot, "bot")
        return state["owner"]

    async def test_pass_builds_report_from_snapshot_and_writes_same_revision_only(self):
        result = collected()
        with patch("catos.supervisor.account_report.build_report", wraps=account_report.build_report) as build:
            gate = await self.supervisor.reconcile_report(result, scope=scope(), **evidence(result))
        self.assertTrue(gate.reconciled)
        self.assertFalse(gate.trade_authorized)
        self.assertEqual(gate.blockers, ())
        self.assertEqual(self.supervisor.health, "LOCAL_READY")
        kwargs = build.call_args.kwargs
        self.assertEqual(kwargs["owned_order_ids"], frozenset())
        self.assertEqual(kwargs["owned_algo_ids"], frozenset())
        self.assertEqual(kwargs["owned_positions"], {})
        self.assertEqual(kwargs["unresolved_local_ids"], frozenset())
        owner = await self.owner()
        self.assertEqual(owner["reconciled_revision"], gate.bot_revision)
        self.assertEqual(owner["evidence_id"], gate.evidence_id)
        self.assertEqual(owner["fills_reconciled"], 1)
        with self.assertRaisesRegex(SupervisorUnavailable, "RECONCILING"):
            await self.supervisor.reconcile_report(result, scope=scope(), **evidence(result))

    async def test_policy_blocker_does_not_write_reconciliation(self):
        result = collected()
        supplied = evidence(result)
        supplied["freshness_policy"] = None
        supplied["freshness_evidence"] = None
        gate = await self.supervisor.reconcile_report(result, scope=scope(), **supplied)
        self.assertFalse(gate.reconciled)
        self.assertEqual(set(gate.blockers), {"freshness_policy_unset", "snapshot_freshness_unverified"})
        self.assertEqual(self.supervisor.health, "RECONCILING")
        self.assertIsNone((await self.owner())["reconciled_revision"])

    async def test_revision_change_after_gate_is_rejected_before_write(self):
        result = collected()
        with patch.object(self.supervisor._journal, "current_revision", side_effect=[0, 0, 1]):
            gate = await self.supervisor.reconcile_report(result, scope=scope(), **evidence(result))
        self.assertFalse(gate.reconciled)
        self.assertIn("local_revision_changed", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")
        self.assertIsNone((await self.owner())["reconciled_revision"])


    async def test_precollection_orchestration_passes_with_injected_transport(self):
        plan, transport = plan_and_transport()
        gate = await self.supervisor.collect_and_reconcile(
            plan, transport, **orchestration_evidence())
        self.assertTrue(gate.reconciled)
        self.assertFalse(gate.trade_authorized)
        self.assertEqual(gate.blockers, ())
        self.assertEqual(self.supervisor.health, "LOCAL_READY")

    async def test_precollection_revision_change_fails_closed(self):
        changed = []

        def bump_revision(_request):
            if changed:
                return
            changed.append(True)
            with closing(sqlite3.connect(self.path)) as connection:
                connection.execute("UPDATE bots SET revision=revision+1 WHERE bot_id='bot'")
                connection.commit()

        plan, transport = plan_and_transport(bump_revision)
        gate = await self.supervisor.collect_and_reconcile(
            plan, transport, **orchestration_evidence())
        self.assertFalse(gate.reconciled)
        self.assertIn("local_revision_changed", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")
        self.assertIsNone((await self.owner())["reconciled_revision"])

    async def test_precollection_responsibility_change_without_revision_fails_closed(self):
        changed = []

        def add_local_order(_request):
            if changed:
                return
            changed.append(True)
            with closing(sqlite3.connect(self.path)) as connection:
                connection.execute("""INSERT INTO execution_orders
                    (order_key,cl_ord_id,intent_key,bot_id,payload_json,quantity,filled,reservation,state,
                     cancel_pending,settled,deadline,epoch,exchange_id,report_revision,report_json)
                    VALUES ('race-order','client-race',NULL,'bot','{"reduceOnly":false}',
                            '1','0','0','LIVE',0,0,999999,0,'remote-race',0,NULL)""")
                connection.commit()

        plan, transport = plan_and_transport(add_local_order)
        gate = await self.supervisor.collect_and_reconcile(
            plan, transport, **orchestration_evidence())
        self.assertFalse(gate.reconciled)
        self.assertIn("local_revision_changed", gate.blockers)
        self.assertEqual(await self.supervisor._io(self.supervisor._journal.current_revision, "bot"), 0)
        self.assertIsNone((await self.owner())["reconciled_revision"])


class PositionBootstrapSupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "bootstrap.sqlite3"
        lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks-bootstrap")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)
        self.exchange = FakeExchange("fake-account")
        self.supervisor = LocalSupervisor(
            self.path, account_id="fake-account", bot_id="bot", config=config(),
            fixture_budget=D("100"), risk_limits=risk.Limits(), exchange=self.exchange)
        self.addAsyncCleanup(self.supervisor.close)
        await self.supervisor.start()
        await self.supervisor.reconcile(proof(0))
        self.supervisor.observe_risk(risk_snapshot(
            1, 3 * STEP, valid_until_ms=20 * STEP, position=D("0")))
        await self.supervisor.persist_controls()
        for index in (0, 1):
            await self.supervisor._io(prepare_and_commit, self.supervisor._journal, index)
        receipt = await self.supervisor._io(
            lambda: prepare_and_commit(self.supervisor._journal, 2, target=D("2")))
        self.key = receipt.intent_key
        self.exchange.enqueue("submit", execution_report(
            self.key, status="FILLED", fills=(Fill("bootstrap-trade", D("2"), D("100")),),
            complete=True))
        await self.supervisor.dispatch(self.key, now_ms=3 * STEP)
        order = await self.supervisor._io(self.supervisor._journal.execution.order, self.key)
        self.remote_order_id = order["exchange_id"]
        self.assertIsNotNone(self.remote_order_id)
        owner = await self.owner()
        self.assertEqual((owner["position"], owner["remote_pos_id"]), ("2", None))

    async def owner(self):
        state = await self.supervisor._io(self.supervisor._journal.snapshot, "bot")
        return state["owner"]

    def bootstrap_plan(self, *, remote_fill="2", remote_position="2",
                       remote_order_id=None, include_fill=True, extra_fill=None,
                       second_position=False, hook=None):
        rows = synthetic_rows()
        rows["positions"] = [dict(
            instType="SWAP", instId="SYNTHETIC-USDT-SWAP", posId="remote-position",
            mgnMode="cross", posSide="net", pos=remote_position, avgPx="100", uTime="150")]
        if second_position:
            rows["positions"].append(dict(
                instType="SWAP", instId="OTHER-USDT-SWAP", posId="foreign-position",
                mgnMode="cross", posSide="net", pos="1", avgPx="50", uTime="150"))
        order_id = self.remote_order_id if remote_order_id is None else remote_order_id
        rows["orders_history"] = [dict(
            instType="SWAP", instId="SYNTHETIC-USDT-SWAP", ordId=order_id,
            tdMode="cross", posSide="net", side="buy", state="filled",
            sz=remote_fill, accFillSz=remote_fill, uTime="150")]
        rows["fills"] = []
        if include_fill:
            rows["fills"].append(dict(
                instId="SYNTHETIC-USDT-SWAP", tradeId="bootstrap-trade",
                ordId=order_id, fillSz=remote_fill, fillPx="100",
                fee="0", feeCcy="USDT", ts="150"))
        if extra_fill is not None:
            rows["fills"].append(extra_fill)
        plan = collection.CollectionPlan(scope(), tuple(rows))
        return plan, SyntheticTransport(rows, hook)

    def bootstrap_result(self, **kwargs):
        plan, transport = self.bootstrap_plan(**kwargs)
        return collection.collect_plan(plan, transport)

    async def test_exact_local_and_remote_fill_lineage_bootstraps_posid_then_reconciles(self):
        plan, transport = self.bootstrap_plan()
        before = self.supervisor.revision
        gate = await self.supervisor.collect_and_reconcile(
            plan, transport, **orchestration_evidence())
        self.assertTrue(gate.reconciled)
        self.assertFalse(gate.trade_authorized)
        self.assertEqual(gate.blockers, ())
        owner = await self.owner()
        self.assertEqual(owner["remote_pos_id"], "remote-position")
        self.assertEqual(owner["reconciled_revision"], gate.bot_revision)
        self.assertEqual(owner["fills_reconciled"], 1)
        self.assertEqual(gate.bot_revision, before + 1)
        snap = await self.supervisor._io(self.supervisor._journal.reconciliation_snapshot, "bot")
        self.assertEqual(snap.owned_remote_position_ids,
                         (("SYNTHETIC-USDT-SWAP", "remote-position"),))

    async def test_collection_race_never_binds_bootstrap_identity(self):
        changed = []

        def bump_revision(_request):
            if changed:
                return
            changed.append(True)
            with closing(sqlite3.connect(self.path)) as connection:
                connection.execute("UPDATE bots SET revision=revision+1 WHERE bot_id='bot'")
                connection.commit()

        plan, transport = self.bootstrap_plan(hook=bump_revision)
        gate = await self.supervisor.collect_and_reconcile(
            plan, transport, **orchestration_evidence())
        self.assertFalse(gate.reconciled)
        self.assertIn("local_revision_changed", gate.blockers)
        self.assertIsNone((await self.owner())["remote_pos_id"])

    async def test_fill_mismatch_never_binds_remote_position_identity(self):
        result = self.bootstrap_result(remote_fill="1")
        gate = await self.supervisor.reconcile_report(result, scope=scope(), **evidence(result))
        self.assertFalse(gate.reconciled)
        self.assertIn("position_identity_unavailable", gate.blockers)
        self.assertIn("foreign_position", gate.blockers)
        owner = await self.owner()
        self.assertIsNone(owner["remote_pos_id"])

    async def test_local_fill_lineage_must_exactly_explain_local_position(self):
        def change_local_position():
            self.supervisor._journal.connection.execute(
                "UPDATE ownership SET position='3' WHERE bot_id='bot'")
            self.supervisor._journal.connection.commit()

        await self.supervisor._io(change_local_position)
        result = self.bootstrap_result(remote_fill="3", remote_position="3")
        gate = await self.supervisor.reconcile_report(result, scope=scope(), **evidence(result))
        self.assertFalse(gate.reconciled)
        self.assertIn("position_identity_unavailable", gate.blockers)
        self.assertIsNone((await self.owner())["remote_pos_id"])

    async def test_missing_remote_fill_never_binds_remote_position_identity(self):
        result = self.bootstrap_result(include_fill=False)
        gate = await self.supervisor.reconcile_report(result, scope=scope(), **evidence(result))
        self.assertFalse(gate.reconciled)
        self.assertIn("position_identity_unavailable", gate.blockers)
        self.assertIsNone((await self.owner())["remote_pos_id"])

    async def test_extra_remote_fill_never_binds_remote_position_identity(self):
        extra = dict(
            instId="SYNTHETIC-USDT-SWAP", tradeId="unexpected-trade",
            ordId=self.remote_order_id, fillSz="1", fillPx="100",
            fee="0", feeCcy="USDT", ts="150")
        result = self.bootstrap_result(extra_fill=extra)
        gate = await self.supervisor.reconcile_report(result, scope=scope(), **evidence(result))
        self.assertFalse(gate.reconciled)
        self.assertIn("position_identity_unavailable", gate.blockers)
        self.assertIsNone((await self.owner())["remote_pos_id"])

    async def test_conflicting_duplicate_trade_never_binds_remote_position_identity(self):
        conflicting = dict(
            instId="SYNTHETIC-USDT-SWAP", tradeId="bootstrap-trade",
            ordId=self.remote_order_id, fillSz="1", fillPx="100",
            fee="0", feeCcy="USDT", ts="150")
        result = self.bootstrap_result(extra_fill=conflicting)
        gate = await self.supervisor.reconcile_report(result, scope=scope(), **evidence(result))
        self.assertFalse(gate.reconciled)
        self.assertIn("position_identity_unavailable", gate.blockers)
        self.assertIsNone((await self.owner())["remote_pos_id"])

    async def test_remote_fill_order_identity_must_match_local_durable_order(self):
        result = self.bootstrap_result(remote_order_id="unexpected-order")
        gate = await self.supervisor.reconcile_report(result, scope=scope(), **evidence(result))
        self.assertFalse(gate.reconciled)
        self.assertIn("position_identity_unavailable", gate.blockers)
        self.assertIsNone((await self.owner())["remote_pos_id"])

    async def test_ambiguous_nonzero_remote_positions_never_bootstrap(self):
        result = self.bootstrap_result(second_position=True)
        gate = await self.supervisor.reconcile_report(result, scope=scope(), **evidence(result))
        self.assertFalse(gate.reconciled)
        self.assertIn("position_identity_unavailable", gate.blockers)
        self.assertIsNone((await self.owner())["remote_pos_id"])


if __name__ == "__main__":
    unittest.main()
