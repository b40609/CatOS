"""Bounded local process/commit faults; no network or real account state."""

import asyncio
from contextlib import closing
from decimal import Decimal as D
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock, patch

from catos import account_lock
from catos.account_lock import AccountBindingError, AccountBusy, AccountLock
from catos.journal import FixtureDecision, Journal, OwnershipError
from catos.supervisor import LocalSupervisor, SupervisorBusy, SupervisorUnavailable
from catos.worker_host import worker_environment, WorkerError
from test_ipc import STEP, account, bar, config
from test_journal import prepare_and_commit, proof

ROOT = Path(__file__).resolve().parents[1]


async def wait_flag(flag):
    async def poll():
        while not flag.is_set():
            await asyncio.sleep(0.005)
    await asyncio.wait_for(poll(), 5)


class SupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "state.sqlite3"
        self.account_id = "fake-account"
        self.lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        self.lock_patch.start()
        self.addCleanup(self.lock_patch.stop)

    async def supervisor(self, **changes):
        options = dict(account_id=self.account_id, bot_id="bot", config=config(), fixture_budget=D("100"))
        options.update(changes)
        supervisor = LocalSupervisor(self.path, **options)
        self.addAsyncCleanup(supervisor.close)
        await supervisor.start()
        return supervisor

    async def ready(self):
        supervisor = await self.supervisor()
        await supervisor.reconcile(proof(supervisor.revision))
        for index in (0, 1):
            await self.event(supervisor, index)
        return supervisor

    async def event(self, supervisor, index, *, amount=None):
        return await supervisor.process_bar(index + 1, bar(index, "101" if index >= 2 else "100"),
            None if index < 2 else account(index), expires_at_ms=(index + 2) * STEP,
            now_ms=(index + 1) * STEP, fixture=None if amount is None else FixtureDecision(True, D(amount)))

    async def child(self, mode, database=None, lock_root=None):
        fixture = str(ROOT / "tests" / "fixtures" / "journal_process.py")
        args = [fixture, mode, str(lock_root or self.root / "locks"), str(database or self.path)]
        bootstrap = (f"import sys, runpy; sys.path[:0]=[{str(ROOT)!r}, {str(ROOT / 'tests')!r}]; "
                     f"sys.argv={args!r}; runpy.run_path({fixture!r}, run_name='__main__')")
        process = await asyncio.create_subprocess_exec(sys.executable, "-I", "-S", "-B", "-u", "-c", bootstrap,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env=worker_environment())

        async def cleanup():
            if process.returncode is None:
                process.kill()
            await process.communicate()
        self.addAsyncCleanup(cleanup)
        return process

    async def test_real_worker_is_acknowledged_only_after_atomic_commit(self):
        supervisor = await self.ready()
        worker = supervisor._worker
        original = worker.acknowledge
        seen = []

        async def checked_ack(seq):
            with closing(sqlite3.connect(self.path)) as connection:
                seen.append(tuple(connection.execute("SELECT consumed_seq FROM bots WHERE bot_id='bot'").fetchone()))
                self.assertEqual(connection.execute("SELECT count(*) FROM reservations").fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT state FROM outbox").fetchone()[0], "HELD_SIMULATION")
            await original(seq)

        with patch.object(worker, "acknowledge", checked_ack):
            receipt = await self.event(supervisor, 2, amount="80")
        self.assertEqual(seen, [(3,)])
        self.assertEqual(receipt.disposition, "RESERVED_SIMULATION")
        self.assertEqual(supervisor.available_fixture_budget, D("20"))
        replay = await self.event(supervisor, 2, amount="99")
        self.assertTrue(replay.replayed)
        self.assertEqual(supervisor.total_reserved, D("80"))

    async def test_reconciliation_is_required_at_every_start(self):
        supervisor = await self.supervisor()
        with self.assertRaises(SupervisorUnavailable):
            await self.event(supervisor, 0)
        self.assertIsNone(supervisor._worker)
        await supervisor.reconcile(proof(supervisor.revision))
        self.assertEqual((await self.event(supervisor, 0)).event_seq, 1)

    async def test_lost_ack_after_commit_replays_without_reexecuting_worker(self):
        supervisor = await self.ready()
        with patch.object(supervisor._worker, "acknowledge", side_effect=WorkerError("synthetic lost ACK")):
            with self.assertRaises(WorkerError):
                await self.event(supervisor, 2, amount="80")
        await supervisor.close()
        resumed = await self.supervisor()
        await resumed.reconcile(proof(resumed.revision))
        receipt = await self.event(resumed, 2, amount="99")
        self.assertTrue(receipt.replayed)
        self.assertEqual(receipt.reservation, D("80"))
        self.assertIsNone(resumed._worker)

    async def test_close_during_commit_waits_without_releasing_account_early(self):
        supervisor = await self.ready()
        entered, release = threading.Event(), threading.Event()
        original = Journal._commit

        def delayed(journal):
            if journal.connection.execute("SELECT consumed_seq FROM bots").fetchone()[0] == 3:
                entered.set()
                if not release.wait(5):
                    raise sqlite3.OperationalError("test timeout")
            original(journal)

        with patch.object(Journal, "_commit", delayed):
            task = asyncio.create_task(self.event(supervisor, 2, amount="80"))
            await wait_flag(entered)
            closing_task = asyncio.create_task(supervisor.close())
            try:
                await asyncio.sleep(0.03)
                self.assertFalse(closing_task.done())
                with self.assertRaises(AccountBusy):
                    AccountLock("fake-account").acquire()
            finally:
                release.set()
            with self.assertRaises(SupervisorUnavailable):
                await task
            await closing_task
        self.assertIsNone(supervisor._worker)
        resumed = await self.supervisor()
        self.assertEqual(resumed.total_reserved, D("80"))

    async def test_torn_account_binding_is_rejected_without_database_creation(self):
        lock = AccountLock("fake-account")
        lock.acquire()
        lock.close()
        with lock.path.open("ab") as handle:
            handle.write(b'{"database":')
        with self.assertRaises(AccountBindingError):
            await self.supervisor()
        self.assertFalse(self.path.exists())

    async def test_second_supervisor_different_database_cannot_bypass_account_lock(self):
        supervisor = await self.supervisor()
        alternate = self.root / "alternate.sqlite3"
        process = await self.child("compete", alternate)
        await asyncio.wait_for(process.communicate(), 5)
        self.assertEqual(process.returncode, 17)
        self.assertFalse(alternate.exists())
        await supervisor.close()
        process = await self.child("compete", alternate)
        _, err = await asyncio.wait_for(process.communicate(), 5)
        self.assertEqual(process.returncode, 19, err)
        self.assertFalse(alternate.exists())
        resumed = await self.supervisor()
        self.assertEqual(resumed.health, "RECONCILING")

    async def test_missing_bound_database_does_not_silently_rebuild(self):
        supervisor = await self.supervisor()
        await supervisor.close()
        # Reversible move in the owned TemporaryDirectory simulates missing storage.
        self.path.rename(self.root / "saved.sqlite3")
        with self.assertRaises(AccountBindingError):
            await self.supervisor()
        self.assertFalse(self.path.exists())

    async def test_process_death_releases_os_lock_without_deleting_lock_file(self):
        process = await self.child("hold")
        self.assertEqual(await asyncio.wait_for(process.stdout.readline(), 5), b"LOCKED\r\n" if sys.platform == "win32" else b"LOCKED\n")
        lock = AccountLock("fake-account")
        with self.assertRaises(AccountBusy):
            lock.acquire()
        process.kill()
        await process.communicate()
        lock.acquire()
        lock.close()
        self.assertTrue(lock.path.exists())

    async def test_kill_and_concurrency_while_financial_commit_waits(self):
        supervisor = await self.ready()
        entered, release = threading.Event(), threading.Event()
        original = Journal._commit

        def delayed(journal):
            row = journal.connection.execute("SELECT consumed_seq FROM bots WHERE bot_id='bot'").fetchone()
            if row and row[0] == 3 and not entered.is_set():
                entered.set()
                if not release.wait(5):
                    raise sqlite3.OperationalError("test release deadline")
            original(journal)

        with patch.object(Journal, "_commit", delayed):
            task = asyncio.create_task(self.event(supervisor, 2, amount="80"))
            try:
                await wait_flag(entered)
                self.assertFalse(task.done())
                self.assertEqual(supervisor._worker.checkpoint.event_seq, 2)
                self.assertEqual(supervisor.available_fixture_budget, D("20"))
                with self.assertRaises(SupervisorBusy):
                    await self.event(supervisor, 3, amount="80")
                supervisor.latch("manual_kill")
                self.assertIn("manual_kill", supervisor.halt_reasons)
                self.assertEqual(supervisor.epoch, 1)
            finally:
                release.set()
            await task
        self.assertEqual(supervisor.pending_reservation, D("0"))
        self.assertEqual(supervisor.total_reserved, D("80"))
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("SELECT epoch FROM control").fetchone()[0], 1)
            self.assertEqual(tuple(connection.execute("SELECT state,epoch FROM outbox").fetchone()), ("HELD_SIMULATION", 0))
        await supervisor.close()
        resumed = await self.supervisor()
        self.assertIn("manual_kill", resumed.halt_reasons)
        self.assertEqual(resumed.health, "RECONCILING")

    async def test_commit_errors_do_not_ack_or_release_tentative_reservation(self):
        for committed in (False, True):
            with self.subTest(committed=committed):
                self.path = self.root / f"failure-{committed}.sqlite3"
                self.account_id = f"failure-{committed}"
                supervisor = await self.ready()
                worker = supervisor._worker
                original = Journal._commit

                def failing(journal):
                    row = journal.connection.execute("SELECT consumed_seq FROM bots WHERE bot_id='bot'").fetchone()
                    if row and row[0] == 3:
                        if committed:
                            original(journal)
                        raise sqlite3.OperationalError("simulated commit outcome failure")
                    original(journal)

                with patch.object(Journal, "_commit", failing), patch.object(worker, "acknowledge", new_callable=AsyncMock) as ack:
                    with self.assertRaises(sqlite3.OperationalError):
                        await self.event(supervisor, 2, amount="80")
                    ack.assert_not_awaited()
                self.assertEqual(supervisor.health, "DEGRADED")
                self.assertEqual(supervisor.pending_reservation, D("80"))
                self.assertIsNotNone(worker.process.returncode)
                await supervisor.close()
                resumed = await self.supervisor()
                self.assertEqual(resumed.checkpoint.event_seq, 3 if committed else 2)
                await resumed.reconcile(proof(resumed.revision))
                receipt = await self.event(resumed, 2, amount="80")
                self.assertEqual(receipt.replayed, committed)
                self.assertEqual(resumed.total_reserved, D("80"))
                await resumed.close()

    async def test_cancel_during_commit_retains_lock_until_writer_finishes(self):
        supervisor = await self.ready()
        entered, release = threading.Event(), threading.Event()
        original = Journal._commit

        def delayed(journal):
            if journal.connection.execute("SELECT consumed_seq FROM bots").fetchone()[0] == 3:
                entered.set()
                if not release.wait(5):
                    raise sqlite3.OperationalError("test timeout")
            original(journal)

        with patch.object(Journal, "_commit", delayed):
            task = asyncio.create_task(self.event(supervisor, 2, amount="80"))
            try:
                await wait_flag(entered)
                task.cancel()
                await asyncio.sleep(0.02)
                self.assertFalse(task.done())
                with self.assertRaises(AccountBusy):
                    AccountLock("fake-account").acquire()
            finally:
                release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual(supervisor.health, "DEGRADED")
        self.assertEqual(supervisor.pending_reservation, D("80"))

    async def test_worker_failure_keeps_pending_input_and_contract_owner(self):
        supervisor = await self.ready()
        with patch.object(supervisor._worker, "process_bar", side_effect=WorkerError("synthetic child crash")):
            with self.assertRaises(WorkerError):
                await self.event(supervisor, 2)
        await supervisor.close()
        with self.assertRaises(OwnershipError):
            await self.supervisor(bot_id="other")
        resumed = await self.supervisor()
        await resumed.reconcile(proof(resumed.revision))
        receipt = await self.event(resumed, 2)
        self.assertEqual(receipt.event_seq, 3)

    async def test_real_process_crash_before_and_after_commit_is_atomic(self):
        for mode in ("before_commit", "after_commit"):
            with self.subTest(mode=mode):
                database = self.root / f"{mode}.sqlite3"
                journal = Journal(database, "fake-account", D("100"))
                journal.register("bot", config())
                journal.reconcile("bot", proof(0))
                prepare_and_commit(journal, 0)
                prepare_and_commit(journal, 1)
                journal.close()
                process = await self.child(mode, database, self.root / f"locks-{mode}")
                _, err = await asyncio.wait_for(process.communicate(), 5)
                self.assertEqual(process.returncode, 72 if mode == "after_commit" else 71, err)
                journal = Journal(database, "fake-account", D("100"))
                try:
                    state = journal.snapshot("bot")
                    committed = mode == "after_commit"
                    self.assertEqual(state["checkpoint"].event_seq, 3 if committed else 2)
                    self.assertEqual(state["total_reserved"], D("80") if committed else D("0"))
                    for table in ("intents", "reservations", "outbox"):
                        self.assertEqual(journal.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], int(committed))
                    self.assertEqual(state["pending"], not committed)
                finally:
                    journal.close()

    async def test_demo_and_live_environments_rejected(self):
        for environment in ("demo", "live"):
            with self.assertRaises(ValueError):
                LocalSupervisor(self.path, account_id="fake-account", bot_id="bot", config=config(),
                                fixture_budget=D("100"), environment=environment)


if __name__ == "__main__":
    unittest.main()
