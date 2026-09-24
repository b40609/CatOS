"""Materialize a local synthetic capture inside Journal's pinned read snapshot."""

from dataclasses import dataclass, fields, replace
from decimal import Decimal
import hashlib
from typing import Literal

from catos import ipc, ipc_lots, lots
from catos.lot_accounting import exact_quantity
from catos.lot_journal import LotStorageError, StoredLot, StoredLotV2, _json, _numeric_identity
from catos.research import ContractSpec


MAX_BOTS = 64
MAX_LOTS = 4096
MAX_PENDING = 4096
_FORMAT = "catos-local-lot-capture-v1"


@dataclass(frozen=True, slots=True)
class BotWatermark:
    bot_id: str
    last_commit_seq: int


@dataclass(frozen=True, slots=True)
class SyntheticPendingObligation:
    order_key: str
    intent_key: str
    bot_id: str
    lot_id: str
    effect: Literal["OPEN", "CLOSE"]
    side: Literal["BUY", "SELL"]
    resolved_quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    last_fill_seq: int


@dataclass(frozen=True, slots=True)
class LocalLotCapture:
    source: Literal["synthetic_ledger"]
    scope: lots.LotScope
    contract: ContractSpec
    capture_id: str
    observed_at_ms: int
    valid_until_ms: int
    bot_watermarks: tuple[BotWatermark, ...]
    lots: tuple[StoredLot, ...]
    pending: tuple[SyntheticPendingObligation, ...]
    unmanaged_unresolved_lot_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LocalLotCaptureV2:
    source: Literal["synthetic_ledger"]
    scope: lots.LotScope
    contract: ContractSpec
    capture_id: str
    observed_at_ms: int
    valid_until_ms: int
    bot_watermarks: tuple[BotWatermark, ...]
    lots: tuple[StoredLotV2, ...]
    pending: tuple[SyntheticPendingObligation, ...]
    unmanaged_unresolved_lot_ids: tuple[str, ...]
    capture_version: int = 2
    schema_version: int = 8


@dataclass(frozen=True, slots=True)
class LocalLotCaptureV3(LocalLotCaptureV2):
    capture_version: int = 3
    schema_version: int = 9


def validate_request(journal, scope, inst_id, observed_at_ms, valid_until_ms):
    try:
        journal.lots._scope(scope)
    except ValueError as exc:
        raise LotStorageError("scope_mismatch") from exc
    try:
        ipc.token(inst_id, "inst_id")
        if not inst_id.endswith("-USDT-SWAP"):
            raise ValueError("unsupported instrument")
    except ValueError as exc:
        raise LotStorageError("invalid_contract") from exc
    if (type(observed_at_ms) is not int or type(valid_until_ms) is not int
            or not 0 <= observed_at_ms < valid_until_ms <= ipc.MAX_INTEGER):
        raise LotStorageError("invalid_capture_time")


def _fragments(capture):
    from catos import lot_snapshot_codec
    v3 = type(capture) is LocalLotCaptureV3
    v2 = type(capture) in (LocalLotCaptureV2, LocalLotCaptureV3)
    contract = {f.name: (capture.contract.inst_id if f.name == "inst_id" else
                         _numeric_identity(getattr(capture.contract, f.name)))
                for f in fields(ContractSpec)}
    header = dict(kind="header", format="catos-local-lot-capture-v3" if v3 else ("catos-local-lot-capture-v2" if v2 else _FORMAT),
                  schema_version=9 if v3 else (8 if v2 else 7), source=capture.source,
                  scope=ipc_lots._scope_to_wire(capture.scope), contract=contract)
    if v2:
        header["capture_version"] = 3 if v3 else 2
    yield header
    for watermark in capture.bot_watermarks:
        yield dict(kind="bot_watermark", bot_id=watermark.bot_id,
                   last_commit_seq=watermark.last_commit_seq)
    for stored in capture.lots:
        wire = (lot_snapshot_codec if v2 else ipc_lots).lot_to_wire(stored.lot)
        for name in (lot_snapshot_codec.FINANCIAL if v2 else ("opened_qty", "remaining_qty", "average_entry", "realized_pnl", "fees_paid", "funding_paid")):
            if wire[name] is not None:
                wire[name] = _numeric_identity(getattr(stored.lot, name))
        if v2 and stored.lot.fee_quality.known_fee_subtotal is not None:
            wire["fee_quality"]["known_fee_subtotal"] = _numeric_identity(stored.lot.fee_quality.known_fee_subtotal)
        for name in ("take_profit", "stop_loss"):
            if wire["protection"][name] is not None:
                wire["protection"][name] = _numeric_identity(getattr(stored.lot.protection, name))
        yield dict(kind="lot", lot=wire, opening_unresolved=stored.opening_unresolved,
                   closing_unresolved=stored.closing_unresolved, commit_seq=stored.commit_seq)
    for pending in capture.pending:
        wire = {f.name: getattr(pending, f.name) for f in fields(SyntheticPendingObligation)}
        for name in ("resolved_quantity", "filled_quantity", "remaining_quantity"):
            wire[name] = _numeric_identity(wire[name])
        yield dict(kind="pending", pending=wire)
    for lot_id in capture.unmanaged_unresolved_lot_ids:
        yield dict(kind="unmanaged_unresolved", lot_id=lot_id)


def _capture_id(capture):
    if type(capture) is LocalLotCaptureV3:
        if (type(capture.capture_version) is not int or capture.capture_version != 3
                or type(capture.schema_version) is not int or capture.schema_version != 9):
            raise LotStorageError("unsupported_fee_version")
        domain = "catos-local-lot-capture-v3"
    elif type(capture) is LocalLotCaptureV2:
        if (type(capture.capture_version) is not int or capture.capture_version != 2
                or type(capture.schema_version) is not int or capture.schema_version != 8):
            raise LotStorageError("unsupported_fee_version")
        domain = "catos-local-lot-capture-v2"
    elif type(capture) is LocalLotCapture:
        domain = _FORMAT
    else:
        raise LotStorageError("unsupported_fee_version")
    digest = hashlib.sha256(domain.encode("ascii"))
    for fragment in _fragments(capture):
        encoded = _json(fragment).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def _materialize(journal, scope, inst_id, observed_at_ms, valid_until_ms, *, v2=False, v3=False):
    """Internal only: caller pins and owns the read transaction."""
    db = journal.connection
    if not db.in_transaction:
        raise LotStorageError("storage_unavailable")
    journal.lots._recover_in_transaction()
    _, _, orders, states = journal.lot_fills._recover_in_transaction()
    bindings = tuple(journal.lots._decode_binding(row) for row in db.execute(
        "SELECT * FROM lot_bindings WHERE inst_id=? ORDER BY bot_id LIMIT ?", (inst_id, MAX_BOTS + 1)))
    if not bindings:
        raise LotStorageError("binding_not_found")
    if len(bindings) > MAX_BOTS:
        raise LotStorageError("capture_limit")
    contract = bindings[0].contract
    if any(binding.contract != contract for binding in bindings):
        raise LotStorageError("contract_conflict")
    by_bot = {binding.bot_id: binding for binding in bindings}
    stored_lots = []
    for head in db.execute("""SELECT h.* FROM lot_heads h JOIN lot_bindings b ON b.bot_id=h.bot_id
        WHERE b.inst_id=? ORDER BY h.lot_id LIMIT ?""", (inst_id, MAX_LOTS + 1)):
        if len(stored_lots) == MAX_LOTS:
            raise LotStorageError("capture_limit")
        row = journal.lots._row(head["bot_id"], head["lot_id"], head["current_revision"])
        stored_lots.append(journal.lots._decode_revision(row, by_bot[head["bot_id"]]))
    managed, pending = set(), []
    for key in sorted(orders):
        order = orders[key]
        validated = order["validated"]
        if validated.inst_id != inst_id:
            continue
        if validated.scope != scope or validated.bot_id not in by_bot:
            raise LotStorageError("integrity_error")
        managed.add(validated.lot_id)
        if order["done"]:
            continue
        if len(pending) == MAX_PENDING:
            raise LotStorageError("capture_limit")
        opening = isinstance(validated.intent, lots.OpenLot)
        if opening:
            side = "BUY" if validated.intent.side == "long" else "SELL"
        else:
            side = "SELL" if states[validated.lot_id].side == "long" else "BUY"
        pending.append(SyntheticPendingObligation(
            key, validated.intent_key, validated.bot_id, validated.lot_id,
            "OPEN" if opening else "CLOSE", side, validated.resolved_quantity, order["total"],
            exact_quantity(validated.resolved_quantity, order["total"].copy_negate()), order["count"]))
    capture = (LocalLotCaptureV3 if v3 else (LocalLotCaptureV2 if v2 else LocalLotCapture))(
        "synthetic_ledger", scope, contract, "", observed_at_ms, valid_until_ms,
        tuple(BotWatermark(b.bot_id, b.last_commit_seq) for b in bindings), tuple(stored_lots), tuple(pending),
        tuple(s.lot.lot_id for s in stored_lots if s.lot.lot_id not in managed
              and (s.opening_unresolved or s.closing_unresolved)))
    return replace(capture, capture_id=_capture_id(capture))
