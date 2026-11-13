"""Historical replay of one approved research deployment on the local-sim Bot.

Step 2 (docs/step2-research-to-bot-proposal.md, approved 2026-11-12): the bars of
a registered research dataset drive the same Supervisor -> Worker -> risk ->
execution -> FakeExchange path as the R4 soak, with the bars' real timestamps.
Nothing here touches the network or a real exchange.

- The strategy resolves only through an active local approval whose profile
  matches (strategy_approvals); every bar re-checks it, so a revocation or an
  edited source stops the replay before the next bar. The position is neither
  flattened nor released (decision 1).
- Fills: decision at the bar close, fill at the next bar open with the profile's
  slippage and fee, computed by the research ledger (research._Ledger), exactly
  like the backtest. Funding is explicitly zero and there is no margin model;
  replay_consistency compares against the backtest with both turned off.
- A reversal goes out as two legs at the same next open: a reduce-only close,
  then the opening leg re-evaluated from flat (decision 8).
- A Soft/Hard crossing, a rejected verdict or any fault stops the replay with
  the reason recorded; nothing is liquidated (decision 7).
- The risk limits are a parameter; the defaults stay risk.Limits() (decision 6).
"""

import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

from catos import ipc, research, research_catalog, risk, strategy_approvals, strategy_registry
from catos.fake_exchange import FakeExchange, Fill, Report, TAG
from catos.journal import Reconciliation, digest
from catos.local_sim_r4 import (RUNTIME_FILES as R4_RUNTIME_FILES, FixtureClock, atomic_json, durable_view,
                                observe)
from catos.research_catalog import ROOT, files_hash, json_text
from catos.supervisor import LocalSupervisor

D = Decimal
BOT_ID = "replay-bot"
DEFAULT_OUTPUT = ROOT / "outputs" / "local-sim-replay"
PACES = {"full": 0, "per-bar-1s": 1}
PROGRESS_EVERY_BARS = 100
PROGRESS_EVERY_SECONDS = 1.0
# Comparison run with the new defaults the user approved for step 3 (not applied
# to risk.Limits() here): single-coin 0.5x equity = leverage 1.0 x share 0.5.
NEW_DEFAULT_LIMITS = risk.Limits(D("1.0"), D("0.50"), D("0.05"), D("0.10"))
LIMIT_SETS = {"current": risk.Limits(), "new-defaults": NEW_DEFAULT_LIMITS}
RUNTIME_FILES = tuple(R4_RUNTIME_FILES) + (
    "catos/local_sim_replay.py", "catos/research_donchian.py", "catos/research_datasets.py",
    "catos/research_only_artifacts/donchian-breakout-donchian-parameters-v1.json",
)
OK_DISPOSITIONS = ("NO_INTENT", "NO_CHANGE", "RESERVED_SIMULATION")


class ReplayStopped(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def build_id():
    return files_hash(RUNTIME_FILES)


def _now():
    return datetime.now(timezone.utc).isoformat()


def worker_config(record, contract):
    """The WorkerConfig bound to one approval record (strategy_registry re-checks it)."""
    profile = record["profile"]
    bot = strategy_approvals.bot_strategy(profile["strategy_id"], profile["version"])
    names = [name for name, _, _ in bot.research.parameters]
    deployment = ipc.Deployment(record["record_id"], record["source_sha256"], record["manifest_sha256"],
                                tuple((name, profile["parameters"][name]) for name in names),
                                D(profile["quantity"]), bot.lookback(profile["parameters"]))
    return ipc.WorkerConfig(contract, profile["timeframe_ms"], profile["warmup_bars"], profile["version"],
                            profile["strategy_id"], deployment)


def fill_config(profile, contract):
    """Next-open fill model of the replay: the profile's capital and costs, no funding, no margin."""
    return research.BacktestConfig(contract, profile["timeframe_ms"], D(profile["initial_balance"]),
                                   D(profile["fee_rate"]), D(profile["slippage_bps"]), ())


def load_bars(profile, dataset_id, max_bars=None):
    """Hash-checked dataset bars that match the profile's instrument and timeframe."""
    dataset = research_catalog.resolve_dataset(dataset_id)
    if dataset.contract.inst_id != profile["inst_id"] or dataset.timeframe_ms != profile["timeframe_ms"]:
        raise ValueError("dataset_does_not_match_profile")
    config = fill_config(profile, dataset.contract)
    bars, _ = research_catalog.load_dataset_bars(dataset.dataset_id, config)
    if max_bars is not None:
        if type(max_bars) is not int or max_bars < 1:
            raise ValueError("max_bars must be a positive integer")
        bars = bars[:max_bars]
    if len(bars) <= profile["warmup_bars"]:
        raise ValueError("dataset_too_short_for_warmup")
    return dataset, bars


class _Events:
    """events.jsonl without a per-line fsync (the ledger is the authority); fsync on close."""

    def __init__(self, path):
        self.handle = path.open("a", encoding="utf-8", newline="\n")

    def event(self, kind, **values):
        self.handle.write(json_text(dict(kind=kind, **values)) + "\n")

    def close(self):
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.handle.close()


async def _reconcile(supervisor, position, evidence_id):
    await supervisor.reconcile(Reconciliation(
        supervisor.revision, evidence_id, position, 0, 0, 0, True,
        supervisor.bot_id if position else None, "replay-position" if position else None))


async def _fill_intent(supervisor, exchange, config, receipt, view, bar, next_bar, now_ms, events, observe_again):
    """Dispatch one reserved intent at the next open; a reversal as close leg then opening leg."""
    execution = supervisor._journal.execution
    target = receipt.target_position
    legs = []
    while True:
        with localcontext(research._CONTEXT):
            closing = view.position * target < 0
            leg_target = D("0") if closing else target
            # risk.evaluate sends every legal reduction (and the reversal close) reduce-only.
            reducing = view.position != 0 and (leg_target == 0 or (
                leg_target * view.position > 0 and abs(leg_target) < abs(view.position)))
            order_key = execution.reversal_close_key(receipt.intent_key) if closing else receipt.intent_key
            preview = research._Ledger(config)
            preview.position, preview.average_entry = view.position, view.average_entry
            trade = preview.fill(research.Intent(now_ms, leg_target), next_bar)
        fill = Fill(f"fill-{receipt.event_seq}-{len(legs)}", trade.quantity.copy_abs(), trade.price, trade.fee)
        exchange.enqueue("submit", Report(digest(order_key)[:32], f"replay-{receipt.event_seq}-{len(legs)}", 1,
                                          "FILLED", fill.quantity, (fill,), True))
        calls = len(exchange.calls)
        row = await supervisor.dispatch(receipt.intent_key, now_ms=now_ms)
        if (row is None or row["order_key"] != order_key or row["state"] != "FILLED" or not row["settled"]
                or len(exchange.calls) != calls + 1):
            raise ReplayStopped("fill_not_terminal_complete")
        payload = exchange.calls[-1][1]
        if payload["tag"] != TAG or payload["reduceOnly"] is not reducing:
            raise ReplayStopped("tag_or_reduce_only_invariant_failed")
        after = await durable_view(supervisor, config, now_ms, bar.close)
        await _reconcile(supervisor, after.position, f"replay-{receipt.event_seq}-{len(legs)}")
        if after.position != trade.position_after:
            raise ReplayStopped("fill_position_mismatch")
        legs.append(dict(leg="close" if closing else ("open" if legs else "single"),
                         decision_seq=receipt.event_seq, decision_time_ms=now_ms,
                         fill_time_ms=next_bar.open_time_ms, quantity=str(trade.quantity),
                         price=str(trade.price), fee=str(trade.fee), position_after=str(after.position),
                         order_key=order_key, request=payload))
        events.event("fill", **legs[-1])
        if not closing:
            break
        # Closing leg done: a fresh risk observation of the flat position, same time.
        view = after
        await observe_again(after)
    if supervisor.total_reserved != 0:
        raise ReplayStopped("reservation_not_released")
    return after, legs


async def replay_bars(*, record, contract, bars, output_dir, risk_limits=None, pace_seconds=0,
                      stop=None, progress=None, dataset=None, approvals_path=None, resume=False):
    """Run the bars through a new ledger in ``output_dir``; returns the summary dict.

    ``record`` is the active approval (strategy_approvals.find_active). The run
    stops between complete events on ``stop``, revocation, a risk halt, a
    rejected verdict or a fault, and the reason is in the summary.

    ``resume=True`` reopens a stopped run's ledger with a new Supervisor and a
    new Worker (restored from the ledger's committed bars, checkpoint v2) and
    continues after the last committed bar. Unresolved orders or a held intent
    from an interrupted fill are not repaired here; the run then fails closed.
    """
    profile = record["profile"]
    limits = risk.Limits() if risk_limits is None else risk_limits
    if type(pace_seconds) not in (int, float) or pace_seconds not in PACES.values():
        raise ValueError("pace must be full (0) or per-bar-1s (1)")
    output_dir = Path(output_dir)
    if resume:
        previous = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        if (previous["approval_id"] != record["record_id"] or previous["profile"] != record["profile"]
                or previous["bars"] != len(bars) or previous["first_open_ms"] != bars[0].open_time_ms
                or previous["last_open_ms"] != bars[-1].open_time_ms
                or previous["risk_limits"] != limits.to_wire()):
            raise ValueError("resume_does_not_match_run")
    else:
        output_dir.mkdir(parents=True, exist_ok=False)
    config = fill_config(profile, contract)
    worker = worker_config(record, contract)  # resolves through the approval (fail closed)
    run_id = output_dir.name
    # The account lock binds an account id to one ledger path for good, so every run gets its own.
    account_id = previous["account_id"] if resume else "replay-" + uuid.uuid4().hex[:24]
    tf = profile["timeframe_ms"]
    warmup = profile["warmup_bars"]
    manifest = dict(
        run_id=run_id, created_at=_now(), mode="local-sim-historical-replay",
        approval_id=record["record_id"], approvals_path=str(strategy_approvals.approvals_path()
                                                           if approvals_path is None else approvals_path),
        approval_record=record, profile=profile, worker_config=worker.to_wire(),
        dataset=None if dataset is None else dataset.provenance(), bars=len(bars),
        first_open_ms=bars[0].open_time_ms, last_open_ms=bars[-1].open_time_ms,
        risk_limits=limits.to_wire(), pace_seconds=pace_seconds, build_id=build_id(),
        runtime_files=list(RUNTIME_FILES), funding="explicit_zero", margin_model="none",
        account_id=account_id, bot_id=BOT_ID, database="state.sqlite3",
        model=("Closed-bar decision; next-open fill with the profile's slippage and fee (research._Ledger); "
               "funding explicitly zero; no margin model; a reversal is a close leg plus an opening leg."),
        notice="一致性通過只證明部署路徑執行了和研究相同的決策，不證明成交模型接近真實交易所，也不證明獲利。")
    if resume:
        manifest = previous
    else:
        atomic_json(output_dir / "manifest.json", manifest)
    events = _Events(output_dir / "events.jsonl")
    exchange = FakeExchange(account_id)
    clock = FixtureClock(bars[0].open_time_ms)
    status = dict(run_id=run_id, state="running", bars=0, warmup_bars=0, evaluation_bars=0, fills=0,
                  last_time_ms=None, stop_reason=None, started_at=_now())
    last_progress = time.monotonic()
    started = time.monotonic()
    supervisor = None
    final = None
    pending = None
    fills = []
    balance = D(profile["initial_balance"])

    def update(force=False):
        nonlocal last_progress
        if force or status["bars"] % PROGRESS_EVERY_BARS == 0 or time.monotonic() - last_progress >= PROGRESS_EVERY_SECONDS:
            last_progress = time.monotonic()
            atomic_json(output_dir / "status.json", status)
            if progress is not None:
                progress(dict(status))

    async def observe_again(view):
        await observe(supervisor, view, view_mark[0], clock, events, balance)

    view_mark = [None]
    try:
        supervisor = LocalSupervisor(output_dir / "state.sqlite3", account_id=account_id, bot_id=BOT_ID,
                                     config=worker, fixture_budget=balance, risk_limits=limits,
                                     exchange=exchange, day_clock=clock, require_new_database=not resume)
        await supervisor.start()
        start = supervisor.checkpoint.event_seq
        if resume:
            if not 0 < start < len(bars):
                raise ReplayStopped("nothing_to_resume")
            last = bars[start - 1]
            clock.time_ms = last.open_time_ms + tf
            held = await supervisor._io(supervisor._journal.execution.unresolved)
            if held:
                raise ReplayStopped("resume_with_unresolved_orders")
            view = await durable_view(supervisor, config, last.open_time_ms + tf, last.close)
            await _reconcile(supervisor, view.position, f"replay-resume-{start}")
            status.update(bars=start, warmup_bars=min(start, warmup), evaluation_bars=max(0, start - warmup))
            events.event("resumed", after_seq=start, position=str(view.position))
        else:
            await _reconcile(supervisor, D("0"), "replay-initial")
        for index, bar in enumerate(bars[start:], start):
            if stop is not None and stop.is_set():
                raise ReplayStopped("operator_stop")
            try:
                strategy_registry.resolve_deployment(worker)
            except strategy_registry.RegistryError as exc:
                raise ReplayStopped(f"approval_or_source_invalid:{exc}") from None
            if supervisor.failure or supervisor.halt_reasons:
                raise ReplayStopped("supervisor_not_healthy")
            seq = index + 1
            now_ms = bar.open_time_ms + tf
            if seq <= warmup:
                receipt = await supervisor.process_bar(seq, bar, None, now_ms=now_ms, expires_at_ms=now_ms + tf)
                if receipt.target_position is not None or receipt.intent_key is not None:
                    raise ReplayStopped("warmup_produced_intent")
                status["warmup_bars"] += 1
            else:
                if pace_seconds and stop is not None:
                    try:
                        await asyncio.wait_for(stop.wait(), pace_seconds)
                    except TimeoutError:
                        pass
                    if stop.is_set():
                        raise ReplayStopped("operator_stop")
                elif pace_seconds:
                    await asyncio.sleep(pace_seconds)
                view = await durable_view(supervisor, config, now_ms, bar.close)
                view_mark[0] = bar.close
                try:
                    await observe(supervisor, view, bar.close, clock, events, balance)
                except RuntimeError as exc:
                    if str(exc).startswith("synthetic_risk_halt"):
                        raise ReplayStopped("risk_halt:" + str(exc).split(":", 1)[1].strip()) from None
                    raise
                receipt = await supervisor.process_bar(seq, bar, view, expires_at_ms=now_ms + tf, now_ms=now_ms)
                if receipt.disposition not in OK_DISPOSITIONS:
                    events.event("verdict", seq=seq, time_ms=now_ms, disposition=receipt.disposition,
                                 reason=receipt.reason, target=str(receipt.target_position))
                    raise ReplayStopped(f"unexpected_verdict:{receipt.disposition}:{receipt.reason}")
                if receipt.disposition == "RESERVED_SIMULATION":
                    if index + 1 == len(bars):
                        # Like the backtest's pending_intent: decided at the last close, never filled.
                        pending = dict(decision_seq=seq, decision_time_ms=now_ms,
                                       target=str(receipt.target_position), intent_key=receipt.intent_key)
                        events.event("pending_intent", **pending)
                    else:
                        _, legs = await _fill_intent(supervisor, exchange, config, receipt, view, bar,
                                                     bars[index + 1], now_ms, events, observe_again)
                        fills.extend(legs)
                        status["fills"] += len(legs)
                status["evaluation_bars"] += 1
            status["bars"] = seq
            status["last_time_ms"] = now_ms
            update()
        last = bars[-1]
        final = await durable_view(supervisor, config, last.open_time_ms + tf, last.close)
        status.update(state="completed")
    except ReplayStopped as exc:
        status.update(state="stopped", stop_reason=exc.reason)
    except Exception as exc:  # recorded, then the ledger is closed without flattening or release
        status.update(state="failed", stop_reason=f"{type(exc).__name__}: {str(exc)[:300]}")
    finally:
        if supervisor is not None:
            try:
                if final is None and supervisor._journal is not None and status["bars"]:
                    last = bars[status["bars"] - 1]
                    final = await durable_view(supervisor, config, last.open_time_ms + tf, last.close)
            except Exception:
                final = None
            await supervisor.close()
        events.close()
    status.update(finished_at=_now(), elapsed_seconds=round(time.monotonic() - started, 3))
    ledger_fills = []
    if (output_dir / "state.sqlite3").exists():
        from catos.replay_consistency import fill_rows, ledger_facts
        try:
            ledger_fills = fill_rows(ledger_facts(output_dir / "state.sqlite3")[2])
        except (ValueError, KeyError, OSError):
            ledger_fills = None
    status["fills"] = None if ledger_fills is None else len(ledger_fills)
    update(force=True)
    summary = dict(manifest, status=status, final_account=None if final is None else ipc.account_to_wire(final),
                   fills=status["fills"], session_fills=len(fills),
                   fills_sha256=None if ledger_fills is None else hashlib.sha256(
                       json_text(ledger_fills).encode()).hexdigest(),
                   pending_intent=pending, ledger_bytes=(output_dir / "state.sqlite3").stat().st_size
                   if (output_dir / "state.sqlite3").exists() else None)
    atomic_json(output_dir / "summary.json", summary)
    return summary


async def replay(*, profile, dataset_id, output_root=None, limits="current", pace="full", max_bars=None,
                 stop=None, progress=None):
    """Load the active approval for ``profile`` and the dataset, then replay into a new run directory."""
    profile = strategy_approvals.validate_profile(profile)
    record = strategy_approvals.find_active(profile)
    dataset, bars = load_bars(profile, dataset_id, max_bars)
    if limits not in LIMIT_SETS or pace not in PACES:
        raise ValueError("unknown limits or pace")
    root = Path(output_root) if output_root is not None else DEFAULT_OUTPUT
    root.mkdir(parents=True, exist_ok=True)
    directory = root / uuid.uuid4().hex
    return await replay_bars(record=record, contract=dataset.contract, bars=bars, output_dir=directory,
                             risk_limits=LIMIT_SETS[limits], pace_seconds=PACES[pace], stop=stop,
                             progress=progress, dataset=dataset)


def cli_main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m catos.cli replay",
                                     description="已核准研究策略的 local-sim Bot 歷史重播（不連網、不下真單）")
    parser.add_argument("--profile", required=True, help="部署設定 JSON 檔（要有有效核准）")
    parser.add_argument("--dataset", required=True, help="研究資料集 id")
    parser.add_argument("--limits", choices=sorted(LIMIT_SETS), default="current")
    parser.add_argument("--pace", choices=sorted(PACES), default="full")
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--max-bars", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        summary = asyncio.run(replay(profile=strategy_approvals.load_profile(args.profile),
                                     dataset_id=args.dataset, output_root=args.output_root,
                                     limits=args.limits, pace=args.pace, max_bars=args.max_bars))
    except (ValueError, OSError) as error:
        print(f"錯誤：{error}")
        return 1
    print(json.dumps({"run_dir": str(Path(args.output_root or DEFAULT_OUTPUT) / summary["run_id"]),
                      "status": summary["status"], "fills": summary["fills"],
                      "final_account": summary["final_account"]}, ensure_ascii=False, indent=2))
    return 0 if summary["status"]["state"] == "completed" else 1
