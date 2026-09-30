"""Bounded read-only projections of fixed local-sim evidence; never open SQLite."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import stat

RUN_ID = re.compile(r"[0-9a-f]{32}")
MAX_METADATA = 64 * 1024
MAX_EVENTS = 2 * 1024 * 1024
MAX_LINE = 32 * 1024
MAX_LINES = 4096
STATUS_FIELDS = (
    "run_id", "profile", "state", "bars", "warmup_bars", "fills", "anomalies",
    "started_at", "finished_at", "heartbeat_at", "expected_finish_at",
    "planned_seconds", "elapsed_seconds", "last_synthetic_time_ms", "worker_pid",
)
MANIFEST_FIELDS = (
    "run_id", "profile", "mode", "created_at", "request", "worker_config",
    "provenance", "runtime_sha256", "bars", "interval_seconds", "funding", "model",
)


class SnapshotError(Exception):
    pass


class LocalSimReader:
    def __init__(self, root, *, clock=None):
        self.root = Path(root).absolute()
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _safe(self, path):
        # Check every ancestor, including Windows junction/reparse points.
        for candidate in (path, *path.parents):
            try:
                info = candidate.lstat()
            except FileNotFoundError:
                continue
            if candidate.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise SnapshotError("linked_evidence_rejected")
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise SnapshotError("evidence_outside_root")
        return path

    def _directory(self, run_id):
        if type(run_id) is not str or RUN_ID.fullmatch(run_id) is None:
            raise SnapshotError("invalid_run_id")
        directory = self._safe(self.root / run_id)
        if not directory.is_dir():
            raise FileNotFoundError("run_not_found")
        return directory

    def _bytes(self, directory, name, maximum):
        path = self._safe(directory / name)
        if not stat.S_ISREG(path.stat().st_mode):
            raise SnapshotError("evidence_not_regular_file")
        with path.open("rb") as stream:
            data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise SnapshotError("evidence_size_limit")
        return data

    @staticmethod
    def _json(data):
        def constant(_value):
            raise ValueError("invalid_constant")

        def pairs(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise ValueError("duplicate_field")
                value[key] = item
            return value

        try:
            value = json.loads(data, parse_constant=constant, object_pairs_hook=pairs)
        except (ValueError, UnicodeError, RecursionError):
            raise SnapshotError("invalid_evidence_json") from None
        if type(value) is not dict:
            raise SnapshotError("invalid_evidence_object")
        return value

    def _metadata(self, directory, name):
        value = self._json(self._bytes(directory, name, MAX_METADATA))
        if value.get("run_id") != directory.name:
            raise SnapshotError("run_identity_mismatch")
        return value

    @staticmethod
    def _event_shape(event):
        def decimal_text(value):
            if type(value) is not str or len(value) > 128:
                raise SnapshotError("event_decimal_text_required")
            try:
                if not Decimal(value).is_finite():
                    raise SnapshotError("invalid_event_decimal")
            except InvalidOperation:
                raise SnapshotError("invalid_event_decimal") from None

        kind = event["kind"]
        if kind in ("signal", "fill", "warmup"):
            if type(event.get("seq")) is not int or event["seq"] < 1:
                raise SnapshotError("invalid_event_sequence")
        if kind == "signal":
            decimal_text(event.get("target"))
            if not isinstance(event.get("account"), dict) or not all(
                type(event.get(key)) is str for key in ("disposition", "reason")
            ):
                raise SnapshotError("invalid_signal_shape")
            for key in ("position", "equity"):
                decimal_text(event["account"].get(key))
        if kind == "fill":
            if not isinstance(event.get("fill"), dict) or not isinstance(event.get("request"), dict):
                raise SnapshotError("invalid_fill_shape")
            for key in ("quantity", "price", "fee"):
                decimal_text(event["fill"].get(key))
            decimal_text(event.get("position"))
            if type(event["fill"].get("trade_id")) is not str or event["request"].get("side") not in ("buy", "sell"):
                raise SnapshotError("invalid_fill_shape")

    def list_runs(self):
        if not self.root.exists():
            return {"state": "empty", "items": [], "issues": []}
        self._safe(self.root)
        directories = []
        for path in self.root.iterdir():
            if RUN_ID.fullmatch(path.name):
                directories.append(path)
                if len(directories) > 200:
                    raise SnapshotError("run_listing_limit")
        items, issues = [], []
        for path in directories:
            try:
                directory = self._directory(path.name)
                status = self._metadata(directory, "status.json")
                items.append({key: status.get(key) for key in STATUS_FIELDS})
            except (OSError, SnapshotError) as error:
                issues.append({"run_id": path.name, "reason": str(error) if isinstance(error, SnapshotError)
                               else "evidence_unavailable"})
        items.sort(key=lambda item: str(item.get("started_at") or ""), reverse=True)
        return {"state": "partial" if issues else "available" if items else "empty",
                "items": items, "issues": issues}

    def snapshot(self, run_id, *, limit=200):
        if type(limit) is not int or not 1 <= limit <= 200:
            raise SnapshotError("invalid_event_limit")
        directory = self._directory(run_id)
        observed = self.clock()
        base = {"contract": "catos.workspace.local-sim.v1", "run_id": run_id,
                "observed_at": observed.isoformat(), "source": "manifest/status/events",
                "read_only": True, "risk": {"state": "unavailable", "can_increase": None,
                "latch": None, "unresolved": None},
                "worker_alive": None, "acceptance": "not_evaluated"}
        try:
            manifest = self._metadata(directory, "manifest.json")
            status = self._metadata(directory, "status.json")
            if manifest.get("mode") != "local-sim-synthetic":
                raise SnapshotError("unsupported_evidence_mode")
            if not all(isinstance(manifest.get(key), dict) for key in ("worker_config", "request", "provenance")):
                raise SnapshotError("invalid_manifest_shape")
            for key in ("bars", "warmup_bars", "fills", "anomalies"):
                if type(status.get(key)) is not int or status[key] < 0:
                    raise SnapshotError("invalid_status_count")
            heartbeat = datetime.fromisoformat(status["heartbeat_at"])
            if heartbeat.tzinfo is None:
                raise SnapshotError("heartbeat_timezone_required")
            data = self._bytes(directory, "events.jsonl", MAX_EVENTS)
            incomplete = bool(data and not data.endswith(b"\n"))
            lines = data.split(b"\n")[:-1]
            if len(lines) > MAX_LINES:
                raise SnapshotError("event_count_limit")
            events = []
            counts = {"signal": 0, "fill": 0, "anomaly": 0, "warmup": 0}
            for number, line in enumerate(lines, 1):
                if len(line) > MAX_LINE or not line:
                    raise SnapshotError("invalid_event_line")
                event = self._json(line)
                if type(event.get("kind")) is not str or type(event.get("wall_time")) is not str:
                    raise SnapshotError("invalid_event_shape")
                self._event_shape(event)
                if event["kind"] in counts:
                    counts[event["kind"]] += 1
                events.append({**event, "line_number": number})
            mapping = {"bars": "signal", "fills": "fill", "anomalies": "anomaly",
                       "warmup_bars": "warmup"}
            reasons = []
            if incomplete:
                reasons.append("incomplete_tail")
            if any(status[key] != counts[kind] for key, kind in mapping.items()):
                reasons.append("status_events_syncing")
            age = (observed - heartbeat).total_seconds()
            if age < -5:
                reasons.append("heartbeat_in_future")
            state = "partial" if reasons else "available" if events else "empty"
            if status.get("state") == "running" and age > 120:
                state = "stale"
                reasons.append("heartbeat_over_120s")
            return {**base, "state": state, "issues": reasons,
                    "manifest": {key: manifest.get(key) for key in MANIFEST_FIELDS},
                    "status": {key: status.get(key) for key in STATUS_FIELDS},
                    "event_counts": counts, "complete_event_lines": len(events),
                    "last_event_seq": next((e.get("seq") for e in reversed(events)
                                            if e.get("seq") is not None), None),
                    "events": events[-limit:], "events_omitted": max(0, len(events) - limit),
                    "last_signal": next((e for e in reversed(events) if e["kind"] == "signal"), None),
                    "last_fill": next((e for e in reversed(events) if e["kind"] == "fill"), None)}
        except FileNotFoundError:
            return {**base, "state": "unavailable", "issues": ["evidence_not_ready"]}
        except (SnapshotError, ValueError, TypeError, KeyError, OSError) as error:
            return {**base, "state": "error", "issues": [str(error) if isinstance(error, SnapshotError)
                    else "evidence_unreadable" ]}
