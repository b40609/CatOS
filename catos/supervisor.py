"""One local-simulation Supervisor, one SQLite writer, no network or dispatch."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from decimal import Decimal, localcontext
from pathlib import Path

from catos import ipc, research
from catos.account_lock import AccountLock, ENVIRONMENT
from catos.journal import FixtureDecision, HALT_REASONS, Journal, OwnershipError, money
from catos.worker_host import WorkerHost


class SupervisorBusy(RuntimeError):
    pass


class SupervisorUnavailable(RuntimeError):
    pass


class LocalSupervisor:
    def __init__(self, database, *, account_id, bot_id, config, fixture_budget, environment=ENVIRONMENT):
        self._lock = AccountLock(account_id, environment)
        self.database = Path(database).resolve()
        self.account_id = account_id
        self.bot_id = ipc.token(bot_id, "bot_id")
        self.config = ipc.WorkerConfig.from_wire(config.to_wire())
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
        # Persistence is serialized after current work; not claimed durable yet.

    async def _io(self, method, *args):
        loop = asyncio.get_running_loop()
        pending = loop.run_in_executor(self._executor, method, *args)
        try:
            return await asyncio.shield(pending)
        except asyncio.CancelledError:
            self.failure = "cancelled while SQLite operation may have committed"
            self.health = "DEGRADED"
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
        self.total_reserved = state["total_reserved"]
        self.health = "DEGRADED" if self.failure else state["health"]
        if state["isolated"]:
            self.failure = "bot remains isolated after a deterministic replay violation"
            self.health = "DEGRADED"

    async def _flush_halts(self):
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
                self._journal = Journal(self.database, self.account_id, self.fixture_budget)
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
            self._load(await self._io(self._journal.reconcile, self.bot_id, evidence))

    async def persist_controls(self):
        async with self._operation():
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
