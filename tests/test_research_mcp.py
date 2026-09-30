"""R3 MCP bridge: fixed localhost registry, same R1/R2 writer and persisted runs."""

import asyncio
from io import BytesIO
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from catos.research_api import create_app
from catos import research_mcp
from catos.research_catalog import (
    APPROVED_STRATEGY_SHA256, DEFAULT_OPTIMIZATION, DEFAULT_REQUEST, STRATEGY_MANIFEST, json_text,
    execute_request, load_strategy_manifest, provenance, validate_strategy_manifest,
)
from catos.research_mcp import ResearchHttpBridge, ResearchMcpError, create_mcp_server


def copy_json(value):
    return json.loads(json_text(value))


def wait_for(service, run_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        task = service.task(run_id)
        if task["status"] in ("complete", "failed"):
            return task
        time.sleep(0.02)
    raise AssertionError("bounded R3 synthetic task did not finish")


def strategy_binding():
    strategy = provenance()["strategy"]
    return {key: strategy[key] for key in ("id", "version", "sha256")}


class LocalResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class ResearchMcpTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.app = create_app(output_dir=root / "research", market_db=root / "missing.sqlite")
        self.client = TestClient(self.app, base_url="http://127.0.0.1:8770")
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

        def open_local(request, timeout):
            self.assertEqual(timeout, 5)
            target = urlsplit(request.full_url)
            self.assertEqual((target.scheme, target.hostname, target.port),
                             ("http", "127.0.0.1", 8770))
            response = self.client.request(
                request.get_method(), target.path,
                content=request.data,
                headers=dict(request.header_items()),
            )
            if response.status_code >= 400:
                raise HTTPError(request.full_url, response.status_code, response.reason_phrase,
                                response.headers, BytesIO(response.content))
            return LocalResponse(response.content)

        self.bridge = ResearchHttpBridge(opener=open_local)

    def test_catalog_backtest_and_optimization_share_web_service(self):
        catalog = self.bridge.catalog()
        expected = provenance()["strategy"]
        strategy = catalog["strategies"][0]
        self.assertEqual((strategy["id"], strategy["version"], strategy["sha256"]),
                         (expected["id"], expected["version"], expected["sha256"]))
        self.assertEqual(strategy["source"], "approved_fixed_artifact_manifest")
        self.assertEqual(strategy["approval_state"], "approved")
        self.assertEqual(strategy["entry"], "catos.research_strategy:RegisteredSMA")
        self.assertEqual(strategy["artifact_manifest"]["schema"],
                         "catos.research.strategy-artifact")
        self.assertEqual(strategy["artifact_manifest"]["schema_version"], 1)
        self.assertEqual(strategy["source_files"], [
            "examples/closed_bar_demo.py", "catos/research_strategy.py",
        ])

        binding = strategy_binding()
        backtest = self.bridge.submit_backtest(binding, copy_json(DEFAULT_REQUEST))
        completed = wait_for(self.app.state.research, backtest["run_id"])
        self.assertEqual(completed["status"], "complete", completed)
        self.assertEqual(self.bridge.get_run(backtest["run_id"])["status"], "complete")
        result = self.bridge.get_result(backtest["run_id"])
        self.assertIsInstance(result["result"]["performance"]["net_pnl"], str)
        self.assertIn(expected["sha256"], self.bridge.get_report(backtest["run_id"]))
        web_runs = self.bridge.list_runs()["items"]
        self.assertEqual(web_runs[0]["run_id"], backtest["run_id"])
        self.assertEqual(web_runs, self.client.get("/api/research/runs").json()["items"])

        request = copy_json(DEFAULT_OPTIMIZATION)
        request["n_trials"] = 2
        optimization = self.bridge.submit_optimization(binding, request)
        completed = wait_for(self.app.state.research, optimization["run_id"])
        self.assertEqual(completed["status"], "complete", completed)
        optimized = self.bridge.get_result(optimization["run_id"])
        self.assertEqual(optimized["kind"], "optimization")
        self.assertEqual(len(optimized["trials"]), 2)
        self.assertEqual(self.client.get(
            f"/api/research/runs/{optimization['run_id']}/result").json(), optimized)

    def test_fixed_artifact_manifest_is_exact_approved_and_fail_closed(self):
        manifest = load_strategy_manifest()
        self.assertEqual(manifest["artifact_id"], "sma-trend")
        self.assertEqual(manifest["version"], "sma-parameters-v1")
        self.assertEqual(manifest["sha256"], APPROVED_STRATEGY_SHA256)
        self.assertEqual(manifest["approval_state"], "approved")
        self.assertEqual(manifest["entry"], "catos.research_strategy:RegisteredSMA")
        self.assertEqual(validate_strategy_manifest(copy_json(manifest)), manifest)

        cases = []
        wrong_hash = copy_json(manifest)
        wrong_hash["sha256"] = "0" * 64
        cases.append((wrong_hash, "artifact_identity_mismatch"))
        wrong_version = copy_json(manifest)
        wrong_version["version"] = "sma-parameters-v2"
        cases.append((wrong_version, "artifact_version_mismatch"))
        unapproved = copy_json(manifest)
        unapproved["approval_state"] = "pending"
        cases.append((unapproved, "artifact_not_approved"))
        unknown = copy_json(manifest)
        unknown["artifact_id"] = "other-strategy"
        cases.append((unknown, "unknown_artifact"))
        missing = copy_json(manifest)
        missing.pop("entry")
        cases.append((missing, "artifact_manifest_exact_fields_required"))
        extra = copy_json(manifest)
        extra["note"] = "not part of the approved schema"
        cases.append((extra, "artifact_manifest_exact_fields_required"))
        for value, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    validate_strategy_manifest(value)

        for forbidden in ("path", "url", "python", "command", "credential", "database"):
            value = copy_json(manifest)
            value[forbidden] = "forbidden"
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(ValueError, "artifact_manifest_exact_fields_required"):
                    validate_strategy_manifest(value)

        with patch("catos.research_catalog._verified_strategy_source_snapshot",
                   return_value=({}, "f" * 64)):
            with self.assertRaisesRegex(ValueError, "artifact_hash_mismatch"):
                load_strategy_manifest()

        # The immutable version is bound to the reviewed digest. Updating source
        # and the manifest together cannot silently redefine sma-parameters-v1.
        changed = copy_json(manifest)
        changed["sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "artifact_identity_mismatch"):
            validate_strategy_manifest(changed)

    def test_rejects_arbitrary_inputs_external_endpoint_and_stale_source(self):
        with self.assertRaisesRegex(ValueError, "127_0_0_1"):
            ResearchHttpBridge("https://example.invalid:8770")
        with self.assertRaisesRegex(ResearchMcpError, "invalid_run_id"):
            self.bridge.get_run("../../anything")
        invalid = {**copy_json(DEFAULT_REQUEST), "python": "print(1)"}
        with self.assertRaisesRegex(ResearchMcpError, "research_http_422"):
            self.bridge.submit_backtest(strategy_binding(), invalid)
        wrong = strategy_binding()
        wrong["sha256"] = "0" * 64
        with self.assertRaisesRegex(ResearchMcpError, "strategy_binding_mismatch"):
            self.bridge.submit_backtest(wrong, copy_json(DEFAULT_REQUEST))
        extra = {**strategy_binding(), "path": "anything.py"}
        with self.assertRaisesRegex(ResearchMcpError, "strategy_binding_exact_fields_required"):
            self.bridge.submit_backtest(extra, copy_json(DEFAULT_REQUEST))
        with patch("catos.research_api.files_hash", return_value="changed"):
            with self.assertRaisesRegex(ResearchMcpError, "source_changed_restart_required"):
                self.bridge.submit_backtest(strategy_binding(), copy_json(DEFAULT_REQUEST))

    def test_strategy_source_is_revalidated_before_execution(self):
        expected = provenance()
        changed = {**expected, "engine_sha256": "changed"}
        with patch("catos.research_catalog.provenance", return_value=changed), \
                patch("catos.research_catalog._strategy_from_verified_snapshot") as execute_source:
            with self.assertRaisesRegex(ValueError, "source_changed_restart_required"):
                execute_request(copy_json(DEFAULT_REQUEST), expected)
            execute_source.assert_not_called()

        from catos import research_optimization
        with patch("catos.research_catalog.provenance", return_value=changed), \
                patch("catos.research_catalog._strategy_from_verified_snapshot") as execute_source:
            with self.assertRaisesRegex(ValueError, "source_changed_restart_required"):
                research_optimization.execute_optimization(copy_json(DEFAULT_OPTIMIZATION), expected)
            execute_source.assert_not_called()

        # If files change after the provenance check, the newly read snapshot
        # must fail its approved digest before any strategy source is executed.
        with patch("catos.research_catalog.provenance", return_value=expected), \
                patch("catos.research_catalog._verified_strategy_source_snapshot",
                      return_value=({}, "f" * 64)), \
                patch("catos.research_catalog._strategy_from_verified_snapshot") as execute_source:
            with self.assertRaisesRegex(ValueError, "artifact_hash_mismatch"):
                execute_request(copy_json(DEFAULT_REQUEST), expected)
            execute_source.assert_not_called()

    def test_mcp_and_web_share_one_busy_slot(self):
        entered = threading.Event()
        release = threading.Event()
        original = self.app.state.research._compute

        def blocked(envelope):
            entered.set()
            if not release.wait(5):
                raise AssertionError("busy-slot test release timed out")
            return original(envelope)

        with patch.object(self.app.state.research, "_compute", side_effect=blocked):
            first = self.bridge.submit_backtest(strategy_binding(), copy_json(DEFAULT_REQUEST))
            self.assertTrue(entered.wait(2))
            version = self.client.get("/api/research/version").json()
            try:
                response = self.client.post(
                    "/api/research/backtests", json=copy_json(DEFAULT_REQUEST),
                    headers={"X-CatOS-Build": version["build_id"]},
                )
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()["detail"], "research_busy")
            finally:
                release.set()
            self.assertEqual(wait_for(self.app.state.research, first["run_id"])["status"], "complete")

    def test_mcp_surface_is_only_registered_research_operations(self):
        server = create_mcp_server(self.bridge)
        tools = asyncio.run(server.list_tools())
        self.assertEqual({tool.name for tool in tools}, {
            "research_catalog", "research_list_runs", "research_submit_backtest",
            "research_submit_optimization", "research_get_run", "research_get_result",
            "research_get_report",
        })
        serialized = json.dumps([tool.model_dump(mode="json") for tool in tools])
        for forbidden in ("url", "path", "python", "credential", "database"):
            self.assertNotIn(f'"{forbidden}"', serialized.lower())
        self.assertFalse(hasattr(research_mcp, "ResearchService"))
        source = Path(research_mcp.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from catos.research_service import", source)
        self.assertNotIn("ResearchService(", source)
        self.assertTrue(STRATEGY_MANIFEST.is_file())


if __name__ == "__main__":
    unittest.main()
