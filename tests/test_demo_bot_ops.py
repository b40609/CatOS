"""Keeping the OKX Demo Bot running unattended (2026-11-27): heartbeat, the disaster-stop
ratio across a resume, long read backoff, and a status file that cannot stop the loop.

Same stateful fake OKX and isolation as tests/test_demo_bot.py (no network).
"""

import contextlib
import io
import json
import os
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

from catos import demo_bot, local_sim_r4
from catos.demo_bot import BotStopped
from catos.demo_bot_liveness import iso_ms

try:  # "discover -s tests" imports test modules top-level; "-m unittest tests.x" as a package
    import test_demo_bot as base
except ImportError:
    from tests import test_demo_bot as base

BASE, Clock, FakeOkx = base.BASE, base.Clock, base.FakeOkx

D = Decimal


class _Base(unittest.TestCase):
    setUp = base.DemoBotTests.setUp
    make_bot = base.DemoBotTests.make_bot
    run_bot = base.DemoBotTests.run_bot
    events = base.DemoBotTests.events
    kill_after = base.DemoBotTests.kill_after
    algo_writes = base.DisasterStopTests.algo_writes
    TEN = D("0.10")

    @staticmethod
    def both(first, second):
        def on_sleep(now):
            first(now)
            second(now)
        return on_sleep

    def stop_with_a_long_position(self, fake, clock, ratio):
        """Long 1 from bar 3 with the disaster stop on OKX, then stopped by stop.request."""
        def stop_later(now):
            if fake.position == 1 and now > fake.bar_time(4) + 5_000:
                (self.root / "run" / "stop.request").write_text("", encoding="utf-8")

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=stop_later, disaster_stop=ratio))
        self.assertEqual((status["stop_reason"], status["position"]), ("operator_stop_file", "1"), status)

    def config_events(self, run="run"):
        return [e for e in self.events(run) if e["kind"] in ("protection_config", "protection_config_changed")]


class DisasterStopInheritanceTests(_Base):
    """CAT-A-03 + CAT-AX-07: a restart command without --disaster-stop must not remove the stop."""

    def test_resume_without_the_option_keeps_the_stopped_runs_ratio(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.stop_with_a_long_position(fake, clock, self.TEN)
        self.assertEqual(self.algo_writes(fake), [("order-algo", {"side": "sell", "slTriggerPx": "94.5"})])
        lines = []
        status = self.run_bot(self.make_bot(fake, clock, events=lines, on_sleep=self.kill_after(fake, 4), run="run2",
                                            disaster_stop=None))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        # The stop on OKX was neither canceled nor moved by the resume; only the Kill flatten ends it.
        self.assertEqual([w[0] for w in self.algo_writes(fake)], ["order-algo", "cancel-algos"])
        manifest = json.loads((self.root / "run" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["resumes"][-1]["disaster_stop"], "0.10")
        self.assertEqual(manifest["resumes"][-1]["disaster_stop_source"], "inherited")
        inherited = [e for e in self.config_events() if e.get("source") == "inherited"]
        self.assertEqual([e["ratio"] for e in inherited], ["0.10"])
        self.assertTrue(any("沿用" in line for line in lines), lines)

    def test_resume_with_an_explicit_zero_removes_the_stop_and_says_so(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.stop_with_a_long_position(fake, clock, self.TEN)
        lines = []
        self.run_bot(self.make_bot(fake, clock, events=lines, on_sleep=self.kill_after(fake, 4), run="run2",
                                   disaster_stop=D("0")))
        self.assertEqual([w[0] for w in self.algo_writes(fake)], ["order-algo", "cancel-algos"])
        self.assertEqual([a["state"] for a in fake.algos.values()], ["canceled"])
        changed = [e for e in self.config_events() if e["kind"] == "protection_config_changed"]
        self.assertEqual([(e["previous"], e["ratio"]) for e in changed], [("0.10", "0")])
        self.assertTrue(any("未啟用保底停損" in line for line in lines), lines)
        # canceled by the resume itself, before the Kill: a "已撤銷" protection event precedes the flatten
        kinds = [e["kind"] for e in self.events()]
        self.assertLess(kinds.index("protection_config_changed"), kinds.index("flatten"))

    def test_resume_inherits_the_newest_resume_not_the_first_start(self):
        manifest = {"disaster_stop": "0.1", "resumes": [{"disaster_stop": "0.05"}]}
        self.assertEqual(demo_bot.last_disaster_stop(manifest), D("0.05"))
        self.assertEqual(demo_bot.last_disaster_stop({"disaster_stop": "0.1"}), D("0.1"))
        self.assertEqual(demo_bot.last_disaster_stop({"disaster_stop": "0"}), D("0"))

    def test_an_unreadable_recorded_ratio_refuses_the_resume_instead_of_guessing(self):
        for bad in ({}, {"disaster_stop": "ten"}, {"disaster_stop": "0.9"}, {"disaster_stop": "0.1", "resumes": [{}]}):
            self.assertIsNone(demo_bot.last_disaster_stop(bad), bad)
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.stop_with_a_long_position(fake, clock, self.TEN)
        path = self.root / "run" / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["disaster_stop"] = "ten"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(BotStopped) as caught:
            self.run_bot(self.make_bot(fake, clock, run="run2", disaster_stop=None))
        self.assertEqual(caught.exception.reason, "resume_disaster_stop_unreadable")
        self.assertEqual([a["state"] for a in fake.algos.values()], ["live"])  # nothing on OKX was touched
        self.assertIsNotNone(demo_bot._hint("resume_disaster_stop_unreadable"))

    def test_new_run_without_the_option_refuses_to_start(self):
        """Review F4 (2026-11-27): a new run never gets 0% silently; started in the background nobody sees a warning."""
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        with self.assertRaises(BotStopped) as caught:
            self.run_bot(self.make_bot(fake, clock, disaster_stop=None))
        self.assertEqual(caught.exception.reason, "disaster_stop_required")
        self.assertFalse((self.root / "run").exists())  # no run folder, nothing for a reader to mistake for a run
        self.assertEqual((fake.posts, fake.algo_posts), ([], []))
        self.assertIn("0%", demo_bot._hint("disaster_stop_required"))
        # The account was released: the same account starts once the ratio is written.
        self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 4), disaster_stop=self.TEN))

    def test_new_run_with_an_explicit_zero_starts_and_says_there_is_no_disaster_stop(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        lines = []
        self.run_bot(self.make_bot(fake, clock, events=lines, on_sleep=self.kill_after(fake, 4), disaster_stop=D("0")))
        self.assertEqual([(e["ratio"], e["source"]) for e in self.config_events()], [("0", "explicit")])
        self.assertTrue(any("未啟用保底停損" in line for line in lines), lines)
        manifest = json.loads((self.root / "run" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["disaster_stop"], "0")  # 0 still means off (P6); it only has to be written
        self.assertEqual(fake.algo_posts, [])

    def test_new_run_with_a_ratio_records_it_as_explicit(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 4), disaster_stop=self.TEN))
        self.assertEqual([(e["ratio"], e["source"]) for e in self.config_events()], [("0.10", "explicit")])

    def test_command_line_tells_not_given_from_zero(self):
        parser = demo_bot._parser()
        self.assertIsNone(parser.parse_args(["--profile", "p.json"]).disaster_stop)
        self.assertEqual(parser.parse_args(["--profile", "p.json", "--disaster-stop", "0%"]).disaster_stop, D("0"))
        self.assertEqual(parser.parse_args(["--profile", "p.json", "--disaster-stop", "10%"]).disaster_stop, D("0.1"))

    def test_a_fraction_without_the_percent_sign_is_refused(self):
        """Review F11: "0.1" meant 10% to the writer and 0.1% to the parser."""
        parser = demo_bot._parser()
        for text in ("0.1", "0.05", ".5"):
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                parser.parse_args(["--profile", "p.json", "--disaster-stop", text])
        ok = {"0.5%": D("0.005"), "10": D("0.1"), "0": D("0"), "1": D("0.01"), "2.5": D("0.025")}
        for text, value in ok.items():
            self.assertEqual(parser.parse_args(["--profile", "p.json", "--disaster-stop", text]).disaster_stop, value)


class ReadBackoffTests(_Base):
    """CAT-A-04: a read outage of a few minutes must not end the run."""

    def fail_reads_once_long(self, fake, count):
        armed = []

        def on_sleep(now):
            if not armed and fake.position == 1 and now > fake.bar_time(4) + 5_000:
                fake.balance_failures = count
                armed.append(now)
        return on_sleep, armed

    def test_eight_failed_reads_in_a_row_are_survived(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        outage, armed = self.fail_reads_once_long(fake, 8)  # the old limit was 4 tries, about 14 s
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.both(outage, self.kill_after(fake, 7))))
        self.assertTrue(armed)
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        retries = [e for e in self.events() if e["kind"] == "read_retry"]
        self.assertGreaterEqual(len(retries), 8)
        self.assertEqual({e["code"] for e in retries}, {"50001"})

    def test_an_outage_longer_than_the_budget_stops_with_the_reason(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        outage, armed = self.fail_reads_once_long(fake, 10**9)
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=outage))
        self.assertEqual((status["state"], status["stop_reason"]), ("stopped", "okx_read_failed:50001"), status)
        self.assertGreaterEqual(clock.ms - armed[0], demo_bot.READ_RETRY_MS - 60_000)
        self.assertLessEqual(clock.ms - armed[0], demo_bot.READ_RETRY_MS + 120_000)

    def test_a_stop_request_ends_the_wait_during_an_outage(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        outage, armed = self.fail_reads_once_long(fake, 10**9)

        def on_sleep(now):
            outage(now)
            if armed and now > armed[0] + 120_000:
                (self.root / "run" / "stop.request").write_text("", encoding="utf-8")

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        self.assertEqual(status["stop_reason"], "operator_stop_file", status)
        self.assertLess(clock.ms - armed[0], 300_000)


class StatusFileTests(_Base):
    """CAT-A-05: status.json is for readers; failing to write it must not stop trading."""

    def test_replace_is_retried_while_a_reader_holds_the_file(self):
        target = self.root / "value.json"
        real_replace, calls = Path.replace, []

        def flaky(path, destination):
            calls.append(path.name)
            if len(calls) <= 3:
                raise PermissionError(5, "Access is denied")
            return real_replace(path, destination)

        with mock.patch.object(Path, "replace", flaky), mock.patch.object(local_sim_r4.time, "sleep", lambda s: None):
            local_sim_r4.atomic_json(target, {"a": 1})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"a": 1})
        self.assertEqual(len(calls), 4)

    def test_replace_that_never_succeeds_still_raises(self):
        def denied(path, destination):
            raise PermissionError(5, "Access is denied")

        with mock.patch.object(Path, "replace", denied), mock.patch.object(local_sim_r4.time, "sleep", lambda s: None), \
                self.assertRaises(PermissionError):
            local_sim_r4.atomic_json(self.root / "value.json", {"a": 1})

    def test_status_write_failures_do_not_stop_the_run(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        real, failed = demo_bot.atomic_json, []

        def flaky(path, value):
            if path.name == "status.json" and value.get("state") == "running" and len(failed) < 3:
                failed.append(value.get("bars"))
                raise PermissionError(5, "Access is denied")
            return real(path, value)

        with mock.patch.object(demo_bot, "atomic_json", flaky):
            status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 7)))
        self.assertEqual(len(failed), 3)
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)  # ran on and traded
        self.assertEqual(len(fake.posts), 4)
        kinds = [e["kind"] for e in self.events()]
        self.assertEqual(kinds.count("status_write_failed"), 3)
        written = json.loads((self.root / "run" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(written["state"], "stopped")


class HeartbeatTests(_Base):
    def test_run_leaves_a_heartbeat_with_time_and_pid(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 4)))
        beat = json.loads((self.root / "run" / "heartbeat.json").read_text(encoding="utf-8"))
        self.assertEqual(beat["pid"], os.getpid())
        self.assertIsNotNone(iso_ms(beat["time"]))

    def test_heartbeat_is_rewritten_while_the_run_lives(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        bot = self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 4))
        bot.heartbeat_s = 0  # every pass of the event loop instead of every minute
        beats, real = [], demo_bot.atomic_json

        def counting(path, value):
            if path.name == "heartbeat.json":
                beats.append(value["time"])
            return real(path, value)

        with mock.patch.object(demo_bot, "atomic_json", counting):
            self.run_bot(bot)
        self.assertGreater(len(beats), 3)

    def test_a_heartbeat_that_cannot_be_written_never_stops_the_run(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        real = demo_bot.atomic_json

        def denied(path, value):
            if path.name == "heartbeat.json":
                raise PermissionError(5, "Access is denied")
            return real(path, value)

        with mock.patch.object(demo_bot, "atomic_json", denied):
            status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 7)))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual(len(fake.posts), 4)

    def test_heartbeat_says_whether_the_position_has_a_confirmed_stop(self):
        """Review F2: the Guardian reads this to tell "holding with no stop on OKX" from outside."""
        for ratio, expected in ((self.TEN, (True, "94.5")), (D("0"), (False, None))):
            with self.subTest(ratio=ratio):
                self.setUp()
                clock = Clock(BASE + 1_000)
                fake = FakeOkx(clock, start_index=3)
                bot = self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 6), disaster_stop=ratio)
                bot.heartbeat_s = 0
                beats, real = [], demo_bot.atomic_json

                def keeping(path, value, beats=beats, real=real):
                    if path.name == "heartbeat.json":
                        beats.append(value)
                    return real(path, value)

                with mock.patch.object(demo_bot, "atomic_json", keeping):
                    self.run_bot(bot)
                flat = [b for b in beats if b.get("position") == "0" and b.get("protection")]
                held = [b for b in beats if b.get("position") == "1"]
                self.assertTrue(flat and held, sorted({str(b.get("position")) for b in beats}))
                self.assertTrue(all(b["protection"]["unprotected_since"] is None for b in flat), flat[:2])
                self.assertEqual(held[-1]["protection"]["ratio"], str(ratio))
                self.assertEqual((held[-1]["protection"]["confirmed"], held[-1]["protection"]["price"]), expected)
                unprotected = held[-1]["protection"]["unprotected_since"]
                if expected[0]:
                    self.assertIsNone(unprotected)
                else:  # holding without a stop: since when, and it does not move while that lasts
                    self.assertIsNotNone(iso_ms(unprotected))
                    self.assertEqual({b["protection"]["unprotected_since"] for b in held}, {unprotected})


class KillReentryTests(_Base):
    def test_a_failed_read_while_flattening_does_not_start_the_kill_again(self):
        """Review F5: the backoff inside a Kill flatten checked the Kill-Switch again and re-entered the flatten."""
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        bot = self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 4), disaster_stop=self.TEN)
        original, hit = bot._reconcile_if_marked, []

        async def failing_once(facts, flattening):
            if flattening and not hit:
                hit.append(clock.ms)
                fake.balance_failures = 1  # the read right after the stop was canceled fails once
            return await original(facts, flattening)

        bot._reconcile_if_marked = failing_once
        status = self.run_bot(bot)
        self.assertTrue(hit)
        kinds = [e["kind"] for e in self.events()]
        self.assertIn("read_retry", kinds)
        self.assertEqual((kinds.count("kill_switch"), kinds.count("flatten")), (1, 1), kinds)
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual((status["position"], fake.position), ("0", 0))


if __name__ == "__main__":
    unittest.main()
