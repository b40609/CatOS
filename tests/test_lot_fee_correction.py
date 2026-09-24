"""S10 synthetic acceptance tests; execution belongs to independent validation."""

from contextlib import closing
from dataclasses import replace
from decimal import Decimal as D, Inexact, InvalidOperation, Overflow, Underflow, localcontext
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import multiprocessing
import sqlite3
import tempfile
import unittest

from catos import ipc, lots, lot_snapshot, research
from catos.journal import Journal
from catos.lot_accounting import FeeCorrection, EffectiveFee, correct_fee
from catos.lot_journal import LotStorageError, _hash, _json
from catos.lot_schema9 import FILL_TABLES
from catos.lot_scenario import (observe_synthetic_scenario_v2, observe_synthetic_scenario_v3,
                                ScenarioInputError)
from catos.lot_scenario_report import render_synthetic_scenario_report_v3
from lot_journal_helpers import scope, contract
from lot_fill_helpers import opening, terminal, current, close_order
from test_lot_fee_completion import fill_v2, completion, external_lot
from test_lot_journal import FailingConnection
from test_lot_scenario import evidence


def identity(*, order="open", trade="trade-1"):
    return dict(scope=scope(), source_id="synthetic", inst_id=contract().inst_id,
                order_id=order, trade_id=trade)


def correction(*, predecessor=2, fee=D(".015"), cid="C1", order="open", trade="trade-1"):
    return FeeCorrection(**identity(order=order, trade=trade), correction_id=cid,
                         predecessor_event_seq=predecessor, fee_paid=fee)


def crash_worker(path, phase, pipe):
    journal = Journal(path, "fake-account", D(100), lot_schema_version=9)
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
    journal.lot_fills.correct_fee(correction())
    pipe.send("unexpected-ack")


class CorrectionTypeTests(unittest.TestCase):
    def assert_code(self, code, callback):
        with self.assertRaises((lots.LotError, LotStorageError)) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def test_a01_a02_input_types_and_bounds(self):
        good = correction()
        for changes in ({"fee_paid": 0.1}, {"fee_paid": 1}, {"fee_paid": True},
                        {"fee_paid": D("NaN")}, {"fee_paid": D("Infinity")},
                        {"fee_paid": D("1e19")}, {"fee_paid": D("1e-19")},
                        {"fee_paid": D("1." + "0" * 28)},
                        {"predecessor_event_seq": True}, {"predecessor_event_seq": 0},
                        {"predecessor_event_seq": ipc.MAX_INTEGER + 1},
                        {"correction_id": None}, {"correction_id": ""},
                        {"correction_id": "x" * 65}, {"trade_id": "bad/path"}):
            with self.subTest(changes=changes):
                self.assert_code("invalid_fee_correction", lambda: replace(good, **changes))
        self.assert_code("unsupported_fee", lambda: replace(good, fee_currency="BTC"))
        self.assert_code("scope_mismatch", lambda: replace(good, scope=lots.LotScope("fake-account", "demo")))
        for fee in (D(0), D("-0"), D("-.01"), D("1e18"), D("1e-18")):
            self.assertEqual(replace(good, fee_paid=fee).fee_paid, fee)

    def test_a03_effective_fee_three_way_pairing(self):
        unknown = EffectiveFee(**identity(), fee_state="UNKNOWN", fee_paid=None,
                              fee_currency="USDT", effective_event_seq=None, effective_event_kind=None)
        for changes in ({"fee_paid": D(0)}, {"effective_event_seq": 2}, {"effective_event_kind": "fill"}):
            self.assert_code("invalid_fee_state", lambda: replace(unknown, **changes))
        for kind in ("fill", "fee_completion", "fee_correction"):
            known = replace(unknown, fee_state="KNOWN", fee_paid=D(0), effective_event_seq=2,
                            effective_event_kind=kind)
            self.assertEqual(known.fee_paid, D(0))

    def test_c01_two_steps_and_external_context(self):
        before = replace(external_lot(), fee_quality=lots.FeeQuality("MANAGED", D(".03"), 2))
        with localcontext() as ctx:
            ctx.prec = 2
            ctx.traps[Inexact] = True
            after = correct_fee(before, correction(), D(".02"))
        self.assertEqual(after, replace(before, revision=2,
                         fee_quality=lots.FeeQuality("MANAGED", D(".025"), 2)))

    def test_c02_c04_reducer_only_rounding_not_a_reachable_journal_fixture(self):
        # This constructed subtotal is a reducer boundary, NOT replay evidence.
        before = replace(external_lot(), fee_quality=lots.FeeQuality("MANAGED", D("1e50"), 0))
        after = correct_fee(before, correction(fee=D(".2")), D(".1"))
        self.assertEqual(after.fee_quality.known_fee_subtotal, D("1e50"))
        self.assertEqual(after.revision, before.revision + 1)
        self.assert_code("no_change", lambda: correct_fee(before, correction(fee=D(".10")), D(".1")))

    def test_c02_p2a_is_not_delta_first_at_rounding_boundary(self):
        # Hand-derived reducer-only boundary. No claim of a feasible fill history.
        subtotal, old, new = D("1e33"), D("6e-18"), D("6e-17")
        before = replace(external_lot(), fee_quality=lots.FeeQuality("MANAGED", subtotal, 0))
        after = correct_fee(before, correction(fee=new), old)
        self.assertEqual(after.fee_quality.known_fee_subtotal, D("1e33"))
        with localcontext(research._CONTEXT):
            self.assertEqual(subtotal - old, D("9" * 33 + "." + "9" * 17))
            delta_first = subtotal + (new - old)
        self.assertEqual(delta_first, D("1" + "0" * 33 + "." + "0" * 15 + "1"))
        self.assertNotEqual(after.fee_quality.known_fee_subtotal, delta_first)

    def test_c03_each_intermediate_is_validated_and_decimal_failures_reject(self):
        before = replace(external_lot(), fee_quality=lots.FeeQuality("MANAGED", D(".03"), 0))
        from catos import lot_accounting
        real = lots._decimal
        seen = []

        def validate(value, code, **kwargs):
            if code == "invalid_decimal":
                seen.append(value)
                if value == D(".01"):
                    raise lots.LotError("invalid_decimal")
            return real(value, code, **kwargs)

        # Controlled guard fault: proves the second step cannot rescue a failed first step.
        with patch.object(lot_accounting.lots, "_decimal", side_effect=validate):
            self.assert_code("invalid_decimal", lambda: correct_fee(before, correction(), D(".02")))
        self.assertEqual(seen[-1], D(".01"))
        self.assertNotIn(D(".025"), seen)
        for error in (Underflow, Overflow, InvalidOperation):
            with patch.object(lot_accounting, "localcontext", side_effect=error):
                self.assert_code("invalid_decimal", lambda: correct_fee(before, correction(), D(".02")))
        self.assert_code("sequence_exhausted", lambda: correct_fee(
            replace(before, revision=ipc.MAX_INTEGER), correction(), D(".02")))


class CorrectionJournalTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "s10.sqlite3"
        self.j = Journal(self.path, "fake-account", D(100), lot_schema_version=9)
        self.addCleanup(lambda: self.j.close() if self.j is not None else None)
        self.j.lots.register_binding(scope=scope(), bot_id="lot-bot", contract=contract())

    def reject(self, code, callback):
        with self.assertRaises((LotStorageError, lots.LotError)) as caught:
            callback()
        self.assertEqual(caught.exception.code, code)

    def seed(self, *, fee=D(".02"), side="long"):
        opening(self.j, side=side)
        return self.j.lot_fills.apply_fill_v2(fill_v2(quantity=D(3), fee=fee))

    def capture(self):
        return self.j.capture_lot_snapshot_v3(scope=scope(), inst_id=contract().inst_id,
                                            observed_at_ms=90, valid_until_ms=110)

    def reopen(self):
        self.j.close()
        self.j = None
        self.j = Journal(self.path, "fake-account", D(100), lot_schema_version=9)

    def dump(self):
        tables = ("lot_bindings", "lot_heads", "lot_revisions", *FILL_TABLES)
        return {name: tuple(tuple(r) for r in self.j.connection.execute(f"SELECT * FROM {name} ORDER BY rowid"))
                for name in tables}

    def damaged_copy(self, mutate):
        path = self.path.with_name("damaged.sqlite3")
        with closing(sqlite3.connect(path)) as db:
            self.j.connection.backup(db)
            mutate(db)
            db.commit()
        self.reject("integrity_error", lambda: Journal(path, "fake-account", D(100), lot_schema_version=9))

    def test_schema9_lotv2_and_request_versions(self):
        self.seed()
        self.assertEqual(self.j.connection.execute("PRAGMA user_version").fetchone()[0], 9)
        row = self.j.connection.execute("SELECT * FROM lot_revisions").fetchone()
        request = json.loads(row["request_json"])
        self.assertEqual(request["format_version"], 3)
        self.assertEqual(request["after"]["snapshot_version"], 2)
        self.assertTrue(row["write_id"].startswith("s10_"))
        self.assertEqual(len(row["write_id"]), 64)
        self.assertIs(type(current(self.j).lot), lots.LotV2)
        for table in ("lot_fill_orders", "lot_fill_events"):
            payload = json.loads(self.j.connection.execute(f"SELECT request_json FROM {table}").fetchone()[0])
            self.assertEqual(payload["event_version"], 3)

    def test_a03_b05_missing_unknown_completion_and_effective_source(self):
        self.assertIsNone(self.j.lot_fills.get_effective_fee(**identity()))
        self.reject("fee_target_not_found", lambda: self.j.lot_fills.correct_fee(correction()))
        self.seed(fee=None)
        unknown = self.j.lot_fills.get_effective_fee(**identity())
        self.assertEqual((unknown.fee_state, unknown.fee_paid, unknown.effective_event_seq), ("UNKNOWN", None, None))
        self.reject("fee_not_known", lambda: self.j.lot_fills.correct_fee(correction()))
        saved = self.j.lot_fills.complete_fee(completion(fee=D(".02")))
        known = self.j.lot_fills.get_effective_fee(**identity())
        self.assertEqual((known.effective_event_kind, known.effective_event_seq), ("fee_completion", saved.event_seq))
        changed = self.j.lot_fills.correct_fee(correction(predecessor=saved.event_seq))
        fee = self.j.lot_fills.get_effective_fee(**identity())
        self.assertEqual((fee.fee_paid, fee.effective_event_kind, fee.effective_event_seq),
                         (D(".015"), "fee_correction", changed.event_seq))

    def test_b01_replay_priority_and_original_receipts(self):
        original = self.seed()
        first = self.j.lot_fills.correct_fee(correction())
        self.j.lot_fills.correct_fee(correction(predecessor=first.event_seq, cid="C2", fee=D(".01")))
        terminal(self.j)
        before = self.dump()
        self.assertEqual(self.j.lot_fills.correct_fee(correction(fee=D(".0150"))), replace(first, replayed=True))
        self.assertEqual(self.j.lot_fills.get_fee_correction(**identity(), correction_id="C1"), first)
        self.reject("write_conflict", lambda: self.j.lot_fills.correct_fee(correction(fee=D(".016"))))
        self.assertEqual(self.j.lot_fills.apply_fill_v2(fill_v2(quantity=D(3), fee=D(".02"))),
                         replace(original, replayed=True))
        self.assertEqual(self.dump(), before)

    def test_b02_no_change_has_no_receipt_or_identity_reservation(self):
        self.seed()
        before, captured = self.dump(), self.capture()
        self.reject("no_change", lambda: self.j.lot_fills.correct_fee(correction(fee=D(".020"))))
        self.assertIsNone(self.j.lot_fills.get_fee_correction(**identity(), correction_id="C1"))
        self.assertEqual(self.dump(), before)
        self.assertEqual(self.capture(), captured)
        self.assertFalse(self.j.lot_fills.correct_fee(correction()).replayed)

    def test_b02_negative_zero_no_change(self):
        self.seed(fee=D(0))
        self.reject("no_change", lambda: self.j.lot_fills.correct_fee(correction(fee=D("-0"))))

    def test_b03_identity_is_scoped_to_trade(self):
        opening(self.j)
        one = self.j.lot_fills.apply_fill_v2(fill_v2(fee=D(".02")))
        two = self.j.lot_fills.apply_fill_v2(fill_v2(seq=2, quantity=D(2), fee=D(".03")))
        self.j.lot_fills.correct_fee(correction(predecessor=one.event_seq, cid="shared"))
        self.j.lot_fills.correct_fee(correction(predecessor=two.event_seq, cid="shared", trade="trade-2"))
        self.assertEqual(self.j.lot_fills.recover().fee_correction_count, 2)

    def test_b03_b04_b05_stale_query_and_aba_reject(self):
        self.seed()
        observed = self.j.lot_fills.get_effective_fee(**identity())
        with closing(Journal(self.path, "fake-account", D(100), lot_schema_version=9)) as other:
            first = other.lot_fills.correct_fee(correction())
        self.reject("fee_predecessor_conflict", lambda: self.j.lot_fills.correct_fee(
            correction(predecessor=observed.effective_event_seq, cid="racer", fee=D(".03"))))
        second = self.j.lot_fills.correct_fee(correction(predecessor=first.event_seq, cid="C2", fee=D(".02")))
        for seq in (1, 2, first.event_seq, second.event_seq + 1):
            self.reject("fee_predecessor_conflict", lambda: self.j.lot_fills.correct_fee(
                correction(predecessor=seq, cid="stale", fee=D(".02"))))
        self.reject("no_change", lambda: self.j.lot_fills.correct_fee(
            correction(predecessor=second.event_seq, cid="stale", fee=D(".02"))))

    def test_b04_other_trade_and_terminal_are_not_predecessors(self):
        opening(self.j)
        self.j.lot_fills.apply_fill_v2(fill_v2(fee=D(".02")))
        other = self.j.lot_fills.apply_fill_v2(fill_v2(seq=2, quantity=D(2), fee=D(".02")))
        done = terminal(self.j, seq=2)
        for seq in (other.event_seq, done.event_seq):
            self.reject("fee_predecessor_conflict", lambda: self.j.lot_fills.correct_fee(correction(predecessor=seq)))

    def test_c05_contract_trace_and_reopen(self):
        opening(self.j)
        self.j.lot_fills.apply_fill_v2(fill_v2(fee=D(".02")))
        original_unknown = self.j.lot_fills.apply_fill_v2(fill_v2(seq=2, quantity=D(2)))
        terminal(self.j, seq=2)
        close_order(self.j)
        before = current(self.j)
        first = self.j.lot_fills.correct_fee(correction())
        self.assertEqual(first.event_seq, 6)
        changed = current(self.j)
        self.assertEqual(changed.lot, replace(before.lot, revision=5,
                         fee_quality=lots.FeeQuality("MANAGED", D(".015"), 1)))
        self.assertEqual((changed.opening_unresolved, changed.closing_unresolved), (False, True))
        comp = self.j.lot_fills.complete_fee(completion(trade="trade-2", fee=D(".01")))
        self.j.lot_fills.correct_fee(correction(predecessor=7, cid="C2", trade="trade-2", fee=D(0)))
        self.j.lot_fills.correct_fee(correction(predecessor=6, cid="C3", fee=D(".02")))
        self.j.lot_fills.apply_fill_v2(fill_v2(order="close", quantity=D(3), fee=D(".01")))
        terminal(self.j, order="close")
        closed = current(self.j)
        last = self.j.lot_fills.correct_fee(correction(predecessor=10, cid="C4", order="close", fee=D("-.005")))
        self.assertEqual((last.event_seq, last.revision), (12, 11))
        final = current(self.j)
        self.assertEqual(final.lot, replace(closed.lot, revision=11,
                         fee_quality=lots.FeeQuality("MANAGED", D(".015"), 0)))
        self.assertEqual((final.lot.remaining_qty, final.lot.realized_pnl, final.lot.funding_paid), (D(0), D(0), None))
        self.assertFalse(final.opening_unresolved or final.closing_unresolved)
        self.assertEqual(self.j.lot_fills.apply_fill_v2(fill_v2(seq=2, quantity=D(2))), replace(original_unknown, replayed=True))
        self.assertEqual(self.j.lot_fills.complete_fee(completion(trade="trade-2", fee=D(".010"))), replace(comp, replayed=True))
        report = self.j.lot_fills.recover()
        self.assertEqual((report.order_count, report.fill_count, report.terminal_count,
                          report.fee_completion_count, report.fee_correction_count), (2, 3, 2, 1, 4))
        state = self.dump()
        self.reopen()
        self.assertEqual(self.dump(), state)
        self.assertEqual(current(self.j), final)
        self.assertEqual(len(self.capture().lots), 1)

    def test_c05_short_partial_close_preserves_nonfee_fields(self):
        self.seed(side="short")
        terminal(self.j)
        close_order(self.j)
        self.j.lot_fills.apply_fill_v2(fill_v2(order="close", quantity=D(1), price=D(80), fee=D(".01")))
        before = current(self.j)
        self.j.lot_fills.correct_fee(correction(fee=D("-.01")))
        after = current(self.j)
        self.assertEqual(after.lot, replace(before.lot, revision=before.lot.revision + 1,
                         fee_quality=lots.FeeQuality("MANAGED", D(0), 0)))
        self.assertEqual(after.lot.realized_pnl, D(".2"))
        self.assertTrue(after.closing_unresolved)

    def test_c05_partial_cancel_and_c06_stale_new_intent(self):
        opening(self.j)
        self.j.lot_fills.apply_fill_v2(fill_v2(fee=D(".02")))
        terminal(self.j, quantity=D(1), status="CANCELED")
        old = current(self.j).lot
        self.j.lot_fills.correct_fee(correction())
        self.assertFalse(current(self.j).opening_unresolved)
        self.reject("revision_conflict", lambda: self.j.lot_fills.bind_order(source_id="synthetic", order_id="stale",
            context=lots.IntentContext(scope(), "lot-bot", contract(), 2, False),
            intent=lots.CloseLot(old.lot_id, None, old.revision)))

    def test_a01_forged_input_revalidated_before_replay(self):
        self.seed()
        saved = self.j.lot_fills.correct_fee(correction())
        forged = correction()
        object.__setattr__(forged, "fee_paid", 0.015)
        self.reject("invalid_fee_correction", lambda: self.j.lot_fills.correct_fee(forged))
        self.assertEqual(self.j.lot_fills.get_fee_correction(**identity(), correction_id="C1"), saved)

    def test_d01_d02_corruption_and_tail_deletion(self):
        self.seed()
        self.j.lot_fills.correct_fee(correction())
        for sql in ("DELETE FROM lot_fee_corrections",
                    "DELETE FROM lot_revisions WHERE revision=2",
                    "UPDATE lot_fee_corrections SET fee_paid='1'",
                    "UPDATE lot_fee_corrections SET predecessor_event_seq=1",
                    "UPDATE lot_fee_corrections SET seq=4",
                    "UPDATE lot_fee_corrections SET trade_id='orphan'",
                    "UPDATE lot_revisions SET known_fee_subtotal='1' WHERE revision=2",
                    "UPDATE lot_revisions SET closing_unresolved=1 WHERE revision=2",
                    "UPDATE lot_revisions SET fee_unknown_fill_count=1 WHERE revision=2",
                    "UPDATE lot_fee_corrections SET revision=1,commit_seq=1"):
            with self.subTest(sql=sql):
                self.damaged_copy(lambda db: db.execute(sql))

    def test_d01_resigned_payloads_still_require_semantics(self):
        self.seed()
        self.j.lot_fills.correct_fee(correction())
        for changes in ({"event_version": 2}, {"event_version": True}, {"unexpected": 1},
                        {"predecessor_event_seq": 1}, {"fee_paid": "0.02"},
                        {"fee_paid": "0.0150"}, {"source_id": "another"}):
            def mutate(db):
                text = db.execute("SELECT request_json FROM lot_fee_corrections").fetchone()[0]
                payload = dict(json.loads(text), **changes)
                canonical = _json(payload)
                db.execute("UPDATE lot_fee_corrections SET request_json=?,request_hash=?",
                           (canonical, _hash(canonical)))
            with self.subTest(changes=changes):
                self.damaged_copy(mutate)

    def test_d02_all_public_s2_paths_require_s3_proof(self):
        self.seed()
        self.j.lot_fills.correct_fee(correction())
        lot = current(self.j).lot
        state = self.dump()
        actions = (
            lambda j: j.lots.get(scope=scope(), bot_id="lot-bot", lot_id=lot.lot_id),
            lambda j: j.lots.get_revision(scope=scope(), bot_id="lot-bot", lot_id=lot.lot_id, revision=1),
            lambda j: j.lots.list_current(scope=scope(), bot_id="lot-bot"),
            lambda j: j.lots.recover(),
            lambda j: j.lots.create_v2(scope=scope(), bot_id="lot-bot", write_id="attempt", open_event_seq=1,
                after=external_lot(), opening_unresolved=False, closing_unresolved=False),
            lambda j: j.lots.replace_v2(scope=scope(), bot_id="lot-bot", write_id="attempt", expected_revision=2,
                after=replace(lot, revision=3), opening_unresolved=True, closing_unresolved=False),
            lambda j: j.lot_fills.get_fee_correction(**identity(), correction_id="absent"),
            lambda j: j.lot_fills.get_effective_fee(**identity()),
            lambda j: j.lot_fills.correct_fee(correction()),
            lambda j: j.capture_lot_snapshot_v3(scope=scope(), inst_id=contract().inst_id,
                observed_at_ms=90, valid_until_ms=110),
        )
        for index, action in enumerate(actions):
            path = self.path.with_name(f"access-{index}.sqlite3")
            with closing(sqlite3.connect(path)) as db:
                self.j.connection.backup(db)
            with closing(Journal(path, "fake-account", D(100), lot_schema_version=9)) as damaged:
                damaged.connection.execute("DELETE FROM lot_fee_corrections")
                self.reject("integrity_error", lambda: action(damaged))
                self.reject("storage_unavailable", damaged.lots.recover)
        self.assertEqual(self.dump(), state)

    def test_d03_atomic_write_failures(self):
        self.seed()
        baseline = self.dump()
        for prefix in ("INSERT INTO lot_revisions", "UPDATE lot_heads", "UPDATE lot_bindings", "INSERT INTO lot_fee_corrections"):
            with self.subTest(prefix=prefix):
                real = self.j.connection
                wrapped = FailingConnection(real, prefix)
                self.j.connection = self.j.lots.db = self.j.lot_fills.db = wrapped
                try:
                    self.reject("storage_unavailable", lambda: self.j.lot_fills.correct_fee(correction()))
                finally:
                    self.j.connection = self.j.lots.db = self.j.lot_fills.db = real
                self.reopen()
                self.assertEqual(self.dump(), baseline)
                self.assertIsNone(self.j.lot_fills.get_fee_correction(**identity(), correction_id="C1"))

    def test_d04_real_process_commit_boundaries(self):
        self.seed()
        baseline = current(self.j)
        self.j.close()
        self.j = None
        context = multiprocessing.get_context("spawn")
        for phase in ("before", "after"):
            parent, child = context.Pipe()
            process = context.Process(target=crash_worker, args=(str(self.path), phase, child))
            process.start()
            child.close()
            try:
                self.assertTrue(parent.poll(20), "child did not reach commit boundary")
                self.assertEqual(parent.recv(), "boundary")
            finally:
                process.terminate()
                process.join(10)
                parent.close()
            self.assertFalse(process.is_alive())
            self.j = Journal(self.path, "fake-account", D(100), lot_schema_version=9)
            if phase == "before":
                self.assertEqual(current(self.j), baseline)
                self.assertIsNone(self.j.lot_fills.get_fee_correction(**identity(), correction_id="C1"))
                self.j.close()
                self.j = None
            else:
                saved = self.j.lot_fills.get_fee_correction(**identity(), correction_id="C1")
                self.assertIsNotNone(saved)
                self.assertEqual(self.j.lot_fills.correct_fee(correction()), replace(saved, replayed=True))
                self.assertEqual(current(self.j).lot.fee_quality.known_fee_subtotal, D(".015"))

    def test_e01_mismatched_versions_do_not_write(self):
        self.seed()
        self.j.close()
        self.j = None
        before = self.path.read_bytes()
        for version in (7, 8):
            self.reject("schema_version_mismatch", lambda: Journal(self.path, "fake-account", D(100), lot_schema_version=version))
            self.assertEqual(self.path.read_bytes(), before)
        for version in (7, 8):
            path = self.path.with_name(f"old-{version}.sqlite3")
            with closing(Journal(path, "fake-account", D(100), lot_schema_version=version)):
                pass
            before = path.read_bytes()
            self.reject("schema_version_mismatch", lambda: Journal(path, "fake-account", D(100), lot_schema_version=9))
            self.assertEqual(path.read_bytes(), before)
        for version in (0, 1, 6, 10):
            path = self.path.with_name(f"unknown-{version}.sqlite3")
            with closing(sqlite3.connect(path)) as db:
                db.execute("CREATE TABLE sentinel (value TEXT)")
                db.execute(f"PRAGMA user_version={version}")
                db.commit()
            before = path.read_bytes()
            self.reject("schema_version_mismatch", lambda: Journal(path, "fake-account", D(100), lot_schema_version=9))
            self.assertEqual(path.read_bytes(), before)

    def test_e03_wrong_version_apis_and_capture(self):
        args = dict(scope=scope(), inst_id=contract().inst_id, observed_at_ms=90, valid_until_ms=110)
        self.reject("unsupported_fee_version", lambda: self.j.capture_lot_snapshot_v2(**args))
        self.reject("unsupported_fee_version", lambda: self.j.capture_lot_snapshot(**args))
        for version in (7, 8):
            with closing(Journal(self.path.with_name(f"v{version}.sqlite3"), "fake-account", D(100), lot_schema_version=version)) as old:
                self.reject("unsupported_fee_version", lambda: old.lot_fills.correct_fee(correction()))
                self.reject("unsupported_fee_version", lambda: old.lot_fills.get_effective_fee(**identity()))
                self.reject("unsupported_fee_version", lambda: old.lot_fills.get_fee_correction(**identity(), correction_id="C1"))
                self.reject("unsupported_fee_version", lambda: old.capture_lot_snapshot_v3(**args))

    def test_e03_external_no_change_and_prefixes_not_relaxed(self):
        value = external_lot()
        args = dict(scope=scope(), bot_id="lot-bot", open_event_seq=1, after=value,
                    opening_unresolved=False, closing_unresolved=False)
        for prefix in ("s3_x", "s9_x", "s10_x"):
            self.reject("reserved_write_id", lambda: self.j.lots.create_v2(**args, write_id=prefix))
        self.reject("unmanaged_lot", lambda: self.j.lots.create_v2(**dict(args,
            after=replace(value, fee_quality=lots.FeeQuality("MANAGED", D(0), 0))), write_id="forge"))
        self.j.lots.create_v2(**args, write_id="external")
        self.reject("no_change", lambda: self.j.lots.replace_v2(scope=scope(), bot_id="lot-bot", write_id="same",
            expected_revision=1, after=replace(value, revision=2), opening_unresolved=False, closing_unresolved=False))
        self.assertIsNone(self.j.lot_fills.get_effective_fee(**identity()))
        self.reject("fee_target_not_found", lambda: self.j.lot_fills.correct_fee(correction()))
        self.reopen()
        self.assertEqual(current(self.j).lot, value)

    def test_e04_external_commit_sequence_is_not_event_sequence(self):
        value = external_lot()
        self.j.lots.create_v2(scope=scope(), bot_id="lot-bot", write_id="external", open_event_seq=1,
            after=value, opening_unresolved=False, closing_unresolved=False)
        self.j.lots.replace_v2(scope=scope(), bot_id="lot-bot", write_id="external-update", expected_revision=1,
            after=replace(value, revision=2, funding_paid=D(1)), opening_unresolved=False, closing_unresolved=False)
        opening(self.j, seq=2)
        original = self.j.lot_fills.apply_fill_v2(fill_v2(quantity=D(3), fee=D(".02")))
        corrected = self.j.lot_fills.correct_fee(correction(predecessor=original.event_seq))
        self.assertEqual((corrected.event_seq, corrected.commit_seq), (3, 4))
        self.assertEqual((original.event_seq, original.commit_seq, original.revision), (2, 3, 1))
        self.reopen()
        self.assertEqual(self.j.lot_fills.get_effective_fee(**identity()).effective_event_seq, corrected.event_seq)
        self.assertEqual(len(self.j.lots.list_current(scope=scope(), bot_id="lot-bot")), 2)

    def test_c04_same_subtotal_proof_gate_with_explicit_synthetic_reducer_stub(self):
        # Mechanism-only fixture: the inflated subtotal is NOT reachable from
        # these fills. The stub supplies a boundary replay state; P2A is real.
        from catos import lot_fills
        real_fill = lot_fills.apply_fill_v2

        def inflated(*args):
            value = real_fill(*args)
            return replace(value, fee_quality=lots.FeeQuality("MANAGED", D("1e50"), 0))

        with patch.object(lot_fills, "apply_fill_v2", side_effect=inflated):
            self.seed()
            before, captured = current(self.j), self.capture()
            saved = self.j.lot_fills.correct_fee(correction())
            after = current(self.j)
            self.assertEqual(after.lot.fee_quality, before.lot.fee_quality)
            self.assertEqual(after.lot.revision, before.lot.revision + 1)
            self.assertNotEqual(self.capture().capture_id, captured.capture_id)
            self.assertEqual(self.j.lot_fills.get_effective_fee(**identity()).effective_event_seq, saved.event_seq)
            self.reopen()
            self.assertEqual(current(self.j), after)
            self.damaged_copy(lambda db: db.execute("DELETE FROM lot_fee_corrections"))
            self.j.connection.execute("DELETE FROM lot_fee_corrections")
            self.reject("integrity_error", lambda: current(self.j))

    def test_f03_unverified_and_long_decimal_escape(self):
        value = external_lot()
        self.j.lots.create_v2(scope=scope(), bot_id="lot-bot", write_id="external", open_event_seq=1,
            after=value, opening_unresolved=False, closing_unresolved=False)
        captured = self.capture()
        html = render_synthetic_scenario_report_v3(capture=captured, scenario=evidence(captured), now_ms=100)
        self.assertIn("fee_coverage_unverified", html)
        self.assertIn("不可用", html)
        # Pure renderer boundary, explicitly not a stored managed ledger.
        amount = D("12345678901234567890123456789012345678901234567890")
        stored = captured.lots[0]
        long_capture = replace(captured, lots=(replace(stored, lot=replace(stored.lot,
            fee_quality=lots.FeeQuality("MANAGED", amount, 1))),))
        long_capture = replace(long_capture, capture_id=lot_snapshot._capture_id(long_capture))
        html = render_synthetic_scenario_report_v3(capture=long_capture, scenario=evidence(long_capture), now_ms=100)
        self.assertIn(format(amount, "f"), html)
        from catos.lot_scenario import LotFeeObservation
        from catos.lot_scenario_report import _fee_section
        section = _fee_section((LotFeeObservation("<script>", "a&b", 1, "UNVERIFIED", None, None, None),))
        self.assertNotIn("<script>", section)
        self.assertIn("&lt;script&gt;", section)

    def test_d05_uncertain_commit_requires_reopen_and_same_identity(self):
        self.seed()
        real = self.j.connection

        class UncertainCommit:
            def __getattr__(self, name):
                return getattr(real, name)

            def commit(self):
                real.commit()
                raise sqlite3.OperationalError("injected acknowledgement loss")

        wrapper = UncertainCommit()
        self.j.connection = self.j.lots.db = self.j.lot_fills.db = wrapper
        try:
            self.reject("storage_unavailable", lambda: self.j.lot_fills.correct_fee(correction()))
            self.reject("storage_unavailable", self.j.lots.recover)
        finally:
            self.j.connection = self.j.lots.db = self.j.lot_fills.db = real
        self.reopen()
        saved = self.j.lot_fills.get_fee_correction(**identity(), correction_id="C1")
        self.assertIsNotNone(saved)
        self.assertEqual(self.j.lot_fills.correct_fee(correction()), replace(saved, replayed=True))

    def test_f01_capture_pins_one_wal_snapshot(self):
        self.seed()
        before = self.capture()
        with closing(Journal(self.path, "fake-account", D(100), lot_schema_version=9)) as writer:
            real = self.j.connection

            class CaptureConnection:
                fired = False

                def __getattr__(self, name):
                    return getattr(real, name)

                def execute(self, sql, args=()):
                    result = real.execute(sql, args)
                    if sql == "SELECT * FROM metadata" and not self.fired:
                        self.fired = True
                        writer.lot_fills.correct_fee(correction())
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
        self.assertEqual(after.lots[0].lot.fee_quality.known_fee_subtotal, D(".015"))

    def test_f02_fixed_header_and_hash_domain(self):
        self.seed()
        captured = self.capture()
        fragments = tuple(lot_snapshot._fragments(captured))
        self.assertEqual(fragments[0]["format"], "catos-local-lot-capture-v3")
        self.assertEqual((fragments[0]["capture_version"], fragments[0]["schema_version"]), (3, 9))
        digest = hashlib.sha256(b"catos-local-lot-capture-v3")
        for fragment in fragments:
            encoded = _json(fragment).encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
        self.assertEqual(captured.capture_id, digest.hexdigest())
        stored = captured.lots[0]
        equivalent = replace(captured, lots=(replace(stored, lot=replace(stored.lot,
            fee_quality=lots.FeeQuality("MANAGED", D(".0200"), 0))),))
        self.assertEqual(lot_snapshot._capture_id(equivalent), captured.capture_id)
        self.assertEqual(lot_snapshot._capture_id(replace(captured, observed_at_ms=91)), captured.capture_id)
        for changed in (replace(captured, capture_version=2), replace(captured, schema_version=8)):
            self.reject("unsupported_fee_version", lambda: lot_snapshot._capture_id(changed))
        with self.assertRaises(ScenarioInputError):
            observe_synthetic_scenario_v2(capture=captured, scenario=evidence(captured), now_ms=100)

    def test_f03_f04_report_changes_fees_not_exposure(self):
        self.seed()
        terminal(self.j)
        before = self.capture()
        old = observe_synthetic_scenario_v3(capture=before, scenario=evidence(before, physical_quantity=D(3)), now_ms=100)
        self.j.lot_fills.correct_fee(correction())
        after = self.capture()
        new = observe_synthetic_scenario_v3(capture=after, scenario=evidence(after, physical_quantity=D(3)), now_ms=100)
        self.assertEqual(old.report, new.report)
        self.assertEqual(new.observation_version, 3)
        self.assertNotEqual(old.fee_quality, new.fee_quality)
        html = render_synthetic_scenario_report_v3(capture=after, scenario=evidence(after), now_ms=100)
        for value in ("capture v3／schema9", after.capture_id, "費用已完整", "funding 未知"):
            self.assertIn(value, html)
        forged = replace(after, capture_id=before.capture_id)
        with self.assertRaises(ScenarioInputError):
            observe_synthetic_scenario_v3(capture=forged, scenario=evidence(forged), now_ms=100)

    def test_f03_empty_unverified_and_incomplete_quality(self):
        capture = self.capture()
        self.assertIn("無 Lot 費用資料", render_synthetic_scenario_report_v3(
            capture=capture, scenario=evidence(capture), now_ms=100))
        opening(self.j)
        self.j.lot_fills.apply_fill_v2(fill_v2(fee=D(".02")))
        self.j.lot_fills.apply_fill_v2(fill_v2(seq=2, quantity=D(2)))
        self.j.lot_fills.correct_fee(correction())
        capture = self.capture()
        html = render_synthetic_scenario_report_v3(capture=capture, scenario=evidence(capture), now_ms=100)
        self.assertIn("fee_incomplete", html)
        self.assertEqual(capture.lots[0].lot.fee_quality.fee_unknown_fill_count, 1)


if __name__ == "__main__":
    unittest.main()
