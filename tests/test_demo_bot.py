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
            fee = -(size * D("0.01") * price * D("0.0005"))
            self.position += size if p["side"] == "buy" else -size
            self.equity += fee
            self.orders[p["clOrdId"]] = {"ordId": ord_id, "clOrdId": p["clOrdId"], "state": "filled", "sz": p["sz"],
                                         "accFillSz": p["sz"], "uTime": str(self.clock.ms), "tag": TAG}
            self.fills[ord_id] = [{"ordId": ord_id, "tradeId": "t" + ord_id, "fillSz": p["sz"],
                                   "fillPx": str(price), "fee": str(fee)}]
            if self.lose_after_fill is not None and len(self.orders) == self.lose_after_fill:
                self.equity -= self.loss  # an outside loss (600 = 12% of the day basis)
            return ok([{"ordId": ord_id, "clOrdId": p["clOrdId"], "sCode": "0"}])
        if method == "GET" and path == "/api/v5/trade/order":
            order = self.orders.get(q.get("clOrdId"))
            if order is None:
                return 200, json.dumps({"code": "51603", "msg": "Order does not exist", "data": []}).encode()
            return ok([order])
        if path == "/api/v5/trade/fills":
            return ok(self.fills.get(q["ordId"], []))
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

    def make_bot(self, fake, clock, events=None, on_sleep=None, limits=None, run="run"):
        """``run`` may be a nested path: another output root shares the same account files."""
        client = DemoClient(Credentials("k", "s", "p"), fake, clock_ms=clock, sleep=lambda s: None, monotonic=lambda: 0.0)
        lines = [] if events is None else events

        async def sleep(seconds):
            clock.ms += int(seconds * 1000) or 1
            if on_sleep is not None:
                on_sleep(clock.ms)

        return DemoBot(client=client, record=self.record, output_dir=self.root / run, echo=lines.append,
                       wall_ms=clock, sleep=sleep, limits=limits)

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
        # The reversal (an increase across zero) is refused under Soft; the run went on to the Kill.
        dispositions = [(e["disposition"], e["reason"]) for e in self.events() if e["kind"] == "bar"]
        self.assertIn(("REJECTED", "increase_gate_closed"), dispositions)
        self.assertEqual([(p["side"], p["reduceOnly"]) for p in fake.posts], [("buy", False), ("sell", True)])
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
        self.assertNotIn("u1", state_file.read_text(encoding="utf-8"))
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

    def test_old_approval_does_not_cover_demo(self):
        record = dict(self.record, created_at="2026-11-13T10:32:37+00:00")
        with mock.patch.object(strategy_approvals, "find_active", return_value=record):
            with self.assertRaises(strategy_approvals.ApprovalError):
                find_demo_approval(PROFILE)


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
