"""Read-only production Demo ledger bootstrap planning contract.

This module fixes the intended production ledger and binding destinations and
combines the existing create preflight with explicit historical-responsibility
evidence.  It never creates the ledger, writes the binding, opens Supervisor,
or grants reconciliation/trading authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
import os
from pathlib import Path

from catos import demo_ledger_binding, demo_ledger_preflight, ipc, risk, supervisor


VERSION = "demo-ledger-bootstrap-plan.v1"
OPERATION_VERSION = "demo-ledger-bootstrap-operation.v1"
UID_DIGEST_SOURCE = "operator_verified_demo_uid.v1"
PRODUCTION_EVIDENCE_PROVENANCE = "production_readonly.v1"
PRODUCTION_DATABASE_RELATIVE_PATH = Path("data/catosv1-demo/state.sqlite3")
PRODUCTION_BINDING_RELATIVE_PATH = Path("data/catosv1-demo/ledger-binding.json")


@dataclass(frozen=True)
class HistoricalResponsibilityEvidence:
    """Evidence required before a fresh local ledger may enter bootstrap.

    Endpoint-complete booleans describe the production read-only collection,
    not a synthetic fixture.  Empty current remote responsibility is accepted
    only when the corresponding endpoint collection is complete and the same
    evidence set also closes current-day accounting and one authorized verified E0 contract.
    """

    provenance: str
    account_alias: str
    remote_environment: str
    expected_uid_sha256: str
    uid_digest_source: str
    identity_verified: bool
    account_mode_verified: bool
    account_config_complete: bool
    balance_complete: bool
    positions_complete: bool
    orders_pending_complete: bool
    algo_pending_complete: bool
    orders_history_complete: bool
    fills_complete: bool
    bills_complete: bool
    algo_history_complete: bool
    current_positions_empty: bool
    current_orders_empty: bool
    current_algo_orders_empty: bool
    day_baseline_verified: bool
    unknown_flow_count: int
    forbidden_activity_count: int
    collection_evidence_id: str
    day_baseline_evidence_id: str


@dataclass(frozen=True)
class DemoLedgerBootstrapPlan:
    version: str
    database_path: str
    binding_path: str
    uid_digest_source: str
    preflight_passed: bool
    responsibility_bridge_verified: bool
    bootstrap_ready: bool
    blockers: tuple[str, ...]
    ledger_initialized: bool = False
    binding_verified: bool = False
    reconciled: bool = False
    trade_authorized: bool = False


class DemoLedgerBootstrapError(RuntimeError):
    """Stable bootstrap operation error; never contains credentials or raw UID."""


@dataclass(frozen=True)
class DemoLedgerBootstrapResult:
    version: str
    plan_version: str
    database_path: str
    binding_path: str
    binding_id: str
    ledger_initialized: bool
    binding_verified: bool
    reconciled: bool = False
    trade_authorized: bool = False


def production_paths(workspace_root) -> tuple[Path, Path]:
    """Return the fixed production Demo ledger destinations without creating them."""
    root = Path(workspace_root).resolve()
    return (
        (root / PRODUCTION_DATABASE_RELATIVE_PATH).resolve(),
        (root / PRODUCTION_BINDING_RELATIVE_PATH).resolve(),
    )


def _nonempty_text(value) -> bool:
    return type(value) is str and bool(value) and value.strip() == value


def _historical_blockers(
    evidence: HistoricalResponsibilityEvidence | None,
    *,
    expected_uid_sha256: str,
) -> tuple[str, ...]:
    if evidence is None:
        return ("historical_responsibility_evidence_missing",)
    if not isinstance(evidence, HistoricalResponsibilityEvidence):
        return ("historical_responsibility_evidence_invalid",)

    blockers = set()
    if evidence.provenance != PRODUCTION_EVIDENCE_PROVENANCE:
        blockers.add("historical_evidence_not_production_readonly")
    if (evidence.account_alias != demo_ledger_preflight.FORMAL_ACCOUNT_ALIAS
            or evidence.remote_environment != "demo"
            or evidence.expected_uid_sha256 != expected_uid_sha256
            or evidence.uid_digest_source != UID_DIGEST_SOURCE):
        blockers.add("historical_evidence_scope_mismatch")
    if evidence.identity_verified is not True:
        blockers.add("historical_identity_unverified")
    if evidence.account_mode_verified is not True:
        blockers.add("historical_account_mode_unverified")

    endpoint_flags = (
        evidence.account_config_complete,
        evidence.balance_complete,
        evidence.positions_complete,
        evidence.orders_pending_complete,
        evidence.algo_pending_complete,
        evidence.orders_history_complete,
        evidence.fills_complete,
        evidence.bills_complete,
        evidence.algo_history_complete,
    )
    if not all(flag is True for flag in endpoint_flags):
        blockers.add("historical_collection_incomplete")

    if not all(flag is True for flag in (
            evidence.current_positions_empty,
            evidence.current_orders_empty,
            evidence.current_algo_orders_empty)):
        blockers.add("preexisting_remote_responsibility")
    if evidence.day_baseline_verified is not True:
        blockers.add("day_baseline_unverified")
    if type(evidence.unknown_flow_count) is not int or evidence.unknown_flow_count != 0:
        blockers.add("unknown_account_flow")
    if (type(evidence.forbidden_activity_count) is not int
            or evidence.forbidden_activity_count != 0):
        blockers.add("forbidden_account_activity")
    if (not _nonempty_text(evidence.collection_evidence_id)
            or not _nonempty_text(evidence.day_baseline_evidence_id)):
        blockers.add("historical_evidence_id_missing")
    return tuple(sorted(blockers))


def plan_production_bootstrap(
    *,
    workspace_root,
    expected_uid_sha256: str,
    bot_id: str,
    config: ipc.WorkerConfig,
    fixture_budget: Decimal,
    risk_limits: risk.Limits,
    historical_evidence: HistoricalResponsibilityEvidence | None = None,
) -> DemoLedgerBootstrapPlan:
    """Build a fail-closed bootstrap plan without creating or modifying state.

    bootstrap_ready means only that an explicitly authorized future writer may
    enter the create operation.  It never means ledger_initialized, reconciled,
    or trade_authorized.
    """
    database, binding = production_paths(workspace_root)
    preflight = demo_ledger_preflight.preflight_demo_ledger(
        intent="create",
        database_path=database,
        binding_path=binding,
        expected_uid_sha256=expected_uid_sha256,
        bot_id=bot_id,
        config=config,
        fixture_budget=fixture_budget,
        risk_limits=risk_limits,
    )
    blockers = _historical_blockers(
        historical_evidence,
        expected_uid_sha256=expected_uid_sha256,
    )
    bridge_verified = not blockers
    return DemoLedgerBootstrapPlan(
        version=VERSION,
        database_path=preflight.database_path,
        binding_path=preflight.binding_path,
        uid_digest_source=UID_DIGEST_SOURCE,
        preflight_passed=preflight.preflight_passed,
        responsibility_bridge_verified=bridge_verified,
        bootstrap_ready=preflight.preflight_passed and bridge_verified,
        blockers=blockers,
    )


def _write_binding_exclusive(path: Path, binding: demo_ledger_binding.DemoLedgerBinding) -> None:
    payload = {**binding.payload(), "binding_id": binding.binding_id}
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    try:
        with path.open("xb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise DemoLedgerBootstrapError("binding_path_exists") from exc
    except OSError as exc:
        raise DemoLedgerBootstrapError("binding_write_failed") from exc


async def bootstrap_production_ledger(
    *,
    workspace_root,
    expected_uid_sha256: str,
    bot_id: str,
    config: ipc.WorkerConfig,
    fixture_budget: Decimal,
    risk_limits: risk.Limits,
    historical_evidence: HistoricalResponsibilityEvidence | None = None,
) -> DemoLedgerBootstrapResult:
    """Create one fresh local ledger and binding after the full read-only gate.

    The operation re-runs the planning contract immediately before mutation,
    uses LocalSupervisor as the only SQLite writer, and reserves the database
    path exclusively while the account lock is held.  Failure leaves any
    created state in place for manual inspection; this function never retries,
    overwrites, deletes, reconciles, or grants trading authority.
    """
    plan = plan_production_bootstrap(
        workspace_root=workspace_root,
        expected_uid_sha256=expected_uid_sha256,
        bot_id=bot_id,
        config=config,
        fixture_budget=fixture_budget,
        risk_limits=risk_limits,
        historical_evidence=historical_evidence,
    )
    if not plan.bootstrap_ready:
        raise DemoLedgerBootstrapError("bootstrap_not_ready")

    instance = supervisor.LocalSupervisor(
        plan.database_path,
        account_id=demo_ledger_preflight.FORMAL_ACCOUNT_ALIAS,
        bot_id=bot_id,
        config=config,
        fixture_budget=fixture_budget,
        risk_limits=risk_limits,
        require_new_database=True,
    )
    started = False
    try:
        try:
            await instance.start()
            started = True
        except Exception as exc:
            raise DemoLedgerBootstrapError("ledger_initialization_failed") from exc

        try:
            proof = demo_ledger_binding.make_binding(
                account_alias=demo_ledger_preflight.FORMAL_ACCOUNT_ALIAS,
                expected_uid_sha256=expected_uid_sha256,
                database_path=plan.database_path,
            )
        except demo_ledger_binding.DemoLedgerBindingError as exc:
            raise DemoLedgerBootstrapError("binding_materialization_failed") from exc
        try:
            demo_ledger_binding.verify_runtime_binding(
                proof,
                expected_uid_sha256=expected_uid_sha256,
                account_alias=demo_ledger_preflight.FORMAL_ACCOUNT_ALIAS,
                remote_environment=demo_ledger_binding.REMOTE_ENVIRONMENT,
                database_path=plan.database_path,
            )
        except demo_ledger_binding.DemoLedgerBindingError as exc:
            raise DemoLedgerBootstrapError("binding_verification_failed") from exc
        binding_path = Path(plan.binding_path)
        _write_binding_exclusive(binding_path, proof)
        try:
            stored_proof = demo_ledger_binding.load_binding(binding_path)
            demo_ledger_binding.verify_runtime_binding(
                stored_proof,
                expected_uid_sha256=expected_uid_sha256,
                account_alias=demo_ledger_preflight.FORMAL_ACCOUNT_ALIAS,
                remote_environment=demo_ledger_binding.REMOTE_ENVIRONMENT,
                database_path=plan.database_path,
            )
        except demo_ledger_binding.DemoLedgerBindingError as exc:
            raise DemoLedgerBootstrapError("persisted_binding_verification_failed") from exc

        return DemoLedgerBootstrapResult(
            version=OPERATION_VERSION,
            plan_version=plan.version,
            database_path=plan.database_path,
            binding_path=plan.binding_path,
            binding_id=stored_proof.binding_id,
            ledger_initialized=True,
            binding_verified=True,
        )
    finally:
        if started:
            await instance.close()
