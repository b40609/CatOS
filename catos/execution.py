"""G lifecycle operations, executed only on Journal's existing single writer."""

from dataclasses import replace
from decimal import Decimal, localcontext
import json

from catos import ipc, research, risk
from catos.fake_exchange import build_payload
from catos.journal import JournalError, OwnershipError, canonical, digest

D = Decimal
TERMINAL = ("FILLED", "CANCELED", "REJECTED", "ABORTED")
SCHEMA = (
    "CREATE TABLE execution_mode (id INTEGER PRIMARY KEY CHECK(id=1))",
    """CREATE TABLE execution_orders (
       order_key TEXT PRIMARY KEY, cl_ord_id TEXT NOT NULL UNIQUE,
       intent_key TEXT UNIQUE REFERENCES intents(intent_key), bot_id TEXT NOT NULL REFERENCES bots(bot_id),
       payload_json TEXT NOT NULL, quantity TEXT NOT NULL CHECK(typeof(quantity)='text'), filled TEXT NOT NULL CHECK(typeof(filled)='text'),
       reservation TEXT NOT NULL CHECK(typeof(reservation)='text'), state TEXT NOT NULL, cancel_pending INTEGER NOT NULL DEFAULT 0,
       settled INTEGER NOT NULL DEFAULT 0, deadline INTEGER NOT NULL, epoch INTEGER NOT NULL,
       exchange_id TEXT UNIQUE, report_revision INTEGER NOT NULL DEFAULT 0, report_json TEXT)""",
    """CREATE TABLE execution_fills (
       exchange_id TEXT NOT NULL, trade_id TEXT NOT NULL, order_key TEXT NOT NULL REFERENCES execution_orders(order_key),
       quantity TEXT NOT NULL CHECK(typeof(quantity)='text'), price TEXT NOT NULL CHECK(typeof(price)='text'), fee TEXT NOT NULL CHECK(typeof(fee)='text'),
       PRIMARY KEY(exchange_id,trade_id))""",
)


class ExecutionJournal:
    def __init__(self, journal):
        self.j = journal
        self.db = journal.connection

    def order(self, key):
        row = self.db.execute("SELECT * FROM execution_orders WHERE order_key=?", (key,)).fetchone()
        if row is None:
            raise JournalError("unknown local order")
        return dict(row)

    def unresolved(self):
        return [dict(row) for row in self.db.execute("SELECT * FROM execution_orders WHERE settled=0 ORDER BY rowid")]

    def _dirty(self, bot_id):
        self.db.execute("UPDATE bots SET revision=revision+1 WHERE bot_id=?", (bot_id,))
        self.db.execute("UPDATE ownership SET reconciled_revision=NULL,fills_reconciled=0 WHERE bot_id=?", (bot_id,))
        self.db.execute("UPDATE control SET health='RECONCILING'")

    def _release(self, key):
        row = self.order(key)
        if row["intent_key"] is not None:
            for table in ("reservations", "outbox", "risk_orders"):
                self.db.execute(f"DELETE FROM {table} WHERE intent_key=?", (row["intent_key"],))
        self.db.execute("UPDATE execution_orders SET settled=1,cancel_pending=0 WHERE order_key=?", (key,))

    def _insert(self, key, bot, qty, reduce_only, deadline, epoch, amount, intent=None, state="SUBMITTING"):
        cl_id = digest(key)[:32]
        collision = self.db.execute("SELECT order_key FROM execution_orders WHERE cl_ord_id=?", (cl_id,)).fetchone()
        if collision is not None:
            raise JournalError("permanent client order id collision")
        contract = self.j._checkpoint(bot).config.contract
        payload = build_payload(contract, cl_id, qty, reduce_only)
        self.db.execute("""INSERT INTO execution_orders
            (order_key,cl_ord_id,intent_key,bot_id,payload_json,quantity,filled,reservation,state,deadline,epoch)
            VALUES (?,?,?,?,?,?,'0',?,?,?,?)""",
            (key, cl_id, intent, bot["bot_id"], canonical(payload), str(qty), str(amount), state, deadline, epoch))
        return dict(order_key=key, payload=payload, epoch=epoch, risk_seq=self.j.risk_state().seq,
                    risk_time=self.j.risk_state().time_ms)

    def _known(self, owner, position, *, allow_unknown_increase=False):
        return (owner["position"] is not None and D(owner["position"]) == position
                and owner["reconciled_revision"] is not None and owner["fills_reconciled"]
                and (owner["unknown_count"] == 0 or allow_unknown_increase) and owner["conditional_open"] == 0)

    def prepare(self, bot_id, intent_key, now_ms):
        ipc.integer(now_ms, "submit time")
        with self.j._transaction(), localcontext(research._CONTEXT):
            old = self.db.execute("SELECT order_key FROM execution_orders WHERE order_key=?", (intent_key,)).fetchone()
            if old is not None:
                return None  # NEVER resend, including a terminal order with the same key.
            bot, owner = self.j._require_owner(bot_id)
            row = self.db.execute("""SELECT i.*,r.quantity,r.reduce_only,r.eligible,v.amount,p.input_json
                FROM intents i JOIN risk_orders r USING(intent_key) JOIN reservations v USING(intent_key)
                JOIN inputs p ON p.bot_id=i.bot_id AND p.seq=i.seq WHERE i.intent_key=? AND i.bot_id=?""",
                (intent_key, bot_id)).fetchone()
            if row is None or bot["isolated"]:
                raise JournalError("only committed risk-approved intents can be submitted")
            state = self.j.risk_state()
            qty = D(row["quantity"])
            deadline = json.loads(row["input_json"])["expires_at_ms"]
            buys, sells, reduction = D("0"), D("0"), False
            for held in self.db.execute("SELECT quantity,reduce_only FROM risk_orders WHERE intent_key<>?", (intent_key,)):
                value = D(held["quantity"])
                buys += max(value, D("0"))
                sells += max(-value, D("0"))
                reduction |= bool(held["reduce_only"])
            s = state.snapshot
            position = D(owner["position"]) if owner["position"] is not None else D("0")
            verdict = risk.evaluate(state, self.j.risk_limits, self.j._checkpoint(bot).config.contract,
                D(row["target"]), position, now_ms, held_buy=buys, held_sell=sells,
                held_reduction=reduction, reconciled=self._known(owner, position))
            allowed = (s is not None and row["eligible"] and row["epoch"] == state.epoch
                       and now_ms < deadline and verdict.accepted and verdict.quantity == qty
                       and verdict.reduce_only == bool(row["reduce_only"]) and not self.unresolved())
            request = self._insert(intent_key, bot, qty, bool(row["reduce_only"]), deadline,
                                   state.epoch, D(row["amount"]), intent_key,
                                   "SUBMITTING" if allowed else "ABORTED")
            if not allowed:
                self._release(intent_key)
                return None
            self._dirty(bot_id)
            return request

    def abort_unsent(self, key):
        """Only called before entering FakeExchange.submit, while holding the operation slot."""
        with self.j._transaction():
            row = self.order(key)
            if row["state"] != "SUBMITTING":
                raise JournalError("cannot prove order remained unsent")
            self.db.execute("UPDATE execution_orders SET state='ABORTED' WHERE order_key=?", (key,))
            self._release(key)
            self._dirty(row["bot_id"])

    def uncertain(self, key):
        with self.j._transaction():
            row = self.order(key)
            if not row["settled"]:
                self.db.execute("UPDATE execution_orders SET state='UNKNOWN' WHERE order_key=?", (key,))
                self._dirty(row["bot_id"])

    def start_cancel(self, key):
        with self.j._transaction():
            row = self.order(key)
            if row["settled"] or row["cancel_pending"] or row["state"] in ("UNKNOWN", "SUBMITTING"):
                return None
            self.db.execute("UPDATE execution_orders SET cancel_pending=1 WHERE order_key=?", (key,))
            self._dirty(row["bot_id"])
            return row["cl_ord_id"]

    def apply(self, key, report):
        data = report.to_wire()
        wire = canonical(data)
        with self.j._transaction(), localcontext(research._CONTEXT):
            row = self.order(key)
            if report.cl_ord_id != row["cl_ord_id"]:
                raise JournalError("report client id mismatch")
            if report.status == "NOT_FOUND":
                # Absence from one query is not proof of nonacceptance.
                return row
            if row["state"] == "ABORTED":
                raise JournalError("report contradicts proven unsent order")
            if report.exchange_id is None or (row["exchange_id"] is not None and report.exchange_id != row["exchange_id"]):
                raise JournalError("report exchange id mismatch")
            if report.revision <= row["report_revision"]:
                if report.revision == row["report_revision"] and wire == row["report_json"]:
                    return row
                raise JournalError("stale or conflicting report evidence")
            quantity = D(row["quantity"])
            total = D(row["filled"])
            delta = D("0")
            seen = set()
            for fill in report.fills:
                contract = self.j._checkpoint(self.j._bot(row["bot_id"])).config.contract
                if fill.quantity % contract.lot_size != 0:
                    raise JournalError("fill violates contract lot size")
                if fill.trade_id in seen:
                    raise JournalError("duplicate trade id inside report")
                seen.add(fill.trade_id)
                old = self.db.execute("SELECT * FROM execution_fills WHERE exchange_id=? AND trade_id=?",
                                      (report.exchange_id, fill.trade_id)).fetchone()
                if old is not None:
                    if (old["order_key"] != key or D(old["quantity"]) != fill.quantity
                            or D(old["price"]) != fill.price or D(old["fee"]) != fill.fee):
                        raise JournalError("same fill id with conflicting content")
                    continue
                self.db.execute("INSERT INTO execution_fills VALUES (?,?,?,?,?,?)",
                    (report.exchange_id, fill.trade_id, key, str(fill.quantity), str(fill.price), str(fill.fee)))
                delta += fill.quantity
            total += delta
            previous_cumulative = D("0") if row["report_json"] is None else D(json.loads(row["report_json"])["cumulative"])
            if report.cumulative < previous_cumulative:
                raise JournalError("cumulative fill evidence cannot regress")
            if total > abs(quantity) or report.cumulative < total or report.cumulative > abs(quantity):
                raise JournalError("inconsistent cumulative fill")
            if report.complete and report.cumulative != total:
                raise JournalError("complete evidence is missing trades")
            if report.status == "FILLED" and report.cumulative != abs(quantity):
                raise JournalError("filled report must account for full order")
            if report.status == "REJECTED" and report.cumulative != 0:
                raise JournalError("rejected order cannot have fills")
            bot, owner = self.j._require_owner(row["bot_id"])
            if owner["position"] is None:
                raise OwnershipError("fills require a reconciled initial position")
            if json.loads(row["payload_json"])["reduceOnly"] and delta > 0:
                prior = D(owner["position"])
                if prior * quantity >= 0 or delta > abs(prior):
                    raise JournalError("reduceOnly fill would increase or cross zero")
            position = D(owner["position"]) + (delta if quantity > 0 else -delta)
            self.db.execute("UPDATE ownership SET position=? WHERE bot_id=?", (str(position), row["bot_id"]))
            self.db.execute("""UPDATE execution_orders SET filled=?,state=?,exchange_id=?,report_revision=?,report_json=?,settled=0
                               WHERE order_key=?""", (str(total), report.status, report.exchange_id, report.revision, wire, key))
            if row["intent_key"] is not None:
                remaining = (abs(quantity) - total) * (D("1") if quantity > 0 else D("-1"))
                self.db.execute("INSERT OR REPLACE INTO reservations VALUES (?,?)", (row["intent_key"], row["reservation"]))
                self.db.execute("INSERT OR REPLACE INTO outbox VALUES (?,'HELD_SIMULATION',?)", (row["intent_key"], row["epoch"]))
                reduce_only = json.loads(row["payload_json"])["reduceOnly"]
                self.db.execute("INSERT OR REPLACE INTO risk_orders VALUES (?,?,?,0)", (row["intent_key"], str(remaining), int(reduce_only)))
            # Release only on terminal AND complete trade evidence, never cancel ACK.
            if report.status in TERMINAL and report.complete:
                self._release(key)
            self._dirty(row["bot_id"])
            state = self.j.risk_state()
            if state.mode == "FLAT" and (delta != 0 or not self.order(key)["settled"]):
                self.j._write_risk(replace(state, phase="WORKING"))
            return self.order(key)

    def check_reconciliation(self, owner, evidence):
        expected = D("0") if owner["position"] is None else D(owner["position"])
        if evidence.position != expected:
            raise OwnershipError("position discrepancy; foreign or missing fills cannot be adopted")
        unresolved = self.unresolved()
        unknown = sum(row["state"] in ("UNKNOWN", "SUBMITTING") for row in unresolved)
        if evidence.unknown_count < unknown:
            raise OwnershipError("UNKNOWN requires order evidence, not an account snapshot")
        live = sum(row["state"] in ("LIVE", "PARTIAL") for row in unresolved)
        if evidence.ordinary_open != live:
            raise OwnershipError("ordinary order inventory disagrees with managed orders")
        if any(row["state"] in TERMINAL for row in unresolved) and evidence.fills_reconciled:
            raise OwnershipError("terminal order lacks complete fill evidence")

    def flatten(self, bot_id, now_ms, deadline):
        """One durable reduction child at a time, within the original flatten operation."""
        ipc.integer(now_ms, "flatten time")
        ipc.integer(deadline, "flatten deadline")
        with self.j._transaction(), localcontext(research._CONTEXT):
            bot, owner = self.j._require_owner(bot_id)
            state = self.j.risk_state()
            if state.mode != "FLAT" or deadline <= now_ms:
                raise JournalError("active FLAT and future deadline required")
            # Unsent old intents can be ended locally; they were never handed off.
            for held in list(self.db.execute("""SELECT i.intent_key FROM intents i JOIN outbox o USING(intent_key)
                        LEFT JOIN execution_orders e ON e.intent_key=i.intent_key WHERE e.order_key IS NULL""")):
                key = held[0]
                r = self.db.execute("SELECT * FROM risk_orders WHERE intent_key=?", (key,)).fetchone()
                if r is None:
                    raise JournalError("fixture order is not executable")
                self._insert(key, bot, D(r["quantity"]), bool(r["reduce_only"]), deadline, state.epoch, D("0"), key, "ABORTED")
                self._release(key)
            unresolved = self.unresolved()
            if any(json.loads(row["payload_json"])["reduceOnly"] for row in unresolved):
                return None
            position = D("0") if owner["position"] is None else D(owner["position"])
            # Unknown increases can still fill later; an accurate proven position
            # is required now. No global wait-for-all-cancels barrier is invented.
            verdict = risk.evaluate(state, self.j.risk_limits, self.j._checkpoint(bot).config.contract,
                D("0"), position, now_ms, reconciled=self._known(owner, position, allow_unknown_increase=True))
            if not verdict.accepted or not verdict.reduce_only:
                self.j._write_risk(replace(state, phase="WAIT" if position != 0 or unresolved else "VERIFY"))
                return None
            child = self.db.execute("SELECT count(*) FROM execution_orders WHERE intent_key IS NULL").fetchone()[0]
            key = canonical(dict(kind="flatten", account_id=self.j.account_id, bot_id=bot_id,
                                 flatten_id=state.flatten_id, child=child))
            request = self._insert(key, bot, verdict.quantity, True, deadline, state.epoch, D("0"))
            self._dirty(bot_id)
            self.j._write_risk(replace(state, phase="WORKING"))
            return request
