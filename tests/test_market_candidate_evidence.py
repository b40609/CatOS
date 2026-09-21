from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from catos.market_api import MarketIntelReader
from catos.market_candidate_evidence import build_candidate_evidence_report, score_candidate_evidence
from catos.market_intel import MarketIntelStore
from catos.market_p1 import make_oi_event_candidate


TZ = ZoneInfo("Asia/Taipei")


def at(hour, minute):
    return int(datetime(2026, 9, 20, hour, minute, tzinfo=TZ).timestamp() * 1000)


def evidence_sample():
    return {
        "schema": "catos-yaozi-signal-surface-sample-v1",
        "sample_date": "2026-09-20",
        "timezone": "Asia/Taipei",
        "capture_anchor": "2026-09-20T10:40:00+08:00",
        "signal_surface": {
            "events": [
                {"observed_at_text": "09/20 10:04", "symbol": "AAA", "view": "risk",
                 "category_text": "x", "event_title": "first"},
                {"observed_at_text": "09/20 10:12", "symbol": "AAA", "view": "risk",
                 "category_text": "x", "event_title": "second"},
                {"observed_at_text": "09/20 10:31", "symbol": "CCC", "view": "risk",
                 "category_text": "x", "event_title": "third"},
            ],
        },
        "public_collection": {
            "comparison_observed_at_ms": at(10, 0),
            "candidates": [
                {"symbol": "AAA-USDT-SWAP", "candidate_type": "OI_POSITIVE_CHANGE"},
                {"symbol": "BBB-USDT-SWAP", "candidate_type": "OI_POSITIVE_CHANGE"},
                {"symbol": "CCC-USDT-SWAP", "candidate_type": "OI_POSITIVE_CHANGE"},
            ],
        },
    }


class CandidateEvidenceTests(unittest.TestCase):
    def test_zero_candidates_preserve_snapshot_and_observed_events(self):
        sample = evidence_sample()
        sample["public_collection"]["candidates"] = []
        report = score_candidate_evidence(sample)
        self.assertEqual(report["candidate_snapshot_ms"], at(10, 0))
        self.assertEqual(report["candidate_population_count"], 0)
        self.assertEqual(report["observed_event_count_after_candidate_snapshot"], 3)
        for window in report["windows"].values():
            self.assertIsNone(window["candidate_hit_rate_text"])
            self.assertEqual(window["candidate_miss_count"], 0)
            self.assertEqual(window["observed_event_link_rate_text"], "0.000000")

    def test_zero_candidates_still_check_exact_public_coverage(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db_path = Path(directory.name) / "intel.sqlite"
        store = MarketIntelStore(db_path)
        self.addCleanup(store.close)
        store.connection.execute(
            "INSERT INTO derivative_snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("AAA-USDT-SWAP", at(10, 0), "1", "-1", None, None,
             None, None, None, None, '{"oi":"fixture"}'),
        )
        sample = evidence_sample()
        sample["public_collection"].update(candidates=[], oi_symbols=1)
        reader = MarketIntelReader(db_path)
        report = score_candidate_evidence(sample, reader=reader)
        self.assertEqual(report["public_symbol_coverage_status"], "exact_derivative_snapshot")
        self.assertEqual(report["public_symbol_coverage_symbols"], ["AAA-USDT-SWAP"])
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["windows"]["5m"]["public_coverage_observed_event_count"], 2)
        self.assertEqual(report["windows"]["5m"]["public_coverage_event_link_rate_text"], "0.000000")
        sample["public_collection"]["oi_symbols"] = 2
        report = score_candidate_evidence(sample, reader=reader)
        self.assertEqual(report["issues"][0]["code"], "public_symbol_coverage_count_mismatch")

    def test_scores_candidate_hits_misses_and_incomplete_followup(self):
        report = score_candidate_evidence(evidence_sample())
        self.assertEqual(report["candidate_population_count"], 3)
        self.assertEqual(report["observed_event_count_after_candidate_snapshot"], 3)
        self.assertEqual(
            report["recall_status"],
            "not_true_recall_signal_surface_filter_and_event_taxonomy_incomplete",
        )

        five = report["windows"]["5m"]
        self.assertEqual(five["candidate_evaluable_count"], 3)
        self.assertEqual(five["candidate_hit_count"], 1)
        self.assertEqual(five["candidate_miss_count"], 2)
        self.assertEqual(five["candidate_hit_rate_text"], "0.333333")
        self.assertEqual(five["linked_observed_event_count"], 1)

        fifteen = report["windows"]["15m"]
        self.assertEqual(fifteen["candidate_hit_count"], 1)
        self.assertEqual(fifteen["linked_observed_event_count"], 2)
        self.assertEqual(
            fifteen["candidate_miss_symbols"],
            ["BBB-USDT-SWAP", "CCC-USDT-SWAP"],
        )

        thirty = report["windows"]["30m"]
        self.assertEqual(thirty["candidate_hit_count"], 1)
        self.assertEqual(thirty["linked_observed_event_count"], 2)

        sixty = report["windows"]["60m"]
        self.assertEqual(sixty["candidate_evaluable_count"], 0)
        self.assertEqual(sixty["candidate_non_evaluable_count"], 3)
        self.assertIsNone(sixty["candidate_hit_rate_text"])
        self.assertEqual(sixty["linked_observed_event_count"], 3)

    def test_build_report_validates_sample_candidates_against_persisted_rows(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        db_path = root / "intel.sqlite"
        sample_path = root / "sample.json"
        store = MarketIntelStore(db_path)
        self.addCleanup(store.close)
        payload = json.dumps({"oi": "fixture"}, separators=(",", ":"), sort_keys=True)
        for symbol in ("AAA-USDT-SWAP", "BBB-USDT-SWAP", "CCC-USDT-SWAP"):
            store.connection.execute(
                "INSERT INTO derivative_snapshot VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (symbol, at(10, 0), "1", "1", None, None, None, None, None, None, payload),
            )
            candidate = make_oi_event_candidate({
                "symbol": symbol,
                "observed_at_ms": at(10, 0),
                "oi_delta_5m_text": "1",
                "oi_delta_1h_text": None,
                "oi_delta_4h_text": None,
            })
            store.record_public_event_candidate(candidate)
        sample_path.write_text(json.dumps(evidence_sample(), ensure_ascii=False), encoding="utf-8")

        report = build_candidate_evidence_report(db_path, sample_path)
        self.assertEqual(report["candidate_persistence_status"], "complete")
        self.assertEqual(report["public_symbol_coverage_status"], "exact_derivative_snapshot")
        self.assertEqual(report["public_symbol_coverage_count"], 3)
        self.assertEqual(report["windows"]["15m"]["public_coverage_observed_event_count"], 3)
        self.assertEqual(report["windows"]["15m"]["public_coverage_linked_event_count"], 2)
        self.assertEqual(report["windows"]["15m"]["public_coverage_event_link_rate_text"], "0.666667")
        self.assertEqual(report["issues"], [])
        self.assertTrue(all(row["candidate_id"] for row in report["candidates"]))

    def test_missing_persisted_candidate_is_diagnostic_not_a_false_hit(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        db_path = root / "intel.sqlite"
        sample_path = root / "sample.json"
        store = MarketIntelStore(db_path)
        store.close()
        sample_path.write_text(json.dumps(evidence_sample(), ensure_ascii=False), encoding="utf-8")

        report = build_candidate_evidence_report(db_path, sample_path)
        self.assertEqual(report["candidate_persistence_status"], "issues")
        self.assertEqual(len(report["issues"]), 4)
        self.assertTrue(
            all(item["code"] == "sample_candidate_not_persisted" for item in report["issues"][:3])
        )
        self.assertEqual(report["issues"][3]["code"], "public_symbol_coverage_missing")
        self.assertEqual(report["windows"]["5m"]["candidate_hit_count"], 1)

    def test_rejects_unsupported_or_naive_capture_anchor(self):
        value = evidence_sample()
        value["schema"] = "other"
        with self.assertRaisesRegex(ValueError, "unsupported_evidence_sample"):
            score_candidate_evidence(value)

        value = evidence_sample()
        value["capture_anchor"] = "2026-09-20T10:40:00"
        with self.assertRaisesRegex(ValueError, "invalid_capture_anchor"):
            score_candidate_evidence(value)


if __name__ == "__main__":
    unittest.main()
