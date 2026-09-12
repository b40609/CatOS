"""One local-simulation Supervisor, one SQLite writer, no network or dispatch."""

import asyncio
import json
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from decimal import Decimal, localcontext
from pathlib import Path

from catos import ipc, research, risk
from catos.account_lock import AccountLock, ENVIRONMENT
from catos.journal import FixtureDecision, HALT_REASONS, Journal, JournalError, OwnershipError, money
from catos.worker_host import WorkerHost
from catos.fake_exchange import FakeExchange


class SupervisorBusy(RuntimeError):
    pass


class SupervisorUnavailable(RuntimeError):
    pass


class LocalSupervisor:
    def __init__(self, database, *, account_id, bot_id, config, fixture_budget,
                 environment=ENVIRONMENT, risk_limits=None, exchange=None):
        self._lock = AccountLock(account_id, environment)
        self.database = Path(database).resolve()
        self.account_id = account_id
        self.bot_id = ipc.token(bot_id, "bot_id")
        self.config = ipc.WorkerConfig.from_wire(config.to_wire())
        if risk_limits is not None and not isinstance(risk_limits, risk.Limits):
            raise ipc.ProtocolError("risk_limits must be Supervisor Limits")
        self.risk_limits = risk_limits
        if exchange is not None and (type(exchange) is not FakeExchange or exchange.account_id != account_id
                                     or risk_limits is None):
            raise SupervisorUnavailable("only a matching local FakeExchange with risk enabled is supported")
        self._exchange = exchange
        self.risk_state = risk.State() if risk_limits is not None else None
        self._risk_loaded = False
        self._risk_persisted = None
        self.fixture_budget = money(fixture_budget, "fixture budget", derived=False)
        if self.fixture_budget <= 0:
            raise ipc.ProtocolError("fixture budget must be positive")
        self.checkpoint = ipc.Checkpoint(self.config)
        self.revision = 0
        self.epoch = 0
        self.halt_reasons = set()
        self.health = "RECONCILING"
        self.failure = None
        self.total_reserved = Decimal("0")
        self.pending_reservation = Decimal("0")
        self._persisted_halts = set()
        self._executor = None
        self._journal = None
        self._worker = None
        self._started = False
        self._closing = False
        self._busy = False
        self._drained = asyncio.Event()
        self._drained.set()

    @property
    def available_fixture_budget(self):
        with localcontext(research._CONTEXT):
            return self.fixture_budget - self.total_reserved - self.pending_reservation

    def latch(self, reason):
        """Fast control input on the owning event loop, including while SQLite waits."""
        if reason not in HALT_REASONS:
            raise ValueError("unsupported latch reason")
        if not self._started or self._closing:
            raise SupervisorUnavailable("Supervisor is not accepting control inputs")
        if reason not in self.halt_reasons:
            self.halt_reasons.add(reason)
            self.epoch += 1
        if self.risk_state is not None:
            self._accept_risk(risk.halt(self.risk_state, {reason}))
        # Persistence is serialized after current work; not claimed durable yet.

    def _accept_risk(self, state):
        self.risk_state = state
        self.halt_reasons |= state.reasons
        self.epoch = max(self.epoch, state.epoch)

    def _degrade_risk(self):
        if self.risk_state is not None:
            state = self.risk_state
            self._accept_risk(replace(state, health="DEGRADED", epoch=state.epoch + (state.health != "DEGRADED")))

    def _require_risk(self):
        if self.risk_state is None or not self._risk_loaded or self._closing:
            raise SupervisorUnavailable("risk mode is not accepting observations")

    def observe_risk(self, snapshot):
        """Immediate bounded reducer, independent of bars/Worker/writer waits.

        Call persist_controls to await durability. Intermediate crossings latch
        immediately even if later snapshots arrive before the writer catches up.
        """
        self._require_risk()
        self._accept_risk(risk.observe(self.risk_state, snapshot))
        if self.failure:
            self._degrade_risk()
        return self.risk_state

    def risk_timer(self, now_ms):
        self._require_risk()
        self._accept_risk(risk.expire(self.risk_state, now_ms))
        return self.risk_state

    async def _io(self, method, *args):
        loop = asyncio.get_running_loop()
        pending = loop.run_in_executor(self._executor, method, *args)
        try:
            return await asyncio.shield(pending)
        except asyncio.CancelledError:
            self.failure = "cancelled while SQLite operation may have committed"
            self.health = "DEGRADED"
            self._degrade_risk()
            # Thread work cannot be cancelled safely. Keep ownership until resolved.
            try:
                await asyncio.shield(pending)
            except Exception:
                pass
            raise

    def _load(self, state):
        self.checkpoint = state["checkpoint"]
        self.revision = state["revision"]
        self.epoch = max(self.epoch, state["epoch"])
        self._persisted_halts = set(state["halt_reasons"])
        self.halt_reasons |= self._persisted_halts
        if self.risk_limits is not None and not self._risk_loaded:
            self._accept_risk(risk.halt(state["risk_state"], self.halt_reasons))
            self._risk_loaded = True
        self.total_reserved = state["total_reserved"]
        self.health = "DEGRADED" if self.failure else state["health"]
        if state["isolated"]:
            self.failure = "bot remains isolated after a deterministic replay violation"
            self.health = "DEGRADED"

    async def _flush_halts(self):
        if self.risk_state is not None and self._risk_loaded:
            while self.risk_state != self._risk_persisted:
                state = self.risk_state
                await self._io(self._journal.save_risk, state)
                self._risk_persisted = state
                self._persisted_halts |= state.reasons
            return
        while self.halt_reasons - self._persisted_halts:
            reasons = frozenset(self.halt_reasons)
            persisted_epoch = await self._io(self._journal.record_halts, reasons)
            self.epoch = max(self.epoch, persisted_epoch)
            self._persisted_halts |= reasons

    async def _stop_worker(self):
        if self._worker is not None:
            await self._worker.close()
            self._worker = None

    @asynccontextmanager
    async def _operation(self):
        if self._closing or not self._started or self._journal is None or self.failure:
            raise SupervisorUnavailable(self.failure or "Supervisor not running")
        if self._busy:
            raise SupervisorBusy("one state/financial operation may be outstanding")
        self._busy = True
        self._drained.clear()
        try:
            yield
        except (OwnershipError, SupervisorUnavailable):
            raise
        except BaseException as exc:
            self.failure = f"{type(exc).__name__}: {exc}"
            self.health = "DEGRADED"
            self._degrade_risk()
            await self._stop_worker()
            raise
        finally:
            self._busy = False
            self._drained.set()

    async def start(self):
        if self._started or self._closing:
            raise SupervisorUnavailable("Supervisor instance is single-use")
        self._started = True
        try:
            self._lock.acquire()
            self._lock.check_database(self.database)
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="catos-sqlite")

            def open_journal():
                self._journal = Journal(self.database, self.account_id, self.fixture_budget, self.risk_limits,
                                        self._exchange is not None)
                return self._journal.register(self.bot_id, self.config)

            self._busy = True
            self._drained.clear()
            self._load(await self._io(open_journal))
            self._lock.bind_database(self.database)
            await self._flush_halts()
            return self
        except BaseException:
            self._busy = False
            self._drained.set()
            await self.close()
            raise
        finally:
            self._busy = False
            self._drained.set()

    async def reconcile(self, evidence):
        async with self._operation():
            await self._flush_halts()
            try:
                self._load(await self._io(self._journal.reconcile, self.bot_id, evidence))
            except OwnershipError:
                self._load(await self._io(self._journal.snapshot, self.bot_id))
                raise

    def _execution(self):
        if self._exchange is None or self._journal.execution is None:
            raise SupervisorUnavailable("local execution is not enabled")
        return self._journal.execution

    async def _execution_sync(self):
        stored = await self._io(self._journal.snapshot, self.bot_id)
        self._load(stored)
        if self.risk_state.mode == "FLAT":
            phase = (stored["risk_state"].phase if stored["risk_state"].mode == "FLAT"
                     and stored["risk_state"].seq == self.risk_state.seq else "WORKING")
            self._accept_risk(replace(self.risk_state, phase=phase))
        await self._flush_halts()

    async def _exchange_result(self, key, operation, argument):
        execution = self._execution()
        try:
            report = await asyncio.wait_for(getattr(self._exchange, operation)(argument), timeout=5)
        except (TimeoutError, OSError):
            await self._io(execution.uncertain, key)
        except asyncio.CancelledError:
            await self._io(execution.uncertain, key)
            raise
        else:
            try:
                await self._io(execution.apply, key, report)
            except OwnershipError as exc:
                raise JournalError("report ownership conflict requires recovery") from exc
        await self._execution_sync()
        return await self._io(execution.order, key)

    async def _submit_prepared(self, request):
        if request is None:
            await self._execution_sync()
            return None
        execution = self._execution()
        key = request["order_key"]
        await self._flush_halts()
        entered = False

        async def handoff():
            nonlocal entered
            # No await between the last in-memory check and entering transport.
            if (self._closing or self.risk_state.epoch != request["epoch"]
                    or self.risk_state.seq != request["risk_seq"]
                    or self.risk_state.time_ms != request["risk_time"]):
                return None
            entered = True
            return await self._exchange.submit(request["payload"])

        try:
            report = await asyncio.wait_for(handoff(), timeout=5)
        except (TimeoutError, OSError):
            await self._io(execution.uncertain, key)
        except asyncio.CancelledError:
            await self._io(execution.uncertain if entered else execution.abort_unsent, key)
            raise
        else:
            if not entered:
                await self._io(execution.abort_unsent, key)
            else:
                try:
                    await self._io(execution.apply, key, report)
                except OwnershipError as exc:
                    raise JournalError("report ownership conflict requires recovery") from exc
        await self._execution_sync()
        return await self._io(execution.order, key)

    async def dispatch(self, intent_key, *, now_ms):
        async with self._operation():
            execution = self._execution()
            await self._flush_halts()
            request = await self._io(execution.prepare, self.bot_id, intent_key, now_ms)
            return await self._submit_prepared(request)

    async def query_order(self, order_key):
        async with self._operation():
            execution = self._execution()
            await self._flush_halts()
            row = await self._io(execution.order, order_key)
            return await self._exchange_result(order_key, "query", row["cl_ord_id"])

    async def cancel_order(self, order_key):
        async with self._operation():
            execution = self._execution()
            await self._flush_halts()
            cl_id = await self._io(execution.start_cancel, order_key)
            if cl_id is None:
                await self._execution_sync()
                return await self._io(execution.order, order_key)
            return await self._exchange_result(order_key, "cancel", cl_id)

    async def flatten_step(self, *, now_ms, expires_at_ms):
        """One bounded local step; caller supplies subsequent query/reconciliation evidence."""
        async with self._operation():
            execution = self._execution()
            await self._flush_halts()
            if self.risk_state.mode != "FLAT":
                raise SupervisorUnavailable("FLAT is not latched")
            orders = await self._io(execution.unresolved)
            query_later = None
            for row in orders:
                # Uncertain outcomes are queried, never blindly resubmitted.
                if row["state"] in ("UNKNOWN", "SUBMITTING") or row["cancel_pending"]:
                    query_later = row
                    continue
                if not json.loads(row["payload_json"])["reduceOnly"]:
                    cl_id = await self._io(execution.start_cancel, row["order_key"])
                    if cl_id is not None:
                        await self._exchange_result(row["order_key"], "cancel", cl_id)
                        return None
            request = await self._io(execution.flatten, self.bot_id, now_ms, expires_at_ms)
            if request is None and query_later is not None:
                await self._exchange_result(query_later["order_key"], "query", query_later["cl_ord_id"])
                return None
            return await self._submit_prepared(request)

    async def control_step(self, *, now_ms, expires_at_ms):
        """Explicit synthetic control tick; no autonomous/live service is started."""
        if self.risk_state is not None and self.risk_state.mode == "FLAT":
            return await self.flatten_step(now_ms=now_ms, expires_at_ms=expires_at_ms)
        async with self._operation():
            execution = self._execution()
            await self._flush_halts()
            if self.risk_state.mode == "RUN" and self.risk_state.health == "HEALTHY":
                return None
            held = await self._io(lambda: [row[0] for row in self._journal.connection.execute(
                """SELECT r.intent_key FROM risk_orders r LEFT JOIN execution_orders e USING(intent_key)
                   WHERE r.reduce_only=0 AND e.order_key IS NULL""")])
            for key in held:
                await self._io(execution.prepare, self.bot_id, key, now_ms)
            orders = await self._io(execution.unresolved)
            for row in orders:
                if json.loads(row["payload_json"])["reduceOnly"]:
                    continue
                cl_id = await self._io(execution.start_cancel, row["order_key"])
                return await self._exchange_result(row["order_key"], "cancel" if cl_id else "query",
                                                   cl_id or row["cl_ord_id"])
            await self._execution_sync()
            return None

    async def persist_controls(self):
        async with self._operation():
            await self._flush_halts()

    async def flatten_progress(self, phase, *, now_ms):
        async with self._operation():
            self._require_risk()
            await self._flush_halts()
            before = self.risk_state
            updated = await self._io(self._journal.flatten_progress, self.bot_id, phase, now_ms)
            if self.risk_state == before:
                self._accept_risk(updated)
                self._risk_persisted = updated
            else:
                # A newer event wins over completion observed before that event.
                self._accept_risk(replace(self.risk_state, phase="WORKING"))
                await self._flush_halts()

    async def release_contract(self):
        async with self._operation():
            await self._flush_halts()
            await self._stop_worker()
            await self._io(self._journal.release, self.bot_id)
            self.health = "RELEASED"

    def _make_worker(self):
        return WorkerHost(self.bot_id, self.config, checkpoint=self.checkpoint, require_commit_ack=True)

    async def process_bar(self, event_seq, bar, account=None, *, expires_at_ms, now_ms, fixture=None):
        """Persist input, evaluate in child, commit once, then send a durable ACK."""
        fixture = FixtureDecision() if fixture is None else fixture
        fixture.validate()
        if self.risk_limits is not None and fixture != FixtureDecision():
            raise SupervisorUnavailable("fixture verdict cannot bypass installed risk engine")
        ipc.integer(now_ms, "simulation now_ms")
        async with self._operation():
            if self.health != "LOCAL_READY":
                raise SupervisorUnavailable("synthetic reconciliation required before processing")
            await self._flush_halts()
            payload = dict(bar=ipc.bar_to_wire(bar), account=ipc.account_to_wire(account))
            replay = await self._io(self._journal.prepare, self.bot_id, event_seq, payload, expires_at_ms)
            if replay is not None:
                return replay
            if self._closing:
                raise SupervisorUnavailable("Supervisor closing; input remains pending")
            if self._worker is None:
                self._worker = self._make_worker()
                await self._worker.start()
            result = await self._worker.process_bar(bar, account)
            await self._flush_halts()
            self.pending_reservation = fixture.amount if result.target_position is not None and fixture.reserve else Decimal("0")
            if self.risk_state is not None and self.risk_state.snapshot is not None and result.target_position is not None:
                with localcontext(research._CONTEXT):
                    # Conservative upper bound while the sole writer computes the
                    # actual verdict; a second financial operation stays blocked.
                    self.pending_reservation = (abs(result.target_position - account.position)
                        * self.config.contract.base_per_contract * self.risk_state.snapshot.mark)
            receipt = await self._io(self._journal.commit_result, self.bot_id, result, fixture, now_ms)
            # Transfer the pending amount to the committed total without double count.
            with localcontext(research._CONTEXT):
                self.total_reserved += receipt.reservation
            self.pending_reservation = Decimal("0")
            self._load(await self._io(self._journal.snapshot, self.bot_id))
            await self._flush_halts()
            if self._closing:
                raise SupervisorUnavailable("Supervisor closing; committed result requires recovery")
            await self._worker.acknowledge(receipt.event_seq)
            await self._flush_halts()
            return receipt

    async def close(self):
        self._closing = True
        await self._stop_worker()
        await self._drained.wait()
        await self._stop_worker()
        try:
            if self._journal is not None:
                # Persist known latches when possible, including after other failures.
                try:
                    await self._flush_halts()
                finally:
                    await self._io(self._journal.close)
                    self._journal = None
        finally:
            if self._executor is not None:
                self._executor.shutdown(wait=True)
                self._executor = None
            self._lock.close()

    async def __aenter__(self):
        return await self.start()

    async def __aexit__(self, *exc):
        await self.close()
