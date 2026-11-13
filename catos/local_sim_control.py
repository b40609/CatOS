"""Single event-loop control slot, durable command bindings, no ledger writes."""

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import time
import uuid

from catos import kill_switch, risk
from catos import simulation_catalog as catalog
from catos.local_sim_control_runner import run_case
from catos.local_sim_r4 import RUNTIME_FILES
from catos.research_catalog import DEFAULT_REQUEST, files_hash, validate_request

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
MAX_LIFECYCLE = 32
DOMAINS = ("service", "bots", "risk", "positions", "events")
BUILD_FILES = tuple(RUNTIME_FILES) + (
    "catos/local_sim_control.py", "catos/local_sim_control_runner.py",
    "catos/local_sim_control_api.py", "catos/simulation_catalog.py", "catos/workspace_api.py")


def build_id():
    return files_hash(BUILD_FILES)


def now():
    return datetime.now(timezone.utc).isoformat()


def now_ms():
    return time.time_ns() // 1_000_000


def valid_id(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value) is not None


class ControlError(Exception):
    def __init__(self, code, status=503):
        super().__init__(code)
        self.status = status


KILL_STATUS = {"kill_switch_engaged": 409, "kill_switch_not_engaged": 409, "simulation_run_active": 409,
               "request_id_conflict": 409, "kill_switch_confirmation_required": 422,
               "kill_switch_reason_invalid": 422, "kill_switch_request_id_invalid": 422}


def kill_error(error):
    code = str(error)
    return ControlError(code, KILL_STATUS.get(code, 503))


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
        # Read-only projection state: a monotonic version per instance, the version at
        # which each domain last changed, and one global event sequence across runs.
        self.state_version = 0
        self.domains = dict.fromkeys(DOMAINS, 0)
        self.seq = 0
        self.started_at_ms = now_ms()
        self.seen_build = self.loaded_build
        self.limits = risk.Limits()
        self._contract = None
        self._kill_stamp = self._kill_signature()

    def _bump(self, *domains):
        self.state_version += 1
        for domain in domains or DOMAINS:
            self.domains[domain] = self.state_version

    def open(self):
        if self.loaded_build == "source_unavailable":
            self.unavailable = "simulation_source_unavailable"
            self._bump("service")
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
            self.seq = max((event.get("event_seq", 0) for run in self.runs.values()
                            for event in [*run["events"], *run.get("lifecycle", [])]
                            if type(event.get("event_seq")) is int), default=0)
            recovered = deepcopy(self.runs)
            changed = False
            for run in recovered.values():
                if run["control_state"] not in TERMINAL or not run["cleanup_confirmed"]:
                    self._transition(run, control_state="recovery_required", cleanup_confirmed=False,
                                     error="interrupted_or_cleanup_unconfirmed")
                    changed = True
            self.unavailable = None
            if changed:
                self._save(recovered)
            else:
                self._bump()
        except (OSError, ValueError, TypeError, KeyError, ControlError) as exc:
            self.unavailable = str(exc) if isinstance(exc, ControlError) else "simulation_metadata_unavailable"
            self._bump("service")

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
            lifecycle = run.get("lifecycle", [])
            if (not valid_id(run["instance_id"]) or type(run["worker_closed"]) is not bool
                    or (run["error"] is not None and type(run["error"]) is not str)
                    or type(lifecycle) is not list or len(lifecycle) > MAX_LIFECYCLE
                    or any(type(event) is not dict or type(event.get("kind")) is not str
                           for event in [*run["events"], *lifecycle])):
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

    def _save(self, runs, *domains):
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
            self._bump(*domains)
        except (OSError, ValueError, TypeError):
            self.unavailable = "simulation_metadata_write_uncertain"
            self._bump("service")
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
        try:
            kill_switch.require_clear()
        except kill_switch.KillSwitchError as error:
            raise ControlError("kill_switch_engaged" if str(error) == "kill_switch_engaged"
                               else "kill_switch_unreadable", 409) from None
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
            events=[], events_omitted=0, error=None, finished_at=None, worker_closed=False,
            lifecycle=[])
        self._lifecycle(record, "run_state", state="starting", previous=None)
        runs = deepcopy(self.runs)
        runs[run_id] = record
        try:
            (self.root / run_id).mkdir(exist_ok=False)
        except OSError:
            self.unavailable = "simulation_run_directory_uncertain"
            self._bump("service")
            raise ControlError(self.unavailable) from None
        self._save(runs, "service", "bots", "events")
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
            if not record["stop_requested"]:
                self._lifecycle(record, "stop_requested", request_id=request_id,
                                state=record["control_state"])
            self._transition(record, control_state="stopping", stop_requested=True,
                             stop_requested_at=record["stop_requested_at"] or now())
        self._save(runs, "service", "bots", "events")
        if self.active == run_id and self.stop_event is not None:
            self.stop_event.set()
        return self.snapshot(run_id)

    def _lifecycle(self, record, kind, **values):
        """Control-plane event kept apart from runner events so run evidence is unchanged."""
        self.seq += 1
        record.setdefault("lifecycle", []).append(
            {"kind": kind, "wall_time": now(), "wall_time_ms": now_ms(),
             "event_seq": self.seq, **values})
        if len(record["lifecycle"]) > MAX_LIFECYCLE:
            record["lifecycle"].pop(0)
            record["events_omitted"] = min(record["events_omitted"] + 1, 100)

    def _transition(self, record, **values):
        previous = record["control_state"]
        record.update(values)
        if record["control_state"] != previous:
            self._lifecycle(record, "run_state", state=record["control_state"], previous=previous)
            return True
        return False

    def _update(self, run_id, **values):
        runs = deepcopy(self.runs)
        record = runs[run_id]
        if record["control_state"] == "stopping" and values.get("control_state") == "running":
            values.pop("control_state")
        changed = self._transition(record, **values)
        self._save(runs, "service", "bots", *(("events",) if changed else ()))

    def _emit(self, run_id, kind, **values):
        runs = deepcopy(self.runs)
        record = runs[run_id]
        self.seq += 1
        event = {"kind": kind, "wall_time": now(), "wall_time_ms": now_ms(),
                 "event_seq": self.seq, **values}
        record["events"].append(event)
        if len(record["events"]) > MAX_EVENTS:
            record["events"].pop(0)
            record["events_omitted"] += 1
        if kind in ("signal", "fill"):
            record["last_" + kind] = event
        domains = ("events", "bots", "risk", "positions") if kind in catalog.ACCOUNT_EVENTS else ("events",)
        self._save(runs, *domains)

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

    # Kill-Switch (work package B, docs/wp-b-kill-switch-proposal.md). The record
    # file is shared with CLI replays; runs check it before every bar themselves.

    @staticmethod
    def _kill_signature():
        try:
            info = kill_switch.kill_switch_path().stat()
        except FileNotFoundError:
            return None
        except OSError:
            return "unavailable"
        return (info.st_size, info.st_mtime_ns)

    def kill_switch(self):
        value = kill_switch.status()
        value.pop("path", None)
        return {**value, "confirm_word": kill_switch.CONFIRM_WORD,
                "default_limits": self.limits.to_wire(), "version": self.state_version}

    def _kill_changed(self):
        stamp = self._kill_signature()
        if stamp != self._kill_stamp:
            self._kill_stamp = stamp
            self._bump("risk")

    async def engage_kill(self, request_id, reason):
        # No _ready(): the switch is a file shared with CLI replays, so engaging must
        # work even when this control plane is unavailable or closing.
        try:
            record, appended = await asyncio.to_thread(
                kill_switch.engage, reason=reason, actor="http", request_id=request_id)
        except kill_switch.KillSwitchError as error:
            raise kill_error(error) from None
        if not self.unavailable:
            self._kill_changed()
        return {"record": kill_switch.public(record), "appended": appended,
                "kill_switch": self.kill_switch()}

    async def clear_kill(self, request_id, reason, confirm):
        self._ready()
        try:
            record = await asyncio.to_thread(
                kill_switch.clear, reason=reason, actor="http", confirm=confirm, request_id=request_id,
                runs_active=lambda: self.active is not None)
        except kill_switch.KillSwitchError as error:
            raise kill_error(error) from None
        self._kill_changed()
        return {"record": kill_switch.public(record), "kill_switch": self.kill_switch()}

    # Read-only projections (contract: docs/simulation-api-contract-draft.md section 2).
    # They read control-plane memory only: no SQLite, no basis creation, no latch changes.

    def contract(self):
        if self._contract is None:
            try:
                self._contract = validate_request(DEFAULT_REQUEST)[1].contract
            except (ValueError, OSError):
                self._contract = False
        return self._contract or None

    def _latest_run(self):
        if self.active is not None and self.active in self.runs:
            return self.runs[self.active]
        return next((self.runs[run_id] for run_id in reversed(self.runs)), None)

    def strategies(self):
        return {"items": [catalog.strategy_entry()], "version": self.state_version}

    def bot(self, bot_id):
        if type(bot_id) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", bot_id):
            raise ControlError("invalid_bot_id", 422)
        if bot_id != catalog.BOT_ID:
            raise ControlError("bot_not_found", 404)
        run = self._latest_run()
        account, risk_state, source = catalog.latest_account(run)
        view = catalog.bot_static(self.contract(), CONFIG["candle_timeframe_ms"], self.started_at_ms)
        signal = None if run is None else run.get("last_signal")
        terminal = run is not None and run["control_state"] in TERMINAL
        view.update({
            "version": self.state_version,
            "state": "stopped" if run is None else run["control_state"],
            "current_run_id": None if run is None else run["run_id"],
            "active": run is not None and run["run_id"] == self.active,
            "run_count": len(self.runs),
            "worker_pid": None if run is None else run.get("worker_pid"),
            "bars": 0 if run is None else run["bars"],
            "warmup_bars": 0 if run is None else run["warmup_bars"],
            "fills": 0 if run is None else run["fills"],
            "last_synthetic_time_ms": None if run is None else run.get("last_synthetic_time_ms"),
            "run_created_at_ms": None if run is None else catalog.iso_to_ms(run["created_at"]),
            "finished_at_ms": None if run is None else catalog.iso_to_ms(run["finished_at"]),
            "account_source": source,
            **{name: None if account is None else account[name] for name in catalog.ACCOUNT_FIELDS},
            "mark": catalog.latest_mark(run, risk_state),
            "last_disposition": None if signal is None else signal.get("disposition"),
            "last_reason": None if signal is None else signal.get("reason"),
            "ownership_retained": bool(terminal and account is not None
                                       and account["position"] not in ("0", None)
                                       and Decimal(account["position"]) != 0),
            "error": None if run is None else run["error"]})
        return view

    def bots(self):
        return {"items": [self.bot(catalog.BOT_ID)], "version": self.state_version}

    def _risk_inputs(self):
        run = self._latest_run()
        account, risk_state, _ = catalog.latest_account(run)
        return run, account, risk_state

    def risk(self):
        self._ready()
        run, _, risk_state = self._risk_inputs()
        value = catalog.risk_projection(run, risk_state, self.contract(), self.limits)
        return None if value is None else {"version": self.state_version, **value}

    def positions(self):
        self._ready()
        run, account, risk_state = self._risk_inputs()
        return {"items": catalog.position_projection(run, account, risk_state, self.contract()),
                "version": self.state_version}

    def summary(self):
        run, account, risk_state = self._risk_inputs()
        risk_dto = catalog.risk_projection(run, risk_state, self.contract(), self.limits)
        return catalog.summary_projection(run, account, risk_dto, self.active, self.limits)

    def _all_events(self):
        for run_id, run in self.runs.items():
            for event in [*run["events"], *run.get("lifecycle", [])]:
                if type(event.get("event_seq")) is int:
                    yield run_id, event

    def events(self, since=0, limit=MAX_EVENTS):
        if type(since) is not int or since < 0:
            raise ControlError("invalid_since", 422)
        if type(limit) is not int or not 1 <= limit <= catalog.MAX_EVENT_LIMIT:
            raise ControlError("invalid_limit", 422)
        ordered = sorted(((event["event_seq"], run_id, event) for run_id, event in self._all_events()
                          if event["event_seq"] > since), key=lambda item: item[0])
        items = [catalog.event_dto(run_id, event) for _, run_id, event in ordered[:limit]]
        return {"items": items, "next_since": items[-1]["seq"] if items else since,
                "more": len(ordered) > limit, "version": self.state_version,
                "omitted": self._omitted()}

    def state(self, since_version=None):
        current = self.current_build()
        if current != self.seen_build:
            self.seen_build = current
            self._bump("service")
        self._ready()
        self._kill_changed()
        if since_version is not None and (type(since_version) is not int or since_version < 0):
            raise ControlError("invalid_since_version", 422)
        base = {"contract": "catos.simulation.v1", "version": self.state_version,
                "instance_id": self.instance_id, "observed_at_ms": now_ms()}
        if since_version == self.state_version:
            return {**base, "unchanged": True}
        recent = sorted((catalog.event_dto(run_id, event) for run_id, event in self._all_events()),
                        key=lambda dto: dto["seq"])[-MAX_EVENTS:]
        return {**base, "unchanged": False, "service": self.version(),
                "strategies": self.strategies()["items"], "bots": self.bots()["items"],
                "risk": self.risk(), "positions": self.positions()["items"],
                "summary": self.summary(), "kill_switch": self.kill_switch(),
                "events": {"items": recent, "next_since": recent[-1]["seq"] if recent else 0,
                           "omitted": self._omitted()},
                "domains": dict(self.domains)}

    def _omitted(self):
        legacy = sum(1 for run in self.runs.values()
                     for event in [*run["events"], *run.get("lifecycle", [])]
                     if type(event.get("event_seq")) is not int)
        return sum(run["events_omitted"] for run in self.runs.values()) + legacy

    async def close(self):
        self.closing = True
        self._bump("service")
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
