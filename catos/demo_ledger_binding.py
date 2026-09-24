"""Fail-closed binding between one OKX Demo account identity and one local ledger.

The binding stores only a SHA-256 digest of the expected UID.  Verification is
read-only: it never creates, migrates, or modifies the SQLite database.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3


VERSION = "demo-ledger-binding.v1"
REMOTE_ENVIRONMENT = "demo"
STORAGE_ENVIRONMENT = "local-sim"
MAX_BINDING_BYTES = 16_384


class DemoLedgerBindingError(ValueError):
    """Stable public error code; never includes UID or database contents."""


def uid_digest(uid: str) -> str:
    if type(uid) is not str or not uid.isdigit() or not 1 <= len(uid) <= 64:
        raise DemoLedgerBindingError("expected_uid_invalid")
    return hashlib.sha256(uid.encode("ascii")).hexdigest()


def _digest_payload(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical_database(path) -> str:
    return str(Path(path).resolve())


def readonly_sqlite_uri(database: Path) -> str:
    """Open a ledger without creating WAL sidecars for a quiescent database."""
    database = Path(database).resolve()
    wal = Path(str(database) + "-wal")
    shm = Path(str(database) + "-shm")
    wal_exists = wal.exists()
    shm_exists = shm.exists()
    if wal_exists != shm_exists:
        raise DemoLedgerBindingError("ledger_binding_sidecar_incomplete")
    suffix = "?mode=ro" if wal_exists else "?mode=ro&immutable=1"
    return database.as_uri() + suffix


@dataclass(frozen=True)
class DemoLedgerBinding:
    account_alias: str
    remote_environment: str
    storage_environment: str
    expected_uid_sha256: str
    database_path: str
    binding_id: str
    version: str = VERSION

    def payload(self) -> dict:
        return {
            "version": self.version,
            "account_alias": self.account_alias,
            "remote_environment": self.remote_environment,
            "storage_environment": self.storage_environment,
            "expected_uid_sha256": self.expected_uid_sha256,
            "database_path": self.database_path,
        }

    def valid(self) -> bool:
        if (self.version != VERSION or self.remote_environment != REMOTE_ENVIRONMENT
                or self.storage_environment != STORAGE_ENVIRONMENT):
            return False
        if (type(self.account_alias) is not str or not self.account_alias
                or self.account_alias.strip() != self.account_alias or len(self.account_alias) > 128):
            return False
        if (type(self.expected_uid_sha256) is not str or len(self.expected_uid_sha256) != 64
                or any(ch not in "0123456789abcdef" for ch in self.expected_uid_sha256)):
            return False
        if type(self.database_path) is not str or not self.database_path:
            return False
        if _canonical_database(self.database_path) != self.database_path:
            return False
        if type(self.binding_id) is not str or len(self.binding_id) != 64:
            return False
        return self.binding_id == _digest_payload(self.payload())


def make_binding(*, account_alias: str, expected_uid_sha256: str, database_path) -> DemoLedgerBinding:
    payload = {
        "version": VERSION,
        "account_alias": account_alias,
        "remote_environment": REMOTE_ENVIRONMENT,
        "storage_environment": STORAGE_ENVIRONMENT,
        "expected_uid_sha256": expected_uid_sha256,
        "database_path": _canonical_database(database_path),
    }
    binding = DemoLedgerBinding(
        account_alias=payload["account_alias"],
        remote_environment=payload["remote_environment"],
        storage_environment=payload["storage_environment"],
        expected_uid_sha256=payload["expected_uid_sha256"],
        database_path=payload["database_path"],
        binding_id=_digest_payload(payload),
    )
    if not binding.valid():
        raise DemoLedgerBindingError("ledger_binding_invalid")
    return binding


def load_binding(path) -> DemoLedgerBinding:
    source = Path(path)
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise DemoLedgerBindingError("ledger_binding_unavailable") from exc
    if not 0 < len(raw) <= MAX_BINDING_BYTES:
        raise DemoLedgerBindingError("ledger_binding_invalid")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DemoLedgerBindingError("ledger_binding_invalid") from exc
    expected = {
        "version", "account_alias", "remote_environment", "storage_environment",
        "expected_uid_sha256", "database_path", "binding_id",
    }
    if type(value) is not dict or set(value) != expected:
        raise DemoLedgerBindingError("ledger_binding_invalid")
    try:
        binding = DemoLedgerBinding(**value)
    except TypeError as exc:
        raise DemoLedgerBindingError("ledger_binding_invalid") from exc
    if not binding.valid():
        raise DemoLedgerBindingError("ledger_binding_invalid")
    return binding


def verify_runtime_binding(binding, *, expected_uid_sha256: str, account_alias: str,
                           remote_environment: str, database_path) -> None:
    """Verify account scope and SQLite identity without modifying the ledger."""
    if not isinstance(binding, DemoLedgerBinding) or not binding.valid():
        raise DemoLedgerBindingError("ledger_binding_missing_or_invalid")
    if (type(expected_uid_sha256) is not str
            or expected_uid_sha256 != binding.expected_uid_sha256):
        raise DemoLedgerBindingError("ledger_binding_uid_mismatch")
    if (account_alias != binding.account_alias
            or remote_environment != binding.remote_environment):
        raise DemoLedgerBindingError("ledger_binding_scope_mismatch")
    database = Path(database_path).resolve()
    if str(database) != binding.database_path:
        raise DemoLedgerBindingError("ledger_binding_database_mismatch")
    if not database.is_file():
        raise DemoLedgerBindingError("ledger_binding_database_missing")

    try:
        # Runtime ledgers use WAL.  Plain mode=ro must observe the live WAL;
        # immutable=1 is appropriate only when no WAL/SHM pair exists and avoids
        # creating sidecars while inspecting a quiescent database.
        uri = readonly_sqlite_uri(database)
        with closing(sqlite3.connect(uri, uri=True, isolation_level=None, timeout=0.25)) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(metadata)")}
            if not {"account_id", "environment"} <= columns:
                raise DemoLedgerBindingError("ledger_binding_metadata_invalid")
            rows = connection.execute("SELECT account_id, environment FROM metadata").fetchall()
    except DemoLedgerBindingError:
        raise
    except sqlite3.Error as exc:
        raise DemoLedgerBindingError("ledger_binding_database_unreadable") from exc

    if len(rows) != 1:
        raise DemoLedgerBindingError("ledger_binding_metadata_invalid")
    if rows[0][0] != account_alias or rows[0][1] != binding.storage_environment:
        raise DemoLedgerBindingError("ledger_binding_metadata_scope_mismatch")
