"""Test-only OS lock and SQLite process-crash probes."""

from decimal import Decimal as D
from pathlib import Path
import os
import sys

from catos import account_lock
from catos.account_lock import AccountBindingError, AccountBusy, AccountLock
from catos.journal import FixtureDecision, Journal
from test_ipc import config
from test_journal import STEP, input_for, proof, result_for


def main():
    mode, root, database = sys.argv[1:]
    account_lock.LOCK_DIRECTORY = Path(root)
    lock = AccountLock("fake-account")
    try:
        lock.acquire()
    except AccountBusy:
        return 17
    if mode == "hold":
        print("LOCKED", flush=True)
        sys.stdin.buffer.read(1)
        lock.close()
        return 0
    try:
        lock.check_database(database)
    except AccountBindingError:
        lock.close()
        return 19
    journal = Journal(database, "fake-account", D("100"))
    try:
        journal.register("bot", config())
        lock.bind_database(database)
        if mode == "compete":
            return 0
        state = journal.snapshot("bot")
        journal.reconcile("bot", proof(state["revision"]))
        journal.prepare("bot", 3, input_for(2, "101"), 4 * STEP)
        original = journal._commit

        def crash():
            if mode == "after_commit":
                original()
            os._exit(72 if mode == "after_commit" else 71)

        journal._commit = crash
        journal.commit_result("bot", result_for(state["checkpoint"], 2, "101", D("2")),
                              FixtureDecision(True, D("80")), 3 * STEP)
    finally:
        journal.close()
        lock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
