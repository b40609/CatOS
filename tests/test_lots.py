"""Synthetic unit coverage for S1 Virtual Lot domain rules (L01-L24)."""

from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal, ROUND_DOWN, getcontext, localcontext
import re
import unittest

from catos import lots
from catos.research import ContractSpec


D = Decimal


def contract(**changes):
    values = dict(inst_id="BTC-USDT-SWAP", base_per_contract=D("0.01"),
                  tick_size=D("0.5"), lot_size=D("0.5"), min_size=D("1"))
    values.update(changes)
    return ContractSpec(**values)


def scope(account="acct", environment="local-sim"):
    return lots.LotScope(account, environment)


def protection(tp="120", sl="90"):
    return lots.LotProtection("mark", None if tp is None else D(tp), None if sl is None else D(sl))


def context(*, account="acct", environment="local-sim", bot="botA", seq=1,
            warmup=False, spec=None):
    return lots.IntentContext(scope(account, environment), bot, spec or contract(), seq, warmup)


def snapshot(*, ctx=None, side="long", seq=1, opened="2", remaining="2",
             average="100.25", realized="0", fees="0.1", funding=None,
             revision=1, protect=None):
    ctx = ctx or context(seq=seq)
    key = lots.make_intent_key(ctx)
    return lots.Lot(ctx.scope, ctx.bot_id, ctx.contract.inst_id, lots.make_lot_id(key), key,
                    side, D(opened), D(remaining), D(average), D(realized), D(fees),
                    None if funding is None else D(funding), protect or protection(), revision)


class LotDomainTests(unittest.TestCase):
    def test_l01_multiple_bots_and_opposite_lots_are_independent(self):
        a = snapshot(ctx=context(bot="A", seq=1), average="100")
        b = snapshot(ctx=context(bot="B", seq=1), average="110")
        c = snapshot(ctx=context(bot="C", seq=1), side="short", average="120",
                     protect=protection("90", "130"))
        self.assertEqual([(x.bot_id, x.side, x.average_entry) for x in (a, b, c)],
                         [("A", "long", D("100")), ("B", "long", D("110")),
                          ("C", "short", D("120"))])

    def test_l02_one_bot_can_represent_multiple_same_and_opposite_lots(self):
        values = [snapshot(ctx=context(bot="A", seq=i), side=side,
                           protect=protection("90", "130") if side == "short" else protection())
                  for i, side in ((1, "long"), (2, "long"), (3, "short"))]
        self.assertEqual([x.side for x in values], ["long", "long", "short"])
        self.assertEqual(len({x.lot_id for x in values}), 3)

    def test_l03_domain_objects_are_frozen_including_protection(self):
        value = snapshot()
        with self.assertRaises(FrozenInstanceError):
            value.remaining_qty = D("1")
        with self.assertRaises(FrozenInstanceError):
            value.protection.stop_loss = D("80")

    def test_l04_snapshot_quantity_and_average_invariants(self):
        for changes in (dict(opened="0"), dict(remaining="-0.5"), dict(remaining="2.5"),
                        dict(average="0"), dict(average="NaN")):
            with self.subTest(changes=changes), self.assertRaises(lots.LotError):
                snapshot(**changes)

    def test_l05_closed_snapshot_retains_audit_fields_and_identity(self):
        value = snapshot(remaining="0", realized="5", fees="-0.2")
        self.assertEqual((value.remaining_qty, value.average_entry, value.realized_pnl,
                          value.fees_paid), (D("0"), D("100.25"), D("5"), D("-0.2")))
        self.assertEqual(value.lot_id, lots.make_lot_id(value.open_intent_key))

    def test_l06_rejects_float_nonfinite_range_and_bad_revision(self):
        with self.assertRaises(lots.LotError):
            lots.OpenLot("long", 1.0, protection())
        for value in (D("NaN"), D("Infinity"), D("1e100")):
            with self.subTest(value=value), self.assertRaises(lots.LotError):
                lots.OpenLot("long", value, protection())
        for revision in (0, True, lots.ipc.MAX_INTEGER + 1):
            with self.subTest(revision=revision), self.assertRaises(lots.LotError):
                snapshot(revision=revision)

    def test_l07_average_need_not_match_tick_but_quantities_match_lot_step(self):
        value = snapshot(average="100.25")
        lots.validate_lot(value, contract())
        with self.assertRaisesRegex(lots.LotError, "invalid_quantity"):
            lots.validate_lot(snapshot(opened="1.25", remaining="1.25"), contract())

    def test_l08_open_validates_minimum_step_and_new_event_gets_new_lot(self):
        first_ctx = context(seq=1)
        second_ctx = context(seq=2)
        intent = lots.OpenLot("long", D("1"), protection())
        first = lots.validate_intent(intent, first_ctx, lots.LotValidationView(None, False, False))
        second = lots.validate_intent(intent, second_ctx, lots.LotValidationView(None, False, False))
        self.assertNotEqual(first.lot_id, second.lot_id)
        for quantity in (D("0.5"), D("1.25")):
            with self.subTest(quantity=quantity), self.assertRaises(lots.LotError):
                lots.validate_intent(lots.OpenLot("long", quantity, protection()), first_ctx,
                                     lots.LotValidationView(None, False, False))

    def test_l09_close_partial_and_null_resolve_to_explicit_quantity(self):
        ctx = context()
        value = snapshot(ctx=ctx)
        view = lots.LotValidationView(value, False, False)
        part = lots.validate_intent(lots.CloseLot(value.lot_id, D("0.5"), 1), ctx, view)
        full = lots.validate_intent(lots.CloseLot(value.lot_id, None, 1), ctx, view)
        self.assertEqual((part.resolved_quantity, full.resolved_quantity), (D("0.5"), D("2")))

    def test_l10_close_rejects_zero_negative_unaligned_and_overclose(self):
        value = snapshot()
        for quantity in (D("0"), D("-0.5")):
            with self.subTest(quantity=quantity), self.assertRaises(lots.LotError):
                lots.CloseLot(value.lot_id, quantity, 1)
        for quantity, code in ((D("0.25"), "invalid_quantity"), (D("2.5"), "over_close")):
            with self.subTest(quantity=quantity), self.assertRaisesRegex(lots.LotError, code):
                lots.validate_intent(lots.CloseLot(value.lot_id, quantity, 1), context(),
                                     lots.LotValidationView(value, False, False))

    def test_full_close_preserves_derived_remaining_quantity(self):
        ctx = context(spec=contract(lot_size=D("0.0000000001")))
        for text in ("1000000000000000001.0000000001", "1e19"):
            with self.subTest(quantity=text):
                value = snapshot(ctx=ctx, opened=text, remaining=text)
                request = lots.CloseLot(value.lot_id, None, value.revision)
                with localcontext() as active:
                    active.prec = 2
                    active.rounding = ROUND_DOWN
                    result = lots.validate_intent(
                        request, ctx, lots.LotValidationView(value, False, False))
                self.assertEqual(result.resolved_quantity, value.remaining_qty)
                self.assertEqual(result.resolved_quantity.as_tuple(),
                                 value.remaining_qty.as_tuple())
                self.assertIsNone(result.intent.quantity)

    def test_explicit_worker_quantities_keep_input_precision_limits(self):
        value = snapshot()
        for text in ("1000000000000000001.0000000001", "1e19"):
            with self.subTest(quantity=text):
                with self.assertRaisesRegex(lots.LotError, "invalid_quantity"):
                    lots.OpenLot("long", D(text), protection())
                with self.assertRaisesRegex(lots.LotError, "invalid_quantity"):
                    lots.CloseLot(value.lot_id, D(text), value.revision)

    def test_l11_full_close_of_existing_fragment_below_minimum_is_valid(self):
        spec = contract(lot_size=D("0.5"), min_size=D("1"))
        ctx = context(spec=spec)
        value = snapshot(ctx=ctx, opened="1", remaining="0.5")
        result = lots.validate_intent(lots.CloseLot(value.lot_id, None, 1), ctx,
                                      lots.LotValidationView(value, False, False))
        self.assertEqual(result.resolved_quantity, D("0.5"))

    def test_l12_other_bot_account_environment_or_contract_is_scope_mismatch(self):
        base = context()
        others = [context(bot="other"), context(account="other"), context(environment="demo"),
                  context(spec=contract(inst_id="ETH-USDT-SWAP"))]
        for other in others:
            value = snapshot(ctx=other)
            request = lots.CloseLot(value.lot_id, None, value.revision)
            with self.subTest(other=other), self.assertRaisesRegex(lots.LotError, "lot_scope_mismatch"):
                lots.validate_intent(request, base, lots.LotValidationView(value, False, False))

    def test_l13_not_found_closed_and_stale_revision_are_distinct(self):
        value = snapshot()
        request = lots.CloseLot(value.lot_id, None, 1)
        with self.assertRaisesRegex(lots.LotError, "lot_not_found"):
            lots.validate_intent(request, context(), lots.LotValidationView(None, False, False))
        closed = replace(value, remaining_qty=D("0"))
        with self.assertRaisesRegex(lots.LotError, "lot_closed"):
            lots.validate_intent(request, context(), lots.LotValidationView(closed, False, False))
        newer = replace(value, revision=2)
        with self.assertRaisesRegex(lots.LotError, "revision_conflict"):
            lots.validate_intent(request, context(), lots.LotValidationView(newer, False, False))

    def test_l14_unresolved_open_or_close_makes_close_and_update_busy(self):
        value = snapshot()
        intents = (lots.CloseLot(value.lot_id, None, 1),
                   lots.UpdateLotProtection(value.lot_id, protection("125", "95"), 1))
        for opening, closing in ((True, False), (False, True)):
            for intent in intents:
                with self.subTest(opening=opening, closing=closing, intent=intent), self.assertRaisesRegex(lots.LotError, "lot_busy"):
                    lots.validate_intent(intent, context(), lots.LotValidationView(value, opening, closing))

    def test_l15_open_requires_empty_consistent_view(self):
        intent = lots.OpenLot("long", D("1"), protection())
        value = snapshot()
        for view in (lots.LotValidationView(value, False, False),
                     lots.LotValidationView(None, True, False),
                     lots.LotValidationView(None, False, True)):
            with self.subTest(view=view), self.assertRaisesRegex(lots.LotError, "invalid_view"):
                lots.validate_intent(intent, context(), view)

    def test_l16_protection_requires_positive_tick_aligned_ordered_prices(self):
        for bad in (("0", None), ("-1", None), ("NaN", None)):
            with self.subTest(bad=bad), self.assertRaises(lots.LotError):
                protection(*bad)
        for value in (protection("120.25", "90"), protection("100", "100"),
                      protection("90", "120")):
            with self.subTest(value=value), self.assertRaisesRegex(lots.LotError, "invalid_protection"):
                lots.validate_protection(value, "long", contract())

    def test_l17_profit_side_stop_and_null_combinations_are_valid(self):
        for side, value in (("long", protection("130", "110")),
                            ("short", protection("90", "110")),
                            ("long", protection(None, "90")),
                            ("short", protection("90", None)),
                            ("long", protection(None, None))):
            lots.validate_protection(value, side, contract())

    def test_l18_signed_pnl_rebate_and_unknown_funding_are_preserved(self):
        value = snapshot(realized="-5", fees="-0.2", funding=None)
        self.assertEqual((value.realized_pnl, value.fees_paid, value.funding_paid),
                         (D("-5"), D("-0.2"), None))
        self.assertEqual(snapshot(funding="-0.3").funding_paid, D("-0.3"))

    def test_l19_stable_identity_changes_only_with_stable_identity_fields(self):
        base = context()
        self.assertEqual(lots.make_intent_key(base), lots.make_intent_key(base))
        variants = [context(account="other"), context(environment="demo"), context(bot="other"),
                    context(spec=contract(inst_id="ETH-USDT-SWAP")), context(seq=2)]
        self.assertEqual(len({lots.make_intent_key(x) for x in [base, *variants]}), 6)

    def test_l20_output_index_and_derived_identifier_format_are_strict(self):
        with self.assertRaises(lots.LotError):
            lots.make_intent_key(context(), 1)
        key = lots.make_intent_key(context())
        lot_id = lots.make_lot_id(key)
        self.assertRegex(key, re.compile(r"^[0-9a-f]{64}$"))
        self.assertRegex(lot_id, re.compile(r"^[0-9a-f]{64}$"))

    def test_l21_decimal_context_does_not_change_validation(self):
        before = getcontext().copy()
        with localcontext() as active:
            active.prec = 2
            active.rounding = ROUND_DOWN
            lots.validate_intent(lots.OpenLot("long", D("1.5"), protection()), context(),
                                 lots.LotValidationView(None, False, False))
            self.assertEqual((active.prec, active.rounding), (2, ROUND_DOWN))
        after = getcontext()
        self.assertEqual(
            (after.prec, after.rounding, after.Emin, after.Emax, after.capitals, after.clamp,
             dict(after.traps), dict(after.flags)),
            (before.prec, before.rounding, before.Emin, before.Emax, before.capitals, before.clamp,
             dict(before.traps), dict(before.flags)),
        )

    def test_l22_warmup_rejects_all_intents_and_validated_type_has_no_approval(self):
        value = snapshot()
        candidates = ((lots.OpenLot("long", D("1"), protection()), lots.LotValidationView(None, False, False)),
                      (lots.CloseLot(value.lot_id, None, 1), lots.LotValidationView(value, False, False)),
                      (lots.UpdateLotProtection(value.lot_id, protection(), 1), lots.LotValidationView(value, False, False)))
        for intent, view in candidates:
            with self.subTest(intent=intent), self.assertRaisesRegex(lots.LotError, "warmup_intent_forbidden"):
                lots.validate_intent(intent, context(warmup=True), view)
        names = {field.name for field in fields(lots.ValidatedLotIntent)}
        self.assertFalse({"approved", "risk_approved", "reservation", "trade_authorized"} & names)

    def test_l23_requested_lot_must_match_snapshot_identity(self):
        ctx = context(bot="A")
        a = snapshot(ctx=ctx, seq=1)
        b = snapshot(ctx=context(bot="A", seq=2), seq=2)
        request = lots.CloseLot(a.lot_id, None, b.revision)
        with self.assertRaisesRegex(lots.LotError, "lot_identity_mismatch"):
            lots.validate_intent(request, ctx, lots.LotValidationView(b, False, False))

    def test_l24_snapshot_identity_must_be_derived_from_open_intent(self):
        value = snapshot()
        with self.assertRaisesRegex(lots.LotError, "lot_identity_mismatch"):
            replace(value, lot_id="a" * 64)
        with self.assertRaisesRegex(lots.LotError, "lot_identity_mismatch"):
            replace(value, open_intent_key="A" * 64)


if __name__ == "__main__":
    unittest.main()
