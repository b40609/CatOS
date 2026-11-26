"""Is an OKX Demo Bot run really doing what its status file says?

One rule for every reader of a run folder: the UI view (``catos.demo_bot_view``), the watch
tool and the Guardian (``tools/``). The Bot writes its own state, so a process that is killed
leaves ``running`` behind for ever (2026-11-20: six days, and the hourly check kept reporting
nothing wrong). Readers therefore judge by time, never by the word in the file:

- ``status.json`` ``updated_at`` moves once per closed bar. Running and silent for more than
  two bars: ``bars_stalled``.
- ``heartbeat.json`` is rewritten every minute while the process lives. Running with a
  heartbeat older than five minutes: ``process_lost``. Runs written before the heartbeat
  existed have no such file; for them only the bar rule applies.

Standard library only and read-only: nothing here connects to OKX or writes anywhere.
"""

from __future__ import annotations

import json
from datetime import datetime

STALE_BARS = 2
STALE_SLACK_MS = 120_000
HEARTBEAT_MAX_MS = 300_000
START_GRACE_MS = 600_000
HEARTBEAT_FILE = "heartbeat.json"
# Stops the user asked for; every other stop reason is something to look at.
OPERATOR_STOPS = ("operator_stop", "operator_stop_file", "interrupted")

MESSAGES = {
    "bars_stalled": "狀態寫 running，但超過兩根 K 線沒有更新",
    "process_lost": "狀態寫 running，但心跳超過 5 分鐘沒有更新（程序不在了）",
    "status_unreadable": "status.json 讀不到或缺少時間，無法判斷是否還在跑",
    "abnormal_stop": "Bot 自己停下了，不是你要它停的",
    "failed": "Bot 因為程式錯誤結束",
    "never_started": "run 資料夾建立超過 10 分鐘，Bot 沒有跑起來",
}


def iso_ms(text):
    """Milliseconds of an ISO time with an offset; None for anything else."""
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if moment.tzinfo is None:
        return None
    return int(moment.timestamp() * 1000)


def running_problem(status, heartbeat, timeframe_ms, now_ms):
    """Why a run that says ``running`` is not believed, or None. Other states return None."""
    if status.get("state") != "running":
        return None
    updated = iso_ms(status.get("updated_at"))
    if updated is None or type(timeframe_ms) is not int or timeframe_ms <= 0:
        return "status_unreadable"
    beat = iso_ms((heartbeat or {}).get("time"))
    if beat is not None and now_ms - beat > HEARTBEAT_MAX_MS:
        return "process_lost"
    if now_ms - updated > STALE_BARS * timeframe_ms + STALE_SLACK_MS:
        return "bars_stalled"
    return None


def _read(path):
    """(value, readable): a missing file is (None, True); a damaged one is (None, False)."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, True
    except (OSError, ValueError):
        return None, False
    return (value, True) if type(value) is dict else (None, False)


def read_heartbeat(run_dir):
    """The heartbeat file, or None; a file being replaced right now counts as absent this time."""
    return _read(run_dir / HEARTBEAT_FILE)[0]


def judge(run_dir, now_ms):
    """What an outside reader concludes about one run folder.

    ``verdict`` is ``alive``, ``starting``, ``stopped_by_operator`` or ``problem``; with
    ``problem`` the ``problem`` field names it (a key of ``MESSAGES``).
    """
    manifest, _ = _read(run_dir / "manifest.json")
    manifest = manifest or {}
    status, readable = _read(run_dir / "status.json")
    heartbeat = read_heartbeat(run_dir)
    timeframe = (manifest.get("profile") or {}).get("timeframe_ms")
    result = {"run_id": run_dir.name, "state": None, "stop_reason": None, "position": None, "bars": None,
              "updated_at": None, "heartbeat_at": (heartbeat or {}).get("time"), "problem": None}
    if not readable:
        return dict(result, verdict="problem", problem="status_unreadable")
    if status is None:
        created = iso_ms(manifest.get("created_at"))
        beat = iso_ms((heartbeat or {}).get("time"))
        starting = ((created is not None and now_ms - created <= START_GRACE_MS)
                    or (beat is not None and now_ms - beat <= HEARTBEAT_MAX_MS))
        return dict(result, verdict="starting") if starting else dict(result, verdict="problem", problem="never_started")
    result.update(state=status.get("state"), stop_reason=status.get("stop_reason"), position=status.get("position"),
                  bars=status.get("bars"), updated_at=status.get("updated_at"))
    state = status.get("state")
    if state == "running":
        problem = running_problem(status, heartbeat, timeframe, now_ms)
        return dict(result, verdict="alive") if problem is None else dict(result, verdict="problem", problem=problem)
    if state == "stopped" and str(status.get("stop_reason")) in OPERATOR_STOPS:
        return dict(result, verdict="stopped_by_operator")
    if state == "stopped":
        return dict(result, verdict="problem", problem="abnormal_stop")
    if state == "starting":
        return dict(result, verdict="starting")
    return dict(result, verdict="problem", problem="failed" if state == "failed" else "status_unreadable")


def newest_run(root):
    """The run folder with the newest manifest ``created_at``, or None."""
    best = None
    try:
        folders = list(root.iterdir())
    except OSError:
        return None
    for path in folders:
        manifest, _ = _read(path / "manifest.json")
        if manifest is None or manifest.get("mode") not in (None, "okx-demo-bot"):
            continue
        key = str(manifest.get("created_at") or "")
        if best is None or key > best[0]:
            best = (key, path)
    return None if best is None else best[1]
