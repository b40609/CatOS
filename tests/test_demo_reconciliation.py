"""Unit tests for the formal Demo reconciliation runner orchestration path.

Tests production wiring with synthetic transport and mocks:
- Synthetic full-pass orchestration
- Partial production catalog permits fully classified observed flows
- Missing E₀ baseline blocked (day_baseline_unverified)
- Main account scope mismatch blocked (scope_mismatch)
- F1 clock freshness violations (stale clock sample, batch >31s, invalid public_time)
- Clock advance after collection before gate check fails closed (fresh check-time semantics)
- Prewrite race re-evaluation evaluates freshness with fresh check time
- Strict Formal production plan contract validation (fail closed locally before network)
  - 48h window rejected
  - Enlarged requests, pages, timeout, runtime bounds rejected
  - Endpoints missing, extra, reordered rejected
  - Invalid account alias, environment, instrument rejected
- W1 window coverage failures (broken fill/bill pagination or missing window evidence)
- S1 non-sequential / overlapping source failures
- Foreign position, order, and algo responsibilities blocked
- Pre-collection ownership fence & revision race detection
- No Journal reconciliation write on gate failure
- Trade authorization remains False unconditionally
"""

from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from catos import (account_lock, account_report, demo_ledger_binding,
                   okx_collection as collection, okx_readonly)
from catos.demo_reconciliation import (
    FORMAL_ACCOUNT_ALIAS,
    FORMAL_DEMO_ENDPOINT_ALIASES,
    FORMAL_ENVIRONMENT,
    FORMAL_F1_POLICY_ID,
    FORMAL_INSTRUMENT,
    FORMAL_MAX_PAGES_PER_ENDPOINT,
    FORMAL_MAX_REQUESTS,
    FORMAL_MAX_RUNTIME_MS,
    FORMAL_REQUEST_TIMEOUT_MS,
    FORMAL_WINDOW_SPAN_MS,
    FormalLedgerBindingViolation,
    FormalPlanContractViolation,
    authorized_formal_scope,
    build_formal_collection_plan,
    derive_f1_freshness,
    run_formal_reconciliation,
    validate_formal_collection_plan,
)
from catos.journal import Journal
from catos.reconciliation_gate import DayLedgerEvidence, FreshnessEvidence, FreshnessPolicy
from catos.research import ContractSpec
from catos.supervisor import LocalSupervisor, SupervisorUnavailable
from test_ipc import STEP, ipc
from test_journal import proof


D = Decimal
SYNTHETIC_FLOW_CLASSIFICATION = okx_readonly.FlowClassification("synthetic-complete-flow", (), True)


def btc_config():
    return ipc.WorkerConfig(ContractSpec("BTC-USDT-SWAP", D("0.01"), D("0.01"), D("1"), D("1")), STEP, 2)


class FakeClock:
    def __init__(self, current_ms=1_700_000_000_000):
        self._current_ms = current_ms

    def wall_ms(self):
        return self._current_ms

    def monotonic_ms(self):
        return self._current_ms

    def advance(self, delta_ms):
        self._current_ms += delta_ms
        return self._current_ms


def base_formal_rows(inst_id="BTC-USDT-SWAP", server_ts="1700000001000"):
    return {
        "account_config": [dict(uid="123456789", mainUid="111111111", acctLv="2",
                                posMode="net_mode", roleType="0", perm="read_only")],
        "account_instruments": [dict(instType="SWAP", instId=inst_id, ctType="linear",
                                     settleCcy="USDT", ctValCcy="BTC", state="live",
                                     ctVal="1", ctMult="1", tickSz="0.1", lotSz="1", minSz="1")],
        "public_instruments": [dict(instType="SWAP", instId=inst_id, ctType="linear",
                                    settleCcy="USDT", ctValCcy="BTC", state="live",
                                    ctVal="1", ctMult="1", tickSz="0.1", lotSz="1", minSz="1")],
        "balance": [dict(totalEq="10000", adjEq="10000", uTime="1700000000500",
                         details=[dict(ccy="USDT", eq="10000", liab="0", availEq="10000",
                                       ordFrozen="0", uTime="1700000000500")])],
        "positions": [],
        "orders_pending": [],
        "algo_pending": [],
        "mark_price": [dict(instType="SWAP", instId=inst_id, markPx="65000", ts="1700000000800")],
        "orders_history": [],
        "fills": [],
        "bills": [],
        "algo_history": [],
        "public_time": [dict(ts=str(server_ts))],
    }


class SequentialSyntheticTransport:
    def __init__(self, rows, clock, *, hook=None, endpoint_delay_ms=100):
        self.rows = dict(rows)
        self.clock = clock
        self.hook = hook
        self.endpoint_delay_ms = endpoint_delay_ms
        self.call_history = []

    def fetch(self, request):
        if self.hook is not None:
            self.hook(request)
        alias = request.endpoint.alias
        self.call_history.append(alias)
        self.clock.advance(self.endpoint_delay_ms)
        now_ms = self.clock.wall_ms()

        # Update public_time dynamically to track current clock unless fixed
        if alias == "public_time" and callable(self.rows[alias]):
            payload_data = self.rows[alias](now_ms)
        elif alias == "public_time" and isinstance(self.rows[alias], list):
            payload_data = self.rows[alias]
        else:
            payload_data = self.rows.get(alias, [])

        window_evidence = None
        if alias in collection.WINDOWED_EVENT_ENDPOINTS:
            if alias == "orders_history":
                window_evidence = collection.WindowRequestEvidence(
                    request.scope.window_start_ms, request.scope.window_end_ms,
                    "cTime", "after_order_id")
            else:
                window_evidence = collection.WindowRequestEvidence(
                    request.scope.window_start_ms, request.scope.window_end_ms)

        payload = {"code": "0", "data": payload_data, "msg": ""}
        return collection.PageResponse(
            request.scope.account_alias,
            request.scope.environment,
            now_ms,
            payload,
            window_evidence=window_evidence,
        )


def taipei_day_start_ms(now_ms: int) -> int:
    taipei = timezone(timedelta(hours=8))
    dt = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).astimezone(taipei)
    day_start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(day_start.astimezone(timezone.utc).timestamp() * 1000)


def synthetic_day_ledger(now_ms=1_700_000_000_000, baseline="10000"):
    return DayLedgerEvidence(
        trading_day_start_ms=taipei_day_start_ms(now_ms),
        baseline_equity_usdt=D(baseline),
        baseline_evidence_id="ev_synthetic_baseline",
        external_flow_usdt=D("0"),
        flow_classification_id=SYNTHETIC_FLOW_CLASSIFICATION.classification_id,
        unknown_flow_count=0,
    )


class DemoReconciliationOrchestrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "state.sqlite3"
        lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)

        journal = Journal(self.path, FORMAL_ACCOUNT_ALIAS, D("100"))
        journal.register("bot", btc_config())
        journal.reconcile("bot", proof(0))
        journal.close()

        self.expected_uid_sha256 = demo_ledger_binding.uid_digest("123456789")
        self.ledger_binding = demo_ledger_binding.make_binding(
            account_alias=FORMAL_ACCOUNT_ALIAS,
            expected_uid_sha256=self.expected_uid_sha256,
            database_path=self.path,
        )

        self.clock = FakeClock(1_700_000_000_000)
        self.supervisor = LocalSupervisor(
            self.path, account_id=FORMAL_ACCOUNT_ALIAS, bot_id="bot", config=btc_config(),
            fixture_budget=D("100"),
            demo_ledger_binding_proof=self.ledger_binding,
            expected_demo_uid_sha256=self.expected_uid_sha256)
        self.addAsyncCleanup(self.supervisor.close)
        await self.supervisor.start()
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_missing_demo_ledger_binding_fails_before_collection(self):
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)
        unbound = LocalSupervisor(
            self.path, account_id=FORMAL_ACCOUNT_ALIAS, bot_id="bot", config=btc_config(),
            fixture_budget=D("100"))

        with self.assertRaisesRegex(FormalLedgerBindingViolation, "ledger_binding_missing_or_invalid"):
            await run_formal_reconciliation(
                unbound, transport, plan=build_formal_collection_plan(scope))
        self.assertEqual(transport.call_history, [])

    async def test_demo_ledger_binding_uid_mismatch_fails_before_collection(self):
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)
        mismatched = LocalSupervisor(
            self.path, account_id=FORMAL_ACCOUNT_ALIAS, bot_id="bot", config=btc_config(),
            fixture_budget=D("100"),
            demo_ledger_binding_proof=self.ledger_binding,
            expected_demo_uid_sha256=demo_ledger_binding.uid_digest("987654321"))

        with self.assertRaisesRegex(FormalLedgerBindingViolation, "ledger_binding_uid_mismatch"):
            await run_formal_reconciliation(
                mismatched, transport, plan=build_formal_collection_plan(scope))
        self.assertEqual(transport.call_history, [])

    async def owner(self):
        state = await self.supervisor._io(self.supervisor._journal.snapshot, "bot")
        return state["owner"]

    async def test_synthetic_formal_happy_path_orchestration_passes(self):
        """Full-pass wiring: synthetic complete classification, verified E₀, F1-compliant clock."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        self.assertEqual(plan.endpoint_aliases, FORMAL_DEMO_ENDPOINT_ALIASES)
        self.assertEqual(plan.endpoint_aliases[-1], "public_time")

        rows = base_formal_rows(inst_id="BTC-USDT-SWAP")
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        day_ledger = synthetic_day_ledger(self.clock.wall_ms())
        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=day_ledger,
            clock=self.clock,
        )

        self.assertTrue(gate.reconciled)
        self.assertFalse(gate.trade_authorized)
        self.assertEqual(gate.blockers, ())
        self.assertEqual(self.supervisor.health, "LOCAL_READY")

        owner = await self.owner()
        self.assertEqual(owner["reconciled_revision"], gate.bot_revision)
        self.assertEqual(owner["evidence_id"], gate.evidence_id)

    async def test_partial_production_catalog_allows_classified_observed_flows(self):
        """Unused catalog gaps do not block otherwise complete evidence."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        # Default classification in run_formal_reconciliation is OKX_DEMO_CATALOG_FLOW_CLASSIFICATION
        day_ledger = synthetic_day_ledger(self.clock.wall_ms())
        from dataclasses import replace
        day_ledger = replace(day_ledger, flow_classification_id=
            okx_readonly.OKX_DEMO_CATALOG_FLOW_CLASSIFICATION.classification_id)
        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            day_ledger=day_ledger,
            clock=self.clock,
        )

        self.assertTrue(gate.reconciled)
        self.assertFalse(gate.trade_authorized)
        self.assertEqual(gate.blockers, ())
        self.assertEqual(self.supervisor.health, "LOCAL_READY")
        self.assertEqual((await self.owner())["reconciled_revision"], gate.bot_revision)

    async def test_missing_day_ledger_evidence_blocks_with_day_baseline_unverified(self):
        """Missing verified E₀ must fail closed without inventing a baseline."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=None,
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("day_baseline_unverified", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")
        self.assertIsNone((await self.owner())["reconciled_revision"])

    async def test_day_ledger_provider_invoked_if_supplied(self):
        """DayLedgerEvidence provider function is invoked with window_end_ms."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        provider_calls = []
        def provider(end_ms):
            provider_calls.append(end_ms)
            return synthetic_day_ledger(self.clock.wall_ms())

        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger_provider=provider,
            clock=self.clock,
        )

        self.assertTrue(gate.reconciled)
        self.assertEqual(provider_calls, [scope.window_end_ms])

    async def test_main_account_config_fails_with_scope_mismatch_without_exception(self):
        """Formal runner does not suppress main account (uid == mainUid -> scope_mismatch)."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        # Main account returns uid == mainUid
        rows["account_config"] = [dict(uid="123456789", mainUid="123456789", acctLv="2",
                                       posMode="net_mode", roleType="0", perm="read_only")]
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("scope_mismatch", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")
        self.assertIsNone((await self.owner())["reconciled_revision"])

    async def test_other_subaccount_uid_fails_with_scope_mismatch(self):
        """A different valid subaccount must not satisfy the expected UID binding."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["account_config"] = [dict(uid="987654321", mainUid="111111111", acctLv="2",
                                       posMode="net_mode", roleType="0", perm="read_only")]
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("scope_mismatch", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")
        self.assertIsNone((await self.owner())["reconciled_revision"])

    async def test_stale_f1_clock_sample_age_exceeding_500ms_blocks(self):
        """Clock sample age > 500ms via FakeClock advance fails closed on snapshot_freshness_unverified."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        # Advance FakeClock by 501ms right after collection completes
        real_build_report = account_report.build_report
        def delay_hook(*args, **kwargs):
            self.clock.advance(501)
            return real_build_report(*args, **kwargs)

        with patch.object(account_report, "build_report", side_effect=delay_hook):
            gate = await run_formal_reconciliation(
                self.supervisor,
                transport,
                plan=plan,
                _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
                day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
                clock=self.clock,
            )

        self.assertFalse(gate.reconciled)
        self.assertIn("snapshot_freshness_unverified", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_checked_at_ms_override_rejected_and_delay_blocks_freshness(self):
        """Attempting to inject checked_at_ms override is rejected, and 600ms delay fails closed."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        # 1. Caller attempt to pass checked_at_ms is explicitly rejected (TypeError)
        with self.assertRaises(TypeError):
            await run_formal_reconciliation(
                self.supervisor,
                transport,
                plan=plan,
                _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
                day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
                clock=self.clock,
                checked_at_ms=self.clock.wall_ms() + 1300,
            )

        # 2. Even after collection completes and clock advances 600ms, gate strictly fails closed
        real_build_report = account_report.build_report
        def delay_hook(*args, **kwargs):
            self.clock.advance(600)
            return real_build_report(*args, **kwargs)

        with patch.object(account_report, "build_report", side_effect=delay_hook):
            gate = await run_formal_reconciliation(
                self.supervisor,
                transport,
                plan=plan,
                _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
                day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
                clock=self.clock,
            )

        self.assertFalse(gate.reconciled)
        self.assertIn("snapshot_freshness_unverified", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_clock_advance_after_collection_before_gate_blocks_freshness(self):
        """Clock advancing > 500ms between collection end and gate evaluate must fail closed."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        # Hook account_report.build_report to advance clock by 600ms right after collection
        # and before reconciliation_gate.evaluate() is called.
        real_build_report = account_report.build_report
        def build_report_with_delay(*args, **kwargs):
            self.clock.advance(600)
            return real_build_report(*args, **kwargs)

        day_ledger = synthetic_day_ledger(self.clock.wall_ms())
        with patch.object(account_report, "build_report", side_effect=build_report_with_delay):
            gate = await run_formal_reconciliation(
                self.supervisor,
                transport,
                plan=plan,
                _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
                day_ledger=day_ledger,
                clock=self.clock,
            )

        self.assertFalse(gate.reconciled)
        self.assertIn("snapshot_freshness_unverified", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")
        self.assertIsNone((await self.owner())["reconciled_revision"])

    async def test_prewrite_race_re_evaluates_with_fresh_check_time(self):
        """In prewrite race path, gate re-evaluates freshness with the fresh check time."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        real_current_revision = self.supervisor._journal.current_revision
        call_count = [0]
        def current_revision_hook(bot_id):
            call_count[0] += 1
            if call_count[0] >= 3:
                # 3rd call is prewrite_revision: advance clock by 600ms and bump revision to simulate race
                self.clock.advance(600)
                return 1
            return real_current_revision(bot_id)

        day_ledger = synthetic_day_ledger(self.clock.wall_ms())
        with patch.object(self.supervisor._journal, "current_revision", side_effect=current_revision_hook):
            gate = await run_formal_reconciliation(
                self.supervisor,
                transport,
                plan=plan,
                _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
                day_ledger=day_ledger,
                clock=self.clock,
            )

        self.assertFalse(gate.reconciled)
        self.assertIn("local_revision_changed", gate.blockers)
        self.assertIn("snapshot_freshness_unverified", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")
        self.assertIsNone((await self.owner())["reconciled_revision"])

    async def test_plan_48h_window_rejected(self):
        """48h window violates formal 24h contract and fails closed before collection."""
        scope = collection.RunScope(
            account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT,
            instrument=FORMAL_INSTRUMENT,
            window_start_ms=self.clock.wall_ms() - 2 * FORMAL_WINDOW_SPAN_MS,
            window_end_ms=self.clock.wall_ms(),
            max_requests=FORMAL_MAX_REQUESTS,
            max_pages_per_endpoint=FORMAL_MAX_PAGES_PER_ENDPOINT,
            request_timeout_ms=FORMAL_REQUEST_TIMEOUT_MS,
            max_runtime_ms=FORMAL_MAX_RUNTIME_MS,
        )
        plan = collection.CollectionPlan(scope, FORMAL_DEMO_ENDPOINT_ALIASES)
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)

        with self.assertRaises(FormalPlanContractViolation):
            await run_formal_reconciliation(self.supervisor, transport, plan=plan)
        self.assertEqual(len(transport.call_history), 0)

    async def test_plan_enlarged_requests_rejected(self):
        """max_requests=999 violates formal contract and fails closed before collection."""
        scope = collection.RunScope(
            account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT,
            instrument=FORMAL_INSTRUMENT,
            window_start_ms=self.clock.wall_ms() - FORMAL_WINDOW_SPAN_MS,
            window_end_ms=self.clock.wall_ms(),
            max_requests=999,
            max_pages_per_endpoint=FORMAL_MAX_PAGES_PER_ENDPOINT,
            request_timeout_ms=FORMAL_REQUEST_TIMEOUT_MS,
            max_runtime_ms=FORMAL_MAX_RUNTIME_MS,
        )
        plan = collection.CollectionPlan(scope, FORMAL_DEMO_ENDPOINT_ALIASES)
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)

        with self.assertRaises(FormalPlanContractViolation):
            await run_formal_reconciliation(self.supervisor, transport, plan=plan)
        self.assertEqual(len(transport.call_history), 0)

    async def test_plan_enlarged_pages_rejected(self):
        """max_pages_per_endpoint=99 violates formal contract and fails closed before collection."""
        scope = collection.RunScope(
            account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT,
            instrument=FORMAL_INSTRUMENT,
            window_start_ms=self.clock.wall_ms() - FORMAL_WINDOW_SPAN_MS,
            window_end_ms=self.clock.wall_ms(),
            max_requests=FORMAL_MAX_REQUESTS,
            max_pages_per_endpoint=99,
            request_timeout_ms=FORMAL_REQUEST_TIMEOUT_MS,
            max_runtime_ms=FORMAL_MAX_RUNTIME_MS,
        )
        plan = collection.CollectionPlan(scope, FORMAL_DEMO_ENDPOINT_ALIASES)
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)

        with self.assertRaises(FormalPlanContractViolation):
            await run_formal_reconciliation(self.supervisor, transport, plan=plan)
        self.assertEqual(len(transport.call_history), 0)

    async def test_plan_enlarged_timeout_rejected(self):
        """request_timeout_ms=20000 violates formal contract and fails closed before collection."""
        scope = collection.RunScope(
            account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT,
            instrument=FORMAL_INSTRUMENT,
            window_start_ms=self.clock.wall_ms() - FORMAL_WINDOW_SPAN_MS,
            window_end_ms=self.clock.wall_ms(),
            max_requests=FORMAL_MAX_REQUESTS,
            max_pages_per_endpoint=FORMAL_MAX_PAGES_PER_ENDPOINT,
            request_timeout_ms=20000,
            max_runtime_ms=FORMAL_MAX_RUNTIME_MS,
        )
        plan = collection.CollectionPlan(scope, FORMAL_DEMO_ENDPOINT_ALIASES)
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)

        with self.assertRaises(FormalPlanContractViolation):
            await run_formal_reconciliation(self.supervisor, transport, plan=plan)
        self.assertEqual(len(transport.call_history), 0)

    async def test_plan_enlarged_runtime_rejected(self):
        """max_runtime_ms=999999 violates formal contract and fails closed before collection."""
        scope = collection.RunScope(
            account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT,
            instrument=FORMAL_INSTRUMENT,
            window_start_ms=self.clock.wall_ms() - FORMAL_WINDOW_SPAN_MS,
            window_end_ms=self.clock.wall_ms(),
            max_requests=FORMAL_MAX_REQUESTS,
            max_pages_per_endpoint=FORMAL_MAX_PAGES_PER_ENDPOINT,
            request_timeout_ms=FORMAL_REQUEST_TIMEOUT_MS,
            max_runtime_ms=999999,
        )
        plan = collection.CollectionPlan(scope, FORMAL_DEMO_ENDPOINT_ALIASES)
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)

        with self.assertRaises(FormalPlanContractViolation):
            await run_formal_reconciliation(self.supervisor, transport, plan=plan)
        self.assertEqual(len(transport.call_history), 0)

    async def test_plan_endpoints_missing_rejected(self):
        """Missing endpoint violates 13 endpoint plan and fails closed before collection."""
        scope = authorized_formal_scope(self.clock.wall_ms() + FORMAL_WINDOW_SPAN_MS)
        plan = collection.CollectionPlan(scope, FORMAL_DEMO_ENDPOINT_ALIASES[:-1])
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)

        with self.assertRaises(FormalPlanContractViolation):
            await run_formal_reconciliation(self.supervisor, transport, plan=plan)
        self.assertEqual(len(transport.call_history), 0)

    async def test_plan_endpoints_extra_rejected(self):
        """Extra endpoint (e.g. fills_history) violates 13 endpoint plan and fails closed before collection."""
        scope = authorized_formal_scope(self.clock.wall_ms() + FORMAL_WINDOW_SPAN_MS)
        plan = collection.CollectionPlan(
            scope, FORMAL_DEMO_ENDPOINT_ALIASES[:10] + ("fills_history",) + FORMAL_DEMO_ENDPOINT_ALIASES[10:]
        )
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)

        with self.assertRaises(FormalPlanContractViolation):
            await run_formal_reconciliation(self.supervisor, transport, plan=plan)
        self.assertEqual(len(transport.call_history), 0)

    async def test_plan_endpoints_reordered_rejected(self):
        """Reordered endpoints violate formal sequence and fail closed before collection."""
        scope = authorized_formal_scope(self.clock.wall_ms() + FORMAL_WINDOW_SPAN_MS)
        reordered = list(FORMAL_DEMO_ENDPOINT_ALIASES)
        reordered[3], reordered[4] = reordered[4], reordered[3]
        plan = collection.CollectionPlan(scope, tuple(reordered))
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)

        with self.assertRaises(FormalPlanContractViolation):
            await run_formal_reconciliation(self.supervisor, transport, plan=plan)
        self.assertEqual(len(transport.call_history), 0)

    async def test_plan_invalid_account_alias_rejected(self):
        """Non-formal account_alias violates scope and fails closed before collection."""
        scope = collection.RunScope(
            account_alias="real-subaccount",
            environment=FORMAL_ENVIRONMENT,
            instrument=FORMAL_INSTRUMENT,
            window_start_ms=self.clock.wall_ms() - FORMAL_WINDOW_SPAN_MS,
            window_end_ms=self.clock.wall_ms(),
            max_requests=FORMAL_MAX_REQUESTS,
            max_pages_per_endpoint=FORMAL_MAX_PAGES_PER_ENDPOINT,
            request_timeout_ms=FORMAL_REQUEST_TIMEOUT_MS,
            max_runtime_ms=FORMAL_MAX_RUNTIME_MS,
        )
        plan = collection.CollectionPlan(scope, FORMAL_DEMO_ENDPOINT_ALIASES)
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)

        with self.assertRaises(FormalPlanContractViolation):
            await run_formal_reconciliation(self.supervisor, transport, plan=plan)
        self.assertEqual(len(transport.call_history), 0)

    async def test_plan_invalid_environment_rejected(self):
        """Non-demo environment violates scope and fails closed before collection."""
        scope = authorized_formal_scope(self.clock.wall_ms() + FORMAL_WINDOW_SPAN_MS)
        object.__setattr__(scope, "environment", "live")
        plan = collection.CollectionPlan(scope, FORMAL_DEMO_ENDPOINT_ALIASES)
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)

        with self.assertRaises(FormalPlanContractViolation):
            await run_formal_reconciliation(self.supervisor, transport, plan=plan)
        self.assertEqual(len(transport.call_history), 0)

    async def test_plan_invalid_instrument_rejected(self):
        """Non-formal instrument violates scope and fails closed before collection."""
        scope = collection.RunScope(
            account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT,
            instrument="ETH-USDT-SWAP",
            window_start_ms=self.clock.wall_ms() - FORMAL_WINDOW_SPAN_MS,
            window_end_ms=self.clock.wall_ms(),
            max_requests=FORMAL_MAX_REQUESTS,
            max_pages_per_endpoint=FORMAL_MAX_PAGES_PER_ENDPOINT,
            request_timeout_ms=FORMAL_REQUEST_TIMEOUT_MS,
            max_runtime_ms=FORMAL_MAX_RUNTIME_MS,
        )
        plan = collection.CollectionPlan(scope, FORMAL_DEMO_ENDPOINT_ALIASES)
        transport = SequentialSyntheticTransport(base_formal_rows(), self.clock)

        with self.assertRaises(FormalPlanContractViolation):
            await run_formal_reconciliation(self.supervisor, transport, plan=plan)
        self.assertEqual(len(transport.call_history), 0)

    async def test_batch_span_exceeding_31000ms_blocks(self):
        """Batch span > 31000ms must fail closed even if collection finishes within hard limit."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        # 13 endpoints * 2400ms = 31200ms (> 31000ms F1 bound)
        transport = SequentialSyntheticTransport(rows, self.clock, endpoint_delay_ms=2400)

        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("snapshot_freshness_unverified", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_missing_or_invalid_public_time_payload_blocks(self):
        """Corrupt public_time data provides no clock evidence and fails closed."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = [dict(ts="not_a_numeric_timestamp")]
        transport = SequentialSyntheticTransport(rows, self.clock)

        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("snapshot_freshness_unverified", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_incomplete_w1_fill_chain_blocks_window_coverage(self):
        """Missing window evidence for fills fails W1 verification."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]

        class BrokenWindowTransport(SequentialSyntheticTransport):
            def fetch(self, request):
                resp = super().fetch(request)
                if request.endpoint.alias == "fills":
                    # Omit window_evidence
                    return collection.PageResponse(
                        resp.account_alias, resp.environment, resp.source_ms,
                        resp.payload, window_evidence=None)
                return resp

        transport = BrokenWindowTransport(rows, self.clock)
        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("fill_window_coverage_unverified", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_incomplete_w1_bill_chain_blocks_window_coverage(self):
        """Missing window evidence for bills fails W1 verification."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]

        class BrokenBillTransport(SequentialSyntheticTransport):
            def fetch(self, request):
                resp = super().fetch(request)
                if request.endpoint.alias == "bills":
                    return collection.PageResponse(
                        resp.account_alias, resp.environment, resp.source_ms,
                        resp.payload, window_evidence=None)
                return resp

        transport = BrokenBillTransport(rows, self.clock)
        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("bill_window_coverage_unverified", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_s1_overlapping_sources_blocks_snapshot_freshness(self):
        """Overlapping or backward source timeline fails S1 verification."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]

        class OverlappingTransport(SequentialSyntheticTransport):
            def fetch(self, request):
                resp = super().fetch(request)
                if request.endpoint.alias == "positions":
                    # Step clock backwards to create timeline overlap
                    self.clock.advance(-300)
                    return collection.PageResponse(
                        resp.account_alias, resp.environment, self.clock.wall_ms(),
                        resp.payload, window_evidence=resp.window_evidence)
                return resp

        transport = OverlappingTransport(rows, self.clock)
        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("snapshot_freshness_unverified", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_foreign_position_blocks_without_adoption(self):
        """Unowned remote position fails closed with foreign_position."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["positions"] = [dict(instType="SWAP", instId="BTC-USDT-SWAP", posId="foreign_pos_1",
                                  mgnMode="cross", posSide="net", pos="1", avgPx="65000", uTime="150")]
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("foreign_position", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_foreign_order_blocks_without_adoption(self):
        """Unowned remote order fails closed with foreign_order."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["orders_pending"] = [dict(instType="SWAP", instId="BTC-USDT-SWAP", ordId="foreign_ord_1",
                                       tdMode="cross", posSide="net", side="buy", state="live",
                                       sz="1", accFillSz="0", uTime="150")]
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("foreign_order", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_foreign_algo_blocks_without_adoption(self):
        """Unowned remote algo order fails closed with foreign_algo."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["algo_pending"] = [dict(instType="SWAP", instId="BTC-USDT-SWAP", algoId="foreign_algo_1",
                                     state="live", tdMode="cross", posSide="net", side="sell",
                                     ordType="conditional", uTime="150", closeFraction="1",
                                     slTriggerPx="60000", slOrdPx="-1", slTriggerPxType="mark",
                                     reduceOnly="true", ordIdList=["dummy_ord"])]
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        transport = SequentialSyntheticTransport(rows, self.clock)

        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("foreign_algo", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_revision_race_during_collection_fails_closed(self):
        """Revision advancing during collection violates pre-collection fence."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]

        changed = []
        def race_hook(request):
            if changed:
                return
            if request.endpoint.alias == "fills":
                changed.append(True)
                with closing(sqlite3.connect(self.path)) as connection:
                    connection.execute("UPDATE bots SET revision=revision+1 WHERE bot_id='bot'")
                    connection.commit()

        transport = SequentialSyntheticTransport(rows, self.clock, hook=race_hook)
        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("local_revision_changed", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")

    async def test_responsibility_digest_race_during_collection_fails_closed(self):
        """Responsibility changing without revision bump during collection fails closed."""
        scope = authorized_formal_scope(self.clock.wall_ms() + 86400000)
        plan = build_formal_collection_plan(scope)
        rows = base_formal_rows()
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]

        changed = []
        def race_hook(request):
            if changed:
                return
            if request.endpoint.alias == "fills":
                changed.append(True)
                with closing(sqlite3.connect(self.path)) as connection:
                    connection.execute("""INSERT INTO execution_orders
                        (order_key,cl_ord_id,intent_key,bot_id,payload_json,quantity,filled,reservation,state,
                         cancel_pending,settled,deadline,epoch,exchange_id,report_revision,report_json)
                        VALUES ('race-order','client-race',NULL,'bot','{"reduceOnly":false}',
                                '1','0','0','LIVE',0,0,999999,0,'remote-race',0,NULL)""")
                    connection.commit()

        transport = SequentialSyntheticTransport(rows, self.clock, hook=race_hook)
        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=synthetic_day_ledger(self.clock.wall_ms()),
            clock=self.clock,
        )

        self.assertFalse(gate.reconciled)
        self.assertIn("local_revision_changed", gate.blockers)
        self.assertEqual(self.supervisor.health, "RECONCILING")


if __name__ == "__main__":
    unittest.main()
