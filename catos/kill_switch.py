"""Operator Kill-Switch shared by every local process that holds a Supervisor.

Work package B (docs/wp-b-kill-switch-proposal.md, approved 2026-11-14 as "照建議").
The 8770 app, the local-sim control runs and CLI replays live in different
processes, so the switch is one append-only, hash-chained JSON Lines file that
each of them reads; it is not a ledger. Each Bot's ledger keeps its own latch
(``manual_kill``) and audit row, and stays the source of truth for that Bot.

- engage: anyone (UI, CLI, an agent); it is the safe direction.
- clear: the user only, with a reason and the typed word 解除 (UI or an
  interactive terminal). Agents must not clear it (AGENTS.md 紅線). This is a
  procedural guard, not a security boundary.
- While engaged no new run starts. A running run checks before every bar and
  stops on any engage written after it started, even if it was cleared since.
- Any doubt about the file (unreadable, edited, truncated, emptied, or deleted
  after it was first used) reads as engaged. A fresh install is the only state
  without records: neither the record file nor its ``.lock`` sidecar exists, so
  resetting the switch means the user deliberately deletes both files. Only an
  engage creates the sidecar; a clear never does.
- Engaging is always possible: on a missing or emptied record file it starts a
  new chain with the engage record (a running run sees fewer records than it
  started with, or a new engage, and stops either way).

``CATOS_KILL_SWITCH`` overrides the path for isolated tests and self-tests.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from catos import research_catalog

ENV_PATH = "CATOS_KILL_SWITCH"
DEFAULT_PATH = research_catalog.ROOT / "outputs" / "controls" / "kill-switch.jsonl"
SCHEMA = "catos.kill-switch"
SCHEMA_VERSION = 1
GENESIS = "0" * 64
CONFIRM_WORD = "解除"
ACTORS = frozenset({"http", "cli"})
MAX_FILE_BYTES = 4_000_000
MAX_RECORDS = 10_000
MAX_REASON = 200
RECENT = 20
FIELDS = frozenset({"schema", "schema_version", "record_id", "prev_sha256", "action", "actor",
                    "reason", "request_id", "created_at"})
_RECORD_ID = re.compile(r"[0-9a-f]{32}\Z")
_REQUEST_ID = re.compile(r"[0-9a-f]{32}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class KillSwitchError(Exception):
    pass


def kill_switch_path():
    override = os.environ.get(ENV_PATH)
    return Path(override) if override else DEFAULT_PATH


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _record_id(record):
    return _sha256(canonical({k: v for k, v in record.items() if k != "record_id"}).encode("utf-8"))[:32]


def valid_reason(value):
    return (type(value) is str and value.strip() == value and 1 <= len(value) <= MAX_REASON
            and all(ch.isprintable() for ch in value))


def _strict_json(line):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise KillSwitchError("kill_switch_duplicate_field")
            result[key] = value
        return result

    def reject(_value):
        raise KillSwitchError("kill_switch_invalid_json_constant")

    try:
        return json.loads(line.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject,
                          parse_float=reject)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise KillSwitchError("kill_switch_invalid_json") from None


def _check(record, prev, engaged):
    if type(record) is not dict or set(record) != FIELDS:
        raise KillSwitchError("kill_switch_exact_fields_required")
    if record["schema"] != SCHEMA or type(record["schema_version"]) is not int or record["schema_version"] != SCHEMA_VERSION:
        raise KillSwitchError("kill_switch_schema_mismatch")
    if record["prev_sha256"] != prev or type(record["record_id"]) is not str \
            or _RECORD_ID.fullmatch(record["record_id"]) is None or record["record_id"] != _record_id(record):
        raise KillSwitchError("kill_switch_chain_broken")
    if record["action"] not in ("engage", "clear") or record["actor"] not in ACTORS:
        raise KillSwitchError("kill_switch_action_invalid")
    if not valid_reason(record["reason"]):
        raise KillSwitchError("kill_switch_reason_invalid")
    request_id = record["request_id"]
    if request_id is not None and (type(request_id) is not str or _REQUEST_ID.fullmatch(request_id) is None):
        raise KillSwitchError("kill_switch_request_id_invalid")
    try:
        stamp = datetime.fromisoformat(record["created_at"])
    except (TypeError, ValueError):
        raise KillSwitchError("kill_switch_timestamp_invalid") from None
    if stamp.utcoffset() is None:
        raise KillSwitchError("kill_switch_timestamp_invalid")
    # Engage only from clear and clear only from engage: the file reads as one sequence.
    if (record["action"] == "engage") == engaged:
        raise KillSwitchError("kill_switch_sequence_invalid")


def lock_path(path):
    return Path(str(path) + ".lock")


def read_records(path=None, *, for_engage=False):
    """Every record in order; any doubt about the file raises (fail closed).

    A missing record file is a fresh install only when its ``.lock`` sidecar is
    missing too. Every write appends a whole line, so an existing empty file is
    never legitimate. ``for_engage`` (the engage writer, under the lock) reads a
    missing or empty file as no records, so the safe direction is never blocked.
    """
    path = kill_switch_path() if path is None else Path(path)
    if path.is_symlink():
        raise KillSwitchError("kill_switch_file_symlink_rejected")
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_FILE_BYTES + 1)
    except FileNotFoundError:
        if for_engage:
            return []
        try:
            used = lock_path(path).exists()
        except OSError:
            used = True
        if used:
            raise KillSwitchError("kill_switch_file_missing") from None
        return []
    except OSError:
        raise KillSwitchError("kill_switch_file_unavailable") from None
    if len(raw) > MAX_FILE_BYTES:
        raise KillSwitchError("kill_switch_file_too_large")
    if not raw:
        if for_engage:
            return []
        raise KillSwitchError("kill_switch_file_empty")
    if not raw.endswith(b"\n"):
        raise KillSwitchError("kill_switch_file_truncated")
    records, prev, engaged = [], GENESIS, False
    for line in raw.split(b"\n")[:-1]:
        record = _strict_json(line)
        _check(record, prev, engaged)
        if canonical(record).encode("utf-8") != line:
            raise KillSwitchError("kill_switch_line_not_canonical")
        records.append(record)
        if len(records) > MAX_RECORDS:
            raise KillSwitchError("kill_switch_record_limit")
        engaged = record["action"] == "engage"
        prev = _sha256(line + b"\n")
    return records


def status(path=None):
    """JSON-ready state for the UI/API. An unreadable file reports engaged with the error."""
    path = kill_switch_path() if path is None else Path(path)
    try:
        records = read_records(path)
    except KillSwitchError as error:
        return {"engaged": True, "error": str(error), "engaged_record": None, "count": None,
                "recent": [], "path": str(path)}
    last = records[-1] if records else None
    engaged = last is not None and last["action"] == "engage"
    return {"engaged": engaged, "error": None, "engaged_record": last if engaged else None,
            "count": len(records), "recent": [public(r) for r in records[-RECENT:]][::-1], "path": str(path)}


def public(record):
    return {name: record[name] for name in ("record_id", "action", "actor", "reason", "created_at")}


class _FileLock:
    """Exclusive sidecar lock so the 8770 app and a CLI never append at once."""

    def __init__(self, path):
        self.path = lock_path(path)
        self.stream = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.path.open("a+b")
        deadline = time.monotonic() + 5
        while True:
            try:
                stream.seek(0, 2)
                if stream.tell() == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    stream.close()
                    raise KillSwitchError("kill_switch_file_busy") from None
                time.sleep(0.05)
        self.stream = stream
        return self

    def __exit__(self, *exc):
        try:
            if os.name == "nt":
                import msvcrt
                self.stream.seek(0)
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        finally:
            self.stream.close()


def _append(path, action, actor, reason, request_id, records):
    prev = _sha256(path.read_bytes().split(b"\n")[-2] + b"\n") if records else GENESIS
    record = {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "prev_sha256": prev, "action": action,
              "actor": actor, "reason": reason, "request_id": request_id,
              "created_at": datetime.now(timezone.utc).isoformat()}
    record["record_id"] = _record_id(record)
    _check(record, prev, bool(records) and records[-1]["action"] == "engage")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as stream:
        stream.write(canonical(record).encode("utf-8") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    if read_records(path)[-1] != record:
        raise KillSwitchError("kill_switch_append_unverified")
    return record


def _validate_command(actor, reason, request_id):
    if actor not in ACTORS:
        raise KillSwitchError("kill_switch_actor_invalid")
    if not valid_reason(reason):
        raise KillSwitchError("kill_switch_reason_invalid")
    if request_id is not None and (type(request_id) is not str or _REQUEST_ID.fullmatch(request_id) is None):
        raise KillSwitchError("kill_switch_request_id_invalid")


def _replayed(records, request_id, action):
    if request_id is None:
        return None
    for record in records:
        if record["request_id"] == request_id:
            if record["action"] != action:
                raise KillSwitchError("request_id_conflict")
            return record
    return None


def engage(*, reason, actor, request_id=None, path=None):
    """Returns (record, appended). Already engaged: the active record, nothing appended."""
    _validate_command(actor, reason, request_id)
    path = kill_switch_path() if path is None else Path(path)
    with _FileLock(path):
        records = read_records(path, for_engage=True)
        replay = _replayed(records, request_id, "engage")
        if replay is not None:
            return replay, False
        if records and records[-1]["action"] == "engage":
            return records[-1], False
        return _append(path, "engage", actor, reason, request_id, records), True


def clear(*, reason, actor, confirm, request_id=None, path=None, runs_active=lambda: False):
    """User-only. ``runs_active`` is the caller's check that no run of its own is still going."""
    _validate_command(actor, reason, request_id)
    if confirm != CONFIRM_WORD:
        raise KillSwitchError("kill_switch_confirmation_required")
    path = kill_switch_path() if path is None else Path(path)
    # Read before locking: on a fresh install a clear must not create the .lock
    # sidecar (that would turn the next read into kill_switch_file_missing).
    if not read_records(path):
        raise KillSwitchError("kill_switch_not_engaged")
    with _FileLock(path):
        records = read_records(path)
        replay = _replayed(records, request_id, "clear")
        if replay is not None:
            return replay
        if not records or records[-1]["action"] != "engage":
            raise KillSwitchError("kill_switch_not_engaged")
        if runs_active():
            raise KillSwitchError("simulation_run_active")
        return _append(path, "clear", actor, reason, request_id, records)


def require_clear(path=None):
    """Called before a run starts; engaged or unreadable raises (fail closed)."""
    path = kill_switch_path() if path is None else Path(path)
    records = read_records(path)
    if records and records[-1]["action"] == "engage":
        raise KillSwitchError("kill_switch_engaged")
    return len(records)


class Watch:
    """Per-run check before every bar.

    Fires on the engaged state, on any engage written after the run started
    (even if it was cleared since) and on any doubt about the file. The file is
    re-read only when its size or modification time, or the presence of its
    ``.lock`` sidecar, changed (a run started on a fresh install still sees an
    engaged-then-deleted file: the sidecar stays).
    """

    def __init__(self, path=None):
        self.path = kill_switch_path() if path is None else Path(path)
        self.start_count = require_clear(self.path)
        self._stamp = self._stat()
        self.fired = None
        self.actor = "kill-switch"  # ledger audit actor; "kill-switch-http"/"-cli" once fired

    def _stat(self):
        try:
            info = self.path.stat()
            record = (info.st_size, info.st_mtime_ns)
        except FileNotFoundError:
            record = None
        return (record, lock_path(self.path).exists())

    def check(self):
        """None while clear; else the evidence string ("kill-switch-<record_id>" or the error)."""
        if self.fired is not None:
            return self.fired
        try:
            stamp = self._stat()
            if stamp == self._stamp:
                return None
            records = read_records(self.path)
        except (OSError, KillSwitchError) as error:
            self.fired = "kill-switch-unreadable"
            self.error = str(error)
            return self.fired
        if len(records) < self.start_count:
            self.fired = "kill-switch-unreadable"
            return self.fired
        engaged = [r for r in records[self.start_count:] if r["action"] == "engage"]
        if engaged:
            self.fired = "kill-switch-" + engaged[0]["record_id"]
            self.actor = "kill-switch-" + engaged[0]["actor"]
            return self.fired
        self._stamp = stamp
        return None


def terminal_confirm(text, word):
    """Interactive confirmation only: a script or agent pipe cannot answer it."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise KillSwitchError("interactive_terminal_required")
    print(text, flush=True)
    return input(f"確認請輸入 {word}：").strip()


def cli_main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m catos.cli kill",
                                     description="Kill-Switch 總開關（觸發任何人都可以；解除只限使用者在終端機執行）")
    commands = parser.add_subparsers(dest="command", required=True)
    engage_cmd = commands.add_parser("engage", help="觸發：停止所有 local-sim run，禁止啟動新 run")
    engage_cmd.add_argument("--reason", required=True)
    clear_cmd = commands.add_parser("clear", help="解除（只限使用者；代理不得執行）")
    clear_cmd.add_argument("--reason", required=True)
    commands.add_parser("status", help="顯示狀態與最近紀錄（唯讀）")
    args = parser.parse_args(argv)
    try:
        if args.command == "engage":
            record, appended = engage(reason=args.reason, actor="cli")
            print(("已觸發" if appended else "原本就在觸發中") + f"：{record['record_id']}（{kill_switch_path()}）")
        elif args.command == "clear":
            word = terminal_confirm(
                "解除後可以再啟動新的 local-sim run；已被 Kill 停下的 run 不會恢復，帳本仍鎖存。", CONFIRM_WORD)
            record = clear(reason=args.reason, actor="cli", confirm=word)
            print(f"已解除：{record['record_id']}")
        else:
            value = status()
            if value["error"]:
                print(f"紀錄檔有問題，視同已觸發：{value['error']}（{value['path']}）")
            else:
                print(f"{'已觸發' if value['engaged'] else '未觸發'}（{value['count']} 筆紀錄，雜湊鏈完整；{value['path']}）")
            for record in value["recent"]:
                print(f"  {record['created_at']}  {record['action']}  {record['actor']}  {record['record_id']}  {record['reason']}")
        return 0
    except (KillSwitchError, OSError) as error:
        print(f"錯誤：{error}", file=sys.stderr)
        return 1
