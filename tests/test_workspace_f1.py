"""Evidence reader boundaries, built-UI serving and the integrated research app."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from catos.workspace_api import create_app
from catos.workspace_snapshot import LocalSimReader, SnapshotError, MAX_METADATA
from kill_isolation import setUpModule, tearDownModule  # noqa: F401  (isolated Kill-Switch file)

RUN = "a" * 32
NOW = datetime(2026, 9, 30, 4, 0, tzinfo=timezone.utc)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "evidence"
        self.directory = self.root / RUN
        self.directory.mkdir(parents=True)
        self.reader = LocalSimReader(self.root, clock=lambda: NOW)
        self.manifest = {"run_id": RUN, "mode": "local-sim-synthetic", "bars": 32,
                         "worker_config": {}, "request": {}, "provenance": {},
                         "database": "DO_NOT_EXPOSE_OR_OPEN.sqlite3"}
        self.status = {"run_id": RUN, "state": "running", "bars": 1, "fills": 1,
                       "warmup_bars": 1, "anomalies": 0, "heartbeat_at": NOW.isoformat()}
        self.events = [
            {"kind": "warmup", "wall_time": NOW.isoformat(), "seq": 1, "target": None},
            {"kind": "signal", "wall_time": NOW.isoformat(), "seq": 2, "target": "2",
             "disposition": "RESERVED_SIMULATION", "reason": "exposure_reserved",
             "account": {"position": "0", "equity": "1000.00000000"}},
            {"kind": "fill", "wall_time": NOW.isoformat(), "seq": 2,
             "fill": {"trade_id": "fill-2", "quantity": "2", "price": "102.03", "fee": "0.00102030"},
             "request": {"side": "buy", "tag": "41cb53c54d6dABDE"}, "position": "2"},
        ]
        self.write()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, tail=b""):
        for name, value in (("manifest", self.manifest), ("status", self.status)):
            (self.directory / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
        (self.directory / "events.jsonl").write_bytes(
            b"".join(json.dumps(value).encode() + b"\n" for value in self.events) + tail)

    def test_decimal_and_decision_vs_fill_views_preserved_without_sqlite(self):
        with patch("sqlite3.connect", side_effect=AssertionError("must not open DB")):
            value = self.reader.snapshot(RUN)
        self.assertEqual(value["state"], "available")
        self.assertEqual(value["last_signal"]["account"]["position"], "0")
        self.assertEqual(value["last_fill"]["position"], "2")
        self.assertEqual(value["last_fill"]["fill"]["fee"], "0.00102030")
        self.assertIsNone(value["risk"]["can_increase"])
        self.assertIsNone(value["worker_alive"])
        self.assertNotIn("database", value["manifest"])
        self.assertEqual(value["acceptance"], "not_evaluated")

    def test_incomplete_tail_not_counted_as_event(self):
        self.write(tail=b'{"kind":"fill"')
        value = self.reader.snapshot(RUN)
        self.assertEqual(value["state"], "partial")
        self.assertIn("incomplete_tail", value["issues"])
        self.assertEqual(value["complete_event_lines"], 3)
        self.assertEqual(value["event_counts"]["fill"], 1)

    def test_status_events_race_is_explicit(self):
        self.status["bars"] = 2
        self.write()
        value = self.reader.snapshot(RUN)
        self.assertIn("status_events_syncing", value["issues"])
        self.assertEqual(value["state"], "partial")

    def test_stale_observation_does_not_change_latch_or_acceptance(self):
        self.status["heartbeat_at"] = (NOW - timedelta(seconds=121)).isoformat()
        self.write()
        value = self.reader.snapshot(RUN)
        self.assertEqual(value["state"], "stale")
        self.assertIsNone(value["risk"]["latch"])
        self.assertEqual(value["acceptance"], "not_evaluated")

    def test_finished_evidence_is_historical_not_stale(self):
        self.status.update(state="completed", heartbeat_at=(NOW - timedelta(days=1)).isoformat())
        self.write()
        self.assertEqual(self.reader.snapshot(RUN)["state"], "available")

    def test_invalid_and_traversal_ids_rejected(self):
        for value in ("../" + RUN, "C:/private", "0" * 31, RUN.upper(), None):
            with self.subTest(value=value), self.assertRaises(SnapshotError):
                self.reader.snapshot(value)

    def test_identity_mismatch_is_error(self):
        self.status["run_id"] = "b" * 32
        self.write()
        value = self.reader.snapshot(RUN)
        self.assertEqual(value["issues"], ["run_identity_mismatch"])

    def test_missing_metadata_is_unavailable(self):
        other = "b" * 32
        (self.root / other).mkdir()
        self.assertEqual(self.reader.snapshot(other)["state"], "unavailable")

    def test_malformed_complete_line_is_not_silently_skipped(self):
        self.write(tail=b'{"kind":not-json}\n')
        self.assertEqual(self.reader.snapshot(RUN)["state"], "error")

    def test_float_money_rejected(self):
        self.events[-1]["fill"]["fee"] = 0.00102030
        self.write()
        self.assertEqual(self.reader.snapshot(RUN)["issues"], ["event_decimal_text_required"])

    def test_duplicate_json_fields_rejected(self):
        (self.directory / "status.json").write_bytes(b'{"run_id":"a","run_id":"b"}')
        self.assertEqual(self.reader.snapshot(RUN)["issues"], ["invalid_evidence_json"])

    def test_oversize_metadata_rejected(self):
        (self.directory / "manifest.json").write_bytes(b" " * (MAX_METADATA + 1))
        self.assertEqual(self.reader.snapshot(RUN)["issues"], ["evidence_size_limit"])

    def test_bounded_tail_keeps_full_counts_and_sequence(self):
        value = self.reader.snapshot(RUN, limit=1)
        self.assertEqual(len(value["events"]), 1)
        self.assertEqual(value["complete_event_lines"], 3)
        self.assertEqual(value["events_omitted"], 2)
        self.assertEqual(value["last_event_seq"], 2)
        self.assertEqual(value["last_signal"]["seq"], 2)

    def test_listing_missing_root_is_empty(self):
        self.assertEqual(LocalSimReader(self.root / "absent").list_runs()["state"], "empty")

    def test_reparse_point_rejected_before_file_open(self):
        original = Path.lstat

        def info(path):
            result = original(path)
            if path == self.directory:
                class Reparse:
                    # Path.is_symlink() reads st_mode from the same lstat result.
                    st_mode = result.st_mode
                    st_file_attributes = 0x400
                return Reparse()
            return result

        with patch.object(Path, "lstat", info), self.assertRaisesRegex(SnapshotError, "linked_evidence"):
            self.reader.snapshot(RUN)


def write_dist(root):
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><div id="root"></div>'
        '<script type="module" src="/assets/app.js"></script>', encoding="utf-8")
    (dist / "assets" / "app.js").write_text("export {};", encoding="utf-8")
    (dist / "assets" / "tool.exe").write_bytes(b"x")
    (dist / "favicon.ico").write_bytes(b"ico")
    (root / "secret.txt").write_text("outside dist", encoding="utf-8")
    return dist


class WorkspaceAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def app(self):
        return create_app(output_dir=self.root / "research", evidence_root=self.root / "evidence",
                          simulation_root=self.root / "simulation", ui_dist=self.root / "dist")

    def test_built_ui_is_served_from_the_api_port(self):
        write_dist(self.root)
        with TestClient(self.app(), base_url="http://127.0.0.1") as client:
            page = client.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertIn('id="root"', page.text)
            self.assertTrue(page.headers["Content-Type"].startswith("text/html"))
            self.assertIn("script-src 'self';", page.headers["Content-Security-Policy"])
            self.assertIn("no-store", page.headers["Cache-Control"])
            script = client.get("/assets/app.js")
            self.assertEqual(script.status_code, 200)
            self.assertTrue(script.headers["Content-Type"].startswith("text/javascript"))
            self.assertEqual(script.headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(client.get("/favicon.ico").status_code, 200)
            self.assertEqual(client.get("/api/workspace/version").json()["ui"], "ready")
            self.assertEqual(client.get("/", headers={"Host": "external.invalid"}).status_code, 403)

    def test_ui_files_are_limited_to_listed_types_inside_dist(self):
        write_dist(self.root)
        with TestClient(self.app(), base_url="http://127.0.0.1") as client:
            for path in ("/assets/unknown.js", "/assets/tool.exe", "/assets/..%2F..%2Fsecret.txt",
                         "/assets/C:%5Csecret.txt", "/..%5Csecret.txt", "/.env", "/secret.txt",
                         "/workspace", "/research", "/quant", "/yaozi"):
                self.assertEqual(client.get(path).status_code, 404, path)
            self.assertEqual(client.post("/", json={}).status_code, 405)

    def test_missing_build_explains_itself_and_keeps_apis(self):
        with TestClient(self.app(), base_url="http://127.0.0.1") as client:
            page = client.get("/")
            self.assertEqual(page.status_code, 503)
            self.assertIn("尚未建置", page.text)
            self.assertEqual(client.get("/assets/app.js").status_code, 404)
            self.assertEqual(client.get("/api/workspace/version").json()["ui"], "not_built")
            self.assertEqual(client.get("/api/research/version").status_code, 200)
            self.assertEqual(
                client.get("/api/workspace/local-sim/runs/" + RUN + "?limit=201").status_code, 422)

    def test_integrated_app_uses_same_research_service_and_decimal_result(self):
        app = self.app()
        with TestClient(app, base_url="http://127.0.0.1") as client:
            version = client.get("/api/research/version").json()
            self.assertNotIn("market_status", version)
            request = client.get("/api/research/catalog").json()["defaults"]
            response = client.post("/api/research/backtests", json=request,
                                   headers={"X-CatOS-Build": version["build_id"]})
            self.assertEqual(response.status_code, 202, response.text)
            run_id = response.json()["run_id"]
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                task = client.get("/api/research/runs/" + run_id).json()
                if task["status"] in ("complete", "failed"):
                    break
                time.sleep(0.02)
            self.assertEqual(task["status"], "complete", task)
            result = client.get("/api/research/runs/" + run_id + "/result").json()
            self.assertEqual(result["result"]["performance"]["net_pnl"], "-0.79532090")
            self.assertIsInstance(result["result"]["trades"][0]["fee"], str)
            self.assertEqual(app.state.research.task(run_id), task)
            self.assertIn(run_id, [item["run_id"] for item in client.get("/api/research/runs").json()["items"]])
            self.assertEqual(client.get("/api/research/runs/" + run_id + "/report").status_code, 200)
            self.assertEqual(client.get("/api/workspace/local-sim/runs").json()["state"], "empty")


if __name__ == "__main__":
    unittest.main()
