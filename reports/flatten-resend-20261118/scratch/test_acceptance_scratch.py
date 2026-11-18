"""Independent acceptance scratch tests for commit 6d600094 (flatten resend with OKX expTime).

FakeOkx only (no network, no key files). Isolated approval / Kill-Switch / lock / account paths via
DemoBotTests.setUp. Run from the repo root with a temporary HOME:

    T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe -m unittest discover \
        -s reports/flatten-resend-20261118/scratch -p "test_*.py" -v
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

from catos import ipc, kill_switch, okx_demo_exchange  # noqa: E402
from catos.okx_demo import TAG, Credentials, DemoClient  # noqa: E402
from catos.okx_demo_exchange import OkxDemoExchange  # noqa: E402
import test_demo_bot as T  # noqa: E402
BASE, Clock, FakeOkx = T.BASE, T.Clock, T.FakeOkx  # DemoBotTests not imported by name: discover would re-run it

INST = "BTC-USDT-SWAP"


def payload(cl, side="sell", sz="1", reduce=True):
    return {"instId": INST, "tdMode": "cross", "posSide": "net", "ordType": "market", "side": side,
            "sz": sz, "reduceOnly": reduce, "clOrdId": cl, "tag": TAG}


def adapter(fake, clock):
    client = DemoClient(Credentials("k", "s", "p"), fake, clock_ms=clock, sleep=lambda s: None, monotonic=lambda: 0.0)
    return OkxDemoExchange(client, "acct", INST)


def time_reads(fake):
    """Count public/time reads by wrapping send."""
    count = [0]
    real = fake.send

    def send(method, target, headers, body):
        if target.startswith("/api/v5/public/time"):
            count[0] += 1
        return real(method, target, headers, body)
    fake.send = send
    return count


class ProofUnitTests(unittest.TestCase):
    """Point 1: when does "not found" become REJECTED (adapter level)."""

    def lost_reduce_only(self):
        """OKX takes a reduce-only sell (position 1 -> 0) but the answer is lost; queries keep
        answering "does not exist" (hide_orders). Returns (fake, clock, exchange, deadline, t_send)."""
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, position="1")
        ex = adapter(fake, clock)
        fake.lose_post_response = True
        fake.hide_orders = 1
        t_send = clock.ms
        with self.assertRaises(OSError):
            asyncio.run(ex.submit(payload("c1")))
        self.assertEqual(fake.position, D("0"))  # OKX DID take it
        return fake, clock, ex, ex._deadlines["c1"], t_send

    def test_1a_without_clock_jump_not_found_stays_not_found_for_15s(self):
        fake, clock, ex, deadline, t0 = self.lost_reduce_only()
        clock.ms = t0 + 15_000  # exactly deadline + margin: not yet proof (strict >)
        self.assertEqual(asyncio.run(ex.query("c1")).status, "NOT_FOUND")
        clock.ms = t0 + 15_001
        r = asyncio.run(ex.query("c1"))
        # Listing lag > 15 s: OKX took and filled the order, the adapter now calls it never taken.
        print(f"\n[1a] listing lag 15 s: status={r.status} complete={r.complete} okx_position={fake.position}")
        self.assertEqual(r.status, "REJECTED")

    def test_1b_forward_clock_step_after_send_proves_before_the_deadline(self):
        fake, clock, ex, deadline, t0 = self.lost_reduce_only()
        # 1 s of real time passes; the local wall clock is stepped +20 s (e.g. Windows time sync).
        # OKX server time only moved 1 s, so it is still BEFORE the expTime we sent.
        clock.ms = t0 + 1_000 + 20_000
        fake.server_skew -= 20_000
        okx_now = clock.ms + fake.server_skew
        r = asyncio.run(ex.query("c1"))
        print(f"\n[1b] okx_server_now - deadline = {okx_now - deadline} ms, status={r.status}, okx_position={fake.position}")
        self.assertLess(okx_now, deadline)
        self.assertEqual(r.status, "REJECTED")  # "proven never taken" while OKX could still take it

    def test_1c_forward_clock_step_inside_offset_cache_before_send(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, position="1")
        ex = adapter(fake, clock)
        asyncio.run(ex._server_offset())  # offset cached (e.g. by an earlier reduce-only order)
        clock.ms += 20_000                # local wall clock stepped +20 s, OKX time unchanged
        fake.server_skew -= 20_000
        fake.drop_posts = 1
        t_send_okx = clock.ms + fake.server_skew
        with self.assertRaises(OSError):
            asyncio.run(ex.submit(payload("c2")))
        deadline = ex._deadlines["c2"]
        print(f"\n[1c] expTime sent = OKX now + {deadline - t_send_okx} ms (intended 5000)")
        clock.ms += 15_001                # 15 s of real time
        okx_now = clock.ms + fake.server_skew
        r = asyncio.run(ex.query("c2"))
        print(f"[1c] at query: okx_now - deadline = {okx_now - deadline} ms, status={r.status}")
        self.assertEqual(deadline - t_send_okx, 25_000)
        self.assertLess(okx_now, deadline)  # OKX would still process the request until its deadline
        self.assertEqual(r.status, "REJECTED")

    def test_1d_slow_time_read_means_no_deadline(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, position="1")
        real = fake.send

        def send(method, target, headers, body):
            if target.startswith("/api/v5/public/time"):
                clock.ms += 2_500  # round trip 2.5 s > CLOCK_MAX_RTT_MS
            return real(method, target, headers, body)
        fake.send = send
        ex = adapter(fake, clock)
        fake.drop_posts = 1
        with self.assertRaises(OSError):
            asyncio.run(ex.submit(payload("c3")))
        clock.ms += 600_000
        r = asyncio.run(ex.query("c3"))
        print(f"\n[1d] RTT 2.5 s: expTime header={fake.exp_times}, deadlines={ex._deadlines}, status={r.status}")
        self.assertEqual(fake.exp_times, [None])
        self.assertEqual(r.status, "NOT_FOUND")

    def test_1e_offset_cache_five_minutes(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, position="3")
        reads = time_reads(fake)
        ex = adapter(fake, clock)
        asyncio.run(ex.submit(payload("d1")))
        clock.ms += 299_999
        asyncio.run(ex.submit(payload("d2")))
        clock.ms += 2
        asyncio.run(ex.submit(payload("d3")))
        print(f"\n[1e] public/time reads for 3 reduce-only orders over 300 001 ms: {reads[0]}")
        self.assertEqual(reads[0], 2)

    def test_1f_backward_clock_step_keeps_a_stale_offset(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, position="3")
        reads = time_reads(fake)
        ex = adapter(fake, clock)
        asyncio.run(ex.submit(payload("e1")))
        clock.ms -= 3_600_000             # local clock stepped back one hour
        fake.server_skew += 3_600_000     # OKX time unchanged
        clock.ms += 600_000               # ten real minutes later
        asyncio.run(ex.submit(payload("e2")))
        okx_at_send = clock.ms + fake.server_skew
        print(f"\n[1f] after a -1 h step: time reads={reads[0]}, second order result posts={len(fake.posts)}")
        # The cached offset is "younger than 5 min" by the stepped clock, so it is reused: the
        # deadline is one hour in the past at OKX and the order comes back 50036 (REJECTED).
        self.assertEqual(reads[0], 1)
        self.assertLess(int(fake.exp_times[-1]), okx_at_send)
        self.assertEqual(len(fake.posts), 1)

    def test_1g_restart_cannot_prove(self):
        fake, clock, ex, deadline, t0 = self.lost_reduce_only()
        fresh = adapter(fake, clock)      # a restarted process: new adapter, deadlines lost
        clock.ms = t0 + 3_600_000
        r = asyncio.run(fresh.query("c1"))
        print(f"\n[1g] restarted adapter, 1 h later: status={r.status}")
        self.assertEqual(r.status, "NOT_FOUND")

    def test_1h_query_time_is_taken_before_the_request(self):
        """asked = local time before the query is sent; a slow query does not help the proof."""
        fake, clock, ex, deadline, t0 = self.lost_reduce_only()
        clock.ms = t0 + 14_000
        real = fake.send

        def send(method, target, headers, body):
            if target.startswith("/api/v5/trade/order?"):
                clock.ms += 5_000  # query takes 5 s; OKX answers "not found" at t0+19 s
            return real(method, target, headers, body)
        fake.send = send
        r = asyncio.run(ex.query("c1"))
        print(f"\n[1h] query sent at t0+14 s, answered at t0+19 s: status={r.status}")
        self.assertEqual(r.status, "NOT_FOUND")


class OpeningOrderTests(unittest.TestCase):
    """Point 3: opening / adding orders keep the old behavior."""

    def test_3a_opening_order_has_no_deadline_and_never_becomes_rejected(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, position="0")
        reads = time_reads(fake)
        ex = adapter(fake, clock)
        asyncio.run(ex._server_offset())  # even with a cached offset
        before = reads[0]
        fake.drop_posts = 1
        with self.assertRaises(OSError):
            asyncio.run(ex.submit(payload("o1", side="buy", reduce=False)))
        clock.ms += 3_600_000
        r = asyncio.run(ex.query("o1"))
        print(f"\n[3a] opening order: expTime={fake.exp_times}, extra time reads={reads[0] - before}, "
              f"deadlines={ex._deadlines}, status 1 h later={r.status}")
        self.assertEqual((fake.exp_times, reads[0] - before, ex._deadlines, r.status), ([None], 0, {}, "NOT_FOUND"))

    def test_3b_reduce_only_must_be_exactly_true(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, position="0")
        ex = adapter(fake, clock)
        p = payload("o2", side="buy", reduce=False)
        p["reduceOnly"] = "true"  # truthy but not True: no deadline (DemoClient then refuses the type)
        with self.assertRaises(OSError):
            asyncio.run(ex.submit(p))
        self.assertEqual(ex._deadlines, {})


class TagTests(unittest.TestCase):
    """Point 4: the stricter tag check."""

    def test_4a_empty_or_missing_tag_on_an_order_is_refused(self):
        for tag in ("", None):
            clock = Clock(BASE + 1_000)
            fake = FakeOkx(clock, start_index=3, position="0")
            ex = adapter(fake, clock)
            fake.orders["x1"] = {"ordId": "1", "clOrdId": "x1", "state": "filled", "sz": "1", "accFillSz": "0",
                                 "uTime": "1", "tag": tag}
            if tag is None:
                del fake.orders["x1"]["tag"]
            with self.assertRaises(ipc.ProtocolError):
                asyncio.run(ex.query("x1"))

    def test_4b_conditional_order_without_tag_is_refused(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, position="1")
        ex = adapter(fake, clock)
        fake.algos["a1"] = {"instId": INST, "algoId": "77", "algoClOrdId": "a1", "ordType": "conditional",
                            "state": "effective", "side": "sell", "slTriggerPx": "90", "slTriggerPxType": "mark",
                            "tag": "", "uTime": "1"}
        p = {"instId": INST, "tdMode": "cross", "posSide": "net", "ordType": "conditional", "closeFraction": "1",
             "reduceOnly": True, "tag": TAG, "requestId": "r1", "algoClOrdId": "a1"}
        with self.assertRaises(ipc.ProtocolError):
            asyncio.run(ex.protection("algo_query", p))


class BotLevelTests(unittest.TestCase):
    """Points 1 and 2 end to end: what the Bot and the ledger do."""

    setUp = T.DemoBotTests.setUp
    make_bot = T.DemoBotTests.make_bot
    run_bot = T.DemoBotTests.run_bot
    events = T.DemoBotTests.events
    kill_after = T.DemoBotTests.kill_after

    def kill_with(self, fake, clock, arm, wrap=None):
        engaged = []

        def on_sleep(now):
            if fake.position == 1 and not engaged and now > fake.bar_time(4) + 10_000:
                arm()
                kill_switch.engage(reason="end", actor="cli")
                engaged.append(now)
        return self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))

    def ledger(self, run="run"):
        con = sqlite3.connect(self.root / run / "state.sqlite3")
        con.row_factory = sqlite3.Row
        try:
            orders = [dict(r) for r in con.execute(
                "SELECT cl_ord_id,quantity,filled,state,settled,exchange_id,payload_json FROM execution_orders ORDER BY rowid")]
            owned = con.execute("SELECT position FROM ownership").fetchone()[0]
            reservations = con.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
            risk_orders = con.execute("SELECT COUNT(*) FROM risk_orders").fetchone()[0]
        finally:
            con.close()
        return orders, owned, reservations, risk_orders

    def test_2a_resend_ledger_state_and_timing(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        posts = []
        real = fake.send

        def send(method, target, headers, body):
            if method == "POST" and target == "/api/v5/trade/order":
                posts.append((clock.ms + fake.server_skew, headers.get("expTime"), json.loads(body)["clOrdId"]))
            return real(method, target, headers, body)
        fake.send = send
        status = self.kill_with(fake, clock, lambda: setattr(fake, "drop_posts", 1))
        orders, owned, reservations, risk_orders = self.ledger()
        print(f"\n[2a] stop={status['stop_reason'][:30]} okx_position={fake.position} ledger_owned={owned}")
        for o in orders:
            print("     ", {k: o[k] for k in ("cl_ord_id", "quantity", "filled", "state", "settled", "exchange_id")})
        print(f"     reservations={reservations} risk_orders={risk_orders}")
        lost, resent = posts[1], posts[2]
        print(f"     lost sent at OKX t={lost[0]}, expTime={lost[1]}; resend at OKX t={resent[0]} "
              f"(= expTime + {resent[0] - int(lost[1])} ms)")
        self.assertNotEqual(lost[2], resent[2])
        self.assertGreater(resent[0], int(lost[1]) + okx_demo_exchange.PROOF_MARGIN_MS)
        rejected = [o for o in orders if o["state"] == "REJECTED"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual((rejected[0]["filled"], rejected[0]["settled"], rejected[0]["exchange_id"]),
                         ("0", 1, "rejected" + lost[2]))
        self.assertEqual((owned, reservations, risk_orders), ("0", 0, 0))
        self.assertTrue(all(o["settled"] for o in orders))

    def test_2b_misjudged_flatten_order_stops_on_position_mismatch(self):
        """OKX took the flatten order but never lists it (lag > 15 s): it is called never taken."""
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)

        def arm():
            fake.lose_post_response = True
            fake.hide_orders = 1
        status = self.kill_with(fake, clock, arm)
        orders, owned, *_ = self.ledger()
        print(f"\n[2b] stop={status['stop_reason']} okx_position={fake.position} ledger_owned={owned} "
              f"posts={[(p['side'], p['reduceOnly']) for p in fake.posts]} states={[o['state'] for o in orders]}")
        self.assertTrue(status["stop_reason"].startswith("flatten_failed:position_mismatch:okx=0:ledger=1"), status)
        self.assertEqual(len(fake.posts), 2)  # no second reduce-only order
        self.assertEqual(orders[-1]["state"], "REJECTED")  # the real fill is not in the ledger

    def test_2c_misjudged_reversal_close_then_restart_starts_a_new_run(self):
        """RareCaseTests.lose_the_reversal_close without its time_failures override: the
        accepted-but-unlisted reversal close is now 'proven' never taken."""
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        armed = []

        def on_sleep(now):
            if fake.position == 1 and not armed and now > fake.bar_time(4) + 10_000:
                fake.lose_post_response = True
                fake.hide_orders = 1
                armed.append(now)
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        orders, owned, *_ = self.ledger()
        print(f"\n[2c] first run stop={status['stop_reason']} okx_position={fake.position} ledger_owned={owned} "
              f"states={[o['state'] for o in orders]}")
        fake.hide_orders = 0  # OKX lists it again
        lines = []
        status2 = self.run_bot(self.make_bot(fake, clock, events=lines, on_sleep=self.kill_after(fake, 6), run="run2"))
        print(f"     restart stop={status2['stop_reason'][:40]} new_run_dir={(self.root / 'run2').exists()}")
        for line in lines:
            if "run" in line and ("沒結清" in line or "新的" in line or "接續" in line):
                print("     note:", line[:160])
        orders_after, owned_after, *_ = self.ledger()
        print(f"     old ledger after restart: owned={owned_after} states={[o['state'] for o in orders_after]}")
        self.assertEqual(status["stop_reason"], "order_rejected")
        self.assertTrue((self.root / "run2").exists())  # not continued: the fill is never booked
        self.assertEqual(owned_after, "1")

    def test_2e_backward_clock_step_within_the_offset_cache_fails_the_kill_flatten(self):
        """The reversal close at bar 5 caches the offset. Within 5 minutes the local clock is stepped
        back 10 s relative to OKX (modelled as OKX time +10 s, which is all the adapter can see). The
        Kill flatten's reduce-only orders then carry an expTime already past at OKX: 50036 every round."""
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        engaged = []

        def on_sleep(now):
            if fake.position == -1 and not engaged and now > fake.bar_time(6) + 10_000:
                fake.server_skew = 10_000
                kill_switch.engage(reason="end", actor="cli")
                engaged.append(now)
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        orders, owned, *_ = self.ledger()
        print(f"\n[2e] stop={status['stop_reason']} okx_position={fake.position} "
              f"states={[o['state'] for o in orders]} expTimes_sent={sum(1 for e in fake.exp_times if e)}")
        self.assertTrue(status["stop_reason"].startswith("flatten_failed:flatten_incomplete:okx_position=-1"), status)
        self.assertEqual(fake.position, D("-1"))

    def test_2d_slow_time_read_eats_the_supervisor_timeout(self):
        """public/time answers after 5.5 s (real): the Supervisor's 5 s wait ends before the POST."""
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
        orders, owned, *_ = self.ledger()
        print(f"\n[2d] stop={status['stop_reason']} okx_position={fake.position} "
              f"posts={[(p['side'], p['reduceOnly']) for p in fake.posts]} states={[o['state'] for o in orders]}")
        self.assertTrue(status["stop_reason"].startswith("flatten_failed:order_not_settled:UNKNOWN"), status)
        self.assertEqual(len(fake.posts), 1)  # the flatten order was never sent at all


class MutationTests(unittest.TestCase):
    """Point 5: do the commit's own tests notice a broken proof?"""

    def run_resend_tests(self):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(T.FlattenResendTests)
        result = unittest.TestResult()
        suite.run(result)
        return result.testsRun, len(result.failures) + len(result.errors)

    def test_5a_proof_without_any_waiting(self):
        with mock.patch.object(okx_demo_exchange, "PROOF_MARGIN_MS", -10**12):
            ran, bad = self.run_resend_tests()
        print(f"\n[5a] PROOF_MARGIN_MS=-1e12 (proof right away): FlattenResendTests ran={ran} failed={bad}")
        self.assertEqual(bad, 0)  # documents the gap: nothing checks the waiting time

    def test_5b_proof_ignoring_server_offset(self):
        def never_taken(self, cl, asked):
            return cl in self._deadlines
        with mock.patch.object(OkxDemoExchange, "_never_taken", never_taken):
            ran, bad = self.run_resend_tests()
        print(f"[5b] _never_taken = 'any deadline' : FlattenResendTests ran={ran} failed={bad}")
        self.assertEqual(bad, 0)

    def test_5c_deadline_in_local_time(self):
        orig = OkxDemoExchange._server_offset

        async def zero(self):
            await orig(self)
            return 0
        with mock.patch.object(OkxDemoExchange, "_server_offset", zero):
            ran, bad = self.run_resend_tests()
        print(f"[5c] deadline in local time (offset 0): FlattenResendTests ran={ran} failed={bad}")
        self.assertGreater(bad, 0)  # this one is caught (test_the_deadline_follows_okx_server_time)


if __name__ == "__main__":
    unittest.main()
