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

Across runs (independent acceptance 2026-11-17, D2/D4): one Bot per OKX account (a file
lock keyed by the account uid), and the account's Taipei-day basis and Soft latch live in
an account file next to the runs, so a restart on the same day reuses the basis and a
Soft latch stays until the user runs ``demo rearm``. A Hard loss also engages the shared
Kill-Switch record (actor ``demo-bot``), which only the user can clear.

Reads from OKX are retried with backoff before the run stops; while flattening they are
retried for about two minutes. Between bars, with a position open, the account is
observed every minute so Hard/Soft and foreign changes do not wait for the bar close.

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
from catos.kill_switch import KillSwitchError, terminal_confirm
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
READ_TRIES = 4            # about 14 s of backoff before an ordinary read stops the run
FLATTEN_READ_TRIES = 12   # about two minutes while flattening
INTRABAR_CHECK_MS = 60_000
AUTHORIZED_INSTRUMENTS = frozenset({"BTC-USDT-SWAP"})  # M1 agent decision: one contract only
ACCOUNT_SCHEMA = "catos.okx-demo-account"
ACCOUNTS_DIRECTORY = None  # Resolved lazily (~/.catos/okx-demo-accounts); tests replace only this constant.


def accounts_directory():
    """Fixed per user, not per output root: a different --output-root must not reset the basis or the latch."""
    return ACCOUNTS_DIRECTORY if ACCOUNTS_DIRECTORY is not None else Path.home() / ".catos" / "okx-demo-accounts"
REARM_WORD = "解除"


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


class AccountGuard:
    """One Bot per OKX Demo account, and the account's day basis and Soft latch across runs.

    Files in ``accounts_directory()``: ``<digest>.lock`` is held for the whole run;
    ``<digest>.json`` holds the current Taipei day's basis and the Soft latch. The digest
    is of the OKX uid; the uid itself is not written. The lock file is never removed, so a
    state file that is missing next to it was lost, not new: the run refuses (R1: a basis
    that existed is never rebuilt as a first observation). Starting over is the user's
    decision: delete both files.
    """

    def __init__(self, directory, uid):
        if not uid:
            raise BotStopped("account_uid_missing")
        self.uid_sha256 = hashlib.sha256(("okx-demo:" + uid).encode("utf-8")).hexdigest()
        self.directory = Path(directory)
        self.state_path = self.directory / f"{self.uid_sha256[:32]}.json"
        self.lock_path = self.directory / f"{self.uid_sha256[:32]}.lock"
        self._handle = None

    def acquire(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        fresh = not self.lock_path.exists()
        handle = self.lock_path.open("a+b")
        try:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise BotStopped("account_busy:another_demo_bot_runs_on_this_okx_account") from None
        self._handle = handle
        if not self.state_path.exists():
            if not fresh:
                self.release()
                raise BotStopped(f"account_state_missing:{self.state_path.name}")
            try:
                self.save(dict(day=None, basis=None, soft_latched=False, soft_reason=None, rearms=[]))
            except BaseException:
                # Nothing was ever recorded for this account: undo the lock file so it is still new.
                self.release()
                try:
                    self.lock_path.unlink()
                except OSError:
                    pass
                raise

    def release(self):
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def load(self):
        """Call with the lock held (acquire creates the file for a new account)."""
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            ok = (type(state) is dict and state.get("schema") == ACCOUNT_SCHEMA
                  and state.get("uid_sha256") == self.uid_sha256 and type(state.get("soft_latched")) is bool)
            if ok and state.get("day") is None:
                ok = state.get("basis") is None
            elif ok:
                ok = (type(state.get("day")) is int and type(state.get("basis")) is dict
                      and type(state["basis"].get("observed_at_ms")) is int
                      and D(state["basis"]["equity"]) > 0 and type(state["basis"].get("digest")) is str)
        except (OSError, ValueError, ArithmeticError, KeyError, TypeError):
            ok = False
        if not ok:
            # A basis that existed and is now unreadable is never rebuilt as a first observation (R1).
            raise BotStopped(f"account_state_unreadable:{self.state_path.name}")
        return state

    @classmethod
    def for_file(cls, path):
        """The guard of an existing account file (``demo rearm``); the uid is not needed."""
        guard = cls.__new__(cls)
        path = Path(path)
        guard.directory = path.parent
        guard.state_path = path
        guard.lock_path = path.with_suffix(".lock")
        guard._handle = None
        try:
            guard.uid_sha256 = json.loads(path.read_text(encoding="utf-8"))["uid_sha256"]
        except (OSError, ValueError, KeyError, TypeError):
            raise BotStopped(f"account_state_unreadable:{path.name}") from None
        if type(guard.uid_sha256) is not str or guard.uid_sha256[:32] != path.stem:
            raise BotStopped(f"account_state_unreadable:{path.name}")
        return guard

    def save(self, state):
        atomic_json(self.state_path, dict(state, schema=ACCOUNT_SCHEMA, uid_sha256=self.uid_sha256,
                                          updated_at=_now_text()))


class DemoBot:
    def __init__(self, *, client: DemoClient, record: dict, output_dir: Path, limits: risk.Limits | None = None,
                 stop: asyncio.Event | None = None, echo=print, wall_ms=_wall_ms, sleep=asyncio.sleep,
                 kill_path=None, accounts_dir=None):
        self.client = client
        self.accounts_dir = accounts_directory() if accounts_dir is None else Path(accounts_dir)
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
        if self.inst_id not in AUTHORIZED_INSTRUMENTS:
            raise BotStopped(f"instrument_not_authorized:{self.inst_id}")
        self.supervisor = None
        self.guard = None
        self.account_state = None
        self.hard_engaged = False
        self.log = None
        self.status = dict(state="starting", bars=0, fills=0, last_bar_open_ms=None, stop_reason=None,
                           position=None, started_at=_now_text())
        self.fills = []

    # ---- observation and reconciliation ----
    def _account(self):
        """OKX facts at one moment; raises BotStopped on anything that would be adopted or guessed."""
        snapshot = self.client.account_snapshot()
        every = self.client.positions()  # the whole account: other contracts count as foreign
        rows = [row for row in every if row["inst_id"] == self.inst_id]
        if any(row["mgn_mode"] != "cross" for row in rows):
            raise BotStopped("foreign_isolated_position")
        position = sum((row["pos"] for row in rows), D("0"))
        orders = self.client.pending_orders()
        pending = [row for row in orders if row["inst_id"] == self.inst_id]
        others = sorted({row["inst_id"] for row in every + orders if row["inst_id"] != self.inst_id})
        mark = self.client.mark_price(self.inst_id)
        return dict(equity=snapshot["usdt_eq"], mgn_ratio=snapshot["mgn_ratio"], position=position,
                    pending=len(pending), others=others, mark=mark, avg_px=rows[0]["avg_px"] if rows else None)

    async def _call(self, fn, *args, tries=READ_TRIES):
        """An OKX read, retried with backoff; still failing, the run stops with the reason."""
        delay = 2
        for attempt in range(tries):
            try:
                return await asyncio.to_thread(fn, *args)
            except DemoError as exc:
                code = getattr(exc, "code", None) or type(exc).__name__
                if attempt == tries - 1:
                    raise BotStopped(f"okx_read_failed:{code}") from None
                if self.log is not None:
                    self.log.event("read_retry", f"讀 OKX 失敗（{code}），{delay} 秒後重試", attempt=attempt + 1, code=code)
                await self.sleep(delay)
                delay = min(delay * 2, 15)

    async def _owned_position(self):
        row = await self.supervisor._io(lambda: self.supervisor._journal.connection.execute(
            "SELECT position FROM ownership WHERE bot_id=?", (BOT_ID,)).fetchone())
        return D("0") if row is None or row[0] is None else D(row[0])

    async def _reconcile(self, facts, label, *, flattening=False):
        if facts["others"] and not flattening:
            raise BotStopped("foreign_positions_or_orders_in_account:" + ",".join(facts["others"]))
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
            stored = self.account_state
            if stored is not None and stored["day"] == day:
                # Same Taipei day as an earlier run on this account: the basis is not replaced (R1).
                observed = stored["basis"]["observed_at_ms"]
                equity, digest = D(stored["basis"]["equity"]), stored["basis"]["digest"]
                message = f"沿用今天稍早的風控基準權益 {equity} USDT"
            else:
                observed, equity = now_ms, facts["equity"]
                digest = hashlib.sha256(json.dumps(
                    dict(inst=self.inst_id, time_ms=now_ms, equity=str(equity), position=str(facts["position"]),
                         mark=str(facts["mark"])), sort_keys=True).encode()).hexdigest()
                self.account_state = dict(stored or dict(soft_latched=False, soft_reason=None, rearms=[]),
                                          day=day, basis=dict(observed_at_ms=observed, equity=str(equity), digest=digest))
                self.guard.save(self.account_state)  # durable before it is used
                message = f"新的一天：風控基準權益 {equity} USDT"
            basis = risk.make_demo_observed_basis(
                account_alias=self.supervisor.account_id, environment="local-sim", observed_at_ms=observed,
                equity=equity, observation_digest=digest, evidence_id=f"okx-demo-day-{day}")
            await self.supervisor.commit_day_basis(basis)
            self.log.event("day_basis", message, basis=basis.to_wire())
        # Margin: no position needs nothing; with one, OKX's maintenance ratio must be reported and above 300%.
        margin_ok = facts["position"] == 0 or (facts["mgn_ratio"] is not None and facts["mgn_ratio"] >= 3)
        state = self.supervisor.observe_risk(risk.Snapshot(
            self.supervisor.risk_state.seq + 1, now_ms, now_ms + self.tf, facts["equity"], facts["equity"],
            facts["position"], facts["mark"], basis=self.supervisor.risk_state.basis,
            valuation_known=True, flows_known=True, margin_ok=margin_ok, position_verified=True))
        await self.supervisor.persist_controls()
        if state.reasons:
            self.log.event("risk", None, reasons=sorted(state.reasons), mode=state.mode)
        if "soft_loss" in state.reasons and not self.account_state["soft_latched"]:
            self.account_state = dict(self.account_state, soft_latched=True,
                                      soft_reason=f"soft_loss {_now_text()} equity={facts['equity']}")
            self.guard.save(self.account_state)
            self.log.event("soft_latched", "Soft 日損鎖住：停止加倉（重啟也一樣，要你執行 demo rearm 才解除）")
        if "hard_loss" in state.reasons and not self.hard_engaged:
            self.hard_engaged = True
            try:
                record, _ = await asyncio.to_thread(
                    kill_switch.engage, reason=f"模擬盤 Bot Hard 日損（權益 {facts['equity']} USDT）",
                    actor="demo-bot", path=self.kill_path)
                self.log.event("hard_kill_switch", "Hard 日損：已觸發 Kill-Switch，只有你能解除",
                               record_id=record["record_id"])
            except (KillSwitchError, OSError) as exc:  # the flatten below still runs
                self.log.event("hard_kill_switch_failed", f"Hard 日損：寫入 Kill-Switch 失敗（{exc}）")
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
        closed_first = False
        while True:
            row = await self.supervisor.dispatch(intent_key, now_ms=now_ms)
            if row is None and closed_first:
                # The opening leg of a reversal was re-evaluated from flat and refused (e.g. Soft).
                self.log.event("order", "反手的開倉腿被風控擋下，維持空倉繼續跑")
                return facts
            if row is None:
                raise BotStopped("dispatch_returned_nothing")
            closing_leg = row["order_key"] != intent_key
            row = await self._settle(row)
            if row["state"] != "FILLED":
                self.log.event("order", f"委託未成交：{row['state']}", row={k: row[k] for k in ("cl_ord_id", "state")})
                raise BotStopped(f"order_{row['state'].lower()}")
            await self._record_fill(row, "反手平倉" if closing_leg else "開倉／調整")
            facts = await self._call(self._account)
            await self._reconcile(facts, f"fill-{row['cl_ord_id']}")
            if not closing_leg:
                return facts
            closed_first = True
            now_ms = self.wall_ms()
            state = await self._observe(facts, now_ms)
            if state.mode == "FLAT":
                return facts  # the next bar (or minute check) flattens and stops

    async def _flatten(self, reason):
        """FLAT latched (Kill-Switch or Hard): reduce-only market orders until OKX shows zero."""
        self.log.event("flatten", f"清倉開始（{reason}）")
        try:
            await self._flatten_rounds()
        except BotStopped as exc:
            self.log.event("flatten_failed", f"清倉沒有完成（{exc.reason}）：部位可能還在 OKX 上，"
                           "請到 OKX 網頁確認並手動平倉；Kill-Switch 維持觸發")
            raise BotStopped(f"flatten_failed:{exc.reason}") from None

    async def _flatten_rounds(self):
        for attempt in range(FLATTEN_ROUNDS):
            facts = await self._call(self._account, tries=FLATTEN_READ_TRIES)
            if facts["position"] == 0 and not await self.supervisor._io(self.supervisor._journal.execution.unresolved):
                await self._reconcile(facts, f"flat-{attempt}", flattening=True)
                self.log.event("flatten_done", "清倉完成：模擬盤部位 0")
                return
            now_ms = self.wall_ms()
            await self._reconcile(facts, f"flatten-{attempt}", flattening=True)
            await self._observe(facts, now_ms)
            row = await self.supervisor.flatten_step(now_ms=now_ms, expires_at_ms=now_ms + 60_000)
            if row is not None:
                row = await self._settle(row)
                if row["state"] == "FILLED":
                    await self._record_fill(row, "清倉")
        facts = await self._call(self._account, tries=FLATTEN_READ_TRIES)
        raise BotStopped(f"flatten_incomplete:okx_position={facts['position']}")

    async def _kill_check(self):
        fired = self.watch.check()
        if fired is None:
            return
        self.log.event("kill_switch", f"Kill-Switch 已觸發（{fired}）", evidence=fired)
        await self.supervisor.manual_kill(actor=self.watch.actor, evidence_id=fired)
        await self._flatten("Kill-Switch")
        raise BotStopped("manual_kill:" + fired)

    async def _stop_checks(self):
        if self.stop is not None and self.stop.is_set():
            raise BotStopped("operator_stop")
        if (self.output_dir / "stop.request").exists():
            raise BotStopped("operator_stop_file")
        await self._kill_check()

    async def _intrabar_check(self):
        """With a position open, observe the account between bars (Hard/Soft, foreign changes)."""
        owned = await self._owned_position()
        if owned == 0:
            return
        facts = await self._call(self._account)
        if facts["others"]:
            raise BotStopped("foreign_positions_or_orders_in_account:" + ",".join(facts["others"]))
        if facts["pending"]:
            raise BotStopped(f"foreign_open_orders_on_contract:{facts['pending']}")
        if facts["position"] != owned:
            raise BotStopped(f"position_mismatch:okx={facts['position']}:ledger={owned}")
        state = await self._observe(facts, self.wall_ms())
        if state.mode == "FLAT":
            await self._flatten(",".join(sorted(state.reasons)))
            raise BotStopped("risk_flat:" + ",".join(sorted(state.reasons)))

    async def _wait_for_bar(self, open_ms):
        """Wait for the bar opening at ``open_ms`` to close; checks stop/kill every second."""
        close_ms = open_ms + self.tf
        next_check = self.wall_ms() + INTRABAR_CHECK_MS
        while self.wall_ms() < close_ms + BAR_GRACE_MS:
            await self._stop_checks()
            if self.wall_ms() >= next_check:
                await self._intrabar_check()
                next_check = self.wall_ms() + INTRABAR_CHECK_MS
            await self.sleep(min(1.0, max(0.05, (close_ms + BAR_GRACE_MS - self.wall_ms()) / 1000)))
        deadline = self.wall_ms() + BAR_WAIT_MS
        while True:
            await self._stop_checks()
            bars = await self._call(self.client.closed_candles, self.inst_id, self.tf, 5)
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
        guard = AccountGuard(self.accounts_dir, config.get("uid", ""))
        guard.acquire()
        try:
            self.account_state = guard.load()
            facts = await asyncio.to_thread(self._account)
            if facts["position"] != 0 or facts["pending"]:
                raise BotStopped(f"contract_not_flat_at_start:position={facts['position']}:orders={facts['pending']}")
            if facts["others"]:
                raise BotStopped("foreign_positions_or_orders_in_account:" + ",".join(facts["others"]))
            self.output_dir.mkdir(parents=True, exist_ok=False)
        except BaseException:
            guard.release()
            raise
        self.guard = guard
        try:
            self._open_run(facts, contract)
        except BaseException:
            guard.release()
            self.guard = None
            if self.log is not None:
                self.log.close()
                self.log = None
            raise
        try:
            await self.supervisor.start()
            if self.account_state["soft_latched"]:
                self.supervisor.latch("soft_loss")
                await self.supervisor.persist_controls()
                self.log.event("soft_latched", "Soft 日損仍鎖住（之前的 run 觸發）：只能減倉，要你執行 demo rearm 才解除")
            await self._main_loop(facts)
        except BotStopped as exc:
            self.status.update(state="stopped", stop_reason=exc.reason)
        except Exception as exc:  # recorded; nothing is resent or flattened outside the Supervisor
            self.status.update(state="failed", stop_reason=f"{type(exc).__name__}: {str(exc)[:300]}")
        except BaseException:  # Ctrl+C / cancellation: the position is kept, nothing is flattened
            self.status.update(state="stopped", stop_reason="interrupted")
            raise
        finally:
            await self._close()
        return self.status

    def _open_run(self, facts, contract):
        """Run folder, log, manifest and Supervisor (not started yet)."""
        profile = self.profile
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
        self.manifest = manifest

    async def _main_loop(self, facts):
        profile = self.profile
        await self._reconcile(facts, "start")
        history = await self._call(self.client.closed_candles, self.inst_id, self.tf, self.warmup)
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
                       f"預熱 {seq} 根完成，權益 {facts['equity']} USDT", manifest=self.manifest)
        while True:
            bars = await self._wait_for_bar(last_open + self.tf)
            for row in bars:
                seq += 1
                await self._bar(seq, _candle(row), is_latest=row is bars[-1])
                last_open = row["open_time_ms"]
                self.status.update(bars=seq, last_bar_open_ms=last_open)
                self._write_status()

    async def _bar(self, seq, bar, *, is_latest):
        await self._kill_check()
        try:
            strategy_registry.resolve_deployment(self.worker)
        except strategy_registry.RegistryError as exc:
            raise BotStopped(f"approval_or_source_invalid:{exc}") from None
        if self.supervisor.failure:
            raise BotStopped("supervisor_failed:" + str(self.supervisor.failure))
        facts = await self._call(self._account)
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
        try:
            if self.supervisor is not None:
                try:
                    self.status["position"] = str(await self._owned_position()) if self.supervisor._journal else None
                except Exception:
                    pass
                try:
                    await self.supervisor.close()
                except Exception as exc:
                    self.status["close_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            self.status["finished_at"] = _now_text()
            if self.output_dir.exists():
                self._write_status()
                atomic_json(self.output_dir / "fills.json", self.fills)
        finally:
            if self.guard is not None:
                self.guard.release()
            if self.log is not None:
                self.log.event("stopped", f"Bot 停止：{self.status['state']}（{self.status['stop_reason']}）"
                               f"；最後部位 {self.status['position']}", status=self.status)
                self.log.close()


def find_demo_approval(profile):
    record = strategy_approvals.find_active(profile)
    if record["created_at"] < APPROVALS_COVER_DEMO_SINCE:
        raise strategy_approvals.ApprovalError("approval_predates_demo_coverage")
    return record


START_HINTS = {
    "account_state_missing": "這個模擬盤帳戶的風控紀錄不見了（~/.catos/okx-demo-accounts/）。要從頭開始，由你本人把同名的 .json 與 .lock 一起刪掉；當天的虧損基準會重新起算。",
    "account_state_unreadable": "這個模擬盤帳戶的風控紀錄壞了（~/.catos/okx-demo-accounts/）。請先檢查；要從頭開始，由你本人把同名的 .json 與 .lock 一起刪掉。",
    "account_busy": "這個 OKX 帳戶已經有一個 Bot 在跑；同一個帳戶一次只能跑一個。",
    "contract_not_flat_at_start": "模擬盤上 BTC-USDT-SWAP 還有部位或掛單，先到 OKX 網頁平倉、撤單再啟動。",
    "foreign_positions_or_orders_in_account": "模擬盤帳戶裡有別的合約的部位或掛單，先到 OKX 網頁處理掉再啟動。",
}


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
    try:
        bot = DemoBot(client=client, record=record, output_dir=directory)
        status = asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n已收到 Ctrl+C；部位留在模擬盤上，沒有平倉。")
        return 1
    except BotStopped as exc:
        sys.stderr.write(f"沒有啟動：{exc.reason}\n")
        hint = next((text for prefix, text in START_HINTS.items() if exc.reason.startswith(prefix)), None)
        if hint:
            sys.stderr.write(hint + "\n")
        return 1
    except KillSwitchError as exc:
        sys.stderr.write(f"沒有啟動：Kill-Switch（{exc}）。要先由你本人解除\n")
        return 1
    except DemoError as exc:
        sys.stderr.write(f"沒有啟動：{exc}\n")
        return 1
    print(f"\n結束：{status['state']}（{status['stop_reason']}），最後部位 {status['position']}")
    if str(status["stop_reason"]).startswith("flatten_failed"):
        print("清倉沒有完成：請到 OKX 網頁確認模擬盤部位，必要時手動平倉。")
        return 2
    return 0 if status["state"] == "stopped" else 1


def rearm_main(argv, confirm=terminal_confirm):
    """User only: clear the Soft latch of an OKX Demo account (no Bot may be running on it)."""
    parser = argparse.ArgumentParser(prog="catos.cli demo rearm",
                                     description="解除模擬盤 Bot 的 Soft 日損鎖住（只限你本人，在終端機輸入確認）")
    parser.add_argument("--reason", required=True, help="解除原因，會記在帳戶紀錄裡")
    parser.add_argument("--accounts-dir", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not kill_switch.valid_reason(args.reason):
        sys.stderr.write("錯誤：原因要是 1～200 個可見字元\n")
        return 1
    latched = 0
    directory = accounts_directory() if args.accounts_dir is None else Path(args.accounts_dir)
    for path in sorted(directory.glob("*.json")):
        try:
            guard = AccountGuard.for_file(path)
            guard.acquire()  # a running Bot holds this lock; read only while holding it
        except BotStopped as exc:
            sys.stderr.write(f"錯誤：{path.name}：{exc.reason}\n")
            return 1
        try:
            try:
                state = guard.load()
            except BotStopped as exc:
                sys.stderr.write(f"錯誤：{path.name}：{exc.reason}\n")
                return 1
            if not state["soft_latched"]:
                continue
            latched += 1
            text = (f"模擬盤帳戶 {path.stem[:8]}… 的 Soft 日損鎖住：{state['soft_reason']}\n"
                    "解除後 Bot 又可以加倉；同一天虧損仍超過 Soft 門檻時，下一根 K 線會再鎖住。")
            try:
                word = confirm(text, REARM_WORD)
            except KillSwitchError as exc:
                sys.stderr.write(f"錯誤：{exc}（要在互動式終端機由你本人輸入）\n")
                return 1
            if word != REARM_WORD:
                print("沒有解除。")
                return 1
            rearms = list(state.get("rearms") or []) + [dict(at=_now_text(), reason=args.reason,
                                                             cleared=state["soft_reason"])]
            guard.save(dict(state, soft_latched=False, soft_reason=None, rearms=rearms))
            print("已解除 Soft 鎖住。")
        finally:
            guard.release()
    if latched == 0:
        print("沒有被 Soft 鎖住的模擬盤帳戶。")
    return 0
