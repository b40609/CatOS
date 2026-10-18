"""Reproducible offline DCM matrix. No network, SQLite, MCP or live adapter."""

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import html
import json
from pathlib import Path

from catos.data_io import load_candles_csv
from catos.dcm import CANDIDATES, DAY, DCMParams, DCMStrategy, D
from catos.dcm_public_data import digest, write_json
from catos.research import BacktestConfig, ContractSpec, FundingEvent, _CONTEXT, backtest

VERSION = "dcm-study-v1"
WARMUP_DAYS = 22
BASE_COST = {"fee_rate": D("0.0005"), "slippage_bps": D("2")}
COSTS = {"base": BASE_COST, "double-cost": {key: value * 2 for key, value in BASE_COST.items()}}


def serial(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: serial(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [serial(item) for item in value]
    return value


def utc(stamp):
    return datetime.fromtimestamp(stamp // 1000, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def round_trips(result):
    """Summarize the core fills; reject scaling/reversal rather than re-account.

    Settlement at entry time belongs to the old flat position; settlement at
    exit time belongs to the held position. Core cash flows are authoritative.
    """
    trips, entry = [], None
    for fill in result.trades:
        if entry is None:
            if fill.position_after == 0:
                raise ValueError("unexpected flat fill in DCM round-trip summary")
            entry = fill
        else:
            if fill.position_after != 0 or fill.quantity != -entry.quantity:
                raise ValueError("DCM summary does not support scaling or reversal")
            funding = sum((item.amount_paid for item in result.funding
                           if entry.time_ms < item.time_ms <= fill.time_ms), D(0))
            net = fill.realized_pnl - entry.fee - fill.fee - funding
            trips.append({"entry_ms": entry.time_ms, "exit_ms": fill.time_ms,
                          "direction": "long" if entry.quantity > 0 else "short",
                          "gross_pnl": fill.realized_pnl, "fees": entry.fee + fill.fee,
                          "funding_paid": funding, "net_pnl": net,
                          "hold_ms": fill.time_ms - entry.time_ms})
            entry = None
    return trips, entry


def summarize(result):
    trips, open_entry = round_trips(result)
    nets = [item["net_pnl"] for item in trips]
    closed = sum(nets, D(0))
    return {"performance": asdict(result.performance), "completed_trades": len(trips),
            "wins": sum(net > 0 for net in nets),
            "expectancy_usdt": closed / len(trips) if trips else None,
            "closed_net_pnl": closed, "open_component_net_pnl": result.performance.net_pnl - closed,
            "open_position": open_entry.position_after if open_entry else D(0),
            "long_trades": sum(item["direction"] == "long" for item in trips),
            "short_trades": sum(item["direction"] == "short" for item in trips),
            "largest_win_share": (max(nets) / sum((net for net in nets if net > 0), D(0))
                                  if any(net > 0 for net in nets) else None),
            "average_hold_hours": (sum((D(item["hold_ms"]) for item in trips), D(0))
                                   / len(trips) / D(3_600_000) if trips else None),
            "pending_intent": asdict(result.pending_intent) if result.pending_intent else None,
            "round_trips": trips,
            "worst_examples": sorted(trips, key=lambda item: item["net_pnl"])[:3]}


def safe_file(root, name):
    if not isinstance(name, str):
        raise ValueError("snapshot path must be a string")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("snapshot file must stay inside the explicit snapshot directory")
    return path


def load_snapshot(root):
    root = Path(root).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("version") != "dcm-public-snapshot-v1" or manifest.get("kind") not in {"public-market", "synthetic"}:
        raise ValueError("unsupported snapshot contract")
    for name, expected in manifest["files"].items():
        if digest(safe_file(root, name)) != expected:
            raise ValueError("snapshot hash mismatch: " + name)
    start, end = manifest["start_ms"], manifest["end_ms"]
    if type(start) is not int or type(end) is not int or start % DAY or end % DAY or end <= start:
        raise ValueError("snapshot must cover complete UTC days")
    c = manifest["contract"]
    spec = ContractSpec(**{key: D(value) if key != "inst_id" else value for key, value in c.items()})
    if spec.inst_id != manifest["symbol"]:
        raise ValueError("snapshot symbol mismatch")
    funding_path = safe_file(root, manifest["funding_file"])
    if manifest["funding_file"] not in manifest["files"]:
        raise ValueError("unhashed funding file")
    events = tuple(FundingEvent(item["time_ms"], D(item["rate"]), D(item["mark_price"]))
                   for item in json.loads(funding_path.read_text(encoding="utf-8")))
    datasets = {}
    for item in manifest["datasets"]:
        bar, step, name = item["bar"], item["timeframe_ms"], item["file"]
        if bar in datasets or name not in manifest["files"] or type(step) is not int or DAY % step:
            raise ValueError("duplicate or invalid unhashed timeframe")
        cfg = BacktestConfig(spec, step, D("10000"), **BASE_COST, funding_events=events)
        bars = load_candles_csv(safe_file(root, name), config=cfg)
        if bars[0].open_time_ms != start or bars[-1].open_time_ms + step != end:
            raise ValueError("all timeframes must have identical coverage")
        datasets[bar] = (bars, cfg)
    if {cfg.timeframe_ms for _, cfg in datasets.values()} != {900_000, 3_600_000, 14_400_000} or len(datasets) != 3:
        raise ValueError("this study requires exactly 15m,1H,4H")
    return manifest, datasets


def run_one(bars, config, params, start, end, cost):
    step = config.timeframe_ms
    if params.timeframe_ms != step:
        raise ValueError("strategy timeframe differs from data")
    window_start = start - WARMUP_DAYS * DAY
    selected = tuple(bar for bar in bars if window_start <= bar.open_time_ms < end)
    if not selected or selected[0].open_time_ms != window_start or selected[-1].open_time_ms + step != end:
        raise ValueError("insufficient data for common evaluation and warm-up")
    warmup = WARMUP_DAYS * DAY // step
    events = tuple(event for event in config.funding_events if window_start <= event.time_ms <= end)
    cfg = replace(config, **COSTS[cost], funding_events=events)
    instance = DCMStrategy(params)
    result = backtest(strategy=lambda: instance, candles=selected, config=cfg, warmup_bars=warmup)
    if result.evaluation_start_ms != start or result.evaluation_end_ms != end:
        raise ValueError("evaluation window differs from the predeclared boundary")
    return {"parameters": asdict(params), "start_ms": start, "end_ms": end,
            "cost": cost, "summary": summarize(result), "trace": instance.trace,
            "fills": [asdict(fill) for fill in result.trades],
            "funding_payments": [asdict(item) for item in result.funding],
            "equity_curve": [{"time_ms": item.time_ms, "equity": item.equity} for item in result.equity_curve],
            "assumptions": result.assumptions}


def source_hashes():
    root = Path(__file__).resolve().parent.parent
    return {name: digest(root / name) for name in (
        "catos/__init__.py", "catos/dcm.py", "catos/dcm_study.py", "catos/dcm_public_data.py",
        "catos/research.py", "catos/data_io.py")}


def rank_training(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["key"], []).append(row)
    ranking = []
    for key, group in grouped.items():
        successful = [row for row in group if "error" not in row]
        robust = (min((row["summary"]["performance"]["net_pnl"] for row in successful), default=D(0))
                  if len(successful) == 4 else None)
        qualifying = len(successful) == 4 and robust > 0 and all(row["summary"]["completed_trades"] >= 5 for row in successful)
        ranking.append({"key": key, "robust_min_net_pnl": robust, "qualifying": qualifying,
                        "low_sample": any(row["summary"]["completed_trades"] < 5 for row in successful),
                        "failures": len(group) - len(successful)})
    return sorted(ranking, key=lambda row: (row["robust_min_net_pnl"] is not None,
                                          row["robust_min_net_pnl"] or D(0)), reverse=True)


def select_families(ranking):
    """Keep three distinct hypotheses, so equivalent cap variants cannot take
    every holdout slot. The best timeframe/cap per family is selected using
    development/validation ONLY; those choices still count as trial selection.
    """
    selected, seen = [], set()
    for item in ranking:
        family = item["key"].split("-", 1)[0]
        if family not in seen and item["robust_min_net_pnl"] is not None:
            selected.append(item["key"])
            seen.add(family)
        if len(selected) == 3:
            break
    return selected


def render(report):
    escape = lambda value: html.escape(str(value))
    sections = []
    for phase in ("development", "validation", "holdout"):
        rows = [row for row in report["runs"] if row["phase"] == phase]
        table = []
        for row in rows:
            if "error" in row:
                table.append(f"<tr><td>{escape(row['key'])}</td><td colspan='8'>失敗：{escape(row['error'])}</td></tr>")
                continue
            s, p = row["summary"], row["summary"]["performance"]
            values = (row["key"], row["cost"], format(p["net_pnl"], ".4f"), format(p["max_drawdown_pct"], ".3f"),
                      s["completed_trades"], format(s["expectancy_usdt"], ".4f") if s["expectancy_usdt"] is not None else "—",
                      f"{s['long_trades']}/{s['short_trades']}", format(s["open_component_net_pnl"], ".4f"),
                      "低樣本" if s["completed_trades"] < 5 else "探索樣本")
            table.append("<tr>" + "".join(f"<td>{escape(value)}</td>" for value in values) + "</tr>")
        sections.append(f"<h2>{escape(phase)}</h2><div class='scroll'><table><thead><tr>"
                        "<th>候選／週期／限幅</th><th>成本</th><th>淨損益 USDT</th><th>回撤 %</th><th>往返數</th>"
                        "<th>每筆期望 USDT</th><th>多／空</th><th>未平部位貢獻</th><th>樣本</th></tr></thead><tbody>"
                        + "".join(table) + "</tbody></table></div>")
    rank_table = "".join(f"<tr><td>{escape(item['key'])}</td><td>{escape(item['robust_min_net_pnl'])}</td>"
                         f"<td>{'符合探索門檻' if item['qualifying'] else '不足／未通過'}</td></tr>" for item in report["ranking"])
    shortlist = ", ".join(report["shortlist"])
    warnings = "".join(f"<li>{escape(item)}</li>" for item in report["limitations"])
    negative = []
    for row in report["runs"]:
        if row["phase"] == "holdout" and row["cost"] == "base" and "error" not in row:
            for trip in row["summary"]["worst_examples"]:
                negative.append(f"<li>{escape(row['key'])} · {utc(trip['entry_ms'])} → {utc(trip['exit_ms'])} · "
                                f"{trip['direction']} · 淨損益 {format(trip['net_pnl'], '.4f')} USDT</li>")
    label = "合成行為驗證；不可用來推薦市場策略" if report["data_kind"] == "synthetic" else "BTC 公開歷史探索研究；尚未證實可部署優勢"
    return ("<!doctype html><html lang='zh-Hant'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
            "<title>DCM 策略研究</title><style>body{font:15px/1.6 system-ui;margin:24px;color:#dae2eb;background:#111820}"
            "h1{font-size:24px}h2{font-size:19px}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}"
            "td,th{padding:7px 10px;text-align:right;border-bottom:1px solid #304050;white-space:nowrap}"
            "td:first-child,th:first-child{text-align:left}.scroll{overflow:auto}a{color:#84cfff}p,li{max-width:1100px}"
            ".notice{padding:16px;background:#25303a;border-left:4px solid #e4b95b}details{margin:16px 0}</style>"
            f"<h1>DCM 六組策略 × 三個 K 線週期</h1><p class='notice'>{label}</p>"
            f"<p>資料：{utc(report['snapshot_start_ms'])} 至 {utc(report['snapshot_end_ms'])}。"
            f"實際回測 {len(report['runs'])} 次；無參數最佳化。每段從空倉開始，獨立預熱 {WARMUP_DAYS} 日。</p>"
            f"<p>事前選擇規則：取開發／驗證、正常／加倍成本四個結果的最低淨損益排名。"
            f"在這兩段選出三個不同策略家族：{escape(shortlist)}。最後一段只評估這份名單，不能拿其結果改選名單。</p>"
            "<p>探索門檻：四結果均正損益且各至少 5 筆往返；5 筆僅是低樣本警示門檻，沒有統計顯著性或實盤含義。"
            "固定 1 張、起始 10,000 USDT；每邊假設手續費 0.05%、不利滑價 2bps，加倍成本為 0.10%／4bps。"
            "包含資金費。DC／短日均線是成本位置代理，未使用 VWAP 或量能。</p>"
            "<details><summary>規則與固定參數</summary><p>A：順勢突破；B：獨立突破事件後回踩重新站回；"
            "C：順勢回踩 DC 或前日已知 5 日均線；D：非強同向趨勢中，突破後收回反轉至凍結 DC；"
            "E：中性環境邊界收回至 DC；F：前日振幅低於更早 20 日振幅中位數的 0.75 倍，再順勢突破。</p>"
            "<p>UTC 日界；20 日均線單日變化除以 14 日簡單平均 TR，±0.03 定趨勢、0.15 定強同向；"
            "回踩容許 0.1 ATR、失效緩衝 0.2 ATR、收盤追蹤 1.5 ATR；事件 12 小時、持倉最長 48 小時。"
            "A/B/C/F 用結構失效及追蹤；D/E 用結構失效與凍結 DC。都在收盤決策、下一根開盤成交，允許隔夜。</p></details>"
            f"<details><summary>開發／驗證排序（已凍結）</summary><table>{rank_table}</table></details>"
            + "".join(sections) + "<h2>最後評估的不利案例</h2><ul>" + "".join(negative)
            + "</ul><h2>結果適用範圍</h2><ul>" + warnings + "</ul><p>完整成交、資金費、理由、參數及來源 hash："
            "<a href='report.json'>report.json</a>；重跑命令見 <a href='README.md'>README.md</a>。</p></html>")


def study(snapshot, output, progress=print, indicator_source=None):
    snapshot, output = Path(snapshot).resolve(), Path(output).resolve()
    if output.is_relative_to(snapshot) or snapshot.is_relative_to(output):
        raise ValueError("research output and immutable input snapshot must be separate directories")
    manifest, datasets = load_snapshot(snapshot)
    hashes = source_hashes()
    indicator_bytes = Path(indicator_source).read_bytes() if indicator_source is not None else None
    indicator_hash = digest(indicator_source) if indicator_source is not None else None
    formal_start = manifest["start_ms"] + WARMUP_DAYS * DAY
    formal_days = (manifest["end_ms"] - formal_start) // DAY
    if formal_days < 42:
        raise ValueError("at least 42 evaluation days are required")
    segment_days = formal_days // 3
    boundaries = {"development": (formal_start, formal_start + segment_days * DAY),
                  "validation": (formal_start + segment_days * DAY, formal_start + 2 * segment_days * DAY),
                  "holdout": (formal_start + 2 * segment_days * DAY, manifest["end_ms"])}
    output.mkdir(parents=True, exist_ok=False)
    source_root = Path(__file__).resolve().parent.parent
    for name, expected in hashes.items():
        destination = output / "sources" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write((source_root / name).read_bytes())
        if digest(destination) != expected:
            raise ValueError("source changed while saving the reproducible artifact")
    if indicator_bytes is not None:
        with (output / "sources" / "indicator.pine.txt").open("xb") as handle:
            handle.write(indicator_bytes)
        if digest(output / "sources" / "indicator.pine.txt") != indicator_hash:
            raise ValueError("indicator source changed while saving the reproducible artifact")
    trials = {}
    for candidate in CANDIDATES:
        for bar, (_, cfg) in datasets.items():
            for capped in (True, False):
                key = f"{candidate}-{bar}-{'cap' if capped else 'uncapped'}"
                trials[key] = (bar, DCMParams(candidate, cfg.timeframe_ms, capped=capped))
    preregistration = {"version": VERSION, "source_hashes": hashes,
                       "indicator_source_sha256": indicator_hash,
                       "snapshot_manifest_sha256": digest(snapshot / "manifest.json"),
                       "boundaries": boundaries, "parameters": {key: serial(asdict(p)) for key, (_, p) in trials.items()},
                       "costs": serial(COSTS), "max_runs": 150,
                       "selection": "top 3 distinct families by minimum development/validation net PnL over baseline/double costs; choose best training timeframe/cap per family; no holdout selection",
                       "minimum_exploration_sample": 5, "optimization_trials": 0}
    write_json(output / "preregistration.json", preregistration)
    runs = []

    def execute(key, phase, cost):
        bar, params = trials[key]
        bars, cfg = datasets[bar]
        row = {"key": key, "phase": phase, "candidate": params.candidate, "bar": bar, "cost": cost}
        try:
            with localcontext(_CONTEXT):
                row.update(run_one(bars, cfg, params, *boundaries[phase], cost))
        except (ValueError, TypeError, ArithmeticError) as error:
            row["error"] = str(error)
        runs.append(row)
        write_json(output / f"run-{len(runs):03d}.json", serial(row))

    for phase in ("development", "validation"):
        for key in trials:
            for cost in COSTS:
                execute(key, phase, cost)
        progress(f"completed {phase}: {len(runs)} total runs", flush=True)
    with localcontext(_CONTEXT):
        ranking = rank_training(runs)
    shortlist = select_families(ranking)
    selection = {"ranking": serial(ranking), "shortlist": shortlist,
                 "qualifying_count": sum(item["qualifying"] for item in ranking),
                 "selection_run_count": len(runs), "holdout_used_for_selection": False}
    # Persist the selection BEFORE any holdout run. Subsequent outcomes never
    # alter it. A nonqualifying shortlist is only a diagnostic falsification run.
    write_json(output / "selection-before-holdout.json", selection)
    for key in shortlist:
        for cost in COSTS:
            execute(key, "holdout", cost)
    if hashes != source_hashes() or digest(snapshot / "manifest.json") != preregistration["snapshot_manifest_sha256"]:
        raise ValueError("source or input manifest changed during the study")
    if indicator_source is not None and digest(indicator_source) != indicator_hash:
        raise ValueError("indicator source changed during the study")
    # Re-read all file hashes to catch mutation of data beneath a static manifest.
    load_snapshot(snapshot)
    report = {"version": VERSION, "data_kind": manifest["kind"], "symbol": manifest["symbol"],
              "snapshot_start_ms": manifest["start_ms"], "snapshot_end_ms": manifest["end_ms"],
              "preregistration": preregistration, "ranking": ranking, "shortlist": shortlist,
              "qualifying_count": selection["qualifying_count"], "runs": runs,
              "limitations": [
                  "短期間、單一市場、固定部位的探索研究；正回測損益不等於已證實正期望值。",
                  "候選與週期共 36 種，正常／加倍成本各比較；選擇本身有多重試驗偏誤，未計算顯著性或 PBO。",
                  "最後評估資料只使用一次；看過後必須標為已使用，後續需新資料或前向模擬。",
                  manifest.get("funding_mark_model", "synthetic funding"),
                  manifest.get("metadata_model", "synthetic specification"),
                  "手續費／滑價為研究假設，未讀帳戶費率；收盤權益回撤，無盤中路徑、保證金或強平模型。",
                  "C 使用 DC／已完成日均線代理，未重現原稿 VWAP／量能；本輪沒有 VWAP、量能、前日高低點消融或全面參數搜尋。",
                  "各時段獨立空倉開始，無跨時段帳戶拼接；期末不強制平倉，未平貢獻及未成交意圖另列。",
                  "策略未接 HTTP／MCP catalog 或部署；沒有更改前端、DB、風控、帳戶或交易出口。" ]}
    write_json(output / "report.json", serial(report))
    with (output / "report.html").open("x", encoding="utf-8") as handle:
        handle.write(render(report))
    with (output / "README.md").open("x", encoding="utf-8") as handle:
        command = f'python -B -m catos.dcm_study --snapshot "{snapshot}" --output "{output}-replay"'
        if indicator_bytes is not None:
            command += f' --indicator-source "{output / "sources" / "indicator.pine.txt"}"'
        handle.write(f"# DCM reproducible study\n\nData kind: {manifest['kind']}\n\n"
                     "Replay with the archived source, choose a NEW output directory:\n\n"
                     f'```powershell\nSet-Location -LiteralPath "{output / "sources"}"\n{command}\n```\n\n'
                     "No network required for replay. All required Python modules are archived under sources/.\n"
                     "All financial values are Decimal strings. Generated output is not a deployment approval.\n")
    write_json(output / "evidence-manifest.json", {"files": {
        str(path.relative_to(output)).replace("\\", "/"): digest(path)
        for path in sorted(output.rglob("*")) if path.is_file()}})
    progress(f"completed study: {len(runs)} runs, qualifying={selection['qualifying_count']}, output={output}", flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--indicator-source", type=Path)
    args = parser.parse_args()
    study(args.snapshot, args.output, indicator_source=args.indicator_source)


if __name__ == "__main__":
    main()
