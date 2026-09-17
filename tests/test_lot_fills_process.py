import asyncio
from contextlib import closing
from decimal import Decimal as D
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from catos.journal import Journal
from catos.worker_host import worker_environment
from lot_journal_helpers import contract, scope
from lot_fill_helpers import opening, fill, terminal, close_order, current


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == "win32", "existing account lock is Windows-only")
class LotFillProcessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "synthetic.sqlite3"
        with closing(self.open()) as journal:
            journal.lots.register_binding(scope=scope(), bot_id="lot-bot", contract=contract())
            opening(journal)

    def open(self):
        return Journal(self.path, "fake-account", D(100))

    def seed_close(self, filled=False):
        with closing(self.open()) as journal:
            journal.lot_fills.apply_fill(fill(quantity=D(3)))
            terminal(journal)
            close_order(journal)
            if filled:
                journal.lot_fills.apply_fill(fill(order="close", quantity=D(3)))

    async def child(self, mode):
        fixture = str(ROOT / "tests" / "fixtures" / "lot_fill_process.py")
        args = [fixture, mode, str(self.root / "locks"), str(self.path)]
        bootstrap = (f"import sys,runpy; sys.path[:0]=[{str(ROOT)!r},{str(ROOT / 'tests')!r}]; "
                     f"sys.argv={args!r}; runpy.run_path({fixture!r},run_name='__main__')")
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-I", "-S", "-B", "-u", "-c", bootstrap,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=worker_environment(), creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            _, error = await asyncio.wait_for(process.communicate(), 10)
            return process.returncode, error.decode("utf-8", errors="replace")
        finally:
            if process.returncode is None:
                process.kill()
                await process.communicate()

    async def test_c01_first_fill_uncommitted_is_entirely_absent(self):
        code, error = await self.child("first_open")
        self.assertEqual(code, 73, error)
        with closing(self.open()) as journal:
            self.assertEqual(journal.lot_fills.recover().fill_count, 0)
            self.assertEqual(journal.lots.recover().lot_count, 0)
            self.assertFalse(journal.lot_fills.apply_fill(fill(quantity=D(3))).replayed)

    async def test_c02_close_before_commit_preserves_previous_quantity(self):
        self.seed_close()
        code, error = await self.child("before_close")
        self.assertEqual(code, 71, error)
        with closing(self.open()) as journal:
            self.assertEqual(current(journal).lot.remaining_qty, D(3))
            self.assertTrue(current(journal).closing_unresolved)
            self.assertEqual(journal.lot_fills.recover().fill_count, 1)

    async def test_c03_close_committed_ack_lost_replays(self):
        self.seed_close()
        code, error = await self.child("after_close")
        self.assertEqual(code, 72, error)
        with closing(self.open()) as journal:
            self.assertEqual(current(journal).lot.remaining_qty, D(2))
            self.assertTrue(journal.lot_fills.apply_fill(fill(order="close")).replayed)
            self.assertEqual(journal.lot_fills.recover().fill_count, 2)

    async def test_c04_terminal_flag_atomic_before_and_after_commit(self):
        self.seed_close(filled=True)
        code, error = await self.child("before_terminal")
        self.assertEqual(code, 71, error)
        with closing(self.open()) as journal:
            self.assertTrue(current(journal).closing_unresolved)
            self.assertEqual(journal.lot_fills.recover().terminal_count, 1)
        code, error = await self.child("after_terminal")
        self.assertEqual(code, 72, error)
        with closing(self.open()) as journal:
            self.assertFalse(current(journal).closing_unresolved)
            self.assertTrue(terminal(journal, order="close").replayed)
            self.assertEqual(journal.lot_fills.recover().terminal_count, 2)


if __name__ == "__main__":
    unittest.main()
