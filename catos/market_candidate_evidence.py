"""Score public candidate follow-up against observed Yaozi signal-surface events.

This is descriptive evidence analysis only. A public candidate is never promoted
into a Yaozi event, and missing rendered events are not treated as proof that a
private Yaozi gate failed.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path

from catos.market_api import MarketIntelReader
from catos.market_candidate_alignment import extract_observed_events


EVIDENCE_WINDOWS_MINUTES = (5, 15, 30, 60)


def _capture_anchor_ms(sample):
    value = sample.get("capture_anchor")
    if type(value) is not str or not value:
        raise ValueError("invalid_capture_anchor")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("invalid_capture_anchor") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("invalid_capture_anchor")
    return int(parsed.timestamp() * 1000)


def _ratio_text(numerator, denominator):
    if denominator == 0:
        return None
    value = Decimal(numerator) / Decimal(denominator)
    return format(value.quantize(Decimal("0.000001")), "f")


def _sample_candidate_population(sample):
    if sample.get("schema") != "catos-yaozi-signal-surface-sample-v1":
        raise ValueError("unsupported_evidence_sample")
    public = sample.get("public_collection")
    if type(public) is not dict:
        raise ValueError("missing_public_collection")
    observed_at_ms = public.get("comparison_observed_at_ms")
    rows = public.get("candidates")
    if type(observed_at_ms) is not int or observed_at_ms < 0 or type(rows) is not list:
        raise ValueError("invalid_public_collection")
    candidates = []
    seen = set()
    for row in rows:
        if type(row) is not dict:
            raise ValueError("invalid_public_candidate")
        symbol = row.get("symbol")
        candidate_type = row.get("candidate_type")
        if type(symbol) is not str or not symbol or type(candidate_type) is not str or not candidate_type:
            raise ValueError("invalid_public_candidate")
        key = (symbol, candidate_type, observed_at_ms)
        if key in seen:
            raise ValueError("duplicate_public_candidate")
        seen.add(key)
        candidates.append({
            "symbol": symbol,
            "candidate_type": candidate_type,
            "observed_at_ms": observed_at_ms,
        })
    candidates.sort(key=lambda item: (item["observed_at_ms"], item["symbol"], item["candidate_type"]))
    return candidates


def _validate_persisted_candidates(reader, candidates):
    windows = [(row["symbol"], row["observed_at_ms"], row["observed_at_ms"]) for row in candidates]
    result = reader.event_candidates_for_windows(windows, limit=1000)
    by_key = {}
    for row in result["items"]:
        key = (row.get("symbol"), row.get("candidate_type"), row.get("observed_at_ms"))
        by_key.setdefault(key, []).append(row)
    issues = []
    validated = []
    for candidate in candidates:
        key = (candidate["symbol"], candidate["candidate_type"], candidate["observed_at_ms"])
        matches = by_key.get(key, [])
        if len(matches) == 1:
            validated.append({
                **candidate,
                "candidate_id": matches[0].get("candidate_id"),
                "persistence_status": "matched",
            })
        elif not matches:
            validated.append({**candidate, "candidate_id": None, "persistence_status": "missing"})
            issues.append({
                "code": "sample_candidate_not_persisted",
                "symbol": candidate["symbol"],
                "candidate_type": candidate["candidate_type"],
                "observed_at_ms": candidate["observed_at_ms"],
            })
        else:
            validated.append({**candidate, "candidate_id": None, "persistence_status": "ambiguous"})
            issues.append({
                "code": "sample_candidate_persistence_ambiguous",
                "symbol": candidate["symbol"],
                "candidate_type": candidate["candidate_type"],
                "observed_at_ms": candidate["observed_at_ms"],
                "match_count": len(matches),
            })
    return validated, issues


def score_candidate_evidence(sample, *, source_name="sample", reader=None,
                             windows_minutes=EVIDENCE_WINDOWS_MINUTES):
    """Return candidate hit/miss controls against explicitly observed surface events."""
    if type(sample) is not dict:
        raise ValueError("invalid_yaozi_sample")
    if (type(windows_minutes) is not tuple or not windows_minutes
            or any(type(value) is not int or value <= 0 for value in windows_minutes)
            or tuple(sorted(set(windows_minutes))) != windows_minutes):
        raise ValueError("invalid_evidence_windows")
    capture_ms = _capture_anchor_ms(sample)
    candidates = _sample_candidate_population(sample)
    events, issues = extract_observed_events(sample, source_name=source_name)
    if reader is not None:
        candidates, persistence_issues = _validate_persisted_candidates(reader, candidates)
        issues.extend(persistence_issues)
    else:
        candidates = [
            {**row, "candidate_id": None, "persistence_status": "not_checked"}
            for row in candidates
        ]

    # The collection exists even when none of its symbols produces a candidate.
    candidate_snapshot_ms = sample["public_collection"]["comparison_observed_at_ms"]
    public_symbol_coverage = []
    public_symbol_coverage_status = "not_checked"
    if reader is not None and candidate_snapshot_ms is not None:
        public_symbol_coverage = reader.derivative_symbols_at(candidate_snapshot_ms)
        public_symbol_coverage_status = "exact_derivative_snapshot" if public_symbol_coverage else "missing"
        public = sample.get("public_collection", {})
        expected_count = public.get("oi_symbols") if type(public) is dict else None
        if type(expected_count) is int and expected_count != len(public_symbol_coverage):
            issues.append({
                "code": "public_symbol_coverage_count_mismatch",
                "expected_count": expected_count,
                "stored_count": len(public_symbol_coverage),
                "observed_at_ms": candidate_snapshot_ms,
            })
        if not public_symbol_coverage:
            issues.append({
                "code": "public_symbol_coverage_missing",
                "observed_at_ms": candidate_snapshot_ms,
            })

    events_after_snapshot = [
        event for event in events
        if candidate_snapshot_ms is not None
        and candidate_snapshot_ms <= event["observed_at_ms"] <= capture_ms
    ]
    coverage_set = set(public_symbol_coverage)
    covered_events_after_snapshot = [
        event for event in events_after_snapshot if event["symbol"] in coverage_set
    ]
    future_events = [event for event in events if event["observed_at_ms"] > capture_ms]
    for event in future_events:
        issues.append({
            "code": "event_after_capture_anchor",
            "symbol": event["symbol"],
            "observed_at_ms": event["observed_at_ms"],
        })

    window_stats = {}
    for minutes in windows_minutes:
        label = f"{minutes}m"
        limit_ms = minutes * 60_000
        evaluable = []
        non_evaluable = []
        hit_candidates = []
        miss_candidates = []
        linked_event_count = 0
        linked_covered_event_count = 0

        for candidate in candidates:
            window_end_ms = candidate["observed_at_ms"] + limit_ms
            if capture_ms < window_end_ms:
                non_evaluable.append(candidate)
                continue
            evaluable.append(candidate)
            matches = [
                event for event in events_after_snapshot
                if event["symbol"] == candidate["symbol"]
                and candidate["observed_at_ms"] <= event["observed_at_ms"] <= window_end_ms
            ]
            if matches:
                hit_candidates.append(candidate)
            else:
                miss_candidates.append(candidate)

        for event in events_after_snapshot:
            if any(
                candidate["symbol"] == event["symbol"]
                and 0 <= event["observed_at_ms"] - candidate["observed_at_ms"] <= limit_ms
                for candidate in candidates
            ):
                linked_event_count += 1
                if event["symbol"] in coverage_set:
                    linked_covered_event_count += 1

        window_stats[label] = {
            "candidate_evaluable_count": len(evaluable),
            "candidate_non_evaluable_count": len(non_evaluable),
            "candidate_hit_count": len(hit_candidates),
            "candidate_miss_count": len(miss_candidates),
            "candidate_hit_rate_text": _ratio_text(len(hit_candidates), len(evaluable)),
            "candidate_miss_rate_text": _ratio_text(len(miss_candidates), len(evaluable)),
            "candidate_hit_symbols": [row["symbol"] for row in hit_candidates],
            "candidate_miss_symbols": [row["symbol"] for row in miss_candidates],
            "candidate_non_evaluable_symbols": [row["symbol"] for row in non_evaluable],
            "linked_observed_event_count": linked_event_count,
            "observed_event_count_after_candidate_snapshot": len(events_after_snapshot),
            "observed_event_link_rate_text": _ratio_text(linked_event_count, len(events_after_snapshot)),
            "public_coverage_observed_event_count": len(covered_events_after_snapshot),
            "public_coverage_linked_event_count": linked_covered_event_count,
            "public_coverage_event_link_rate_text": _ratio_text(
                linked_covered_event_count, len(covered_events_after_snapshot)),
        }

    persistence_status = (
        "not_checked" if reader is None
        else "complete" if all(row["persistence_status"] == "matched" for row in candidates)
        else "issues"
    )
    return {
        "contract": "catos_yaozi_candidate_evidence_score_v1",
        "interpretation": "descriptive_observed_surface_hit_rates_only_no_private_gate_or_causality_inference",
        "sample_source": source_name,
        "capture_anchor_ms": capture_ms,
        "candidate_snapshot_ms": candidate_snapshot_ms,
        "candidate_population_count": len(candidates),
        "candidate_persistence_status": persistence_status,
        "public_symbol_coverage_status": public_symbol_coverage_status,
        "public_symbol_coverage_count": len(public_symbol_coverage),
        "public_symbol_coverage_symbols": public_symbol_coverage,
        "observed_event_count": len(events),
        "observed_event_count_after_candidate_snapshot": len(events_after_snapshot),
        "recall_status": "not_true_recall_signal_surface_filter_and_event_taxonomy_incomplete",
        "negative_control_contract": "candidate_miss_means_no_event_in_captured_signal_surface_window_only",
        "windows_minutes": list(windows_minutes),
        "windows": window_stats,
        "candidates": candidates,
        "issues": issues,
    }


def build_candidate_evidence_report(db_path, sample_path):
    path = Path(sample_path)
    with path.open("r", encoding="utf-8") as handle:
        sample = json.load(handle)
    reader = MarketIntelReader(db_path)
    return score_candidate_evidence(sample, source_name=path.name, reader=reader)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Score persisted public candidates against observed Yaozi signal-surface follow-up")
    parser.add_argument("--db", default="outputs/catos-market-intel-v14.sqlite")
    parser.add_argument("--sample", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    report = build_candidate_evidence_report(Path(args.db), Path(args.sample))
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
