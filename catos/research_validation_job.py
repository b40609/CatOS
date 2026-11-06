"""Registered validation adapter over a registered dataset; persistence belongs to ResearchService."""

from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
import platform

import optuna
import packaging

from catos import research_costs, research_overfit
from catos.optimization import IntRange
from catos.research_catalog import (
    DEFAULT_VALIDATION, ENGINE_FILES, MAX_BARS, MAX_VALIDATION_BAR_EVALUATIONS,
    MAX_VALIDATION_CANDIDATES, MAX_VALIDATION_CURVE_POINTS, MAX_VALIDATION_LOOKBACK_BARS,
    MAX_VALIDATION_RUNS, MAX_VALIDATION_WINDOWS, ROOT, check_search_grid, costs_for, costs_html,
    decimal_string,
    drawdown_pcts, json_text, load_dataset_bars, provenance, registered_factory,
    require_search_names, resolve_dataset, sample_curve_indices, strategy_spec, validate_request,
)
from catos.research_datasets import SOURCE as FETCHED_SOURCE, rel_path
from catos.research_regimes import REGIMES, RegimeRule, regime_walk_forward, regimes_json
from catos.research_validation import WalkForwardPlan

# v2 keeps every v1 figure but not the per-bar detail that grows with the data
# (14.1 MB on the fetched 8,640-bar dataset in v1): per-bar labels become
# per-regime bar counts, per-bar interval attribution is left to the per-regime
# summaries, OOS equity curves are sampled above their share of
# MAX_VALIDATION_CURVE_POINTS, and fetched data files are referenced by hash.
SCHEMA = "catos.research.validation-result.v2"
OMITTED_DETAIL = ("labels", "windows.evaluation.intervals")


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name}: integer in [{low}, {high}] required")
    return value


def validate_validation_request(value):
    if type(value) is not dict or set(value) != set(DEFAULT_VALIDATION):
        raise ValueError("validation: exact registered fields required")
    backtest, config, _, quantity = validate_request(value["backtest"])
    spec = strategy_spec(backtest["strategy_id"])
    space = value["search_space"]
    require_search_names(spec, space)
    # A single-parameter grid keeps the original bare low/high/step field names.
    single = len(spec.parameters) == 1
    axes, count = {}, 1
    for name, low_bound, high_bound in spec.parameters:
        label = "" if single else f"{name}."
        low = _integer(space[name]["low"], f"{label}low", low_bound, high_bound)
        high = _integer(space[name]["high"], f"{label}high", low_bound, high_bound)
        step = _integer(space[name]["step"], f"{label}step", 1, high_bound - low_bound)
        if (high <= low if single else high < low) or (high - low) % step:
            raise ValueError(f"{name}: at least two aligned candidates required" if single
                             else f"{name}: aligned range required")
        axes[name] = IntRange(low, high, step)
        count *= (high - low) // step + 1
    if count < 2:
        raise ValueError("search_space: at least two candidates required")
    candidates = _integer(value["max_candidates"], "max_candidates", 2, MAX_VALIDATION_CANDIDATES)
    runs = _integer(value["max_runs"], "max_runs", 1, MAX_VALIDATION_RUNS)
    if count > candidates:
        raise ValueError("grid exceeds max_candidates before execution")
    check_search_grid(spec, {name: (axis.low, axis.high) for name, axis in axes.items()},
                      backtest["warmup_bars"])
    plan = value["plan"]
    if type(plan) is not dict or set(plan) != {"train_bars", "test_bars", "windows"}:
        raise ValueError("plan: train_bars, test_bars and windows required")
    train = _integer(plan["train_bars"], "train_bars", 1, MAX_BARS)
    test = _integer(plan["test_bars"], "test_bars", 1, MAX_BARS)
    windows = _integer(plan["windows"], "windows", 1, MAX_VALIDATION_WINDOWS)
    if windows * (count + 1) > runs:
        raise ValueError("walk-forward exceeds max_runs before execution")
    warmup = backtest["warmup_bars"]
    if windows * (count * (warmup + train) + warmup + test) > MAX_VALIDATION_BAR_EVALUATIONS:
        raise ValueError("walk-forward exceeds max_bar_evaluations before execution")
    rule = value["regime_rule"]
    if type(rule) is not dict or set(rule) != {
        "lookback_bars", "trend_efficiency", "high_volatility_bps",
    }:
        raise ValueError("regime_rule: exact explicit fields required")
    lookback = _integer(rule["lookback_bars"], "lookback_bars", 1, MAX_VALIDATION_LOOKBACK_BARS)
    efficiency = decimal_string(rule["trend_efficiency"], "trend_efficiency", positive=True)
    volatility = decimal_string(rule["high_volatility_bps"], "high_volatility_bps", positive=True)
    if efficiency > 1:
        raise ValueError("trend_efficiency: must be <= 1")
    bars, config = load_dataset_bars(backtest["dataset_id"], config)
    if backtest["warmup_bars"] + train + windows * test > len(bars):
        raise ValueError("insufficient candles for the explicit walk-forward plan")
    snapshot = json.loads(json_text(value))
    snapshot["backtest"] = backtest
    return (snapshot, config, quantity, bars, axes,
            WalkForwardPlan(train, test, windows, backtest["warmup_bars"]),
            RegimeRule(lookback, efficiency, volatility))


def _reproduction(expected_source):
    # Fixed, inspected source/data paths only. Never follow request-supplied paths
    # or execute archived code. These materials travel through the existing writer.
    # Fetched market data stays in git-ignored data/okx and is pinned by its
    # manifest hashes, so it is referenced by sha256 instead of embedded.
    dataset = resolve_dataset(expected_source["dataset"]["id"])
    spec = strategy_spec(expected_source["strategy"]["id"])
    manifest = spec.manifest.relative_to(ROOT).as_posix()
    data_files = tuple(path for path, _ in dataset.files)
    referenced = data_files if dataset.source == FETCHED_SOURCE else ()
    names = tuple(dict.fromkeys((*ENGINE_FILES, *spec.files, manifest,
                                 *(path for path in data_files if path not in referenced))))
    files = []
    for name in names:
        content = (ROOT / name).read_bytes()
        files.append({"path": name, "sha256": sha256(content).hexdigest(),
                      "content_utf8": content.decode("utf-8")})
    references = [{"path": name, "sha256": sha256((ROOT / name).read_bytes()).hexdigest()}
                  for name in referenced]
    hashes = {item["path"]: item["sha256"] for item in (*files, *references)}
    for names, expected in ((ENGINE_FILES, expected_source["engine_sha256"]),
                            (spec.files, expected_source["strategy"]["sha256"])):
        actual = sha256(json_text([(name, hashes[name]) for name in names]).encode("utf-8")).hexdigest()
        if actual != expected:
            raise ValueError("source_changed_during_archive")
    if (any(hashes[path] != sha for path, sha in dataset.files)
            or hashes[rel_path(dataset.candles_path)] != expected_source["dataset"]["sha256"]
            or hashes[manifest] != expected_source["strategy"]["artifact_manifest"]["sha256"]):
        raise ValueError("source_changed_during_archive")
    notice = "研究來源快照；不是可自動執行的套件、環境鎖檔或 OS 安全沙箱。"
    if references:
        notice += ("已抓取的資料集檔案只記路徑與 sha256、不內嵌內容；"
                   "重現時以同一份 manifest 核對，或依 README 以 --end-ms 重抓同一區間。")
    return {"python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "optuna_version": optuna.__version__, "packaging_version": packaging.__version__,
            "algorithm": "exhaustive_grid; deterministic; no random seed",
            "files": files, "referenced_files": references, "notice": notice}


def _sampled_curve(result, limit):
    """Kept indices for one OOS equity curve, or None when it already fits the limit."""
    if len(result.equity_curve) <= limit:
        return None
    keep = sample_curve_indices(drawdown_pcts(result.equity_curve, result.config.initial_balance),
                                limit - 1)
    # Each window starts flat at the initial balance; keep that anchor point too.
    return keep if keep[0] == 0 else [0, *keep]


def compact_result(result):
    """v2 result: regimes_json minus per-bar detail; every reported figure is unchanged.

    Per-bar labels and interval attributions are recomputable from the bound
    inputs (input_sha256 covers candles, config and rule).
    """
    limit = MAX_VALIDATION_CURVE_POINTS // len(result.validation.windows)
    windows, sampling = [], {}
    for window in result.validation.windows:
        oos = window.out_of_sample
        keep = _sampled_curve(oos, limit) if oos is not None else None
        if keep is not None:
            sampling[window.number] = {"total_points": len(oos.equity_curve),
                                       "returned_points": len(keep),
                                       "method": "bucket_deepest_drawdown_keep_first"}
            oos = replace(oos, equity_curve=tuple(oos.equity_curve[index] for index in keep))
        windows.append(replace(window, out_of_sample=oos))
    slim = replace(result, labels=(), validation=replace(result.validation, windows=tuple(windows)),
                   windows=tuple(replace(row, evaluation=replace(row.evaluation, intervals=()))
                                 if row.evaluation is not None else row for row in result.windows))
    value = json.loads(regimes_json(slim))
    del value["labels"]
    for row in value["windows"]:
        if row["evaluation"] is not None:
            del row["evaluation"]["intervals"]
    for row in value["validation"]["windows"]:
        if row["number"] in sampling:
            row["curve_sampling"] = sampling[row["number"]]
    counts = Counter(label.regime for label in result.labels)
    value["label_counts"] = [{"regime": name, "bar_count": counts[name]} for name in REGIMES]
    value["omitted_detail"] = list(OMITTED_DETAIL)
    return value


def _utc(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _table(headers, rows):
    head = "".join(f"<th>{escape(str(item))}</th>" for item in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(item))}</td>" for item in row) + "</tr>"
                   for row in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def _report(payload):
    """A read-only summary of the archived JSON; result.json stays the full record."""
    request, result = payload["request"], payload["result"]
    rows, regimes = [], []
    for window, diagnostic in zip(result["validation"]["windows"], result["windows"]):
        training, oos = window["training"], window["out_of_sample"]
        chosen = (None if training["selected_trial_number"] is None
                  else training["trials"][training["selected_trial_number"]])
        performance = oos["performance"] if oos else None
        rows.append((
            window["number"], window["status"],
            f"{_utc(window['train_start_ms'])} ~ {_utc(window['train_end_ms'])}",
            f"{_utc(window['test_start_ms'])} ~ {_utc(window['test_end_ms'])}",
            ", ".join(f"{name}={value}" for name, value in chosen["params"]) if chosen else "—",
            chosen["score"] if chosen else "—",
            *((performance[key] for key in ("return_pct", "net_pnl", "max_drawdown_pct", "fees",
                                            "funding_paid", "trade_count"))
              if performance else ("—",) * 6),
            window["error"] or "",
        ))
        if diagnostic["evaluation"] is not None:
            regimes.extend((window["number"], row["regime"], row["bar_count"], row["fill_count"],
                            row["net_pnl"], row["fees"], row["funding_paid"])
                           for row in diagnostic["evaluation"]["summaries"] if row["bar_count"])
    backtest = request["backtest"]
    settings = (
        ("資料集", backtest["dataset_id"]), ("策略", backtest["strategy_id"]),
        ("搜尋範圍", json_text(request["search_space"])),
        ("計畫", json_text(request["plan"])), ("分類規則", json_text(request["regime_rule"])),
        ("本金／手續費率／滑價 bps",
         f"{backtest['initial_balance']} / {backtest['fee_rate']} / {backtest['slippage_bps']}"),
        ("預熱 K 線", backtest["warmup_bars"]), ("evaluation_complete", payload["evaluation_complete"]),
    )
    return ("<!doctype html><html lang='zh-TW'><meta charset='utf-8'>"
            "<title>catOS 研究驗證</title><body><h1>catOS 滾動驗證（walk-forward）</h1><p>"
            + escape(payload["data_notice"]) + "</p>"
            + _table(("項目", "設定"), settings)
            + "<h2>各視窗（時間為 UTC；績效為各窗獨立的 OOS 回測）</h2>"
            + _table(("視窗", "狀態", "訓練區間", "OOS 區間", "選定參數", "訓練評分 return_pct",
                      "OOS return_pct", "OOS 淨損益", "OOS 最大回撤 %", "手續費", "資金費",
                      "成交筆數", "錯誤"), rows)
            + "<h2>分環境歸屬（只列有樣本的環境）</h2>"
            + _table(("視窗", "環境", "K 線數", "成交筆數", "淨損益", "手續費", "資金費"), regimes)
            + _costs_report(payload["costs"])
            + _edges_report(payload["selection_edges"])
            + "<p>完整結果見同一任務的 result.json；逐根環境標籤與逐根歸屬不保存，"
              "可由綁定的資料集與分類規則重算。</p></body></html>")


COST_COLUMNS = ("price_pnl", "fees", "slippage", "funding_paid", "net_pnl", "fill_count",
                "break_even_bps_per_side")


def _costs_report(costs):
    rows = [(row["number"], *(row["costs"][key] for key in COST_COLUMNS),
             row["costs"]["buy_hold"]["pnl"],
             (row["costs"]["funding_scenario"] or {}).get("net_pnl_with_assumption", "—"))
            for row in costs["windows"]]
    html = ("<h2>各視窗成本拆解（價格損益以成交 K 線開盤價計、成本前）</h2>"
            + _table(("視窗", "價格損益", "手續費", "滑價", "資金費", "淨損益", "成交筆數",
                      "每邊兩平 bps", "買進持有（成本前）", "淨損益（含假設資金費）"), rows))
    total = costs["total"]
    if total is not None:
        html += costs_html([(label, total.get(key)) for key, label in (
            ("price_pnl", "價格損益"), ("fees", "手續費"), ("slippage", "滑價"),
            ("funding_paid", "資金費（實際）"), ("net_pnl", "淨損益"), ("traded_notional", "成交名目"),
            ("fill_count", "成交筆數"), ("cost_bps_per_side", "每邊成本 bps"),
            ("break_even_bps_per_side", "每邊兩平成本 bps"), ("buy_hold_pnl", "買進持有（各窗合計、成本前）"),
            ("assumed_funding_paid", "假設資金費（未涵蓋期間）"))], "各視窗合計（各窗獨立，不是連續投資組合）")
    return html


def _edges_report(edges):
    rows = [(name, counts["at_low"], counts["at_high"]) for name, counts in edges["params"].items()]
    return ("<h2>選參落在搜尋範圍邊界</h2><p>" + escape(
        f"{edges['windows_at_edge']} / {edges['windows_with_selection']} 個有選定參數的視窗落在邊界。{edges['notice']}")
        + "</p>" + _table(("參數", "選在下限的視窗數", "選在上限的視窗數"), rows))


def _window_costs(result, bars, quantity, dataset):
    """Exact attribution of every completed OOS window, before curves are sampled."""
    windows = []
    for window in result.validation.windows:
        if window.out_of_sample is not None:
            windows.append((window.number, costs_for(window.out_of_sample, bars, quantity, dataset)))
    # JSON round-trip: Decimal becomes the same strings as every other payload figure.
    return json.loads(json_text({
        "windows": [{"number": number, "costs": asdict(costs)} for number, costs in windows],
        "total": research_costs.total([costs for _, costs in windows]),
        "funding_coverage": dataset.funding_summary()}))


def execute_validation(request, expected_source):
    snapshot, config, quantity, bars, space, plan, rule = validate_validation_request(request)
    strategy_id = snapshot["backtest"]["strategy_id"]
    build = registered_factory(expected_source, strategy_id, quantity)
    reproduction = _reproduction(expected_source)
    result = regime_walk_forward(
        strategy_factory=build, search_space=space, candles=bars, config=config, rule=rule,
        score=lambda performance: performance.return_pct, score_name="return_pct",
        plan=plan, max_candidates=snapshot["max_candidates"], max_runs=snapshot["max_runs"],
        direction="maximize",
    )
    dataset = resolve_dataset(snapshot["backtest"]["dataset_id"])
    costs = _window_costs(result, bars, quantity, dataset)
    if provenance(dataset.dataset_id, strategy_id) != expected_source:
        raise ValueError("source_changed_during_run")
    payload = {
        "schema": SCHEMA, "kind": "validation", "request": snapshot,
        "provenance": expected_source, "reproduction": reproduction,
        "objective": {"name": "return_pct", "direction": "maximize",
                      "formula": "Decimal performance.return_pct; no float conversion"},
        "result": compact_result(result),
        "costs": costs,
        "evaluation_complete": result.validation.complete,
        "data_notice": f"各 OOS 視窗獨立，不是連續投資組合或部署通過門檻。分類參數僅供示範。{dataset.notice}",
    }
    payload["selection_edges"] = research_overfit.edge_selections(
        [(row["number"], None if row["training"]["selected_trial_number"] is None
          else row["training"]["trials"][row["training"]["selected_trial_number"]]["params"])
         for row in payload["result"]["validation"]["windows"]],
        snapshot["search_space"])
    return payload, _report(payload)
