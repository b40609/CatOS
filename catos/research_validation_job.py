"""Registered validation adapter over a registered dataset; persistence belongs to ResearchService."""

from hashlib import sha256
from html import escape
import json
import platform

import optuna
import packaging

from catos.optimization import IntRange
from catos.research_catalog import (
    DATASET_ID, DEFAULT_VALIDATION, ENGINE_FILES, MAX_BARS, MAX_VALIDATION_CANDIDATES,
    MAX_VALIDATION_RUNS, MAX_VALIDATION_WINDOWS, ROOT, STRATEGY_FILES,
    STRATEGY_MANIFEST, decimal_string, json_text, load_dataset_bars, load_registered_strategy,
    provenance, resolve_dataset, validate_request,
)
from catos.research_datasets import rel_path
from catos.research_regimes import RegimeRule, regime_walk_forward, regimes_json
from catos.research_validation import WalkForwardPlan

SCHEMA = "catos.research.validation-result.v1"


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name}: integer in [{low}, {high}] required")
    return value


def validate_validation_request(value):
    if type(value) is not dict or set(value) != set(DEFAULT_VALIDATION):
        raise ValueError("validation: exact registered fields required")
    backtest, config, _, quantity = validate_request(value["backtest"])
    # Per-bar regime labels, per-window curves and the HTML report exceed the 2 MB
    # output cap on a fetched dataset (13.7 MB measured on 8,640 bars), so reject
    # at submission instead of failing after the computation.
    if backtest["dataset_id"] != DATASET_ID:
        raise ValueError("validation_supports_synthetic_dataset_only")
    space = value["search_space"]
    if type(space) is not dict or set(space) != {"period"}:
        raise ValueError("search_space: only registered period range is supported")
    period = space["period"]
    if type(period) is not dict or set(period) != {"low", "high", "step"}:
        raise ValueError("period: low, high and step required")
    low = _integer(period["low"], "low", 2, 32)
    high = _integer(period["high"], "high", 2, 32)
    step = _integer(period["step"], "step", 1, 30)
    if high <= low or (high - low) % step:
        raise ValueError("period: at least two aligned candidates required")
    count = (high - low) // step + 1
    candidates = _integer(value["max_candidates"], "max_candidates", 2, MAX_VALIDATION_CANDIDATES)
    runs = _integer(value["max_runs"], "max_runs", 1, MAX_VALIDATION_RUNS)
    if count > candidates:
        raise ValueError("grid exceeds max_candidates before execution")
    if backtest["warmup_bars"] < high:
        raise ValueError("warmup_bars: must cover highest searched period")
    plan = value["plan"]
    if type(plan) is not dict or set(plan) != {"train_bars", "test_bars", "windows"}:
        raise ValueError("plan: train_bars, test_bars and windows required")
    train = _integer(plan["train_bars"], "train_bars", 1, MAX_BARS)
    test = _integer(plan["test_bars"], "test_bars", 1, MAX_BARS)
    windows = _integer(plan["windows"], "windows", 1, MAX_VALIDATION_WINDOWS)
    if windows * (count + 1) > runs:
        raise ValueError("walk-forward exceeds max_runs before execution")
    rule = value["regime_rule"]
    if type(rule) is not dict or set(rule) != {
        "lookback_bars", "trend_efficiency", "high_volatility_bps",
    }:
        raise ValueError("regime_rule: exact explicit fields required")
    lookback = _integer(rule["lookback_bars"], "lookback_bars", 1, MAX_BARS - 1)
    efficiency = decimal_string(rule["trend_efficiency"], "trend_efficiency", positive=True)
    volatility = decimal_string(rule["high_volatility_bps"], "high_volatility_bps", positive=True)
    if efficiency > 1:
        raise ValueError("trend_efficiency: must be <= 1")
    bars, config = load_dataset_bars(backtest["dataset_id"], config)
    if backtest["warmup_bars"] + train + windows * test > len(bars):
        raise ValueError("insufficient candles for the explicit walk-forward plan")
    snapshot = json.loads(json_text(value))
    snapshot["backtest"] = backtest
    return (snapshot, config, quantity, bars, IntRange(low, high, step),
            WalkForwardPlan(train, test, windows, backtest["warmup_bars"]),
            RegimeRule(lookback, efficiency, volatility))


def _reproduction(expected_source):
    # Fixed, inspected source/data paths only. Never follow request-supplied paths
    # or execute archived code. These materials travel through the existing writer.
    dataset = resolve_dataset(expected_source["dataset"]["id"])
    names = tuple(dict.fromkeys((*ENGINE_FILES, *STRATEGY_FILES,
                                 STRATEGY_MANIFEST.relative_to(ROOT).as_posix(),
                                 *(path for path, _ in dataset.files))))
    files = []
    for name in names:
        content = (ROOT / name).read_bytes()
        files.append({"path": name, "sha256": sha256(content).hexdigest(),
                      "content_utf8": content.decode("utf-8")})
    hashes = {item["path"]: item["sha256"] for item in files}
    for names, expected in ((ENGINE_FILES, expected_source["engine_sha256"]),
                            (STRATEGY_FILES, expected_source["strategy"]["sha256"])):
        actual = sha256(json_text([(name, hashes[name]) for name in names]).encode("utf-8")).hexdigest()
        if actual != expected:
            raise ValueError("source_changed_during_archive")
    if (any(hashes[path] != sha for path, sha in dataset.files)
            or hashes[rel_path(dataset.candles_path)] != expected_source["dataset"]["sha256"]
            or hashes[STRATEGY_MANIFEST.relative_to(ROOT).as_posix()]
            != expected_source["strategy"]["artifact_manifest"]["sha256"]):
        raise ValueError("source_changed_during_archive")
    return {"python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "optuna_version": optuna.__version__, "packaging_version": packaging.__version__,
            "algorithm": "exhaustive_grid; deterministic; no random seed",
            "files": files,
            "notice": "研究來源快照；不是可自動執行的套件、環境鎖檔或 OS 安全沙箱。"}


def execute_validation(request, expected_source):
    snapshot, config, quantity, bars, space, plan, rule = validate_validation_request(request)
    RegisteredSMA = load_registered_strategy(expected_source)
    reproduction = _reproduction(expected_source)
    result = regime_walk_forward(
        strategy_factory=lambda params: RegisteredSMA(params["period"], quantity),
        search_space={"period": space}, candles=bars, config=config, rule=rule,
        score=lambda performance: performance.return_pct, score_name="return_pct",
        plan=plan, max_candidates=snapshot["max_candidates"], max_runs=snapshot["max_runs"],
        direction="maximize",
    )
    dataset = resolve_dataset(snapshot["backtest"]["dataset_id"])
    if provenance(dataset.dataset_id) != expected_source:
        raise ValueError("source_changed_during_run")
    payload = {
        "schema": SCHEMA, "kind": "validation", "request": snapshot,
        "provenance": expected_source, "reproduction": reproduction,
        "objective": {"name": "return_pct", "direction": "maximize",
                      "formula": "Decimal performance.return_pct; no float conversion"},
        "result": json.loads(regimes_json(result)),
        "evaluation_complete": result.validation.complete,
        "data_notice": f"各 OOS 視窗獨立，不是連續投資組合或部署通過門檻。分類參數僅供示範。{dataset.notice}",
    }
    # A read-only downloadable report, not a new interactive frontend.
    report = ("<!doctype html><html lang='zh-TW'><meta charset='utf-8'>"
              "<title>catOS 研究驗證</title><body><p>" + escape(payload["data_notice"])
              + "</p><pre>" + escape(json_text({key: value for key, value in payload.items()
                                              if key != "reproduction"})) + "</pre></body></html>")
    return payload, report
