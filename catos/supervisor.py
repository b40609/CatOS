"""One local-simulation Supervisor, one SQLite writer, no network or dispatch."""

import asyncio
import json
import logging
import time
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from decimal import Decimal, localcontext
from pathlib import Path

from catos import (account_report, demo_ledger_binding, ipc,
                   okx_collection as reconciliation_collection,
                   reconciliation_gate, research, risk, trade_authorization)
from catos.account_lock import AccountLock, ENVIRONMENT
from catos.journal import (FixtureDecision, HALT_REASONS, Journal, JournalError,
                           OwnershipError, Reconciliation, money)
from catos.worker_host import WorkerHost
from catos.fake_exchange import FakeExchange


class SupervisorBusy(RuntimeError):
    pass


class SupervisorUnavailable(RuntimeError):
    pass


class LocalSupervisor:
    def __init__(self, database, *, account_id, bot_id, config, fixture_budget,
                 environment=ENVIRONMENT, risk_limits=None, exchange=None, day_clock=None,
                 require_demo_trade_grant=False, demo_ledger_binding_proof=None,
                 expected_demo_uid_sha256=None, require_new_database=False):
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
        if day_clock is not None and not callable(getattr(day_clock, "wall_ms", None)):
            raise ipc.ProtocolError("day_clock must provide wall_ms")
        self._day_clock = day_clock
        if type(require_demo_trade_grant) is not bool:
            raise ipc.ProtocolError("require_demo_trade_grant must be bool")
        if type(require_new_database) is not bool:
            raise ipc.ProtocolError("require_new_database must be bool")
        if ((demo_ledger_binding_proof is None) != (expected_demo_uid_sha256 is None)
                or (demo_ledger_binding_proof is not None
                    and not isinstance(demo_ledger_binding_proof, demo_ledger_binding.DemoLedgerBinding))):
            raise ipc.ProtocolError("Demo ledger binding proof and expected UID digest must be paired")
        self._require_demo_trade_grant = require_demo_trade_grant
        self._require_new_database = require_new_database
        self._demo_ledger_binding_proof = demo_ledger_binding_proof
        self._expected_demo_uid_sha256 = expected_demo_uid_sha256
        self._demo_trade_grant = None
        self._demo_grant_generation = 0
        self._demo_consumed_authorization_ids = set()
        self.risk_state = risk.State() if risk_limits is not None else None
        self._risk_loaded = False
        self._risk_persisted = None
        self._control_generation = 0
        self._protection_alert = None
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
        self._busy_task = None
        self._drained = asyncio.Event()
        self._drained.set()

    def verify_demo_ledger_binding(self, *, account_alias, remote_environment):
        """Fail closed on Demo account-to-ledger mismatch before collection."""
        demo_ledger_binding.verify_runtime_binding(
            self._demo_ledger_binding_proof,
            expected_uid_sha256=self._expected_demo_uid_sha256,
            account_alias=account_alias,
            remote_environment=remote_environment,
            database_path=self.database,
        )

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
        self._control_generation += 1
        if reason not in self.halt_reasons:
            self.halt_reasons.add(reason)
            self.epoch += 1
        if self.risk_state is not None:
            self._accept_risk(risk.halt(self.risk_state, {reason}))
        # Persistence is serialized after current work; not claimed durable yet.

    def _accept_risk(self, state):
        if self.halt_reasons - state.reasons:
            state = risk.halt(state, self.halt_reasons)
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
        if (snapshot.basis is not None and snapshot.basis.source == risk.RISK_PERIOD_SOURCE
                and (self._risk_persisted is None or snapshot.basis != self._risk_persisted.basis)):
            raise SupervisorUnavailable("R1 basis is not durably committed")
        self._control_generation += 1
        self._accept_risk(risk.observe(self.risk_state, snapshot, self.risk_limits))
        if self.failure:
            self._degrade_risk()
        return self.risk_state

    def risk_timer(self, now_ms):
        self._require_risk()
        self._control_generation += 1
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
        current_task = asyncio.current_task()
        if self._busy_task is not None and self._busy_task is not current_task:
            raise SupervisorBusy("one state/financial operation may be outstanding")
        if self._busy_task is current_task:
            yield
            return
        self._busy_task = current_task
        self._busy = True
        self._drained.clear()
        try:
            yield
        except (OwnershipError, SupervisorUnavailable, JournalError):
            raise
        except BaseException as exc:
            self.failure = f"{type(exc).__name__}: {exc}"
            self.health = "DEGRADED"
            self._degrade_risk()
            await self._stop_worker()
            raise
        finally:
            self._busy_task = None
            self._busy = False
            self._drained.set()

    async def start(self):
        if self._started or self._closing:
            raise SupervisorUnavailable("Supervisor instance is single-use")
        self._started = True
        try:
            self._lock.acquire()
            already_bound = self._lock.check_database(self.database)
            if self._require_new_database:
                if already_bound:
                    raise SupervisorUnavailable("new ledger account is already bound")
                self.database.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with self.database.open("xb"):
                        pass
                except FileExistsError as exc:
                    raise SupervisorUnavailable("new ledger database path already exists") from exc
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="catos-sqlite")

            def open_journal():
                self._journal = Journal(self.database, self.account_id, self.fixture_budget, self.risk_limits,
                                        self._exchange is not None)
                return self._journal.register(self.bot_id, self.config)

            self._busy_task = asyncio.current_task()
            self._busy = True
            self._drained.clear()
            self._load(await self._io(open_journal))
            if self._require_demo_trade_grant and self._journal.execution is not None:
                recovered = await self._io(
                    self._journal.execution.consumed_demo_authorization_ids)
                self._demo_consumed_authorization_ids.update(recovered)
            self._lock.bind_database(self.database)
            await self._flush_halts()
            if self._exchange is not None:
                await self._log_protection_alert()
            return self
        except BaseException:
            self._busy_task = None
            self._busy = False
            self._drained.set()
            await self.close()
            raise
        finally:
            self._busy_task = None
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

    async def collect_and_reconcile(self, plan, transport, *, classifications=None,
                                    freshness_policy=None, freshness_evidence=None,
                                    freshness_builder=None,
                                    clock=None,
                                    day_ledger=None,
                                    day_ledger_provider=None,
                                    day_basis_builder=None):
        """Fence before a caller-injected bounded collection, then consume it."""
        if not isinstance(plan, reconciliation_collection.CollectionPlan):
            raise SupervisorUnavailable("formal reconciliation requires a CollectionPlan")
        async with self._operation():
            if self.health != "RECONCILING":
                raise SupervisorUnavailable("formal reconciliation requires RECONCILING state")
            await self._flush_halts()
            ownership_snapshot = await self._io(self._journal.reconciliation_snapshot, self.bot_id)
        try:
            result = await asyncio.to_thread(reconciliation_collection.collect_plan, plan, transport, clock=clock)
        except (ValueError, TypeError, AttributeError) as exc:
            raise SupervisorUnavailable("invalid formal reconciliation collection") from exc
        freshness_policy_builder = None
        if freshness_builder is not None:
            try:
                built_policy, freshness_evidence = freshness_builder(result)
                if callable(built_policy):
                    freshness_policy_builder = built_policy
                else:
                    freshness_policy = built_policy
            except Exception:
                freshness_policy, freshness_evidence = None, None
        if day_basis_builder is not None and self.risk_limits is not None:
            target_day = risk.taipei_day(plan.scope.window_end_ms)
            current_basis = await self.load_day_basis(target_day)
            blocked_day = None if self.risk_state is None else self.risk_state.basis_blocked_day
            if current_basis is None and blocked_day != target_day:
                try:
                    bootstrap_report = account_report.build_report(
                        result, scope=plan.scope, classifications=classifications,
                        expected_uid_sha256=self._expected_demo_uid_sha256,
                        **ownership_snapshot.report_attribution())
                    basis = day_basis_builder(
                        result, bootstrap_report, self._expected_demo_uid_sha256)
                    if basis is not None:
                        await self.commit_day_basis(basis)
                except Exception:
                    # Q1 is optional evidence production. Any malformed/incomplete proof
                    # leaves the basis absent so the existing D3 provider remains fail-closed.
                    pass
        return await self.reconcile_report(
            result,
            scope=plan.scope,
            classifications=classifications,
            freshness_policy=freshness_policy,
            freshness_evidence=freshness_evidence,
            freshness_policy_builder=freshness_policy_builder,
            clock=clock,
            day_ledger=day_ledger,
            day_ledger_provider=day_ledger_provider,
            ownership_snapshot=ownership_snapshot,
            revision_before=ownership_snapshot.bot_revision,
        )

    async def reconcile_report(self, result, *, scope, classifications=None,
                               freshness_policy=None, freshness_evidence=None,
                               freshness_policy_builder=None,
                               clock=None,
                               day_ledger=None,
                               day_ledger_provider=None,
                               ownership_snapshot=None, revision_before=None):
        """Consume one already-collected in-memory report through the formal gate.

        This method has no transport. ``collect_and_reconcile`` supplies a
        pre-collection ownership/revision fence for caller-injected bounded
        transports; direct callers may supply the same explicit fence.
        """
        if revision_before is not None and (type(revision_before) is not int or revision_before < 0):
            raise SupervisorUnavailable("invalid reconciliation revision fence")
        if (ownership_snapshot is not None
                and (not isinstance(ownership_snapshot, reconciliation_gate.OwnershipSnapshot)
                     or not ownership_snapshot.valid()
                     or ownership_snapshot.bot_id != self.bot_id)):
            raise SupervisorUnavailable("invalid reconciliation ownership fence")

        async with self._operation():
            if self.health != "RECONCILING":
                raise SupervisorUnavailable("formal reconciliation requires RECONCILING state")
            await self._flush_halts()
            entry_revision = await self._io(self._journal.current_revision, self.bot_id)
            current_snapshot = await self._io(self._journal.reconciliation_snapshot, self.bot_id)
            snapshot = current_snapshot if ownership_snapshot is None else ownership_snapshot
            if revision_before is None:
                revision_before = entry_revision
            try:
                report = account_report.build_report(
                    result, scope=scope, classifications=classifications,
                    expected_uid_sha256=self._expected_demo_uid_sha256,
                    **snapshot.report_attribution())
            except (ValueError, TypeError, AttributeError) as exc:
                raise SupervisorUnavailable("invalid formal reconciliation report") from exc

            # First remote posId bootstrap is deliberately separate from normal
            # attribution.  A raw posId alone is never ownership proof: bind it
            # only when durable local fills and the collected remote fills match
            # one-for-one and the pre-collection responsibility fence still holds.
            if (snapshot.local_position not in (None, Decimal("0"))
                    and not snapshot.owned_remote_position_ids
                    and current_snapshot.snapshot_digest == snapshot.snapshot_digest):
                lineage = await self._io(self._journal.position_bootstrap_lineage, self.bot_id)
                bootstrap = reconciliation_gate.build_position_identity_evidence(
                    report, result, snapshot, lineage) if lineage is not None else None
                if bootstrap is not None:
                    try:
                        snapshot = await self._io(
                            self._journal.bind_remote_position_identity, self.bot_id, bootstrap)
                    except OwnershipError:
                        snapshot = None
                    if snapshot is not None:
                        current_snapshot = snapshot
                        entry_revision = snapshot.bot_revision
                        revision_before = snapshot.bot_revision
                        try:
                            report = account_report.build_report(
                                result, scope=scope, classifications=classifications,
                                expected_uid_sha256=self._expected_demo_uid_sha256,
                                **snapshot.report_attribution())
                        except (ValueError, TypeError, AttributeError) as exc:
                            raise SupervisorUnavailable("invalid formal reconciliation report") from exc

            after_report = await self._io(self._journal.reconciliation_snapshot, self.bot_id)
            revision_after = await self._io(self._journal.current_revision, self.bot_id)
            responsibility_unchanged = (
                current_snapshot.snapshot_digest == snapshot.snapshot_digest
                and after_report.snapshot_digest == snapshot.snapshot_digest)
            if not responsibility_unchanged:
                revision_after = -1

            if day_ledger is None and day_ledger_provider is not None:
                day_flow_context = {
                    "day_external_flow_usdt": report.get("day_external_flow_usdt"),
                    "flow_classification_id": report.get("flow_classification_id"),
                    "unknown_flow_count": report.get("day_unknown_flow_count", 0),
                    "day_flow_start_ms": report.get("day_flow_start_ms"),
                    "day_flow_cutoff_ms": report.get("day_flow_cutoff_ms"),
                }
                import inspect
                try:
                    sig = inspect.signature(day_ledger_provider)
                    accepts_context = len(sig.parameters) >= 2
                except (ValueError, TypeError):
                    accepts_context = False

                try:
                    if accepts_context:
                        if inspect.iscoroutinefunction(day_ledger_provider):
                            day_ledger = await day_ledger_provider(scope.window_end_ms, day_flow_context)
                        else:
                            day_ledger = day_ledger_provider(scope.window_end_ms, day_flow_context)
                    else:
                        if inspect.iscoroutinefunction(day_ledger_provider):
                            day_ledger = await day_ledger_provider(scope.window_end_ms)
                        else:
                            day_ledger = day_ledger_provider(scope.window_end_ms)
                except Exception:
                    day_ledger = None

            def _resolve_freshness_policy():
                builder = freshness_policy_builder or (freshness_policy if callable(freshness_policy) else None)
                if builder is not None:
                    now_ms = clock.wall_ms() if clock is not None and hasattr(clock, "wall_ms") else (time.time_ns() // 1_000_000)
                    try:
                        return builder(now_ms)
                    except Exception:
                        return None
                return freshness_policy

            gate = reconciliation_gate.evaluate(
                report, snapshot, revision_before=revision_before, revision_after=revision_after,
                freshness_policy=_resolve_freshness_policy(),
                freshness_evidence=freshness_evidence,
                day_ledger=day_ledger)
            if not gate.reconciled:
                self._load(await self._io(self._journal.snapshot, self.bot_id))
                return gate

            # The pure gate may take nonzero CPU time. Re-read the durable fence
            # immediately before the Journal write instead of trusting its verdict.
            prewrite_revision = await self._io(self._journal.current_revision, self.bot_id)
            prewrite = await self._io(self._journal.reconciliation_snapshot, self.bot_id)
            if (prewrite_revision != gate.bot_revision
                    or prewrite.snapshot_digest != snapshot.snapshot_digest):
                gate = reconciliation_gate.evaluate(
                    report, snapshot, revision_before=revision_before, revision_after=-1,
                    freshness_policy=_resolve_freshness_policy(),
                    freshness_evidence=freshness_evidence,
                    day_ledger=day_ledger)
                self._load(await self._io(self._journal.snapshot, self.bot_id))
                return gate

            position = snapshot.local_position
            position_id = (snapshot.owned_remote_position_ids[0][1]
                           if position != 0 and len(snapshot.owned_remote_position_ids) == 1 else None)
            evidence = Reconciliation(
                gate.bot_revision, gate.evidence_id, position,
                snapshot.ordinary_open_count, snapshot.conditional_open_count,
                snapshot.unknown_count, True,
                self.bot_id if position != 0 else None, position_id)
            try:
                self._load(await self._io(self._journal.reconcile, self.bot_id, evidence))
            except OwnershipError:
                latest = await self._io(self._journal.reconciliation_snapshot, self.bot_id)
                self._load(await self._io(self._journal.snapshot, self.bot_id))
                if latest.snapshot_digest != snapshot.snapshot_digest:
                    return reconciliation_gate.evaluate(
                        report, snapshot, revision_before=revision_before, revision_after=-1,
                        freshness_policy=_resolve_freshness_policy(),
                        freshness_evidence=freshness_evidence,
                        day_ledger=day_ledger)
                raise
            return gate

    def _trusted_wall_ms(self):
        return (self._day_clock.wall_ms() if self._day_clock is not None
                else time.time_ns() // 1_000_000)

    def _trusted_day_context(self):
        return risk.DayContext.from_target_time_ms(self._trusted_wall_ms())

    async def commit_day_basis(self, basis, *, period_observation=None):
        async with self._operation():
            await self._flush_halts()
            day_context = self._trusted_day_context()
            if not isinstance(basis, risk.DayBasis) or basis.day != day_context.day:
                raise JournalError("day basis must match Supervisor trusted current Taipei day")
            gen_before = self._control_generation
            try:
                state = await self._io(
                    self._journal.commit_day_basis, basis, day_context, frozenset(self.halt_reasons), period_observation)
            except JournalError:
                raise
            except BaseException:
                if basis.source == risk.RISK_PERIOD_SOURCE:
                    # An ACK failure can follow a successful COMMIT. Read only to
                    # prevent stale shutdown state from erasing that basis/latches;
                    # the operation still fails and cannot authorize trading.
                    try:
                        stored = await self._io(self._journal.risk_state)
                        merged = replace(self.risk_state, basis=stored.basis,
                            basis_blocked_day=stored.basis_blocked_day,
                            basis_established_day=stored.basis_established_day,
                            epoch=max(self.risk_state.epoch, stored.epoch))
                        self._accept_risk(risk.halt(merged, stored.reasons))
                        self._risk_persisted = stored
                    except Exception:
                        pass  # Retain the original storage failure and closed gate.
                raise
            if self.risk_state is not None:
                merged = replace(self.risk_state, basis=state.basis, basis_blocked_day=state.basis_blocked_day,
                                 basis_established_day=state.basis_established_day,
                                 epoch=max(self.risk_state.epoch, state.epoch))
                self._accept_risk(merged)
            else:
                self._accept_risk(state)
            self._risk_persisted = state
            if self._control_generation != gen_before or self.risk_state != self._risk_persisted:
                await self._flush_halts()
            return self.risk_state

    async def prepare_risk_period(self, report, *, classifications, freshness_policy, freshness_evidence):
        """R1 local-sim only: qualify, durably establish, then reconcile."""
        from copy import deepcopy
        from catos import risk_period
        report = deepcopy(report)
        # Validate identity/equity even when a durable period already exists.
        observed, _ = risk_period.observation(report, self.account_id)
        context = self._trusted_day_context()
        if (freshness_policy.checked_at_ms != context.target_time_ms
                or risk.taipei_day(observed) != context.day):
            raise JournalError("period observation is not current")
        async with self._operation():
            await self._flush_halts()
            basis = await self.load_day_basis(context.day)
            if basis is None:
                candidate = risk_period.candidate(report, self.account_id)
                await self.commit_day_basis(candidate, period_observation=(
                    report, classifications, freshness_policy, freshness_evidence, self.bot_id))
                basis = await self.load_day_basis(context.day)
            if basis is None or self._trusted_day_context().day != basis.day:
                raise SupervisorUnavailable("period commit unavailable or day changed")
            projected, ledger = risk_period.project(report, basis, classifications)
            snapshot = await self._io(self._journal.reconciliation_snapshot, self.bot_id)
            policy = replace(freshness_policy, checked_at_ms=self._trusted_wall_ms())
            gate = reconciliation_gate.evaluate(projected, snapshot,
                revision_before=snapshot.bot_revision, revision_after=snapshot.bot_revision,
                freshness_policy=policy, freshness_evidence=freshness_evidence, day_ledger=ledger)
            if gate.reconciled:
                position_id = (snapshot.owned_remote_position_ids[0][1]
                    if snapshot.local_position != 0 and len(snapshot.owned_remote_position_ids) == 1 else None)
                proof = Reconciliation(snapshot.bot_revision, gate.evidence_id, snapshot.local_position,
                    snapshot.ordinary_open_count, snapshot.conditional_open_count, snapshot.unknown_count,
                    True, self.bot_id if snapshot.local_position != 0 else None, position_id)
                self._load(await self._io(self._journal.reconcile, self.bot_id, proof))
            else:
                self._degrade_risk()
            return projected, ledger, gate

    async def observe_risk_period(self, report, snapshot, **qualification):
        """Bind a synthetic risk observation to its durable period and bill window."""
        from catos import risk_period
        async with self._operation():
            projected, ledger, gate = await self.prepare_risk_period(report, **qualification)
            if not gate.reconciled:
                return projected, gate
            ownership = await self._io(self._journal.reconciliation_snapshot, self.bot_id)
            if snapshot.time_ms != self._trusted_wall_ms() or snapshot.position != ownership.local_position:
                self._degrade_risk()
                raise SupervisorUnavailable("risk observation differs from qualified account")
            value = risk_period.equity(projected)
            bound = replace(snapshot, equity=value, risk_equity=value, external_net=ledger.external_flow_usdt,
                basis=ledger.period_basis, flow_basis_id=ledger.baseline_evidence_id,
                flow_start_ms=projected["risk_period_start_ms"])
            self.observe_risk(bound)
            await self.persist_controls()
            return projected, gate

    async def block_day_basis(self, day):
        async with self._operation():
            await self._flush_halts()
            day_context = self._trusted_day_context()
            if type(day) is not int or day != day_context.day:
                raise JournalError("basis block must match Supervisor trusted current Taipei day")
            gen_before = self._control_generation
            state = await self._io(
                self._journal.block_day_basis, day, day_context, frozenset(self.halt_reasons))
            if self.risk_state is not None:
                merged = replace(self.risk_state, basis=state.basis, basis_blocked_day=state.basis_blocked_day, epoch=max(self.risk_state.epoch, state.epoch))
                self._accept_risk(merged)
            else:
                self._accept_risk(state)
            self._risk_persisted = state
            if self._control_generation != gen_before or self.risk_state != self._risk_persisted:
                await self._flush_halts()
            return self.risk_state

    async def load_day_basis(self, day):
        if self._closing or not self._started or self._journal is None or self.failure:
            raise SupervisorUnavailable(self.failure or "Supervisor not running")
        return await self._io(self._journal.load_day_basis, day)

    async def authorize_demo_trading(self, grant):
        """Install one explicit in-memory Demo entry grant after reconciliation.

        The grant is deliberately not persisted.  A restarted Supervisor must be
        reconciled and explicitly authorized again before increasing exposure.
        """
        if not self._require_demo_trade_grant:
            raise SupervisorUnavailable("Demo trade authorization mode is not enabled")
        if not isinstance(grant, trade_authorization.DemoTradeGrant):
            raise ipc.ProtocolError("DemoTradeGrant required")
        async with self._operation():
            if grant.authorization_id in self._demo_consumed_authorization_ids:
                raise SupervisorUnavailable("demo_trade_grant_consumed")
            generation = self._demo_grant_generation
            await self._flush_halts()
            stored = await self._io(self._journal.snapshot, self.bot_id)
            owner = stored["owner"]
            if self.health != "LOCAL_READY":
                raise SupervisorUnavailable("demo_trade_reconciliation_required")
            blocker = trade_authorization.entry_blocker(
                grant,
                now_ms=self._trusted_wall_ms(),
                account_id=self.account_id,
                bot_id=self.bot_id,
                inst_id=self.config.contract.inst_id,
                reconciliation_evidence_id=owner["evidence_id"],
                reconciled_revision=owner["reconciled_revision"],
            )
            if blocker is not None:
                raise SupervisorUnavailable(blocker)
            if self._closing or generation != self._demo_grant_generation:
                raise SupervisorUnavailable("demo_trade_grant_revoked_during_authorization")
            self._demo_trade_grant = grant
            return grant

    async def revoke_demo_trading(self):
        # Control input on the owning event loop: must work during writer I/O.
        self._demo_grant_generation += 1
        self._demo_trade_grant = None

    async def _demo_entry_authorization(self):
        if not self._require_demo_trade_grant:
            return None
        stored = await self._io(self._journal.snapshot, self.bot_id)
        owner = stored["owner"]
        if self.health != "LOCAL_READY":
            raise SupervisorUnavailable("demo_trade_reconciliation_required")
        blocker = trade_authorization.entry_blocker(
            self._demo_trade_grant,
            now_ms=self._trusted_wall_ms(),
            account_id=self.account_id,
            bot_id=self.bot_id,
            inst_id=self.config.contract.inst_id,
            reconciliation_evidence_id=owner["evidence_id"],
            reconciled_revision=owner["reconciled_revision"],
        )
        if blocker is not None:
            raise SupervisorUnavailable(blocker)
        authorization_id = self._demo_trade_grant.authorization_id
        if authorization_id in self._demo_consumed_authorization_ids:
            raise SupervisorUnavailable("demo_trade_grant_consumed")
        return authorization_id, self._demo_grant_generation

    def _demo_entry_handoff_blocker(self, request, authorization):
        """Revalidate one entry immediately before transport without awaiting."""
        if authorization is None:
            return "demo_trade_grant_required"
        authorization_id, generation = authorization
        grant = self._demo_trade_grant
        now_ms = self._trusted_wall_ms()
        if (generation != self._demo_grant_generation
                or not isinstance(grant, trade_authorization.DemoTradeGrant)
                or grant.authorization_id != authorization_id):
            return "demo_trade_grant_expired_or_changed"
        if authorization_id in self._demo_consumed_authorization_ids:
            return "demo_trade_grant_consumed"
        if now_ms < grant.starts_at_ms or now_ms > grant.entry_cutoff_ms:
            return "demo_trade_grant_expired_or_changed"
        state = self.risk_state
        snapshot = None if state is None else state.snapshot
        if (snapshot is None or now_ms < state.time_ms
                or not snapshot.time_ms <= now_ms < snapshot.valid_until_ms
                or state.epoch != request["epoch"]
                or state.seq != request["risk_seq"]
                or state.time_ms != request["risk_time"]):
            return "demo_trade_risk_snapshot_changed"
        quantity = Decimal(request["payload"]["sz"])
        notional = trade_authorization.entry_mark_notional(
            quantity, self.config.contract.base_per_contract, snapshot.mark)
        if notional > grant.max_entry_mark_notional_usdt:
            return "demo_trade_grant_limit_exceeded"
        return None

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
        await self._log_protection_alert()

    async def _log_protection_alert(self):
        state = await self._io(self._journal.protection.state, self.bot_id)
        if state['alert'] and state['alert'] != self._protection_alert:
            logging.getLogger('catos.protection').warning('Bot %s: %s', self.bot_id, state['alert'])
        self._protection_alert = state['alert']

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

    async def _submit_prepared(self, request, *, demo_entry_authorization=None):
        if request is None:
            await self._execution_sync()
            return None
        execution = self._execution()
        key = request["order_key"]
        await self._flush_halts()
        entry_request = request["payload"].get("reduceOnly") is not True
        if self._require_demo_trade_grant and entry_request:
            blocker = self._demo_entry_handoff_blocker(request, demo_entry_authorization)
            if blocker is not None:
                await self._io(execution.abort_unsent, key)
                await self._execution_sync()
                raise SupervisorUnavailable(blocker)
        entered = False
        handoff_blocker = None

        async def handoff():
            nonlocal entered, handoff_blocker
            if self._require_demo_trade_grant and entry_request:
                handoff_blocker = self._demo_entry_handoff_blocker(
                    request, demo_entry_authorization)
                if handoff_blocker is not None:
                    return None
            if (self._closing or self.risk_state.epoch != request["epoch"]
                    or self.risk_state.seq != request["risk_seq"]
                    or self.risk_state.time_ms != request["risk_time"]):
                return None
            if self._require_demo_trade_grant and entry_request:
                authorization_id = demo_entry_authorization[0]
                # No await between the final checks, one-shot consumption, and
                # entering transport. Any transport outcome keeps this tombstone.
                self._demo_consumed_authorization_ids.add(authorization_id)
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
                await self._execution_sync()
                if handoff_blocker is not None:
                    raise SupervisorUnavailable(handoff_blocker)
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
            reduce_only = await self._io(lambda: self._journal.connection.execute(
                "SELECT reduce_only FROM risk_orders WHERE intent_key=?", (intent_key,)).fetchone())
            demo_entry_authorization = None
            if reduce_only is not None and not bool(reduce_only[0]):
                demo_entry_authorization = await self._demo_entry_authorization()
            authorization_id = (None if demo_entry_authorization is None
                                else demo_entry_authorization[0])
            request = await self._io(
                execution.prepare, self.bot_id, intent_key, now_ms, authorization_id)
            return await self._submit_prepared(
                request, demo_entry_authorization=demo_entry_authorization)

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

    async def configure_protection(self, config):
        from catos.protection import Config
        if not isinstance(config, Config):
            raise ipc.ProtocolError('Supervisor protection config required')
        async with self._operation():
            self._execution()
            try:
                state = await self._io(self._journal.protection.configure, self.bot_id, config)
                await self._log_protection_alert()
                return state
            except ipc.ProtocolError as exc:
                raise SupervisorUnavailable(str(exc)) from exc

    async def protection_state(self):
        async with self._operation():
            return await self._io(self._journal.protection.state, self.bot_id)

    async def protection_step(self, *, now_ms):
        """One explicit FakeExchange step; no autonomous service or live transport."""
        async with self._operation():
            self._execution()
            p = self._journal.protection
            try:
                request = await self._io(p.prepare, self.bot_id, now_ms)
            except ipc.ProtocolError as exc:
                raise SupervisorUnavailable(str(exc)) from exc
            if request is not None:
                try:
                    report = await asyncio.wait_for(self._exchange.protection(
                        request['operation'], request['payload']), timeout=5)
                except (TimeoutError, OSError):
                    pass  # Durable pending/UNKNOWN already closes increases.
                else:
                    await self._io(p.apply, self.bot_id, report)
            await self._execution_sync()
            return await self._io(p.state, self.bot_id)

    async def set_loss_limits(self, *, soft_loss, hard_loss, actor, evidence_id):
        self._require_risk()
        limits = replace(self.risk_limits, soft_loss=soft_loss, hard_loss=hard_loss)
        ipc.token(actor, "operator")
        ipc.token(evidence_id, "configuration evidence")
        async with self._operation():
            await self._flush_halts()
            before = self.risk_state
            # New observations immediately use the new limits; tighter limits
            # close the in-memory gate even while the sole writer is waiting.
            self.risk_limits = limits
            self._accept_risk(risk.halt(replace(before, epoch=before.epoch + 1),
                                        risk.loss_reasons(before, limits)))
            updated = await self._io(self._journal.set_loss_limits, limits, before, actor, evidence_id)
            self._risk_persisted = updated
            await self._flush_halts()
            return self.risk_state

    async def rearm(self, *, now_ms, actor, evidence_id, manual_cause_cleared=False):
        self._require_risk()
        ipc.token(actor, "operator")
        ipc.token(evidence_id, "re-arm evidence")
        if type(manual_cause_cleared) is not bool:
            raise ipc.ProtocolError("manual cause confirmation must be bool")
        # Expected policy rejection is not a Supervisor fault.
        try:
            risk.rearm(self.risk_state, self.risk_limits, now_ms, reconciled=True,
                       manual_cause_cleared=manual_cause_cleared)
        except ipc.ProtocolError as exc:
            raise SupervisorUnavailable(str(exc)) from exc
        async with self._operation():
            await self._flush_halts()
            before, generation = self.risk_state, self._control_generation
            try:
                updated = await self._io(self._journal.rearm, self.bot_id, before, now_ms,
                                         actor, evidence_id, manual_cause_cleared)
            except ipc.ProtocolError as exc:
                raise SupervisorUnavailable(str(exc)) from exc
            if generation == self._control_generation:
                self.risk_state = updated
                self.halt_reasons = set(updated.reasons)
                self._persisted_halts = set(updated.reasons)
                self.epoch = max(self.epoch, updated.epoch)
                self._risk_persisted = updated
            else:
                # Even a repeated Kill or crossing-then-bounce during COMMIT
                # vetoes application of the recovery result to the local gate.
                self._accept_risk(replace(self.risk_state, epoch=max(self.risk_state.epoch, updated.epoch) + 1))
                self._risk_persisted = updated
                await self._flush_halts()
                raise SupervisorUnavailable("new control input superseded re-arm")
            return self.risk_state

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
        self._demo_grant_generation += 1
        self._demo_trade_grant = None
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
