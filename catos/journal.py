"""Single-thread SQLite journal for local simulation; no order dispatcher."""

from contextlib import contextmanager
from dataclasses import dataclass, replace
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import sqlite3

from catos import ipc, research, risk
from catos.account_lock import ENVIRONMENT

SCHEMA_VERSION = 5
HALT_REASONS = frozenset(("manual_kill", "soft_loss", "hard_loss"))


class JournalError(RuntimeError):
    pass


class ReplayConflict(JournalError):
    pass


class OwnershipError(JournalError):
    pass


def canonical(value):
    ipc.encode_frame(value)  # Same bounded JSON data-only rules as IPC.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def money(value, name, *, derived=True):
    if not isinstance(value, Decimal):
        raise ipc.ProtocolError(f"{name} must be Decimal")
    return ipc.decimal_text(str(value), name, derived=derived)


@dataclass(frozen=True)
class FixtureDecision:
    """Explicit test verdict; reservations remain non-dispatchable in Slice E."""
    reserve: bool = False
    amount: Decimal = Decimal("0")
    reason: str = "risk_engine_not_installed"

    def validate(self):
        amount = money(self.amount, "fixture reservation", derived=False)
        if type(self.reserve) is not bool or amount < 0 or (not self.reserve and amount != 0):
            raise ipc.ProtocolError("invalid simulation fixture decision")
        ipc.token(self.reason, "fixture reason")


@dataclass(frozen=True)
class Reconciliation:
    """Supervisor-supplied synthetic evidence, never inferred from a Worker."""
    revision: int
    evidence_id: str
    position: Decimal
    ordinary_open: int
    conditional_open: int
    unknown_count: int
    fills_reconciled: bool
    attributed_bot_id: str | None = None

    def validate(self, bot_id):
        ipc.integer(self.revision, "reconciliation revision")
        ipc.token(self.evidence_id, "synthetic evidence_id")
        money(self.position, "reconciled position")
        for name in ("ordinary_open", "conditional_open", "unknown_count"):
            ipc.integer(getattr(self, name), name)
        if type(self.fills_reconciled) is not bool:
            raise ipc.ProtocolError("fills_reconciled must be bool")
        if self.attributed_bot_id is not None:
            ipc.token(self.attributed_bot_id, "attributed_bot_id")
        if (self.attributed_bot_id not in (None, bot_id)
                or (self.position != 0 and self.attributed_bot_id != bot_id)):
            raise OwnershipError("unattributed or foreign position cannot be taken over")


@dataclass(frozen=True)
class CommitReceipt:
    event_seq: int
    checkpoint: ipc.Checkpoint
    target_position: Decimal | None
    disposition: str
    reason: str
    reservation: Decimal
    intent_key: str | None
    epoch: int
    replayed: bool = False


_SCHEMA = (
    "CREATE TABLE metadata (account_id TEXT NOT NULL, environment TEXT NOT NULL, fixture_budget TEXT NOT NULL)",
    """CREATE TABLE control (id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL,
       halt_reasons TEXT NOT NULL, health TEXT NOT NULL)""",
    """CREATE TABLE bots (bot_id TEXT PRIMARY KEY, inst_id TEXT NOT NULL, config_json TEXT NOT NULL,
       checkpoint_json TEXT NOT NULL, consumed_seq INTEGER NOT NULL, revision INTEGER NOT NULL,
       isolated INTEGER NOT NULL DEFAULT 0 CHECK(isolated IN (0,1)))""",
    """CREATE TABLE ownership (inst_id TEXT PRIMARY KEY, bot_id TEXT NOT NULL UNIQUE REFERENCES bots(bot_id),
       position TEXT, ordinary_open INTEGER, conditional_open INTEGER, unknown_count INTEGER,
       fills_reconciled INTEGER NOT NULL DEFAULT 0, evidence_id TEXT, reconciled_revision INTEGER)""",
    """CREATE TABLE inputs (bot_id TEXT NOT NULL REFERENCES bots(bot_id), seq INTEGER NOT NULL,
       input_json TEXT NOT NULL, input_hash TEXT NOT NULL, before_json TEXT NOT NULL,
       state TEXT NOT NULL CHECK(state IN ('PENDING','COMMITTED')), result_json TEXT,
       result_hash TEXT, receipt_json TEXT, PRIMARY KEY(bot_id,seq))""",
    """CREATE TABLE intents (intent_key TEXT PRIMARY KEY, bot_id TEXT NOT NULL, seq INTEGER NOT NULL,
       output_index INTEGER NOT NULL CHECK(output_index=0), target TEXT NOT NULL CHECK(typeof(target)='text'),
       disposition TEXT NOT NULL, reason TEXT NOT NULL, epoch INTEGER NOT NULL,
       UNIQUE(bot_id,seq,output_index), FOREIGN KEY(bot_id,seq) REFERENCES inputs(bot_id,seq))""",
    """CREATE TABLE reservations (intent_key TEXT PRIMARY KEY REFERENCES intents(intent_key),
       amount TEXT NOT NULL CHECK(typeof(amount)='text'))""",
    """CREATE TABLE outbox (intent_key TEXT PRIMARY KEY REFERENCES intents(intent_key),
       state TEXT NOT NULL CHECK(state='HELD_SIMULATION'), epoch INTEGER NOT NULL)""",
)

_RISK_SCHEMA = (
    "CREATE TABLE risk_control (id INTEGER PRIMARY KEY CHECK(id=1), limits_json TEXT NOT NULL, state_json TEXT NOT NULL)",
    """CREATE TABLE risk_orders (intent_key TEXT PRIMARY KEY REFERENCES intents(intent_key),
       quantity TEXT NOT NULL CHECK(typeof(quantity)='text'), reduce_only INTEGER NOT NULL,
       eligible INTEGER NOT NULL CHECK(eligible IN (0,1)))""",
)


class Journal:
    """Internal writer owned by Supervisor's one dedicated thread and account lock."""
    def __init__(self, path, account_id, fixture_budget, risk_limits=None, execution_enabled=False):
        from catos.execution import ExecutionJournal, SCHEMA as EXECUTION_SCHEMA
        from catos.protection import ProtectionJournal
        if type(execution_enabled) is not bool or (execution_enabled and risk_limits is None):
            raise JournalError("local execution requires installed risk")
        self.execution = None
        self.protection = None
        self.account_id = ipc.token(account_id, "account_id")
        if risk_limits is not None and not isinstance(risk_limits, risk.Limits):
            raise ipc.ProtocolError("risk_limits must be Supervisor Limits")
        self.risk_limits = risk_limits
        self.budget = money(fixture_budget, "fixture budget", derived=False)
        if self.budget <= 0:
            raise ipc.ProtocolError("fixture budget must be positive")
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, isolation_level=None, timeout=0.25)
        self.connection.row_factory = sqlite3.Row
        try:
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                if self.connection.execute("SELECT 1 FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone():
                    raise JournalError("refusing an unrecognized nonempty database")
            elif version not in (1, 2, 3, 4, SCHEMA_VERSION):
                raise JournalError("unsupported journal schema; no automatic rebuild")
            else:
                meta = self.connection.execute("SELECT * FROM metadata").fetchone()
                if (meta is None or meta["account_id"] != account_id or meta["environment"] != ENVIRONMENT
                        or ipc.decimal_text(meta["fixture_budget"], "stored budget", derived=True) != self.budget):
                    raise JournalError("database account/environment/budget mismatch")
            mode = self.connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("PRAGMA foreign_keys=ON")
            if mode.lower() != "wal" or self.connection.execute("PRAGMA synchronous").fetchone()[0] != 2:
                raise JournalError("WAL/FULL unavailable")
            with self._transaction():
                if version == 0:
                    for statement in _SCHEMA:
                        self.connection.execute(statement)
                    self.connection.execute("INSERT INTO metadata VALUES (?,?,?)",
                                            (account_id, ENVIRONMENT, str(self.budget)))
                    self.connection.execute("INSERT INTO control VALUES (1,0,'[]','RECONCILING')")
                if version < 2:
                    for statement in _RISK_SCHEMA:
                        self.connection.execute(statement)
                if version < 3:
                    for statement in EXECUTION_SCHEMA:
                        self.connection.execute(statement)
                if version < 4:
                    self.connection.execute("""CREATE TABLE IF NOT EXISTS risk_actions (
                        id INTEGER PRIMARY KEY, kind TEXT NOT NULL, actor TEXT NOT NULL,
                        evidence_id TEXT NOT NULL, before_json TEXT NOT NULL,
                        after_json TEXT NOT NULL, limits_json TEXT NOT NULL)""")
                if version < 5:
                    self.connection.execute("CREATE TABLE IF NOT EXISTS protection (bot_id TEXT PRIMARY KEY REFERENCES bots(bot_id), state_json TEXT NOT NULL)")
                self.protection = ProtectionJournal(self)
                for row in self.connection.execute('SELECT bot_id FROM protection'):
                    state = self.protection.state(row[0])
                    if state['active'] or state['pending']:
                        state['uncertain'] = True
                        state['alert'] = 'restart_protection_reconciliation'
                        self.protection.save(row[0], state)
                self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                installed = self.connection.execute("SELECT 1 FROM execution_mode").fetchone() is not None
                if installed and not execution_enabled:
                    raise JournalError("execution mode cannot be disabled in place")
                if execution_enabled:
                    self.connection.execute("INSERT OR IGNORE INTO execution_mode VALUES (1)")
                    self.execution = ExecutionJournal(self)
                    self.connection.execute("UPDATE execution_orders SET state='UNKNOWN' WHERE settled=0 AND (state='SUBMITTING' OR cancel_pending=1)")
                saved_risk = self.connection.execute("SELECT * FROM risk_control WHERE id=1").fetchone()
                if saved_risk is not None:
                    saved_limits = json.loads(saved_risk["limits_json"])
                    legacy = set(saved_limits) == {"leverage", "symbol_share"}
                    if legacy:
                        saved_limits.update(soft_loss="0.10", hard_loss="0.20")
                    if risk_limits is None or saved_limits != risk_limits.to_wire():
                        raise JournalError("risk mode/limits cannot be replaced in place")
                    restored = risk.State.from_wire(ipc.decode_payload(saved_risk["state_json"].encode()))
                    if legacy:
                        self.connection.execute("UPDATE risk_control SET limits_json=? WHERE id=1",
                                                (canonical(saved_limits),))
                        self._audit_risk("migrate_p5", "migration", "schema-4", restored, restored, risk_limits)
                    self._write_risk(replace(restored, health="RECONCILING", snapshot=None,
                                                 epoch=restored.epoch + 1))
                elif risk_limits is not None:
                    if self.connection.execute("SELECT 1 FROM reservations UNION ALL SELECT 1 FROM outbox LIMIT 1").fetchone():
                        raise JournalError("fixture obligations must be resolved before enabling risk")
                    reasons = json.loads(self.connection.execute("SELECT halt_reasons FROM control").fetchone()[0])
                    state = risk.halt(risk.State(), reasons)
                    self.connection.execute("INSERT INTO risk_control VALUES (1,?,?)",
                                            (canonical(risk_limits.to_wire()), canonical(state.to_wire())))
                # A new process cannot reuse a previous process's reconciliation gate.
                self.connection.execute("UPDATE control SET health='RECONCILING' WHERE id=1")
                self.connection.execute("UPDATE ownership SET reconciled_revision=NULL")
        except BaseException:
            self.connection.close()
            raise

    def _commit(self):
        self.connection.commit()

    @contextmanager
    def _transaction(self):
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self._commit()
        except BaseException:
            if self.connection.in_transaction:
                self.connection.rollback()
            raise

    def close(self):
        self.connection.close()

    def _bot(self, bot_id):
        row = self.connection.execute("SELECT * FROM bots WHERE bot_id=?", (bot_id,)).fetchone()
        if row is None:
            raise OwnershipError("unknown bot")
        return row

    def _checkpoint(self, row):
        config = ipc.WorkerConfig.from_wire(ipc.decode_payload(row["config_json"].encode("utf-8")))
        result = ipc.Checkpoint.from_wire(ipc.decode_payload(row["checkpoint_json"].encode("utf-8")), config)
        if result.event_seq != row["consumed_seq"] or config.contract.inst_id != row["inst_id"]:
            raise JournalError("stored consumption position/config is inconsistent")
        return result

    def _require_owner(self, bot_id):
        bot = self._bot(bot_id)
        owner = self.connection.execute("SELECT * FROM ownership WHERE inst_id=?", (bot["inst_id"],)).fetchone()
        if owner is None or owner["bot_id"] != bot_id:
            raise OwnershipError("bot does not own this contract")
        return bot, owner

    def register(self, bot_id, config):
        ipc.token(bot_id, "bot_id")
        config = ipc.WorkerConfig.from_wire(config.to_wire())
        config_json = canonical(config.to_wire())
        with self._transaction():
            if self.connection.execute("SELECT 1 FROM ownership WHERE bot_id<>?", (bot_id,)).fetchone():
                raise OwnershipError("Slice E manages one bot/contract per account")
            owner = self.connection.execute("SELECT bot_id FROM ownership WHERE inst_id=?", (config.contract.inst_id,)).fetchone()
            if owner is not None and owner[0] != bot_id:
                raise OwnershipError("contract remains owned by another bot")
            bot = self.connection.execute("SELECT * FROM bots WHERE bot_id=?", (bot_id,)).fetchone()
            if bot is None:
                self.connection.execute("INSERT INTO bots VALUES (?,?,?,?,0,0,0)",
                    (bot_id, config.contract.inst_id, config_json, canonical(ipc.Checkpoint(config).to_wire())))
            elif bot["config_json"] != config_json:
                raise OwnershipError("bot artifact/config cannot be replaced in place")
            if owner is None:
                self.connection.execute("INSERT INTO ownership (inst_id,bot_id) VALUES (?,?)", (config.contract.inst_id, bot_id))
            self.protection.register(bot_id)
        return self.snapshot(bot_id)

    def total_reserved(self):
        with localcontext(research._CONTEXT):
            return sum((ipc.decimal_text(row[0], "reservation", derived=True)
                        for row in self.connection.execute("SELECT amount FROM reservations")), Decimal("0"))

    def risk_state(self):
        row = self.connection.execute("SELECT state_json FROM risk_control WHERE id=1").fetchone()
        return None if row is None else risk.State.from_wire(ipc.decode_payload(row[0].encode()))

    def _write_risk(self, state):
        self.connection.execute("UPDATE risk_control SET state_json=? WHERE id=1", (canonical(state.to_wire()),))
        self.connection.execute("UPDATE control SET epoch=?,halt_reasons=? WHERE id=1",
                                (state.epoch, json.dumps(sorted(state.reasons))))
        if state.mode != "RUN" or state.health != "HEALTHY":
            # HELD_SIMULATION has never been sent. Keep its reservation until G
            # supplies a terminal lifecycle; it cannot become eligible again.
            self.connection.execute("UPDATE risk_orders SET eligible=0 WHERE reduce_only=0")

    def save_risk(self, state):
        if self.risk_limits is None:
            raise JournalError("risk mode is not enabled")
        with self._transaction():
            previous = self.risk_state()
            if state.seq < previous.seq or state.epoch < previous.epoch or not previous.reasons <= state.reasons:
                raise JournalError("risk state cannot move backwards")
            self._write_risk(state)

    def _audit_risk(self, kind, actor, evidence_id, before, after, limits):
        self.connection.execute("INSERT INTO risk_actions VALUES (NULL,?,?,?,?,?,?)",
            (kind, actor, evidence_id, canonical(before.to_wire()), canonical(after.to_wire()),
             canonical(limits.to_wire())))

    def set_loss_limits(self, limits, expected, actor, evidence_id):
        ipc.token(actor, "operator")
        ipc.token(evidence_id, "configuration evidence")
        if not isinstance(limits, risk.Limits) or self.risk_limits is None:
            raise JournalError("risk limits required")
        if (limits.leverage, limits.symbol_share) != (self.risk_limits.leverage, self.risk_limits.symbol_share):
            raise JournalError("only loss thresholds can change in place")
        with self._transaction():
            previous = self.risk_state()
            if previous != expected:
                raise JournalError("risk changed before configuration update")
            updated = risk.halt(replace(previous, epoch=previous.epoch + 1), risk.loss_reasons(previous, limits))
            self.connection.execute("UPDATE risk_control SET limits_json=? WHERE id=1", (canonical(limits.to_wire()),))
            self._write_risk(updated)
            self._audit_risk("loss_limits", actor, evidence_id, previous, updated, limits)
        self.risk_limits = limits
        return updated

    def rearm(self, bot_id, expected, now_ms, actor, evidence_id, manual_cause_cleared):
        ipc.token(actor, "operator")
        ipc.token(evidence_id, "re-arm evidence")
        if type(manual_cause_cleared) is not bool:
            raise ipc.ProtocolError("manual cause confirmation must be bool")
        with self._transaction():
            previous = self.risk_state()
            if previous != expected:
                raise JournalError("risk changed before re-arm")
            bot, owner = self._require_owner(bot_id)
            s = previous.snapshot
            ready = (s is not None and owner["position"] is not None
                     and Decimal(owner["position"]) == s.position
                     and owner["ordinary_open"] == 0 and owner["conditional_open"] == 0
                     and owner["unknown_count"] == 0 and owner["fills_reconciled"] == 1
                     and owner["reconciled_revision"] == bot["revision"] and not bot["isolated"]
                     and self.connection.execute("SELECT health FROM control WHERE id=1").fetchone()[0] == "LOCAL_READY"
                     and not self.connection.execute("SELECT 1 FROM reservations UNION ALL SELECT 1 FROM outbox LIMIT 1").fetchone()
                     and not self.connection.execute("SELECT 1 FROM inputs WHERE state='PENDING'").fetchone()
                     and (self.execution is None or not self.execution.unresolved())
                     and not self.protection.obligations(bot_id))
            updated = risk.rearm(previous, self.risk_limits, now_ms, reconciled=bool(ready),
                                 manual_cause_cleared=manual_cause_cleared)
            self._write_risk(updated)
            # Old work never becomes eligible again after recovery.
            self.connection.execute("UPDATE risk_orders SET eligible=0 WHERE reduce_only=0")
            self._audit_risk("rearm", actor, evidence_id, previous, updated, self.risk_limits)
        return updated

    def flatten_progress(self, bot_id, phase, now_ms):
        if self.risk_limits is None:
            raise JournalError("risk mode is not enabled")
        ipc.integer(now_ms, "flatten time")
        with self._transaction():
            state = self.risk_state()
            complete = False
            if phase == "DONE":
                bot, owner = self._require_owner(bot_id)
                s = state.snapshot
                complete = (s is not None and state.time_ms <= now_ms < s.valid_until_ms
                            and s.position_verified and s.position == 0 and s.other_notional == 0
                            and s.pending_buy == 0 and s.pending_sell == 0 and not s.reduction_conflict
                            and owner["position"] is not None and Decimal(owner["position"]) == 0
                            and owner["ordinary_open"] == 0 and owner["conditional_open"] == 0
                            and owner["unknown_count"] == 0 and owner["fills_reconciled"]
                            and owner["reconciled_revision"] == bot["revision"]
                            and not self.connection.execute("SELECT 1 FROM reservations UNION ALL SELECT 1 FROM outbox LIMIT 1").fetchone()
                            and not self.connection.execute("SELECT 1 FROM inputs WHERE state='PENDING'").fetchone())
                if self.execution is not None and self.execution.unresolved():
                    complete = False
                if self.protection.obligations(bot_id):
                    complete = False
            updated = risk.progress(state, phase, complete=bool(complete))
            self._write_risk(updated)
        return updated

    def _risk_verdict(self, bot, owner, result, account, now_ms):
        position = account.position
        target = result.target_position
        reduction = position != 0 and (target == 0 or (target * position > 0 and abs(target) < abs(position)))
        if not reduction and self.protection.blocked(bot['bot_id']):
            return risk.Verdict(False, 'protection_gate_closed')
        if not reduction and self.execution is not None and (self.execution.unresolved()
                or self.connection.execute("SELECT 1 FROM risk_orders").fetchone()):
            return risk.Verdict(False, "order_pending")
        state = self.risk_state()
        buys, sells, reducing = Decimal("0"), Decimal("0"), False
        with localcontext(research._CONTEXT):
            for row in self.connection.execute("SELECT quantity,reduce_only FROM risk_orders"):
                qty = ipc.decimal_text(row["quantity"], "held quantity", derived=True)
                buys += max(qty, Decimal("0"))
                sells += max(-qty, Decimal("0"))
                reducing |= bool(row["reduce_only"])
        if self.execution is not None:
            reducing |= self.execution.reduction_conflict(position)
        known = (owner["position"] is not None and owner["reconciled_revision"] is not None
                 and owner["fills_reconciled"] and owner["unknown_count"] == 0
                 and Decimal(owner["position"]) == account.position)
        return risk.evaluate(state, self.risk_limits, self._checkpoint(bot).config.contract,
                             result.target_position, account.position, now_ms,
                             held_buy=buys, held_sell=sells, held_reduction=reducing, reconciled=bool(known))

    def snapshot(self, bot_id):
        bot = self._bot(bot_id)
        control = self.connection.execute("SELECT * FROM control WHERE id=1").fetchone()
        owner = self.connection.execute("SELECT * FROM ownership WHERE bot_id=?", (bot_id,)).fetchone()
        return dict(checkpoint=self._checkpoint(bot), revision=bot["revision"], isolated=bool(bot["isolated"]),
                    health=control["health"], epoch=control["epoch"], halt_reasons=tuple(json.loads(control["halt_reasons"])),
                    owner=None if owner is None else dict(owner), total_reserved=self.total_reserved(),
                    pending=self.connection.execute("SELECT seq FROM inputs WHERE bot_id=? AND state='PENDING'", (bot_id,)).fetchone() is not None,
                    risk_state=self.risk_state())

    def record_halts(self, reasons):
        if not set(reasons) <= HALT_REASONS:
            raise JournalError("unknown halt reason")
        with self._transaction():
            if self.risk_limits is not None:
                state = risk.halt(self.risk_state(), reasons)
                self._write_risk(state)
                return state.epoch
            row = self.connection.execute("SELECT epoch,halt_reasons FROM control WHERE id=1").fetchone()
            previous = set(json.loads(row["halt_reasons"]))
            merged = previous | set(reasons)
            epoch = row["epoch"] + len(merged - previous)
            self.connection.execute("UPDATE control SET epoch=?,halt_reasons=? WHERE id=1",
                                    (epoch, json.dumps(sorted(merged))))
        return epoch

    def reconcile(self, bot_id, evidence):
        if self.execution is not None:
            try:
                evidence.validate(bot_id)
                bot, owner = self._require_owner(bot_id)
                if evidence.revision != bot["revision"]:
                    raise OwnershipError("stale reconciliation evidence")
                self.execution.check_reconciliation(owner, evidence)
            except OwnershipError:
                with self._transaction():
                    self.execution._dirty(bot_id)
                raise
        evidence.validate(bot_id)
        with self._transaction():
            bot, owner = self._require_owner(bot_id)
            if evidence.revision != bot["revision"]:
                raise OwnershipError("stale reconciliation evidence")
            self.connection.execute("""UPDATE ownership SET position=?,ordinary_open=?,conditional_open=?,unknown_count=?,
                fills_reconciled=?,evidence_id=?,reconciled_revision=? WHERE bot_id=?""",
                (str(evidence.position), evidence.ordinary_open, evidence.conditional_open, evidence.unknown_count,
                 int(evidence.fills_reconciled), evidence.evidence_id, evidence.revision, bot_id))
            health = "LOCAL_READY" if evidence.unknown_count == 0 and evidence.fills_reconciled else "RECONCILING"
            if self.execution is not None and evidence.conditional_open > int(self.protection.state(bot_id)['active'] is not None):
                health = "RECONCILING"
            self.connection.execute("UPDATE control SET health=? WHERE id=1", (health,))
        return self.snapshot(bot_id)

    def release(self, bot_id):
        if self.protection.obligations(bot_id):
            raise OwnershipError('protection responsibility still belongs to bot')
        with self._transaction():
            bot, owner = self._require_owner(bot_id)
            if (owner["position"] is None or ipc.decimal_text(owner["position"], "position", derived=True) != 0
                    or owner["ordinary_open"] != 0 or owner["conditional_open"] != 0 or owner["unknown_count"] != 0
                    or not owner["fills_reconciled"] or owner["reconciled_revision"] != bot["revision"]):
                raise OwnershipError("release requires fresh flat/terminal/reconciled evidence")
            pending = self.connection.execute("SELECT 1 FROM inputs WHERE bot_id=? AND state='PENDING'", (bot_id,)).fetchone()
            obligations = self.connection.execute("""SELECT 1 FROM intents i WHERE i.bot_id=? AND
                (EXISTS(SELECT 1 FROM reservations r WHERE r.intent_key=i.intent_key)
                 OR EXISTS(SELECT 1 FROM outbox o WHERE o.intent_key=i.intent_key))""", (bot_id,)).fetchone()
            if pending or obligations:
                raise OwnershipError("pending input, reservation or outbox still belongs to this bot")
            if self.execution is not None and self.execution.unresolved():
                raise OwnershipError("unresolved execution still belongs to this bot")
            self.connection.execute("DELETE FROM ownership WHERE bot_id=?", (bot_id,))

    def _conflict(self, bot_id):
        with self._transaction():
            self.connection.execute("UPDATE bots SET isolated=1 WHERE bot_id=?", (bot_id,))
        raise ReplayConflict("same event key with different content; bot isolated")

    def _receipt(self, row, replayed=False):
        data = ipc.decode_payload(row["receipt_json"].encode("utf-8"))
        cp = self._checkpoint(self._bot(row["bot_id"]))
        checkpoint = ipc.Checkpoint.from_wire(data["checkpoint"], cp.config)
        return CommitReceipt(row["seq"], checkpoint,
            None if data["target"] is None else ipc.decimal_text(data["target"], "target"),
            data["disposition"], data["reason"], ipc.decimal_text(data["reservation"], "reservation", derived=True),
            data["intent_key"], data["epoch"], replayed)

    def prepare(self, bot_id, seq, payload, expires_at_ms):
        ipc.integer(seq, "event sequence", 1)
        ipc.integer(expires_at_ms, "expires_at_ms")
        bot, owner = self._require_owner(bot_id)
        if bot["isolated"]:
            raise ReplayConflict("bot is isolated")
        input_json = canonical(dict(payload=payload, expires_at_ms=expires_at_ms))
        old = self.connection.execute("SELECT * FROM inputs WHERE bot_id=? AND seq=?", (bot_id, seq)).fetchone()
        if old is not None:
            if old["input_hash"] != digest(input_json) or old["input_json"] != input_json:
                self._conflict(bot_id)
            return self._receipt(old, True) if old["state"] == "COMMITTED" else None
        checkpoint = self._checkpoint(bot)
        if seq != checkpoint.event_seq + 1:
            raise ipc.ProtocolError("input sequence does not follow committed checkpoint")
        bar, account, warmup = ipc.parse_event(payload, checkpoint)
        if expires_at_ms < bar.open_time_ms + checkpoint.config.timeframe_ms:
            raise ipc.ProtocolError("deadline cannot precede this decision's close time")
        with self._transaction():
            self.connection.execute("INSERT INTO inputs VALUES (?,?,?,?,?,'PENDING',NULL,NULL,NULL)",
                (bot_id, seq, input_json, digest(input_json), canonical(checkpoint.to_wire())))
            self.connection.execute("UPDATE bots SET revision=revision+1 WHERE bot_id=?", (bot_id,))
        return None

    def commit_result(self, bot_id, result, fixture, now_ms):
        fixture.validate()
        if self.risk_limits is not None and fixture != FixtureDecision():
            raise JournalError("fixture verdict cannot bypass installed risk engine")
        ipc.integer(result.event_seq, "result sequence", 1)
        ipc.integer(now_ms, "simulation now_ms")
        bot, owner = self._require_owner(bot_id)
        if bot["isolated"]:
            raise ReplayConflict("bot is isolated")
        row = self.connection.execute("SELECT * FROM inputs WHERE bot_id=? AND seq=?", (bot_id, result.event_seq)).fetchone()
        if row is None:
            raise JournalError("input must be durable before accepting a result")
        result_payload = dict(target=None if result.target_position is None else str(money(result.target_position, "target")),
                              checkpoint=result.checkpoint.to_wire(), ready=result.ready)
        result_json = canonical(result_payload)
        if row["state"] == "COMMITTED":
            if row["result_hash"] != digest(result_json) or row["result_json"] != result_json:
                self._conflict(bot_id)
            return self._receipt(row, True)
        current = self._checkpoint(bot)
        if result.event_seq != current.event_seq + 1:
            raise JournalError("result sequence does not follow consumption position")
        stored = ipc.decode_payload(row["input_json"].encode("utf-8"))
        bar, account, warmup = ipc.parse_event(stored["payload"], current)
        result = ipc.parse_result(result_payload, current, bar, account, warmup)
        if now_ms < bar.open_time_ms + current.config.timeframe_ms:
            raise ipc.ProtocolError("simulation clock precedes the decision")
        with self._transaction():
            control = self.connection.execute("SELECT * FROM control WHERE id=1").fetchone()
            amount = Decimal("0")
            key = None
            status, reason = "NO_INTENT", "no_target"
            verdict = None
            if result.target_position is not None:
                key = json.dumps([ENVIRONMENT, self.account_id, bot_id, ipc.STRATEGY_ID,
                                  ipc.STRATEGY_VERSION, result.event_seq, 0], separators=(",", ":"))
                if now_ms >= stored["expires_at_ms"]:
                    status, reason = "EXPIRED", "deadline_elapsed"
                elif self.risk_limits is not None:
                    verdict = self._risk_verdict(bot, owner, result, account, now_ms)
                    status = "RESERVED_SIMULATION" if verdict.accepted else "NO_CHANGE" if verdict.reason == "target_equals_position" else "REJECTED"
                    reason, amount = verdict.reason, verdict.reservation
                elif json.loads(control["halt_reasons"]) or control["health"] != "LOCAL_READY":
                    status, reason = "REJECTED", "control_gate_closed"
                elif result.target_position == account.position:
                    status, reason = "NO_CHANGE", "target_equals_position"
                elif not fixture.reserve:
                    status, reason = "REJECTED", fixture.reason
                else:
                    with localcontext(research._CONTEXT):
                        fits = self.total_reserved() + fixture.amount <= self.budget
                    status, reason = ("RESERVED_SIMULATION", fixture.reason) if fits else ("REJECTED", "fixture_budget_exceeded")
                    if fits:
                        amount = fixture.amount
                self.connection.execute("INSERT INTO intents VALUES (?,?,?,0,?,?,?,?)",
                    (key, bot_id, result.event_seq, str(result.target_position), status, reason, control["epoch"]))
                if status == "RESERVED_SIMULATION":
                    self.connection.execute("INSERT INTO reservations VALUES (?,?)", (key, str(amount)))
                    self.connection.execute("INSERT INTO outbox VALUES (?,'HELD_SIMULATION',?)", (key, control["epoch"]))
                    if verdict is not None:
                        self.connection.execute("INSERT INTO risk_orders VALUES (?,?,?,1)",
                                                (key, str(verdict.quantity), int(verdict.reduce_only)))
            receipt_json = canonical(dict(checkpoint=result.checkpoint.to_wire(), target=result_payload["target"],
                disposition=status, reason=reason, reservation=str(amount), intent_key=key, epoch=control["epoch"]))
            self.connection.execute("UPDATE bots SET checkpoint_json=?,consumed_seq=?,revision=revision+1 WHERE bot_id=?",
                                    (canonical(result.checkpoint.to_wire()), result.event_seq, bot_id))
            self.connection.execute("UPDATE inputs SET state='COMMITTED',result_json=?,result_hash=?,receipt_json=? WHERE bot_id=? AND seq=?",
                                    (result_json, digest(result_json), receipt_json, bot_id, result.event_seq))
        committed = self.connection.execute("SELECT * FROM inputs WHERE bot_id=? AND seq=?", (bot_id, result.event_seq)).fetchone()
        return self._receipt(committed)
