"""S2 test-only crash probes using a temporary database and account lock."""

from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import os
import sys

from catos import account_lock
from catos.account_lock import AccountLock
from catos.journal import Journal
from lot_journal_helpers import create, snapshot, update


class CrashAfterHead:
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, sql, args=()):
        result = self.connection.execute(sql, args)
        if sql.startswith("INSERT INTO lot_heads"):
            os._exit(73)
        return result


def main():
    mode, root, database = sys.argv[1:]
    if mode not in ("partial_create", "before_commit", "after_commit", "after_commit_multi"):
        raise ValueError("unknown synthetic crash mode")
    account_lock.LOCK_DIRECTORY = Path(root)
    lock = AccountLock("fake-account")
    lock.acquire()
    journal = None
    try:
        lock.check_database(database)
        journal = Journal(database, "fake-account", D("100"))
        lock.bind_database(database)
        if mode == "partial_create":
            journal.lots.db = CrashAfterHead(journal.connection)
            create(journal, write_id="process-create")
        else:
            original_commit = journal._commit

            def crash_commit():
                if mode != "before_commit":
                    original_commit()
                os._exit(71 if mode == "before_commit" else 72)

            journal._commit = crash_commit
            update(journal, replace(snapshot(), revision=2, remaining_qty=D("1")),
                   write_id="process-update", closing=True)
        raise AssertionError("crash probe unexpectedly returned")
    finally:
        if journal is not None:
            journal.close()
        lock.close()


if __name__ == "__main__":
    main()
