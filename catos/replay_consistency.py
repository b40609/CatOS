"""Fill-by-fill comparison of a Bot replay with the research backtest (step 2, decision 5).

The baseline is the same backtest with funding and the margin model turned off
(``funding_events=()``, ``margin=None``), on the same bars, parameters and costs.
Threshold: zero difference. Both sides compute prices, fees and realized PnL with
the same Decimal code (research._Ledger), so any difference is a wiring defect.

Bot side, read-only from the replay ledger: the Worker's target for every
evaluation bar (inputs.result_json), the account view the Supervisor gave the
Worker at every close (inputs.input_json), every risk verdict (intents), and
every fill (execution_fills). The two legs of a reversal are merged per decision
before comparison; their prices must be equal.

Passing proves the deployment path executed the research decisions. It does not
prove the fill model is close to a real exchange, nor that the strategy profits.
"""

import argparse
from dataclasses import asdict, fields, replace
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import sqlite3

from catos import research, research_catalog
from catos.research_catalog import json_text

D = Decimal
NOTICE = ("一致性通過只證明部署路徑執行了和研究相同的決策；不證明成交模型接近真實交易所，"
          "不含資金費、保證金與強平，也不證明策略會獲利。")
ACCOUNT_FIELDS = tuple(f.name for f in fields(research.AccountView))
MAX_LISTED = 20


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def ledger_facts(database):
    """Targets, account views, verdicts and fills from a replay ledger, opened read-only."""
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        inputs = {}
        for row in connection.execute("SELECT seq,input_json,result_json,state FROM inputs ORDER BY seq"):
            if row["state"] != "COMMITTED":
                raise ValueError("ledger_has_uncommitted_input")
            payload = json.loads(row["input_json"])["payload"]
            inputs[row["seq"]] = dict(bar=payload["bar"], account=payload["account"],
                                      target=json.loads(row["result_json"])["target"])
        intents = {row["intent_key"]: dict(row) for row in connection.execute(
            "SELECT intent_key,seq,target,disposition,reason FROM intents ORDER BY seq")}
        fills = []
        for row in connection.execute("""SELECT o.order_key,o.intent_key,o.quantity AS order_quantity,o.payload_json,
                o.state,f.quantity,f.price,f.fee FROM execution_fills f JOIN execution_orders o USING(order_key)
                ORDER BY f.rowid"""):
            intent_key = row["intent_key"]
            leg = "intent"
            if intent_key is None:
                key = json.loads(row["order_key"])
                if type(key) is not dict or key.get("kind") != "reversal_close":
                    raise ValueError("ledger_fill_without_intent")
                intent_key, leg = key["intent_key"], "reversal_close"
            quantity = D(row["quantity"])
            signed = quantity if D(row["order_quantity"]) > 0 else -quantity
            fills.append(dict(seq=intents[intent_key]["seq"], leg=leg, quantity=signed, price=D(row["price"]),
                              fee=D(row["fee"]), reduce_only=json.loads(row["payload_json"])["reduceOnly"]))
        orders = [dict(row) for row in connection.execute(
            "SELECT order_key,intent_key,state,settled FROM execution_orders ORDER BY rowid")]
        return inputs, intents, fills, orders
    finally:
        connection.close()


def fill_rows(fills):
    """Canonical per-leg fill rows; their sha256 is the replay's fill digest."""
    return [[f["seq"], f["leg"], str(f["quantity"]), str(f["price"]), str(f["fee"])] for f in fills]


def _merge(fills, inputs, timeframe_ms, contract, config):
    """Bot fills merged per decision, with realized PnL from replaying each leg."""
    merged = []
    with localcontext(research._CONTEXT):
        # Zero slippage and fee: each leg's realized PnL uses its actual fill price.
        ledger = research._Ledger(replace(config, slippage_bps=D("0"), fee_rate=D("0")))
        for fill in fills:
            bar = inputs[fill["seq"]]["bar"]
            time_ms = bar["open_time_ms"] + timeframe_ms
            price = fill["price"]
            target = ledger.position + fill["quantity"]
            delta, _, _, realized, average = ledger.execution(target, research.Candle(0, price, price, price, price))
            ledger.average_entry, ledger.position = average, target
            ledger.realized_pnl += realized
            if merged and merged[-1]["seq"] == fill["seq"]:
                last = merged[-1]
                last["legs"].append(fill["leg"])
                last["prices"].append(price)
                last["quantity"] += fill["quantity"]
                last["fee"] += fill["fee"]
                last["realized_pnl"] += realized
                last["position_after"] = target
            else:
                merged.append(dict(seq=fill["seq"], time_ms=time_ms, quantity=fill["quantity"], price=price,
                                   prices=[price], fee=fill["fee"], realized_pnl=realized, position_after=target,
                                   legs=[fill["leg"]]))
    return merged


def research_run(profile, contract, bars):
    """The baseline backtest (funding and margin off) with every on_bar target recorded."""
    strategy_id = profile["strategy_id"]
    spec = research_catalog.strategy_spec(strategy_id)
    artifact = research_catalog.load_strategy_manifest(spec)
    snapshot, source_hash = research_catalog._verified_strategy_source_snapshot(artifact["source_files"], spec)
    if source_hash != spec.sha256:
        raise ValueError("artifact_hash_mismatch")
    strategy_class = research_catalog._module_strategy_from_verified_snapshot(snapshot, spec)
    names = [name for name, _, _ in spec.parameters]
    targets = {}

    class Recorded(research.Strategy):
        def __init__(self):
            self.inner = strategy_class(*(profile["parameters"][name] for name in names), D(profile["quantity"]))

        def update_indicators(self, bar):
            return self.inner.update_indicators(bar)

        @property
        def ready(self):
            return self.inner.ready

        def on_bar(self, bar, account):
            target = self.inner.on_bar(bar, account)
            targets[bar.open_time_ms] = target
            return target

    config = research.BacktestConfig(contract, profile["timeframe_ms"], D(profile["initial_balance"]),
                                     D(profile["fee_rate"]), D(profile["slippage_bps"]), ())
    result = research.backtest(strategy=Recorded, candles=bars, config=config, warmup_bars=profile["warmup_bars"])
    return result, targets, source_hash


def _text(value):
    return None if value is None else str(value)


def _view(view):
    """AccountView as the ledger stores it: Decimal fields as text, time_ms as an integer."""
    return {k: (v if k == "time_ms" else _text(v)) for k, v in asdict(view).items()}


def compare_run(run_dir, bars, contract, *, published=None):
    """Compare one replay directory against the research baseline on ``bars``; returns the report dict."""
    run_dir = Path(run_dir)
    manifest = _read_json(run_dir / "manifest.json")
    summary = _read_json(run_dir / "summary.json")
    profile = manifest["profile"]
    tf = profile["timeframe_ms"]
    if (len(bars) != manifest["bars"] or bars[0].open_time_ms != manifest["first_open_ms"]
            or bars[-1].open_time_ms != manifest["last_open_ms"]):
        raise ValueError("bars_do_not_match_replay_manifest")
    inputs, intents, fills, orders = ledger_facts(run_dir / manifest["database"])
    result, research_targets, source_hash = research_run(profile, contract, bars)
    config = result.config
    checks = {}
    mismatches = {}

    # 0. The replay covered every bar.
    checks["replay_completed"] = summary["status"]["state"] == "completed" and len(inputs) == len(bars)

    # 1. Worker target at every evaluation bar.
    warmup = profile["warmup_bars"]
    bot_targets = {inputs[seq]["bar"]["open_time_ms"]: inputs[seq]["target"] for seq in sorted(inputs) if seq > warmup}
    warmup_targets = [inputs[seq]["target"] for seq in sorted(inputs) if seq <= warmup]
    ref_targets = {time_ms: _text(target) for time_ms, target in research_targets.items()}
    target_diff = [dict(open_time_ms=t, bot=bot_targets.get(t), research=ref_targets.get(t))
                   for t in sorted(set(bot_targets) | set(ref_targets)) if bot_targets.get(t, "∅") != ref_targets.get(t, "∅")]
    checks["targets_equal"] = not target_diff and all(target is None for target in warmup_targets)
    mismatches["targets"] = target_diff[:MAX_LISTED]

    # 2. Fills, two reversal legs merged per decision.
    merged = _merge(fills, inputs, tf, contract, config)
    bot_rows = [dict(time_ms=m["time_ms"], quantity=str(m["quantity"]), price=str(m["price"]), fee=str(m["fee"]),
                     realized_pnl=str(m["realized_pnl"]), position_after=str(m["position_after"])) for m in merged]
    ref_rows = [dict(time_ms=t.time_ms, quantity=str(t.quantity), price=str(t.price), fee=str(t.fee),
                     realized_pnl=str(t.realized_pnl), position_after=str(t.position_after)) for t in result.trades]
    fill_diff = []
    for index in range(max(len(bot_rows), len(ref_rows))):
        bot = bot_rows[index] if index < len(bot_rows) else None
        ref = ref_rows[index] if index < len(ref_rows) else None
        if bot is None or ref is None or any(D(bot[k]) != D(ref[k]) if k != "time_ms" else bot[k] != ref[k]
                                             for k in bot):
            fill_diff.append(dict(index=index, bot=bot, research=ref))
    leg_prices_equal = all(len(set(m["prices"])) == 1 for m in merged)
    checks["fills_equal"] = not fill_diff and len(bot_rows) == len(ref_rows)
    checks["reversal_leg_prices_equal"] = leg_prices_equal
    mismatches["fills"] = fill_diff[:MAX_LISTED]

    # 3. Account view at every evaluation close (= research equity curve after the start point).
    curve = result.equity_curve[1:]
    bot_views = [inputs[seq]["account"] for seq in sorted(inputs) if seq > warmup]
    view_diff = []
    for index in range(max(len(curve), len(bot_views))):
        ref = None if index >= len(curve) else _view(curve[index])
        bot = None if index >= len(bot_views) else bot_views[index]
        if ref is None or bot is None or any(
                (D(bot[k]) != D(ref[k])) if k != "time_ms" else bot[k] != ref[k] for k in ACCOUNT_FIELDS):
            view_diff.append(dict(index=index, bot=bot, research=ref))
    checks["equity_curve_equal"] = not view_diff
    mismatches["equity_curve"] = view_diff[:MAX_LISTED]

    # 4. Final account, realized PnL and fees.
    final_ref = _view(result.equity_curve[-1])
    final_bot = summary["final_account"]
    checks["final_account_equal"] = final_bot is not None and all(
        (D(final_bot[k]) == D(final_ref[k])) if k != "time_ms" else final_bot[k] == final_ref[k]
        for k in ACCOUNT_FIELDS)
    checks["realized_and_fees_equal"] = final_bot is not None and (
        D(final_bot["realized_pnl"]) == result.performance.realized_pnl and D(final_bot["fees"]) == result.performance.fees)

    # 5. Pending intent at the end (decided at the last close, unfilled on both sides).
    pending_ref = None if result.pending_intent is None else dict(
        decision_time_ms=result.pending_intent.decision_time_ms, target=str(result.pending_intent.target_position))
    pending_bot = None if summary["pending_intent"] is None else dict(
        decision_time_ms=summary["pending_intent"]["decision_time_ms"], target=summary["pending_intent"]["target"])
    checks["pending_intent_equal"] = pending_ref == pending_bot

    # 6. Risk verdicts: only reserved / no-change; any rejection fails.
    dispositions = {}
    reasons = {}
    for intent in intents.values():
        dispositions[intent["disposition"]] = dispositions.get(intent["disposition"], 0) + 1
        reasons[intent["reason"]] = reasons.get(intent["reason"], 0) + 1
    rejected = [dict(seq=i["seq"], disposition=i["disposition"], reason=i["reason"]) for i in intents.values()
                if i["disposition"] not in ("RESERVED_SIMULATION", "NO_CHANGE")]
    checks["risk_verdicts_ok"] = not rejected
    checks["orders_terminal"] = all(o["state"] == "FILLED" and o["settled"] for o in orders)
    mismatches["rejected_verdicts"] = rejected[:MAX_LISTED]

    report = dict(
        contract="catos.replay-consistency.v1", run_id=manifest["run_id"], notice=NOTICE,
        passed=all(checks.values()), checks=checks, mismatches=mismatches,
        threshold="Decimal 完全相等，誤差 0",
        baseline="research.backtest，同一份 K 線、參數與成本；funding_events=()、margin=None",
        approval_id=manifest["approval_id"], approvals_path=manifest["approvals_path"], profile=profile,
        source_sha256=source_hash, dataset=manifest["dataset"], build_id=manifest["build_id"],
        risk_limits=manifest["risk_limits"], bars=len(bars), warmup_bars=warmup,
        evaluation_bars=len(curve),
        counts=dict(bot_fills=len(fills), bot_merged_fills=len(merged), research_fills=len(result.trades),
                    reversal_decisions=sum(1 for m in merged if len(m["legs"]) > 1),
                    dispositions=dispositions, reasons=reasons),
        bot=dict(final_account=final_bot, elapsed_seconds=summary["status"]["elapsed_seconds"],
                 ledger_bytes=summary["ledger_bytes"], fills_sha256=summary["fills_sha256"]),
        research=dict(final_equity=str(result.performance.final_equity), net_pnl=str(result.performance.net_pnl),
                      realized_pnl=str(result.performance.realized_pnl), fees=str(result.performance.fees),
                      trade_count=result.performance.trade_count),
        decision_digest=decision_digest(inputs, intents),
        fill_digest=hashlib.sha256(json_text(bot_rows).encode()).hexdigest(),
    )
    if published is not None:
        report["published_research"] = published(result)
    return report


def decision_digest(inputs, intents):
    rows = [[seq, inputs[seq]["target"]] for seq in sorted(inputs)]
    rows += [[i["seq"], i["target"], i["disposition"], i["reason"]] for i in sorted(intents.values(), key=lambda i: i["seq"])]
    return hashlib.sha256(json_text(rows).encode()).hexdigest()


def compare(run_dir):
    """Compare a replay of a registered dataset; also report the published (funding + margin) backtest."""
    run_dir = Path(run_dir)
    manifest = _read_json(run_dir / "manifest.json")
    profile = manifest["profile"]
    if manifest["dataset"] is None:
        raise ValueError("replay_without_dataset")
    dataset = research_catalog.resolve_dataset(manifest["dataset"]["id"])
    if dataset.provenance() != manifest["dataset"]:
        raise ValueError("dataset_changed_since_replay")
    config = research.BacktestConfig(dataset.contract, profile["timeframe_ms"], D(profile["initial_balance"]),
                                     D(profile["fee_rate"]), D(profile["slippage_bps"]), ())
    bars, full_config = research_catalog.load_dataset_bars(dataset.dataset_id, config)
    bars = bars[:manifest["bars"]]

    def published(baseline):
        """The backtest as published (dataset funding and the margin model on); the difference is reported."""
        full = research.backtest(strategy=lambda: _strategy(profile), candles=bars,
                                 config=full_config, warmup_bars=profile["warmup_bars"])
        same_fills = [(t.time_ms, t.quantity, t.price, t.fee) for t in full.trades] == [
            (t.time_ms, t.quantity, t.price, t.fee) for t in baseline.trades]
        with localcontext(research._CONTEXT):
            difference = full.performance.final_equity - baseline.performance.final_equity
        return dict(final_equity=str(full.performance.final_equity), net_pnl=str(full.performance.net_pnl),
                    funding_paid=str(full.performance.funding_paid),
                    final_equity_minus_baseline=str(difference), same_fills_as_baseline=same_fills,
                    liquidation=full.liquidation is not None, margin_rejections=full.margin_rejection_count,
                    margin_model=dataset.margin_summary()["enabled"], funding=dataset.funding_summary())

    return compare_run(run_dir, bars, dataset.contract, published=published)


def _strategy(profile):
    spec = research_catalog.strategy_spec(profile["strategy_id"])
    artifact = research_catalog.load_strategy_manifest(spec)
    snapshot, _ = research_catalog._verified_strategy_source_snapshot(artifact["source_files"], spec)
    strategy_class = research_catalog._module_strategy_from_verified_snapshot(snapshot, spec)
    names = [name for name, _, _ in spec.parameters]
    return strategy_class(*(profile["parameters"][name] for name in names), D(profile["quantity"]))


def compare_repeat(run_a, run_b):
    """Two replays of the same approval and bars must record the same decisions and fills byte for byte."""
    facts = []
    for run_dir in (Path(run_a), Path(run_b)):
        manifest = _read_json(run_dir / "manifest.json")
        summary = _read_json(run_dir / "summary.json")
        inputs, intents, fills, _ = ledger_facts(run_dir / manifest["database"])
        rows = fill_rows(fills)
        facts.append(dict(decision_digest=decision_digest(inputs, intents),
                          fills_digest=hashlib.sha256(json_text(rows).encode()).hexdigest(),
                          summary_fills_sha256=summary["fills_sha256"], build_id=manifest["build_id"],
                          approval_id=manifest["approval_id"], bars=manifest["bars"]))
    a, b = facts
    same = {key: a[key] == b[key] for key in a}
    return dict(contract="catos.replay-repeat.v1", runs=[str(run_a), str(run_b)], facts=facts,
                same=same, passed=all(same.values()))


def markdown(report):
    lines = [f"# 重播一致性報告 {report['run_id']}", "", f"> {report['notice']}", "",
             f"- 結果：{'PASS' if report['passed'] else 'FAIL'}（門檻：{report['threshold']}）",
             f"- 比對基準：{report['baseline']}",
             f"- 核准 id：`{report['approval_id']}`（核准檔 `{report['approvals_path']}`）",
             f"- 策略來源 sha256：`{report['source_sha256']}`；build_id `{report['build_id']}`",
             f"- 資料集：`{(report['dataset'] or {}).get('id')}`，{report['bars']} 根（預熱 {report['warmup_bars']}、"
             f"評估 {report['evaluation_bars']}）",
             f"- 風控上限：`{json.dumps(report['risk_limits'])}`", "", "| 檢查 | 結果 |", "| --- | --- |"]
    lines += [f"| {name} | {'PASS' if ok else 'FAIL'} |" for name, ok in report["checks"].items()]
    counts = report["counts"]
    lines += ["", f"- Bot 成交 {counts['bot_fills']} 筆（合併後 {counts['bot_merged_fills']}，反手 "
                  f"{counts['reversal_decisions']} 次）；研究成交 {counts['research_fills']} 筆",
              f"- 風控判定：`{json.dumps(counts['dispositions'], ensure_ascii=False)}`；原因 "
              f"`{json.dumps(counts['reasons'], ensure_ascii=False)}`",
              f"- Bot 期末權益 {report['bot']['final_account']['equity'] if report['bot']['final_account'] else '—'}；"
              f"研究（關掉資金費與保證金）{report['research']['final_equity']}",
              f"- 重播耗時 {report['bot']['elapsed_seconds']} 秒；帳本 {report['bot']['ledger_bytes']} bytes",
              f"- 成交摘要 sha256 `{report['fill_digest']}`；決策摘要 sha256 `{report['decision_digest']}`"]
    published = report.get("published_research")
    if published:
        lines += ["", "## 和已發表研究結果（含資金費與保證金模型）的差", "",
                  f"- 期末權益 {published['final_equity']}，與基準差 {published['final_equity_minus_baseline']}"
                  f"（資金費支付 {published['funding_paid']}）",
                  f"- 成交與基準相同：{published['same_fills_as_baseline']}；強平：{published['liquidation']}；"
                  f"保證金拒單 {published['margin_rejections']} 筆；保證金模型啟用：{published['margin_model']}"]
    for name, items in report["mismatches"].items():
        if items:
            lines += ["", f"## 不一致：{name}（最多列 {MAX_LISTED} 筆）", "", "```json",
                      json.dumps(items, ensure_ascii=False, indent=1), "```"]
    return "\n".join(lines) + "\n"


def cli_main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m catos.cli replay-compare",
                                     description="重播與研究回測逐筆比對（唯讀）")
    parser.add_argument("run_dir")
    parser.add_argument("--repeat-of", default=None, help="另一個同設定的重播目錄，比對兩次是否位元組相同")
    parser.add_argument("--output", default=None, help="報告輸出目錄（寫 consistency.json 與 consistency.md）")
    args = parser.parse_args(argv)
    report = compare(args.run_dir)
    if args.repeat_of:
        report["repeat"] = compare_repeat(args.repeat_of, args.run_dir)
        report["passed"] = report["passed"] and report["repeat"]["passed"]
    output = Path(args.output) if args.output else Path(args.run_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "consistency.json").write_text(json_text(report) + "\n", encoding="utf-8")
    text = markdown(report)
    if "repeat" in report:
        text += (f"\n## 兩次重播\n\n- 位元組相同：{report['repeat']['passed']}\n- `"
                 + json.dumps(report["repeat"]["same"]) + "`\n")
    (output / "consistency.md").write_text(text, encoding="utf-8")
    print(text)
    return 0 if report["passed"] else 1
