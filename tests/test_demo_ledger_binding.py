"""Synthetic, read-only tests for the Demo UID-to-ledger binding contract."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from catos import demo_ledger_binding as binding


class DemoLedgerBindingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.database = self.root / "state.sqlite3"
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("CREATE TABLE metadata (account_id TEXT NOT NULL, environment TEXT NOT NULL)")
            db.execute("INSERT INTO metadata VALUES (?, ?)", ("catOSv1", "local-sim"))
        self.uid_sha256 = binding.uid_digest("123456789")
        self.proof = binding.make_binding(
            account_alias="catOSv1",
            expected_uid_sha256=self.uid_sha256,
            database_path=self.database,
        )

    def verify(self, proof=None, **overrides):
        values = dict(
            expected_uid_sha256=self.uid_sha256,
            account_alias="catOSv1",
            remote_environment="demo",
            database_path=self.database,
        )
        values.update(overrides)
        return binding.verify_runtime_binding(self.proof if proof is None else proof, **values)

    def test_valid_binding_verifies_without_mutating_database(self):
        before = self.database.stat().st_mtime_ns
        self.verify()
        self.assertEqual(self.database.stat().st_mtime_ns, before)
        self.assertFalse(Path(str(self.database) + "-wal").exists())
        self.assertFalse(Path(str(self.database) + "-shm").exists())

    def test_binding_rejects_uid_scope_path_and_metadata_mismatch(self):
        with self.assertRaisesRegex(binding.DemoLedgerBindingError, "ledger_binding_uid_mismatch"):
            self.verify(expected_uid_sha256=binding.uid_digest("987654321"))
        with self.assertRaisesRegex(binding.DemoLedgerBindingError, "ledger_binding_scope_mismatch"):
            self.verify(account_alias="other")
        other = self.root / "other.sqlite3"
        other.write_bytes(self.database.read_bytes())
        with self.assertRaisesRegex(binding.DemoLedgerBindingError, "ledger_binding_database_mismatch"):
            self.verify(database_path=other)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE metadata SET account_id='wrong'")
        with self.assertRaisesRegex(binding.DemoLedgerBindingError, "ledger_binding_metadata_scope_mismatch"):
            self.verify()

    def test_missing_database_fails_closed(self):
        missing = self.root / "missing.sqlite3"
        proof = binding.make_binding(
            account_alias="catOSv1",
            expected_uid_sha256=self.uid_sha256,
            database_path=missing,
        )
        with self.assertRaisesRegex(binding.DemoLedgerBindingError, "ledger_binding_database_missing"):
            self.verify(proof=proof, database_path=missing)

    def test_load_binding_rejects_tamper_and_preserves_uid_digest_only(self):
        path = self.root / "binding.json"
        payload = {**self.proof.payload(), "binding_id": self.proof.binding_id}
        path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = binding.load_binding(path)
        self.assertEqual(loaded, self.proof)
        self.assertNotIn("123456789", path.read_text(encoding="utf-8"))

        payload["account_alias"] = "tampered"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(binding.DemoLedgerBindingError, "ledger_binding_invalid"):
            binding.load_binding(path)


if __name__ == "__main__":
    unittest.main()
