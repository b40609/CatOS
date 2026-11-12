"""Schema 7 stays byte-identical after the Virtual Lots prototype was removed."""

from contextlib import closing
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from catos import risk
from catos.journal import Journal, JournalError, RETAINED_LOT_TABLES, RETAINED_LOT_FILL_TABLES
from journal_legacy_helpers import drop_empty_fill_schema, drop_empty_lot_schema
from test_ipc import config
from test_journal import prepare_and_commit, proof

D = Decimal
# Captured from git e95d37dc (before removal) by
# reports/remove-virtual-lots-acceptance-20261112/dump_journal_schema.py.
BASELINE = json.loads((Path(__file__).parent / "fixtures" / "journal_schema_v7.json")
                      .read_text(encoding="utf-8"))


def schema(path):
    with closing(sqlite3.connect(path)) as db:
        rows = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")
        return db.execute("PRAGMA user_version").fetchone()[0], [list(row) for row in rows]


def _drop(db, *tables):
    for table in tables:
        db.execute(f"DROP TABLE {table}")


# What each older user_version lacked, mirroring the Journal upgrade steps.
DOWNGRADES = {
    6: lambda db: drop_empty_fill_schema(db),
    5: lambda db: drop_empty_lot_schema(db),
    4: lambda db: _drop(db, "protection"),
    3: lambda db: _drop(db, "risk_actions"),
    2: lambda db: _drop(db, "execution_fills", "execution_orders", "execution_mode"),
    1: lambda db: _drop(db, "risk_orders", "risk_control"),
}


class JournalSchemaTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def open(self, name, *args):
        journal = Journal(self.root / name, "fake-account", D("100"), *args)
        self.addCleanup(journal.close)
        return journal

    def test_new_ledger_schema_and_user_version_match_pre_removal_baseline(self):
        self.assertEqual(BASELINE["user_version"], 7)
        for name, args in (("plain", ()), ("risk", (risk.Limits(),)),
                           ("execution", (risk.Limits(), True))):
            with self.subTest(name):
                self.open(f"{name}.sqlite3", *args).close()
                self.assertEqual(schema(self.root / f"{name}.sqlite3"),
                                 (7, BASELINE["sqlite_master"]))

    def test_retained_lot_tables_are_the_six_baseline_tables_and_stay_empty(self):
        journal = self.open("new.sqlite3")
        names = {row[1] for row in BASELINE["sqlite_master"] if row[0] == "table"}
        self.assertEqual(set(RETAINED_LOT_TABLES + RETAINED_LOT_FILL_TABLES),
                         {name for name in names if name.startswith("lot_")})
        self.assertFalse(hasattr(journal, "lots") or hasattr(journal, "lot_fills"))
        for table in RETAINED_LOT_TABLES + RETAINED_LOT_FILL_TABLES:
            self.assertEqual(journal.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)

    def test_versions_one_to_six_upgrade_to_identical_schema_seven(self):
        for version in range(1, 7):
            with self.subTest(version=version):
                path = self.root / f"v{version}.sqlite3"
                journal = Journal(path, "fake-account", D("100"))
                journal.register("bot", config())
                journal.reconcile("bot", proof(0))
                prepare_and_commit(journal, 0)
                journal.close()
                with closing(sqlite3.connect(path)) as db, db:
                    for step in range(6, version - 1, -1):
                        DOWNGRADES[step](db)
                    db.execute(f"PRAGMA user_version={version}")
                journal = Journal(path, "fake-account", D("100"))
                try:
                    self.assertEqual(journal.snapshot("bot")["checkpoint"].event_seq, 1)
                finally:
                    journal.close()
                self.assertEqual(schema(path)[0], 7)
                # Upgrade order changes rootpage, never the statements themselves.
                self.assertEqual(sorted(schema(path)[1]), sorted(BASELINE["sqlite_master"]))

    def test_unexpected_retained_table_before_install_is_refused(self):
        path = self.root / "partial.sqlite3"
        Journal(path, "fake-account", D("100")).close()
        with closing(sqlite3.connect(path)) as db, db:
            drop_empty_fill_schema(db)
            _drop(db, "lot_revisions")  # lot_bindings/lot_heads remain: not a real v5 ledger.
            db.execute("PRAGMA user_version=5")
        with self.assertRaisesRegex(JournalError, "retained table"):
            Journal(path, "fake-account", D("100"))
        self.assertEqual(schema(path)[0], 5)

    def test_prototype_schema_eight_and_nine_ledgers_are_refused_unchanged(self):
        for version in (8, 9):
            with self.subTest(version=version):
                path = self.root / f"v{version}.sqlite3"
                Journal(path, "fake-account", D("100")).close()
                with closing(sqlite3.connect(path)) as db, db:
                    db.execute(f"PRAGMA user_version={version}")
                before = schema(path)
                with self.assertRaisesRegex(JournalError, "Virtual Lots prototype"):
                    Journal(path, "fake-account", D("100"))
                self.assertEqual(schema(path), before)

    def test_unknown_versions_still_refused(self):
        for version in (10, 99):
            with self.subTest(version=version):
                path = self.root / f"v{version}.sqlite3"
                Journal(path, "fake-account", D("100")).close()
                with closing(sqlite3.connect(path)) as db, db:
                    db.execute(f"PRAGMA user_version={version}")
                with self.assertRaisesRegex(JournalError, "unsupported journal schema"):
                    Journal(path, "fake-account", D("100"))

    def test_startup_integrity_check_still_refuses_a_corrupt_ledger(self):
        path = self.root / "corrupt.sqlite3"
        journal = Journal(path, "fake-account", D("100"))
        journal.register("bot", config())
        journal.close()
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("PRAGMA writable_schema=ON")
            # Point the bots table's unique index at the wrong root page.
            db.execute("UPDATE sqlite_master SET rootpage=(SELECT rootpage FROM sqlite_master "
                       "WHERE name='control') WHERE name='sqlite_autoindex_bots_1'")
        with self.assertRaises((JournalError, sqlite3.DatabaseError)):
            Journal(path, "fake-account", D("100"))


if __name__ == "__main__":
    unittest.main()
