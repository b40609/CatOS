"""Risk verdict, quantity reservation, checkpoint, and latches share E's writer."""

from dataclasses import replace
from contextlib import closing
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from catos import ipc, risk
from catos.journal import FixtureDecision, Journal, JournalError
from test_ipc import STEP, config
from test_journal import input_for, prepare_and_commit, proof, result_for
from test_risk import snapshot
from lot_journal_helpers import drop_empty_lot_schema

D = Decimal


class RiskJournalTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "risk.sqlite3"
        self.journal = Journal(self.path, "fake-account", D("100"), risk.Limits())
        self.addCleanup(lambda: self.journal.close() if self.journal else None)
        self.journal.register("bot", config())
        self.journal.reconcile("bot", proof(0))
        self.observe()
        prepare_and_commit(self.journal, 0)
        prepare_and_commit(self.journal, 1)

    def observe(self, **changes):
        old = self.journal.risk_state()
        s = snapshot(old.seq + 1, 3 * STEP, valid_until_ms=20 * STEP, **changes)
        self.journal.save_risk(risk.observe(old, s))

    def test_atomic_risk_reservation_counts_prior_quantity_and_replay(self):
        first = prepare_and_commit(self.journal, 2, target=D("1000"))
        self.assertEqual((first.disposition, first.reservation), ("RESERVED_SIMULATION", D("1000")))
        self.assertEqual(self.journal.prepare("bot", 3, input_for(2), 4 * STEP).reservation, first.reservation)
        second = prepare_and_commit(self.journal, 3, target=D("1000"))
        self.assertEqual(second.reason, "symbol_exposure_limit")
        self.assertEqual(self.journal.total_reserved(), D("1000"))
        self.assertEqual(tuple(self.journal.connection.execute("SELECT quantity,typeof(quantity),reduce_only FROM risk_orders").fetchone()), ("1000", "text", 0))

    def test_risk_fixture_cannot_override_and_mode_cannot_be_disabled(self):
        with self.assertRaisesRegex(JournalError, "bypass"):
            prepare_and_commit(self.journal, 2, target=D("2"), fixture=FixtureDecision(True, D("1")))
        self.journal.close()
        self.journal = None
        for limits in (None, risk.Limits(D("4"))):
            with self.assertRaisesRegex(JournalError, "mode/limits"):
                Journal(self.path, "fake-account", D("100"), limits)

    def test_commit_failure_rolls_back_risk_quantity_intent_and_checkpoint(self):
        cp = self.journal.snapshot("bot")["checkpoint"]
        self.journal.prepare("bot", 3, input_for(2), 4 * STEP)
        with patch.object(self.journal, "_commit", side_effect=sqlite3.OperationalError("synthetic disk failure")):
            with self.assertRaises(sqlite3.OperationalError):
                self.journal.commit_result("bot", result_for(cp, 2, target=D("2")), FixtureDecision(), 3 * STEP)
        self.assertEqual(self.journal.snapshot("bot")["checkpoint"], cp)
        self.assertEqual(self.journal.connection.execute("SELECT count(*) FROM risk_orders").fetchone()[0], 0)
        self.assertEqual(self.journal.total_reserved(), 0)
        retry = self.journal.commit_result("bot", result_for(cp, 2, target=D("2")), FixtureDecision(), 3 * STEP)
        self.assertEqual(retry.reservation, D("2"))

    def test_halt_invalidates_increase_but_retains_obligation_and_restart(self):
        prepare_and_commit(self.journal, 2, target=D("2"))
        self.observe(equity=D("800"))
        state = self.journal.risk_state()
        self.assertEqual(self.journal.connection.execute("SELECT eligible FROM risk_orders").fetchone()[0], 0)
        self.assertEqual(self.journal.total_reserved(), D("2"))
        self.journal.close()
        self.journal = Journal(self.path, "fake-account", D("100"), risk.Limits())
        restored = self.journal.risk_state()
        self.assertEqual((restored.mode, restored.phase, restored.flatten_id, restored.basis),
                         ("FLAT", "WORKING", state.flatten_id, state.basis))
        self.assertIsNone(restored.snapshot)
        self.assertEqual(restored.health, "RECONCILING")
        self.journal.reconcile("bot", proof(self.journal.snapshot("bot")["revision"]))
        self.assertEqual(prepare_and_commit(self.journal, 3, target=D("2")).reason, "risk_snapshot_stale")

    def test_reduction_under_hard_latch_has_reduce_only_and_no_new_exposure(self):
        self.observe(position=D("10"), equity=D("800"))
        self.journal.reconcile("bot", proof(self.journal.snapshot("bot")["revision"], position=D("10"), attributed_bot_id="bot"))
        cp = self.journal.snapshot("bot")["checkpoint"]
        payload = input_for(2)
        payload["account"]["position"] = "10"
        payload["account"]["average_entry"] = "100"
        self.journal.prepare("bot", 3, payload, 4 * STEP)
        result = self.journal.commit_result("bot", result_for(cp, 2, target=D("0")), FixtureDecision(), 3 * STEP)
        self.assertEqual((result.reason, result.reservation), ("legal_reduction", D("0")))
        self.assertEqual(tuple(self.journal.connection.execute("SELECT quantity,reduce_only FROM risk_orders").fetchone()), ("-10", 1))

    def test_flatten_done_requires_full_fresh_evidence_then_late_fill_reopens_same_id(self):
        self.journal.record_halts({"manual_kill"})
        op = self.journal.risk_state().flatten_id
        self.journal.flatten_progress("bot", "VERIFY", 3 * STEP)
        with self.assertRaises(ipc.ProtocolError):
            self.journal.flatten_progress("bot", "DONE", 3 * STEP)
        revision = self.journal.snapshot("bot")["revision"]
        for changes in (dict(conditional_open=1), dict(unknown_count=1), dict(fills_reconciled=False)):
            self.journal.reconcile("bot", proof(revision, **changes))
            with self.assertRaises(ipc.ProtocolError):
                self.journal.flatten_progress("bot", "DONE", 3 * STEP)
        self.journal.reconcile("bot", proof(revision))
        self.assertEqual(self.journal.flatten_progress("bot", "DONE", 3 * STEP).phase, "DONE")
        self.observe(position=D("1"))
        self.assertEqual((self.journal.risk_state().phase, self.journal.risk_state().flatten_id), ("WORKING", op))

    def test_version_one_migration_keeps_checkpoint_and_latch(self):
        legacy = self.path.parent / "legacy.sqlite3"
        journal = Journal(legacy, "legacy", D("100"))
        journal.register("bot", config())
        journal.reconcile("bot", proof(0))
        prepare_and_commit(journal, 0)
        journal.record_halts({"hard_loss"})
        journal.close()
        with closing(sqlite3.connect(legacy)) as db, db:
            drop_empty_lot_schema(db)
            db.execute("DROP TABLE risk_orders")
            db.execute("DROP TABLE risk_control")
            db.execute("DROP TABLE execution_fills")
            db.execute("DROP TABLE execution_orders")
            db.execute("DROP TABLE execution_mode")
            db.execute("PRAGMA user_version=1")
        journal = Journal(legacy, "legacy", D("100"), risk.Limits())
        self.addCleanup(journal.close)
        self.assertEqual(journal.snapshot("bot")["checkpoint"].event_seq, 1)
        self.assertEqual(journal.risk_state().mode, "FLAT")
        self.assertEqual(journal.connection.execute("PRAGMA user_version").fetchone()[0], 6)

    def test_enabling_risk_refuses_existing_fixture_obligations(self):
        legacy = self.path.parent / "legacy.sqlite3"
        journal = Journal(legacy, "legacy", D("100"))
        journal.register("bot", config())
        journal.reconcile("bot", proof(0))
        prepare_and_commit(journal, 0)
        prepare_and_commit(journal, 1)
        prepare_and_commit(journal, 2, target=D("2"), fixture=FixtureDecision(True, D("1")))
        journal.close()
        with self.assertRaisesRegex(JournalError, "fixture obligations"):
            Journal(legacy, "legacy", D("100"), risk.Limits())


if __name__ == "__main__":
    unittest.main()
