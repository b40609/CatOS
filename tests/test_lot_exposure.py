"""S4 pure synthetic observations; no database or external account access."""

from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal as D, ROUND_DOWN, localcontext
import unittest

from catos import lots, risk
from catos.lot_exposure import (
    ExposureInputError, ExposureRequest, LotInventory, MarkObservation,
    PendingInventory, PendingObligation, PhysicalPosition, observe_exposure,
)
from catos.lot_journal import StoredLot
from lot_journal_helpers import contract, scope, snapshot


def item(seq=1, quantity=D(2), side="long", opening=False, closing=False, spec=None):
    lot = snapshot(seq=seq, spec=spec, side=side, opened_qty=max(quantity, D(2)), remaining_qty=quantity)
    return StoredLot(lot, opening, closing, seq)


def request(items=None, quantity=D(2), orders=(), spec=None):
    spec = spec or contract()
    items = (item(spec=spec),) if items is None else items
    return ExposureRequest(
        scope(), spec, 100,
        LotInventory(scope(), spec.inst_id, "cut", 90, 110, True, ("lot-bot",), ("lot-bot",), items),
        PhysicalPosition(scope(), spec.inst_id, "cut", 90, 110, quantity, quantity is not None),
        MarkObservation(scope(), spec.inst_id, "quote", 90, 110, D(100)),
        PendingInventory(scope(), spec.inst_id, "cut", 90, 110, True, orders))


def order(obligation_id="order", quantity=D(1), side="BUY", effect="OPEN", lot_id=None,
          origin="EXCHANGE", state="WORKING"):
    return PendingObligation(obligation_id, origin, state, side, quantity, effect,
                             snapshot(seq=9).lot_id if lot_id is None and effect != "UNCLASSIFIED" else lot_id)


class LotExposureTests(unittest.TestCase):
    def reject(self, value, code=None):
        with self.assertRaises(ExposureInputError) as caught:
            observe_exposure(value)
        if code is not None:
            self.assertEqual(caught.exception.code, code)

    def test_e01_complete_empty_inventory(self):
        result = observe_exposure(request(items=(), quantity=D(0)))
        self.assertEqual((result.observed_gross_qty, result.observed_net_qty, result.delta_qty), (D(0), D(0), D(0)))
        self.assertEqual(result.comparison_status, "MATCH")
        self.assertEqual(result.virtual_gross_scenario_upper_qty, D(0))

    def test_e02_single_long_and_short(self):
        for side, net in (("long", D(2)), ("short", D(-2))):
            with self.subTest(side=side):
                result = observe_exposure(request(items=(item(side=side),), quantity=net))
                self.assertEqual(result.observed_gross_qty, D(2))
                self.assertEqual(result.observed_net_qty, net)
                self.assertEqual(result.observed_signed_net_notional, net)
                self.assertEqual(result.physical_notional, D(2))

    def test_e03_opposite_lots_do_not_cancel_gross(self):
        result = observe_exposure(request(items=(item(quantity=D(3)), item(seq=2, side="short")), quantity=D(1)))
        self.assertEqual((result.observed_long_qty, result.observed_short_qty, result.observed_gross_qty), (D(3), D(2), D(5)))
        self.assertEqual((result.observed_net_qty, result.observed_gross_notional), (D(1), D(5)))
        other = StoredLot(snapshot(bot="other", seq=2, side="short"), False, False, 1)
        r = request(items=(item(quantity=D(3)), other), quantity=D(1))
        r = replace(r, lots_view=replace(r.lots_view, expected_bot_ids=("lot-bot", "other"),
                                        included_bot_ids=("other", "lot-bot")))
        self.assertEqual(observe_exposure(r).observed_gross_qty, D(5))

    def test_e04_closed_lot_retains_unresolved_responsibility(self):
        closed = item(quantity=D(0), closing=True)
        result = observe_exposure(request(items=(closed,), quantity=D(0)))
        self.assertEqual(result.observed_gross_qty, D(0))
        self.assertEqual(result.unresolved_lot_count, 1)
        self.assertIn("pending_lot_link_incomplete", result.reasons)
        self.assertIsNone(result.physical_scenario_upper_qty)

    def test_e05_exact_signed_differences(self):
        for physical, delta, status in ((D(2), D(0), "MATCH"), (D(3), D(-1), "MISMATCH"), (D(0), D(2), "MISMATCH")):
            with self.subTest(physical=physical):
                result = observe_exposure(request(quantity=physical))
                self.assertEqual((result.delta_qty, result.comparison_status), (delta, status))

    def test_e06_missing_page_or_bot_is_not_complete(self):
        r = request()
        for inventory in (replace(r.lots_view, complete=False),
                          replace(r.lots_view, expected_bot_ids=("lot-bot", "missing"), complete=False)):
            result = observe_exposure(replace(r, lots_view=inventory))
            self.assertEqual(result.observed_gross_qty, D(2))
            self.assertIsNone(result.delta_qty)
            self.assertIn("lot_inventory_incomplete", result.reasons)

    def test_e07_equal_timestamps_do_not_prove_equal_cut(self):
        r = request()
        result = observe_exposure(replace(r, physical_view=replace(r.physical_view, cut_id="other")))
        self.assertIsNone(result.delta_qty)
        self.assertIn("position_cut_mismatch", result.reasons)

    def test_e08_unknown_and_unverified_physical(self):
        r = request()
        for position in (replace(r.physical_view, quantity=None, verified=False), replace(r.physical_view, verified=False)):
            result = observe_exposure(replace(r, physical_view=position))
            self.assertEqual(result.physical_qty, position.quantity)
            self.assertIsNone(result.delta_qty)
            self.assertIsNone(result.pending_buy_qty)
        self.reject(replace(r, physical_view=replace(r.physical_view, quantity=None)), "identity_mismatch")

    def test_e09_missing_mark_preserves_quantity_comparison(self):
        result = observe_exposure(replace(request(), mark_view=None))
        self.assertEqual(result.comparison_status, "MATCH")
        self.assertIsNone(result.observed_gross_notional)
        self.assertIsNone(result.physical_notional)
        self.assertIn("mark_missing", result.reasons)

    def test_e10_freshness_deadline_is_exclusive(self):
        r = request()
        self.assertTrue(observe_exposure(replace(r, now_ms=109)).mark_fresh)
        result = observe_exposure(replace(r, now_ms=110))
        for name in ("lot_stale", "physical_stale", "mark_stale", "pending_stale"):
            self.assertIn(name, result.reasons)
        self.assertIsNone(result.delta_qty)
        self.assertIsNone(result.observed_gross_notional)

    def test_e11_future_observation_and_invalid_range(self):
        r = request()
        for field in ("lots_view", "physical_view", "mark_view", "pending_view"):
            with self.subTest(field=field):
                value = getattr(r, field)
                future = replace(value, observed_at_ms=101)
                self.assertIn("future_observation", observe_exposure(replace(r, **{field: future})).reasons)
                self.reject(replace(r, **{field: replace(value, valid_until_ms=90)}), "invalid_time_range")

    def test_e12_mark_does_not_require_tick_alignment(self):
        r = request()
        result = observe_exposure(replace(r, mark_view=replace(r.mark_view, mark=D("100.125"))))
        self.assertEqual(result.observed_gross_notional, D("2.0025"))
        self.assertTrue(result.mark_fresh)

    def test_e13_held_and_exchange_buckets(self):
        orders = (order("held", D(2), origin="HELD", state="HELD"),
                  order("exchange", D(3), side="SELL", lot_id=snapshot(seq=10).lot_id))
        result = observe_exposure(request(orders=orders))
        self.assertEqual((result.held_buy_qty, result.held_sell_qty, result.exchange_buy_qty, result.exchange_sell_qty),
                         (D(2), D(0), D(0), D(3)))

    def test_e14_opposite_pending_are_not_netted(self):
        orders = (order("buy", D(2)), order("sell", D(3), side="SELL", lot_id=snapshot(seq=10).lot_id))
        result = observe_exposure(request(quantity=D(1), orders=orders))
        self.assertEqual((result.pending_buy_qty, result.pending_sell_qty), (D(2), D(3)))
        self.assertEqual(result.physical_scenario_upper_qty, D(3))
        self.assertEqual(result.virtual_gross_scenario_upper_qty, D(7))
        self.assertEqual(result.comparison_status, "MISMATCH")

    def test_e15_equivalent_duplicates_count_once(self):
        a = order()
        result = observe_exposure(request(orders=(a, replace(a, remaining_quantity=D("1.00")))))
        self.assertEqual((result.pending_unique_count, result.pending_duplicate_count), (1, 1))
        self.assertEqual(result.pending_buy_qty, D(1))

    def test_e16_duplicate_conflict_is_rejected(self):
        a = order()
        for change in ({"origin": "HELD", "state": "HELD"}, {"remaining_quantity": D(2)},
                       {"state": "UNKNOWN"}, {"side": "SELL"}, {"effect": "UNCLASSIFIED"},
                       {"lot_id": snapshot(seq=8).lot_id}):
            with self.subTest(change=change):
                self.reject(request(orders=(a, replace(a, **change))), "pending_conflict")

    def test_e17_known_unknown_quantity_is_counted(self):
        result = observe_exposure(request(orders=(order(quantity=D(3), state="UNKNOWN"),)))
        self.assertTrue(result.has_unknown)
        self.assertEqual(result.pending_buy_qty, D(3))
        self.assertEqual(result.physical_scenario_upper_qty, D(5))

    def test_e18_missing_quantity_never_becomes_zero(self):
        for state in ("UNKNOWN", "WORKING"):
            result = observe_exposure(request(orders=(order(quantity=None, state=state),)))
            self.assertIsNone(result.pending_buy_qty)
            self.assertIsNone(result.held_buy_qty)
            self.assertIsNone(result.virtual_gross_scenario_upper_qty)
            self.assertIn("pending_quantity_unknown", result.reasons)

    def test_e19_pending_close_does_not_reduce_current_gross(self):
        lot = item(closing=True)
        result = observe_exposure(request(items=(lot,), orders=(order(side="SELL", effect="CLOSE", lot_id=lot.lot.lot_id),)))
        self.assertEqual(result.observed_gross_qty, D(2))
        self.assertEqual(result.virtual_gross_scenario_upper_qty, D(2))
        self.assertEqual(result.physical_scenario_upper_qty, D(2))

    def test_e20_unclassified_has_only_physical_scenario(self):
        for lot_id, items in ((None, (item(),)), (item().lot.lot_id, (item(opening=True),))):
            result = observe_exposure(request(items=items, orders=(order(effect="UNCLASSIFIED", lot_id=lot_id),)))
            self.assertEqual(result.physical_scenario_upper_qty, D(3))
            self.assertIsNone(result.virtual_gross_scenario_upper_qty)
            self.assertIn("pending_effect_unknown", result.reasons)

    def test_e21_missing_and_incomplete_pending(self):
        r = request()
        for pend, reason in ((None, "pending_missing"), (replace(r.pending_view, complete=False), "pending_incomplete")):
            result = observe_exposure(replace(r, pending_view=pend))
            self.assertIsNone(result.pending_sell_qty)
            self.assertIn(reason, result.reasons)
            self.assertEqual(result.comparison_status, "MATCH")

    def test_e22_pending_cut_mismatch(self):
        r = request()
        result = observe_exposure(replace(r, pending_view=replace(r.pending_view, cut_id="different")))
        self.assertIsNone(result.physical_scenario_upper_qty)
        self.assertIn("pending_cut_mismatch", result.reasons)

    def test_e23_flags_require_matching_responsibility(self):
        for value in (request(items=(item(opening=True),)),
                      request(orders=(order(lot_id=item().lot.lot_id),)),
                      request(items=(item(opening=True, closing=True),))):
            result = observe_exposure(value)
            self.assertIn("pending_lot_link_incomplete", result.reasons)
            self.assertIsNone(result.pending_buy_qty)
        opened = item(opening=True)
        result = observe_exposure(request(items=(opened,), orders=(order(lot_id=opened.lot.lot_id),)))
        self.assertEqual(result.virtual_gross_scenario_upper_qty, D(3))
        closed = item(side="short", closing=True)
        result = observe_exposure(request(items=(closed,), quantity=D(-2),
            orders=(order(effect="CLOSE", lot_id=closed.lot.lot_id),)))
        self.assertEqual(result.virtual_gross_scenario_upper_qty, D(2))

    def test_e24_zero_unknown_retains_responsibility(self):
        result = observe_exposure(request(orders=(order(quantity=D(0), state="UNKNOWN"),)))
        self.assertTrue(result.has_unknown)
        self.assertEqual(result.pending_buy_qty, D(0))
        self.assertEqual(result.pending_unique_count, 1)

    def test_e25_scope_and_contract_identity(self):
        r = request()
        for field in ("lots_view", "physical_view", "mark_view", "pending_view"):
            for change in ({"scope": lots.LotScope("other", "local-sim")}, {"inst_id": "OTHER-USDT-SWAP"}):
                with self.subTest(field=field, change=change):
                    self.reject(replace(r, **{field: replace(getattr(r, field), **change)}), "identity_mismatch")
        self.reject(replace(r, scope=lots.LotScope("fake-account", "demo")), "invalid_scope")

    def test_e26_duplicate_lot_and_invalid_bot_coverage(self):
        r = request()
        self.reject(request(items=(item(), item())), "duplicate_lot")
        for changes in ({"expected_bot_ids": ("lot-bot", "lot-bot")},
                        {"included_bot_ids": ("lot-bot", "other")},
                        {"expected_bot_ids": ("lot-bot", "missing")}, {"included_bot_ids": ()}):
            with self.subTest(changes=changes):
                self.reject(replace(r, lots_view=replace(r.lots_view, **changes)), "invalid_bot_coverage")

    def test_e27_pending_direction_and_missing_close_lot(self):
        lot = item(closing=True)
        self.reject(request(items=(lot,), orders=(order(effect="CLOSE", lot_id=lot.lot.lot_id),)), "invalid_pending_direction")
        self.reject(request(orders=(order(effect="CLOSE", side="SELL"),)), "identity_mismatch")
        self.reject(request(orders=(replace(order(), origin="HELD"),)), "pending_conflict")
        self.reject(request(orders=(replace(order(), lot_id=None),)), "identity_mismatch")

    def test_e28_same_lot_cannot_have_two_obligations(self):
        self.reject(request(orders=(order("one"), order("two"))), "pending_conflict")

    def test_e29_non_decimal_and_boolean_inputs(self):
        r = request()
        for value in (1.0, True, D("NaN"), D("Infinity"), "1"):
            with self.subTest(value=value):
                self.reject(replace(r, physical_view=replace(r.physical_view, quantity=value)), "invalid_decimal")
                self.reject(replace(r, mark_view=replace(r.mark_view, mark=value)), "invalid_decimal")
        self.reject(replace(r, now_ms=True), "invalid_integer")
        self.reject(replace(r, lots_view=replace(r.lots_view, complete=1)), "invalid_integer")
        self.reject(request(items=(replace(item(), commit_seq=True),)), "invalid_integer")
        self.reject(request(items=(replace(item(), opening_unresolved=1),)), "invalid_integer")
        self.reject(request(quantity=D("0.1")), "invalid_decimal")
        self.reject(request(orders=(order(quantity=D("0.1")),)), "invalid_decimal")
        for mark in (D(0), D(-1)):
            self.reject(replace(r, mark_view=replace(r.mark_view, mark=mark)), "invalid_decimal")
        for field in ("lots_view", "physical_view", "mark_view", "pending_view"):
            self.reject(replace(r, **{field: replace(getattr(r, field), observed_at_ms=True)}), "invalid_integer")

    def test_e30_derived_precision_preserves_small_difference(self):
        spec = contract(lot_size=D("1e-18"), min_size=D("1e-18"))
        value = D("999999999999999999.999999999999999999")
        r = request(items=(item(quantity=value, spec=spec),), quantity=D("1e18"), spec=spec)
        result = observe_exposure(r)
        self.assertEqual(result.delta_qty, D("-1e-18"))
        self.assertEqual(result.comparison_status, "MISMATCH")

    def test_e31_exact_products_and_range_rejection(self):
        r = request()
        self.reject(replace(r, mark_view=replace(r.mark_view, mark=D("1e-148"))), "decimal_range")
        spec = contract(base_per_contract=D("1e18"))
        self.reject(replace(request(spec=spec), mark_view=replace(r.mark_view, mark=D("1e99"))), "decimal_range")
        value = D("1." + "1" * 49)
        spec = contract(base_per_contract=D("1.000000000000000001"))
        self.reject(replace(request(spec=spec), mark_view=replace(r.mark_view, mark=value)), "decimal_range")
        self.reject(request(items=(item(quantity=D("1e49")), item(seq=2, quantity=D("0.5")))), "decimal_range")
        boundary = replace(r, mark_view=replace(r.mark_view, mark=D("1e-146")))
        self.assertEqual(observe_exposure(boundary).observed_gross_notional, D("2e-148"))

    def test_e32_ambient_context_and_flags_are_unchanged(self):
        r = request()
        expected = observe_exposure(r)
        with localcontext() as ctx:
            ctx.prec, ctx.rounding = 2, ROUND_DOWN
            ctx.clear_flags()
            flags = dict(ctx.flags)
            self.assertEqual(observe_exposure(r), expected)
            self.assertEqual(ctx.flags, flags)

    def test_e33_input_order_does_not_change_report(self):
        r = request(items=(item(), item(seq=2, side="short")), quantity=D(0),
                    orders=(order("a"), order("b", side="SELL", lot_id=snapshot(seq=8).lot_id)))
        changed = replace(r, lots_view=replace(r.lots_view, lots=tuple(reversed(r.lots_view.lots))),
                          pending_view=replace(r.pending_view, orders=tuple(reversed(r.pending_view.orders))))
        self.assertEqual(observe_exposure(r), observe_exposure(changed))

    def test_e34_immutable_and_repeatable_observations(self):
        r = request()
        before = repr(r)
        a, b = observe_exposure(r), observe_exposure(r)
        self.assertEqual(a, b)
        self.assertEqual(repr(r), before)
        with self.assertRaises(FrozenInstanceError):
            a.observed_gross_qty = D(99)
        self.assertFalse({"accepted", "ready", "allowed", "verdict"} & {f.name for f in fields(a)})
        self.assertEqual(a.reasons, tuple(sorted(set(a.reasons))))

    def test_e35_capacity_is_bounded_without_truncation(self):
        r = request()
        self.reject(request(items=(item(),) * 4097), "input_limit")
        self.reject(request(orders=(order(),) * 4097), "input_limit")
        self.reject(replace(r, lots_view=replace(r.lots_view, expected_bot_ids=tuple(f"bot{i}" for i in range(65)))), "input_limit")
        result = observe_exposure(request(orders=(order(),) * 4096))
        self.assertEqual(result.pending_duplicate_count, 4095)
        items = tuple(item(seq=i + 1, quantity=D(0)) for i in range(4096))
        self.assertEqual(observe_exposure(request(items=items, quantity=D(0))).observed_gross_qty, D(0))

    def test_e36_physical_scenario_matches_existing_risk_arithmetic(self):
        r = request(orders=(order("buy", D(2)), order("sell", D(4), side="SELL", lot_id=snapshot(seq=8).lot_id)))
        result = observe_exposure(r)
        self.assertEqual(result.physical_scenario_upper_qty, D(4))
        self.assertEqual(risk.worst_notional(D(2), D(2), D(4), r.contract.base_per_contract, r.mark_view.mark), D(4))


if __name__ == "__main__":
    unittest.main()
