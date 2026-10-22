"""Trusted Python artifacts: real child execution, durable binding and stop ownership."""
import asyncio
from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

from catos import account_lock, ipc
from catos import local_sim_control_runner as runner
from catos.local_sim_control import ControlError, LocalSimControlService, TEMPLATE
from catos.python_strategy import CONTRACT, artifact, digest
from catos.worker_host import WorkerHost, WorkerError
from test_ipc import config, bar, account

SOURCE = '''from decimal import Decimal
class Strategy:
    def __init__(self, parameters):
        self.parameters = parameters
        self.n = 0
        self.decisions = 0
    def update_indicators(self, bar):
        self.n += 1
    @property
    def ready(self):
        return self.n >= 2
    def on_bar(self, bar, account):
        self.decisions += 1
        if self.parameters.get("hold") or self.n % 2:
            return Decimal(self.parameters["quantity"])
        return Decimal("0")
    def snapshot_state(self):
        return {"n": self.n, "decisions": self.decisions}
    def restore_state(self, state):
        self.n = state["n"]
        self.decisions = state["decisions"]
'''

def manifest(version="v1", hold=False):
    return dict(contract=CONTRACT, strategy_id="counter-python", version=version,
                name="Counter Python", description="Non-SMA short/flat counter with durable state",
                source=SOURCE, defaults={"quantity": "-1", "hold": hold}, warmup_bars=2)

def bound(value=None, parameters=None):
    value = value or manifest()
    return dict(artifact=value, artifact_hash=digest(value),
                parameters=parameters if parameters is not None else deepcopy(value["defaults"]))

def pyconfig(value=None, parameters=None):
    return replace(config(), python_strategy=bound(value, parameters))

def command():
    return uuid.uuid4().hex

class PythonWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def started(self, cfg, checkpoint=None):
        host = WorkerHost("python-bot", cfg, checkpoint=checkpoint)
        self.addAsyncCleanup(host.close)
        await host.start()
        return host

    async def test_non_sma_warmup_and_restore_exact_next_decision(self):
        cfg = pyconfig()
        host = await self.started(cfg)
        for i in range(2):
            result = await host.process_bar(bar(i))
            self.assertIsNone(result.target_position)
            self.assertEqual(result.checkpoint.strategy_state["decisions"], 0)
        result = await host.process_bar(bar(2), account(2))
        self.assertEqual(result.target_position, Decimal("-1"))
        checkpoint = ipc.Checkpoint.from_wire(host.checkpoint.to_wire(), cfg)
        expected = await host.process_bar(bar(3), account(3))
        await host.close()
        self.assertEqual(host.process.returncode, 0)
        restored = await self.started(cfg, checkpoint)
        actual = await restored.process_bar(bar(3), account(3))
        self.assertEqual(actual, expected)
        self.assertEqual(actual.target_position, Decimal("0"))
        await restored.close()
        self.assertEqual(restored.process.returncode, 0)

    async def test_checkpoint_rejects_version_source_parameters_and_bad_restore(self):
        cfg = pyconfig()
        host = await self.started(cfg)
        await host.process_bar(bar(0))
        saved = host.checkpoint
        await host.close()
        for changed in (pyconfig(manifest("v2")), pyconfig(parameters={"quantity": "-2", "hold": False}),
                        pyconfig({**manifest(), "source": SOURCE + "\n# changed\n"})):
            with self.assertRaisesRegex(ipc.ProtocolError, "mismatch"):
                WorkerHost("python-bot", changed, checkpoint=saved)
        bad = {**manifest(), "source": SOURCE.replace('self.n = state["n"]', 'self.n = state["n"] + 1')}
        bad_cfg = pyconfig(bad)
        bad_checkpoint = replace(saved, config=bad_cfg)
        with self.assertRaises(WorkerError):
            await self.started(bad_cfg, bad_checkpoint)

    async def test_python_checkpoint_commit_ack_keeps_durable_boundary(self):
        host = WorkerHost("python-bot", pyconfig(), require_commit_ack=True)
        self.addAsyncCleanup(host.close)
        await host.start()
        result = await host.process_bar(bar(0))
        self.assertEqual(host.checkpoint.event_seq, 0)
        with self.assertRaisesRegex(WorkerError, "awaits durable"):
            await host.process_bar(bar(1))
        await host.acknowledge(1)
        self.assertEqual(host.checkpoint, result.checkpoint)
        await host.close()
        self.assertEqual(host.process.returncode, 0)

    async def test_contract_rejects_float_and_intent_from_indicator(self):
        with self.assertRaisesRegex(ValueError, "no_float"):
            artifact({**manifest(), "defaults": {"quantity": 0.1}})
        bad = {**manifest(), "source": SOURCE.replace('self.n += 1', 'self.n += 1\n        return Decimal("1")')}
        host = await self.started(pyconfig(bad))
        with self.assertRaises(WorkerError):
            await host.process_bar(bar(0))
        self.assertEqual(host.checkpoint.event_seq, 0)

class LibraryAndRunTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lock_patch = patch.object(account_lock, "LOCK_DIRECTORY", self.root / "locks")
        self.lock_patch.start()
        self.addCleanup(self.lock_patch.stop)
        self.services = []
        self.addAsyncCleanup(self.close_services)

    async def close_services(self):
        for service in reversed(self.services):
            await service.close()

    def service(self, name="runs"):
        service = LocalSimControlService(self.root / name)
        service.open()
        self.assertIsNone(service.unavailable)
        self.services.append(service)
        return service

    def allocate(self, service, name="counter", value=None):
        entry = service.library.create(command(), value or manifest())
        return service.library.allocate(command(), name, entry["artifact_hash"],
                                        entry["artifact"]["defaults"], True, "local")

    async def test_immutable_versions_bot_snapshot_command_conflicts_and_modes(self):
        service = self.service()
        request = command()
        entry = service.library.create(request, manifest())
        self.assertEqual(service.library.create(request, manifest()), entry)
        with self.assertRaisesRegex(ControlError, "request_id_conflict"):
            service.library.create(request, manifest("v2"))
        with self.assertRaisesRegex(ControlError, "immutable_version"):
            service.library.create(command(), {**manifest(), "description": "changed"})
        bot = self.allocate(service)
        service.library.create(command(), manifest("v2"))
        self.assertEqual(service.library.bot("counter"), bot)
        changed_parameters = {"quantity": "-3", "hold": False}
        changed_bot = service.library.allocate(command(), "other", entry["artifact_hash"], changed_parameters, True, "local")
        changed_parameters["quantity"] = "-999"
        self.assertEqual(service.library.bot("other"), changed_bot)
        with self.assertRaisesRegex(ControlError, "immutable_bot"):
            self.allocate(service)
        for mode, trusted in (("demo", True), ("live", True), ("local", False)):
            with self.assertRaises(ControlError):
                service.library.allocate(command(), mode, entry["artifact_hash"], {}, trusted, mode)
        with self.assertRaisesRegex(ControlError, "request_id_conflict"):
            await service.start(request, bot_id="counter")
        # Parent only parses this source; executing it would immediately fail.
        service.library.create(command(), {**manifest("never-exec"), "source": 'raise RuntimeError("child_only")\n' + SOURCE})
        await service.close()
        restored = self.service()
        self.assertEqual(restored.library.bot("counter"), bot)
        self.assertEqual(restored.library.create(request, manifest()), entry)

    async def test_real_completed_and_position_stop_history_and_retained_ownership(self):
        service = self.service()
        self.allocate(service)
        request = command()
        with patch.object(runner, "INTERVAL_SECONDS", 0):
            first = await service.start(request, bot_id="counter")
            self.assertEqual((await service.start(request, bot_id="counter"))["run_id"], first["run_id"])
            await service.task
        completed = service.snapshot(first["run_id"])
        self.assertEqual(completed["control_state"], "completed", completed)
        self.assertEqual((completed["warmup_bars"], completed["bars"], completed["fills"]), (2, 8, 8))
        self.assertEqual(completed["worker_returncode"], 0)
        self.assertTrue(completed["cleanup_confirmed"])
        self.assertEqual([e["target"] for e in completed["events"] if e["kind"] == "signal"], ["-1", "0"] * 4)
        for event in completed["events"]:
            if event["kind"] == "signal":
                self.assertEqual(json.loads(event["intent_key"])[3:5],
                    ["counter-python", completed["config"]["binding"]["artifact_hash"]])
        self.assertIsNone(service.retained_run())
        with closing(sqlite3.connect(service.root / first["run_id"] / "state.sqlite3")) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("SELECT count(*) FROM inputs WHERE state='COMMITTED'").fetchone()[0], 10)
            self.assertEqual(db.execute("SELECT DISTINCT typeof(quantity),typeof(price),typeof(fee) FROM execution_fills").fetchall(), [("text", "text", "text")])
            self.assertEqual(db.execute("SELECT count(*) FROM reservations").fetchone()[0], 0)
            for (payload,) in db.execute("SELECT payload_json FROM execution_orders"):
                self.assertEqual(json.loads(payload)["tag"], "41cb53c54d6dABDE")
        self.allocate(service, "holding", manifest("hold-v1", True))
        with patch.object(runner, "INTERVAL_SECONDS", 0.05):
            second = await service.start(command(), bot_id="holding")
            async with asyncio.timeout(5):
                while service.runs[second["run_id"]]["fills"] < 1:
                    await asyncio.sleep(0.01)
            stop_id = command()
            await service.stop(second["run_id"], stop_id)
            await service.task
        stopped = service.snapshot(second["run_id"])
        self.assertEqual(stopped["control_state"], "stopped", stopped)
        self.assertEqual(stopped["worker_returncode"], 0)
        final = next(e for e in stopped["events"] if e["kind"] == "final_account")
        self.assertEqual(final["account"]["position"], "-1")
        self.assertEqual(service.version()["retained_run_id"], second["run_id"])
        self.assertFalse(service.version()["capabilities"]["start"])
        for arguments in ({"bot_id": "counter"}, {"template_id": TEMPLATE}):
            with self.assertRaisesRegex(ControlError, "retained"):
                await service.start(command(), **arguments)
        with self.assertRaisesRegex(ControlError, "request_id_conflict"):
            service.library.create(stop_id, manifest("v3"))
        await service.close()
        restored = self.service()
        self.assertEqual(restored.snapshot(first["run_id"]), completed)
        self.assertEqual(restored.snapshot(second["run_id"]), stopped)
        self.assertIsNone(restored.task)
        self.assertEqual(restored.retained_run(), second["run_id"])
        self.assertEqual((await restored.stop(second["run_id"], stop_id))["control_state"], "stopped")

    async def test_corrupt_library_and_run_bindings_fail_closed(self):
        service = self.service()
        self.allocate(service)
        await service.close()
        path = service.root / "strategy-library.json"
        value = json.loads(path.read_text())
        value["bots"]["counter"]["binding"]["parameters"]["quantity"] = "-99"
        path.write_text(json.dumps(value), encoding="utf-8")
        restored = LocalSimControlService(service.root)
        restored.open()
        self.services.append(restored)
        self.assertEqual(restored.unavailable, "simulation_metadata_unavailable")
        with self.assertRaises(ControlError):
            await restored.start(command(), bot_id="counter")

if __name__ == "__main__":
    unittest.main()
