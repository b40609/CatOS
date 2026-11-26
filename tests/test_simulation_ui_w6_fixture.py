"""Verify the reply fault happens after acceptance, retaining a single run."""

import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from catos import account_lock
from catos.local_sim_control_api import PREFIX
from tests.simulation_ui_w6_fixture import create_fixture
try:
    from kill_isolation import setUpModule, tearDownModule  # noqa: F401  (isolated Kill-Switch file)
except ImportError:
    from tests.kill_isolation import setUpModule, tearDownModule  # noqa: F401


class W6ReplyTests(unittest.TestCase):
    def test_accepted_reply_hidden_then_same_command_returns_original_run(self):
        root = Path(tempfile.mkdtemp(prefix="catos-w6-fixture-"))
        self.addCleanup(shutil.rmtree, root, True)
        with mock.patch.object(account_lock, "LOCK_DIRECTORY", root / "locks"), \
                mock.patch.dict(os.environ, {"CATOS_STRATEGY_APPROVALS": str(root / "approvals.jsonl"),
                                            "CATOS_STRATEGY_HOME": str(root / "strategy-home")}):
            with TestClient(create_fixture(root), base_url="http://127.0.0.1") as client:
                version = client.get(PREFIX + "/version").json()
                headers = {"X-CatOS-Build": version["build_id"], "X-CatOS-Instance": version["instance_id"]}
                body = {"request_id": "d" * 32, "template_id": "sma-synthetic-smoke-v1"}
                self.assertEqual(client.post(PREFIX + "/start", json=body, headers=headers).status_code, 503)
                items = client.get(PREFIX + "/runs").json()["items"]
                self.assertEqual(len(items), 1)
                run_id = items[0]["run_id"]
                reply = client.post(PREFIX + "/start", json=body, headers=headers)
                self.assertEqual(reply.status_code, 202)
                self.assertEqual(reply.json()["run_id"], run_id)
                self.assertEqual(len(client.get(PREFIX + "/runs").json()["items"]), 1)
                posts = client.get("/__test/observations").json()["posts"]
                self.assertEqual([p["backend_status"] for p in posts], [202, 202])
                self.assertEqual([p["client_status"] for p in posts], [503, 202])
                self.assertEqual(posts[0]["accepted_run_ids"], [run_id])
                self.assertEqual([(p["path"], p["body"], p["build"], p["instance"]) for p in posts],
                                 [(posts[0]["path"], posts[0]["body"], posts[0]["build"], posts[0]["instance"])] * 2)
                # Lifespan uses the ordinary stop/cleanup path for this held stub.
            self.assertTrue(root.joinpath("commands.jsonl").is_file())
