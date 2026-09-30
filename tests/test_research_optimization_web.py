"""R2 registered Optuna path, shared writer and persisted candidate replay."""

from decimal import Decimal
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from catos.research_api import create_app
from catos.research_catalog import (
    DEFAULT_OPTIMIZATION, execute_request, json_text, provenance,
    validate_optimization_request,
)
from catos.research_optimization import execute_optimization
from catos.research_service import ResearchError, ResearchService


def optimization_request():
    return json.loads(json_text(DEFAULT_OPTIMIZATION))


def wait_for(service, run_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        task = service.task(run_id)
        if task["status"] in ("complete", "failed"):
            return task
        time.sleep(0.02)
    raise AssertionError("bounded synthetic optimization did not finish")


class OptimizationCatalogTests(unittest.TestCase):
    def test_exact_decimal_performance_and_candidate_replay(self):
        request = optimization_request()
        request["n_trials"] = 3
        payload, report = execute_optimization(request, provenance())
        self.assertEqual(len(payload["trials"]), 3)
        self.assertIn("未執行樣本外檢驗", report)
        self.assertEqual(payload["objective"]["name"], "return_pct")
        self.assertNotIn("score_float", payload["trials"][0])
        best = payload["trials"][payload["best_trial_number"]]
        self.assertEqual(best["score_decimal"], best["performance"]["return_pct"])
        self.assertIsInstance(best["performance"]["final_equity"], str)
        candidate = json.loads(json_text(request["backtest"]))
        candidate["parameters"]["period"] = best["params"]["period"]
        replay, _ = execute_request(candidate, provenance())
        self.assertEqual(replay["result"]["performance"], best["performance"])
        self.assertEqual(Decimal(best["score_decimal"]),
                         max(Decimal(item["score_decimal"]) for item in payload["trials"]
                             if item["state"] == "COMPLETE"))

    def test_rejects_arbitrary_or_unbounded_space(self):
        variants = (
            {"n_trials": 0}, {"n_trials": 21}, {"n_trials": True},
            {"seed": -1}, {"seed": 2 ** 32}, {"seed": 1.5},
            {"search_space": {"period": {"low": 2, "high": 7, "step": 2}}},
            {"search_space": {"period": {"low": 2, "high": 33, "step": 1}}},
            {"search_space": {"quantity": {"low": 1, "high": 2, "step": 1}}},
            {"backtest": {**optimization_request()["backtest"], "warmup_bars": 2}},
            {"python": "print(1)"},
        )
        for changes in variants:
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                validate_optimization_request({**optimization_request(), **changes})

    def test_changed_source_rejected(self):
        source = provenance()
        source["dataset"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source_changed"):
            execute_optimization(optimization_request(), source)


class OptimizationServiceTests(unittest.TestCase):
    def test_persist_reload_and_shared_busy_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ResearchService(directory)
            service.start()
            try:
                request = optimization_request()
                request["n_trials"] = 3
                task = service.submit_optimization(request, "r2-test")
                request["seed"] = 999
                self.assertEqual(task["kind"], "optimization")
                completed = wait_for(service, task["run_id"])
                self.assertEqual(completed["status"], "complete", completed)
                result = service.result(task["run_id"])
                self.assertEqual(result["request"]["seed"], 42)
                self.assertIn("未執行樣本外檢驗", service.report(task["run_id"]))
                saved = (Path(directory) / task["run_id"] / "result.json").read_bytes()
            finally:
                service.close()
            restart = ResearchService(directory)
            restart.start()
            try:
                self.assertEqual(restart.result(task["run_id"]), result)
                best = result["trials"][result["best_trial_number"]]
                replay_request = result["request"]["backtest"]
                replay_request["parameters"]["period"] = best["params"]["period"]
                backtest = restart.submit(replay_request, "r2-test")
                self.assertEqual(wait_for(restart, backtest["run_id"])["status"], "complete")
                self.assertEqual(restart.result(backtest["run_id"])["result"]["performance"],
                                 best["performance"])
                self.assertEqual((Path(directory) / task["run_id"] / "result.json").read_bytes(), saved)
                self.assertEqual(len(restart.list_runs()), 2)
            finally:
                restart.close()

    def test_optimization_rejected_while_backtest_owns_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ResearchService(directory)
            service.start()
            try:
                service._active = "fixture-running"
                with self.assertRaisesRegex(ResearchError, "research_busy"):
                    service.submit_optimization(optimization_request(), "r2-test")
            finally:
                service._active = None
                service.close()


class OptimizationApiTests(unittest.TestCase):
    def test_api_gates_and_saved_result(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(output_dir=Path(directory) / "research",
                             market_db=Path(directory) / "missing.sqlite")
            with TestClient(app, base_url="http://127.0.0.1:8770") as client:
                version = client.get("/api/research/version").json()
                headers = {"X-CatOS-Build": version["build_id"],
                           "Origin": "http://127.0.0.1:8770"}
                request = optimization_request()
                request["n_trials"] = 2
                invalid = {**request, "n_trials": 21}
                self.assertEqual(client.post("/api/research/optimizations", json=invalid,
                                             headers=headers).status_code, 422)
                self.assertEqual(client.post("/api/research/optimizations", json=request,
                                             headers={**headers, "X-CatOS-Build": "old"}).status_code, 409)
                with patch("catos.research_api.files_hash", return_value="changed"):
                    self.assertEqual(client.post("/api/research/optimizations", json=request,
                                                 headers=headers).status_code, 409)
                response = client.post("/api/research/optimizations", json=request, headers=headers)
                self.assertEqual(response.status_code, 202, response.text)
                run_id = response.json()["run_id"]
                task = wait_for(app.state.research, run_id)
                self.assertEqual(task["status"], "complete", task)
                result = client.get(f"/api/research/runs/{run_id}/result").json()
                self.assertEqual(result["kind"], "optimization")
                self.assertEqual(len(result["trials"]), 2)
                self.assertEqual(client.get(f"/api/research/runs/{run_id}/report").status_code, 200)


if __name__ == "__main__":
    unittest.main()
