"""Strict IPC v2 serialization for the isolated S1 Virtual Lot data contract."""

from decimal import Decimal
import json

from catos import ipc
from catos import lots


LOT_PROTOCOL_VERSION = 2
MAX_INTENTS_PER_EVENT = 1


def _protocol(exc: lots.LotError) -> ipc.ProtocolError:
    return ipc.ProtocolError(exc.code)


def _decimal_text(value: Decimal, *, derived: bool) -> str:
    """Fixed-point numeric canonicalization for intent content."""
    try:
        checked = lots._decimal(value, "invalid_decimal", derived=derived)
    except lots.LotError as exc:
        raise _protocol(exc) from exc
    if checked.is_zero():
        return "0"
    text = format(checked, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _snapshot_decimal_text(value: Decimal) -> str:
    """Preserve the checked coefficient/exponent without fixed-point expansion."""
    try:
        checked = lots._decimal(value, "invalid_decimal", derived=True)
    except lots.LotError as exc:
        raise _protocol(exc) from exc
    return str(checked)


def _parse_decimal(value, name: str, *, derived: bool, positive: bool = False) -> Decimal:
    result = ipc.decimal_text(value, name, derived=derived, positive=positive and not derived)
    if positive and result <= 0:
        raise ipc.ProtocolError(f"invalid {name}")
    return result


def _scope_to_wire(scope: lots.LotScope) -> dict:
    try:
        checked = lots.LotScope(scope.account_ref, scope.environment)
    except (AttributeError, lots.LotError) as exc:
        if isinstance(exc, lots.LotError):
            raise _protocol(exc) from exc
        raise ipc.ProtocolError("invalid lot scope") from exc
    return {"account_ref": checked.account_ref, "environment": checked.environment}


def _scope_from_wire(value: dict) -> lots.LotScope:
    value = ipc.exact(value, ("account_ref", "environment"))
    try:
        return lots.LotScope(value["account_ref"], value["environment"])
    except lots.LotError as exc:
        raise _protocol(exc) from exc


def _protection_to_wire(protection: lots.LotProtection) -> dict:
    try:
        checked = lots.LotProtection(protection.trigger_price_type,
                                     protection.take_profit, protection.stop_loss)
    except (AttributeError, lots.LotError) as exc:
        if isinstance(exc, lots.LotError):
            raise _protocol(exc) from exc
        raise ipc.ProtocolError("invalid lot protection") from exc
    return {
        "trigger_price_type": checked.trigger_price_type,
        "take_profit": None if checked.take_profit is None else _decimal_text(checked.take_profit, derived=False),
        "stop_loss": None if checked.stop_loss is None else _decimal_text(checked.stop_loss, derived=False),
    }


def _protection_from_wire(value: dict) -> lots.LotProtection:
    value = ipc.exact(value, ("trigger_price_type", "take_profit", "stop_loss"))
    if value["trigger_price_type"] != "mark":
        raise ipc.ProtocolError("invalid_protection")
    take_profit = (None if value["take_profit"] is None else
                   _parse_decimal(value["take_profit"], "take_profit", derived=False, positive=True))
    stop_loss = (None if value["stop_loss"] is None else
                 _parse_decimal(value["stop_loss"], "stop_loss", derived=False, positive=True))
    try:
        return lots.LotProtection("mark", take_profit, stop_loss)
    except lots.LotError as exc:
        raise _protocol(exc) from exc


def intent_to_wire(intent: lots.LotIntent) -> dict:
    try:
        if isinstance(intent, lots.OpenLot):
            checked = lots.OpenLot(intent.side, intent.quantity, intent.protection)
            return {"op": "OPEN_LOT", "side": checked.side,
                    "quantity": _decimal_text(checked.quantity, derived=False),
                    "protection": _protection_to_wire(checked.protection)}
        if isinstance(intent, lots.CloseLot):
            checked = lots.CloseLot(intent.lot_id, intent.quantity, intent.expected_revision)
            return {"op": "CLOSE_LOT", "lot_id": checked.lot_id,
                    "quantity": None if checked.quantity is None else _decimal_text(checked.quantity, derived=False),
                    "expected_revision": checked.expected_revision}
        if isinstance(intent, lots.UpdateLotProtection):
            checked = lots.UpdateLotProtection(intent.lot_id, intent.protection,
                                               intent.expected_revision)
            return {"op": "UPDATE_LOT_PROTECTION", "lot_id": checked.lot_id,
                    "protection": _protection_to_wire(checked.protection),
                    "expected_revision": checked.expected_revision}
    except lots.LotError as exc:
        raise _protocol(exc) from exc
    raise ipc.ProtocolError("unsupported lot intent")


def intent_from_wire(value: dict) -> lots.LotIntent:
    if type(value) is not dict or type(value.get("op")) is not str:
        raise ipc.ProtocolError("lot intent must be an object with op")
    op = value["op"]
    try:
        if op == "OPEN_LOT":
            value = ipc.exact(value, ("op", "side", "quantity", "protection"))
            if type(value["side"]) is not str:
                raise ipc.ProtocolError("invalid side")
            return lots.OpenLot(value["side"],
                                _parse_decimal(value["quantity"], "quantity", derived=False, positive=True),
                                _protection_from_wire(value["protection"]))
        if op == "CLOSE_LOT":
            value = ipc.exact(value, ("op", "lot_id", "quantity", "expected_revision"))
            quantity = (None if value["quantity"] is None else
                        _parse_decimal(value["quantity"], "quantity", derived=False, positive=True))
            revision = ipc.integer(value["expected_revision"], "expected_revision", 1)
            return lots.CloseLot(value["lot_id"], quantity, revision)
        if op == "UPDATE_LOT_PROTECTION":
            value = ipc.exact(value, ("op", "lot_id", "protection", "expected_revision"))
            revision = ipc.integer(value["expected_revision"], "expected_revision", 1)
            return lots.UpdateLotProtection(value["lot_id"],
                                            _protection_from_wire(value["protection"]), revision)
    except lots.LotError as exc:
        raise _protocol(exc) from exc
    raise ipc.ProtocolError("unknown lot intent op")


def lot_to_wire(lot: lots.Lot) -> dict:
    if not isinstance(lot, lots.Lot):
        raise ipc.ProtocolError("lot must be Lot")
    try:
        checked = lots.Lot(lot.scope, lot.bot_id, lot.inst_id, lot.lot_id,
                           lot.open_intent_key, lot.side, lot.opened_qty,
                           lot.remaining_qty, lot.average_entry, lot.realized_pnl,
                           lot.fees_paid, lot.funding_paid, lot.protection, lot.revision)
    except lots.LotError as exc:
        raise _protocol(exc) from exc
    return {
        "scope": _scope_to_wire(checked.scope),
        "bot_id": checked.bot_id,
        "inst_id": checked.inst_id,
        "lot_id": checked.lot_id,
        "open_intent_key": checked.open_intent_key,
        "side": checked.side,
        "opened_qty": _snapshot_decimal_text(checked.opened_qty),
        "remaining_qty": _snapshot_decimal_text(checked.remaining_qty),
        "average_entry": _snapshot_decimal_text(checked.average_entry),
        "realized_pnl": _snapshot_decimal_text(checked.realized_pnl),
        "fees_paid": _snapshot_decimal_text(checked.fees_paid),
        "funding_paid": None if checked.funding_paid is None else _snapshot_decimal_text(checked.funding_paid),
        "protection": _protection_to_wire(checked.protection),
        "revision": checked.revision,
    }


def lot_from_wire(value: dict) -> lots.Lot:
    value = ipc.exact(value, ("scope", "bot_id", "inst_id", "lot_id", "open_intent_key",
                              "side", "opened_qty", "remaining_qty", "average_entry",
                              "realized_pnl", "fees_paid", "funding_paid", "protection", "revision"))
    try:
        funding = (None if value["funding_paid"] is None else
                   _parse_decimal(value["funding_paid"], "funding_paid", derived=True))
        return lots.Lot(
            _scope_from_wire(value["scope"]), value["bot_id"], value["inst_id"],
            value["lot_id"], value["open_intent_key"], value["side"],
            _parse_decimal(value["opened_qty"], "opened_qty", derived=True, positive=True),
            _parse_decimal(value["remaining_qty"], "remaining_qty", derived=True),
            _parse_decimal(value["average_entry"], "average_entry", derived=True, positive=True),
            _parse_decimal(value["realized_pnl"], "realized_pnl", derived=True),
            _parse_decimal(value["fees_paid"], "fees_paid", derived=True), funding,
            _protection_from_wire(value["protection"]),
            ipc.integer(value["revision"], "revision", 1),
        )
    except lots.LotError as exc:
        raise _protocol(exc) from exc


def encode_lot_message(intents: tuple[lots.LotIntent, ...], *, generation: str, seq: int) -> bytes:
    if type(intents) is not tuple or len(intents) > MAX_INTENTS_PER_EVENT:
        raise ipc.ProtocolError("intents must be a tuple with at most one item")
    ipc.token(generation, "generation")
    ipc.integer(seq, "seq", 1)
    message = {"version": LOT_PROTOCOL_VERSION, "kind": "lot_intents",
               "generation": generation, "seq": seq,
               "payload": {"intents": [intent_to_wire(intent) for intent in intents]}}
    return ipc.encode_frame(message)


def parse_lot_message(message: dict, *, generation: str, seq: int,
                      warmup: bool) -> tuple[lots.LotIntent, ...]:
    if type(warmup) is not bool:
        raise ipc.ProtocolError("warmup must be bool")
    ipc.token(generation, "generation")
    ipc.integer(seq, "seq", 1)
    message = ipc.exact(message, ("version", "kind", "generation", "seq", "payload"))
    ipc.integer(message["version"], "version", 1)
    ipc.integer(message["seq"], "seq", 1)
    ipc.token(message["generation"], "generation")
    if (message["version"] != LOT_PROTOCOL_VERSION or message["kind"] != "lot_intents"
            or message["generation"] != generation or message["seq"] != seq):
        raise ipc.ProtocolError("wrong version, kind, generation or event sequence")
    payload = ipc.exact(message["payload"], ("intents",))
    raw = payload["intents"]
    if type(raw) is not list or len(raw) > MAX_INTENTS_PER_EVENT:
        raise ipc.ProtocolError("intents must be an array with at most one item")
    if warmup and raw:
        raise ipc.ProtocolError("warmup_intent_forbidden")
    return tuple(intent_from_wire(item) for item in raw)


def canonical_intent(intent: lots.LotIntent) -> bytes:
    value = intent_to_wire(intent)
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
