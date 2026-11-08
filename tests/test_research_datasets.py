"""Fetched-dataset manifests: write, verify, resolve and run research on them (offline)."""

from dataclasses import asdict, replace
from decimal import Decimal
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock

from catos import research_datasets as datasets
from catos.research_catalog import (
    DATASET_ID, DEFAULT_REQUEST, MAX_CURVE_POINTS, catalog, execute_request, provenance,
    resolve_dataset, sample_curve_indices, validate_request,
)

TF = 900_000
EIGHT_H = 28_800_000
START = 1_790_726_400_000  # 8h-aligned
INSTRUMENT = {
    "instId": "BTC-USDT-SWAP", "instType": "SWAP", "ctType": "linear", "settleCcy": "USDT",
    "ctValCcy": "BTC", "ctVal": "0.01", "ctMult": "1", "tickSz": "0.1", "lotSz": "0.01",
    "minSz": "0.01", "state": "live",
}


def make_bars(count, start=START):
    """Deterministic random walk on a 0.1 tick: (open_time_ms, open, high, low, close) strings."""
    rows, price, seed = [], Decimal("60000.0"), 7
    for index in range(count):
        seed = (seed * 1103515245 + 12345) % 2**31
        close = price + Decimal((seed % 801) - 400) / Decimal("10")
        high, low = max(price, close) + Decimal("3.0"), min(price, close) - Decimal("3.0")
        rows.append((start + index * TF, str(price), str(high), str(low), str(close)))
        price = close
    return rows


def make_funding(start, end):
    return [(ms, "0.0001" if (ms // EIGHT_H) % 2 else "-0.00005", "0.00012")
            for ms in range(start, end, EIGHT_H)]


def write_fixture(root, count=192, **overrides):
    end = START + count * TF
    kwargs = dict(inst_id="BTC-USDT-SWAP", bar="15m", start_ms=START, end_ms=end,
                  candles=make_bars(count), funding=make_funding(START, end),
                  instrument=dict(INSTRUMENT), fetched_at_ms=end + 60_000, requests=5)
    kwargs.update(overrides)
    return datasets.write_dataset(root, **kwargs)


def request_for(dataset_id, **over):
    return {**DEFAULT_REQUEST, "dataset_id": dataset_id, **over}


class DatasetFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "okx"
        patcher = mock.patch.object(datasets, "DATA_ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)


class WriteAndVerifyTest(DatasetFixture):
    def test_round_trip_manifest_is_accepted(self):
        target = write_fixture(self.root)
        manifest = json.loads((target / datasets.MANIFEST).read_text(encoding="utf-8"))
        # START is 2026-09-30T00:00Z; 192 bars end (exclusive) at 2026-10-02T00:00Z.
        self.assertEqual(manifest["dataset_id"], "okx-btc-usdt-swap-15m-20260930-20261002")
        self.assertEqual(manifest["bars"], 192)
        self.assertEqual(manifest["funding"], {"rate_field": "realizedRate", "events": 6,
                                               "interval_ms": EIGHT_H, "complete": True,
                                               "mark_price_source": "candle_open_at_funding_time"})
        self.assertEqual(manifest["contract"]["tick_size"], "0.1")
        valid, rejected = datasets.list_datasets()
        self.assertEqual([item.dataset_id for item in valid], [manifest["dataset_id"]])
        self.assertEqual(rejected, [])
        self.assertEqual(valid[0].contract.base_per_contract, Decimal("0.01"))
        self.assertTrue((target / datasets.CANDLES).read_bytes().startswith(
            b"open_time_ms,open,high,low,close,closed\n"))

    def test_writer_refuses_gaps_funding_that_stops_early_and_overwrite(self):
        bars = make_bars(192)
        with self.assertRaisesRegex(ValueError, "dataset_has_gaps"):
            write_fixture(self.root, candles=bars[:50] + bars[51:])
        end = START + 192 * TF
        with self.assertRaisesRegex(ValueError, "funding_stops_before_end"):
            write_fixture(self.root, funding=make_funding(START, end - EIGHT_H))
        with self.assertRaisesRegex(ValueError, "funding_interval_irregular"):
            funding = make_funding(START, end)
            write_fixture(self.root, funding=funding[:2] + funding[3:])
        with self.assertRaisesRegex(ValueError, "instrument_not_linear_usdt_swap"):
            write_fixture(self.root, instrument={**INSTRUMENT, "ctType": "inverse"})
        self.assertFalse(self.root.exists() and any(self.root.glob("*/*/okx-*")))
        write_fixture(self.root)
        with self.assertRaises(FileExistsError):
            write_fixture(self.root)

    def test_tampered_or_unexpected_manifest_is_rejected_fail_closed(self):
        target = write_fixture(self.root)
        dataset_id = target.name
        candles = target / datasets.CANDLES
        original = candles.read_bytes()
        candles.write_bytes(original[:-2] + b"0\n")  # last bar's closed flag flipped
        valid, rejected = datasets.list_datasets()
        self.assertEqual(valid, [])
        self.assertIn("dataset_hash_mismatch", rejected[0][1])
        with self.assertRaisesRegex(ValueError, "unknown_dataset"):
            resolve_dataset(dataset_id)
        candles.write_bytes(original)
        manifest_path = target / datasets.MANIFEST
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_path.write_text(json.dumps({**manifest, "extra": 1}), encoding="utf-8")
        self.assertIn("manifest_fields_mismatch", datasets.list_datasets()[1][0][1])
        manifest_path.write_text(json.dumps({**manifest, "gaps": [START]}), encoding="utf-8")
        self.assertIn("dataset_has_gaps", datasets.list_datasets()[1][0][1])
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(len(datasets.list_datasets()[0]), 1)


class CatalogAndRunTest(DatasetFixture):
    def test_synthetic_default_is_unchanged(self):
        source = provenance()
        self.assertEqual(set(source["dataset"]), {"id", "source", "sha256"})
        self.assertEqual(source["dataset"]["id"], DATASET_ID)
        self.assertEqual([item["id"] for item in catalog()["datasets"]], [DATASET_ID])

    def test_catalog_lists_fetched_dataset_with_its_contract(self):
        dataset_id = write_fixture(self.root).name
        entries = {item["id"]: item for item in catalog()["datasets"]}
        self.assertEqual(list(entries), [DATASET_ID, dataset_id])
        fetched = entries[dataset_id]
        self.assertEqual((fetched["source"], fetched["bars"], fetched["funding"]),
                         ("okx_public_history", 192, True))
        self.assertEqual(fetched["contract"]["tick_size"], Decimal("0.1"))
        self.assertEqual(set(fetched["files"]), {
            datasets.rel_path(self.root / "BTC-USDT-SWAP" / "15m" / dataset_id / name)
            for name in (datasets.MANIFEST, *datasets.FILES)})
        _, config, _, _ = validate_request(request_for(dataset_id))
        self.assertEqual((config.contract.tick_size, config.timeframe_ms), (Decimal("0.1"), TF))

    def test_backtest_on_fetched_dataset_settles_funding_and_carries_notice(self):
        dataset_id = write_fixture(self.root).name
        source = provenance(dataset_id)
        payload, report = execute_request(request_for(dataset_id), source)
        self.assertEqual(payload["provenance"]["dataset"]["id"], dataset_id)
        self.assertIn("OKX 公開歷史 K 線", payload["data_notice"])
        self.assertGreater(len(payload["result"]["funding"]), 0)
        self.assertNotIn("curve_sampling", payload)
        self.assertIsNone(payload["equity_wiped_out"])
        self.assertEqual(len(payload["drawdown_curve"]), len(payload["result"]["equity_curve"]))
        self.assertIn("<", report)
        with self.assertRaisesRegex(ValueError, "source_changed"):
            execute_request(request_for(dataset_id), provenance())

    def test_large_dataset_curve_is_sampled_keeping_the_deepest_drawdown(self):
        count = MAX_CURVE_POINTS + 400
        dataset_id = write_fixture(self.root, count=count).name
        payload, report = execute_request(request_for(dataset_id), provenance(dataset_id))
        sampling = payload["curve_sampling"]
        # The HTML report draws the same sampled points (worker stdout carries both).
        drawn = re.search(r'<polyline points="([^"]+)"', report).group(1).split()
        self.assertEqual(len(drawn), sampling["returned_points"])
        self.assertIn(f"圖表取樣 {sampling['returned_points']}／{sampling['total_points']} 點", report)
        self.assertGreater(sampling["total_points"], MAX_CURVE_POINTS)
        self.assertLessEqual(sampling["total_points"], count)
        self.assertLessEqual(sampling["returned_points"], MAX_CURVE_POINTS)
        self.assertEqual(len(payload["result"]["equity_curve"]), sampling["returned_points"])
        deepest = max(Decimal(point["drawdown_pct"]) for point in payload["drawdown_curve"])
        self.assertEqual(str(deepest.normalize()),
                         str(Decimal(payload["result"]["performance"]["max_drawdown_pct"]).normalize()))

    def test_sample_curve_indices_are_ordered_and_keep_extremes(self):
        values = [Decimal(i % 7) for i in range(10)] + [Decimal(99)] + [Decimal(0)] * 30
        keep = sample_curve_indices(values, limit=5)
        self.assertEqual(keep, sorted(keep))
        self.assertIn(10, keep)
        self.assertEqual(keep[-1], len(values) - 1)
        self.assertEqual(sample_curve_indices(values[:4], limit=5), [0, 1, 2, 3])

    def test_optimization_and_validation_use_the_requested_dataset(self):
        from catos.research_catalog import DEFAULT_OPTIMIZATION, DEFAULT_VALIDATION
        from catos.research_optimization import execute_optimization
        from catos.research_validation_job import execute_validation
        dataset_id = write_fixture(self.root).name
        source = provenance(dataset_id)
        optimization = {**DEFAULT_OPTIMIZATION, "n_trials": 2,
                        "backtest": {**DEFAULT_OPTIMIZATION["backtest"], "dataset_id": dataset_id}}
        payload, _ = execute_optimization(optimization, source)
        self.assertEqual(payload["provenance"]["dataset"]["id"], dataset_id)
        self.assertIn("OKX 公開歷史 K 線", payload["data_notice"])
        validation = {**DEFAULT_VALIDATION,
                      "backtest": {**DEFAULT_VALIDATION["backtest"], "dataset_id": dataset_id}}
        payload, _ = execute_validation(validation, source)
        self.assertEqual(payload["provenance"]["dataset"]["id"], dataset_id)
        self.assertIn("OKX 公開歷史 K 線", payload["data_notice"])
        self.assertTrue(payload["evaluation_complete"])
        payload, _ = execute_validation(DEFAULT_VALIDATION, provenance())
        self.assertEqual(payload["provenance"]["dataset"]["id"], DATASET_ID)

    def test_validation_on_large_fetched_dataset_is_compact_and_exact(self):
        from catos.research import backtest
        from catos.research_catalog import (
            DEFAULT_VALIDATION, MAX_OUTPUT_BYTES, MAX_VALIDATION_CURVE_POINTS, drawdown_pcts,
            json_text, load_registered_strategy,
        )
        from catos.research_validation_job import SCHEMA, execute_validation, validate_validation_request
        count, test_bars, windows = 4_000, 900, 3
        dataset_id = write_fixture(self.root, count=count).name
        source = provenance(dataset_id)
        request = {**DEFAULT_VALIDATION,
                   "backtest": {**DEFAULT_VALIDATION["backtest"], "dataset_id": dataset_id, "warmup_bars": 8},
                   "search_space": {"period": {"low": 2, "high": 8, "step": 3}},
                   "plan": {"train_bars": 1_000, "test_bars": test_bars, "windows": windows}}
        payload, report = execute_validation(request, source)
        self.assertEqual(payload["schema"], SCHEMA)
        self.assertLess(len(json_text({"payload": payload, "report": report}).encode("utf-8")),
                        MAX_OUTPUT_BYTES)
        result = payload["result"]
        self.assertEqual(result["omitted_detail"], ["labels", "windows.evaluation.intervals"])
        self.assertNotIn("labels", result)
        self.assertEqual(sum(row["bar_count"] for row in result["label_counts"]), count)
        _, config, quantity, bars, _, plan, _ = validate_validation_request(request)
        strategy = load_registered_strategy(source)
        for window, diagnostic in zip(result["validation"]["windows"], result["windows"]):
            oos = window["out_of_sample"]
            training = window["training"]
            period = dict(training["trials"][training["selected_trial_number"]]["params"])["period"]
            start = next(i for i, bar in enumerate(bars) if bar.open_time_ms == window["test_start_ms"])
            window_bars = bars[start - plan.warmup_bars:start + test_bars]
            first, last = window_bars[0].open_time_ms, window_bars[-1].open_time_ms + TF
            window_config = replace(config, funding_events=tuple(
                event for event in config.funding_events if first <= event.time_ms <= last))
            replay = backtest(strategy=lambda: strategy(period, quantity), candles=window_bars,
                              config=window_config, warmup_bars=plan.warmup_bars)
            full = json.loads(json_text([asdict(point) for point in replay.equity_curve]))
            sampled = oos["equity_curve"]
            # Sampling thins only the curve: performance, trades and funding stay exact.
            self.assertEqual(oos["performance"], json.loads(json_text(asdict(replay.performance))))
            self.assertEqual(oos["trades"], json.loads(json_text([asdict(t) for t in replay.trades])))
            self.assertEqual(oos["funding"], json.loads(json_text([asdict(f) for f in replay.funding])))
            self.assertEqual(window["curve_sampling"], {
                "total_points": test_bars + 1, "returned_points": len(sampled),
                "method": "bucket_deepest_drawdown_keep_first"})
            self.assertLessEqual(len(sampled), MAX_VALIDATION_CURVE_POINTS // windows)
            by_time = {point["time_ms"]: point for point in full}
            self.assertEqual([by_time[point["time_ms"]] for point in sampled], sampled)
            self.assertEqual([point["time_ms"] for point in sampled],
                             sorted({point["time_ms"] for point in sampled}))
            drawdowns = drawdown_pcts(replay.equity_curve, config.initial_balance)
            deepest = full[max(range(len(full)), key=lambda i: (drawdowns[i], -i))]
            for point in (full[0], full[-1], deepest):
                self.assertIn(point, sampled)
            self.assertNotIn("intervals", diagnostic["evaluation"])
            self.assertTrue(diagnostic["evaluation"]["reconciled"])
            self.assertEqual(diagnostic["evaluation"]["total"]["bar_count"], test_bars)
            self.assertEqual(diagnostic["evaluation"]["total"]["net_pnl"], oos["performance"]["net_pnl"])
        # Fetched data stays in data/okx and is referenced by hash, never embedded.
        reproduction = payload["reproduction"]
        referenced = {item["path"]: item["sha256"] for item in reproduction["referenced_files"]}
        self.assertEqual(referenced, dict(resolve_dataset(dataset_id).files))
        self.assertFalse(any(item["path"] in referenced for item in reproduction["files"]))
        self.assertIn("sha256", reproduction["notice"])
        self.assertIn("<table>", report)
        self.assertNotIn("<pre>", report)

    def test_service_report_footer_names_the_fetched_source(self):
        from catos.research_service import ResearchService
        dataset_id = write_fixture(self.root).name
        with tempfile.TemporaryDirectory() as directory:
            service = ResearchService(directory)
            service.start()
            try:
                reply = lambda envelope: {"payload": {"provenance": envelope["provenance"]},
                                          "report": "<html><body></body></html>"}
                with mock.patch.object(service, "_compute", side_effect=reply):
                    run_id = service.submit(request_for(dataset_id), "fixture")["run_id"]
                    service._thread.join(10)
                report = service.report(run_id)
            finally:
                service.close()
        self.assertIn("固定研究來源 · OKX 公開歷史資料", report)
        self.assertNotIn("合成資料", report)


if __name__ == "__main__":
    unittest.main()
