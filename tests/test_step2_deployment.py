"""Step 2: approved research deployment on the local-sim Bot (approvals, checkpoint v2, reversal legs, replay).

Every test uses an isolated approvals file (CATOS_STRATEGY_APPROVALS) with TEST
records and an isolated output directory; nothing touches outputs/ or a network.
"""

import asyncio
from dataclasses import replace
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from catos import (ipc, local_sim_replay, replay_consistency, research, research_catalog, risk,
                   strategy_approvals as approvals, strategy_registry)
from catos.worker_host import WorkerError, WorkerHost

D = Decimal
START = 1_767_225_600_000  # 2026-01-01 00:00 UTC (08:00 Taipei)
STEP = 900_000
CONTRACT = research_catalog.SYNTHETIC_CONTRACT
# Warm-up at 100, a long breakout, a reversal short, a reversal long, a reversal short, an exit.
CLOSES = ("100", "100", "100", "100", "110", "110", "110", "110", "90", "90", "90", "90",
          "95", "100", "120", "120", "80", "80", "80", "80", "85", "86")


def profile(entry=4, exit=2, warmup=None, quantity="1", **changes):
    value = {"schema": "catos.strategy-deployment", "schema_version": 1,
             "strategy_id": "donchian-breakout", "version": "donchian-parameters-v1",
             "parameters": {"entry_bars": entry, "exit_bars": exit}, "quantity": quantity,
             "inst_id": "BTC-USDT-SWAP", "timeframe_ms": STEP, "warmup_bars": entry if warmup is None else warmup,
             "initial_balance": "1000", "fee_rate": "0.0005", "slippage_bps": "2"}
    value.update(changes)
    return value


def bars(closes=CLOSES):
    return tuple(research.Candle(START + i * STEP, D(c), D(c), D(c), D(c)) for i, c in enumerate(closes))


def yes(_text, _word):
    return True


class Isolated(unittest.TestCase):
    def setUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.temp / "approvals.jsonl"
        self.enterContext(patch.dict(os.environ, {approvals.ENV_PATH: str(self.path)}))

    def approve(self, value=None, **kwargs):
        value = profile() if value is None else value
        artifact, _ = approvals.deployment_identity(value)
        return approvals.approve(strategy_id=value["strategy_id"], version=value["version"],
                                 sha256=artifact["sha256"], profile=value, confirm=yes, **kwargs)


class ApprovalRecordTests(Isolated):
    def test_approve_appends_a_hash_chained_canonical_record(self):
        first = self.approve(research_basis="test-basis")
        second = self.approve(profile(entry=6, exit=3))
        records = approvals.read_records()
        self.assertEqual([r["record_id"] for r in records], [first["record_id"], second["record_id"]])
        self.assertEqual(first["prev_sha256"], approvals.GENESIS)
        lines = self.path.read_bytes().split(b"\n")
        self.assertEqual(second["prev_sha256"], approvals._sha256(lines[0] + b"\n"))
        self.assertEqual(approvals.active_approval(first["record_id"]), first)
        self.assertEqual(approvals.find_active(profile())["record_id"], first["record_id"])
        artifact, manifest_sha = approvals.deployment_identity(profile())
        self.assertEqual((first["source_sha256"], first["manifest_sha256"]), (artifact["sha256"], manifest_sha))

    def test_approval_requires_the_full_current_sha256_and_confirmation(self):
        artifact, _ = approvals.deployment_identity(profile())
        for sha, reason in ((artifact["sha256"][:63], "full_sha256_required"),
                            (artifact["sha256"].upper(), "full_sha256_required"),
                            ("0" * 64, "sha256_does_not_match_current_source")):
            with self.subTest(sha=sha), self.assertRaisesRegex(approvals.ApprovalError, reason):
                approvals.approve(strategy_id="donchian-breakout", version="donchian-parameters-v1",
                                  sha256=sha, profile=profile(), confirm=yes)
        with self.assertRaisesRegex(approvals.ApprovalError, "approval_not_confirmed"):
            approvals.approve(strategy_id="donchian-breakout", version="donchian-parameters-v1",
                              sha256=artifact["sha256"], profile=profile(), confirm=lambda t, w: False)
        self.assertFalse(self.path.exists())

    def test_only_bot_eligible_strategies_and_valid_profiles(self):
        cases = (
            (profile(strategy_id="sma-trend", version="sma-parameters-v1"), "strategy_not_bot_eligible"),
            (profile(strategy_id="donchian-ensemble", version="donchian-ensemble-preregistered-v1"),
             "strategy_not_bot_eligible"),
            (profile(entry=4, exit=4), "exit_bars_must_be_below_entry_bars"),
            (profile(entry=600, exit=48), "lookback_above_bot_limit"),
            (profile(warmup=3), "warmup_bars_invalid"),
            (profile(quantity="1.5"), "quantity_out_of_range"),
            (profile(quantity="01"), "quantity_not_canonical"),
            (profile(timeframe_ms=60_000), "timeframe_invalid"),
            (profile(inst_id="BTC-USD-SWAP"), "inst_id_invalid"),
            ({**profile(), "extra": 1}, "exact_fields_required"),
        )
        for value, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(approvals.ApprovalError, reason):
                approvals.validate_profile(value)

    def test_terminal_confirmation_refuses_a_pipe(self):
        with patch.object(approvals.sys, "stdin", io.StringIO("approve\n")):
            with self.assertRaisesRegex(approvals.ApprovalError, "interactive_terminal_required"):
                approvals.terminal_confirm("text", "approve")
        profile_file = self.temp / "profile.json"
        profile_file.write_text(json.dumps(profile()), encoding="utf-8")
        artifact, _ = approvals.deployment_identity(profile())
        with patch.object(approvals.sys, "stdin", io.StringIO("approve\n")), \
                patch("sys.stderr", io.StringIO()):
            code = approvals.cli_main(["approve", "--strategy", "donchian-breakout", "--version",
                                       "donchian-parameters-v1", "--sha256", artifact["sha256"],
                                       "--profile", str(profile_file)])
        self.assertEqual(code, 1)
        self.assertFalse(self.path.exists())

    def test_edited_removed_or_truncated_lines_fail_closed(self):
        first = self.approve()
        self.approve(profile(entry=6, exit=3))
        original = self.path.read_bytes()
        lines = original.split(b"\n")
        tampered = {
            "edited": original.replace(b'"quantity":"1"', b'"quantity":"2"', 1),
            "removed": lines[1] + b"\n",
            "reordered": lines[1] + b"\n" + lines[0] + b"\n",
            "truncated": original[:-1],
            "not_canonical": original.replace(b'{"action"', b'{ "action"', 1),
        }
        for name, data in tampered.items():
            with self.subTest(name=name):
                self.path.write_bytes(data)
                with self.assertRaises(approvals.ApprovalError):
                    approvals.read_records()
                with self.assertRaises(approvals.ApprovalError):
                    approvals.active_approval(first["record_id"])
        self.path.write_bytes(original)
        self.assertEqual(len(approvals.read_records()), 2)

    def test_revoke_is_a_new_record_and_cannot_repeat(self):
        record = self.approve()
        approvals.revoke(approval_id=record["record_id"], confirm=yes)
        with self.assertRaisesRegex(approvals.ApprovalError, "approval_revoked"):
            approvals.active_approval(record["record_id"])
        with self.assertRaises(approvals.ApprovalError):
            approvals.revoke(approval_id=record["record_id"], confirm=yes)
        with self.assertRaisesRegex(approvals.ApprovalError, "approval_not_found"):
            approvals.revoke(approval_id="f" * 32, confirm=yes)
        with self.assertRaisesRegex(approvals.ApprovalError, "no_active_approval_for_profile"):
            approvals.find_active(profile())
        self.assertEqual([r["action"] for r in approvals.read_records()], ["approve", "revoke"])


class ResolutionTests(Isolated):
    def config(self, record, **changes):
        return replace(local_sim_replay.worker_config(record, CONTRACT), **changes)

    def test_research_strategy_resolves_only_through_a_matching_active_approval(self):
        with self.assertRaisesRegex(strategy_registry.RegistryError, "unknown_strategy"):
            strategy_registry.resolve("donchian-breakout", "donchian-parameters-v1")
        record = self.approve()
        config = local_sim_replay.worker_config(record, CONTRACT)
        self.assertEqual(ipc.WorkerConfig.from_wire(config.to_wire()), config)
        entry = strategy_registry.resolve_deployment(config)
        self.assertEqual((entry.strategy_id, entry.sha256), ("donchian-breakout", research_catalog.DONCHIAN_SHA256))
        deployment = config.deployment
        mismatches = {
            "quantity": self.config(record, deployment=replace(deployment, quantity=D("2"))),
            "parameters": self.config(record, deployment=replace(
                deployment, parameters=(("entry_bars", 5), ("exit_bars", 2)))),
            "lookback": self.config(record, deployment=replace(deployment, lookback=5)),
            "warmup": self.config(record, warmup_bars=5),
            "timeframe": self.config(record, timeframe_ms=3_600_000),
            "instrument": self.config(record, contract=replace(CONTRACT, inst_id="ETH-USDT-SWAP")),
            "source": self.config(record, deployment=replace(deployment, source_sha256="0" * 64)),
        }
        for name, bad in mismatches.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(strategy_registry.RegistryError, "deployment_does_not_match_approval"):
                    strategy_registry.resolve_deployment(bad)
                with self.assertRaisesRegex(ipc.ProtocolError, "unregistered strategy"):
                    ipc.WorkerConfig.from_wire(bad.to_wire())
        unknown = self.config(record, deployment=replace(deployment, approval_id="a" * 32))
        with self.assertRaisesRegex(ipc.ProtocolError, "approval_not_found"):
            ipc.WorkerConfig.from_wire(unknown.to_wire())
        approvals.revoke(approval_id=record["record_id"], confirm=yes)
        with self.assertRaisesRegex(ipc.ProtocolError, "approval_revoked"):
            ipc.WorkerConfig.from_wire(config.to_wire())

    def test_edited_source_or_manifest_is_rejected_after_approval(self):
        record = self.approve()
        config = local_sim_replay.worker_config(record, CONTRACT)
        real = strategy_registry.read_manifest(research_catalog.DONCHIAN_MANIFEST, research_catalog.ROOT)
        copy = self.temp / "root"
        target = copy / "catos" / "research_donchian.py"
        target.parent.mkdir(parents=True)
        target.write_bytes((research_catalog.ROOT / "catos" / "research_donchian.py").read_bytes() + b"\n# edited\n")
        with patch.object(strategy_registry, "read_manifest", return_value=replace(real, root=copy)):
            with self.assertRaisesRegex(strategy_registry.RegistryError, "artifact_hash_mismatch"):
                strategy_registry.resolve_deployment(config)
        with patch.object(research_catalog, "file_hash", return_value="1" * 64):
            with self.assertRaisesRegex(strategy_registry.RegistryError, "deployment_manifest_changed"):
                strategy_registry.resolve_deployment(config)

    def test_checkpoint_v2_and_restart_history_contract(self):
        record = self.approve()
        config = local_sim_replay.worker_config(record, CONTRACT)
        initial = ipc.Checkpoint(config)
        self.assertEqual(set(initial.to_wire()), {"config", "event_seq", "last_open_time_ms"})
        self.assertEqual(ipc.Checkpoint.from_wire(initial.to_wire(), config), initial)
        with self.assertRaises(ipc.ProtocolError):
            ipc.Checkpoint.from_wire({**initial.to_wire(), "closes": []}, config)
        series = bars()
        checkpoint = ipc.Checkpoint(config, 6, series[5].open_time_ms)
        history = ipc.history_to_wire(series[2:6])
        self.assertEqual(ipc.parse_history(history, checkpoint), series[2:6])
        for bad in (ipc.history_to_wire(series[1:6]), ipc.history_to_wire(series[3:6]),
                    ipc.history_to_wire(series[1:5]), ipc.history_to_wire((*series[2:4], *series[5:7])),
                    None):
            with self.subTest(bad=bad), self.assertRaises(ipc.ProtocolError):
                ipc.parse_history(bad, checkpoint)
        v1 = ipc.WorkerConfig(CONTRACT, STEP, 2)
        with self.assertRaises(ipc.ProtocolError):
            ipc.parse_history(history, ipc.Checkpoint(v1))
        with self.assertRaisesRegex(ipc.ProtocolError, "names its artifact version"):
            ipc.WorkerConfig.from_wire({k: v for k, v in config.to_wire().items() if k != "strategy_artifact"})


class ReversalRiskTests(unittest.TestCase):
    def state(self, **changes):
        snapshot = risk.Snapshot(1, 0, 60_000, D("1000"), D("1000"), D("10"), D("100"),
                                 basis=risk.DayBasis(risk.taipei_day(0), D("1000"), "synthetic-day"),
                                 valuation_known=True, flows_known=True, margin_ok=True, position_verified=True)
        return risk.observe(risk.State(), replace(snapshot, **changes))

    def evaluate(self, target, state=None, **kwargs):
        state = self.state() if state is None else state
        return risk.evaluate(state, risk.Limits(), CONTRACT, D(target), state.snapshot.position, 0,
                             reconciled=True, **kwargs)

    def test_reversal_reserves_the_opening_leg_only_when_allowed(self):
        self.assertEqual(self.evaluate("-5").reason, "cross_zero_forbidden")
        verdict = self.evaluate("-5", allow_reversal=True)
        self.assertEqual((verdict.accepted, verdict.reason, verdict.quantity, verdict.reduce_only),
                         (True, "reversal_reserved", D("-5"), False))
        self.assertEqual(verdict.reservation, D("5") * CONTRACT.base_per_contract * D("100"))
        self.assertEqual(self.evaluate("0", allow_reversal=True).reason, "legal_reduction")

    def test_reversal_keeps_conflict_gates_and_exposure_budget(self):
        self.assertEqual(self.evaluate("-5", self.state(reduction_conflict=True), allow_reversal=True).reason,
                         "reduction_conflict")
        self.assertEqual(self.evaluate("-5", held_reduction=True, allow_reversal=True).reason, "reduction_conflict")
        self.assertEqual(self.evaluate("-5", self.state(pending_sell=D("1")), allow_reversal=True).reason,
                         "reduction_conflict")
        self.assertEqual(self.evaluate("-5", self.state(margin_ok=False), allow_reversal=True).reason,
                         "increase_gate_closed")
        # 1500 USDT single-coin budget at mark 100 and 0.01 per contract = 1500 contracts.
        self.assertTrue(self.evaluate("-1500", allow_reversal=True).accepted)
        self.assertEqual(self.evaluate("-1501", allow_reversal=True).reason, "symbol_exposure_limit")


class WorkerV2Tests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, {approvals.ENV_PATH: str(self.temp / "approvals.jsonl")}))
        value = profile()
        artifact, _ = approvals.deployment_identity(value)
        self.record = approvals.approve(strategy_id=value["strategy_id"], version=value["version"],
                                        sha256=artifact["sha256"], profile=value, confirm=yes)
        self.config = local_sim_replay.worker_config(self.record, CONTRACT)

    async def run_host(self, host, series, start, position=D("0")):
        results = []
        for index in range(start, len(series)):
            bar = series[index]
            seq = index + 1
            account = None if seq <= 4 else research.AccountView(
                bar.open_time_ms + STEP, position, D("0"), D("1000"), D("0"), D("0"), D("1000"), D("0"), D("0"))
            result = await host.process_bar(bar, account)
            results.append((result.target_position, result.ready))
        return results

    async def test_restart_from_committed_history_matches_uninterrupted_worker(self):
        series = bars()
        async with WorkerHost("bot", self.config) as host:
            uninterrupted = await self.run_host(host, series, 0)
        self.assertEqual([ready for _, ready in uninterrupted], [i >= 3 for i in range(len(series))])
        for cut in (2, 4, 7, 12):
            with self.subTest(cut=cut):
                checkpoint = ipc.Checkpoint(self.config, cut, series[cut - 1].open_time_ms)
                history = series[max(0, cut - 4):cut]
                async with WorkerHost("bot", self.config, checkpoint=checkpoint, history=history) as host:
                    resumed = await self.run_host(host, series, cut)
                self.assertEqual(resumed, uninterrupted[cut:])
        with self.assertRaises(ipc.ProtocolError):
            WorkerHost("bot", self.config, checkpoint=ipc.Checkpoint(self.config, 7, series[6].open_time_ms),
                       history=series[2:6])

    async def test_revocation_stops_the_worker_at_the_next_bar(self):
        series = bars()
        host = WorkerHost("bot", self.config)
        self.addAsyncCleanup(host.close)
        await host.start()
        await host.process_bar(series[0])
        approvals.revoke(approval_id=self.record["record_id"], confirm=yes)
        with self.assertRaises(WorkerError):
            await host.process_bar(series[1])
        self.assertIn("approval_revoked", bytes(host.stderr_tail).decode() + str(host.failure))


class ReplayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, {approvals.ENV_PATH: str(self.temp / "approvals.jsonl")}))
        value = profile()
        artifact, _ = approvals.deployment_identity(value)
        self.record = approvals.approve(strategy_id=value["strategy_id"], version=value["version"],
                                        sha256=artifact["sha256"], profile=value, confirm=yes)

    async def replay(self, name, series=None, **kwargs):
        return await local_sim_replay.replay_bars(record=self.record, contract=CONTRACT,
                                                  bars=bars() if series is None else series,
                                                  output_dir=self.temp / name, **kwargs)

    def ledger(self, name, query):
        connection = sqlite3.connect(self.temp / name / "state.sqlite3")
        try:
            return connection.execute(query).fetchall()
        finally:
            connection.close()

    async def test_reversals_go_out_as_two_legs_and_match_research_exactly(self):
        summary = await self.replay("a")
        self.assertEqual(summary["status"]["state"], "completed", summary["status"])
        report = replay_consistency.compare_run(self.temp / "a", bars(), CONTRACT)
        self.assertTrue(report["passed"], json.dumps(report["checks"]))
        self.assertGreaterEqual(report["counts"]["reversal_decisions"], 3)
        self.assertEqual(report["counts"]["dispositions"].get("REJECTED"), None)
        orders = self.ledger("a", "SELECT order_key,intent_key,payload_json FROM execution_orders ORDER BY rowid")
        closes = [row for row in orders if row[1] is None]
        self.assertEqual(len(closes), report["counts"]["reversal_decisions"])
        for order_key, _, payload in closes:
            self.assertEqual(json.loads(order_key)["kind"], "reversal_close")
            self.assertTrue(json.loads(payload)["reduceOnly"])
            self.assertEqual(json.loads(payload)["tag"], "41cb53c54d6dABDE")
            following = orders[orders.index((order_key, None, payload)) + 1]
            self.assertEqual(following[1], json.loads(order_key)["intent_key"])
            self.assertFalse(json.loads(following[2])["reduceOnly"])
        reasons = dict(self.ledger("a", "SELECT reason,count(*) FROM intents GROUP BY reason"))
        self.assertEqual(reasons["reversal_reserved"], report["counts"]["reversal_decisions"])
        keys = [json.loads(row[0]) for row in self.ledger("a", "SELECT intent_key FROM intents")]
        self.assertTrue(all(key[3:6] == ["donchian-breakout", "donchian-parameters-v1", self.record["record_id"]]
                            for key in keys))

    async def test_two_replays_are_byte_identical(self):
        await self.replay("a")
        await self.replay("b")
        repeat = replay_consistency.compare_repeat(self.temp / "a", self.temp / "b")
        self.assertTrue(repeat["passed"], repeat)

    async def test_resume_restores_the_worker_from_committed_bars(self):
        stop = asyncio.Event()

        def at(status):
            if status["bars"] == 10:
                stop.set()

        with patch.object(local_sim_replay, "PROGRESS_EVERY_BARS", 1):
            first = await self.replay("a", stop=stop, progress=at)
        self.assertEqual((first["status"]["state"], first["status"]["stop_reason"], first["status"]["bars"]),
                         ("stopped", "operator_stop", 10))
        resumed = await local_sim_replay.replay_bars(record=self.record, contract=CONTRACT, bars=bars(),
                                                     output_dir=self.temp / "a", resume=True)
        self.assertEqual(resumed["status"]["state"], "completed", resumed["status"])
        await self.replay("fresh")
        repeat = replay_consistency.compare_repeat(self.temp / "a", self.temp / "fresh")
        self.assertTrue(repeat["passed"], repeat)
        self.assertTrue(replay_consistency.compare_run(self.temp / "a", bars(), CONTRACT)["passed"])

    async def test_revocation_stops_before_the_next_bar_without_flatten_or_release(self):
        def at(status):
            if status["bars"] == 7 and status["state"] == "running":
                approvals.revoke(approval_id=self.record["record_id"], confirm=yes)

        with patch.object(local_sim_replay, "PROGRESS_EVERY_BARS", 1):
            summary = await self.replay("a", progress=at)
        self.assertEqual(summary["status"]["state"], "stopped")
        self.assertTrue(summary["status"]["stop_reason"].endswith("approval_revoked"), summary["status"])
        self.assertEqual(summary["status"]["bars"], 7)
        self.assertEqual(self.ledger("a", "SELECT position FROM ownership"), [("1",)])
        self.assertEqual(self.ledger("a", "SELECT count(*) FROM execution_orders WHERE json_extract(payload_json,"
                                          "'$.reduceOnly')=1"), [(0,)])

    async def test_soft_loss_stops_the_replay_without_liquidation(self):
        tight = risk.Limits(D("3.0"), D("0.50"), D("0.0001"), D("0.0002"))
        summary = await self.replay("a", risk_limits=tight)
        self.assertEqual(summary["status"]["state"], "stopped")
        self.assertTrue(summary["status"]["stop_reason"].startswith("risk_halt:"), summary["status"])
        flatten = self.ledger("a", "SELECT count(*) FROM execution_orders WHERE order_key LIKE '%flatten%'")
        self.assertEqual(flatten, [(0,)])

    async def test_rejected_verdict_stops_the_replay(self):
        tiny = risk.Limits(D("0.0001"), D("0.50"), D("0.10"), D("0.20"))
        summary = await self.replay("a", risk_limits=tiny)
        self.assertEqual(summary["status"]["state"], "stopped")
        self.assertEqual(summary["status"]["stop_reason"], "unexpected_verdict:REJECTED:account_exposure_limit")
        self.assertFalse(replay_consistency.compare_run(self.temp / "a", bars(), CONTRACT)["passed"])

    async def test_blocked_close_leg_ends_the_whole_reversal_atomically(self):
        original = local_sim_replay._fill_intent
        seen = {}

        async def latched(supervisor, exchange, config, receipt, view, *args):
            if view.position * receipt.target_position < 0 and not seen:
                supervisor.latch("manual_kill")  # gates close between commit and dispatch
                await supervisor.persist_controls()
                seen["row"] = await supervisor.dispatch(receipt.intent_key, now_ms=args[-3])
                seen["key"] = receipt.intent_key
                raise local_sim_replay.ReplayStopped("test_latched")
            return await original(supervisor, exchange, config, receipt, view, *args)

        with patch.object(local_sim_replay, "_fill_intent", latched):
            summary = await self.replay("a")
        self.assertEqual(summary["status"]["stop_reason"], "test_latched")
        self.assertIsNone(seen["row"])
        rows = self.ledger("a", "SELECT order_key,intent_key,state,settled FROM execution_orders ORDER BY rowid")
        close_key = json.dumps({"intent_key": seen["key"], "kind": "reversal_close"}, sort_keys=True,
                               separators=(",", ":"), ensure_ascii=False)
        self.assertEqual(rows[-2:], [(close_key, None, "ABORTED", 1), (seen["key"], seen["key"], "ABORTED", 1)])
        for table in ("reservations", "outbox", "risk_orders"):
            self.assertEqual(self.ledger("a", f"SELECT count(*) FROM {table}"), [(0,)])
        self.assertEqual(self.ledger("a", "SELECT position FROM ownership"), [("1",)])

    async def test_read_only_overview_lists_approvals_runs_and_consistency(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from catos import replay_api
        runs = self.temp / "runs"
        await local_sim_replay.replay_bars(record=self.record, contract=CONTRACT, bars=bars(),
                                           output_dir=runs / "r1")
        report = replay_consistency.compare_run(runs / "r1", bars(), CONTRACT)
        (runs / "r1" / "consistency.json").write_text(json.dumps(report), encoding="utf-8")
        before = {p: p.stat().st_mtime_ns for p in self.temp.rglob("*") if p.is_file()}
        client = TestClient(replay_api.mount_replay(FastAPI(), root=runs), base_url="http://127.0.0.1")
        response = client.get(replay_api.PATH)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["approvals_state"], "available")
        self.assertEqual([(a["approval_id"], a["state"], a["source"]) for a in body["approvals"]],
                         [(self.record["record_id"], "active", "current")])
        (run,) = body["runs"]
        self.assertEqual((run["state"], run["bars_done"], run["consistency"]["passed"]), ("completed", len(CLOSES), True))
        self.assertEqual(client.post(replay_api.PATH).status_code, 405)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in self.temp.rglob("*") if p.is_file()})
        approvals.revoke(approval_id=self.record["record_id"], confirm=yes)
        self.assertEqual(client.get(replay_api.PATH).json()["approvals"][0]["state"], "revoked")
        Path(os.environ[approvals.ENV_PATH]).write_bytes(b"broken" + bytes([10]))
        broken = client.get(replay_api.PATH).json()
        self.assertEqual((broken["approvals_state"], broken["approvals"]), ("unavailable", []))

    async def test_unapproved_profile_cannot_replay(self):
        with self.assertRaisesRegex(approvals.ApprovalError, "no_active_approval_for_profile"):
            await local_sim_replay.replay(profile=profile(entry=6, exit=3),
                                          dataset_id=research_catalog.DATASET_ID, output_root=self.temp / "x")
        self.assertFalse((self.temp / "x").exists())


if __name__ == "__main__":
    unittest.main()
