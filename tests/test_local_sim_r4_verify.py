"""Verifier rejects fabricated completion and inconsistent retained evidence."""

import asyncio
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from catos import account_lock, local_sim_r4 as runner, local_sim_r4_verify as audit


class R4VerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.fixture.cleanup)
        root = Path(cls.fixture.name)
        with patch.object(account_lock, "LOCK_DIRECTORY", root / "locks"):
            cls.completed, status = asyncio.run(runner.run("smoke", output_root=root / "runs"))
        if status["state"] != "complete":
            raise RuntimeError(status)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / self.completed.name
        shutil.copytree(self.completed, self.directory)
        self.change_json("manifest.json", database=str(self.directory / "state.sqlite3"))

    def change_json(self, name, **changes):
        path = self.directory / name
        value = json.loads(path.read_text(encoding="utf-8"))
        value.update(changes)
        path.write_text(json.dumps(value), encoding="utf-8")

    def verify(self):
        return audit.verify_directory(self.directory, alive=lambda _pid: False)

    def test_finished_smoke_passes_read_only_without_claiming_eight_hours(self):
        result = self.verify()
        self.assertEqual((result["verdict"], result["bars"], result["fills"]), ("SMOKE_PASS", 8, 4))
        self.assertEqual(result["database_mode"], "read-only")
        self.assertEqual(result["fees"], "0.00404010")

    def test_running_is_pending_without_opening_database(self):
        self.change_json("status.json", state="running", finished_at=None)
        with patch.object(audit.sqlite3, "connect", side_effect=AssertionError("must not audit live DB")):
            self.assertEqual(self.verify()["verdict"], "PENDING")

    def test_duration_cannot_be_forged_short(self):
        self.change_json("status.json", elapsed_seconds=1)
        with self.assertRaisesRegex(audit.VerificationError, "wall_duration_incomplete"):
            self.verify()

    def test_live_worker_cannot_be_called_finished(self):
        with self.assertRaisesRegex(audit.VerificationError, "run_process_still_alive"):
            audit.verify_directory(self.directory, alive=lambda _pid: True)

    def test_runtime_change_is_rejected(self):
        with patch.object(audit, "files_hash", return_value="0" * 64):
            with self.assertRaisesRegex(audit.VerificationError, "runtime_digest_changed"):
                self.verify()

    def test_fee_log_and_sqlite_must_match(self):
        path = self.directory / "events.jsonl"
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        next(event for event in events if event["kind"] == "fill")["fill"]["fee"] = "0"
        path.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
        with self.assertRaisesRegex(audit.VerificationError, "decimal_fill_mismatch"):
            self.verify()

    def test_unsettled_order_is_not_released_by_verifier(self):
        with closing(sqlite3.connect(self.directory / "state.sqlite3")) as db:
            db.execute("UPDATE execution_orders SET settled=0 WHERE rowid=1")
            db.commit()
        with self.assertRaisesRegex(audit.VerificationError, "unresolved_orders"):
            self.verify()
        with closing(sqlite3.connect(self.directory / "state.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT settled FROM execution_orders WHERE rowid=1").fetchone()[0], 0)

    def test_worker_manifest_cannot_omit_registered_artifact(self):
        path = self.directory / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["worker_config"].pop("strategy_artifact")
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(audit.VerificationError, "registered_worker_config_mismatch"):
            self.verify()

    def test_journal_content_hash_must_match_stored_input(self):
        with closing(sqlite3.connect(self.directory / "state.sqlite3")) as db:
            db.execute("UPDATE inputs SET input_hash=? WHERE seq=3", ("0" * 64,))
            db.commit()
        with self.assertRaisesRegex(audit.VerificationError, "journal_content_digest_mismatch"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
