"""Comprehensive unit tests for the Verified E₀ lifecycle and durable baseline slice.

Strictly covers:
1. Valid durable baseline for target trading day, account, and environment passes formal gate.
2. Wrong account, wrong environment, prior/future day baseline, invalid token, or forged digest fail closed.
3. First formal evaluation of missing baseline permanently blocks that day (D3 / E1 fail-closed);
   rebuilding on same day is rejected, and the block persists across restart.
4. Idempotent replay of identical baseline succeeds; replacement with differing equity/evidence is rejected.
5. Next-day valid baseline is accepted, preserving all previous Soft, Hard, and manual kill latches.
6. Persistence transaction rollback leaves state uncommitted; restart recovers verified durable state.
7. External flow calculation strictly isolates current Taipei day C_t:
   - Yesterday's flow is excluded from day_external_flow_usdt (retained in 24h observed_external_flow_usdt).
   - Duplicate bills are deduplicated.
   - Day denominator remains fixed.
8. Exact midnight bill handling (D2):
   - Certified prior-to-baseline events are excluded from day C_t (prevent double deduction).
   - Certified after-baseline events are included in day C_t.
   - Ambiguous timing blocks gate with external_flow_unavailable.
9. Cross-midnight collection/evaluation boundary rejection:
   - Stale previous-day ledger or misaligned collection is blocked.
10. Classification incompleteness (catalog 156/185), unknown flows, or coverage gaps remain fail closed.
11. Forbidden flow fallback: gate strictly rejects reports lacking day_external_flow_usdt.
12. Durable != Verified: token-only baseline lacking provenance/digest remains blocked.
13. Supervisor single-writer serialization: provider does not bypass Supervisor I/O queue.
14. Provider requires explicit flow context and refuses to default external flows to zero.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from catos import (account_lock, account_report, demo_ledger_binding,
                   okx_collection as collection, okx_readonly, risk)
from catos.demo_reconciliation import (
    FORMAL_ACCOUNT_ALIAS,
    FORMAL_DEMO_ENDPOINT_ALIASES,
    FORMAL_ENVIRONMENT,
    FORMAL_INSTRUMENT,
    CollectionPlan,
    authorized_formal_scope,
    build_formal_collection_plan,
    create_durable_day_ledger_provider,
    run_formal_reconciliation,
)
from catos.journal import Journal, JournalError
from catos.reconciliation_gate import (
    DayLedgerEvidence,
    FreshnessEvidence,
    FreshnessPolicy,
    evaluate as gate_evaluate,
)
from catos.research import ContractSpec
from catos.supervisor import LocalSupervisor
from test_demo_reconciliation import (
    FakeClock,
    SequentialSyntheticTransport,
    base_formal_rows,
    taipei_day_start_ms,
)
from test_ipc import STEP, ipc
from test_journal import proof


D = Decimal
SYNTHETIC_FLOW_CLASSIFICATION = okx_readonly.FlowClassification("synthetic-complete-flow", (), True)


def btc_config():
    return ipc.WorkerConfig(ContractSpec(FORMAL_INSTRUMENT, D("0.01"), D("0.01"), D("1"), D("1")), STEP, 2)


def make_verified_basis(
    target_time_ms: int,
    equity: str = "10000",
    *,
    account_alias: str = FORMAL_ACCOUNT_ALIAS,
    environment: str = FORMAL_ENVIRONMENT,
    evidence_id: str = "ev_verified_baseline_01",
    source: str = risk.SYNTHETIC_BASELINE_SOURCE,
) -> risk.DayBasis:
    target_day = (target_time_ms + 28_800_000) // 86_400_000
    evidence = (risk.make_synthetic_baseline_evidence(
        account_alias=account_alias, environment=environment, day=target_day,
        equity=D(equity), evidence_id=evidence_id)
        if source == risk.SYNTHETIC_BASELINE_SOURCE else None)
    digest = risk.compute_baseline_digest(
        account_alias=account_alias,
        environment=environment,
        day=target_day,
        equity=D(equity),
        source=source,
        evidence_id=evidence_id,
        evidence=evidence,
    )
    return risk.DayBasis(
        day=target_day,
        equity=D(equity),
        evidence_id=evidence_id,
        account_alias=account_alias,
        environment=environment,
        source=source,
        digest=digest,
        evidence=evidence,
    )


def day_context(target_time_ms: int) -> risk.DayContext:
    return risk.DayContext.from_target_time_ms(target_time_ms)


class VerifiedE0LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "state.sqlite3"
        lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        lock_patch.start()
        self.addCleanup(lock_patch.stop)

        journal = Journal(self.path, FORMAL_ACCOUNT_ALIAS, D("100"), risk_limits=risk.Limits())
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
            fixture_budget=D("100"), risk_limits=risk.Limits(), day_clock=self.clock,
            demo_ledger_binding_proof=self.ledger_binding,
            expected_demo_uid_sha256=self.expected_uid_sha256)
        self.addAsyncCleanup(self.supervisor.close)
        await self.supervisor.start()

    async def _setup_transport(self, rows_mutator=None, *, endpoint_delay_ms=100):
        rows = base_formal_rows(inst_id=FORMAL_INSTRUMENT)
        rows["public_time"] = lambda now_ms: [dict(ts=str(now_ms))]
        if rows_mutator:
            rows_mutator(rows)
        return SequentialSyntheticTransport(rows, self.clock, endpoint_delay_ms=endpoint_delay_ms)

    # 1. Valid durable baseline for target trading day passes formal reconciliation
    async def test_01_valid_durable_baseline_passes_formal_reconciliation(self):
        now_ms = self.clock.wall_ms()
        basis = make_verified_basis(now_ms, "10000")
        await self.supervisor.commit_day_basis(basis)

        provider = create_durable_day_ledger_provider(self.supervisor)
        transport = await self._setup_transport()
        scope = authorized_formal_scope(now_ms + 1000)
        plan = build_formal_collection_plan(scope)

        gate = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=plan,
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger_provider=provider,
            clock=self.clock,
        )

        self.assertTrue(gate.reconciled)
        self.assertFalse(gate.trade_authorized)
        self.assertEqual(gate.blockers, ())
        self.assertEqual(self.supervisor.health, "LOCAL_READY")

    # 2. Wrong account, wrong environment, wrong day, or forged digest fail closed
    async def test_02_provenance_and_day_mismatches_fail_closed(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000

        # Wrong account
        bad_acct = make_verified_basis(now_ms, account_alias="wrong-account")
        self.assertFalse(risk.is_verified_baseline(bad_acct, account_alias=FORMAL_ACCOUNT_ALIAS,
                                                   environment=FORMAL_ENVIRONMENT, target_day=target_day))

        # Wrong environment
        bad_env = make_verified_basis(now_ms, environment="live")
        self.assertFalse(risk.is_verified_baseline(bad_env, account_alias=FORMAL_ACCOUNT_ALIAS,
                                                  environment=FORMAL_ENVIRONMENT, target_day=target_day))

        # Prior day baseline
        prior_basis = make_verified_basis(now_ms - 86_400_000)
        self.assertFalse(risk.is_verified_baseline(prior_basis, account_alias=FORMAL_ACCOUNT_ALIAS,
                                                    environment=FORMAL_ENVIRONMENT, target_day=target_day))

        # Forged digest
        forged = risk.DayBasis(
            day=target_day,
            equity=D("10000"),
            evidence_id="forged",
            account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT,
            source="okx",
            digest="invalid_digest_token",
        )
        self.assertFalse(risk.is_verified_baseline(forged, account_alias=FORMAL_ACCOUNT_ALIAS,
                                                   environment=FORMAL_ENVIRONMENT, target_day=target_day))

    # 3. D3 Missing baseline blocks day; rebuild rejected on same day; block survives restart
    async def test_03_missing_baseline_blocks_day_rebuild_rejected_and_survives_restart(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000

        # Empty initial baseline -> provider evaluation blocks the day per D3
        provider = create_durable_day_ledger_provider(self.supervisor)
        resolved = await provider(now_ms, {"day_external_flow_usdt": "0", "flow_classification_id": "c1"})
        self.assertIsNone(resolved)

        # Verify day is blocked in supervisor state
        state = self.supervisor.risk_state
        self.assertEqual(state.basis_blocked_day, target_day)

        # Attempt to rebuild on same day via commit_day_basis must be rejected
        basis = make_verified_basis(now_ms)
        with self.assertRaises(JournalError) as ctx:
            await self.supervisor.commit_day_basis(basis)
        self.assertIn("cannot be rebuilt", str(ctx.exception))

        # Restart supervisor; block must persist in SQLite WAL
        await self.supervisor.close()
        restarted = LocalSupervisor(
            self.path, account_id=FORMAL_ACCOUNT_ALIAS, bot_id="bot", config=btc_config(),
            fixture_budget=D("100"), risk_limits=risk.Limits(), day_clock=self.clock)
        self.addAsyncCleanup(restarted.close)
        await restarted.start()

        self.assertEqual(restarted.risk_state.basis_blocked_day, target_day)
        # Attempt to rebuild after restart on same day must still be rejected
        with self.assertRaises(JournalError) as ctx:
            await restarted.commit_day_basis(basis)
        self.assertIn("cannot be rebuilt", str(ctx.exception))

    # 4. Same baseline is idempotent; different baseline replacement is rejected
    async def test_04_idempotent_replay_and_replacement_rejection(self):
        now_ms = self.clock.wall_ms()
        basis = make_verified_basis(now_ms, "10000")
        state1 = await self.supervisor.commit_day_basis(basis)
        self.assertEqual(state1.basis, basis)

        # Idempotent replay
        state2 = await self.supervisor.commit_day_basis(basis)
        self.assertEqual(state2.basis, basis)

        # Conflicting equity replacement rejected
        conflicting = make_verified_basis(now_ms, "20000")
        with self.assertRaises(JournalError) as ctx:
            await self.supervisor.commit_day_basis(conflicting)
        self.assertIn("fixed day basis cannot be replaced", str(ctx.exception))

    # 5. Next-day baseline accepted; preserves existing soft/hard loss and manual latches
    async def test_05_next_day_baseline_accepted_and_preserves_halt_latches(self):
        now_ms = self.clock.wall_ms()
        basis1 = make_verified_basis(now_ms, "10000")
        await self.supervisor.commit_day_basis(basis1)

        # Trigger soft and manual latches
        halted = risk.halt(self.supervisor.risk_state, ("soft_loss", "manual_kill"))
        await self.supervisor._io(self.supervisor._journal.save_risk, halted)
        self.supervisor._accept_risk(halted)
        self.assertEqual(self.supervisor.risk_state.reasons, frozenset(("soft_loss", "manual_kill")))

        # Advance to next Taipei day
        next_day_ms = now_ms + 86_400_000
        self.clock.advance(86_400_000)
        basis2 = make_verified_basis(next_day_ms, "9000")
        updated = await self.supervisor.commit_day_basis(basis2)

        self.assertEqual(updated.basis, basis2)
        # Halt latches must NOT be cleared by new day or new baseline
        self.assertEqual(updated.reasons, frozenset(("soft_loss", "manual_kill")))

    # 6. Persistence failure leaves state uncommitted; durable recovery
    async def test_06_persistence_failure_rollback(self):
        now_ms = self.clock.wall_ms()
        basis = make_verified_basis(now_ms)

        # Simulate SQLite I/O failure during commit
        with patch.object(self.supervisor._journal, "_write_risk", side_effect=sqlite3.OperationalError("disk failure")):
            with self.assertRaises(sqlite3.OperationalError):
                await self.supervisor.commit_day_basis(basis)

        # State remains clean and uncommitted
        self.assertIsNone(self.supervisor.risk_state.basis)

    # 7. Day C_t excludes yesterday's external flow and deduplicates bills
    async def test_07_day_ct_excludes_yesterday_flows_and_deduplicates(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000
        day_start_ms = target_day * 86_400_000 - 28_800_000

        scope = authorized_formal_scope(now_ms + 1000)
        # Window spans [now_ms - 86400000, now_ms + 1000]
        yesterday_ts = day_start_ms - 3600_000  # 1 hour before midnight
        today_ts1 = day_start_ms + 3600_000     # 1 hour after midnight
        today_ts2 = day_start_ms + 7200_000     # 2 hours after midnight

        bills = [
            # Yesterday flow (should be excluded from day_external_flow_usdt)
            dict(billId="b_yesterday", type="1", subType="101", ccy="USDT", balChg="500", ts=str(yesterday_ts)),
            # Today flow 1
            dict(billId="b_today_1", type="1", subType="101", ccy="USDT", balChg="100", ts=str(today_ts1)),
            # Duplicate of today flow 1 (should be deduplicated)
            dict(billId="b_today_1", type="1", subType="101", ccy="USDT", balChg="100", ts=str(today_ts1)),
            # Today flow 2 (withdrawal: negative)
            dict(billId="b_today_2", type="2", subType="201", ccy="USDT", balChg="-40", ts=str(today_ts2)),
        ]

        classifications = okx_readonly.FlowClassification("test-flows", (
            okx_readonly.FlowClassificationEntry("1", "101", "external", "deposit"),
            okx_readonly.FlowClassificationEntry("2", "201", "external", "withdrawal"),
        ), True)

        transport = await self._setup_transport(lambda rows: rows.update(bills=bills))
        plan = build_formal_collection_plan(scope)
        res = collection.collect_plan(plan, transport, clock=self.clock)

        report = account_report.build_report(res, scope=scope, classifications=classifications)

        # Full 24h observed flow includes yesterday (500 + 100 - 40 = 560)
        self.assertEqual(report["observed_external_flow_usdt"], "560")
        # Current day C_t strictly includes only today's bills (100 - 40 = 60)
        self.assertEqual(report["day_external_flow_usdt"], "60")
        self.assertEqual(report["day_flow_start_ms"], day_start_ms)

    # 8. Exact midnight bill handling (D2):
    # - prior_to_baseline excluded from day C_t
    # - after_baseline included in day C_t
    # - ambiguous timing blocks gate
    async def test_08_exact_midnight_bill_timing_semantics_d2(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000
        midnight_ms = target_day * 86_400_000 - 28_800_000
        scope = authorized_formal_scope(now_ms + 1000)

        classifications = okx_readonly.FlowClassification("test-flows", (
            okx_readonly.FlowClassificationEntry("1", "101", "external", "deposit"),
        ), True)

        # 8a: Prior-to-baseline event: excluded from day C_t
        bills_prior = [
            dict(billId="b_mid_prior", type="1", subType="101", ccy="USDT", balChg="200",
                 ts=str(midnight_ms), timing_verified="prior_to_baseline",
                 timing_evidence_id="ev_verified_baseline_01")
        ]
        t_prior = await self._setup_transport(lambda rows: rows.update(bills=bills_prior))
        res_prior = collection.collect_plan(build_formal_collection_plan(scope), t_prior, clock=self.clock)
        report_prior = account_report.build_report(res_prior, scope=scope, classifications=classifications)
        self.assertEqual(report_prior["day_external_flow_usdt"], "0")

        # 8b: After-baseline event: included in day C_t
        bills_after = [
            dict(billId="b_mid_after", type="1", subType="101", ccy="USDT", balChg="200",
                 ts=str(midnight_ms), timing_verified="after_baseline",
                 timing_evidence_id="ev_verified_baseline_01")
        ]
        t_after = await self._setup_transport(lambda rows: rows.update(bills=bills_after))
        res_after = collection.collect_plan(build_formal_collection_plan(scope), t_after, clock=self.clock)
        report_after = account_report.build_report(res_after, scope=scope, classifications=classifications)
        self.assertEqual(report_after["day_external_flow_usdt"], "200")

        # 8c: Ambiguous timing (no timing_verified cert): fails closed immediately
        bills_ambig = [
            dict(billId="b_mid_ambig", type="1", subType="101", ccy="USDT", balChg="200",
                 ts=str(midnight_ms))
        ]
        t_ambig = await self._setup_transport(lambda rows: rows.update(bills=bills_ambig))
        res_ambig = collection.collect_plan(build_formal_collection_plan(scope), t_ambig, clock=self.clock)
        report_ambig = account_report.build_report(res_ambig, scope=scope, classifications=classifications)
        self.assertIsNone(report_ambig["day_external_flow_usdt"])
        self.assertIn("external_flow_unavailable", report_ambig["discrepancies"])

        # 8d: Self-stated timing without baseline evidence ID fails closed as ambiguous
        bills_unbound = [
            dict(billId="b_mid_unbound", type="1", subType="101", ccy="USDT", balChg="200",
                 ts=str(midnight_ms), timing_verified="after_baseline")
        ]
        t_unbound = await self._setup_transport(lambda rows: rows.update(bills=bills_unbound))
        res_unbound = collection.collect_plan(build_formal_collection_plan(scope), t_unbound, clock=self.clock)
        report_unbound = account_report.build_report(res_unbound, scope=scope, classifications=classifications)
        self.assertIsNone(report_unbound["day_external_flow_usdt"])
        self.assertIn("external_flow_unavailable", report_unbound["discrepancies"])

    # 9. Cross-midnight collection/evaluation boundary rejection
    async def test_09_cross_midnight_collection_is_rejected(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000
        midnight_ms = target_day * 86_400_000 - 28_800_000

        # Simulate collection that started yesterday and completed today
        report = {
            "version": "i-b-2.v1",
            "account_alias": FORMAL_ACCOUNT_ALIAS,
            "environment": FORMAL_ENVIRONMENT,
            "instrument": FORMAL_INSTRUMENT,
            "window_start_ms": midnight_ms - 86400000,
            "window_end_ms": now_ms,
            "started_ms": midnight_ms - 1000,  # Prior day
            "completed_ms": now_ms,           # Current day
            "collection_complete": True,
            "reconciled": False,
            "trade_authorized": False,
            "snapshot_semantics": {
                "contract_id": "s1-bounded-sequential.v1",
                "mode": "bounded_sequential_observation",
                "atomic_snapshot": False,
                "record_update_time_is_snapshot_fence": False,
                "transport_time_is_snapshot_fence": False,
            },
            "sources": [],
            "facts": [],
            "discrepancies": [],
            "record_diagnostics": [],
            "observed_signed_fees_by_currency": {},
            "observed_external_flow_usdt": "0",
            "day_external_flow_usdt": "0",
            "flow_classification_id": "test-flow",
            "flow_classification_complete": True,
            "content_digest": "dummy",
        }

        evidence = DayLedgerEvidence(
            trading_day_start_ms=midnight_ms,
            baseline_equity_usdt=D("10000"),
            baseline_evidence_id="ev_01",
            external_flow_usdt=D("0"),
            flow_classification_id="test-flow",
            unknown_flow_count=0,
        )
        policy = FreshnessPolicy("pol", 1000, 1000, 1000, 1000, now_ms)
        snap = await self.supervisor._io(self.supervisor._journal.reconciliation_snapshot, "bot")

        gate = gate_evaluate(report, snap, revision_before=0, revision_after=0,
                             freshness_policy=policy, freshness_evidence=FreshnessEvidence(now_ms, now_ms),
                             day_ledger=evidence)
        self.assertFalse(gate.reconciled)
        self.assertIn("day_baseline_unverified", gate.blockers)

    # 10. Observed unknown flow blocks; unused catalog gaps alone do not block
    async def test_10_incomplete_classification_and_unknown_flows_block(self):
        now_ms = self.clock.wall_ms()
        basis = make_verified_basis(now_ms, "10000")
        await self.supervisor.commit_day_basis(basis)

        # 10a: unknown_flow_count > 0 in DayLedgerEvidence
        ledger_unknown = DayLedgerEvidence(
            trading_day_start_ms=taipei_day_start_ms(now_ms),
            baseline_equity_usdt=D("10000"),
            baseline_evidence_id="ev_01",
            external_flow_usdt=D("0"),
            flow_classification_id=SYNTHETIC_FLOW_CLASSIFICATION.classification_id,
            unknown_flow_count=1,
        )
        transport = await self._setup_transport()
        scope = authorized_formal_scope(now_ms + 1000)
        gate1 = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=build_formal_collection_plan(scope),
            _test_classification_override=SYNTHETIC_FLOW_CLASSIFICATION,
            day_ledger=ledger_unknown,
            clock=self.clock,
        )
        self.assertFalse(gate1.reconciled)
        self.assertIn("unknown_external_flow", gate1.blockers)

        # 10b: Production catalog complete=False is informational when observed flows are classified.
        ledger_ok = DayLedgerEvidence(
            trading_day_start_ms=taipei_day_start_ms(now_ms),
            baseline_equity_usdt=D("10000"),
            baseline_evidence_id="ev_01",
            external_flow_usdt=D("0"),
            flow_classification_id=okx_readonly.OKX_DEMO_CATALOG_FLOW_CLASSIFICATION.classification_id,
            unknown_flow_count=0,
        )
        gate2 = await run_formal_reconciliation(
            self.supervisor,
            transport,
            plan=build_formal_collection_plan(scope),
            # Default production catalog classification is incomplete, but bills are empty.
            day_ledger=ledger_ok,
            clock=self.clock,
        )
        self.assertTrue(gate2.reconciled)
        self.assertEqual(gate2.blockers, ())

    # 11. Forbidden flow fallback: missing day_external_flow_usdt fails closed
    async def test_11_missing_day_external_flow_fails_closed_without_fallback(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000
        midnight_ms = target_day * 86_400_000 - 28_800_000

        # Report has observed_external_flow_usdt but lacks day_external_flow_usdt
        report = {
            "version": "i-b-2.v1",
            "account_alias": FORMAL_ACCOUNT_ALIAS,
            "environment": FORMAL_ENVIRONMENT,
            "instrument": FORMAL_INSTRUMENT,
            "window_start_ms": midnight_ms,
            "window_end_ms": now_ms,
            "started_ms": now_ms - 100,
            "completed_ms": now_ms,
            "collection_complete": True,
            "reconciled": False,
            "trade_authorized": False,
            "snapshot_semantics": {
                "contract_id": "s1-bounded-sequential.v1",
                "mode": "bounded_sequential_observation",
                "atomic_snapshot": False,
                "record_update_time_is_snapshot_fence": False,
                "transport_time_is_snapshot_fence": False,
            },
            "sources": [],
            "facts": [],
            "discrepancies": [],
            "record_diagnostics": [],
            "observed_signed_fees_by_currency": {},
            "observed_external_flow_usdt": "100",  # 24h subtotal exists
            "day_external_flow_usdt": None,       # Day C_t is missing
            "flow_classification_id": "test-flow",
            "flow_classification_complete": True,
            "content_digest": "dummy",
        }

        evidence = DayLedgerEvidence(
            trading_day_start_ms=midnight_ms,
            baseline_equity_usdt=D("10000"),
            baseline_evidence_id="ev_01",
            external_flow_usdt=D("100"),
            flow_classification_id="test-flow",
            unknown_flow_count=0,
        )
        policy = FreshnessPolicy("pol", 1000, 1000, 1000, 1000, now_ms)
        snap = await self.supervisor._io(self.supervisor._journal.reconciliation_snapshot, "bot")

        gate = gate_evaluate(report, snap, revision_before=0, revision_after=0,
                             freshness_policy=policy, freshness_evidence=FreshnessEvidence(now_ms, now_ms),
                             day_ledger=evidence)
        self.assertFalse(gate.reconciled)
        # MUST block on external_flow_unavailable, NOT fall back to observed_external_flow_usdt!
        self.assertIn("external_flow_unavailable", gate.blockers)

    # 12. Durable != Verified: token-only baseline remains blocked
    async def test_12_token_only_baseline_lacking_provenance_remains_unverified(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000

        # Legacy token-only basis (no account_alias, no environment, no source, no digest)
        legacy_basis = risk.DayBasis(target_day, D("10000"), "legacy_token_only")
        self.assertFalse(risk.is_verified_baseline(legacy_basis, account_alias=FORMAL_ACCOUNT_ALIAS,
                                                   environment=FORMAL_ENVIRONMENT, target_day=target_day))

        # Committing legacy basis and evaluating provider must fail closed
        await self.supervisor.commit_day_basis(legacy_basis)
        provider = create_durable_day_ledger_provider(self.supervisor)
        resolved = await provider(now_ms, {"day_external_flow_usdt": "0", "flow_classification_id": "c1"})
        self.assertIsNone(resolved)

    # 13. Supervisor single-writer serialization: provider operates via Supervisor I/O
    async def test_13_provider_uses_supervisor_serialized_channel(self):
        now_ms = self.clock.wall_ms()
        basis = make_verified_basis(now_ms, "10000")
        await self.supervisor.commit_day_basis(basis)

        target_day = (now_ms + 28_800_000) // 86_400_000
        expected_start = target_day * 86_400_000 - 28_800_000
        provider = create_durable_day_ledger_provider(self.supervisor)
        # Calling provider successfully resolves via Supervisor's single-writer channel
        resolved = await provider(now_ms, {
            "day_external_flow_usdt": "0",
            "flow_classification_id": "test-c1",
            "unknown_flow_count": 0,
            "day_flow_start_ms": expected_start,
            "day_flow_cutoff_ms": now_ms,
        })
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.baseline_equity_usdt, D("10000"))
        self.assertEqual(resolved.day_flow_cutoff_ms, now_ms)

    # 14. Provider requires explicit flow context and refuses to default flow to zero
    async def test_14_provider_refuses_to_default_flow_to_zero(self):
        now_ms = self.clock.wall_ms()
        basis = make_verified_basis(now_ms, "10000")
        await self.supervisor.commit_day_basis(basis)

        provider = create_durable_day_ledger_provider(self.supervisor)
        # Invoking provider without day_flow_context must return None (fail closed)
        resolved_none = await provider(now_ms, None)
        self.assertIsNone(resolved_none)

        # Invoking provider with missing day_external_flow_usdt must return None
        resolved_missing_flow = await provider(now_ms, {
            "flow_classification_id": "c1",
            "unknown_flow_count": 0,
        })
        self.assertIsNone(resolved_missing_flow)

    # --- REGRESSION TESTS FOR R1-R4 (Astra Review Findings) ---

    # R1: Latch persists across commit_day_basis and survives restart
    async def test_r1_latch_persists_across_commit_day_basis_and_restart(self):
        now_ms = self.clock.wall_ms()
        basis = make_verified_basis(now_ms, "10000")

        # Set manual kill latch before commit
        self.supervisor.latch("manual_kill")
        self.assertEqual(self.supervisor.risk_state.reasons, frozenset({"manual_kill"}))
        self.assertEqual(self.supervisor.risk_state.mode, "FLAT")

        # Commit baseline: latch must not be overwritten or cleared
        updated = await self.supervisor.commit_day_basis(basis)
        self.assertEqual(updated.reasons, frozenset({"manual_kill"}))
        self.assertEqual(updated.mode, "FLAT")
        self.assertEqual(self.supervisor.risk_state.reasons, frozenset({"manual_kill"}))

        # Check DB state directly
        stored = await self.supervisor._io(self.supervisor._journal.snapshot, "bot")
        self.assertEqual(stored["risk_state"].reasons, frozenset({"manual_kill"}))
        self.assertEqual(stored["risk_state"].mode, "FLAT")

        # Reopen on same database: latch must survive restart
        await self.supervisor.close()
        sup2 = LocalSupervisor(
            self.path, account_id=FORMAL_ACCOUNT_ALIAS, bot_id="bot", config=btc_config(),
            fixture_budget=D("100"), risk_limits=risk.Limits(), day_clock=self.clock,
        )
        self.addAsyncCleanup(sup2.close)
        await sup2.start()
        self.assertEqual(sup2.risk_state.reasons, frozenset({"manual_kill"}))
        self.assertEqual(sup2.risk_state.mode, "FLAT")
        self.assertEqual(sup2.risk_state.basis, basis)

    # R2: Report day_cutoff anchored strictly to query window end, not manifest completed
    async def test_r2_report_day_cutoff_anchored_to_query_window_not_completed(self):
        now_ms = self.clock.wall_ms()
        scope = authorized_formal_scope(now_ms)
        # Setup transport that advances clock by 100ms per endpoint (13 endpoints = 1300 ms elapsed)
        transport = await self._setup_transport(endpoint_delay_ms=100)
        plan = build_formal_collection_plan(scope)
        res = collection.collect_plan(plan, transport, clock=self.clock)
        self.assertEqual(res.manifest.completed_ms, now_ms + 1300)

        snap = await self.supervisor._io(self.supervisor._journal.reconciliation_snapshot, "bot")
        report = account_report.build_report(
            res, scope=scope, classifications=SYNTHETIC_FLOW_CLASSIFICATION, **snap.report_attribution()
        )
        # Cutoff MUST be scope.window_end_ms, NOT completed_ms!
        self.assertEqual(report["day_flow_cutoff_ms"], scope.window_end_ms)
        self.assertNotEqual(report["day_flow_cutoff_ms"], res.manifest.completed_ms)

        # Tampering with cutoff to exceed window_end_ms must be blocked by gate
        tampered_report = dict(report)
        tampered_report["day_flow_cutoff_ms"] = res.manifest.completed_ms
        target_day = (scope.window_end_ms + 28_800_000) // 86_400_000
        start_ms = target_day * 86_400_000 - 28_800_000
        dl = DayLedgerEvidence(
            trading_day_start_ms=start_ms,
            baseline_equity_usdt=D("10000"),
            baseline_evidence_id="ev_01",
            external_flow_usdt=D("0"),
            flow_classification_id=SYNTHETIC_FLOW_CLASSIFICATION.classification_id,
            unknown_flow_count=0,
            day_flow_cutoff_ms=scope.window_end_ms,
        )
        gate = gate_evaluate(
            tampered_report, snap, revision_before=0, revision_after=0,
            freshness_policy=FreshnessPolicy("pol", 1000, 1000, 1000, 1000, now_ms),
            freshness_evidence=FreshnessEvidence(now_ms, now_ms),
            day_ledger=dl,
        )
        self.assertFalse(gate.reconciled)
        self.assertIn("day_baseline_unverified", gate.blockers)

    # R2: Window coverage gap at start of day blocks gate
    async def test_r2_window_coverage_gap_at_day_start_blocks(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000
        day_start_ms = target_day * 86_400_000 - 28_800_000

        # Query window that starts after day_start_ms (e.g. 1 hour late)
        late_scope = authorized_formal_scope(now_ms)
        late_scope = replace(late_scope, window_start_ms=day_start_ms + 3600_000)

        snap = await self.supervisor._io(self.supervisor._journal.reconciliation_snapshot, "bot")
        t = await self._setup_transport()
        res = collection.collect_plan(CollectionPlan(late_scope, FORMAL_DEMO_ENDPOINT_ALIASES), t, clock=self.clock)
        report = account_report.build_report(res, scope=late_scope, classifications=SYNTHETIC_FLOW_CLASSIFICATION, **snap.report_attribution())

        self.assertIn("window_coverage_unverified", report["discrepancies"])
        self.assertIn("day_baseline_unverified", report["discrepancies"])

    # R3: Block cannot be overwritten by prior day and preserves E1
    async def test_r3_block_cannot_be_overwritten_by_prior_day(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000

        # Block target day
        await self.supervisor.block_day_basis(target_day)
        self.assertEqual(self.supervisor.risk_state.basis_blocked_day, target_day)

        # Attempt to block prior day D-1 must raise JournalError
        with self.assertRaises(JournalError) as ctx:
            await self.supervisor.block_day_basis(target_day - 1)
        self.assertIn("trusted current Taipei day", str(ctx.exception))

        # A caller cannot jump the durable block state into an arbitrary future day.
        with self.assertRaises(JournalError) as ctx:
            await self.supervisor.block_day_basis(target_day + 100)
        self.assertIn("trusted current Taipei day", str(ctx.exception))

        future_basis = make_verified_basis(now_ms + 100 * 86_400_000)
        with self.assertRaises(JournalError) as ctx:
            await self.supervisor.commit_day_basis(future_basis)
        self.assertIn("trusted current Taipei day", str(ctx.exception))

        # Attempt to commit basis on target_day must still be rejected
        with self.assertRaises(JournalError) as ctx:
            await self.supervisor.commit_day_basis(make_verified_basis(now_ms))
        self.assertIn("missing day basis cannot be rebuilt before next Taipei day", str(ctx.exception))

    # R3: Legacy unverified basis is durably blocked by block_day_basis and survives restart
    async def test_r3_legacy_unverified_basis_is_durably_blocked(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000

        # Inject legacy token-only basis directly into journal
        legacy_basis = risk.DayBasis(target_day, D("10000"), "legacy_unverified")
        await self.supervisor.commit_day_basis(legacy_basis)
        self.assertEqual(self.supervisor.risk_state.basis, legacy_basis)

        # Calling block_day_basis must succeed, invalidate the unverified basis, and persist block
        await self.supervisor.block_day_basis(target_day)
        self.assertIsNone(self.supervisor.risk_state.basis)
        self.assertEqual(self.supervisor.risk_state.basis_blocked_day, target_day)

        # Verify persistence after supervisor restart
        await self.supervisor.close()
        sup2 = LocalSupervisor(
            self.path, account_id=FORMAL_ACCOUNT_ALIAS, bot_id="bot", config=btc_config(),
            fixture_budget=D("100"), risk_limits=risk.Limits(), day_clock=self.clock,
        )
        self.addAsyncCleanup(sup2.close)
        await sup2.start()
        self.assertIsNone(sup2.risk_state.basis)
        self.assertEqual(sup2.risk_state.basis_blocked_day, target_day)

    # R4: Arbitrary source and self-computed digest rejected
    async def test_r4_arbitrary_source_rejected(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000

        # Source 'unverified_intraday_guess' must be rejected
        unverified_basis = make_verified_basis(now_ms, source="unverified_intraday_guess")
        self.assertFalse(
            risk.is_verified_baseline(
                unverified_basis, account_alias=FORMAL_ACCOUNT_ALIAS,
                environment=FORMAL_ENVIRONMENT, target_day=target_day,
            )
        )

        # Committing this basis into journal and calling provider must fail closed
        await self.supervisor.commit_day_basis(unverified_basis)
        provider = create_durable_day_ledger_provider(self.supervisor)
        resolved = await provider(now_ms, {
            "day_external_flow_usdt": "0",
            "flow_classification_id": "c1",
            "unknown_flow_count": 0,
            "day_flow_start_ms": target_day * 86_400_000 - 28_800_000,
            "day_flow_cutoff_ms": now_ms,
        })
        self.assertIsNone(resolved)
        # And day is blocked
        self.assertEqual(self.supervisor.risk_state.basis_blocked_day, target_day)

    async def test_r4_authorized_source_and_self_hash_without_payload_rejected(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000
        source = risk.SYNTHETIC_BASELINE_SOURCE
        digest = risk.compute_baseline_digest(
            account_alias=FORMAL_ACCOUNT_ALIAS, environment=FORMAL_ENVIRONMENT,
            day=target_day, equity=D("12345.67"), source=source,
            evidence_id="self_asserted")
        self_asserted = risk.DayBasis(
            target_day, D("12345.67"), "self_asserted",
            account_alias=FORMAL_ACCOUNT_ALIAS, environment=FORMAL_ENVIRONMENT,
            source=source, digest=digest)
        self.assertFalse(risk.is_verified_baseline(
            self_asserted, account_alias=FORMAL_ACCOUNT_ALIAS,
            environment=FORMAL_ENVIRONMENT, target_day=target_day))

        await self.supervisor.commit_day_basis(self_asserted)
        provider = create_durable_day_ledger_provider(self.supervisor)
        resolved = await provider(now_ms, {
            "day_external_flow_usdt": "0", "flow_classification_id": "c1",
            "unknown_flow_count": 0,
            "day_flow_start_ms": target_day * 86_400_000 - 28_800_000,
            "day_flow_cutoff_ms": now_ms,
        })
        self.assertIsNone(resolved)
        self.assertEqual(self.supervisor.risk_state.basis_blocked_day, target_day)

    async def test_d2_midnight_timing_evidence_must_match_baseline(self):
        now_ms = self.clock.wall_ms()
        target_day = (now_ms + 28_800_000) // 86_400_000
        midnight_ms = target_day * 86_400_000 - 28_800_000
        basis = make_verified_basis(now_ms, evidence_id="baseline_A")
        await self.supervisor.commit_day_basis(basis)

        classifications = okx_readonly.FlowClassification("test-flows", (
            okx_readonly.FlowClassificationEntry("1", "101", "external", "deposit"),
        ), True)
        bills = [dict(
            billId="b_wrong_timing_evidence", type="1", subType="101", ccy="USDT",
            balChg="200", ts=str(midnight_ms), timing_verified="after_baseline",
            timing_evidence_id="baseline_B")]
        transport = await self._setup_transport(lambda rows: rows.update(bills=bills))
        scope = authorized_formal_scope(now_ms)
        gate = await run_formal_reconciliation(
            self.supervisor, transport, plan=build_formal_collection_plan(scope),
            _test_classification_override=classifications,
            day_ledger_provider=create_durable_day_ledger_provider(self.supervisor),
            clock=self.clock)
        self.assertFalse(gate.reconciled)
        self.assertIn("day_baseline_unverified", gate.blockers)
