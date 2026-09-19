"""S6 provenance, forged captures, degradation and real S3/S5 integration."""

from dataclasses import FrozenInstanceError, fields, replace
from decimal import Decimal as D, localcontext
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from catos import lot_exposure as exposure, lot_snapshot as snapshots, lots
from catos.journal import Journal
from catos.lot_journal import StoredLot
from catos.lot_scenario import (
    ScenarioInputError, SyntheticScenarioEvidence, observe_synthetic_scenario,
)
from lot_journal_helpers import contract, scope, snapshot, create
from lot_fill_helpers import opening, fill, terminal, close_order


def signed(value):
    return replace(value, capture_id=snapshots._capture_id(value))


def capture(items=(), pending=(), unmanaged=(), spec=None, bots=None):
    return signed(snapshots.LocalLotCapture(
        "synthetic_ledger", scope(), spec or contract(), "", 90, 110,
        bots or (snapshots.BotWatermark("lot-bot", 10),),
        tuple(sorted(items, key=lambda s: s.lot.lot_id)),
        tuple(sorted(pending, key=lambda p: p.order_key)), tuple(sorted(unmanaged))))


def evidence(value, **changes):
    base = SyntheticScenarioEvidence("synthetic_scenario", value.scope, value.contract,
        "scenario-cut", value.capture_id, 91, 111, D(0), True, "quote", 92, 112, D(100))
    return replace(base, **changes)


def pending(seq=1, side="BUY", quantity=D(3), spec=None, bot="lot-bot"):
    lot = snapshot(seq=seq, spec=spec, bot=bot)
    return snapshots.SyntheticPendingObligation(
        f"{seq:064x}", lot.open_intent_key, bot, lot.lot_id, "OPEN", side, quantity, D(0), quantity, 0)


class LotScenarioTests(unittest.TestCase):
    def observe(self, value=None, scene=None, now=100):
        value = value if value is not None else capture()
        return observe_synthetic_scenario(capture=value, scenario=scene or evidence(value), now_ms=now)

    def reject(self, value, code="invalid_capture", scene=None, now=100):
        if scene is None and isinstance(value, snapshots.LocalLotCapture):
            scene = evidence(value)
        with self.assertRaises(ScenarioInputError) as caught:
            observe_synthetic_scenario(capture=value, scenario=scene, now_ms=now)
        self.assertEqual(caught.exception.code, code)

    def test_a01_empty_attested_scenario(self):
        value = capture()
        result = self.observe(value)
        self.assertEqual(result.source_capture_id, value.capture_id)
        self.assertEqual(result.scenario_cut_id, "scenario-cut")
        self.assertEqual(result.report.evidence_kind, "SYNTHETIC_SCENARIO")
        self.assertEqual(result.report.comparison_status, "MATCH")
        self.assertEqual(result.report.virtual_gross_scenario_upper_qty, D(0))
        self.assertFalse({"accepted", "ready", "authorized"} & {f.name for f in fields(result.report)})

    def test_a02_capture_binding_rejected_before_observation(self):
        value = capture()
        with patch.object(exposure, "observe_exposure", side_effect=AssertionError("must not observe")):
            self.reject(value, "scenario_identity_mismatch", evidence(value, source_capture_id="f" * 64))

    def test_a03_capture_identity_is_not_cut(self):
        value = capture()
        self.reject(value, "invalid_scenario_cut", evidence(value, scenario_cut_id=value.capture_id))

    def test_a04_scope_and_every_contract_field(self):
        value = capture()
        for other in (lots.LotScope("other", "local-sim"), lots.LotScope("fake-account", "demo")):
            self.reject(value, "scenario_identity_mismatch", evidence(value, scope=other))
        for field in fields(value.contract):
            changed = "OTHER-USDT-SWAP" if field.name == "inst_id" else D(2)
            with self.subTest(field=field.name):
                self.reject(value, "scenario_identity_mismatch",
                            evidence(value, contract=replace(value.contract, **{field.name: changed})))
        self.reject(value, "scenario_identity_mismatch", evidence(value, source="exchange"))

    def test_a05_missing_or_invalid_attestation(self):
        value = capture()
        for cut in (None, "", "bad cut", "x" * 65, True):
            self.reject(value, "invalid_scenario_cut", evidence(value, scenario_cut_id=cut))

    def test_a06_original_times_and_identity_are_forwarded(self):
        value = capture(pending=(pending(),))
        scene = evidence(value)
        with patch.object(exposure, "observe_exposure", wraps=exposure.observe_exposure) as observe:
            self.observe(value, scene)
        request = observe.call_args.args[0]
        self.assertEqual((request.lots_view.observed_at_ms, request.lots_view.valid_until_ms), (90, 110))
        self.assertEqual((request.pending_view.observed_at_ms, request.pending_view.valid_until_ms), (90, 110))
        self.assertEqual((request.physical_view.observed_at_ms, request.physical_view.valid_until_ms), (91, 111))
        self.assertEqual((request.mark_view.quote_id, request.mark_view.observed_at_ms,
                          request.mark_view.valid_until_ms), ("quote", 92, 112))
        order = request.pending_view.orders[0]
        self.assertEqual((order.obligation_id, order.origin, order.state, order.remaining_quantity),
                         (value.pending[0].order_key, "SYNTHETIC_LEDGER", "UNTERMINATED", D(3)))
        self.assertEqual(request.lots_view.cut_id, scene.scenario_cut_id)

    def test_b01_first_fill_pending_has_no_lot(self):
        result = self.observe(capture(pending=(pending(),))).report
        self.assertEqual((result.observed_gross_qty, result.pending_buy_qty), (D(0), D(3)))
        self.assertEqual(result.virtual_gross_scenario_upper_qty, D(3))
        self.assertFalse(result.has_unknown)

    def test_b07_multibot_buys_and_sells_are_separate(self):
        value = capture(pending=(pending(), pending(seq=2, bot="other", side="SELL", quantity=D(5))),
                        bots=(snapshots.BotWatermark("lot-bot", 0), snapshots.BotWatermark("other", 0)))
        report = self.observe(value).report
        self.assertEqual((report.synthetic_buy_qty, report.synthetic_sell_qty), (D(3), D(5)))
        self.assertEqual((report.pending_buy_qty, report.pending_sell_qty), (D(3), D(5)))
        self.assertEqual((report.held_buy_qty, report.held_sell_qty,
                          report.exchange_buy_qty, report.exchange_sell_qty), (D(0),) * 4)
        self.assertEqual(report.physical_scenario_upper_qty, D(5))
        self.assertEqual(report.virtual_gross_scenario_upper_qty, D(8))

    def test_c01_c02_unmanaged_is_incomplete_without_fake_orders(self):
        item = StoredLot(snapshot(), True, False, 1)
        value = capture((item,), unmanaged=(item.lot.lot_id,))
        report = self.observe(value, evidence(value, physical_quantity=D(2))).report
        self.assertFalse(report.pending_complete)
        self.assertEqual(report.pending_unique_count, 0)
        self.assertFalse(report.has_unknown)
        self.assertIn("pending_incomplete", report.reasons)
        self.assertIn("pending_lot_link_incomplete", report.reasons)
        self.assertIsNone(report.physical_scenario_upper_qty)
        self.assertIsNone(report.virtual_gross_scenario_upper_qty)

    def test_c03_unmanaged_cannot_overlap_pending(self):
        order = replace(pending(), filled_quantity=D(2), remaining_quantity=D(1), last_fill_seq=1)
        item = StoredLot(snapshot(), True, False, 1)
        self.reject(capture((item,), (order,), (item.lot.lot_id,)))

    def test_c04_unmanaged_must_exist_and_be_unresolved(self):
        item = StoredLot(snapshot(), False, False, 1)
        self.reject(capture(unmanaged=(item.lot.lot_id,)))
        self.reject(capture((item,), unmanaged=(item.lot.lot_id,)))
        unresolved = replace(item, opening_unresolved=True)
        self.reject(capture((unresolved,), unmanaged=(item.lot.lot_id, item.lot.lot_id)))

    def test_c05_managed_unresolved_complete(self):
        order = replace(pending(), filled_quantity=D(2), remaining_quantity=D(1), last_fill_seq=1)
        item = StoredLot(snapshot(), True, False, 1)
        report = self.observe(capture((item,), (order,))).report
        self.assertTrue(report.pending_complete)
        self.assertNotIn("pending_lot_link_incomplete", report.reasons)
        self.assertEqual(report.virtual_gross_scenario_upper_qty, D(3))

    def test_c06_modified_content_with_old_hash(self):
        value = capture(pending=(pending(),))
        self.reject(replace(value, pending=()))
        self.reject(replace(value, capture_id=value.capture_id.upper()))

    def test_c07_duplicates_and_unsorted_collections(self):
        items = (StoredLot(snapshot(), False, False, 1), StoredLot(snapshot(seq=2), False, False, 2))
        value = capture(items, (pending(seq=3), pending(seq=4)),
                        bots=(snapshots.BotWatermark("lot-bot", 10), snapshots.BotWatermark("other", 0)))
        for name in ("lots", "pending", "bot_watermarks"):
            original = getattr(value, name)
            for bad in (original[::-1], original + (original[0],)):
                with self.subTest(name=name, bad=bad):
                    self.reject(signed(replace(value, **{name: bad})))

    def test_capture_internal_contradictions_even_with_recomputed_hash(self):
        order = pending()
        for changes in (dict(side="long"), dict(effect="UNKNOWN"), dict(bot_id="missing"),
                        dict(filled_quantity=D(1)), dict(remaining_quantity=D(2)),
                        dict(last_fill_seq=True), dict(last_fill_seq=1), dict(resolved_quantity=D(0)),
                        dict(remaining_quantity=D("0.1")), dict(lot_id="f" * 64)):
            with self.subTest(changes=changes):
                self.reject(capture(pending=(replace(order, **changes),)))
        item = StoredLot(snapshot(), True, False, 1)
        self.reject(capture((item,)))
        self.reject(capture((replace(item, commit_seq=11),), unmanaged=(item.lot.lot_id,)))
        matched = replace(order, filled_quantity=D(2), remaining_quantity=D(1), last_fill_seq=1)
        self.reject(capture((item,), (replace(matched, side="SELL"),)))
        self.reject(capture((replace(item, opening_unresolved=False),), (matched,)))
        self.reject(capture((item,), (replace(matched, bot_id="other"),),
                            bots=(snapshots.BotWatermark("lot-bot", 10), snapshots.BotWatermark("other", 0))))

    def test_capture_types_source_time_and_limits(self):
        value = capture()
        for bad in (None, replace(value, source="exchange"), replace(value, observed_at_ms=True),
                    replace(value, valid_until_ms=90), replace(value, bot_watermarks=()),
                    replace(value, lots=[]), replace(value, pending=(object(),)),
                    replace(value, scope=lots.LotScope("fake-account", "live"))):
            self.reject(bad)
        for name, entries in (("bot_watermarks", (value.bot_watermarks[0],) * 65),
                              ("lots", (StoredLot(snapshot(), False, False, 1),) * 4097),
                              ("pending", (pending(),) * 4097)):
            self.reject(replace(value, **{name: entries}), "input_limit")

    def test_d01_physical_never_inferred(self):
        value = capture((StoredLot(snapshot(), False, False, 1),))
        report = self.observe(value, evidence(value, physical_quantity=None, physical_complete=False)).report
        self.assertIsNone(report.physical_qty)
        self.assertEqual(report.observed_net_qty, D(2))
        self.assertEqual(report.comparison_status, "UNAVAILABLE")

    def test_capacity_exact_limits_are_accepted(self):
        bots = tuple(snapshots.BotWatermark(f"bot{i:02d}", 0) for i in range(64))
        self.assertEqual(self.observe(capture(bots=bots)).report.comparison_status, "MATCH")
        orders = tuple(pending(seq=i + 1, quantity=D(1)) for i in range(4096))
        self.assertEqual(self.observe(capture(pending=orders)).report.pending_unique_count, 4096)
        items = tuple(StoredLot(snapshot(seq=i + 1), False, False, i + 1) for i in range(4096))
        value = capture(items, bots=(snapshots.BotWatermark("lot-bot", 4096),))
        self.assertEqual(self.observe(value).report.observed_gross_qty, D(8192))

    def test_d02_incomplete_matching_physical_is_unavailable(self):
        value = capture()
        report = self.observe(value, evidence(value, physical_complete=False)).report
        self.assertEqual(report.comparison_status, "UNAVAILABLE")

    def test_d03_invalid_physical(self):
        value = capture()
        for changes in (dict(physical_quantity=None), dict(physical_complete=1),
                        dict(physical_quantity=1.0), dict(physical_quantity=D("NaN")),
                        dict(physical_quantity=D("0.1"))):
            self.reject(value, "invalid_scenario_physical", evidence(value, **changes))

    def test_d04_d05_exact_match_and_mismatch(self):
        value = capture((StoredLot(snapshot(), False, False, 1),))
        for physical, delta, status in ((D(2), D(0), "MATCH"), (D("2.5"), D("-0.5"), "MISMATCH")):
            report = self.observe(value, evidence(value, physical_quantity=physical)).report
            self.assertEqual((report.comparison_status, report.delta_qty), (status, delta))

    def test_d06_absent_mark_preserves_quantity_comparison(self):
        value = capture()
        scene = evidence(value, mark=None, mark_quote_id=None, mark_observed_at_ms=None, mark_valid_until_ms=None)
        report = self.observe(value, scene).report
        self.assertEqual(report.comparison_status, "MATCH")
        self.assertEqual((report.observed_gross_notional, report.observed_signed_net_notional,
                          report.physical_notional), (None, None, None))

    def test_d07_stale_future_mark_and_invalid_metadata(self):
        value = capture()
        for changes in (dict(mark_observed_at_ms=1, mark_valid_until_ms=99),
                        dict(mark_observed_at_ms=101, mark_valid_until_ms=120)):
            report = self.observe(value, evidence(value, **changes)).report
            self.assertIn("mark_stale", report.reasons)
            self.assertIsNone(report.physical_notional)
        for changes in (dict(mark=None), dict(mark_quote_id=None), dict(mark_quote_id="bad quote"),
                        dict(mark_observed_at_ms=None), dict(mark=D(0)), dict(mark=D("Infinity")), dict(mark=1.0)):
            self.reject(value, "invalid_scenario_mark", evidence(value, **changes))

    def test_e06_source_freshness_preserved(self):
        value = capture()
        for changes, reason in ((dict(observed_at_ms=1, valid_until_ms=99), "lot_stale"),
                                (dict(observed_at_ms=101, valid_until_ms=120), "future_observation")):
            changed = replace(value, **changes)  # S5 content identity intentionally excludes time.
            report = self.observe(changed).report
            self.assertIn(reason, report.reasons)
            self.assertIn("pending_stale", report.reasons)
            self.assertEqual(report.comparison_status, "UNAVAILABLE")
        report = self.observe(value, evidence(value, physical_valid_until_ms=99)).report
        self.assertIn("physical_stale", report.reasons)

    def test_invalid_time_types_ranges_and_order(self):
        value = capture()
        for now in (True, -1, 1.0):
            self.reject(value, "invalid_scenario_time", now=now)
        for changes in (dict(physical_observed_at_ms=True), dict(physical_valid_until_ms=91),
                        dict(mark_observed_at_ms=-1), dict(mark_valid_until_ms=92)):
            self.reject(value, "invalid_scenario_time", evidence(value, **changes))

    def test_f01_decimal_equivalence_and_low_context(self):
        value = capture(pending=(pending(quantity=D("123.5")),))
        expected = self.observe(value)
        equivalent = signed(replace(value, pending=(replace(value.pending[0],
                            resolved_quantity=D("123.500"), remaining_quantity=D("123.500")),)))
        self.assertEqual(equivalent.capture_id, value.capture_id)
        with localcontext() as ctx:
            ctx.prec = 2
            self.assertEqual(self.observe(equivalent), expected)
            self.assertEqual(ctx.prec, 2)

    def test_f02_small_steps_and_large_derived_mark(self):
        spec = contract(lot_size=D("1e-18"), min_size=D("1e-18"))
        value = capture(pending=(pending(quantity=D("1e-18"), spec=spec),), spec=spec)
        result = self.observe(value, evidence(value, mark=D("1e50"))).report
        self.assertEqual(result.synthetic_buy_qty, D("1e-18"))
        self.assertEqual(result.physical_scenario_upper_qty, D("1e-18"))
        self.assertIsInstance(result.physical_notional, D)

    def test_f03_frozen_and_nonmutating(self):
        value = capture(pending=(pending(),))
        scene = evidence(value)
        before = (repr(value), repr(scene))
        result = self.observe(value, scene)
        self.assertEqual((repr(value), repr(scene)), before)
        for obj, name in ((scene, "source"), (result, "evidence_kind")):
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, name, "changed")

    def test_derived_close_remainder_survives_low_context(self):
        spec = contract(lot_size=D("1e-18"), min_size=D("1e-18"))
        quantity = D("123456789012.123456789012345678")
        lot = snapshot(spec=spec, opened_qty=quantity, remaining_qty=quantity)
        item = StoredLot(lot, False, True, 1)
        obligation = snapshots.SyntheticPendingObligation(
            "1" * 64, snapshot(seq=2, spec=spec).open_intent_key, lot.bot_id, lot.lot_id,
            "CLOSE", "SELL", quantity, D(0), quantity, 0)
        value = capture((item,), (obligation,), spec=spec)
        with localcontext() as ctx:
            ctx.prec = 2
            result = self.observe(value, evidence(value, physical_quantity=quantity)).report
        self.assertEqual(result.synthetic_sell_qty, quantity)
        self.assertEqual(result.virtual_gross_scenario_upper_qty, quantity)
        self.assertEqual(result.comparison_status, "MATCH")

    def test_exposure_errors_are_not_silently_downgraded(self):
        value = capture()
        error = exposure.ExposureInputError("adapter_bug")
        with patch.object(exposure, "observe_exposure", side_effect=error):
            with self.assertRaises(exposure.ExposureInputError) as caught:
                self.observe(value)
        self.assertIs(caught.exception, error)

    def test_f04_adapter_needs_no_io(self):
        value = capture(pending=(pending(),))
        scene = evidence(value)
        with patch("builtins.open", side_effect=AssertionError("file I/O")), \
             patch("sqlite3.connect", side_effect=AssertionError("database I/O")), \
             patch("socket.socket", side_effect=AssertionError("network I/O")), \
             patch("time.time", side_effect=AssertionError("wall clock")):
            self.assertEqual(self.observe(value, scene).report.synthetic_buy_qty, D(3))


class LotScenarioJournalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.j = Journal(Path(temp.name) / "scenario.sqlite3", "fake-account", D(100))
        self.addCleanup(self.j.close)
        self.j.lots.register_binding(scope=scope(), bot_id="lot-bot", contract=contract())

    def report(self):
        value = self.j.capture_lot_snapshot(scope=scope(), inst_id=contract().inst_id,
                                           observed_at_ms=90, valid_until_ms=110)
        return observe_synthetic_scenario(capture=value, scenario=evidence(value), now_ms=100).report

    def test_b02_b04_b06_real_open_lifecycle(self):
        opening(self.j)
        self.assertEqual(self.report().pending_buy_qty, D(3))
        self.j.lot_fills.apply_fill(fill(quantity=D(1)))
        report = self.report()
        self.assertEqual((report.observed_gross_qty, report.pending_buy_qty), (D(1), D(2)))
        self.j.lot_fills.apply_fill(fill(seq=2, quantity=D(2)))
        report = self.report()
        self.assertEqual((report.pending_unique_count, report.pending_buy_qty), (1, D(0)))
        terminal(self.j, seq=2)
        self.assertEqual(self.report().pending_unique_count, 0)

    def test_b03_b05_close_never_precredits_gross(self):
        for side in ("long", "short"):
            with self.subTest(side=side):
                # Distinct journals keep S3 event and Lot identities independent.
                if side == "short":
                    self.j.close()
                    temp = tempfile.TemporaryDirectory()
                    self.addCleanup(temp.cleanup)
                    self.j = Journal(Path(temp.name) / "short.sqlite3", "fake-account", D(100))
                    self.addCleanup(self.j.close)
                    self.j.lots.register_binding(scope=scope(), bot_id="lot-bot", contract=contract())
                opening(self.j, side=side)
                self.j.lot_fills.apply_fill(fill(quantity=D(3)))
                terminal(self.j)
                close_order(self.j)
                self.j.lot_fills.apply_fill(fill(order="close", quantity=D(1)))
                report = self.report()
                self.assertEqual((report.observed_gross_qty, report.virtual_gross_scenario_upper_qty), (D(2), D(2)))
                self.assertEqual(report.synthetic_sell_qty if side == "long" else report.synthetic_buy_qty, D(2))
                self.j.lot_fills.apply_fill(fill(order="close", seq=2, quantity=D(2)))
                report = self.report()
                self.assertEqual((report.observed_gross_qty, report.pending_unique_count), (D(0), 1))
                terminal(self.j, order="close", seq=2, terminal_id="close-terminal")
                self.assertEqual(self.report().pending_unique_count, 0)

    def test_real_s2_unmanaged_capture_degrades(self):
        create(self.j, opening=True)
        report = self.report()
        self.assertFalse(report.pending_complete)
        self.assertEqual(report.pending_unique_count, 0)
        self.assertIsNone(report.physical_scenario_upper_qty)
