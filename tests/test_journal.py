"""Temporary SQLite and synthetic ownership evidence only."""

from dataclasses import replace
from contextlib import closing
from decimal import Decimal, localcontext
from pathlib import Path
import sqlite3
import tempfile
import unittest

from catos import ipc
from catos.journal import FixtureDecision, Journal, JournalError, OwnershipError, Reconciliation, ReplayConflict
from test_ipc import STEP, account, bar, config

D = Decimal


def proof(revision, **changes):
    return replace(Reconciliation(revision, "synthetic-evidence", D("0"), 0, 0, 0, True), **changes)


def input_for(index, price="100"):
    return dict(bar=ipc.bar_to_wire(bar(index, price)), account=ipc.account_to_wire(None if index < 2 else account(index)))


def result_for(checkpoint, index, price="100", target=None):
    cp = ipc.Checkpoint(checkpoint.config, index + 1, index * STEP, (*checkpoint.closes, D(price))[-2:])
    return ipc.EventResult(index + 1, target, cp, len(cp.closes) == 2)


def prepare_and_commit(journal, index, *, price="100", target=None, fixture=None, now_ms=None):
    cp = journal.snapshot("bot")["checkpoint"]
    journal.prepare("bot", index + 1, input_for(index, price), (index + 2) * STEP)
    return journal.commit_result("bot", result_for(cp, index, price, target), fixture or FixtureDecision(),
                                  (index + 1) * STEP if now_ms is None else now_ms)


class JournalTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state.sqlite3"
        self.journal = Journal(self.path, "fake-account", D("100"))
        self.addCleanup(lambda: self.journal.close() if self.journal else None)
        self.journal.register("bot", config())
        self.journal.reconcile("bot", proof(0))

    def warmup(self):
        prepare_and_commit(self.journal, 0)
        prepare_and_commit(self.journal, 1)

    def reopen(self):
        self.journal.close()
        self.journal = Journal(self.path, "fake-account", D("100"))
        self.journal.register("bot", config())

    def test_wal_full_and_financial_columns_are_decimal_text(self):
        self.assertEqual(self.journal.connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.journal.connection.execute("PRAGMA synchronous").fetchone()[0], 2)
        self.warmup()
        amount = D("80.123456789012345678")
        with localcontext() as context:
            context.prec = 2
            receipt = prepare_and_commit(self.journal, 2, target=D("2"), fixture=FixtureDecision(True, amount))
            self.assertEqual(receipt.reservation, amount)
        self.assertEqual(tuple(self.journal.connection.execute("SELECT amount,typeof(amount) FROM reservations").fetchone()), (str(amount), "text"))
        self.assertEqual(self.journal.total_reserved(), amount)
        self.assertEqual(self.journal.connection.execute("SELECT state FROM outbox").fetchone()[0], "HELD_SIMULATION")

    def test_default_rejection_is_durable_without_outbox(self):
        self.warmup()
        receipt = prepare_and_commit(self.journal, 2, target=D("2"))
        self.assertEqual((receipt.disposition, receipt.reason), ("REJECTED", "risk_engine_not_installed"))
        self.assertEqual(self.journal.connection.execute("SELECT count(*) FROM outbox").fetchone()[0], 0)
        self.assertEqual(self.journal.snapshot("bot")["checkpoint"].event_seq, 3)

    def test_exact_replay_returns_same_receipt_and_reserves_once(self):
        self.warmup()
        before = self.journal.snapshot("bot")["checkpoint"]
        first = prepare_and_commit(self.journal, 2, target=D("2"), fixture=FixtureDecision(True, D("80")))
        replay = self.journal.prepare("bot", 3, input_for(2), 4 * STEP)
        self.assertEqual(replace(replay, replayed=False), first)
        repeated = self.journal.commit_result("bot", result_for(before, 2, target=D("2")), FixtureDecision(True, D("99")), 99 * STEP)
        self.assertEqual(replace(repeated, replayed=False), first)
        self.assertNotIn("generation", first.intent_key)
        self.assertEqual(self.journal.total_reserved(), D("80"))
        self.assertEqual(self.journal.connection.execute("SELECT count(*) FROM intents").fetchone()[0], 1)

    def test_changed_input_isolates_bot_durably(self):
        self.journal.prepare("bot", 1, input_for(0), 2 * STEP)
        with self.assertRaises(ReplayConflict):
            self.journal.prepare("bot", 1, input_for(0, "101"), 2 * STEP)
        self.reopen()
        self.assertTrue(self.journal.snapshot("bot")["isolated"])

    def test_changed_result_does_not_overwrite_prior_intent(self):
        self.warmup()
        before = self.journal.snapshot("bot")["checkpoint"]
        prepare_and_commit(self.journal, 2, target=D("2"), fixture=FixtureDecision(True, D("80")))
        with self.assertRaises(ReplayConflict):
            self.journal.commit_result("bot", result_for(before, 2, target=D("0")), FixtureDecision(), 3 * STEP)
        self.assertEqual(self.journal.connection.execute("SELECT target FROM intents").fetchone()[0], "2")
        self.assertEqual(self.journal.total_reserved(), D("80"))

    def test_budget_includes_reservations_and_expired_intents_do_not_reserve(self):
        self.warmup()
        prepare_and_commit(self.journal, 2, target=D("2"), fixture=FixtureDecision(True, D("80")))
        refused = prepare_and_commit(self.journal, 3, target=D("2"), fixture=FixtureDecision(True, D("80")))
        self.assertEqual(refused.reason, "fixture_budget_exceeded")
        expired = prepare_and_commit(self.journal, 4, target=D("2"), fixture=FixtureDecision(True, D("10")), now_ms=6 * STEP)
        self.assertEqual(expired.disposition, "EXPIRED")
        self.assertEqual(self.journal.total_reserved(), D("80"))

    def test_warmup_and_no_change_never_create_outbox(self):
        self.warmup()
        self.assertEqual(self.journal.connection.execute("SELECT count(*) FROM intents").fetchone()[0], 0)
        receipt = prepare_and_commit(self.journal, 2, target=D("0"), fixture=FixtureDecision(True, D("80")))
        self.assertEqual(receipt.disposition, "NO_CHANGE")
        self.assertEqual(self.journal.total_reserved(), D("0"))

    def test_reopen_requires_reconciliation_and_preserves_latches_and_ownership(self):
        self.journal.record_halts({"hard_loss", "manual_kill"})
        self.reopen()
        state = self.journal.snapshot("bot")
        self.assertEqual(state["health"], "RECONCILING")
        self.assertEqual(set(state["halt_reasons"]), {"hard_loss", "manual_kill"})
        self.assertEqual(state["epoch"], 2)
        self.assertEqual(state["owner"]["bot_id"], "bot")
        self.assertIsNone(state["owner"]["reconciled_revision"])
        self.journal.reconcile("bot", proof(state["revision"]))
        self.warmup()
        receipt = prepare_and_commit(self.journal, 2, target=D("2"), fixture=FixtureDecision(True, D("80")))
        self.assertEqual(receipt.reason, "control_gate_closed")

    def test_ownership_cannot_change_bot_or_artifact_while_held(self):
        with self.assertRaises(OwnershipError):
            self.journal.register("other", config())
        with self.assertRaises(OwnershipError):
            self.journal.register("bot", config(3))
        self.journal.release("bot")
        self.journal.register("other", config())
        self.assertEqual(self.journal.snapshot("other")["owner"]["bot_id"], "other")

    def test_release_requires_all_fresh_evidence(self):
        variants = [dict(position=D("1"), attributed_bot_id="bot"), dict(ordinary_open=1),
                    dict(conditional_open=1), dict(unknown_count=1), dict(fills_reconciled=False)]
        for changes in variants:
            self.journal.reconcile("bot", proof(0, **changes))
            with self.subTest(changes=changes), self.assertRaises(OwnershipError):
                self.journal.release("bot")
        self.journal.reconcile("bot", proof(0))
        self.journal.prepare("bot", 1, input_for(0), 2 * STEP)
        with self.assertRaisesRegex(OwnershipError, "stale"):
            self.journal.reconcile("bot", proof(0))
        with self.assertRaises(OwnershipError):
            self.journal.release("bot")
        self.journal.reconcile("bot", proof(1))
        with self.assertRaisesRegex(OwnershipError, "pending"):
            self.journal.release("bot")

    def test_reservation_blocks_release_even_with_flat_snapshot(self):
        self.warmup()
        prepare_and_commit(self.journal, 2, target=D("2"), fixture=FixtureDecision(True, D("80")))
        self.journal.reconcile("bot", proof(self.journal.snapshot("bot")["revision"]))
        with self.assertRaisesRegex(OwnershipError, "reservation"):
            self.journal.release("bot")

    def test_foreign_position_is_not_automatically_attributed(self):
        for identity in (None, "stranger"):
            with self.assertRaisesRegex(OwnershipError, "taken over"):
                self.journal.reconcile("bot", proof(0, position=D("1"), attributed_bot_id=identity))

    def test_invalid_database_identity_budget_and_schema_are_not_rebuilt(self):
        self.journal.close()
        self.journal = None
        for account_id, budget in (("different", D("100")), ("fake-account", D("200"))):
            with self.assertRaises(JournalError):
                Journal(self.path, account_id, budget)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("PRAGMA user_version=99")
        with self.assertRaisesRegex(JournalError, "schema"):
            Journal(self.path, "fake-account", D("100"))
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 99)

    def test_no_result_without_durable_input_and_no_float_fixture(self):
        cp = self.journal.snapshot("bot")["checkpoint"]
        with self.assertRaisesRegex(JournalError, "input must"):
            self.journal.commit_result("bot", result_for(cp, 0), FixtureDecision(), STEP)
        for amount in (1.0, D("NaN"), D("-1")):
            with self.assertRaises(ipc.ProtocolError):
                FixtureDecision(True, amount).validate()


if __name__ == "__main__":
    unittest.main()
