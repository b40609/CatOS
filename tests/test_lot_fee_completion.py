"""S9 synthetic-only acceptance cases. Execute with unittest discovery."""

from contextlib import closing
from dataclasses import fields, replace
from decimal import Decimal as D, localcontext
from pathlib import Path
import multiprocessing
import sqlite3
import tempfile
import unittest

from catos import ipc, ipc_lots, lots, lot_snapshot, lot_snapshot_codec
from catos.journal import Journal, JournalError
from catos.lot_accounting import SyntheticFillV2, FeeCompletion
from catos.lot_journal import LotStorageError
from catos.lot_scenario import observe_synthetic_scenario, observe_synthetic_scenario_v2, ScenarioInputError
from catos.lot_scenario_report import render_synthetic_scenario_report_v2
from lot_journal_helpers import scope, contract, snapshot
from lot_fill_helpers import opening, terminal, current, close_order, fill
from test_lot_journal import FailingConnection
from test_lot_scenario import evidence


def fill_v2(*, order="open", seq=1, quantity=D(1), price=D(100), fee=None, trade=None):
    return SyntheticFillV2(scope(), "synthetic", contract().inst_id, order,
        trade or f"trade-{seq}", seq, quantity, price, "UNKNOWN" if fee is None else "KNOWN", fee)


def completion(*, order="open", trade="trade-1", fee=D(0)):
    return FeeCompletion(scope(), "synthetic", contract().inst_id, order, trade, fee)


def external_lot():
    old = snapshot()
    return lots.LotV2(**{f.name: getattr(old, f.name) for f in fields(old) if f.name != "fees_paid"},
                      fee_quality=lots.FeeQuality("UNVERIFIED", None, None))


def crash_worker(path, phase, pipe):
    """Parent terminates a real spawned process at an acknowledged commit boundary."""
    journal = Journal(path, "fake-account", D(100), lot_schema_version=8)
    real = journal.connection

    class BoundaryConnection:
        def __getattr__(self, name):
            return getattr(real, name)

        def commit(self):
            if phase == "before":
                pipe.send("boundary")
                pipe.recv()
            result = real.commit()
            if phase == "after":
                pipe.send("boundary")
                pipe.recv()
            return result

    wrapped = BoundaryConnection()
    journal.connection = journal.lots.db = journal.lot_fills.db = wrapped
    journal.lot_fills.complete_fee(completion(fee=D("0.1")))
    pipe.send("unexpected-ack")


class FeeTypeTests(unittest.TestCase):
    def test_a01_fill_pairing_and_input_bounds(self):
        good = fill_v2()
        for changes in ({"fee_state": "KNOWN"}, {"fee_paid": D(0)}, {"fee_state": "other"},
                        {"fee_state": "KNOWN", "fee_paid": 0.1},
                        {"fee_state": "KNOWN", "fee_paid": D("NaN")},
                        {"fee_state": "KNOWN", "fee_paid": D("Infinity")},
                        {"fee_currency": "BTC"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(good, **changes)
        for fee in (D(0), D("-.01"), D(".01")):
            self.assertEqual(fill_v2(fee=fee).fee_state, "KNOWN")

    def test_a02_quality_three_states_and_rejections(self):
        self.assertIsNone(lots.FeeQuality("UNVERIFIED", None, None).fee_complete)
        self.assertTrue(lots.FeeQuality("MANAGED", D(0), 0).fee_complete)
        self.assertFalse(lots.FeeQuality("MANAGED", D(0), 1).fee_complete)
        for values in (("MANAGED", None, 0), ("MANAGED", D(0), True), ("MANAGED", D(0), -1),
                       ("MANAGED", D("NaN"), 0), ("UNVERIFIED", D(0), None),
                       ("UNVERIFIED", None, 0), ("other", None, None)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                lots.FeeQuality(*values)

    def test_a02_strict_codec_and_legacy_separation(self):
        value = external_lot()
        wire = lot_snapshot_codec.lot_to_wire(value)
        self.assertEqual(lot_snapshot_codec.lot_from_wire(wire), value)
        for bad in (dict(wire, snapshot_version=True), dict(wire, snapshot_version=1), dict(wire, fees_paid="0"),
                    {k: v for k, v in wire.items() if k != "fee_quality"},
                    dict(wire, fee_quality=dict(coverage="MANAGED", known_fee_subtotal="0"))):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                lot_snapshot_codec.lot_from_wire(bad)
        with self.assertRaises(ValueError):
            ipc_lots.lot_to_wire(value)
        with self.assertRaises(ValueError):
            lot_snapshot_codec.lot_to_wire(snapshot())
        self.assertFalse(hasattr(value, "fees_paid"))


class FeeJournalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "synthetic.sqlite3"
        self.j = Journal(self.path, "fake-account", D(100), lot_schema_version=8)
        self.addCleanup(lambda: self.j.close() if self.j is not None else None)
        self.j.lots.register_binding(scope=scope(), bot_id="lot-bot", contract=contract())

    def reopen(self):
        self.j.close()
        self.j = None
        self.j = Journal(self.path, "fake-account", D(100), lot_schema_version=8)

    def seed(self, *, fee=None, side="long"):
        opening(self.j, side=side)
        return self.j.lot_fills.apply_fill_v2(fill_v2(quantity=D(3), fee=fee))

    def capture(self):
        return self.j.capture_lot_snapshot_v2(scope=scope(), inst_id=contract().inst_id,
                                             observed_at_ms=90, valid_until_ms=110)

    def reject(self, code, callback):
        with self.assertRaises((LotStorageError, lots.LotError)) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def corrupt(self, sql):
        path = self.path.with_name("corrupt.sqlite3")
        # Each call uses a fresh destination file, never a user database.
        with closing(sqlite3.connect(path)) as db:
            self.j.connection.backup(db)
            db.executescript(sql)
            db.commit()
        with self.assertRaises(JournalError):
            Journal(path, "fake-account", D(100), lot_schema_version=8)

    def test_schema8_strict_and_empty_counts(self):
        self.assertEqual(self.j.connection.execute("PRAGMA user_version").fetchone()[0], 8)
        report = self.j.lot_fills.recover()
        self.assertEqual((report.order_count, report.fill_count, report.terminal_count, report.fee_completion_count), (0, 0, 0, 0))
        columns = {r[1]: r for r in self.j.connection.execute("PRAGMA table_info(lot_revisions)")}
        self.assertNotIn("fees_paid", columns)
        self.assertIn("fee_unknown_fill_count", columns)

    def test_a03_a04_short_partial_close_and_external_context(self):
        self.seed(side="short")
        terminal(self.j)
        close_order(self.j)
        with localcontext() as ctx:
            ctx.prec = 2
            self.j.lot_fills.apply_fill_v2(fill_v2(order="close", quantity=D(1), price=D(80), fee=D(".0123456789")))
            self.j.lot_fills.complete_fee(completion(fee=D("-.0023456789")))
        value = current(self.j).lot
        self.assertEqual(value.remaining_qty, D(2))
        self.assertEqual(value.realized_pnl, D(".2"))
        self.assertEqual(value.fee_quality, lots.FeeQuality("MANAGED", D(".01"), 0))
        terminal(self.j, order="close", quantity=D(1), status="CANCELED")
        before = current(self.j)
        self.reopen()
        self.assertEqual(current(self.j), before)

    def test_a05_sequential_decimal_replay(self):
        opening(self.j, quantity=D(4))
        values = (D("1000000000000000000"), D(".000000000000000001"), D("-1000000000000000000"), None)
        for seq, fee in enumerate(values, 1):
            self.j.lot_fills.apply_fill_v2(fill_v2(seq=seq, fee=fee))
        self.j.lot_fills.complete_fee(completion(trade="trade-4", fee=D("-.000000000000000001")))
        self.assertEqual(current(self.j).lot.fee_quality, lots.FeeQuality("MANAGED", D(0), 0))
        before = current(self.j)
        self.reopen()
        self.assertEqual(current(self.j), before)

    def test_b01_completion_idempotence_and_numeric_equivalence(self):
        self.seed()
        saved = self.j.lot_fills.complete_fee(completion(fee=D(".10")))
        before = current(self.j)
        for fee in (D(".1"), D(".100")):
            self.assertEqual(self.j.lot_fills.complete_fee(completion(fee=fee)), replace(saved, replayed=True))
        self.reopen()
        self.assertEqual(current(self.j), before)
        self.assertEqual(self.j.lot_fills.complete_fee(completion(fee=D(".1"))), replace(saved, replayed=True))
        self.assertEqual(self.j.lot_fills.recover().fee_completion_count, 1)

    def test_b02_conflict_and_known_fee_not_pending(self):
        self.seed()
        self.j.lot_fills.complete_fee(completion())
        self.reject("write_conflict", lambda: self.j.lot_fills.complete_fee(completion(fee=D(1))))
        self.assertTrue(self.j.lot_fills.recover().storage_ready)
        opening(self.j, order="other", seq=2)
        self.j.lot_fills.apply_fill_v2(fill_v2(order="other", quantity=D(3), fee=D(0)))
        self.reject("fee_not_pending", lambda: self.j.lot_fills.complete_fee(completion(order="other")))

    def test_b03_original_unknown_replay_and_changed_known_conflict(self):
        saved = self.seed()
        terminal(self.j)
        self.j.lot_fills.complete_fee(completion())
        self.assertEqual(self.j.lot_fills.apply_fill_v2(fill_v2(quantity=D(3))), replace(saved, replayed=True))
        self.reject("write_conflict", lambda: self.j.lot_fills.apply_fill_v2(fill_v2(quantity=D(3), fee=D(0))))
        self.reject("order_unavailable", lambda: self.j.lot_fills.apply_fill_v2(fill_v2(seq=2)))

    def test_b04_absent_wrong_scope_order_trade_and_rejected(self):
        self.seed()
        for event in (completion(order="missing"), completion(trade="missing")):
            self.reject("fee_target_not_found", lambda: self.j.lot_fills.complete_fee(event))
        self.reject("scope_mismatch", lambda: self.j.lot_fills.complete_fee(replace(completion(), scope=lots.LotScope("other", "local-sim"))))
        opening(self.j, order="rejected", seq=2)
        terminal(self.j, order="rejected", seq=0, quantity=D(0), status="REJECTED")
        self.reject("fee_target_not_found", lambda: self.j.lot_fills.complete_fee(completion(order="rejected")))

    def test_c01_partial_cancel_completion_does_not_change_order(self):
        opening(self.j)
        self.j.lot_fills.apply_fill_v2(fill_v2())
        terminal(self.j, quantity=D(1), status="CANCELED")
        before = tuple(dict(r) for r in self.j.connection.execute("SELECT * FROM lot_fill_orders"))
        self.j.lot_fills.complete_fee(completion(fee=D("-.1")))
        self.assertEqual(before, tuple(dict(r) for r in self.j.connection.execute("SELECT * FROM lot_fill_orders")))
        self.assertFalse(current(self.j).opening_unresolved)
        self.assertEqual(self.capture().pending, ())

    def test_c02_c03_c04_c05_complete_contract_trace(self):
        opening(self.j)
        self.j.lot_fills.apply_fill_v2(fill_v2())
        self.j.lot_fills.apply_fill_v2(fill_v2(seq=2, quantity=D(2), fee=D(".02")))
        terminal(self.j, seq=2)
        old = current(self.j).lot
        close_order(self.j)
        before = current(self.j)
        captured = self.capture()
        zero = self.j.lot_fills.complete_fee(completion())
        after = current(self.j)
        self.assertEqual(after.lot, replace(before.lot, revision=before.lot.revision + 1,
                          fee_quality=lots.FeeQuality("MANAGED", D(".02"), 0)))
        self.assertEqual((after.opening_unresolved, after.closing_unresolved), (False, True))
        self.assertNotEqual(captured.capture_id, self.capture().capture_id)
        self.assertEqual(self.j.lot_fills.complete_fee(completion(fee=D("-0"))), replace(zero, replayed=True))
        self.reopen()
        self.assertEqual(current(self.j), after)
        self.j.lot_fills.apply_fill_v2(fill_v2(order="close", quantity=D(3)))
        terminal(self.j, order="close")
        closed = current(self.j)
        self.assertEqual(closed.lot.remaining_qty, D(0))
        self.assertEqual(self.capture().pending, ())
        self.j.lot_fills.complete_fee(completion(order="close", fee=D("-.01")))
        final = current(self.j)
        self.assertEqual(final.lot, replace(closed.lot, revision=closed.lot.revision + 1,
                          fee_quality=lots.FeeQuality("MANAGED", D(".01"), 0)))
        self.assertFalse(final.opening_unresolved or final.closing_unresolved)
        self.assertEqual(final.lot.average_entry, old.average_entry)
        self.assertEqual(len(self.capture().lots), 1)
        self.reopen()
        self.assertEqual(current(self.j), final)

    def test_c05_new_stale_close_rejected_after_completion(self):
        self.seed()
        terminal(self.j)
        old = current(self.j).lot
        self.j.lot_fills.complete_fee(completion())
        self.reject("revision_conflict", lambda: self.j.lot_fills.bind_order(source_id="synthetic", order_id="stale",
            context=lots.IntentContext(scope(), "lot-bot", contract(), 2, False),
            intent=lots.CloseLot(old.lot_id, None, old.revision)))

    def test_d01_d02_d03_corruption_rejected(self):
        self.seed()
        self.j.lot_fills.complete_fee(completion())
        for sql in (
            "DELETE FROM lot_fee_completions;",
            "DELETE FROM lot_revisions WHERE revision=2;",
            "UPDATE lot_fee_completions SET seq=seq+1;",
            "UPDATE lot_fee_completions SET seq=1;",
            "UPDATE lot_fee_completions SET trade_id='orphan';",
            "UPDATE lot_fee_completions SET revision=1,commit_seq=1;",
            "UPDATE lot_fee_completions SET fee_paid='1';",
            "UPDATE lot_revisions SET known_fee_subtotal='1' WHERE revision=2;",
            "UPDATE lot_revisions SET fee_unknown_fill_count=2 WHERE revision=2;",
            "UPDATE lot_revisions SET fee_coverage='UNVERIFIED',known_fee_subtotal=NULL,fee_unknown_fill_count=NULL WHERE revision=2;",
            "UPDATE lot_revisions SET opening_unresolved=0 WHERE revision=2;",
            "UPDATE lot_fee_completions SET request_json=replace(request_json,'\"event_version\":2','\"event_version\":1');",
        ):
            with self.subTest(sql=sql):
                self.corrupt(sql)

    def test_d04_each_write_failure_rolls_back(self):
        self.seed()
        before = current(self.j)
        for prefix in ("INSERT INTO lot_revisions", "UPDATE lot_heads", "UPDATE lot_bindings", "INSERT INTO lot_fee_completions"):
            with self.subTest(prefix=prefix):
                real = self.j.connection
                wrapped = FailingConnection(real, prefix)
                self.j.connection = self.j.lots.db = self.j.lot_fills.db = wrapped
                self.reject("storage_unavailable", lambda: self.j.lot_fills.complete_fee(completion()))
                self.j.connection = self.j.lots.db = self.j.lot_fills.db = real
                self.reopen()
                self.assertEqual(current(self.j), before)
                self.assertEqual(self.j.lot_fills.recover().fee_completion_count, 0)

    def test_d02_deleted_nonzero_tail_completion_is_rejected(self):
        self.seed()
        self.j.lot_fills.complete_fee(completion(fee=D(".1")))
        self.corrupt("DELETE FROM lot_fee_completions;")

    def test_d06_all_versions_receipts_and_watermarks_survive_reopen(self):
        self.seed()
        terminal(self.j)
        close_order(self.j)
        self.j.lot_fills.complete_fee(completion())
        from catos.lot_schema8 import FILL_TABLES
        tables = ("lot_bindings", "lot_heads", "lot_revisions", *FILL_TABLES)
        before = {name: tuple(tuple(r) for r in self.j.connection.execute(f"SELECT * FROM {name} ORDER BY rowid")) for name in tables}
        self.reopen()
        after = {name: tuple(tuple(r) for r in self.j.connection.execute(f"SELECT * FROM {name} ORDER BY rowid")) for name in tables}
        self.assertEqual(before, after)
        self.assertTrue(current(self.j).closing_unresolved)

    def test_d05_real_process_kill_before_and_after_commit(self):
        self.seed()
        baseline = current(self.j)
        self.j.close()
        self.j = None
        context = multiprocessing.get_context("spawn")
        for phase in ("before", "after"):
            with self.subTest(phase=phase):
                parent, child = context.Pipe()
                process = context.Process(target=crash_worker, args=(str(self.path), phase, child))
                process.start()
                child.close()
                try:
                    self.assertTrue(parent.poll(20), "child did not reach COMMIT boundary")
                    self.assertEqual(parent.recv(), "boundary")
                finally:
                    process.terminate()
                    process.join(10)
                    parent.close()
                self.assertFalse(process.is_alive())
                self.j = Journal(self.path, "fake-account", D(100), lot_schema_version=8)
                if phase == "before":
                    self.assertEqual(current(self.j), baseline)
                    self.assertEqual(self.j.lot_fills.recover().fee_completion_count, 0)
                    self.j.close()
                    self.j = None
                else:
                    result = self.j.lot_fills.complete_fee(completion(fee=D(".1")))
                    self.assertTrue(result.replayed)
                    self.assertEqual(current(self.j).lot.fee_quality, lots.FeeQuality("MANAGED", D(".1"), 0))
                    self.assertEqual(self.j.lot_fills.recover().fee_completion_count, 1)

    def test_e02_mismatched_open_does_not_write(self):
        self.seed()
        self.j.close()
        self.j = None
        before = self.path.read_bytes()
        self.reject("schema_version_mismatch", lambda: Journal(self.path, "fake-account", D(100)))
        self.assertEqual(self.path.read_bytes(), before)
        old_path = self.path.with_name("schema7.sqlite3")
        old = Journal(old_path, "fake-account", D(100))
        old.close()
        before = old_path.read_bytes()
        self.reject("schema_version_mismatch", lambda: Journal(old_path, "fake-account", D(100), lot_schema_version=8))
        self.assertEqual(old_path.read_bytes(), before)

    def test_e03_wrong_api_rejected(self):
        self.reject("unsupported_fee_version", lambda: self.j.lot_fills.apply_fill(fill()))
        self.reject("unsupported_fee_version", lambda: self.j.capture_lot_snapshot(scope=scope(),
            inst_id=contract().inst_id, observed_at_ms=90, valid_until_ms=110))
        with closing(Journal(self.path.with_name("old.sqlite3"), "fake-account", D(100))) as old:
            self.reject("unsupported_fee_version", lambda: old.lot_fills.apply_fill_v2(fill_v2()))
            self.reject("unsupported_fee_version", lambda: old.lot_fills.complete_fee(completion()))

    def test_e04_unverified_only_external_snapshot(self):
        value = external_lot()
        args = dict(scope=scope(), bot_id="lot-bot", write_id="external", open_event_seq=1,
                    after=value, opening_unresolved=False, closing_unresolved=False)
        self.reject("unmanaged_lot", lambda: self.j.lots.create_v2(**dict(args,
            after=replace(value, fee_quality=lots.FeeQuality("MANAGED", D(0), 0)))))
        self.j.lots.create_v2(**args)
        self.assertEqual(current(self.j).lot, value)
        self.reopen()
        self.assertIsNone(current(self.j).lot.fee_quality.fee_complete)

    def test_f02_quality_hash_and_numeric_identity(self):
        self.seed(fee=D(".10"))
        capture = self.capture()
        stored = capture.lots[0]
        equal = replace(capture, lots=(replace(stored, lot=replace(stored.lot,
            fee_quality=lots.FeeQuality("MANAGED", D(".1"), 0))),))
        self.assertEqual(lot_snapshot._capture_id(equal), capture.capture_id)
        forged = replace(capture, lots=(replace(stored, lot=replace(stored.lot,
            fee_quality=lots.FeeQuality("MANAGED", D(".1"), 1))),))
        self.assertNotEqual(lot_snapshot._capture_id(forged), capture.capture_id)
        with self.assertRaises(ScenarioInputError):
            observe_synthetic_scenario_v2(capture=forged, scenario=evidence(forged), now_ms=100)

    def test_f01_capture_pins_fee_and_revision_before_concurrent_commit(self):
        self.seed()
        before = self.capture()
        with closing(Journal(self.path, "fake-account", D(100), lot_schema_version=8)) as writer:
            real = self.j.connection

            class CaptureConnection:
                fired = False

                def __getattr__(self, name):
                    return getattr(real, name)

                def execute(self, sql, args=()):
                    result = real.execute(sql, args)
                    if sql == "SELECT * FROM metadata" and not self.fired:
                        self.fired = True
                        writer.lot_fills.complete_fee(completion())
                    return result

            wrapper = CaptureConnection()
            self.j.connection = self.j.lots.db = self.j.lot_fills.db = wrapper
            try:
                pinned = self.capture()
            finally:
                self.j.connection = self.j.lots.db = self.j.lot_fills.db = real
            self.assertTrue(wrapper.fired)
            self.assertEqual(pinned, before)
        after = self.capture()
        self.assertNotEqual(after.capture_id, before.capture_id)
        self.assertEqual(after.lots[0].lot.revision, before.lots[0].lot.revision + 1)
        self.assertTrue(after.lots[0].lot.fee_quality.fee_complete)

    def test_e04_reserved_prefixes_and_no_change_still_rejected(self):
        value = external_lot()
        for prefix in ("s3_reserved", "s9_reserved"):
            self.reject("reserved_write_id", lambda: self.j.lots.create_v2(scope=scope(), bot_id="lot-bot",
                write_id=prefix, open_event_seq=1, after=value, opening_unresolved=False, closing_unresolved=False))
        self.j.lots.create_v2(scope=scope(), bot_id="lot-bot", write_id="external", open_event_seq=1,
            after=value, opening_unresolved=False, closing_unresolved=False)
        self.reject("no_change", lambda: self.j.lots.replace_v2(scope=scope(), bot_id="lot-bot",
            write_id="unchanged", expected_revision=1, after=replace(value, revision=2),
            opening_unresolved=False, closing_unresolved=False))

    def test_b01_completion_lookup_does_not_join_fill_count(self):
        self.seed()
        args = dict(scope=scope(), source_id="synthetic", inst_id=contract().inst_id, order_id="open")
        self.assertIsNone(self.j.lot_fills.get_fee_completion(**args, trade_id="trade-1"))
        fills = self.j.lot_fills.list_fills(**args)
        saved = self.j.lot_fills.complete_fee(completion())
        self.assertEqual(self.j.lot_fills.get_fee_completion(**args, trade_id="trade-1"), saved)
        self.assertEqual(self.j.lot_fills.list_fills(**args), fills)
        self.assertEqual(self.j.lot_fills.recover().fill_count, 1)

    def test_a03_long_average_and_realized_match_known_fee_path(self):
        with closing(Journal(self.path.with_name("known.sqlite3"), "fake-account", D(100))) as known:
            known.lots.register_binding(scope=scope(), bot_id="lot-bot", contract=contract())
            for journal in (self.j, known):
                opening(journal)
            for seq, quantity, price in ((1, D(1), D(100)), (2, D(2), D(130))):
                self.j.lot_fills.apply_fill_v2(fill_v2(seq=seq, quantity=quantity, price=price))
                known.lot_fills.apply_fill(fill(seq=seq, quantity=quantity, price=price))
            for journal in (self.j, known):
                terminal(journal, seq=2)
                close_order(journal)
            self.j.lot_fills.apply_fill_v2(fill_v2(order="close", quantity=D(2), price=D(140)))
            known.lot_fills.apply_fill(fill(order="close", quantity=D(2), price=D(140)))
            new, old = current(self.j).lot, current(known).lot
            for name in ("opened_qty", "remaining_qty", "average_entry", "realized_pnl", "protection", "revision"):
                self.assertEqual(getattr(new, name), getattr(old, name))
            self.assertEqual(new.average_entry, D(120))
            self.assertEqual(new.realized_pnl, D(".4"))
            self.assertEqual(new.fee_quality.fee_unknown_fill_count, 3)

    def test_a05_quality_derived_bounds(self):
        for subtotal in (D("1e100"), D("1e-149"), D("1." + "1" * 50)):
            with self.subTest(subtotal=subtotal), self.assertRaises(lots.LotError):
                lots.FeeQuality("MANAGED", subtotal, 0)
        for subtotal in (D("1e99"), D("1e-148"), D("1." + "1" * 49)):
            self.assertTrue(lots.FeeQuality("MANAGED", subtotal, 0).fee_complete)

    def test_e02_legacy_selection_is_rejected_before_pragmas(self):
        for version in (1, 2, 3, 4, 5, 6, 9):
            path = self.path.with_name(f"version-{version}.sqlite3")
            with closing(sqlite3.connect(path)) as db:
                db.execute(f"PRAGMA user_version={version}")
                db.commit()
            before = path.read_bytes()
            self.reject("schema_version_mismatch", lambda: Journal(path, "fake-account", D(100), lot_schema_version=8))
            self.assertEqual(path.read_bytes(), before)

    def test_d03_corruption_invalidates_handle(self):
        self.seed()
        self.j.lot_fills.complete_fee(completion())
        self.j.connection.execute("DELETE FROM lot_fee_completions")
        self.reject("integrity_error", self.j.lot_fills.recover)
        self.reject("storage_unavailable", self.j.lot_fills.recover)

    def test_f03_f04_f05_fee_quality_separate_from_exposure(self):
        self.seed()
        terminal(self.j)
        capture = self.capture()
        scene = evidence(capture, physical_quantity=D(3))
        before = observe_synthetic_scenario_v2(capture=capture, scenario=scene, now_ms=100)
        self.assertFalse(before.fee_quality[0].fee_complete)
        self.assertEqual(before.report.comparison_status, "MATCH")
        self.assertTrue(before.report.pending_complete)
        self.assertEqual(before.report.reasons, ())
        html = render_synthetic_scenario_report_v2(capture=capture, scenario=scene, now_ms=100)
        self.assertIn("fee_incomplete", html)
        self.assertIn("已知費用小計，非全部費用", html)
        self.j.lot_fills.complete_fee(completion())
        capture = self.capture()
        scene = evidence(capture, physical_quantity=D(3))
        after = observe_synthetic_scenario_v2(capture=capture, scenario=scene, now_ms=100)
        self.assertEqual(before.report, after.report)
        self.assertTrue(after.fee_quality[0].fee_complete)
        html = render_synthetic_scenario_report_v2(capture=capture, scenario=scene, now_ms=100)
        self.assertIn("費用已完整", html)
        self.assertIn("funding 未知", html)
        with self.assertRaises(ScenarioInputError):
            observe_synthetic_scenario(capture=capture, scenario=scene, now_ms=100)

    def test_f04_empty_and_unverified_render(self):
        capture = self.capture()
        self.assertIn("無 Lot 費用資料", render_synthetic_scenario_report_v2(capture=capture,
            scenario=evidence(capture), now_ms=100))
        self.j.lots.create_v2(scope=scope(), bot_id="lot-bot", write_id="external", open_event_seq=1,
            after=external_lot(), opening_unresolved=False, closing_unresolved=False)
        capture = self.capture()
        html = render_synthetic_scenario_report_v2(capture=capture, scenario=evidence(capture), now_ms=100)
        self.assertIn("fee_coverage_unverified", html)
        self.assertIn("不可用", html)

    def test_f04_long_decimal_and_fee_table_escape(self):
        self.seed()
        capture = self.capture()
        amount = D("12345678901234567890123456789012345678901234567890")
        stored = capture.lots[0]
        capture = replace(capture, lots=(replace(stored, lot=replace(stored.lot,
            fee_quality=lots.FeeQuality("MANAGED", amount, 1))),))
        capture = replace(capture, capture_id=lot_snapshot._capture_id(capture))
        html = render_synthetic_scenario_report_v2(capture=capture, scenario=evidence(capture), now_ms=100)
        self.assertIn(format(amount, "f"), html)
        from catos.lot_scenario import LotFeeObservation
        from catos.lot_scenario_report import _fee_section
        section = _fee_section((LotFeeObservation("<script>", "a&b", 1, "UNVERIFIED", None, None, None),))
        self.assertNotIn("<script>", section)
        self.assertIn("&lt;script&gt;", section)
        self.assertIn("a&amp;b", section)


if __name__ == "__main__":
    unittest.main()
