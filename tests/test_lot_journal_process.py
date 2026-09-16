"""C01-C04: actual process death around SQLite COMMIT; synthetic data only."""

import asyncio
from contextlib import closing
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from catos import account_lock
from catos.account_lock import AccountLock
from catos.journal import Journal
from catos.worker_host import worker_environment
from lot_journal_helpers import contract, create, scope, snapshot, update
from test_ipc import config


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "win32", "existing account lock is Windows-only")
class LotJournalProcessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "state.sqlite3"
        self.locks = self.root / "locks"
        with closing(Journal(self.path, "fake-account", D("100"))) as journal:
            journal.register("bot", config())
            journal.lots.register_binding(scope=scope(), bot_id="lot-bot", contract=contract())

    async def child(self, mode):
        fixture = str(ROOT / "tests" / "fixtures" / "lot_journal_process.py")
        args = [fixture, mode, str(self.locks), str(self.path)]
        bootstrap = (f"import sys,runpy; sys.path[:0]=[{str(ROOT)!r},{str(ROOT / 'tests')!r}]; "
                     f"sys.argv={args!r}; runpy.run_path({fixture!r},run_name='__main__')")
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-S", "-B", "-u", "-c", bootstrap,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=worker_environment(), creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            _, stderr = await asyncio.wait_for(process.communicate(), 10)
            return process.returncode, stderr.decode("utf-8", errors="replace")
        finally:
            if process.returncode is None:
                process.kill()
                await process.communicate()

    def seed(self, multiple=False):
        with closing(Journal(self.path, "fake-account", D("100"))) as journal:
            create(journal, opening=True)
            if multiple:
                create(journal, snapshot(seq=2, side="short"), seq=2,
                       write_id="second", closing=True)

    async def test_c01_partial_create_leaves_no_head_revision_or_consumed_sequence(self):
        code, stderr = await self.child("partial_create")
        self.assertEqual(code, 73, stderr)
        with closing(Journal(self.path, "fake-account", D("100"))) as journal:
            report = journal.lots.recover()
            self.assertEqual((report.lot_count, report.revision_count), (0, 0))
            self.assertEqual(journal.connection.execute("SELECT last_commit_seq FROM lot_bindings").fetchone()[0], 0)
            self.assertFalse(create(journal, write_id="process-create").replayed)

    async def test_c02_exit_before_commit_retains_entire_previous_state(self):
        self.seed()
        code, stderr = await self.child("before_commit")
        self.assertEqual(code, 71, stderr)
        with closing(Journal(self.path, "fake-account", D("100"))) as journal:
            state = journal.lots.get(scope=scope(), bot_id="lot-bot", lot_id=snapshot().lot_id)
            self.assertEqual((state.lot.revision, state.lot.remaining_qty, state.commit_seq), (1, D("2"), 1))
            self.assertTrue(state.opening_unresolved)
            self.assertFalse(state.closing_unresolved)
            self.assertEqual(journal.lots.recover().revision_count, 1)

    async def test_c03_exit_after_commit_replays_receipt_without_duplicate_version(self):
        self.seed()
        code, stderr = await self.child("after_commit")
        self.assertEqual(code, 72, stderr)
        with closing(Journal(self.path, "fake-account", D("100"))) as journal:
            value = replace(snapshot(), revision=2, remaining_qty=D("1"))
            receipt = update(journal, value, write_id="process-update", closing=True)
            self.assertEqual((receipt.revision, receipt.commit_seq, receipt.replayed), (2, 2, True))
            self.assertEqual(journal.lots.recover().revision_count, 2)

    async def test_c04_multilot_recovery_preserves_obligations_and_releases_only_os_lock(self):
        self.seed(multiple=True)
        code, stderr = await self.child("after_commit_multi")
        self.assertEqual(code, 72, stderr)
        with patch.object(account_lock, "LOCK_DIRECTORY", self.locks):
            lock = AccountLock("fake-account")
            try:
                lock.acquire()
                self.assertTrue(lock.check_database(self.path))
            finally:
                lock.close()
        with closing(Journal(self.path, "fake-account", D("100"))) as journal:
            report = journal.lots.recover()
            self.assertEqual((report.lot_count, report.revision_count, report.unresolved_lot_count), (2, 3, 2))
            self.assertEqual(journal.connection.execute("SELECT bot_id FROM ownership").fetchone()[0], "bot")
            value = replace(snapshot(), revision=2, remaining_qty=D("1"))
            self.assertTrue(update(journal, value, write_id="process-update", closing=True).replayed)


if __name__ == "__main__":
    unittest.main()
