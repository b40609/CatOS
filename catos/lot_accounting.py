"""Synthetic per-fill accounting. No exchange adapter or execution authority."""

from dataclasses import dataclass, replace
from decimal import Decimal, DecimalException, Underflow, localcontext

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


def apply_fill(before, validated, contract, fill):
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
        lots.validate_lot(before, contract)
        if (before.lot_id != validated.lot_id or before.bot_id != validated.bot_id
                or before.scope != validated.scope):
            raise lots.LotError("lot_identity_mismatch")
        if before.remaining_qty == 0:
            raise lots.LotError("lot_closed")
    try:
        with localcontext(research._CONTEXT) as ctx:
            ctx.traps[Underflow] = True
            q, p = fill.quantity, fill.price
            if validated.resolved_quantity is None or q > validated.resolved_quantity:
                raise lots.LotError("over_fill")
            if isinstance(validated.intent, lots.OpenLot):
                if before is not None and exact_quantity(before.opened_qty, q) > validated.resolved_quantity:
                    raise lots.LotError("over_fill")
                if before is None:
                    result = lots.Lot(validated.scope, validated.bot_id, contract.inst_id,
                                      validated.lot_id, validated.intent_key, validated.intent.side,
                                      q, q, p, Decimal(0), fill.fee_paid, None,
                                      validated.intent.protection, 1)
                else:
                    remaining = exact_quantity(before.remaining_qty, q)
                    result = replace(before, opened_qty=exact_quantity(before.opened_qty, q),
                                     remaining_qty=remaining,
                                     average_entry=(before.remaining_qty * before.average_entry + q * p) / remaining,
                                     fees_paid=before.fees_paid + fill.fee_paid, revision=before.revision + 1)
            elif isinstance(validated.intent, lots.CloseLot) and before is not None:
                if q > before.remaining_qty:
                    raise lots.LotError("over_close")
                sign = Decimal(1 if before.side == "long" else -1)
                result = replace(before, remaining_qty=exact_quantity(before.remaining_qty, q.copy_negate()),
                                 realized_pnl=before.realized_pnl + sign * (p - before.average_entry) * q * contract.base_per_contract,
                                 fees_paid=before.fees_paid + fill.fee_paid, revision=before.revision + 1)
            else:
                raise lots.LotError("invalid_fill")
            lots.validate_lot(result, contract)
            return result
    except DecimalException as exc:
        raise lots.LotError("invalid_decimal") from exc
