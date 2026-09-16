"""S01-S34: synthetic SQLite storage, recovery and v1 isolation; no network."""

from contextlib import closing
from dataclasses import replace
from decimal import Decimal as D, ROUND_DOWN, localcontext
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from catos import ipc, lot_journal, lots, risk
from catos.journal import FixtureDecision, Journal, JournalError, OwnershipError
from catos.lot_journal import LotStorageError, TABLES
from lot_journal_helpers import contract, create, drop_empty_lot_schema, scope, snapshot, update
from test_ipc import config, STEP
from test_journal import prepare_and_commit, proof
from test_risk import snapshot as risk_snapshot


class FailingConnection:
    """Inject after a real SQL statement, before the surrounding COMMIT."""
    def __init__(self, connection, prefix):
        self.connection, self.prefix = connection, prefix

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, sql, args=()):
        result = self.connection.execute(sql, args)
        if sql.lstrip().startswith(self.prefix):
            raise sqlite3.OperationalError("synthetic write failure")
        return result


class LotJournalTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / "state.sqlite3"
        self.j = Journal(self.path, "fake-account", D("100"))
        self.addCleanup(lambda: self.j.close() if self.j is not None else None)
        self.bind()
        self.copy_index = 0

    def bind(self, bot="lot-bot", spec=None):
        self.j.lots.register_binding(scope=scope(), bot_id=bot, contract=spec or contract())

    def reopen(self, **options):
        if self.j is not None:
            self.j.close()
        self.j = None
        self.j = Journal(self.path, "fake-account", D("100"), **options)

    def get(self, value=None):
        value = value or snapshot()
        return self.j.lots.get(scope=scope(), bot_id=value.bot_id, lot_id=value.lot_id)

    def dump(self, tables=TABLES):
        return {table: sorted((tuple(row) for row in self.j.connection.execute(f"SELECT * FROM {table}")),
                              key=repr) for table in tables}

    def copy(self):
        self.copy_index += 1
        path = self.root / f"copy-{self.copy_index}.sqlite3"
        with closing(sqlite3.connect(path)) as db:
            self.j.connection.backup(db)
        return path

    def corrupt(self, sql, args=(), *, ignore_checks=False):
        path = self.copy()
        with closing(sqlite3.connect(path)) as db, db:
            if ignore_checks:
                db.execute("PRAGMA ignore_check_constraints=ON")
            db.execute(sql, args)
        with self.assertRaises(JournalError):
            Journal(path, "fake-account", D("100"))
        return path

    def test_s01_schema_wal_full_foreign_keys_and_strict_tables(self):
        db = self.j.connection
        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 6)
        self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(db.execute("PRAGMA synchronous").fetchone()[0], 2)
        self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        strict = {row["name"]: row["strict"] for row in db.execute("PRAGMA table_list")}
        for table in TABLES:
            self.assertEqual(strict[table], 1)
            self.assertTrue(db.execute(f"PRAGMA index_list({table})").fetchall())
        self.assertEqual(len(db.execute("PRAGMA foreign_key_list(lot_heads)").fetchall()), 3)
        self.assertEqual(len(db.execute("PRAGMA foreign_key_list(lot_revisions)").fetchall()), 2)
        value = snapshot()
        # A head without its first revision must fail at COMMIT, not persist.
        with self.assertRaises(sqlite3.IntegrityError):
            with self.j._transaction():
                db.execute("INSERT INTO lot_heads VALUES (?,?,?,?,?,?)",
                           (value.lot_id, value.bot_id, 1, value.open_intent_key, "long", 1))
        self.assertEqual(db.execute("SELECT count(*) FROM lot_heads").fetchone()[0], 0)

    def test_s02_upgrade_real_schema_five_preserves_v1_data_and_latch(self):
        self.j.register("bot", config())
        self.j.record_halts({"hard_loss"})
        path = self.copy()
        with closing(sqlite3.connect(path)) as db, db:
            # This copy has no Lot data; remove the empty binding first.
            db.execute("DELETE FROM lot_bindings")
            drop_empty_lot_schema(db)
            db.execute("PRAGMA user_version=5")
            original = db.execute("SELECT * FROM bots").fetchall()
        with closing(Journal(path, "fake-account", D("100"))) as upgraded:
            self.assertEqual([tuple(r) for r in upgraded.connection.execute("SELECT * FROM bots")], original)
            for table in TABLES:
                self.assertEqual(upgraded.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)
            self.assertIn("hard_loss", upgraded.snapshot("bot")["halt_reasons"])

    def test_s03_failed_migration_rolls_back_ddl_and_version(self):
        path = self.copy()
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("DELETE FROM lot_bindings")
            drop_empty_lot_schema(db)
            db.execute("PRAGMA user_version=5")

        def fail_midway(connection):
            connection.execute(lot_journal.SCHEMA[0])
            raise sqlite3.OperationalError("synthetic migration failure")

        with patch.object(lot_journal, "install_schema", fail_midway), self.assertRaises(sqlite3.Error):
            Journal(path, "fake-account", D("100"))
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 5)
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='lot_bindings'").fetchone())
        with closing(Journal(path, "fake-account", D("100"))) as upgraded:
            self.assertEqual(upgraded.connection.execute("PRAGMA user_version").fetchone()[0], 6)

    def test_s04_invalid_schema_and_scope_do_not_rebuild(self):
        for sql in ("PRAGMA user_version=99", "PRAGMA user_version=5",
                    "DROP TABLE lot_revisions", "UPDATE metadata SET environment='demo'"):
            with self.subTest(sql=sql):
                self.corrupt(sql)
        with self.assertRaises(JournalError):
            Journal(self.path, "other-account", D("100"))
        for environment in ("demo", "live"):
            with self.assertRaisesRegex(LotStorageError, "scope_mismatch"):
                self.j.lots.register_binding(scope=lots.LotScope("fake-account", environment),
                                             bot_id="new", contract=contract())
        with patch.object(sqlite3, "sqlite_version_info", (3, 36, 0)), self.assertRaises(JournalError):
            Journal(self.path, "fake-account", D("100"))

    def test_s05_bindings_are_immutable_idempotent_and_allow_same_contract(self):
        before = self.dump()
        self.bind(spec=contract(base_per_contract=D("0.010")))
        self.assertEqual(self.dump(), before)
        for spec in (contract(inst_id="OTHER-USDT-SWAP"), contract(lot_size=D("1"))):
            with self.assertRaisesRegex(LotStorageError, "binding_conflict"):
                self.bind(spec=spec)
        self.bind("other")
        create(self.j, snapshot(bot="other"))
        create(self.j)
        self.assertEqual(self.j.lots.recover().lot_count, 2)

    def test_s06_create_atomically_stores_first_revision_and_receipt(self):
        receipt = create(self.j)
        self.assertEqual((receipt.revision, receipt.commit_seq, receipt.replayed), (1, 1, False))
        self.assertEqual(self.get().lot, snapshot())
        for table in ("lot_heads", "lot_revisions"):
            self.assertEqual(self.j.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 1)
        for table in ("bots", "ownership", "execution_orders"):
            self.assertEqual(self.j.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)

    def test_s07_invalid_create_never_persists_an_empty_or_forged_lot(self):
        before = self.dump()
        for field, value in (("opened_qty", D("0")), ("average_entry", D("NaN")),
                             ("fees_paid", 0.1), ("lot_id", "a" * 64)):
            bad = snapshot()
            object.__setattr__(bad, field, value)
            with self.subTest(field=field), self.assertRaises(LotStorageError):
                create(self.j, bad)
        with self.assertRaisesRegex(LotStorageError, "identity_conflict"):
            create(self.j, snapshot(), seq=2)
        self.assertEqual(self.dump(), before)

    def test_s08_decimal_text_rebate_and_unknown_funding_round_trip(self):
        create(self.j)
        row = self.j.connection.execute("SELECT typeof(opened_qty),typeof(fees_paid),fees_paid,funding_paid FROM lot_revisions").fetchone()
        self.assertEqual(tuple(row), ("text", "text", "-0.1", None))
        for revision, funding in ((2, D("0")), (3, D("-0.25"))):
            value = replace(snapshot(), revision=revision, funding_paid=funding)
            update(self.j, value, expected=revision - 1, write_id=f"funding-{revision}")
            self.assertEqual(self.get().lot.funding_paid, funding)
        historical = self.j.lots.get_revision(scope=scope(), bot_id="lot-bot", lot_id=snapshot().lot_id, revision=1)
        self.assertIsNone(historical.lot.funding_paid)

    def test_s09_derived_exponent_boundaries_round_trip_and_excess_is_rejected(self):
        for seq, text in enumerate(("1e50", "1e99", "1e-148", "9" * 50 + "e50"), 1):
            value = snapshot(seq=seq, average_entry=D(text), fees_paid=D(text).copy_negate())
            create(self.j, value, seq=seq, write_id=f"large-{seq}")
            self.assertEqual(self.get(value).lot, value)
        self.reopen()
        self.assertEqual(self.j.lots.recover().lot_count, 4)
        for text in ("1e100", "1e-149", "1." + "0" * 50):
            bad = snapshot(seq=10)
            object.__setattr__(bad, "average_entry", D(text))
            with self.assertRaises(LotStorageError):
                create(self.j, bad, seq=10, write_id="bad")

    def test_s10_derived_quantity_fragments_and_contract_validation(self):
        spec = contract(lot_size=D("0.0000000001"))
        self.bind("precise", spec)
        amount = D("1000000000000000001.0000000001")
        value = snapshot(bot="precise", spec=spec, opened_qty=amount, remaining_qty=amount)
        create(self.j, value)
        closed = replace(value, remaining_qty=D("0"), revision=2)
        update(self.j, closed)
        fragment = snapshot(seq=2, opened_qty=D("1"), remaining_qty=D("0.5"))
        create(self.j, fragment, seq=2, write_id="fragment")
        self.assertEqual(self.get(fragment).lot.average_entry, D("100.25"))
        for bad in (snapshot(seq=3, remaining_qty=D("0.25")),
                    snapshot(seq=3, protection=lots.LotProtection("mark", D("120.25"), None))):
            with self.assertRaises(LotStorageError):
                create(self.j, bad, seq=3, write_id="unaligned")

    def test_s11_update_retains_history_and_advances_head_and_sequence(self):
        create(self.j)
        value = replace(snapshot(), revision=2, remaining_qty=D("1"), realized_pnl=D("2"))
        receipt = update(self.j, value)
        self.assertEqual((receipt.revision, receipt.commit_seq), (2, 2))
        self.assertEqual(self.get().lot, value)
        self.assertEqual(self.j.lots.get_revision(scope=scope(), bot_id="lot-bot",
                         lot_id=value.lot_id, revision=1).lot, snapshot())

    def test_s12_bad_revision_and_sequence_types_leave_tables_unchanged(self):
        create(self.j)
        before = self.dump()
        for expected in (0, True, -1, ipc.MAX_INTEGER + 1, 2):
            with self.subTest(expected=expected), self.assertRaises(LotStorageError):
                update(self.j, replace(snapshot(), revision=2, remaining_qty=D("1")), expected=expected)
        with self.assertRaisesRegex(LotStorageError, "revision_conflict"):
            update(self.j, replace(snapshot(), revision=3, remaining_qty=D("1")))
        with self.assertRaises(LotStorageError):
            create(self.j, snapshot(seq=2), seq=True, write_id="bool")
        self.assertEqual(self.dump(), before)

    def test_s13_two_candidates_from_same_revision_only_commit_once(self):
        create(self.j)
        a = replace(snapshot(), revision=2, remaining_qty=D("1"))
        b = replace(snapshot(), revision=2, remaining_qty=D("0.5"))
        update(self.j, a, write_id="a")
        before = self.dump()
        with self.assertRaisesRegex(LotStorageError, "revision_conflict"):
            update(self.j, b, write_id="b")
        self.assertEqual(self.dump(), before)
        self.assertEqual(self.get().commit_seq, 2)

    def test_s14_identity_changes_and_cross_bot_reads_are_rejected(self):
        create(self.j)
        self.bind("other")
        value = snapshot()
        self.assertIsNone(self.j.lots.get(scope=scope(), bot_id="other", lot_id=value.lot_id))
        for changes in (dict(side="short"), dict(inst_id="OTHER-USDT-SWAP"),
                        dict(scope=lots.LotScope("other-account", "local-sim"))):
            with self.assertRaisesRegex(LotStorageError, "identity_conflict"):
                update(self.j, replace(value, revision=2, remaining_qty=D("1"), **changes))
        with self.assertRaisesRegex(LotStorageError, "scope_mismatch"):
            self.j.lots.get(scope=lots.LotScope("other-account", "local-sim"),
                            bot_id="lot-bot", lot_id=value.lot_id)

    def test_s15_same_write_id_and_numeric_equivalence_return_original_receipt(self):
        first = create(self.j)
        equivalent = replace(snapshot(), opened_qty=D("2.0"), remaining_qty=D("2e0"), fees_paid=D("-0.10"))
        repeated = create(self.j, equivalent)
        self.assertEqual(replace(repeated, replayed=False), first)
        self.assertTrue(repeated.replayed)
        self.assertEqual(self.j.lots.recover().revision_count, 1)

    def test_s16_same_write_id_with_changed_content_is_conflict(self):
        create(self.j)
        before = self.dump()
        for changed in (snapshot(remaining_qty=D("1")), snapshot(seq=2)):
            with self.assertRaisesRegex(LotStorageError, "write_conflict"):
                create(self.j, changed, seq=2 if changed.lot_id != snapshot().lot_id else 1)
        with self.assertRaisesRegex(LotStorageError, "write_conflict"):
            create(self.j, opening=True)
        with self.assertRaisesRegex(LotStorageError, "write_conflict"):
            update(self.j, replace(snapshot(), revision=2, remaining_qty=D("1")), write_id="create-1")
        self.assertEqual(self.dump(), before)

    def test_s17_old_receipt_replays_after_newer_commits_and_restart(self):
        first = create(self.j)
        second_lot = replace(snapshot(), revision=2, remaining_qty=D("1"))
        second = update(self.j, second_lot)
        update(self.j, replace(second_lot, revision=3, remaining_qty=D("0")), expected=2, write_id="close")
        self.reopen()
        self.assertEqual(replace(create(self.j), replayed=False), first)
        self.assertEqual(replace(update(self.j, second_lot), replayed=False), second)
        self.assertEqual(self.get().lot.revision, 3)
        self.assertEqual(self.j.lots.recover().revision_count, 3)

    def test_s18_no_change_refused_but_flag_changes_have_versions(self):
        create(self.j)
        value = replace(snapshot(), revision=2)
        with self.assertRaisesRegex(LotStorageError, "no_change"):
            update(self.j, value)
        receipt = update(self.j, value, opening=True)
        self.assertTrue(self.get().opening_unresolved)
        self.assertEqual(replace(update(self.j, value, opening=True), replayed=False), receipt)

    def test_s19_closed_lot_cannot_reopen_but_can_receive_accounting_snapshot(self):
        create(self.j)
        closed = replace(snapshot(), revision=2, remaining_qty=D("0"))
        update(self.j, closed)
        for changes in (dict(remaining_qty=D("1")), dict(opened_qty=D("3")),
                        dict(opened_qty=D("1")), dict(average_entry=D("101"))):
            with self.assertRaisesRegex(LotStorageError, "invalid_transition"):
                update(self.j, replace(closed, revision=3, **changes), expected=2, write_id="bad")
        updated = replace(closed, revision=3, fees_paid=D("0.3"), funding_paid=D("-0.1"))
        update(self.j, updated, expected=2, write_id="late-fee")
        self.assertEqual(self.get().lot, updated)

    def test_s20_quantity_and_average_transition_rules(self):
        first = snapshot(remaining_qty=D("1"))
        create(self.j, first)
        for changes in (dict(remaining_qty=D("1.5")), dict(average_entry=D("102"))):
            with self.assertRaisesRegex(LotStorageError, "invalid_transition"):
                update(self.j, replace(first, revision=2, **changes))
        grown = replace(first, revision=2, opened_qty=D("3"), remaining_qty=D("2"), average_entry=D("101.25"))
        update(self.j, grown)
        reduced = replace(grown, revision=3, remaining_qty=D("1"), realized_pnl=D("2"))
        update(self.j, reduced, expected=2, write_id="reduce")
        self.assertEqual(self.get().lot, reduced)

    def test_s21_flat_unresolved_snapshot_survives_restart_without_releasing_v1(self):
        self.j.register("bot", config())
        create(self.j, snapshot(remaining_qty=D("0")), closing=True)
        self.reopen()
        current = self.get()
        self.assertEqual(current.lot.remaining_qty, D("0"))
        self.assertTrue(current.closing_unresolved)
        self.assertEqual(self.j.lots.recover().unresolved_lot_count, 1)
        self.assertEqual(self.j.connection.execute("SELECT bot_id FROM ownership").fetchone()[0], "bot")

    def test_s22_pagination_history_and_closed_lots(self):
        values = [snapshot(seq=i, remaining_qty=D("0") if i == 2 else D("2")) for i in (1, 2, 3)]
        for seq, value in enumerate(values, 1):
            create(self.j, value, seq=seq, write_id=f"create-{seq}")
        seen, cursor = [], None
        for _ in values:
            page = self.j.lots.list_current(scope=scope(), bot_id="lot-bot", after_lot_id=cursor, limit=1)
            self.assertEqual(len(page), 1)
            seen.append(page[0].lot.lot_id)
            cursor = seen[-1]
        self.assertEqual(seen, sorted(v.lot_id for v in values))
        self.assertEqual(self.j.lots.list_current(scope=scope(), bot_id="lot-bot", after_lot_id=cursor), ())
        self.assertIsNone(self.j.lots.get_revision(scope=scope(), bot_id="lot-bot", lot_id=values[0].lot_id, revision=2))
        for limit in (0, 1001, True):
            with self.assertRaises(LotStorageError):
                self.j.lots.list_current(scope=scope(), bot_id="lot-bot", limit=limit)

    def test_s23_each_mutating_statement_is_rolled_back_on_sql_failure(self):
        create(self.j)
        cases = (("CREATE", "INSERT INTO lot_heads"), ("CREATE", "INSERT INTO lot_revisions"),
                 ("CREATE", "UPDATE lot_bindings"), ("REPLACE", "INSERT INTO lot_revisions"),
                 ("REPLACE", "UPDATE lot_heads"), ("REPLACE", "UPDATE lot_bindings"))
        for operation, prefix in cases:
            with self.subTest(operation=operation, prefix=prefix):
                before = self.dump()
                self.j.lots.db = FailingConnection(self.j.connection, prefix)
                with self.assertRaisesRegex(LotStorageError, "storage_unavailable"):
                    if operation == "CREATE":
                        create(self.j, snapshot(seq=2), seq=2, write_id="second")
                    else:
                        update(self.j, replace(snapshot(), revision=2, remaining_qty=D("1")))
                self.assertEqual(self.dump(), before)
                self.reopen()

    def test_s24_busy_and_uncertain_commit_require_reopen_and_same_id(self):
        with closing(sqlite3.connect(self.path, isolation_level=None)) as other:
            other.execute("BEGIN IMMEDIATE")
            with self.assertRaisesRegex(LotStorageError, "storage_unavailable"):
                create(self.j)
            other.rollback()
        with self.assertRaisesRegex(LotStorageError, "storage_unavailable"):
            create(self.j)
        self.reopen()
        commit = self.j._commit

        def commit_then_error():
            commit()
            raise sqlite3.OperationalError("synthetic lost completion")

        with patch.object(self.j, "_commit", commit_then_error), self.assertRaises(LotStorageError):
            create(self.j)
        with self.assertRaises(LotStorageError):
            self.get()
        self.reopen()
        self.assertTrue(create(self.j).replayed)
        self.assertEqual(self.j.lots.recover().revision_count, 1)

    def test_s25_sequence_limits_never_wrap_or_partially_commit(self):
        create(self.j)
        before = self.dump()
        with self.assertRaisesRegex(LotStorageError, "sequence_exhausted"):
            update(self.j, replace(snapshot(), revision=ipc.MAX_INTEGER), expected=ipc.MAX_INTEGER)
        self.assertEqual(self.dump(), before)
        # Artificial boundary fixture: not a claim to have MAX_INTEGER history rows.
        self.j.connection.execute("UPDATE lot_bindings SET last_commit_seq=?", (ipc.MAX_INTEGER,))
        boundary = self.dump()
        with self.assertRaisesRegex(LotStorageError, "sequence_exhausted"):
            create(self.j, snapshot(seq=2), seq=2, write_id="overflow")
        self.assertEqual(self.dump(), boundary)

    def test_s26_decimal_context_does_not_change_storage_or_fingerprint(self):
        with localcontext() as active:
            active.prec = 2
            active.rounding = ROUND_DOWN
            flags = dict(active.flags)
            receipt = create(self.j, snapshot(fees_paid=D("-0.1234567890123456789")))
            self.assertEqual(self.get().lot.fees_paid, D("-0.1234567890123456789"))
            self.assertEqual((active.prec, active.rounding, dict(active.flags)), (2, ROUND_DOWN, flags))
        repeated = create(self.j, snapshot(fees_paid=D("-0.12345678901234567890")))
        self.assertEqual(receipt.request_hash, repeated.request_hash)

    def test_s27_interleaved_lots_replay_and_open_sequence_arrival_can_differ(self):
        a, b = snapshot(seq=9), snapshot(seq=2)
        create(self.j, a, seq=9, write_id="a")
        create(self.j, b, seq=2, write_id="b")
        update(self.j, replace(a, revision=2, remaining_qty=D("1")), write_id="a2")
        update(self.j, replace(b, revision=2, remaining_qty=D("0")), write_id="b2")
        before = self.dump()
        report = self.j.lots.recover()
        self.assertEqual((report.lot_count, report.revision_count), (2, 4))
        self.assertEqual(self.dump(), before)
        self.reopen()
        self.assertEqual((self.get(a).commit_seq, self.get(b).commit_seq), (3, 4))

    def three_versions(self):
        create(self.j)
        update(self.j, replace(snapshot(), revision=2, remaining_qty=D("1")))
        update(self.j, replace(snapshot(), revision=3, remaining_qty=D("0")), expected=2, write_id="close")

    def test_s28_missing_versions_and_bad_watermark_fail_recovery(self):
        self.three_versions()
        for sql in ("DELETE FROM lot_revisions WHERE revision=2",
                    "DELETE FROM lot_revisions WHERE revision=3",
                    "UPDATE lot_bindings SET last_commit_seq=2",
                    "UPDATE lot_bindings SET last_commit_seq=4"):
            with self.subTest(sql=sql):
                self.corrupt(sql)

    def test_s29_missing_stale_heads_or_rebound_identity_fail_recovery(self):
        self.three_versions()
        for sql in ("DELETE FROM lot_heads", "UPDATE lot_heads SET current_revision=2",
                    "UPDATE lot_heads SET open_event_seq=7", "DELETE FROM lot_bindings"):
            with self.subTest(sql=sql):
                self.corrupt(sql)

    def test_s30_mutated_numbers_requests_and_hashes_are_detected(self):
        create(self.j)
        for sql in ("UPDATE lot_revisions SET fees_paid='0.9'",
                    "UPDATE lot_revisions SET request_json='{}'",
                    "UPDATE lot_revisions SET request_hash='" + "a" * 64 + "'"):
            with self.subTest(sql=sql):
                self.corrupt(sql)
        self.j.connection.execute("UPDATE lot_revisions SET fees_paid='0.9'")
        with self.assertRaisesRegex(LotStorageError, "integrity_error"):
            self.get()

    def test_s31_invalid_stored_values_are_never_replaced_by_defaults(self):
        create(self.j)
        cases = (("UPDATE lot_revisions SET average_entry='NaN'", False),
                 ("UPDATE lot_revisions SET opening_unresolved=3", True),
                 ("UPDATE lot_revisions SET expected_revision=5", True),
                 ("UPDATE lot_bindings SET contract_json='{}'", False),
                 ("UPDATE lot_bindings SET contract_json='{" + '"inst_id":"x","inst_id":"y"' + "}'", False))
        for sql, ignore in cases:
            with self.subTest(sql=sql):
                self.corrupt(sql, ignore_checks=ignore)

    def test_s32_recovery_is_read_only_for_empty_and_closed_multibot_data(self):
        report = self.j.lots.recover()
        self.assertEqual((report.storage_ready, report.lot_count, report.revision_count), (True, 0, 0))
        self.bind("other")
        create(self.j, snapshot(remaining_qty=D("0")))
        create(self.j, snapshot(bot="other"), opening=True)
        before = self.dump()
        report = self.j.lots.recover()
        self.assertEqual((report.binding_count, report.lot_count, report.unresolved_lot_count), (2, 2, 1))
        self.assertEqual(self.dump(), before)
        self.assertEqual(self.j.connection.execute("SELECT count(*) FROM execution_orders").fetchone()[0], 0)

    def test_s33_lot_writes_leave_all_v1_tables_unchanged(self):
        self.j.register("bot", config())
        tables = [r[0] for r in self.j.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                  if r[0] not in TABLES and not r[0].startswith("sqlite_")]
        before = self.dump(tables)
        create(self.j)
        update(self.j, replace(snapshot(), revision=2, remaining_qty=D("0")))
        self.assertEqual(self.dump(tables), before)
        with self.assertRaises(OwnershipError):
            self.j.register("other", config())

    def test_s34_restart_preserves_v1_latch_unknown_reservation_and_p6_obligation(self):
        self.reopen(risk_limits=risk.Limits(), execution_enabled=True)
        self.j.register("bot", config())
        self.j.reconcile("bot", proof(0))
        previous = self.j.risk_state()
        self.j.save_risk(risk.observe(previous, risk_snapshot(previous.seq + 1, 3 * STEP,
                                                             valid_until_ms=10 * STEP)))
        prepare_and_commit(self.j, 0)
        prepare_and_commit(self.j, 1)
        receipt = prepare_and_commit(self.j, 2, target=D("2"))
        request = self.j.execution.prepare("bot", receipt.intent_key, 3 * STEP)
        self.assertIsNotNone(request)
        self.j.record_halts({"hard_loss", "manual_kill"})
        protection = self.j.protection.state("bot")
        protection["pending"] = {"synthetic": "unresolved"}
        with self.j._transaction():
            self.j.protection.save("bot", protection)
        create(self.j, closing=True)
        reserved = self.j.total_reserved()
        self.reopen(risk_limits=risk.Limits(), execution_enabled=True)
        state = self.j.snapshot("bot")
        self.assertEqual(set(state["halt_reasons"]), {"hard_loss", "manual_kill"})
        self.assertEqual(state["health"], "RECONCILING")
        self.assertIsNone(state["owner"]["reconciled_revision"])
        self.assertEqual(self.j.total_reserved(), reserved)
        self.assertEqual(self.j.execution.order(receipt.intent_key)["state"], "UNKNOWN")
        self.assertTrue(self.j.protection.state("bot")["uncertain"])
        self.assertEqual(self.j.protection.state("bot")["pending"], protection["pending"])
        self.assertTrue(self.get().closing_unresolved)


if __name__ == "__main__":
    unittest.main()
