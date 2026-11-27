"""What the Guardian says and to whom (review of 2026-11-27, F1 F2 F3 F7 F8).

Fixture run folders and a stand-in OmniKeep in a temporary directory: nothing connects to OKX,
nothing is sent to a real phone, and the real ``~/.catos/owner-alert.json`` is never read.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

from catos.demo_bot_view import mount_demo_bot

try:  # "discover -s tests" imports test modules top-level; "-m unittest tests.x" as a package
    import test_demo_bot_guardian as base
except ImportError:
    from tests import test_demo_bot_guardian as base

guardian, write_run, ago, NOW_MS = base.guardian, base.write_run, base.ago, base.NOW_MS
notifier = guardian.notifier
A, B = "a" * 32, "b" * 32


def beat(run_dir, *, position, confirmed, since=None, ratio="0.1", time=None):
    (run_dir / "heartbeat.json").write_text(json.dumps({
        "time": time or ago(seconds=20), "pid": 1, "position": position,
        "protection": {"ratio": ratio, "confirmed": confirmed, "price": "94.5" if confirmed else None, "alert": None,
                       "unprotected_since": since, "checked_at": ago(seconds=30)}}), encoding="utf-8")


def events(run_dir, *rows):
    (run_dir / "events.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class _Guardian(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.state_dir = self.root / "guardian"
        self.runs = self.root / "runs"
        self.runs.mkdir()
        self.sent, self.phone = [], []
        self.phone_answer = {"ok": True, "detail": "omnikeep:telegram=1"}

    def check(self, now_ms=NOW_MS):
        def notify(title, body):
            self.sent.append(body)
            return {"ok": True, "detail": "test"}

        def external(title, body):
            self.phone.append((title, body))
            return dict(self.phone_answer)

        return guardian.run_once(root=self.runs, state_dir=self.state_dir, now_ms=now_ms, notify=notify,
                                 external=external)

    def alerts(self):
        path = self.state_dir / "alerts.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


class UnprotectedPositionTests(_Guardian):
    """F2: alive, bars moving, and the position has no confirmed stop on OKX."""

    def test_heartbeat_reporting_no_confirmed_stop_is_a_problem_after_the_grace(self):
        run = write_run(self.runs, A, updated=ago(minutes=5), position="1")
        beat(run, position="1", confirmed=False, since=ago(minutes=10))
        result = self.check()
        self.assertEqual((result["verdict"], result["problem"]), ("problem", "position_unprotected"))
        self.assertIn("沒有已確認的保底停損", self.sent[0])
        self.assertIn("還沒確認或被 OKX 拒絕", self.sent[0])
        self.assertEqual(len(self.phone), 1)

    def test_a_gap_of_a_minute_or_a_confirmed_stop_is_not_a_problem(self):
        run = write_run(self.runs, A, updated=ago(minutes=5), position="1")
        beat(run, position="1", confirmed=False, since=ago(seconds=60))  # the stop is being placed or moved
        self.assertEqual(self.check()["verdict"], "alive")
        beat(run, position="1", confirmed=True)
        self.assertEqual(self.check()["verdict"], "alive")
        beat(run, position="0", confirmed=False)  # flat: nothing to protect
        self.assertEqual((self.check()["verdict"], self.sent), ("alive", []))

    def test_a_run_holding_with_ratio_zero_says_so(self):
        run = write_run(self.runs, A, updated=ago(minutes=5), position="1")
        beat(run, position="1", confirmed=False, since=ago(minutes=30), ratio="0")
        self.assertEqual(self.check()["problem"], "position_unprotected")
        self.assertIn("比例是 0%", self.sent[0])

    def test_a_bot_from_before_the_summary_is_judged_by_its_event_log(self):
        run = write_run(self.runs, A, updated=ago(minutes=5), heartbeat=ago(seconds=20), position="1")
        config = {"time": ago(hours=5), "kind": "protection_config", "ratio": "0.10", "source": "explicit"}
        fill = {"time": ago(minutes=20), "kind": "fill"}
        placed = {"time": ago(minutes=19), "kind": "protection", "price": "94.5", "side": "sell"}
        cases = [
            ([config, fill, placed], None),
            ([config, fill], "position_unprotected"),  # filled twenty minutes ago and no stop was ever recorded
            ([config, fill, placed, {"time": ago(minutes=9), "kind": "protection_alert",
                                     "alert": "protection_request_failed"}], "position_unprotected"),
            ([config, fill, placed, {"time": ago(minutes=9), "kind": "protection"}], "position_unprotected"),  # removed
            ([dict(config, ratio="0"), fill], "position_unprotected"),
            ([config, dict(fill, time=ago(seconds=50))], None),  # just filled: the stop is on its way
        ]
        for rows, expected in cases:
            with self.subTest(kinds=[row["kind"] for row in rows], expected=expected):
                events(run, *rows)
                self.assertEqual(self.check()["problem"], expected)

    def test_an_old_bot_that_enters_again_after_closing_gets_the_grace_again(self):
        """R4: the stop removed when the first position closed made a new entry hours later look
        unprotected since then, skipping the three minutes the new stop needs."""
        run = write_run(self.runs, A, updated=ago(minutes=5), heartbeat=ago(seconds=20), position="1")
        config = {"time": ago(hours=6), "kind": "protection_config", "ratio": "0.10", "source": "explicit"}
        first = [config, {"time": ago(hours=5), "kind": "fill"},
                 {"time": ago(hours=5), "kind": "protection", "price": "94.5", "side": "sell"},
                 {"time": ago(hours=4), "kind": "fill"}, {"time": ago(hours=4), "kind": "protection"}]
        events(run, *first, {"time": ago(seconds=30), "kind": "fill"})
        self.assertIsNone(self.check()["problem"])  # just entered again: the stop is on its way
        events(run, *first, {"time": ago(minutes=10), "kind": "fill"})
        result = self.check()
        self.assertEqual(result["problem"], "position_unprotected")
        self.assertIn("紀錄裡沒有掛上條件單", self.sent[-1])

    def test_an_old_bot_whose_stop_was_changed_on_okx_is_unprotected(self):
        """R4: ``protection_altered`` (the stop made a limit order on the OKX page) was not read."""
        run = write_run(self.runs, A, updated=ago(minutes=5), heartbeat=ago(seconds=20), position="1")
        events(run, {"time": ago(hours=5), "kind": "protection_config", "ratio": "0.10", "source": "explicit"},
               {"time": ago(minutes=40), "kind": "fill"},
               {"time": ago(minutes=40), "kind": "protection", "price": "94.5", "side": "sell"},
               {"time": ago(minutes=9), "kind": "protection_altered", "algo_id": "1"})
        self.assertEqual(self.check()["problem"], "position_unprotected")
        self.assertIn("條件單還沒確認或被 OKX 拒絕", self.sent[-1])

    def test_a_flat_old_bot_is_never_unprotected(self):
        run = write_run(self.runs, A, updated=ago(minutes=5), heartbeat=ago(seconds=20), position="0")
        events(run, {"time": ago(hours=5), "kind": "protection_config", "ratio": "0", "source": "default"})
        self.assertEqual((self.check()["verdict"], self.sent), ("alive", []))


class OtherRunsTests(_Guardian):
    def test_an_empty_newest_folder_does_not_hide_the_dead_run_that_holds_the_position(self):
        """F7 (the review's R2): a start died after writing its manifest; the real run is the older one."""
        write_run(self.runs, A, updated=ago(minutes=40), heartbeat=ago(minutes=40), position="1", created=ago(days=1))
        write_run(self.runs, B, status=False, created=ago(minutes=30))
        result = self.check()
        self.assertEqual(sorted((item["run_id"][:1], item["problem"]) for item in result["findings"]),
                         [("a", "process_lost"), ("b", "never_started")])
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(any("aaaaaaaa" in body and "部位 1" in body for body in self.sent), self.sent)

    def test_an_older_run_that_is_really_alive_is_not_reported(self):
        write_run(self.runs, A, updated=ago(minutes=4), heartbeat=ago(seconds=20), created=ago(days=1))
        write_run(self.runs, B, state="stopped", stop_reason="operator_stop", created=ago(minutes=30))
        self.assertEqual((self.check()["findings"], self.sent), ([], []))

    def test_a_stop_you_asked_for_that_leaves_a_position_is_said_once(self):
        """F8: interrupted or stop.request with the position still on OKX."""
        run = write_run(self.runs, A, state="stopped", stop_reason="interrupted", position="1")
        beat(run, position="1", confirmed=True, time=ago(hours=1))
        result = self.check()
        self.assertEqual((result["verdict"], result["problem"]), ("stopped_by_operator", None))
        self.assertEqual([item["problem"] for item in result["findings"]], ["stopped_with_position"])
        self.assertEqual(len(self.sent), 1)
        self.assertIn("部位還留在 OKX 上", self.sent[0])
        self.check(now_ms=NOW_MS + 3 * guardian.REPEAT_MS)
        self.assertEqual(len(self.sent), 1)  # a reminder, not an alarm: never repeated
        args = ["--root", str(self.runs), "--state-dir", str(self.state_dir), "--no-notify"]
        self.assertEqual(guardian.main(args), 0)

    def test_an_old_run_stopped_with_a_position_long_ago_is_not_dug_up(self):
        write_run(self.runs, A, state="stopped", stop_reason="operator_stop_file", position="1", created=ago(days=9))
        write_run(self.runs, B, updated=ago(minutes=4), heartbeat=ago(seconds=20), created=ago(hours=7))
        self.assertEqual((self.check()["findings"], self.sent), ([], []))


class ChannelTests(_Guardian):
    """F1: the phone is told, and a phone that cannot be reached never costs the local notice."""

    def test_a_problem_goes_to_this_computer_and_to_the_phone(self):
        write_run(self.runs, A, updated=ago(days=6))
        self.check()
        self.assertEqual((len(self.sent), len(self.phone)), (1, 1))
        self.assertEqual(self.phone[0][0], guardian.TITLE)
        row = self.alerts()[0]
        self.assertEqual((row["notified"], row["external"], row["external_detail"]), (True, True, "omnikeep:telegram=1"))

    def test_omnikeep_failing_keeps_the_local_notice_and_is_tried_again(self):
        write_run(self.runs, A, updated=ago(days=6))
        self.phone_answer = {"ok": False, "detail": "omnikeep_failed:exit=3:ImportError"}
        self.check()
        row = self.alerts()[0]
        self.assertEqual((row["notified"], row["external"], row["external_detail"]),
                         (True, False, "omnikeep_failed:exit=3:ImportError"))
        self.check(now_ms=NOW_MS + 300_000)
        self.assertEqual((len(self.sent), len(self.phone)), (1, 2))  # only the phone is owed
        self.phone_answer = {"ok": True, "detail": "omnikeep:telegram=1"}
        self.check(now_ms=NOW_MS + 600_000)
        self.check(now_ms=NOW_MS + 900_000)
        self.assertEqual((len(self.sent), len(self.phone)), (1, 3))  # delivered: nothing owed any more
        self.assertEqual([row.get("external") for row in self.alerts()], [False, False, True])

    def test_retries_stop_after_an_hour_until_the_six_hour_repeat(self):
        write_run(self.runs, A, updated=ago(days=6))
        self.phone_answer = {"ok": False, "detail": "omnikeep_timeout"}
        for step in range(30):
            self.check(now_ms=NOW_MS + step * 300_000)
        self.assertEqual(len(self.phone), notifier.EXTERNAL_RETRIES)
        self.check(now_ms=NOW_MS + guardian.REPEAT_MS + 1)
        self.assertEqual((len(self.sent), len(self.phone)), (2, notifier.EXTERNAL_RETRIES + 1))

    def test_no_omnikeep_configured_is_recorded_once_and_not_retried(self):
        write_run(self.runs, A, updated=ago(days=6))
        self.phone_answer = {"ok": False, "final": True, "detail": "not_configured"}
        self.check()
        self.check(now_ms=NOW_MS + 300_000)
        self.assertEqual((len(self.sent), len(self.phone)), (1, 1))
        self.assertEqual(self.alerts()[0]["external_detail"], "not_configured")

    def test_the_phone_hears_once_when_the_problem_is_over(self):
        write_run(self.runs, A, updated=ago(days=6))
        self.check()
        write_run(self.runs, A, updated=ago(minutes=2), heartbeat=ago(seconds=10))
        self.check(now_ms=NOW_MS + 60_000)
        self.check(now_ms=NOW_MS + 120_000)
        self.assertEqual([title for title, _ in self.phone], [guardian.TITLE, notifier.CLEARED_TITLE])
        self.assertEqual(len(self.sent), 1)  # no second pop-up on this computer for good news
        self.assertEqual([row["problem"] for row in self.alerts()], ["bars_stalled", None])

    def test_a_channel_that_raises_does_not_stop_the_check(self):
        write_run(self.runs, A, updated=ago(days=6))

        def broken(title, body):
            raise RuntimeError("boom")

        result = guardian.run_once(root=self.runs, state_dir=self.state_dir, now_ms=NOW_MS, notify=broken,
                                   external=broken)
        self.assertEqual(result["problem"], "bars_stalled")
        row = self.alerts()[0]
        self.assertEqual((row["notified"], row["external"], row["external_detail"]), (False, False, "raised:RuntimeError"))


class WhoWatchesTheGuardianTests(_Guardian):
    """F3: the Guardian says when it is broken, and notices when the other task went silent."""

    def main(self, **patches):
        args = ["--root", str(self.runs), "--state-dir", str(self.state_dir)]
        local = mock.Mock(return_value={"ok": True, "detail": "test"})
        phone = mock.Mock(return_value={"ok": True, "detail": "omnikeep:telegram=1"})
        with mock.patch.object(notifier, "toast", local), mock.patch.object(notifier, "external", phone):
            code = guardian.main(args)
        return code, local, phone

    def test_any_exception_is_logged_and_announced(self):
        write_run(self.runs, A, updated=ago(minutes=2), heartbeat=ago(seconds=10))
        with mock.patch.object(guardian, "run_once", side_effect=RuntimeError("not one of the five")):
            code, local, phone = self.main()
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", (self.state_dir / "errors.log").read_text(encoding="utf-8"))
        self.assertEqual((local.call_count, phone.call_count), (1, 1))
        self.assertEqual(local.call_args.args[0], guardian.SELF_TITLE)
        self.assertIn("RuntimeError", phone.call_args.args[1])

    def test_a_broken_catos_import_is_announced_too(self):
        write_run(self.runs, A, updated=ago(minutes=2), heartbeat=ago(seconds=10))
        with mock.patch.dict(sys.modules, {"catos.demo_bot_liveness": None}):
            code, local, phone = self.main()
        self.assertEqual((code, local.call_count, phone.call_count), (1, 1, 1))
        self.assertIn("ModuleNotFoundError", phone.call_args.args[1])

    def test_the_failure_is_said_once_and_cleared_by_the_next_good_check(self):
        real = datetime.now(UTC)  # main() takes the real time
        write_run(self.runs, A, updated=(real - timedelta(minutes=2)).isoformat(),
                  heartbeat=(real - timedelta(seconds=10)).isoformat())
        with mock.patch.object(guardian, "run_once", side_effect=RuntimeError("x")):
            self.main()
            code, local, phone = self.main()
        self.assertEqual((code, local.call_count, phone.call_count), (1, 0, 0))  # already said
        code, local, phone = self.main()
        self.assertEqual((code, local.call_count), (0, 0))
        self.assertEqual(phone.call_args.args[0], notifier.CLEARED_TITLE)

    def test_a_silent_autostart_task_is_a_finding(self):
        write_run(self.runs, A, updated=ago(minutes=2), heartbeat=ago(seconds=10))
        self.assertEqual(self.check()["findings"], [])  # never ran here: nothing to miss
        self.state_dir.mkdir(exist_ok=True)
        check_file = self.state_dir / guardian.AUTOSTART_CHECK
        check_file.write_text(json.dumps({"checked_at": ago(minutes=4)}), encoding="utf-8")
        self.assertEqual(self.check()["findings"], [])
        check_file.write_text(json.dumps({"checked_at": ago(minutes=20)}), encoding="utf-8")
        result = self.check()
        self.assertEqual([item["key"] for item in result["findings"]], ["watcher:autostart_silent"])
        self.assertEqual(result["verdict"], "alive")  # the Bot itself is fine
        self.assertIn("自動接續", self.sent[0])


class PageSaysWhenNobodyWatchesTests(unittest.TestCase):
    """F3: the simulation page shows a Guardian that stopped running, and a position with no stop."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.runs = self.root / "okx-demo-bot"
        self.runs.mkdir()
        self.watch = self.root / "demo-bot-guardian"
        self.real = datetime.now(UTC)

    def real_ago(self, **delta):
        return (self.real - timedelta(**delta)).isoformat()

    def overview(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        mount_demo_bot(app, root=self.runs)
        return TestClient(app).get("/api/workspace/demo-bot").json()

    def test_a_guardian_that_never_ran_or_went_silent_is_stale(self):
        write_run(self.runs, A, updated=self.real_ago(minutes=2), heartbeat=self.real_ago(seconds=10))
        watch = self.overview()["watch"]
        self.assertEqual((watch["guardian"]["stale"], watch["guardian"]["checked_at_ms"]), (True, None))
        self.watch.mkdir()
        (self.watch / "last_check.json").write_text(json.dumps({
            "checked_at": self.real_ago(minutes=3), "verdict": "alive", "findings": []}), encoding="utf-8")
        (self.watch / "autostart_check.json").write_text(json.dumps({
            "checked_at": self.real_ago(minutes=2), "action": "skip", "reason": "already_running"}), encoding="utf-8")
        watch = self.overview()["watch"]
        self.assertEqual((watch["guardian"]["stale"], watch["guardian"]["verdict"]), (False, "alive"))
        self.assertEqual((watch["autostart"]["stale"], watch["autostart"]["reason"], watch["autostart"]["disabled"]),
                         (False, "already_running", False))
        (self.watch / "last_check.json").write_text(json.dumps({
            "checked_at": self.real_ago(minutes=40), "verdict": "alive",
            "findings": [{"key": "k", "problem": "bars_stalled", "message": "m", "run_id": A}]}), encoding="utf-8")
        (self.watch / "autostart.disabled").write_text("", encoding="utf-8")
        watch = self.overview()["watch"]
        self.assertTrue(watch["guardian"]["stale"])
        self.assertEqual(watch["guardian"]["findings"], [{"problem": "bars_stalled", "message": "m"}])
        self.assertTrue(watch["autostart"]["disabled"])

    def test_a_running_position_without_a_stop_is_flagged(self):
        run = write_run(self.runs, A, updated=self.real_ago(minutes=2), position="1")
        beat(run, position="1", confirmed=False, since=self.real_ago(minutes=10), time=self.real_ago(seconds=10))
        current = self.overview()["current"]
        self.assertEqual((current["unprotected"], current["unprotected_why"], current["stale"]),
                         (True, "unconfirmed", False))
        beat(run, position="1", confirmed=True, time=self.real_ago(seconds=10))
        self.assertFalse(self.overview()["current"]["unprotected"])


class ToastTests(unittest.TestCase):
    """R1: Windows tools answer in the console code page (Big5 here). In UTF-8 mode the reader
    failed, stdout came back None, and toast() raised, so a notice already shown was sent again."""

    def test_an_unreadable_answer_still_counts_as_shown(self):
        calls = []

        def run(arguments, **options):
            calls.append((arguments[0], options))
            return subprocess.CompletedProcess(arguments, 0, stdout=None, stderr=None)

        with mock.patch.object(notifier.sys, "platform", "win32"), mock.patch.object(notifier.subprocess, "run", run):
            self.assertEqual(notifier.toast("t", "b"), {"ok": True, "detail": "toast:"})
        self.assertEqual([options.get("errors") for _, options in calls], ["replace"])

    def test_the_message_box_fallback_reads_its_answer_the_same_way(self):
        calls = []

        def run(arguments, **options):
            calls.append((arguments[0], options))
            return subprocess.CompletedProcess(arguments, 1 if arguments[0] == "powershell.exe" else 0,
                                               stdout=None, stderr=None)

        with mock.patch.object(notifier.sys, "platform", "win32"), mock.patch.object(notifier.subprocess, "run", run):
            answer = notifier.toast("t", "b")
        self.assertEqual(answer, {"ok": True, "detail": "toast_failed:; msg:0"})
        self.assertEqual([(name, options.get("errors")) for name, options in calls],
                         [("powershell.exe", "replace"), ("msg.exe", "replace")])


class OmniKeepCallTests(unittest.TestCase):
    """The contract with OmniKeep: its own interpreter, its own settings, only delivery counts back."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.omnikeep = self.root / "OmniKeep"
        (self.omnikeep / "app").mkdir(parents=True)
        (self.omnikeep / "app" / "__init__.py").write_text("", encoding="utf-8")
        self.config = self.root / "owner-alert.json"
        self.config.write_text(json.dumps({"omnikeep_root": str(self.omnikeep), "python": sys.executable}),
                               encoding="utf-8")

    def fake_owner_alert(self, body):
        (self.omnikeep / "app" / "owner_alert.py").write_text(body, encoding="utf-8")

    def answer(self, stdout="", returncode=0):
        def run(command, **options):
            self.command, self.options = command, options
            return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr="Traceback secret-token")
        return run

    def test_no_config_file_means_this_computer_only(self):
        result = notifier.external("t", "b", path=self.root / "missing.json")
        self.assertEqual(result, {"ok": False, "final": True, "detail": "not_configured"})

    def test_the_real_child_process_reaches_send_with_the_text_intact(self):
        seen = self.root / "seen.json"
        self.fake_owner_alert(
            "import json\n"
            "async def send(title, body, tag='x'):\n"
            f"    open({str(seen)!r}, 'w', encoding='utf-8').write(json.dumps([title, body, tag]))\n"
            "    print('some log line of OmniKeep')\n"
            "    return {'telegram': 1, 'web_push': 2, 'line': 0}\n")
        result = notifier.external("CatOS 模擬盤 Bot 需要你看一下", "run 16330199：部位 1", path=self.config)
        self.assertEqual(result["ok"], True, result)
        self.assertEqual(result["counts"], {"telegram": 1, "web_push": 2, "line": 0})
        self.assertEqual(json.loads(seen.read_text(encoding="utf-8")),
                         ["CatOS 模擬盤 Bot 需要你看一下", "run 16330199：部位 1", notifier.TAG])

    def test_no_channel_delivering_is_a_failure_with_the_counts(self):
        self.fake_owner_alert("async def send(title, body, tag='x'):\n    return {'telegram': 0, 'web_push': 0, 'line': 0}\n")
        result = notifier.external("t", "b", path=self.config)
        self.assertEqual((result["ok"], result["detail"]),
                         (False, "omnikeep_no_channel_delivered:line=0,telegram=0,web_push=0"))

    def test_a_crash_inside_omnikeep_is_reported_by_type_only(self):
        self.fake_owner_alert("raise RuntimeError('token=SECRET-VALUE')\n")
        result = notifier.external("t", "b", path=self.config)
        self.assertEqual((result["ok"], result["detail"]), (False, "omnikeep_failed:exit=3:RuntimeError"))
        self.assertNotIn("SECRET", json.dumps(result))

    def test_the_call_runs_omnikeeps_python_in_its_folder_and_keeps_none_of_its_output(self):
        self.fake_owner_alert("")
        marked = "noise token=SECRET\n" + notifier.RESULT_MARK + '{"telegram": 1}\n'
        result = notifier.external("標題", "內文", path=self.config, run=self.answer(marked))
        self.assertEqual(result, {"ok": True, "detail": "omnikeep:telegram=1", "counts": {"telegram": 1}})
        self.assertEqual(self.command[0], sys.executable)
        self.assertEqual(self.options["cwd"], str(self.omnikeep))
        self.assertEqual((self.options["env"]["CATOS_ALERT_TITLE"], self.options["env"]["CATOS_ALERT_BODY"]),
                         ("標題", "內文"))
        for reading in ("open(", "read_text", "dotenv", "getenv"):  # CatOS never opens OmniKeep's settings itself
            self.assertNotIn(reading, self.command[-1])
        failed = notifier.external("t", "b", path=self.config, run=self.answer("noise token=SECRET\n", returncode=1))
        self.assertEqual(failed, {"ok": False, "detail": "omnikeep_failed:exit=1:no_result"})

    def test_timeouts_missing_folders_and_bad_config_are_reasons_not_exceptions(self):
        self.fake_owner_alert("")

        def hang(command, **options):
            raise subprocess.TimeoutExpired(command, 90)

        def refuse(command, **options):
            raise PermissionError(5, "Access is denied")

        self.assertEqual(notifier.external("t", "b", path=self.config, run=hang)["detail"], "omnikeep_timeout")
        self.assertEqual(notifier.external("t", "b", path=self.config, run=refuse)["detail"],
                         "omnikeep_start_failed:PermissionError")
        (self.omnikeep / "app" / "owner_alert.py").unlink()
        self.assertEqual(notifier.external("t", "b", path=self.config)["detail"], "omnikeep_not_found")
        self.fake_owner_alert("")
        self.config.write_text(json.dumps({"omnikeep_root": str(self.omnikeep), "python": str(self.root / "no.exe")}),
                               encoding="utf-8")
        self.assertEqual(notifier.external("t", "b", path=self.config)["detail"], "omnikeep_python_not_found")
        self.config.write_text("{not json", encoding="utf-8")
        self.assertEqual(notifier.external("t", "b", path=self.config)["detail"], "config_unreadable")


if __name__ == "__main__":
    unittest.main()
