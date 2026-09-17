from contextlib import closing
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from catos import lots, lot_fills
from catos.journal import Journal, JournalError
from catos.lot_journal import LotStorageError
from lot_journal_helpers import contract, scope, snapshot, create, update, drop_empty_fill_schema
from lot_fill_helpers import opening, fill, terminal, current, close_order
from test_lot_journal import FailingConnection
from test_ipc import config


class LotFillIdentityTests(unittest.TestCase):
    """Identity serialization regressions independent of database setup."""

    def test_order_identity_is_stable_and_includes_every_scope_field(self):
        args = (scope(), "synthetic", contract().inst_id, "open")
        original = lot_fills._key(*args)
        self.assertEqual(original, lot_fills._key(*args))
        self.assertRegex(original, r"^[0-9a-f]{64}$")
        variants = (
            (lots.LotScope("other-account", "local-sim"), *args[1:]),
            (lots.LotScope("fake-account", "demo"), *args[1:]),
            (args[0], "other-source", args[2], args[3]),
            (args[0], args[1], "OTHER-USDT-SWAP", args[3]),
            (*args[:3], "other-order"),
        )
        keys = [original]
        for variant in variants:
            with self.subTest(identity=variant):
                value = lot_fills._key(*variant)
                self.assertNotIn(value, keys)
                keys.append(value)

    def test_write_identity_is_stable_and_includes_sequence_and_fingerprint(self):
        make = lot_fills.LotFillJournal._write_id
        original = make(1, "a" * 64)
        self.assertEqual(original, make(1, "a" * 64))
        self.assertRegex(original, r"^s3_[0-9a-f]{61}$")
        self.assertNotEqual(original, make(2, "a" * 64))
        self.assertNotEqual(original, make(1, "b" * 64))


class LotFillTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "synthetic.sqlite3"
        self.j = Journal(self.path, "fake-account", D(100))
        self.addCleanup(lambda: self.j.close() if self.j is not None else None)
        self.j.lots.register_binding(scope=scope(), bot_id="lot-bot", contract=contract())

    def reopen(self):
        self.j.close()
        self.j = None
        self.j = Journal(self.path, "fake-account", D(100))

    def full_open(self):
        opening(self.j)
        self.j.lot_fills.apply_fill(fill(quantity=D(3)))
        terminal(self.j)

    def dump(self):
        return tuple(self.j.connection.iterdump())

    def corrupt(self, sql):
        path = self.path.with_name("corrupt.sqlite3")
        with closing(sqlite3.connect(path)) as db:
            self.j.connection.backup(db)
            db.execute(sql)
            db.commit()
        with self.assertRaises(JournalError):
            Journal(path, "fake-account", D(100))

    def test_strict_schema_and_empty_recovery(self):
        strict = {r["name"]: r["strict"] for r in self.j.connection.execute("PRAGMA table_list")}
        self.assertTrue(all(strict[t] == 1 for t in lot_fills.TABLES))
        self.assertEqual(self.j.lot_fills.recover().order_count, 0)

    def test_binding_idempotence_no_zero_lot(self):
        a, b = opening(self.j), opening(self.j)
        self.assertTrue(b.replayed)
        self.assertEqual(a.event_seq, b.event_seq)
        self.assertEqual(self.j.lots.list_current(scope=scope(), bot_id="lot-bot"), ())
        self.assertIsNone(a.revision)

    def test_first_fill_receipt_replays_before_and_after_restart(self):
        bound = opening(self.j)
        first = self.j.lot_fills.apply_fill(fill())
        replay = self.j.lot_fills.apply_fill(fill())
        self.assertFalse(first.replayed)
        self.assertEqual((first.revision, first.commit_seq), (1, 1))
        self.assertEqual(replay, replace(first, replayed=True))
        self.reopen()
        self.assertEqual(opening(self.j), replace(bound, replayed=True))
        self.assertEqual(self.j.lot_fills.apply_fill(fill()), replay)
        self.assertEqual(self.j.lot_fills.recover().fill_count, 1)
        self.assertEqual(self.j.lots.recover().revision_count, 1)
        self.assertTrue(current(self.j).opening_unresolved)

    def test_binding_conflict_and_event_reuse(self):
        opening(self.j)
        for args in ({"quantity": D(4)}, {"order": "other"}):
            with self.subTest(args=args), self.assertRaises(LotStorageError):
                opening(self.j, **args)

    def test_warmup_and_contract_mismatch(self):
        for context in (lots.IntentContext(scope(), "lot-bot", contract(), 1, True),
                        lots.IntentContext(scope(), "lot-bot", contract(tick_size=D(1)), 1, False)):
            with self.subTest(context=context), self.assertRaises((LotStorageError, lots.LotError)):
                self.j.lot_fills.bind_order(source_id="synthetic", order_id="open", context=context,
                    intent=lots.OpenLot("long", D(3), lots.LotProtection("mark", None, None)))

    def test_first_fill_and_flags(self):
        opening(self.j)
        receipt = self.j.lot_fills.apply_fill(fill(quantity=D(3)))
        self.assertEqual(receipt.revision, 1)
        self.assertTrue(current(self.j).opening_unresolved)
        terminal(self.j)
        self.assertFalse(current(self.j).opening_unresolved)
        self.assertEqual(current(self.j).lot.revision, 2)

    def test_close_binding_changes_only_flag_then_accounts(self):
        self.full_open()
        close_order(self.j)
        self.assertTrue(current(self.j).closing_unresolved)
        self.j.lot_fills.apply_fill(fill(order="close", quantity=D(3), price=D(120)))
        self.assertEqual(current(self.j).lot.realized_pnl, D("0.60"))
        self.assertTrue(current(self.j).closing_unresolved)
        terminal(self.j, order="close")
        self.assertFalse(current(self.j).closing_unresolved)
        self.reopen()
        self.assertEqual(self.j.lot_fills.recover().fill_count, 2)

    def test_partial_cancel_and_another_close(self):
        self.full_open()
        close_order(self.j)
        self.j.lot_fills.apply_fill(fill(order="close"))
        terminal(self.j, order="close", quantity=D(1), status="CANCELED")
        close_order(self.j, order="close2", seq=3)
        self.j.lot_fills.apply_fill(fill(order="close2", quantity=D(2)))
        terminal(self.j, order="close2", quantity=D(2))
        self.assertEqual(current(self.j).lot.remaining_qty, D(0))

    def test_zero_fill_rejection(self):
        opening(self.j)
        receipt = terminal(self.j, seq=0, quantity=D(0), status="REJECTED")
        self.assertIsNone(receipt.lot_id)
        self.reopen()
        self.assertEqual(self.j.lot_fills.recover().terminal_count, 1)

    def test_fill_numeric_equivalence_and_conflict(self):
        opening(self.j)
        a = self.j.lot_fills.apply_fill(fill())
        b = self.j.lot_fills.apply_fill(fill(quantity=D("1.00"), price=D("100.0"), fee=D(".010")))
        self.assertEqual(a.request_hash, b.request_hash)
        self.assertTrue(b.replayed)
        with self.assertRaisesRegex(LotStorageError, "write_conflict"):
            self.j.lot_fills.apply_fill(fill(price=D(101)))

    def test_old_receipt_after_terminal_and_restart(self):
        self.full_open()
        close_order(self.j)
        self.reopen()
        receipt = self.j.lot_fills.apply_fill(fill(quantity=D(3)))
        self.assertTrue(receipt.replayed)
        self.assertEqual(receipt.revision, 1)
        self.assertEqual(current(self.j).lot.revision, 3)

    def test_sequence_gap_then_retry(self):
        opening(self.j)
        with self.assertRaisesRegex(LotStorageError, "fill_sequence"):
            self.j.lot_fills.apply_fill(fill(seq=2))
        self.j.lot_fills.apply_fill(fill())
        self.j.lot_fills.apply_fill(fill(seq=2))
        self.assertEqual(current(self.j).lot.remaining_qty, D(2))

    def test_overfill_rejected_without_write(self):
        opening(self.j)
        before = self.dump()
        with self.assertRaisesRegex(LotStorageError, "over_fill"):
            self.j.lot_fills.apply_fill(fill(quantity=D(4)))
        self.assertEqual(self.dump(), before)

    def test_terminal_evidence_and_late_fill(self):
        opening(self.j)
        self.j.lot_fills.apply_fill(fill())
        for args in ({"quantity": D(2)}, {"seq": 2, "quantity": D(1)},
                     {"quantity": D(1), "status": "REJECTED"}, {"quantity": D(1)}):
            with self.subTest(args=args), self.assertRaises(LotStorageError):
                terminal(self.j, **args)
        terminal(self.j, quantity=D(1), status="CANCELED")
        with self.assertRaisesRegex(LotStorageError, "order_unavailable"):
            self.j.lot_fills.apply_fill(fill(seq=2))

    def test_terminal_replay_and_conflict(self):
        self.full_open()
        self.assertTrue(terminal(self.j).replayed)
        with self.assertRaisesRegex(LotStorageError, "write_conflict"):
            terminal(self.j, terminal_id="other")

    def test_same_lot_only_one_unresolved_order(self):
        opening(self.j)
        self.j.lot_fills.apply_fill(fill())
        with self.assertRaisesRegex(LotStorageError, "lot_busy"):
            close_order(self.j)

    def test_managed_snapshot_and_reserved_namespace_rejected(self):
        self.full_open()
        lot = current(self.j).lot
        with self.assertRaisesRegex(LotStorageError, "managed_lot"):
            update(self.j, replace(lot, revision=lot.revision + 1, fees_paid=D(99)), expected=lot.revision)
        with self.assertRaisesRegex(LotStorageError, "reserved_write_id"):
            create(self.j, snapshot(seq=9), seq=9, write_id="s3_reserved")

    def test_existing_s2_lot_not_adopted(self):
        create(self.j)
        with self.assertRaisesRegex(LotStorageError, "unmanaged_lot"):
            opening(self.j)
        with self.assertRaisesRegex(LotStorageError, "unmanaged_lot"):
            close_order(self.j)

    def test_unknown_order_and_wrong_scope(self):
        with self.assertRaises(LotStorageError):
            self.j.lot_fills.apply_fill(fill())
        with self.assertRaises(LotStorageError):
            self.j.lot_fills.apply_fill(replace(fill(), scope=lots.LotScope("other", "local-sim")))

    def test_pagination(self):
        opening(self.j)
        self.j.lot_fills.apply_fill(fill())
        self.j.lot_fills.apply_fill(fill(seq=2))
        args = dict(scope=scope(), source_id="synthetic", inst_id=contract().inst_id, order_id="open")
        self.assertIsNotNone(self.j.lot_fills.get_order(**args))
        self.assertEqual(len(self.j.lot_fills.list_fills(**args, limit=1)), 1)
        self.assertEqual(len(self.j.lot_fills.list_fills(**args, after_fill_seq=1)), 1)
        with self.assertRaises(LotStorageError):
            self.j.lot_fills.list_fills(**args, limit=True)

    def test_each_sql_write_failure_rolls_back(self):
        for prefix in ("INSERT INTO lot_heads", "INSERT INTO lot_revisions", "UPDATE lot_bindings", "INSERT INTO lot_fill_events"):
            with self.subTest(prefix=prefix):
                opening(self.j)
                before = self.dump()
                proxy = FailingConnection(self.j.connection, prefix)
                self.j.lots.db = self.j.lot_fills.db = proxy
                with self.assertRaises(LotStorageError):
                    self.j.lot_fills.apply_fill(fill())
                self.j.lots.db = self.j.lot_fills.db = self.j.connection
                self.assertEqual(self.dump(), before)
                self.reopen()

    def test_commit_ack_failure_replays(self):
        opening(self.j)
        commit = self.j._commit
        def uncertain():
            commit()
            raise sqlite3.OperationalError("synthetic lost ACK")
        with patch.object(self.j, "_commit", uncertain), self.assertRaises(LotStorageError):
            self.j.lot_fills.apply_fill(fill())
        self.reopen()
        self.assertTrue(self.j.lot_fills.apply_fill(fill()).replayed)

    def test_busy_requires_reopen(self):
        opening(self.j)
        with closing(sqlite3.connect(self.path)) as other:
            other.execute("BEGIN IMMEDIATE")
            with self.assertRaises(LotStorageError):
                self.j.lot_fills.apply_fill(fill())
            other.rollback()
        self.reopen()
        self.assertFalse(self.j.lot_fills.apply_fill(fill()).replayed)

    def test_corruption_missing_event_and_accounting(self):
        self.full_open()
        for sql in ("DELETE FROM lot_fill_events", "UPDATE lot_fill_events SET fee_paid='9'",
                    "UPDATE lot_fill_events SET request_hash='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'",
                    "UPDATE lot_fill_orders SET resolved_quantity='99'", "DELETE FROM lot_fill_terminals"):
            with self.subTest(sql=sql):
                self.corrupt(sql)

    def test_schema_six_migration_preserves_s2_data(self):
        create(self.j)
        self.j.close()
        self.j = None
        with closing(sqlite3.connect(self.path)) as db, db:
            drop_empty_fill_schema(db)
            db.execute("PRAGMA user_version=6")
        self.j = Journal(self.path, "fake-account", D(100))
        self.assertEqual(current(self.j).lot, snapshot())

    def test_migration_failure_is_atomic(self):
        self.j.close()
        self.j = None
        with closing(sqlite3.connect(self.path)) as db, db:
            drop_empty_fill_schema(db)
            db.execute("PRAGMA user_version=6")
        def fail(db):
            db.execute(lot_fills.SCHEMA[0])
            raise sqlite3.OperationalError("migration probe")
        with patch.object(lot_fills, "install_schema", fail), self.assertRaises(sqlite3.Error):
            Journal(self.path, "fake-account", D(100))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 6)
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='lot_fill_orders'").fetchone())

    def test_v1_tables_remain_unchanged(self):
        self.j.register("bot", config())
        tables = [r[0] for r in self.j.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                  if not r[0].startswith(("lot_", "sqlite_"))]
        def snapshot_v1():
            return {t: [tuple(r) for r in self.j.connection.execute(f"SELECT * FROM {t}")] for t in tables}
        before = snapshot_v1()
        self.full_open()
        close_order(self.j)
        self.assertEqual(snapshot_v1(), before)

    def test_multiple_bots_same_contract_and_source_identity(self):
        self.j.lots.register_binding(scope=scope(), bot_id="other", contract=contract())
        opening(self.j)
        opening(self.j, order="other-order", bot="other", side="short")
        self.j.lot_fills.apply_fill(fill())
        self.j.lot_fills.apply_fill(fill(order="other-order", price=D(110)))
        self.reopen()
        other = self.j.lots.list_current(scope=scope(), bot_id="other")[0].lot
        self.assertEqual((other.side, other.average_entry), ("short", D(110)))
        self.assertEqual(current(self.j).lot.average_entry, D(100))
        with self.assertRaises(LotStorageError):
            opening(self.j, bot="other")

    def test_order_binding_numeric_equivalence(self):
        opening(self.j)
        self.assertTrue(opening(self.j, quantity=D("3.00")).replayed)

    def test_raw_cumulative_payload_is_not_a_fill(self):
        opening(self.j)
        before = self.dump()
        with self.assertRaises(TypeError):
            self.j.lot_fills.apply_fill(dict(order_id="open", cumulative_qty="3"))
        self.assertEqual(self.dump(), before)

    def test_recovery_is_read_only(self):
        self.full_open()
        close_order(self.j)
        before = self.dump()
        self.j.lot_fills.recover()
        self.assertEqual(self.dump(), before)

    def test_extra_internal_snapshot_is_detected(self):
        self.full_open()
        lot = current(self.j).lot
        with self.j._transaction():
            self.j.lots._write(lot.scope, lot.bot_id, "unattributed", "REPLACE", None,
                lot.revision, replace(lot, revision=lot.revision + 1, fees_paid=D(99)),
                False, False, _in_transaction=True)
        with self.assertRaisesRegex(LotStorageError, "integrity_error"):
            self.j.lot_fills.recover()

    def test_schema_residue_trigger_and_missing_table(self):
        for sql in ("PRAGMA user_version=6", "DROP TABLE lot_fill_events",
                    "CREATE TRIGGER unexpected AFTER INSERT ON lot_fill_events BEGIN SELECT 1; END"):
            with self.subTest(sql=sql):
                self.corrupt(sql)

    def test_close_expected_revision_checked(self):
        self.full_open()
        lot = current(self.j).lot
        with self.assertRaisesRegex(LotStorageError, "revision_conflict"):
            self.j.lot_fills.bind_order(source_id="synthetic", order_id="close",
                context=lots.IntentContext(scope(), "lot-bot", contract(), 2, False),
                intent=lots.CloseLot(lot.lot_id, None, 1))

    def test_terminal_and_close_binding_sql_failures_are_atomic(self):
        self.full_open()
        for prefix, action in (("INSERT INTO lot_fill_orders", lambda: close_order(self.j)),
                               ("UPDATE lot_heads", lambda: close_order(self.j))):
            before = self.dump()
            proxy = FailingConnection(self.j.connection, prefix)
            self.j.lots.db = self.j.lot_fills.db = proxy
            with self.assertRaises(LotStorageError):
                action()
            self.j.lots.db = self.j.lot_fills.db = self.j.connection
            self.assertEqual(self.dump(), before)
            self.reopen()
        close_order(self.j)
        before = self.dump()
        proxy = FailingConnection(self.j.connection, "INSERT INTO lot_fill_terminals")
        self.j.lots.db = self.j.lot_fills.db = proxy
        with self.assertRaises(LotStorageError):
            terminal(self.j, order="close", seq=0, quantity=D(0), status="CANCELED")
        self.j.lots.db = self.j.lot_fills.db = self.j.connection
        self.assertEqual(self.dump(), before)

    def test_derived_remaining_quantity_can_be_fully_closed(self):
        spec = contract(lot_size=D("1e-18"), min_size=D("1e-18"))
        self.j.lots.register_binding(scope=scope(), bot_id="precise", contract=spec)
        self.j.lot_fills.bind_order(source_id="synthetic", order_id="open",
            context=lots.IntentContext(scope(), "precise", spec, 1, False),
            intent=lots.OpenLot("long", D("1e18"), lots.LotProtection("mark", None, None)))
        self.j.lot_fills.apply_fill(fill(quantity=D("1e18")))
        terminal(self.j, quantity=D("1e18"))
        for seq, quantity in ((2, D("1e-18")), (3, None)):
            lot = self.j.lots.list_current(scope=scope(), bot_id="precise")[0].lot
            order = f"precise-close-{seq}"
            resolved = lot.remaining_qty if quantity is None else quantity
            if quantity is None:
                self.assertGreater(len(resolved.as_tuple().digits), 28)
            self.j.lot_fills.bind_order(source_id="synthetic", order_id=order,
                context=lots.IntentContext(scope(), "precise", spec, seq, False),
                intent=lots.CloseLot(lot.lot_id, quantity, lot.revision))
            self.j.lot_fills.apply_fill(fill(order=order, quantity=resolved))
            terminal(self.j, order=order, quantity=resolved)
        self.reopen()
        self.assertEqual(self.j.lots.list_current(scope=scope(), bot_id="precise")[0].lot.remaining_qty, D(0))


if __name__ == "__main__":
    unittest.main()
