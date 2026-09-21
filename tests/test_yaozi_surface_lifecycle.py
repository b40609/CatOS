import json
from pathlib import Path
import tempfile
import unittest

from catos.yaozi_surface_lifecycle import analyze_surface_samples


def _sample(events):
    return {
        "schema": "catos-yaozi-signal-surface-sample-v1",
        "sample_date": "2026-09-20",
        "timezone": "Asia/Taipei",
        "signal_surface": {"events": events},
    }


def _event(time, symbol, view, title):
    return {
        "observed_at_text": time,
        "symbol": symbol,
        "view": view,
        "category_text": "fixture",
        "event_title": title,
    }


class YaoziSurfaceLifecycleTests(unittest.TestCase):
    def test_deduplicates_overlapping_samples_and_counts_ordered_transition(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.json"
            second = root / "second.json"
            entry = _event("09/20 12:43", "JTO", "momentum", "首次入池 · 異動視角")
            exit_event = _event("09/20 12:47", "JTO", "momentum", "結構撤離確認 · 降級至先行")
            first.write_text(json.dumps(_sample([entry]), ensure_ascii=False), encoding="utf-8")
            second.write_text(json.dumps(_sample([entry, exit_event]), ensure_ascii=False), encoding="utf-8")

            report = analyze_surface_samples([first, second])

            self.assertEqual(report["counts"]["unique_candidate_events"], 2)
            self.assertEqual(report["counts"]["ordered_transitions"], 1)
            self.assertEqual(
                report["event_class_transitions"][0],
                {
                    "transition": "首次入池 -> 結構撤離確認",
                    "count": 1,
                    "min_elapsed_minutes": 4,
                    "max_elapsed_minutes": 4,
                },
            )
            self.assertEqual(
                report["symbol_sequences"][0]["events"][0]["source_samples"],
                ["first.json", "second.json"],
            )

    def test_same_minute_events_are_ambiguous_and_not_ordered(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.json"
            events = [
                _event("09/20 09:29", "USELESS", "risk", "首次入池 · 風險視角"),
                _event("09/20 09:29", "USELESS", "risk", "結構撤離確認 · 24h 高回落"),
            ]
            path.write_text(json.dumps(_sample(events), ensure_ascii=False), encoding="utf-8")

            report = analyze_surface_samples([path])

            self.assertEqual(report["counts"]["ordered_transitions"], 0)
            self.assertEqual(report["counts"]["ambiguous_same_minute_groups"], 1)

    def test_non_candidate_views_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.json"
            path.write_text(
                json.dumps(
                    _sample([
                        _event("09/20 08:35", "CRV", "onchain", "鏈上巨鯨掃貨 · fixture")
                    ]),
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = analyze_surface_samples([path])

            self.assertEqual(report["counts"]["unique_candidate_events"], 0)
            self.assertEqual(report["counts"]["excluded_non_candidate_events"], 1)


if __name__ == "__main__":
    unittest.main()
