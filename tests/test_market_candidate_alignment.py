from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from catos.market_api import MarketIntelReader
from catos.market_candidate_alignment import (
    align_candidates,
    build_alignment_report,
    extract_observed_events,
    summarize_alignment,
)
from catos.market_intel import MarketIntelStore
from catos.market_p1 import make_oi_event_candidate


SYMBOL = "INJ-USDT-SWAP"


def event_ms():
    return int(datetime(2026, 9, 18, 18, 53, tzinfo=ZoneInfo("Asia/Taipei")).timestamp() * 1000)


def sample():
    return {
        "schema": "catos-yaozi-blackbox-sample-v1",
        "sample_date": "2026-09-18",
        "timezone": "Asia/Taipei",
        "yaozi_detail_samples": [{
            "symbol": "INJ",
            "recent_events": [
                "OI_BREAKOUT OI5m+1.8% · OI1h+8.0% 09/18 18:53",
            ],
        }],
    }


def candidate(candidate_id, lead_minutes, possible=("OI_BREAKOUT",)):
    return {
        "candidate_id": candidate_id,
        "candidate_type": "OI_POSITIVE_CHANGE",
        "symbol": SYMBOL,
        "observed_at_ms": event_ms() - lead_minutes * 60_000,
        "possible_yaozi_event_types_json": list(possible),
        "evidence_json": {"yaozi_event_triggered": False},
        "source_snapshot_ids_json": [f"source:{candidate_id}"],
    }


class CandidateAlignmentTests(unittest.TestCase):
    def _report_fixture(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        db_path = root / "intel.sqlite"
        store = MarketIntelStore(db_path)
        self.addCleanup(store.close)
        sample_path = root / "sample.json"
        sample_path.write_text(json.dumps(sample(), ensure_ascii=False), encoding="utf-8")
        return store, db_path, sample_path

    def _record_candidate(self, store, observed_at_ms, symbol=SYMBOL):
        value = make_oi_event_candidate({
            "symbol": symbol,
            "observed_at_ms": observed_at_ms,
            "oi_delta_5m_text": "1.8000000000000000001",
            "oi_delta_1h_text": None,
            "oi_delta_4h_text": None,
        })
        store.record_public_event_candidate(value)
        return value.candidate_id

    def test_extracts_explicit_event_type_and_taipei_minute(self):
        events, issues = extract_observed_events(sample(), source_name="fixture.json")
        self.assertEqual(issues, [])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["symbol"], SYMBOL)
        self.assertEqual(events[0]["event_type"], "OI_BREAKOUT")
        self.assertEqual(events[0]["observed_at_ms"], event_ms())
        self.assertEqual(events[0]["source"], "fixture.json")

    def test_sample_without_detail_events_is_valid_empty_observation(self):
        value = sample()
        value.pop("yaozi_detail_samples")
        events, issues = extract_observed_events(value, source_name="scan-only.json")
        self.assertEqual(events, [])
        self.assertEqual(issues, [])

    def test_extracts_signal_surface_event_without_taxonomy_claim(self):
        value = {
            "schema": "catos-yaozi-signal-surface-sample-v1",
            "sample_date": "2026-09-20",
            "timezone": "Asia/Taipei",
            "signal_surface": {
                "events": [{
                    "observed_at_text": "09/20 09:03",
                    "symbol": "PONS",
                    "view": "risk",
                    "category_text": "新進候選監控",
                    "event_title": "首次入池 · 風險視角",
                }],
            },
        }
        events, issues = extract_observed_events(value, source_name="signals.json")
        self.assertEqual(issues, [])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["symbol"], "PONS-USDT-SWAP")
        self.assertEqual(events[0]["event_type"], "SIGNAL_SURFACE_EVENT")
        self.assertFalse(events[0]["taxonomy_comparable"])
        self.assertEqual(events[0]["surface_event_title"], "首次入池 · 風險視角")

    def test_signal_surface_alignment_keeps_taxonomy_compatibility_not_applicable(self):
        event = {
            "source": "signals.json",
            "symbol": SYMBOL,
            "event_type": "SIGNAL_SURFACE_EVENT",
            "observed_at_ms": event_ms(),
            "raw_text": "首次入池 · 異動視角",
            "taxonomy_comparable": False,
        }
        result = align_candidates([event], [candidate("c4", 4)])[0]
        self.assertIsNone(result["preceding_candidates"][0]["taxonomy_compatible"])
        summary = summarize_alignment([result])
        self.assertEqual(summary["window_link_counts"]["5m"], 1)
        self.assertEqual(summary["taxonomy_compatible_link_counts"]["5m"], 0)

    def test_alignment_uses_pre_event_windows_without_trigger_inference(self):
        events, _ = extract_observed_events(sample())
        rows = [
            candidate("c4", 4),
            candidate("c10", 10, ()),
            candidate("c30", 30),
            candidate("future", -1),
            {**candidate("other", 1), "symbol": "BTC-USDT-SWAP"},
        ]
        result = align_candidates(events, rows)[0]
        self.assertEqual(result["window_counts"], {"5m": 1, "15m": 2, "60m": 3})
        self.assertEqual(
            [item["candidate_id"] for item in result["preceding_candidates"]],
            ["c4", "c10", "c30"],
        )
        self.assertTrue(result["preceding_candidates"][0]["taxonomy_compatible"])
        self.assertFalse(result["preceding_candidates"][1]["taxonomy_compatible"])
        self.assertFalse(result["preceding_candidates"][0]["evidence"]["yaozi_event_triggered"])

    def test_alignment_summary_counts_links_events_taxonomy_and_candidate_types(self):
        events, _ = extract_observed_events(sample())
        aligned = align_candidates(events, [
            candidate("c4", 4),
            candidate("c10", 10, ()),
            candidate("c30", 30),
        ])
        summary = summarize_alignment(aligned)
        self.assertEqual(summary["window_link_counts"], {"5m": 1, "15m": 2, "60m": 3})
        self.assertEqual(summary["window_event_counts"], {"5m": 1, "15m": 1, "60m": 1})
        self.assertEqual(
            summary["taxonomy_compatible_link_counts"],
            {"5m": 1, "15m": 1, "60m": 2},
        )
        self.assertEqual(summary["largest_window_minutes"], 60)
        self.assertEqual(
            summary["candidate_type_link_counts_largest_window"],
            {"OI_POSITIVE_CHANGE": 3},
        )

    def test_report_reads_persisted_candidates_and_sample_without_db_write(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        db_path = root / "intel.sqlite"
        sample_path = root / "sample.json"
        store = MarketIntelStore(db_path)
        candidate_value = make_oi_event_candidate({
            "symbol": SYMBOL,
            "observed_at_ms": event_ms() - 4 * 60_000,
            "oi_delta_5m_text": "1.8",
            "oi_delta_1h_text": "8.0",
            "oi_delta_4h_text": None,
        })
        store.record_public_event_candidate(candidate_value)
        store.close()
        sample_path.write_text(json.dumps(sample(), ensure_ascii=False), encoding="utf-8")

        report = build_alignment_report(db_path, [sample_path])
        self.assertEqual(report["contract"], "catos_yaozi_candidate_alignment_v1")
        self.assertEqual(
            report["interpretation"],
            "observational_timing_only_no_trigger_threshold_or_causality_inference",
        )
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["observed_event_count"], 1)
        self.assertEqual(report["alignment_summary"]["window_link_counts"]["5m"], 1)
        self.assertEqual(report["alignment_summary"]["taxonomy_compatible_link_counts"]["5m"], 1)
        self.assertEqual(report["events"][0]["window_counts"]["5m"], 1)
        self.assertEqual(report["events"][0]["preceding_candidates"][0]["lead_ms"], 240_000)

    def test_historical_window_survives_newer_candidates_and_other_symbols(self):
        store, db_path, sample_path = self._report_fixture()
        expected = self._record_candidate(store, event_ms() - 240_000)
        for index in range(1001):
            self._record_candidate(store, event_ms() + index + 1)
        self._record_candidate(store, event_ms(), "BTC-USDT-SWAP")

        report = build_alignment_report(db_path, [sample_path], limit=1)
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["candidate_query"]["status"], "complete_stored_rows")
        links = report["events"][0]["preceding_candidates"]
        self.assertEqual([item["candidate_id"] for item in links], [expected])
        self.assertEqual(links[0]["evidence"]["oi_delta"]["oi_delta_5m_text"],
                         "1.8000000000000000001")

    def test_historical_window_is_inclusive_and_does_not_admit_future_rows(self):
        store, db_path, sample_path = self._report_fixture()
        for delta in (-3_600_001, -3_600_000, -900_000, -300_000, 0, 1):
            self._record_candidate(store, event_ms() + delta)

        report = build_alignment_report(db_path, [sample_path], limit=4)
        self.assertEqual(report["events"][0]["window_counts"], {"5m": 2, "15m": 3, "60m": 4})
        self.assertEqual(report["candidate_query"]["status"], "complete_stored_rows")
        self.assertFalse(report["candidate_query"]["windows"][0]["truncated"])
        self.assertEqual(report["issues"], [])

    def test_truncation_marks_counts_as_lower_bounds(self):
        store, db_path, sample_path = self._report_fixture()
        for minutes in (1, 4, 10):
            self._record_candidate(store, event_ms() - minutes * 60_000)

        report = build_alignment_report(db_path, [sample_path], limit=2)
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual(report["candidate_query"]["status"], "truncated")
        self.assertEqual(report["count_semantics"], "lower_bound_due_to_query_limit")
        self.assertEqual(report["issues"][0]["code"], "candidate_window_truncated")
        self.assertEqual(report["candidate_query"]["windows"][0]["returned_count"], 2)
        self.assertEqual(report["alignment_summary"]["window_link_counts"]["60m"], 2)

    def test_overlapping_windows_dedupe_candidates_but_preserve_observations(self):
        store, db_path, sample_path = self._report_fixture()
        self._record_candidate(store, event_ms() - 240_000)
        value = sample()
        value["yaozi_detail_samples"][0]["recent_events"].append(
            "OI_BREAKOUT OI5m+1.8% 09/18 18:54")
        sample_path.write_text(json.dumps(value), encoding="utf-8")

        report = build_alignment_report(db_path, [sample_path, sample_path])
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["observed_event_count"], 4)
        self.assertEqual(len(report["candidate_query"]["windows"]), 2)
        self.assertEqual(report["alignment_summary"]["window_link_counts"]["5m"], 4)
        self.assertEqual(report["count_semantics"], "stored_candidate_links_per_observation")

    def test_missing_candidates_do_not_claim_source_coverage(self):
        _, db_path, sample_path = self._report_fixture()
        report = build_alignment_report(db_path, [sample_path])
        self.assertEqual(report["candidate_count"], 0)
        self.assertEqual(report["candidate_query"]["status"], "complete_stored_rows")
        self.assertEqual(report["candidate_query"]["source_coverage"],
                         "unknown_not_measured_by_candidate_alignment")

    def test_sample_without_events_does_not_read_unrelated_candidates(self):
        store, db_path, sample_path = self._report_fixture()
        self._record_candidate(store, event_ms())
        value = sample()
        value.pop("yaozi_detail_samples")
        sample_path.write_text(json.dumps(value), encoding="utf-8")

        report = build_alignment_report(db_path, [sample_path])
        self.assertEqual(report["candidate_count"], 0)
        self.assertEqual(report["candidate_query"]["status"], "no_observed_events")
        self.assertEqual(report["candidate_query"]["windows"], [])

    def test_historical_reader_validates_limits_and_windows(self):
        _, db_path, _ = self._report_fixture()
        reader = MarketIntelReader(db_path)
        for limit in (0, 1001, True, "1"):
            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError, "invalid_limit"):
                reader.event_candidates_for_windows([], limit=limit)
        for windows in (None, [None], [(SYMBOL, 0)], [(SYMBOL, True, 1)],
                        [(SYMBOL, 0, 1.0)], [(SYMBOL, -1, 1)], [(SYMBOL, 2, 1)],
                        [(SYMBOL, 0, 2**63)]):
            with self.subTest(windows=windows), self.assertRaisesRegex(
                    ValueError, "invalid_candidate_windows"):
                reader.event_candidates_for_windows(windows)

    def test_historical_reader_uses_one_snapshot_during_concurrent_insert(self):
        store, db_path, _ = self._report_fixture()
        reader = MarketIntelReader(db_path)
        self._record_candidate(store, event_ms() - 240_000)
        original_decode = reader._decode
        inserted = False

        def decode_and_insert(row, *fields):
            nonlocal inserted
            if not inserted:
                inserted = True
                self._record_candidate(store, event_ms() + 60_000)
            return original_decode(row, *fields)

        reader._decode = decode_and_insert
        windows = [
            (SYMBOL, event_ms() - 300_000, event_ms()),
            (SYMBOL, event_ms() + 1, event_ms() + 120_000),
        ]
        result = reader.event_candidates_for_windows(windows)
        self.assertTrue(inserted)
        self.assertEqual([row["returned_count"] for row in result["windows"]], [1, 0])
        fresh = reader.event_candidates_for_windows(windows)
        self.assertEqual([row["returned_count"] for row in fresh["windows"]], [1, 1])


if __name__ == "__main__":
    unittest.main()
