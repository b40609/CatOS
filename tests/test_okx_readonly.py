"""Synthetic public-schema fixtures only; no recorded account data."""
from dataclasses import replace
from decimal import Decimal as D, localcontext
import unittest

from catos import okx_readonly as o


def order(**changes):
    raw = dict(instType="SWAP", instId="BTC-USDT-SWAP", tdMode="cross", posSide="net",
               ordId="1", clOrdId="local1", side="buy", state="partially_filled",
               sz="2", accFillSz="1", uTime="1000")
    return o.order(raw | changes)


def fill(**changes):
    return dict(instId="BTC-USDT-SWAP", tradeId="10", ordId="1", fillSz="1",
                fillPx="100.12345678901234567890123456789", fee="-0.01", feeCcy="USDT") | changes


class ReadonlyTests(unittest.TestCase):
    def test_equity_exact_without_usd_conversion_or_buffer(self):
        value = "1000.12345678901234567890123456789"
        payload = dict(code="0", data=[dict(totalEq="99999", adjEq="1", details=[
            dict(ccy="USDT", eq=value, liab="0")])])
        with localcontext() as ctx:
            ctx.prec = 6
            self.assertEqual(o.usdt_equity(payload), (D(value), D(value)))

    def test_invalid_financial_values_do_not_become_zero(self):
        for value in (None, "", "NaN", "Infinity", 1.5, "1e1000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                o.number({"x": value}, "x")

    def test_balance_profile_is_explicit(self):
        for detail in (dict(ccy="BTC", eq="1", liab="0"), dict(ccy="USDT", eq="1", liab="1")):
            with self.assertRaises(ValueError):
                o.usdt_equity(dict(code="0", data=[dict(details=[detail])]))

    def test_error_envelope_and_missing_rows_rejected(self):
        for payload in ({"code": "1", "data": []}, {"code": "0"}, {"code": "0", "data": [None]}):
            with self.assertRaises(ValueError):
                o.rows(payload)

    def test_modes_unknown_states_and_sizes_rejected(self):
        for change in (dict(posSide="long"), dict(tdMode="isolated"), dict(state="unknown"),
                       dict(accFillSz="3"), dict(instId="BTC-USD-SWAP"), dict(uTime="1.2")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                order(**change)

    def test_merge_duplicate_and_out_of_order(self):
        new = order(uTime="2000", accFillSz="2", state="filled")
        merged, issues = o.merge_orders([new, new, order()])
        self.assertEqual(merged, {"1": new})
        self.assertIn("out_of_order", issues)

    def test_same_timestamp_not_revision(self):
        _, issues = o.merge_orders([order(), order(accFillSz="2", state="filled")])
        self.assertIn("same_time_conflict", issues)

    def test_cumulative_regression_and_identity_conflict(self):
        _, issues = o.merge_orders([order(), order(uTime="2000", accFillSz="0", clOrdId="other")])
        self.assertEqual(issues, {"cumulative_regression", "order_identity_conflict"})

    def test_trade_ids_scoped_per_symbol_and_fee_signs(self):
        rows = [fill(), fill(), fill(instId="ETH-USDT-SWAP", ordId="2", fee="0.002")]
        quantities, fees = o.fill_totals(rows)
        self.assertEqual(quantities, {"1": D(1), "2": D(1)})
        self.assertEqual(fees, {"USDT": D("-.008")})

    def test_conflicting_fill_is_not_silently_deduped(self):
        with self.assertRaises(ValueError):
            o.fill_totals([fill(), fill(fee="-.02")])

    def test_partial_fill_audit_is_not_terminal_permission(self):
        issues, _ = o.reconcile([order()], [fill()], owned_order_ids={"1"},
                                unresolved_local_ids=set(), evidence_problems=set())
        self.assertEqual(issues, set())  # consistent partial evidence, not DONE.

    def test_foreign_missing_fills_and_local_unknown_preserved(self):
        issues, _ = o.reconcile([order()], [], owned_order_ids=set(),
                                unresolved_local_ids={"not-in-response"},
                                evidence_problems={"incomplete_coverage"})
        self.assertEqual(issues, {"foreign_order", "fill_gap", "local_unknown", "incomplete_coverage"})

    def test_terminal_quantity_and_orphan_fills(self):
        issues, _ = o.reconcile([order(state="filled")], [fill(), fill(ordId="2", tradeId="11")],
                                owned_order_ids={"1"}, unresolved_local_ids=set(), evidence_problems=set())
        self.assertEqual(issues, {"invalid_terminal", "orphan_fill"})

    def test_explicit_freshness_scope_and_missing_pages(self):
        e = o.Evidence("sub", "demo", "orders", "fixture-1", 1000, 1010, True)
        args = dict(account="sub", environment="demo", now_ms=1100, max_age_ms=200, max_skew_ms=50)
        self.assertFalse(o.evidence_issues([e], **args))
        self.assertEqual(o.evidence_issues([], **args), {"missing_evidence"})
        bad = replace(e, environment="live", source_ms=500, complete=False)
        self.assertEqual(o.evidence_issues([e, bad], **args),
                         {"scope_mismatch", "incomplete_coverage", "stale", "snapshot_skew"})
        self.assertIn("clock_mismatch", o.evidence_issues([replace(e, received_ms=1200)], **args))

    def test_whitelist_is_explicit_unknowns_preserved_and_deduped(self):
        a = dict(billId="1", type="fixture", subType="deposit", ccy="USDT", balChg="100")
        b = a | dict(billId="2", subType="withdraw", balChg="-20")
        c = a | dict(billId="3", subType="rebate", balChg="1")
        whitelist = {("fixture", "deposit"): "external", ("fixture", "withdraw"): "external"}
        self.assertEqual(o.external_flows([a, a, b, c], whitelist), (D(80), {"3"}))
        self.assertEqual(o.external_flows([a], {}), (D(0), {"1"}))

    def test_bill_conflict_rejected(self):
        a = dict(billId="1", type="fixture", subType="deposit", ccy="USDT", balChg="100")
        with self.assertRaises(ValueError):
            o.external_flows([a, a | dict(balChg="200")], {})


if __name__ == "__main__":
    unittest.main()
