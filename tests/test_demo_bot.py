"""OKX Demo Bot end to end against a stateful fake OKX (no network).

Isolated approval file, Kill-Switch file, account locks and output directory.
"""

import asyncio
import io
from decimal import Decimal
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs

from catos import account_lock, demo_bot, kill_switch, risk, strategy_approvals
from catos.demo_bot import DemoBot, find_demo_approval
from catos.okx_demo import TAG, Credentials, DemoClient
from catos.okx_demo_exchange import OkxDemoExchange

D = Decimal
TF = 300_000
BASE = 1_794_801_600_000  # 2026-11-16T02:00:00Z, 10:00 Taipei, aligned to 5 minutes
PROFILE = {
    "schema": "catos.strategy-deployment", "schema_version": 1, "strategy_id": "donchian-breakout",
    "version": "donchian-parameters-v1", "parameters": {"entry_bars": 3, "exit_bars": 2}, "quantity": "1",
    "inst_id": "BTC-USDT-SWAP", "timeframe_ms": TF, "warmup_bars": 3, "initial_balance": "5000",
    "fee_rate": "0.0005", "slippage_bps": "2",
}
# (high, low, close); open = previous close. Three warm-up bars, then live bars.
BARS = [(101, 99, 100), (101, 99, 100), (101, 99, 100),   # warm-up
        (105, 100, 105),                                  # close > 101: long 1
        (105, 103, 104),                                  # hold
        (104, 90, 90),                                    # close < 99: reverse to short 1
        (95, 89, 92), (95, 89, 92), (95, 89, 92)]


class Clock:
    def __init__(self, ms):
        self.ms = ms

    def __call__(self):
        return self.ms


class FakeOkx:
    """Market orders fill immediately at the last closed bar's close; fee 0.05% of notional."""

    def __init__(self, clock, *, start_index, position="0", pending=0, reject=False, lose_after_fill=None,
                 loss="600", uid="u1"):
        self.clock = clock
        self.start_index = start_index  # bar index that is forming at clock start
        self.position = D(position)
        self.pending = pending
        self.reject = reject
        self.equity = D("5000")
        self.orders = {}
        self.fills = {}
        self.posts = []
        self.lose_after_fill = lose_after_fill
        self.loss = D(loss)
        self.uid = uid
        self.others = []          # (instId, pos) rows on other contracts
        self.balance_failures = 0  # next N balance reads answer HTTP 503
        self.lose_post_response = False  # the next order is accepted but its response is lost
        self.hide_orders = 0       # order queries answer "does not exist" while this is set
        self.algos = {}            # algoClOrdId -> conditional order (P6 disaster stop)
        self.algo_posts = []       # (path, body) of every algo write
        self.foreign_algos = []    # conditional orders someone else placed
        self.reject_algo = None    # sCode to refuse the next algo create with
        self.lose_algo_create = False  # the next algo create never reaches OKX (connection error)
        # Gemini review 2026-11-18 (all unverified OKX behavior, modeled as the worst case):
        self.auto_cancel_on_flat = False   # OKX cancels the whole-position stop once the position is 0
        self.finished_algos_vanish = False  # order-algo answers 51603 for finished stops (history has them)
        self.reject_amend = None           # sCode every amend is refused with while set
        self.cancel_race = False           # the stop ends just before our cancel arrives: 51402
        self.partial_fill = None           # the next order fills only this size; the rest is canceled
        self.lag_after_cancel = 0          # after our cancel, the next N order-algo looks (and that round's
        self.algo_lag, self.last_hidden = 0, False  # history look) do not show the stop yet
        self.amend_source_lag = 0          # after an amend, the next N order-algo looks still show the old source
        self.pending_source = None

    def trigger_stop(self):
        """OKX fires the live disaster stop: the whole position is closed at market."""
        algo = next(a for a in self.algos.values() if a["state"] == "live")
        algo["state"] = "effective"
        self.position = D("0")

    def bar_time(self, index):
        return BASE + (index - self.start_index) * TF

    def closed(self):
        return [i for i in range(len(BARS)) if self.bar_time(i) + TF <= self.clock.ms]

    def mark(self):
        index = self.closed()[-1]
        return D(BARS[index][2])

    def send(self, method, target, headers, body):
        assert headers["x-simulated-trading"] == "1"
        path, _, query = target.partition("?")
        q = {k: v[0] for k, v in parse_qs(query).items()}
        ok = lambda data: (200, json.dumps({"code": "0", "data": data}).encode())
        if path == "/api/v5/account/config":
            return ok([{"acctLv": "2", "posMode": "net_mode", "perm": "read_only,trade", "label": "t", "uid": self.uid}])
        if path == "/api/v5/public/instruments":
            return ok([{"instId": "BTC-USDT-SWAP", "ctVal": "0.01", "lotSz": "0.01", "minSz": "0.01",
                        "tickSz": "0.1", "state": "live"}])
        if path == "/api/v5/public/mark-price":
            return ok([{"markPx": str(self.mark())}])
        if path == "/api/v5/account/balance":
            if self.balance_failures:
                self.balance_failures -= 1
                return 503, b'{"code":"50001","msg":"Service temporarily unavailable","data":[]}'
            return ok([{"totalEq": str(self.equity), "mgnRatio": "50" if self.position else "",
                        "details": [{"ccy": "USDT", "eq": str(self.equity), "availEq": str(self.equity)}]}])
        if path == "/api/v5/account/positions":
            rows = [{"instId": inst, "pos": pos, "mgnMode": "cross", "avgPx": "10"} for inst, pos in self.others]
            return ok(rows + ([{"instId": "BTC-USDT-SWAP", "pos": str(self.position), "mgnMode": "cross", "avgPx": "100"}]
                              if self.position else []))
        if path == "/api/v5/trade/orders-pending":
            return ok([{"instId": "BTC-USDT-SWAP", "ordId": str(9000 + i), "side": "buy", "sz": "1", "state": "live"}
                       for i in range(self.pending)])
        if path == "/api/v5/market/candles":
            rows = []
            for i in range(len(BARS)):
                t = self.bar_time(i)
                if t > self.clock.ms:
                    break
                high, low, close = BARS[i]
                opened = BARS[i - 1][2] if i else close
                rows.append([str(t), str(opened), str(high), str(low), str(close), "1", "1", "1",
                             "1" if t + TF <= self.clock.ms else "0"])
            rows.reverse()
            return ok(rows[:int(q["limit"])])
        if method == "POST" and path == "/api/v5/trade/order":
            p = json.loads(body)
            self.posts.append(p)
            assert p["tag"] == TAG and p["tdMode"] == "cross" and p["posSide"] == "net"
            if self.reject:
                return 200, json.dumps({"code": "1", "msg": "failed", "data": [{"sCode": "51008", "sMsg": "margin"}]}).encode()
            size = D(p["sz"])
            if p["reduceOnly"]:
                assert self.position != 0 and (self.position > 0) == (p["side"] == "sell") and size <= abs(self.position)
            price = self.mark()
            ord_id = str(4000 + len(self.orders))
            state = "filled"
            if self.partial_fill is not None:
                size, state, self.partial_fill = D(self.partial_fill), "canceled", None
            fee = -(size * D("0.01") * price * D("0.0005"))
            self.position += size if p["side"] == "buy" else -size
            self.equity += fee
            if self.auto_cancel_on_flat and self.position == 0:
                for algo in self.algos.values():
                    if algo["state"] == "live":
                        algo["state"] = "canceled"
            self.orders[p["clOrdId"]] = {"ordId": ord_id, "clOrdId": p["clOrdId"], "state": state, "sz": p["sz"],
                                         "accFillSz": str(size), "uTime": str(self.clock.ms), "tag": TAG}
            self.fills[ord_id] = [{"ordId": ord_id, "tradeId": "t" + ord_id, "fillSz": str(size),
                                   "fillPx": str(price), "fee": str(fee)}]
            if self.lose_after_fill is not None and len(self.orders) == self.lose_after_fill:
                self.equity -= self.loss  # an outside loss (600 = 12% of the day basis)
            if self.lose_post_response:
                self.lose_post_response = False
                raise ConnectionError("accepted, response lost")
            return ok([{"ordId": ord_id, "clOrdId": p["clOrdId"], "sCode": "0"}])
        if method == "GET" and path == "/api/v5/trade/order":
            order = self.orders.get(q.get("clOrdId"))
            if order is None or self.hide_orders:
                return 200, json.dumps({"code": "51603", "msg": "Order does not exist", "data": []}).encode()
            return ok([order])
        if path == "/api/v5/trade/fills":
            return ok(self.fills.get(q["ordId"], []))
        if path == "/api/v5/trade/orders-algo-pending":
            rows = [a for a in list(self.algos.values()) + self.foreign_algos
                    if a["state"] == "live" and a["ordType"] == q["ordType"]]
            return ok([dict(a) for a in rows])
        if method == "GET" and path == "/api/v5/trade/order-algo":
            algo = self.algos.get(q.get("algoClOrdId"))
            self.last_hidden = self.algo_lag > 0
            if self.last_hidden:
                self.algo_lag -= 1
                return 200, json.dumps({"code": "51603", "msg": "Order does not exist", "data": []}).encode()
            if algo is None or (self.finished_algos_vanish and algo["state"] != "live"):
                return 200, json.dumps({"code": "51603", "msg": "Order does not exist", "data": []}).encode()
            if self.pending_source is not None:
                if self.amend_source_lag:
                    self.amend_source_lag -= 1
                else:
                    algo["slTriggerPxType"], self.pending_source = self.pending_source, None
            return ok([dict(algo)])
        if method == "GET" and path == "/api/v5/trade/orders-algo-history":
            assert q["ordType"] == "conditional" and q["instType"] == "SWAP" and "algoClOrdId" not in q
            if self.last_hidden:
                return ok([])
            return ok([dict(a) for a in self.algos.values() if a["state"] == q["state"] and a["instId"] == q["instId"]])
        if method == "POST" and path == "/api/v5/trade/order-algo":
            p = json.loads(body)
            self.algo_posts.append((path, p))
            assert p["tag"] == TAG and p["closeFraction"] == "1" and p["reduceOnly"] is True and p["slOrdPx"] == "-1"
            assert p["slTriggerPxType"] == "mark" and p["ordType"] == "conditional" and "requestId" not in p
            if self.lose_algo_create:
                self.lose_algo_create = False
                raise ConnectionError("never reached OKX")
            if self.reject_algo:
                code, self.reject_algo = self.reject_algo, None
                return 200, json.dumps({"code": "1", "msg": "", "data": [{"sCode": code, "sMsg": "refused"}]}).encode()
            algo_id = str(7000 + len(self.algo_posts))
            self.algos[p["algoClOrdId"]] = {"instId": p["instId"], "algoId": algo_id, "algoClOrdId": p["algoClOrdId"],
                                            "ordType": "conditional", "state": "live", "side": p["side"],
                                            "slTriggerPx": p["slTriggerPx"], "slTriggerPxType": p["slTriggerPxType"],
                                            "tag": TAG, "uTime": str(self.clock.ms)}
            return ok([{"algoId": algo_id, "algoClOrdId": p["algoClOrdId"], "sCode": "0"}])
        if method == "POST" and path == "/api/v5/trade/amend-algos":
            p = json.loads(body)
            self.algo_posts.append((path, p))
            algo = self.algos[p["algoClOrdId"]]
            assert algo["state"] == "live" and p["newSlOrdPx"] == "-1"
            if self.reject_amend:
                return 200, json.dumps({"code": "1", "msg": "", "data": [{"sCode": self.reject_amend,
                                                                          "sMsg": "refused"}]}).encode()
            algo.update(slTriggerPx=p["newSlTriggerPx"], uTime=str(self.clock.ms))
            if self.amend_source_lag:
                self.pending_source = p["newSlTriggerPxType"]
            else:
                algo["slTriggerPxType"] = p["newSlTriggerPxType"]
            return ok([{"algoId": algo["algoId"], "reqId": p["reqId"], "sCode": "0"}])
        if method == "POST" and path == "/api/v5/trade/cancel-algos":
            p = json.loads(body)
            self.algo_posts.append((path, p))
            for item in p:
                algo = next(a for a in self.algos.values() if a["algoId"] == item["algoId"])
                algo["state"] = "canceled"
            self.algo_lag = self.lag_after_cancel
            if self.cancel_race:
                self.cancel_race = False
                return 200, json.dumps({"code": "1", "msg": "", "data": [{"algoId": p[0]["algoId"], "sCode": "51402",
                                                                          "sMsg": "already canceled"}]}).encode()
            return ok([{"algoId": item["algoId"], "sCode": "0"} for item in p])
        raise AssertionError(target)


class DemoBotTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.root, ignore_errors=True))
        patches = [mock.patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks"),
                   mock.patch.object(demo_bot, "ACCOUNTS_DIRECTORY", self.root / "accounts"),
                   mock.patch.dict(os.environ, {strategy_approvals.ENV_PATH: str(self.root / "approvals.jsonl"),
                                                kill_switch.ENV_PATH: str(self.root / "kill.jsonl")})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        sha = strategy_approvals.deployment_identity(PROFILE)[0]["sha256"]
        strategy_approvals.approve(strategy_id=PROFILE["strategy_id"], version=PROFILE["version"], sha256=sha,
                                   profile=PROFILE, confirm=lambda text, word: True)
        self.record = find_demo_approval(PROFILE)

    def make_bot(self, fake, clock, events=None, on_sleep=None, limits=None, run="run", disaster_stop=D("0"),
                 new_run=False):
        """``run`` may be a nested path: another output root shares the same account files."""
        client = DemoClient(Credentials("k", "s", "p"), fake, clock_ms=clock, sleep=lambda s: None, monotonic=lambda: 0.0)
        lines = [] if events is None else events

        async def sleep(seconds):
            clock.ms += int(seconds * 1000) or 1
            if on_sleep is not None:
                on_sleep(clock.ms)

        return DemoBot(client=client, record=self.record, output_dir=self.root / run, echo=lines.append,
                       wall_ms=clock, sleep=sleep, limits=limits, disaster_stop=disaster_stop, new_run=new_run)

    def run_bot(self, bot):
        return asyncio.run(bot.run())

    def events(self, run="run"):
        return [json.loads(line) for line in (self.root / run / "events.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_trades_reverses_and_kill_flattens_through_supervisor(self):
        clock = Clock(BASE + 1_000)  # bar index 3 is forming; bars 0..2 are the warm-up
        fake = FakeOkx(clock, start_index=3)
        engaged = []

        def on_sleep(now):
            # Engage once the reversal bar (index 5) has been processed.
            if not engaged and now > fake.bar_time(6) + 10_000:
                kill_switch.engage(reason="test stop", actor="cli")
                engaged.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        self.assertEqual(status["state"], "stopped", status)
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual(fake.position, 0)
        self.assertEqual([(p["side"], p["sz"], p["reduceOnly"]) for p in fake.posts],
                         [("buy", "1", False), ("sell", "1", True), ("sell", "1", False), ("buy", "1", True)])
        self.assertTrue(all(p["tag"] == TAG for p in fake.posts))
        kinds = [e["kind"] for e in self.events()]
        self.assertIn("day_basis", kinds)
        self.assertEqual(kinds.count("fill"), 4)
        self.assertIn("flatten_done", kinds)
        state = json.loads((self.root / "run" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(state["position"], "0")
        self.assertEqual(state["fills"], 4)

    def test_refuses_foreign_position_or_orders_before_creating_a_ledger(self):
        for kwargs in ({"position": "1"}, {"pending": 1}):
            clock = Clock(BASE + 1_000)
            fake = FakeOkx(clock, start_index=3, **kwargs)
            status = self.run_bot_quietly(fake, clock)
            self.assertIn("contract_not_flat_at_start", status)
            self.assertEqual(fake.posts, [])
            self.assertFalse((self.root / "run").exists())

    def run_bot_quietly(self, fake, clock, run="run"):
        from catos.demo_bot import BotStopped
        try:
            self.run_bot(self.make_bot(fake, clock, run=run))
        except BotStopped as exc:
            return exc.reason
        return "ran"

    def test_refuses_when_kill_switch_engaged(self):
        kill_switch.engage(reason="pre", actor="cli")
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        with self.assertRaises(kill_switch.KillSwitchError):
            self.run_bot(self.make_bot(fake, clock))
        self.assertEqual(fake.posts, [])

    def test_position_changed_outside_stops_without_adopting(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)

        def on_sleep(now):
            if now > fake.bar_time(4) + 5_000 and fake.position == 1:
                fake.position = D("3")  # someone traded by hand

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        self.assertEqual(status["state"], "stopped")
        self.assertTrue(status["stop_reason"].startswith("position_mismatch:okx=3"), status)
        self.assertEqual(len(fake.posts), 1)

    def test_rejected_order_stops_without_resending(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, reject=True)
        status = self.run_bot(self.make_bot(fake, clock))
        self.assertEqual(status["stop_reason"], "order_rejected", status)
        self.assertEqual(len(fake.posts), 1)

    def test_hard_loss_latches_and_flattens(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, lose_after_fill=1)
        status = self.run_bot(self.make_bot(fake, clock))
        self.assertEqual(status["state"], "stopped", status)
        self.assertIn("hard_loss", status["stop_reason"])
        self.assertEqual(fake.position, 0)
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts], [("buy", False), ("sell", True)])

    def test_soft_loss_blocks_increase_but_keeps_running(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake_loss = []
        engaged = []

        def on_sleep(now):
            if fake.posts and not fake_loss:
                fake.equity -= D("300")  # 6% of the day basis: Soft, not Hard
                fake_loss.append(now)
            if not engaged and now > fake.bar_time(7) + 10_000:
                kill_switch.engage(reason="end", actor="cli")
                engaged.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        # Under Soft the reversal's short is refused, but the long is still closed (2026-11-17,
        # user "改"): one reduce-only sell at the reversal bar; the Kill then has nothing to flatten.
        bars = [e for e in self.events() if e["kind"] == "bar"]
        self.assertIn(("RESERVED_SIMULATION", "reversal_close_only"), [(e["disposition"], e["reason"]) for e in bars])
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts], [("buy", False), ("sell", True)])
        closed_at = next(e for e in bars if e["reason"] == "reversal_close_only")["bar"]["open_time_ms"]
        self.assertEqual(closed_at, fake.bar_time(5))
        self.assertEqual(fake.position, 0)

    # ---- independent acceptance 2026-11-17: D1–D4 and observations ----
    def test_flatten_survives_a_failed_read(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        engaged = []

        def on_sleep(now):
            if not engaged and fake.position == 1 and now > fake.bar_time(4) + 10_000:
                kill_switch.engage(reason="test stop", actor="cli")
                fake.balance_failures = 1  # the flatten's first account read answers 503
                engaged.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual(fake.position, 0)
        kinds = [e["kind"] for e in self.events()]
        self.assertIn("read_retry", kinds)
        self.assertIn("flatten_done", kinds)

    def test_hard_loss_engages_kill_switch_and_blocks_a_restart(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, lose_after_fill=1)
        status = self.run_bot(self.make_bot(fake, clock))
        self.assertIn("hard_loss", status["stop_reason"])
        self.assertEqual(fake.position, 0)
        # Flattened by the minute check, before the bar that was open at the loss closed.
        self.assertLess(clock.ms, fake.bar_time(5))
        records = kill_switch.read_records(Path(os.environ[kill_switch.ENV_PATH]))
        self.assertEqual((records[-1]["action"], records[-1]["actor"]), ("engage", "demo-bot"))
        with self.assertRaises(kill_switch.KillSwitchError):
            kill_switch.clear(reason="agent", actor="demo-bot", confirm=kill_switch.CONFIRM_WORD)
        with self.assertRaises(kill_switch.KillSwitchError):
            self.run_bot(self.make_bot(FakeOkx(clock, start_index=3), clock, run="run2"))

    def test_same_day_restart_keeps_the_basis_and_the_soft_latch(self):
        from catos.demo_bot import rearm_main
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)

        def on_sleep(now):
            if fake.posts and fake.equity > D("4800"):
                fake.equity -= D("300")  # 6%: Soft
            if fake.equity < D("4800") and now > fake.bar_time(5) + 10_000:
                (self.root / "run" / "stop.request").write_text("", encoding="utf-8")

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        self.assertEqual(status["stop_reason"], "operator_stop_file", status)
        fake.position = D("0")  # closed by hand on OKX before the restart
        (self.root / "other-root").mkdir()
        second = self.make_bot(fake, clock, run="other-root/run2")  # a different --output-root
        self.run_bot(second)
        events = self.events("other-root/run2")
        basis = [e for e in events if e["kind"] == "day_basis"]
        self.assertEqual(basis[0]["basis"]["equity"], "5000")  # not the equity after the loss
        self.assertIn("soft_latched", [e["kind"] for e in events])
        state_file = next((self.root / "accounts").glob("*.json"))
        self.assertTrue(json.loads(state_file.read_text(encoding="utf-8"))["soft_latched"])
        self.assertNotIn('"u1"', state_file.read_text(encoding="utf-8"))  # the uid is not a stored value
        # Only an interactive confirmation clears it.
        with mock.patch("sys.stdout", new=io.StringIO()), mock.patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(rearm_main(["--reason", "test"]), 1)
            self.assertEqual(rearm_main(["--reason", "test"], confirm=lambda text, word: word), 0)
        state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertFalse(state["soft_latched"])
        self.assertEqual(state["rearms"][0]["reason"], "test")

    def test_unreadable_account_file_is_not_rebuilt(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.run_bot_quietly(fake, clock)
        state_file = next((self.root / "accounts").glob("*.json"))
        state_file.write_text("{", encoding="utf-8")
        reason = self.run_bot_quietly(FakeOkx(clock, start_index=3), clock, run="run2")
        self.assertTrue(reason.startswith("account_state_unreadable"), reason)
        # Deleted next to its lock: lost, not new; no first observation is rebuilt.
        state_file.unlink()
        reason = self.run_bot_quietly(FakeOkx(clock, start_index=3), clock, run="run3")
        self.assertTrue(reason.startswith("account_state_missing"), reason)
        self.assertFalse((self.root / "run3").exists())
        # Only deleting both files (the user's decision) starts over.
        state_file.with_suffix(".lock").unlink()
        self.assertEqual(self.run_bot_quietly(FakeOkx(clock, start_index=3), clock, run="run4"), "ran")

    def test_positions_on_other_contracts_are_foreign(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake.others = [("ETH-USDT-SWAP", "1")]
        self.assertEqual(self.run_bot_quietly(fake, clock), "foreign_positions_or_orders_in_account:ETH-USDT-SWAP")
        self.assertEqual(fake.posts, [])

        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)

        def on_sleep(now):
            if fake.position == 1 and not fake.others:
                fake.others = [("ETH-USDT-SWAP", "1")]

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep, run="run2"))
        self.assertEqual(status["stop_reason"], "foreign_positions_or_orders_in_account:ETH-USDT-SWAP", status)
        self.assertEqual(len(fake.posts), 1)

    def test_one_bot_per_okx_account(self):
        from catos.demo_bot import AccountGuard
        guard = AccountGuard(self.root / "accounts", "u1")
        guard.acquire()
        try:
            clock = Clock(BASE + 1_000)
            fake = FakeOkx(clock, start_index=3)
            self.assertTrue(self.run_bot_quietly(fake, clock).startswith("account_busy"))
            self.assertEqual(fake.posts, [])
            self.assertFalse((self.root / "run").exists())
        finally:
            guard.release()

    def test_soft_between_reversal_legs_keeps_running_flat(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, lose_after_fill=2, loss="300")
        engaged = []

        def on_sleep(now):
            if not engaged and now > fake.bar_time(7) + 10_000:
                kill_switch.engage(reason="end", actor="cli")
                engaged.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts], [("buy", False), ("sell", True)])
        self.assertEqual(fake.position, 0)
        orders = [e for e in self.events() if e["kind"] == "order"]
        self.assertEqual(len(orders), 1)  # the refused opening leg; the run went on to the Kill

    def test_only_the_authorized_contract(self):
        from catos.demo_bot import BotStopped
        record = dict(self.record, profile=dict(PROFILE, inst_id="ETH-USDT-SWAP"))
        clock = Clock(BASE)
        with self.assertRaises(BotStopped):
            DemoBot(client=DemoClient(Credentials("k", "s", "p"), FakeOkx(clock, start_index=3)), record=record,
                    output_dir=self.root / "run")

    # ---- third recheck observations O1/O3 ----
    def test_failed_first_write_leaves_the_account_new(self):
        from catos.demo_bot import AccountGuard
        clock = Clock(BASE + 1_000)
        with mock.patch.object(AccountGuard, "save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.run_bot(self.make_bot(FakeOkx(clock, start_index=3), clock))
        self.assertEqual(list((self.root / "accounts").glob("*")), [])
        self.assertEqual(self.run_bot_quietly(FakeOkx(clock, start_index=3), clock, run="run2"), "ran")

    def test_lock_is_released_when_closing_the_supervisor_fails(self):
        from catos.demo_bot import AccountGuard
        from catos.supervisor import LocalSupervisor
        clock = Clock(BASE + 1_000)
        real_close = LocalSupervisor.close

        async def failing_close(supervisor):
            await real_close(supervisor)  # the Worker still stops; only the result is an error
            raise RuntimeError("close failed")

        with mock.patch.object(LocalSupervisor, "close", failing_close):
            status = self.run_bot(self.make_bot(FakeOkx(clock, start_index=3), clock))
        self.assertIn("close_error", status)
        guard = AccountGuard(self.root / "accounts", "u1")
        guard.acquire()  # would raise BotStopped(account_busy) if the run kept the lock
        guard.release()

    def test_old_approval_does_not_cover_demo(self):
        record = dict(self.record, created_at="2026-11-13T10:32:37+00:00")
        with mock.patch.object(strategy_approvals, "find_active", return_value=record):
            with self.assertRaises(strategy_approvals.ApprovalError):
                find_demo_approval(PROFILE)

    # ---- resuming a stopped run (2026-11-17) ----
    def stop_while_long(self, fake, clock, *, delay=5_000, extra=None):
        """Run until the long from bar 3 is held, then stop with stop.request (position kept)."""
        def on_sleep(now):
            if extra is not None:
                extra(now)
            if fake.position == 1 and now > fake.bar_time(4) + delay:
                (self.root / "run" / "stop.request").write_text("", encoding="utf-8")

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        self.assertEqual((status["stop_reason"], status["position"]), ("operator_stop_file", "1"), status)
        return status

    def kill_after(self, fake, index):
        engaged = []

        def on_sleep(now):
            if not engaged and now > fake.bar_time(index) + 10_000:
                kill_switch.engage(reason="end", actor="cli")
                engaged.append(now)
        return on_sleep

    def test_resume_continues_the_stopped_run_and_its_position(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.stop_while_long(fake, clock)
        state_file = next((self.root / "accounts").glob("*.json"))
        pointer = json.loads(state_file.read_text(encoding="utf-8"))["run"]
        self.assertEqual(Path(pointer["dir"]), (self.root / "run").resolve())
        clock.ms = fake.bar_time(6) + 1_000  # bars 4 and 5 closed while stopped
        lines = []
        status = self.run_bot(self.make_bot(fake, clock, events=lines, on_sleep=self.kill_after(fake, 7), run="run2"))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertFalse((self.root / "run2").exists())  # the stopped run's folder is reused
        # Bar 4 was only fed to the strategy; bar 5 (the newest closed bar) reversed the position.
        self.assertEqual([(p["side"], p["sz"], p["reduceOnly"]) for p in fake.posts],
                         [("buy", "1", False), ("sell", "1", True), ("sell", "1", False), ("buy", "1", True)])
        self.assertEqual(fake.position, 0)
        events = self.events()
        catch_up = [e for e in events if e["kind"] == "bar" and e.get("catch_up")]
        self.assertEqual([(e["seq"], e["bar"]["open_time_ms"]) for e in catch_up], [(5, fake.bar_time(4))])
        self.assertTrue(any(e["kind"] == "started" and e.get("resumed") for e in events))
        self.assertTrue(any("接續" in line for line in lines))
        manifest = json.loads((self.root / "run" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["resumes"]), 1)
        fills = json.loads((self.root / "run" / "fills.json").read_text(encoding="utf-8"))
        self.assertEqual(len(fills), 4)  # the first run's fill is kept
        self.assertTrue(list((self.root / "run").glob("stop.request.used-*")))

    def test_resume_refuses_what_the_ledger_does_not_own(self):
        import shutil
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.stop_while_long(fake, clock)
        manifest_before = (self.root / "run" / "manifest.json").read_text(encoding="utf-8")
        fake.position = D("2")  # someone added by hand on OKX
        reason = self.run_bot_quietly(fake, clock, run="run2")
        self.assertEqual(reason, "resume_position_mismatch:okx=2:ledger=1")
        self.assertEqual(len(fake.posts), 1)
        self.assertEqual((self.root / "run" / "manifest.json").read_text(encoding="utf-8"), manifest_before)
        fake.position = D("1")
        shutil.rmtree(self.root / "run")
        self.assertTrue(self.run_bot_quietly(fake, clock, run="run3").startswith("resume_run_unreadable"))
        self.assertEqual(len(fake.posts), 1)

    def test_resume_refuses_after_a_new_approval(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.stop_while_long(fake, clock)
        strategy_approvals.revoke(approval_id=self.record["record_id"], confirm=lambda text, word: True)
        sha = strategy_approvals.deployment_identity(PROFILE)[0]["sha256"]
        strategy_approvals.approve(strategy_id=PROFILE["strategy_id"], version=PROFILE["version"], sha256=sha,
                                   profile=PROFILE, confirm=lambda text, word: True)
        self.record = find_demo_approval(PROFILE)
        self.assertEqual(self.run_bot_quietly(fake, clock, run="run2"), "resume_approval_changed")
        self.assertEqual(len(fake.posts), 1)

    def test_resume_does_not_bridge_a_gap_longer_than_one_candles_page(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.stop_while_long(fake, clock)
        clock.ms = fake.bar_time(6) + 1_000
        with mock.patch.object(demo_bot, "RESUME_CANDLES", 1):
            status = self.run_bot(self.make_bot(fake, clock, run="run2"))
        self.assertTrue(status["stop_reason"].startswith("resume_gap_too_long"), status)
        self.assertEqual(len(fake.posts), 1)
        self.assertEqual(fake.position, 1)

    def test_resume_settles_an_uncertain_order_first(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake.lose_post_response = True  # the buy is accepted, its response lost: UNKNOWN
        fake.hide_orders = 1
        status = self.run_bot(self.make_bot(fake, clock))
        self.assertTrue(status["stop_reason"].startswith("order_not_settled:UNKNOWN"), status)
        self.assertEqual(fake.position, 1)
        fake.hide_orders = 0  # OKX answers again
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 4), run="run2"))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts], [("buy", False), ("sell", True)])
        legs = [f["leg"] for f in json.loads((self.root / "run" / "fills.json").read_text(encoding="utf-8"))]
        self.assertEqual(legs, ["接續時補查", "清倉"])

    def test_resume_refeeds_an_unfinished_bar_with_the_same_bytes(self):
        from catos.worker_host import WorkerHost
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        real = WorkerHost.process_bar
        calls = []

        async def interrupted(host, bar, account):
            calls.append(bar.open_time_ms)
            if len(calls) == 5:  # bar 4, after the long from bar 3
                raise KeyboardInterrupt
            return await real(host, bar, account)

        with mock.patch.object(WorkerHost, "process_bar", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.run_bot(self.make_bot(fake, clock))
        state = json.loads((self.root / "run" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual((state["state"], state["stop_reason"], fake.position), ("stopped", "interrupted", 1))
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 7), run="run2"))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        events = self.events()
        self.assertIn("resume_input", [e["kind"] for e in events])
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts],
                         [("buy", False), ("sell", True), ("sell", False), ("buy", True)])

    def test_resume_never_sends_an_intent_the_stopped_run_did_not_send(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        real = DemoBot._execute
        calls = []

        async def interrupted(bot, receipt, facts, now_ms):
            calls.append(receipt.intent_key)
            if len(calls) == 2:  # the reversal from bar 5 is committed, then the process dies
                raise KeyboardInterrupt
            return await real(bot, receipt, facts, now_ms)

        with mock.patch.object(DemoBot, "_execute", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.run_bot(self.make_bot(fake, clock))
        self.assertEqual(len(fake.posts), 1)
        # Restarted at once, inside the intent's deadline: it is waited out and ended unsent.
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 7), run="run2"))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertIn("resume_intent", [e["kind"] for e in self.events()])
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts], [("buy", False), ("sell", True)])

    def test_resume_follows_a_soft_rearm_made_while_stopped(self):
        from catos.demo_bot import rearm_main
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        dropped = []

        def drop(now):
            if fake.posts and not dropped:
                fake.equity -= D("300")  # 6%: Soft
                dropped.append(now)

        self.stop_while_long(fake, clock, delay=70_000, extra=drop)  # after a minute check saw the loss
        state_file = next((self.root / "accounts").glob("*.json"))
        self.assertTrue(json.loads(state_file.read_text(encoding="utf-8"))["soft_latched"])
        with mock.patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(rearm_main(["--reason", "checked"], confirm=lambda text, word: word), 0)
        fake.equity += D("300")  # recovered: the cause is gone
        clock.ms = fake.bar_time(5) + 1_000
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 7), run="run2"))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertIn("soft_rearmed", [e["kind"] for e in self.events()])
        # Both legs of the reversal went out: Soft no longer blocks the opening leg.
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts],
                         [("buy", False), ("sell", True), ("sell", False), ("buy", True)])
        self.assertFalse(json.loads(state_file.read_text(encoding="utf-8"))["soft_latched"])

    def test_resume_without_a_rearm_keeps_the_ledger_soft_latch(self):
        """Saving the account file failed when Soft latched: resuming must not clear Soft by itself."""
        from catos.demo_bot import AccountGuard
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        real_save = AccountGuard.save

        def failing_save(guard, state):
            if state.get("soft_latched"):
                raise OSError("disk full")
            return real_save(guard, state)

        def on_sleep(now):
            if fake.posts and fake.equity > D("4800") and now > fake.bar_time(4) + 70_000:
                fake.equity -= D("300")  # 6%: Soft

        with mock.patch.object(AccountGuard, "save", failing_save):
            status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        self.assertEqual((status["state"], status["position"]), ("failed", "1"), status)
        state_file = next((self.root / "accounts").glob("*.json"))
        stored = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertFalse(stored["soft_latched"])
        # A rearm from before this run stopped does not count either.
        stored["rearms"] = [dict(at="2026-11-16T01:00:00+00:00", reason="old", cleared="x")]
        state_file.write_text(json.dumps(stored), encoding="utf-8")
        fake.equity += D("300")  # recovered, but nobody ran demo rearm
        clock.ms = fake.bar_time(5) + 1_000
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 7), run="run2"))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        kinds = [e["kind"] for e in self.events()]
        self.assertNotIn("soft_rearmed", kinds)
        self.assertIn("soft_latched", kinds)
        # Only the closing leg of the reversal went out: Soft still blocks the opening leg.
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts], [("buy", False), ("sell", True)])
        self.assertTrue(json.loads(state_file.read_text(encoding="utf-8"))["soft_latched"])


class DisasterStopTests(unittest.TestCase):
    """P6 on OKX Demo (2026-11-17, user: 10%, stop and tell me when it fires, a start option)."""

    setUp = DemoBotTests.setUp
    make_bot = DemoBotTests.make_bot
    run_bot = DemoBotTests.run_bot
    events = DemoBotTests.events
    run_bot_quietly = DemoBotTests.run_bot_quietly
    kill_after = DemoBotTests.kill_after
    TEN = D("0.10")

    def algo_writes(self, fake):
        return [(path.rsplit("/", 1)[1], body if isinstance(body, list) else
                 {k: body.get(k) for k in ("side", "slTriggerPx", "newSlTriggerPx") if k in body})
                for path, body in fake.algo_posts]

    def test_the_stop_follows_entries_reversals_and_the_kill_flatten(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 6), disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts],
                         [("buy", False), ("sell", True), ("sell", False), ("buy", True)])
        writes = self.algo_writes(fake)
        # Long 1 at 105: sell stop at 94.5. Reversal: that stop is canceled before the short at 90
        # opens, then a buy stop at 99. The Kill flatten cancels the last one.
        self.assertEqual([w[0] for w in writes], ["order-algo", "cancel-algos", "order-algo", "cancel-algos"])
        self.assertEqual(writes[0][1], {"side": "sell", "slTriggerPx": "94.5"})
        self.assertEqual(writes[2][1], {"side": "buy", "slTriggerPx": "99.0"})
        self.assertEqual([a["state"] for a in fake.algos.values()], ["canceled", "canceled"])
        self.assertEqual(fake.position, 0)
        manifest = json.loads((self.root / "run" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["disaster_stop"], "0.10")

    def test_off_by_default_sends_no_conditional_order(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 6)))
        self.assertEqual(fake.algo_posts, [])
        self.assertEqual(len(fake.posts), 4)

    def test_a_fired_stop_ends_the_run_and_a_restart_starts_flat(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fired = []

        def on_sleep(now):
            if fake.algos and not fired and now > fake.bar_time(4) + 20_000:
                fake.trigger_stop()  # the computer was fine, but OKX hit the stop first
                fired.append(now)

        lines = []
        status = self.run_bot(self.make_bot(fake, clock, events=lines, on_sleep=on_sleep, disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("disaster_stop_triggered"), status)
        self.assertEqual(len(fake.posts), 1)  # nothing sent after the stop fired
        self.assertLess(clock.ms, fake.bar_time(5))  # noticed by a minute check, not at the next bar
        self.assertIn("保底停損", demo_bot._hint(status["stop_reason"]))
        # OKX is flat now: the next start is a new run, not a resume.
        self.assertEqual(self.run_bot_quietly(FakeOkx(clock, start_index=3), clock, run="run2"), "ran")

    def test_conditional_orders_from_someone_else_are_foreign(self):
        foreign = {"instId": "BTC-USDT-SWAP", "algoId": "1", "algoClOrdId": "manual1", "ordType": "conditional",
                   "state": "live", "side": "sell", "slTriggerPx": "90", "slTriggerPxType": "last", "tag": ""}
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake.foreign_algos = [foreign]
        self.assertTrue(self.run_bot_quietly(fake, clock).startswith("contract_not_flat_at_start"))
        fake.foreign_algos = [dict(foreign, instId="ETH-USDT-SWAP", ordType="oco")]
        self.assertEqual(self.run_bot_quietly(fake, clock, run="run2"), "foreign_positions_or_orders_in_account:ETH-USDT-SWAP")
        self.assertEqual((fake.posts, fake.algo_posts), ([], []))

        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)

        def on_sleep(now):
            if fake.position == 1 and not fake.foreign_algos and now > fake.bar_time(4) + 10_000:
                fake.foreign_algos = [foreign]

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep, run="run3", disaster_stop=self.TEN))
        self.assertEqual(status["stop_reason"], "foreign_algo_orders_on_contract:manual1", status)
        self.assertEqual(len(fake.posts), 1)

    def test_a_refused_stop_is_retried_and_blocks_increases_meanwhile(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake.reject_algo = "51277"
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 6), disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        events = self.events()
        self.assertIn("protection_request_failed", [e.get("alert") for e in events if e["kind"] == "protection_alert"])
        # Retried at the next minute check; the run went on and the reversal still traded.
        self.assertEqual([w[0] for w in self.algo_writes(fake)][:2], ["order-algo", "order-algo"])
        self.assertEqual(len(fake.posts), 4)

    def test_resume_keeps_the_stop_and_applies_the_new_ratio(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)

        def stop_later(now):
            if fake.algos and now > fake.bar_time(4) + 5_000:
                (self.root / "run" / "stop.request").write_text("", encoding="utf-8")

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=stop_later, disaster_stop=self.TEN))
        self.assertEqual((status["stop_reason"], status["position"]), ("operator_stop_file", "1"), status)
        self.assertEqual(self.algo_writes(fake), [("order-algo", {"side": "sell", "slTriggerPx": "94.5"})])
        # Restarted with 5%: the same OKX stop is checked, then moved to 99.75, rounded to the 0.1
        # tick toward triggering earlier (99.8); nothing is sent twice.
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 4), run="run2",
                                            disaster_stop=D("0.05")))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual([w[0] for w in self.algo_writes(fake)], ["order-algo", "amend-algos", "cancel-algos"])
        self.assertEqual(self.algo_writes(fake)[1][1], {"newSlTriggerPx": "99.8"})
        self.assertEqual(len(fake.algos), 1)

    # ---- independent acceptance 2026-11-17 (p6-cleanup), D1/D3 ----
    def test_an_unconfirmed_stop_never_blocks_the_kill_flatten(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake.lose_algo_create = True  # the stop request is lost: OKX never saw it, queries say "not found"
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 4), disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts], [("buy", False), ("sell", True)])
        self.assertEqual((fake.position, fake.algos), (0, {}))  # flattened; nothing was resent
        alerts = [e.get("alert") for e in self.events() if e["kind"] == "protection_alert"]
        self.assertIn("protection_unconfirmed", alerts)

    def test_a_reversal_under_an_unconfirmed_stop_only_closes(self):  # 2026-11-17, user "改"
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake.lose_algo_create = True  # the long's stop stays unconfirmed: increases are refused
        lines = []
        status = self.run_bot(self.make_bot(fake, clock, events=lines, on_sleep=self.kill_after(fake, 7),
                                            disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        # Bar 5 wants long 1 -> short 1: the long is closed, the short is not opened.
        self.assertEqual([(p["side"], p["sz"], p["reduceOnly"]) for p in fake.posts],
                         [("buy", "1", False), ("sell", "1", True)])
        self.assertEqual(fake.position, 0)
        self.assertTrue(any("只平掉原部位" in line for line in lines))

    def test_an_unconfirmed_stop_never_blocks_the_hard_flatten(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3, lose_after_fill=1)
        fake.lose_algo_create = True
        status = self.run_bot(self.make_bot(fake, clock, disaster_stop=self.TEN))
        self.assertIn("hard_loss", status["stop_reason"])
        self.assertEqual(fake.position, 0)
        records = kill_switch.read_records(Path(os.environ[kill_switch.ENV_PATH]))
        self.assertEqual((records[-1]["action"], records[-1]["actor"]), ("engage", "demo-bot"))

    def test_a_stop_changed_on_okx_is_put_back(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        changed = []

        def on_sleep(now):
            if fake.algos and not changed and now > fake.bar_time(4) + 10_000:
                next(iter(fake.algos.values()))["slTriggerPx"] = "80"  # someone moved it by hand
                changed.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep, run="run", disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:") or status["state"] == "stopped", status)
        writes = self.algo_writes(fake)
        self.assertIn(("amend-algos", {"newSlTriggerPx": "94.5"}), writes)

    def test_a_stop_that_fired_without_closing_says_a_position_is_left(self):  # recheck N1/N2
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fired = []

        def on_sleep(now):
            if fake.algos and not fired and now > fake.bar_time(4) + 20_000:
                next(iter(fake.algos.values()))["state"] = "order_failed"  # fired, but its order failed
                fired.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep, disaster_stop=self.TEN))
        self.assertEqual(status["stop_reason"], "disaster_stop_incomplete:okx=1", status)
        self.assertIn("手動平倉", demo_bot._hint(status["stop_reason"]))
        self.assertEqual(len(fake.posts), 1)

    def test_start_option_reads_percent(self):
        self.assertEqual(demo_bot._percent("10%"), D("0.10"))
        self.assertEqual(demo_bot._percent("0"), D("0"))
        for bad in ("50%", "-1", "ten"):
            with self.assertRaises(Exception):
                demo_bot._percent(bad)


class ReviewFixTests(unittest.TestCase):
    """Gemini second-opinion review of P6 and the reversal close-only rule (2026-11-18).

    The OKX behaviors here (auto-cancel at flat, 51603 for finished stops, refused amends,
    51402 on a cancel race, partial market fills) are not measured on Demo yet; they are
    modeled as the case that used to leave the run stuck or silent.
    """

    setUp = DemoBotTests.setUp
    make_bot = DemoBotTests.make_bot
    run_bot = DemoBotTests.run_bot
    events = DemoBotTests.events
    run_bot_quietly = DemoBotTests.run_bot_quietly
    kill_after = DemoBotTests.kill_after
    algo_writes = DisasterStopTests.algo_writes
    TEN = D("0.10")

    def alerts(self):
        return [e.get("alert") for e in self.events() if e["kind"] == "protection_alert"]

    def test_a_stop_okx_canceled_at_flat_is_settled_from_the_algo_history(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake.auto_cancel_on_flat = fake.finished_algos_vanish = True
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 6), disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        # The reversal's close made OKX cancel the long's stop, and order-algo no longer finds it:
        # the history says canceled, so the short still opens (it used to stay "unconfirmed" for good).
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts],
                         [("buy", False), ("sell", True), ("sell", False), ("buy", True)])
        self.assertEqual([w[0] for w in self.algo_writes(fake)], ["order-algo", "order-algo"])
        self.assertEqual([a["state"] for a in fake.algos.values()], ["canceled", "canceled"])
        self.assertNotIn("protection_unconfirmed", self.alerts())
        self.assertNotIn("protection_left", [e["kind"] for e in self.events()])

    def test_a_stop_fired_and_gone_from_order_algo_still_ends_the_run(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake.finished_algos_vanish = True
        fired = []

        def on_sleep(now):
            if fake.algos and not fired and now > fake.bar_time(4) + 20_000:
                fake.trigger_stop()
                fired.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep, disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("disaster_stop_triggered"), status)
        self.assertEqual(len(fake.posts), 1)

    def test_a_refused_amend_reports_the_refusal_once_and_keeps_the_old_stop(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)

        def stop_later(now):
            if fake.algos and now > fake.bar_time(4) + 5_000:
                (self.root / "run" / "stop.request").write_text("", encoding="utf-8")

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=stop_later, disaster_stop=self.TEN))
        self.assertEqual(status["position"], "1", status)
        fake.reject_amend = "51280"  # every move to the new 5% price is refused
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 5), run="run2",
                                            disaster_stop=D("0.05")))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        names = [w[0] for w in self.algo_writes(fake)]
        self.assertGreaterEqual(names.count("amend-algos"), 2)  # retried at later checks
        self.assertEqual(names[-1], "cancel-algos")             # the old stop is removed after the flatten
        # Before: "unconfirmed" and "mismatch" alternated at every check.
        self.assertEqual(self.alerts(), ["protection_request_failed"])
        self.assertEqual(fake.position, 0)

    def test_a_cancel_that_loses_the_race_is_settled_by_the_query(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake.cancel_race = True  # the reversal's cancel gets 51402: OKX had just canceled it
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 6), disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts],
                         [("buy", False), ("sell", True), ("sell", False), ("buy", True)])
        self.assertNotIn("protection_unconfirmed", self.alerts())

    def test_a_cancel_okx_lists_late_is_queried_again_before_the_history(self):  # acceptance D1
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake.lag_after_cancel = 1  # right after the cancel neither order-algo nor the history shows it
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 6), disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts],
                         [("buy", False), ("sell", True), ("sell", False), ("buy", True)])
        self.assertNotIn("protection_unconfirmed", self.alerts())

    def test_a_partly_filled_flatten_order_is_recorded_and_the_rest_closed(self):  # acceptance O1
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        engaged = []

        def on_sleep(now):
            if fake.position == 1 and not engaged and now > fake.bar_time(4) + 10_000:
                fake.partial_fill = "0.5"  # the Kill flatten's first order fills half
                kill_switch.engage(reason="end", actor="cli")
                engaged.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual((fake.position, status["fills"]), (0, 3), status)
        fills = json.loads((self.root / "run" / "fills.json").read_text(encoding="utf-8"))
        self.assertEqual([(f["leg"], f["state"]) for f in fills],
                         [("開倉／調整", "FILLED"), ("清倉（部分成交）", "CANCELED"), ("清倉", "FILLED")])

    def test_a_stop_gone_everywhere_is_reported_once_by_the_minute_check(self):  # Gemini recheck #3
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        gone = []

        def on_sleep(now):
            if fake.algos and not gone and now > fake.bar_time(4) + 20_000:
                fake.algos.clear()  # neither order-algo, the pending list nor the history knows it
                gone.append(now)
            if gone and now > fake.bar_time(4) + 200_000:
                (self.root / "run" / "stop.request").write_text("", encoding="utf-8")

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep, disaster_stop=self.TEN))
        self.assertEqual(status["stop_reason"], "operator_stop_file", status)
        self.assertEqual(self.alerts(), ["protection_unconfirmed"])  # logged once, not silently
        self.assertEqual(len(fake.posts), 1)  # nothing resent while it stays uncertain

    def test_a_partial_fill_is_recorded_and_protected_before_the_run_stops(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        fake.partial_fill = "0.5"  # the long fills 0.5 of 1; OKX cancels the rest
        lines = []
        status = self.run_bot(self.make_bot(fake, clock, events=lines, disaster_stop=self.TEN))
        self.assertEqual((status["stop_reason"], status["position"], status["fills"]),
                         ("order_partially_filled:canceled", "0.5", 1), status)
        fills = json.loads((self.root / "run" / "fills.json").read_text(encoding="utf-8"))
        self.assertEqual([(f["state"], f["fills"][0]["quantity"]) for f in fills], [("CANCELED", "0.5")])
        self.assertEqual(self.algo_writes(fake), [("order-algo", {"side": "sell", "slTriggerPx": "94.5"})])
        self.assertEqual([a["state"] for a in fake.algos.values()], ["live"])
        self.assertTrue(any("只成交一部分" in line and "保底停損在 94.5" in line for line in lines), lines)
        self.assertIn("接續", demo_bot._hint(status["stop_reason"]))
        # The restart resumes the 0.5 with its stop.
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 5), run="run2",
                                            disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertEqual(fake.position, 0)


class RareCaseTests(unittest.TestCase):
    """Six rare cases the 2026-11-18 review left open, fixed the same day (user: "修那 6 個少見情況")."""

    setUp = DemoBotTests.setUp
    make_bot = DemoBotTests.make_bot
    run_bot = DemoBotTests.run_bot
    events = DemoBotTests.events
    run_bot_quietly = DemoBotTests.run_bot_quietly
    kill_after = DemoBotTests.kill_after
    algo_writes = DisasterStopTests.algo_writes
    TEN = D("0.10")

    def alerts(self, run="run"):
        return [e.get("alert") for e in self.events(run) if e["kind"] == "protection_alert"]

    @staticmethod
    def both(first, second):
        def on_sleep(now):
            first(now)
            second(now)
        return on_sleep

    def lose_the_reversal_close(self, fake, clock):
        """Long from bar 3; bar 5's reversal close is accepted by OKX but its answer is lost: OKX is
        flat, the ledger keeps one unsettled close, and the run stops."""
        armed = []

        def on_sleep(now):
            if fake.position == 1 and not armed and now > fake.bar_time(4) + 10_000:
                fake.lose_post_response = True
                fake.hide_orders = 1
                armed.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=on_sleep))
        self.assertTrue(status["stop_reason"].startswith("order_not_settled:UNKNOWN"), status)
        self.assertEqual((fake.position, len(fake.posts)), (0, 2))
        fake.hide_orders = 0  # OKX answers again
        return status

    # 1. Flat on OKX, but the stopped run left an order of unknown outcome.
    def test_a_flat_restart_settles_the_stopped_runs_unknown_order(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.lose_the_reversal_close(fake, clock)
        lines = []
        status = self.run_bot(self.make_bot(fake, clock, events=lines, on_sleep=self.kill_after(fake, 6), run="run2"))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertFalse((self.root / "run2").exists())  # the stopped run is continued, not a new one
        self.assertTrue(any("有委託沒結清" in line for line in lines), lines)
        legs = [f["leg"] for f in json.loads((self.root / "run" / "fills.json").read_text(encoding="utf-8"))]
        self.assertEqual(legs[-1], "接續時補查")
        self.assertEqual(len(fake.posts), 2)  # nothing resent

    def test_new_run_leaves_the_unsettled_run_as_it_is(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.lose_the_reversal_close(fake, clock)
        before = (self.root / "run" / "manifest.json").read_text(encoding="utf-8")
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 6), run="run2", new_run=True))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertTrue((self.root / "run2").exists())
        self.assertEqual((self.root / "run" / "manifest.json").read_text(encoding="utf-8"), before)
        self.assertIn("--new-run", demo_bot._hint("resume_unresolved_orders"))

    def test_an_unsettled_run_that_cannot_continue_is_noted_in_the_new_run(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        self.lose_the_reversal_close(fake, clock)
        strategy_approvals.revoke(approval_id=self.record["record_id"], confirm=lambda text, word: True)
        sha = strategy_approvals.deployment_identity(PROFILE)[0]["sha256"]
        strategy_approvals.approve(strategy_id=PROFILE["strategy_id"], version=PROFILE["version"], sha256=sha,
                                   profile=PROFILE, confirm=lambda text, word: True)
        self.record = find_demo_approval(PROFILE)
        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 6), run="run2"))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        notes = [e for e in self.events("run2") if e["kind"] == "previous_run_unsettled"]
        self.assertEqual([(n["reason"], n["unsettled"]) for n in notes], [("resume_approval_changed", 1)])

    # 2. A risk change between decision and dispatch (new epoch) no longer voids a legal reduction.
    def test_a_soft_latch_before_the_reversal_still_closes_the_long(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        real = DemoBot._execute
        calls = []

        async def soft_first(bot, receipt, facts, now_ms):
            calls.append(receipt.intent_key)
            if len(calls) == 2:  # the reversal from bar 5: Soft latches right before its dispatch
                # As _observe would: the Supervisor's risk state latches, dispatch persists it first.
                bot.supervisor.risk_state = risk.halt(bot.supervisor.risk_state, {"soft_loss"})
            return await real(bot, receipt, facts, now_ms)

        lines = []
        with mock.patch.object(DemoBot, "_execute", soft_first):
            status = self.run_bot(self.make_bot(fake, clock, events=lines, on_sleep=self.kill_after(fake, 7)))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        # The close leg goes out under the new epoch; the opening leg is refused by Soft.
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts], [("buy", False), ("sell", True)])
        self.assertEqual(fake.position, 0)
        self.assertTrue(any("開倉腿被風控擋下" in line for line in lines), lines)

    # 3. A stop changed outside CatOS to a limit price or a partial size.
    def test_a_stop_changed_to_a_limit_price_blocks_increases(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        changed = []

        def on_sleep(now):
            if fake.algos and not changed and now > fake.bar_time(4) + 10_000:
                next(iter(fake.algos.values())).update(slOrdPx="94", closeFraction="")  # a limit price by hand
                changed.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.both(on_sleep, self.kill_after(fake, 7)), disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertIn("protection_altered", [e["kind"] for e in self.events()])
        # Bar 5 wants a short: the long is closed, the short is not opened while the stop is not whole.
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts], [("buy", False), ("sell", True)])
        self.assertEqual(fake.position, 0)

    def test_the_fill_size_okx_adds_after_firing_is_not_an_alteration(self):
        from catos.okx_demo import altered_stop
        self.assertFalse(altered_stop({"sl_ord_px": "-1", "close_fraction": "1", "sz": "1"}))
        self.assertFalse(altered_stop({"sl_ord_px": "", "close_fraction": "", "sz": ""}))
        self.assertTrue(altered_stop({"sl_ord_px": "94", "close_fraction": "1", "sz": ""}))
        self.assertTrue(altered_stop({"sl_ord_px": "-1", "close_fraction": "0.5", "sz": ""}))

    # 4. An amend that only changes the trigger source is confirmed by the source, not the price.
    def test_an_amend_of_the_source_alone_waits_until_okx_shows_it(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        changed = []

        def on_sleep(now):
            if fake.algos and not changed and now > fake.bar_time(4) + 10_000:
                next(iter(fake.algos.values()))["slTriggerPxType"] = "last"  # same price, other source
                fake.amend_source_lag = 1  # our amend back to mark shows one query late
                changed.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.both(on_sleep, self.kill_after(fake, 5)), disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        amends = [w for w in self.algo_writes(fake) if w[0] == "amend-algos"]
        self.assertEqual(amends, [("amend-algos", {"newSlTriggerPx": "94.5"})])  # once, then confirmed
        self.assertNotIn("protection_unconfirmed", self.alerts())

    # 5. An empty trigger source from OKX reads as its default (last) and is amended to mark.
    def test_an_empty_trigger_source_is_amended_not_a_crash(self):
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)
        changed = []

        def on_sleep(now):
            if fake.algos and not changed and now > fake.bar_time(4) + 10_000:
                next(iter(fake.algos.values()))["slTriggerPxType"] = ""
                changed.append(now)

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.both(on_sleep, self.kill_after(fake, 5)), disaster_stop=self.TEN))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        self.assertIn(("amend-algos", {"newSlTriggerPx": "94.5"}), self.algo_writes(fake))
        self.assertEqual([a["slTriggerPxType"] for a in fake.algos.values()], ["mark"])

    # 6. On resume, a new ratio that cannot be installed never lets the old ratio place or move a stop.
    def test_resume_never_uses_the_old_ratio_while_the_new_one_is_not_installed(self):
        from catos.supervisor import LocalSupervisor, SupervisorUnavailable
        clock = Clock(BASE + 1_000)
        fake = FakeOkx(clock, start_index=3)

        def stop_later(now):
            if fake.algos and now > fake.bar_time(4) + 5_000:
                (self.root / "run" / "stop.request").write_text("", encoding="utf-8")

        status = self.run_bot(self.make_bot(fake, clock, on_sleep=stop_later, disaster_stop=self.TEN))
        self.assertEqual(status["position"], "1", status)
        before = len(fake.algo_posts)

        async def refuse(supervisor, config):
            raise SupervisorUnavailable("synthetic")

        with mock.patch.object(LocalSupervisor, "configure_protection", refuse):
            status = self.run_bot(self.make_bot(fake, clock, on_sleep=self.kill_after(fake, 5), run="run2",
                                                disaster_stop=D("0.05")))
        self.assertTrue(status["stop_reason"].startswith("manual_kill:"), status)
        names = [w[0] for w in self.algo_writes(fake)[before:]]
        self.assertNotIn("order-algo", names)
        self.assertNotIn("amend-algos", names)
        self.assertIn("protection_wait", [e["kind"] for e in self.events()])
        self.assertEqual(fake.position, 0)


class AdapterTests(unittest.TestCase):
    def test_reports_translate_fills_and_fee_sign(self):
        clock = Clock(BASE + 1_000 + 4 * TF)
        fake = FakeOkx(clock, start_index=3)
        client = DemoClient(Credentials("k", "s", "p"), fake, clock_ms=clock, sleep=lambda s: None, monotonic=lambda: 0.0)
        adapter = OkxDemoExchange(client, "acct", "BTC-USDT-SWAP")
        payload = dict(instId="BTC-USDT-SWAP", tdMode="cross", posSide="net", ordType="market", side="buy",
                       sz="1", reduceOnly=False, clOrdId="abc123", tag=TAG)
        report = asyncio.run(adapter.submit(payload))
        self.assertEqual((report.status, report.complete, report.cumulative), ("FILLED", True, D("1")))
        self.assertEqual(report.fills[0].fee, D("0.0005") * D("0.01") * fake.mark())
        missing = asyncio.run(adapter.query("nope"))
        self.assertEqual(missing.status, "NOT_FOUND")

    def test_transport_failure_is_uncertain_not_rejected(self):
        class Down:
            def send(self, *a):
                raise ConnectionError("down")
        client = DemoClient(Credentials("k", "s", "p"), Down(), clock_ms=lambda: 0, sleep=lambda s: None, monotonic=lambda: 0.0)
        adapter = OkxDemoExchange(client, "acct", "BTC-USDT-SWAP")
        payload = dict(instId="BTC-USDT-SWAP", tdMode="cross", posSide="net", ordType="market", side="buy",
                       sz="1", reduceOnly=False, clOrdId="abc123", tag=TAG)
        with self.assertRaises(OSError):
            asyncio.run(adapter.submit(payload))
        with self.assertRaises(OSError):
            asyncio.run(adapter.query("abc123"))

    def test_payload_without_tag_never_leaves(self):
        fake = FakeOkx(Clock(BASE), start_index=3)
        client = DemoClient(Credentials("k", "s", "p"), fake, clock_ms=lambda: 0, sleep=lambda s: None, monotonic=lambda: 0.0)
        adapter = OkxDemoExchange(client, "acct", "BTC-USDT-SWAP")
        payload = dict(instId="BTC-USDT-SWAP", tdMode="cross", posSide="net", ordType="market", side="buy",
                       sz="1", reduceOnly=False, clOrdId="abc123", tag="other")
        with self.assertRaises(Exception):
            asyncio.run(adapter.submit(payload))
        self.assertEqual(fake.posts, [])


if __name__ == "__main__":
    unittest.main()
