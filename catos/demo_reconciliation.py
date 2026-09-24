"""Formal Demo reconciliation runner orchestration path.

Connects bounded collection, pre-collection ownership/revision fence,
F1 freshness evidence derived from batch-tail public_time sample, S1/W1
verification, DayLedgerEvidence, and formal reconciliation gate.

No import-time I/O. No credential loading. Private GET and OKX connections
strictly prohibited during unit testing and synthetic validation.
"""

from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import time
from typing import Callable

from catos import demo_ledger_binding, okx_collection as reconciliation_collection
from catos import reconciliation_gate, risk
from catos.okx_collection import CollectionPlan, CollectionResult, PageTransport, RunScope
from catos.okx_readonly import FlowClassification, OKX_DEMO_CATALOG_FLOW_CLASSIFICATION
from catos.reconciliation_gate import (
    DayLedgerEvidence,
    FreshnessEvidence,
    FreshnessPolicy,
    GateResult,
)
from catos.supervisor import LocalSupervisor, SupervisorUnavailable


FORMAL_ACCOUNT_ALIAS = "catOSv1"
FORMAL_ENVIRONMENT = "demo"
FORMAL_INSTRUMENT = "BTC-USDT-SWAP"
FORMAL_WINDOW_SPAN_MS = 86400000
FORMAL_MAX_REQUESTS = 120
FORMAL_MAX_PAGES_PER_ENDPOINT = 40
FORMAL_REQUEST_TIMEOUT_MS = 10000
FORMAL_MAX_RUNTIME_MS = 180000

FORMAL_F1_POLICY_ID = "f1-demo-2026-09-22"
FORMAL_F1_MAX_REPORT_AGE_MS = 1000
FORMAL_F1_MAX_BATCH_SPAN_MS = 31000
FORMAL_F1_MAX_CLOCK_SKEW_MS = 3000
FORMAL_F1_MAX_CLOCK_SAMPLE_AGE_MS = 500

FORMAL_DEMO_ENDPOINT_ALIASES = (
    "account_config",
    "account_instruments",
    "public_instruments",
    "balance",
    "positions",
    "orders_pending",
    "algo_pending",
    "mark_price",
    "orders_history",
    "fills",
    "bills",
    "algo_history",
    "public_time",
)


class FormalPlanContractViolation(ValueError):
    """Raised when a CollectionPlan violates the formal production contract."""


class FormalLedgerBindingViolation(ValueError):
    """Raised before collection when local Demo ledger identity is not proven."""


def validate_formal_collection_plan(plan: CollectionPlan) -> None:
    """Validate that a CollectionPlan strictly adheres to the formal production bounds.

    Fails closed locally before any network request or pre-collection fence.
    """
    if not isinstance(plan, CollectionPlan):
        raise FormalPlanContractViolation("plan must be an instance of CollectionPlan")
    if plan.endpoint_aliases != FORMAL_DEMO_ENDPOINT_ALIASES:
        raise FormalPlanContractViolation(
            f"formal endpoint aliases and ordering must strictly match FORMAL_DEMO_ENDPOINT_ALIASES; "
            f"got {plan.endpoint_aliases}"
        )
    scope = plan.scope
    if not isinstance(scope, RunScope):
        raise FormalPlanContractViolation("plan.scope must be an instance of RunScope")
    if scope.account_alias != FORMAL_ACCOUNT_ALIAS:
        raise FormalPlanContractViolation(
            f"scope.account_alias must be {FORMAL_ACCOUNT_ALIAS!r}; got {scope.account_alias!r}"
        )
    if scope.environment != FORMAL_ENVIRONMENT:
        raise FormalPlanContractViolation(
            f"scope.environment must be {FORMAL_ENVIRONMENT!r}; got {scope.environment!r}"
        )
    if scope.instrument != FORMAL_INSTRUMENT:
        raise FormalPlanContractViolation(
            f"scope.instrument must be {FORMAL_INSTRUMENT!r}; got {scope.instrument!r}"
        )
    window_span = scope.window_end_ms - scope.window_start_ms
    if window_span != FORMAL_WINDOW_SPAN_MS:
        raise FormalPlanContractViolation(
            f"scope window span must be exactly 24h ({FORMAL_WINDOW_SPAN_MS}ms); got {window_span}ms"
        )
    if scope.max_requests != FORMAL_MAX_REQUESTS:
        raise FormalPlanContractViolation(
            f"scope.max_requests must be {FORMAL_MAX_REQUESTS}; got {scope.max_requests}"
        )
    if scope.max_pages_per_endpoint != FORMAL_MAX_PAGES_PER_ENDPOINT:
        raise FormalPlanContractViolation(
            f"scope.max_pages_per_endpoint must be {FORMAL_MAX_PAGES_PER_ENDPOINT}; got {scope.max_pages_per_endpoint}"
        )
    if scope.request_timeout_ms != FORMAL_REQUEST_TIMEOUT_MS:
        raise FormalPlanContractViolation(
            f"scope.request_timeout_ms must be {FORMAL_REQUEST_TIMEOUT_MS}; got {scope.request_timeout_ms}"
        )
    if scope.max_runtime_ms != FORMAL_MAX_RUNTIME_MS:
        raise FormalPlanContractViolation(
            f"scope.max_runtime_ms must be {FORMAL_MAX_RUNTIME_MS}; got {scope.max_runtime_ms}"
        )


class _Clock:
    @staticmethod
    def wall_ms() -> int:
        return time.time_ns() // 1_000_000

    @staticmethod
    def monotonic_ms() -> int:
        return time.monotonic_ns() // 1_000_000


def authorized_formal_scope(end_ms: int) -> RunScope:
    """Freeze the approved trailing 24h window once, before the first request."""
    return RunScope(
        account_alias=FORMAL_ACCOUNT_ALIAS,
        environment=FORMAL_ENVIRONMENT,
        instrument=FORMAL_INSTRUMENT,
        window_start_ms=end_ms - FORMAL_WINDOW_SPAN_MS,
        window_end_ms=end_ms,
        max_requests=FORMAL_MAX_REQUESTS,
        max_pages_per_endpoint=FORMAL_MAX_PAGES_PER_ENDPOINT,
        request_timeout_ms=FORMAL_REQUEST_TIMEOUT_MS,
        max_runtime_ms=FORMAL_MAX_RUNTIME_MS,
    )


def build_formal_collection_plan(
    scope: RunScope | None = None,
    *,
    end_ms: int | None = None,
) -> CollectionPlan:
    """Build a deterministic bounded formal CollectionPlan with public_time at the tail."""
    if scope is None:
        active_end_ms = _Clock.wall_ms() if end_ms is None else end_ms
        scope = authorized_formal_scope(active_end_ms)
    plan = CollectionPlan(scope, FORMAL_DEMO_ENDPOINT_ALIASES)
    validate_formal_collection_plan(plan)
    return plan


def derive_f1_freshness_evidence(result: CollectionResult) -> FreshnessEvidence | None:
    """Extract server_time_ms and local_time_ms midpoint from batch-tail public_time."""
    if not isinstance(result, CollectionResult) or not result.manifest.complete:
        return None

    time_page = next((p for p in result.pages if p.endpoint_alias == "public_time"), None)
    if time_page is None:
        return None

    try:
        payload = json.loads(time_page.payload_json)
        if payload.get("code") != "0":
            return None
        data = payload.get("data")
        if type(data) is not list or len(data) != 1 or type(data[0]) is not dict:
            return None
        raw_ts = data[0].get("ts")
        if not isinstance(raw_ts, str) or not raw_ts.isdigit() or len(raw_ts) > 19:
            return None
        server_time_ms = int(raw_ts)
    except Exception:
        return None

    time_manifest = next(
        (m for m in result.manifest.endpoint_manifests if m.alias == "public_time"),
        None,
    )
    if time_manifest is None or not time_manifest.complete:
        return None

    if time_manifest.started_ms is not None:
        local_time_ms = (time_manifest.started_ms + time_manifest.completed_ms) // 2
    elif time_manifest.pages:
        local_time_ms = time_manifest.pages[0].received_ms
    else:
        local_time_ms = time_manifest.completed_ms

    try:
        return FreshnessEvidence(server_time_ms=server_time_ms, local_time_ms=local_time_ms)
    except (ValueError, TypeError):
        return None


def create_f1_freshness_policy(checked_at_ms: int) -> FreshnessPolicy:
    """Construct an F1 FreshnessPolicy with formal production thresholds."""
    return FreshnessPolicy(
        policy_id=FORMAL_F1_POLICY_ID,
        max_report_age_ms=FORMAL_F1_MAX_REPORT_AGE_MS,
        max_batch_span_ms=FORMAL_F1_MAX_BATCH_SPAN_MS,
        max_clock_skew_ms=FORMAL_F1_MAX_CLOCK_SKEW_MS,
        max_clock_sample_age_ms=FORMAL_F1_MAX_CLOCK_SAMPLE_AGE_MS,
        checked_at_ms=checked_at_ms,
    )


def derive_f1_freshness(
    result: CollectionResult,
) -> tuple[Callable[[int], FreshnessPolicy] | None, FreshnessEvidence | None]:
    """Derive FreshnessEvidence and a dynamic FreshnessPolicy builder for gate check time.

    Returns (policy_builder, evidence). The policy_builder accepts eval_checked_at_ms
    at the exact moment reconciliation_gate.evaluate() is invoked, guaranteeing that
    checked_at_ms reflects actual evaluation time and preventing false PASS from delays
    between collection completion and gate evaluation.
    """
    evidence = derive_f1_freshness_evidence(result)
    if evidence is None:
        return None, None

    def policy_builder(eval_checked_at_ms: int) -> FreshnessPolicy:
        return create_f1_freshness_policy(eval_checked_at_ms)

    return policy_builder, evidence


def _sha256_json(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _verified_report_digest(report: dict) -> str | None:
    if type(report) is not dict or type(report.get("content_digest")) is not str:
        return None
    body = dict(report)
    claimed = body.pop("content_digest")
    actual = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    return claimed if claimed == actual else None


def _endpoint_manifest(result: CollectionResult, alias: str):
    matches = [item for item in result.manifest.endpoint_manifests if item.alias == alias]
    return matches[0] if len(matches) == 1 else None


def _raw_rows(result: CollectionResult, alias: str) -> list[dict] | None:
    endpoint = _endpoint_manifest(result, alias)
    if (endpoint is None or endpoint.complete is not True or endpoint.issue != ""
            or not endpoint.pages or endpoint.pages[-1].next_cursor is not None):
        return None
    collected = sorted(
        (page for page in result.pages if page.endpoint_alias == alias),
        key=lambda page: page.page_number,
    )
    if len(collected) != len(endpoint.pages):
        return None
    rows: list[dict] = []
    for page, evidence in zip(collected, endpoint.pages):
        if (page.page_number != evidence.page_number
                or page.request_cursor != evidence.request_cursor
                or hashlib.sha256(page.payload_json.encode("utf-8")).hexdigest() != evidence.digest):
            return None
        try:
            payload = json.loads(page.payload_json)
        except (ValueError, TypeError):
            return None
        data = payload.get("data") if type(payload) is dict and payload.get("code") == "0" else None
        if type(data) is not list or any(type(row) is not dict for row in data):
            return None
        rows.extend(data)
    return rows


def _collection_evidence_digest(result: CollectionResult) -> str:
    manifest = result.manifest
    endpoints = []
    for endpoint in manifest.endpoint_manifests:
        window = endpoint.window_evidence
        endpoints.append({
            "alias": endpoint.alias,
            "path": endpoint.path,
            "started_ms": endpoint.started_ms,
            "completed_ms": endpoint.completed_ms,
            "requests": endpoint.requests,
            "complete": endpoint.complete,
            "issue": endpoint.issue,
            "window_evidence": None if window is None else {
                "begin_ms": window.begin_ms,
                "end_ms": window.end_ms,
                "event_time_field": window.event_time_field,
                "cursor_semantics": window.cursor_semantics,
            },
            "pages": [{
                "page_number": page.page_number,
                "request_cursor": page.request_cursor,
                "next_cursor": page.next_cursor,
                "source_ms": page.source_ms,
                "received_ms": page.received_ms,
                "digest": page.digest,
            } for page in endpoint.pages],
        })
    return _sha256_json({
        "collector_version": manifest.collector_version,
        "account_alias": manifest.account_alias,
        "environment": manifest.environment,
        "instrument": manifest.instrument,
        "window_start_ms": manifest.window_start_ms,
        "window_end_ms": manifest.window_end_ms,
        "started_ms": manifest.started_ms,
        "completed_ms": manifest.completed_ms,
        "requests": manifest.requests,
        "complete": manifest.complete,
        "endpoints": endpoints,
    })


def build_demo_quiescent_midnight_basis(
    result: CollectionResult,
    report: dict,
    expected_uid_sha256: str | None,
) -> risk.DayBasis | None:
    """Build Q1 E₀ only from a complete zero-activity Demo interval proof.

    The function is pure and fail-closed. It never reconstructs equity from bills and
    never mutates Supervisor, Journal, reconciliation state, or trade authorization.
    """
    if (not isinstance(result, CollectionResult) or type(report) is not dict
            or type(expected_uid_sha256) is not str or len(expected_uid_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in expected_uid_sha256)):
        return None
    manifest = result.manifest
    if ((manifest.account_alias, manifest.environment, manifest.instrument) !=
            (FORMAL_ACCOUNT_ALIAS, FORMAL_ENVIRONMENT, FORMAL_INSTRUMENT)
            or manifest.complete is not True
            or tuple(item.alias for item in manifest.endpoint_manifests) != FORMAL_DEMO_ENDPOINT_ALIASES):
        return None
    report_digest = _verified_report_digest(report)
    if (report_digest is None or report.get("collection_complete") is not True
            or (report.get("account_alias"), report.get("environment"), report.get("instrument")) !=
               (FORMAL_ACCOUNT_ALIAS, FORMAL_ENVIRONMENT, FORMAL_INSTRUMENT)
            or report.get("window_start_ms") != manifest.window_start_ms
            or report.get("window_end_ms") != manifest.window_end_ms):
        return None
    allowed_placeholders = {"freshness_unverified", "window_coverage_unverified", "day_baseline_unverified"}
    discrepancies = report.get("discrepancies")
    if type(discrepancies) is not list or any(item not in allowed_placeholders for item in discrepancies):
        return None

    cutoff_ms = manifest.window_end_ms
    day_context = risk.DayContext.from_target_time_ms(cutoff_ms)
    day_start_ms = day_context.trading_day_start_ms
    if manifest.window_start_ms > day_start_ms or manifest.completed_ms < cutoff_ms:
        return None

    freshness = derive_f1_freshness_evidence(result)
    if freshness is None:
        return None
    freshness_policy = create_f1_freshness_policy(manifest.completed_ms)
    if reconciliation_gate._freshness_blockers(report, freshness_policy, freshness):
        return None

    config_rows = _raw_rows(result, "account_config")
    balance_rows = _raw_rows(result, "balance")
    if config_rows is None or len(config_rows) != 1 or balance_rows is None or len(balance_rows) != 1:
        return None
    config = config_rows[0]
    uid = config.get("uid")
    main_uid = config.get("mainUid")
    if (type(uid) is not str or not uid or type(main_uid) is not str or not main_uid
            or uid == main_uid or config.get("acctLv") != "2" or config.get("posMode") != "net_mode"):
        return None
    try:
        observed_uid_sha256 = hashlib.sha256(uid.encode("ascii")).hexdigest()
    except UnicodeEncodeError:
        return None
    if observed_uid_sha256 != expected_uid_sha256:
        return None

    facts = report.get("facts")
    if type(facts) is not list:
        return None
    balance_facts = [fact for fact in facts
                     if type(fact) is dict and fact.get("kind") == "balance"]
    if len(balance_facts) != 1:
        return None
    details = balance_facts[0].get("details")
    if type(details) is not list or len(details) != 1 or type(details[0]) is not dict:
        return None
    detail = details[0]
    try:
        equity = Decimal(detail.get("eq"))
        available = Decimal(detail.get("availEq"))
        order_frozen = Decimal(detail.get("ordFrozen"))
        liability = Decimal("0") if detail.get("liab") is None else Decimal(detail.get("liab"))
    except Exception:
        return None
    if (detail.get("ccy") != "USDT" or not equity.is_finite() or equity <= 0
            or not available.is_finite() or available != equity
            or not order_frozen.is_finite() or order_frozen != 0
            or not liability.is_finite() or liability != 0):
        return None

    balance_manifest = _endpoint_manifest(result, "balance")
    if (balance_manifest is None or balance_manifest.completed_ms > cutoff_ms
            or any(page.received_ms > cutoff_ms for page in balance_manifest.pages)):
        return None

    zero_aliases = ("positions", "orders_pending", "algo_pending", "orders_history", "fills", "bills")
    zero_payload = {}
    for alias in zero_aliases:
        rows = _raw_rows(result, alias)
        endpoint = _endpoint_manifest(result, alias)
        if rows is None or rows or endpoint is None:
            return None
        zero_payload[alias] = {
            "page_digests": [page.digest for page in endpoint.pages],
            "received_ms": [page.received_ms for page in endpoint.pages],
        }
    for alias in ("positions", "orders_pending", "algo_pending"):
        endpoint = _endpoint_manifest(result, alias)
        if endpoint is None or any(page.received_ms < cutoff_ms for page in endpoint.pages):
            return None

    expected_windows = {
        "orders_history": reconciliation_collection.WindowRequestEvidence(
            manifest.window_start_ms, cutoff_ms, "cTime", "after_order_id"),
        "fills": reconciliation_collection.WindowRequestEvidence(manifest.window_start_ms, cutoff_ms),
        "bills": reconciliation_collection.WindowRequestEvidence(manifest.window_start_ms, cutoff_ms),
    }
    for alias, expected in expected_windows.items():
        endpoint = _endpoint_manifest(result, alias)
        if endpoint is None or endpoint.window_evidence != expected or endpoint.started_ms < cutoff_ms:
            return None

    balance_content_digest = _sha256_json({
        "page_digests": [page.digest for page in balance_manifest.pages],
        "equity_usdt": str(equity),
        "available_equity_usdt": str(available),
        "order_frozen_usdt": str(order_frozen),
        "liability_usdt": str(liability),
    })
    zero_event_digest = _sha256_json({
        "day_start_ms": day_start_ms,
        "cutoff_ms": cutoff_ms,
        "zero_sources": zero_payload,
        "window_sources": {
            alias: {
                "begin_ms": evidence.begin_ms,
                "end_ms": evidence.end_ms,
                "event_time_field": evidence.event_time_field,
                "cursor_semantics": evidence.cursor_semantics,
            } for alias, evidence in expected_windows.items()
        },
    })
    collection_digest = _collection_evidence_digest(result)
    evidence_id = "q1_" + _sha256_json({
        "uid": expected_uid_sha256,
        "day_start_ms": day_start_ms,
        "cutoff_ms": cutoff_ms,
        "report": report_digest,
        "balance": balance_content_digest,
        "collection": collection_digest,
        "zero": zero_event_digest,
    })[:48]
    evidence = risk.make_demo_quiescent_baseline_evidence(
        account_alias=FORMAL_ACCOUNT_ALIAS,
        environment=FORMAL_ENVIRONMENT,
        day=day_context.day,
        cutoff_ms=cutoff_ms,
        equity=equity,
        evidence_id=evidence_id,
        expected_uid_sha256=expected_uid_sha256,
        report_content_digest=report_digest,
        balance_content_digest=balance_content_digest,
        collection_evidence_digest=collection_digest,
        zero_event_digest=zero_event_digest,
    )
    digest = risk.compute_baseline_digest(
        account_alias=FORMAL_ACCOUNT_ALIAS,
        environment=FORMAL_ENVIRONMENT,
        day=day_context.day,
        equity=equity,
        source=risk.DEMO_QUIESCENT_BASELINE_SOURCE,
        evidence_id=evidence_id,
        evidence=evidence,
    )
    return risk.DayBasis(
        day=day_context.day,
        equity=equity,
        evidence_id=evidence_id,
        account_alias=FORMAL_ACCOUNT_ALIAS,
        environment=FORMAL_ENVIRONMENT,
        source=risk.DEMO_QUIESCENT_BASELINE_SOURCE,
        digest=digest,
        evidence=evidence,
    )


def create_durable_day_ledger_provider(
    supervisor: LocalSupervisor,
    *,
    account_alias: str = FORMAL_ACCOUNT_ALIAS,
    environment: str = FORMAL_ENVIRONMENT,
):
    """Create a durable DayLedgerEvidence provider wired to Supervisor's single-writer path.

    - Resolves target trading day from cutoff timestamp.
    - Validates account_alias and environment bounds.
    - Loads durable baseline via Supervisor serialized I/O.
    - Verifies baseline provenance and digest; blocks old token-only baselines.
    - On first formal evaluation of a missing baseline day, atomically blocks that day
      via supervisor.block_day_basis(target_day) per D3 (fail-closed, no rebuild, restart persistent).
    - Assembles DayLedgerEvidence strictly using verified baseline and actual day_flow_context
      (forbidden to assume or default external flows to zero).
    """
    async def provider(target_time_ms: int, day_flow_context: dict | None = None) -> DayLedgerEvidence | None:
        day_context = risk.DayContext.from_target_time_ms(target_time_ms)
        target_day = day_context.day
        expected_start_ms = day_context.trading_day_start_ms

        # Load durable basis through Supervisor's serialized single-writer channel
        basis = await supervisor.load_day_basis(target_day)

        # Check if already blocked
        risk_state = supervisor.risk_state
        if risk_state is not None and risk_state.basis_blocked_day == target_day:
            return None

        # Verify durable baseline provenance, account, environment, and digest
        if not risk.is_verified_baseline(basis, account_alias=account_alias, environment=environment, target_day=target_day):
            # Missing or unverified durable basis on first formal evaluation:
            # Atomically block day per D3 (fail closed, no wait grace, no rebuild)
            await supervisor.block_day_basis(target_day)
            return None

        # Require explicit day_flow_context and validate exact day bounds (R2)
        if not isinstance(day_flow_context, dict):
            return None

        ctx_start = day_flow_context.get("day_flow_start_ms")
        ctx_cutoff = day_flow_context.get("day_flow_cutoff_ms")
        if ctx_start != expected_start_ms:
            return None
        if not isinstance(ctx_cutoff, int) or ctx_cutoff < expected_start_ms or ctx_cutoff > target_time_ms:
            return None

        raw_flow = day_flow_context.get("day_external_flow_usdt")
        if raw_flow is None:
            return None
        try:
            flow_usdt = Decimal(str(raw_flow))
        except Exception:
            return None

        flow_classification_id = day_flow_context.get("flow_classification_id")
        if not isinstance(flow_classification_id, str) or not flow_classification_id:
            return None

        unknown_count = day_flow_context.get("unknown_flow_count", 0)
        if type(unknown_count) is not int or unknown_count < 0:
            return None

        return DayLedgerEvidence(
            trading_day_start_ms=expected_start_ms,
            baseline_equity_usdt=basis.equity,
            baseline_evidence_id=basis.evidence_id,
            external_flow_usdt=flow_usdt,
            flow_classification_id=flow_classification_id,
            unknown_flow_count=unknown_count,
            day_flow_cutoff_ms=ctx_cutoff,
        )

    return provider


async def run_formal_reconciliation(
    supervisor: LocalSupervisor,
    transport: PageTransport,
    *,
    scope: RunScope | None = None,
    plan: CollectionPlan | None = None,
    day_ledger: DayLedgerEvidence | None = None,
    day_ledger_provider: Callable[..., DayLedgerEvidence | None] | None = None,
    clock: object | None = None,
    _test_classification_override: FlowClassification | None = None,
) -> GateResult:
    """Execute the production formal Demo reconciliation orchestration path.

    - Validates formal production plan bounds (exactly 24h, 120 reqs, 40 pages, 180s runtime,
      10s timeout, fixed 13 endpoints in exact order) before any pre-collection fence or network.
    - Acquires pre-collection ownership & revision fence via LocalSupervisor.
    - Executes caller-injected bounded collection (CollectionPlan).
    - Derives F1 FreshnessEvidence from public_time and evaluates gate with check-time checked_at_ms.
    - Evaluates formal reconciliation gate (fail-closed on observed unknown/forbidden
      flows, missing verified E₀, foreign responsibilities, S1/W1/F1 violations).
    - Writes Journal reconciliation evidence ONLY on gate.reconciled == True.
    - Enforces trade_authorized == False unconditionally in current phase.
    """
    if plan is None:
        if scope is None:
            active_end = clock.wall_ms() if clock is not None and hasattr(clock, "wall_ms") else _Clock.wall_ms()
            scope = authorized_formal_scope(active_end)
        plan = CollectionPlan(scope, FORMAL_DEMO_ENDPOINT_ALIASES)

    # Strictly validate formal production contract before any network I/O or pre-collection fence
    validate_formal_collection_plan(plan)

    try:
        supervisor.verify_demo_ledger_binding(
            account_alias=plan.scope.account_alias,
            remote_environment=plan.scope.environment,
        )
    except (AttributeError, demo_ledger_binding.DemoLedgerBindingError) as exc:
        raise FormalLedgerBindingViolation(str(exc)) from None

    # Use official catalog flow classification by default; test seam only via explicit private override
    formal_classifications = (
        OKX_DEMO_CATALOG_FLOW_CLASSIFICATION
        if _test_classification_override is None
        else _test_classification_override
    )

    # Resolve DayLedgerEvidence from explicit provider if not directly passed
    resolved_day_ledger = day_ledger
    resolved_provider = day_ledger_provider
    if resolved_day_ledger is None and resolved_provider is not None:
        import inspect
        try:
            sig = inspect.signature(resolved_provider)
            if len(sig.parameters) == 1 and not inspect.iscoroutinefunction(resolved_provider):
                resolved_day_ledger = resolved_provider(plan.scope.window_end_ms)
                resolved_provider = None
        except (ValueError, TypeError):
            pass

    def _freshness_builder(result: CollectionResult):
        return derive_f1_freshness(result)

    gate = await supervisor.collect_and_reconcile(
        plan,
        transport,
        classifications=formal_classifications,
        freshness_builder=_freshness_builder,
        clock=clock,
        day_ledger=resolved_day_ledger,
        day_ledger_provider=resolved_provider,
        day_basis_builder=build_demo_quiescent_midnight_basis,
    )
    return gate
