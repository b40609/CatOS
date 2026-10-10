"""Stop reply fault occurs after acceptance; terminal replay preserves metadata."""

import json
from pathlib import Path
import time
import unittest
import uuid

from fastapi.testclient import TestClient

from catos.local_sim_control_api import PREFIX
from tests.simulation_ui_w6_fixture import create_fixture


class W8ReplyTests(unittest.TestCase):
    def test_stop_reply_hidden_then_terminal_same_command_is_read_only(self):
        root = Path("outputs") / ("workspace-w8-fixture-test-" + uuid.uuid4().hex)
        root.mkdir(parents=True, exist_ok=False)
        with TestClient(create_fixture(root, hide_reply="stop"), base_url="http://127.0.0.1") as client:
            version = client.get(PREFIX + "/version").json()
            headers = {"X-CatOS-Build": version["build_id"], "X-CatOS-Instance": version["instance_id"]}
            started = client.post(PREFIX + "/start", json={"request_id": "d" * 32,
                "template_id": "sma-synthetic-smoke-v1"}, headers=headers)
            self.assertEqual(started.status_code, 202)
            run_id = started.json()["run_id"]
            path = PREFIX + "/runs/" + run_id + "/stop"
            body = {"request_id": "e" * 32}
            self.assertEqual(client.post(path, json=body, headers=headers).status_code, 503)
            post = client.get("/__test/observations").json()["posts"][1]
            self.assertEqual(post["accepted_run_id"], run_id)
            self.assertTrue(post["accepted_snapshot"]["stop_requested"])
            self.assertIsNotNone(post["accepted_snapshot"]["stop_requested_at"])
            self.assertEqual(post["accepted_stop_commands"], [body["request_id"]])
            deadline = time.monotonic() + 30
            while True:
                snapshot = client.get(path.removesuffix("/stop")).json()
                if snapshot["cleanup_confirmed"]:
                    break
                self.assertLess(time.monotonic(), deadline, "stub cleanup exceeded budget")
                time.sleep(0.1)
            self.assertEqual(snapshot["control_state"], "stopped")
            self.assertTrue(snapshot["worker_closed"])
            self.assertIsNone(snapshot["error"])
            before = (root / "simulation" / "control.json").read_bytes()
            before_version = client.get(PREFIX + "/version").json()
            before_runs = client.get(PREFIX + "/runs").json()
            reply = client.post(path, json=body, headers=headers)
            self.assertEqual(reply.status_code, 202)
            self.assertEqual(reply.json(), snapshot)
            self.assertEqual(client.get(PREFIX + "/version").json(), before_version)
            self.assertEqual(client.get(PREFIX + "/runs").json(), before_runs)
            self.assertEqual((root / "simulation" / "control.json").read_bytes(), before)
            posts = client.get("/__test/observations").json()["posts"]
            self.assertEqual([p["backend_status"] for p in posts], [202, 202, 202])
            self.assertEqual([p["client_status"] for p in posts], [202, 503, 202])
            fields = ("path", "body", "content_type", "build", "instance")
            self.assertEqual([posts[1][k] for k in fields], [posts[2][k] for k in fields])
            self.assertEqual(len(before_runs["items"]), 1)
        self.assertEqual(len((root / "commands.jsonl").read_text().splitlines()), 3)
        self.assertEqual(json.loads(before)["runs"][run_id]["stop_commands"], [body["request_id"]])
        print("Retained fixture unit evidence:", root.resolve())
