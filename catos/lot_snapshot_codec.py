"""Strict local snapshot v2 codec; deliberately separate from Worker IPC."""

from dataclasses import replace

from catos import ipc, ipc_lots, lots

FINANCIAL = ("opened_qty", "remaining_qty", "average_entry", "realized_pnl", "funding_paid")


def lot_to_wire(lot):
    if type(lot) is not lots.LotV2:
        raise ipc.ProtocolError("unsupported_fee_version")
    if (type(lot.fee_quality) is not lots.FeeQuality or type(lot.protection) is not lots.LotProtection
            or type(lot.scope) is not lots.LotScope):
        raise ipc.ProtocolError("invalid_snapshot")
    lot = replace(lot, fee_quality=replace(lot.fee_quality), protection=replace(lot.protection),
                  scope=replace(lot.scope))
    quality = lot.fee_quality
    return dict(snapshot_version=2, scope=ipc_lots._scope_to_wire(lot.scope),
                bot_id=lot.bot_id, inst_id=lot.inst_id, lot_id=lot.lot_id,
                open_intent_key=lot.open_intent_key, side=lot.side, revision=lot.revision,
                protection=ipc_lots._protection_to_wire(lot.protection),
                fee_quality=dict(coverage=quality.coverage,
                    known_fee_subtotal=None if quality.known_fee_subtotal is None else ipc_lots._snapshot_decimal_text(quality.known_fee_subtotal),
                    fee_unknown_fill_count=quality.fee_unknown_fill_count),
                **{n: None if getattr(lot, n) is None else ipc_lots._snapshot_decimal_text(getattr(lot, n)) for n in FINANCIAL})


def lot_from_wire(value):
    ipc.exact(value, ("snapshot_version", "scope", "bot_id", "inst_id", "lot_id",
                     "open_intent_key", "side", "revision", "protection", "fee_quality", *FINANCIAL))
    if type(value["snapshot_version"]) is not int or value["snapshot_version"] != 2:
        raise ipc.ProtocolError("unsupported_fee_version")
    quality = ipc.exact(value["fee_quality"], ("coverage", "known_fee_subtotal", "fee_unknown_fill_count"))
    try:
        quality = lots.FeeQuality(quality["coverage"],
            None if quality["known_fee_subtotal"] is None else ipc_lots._parse_decimal(quality["known_fee_subtotal"], "known_fee_subtotal", derived=True),
            quality["fee_unknown_fill_count"])
        financial = {n: None if n == "funding_paid" and value[n] is None else
                     ipc_lots._parse_decimal(value[n], n, derived=True,
                                             positive=n in ("opened_qty", "average_entry")) for n in FINANCIAL}
        return lots.LotV2(ipc_lots._scope_from_wire(value["scope"]), value["bot_id"], value["inst_id"],
            value["lot_id"], value["open_intent_key"], value["side"], fee_quality=quality,
            protection=ipc_lots._protection_from_wire(value["protection"]),
            revision=ipc.integer(value["revision"], "revision", 1), **financial)
    except lots.LotError as exc:
        raise ipc.ProtocolError(exc.code) from exc
