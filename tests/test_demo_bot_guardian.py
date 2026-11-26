"""Liveness of a demo bot run as readers see it: the shared rule, the watch tool, the Guardian.

Fixture run folders in a temporary directory; nothing connects to OKX and no notification
is shown (the Guardian's notifier is replaced).
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from catos import demo_bot_liveness as liveness
from catos.demo_bot_view import mount_demo_bot

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import demo_bot_guardian as guardian
import demo_bot_watch as watch

TF = 900_000
NOW = datetime(2026, 11, 27, 1, 0, tzinfo=UTC)
NOW_MS = int(NOW.timestamp() * 1000)


def ago(**delta):
    return (NOW - timedelta(**delta)).isoformat()


def write_run(root, run_id, *, state="running", updated=None, heartbeat=None, created=None, stop_reason=None,
              bars=269, fills=0, position="0", status=True):
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "manifest.json").write_text(json.dumps({
        "run_id": run_id, "created_at": created or ago(days=1), "mode": "okx-demo-bot", "disaster_stop": "0.1",
        "contract": {"tick_size": "0.1"}, "profile": {"timeframe_ms": TF, "inst_id": "BTC-USDT-SWAP"}}), encoding="utf-8")
    if status:
        (directory / "status.json").write_text(json.dumps({
            "state": state, "bars": bars, "fills": fills, "position": position, "stop_reason": stop_reason,
            "updated_at": updated or ago(minutes=1)}), encoding="utf-8")
    (directory / "events.jsonl").write_text("", encoding="utf-8")
    if heartbeat is not None:
        (directory / "heartbeat.json").write_text(json.dumps({"time": heartbeat, "pid": 1}), encoding="utf-8")
    return directory


class RunningProblemTests(unittest.TestCase):
    def problem(self, *, state="running", updated, heartbeat=None, tf=TF):
        return liveness.running_problem({"state": state, "updated_at": updated},
                                        None if heartbeat is None else {"time": heartbeat}, tf, NOW_MS)

    def test_fresh_bar_and_heartbeat_is_alive(self):
        self.assertIsNone(self.problem(updated=ago(minutes=14), heartbeat=ago(seconds=50)))

    def test_no_heartbeat_file_falls_back_to_the_bar_rule(self):
        self.assertIsNone(self.problem(updated=ago(minutes=31)))        # two bars plus slack is 32 minutes
        self.assertEqual(self.problem(updated=ago(minutes=33)), "bars_stalled")

    def test_old_heartbeat_means_the_process_is_gone(self):
        self.assertEqual(self.problem(updated=ago(minutes=3), heartbeat=ago(minutes=6)), "process_lost")
        self.assertIsNone(self.problem(updated=ago(minutes=3), heartbeat=ago(minutes=4)))

    def test_alive_process_without_new_bars_is_still_a_problem(self):
        self.assertEqual(self.problem(updated=ago(minutes=40), heartbeat=ago(seconds=30)), "bars_stalled")

    def test_stopped_run_is_never_stalled(self):
        self.assertIsNone(self.problem(state="stopped", updated=ago(days=6), heartbeat=ago(days=6)))

    def test_running_without_a_readable_time_is_not_reported_alive(self):
        self.assertEqual(self.problem(updated=None), "status_unreadable")
        self.assertEqual(self.problem(updated="yesterday"), "status_unreadable")
        self.assertEqual(self.problem(updated=ago(minutes=1), tf=None), "status_unreadable")


class ViewUsesTheSharedRuleTests(unittest.TestCase):
    def test_view_flags_a_run_whose_heartbeat_stopped_before_two_bars_pass(self):
        root = Path(tempfile.mkdtemp())
        real_now = datetime.now(UTC)
        write_run(root, "a" * 32, updated=(real_now - timedelta(minutes=3)).isoformat(),
                  heartbeat=(real_now - timedelta(minutes=10)).isoformat())
        app = FastAPI()
        mount_demo_bot(app, root=root)
        data = TestClient(app).get("/api/workspace/demo-bot").json()
        self.assertTrue(data["current"]["stale"])
        self.assertEqual(data["current"]["liveness"], "process_lost")


class WatchTests(unittest.TestCase):
    """The watch tool through its command line, the way the hourly check ran it."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.state = self.root / "watch-state.json"

    def run_watch(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            watch.main(["--root", str(self.root), "--state", str(self.state)])
        return json.loads(out.getvalue())

    def real_ago(self, **delta):
        return (datetime.now(UTC) - timedelta(**delta)).isoformat()

    def test_dead_run_without_fills_is_stalled_not_no_fill_yet(self):
        # The 2026-11-20 case: "running", zero fills, last bar six days ago.
        write_run(self.root, "d" * 32, updated=self.real_ago(days=6))
        self.assertEqual(self.run_watch()["verdict"], "stalled")

    def test_live_run_without_fills_is_still_no_fill_yet(self):
        write_run(self.root, "d" * 32, updated=self.real_ago(minutes=5), heartbeat=self.real_ago(seconds=20))
        self.assertEqual(self.run_watch()["verdict"], "no_fill_yet")

    def test_a_new_bar_changes_the_fingerprint(self):
        write_run(self.root, "d" * 32, updated=self.real_ago(minutes=5), bars=269)
        self.assertTrue(self.run_watch()["changed"])
        self.assertFalse(self.run_watch()["changed"])
        write_run(self.root, "d" * 32, updated=self.real_ago(minutes=1), bars=270)
        self.assertTrue(self.run_watch()["changed"])

    def test_going_stale_changes_the_fingerprint(self):
        write_run(self.root, "d" * 32, updated=self.real_ago(minutes=5), bars=269)
        self.run_watch()
        write_run(self.root, "d" * 32, updated=self.real_ago(hours=3), bars=269)
        summary = self.run_watch()
        self.assertEqual((summary["verdict"], summary["changed"]), ("stalled", True))

    def test_empty_root_reports_no_run_instead_of_crashing(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            watch.main(["--root", str(self.root)])
        self.assertEqual(json.loads(out.getvalue())["verdict"], "no_run")


class GuardianTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.state_dir = self.root / "guardian"
        self.runs = self.root / "runs"
        self.runs.mkdir()
        self.sent = []

    def check(self, now_ms=NOW_MS, notify_ok=True):
        def notify(title, body):
            self.sent.append((title, body))
            return {"ok": notify_ok, "detail": "test"}
        return guardian.run_once(root=self.runs, state_dir=self.state_dir, now_ms=now_ms, notify=notify)

    def alerts(self):
        path = self.state_dir / "alerts.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []

    def test_alive_run_is_ok_and_silent(self):
        write_run(self.runs, "a" * 32, updated=ago(minutes=5), heartbeat=ago(seconds=30))
        result = self.check()
        self.assertEqual((result["verdict"], result["problem"], self.sent), ("alive", None, []))
        saved = json.loads((self.state_dir / "last_check.json").read_text(encoding="utf-8"))
        self.assertEqual((saved["run_id"], saved["verdict"]), ("a" * 32, "alive"))
        self.assertEqual(self.alerts(), [])

    def test_dead_run_notifies_once_and_is_logged(self):
        write_run(self.runs, "a" * 32, updated=ago(days=6))
        first = self.check()
        self.assertEqual((first["verdict"], first["problem"]), ("problem", "bars_stalled"))
        self.assertEqual(len(self.sent), 1)
        self.assertIn("aaaaaaaa", self.sent[0][1])
        second = self.check(now_ms=NOW_MS + 300_000)
        self.assertEqual((second["problem"], len(self.sent)), ("bars_stalled", 1))  # same problem: no second toast
        self.assertEqual([(row["problem"], row["notified"]) for row in self.alerts()], [("bars_stalled", True)])

    def test_same_problem_is_repeated_after_six_hours(self):
        write_run(self.runs, "a" * 32, updated=ago(days=6))
        self.check()
        self.check(now_ms=NOW_MS + guardian.REPEAT_MS - 1)
        self.assertEqual(len(self.sent), 1)
        self.check(now_ms=NOW_MS + guardian.REPEAT_MS + 1)
        self.assertEqual(len(self.sent), 2)

    def test_lost_process_is_caught_by_the_heartbeat_within_minutes(self):
        write_run(self.runs, "a" * 32, updated=ago(minutes=7), heartbeat=ago(minutes=6), position="1")
        result = self.check()
        self.assertEqual(result["problem"], "process_lost")
        self.assertIn("部位 1", self.sent[0][1])

    def test_abnormal_stop_notifies_but_an_operator_stop_does_not(self):
        write_run(self.runs, "a" * 32, state="stopped", stop_reason="operator_stop_file", created=ago(days=2))
        self.assertEqual((self.check()["verdict"], self.sent), ("stopped_by_operator", []))
        write_run(self.runs, "b" * 32, state="stopped", stop_reason="position_mismatch:okx=1:ledger=0", created=ago(hours=1))
        result = self.check()
        self.assertEqual((result["run_id"], result["problem"]), ("b" * 32, "abnormal_stop"))
        self.assertEqual(len(self.sent), 1)
        self.assertIn("position_mismatch", self.sent[0][1])

    def test_failed_run_notifies(self):
        write_run(self.runs, "a" * 32, state="failed", stop_reason="PermissionError: [WinError 5]")
        self.assertEqual(self.check()["problem"], "failed")
        self.assertEqual(len(self.sent), 1)

    def test_run_that_never_wrote_a_status_is_a_problem_after_ten_minutes(self):
        write_run(self.runs, "a" * 32, status=False, created=ago(minutes=5))
        self.assertEqual(self.check()["verdict"], "starting")
        write_run(self.runs, "b" * 32, status=False, created=ago(minutes=30))
        (self.runs / ("a" * 32) / "manifest.json").unlink()
        self.assertEqual(self.check()["problem"], "never_started")

    def test_recovery_is_logged_and_a_later_problem_notifies_again(self):
        write_run(self.runs, "a" * 32, updated=ago(days=6))
        self.check()
        write_run(self.runs, "b" * 32, updated=ago(minutes=2), heartbeat=ago(seconds=10), created=ago(minutes=20))
        self.assertEqual(self.check()["verdict"], "alive")
        write_run(self.runs, "b" * 32, updated=ago(minutes=2), heartbeat=ago(minutes=30), created=ago(minutes=20))
        self.check(now_ms=NOW_MS + 60_000)
        self.assertEqual([row["problem"] for row in self.alerts()], ["bars_stalled", None, "process_lost"])
        self.assertEqual(len(self.sent), 2)

    def test_failed_notification_is_recorded_and_tried_again_next_time(self):
        write_run(self.runs, "a" * 32, updated=ago(days=6))
        self.check(notify_ok=False)
        self.assertEqual([row["notified"] for row in self.alerts()], [False])
        self.check(now_ms=NOW_MS + 300_000)
        self.assertEqual(len(self.sent), 2)

    def test_no_run_folder_is_not_a_problem(self):
        self.assertEqual((self.check()["verdict"], self.sent), ("no_run", []))

    def test_unreadable_status_is_a_problem_not_silence(self):
        directory = write_run(self.runs, "a" * 32)
        (directory / "status.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.check()["problem"], "status_unreadable")

    def test_guardian_never_writes_into_the_run_folder(self):
        directory = write_run(self.runs, "a" * 32, updated=ago(days=6))
        before = sorted(p.name for p in directory.iterdir())
        self.check()
        self.assertEqual(sorted(p.name for p in directory.iterdir()), before)

    def test_main_exit_code_tells_problem_from_ok(self):
        write_run(self.runs, "a" * 32, updated=ago(days=6))
        args = ["--root", str(self.runs), "--state-dir", str(self.state_dir), "--no-notify"]
        self.assertEqual(guardian.main(args), 2)
        write_run(self.runs, "a" * 32, state="stopped", stop_reason="operator_stop")
        self.assertEqual(guardian.main(args), 0)


if __name__ == "__main__":
    unittest.main()
