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

Resuming (2026-11-17, user "按照你建議執行"): when OKX shows a position at start, the
run the account file points to is reopened instead of refusing, but only if that run's
ledger owns exactly this position under the same approval, settings and risk limits
(nothing is adopted). Its uncertain orders are queried first, an unfinished bar input is
re-fed byte for byte, intents it decided but never sent are waited out and ended unsent,
and the missed closed bars are fed in order: they update the strategy only, and only the
newest closed bar may trade, as in the main loop. Recovering sends nothing; after it, a
ledger already FLAT is flattened and the newest bar may trade. A Soft latch in the ledger is
cleared only by a ``demo rearm`` made after the run stopped. A gap longer than one OKX
candles page (299 bars) is not bridged.

Disaster stop (P6, 2026-11-17, user: 10%, stop and tell me when it fires, a start option):
with ``--disaster-stop`` above 0, every position carries one OKX conditional order that
closes the whole position at market when the mark price moves that fraction against the
average entry (catos/protection.py computes the price; the Supervisor sends it). It is
created after an entry fill, moved when the average changes, canceled when the position
closes (a reversal's old stop is canceled before the opening leg) and after a Kill/Hard
flatten. Until OKX confirms it, increases stay blocked and later checks keep querying; it
never blocks a reduction, a flatten or reconciliation. A stop that OKX has fired ends the
run (``disaster_stop_triggered``); OKX is then flat and the next start is a new run. A stop
OKX shows changed or missing is queried again and the ledger follows OKX. Any other
conditional, OCO, trigger or trailing order on the account is foreign. Default 0: off.
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
import sqlite3
import sys
import time
import uuid

from catos import ipc, kill_switch, protection, research, risk, strategy_approvals, strategy_registry
from catos.kill_switch import KillSwitchError, terminal_confirm
from catos.journal import Reconciliation
from catos.local_sim_r4 import atomic_json, durable_view
from catos.local_sim_replay import fill_config, worker_config
from catos.okx_demo import DemoClient, DemoError, account_issues, altered_stop, connect, credentials_path
from catos.okx_demo_exchange import OkxDemoExchange
from catos.research_catalog import ROOT
from catos.supervisor import LocalSupervisor, SupervisorUnavailable

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
RESUME_CANDLES = 299      # one OKX market/candles page: the longest gap a resume bridges
RESUME_QUERY_ROUNDS = 10  # uncertain orders left by the stopped run are queried this many times
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


def _iso_ms(text):
    """Milliseconds of an ISO time written by ``_now_text``; anything unreadable counts as never."""
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return -1
    if moment.tzinfo is None:
        return -1
    return int(moment.timestamp() * 1000)


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
            run = state.get("run") if ok else None
            if run is not None:  # the last run started on this account (absent in files written before resuming)
                ok = type(run) is dict and type(run.get("dir")) is str and type(run.get("account_id")) is str
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
                 kill_path=None, accounts_dir=None, disaster_stop=D("0"), new_run=False):
        self.client = client
        # P6 (2026-11-17): exchange-side disaster stop as a fraction of the average entry price; 0 = off.
        if type(disaster_stop) is not Decimal or not disaster_stop.is_finite() or not 0 <= disaster_stop < D("0.5"):
            raise BotStopped("disaster_stop_out_of_range")
        self.disaster_stop = disaster_stop
        self.protection_configured = False
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
        self.resumed = None  # the stopped run being continued, if any
        self.new_run = new_run  # flat on OKX: never continue the last run, even with unsettled orders
        self.start_notes = []
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
        algos = self.client.pending_algos()  # conditional/OCO/trigger/trailing orders count too
        others = sorted({row["inst_id"] for row in every + orders + algos if row["inst_id"] != self.inst_id})
        mark = self.client.mark_price(self.inst_id)
        return dict(equity=snapshot["usdt_eq"], mgn_ratio=snapshot["mgn_ratio"], position=position,
                    pending=len(pending), others=others, mark=mark, avg_px=rows[0]["avg_px"] if rows else None,
                    algos=[row for row in algos if row["inst_id"] == self.inst_id])

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
        # The disaster stop never gates reconciliation or a flatten: an unconfirmed stop only keeps
        # increases blocked (journal) while later steps query it (acceptance D1, 2026-11-17).
        guard = await self.supervisor.protection_state()
        active = guard["active"]
        listed = {row["algo_cl_ord_id"]: row for row in facts["algos"]}
        if active is not None and not (guard["pending"] or guard["uncertain"] or guard["triggered"]):
            row = listed.get(active["payload"]["algoClOrdId"])
            altered = row is not None and altered_stop(row)
            if altered:  # changed outside CatOS to a limit price or a partial size (2026-11-18 review gap)
                self.log.event("protection_altered", "保底停損在 OKX 上被改成限價或部分張數：確認前不加倉。"
                               "請到 OKX 網頁撤掉這張條件單，Bot 下次檢查會重掛", algo_id=row["algo_id"],
                               sl_ord_px=row["sl_ord_px"], close_fraction=row["close_fraction"], sz=row["sz"])
            if altered or row is None or (row["sl_trigger_px"], row["side"], row["sl_trigger_px_type"] or "last") != (
                    D(active["price"]), active["side"], active["trigger"]):
                # OKX no longer lists our stop (fired or canceled there) or shows it changed: query
                # it once more and let the ledger follow what OKX reports. Nothing is resent.
                before = guard["alert"]
                try:
                    guard = await self.supervisor.protection_verify(now_ms=self.wall_ms())
                except SupervisorUnavailable as exc:
                    self.log.event("protection_wait", None, reason=str(exc))
                    guard = await self.supervisor.protection_state()
                if guard["alert"] and guard["alert"] != before:  # _protect would no longer see it change
                    self.log.event("protection_alert", self.ALERTS.get(guard["alert"]), alert=guard["alert"])
        # A fired stop ends the run; while flattening only when OKX no longer matches the ledger.
        if guard["triggered"] and (not flattening or facts["position"] != owned):
            raise BotStopped(_fired(facts["position"]))
        if facts["position"] != owned:
            raise BotStopped(f"position_mismatch:okx={facts['position']}:ledger={owned}")
        known = {item["payload"]["algoClOrdId"] for item in (guard["active"], guard["pending"]) if item}
        foreign = sorted(row["algo_cl_ord_id"] or row["algo_id"] for row in facts["algos"]
                         if row["algo_cl_ord_id"] not in known)
        if foreign and not flattening:
            raise BotStopped("foreign_algo_orders_on_contract:" + ",".join(foreign))
        position = facts["position"]
        await self.supervisor.reconcile(Reconciliation(
            self.supervisor.revision, f"okx-demo-{label}"[:64], position, 0, int(guard["active"] is not None), 0, True,
            BOT_ID if position else None, ("okx-net-" + self.inst_id) if position else None))
        self.status["position"] = str(position)

    async def _configure_protection(self):
        """Install this start's ratio; a failure stops the run (position and any confirmed OKX stop
        are kept). On resume it is only attempted once no inherited stop is pending, uncertain or
        triggered, so a refusal then is not transient. Going on without it would let a flat ledger
        (OKX ends the stop at flat) open a position with no stop at all (acceptance D1, 2026-11-18)."""
        config = protection.Config(self.disaster_stop, "mark", "earlier", "cancel_confirm")
        try:
            await self.supervisor.configure_protection(config)
        except SupervisorUnavailable as exc:
            raise BotStopped(f"protection_config_failed:{exc}") from None
        self.protection_configured = True
        if self.disaster_stop:
            self.log.event("protection_config", f"保底停損：價格從進場均價反向 {self.disaster_stop * 100:g}% 時，"
                           "由 OKX 以市價整倉平倉（標記價格觸發）", ratio=str(self.disaster_stop))

    ALERTS = {
        "protection_unconfirmed": "保底停損單還沒確認（OKX 沒回應或還查不到）：確認前不加倉，Bot 會繼續查",
        "protection_request_failed": "OKX 拒絕了保底停損單：確認前不加倉，下次檢查會重掛",
        "protection_mismatch": "保底停損和部位對不上：確認前不加倉，下次檢查會修正",
    }

    async def _protect(self, facts, *, flattening=False):
        """One disaster-stop step after a fresh observation: create, move or cancel the OKX stop.

        A step that cannot run now leaves increases blocked by the journal and is retried
        at the next check. Returns the facts to continue with (re-read after a change).
        """
        before = await self.supervisor.protection_state()
        if not self.protection_configured and not (before["pending"] or before["uncertain"] or before["triggered"]):
            # Resume: nothing is placed or moved with the stopped run's ratio (2026-11-18 review gap).
            await self._configure_protection()
            before = await self.supervisor.protection_state()
        try:
            state = await self.supervisor.protection_step(now_ms=self.wall_ms())
            if not self.protection_configured and not (state["pending"] or state["uncertain"] or state["triggered"]):
                # Resume: the inherited stop was just confirmed (which may mark the ledger for
                # reconciliation); now this start's ratio applies.
                facts = await self._reconcile_if_marked(facts, flattening)
                await self._configure_protection()
                state = await self.supervisor.protection_step(now_ms=self.wall_ms())
        except SupervisorUnavailable as exc:
            self.log.event("protection_wait", None, reason=str(exc))
            return await self._reconcile_if_marked(facts, flattening)
        if state["triggered"] and not flattening:
            facts = await self._call(self._account)  # what the fired stop left on OKX
            raise BotStopped(_fired(facts["position"]))
        active, old = state["active"], before["active"]
        if active is not None and (old is None or active["price"] != old["price"]):
            self.log.event("protection", f"保底停損已{'掛上' if old is None else '更新'}："
                           f"{'賣出' if active['side'] == 'sell' else '買入'}平倉，標記價格到 {active['price']} 觸發",
                           price=active["price"], side=active["side"], algo_id=active.get("algo_id"))
        elif active is None and old is not None:
            self.log.event("protection", "保底停損已撤銷")
        if state["alert"] and state["alert"] != before["alert"]:
            self.log.event("protection_alert", self.ALERTS.get(state["alert"]), alert=state["alert"])
        # A stop that appeared or went away marks the ledger for reconciliation; on resume two steps
        # may do both (confirm the inherited one, then cancel it), so the mark is read, not inferred
        # from the end states (Gemini second opinion O4, 2026-11-18).
        return await self._reconcile_if_marked(facts, flattening)

    async def _reconcile_if_marked(self, facts, flattening):
        """Confirm against OKX before going on when a protection change marked the ledger."""
        if self.supervisor.health != "RECONCILING":
            return facts
        facts = await self._call(self._account)
        await self._reconcile(facts, "protection", flattening=flattening)
        return facts

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
        # The account file latches on an actual crossing (a resumed ledger may still hold a
        # Soft latch the user has since cleared with demo rearm; that one is not re-recorded).
        if "soft_loss" in risk.loss_reasons(state, self.limits) and not self.account_state["soft_latched"]:
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
            # Partly filled and the rest canceled (Gemini review, 2026-11-18): the filled part is a real
            # position, so it is recorded, reconciled and protected like any fill before the run stops.
            partial = row["state"] != "FILLED" and D(row["filled"]) != 0
            if row["state"] != "FILLED" and not partial:
                self.log.event("order", f"委託未成交：{row['state']}", row={k: row[k] for k in ("cl_ord_id", "state")})
                raise BotStopped(f"order_{row['state'].lower()}")
            await self._record_fill(row, "部分成交" if partial else "反手平倉" if closing_leg else
                                    "反手只平倉" if receipt.reason == "reversal_close_only" else "開倉／調整")
            facts = await self._call(self._account)
            await self._reconcile(facts, f"fill-{row['cl_ord_id']}")
            state = await self._observe(facts, self.wall_ms())
            if state.mode == "FLAT":  # e.g. Hard right after the fill: flatten now, as a minute check would
                await self._flatten(",".join(sorted(state.reasons)))
                raise BotStopped("risk_flat:" + ",".join(sorted(state.reasons)))
            # The disaster stop follows the new position. A reversal's old stop is canceled before
            # the opening leg, which the journal would otherwise refuse as an unprotected increase.
            facts = await self._protect(facts)
            if partial:
                guard = await self.supervisor.protection_state()
                confirmed = guard["active"] is not None and not (guard["pending"] or guard["uncertain"])
                stop = ("" if facts["position"] == 0 else
                        f"保底停損在 {guard['active']['price']}；" if confirmed else
                        "沒有設保底停損；" if not self.disaster_stop else
                        "保底停損還沒確認，請到 OKX 網頁看條件單；")
                self.log.event("order", f"委託只成交一部分就被撤（{row['state']}）：成交 {abs(D(row['filled']))} 張，"
                               f"已記帳；目前部位 {facts['position']}，{stop}Bot 停下，用同一個指令重開會接續",
                               row={k: row[k] for k in ("cl_ord_id", "state", "quantity", "filled")})
                raise BotStopped(f"order_partially_filled:{row['state'].lower()}")
            if not closing_leg:
                return facts
            closed_first = True
            now_ms = self.wall_ms()

    async def _flatten(self, reason):
        """FLAT latched (Kill-Switch or Hard): reduce-only market orders until OKX shows zero."""
        self.log.event("flatten", f"清倉開始（{reason}）")
        try:
            await self._flatten_rounds()
        except BotStopped as exc:
            if exc.reason.startswith("disaster_stop_triggered"):
                self.log.event("flatten_failed", "清倉途中 OKX 的保底停損先觸發了，OKX 已經平倉：請到 OKX 網頁確認部位是 0；"
                               "Kill-Switch 維持觸發")
            elif exc.reason.startswith("disaster_stop_incomplete"):
                self.log.event("flatten_failed", "清倉途中 OKX 的保底停損觸發了，但沒有完全平倉：OKX 上還有部位，"
                               "帳本已對不上，Bot 不能再下單。請到 OKX 網頁手動平倉；Kill-Switch 維持觸發")
            else:
                self.log.event("flatten_failed", f"清倉沒有完成（{exc.reason}）：部位可能還在 OKX 上，"
                               "請到 OKX 網頁確認並手動平倉；Kill-Switch 維持觸發")
            raise BotStopped(f"flatten_failed:{exc.reason}") from None

    async def _flatten_rounds(self):
        for attempt in range(FLATTEN_ROUNDS):
            facts = await self._call(self._account, tries=FLATTEN_READ_TRIES)
            if facts["position"] == 0 and not await self.supervisor._io(self.supervisor._journal.execution.unresolved):
                await self._reconcile(facts, f"flat-{attempt}", flattening=True)
                self.log.event("flatten_done", "清倉完成：模擬盤部位 0")
                await self._remove_stop_after_flat(facts)
                return
            now_ms = self.wall_ms()
            await self._reconcile(facts, f"flatten-{attempt}", flattening=True)
            await self._observe(facts, now_ms)
            row = await self.supervisor.flatten_step(now_ms=now_ms, expires_at_ms=now_ms + 60_000)
            if row is not None:
                row = await self._settle(row)
                if D(row["filled"]) != 0:  # also partly filled; the next round closes the rest (acceptance O1)
                    await self._record_fill(row, "清倉" if row["state"] == "FILLED" else "清倉（部分成交）")
        facts = await self._call(self._account, tries=FLATTEN_READ_TRIES)
        raise BotStopped(f"flatten_incomplete:okx_position={facts['position']}")

    async def _remove_stop_after_flat(self, facts):
        """Flat after Kill/Hard: cancel the disaster stop too; a failure here only warns (the position is 0)."""
        if (await self.supervisor.protection_state())["active"] is None:
            return
        try:
            await self._observe(facts, self.wall_ms())
            await self._protect(facts, flattening=True)  # other contracts' positions do not matter here
        except BotStopped as exc:
            self.log.event("protection_left", f"保底停損單沒有確認撤掉（{exc.reason}）：部位已是 0，"
                           "請到 OKX 網頁的條件單確認並撤銷", reason=exc.reason)
            return
        if (await self.supervisor.protection_state())["active"] is not None:
            self.log.event("protection_left", "保底停損單還沒確認撤掉：部位已是 0，請到 OKX 網頁的條件單確認並撤銷")

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
        # Foreign positions/orders/conditional orders, the position and the disaster stop's
        # presence on OKX (a triggered stop ends the run here, between bars).
        await self._reconcile(facts, "minute")
        state = await self._observe(facts, self.wall_ms())
        if state.mode == "FLAT":
            await self._flatten(",".join(sorted(state.reasons)))
            raise BotStopped("risk_flat:" + ",".join(sorted(state.reasons)))
        await self._protect(facts)

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
            if facts["pending"] or (facts["position"] == 0 and facts["algos"]):
                raise BotStopped(f"contract_not_flat_at_start:position={facts['position']}:orders={facts['pending']}"
                                 f":algo_orders={len(facts['algos'])}")
            if facts["position"] != 0:
                self.resumed = self._resumable_run(facts)  # refuses unless the last run's ledger owns it
                self.output_dir = self.resumed["dir"]
            elif not self.new_run:
                # Flat on OKX, but the last run may have stopped with an order of unknown outcome (e.g. a
                # close whose answer was lost): continue that run so the order is queried and its ledger
                # settled, instead of leaving it open forever (2026-11-18 review gap).
                self.resumed = self._unsettled_flat_run(facts)
                if self.resumed is not None:
                    self.output_dir = self.resumed["dir"]
            if facts["others"]:
                raise BotStopped("foreign_positions_or_orders_in_account:" + ",".join(facts["others"]))
            if self.resumed is None:
                self.output_dir.mkdir(parents=True, exist_ok=False)
        except BaseException:
            guard.release()
            raise
        self.guard = guard
        self.echo(f"紀錄資料夾：{self.output_dir}" + ("" if not self.resumed else "（接續上一次的 run）" if facts["position"]
                                                    else "（接續上一次的 run：有委託沒結清，先查清楚）"))
        try:
            self._open_run(facts, contract)
        except BaseException:
            guard.release()
            self.guard = None
            if self.log is not None:
                self.log.close()
                self.log = None
            raise
        for message, fields in self.start_notes:
            self.log.event("previous_run_unsettled", message, **fields)
        try:
            await self.supervisor.start()
            # A resumed ledger that already latched Hard engaged the Kill-Switch back then.
            self.hard_engaged = "hard_loss" in self.supervisor.risk_state.reasons
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

    def _unsettled_flat_run(self, facts):
        """The last run, if its ledger has unsettled orders and it can be continued; otherwise None.

        A run that cannot be continued (changed approval or settings, unreadable, stopped too long
        ago) is left as it is and a new run starts; the reason is logged in the new run.
        """
        pointer = self.account_state.get("run")
        if pointer is None:
            return None
        directory = Path(pointer["dir"])
        try:
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            connection = sqlite3.connect((directory / manifest["database"]).resolve().as_uri() + "?mode=ro", uri=True)
            try:
                unresolved = connection.execute("SELECT COUNT(*) FROM execution_orders WHERE settled=0").fetchone()[0]
            finally:
                connection.close()
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
            # Nothing readable to settle (a position would have been refused above); said, not silent
            # (acceptance O6, 2026-11-18).
            self.start_notes.append((f"讀不到上一次 run 的帳本，不知道有沒有沒結清的委託，開新的 run；舊資料夾 {directory}",
                                     dict(reason="previous_run_unreadable", previous_run=str(directory))))
            return None
        if not unresolved:
            return None

        def note(why, reason):
            self.start_notes.append((f"上一次 run 有 {unresolved} 筆委託沒結清，但{why}，開新的 run；舊帳本保留在 {directory}",
                                     dict(reason=reason, unsettled=unresolved, previous_run=str(directory))))

        try:
            resumed = self._resumable_run(facts)
            status = json.loads((directory / "status.json").read_text(encoding="utf-8"))
            last_open = int(status["last_bar_open_ms"])
        except BotStopped as exc:
            note(f"不能接續（{exc.reason}）", exc.reason)
            return None
        except (OSError, ValueError, KeyError, TypeError):
            note("讀不到它停在哪根 K 線", "resume_last_bar_unreadable")
            return None
        if (self.wall_ms() - last_open) // self.tf >= RESUME_CANDLES - 1:
            note("停下太久補不回 K 線", "resume_gap_too_long")
            return None
        return resumed

    def _resumable_run(self, facts):
        """The account's last run, if its ledger owns exactly the OKX position; otherwise refuse.

        Read-only: nothing in the old run changes before every check here has passed.
        """
        pointer = self.account_state.get("run")
        if pointer is None:
            raise BotStopped(f"contract_not_flat_at_start:position={facts['position']}:orders={facts['pending']}")
        directory = Path(pointer["dir"])
        try:
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            database = directory / manifest["database"]
            ok = (manifest.get("mode") == "okx-demo-bot" and manifest.get("bot_id") == BOT_ID
                  and manifest.get("account_id") == pointer["account_id"] and database.is_file())
            budget = D(manifest["starting_equity"])
        except (OSError, ValueError, KeyError, TypeError, ArithmeticError):
            ok = False
        if not ok:
            raise BotStopped(f"resume_run_unreadable:{directory}")
        if manifest.get("approval_id") != self.record["record_id"]:
            raise BotStopped("resume_approval_changed")
        if (manifest.get("worker_config") != json.loads(json.dumps(self.worker.to_wire(), default=str))
                or manifest.get("risk_limits") != json.loads(json.dumps(self.limits.to_wire(), default=str))):
            raise BotStopped("resume_config_changed")
        try:
            connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                owner = connection.execute("SELECT position FROM ownership WHERE bot_id=?", (BOT_ID,)).fetchone()
                bot = connection.execute("SELECT isolated FROM bots WHERE bot_id=?", (BOT_ID,)).fetchone()
                unresolved = connection.execute("SELECT COUNT(*) FROM execution_orders WHERE settled=0").fetchone()[0]
            finally:
                connection.close()
        except sqlite3.Error:
            raise BotStopped(f"resume_run_unreadable:{database}") from None
        if bot is None or bot[0] or owner is None:
            raise BotStopped("resume_run_unreadable:ledger_not_resumable")
        owned = D("0") if owner[0] is None else D(owner[0])
        # Uncertain orders are queried after the ledger opens; they may explain the difference.
        if not unresolved and owned != facts["position"]:
            raise BotStopped(f"resume_position_mismatch:okx={facts['position']}:ledger={owned}")
        try:
            fills = json.loads((directory / "fills.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            fills = []  # stopped before writing it; every fill is still in the ledger and events.jsonl
        except (OSError, ValueError):
            raise BotStopped(f"resume_run_unreadable:{directory / 'fills.json'}") from None
        if type(fills) is not list:
            raise BotStopped(f"resume_run_unreadable:{directory / 'fills.json'}")
        return dict(dir=directory, manifest=manifest, budget=budget, fills=fills)

    def _open_run(self, facts, contract):
        """Run folder, log, manifest and Supervisor (not started yet)."""
        if self.resumed is not None:
            return self._reopen_run(facts)
        profile = self.profile
        self.log = _Log(self.output_dir, self.echo)
        account_id = "okxdemo-" + uuid.uuid4().hex[:24]
        manifest = dict(run_id=self.output_dir.name, created_at=_now_text(), mode="okx-demo-bot",
                        exchange="OKX Demo (x-simulated-trading: 1)", approval_id=self.record["record_id"],
                        approval_record=self.record, profile=profile, worker_config=self.worker.to_wire(),
                        contract=dict(inst_id=contract.inst_id, base_per_contract=str(contract.base_per_contract),
                                      tick_size=str(contract.tick_size), lot_size=str(contract.lot_size),
                                      min_size=str(contract.min_size)),
                        risk_limits=self.limits.to_wire(), disaster_stop=str(self.disaster_stop),
                        account_id=account_id, bot_id=BOT_ID,
                        starting_equity=str(facts["equity"]), database="state.sqlite3",
                        ledger_environment_label="local-sim",
                        notice=("帳本沿用 local-sim 的結構與標籤（不改資料庫結構）；實際交易所是 OKX 模擬盤。"
                                "外部資金流在模擬盤階段不分類（2026-11-16 使用者決定）。"))
        atomic_json(self.output_dir / "manifest.json", manifest)
        # The account remembers its last run, so a restart with a position can resume it.
        self.account_state = dict(self.account_state, run=dict(dir=str(self.output_dir.resolve()),
                                                               account_id=account_id))
        self.guard.save(self.account_state)
        exchange = OkxDemoExchange(self.client, account_id, self.inst_id)
        self.supervisor = LocalSupervisor(self.output_dir / "state.sqlite3", account_id=account_id, bot_id=BOT_ID,
                                          config=self.worker, fixture_budget=facts["equity"], risk_limits=self.limits,
                                          exchange=exchange, day_clock=self, require_new_database=True)
        self.manifest = manifest

    def _reopen_run(self, facts):
        """Resume: the same folder, log, ledger and account id; the manifest records the resume."""
        resumed = self.resumed
        stop_file = self.output_dir / "stop.request"
        if stop_file.exists():  # the request that stopped the old run is used up, not obeyed again
            stop_file.replace(self.output_dir / f"stop.request.used-{_wall_ms()}")
        self.log = _Log(self.output_dir, self.echo)
        manifest = resumed["manifest"]
        manifest = dict(manifest, resumes=[*manifest.get("resumes", []), dict(
            at=_now_text(), equity=str(facts["equity"]), okx_position=str(facts["position"]),
            disaster_stop=str(self.disaster_stop))])
        atomic_json(self.output_dir / "manifest.json", manifest)
        self.fills = list(resumed["fills"])
        self.status.update(fills=len(self.fills), resumed=True)
        exchange = OkxDemoExchange(self.client, manifest["account_id"], self.inst_id)
        self.supervisor = LocalSupervisor(self.output_dir / manifest["database"], account_id=manifest["account_id"],
                                          bot_id=BOT_ID, config=self.worker, fixture_budget=resumed["budget"],
                                          risk_limits=self.limits, exchange=exchange, day_clock=self,
                                          require_new_database=False)
        self.manifest = manifest

    async def _main_loop(self, facts):
        if self.resumed is None:
            seq, last_open = await self._warm_up(facts)
        else:
            seq, last_open = await self._resume()
        while True:
            bars = await self._wait_for_bar(last_open + self.tf)
            for row in bars:
                seq += 1
                await self._bar(seq, _candle(row), is_latest=row is bars[-1])
                last_open = row["open_time_ms"]
                self.status.update(bars=seq, last_bar_open_ms=last_open)
                self._write_status()

    async def _warm_up(self, facts):
        profile = self.profile
        await self._reconcile(facts, "start")
        await self._configure_protection()
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
        return seq, last_open

    # ---- resume ----
    async def _recover(self):
        """What the stopped run left behind, settled before anything new. Nothing is sent here.

        Uncertain orders are queried (never resent); an input written but not finished is
        re-fed with the same bytes; intents decided but never sent end unsent once their
        deadline has passed. The OKX position must then equal the ledger's.
        """
        journal = self.supervisor._journal
        for _ in range(RESUME_QUERY_ROUNDS):
            unresolved = await self.supervisor._io(journal.execution.unresolved)
            if not unresolved:
                break
            for row in unresolved:
                row = await self.supervisor.query_order(row["order_key"])
                if row["settled"] and D(row["filled"]) != 0:  # also partly filled, rest canceled
                    await self._record_fill(row, "接續時補查")
            await self.sleep(1)
        unresolved = await self.supervisor._io(journal.execution.unresolved)
        if unresolved:
            raise BotStopped("resume_unresolved_orders:" + ",".join(row["cl_ord_id"] for row in unresolved))
        facts = await self._call(self._account)
        await self._reconcile(facts, "resume")
        pending = await self.supervisor._io(lambda: journal.connection.execute(
            "SELECT seq,input_json FROM inputs WHERE bot_id=? AND state='PENDING'", (BOT_ID,)).fetchone())
        if pending is not None:
            stored = ipc.decode_payload(pending["input_json"].encode("utf-8"))
            bar, account, _ = ipc.parse_event(stored["payload"], self.supervisor.checkpoint)
            receipt = await self.supervisor.process_bar(pending["seq"], bar, account, now_ms=self.wall_ms(),
                                                        expires_at_ms=stored["expires_at_ms"])
            self.log.event("resume_input", f"補完上一次 run 沒處理完的那根 K 線：{receipt.disposition}",
                           seq=pending["seq"], disposition=receipt.disposition, reason=receipt.reason)
        held = await self.supervisor._io(lambda: [tuple(row) for row in journal.connection.execute(
            """SELECT o.intent_key,p.input_json FROM outbox o JOIN intents i USING(intent_key)
               JOIN inputs p ON p.bot_id=i.bot_id AND p.seq=i.seq ORDER BY i.seq""")])
        for intent_key, input_json in held:
            deadline = json.loads(input_json)["expires_at_ms"]
            while self.wall_ms() <= deadline:
                await self.sleep(min(1.0, max(0.05, (deadline + 1 - self.wall_ms()) / 1000)))
            row = await self.supervisor.dispatch(intent_key, now_ms=self.wall_ms())
            if row is not None:  # past its deadline nothing may go out; stop rather than guess
                raise BotStopped("resume_sent_an_order:" + row["cl_ord_id"])
            self.log.event("resume_intent", "上一次 run 決定了但沒送出的委託：已過期限，結束、不送出", intent_key=intent_key)
        facts = await self._call(self._account)
        await self._reconcile(facts, "resume-ready")
        return facts

    async def _resume(self):
        """Continue the stopped run: recover, observe, then feed the closed bars it missed."""
        # The stopped run's last risk observation: a Soft latch in its ledger is no later than this.
        stopped_risk_ms = self.supervisor.risk_state.time_ms
        facts = await self._recover()
        now_ms = self.wall_ms()
        state = await self._observe(facts, now_ms)
        if state.mode == "FLAT":
            await self._flatten(",".join(sorted(state.reasons)))
            raise BotStopped("risk_flat:" + ",".join(sorted(state.reasons)))
        if state.reasons == frozenset({"soft_loss"}) and not self.account_state["soft_latched"]:
            rearms = list(self.account_state.get("rearms") or [])
            if rearms and _iso_ms(rearms[-1].get("at")) > stopped_risk_ms:
                # The user cleared Soft with demo rearm after the run stopped; the ledger follows,
                # unless the loss is still past the threshold (then it stays latched).
                try:
                    await self.supervisor.rearm(now_ms=now_ms, actor="cli", evidence_id=f"demo-rearm-{len(rearms) - 1}")
                    self.log.event("soft_rearmed", "Soft 鎖住已由你解除（demo rearm），接續的 run 也解除")
                except SupervisorUnavailable as exc:
                    self.log.event("soft_rearm_refused", f"Soft 仍鎖住：{exc}")
            else:
                # No rearm after the run stopped (e.g. saving the account file failed when Soft
                # latched): the ledger's latch stands and the account file is brought back in line.
                self.account_state = dict(self.account_state, soft_latched=True,
                                          soft_reason=f"soft_loss（接續時從帳本補回）{_now_text()}")
                self.guard.save(self.account_state)
                self.log.event("soft_latched", "帳本的 Soft 鎖住沒有對應的 demo rearm：維持鎖住，帳戶紀錄已補回")
        # This start's --disaster-stop applies (it may differ from the stopped run's): _protect installs
        # it once the inherited stop is confirmed on OKX, and the stop follows.
        facts = await self._protect(facts)
        seq = self.supervisor.checkpoint.event_seq
        last_open = self.supervisor.checkpoint.last_open_time_ms
        candles = await self._call(self.client.closed_candles, self.inst_id, self.tf, RESUME_CANDLES)
        if any(b["open_time_ms"] - a["open_time_ms"] != self.tf for a, b in zip(candles, candles[1:])):
            raise BotStopped("resume_candles_not_contiguous")
        missed = [row for row in candles if row["open_time_ms"] > last_open]
        if missed and missed[0]["open_time_ms"] != last_open + self.tf:
            raise BotStopped(f"resume_gap_too_long:last_bar={last_open}:oldest_available={missed[0]['open_time_ms']}")
        for row in missed[:-1]:  # missed while stopped: the strategy sees them, nothing trades
            seq += 1
            await self._catch_up_bar(seq, _candle(row), facts)
        if missed:  # the newest closed bar is decided like any latest bar
            seq += 1
            await self._bar(seq, _candle(missed[-1]), is_latest=True)
            last_open = missed[-1]["open_time_ms"]
        self.status.update(state="running", bars=seq, last_bar_open_ms=last_open)
        self._write_status()
        self.log.event("started", f"Bot 接續：補上停下期間的 {len(missed)} 根 K 線；"
                       f"部位 {self.status['position']}，權益 {facts['equity']} USDT", resumed=True,
                       missed=len(missed), manifest=self.manifest)
        return seq, last_open

    async def _catch_up_bar(self, seq, bar, facts):
        """A closed bar missed while stopped: its deadline is now, so an intent can only expire."""
        view = await self._view(facts, bar.open_time_ms + self.tf)
        now_ms = self.wall_ms()
        receipt = await self.supervisor.process_bar(seq, bar, view, now_ms=now_ms, expires_at_ms=now_ms)
        if receipt.disposition not in ("NO_INTENT", "NO_CHANGE", "REJECTED", "EXPIRED"):
            raise BotStopped(f"unexpected_disposition:{receipt.disposition}")
        self.log.event("bar", None, seq=seq, bar=ipc.bar_to_wire(bar), catch_up=True,
                       disposition=receipt.disposition, reason=receipt.reason,
                       target=None if receipt.target_position is None else str(receipt.target_position))

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
        facts = await self._protect(facts)  # a missing or stale disaster stop is fixed before deciding
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
            if receipt.reason == "reversal_close_only":
                self.log.event("order", "反手的開新倉被風控擋下：只平掉原部位")
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
    "contract_not_flat_at_start": "模擬盤上 BTC-USDT-SWAP 有掛單或條件單，或有部位但帳戶紀錄沒有可以接續的上一次 run，先到 OKX 網頁平倉、撤單再啟動。",
    "foreign_positions_or_orders_in_account": "模擬盤帳戶裡有別的合約的部位或掛單，先到 OKX 網頁處理掉再啟動。",
    "resume_run_unreadable": "模擬盤上有部位，但上一次 run 的資料夾不見了或讀不到，不能接續。先到 OKX 網頁平倉再啟動。",
    "resume_approval_changed": "上一次 run 用的核准跟現在有效的核准不同（重新核准或撤銷過），不能接續。先到 OKX 網頁平倉再啟動。",
    "resume_config_changed": "上一次 run 的策略設定或風控門檻跟現在不同，不能接續。先到 OKX 網頁平倉再啟動。",
    "resume_position_mismatch": "OKX 上的部位跟上一次 run 的帳本對不上（可能有人手動下過單），不會接手。先到 OKX 網頁處理部位再啟動。",
    "resume_unresolved_orders": "上一次 run 留下結果不明的委託，查了幾次還是查不到，不能接續。請到 OKX 網頁確認部位與委託，平倉後再啟動；"
                                "OKX 已經空倉時，啟動指令加 --new-run 開新的 run（舊 run 的帳本保留、不結清）。",
    "resume_gap_too_long": "停下太久（超過 299 根 K 線，15 分鐘線約 3 天），補不回中間的 K 線，不能接續。先到 OKX 網頁平倉再啟動。",
    "disaster_stop_triggered": "OKX 的保底停損已觸發並平倉（模擬盤）。Bot 已停下；到 OKX 網頁確認部位是 0、沒有剩下的條件單之後，用同一個指令重開會從空倉開始。",
    "disaster_stop_incomplete": "OKX 的保底停損觸發了，但 OKX 上還有部位（停損單沒有完全成交）。帳本已經對不上，Bot 不能替你處理：請到 OKX 網頁手動平倉，再用同一個指令重開。",
    "foreign_algo_orders_on_contract": "模擬盤上 BTC-USDT-SWAP 有不是 Bot 掛的條件單（停損、止盈、計畫或追蹤委託），先到 OKX 網頁撤掉再啟動。",
    "order_partially_filled": "委託只成交一部分，剩下的被 OKX 撤掉。成交的部分已記帳，Bot 先停下讓你看一下；到 OKX 網頁確認部位與條件單後，用同一個指令重開會接續目前部位。",
    "protection_config_failed": "保底停損比例裝不上，Bot 先停下；部位與 OKX 上已確認的條件單都留著。用同一個指令重開會再試；還是不行就把錯誤訊息截圖給我。",
    "disaster_stop_out_of_range": "--disaster-stop 要在 0% 到 50% 之間（0 表示不掛保底停損）。",
}


def _percent(text):
    """'10%', '10' or '0' -> Decimal fraction (0.1); argparse reports anything else."""
    raw = str(text).strip().removesuffix("%")
    try:
        value = Decimal(raw)
    except ArithmeticError:
        raise argparse.ArgumentTypeError("要寫成百分比，例如 10%") from None
    if not value.is_finite() or not 0 <= value < 50:
        raise argparse.ArgumentTypeError("要在 0% 到 50% 之間（0 表示不掛保底停損）")
    return value / 100


def _fired(okx_position):
    """Stop reason after OKX fired the disaster stop: flat, or something left (failed/partial)."""
    return "disaster_stop_triggered" if okx_position == 0 else f"disaster_stop_incomplete:okx={okx_position}"


def _hint(reason):
    return next((text for prefix, text in START_HINTS.items() if str(reason).startswith(prefix)), None)


def cli_main(argv):
    parser = argparse.ArgumentParser(prog="catos.cli demo bot", description="核准過的策略在 OKX 模擬盤上跑（前景執行，Ctrl+C 停止）")
    parser.add_argument("--profile", required=True, help="部署設定 JSON（要先由使用者核准）")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--disaster-stop", type=_percent, default=Decimal("0"), metavar="10%",
                        help="保底停損：價格從進場均價反向這麼多時，由 OKX 以市價整倉平倉（電腦當機、斷線時的最後保險）。"
                             "預設 0（不掛）")
    parser.add_argument("--new-run", action="store_true",
                        help="OKX 空倉時一定開新的 run，不接續上一次有委託沒結清的 run（舊帳本保留、不結清）")
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
    directory = Path(args.output_root) / uuid.uuid4().hex  # a resumed run keeps its own folder instead
    print("停止：按 Ctrl+C（部位保留，重開會接續），或在紀錄資料夾建立 stop.request；緊急停止用 Kill-Switch（會平倉）。\n")
    try:
        bot = DemoBot(client=client, record=record, output_dir=directory, disaster_stop=args.disaster_stop,
                      new_run=args.new_run)
        status = asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n已收到 Ctrl+C；部位留在模擬盤上，沒有平倉。用同一個指令重開會接續這個 run。")
        return 1
    except BotStopped as exc:
        sys.stderr.write(f"沒有啟動：{exc.reason}\n")
        hint = _hint(exc.reason)
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
    hint = _hint(status["stop_reason"])
    if hint:
        print(hint)
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
