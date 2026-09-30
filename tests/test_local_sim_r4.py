"""R4 artifact binding, real local execution, and retained failure evidence."""

import asyncio
from contextlib import closing
from dataclasses import replace
from decimal import Decimal, localcontext
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from catos import account_lock, ipc, local_sim_r4 as r4, research
from catos.data_io import load_candles_csv
from catos.research_catalog import DATA_PATH, DEFAULT_REQUEST, load_registered_strategy, provenance, validate_request
from catos.worker_host import WorkerHost
from test_ipc import account, bar, config

D = Decimal


class R4Tests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        self.lock_patch.start()
        self.addCleanup(self.lock_patch.stop)

    async def run_fast(self, **kwargs):
        # Accelerated fixtures test mechanics only; the CLI smoke remains 8 sec.
        with patch.dict(r4.PROFILES, {"smoke": (8, 0)}):
            return await r4.run("smoke", output_root=self.root / "runs", **kwargs)

    def events(self, directory):
        return [json.loads(line) for line in (directory / "events.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_exact_artifact_and_checkpoint_binding_keep_legacy_wire(self):
        legacy = config()
        self.assertNotIn("strategy_artifact", legacy.to_wire())
        bound = replace(legacy, strategy_artifact="sma-parameters-v1")
        self.assertEqual(ipc.WorkerConfig.from_wire(bound.to_wire()), bound)
        for unsupported in (None, "other", "../strategy.py", {"id": "sma-trend"}):
            wire = {**bound.to_wire(), "strategy_artifact": unsupported}
            with self.assertRaises(ipc.ProtocolError):
                ipc.WorkerConfig.from_wire(wire)
        with self.assertRaisesRegex(ipc.ProtocolError, "artifact/config mismatch"):
            ipc.Checkpoint.from_wire(ipc.Checkpoint(legacy).to_wire(), bound)

    async def test_registered_worker_restores_without_losing_commit_ack(self):
        bound = replace(config(), strategy_artifact="sma-parameters-v1")
        async with WorkerHost("r4", bound, require_commit_ack=True) as host:
            for index, price in enumerate(("100", "101", "103")):
                result = await host.process_bar(bar(index, price), None if index < 2 else account(index))
                self.assertEqual(host.checkpoint.event_seq, index)
                await host.acknowledge(index + 1)
            self.assertEqual(result.target_position, D("2"))
            saved = host.checkpoint
        self.assertIsNotNone(host.process.returncode)
        async with WorkerHost("r4", bound, checkpoint=saved) as resumed:
            self.assertEqual((await resumed.process_bar(bar(3, "102"), account(3))).target_position, D("0"))

    async def test_real_smoke_matches_core_trades_and_journal_without_no_change_dispatch(self):
        directory, status = await self.run_fast()
        self.assertEqual(status["state"], "complete", status)
        self.assertEqual((status["bars"], status["warmup_bars"], status["fills"], status["anomalies"]), (8, 2, 4, 0))
        self.assertTrue(status["worker_closed"])
        events = self.events(directory)
        warmups = [row for row in events if row["kind"] == "warmup"]
        signals = [row for row in events if row["kind"] == "signal"]
        fills = [row for row in events if row["kind"] == "fill"]
        bases = [row for row in events if row["kind"] == "day_basis"]
        self.assertEqual([row["target"] for row in warmups], [None, None])
        self.assertEqual([row["target"] for row in signals], ["2", "0", "0", "0", "2", "2", "2", "0"])
        self.assertEqual(len(bases), 2)
        self.assertEqual(bases[1]["synthetic_time_ms"], bases[1]["basis"]["evidence"]["trading_day_start_ms"])
        _, core_config, _, _ = validate_request(DEFAULT_REQUEST)
        candles = load_candles_csv(DATA_PATH, config=core_config)
        strategy = load_registered_strategy(provenance())
        expected = research.backtest(strategy=lambda: strategy(2, D("2")), candles=candles[:11], config=core_config, warmup_bars=2)
        self.assertEqual([(row["fill"]["quantity"], row["fill"]["price"], row["fill"]["fee"]) for row in fills],
                         [(str(trade.quantity.copy_abs()), str(trade.price), str(trade.fee)) for trade in expected.trades])
        with closing(sqlite3.connect(directory / "state.sqlite3")) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("SELECT count(*) FROM inputs WHERE state='COMMITTED'").fetchone()[0], 10)
            self.assertEqual(db.execute("SELECT count(*) FROM execution_fills").fetchone()[0], 4)
            self.assertEqual(db.execute("SELECT count(*) FROM reservations").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM execution_orders WHERE settled=0").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT position FROM ownership").fetchone()[0], "0")
            self.assertEqual(db.execute("SELECT count(*) FROM intents WHERE disposition='NO_CHANGE'").fetchone()[0], 4)
            for (payload,) in db.execute("SELECT payload_json FROM execution_orders"):
                value = json.loads(payload)
                self.assertEqual((value["tag"], value["tdMode"], value["posSide"]), (r4.TAG, "cross", "net"))
            self.assertEqual(db.execute("SELECT DISTINCT typeof(quantity),typeof(price),typeof(fee) FROM execution_fills").fetchall(), [("text", "text", "text")])
        last = next(row for row in events if row["kind"] == "final_account")
        self.assertEqual(last["account"]["fees"], "0.00404010")
        self.assertEqual(last["account"]["equity"], "999.91375990")

    def test_projection_keeps_exact_fee_sign_and_decimal_context(self):
        _, core_config, _, _ = validate_request(DEFAULT_REQUEST)
        rows = [dict(quantity="2", order_quantity="2", price="100.01", fee="0.0001"),
                dict(quantity="2", order_quantity="-2", price="102.03", fee="-0.00001")]
        with localcontext() as context:
            context.prec = 2
            view = r4.project_account(rows, core_config, 1000, D("102.03"))
            self.assertEqual(context.prec, 2)
        self.assertEqual((view.position, view.average_entry, view.fees, view.balance),
                         (D("0"), D("0"), D("0.00009"), D("1000.04031")))

    async def test_source_drift_preserves_failed_db_and_stops_before_first_signal(self):
        with patch.object(r4, "check_health", side_effect=RuntimeError("source_changed_during_local_sim")):
            directory, status = await self.run_fast()
        self.assertEqual((status["state"], status["bars"], status["anomalies"]), ("failed", 0, 1))
        self.assertTrue((directory / "state.sqlite3").exists())
        self.assertEqual(self.events(directory)[-1]["kind"], "anomaly")

    async def test_operator_stop_does_not_claim_success_or_delete_evidence(self):
        with patch.object(r4, "check_health", side_effect=r4.StopRequested("operator_stop_requested")):
            directory, status = await self.run_fast()
        self.assertEqual((status["state"], status["bars"], status["anomalies"]), ("stopped", 0, 0))
        self.assertTrue((directory / "state.sqlite3").exists())
        self.assertEqual(self.events(directory)[-1]["kind"], "stop")

    async def test_missing_fake_script_keeps_unknown_and_reservation_without_resubmit(self):
        with patch.object(r4.FakeExchange, "enqueue", return_value=None):
            directory, status = await self.run_fast()
        self.assertEqual((status["state"], status["fills"], status["anomalies"]), ("failed", 0, 1))
        with closing(sqlite3.connect(directory / "state.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT state,settled FROM execution_orders").fetchall(), [("UNKNOWN", 0)])
            self.assertEqual(db.execute("SELECT count(*) FROM reservations").fetchone()[0], 1)

    async def test_all_32_bar_mechanics_without_claiming_eight_wall_hours(self):
        with patch.dict(r4.PROFILES, {"eight-hour": (32, 0)}):
            directory, status = await r4.run("eight-hour", output_root=self.root / "runs")
        self.assertEqual((status["state"], status["bars"], status["anomalies"]), ("complete", 32, 0), status)
        with closing(sqlite3.connect(directory / "state.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM inputs WHERE state='COMMITTED'").fetchone()[0], 34)
            self.assertEqual(db.execute("SELECT count(*) FROM execution_orders WHERE settled=0").fetchone()[0], 0)
        self.assertEqual(len([row for row in self.events(directory) if row["kind"] == "signal"]), 32)

    async def test_wait_detects_sleep_gap_and_stop_request(self):
        evidence = r4.Evidence(self.root, "smoke", "test")
        supervisor = SimpleNamespace()
        with patch.object(r4.time, "monotonic", side_effect=[0, 121]), patch.object(r4.time, "time", side_effect=[0, 121]):
            with self.assertRaisesRegex(RuntimeError, "continuity_gap"):
                await r4.wait_slot(200, supervisor, evidence, "unused")
        (self.root / "stop.request").write_text("stop", encoding="utf-8")
        with self.assertRaises(r4.StopRequested):
            await r4.wait_slot(r4.time.monotonic() + 1, supervisor, evidence, "unused")


if __name__ == "__main__":
    unittest.main()
