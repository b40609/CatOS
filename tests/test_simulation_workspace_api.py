"""v1 simulation workspace projections and HTTP routes (isolated data roots only)."""

import asyncio
from decimal import Decimal, localcontext
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from catos import account_lock, research, risk
from catos import local_sim_control as control
from catos import local_sim_control_runner as runner
from catos import simulation_catalog as catalog
from catos.local_sim_control_api import PREFIX
from catos.workspace_api import create_app

BUILD = "a" * 64
REQUEST, STOP, OTHER = "a" * 32, "b" * 32, "c" * 32
T0 = 1_762_092_900_000
DAY = risk.taipei_day(T0)
BASIS = risk.DayBasis(DAY, Decimal("1000"), f"r4-midnight-{DAY}", account_alias="sim-control-test",
                      environment="local-sim", source=risk.SYNTHETIC_BASELINE_SOURCE)
FLAT = {"time_ms": T0, "position": "0", "average_entry": "0", "balance": "1000", "realized_pnl": "0",
        "unrealized_pnl": "0", "equity": "1000", "fees": "0", "funding_paid": "0"}
LONG = {**FLAT, "time_ms": T0 + 900_000, "position": "2", "average_entry": "100.1",
        "unrealized_pnl": "3.21", "equity": "1003.21", "fees": "0.1"}


def state(seq, time_ms, equity, position, reasons=()):
    snapshot = risk.Snapshot(seq, time_ms, time_ms + 900_000, Decimal(equity), Decimal(equity),
                             Decimal(position), Decimal("101.5"), basis=BASIS, valuation_known=True,
                             flows_known=True, margin_ok=True, position_verified=True)
    value = risk.State(seq, time_ms, "RUN", "HEALTHY", "IDLE", basis=BASIS, snapshot=snapshot)
    return risk.halt(value, reasons) if reasons else value


async def held_runner(directory, run_id, stop, emit, update, source_ok):
    update(control_state="running")
    await stop.wait()
    return dict(control_state="stopped", cleanup_confirmed=True, worker_closed=True)


async def scripted_runner(directory, run_id, stop, emit, update, source_ok):
    """Realistic event shapes (real risk.State wire) without a Supervisor or SQLite."""
    update(control_state="running", worker_pid=4242)
    emit("warmup", seq=1, target=None, disposition="NO_INTENT")
    emit("day_basis", synthetic_time_ms=T0, basis=BASIS.to_wire())
    emit("signal", seq=3, synthetic_time_ms=T0, target="2", disposition="RESERVED_SIMULATION",
         reason="sma_cross_up", account=FLAT, intent_key="k3", mark="101.5",
         risk_state=state(1, T0, "1000", "0").to_wire())
    emit("fill", seq=3, synthetic_time_ms=T0 + 900_000, request={"tag": "41cb53c54d6dABDE"},
         fill={"quantity": "2", "price": "100.1", "fee": "0.1"}, position="2", fees="0.1",
         equity="1003.21", state="FILLED")
    update(bars=1, fills=1, last_synthetic_time_ms=T0)
    await stop.wait()
    return dict(control_state="stopped", cleanup_confirmed=True, worker_closed=True)


async def completing_runner(directory, run_id, stop, emit, update, source_ok):
    update(control_state="running")
    emit("signal", seq=3, synthetic_time_ms=T0 + 900_000, target=None, disposition="NO_CHANGE",
         reason=None, account=LONG, intent_key=None, mark="101.5",
         risk_state=state(2, T0 + 900_000, "1003.21", "2").to_wire())
    emit("signal", seq=4, synthetic_time_ms=T0 + 1_800_000, target=None, disposition="NO_INCREASE",
         reason="soft_loss", account={**LONG, "equity": "880"}, intent_key=None, mark="101.5",
         risk_state=state(3, T0 + 1_800_000, "880", "2", ("soft_loss",)).to_wire())
    emit("final_account", account={**LONG, "position": "0", "equity": "999.5"},
         risk_state=state(4, T0 + 2_700_000, "999.5", "0").to_wire())
    update(bars=8, fills=1)
    return dict(control_state="completed", cleanup_confirmed=True, worker_closed=True)


class ProjectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.services = []
        self.addAsyncCleanup(self.close_services)

    async def close_services(self):
        for service in reversed(self.services):
            await service.close()

    def service(self, runner=held_runner, name="control"):
        service = control.LocalSimControlService(self.root / name, source=lambda: BUILD, runner=runner)
        service.open()
        self.services.append(service)
        return service

    async def test_state_version_domains_and_unchanged(self):
        service = self.service()
        opened = service.state_version
        self.assertGreater(opened, 0)
        self.assertEqual(service.state(opened), {"contract": "catos.simulation.v1", "version": opened,
            "instance_id": service.instance_id, "observed_at_ms": service.state(opened)["observed_at_ms"],
            "unchanged": True})
        first = await service.start(REQUEST, control.TEMPLATE)
        await asyncio.sleep(0)
        full = service.state(opened)
        self.assertFalse(full["unchanged"])
        self.assertGreater(full["version"], opened)
        self.assertEqual(set(full), {"contract", "version", "instance_id", "observed_at_ms", "unchanged",
                                     "service", "strategies", "bots", "risk", "positions", "summary",
                                     "events", "domains"})
        self.assertEqual(full["domains"]["bots"], full["version"])
        self.assertEqual(full["domains"]["events"], full["version"])
        self.assertEqual(full["domains"]["risk"], opened)
        self.assertIsNone(full["risk"])
        self.assertIsNone(full["summary"])
        self.assertEqual(full["positions"], [])
        self.assertEqual([e["kind"] for e in full["events"]["items"]], ["run_state", "run_state"])
        self.assertEqual(full["bots"][0]["state"], "running")
        self.assertEqual(full["bots"][0]["current_run_id"], first["run_id"])
        # Build drift bumps the service domain so pollers see restart_required change.
        service.source = lambda: "b" * 64
        drifted = service.state(full["version"])
        self.assertFalse(drifted["unchanged"])
        self.assertTrue(drifted["service"]["restart_required"])
        self.assertEqual(drifted["domains"]["service"], drifted["version"])
        self.assertEqual(drifted["domains"]["bots"], full["version"])

    async def test_strategy_and_bot_static_fields_are_registered_constants(self):
        service = self.service()
        [entry] = service.strategies()["items"]
        self.assertEqual((entry["strategy_id"], entry["version"], entry["allowed_modes"], entry["kind"]),
                         ("sma-trend", "sma-parameters-v1", ["local"], "registered_python_module"))
        self.assertEqual(entry["defaults"], {"parameters": {"period": 2, "quantity": "2"}, "warmup_bars": 2})
        self.assertNotIn("source", entry)
        bot = service.bot(catalog.BOT_ID)
        self.assertEqual((bot["bot_id"], bot["mode"], bot["inst_id"], bot["symbol"], bot["timeframe_ms"]),
                         ("sim-control-sma", "local", "BTC-USDT-SWAP", "BTC-USDT-SWAP", 900000))
        self.assertEqual(bot["contract"]["base_per_contract"], "0.01")
        self.assertEqual((bot["state"], bot["current_run_id"], bot["equity"], bot["ownership_retained"]),
                         ("stopped", None, None, False))
        self.assertEqual(bot["created_at_ms"], service.started_at_ms)
        with self.assertRaisesRegex(control.ControlError, "bot_not_found"):
            service.bot("other-bot")
        with self.assertRaisesRegex(control.ControlError, "invalid_bot_id"):
            service.bot("bad id!")

    async def test_mid_run_account_fill_override_risk_positions_and_summary(self):
        service = self.service(scripted_runner)
        first = await service.start(REQUEST, control.TEMPLATE)
        await asyncio.sleep(0)
        bot = service.bot(catalog.BOT_ID)
        self.assertEqual((bot["state"], bot["worker_pid"], bot["bars"], bot["fills"]), ("running", 4242, 1, 1))
        # The fill in the same bar overrides position/fees/equity of the pre-decision view.
        self.assertEqual((bot["account_source"], bot["position"], bot["fees"], bot["equity"],
                          bot["average_entry"]), ("signal_fill", "2", "0.1", "1003.21", "0"))
        self.assertEqual((bot["mark"], bot["last_disposition"], bot["last_reason"], bot["ownership_retained"]),
                         ("101.5", "RESERVED_SIMULATION", "sma_cross_up", False))
        snapshot = service.risk()
        self.assertEqual((snapshot["run_id"], snapshot["mode"], snapshot["health"], snapshot["reasons"]),
                         (first["run_id"], "RUN", "HEALTHY", []))
        self.assertEqual(snapshot["limits"], {"leverage": "3.0", "symbol_share": "0.50",
                                              "soft_loss": "0.10", "hard_loss": "0.20"})
        self.assertEqual(snapshot["basis"]["period_start_ms"], DAY * risk.DAY_MS - risk.TAIPEI_OFFSET_MS)
        self.assertEqual(snapshot["basis"]["equity"], "1000")
        self.assertNotIn("basis", snapshot["snapshot"])
        derived = snapshot["derived"]
        self.assertEqual((derived["period_pnl"], derived["period_pnl_ratio"], derived["exposure_budget"],
                          derived["symbol_budget"], derived["can_increase"], derived["status"]),
                         ("0", "0", "3000.0", "1500.000", True, "normal"))
        # Decimal strings keep their scale; the flat pre-decision snapshot has zero exposure.
        self.assertEqual((Decimal(derived["notional"]), Decimal(derived["effective_leverage"])), (0, 0))
        for value in (derived["period_pnl"], snapshot["snapshot"]["equity"], bot["equity"]):
            self.assertIsInstance(value, str)
            Decimal(value)
        [position] = service.positions()["items"]
        self.assertEqual((position["position"], position["mark"], position["notional"], position["verified"],
                          position["protection"], position["liquidation_price"]),
                         ("2", "101.5", "2.030", True, None, None))
        summary = service.summary()
        self.assertEqual((summary["equity"], summary["running_bots"], summary["total_bots"],
                          summary["leverage_limit"], summary["risk_status"], summary["basis_equity"]),
                         ("1003.21", 1, 1, "3.0", "normal", "1000"))
        self.assertEqual(summary["invariants"]["fixed_tag"], "41cb53c54d6dABDE")
        await service.stop(first["run_id"], STOP)
        await service.task
        bot = service.bot(catalog.BOT_ID)
        self.assertEqual((bot["state"], bot["ownership_retained"], bot["active"]), ("stopped", True, False))
        self.assertEqual(len(service.positions()["items"]), 1)
        self.assertEqual(service.summary()["running_bots"], 0)

    async def test_final_account_and_soft_latch_projection(self):
        service = self.service(completing_runner)
        first = await service.start(REQUEST, control.TEMPLATE)
        await service.task
        bot = service.bot(catalog.BOT_ID)
        self.assertEqual((bot["state"], bot["account_source"], bot["position"], bot["equity"],
                          bot["ownership_retained"], bot["last_disposition"]),
                         ("completed", "final_account", "0", "999.5", False, "NO_INCREASE"))
        self.assertEqual(service.positions()["items"], [])
        snapshot = service.risk()
        self.assertEqual((snapshot["seq"], snapshot["mode"], snapshot["derived"]["status"],
                          snapshot["derived"]["period_pnl"], snapshot["derived"]["period_pnl_ratio"]),
                         (4, "RUN", "normal", "-0.5", "-0.0005"))
        levels = {(e["kind"], e["payload"].get("seq")): (e["level"], e["category"])
                  for e in service.events(0, 50)["items"]}
        self.assertEqual(levels[("signal", 3)], ("INFO", "WORKER"))
        self.assertEqual(levels[("signal", 4)], ("WARN", "WORKER"))
        self.assertEqual(levels[("final_account", None)], ("INFO", "RISK"))
        self.assertEqual(levels[("run_state", None)], ("INFO", "SYSTEM"))
        # A soft latch on the latest observation maps to soft_latch and blocks increase.
        latched = catalog.risk_projection(service.runs[first["run_id"]],
                                          state(5, T0, "880", "2", ("soft_loss",)).to_wire(),
                                          service.contract(), service.limits)
        self.assertEqual((latched["derived"]["status"], latched["derived"]["can_increase"],
                          latched["mode"], latched["reasons"]), ("soft_latch", False, "NO_INCREASE", ["soft_loss"]))
        with localcontext(research._CONTEXT):
            self.assertEqual(latched["derived"]["effective_leverage"],
                             str(Decimal("2.030") / Decimal("880")))

    async def test_events_cursor_pagination_omitted_and_restart_continuity(self):
        service = self.service(scripted_runner)
        first = await service.start(REQUEST, control.TEMPLATE)
        await asyncio.sleep(0)
        await service.stop(first["run_id"], STOP)
        await service.task
        everything = service.events(0, 200)
        kinds = [e["kind"] for e in everything["items"]]
        self.assertEqual(kinds, ["run_state", "run_state", "warmup", "day_basis", "signal", "fill",
                                 "stop_requested", "run_state", "run_state"])
        seqs = [e["seq"] for e in everything["items"]]
        self.assertEqual(seqs, list(range(seqs[0], seqs[0] + len(seqs))))
        self.assertEqual((everything["next_since"], everything["more"], everything["omitted"]), (seqs[-1], False, 0))
        page = service.events(seqs[1], 3)
        self.assertEqual(([e["seq"] for e in page["items"]], page["more"], page["next_since"]),
                         (seqs[2:5], True, seqs[4]))
        self.assertEqual(service.events(seqs[-1], 10)["items"], [])
        fill = next(e for e in everything["items"] if e["kind"] == "fill")
        self.assertEqual((fill["run_id"], fill["bot_id"], fill["synthetic_time_ms"], fill["category"]),
                         (first["run_id"], "sim-control-sma", T0 + 900_000, "ORDER"))
        self.assertEqual(set(fill["payload"]), {"seq", "synthetic_time_ms", "request", "fill", "position",
                                                "fees", "equity", "state"})
        self.assertIsInstance(fill["wall_time_ms"], int)
        for event in service.runs[first["run_id"]]["events"]:
            self.assertIn("wall_time", event)
        for invalid in ((-1, 10), ("0", 10), (0, 0), (0, 201), (0, "5")):
            with self.assertRaises(control.ControlError):
                service.events(*invalid)
        # Ring buffer overflow is reported as omitted, never as a deleted cursor range.
        for i in range(control.MAX_EVENTS):
            service._emit(first["run_id"], "test", seq=i)
        self.assertEqual(service.events(0, 200)["omitted"], len(kinds) - 5)
        await service.close()
        new = self.service(name="control")
        self.assertEqual(new.seq, service.seq)
        self.assertEqual([e["seq"] for e in new.events(0, 200)["items"]],
                         [e["seq"] for e in service.events(0, 200)["items"]])
        other = await new.start(OTHER, control.TEMPLATE)
        await asyncio.sleep(0)
        newest = new.events(service.seq, 10)["items"]
        self.assertEqual([(e["kind"], e["run_id"]) for e in newest],
                         [("run_state", other["run_id"]), ("run_state", other["run_id"])])
        self.assertGreater(newest[0]["seq"], service.seq)

    async def test_recovery_and_legacy_records_project_without_rewriting_evidence(self):
        service = self.service()
        first = await service.start(REQUEST, control.TEMPLATE)
        await service.stop(first["run_id"], STOP)
        await service.task
        await service.close()
        path = service.root / "control.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        run = value["runs"][first["run_id"]]
        run.pop("lifecycle")
        run["events"] = [{"kind": "signal", "wall_time": run["created_at"], "seq": 3, "account": LONG,
                          "disposition": "NO_CHANGE", "reason": None}]
        run["last_signal"] = run["events"][0]
        run.update(control_state="running", cleanup_confirmed=False)
        path.write_text(json.dumps(value), encoding="utf-8")
        new = self.service()
        self.assertIsNone(new.unavailable)
        bot = new.bot(catalog.BOT_ID)
        self.assertEqual((bot["state"], bot["position"], bot["account_source"], bot["ownership_retained"]),
                         ("recovery_required", "2", "signal", False))
        events = new.events(0, 50)
        self.assertEqual(([(e["kind"], e["level"]) for e in events["items"]], events["omitted"]),
                         ([("run_state", "ERROR")], 1))
        self.assertIsNone(new.risk())
        self.assertEqual(new.positions()["items"][0]["mark"], None)
        self.assertEqual(new.snapshot(first["run_id"])["events"], run["events"])

    async def test_unavailable_blocks_state_risk_positions_only(self):
        broken = self.root / "broken"
        broken.mkdir()
        (broken / "control.json").write_text("broken", encoding="utf-8")
        service = control.LocalSimControlService(broken, source=lambda: BUILD, runner=held_runner)
        service.open()
        self.services.append(service)
        for method in (service.state, service.risk, service.positions):
            with self.assertRaisesRegex(control.ControlError, "simulation_metadata_unavailable"):
                method()
        self.assertEqual(service.bots()["items"][0]["state"], "stopped")
        self.assertEqual(service.events()["items"], [])
        self.assertEqual(len(service.strategies()["items"]), 1)


class RealRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        self.lock_patch.start()
        self.addCleanup(self.lock_patch.stop)
        self.service = control.LocalSimControlService(self.root / "runs")
        self.service.open()
        self.addAsyncCleanup(self.service.close)

    async def test_signal_events_carry_mark_and_risk_state_and_projection_matches_final_account(self):
        with patch.object(runner, "INTERVAL_SECONDS", 0):
            first = await self.service.start(REQUEST, control.TEMPLATE)
            await self.service.task
        status = self.service.snapshot(first["run_id"])
        self.assertEqual(status["control_state"], "completed", status)
        signals = [e for e in status["events"] if e["kind"] == "signal"]
        self.assertEqual(len(signals), 8)
        for event in signals:
            Decimal(event["mark"])
            self.assertEqual(event["risk_state"]["mode"], "RUN")
            self.assertEqual(event["risk_state"]["snapshot"]["mark"], event["mark"])
            self.assertEqual(event["risk_state"]["basis"]["day"], risk.taipei_day(event["synthetic_time_ms"]))
        # The case starts 22:00 Taipei; the first basis is the synthetic 1000 midnight fixture
        # and the crossing into the next day rebases to the equity observed at that midnight.
        self.assertEqual(signals[0]["risk_state"]["basis"]["equity"], "1000")
        final = next(e for e in status["events"] if e["kind"] == "final_account")
        bot = self.service.bot(catalog.BOT_ID)
        self.assertEqual((bot["account_source"], bot["equity"], bot["fees"], bot["position"]),
                         ("final_account", "999.91375990", "0.00404010", final["account"]["position"]))
        snapshot = self.service.risk()
        wire = final["risk_state"]
        with localcontext(research._CONTEXT):
            pnl = (Decimal(wire["snapshot"]["equity"]) - Decimal(wire["basis"]["equity"])
                   - Decimal(wire["snapshot"]["external_net"]))
            ratio = pnl / Decimal(wire["basis"]["equity"])
        self.assertEqual((snapshot["derived"]["status"], snapshot["basis"]["equity"], snapshot["basis"]["day"],
                          snapshot["derived"]["period_pnl"], snapshot["derived"]["period_pnl_ratio"]),
                         ("normal", wire["basis"]["equity"], wire["basis"]["day"], str(pnl), str(ratio)))
        # The risk observation precedes the last bar's decision/fill, so it lags the
        # final durable account by that fill; the DTO reports the observation as-is.
        self.assertEqual(snapshot["snapshot"]["equity"], wire["snapshot"]["equity"])
        self.assertNotEqual(snapshot["snapshot"]["equity"], bot["equity"])
        positions = self.service.positions()["items"]
        self.assertEqual(len(positions), 0 if Decimal(final["account"]["position"]) == 0 else 1)
        state = self.service.state()
        self.assertEqual(state["summary"]["equity"], "999.91375990")
        self.assertEqual(state["events"]["items"][-1]["kind"], "run_state")
        self.assertEqual(state["events"]["items"][-1]["payload"]["state"], "completed")


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def app(self, runner=held_runner):
        app = create_app(output_dir=self.root / "research", market_db=self.root / "missing.sqlite",
                         evidence_root=self.root / "r4", simulation_root=self.root / "simulation")
        app.state.simulation.runner = runner
        return app

    def headers(self, client):
        value = client.get(PREFIX + "/version").json()
        return {"X-CatOS-Build": value["build_id"], "X-CatOS-Instance": value["instance_id"]}

    def start_bot(self, client, headers, **body):
        return client.post(PREFIX + "/bots/start",
                           json={"request_id": REQUEST, "bot_id": catalog.BOT_ID, **body}, headers=headers)

    def test_read_routes_shapes_headers_and_decimal_strings(self):
        with TestClient(self.app(scripted_runner), base_url="http://127.0.0.1") as client:
            headers = self.headers(client)
            self.assertEqual(client.get(PREFIX + "/risk").json(), None)
            response = self.start_bot(client, headers)
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(set(response.json()), {"run", "bot", "version"})
            run_id = response.json()["run"]["run_id"]
            for path in ("/state", "/strategies", "/bots", "/bots/" + catalog.BOT_ID, "/risk",
                         "/positions", "/events", "/events?since=0&limit=5", "/state?since_version=0"):
                reply = client.get(PREFIX + path)
                self.assertEqual(reply.status_code, 200, path)
                self.assertEqual(reply.headers["X-CatOS-Instance"], headers["X-CatOS-Instance"])
                self.assertIn("no-store", reply.headers["Cache-Control"])
            state = client.get(PREFIX + "/state").json()
            self.assertEqual(state["service"], client.get(PREFIX + "/version").json())
            self.assertEqual(state["bots"][0]["current_run_id"], run_id)
            self.assertEqual(state["risk"]["derived"]["exposure_budget"], "3000.0")
            self.assertEqual(state["positions"][0]["notional"], "2.030")
            self.assertEqual(state["summary"]["equity"], "1003.21")
            self.assertIsInstance(state["summary"]["equity"], str)
            unchanged = client.get(PREFIX + f"/state?since_version={state['version']}").json()
            self.assertEqual((unchanged["unchanged"], unchanged["version"]), (True, state["version"]))
            events = client.get(PREFIX + "/events?limit=2").json()
            self.assertEqual((len(events["items"]), events["more"]), (2, True))
            self.assertEqual(client.get(PREFIX + "/bots/" + catalog.BOT_ID).json()["bot_id"], catalog.BOT_ID)
            self.assertEqual(client.post(PREFIX + f"/runs/{run_id}/stop", json={"request_id": STOP},
                                         headers=headers).status_code, 202)

    def test_host_and_mode_guards_return_403(self):
        with TestClient(self.app(), base_url="http://127.0.0.1") as client:
            headers = self.headers(client)
            external = client.get(PREFIX + "/state", headers={"Host": "external.invalid"})
            self.assertEqual((external.status_code, external.json()), (403, {"detail": "simulation_requires_127_0_0_1"}))
            for path in ("/bots/demo", "/bots/live", "/bots/LIVE", "/demo/state", "/state?mode=demo",
                         "/events?live=1", "/bots/start?mode=live"):
                reply = client.get(PREFIX + path)
                self.assertEqual((reply.status_code, reply.json()), (403, {"detail": "mode_not_available"}), path)
            for mode in ("demo", "live"):
                reply = self.start_bot(client, headers, mode=mode)
                self.assertEqual((reply.status_code, reply.json()), (403, {"detail": "mode_not_available"}))
            self.assertEqual(self.start_bot(client, headers, mode="local").status_code, 202)
            self.assertEqual(client.get(PREFIX + "/bots").json()["items"][0]["mode"], "local")

    def test_bots_start_idempotent_conflicts_and_lookup_errors(self):
        with TestClient(self.app(), base_url="http://127.0.0.1") as client:
            headers = self.headers(client)
            self.assertEqual(self.start_bot(client, {}).status_code, 409)
            self.assertEqual(self.start_bot(client, headers, bot_id="other-bot").status_code, 404)
            self.assertEqual(self.start_bot(client, headers, bot_id="bad id!").status_code, 422)
            self.assertEqual(client.post(PREFIX + "/bots/start", json={"request_id": REQUEST},
                                         headers=headers).status_code, 422)
            self.assertEqual(self.start_bot(client, headers, extra=1).status_code, 422)
            first = self.start_bot(client, headers)
            self.assertEqual(first.status_code, 202, first.text)
            run_id = first.json()["run"]["run_id"]
            replay = self.start_bot(client, headers)
            self.assertEqual((replay.status_code, replay.json()["run"]["run_id"]), (202, run_id))
            legacy = client.post(PREFIX + "/start", json={"request_id": REQUEST, "template_id": control.TEMPLATE},
                                 headers=headers)
            self.assertEqual((legacy.status_code, legacy.json()["run_id"]), (202, run_id))
            conflict = client.post(PREFIX + "/start", json={"request_id": REQUEST, "template_id": "other"},
                                   headers=headers)
            self.assertEqual((conflict.status_code, conflict.json()), (409, {"detail": "request_id_conflict"}))
            occupied = self.start_bot(client, headers, request_id=OTHER)
            self.assertEqual((occupied.status_code, occupied.json()), (409, {"detail": "simulation_slot_occupied"}))
            self.assertEqual(len(client.get(PREFIX + "/runs").json()["items"]), 1)
            self.assertEqual(client.post(PREFIX + f"/runs/{run_id}/stop", json={"request_id": STOP},
                                         headers=headers).status_code, 202)

    def test_events_query_validation(self):
        with TestClient(self.app(), base_url="http://127.0.0.1") as client:
            for path, code in (("/events?since=-1", "invalid_since"), ("/events?since=x", "invalid_since"),
                               ("/events?limit=0", "invalid_limit"), ("/events?limit=201", "invalid_limit"),
                               ("/events?limit=1.5", "invalid_limit"), ("/state?since_version=x", "invalid_since_version")):
                reply = client.get(PREFIX + path)
                self.assertEqual((reply.status_code, reply.json()), (422, {"detail": code}), path)
            self.assertEqual(client.get(PREFIX + "/events?since=0&limit=200").status_code, 200)

    def test_unavailable_control_returns_503_for_state_risk_positions_only(self):
        app = self.app()
        (self.root / "simulation").mkdir()
        (self.root / "simulation" / "control.json").write_text("broken", encoding="utf-8")
        with TestClient(app, base_url="http://127.0.0.1") as client:
            for path in ("/state", "/risk", "/positions"):
                reply = client.get(PREFIX + path)
                self.assertEqual((reply.status_code, reply.json()), (503, {"detail": "simulation_metadata_unavailable"}), path)
            for path in ("/version", "/runs", "/strategies", "/bots", "/bots/" + catalog.BOT_ID, "/events"):
                self.assertEqual(client.get(PREFIX + path).status_code, 200, path)
            self.assertEqual(self.start_bot(client, self.headers(client)).status_code, 503)

    def test_existing_routes_keep_their_contract(self):
        with TestClient(self.app(), base_url="http://127.0.0.1") as client:
            headers = self.headers(client)
            version = client.get(PREFIX + "/version").json()
            self.assertEqual(set(version), {"contract", "mode", "build_id", "current_build_id", "restart_required",
                                            "instance_id", "slot", "active_run_id", "capabilities",
                                            "unavailable_reason", "config"})
            started = client.post(PREFIX + "/start", json={"request_id": REQUEST, "template_id": control.TEMPLATE},
                                  headers=headers)
            self.assertEqual(started.status_code, 202)
            run = client.get(PREFIX + "/runs/" + started.json()["run_id"]).json()
            self.assertTrue({"run_id", "request_id", "config", "build_id", "instance_id", "created_at",
                             "control_state", "cleanup_confirmed", "stop_requested", "stop_requested_at",
                             "bars", "warmup_bars", "fills", "events", "events_omitted", "error",
                             "finished_at", "worker_closed", "still_finishing"} <= set(run))
            self.assertNotIn("stop_commands", run)
            self.assertEqual(run["events"], [])
            self.assertEqual([e["kind"] for e in run["lifecycle"]], ["run_state", "run_state"])
            self.assertEqual(client.get(PREFIX + "/runs").json()["items"][0]["run_id"], run["run_id"])
            self.assertEqual(client.get(PREFIX + "/runs/" + "f" * 32).status_code, 404)
            self.assertEqual(client.post(PREFIX + "/runs/" + run["run_id"] + "/stop", json={"request_id": STOP},
                                         headers=headers).status_code, 202)


if __name__ == "__main__":
    unittest.main()
