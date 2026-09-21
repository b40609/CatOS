"""Offline timing alignment between public candidates and observed Yaozi events.

This module performs no network I/O and never promotes a public candidate into
a Yaozi event. It only answers whether already-persisted candidate evidence was
observed before an event that was visible in a supplied black-box sample.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from catos.market_api import MarketIntelReader


ALIGNMENT_WINDOWS_MINUTES = (5, 15, 60)
_EVENT_LINE = re.compile(
    r"^(?P<event_type>[A-Z][A-Z0-9_]*)\b.*\s"
    r"(?P<month>\d{2})/(?P<day>\d{2})\s(?P<hour>\d{2}):(?P<minute>\d{2})$"
)
_SURFACE_TIME = re.compile(
    r"^(?P<month>\d{2})/(?P<day>\d{2})\s(?P<hour>\d{2}):(?P<minute>\d{2})$"
)


def _sample_year(sample):
    value = sample.get("sample_date")
    if type(value) is not str:
        raise ValueError("invalid_sample_date")
    try:
        return datetime.strptime(value, "%Y-%m-%d").year
    except ValueError:
        raise ValueError("invalid_sample_date") from None


def _sample_timezone(sample):
    value = sample.get("timezone")
    if type(value) is not str or not value:
        raise ValueError("invalid_sample_timezone")
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        raise ValueError("invalid_sample_timezone") from None


def _extract_detail_events(sample, *, source_name):
    year = _sample_year(sample)
    timezone = _sample_timezone(sample)
    details = sample.get("yaozi_detail_samples", [])
    if type(details) is not list:
        raise ValueError("invalid_yaozi_sample")
    events = []
    issues = []
    for detail in details:
        if type(detail) is not dict or type(detail.get("symbol")) is not str:
            issues.append({"source": source_name, "code": "invalid_detail_sample"})
            continue
        symbol = detail["symbol"]
        recent = detail.get("recent_events")
        if type(recent) is not list:
            continue
        for raw in recent:
            if type(raw) is not str:
                issues.append({"source": source_name, "symbol": symbol, "code": "invalid_event_text"})
                continue
            match = _EVENT_LINE.match(raw)
            if match is None:
                issues.append({
                    "source": source_name,
                    "symbol": symbol,
                    "code": "unparsed_event_text",
                    "text": raw,
                })
                continue
            try:
                observed = datetime(
                    year,
                    int(match["month"]),
                    int(match["day"]),
                    int(match["hour"]),
                    int(match["minute"]),
                    tzinfo=timezone,
                )
            except ValueError:
                issues.append({
                    "source": source_name,
                    "symbol": symbol,
                    "code": "invalid_event_time",
                    "text": raw,
                })
                continue
            events.append({
                "source": source_name,
                "symbol": f"{symbol}-USDT-SWAP",
                "event_type": match["event_type"],
                "observed_at_ms": int(observed.timestamp() * 1000),
                "raw_text": raw,
                "taxonomy_comparable": True,
            })
    return events, issues


def _extract_signal_surface_events(sample, *, source_name):
    year = _sample_year(sample)
    timezone = _sample_timezone(sample)
    surface = sample.get("signal_surface")
    if type(surface) is not dict or type(surface.get("events")) is not list:
        raise ValueError("invalid_yaozi_sample")
    events = []
    issues = []
    for row in surface["events"]:
        if type(row) is not dict:
            issues.append({"source": source_name, "code": "invalid_signal_surface_event"})
            continue
        symbol = row.get("symbol")
        raw_time = row.get("observed_at_text")
        title = row.get("event_title")
        if type(symbol) is not str or not symbol or type(raw_time) is not str or type(title) is not str:
            issues.append({"source": source_name, "code": "invalid_signal_surface_event"})
            continue
        match = _SURFACE_TIME.match(raw_time)
        if match is None:
            issues.append({
                "source": source_name,
                "symbol": symbol,
                "code": "unparsed_signal_surface_time",
                "text": raw_time,
            })
            continue
        try:
            observed = datetime(
                year,
                int(match["month"]),
                int(match["day"]),
                int(match["hour"]),
                int(match["minute"]),
                tzinfo=timezone,
            )
        except ValueError:
            issues.append({
                "source": source_name,
                "symbol": symbol,
                "code": "invalid_signal_surface_time",
                "text": raw_time,
            })
            continue
        events.append({
            "source": source_name,
            "symbol": f"{symbol}-USDT-SWAP",
            "event_type": "SIGNAL_SURFACE_EVENT",
            "observed_at_ms": int(observed.timestamp() * 1000),
            "raw_text": title,
            "taxonomy_comparable": False,
            "surface_view": row.get("view"),
            "surface_category_text": row.get("category_text"),
            "surface_event_title": title,
        })
    return events, issues


def extract_observed_events(sample, *, source_name="sample"):
    """Parse only explicit event name/time facts from supported Yaozi samples."""
    if type(sample) is not dict:
        raise ValueError("invalid_yaozi_sample")
    schema = sample.get("schema")
    if schema == "catos-yaozi-blackbox-sample-v1":
        events, issues = _extract_detail_events(sample, source_name=source_name)
    elif schema == "catos-yaozi-signal-surface-sample-v1":
        events, issues = _extract_signal_surface_events(sample, source_name=source_name)
    else:
        raise ValueError("invalid_yaozi_sample")
    events.sort(key=lambda item: (
        item["observed_at_ms"], item["symbol"], item["event_type"], item["source"], item["raw_text"]))
    return events, issues


def align_candidates(events, candidates, *, windows_minutes=ALIGNMENT_WINDOWS_MINUTES):
    """Return preceding candidate evidence for each event, without causal inference."""
    if type(events) is not list or type(candidates) is not list:
        raise ValueError("invalid_alignment_input")
    if (type(windows_minutes) is not tuple or not windows_minutes
            or any(type(value) is not int or value <= 0 for value in windows_minutes)
            or tuple(sorted(set(windows_minutes))) != windows_minutes):
        raise ValueError("invalid_alignment_windows")
    by_symbol = {}
    for candidate in candidates:
        if type(candidate) is not dict:
            raise ValueError("invalid_candidate")
        symbol = candidate.get("symbol")
        observed_at_ms = candidate.get("observed_at_ms")
        if type(symbol) is not str or type(observed_at_ms) is not int:
            raise ValueError("invalid_candidate")
        by_symbol.setdefault(symbol, []).append(candidate)
    for rows in by_symbol.values():
        rows.sort(key=lambda item: (item["observed_at_ms"], item.get("candidate_id", "")))

    aligned = []
    largest_window_ms = windows_minutes[-1] * 60_000
    for event in events:
        symbol = event.get("symbol")
        event_ms = event.get("observed_at_ms")
        event_type = event.get("event_type")
        if type(symbol) is not str or type(event_ms) is not int or type(event_type) is not str:
            raise ValueError("invalid_observed_event")
        preceding = []
        for candidate in by_symbol.get(symbol, ()):
            delta_ms = event_ms - candidate["observed_at_ms"]
            if delta_ms < 0 or delta_ms > largest_window_ms:
                continue
            possible = candidate.get("possible_yaozi_event_types_json")
            if type(possible) is not list:
                possible = []
            taxonomy_comparable = event.get("taxonomy_comparable", True)
            preceding.append({
                "candidate_id": candidate.get("candidate_id"),
                "candidate_type": candidate.get("candidate_type"),
                "candidate_observed_at_ms": candidate["observed_at_ms"],
                "lead_ms": delta_ms,
                "lead_minutes_text": str(delta_ms // 60_000),
                "taxonomy_compatible": event_type in possible if taxonomy_comparable else None,
                "possible_yaozi_event_types": possible,
                "evidence": candidate.get("evidence_json"),
                "source_snapshot_ids": candidate.get("source_snapshot_ids_json"),
            })
        preceding.sort(key=lambda item: (item["lead_ms"], item["candidate_id"] or ""))
        window_counts = {
            f"{minutes}m": sum(item["lead_ms"] <= minutes * 60_000 for item in preceding)
            for minutes in windows_minutes
        }
        aligned.append({
            **event,
            "window_counts": window_counts,
            "preceding_candidates": preceding,
        })
    return aligned


def summarize_alignment(events, *, windows_minutes=ALIGNMENT_WINDOWS_MINUTES):
    """Summarize observational links without converting them into trigger evidence."""
    if type(events) is not list:
        raise ValueError("invalid_alignment_input")
    if (type(windows_minutes) is not tuple or not windows_minutes
            or any(type(value) is not int or value <= 0 for value in windows_minutes)
            or tuple(sorted(set(windows_minutes))) != windows_minutes):
        raise ValueError("invalid_alignment_windows")

    window_link_counts = {}
    window_event_counts = {}
    taxonomy_compatible_link_counts = {}
    for minutes in windows_minutes:
        label = f"{minutes}m"
        link_count = 0
        event_count = 0
        compatible_count = 0
        limit_ms = minutes * 60_000
        for event in events:
            preceding = event.get("preceding_candidates")
            if type(preceding) is not list:
                raise ValueError("invalid_aligned_event")
            in_window = [item for item in preceding if item.get("lead_ms", limit_ms + 1) <= limit_ms]
            link_count += len(in_window)
            event_count += bool(in_window)
            compatible_count += sum(item.get("taxonomy_compatible") is True for item in in_window)
        window_link_counts[label] = link_count
        window_event_counts[label] = event_count
        taxonomy_compatible_link_counts[label] = compatible_count

    candidate_type_link_counts = {}
    largest_window_ms = windows_minutes[-1] * 60_000
    for event in events:
        for item in event["preceding_candidates"]:
            if item["lead_ms"] > largest_window_ms:
                continue
            candidate_type = item.get("candidate_type")
            if type(candidate_type) is not str or not candidate_type:
                candidate_type = "UNKNOWN"
            candidate_type_link_counts[candidate_type] = candidate_type_link_counts.get(candidate_type, 0) + 1

    return {
        "window_link_counts": window_link_counts,
        "window_event_counts": window_event_counts,
        "taxonomy_compatible_link_counts": taxonomy_compatible_link_counts,
        "largest_window_minutes": windows_minutes[-1],
        "candidate_type_link_counts_largest_window": dict(sorted(candidate_type_link_counts.items())),
    }


def build_alignment_report(db_path, sample_paths, *, limit=1000):
    if not sample_paths:
        raise ValueError("sample_required")
    reader = MarketIntelReader(db_path)
    events = []
    issues = []
    sources = []
    for raw_path in sample_paths:
        path = Path(raw_path)
        with path.open("r", encoding="utf-8") as handle:
            sample = json.load(handle)
        parsed, parsed_issues = extract_observed_events(sample, source_name=path.name)
        events.extend(parsed)
        issues.extend(parsed_issues)
        sources.append(path.name)
    events.sort(key=lambda item: (
        item["observed_at_ms"], item["symbol"], item["event_type"], item["source"], item["raw_text"]))
    largest_window_ms = ALIGNMENT_WINDOWS_MINUTES[-1] * 60_000
    candidate_result = reader.event_candidates_for_windows([
        (event["symbol"], max(0, event["observed_at_ms"] - largest_window_ms),
         event["observed_at_ms"])
        for event in events
    ], limit=limit)
    for window in candidate_result["windows"]:
        if window["truncated"]:
            issues.append({"code": "candidate_window_truncated", **window})
    aligned = align_candidates(events, candidate_result["items"])
    query_status = (
        "no_observed_events" if not events else
        "truncated" if candidate_result["truncated"] else "complete_stored_rows"
    )
    return {
        "contract": "catos_yaozi_candidate_alignment_v1",
        "interpretation": "observational_timing_only_no_trigger_threshold_or_causality_inference",
        "windows_minutes": list(ALIGNMENT_WINDOWS_MINUTES),
        "sample_sources": sources,
        "candidate_count": len(candidate_result["items"]),
        "candidate_query": {
            "scope": "per_symbol_pre_event_windows_inclusive",
            "consistency": "single_sqlite_read_snapshot",
            "status": query_status,
            "limit_per_window": candidate_result["limit_per_window"],
            "windows": candidate_result["windows"],
            "source_coverage": "unknown_not_measured_by_candidate_alignment",
        },
        "count_semantics": (
            "lower_bound_due_to_query_limit" if candidate_result["truncated"]
            else "stored_candidate_links_per_observation"
        ),
        "observed_event_count": len(events),
        "issues": issues,
        "alignment_summary": summarize_alignment(aligned),
        "events": aligned,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Align persisted public candidates to Yaozi samples")
    parser.add_argument("--db", default="outputs/catos-market-intel-v14.sqlite")
    parser.add_argument("--sample", action="append", required=True)
    parser.add_argument("--limit", type=int, default=1000,
                        help="Maximum candidates per symbol/event window (1..1000); truncation is reported")
    args = parser.parse_args(argv)
    report = build_alignment_report(Path(args.db), [Path(value) for value in args.sample], limit=args.limit)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
