"""S2 snapshot storage on the existing Journal writer; no fill or order engine."""

from contextlib import contextmanager
from dataclasses import dataclass, fields, replace
from decimal import Decimal
import hashlib
import json
import sqlite3

from catos import ipc, ipc_lots, lots
from catos.journal import JournalError
from catos.research import ContractSpec


TABLES = ("lot_bindings", "lot_heads", "lot_revisions")
SCHEMA = (
    """CREATE TABLE lot_bindings (
        bot_id TEXT PRIMARY KEY NOT NULL,
        account_ref TEXT NOT NULL,
        environment TEXT NOT NULL CHECK(environment='local-sim'),
        inst_id TEXT NOT NULL,
        contract_json TEXT NOT NULL
            CHECK(length(CAST(contract_json AS BLOB)) BETWEEN 1 AND 65536),
        last_commit_seq INTEGER NOT NULL DEFAULT 0
            CHECK(last_commit_seq BETWEEN 0 AND 9223372036854775807)
    ) STRICT""",
    """CREATE TABLE lot_heads (
        lot_id TEXT PRIMARY KEY NOT NULL
            CHECK(length(lot_id)=64 AND lot_id NOT GLOB '*[^0-9a-f]*'),
        bot_id TEXT NOT NULL REFERENCES lot_bindings(bot_id),
        open_event_seq INTEGER NOT NULL
            CHECK(open_event_seq BETWEEN 1 AND 9223372036854775807),
        open_intent_key TEXT NOT NULL UNIQUE
            CHECK(length(open_intent_key)=64 AND open_intent_key NOT GLOB '*[^0-9a-f]*'),
        side TEXT NOT NULL CHECK(side IN ('long','short')),
        current_revision INTEGER NOT NULL
            CHECK(current_revision BETWEEN 1 AND 9223372036854775807),
        UNIQUE(bot_id, open_event_seq),
        UNIQUE(lot_id, bot_id),
        FOREIGN KEY(lot_id, current_revision)
            REFERENCES lot_revisions(lot_id, revision) DEFERRABLE INITIALLY DEFERRED
    ) STRICT""",
    """CREATE TABLE lot_revisions (
        lot_id TEXT NOT NULL,
        bot_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK(revision BETWEEN 1 AND 9223372036854775807),
        expected_revision INTEGER NOT NULL
            CHECK(expected_revision BETWEEN 0 AND 9223372036854775806),
        write_id TEXT NOT NULL CHECK(length(write_id) BETWEEN 1 AND 64),
        commit_seq INTEGER NOT NULL CHECK(commit_seq BETWEEN 1 AND 9223372036854775807),
        operation TEXT NOT NULL CHECK(operation IN ('CREATE','REPLACE')),
        opened_qty TEXT NOT NULL CHECK(typeof(opened_qty)='text'),
        remaining_qty TEXT NOT NULL CHECK(typeof(remaining_qty)='text'),
        average_entry TEXT NOT NULL CHECK(typeof(average_entry)='text'),
        realized_pnl TEXT NOT NULL CHECK(typeof(realized_pnl)='text'),
        fees_paid TEXT NOT NULL CHECK(typeof(fees_paid)='text'),
        funding_paid TEXT CHECK(funding_paid IS NULL OR typeof(funding_paid)='text'),
        trigger_price_type TEXT NOT NULL CHECK(trigger_price_type='mark'),
        take_profit TEXT CHECK(take_profit IS NULL OR typeof(take_profit)='text'),
        stop_loss TEXT CHECK(stop_loss IS NULL OR typeof(stop_loss)='text'),
        opening_unresolved INTEGER NOT NULL CHECK(opening_unresolved IN (0,1)),
        closing_unresolved INTEGER NOT NULL CHECK(closing_unresolved IN (0,1)),
        request_json TEXT NOT NULL
            CHECK(length(CAST(request_json AS BLOB)) BETWEEN 1 AND 65536),
        request_hash TEXT NOT NULL
            CHECK(length(request_hash)=64 AND request_hash NOT GLOB '*[^0-9a-f]*'),
        PRIMARY KEY(lot_id, revision),
        UNIQUE(bot_id, write_id),
        UNIQUE(bot_id, commit_seq),
        FOREIGN KEY(lot_id, bot_id) REFERENCES lot_heads(lot_id, bot_id),
        CHECK(revision=expected_revision+1),
        CHECK((operation='CREATE' AND expected_revision=0)
           OR (operation='REPLACE' AND expected_revision>=1))
    ) STRICT""",
)

_FINANCIAL = ("opened_qty", "remaining_qty", "average_entry", "realized_pnl",
              "fees_paid", "funding_paid")
_SELECT = """SELECT r.*, h.open_event_seq, h.open_intent_key, h.side, h.current_revision
             FROM lot_revisions r JOIN lot_heads h
             ON h.lot_id=r.lot_id AND h.bot_id=r.bot_id"""


class LotStorageError(JournalError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StoredLot:
    lot: lots.Lot
    opening_unresolved: bool
    closing_unresolved: bool
    commit_seq: int


@dataclass(frozen=True, slots=True)
class StoredLotV2:
    lot: lots.LotV2
    opening_unresolved: bool
    closing_unresolved: bool
    commit_seq: int


@dataclass(frozen=True, slots=True)
class LotWriteReceipt:
    bot_id: str
    lot_id: str
    write_id: str
    revision: int
    commit_seq: int
    request_hash: str
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class LotRecoveryReport:
    storage_ready: bool
    binding_count: int
    lot_count: int
    revision_count: int
    unresolved_lot_count: int


@dataclass(frozen=True, slots=True)
class _Binding:
    scope: lots.LotScope
    bot_id: str
    contract: ContractSpec
    last_commit_seq: int


def _json(value):
    ipc.encode_frame(value)
    text = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    if len(text.encode("utf-8")) > ipc.MAX_FRAME:
        raise ipc.ProtocolError("frame size limit exceeded")
    return text


def _decode_json(text):
    if type(text) is not str:
        raise ipc.ProtocolError("stored JSON must be TEXT")
    return ipc.decode_payload(text.encode("utf-8"))


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _contract_wire(contract):
    lots._validate_contract(contract)
    return {f.name: str(getattr(contract, f.name)) if f.name != "inst_id"
            else contract.inst_id for f in fields(ContractSpec)}


def _contract_from_wire(value):
    ipc.exact(value, tuple(f.name for f in fields(ContractSpec)))
    contract = ContractSpec(value["inst_id"], **{
        name: ipc.decimal_text(value[name], name, positive=True)
        for name in value if name != "inst_id"})
    lots._validate_contract(contract)
    return contract


def _numeric_identity(value):
    # Only called after domain/wire validation. No context-sensitive arithmetic.
    if value.is_zero():
        return [0, "0", 0]
    sign, digits, exponent = value.as_tuple()
    coefficient = "".join(map(str, digits))
    trimmed = coefficient.rstrip("0")
    return [sign, trimmed, exponent + len(coefficient) - len(trimmed)]


def _request(binding, write_id, operation, open_event_seq, expected_revision,
             after, opening, closing, *, v2=False):
    from catos import lot_snapshot_codec
    wire = (lot_snapshot_codec if v2 else ipc_lots).lot_to_wire(after)
    for name in (lot_snapshot_codec.FINANCIAL if v2 else _FINANCIAL):
        if wire[name] is not None:
            wire[name] = _numeric_identity(getattr(after, name))
    if v2 and after.fee_quality.known_fee_subtotal is not None:
        wire["fee_quality"]["known_fee_subtotal"] = _numeric_identity(after.fee_quality.known_fee_subtotal)
    for name in ("take_profit", "stop_loss"):
        if wire["protection"][name] is not None:
            wire["protection"][name] = _numeric_identity(getattr(after.protection, name))
    contract = _contract_wire(binding.contract)
    for name in contract:
        if name != "inst_id":
            contract[name] = _numeric_identity(getattr(binding.contract, name))
    return _json(dict(format_version=2 if v2 else 1,
                     scope=dict(account_ref=binding.scope.account_ref,
                                environment=binding.scope.environment),
                     bot_id=binding.bot_id, inst_id=binding.contract.inst_id,
                     contract=contract, write_id=write_id, operation=operation,
                     open_event_seq=open_event_seq, expected_revision=expected_revision,
                     after=wire, opening_unresolved=opening, closing_unresolved=closing))


def install_schema(connection):
    """Called only inside Journal's initialization transaction."""
    if sqlite3.sqlite_version_info < (3, 37, 0):
        raise LotStorageError("storage_unavailable")
    for name in TABLES:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone():
            raise LotStorageError("integrity_error")
    for statement in SCHEMA:
        connection.execute(statement)


class LotJournal:
    schema_version = 7
    schema = SCHEMA

    def __init__(self, journal):
        self.j = journal
        self.db = journal.connection
        self._failed = False
        from catos import lot_snapshot_codec
        self.v2 = self.schema_version == 8
        self.codec = lot_snapshot_codec if self.v2 else ipc_lots
        self.financial = lot_snapshot_codec.FINANCIAL if self.v2 else _FINANCIAL
        self.validator = lots.validate_lot_v2 if self.v2 else lots.validate_lot

    def _request(self, *args):
        return _request(*args, v2=self.v2)

    @contextmanager
    def _access(self):
        if self._failed:
            raise LotStorageError("storage_unavailable")
        try:
            if self.db.in_transaction:
                raise LotStorageError("storage_unavailable")
            with self.j._transaction():
                yield
        except LotStorageError as exc:
            if exc.code == "integrity_error":
                self._failed = True
            raise
        except lots.LotError as exc:
            raise LotStorageError(exc.code) from exc
        except ipc.ProtocolError as exc:
            raise LotStorageError("invalid_transition") from exc
        except sqlite3.Error as exc:
            self._failed = True
            raise LotStorageError("storage_unavailable") from exc
        except BaseException:
            # Includes interruption while COMMIT may already have completed.
            self._failed = True
            raise

    def _scope(self, scope):
        if (not isinstance(scope, lots.LotScope)
                or scope.account_ref != self.j.account_id or scope.environment != "local-sim"):
            raise LotStorageError("scope_mismatch")
        lots.LotScope(scope.account_ref, scope.environment)

    def _decode_binding(self, row):
        try:
            scope = lots.LotScope(row["account_ref"], row["environment"])
            self._scope(scope)
            ipc.token(row["bot_id"], "bot_id")
            contract = _contract_from_wire(_decode_json(row["contract_json"]))
            if contract.inst_id != row["inst_id"]:
                raise ValueError("contract mismatch")
            seq = ipc.integer(row["last_commit_seq"], "stored commit sequence")
            return _Binding(scope, row["bot_id"], contract, seq)
        except (ValueError, TypeError, LotStorageError) as exc:
            raise LotStorageError("integrity_error") from exc

    def _binding(self, scope, bot_id):
        self._scope(scope)
        ipc.token(bot_id, "bot_id")
        row = self.db.execute("SELECT * FROM lot_bindings WHERE bot_id=?", (bot_id,)).fetchone()
        if row is None:
            raise LotStorageError("binding_conflict")
        return self._decode_binding(row)

    def register_binding(self, *, scope, bot_id, contract):
        with self._access():
            self._scope(scope)
            ipc.token(bot_id, "bot_id")
            wire = _contract_wire(contract)
            old = self.db.execute("SELECT * FROM lot_bindings WHERE bot_id=?", (bot_id,)).fetchone()
            if old is not None:
                binding = self._decode_binding(old)
                if binding.scope != scope or binding.contract != contract:
                    raise LotStorageError("binding_conflict")
            else:
                self.db.execute("INSERT INTO lot_bindings VALUES (?,?,?,?,?,0)",
                                (bot_id, scope.account_ref, scope.environment,
                                 contract.inst_id, _json(wire)))

    def _head_identity(self, row, binding):
        seq = ipc.integer(row["open_event_seq"], "open_event_seq", 1)
        ipc.integer(row["current_revision"], "current_revision", 1)
        lots._validate_side(row["side"])
        context = lots.IntentContext(binding.scope, binding.bot_id, binding.contract, seq, False)
        key = lots.make_intent_key(context)
        if (row["bot_id"] != binding.bot_id or row["open_intent_key"] != key
                or row["lot_id"] != lots.make_lot_id(key)):
            raise ValueError("stored identity mismatch")

    def _decode_revision(self, row, binding):
        try:
            self._head_identity(row, binding)
            revision = ipc.integer(row["revision"], "revision", 1)
            expected = ipc.integer(row["expected_revision"], "expected_revision")
            seq = ipc.integer(row["commit_seq"], "commit_seq", 1)
            ipc.token(row["write_id"], "write_id")
            if (revision != expected + 1 or revision > row["current_revision"]
                    or seq > binding.last_commit_seq
                    or row["operation"] != ("CREATE" if expected == 0 else "REPLACE")):
                raise ValueError("stored sequence mismatch")
            for name in ("opening_unresolved", "closing_unresolved"):
                if type(row[name]) is not int or row[name] not in (0, 1):
                    raise ValueError("stored flag mismatch")
            value = dict(scope=dict(account_ref=binding.scope.account_ref,
                                    environment=binding.scope.environment),
                         bot_id=binding.bot_id, inst_id=binding.contract.inst_id,
                         lot_id=row["lot_id"], open_intent_key=row["open_intent_key"],
                         side=row["side"], revision=revision,
                         protection={name: row[name] for name in
                                     ("trigger_price_type", "take_profit", "stop_loss")},
                         **{name: row[name] for name in self.financial})
            if self.v2:
                value.update(snapshot_version=2, fee_quality=dict(coverage=row["fee_coverage"],
                    known_fee_subtotal=row["known_fee_subtotal"], fee_unknown_fill_count=row["fee_unknown_fill_count"]))
            lot = self.codec.lot_from_wire(value)
            self.validator(lot, binding.contract)
            opening, closing = bool(row["opening_unresolved"]), bool(row["closing_unresolved"])
            request = self._request(binding, row["write_id"], row["operation"],
                               row["open_event_seq"] if expected == 0 else None,
                               expected, lot, opening, closing)
            _decode_json(row["request_json"])
            if row["request_json"] != request or row["request_hash"] != _hash(request):
                raise ValueError("stored fingerprint mismatch")
            return (StoredLotV2 if self.v2 else StoredLot)(lot, opening, closing, seq)
        except (ValueError, TypeError) as exc:
            raise LotStorageError("integrity_error") from exc

    def _head(self, binding, lot_id):
        row = self.db.execute("SELECT * FROM lot_heads WHERE lot_id=? AND bot_id=?",
                              (lot_id, binding.bot_id)).fetchone()
        latest = self.db.execute("SELECT max(revision) FROM lot_revisions WHERE lot_id=? AND bot_id=?",
                                 (lot_id, binding.bot_id)).fetchone()[0]
        if row is None:
            if latest is not None:
                raise LotStorageError("integrity_error")
            return None
        try:
            self._head_identity(row, binding)
            if latest != row["current_revision"]:
                raise ValueError("head is not latest")
        except (ValueError, TypeError) as exc:
            raise LotStorageError("integrity_error") from exc
        return row

    def _row(self, bot_id, lot_id, revision):
        return self.db.execute(_SELECT + " WHERE r.bot_id=? AND r.lot_id=? AND r.revision=?",
                               (bot_id, lot_id, revision)).fetchone()

    @staticmethod
    def _transition(before, after, opening, closing):
        old = before.lot
        immutable = ("scope", "bot_id", "inst_id", "lot_id", "open_intent_key", "side")
        if any(getattr(old, name) != getattr(after, name) for name in immutable):
            raise LotStorageError("identity_conflict")
        if (after.opened_qty < old.opened_qty
                or (old.remaining_qty == 0 and
                    (after.remaining_qty != 0 or after.opened_qty != old.opened_qty
                     or after.average_entry != old.average_entry))
                or (after.opened_qty == old.opened_qty and
                    (after.remaining_qty > old.remaining_qty or after.average_entry != old.average_entry))):
            raise LotStorageError("invalid_transition")
        if (replace(after, revision=old.revision) == old
                and opening == before.opening_unresolved and closing == before.closing_unresolved):
            raise LotStorageError("no_change")

    @staticmethod
    def _receipt(row, replayed=False):
        return LotWriteReceipt(row["bot_id"], row["lot_id"], row["write_id"],
                               row["revision"], row["commit_seq"], row["request_hash"], replayed)

    def create(self, *, scope, bot_id, write_id, open_event_seq, after,
               opening_unresolved, closing_unresolved):
        if self.v2:
            raise LotStorageError("unsupported_fee_version")
        return self._write(scope, bot_id, write_id, "CREATE", open_event_seq, 0,
                           after, opening_unresolved, closing_unresolved)

    def replace(self, *, scope, bot_id, write_id, expected_revision, after,
                opening_unresolved, closing_unresolved):
        if self.v2:
            raise LotStorageError("unsupported_fee_version")
        return self._write(scope, bot_id, write_id, "REPLACE", None, expected_revision,
                           after, opening_unresolved, closing_unresolved)

    def create_v2(self, *, scope, bot_id, write_id, open_event_seq, after,
                  opening_unresolved, closing_unresolved):
        if not self.v2 or type(after) is not lots.LotV2:
            raise LotStorageError("unsupported_fee_version")
        return self._write(scope, bot_id, write_id, "CREATE", open_event_seq, 0,
                           after, opening_unresolved, closing_unresolved)

    def replace_v2(self, *, scope, bot_id, write_id, expected_revision, after,
                   opening_unresolved, closing_unresolved):
        if not self.v2 or type(after) is not lots.LotV2:
            raise LotStorageError("unsupported_fee_version")
        return self._write(scope, bot_id, write_id, "REPLACE", None, expected_revision,
                           after, opening_unresolved, closing_unresolved)

    @contextmanager
    def _write_access(self, internal, after):
        if internal:
            if self._failed or not self.db.in_transaction:
                raise LotStorageError("storage_unavailable")
            yield
        else:
            with self._access():
                fills = getattr(self.j, "lot_fills", None)
                if fills is not None and fills._managed(after.lot_id):
                    raise LotStorageError("managed_lot")
                yield

    def _write(self, scope, bot_id, write_id, operation, open_seq, expected, after, opening, closing,
               *, _in_transaction=False):
        if not _in_transaction and isinstance(write_id, str) and write_id.startswith(("s3_", "s9_")):
            raise LotStorageError("reserved_write_id")
        with self._write_access(_in_transaction, after):
            binding = self._binding(scope, bot_id)
            ipc.token(write_id, "write_id")
            ipc.integer(expected, "expected_revision", 0 if operation == "CREATE" else 1)
            if expected == ipc.MAX_INTEGER:
                raise LotStorageError("sequence_exhausted")
            if type(opening) is not bool or type(closing) is not bool:
                raise LotStorageError("invalid_transition")
            # Reconstruct to validate even locally forged/mutated frozen objects.
            after = self.codec.lot_from_wire(self.codec.lot_to_wire(after))
            if self.v2 and not _in_transaction and after.fee_quality.coverage != "UNVERIFIED":
                raise LotStorageError("unmanaged_lot")
            if (after.scope != scope or after.bot_id != bot_id
                    or after.inst_id != binding.contract.inst_id):
                raise LotStorageError("identity_conflict")
            self.validator(after, binding.contract)
            if operation == "CREATE":
                ipc.integer(open_seq, "open_event_seq", 1)
                origin = lots.IntentContext(scope, bot_id, binding.contract, open_seq, False)
                if after.open_intent_key != lots.make_intent_key(origin):
                    raise LotStorageError("identity_conflict")
            request = self._request(binding, write_id, operation, open_seq, expected, after, opening, closing)
            prior = self.db.execute(_SELECT + " WHERE r.bot_id=? AND r.write_id=?",
                                    (bot_id, write_id)).fetchone()
            if prior is not None:
                self._decode_revision(prior, binding)
                if prior["request_json"] != request or prior["request_hash"] != _hash(request):
                    raise LotStorageError("write_conflict")
                receipt = self._receipt(prior, True)
            else:
                if after.revision != expected + 1:
                    raise LotStorageError("revision_conflict")
                head = self._head(binding, after.lot_id)
                if operation == "CREATE":
                    if head is not None or self.db.execute(
                            "SELECT 1 FROM lot_heads WHERE lot_id=? OR (bot_id=? AND open_event_seq=?)",
                            (after.lot_id, bot_id, open_seq)).fetchone():
                        raise LotStorageError("lot_exists")
                else:
                    if head is None:
                        raise LotStorageError("lot_not_found")
                    if expected != head["current_revision"]:
                        raise LotStorageError("revision_conflict")
                    previous = self._decode_revision(self._row(bot_id, after.lot_id, expected), binding)
                    self._transition(previous, after, opening, closing)
                if binding.last_commit_seq == ipc.MAX_INTEGER:
                    raise LotStorageError("sequence_exhausted")
                seq = binding.last_commit_seq + 1
                if operation == "CREATE":
                    self.db.execute("INSERT INTO lot_heads VALUES (?,?,?,?,?,?)",
                                    (after.lot_id, bot_id, open_seq, after.open_intent_key,
                                     after.side, after.revision))
                wire = self.codec.lot_to_wire(after)
                values = dict(lot_id=after.lot_id, bot_id=bot_id, revision=after.revision,
                              expected_revision=expected, write_id=write_id, commit_seq=seq,
                              operation=operation, **{name: wire[name] for name in self.financial},
                              **wire["protection"], opening_unresolved=int(opening),
                              closing_unresolved=int(closing), request_json=request,
                              request_hash=_hash(request))
                if self.v2:
                    quality = wire["fee_quality"]
                    values.update(fee_coverage=quality["coverage"], known_fee_subtotal=quality["known_fee_subtotal"],
                                  fee_unknown_fill_count=quality["fee_unknown_fill_count"])
                columns = ",".join(values)
                self.db.execute(f"INSERT INTO lot_revisions ({columns}) VALUES ({','.join('?' for _ in values)})",
                                tuple(values.values()))
                if operation == "REPLACE":
                    updated = self.db.execute("""UPDATE lot_heads SET current_revision=?
                        WHERE lot_id=? AND bot_id=? AND current_revision=?""",
                        (after.revision, after.lot_id, bot_id, expected)).rowcount
                    if updated != 1:
                        raise LotStorageError("revision_conflict")
                updated = self.db.execute("""UPDATE lot_bindings SET last_commit_seq=?
                    WHERE bot_id=? AND last_commit_seq=?""", (seq, bot_id, binding.last_commit_seq)).rowcount
                if updated != 1:
                    raise LotStorageError("integrity_error")
                receipt = self._receipt(values)
        # The context manager has successfully returned from COMMIT before ACK.
        return receipt

    def get(self, *, scope, bot_id, lot_id):
        return self._get(scope, bot_id, lot_id, None)

    def get_revision(self, *, scope, bot_id, lot_id, revision):
        # None denotes latest only in the private helper.
        if type(revision) is not int or not 1 <= revision <= ipc.MAX_INTEGER:
            raise LotStorageError("invalid_transition")
        return self._get(scope, bot_id, lot_id, revision)

    def _get(self, scope, bot_id, lot_id, revision):
        with self._access():
            binding = self._binding(scope, bot_id)
            lots._hex_id(lot_id)
            head = self._head(binding, lot_id)
            if head is None:
                return None
            target = head["current_revision"] if revision is None else revision
            row = self._row(bot_id, lot_id, target)
            if row is None:
                if target <= head["current_revision"]:
                    raise LotStorageError("integrity_error")
                return None
            return self._decode_revision(row, binding)

    def list_current(self, *, scope, bot_id, after_lot_id=None, limit=100):
        with self._access():
            binding = self._binding(scope, bot_id)
            if type(limit) is not int or not 1 <= limit <= 1000:
                raise LotStorageError("invalid_transition")
            if after_lot_id is not None:
                lots._hex_id(after_lot_id)
            heads = self.db.execute("""SELECT lot_id,current_revision FROM lot_heads
                WHERE bot_id=? AND lot_id>? ORDER BY lot_id LIMIT ?""",
                (bot_id, after_lot_id or "", limit)).fetchall()
            result = []
            for head in heads:
                self._head(binding, head["lot_id"])
                row = self._row(bot_id, head["lot_id"], head["current_revision"])
                result.append(self._decode_revision(row, binding))
            return tuple(result)

    def recover(self):
        with self._access():
            return self._recover_in_transaction()

    def _recover_in_transaction(self):
        """Initialization uses the existing transaction, never a nested BEGIN."""
        try:
            return self._scan()
        except LotStorageError:
            self._failed = True
            raise
        except (ValueError, TypeError, sqlite3.Error) as exc:
            self._failed = True
            raise LotStorageError("integrity_error") from exc

    def _scan(self):
        if not self.db.in_transaction:
            raise LotStorageError("storage_unavailable")
        if (self.db.execute("PRAGMA user_version").fetchone()[0] != self.schema_version
                or self.db.execute("PRAGMA foreign_keys").fetchone()[0] != 1
                or self.db.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal"
                or self.db.execute("PRAGMA synchronous").fetchone()[0] != 2):
            raise LotStorageError("integrity_error")
        # Compare the fixed local DDL, including CHECKs, keys and deferred FKs.
        # No user-provided SQL or generic migration framework is involved.
        for name, statement in zip(TABLES, self.schema):
            row = self.db.execute("SELECT type,sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
            if (row is None or row["type"] != "table"
                    or "".join(row["sql"].split()) != "".join(statement.split())):
                raise LotStorageError("integrity_error")
            if self.db.execute(f"PRAGMA foreign_key_check({name})").fetchone() is not None:
                raise LotStorageError("integrity_error")
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name IN (?,?,?)",
                           TABLES).fetchone():
            raise LotStorageError("integrity_error")
        if [row[0] for row in self.db.execute("PRAGMA quick_check")] != ["ok"]:
            raise LotStorageError("integrity_error")
        binding_count = lot_count = revision_count = unresolved = 0
        for raw in self.db.execute("SELECT * FROM lot_bindings ORDER BY bot_id"):
            binding = self._decode_binding(raw)
            binding_count += 1
            last_seq = 0
            latest = {}
            for row in self.db.execute(_SELECT + " WHERE r.bot_id=? ORDER BY r.commit_seq",
                                       (binding.bot_id,)):
                current = self._decode_revision(row, binding)
                if current.commit_seq != last_seq + 1:
                    raise LotStorageError("integrity_error")
                previous = latest.get(current.lot.lot_id)
                if previous is None:
                    if current.lot.revision != 1 or row["operation"] != "CREATE":
                        raise LotStorageError("integrity_error")
                else:
                    if (current.lot.revision != previous.lot.revision + 1
                            or row["expected_revision"] != previous.lot.revision):
                        raise LotStorageError("integrity_error")
                    try:
                        self._transition(previous, current.lot,
                                         current.opening_unresolved, current.closing_unresolved)
                    except LotStorageError as exc:
                        raise LotStorageError("integrity_error") from exc
                latest[current.lot.lot_id] = current
                last_seq = current.commit_seq
                revision_count += 1
            heads = self.db.execute("SELECT * FROM lot_heads WHERE bot_id=?", (binding.bot_id,)).fetchall()
            if last_seq != binding.last_commit_seq or {h["lot_id"] for h in heads} != set(latest):
                raise LotStorageError("integrity_error")
            for head in heads:
                current = latest[head["lot_id"]]
                if head["current_revision"] != current.lot.revision:
                    raise LotStorageError("integrity_error")
                lot_count += 1
                unresolved += int(current.opening_unresolved or current.closing_unresolved)
        return LotRecoveryReport(True, binding_count, lot_count, revision_count, unresolved)
