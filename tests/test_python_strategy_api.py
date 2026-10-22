"""Real API requests to isolated metadata; no product data or network provider."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import unittest

from catos.local_sim_control import LocalSimControlService
from catos.local_sim_control_api import mount_simulation, PREFIX
from catos.strategy_mcp import create_server
from test_python_strategy_v1 import manifest, command

class PythonApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = LocalSimControlService(Path(self.temp.name) / "runs")
        self.app = mount_simulation(FastAPI(), self.service.root, service=self.service)
        self.client = self.enterContext(TestClient(self.app, base_url="http://127.0.0.1:9123"))
        self.headers = {"X-CatOS-Build": self.service.loaded_build, "X-CatOS-Instance": self.service.instance_id}

    def post(self, suffix, value, headers=None):
        return self.client.post(PREFIX + suffix, json=value, headers=self.headers if headers is None else headers)

    def test_file_json_contract_and_version_conflict_do_not_load_source(self):
        value = manifest()
        value["source"] = 'raise RuntimeError("never_in_parent")\n' + value["source"]
        request = command()
        reply = self.post("/strategies", dict(request_id=request, manifest=value))
        self.assertEqual(reply.status_code, 201)
        self.assertEqual(self.post("/strategies", dict(request_id=request, manifest=value)).json(), reply.json())
        changed = {**value, "description": "modified"}
        self.assertEqual(self.post("/strategies", dict(request_id=command(), manifest=changed)).status_code, 409)
        self.assertEqual(self.post("/strategies", dict(request_id=request, manifest=manifest("v2"))).status_code, 409)
        self.assertEqual(self.client.get(PREFIX + "/strategies").json()["items"], [reply.json()])
        self.assertIsNone(self.service.task)

    def test_human_trust_mode_snapshot_and_cross_operation_retry(self):
        created = self.post("/strategies", dict(request_id=command(), manifest=manifest())).json()
        request = command()
        body = dict(request_id=request, bot_id="manual-bot", artifact_hash=created["artifact_hash"],
                    parameters={"quantity": "-2", "hold": False}, trusted=True, mode="local")
        self.assertEqual(self.post("/bots", {**body, "trusted": False}).status_code, 422)
        self.assertEqual(self.post("/bots", {**body, "mode": "demo"}).status_code, 422)
        self.assertEqual(self.post("/bots", {**body, "parameters": {"quantity": 0.1}}).status_code, 422)
        allocated = self.post("/bots", body)
        self.assertEqual(allocated.status_code, 201)
        self.assertEqual(self.post("/bots", body).json(), allocated.json())
        self.assertEqual(self.post("/bots", {**body, "parameters": {"quantity": "-3"}}).status_code, 409)
        self.assertEqual(self.post("/bots/start", {"request_id": request, "bot_id": "manual-bot"}).status_code, 409)
        self.assertEqual(self.client.get(PREFIX + "/bots").json()["items"], [allocated.json()])

    def test_stale_instance_origin_and_shape_reject_before_creation(self):
        value = dict(request_id=command(), manifest=manifest())
        self.assertEqual(self.post("/strategies", value, {}).status_code, 409)
        self.assertEqual(self.post("/strategies", value, {**self.headers, "Origin": "https://external.invalid"}).status_code, 403)
        self.assertEqual(self.post("/strategies", {**value, "start": True}).status_code, 422)
        self.assertEqual(self.client.get(PREFIX + "/strategies").json()["items"], [])

    def test_mcp_surface_has_only_five_artifact_result_tools(self):
        self.assertEqual(set(create_server()._tool_manager._tools), {
            "strategy_contract", "list_strategy_versions", "create_strategy_version",
            "list_simulation_results", "get_simulation_result"})

if __name__ == "__main__":
    unittest.main()
