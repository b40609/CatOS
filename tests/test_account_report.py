"""I-b-2 synthetic evidence only; no network, credentials or database."""

from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import unittest

from catos import account_report as r, okx_collection as c


def scope():
    return c.RunScope("okx-demo", "demo", "BTC-USDT-SWAP", 100, 200, 30, 5, 100, 5000)


def collect(data):
    class Transport:
        def fetch(self, request):
            return c.PageResponse("okx-demo", "demo", 200,
                                  {"code": "0", "data": data[request.endpoint.alias]})
    return c.collect_plan(c.CollectionPlan(scope(), tuple(data)), Transport())


def replace_endpoint(result, endpoint):
    return replace(result, manifest=replace(result.manifest, endpoint_manifests=tuple(
        endpoint if current.alias == endpoint.alias else current
        for current in result.manifest.endpoint_manifests)))


def collect_pages(data, alias, cursors):
    result = collect(data)
    template = next(p for p in result.pages if p.endpoint_alias == alias)
    endpoint = next(e for e in result.manifest.endpoint_manifests if e.alias == alias)
    pages, evidence = [], []
    for number, (request_cursor, next_cursor) in enumerate(cursors, 1):
        page = replace(template, page_number=number, request_cursor=request_cursor)
        pages.append(page)
        evidence.append(replace(endpoint.pages[0], page_number=number, request_cursor=request_cursor,
                                next_cursor=next_cursor,
                                digest=hashlib.sha256(page.payload_json.encode("utf-8")).hexdigest()))
    result = replace(result, pages=tuple(p for p in result.pages if p.endpoint_alias != alias) + tuple(pages))
    result = replace_endpoint(result, replace(endpoint, pages=tuple(evidence), requests=len(pages)))
    return replace(result, manifest=replace(result.manifest, requests=sum(
        e.requests for e in result.manifest.endpoint_manifests)))


def balance(**changes):
    return dict(totalEq="1001", adjEq="999", uTime="150", details=[dict(
        ccy="USDT", eq="1000", liab="0", availEq="900", ordFrozen="100", uTime="140")]) | changes


def position(**changes):
    row = dict(instType="SWAP", instId="BTC-USDT-SWAP", posId="secret-position",
               mgnMode="cross", posSide="net", pos="2", avgPx="123.1234567890123456789", uTime="150")
    return row | changes


def order(**changes):
    return dict(instType="SWAP", instId="BTC-USDT-SWAP", ordId="secret-order",
                tdMode="cross", posSide="net", side="buy", state="filled", sz="2",
                accFillSz="2", uTime="150") | changes


def fill(**changes):
    return dict(instId="BTC-USDT-SWAP", tradeId="secret-trade", ordId="secret-order",
                fillSz="2", fillPx="123", fee="-0.01", feeCcy="USDT", ts="150") | changes


def algo(**changes):
    return dict(instType="SWAP", instId="BTC-USDT-SWAP", algoId="secret-algo",
                state="effective", tdMode="cross", posSide="net", side="sell",
                ordType="conditional", uTime="150", closeFraction="1", slTriggerPx="100",
                slOrdPx="-1", slTriggerPxType="mark", reduceOnly=True,
                ordIdList=["secret-order"]) | changes


class AccountReportTests(unittest.TestCase):
    def report(self, data, **kwargs):
        return r.build_report(collect(data), scope=scope(), **kwargs)

    def test_decimal_and_missing_fields(self):
        f = r.decode_row("positions", position())
        self.assertEqual(f["avgPx"], Decimal("123.1234567890123456789"))
        for bad in (None, "", 1.5, "NaN", "Infinity"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                r.decode_row("positions", position(pos=bad))

    def test_flat_average_is_explicit_unknown(self):
        self.assertIsNone(r.decode_row("positions", position(pos="0", avgPx=""))["avgPx"])

    def test_foreign_position_and_quantity_mismatch(self):
        self.assertIn("foreign_position", self.report({"positions": [position()]})["discrepancies"])
        report = self.report({"positions": [position()]},
                             owned_positions={("BTC-USDT-SWAP", "secret-position"): Decimal(1)})
        self.assertIn("position_mismatch", report["discrepancies"])

    def test_config_preserves_subaccount_relation(self):
        row = dict(uid="secret-child", mainUid="secret-parent", acctLv="2",
                   posMode="net_mode", roleType="0", perm="read_only,trade", apiKey="DO-NOT-EXPORT")
        report = self.report({"account_config": [row]})
        self.assertTrue(report["facts"][0]["is_subaccount"])
        self.assertNotIn("secret-child", json.dumps(report))
        self.assertNotIn("DO-NOT-EXPORT", json.dumps(report))
        report = self.report({"account_config": [row | {"mainUid": "secret-child", "posMode": "long_short_mode"}]})
        self.assertIn("not_subaccount", report["discrepancies"])
        self.assertIn("mode_mismatch", report["discrepancies"])

    def test_balance_does_not_convert_usd(self):
        row = dict(totalEq="1001", adjEq="999", uTime="150", details=[dict(
            ccy="USDT", eq="1000", liab="0", availEq="900", ordFrozen="100", uTime="140")])
        f = self.report({"balance": [row]})["facts"][0]
        self.assertEqual((f["aggregate_currency"], f["totalEq"], f["details"][0]["eq"]), ("USD", "1001", "1000"))
        row["details"][0]["ccy"] = "BTC"
        self.assertIn("unsupported_collateral", self.report({"balance": [row]})["discrepancies"])

    def test_balance_field_diagnostics_are_fixed_and_private(self):
        cases = []
        for field in ("totalEq", "adjEq", "uTime", "details"):
            row = balance()
            del row[field]
            cases.append((row, field, "missing"))
        for field in ("totalEq", "adjEq"):
            for bad in ("PRIVATE-BAD-DECIMAL", "NaN", "Infinity", True):
                cases.append((balance(**{field: bad}), field, "invalid_decimal"))
        cases.extend((
            (balance(uTime="PRIVATE-BAD-TIME"), "uTime", "invalid_timestamp"),
            (balance(details=[]), "details", "missing"),
            (balance(details="PRIVATE-DETAILS"), "details", "invalid_structure"),
            (balance(details=["PRIVATE-DETAIL"]), "details[]", "invalid_structure"),
        ))
        for field in ("ccy", "uTime", "eq", "liab", "availEq", "ordFrozen"):
            row = balance()
            del row["details"][0][field]
            cases.append((row, "details[]." + field, "missing"))
        for field in ("eq", "liab", "availEq", "ordFrozen"):
            row = balance()
            row["details"][0][field] = "PRIVATE-DETAIL-DECIMAL"
            cases.append((row, "details[]." + field, "invalid_decimal"))
        row = balance()
        row["details"][0]["uTime"] = "PRIVATE-DETAIL-TIME"
        cases.append((row, "details[].uTime", "invalid_timestamp"))
        row = balance()
        row["details"][0]["ccy"] = "PRIVATE CURRENCY"
        cases.append((row, "details[].ccy", "invalid_text"))
        row = balance()
        row["details"][0]["ccy"] = "PRIVATE-CURRENCY"
        row["details"].append(dict(row["details"][0]))
        cases.append((row, "details[].ccy", "duplicate_currency"))
        for row, field, reason in cases:
            with self.subTest(field=field, reason=reason):
                row["uid"] = "PRIVATE-ACCOUNT-ID"
                row["extra"] = "PRIVATE-EXTRA"
                report = self.report({"balance": [row]})
                self.assertIn("invalid_record:balance", report["discrepancies"])
                self.assertEqual(report["record_diagnostics"], [{
                    "alias": "balance", "page": 1, "row": 0, "field": field, "reason": reason}])
                self.assertEqual(report["facts"], [])
                self.assertNotIn("PRIVATE", json.dumps(report))
                with self.assertRaisesRegex(ValueError, "^invalid balance field$"):
                    r.decode_row("balance", row)
        for field in ("totalEq", "adjEq"):
            with self.subTest(field=field, reason="float_rejected_by_decoder"):
                with self.assertRaisesRegex(r._BalanceFieldError, "^invalid balance field$") as caught:
                    r.decode_row("balance", balance(**{field: 1.5}))
                self.assertEqual(caught.exception.field, field)
                self.assertEqual(caught.exception.reason, "invalid_decimal")

    def test_balance_diagnostics_keep_page_and_row_coordinates(self):
        result = collect_pages({"balance": [balance()]}, "balance", ((None, "private-cursor"), ("private-cursor", None)))
        payload = json.dumps({"code": "0", "data": [balance(), balance(adjEq="PRIVATE-VALUE")]})
        page = replace(result.pages[1], payload_json=payload)
        endpoint = result.manifest.endpoint_manifests[0]
        evidence = replace(endpoint.pages[1], digest=hashlib.sha256(payload.encode("utf-8")).hexdigest())
        result = replace_endpoint(replace(result, pages=(result.pages[0], page)),
                                  replace(endpoint, pages=(endpoint.pages[0], evidence)))
        report = r.build_report(result, scope=scope())
        self.assertEqual(report["record_diagnostics"], [{
            "alias": "balance", "page": 2, "row": 1, "field": "adjEq", "reason": "invalid_decimal"}])
        self.assertIn("invalid_record:balance", report["discrepancies"])
        self.assertNotIn("PRIVATE-VALUE", json.dumps(report))
        self.assertNotIn("private-cursor", json.dumps(report))

    def test_record_diagnostics_default_empty_for_valid_and_other_sources(self):
        for data in ({"balance": [balance()]}, {"positions": []}, {"fills": [fill(fee="PRIVATE-FEE")]}):
            with self.subTest(alias=next(iter(data))):
                self.assertEqual(self.report(data)["record_diagnostics"], [])

    def test_fee_sign_dedup_and_order_link(self):
        report = self.report({"fills": [fill(), fill()], "fills_history": [fill()],
                              "order": [order()]}, owned_order_ids={"secret-order"})
        self.assertEqual(report["observed_signed_fees_by_currency"], {"USDT": "-0.01"})
        self.assertNotIn("fill_window_gap", report["discrepancies"])
        fs = [f for f in report["facts"] if f["kind"] == "fill"]
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0]["source"], {"alias": "fills", "page": 1, "row": 0})
        self.assertEqual(fs[0]["observations"], [
            {"alias": "fills", "page": 1, "row": 0},
            {"alias": "fills", "page": 1, "row": 1},
            {"alias": "fills_history", "page": 1, "row": 0},
        ])
        self.assertEqual(fs[0]["ordId"], next(f for f in report["facts"] if f["kind"] == "order")["ordId"])
        self.assertEqual(self.report({"fills": [fill(fee="0.02")]})["observed_signed_fees_by_currency"], {"USDT": "0.02"})

    def test_conflicting_duplicate_withholds_totals(self):
        report = self.report({"fills": [fill(), fill(fee="-0.02")]})
        self.assertIn("conflicting_observation:fill", report["discrepancies"])
        self.assertIsNone(report["observed_signed_fees_by_currency"])
        fs = [f for f in report["facts"] if f["kind"] == "fill"]
        self.assertEqual(len(fs), 2)
        self.assertEqual([f["fee"] for f in fs], ["-0.01", "-0.02"])
        for index, fact in enumerate(fs):
            source = {"alias": "fills", "page": 1, "row": index}
            self.assertEqual(fact["source"], source)
            self.assertEqual(fact["observations"], [source])
        self.assertFalse(report["reconciled"])
        self.assertFalse(report["trade_authorized"])

    def test_a_b_a_versions_keep_separate_sources_for_all_identity_kinds(self):
        bill = dict(billId="secret-bill", type="fixture", subType="deposit",
                    ccy="USDT", balChg="10", ts="150")
        cases = (
            ("fills", "fill", fill(), fill(fee="-0.02")),
            ("orders_history", "order", order(), order(state="canceled")),
            ("positions", "positions", position(), position(pos="3")),
            ("bills", "bill", bill, bill | {"balChg": "20"}),
            ("algo_history", "algo", algo(), algo(slTriggerPx="110")),
        )
        for alias, kind, a, b in cases:
            with self.subTest(kind=kind):
                report = self.report({alias: [a, b, dict(a)]})
                fs = [f for f in report["facts"] if f["kind"] == kind]
                self.assertEqual(len(fs), 2)
                expected = [{"alias": alias, "page": 1, "row": index} for index in range(3)]
                self.assertEqual(fs[0]["source"], expected[0])
                self.assertEqual(fs[0]["observations"], [expected[0], expected[2]])
                self.assertEqual(fs[1]["source"], expected[1])
                self.assertEqual(fs[1]["observations"], [expected[1]])
                self.assertIn("conflicting_observation:" + kind, report["discrepancies"])
                self.assertFalse(report["reconciled"])
                self.assertFalse(report["trade_authorized"])
                if kind == "fill":
                    self.assertIsNone(report["observed_signed_fees_by_currency"])
                if kind == "bill":
                    self.assertIsNone(report["observed_external_flow_usdt"])

    def test_returning_version_merges_across_sources_without_losing_conflict(self):
        report = self.report({"fills": [fill()], "fills_history": [fill(fee="-0.02"), fill()]})
        fs = [f for f in report["facts"] if f["kind"] == "fill"]
        self.assertEqual(len(fs), 2)
        self.assertEqual(fs[0]["observations"], [
            {"alias": "fills", "page": 1, "row": 0},
            {"alias": "fills_history", "page": 1, "row": 1},
        ])
        self.assertEqual(fs[1]["observations"], [{"alias": "fills_history", "page": 1, "row": 0}])
        self.assertEqual(fs[0]["tradeId"], fs[1]["tradeId"])
        self.assertEqual(fs[0]["ordId"], fs[1]["ordId"])
        self.assertIn("conflicting_observation:fill", report["discrepancies"])
        self.assertIsNone(report["observed_signed_fees_by_currency"])
        for private in ("secret-trade", "secret-order"):
            self.assertNotIn(private, json.dumps(report))

    def test_equivalent_decimal_values_still_share_one_version(self):
        report = self.report({"fills": [fill(), fill(fee="-0.0100")]})
        fs = [f for f in report["facts"] if f["kind"] == "fill"]
        self.assertEqual(len(fs), 1)
        self.assertEqual(len(fs[0]["observations"]), 2)
        self.assertNotIn("conflicting_observation:fill", report["discrepancies"])
        self.assertEqual(report["observed_signed_fees_by_currency"], {"USDT": "-0.01"})

    def test_fill_identity_keeps_distinct_trades_and_instruments_separate(self):
        report = self.report({"fills": [fill(), fill(tradeId="other-trade"),
                                       fill(instId="ETH-USDT-SWAP")]})
        fs = [f for f in report["facts"] if f["kind"] == "fill"]
        self.assertEqual(len(fs), 3)
        for index, fact in enumerate(fs):
            self.assertEqual(fact["observations"], [{"alias": "fills", "page": 1, "row": index}])
        self.assertNotIn("conflicting_observation:fill", report["discrepancies"])
        self.assertIn("instrument_scope_mismatch", report["discrepancies"])

    def test_invalid_fill_never_becomes_zero_total(self):
        report = self.report({"fills": [fill(fee="")]})
        self.assertIn("invalid_record:fills", report["discrepancies"])
        self.assertIsNone(report["observed_signed_fees_by_currency"])

    def test_window_endpoints_and_outside(self):
        for ts in ("100", "200"):
            self.assertNotIn("outside_window:fill", self.report({"fills": [fill(ts=ts)]})["discrepancies"])
        report = self.report({"fills": [fill(ts="201")]})
        self.assertIn("outside_window:fill", report["discrepancies"])
        self.assertIsNone(report["observed_signed_fees_by_currency"])

    def test_order_update_time_is_not_event_window(self):
        report = self.report({"order": [order(uTime="1", tdMode="isolated")]})
        self.assertIn("mode_mismatch", report["discrepancies"])
        self.assertIn("foreign_order", report["discrepancies"])

    def test_bill_whitelist_and_duplicate(self):
        bill = dict(billId="secret-bill", type="fixture", subType="deposit", ccy="USDT", balChg="10", ts="150")
        self.assertIsNone(self.report({"bills": [bill]})["observed_external_flow_usdt"])
        report = self.report({"bills": [bill, bill]}, classifications={("fixture", "deposit"): "external"})
        self.assertEqual(report["observed_external_flow_usdt"], "10")
        report = self.report({"bills": [bill, bill | {"balChg": "20"}]})
        self.assertIsNone(report["observed_external_flow_usdt"])

    def test_p6_effective_does_not_close_and_children_link(self):
        report = self.report({"algo_history": [algo()], "order": [order()]})
        self.assertIn("p6_triggered_not_reconciled", report["discrepancies"])
        self.assertNotIn("p6_child_order_gap", report["discrepancies"])
        self.assertEqual(report["facts"][0]["ordIdList"], [report["facts"][1]["ordId"]])
        self.assertFalse(report["trade_authorized"])
        self.assertFalse(report["reconciled"])
        report = self.report({"algo_history": [algo(ordIdList=[])]})
        self.assertIn("p6_child_order_gap", report["discrepancies"])

    def test_p6_missing_protection_parameters(self):
        report = self.report({"algo_pending": [algo(state="live", slTriggerPx="")]})
        self.assertIn("p6_protection_unverified", report["discrepancies"])

    def test_algo_reduce_only_accepts_documented_string_boolean_only(self):
        self.assertTrue(r.decode_row("algo_pending", algo(reduceOnly="true"))["reduceOnly"])
        self.assertFalse(r.decode_row("algo_pending", algo(reduceOnly="false"))["reduceOnly"])
        for bad in ("True", "0", 0, 1, None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                r.decode_row("algo_pending", algo(reduceOnly=bad))

    def test_local_unknown_and_missing_source_survive_empty_pages(self):
        report = self.report({"positions": []}, unresolved_local_ids={"secret-local"})
        self.assertTrue(report["collection_complete"])
        self.assertIn("local_unknown", report["discrepancies"])
        self.assertIn("missing_governance_source", report["discrepancies"])
        self.assertIsNone(report["observed_external_flow_usdt"])

    def test_scope_mismatch_rejected(self):
        result = collect({"positions": []})
        with self.assertRaisesRegex(ValueError, "scope_mismatch"):
            r.build_report(result, scope=replace(scope(), account_alias="other"))

    def test_tamper_and_missing_page(self):
        result = collect({"positions": [position()]})
        report = r.build_report(replace(result, pages=()), scope=scope())
        self.assertIn("page_evidence_gap", report["discrepancies"])
        self.assertFalse(report["collection_complete"])
        page = replace(result.pages[0], payload_json='{"code":"0","data":[]}')
        report = r.build_report(replace(result, pages=(page,)), scope=scope())
        self.assertIn("page_evidence_mismatch", report["discrepancies"])

    def event_chain(self, cursors=((None, "private-cursor"), ("private-cursor", None))):
        bill = dict(billId="secret-bill", type="fixture", subType="deposit", ccy="USDT", balChg="10", ts="150")
        return collect_pages({"fills": [fill()], "bills": [bill]}, "fills", cursors)

    def chain_report(self, result):
        return r.build_report(result, scope=scope(), classifications={("fixture", "deposit"): "external"})

    def assert_collection_unavailable(self, report, code):
        self.assertIn(code, report["discrepancies"])
        self.assertFalse(report["collection_complete"])
        self.assertIsNone(report["observed_signed_fees_by_currency"])
        self.assertIsNone(report["observed_external_flow_usdt"])
        self.assertIn("fill_totals_unavailable", report["discrepancies"])
        self.assertIn("external_flow_unavailable", report["discrepancies"])
        for private in ("private-cursor", "private-other", "secret-order", "secret-trade", "secret-bill"):
            self.assertNotIn(private, json.dumps(report))

    def test_page_chain_rejects_first_cursor_disconnect_terminal_and_cycles(self):
        cases = (
            (("private-cursor", None),),
            ((None, "private-cursor"), ("private-other", None)),
            ((None, None), (None, None)),
            ((None, None), ("private-cursor", None)),
            ((None, "private-cursor"), ("private-cursor", "private-cursor")),
            ((None, "private-cursor"), ("private-cursor", "private-other"),
             ("private-other", "private-cursor")),
        )
        for cursors in cases:
            for complete in (True, False):
                with self.subTest(cursors=cursors, complete=complete):
                    result = self.event_chain(cursors)
                    if not complete:
                        result = replace_endpoint(result, replace(result.manifest.endpoint_manifests[0],
                                                                  complete=False, issue="PRIVATE-ISSUE"))
                        result = replace(result, manifest=replace(result.manifest, complete=False))
                    report = self.chain_report(result)
                    self.assert_collection_unavailable(report, "page_chain_invalid")
                    self.assertNotIn("PRIVATE-ISSUE", json.dumps(report))

    def test_page_chain_rejects_invalid_cursor_types_and_empty_text(self):
        for bad in ("", 1, False, [], {"PRIVATE": "CURSOR"}):
            for field in ("request_cursor", "next_cursor"):
                with self.subTest(field=field, bad=bad):
                    result = self.event_chain(((None, None),))
                    endpoint = result.manifest.endpoint_manifests[0]
                    endpoint = replace(endpoint, pages=(replace(endpoint.pages[0], **{field: bad}),))
                    report = self.chain_report(replace_endpoint(result, endpoint))
                    self.assert_collection_unavailable(report, "page_chain_invalid")
                    self.assertNotIn("PRIVATE", json.dumps(report))

    def test_page_chain_rejects_nonstarting_missing_repeated_and_reordered_evidence(self):
        result = self.event_chain()
        endpoint = result.manifest.endpoint_manifests[0]
        first, second = endpoint.pages
        cases = (
            ((replace(first, page_number=2), replace(second, page_number=3)), (2, 3)),
            ((first, replace(second, page_number=3)), (1, 3)),
            ((first, first, second), (1, 2)),
            ((second, first), (1, 2)),
        )
        collected = tuple(p for p in result.pages if p.endpoint_alias == "fills")
        for evidence, numbers in cases:
            with self.subTest(numbers=[ev.page_number for ev in evidence]):
                pages = tuple(p for p in result.pages if p.endpoint_alias != "fills") + tuple(
                    replace(page, page_number=number) for page, number in zip(collected, numbers))
                changed = replace_endpoint(replace(result, pages=pages), replace(endpoint, pages=evidence))
                report = self.chain_report(changed)
                self.assert_collection_unavailable(report, "page_chain_invalid")
                self.assertNotIn("page_evidence_gap", report["discrepancies"])
                self.assertNotIn("page_evidence_mismatch", report["discrepancies"])

    def test_page_chain_requires_actual_positive_integer_evidence_numbers(self):
        for bad in (True, False, 0, -1, 1.0, "1", None, [], {"PRIVATE": "PAGE"}):
            with self.subTest(bad=bad):
                result = self.event_chain(((None, None),))
                endpoint = result.manifest.endpoint_manifests[0]
                endpoint = replace(endpoint, pages=(replace(endpoint.pages[0], page_number=bad),))
                report = self.chain_report(replace_endpoint(result, endpoint))
                self.assert_collection_unavailable(report, "page_chain_invalid")
                self.assertNotIn("PRIVATE", json.dumps(report))

    def test_page_chain_requires_actual_positive_integer_collected_numbers(self):
        for bad in (True, False, 0, -1, 1.0, "1", None, [], {"PRIVATE": "PAGE"}):
            with self.subTest(bad=bad):
                result = self.event_chain(((None, None),))
                result = replace(result, pages=tuple(replace(p, page_number=bad) if p.endpoint_alias == "fills" else p
                                                     for p in result.pages))
                report = self.chain_report(result)
                self.assert_collection_unavailable(report, "page_chain_invalid")
                self.assertNotIn("PRIVATE", json.dumps(report))

    def test_duplicate_collected_page_keeps_existing_exception(self):
        result = self.event_chain()
        with self.assertRaisesRegex(ValueError, "^duplicate_page$"):
            self.chain_report(replace(result, pages=result.pages + (result.pages[0],)))

    def test_duplicate_evidence_is_not_decoded_twice(self):
        result = self.event_chain()
        endpoint = result.manifest.endpoint_manifests[0]
        endpoint = replace(endpoint, pages=(endpoint.pages[0], endpoint.pages[0], endpoint.pages[1]))
        report = self.chain_report(replace_endpoint(result, endpoint))
        self.assert_collection_unavailable(report, "page_chain_invalid")
        facts = [f for f in report["facts"] if f["kind"] == "fill"]
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["observations"], [
            {"alias": "fills", "page": 1, "row": 0}, {"alias": "fills", "page": 2, "row": 0}])

    def test_complete_requires_page_terminal_cursor_and_no_issue(self):
        for cursors, issue in (((), ""), (((None, "private-cursor"),), ""), (((None, None),), "PRIVATE-ISSUE")):
            with self.subTest(cursors=cursors, issue=issue):
                result = self.event_chain(cursors)
                endpoint = replace(result.manifest.endpoint_manifests[0], issue=issue)
                report = self.chain_report(replace_endpoint(result, endpoint))
                self.assert_collection_unavailable(report, "manifest_completion_mismatch")
                self.assertNotIn("PRIVATE-ISSUE", json.dumps(report))

    def test_batch_and_source_completion_flags_must_agree(self):
        for batch_complete, source_complete in ((True, False), (False, True)):
            with self.subTest(batch_complete=batch_complete, source_complete=source_complete):
                result = self.event_chain()
                result = replace_endpoint(result, replace(result.manifest.endpoint_manifests[0], complete=source_complete))
                result = replace(result, manifest=replace(result.manifest, complete=batch_complete))
                self.assert_collection_unavailable(self.chain_report(result), "manifest_completion_mismatch")

    def test_incomplete_prefix_allows_zero_pages_and_either_final_cursor(self):
        cases = ((), ((None, "private-cursor"),), ((None, None),),
                 ((None, "private-cursor"), ("private-cursor", "private-other")),
                 ((None, "private-cursor"), ("private-cursor", None)))
        for cursors in cases:
            with self.subTest(cursors=cursors):
                result = self.event_chain(cursors)
                result = replace(result, manifest=replace(result.manifest, complete=False, endpoint_manifests=tuple(
                    replace(endpoint, complete=False, issue="PRIVATE-ISSUE")
                    for endpoint in result.manifest.endpoint_manifests)))
                report = self.chain_report(result)
                self.assertIn("incomplete_collection", report["discrepancies"])
                self.assertFalse(report["collection_complete"])
                self.assertFalse(report["reconciled"])
                self.assertFalse(report["trade_authorized"])
                self.assertEqual(report["observed_signed_fees_by_currency"], {"USDT": "-0.01"} if cursors else {})
                self.assertEqual(report["observed_external_flow_usdt"], "10")
                self.assertNotIn("fill_totals_unavailable", report["discrepancies"])
                self.assertNotIn("external_flow_unavailable", report["discrepancies"])
                self.assertNotIn("page_chain_invalid", report["discrepancies"])
                self.assertNotIn("manifest_completion_mismatch", report["discrepancies"])
                self.assertNotIn("page_evidence_gap", report["discrepancies"])
                self.assertNotIn("PRIVATE-ISSUE", json.dumps(report))

    def test_opaque_cursors_and_retry_request_counts_remain_valid(self):
        first, second = ' private-cursor:["a", 1] /?= ', 'private-cursor:["a", 1] /?='
        result = self.event_chain(((None, first), (first, second), (second, None)))
        endpoint = result.manifest.endpoint_manifests[0]
        result = replace_endpoint(result, replace(endpoint, requests=endpoint.requests + 3))
        result = replace(result, manifest=replace(result.manifest, requests=result.manifest.requests + 3))
        report = self.chain_report(result)
        self.assertTrue(report["collection_complete"])
        self.assertNotIn("page_chain_invalid", report["discrepancies"])
        self.assertEqual(report["observed_signed_fees_by_currency"], {"USDT": "-0.01"})
        self.assertEqual(report["observed_external_flow_usdt"], "10")
        self.assertEqual(report["sources"][0]["requests"], 6)
        self.assertNotIn("private-cursor", json.dumps(report))

    def test_balance_supports_multiple_nonempty_pages(self):
        result = collect_pages({"balance": [balance()]}, "balance", ((None, "private-cursor"), ("private-cursor", None)))
        report = r.build_report(result, scope=scope())
        self.assertTrue(report["collection_complete"])
        self.assertNotIn("page_chain_invalid", report["discrepancies"])
        self.assertNotIn("manifest_completion_mismatch", report["discrepancies"])
        self.assertEqual(len(report["facts"]), 2)

    def test_evidence_integrity_errors_withhold_both_event_totals(self):
        for mode, code in (("missing", "page_evidence_gap"), ("digest", "page_evidence_mismatch"),
                           ("request", "page_evidence_mismatch"), ("malformed", "malformed_page")):
            with self.subTest(mode=mode):
                result = self.event_chain(((None, None),))
                page = next(p for p in result.pages if p.endpoint_alias == "fills")
                if mode == "missing":
                    result = replace(result, pages=tuple(p for p in result.pages if p.endpoint_alias != "fills"))
                else:
                    if mode == "request":
                        page = replace(page, request_cursor="private-other")
                    else:
                        page = replace(page, payload_json="PRIVATE-MALFORMED-JSON")
                    result = replace(result, pages=tuple(page if p.endpoint_alias == "fills" else p for p in result.pages))
                    if mode == "malformed":
                        endpoint = result.manifest.endpoint_manifests[0]
                        ev = replace(endpoint.pages[0], digest=hashlib.sha256(page.payload_json.encode("utf-8")).hexdigest())
                        result = replace_endpoint(result, replace(endpoint, pages=(ev,)))
                report = self.chain_report(result)
                self.assert_collection_unavailable(report, code)
                self.assertNotIn("PRIVATE-MALFORMED-JSON", json.dumps(report))

    def test_incomplete_and_custom_error_are_sanitized(self):
        result = collect({"positions": []})
        endpoint = replace(result.manifest.endpoint_manifests[0], complete=False, issue="PRIVATE-ERROR-BODY")
        result = replace(result, manifest=replace(result.manifest, complete=False, endpoint_manifests=(endpoint,)))
        report = r.build_report(result, scope=scope())
        self.assertIn("incomplete_collection", report["discrepancies"])
        self.assertNotIn("PRIVATE-ERROR-BODY", json.dumps(report))

    def test_instrument_and_public_reference_decoders(self):
        row = dict(instType="SWAP", instId="BTC-USDT-SWAP", ctType="linear", settleCcy="USDT",
                   ctValCcy="BTC", state="live", ctVal="0.01", ctMult="1", tickSz="0.1", lotSz="1", minSz="1")
        report = self.report({"account_instruments": [row], "public_instruments": [row],
                              "public_time": [{"ts": "150"}], "mark_price": [dict(
                                  instType="SWAP", instId="BTC-USDT-SWAP", markPx="120", ts="150")]})
        self.assertNotIn("unsupported_contract", report["discrepancies"])
        self.assertEqual(len(report["facts"]), 4)


if __name__ == "__main__":
    unittest.main()
