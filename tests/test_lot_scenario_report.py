"""S7 presentation contracts; real S6 results plus explicit defensive stubs."""

from contextlib import ExitStack
from dataclasses import fields, replace
from decimal import Decimal as D, Inexact, localcontext
from html.parser import HTMLParser
from pathlib import Path
import io
import os
import socket
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from catos import lot_exposure, lot_scenario, lot_scenario_report as rendering, lots
from catos.journal import Journal
from catos.lot_journal import StoredLot
from lot_journal_helpers import contract, scope, snapshot
from lot_fill_helpers import opening, fill, terminal, close_order
from test_lot_scenario import capture, evidence, pending


class Document(HTMLParser):
    """Read row values independently of renderer formatting helpers."""
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.rows, self.tags, self.text, self.keys = {}, [], [], []
        self.key, self.cell, self.cells = None, None, []
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == "tr":
            self.key, self.cells = attrs.get("data-field"), []
        if tag == "td" and self.key is not None:
            self.cell = []

    def handle_data(self, data):
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None:
            self.cells.append("".join(self.cell))
            self.cell = None
        if tag == "tr" and self.key is not None:
            self.keys.append(self.key)
            self.rows[self.key] = tuple(self.cells)
            self.key = None


def expected(value, missing="不可用"):
    if value is None:
        return missing
    if type(value) is bool:
        return "是（true）" if value else "否（false）"
    if isinstance(value, D):
        return "0" if value.is_zero() else f"{value:f}"
    return str(value)


class LotScenarioReportTests(unittest.TestCase):
    def render(self, value=None, scene=None, now=100):
        value = capture() if value is None else value
        scene = evidence(value) if scene is None else scene
        return rendering.render_synthetic_scenario_report(capture=value, scenario=scene, now_ms=now)

    def check_report(self, value, scene=None, now=100):
        scene = evidence(value) if scene is None else scene
        result = lot_scenario.observe_synthetic_scenario(capture=value, scenario=scene, now_ms=now)
        document = Document(self.render(value, scene, now))
        report = result.report
        for field in fields(report):
            key = field.name
            if key in ("scope", "contract", "reasons", "comparison_status"):
                continue
            with self.subTest(field=key):
                missing = "未提供" if key in ("quote_id", "pending_cut_id") else "不可用"
                self.assertEqual(document.rows[key][0], expected(getattr(report, key), missing))
        for parent in ("scope", "contract"):
            for field in fields(getattr(report, parent)):
                self.assertEqual(document.rows[parent + "." + field.name][0],
                                 expected(getattr(getattr(report, parent), field.name)))
        self.assertIn(report.comparison_status, document.rows["comparison_status"][0])
        for reason in report.reasons:
            self.assertIn(reason, document.text)
        self.assertEqual(len(document.keys), len(set(document.keys)))
        return document

    def test_a01_all_fields_identity_metadata_and_units(self):
        value = capture((StoredLot(snapshot(), False, False, 1),))
        scene = evidence(value, physical_quantity=D(2))
        doc = self.check_report(value, scene)
        extras = {
            "observation.evidence_kind": "SYNTHETIC_SCENARIO", "capture.source": value.source,
            "scenario.source": scene.source, "source_capture_id": value.capture_id,
            "scenario_cut_id": scene.scenario_cut_id, "capture.observed_at_ms": "90",
            "capture.valid_until_ms": "110", "scenario.physical_observed_at_ms": "91",
            "scenario.physical_valid_until_ms": "111", "scenario.mark_observed_at_ms": "92",
            "scenario.mark_valid_until_ms": "112", "scenario.mark": "100",
        }
        for key, value in extras.items():
            self.assertEqual(doc.rows[key][0], value)
        for key, cells in doc.rows.items():
            if key.endswith("_qty"):
                self.assertEqual(cells[1], "張")
            if key.endswith("_notional"):
                self.assertEqual(cells[1], "USDT")
        self.assertEqual(doc.rows["contract.base_per_contract"][1], "標的資產／張")
        self.assertEqual(doc.rows["scenario.mark"][1], "USDT／標的資產")

    def test_a02_three_comparison_states(self):
        value = capture()
        for changes, label in (({}, "合成情境數量相符（MATCH）"),
                               ({"physical_quantity": D(1)}, "合成情境數量不符（MISMATCH）"),
                               ({"physical_complete": False}, "無法比較（UNAVAILABLE）")):
            doc = self.check_report(value, evidence(value, **changes))
            self.assertEqual(doc.rows["comparison_status"][0], label)
            self.assertIn("不是交易所證據或交易許可", "".join(doc.text))

    def test_a03_exactly_one_real_s6_and_s4_call(self):
        value, now = capture(), 100
        scene = evidence(value)
        with patch.object(lot_scenario, "observe_synthetic_scenario", wraps=lot_scenario.observe_synthetic_scenario) as s6:
            with patch.object(lot_exposure, "observe_exposure", wraps=lot_exposure.observe_exposure) as s4:
                self.render(value, scene, now)
        s6.assert_called_once_with(capture=value, scenario=scene, now_ms=now)
        self.assertIs(s6.call_args.kwargs["capture"], value)
        self.assertIs(s6.call_args.kwargs["scenario"], scene)
        s4.assert_called_once()

    def test_a04_determinism_immutability_and_decimal_context(self):
        value = capture(pending=(pending(),))
        scene = evidence(value)
        before = repr((value, scene))
        normal = self.render(value, scene)
        with localcontext() as ctx:
            ctx.prec = 2
            ctx.flags[Inexact] = True
            saved = (ctx.prec, ctx.rounding, ctx.Emin, ctx.Emax, dict(ctx.flags), dict(ctx.traps))
            self.assertEqual(self.render(value, scene), normal)
            self.assertEqual(self.render(value, scene), normal)
            self.assertEqual(saved, (ctx.prec, ctx.rounding, ctx.Emin, ctx.Emax, dict(ctx.flags), dict(ctx.traps)))
        self.assertEqual(repr((value, scene)), before)

    def test_b01_missing_mark_is_not_zero(self):
        value = capture()
        scene = evidence(value, mark=None, mark_quote_id=None, mark_observed_at_ms=None, mark_valid_until_ms=None)
        doc = self.check_report(value, scene)
        for key in ("quote_id", "scenario.mark", "scenario.mark_observed_at_ms", "scenario.mark_valid_until_ms"):
            self.assertEqual(doc.rows[key][0], "未提供")
        self.assertEqual(doc.rows["observed_gross_notional"][0], "不可用")
        self.assertEqual(doc.rows["observed_gross_qty"][0], "0")
        self.assertIn("MATCH", doc.rows["comparison_status"][0])

    def test_b02_missing_or_unverified_physical(self):
        value = capture()
        for quantity in (None, D(1)):
            doc = self.check_report(value, evidence(value, physical_quantity=quantity, physical_complete=False))
            self.assertEqual(doc.rows["physical_qty"][0], expected(quantity))
            self.assertEqual(doc.rows["delta_qty"][0], "不可用")
            self.assertEqual(doc.rows["physical_scenario_upper_qty"][0], "不可用")

    def test_b03_unmanaged_pending_retains_all_reasons(self):
        item = StoredLot(snapshot(), True, False, 1)
        value = capture((item,), unmanaged=(item.lot.lot_id,))
        doc = self.check_report(value, evidence(value, physical_quantity=D(2)))
        self.assertEqual(doc.rows["pending_complete"][0], "否（false）")
        for key in ("synthetic_buy_qty", "held_buy_qty", "exchange_sell_qty", "virtual_gross_scenario_upper_qty"):
            self.assertEqual(doc.rows[key][0], "不可用")
        self.assertIn("pending_incomplete", doc.text)
        self.assertIn("pending_lot_link_incomplete", doc.text)

    def test_b04_stale_and_future_each_source(self):
        base = capture((StoredLot(snapshot(), False, False, 1),))
        for source in ("capture", "physical", "mark"):
            for observed, until in ((10, 50), (101, 120)):
                value = replace(base, observed_at_ms=observed, valid_until_ms=until) if source == "capture" else base
                scene = evidence(value, physical_quantity=D(2))
                if source != "capture":
                    scene = replace(scene, **{source + "_observed_at_ms": observed, source + "_valid_until_ms": until})
                with self.subTest(source=source, observed=observed):
                    doc = self.check_report(value, scene)
                    key = "lot_fresh" if source == "capture" else source + "_fresh"
                    self.assertEqual(doc.rows[key][0], "否（false）")
                    if source == "capture":
                        self.assertEqual(doc.rows["pending_fresh"][0], "否（false）")
                        self.assertEqual(doc.rows["observed_gross_notional"][0], "2")
                    if observed > 100:
                        self.assertIn("future_observation", doc.text)

    def test_b05_time_endpoints(self):
        value = replace(capture(), observed_at_ms=90, valid_until_ms=110)
        scene = evidence(value, physical_observed_at_ms=90, physical_valid_until_ms=110,
                         mark_observed_at_ms=90, mark_valid_until_ms=110)
        for now, fresh in ((90, True), (110, False)):
            doc = self.check_report(value, scene, now)
            for key in ("lot_fresh", "physical_fresh", "mark_fresh", "pending_fresh"):
                self.assertEqual(doc.rows[key][0], expected(fresh))

    def test_b06_empty_valid_capture(self):
        doc = self.check_report(capture())
        self.assertIn("無降級原因", doc.text)
        self.assertEqual(doc.rows["pending_unique_count"][0], "0")
        self.assertEqual(doc.rows["synthetic_buy_qty"][0], "0")

    def test_c01_multiside_signed_and_absolute_values(self):
        items = (StoredLot(snapshot(), False, False, 1),
                 StoredLot(snapshot(seq=2, side="short", opened_qty=D(5), remaining_qty=D(5)), False, False, 2))
        value = capture(items)
        doc = self.check_report(value, evidence(value, physical_quantity=D(-2)))
        for key, number in {"observed_gross_qty": "7", "observed_net_qty": "-3", "delta_qty": "-1",
                            "observed_signed_net_notional": "-3", "physical_notional": "2"}.items():
            self.assertEqual(doc.rows[key][0], number)

    def test_c02_c03_e04_real_journal_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(Path(directory) / "report.sqlite3", "fake-account", D(100))
            try:
                journal.lots.register_binding(scope=scope(), bot_id="lot-bot", contract=contract())
                def check(physical, pending_buy, pending_sell, gross, upper, count):
                    value = journal.capture_lot_snapshot(scope=scope(), inst_id=contract().inst_id,
                                                        observed_at_ms=90, valid_until_ms=110)
                    doc = self.check_report(value, evidence(value, physical_quantity=D(physical)))
                    for key, number in (("pending_buy_qty", pending_buy), ("pending_sell_qty", pending_sell),
                                        ("observed_gross_qty", gross), ("virtual_gross_scenario_upper_qty", upper),
                                        ("pending_unique_count", count)):
                        self.assertEqual(doc.rows[key][0], str(number))
                opening(journal)
                check(0, 3, 0, 0, 3, 1)
                journal.lot_fills.apply_fill(fill(quantity=D(1)))
                check(1, 2, 0, 1, 3, 1)
                journal.lot_fills.apply_fill(fill(seq=2, quantity=D(2)))
                check(3, 0, 0, 3, 3, 1)
                terminal(journal, seq=2)
                check(3, 0, 0, 3, 3, 0)
                close_order(journal)
                check(3, 0, 3, 3, 3, 1)
            finally:
                journal.close()

    def test_c04_buckets_and_limitations(self):
        value = capture(pending=(pending(), pending(seq=2, side="SELL", quantity=D(5))))
        doc = self.check_report(value)
        self.assertEqual(doc.rows["synthetic_buy_qty"][0], "3")
        self.assertEqual(doc.rows["synthetic_sell_qty"][0], "5")
        text = "".join(doc.text)
        for phrase in ("不能證明交易所沒有委託", "未成交 CLOSE 不預扣目前 Gross",
                       "has_unknown=false 不表示無未決責任", "非交易所查證"):
            self.assertIn(phrase, text)

    def test_d01_private_formatter_full_precision(self):
        cases = ((D("1E-40"), "0." + "0" * 39 + "1"),
                 (D("-12345678901234567890.123456789"), "-12345678901234567890.123456789"),
                 (D("1.2300"), "1.2300"), (D("-0.000"), "0"), (D("0E+40"), "0"))
        with localcontext() as ctx:
            ctx.prec = 2
            for number, text in cases:
                self.assertEqual(rendering._format(number), text)

    def test_d02_defensive_reason_order_and_unknown_status_stub(self):
        value = capture()
        scene = evidence(value)
        original = lot_scenario.observe_synthetic_scenario(capture=value, scenario=scene, now_ms=100)
        codes = ("pending_effect_unknown", "pending_quantity_unknown", "pending_cut_mismatch",
                 "pending_incomplete", "pending_lot_link_incomplete", "pending_missing", "mark_missing",
                 "position_cut_mismatch", "lot_inventory_incomplete", "physical_unverified", "physical_unknown",
                 "future_observation", "pending_stale", "mark_stale", "physical_stale", "lot_stale", "new_reason")
        result = replace(original, report=replace(original.report, reasons=codes, comparison_status="NEW_STATUS"))
        with patch.object(lot_scenario, "observe_synthetic_scenario", return_value=result):
            doc = Document(self.render(value, scene))
        self.assertEqual([text for text in doc.text if text in codes], list(codes))
        self.assertIn("未收錄原因", doc.text)
        self.assertEqual(doc.rows["comparison_status"][0], "未識別比較狀態（NEW_STATUS）")
        for phrase in ("存在效果未分類的未決責任", "存在數量未知的未決責任", "未決責任與部位截點不一致",
                       "未決責任集合不完整", "未決責任與 Lot 關聯不足", "未決責任集合未提供", "合成 mark 未提供",
                       "Lot 與合成實體截點不一致", "Lot 集合不完整", "合成實體完整性聲明未成立",
                       "合成實體數量未提供", "存在晚於評估時間的取樣", "未決責任來源不在有效期內",
                       "合成 mark 不在有效期內", "合成實體來源不在有效期內", "Lot 來源不在有效期內"):
            self.assertIn(phrase, doc.text)

    def test_d03_defensive_dynamic_html_escaping_stub(self):
        value = capture()
        scene = evidence(value)
        original = lot_scenario.observe_synthetic_scenario(capture=value, scenario=scene, now_ms=100)
        attack = '<img src="x" onerror="bad">&\'text'
        result = replace(original, source_capture_id=attack,
                         report=replace(original.report, quote_id=attack, reasons=(attack,), comparison_status=attack))
        with patch.object(lot_scenario, "observe_synthetic_scenario", return_value=result):
            output = self.render(value, scene)
        doc = Document(output)
        self.assertEqual(doc.rows["source_capture_id"][0], attack)
        self.assertEqual(doc.rows["quote_id"][0], attack)
        self.assertIn(attack, doc.text)
        self.assertIn("&lt;img", output)
        self.assertIn("&quot;", output)
        self.assertIn("&#x27;", output)
        self.assertNotIn("img", [tag for tag, attrs in doc.tags])

    def test_d04_html_structure_and_no_external_resources(self):
        output = self.render()
        doc = Document(output)
        self.assertTrue(output.startswith("<!DOCTYPE html>"))
        self.assertIn(("html", {"lang": "zh-Hant"}), doc.tags)
        self.assertIn(("meta", {"charset": "utf-8"}), doc.tags)
        self.assertTrue(any(tag == "meta" and attrs.get("name") == "viewport" for tag, attrs in doc.tags))
        self.assertFalse({"script", "iframe", "form", "link", "img"} & {tag for tag, attrs in doc.tags})
        self.assertFalse(any("src" in attrs or "href" in attrs for tag, attrs in doc.tags))
        self.assertNotIn("url(", output)
        self.assertNotIn("@import", output)
        self.assertIn("overflow-wrap: anywhere", output)
        self.assertIn("overflow-x: auto", output)

    def test_e01_real_s6_rejections(self):
        value = capture()
        for changes, code in (({"source_capture_id": "f" * 64}, "scenario_identity_mismatch"),
                              ({"scenario_cut_id": value.capture_id}, "invalid_scenario_cut"),
                              ({"scope": lots.LotScope("other", "local-sim")}, "scenario_identity_mismatch")):
            with self.subTest(code=code):
                with self.assertRaises(lot_scenario.ScenarioInputError) as caught:
                    self.render(value, evidence(value, **changes))
                self.assertEqual(caught.exception.code, code)

    def test_e02_exception_identity_preserved_stub(self):
        for error in (lot_scenario.ScenarioInputError("invalid_capture"),
                      lot_exposure.ExposureInputError("decimal_range"), RuntimeError("unexpected")):
            with patch.object(lot_scenario, "observe_synthetic_scenario", side_effect=error):
                with self.assertRaises(type(error)) as caught:
                    self.render()
            self.assertIs(caught.exception, error)

    def test_e03_runtime_io_blocked(self):
        value = capture(pending=(pending(),))
        scene = evidence(value)
        with ExitStack() as stack:
            for target in ("builtins.open", "io.open", "sqlite3.connect", "socket.socket", "socket.create_connection",
                           "time.time", "time.time_ns", "time.monotonic", "os.getenv", "builtins.print"):
                stack.enter_context(patch(target, side_effect=AssertionError("forbidden I/O")))
            stack.enter_context(patch.object(type(os.environ), "__getitem__", side_effect=AssertionError("environment")))
            with patch("sys.stdout") as stdout, patch("sys.stderr") as stderr:
                output = self.render(value, scene)
                stdout.write.assert_not_called()
                stderr.write.assert_not_called()
        self.assertIn("SYNTHETIC_SCENARIO", output)

    def test_public_arguments_are_required_and_keyword_only(self):
        with self.assertRaises(TypeError):
            rendering.render_synthetic_scenario_report()
        with self.assertRaises(TypeError):
            rendering.render_synthetic_scenario_report(capture(), None, 100)


if __name__ == "__main__":
    unittest.main()
