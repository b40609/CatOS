"""Guardian: an outside, read-only check that the newest OKX Demo Bot run is alive.

Run by Windows Task Scheduler every five minutes under the user's own account (not a service:
the Bot's key file, account records and locks all live under the user's home). It reads only
the run folder (manifest.json, status.json, heartbeat.json); it never connects to OKX, never
reads credentials, never writes into the run folder and never starts, stops or resumes a Bot.

A run that says running but is not believed (no new bar for over two bars, or its heartbeat
stopped), a run that stopped for a reason the user did not ask for, a failed run and a run
that never started are problems. A problem shows a Windows notification on this computer
(once when it appears, again every six hours while it lasts) and is appended to
``outputs/demo-bot-guardian/alerts.jsonl``; every check rewrites ``last_check.json`` there.

    .venv/Scripts/pythonw.exe tools/demo_bot_guardian.py [--root <runs>] [--state-dir <dir>] [--no-notify]

Exit code: 0 nothing to look at, 2 a problem was found, 1 the Guardian itself failed
(the traceback is appended to ``errors.log`` in the state folder).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from catos.demo_bot_liveness import MESSAGES, iso_ms, judge, newest_run

ROOT = REPO / "outputs" / "okx-demo-bot"
STATE_DIR = REPO / "outputs" / "demo-bot-guardian"
REPEAT_MS = 6 * 3_600_000
TOAST_SCRIPT = Path(__file__).with_name("demo_bot_toast.ps1")
TITLE = "CatOS 模擬盤 Bot 需要你看一下"


def _local(text):
    ms = iso_ms(text)
    return "不明" if ms is None else datetime.fromtimestamp(ms / 1000).strftime("%m-%d %H:%M")


def describe(result):
    """One line for the notification and the log."""
    line = f"run {result['run_id'][:8]}：{MESSAGES.get(result['problem'], result['problem'])}"
    if result.get("stop_reason"):
        line += f"（{str(result['stop_reason'])[:80]}）"
    return f"{line}。部位 {result.get('position')}，最後一根 K 線 {_local(result.get('updated_at'))}。"


def toast(title, body):
    """A Windows notification on this computer; falls back to a message box when the toast fails."""
    if sys.platform != "win32":
        return {"ok": False, "detail": "not_windows"}
    env = dict(os.environ, CATOS_TOAST_TITLE=title, CATOS_TOAST_BODY=body)
    hidden = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        done = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(TOAST_SCRIPT)],
                              env=env, capture_output=True, text=True, timeout=45, creationflags=hidden, check=False)
        detail = (done.stdout.strip() or done.stderr.strip())[-300:]
        if done.returncode == 0:
            return {"ok": True, "detail": "toast:" + detail}
    except (OSError, subprocess.SubprocessError) as exc:
        detail = f"{type(exc).__name__}: {exc}"[:300]
    try:
        boxed = subprocess.run(["msg.exe", os.environ.get("USERNAME", "*"), "/TIME:0", f"{title}\n{body}"],
                               capture_output=True, text=True, timeout=20, creationflags=hidden, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "detail": f"toast_failed:{detail}; msg_failed:{type(exc).__name__}"}
    return {"ok": boxed.returncode == 0, "detail": f"toast_failed:{detail}; msg:{boxed.returncode}"}


def _load(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if type(value) is dict else {}


def _save(path, value):
    pending = path.with_suffix(".pending")
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    pending.replace(path)


def run_once(*, root=ROOT, state_dir=STATE_DIR, now_ms=None, notify=toast):
    """One check. Returns what was concluded; side effects are the two files and the notification."""
    if now_ms is None:
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
    root, state_dir = Path(root), Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    run_dir = newest_run(root)
    if run_dir is None:
        result = {"run_id": None, "verdict": "no_run", "problem": None}
    else:
        result = judge(run_dir, now_ms)
    checked = datetime.fromtimestamp(now_ms / 1000, UTC).isoformat()
    result = dict(result, checked_at=checked, root=str(root))
    key = None if result["problem"] is None else f"{result['run_id']}:{result['problem']}"
    state = _load(state_dir / "state.json")
    previous = state.get("key")
    record = None
    if key is None:
        if previous is not None:  # the problem went away (a new run, or the run moved again)
            record = {"time": checked, "run_id": result["run_id"], "problem": None, "cleared": previous,
                      "verdict": result["verdict"]}
            state = {"key": None}
    elif (key != previous or not state.get("notified")
          or now_ms - int(state.get("notified_at_ms") or 0) >= REPEAT_MS):
        message = describe(result)
        sent = notify(TITLE, message)
        record = {"time": checked, "run_id": result["run_id"], "problem": result["problem"], "message": message,
                  "notified": bool(sent.get("ok")), "notify_detail": sent.get("detail"), "repeat": key == previous}
        state = {"key": key, "notified": bool(sent.get("ok")), "notified_at_ms": now_ms}
    if record is not None:
        with (state_dir / "alerts.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        _save(state_dir / "state.json", state)
    _save(state_dir / "last_check.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="folder holding the run folders")
    parser.add_argument("--state-dir", type=Path, default=STATE_DIR, help="where last_check.json and alerts.jsonl go")
    parser.add_argument("--no-notify", action="store_true", help="record only; show no notification")
    args = parser.parse_args(argv)
    try:
        notify = (lambda title, body: {"ok": False, "detail": "no_notify"}) if args.no_notify else toast
        result = run_once(root=args.root, state_dir=args.state_dir, notify=notify)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):  # the Guardian's own failure, recorded
        try:
            args.state_dir.mkdir(parents=True, exist_ok=True)
            with (args.state_dir / "errors.log").open("a", encoding="utf-8") as handle:
                handle.write(datetime.now(UTC).isoformat() + "\n" + traceback.format_exc() + "\n")
        except OSError:
            pass
        return 1
    if sys.stdout is not None:  # pythonw has no console
        json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
        print()
    return 2 if result["problem"] is not None else 0


if __name__ == "__main__":
    sys.exit(main())
