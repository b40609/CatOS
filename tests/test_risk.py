"""Synthetic Decimal exposure, fixed daily basis, and monotonic control tests."""

from dataclasses import replace
from decimal import Decimal, localcontext
import unittest

from catos import ipc, risk
from test_ipc import config

D = Decimal


def snapshot(seq=1, time_ms=0, **changes):
    return replace(risk.Snapshot(seq, time_ms, time_ms + 60_000, D("1000"), D("1000"),
                                D("0"), D("100"), basis=risk.DayBasis(risk.taipei_day(time_ms),
                                                                      D("1000"), "synthetic-day")), **changes)


def verdict(s=None, target="2", **kwargs):
    state = risk.observe(risk.State(), snapshot() if s is None else s)
    return risk.evaluate(state, risk.Limits(), config().contract, D(target), state.snapshot.position,
                         state.snapshot.time_ms, reconciled=True, **kwargs)


class RiskTests(unittest.TestCase):
    def test_actual_leverage_uses_equity_without_pending_credit(self):
        self.assertEqual(risk.effective_leverage((D("1000"), D("500")), D("1000")), D("1.5"))
        self.assertIsNone(risk.effective_leverage((D("1000"),), D("0")))

    def test_pending_both_sides_and_unknown_are_not_netted(self):
        self.assertEqual(risk.worst_notional(D("10"), D("4"), D("9"), D(".01"), D("100")), D("14"))
        self.assertEqual(risk.worst_notional(D("-10"), D("9"), D("4"), D(".01"), D("100")), D("14"))
        self.assertEqual(risk.worst_notional(D("0"), D("10"), D("10"), D("1"), D("100")), D("1000"))
        self.assertFalse(verdict(snapshot(pending_buy=D("1499")), held_sell=D("1499")).accepted)

    def test_symbol_budget_is_fraction_of_max_budget_and_exact_boundary(self):
        self.assertTrue(verdict(target="1500").accepted)
        self.assertEqual(verdict(target="1501").reason, "symbol_exposure_limit")
        self.assertEqual(verdict(snapshot(other_notional=D("1501")), target="1500").reason, "account_exposure_limit")
        self.assertTrue(verdict(snapshot(other_notional=D("1500")), target="1500").accepted)

    def test_held_reservations_are_revalued_at_current_mark(self):
        self.assertTrue(verdict(held_buy=D("1498")).accepted)
        self.assertFalse(verdict(held_buy=D("1499")).accepted)
        self.assertFalse(verdict(snapshot(mark=D("200")), held_buy=D("750")).accepted)

    def test_nonpositive_or_unreliable_equity_blocks_increase_without_division(self):
        for changes in (dict(equity=D("0")), dict(risk_equity=D("0")), dict(risk_equity=D("-1")),
                        dict(valuation_known=False), dict(flows_known=False), dict(margin_ok=False), dict(basis=None)):
            with self.subTest(changes=changes):
                self.assertFalse(verdict(snapshot(**changes)).accepted)

    def test_legal_reduction_survives_all_increase_gates(self):
        state = risk.observe(risk.State(), snapshot(position=D("10"), equity=D("800"),
                                                   risk_equity=D("0"), margin_ok=False))
        self.assertEqual(state.mode, "FLAT")
        for target in (D("0"), D("5")):
            result = risk.evaluate(state, risk.Limits(), config().contract, target, D("10"), 0, reconciled=True)
            self.assertTrue(result.accepted)
            self.assertTrue(result.reduce_only)
            self.assertEqual(result.reservation, 0)
        self.assertFalse(risk.evaluate(state, risk.Limits(), config().contract, D("-1"), D("10"), 0, reconciled=True).accepted)

    def test_reduction_requires_fresh_position_and_no_conflicting_reduction(self):
        for changes in (dict(position_verified=False), dict(reduction_conflict=True), dict(pending_sell=D("1"))):
            with self.subTest(changes=changes):
                self.assertFalse(verdict(snapshot(position=D("10"), **changes), target="0").accepted)
        self.assertFalse(verdict(snapshot(position=D("10")), target="0", held_reduction=True).accepted)
        state = risk.observe(risk.State(), snapshot(position=D("10")))
        for position, now, known in ((D("9"), 0, True), (D("10"), 60_000, True), (D("10"), 0, False)):
            self.assertFalse(risk.evaluate(state, risk.Limits(), config().contract, D("0"), position, now, reconciled=known).accepted)
        expired = risk.expire(state, 60_000)
        self.assertFalse(risk.evaluate(expired, risk.Limits(), config().contract, D("0"), D("10"), 0, reconciled=True).accepted)
        self.assertEqual(verdict(snapshot(position=D("10")), target="9.5").reason, "invalid_contract_quantity")

    def test_short_reduction_and_cross_zero_rejected(self):
        self.assertTrue(verdict(snapshot(position=D("-10")), target="-5").reduce_only)
        self.assertEqual(verdict(snapshot(position=D("10")), target="-1").reason, "cross_zero_forbidden")

    def test_soft_hard_boundaries_and_fixed_external_flow_denominator(self):
        for equity, expected in (("900.0001", "RUN"), ("900", "NO_INCREASE"), ("800", "FLAT")):
            self.assertEqual(risk.observe(risk.State(), snapshot(equity=D(equity))).mode, expected)
        # A 100 deposit is excluded, and does not dilute the original 1000 denominator.
        self.assertEqual(risk.observe(risk.State(), snapshot(equity=D("1000"), external_net=D("100"))).mode, "NO_INCREASE")
        self.assertEqual(risk.observe(risk.State(), snapshot(equity=D("700"), external_net=D("-100"))).mode, "FLAT")

    def test_taipei_midnight_requires_explicit_basis_and_keeps_latches(self):
        midnight = risk.DAY_MS - risk.TAIPEI_OFFSET_MS
        self.assertEqual(risk.taipei_day(midnight - 1), 0)
        self.assertEqual(risk.taipei_day(midnight), 1)
        state = risk.observe(risk.State(), snapshot(time_ms=midnight - 1, equity=D("800")))
        op = state.flatten_id
        state = risk.observe(state, snapshot(2, midnight, basis=None, equity=D("2000")))
        self.assertEqual((state.mode, state.health, state.flatten_id), ("FLAT", "DEGRADED", op))
        restored = risk.State.from_wire(state.to_wire())
        self.assertIsNone(restored.basis_blocked_day)
        retried = risk.observe(restored, snapshot(3, midnight + 1, equity=D("2000")))
        self.assertEqual((retried.mode, retried.health), ("FLAT", "HEALTHY"))
        next_midnight = midnight + risk.DAY_MS
        state = risk.observe(restored, snapshot(3, next_midnight, equity=D("2000")))
        self.assertEqual((state.mode, state.health, state.flatten_id), ("FLAT", "HEALTHY", op))
        self.assertIsNone(state.basis_blocked_day)

    def test_fixed_basis_cannot_be_rebuilt_on_restart_or_same_day(self):
        state = risk.observe(risk.State(), snapshot())
        restored = risk.State.from_wire(state.to_wire())
        self.assertEqual(restored, state)
        with self.assertRaisesRegex(ipc.ProtocolError, "fixed day basis"):
            risk.observe(restored, snapshot(2, 1, basis=risk.DayBasis(0, D("2000"), "new")))
        with self.assertRaises(ipc.ProtocolError):
            risk.observe(restored, snapshot())

    def test_bounce_deposit_kill_and_progress_never_rearm(self):
        state = risk.observe(risk.State(), snapshot(equity=D("800")))
        epoch = state.epoch
        op = state.flatten_id
        state = risk.observe(state, snapshot(2, 1, equity=D("3000"), external_net=D("2000")))
        self.assertEqual(state.mode, "FLAT")
        state = risk.halt(state, {"manual_kill"})
        self.assertGreater(state.epoch, epoch)
        self.assertEqual(state.flatten_id, op)
        self.assertEqual(risk.halt(state, {"manual_kill"}), state)
        with self.assertRaises(ipc.ProtocolError):
            risk.progress(state, "DONE", complete=True)
        state = risk.progress(risk.progress(state, "VERIFY"), "DONE", complete=True)
        state = risk.observe(state, snapshot(3, 2, position=D("1")))
        self.assertEqual((state.mode, state.phase, state.flatten_id), ("FLAT", "WORKING", op))

    def test_timer_and_next_day_close_increases_independent_of_bar(self):
        state = risk.observe(risk.State(), snapshot())
        self.assertEqual(risk.expire(state, 60_000).health, "DEGRADED")
        midnight = risk.DAY_MS - risk.TAIPEI_OFFSET_MS
        state = risk.observe(risk.State(), snapshot(time_ms=midnight - 1))
        self.assertEqual(risk.expire(state, midnight).health, "DEGRADED")
        self.assertEqual(risk.evaluate(state, risk.Limits(), config().contract, D("1"), D("0"), midnight, reconciled=True).reason, "day_basis_missing")

    def test_decimal_context_isolation_and_float_rejection(self):
        with localcontext() as ctx:
            ctx.prec = 2
            self.assertEqual(risk.worst_notional(D("123.456"), D("1.234"), D("0"), D(".01"), D("100")), D("124.690"))
            self.assertTrue(verdict(target="1500").accepted)
        for value in (1.0, D("NaN"), D("Infinity")):
            with self.assertRaises(ipc.ProtocolError):
                snapshot(mark=value)
            with self.assertRaises(ipc.ProtocolError):
                risk.Limits(leverage=value)


if __name__ == "__main__":
    unittest.main()
