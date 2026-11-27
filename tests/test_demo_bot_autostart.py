"""Autostart of the OKX Demo Bot (authorised 2026-11-27): which interruptions it continues,
which stops it must never restart, and what it tells the owner.

Fixture run folders, an isolated Kill-Switch record and a stand-in for both the task launcher
and the Bot: nothing connects to OKX, no task is run and no notification is shown.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from catos import kill_switch, strategy_approvals

try:  # "discover -s tests" imports test modules top-level; "-m unittest tests.x" as a package
    import test_demo_bot_guardian as base
except ImportError:
    from tests import test_demo_bot_guardian as base

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import demo_bot_autostart as autostart

guardian, ago, NOW_MS = base.guardian, base.ago, base.NOW_MS
A, B = "a" * 32, "b" * 32
APPROVED = strategy_approvals.load_profile(autostart.PROFILE)


class _Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.state_dir = self.root / "guardian"
        self.runs = self.root / "runs"
        self.runs.mkdir()
        self.kill = self.root / "kill-switch.jsonl"
        self.sent, self.phone, self.launched = [], [], []
        self.launch_answer = {"ok": True, "detail": "schtasks:0"}

    def run_folder(self, run_id=A, *, profile=APPROVED, **fields):
        directory = base.write_run(self.runs, run_id, **fields)
        path = directory / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(dict(manifest, profile=profile)), encoding="utf-8")
        return directory

    def lost(self, run_id=A, **fields):
        """Says running, heartbeat ten minutes old, holding 1: the computer restarted under it."""
        return self.run_folder(run_id, **{"updated": ago(minutes=12), "heartbeat": ago(minutes=10), "position": "1",
                                          **fields})

    def stopped(self, reason, **fields):
        return self.run_folder(state="stopped", stop_reason=reason, **fields)

    def decide(self, now_ms=NOW_MS, **options):
        return autostart.decide(root=self.runs, state_dir=self.state_dir, now_ms=now_ms, kill_path=self.kill,
                                **options)

    def gate(self, now_ms=NOW_MS, **options):
        def notify(title, body):
            self.sent.append(body)
            return {"ok": True, "detail": "test"}

        def external(title, body):
            self.phone.append((title, body))
            return {"ok": True, "detail": "omnikeep:telegram=1"}

        def start():
            self.launched.append(now_ms)
            return dict(self.launch_answer)

        return autostart.gate_once(root=self.runs, state_dir=self.state_dir, now_ms=now_ms, kill_path=self.kill,
                                   notify=notify, external=external, start=start, **options)

    def history(self):
        path = self.state_dir / autostart.HISTORY_FILE
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []


class ContinuesAnInterruptionTests(_Base):
    def test_a_lost_process_is_started_again_with_the_ten_percent_stop_announced(self):
        self.lost()
        result = self.gate()
        self.assertEqual((result["action"], result["reason"], result["run_id"]), ("start", "process_lost", A))
        self.assertEqual(len(self.launched), 1)
        self.assertEqual((len(self.sent), len(self.phone)), (1, 1))
        self.assertIn("10%", self.sent[0])
        self.assertIn("部位 1", self.sent[0])
        self.assertEqual([row["action"] for row in self.history()], ["start", "start_announced"])

    def test_stops_caused_by_okx_or_a_missing_bar_are_continued(self):
        for reason in ("okx_read_failed:50001", "bar_not_published:1795750000000", "bar_gap:expected=1:got=2",
                       "process_lost"):
            with self.subTest(reason=reason):
                self.setUp()
                self.stopped(reason, position="1")
                self.assertEqual((self.decide()["action"], self.decide()["reason"]), ("start", "transient_stop"))

    def test_a_start_that_never_wrote_a_status_is_tried_again(self):
        self.run_folder(status=False, created=ago(minutes=30))
        self.assertEqual((self.decide()["action"], self.decide()["reason"]), ("start", "never_started"))
        self.setUp()
        self.run_folder(status=False, created=ago(minutes=3))  # still inside its ten minutes
        self.assertEqual((self.decide()["action"], self.decide()["reason"]), ("skip", "starting"))

    def test_the_bot_is_given_exactly_the_approved_profile_and_ten_percent(self):
        self.lost()
        calls = []

        def bot(arguments):
            calls.append(arguments)
            print("金鑰：…（Bot 的輸出）")
            return 0

        before = sys.stdout, sys.stderr
        code = autostart.run_bot(root=self.runs, state_dir=self.state_dir, now_ms=NOW_MS, kill_path=self.kill, bot=bot)
        self.assertEqual(code, 0)
        self.assertEqual(calls, [["--profile", str(autostart.PROFILE), "--disaster-stop", "10%"]])
        self.assertIn("Bot 的輸出", (self.state_dir / autostart.BOT_LOG).read_text(encoding="utf-8"))
        self.assertEqual([row["action"] for row in self.history()], ["bot_started", "bot_exit"])
        self.assertEqual((sys.stdout, sys.stderr), before)  # the redirection ends with the Bot

    def test_the_fixed_arguments_are_accepted_by_the_real_command_line(self):
        from catos import demo_bot

        args = demo_bot._parser().parse_args(["--profile", str(autostart.PROFILE), "--disaster-stop",
                                              autostart.DISASTER_STOP])
        self.assertEqual(str(args.disaster_stop), "0.1")
        self.assertTrue(autostart.PROFILE.is_file())


class NeverRestartsARiskStopTests(_Base):
    def test_risk_stops_are_refused_and_announced_once(self):
        for reason in ("risk_flat:hard_loss", "risk_flat:manual_kill", "manual_kill:kill-switch-0123abcd",
                       "flatten_failed:flatten_incomplete:okx_position=1", "flatten_incomplete:okx_position=1"):
            with self.subTest(reason=reason):
                self.setUp()
                self.stopped(reason)
                result = self.gate()
                self.assertEqual((result["action"], result["reason"]), ("refuse", "risk_stop"))
                self.assertEqual(self.launched, [])
                self.assertEqual((len(self.sent), len(self.phone)), (1, 1))
                self.assertIn("風控停機", self.sent[0])
                self.assertIn("不會自動重開", self.sent[0])
                self.gate(now_ms=NOW_MS + 300_000)
                self.gate(now_ms=NOW_MS + 7 * 3_600_000)
                self.assertEqual((self.launched, len(self.sent), len(self.phone)), ([], 1, 1))

    def test_an_engaged_kill_switch_refuses_even_a_lost_process(self):
        self.lost()
        kill_switch.engage(reason="test", actor="cli", path=self.kill)
        result = self.gate()
        self.assertEqual((result["action"], result["reason"], self.launched), ("refuse", "kill_switch_engaged", []))
        self.assertIn("Kill-Switch", self.sent[0])
        self.assertEqual(autostart.run_bot(root=self.runs, state_dir=self.state_dir, now_ms=NOW_MS, kill_path=self.kill,
                                           bot=self.fail), 2)

    def test_an_unreadable_kill_switch_record_counts_as_engaged(self):
        self.lost()
        self.kill.write_text("{not a record\n", encoding="utf-8")
        self.assertEqual((self.decide()["action"], self.decide()["reason"]), ("refuse", "kill_switch_unreadable"))

    def test_a_clear_kill_switch_record_does_not_block(self):
        self.lost()
        kill_switch.engage(reason="test", actor="cli", path=self.kill)
        kill_switch.clear(reason="test over", actor="cli", confirm="解除", path=self.kill)  # isolated test record
        self.assertEqual(self.decide()["action"], "start")

    def test_every_other_stop_reason_needs_the_user(self):
        reasons = ("position_mismatch:okx=1:ledger=0", "disaster_stop_triggered", "disaster_stop_incomplete:okx=1",
                   "order_partially_filled:canceled", "protection_config_failed:x", "resume_position_mismatch:okx=1",
                   "foreign_algo_orders_on_contract:abc", "approval_or_source_invalid:x", "supervisor_failed:x",
                   "a_reason_added_later")
        for reason in reasons:
            with self.subTest(reason=reason):
                self.setUp()
                self.stopped(reason)
                self.assertEqual((self.decide()["action"], self.decide()["reason"]), ("refuse", "needs_review"))

    def test_failed_and_unreadable_runs_are_refused(self):
        self.run_folder(state="failed", stop_reason="KeyError: 'x'")
        self.assertEqual((self.decide()["action"], self.decide()["reason"]), ("refuse", "run_failed"))
        self.setUp()
        directory = self.run_folder()
        (directory / "status.json").write_text("{not json", encoding="utf-8")
        self.assertEqual((self.decide()["action"], self.decide()["reason"]), ("refuse", "status_unreadable"))

    def test_only_the_approved_profile_is_continued(self):
        self.lost(profile=dict(APPROVED, timeframe_ms=300_000))  # e.g. the 5m test deployment
        result = self.gate()
        self.assertEqual((result["action"], result["reason"], self.launched), ("refuse", "profile_differs", []))
        self.setUp()
        self.lost()
        with mock.patch.object(autostart, "PROFILE", self.root / "missing.json"):
            decision = autostart.decide(root=self.runs, state_dir=self.state_dir, now_ms=NOW_MS, kill_path=self.kill,
                                        profile=self.root / "missing.json")
        self.assertEqual((decision["action"], decision["reason"]), ("refuse", "profile_unreadable"))

    def fail(self, arguments):
        raise AssertionError("the Bot must not be started")

    def test_the_bots_own_task_refuses_too_when_asked_by_hand(self):
        self.stopped("risk_flat:hard_loss")
        self.assertEqual(autostart.run_bot(root=self.runs, state_dir=self.state_dir, now_ms=NOW_MS, kill_path=self.kill,
                                           bot=self.fail), 2)
        self.assertEqual([row["action"] for row in self.history()], ["bot_not_started"])


class LeavesAloneTests(_Base):
    def test_a_live_bot_is_left_alone(self):
        self.run_folder(updated=ago(minutes=4), heartbeat=ago(seconds=20))
        result = self.gate()
        self.assertEqual((result["action"], result["reason"]), ("skip", "already_running"))
        self.assertEqual((self.launched, self.sent, self.phone), ([], [], []))
        self.assertEqual(autostart.run_bot(root=self.runs, state_dir=self.state_dir, now_ms=NOW_MS, kill_path=self.kill,
                                           bot=NeverRestartsARiskStopTests.fail.__get__(self)), 0)

    def test_a_bot_whose_process_lives_is_not_started_twice(self):
        self.run_folder(updated=ago(minutes=50), heartbeat=ago(seconds=20))  # no bars, but the process is there
        self.assertEqual((self.decide()["action"], self.decide()["reason"]), ("skip", "alive_but_stalled"))
        directory = self.run_folder(updated=ago(minutes=4), position="1")
        base_beat = {"time": ago(seconds=20), "pid": 1, "position": "1", "protection": {
            "ratio": "0.1", "confirmed": False, "price": None, "alert": "protection_request_failed",
            "unprotected_since": ago(minutes=20), "checked_at": ago(seconds=30)}}
        (directory / "heartbeat.json").write_text(json.dumps(base_beat), encoding="utf-8")
        self.assertEqual((self.decide()["action"], self.decide()["reason"]), ("skip", "already_running"))

    def test_the_live_run_may_be_an_older_folder(self):
        self.run_folder(A, updated=ago(minutes=4), heartbeat=ago(seconds=20), created=ago(days=1))
        self.run_folder(B, status=False, created=ago(minutes=30))
        self.assertEqual((self.decide()["action"], self.decide()["reason"]), ("skip", "already_running"))

    def test_a_stop_the_user_asked_for_is_never_undone(self):
        for reason in ("operator_stop", "operator_stop_file", "interrupted"):
            with self.subTest(reason=reason):
                self.setUp()
                self.stopped(reason, position="1")
                result = self.gate()
                self.assertEqual((result["action"], result["reason"]), ("skip", "stopped_by_operator"))
                self.assertEqual((self.launched, self.sent), ([], []))

    def test_nothing_is_started_from_nothing_or_when_switched_off(self):
        self.assertEqual((self.gate()["action"], self.gate()["reason"]), ("skip", "no_previous_run"))
        self.lost()
        (self.state_dir / autostart.DISABLED_FILE).write_text("", encoding="utf-8")
        result = self.gate()
        self.assertEqual((result["action"], result["reason"], self.launched), ("skip", "disabled_by_file", []))

    def test_the_gate_never_writes_into_a_run_folder_and_a_dry_run_writes_nothing_at_all(self):
        directory = self.lost()
        before = sorted(p.name for p in directory.iterdir())
        result = self.gate(dry_run=True)
        self.assertEqual((result["action"], self.launched, self.sent), ("start", [], []))
        self.assertEqual([p.name for p in self.state_dir.iterdir()], [])
        self.gate()
        self.assertEqual(sorted(p.name for p in directory.iterdir()), before)


class LimitsTests(_Base):
    def test_a_second_start_waits_ten_minutes(self):
        self.lost()
        self.gate()
        self.assertEqual(self.gate(now_ms=NOW_MS + 300_000)["reason"], "cooling_down")
        self.assertEqual(len(self.launched), 1)
        self.assertEqual(self.gate(now_ms=NOW_MS + 660_000)["action"], "start")
        self.assertEqual(len(self.launched), 2)

    def test_the_fourth_start_in_a_day_is_refused_and_said(self):
        self.lost()
        for step in range(3):
            self.assertEqual(self.gate(now_ms=NOW_MS + step * 3_600_000)["action"], "start")
        result = self.gate(now_ms=NOW_MS + 4 * 3_600_000)
        self.assertEqual((result["action"], result["reason"]), ("refuse", "too_many_restarts"))
        self.assertEqual(len(self.launched), 3)
        self.assertIn("3 次", self.sent[-1])
        self.assertEqual(self.gate(now_ms=NOW_MS + 25 * 3_600_000)["action"], "start")  # the first one aged out

    def test_starts_that_died_at_once_do_not_use_up_the_three(self):
        self.lost()
        for step in range(5):  # e.g. the network was not up yet after a restart
            at = NOW_MS + step * 660_000
            self.assertEqual(self.gate(now_ms=at)["action"], "start", step)
            autostart.record(self.state_dir, at + 20_000, action="bot_exit", code=1, seconds=20, run_id=A)
        at = NOW_MS + 5 * 660_000
        self.assertEqual(self.gate(now_ms=at)["action"], "start")
        autostart.record(self.state_dir, at + 20_000, action="bot_exit", code=1, seconds=20, run_id=A)
        result = self.gate(now_ms=NOW_MS + 6 * 660_000)
        self.assertEqual((result["action"], result["reason"]), ("refuse", "too_many_failed_starts"))

    def test_a_task_that_cannot_be_run_is_said_not_swallowed(self):
        self.lost()
        self.launch_answer = {"ok": False, "detail": "schtasks:1"}
        result = self.gate()
        self.assertEqual((result["action"], result["reason"]), ("refuse", "launch_failed"))
        self.assertIn("工作排程器", self.sent[0])


class EachWatchesTheOtherTests(_Base):
    def test_the_gate_leaves_a_trace_the_guardian_accepts(self):
        self.run_folder(updated=ago(minutes=4), heartbeat=ago(seconds=20))
        self.gate()
        seen = json.loads((self.state_dir / autostart.CHECK_FILE).read_text(encoding="utf-8"))
        self.assertEqual((seen["action"], seen["reason"]), ("skip", "already_running"))
        self.assertIsNone(guardian.watcher_finding(self.state_dir, NOW_MS + 600_000))
        self.assertIsNotNone(guardian.watcher_finding(self.state_dir, NOW_MS + 1_000_000))

    def test_a_silent_guardian_is_announced_from_here(self):
        self.run_folder(updated=ago(minutes=4), heartbeat=ago(seconds=20))
        self.state_dir.mkdir()
        last = self.state_dir / "last_check.json"
        last.write_text(json.dumps({"checked_at": ago(minutes=3)}), encoding="utf-8")
        self.assertFalse(self.gate()["guardian_silent"])
        last.write_text(json.dumps({"checked_at": ago(minutes=40)}), encoding="utf-8")
        self.assertTrue(self.gate()["guardian_silent"])
        self.assertEqual((len(self.sent), len(self.phone)), (1, 1))
        self.assertEqual(self.phone[0][0], guardian.SELF_TITLE)
        self.gate(now_ms=NOW_MS + 60_000)
        self.assertEqual(len(self.sent), 1)

    def test_its_own_failure_is_logged_and_announced(self):
        local = mock.Mock(return_value={"ok": True, "detail": "test"})
        phone = mock.Mock(return_value={"ok": True, "detail": "omnikeep:telegram=1"})
        with mock.patch.object(autostart, "gate_once", side_effect=RuntimeError("x")), \
                mock.patch.object(autostart.notifier, "toast", local), \
                mock.patch.object(autostart.notifier, "external", phone):
            code = autostart.main(["--root", str(self.runs), "--state-dir", str(self.state_dir)])
        self.assertEqual((code, local.call_count, phone.call_count), (1, 1, 1))
        self.assertIn("RuntimeError", (self.state_dir / "errors.log").read_text(encoding="utf-8"))


class SecondReviewTests(_Base):
    """Cross review of 2026-11-27 (R1 R2 R3): edges of the gate found after the first fixes."""

    def test_a_launch_that_keeps_failing_is_said_once_and_never_counted_as_a_restart(self):
        """R2: the start was recorded before the launch, so a failed launch cooled down, cleared its
        alert, alerted again and after three tries claimed three restarts that never happened."""
        self.lost()
        self.launch_answer = {"ok": False, "detail": "schtasks:1"}
        seen = [self.gate(now_ms=NOW_MS + step * 300_000)["reason"] for step in range(8)]
        self.assertEqual(set(seen), {"launch_failed"}, seen)
        self.assertEqual(len(self.sent), 1, self.sent)
        self.assertNotIn("start", [row.get("action") for row in self.history()])
        self.assertIn("launch_failed", [row.get("action") for row in self.history()])
        self.launch_answer = {"ok": True, "detail": "schtasks:0"}  # Task Scheduler works again
        self.assertEqual(self.gate(now_ms=NOW_MS + 8 * 300_000)["action"], "start")
        self.assertEqual([row.get("action") for row in self.history()].count("start"), 1)

    def test_the_phone_hears_when_the_guardian_is_back(self):
        """R2: the gate's settle() was not given the phone, so the all-clear never reached it."""
        self.run_folder(updated=ago(minutes=4), heartbeat=ago(seconds=20))
        self.state_dir.mkdir()
        last = self.state_dir / "last_check.json"
        last.write_text(json.dumps({"checked_at": ago(minutes=40)}), encoding="utf-8")
        self.assertTrue(self.gate()["guardian_silent"])
        last.write_text(json.dumps({"checked_at": ago(minutes=1)}), encoding="utf-8")
        self.assertFalse(self.gate(now_ms=NOW_MS + 60_000)["guardian_silent"])
        self.assertEqual([title for title, _ in self.phone], [guardian.SELF_TITLE, autostart.notifier.CLEARED_TITLE])
        self.assertEqual(len(self.sent), 1)

    def test_an_older_live_run_that_is_stalled_or_unprotected_is_not_started_twice(self):
        """R3: only ``alive`` counted for an older folder; a live Bot holding without a confirmed stop,
        or waiting for a bar, made the gate start a second one into the account lock."""
        for case in ("bars_stalled", "position_unprotected"):
            with self.subTest(case=case):
                self.setUp()
                if case == "bars_stalled":
                    self.run_folder(A, updated=ago(minutes=50), heartbeat=ago(seconds=20), created=ago(days=1))
                else:
                    older = self.run_folder(A, updated=ago(minutes=4), position="1", created=ago(days=1))
                    (older / "heartbeat.json").write_text(json.dumps({
                        "time": ago(seconds=20), "pid": 1, "position": "1", "protection": {
                            "ratio": "0.1", "confirmed": False, "price": None, "alert": None,
                            "unprotected_since": ago(minutes=20), "checked_at": ago(seconds=30)}}), encoding="utf-8")
                self.run_folder(B, status=False, created=ago(minutes=30))  # newest: a start that never got going
                result = self.gate()
                self.assertEqual((result["action"], result["reason"]), ("skip", "already_running"), result)
                self.assertEqual(self.launched, [])

    def test_the_gate_never_runs_the_real_task_for_other_folders(self):
        """R3: ``start`` defaulted to the real launcher, so a test that forgot it ran schtasks.exe."""
        self.lost()
        never = mock.Mock(side_effect=AssertionError("schtasks.exe must not run from a test"))
        with mock.patch.object(autostart.subprocess, "run", never):
            result = autostart.gate_once(root=self.runs, state_dir=self.state_dir, now_ms=NOW_MS,
                                         kill_path=self.kill, notify=lambda t, b: {"ok": True},
                                         external=lambda t, b: {"ok": True})
        never.assert_not_called()
        self.assertEqual((result["action"], result["reason"]), ("refuse", "launch_failed"))
        self.assertEqual(result["launch"]["detail"], "not_the_real_run_folders")

    def test_launch_reads_a_big5_answer_without_failing(self):
        """R1: schtasks answers in the console code page; in UTF-8 mode that raised in the reader."""
        calls = []

        def run(arguments, **options):
            calls.append(options)
            return autostart.subprocess.CompletedProcess(arguments, 0, stdout=None, stderr=None)

        with mock.patch.object(autostart.subprocess, "run", run):
            self.assertEqual(autostart.launch(), {"ok": True, "detail": "schtasks:0"})
        self.assertEqual(calls[0].get("errors"), "replace")


if __name__ == "__main__":
    unittest.main()
