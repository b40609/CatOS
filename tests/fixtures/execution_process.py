"""Real process termination around G's durable handoff; synthetic account only."""

import asyncio
from decimal import Decimal as D
import os
from pathlib import Path
import sys

from catos import account_lock, risk
from catos.account_lock import AccountLock
from catos.fake_exchange import FakeExchange
from catos.journal import Journal
from test_ipc import STEP, config
from test_journal import prepare_and_commit, proof
from test_risk import snapshot


def main():
    mode, root, database = sys.argv[1:]
    account_lock.LOCK_DIRECTORY = Path(root)
    lock = AccountLock("fake-account")
    lock.acquire()
    lock.check_database(database)
    j = Journal(database, "fake-account", D("100"), risk.Limits(), True)
    j.register("bot", config())
    lock.bind_database(database)
    j.reconcile("bot", proof(j.snapshot("bot")["revision"]))
    j.save_risk(risk.observe(j.risk_state(), snapshot(j.risk_state().seq + 1, 3 * STEP, valid_until_ms=10 * STEP)))
    receipt = prepare_and_commit(j, 2, target=D("2"))
    original = j._commit

    def crash():
        if mode == "after_commit":
            original()
        os._exit(71 if mode == "before_commit" else 72)

    if mode in ("before_commit", "after_commit"):
        j._commit = crash
    request = j.execution.prepare("bot", receipt.intent_key, 3 * STEP)
    if request is None:
        raise RuntimeError("test order was not prepared")
    fake = FakeExchange("fake-account")
    try:
        asyncio.run(fake.submit(request["payload"]))
    except TimeoutError:
        pass
    print(f"HANDED_OFF:{len(fake.calls)}", flush=True)
    j.record_halts({"hard_loss"})
    os._exit(73)  # No finally/close; SQLite and the account lock see process death.


if __name__ == "__main__":
    main()
