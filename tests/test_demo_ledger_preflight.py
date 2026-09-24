"""Synthetic tests for the read-only Demo ledger bootstrap preflight."""

from decimal import Decimal
from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catos import account_lock, demo_ledger_binding, demo_ledger_preflight, ipc, risk
from catos.journal import Journal
from catos.research import ContractSpec


D = Decimal


def config():
    return ipc.WorkerConfig(
        ContractSpec("BTC-USDT-SWAP", D("0.01"), D("0.01"), D("1"), D("1")),
        60_000,
        2,
    )


class DemoLedgerPreflightTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)
        self.database = self.root / "production" / "catosv1.sqlite3"
        self.binding = self.root / "bindings" / "catosv1-demo.json"
        self.uid_sha256 = demo_ledger_binding.uid_digest("123456789")
        self.limits = risk.Limits()
        self.config = config()

    def preflight(self, **overrides):
        values = dict(
            intent="create",
            database_path=self.database,
            binding_path=self.binding,
            expected_uid_sha256=self.uid_sha256,
            bot_id="bot",
            config=self.config,
            fixture_budget=D("100"),
            risk_limits=self.limits,
        )
        values.update(overrides)
        return demo_ledger_preflight.preflight_demo_ledger(**values)

    def make_resume_fixture(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        journal = Journal(
            self.database,
            "catOSv1",
            D("100"),
            risk_limits=self.limits,
        )
        journal.register("bot", self.config)
        journal.close()
        proof = demo_ledger_binding.make_binding(
            account_alias="catOSv1",
            expected_uid_sha256=self.uid_sha256,
            database_path=self.database,
        )
        self.binding.parent.mkdir(parents=True, exist_ok=True)
        self.binding.write_text(json.dumps(
            {**proof.payload(), "binding_id": proof.binding_id}, sort_keys=True), encoding="utf-8")

    def test_create_preflight_is_read_only_and_reports_no_authorization(self):
        before = tuple(self.root.rglob("*"))
        result = self.preflight()
        self.assertEqual(tuple(self.root.rglob("*")), before)
        self.assertTrue(result.preflight_passed)
        self.assertFalse(result.schema_verified)
        self.assertFalse(result.binding_verified)
        self.assertFalse(result.reconciled)
        self.assertFalse(result.trade_authorized)
        self.assertFalse(self.database.exists())
        self.assertFalse(self.binding.exists())

    def test_missing_or_mismatched_explicit_settings_fail_closed(self):
        cases = (
            (dict(expected_uid_sha256=None), "expected_uid_digest_invalid"),
            (dict(account_alias="other"), "account_alias_mismatch"),
            (dict(remote_environment="live"), "remote_environment_mismatch"),
            (dict(bot_id=None), "bot_id_invalid"),
            (dict(config=None), "worker_config_missing_or_invalid"),
            (dict(fixture_budget=None), "fixture_budget_missing_or_invalid"),
            (dict(risk_limits=None), "risk_limits_missing_or_invalid"),
        )
        for overrides, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(
                    demo_ledger_preflight.DemoLedgerPreflightError, code):
                self.preflight(**overrides)

    def test_known_qa_database_is_rejected_without_opening_it(self):
        qa_database = Path(demo_ledger_preflight.qa_database_paths()[0])
        with self.assertRaisesRegex(
                demo_ledger_preflight.DemoLedgerPreflightError, "qa_database_excluded"):
            self.preflight(database_path=qa_database)

    def test_create_rejects_existing_database_binding_and_sidecars(self):
        cases = (
            (self.database, "database_path_exists"),
            (self.binding, "binding_path_exists"),
            (Path(str(self.database) + "-wal"), "database_wal_exists"),
            (Path(str(self.database) + "-shm"), "database_shm_exists"),
        )
        for path, code in cases:
            with self.subTest(code=code):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"existing")
                try:
                    with self.assertRaisesRegex(
                            demo_ledger_preflight.DemoLedgerPreflightError, code):
                        self.preflight()
                finally:
                    path.unlink()

    def test_resume_verifies_binding_schema_and_settings_without_mutating_files(self):
        self.make_resume_fixture()
        paths_before = tuple(sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*")))
        database_before = (self.database.stat().st_size, self.database.stat().st_mtime_ns)
        binding_before = (self.binding.stat().st_size, self.binding.stat().st_mtime_ns)
        result = self.preflight(intent="resume")
        self.assertEqual(
            tuple(sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*"))),
            paths_before,
        )
        self.assertEqual(
            (self.database.stat().st_size, self.database.stat().st_mtime_ns), database_before)
        self.assertEqual(
            (self.binding.stat().st_size, self.binding.stat().st_mtime_ns), binding_before)
        self.assertTrue(result.schema_verified)
        self.assertTrue(result.binding_verified)
        self.assertFalse(result.reconciled)
        self.assertFalse(result.trade_authorized)

    def test_resume_rejects_uid_budget_risk_and_bot_mismatch(self):
        self.make_resume_fixture()
        cases = (
            (dict(expected_uid_sha256=demo_ledger_binding.uid_digest("987654321")),
             "ledger_binding_uid_mismatch"),
            (dict(fixture_budget=D("101")), "fixture_budget_mismatch"),
            (dict(risk_limits=risk.Limits(leverage=D("2.0"))), "risk_limits_mismatch"),
            (dict(bot_id="other-bot"), "ledger_bot_scope_mismatch"),
        )
        for overrides, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(
                    demo_ledger_preflight.DemoLedgerPreflightError, code):
                self.preflight(intent="resume", **overrides)

    def test_resume_rejects_incomplete_schema_without_migrating_it(self):
        self.database.parent.mkdir(parents=True, exist_ok=True)
        import sqlite3
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA user_version=7")
            db.execute("""CREATE TABLE metadata (
                account_id TEXT NOT NULL, environment TEXT NOT NULL,
                fixture_budget TEXT NOT NULL, core_schema_version INTEGER NOT NULL)""")
            db.execute("INSERT INTO metadata VALUES ('catOSv1','local-sim','100',2)")
        proof = demo_ledger_binding.make_binding(
            account_alias="catOSv1",
            expected_uid_sha256=self.uid_sha256,
            database_path=self.database,
        )
        self.binding.parent.mkdir(parents=True, exist_ok=True)
        self.binding.write_text(json.dumps(
            {**proof.payload(), "binding_id": proof.binding_id}), encoding="utf-8")
        before = (self.database.stat().st_size, self.database.stat().st_mtime_ns)
        with self.assertRaisesRegex(
                demo_ledger_preflight.DemoLedgerPreflightError, "ledger_schema_incomplete"):
            self.preflight(intent="resume")
        self.assertEqual((self.database.stat().st_size, self.database.stat().st_mtime_ns), before)

    def test_resume_rejects_non_wal_database_without_changing_it(self):
        self.make_resume_fixture()
        import sqlite3
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("PRAGMA journal_mode=DELETE").fetchone()[0], "delete")
        before = (self.database.stat().st_size, self.database.stat().st_mtime_ns)
        with self.assertRaisesRegex(
                demo_ledger_preflight.DemoLedgerPreflightError, "ledger_journal_mode_mismatch"):
            self.preflight(intent="resume")
        self.assertEqual((self.database.stat().st_size, self.database.stat().st_mtime_ns), before)

    def test_account_binding_conflict_and_incomplete_binding_fail_closed(self):
        other = self.root / "other.sqlite3"
        other.write_bytes(b"existing")
        lock = account_lock.AccountLock("catOSv1")
        lock.acquire()
        lock.bind_database(other)
        lock.close()
        with self.assertRaisesRegex(
                demo_ledger_preflight.DemoLedgerPreflightError,
                "account_bound_to_different_database"):
            self.preflight()

        Path(demo_ledger_preflight._account_lock_path("catOSv1")).write_bytes(b"\0")
        with self.assertRaisesRegex(
                demo_ledger_preflight.DemoLedgerPreflightError, "account_binding_incomplete"):
            self.preflight()


if __name__ == "__main__":
    unittest.main()
