"""Synthetic S3 process-death probes; only caller-provided temporary DB."""
from decimal import Decimal as D
from pathlib import Path
import os
import sys

from catos import account_lock
from catos.account_lock import AccountLock
from catos.journal import Journal
from lot_fill_helpers import fill, terminal


class CrashAfterEvent:
    def __init__(self, db):
        self.db = db

    def __getattr__(self, name):
        return getattr(self.db, name)

    def execute(self, sql, args=()):
        result = self.db.execute(sql, args)
        if sql.startswith("INSERT INTO lot_fill_events"):
            os._exit(73)
        return result


def main():
    mode, directory, path = sys.argv[1:]
    if mode not in ("first_open", "before_close", "after_close", "before_terminal", "after_terminal"):
        raise ValueError("unknown crash mode")
    account_lock.LOCK_DIRECTORY = Path(directory)
    lock = AccountLock("fake-account")
    lock.acquire()
    journal = None
    try:
        lock.check_database(path)
        journal = Journal(path, "fake-account", D(100))
        lock.bind_database(path)
        if mode == "first_open":
            journal.lot_fills.db = CrashAfterEvent(journal.connection)
            journal.lot_fills.apply_fill(fill(quantity=D(3)))
        else:
            original = journal._commit
            def crash():
                if mode.startswith("after"):
                    original()
                os._exit(72 if mode.startswith("after") else 71)
            journal._commit = crash
            if mode.endswith("terminal"):
                terminal(journal, order="close")
            else:
                journal.lot_fills.apply_fill(fill(order="close", quantity=D(1)))
        raise AssertionError("probe returned")
    finally:
        if journal is not None:
            journal.close()
        lock.close()


if __name__ == "__main__":
    main()
