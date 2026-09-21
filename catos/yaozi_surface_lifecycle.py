"""Descriptive lifecycle analysis for captured Yaozi signal-surface events.

This module intentionally analyzes only rendered UI observations. It does not
map event labels to unpublished Yaozi gates, scores, or causal rules.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path


SAMPLE_SCHEMA = "catos-yaozi-signal-surface-sample-v1"
ANALYSIS_SCHEMA = "catos-yaozi-surface-lifecycle-analysis-v1"
CANDIDATE_VIEWS = frozenset({"leading", "momentum", "opportunity", "risk"})


def _event_class(title: str) -> str:
    return title.split(" · ", 1)[0].strip()


def _parse_minute(sample_date: str, observed_at_text: str) -> datetime:
    year = datetime.strptime(sample_date, "%Y-%m-%d").year
    return datetime.strptime(f"{year}/{observed_at_text}", "%Y/%m/%d %H:%M")


def _load_events(path: Path) -> tuple[list[dict], int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != SAMPLE_SCHEMA:
        raise ValueError(f"unsupported_sample_schema:{path}")
    if payload.get("timezone") != "Asia/Taipei":
        raise ValueError(f"unsupported_timezone:{path}")
    sample_date = payload.get("sample_date")
    if type(sample_date) is not str:
        raise ValueError(f"missing_sample_date:{path}")

    events = []
    excluded = 0
    for raw in payload.get("signal_surface", {}).get("events", []):
        if raw.get("view") not in CANDIDATE_VIEWS:
            excluded += 1
            continue
        required = ("observed_at_text", "symbol", "view", "category_text", "event_title")
        if any(type(raw.get(name)) is not str or not raw[name] for name in required):
            raise ValueError(f"invalid_surface_event:{path}")
        observed = _parse_minute(sample_date, raw["observed_at_text"])
        events.append({
            "observed_at_text": raw["observed_at_text"],
            "sort_minute": observed,
            "symbol": raw["symbol"],
            "view": raw["view"],
            "category_text": raw["category_text"],
            "event_title": raw["event_title"],
            "event_class": _event_class(raw["event_title"]),
            "source_sample": path.name,
        })
    return events, excluded


def analyze_surface_samples(paths: list[Path]) -> dict:
    if not paths:
        raise ValueError("no_sample_paths")

    deduped: dict[tuple[str, str, str, str, str], dict] = {}
    excluded_non_candidate_events = 0
    source_samples = []
    for path in sorted(paths, key=lambda item: item.name):
        source_samples.append(path.name)
        events, excluded = _load_events(path)
        excluded_non_candidate_events += excluded
        for event in events:
            key = (
                event["observed_at_text"], event["symbol"], event["view"],
                event["category_text"], event["event_title"],
            )
            existing = deduped.get(key)
            if existing is None:
                event["source_samples"] = [event.pop("source_sample")]
                deduped[key] = event
            elif event["source_sample"] not in existing["source_samples"]:
                existing["source_samples"].append(event["source_sample"])

    by_symbol = defaultdict(list)
    for event in deduped.values():
        by_symbol[event["symbol"]].append(event)

    class_transitions = Counter()
    view_transitions = Counter()
    transition_records = []
    ambiguous_groups = []
    sequences = []

    for symbol in sorted(by_symbol):
        events = sorted(
            by_symbol[symbol],
            key=lambda item: (
                item["sort_minute"], item["view"], item["event_title"], item["category_text"]
            ),
        )
        minute_groups = defaultdict(list)
        for event in events:
            minute_groups[event["sort_minute"]].append(event)
        for minute, group in sorted(minute_groups.items()):
            if len(group) > 1:
                ambiguous_groups.append({
                    "symbol": symbol,
                    "observed_at_text": group[0]["observed_at_text"],
                    "event_titles": sorted(item["event_title"] for item in group),
                    "reason": "ui_minute_precision_cannot_order_same_minute_events",
                })

        ordered_minutes = sorted(minute_groups)
        for previous_minute, current_minute in zip(ordered_minutes, ordered_minutes[1:]):
            previous_group = minute_groups[previous_minute]
            current_group = minute_groups[current_minute]
            if len(previous_group) != 1 or len(current_group) != 1:
                continue
            previous = previous_group[0]
            current = current_group[0]
            elapsed_minutes = int((current_minute - previous_minute).total_seconds() // 60)
            class_key = f"{previous['event_class']} -> {current['event_class']}"
            view_key = f"{previous['view']} -> {current['view']}"
            class_transitions[class_key] += 1
            view_transitions[view_key] += 1
            transition_records.append({
                "symbol": symbol,
                "from_time_text": previous["observed_at_text"],
                "to_time_text": current["observed_at_text"],
                "elapsed_minutes": elapsed_minutes,
                "from_view": previous["view"],
                "to_view": current["view"],
                "from_event_title": previous["event_title"],
                "to_event_title": current["event_title"],
                "same_cycle_status": "unknown_unpublished",
            })

        if len(events) >= 2:
            sequences.append({
                "symbol": symbol,
                "events": [
                    {
                        "observed_at_text": event["observed_at_text"],
                        "view": event["view"],
                        "event_title": event["event_title"],
                        "category_text": event["category_text"],
                        "source_samples": sorted(event["source_samples"]),
                    }
                    for event in events
                ],
            })

    timing_by_class = defaultdict(list)
    for record in transition_records:
        key = f"{_event_class(record['from_event_title'])} -> {_event_class(record['to_event_title'])}"
        timing_by_class[key].append(record["elapsed_minutes"])

    class_summary = []
    for transition, count in sorted(class_transitions.items(), key=lambda item: (-item[1], item[0])):
        timings = timing_by_class[transition]
        class_summary.append({
            "transition": transition,
            "count": count,
            "min_elapsed_minutes": min(timings),
            "max_elapsed_minutes": max(timings),
        })

    return {
        "schema": ANALYSIS_SCHEMA,
        "source_samples": source_samples,
        "candidate_views": sorted(CANDIDATE_VIEWS),
        "event_precision": "minute",
        "deduplication_key": [
            "observed_at_text", "symbol", "view", "category_text", "event_title"
        ],
        "counts": {
            "source_samples": len(source_samples),
            "unique_candidate_events": len(deduped),
            "symbols": len(by_symbol),
            "ordered_transitions": len(transition_records),
            "ambiguous_same_minute_groups": len(ambiguous_groups),
            "excluded_non_candidate_events": excluded_non_candidate_events,
        },
        "event_class_transitions": class_summary,
        "view_transitions": [
            {"transition": transition, "count": count}
            for transition, count in sorted(view_transitions.items(), key=lambda item: (-item[1], item[0]))
        ],
        "ordered_transitions": transition_records,
        "ambiguous_same_minute_groups": ambiguous_groups,
        "symbol_sequences": sequences,
        "interpretation": (
            "descriptive rendered-surface ordering only; same-minute events are not ordered; "
            "adjacent events are not asserted to belong to the same private Yaozi cycle; "
            "private thresholds, gates, taxonomy mappings, and causality remain unknown_unpublished"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze captured Yaozi surface lifecycle sequences")
    parser.add_argument("samples", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = analyze_surface_samples(args.samples)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
