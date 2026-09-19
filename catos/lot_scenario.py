"""Pure S5-to-S4 synthetic scenario attestation; never exchange evidence."""

from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext
from typing import Literal

from catos import ipc, lots, lot_exposure as exposure, lot_snapshot as snapshot
from catos.research import ContractSpec


class ScenarioInputError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class SyntheticScenarioEvidence:
    source: Literal["synthetic_scenario"]
    scope: lots.LotScope
    contract: ContractSpec
    scenario_cut_id: str
    source_capture_id: str
    physical_observed_at_ms: int
    physical_valid_until_ms: int
    physical_quantity: Decimal | None
    physical_complete: bool
    mark_quote_id: str | None
    mark_observed_at_ms: int | None
    mark_valid_until_ms: int | None
    mark: Decimal | None


@dataclass(frozen=True, slots=True)
class SyntheticScenarioObservation:
    evidence_kind: Literal["SYNTHETIC_SCENARIO"]
    scenario_cut_id: str
    source_capture_id: str
    report: exposure.ExposureReport


def _reject(code):
    raise ScenarioInputError(code)


def _time(observed, valid, code):
    if (type(observed) is not int or type(valid) is not int
            or not 0 <= observed < valid <= ipc.MAX_INTEGER):
        _reject(code)


def _sequence(values, limit, key):
    if type(values) is not tuple:
        _reject("invalid_capture")
    if len(values) > limit:
        _reject("input_limit")
    keys = tuple(key(value) for value in values)
    if keys != tuple(sorted(set(keys))):
        _reject("invalid_capture")


def _lot_view(capture, cut):
    bots = tuple(w.bot_id for w in capture.bot_watermarks)
    return exposure.LotInventory(
        capture.scope, capture.contract.inst_id, cut, capture.observed_at_ms,
        capture.valid_until_ms, True, bots, bots, capture.lots)


def _validate_capture(capture):
    # Hashes prove content identity, not provenance or semantic consistency.
    try:
        if not isinstance(capture, snapshot.LocalLotCapture) or capture.source != "synthetic_ledger":
            _reject("invalid_capture")
        exposure._scope(capture.scope)
        lots._validate_contract(capture.contract)
        lots._hex_id(capture.capture_id)
        _time(capture.observed_at_ms, capture.valid_until_ms, "invalid_capture")
        _sequence(capture.bot_watermarks, snapshot.MAX_BOTS, lambda w: w.bot_id)
        _sequence(capture.lots, snapshot.MAX_LOTS, lambda s: s.lot.lot_id)
        _sequence(capture.pending, snapshot.MAX_PENDING, lambda p: p.order_key)
        _sequence(capture.unmanaged_unresolved_lot_ids, snapshot.MAX_LOTS, lambda value: value)
        if not capture.bot_watermarks:
            _reject("invalid_capture")
        watermarks = {}
        for watermark in capture.bot_watermarks:
            if not isinstance(watermark, snapshot.BotWatermark):
                _reject("invalid_capture")
            ipc.token(watermark.bot_id, "bot_id")
            exposure._integer(watermark.last_commit_seq)
            watermarks[watermark.bot_id] = watermark.last_commit_seq
        entries = exposure._inventory(_lot_view(capture, "validation"), capture.contract)
        for item in entries.values():
            if item.commit_seq > watermarks[item.lot.bot_id]:
                _reject("invalid_capture")
        linked, intent_keys = {}, set()
        for pending in capture.pending:
            if not isinstance(pending, snapshot.SyntheticPendingObligation):
                _reject("invalid_capture")
            for identity in (pending.order_key, pending.intent_key, pending.lot_id):
                lots._hex_id(identity)
            if pending.intent_key in intent_keys:
                _reject("invalid_capture")
            intent_keys.add(pending.intent_key)
            if (pending.bot_id not in watermarks or pending.lot_id in linked
                    or pending.effect not in ("OPEN", "CLOSE") or pending.side not in ("BUY", "SELL")):
                _reject("invalid_capture")
            exposure._integer(pending.last_fill_seq)
            for name in ("resolved_quantity", "filled_quantity", "remaining_quantity"):
                value = getattr(pending, name)
                lots._decimal(value, "invalid_capture", derived=True,
                              positive=name == "resolved_quantity", nonnegative=True)
                exposure._aligned(value, capture.contract)
            # Verify supplied quantities without replacing the S5 remainder.
            if (pending.filled_quantity + pending.remaining_quantity != pending.resolved_quantity
                    or (pending.last_fill_seq == 0) != (pending.filled_quantity == 0)):
                _reject("invalid_capture")
            item = entries.get(pending.lot_id)
            if pending.effect == "OPEN":
                lots._decimal(pending.resolved_quantity, "invalid_capture", derived=False, positive=True)
                if (lots.make_lot_id(pending.intent_key) != pending.lot_id
                        or pending.resolved_quantity < capture.contract.min_size):
                    _reject("invalid_capture")
            if item is None:
                if pending.effect != "OPEN" or pending.filled_quantity != 0:
                    _reject("invalid_capture")
            else:
                if item.lot.bot_id != pending.bot_id:
                    _reject("invalid_capture")
                expected_flags = (pending.effect == "OPEN", pending.effect == "CLOSE")
                if (item.opening_unresolved, item.closing_unresolved) != expected_flags:
                    _reject("invalid_capture")
                buy = (item.lot.side == "long") == (pending.effect == "OPEN")
                if pending.side != ("BUY" if buy else "SELL"):
                    _reject("invalid_capture")
                if pending.effect == "OPEN":
                    if (item.lot.open_intent_key != pending.intent_key
                            or item.lot.opened_qty != pending.filled_quantity
                            or item.lot.remaining_qty != pending.filled_quantity):
                        _reject("invalid_capture")
                elif (pending.remaining_quantity > item.lot.remaining_qty
                      or pending.filled_quantity + item.lot.remaining_qty > item.lot.opened_qty
                      or pending.intent_key == item.lot.open_intent_key):
                    _reject("invalid_capture")
            linked[pending.lot_id] = pending
        unmanaged = set(capture.unmanaged_unresolved_lot_ids)
        for lot_id in unmanaged:
            lots._hex_id(lot_id)
            item = entries.get(lot_id)
            if (item is None or not (item.opening_unresolved or item.closing_unresolved)
                    or lot_id in linked):
                _reject("invalid_capture")
        for lot_id, item in entries.items():
            if (item.opening_unresolved or item.closing_unresolved) and lot_id not in linked and lot_id not in unmanaged:
                _reject("invalid_capture")
        if snapshot._capture_id(capture) != capture.capture_id:
            _reject("invalid_capture")
    except ScenarioInputError:
        raise
    except (ValueError, TypeError, AttributeError, KeyError, DecimalException) as exc:
        raise ScenarioInputError("invalid_capture") from exc


def _validate_scenario(capture, scenario, now_ms):
    if (not isinstance(scenario, SyntheticScenarioEvidence) or scenario.source != "synthetic_scenario"
            or scenario.scope != capture.scope or scenario.contract != capture.contract
            or scenario.source_capture_id != capture.capture_id):
        _reject("scenario_identity_mismatch")
    try:
        exposure._scope(scenario.scope)
        lots._validate_contract(scenario.contract)
        lots._hex_id(scenario.source_capture_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ScenarioInputError("scenario_identity_mismatch") from exc
    try:
        ipc.token(scenario.scenario_cut_id, "scenario_cut_id")
    except (ValueError, TypeError) as exc:
        raise ScenarioInputError("invalid_scenario_cut") from exc
    if scenario.scenario_cut_id == capture.capture_id:
        _reject("invalid_scenario_cut")
    if type(now_ms) is not int or not 0 <= now_ms <= ipc.MAX_INTEGER:
        _reject("invalid_scenario_time")
    _time(scenario.physical_observed_at_ms, scenario.physical_valid_until_ms, "invalid_scenario_time")
    try:
        if type(scenario.physical_complete) is not bool:
            _reject("invalid_scenario_physical")
        if scenario.physical_quantity is None:
            if scenario.physical_complete:
                _reject("invalid_scenario_physical")
        else:
            lots._decimal(scenario.physical_quantity, "invalid_scenario_physical", derived=True)
            exposure._aligned(scenario.physical_quantity, capture.contract)
    except (ValueError, DecimalException) as exc:
        raise ScenarioInputError("invalid_scenario_physical") from exc
    metadata = (scenario.mark_quote_id, scenario.mark_observed_at_ms, scenario.mark_valid_until_ms)
    if scenario.mark is None:
        if any(value is not None for value in metadata):
            _reject("invalid_scenario_mark")
    else:
        if any(value is None for value in metadata):
            _reject("invalid_scenario_mark")
        try:
            ipc.token(scenario.mark_quote_id, "mark_quote_id")
            lots._decimal(scenario.mark, "invalid_scenario_mark", derived=True, positive=True)
        except (ValueError, TypeError) as exc:
            raise ScenarioInputError("invalid_scenario_mark") from exc
        _time(scenario.mark_observed_at_ms, scenario.mark_valid_until_ms, "invalid_scenario_time")


def observe_synthetic_scenario(*, capture: snapshot.LocalLotCapture,
                               scenario: SyntheticScenarioEvidence,
                               now_ms: int) -> SyntheticScenarioObservation:
    """Observe only the explicitly attested simulation, preserving source times."""
    with localcontext(exposure._CONTEXT):
        _validate_capture(capture)
        _validate_scenario(capture, scenario, now_ms)
        cut = scenario.scenario_cut_id
        pending = exposure.PendingInventory(
            capture.scope, capture.contract.inst_id, cut, capture.observed_at_ms, capture.valid_until_ms,
            capture.unmanaged_unresolved_lot_ids == (),
            tuple(exposure.PendingObligation(p.order_key, "SYNTHETIC_LEDGER", "UNTERMINATED", p.side,
                                             p.remaining_quantity, p.effect, p.lot_id) for p in capture.pending))
        physical = exposure.PhysicalPosition(
            scenario.scope, scenario.contract.inst_id, cut, scenario.physical_observed_at_ms,
            scenario.physical_valid_until_ms, scenario.physical_quantity, scenario.physical_complete)
        mark = None if scenario.mark is None else exposure.MarkObservation(
            scenario.scope, scenario.contract.inst_id, scenario.mark_quote_id, scenario.mark_observed_at_ms,
            scenario.mark_valid_until_ms, scenario.mark)
        report = exposure.observe_exposure(exposure.ExposureRequest(
            capture.scope, capture.contract, now_ms, _lot_view(capture, cut), physical, mark, pending,
            evidence_kind="SYNTHETIC_SCENARIO"))
        return SyntheticScenarioObservation("SYNTHETIC_SCENARIO", cut, capture.capture_id, report)
