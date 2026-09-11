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

    def __post_init__(self):
        if decimal(self.leverage, "leverage") <= 0:
            raise ipc.ProtocolError("leverage must be positive")
        if not 0 < decimal(self.symbol_share, "symbol_share") <= 1:
            raise ipc.ProtocolError("symbol_share must be in (0,1]")

    def to_wire(self):
        return dict(leverage=str(self.leverage), symbol_share=str(self.symbol_share))


@dataclass(frozen=True)
class DayBasis:
    day: int
    equity: Decimal
    evidence_id: str

    def __post_init__(self):
        ipc.integer(self.day, "basis day")
        if decimal(self.equity, "day initial equity") <= 0:
            raise ipc.ProtocolError("day initial equity must be positive")
        ipc.token(self.evidence_id, "day basis evidence")

    def to_wire(self):
        return dict(day=self.day, equity=str(self.equity), evidence_id=self.evidence_id)


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
            values["basis"] = DayBasis(basis["day"], D(basis["equity"]), basis["evidence_id"])
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

    def to_wire(self):
        return dict(seq=self.seq, time_ms=self.time_ms, mode=self.mode, health=self.health,
                    phase=self.phase, reasons=sorted(self.reasons), epoch=self.epoch,
                    flatten_id=self.flatten_id, basis=None if self.basis is None else self.basis.to_wire(),
                    snapshot=None if self.snapshot is None else self.snapshot.to_wire())

    @classmethod
    def from_wire(cls, data):
        values = dict(data)
        values["reasons"] = frozenset(values["reasons"])
        basis = values["basis"]
        values["basis"] = None if basis is None else DayBasis(basis["day"], D(basis["equity"]), basis["evidence_id"])
        values["snapshot"] = None if values["snapshot"] is None else Snapshot.from_wire(values["snapshot"])
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


def observe(state, snapshot):
    if snapshot.seq != state.seq + 1 or snapshot.time_ms < state.time_ms:
        raise ipc.ProtocolError("risk observation must follow sequence and time")
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
                     basis=basis, health=health, epoch=state.epoch + (state.health != health))
    if basis_known and snapshot.valuation_known and snapshot.flows_known:
        with localcontext(research._CONTEXT):
            loss = (snapshot.equity - basis.equity - snapshot.external_net) / basis.equity
        reasons = {"soft_loss"} if loss <= D("-0.03") else set()
        if loss <= D("-0.05"):
            reasons.add("hard_loss")
        result = halt(result, reasons)
    if result.mode == "FLAT" and result.phase == "DONE" and (snapshot.position != 0
            or snapshot.pending_buy != 0 or snapshot.pending_sell != 0 or snapshot.other_notional != 0):
        result = replace(result, phase="WORKING")
    return result


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
