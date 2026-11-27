"""Autostart: bring the approved OKX Demo Bot back after an interruption, and never after a risk stop.

Authorised by the user on 2026-11-27 ("3A"): after the computer restarts or the process is
lost, the demo Bot may continue by itself, only with the approved deployment profile and
always with a 10% disaster stop; a risk stop or the Kill-Switch is never restarted, only
announced. Two scheduled tasks under the user's own account use this file:

- every five minutes (the gate): ``pythonw tools/demo_bot_autostart.py``
  reads the run folders and the Kill-Switch record (read-only, no OKX connection) and decides
  ``start``, ``skip`` or ``refuse``. ``start`` asks Task Scheduler to run the second task; a
  ``refuse`` is announced once (this computer, and the phone through OmniKeep when configured).
  It also notices when the Guardian has been silent for over fifteen minutes.
- on demand (the Bot): ``pythonw tools/demo_bot_autostart.py --run-bot``
  decides once more, then runs ``catos.cli demo bot --profile <approved> --disaster-stop 10%``
  in this process with its output appended to ``outputs/demo-bot-guardian/bot-output.log``.
  The Bot lives in its own task, so nothing that started it can take it down by ending.

When it starts the Bot (everything else is left alone):

- the newest run says running but its heartbeat stopped (the process is gone: a restart of
  the computer, a crash, a killed terminal), or it never wrote a status;
- the newest run stopped because OKX could not be read or a bar did not arrive
  (``okx_read_failed``, ``bar_not_published``, ``bar_gap``).

When it refuses and says so: any other stop reason (``risk_flat``, ``manual_kill``,
``flatten_failed``, ``disaster_stop_triggered``, ``position_mismatch`` and the rest), a failed
or unreadable run, the Kill-Switch engaged or unreadable, a last run that used another
profile, and more than three starts in 24 hours. A stop the user asked for, a Bot that is
alive, and no earlier run at all are skipped silently. The Bot's own start checks (approval,
account lock, position against the ledger, Soft/Hard latches) still apply after this gate.

Switch it off: create ``outputs/demo-bot-guardian/autostart.disabled`` (any content).

    .venv/Scripts/pythonw.exe tools/demo_bot_autostart.py [--run-bot] [--dry-run] [--no-notify]

Exit code: 0 skipped or started, 2 refused, 1 this tool itself failed (``errors.log``).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _entry in (str(REPO), str(Path(__file__).resolve().parent)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import demo_bot_guardian as guardian  # standard library only at import time
import demo_bot_notify as notifier

ROOT = guardian.ROOT
STATE_DIR = guardian.STATE_DIR
PROFILE = REPO / "catos" / "deployment_profiles" / "donchian-breakout-15m-192-48.json"
DISASTER_STOP = "10%"  # fixed by the authorisation; never taken from a command line
RUN_TASK = "CatOS-DemoBot-Run"
DISABLED_FILE = "autostart.disabled"
CHECK_FILE = guardian.AUTOSTART_CHECK
HISTORY_FILE = "autostart.jsonl"
STATE_FILE = "autostart_state.json"
BOT_LOG = "bot-output.log"
RESUMABLE_STOPS = ("okx_read_failed", "bar_not_published", "bar_gap", "process_lost")
RISK_STOPS = ("risk_flat", "manual_kill", "flatten_failed", "flatten_incomplete")
DAY_MS = 86_400_000
COOLDOWN_MS = 600_000
MAX_STARTS = 3       # per 24 hours, starts whose Bot got going
MAX_FAST_FAILS = 6   # per 24 hours, starts whose Bot ended within two minutes (e.g. no network yet)
FAST_FAIL_S = 120
TITLE = "CatOS 模擬盤 Bot 自動接續"

REASONS = {
    "disabled_by_file": "自動接續已用 autostart.disabled 關閉",
    "no_previous_run": "沒有可以接續的 run（自動接續不會從零開一個新的）",
    "already_running": "Bot 正在跑",
    "starting": "Bot 正在啟動",
    "alive_but_stalled": "Bot 的程序還在，但沒有新的 K 線；不重複啟動",
    "stopped_by_operator": "Bot 是你要它停的",
    "cooling_down": "10 分鐘內才啟動過一次，先等一下",
    "process_lost": "程序不在了（重開機、當機或終端機被關掉）",
    "never_started": "上一次啟動沒有跑起來",
    "transient_stop": "上一次是因為讀不到 OKX 或 K 線沒到而停下",
    "risk_stop": "上一次是風控停機（Hard 日損或 Kill-Switch 清倉）",
    "kill_switch_engaged": "Kill-Switch 目前是觸發狀態",
    "kill_switch_unreadable": "Kill-Switch 紀錄讀不到，當成已觸發",
    "needs_review": "上一次停下的原因需要你看過",
    "run_failed": "上一次是程式錯誤結束",
    "status_unreadable": "上一次 run 的狀態讀不到",
    "profile_differs": "上一次 run 用的不是核准的正式部署設定",
    "profile_unreadable": "核准的部署設定檔讀不到",
    "too_many_restarts": "24 小時內已經自動接續 3 次",
    "too_many_failed_starts": "24 小時內啟動失敗太多次",
    "launch_failed": "要求工作排程器啟動 Bot 失敗",
}


def _now_ms():
    return int(datetime.now(UTC).timestamp() * 1000)


def _text(now_ms):
    return datetime.fromtimestamp(now_ms / 1000, UTC).isoformat()


def history(state_dir, now_ms):
    """Rows of the last 24 hours from autostart.jsonl (unreadable lines are skipped)."""
    rows = []
    try:
        lines = (Path(state_dir) / HISTORY_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        at = guardian._iso_ms(row.get("time")) if type(row) is dict else None
        if at is not None and now_ms - at < DAY_MS:
            rows.append(dict(row, at_ms=at))
    return rows


def record(state_dir, now_ms, **row):
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / HISTORY_FILE).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(time=_text(now_ms), **row), ensure_ascii=False) + "\n")


def decide(*, root=ROOT, state_dir=STATE_DIR, now_ms=None, kill_path=None, profile=PROFILE, rate_limit=True):
    """``{"action": "start" | "skip" | "refuse", "reason": ..., "run_id": ..., "stop_reason": ...}``.

    Reads files only. Anything it cannot read or does not recognise is a refusal, never a start.
    """
    from catos.demo_bot_liveness import _read, claimed_running, judge, newest_run
    from catos.kill_switch import status as kill_switch_status

    now_ms = _now_ms() if now_ms is None else now_ms
    root, state_dir = Path(root), Path(state_dir)

    def answer(action, reason, judged=None):
        judged = judged or {}
        return {"action": action, "reason": reason, "run_id": judged.get("run_id"),
                "stop_reason": judged.get("stop_reason"), "position": judged.get("position")}

    if (state_dir / DISABLED_FILE).exists():
        return answer("skip", "disabled_by_file")
    run_dir = newest_run(root)
    if run_dir is None:
        return answer("skip", "no_previous_run")
    judged = judge(run_dir, now_ms)
    for other in claimed_running(root, besides=run_dir):
        seen = judge(other, now_ms)
        # Another run folder holds the live Bot: the same "its process is there" answers as for the
        # newest one below, a live Bot without a confirmed stop or waiting for a bar included (review R3).
        if seen["verdict"] == "alive" or seen["problem"] in ("position_unprotected", "bars_stalled"):
            return answer("skip", "already_running", judged)
    verdict, problem = judged["verdict"], judged["problem"]
    if verdict == "alive" or problem == "position_unprotected":
        return answer("skip", "already_running", judged)
    if verdict == "starting":
        return answer("skip", "starting", judged)
    if verdict == "stopped_by_operator":
        return answer("skip", "stopped_by_operator", judged)
    if problem == "bars_stalled":  # the heartbeat is fresh: a second Bot would only hit the account lock
        return answer("skip", "alive_but_stalled", judged)
    if problem in ("process_lost", "never_started"):
        why = problem
    elif problem == "abnormal_stop":
        stop_reason = str(judged.get("stop_reason") or "")
        if stop_reason.startswith(RISK_STOPS):
            return answer("refuse", "risk_stop", judged)
        if not stop_reason.startswith(RESUMABLE_STOPS):
            return answer("refuse", "needs_review", judged)
        why = "transient_stop"
    elif problem == "failed":
        return answer("refuse", "run_failed", judged)
    else:
        return answer("refuse", "status_unreadable", judged)
    kill = kill_switch_status(kill_path)
    if kill["engaged"]:
        return answer("refuse", "kill_switch_unreadable" if kill["error"] else "kill_switch_engaged", judged)
    manifest, _ = _read(run_dir / "manifest.json")
    try:
        from catos import strategy_approvals

        approved = strategy_approvals.load_profile(profile)
    except Exception:  # noqa: BLE001 - whatever is wrong with the profile, the answer is the same: do not start
        return answer("refuse", "profile_unreadable", judged)
    if (manifest or {}).get("profile") != approved:
        return answer("refuse", "profile_differs", judged)
    if rate_limit:
        rows = history(state_dir, now_ms)
        starts = [row for row in rows if row.get("action") == "start"]
        fast = [row for row in rows if row.get("action") == "bot_exit"
                and type(row.get("seconds")) is int and row["seconds"] < FAST_FAIL_S]
        if len(fast) >= MAX_FAST_FAILS:
            return answer("refuse", "too_many_failed_starts", judged)
        if len(starts) - len(fast) >= MAX_STARTS:
            return answer("refuse", "too_many_restarts", judged)
        if starts and now_ms - starts[-1]["at_ms"] < COOLDOWN_MS:
            return answer("skip", "cooling_down", judged)
    return answer("start", why, judged)


def describe(decision):
    run = f"run {str(decision['run_id'])[:8]}" if decision.get("run_id") else "模擬盤 Bot"
    line = f"{run}：{REASONS.get(decision['reason'], decision['reason'])}"
    if decision.get("stop_reason"):
        line += f"（{str(decision['stop_reason'])[:80]}）"
    line += f"。部位 {decision.get('position')}。"
    if decision["action"] == "start":
        return line + f"已自動接續，固定帶 {DISASTER_STOP} 保底停損；接續後的狀況由監看程式另外通知。"
    return line + "不會自動重開，要你看過之後手動處理。"


def launch():
    """Ask Task Scheduler to run the Bot's own task; the Bot never becomes a child of this process."""
    try:
        done = subprocess.run(["schtasks.exe", "/Run", "/TN", RUN_TASK], capture_output=True, text=True,
                              errors="replace", timeout=60,  # schtasks answers in the console code page
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "detail": f"{type(exc).__name__}"}
    return {"ok": done.returncode == 0, "detail": f"schtasks:{done.returncode}"}


def _not_the_real_folders():
    return {"ok": False, "detail": "not_the_real_run_folders"}


def _same_path(a, b):
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return False


def gate_once(*, root=ROOT, state_dir=STATE_DIR, now_ms=None, kill_path=None, profile=PROFILE, notify=None,
              external=None, start=None, dry_run=False):
    """One five-minute check: decide, act, announce, and leave a trace the Guardian can watch.

    ``start`` defaults to the real task only for the real run folders and state folder: the task
    decides on those, and an isolated check that forgot ``start`` must never run it (review R3).
    """
    now_ms = _now_ms() if now_ms is None else now_ms
    notify = notifier.toast if notify is None else notify
    state_dir = Path(state_dir)
    if start is None:
        start = launch if _same_path(root, ROOT) and _same_path(state_dir, STATE_DIR) else _not_the_real_folders
    state_dir.mkdir(parents=True, exist_ok=True)
    decision = decide(root=root, state_dir=state_dir, now_ms=now_ms, kill_path=kill_path, profile=profile)
    active = set()
    if decision["action"] == "start" and not dry_run:
        started = start()
        decision["launch"] = started
        # Only a launch Task Scheduler accepted is a start (cooling down and the daily limit count
        # these). A failed one is retried next time and stays one alert while it lasts (review R2).
        record(state_dir, now_ms, action="start" if started.get("ok") else "launch_failed",
               reason=decision["reason"], run_id=decision["run_id"], stop_reason=decision["stop_reason"],
               launch_detail=started.get("detail"))
        if started.get("ok"):
            message = describe(decision)
            sent = [notifier._safely(channel, TITLE, message) for channel in (notify, external or notifier._nowhere)]
            record(state_dir, now_ms, action="start_announced", run_id=decision["run_id"],
                   notified=bool(sent[0].get("ok")), external=bool(sent[1].get("ok")),
                   external_detail=sent[1].get("detail"))
        else:
            decision = dict(decision, action="refuse", reason="launch_failed")
    if decision["action"] == "refuse":
        key = f"autostart:{decision['run_id']}:{decision['reason']}"
        active.add(key)
        if not dry_run:
            notifier.deliver(state_dir, key, TITLE, describe(decision), now_ms, local=notify, remote=external,
                             repeat=False, state_file=STATE_FILE, log_file=HISTORY_FILE,
                             fields={"action": "refuse_announced", "run_id": decision["run_id"],
                                     "reason": decision["reason"]})
    # The Guardian is the one that tells the owner about the Bot: if it went silent, say so from here.
    silent = guardian.watcher_finding(state_dir, now_ms, file_name="last_check.json", who="監看（Guardian）",
                                      key="watcher:guardian_silent",
                                      consequence="Bot 停下或部位沒有停損時不會有人通知你")
    if silent is not None:
        active.add(silent["key"])
        if not dry_run:
            notifier.deliver(state_dir, silent["key"], guardian.SELF_TITLE, silent["message"], now_ms, local=notify,
                             remote=external, state_file=STATE_FILE, log_file=HISTORY_FILE,
                             fields={"action": "guardian_silent"})
    if not dry_run:
        notifier.settle(state_dir, active, now_ms, remote=external, state_file=STATE_FILE, log_file=HISTORY_FILE)
        notifier.save(state_dir / CHECK_FILE, dict(decision, checked_at=_text(now_ms), guardian_silent=silent is not None))
    return dict(decision, guardian_silent=silent is not None)


def run_bot(*, root=ROOT, state_dir=STATE_DIR, now_ms=None, kill_path=None, profile=PROFILE, bot=None):
    """The Bot's own task: decide once more (no rate limit: the gate, or the user by hand, asked), then run it."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    began = _now_ms() if now_ms is None else now_ms
    decision = decide(root=root, state_dir=state_dir, now_ms=began, kill_path=kill_path, profile=profile,
                      rate_limit=False)
    if decision["action"] != "start":
        record(state_dir, began, action="bot_not_started", reason=decision["reason"], run_id=decision["run_id"])
        return 0 if decision["action"] == "skip" else 2
    arguments = ["--profile", str(profile), "--disaster-stop", DISASTER_STOP]
    record(state_dir, began, action="bot_started", run_id=decision["run_id"], arguments=arguments)
    if bot is None:
        from catos import demo_bot

        bot = demo_bot.cli_main
    saved = sys.stdout, sys.stderr
    code, wall = None, _now_ms()
    try:
        with (state_dir / BOT_LOG).open("a", encoding="utf-8", buffering=1) as stream:  # line buffered: readable live
            sys.stdout = sys.stderr = stream
            print(f"\n==== {_text(began)} autostart: {' '.join(arguments)} ====")
            try:
                code = bot(arguments)
            except BaseException:
                traceback.print_exc()
                raise
            finally:
                sys.stdout, sys.stderr = saved
    finally:
        lasted = (_now_ms() - wall) // 1000
        record(state_dir, began + lasted * 1000, action="bot_exit", code=code, seconds=lasted,
               run_id=decision["run_id"])
    return 0 if code == 0 else 1


def _own_failure(state_dir, notify, external):
    detail = traceback.format_exc()
    kind = (sys.exc_info()[0] or Exception).__name__
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        with (state_dir / "errors.log").open("a", encoding="utf-8") as handle:
            handle.write(datetime.now(UTC).isoformat() + " autostart\n" + detail + "\n")
    except OSError:
        return 1
    try:
        notifier.deliver(state_dir, "autostart:failed", TITLE,
                         f"自動接續程式執行失敗（{kind}）：Bot 停下時不會自動接續。"
                         "細節在 outputs/demo-bot-guardian/errors.log。", _now_ms(), local=notify, remote=external,
                         state_file=STATE_FILE, log_file=HISTORY_FILE, fields={"action": "autostart_failed"})
    except Exception:  # noqa: BLE001 - already failing; errors.log and the exit code are what is left
        return 1
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="folder holding the run folders")
    parser.add_argument("--state-dir", type=Path, default=STATE_DIR)
    parser.add_argument("--run-bot", action="store_true", help="the Bot's own task: decide once more, then run the Bot")
    parser.add_argument("--dry-run", action="store_true", help="only print the decision: start nothing, write nothing")
    parser.add_argument("--no-notify", action="store_true", help="record only; no notification on any channel")
    args = parser.parse_args(argv)

    def silent(title, body):
        return {"ok": False, "final": True, "detail": "no_notify"}

    notify, external = (silent, silent) if args.no_notify else (notifier.toast, notifier.external)
    try:
        if args.run_bot and not args.dry_run:
            return run_bot(root=args.root, state_dir=args.state_dir)
        result = gate_once(root=args.root, state_dir=args.state_dir, notify=notify, external=external,
                           dry_run=args.dry_run)
    except Exception:  # noqa: BLE001 - whatever broke this tool has to be said, not swallowed
        return _own_failure(args.state_dir, notify, external)
    if sys.stdout is not None:  # pythonw has no console
        json.dump(result, sys.stdout, ensure_ascii=False, indent=1)
        print()
    return 2 if result["action"] == "refuse" else 0


if __name__ == "__main__":
    sys.exit(main())
