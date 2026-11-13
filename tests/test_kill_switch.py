"""Work package B: Kill-Switch record file, its checks in every run, the HTTP routes, and the new defaults.

Every test points CATOS_KILL_SWITCH (and CATOS_STRATEGY_APPROVALS where needed) at an
isolated temporary file; nothing touches outputs/ or a network.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from catos import account_lock, cli, kill_switch as ks, local_sim_replay, risk, strategy_approvals as approvals
from catos import local_sim_control as control
from catos import simulation_catalog as catalog
from catos.local_sim_control_api import PREFIX
from catos.supervisor import LocalSupervisor
from catos.workspace_api import create_app
from test_ipc import config
from test_journal import proof
from test_risk import snapshot
from test_step2_deployment import CONTRACT, bars, profile, yes

D = Decimal
REQ_A, REQ_B, REQ_C = "a" * 32, "b" * 32, "c" * 32


class IsolatedSwitch(unittest.TestCase):
    def setUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.temp / "controls" / "kill-switch.jsonl"
        self.enterContext(patch.dict(os.environ, {ks.ENV_PATH: str(self.path)}))


class RecordFileTests(IsolatedSwitch):
    def test_missing_file_is_clear(self):
        value = ks.status()
        self.assertEqual((value["engaged"], value["error"], value["count"]), (False, None, 0))
        self.assertEqual(ks.require_clear(), 0)

    def test_engage_is_idempotent_and_clear_needs_the_typed_word(self):
        first, appended = ks.engage(reason="手動測試", actor="http", request_id=REQ_A)
        self.assertTrue(appended)
        self.assertEqual(first["prev_sha256"], ks.GENESIS)
        again, appended = ks.engage(reason="再按一次", actor="cli")
        self.assertEqual((again, appended), (first, False))
        replay, appended = ks.engage(reason="同一個 request", actor="http", request_id=REQ_A)
        self.assertEqual((replay, appended), (first, False))
        self.assertTrue(ks.status()["engaged"])
        with self.assertRaisesRegex(ks.KillSwitchError, "kill_switch_engaged"):
            ks.require_clear()
        for word in ("", "解除 ", "clear", None):
            with self.subTest(word=word), self.assertRaisesRegex(ks.KillSwitchError, "confirmation_required"):
                ks.clear(reason="r", actor="http", confirm=word)
        with self.assertRaisesRegex(ks.KillSwitchError, "simulation_run_active"):
            ks.clear(reason="r", actor="http", confirm="解除", runs_active=lambda: True)
        with self.assertRaisesRegex(ks.KillSwitchError, "request_id_conflict"):
            ks.clear(reason="r", actor="http", confirm="解除", request_id=REQ_A)
        cleared = ks.clear(reason="查完了", actor="http", confirm="解除", request_id=REQ_B)
        self.assertEqual(ks.clear(reason="x", actor="http", confirm="解除", request_id=REQ_B), cleared)
        with self.assertRaisesRegex(ks.KillSwitchError, "kill_switch_not_engaged"):
            ks.clear(reason="r", actor="http", confirm="解除")
        lines = self.path.read_bytes().split(b"\n")
        self.assertEqual(cleared["prev_sha256"], ks._sha256(lines[0] + b"\n"))
        self.assertEqual([r["action"] for r in ks.read_records()], ["engage", "clear"])
        self.assertEqual(ks.require_clear(), 2)

    def test_reason_and_actor_are_validated(self):
        for reason in ("", " x", "x" * 201, "a\nb", 3):
            with self.subTest(reason=reason), self.assertRaisesRegex(ks.KillSwitchError, "reason_invalid"):
                ks.engage(reason=reason, actor="http")
        with self.assertRaisesRegex(ks.KillSwitchError, "actor_invalid"):
            ks.engage(reason="r", actor="agent")
        with self.assertRaisesRegex(ks.KillSwitchError, "request_id_invalid"):
            ks.engage(reason="r", actor="http", request_id="A" * 32)
        self.assertFalse(self.path.exists())

    def test_any_doubt_about_the_file_reads_as_engaged(self):
        ks.engage(reason="r", actor="cli")
        ks.clear(reason="r", actor="cli", confirm="解除")
        good = self.path.read_bytes()
        broken = {
            "edited": good.replace("\"r\"".encode(), "\"x\"".encode(), 1),
            "truncated": good[:-1],
            "reordered": b"\n".join(reversed(good.split(b"\n")[:-1])) + b"\n",
            "removed_first": good.split(b"\n", 1)[1],
            "not_json": good + b"{\n",
        }
        for name, raw in broken.items():
            with self.subTest(name=name):
                self.path.write_bytes(raw)
                value = ks.status()
                self.assertTrue(value["engaged"])
                self.assertIsNotNone(value["error"])
                with self.assertRaises(ks.KillSwitchError):
                    ks.require_clear()
                with self.assertRaises(ks.KillSwitchError):
                    ks.Watch()

    def test_deleted_or_emptied_file_after_first_use_reads_as_engaged(self):
        # Acceptance D1 (2026-11-14): only "neither file nor .lock sidecar" is a fresh install.
        ks.engage(reason="r", actor="cli")
        self.assertTrue(ks.lock_path(self.path).exists())
        self.path.unlink()
        value = ks.status()
        self.assertEqual((value["engaged"], value["error"]), (True, "kill_switch_file_missing"))
        with self.assertRaisesRegex(ks.KillSwitchError, "kill_switch_file_missing"):
            ks.require_clear()
        with self.assertRaisesRegex(ks.KillSwitchError, "kill_switch_file_missing"):
            ks.Watch()
        with self.assertRaisesRegex(ks.KillSwitchError, "kill_switch_file_missing"):
            ks.engage(reason="r", actor="cli")
        self.path.write_bytes(b"")
        value = ks.status()
        self.assertEqual((value["engaged"], value["error"]), (True, "kill_switch_file_empty"))
        with self.assertRaisesRegex(ks.KillSwitchError, "kill_switch_file_empty"):
            ks.require_clear()
        # Resetting means deleting both files on purpose.
        self.path.unlink()
        ks.lock_path(self.path).unlink()
        self.assertFalse(ks.status()["engaged"])
        self.assertEqual(ks.require_clear(), 0)
        record, appended = ks.engage(reason="r", actor="http")
        self.assertTrue(appended)
        self.assertEqual(record["prev_sha256"], ks.GENESIS)

    def test_concurrent_engages_append_exactly_one_record(self):
        ids = [f"{i:032x}" for i in range(12)]
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda rid: ks.engage(reason="並行", actor="http", request_id=rid), ids))
        self.assertEqual(sum(appended for _, appended in results), 1)
        self.assertEqual(len(ks.read_records()), 1)


class WatchTests(IsolatedSwitch):
    def test_fires_on_engage_even_if_cleared_before_the_next_check(self):
        watch = ks.Watch()
        self.assertIsNone(watch.check())
        record, _ = ks.engage(reason="r", actor="http")
        ks.clear(reason="r", actor="http", confirm="解除")
        self.assertEqual(watch.check(), "kill-switch-" + record["record_id"])
        self.assertEqual(watch.check(), "kill-switch-" + record["record_id"])  # stays fired

    def test_earlier_history_does_not_fire_and_a_vanished_file_does(self):
        ks.engage(reason="r", actor="cli")
        ks.clear(reason="r", actor="cli", confirm="解除")
        watch = ks.Watch()
        self.assertEqual(watch.start_count, 2)
        self.assertIsNone(watch.check())
        self.path.unlink()
        self.assertEqual(watch.check(), "kill-switch-unreadable")

    def test_watch_reports_who_engaged(self):
        watch = ks.Watch()
        self.assertEqual(watch.actor, "kill-switch")
        ks.engage(reason="r", actor="http")
        watch.check()
        self.assertEqual(watch.actor, "kill-switch-http")

    def test_engaged_switch_refuses_a_new_watch(self):
        ks.engage(reason="r", actor="cli")
        with self.assertRaisesRegex(ks.KillSwitchError, "kill_switch_engaged"):
            ks.Watch()


class CliTests(IsolatedSwitch):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            code = cli.main(["kill", *argv])
        return code, out.getvalue() + err.getvalue()

    def test_engage_status_and_clear_needs_an_interactive_terminal(self):
        code, text = self.run_cli("engage", "--reason", "cli test")
        self.assertEqual(code, 0, text)
        self.assertIn("已觸發", text)
        code, text = self.run_cli("status")
        self.assertIn("已觸發", text)
        code, text = self.run_cli("clear", "--reason", "agent tries")
        self.assertEqual(code, 1)
        self.assertIn("interactive_terminal_required", text)
        self.assertTrue(ks.status()["engaged"])


class NewDefaultTests(unittest.TestCase):
    def verdict(self, s=None, target="2", limits=None, **kwargs):
        limits = risk.Limits() if limits is None else limits
        state = risk.observe(risk.State(), snapshot() if s is None else s, limits)
        return risk.evaluate(state, limits, config().contract, D(target), state.snapshot.position,
                             state.snapshot.time_ms, reconciled=True, **kwargs)

    def test_default_values(self):
        self.assertEqual(risk.Limits().to_wire(),
                         {"leverage": "1.0", "symbol_share": "0.50", "soft_loss": "0.05", "hard_loss": "0.10"})
        self.assertEqual(risk.LEGACY_LIMITS.to_wire(),
                         {"leverage": "3.0", "symbol_share": "0.50", "soft_loss": "0.10", "hard_loss": "0.20"})
        self.assertEqual(local_sim_replay.LIMIT_SETS["current"], risk.Limits())
        self.assertEqual(local_sim_replay.LIMIT_SETS["legacy-v1"], risk.LEGACY_LIMITS)
        self.assertEqual(control.LocalSimControlService(Path(tempfile.gettempdir())).limits, risk.Limits())

    def test_single_coin_is_half_of_equity_and_account_is_one_times(self):
        # equity 1000, mark 100, 0.01 base per contract: 500 contracts = 500 notional = 0.5x.
        self.assertTrue(self.verdict(target="500").accepted)
        self.assertEqual(self.verdict(target="501").reason, "symbol_exposure_limit")
        self.assertTrue(self.verdict(snapshot(other_notional=D("500")), target="500").accepted)
        self.assertEqual(self.verdict(snapshot(other_notional=D("501")), target="500").reason,
                         "account_exposure_limit")
        self.assertTrue(self.verdict(target="1500", limits=risk.LEGACY_LIMITS).accepted)

    def test_soft_five_and_hard_ten_percent_boundaries(self):
        for equity, expected in (("950.0001", "RUN"), ("950", "NO_INCREASE"), ("900.0001", "NO_INCREASE"),
                                 ("900", "FLAT")):
            with self.subTest(equity=equity):
                self.assertEqual(risk.observe(risk.State(), snapshot(equity=D(equity)), risk.Limits()).mode, expected)


class SupervisorKillTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.directory / "state.sqlite3"
        self.enterContext(patch.object(account_lock, "LOCK_DIRECTORY", self.directory / "locks"))
        self.s = self.make()
        await self.s.start()
        await self.s.reconcile(proof(0))
        self.s.observe_risk(snapshot(1, 1))
        await self.s.persist_controls()

    async def asyncTearDown(self):
        await self.s.close()

    def make(self):
        return LocalSupervisor(self.path, account_id="fake-account", bot_id="bot", config=config(),
                               fixture_budget=D(100), risk_limits=risk.Limits())

    async def test_manual_kill_latches_flat_with_an_audit_row_and_survives_restart(self):
        state = await self.s.manual_kill(actor="kill-switch", evidence_id="kill-switch-" + "e" * 32)
        self.assertEqual((state.mode, set(state.reasons)), ("FLAT", {"manual_kill"}))
        audit = await self.s._io(lambda: [tuple(r) for r in self.s._journal.connection.execute(
            "SELECT kind, actor, evidence_id, before_json, after_json FROM risk_actions")])
        self.assertEqual([row[:3] for row in audit], [("manual_kill", "kill-switch", "kill-switch-" + "e" * 32)])
        self.assertEqual(json.loads(audit[0][3])["mode"], "RUN")
        self.assertEqual(json.loads(audit[0][4])["mode"], "FLAT")
        await self.s.close()
        self.s = self.make()
        await self.s.start()
        self.assertIn("manual_kill", self.s.halt_reasons)
        self.assertEqual(self.s.risk_state.mode, "FLAT")

    async def test_invalid_evidence_is_rejected_before_latching(self):
        with self.assertRaises(Exception):
            await self.s.manual_kill(actor="kill switch", evidence_id="x")
        self.assertEqual(self.s.risk_state.mode, "RUN")


class ControlPlaneKillTests(unittest.IsolatedAsyncioTestCase):
    """The real runner (Supervisor, Worker, FakeExchange) in an isolated data root."""

    async def asyncSetUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, {ks.ENV_PATH: str(self.temp / "kill.jsonl")}))
        self.service = control.LocalSimControlService(self.temp / "simulation")
        self.service.open()

    async def asyncTearDown(self):
        await self.service.close()

    async def test_engage_refuses_new_runs_and_stops_a_running_one_before_its_next_bar(self):
        run = await self.service.start(REQ_A, control.TEMPLATE)
        run_id = run["run_id"]
        for _ in range(200):
            if self.service.runs[run_id]["warmup_bars"] >= 1:
                break
            await asyncio.sleep(0.05)
        reply = await self.service.engage_kill(REQ_B, "測試中途停止")
        self.assertTrue(reply["appended"])
        with self.assertRaisesRegex(control.ControlError, "simulation_run_active"):
            await self.service.clear_kill(REQ_C, "太早", "解除")
        await asyncio.wait_for(asyncio.shield(self.service.task), 60)
        record = self.service.runs[run_id]
        self.assertEqual((record["control_state"], record["error"], record["cleanup_confirmed"]),
                         ("stopped", "manual_kill", True))
        self.assertLess(record["bars"], 8)
        kinds = [event["kind"] for event in record["events"]]
        self.assertIn("kill_switch", kinds)
        connection = sqlite3.connect(self.temp / "simulation" / run_id / "state.sqlite3")
        try:
            rows = connection.execute("SELECT kind, evidence_id FROM risk_actions").fetchall()
            reasons = json.loads(connection.execute("SELECT halt_reasons FROM control").fetchone()[0])
        finally:
            connection.close()
        self.assertEqual(rows, [("manual_kill", "kill-switch-" + reply["record"]["record_id"])])
        actors = sqlite3.connect(self.temp / "simulation" / run_id / "state.sqlite3")
        try:
            self.assertEqual(actors.execute("SELECT actor FROM risk_actions").fetchall(), [("kill-switch-http",)])
        finally:
            actors.close()
        self.assertIn("manual_kill", reasons)
        with self.assertRaises(control.ControlError) as caught:
            await self.service.start("d" * 32, control.TEMPLATE)
        self.assertEqual((str(caught.exception), caught.exception.status), ("kill_switch_engaged", 409))
        self.assertTrue(self.service.state()["kill_switch"]["engaged"])
        await self.service.clear_kill(REQ_C, "確認過了", "解除")
        self.assertFalse(self.service.kill_switch()["engaged"])
        self.assertEqual(record["control_state"], "stopped")  # a killed run stays terminal


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, {ks.ENV_PATH: str(self.temp / "kill.jsonl")}))

    def client(self):
        app = create_app(output_dir=self.temp / "research", evidence_root=self.temp / "r4",
                         simulation_root=self.temp / "simulation", replay_root=self.temp / "replay")
        return TestClient(app, base_url="http://127.0.0.1")

    def headers(self, client):
        value = client.get(PREFIX + "/version").json()
        return {"X-CatOS-Build": value["build_id"], "X-CatOS-Instance": value["instance_id"]}

    def test_routes_checks_and_state(self):
        with self.client() as client:
            headers = self.headers(client)
            status = client.get(PREFIX + "/kill-switch").json()
            self.assertEqual((status["engaged"], status["confirm_word"]), (False, "解除"))
            self.assertEqual(status["default_limits"], risk.Limits().to_wire())
            self.assertNotIn("path", status)
            before = client.get(PREFIX + "/state").json()
            self.assertFalse(before["kill_switch"]["engaged"])
            engage = PREFIX + "/kill-switch/engage"
            self.assertEqual(client.post(engage, json={"request_id": REQ_A, "reason": "r"},
                                         headers={**headers, "Origin": "http://evil.example"}).status_code, 403)
            self.assertEqual(client.post(engage, json={"request_id": REQ_A, "reason": "r", "x": 1},
                                         headers=headers).status_code, 422)
            self.assertEqual(client.post(engage, json={"request_id": REQ_A, "reason": ""},
                                         headers=headers).status_code, 422)
            # Engage is not bound to the page's instance/build: a stale page can still stop everything.
            reply = client.post(engage, json={"request_id": REQ_A, "reason": "介面測試"},
                                headers={"X-CatOS-Build": "old", "X-CatOS-Instance": "old"})
            self.assertEqual(reply.status_code, 200, reply.text)
            self.assertTrue(reply.json()["kill_switch"]["engaged"])
            after = client.get(PREFIX + f"/state?since_version={before['version']}").json()
            self.assertFalse(after["unchanged"])
            self.assertTrue(after["kill_switch"]["engaged"])
            start = client.post(PREFIX + "/bots/start", json={"request_id": REQ_B, "bot_id": catalog.BOT_ID},
                                headers=headers)
            self.assertEqual((start.status_code, start.json()["detail"]), (409, "kill_switch_engaged"))
            clear = PREFIX + "/kill-switch/clear"
            self.assertEqual(client.post(clear, json={"request_id": REQ_C, "reason": "r", "confirm": "解除"},
                                         headers={**headers, "X-CatOS-Build": "old"}).status_code, 409)
            wrong = client.post(clear, json={"request_id": REQ_C, "reason": "r", "confirm": "clear"}, headers=headers)
            self.assertEqual((wrong.status_code, wrong.json()["detail"]), (422, "kill_switch_confirmation_required"))
            self.assertEqual(client.post(clear + "?mode=live", json={"request_id": REQ_C, "reason": "r",
                                         "confirm": "解除"}, headers=headers).status_code, 403)
            ok = client.post(clear, json={"request_id": REQ_C, "reason": "查過了", "confirm": "解除"}, headers=headers)
            self.assertEqual(ok.status_code, 200, ok.text)
            self.assertFalse(ok.json()["kill_switch"]["engaged"])
            self.assertEqual([r["action"] for r in client.get(PREFIX + "/kill-switch").json()["recent"]],
                             ["clear", "engage"])
        with TestClient(create_app(output_dir=self.temp / "research2", evidence_root=self.temp / "r4b",
                                   simulation_root=self.temp / "simulation2"),
                        base_url="http://localhost") as remote:
            self.assertEqual(remote.get(PREFIX + "/kill-switch").status_code, 403)


class ReplayKillTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, {approvals.ENV_PATH: str(self.temp / "approvals.jsonl"),
                                                  ks.ENV_PATH: str(self.temp / "kill.jsonl")}))
        value = profile()
        artifact, _ = approvals.deployment_identity(value)
        self.record = approvals.approve(strategy_id=value["strategy_id"], version=value["version"],
                                        sha256=artifact["sha256"], profile=value, confirm=yes)

    async def replay(self, name, **kwargs):
        return await local_sim_replay.replay_bars(record=self.record, contract=CONTRACT, bars=bars(),
                                                  output_dir=self.temp / name, **kwargs)

    def ledger(self, name, query):
        connection = sqlite3.connect(self.temp / name / "state.sqlite3")
        try:
            return connection.execute(query).fetchall()
        finally:
            connection.close()

    async def test_engaged_switch_refuses_before_the_run_directory_exists(self):
        ks.engage(reason="r", actor="cli")
        with self.assertRaisesRegex(ks.KillSwitchError, "kill_switch_engaged"):
            await self.replay("a")
        self.assertFalse((self.temp / "a").exists())

    async def test_engage_mid_run_latches_and_stops_without_flatten_and_cannot_resume(self):
        fired = {}

        def at(status):
            if status["bars"] == 7 and status["state"] == "running" and not fired:
                fired["record"], _ = ks.engage(reason="中途停", actor="cli")

        with patch.object(local_sim_replay, "PROGRESS_EVERY_BARS", 1):
            summary = await self.replay("a", progress=at)
        evidence = "kill-switch-" + fired["record"]["record_id"]
        self.assertEqual((summary["status"]["state"], summary["status"]["stop_reason"]),
                         ("stopped", "manual_kill:" + evidence))
        self.assertEqual(summary["status"]["bars"], 7)
        self.assertEqual(self.ledger("a", "SELECT kind, evidence_id FROM risk_actions"),
                         [("manual_kill", evidence)])
        self.assertEqual(self.ledger("a", "SELECT count(*) FROM execution_orders WHERE json_extract(payload_json,"
                                          "'$.reduceOnly')=1"), [(0,)])
        self.assertEqual(self.ledger("a", "SELECT position FROM ownership"), [("1",)])
        ks.clear(reason="r", actor="cli", confirm="解除")
        resumed = await local_sim_replay.replay_bars(record=self.record, contract=CONTRACT, bars=bars(),
                                                     output_dir=self.temp / "a", resume=True)
        self.assertEqual((resumed["status"]["state"], resumed["status"]["stop_reason"]),
                         ("stopped", "supervisor_not_healthy"))

    async def test_a_latch_that_does_not_persist_is_a_failure_not_a_clean_stop(self):
        def at(status):
            if status["bars"] == 7 and status["state"] == "running" and not ks.status()["engaged"]:
                ks.engage(reason="r", actor="cli")

        async def broken(self, **kwargs):
            raise OSError("disk full")

        with patch.object(local_sim_replay, "PROGRESS_EVERY_BARS", 1), \
                patch.object(LocalSupervisor, "manual_kill", broken):
            summary = await self.replay("a", progress=at)
        self.assertEqual(summary["status"]["state"], "failed")
        self.assertIn("manual_kill_latch_failed", summary["status"]["stop_reason"])

    async def test_legacy_limit_set_is_recorded_in_the_manifest(self):
        summary = await self.replay("a", risk_limits=local_sim_replay.LIMIT_SETS["legacy-v1"])
        self.assertEqual(summary["risk_limits"], risk.LEGACY_LIMITS.to_wire())
        default = await self.replay("b")
        self.assertEqual(default["risk_limits"], risk.Limits().to_wire())
        self.assertEqual(default["fills_sha256"], summary["fills_sha256"])


if __name__ == "__main__":
    unittest.main()
