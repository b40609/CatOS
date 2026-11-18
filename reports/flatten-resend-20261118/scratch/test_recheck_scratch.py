"""Narrow re-check of commit bdb645bc (D1-D3, O2, O5). FakeOkx only, isolated paths, temporary HOME:

    T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe -m unittest discover \
        -s reports/flatten-resend-20261118/scratch -p "test_recheck_*.py" -v
"""

import asyncio
import json
from pathlib import Path
import sqlite3
import sys
import time
import unittest
from decimal import Decimal as D
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(1, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from catos import kill_switch, okx_demo_exchange  # noqa: E402
from catos.okx_demo import TAG, Credentials, DemoClient  # noqa: E402
from catos.okx_demo_exchange import OkxDemoExchange  # noqa: E402
import test_demo_bot as T  # noqa: E402

BASE, Clock, FakeOkx = T.BASE, T.Clock, T.FakeOkx
INST = "BTC-USDT-SWAP"


def payload(cl, side="sell", sz="1", reduce=True):
    return {"instId": INST, "tdMode": "cross", "posSide": "net", "ordType": "market", "side": side,
            "sz": sz, "reduceOnly": reduce, "clOrdId": cl, "tag": TAG}


def adapter(fake, clock, flattening=True):
    client = DemoClient(Credentials("k", "s", "p"), fake, clock_ms=clock, sleep=lambda s: None, monotonic=lambda: 0.0)
    ex = OkxDemoExchange(client, "acct", INST)
    ex.flattening = flattening
    return ex


def okx_now(fake, clock):
    return clock.ms + fake.server_skew


class AdapterRecheck(unittest.TestCase):
    def lost(self, flattening=True):
        """OKX takes the reduce-only sell (position 1 -> 0), the answer is lost, queries keep saying
        "does not exist" (hide_orders)."""
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, position="1")
        ex = adapter(fake, clock, flattening)
        fake.lose_post_response = True
        fake.hide_orders = 1
        sent_okx = okx_now(fake, clock)
        with self.assertRaises(OSError):
            asyncio.run(ex.submit(payload("c1")))
        self.assertEqual(fake.position, D("0"))
        return fake, clock, ex, sent_okx

    def test_r1b_forward_step_after_send(self):
        fake, clock, ex, sent = self.lost()
        deadline = ex._deadlines["c1"]
        clock.ms += 21_000          # 1 s real + local clock stepped +20 s
        fake.server_skew -= 20_000  # OKX moved 1 s only
        r = asyncio.run(ex.query("c1"))
        print(f"\n[r1b] deadline-sent={deadline - sent} okx_now-deadline={okx_now(fake, clock) - deadline} status={r.status}")
        self.assertEqual((deadline - sent, r.status), (5_000, "NOT_FOUND"))

    def test_r1c_forward_step_before_send(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, position="1")
        ex = adapter(fake, clock)
        asyncio.run(ex._server_ms())
        clock.ms += 20_000
        fake.server_skew -= 20_000
        fake.drop_posts = 1
        sent = okx_now(fake, clock)
        with self.assertRaises(OSError):
            asyncio.run(ex.submit(payload("c2")))
        deadline = ex._deadlines["c2"]
        clock.ms += 15_001
        r_early = asyncio.run(ex.query("c2"))  # OKX now = sent + 15001 > deadline + 10000: provable
        print(f"\n[r1c] expTime-sent={deadline - sent} (want 5000); 15.001 s of OKX time later status={r_early.status}")
        self.assertEqual(deadline - sent, 5_000)
        self.assertEqual(r_early.status, "REJECTED")  # correct: OKX never got it (drop_posts)

    def test_r1a_listing_lag_assumption_remains(self):
        fake, clock, ex, sent = self.lost()
        deadline = ex._deadlines["c1"]
        clock.ms = sent + 15_000
        a = asyncio.run(ex.query("c1")).status
        clock.ms = sent + 15_001
        b = asyncio.run(ex.query("c1")).status
        print(f"\n[r1a] OKX took it, never listed: at deadline+10000 {a}, at deadline+10001 {b}")
        self.assertEqual((a, b), ("NOT_FOUND", "REJECTED"))  # documented assumption 2, unchanged

    def test_r1d_order_listed_between_first_query_and_proof(self):
        """Q1 says not found; the order shows up before the second look: never REJECTED."""
        fake, clock, ex, sent = self.lost()
        clock.ms = sent + 20_000
        real = fake.send

        def send(method, target, headers, body):
            if target.startswith("/api/v5/public/time"):
                fake.hide_orders = 0  # listed right after Q1
            return real(method, target, headers, body)
        fake.send = send
        r = asyncio.run(ex.query("c1"))
        r2 = asyncio.run(ex.query("c1"))
        print(f"\n[r1d] listed between Q1 and Q2: first report={r.status} next report={r2.status} filled={r2.cumulative}")
        self.assertEqual(r.status, "NOT_FOUND")  # the found order is not used in this round (see O-R2)
        self.assertEqual(r2.status, "FILLED")

    def test_r1e_time_read_fails_no_proof(self):
        fake, clock, ex, sent = self.lost()
        fake.time_failures = 10**9
        clock.ms = sent + 3_600_000
        r = asyncio.run(ex.query("c1"))
        print(f"\n[r1e] public/time failing, 1 h later: {r.status}")
        self.assertEqual(r.status, "NOT_FOUND")

    def test_r1f_restart_cannot_prove(self):
        fake, clock, ex, sent = self.lost()
        fresh = adapter(fake, clock)
        clock.ms = sent + 3_600_000
        r = asyncio.run(fresh.query("c1"))
        print(f"\n[r1f] new adapter (restart), 1 h later: {r.status}")
        self.assertEqual(r.status, "NOT_FOUND")

    def test_r3_deadline_only_for_flatten_reduce_only(self):
        rows = []
        for flattening, reduce, side, pos in ((False, True, "sell", "1"), (True, False, "buy", "0"),
                                              (False, False, "buy", "0"), (True, True, "sell", "1")):
            clock = Clock(BASE + 1_000)
            fake = FakeOkx(clock, start_index=3, position=pos)
            ex = adapter(fake, clock, flattening)
            fake.drop_posts = 1
            with self.assertRaises(OSError):
                asyncio.run(ex.submit(payload("o1", side=side, reduce=reduce)))
            clock.ms += 3_600_000
            rows.append((flattening, reduce, fake.exp_times[0] is not None, asyncio.run(ex.query("o1")).status))
        print(f"\n[r3] (flattening, reduceOnly, expTime sent, status 1 h later): {rows}")
        self.assertEqual([r[2:] for r in rows], [(False, "NOT_FOUND"), (False, "NOT_FOUND"), (False, "NOT_FOUND"),
                                                 (True, "REJECTED")])

    def test_r_o5_deadline_dropped_when_okx_answers(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, position="1")
        ex = adapter(fake, clock)
        report = asyncio.run(ex.submit(payload("ok1")))
        print(f"\n[o5] answered order: status={report.status} deadlines={ex._deadlines} expTime={fake.exp_times}")
        self.assertEqual((report.status, ex._deadlines), ("FILLED", {}))
        self.assertIsNotNone(fake.exp_times[0])


class BotRecheck(unittest.TestCase):
    setUp = T.DemoBotTests.setUp
    make_bot = T.DemoBotTests.make_bot
    run_bot = T.DemoBotTests.run_bot
    events = T.DemoBotTests.events
    kill_after = T.DemoBotTests.kill_after

    def ledger(self, run="run"):
        con = sqlite3.connect(self.root / run / "state.sqlite3")
        con.row_factory = sqlite3.Row
        try:
            orders = [dict(r) for r in con.execute(
                "SELECT cl_ord_id,quantity,filled,state,settled,exchange_id FROM execution_orders ORDER BY rowid")]
            owned = con.execute("SELECT position FROM ownership").fetchone()[0]
            res = con.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
        finally:
            con.close()
        return orders, owned, res

    def kill_with(self, fake, clock, arm):
        engaged = []

        def on_sleep(now):
            if fake.position == 1 and not engaged and now > fake.bar_time(4) + 10_000:
                arm()
                kill_switch.engage(reason="end", actor="cli")
                engaged.append(now)
        return self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))

    def test_d1_backward_step_kill_flatten(self):
        """Round-1 test_2e: reversal reduce-only at bar 5, then within 5 minutes the local clock steps
        back 10 s relative to OKX, then Kill."""
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        engaged = []

        def on_sleep(now):
            if fake.position == -1 and not engaged and now > fake.bar_time(6) + 10_000:
                fake.server_skew = 10_000
                kill_switch.engage(reason="end", actor="cli")
                engaged.append(now)
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        orders, owned, _ = self.ledger()
        print(f"\n[d1] stop={status['stop_reason'][:24]} okx_position={fake.position} states={[o['state'] for o in orders]} "
              f"expTime per order={[e is not None for e in fake.exp_times]}")
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual(fake.position, 0)

    def test_r2a_resend_timing_in_okx_time(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        posts = []
        real = fake.send

        def send(method, target, headers, body):
            if method == "POST" and target == "/api/v5/trade/order":
                posts.append((okx_now(fake, clock), headers.get("expTime"), json.loads(body)["clOrdId"]))
            return real(method, target, headers, body)
        fake.send = send

        def arm():
            fake.drop_posts = 1
            fake.server_skew = -40_000  # and the local clock is 40 s ahead of OKX all along
        status = self.kill_with(fake, clock, arm)
        orders, owned, res = self.ledger()
        lost, resent = posts[1], posts[2]
        print(f"\n[r2a] stop={status['stop_reason'][:24]} owned={owned} reservations={res} "
              f"states={[(o['state'], o['settled'], o['filled']) for o in orders]}")
        print(f"      lost: OKX t={lost[0]} expTime={lost[1]} (+{int(lost[1]) - lost[0]}); resend at expTime+{resent[0] - int(lost[1])} ms")
        self.assertEqual(int(lost[1]) - lost[0], 5_000)
        self.assertGreater(resent[0], int(lost[1]) + okx_demo_exchange.PROOF_MARGIN_MS)
        self.assertEqual((owned, res, fake.position), ("0", 0, 0))

    def test_r2b_listing_lag_misjudged_in_flatten(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)

        def arm():
            fake.lose_post_response = True
            fake.hide_orders = 1
        status = self.kill_with(fake, clock, arm)
        orders, owned, _ = self.ledger()
        print(f"\n[r2b] stop={status['stop_reason']} posts={len(fake.posts)} states={[o['state'] for o in orders]}")
        self.assertTrue(status["stop_reason"].startswith("flatten_failed:position_mismatch:okx=0:ledger=1"))
        self.assertEqual(len(fake.posts), 2)

    def test_r2c_reversal_close_lost_then_restart_books_it(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        armed = []

        def on_sleep(now):
            if fake.position == 1 and not armed and now > fake.bar_time(4) + 10_000:
                fake.lose_post_response = True
                fake.hide_orders = 1
                armed.append(now)
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        print(f"\n[r2c] first stop={status['stop_reason'][:40]} expTimes={fake.exp_times}")
        fake.hide_orders = 0
        status2 = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 6), run="run2"))
        orders, owned, _ = self.ledger()
        legs = [f["leg"] for f in json.loads((self.root / "run" / "fills.json").read_text(encoding="utf-8"))]
        print(f"      restart stop={status2['stop_reason'][:24]} run2_created={(self.root / 'run2').exists()} "
              f"owned={owned} legs={legs}")
        self.assertTrue(status["stop_reason"].startswith("order_not_settled:UNKNOWN"))
        self.assertFalse((self.root / "run2").exists())
        self.assertIn("接續時補查", legs)

    def test_r2d_slow_time_read_o1_unchanged(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        slow = []
        real = fake.send

        def send(method, target, headers, body):
            if target.startswith("/api/v5/public/time") and slow and slow[0]:
                slow[0] = False
                time.sleep(5.5)
            return real(method, target, headers, body)
        fake.send = send
        status = self.kill_with(fake, clock, lambda: slow.append(True))
        print(f"\n[r2d] stop={status['stop_reason'][:50]} posts={len(fake.posts)} okx_position={fake.position}")
        self.assertTrue(status["stop_reason"].startswith("flatten_failed:order_not_settled:UNKNOWN"))
        self.assertEqual(len(fake.posts), 1)


class MutationRecheck(unittest.TestCase):
    """Would FlattenResendTests notice a broken proof now?"""

    def run_resend(self):
        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(T.FlattenResendTests).run(result)
        failed = sorted(t.id().rsplit(".", 1)[1] for t, _ in result.failures + result.errors)
        return result.testsRun, failed

    def check(self, label, *patches):
        for p in patches:
            p.start()
        try:
            ran, failed = self.run_resend()
        finally:
            for p in patches:
                p.stop()
        print(f"[mut] {label}: ran={ran} failed={len(failed)} {failed}")
        return failed

    def test_mutations(self):
        print()
        results = {}
        results["m1"] = self.check("PROOF_MARGIN_MS=-1e12 (no waiting)",
                                   mock.patch.object(okx_demo_exchange, "PROOF_MARGIN_MS", -10**12))

        async def any_deadline(self, cl):
            return cl in self._deadlines
        results["m2"] = self.check("_never_taken = any deadline",
                                   mock.patch.object(OkxDemoExchange, "_never_taken", any_deadline))

        async def local_clock(self, cl):
            d = self._deadlines.get(cl)
            return d is not None and self._client._clock_ms() > d + okx_demo_exchange.PROOF_MARGIN_MS
        results["m3"] = self.check("proof by local clock (round-1 D2)",
                                   mock.patch.object(OkxDemoExchange, "_never_taken", local_clock))

        async def no_second_look(self, cl):
            d = self._deadlines.get(cl)
            if d is None:
                return False
            server = await self._server_ms()
            return server is not None and server > d + okx_demo_exchange.PROOF_MARGIN_MS
        results["m4"] = self.check("no second query after the time read",
                                   mock.patch.object(OkxDemoExchange, "_never_taken", no_second_look))

        orig_submit = OkxDemoExchange.submit

        async def always_flattening(self, p):
            self.flattening = True
            return await orig_submit(self, p)
        results["m5"] = self.check("every reduce-only gets a deadline (round-1 D3)",
                                   mock.patch.object(OkxDemoExchange, "submit", always_flattening))

        class NoPop(dict):
            def pop(self, *a):
                return None

        async def keep_deadline(self, p):
            if type(self._deadlines) is not NoPop:
                self._deadlines = NoPop(self._deadlines)
            return await orig_submit(self, p)
        results["m6"] = self.check("deadline kept after an ordId (O5 reverted)",
                                   mock.patch.object(OkxDemoExchange, "submit", keep_deadline))
        self.results = results
        self.assertTrue(results["m1"] and results["m2"] and results["m3"] and results["m5"])


if __name__ == "__main__":
    unittest.main()
