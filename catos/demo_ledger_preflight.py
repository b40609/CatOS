"""Read-only preflight for a catOSv1 Demo ledger bootstrap or resume.

This module never opens Journal or Supervisor and never creates, migrates, or
repairs the selected ledger.  A successful preflight is not reconciliation or
trade authorization.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from catos import account_lock, demo_ledger_binding, ipc, risk


VERSION = "demo-ledger-preflight.v1"
FORMAL_ACCOUNT_ALIAS = "catOSv1"
CURRENT_TRADING_SCHEMA_VERSION = 7
INTENTS = frozenset(("create", "resume"))

_QA_DATABASE_RELATIVE_PATHS = (
    "outputs/s10-qa-20260921-sol/scenario.sqlite3",
    "outputs/s10-s9-regression-20260921-sol/scenario.sqlite3",
    "outputs/s9-qa-20260921-101840/scenario.sqlite3",
    "reports/s8-qa-20260919-impl/scenario.sqlite3",
    "reports/s9-qa-20260921/scenario.sqlite3",
)

_REQUIRED_TABLES = frozenset((
    "metadata", "control", "bots", "ownership", "inputs", "intents",
    "reservations", "outbox", "risk_control", "risk_orders", "execution_mode",
    "execution_orders", "execution_fills", "risk_actions", "protection",
    "lot_bindings", "lot_heads", "lot_revisions", "lot_fill_orders",
    "lot_fill_events", "lot_fill_terminals",
))
_REQUIRED_METADATA_COLUMNS = frozenset((
    "account_id", "environment", "fixture_budget", "core_schema_version",
))
_REQUIRED_OWNERSHIP_COLUMNS = frozenset((
    "inst_id", "bot_id", "position", "ordinary_open", "conditional_open",
    "unknown_count", "fills_reconciled", "evidence_id", "reconciled_revision",
    "remote_pos_id",
))


class DemoLedgerPreflightError(ValueError):
    """Stable error code; never contains UID or database contents."""


@dataclass(frozen=True)
class DemoLedgerPreflight:
    intent: str
    database_path: str
    binding_path: str
    expected_uid_sha256: str
    account_alias: str
    remote_environment: str
    account_binding_status: str
    schema_verified: bool
    binding_verified: bool
    preflight_passed: bool = True
    reconciled: bool = False
    trade_authorized: bool = False
    version: str = VERSION


def qa_database_paths() -> tuple[str, ...]:
    root = Path(__file__).resolve().parents[1]
    return tuple(str((root / path).resolve()) for path in _QA_DATABASE_RELATIVE_PATHS)


def _canonical(path, name: str) -> Path:
    if not isinstance(path, (str, os.PathLike)) or not os.fspath(path):
        raise DemoLedgerPreflightError(f"{name}_missing")
    try:
        return Path(path).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise DemoLedgerPreflightError(f"{name}_invalid") from exc


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def _exists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _validate_uid_digest(value: str) -> str:
    if (type(value) is not str or len(value) != 64
            or any(ch not in "0123456789abcdef" for ch in value)):
        raise DemoLedgerPreflightError("expected_uid_digest_invalid")
    return value


def _validate_settings(*, account_alias, remote_environment, bot_id, config,
                       fixture_budget, risk_limits) -> str:
    if account_alias != FORMAL_ACCOUNT_ALIAS:
        raise DemoLedgerPreflightError("account_alias_mismatch")
    if remote_environment != demo_ledger_binding.REMOTE_ENVIRONMENT:
        raise DemoLedgerPreflightError("remote_environment_mismatch")
    try:
        ipc.token(bot_id, "bot_id")
    except ipc.ProtocolError as exc:
        raise DemoLedgerPreflightError("bot_id_invalid") from exc
    if not isinstance(config, ipc.WorkerConfig):
        raise DemoLedgerPreflightError("worker_config_missing_or_invalid")
    try:
        config = ipc.WorkerConfig.from_wire(config.to_wire())
    except (ipc.ProtocolError, TypeError, ValueError, AttributeError) as exc:
        raise DemoLedgerPreflightError("worker_config_missing_or_invalid") from exc
    if not isinstance(fixture_budget, Decimal):
        raise DemoLedgerPreflightError("fixture_budget_missing_or_invalid")
    try:
        budget = ipc.decimal_text(str(fixture_budget), "fixture budget", derived=False)
    except ipc.ProtocolError as exc:
        raise DemoLedgerPreflightError("fixture_budget_missing_or_invalid") from exc
    if budget <= 0:
        raise DemoLedgerPreflightError("fixture_budget_missing_or_invalid")
    if not isinstance(risk_limits, risk.Limits):
        raise DemoLedgerPreflightError("risk_limits_missing_or_invalid")
    return json.dumps(config.to_wire(), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _account_lock_path(account_id: str) -> Path:
    digest = hashlib.sha256(
        f"{account_lock.ENVIRONMENT}:{account_id}".encode("ascii")).hexdigest()
    directory = (account_lock.LOCK_DIRECTORY if account_lock.LOCK_DIRECTORY is not None
                 else Path.home() / ".catos" / "local-simulation-locks")
    return Path(directory) / f"{digest}.lock"


def _read_account_database_binding(account_id: str) -> Path | None:
    """Inspect the persistent AccountLock path without acquiring or modifying it."""
    lock_path = _account_lock_path(account_id)
    if not _exists(lock_path):
        return None
    if not lock_path.is_file():
        raise DemoLedgerPreflightError("account_binding_invalid")
    try:
        raw = lock_path.read_bytes()
    except OSError as exc:
        raise DemoLedgerPreflightError("account_binding_unreadable") from exc
    if not raw or raw[:1] != b"\0":
        raise DemoLedgerPreflightError("account_binding_invalid")
    if len(raw) == 1:
        raise DemoLedgerPreflightError("account_binding_incomplete")
    if len(raw) - 1 > ipc.MAX_FRAME:
        raise DemoLedgerPreflightError("account_binding_invalid")
    try:
        payload = ipc.decode_payload(raw[1:])
        ipc.exact(payload, ("database",))
        if type(payload["database"]) is not str:
            raise ipc.ProtocolError("invalid database path")
        return Path(payload["database"]).resolve()
    except (ipc.ProtocolError, OSError, RuntimeError, ValueError) as exc:
        raise DemoLedgerPreflightError("account_binding_invalid") from exc


def _ensure_parent_shape(path: Path, name: str) -> None:
    parent = path.parent
    if _exists(parent) and not parent.is_dir():
        raise DemoLedgerPreflightError(f"{name}_parent_invalid")


def _qa_excluded(database: Path) -> bool:
    return any(_same_path(database, Path(path)) for path in qa_database_paths())


def _verify_wal_header(database: Path) -> None:
    try:
        with database.open("rb") as stream:
            header = stream.read(20)
    except OSError as exc:
        raise DemoLedgerPreflightError("ledger_database_unreadable") from exc
    if (len(header) != 20 or header[:16] != b"SQLite format 3\0"
            or header[18:20] != b"\x02\x02"):
        raise DemoLedgerPreflightError("ledger_journal_mode_mismatch")


def _read_resume_schema(database: Path, *, bot_id: str, config_json: str,
                        fixture_budget: Decimal, risk_limits: risk.Limits) -> None:
    _verify_wal_header(database)
    try:
        try:
            uri = demo_ledger_binding.readonly_sqlite_uri(database)
        except demo_ledger_binding.DemoLedgerBindingError as exc:
            raise DemoLedgerPreflightError(str(exc)) from None
        with closing(sqlite3.connect(uri, uri=True, isolation_level=None, timeout=0.25)) as db:
            db.row_factory = sqlite3.Row
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version != CURRENT_TRADING_SCHEMA_VERSION:
                raise DemoLedgerPreflightError("ledger_schema_version_mismatch")
            tables = {row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            if not _REQUIRED_TABLES <= tables:
                raise DemoLedgerPreflightError("ledger_schema_incomplete")
            metadata_columns = {row[1] for row in db.execute("PRAGMA table_info(metadata)")}
            ownership_columns = {row[1] for row in db.execute("PRAGMA table_info(ownership)")}
            if (not _REQUIRED_METADATA_COLUMNS <= metadata_columns
                    or not _REQUIRED_OWNERSHIP_COLUMNS <= ownership_columns):
                raise DemoLedgerPreflightError("ledger_schema_incomplete")

            metadata = db.execute(
                "SELECT account_id, environment, fixture_budget, core_schema_version FROM metadata"
            ).fetchall()
            if len(metadata) != 1 or metadata[0]["core_schema_version"] != 2:
                raise DemoLedgerPreflightError("ledger_metadata_invalid")
            try:
                stored_budget = ipc.decimal_text(
                    metadata[0]["fixture_budget"], "stored fixture budget", derived=True)
            except ipc.ProtocolError as exc:
                raise DemoLedgerPreflightError("ledger_metadata_invalid") from exc
            if stored_budget != fixture_budget:
                raise DemoLedgerPreflightError("fixture_budget_mismatch")

            bots = db.execute("SELECT bot_id, inst_id, config_json FROM bots").fetchall()
            if len(bots) != 1 or bots[0]["bot_id"] != bot_id:
                raise DemoLedgerPreflightError("ledger_bot_scope_mismatch")
            if (bots[0]["inst_id"] != json.loads(config_json)["contract"]["inst_id"]
                    or bots[0]["config_json"] != config_json):
                raise DemoLedgerPreflightError("ledger_bot_config_mismatch")
            owners = db.execute("SELECT bot_id, inst_id FROM ownership").fetchall()
            if (len(owners) != 1 or owners[0]["bot_id"] != bot_id
                    or owners[0]["inst_id"] != bots[0]["inst_id"]):
                raise DemoLedgerPreflightError("ledger_ownership_scope_mismatch")
            protection = db.execute("SELECT bot_id FROM protection").fetchall()
            if len(protection) != 1 or protection[0]["bot_id"] != bot_id:
                raise DemoLedgerPreflightError("ledger_protection_scope_mismatch")

            controls = db.execute("SELECT id FROM control").fetchall()
            if len(controls) != 1 or controls[0]["id"] != 1:
                raise DemoLedgerPreflightError("ledger_control_invalid")
            saved_risk = db.execute(
                "SELECT limits_json FROM risk_control WHERE id=1").fetchall()
            if len(saved_risk) != 1:
                raise DemoLedgerPreflightError("ledger_risk_state_missing")
            expected_limits = json.dumps(
                risk_limits.to_wire(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            if saved_risk[0]["limits_json"] != expected_limits:
                raise DemoLedgerPreflightError("risk_limits_mismatch")
    except DemoLedgerPreflightError:
        raise
    except sqlite3.Error as exc:
        raise DemoLedgerPreflightError("ledger_database_unreadable") from exc


def preflight_demo_ledger(*, intent: str, database_path, binding_path,
                          expected_uid_sha256: str, bot_id: str,
                          config: ipc.WorkerConfig, fixture_budget: Decimal,
                          risk_limits: risk.Limits,
                          account_alias: str = FORMAL_ACCOUNT_ALIAS,
                          remote_environment: str = demo_ledger_binding.REMOTE_ENVIRONMENT,
                          ) -> DemoLedgerPreflight:
    """Check bootstrap/resume inputs without creating or modifying ledger state."""
    if intent not in INTENTS:
        raise DemoLedgerPreflightError("preflight_intent_invalid")
    expected_uid_sha256 = _validate_uid_digest(expected_uid_sha256)
    config_json = _validate_settings(
        account_alias=account_alias,
        remote_environment=remote_environment,
        bot_id=bot_id,
        config=config,
        fixture_budget=fixture_budget,
        risk_limits=risk_limits,
    )
    database = _canonical(database_path, "database_path")
    binding_file = _canonical(binding_path, "binding_path")
    _ensure_parent_shape(database, "database_path")
    _ensure_parent_shape(binding_file, "binding_path")
    if _same_path(database, binding_file):
        raise DemoLedgerPreflightError("database_binding_path_conflict")
    if _qa_excluded(database):
        raise DemoLedgerPreflightError("qa_database_excluded")

    wal = Path(str(database) + "-wal")
    shm = Path(str(database) + "-shm")
    if _same_path(binding_file, wal) or _same_path(binding_file, shm):
        raise DemoLedgerPreflightError("database_binding_path_conflict")

    bound_database = _read_account_database_binding(account_alias)
    if bound_database is not None and not _same_path(bound_database, database):
        raise DemoLedgerPreflightError("account_bound_to_different_database")

    database_exists = _exists(database)
    binding_exists = _exists(binding_file)
    wal_exists = _exists(wal)
    shm_exists = _exists(shm)

    if intent == "create":
        if bound_database is not None:
            if not database_exists:
                raise DemoLedgerPreflightError("account_binding_database_missing")
            raise DemoLedgerPreflightError("database_already_account_bound")
        if database_exists:
            raise DemoLedgerPreflightError("database_path_exists")
        if binding_exists:
            raise DemoLedgerPreflightError("binding_path_exists")
        if wal_exists:
            raise DemoLedgerPreflightError("database_wal_exists")
        if shm_exists:
            raise DemoLedgerPreflightError("database_shm_exists")
        return DemoLedgerPreflight(
            intent=intent,
            database_path=str(database),
            binding_path=str(binding_file),
            expected_uid_sha256=expected_uid_sha256,
            account_alias=account_alias,
            remote_environment=remote_environment,
            account_binding_status="unbound",
            schema_verified=False,
            binding_verified=False,
        )

    if not database_exists or not database.is_file():
        raise DemoLedgerPreflightError("resume_database_missing")
    if not binding_exists or not binding_file.is_file():
        raise DemoLedgerPreflightError("resume_binding_missing")
    if wal_exists != shm_exists:
        raise DemoLedgerPreflightError("ledger_sidecar_pair_incomplete")

    try:
        proof = demo_ledger_binding.load_binding(binding_file)
        demo_ledger_binding.verify_runtime_binding(
            proof,
            expected_uid_sha256=expected_uid_sha256,
            account_alias=account_alias,
            remote_environment=remote_environment,
            database_path=database,
        )
    except demo_ledger_binding.DemoLedgerBindingError as exc:
        raise DemoLedgerPreflightError(str(exc)) from None

    _read_resume_schema(
        database,
        bot_id=bot_id,
        config_json=config_json,
        fixture_budget=fixture_budget,
        risk_limits=risk_limits,
    )
    return DemoLedgerPreflight(
        intent=intent,
        database_path=str(database),
        binding_path=str(binding_file),
        expected_uid_sha256=expected_uid_sha256,
        account_alias=account_alias,
        remote_environment=remote_environment,
        account_binding_status=("matches" if bound_database is not None else "unbound"),
        schema_verified=True,
        binding_verified=True,
    )
