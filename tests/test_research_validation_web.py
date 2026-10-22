"""Synthetic validation requests, real worker archives and in-process HTTP only."""

from dataclasses import asdict
from decimal import Decimal, localcontext
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from catos.research import backtest
from catos.research_api import create_app
from catos.research_catalog import DEFAULT_VALIDATION, json_text, provenance
from catos.research_regimes import REGIMES
from catos.research_service import ResearchError, ResearchService
from catos.research_validation import walk_forward
from catos.research_validation_job import (
    SCHEMA, execute_validation, validate_validation_request,
)


def request_copy():
    return json.loads(json_text(DEFAULT_VALIDATION))


def wait_for(service, run_id):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        task = service.task(run_id)
        if task["status"] in ("complete", "failed"):
            return task
        time.sleep(0.02)
    raise AssertionError("bounded synthetic validation did not finish")


class ValidationJobTests(unittest.TestCase):
    def test_combined_result_matches_core_replay_and_exact_regime_totals(self):
        request = request_copy()
        source = provenance()
        payload, report = execute_validation(request, source)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertTrue(payload["evaluation_complete"])
        result = payload["result"]
        self.assertEqual(result["validation"]["required_runs"], 12)
        self.assertEqual(result["validation"]["attempted_runs"], 12)
        self.assertEqual(result["validation"]["unused_bars"], 20)
        self.assertIn("合成資料", report)
        _, config, quantity, bars, space, plan, _ = validate_validation_request(request)
        from catos.research_catalog import load_registered_strategy
        strategy = load_registered_strategy(source)
        direct = walk_forward(
            strategy_factory=lambda params: strategy(params["period"], quantity),
            search_space={"period": space}, candles=bars, config=config,
            score=lambda p: p.return_pct, score_name="return_pct", plan=plan,
            max_candidates=3, max_runs=12,
        )
        for window, diagnostic, original in zip(result["validation"]["windows"],
                                                 result["windows"], direct.windows):
            training = window["training"]
            chosen = training["trials"][training["selected_trial_number"]]
            self.assertEqual(training["selected_trial_number"], original.training.selected_trial_number)
            start = next(i for i, bar in enumerate(bars) if bar.open_time_ms == window["test_start_ms"])
            end = start + plan.test_bars
            replay = backtest(strategy=lambda: strategy(dict(chosen["params"])["period"], quantity),
                              candles=bars[start-plan.warmup_bars:end], config=config,
                              warmup_bars=plan.warmup_bars)
            self.assertEqual(window["out_of_sample"], json.loads(json_text(asdict(replay))))
            evaluation = diagnostic["evaluation"]
            self.assertTrue(evaluation["reconciled"])
            self.assertEqual([row["regime"] for row in evaluation["summaries"]], list(REGIMES))
            self.assertEqual(sum(row["bar_count"] for row in evaluation["summaries"]), 16)
            for field in ("net_pnl", "fees", "funding_paid"):
                self.assertIsInstance(evaluation["total"][field], str)
                self.assertEqual(sum((Decimal(row[field]) for row in evaluation["summaries"]), Decimal(0)),
                                 Decimal(evaluation["total"][field]))

    def test_source_and_data_snapshots_are_bound_and_deterministic(self):
        source = provenance()
        first, _ = execute_validation(request_copy(), source)
        with localcontext() as context:
            context.prec = 5
            second, _ = execute_validation(request_copy(), source)
        self.assertEqual(first, second)
        for item in first["reproduction"]["files"]:
            self.assertEqual(sha256(item["content_utf8"].encode("utf-8")).hexdigest(), item["sha256"])
            self.assertFalse(Path(item["path"]).is_absolute())
        dataset = next(item for item in first["reproduction"]["files"] if item["path"].endswith(".csv"))
        self.assertEqual(dataset["sha256"], source["dataset"]["sha256"])
        self.assertIn("no random seed", first["reproduction"]["algorithm"])
        self.assertLess(len(json_text({"payload": first, "report": ""}).encode("utf-8")), 2_000_000)

    def test_preflight_rejects_invalid_requests_before_strategy_load(self):
        variants = [
            {"max_runs": 11}, {"max_runs": 101}, {"max_runs": True},
            {"max_candidates": 2}, {"max_candidates": 21}, {"max_candidates": 3.0},
            {"plan": {"train_bars": 24, "test_bars": 16, "windows": 9}},
            {"plan": {"train_bars": 80, "test_bars": 16, "windows": 1}},
            {"plan": {"train_bars": 0, "test_bars": 16, "windows": 1}},
            {"search_space": {"period": {"low": 2, "high": 2, "step": 1}}},
            {"search_space": {"period": {"low": 2, "high": 5, "step": 2}}},
            {"search_space": {"quantity": {"low": 1, "high": 2, "step": 1}}},
            {"backtest": {**request_copy()["backtest"], "warmup_bars": 2}},
            {"regime_rule": {"lookback_bars": 0, "trend_efficiency": "0.5", "high_volatility_bps": "250"}},
            {"regime_rule": {"lookback_bars": 4, "trend_efficiency": 0.5, "high_volatility_bps": "250"}},
            {"regime_rule": {"lookback_bars": 4, "trend_efficiency": "1.1", "high_volatility_bps": "250"}},
            {"regime_rule": {"lookback_bars": 4, "trend_efficiency": "NaN", "high_volatility_bps": "250"}},
            {"python": "forbidden"}, {"path": "../forbidden"},
        ]
        with patch("catos.research_validation_job.load_registered_strategy") as load:
            for changes in variants:
                with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                    execute_validation({**request_copy(), **changes}, provenance())
        load.assert_not_called()

    def test_changed_sources_never_produce_an_archive(self):
        source = provenance()
        source["engine_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source_changed"):
            execute_validation(request_copy(), source)
        from catos.research_validation_job import _reproduction
        with self.assertRaisesRegex(ValueError, "source_changed_during_archive"):
            _reproduction(source)

    def test_failed_oos_is_null_and_does_not_erase_training_or_other_windows(self):
        calls = 0
        def fail_one_oos(**kwargs):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise ValueError("fixture OOS failure")
            return backtest(**kwargs)
        with patch("catos.research_validation.backtest", side_effect=fail_one_oos):
            payload, _ = execute_validation(request_copy(), provenance())
        self.assertFalse(payload["evaluation_complete"])
        self.assertEqual(payload["result"]["windows"][0]["status"], "OOS_FAILED")
        self.assertIsNone(payload["result"]["windows"][0]["evaluation"])
        self.assertIn("fixture OOS failure", payload["result"]["windows"][0]["error"])
        self.assertEqual(len(payload["result"]["validation"]["windows"][0]["training"]["trials"]), 3)
        self.assertTrue(all(w["status"] == "COMPLETE" for w in payload["result"]["windows"][1:]))

    def test_no_selection_keeps_failure_records_and_unknown_zero_sample_groups(self):
        with patch("catos.research_validation.backtest", side_effect=ValueError("fixture grid failure")):
            payload, _ = execute_validation(request_copy(), provenance())
        self.assertFalse(payload["evaluation_complete"])
        self.assertEqual(payload["result"]["validation"]["attempted_runs"], 9)
        self.assertTrue(all(row["status"] == "NO_SELECTION" and row["evaluation"] is None
                            for row in payload["result"]["windows"]))
        for window in payload["result"]["validation"]["windows"]:
            self.assertIsNone(window["training"]["selected_trial_number"])
            self.assertTrue(all("fixture grid failure" in trial["error"] for trial in window["training"]["trials"]))
        request = request_copy()
        request["regime_rule"]["lookback_bars"] = 511
        payload, _ = execute_validation(request, provenance())
        for window in payload["result"]["windows"]:
            self.assertEqual(window["evaluation"]["summaries"][0]["bar_count"], 16)
            self.assertTrue(all(row["bar_count"] == 0 for row in window["evaluation"]["summaries"][1:]))


class ValidationServiceTests(unittest.TestCase):
    def test_real_worker_archive_survives_restart_and_is_not_recomputed(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ResearchService(directory)
            service.start()
            try:
                request = request_copy()
                task = service.submit_validation(request, "validation-fixture")
                request["regime_rule"]["trend_efficiency"] = "1"
                task["request"]["plan"]["windows"] = 1
                task["provenance"]["engine_sha256"] = "caller-mutated-fixture"
                completed = wait_for(service, task["run_id"])
                self.assertEqual(completed["status"], "complete", completed)
                result = service.result(task["run_id"])
                self.assertEqual(result["request"]["regime_rule"]["trend_efficiency"], "0.5")
                self.assertEqual(result["build_id"], "validation-fixture")
                self.assertEqual(result["run_id"], task["run_id"])
                self.assertEqual(result["request"]["plan"]["windows"], 3)
                self.assertEqual(result["provenance"], completed["provenance"])
                envelope = json.loads((Path(directory) / task["run_id"] / "request.json").read_text(encoding="utf-8"))
                self.assertEqual(envelope["provenance"], result["provenance"])
                self.assertEqual(envelope["request"], result["request"])
                saved = {name: (Path(directory) / task["run_id"] / name).read_bytes()
                         for name in ("request.json", "result.json", "report.html")}
            finally:
                service.close()
            restarted = ResearchService(directory)
            restarted.start()
            try:
                with patch.object(restarted, "_compute", side_effect=AssertionError("read must not compute")):
                    self.assertEqual(restarted.result(task["run_id"]), result)
                    self.assertIn(task["run_id"], restarted.report(task["run_id"]))
                    self.assertEqual(restarted.list_runs()[0]["kind"], "validation")
                for name, content in saved.items():
                    self.assertEqual((Path(directory) / task["run_id"] / name).read_bytes(), content)
            finally:
                restarted.close()

    def test_validation_uses_same_busy_slot_and_invalid_requests_write_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ResearchService(directory)
            service.start()
            try:
                with self.assertRaises(ValueError):
                    service.submit_validation({**request_copy(), "max_runs": 1}, "fixture")
                self.assertEqual([p.name for p in Path(directory).iterdir()], ["writer.lock"])
                service._active = "fixture-owned"
                with self.assertRaisesRegex(ResearchError, "research_busy"):
                    service.submit_validation(request_copy(), "fixture")
            finally:
                service._active = None
                service.close()


class ValidationApiTests(unittest.TestCase):
    def test_http_submission_gates_and_existing_query_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(output_dir=Path(directory) / "research", market_db=Path(directory) / "missing.sqlite")
            with TestClient(app, base_url="http://127.0.0.1:8770") as client:
                version = client.get("/api/research/version").json()
                headers = {"X-CatOS-Build": version["build_id"], "Origin": "http://127.0.0.1:8770"}
                example = client.get("/api/research/catalog").json()["validation"]["example_request"]
                endpoint = "/api/research/validations"
                for changes, code in (({"X-CatOS-Build": "old"}, 409), ({"Origin": "http://evil.invalid"}, 403)):
                    self.assertEqual(client.post(endpoint, json=example, headers={**headers, **changes}).status_code, code)
                self.assertEqual(client.post(endpoint, json={**example, "max_runs": 1}, headers=headers).status_code, 422)
                self.assertEqual(client.post(endpoint, content=" " * 8193,
                                             headers={**headers, "Content-Type": "application/json"}).status_code, 413)
                self.assertEqual(client.post(endpoint, content='{"plan":{},"plan":{}}',
                                             headers={**headers, "Content-Type": "application/json"}).status_code, 422)
                with patch("catos.research_api.files_hash", return_value="changed"):
                    self.assertEqual(client.post(endpoint, json=example, headers=headers).status_code, 409)
                response = client.post(endpoint, json=example, headers=headers)
                self.assertEqual(response.status_code, 202, response.text)
                run_id = response.json()["run_id"]
                self.assertEqual(wait_for(app.state.research, run_id)["status"], "complete")
                self.assertEqual(client.get("/api/research/runs").json()["items"][0]["kind"], "validation")
                result = client.get(f"/api/research/runs/{run_id}/result")
                self.assertEqual(result.status_code, 200)
                self.assertIn("no-store", result.headers["Cache-Control"])
                self.assertEqual(result.json()["schema"], SCHEMA)
                self.assertTrue(result.json()["evaluation_complete"])
                self.assertEqual(client.get(f"/api/research/runs/{run_id}/report").status_code, 200)
                self.assertFalse((Path(directory) / "missing.sqlite").exists())

    def test_preview_relays_validation_to_existing_writer_only(self):
        from catos.workspace_api import create_app as workspace_app
        from starlette.responses import JSONResponse
        with tempfile.TemporaryDirectory() as directory:
            app = workspace_app(preview=True, evidence_root=Path(directory) / "missing")
            with TestClient(app, base_url="http://127.0.0.1:8771") as client:
                with patch("catos.workspace_api.relay", return_value=JSONResponse({"run_id": "fixture"}, status_code=202)) as relay:
                    response = client.post("/api/research/validations", json=request_copy(),
                                           headers={"X-CatOS-Build": "fixture", "Origin": "http://127.0.0.1:8771"})
                self.assertEqual(response.status_code, 202)
                self.assertEqual(relay.call_args.args[0:2], ("POST", "/api/research/validations"))
                self.assertEqual(json.loads(relay.call_args.args[2]), request_copy())
                self.assertFalse(hasattr(app.state, "research"))


if __name__ == "__main__":
    unittest.main()
