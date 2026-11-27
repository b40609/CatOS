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

A live run can still be in trouble: holding a position with no confirmed disaster stop on OKX
(``position_unprotected``, review F2 of 2026-11-27). Newer Bots say so in the heartbeat
(``protection.unprotected_since``); for a Bot started before that, the rule is read out of
``events.jsonl``. A short gap is normal (the stop is placed right after the fill, and moved
when the average changes), so only a gap longer than three minutes counts.

Standard library only and read-only: nothing here connects to OKX or writes anywhere.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

STALE_BARS = 2
STALE_SLACK_MS = 120_000
HEARTBEAT_MAX_MS = 300_000
START_GRACE_MS = 600_000
UNPROTECTED_GRACE_MS = 180_000
EVENTS_TAIL_BYTES = 2_000_000
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
    "position_unprotected": "有部位，但 OKX 上沒有已確認的保底停損條件單",
    "stopped_with_position": "Bot 已照你的要求停下，但部位還留在 OKX 上，沒有人在看",
}
GAP_REASONS = {
    "ratio_zero": "這個 run 的保底停損比例是 0%",
    "unconfirmed": "條件單還沒確認或被 OKX 拒絕",
    "no_stop_recorded": "紀錄裡沒有掛上條件單",
    "stop_removed": "條件單已撤銷",
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


def holds_position(value):
    """True for a readable non-zero position; None, "0" and anything unreadable are False."""
    try:
        return Decimal(str(value)) != 0
    except (InvalidOperation, ValueError):
        return False


def _events_tail(run_dir):
    try:
        with (run_dir / "events.jsonl").open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - EVENTS_TAIL_BYTES))
            raw = handle.read()
    except OSError:
        return []
    rows = []
    for line in raw.decode("utf-8", errors="replace").splitlines()[1 if size > EVENTS_TAIL_BYTES else 0:]:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if type(row) is dict:
            rows.append(row)
    return rows


def protection_gap(run_dir, status, heartbeat):
    """``(since_ms, why)`` while the run holds a position with no confirmed stop on OKX, else None.

    ``why`` is a key of ``GAP_REASONS``. ``since_ms`` may be None when the time is unknown.
    """
    summary = (heartbeat or {}).get("protection")
    if type(summary) is dict:  # written by the Bot from its ledger and what OKX answered
        if not holds_position((heartbeat or {}).get("position")) or summary.get("confirmed") is True:
            return None
        try:
            zero = Decimal(str(summary.get("ratio"))) == 0
        except (InvalidOperation, ValueError):
            zero = False
        return iso_ms(summary.get("unprotected_since")), "ratio_zero" if zero else "unconfirmed"
    if not holds_position(status.get("position")):
        return None
    # A Bot started before the heartbeat carried this: the same answer out of its event log.
    ratio, placed, last_fill, since, why = None, None, None, None, "no_stop_recorded"
    for row in _events_tail(run_dir):
        kind = row.get("kind")
        if kind in ("protection_config", "protection_config_changed"):
            ratio = row.get("ratio")
        elif kind == "fill":
            last_fill = iso_ms(row.get("time"))
            if why == "stop_removed":  # the stop went with the closed position; this fill opens a new
                since, why = None, "no_stop_recorded"  # one, timed from the fill (review R4)
        elif kind == "protection":
            placed = row.get("price") is not None
            since, why = (None, None) if placed else (iso_ms(row.get("time")), "stop_removed")
        elif kind in ("protection_alert", "protection_altered"):  # altered: changed on the OKX page (R4)
            placed, since, why = False, iso_ms(row.get("time")), "unconfirmed"
    try:
        zero = ratio is not None and Decimal(str(ratio)) == 0
    except (InvalidOperation, ValueError):
        zero = False
    if zero:
        return last_fill, "ratio_zero"
    if placed:
        return None
    return (since if since is not None else last_fill), (why or "no_stop_recorded")


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
    gap = protection_gap(run_dir, status, heartbeat)
    if gap is not None:
        result.update(unprotected_since_ms=gap[0], unprotected_why=gap[1])
    if state == "running":
        problem = running_problem(status, heartbeat, timeframe, now_ms)
        if problem is None and gap is not None and (gap[0] is None or now_ms - gap[0] > UNPROTECTED_GRACE_MS):
            problem = "position_unprotected"
        return dict(result, verdict="alive") if problem is None else dict(result, verdict="problem", problem=problem)
    if state == "stopped" and str(status.get("stop_reason")) in OPERATOR_STOPS:
        # Asked for, so not a problem; with a position left behind it is still worth one reminder
        # (review F8): ``reminder`` is for the caller that knows this is the run that matters.
        reminder = "stopped_with_position" if holds_position(status.get("position")) else None
        return dict(result, verdict="stopped_by_operator", reminder=reminder)
    if state == "stopped":
        return dict(result, verdict="problem", problem="abnormal_stop")
    if state == "starting":
        return dict(result, verdict="starting")
    return dict(result, verdict="problem", problem="failed" if state == "failed" else "status_unreadable")


def claimed_running(root, *, besides=None):
    """Run folders whose status says ``running``, oldest first, without ``besides``.

    The newest folder is not always the run that matters: a start that died right after writing
    its manifest leaves an empty newest folder while the real run (and its position) is the one
    before it (review F7, 2026-11-27).
    """
    found = []
    try:
        folders = list(root.iterdir())
    except OSError:
        return found
    for path in folders:
        if besides is not None and path == besides:
            continue
        manifest, _ = _read(path / "manifest.json")
        if manifest is None or manifest.get("mode") not in (None, "okx-demo-bot"):
            continue
        status, _ = _read(path / "status.json")
        if status is not None and status.get("state") == "running":
            found.append((str(manifest.get("created_at") or ""), path))
    return [path for _, path in sorted(found, key=lambda item: (item[0], item[1].name))]


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
