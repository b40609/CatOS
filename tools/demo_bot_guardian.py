"""Guardian: an outside, read-only check that the OKX Demo Bot is alive and its position covered.

Run by Windows Task Scheduler every five minutes under the user's own account (not a service:
the Bot's key file, account records and locks all live under the user's home). It reads only
run folders (manifest.json, status.json, heartbeat.json, events.jsonl); it never connects to
OKX, never reads credentials, never writes into a run folder and never starts, stops or
resumes a Bot (restarting is ``tools/demo_bot_autostart.py``, a separate task).

What it reports, for the newest run and for any other run whose status still says running:

- running but not believed (no new bar for over two bars, or its heartbeat stopped);
- stopped for a reason the user did not ask for, failed, or never started;
- holding a position with no confirmed disaster stop on OKX for over three minutes;
- stopped on request with a position left on OKX (said once, not repeated);
- the autostart task silent for over fifteen minutes (each task watches the other).

A report goes to this computer (a Windows notification) and to the owner's phone through
OmniKeep when ``~/.catos/owner-alert.json`` points at it (``tools/demo_bot_notify.py``): once
when it appears, again every six hours while it lasts, and "it is over" when it goes away.
Every send is appended to ``outputs/demo-bot-guardian/alerts.jsonl``; every check rewrites
``last_check.json`` there, which the simulation page reads to show when nobody is watching.

    .venv/Scripts/pythonw.exe tools/demo_bot_guardian.py [--root <runs>] [--state-dir <dir>] [--no-notify]

Exit code: 0 nothing to look at, 2 a problem was found, 1 the Guardian itself failed (the
traceback is appended to ``errors.log`` in the state folder, and that failure is announced too).
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _entry in (str(REPO), str(Path(__file__).resolve().parent)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import demo_bot_notify as notifier  # standard library only; catos is imported inside run_once

ROOT = REPO / "outputs" / "okx-demo-bot"
STATE_DIR = REPO / "outputs" / "demo-bot-guardian"
REPEAT_MS = notifier.REPEAT_MS
WATCHER_MAX_MS = 900_000  # three missed five-minute runs
AUTOSTART_CHECK = "autostart_check.json"
TITLE = "CatOS 模擬盤 Bot 需要你看一下"
SELF_TITLE = "CatOS 模擬盤 Bot 的監看程式自己壞了"
toast = notifier.toast  # the local channel, under its old name


def _iso_ms(text):
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return None if moment.tzinfo is None else int(moment.timestamp() * 1000)


def _local(text):
    ms = _iso_ms(text)
    return "不明" if ms is None else datetime.fromtimestamp(ms / 1000).strftime("%m-%d %H:%M")


def describe(result):
    """One line for the notification and the log."""
    from catos.demo_bot_liveness import GAP_REASONS, MESSAGES

    line = f"run {result['run_id'][:8]}：{MESSAGES.get(result['problem'], result['problem'])}"
    if result["problem"] in ("position_unprotected", "stopped_with_position"):
        if result.get("unprotected_why"):
            line += f"（{GAP_REASONS.get(result['unprotected_why'], result['unprotected_why'])}）"
    elif result.get("stop_reason"):
        line += f"（{str(result['stop_reason'])[:80]}）"
    line += f"。部位 {result.get('position')}，最後一根 K 線 {_local(result.get('updated_at'))}。"
    if result["problem"] == "position_unprotected":
        line += "電腦當機或斷線時這個部位沒有停損，請到 OKX 網頁看條件單。"
    elif result["problem"] == "stopped_with_position":
        line += "要繼續就重開 Bot（會接續這個部位），不要了請到 OKX 網頁平倉。"
    return line


def watcher_finding(state_dir, now_ms, *, file_name=AUTOSTART_CHECK, who="自動接續", key="watcher:autostart_silent",
                    consequence="Bot 停下時不會自動接續"):
    """The other scheduled task has been silent too long (it ran before: a missing file is not a finding)."""
    seen = notifier.load(Path(state_dir) / file_name)
    if not seen:
        return None
    checked = _iso_ms(seen.get("checked_at"))
    if checked is not None and now_ms - checked <= WATCHER_MAX_MS:
        return None
    return {"key": key, "run_id": None, "problem": key.split(":", 1)[1], "repeat": True,
            "message": f"{who}的排程超過 15 分鐘沒有執行（最後一次 {_local(seen.get('checked_at'))}）：{consequence}。"
                       "請到工作排程器確認它還在、沒有被停用。"}


def run_once(*, root=ROOT, state_dir=STATE_DIR, now_ms=None, notify=None, external=None):
    """One check. Returns what was concluded; side effects are the state files and the notifications."""
    from catos.demo_bot_liveness import claimed_running, judge, newest_run

    if now_ms is None:
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
    notify = notifier.toast if notify is None else notify
    root, state_dir = Path(root), Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    findings = []

    def note(judged, problem, repeat):
        judged = dict(judged, problem=problem)
        findings.append({"key": f"{judged['run_id']}:{problem}", "run_id": judged["run_id"], "problem": problem,
                         "repeat": repeat, "message": describe(judged)})

    run_dir = newest_run(root)
    if run_dir is None:
        result = {"run_id": None, "verdict": "no_run", "problem": None}
    else:
        result = judge(run_dir, now_ms)
        if result["problem"] is not None:
            note(result, result["problem"], True)
        elif result.get("reminder"):
            note(result, result["reminder"], False)
        for other in claimed_running(root, besides=run_dir):  # the newest folder is not always the live run
            judged = judge(other, now_ms)
            if judged["problem"] is not None:
                note(judged, judged["problem"], True)
    silent = watcher_finding(state_dir, now_ms)
    if silent is not None:
        findings.append(silent)
    checked = datetime.fromtimestamp(now_ms / 1000, UTC).isoformat()
    result = dict(result, checked_at=checked, root=str(root), findings=findings)
    notifier.settle(state_dir, {item["key"] for item in findings}, now_ms, remote=external,
                    fields={"run_id": result["run_id"], "verdict": result["verdict"]})
    for item in findings:
        notifier.deliver(state_dir, item["key"], TITLE, item["message"], now_ms, local=notify, remote=external,
                         repeat=item["repeat"], fields={"run_id": item["run_id"], "problem": item["problem"]})
    notifier.save(state_dir / "last_check.json", result)
    return result


def _own_failure(state_dir, notify, external):
    """The Guardian could not do its check: written down, and said on every channel that still works."""
    detail = traceback.format_exc()
    kind = (sys.exc_info()[0] or Exception).__name__
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        with (state_dir / "errors.log").open("a", encoding="utf-8") as handle:
            handle.write(datetime.now(UTC).isoformat() + "\n" + detail + "\n")
    except OSError:
        pass
    try:
        notifier.deliver(state_dir, "guardian:failed", SELF_TITLE,
                         f"監看程式執行失敗（{kind}）：現在沒有人在看模擬盤 Bot 有沒有停、部位有沒有停損。"
                         "細節在 outputs/demo-bot-guardian/errors.log。", now_ms, local=notify, remote=external,
                         fields={"run_id": None, "problem": "guardian_failed"})
    except Exception:  # noqa: BLE001 - already failing; the exit code and errors.log are what is left
        return 1
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="folder holding the run folders")
    parser.add_argument("--state-dir", type=Path, default=STATE_DIR, help="where last_check.json and alerts.jsonl go")
    parser.add_argument("--no-notify", action="store_true", help="record only; no notification on any channel")
    args = parser.parse_args(argv)

    def silent(title, body):
        return {"ok": False, "final": True, "detail": "no_notify"}

    notify, external = (silent, silent) if args.no_notify else (notifier.toast, notifier.external)
    try:
        result = run_once(root=args.root, state_dir=args.state_dir, notify=notify, external=external)
    except Exception:  # noqa: BLE001 - whatever broke the Guardian has to be said, not swallowed (review F3)
        return _own_failure(args.state_dir, notify, external)
    if sys.stdout is not None:  # pythonw has no console
        json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
        print()
    return 2 if any(item["repeat"] for item in result["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
