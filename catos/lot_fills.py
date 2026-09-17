"""Isolated synthetic fill journal, using the existing Journal transaction."""

from dataclasses import dataclass, replace
from decimal import Decimal
import sqlite3

from catos import ipc, ipc_lots, lots
from catos.lot_accounting import SyntheticFill, apply_fill, exact_quantity
from catos.lot_journal import (LotStorageError, _json, _decode_json, _hash,
                               _contract_wire, _contract_from_wire, _numeric_identity)


TABLES = ("lot_fill_orders", "lot_fill_events", "lot_fill_terminals")
_COMMON = """seq INTEGER NOT NULL UNIQUE CHECK(seq>0),
    request_json TEXT NOT NULL CHECK(length(CAST(request_json AS BLOB)) BETWEEN 1 AND 65536),
    request_hash TEXT NOT NULL CHECK(length(request_hash)=64),
    lot_id TEXT, revision INTEGER, commit_seq INTEGER,
    CHECK((lot_id IS NULL AND revision IS NULL AND commit_seq IS NULL)
       OR (lot_id IS NOT NULL AND revision IS NOT NULL AND commit_seq IS NOT NULL
           AND revision>0 AND commit_seq>0)),
    FOREIGN KEY(lot_id,revision) REFERENCES lot_revisions(lot_id,revision),
    UNIQUE(lot_id,revision)"""
SCHEMA = (
    f"""CREATE TABLE lot_fill_orders (
        order_key TEXT PRIMARY KEY NOT NULL,
        bot_id TEXT NOT NULL REFERENCES lot_bindings(bot_id),
        event_seq INTEGER NOT NULL CHECK(event_seq>0),
        managed_lot_id TEXT NOT NULL,
        intent_key TEXT NOT NULL UNIQUE,
        resolved_quantity TEXT NOT NULL,
        {_COMMON}, UNIQUE(bot_id,event_seq)
    ) STRICT""",
    f"""CREATE TABLE lot_fill_events (
        order_key TEXT NOT NULL REFERENCES lot_fill_orders(order_key),
        trade_id TEXT NOT NULL, fill_seq INTEGER NOT NULL CHECK(fill_seq>0),
        quantity TEXT NOT NULL, price TEXT NOT NULL, fee_paid TEXT NOT NULL,
        fee_currency TEXT NOT NULL CHECK(fee_currency='USDT'),
        {_COMMON}, PRIMARY KEY(order_key,trade_id), UNIQUE(order_key,fill_seq)
    ) STRICT""",
    f"""CREATE TABLE lot_fill_terminals (
        order_key TEXT PRIMARY KEY NOT NULL REFERENCES lot_fill_orders(order_key),
        terminal_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('FILLED','CANCELED','REJECTED')),
        final_fill_seq INTEGER NOT NULL CHECK(final_fill_seq>=0),
        final_filled_qty TEXT NOT NULL,
        {_COMMON}
    ) STRICT""",
)


def install_schema(db):
    for name in TABLES:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone():
            raise LotStorageError("integrity_error")
    for sql in SCHEMA:
        db.execute(sql)


def _number(value):
    sign, coefficient, exponent = _numeric_identity(value)
    return str(Decimal((sign, tuple(map(int, coefficient)), exponent)))


def _key(scope, source_id, inst_id, order_id):
    if not isinstance(scope, lots.LotScope):
        raise LotStorageError("scope_mismatch")
    for value in (source_id, inst_id, order_id):
        ipc.token(value, "source/order identity")
    return _hash(_json(dict(account_ref=scope.account_ref, environment=scope.environment,
                            source_id=source_id, inst_id=inst_id, order_id=order_id)))


@dataclass(frozen=True, slots=True)
class EventReceipt:
    event_seq: int
    request_hash: str
    lot_id: str | None
    revision: int | None
    commit_seq: int | None
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    storage_ready: bool
    order_count: int
    fill_count: int
    terminal_count: int


class LotFillJournal:
    def __init__(self, journal):
        self.j = journal
        self.db = journal.connection

    def _managed(self, lot_id):
        return self.db.execute("SELECT 1 FROM lot_fill_orders WHERE managed_lot_id=?", (lot_id,)).fetchone() is not None

    @staticmethod
    def _receipt(row, replayed=False):
        return EventReceipt(row["seq"], row["request_hash"], row["lot_id"],
                            row["revision"], row["commit_seq"], replayed)

    def bind_order(self, *, source_id, order_id, context, intent):
        context = lots.IntentContext(context.scope, context.bot_id, context.contract,
                                     context.event_seq, context.warmup)
        self.j.lots._scope(context.scope)
        if not isinstance(intent, (lots.OpenLot, lots.CloseLot)):
            raise LotStorageError("invalid_intent")
        # S1 canonical intent normalizes input Decimal representations.
        wire = ipc.decode_payload(ipc_lots.canonical_intent(intent))
        contract = _contract_wire(context.contract)
        for name in contract:
            if name != "inst_id":
                contract[name] = _number(getattr(context.contract, name))
        payload = dict(kind="bind", scope=ipc_lots._scope_to_wire(context.scope),
                       source_id=source_id, order_id=order_id, bot_id=context.bot_id,
                       contract=contract, event_seq=context.event_seq, warmup=context.warmup,
                       intent=wire)
        return self._append(payload)

    def apply_fill(self, fill):
        fill = replace(fill)
        self.j.lots._scope(fill.scope)
        payload = dict(kind="fill", scope=ipc_lots._scope_to_wire(fill.scope),
                       source_id=fill.source_id, inst_id=fill.inst_id, order_id=fill.order_id,
                       trade_id=fill.trade_id, fill_seq=fill.fill_seq,
                       quantity=_number(fill.quantity), price=_number(fill.price),
                       fee_paid=_number(fill.fee_paid), fee_currency=fill.fee_currency)
        return self._append(payload)

    def finish_order(self, *, scope, source_id, inst_id, order_id, terminal_id,
                     status, final_fill_seq, final_filled_qty):
        self.j.lots._scope(scope)
        ipc.token(terminal_id, "terminal_id")
        ipc.integer(final_fill_seq, "final_fill_seq")
        lots._decimal(final_filled_qty, "invalid_quantity", derived=True, nonnegative=True)
        if status not in ("FILLED", "CANCELED", "REJECTED"):
            raise LotStorageError("invalid_terminal")
        return self._append(dict(kind="terminal", scope=ipc_lots._scope_to_wire(scope),
                                 source_id=source_id, inst_id=inst_id, order_id=order_id,
                                 terminal_id=terminal_id, status=status, final_fill_seq=final_fill_seq,
                                 final_filled_qty=_number(final_filled_qty)))

    @staticmethod
    def _identity(p):
        scope = ipc_lots._scope_from_wire(p["scope"])
        inst = p["contract"]["inst_id"] if p["kind"] == "bind" else p["inst_id"]
        return _key(scope, p["source_id"], inst, p["order_id"])

    def _rows(self):
        rows = []
        for kind, table in zip(("bind", "fill", "terminal"), TABLES):
            for row in self.db.execute(f"SELECT * FROM {table}"):
                rows.append((row["seq"], kind, dict(row)))
        return sorted(rows, key=lambda entry: entry[0])

    def _evaluate(self, payloads):
        """One deterministic state machine for new events and startup replay."""
        orders, states, active, origins, used_events = {}, {}, {}, {}, set()
        results = []
        for p in payloads:
            kind, key = p["kind"], self._identity(p)
            scope = ipc_lots._scope_from_wire(p["scope"])
            self.j.lots._scope(scope)
            after = None
            opening = closing = False
            if kind == "bind":
                ipc.exact(p, ("kind", "scope", "source_id", "order_id", "bot_id", "contract", "event_seq", "warmup", "intent"))
                if key in orders:
                    raise LotStorageError("binding_conflict")
                contract = _contract_from_wire(p["contract"])
                binding = self.j.lots._binding(scope, p["bot_id"])
                if contract != binding.contract:
                    raise LotStorageError("binding_conflict")
                context = lots.IntentContext(scope, p["bot_id"], contract, p["event_seq"], p["warmup"])
                intent = ipc_lots.intent_from_wire(p["intent"])
                if not isinstance(intent, (lots.OpenLot, lots.CloseLot)):
                    raise LotStorageError("invalid_intent")
                event_key = (context.bot_id, context.event_seq)
                if event_key in used_events:
                    raise LotStorageError("binding_conflict")
                used_events.add(event_key)
                lot_id = lots.make_lot_id(lots.make_intent_key(context)) if isinstance(intent, lots.OpenLot) else intent.lot_id
                before = states.get(lot_id)
                if lot_id in active:
                    raise LotStorageError("lot_busy")
                if isinstance(intent, lots.OpenLot):
                    if lot_id in origins:
                        raise LotStorageError("lot_exists")
                    origins[lot_id] = context.event_seq
                elif lot_id not in origins or before is None:
                    raise LotStorageError("unmanaged_lot")
                validated = lots.validate_intent(intent, context, lots.LotValidationView(before, False, False))
                order = dict(validated=validated, contract=contract, total=Decimal(0), count=0,
                             trades=set(), done=False, lot_id=lot_id, bot_id=context.bot_id)
                orders[key] = order
                active[lot_id] = key
                if before is not None:
                    after, closing = replace(before, revision=before.revision + 1), True
            else:
                order = orders.get(key)
                if order is None or order["done"]:
                    raise LotStorageError("order_unavailable")
                validated, contract, lot_id = order["validated"], order["contract"], order["lot_id"]
                before = states.get(lot_id)
                if kind == "fill":
                    ipc.exact(p, ("kind", "scope", "source_id", "inst_id", "order_id", "trade_id", "fill_seq", "quantity", "price", "fee_paid", "fee_currency"))
                    fill = SyntheticFill(scope, p["source_id"], p["inst_id"], p["order_id"], p["trade_id"],
                                         p["fill_seq"], ipc_lots._parse_decimal(p["quantity"], "quantity", derived=True, positive=True),
                                         ipc.decimal_text(p["price"], "price", positive=True),
                                         ipc.decimal_text(p["fee_paid"], "fee_paid"), p["fee_currency"])
                    if fill.fill_seq != order["count"] + 1 or fill.trade_id in order["trades"]:
                        raise LotStorageError("fill_sequence_conflict")
                    total = exact_quantity(order["total"], fill.quantity)
                    if total > validated.resolved_quantity:
                        raise LotStorageError("over_fill")
                    after = apply_fill(before, validated, contract, fill)
                    opening = isinstance(validated.intent, lots.OpenLot)
                    closing = not opening
                    order.update(total=total, count=fill.fill_seq)
                    order["trades"].add(fill.trade_id)
                elif kind == "terminal":
                    ipc.exact(p, ("kind", "scope", "source_id", "inst_id", "order_id", "terminal_id", "status", "final_fill_seq", "final_filled_qty"))
                    ipc.token(p["terminal_id"], "terminal_id")
                    ipc.integer(p["final_fill_seq"], "final_fill_seq")
                    total = ipc_lots._parse_decimal(p["final_filled_qty"], "final_filled_qty", derived=True)
                    if (p["final_fill_seq"] != order["count"] or total != order["total"]
                            or p["status"] not in ("FILLED", "CANCELED", "REJECTED")
                            or (p["status"] == "FILLED" and total != validated.resolved_quantity)
                            or (p["status"] == "REJECTED" and total != 0)):
                        raise LotStorageError("terminal_conflict")
                    order["done"] = True
                    del active[lot_id]
                    if before is not None:
                        after = replace(before, revision=before.revision + 1)
                else:
                    raise LotStorageError("invalid_event")
            if after is not None:
                states[lot_id] = after
            results.append((order, after, opening, closing, origins[lot_id]))
        return orders, states, results

    def _columns(self, p, result):
        order, after, _, _, _ = result
        columns = dict(order_key=self._identity(p))
        if p["kind"] == "bind":
            columns.update(bot_id=p["bot_id"], event_seq=p["event_seq"], managed_lot_id=order["lot_id"],
                           intent_key=order["validated"].intent_key,
                           resolved_quantity=_number(order["validated"].resolved_quantity))
        elif p["kind"] == "fill":
            columns.update({n: p[n] for n in ("trade_id", "fill_seq", "quantity", "price", "fee_paid", "fee_currency")})
        else:
            columns.update({n: p[n] for n in ("terminal_id", "status", "final_fill_seq", "final_filled_qty")})
        return columns

    def _recover_in_transaction(self):
        try:
            if not self.db.in_transaction:
                raise LotStorageError("storage_unavailable")
            for name, sql in zip(TABLES, SCHEMA):
                row = self.db.execute("SELECT type,sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
                if row is None or row["type"] != "table" or "".join(row["sql"].split()) != "".join(sql.split()):
                    raise ValueError("schema")
                if self.db.execute(f"PRAGMA foreign_key_check({name})").fetchone():
                    raise ValueError("foreign key")
                if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (name,)).fetchone():
                    raise ValueError("trigger")
            rows = self._rows()
            payloads = []
            for expected, (seq, kind, row) in enumerate(rows, 1):
                p = _decode_json(row["request_json"])
                if seq != expected or p["kind"] != kind or _json(p) != row["request_json"] or _hash(row["request_json"]) != row["request_hash"]:
                    raise ValueError("event sequence/hash")
                payloads.append(p)
            orders, states, results = self._evaluate(payloads)
            referenced = set()
            for (_, _, row), p, result in zip(rows, payloads, results):
                for name, value in self._columns(p, result).items():
                    if row[name] != value:
                        raise ValueError("event columns")
                order, after, opening, closing, origin = result
                if after is None:
                    if any(row[n] is not None for n in ("lot_id", "revision", "commit_seq")):
                        raise ValueError("empty receipt")
                    continue
                if row["lot_id"] != after.lot_id or row["revision"] != after.revision:
                    raise ValueError("version link")
                binding = self.j.lots._binding(after.scope, after.bot_id)
                stored_row = self.j.lots._row(after.bot_id, after.lot_id, after.revision)
                stored = self.j.lots._decode_revision(stored_row, binding)
                if (stored.lot != after or stored.opening_unresolved != opening
                        or stored.closing_unresolved != closing or stored.commit_seq != row["commit_seq"]
                        or stored_row["write_id"] != self._write_id(row["seq"], row["request_hash"])):
                    raise ValueError("accounting mismatch")
                reference = (after.lot_id, after.revision)
                if reference in referenced:
                    raise ValueError("duplicate version")
                referenced.add(reference)
            managed = {o["lot_id"] for o in orders.values()}
            for row in self.db.execute("SELECT lot_id,revision,write_id FROM lot_revisions"):
                if row["lot_id"] in managed or row["write_id"].startswith("s3_"):
                    if (row["lot_id"], row["revision"]) not in referenced:
                        raise ValueError("orphan version")
            return rows, payloads, orders, states
        except (ValueError, TypeError, KeyError, sqlite3.Error, LotStorageError) as exc:
            self.j.lots._failed = True
            raise LotStorageError("integrity_error") from exc

    @staticmethod
    def _write_id(seq, fingerprint):
        return "s3_" + _hash(_json(dict(seq=seq, fingerprint=fingerprint)))[:61]

    def _append(self, p):
        text = _json(p)
        fingerprint = _hash(text)
        key = self._identity(p)
        table = dict(bind=TABLES[0], fill=TABLES[1], terminal=TABLES[2])[p["kind"]]
        with self.j.lots._access():
            rows, payloads, orders, states = self._recover_in_transaction()
            query, args = f"SELECT * FROM {table} WHERE order_key=?", [key]
            if p["kind"] == "fill":
                query += " AND trade_id=?"
                args.append(p["trade_id"])
            old = self.db.execute(query, args).fetchone()
            if old is not None:
                if old["request_json"] != text:
                    raise LotStorageError("write_conflict")
                receipt = self._receipt(old, True)
            else:
                seq = len(rows) + 1
                ipc.integer(seq, "event sequence", 1)
                _, _, results = self._evaluate(payloads + [p])
                result = results[-1]
                order, after, opening, closing, origin = result
                if p["kind"] == "bind" and isinstance(order["validated"].intent, lots.OpenLot):
                    if self.db.execute("SELECT 1 FROM lot_heads WHERE lot_id=?", (order["lot_id"],)).fetchone():
                        raise LotStorageError("unmanaged_lot")
                values = self._columns(p, result)
                values.update(seq=seq, request_json=text, request_hash=fingerprint,
                              lot_id=None, revision=None, commit_seq=None)
                if after is not None:
                    saved = self.j.lots._write(after.scope, after.bot_id, self._write_id(seq, fingerprint),
                                              "CREATE" if after.revision == 1 else "REPLACE",
                                              origin if after.revision == 1 else None, after.revision - 1,
                                              after, opening, closing, _in_transaction=True)
                    values.update(lot_id=saved.lot_id, revision=saved.revision, commit_seq=saved.commit_seq)
                self.db.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
                receipt = self._receipt(values)
        return receipt

    def recover(self):
        with self.j.lots._access():
            self.j.lots._recover_in_transaction()
            rows, _, orders, _ = self._recover_in_transaction()
            return RecoveryReport(True, len(orders), sum(k == "fill" for _, k, _ in rows),
                                  sum(k == "terminal" for _, k, _ in rows))

    def get_order(self, *, scope, source_id, inst_id, order_id):
        self.j.lots._scope(scope)
        key = _key(scope, source_id, inst_id, order_id)
        with self.j.lots._access():
            self._recover_in_transaction()
            row = self.db.execute("SELECT * FROM lot_fill_orders WHERE order_key=?", (key,)).fetchone()
            return None if row is None else self._receipt(row)

    def list_fills(self, *, scope, source_id, inst_id, order_id, after_fill_seq=0, limit=100):
        self.j.lots._scope(scope)
        ipc.integer(after_fill_seq, "after_fill_seq")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise LotStorageError("invalid_limit")
        key = _key(scope, source_id, inst_id, order_id)
        with self.j.lots._access():
            self._recover_in_transaction()
            return tuple(self._receipt(row) for row in self.db.execute(
                "SELECT * FROM lot_fill_events WHERE order_key=? AND fill_seq>? ORDER BY fill_seq LIMIT ?",
                (key, after_fill_seq, limit)))
