"""Read-only view of OKX Demo Bot runs for the UI (GET only; nothing is written or sent).

Reads the run folders the Bot writes (manifest.json, status.json, events.jsonl). It never
connects to OKX, never reads credentials, and has no control endpoints: starting and
stopping the Bot stay in the terminal (CLI).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

from fastapi import HTTPException

from catos.demo_bot_liveness import read_heartbeat, running_problem

CONTRACT = "catos.demo-bot.v1"
RUN_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_RUNS = 30
MAX_EVENTS = 60
# Events kept for the UI and the fields each may show; anything else is left out (the manifest
# copy in "started" carries the approval record, which the UI does not need).
EVENT_FIELDS = {
    "started": ("resumed", "missed"), "stopped": ("reason",), "fill": ("leg",),
    "order": (), "protection": ("price", "side", "algo_id"), "protection_alert": ("alert",),
    "protection_altered": ("algo_id",), "protection_config": ("ratio", "source"),
    "protection_config_changed": ("previous", "ratio", "source"), "protection_left": (),
    "protection_wait": ("reason",), "kill_switch": (), "hard_kill_switch": (), "flatten": (),
    "flatten_done": (), "flatten_failed": (), "soft_latched": (), "soft_rearmed": (),
    "soft_rearm_refused": (), "risk": ("reasons", "mode"), "day_basis": (), "read_retry": ("code", "attempt"),
    "status_write_failed": ("error",), "resume_input": ("disposition",), "resume_intent": (), "previous_run_unsettled": (),
}


def _iso_ms(text):
    try:
        return int(datetime.fromisoformat(text).timestamp() * 1000)
    except (TypeError, ValueError):
        return None


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _events(run_dir):
    try:
        lines = (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue  # a line being written right now
        if isinstance(row, dict) and isinstance(row.get("kind"), str):
            rows.append(row)
    return rows


def _summary(run_dir, now_ms):
    manifest = _read_json(run_dir / "manifest.json")
    if manifest.get("mode") != "okx-demo-bot":
        raise ValueError("not a demo bot run")
    try:
        status = _read_json(run_dir / "status.json")
    except FileNotFoundError:
        status = {}
    profile = manifest.get("profile") or {}
    tf = profile.get("timeframe_ms")
    updated = _iso_ms(status.get("updated_at"))
    # Running but not believed (no new bar for over two bars, or the heartbeat stopped): the
    # rule is shared with the watch tool and the Guardian (catos.demo_bot_liveness).
    liveness = running_problem(status, read_heartbeat(run_dir), tf, now_ms)
    return dict(
        run_id=run_dir.name, created_at_ms=_iso_ms(manifest.get("created_at")),
        state=status.get("state", "unknown"), stale=liveness is not None, liveness=liveness,
        stop_reason=status.get("stop_reason"),
        bars=status.get("bars", 0), fills=status.get("fills", 0), position=status.get("position"),
        updated_at_ms=updated, finished_at_ms=_iso_ms(status.get("finished_at")),
        strategy_id=profile.get("strategy_id"), version=profile.get("version"),
        parameters=profile.get("parameters"), timeframe_ms=tf, quantity=profile.get("quantity"),
        inst_id=profile.get("inst_id"), disaster_stop=manifest.get("disaster_stop"),
        approval_id=manifest.get("approval_id"), starting_equity=manifest.get("starting_equity"),
        resumes=len(manifest.get("resumes") or []))


def _detail(run_dir, now_ms):
    from catos.demo_bot import _hint
    summary = _summary(run_dir, now_ms)
    events = _events(run_dir)
    last_bar = next((e for e in reversed(events) if e["kind"] == "bar"), None)
    protection = None
    for event in events:
        if event["kind"] == "protection":
            protection = None if event.get("price") is None else dict(
                price=event["price"], side=event.get("side"), algo_id=event.get("algo_id"),
                since_ms=_iso_ms(event.get("time")))
    fills = []
    for event in events:
        if event["kind"] != "fill":
            continue
        rows = event.get("fills") or []
        try:
            quantity = sum((Decimal(str(r.get("quantity", "0"))) for r in rows), Decimal("0"))
        except InvalidOperation:
            quantity = Decimal("0")
        fills.append(dict(time_ms=_iso_ms(event.get("time")), leg=event.get("leg"),
                          cl_ord_id=(event.get("row") or {}).get("cl_ord_id"),
                          state=(event.get("row") or {}).get("state"),
                          quantity=(event.get("row") or {}).get("filled"),
                          side="buy" if quantity > 0 else "sell",
                          prices=[r.get("price") for r in rows], fees=[r.get("fee") for r in rows]))
    shown = []
    for event in events:
        fields = EVENT_FIELDS.get(event["kind"])
        if fields is None:
            continue
        shown.append(dict(time_ms=_iso_ms(event.get("time")), kind=event["kind"],
                          **{k: event[k] for k in fields if k in event}))
    bar = None if last_bar is None else dict(
        open_time_ms=(last_bar.get("bar") or {}).get("open_time_ms"), close=(last_bar.get("bar") or {}).get("close"),
        mark=last_bar.get("mark"), equity=last_bar.get("equity"), disposition=last_bar.get("disposition"),
        reason=last_bar.get("reason"), target=last_bar.get("target"), risk_reasons=last_bar.get("risk_reasons") or [],
        time_ms=_iso_ms(last_bar.get("time")))
    return dict(summary, last_bar=bar, protection=protection, fill_rows=fills[::-1], events=shown[::-1][:MAX_EVENTS],
                stop_hint=_hint(summary["stop_reason"]) if summary["stop_reason"] else None)


def _now_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def mount_demo_bot(app, *, root):
    root = Path(root)

    def run_dirs():
        if not root.is_dir():
            return []
        found = []
        for path in root.iterdir():
            if RUN_ID.match(path.name) and (path / "manifest.json").is_file():
                found.append(path)
        return found

    @app.get("/api/workspace/demo-bot")
    def overview():
        now = _now_ms()
        runs = []
        for path in run_dirs():
            try:
                runs.append(_summary(path, now))
            except (OSError, ValueError, TypeError, AttributeError):
                continue
        runs.sort(key=lambda r: r["created_at_ms"] or 0, reverse=True)
        runs = runs[:MAX_RUNS]
        current = None
        if runs:
            try:
                current = _detail(root / runs[0]["run_id"], now)
            except (OSError, ValueError, TypeError, AttributeError):
                current = None
        return dict(contract=CONTRACT, runs=runs, current=current, observed_at_ms=now)

    @app.get("/api/workspace/demo-bot/runs/{run_id}")
    def run(run_id: str):
        if not RUN_ID.match(run_id) or not (root / run_id / "manifest.json").is_file():
            raise HTTPException(404, "run_not_found")
        try:
            return dict(contract=CONTRACT, run=_detail(root / run_id, _now_ms()))
        except (OSError, ValueError, TypeError, AttributeError):
            raise HTTPException(503, "run_unreadable") from None

    return app
