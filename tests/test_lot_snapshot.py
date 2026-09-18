"""S5 synthetic captures, stable identities and two-connection WAL isolation."""

from contextlib import closing
from dataclasses import fields, replace, FrozenInstanceError
from decimal import Decimal as D, localcontext, ROUND_DOWN
from pathlib import Path
import hashlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from catos import ipc, ipc_lots, lots, lot_snapshot, lot_fills, risk
from catos.journal import Journal
from catos.lot_journal import LotStorageError, _json, _hash
from lot_journal_helpers import contract, scope, snapshot, create, update
from lot_fill_helpers import opening, fill, terminal, close_order
from test_ipc import config


class AfterPin:
    """Run a real second writer after the reader's first SELECT is consumed."""
    def __init__(self, connection, callback):
        self.connection, self.callback = connection, callback

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, sql, args=()):
        cursor = self.connection.execute(sql, args)
        if sql == "SELECT * FROM metadata" and self.callback is not None:
            callback, self.callback = self.callback, None
            class PinnedCursor:
                def fetchall(self):
                    rows = cursor.fetchall()
                    callback()
                    return rows
            return PinnedCursor()
        return cursor


class LotSnapshotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "snapshot.sqlite3"
        self.j = Journal(self.path, "fake-account", D(100))
        self.addCleanup(self.j.close)
        self.bind()

    def bind(self, bot="lot-bot", spec=None):
        self.j.lots.register_binding(scope=scope(), bot_id=bot, contract=spec or contract())

    def capture(self, **changes):
        args = dict(scope=scope(), inst_id=contract().inst_id, observed_at_ms=100, valid_until_ms=200)
        args.update(changes)
        return self.j.capture_lot_snapshot(**args)

    def full_open(self):
        opening(self.j)
        self.j.lot_fills.apply_fill(fill(quantity=D(3)))
        terminal(self.j)

    def reject(self, code, **changes):
        with self.assertRaises(LotStorageError) as caught:
            self.capture(**changes)
        self.assertEqual(caught.exception.code, code)

    def dump(self):
        return tuple(self.j.connection.iterdump())

    def test_a01_binding_without_lots_is_complete_empty_capture(self):
        value = self.capture()
        self.assertEqual((value.lots, value.pending, value.unmanaged_unresolved_lot_ids), ((), (), ()))
        self.assertEqual(value.bot_watermarks[0].last_commit_seq, 0)

    def test_a02_absent_binding_is_not_empty_capture(self):
        self.reject("binding_not_found", inst_id="OTHER-USDT-SWAP")
        self.assertFalse(self.j.lots._failed)
        self.assertFalse(self.j.connection.in_transaction)
        self.capture()

    def test_a03_all_matching_bots_are_sorted(self):
        self.bind("aaa")
        self.bind("zzz")
        create(self.j, snapshot(bot="zzz"))
        create(self.j, snapshot(bot="aaa"))
        value = self.capture()
        self.assertEqual(tuple(b.bot_id for b in value.bot_watermarks), ("aaa", "lot-bot", "zzz"))
        self.assertEqual(tuple(s.lot.lot_id for s in value.lots), tuple(sorted(s.lot.lot_id for s in value.lots)))

    def test_a04_other_instrument_is_excluded(self):
        before = self.capture()
        spec = contract(inst_id="OTHER-USDT-SWAP")
        self.bind("other", spec)
        create(self.j, snapshot(bot="other", spec=spec))
        self.j.lot_fills.bind_order(source_id="synthetic", order_id="other",
            context=lots.IntentContext(scope(), "other", spec, 2, False),
            intent=lots.OpenLot("short", D(3), lots.LotProtection("mark", None, None)))
        self.assertEqual(self.capture(), before)

    def test_a05_contract_conflicts_are_not_arbitrarily_resolved(self):
        for field, value in (("base_per_contract", D(".02")), ("tick_size", D(1)),
                             ("lot_size", D(1)), ("min_size", D(2))):
            with self.subTest(field=field):
                with self.j._transaction():
                    self.j.connection.execute("DELETE FROM lot_bindings WHERE bot_id='other'")
                self.bind("other", contract(**{field: value}))
                self.reject("contract_conflict")
                self.assertFalse(self.j.lots._failed)

    def test_a06_closed_lots_remain_visible(self):
        create(self.j, snapshot(remaining_qty=D(0)))
        self.assertEqual(self.capture().lots[0].lot.remaining_qty, D(0))

    def test_a07_only_current_head_is_exported(self):
        create(self.j)
        changed = replace(snapshot(), revision=2, remaining_qty=D(1))
        update(self.j, changed)
        value = self.capture()
        self.assertEqual(len(value.lots), 1)
        self.assertEqual(value.lots[0].lot, changed)

    def test_a08_invalid_input_does_not_poison_handle(self):
        for values, code in ((dict(scope=lots.LotScope("other", "local-sim")), "scope_mismatch"),
                             (dict(scope=lots.LotScope("fake-account", "demo")), "scope_mismatch"),
                             (dict(inst_id="BTC-SPOT"), "invalid_contract"),
                             (dict(inst_id=True), "invalid_contract"),
                             (dict(observed_at_ms=True), "invalid_capture_time"),
                             (dict(valid_until_ms=100), "invalid_capture_time"),
                             (dict(observed_at_ms=-1), "invalid_capture_time"),
                             (dict(valid_until_ms=ipc.MAX_INTEGER + 1), "invalid_capture_time")):
            with self.subTest(values=values):
                self.reject(code, **values)
                self.assertFalse(self.j.lots._failed)
                self.assertFalse(self.j.connection.in_transaction)

    def test_b01_unfilled_open_has_pending_without_lot(self):
        opening(self.j, side="short")
        value = self.capture()
        self.assertEqual(value.lots, ())
        pending = value.pending[0]
        self.assertEqual((pending.effect, pending.side, pending.filled_quantity, pending.remaining_quantity, pending.last_fill_seq),
                         ("OPEN", "SELL", D(0), D(3), 0))

    def test_b02_partial_open_has_exact_remainder(self):
        opening(self.j)
        self.j.lot_fills.apply_fill(fill())
        value = self.capture()
        self.assertEqual(value.lots[0].lot.remaining_qty, D(1))
        self.assertEqual((value.pending[0].filled_quantity, value.pending[0].remaining_quantity), (D(1), D(2)))

    def test_b03_partial_close_keeps_unfilled_responsibility(self):
        self.full_open()
        close_order(self.j)
        self.j.lot_fills.apply_fill(fill(order="close"))
        value = self.capture()
        self.assertEqual(value.lots[0].lot.remaining_qty, D(2))
        self.assertEqual((value.pending[0].effect, value.pending[0].side, value.pending[0].remaining_quantity), ("CLOSE", "SELL", D(2)))

    def test_b03_short_close_has_buy_direction(self):
        opening(self.j, side="short")
        self.j.lot_fills.apply_fill(fill(quantity=D(3)))
        terminal(self.j)
        close_order(self.j)
        self.assertEqual(self.capture().pending[0].side, "BUY")

    def test_b04_fully_filled_open_still_pending_before_terminal(self):
        opening(self.j)
        self.j.lot_fills.apply_fill(fill(quantity=D(3)))
        value = self.capture()
        self.assertEqual(value.pending[0].remaining_quantity, D(0))
        self.assertTrue(value.lots[0].opening_unresolved)

    def test_b05_closed_lot_and_zero_pending_coexist(self):
        self.full_open()
        close_order(self.j)
        self.j.lot_fills.apply_fill(fill(order="close", quantity=D(3)))
        value = self.capture()
        self.assertEqual((value.lots[0].lot.remaining_qty, value.pending[0].remaining_quantity), (D(0), D(0)))
        self.assertTrue(value.lots[0].closing_unresolved)

    def test_b06_terminal_removes_pending_only_after_recorded(self):
        self.full_open()
        value = self.capture()
        self.assertEqual(value.pending, ())
        self.assertEqual(value.lots[0].lot.revision, 2)

    def test_b07_zero_fill_terminal_returns_original_content_identity(self):
        before = self.capture()
        opening(self.j)
        terminal(self.j, seq=0, quantity=D(0), status="REJECTED")
        self.assertEqual(self.capture(), before)

    def test_b08_pending_sorted_by_stable_order_key(self):
        for seq in (3, 1, 2):
            opening(self.j, order=f"order-{seq}", seq=seq)
        value = self.capture()
        self.assertEqual(tuple(p.order_key for p in value.pending), tuple(sorted(p.order_key for p in value.pending)))

    def test_b09_unmanaged_unresolved_flags_are_explicit(self):
        create(self.j, snapshot(seq=7), seq=7, opening=True)
        create(self.j, snapshot(seq=8), seq=8, write_id="other", closing=True)
        value = self.capture()
        self.assertEqual(value.unmanaged_unresolved_lot_ids, tuple(sorted((snapshot(seq=7).lot_id, snapshot(seq=8).lot_id))))
        self.assertEqual(value.pending, ())

    def test_b10_managed_flags_are_not_duplicated_as_unmanaged(self):
        opening(self.j)
        self.j.lot_fills.apply_fill(fill())
        value = self.capture()
        self.assertEqual(value.unmanaged_unresolved_lot_ids, ())
        self.assertTrue(value.lots[0].opening_unresolved)

    def test_c01_wrapper_time_is_not_content_identity(self):
        create(self.j)
        before = self.capture()
        after = self.capture(observed_at_ms=300, valid_until_ms=400)
        self.assertEqual(before.capture_id, after.capture_id)
        self.assertNotEqual(before.observed_at_ms, after.observed_at_ms)

    def test_c02_full_lot_and_watermark_content_is_hashed(self):
        create(self.j)
        capture = self.capture()
        stored = capture.lots[0]
        for changes in (dict(fees_paid=D(2)), dict(funding_paid=D(0)), dict(average_entry=D(101)),
                        dict(realized_pnl=D(1)), dict(remaining_qty=D(1)), dict(revision=2),
                        dict(protection=lots.LotProtection("mark", D(120), None))):
            with self.subTest(changes=changes):
                changed = replace(capture, lots=(replace(stored, lot=replace(stored.lot, **changes)),))
                self.assertNotEqual(lot_snapshot._capture_id(changed), capture.capture_id)
        for changes in (dict(opening_unresolved=True), dict(closing_unresolved=True), dict(commit_seq=2)):
            self.assertNotEqual(lot_snapshot._capture_id(replace(capture, lots=(replace(stored, **changes),))), capture.capture_id)
        watermark = replace(capture.bot_watermarks[0], last_commit_seq=2)
        self.assertNotEqual(lot_snapshot._capture_id(replace(capture, bot_watermarks=(watermark,))), capture.capture_id)

    def test_c03_binding_changes_pending_identity_without_watermark(self):
        before = self.capture()
        opening(self.j)
        after = self.capture()
        self.assertEqual(before.bot_watermarks, after.bot_watermarks)
        self.assertNotEqual(before.capture_id, after.capture_id)

    def test_c04_fill_changes_identity_and_sequence(self):
        opening(self.j)
        before = self.capture()
        self.j.lot_fills.apply_fill(fill())
        after = self.capture()
        self.assertNotEqual(before.capture_id, after.capture_id)
        self.assertEqual(after.pending[0].last_fill_seq, 1)
        pending = before.pending[0]
        for changes in (dict(order_key="a" * 64), dict(intent_key="b" * 64), dict(bot_id="other"),
                        dict(lot_id="c" * 64), dict(effect="CLOSE"), dict(side="SELL"),
                        dict(resolved_quantity=D(4)), dict(filled_quantity=D(1)),
                        dict(remaining_quantity=D(2)), dict(last_fill_seq=1)):
            with self.subTest(changes=changes):
                changed = replace(before, pending=(replace(pending, **changes),))
                self.assertNotEqual(lot_snapshot._capture_id(changed), before.capture_id)

    def test_c05_terminal_changes_pending_and_lot_version_identity(self):
        opening(self.j)
        self.j.lot_fills.apply_fill(fill(quantity=D(3)))
        before = self.capture()
        terminal(self.j)
        self.assertNotEqual(self.capture().capture_id, before.capture_id)

    def test_c06_other_contract_mutations_do_not_change_identity(self):
        spec = contract(inst_id="OTHER-USDT-SWAP")
        self.bind("other", spec)
        value = snapshot(bot="other", spec=spec)
        create(self.j, value)
        before = self.capture()
        update(self.j, replace(value, revision=2, fees_paid=D(2)))
        self.assertEqual(self.capture(), before)

    def test_c07_equivalent_numbers_and_ambient_context_are_stable(self):
        opening(self.j)
        self.j.lot_fills.apply_fill(fill())
        capture = self.capture()
        self.assertRegex(capture.capture_id, r"^[0-9a-f]{64}$")
        stored = capture.lots[0]
        changed = replace(capture, contract=replace(capture.contract, base_per_contract=D("0.0100")),
            lots=(replace(stored, lot=replace(stored.lot, remaining_qty=D("1.00"))),),
            pending=(replace(capture.pending[0], remaining_quantity=D("2.00")),))
        self.assertEqual(lot_snapshot._capture_id(changed), capture.capture_id)
        with localcontext() as ctx:
            ctx.prec, ctx.rounding = 2, ROUND_DOWN
            ctx.clear_flags()
            flags = dict(ctx.flags)
            self.assertEqual(self.capture().capture_id, capture.capture_id)
            self.assertEqual(ctx.flags, flags)

    def test_d01_d04_real_wal_writer_commits_after_pin_without_mixing(self):
        opening(self.j)
        opening(self.j, order="second", seq=2)
        self.bind("other")
        opening(self.j, order="third", bot="other")
        with closing(Journal(self.path, "fake-account", D(100))) as writer:
            old = self.capture()
            committed = []
            def write_after_pin():
                for order_id in ("open", "second", "third"):
                    writer.lot_fills.apply_fill(fill(order=order_id))
                committed.append(True)
            real = self.j.connection
            with patch.object(self.j, "connection", AfterPin(real, write_after_pin)):
                during = self.capture()
            self.assertEqual(committed, [True])
            self.assertEqual(during, old)
            self.assertEqual(during.lots, ())
            after = self.capture()
            self.assertEqual(len(after.lots), 3)
            self.assertTrue(all(p.filled_quantity == D(1) for p in after.pending))
            self.assertNotEqual(after.capture_id, old.capture_id)

    def test_d05_read_only_trace_and_all_tables_unchanged(self):
        self.j.close()
        self.j = Journal(self.path, "fake-account", D(100), risk_limits=risk.Limits(), execution_enabled=True)
        self.addCleanup(self.j.close)
        self.j.register("bot", config())
        self.j.record_halts({"manual_kill"})
        protection = self.j.protection.state("bot")
        protection["pending"] = {"synthetic": "unresolved"}
        with self.j._transaction():
            self.j.protection.save("bot", protection)
        opening(self.j)
        self.j.lot_fills.apply_fill(fill())
        before = self.dump()
        statements = []
        self.j.connection.set_trace_callback(statements.append)
        try:
            with patch.object(self.j, "_commit", side_effect=AssertionError("capture must not commit")):
                self.capture()
        finally:
            self.j.connection.set_trace_callback(None)
        self.assertEqual(self.dump(), before)
        self.assertEqual(statements[:2], ["BEGIN DEFERRED", "SELECT * FROM metadata"])
        self.assertEqual(statements[-1], "ROLLBACK")
        self.assertFalse(any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")) for s in statements))

    def test_d06_failures_close_transaction_without_writes(self):
        create(self.j)
        before = self.dump()
        cases = (("_recover_in_transaction", sqlite3.OperationalError("read I/O"), "storage_unavailable"),
                 ("_decode_binding", ValueError("invalid decoded record"), "integrity_error"),
                 ("_capture_id", ValueError("invalid hash fragment"), "integrity_error"))
        for name, error, code in cases:
            with self.subTest(name=name):
                target = lot_snapshot if name == "_capture_id" else self.j.lots
                with patch.object(target, name, side_effect=error):
                    self.reject(code)
                self.assertFalse(self.j.connection.in_transaction)
                self.assertEqual(self.dump(), before)
                self.assertTrue(self.j.lots._failed)
                self.j.close()
                self.j = Journal(self.path, "fake-account", D(100))
                self.addCleanup(self.j.close)

    def test_d06_wrapped_sqlite_io_and_rollback_failure_are_storage_errors(self):
        with patch.object(self.j.lots, "_decode_binding", side_effect=sqlite3.OperationalError("wrapped I/O")):
            self.reject("storage_unavailable")
        self.assertFalse(self.j.connection.in_transaction)
        self.assertTrue(self.j.lots._failed)
        self.j.close()
        self.j = Journal(self.path, "fake-account", D(100))
        self.addCleanup(self.j.close)
        real = self.j.connection
        class FailedRollback:
            def __getattr__(self, name):
                return getattr(real, name)
            def rollback(self):
                real.rollback()
                raise sqlite3.OperationalError("rollback ACK failure")
        with patch.object(self.j, "connection", FailedRollback()):
            self.reject("storage_unavailable")
        self.assertFalse(real.in_transaction)
        self.assertTrue(self.j.lots._failed)

    def test_d07_nested_and_failed_handles_rejected(self):
        self.j.connection.execute("BEGIN DEFERRED")
        try:
            self.reject("storage_unavailable")
            self.assertTrue(self.j.connection.in_transaction)
            self.assertFalse(self.j.lots._failed)
        finally:
            self.j.connection.rollback()
        self.j.lots._failed = True
        self.reject("storage_unavailable")

    def test_e01_s2_corruption_blocks_entire_capture(self):
        create(self.j)
        self.j.connection.execute("UPDATE lot_revisions SET fees_paid='999'")
        self.reject("integrity_error")
        self.assertTrue(self.j.lots._failed)
        self.assertFalse(self.j.connection.in_transaction)

    def test_e02_s3_corruption_blocks_capture(self):
        opening(self.j)
        self.j.connection.execute("UPDATE lot_fill_orders SET resolved_quantity='999'")
        self.reject("integrity_error")
        self.assertFalse(self.j.connection.in_transaction)

    def test_e03_bot_limit(self):
        for index in range(63):
            self.bind(f"bot-{index}")
        self.assertEqual(len(self.capture().bot_watermarks), 64)
        self.bind("overflow")
        self.reject("capture_limit")
        self.assertFalse(self.j.lots._failed)

    def test_e03_lot_limit_with_real_valid_history(self):
        with self.j._transaction():
            for seq in range(1, 4097):
                value = snapshot(seq=seq)
                self.j.lots._write(scope(), value.bot_id, f"seed-{seq}", "CREATE", seq, 0,
                                   value, False, False, _in_transaction=True)
        self.assertEqual(len(self.capture().lots), 4096)
        create(self.j, snapshot(seq=4097), seq=4097, write_id="overflow")
        self.reject("capture_limit")

    def test_e03_pending_limit_with_real_replay(self):
        # Bulk fixture creation avoids quadratic public replay during seeding.
        # Capture still runs the unmodified full S2/S3 integrity checks.
        payloads = []
        for seq in range(1, 4098):
            payloads.append(dict(kind="bind", scope=ipc_lots._scope_to_wire(scope()), source_id="synthetic",
                order_id=f"order-{seq}", bot_id="lot-bot", contract=lot_fills._contract_wire(contract()),
                event_seq=seq, warmup=False, intent=ipc_lots.intent_to_wire(
                    lots.OpenLot("long", D(3), lots.LotProtection("mark", None, None)))))
        _, _, results = self.j.lot_fills._evaluate(payloads)
        def insert(index):
            p = payloads[index]
            text = _json(p)
            values = self.j.lot_fills._columns(p, results[index])
            values.update(seq=index + 1, request_json=text, request_hash=_hash(text), lot_id=None, revision=None, commit_seq=None)
            self.j.connection.execute(f"INSERT INTO lot_fill_orders ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
        with self.j._transaction():
            for index in range(4096):
                insert(index)
        self.assertEqual(len(self.capture().pending), 4096)
        with self.j._transaction():
            insert(4096)
        self.reject("capture_limit")

    def test_e04_streaming_hash_exceeds_one_frame_without_relaxing_it(self):
        with self.j._transaction():
            for seq in range(1, 201):
                self.j.lots._write(scope(), "lot-bot", f"seed-{seq}", "CREATE", seq, 0,
                                   snapshot(seq=seq), False, False, _in_transaction=True)
        value = self.capture()
        encoded = [_json(p).encode("utf-8") for p in lot_snapshot._fragments(value)]
        self.assertGreater(sum(map(len, encoded)), ipc.MAX_FRAME)
        self.assertTrue(all(len(p) <= ipc.MAX_FRAME for p in encoded))
        digest = hashlib.sha256(b"catos-local-lot-capture-v1")
        for data in encoded:
            digest.update(len(data).to_bytes(8, "big") + data)
        self.assertEqual(value.capture_id, digest.hexdigest())
        with self.assertRaises(ipc.ProtocolError):
            _json(dict(oversized="x" * ipc.MAX_FRAME))

    def test_e05_exact_derived_remainder(self):
        spec = contract(lot_size=D("1e-18"), min_size=D("1e-18"))
        self.bind("precise", spec)
        # All matching bindings must agree before capture.
        with self.j._transaction():
            self.j.connection.execute("DELETE FROM lot_bindings WHERE bot_id='lot-bot'")
        self.j.lot_fills.bind_order(source_id="synthetic", order_id="precise",
            context=lots.IntentContext(scope(), "precise", spec, 1, False),
            intent=lots.OpenLot("long", D("1e18"), lots.LotProtection("mark", None, None)))
        self.j.lot_fills.apply_fill(fill(order="precise", quantity=D("999999999999999999.999999999999999999")))
        with localcontext() as ctx:
            ctx.prec = 2
            value = self.capture()
        self.assertEqual(value.pending[0].remaining_quantity, D("1e-18"))
        extreme = snapshot(bot="precise", spec=spec, seq=2, realized_pnl=D("1e99"), fees_paid=D("1e-148"))
        create(self.j, extreme, seq=2, write_id="extreme-accounting")
        with localcontext() as ctx:
            ctx.prec = 2
            captured = self.capture()
        stored = next(s.lot for s in captured.lots if s.lot.lot_id == extreme.lot_id)
        self.assertEqual((stored.realized_pnl, stored.fees_paid), (D("1e99"), D("1e-148")))

    def test_e06_identity_excludes_path_and_has_no_authority_fields(self):
        create(self.j)
        value = self.capture()
        copy = self.path.with_name("copy.sqlite3")
        with closing(sqlite3.connect(copy)) as db:
            self.j.connection.backup(db)
        with closing(Journal(copy, "fake-account", D(100))) as other:
            result = other.capture_lot_snapshot(scope=scope(), inst_id=contract().inst_id, observed_at_ms=500, valid_until_ms=600)
        self.assertEqual(value.capture_id, result.capture_id)
        self.assertFalse({"accepted", "ready", "verified", "reconciled"} & {f.name for f in fields(value)})
        with self.assertRaises(FrozenInstanceError):
            value.capture_id = "bad"


if __name__ == "__main__":
    unittest.main()
