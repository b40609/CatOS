"""One approved strategy on the OKX Demo account, bar by bar (M1 steps 3 and 4, 2026-11-16).

Same path as the historical replay: Supervisor -> Worker -> risk -> execution, with the
OKX Demo adapter (catos/okx_demo_exchange.py) instead of FakeExchange. Per closed bar:

1. Stop requests, the Kill-Switch and the approval are checked first.
2. The account is observed on OKX: USDT equity, mark price, the position and open
   orders. The OKX position must equal the ledger's and there must be no open order on
   the contract (a foreign position/order is never adopted); otherwise the run stops.
3. The first observation of each Taipei day fixes the Soft/Hard basis (R1 semantics).
   External flows are not classified at the Demo stage (user decision 3, 2026-11-16).
4. The bar goes to the Worker; an accepted intent is sent through the Supervisor right
   away (a reversal as a reduce-only close, then the opening leg), and queried until the
   journal settles it.

Kill-Switch or Hard loss latches FLAT: the run then sends reduce-only market orders
through the Supervisor until the OKX position is zero, and stops (INVARIANTS: Hard
starts a market close and the Kill-Switch). Soft blocks increases and the run goes on.
Anything uncertain (UNKNOWN order, position mismatch, missing bars) stops the run with
the reason; nothing is resent blindly and nothing is adopted.

Not covered yet: resuming a stopped run (a new run refuses a non-zero position), and
the exchange-side disaster stop (P6, default 0%).
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

from catos import ipc, kill_switch, research, risk, strategy_approvals, strategy_registry
from catos.journal import Reconciliation
from catos.local_sim_r4 import atomic_json, durable_view
from catos.local_sim_replay import fill_config, worker_config
from catos.okx_demo import DemoClient, DemoError, account_issues, connect, credentials_path
from catos.okx_demo_exchange import OkxDemoExchange
from catos.research_catalog import ROOT
from catos.supervisor import LocalSupervisor

D = Decimal
BOT_ID = "demo-bot"
DEFAULT_OUTPUT = ROOT / "outputs" / "okx-demo-bot"
# Approvals written before the approval text said it covers OKX Demo do not count here.
APPROVALS_COVER_DEMO_SINCE = "2026-11-16T00:00:00+00:00"
BAR_GRACE_MS = 3_000
BAR_WAIT_MS = 90_000
SETTLE_TRIES = 30
FLATTEN_ROUNDS = 5


class BotStopped(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _now_text():
    return datetime.now(timezone.utc).isoformat()


def _wall_ms():
    return time.time_ns() // 1_000_000


class _Log:
    def __init__(self, directory, echo):
        self.handle = (directory / "events.jsonl").open("a", encoding="utf-8")
        self.echo = echo

    def event(self, kind, message=None, **values):
        row = dict(time=_now_text(), kind=kind, **values)
        self.handle.write(json.dumps(row, ensure_ascii=False, default=str, sort_keys=True) + "\n")
        self.handle.flush()
        if message and self.echo is not None:
            self.echo(f"{datetime.now().strftime('%m-%d %H:%M:%S')}  {message}")

    def close(self):
        self.handle.close()


def _contract(client, inst_id):
    spec = client.instrument(inst_id)
    if spec["state"] != "live":
        raise BotStopped(f"contract_not_live:{spec['state']}")
    return research.ContractSpec(inst_id, spec["ct_val"], spec["tick_sz"], spec["lot_sz"], spec["min_sz"])


def _candle(row):
    return research.Candle(row["open_time_ms"], row["open"], row["high"], row["low"], row["close"])


class DemoBot:
    def __init__(self, *, client: DemoClient, record: dict, output_dir: Path, limits: risk.Limits | None = None,
                 stop: asyncio.Event | None = None, echo=print, wall_ms=_wall_ms, sleep=asyncio.sleep,
                 kill_path=None):
        self.client = client
        self.record = record
        self.profile = record["profile"]
        self.inst_id = self.profile["inst_id"]
        self.tf = self.profile["timeframe_ms"]
        self.warmup = self.profile["warmup_bars"]
        self.output_dir = Path(output_dir)
        self.limits = risk.Limits() if limits is None else limits
        self.stop = stop
        self.echo = echo
        self.wall_ms = wall_ms
        self.sleep = sleep
        self.kill_path = kill_path
        self.supervisor = None
        self.status = dict(state="starting", bars=0, fills=0, last_bar_open_ms=None, stop_reason=None,
                           position=None, started_at=_now_text())
        self.fills = []

    # ---- observation and reconciliation ----
    def _account(self):
        """OKX facts at one moment; raises BotStopped on anything that would be adopted or guessed."""
        snapshot = self.client.account_snapshot()
        rows = self.client.positions(self.inst_id)
        if any(row["mgn_mode"] != "cross" for row in rows):
            raise BotStopped("foreign_isolated_position")
        position = sum((row["pos"] for row in rows), D("0"))
        pending = self.client.pending_orders(self.inst_id)
        mark = self.client.mark_price(self.inst_id)
        return dict(equity=snapshot["usdt_eq"], mgn_ratio=snapshot["mgn_ratio"], position=position,
                    pending=len(pending), mark=mark, avg_px=rows[0]["avg_px"] if rows else None)

    async def _owned_position(self):
        row = await self.supervisor._io(lambda: self.supervisor._journal.connection.execute(
            "SELECT position FROM ownership WHERE bot_id=?", (BOT_ID,)).fetchone())
        return D("0") if row is None or row[0] is None else D(row[0])

    async def _reconcile(self, facts, label):
        unresolved = await self.supervisor._io(self.supervisor._journal.execution.unresolved)
        if unresolved:
            raise BotStopped("unresolved_orders_before_reconcile")
        owned = await self._owned_position()
        if facts["pending"]:
            raise BotStopped(f"foreign_open_orders_on_contract:{facts['pending']}")
        if facts["position"] != owned:
            raise BotStopped(f"position_mismatch:okx={facts['position']}:ledger={owned}")
        position = facts["position"]
        await self.supervisor.reconcile(Reconciliation(
            self.supervisor.revision, f"okx-demo-{label}"[:64], position, 0, 0, 0, True,
            BOT_ID if position else None, ("okx-net-" + self.inst_id) if position else None))
        self.status["position"] = str(position)

    async def _observe(self, facts, now_ms):
        state = self.supervisor.risk_state
        day = risk.taipei_day(now_ms)
        if state.basis is None or state.basis.day != day:
            digest = hashlib.sha256(json.dumps(
                dict(inst=self.inst_id, time_ms=now_ms, equity=str(facts["equity"]), position=str(facts["position"]),
                     mark=str(facts["mark"])), sort_keys=True).encode()).hexdigest()
            basis = risk.make_demo_observed_basis(
                account_alias=self.supervisor.account_id, environment="local-sim", observed_at_ms=now_ms,
                equity=facts["equity"], observation_digest=digest, evidence_id=f"okx-demo-day-{day}")
            await self.supervisor.commit_day_basis(basis)
            self.log.event("day_basis", f"新的一天：風控基準權益 {facts['equity']} USDT", basis=basis.to_wire())
        # Margin: no position needs nothing; with one, OKX's maintenance ratio must be reported and above 300%.
        margin_ok = facts["position"] == 0 or (facts["mgn_ratio"] is not None and facts["mgn_ratio"] >= 3)
        state = self.supervisor.observe_risk(risk.Snapshot(
            self.supervisor.risk_state.seq + 1, now_ms, now_ms + self.tf, facts["equity"], facts["equity"],
            facts["position"], facts["mark"], basis=self.supervisor.risk_state.basis,
            valuation_known=True, flows_known=True, margin_ok=margin_ok, position_verified=True))
        await self.supervisor.persist_controls()
        if state.reasons:
            self.log.event("risk", None, reasons=sorted(state.reasons), mode=state.mode)
        return state

    async def _view(self, facts, now_ms):
        view = await durable_view(self.supervisor, self.fill_config, now_ms, facts["mark"])
        if view.position != facts["position"]:
            raise BotStopped("ledger_projection_mismatch")
        return replace(view, equity=facts["equity"], time_ms=now_ms)

    async def _settle(self, row):
        """Query until the journal settles the order; an order that stays uncertain stops the run."""
        for _ in range(SETTLE_TRIES):
            if row is None:
                raise BotStopped("order_row_missing")
            if row["settled"]:
                return row
            await self.sleep(1)
            row = await self.supervisor.query_order(row["order_key"])
        raise BotStopped(f"order_not_settled:{row['state']}:{row['cl_ord_id']}")

    async def _record_fill(self, row, leg):
        fills = await self.supervisor._io(lambda: [dict(r) for r in self.supervisor._journal.connection.execute(
            "SELECT trade_id,quantity,price,fee FROM execution_fills WHERE order_key=? ORDER BY rowid",
            (row["order_key"],))])
        side = "買" if D(row["quantity"]) > 0 else "賣"
        qty = sum((D(f["quantity"]) for f in fills), D("0"))
        price = fills[0]["price"] if len(fills) == 1 else "多筆"
        self.status["fills"] += 1
        self.fills.append(dict(leg=leg, order_key=row["order_key"], cl_ord_id=row["cl_ord_id"],
                               exchange_id=row["exchange_id"], state=row["state"], fills=fills))
        self.log.event("fill", f"成交（{leg}）：{side} {qty} 張 @ {price}，ordId={row['exchange_id']}",
                       leg=leg, row={k: row[k] for k in ("order_key", "cl_ord_id", "exchange_id", "state", "quantity", "filled")},
                       fills=fills)

    async def _execute(self, receipt, facts, now_ms):
        intent_key = receipt.intent_key
        while True:
            row = await self.supervisor.dispatch(intent_key, now_ms=now_ms)
            if row is None:
                raise BotStopped("dispatch_returned_nothing")
            closing_leg = row["order_key"] != intent_key
            row = await self._settle(row)
            if row["state"] != "FILLED":
                self.log.event("order", f"委託未成交：{row['state']}", row={k: row[k] for k in ("cl_ord_id", "state")})
                raise BotStopped(f"order_{row['state'].lower()}")
            await self._record_fill(row, "反手平倉" if closing_leg else "開倉／調整")
            facts = await asyncio.to_thread(self._account)
            await self._reconcile(facts, f"fill-{row['cl_ord_id']}")
            if not closing_leg:
                return facts
            now_ms = self.wall_ms()
            await self._observe(facts, now_ms)

    async def _flatten(self, reason):
        """FLAT latched (Kill-Switch or Hard): reduce-only market orders until OKX shows zero."""
        self.log.event("flatten", f"清倉開始（{reason}）")
        for attempt in range(FLATTEN_ROUNDS):
            facts = await asyncio.to_thread(self._account)
            if facts["position"] == 0 and not await self.supervisor._io(self.supervisor._journal.execution.unresolved):
                await self._reconcile(facts, f"flat-{attempt}")
                self.log.event("flatten_done", "清倉完成：模擬盤部位 0")
                return
            now_ms = self.wall_ms()
            await self._reconcile(facts, f"flatten-{attempt}")
            await self._observe(facts, now_ms)
            row = await self.supervisor.flatten_step(now_ms=now_ms, expires_at_ms=now_ms + 60_000)
            if row is not None:
                row = await self._settle(row)
                if row["state"] == "FILLED":
                    await self._record_fill(row, "清倉")
        facts = await asyncio.to_thread(self._account)
        raise BotStopped(f"flatten_incomplete:okx_position={facts['position']}")

    async def _kill_check(self):
        fired = self.watch.check()
        if fired is None:
            return
        self.log.event("kill_switch", f"Kill-Switch 已觸發（{fired}）", evidence=fired)
        await self.supervisor.manual_kill(actor=self.watch.actor, evidence_id=fired)
        await self._flatten("Kill-Switch")
        raise BotStopped("manual_kill:" + fired)

    async def _wait_for_bar(self, open_ms):
        """Wait for the bar opening at ``open_ms`` to close; checks stop/kill every second."""
        close_ms = open_ms + self.tf
        while self.wall_ms() < close_ms + BAR_GRACE_MS:
            if self.stop is not None and self.stop.is_set():
                raise BotStopped("operator_stop")
            if (self.output_dir / "stop.request").exists():
                raise BotStopped("operator_stop_file")
            await self._kill_check()
            await self.sleep(min(1.0, max(0.05, (close_ms + BAR_GRACE_MS - self.wall_ms()) / 1000)))
        deadline = self.wall_ms() + BAR_WAIT_MS
        while True:
            bars = await asyncio.to_thread(self.client.closed_candles, self.inst_id, self.tf, 5)
            newer = [b for b in bars if b["open_time_ms"] >= open_ms]
            if newer and newer[0]["open_time_ms"] != open_ms:
                raise BotStopped(f"bar_gap:expected={open_ms}:got={newer[0]['open_time_ms']}")
            if newer:
                return newer
            if self.wall_ms() >= deadline:
                raise BotStopped(f"bar_not_published:{open_ms}")
            await self.sleep(2)

    # ---- run ----
    async def run(self):
        profile = self.profile
        self.watch = kill_switch.Watch(self.kill_path)  # engaged or unreadable: refuse before anything else
        config = await asyncio.to_thread(self.client.account_config)
        issues = account_issues(config)
        if issues:
            raise BotStopped("account_not_tradeable:" + "；".join(issues))
        contract = await asyncio.to_thread(_contract, self.client, self.inst_id)
        self.fill_config = fill_config(profile, contract)
        self.worker = worker_config(self.record, contract)  # resolves through the approval (fail closed)
        facts = await asyncio.to_thread(self._account)
        if facts["position"] != 0 or facts["pending"]:
            raise BotStopped(f"contract_not_flat_at_start:position={facts['position']}:orders={facts['pending']}")
        self.output_dir.mkdir(parents=True, exist_ok=False)
        self.log = _Log(self.output_dir, self.echo)
        account_id = "okxdemo-" + uuid.uuid4().hex[:24]
        manifest = dict(run_id=self.output_dir.name, created_at=_now_text(), mode="okx-demo-bot",
                        exchange="OKX Demo (x-simulated-trading: 1)", approval_id=self.record["record_id"],
                        approval_record=self.record, profile=profile, worker_config=self.worker.to_wire(),
                        contract=dict(inst_id=contract.inst_id, base_per_contract=str(contract.base_per_contract),
                                      tick_size=str(contract.tick_size), lot_size=str(contract.lot_size),
                                      min_size=str(contract.min_size)),
                        risk_limits=self.limits.to_wire(), account_id=account_id, bot_id=BOT_ID,
                        starting_equity=str(facts["equity"]), database="state.sqlite3",
                        ledger_environment_label="local-sim",
                        notice=("帳本沿用 local-sim 的結構與標籤（不改資料庫結構）；實際交易所是 OKX 模擬盤。"
                                "外部資金流在模擬盤階段不分類（2026-11-16 使用者決定）。"))
        atomic_json(self.output_dir / "manifest.json", manifest)
        exchange = OkxDemoExchange(self.client, account_id, self.inst_id)
        self.supervisor = LocalSupervisor(self.output_dir / "state.sqlite3", account_id=account_id, bot_id=BOT_ID,
                                          config=self.worker, fixture_budget=facts["equity"], risk_limits=self.limits,
                                          exchange=exchange, day_clock=self, require_new_database=True)
        try:
            await self.supervisor.start()
            await self._reconcile(facts, "start")
            history = await asyncio.to_thread(self.client.closed_candles, self.inst_id, self.tf, self.warmup)
            if len(history) != self.warmup or any(b["open_time_ms"] - a["open_time_ms"] != self.tf
                                                  for a, b in zip(history, history[1:])):
                raise BotStopped("warmup_history_incomplete")
            seq = 0
            for row in history:
                seq += 1
                bar = _candle(row)
                receipt = await self.supervisor.process_bar(seq, bar, None, now_ms=bar.open_time_ms + self.tf,
                                                            expires_at_ms=bar.open_time_ms + 2 * self.tf)
                if receipt.target_position is not None:
                    raise BotStopped("warmup_produced_intent")
            last_open = history[-1]["open_time_ms"]
            self.status.update(state="running", bars=seq, last_bar_open_ms=last_open)
            self._write_status()
            self.log.event("started", f"Bot 啟動：{profile['strategy_id']} {profile['parameters']}，"
                           f"{self.inst_id} {self.tf // 60000} 分鐘，{profile['quantity']} 張；"
                           f"預熱 {seq} 根完成，權益 {facts['equity']} USDT", manifest=manifest)
            while True:
                bars = await self._wait_for_bar(last_open + self.tf)
                for row in bars:
                    seq += 1
                    await self._bar(seq, _candle(row), is_latest=row is bars[-1])
                    last_open = row["open_time_ms"]
                    self.status.update(bars=seq, last_bar_open_ms=last_open)
                    self._write_status()
        except BotStopped as exc:
            self.status.update(state="stopped", stop_reason=exc.reason)
        except Exception as exc:  # recorded; nothing is resent or flattened outside the Supervisor
            self.status.update(state="failed", stop_reason=f"{type(exc).__name__}: {str(exc)[:300]}")
        finally:
            await self._close()
        return self.status

    async def _bar(self, seq, bar, *, is_latest):
        await self._kill_check()
        try:
            strategy_registry.resolve_deployment(self.worker)
        except strategy_registry.RegistryError as exc:
            raise BotStopped(f"approval_or_source_invalid:{exc}") from None
        if self.supervisor.failure:
            raise BotStopped("supervisor_failed:" + str(self.supervisor.failure))
        facts = await asyncio.to_thread(self._account)
        await self._reconcile(facts, f"bar-{seq}")
        now_ms = self.wall_ms()
        state = await self._observe(facts, now_ms)
        if state.mode == "FLAT":
            await self._flatten(",".join(sorted(state.reasons)))
            raise BotStopped("risk_flat:" + ",".join(sorted(state.reasons)))
        # The Worker contract: the account view is stamped with this bar's close time.
        view = await self._view(facts, bar.open_time_ms + self.tf)
        # A bar caught up after a delay is processed for the strategy state, but its intent
        # expires: only the latest closed bar may trade.
        expires = now_ms + 60_000 if is_latest else now_ms
        receipt = await self.supervisor.process_bar(seq, bar, view, now_ms=now_ms, expires_at_ms=expires)
        self.log.event("bar", f"K 線 {datetime.fromtimestamp((bar.open_time_ms + self.tf) / 1000).strftime('%H:%M')} 收 {bar.close}"
                       f"｜部位 {facts['position']}｜權益 {facts['equity']}｜決策 {receipt.disposition}"
                       + (f"（{receipt.reason}）" if receipt.disposition not in ("NO_INTENT", "NO_CHANGE") else ""),
                       seq=seq, bar=ipc.bar_to_wire(bar), equity=str(facts["equity"]), mark=str(facts["mark"]),
                       position=str(facts["position"]), disposition=receipt.disposition, reason=receipt.reason,
                       target=None if receipt.target_position is None else str(receipt.target_position),
                       risk_reasons=sorted(state.reasons))
        if receipt.disposition == "RESERVED_SIMULATION":
            await self._execute(receipt, facts, now_ms)
        elif receipt.disposition not in ("NO_INTENT", "NO_CHANGE", "REJECTED", "EXPIRED"):
            raise BotStopped(f"unexpected_disposition:{receipt.disposition}")

    def _write_status(self):
        atomic_json(self.output_dir / "status.json", dict(self.status, updated_at=_now_text()))

    async def _close(self):
        if self.supervisor is not None:
            try:
                self.status["position"] = str(await self._owned_position()) if self.supervisor._journal else None
            except Exception:
                pass
            await self.supervisor.close()
        self.status["finished_at"] = _now_text()
        if self.output_dir.exists():
            self._write_status()
            atomic_json(self.output_dir / "fills.json", self.fills)
        if getattr(self, "log", None) is not None:
            self.log.event("stopped", f"Bot 停止：{self.status['state']}（{self.status['stop_reason']}）"
                           f"；最後部位 {self.status['position']}", status=self.status)
            self.log.close()


def find_demo_approval(profile):
    record = strategy_approvals.find_active(profile)
    if record["created_at"] < APPROVALS_COVER_DEMO_SINCE:
        raise strategy_approvals.ApprovalError("approval_predates_demo_coverage")
    return record


def cli_main(argv):
    parser = argparse.ArgumentParser(prog="catos.cli demo bot", description="核准過的策略在 OKX 模擬盤上跑（前景執行，Ctrl+C 停止）")
    parser.add_argument("--profile", required=True, help="部署設定 JSON（要先由使用者核准）")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    try:
        profile = strategy_approvals.load_profile(args.profile)
        record = find_demo_approval(profile)
        client, note = connect()
    except strategy_approvals.ApprovalError as exc:
        hint = {"no_active_approval_for_profile": "這份部署設定還沒核准",
                "approval_predates_demo_coverage": "這筆核准是 11/16 之前的版本（只涵蓋本機重播），請重新核准"}.get(str(exc), "")
        sys.stderr.write(f"錯誤：{exc} {hint}\n")
        return 1
    except DemoError as exc:
        sys.stderr.write(f"錯誤：{exc}\n")
        return 1
    print(f"金鑰：{credentials_path()}，{note}")
    directory = Path(args.output_root) / uuid.uuid4().hex
    print(f"紀錄資料夾：{directory}")
    print("停止：按 Ctrl+C，或在紀錄資料夾建立 stop.request；緊急停止用 Kill-Switch（會平倉）。\n")
    bot = DemoBot(client=client, record=record, output_dir=directory)
    try:
        status = asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n已收到 Ctrl+C；部位留在模擬盤上，沒有平倉。")
        return 1
    print(f"\n結束：{status['state']}（{status['stop_reason']}），最後部位 {status['position']}")
    return 0 if status["state"] == "stopped" else 1
