"""Pure Virtual Lot domain types for the isolated S1 data slice."""

from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext
import hashlib
import json
import re
from typing import Literal, TypeAlias

from catos import ipc, research
from catos.research import ContractSpec


Side: TypeAlias = Literal["long", "short"]
Environment: TypeAlias = Literal["local-sim", "demo", "live"]

_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_HEX_ID = re.compile(r"[0-9a-f]{64}\Z")
_ENVIRONMENTS = frozenset(("local-sim", "demo", "live"))
_SIDES = frozenset(("long", "short"))


class LotError(ValueError):
    """Stable S1 domain rejection with a non-sensitive machine-readable code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _token(value: object, code: str) -> str:
    if type(value) is not str or not _TOKEN.fullmatch(value):
        raise LotError(code)
    return value


def _hex_id(value: object) -> str:
    if type(value) is not str or not _HEX_ID.fullmatch(value):
        raise LotError("lot_identity_mismatch")
    return value


def _integer(value: object, code: str, *, minimum: int) -> int:
    if type(value) is not int or not minimum <= value <= ipc.MAX_INTEGER:
        raise LotError(code)
    return value


def _decimal(value: object, code: str, *, derived: bool, positive: bool = False,
             nonnegative: bool = False) -> Decimal:
    if not isinstance(value, Decimal):
        raise LotError(code)
    try:
        with localcontext(research._CONTEXT):
            if not value.is_finite():
                raise ValueError
            if derived:
                if (len(value.as_tuple().digits) > 50
                        or value.as_tuple().exponent < -148
                        or value.adjusted() > 99):
                    raise ValueError
            else:
                research._decimal(value, "lot decimal")
            if positive and value <= 0:
                raise ValueError
            if nonnegative and value < 0:
                raise ValueError
    except (ValueError, DecimalException):
        raise LotError(code) from None
    return value


def _multiple(value: Decimal, step: Decimal, code: str) -> None:
    try:
        with localcontext(research._CONTEXT):
            if value % step != 0:
                raise LotError(code)
    except DecimalException:
        raise LotError(code) from None


def _validate_contract(contract: object) -> ContractSpec:
    if not isinstance(contract, ContractSpec):
        raise LotError("invalid_contract")
    try:
        inst_id = _token(contract.inst_id, "invalid_contract")
        if not inst_id.endswith("-USDT-SWAP"):
            raise LotError("invalid_contract")
        base = _decimal(contract.base_per_contract, "invalid_contract", derived=False, positive=True)
        tick = _decimal(contract.tick_size, "invalid_contract", derived=False, positive=True)
        lot = _decimal(contract.lot_size, "invalid_contract", derived=False, positive=True)
        minimum = _decimal(contract.min_size, "invalid_contract", derived=False, positive=True)
        _multiple(minimum, lot, "invalid_contract")
        if minimum < lot or base <= 0 or tick <= 0:
            raise LotError("invalid_contract")
    except LotError:
        raise
    return contract


def _validate_side(side: object) -> Side:
    if type(side) is not str or side not in _SIDES:
        raise LotError("invalid_quantity")
    return side  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class LotScope:
    account_ref: str
    environment: Environment

    def __post_init__(self) -> None:
        _token(self.account_ref, "lot_scope_mismatch")
        if type(self.environment) is not str or self.environment not in _ENVIRONMENTS:
            raise LotError("lot_scope_mismatch")


@dataclass(frozen=True, slots=True)
class LotProtection:
    trigger_price_type: Literal["mark"]
    take_profit: Decimal | None
    stop_loss: Decimal | None

    def __post_init__(self) -> None:
        if self.trigger_price_type != "mark":
            raise LotError("invalid_protection")
        for value in (self.take_profit, self.stop_loss):
            if value is not None:
                _decimal(value, "invalid_protection", derived=False, positive=True)


@dataclass(frozen=True, slots=True)
class Lot:
    scope: LotScope
    bot_id: str
    inst_id: str
    lot_id: str
    open_intent_key: str
    side: Side
    opened_qty: Decimal
    remaining_qty: Decimal
    average_entry: Decimal
    realized_pnl: Decimal
    fees_paid: Decimal
    funding_paid: Decimal | None
    protection: LotProtection
    revision: int

    def __post_init__(self) -> None:
        _validate_lot_fields(self)
        _decimal(self.fees_paid, "invalid_decimal", derived=True)


def _validate_lot_fields(self) -> None:
    if not isinstance(self.scope, LotScope):
        raise LotError("lot_scope_mismatch")
    _token(self.bot_id, "lot_scope_mismatch")
    _token(self.inst_id, "invalid_contract")
    _hex_id(self.open_intent_key)
    _hex_id(self.lot_id)
    _validate_side(self.side)
    opened = _decimal(self.opened_qty, "invalid_quantity", derived=True, positive=True)
    remaining = _decimal(self.remaining_qty, "invalid_quantity", derived=True, nonnegative=True)
    if remaining > opened:
        raise LotError("invalid_quantity")
    _decimal(self.average_entry, "invalid_decimal", derived=True, positive=True)
    _decimal(self.realized_pnl, "invalid_decimal", derived=True)
    if self.funding_paid is not None:
        _decimal(self.funding_paid, "invalid_decimal", derived=True)
    if not isinstance(self.protection, LotProtection):
        raise LotError("invalid_protection")
    _integer(self.revision, "invalid_revision", minimum=1)
    if self.lot_id != make_lot_id(self.open_intent_key):
        raise LotError("lot_identity_mismatch")


@dataclass(frozen=True, slots=True)
class FeeQuality:
    coverage: Literal["MANAGED", "UNVERIFIED"]
    known_fee_subtotal: Decimal | None
    fee_unknown_fill_count: int | None

    def __post_init__(self) -> None:
        if type(self.coverage) is not str:
            raise LotError("invalid_fee_quality")
        if self.coverage == "MANAGED":
            _decimal(self.known_fee_subtotal, "invalid_fee_quality", derived=True)
            _integer(self.fee_unknown_fill_count, "invalid_fee_quality", minimum=0)
        elif self.coverage != "UNVERIFIED" or self.known_fee_subtotal is not None or self.fee_unknown_fill_count is not None:
            raise LotError("invalid_fee_quality")

    @property
    def fee_complete(self) -> bool | None:
        return self.fee_unknown_fill_count == 0 if self.coverage == "MANAGED" else None


@dataclass(frozen=True, slots=True)
class LotV2:
    scope: LotScope
    bot_id: str
    inst_id: str
    lot_id: str
    open_intent_key: str
    side: Side
    opened_qty: Decimal
    remaining_qty: Decimal
    average_entry: Decimal
    realized_pnl: Decimal
    fee_quality: FeeQuality
    funding_paid: Decimal | None
    protection: LotProtection
    revision: int

    def __post_init__(self) -> None:
        _validate_lot_fields(self)
        if type(self.fee_quality) is not FeeQuality:
            raise LotError("invalid_fee_quality")
        self.fee_quality.__post_init__()


@dataclass(frozen=True, slots=True)
class OpenLot:
    side: Side
    quantity: Decimal
    protection: LotProtection

    def __post_init__(self) -> None:
        _validate_side(self.side)
        _decimal(self.quantity, "invalid_quantity", derived=False, positive=True)
        if not isinstance(self.protection, LotProtection):
            raise LotError("invalid_protection")


@dataclass(frozen=True, slots=True)
class CloseLot:
    lot_id: str
    quantity: Decimal | None
    expected_revision: int

    def __post_init__(self) -> None:
        _hex_id(self.lot_id)
        if self.quantity is not None:
            _decimal(self.quantity, "invalid_quantity", derived=False, positive=True)
        _integer(self.expected_revision, "invalid_revision", minimum=1)


@dataclass(frozen=True, slots=True)
class UpdateLotProtection:
    lot_id: str
    protection: LotProtection
    expected_revision: int

    def __post_init__(self) -> None:
        _hex_id(self.lot_id)
        if not isinstance(self.protection, LotProtection):
            raise LotError("invalid_protection")
        _integer(self.expected_revision, "invalid_revision", minimum=1)


LotIntent: TypeAlias = OpenLot | CloseLot | UpdateLotProtection


@dataclass(frozen=True, slots=True)
class IntentContext:
    scope: LotScope
    bot_id: str
    contract: ContractSpec
    event_seq: int
    warmup: bool

    def __post_init__(self) -> None:
        if not isinstance(self.scope, LotScope):
            raise LotError("lot_scope_mismatch")
        _token(self.bot_id, "lot_scope_mismatch")
        _validate_contract(self.contract)
        _integer(self.event_seq, "invalid_view", minimum=1)
        if type(self.warmup) is not bool:
            raise LotError("invalid_view")


@dataclass(frozen=True, slots=True)
class LotValidationView:
    lot: Lot | None
    opening_unresolved: bool
    closing_unresolved: bool

    def __post_init__(self) -> None:
        if self.lot is not None and not isinstance(self.lot, Lot):
            raise LotError("invalid_view")
        if type(self.opening_unresolved) is not bool or type(self.closing_unresolved) is not bool:
            raise LotError("invalid_view")


@dataclass(frozen=True, slots=True)
class ValidatedLotIntent:
    intent_key: str
    scope: LotScope
    bot_id: str
    inst_id: str
    lot_id: str
    intent: LotIntent
    resolved_quantity: Decimal | None

    def __post_init__(self) -> None:
        _hex_id(self.intent_key)
        _hex_id(self.lot_id)
        if not isinstance(self.scope, LotScope):
            raise LotError("lot_scope_mismatch")
        _token(self.bot_id, "lot_scope_mismatch")
        _token(self.inst_id, "invalid_contract")
        if not isinstance(self.intent, (OpenLot, CloseLot, UpdateLotProtection)):
            raise LotError("invalid_view")
        if self.resolved_quantity is not None:
            # A full close resolves from the snapshot, not a Worker input.
            # OpenLot and explicit CloseLot quantities retain their input bounds.
            _decimal(self.resolved_quantity, "invalid_quantity", derived=True, positive=True)


def make_intent_key(context: IntentContext, output_index: int = 0) -> str:
    if not isinstance(context, IntentContext):
        raise LotError("invalid_view")
    if type(output_index) is not int or output_index != 0:
        raise LotError("invalid_view")
    payload = ["catos-lot-intent-v2", context.scope.account_ref, context.scope.environment,
               context.bot_id, context.contract.inst_id, context.event_seq, output_index]
    raw = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def make_lot_id(open_intent_key: str) -> str:
    _hex_id(open_intent_key)
    raw = json.dumps(["catos-lot-v2", open_intent_key], ensure_ascii=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_protection(protection: LotProtection, side: Side, contract: ContractSpec) -> None:
    if not isinstance(protection, LotProtection):
        raise LotError("invalid_protection")
    _validate_side(side)
    contract = _validate_contract(contract)
    for value in (protection.take_profit, protection.stop_loss):
        if value is not None:
            _multiple(value, contract.tick_size, "invalid_protection")
    if protection.take_profit is not None and protection.stop_loss is not None:
        if side == "long" and protection.stop_loss >= protection.take_profit:
            raise LotError("invalid_protection")
        if side == "short" and protection.take_profit >= protection.stop_loss:
            raise LotError("invalid_protection")


def validate_lot(lot: Lot, contract: ContractSpec) -> None:
    if not isinstance(lot, Lot):
        raise LotError("invalid_view")
    _validate_lot_contract(lot, contract)


def validate_lot_v2(lot: LotV2, contract: ContractSpec) -> None:
    if type(lot) is not LotV2:
        raise LotError("invalid_view")
    lot.__post_init__()
    _validate_lot_contract(lot, contract)


def _validate_lot_contract(lot, contract) -> None:
    contract = _validate_contract(contract)
    if lot.inst_id != contract.inst_id:
        raise LotError("invalid_contract")
    _multiple(lot.opened_qty, contract.lot_size, "invalid_quantity")
    _multiple(lot.remaining_qty, contract.lot_size, "invalid_quantity")
    validate_protection(lot.protection, lot.side, contract)


def _bound_lot(intent: CloseLot | UpdateLotProtection, context: IntentContext,
               view: LotValidationView, validator=validate_lot) -> Lot:
    if view.lot is None:
        if view.opening_unresolved or view.closing_unresolved:
            raise LotError("invalid_view")
        raise LotError("lot_not_found")
    lot = view.lot
    if (lot.scope != context.scope or lot.bot_id != context.bot_id
            or lot.inst_id != context.contract.inst_id):
        raise LotError("lot_scope_mismatch")
    if intent.lot_id != lot.lot_id:
        raise LotError("lot_identity_mismatch")
    validator(lot, context.contract)
    if intent.expected_revision != lot.revision:
        raise LotError("revision_conflict")
    if lot.remaining_qty == 0:
        raise LotError("lot_closed")
    if view.opening_unresolved or view.closing_unresolved:
        raise LotError("lot_busy")
    return lot


def validate_intent(intent: LotIntent, context: IntentContext,
                    view: LotValidationView) -> ValidatedLotIntent:
    if not isinstance(context, IntentContext) or not isinstance(view, LotValidationView):
        raise LotError("invalid_view")
    return _validate_intent(intent, context, view, validate_lot)


@dataclass(frozen=True, slots=True)
class LotValidationViewV2:
    lot: LotV2 | None
    opening_unresolved: bool
    closing_unresolved: bool

    def __post_init__(self):
        if self.lot is not None and type(self.lot) is not LotV2:
            raise LotError("invalid_view")
        if type(self.opening_unresolved) is not bool or type(self.closing_unresolved) is not bool:
            raise LotError("invalid_view")


def validate_intent_v2(intent, context, view):
    if not isinstance(context, IntentContext) or type(view) is not LotValidationViewV2:
        raise LotError("invalid_view")
    view.__post_init__()
    return _validate_intent(intent, context, view, validate_lot_v2)


def _validate_intent(intent, context, view, validator):
    if not isinstance(intent, (OpenLot, CloseLot, UpdateLotProtection)):
        raise LotError("invalid_view")
    if context.warmup:
        raise LotError("warmup_intent_forbidden")
    intent_key = make_intent_key(context)

    if isinstance(intent, OpenLot):
        if view.lot is not None or view.opening_unresolved or view.closing_unresolved:
            raise LotError("invalid_view")
        validate_protection(intent.protection, intent.side, context.contract)
        _multiple(intent.quantity, context.contract.lot_size, "invalid_quantity")
        if intent.quantity < context.contract.min_size:
            raise LotError("invalid_quantity")
        lot_id = make_lot_id(intent_key)
        return ValidatedLotIntent(intent_key, context.scope, context.bot_id,
                                  context.contract.inst_id, lot_id, intent, intent.quantity)

    lot = _bound_lot(intent, context, view, validator)
    if isinstance(intent, CloseLot):
        quantity = lot.remaining_qty if intent.quantity is None else intent.quantity
        _multiple(quantity, context.contract.lot_size, "invalid_quantity")
        if quantity > lot.remaining_qty:
            raise LotError("over_close")
        return ValidatedLotIntent(intent_key, context.scope, context.bot_id,
                                  context.contract.inst_id, lot.lot_id, intent, quantity)

    validate_protection(intent.protection, lot.side, context.contract)
    return ValidatedLotIntent(intent_key, context.scope, context.bot_id,
                              context.contract.inst_id, lot.lot_id, intent, None)
