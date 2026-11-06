"""Trusted Optuna adapter for the registered research strategies."""

from dataclasses import asdict
from html import escape
import json

from catos import research, research_overfit
from catos.optimization import IntRange, optimize
from catos.research_catalog import (
    cost_rows, costs_for, costs_html, json_text, load_dataset_bars, provenance, registered_factory,
    resolve_dataset, validate_optimization_request,
)


def overfit_rows(report):
    pbo = report["pbo"]
    return [
        ("不同參數組數 N（只計本次）", report["distinct_trials"]), ("評估 K 線數", report["bars"]),
        ("最佳參數", ", ".join(f"{name}={value}" for name, value in report["best"]["params"])),
        ("最佳 Sharpe（年化）", report["best"]["sharpe_annualized"]),
        ("N 組純運氣可期待的最大 Sharpe（年化）", report["expected_max_sharpe_annualized"]),
        ("PSR（真實 Sharpe > 0 的機率）", report["psr_vs_zero"]), ("DSR", report["dsr"]),
        ("PBO（CSCV）", "樣本不足" if pbo is None else f"{pbo['pbo']}（{pbo['blocks']} 區塊、{pbo['splits']} 種切法）"),
        ("判讀", report["verdict"]), ("說明", report["notice"]),
    ]


def execute_optimization(request, expected_source):
    snapshot, config, quantity = validate_optimization_request(request)
    strategy_id = snapshot["backtest"]["strategy_id"]
    # Keep the strategy import in the calculation process and share the same
    # approved-artifact gate as backtests.
    build = registered_factory(expected_source, strategy_id, quantity)
    dataset = resolve_dataset(snapshot["backtest"]["dataset_id"])
    bars, config = load_dataset_bars(dataset.dataset_id, config)
    candidates = {}  # first COMPLETE result per distinct parameter set, in trial order
    result = optimize(
        on_result=lambda params, run: candidates.setdefault(params, run),
        strategy_factory=build,
        search_space={name: IntRange(**item) for name, item in snapshot["search_space"].items()},
        candles=bars, config=config,
        score=lambda performance: performance.return_pct,
        score_name="return_pct", direction="maximize",
        n_trials=snapshot["n_trials"], seed=snapshot["seed"],
        warmup_bars=snapshot["backtest"]["warmup_bars"],
    )
    best_costs = None
    if result.best_trial_number is not None:
        # Trials keep only Performance; one deterministic re-run of the best
        # parameters gives the exact attribution (same bars, config and warm-up).
        best = next(trial for trial in result.trials if trial.number == result.best_trial_number)
        rerun = research.backtest(strategy=lambda: build(dict(best.params)), candles=bars, config=config,
                                  warmup_bars=snapshot["backtest"]["warmup_bars"])
        if rerun.performance != best.performance:
            raise ValueError("best_trial_rerun_mismatch")
        best_costs = costs_for(rerun, bars, quantity, dataset)
    overfitting = None
    if result.best_trial_number is not None:
        overfitting = research_overfit.search_report(candidates, best.params, dataset.timeframe_ms)
    if provenance(dataset.dataset_id, strategy_id) != expected_source:
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
               "best_costs": asdict(best_costs) if best_costs else None,
               "overfitting": overfitting,
               "funding_coverage": dataset.funding_summary(),
               "data_notice": f"樣本內搜尋，未執行樣本外檢驗，不代表市場績效。{dataset.notice}"}
    payload = json.loads(json_text(payload))
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            trial["number"], escape(trial["state"]),
            escape(", ".join(f"{name}={value}" for name, value in trial["params"].items())),
            escape(str(trial["score_decimal"] if trial["score_decimal"] is not None else "—"))) for trial in trials
    )
    report = ("<!doctype html><html lang='zh-TW'><meta charset='utf-8'>"
              "<title>catOS Optuna 研究</title><body><h1>Optuna 候選</h1>"
              "<p>" + escape(f"{strategy_id}：{payload['data_notice']}") + "</p>"
              "<table><tr><th>Trial</th><th>狀態</th><th>參數</th><th>報酬率 %</th></tr>"
              + rows + "</table>"
              + (costs_html(cost_rows(payload["best_costs"]), "最佳 Trial 成本拆解") if best_costs else "")
              + (costs_html(overfit_rows(payload["overfitting"]), "過擬合檢查（DSR／PBO）") if overfitting else "")
              + "<pre>" + escape(json_text(payload)) + "</pre></body></html>")
    return payload, report
