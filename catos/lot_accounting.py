"""Synthetic per-fill accounting. No exchange adapter or execution authority."""

from dataclasses import dataclass, replace
from decimal import Decimal, DecimalException, Underflow, localcontext
from typing import Literal

from catos import ipc, lots, research


@dataclass(frozen=True, slots=True)
class SyntheticFill:
    scope: lots.LotScope
    source_id: str
    inst_id: str
    order_id: str
    trade_id: str
    fill_seq: int
    quantity: Decimal
    price: Decimal
    fee_paid: Decimal
    fee_currency: str = "USDT"

    def __post_init__(self):
        if not isinstance(self.scope, lots.LotScope):
            raise lots.LotError("invalid_fill")
        for name in ("source_id", "inst_id", "order_id", "trade_id"):
            ipc.token(getattr(self, name), name)
        ipc.integer(self.fill_seq, "fill_seq", 1)
        lots._decimal(self.quantity, "invalid_fill", derived=True, positive=True)
        lots._decimal(self.price, "invalid_fill", derived=False, positive=True)
        lots._decimal(self.fee_paid, "invalid_fill", derived=False)
        if self.fee_currency != "USDT":
            raise lots.LotError("unsupported_fee")


def exact_quantity(left, right):
    """Bounded exact sum; never silently lose a small executed quantity."""
    for value in (left, right):
        lots._decimal(value, "invalid_quantity", derived=True)
    try:
        with localcontext(research._CONTEXT) as ctx:
            ctx.prec = 300
            result = left + right
            result = result.normalize() if result else Decimal(0)
    except DecimalException as exc:
        raise lots.LotError("invalid_quantity") from exc
    return lots._decimal(result, "invalid_quantity", derived=True, nonnegative=True)


@dataclass(frozen=True, slots=True)
class SyntheticFillV2:
    scope: lots.LotScope
    source_id: str
    inst_id: str
    order_id: str
    trade_id: str
    fill_seq: int
    quantity: Decimal
    price: Decimal
    fee_state: Literal["KNOWN", "UNKNOWN"]
    fee_paid: Decimal | None
    fee_currency: Literal["USDT"] = "USDT"

    def __post_init__(self):
        _fee_identity(self)
        if type(self.fee_state) is not str:
            raise lots.LotError("invalid_fee_state")
        ipc.integer(self.fill_seq, "fill_seq", 1)
        lots._decimal(self.quantity, "invalid_fill", derived=True, positive=True)
        lots._decimal(self.price, "invalid_fill", derived=False, positive=True)
        if self.fee_state == "KNOWN":
            if self.fee_paid is None:
                raise lots.LotError("invalid_fee_state")
            lots._decimal(self.fee_paid, "invalid_fill", derived=False)
        elif self.fee_state != "UNKNOWN" or self.fee_paid is not None:
            raise lots.LotError("invalid_fee_state")


@dataclass(frozen=True, slots=True)
class FeeCompletion:
    scope: lots.LotScope
    source_id: str
    inst_id: str
    order_id: str
    trade_id: str
    fee_paid: Decimal
    fee_currency: Literal["USDT"] = "USDT"

    def __post_init__(self):
        _fee_identity(self)
        lots._decimal(self.fee_paid, "invalid_fill", derived=False)


@dataclass(frozen=True, slots=True)
class FeeCorrection:
    scope: lots.LotScope
    source_id: str
    inst_id: str
    order_id: str
    trade_id: str
    correction_id: str
    predecessor_event_seq: int
    fee_paid: Decimal
    fee_currency: Literal["USDT"] = "USDT"

    def __post_init__(self):
        validate_correction_identity(self.scope, self.source_id, self.inst_id,
                                     self.order_id, self.trade_id, self.correction_id)
        try:
            ipc.token(self.correction_id, "correction_id")
            ipc.integer(self.predecessor_event_seq, "predecessor_event_seq", 1)
        except ValueError as exc:
            raise lots.LotError("invalid_fee_correction") from exc
        if type(self.fee_currency) is not str or self.fee_currency != "USDT":
            raise lots.LotError("unsupported_fee")
        lots._decimal(self.fee_paid, "invalid_fee_correction", derived=False)


def validate_correction_identity(scope, source_id, inst_id, order_id, trade_id,
                                 correction_id=None):
    if not isinstance(scope, lots.LotScope) or scope.environment != "local-sim":
        raise lots.LotError("scope_mismatch")
    try:
        lots.LotScope(scope.account_ref, scope.environment)
    except ValueError as exc:
        raise lots.LotError("scope_mismatch") from exc
    try:
        for value in (source_id, inst_id, order_id, trade_id):
            ipc.token(value, "fee identity")
        if correction_id is not None:
            ipc.token(correction_id, "correction_id")
    except ValueError as exc:
        raise lots.LotError("invalid_fee_correction") from exc


@dataclass(frozen=True, slots=True)
class EffectiveFee:
    scope: lots.LotScope
    source_id: str
    inst_id: str
    order_id: str
    trade_id: str
    fee_state: Literal["KNOWN", "UNKNOWN"]
    fee_paid: Decimal | None
    fee_currency: Literal["USDT"]
    effective_event_seq: int | None
    effective_event_kind: Literal["fill", "fee_completion", "fee_correction"] | None

    def __post_init__(self):
        validate_correction_identity(self.scope, self.source_id, self.inst_id, self.order_id, self.trade_id)
        if type(self.fee_currency) is not str or self.fee_currency != "USDT":
            raise lots.LotError("unsupported_fee")
        if type(self.fee_state) is not str:
            raise lots.LotError("invalid_fee_state")
        if self.fee_state == "UNKNOWN":
            if any(v is not None for v in (self.fee_paid, self.effective_event_seq, self.effective_event_kind)):
                raise lots.LotError("invalid_fee_state")
        elif self.fee_state == "KNOWN":
            lots._decimal(self.fee_paid, "invalid_fee_correction", derived=False)
            ipc.integer(self.effective_event_seq, "effective_event_seq", 1)
            if (type(self.effective_event_kind) is not str
                    or self.effective_event_kind not in ("fill", "fee_completion", "fee_correction")):
                raise lots.LotError("invalid_fee_state")
        else:
            raise lots.LotError("invalid_fee_state")


def correct_fee(before, correction, old_effective_fee):
    """P2A arithmetic only; the journal proves target, predecessor and active flags."""
    if type(before) is not lots.LotV2 or type(correction) is not FeeCorrection:
        raise lots.LotError("unsupported_fee_version")
    before, correction = replace(before), replace(correction)
    if before.scope != correction.scope or before.inst_id != correction.inst_id:
        raise lots.LotError("scope_mismatch")
    quality = before.fee_quality
    if quality.coverage != "MANAGED":
        raise lots.LotError("unmanaged_lot")
    lots._decimal(old_effective_fee, "invalid_fee_correction", derived=False)
    if old_effective_fee == correction.fee_paid:
        raise lots.LotError("no_change")
    if before.revision == ipc.MAX_INTEGER:
        raise lots.LotError("sequence_exhausted")
    try:
        with localcontext(research._CONTEXT) as ctx:
            ctx.clear_flags()
            ctx.traps[Underflow] = True
            intermediate = quality.known_fee_subtotal - old_effective_fee
            lots._decimal(intermediate, "invalid_decimal", derived=True)
            subtotal = intermediate + correction.fee_paid
            lots._decimal(subtotal, "invalid_decimal", derived=True)
            return replace(before, revision=before.revision + 1,
                           fee_quality=lots.FeeQuality("MANAGED", subtotal, quality.fee_unknown_fill_count))
    except DecimalException as exc:
        raise lots.LotError("invalid_decimal") from exc


def _fee_identity(value):
    if not isinstance(value.scope, lots.LotScope):
        raise lots.LotError("invalid_fill")
    lots.LotScope(value.scope.account_ref, value.scope.environment)
    for name in ("source_id", "inst_id", "order_id", "trade_id"):
        ipc.token(getattr(value, name), name)
    if type(value.fee_currency) is not str or value.fee_currency != "USDT":
        raise lots.LotError("unsupported_fee")


def apply_fill(before, validated, contract, fill):
    if type(fill) is not SyntheticFill or (before is not None and type(before) is not lots.Lot):
        raise lots.LotError("unsupported_fee_version")
    return _apply_fill(before, validated, contract, fill, False)


def apply_fill_v2(before, validated, contract, fill):
    if type(fill) is not SyntheticFillV2 or (before is not None and type(before) is not lots.LotV2):
        raise lots.LotError("unsupported_fee_version")
    return _apply_fill(before, validated, contract, fill, True)


def complete_fee(before, completion):
    if type(before) is not lots.LotV2 or type(completion) is not FeeCompletion:
        raise lots.LotError("unsupported_fee_version")
    before, completion = replace(before), replace(completion)
    if before.scope != completion.scope or before.inst_id != completion.inst_id:
        raise lots.LotError("lot_scope_mismatch")
    quality = before.fee_quality
    if quality.coverage != "MANAGED":
        raise lots.LotError("unmanaged_lot")
    if quality.fee_unknown_fill_count == 0:
        raise lots.LotError("integrity_error")
    try:
        with localcontext(research._CONTEXT) as ctx:
            ctx.traps[Underflow] = True
            quality = lots.FeeQuality("MANAGED", quality.known_fee_subtotal + completion.fee_paid,
                                      quality.fee_unknown_fill_count - 1)
            return replace(before, fee_quality=quality, revision=before.revision + 1)
    except DecimalException as exc:
        raise lots.LotError("invalid_decimal") from exc


def _apply_fill(before, validated, contract, fill, v2):
    """Return the next immutable snapshot; callers own deduplication and limits."""
    fill = replace(fill)  # Revalidate even a locally forged frozen instance.
    lots._validate_contract(contract)
    if (fill.scope != validated.scope or fill.inst_id != contract.inst_id
            or validated.inst_id != contract.inst_id):
        raise lots.LotError("lot_scope_mismatch")
    lots._multiple(fill.quantity, contract.lot_size, "invalid_quantity")
    lots._multiple(fill.price, contract.tick_size, "invalid_price")
    if before is not None:
        before = replace(before)
        (lots.validate_lot_v2 if v2 else lots.validate_lot)(before, contract)
        if (before.lot_id != validated.lot_id or before.bot_id != validated.bot_id
                or before.scope != validated.scope):
            raise lots.LotError("lot_identity_mismatch")
        if before.remaining_qty == 0:
            raise lots.LotError("lot_closed")
    try:
        with localcontext(research._CONTEXT) as ctx:
            ctx.traps[Underflow] = True
            if v2:
                quality = lots.FeeQuality("MANAGED", Decimal(0), 0) if before is None else before.fee_quality
                if quality.coverage != "MANAGED":
                    raise lots.LotError("unmanaged_lot")
                quality = lots.FeeQuality("MANAGED",
                    quality.known_fee_subtotal + fill.fee_paid if fill.fee_state == "KNOWN" else quality.known_fee_subtotal,
                    quality.fee_unknown_fill_count + (1 if fill.fee_state == "UNKNOWN" else 0))
                fee = dict(fee_quality=quality)
            else:
                fee = dict(fees_paid=fill.fee_paid if before is None else before.fees_paid + fill.fee_paid)
            q, p = fill.quantity, fill.price
            if validated.resolved_quantity is None or q > validated.resolved_quantity:
                raise lots.LotError("over_fill")
            if isinstance(validated.intent, lots.OpenLot):
                if before is not None and exact_quantity(before.opened_qty, q) > validated.resolved_quantity:
                    raise lots.LotError("over_fill")
                if before is None:
                    result = (lots.LotV2 if v2 else lots.Lot)(validated.scope, validated.bot_id, contract.inst_id,
                                      validated.lot_id, validated.intent_key, validated.intent.side,
                                      q, q, p, Decimal(0), quality if v2 else fill.fee_paid, None,
                                      validated.intent.protection, 1)
                else:
                    remaining = exact_quantity(before.remaining_qty, q)
                    result = replace(before, opened_qty=exact_quantity(before.opened_qty, q),
                                     remaining_qty=remaining,
                                     average_entry=(before.remaining_qty * before.average_entry + q * p) / remaining,
                                     **fee, revision=before.revision + 1)
            elif isinstance(validated.intent, lots.CloseLot) and before is not None:
                if q > before.remaining_qty:
                    raise lots.LotError("over_close")
                sign = Decimal(1 if before.side == "long" else -1)
                result = replace(before, remaining_qty=exact_quantity(before.remaining_qty, q.copy_negate()),
                                 realized_pnl=before.realized_pnl + sign * (p - before.average_entry) * q * contract.base_per_contract,
                                 **fee, revision=before.revision + 1)
            else:
                raise lots.LotError("invalid_fill")
            (lots.validate_lot_v2 if v2 else lots.validate_lot)(result, contract)
            return result
    except DecimalException as exc:
        raise lots.LotError("invalid_decimal") from exc
