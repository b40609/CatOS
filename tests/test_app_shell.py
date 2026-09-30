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

    async def test_root_is_multi_page_workbench_and_strategy_routes_are_read_only(self):
        client = TestClient(create_app(self.market_path))
        shell = client.get("/")
        self.assertEqual(shell.status_code, 200)
        self.assertIn("Dashboard", shell.text)
        self.assertIn("Strategy", shell.text)
        self.assertIn("Bots", shell.text)
        self.assertIn("Risk", shell.text)
        self.assertIn("Logs", shell.text)
        self.assertIn("Yaozi", shell.text)
        self.assertIn("設定與連線", shell.text)
        self.assertIn('href="/app/dashboard"', shell.text)
        self.assertIn('href="/app/strategy"', shell.text)
        self.assertIn('href="/app/settings"', shell.text)
        self.assertNotIn("量化交易</button>", shell.text)
        self.assertIn("示意資料", shell.text)

        workbench_routes = (
            "/app/dashboard",
            "/app/strategy",
            "/app/strategy/momentum15",
            "/app/bots",
            "/app/bots/btc-sim",
            "/app/risk",
            "/app/logs",
            "/app/yaozi",
            "/app/settings",
        )
        for route in workbench_routes:
            response = client.get(route)
            self.assertEqual(response.status_code, 200)
            self.assertIn("示意資料", response.text)

        strategy = client.get("/app/strategy/momentum15")
        self.assertIn("策略</button>", strategy.text)
        self.assertIn("回測</button>", strategy.text)
        self.assertIn("參數優化</button>", strategy.text)
        self.assertIn("設定已變更，尚未重跑", strategy.text)
        self.assertIn("尚未樣本外驗證", strategy.text)
        self.assertIn("Antigravity IDE", client.get("/app/settings").text)
        self.assertIn("DeepSeek Harness", client.get("/app/settings").text)

        # Legacy prototype and existing Yaozi backend stay available.
        quant = client.get("/quant")
        self.assertIn("策略研究", quant.text)
        self.assertIn("A 曲線優先", quant.text)
        self.assertIn("B 並排", quant.text)
        self.assertIn("模擬 AI 更新策略", quant.text)
        self.assertIn("示意資料", quant.text)
        self.assertEqual(client.get("/yaozi").status_code, 200)
        self.assertEqual(client.get("/dashboard").status_code, 200)

        status = client.get("/system/strategy-status").json()
        self.assertEqual(status["status"], "not_materialized")
        self.assertEqual(status["lifecycle_owner"], "backend_supervisor")
        self.assertFalse(status["browser_controls_lifecycle"])
        self.assertEqual(status["mutation_routes"], [])
        paths = client.get("/openapi.json").json()["paths"]
        self.assertEqual(set(paths["/system/strategy-status"]), {"get"})
        for route in workbench_routes[:2] + workbench_routes[3:4] + workbench_routes[5:]:
            self.assertEqual(set(paths[route]), {"get"})
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
            for route in (
                "/",
                "/app/dashboard",
                "/app/strategy",
                "/app/strategy/momentum15",
                "/app/bots",
                "/app/bots/btc-sim",
                "/app/risk",
                "/app/logs",
                "/app/yaozi",
                "/app/settings",
                "/quant",
                "/dashboard",
                "/system/strategy-status",
            ):
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
