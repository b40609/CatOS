"""Decimal-only synthetic account risk. No strategy, I/O, or exchange client."""

from dataclasses import dataclass, replace
from decimal import Decimal, localcontext

from catos import ipc, research

D = Decimal
DAY_MS = 86_400_000
TAIPEI_OFFSET_MS = 28_800_000
HALTS = frozenset(("soft_loss", "hard_loss", "manual_kill"))


def decimal(value, name):
    if not isinstance(value, Decimal):
        raise ipc.ProtocolError(f"{name} must be Decimal")
    return ipc.decimal_text(str(value), name, derived=True)


def taipei_day(time_ms):
    ipc.integer(time_ms, "time_ms")
    return (time_ms + TAIPEI_OFFSET_MS) // DAY_MS


@dataclass(frozen=True)
class Limits:
    leverage: Decimal = D("3.0")
    symbol_share: Decimal = D("0.50")
    soft_loss: Decimal = D("0.10")
    hard_loss: Decimal = D("0.20")

    def __post_init__(self):
        if decimal(self.leverage, "leverage") <= 0:
            raise ipc.ProtocolError("leverage must be positive")
        if not 0 < decimal(self.symbol_share, "symbol_share") <= 1:
            raise ipc.ProtocolError("symbol_share must be in (0,1]")
        if not 0 < decimal(self.soft_loss, "soft_loss") < decimal(self.hard_loss, "hard_loss") <= 1:
            raise ipc.ProtocolError("loss limits require 0 < soft < hard <= 1")

    def to_wire(self):
        return {name: str(value) for name, value in vars(self).items()}


SYNTHETIC_BASELINE_SOURCE = "synthetic_midnight_snapshot_v1"
SYNTHETIC_BASELINE_CONTRACT = "synthetic_baseline_evidence_v1"
SYNTHETIC_BASELINE_EVENT_SEMANTICS = "pre_event_midnight_equity"
DEMO_QUIESCENT_BASELINE_SOURCE = "demo_quiescent_midnight_equivalence_v1"
DEMO_QUIESCENT_BASELINE_CONTRACT = "demo_quiescent_midnight_equivalence_evidence_v1"
DEMO_QUIESCENT_BASELINE_EVENT_SEMANTICS = "quiescent_interval_equivalent_midnight_equity"
DAY_CONTEXT_CONTRACT = "taipei_day_context_v1"
AUTHORIZED_BASELINE_SOURCES = frozenset({
    SYNTHETIC_BASELINE_SOURCE,
    DEMO_QUIESCENT_BASELINE_SOURCE,
})


def _sha256_text(value, name):
    if (type(value) is not str or len(value) != 64
            or any(ch not in "0123456789abcdef" for ch in value)):
        raise ipc.ProtocolError(f"invalid {name}")
    return value


@dataclass(frozen=True)
class DayContext:
    target_time_ms: int
    day: int
    trading_day_start_ms: int
    contract_id: str = DAY_CONTEXT_CONTRACT

    def __post_init__(self):
        ipc.integer(self.target_time_ms, "day context target time")
        ipc.integer(self.day, "day context day")
        ipc.integer(self.trading_day_start_ms, "day context start")
        ipc.token(self.contract_id, "day context contract")
        expected_day = taipei_day(self.target_time_ms)
        expected_start = expected_day * DAY_MS - TAIPEI_OFFSET_MS
        if (self.contract_id != DAY_CONTEXT_CONTRACT or self.day != expected_day
                or self.trading_day_start_ms != expected_start):
            raise ipc.ProtocolError("invalid Taipei day context")

    @classmethod
    def from_target_time_ms(cls, target_time_ms):
        day = taipei_day(target_time_ms)
        return cls(target_time_ms, day, day * DAY_MS - TAIPEI_OFFSET_MS)


@dataclass(frozen=True)
class BaselineEvidence:
    contract_id: str
    account_alias: str
    environment: str
    source: str
    trading_day_start_ms: int
    observed_at_ms: int
    equity: Decimal
    event_semantics: str
    evidence_id: str
    expected_uid_sha256: str | None = None
    cutoff_ms: int | None = None
    report_content_digest: str | None = None
    balance_content_digest: str | None = None
    collection_evidence_digest: str | None = None
    zero_event_digest: str | None = None

    def __post_init__(self):
        for value, name in ((self.contract_id, "baseline contract"),
                            (self.account_alias, "baseline account alias"),
                            (self.environment, "baseline environment"),
                            (self.source, "baseline source"),
                            (self.event_semantics, "baseline event semantics"),
                            (self.evidence_id, "baseline evidence")):
            ipc.token(value, name)
        ipc.integer(self.trading_day_start_ms, "baseline trading day start")
        ipc.integer(self.observed_at_ms, "baseline observed at")
        if decimal(self.equity, "baseline evidence equity") <= 0:
            raise ipc.ProtocolError("baseline evidence equity must be positive")
        if (self.trading_day_start_ms + TAIPEI_OFFSET_MS) % DAY_MS != 0:
            raise ipc.ProtocolError("invalid Taipei midnight baseline boundary")
        q1_fields = (
            self.expected_uid_sha256,
            self.cutoff_ms,
            self.report_content_digest,
            self.balance_content_digest,
            self.collection_evidence_digest,
            self.zero_event_digest,
        )
        if self.source == SYNTHETIC_BASELINE_SOURCE:
            if (self.contract_id != SYNTHETIC_BASELINE_CONTRACT
                    or self.event_semantics != SYNTHETIC_BASELINE_EVENT_SEMANTICS
                    or self.observed_at_ms != self.trading_day_start_ms
                    or any(value is not None for value in q1_fields)):
                raise ipc.ProtocolError("invalid synthetic midnight baseline evidence")
        elif self.source == DEMO_QUIESCENT_BASELINE_SOURCE:
            if (self.contract_id != DEMO_QUIESCENT_BASELINE_CONTRACT
                    or self.event_semantics != DEMO_QUIESCENT_BASELINE_EVENT_SEMANTICS
                    or type(self.cutoff_ms) is not int
                    or self.cutoff_ms != self.observed_at_ms
                    or not self.trading_day_start_ms < self.cutoff_ms < self.trading_day_start_ms + DAY_MS):
                raise ipc.ProtocolError("invalid Demo quiescent baseline evidence")
            _sha256_text(self.expected_uid_sha256, "baseline expected UID digest")
            _sha256_text(self.report_content_digest, "baseline report digest")
            _sha256_text(self.balance_content_digest, "baseline balance digest")
            _sha256_text(self.collection_evidence_digest, "baseline collection digest")
            _sha256_text(self.zero_event_digest, "baseline zero-event digest")
        else:
            raise ipc.ProtocolError("unauthorized baseline evidence source")

    def to_wire(self):
        data = dict(contract_id=self.contract_id, account_alias=self.account_alias,
                    environment=self.environment, source=self.source,
                    trading_day_start_ms=self.trading_day_start_ms,
                    observed_at_ms=self.observed_at_ms, equity=str(self.equity),
                    event_semantics=self.event_semantics, evidence_id=self.evidence_id)
        if self.source == DEMO_QUIESCENT_BASELINE_SOURCE:
            data.update(
                expected_uid_sha256=self.expected_uid_sha256,
                cutoff_ms=self.cutoff_ms,
                report_content_digest=self.report_content_digest,
                balance_content_digest=self.balance_content_digest,
                collection_evidence_digest=self.collection_evidence_digest,
                zero_event_digest=self.zero_event_digest,
            )
        return data

    @classmethod
    def from_wire(cls, data):
        if type(data) is not dict:
            raise ipc.ProtocolError("baseline evidence object required")
        return cls(
            data.get("contract_id"), data.get("account_alias"), data.get("environment"),
            data.get("source"), data.get("trading_day_start_ms"), data.get("observed_at_ms"),
            ipc.decimal_text(data.get("equity"), "baseline evidence equity", derived=True),
            data.get("event_semantics"), data.get("evidence_id"),
            data.get("expected_uid_sha256"), data.get("cutoff_ms"),
            data.get("report_content_digest"), data.get("balance_content_digest"),
            data.get("collection_evidence_digest"), data.get("zero_event_digest"))


@dataclass(frozen=True)
class DayBasis:
    day: int
    equity: Decimal
    evidence_id: str
    account_alias: str | None = None
    environment: str | None = None
    source: str | None = None
    digest: str | None = None
    evidence: BaselineEvidence | None = None

    def __post_init__(self):
        ipc.integer(self.day, "basis day")
        if decimal(self.equity, "day initial equity") <= 0:
            raise ipc.ProtocolError("day initial equity must be positive")
        ipc.token(self.evidence_id, "day basis evidence")
        if self.account_alias is not None:
            ipc.token(self.account_alias, "basis account alias")
        if self.environment is not None:
            ipc.token(self.environment, "basis environment")
        if self.source is not None:
            ipc.token(self.source, "basis source")
        if self.digest is not None:
            ipc.token(self.digest, "basis digest")
        if self.evidence is not None and not isinstance(self.evidence, BaselineEvidence):
            raise ipc.ProtocolError("invalid baseline evidence")

    def to_wire(self):
        data = dict(day=self.day, equity=str(self.equity), evidence_id=self.evidence_id)
        if self.account_alias is not None:
            data["account_alias"] = self.account_alias
        if self.environment is not None:
            data["environment"] = self.environment
        if self.source is not None:
            data["source"] = self.source
        if self.digest is not None:
            data["digest"] = self.digest
        if self.evidence is not None:
            data["evidence"] = self.evidence.to_wire()
        return data


def make_synthetic_baseline_evidence(*, account_alias: str, environment: str,
                                     day: int, equity: Decimal, evidence_id: str) -> BaselineEvidence:
    ipc.integer(day, "basis day")
    start_ms = day * DAY_MS - TAIPEI_OFFSET_MS
    return BaselineEvidence(
        SYNTHETIC_BASELINE_CONTRACT, account_alias, environment, SYNTHETIC_BASELINE_SOURCE,
        start_ms, start_ms, equity, SYNTHETIC_BASELINE_EVENT_SEMANTICS, evidence_id)


def make_demo_quiescent_baseline_evidence(
        *, account_alias: str, environment: str, day: int, cutoff_ms: int,
        equity: Decimal, evidence_id: str, expected_uid_sha256: str,
        report_content_digest: str, balance_content_digest: str,
        collection_evidence_digest: str, zero_event_digest: str) -> BaselineEvidence:
    ipc.integer(day, "basis day")
    start_ms = day * DAY_MS - TAIPEI_OFFSET_MS
    return BaselineEvidence(
        DEMO_QUIESCENT_BASELINE_CONTRACT,
        account_alias,
        environment,
        DEMO_QUIESCENT_BASELINE_SOURCE,
        start_ms,
        cutoff_ms,
        equity,
        DEMO_QUIESCENT_BASELINE_EVENT_SEMANTICS,
        evidence_id,
        expected_uid_sha256,
        cutoff_ms,
        report_content_digest,
        balance_content_digest,
        collection_evidence_digest,
        zero_event_digest,
    )


def compute_baseline_digest(*, account_alias: str, environment: str, day: int, equity: Decimal,
                            source: str, evidence_id: str,
                            evidence: BaselineEvidence | None = None) -> str:
    import hashlib
    import json
    trading_day_start_ms = day * 86_400_000 - 28_800_000
    payload = {
        "account_alias": account_alias,
        "day": day,
        "environment": environment,
        "equity": str(equity),
        "evidence_id": evidence_id,
        "source": source,
        "trading_day_start_ms": trading_day_start_ms,
        "evidence": None if evidence is None else evidence.to_wire(),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def is_verified_baseline(basis: DayBasis | None, *, account_alias: str, environment: str, target_day: int) -> bool:
    """Verify one authorized durable E₀ evidence contract and its persisted digest."""
    if not isinstance(basis, DayBasis) or not isinstance(basis.evidence, BaselineEvidence):
        return False
    if basis.day != target_day or basis.equity <= 0:
        return False
    if (basis.account_alias != account_alias
            or basis.environment != environment
            or basis.source not in AUTHORIZED_BASELINE_SOURCES
            or not basis.digest):
        return False
    evidence = basis.evidence
    trading_day_start_ms = basis.day * 86_400_000 - 28_800_000
    if (trading_day_start_ms < 0
            or evidence.account_alias != account_alias
            or evidence.environment != environment
            or evidence.source != basis.source
            or evidence.trading_day_start_ms != trading_day_start_ms
            or evidence.equity != basis.equity
            or evidence.evidence_id != basis.evidence_id):
        return False
    if basis.source == SYNTHETIC_BASELINE_SOURCE:
        if evidence.observed_at_ms != trading_day_start_ms:
            return False
    elif basis.source == DEMO_QUIESCENT_BASELINE_SOURCE:
        if (evidence.cutoff_ms != evidence.observed_at_ms
                or not trading_day_start_ms < evidence.observed_at_ms < trading_day_start_ms + DAY_MS):
            return False
    else:
        return False
    expected_digest = compute_baseline_digest(
        account_alias=account_alias,
        environment=environment,
        day=basis.day,
        equity=basis.equity,
        source=basis.source,
        evidence_id=basis.evidence_id,
        evidence=evidence,
    )
    return basis.digest == expected_digest


@dataclass(frozen=True)
class Snapshot:
    """Supervisor evidence; pending quantities include UNKNOWN, exclude local held intents.

    Other notional is the supplied worst-case total for the rest of the account.
    Margin/valuation/flow completeness are explicit synthetic facts, not models.
    """
    seq: int
    time_ms: int
    valid_until_ms: int
    equity: Decimal
    risk_equity: Decimal
    position: Decimal
    mark: Decimal
    pending_buy: Decimal = D("0")
    pending_sell: Decimal = D("0")
    other_notional: Decimal = D("0")
    external_net: Decimal = D("0")
    basis: DayBasis | None = None
    valuation_known: bool = True
    flows_known: bool = True
    margin_ok: bool = True
    position_verified: bool = True
    reduction_conflict: bool = False

    def __post_init__(self):
        ipc.integer(self.seq, "risk sequence", 1)
        ipc.integer(self.time_ms, "risk time")
        ipc.integer(self.valid_until_ms, "risk expiry")
        if self.valid_until_ms <= self.time_ms:
            raise ipc.ProtocolError("risk expiry must follow observation")
        for name in ("equity", "risk_equity", "position", "mark", "pending_buy",
                     "pending_sell", "other_notional", "external_net"):
            decimal(getattr(self, name), name)
        if self.mark <= 0 or min(self.pending_buy, self.pending_sell, self.other_notional) < 0:
            raise ipc.ProtocolError("invalid mark or pending exposure")
        for name in ("valuation_known", "flows_known", "margin_ok", "position_verified", "reduction_conflict"):
            if type(getattr(self, name)) is not bool:
                raise ipc.ProtocolError(f"{name} must be bool")
        if self.basis is not None and (not isinstance(self.basis, DayBasis)
                                      or self.basis.day != taipei_day(self.time_ms)):
            raise ipc.ProtocolError("basis must identify this Taipei day")

    def to_wire(self):
        return {name: (str(value) if isinstance(value, Decimal) else
                       value.to_wire() if isinstance(value, DayBasis) else value)
                for name, value in vars(self).items()}

    @classmethod
    def from_wire(cls, data):
        values = dict(data)
        for name in ("equity", "risk_equity", "position", "mark", "pending_buy",
                     "pending_sell", "other_notional", "external_net"):
            values[name] = ipc.decimal_text(values[name], name, derived=True)
        if values["basis"] is not None:
            basis = values["basis"]
            values["basis"] = DayBasis(
                basis["day"], D(basis["equity"]), basis["evidence_id"],
                account_alias=basis.get("account_alias"),
                environment=basis.get("environment"),
                source=basis.get("source"),
                digest=basis.get("digest"),
                evidence=None if basis.get("evidence") is None else BaselineEvidence.from_wire(basis["evidence"]),
            )
        return cls(**values)


@dataclass(frozen=True)
class State:
    seq: int = 0
    time_ms: int = 0
    mode: str = "RUN"
    health: str = "RECONCILING"
    phase: str = "IDLE"
    reasons: frozenset = frozenset()
    epoch: int = 0
    flatten_id: str | None = None
    basis: DayBasis | None = None
    snapshot: Snapshot | None = None
    basis_blocked_day: int | None = None

    def to_wire(self):
        return dict(seq=self.seq, time_ms=self.time_ms, mode=self.mode, health=self.health,
                    phase=self.phase, reasons=sorted(self.reasons), epoch=self.epoch,
                    flatten_id=self.flatten_id, basis=None if self.basis is None else self.basis.to_wire(),
                    snapshot=None if self.snapshot is None else self.snapshot.to_wire(),
                    basis_blocked_day=self.basis_blocked_day)

    @classmethod
    def from_wire(cls, data):
        values = dict(data)
        values["reasons"] = frozenset(values["reasons"])
        basis = values["basis"]
        values["basis"] = None if basis is None else DayBasis(
            basis["day"], D(basis["equity"]), basis["evidence_id"],
            account_alias=basis.get("account_alias"),
            environment=basis.get("environment"),
            source=basis.get("source"),
            digest=basis.get("digest"),
            evidence=None if basis.get("evidence") is None else BaselineEvidence.from_wire(basis["evidence"]),
        )
        values["snapshot"] = None if values["snapshot"] is None else Snapshot.from_wire(values["snapshot"])
        if values.get("basis_blocked_day") is not None:
            ipc.integer(values["basis_blocked_day"], "blocked basis day")
        return cls(**values)


def halt(state, reasons):
    reasons = frozenset(reasons)
    if not reasons <= HALTS:
        raise ipc.ProtocolError("unknown risk halt")
    merged = state.reasons | reasons
    epoch = state.epoch + len(merged - state.reasons)
    mode = "FLAT" if merged & {"hard_loss", "manual_kill"} else "NO_INCREASE" if merged else state.mode
    flatten_id = state.flatten_id or (f"flatten-{epoch}" if mode == "FLAT" else None)
    phase = "WORKING" if mode == "FLAT" and state.phase == "IDLE" else state.phase
    return replace(state, mode=mode, reasons=merged, epoch=epoch, flatten_id=flatten_id, phase=phase)


def loss_reasons(state, limits):
    s, basis = state.snapshot, state.basis
    if (s is None or basis is None or basis.day != taipei_day(s.time_ms)
            or not s.valuation_known or not s.flows_known):
        return frozenset()
    with localcontext(research._CONTEXT):
        loss = (s.equity - basis.equity - s.external_net) / basis.equity
        return frozenset(name for name, limit in (("soft_loss", limits.soft_loss),
                         ("hard_loss", limits.hard_loss)) if loss <= -limit)


def observe(state, snapshot, limits=Limits()):
    if snapshot.seq != state.seq + 1 or snapshot.time_ms < state.time_ms:
        raise ipc.ProtocolError("risk observation must follow sequence and time")
    day = taipei_day(snapshot.time_ms)
    blocked_day = state.basis_blocked_day
    if blocked_day is not None and day > blocked_day:
        blocked_day = None
    previous_day = None if state.seq == 0 else taipei_day(state.time_ms)
    if (state.seq == 0 or previous_day != day) and snapshot.basis is None:
        blocked_day = day
    if blocked_day == day and snapshot.basis is not None:
        raise ipc.ProtocolError("missing day basis cannot be rebuilt before next Taipei day")
    basis = state.basis
    if snapshot.basis is not None:
        if basis is not None and basis.day == snapshot.basis.day and basis != snapshot.basis:
            raise ipc.ProtocolError("fixed day basis cannot be replaced")
        basis = snapshot.basis
    basis_known = basis is not None and basis.day == taipei_day(snapshot.time_ms)
    health = "HEALTHY" if (basis_known and snapshot.valuation_known and snapshot.flows_known
                            and snapshot.equity > 0 and snapshot.risk_equity > 0
                            and snapshot.margin_ok) else "DEGRADED"
    result = replace(state, seq=snapshot.seq, time_ms=snapshot.time_ms, snapshot=snapshot,
                     basis=basis, health=health, epoch=state.epoch + (state.health != health),
                     basis_blocked_day=blocked_day)
    result = halt(result, loss_reasons(result, limits))
    if result.mode == "FLAT" and result.phase == "DONE" and (snapshot.position != 0
            or snapshot.pending_buy != 0 or snapshot.pending_sell != 0 or snapshot.other_notional != 0):
        result = replace(result, phase="WORKING")
    return result


def rearm(state, limits, now_ms, *, reconciled, manual_cause_cleared=False):
    """Explicit manual action; never called by observation/configuration changes."""
    current = expire(state, now_ms)
    s = current.snapshot
    if (not current.reasons or current.health != "HEALTHY" or not reconciled
            or s is None or not s.position_verified or s.reduction_conflict
            or s.pending_buy != 0 or s.pending_sell != 0
            or loss_reasons(current, limits)
            or ("manual_kill" in current.reasons and not manual_cause_cleared)
            or (current.mode == "FLAT" and (current.phase != "DONE" or s.position != 0
                                           or s.other_notional != 0))):
        raise ipc.ProtocolError("re-arm conditions not satisfied")
    return replace(current, mode="RUN", reasons=frozenset(), phase="IDLE",
                   flatten_id=None, epoch=current.epoch + 1)


def expire(state, now_ms):
    ipc.integer(now_ms, "risk timer")
    if now_ms < state.time_ms:
        raise ipc.ProtocolError("risk timer moved backwards")
    if (state.snapshot is None or now_ms >= state.snapshot.valid_until_ms
            or taipei_day(now_ms) != taipei_day(state.snapshot.time_ms)):
        return replace(state, time_ms=now_ms, health="DEGRADED", epoch=state.epoch + (state.health != "DEGRADED"))
    return replace(state, time_ms=now_ms)


def progress(state, phase, *, complete=False):
    """Execution progress is synthetic in F. Completion requires separate full proof."""
    if state.mode != "FLAT" or phase not in {"WORKING", "VERIFY", "WAIT", "DONE"}:
        raise ipc.ProtocolError("invalid flatten progress")
    if phase == "DONE" and (state.phase != "VERIFY" or not complete):
        raise ipc.ProtocolError("flatten completion requires verification")
    return replace(state, phase=phase)


def worst_notional(position, buys, sells, base_per_contract, mark):
    for name, value in (("position", position), ("buys", buys), ("sells", sells),
                        ("base_per_contract", base_per_contract), ("mark", mark)):
        decimal(value, name)
    if buys < 0 or sells < 0 or base_per_contract <= 0 or mark <= 0:
        raise ipc.ProtocolError("invalid exposure inputs")
    with localcontext(research._CONTEXT):
        return max(abs(position - sells), abs(position + buys)) * base_per_contract * mark


def effective_leverage(notionals, equity):
    """Actual marked exposure / equity; callers supply actual, not reserved amounts."""
    decimal(equity, "equity")
    if not isinstance(notionals, tuple) or len(notionals) > 64:
        raise ipc.ProtocolError("at most 64 actual notionals required")
    for value in notionals:
        if decimal(value, "actual notional") < 0:
            raise ipc.ProtocolError("actual notional cannot be negative")
    with localcontext(research._CONTEXT):
        return None if equity <= 0 else sum(notionals, D("0")) / equity


@dataclass(frozen=True)
class Verdict:
    accepted: bool
    reason: str
    quantity: Decimal = D("0")
    reservation: Decimal = D("0")
    reduce_only: bool = False


def evaluate(state, limits, contract, target, position, now_ms, *, held_buy=D("0"),
             held_sell=D("0"), held_reduction=False, reconciled=False):
    """Do not net opposite pending orders or credit reductions before fills."""
    decimal(target, "target")
    decimal(position, "decision position")
    decimal(held_buy, "held buys")
    decimal(held_sell, "held sells")
    ipc.integer(now_ms, "decision time")
    if held_buy < 0 or held_sell < 0:
        raise ipc.ProtocolError("negative held quantity")
    s = state.snapshot
    if s is None or now_ms < state.time_ms or not s.time_ms <= now_ms < s.valid_until_ms:
        return Verdict(False, "risk_snapshot_stale")
    if not reconciled or not s.position_verified or position != s.position:
        return Verdict(False, "position_not_verified")
    if target == position:
        return Verdict(False, "target_equals_position")
    with localcontext(research._CONTEXT):
        delta = target - position
        if target % contract.lot_size != 0 or delta % contract.lot_size != 0 or abs(delta) < contract.min_size:
            return Verdict(False, "invalid_contract_quantity")
        reduction = position != 0 and (target == 0 or (target * position > 0 and abs(target) < abs(position)))
        if reduction:
            conflict = s.reduction_conflict or held_reduction or (s.pending_sell > 0 if position > 0 else s.pending_buy > 0)
            return Verdict(not conflict, "reduction_conflict" if conflict else "legal_reduction",
                           delta if not conflict else D("0"), D("0"), not conflict)
        if state.mode != "RUN" or state.health != "HEALTHY":
            return Verdict(False, "increase_gate_closed")
        if state.basis is None or state.basis.day != taipei_day(now_ms):
            return Verdict(False, "day_basis_missing")
        # A reversal must be split into a proven reduction and a later increase.
        if position * target < 0:
            return Verdict(False, "cross_zero_forbidden")
        buys = s.pending_buy + held_buy + max(delta, D("0"))
        sells = s.pending_sell + held_sell + max(-delta, D("0"))
        notional = worst_notional(position, buys, sells, contract.base_per_contract, s.mark)
        budget = limits.leverage * s.risk_equity
        if notional + s.other_notional > budget:
            return Verdict(False, "account_exposure_limit")
        if notional > budget * limits.symbol_share:
            return Verdict(False, "symbol_exposure_limit")
        return Verdict(True, "exposure_reserved", delta, abs(delta) * contract.base_per_contract * s.mark)
