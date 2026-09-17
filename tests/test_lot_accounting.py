from dataclasses import replace
from decimal import Decimal as D, localcontext, ROUND_DOWN
import unittest

from catos import lots
from catos.lot_accounting import apply_fill, exact_quantity
from lot_journal_helpers import contract, scope
from lot_fill_helpers import fill


class LotAccountingTests(unittest.TestCase):
    def opening(self, side="long"):
        context = lots.IntentContext(scope(), "lot-bot", contract(), 1, False)
        return lots.validate_intent(lots.OpenLot(side, D("3"), lots.LotProtection("mark", None, None)),
                                    context, lots.LotValidationView(None, False, False))

    def close(self, lot):
        return lots.validate_intent(lots.CloseLot(lot.lot_id, None, lot.revision),
                                    lots.IntentContext(scope(), "lot-bot", contract(), 2, False),
                                    lots.LotValidationView(lot, False, False))

    def test_long_hand_calculation(self):
        intent = self.opening()
        lot = apply_fill(None, intent, contract(), fill(quantity=D("2")))
        lot = apply_fill(lot, intent, contract(), fill(seq=2, price=D("130"), fee=D("-0.02")))
        self.assertEqual((lot.remaining_qty, lot.average_entry, lot.fees_paid), (D(3), D(110), D("-0.01")))
        lot = apply_fill(lot, self.close(lot), contract(), fill(order="close", price=D(120)))
        self.assertEqual(lot.realized_pnl, D("0.10"))
        lot = apply_fill(lot, self.close(lot), contract(), fill(order="close2", quantity=D(2), price=D(90)))
        self.assertEqual((lot.remaining_qty, lot.average_entry, lot.realized_pnl, lot.fees_paid),
                         (D(0), D(110), D("-0.30"), D("0.01")))
        self.assertIsNone(lot.funding_paid)

    def test_short_profit_sign(self):
        lot = apply_fill(None, self.opening("short"), contract(), fill(quantity=D(3)))
        result = apply_fill(lot, self.close(lot), contract(), fill(quantity=D(3), price=D(90)))
        self.assertEqual(result.realized_pnl, D("0.30"))

    def test_context_does_not_change_result_or_flags(self):
        with localcontext() as ctx:
            ctx.prec, ctx.rounding = 2, ROUND_DOWN
            ctx.clear_flags()
            before = dict(ctx.flags)
            result = apply_fill(None, self.opening(), contract(), fill(price=D("100.5")))
            self.assertEqual(result.average_entry, D("100.5"))
            self.assertEqual(ctx.flags, before)

    def test_exact_quantity_rejects_lost_fragment(self):
        with self.assertRaises(lots.LotError):
            exact_quantity(D("1e49"), D("0.1"))
        self.assertEqual(exact_quantity(D("1e49"), D(1)), D("1" + "0" * 48 + "1"))

    def test_fill_validation(self):
        for changes in ({"quantity": D(0)}, {"price": D("NaN")}, {"fee_paid": None},
                        {"fee_paid": 0.1}, {"fill_seq": True}, {"fee_currency": "BTC"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(fill(), **changes)

    def test_alignment_and_partial_below_minimum(self):
        result = apply_fill(None, self.opening(), contract(), fill(quantity=D("0.5")))
        self.assertEqual(result.remaining_qty, D("0.5"))
        for changes in ({"quantity": D("0.1")}, {"price": D("100.1")}):
            with self.subTest(changes=changes), self.assertRaises(lots.LotError):
                apply_fill(None, self.opening(), contract(), replace(fill(), **changes))

    def test_overclose_and_closed_reopen_rejected(self):
        intent = self.opening()
        lot = apply_fill(None, intent, contract(), fill())
        with self.assertRaises(lots.LotError):
            apply_fill(lot, self.close(lot), contract(), fill(quantity=D(2)))
        closed = apply_fill(lot, self.close(lot), contract(), fill())
        with self.assertRaises(lots.LotError):
            apply_fill(closed, intent, contract(), fill())

    def test_wrong_scope_or_lot(self):
        with self.assertRaises(lots.LotError):
            apply_fill(None, self.opening(), contract(), replace(fill(), scope=lots.LotScope("other", "local-sim")))

    def test_repeating_average_has_fixed_precision(self):
        intent = self.opening()
        lot = apply_fill(None, intent, contract(), fill(quantity=D(2)))
        lot = apply_fill(lot, intent, contract(), fill(price=D(101)))
        self.assertEqual(lot.average_entry, D("100." + "3" * 47))

    def test_quantity_exponent_and_overflow(self):
        self.assertEqual(exact_quantity(D("1e-148"), D("1e-148")), D("2e-148"))
        self.assertEqual(exact_quantity(D("1e99"), D("-1e99")), D(0))
        with self.assertRaises(lots.LotError):
            exact_quantity(D("9e99"), D("9e99"))

    def test_input_precision_limits(self):
        for changes in ({"price": D("1e19")}, {"fee_paid": D("1e-19")},
                        {"quantity": D("1e100")}, {"quantity": D("1e-149")}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(fill(), **changes)


if __name__ == "__main__":
    unittest.main()
