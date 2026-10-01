"""Single event-loop control slot, durable command bindings, no ledger writes."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import uuid

from catos.local_sim_control_runner import run_case
from catos.local_sim_r4 import RUNTIME_FILES
from catos.research_catalog import DEFAULT_REQUEST, files_hash

TEMPLATE = "sma-synthetic-smoke-v1"
CONFIG = {"template_id": TEMPLATE, "bars": 8, "warmup_bars": 2,
          "interval_seconds": 1, "mode": "local-sim-synthetic",
          "research_request": deepcopy(DEFAULT_REQUEST), "candle_timeframe_ms": 900000,
          "funding": "explicit_zero", "fill_model": "next_open_with_declared_slippage",
          "stop_semantics": "complete_current_event_then_stop"}
TERMINAL = {"completed", "stopped", "failed"}
STATES = TERMINAL | {"starting", "running", "stopping", "recovery_required"}
MAX_RUNS = 100
MAX_EVENTS = 40
MAX_STOP_COMMANDS = 100
MAX_METADATA = 4_000_000
BUILD_FILES = tuple(RUNTIME_FILES) + (
    "catos/local_sim_control.py", "catos/local_sim_control_runner.py",
    "catos/local_sim_control_api.py", "catos/workspace_api.py")


def build_id():
    return files_hash(BUILD_FILES)


def now():
    return datetime.now(timezone.utc).isoformat()


def valid_id(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value) is not None


class ControlError(Exception):
    def __init__(self, code, status=503):
        super().__init__(code)
        self.status = status


def strict_json(data):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate_json_field")
            value[key] = item
        return value

    def reject(_):
        raise ValueError("invalid_json_constant")

    return json.loads(data, object_pairs_hook=pairs, parse_constant=reject)


class LocalSimControlService:
    """Methods and callbacks must run on the owning app event loop."""

    def __init__(self, output_root, *, runner=run_case, source=build_id):
        self.root = Path(output_root).resolve()
        self.runner, self.source = runner, source
        try:
            self.loaded_build = source()
        except OSError:
            self.loaded_build = "source_unavailable"
        self.instance_id = uuid.uuid4().hex
        self.runs = {}
        self.owner = None
        self.task = None
        self.stop_event = None
        self.active = None
        self.unavailable = "not_started"
        self.closing = False

    def open(self):
        if self.loaded_build == "source_unavailable":
            self.unavailable = "simulation_source_unavailable"
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            owner = (self.root / "control.lock").open("a+b")
            try:
                owner.seek(0, 2)
                if owner.tell() == 0:
                    owner.write(b"0")
                    owner.flush()
                owner.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(owner.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                owner.close()
                raise ControlError("simulation_output_in_use") from None
            self.owner = owner
            if (self.root / "control.pending").exists():
                raise ValueError("uncertain_metadata_write")
            path = self.root / "control.json"
            if path.exists():
                with path.open("rb") as stream:
                    raw = stream.read(MAX_METADATA + 1)
                if len(raw) > MAX_METADATA:
                    raise ValueError("metadata_size_limit")
                value = strict_json(raw)
                self._validate(value)
                self.runs = value["runs"]
            known = set(self.runs)
            if any(item.is_dir() and item.name not in known for item in self.root.iterdir()):
                raise ValueError("untracked_run_directory")
            if any(not (self.root / run_id).is_dir() for run_id in known):
                raise ValueError("run_directory_missing")
            recovered = deepcopy(self.runs)
            changed = False
            for run in recovered.values():
                if run["control_state"] not in TERMINAL or not run["cleanup_confirmed"]:
                    run.update(control_state="recovery_required", cleanup_confirmed=False,
                               error="interrupted_or_cleanup_unconfirmed")
                    changed = True
            self.unavailable = None
            if changed:
                self._save(recovered)
        except (OSError, ValueError, TypeError, KeyError, ControlError) as exc:
            self.unavailable = str(exc) if isinstance(exc, ControlError) else "simulation_metadata_unavailable"

    def _validate(self, value):
        if type(value) is not dict or set(value) != {"contract", "runs"} or value["contract"] != "catos.simulation.v1":
            raise ValueError("metadata_contract")
        runs = value["runs"]
        if type(runs) is not dict or len(runs) > MAX_RUNS:
            raise ValueError("run_limit")
        bindings = set()
        for run_id, run in runs.items():
            if (not valid_id(run_id) or type(run) is not dict or run["run_id"] != run_id
                    or run["config"] != CONFIG or run["control_state"] not in STATES
                    or type(run["cleanup_confirmed"]) is not bool
                    or type(run["stop_requested"]) is not bool
                    or not valid_id(run["request_id"])
                    or type(run["events"]) is not list or len(run["events"]) > MAX_EVENTS
                    or type(run["stop_commands"]) is not list or len(run["stop_commands"]) > MAX_STOP_COMMANDS
                    or type(run["build_id"]) is not str or not re.fullmatch(r"[0-9a-f]{64}", run["build_id"])):
                raise ValueError("invalid_run_metadata")
            for count, maximum in (("bars", 8), ("warmup_bars", 2), ("fills", 8),
                                   ("events_omitted", 100)):
                if type(run[count]) is not int or not 0 <= run[count] <= maximum:
                    raise ValueError("invalid_run_counts")
            if (not valid_id(run["instance_id"]) or type(run["worker_closed"]) is not bool
                    or (run["error"] is not None and type(run["error"]) is not str)
                    or any(type(event) is not dict or type(event.get("kind")) is not str
                           for event in run["events"])):
                raise ValueError("invalid_run_evidence")
            for field in ("created_at", "finished_at", "stop_requested_at"):
                stamp = run[field]
                if stamp is None and field != "created_at":
                    continue
                if type(stamp) is not str or datetime.fromisoformat(stamp).utcoffset() is None:
                    raise ValueError("invalid_timestamp")
            if run["control_state"] == "stopping" and run["stop_requested_at"] is None:
                raise ValueError("missing_stop_timestamp")
            for command in [run["request_id"], *run["stop_commands"]]:
                if not valid_id(command) or command in bindings:
                    raise ValueError("invalid_command_binding")
                bindings.add(command)

    def _save(self, runs):
        try:
            encoded = json.dumps({"contract": "catos.simulation.v1", "runs": runs},
                                 ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            if len(encoded.encode("utf-8")) > MAX_METADATA:
                raise ValueError("metadata_size_limit")
            with (self.root / "control.pending").open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(encoded + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            (self.root / "control.pending").replace(self.root / "control.json")
            self.runs = runs
        except (OSError, ValueError, TypeError):
            self.unavailable = "simulation_metadata_write_uncertain"
            if self.stop_event is not None:
                self.stop_event.set()
            raise ControlError(self.unavailable) from None

    def _ready(self):
        if self.unavailable or self.owner is None or self.closing:
            raise ControlError(self.unavailable or "simulation_service_closing")

    def current_build(self):
        try:
            return self.source()
        except OSError:
            return "source_unavailable"

    def version(self):
        current = self.current_build()
        blocked = next((r for r in self.runs.values()
                        if r["control_state"] not in TERMINAL or not r["cleanup_confirmed"]), None)
        slot = "unavailable" if self.unavailable else (blocked["control_state"] if blocked else "idle")
        return {"contract": "catos.simulation.v1", "mode": "local-sim-synthetic",
                "build_id": self.loaded_build, "current_build_id": current,
                "restart_required": current != self.loaded_build, "instance_id": self.instance_id,
                "slot": slot, "active_run_id": self.active,
                "capabilities": {"start": slot == "idle" and current == self.loaded_build and not self.closing,
                                 "stop": self.active is not None and not self.closing and not self.unavailable},
                "unavailable_reason": self.unavailable, "config": dict(CONFIG)}

    def snapshot(self, run_id):
        if not valid_id(run_id):
            raise ControlError("invalid_run_id", 422)
        if run_id not in self.runs:
            raise ControlError("run_not_found", 404)
        value = deepcopy(self.runs[run_id])
        value.pop("stop_commands")
        value["still_finishing"] = (value["control_state"] == "stopping" and
            (datetime.now(timezone.utc) - datetime.fromisoformat(value["stop_requested_at"])).total_seconds() >= 5)
        return value

    def list_runs(self):
        return {"items": [self.snapshot(run_id) for run_id in reversed(self.runs)],
                "state": "unavailable" if self.unavailable else "available",
                "issues": [self.unavailable] if self.unavailable else []}

    def _binding(self, request_id):
        for run in self.runs.values():
            if request_id == run["request_id"]:
                return "start", run["run_id"]
            if request_id in run["stop_commands"]:
                return "stop", run["run_id"]
        return None

    async def start(self, request_id, template_id):
        self._ready()
        if not valid_id(request_id) or type(template_id) is not str:
            raise ControlError("invalid_command_contract", 422)
        binding = self._binding(request_id)
        if binding:
            if binding[0] != "start" or template_id != TEMPLATE:
                raise ControlError("request_id_conflict", 409)
            return self.snapshot(binding[1])
        if template_id != TEMPLATE:
            raise ControlError("unsupported_template", 422)
        if self.current_build() != self.loaded_build:
            raise ControlError("source_changed_restart_required", 409)
        if any(r["control_state"] not in TERMINAL or not r["cleanup_confirmed"] for r in self.runs.values()):
            raise ControlError("simulation_slot_occupied", 409)
        if len(self.runs) >= MAX_RUNS:
            raise ControlError("simulation_run_limit", 409)
        run_id = uuid.uuid4().hex
        record = dict(run_id=run_id, request_id=request_id, config=dict(CONFIG),
            build_id=self.loaded_build, instance_id=self.instance_id, created_at=now(),
            control_state="starting", cleanup_confirmed=False, stop_requested=False,
            stop_requested_at=None, stop_commands=[], bars=0, warmup_bars=0, fills=0,
            events=[], events_omitted=0, error=None, finished_at=None, worker_closed=False)
        runs = deepcopy(self.runs)
        runs[run_id] = record
        try:
            (self.root / run_id).mkdir(exist_ok=False)
        except OSError:
            self.unavailable = "simulation_run_directory_uncertain"
            raise ControlError(self.unavailable) from None
        self._save(runs)
        self.active, self.stop_event = run_id, asyncio.Event()
        coroutine = self._execute(run_id)
        try:
            self.task = asyncio.create_task(coroutine, name="simulation-" + run_id)
        except Exception:
            coroutine.close()
            self.active = None
            self._update(run_id, control_state="failed", cleanup_confirmed=True,
                         worker_closed=True, error="task_schedule_failed", finished_at=now())
            raise ControlError("simulation_task_schedule_failed") from None
        return self.snapshot(run_id)

    async def stop(self, run_id, request_id):
        self._ready()
        if not valid_id(request_id):
            raise ControlError("invalid_command_contract", 422)
        self.snapshot(run_id)
        binding = self._binding(request_id)
        if binding:
            if binding != ("stop", run_id):
                raise ControlError("request_id_conflict", 409)
            return self.snapshot(run_id)
        run = self.runs[run_id]
        if len(run["stop_commands"]) >= MAX_STOP_COMMANDS:
            raise ControlError("simulation_stop_command_limit", 409)
        runs = deepcopy(self.runs)
        record = runs[run_id]
        record["stop_commands"].append(request_id)
        if record["control_state"] in {"starting", "running", "stopping"}:
            record.update(control_state="stopping", stop_requested=True,
                          stop_requested_at=record["stop_requested_at"] or now())
        self._save(runs)
        if self.active == run_id and self.stop_event is not None:
            self.stop_event.set()
        return self.snapshot(run_id)

    def _update(self, run_id, **values):
        runs = deepcopy(self.runs)
        record = runs[run_id]
        if record["control_state"] == "stopping" and values.get("control_state") == "running":
            values.pop("control_state")
        record.update(values)
        self._save(runs)

    def _emit(self, run_id, kind, **values):
        runs = deepcopy(self.runs)
        record = runs[run_id]
        event = {"kind": kind, "wall_time": now(), **values}
        record["events"].append(event)
        if len(record["events"]) > MAX_EVENTS:
            record["events"].pop(0)
            record["events_omitted"] += 1
        if kind in ("signal", "fill"):
            record["last_" + kind] = event
        self._save(runs)

    async def _execute(self, run_id):
        try:
            result = await self.runner(self.root / run_id, run_id, self.stop_event,
                lambda kind, **values: self._emit(run_id, kind, **values),
                lambda **values: self._update(run_id, **values),
                lambda: self.current_build() == self.loaded_build)
            if result.get("control_state") not in TERMINAL | {"recovery_required"} or result.get("cleanup_confirmed") is not True:
                result.update(control_state="recovery_required", cleanup_confirmed=False)
            self._update(run_id, **result, finished_at=now())
        except BaseException as exc:
            if not self.unavailable:
                try:
                    self._update(run_id, control_state="recovery_required", cleanup_confirmed=False,
                                 error=type(exc).__name__, finished_at=now())
                except ControlError:
                    pass
        finally:
            self.active = None

    async def close(self):
        self.closing = True
        if self.stop_event is not None and self.task is not None and not self.task.done():
            if not self.unavailable:
                try:
                    self._update(self.active, control_state="stopping", stop_requested=True,
                                 stop_requested_at=self.runs[self.active]["stop_requested_at"] or now())
                except ControlError:
                    pass
            self.stop_event.set()
            await asyncio.shield(self.task)
        if self.owner is not None:
            self.owner.close()
            self.owner = None
