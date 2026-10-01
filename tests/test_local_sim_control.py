"""W2 command durability, event boundaries and isolated synthetic accounting."""

import asyncio
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from catos import account_lock
from catos import local_sim_control as control
from catos import local_sim_control_runner as runner
from catos.local_sim_control_api import PREFIX
from catos.supervisor import LocalSupervisor
from catos.workspace_api import create_app

BUILD = "a" * 64
REQUEST = "a" * 32
STOP = "b" * 32


async def held_runner(directory, run_id, stop, emit, update, source_ok):
    update(control_state="running")
    await stop.wait()
    return dict(control_state="stopped", cleanup_confirmed=True, worker_closed=True)


class ControlTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.services = []
        self.addAsyncCleanup(self.close_services)

    async def close_services(self):
        for service in reversed(self.services):
            await service.close()

    def service(self, **kwargs):
        service = control.LocalSimControlService(self.root / "control", source=lambda: BUILD,
            runner=kwargs.pop("runner", held_runner), **kwargs)
        service.open()
        self.services.append(service)
        return service

    async def start(self, service, request=REQUEST):
        return await service.start(request, control.TEMPLATE)

    async def test_concurrent_same_id_is_one_task_and_other_request_conflicts(self):
        service = self.service()
        first, retry = await asyncio.gather(self.start(service), self.start(service))
        self.assertEqual(first["run_id"], retry["run_id"])
        self.assertEqual(len(service.runs), 1)
        with self.assertRaisesRegex(control.ControlError, "slot_occupied"):
            await self.start(service, "c" * 32)
        with self.assertRaisesRegex(control.ControlError, "request_id_conflict"):
            await service.start(REQUEST, "different-template")
        await service.stop(first["run_id"], STOP)
        await service.task
        self.assertEqual(service.snapshot(first["run_id"])["control_state"], "stopped")

    async def test_stop_starting_then_terminal_and_cross_operation_bindings(self):
        service = self.service()
        first = await self.start(service)
        # No yield between scheduling start and stop: the task has not begun.
        stopped = await service.stop(first["run_id"], STOP)
        self.assertEqual(stopped["control_state"], "stopping")
        await service.task
        same = await service.stop(first["run_id"], STOP)
        self.assertEqual(same["control_state"], "stopped")
        terminal = await service.stop(first["run_id"], "c" * 32)
        self.assertEqual(terminal["control_state"], "stopped")
        with self.assertRaisesRegex(control.ControlError, "request_id_conflict"):
            await self.start(service, STOP)
        other = await self.start(service, "d" * 32)
        with self.assertRaisesRegex(control.ControlError, "request_id_conflict"):
            await service.stop(other["run_id"], STOP)

    async def test_completed_start_binding_survives_new_service(self):
        service = self.service()
        first = await self.start(service)
        await service.stop(first["run_id"], STOP)
        await service.task
        await service.close()
        new = self.service()
        replay = await self.start(new)
        self.assertEqual((replay["run_id"], replay["control_state"]), (first["run_id"], "stopped"))
        self.assertIsNone(new.task)
        self.assertNotEqual(service.instance_id, new.instance_id)
        self.assertEqual((await new.stop(first["run_id"], STOP))["control_state"], "stopped")

    async def test_interrupted_and_uncertain_cleanup_block_restart(self):
        for state in ("starting", "running", "stopping", "failed"):
            with self.subTest(state=state):
                root = self.root / state
                service = control.LocalSimControlService(root, runner=held_runner, source=lambda: BUILD)
                service.open()
                first = await self.start(service)
                await service.stop(first["run_id"], STOP)
                await service.task
                runs = service.runs.copy()
                runs[first["run_id"]] = {**runs[first["run_id"]], "control_state": state,
                                         "cleanup_confirmed": False}
                service._save(runs)
                await service.close()
                new = control.LocalSimControlService(root, runner=held_runner, source=lambda: BUILD)
                new.open()
                self.services.append(new)
                replay = await self.start(new)
                self.assertEqual(replay["control_state"], "recovery_required")
                with self.assertRaisesRegex(control.ControlError, "slot_occupied"):
                    await self.start(new, "c" * 32)
                self.assertIsNone(new.task)

    async def test_lock_competition_does_not_take_owner_or_block_other_features(self):
        owner = self.service()
        other = self.service()
        self.assertEqual(other.version()["slot"], "unavailable")
        with self.assertRaisesRegex(control.ControlError, "output_in_use"):
            await self.start(other)
        self.assertTrue(owner.version()["capabilities"]["start"])
        await owner.close()
        third = self.service()
        self.assertTrue(third.version()["capabilities"]["start"])

    async def test_write_failure_never_schedules_task_and_pending_blocks_restart(self):
        service = self.service()
        with patch("catos.local_sim_control.os.fsync", side_effect=OSError("injected")):
            with self.assertRaises(control.ControlError):
                await self.start(service)
        self.assertIsNone(service.task)
        self.assertTrue((service.root / "control.pending").exists())
        self.assertEqual(service.version()["slot"], "unavailable")
        await service.close()
        new = self.service()
        self.assertEqual(new.version()["slot"], "unavailable")
        with self.assertRaises(control.ControlError):
            await self.start(new)

    async def test_metadata_replace_failure_blocks_commands_even_if_write_may_have_landed(self):
        service = self.service()
        original = Path.replace

        def uncertain(path, target):
            original(path, target)
            raise OSError("lost_confirmation")

        with patch.object(Path, "replace", uncertain):
            with self.assertRaises(control.ControlError):
                await self.start(service)
        self.assertIsNone(service.task)
        await service.close()
        new = self.service()
        self.assertEqual((await self.start(new))["control_state"], "recovery_required")
        self.assertIsNone(new.task)

    async def test_stop_write_fault_signals_runner_and_shutdown_drains_without_false_terminal(self):
        service = self.service()
        first = await self.start(service)
        await asyncio.sleep(0)
        with patch("catos.local_sim_control.os.fsync", side_effect=OSError("injected_stop")):
            with self.assertRaises(control.ControlError):
                await service.stop(first["run_id"], STOP)
        self.assertTrue(service.stop_event.is_set())
        await service.close()
        self.assertTrue(service.task.done())
        self.assertEqual(service.version()["slot"], "unavailable")
        self.assertFalse(service.runs[first["run_id"]]["cleanup_confirmed"])
        self.assertTrue((service.root / "control.pending").exists())

    async def test_source_unreadable_does_not_crash_service_start(self):
        with patch("catos.local_sim_control.build_id", side_effect=OSError("source")):
            def unreadable():
                raise OSError("source")
            service = control.LocalSimControlService(self.root / "absent", source=unreadable)
            service.open()
            self.services.append(service)
            self.assertEqual(service.version()["slot"], "unavailable")
            self.assertFalse(service.version()["capabilities"]["start"])

    async def test_corrupt_metadata_and_untracked_directory_fail_closed(self):
        for name, content in (("bad", b'{"contract":broken}'),
                              ("duplicate", b'{"runs":{},"runs":{}}'),
                              ("oversize", b" " * (control.MAX_METADATA + 1))):
            root = self.root / name
            root.mkdir()
            (root / "control.json").write_bytes(content)
            service = control.LocalSimControlService(root, source=lambda: BUILD)
            service.open()
            self.services.append(service)
            self.assertEqual(service.version()["slot"], "unavailable")
        service = self.service()
        (service.root / ("f" * 32)).mkdir()
        await service.close()
        new = self.service()
        self.assertEqual(new.version()["slot"], "unavailable")

    async def test_cleanup_uncertain_keeps_slot_blocked(self):
        async def uncertain(*args):
            return dict(control_state="failed", cleanup_confirmed=False, error="close_unconfirmed")
        service = self.service(runner=uncertain)
        first = await self.start(service)
        await service.task
        state = service.snapshot(first["run_id"])
        self.assertEqual(state["control_state"], "recovery_required")
        self.assertFalse(state["cleanup_confirmed"])
        with self.assertRaises(control.ControlError):
            await self.start(service, "c" * 32)

    async def test_schedule_failure_is_durable_without_untracked_task(self):
        service = self.service()
        with patch("catos.local_sim_control.asyncio.create_task", side_effect=RuntimeError("schedule")):
            with self.assertRaisesRegex(control.ControlError, "task_schedule_failed"):
                await self.start(service)
        self.assertIsNone(service.task)
        replay = await self.start(service)
        self.assertEqual(replay["control_state"], "failed")
        self.assertTrue(replay["cleanup_confirmed"])

    async def test_missing_run_fields_and_invalid_timestamps_fail_closed(self):
        service = self.service()
        first = await self.start(service)
        await service.stop(first["run_id"], STOP)
        await service.task
        await service.close()
        path = service.root / "control.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for change in ({"created_at": "bad"}, {"bars": 0.5}, {"stop_requested_at": None, "control_state": "stopping"}):
            value = json.loads(json.dumps(original))
            value["runs"][first["run_id"]].update(change)
            path.write_text(json.dumps(value), encoding="utf-8")
            new = self.service()
            self.assertEqual(new.version()["slot"], "unavailable")
            await new.close()

    async def test_stop_waits_for_inflight_event_and_close_without_cancellation(self):
        entered, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def inflight(directory, run_id, stop, emit, update, source_ok):
            update(control_state="running")
            entered.set()
            await release.wait()
            emit("fill", fill={"quantity": "2", "price": "102.03", "fee": "0.00102030"})
            finished.set()
            self.assertTrue(stop.is_set())
            return dict(control_state="stopped", cleanup_confirmed=True)

        service = self.service(runner=inflight)
        first = await self.start(service)
        await entered.wait()
        await service.stop(first["run_id"], STOP)
        shutdown = asyncio.create_task(service.close())
        await asyncio.sleep(0)
        self.assertFalse(shutdown.done())
        self.assertFalse(finished.is_set())
        service._update(first["run_id"], stop_requested_at=(
            datetime.now(timezone.utc) - timedelta(seconds=6)).isoformat())
        self.assertTrue(service.snapshot(first["run_id"])["still_finishing"])
        self.assertEqual(service.snapshot(first["run_id"])["control_state"], "stopping")
        release.set()
        await shutdown
        self.assertEqual(len(service.snapshot(first["run_id"])["events"]), 1)
        self.assertTrue(finished.is_set())

    async def test_source_drift_blocks_new_start_but_accepts_stop(self):
        service = self.service()
        first = await self.start(service)
        service.source = lambda: "b" * 64
        self.assertTrue(service.version()["restart_required"])
        await service.stop(first["run_id"], STOP)
        await service.task
        with self.assertRaisesRegex(control.ControlError, "source_changed"):
            await self.start(service, "c" * 32)
        # Replaying the original command cannot create a task even after drift.
        self.assertEqual((await self.start(service))["run_id"], first["run_id"])

    async def test_event_and_run_limits_do_not_delete_old_records(self):
        service = self.service()
        first = await self.start(service)
        await service.stop(first["run_id"], STOP)
        await service.task
        for i in range(control.MAX_EVENTS + 3):
            service._emit(first["run_id"], "test", seq=i)
        snap = service.snapshot(first["run_id"])
        self.assertEqual((len(snap["events"]), snap["events_omitted"]), (control.MAX_EVENTS, 3))
        with patch.object(control, "MAX_RUNS", 1):
            with self.assertRaisesRegex(control.ControlError, "run_limit"):
                await self.start(service, "c" * 32)
        self.assertEqual(len(service.runs), 1)


class RunnerTests(unittest.IsolatedAsyncioTestCase):
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

    async def launch(self):
        first = await self.service.start(REQUEST, control.TEMPLATE)
        return first["run_id"]

    async def test_full_case_decimal_tag_single_writer_warmup_and_worker_exit(self):
        writers, processes = set(), []
        original_io = LocalSupervisor._io
        original_close = LocalSupervisor.close

        async def tracked_io(supervisor, function, *args, **kwargs):
            def wrapped():
                writers.add(threading.get_ident())
                return function(*args, **kwargs)
            return await original_io(supervisor, wrapped)

        async def tracked_close(supervisor):
            if supervisor._worker is not None:
                processes.append(supervisor._worker.process)
            await original_close(supervisor)

        with patch.object(runner, "INTERVAL_SECONDS", 0), \
                patch.object(LocalSupervisor, "_io", tracked_io), \
                patch.object(LocalSupervisor, "close", tracked_close):
            run_id = await self.launch()
            await self.service.task
        status = self.service.snapshot(run_id)
        self.assertEqual(status["control_state"], "completed", status)
        self.assertEqual((status["bars"], status["warmup_bars"], status["fills"]), (8, 2, 4))
        self.assertTrue(status["cleanup_confirmed"])
        self.assertEqual(len(writers), 1)
        self.assertNotIn(threading.get_ident(), writers)
        self.assertTrue(processes and all(p.returncode is not None for p in processes))
        final = next(e for e in status["events"] if e["kind"] == "final_account")
        self.assertEqual(final["account"]["fees"], "0.00404010")
        self.assertEqual(final["account"]["equity"], "999.91375990")
        with closing(sqlite3.connect(self.service.root / run_id / "state.sqlite3")) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("SELECT count(*) FROM inputs WHERE state='COMMITTED'").fetchone()[0], 10)
            self.assertEqual(db.execute("SELECT count(*) FROM execution_fills").fetchone()[0], 4)
            self.assertEqual(db.execute("SELECT count(*) FROM reservations").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM execution_orders WHERE settled=0").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT DISTINCT typeof(quantity),typeof(price),typeof(fee) FROM execution_fills").fetchall(), [("text", "text", "text")])
            self.assertEqual(db.execute("SELECT count(*) FROM ownership").fetchone()[0], 1)
            for (payload,) in db.execute("SELECT payload_json FROM execution_orders"):
                value = json.loads(payload)
                self.assertEqual((value["tag"], value["tdMode"], value["posSide"]),
                                 ("41cb53c54d6dABDE", "cross", "net"))
        # The unique account binding remains; close must not release ownership.
        self.assertEqual(len(list((self.root / "locks").glob("*.lock"))), 1)

    async def test_real_stop_while_waiting_wakes_without_another_bar(self):
        waiting = asyncio.Event()
        original_wait = runner.wait_boundary

        async def tracked_wait(stop):
            waiting.set()
            await original_wait(stop)

        with patch.object(runner, "wait_boundary", tracked_wait), patch.object(runner, "INTERVAL_SECONDS", 30):
            run_id = await self.launch()
            await asyncio.wait_for(waiting.wait(), 5)
            await self.service.stop(run_id, STOP)
            await asyncio.wait_for(asyncio.shield(self.service.task), 5)
        status = self.service.snapshot(run_id)
        self.assertEqual((status["control_state"], status["bars"], status["warmup_bars"]), ("stopped", 0, 2))
        self.assertTrue(status["cleanup_confirmed"])

    async def test_real_stop_before_task_starts_creates_no_database(self):
        run_id = await self.launch()
        await self.service.stop(run_id, STOP)
        await self.service.task
        status = self.service.snapshot(run_id)
        self.assertEqual((status["control_state"], status["warmup_bars"]), ("stopped", 0))
        self.assertTrue(status["cleanup_confirmed"])
        self.assertFalse((self.service.root / run_id / "state.sqlite3").exists())

    async def test_real_stop_during_warmup_finishes_only_current_warmup(self):
        entered, release = asyncio.Event(), asyncio.Event()
        process_bar = LocalSupervisor.process_bar

        async def held(supervisor, seq, *args, **kwargs):
            if seq == 1:
                entered.set()
                await release.wait()
            return await process_bar(supervisor, seq, *args, **kwargs)

        with patch.object(LocalSupervisor, "process_bar", held):
            run_id = await self.launch()
            await asyncio.wait_for(entered.wait(), 5)
            await self.service.stop(run_id, STOP)
            release.set()
            await self.service.task
        status = self.service.snapshot(run_id)
        self.assertEqual((status["control_state"], status["warmup_bars"], status["bars"]), ("stopped", 1, 0))
        self.assertIsNone(next(e for e in status["events"] if e["kind"] == "warmup")["target"])

    async def test_real_stop_during_dispatch_finishes_fill_ack_and_reconcile(self):
        entered, release = asyncio.Event(), asyncio.Event()
        dispatch = LocalSupervisor.dispatch

        async def held(supervisor, *args, **kwargs):
            entered.set()
            await release.wait()
            return await dispatch(supervisor, *args, **kwargs)

        with patch.object(runner, "INTERVAL_SECONDS", 0), patch.object(LocalSupervisor, "dispatch", held):
            run_id = await self.launch()
            await asyncio.wait_for(entered.wait(), 5)
            await self.service.stop(run_id, STOP)
            self.assertEqual(self.service.snapshot(run_id)["control_state"], "stopping")
            release.set()
            await self.service.task
        status = self.service.snapshot(run_id)
        self.assertEqual((status["control_state"], status["bars"], status["fills"]), ("stopped", 1, 1))
        with closing(sqlite3.connect(self.service.root / run_id / "state.sqlite3")) as db:
            self.assertEqual(db.execute("SELECT state,settled FROM execution_orders").fetchall(), [("FILLED", 1)])
            self.assertEqual(db.execute("SELECT count(*) FROM execution_fills").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM reservations").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT position FROM ownership").fetchone()[0], "2")

    async def test_worker_failure_closes_resources_without_claiming_completion(self):
        processes = []
        process_bar = LocalSupervisor.process_bar

        async def exit_after_warmup(supervisor, seq, *args, **kwargs):
            receipt = await process_bar(supervisor, seq, *args, **kwargs)
            if seq == 2:
                process = supervisor._worker.process
                processes.append(process)
                process.kill()
                await process.wait()
            return receipt

        with patch.object(LocalSupervisor, "process_bar", exit_after_warmup), patch.object(runner, "INTERVAL_SECONDS", 0):
            run_id = await self.launch()
            await self.service.task
        status = self.service.snapshot(run_id)
        self.assertEqual(status["control_state"], "failed", status)
        self.assertTrue(status["cleanup_confirmed"])
        self.assertTrue((self.service.root / run_id / "state.sqlite3").is_file())
        self.assertTrue(processes and processes[0].returncode is not None)

    async def test_real_close_exception_does_not_release_slot(self):
        original = LocalSupervisor.close

        async def unconfirmed(supervisor):
            await original(supervisor)
            raise RuntimeError("unconfirmed_close")
        waiting = asyncio.Event()

        async def wait(stop):
            waiting.set()
            await stop.wait()
            runner.boundary(stop)

        with patch.object(LocalSupervisor, "close", unconfirmed), patch.object(runner, "wait_boundary", wait):
            run_id = await self.launch()
            await asyncio.wait_for(waiting.wait(), 5)
            await self.service.stop(run_id, STOP)
            await self.service.task
        self.assertEqual(self.service.snapshot(run_id)["control_state"], "recovery_required")
        self.assertFalse(self.service.snapshot(run_id)["cleanup_confirmed"])


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def app(self):
        app = create_app(output_dir=self.root / "research", market_db=self.root / "missing.sqlite",
                         evidence_root=self.root / "r4", simulation_root=self.root / "simulation")
        app.state.simulation.runner = held_runner
        return app

    def headers(self, client):
        value = client.get(PREFIX + "/version").json()
        return {"X-CatOS-Build": value["build_id"], "X-CatOS-Instance": value["instance_id"]}

    def submit(self, client, headers, **extra):
        return client.post(PREFIX + "/start", json={"request_id": REQUEST, "template_id": control.TEMPLATE, **extra}, headers=headers)

    def test_api_strict_contract_origin_size_instance_and_headers(self):
        with TestClient(self.app(), base_url="http://127.0.0.1") as client:
            headers = self.headers(client)
            self.assertEqual(self.submit(client, {}).status_code, 409)
            self.assertEqual(self.submit(client, {**headers, "X-CatOS-Instance": "old"}).status_code, 409)
            self.assertEqual(self.submit(client, {**headers, "X-CatOS-Build": "old"}).status_code, 409)
            self.assertEqual(self.submit(client, {**headers, "Origin": "https://external.invalid"}).status_code, 403)
            self.assertEqual(self.submit(client, {**headers, "Host": "external.invalid"}).status_code, 403)
            self.assertEqual(self.submit(client, headers, path="private").status_code, 422)
            self.assertEqual(self.submit(client, headers, request_id="A" * 32).status_code, 422)
            self.assertEqual(self.submit(client, headers, template_id="live").status_code, 422)
            self.assertEqual(client.post(PREFIX + "/start", content="x", headers=headers).status_code, 415)
            json_headers = {**headers, "Content-Type": "application/json"}
            self.assertEqual(client.post(PREFIX + "/start", content=b" " * 8193, headers=json_headers).status_code, 413)
            for body in (b'{}', b'[]', b'{"request_id":"a","request_id":"b"}', b'{"x":NaN}'):
                self.assertEqual(client.post(PREFIX + "/start", content=body, headers=json_headers).status_code, 422)
            response = self.submit(client, headers)
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(response.headers["X-CatOS-Instance"], headers["X-CatOS-Instance"])
            self.assertIn("no-store", response.headers["Cache-Control"])
            run_id = response.json()["run_id"]
            self.assertEqual(self.submit(client, headers).json()["run_id"], run_id)
            self.assertEqual(client.get(PREFIX + "/runs/" + "f" * 32).status_code, 404)
            self.assertEqual(client.get(PREFIX + "/runs/private").status_code, 422)
            self.assertEqual(client.post(PREFIX + "/runs/" + run_id + "/stop", json={"request_id": STOP}, headers=headers).status_code, 202)

    def test_get_and_http_client_teardown_leave_task_running_lifespan_shutdown_drains(self):
        app = self.app()
        with TestClient(app, base_url="http://127.0.0.1") as client:
            headers = self.headers(client)
            run_id = self.submit(client, headers).json()["run_id"]
            before = client.get(PREFIX + "/runs/" + run_id).json()
            for path in ("/", "/workspace/research", "/workspace/execution", PREFIX + "/runs"):
                self.assertEqual(client.get(path).status_code, 200)
            self.assertEqual(client.get(PREFIX + "/runs/" + run_id).json(), before)
            # Closing a transport/client (without entering another lifespan) owns no task.
            import httpx

            async def transient_client():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                             base_url="http://127.0.0.1") as temporary:
                    self.assertEqual((await temporary.get(PREFIX + "/runs/" + run_id)).status_code, 200)

            client.portal.call(transient_client)
            self.assertFalse(app.state.simulation.task.done())
            self.assertEqual(app.state.simulation.snapshot(run_id)["control_state"], "running")
        self.assertTrue(app.state.simulation.task.done())
        self.assertEqual(app.state.simulation.snapshot(run_id)["control_state"], "stopped")
        self.assertIsNone(app.state.simulation.owner)

    def test_source_drift_stop_still_works_same_instance(self):
        app = self.app()
        with TestClient(app, base_url="http://127.0.0.1") as client:
            headers = self.headers(client)
            run_id = self.submit(client, headers).json()["run_id"]
            app.state.simulation.source = lambda: "b" * 64
            self.assertTrue(client.get(PREFIX + "/version").json()["restart_required"])
            stopped = client.post(PREFIX + "/runs/" + run_id + "/stop", json={"request_id": STOP}, headers=headers)
            self.assertEqual(stopped.status_code, 202)
            response = self.submit(client, headers, request_id="c" * 32)
            self.assertEqual(response.status_code, 409)

    def test_unavailable_control_keeps_workspace_and_research_readable(self):
        app = self.app()
        (self.root / "simulation").mkdir()
        (self.root / "simulation" / "control.json").write_text("broken", encoding="utf-8")
        with TestClient(app, base_url="http://127.0.0.1") as client:
            headers = self.headers(client)
            self.assertEqual(client.get(PREFIX + "/version").json()["slot"], "unavailable")
            self.assertEqual(self.submit(client, headers).status_code, 503)
            for path in ("/", "/api/research/version", "/api/research/runs", "/api/workspace/local-sim/runs"):
                self.assertEqual(client.get(path).status_code, 200)

    def test_preview_does_not_mount_or_proxy_simulation(self):
        app = create_app(preview=True, simulation_root=self.root / "simulation")
        with TestClient(app, base_url="http://127.0.0.1:8771") as client, patch("catos.workspace_api.relay") as relay:
            self.assertEqual(client.post(PREFIX + "/start", json={}).status_code, 404)
            self.assertEqual(client.get(PREFIX + "/version").status_code, 404)
            self.assertNotIn("simulation", app.state._state)
            relay.assert_not_called()
        self.assertFalse((self.root / "simulation").exists())


if __name__ == "__main__":
    unittest.main()
