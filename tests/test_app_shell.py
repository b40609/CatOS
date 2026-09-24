"""Unified localhost shell and backend-owned strategy lifecycle tests."""

from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from catos import account_lock
from catos.app_shell import supervisor_status_provider
from catos import ipc
from catos.journal import Reconciliation
from catos.market_api import create_app
from catos.market_intel import MarketIntelStore
from catos.research import Candle, ContractSpec
from catos.supervisor import LocalSupervisor

STEP = 900_000


def config():
    return ipc.WorkerConfig(
        ContractSpec("SYNTHETIC-USDT-SWAP", D("0.01"), D("0.01"), D("1"), D("1")),
        STEP,
        2,
    )


def bar(index, price="100"):
    value = D(price)
    return Candle(index * STEP, value, value, value, value)


def proof(revision, **changes):
    return replace(
        Reconciliation(revision, "synthetic-shell-evidence", D("0"), 0, 0, 0, True),
        **changes,
    )


class AppShellTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.market_path = self.root / "intel.sqlite3"
        store = MarketIntelStore(self.market_path)
        store.close()
        self.supervisor_path = self.root / "supervisor.sqlite3"
        self.lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        self.lock_patch.start()
        self.addCleanup(self.lock_patch.stop)

    async def _supervisor(self):
        supervisor = LocalSupervisor(
            self.supervisor_path,
            account_id="shell-local-sim",
            bot_id="shell-bot",
            config=config(),
            fixture_budget=D("100"),
        )
        self.addAsyncCleanup(supervisor.close)
        await supervisor.start()
        await supervisor.reconcile(proof(supervisor.revision))
        return supervisor

    async def _event(self, supervisor, index):
        return await supervisor.process_bar(
            index + 1,
            bar(index, "100"),
            None,
            expires_at_ms=(index + 2) * STEP,
            now_ms=(index + 1) * STEP,
        )

    async def test_root_is_single_product_shell_and_strategy_routes_are_read_only(self):
        client = TestClient(create_app(self.market_path))
        shell = client.get("/")
        self.assertEqual(shell.status_code, 200)
        self.assertIn("量化交易", shell.text)
        self.assertIn("Yaozi 情報", shell.text)
        self.assertIn('data-route="/quant"', shell.text)
        self.assertIn('data-route="/dashboard"', shell.text)
        self.assertIn('src="/quant"', shell.text)
        self.assertEqual(client.get("/dashboard").status_code, 200)

        status = client.get("/system/strategy-status").json()
        self.assertEqual(status["status"], "not_materialized")
        self.assertEqual(status["lifecycle_owner"], "backend_supervisor")
        self.assertFalse(status["browser_controls_lifecycle"])
        self.assertEqual(status["mutation_routes"], [])
        paths = client.get("/openapi.json").json()["paths"]
        self.assertEqual(set(paths["/system/strategy-status"]), {"get"})
        self.assertNotIn("/system/strategy-start", paths)
        self.assertNotIn("/system/strategy-stop", paths)

    async def test_navigation_and_reload_do_not_control_local_supervisor_lifecycle(self):
        supervisor = await self._supervisor()
        first = await self._event(supervisor, 0)
        self.assertEqual(first.event_seq, 1)
        self.assertEqual(supervisor.checkpoint.event_seq, 1)
        self.assertIsNotNone(supervisor._worker)

        before_revision = supervisor.revision
        before_seq = supervisor.checkpoint.event_seq
        with TestClient(create_app(
            self.market_path,
            strategy_status_provider=supervisor_status_provider(supervisor),
        )) as client:
            for route in ("/", "/quant", "/dashboard", "/", "/system/strategy-status"):
                self.assertEqual(client.get(route).status_code, 200)
            status = client.get("/system/strategy-status").json()
            self.assertEqual(status["health"], "LOCAL_READY")
            self.assertEqual(status["event_seq"], 1)
            self.assertTrue(status["worker_running"])
            self.assertEqual(supervisor.revision, before_revision)
            self.assertEqual(supervisor.checkpoint.event_seq, before_seq)
            self.assertIsNotNone(supervisor._worker)

        self.assertEqual(supervisor.revision, before_revision)
        self.assertEqual(supervisor.checkpoint.event_seq, before_seq)
        self.assertIsNotNone(supervisor._worker)
        second = await self._event(supervisor, 1)
        self.assertEqual(second.event_seq, 2)
        self.assertEqual(supervisor.checkpoint.event_seq, 2)
        self.assertIsNotNone(supervisor._worker)


if __name__ == "__main__":
    unittest.main()
