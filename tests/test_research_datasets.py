"""Fetched-dataset manifests: write, verify, resolve and run research on them (offline)."""

from decimal import Decimal
import json
from pathlib import Path
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

    def test_writer_refuses_gaps_incomplete_funding_and_overwrite(self):
        bars = make_bars(192)
        with self.assertRaisesRegex(ValueError, "dataset_has_gaps"):
            write_fixture(self.root, candles=bars[:50] + bars[51:])
        end = START + 192 * TF
        with self.assertRaisesRegex(ValueError, "funding_incomplete"):
            write_fixture(self.root, funding=make_funding(START + EIGHT_H, end))
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
        self.assertEqual(len(payload["drawdown_curve"]), len(payload["result"]["equity_curve"]))
        self.assertIn("<", report)
        with self.assertRaisesRegex(ValueError, "source_changed"):
            execute_request(request_for(dataset_id), provenance())

    def test_large_dataset_curve_is_sampled_keeping_the_deepest_drawdown(self):
        count = MAX_CURVE_POINTS + 400
        dataset_id = write_fixture(self.root, count=count).name
        payload, _ = execute_request(request_for(dataset_id), provenance(dataset_id))
        sampling = payload["curve_sampling"]
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
        # Walk-forward output does not fit the output cap on fetched data yet; reject up front.
        validation = {**DEFAULT_VALIDATION,
                      "backtest": {**DEFAULT_VALIDATION["backtest"], "dataset_id": dataset_id}}
        with self.assertRaisesRegex(ValueError, "validation_supports_synthetic_dataset_only"):
            execute_validation(validation, source)
        payload, _ = execute_validation(DEFAULT_VALIDATION, provenance())
        self.assertEqual(payload["provenance"]["dataset"]["id"], DATASET_ID)


if __name__ == "__main__":
    unittest.main()
