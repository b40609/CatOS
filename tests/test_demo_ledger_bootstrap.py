"""Synthetic tests for the read-only production Demo bootstrap plan contract."""

from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catos import (account_lock, demo_ledger_binding, demo_ledger_bootstrap,
                   demo_ledger_preflight, ipc, risk)
from catos.research import ContractSpec


D = Decimal


def config():
    return ipc.WorkerConfig(
        ContractSpec("BTC-USDT-SWAP", D("0.01"), D("0.01"), D("1"), D("1")),
        60_000,
        2,
    )


class DemoLedgerBootstrapTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)
        self.uid_sha256 = demo_ledger_binding.uid_digest("123456789")
        self.config = config()
        self.limits = risk.Limits()

    def evidence(self, **overrides):
        values = dict(
            provenance=demo_ledger_bootstrap.PRODUCTION_EVIDENCE_PROVENANCE,
            account_alias="catOSv1",
            remote_environment="demo",
            expected_uid_sha256=self.uid_sha256,
            uid_digest_source=demo_ledger_bootstrap.UID_DIGEST_SOURCE,
            identity_verified=True,
            account_mode_verified=True,
            account_config_complete=True,
            balance_complete=True,
            positions_complete=True,
            orders_pending_complete=True,
            algo_pending_complete=True,
            orders_history_complete=True,
            fills_complete=True,
            bills_complete=True,
            algo_history_complete=True,
            current_positions_empty=True,
            current_orders_empty=True,
            current_algo_orders_empty=True,
            day_baseline_verified=True,
            unknown_flow_count=0,
            forbidden_activity_count=0,
            collection_evidence_id="collection-evidence",
            day_baseline_evidence_id="midnight-e0-evidence",
        )
        values.update(overrides)
        return demo_ledger_bootstrap.HistoricalResponsibilityEvidence(**values)

    def plan(self, evidence=None):
        return demo_ledger_bootstrap.plan_production_bootstrap(
            workspace_root=self.root,
            expected_uid_sha256=self.uid_sha256,
            bot_id="bot",
            config=self.config,
            fixture_budget=D("100"),
            risk_limits=self.limits,
            historical_evidence=evidence,
        )

    def test_missing_history_stays_blocked_and_creates_nothing(self):
        before = tuple(self.root.rglob("*"))
        result = self.plan()
        self.assertTrue(result.preflight_passed)
        self.assertFalse(result.responsibility_bridge_verified)
        self.assertFalse(result.bootstrap_ready)
        self.assertEqual(result.blockers, ("historical_responsibility_evidence_missing",))
        self.assertFalse(result.ledger_initialized)
        self.assertFalse(result.binding_verified)
        self.assertFalse(result.reconciled)
        self.assertFalse(result.trade_authorized)
        self.assertEqual(tuple(self.root.rglob("*")), before)

    def test_fixed_paths_are_under_dedicated_demo_directory(self):
        result = self.plan(self.evidence())
        database, binding = demo_ledger_bootstrap.production_paths(self.root)
        self.assertEqual(result.database_path, str(database))
        self.assertEqual(result.binding_path, str(binding))
        self.assertEqual(database.relative_to(self.root), Path("data/catosv1-demo/state.sqlite3"))
        self.assertEqual(binding.relative_to(self.root), Path("data/catosv1-demo/ledger-binding.json"))

    def test_empty_remote_state_alone_cannot_bridge_incomplete_accounting_or_e0(self):
        result = self.plan(self.evidence(
            balance_complete=False,
            fills_complete=False,
            bills_complete=False,
            day_baseline_verified=False,
        ))
        self.assertFalse(result.bootstrap_ready)
        self.assertIn("historical_collection_incomplete", result.blockers)
        self.assertIn("day_baseline_unverified", result.blockers)

    def test_synthetic_or_qa_provenance_cannot_satisfy_production_bridge(self):
        for provenance in ("synthetic.v1", "qa.v1"):
            with self.subTest(provenance=provenance):
                result = self.plan(self.evidence(provenance=provenance))
                self.assertFalse(result.bootstrap_ready)
                self.assertIn("historical_evidence_not_production_readonly", result.blockers)

    def test_complete_contract_can_only_mark_future_bootstrap_ready(self):
        result = self.plan(self.evidence())
        self.assertTrue(result.bootstrap_ready)
        self.assertTrue(result.responsibility_bridge_verified)
        self.assertEqual(result.blockers, ())
        self.assertFalse(result.ledger_initialized)
        self.assertFalse(result.binding_verified)
        self.assertFalse(result.reconciled)
        self.assertFalse(result.trade_authorized)
        database, binding = demo_ledger_bootstrap.production_paths(self.root)
        self.assertFalse(database.exists())
        self.assertFalse(binding.exists())

    def test_scope_open_responsibility_and_observed_bad_flows_fail_closed(self):
        result = self.plan(self.evidence(
            expected_uid_sha256=demo_ledger_binding.uid_digest("987654321"),
            current_positions_empty=False,
            unknown_flow_count=1,
            forbidden_activity_count=1,
        ))
        self.assertFalse(result.bootstrap_ready)
        self.assertEqual(set(result.blockers), {
            "historical_evidence_scope_mismatch",
            "preexisting_remote_responsibility",
            "unknown_account_flow",
            "forbidden_account_activity",
        })

    def test_truthy_non_boolean_flags_fail_closed(self):
        result = self.plan(self.evidence(
            identity_verified=1,
            current_positions_empty=1,
            day_baseline_verified=1,
        ))
        self.assertFalse(result.bootstrap_ready)
        self.assertIn("historical_identity_unverified", result.blockers)
        self.assertIn("preexisting_remote_responsibility", result.blockers)
        self.assertIn("day_baseline_unverified", result.blockers)


class DemoLedgerBootstrapOperationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)
        self.uid_sha256 = demo_ledger_binding.uid_digest("123456789")
        self.config = config()
        self.limits = risk.Limits()

    def evidence(self):
        return demo_ledger_bootstrap.HistoricalResponsibilityEvidence(
            provenance=demo_ledger_bootstrap.PRODUCTION_EVIDENCE_PROVENANCE,
            account_alias="catOSv1",
            remote_environment="demo",
            expected_uid_sha256=self.uid_sha256,
            uid_digest_source=demo_ledger_bootstrap.UID_DIGEST_SOURCE,
            identity_verified=True,
            account_mode_verified=True,
            account_config_complete=True,
            balance_complete=True,
            positions_complete=True,
            orders_pending_complete=True,
            algo_pending_complete=True,
            orders_history_complete=True,
            fills_complete=True,
            bills_complete=True,
            algo_history_complete=True,
            current_positions_empty=True,
            current_orders_empty=True,
            current_algo_orders_empty=True,
            day_baseline_verified=True,
            unknown_flow_count=0,
            forbidden_activity_count=0,
            collection_evidence_id="synthetic-test-collection",
            day_baseline_evidence_id="synthetic-test-midnight-e0",
        )

    async def bootstrap(self, evidence):
        return await demo_ledger_bootstrap.bootstrap_production_ledger(
            workspace_root=self.root,
            expected_uid_sha256=self.uid_sha256,
            bot_id="bot",
            config=self.config,
            fixture_budget=D("100"),
            risk_limits=self.limits,
            historical_evidence=evidence,
        )

    async def test_blocked_plan_never_creates_production_paths(self):
        before = tuple(self.root.rglob("*"))
        with self.assertRaisesRegex(
                demo_ledger_bootstrap.DemoLedgerBootstrapError, "bootstrap_not_ready"):
            await self.bootstrap(None)
        self.assertEqual(tuple(self.root.rglob("*")), before)

    async def test_ready_plan_uses_supervisor_writer_and_produces_resumable_binding(self):
        result = await self.bootstrap(self.evidence())
        database, binding_path = demo_ledger_bootstrap.production_paths(self.root)
        self.assertTrue(result.ledger_initialized)
        self.assertTrue(result.binding_verified)
        self.assertFalse(result.reconciled)
        self.assertFalse(result.trade_authorized)
        self.assertTrue(database.is_file())
        self.assertTrue(binding_path.is_file())

        proof = demo_ledger_binding.load_binding(binding_path)
        self.assertEqual(proof.binding_id, result.binding_id)
        resume = demo_ledger_preflight.preflight_demo_ledger(
            intent="resume",
            database_path=database,
            binding_path=binding_path,
            expected_uid_sha256=self.uid_sha256,
            bot_id="bot",
            config=self.config,
            fixture_budget=D("100"),
            risk_limits=self.limits,
        )
        self.assertTrue(resume.preflight_passed)
        self.assertTrue(resume.schema_verified)
        self.assertTrue(resume.binding_verified)
        self.assertFalse(resume.reconciled)
        self.assertFalse(resume.trade_authorized)

    async def test_database_race_after_plan_is_fail_closed_without_overwrite(self):
        plan = demo_ledger_bootstrap.plan_production_bootstrap(
            workspace_root=self.root,
            expected_uid_sha256=self.uid_sha256,
            bot_id="bot",
            config=self.config,
            fixture_budget=D("100"),
            risk_limits=self.limits,
            historical_evidence=self.evidence(),
        )
        database = Path(plan.database_path)
        database.parent.mkdir(parents=True)
        database.write_bytes(b"sentinel")
        with patch.object(demo_ledger_bootstrap, "plan_production_bootstrap", return_value=plan):
            with self.assertRaisesRegex(
                    demo_ledger_bootstrap.DemoLedgerBootstrapError,
                    "ledger_initialization_failed"):
                await self.bootstrap(self.evidence())
        self.assertEqual(database.read_bytes(), b"sentinel")
        self.assertFalse(Path(plan.binding_path).exists())

    async def test_binding_race_preserves_initialized_ledger_and_conflicting_file(self):
        database, binding_path = demo_ledger_bootstrap.production_paths(self.root)
        real_write = demo_ledger_bootstrap._write_binding_exclusive

        def collide(path, proof):
            path.write_bytes(b"sentinel-binding")
            return real_write(path, proof)

        with patch.object(
                demo_ledger_bootstrap, "_write_binding_exclusive", side_effect=collide):
            with self.assertRaisesRegex(
                    demo_ledger_bootstrap.DemoLedgerBootstrapError, "binding_path_exists"):
                await self.bootstrap(self.evidence())

        self.assertTrue(database.is_file())
        self.assertEqual(binding_path.read_bytes(), b"sentinel-binding")
        with self.assertRaisesRegex(
                demo_ledger_preflight.DemoLedgerPreflightError,
                "database_already_account_bound"):
            demo_ledger_preflight.preflight_demo_ledger(
                intent="create",
                database_path=database,
                binding_path=binding_path,
                expected_uid_sha256=self.uid_sha256,
                bot_id="bot",
                config=self.config,
                fixture_budget=D("100"),
                risk_limits=self.limits,
            )


if __name__ == "__main__":
    unittest.main()
