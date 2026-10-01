"""One bounded synthetic case; stop only between complete accounting events."""

import asyncio
from dataclasses import replace
from decimal import Decimal, localcontext
import time

from catos import ipc, research, risk
from catos.data_io import load_candles_csv
from catos.fake_exchange import FakeExchange, Fill, Report, TAG
from catos.journal import digest
from catos.local_sim_r4 import FixtureClock, durable_view, observe, reconcile
from catos.research_catalog import DATA_PATH, DEFAULT_REQUEST, STRATEGY_VERSION, validate_request
from catos.supervisor import LocalSupervisor

BAR_COUNT = 8
INTERVAL_SECONDS = 1


class Stopped(Exception):
    pass


def boundary(stop):
    if stop.is_set():
        raise Stopped()


async def wait_boundary(stop):
    try:
        await asyncio.wait_for(stop.wait(), INTERVAL_SECONDS)
    except TimeoutError:
        pass
    boundary(stop)


class Events:
    def __init__(self, emit):
        self.emit = emit

    def event(self, kind, **values):
        self.emit(kind, **values)


async def run_case(directory, run_id, stop, emit, update, source_ok):
    """Returns cleanup evidence; never releases ownership, flattens or re-arms."""
    supervisor = None
    worker_process = None
    outcome, error, cleanup = "completed", None, False
    try:
        boundary(stop)
        _, config, _, _ = validate_request(DEFAULT_REQUEST)
        raw = load_candles_csv(DATA_PATH, config=config)
        day = risk.taipei_day(time.time_ns() // 1_000_000)
        anchor = day * risk.DAY_MS - risk.TAIPEI_OFFSET_MS + 22 * 3_600_000
        bars = tuple(replace(bar, open_time_ms=anchor + i * config.timeframe_ms)
                     for i, bar in enumerate(raw[:BAR_COUNT + 3]))
        worker_config = ipc.WorkerConfig(config.contract, config.timeframe_ms, 2, STRATEGY_VERSION)
        account_id = "sim-control-" + run_id
        exchange = FakeExchange(account_id)
        clock = FixtureClock(anchor)
        supervisor = LocalSupervisor(directory / "state.sqlite3", account_id=account_id,
            bot_id="sim-control-sma", config=worker_config, fixture_budget=Decimal("1000"),
            risk_limits=risk.Limits(), exchange=exchange, day_clock=clock,
            require_new_database=True)
        await supervisor.start()
        boundary(stop)
        await reconcile(supervisor, Decimal("0"), 0)
        for i, bar in enumerate(bars[:2]):
            boundary(stop)
            if not source_ok():
                raise RuntimeError("source_changed_during_simulation")
            receipt = await supervisor.process_bar(i + 1, bar, None,
                now_ms=bar.open_time_ms + config.timeframe_ms,
                expires_at_ms=bar.open_time_ms + 2 * config.timeframe_ms)
            worker_process = supervisor._worker.process
            if receipt.target_position is not None or receipt.intent_key is not None:
                raise RuntimeError("warmup_produced_intent")
            emit("warmup", seq=i + 1, target=None, disposition=receipt.disposition)
            update(warmup_bars=i + 1, worker_pid=worker_process.pid)
        boundary(stop)
        update(control_state="running")
        fills = 0
        for offset, bar in enumerate(bars[2:BAR_COUNT + 2], 1):
            await wait_boundary(stop)
            if not source_ok():
                raise RuntimeError("source_changed_during_simulation")
            worker = supervisor._worker
            if supervisor.failure or supervisor.halt_reasons or (worker and (
                    worker.failure or worker.process.returncode is not None)):
                raise RuntimeError("worker_or_supervisor_not_healthy")
            # No stop check inside this event: decision -> COMMIT -> ACK -> fill.
            seq = offset + 2
            now_ms = bar.open_time_ms + config.timeframe_ms
            view = await durable_view(supervisor, config, now_ms, bar.close)
            await observe(supervisor, view, bar.close, clock, Events(emit))
            receipt = await supervisor.process_bar(seq, bar, view,
                expires_at_ms=now_ms + config.timeframe_ms, now_ms=now_ms)
            emit("signal", seq=seq, synthetic_time_ms=now_ms,
                target=None if receipt.target_position is None else str(receipt.target_position),
                disposition=receipt.disposition, reason=receipt.reason,
                account=ipc.account_to_wire(view), intent_key=receipt.intent_key)
            if receipt.disposition not in ("NO_INTENT", "NO_CHANGE", "RESERVED_SIMULATION"):
                raise RuntimeError("unexpected_simulation_verdict")
            if receipt.disposition == "RESERVED_SIMULATION":
                with localcontext(research._CONTEXT):
                    preview = research._Ledger(config)
                    preview.position, preview.average_entry = view.position, view.average_entry
                    trade = preview.fill(research.Intent(now_ms, receipt.target_position), bars[seq])
                    fill = Fill("fill-" + str(seq), trade.quantity.copy_abs(), trade.price, trade.fee)
                exchange.enqueue("submit", Report(digest(receipt.intent_key)[:32],
                    "sim-control-" + str(seq), 1, "FILLED", fill.quantity, (fill,), True))
                row = await supervisor.dispatch(receipt.intent_key, now_ms=now_ms)
                if row is None or row["state"] != "FILLED" or not row["settled"]:
                    raise RuntimeError("synthetic_fill_not_terminal_complete")
                payload = exchange.calls[-1][1]
                if payload["tag"] != TAG or supervisor.total_reserved != 0:
                    raise RuntimeError("tag_or_reservation_invariant_failed")
                after = await durable_view(supervisor, config, now_ms, bar.close)
                await reconcile(supervisor, after.position, seq)
                emit("fill", seq=seq, synthetic_time_ms=trade.time_ms,
                    request=payload, fill=fill.to_wire(), position=str(after.position),
                    fees=str(after.fees), equity=str(after.equity), state=row["state"])
                fills += 1
            update(bars=offset, fills=fills, last_synthetic_time_ms=now_ms)
        boundary(stop)
        last = bars[BAR_COUNT + 1]
        final = await durable_view(supervisor, config,
            last.open_time_ms + config.timeframe_ms, last.close)
        emit("final_account", account=ipc.account_to_wire(final),
             risk_state=supervisor.risk_state.to_wire())
    except Stopped:
        outcome = "stopped"
    except BaseException as exc:
        outcome, error = "failed", type(exc).__name__
        if isinstance(exc, asyncio.CancelledError):
            outcome = "recovery_required"
    finally:
        try:
            if supervisor is not None:
                # Retain process reference before close clears Supervisor._worker.
                if supervisor._worker is not None:
                    worker_process = supervisor._worker.process
                await supervisor.close()
                cleanup = (supervisor._journal is None and supervisor._executor is None
                           and supervisor._lock._file is None
                           and (worker_process is None or worker_process.returncode is not None))
            else:
                cleanup = True
        except BaseException as exc:
            error = "cleanup_" + type(exc).__name__
            cleanup = False
    return {"control_state": outcome if cleanup else "recovery_required",
            "cleanup_confirmed": cleanup, "error": error,
            "worker_closed": worker_process is None or worker_process.returncode is not None}
