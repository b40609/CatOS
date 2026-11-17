"""strategies/ folder strategies (2026-11-17, docs/agent-strategy-submission-proposal.md).

Every test writes its strategies under an isolated CATOS_STRATEGY_HOME and uses an
isolated approvals file and research output directory; nothing touches outputs/,
the repository's strategies/ folder or a network.
"""

from decimal import Decimal
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit

from catos import (account_lock, local_sim_replay, replay_consistency, research, research_catalog, research_optimization,
                   research_overfit, strategy_approvals as approvals, strategy_folder, strategy_registry)
from catos.research_mcp import CHECK_TIMEOUT_SECONDS, ResearchHttpBridge
from catos.research_service import ResearchError, ResearchService
from kill_isolation import setUpModule, tearDownModule  # noqa: F401  (isolated Kill-Switch file)

D = Decimal
SID = "test-cross"
EXAMPLE = Path(__file__).resolve().parent.parent / "strategies" / "example-sma-cross"
SOURCE = (EXAMPLE / "strategy.py").read_text(encoding="utf-8")
MANIFEST = {**json.loads((EXAMPLE / "strategy.json").read_text(encoding="utf-8")), "strategy_id": SID}
# Long once it has ever seen `slow` bars rise in a row: state older than the window.
STATEFUL = '''
from collections import deque
from decimal import Decimal
from catos.research import Strategy


class SmaCross(Strategy):
    def __init__(self, fast, slow, quantity):
        self.closes = deque(maxlen=slow)
        self.seen = 0
        self.quantity = quantity

    def update_indicators(self, bar):
        self.closes.append(bar.close)
        self.seen += 1

    @property
    def ready(self):
        return len(self.closes) == self.closes.maxlen

    def on_bar(self, bar, account):
        return self.quantity if self.seen % 7 < 3 else -self.quantity
'''
START = 1_767_225_600_000
STEP = 900_000
CLOSES = ("100", "100", "100", "100", "110", "112", "115", "111", "95", "90", "88", "92",
          "95", "100", "120", "121", "80", "79", "78", "85", "86", "90")


def bars(closes=CLOSES):
    return tuple(research.Candle(START + i * STEP, D(c), D(c), D(c), D(c)) for i, c in enumerate(closes))


def yes(_text, _word):
    return True


class Home(unittest.TestCase):
    def setUp(self):
        self.temp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.dict(os.environ, {strategy_folder.HOME_ENV: str(self.temp),
                                                  approvals.ENV_PATH: str(self.temp / "approvals.jsonl")}))
        # Replays take the local-sim account lock; keep it out of ~/.catos, where the real Bot's lock lives.
        self.enterContext(patch.object(account_lock, "LOCK_DIRECTORY", self.temp / "locks"))

    def write(self, sid=SID, source=SOURCE, **manifest):
        directory = self.temp / "strategies" / sid
        directory.mkdir(parents=True, exist_ok=True)
        value = {**MANIFEST, "strategy_id": sid, **manifest}
        (directory / "strategy.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        (directory / "strategy.py").write_text(source, encoding="utf-8")
        return directory

    def request(self, fast=2, slow=4, warmup=4, quantity="1", sid=SID):
        return dict(research_catalog.DEFAULT_REQUEST, strategy_id=sid, warmup_bars=warmup,
                    parameters={"fast": fast, "slow": slow, "quantity": quantity})


class FolderContractTests(Home):
    def test_catalog_lists_valid_folders_and_reports_broken_ones(self):
        self.write()
        (self.temp / "strategies" / "broken").mkdir()
        (self.temp / "strategies" / "broken" / "strategy.json").write_text("{", encoding="utf-8")
        self.write("sma-trend")  # a built-in name
        catalog = research_catalog.catalog()
        ids = [item["id"] for item in catalog["strategies"]]
        self.assertEqual(ids[:7], list(research_catalog.STRATEGIES))
        self.assertIn(SID, ids)
        item = next(item for item in catalog["strategies"] if item["id"] == SID)
        source = (self.temp / "strategies" / SID / "strategy.py").read_bytes()
        expected = strategy_folder.source_hash([(f"strategies/{SID}/strategy.py", strategy_folder._sha256(source))])
        self.assertEqual(item["sha256"], expected)
        self.assertEqual((item["origin"], item["source"], item["approval_state"]),
                         ("folder", "user_strategy_folder", "research"))
        self.assertEqual(item["constraints"], [["fast", "<", "slow"]])
        self.assertEqual(item["preset"]["parameters"], {"fast": 20, "slow": 50})
        errors = {error["strategy_id"]: error["error"] for error in catalog["strategy_folder"]["errors"]}
        self.assertIn("invalid JSON", errors["broken"])
        self.assertIn("built-in", errors["sma-trend"])
        with self.assertRaisesRegex(ValueError, "strategy_folder_invalid"):
            research_catalog.strategy_spec("broken")
        self.assertEqual(research_catalog.strategy_spec("sma-trend").origin, "builtin")

    def test_source_and_manifest_outside_the_contract_are_refused(self):
        sources = {
            "import os": "import os\n" + SOURCE,
            "from . import": "from . import helper\n" + SOURCE,
            "float literal": SOURCE.replace('Decimal("0")', "0.0"),
            "float is not allowed": SOURCE.replace("self.fast = fast", "self.fast = float(fast)"),
            "exactly one top-level class": SOURCE.replace("class SmaCross", "class Other"),
            "syntax error": SOURCE + "\ndef broken(:\n",
        }
        for expected, source in sources.items():
            with self.subTest(expected):
                self.write(source=source)
                with self.assertRaisesRegex(ValueError, expected):
                    research_catalog.strategy_spec(SID)
        manifests = {
            "exact fields": {"extra": 1},
            "not quantity": {"parameters": [{"name": "quantity", "min": 1, "max": 3, "default": 2}],
                             "lookback": "quantity", "constraints": []},
            "lookback must name": {"lookback": "window"},
            "defaults break": {"constraints": [["slow", "<", "fast"]]},
            "folder name": {"strategy_id": "other-name"},
            "min < max": {"parameters": [{"name": "fast", "min": 3, "max": 3, "default": 3},
                                         {"name": "slow", "min": 3, "max": 9, "default": 5}]},
        }
        for expected, changes in manifests.items():
            with self.subTest(expected):
                self.write(**changes)
                with self.assertRaisesRegex(ValueError, expected):
                    research_catalog.strategy_spec(SID)
        directory = self.write()
        (directory / "strategy.json").write_text(
            (directory / "strategy.json").read_text(encoding="utf-8").replace('"default": 20', '"default": 20.0'),
            encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "integers and strings only"):
            research_catalog.strategy_spec(SID)

    def test_constraints_apply_to_requests_and_search_grids(self):
        self.write()
        with self.assertRaisesRegex(ValueError, "fast: must be below slow"):
            research_catalog.validate_request(self.request(fast=4, slow=4))
        with self.assertRaisesRegex(ValueError, "warmup_bars"):
            research_catalog.validate_request(self.request(warmup=3))
        optimization = {"backtest": self.request(warmup=6), "n_trials": 4, "seed": 1,
                        "search_space": {"fast": {"low": 2, "high": 5, "step": 1}, "slow": {"low": 4, "high": 6, "step": 1}}}
        with self.assertRaisesRegex(ValueError, "fast: highest searched value must be below lowest slow"):
            research_catalog.validate_optimization_request(optimization)


class FolderResearchTests(Home):
    def test_backtest_optimization_and_validation_run_a_folder_strategy(self):
        self.write()
        source = research_catalog.provenance(research_catalog.DATASET_ID, SID)
        payload, report = research_catalog.execute_request(self.request(), source)
        self.assertEqual(payload["provenance"]["strategy"]["id"], SID)
        self.assertGreater(len(payload["result"]["trades"]), 0)
        self.assertIn("</body>", report)
        # Same numbers as constructing the class directly.
        strategy_class = research_catalog.verified_strategy_class(research_catalog.strategy_spec(SID))
        _, config, _, _ = research_catalog.validate_request(self.request())
        direct = research.backtest(strategy=lambda: strategy_class(fast=2, slow=4, quantity=D("1")),
                                   candles=research_catalog.load_dataset_bars(research_catalog.DATASET_ID, config)[0],
                                   config=config, warmup_bars=4)
        self.assertEqual(payload["result"]["performance"]["return_pct"], str(direct.performance.return_pct))
        optimization = {"backtest": self.request(warmup=6), "n_trials": 6, "seed": 1,
                        "search_space": {"fast": {"low": 2, "high": 3, "step": 1}, "slow": {"low": 4, "high": 6, "step": 1}}}
        payload, _ = research_optimization.execute_optimization(optimization, source, {"configurations": 60})
        self.assertEqual(payload["overfitting"]["distinct_trials"], 6)
        self.assertEqual(payload["overfitting"]["history_trials"], 60)
        if payload["overfitting"]["dsr"] is not None:
            self.assertLessEqual(D(payload["overfitting"]["dsr_with_history"]), D(payload["overfitting"]["dsr"]))
        payload, _ = research_optimization.execute_optimization(optimization, source, {"configurations": 6})
        self.assertIsNone(payload["overfitting"]["history_trials"])
        from catos.research_validation_job import execute_validation
        validation = dict(research_catalog.DEFAULT_VALIDATION, backtest=self.request(warmup=5),
                          search_space={"fast": {"low": 2, "high": 3, "step": 1}, "slow": {"low": 4, "high": 5, "step": 1}},
                          max_candidates=4, max_runs=40)
        payload, _ = execute_validation(validation, source)
        names = {item["path"] for item in payload["reproduction"]["files"]}
        self.assertIn(f"strategies/{SID}/strategy.py", names)
        self.assertIn(f"strategies/{SID}/strategy.json", names)

    def test_an_edit_after_submission_is_detected(self):
        directory = self.write()
        source = research_catalog.provenance(research_catalog.DATASET_ID, SID)
        (directory / "strategy.py").write_text(SOURCE + "\n# edited\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            research_catalog.execute_request(self.request(), source)
        self.assertNotEqual(research_catalog.provenance(research_catalog.DATASET_ID, SID), source)

    def test_check_passes_a_window_strategy_and_explains_failures(self):
        self.write()
        source = research_catalog.provenance(research_catalog.DATASET_ID, SID)
        report = research_catalog.execute_check({"strategy_id": SID}, source)
        self.assertTrue(report["ok"] and report["bot_eligible"], report)
        self.assertEqual(report["parameters"], {"fast": 20, "slow": 50})
        self.assertGreater(report["trades"], 0)
        self.assertEqual([stage["name"] for stage in report["stages"]],
                         ["load", "construct", "backtest", "deterministic", "restart_consistency"])
        self.assertEqual(report["strategy"]["sha256"], source["strategy"]["sha256"])

        self.write(source=STATEFUL)
        source = research_catalog.provenance(research_catalog.DATASET_ID, SID)
        report = research_catalog.execute_check({"strategy_id": SID, "parameters": {"fast": 2, "slow": 5}}, source)
        self.assertTrue(report["ok"])
        self.assertFalse(report["bot_eligible"])
        self.assertIn("不能上 Bot", report["bot_reason"])

        self.write(source=SOURCE.replace("closes = list(self.closes)", "closes = list(self.closes)\n        1 / 0"))
        source = research_catalog.provenance(research_catalog.DATASET_ID, SID)
        report = research_catalog.execute_check({"strategy_id": SID}, source)
        self.assertFalse(report["ok"])
        failed = [stage for stage in report["stages"] if not stage["ok"]]
        self.assertEqual(failed[0]["name"], "backtest")
        self.assertIn("ZeroDivisionError", failed[0]["detail"])
        self.assertIn("strategy.py line", failed[0]["detail"])

        self.write(source=SOURCE.replace("class SmaCross(Strategy):", "class SmaCross:"))
        source = research_catalog.provenance(research_catalog.DATASET_ID, SID)
        report = research_catalog.execute_check({"strategy_id": SID}, source)
        self.assertEqual(report["stages"][0]["name"], "load")
        self.assertIn("catos.research.Strategy", report["stages"][0]["detail"])
        with self.assertRaisesRegex(ValueError, "only strategies/ folder"):
            research_catalog.validate_check_request({"strategy_id": "sma-trend"})


class ServiceTests(Home):
    def setUp(self):
        super().setUp()
        self.write()
        self.service = ResearchService(self.temp / "research")
        self.service.start()
        self.addCleanup(self.service.close)

    def wait(self, run_id):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            task = self.service.task(run_id)
            if task["status"] in ("complete", "failed"):
                return task
            time.sleep(0.05)
        raise AssertionError("research task did not finish")

    def test_check_runs_in_the_worker_and_runs_are_counted_per_strategy(self):
        report = self.service.check({"strategy_id": SID, "parameters": {"fast": 3, "slow": 8}})
        self.assertTrue(report["ok"] and report["bot_eligible"], report)
        self.assertIsNone(self.service.active_run)
        self.assertFalse((self.temp / "research" / "trials.jsonl").exists())
        first = self.service.submit(self.request(), "build")
        self.assertEqual(self.wait(first["run_id"])["status"], "complete")
        self.assertEqual(first["trial_log"]["runs"], 1)
        optimization = {"backtest": self.request(warmup=6), "n_trials": 20, "seed": 1,
                        "search_space": {"fast": {"low": 2, "high": 3, "step": 1}, "slow": {"low": 4, "high": 6, "step": 1}}}
        second = self.service.submit_optimization(optimization, "build")
        self.assertEqual(self.wait(second["run_id"])["status"], "complete", self.service.task(second["run_id"]))
        self.assertEqual((second["trial_log"]["runs"], second["trial_log"]["configurations"],
                          second["trial_log"]["versions"]), (2, 7, 1))
        result = self.service.result(second["run_id"])
        self.assertEqual(result["trial_log"], second["trial_log"])
        self.assertEqual(result["overfitting"]["history_trials"], 7)
        other = self.service.submit(dict(research_catalog.DEFAULT_REQUEST), "build")
        self.assertEqual(other["trial_log"]["runs"], 1)  # another strategy has its own count
        self.wait(other["run_id"])
        good = (self.temp / "research" / "trials.jsonl").read_text(encoding="utf-8")
        line = json.loads(good.splitlines()[0])
        for broken in ("not json\n", json.dumps({**line, "configurations": -5}) + "\n",
                       json.dumps({key: value for key, value in line.items() if key != "sha256"}) + "\n"):
            with self.subTest(broken=broken[:30]):
                (self.temp / "research" / "trials.jsonl").write_text(good + broken, encoding="utf-8")
                with self.assertRaises(ResearchError) as caught:
                    self.service.submit(self.request(), "build")
                self.assertEqual(str(caught.exception), "trial_log_unreadable")


class ApiTests(Home):
    def test_strategy_check_endpoint(self):
        from fastapi.testclient import TestClient
        from catos.research_api import create_app

        self.write()
        app = create_app(output_dir=self.temp / "research")
        with TestClient(app, base_url="http://127.0.0.1:8770") as client:
            build = client.get("/api/research/version").json()["build_id"]
            reply = client.post("/api/research/strategy-checks", json={"strategy_id": SID},
                                headers={"X-CatOS-Build": build})
            self.assertEqual(reply.status_code, 200, reply.text)
            self.assertTrue(reply.json()["bot_eligible"])
            reply = client.post("/api/research/strategy-checks", json={"strategy_id": "nope"},
                                headers={"X-CatOS-Build": build})
            self.assertEqual((reply.status_code, reply.json()["detail"]), (422, "unknown_strategy"))
            reply = client.post("/api/research/strategy-checks", json={"strategy_id": SID},
                                headers={"X-CatOS-Build": "stale"})
            self.assertEqual(reply.status_code, 409)
            ids = [item["id"] for item in client.get("/api/research/catalog").json()["strategies"]]
            self.assertIn(SID, ids)


class LocalResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class BridgeTests(unittest.TestCase):
    def test_check_and_validation_tools_call_the_local_service(self):
        calls = []

        def opener(request, timeout):
            path = urlsplit(request.full_url).path
            calls.append((request.get_method(), path, timeout, request.data, request.get_header("X-catos-build")))
            if path == "/api/research/version":
                return LocalResponse(json.dumps({"restart_required": False, "build_id": "b1"}).encode())
            if path == "/api/research/catalog":
                return LocalResponse(json.dumps({"strategies": [{"id": SID, "version": "v1", "sha256": "a" * 64}]}).encode())
            if path in ("/api/research/strategy-checks", "/api/research/validations"):
                return LocalResponse(b'{"ok": true}')
            raise HTTPError(request.full_url, 404, "x", {}, BytesIO(b"{}"))

        bridge = ResearchHttpBridge(opener=opener)
        self.assertEqual(bridge.check_strategy(SID, {"fast": 2, "slow": 4}, "2"), {"ok": True})
        method, path, timeout, data, build = calls[-1]
        self.assertEqual((method, path, timeout, build), ("POST", "/api/research/strategy-checks", CHECK_TIMEOUT_SECONDS, "b1"))
        self.assertEqual(json.loads(data), {"strategy_id": SID, "parameters": {"fast": 2, "slow": 4}, "quantity": "2"})
        binding = {"id": SID, "version": "v1", "sha256": "a" * 64}
        self.assertEqual(bridge.submit_validation(binding, {"x": 1}), {"ok": True})
        self.assertEqual(calls[-1][:3], ("POST", "/api/research/validations", 5))


class McpResultFieldsTests(unittest.TestCase):
    def test_get_result_can_return_only_the_requested_fields(self):  # trial-user friction 1
        import asyncio
        from catos.research_mcp import create_mcp_server

        class Bridge:
            def get_result(self, run_id):
                return {"trial_log": {"runs": 2}, "result": {"fills": [1] * 1000}, "costs": {"net": "1"}}

        server = create_mcp_server(Bridge())

        def call(arguments):
            reply = asyncio.run(server.call_tool("research_get_result", arguments))
            return reply[1] if isinstance(reply, tuple) else reply

        self.assertEqual(call({"run_id": "a" * 32, "fields": ["trial_log", "missing"]}),
                         {"available_fields": ["costs", "result", "trial_log"], "trial_log": {"runs": 2}})
        self.assertEqual(set(call({"run_id": "a" * 32})), {"trial_log", "result", "costs"})


class FolderBotTests(Home):
    def profile(self, fast=2, slow=4, **changes):
        value = {"schema": "catos.strategy-deployment", "schema_version": 1, "strategy_id": SID, "version": "v1",
                 "parameters": {"fast": fast, "slow": slow}, "quantity": "1", "inst_id": "BTC-USDT-SWAP",
                 "timeframe_ms": STEP, "warmup_bars": slow, "initial_balance": "1000", "fee_rate": "0.0005",
                 "slippage_bps": "2"}
        value.update(changes)
        return value

    def approve(self, value):
        artifact, _ = approvals.deployment_identity(value)
        shown = []
        record = approvals.approve(strategy_id=value["strategy_id"], version=value["version"],
                                   sha256=artifact["sha256"], profile=value,
                                   confirm=lambda text, word: shown.append(text) or True)
        return record, shown[0]

    def test_approval_runs_the_restart_check_and_binds_the_folder_files(self):
        directory = self.write()
        record, text = self.approve(self.profile())
        self.assertIn("重啟一致性檢查通過", text)
        self.assertEqual(record["entry"], f"strategies/{SID}/strategy.py:SmaCross")
        config = local_sim_replay.worker_config(record, research_catalog.SYNTHETIC_CONTRACT)
        deployment = strategy_registry.resolve_deployment(config)
        strategy = deployment.instantiate_deployment(config.deployment)
        self.assertEqual((strategy.fast, strategy.closes.maxlen, strategy.quantity), (2, 4, D("1")))
        with self.assertRaisesRegex(approvals.ApprovalError, "profile_fast_must_be_below_slow"):
            approvals.validate_profile(self.profile(fast=4, slow=4))
        (directory / "strategy.py").write_text(SOURCE + "\n# edited\n", encoding="utf-8")
        with self.assertRaises(strategy_registry.RegistryError):
            strategy_registry.resolve_deployment(config)
        (directory / "strategy.py").write_text(SOURCE, encoding="utf-8")
        strategy_registry.resolve_deployment(config)
        manifest = json.loads((directory / "strategy.json").read_text(encoding="utf-8"))
        (directory / "strategy.json").write_text(json.dumps({**manifest, "name": "renamed"}), encoding="utf-8")
        with self.assertRaisesRegex(strategy_registry.RegistryError, "deployment_manifest_changed"):
            strategy_registry.resolve_deployment(config)

    def test_a_strategy_failing_the_restart_check_is_not_approved(self):
        self.write(source=STATEFUL)
        with self.assertRaisesRegex(approvals.ApprovalError, "restart_consistency_failed"):
            self.approve(self.profile(slow=5))
        self.assertEqual(approvals.read_records(), [])
        with self.assertRaisesRegex(approvals.ApprovalError, "strategy_not_bot_eligible"):
            approvals.validate_profile(self.profile(version="v2"))


class AcceptanceFixTests(FolderBotTests):
    """Regressions for the 2026-11-17 acceptance (reports/agent-strategy-acceptance-20261117)."""

    def test_editing_an_approved_folder_never_breaks_other_approvals(self):  # D1
        from test_step2_deployment import profile as donchian_profile

        self.write()
        donchian, _ = self.approve(donchian_profile())
        folder, _ = self.approve(self.profile())
        directory = self.temp / "strategies" / SID
        edits = {
            "version": lambda: self.write(version="v2"),
            "float literal": lambda: self.write(source=SOURCE.replace('Decimal("0")', "0.0")),
            "broken json": lambda: (directory / "strategy.json").write_text("{", encoding="utf-8"),
            "narrower range": lambda: self.write(parameters=[{"name": "fast", "min": 2, "max": 3, "default": 2},
                                                             {"name": "slow", "min": 3, "max": 500, "default": 50}]),
            # Same version, renamed parameter (recheck O-B): a RegistryError, not a KeyError.
            "renamed parameter": lambda: self.write(parameters=[{"name": "quick", "min": 2, "max": 200, "default": 20},
                                                                {"name": "slow", "min": 3, "max": 500, "default": 50}],
                                                    constraints=[["quick", "<", "slow"]]),
        }
        donchian_config = local_sim_replay.worker_config(donchian, research_catalog.SYNTHETIC_CONTRACT)
        folder_config = local_sim_replay.worker_config(folder, research_catalog.SYNTHETIC_CONTRACT)
        for name, edit in edits.items():
            with self.subTest(name):
                self.write()
                edit()
                self.assertEqual(len(approvals.read_records()), 2)
                strategy_registry.resolve_deployment(donchian_config)
                with self.assertRaises(strategy_registry.RegistryError):
                    strategy_registry.resolve_deployment(folder_config)
        import shutil
        shutil.rmtree(directory)
        approvals.revoke(approval_id=folder["record_id"], confirm=yes)
        self.assertEqual([r["action"] for r in approvals.read_records()], ["approve", "approve", "revoke"])
        strategy_registry.resolve_deployment(donchian_config)

    def test_default_ready_is_refused_for_a_bot(self):  # D2
        source = SOURCE.replace("""    @property
    def ready(self) -> bool:
        return len(self.closes) == self.closes.maxlen

""", "")
        self.assertNotIn("def ready", source)
        self.write(source=source)
        report = research_catalog.execute_check({"strategy_id": SID, "parameters": {"fast": 2, "slow": 4}},
                                                research_catalog.provenance(research_catalog.DATASET_ID, SID))
        self.assertTrue(report["ok"])
        self.assertFalse(report["bot_eligible"])
        self.assertIn("ready", report["bot_reason"])
        with self.assertRaisesRegex(approvals.ApprovalError, "restart_consistency_failed"):
            self.approve(self.profile())

    def test_restart_check_compares_every_bar_and_catches_on_bar_state(self):  # O1
        self.write()
        report = research_catalog.execute_check({"strategy_id": SID},
                                                research_catalog.provenance(research_catalog.DATASET_ID, SID))
        self.assertTrue(report["exhaustive"])
        self.assertEqual(report["decisions_checked"], report["restart_points"])
        held = SOURCE.replace("        self.quantity = quantity\n",
                              "        self.quantity = quantity\n        self.held = 3\n        self.side = None\n").replace(
            """        if fast > slow:
            return self.quantity
        if fast < slow:
            return -self.quantity
        return None""", """        want = self.quantity if fast > slow else -self.quantity
        self.held += 1
        if want != self.side and self.held >= 3:
            self.side, self.held = want, 0
        return self.side""")
        self.write(source=held)
        report = research_catalog.execute_check({"strategy_id": SID, "parameters": {"fast": 3, "slow": 10}},
                                                research_catalog.provenance(research_catalog.DATASET_ID, SID))
        self.assertTrue(report["ok"], report)
        self.assertFalse(report["bot_eligible"])

    def test_a_slow_restart_check_reports_how_far_it_got(self):  # recheck O-A
        self.write()
        with patch.object(strategy_folder, "CHECK_RESTART_SECONDS", -1):
            report = research_catalog.execute_check({"strategy_id": SID},
                                                    research_catalog.provenance(research_catalog.DATASET_ID, SID))
        self.assertTrue(report["ok"])
        self.assertFalse(report["bot_eligible"] or report["exhaustive"])
        self.assertIn("只比對了 0／", report["bot_reason"])

    def test_contract_details_from_the_acceptance(self):  # O5, O6, O7
        self.write(source=SOURCE.replace("        closes = list(self.closes)", "        print(1)\n        closes = list(self.closes)"))
        with self.assertRaisesRegex(ValueError, "print is not allowed"):
            research_catalog.strategy_spec(SID)
        allowed = ("from __future__ import annotations\nfrom collections.abc import Sequence\n"
                   "from dataclasses import dataclass\nfrom catos import research\n" + SOURCE
                   + "\n\n@dataclass\nclass Window:\n    size: int\n")
        self.write(source=allowed)
        report = research_catalog.execute_check({"strategy_id": SID},
                                                research_catalog.provenance(research_catalog.DATASET_ID, SID))
        self.assertTrue(report["ok"] and report["bot_eligible"], report)
        import sys
        self.assertFalse(any(name.startswith("catos_strategy_") for name in sys.modules))

    def test_single_trial_search_has_no_history_dsr(self):  # O3
        self.write()
        optimization = {"backtest": self.request(warmup=4), "n_trials": 1, "seed": 1,
                        "search_space": {"fast": {"low": 2, "high": 2, "step": 1}, "slow": {"low": 4, "high": 4, "step": 1}}}
        source = research_catalog.provenance(research_catalog.DATASET_ID, SID)
        payload, _ = research_optimization.execute_optimization(optimization, source, {"configurations": 60})
        self.assertIsNone(payload["overfitting"]["history_trials"])
        self.assertIsNone(payload["overfitting"]["dsr_with_history"])

    def test_edited_folder_reports_resubmission_not_restart(self):  # O8
        directory = self.write()
        source = research_catalog.provenance(research_catalog.DATASET_ID, SID)
        (directory / "strategy.py").write_text(SOURCE + "\n# edited\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "strategy_changed_since_submission"):
            research_catalog.execute_request(self.request(), source)


class FolderReplayTests(Home):
    def test_replay_on_the_bot_matches_the_research_backtest(self):
        import asyncio

        self.write()
        value = FolderBotTests.profile(self)
        artifact, _ = approvals.deployment_identity(value)
        record = approvals.approve(strategy_id=SID, version="v1", sha256=artifact["sha256"], profile=value,
                                   confirm=yes)
        series = bars()
        summary = asyncio.run(local_sim_replay.replay_bars(record=record, contract=research_catalog.SYNTHETIC_CONTRACT,
                                                           bars=series, output_dir=self.temp / "replay"))
        self.assertEqual(summary["status"]["state"], "completed", summary["status"])
        report = replay_consistency.compare_run(self.temp / "replay", series, research_catalog.SYNTHETIC_CONTRACT)
        self.assertTrue(report["passed"], json.dumps(report["checks"], ensure_ascii=False))
        self.assertGreater(report["counts"]["reversal_decisions"], 0)
        # D3: once the folder changes, this replay is not compared against another version.
        (self.temp / "strategies" / SID / "strategy.py").write_text(SOURCE + "\n# edited\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "strategy_source_changed_since_replay"):
            replay_consistency.compare_run(self.temp / "replay", series, research_catalog.SYNTHETIC_CONTRACT)


if __name__ == "__main__":
    unittest.main()
