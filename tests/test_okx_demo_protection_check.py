"""`demo protection-check` against the stateful fake OKX (no network)."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from catos.okx_demo import Credentials, DemoClient
from catos.okx_demo_protection_check import CheckStopped, bot_running, render, run_check
from tests.test_demo_bot import BASE, TF, Clock, FakeOkx

D = Decimal


async def _no_sleep(_):
    return None


class ProtectionCheckTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock(BASE + 1_000 + 4 * TF)
        self.fake = FakeOkx(self.clock, start_index=3)
        self.client = DemoClient(Credentials("k", "s", "p"), self.fake, clock_ms=self.clock, sleep=lambda s: None,
                                 monotonic=lambda: 0.0)

    def run_check(self):
        return asyncio.run(run_check(self.client, "BTC-USDT-SWAP", sleep=_no_sleep, stamp="1"))

    def algo_paths(self):
        return [path.rsplit("/", 1)[1] for path, _ in self.fake.algo_posts]

    def test_stop_stays_after_close_then_is_canceled(self):
        report = self.run_check()
        self.assertEqual(report["create"]["adapter"]["status"], "LIVE")
        self.assertEqual(report["create"]["adapter"]["price"], D(report["create"]["expected"]))
        self.assertEqual(report["amend"]["adapter"]["price"], D(report["amend"]["expected"]))
        self.assertLess(D(report["amend"]["expected"]), D(report["create"]["expected"]))  # 12% is further away
        self.assertEqual(report["create"]["adapter"]["side"], "sell")
        self.assertFalse(report["findings"]["auto_cancel_on_flat"])
        self.assertEqual(report["cancel_adapter"]["status"], "CANCELED")
        self.assertEqual(report["findings"]["history_has_it"], ["canceled"])
        self.assertEqual(report["findings"]["adapter_final_status"], "CANCELED")
        self.assertEqual(self.algo_paths(), ["order-algo", "amend-algos", "cancel-algos"])
        self.assertEqual(self.fake.position, 0)
        self.assertEqual([p["reduceOnly"] for p in self.fake.posts], [False, True])
        self.assertIn("平倉後自動結束條件單：否", render(report))

    def test_okx_cancels_on_flat_and_hides_finished_stop(self):
        self.fake.auto_cancel_on_flat = self.fake.finished_algos_vanish = True
        report = self.run_check()
        self.assertTrue(report["findings"]["auto_cancel_on_flat"])
        self.assertEqual(report["findings"]["finished_order_algo_code"], "51603")
        self.assertEqual(report["findings"]["history_has_it"], ["canceled"])
        self.assertEqual(report["findings"]["adapter_final_status"], "CANCELED")  # settled through the history
        self.assertNotIn("cancel-algos", self.algo_paths())
        self.assertEqual(report["after_close_order_algo"][0]["code"], "51603")

    def test_refuses_with_a_position_and_sends_nothing(self):
        self.fake.position = D("1")
        with self.assertRaises(CheckStopped):
            self.run_check()
        self.assertEqual(self.fake.posts, [])
        self.assertEqual(self.fake.algo_posts, [])

    def test_refuses_with_a_foreign_conditional_order(self):
        self.fake.foreign_algos.append({"instId": "BTC-USDT-SWAP", "algoId": "1", "algoClOrdId": "x",
                                        "ordType": "conditional", "state": "live", "side": "buy"})
        with self.assertRaises(CheckStopped):
            self.run_check()
        self.assertEqual(self.fake.posts, [])

    def test_failed_stop_closes_the_position(self):
        self.fake.reject_algo = "51000"
        with self.assertRaises(CheckStopped) as caught:
            self.run_check()
        self.assertEqual(self.fake.position, 0)
        self.assertTrue(self.fake.posts[-1]["reduceOnly"])
        self.assertTrue(any("平倉單" in step for step in caught.exception.report["steps"]))


class TriggerModeTests(ProtectionCheckTests.__base__):
    setUp = ProtectionCheckTests.setUp

    def run_trigger(self, fire_after):
        looks = []

        async def sleep(seconds):
            looks.append(seconds)
            if len(looks) == fire_after:
                self.fake.trigger_stop()

        return asyncio.run(run_check(self.client, "BTC-USDT-SWAP", sleep=sleep, stamp="1", ratio=D("0.01"),  # fake price ~100, tick 0.1
                                     trigger_wait_seconds=60))

    def test_fired_stop_is_reported_as_triggered(self):
        self.fake.finished_algos_vanish = True
        report = self.run_trigger(fire_after=2)
        self.assertTrue(report["trigger_wait"]["fired"])
        self.assertEqual(report["findings"]["adapter_after_trigger"], "TRIGGERED")
        self.assertEqual(report["findings"]["triggered_history_has_it"], ["effective"])
        self.assertEqual(report["findings"]["position_after_trigger"], "0")
        self.assertEqual(self.fake.position, 0)
        self.assertEqual([p["reduceOnly"] for p in self.fake.posts], [False])  # OKX closed it, not us
        self.assertIn("Bot 的轉接層判定：TRIGGERED", render(report))

    def test_not_fired_in_time_cancels_and_closes(self):
        report = self.run_trigger(fire_after=10_000)
        self.assertFalse(report["trigger_wait"]["fired"])
        self.assertEqual(report["findings"]["adapter_final_status"], "CANCELED")
        self.assertEqual(self.fake.position, 0)
        self.assertEqual([p["reduceOnly"] for p in self.fake.posts], [False, True])


class BotRunningTests(unittest.TestCase):
    def test_recent_running_status_blocks(self):
        root = Path(tempfile.mkdtemp())
        now = datetime(2026, 11, 18, 6, tzinfo=timezone.utc)
        for name, state, minutes in (("old", "running", 60), ("done", "stopped", 1), ("live", "running", 2)):
            (root / name).mkdir()
            updated = now.timestamp() - minutes * 60
            (root / name / "status.json").write_text(json.dumps(dict(
                state=state, updated_at=datetime.fromtimestamp(updated, timezone.utc).isoformat())), encoding="utf-8")
        self.assertEqual(bot_running(root, now.timestamp()), "live")
        (root / "live" / "status.json").unlink()
        self.assertIsNone(bot_running(root, now.timestamp()))
        self.assertIsNone(bot_running(root / "missing", now.timestamp()))


if __name__ == "__main__":
    unittest.main()
