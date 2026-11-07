"""Registered Donchian breakout: closed-bar rules, research-only registration, research paths."""

from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path
import random
import tempfile
import time
import unittest

from catos import ipc, research_datasets as datasets, strategy_registry
from catos.research import BacktestConfig, Candle, ContractSpec, backtest
from catos.research_catalog import (
    DEFAULT_OPTIMIZATION, DEFAULT_REQUEST, DEFAULT_VALIDATION, DONCHIAN_FILES, DONCHIAN_ID,
    DONCHIAN_MANIFEST, DONCHIAN_SHA256, STRATEGIES, catalog, execute_request, files_hash,
    json_text, load_dataset_bars, load_registered_strategy, provenance, registered_factory,
    resolve_dataset, validate_optimization_request, validate_request, validate_strategy_manifest,
)
from catos.research_donchian import RegisteredDonchian, _Extreme
from catos.research_optimization import execute_optimization
from catos.research_service import ResearchService
from catos.research_validation_job import execute_validation, validate_validation_request
from test_research_datasets import DatasetFixture, write_fixture

CONTRACT = ContractSpec("BTC-USDT-SWAP", Decimal("0.01"), Decimal("0.1"), Decimal("1"), Decimal("1"))
STEP = 900_000


def donchian_request(**over):
    request = {**json.loads(json_text(DEFAULT_REQUEST)), "strategy_id": DONCHIAN_ID,
               "parameters": {"entry_bars": 6, "exit_bars": 3, "quantity": "1"}, "warmup_bars": 6}
    request.update(over)
    return request


def donchian_validation(**over):
    request = {**json.loads(json_text(DEFAULT_VALIDATION)),
               "backtest": donchian_request(),
               "search_space": {"entry_bars": {"low": 4, "high": 6, "step": 2},
                                "exit_bars": {"low": 2, "high": 3, "step": 1}},
               "max_candidates": 4, "max_runs": 15}
    request.update(over)
    return request


def candles(rows):
    return tuple(Candle(index * STEP, *map(Decimal, row)) for index, row in enumerate(rows))


class RuleTests(unittest.TestCase):
    def test_rolling_extremes_match_brute_force(self):
        rng = random.Random(7)
        values = [Decimal(rng.randrange(-50, 50)) / 10 for _ in range(400)]
        for size in (1, 2, 5, 17):
            for highest in (True, False):
                extreme = _Extreme(size, highest)
                for index, value in enumerate(values):
                    extreme.push(value)
                    window = values[max(0, index + 1 - size):index + 1]
                    self.assertEqual(extreme.value, max(window) if highest else min(window))

    def test_breakout_exit_and_reversal_on_closed_bars(self):
        # (open, high, low, close); entry channel 3 bars, exit channel 2 bars, warm-up 3.
        bars = candles([
            ("9", "10", "8", "9"), ("9", "11", "9", "10"), ("10", "12", "9", "11"),
            ("11", "12", "11", "12"),        # close equals the previous 3-bar high: no entry
            ("12", "13.5", "12", "13"),      # close above 12: long from the next open
            ("13", "14", "12.5", "13.5"),    # inside both channels: hold
            ("13", "13", "11.2", "11.5"),    # below the 2-bar low 12, above the 3-bar low 11: exit
            ("11.5", "11.6", "10", "10.5"),  # below the 3-bar low 11.2: short
            ("10.5", "15", "10.4", "14.5"),  # above the 3-bar high 14: reverse to long
            ("14.5", "15", "14", "14.8"),    # inside both channels: hold
        ])
        config = BacktestConfig(CONTRACT, STEP, Decimal("1000"), Decimal("0"), Decimal("0"), ())
        result = backtest(strategy=lambda: RegisteredDonchian(3, 2, Decimal("1")), candles=bars,
                          config=config, warmup_bars=3)
        fills = [(trade.time_ms // STEP, trade.quantity, trade.price, trade.position_after)
                 for trade in result.trades]
        self.assertEqual(fills, [(5, Decimal("1"), Decimal("13"), Decimal("1")),
                                 (7, Decimal("-1"), Decimal("11.5"), Decimal("0")),
                                 (8, Decimal("-1"), Decimal("10.5"), Decimal("-1")),
                                 (9, Decimal("2"), Decimal("14.5"), Decimal("1"))])
        self.assertIsNone(result.pending_intent)

    def test_short_exit_uses_the_exit_channel_high(self):
        bars = candles([
            ("10", "11", "9", "10"), ("10", "11", "9", "10"), ("10", "11", "9", "10"),
            ("10", "10", "8", "8.5"),        # below the 3-bar low 9: short
            ("8.5", "9", "8", "8.2"),        # inside: hold
            ("8.2", "10.5", "8.1", "10.2"),  # above the 2-bar high 10 but below 11: cover
        ])
        config = BacktestConfig(CONTRACT, STEP, Decimal("1000"), Decimal("0"), Decimal("0"), ())
        result = backtest(strategy=lambda: RegisteredDonchian(3, 2, Decimal("1")), candles=bars,
                          config=config, warmup_bars=3)
        self.assertEqual([(trade.time_ms // STEP, trade.position_after) for trade in result.trades],
                         [(4, Decimal("-1"))])
        self.assertEqual(result.pending_intent.target_position, Decimal("0"))

    def test_warmup_must_cover_the_entry_channel(self):
        bars = candles([("10", "11", "9", "10")] * 8)
        config = BacktestConfig(CONTRACT, STEP, Decimal("1000"), Decimal("0"), Decimal("0"), ())
        with self.assertRaisesRegex(ValueError, "not ready after warm-up"):
            backtest(strategy=lambda: RegisteredDonchian(4, 2, Decimal("1")), candles=bars,
                     config=config, warmup_bars=3)
        backtest(strategy=lambda: RegisteredDonchian(4, 2, Decimal("1")), candles=bars,
                 config=config, warmup_bars=4)


class RegistrationTests(unittest.TestCase):
    def test_pinned_artifact_and_catalog_entry(self):
        manifest = json.loads(DONCHIAN_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(files_hash(DONCHIAN_FILES), DONCHIAN_SHA256)
        self.assertEqual(manifest["sha256"], DONCHIAN_SHA256)
        self.assertEqual(manifest["provenance"]["scope"], "research-only")
        strategies = catalog()["strategies"]
        # Package E (2026-11-06) appended three preregistered daily strategies after these two,
        # package F (2026-11-07) two intraday DCM strategies.
        self.assertEqual([item["id"] for item in strategies],
                         ["sma-trend", DONCHIAN_ID, "donchian-ensemble", "tsmom-multi", "dcm-daily",
                          "dcm-fade", "dcm-pullback"])
        donchian = strategies[1]
        self.assertEqual(donchian["parameters"], {"entry_bars": {"min": 2, "max": 960},
                                                  "exit_bars": {"min": 1, "max": 959},
                                                  "quantity": {"unit": "contracts"}})
        self.assertEqual(donchian["warmup"], {"covers": "entry_bars", "below": 961, "min_days": 0})
        self.assertEqual(donchian["entry"], "catos.research_donchian:RegisteredDonchian")
        self.assertEqual(strategies[0]["warmup"], {"covers": "period", "below": 64, "min_days": 0})

    def test_manifest_fields_are_pinned(self):
        manifest = json.loads(DONCHIAN_MANIFEST.read_text(encoding="utf-8"))
        spec = STRATEGIES[DONCHIAN_ID]
        cases = {"sha256": ("0" * 64, "artifact_identity_mismatch"),
                 "entry": ("catos.research_donchian:Other", "artifact_entry_mismatch"),
                 "provenance": ({**manifest["provenance"], "scope": "local-sim"},
                                "artifact_provenance_mismatch"),
                 "source_files": (["catos/research_strategy.py"], "artifact_source_files_mismatch"),
                 "approval_state": ("draft", "artifact_not_approved")}
        for field, (value, error) in cases.items():
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, error):
                validate_strategy_manifest({**manifest, field: value}, spec)

    def test_build_id_covers_the_research_strategy_sources(self):
        from catos.research_api import RUNTIME_FILES
        for path in (*DONCHIAN_FILES, DONCHIAN_MANIFEST.relative_to(DONCHIAN_MANIFEST.parents[2]).as_posix()):
            self.assertIn(path, RUNTIME_FILES)

    def test_worker_registry_and_ipc_never_resolve_the_research_strategy(self):
        self.assertNotIn(DONCHIAN_ID, {sid for sid, _ in strategy_registry.manifests()})
        with self.assertRaisesRegex(strategy_registry.RegistryError, "unknown_strategy"):
            strategy_registry.resolve(DONCHIAN_ID)
        wire = ipc.WorkerConfig(CONTRACT, STEP, 4, strategy_id=DONCHIAN_ID).to_wire()
        with self.assertRaisesRegex(ipc.ProtocolError, "unregistered strategy"):
            ipc.WorkerConfig.from_wire(wire)

    def test_loaded_class_comes_from_verified_bytes_and_must_match_the_request(self):
        source = provenance(DEFAULT_REQUEST["dataset_id"], DONCHIAN_ID)
        loaded = load_registered_strategy(source)
        self.assertEqual(loaded.__name__, "RegisteredDonchian")
        self.assertIsNot(loaded, RegisteredDonchian)
        with self.assertRaisesRegex(ValueError, "strategy_source_mismatch"):
            registered_factory(provenance(), DONCHIAN_ID, Decimal("1"))
        with self.assertRaisesRegex(ValueError, "strategy_source_mismatch"):
            registered_factory(source, "sma-trend", Decimal("1"))


class RequestTests(unittest.TestCase):
    def test_backtest_parameters_are_bounded(self):
        _, _, params, quantity = validate_request(donchian_request())
        self.assertEqual((params, quantity), ({"entry_bars": 6, "exit_bars": 3}, Decimal("1")))
        variants = [
            {"parameters": {"entry_bars": 6, "quantity": "1"}},
            {"parameters": {"entry_bars": 6, "exit_bars": 6, "quantity": "1"}},
            {"parameters": {"entry_bars": 961, "exit_bars": 3, "quantity": "1"}, "warmup_bars": 961},
            {"parameters": {"entry_bars": 6, "exit_bars": 0, "quantity": "1"}},
            {"parameters": {"entry_bars": 6, "exit_bars": True, "quantity": "1"}},
            {"parameters": {"period": 6, "quantity": "1"}},
            {"warmup_bars": 5}, {"warmup_bars": 961},
        ]
        for changes in variants:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_request(donchian_request(**changes))
        # The 96-bar synthetic fixture cannot hold a 200-bar warm-up; a 960-bar one fits a fetched dataset.
        with self.assertRaisesRegex(ValueError, "must leave evaluation bars in the 96-bar dataset"):
            validate_request(donchian_request(parameters={"entry_bars": 200, "exit_bars": 10, "quantity": "1"},
                                              warmup_bars=200))
        validate_request(donchian_request(parameters={"entry_bars": 95, "exit_bars": 94, "quantity": "1"},
                                          warmup_bars=95))

    def test_search_spaces_keep_every_grid_point_valid(self):
        def optimization(space, warmup=6):
            return {**json.loads(json_text(DEFAULT_OPTIMIZATION)),
                    "backtest": donchian_request(warmup_bars=warmup), "search_space": space}

        good = {"entry_bars": {"low": 4, "high": 6, "step": 2}, "exit_bars": {"low": 1, "high": 3, "step": 1}}
        validate_optimization_request(optimization(good))
        for space, error in [
            ({"period": {"low": 2, "high": 4, "step": 1}}, "only registered entry_bars and exit_bars"),
            ({**good, "exit_bars": {"low": 1, "high": 4, "step": 1}}, "below lowest entry_bars"),
            ({**good, "entry_bars": {"low": 4, "high": 7, "step": 2}}, "aligned integer range"),
            ({**good, "entry_bars": {"low": 4, "high": 8, "step": 2}}, "must cover highest searched entry_bars"),
        ]:
            with self.subTest(space=space), self.assertRaisesRegex(ValueError, error):
                validate_optimization_request(optimization(space))
        validate_validation_request(donchian_validation())
        for changes, error in [
            ({"search_space": {"entry_bars": {"low": 6, "high": 6, "step": 1},
                               "exit_bars": {"low": 3, "high": 3, "step": 1}}}, "at least two candidates"),
            ({"max_candidates": 3}, "max_candidates"),
            ({"search_space": {"entry_bars": {"low": 4, "high": 6, "step": 2},
                               "exit_bars": {"low": 2, "high": 4, "step": 1}},
              "max_candidates": 6, "max_runs": 21}, "below lowest entry_bars"),
        ]:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, error):
                validate_validation_request(donchian_validation(**changes))


class ExecutionTests(unittest.TestCase):
    def test_backtest_matches_the_core_engine(self):
        request = donchian_request()
        source = provenance(request["dataset_id"], DONCHIAN_ID)
        payload, report = execute_request(request, source)
        _, config, _, _ = validate_request(request)
        bars, config = load_dataset_bars(request["dataset_id"], config)
        direct = backtest(strategy=lambda: RegisteredDonchian(6, 3, Decimal("1")), candles=bars,
                          config=config, warmup_bars=6)
        self.assertEqual(payload["result"], json.loads(json_text(asdict(direct))))
        self.assertGreater(direct.performance.trade_count, 0)
        self.assertEqual(payload["provenance"]["strategy"]["id"], DONCHIAN_ID)
        self.assertIn("<html", report)

    def test_optimization_searches_both_axes(self):
        request = {**json.loads(json_text(DEFAULT_OPTIMIZATION)), "backtest": donchian_request(),
                   "search_space": {"entry_bars": {"low": 4, "high": 6, "step": 2},
                                    "exit_bars": {"low": 1, "high": 3, "step": 1}},
                   "n_trials": 6}
        payload, report = execute_optimization(request, provenance(DEFAULT_REQUEST["dataset_id"], DONCHIAN_ID))
        self.assertEqual(len(payload["trials"]), 6)
        for trial in payload["trials"]:
            self.assertEqual(trial["state"], "COMPLETE", trial)
            self.assertIn(trial["params"]["entry_bars"], (4, 6))
            self.assertIn(trial["params"]["exit_bars"], (1, 2, 3))
        self.assertIn("<th>參數</th>", report)
        self.assertIn("entry_bars=", report)
        self.assertNotIn("合成資料樣本內搜尋", report)

    def test_walk_forward_selects_from_the_two_axis_grid(self):
        request = donchian_validation()
        source = provenance(DEFAULT_REQUEST["dataset_id"], DONCHIAN_ID)
        payload, report = execute_validation(request, source)
        self.assertTrue(payload["evaluation_complete"])
        _, config, quantity, bars, space, plan, _ = validate_validation_request(request)
        self.assertEqual(set(space), {"entry_bars", "exit_bars"})
        for window in payload["result"]["validation"]["windows"]:
            training = window["training"]
            self.assertEqual(len(training["trials"]), 4)
            chosen = dict(training["trials"][training["selected_trial_number"]]["params"])
            start = next(i for i, bar in enumerate(bars) if bar.open_time_ms == window["test_start_ms"])
            replay = backtest(
                strategy=lambda: RegisteredDonchian(chosen["entry_bars"], chosen["exit_bars"], quantity),
                candles=bars[start - plan.warmup_bars:start + plan.test_bars], config=config,
                warmup_bars=plan.warmup_bars)
            self.assertEqual(window["out_of_sample"], json.loads(json_text(asdict(replay))))
        paths = [item["path"] for item in payload["reproduction"]["files"]]
        self.assertIn("catos/research_donchian.py", paths)
        self.assertIn("catos/research_only_artifacts/donchian-breakout-donchian-parameters-v1.json", paths)
        self.assertNotIn("catos/research_strategy.py", paths)
        self.assertIn("選定參數", report)
        self.assertIn("entry_bars=", report)


class FetchedDatasetTests(DatasetFixture):
    def test_walk_forward_on_a_fetched_dataset(self):
        target = write_fixture(self.root, count=1500)
        dataset_id = json.loads((target / datasets.MANIFEST).read_text(encoding="utf-8"))["dataset_id"]
        request = donchian_validation(
            backtest=donchian_request(dataset_id=dataset_id, warmup_bars=48,
                                      parameters={"entry_bars": 48, "exit_bars": 12, "quantity": "1"}),
            search_space={"entry_bars": {"low": 24, "high": 48, "step": 24},
                          "exit_bars": {"low": 6, "high": 12, "step": 6}},
            plan={"train_bars": 300, "test_bars": 200, "windows": 3})
        payload, _ = execute_validation(request, provenance(dataset_id, DONCHIAN_ID))
        self.assertTrue(payload["evaluation_complete"])
        self.assertEqual(len(payload["result"]["validation"]["windows"]), 3)
        self.assertEqual({item["path"] for item in payload["reproduction"]["referenced_files"]},
                         {path for path, _ in resolve_dataset(dataset_id).files})
        for window in payload["result"]["windows"]:
            self.assertTrue(window["evaluation"]["reconciled"])


class ServiceTests(unittest.TestCase):
    def test_service_runs_a_donchian_backtest_with_its_own_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            service = ResearchService(directory)
            service.start()
            try:
                task = service.submit(donchian_request(), "donchian-fixture")
                self.assertEqual(task["provenance"]["strategy"]["id"], DONCHIAN_ID)
                deadline = time.monotonic() + 20
                while service.task(task["run_id"])["status"] not in ("complete", "failed"):
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.02)
                self.assertEqual(service.task(task["run_id"])["status"], "complete",
                                 service.task(task["run_id"]))
                result = service.result(task["run_id"])
                self.assertEqual(result["provenance"]["strategy"]["sha256"], DONCHIAN_SHA256)
                self.assertTrue(Path(directory, task["run_id"], "report.html").is_file())
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
