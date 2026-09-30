"""Bounded R4 synthetic soak; existing Supervisor is the only SQLite writer."""

import argparse
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import json
import os
from pathlib import Path
import time
import uuid

from catos import ipc, research, risk
from catos.data_io import load_candles_csv
from catos.fake_exchange import FakeExchange, Fill, Report, TAG
from catos.journal import Reconciliation, digest
from catos.research_catalog import (
    DATA_PATH, ROOT, STRATEGY_VERSION, files_hash, json_text, provenance,
    validate_request, DEFAULT_REQUEST,
)
from catos.supervisor import LocalSupervisor

D = Decimal
TAIPEI = timezone(timedelta(hours=8))
PROFILES = {"smoke": (8, 1), "eight-hour": (32, 900)}
RUNTIME_FILES = (
    "catos/local_sim_r4.py", "catos/ipc.py", "catos/worker.py",
    "catos/worker_host.py", "examples/sma_state.py", "catos/research.py",
    "catos/research_catalog.py", "catos/research_strategy.py",
    "examples/closed_bar_demo.py", "examples/research-web-synthetic.csv",
    "catos/research_artifacts/sma-trend-sma-parameters-v1.json",
    "catos/supervisor.py", "catos/journal.py", "catos/risk.py",
    "catos/execution.py", "catos/fake_exchange.py", "catos/account_lock.py",
    "catos/protection.py", "catos/data_io.py",
)


def wall_text():
    return datetime.now(TAIPEI).isoformat()


def atomic_json(path, value):
    pending = path.with_suffix(".pending")
    with pending.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json_text(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    pending.replace(path)


class Evidence:
    def __init__(self, directory, profile, run_id):
        self.directory = directory
        self.status = dict(run_id=run_id, profile=profile, pid=os.getpid(), state="starting",
                           bars=0, warmup_bars=0, fills=0, anomalies=0,
                           started_at=None, finished_at=None, elapsed_seconds=None,
                           planned_seconds=PROFILES[profile][0] * PROFILES[profile][1])

    def event(self, kind, **values):
        with (self.directory / "events.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json_text(dict(wall_time=wall_text(), kind=kind, **values)) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def update(self, **values):
        self.status.update(values, heartbeat_at=wall_text())
        atomic_json(self.directory / "status.json", self.status)


class FixtureClock:
    def __init__(self, time_ms):
        self.time_ms = time_ms

    def wall_ms(self):
        return self.time_ms


class StopRequested(RuntimeError):
    pass


def project_account(rows, config, time_ms, mark):
    """Read-only replay of authoritative execution_fills using the research core."""
    with localcontext(research._CONTEXT):
        ledger = research._Ledger(replace(config, slippage_bps=D("0"), fee_rate=D("0")))
        for row in rows:
            quantity, price, fee = (D(row[name]) for name in ("quantity", "price", "fee"))
            signed = quantity if D(row["order_quantity"]) > 0 else -quantity
            ledger.fill(research.Intent(0, ledger.position + signed),
                        research.Candle(0, price, price, price, price))
            ledger.balance -= fee
            ledger.fees += fee
        return ledger.view(time_ms, mark)


async def durable_view(supervisor, config, time_ms, mark):
    def read():
        db = supervisor._journal.connection
        rows = [dict(row) for row in db.execute("""SELECT f.quantity,f.price,f.fee,
            o.quantity AS order_quantity FROM execution_fills f
            JOIN execution_orders o ON o.order_key=f.order_key ORDER BY f.rowid""")]
        owner = db.execute("SELECT position FROM ownership WHERE bot_id=?",
                           (supervisor.bot_id,)).fetchone()
        unresolved = supervisor._journal.execution.unresolved()
        return rows, None if owner is None else owner[0], unresolved

    rows, owned, unresolved = await supervisor._io(read)
    if unresolved or owned is None:
        raise RuntimeError("unresolved_or_unverified_synthetic_position")
    view = project_account(rows, config, time_ms, mark)
    if view.position != D(owned):
        raise RuntimeError("fill_projection_position_mismatch")
    return view


async def reconcile(supervisor, position, seq):
    await supervisor.reconcile(Reconciliation(
        supervisor.revision, f"r4-synthetic-{seq}", position, 0, 0, 0, True,
        supervisor.bot_id if position else None,
        "r4-synthetic-position" if position else None,
    ))


async def observe(supervisor, view, mark, clock, evidence):
    clock.time_ms = view.time_ms
    day = risk.taipei_day(view.time_ms)
    previous = supervisor.risk_state.basis
    if previous is None or previous.day != day:
        # The initial fixture is inactive from midnight. Subsequent days must
        # actually land on the pre-decision midnight boundary.
        if previous is not None and view.time_ms != day * risk.DAY_MS - risk.TAIPEI_OFFSET_MS:
            raise RuntimeError("missing_synthetic_midnight_boundary")
        equity = D("1000") if previous is None else view.equity
        baseline = risk.make_synthetic_baseline_evidence(
            account_alias=supervisor.account_id, environment="local-sim",
            day=day, equity=equity, evidence_id=f"r4-midnight-{day}")
        source = risk.SYNTHETIC_BASELINE_SOURCE
        basis = risk.DayBasis(day, equity, baseline.evidence_id,
            account_alias=supervisor.account_id, environment="local-sim", source=source,
            digest=risk.compute_baseline_digest(account_alias=supervisor.account_id,
                environment="local-sim", day=day, equity=equity, source=source,
                evidence_id=baseline.evidence_id, evidence=baseline), evidence=baseline)
        await supervisor.commit_day_basis(basis)
        evidence.event("day_basis", synthetic_time_ms=view.time_ms, basis=basis.to_wire())
    state = supervisor.observe_risk(risk.Snapshot(
        supervisor.risk_state.seq + 1, view.time_ms, view.time_ms + config_step(supervisor),
        view.equity, view.equity, view.position, mark, basis=supervisor.risk_state.basis))
    await supervisor.persist_controls()
    if state.reasons or state.mode != "RUN" or state.health != "HEALTHY":
        raise RuntimeError("synthetic_risk_halt: " + ",".join(sorted(state.reasons)))


def config_step(supervisor):
    return supervisor.config.timeframe_ms


def check_health(supervisor, directory, runtime_sha):
    if (directory / "stop.request").exists():
        raise StopRequested("operator_stop_requested")
    if files_hash(RUNTIME_FILES) != runtime_sha:
        raise RuntimeError("source_changed_during_local_sim")
    worker = supervisor._worker
    if supervisor.failure or supervisor.halt_reasons or (worker and (
            worker.failure or worker.process.returncode is not None)):
        raise RuntimeError("worker_or_supervisor_not_healthy")


async def wait_slot(deadline, supervisor, evidence, runtime_sha):
    last_wall, last_mono = time.time(), time.monotonic()
    last_heartbeat = last_mono
    while True:
        current_wall, current_mono = time.time(), time.monotonic()
        if max(current_wall - last_wall, current_mono - last_mono) > 120:
            raise RuntimeError("continuity_gap_exceeded_120_seconds")
        last_wall, last_mono = current_wall, current_mono
        if (evidence.directory / "stop.request").exists():
            raise StopRequested("operator_stop_requested")
        if current_mono - last_heartbeat >= 30 or current_mono >= deadline:
            check_health(supervisor, evidence.directory, runtime_sha)
            evidence.update(worker_pid=supervisor._worker.process.pid)
            last_heartbeat = current_mono
        if current_mono >= deadline:
            if current_mono - deadline > 120:
                raise RuntimeError("scheduled_bar_lateness_exceeded_120_seconds")
            return
        await asyncio.sleep(min(1, deadline - current_mono))


async def run(profile="smoke", *, output_root=None):
    if profile not in PROFILES:
        raise ValueError("unsupported R4 profile")
    bars_count, interval = PROFILES[profile]
    run_id = uuid.uuid4().hex
    directory = Path(output_root or ROOT / "outputs" / "local-sim-r4") / run_id
    directory.mkdir(parents=True, exist_ok=False)
    evidence = Evidence(directory, profile, run_id)
    started_mono = None
    try:
        request, config, _, _ = validate_request(DEFAULT_REQUEST)
        source = provenance()
        runtime_sha = files_hash(RUNTIME_FILES)
        raw_bars = load_candles_csv(DATA_PATH, config=config)
        day = risk.taipei_day(time.time_ns() // 1_000_000)
        anchor = day * risk.DAY_MS - risk.TAIPEI_OFFSET_MS + 22 * 3_600_000
        bars = tuple(replace(bar, open_time_ms=anchor + i * config.timeframe_ms)
                     for i, bar in enumerate(raw_bars[:bars_count + 3]))
        worker_config = ipc.WorkerConfig(config.contract, config.timeframe_ms, 2, STRATEGY_VERSION)
        account_id = "r4-" + run_id
        exchange = FakeExchange(account_id)
        clock = FixtureClock(anchor)
        manifest = dict(run_id=run_id, profile=profile, created_at=wall_text(),
            base_commit="7c346f2", mode="local-sim-synthetic", request=request,
            worker_config=worker_config.to_wire(), provenance=source,
            runtime_files=list(RUNTIME_FILES), runtime_sha256=runtime_sha,
            bars=bars_count, interval_seconds=interval, synthetic_anchor_ms=anchor,
            funding="explicit_zero", database=str(directory / "state.sqlite3"),
            model="Closed-bar decision; next-open fill at the same boundary; no terminal liquidation.")
        atomic_json(directory / "manifest.json", manifest)
        evidence.update()
        async with LocalSupervisor(directory / "state.sqlite3", account_id=account_id,
                bot_id="r4-sma", config=worker_config, fixture_budget=D("1000"),
                risk_limits=risk.Limits(), exchange=exchange, day_clock=clock,
                require_new_database=True) as supervisor:
            await reconcile(supervisor, D("0"), 0)
            for i, bar in enumerate(bars[:2]):
                receipt = await supervisor.process_bar(i + 1, bar, None,
                    now_ms=bar.open_time_ms + config.timeframe_ms,
                    expires_at_ms=bar.open_time_ms + 2 * config.timeframe_ms)
                if receipt.target_position is not None or receipt.intent_key is not None:
                    raise RuntimeError("warmup_produced_intent")
                evidence.event("warmup", seq=i + 1, target=None, disposition=receipt.disposition)
                evidence.status["warmup_bars"] += 1
            started_mono = time.monotonic()
            evidence.update(state="running", started_at=wall_text(),
                expected_finish_at=(datetime.now(TAIPEI) + timedelta(seconds=bars_count * interval)).isoformat(),
                worker_pid=supervisor._worker.process.pid)
            for offset, bar in enumerate(bars[2:bars_count + 2], 1):
                await wait_slot(started_mono + offset * interval, supervisor, evidence, runtime_sha)
                event_started = time.monotonic()
                seq = offset + 2
                now_ms = bar.open_time_ms + config.timeframe_ms
                view = await durable_view(supervisor, config, now_ms, bar.close)
                await observe(supervisor, view, bar.close, clock, evidence)
                receipt = await supervisor.process_bar(seq, bar, view,
                    expires_at_ms=now_ms + config.timeframe_ms, now_ms=now_ms)
                evidence.event("signal", seq=seq, synthetic_time_ms=now_ms,
                    target=None if receipt.target_position is None else str(receipt.target_position),
                    disposition=receipt.disposition, reason=receipt.reason,
                    account=ipc.account_to_wire(view), intent_key=receipt.intent_key)
                if receipt.disposition not in ("NO_INTENT", "NO_CHANGE", "RESERVED_SIMULATION"):
                    raise RuntimeError("unexpected_simulation_verdict: " + receipt.reason)
                if receipt.disposition == "RESERVED_SIMULATION":
                    with localcontext(research._CONTEXT):
                        preview = research._Ledger(config)
                        preview.position, preview.average_entry = view.position, view.average_entry
                        trade = preview.fill(research.Intent(now_ms, receipt.target_position), bars[seq])
                        fill = Fill("fill-" + str(seq), trade.quantity.copy_abs(), trade.price, trade.fee)
                    report = Report(digest(receipt.intent_key)[:32], "r4-" + str(seq),
                                    1, "FILLED", fill.quantity, (fill,), True)
                    exchange.enqueue("submit", report)
                    row = await supervisor.dispatch(receipt.intent_key, now_ms=now_ms)
                    if row is None or row["state"] != "FILLED" or not row["settled"]:
                        raise RuntimeError("synthetic_fill_not_terminal_complete")
                    payload = exchange.calls[-1][1]
                    if payload["tag"] != TAG or supervisor.total_reserved != 0:
                        raise RuntimeError("tag_or_reservation_invariant_failed")
                    after = await durable_view(supervisor, config, now_ms, bar.close)
                    await reconcile(supervisor, after.position, seq)
                    evidence.event("fill", seq=seq, synthetic_time_ms=trade.time_ms,
                        request=payload, fill=fill.to_wire(), position=str(after.position),
                        fees=str(after.fees), equity=str(after.equity), state=row["state"])
                    evidence.status["fills"] += 1
                evidence.status["bars"] += 1
                if time.monotonic() - event_started > 120:
                    raise RuntimeError("bar_processing_exceeded_120_seconds")
                evidence.update(last_synthetic_time_ms=now_ms)
            check_health(supervisor, directory, runtime_sha)
            last = bars[bars_count + 1]
            final = await durable_view(supervisor, config, last.open_time_ms + config.timeframe_ms, last.close)
            evidence.event("final_account", account=ipc.account_to_wire(final),
                           risk_state=supervisor.risk_state.to_wire())
        evidence.update(state="complete", finished_at=wall_text(),
                        elapsed_seconds=time.monotonic() - started_mono, worker_closed=True)
    except (Exception, asyncio.CancelledError) as error:
        stopped = isinstance(error, StopRequested)
        evidence.event("stop" if stopped else "anomaly", error=f"{type(error).__name__}: {str(error)[:512]}")
        evidence.update(state="stopped" if stopped else "failed", finished_at=wall_text(),
            anomalies=0 if stopped else 1,
            elapsed_seconds=None if started_mono is None else time.monotonic() - started_mono,
            error=f"{type(error).__name__}: {str(error)[:512]}")
    return directory, dict(evidence.status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="smoke")
    args = parser.parse_args()
    directory, status = asyncio.run(run(args.profile))
    print(json_text({"directory": str(directory), **status}), flush=True)
    return 0 if status["state"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
