"""Telling the owner about the OKX Demo Bot: this computer first, then the owner's phone.

Two channels, both best effort and neither ever raising:

- ``toast``: a Windows notification on this computer (a message box when the toast fails).
  It needs the user's desktop session; a task that runs while nobody is logged on has none.
- ``external``: OmniKeep's owner alert (Telegram, Web Push, LINE: whatever the user set up
  there), reached by running OmniKeep's own Python on its ``app.owner_alert.send`` in a child
  process (the interface ``scripts/alert_owner.py --event custom`` uses, chosen because it
  answers how many deliveries went out). CatOS never reads OmniKeep's settings or keys: the
  child process loads them itself, and only its delivery counts come back. Where OmniKeep
  lives is in ``~/.catos/owner-alert.json`` (``CATOS_OWNER_ALERT`` overrides the path):

      {"omnikeep_root": "C:\\\\...\\\\OmniKeep", "python": "C:\\\\...\\\\python.exe"}

  No such file: this computer only (``not_configured``). OmniKeep gone, broken or with no
  channel delivering: recorded with the reason, and the local notification still stands.

``deliver`` and ``settle`` keep one small state file per caller so a problem is announced
once, repeated every six hours while it lasts, retried on the channel that failed, and
followed by one "it is over" message on the phone when it goes away.

Standard library only: the Guardian must still be able to say it is broken when ``catos``
cannot be imported.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

TOAST_SCRIPT = Path(__file__).with_name("demo_bot_toast.ps1")
REPEAT_MS = 6 * 3_600_000
EXTERNAL_RETRIES = 12  # per announcement: about an hour of five-minute checks, then wait for the repeat
EXTERNAL_TIMEOUT_S = 90
RESULT_MARK = "CATOS_ALERT_RESULT "
ERROR_MARK = "CATOS_ALERT_ERROR "
TAG = "catos-demo-bot"
CLEARED_TITLE = "CatOS 模擬盤 Bot：狀況解除"

# Runs inside OmniKeep's interpreter. Only the two marked lines are ever read back.
_SNIPPET = (
    "import asyncio, json, os, sys\n"
    "try:\n"
    "    sys.path.insert(0, os.environ['CATOS_ALERT_ROOT'])\n"
    "    from app import owner_alert\n"
    "    counts = asyncio.run(owner_alert.send(os.environ['CATOS_ALERT_TITLE'], os.environ['CATOS_ALERT_BODY'],\n"
    "                                          tag=os.environ['CATOS_ALERT_TAG']))\n"
    "    print('" + RESULT_MARK + "' + json.dumps({k: int(v) for k, v in dict(counts).items()}))\n"
    "except BaseException as exc:\n"
    "    print('" + ERROR_MARK + "' + type(exc).__name__)\n"
    "    raise SystemExit(3)\n"
)


def config_path():
    override = os.environ.get("CATOS_OWNER_ALERT")
    return Path(override) if override else Path.home() / ".catos" / "owner-alert.json"


def toast(title, body):
    """A Windows notification on this computer; falls back to a message box when the toast fails."""
    if sys.platform != "win32":
        return {"ok": False, "detail": "not_windows"}
    env = dict(os.environ, CATOS_TOAST_TITLE=title, CATOS_TOAST_BODY=body)
    hidden = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # Windows tools answer in the console code page (Big5 here): in UTF-8 mode (PYTHONUTF8=1) a strict
    # decode fails in the reader and leaves stdout None, so read leniently and never trust it is a str.
    try:
        done = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(TOAST_SCRIPT)],
                              env=env, capture_output=True, text=True, errors="replace", timeout=45,
                              creationflags=hidden, check=False)
        detail = ((done.stdout or "").strip() or (done.stderr or "").strip())[-300:]
        if done.returncode == 0:
            return {"ok": True, "detail": "toast:" + detail}
    except (OSError, subprocess.SubprocessError) as exc:
        detail = f"{type(exc).__name__}: {exc}"[:300]
    try:
        boxed = subprocess.run(["msg.exe", os.environ.get("USERNAME", "*"), "/TIME:0", f"{title}\n{body}"],
                               capture_output=True, text=True, errors="replace", timeout=20, creationflags=hidden,
                               check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "detail": f"toast_failed:{detail}; msg_failed:{type(exc).__name__}"}
    return {"ok": boxed.returncode == 0, "detail": f"toast_failed:{detail}; msg:{boxed.returncode}"}


def external(title, body, *, path=None, run=subprocess.run):
    """Send through OmniKeep. ``ok`` only when at least one delivery went out; never raises.

    ``final`` marks an answer that trying again cannot change (nothing is configured).
    """
    path = config_path() if path is None else Path(path)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
        root, python = Path(config["omnikeep_root"]), Path(config["python"])
    except FileNotFoundError:
        return {"ok": False, "final": True, "detail": "not_configured"}
    except (OSError, ValueError, KeyError, TypeError):
        return {"ok": False, "detail": "config_unreadable"}
    if not (root / "app" / "owner_alert.py").is_file():
        return {"ok": False, "detail": "omnikeep_not_found"}
    if not python.is_file():
        return {"ok": False, "detail": "omnikeep_python_not_found"}
    env = dict(os.environ, CATOS_ALERT_ROOT=str(root), CATOS_ALERT_TITLE=str(title)[:200],
               CATOS_ALERT_BODY=str(body)[:3000], CATOS_ALERT_TAG=TAG, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        done = run([str(python), "-B", "-c", _SNIPPET], cwd=str(root), env=env, capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=EXTERNAL_TIMEOUT_S,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": "omnikeep_timeout"}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "detail": f"omnikeep_start_failed:{type(exc).__name__}"}
    # Nothing else of the child's output is kept: its log lines are OmniKeep's, not ours to store.
    lines = str(done.stdout or "").splitlines()
    result = next((line[len(RESULT_MARK):] for line in reversed(lines) if line.startswith(RESULT_MARK)), None)
    if result is None:
        error = next((line[len(ERROR_MARK):][:60] for line in reversed(lines) if line.startswith(ERROR_MARK)), None)
        return {"ok": False, "detail": f"omnikeep_failed:exit={done.returncode}:{error or 'no_result'}"}
    try:
        counts = {str(k): int(v) for k, v in json.loads(result).items()}
    except (ValueError, TypeError, AttributeError):
        return {"ok": False, "detail": "omnikeep_result_unreadable"}
    summary = ",".join(f"{name}={count}" for name, count in sorted(counts.items()))
    if sum(counts.values()) < 1:
        return {"ok": False, "detail": "omnikeep_no_channel_delivered:" + summary, "counts": counts}
    return {"ok": True, "detail": "omnikeep:" + summary, "counts": counts}


def _nowhere(title, body):
    return {"ok": False, "final": True, "detail": "not_configured"}


def _safely(send, title, body):
    try:
        answer = send(title, body)
        return answer if type(answer) is dict else {"ok": False, "detail": "bad_answer"}
    except Exception as exc:  # noqa: BLE001 - a channel that breaks must not stop the other one or the caller
        return {"ok": False, "detail": f"raised:{type(exc).__name__}"}


def load(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if type(value) is dict else {}


def save(path, value):
    path = Path(path)
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pending.replace(path)


def _text(now_ms):
    return datetime.fromtimestamp(now_ms / 1000, UTC).isoformat()


def _append(path, row):
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def deliver(state_dir, key, title, body, now_ms, *, local=toast, remote=None, repeat=True, fields=None,
            state_file="state.json", log_file="alerts.jsonl"):
    """Announce ``key`` when it is new, due again, or a channel still owes a delivery.

    Returns the row appended to the log, or None when nothing was sent this time.
    """
    state_dir = Path(state_dir)
    remote = _nowhere if remote is None else remote
    state = load(state_dir / state_file)
    alerts = state.get("alerts") if type(state.get("alerts")) is dict else {}
    entry = alerts.get(key)
    due = entry is None or (repeat and now_ms - int(entry.get("announced_at_ms") or 0) >= REPEAT_MS)
    if due:
        entry = {"first_ms": (entry or {}).get("first_ms", now_ms), "announced_at_ms": now_ms, "title": title,
                 "local_ok": False, "remote_ok": False, "remote_final": False, "remote_tries": 0,
                 "repeat": entry is not None}
    owe_local = not entry["local_ok"]
    owe_remote = (not entry["remote_ok"] and not entry["remote_final"]
                  and entry["remote_tries"] < EXTERNAL_RETRIES)
    if not (due or owe_local or owe_remote):
        return None
    row = {"time": _text(now_ms), "key": key, "message": body, "repeat": entry["repeat"], **(fields or {})}
    if owe_local:
        sent = _safely(local, title, body)
        entry["local_ok"] = bool(sent.get("ok"))
        row.update(notified=entry["local_ok"], notify_detail=sent.get("detail"))
    if owe_remote:
        sent = _safely(remote, title, body)
        entry["remote_tries"] += 1
        entry["remote_ok"] = bool(sent.get("ok"))
        entry["remote_final"] = bool(sent.get("final"))
        entry["remote_detail"] = sent.get("detail")
        row.update(external=entry["remote_ok"], external_detail=sent.get("detail"), external_try=entry["remote_tries"])
    alerts[key] = entry
    save(state_dir / state_file, dict(state, alerts=alerts))
    _append(state_dir / log_file, row)
    return row


def settle(state_dir, active_keys, now_ms, *, remote=None, fields=None, state_file="state.json",
           log_file="alerts.jsonl"):
    """Forget every announced key that is no longer active; the phone hears once that it is over."""
    state_dir = Path(state_dir)
    state = load(state_dir / state_file)
    alerts = state.get("alerts") if type(state.get("alerts")) is dict else {}
    rows = []
    for key in [k for k in alerts if k not in active_keys]:
        entry = alerts.pop(key)
        row = {"time": _text(now_ms), "key": key, "problem": None, "cleared": key, **(fields or {})}
        if entry.get("remote_ok") and remote is not None:
            sent = _safely(remote, CLEARED_TITLE, f"先前通知的狀況已解除：{entry.get('title') or key}（{key}）")
            row.update(external=bool(sent.get("ok")), external_detail=sent.get("detail"))
        rows.append(row)
    if rows:
        save(state_dir / state_file, dict(state, alerts=alerts))
        for row in rows:
            _append(state_dir / log_file, row)
    return rows
