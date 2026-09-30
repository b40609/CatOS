"""R1 service/API contracts against the registered synthetic Decimal fixture."""

from dataclasses import asdict
from decimal import Decimal
import json
from io import BytesIO
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from catos.data_io import load_candles_csv
from catos.research import backtest
from catos.research_api import create_app, main
from catos.research_catalog import (
    DATA_PATH, DEFAULT_REQUEST, execute_request, json_text, provenance, validate_request,
)
from catos.research_service import ResearchError, ResearchService
from catos.research_strategy import RegisteredSMA


def request_copy():
    return json.loads(json_text(DEFAULT_REQUEST))


def await_task(service, run_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        task = service.task(run_id)
        if task["status"] in ("complete", "failed"):
            return task
        time.sleep(0.02)
    raise AssertionError("Research fixture did not finish within 10 seconds")


class ResearchCatalogTests(unittest.TestCase):
    def test_exact_core_equivalence_and_decimal_serialization(self):
        request, config, period, quantity = validate_request(request_copy())
        result = backtest(strategy=lambda: RegisteredSMA(period, quantity),
                          candles=load_candles_csv(DATA_PATH, config=config),
                          config=config, warmup_bars=request["warmup_bars"])
        payload, report = execute_request(request, provenance())
        self.assertEqual(payload["result"], json.loads(json_text(asdict(result))))
        self.assertIsInstance(payload["result"]["performance"]["fees"], str)
        self.assertIn("<html", report)
        self.assertEqual(result.config.funding_events, ())
        self.assertEqual(len(payload["drawdown_curve"]), len(result.equity_curve))
        self.assertEqual(max(Decimal(point["drawdown_pct"]) for point in payload["drawdown_curve"]),
                         result.performance.max_drawdown_pct)

    def test_parameter_defaults_keep_original_sma_rule(self):
        from examples.closed_bar_demo import SMATrend
        request, config, _, _ = validate_request(request_copy())
        original = backtest(strategy=SMATrend, candles=load_candles_csv(DATA_PATH, config=config),
                            config=config, warmup_bars=request["warmup_bars"])
        payload, _ = execute_request(request, provenance())
        self.assertEqual(payload["result"], json.loads(json_text(asdict(original))))

    def test_invalid_values_and_arbitrary_execution_rejected(self):
        variants = [
            {"strategy_id": "../../anything.py"}, {"dataset_id": "https://example.invalid/data"},
            {"initial_balance": 1000}, {"fee_rate": 0.0005}, {"slippage_bps": True},
            {"initial_balance": "NaN"}, {"initial_balance": "Infinity"},
            {"fee_rate": "-0.001"}, {"slippage_bps": "101"}, {"warmup_bars": True},
            {"warmup_bars": 1}, {"warmup_bars": 64}, {"initial_balance": "1e999"},
            {"initial_balance": "1e-999"}, {"parameters": {"period": 2, "quantity": "1.5"}},
            {"parameters": {"period": 33, "quantity": "2"}},
            {"parameters": {"period": 2, "quantity": 2}},
            {"path": "C:/secret.py"}, {"python": "print(1)"},
        ]
        for updates in variants:
            with self.subTest(updates=updates), self.assertRaises((ValueError, TypeError)):
                validate_request({**request_copy(), **updates})

    def test_changed_provenance_rejected(self):
        source = provenance()
        source["strategy"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source_changed"):
            execute_request(request_copy(), source)


class ResearchServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.service = ResearchService(self.path)
        self.service.start()
        self.addCleanup(self.service.close)

    def test_persist_result_restart_and_no_overwrite(self):
        request = request_copy()
        task = self.service.submit(request, "test-build")
        request["parameters"]["quantity"] = "999"
        completed = await_task(self.service, task["run_id"])
        self.assertEqual(completed["status"], "complete", completed)
        result = self.service.result(task["run_id"])
        self.assertEqual(result["request"]["parameters"]["quantity"], "2")
        saved = (self.path / task["run_id"] / "result.json").read_bytes()
        self.service.close()
        restart = ResearchService(self.path)
        restart.start()
        self.addCleanup(restart.close)
        self.assertEqual(restart.result(task["run_id"]), result)
        report = restart.report(task["run_id"])
        self.assertIn("<html", report)
        self.assertIn(task["run_id"], report)
        self.assertIn(result["provenance"]["dataset"]["sha256"], report)
        newer = restart.submit(request_copy(), "test-build")
        self.assertNotEqual(newer["run_id"], task["run_id"])
        self.assertEqual(await_task(restart, newer["run_id"])["status"], "complete")
        self.assertEqual((self.path / task["run_id"] / "result.json").read_bytes(), saved)

    def test_one_task_busy_and_failed_status(self):
        entered = threading.Event()
        release = threading.Event()
        def blocked(_envelope):
            entered.set()
            release.wait(5)
            raise ResearchError("fixture_failure")
        with patch.object(self.service, "_compute", blocked):
            first = self.service.submit(request_copy(), "test-build")
            self.assertTrue(entered.wait(2))
            try:
                with self.assertRaisesRegex(ResearchError, "research_busy"):
                    self.service.submit(request_copy(), "test-build")
                with self.assertRaisesRegex(ResearchError, "result_not_complete"):
                    self.service.result(first["run_id"])
            finally:
                release.set()
            result = await_task(self.service, first["run_id"])
        self.assertEqual(result["status"], "failed")
        self.assertIn("fixture_failure", result["error"])

    def test_output_single_writer(self):
        other = ResearchService(self.path)
        with self.assertRaisesRegex(ResearchError, "research_output_in_use"):
            other.start()

    def test_interrupted_jobs_not_resumed(self):
        self.service.close()
        for index, status in enumerate(("queued", "running")):
            run_id = str(index) * 32
            directory = self.path / run_id
            directory.mkdir()
            (directory / "status.json").write_text(json_text({
                "run_id": run_id, "status": status, "created_at": "2026-09-30", "error": None,
            }), encoding="utf-8")
        restart = ResearchService(self.path)
        restart.start()
        self.addCleanup(restart.close)
        for item in restart.list_runs():
            self.assertEqual(item["status"], "failed")
            self.assertEqual(item["error"], "interrupted_by_service_restart")

    def test_path_traversal_rejected(self):
        for run_id in ("..", "../../secrets", "A" * 32, "a" * 33):
            with self.subTest(run_id=run_id), self.assertRaises(ResearchError):
                self.service.task(run_id)

    def test_timeout_and_no_inherited_credentials(self):
        process = Mock()
        process.stdin, process.stdout, process.stderr = BytesIO(), BytesIO(), BytesIO()
        process.wait.side_effect = [subprocess.TimeoutExpired("trusted-worker", 30), 0]
        process.poll.return_value = -9
        benign_and_fake = {"SystemRoot": "C:/Windows", "WINDIR": "C:/Windows",
                           "FAKE_CREDENTIAL": "fixture-only", "PYTHONPATH": "forbidden-fixture"}
        with patch("catos.research_service.os.environ", benign_and_fake), \
                patch("catos.research_service.subprocess.Popen", return_value=process) as launch:
            with self.assertRaisesRegex(ResearchError, "research_timeout"):
                self.service._compute({"request": request_copy(), "provenance": provenance()})
        self.assertEqual(launch.call_args.kwargs["env"], {"SystemRoot": "C:/Windows", "WINDIR": "C:/Windows"})
        process.kill.assert_called_once()

    def test_output_cap_kills_only_owned_worker(self):
        process = Mock()
        process.stdin = BytesIO()
        process.stdout = BytesIO(b"x" * 2_000_001)
        process.stderr = BytesIO()
        process.poll.return_value = 0
        process.returncode = 0
        with patch("catos.research_service.subprocess.Popen", return_value=process):
            with self.assertRaisesRegex(ResearchError, "research_output_limit"):
                self.service._compute({"request": request_copy(), "provenance": provenance()})
        process.kill.assert_called_once()

    def test_shutdown_keeps_writer_until_active_result_finishes(self):
        entered, release, closed = threading.Event(), threading.Event(), threading.Event()
        payload, report = execute_request(request_copy(), provenance())
        def held_computation(_envelope):
            entered.set()
            release.wait(5)
            return {"payload": payload, "report": report}
        def shutdown():
            self.service.close()
            closed.set()
        with patch.object(self.service, "_compute", held_computation):
            task = self.service.submit(request_copy(), "test-build")
            self.assertTrue(entered.wait(2))
            stopping = threading.Thread(target=shutdown)
            stopping.start()
            try:
                self.assertFalse(closed.wait(0.05))
                self.assertEqual(self.service.active_run, task["run_id"])
                with self.assertRaisesRegex(ResearchError, "research_output_in_use"):
                    ResearchService(self.path).start()
            finally:
                release.set()
                stopping.join(5)
        self.assertTrue(closed.is_set())
        self.assertEqual(self.service.task(task["run_id"])["status"], "complete")


class ResearchApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = create_app(output_dir=Path(self.directory.name) / "research",
                              market_db=Path(self.directory.name) / "missing-market.sqlite")
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8770")
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.version = self.client.get("/api/research/version").json()
        self.headers = {"X-CatOS-Build": self.version["build_id"], "Origin": "http://127.0.0.1:8770"}

    def test_success_result_and_reload_read_contract(self):
        page = self.client.get("/research/")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["cache-control"], "no-store, max-age=0")
        self.assertIn(self.version["build_id"], page.text)
        asset = self.client.get("/research/assets/js/research.js")
        self.assertEqual(asset.status_code, 200)
        self.assertIn("no-store", asset.headers["cache-control"])
        catalog = self.client.get("/api/research/catalog").json()
        self.assertEqual(catalog["strategies"][0]["id"], "sma-trend")
        response = self.client.post("/api/research/backtests", json=request_copy(), headers=self.headers)
        self.assertEqual(response.status_code, 202, response.text)
        run_id = response.json()["run_id"]
        task = await_task(self.app.state.research, run_id)
        self.assertEqual(task["status"], "complete", task)
        result = self.client.get(f"/api/research/runs/{run_id}/result")
        self.assertEqual(result.status_code, 200)
        self.assertIsInstance(result.json()["result"]["performance"]["net_pnl"], str)
        self.assertEqual(self.client.get(f"/api/research/runs/{run_id}/result").json(), result.json())
        self.assertEqual(self.client.get("/api/research/runs").json()["items"][0]["run_id"], run_id)
        self.assertEqual(self.client.get(f"/api/research/runs/{run_id}/report").status_code, 200)
        # The original app root and Yaozi paths remain available.
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/app/yaozi").status_code, 200)
        unavailable = self.client.get("/intel/today")
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.json()["detail"]["reason"], "market_intel_not_found")
        self.assertFalse((Path(self.directory.name) / "missing-market.sqlite").exists())

    def test_error_contract_and_origin_version_gates(self):
        invalid = {**request_copy(), "initial_balance": 1000}
        response = self.client.post("/api/research/backtests", json=invalid, headers=self.headers)
        self.assertEqual(response.status_code, 422)
        self.assertIn("Decimal", response.json()["detail"])
        for updates, expected in (({"Origin": "http://evil.invalid"}, 403), ({"X-CatOS-Build": "old"}, 409)):
            response = self.client.post("/api/research/backtests", json=request_copy(), headers={**self.headers, **updates})
            self.assertEqual(response.status_code, expected)
        with patch("catos.research_api.files_hash", return_value="changed"):
            self.assertTrue(self.client.get("/api/research/version").json()["restart_required"])
            self.assertEqual(self.client.post("/api/research/backtests", json=request_copy(), headers=self.headers).status_code, 409)
        self.assertEqual(self.client.get("/api/research/runs/not-an-id").status_code, 400)
        self.assertEqual(self.client.get("/research/assets/not-registered.js").status_code, 404)
        self.assertEqual(self.client.get("/api/research/version", headers={"Host": "evil.invalid"}).status_code, 403)

    def test_duplicate_fields_and_request_limit(self):
        headers = {**self.headers, "Content-Type": "application/json"}
        response = self.client.post("/api/research/backtests", content='{"strategy_id":"sma-trend","strategy_id":"other"}', headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.post("/api/research/backtests", content=" " * 8193, headers=headers).status_code, 413)

    def test_port_occupied_no_fallback(self):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        self.assertEqual(main(["--port", str(listener.getsockname()[1])]), 2)


if __name__ == "__main__":
    unittest.main()
