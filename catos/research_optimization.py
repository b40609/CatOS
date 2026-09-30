"""Trusted Optuna adapter for the registered synthetic SMA research fixture."""

from dataclasses import asdict
from html import escape
import json

from catos.data_io import load_candles_csv
from catos.optimization import IntRange, optimize
from catos.research_catalog import (
    DATA_PATH, MAX_BARS, json_text, load_registered_strategy, provenance,
    validate_optimization_request,
)


def execute_optimization(request, expected_source):
    snapshot, config, quantity = validate_optimization_request(request)
    # Keep the strategy import in the calculation process and share the same
    # approved-artifact gate as backtests.
    RegisteredSMA = load_registered_strategy(expected_source)
    bars = load_candles_csv(DATA_PATH, config=config)
    if len(bars) > MAX_BARS:
        raise ValueError("dataset_bar_limit")
    period = snapshot["search_space"]["period"]
    result = optimize(
        strategy_factory=lambda params: RegisteredSMA(params["period"], quantity),
        search_space={"period": IntRange(**period)}, candles=bars, config=config,
        score=lambda performance: performance.return_pct,
        score_name="return_pct", direction="maximize",
        n_trials=snapshot["n_trials"], seed=snapshot["seed"],
        warmup_bars=snapshot["backtest"]["warmup_bars"],
    )
    if provenance() != expected_source:
        raise ValueError("source_changed_during_run")
    trials = [{"number": trial.number, "state": trial.state,
               "params": dict(trial.params), "score_decimal": trial.score_decimal,
               "performance": asdict(trial.performance) if trial.performance else None,
               "error": trial.error} for trial in result.trials]
    payload = {"kind": "optimization", "request": snapshot,
               "provenance": expected_source, "trials": trials,
               "best_trial_number": result.best_trial_number,
               "objective": {"name": result.score_name, "direction": result.direction,
                             "formula": "Decimal performance.return_pct; Float only for Optuna ranking"},
               "seed": result.seed, "optuna_version": result.optuna_version,
               "data_notice": "合成資料的樣本內搜尋；未執行樣本外檢驗，不代表市場績效。"}
    payload = json.loads(json_text(payload))
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            trial["number"], escape(trial["state"]),
            escape(str(trial["params"].get("period", ""))),
            escape(str(trial["score_decimal"] if trial["score_decimal"] is not None else "—"))) for trial in trials
    )
    report = ("<!doctype html><html lang='zh-TW'><meta charset='utf-8'>"
              "<title>catOS Optuna 研究</title><body><h1>Optuna 候選</h1>"
              "<p>合成資料樣本內搜尋；未執行樣本外檢驗。</p>"
              "<table><tr><th>Trial</th><th>狀態</th><th>SMA 週期</th><th>報酬率 %</th></tr>"
              + rows + "</table><pre>" + escape(json_text(payload)) + "</pre></body></html>")
    return payload, report
