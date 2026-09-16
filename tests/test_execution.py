"""Local journal lifecycle with synthetic reports, never exchange/network access."""

from dataclasses import replace
from contextlib import closing
from decimal import Decimal, localcontext
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from catos import risk
from catos.fake_exchange import Fill, Report, TAG
from catos.journal import Journal, JournalError, OwnershipError, digest, canonical
from test_ipc import STEP, config
from test_journal import prepare_and_commit, proof, input_for, result_for
from catos.journal import FixtureDecision
from test_risk import snapshot

D = Decimal


def report(key, revision=1, status="LIVE", fills=(), complete=False, cumulative=None):
    return Report(digest(key)[:32], "fake-" + digest(key)[:16], revision, status,
                  sum((fill.quantity for fill in fills), D("0")) if cumulative is None else cumulative,
                  fills, complete)


def position_intent(journal, index, position, target):
    checkpoint = journal.snapshot("bot")["checkpoint"]
    payload = input_for(index)
    payload["account"]["position"] = str(position)
    payload["account"]["average_entry"] = "100" if position else "0"
    journal.prepare("bot", index + 1, payload, (index + 2) * STEP)
    return journal.commit_result("bot", result_for(checkpoint, index, target=target),
                                 FixtureDecision(), (index + 1) * STEP)


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "state.sqlite3"
        self.j = Journal(self.path, "fake-account", D("100"), risk.Limits(), True)
        self.addCleanup(lambda: self.j.close() if self.j else None)
        self.j.register("bot", config())
        self.reconcile()
        self.observe()
        prepare_and_commit(self.j, 0)
        prepare_and_commit(self.j, 1)
        self.receipt = prepare_and_commit(self.j, 2, target=D("2"))
        self.key = self.receipt.intent_key

    def observe(self, **changes):
        previous = self.j.risk_state()
        s = snapshot(previous.seq + 1, 3 * STEP, valid_until_ms=10 * STEP, **changes)
        self.j.save_risk(risk.observe(previous, s))

    def reconcile(self, **changes):
        state = self.j.snapshot("bot")
        return self.j.reconcile("bot", proof(state["revision"], **changes))

    def submit(self):
        return self.j.execution.prepare("bot", self.key, 3 * STEP)

    def test_submitting_payload_has_fixed_tag_and_permanent_id(self):
        request = self.submit()
        payload = request["payload"]
        self.assertEqual((payload["tag"], payload["tdMode"], payload["posSide"], payload["ordType"]), (TAG, "cross", "net", "market"))
        self.assertFalse(payload["reduceOnly"])
        self.assertEqual(payload["sz"], "2")
        self.assertEqual(len(payload["clOrdId"]), 32)
        self.assertEqual(self.j.execution.order(self.key)["state"], "SUBMITTING")
        self.assertIsNone(self.submit())

    def test_ack_is_not_fill_and_second_same_target_is_rejected(self):
        self.submit()
        self.j.execution.apply(self.key, report(self.key))
        self.assertEqual(self.j.total_reserved(), D("2"))
        self.reconcile(ordinary_open=1)
        again = prepare_and_commit(self.j, 3, target=D("2"))
        self.assertEqual(again.reason, "order_pending")

    def test_unknown_and_not_found_never_release_or_resend(self):
        self.submit()
        self.j.execution.uncertain(self.key)
        missing = Report(digest(self.key)[:32], None, 1, "NOT_FOUND")
        self.j.execution.apply(self.key, missing)
        self.assertEqual(self.j.execution.order(self.key)["state"], "UNKNOWN")
        self.assertEqual(self.j.total_reserved(), D("2"))
        self.assertIsNone(self.submit())
        with self.assertRaises(OwnershipError):
            self.reconcile()

    def test_partial_fill_duplicate_rest_ws_and_final_release(self):
        self.submit()
        first = Fill("trade1", D("1"), D("101"), D(".01"))
        partial = report(self.key, status="PARTIAL", fills=(first,))
        self.j.execution.apply(self.key, partial)
        self.j.execution.apply(self.key, partial)
        self.j.execution.apply(self.key, replace(partial, revision=2))
        self.assertEqual(self.j.snapshot("bot")["owner"]["position"], "1")
        self.assertEqual(self.j.total_reserved(), D("2"))
        self.assertEqual(self.j.connection.execute("SELECT quantity FROM risk_orders").fetchone()[0], "1")
        second = Fill("trade2", D("1"), D("102"), D(".02"))
        with localcontext() as ctx:
            ctx.prec = 2
            self.j.execution.apply(self.key, report(self.key, 3, "FILLED", (first, second), True))
        self.assertEqual(self.j.snapshot("bot")["owner"]["position"], "2")
        self.assertEqual(self.j.connection.execute("SELECT count(*) FROM execution_fills").fetchone()[0], 2)
        self.assertEqual(self.j.total_reserved(), 0)
        self.assertEqual(self.j.snapshot("bot")["health"], "RECONCILING")
        self.reconcile(position=D("2"), attributed_bot_id="bot")

    def test_conflicting_fill_rolls_back_position_and_amount(self):
        self.submit()
        first = Fill("trade1", D("1"), D("101"))
        self.j.execution.apply(self.key, report(self.key, status="PARTIAL", fills=(first,)))
        with self.assertRaisesRegex(JournalError, "conflicting content"):
            self.j.execution.apply(self.key, report(self.key, 2, "PARTIAL", (replace(first, price=D("102")),)))
        self.assertEqual(self.j.snapshot("bot")["owner"]["position"], "1")
        self.assertEqual(self.j.total_reserved(), D("2"))

    def test_cancel_ack_does_not_end_order_and_fill_can_race_cancel(self):
        self.submit()
        self.j.execution.apply(self.key, report(self.key))
        self.assertIsNotNone(self.j.execution.start_cancel(self.key))
        self.j.execution.apply(self.key, report(self.key, 2))
        self.assertIsNone(self.j.execution.start_cancel(self.key))
        self.assertEqual(self.j.total_reserved(), D("2"))
        fill = Fill("race", D("1"), D("100"))
        self.j.execution.apply(self.key, report(self.key, 3, "CANCELED", (fill,), True))
        self.assertEqual(self.j.snapshot("bot")["owner"]["position"], "1")
        self.assertEqual(self.j.total_reserved(), 0)

    def test_terminal_incomplete_evidence_keeps_obligation(self):
        self.submit()
        self.j.execution.apply(self.key, report(self.key, status="CANCELED", cumulative=D("1")))
        self.assertEqual(self.j.total_reserved(), D("2"))
        with self.assertRaises(OwnershipError):
            self.reconcile()
        with self.assertRaisesRegex(JournalError, "missing trades"):
                self.j.execution.apply(self.key, report(self.key, 2, "CANCELED", complete=True, cumulative=D("1")))

    def test_late_fill_after_done_reopens_original_flatten_operation(self):
        self.submit()
        self.j.execution.apply(self.key, report(self.key, status="CANCELED", complete=True))
        self.reconcile()
        self.observe(equity=D("800"))
        op = self.j.risk_state().flatten_id
        self.j.execution.flatten("bot", 3 * STEP, 4 * STEP)
        self.j.flatten_progress("bot", "DONE", 3 * STEP)
        self.j.execution.apply(self.key, report(self.key, 2, "CANCELED", (Fill("late", D("1"), D("100")),), True))
        self.assertEqual((self.j.risk_state().phase, self.j.risk_state().flatten_id), ("WORKING", op))
        self.assertEqual(self.j.snapshot("bot")["owner"]["position"], "1")

    def test_fixed_id_collision_is_rejected_before_handoff(self):
        self.submit()
        bot = self.j._bot("bot")
        with patch("catos.execution.digest", return_value=digest(self.key)):
            with self.assertRaisesRegex(JournalError, "collision"):
                with self.j._transaction():
                    self.j.execution._insert("different-key", bot, D("1"), False, 4 * STEP, 0, D("1"))

    def test_schema_two_upgrade_keeps_held_intent_and_disallows_fixture_execution(self):
        self.j.close()
        self.j = None
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("DROP TABLE execution_fills")
            db.execute("DROP TABLE execution_orders")
            db.execute("DROP TABLE execution_mode")
            db.execute("PRAGMA user_version=2")
            db.commit()
        self.j = Journal(self.path, "fake-account", D("100"), risk.Limits(), True)
        self.assertEqual(self.j.snapshot("bot")["checkpoint"].event_seq, 3)
        self.assertEqual(self.j.total_reserved(), D("2"))
        self.assertIsNone(self.submit())  # Restart invalidates the old unsent epoch.
        self.assertEqual(self.j.execution.order(self.key)["state"], "ABORTED")

    def test_normal_strategy_close_uses_same_reduce_only_builder(self):
        self.submit()
        self.j.execution.apply(self.key, report(self.key, status="FILLED", fills=(Fill("entry", D("2"), D("100")),), complete=True))
        self.reconcile(position=D("2"), attributed_bot_id="bot")
        self.observe(position=D("2"))
        cp = self.j.snapshot("bot")["checkpoint"]
        payload = input_for(3)
        payload["account"]["position"] = "2"
        payload["account"]["average_entry"] = "100"
        self.j.prepare("bot", 4, payload, 5 * STEP)
        receipt = self.j.commit_result("bot", result_for(cp, 3, target=D("0")), FixtureDecision(), 4 * STEP)
        request = self.j.execution.prepare("bot", receipt.intent_key, 4 * STEP)
        self.assertEqual((request["payload"]["tag"], request["payload"]["side"], request["payload"]["reduceOnly"]), (TAG, "sell", True))

    def test_pending_cancel_does_not_block_verified_reduction(self):
        self.submit()
        partial = report(self.key, status="PARTIAL", fills=(Fill("entry", D("1"), D("100")),))
        self.j.execution.apply(self.key, partial)
        self.j.execution.start_cancel(self.key)
        self.j.execution.apply(self.key, replace(partial, revision=2))
        self.reconcile(position=D("1"), attributed_bot_id="bot", ordinary_open=1)
        self.observe(position=D("1"), equity=D("800"))
        request = self.j.execution.flatten("bot", 3 * STEP, 4 * STEP)
        self.assertEqual(request["payload"]["sz"], "1")
        self.assertTrue(request["payload"]["reduceOnly"])

    def test_ordinary_reduction_does_not_wait_for_same_direction_entry(self):
        for position in (D("1"), D("-1")):
            for cancel_pending in (False, True):
                with self.subTest(position=position, cancel_pending=cancel_pending):
                    path = self.path.with_name(f"partial-{position}-{cancel_pending}.sqlite3")
                    with closing(Journal(path, "fake-account", D("100"), risk.Limits(), True)) as j:
                        j.register("bot", config())
                        j.reconcile("bot", proof(0))
                        j.save_risk(risk.observe(j.risk_state(), snapshot(1, 3 * STEP, valid_until_ms=10 * STEP)))
                        prepare_and_commit(j, 0)
                        prepare_and_commit(j, 1)
                        entry = position_intent(j, 2, D("0"), 2 * position)
                        request = j.execution.prepare("bot", entry.intent_key, 3 * STEP)
                        self.assertFalse(request["payload"]["reduceOnly"])
                        partial = report(entry.intent_key, status="PARTIAL",
                                         fills=(Fill("entry", D("1"), D("100")),))
                        j.execution.apply(entry.intent_key, partial)
                        if cancel_pending:
                            j.execution.start_cancel(entry.intent_key)
                            j.execution.apply(entry.intent_key, replace(partial, revision=2))
                        j.reconcile("bot", proof(j.snapshot("bot")["revision"], position=position,
                                                attributed_bot_id="bot", ordinary_open=1))
                        j.save_risk(risk.observe(j.risk_state(), snapshot(2, 3 * STEP,
                            valid_until_ms=10 * STEP, position=position)))
                        duplicate = position_intent(j, 3, position, 2 * position)
                        self.assertEqual(duplicate.reason, "order_pending")
                        reduction = position_intent(j, 4, position, D("0"))
                        self.assertEqual((reduction.disposition, reduction.reason, reduction.reservation),
                                         ("RESERVED_SIMULATION", "legal_reduction", D("0")))
                        original = j.execution.order(entry.intent_key)
                        request = j.execution.prepare("bot", reduction.intent_key, 5 * STEP)
                        payload = request["payload"]
                        self.assertEqual((payload["side"], payload["reduceOnly"], payload["sz"]),
                                         ("sell" if position > 0 else "buy", True, "1"))
                        self.assertEqual(j.execution.order(entry.intent_key), original)
                        self.assertEqual(original["cancel_pending"], int(cancel_pending))
                        self.assertFalse(original["settled"])
                        self.assertEqual(j.total_reserved(), D("2"))
                        held = j.connection.execute("SELECT quantity FROM risk_orders WHERE intent_key=?",
                                                    (entry.intent_key,)).fetchone()
                        self.assertEqual(D(held[0]), position)
                        self.assertEqual(len(j.execution.unresolved()), 2)

    def test_ordinary_reduction_keeps_entry_reservation_under_soft_loss(self):
        self.submit()
        self.j.execution.apply(self.key, report(self.key, status="PARTIAL",
            fills=(Fill("entry", D("1"), D("100")),)))
        self.reconcile(position=D("1"), attributed_bot_id="bot", ordinary_open=1)
        self.observe(position=D("1"), equity=D("900"))
        before = self.j.risk_state()
        self.assertEqual(before.mode, "NO_INCREASE")
        self.assertEqual(before.reasons, {"soft_loss"})
        original = self.j.execution.order(self.key)
        reduction = position_intent(self.j, 3, D("1"), D("0"))
        self.assertEqual((reduction.disposition, reduction.reason, reduction.reservation),
                         ("RESERVED_SIMULATION", "legal_reduction", D("0")))
        request = self.j.execution.prepare("bot", reduction.intent_key, 4 * STEP)
        payload = request["payload"]
        self.assertEqual((payload["tag"], payload["side"], payload["reduceOnly"], payload["sz"]),
                         (TAG, "sell", True, "1"))
        self.assertEqual(self.j.risk_state(), before)
        self.assertEqual(self.j.execution.order(self.key), original)
        self.assertFalse(original["settled"])
        self.assertEqual(self.j.total_reserved(), D("2"))
        held = self.j.connection.execute("SELECT quantity,eligible FROM risk_orders WHERE intent_key=?",
                                         (self.key,)).fetchone()
        self.assertEqual((D(held["quantity"]), held["eligible"]), (D("1"), 0))
        self.assertEqual(len(self.j.execution.unresolved()), 2)

    def test_held_ordinary_reduction_blocks_second_reduction(self):
        self.submit()
        self.j.execution.apply(self.key, report(self.key, status="FILLED",
            fills=(Fill("entry", D("2"), D("100")),), complete=True))
        self.reconcile(position=D("2"), attributed_bot_id="bot")
        self.observe(position=D("2"))
        first = position_intent(self.j, 3, D("2"), D("0"))
        second = position_intent(self.j, 4, D("2"), D("0"))
        self.assertEqual(first.reason, "legal_reduction")
        self.assertEqual((second.disposition, second.reason), ("REJECTED", "reduction_conflict"))
        self.assertFalse(self.j.execution.unresolved())
        self.assertEqual(self.j.connection.execute("SELECT count(*) FROM reservations").fetchone()[0], 1)
        self.assertEqual(self.j.connection.execute("SELECT intent_key FROM risk_orders").fetchone()[0], first.intent_key)

    def test_ordinary_reduction_keeps_unknown_position_gate_at_both_stages(self):
        self.submit()
        self.j.execution.apply(self.key, report(self.key, status="PARTIAL",
            fills=(Fill("entry", D("1"), D("100")),)))
        self.reconcile(position=D("1"), attributed_bot_id="bot", ordinary_open=1)
        self.observe(position=D("1"))
        reduction = position_intent(self.j, 3, D("1"), D("0"))
        self.assertEqual(reduction.reason, "legal_reduction")
        self.j.execution.uncertain(self.key)
        self.reconcile(position=D("1"), attributed_bot_id="bot", unknown_count=1)
        self.observe(position=D("1"))
        self.assertIsNone(self.j.execution.prepare("bot", reduction.intent_key, 4 * STEP))
        self.assertEqual(self.j.execution.order(reduction.intent_key)["state"], "ABORTED")
        rejected = position_intent(self.j, 4, D("1"), D("0"))
        self.assertEqual((rejected.disposition, rejected.reason), ("REJECTED", "position_not_verified"))
        self.assertEqual(self.j.execution.order(self.key)["state"], "UNKNOWN")
        self.assertEqual(self.j.total_reserved(), D("2"))

    def test_child_without_intent_blocks_submission_and_later_reduction_intent(self):
        self.submit()
        self.j.execution.apply(self.key, report(self.key, status="FILLED",
            fills=(Fill("entry", D("2"), D("100")),), complete=True))
        self.reconcile(position=D("2"), attributed_bot_id="bot")
        self.observe(position=D("2"))
        reduction = position_intent(self.j, 3, D("2"), D("0"))
        self.assertEqual(reduction.reason, "legal_reduction")
        with self.j._transaction():
            child = self.j.execution._insert("synthetic-flatten-child", self.j._bot("bot"),
                D("-1"), True, 10 * STEP, self.j.risk_state().epoch, D("0"), state="LIVE")
        child_key = child["order_key"]
        self.reconcile(position=D("2"), attributed_bot_id="bot", ordinary_open=1)
        self.observe(position=D("2"))
        self.assertIsNone(self.j.execution.order(child_key)["intent_key"])
        self.assertEqual(self.j.connection.execute("SELECT count(*) FROM risk_orders").fetchone()[0], 1)
        self.assertIsNone(self.j.execution.prepare("bot", reduction.intent_key, 4 * STEP))
        self.assertEqual(self.j.execution.order(reduction.intent_key)["state"], "ABORTED")
        self.assertEqual(self.j.connection.execute("SELECT count(*) FROM risk_orders").fetchone()[0], 0)
        rejected = position_intent(self.j, 4, D("2"), D("0"))
        self.assertEqual((rejected.disposition, rejected.reason), ("REJECTED", "reduction_conflict"))
        self.assertEqual([row["order_key"] for row in self.j.execution.unresolved()], [child_key])

    def test_reduction_conflict_reads_all_unsettled_states_and_order_directions(self):
        for state in ("LIVE", "PARTIAL", "SUBMITTING", "UNKNOWN", "CANCELED", "FILLED"):
            for position in (D("2"), D("-2")):
                for reduce_only, quantity, expected in ((True, position, True),
                                                        (False, -position, True), (False, position, False)):
                    with self.subTest(state=state, position=position, reduce_only=reduce_only, quantity=quantity):
                        key = f"synthetic-{state}-{position}-{reduce_only}-{quantity}"
                        with self.j._transaction():
                            self.j.execution._insert(key, self.j._bot("bot"), quantity, reduce_only,
                                10 * STEP, self.j.risk_state().epoch, D("0"), state=state)
                        before = self.j.execution.order(key)
                        self.assertEqual(self.j.execution.reduction_conflict(position), expected)
                        self.assertEqual(self.j.execution.order(key), before)
                        with self.j._transaction():
                            self.j.connection.execute("UPDATE execution_orders SET settled=1 WHERE order_key=?", (key,))
                        self.assertFalse(self.j.execution.reduction_conflict(position))

    def test_restart_submitting_becomes_unknown_without_new_id(self):
        self.submit()
        self.j.record_halts({"hard_loss"})
        op = self.j.risk_state().flatten_id
        self.j.close()
        self.j = Journal(self.path, "fake-account", D("100"), risk.Limits(), True)
        self.assertEqual(self.j.execution.order(self.key)["state"], "UNKNOWN")
        self.assertEqual(self.j.risk_state().flatten_id, op)
        self.assertIsNone(self.submit())
        self.j.execution.apply(self.key, report(self.key, status="REJECTED", complete=True))
        self.assertEqual(self.j.total_reserved(), 0)
        self.assertEqual(self.j.risk_state().mode, "FLAT")

    def test_expired_stale_epoch_or_new_mark_abort_unsent(self):
        self.observe(mark=D("1000000"))
        self.assertIsNone(self.submit())
        self.assertEqual(self.j.execution.order(self.key)["state"], "ABORTED")
        self.assertEqual(self.j.total_reserved(), 0)

    def test_atomic_submission_failure_never_creates_partial_mapping(self):
        with patch.object(self.j, "_commit", side_effect=sqlite3.OperationalError("synthetic failure")):
            with self.assertRaises(sqlite3.OperationalError):
                self.submit()
        self.assertEqual(self.j.connection.execute("SELECT count(*) FROM execution_orders").fetchone()[0], 0)
        self.assertEqual(self.j.total_reserved(), D("2"))

    def test_position_discrepancy_is_not_adopted_and_closes_gate(self):
        with self.assertRaises(OwnershipError):
            self.reconcile(position=D("3"), attributed_bot_id="bot")
        self.assertEqual(self.j.snapshot("bot")["owner"]["position"], "0")
        self.assertEqual(self.j.snapshot("bot")["health"], "RECONCILING")

    def test_flatten_has_same_builder_and_completes_only_after_fresh_proof(self):
        self.submit()
        fill = Fill("entry", D("2"), D("100"))
        self.j.execution.apply(self.key, report(self.key, status="FILLED", fills=(fill,), complete=True))
        self.reconcile(position=D("2"), attributed_bot_id="bot")
        self.observe(position=D("2"), equity=D("800"))
        op = self.j.risk_state().flatten_id
        request = self.j.execution.flatten("bot", 3 * STEP, 4 * STEP)
        self.assertEqual((request["payload"]["tag"], request["payload"]["reduceOnly"], request["payload"]["sz"]), (TAG, True, "2"))
        self.assertIsNone(self.j.execution.flatten("bot", 3 * STEP, 4 * STEP))
        key = request["order_key"]
        self.j.execution.apply(key, report(key, status="FILLED", fills=(Fill("exit", D("2"), D("99")),), complete=True))
        self.reconcile()
        self.observe(equity=D("800"))
        self.j.execution.flatten("bot", 3 * STEP, 4 * STEP)
        self.assertEqual(self.j.flatten_progress("bot", "DONE", 3 * STEP).phase, "DONE")
        self.assertEqual(self.j.risk_state().flatten_id, op)
        self.j.release("bot")

    def test_unknown_reduction_blocks_second_flatten_child(self):
        self.setup_position()
        request = self.j.execution.flatten("bot", 3 * STEP, 4 * STEP)
        self.j.execution.uncertain(request["order_key"])
        self.assertIsNone(self.j.execution.flatten("bot", 3 * STEP, 4 * STEP))
        self.assertEqual(len(self.j.execution.unresolved()), 1)

    def setup_position(self):
        self.submit()
        self.j.execution.apply(self.key, report(self.key, status="FILLED", fills=(Fill("entry", D("2"), D("100")),), complete=True))
        self.reconcile(position=D("2"), attributed_bot_id="bot")
        self.observe(position=D("2"), equity=D("800"))


if __name__ == "__main__":
    unittest.main()
