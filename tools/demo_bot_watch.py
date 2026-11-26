"""Read-only check of the newest OKX Demo Bot run: fills and the P6 disaster stop.

Reads only the run folder (status.json, manifest.json, events.jsonl); it never connects
to OKX, never reads credentials and never writes into the run folder. With --state it
remembers the last summary in that file and reports whether anything changed.

For each fill it rebuilds the position and the average entry from the fill rows and
recomputes the stop the way ``catos.protection.stop_price`` does (mark trigger, the
tick rounded towards triggering earlier), then compares it with the next ``protection``
event the Bot wrote after querying OKX.

The verdict is ``stalled`` when the run says running but is not believed (no new bar for over
two bars, or its heartbeat stopped): the rule in ``catos.demo_bot_liveness``, shared with the UI
view and the Guardian. Until 2026-11-27 a run that died without fills stayed ``no_fill_yet``.

    .venv/Scripts/python.exe tools/demo_bot_watch.py [--run <run_id>] [--state <file>]
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from catos.demo_bot_liveness import read_heartbeat, running_problem  # noqa: E402

D = Decimal
ROOT = REPO / "outputs" / "okx-demo-bot"


def expected_stop(average, position, tick, ratio):
    if not ratio or not position:
        return None
    raw = average * (1 - ratio if position > 0 else 1 + ratio)
    rounding = ROUND_CEILING if position > 0 else ROUND_FLOOR  # earlier: long up, short down
    return (raw / tick).to_integral_value(rounding=rounding) * tick


def check(run_dir, now_ms=None):
    if now_ms is None:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
    ratio = D(manifest.get("disaster_stop") or "0")
    tick = D(manifest["contract"]["tick_size"])
    position, average = D("0"), None
    checks, waiting = [], None
    notable = []
    for event in events:
        kind = event["kind"]
        if kind == "bar":
            continue
        if kind == "fill":
            before = position
            for row in event["fills"]:
                quantity, price = D(row["quantity"]), D(row["price"])
                if position == 0 or (position > 0) == (quantity > 0):
                    average = price if position == 0 else (average * abs(position) + price * abs(quantity)) / (
                        abs(position) + abs(quantity))
                position += quantity
                if position == 0:
                    average = None
            if before != 0 and position != 0 and (before > 0) != (position > 0):
                average = D(event["fills"][-1]["price"])  # crossed zero inside one leg (not expected)
            stop = expected_stop(average, position, tick, ratio) if average is not None else None
            waiting = dict(time=event["time"], leg=event["leg"], position=str(position),
                           average=None if average is None else str(average),
                           expected_price=None if stop is None else str(stop),
                           expected_side=None if stop is None else ("sell" if position > 0 else "buy"))
            if stop is None:
                checks.append(dict(waiting, result="no_stop_expected"))
                waiting = None
        elif kind == "protection" and waiting is not None and event.get("price") is not None:
            ok = D(event["price"]) == D(waiting["expected_price"]) and event.get("side") == waiting["expected_side"]
            checks.append(dict(waiting, okx_price=event["price"], okx_side=event.get("side"),
                               algo_id=event.get("algo_id"), result="match" if ok else "MISMATCH"))
            waiting = None
        if kind not in ("started", "day_basis", "resume_input"):
            notable.append({k: v for k, v in event.items() if k not in ("basis", "bar")})
    if waiting is not None:
        checks.append(dict(waiting, result="stop_not_reported_yet"))
    liveness = running_problem(status, read_heartbeat(run_dir), (manifest.get("profile") or {}).get("timeframe_ms"),
                               now_ms)
    if liveness is not None:
        verdict = "stalled"  # says running, is not: checked before anything else
    elif status["fills"] == 0:
        verdict = "no_fill_yet"
    elif any(c["result"] in ("MISMATCH", "stop_not_reported_yet") for c in checks) or any(
            e["kind"] in ("protection_alert", "protection_request_failed", "protection_mismatch",
                          "protection_unconfirmed") for e in notable):
        verdict = "needs_attention"
    else:
        verdict = "ok"
    return dict(run_id=manifest["run_id"], created_at=manifest["created_at"], disaster_stop=str(ratio),
                status=status, verdict=verdict, liveness=liveness, stop_checks=checks, event_count=len(notable), events=notable[-30:])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run", help="run id (default: the newest run folder)")
    parser.add_argument("--state", type=Path, help="file that remembers the last summary")
    parser.add_argument("--root", type=Path, default=ROOT, help="folder holding the run folders")
    args = parser.parse_args(argv)
    runs = sorted((p for p in args.root.iterdir() if (p / "manifest.json").is_file()),
                  key=lambda p: json.loads((p / "manifest.json").read_text(encoding="utf-8"))["created_at"])
    if not runs and not args.run:
        json.dump(dict(verdict="no_run", root=str(args.root)), sys.stdout, ensure_ascii=False, indent=1)
        print()
        return
    run_dir = args.root / args.run if args.run else runs[-1]
    summary = check(run_dir)
    # bars and the liveness verdict are part of the fingerprint: a run that stops producing bars
    # or goes stale is a change (before 2026-11-27 a dead run was "unchanged" for ever).
    fingerprint = hashlib.sha256(json.dumps(
        dict(run=summary["run_id"], state=summary["status"]["state"], fills=summary["status"]["fills"],
             bars=summary["status"].get("bars"), liveness=summary["liveness"], verdict=summary["verdict"],
             stop=summary["status"]["stop_reason"], checks=summary["stop_checks"], events=summary["event_count"]),
        sort_keys=True).encode()).hexdigest()
    if args.state is not None:
        previous = json.loads(args.state.read_text(encoding="utf-8")) if args.state.is_file() else {}
        summary["changed"] = previous.get("fingerprint") != fingerprint
        summary["previous_run_id"] = previous.get("run_id")
        args.state.parent.mkdir(parents=True, exist_ok=True)
        args.state.write_text(json.dumps(dict(fingerprint=fingerprint, run_id=summary["run_id"])), encoding="utf-8")
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
