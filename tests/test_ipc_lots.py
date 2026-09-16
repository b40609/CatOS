"""Synthetic protocol coverage for S1 Lot IPC v2 (P01-P20)."""

from dataclasses import replace
from decimal import Decimal, ROUND_DOWN, localcontext
import io
import json
import struct
import unittest

from catos import ipc, ipc_lots, lots
from catos.research import ContractSpec


D = Decimal


def spec():
    return ContractSpec("BTC-USDT-SWAP", D("0.01"), D("0.5"), D("0.5"), D("1"))


def ctx(seq=1):
    return lots.IntentContext(lots.LotScope("acct", "local-sim"), "bot", spec(), seq, False)


def protect(tp="120", sl="90"):
    return lots.LotProtection("mark", None if tp is None else D(tp), None if sl is None else D(sl))


def open_intent(quantity="1"):
    return lots.OpenLot("long", D(quantity), protect())


def lot():
    context = ctx()
    key = lots.make_intent_key(context)
    return lots.Lot(context.scope, context.bot_id, context.contract.inst_id,
                    lots.make_lot_id(key), key, "long", D("2"), D("1.5"),
                    D("100.25"), D("-2"), D("-0.1"), None, protect(), 4)


def message(intent=None, **changes):
    base = {"version": 2, "kind": "lot_intents", "generation": "gen1", "seq": 1,
            "payload": {"intents": [] if intent is None else [ipc_lots.intent_to_wire(intent)]}}
    base.update(changes)
    return base


class ShortIO(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 2))


class LotIPCTests(unittest.TestCase):
    def test_p01_three_intent_types_round_trip_without_float(self):
        value = lot()
        intents = (open_intent(), lots.CloseLot(value.lot_id, D("0.5"), 4),
                   lots.UpdateLotProtection(value.lot_id, protect("130", "95"), 4))
        for intent in intents:
            with self.subTest(intent=intent):
                self.assertEqual(ipc_lots.intent_from_wire(ipc_lots.intent_to_wire(intent)), intent)
                self.assertNotIn("1.0", json.dumps(ipc_lots.intent_to_wire(intent)))

    def test_p02_lot_snapshot_round_trip_preserves_negative_fee_and_unknown_funding(self):
        value = lot()
        wire = ipc_lots.lot_to_wire(value)
        self.assertEqual(wire["fees_paid"], "-0.1")
        self.assertIsNone(wire["funding_paid"])
        self.assertEqual(ipc_lots.lot_from_wire(wire), value)

    def test_p03_empty_intents_valid_null_object_and_multiple_rejected(self):
        self.assertEqual(ipc_lots.parse_lot_message(message(), generation="gen1", seq=1, warmup=False), ())
        for raw in (None, {}, [ipc_lots.intent_to_wire(open_intent()), ipc_lots.intent_to_wire(open_intent())]):
            bad = message()
            bad["payload"] = {"intents": raw}
            with self.subTest(raw=raw), self.assertRaises(ipc.ProtocolError):
                ipc_lots.parse_lot_message(bad, generation="gen1", seq=1, warmup=False)

    def test_snapshot_exponent_and_large_derived_values_round_trip(self):
        numeric_fields = ("opened_qty", "remaining_qty", "average_entry",
                          "realized_pnl", "fees_paid", "funding_paid")
        cases = ("1e50", "1e99", "1e-148", "9" * 50 + "e50",
                 "9" * 50 + "e-148")
        for text in cases:
            with self.subTest(value=text):
                number = D(text)
                original = replace(lot(), opened_qty=number, remaining_qty=number,
                                   average_entry=number, realized_pnl=number.copy_negate(),
                                   fees_paid=number.copy_negate(), funding_paid=number)
                with localcontext() as active:
                    active.prec = 2
                    active.rounding = ROUND_DOWN
                    active.capitals = 0
                    wire = ipc_lots.lot_to_wire(original)
                    for name in numeric_fields:
                        self.assertIsInstance(wire[name], str)
                        self.assertLessEqual(len(wire[name]), 192)
                    decoded = ipc.read_frame_sync(io.BytesIO(ipc.encode_frame(wire)))
                    restored = ipc_lots.lot_from_wire(decoded)
                self.assertEqual(restored, original)
                for name in numeric_fields:
                    self.assertEqual(getattr(restored, name).as_tuple(),
                                     getattr(original, name).as_tuple())

    def test_snapshot_serialization_still_rejects_out_of_range_values(self):
        for text in ("1e100", "1e-149", "1." + "0" * 50):
            with self.subTest(value=text):
                wire = ipc_lots.lot_to_wire(lot())
                wire["average_entry"] = text
                with self.assertRaises(ipc.ProtocolError):
                    ipc_lots.lot_from_wire(wire)
                invalid = lot()
                object.__setattr__(invalid, "average_entry", D(text))
                with self.assertRaises(ipc.ProtocolError):
                    ipc_lots.lot_to_wire(invalid)

    def test_intent_canonical_keeps_fixed_point_for_exponent_inputs(self):
        value = lots.OpenLot("long", D("1e18"),
                             lots.LotProtection("mark", D("1e3"), D("1e-18")))
        canonical = ipc_lots.canonical_intent(value)
        parsed = json.loads(canonical)
        self.assertEqual(parsed["quantity"], "1000000000000000000")
        self.assertEqual(parsed["protection"]["take_profit"], "1000")
        self.assertEqual(parsed["protection"]["stop_loss"], "0.000000000000000001")
        equivalent = lots.OpenLot("long", D("1000000000000000000"),
                                  protect("1000.0", "0.000000000000000001"))
        self.assertEqual(canonical, ipc_lots.canonical_intent(equivalent))

    def test_p04_every_nested_object_rejects_missing_and_extra_fields(self):
        candidates = [ipc_lots.intent_to_wire(open_intent()),
                      ipc_lots.intent_to_wire(lots.CloseLot(lot().lot_id, None, 4)),
                      ipc_lots.intent_to_wire(lots.UpdateLotProtection(lot().lot_id, protect(), 4))]
        for original in candidates:
            for mutate in (lambda v: v.pop(next(iter(v))), lambda v: v.update(extra=1)):
                value = dict(original)
                mutate(value)
                with self.subTest(value=value), self.assertRaises(ipc.ProtocolError):
                    ipc_lots.intent_from_wire(value)
        nested = ipc_lots.intent_to_wire(open_intent())
        nested["protection"] = dict(nested["protection"], extra="x")
        with self.assertRaises(ipc.ProtocolError):
            ipc_lots.intent_from_wire(nested)
        scope_wire = ipc_lots.lot_to_wire(lot())
        scope_wire["scope"] = dict(scope_wire["scope"], uid="forged")
        with self.assertRaises(ipc.ProtocolError):
            ipc_lots.lot_from_wire(scope_wire)

    def test_p05_worker_identity_and_execution_field_injection_is_rejected(self):
        base = ipc_lots.intent_to_wire(open_intent())
        for key in ("bot_id", "account", "inst_id", "tag", "posSide", "reduceOnly", "target"):
            with self.subTest(key=key), self.assertRaises(ipc.ProtocolError):
                ipc_lots.intent_from_wire(dict(base, **{key: "forged"}))

    def test_p06_version_kind_generation_seq_and_bool_are_strict(self):
        variants = ({"version": 1}, {"version": 3}, {"version": True}, {"kind": "result"},
                    {"generation": "old"}, {"seq": 2}, {"seq": True})
        for changes in variants:
            with self.subTest(changes=changes), self.assertRaises(ipc.ProtocolError):
                ipc_lots.parse_lot_message(message(**changes), generation="gen1", seq=1, warmup=False)

    def test_p07_warmup_accepts_only_empty_and_parameter_is_bool(self):
        self.assertEqual(ipc_lots.parse_lot_message(message(), generation="gen1", seq=1, warmup=True), ())
        with self.assertRaisesRegex(ipc.ProtocolError, "warmup_intent_forbidden"):
            ipc_lots.parse_lot_message(message(open_intent()), generation="gen1", seq=1, warmup=True)
        with self.assertRaises(ipc.ProtocolError):
            ipc_lots.parse_lot_message(message(), generation="gen1", seq=1, warmup=1)

    def test_p08_v1_and_v2_parsers_do_not_cross_accept(self):
        v2 = message()
        with self.assertRaises(ipc.ProtocolError):
            ipc.check_envelope(v2, "lot_intents", "gen1", 1)
        v1 = ipc.envelope("result", "gen1", 1, {"target": None})
        with self.assertRaises(ipc.ProtocolError):
            ipc_lots.parse_lot_message(v1, generation="gen1", seq=1, warmup=False)

    def test_p09_decimal_fields_reject_json_numbers_bool_and_nonfinite_text(self):
        base = ipc_lots.intent_to_wire(open_intent())
        for value in (1, 1.0, True, "NaN", "Infinity"):
            bad = dict(base, quantity=value)
            with self.subTest(value=value), self.assertRaises(ipc.ProtocolError):
                ipc_lots.intent_from_wire(bad)

    def test_p10_shared_json_decoder_rejects_duplicates_invalid_utf8_depth_and_size(self):
        bad = [b'{"version":2,"version":2}', b'{"x":"\xff"}',
               b'{"x":' + b'[' * 9 + b'0' + b']' * 9 + b'}']
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaises(ipc.ProtocolError):
                ipc.decode_payload(raw)
        with self.assertRaises(ipc.ProtocolError):
            ipc.encode_frame({"x": "x" * ipc.MAX_FRAME})

    def test_p11_shared_framing_handles_truncation_fragmentation_and_consecutive_frames(self):
        raw = ipc_lots.encode_lot_message((open_intent(),), generation="gen1", seq=1)
        with self.assertRaises(ipc.ProtocolError):
            ipc.read_frame_sync(io.BytesIO(raw[:-1]))
        stream = ShortIO(raw + ipc_lots.encode_lot_message((), generation="gen1", seq=2))
        first = ipc.read_frame_sync(stream)
        second = ipc.read_frame_sync(stream)
        self.assertEqual(len(ipc_lots.parse_lot_message(first, generation="gen1", seq=1, warmup=False)), 1)
        self.assertEqual(ipc_lots.parse_lot_message(second, generation="gen1", seq=2, warmup=False), ())

    def test_p12_close_null_remains_null_on_wire(self):
        value = lots.CloseLot(lot().lot_id, None, 4)
        wire = ipc_lots.intent_to_wire(value)
        self.assertIsNone(wire["quantity"])
        self.assertIsNone(ipc_lots.intent_from_wire(wire).quantity)

    def test_p13_update_double_null_is_valid_and_missing_field_is_not_patch(self):
        value = lots.UpdateLotProtection(lot().lot_id, protect(None, None), 4)
        wire = ipc_lots.intent_to_wire(value)
        self.assertEqual(ipc_lots.intent_from_wire(wire), value)
        wire["protection"].pop("stop_loss")
        with self.assertRaises(ipc.ProtocolError):
            ipc_lots.intent_from_wire(wire)

    def test_p14_canonical_decimal_forms_match_and_integer_trailing_zeros_remain(self):
        values = [lots.OpenLot("long", D(text), protect(None, None)) for text in ("1", "1.0", "1e0", "+1")]
        canon = {ipc_lots.canonical_intent(value) for value in values}
        self.assertEqual(len(canon), 1)
        self.assertEqual(ipc_lots._decimal_text(D("-0"), derived=False), "0")
        hundred = ipc_lots.intent_to_wire(lots.OpenLot("long", D("100"), protect(None, None)))
        self.assertEqual(hundred["quantity"], "100")

    def test_p15_content_changes_canonical_bytes_but_not_stable_event_key(self):
        a = open_intent("1")
        b = open_intent("2")
        self.assertNotEqual(ipc_lots.canonical_intent(a), ipc_lots.canonical_intent(b))
        self.assertEqual(lots.make_intent_key(ctx()), lots.make_intent_key(ctx()))

    def test_p16_close_null_and_explicit_quantity_have_distinct_canonical_bytes(self):
        target = lot().lot_id
        null = lots.CloseLot(target, None, 4)
        explicit = lots.CloseLot(target, D("1.5"), 4)
        self.assertNotEqual(ipc_lots.canonical_intent(null), ipc_lots.canonical_intent(explicit))
        expected = json.dumps(ipc_lots.intent_to_wire(null), ensure_ascii=True, sort_keys=True,
                              separators=(",", ":")).encode("utf-8")
        self.assertEqual(ipc_lots.canonical_intent(null), expected)

    def test_p17_precision_is_checked_before_trailing_zero_normalization(self):
        wire = ipc_lots.intent_to_wire(open_intent())
        wire["quantity"] = "1." + "0" * 28
        with self.assertRaises(ipc.ProtocolError):
            ipc_lots.intent_from_wire(wire)

    def test_p18_snapshot_uses_derived_range_but_still_requires_positive_average(self):
        wire = ipc_lots.lot_to_wire(lot())
        wire["average_entry"] = "123456789012345678901234567890.123456789"
        parsed = ipc_lots.lot_from_wire(wire)
        self.assertEqual(parsed.average_entry, D(wire["average_entry"]))
        wire["average_entry"] = "-1"
        with self.assertRaises(ipc.ProtocolError):
            ipc_lots.lot_from_wire(wire)

    def test_p19_wrong_op_and_object_type_fail_without_partial_result(self):
        for value in (None, [], {"op": "UNKNOWN"}, {"side": "long"}):
            with self.subTest(value=value), self.assertRaises(ipc.ProtocolError):
                ipc_lots.intent_from_wire(value)

    def test_p20_encoder_validates_local_object_generation_and_seq(self):
        value = open_intent()
        object.__setattr__(value, "quantity", D("0"))
        with self.assertRaises(ipc.ProtocolError):
            ipc_lots.intent_to_wire(value)
        for generation, seq in (("bad space", 1), ("gen1", 0), ("gen1", True)):
            with self.subTest(generation=generation, seq=seq), self.assertRaises(ipc.ProtocolError):
                ipc_lots.encode_lot_message((), generation=generation, seq=seq)


if __name__ == "__main__":
    unittest.main()
