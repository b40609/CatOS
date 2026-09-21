"""Pure synthetic exposure observations; no risk verdict or persistence access."""

from dataclasses import dataclass, replace
from decimal import Context, Decimal, DecimalException, Inexact, ROUND_HALF_EVEN, Underflow, localcontext

from catos import ipc, lots
from catos.lot_journal import StoredLot, StoredLotV2
from catos.research import ContractSpec


MAX_BOTS = 64
MAX_LOTS = 4096
MAX_PENDING = 4096
_CONTEXT = Context(prec=512, rounding=ROUND_HALF_EVEN, Emin=-999, Emax=999)
_CONTEXT.traps[Inexact] = True
_CONTEXT.traps[Underflow] = True
ZERO = Decimal(0)


class ExposureInputError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class LotInventory:
    scope: lots.LotScope
    inst_id: str
    cut_id: str
    observed_at_ms: int
    valid_until_ms: int
    complete: bool
    expected_bot_ids: tuple[str, ...]
    included_bot_ids: tuple[str, ...]
    lots: tuple[StoredLot, ...]


@dataclass(frozen=True, slots=True)
class LotInventoryV2:
    scope: lots.LotScope
    inst_id: str
    cut_id: str
    observed_at_ms: int
    valid_until_ms: int
    complete: bool
    expected_bot_ids: tuple[str, ...]
    included_bot_ids: tuple[str, ...]
    lots: tuple[StoredLotV2, ...]


@dataclass(frozen=True, slots=True)
class PhysicalPosition:
    scope: lots.LotScope
    inst_id: str
    cut_id: str
    observed_at_ms: int
    valid_until_ms: int
    quantity: Decimal | None
    verified: bool


@dataclass(frozen=True, slots=True)
class MarkObservation:
    scope: lots.LotScope
    inst_id: str
    quote_id: str
    observed_at_ms: int
    valid_until_ms: int
    mark: Decimal


@dataclass(frozen=True, slots=True)
class PendingObligation:
    obligation_id: str
    origin: str
    state: str
    side: str
    remaining_quantity: Decimal | None
    effect: str
    lot_id: str | None


@dataclass(frozen=True, slots=True)
class PendingInventory:
    scope: lots.LotScope
    inst_id: str
    cut_id: str
    observed_at_ms: int
    valid_until_ms: int
    complete: bool
    orders: tuple[PendingObligation, ...]


@dataclass(frozen=True, slots=True)
class ExposureRequest:
    scope: lots.LotScope
    contract: ContractSpec
    now_ms: int
    lots_view: LotInventory
    physical_view: PhysicalPosition
    mark_view: MarkObservation | None
    pending_view: PendingInventory | None
    evidence_kind: str = "OBSERVED"


@dataclass(frozen=True, slots=True)
class ExposureRequestV2:
    scope: lots.LotScope
    contract: ContractSpec
    now_ms: int
    lots_view: LotInventoryV2
    physical_view: PhysicalPosition
    mark_view: MarkObservation | None
    pending_view: PendingInventory | None
    evidence_kind: str = "OBSERVED"


@dataclass(frozen=True, slots=True)
class ExposureReport:
    scope: lots.LotScope
    contract: ContractSpec
    now_ms: int
    lot_cut_id: str
    physical_cut_id: str
    pending_cut_id: str | None
    quote_id: str | None
    observed_long_qty: Decimal
    observed_short_qty: Decimal
    observed_gross_qty: Decimal
    observed_net_qty: Decimal
    physical_qty: Decimal | None
    delta_qty: Decimal | None
    comparison_status: str
    observed_gross_notional: Decimal | None
    observed_signed_net_notional: Decimal | None
    physical_notional: Decimal | None
    pending_buy_qty: Decimal | None
    pending_sell_qty: Decimal | None
    held_buy_qty: Decimal | None
    held_sell_qty: Decimal | None
    exchange_buy_qty: Decimal | None
    exchange_sell_qty: Decimal | None
    physical_scenario_upper_qty: Decimal | None
    virtual_gross_scenario_upper_qty: Decimal | None
    lot_complete: bool
    lot_fresh: bool
    physical_fresh: bool
    physical_verified: bool
    mark_fresh: bool
    pending_complete: bool
    pending_fresh: bool
    has_unknown: bool
    unresolved_lot_count: int
    pending_unique_count: int
    pending_duplicate_count: int
    reasons: tuple[str, ...]
    synthetic_buy_qty: Decimal | None = ZERO
    synthetic_sell_qty: Decimal | None = ZERO
    evidence_kind: str = "OBSERVED"


def _reject(code):
    raise ExposureInputError(code)


def _bool(value):
    if type(value) is not bool:
        _reject("invalid_integer")


def _integer(value, minimum=0):
    if type(value) is not int or not minimum <= value <= ipc.MAX_INTEGER:
        _reject("invalid_integer")


def _token(value, code="identity_mismatch"):
    try:
        ipc.token(value, "identity")
    except ValueError:
        _reject(code)


def _decimal(value, *, positive=False, nonnegative=False):
    try:
        return lots._decimal(value, "invalid_decimal", derived=True,
                             positive=positive, nonnegative=nonnegative)
    except ValueError:
        _reject("invalid_decimal")


def _result(value):
    # The surrounding 512-digit context is sufficient for all bounded inputs.
    value = value.normalize() if value else ZERO
    try:
        return lots._decimal(value, "decimal_range", derived=True)
    except ValueError:
        _reject("decimal_range")


def _tuple(value, limit, code="input_limit"):
    if type(value) is not tuple or len(value) > limit:
        _reject(code)


def _aligned(value, contract):
    if value % contract.lot_size != 0:
        _reject("invalid_decimal")


def _scope(value):
    if not isinstance(value, lots.LotScope) or value.environment != "local-sim":
        _reject("invalid_scope")
    _token(value.account_ref, "invalid_scope")


def _source(value, cls, request, reasons, prefix):
    if not isinstance(value, cls):
        _reject("identity_mismatch")
    _scope(value.scope)
    if value.scope != request.scope or value.inst_id != request.contract.inst_id:
        _reject("identity_mismatch")
    _token(value.quote_id if cls is MarkObservation else value.cut_id)
    _integer(value.observed_at_ms)
    _integer(value.valid_until_ms)
    if value.valid_until_ms <= value.observed_at_ms:
        _reject("invalid_time_range")
    fresh = value.observed_at_ms <= request.now_ms < value.valid_until_ms
    if not fresh:
        reasons.add(prefix + "_stale")
    if value.observed_at_ms > request.now_ms:
        reasons.add("future_observation")
    return fresh


def _inventory(view, contract, *, v2=False):
    _bool(view.complete)
    for names in (view.expected_bot_ids, view.included_bot_ids):
        _tuple(names, MAX_BOTS)
        for name in names:
            _token(name, "invalid_bot_coverage")
        if len(set(names)) != len(names):
            _reject("invalid_bot_coverage")
    expected, included = set(view.expected_bot_ids), set(view.included_bot_ids)
    if not included <= expected or (view.complete and included != expected):
        _reject("invalid_bot_coverage")
    _tuple(view.lots, MAX_LOTS)
    entries = {}
    for item in view.lots:
        if not isinstance(item, StoredLotV2 if v2 else StoredLot):
            _reject("identity_mismatch")
        _bool(item.opening_unresolved)
        _bool(item.closing_unresolved)
        _integer(item.commit_seq, 1)
        try:
            if not isinstance(item.lot, lots.LotV2 if v2 else lots.Lot):
                _reject("identity_mismatch")
            # Reconstruct nested immutable values to detect forged local objects.
            lot = replace(item.lot, scope=lots.LotScope(item.lot.scope.account_ref, item.lot.scope.environment),
                          protection=replace(item.lot.protection))
            (lots.validate_lot_v2 if v2 else lots.validate_lot)(lot, contract)
        except (ValueError, TypeError, AttributeError) as exc:
            if isinstance(exc, ExposureInputError):
                raise
            _reject("invalid_decimal" if isinstance(exc, lots.LotError) and exc.code in
                    ("invalid_decimal", "invalid_quantity") else "identity_mismatch")
        if lot.scope != view.scope or lot.inst_id != view.inst_id or lot.bot_id not in included:
            _reject("identity_mismatch")
        if lot.lot_id in entries:
            _reject("duplicate_lot")
        entries[lot.lot_id] = replace(item, lot=lot)
    return entries


def _pending(view, entries, contract, reasons, evidence_kind):
    _bool(view.complete)
    _tuple(view.orders, MAX_PENDING)
    unique, linked = {}, {}
    for order in view.orders:
        if not isinstance(order, PendingObligation):
            _reject("pending_conflict")
        _token(order.obligation_id, "pending_conflict")
        allowed = {"HELD": ("HELD",), "EXCHANGE": ("WORKING", "UNKNOWN")}
        if evidence_kind == "SYNTHETIC_SCENARIO":
            allowed = {"SYNTHETIC_LEDGER": ("UNTERMINATED",)}
        if not isinstance(order.origin, str) or order.state not in allowed.get(order.origin, ()):
            _reject("pending_conflict")
        if order.side not in ("BUY", "SELL") or order.effect not in ("OPEN", "CLOSE", "UNCLASSIFIED"):
            _reject("invalid_pending_direction")
        if order.remaining_quantity is not None:
            _decimal(order.remaining_quantity, nonnegative=True)
            _aligned(order.remaining_quantity, contract)
        if order.lot_id is not None:
            try:
                lots._hex_id(order.lot_id)
            except ValueError:
                _reject("identity_mismatch")
        elif order.effect != "UNCLASSIFIED":
            _reject("identity_mismatch")
        previous = unique.get(order.obligation_id)
        if previous is not None:
            if previous != order:
                _reject("pending_conflict")
            continue
        unique[order.obligation_id] = order
        if order.lot_id is not None:
            if order.lot_id in linked:
                _reject("pending_conflict")
            linked[order.lot_id] = order
        item = entries.get(order.lot_id)
        if order.effect == "CLOSE" and item is None:
            _reject("identity_mismatch")
        if item is not None and order.effect != "UNCLASSIFIED":
            buy = (item.lot.side == "long") == (order.effect == "OPEN")
            if order.side != ("BUY" if buy else "SELL"):
                _reject("invalid_pending_direction")
        if item is None and order.lot_id is not None and order.effect == "UNCLASSIFIED":
            reasons.add("pending_lot_link_incomplete")
    for lot_id, item in entries.items():
        order = linked.get(lot_id)
        opened, closed = item.opening_unresolved, item.closing_unresolved
        if opened and closed:
            reasons.add("pending_lot_link_incomplete")
        elif order is None:
            if opened or closed:
                reasons.add("pending_lot_link_incomplete")
        elif (not (opened or closed) or (order.effect == "OPEN" and not opened)
              or (order.effect == "CLOSE" and not closed)):
            reasons.add("pending_lot_link_incomplete")
    return tuple(unique[key] for key in sorted(unique)), len(view.orders) - len(unique)


def observe_exposure(request: ExposureRequest) -> ExposureReport:
    """Validate evidence and return observations, never an execution verdict."""
    try:
        with localcontext(_CONTEXT):
            return _observe(request)
    except DecimalException as exc:
        raise ExposureInputError("decimal_range") from exc


def observe_exposure_v2(request: ExposureRequestV2) -> ExposureReport:
    try:
        with localcontext(_CONTEXT):
            return _observe(request, v2=True)
    except DecimalException as exc:
        raise ExposureInputError("decimal_range") from exc


def _observe(request, *, v2=False):
    if not isinstance(request, ExposureRequestV2 if v2 else ExposureRequest):
        _reject("identity_mismatch")
    if request.evidence_kind not in ("OBSERVED", "SYNTHETIC_SCENARIO"):
        _reject("identity_mismatch")
    _scope(request.scope)
    _integer(request.now_ms)
    try:
        lots._validate_contract(request.contract)
    except (ValueError, TypeError):
        _reject("invalid_contract")
    contract, reasons = request.contract, set()
    lv, pv, mv, pend = request.lots_view, request.physical_view, request.mark_view, request.pending_view
    lf = _source(lv, LotInventoryV2 if v2 else LotInventory, request, reasons, "lot")
    pf = _source(pv, PhysicalPosition, request, reasons, "physical")
    entries = _inventory(lv, contract, v2=v2)
    _bool(pv.verified)
    if pv.quantity is None:
        if pv.verified:
            _reject("identity_mismatch")
        reasons.add("physical_unknown")
    else:
        _decimal(pv.quantity)
        _aligned(pv.quantity, contract)
    if not pv.verified:
        reasons.add("physical_unverified")
    if not lv.complete:
        reasons.add("lot_inventory_incomplete")
    cuts_match = lv.cut_id == pv.cut_id
    if not cuts_match:
        reasons.add("position_cut_mismatch")
    long = _result(sum((v.lot.remaining_qty for v in entries.values() if v.lot.side == "long"), ZERO))
    short = _result(sum((v.lot.remaining_qty for v in entries.values() if v.lot.side == "short"), ZERO))
    gross, net = _result(long + short), _result(long - short)
    comparable = lv.complete and lf and pf and pv.verified and pv.quantity is not None and cuts_match
    delta = _result(net - pv.quantity) if comparable else None
    mf = False
    if mv is None:
        reasons.add("mark_missing")
    else:
        mf = _source(mv, MarkObservation, request, reasons, "mark")
        _decimal(mv.mark, positive=True)
    def notional(quantity):
        return _result(quantity * contract.base_per_contract * mv.mark) if mf and quantity is not None else None
    unresolved = sum(v.opening_unresolved or v.closing_unresolved for v in entries.values())
    orders, duplicates, pending_fresh = (), 0, False
    if pend is None:
        reasons.add("pending_missing")
        if unresolved:
            reasons.add("pending_lot_link_incomplete")
    else:
        pending_fresh = _source(pend, PendingInventory, request, reasons, "pending")
        orders, duplicates = _pending(pend, entries, contract, reasons, request.evidence_kind)
        if not pend.complete:
            reasons.add("pending_incomplete")
        if pend.cut_id != lv.cut_id or pend.cut_id != pv.cut_id:
            reasons.add("pending_cut_mismatch")
        if any(o.remaining_quantity is None for o in orders):
            reasons.add("pending_quantity_unknown")
        if any(o.effect == "UNCLASSIFIED" for o in orders):
            reasons.add("pending_effect_unknown")
    usable = (comparable and pend is not None and pend.complete and pending_fresh
              and not reasons.intersection(("pending_cut_mismatch", "pending_quantity_unknown", "pending_lot_link_incomplete")))
    buckets = {name: None for name in ("held_buy_qty", "held_sell_qty", "exchange_buy_qty", "exchange_sell_qty")}
    buckets.update(synthetic_buy_qty=ZERO, synthetic_sell_qty=ZERO)
    if request.evidence_kind == "SYNTHETIC_SCENARIO":
        buckets.update(synthetic_buy_qty=None, synthetic_sell_qty=None)
    buys = sells = physical_upper = virtual_upper = None
    if usable:
        for origin, bucket in (("HELD", "held"), ("EXCHANGE", "exchange"),
                               ("SYNTHETIC_LEDGER", "synthetic")):
            for side in ("BUY", "SELL"):
                buckets[f"{bucket}_{side.lower()}_qty"] = _result(sum(
                    (o.remaining_quantity for o in orders if o.origin == origin and o.side == side), ZERO))
        buys = _result(buckets["held_buy_qty"] + buckets["exchange_buy_qty"] + buckets["synthetic_buy_qty"])
        sells = _result(buckets["held_sell_qty"] + buckets["exchange_sell_qty"] + buckets["synthetic_sell_qty"])
        physical_upper = _result(max(abs(pv.quantity - sells), abs(pv.quantity + buys)))
        if "pending_effect_unknown" not in reasons:
            virtual_upper = _result(gross + sum((o.remaining_quantity for o in orders if o.effect == "OPEN"), ZERO))
    return ExposureReport(
        scope=request.scope, contract=contract, now_ms=request.now_ms, evidence_kind=request.evidence_kind,
        lot_cut_id=lv.cut_id, physical_cut_id=pv.cut_id, pending_cut_id=None if pend is None else pend.cut_id,
        quote_id=None if mv is None else mv.quote_id,
        observed_long_qty=long, observed_short_qty=short, observed_gross_qty=gross, observed_net_qty=net,
        physical_qty=pv.quantity, delta_qty=delta,
        comparison_status="UNAVAILABLE" if delta is None else ("MATCH" if delta == 0 else "MISMATCH"),
        observed_gross_notional=notional(gross), observed_signed_net_notional=notional(net),
        physical_notional=notional(None if pv.quantity is None else abs(pv.quantity)),
        pending_buy_qty=buys, pending_sell_qty=sells, **buckets,
        physical_scenario_upper_qty=physical_upper, virtual_gross_scenario_upper_qty=virtual_upper,
        lot_complete=lv.complete, lot_fresh=lf, physical_fresh=pf, physical_verified=pv.verified,
        mark_fresh=mf, pending_complete=False if pend is None else pend.complete, pending_fresh=pending_fresh,
        has_unknown=any(o.state == "UNKNOWN" for o in orders), unresolved_lot_count=unresolved,
        pending_unique_count=len(orders), pending_duplicate_count=duplicates, reasons=tuple(sorted(reasons)))
