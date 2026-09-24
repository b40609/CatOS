"""Synthetic public-schema fixtures only; no recorded account data."""
from dataclasses import replace
from decimal import Decimal as D, localcontext
import unittest
import hashlib
import json
from pathlib import Path

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

        versioned = o.FlowClassification("synthetic-flow-map", (
            o.FlowClassificationEntry("fixture", "deposit", "external", "synthetic evidence"),
            o.FlowClassificationEntry("fixture", "withdraw", "external", "synthetic evidence"),
        ))
        self.assertEqual(o.flow_classification_id(versioned), versioned.classification_id)
        self.assertTrue(versioned.classification_id.startswith("synthetic-flow-map:"))
        self.assertEqual(o.external_flows([a, b, c], versioned), (D(80), {"3"}))
        self.assertEqual(dict(versioned.mapping()), whitelist)

    def test_static_okx_transfer_mapping_is_partial_and_explicit(self):
        mapping = dict(o.OKX_STATIC_TRANSFER_FLOW_CLASSIFICATION.mapping())
        self.assertEqual(mapping, {("1", "11"): "external", ("1", "12"): "external"})
        self.assertFalse(o.OKX_STATIC_TRANSFER_FLOW_CLASSIFICATION.complete)
        self.assertTrue(o.OKX_STATIC_TRANSFER_FLOW_CLASSIFICATION.classification_id.startswith(
            "okx-v5-static-transfer-2026-09-21:"))
        unknown = dict(billId="1", type="1", subType="999", ccy="USDT", balChg="1")
        self.assertEqual(
            o.external_flows([unknown], o.OKX_STATIC_TRANSFER_FLOW_CLASSIFICATION),
            (D(0), {"1"}),
        )

    def test_demo_catalog_mapping_preserves_ambiguous_and_disabled_unknowns(self):
        classification = o.OKX_DEMO_CATALOG_FLOW_CLASSIFICATION
        catalog = json.loads((Path(__file__).resolve().parents[1] /
            "docs/evidence/okx-demo-subtypes-20260922.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256(json.dumps(catalog, sort_keys=True,
            separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        self.assertEqual(digest, "84373423204fe2ccf65955ba096e11687e96879caf436d00efcf5af030506e4c")
        labels = {(row["type"], sub["subType"]): row["typeDesc"] + " / " + sub["subTypeDesc"]
                  for row in catalog for sub in row["subTypeDetails"]}
        self.assertEqual(len(labels), 185)
        self.assertFalse(classification.complete)
        self.assertEqual(len(classification.entries), 166)
        for pair in (("1", "292"), ("1", "290"), ("22", "259"), ("37", "421")):
            bill = dict(billId="unknown", type=pair[0], subType=pair[1],
                        ccy="USDT", balChg="1")
            self.assertEqual(o.external_flows([bill], classification), (D(0), {"unknown"}))
        for entry in classification.entries:
            self.assertIn("84373423204fe2cc", entry.evidence)
            self.assertIn(labels[(entry.bill_type, entry.sub_type)], entry.evidence)
        self.assertEqual(classification.mapping()[("8", "173")], "internal")
        self.assertEqual(classification.mapping()[("5", "104")], "internal")
        self.assertEqual(classification.mapping()[("27", "318")], "internal")
        self.assertEqual(classification.mapping()[("1", "288")], "external")
        self.assertEqual(classification.mapping()[("7", "295")], "internal")
        self.assertEqual(classification.mapping()[("12", "200")], "forbidden")
        self.assertEqual(classification.mapping()[("13", "131")], "internal")
        self.assertEqual(classification.mapping()[("4", "114")], "internal")
        self.assertEqual(classification.mapping()[("16", "306")], "internal")
        self.assertEqual(classification.mapping()[("29", "224")], "internal")
        self.assertEqual(classification.mapping()[("1", "420")], "forbidden")
        self.assertEqual(classification.mapping()[("6", "160")], "forbidden")
        self.assertEqual(classification.mapping()[("15", "210")], "forbidden")
        self.assertEqual(classification.mapping()[("4", "312")], "internal")
        self.assertEqual(classification.mapping()[("4", "376")], "internal")
        self.assertEqual(classification.mapping()[("4", "377")], "internal")
        self.assertEqual(classification.mapping()[("5", "313")], "internal")
        self.assertEqual(classification.mapping()[("5", "317")], "internal")
        self.assertEqual(classification.mapping()[("6", "332")], "forbidden")
        self.assertEqual(classification.mapping()[("6", "334")], "forbidden")
        self.assertEqual(classification.mapping()[("33", "348")], "internal")
        self.assertEqual(classification.mapping()[("33", "349")], "internal")
        self.assertEqual(classification.mapping()[("33", "356")], "internal")
        self.assertEqual(classification.mapping()[("33", "357")], "external")
        self.assertEqual(classification.mapping()[("33", "358")], "external")
        self.assertEqual(classification.mapping()[("33", "359")], "external")
        self.assertEqual(classification.mapping()[("24", "274")], "internal")
        self.assertEqual(classification.mapping()[("24", "275")], "internal")
        self.assertEqual(classification.mapping()[("37", "422")], "internal")
        self.assertEqual(classification.mapping()[("37", "427")], "internal")

    def test_forbidden_flows_are_distinct_deduped_and_never_offset_external(self):
        classification = o.FlowClassification("synthetic-policy", (
            o.FlowClassificationEntry("fixture", "blocked", "forbidden", "synthetic evidence"),
            o.FlowClassificationEntry("fixture", "capital", "external", "synthetic evidence"),
        ), True)
        for ccy in ("USDT", "BTC"):
            for amount in ("0", "10", "-10"):
                bill = dict(billId="blocked", type="fixture", subType="blocked", ccy=ccy, balChg=amount)
                capital = bill | dict(billId="capital", subType="capital", ccy="USDT", balChg="20")
                unknown = bill | dict(billId="unknown", subType="unmapped")
                self.assertEqual(o.classify_bill_flows([bill, bill, capital, unknown], classification),
                                 (D(20), {"unknown"}, {"blocked"}))
                self.assertEqual(o.external_flows([bill], classification), (D(0), {"blocked"}))
                with self.assertRaises(ValueError):
                    o.classify_bill_flows([bill, bill | dict(balChg="999")], classification)
        self.assertEqual(o.classify_bill_flows([], classification), (D(0), set(), set()))

    def test_bill_conflict_rejected(self):
        a = dict(billId="1", type="fixture", subType="deposit", ccy="USDT", balChg="100")
        with self.assertRaises(ValueError):
            o.external_flows([a, a | dict(balChg="200")], {})

    def test_versioned_flow_classification_rejects_duplicate_keys(self):
        entry = o.FlowClassificationEntry("1", "11", "external", "synthetic evidence")
        with self.assertRaises(ValueError):
            o.FlowClassification("duplicate", (entry, entry))

    def test_flow_classification_id_binds_mapping_and_evidence(self):
        base = o.FlowClassification("same-name", (
            o.FlowClassificationEntry("1", "11", "external", "evidence-a"),
        ))
        changed_mapping = o.FlowClassification("same-name", (
            o.FlowClassificationEntry("1", "11", "internal", "evidence-a"),
        ))
        changed_evidence = o.FlowClassification("same-name", (
            o.FlowClassificationEntry("1", "11", "external", "evidence-b"),
        ))
        complete = o.FlowClassification("same-name", (
            o.FlowClassificationEntry("1", "11", "external", "evidence-a"),
        ), True)
        self.assertNotEqual(base.classification_id, changed_mapping.classification_id)
        self.assertNotEqual(base.classification_id, changed_evidence.classification_id)
        self.assertNotEqual(base.classification_id, complete.classification_id)


if __name__ == "__main__":
    unittest.main()
