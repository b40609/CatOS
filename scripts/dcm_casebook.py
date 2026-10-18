"""Illustrate existing DCM research evidence; no new backtest or data collection.

All feature/price comparisons stay Decimal. Float conversion occurs only at
the plotting boundary and cannot change strategy signals or financial results.
"""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from decimal import localcontext
import html
import json
from pathlib import Path

from catos.dcm import D, DCMParams, DCMStrategy, HOUR
from catos.dcm_public_data import digest, write_json
from catos.dcm_study import load_snapshot, serial
from catos.research import _CONTEXT


def display_time(stamp):
    return datetime.fromtimestamp(stamp // 1000, timezone(timedelta(hours=8))).strftime("%m/%d %H:%M")


def build_cases(report, bars, step):
    run = next(row for row in report["runs"] if row["key"] == "D-15m-cap"
               and row["phase"] == "holdout" and row["cost"] == "base")
    params = DCMParams(**{name: D(value) if isinstance(value, str) and name != "candidate" else value
                         for name, value in run["parameters"].items()})
    trips, traces = run["summary"]["round_trips"], run["trace"]
    profitable = next(trip for trip in trips if trip["direction"] == "short" and D(trip["net_pnl"]) > 0)
    losing = next(trip for trip in trips if trip["direction"] == "long" and D(trip["net_pnl"]) < 0)
    by_time = {bar.open_time_ms: bar for bar in bars}
    instance = DCMStrategy(params)
    frames, rejected = {}, None
    for bar in bars:
        instance.update_indicators(bar)
        frame = instance.frame
        if frame is None:
            continue
        now = bar.open_time_ms + step
        frames[now] = frame
        if not run["start_ms"] <= bar.open_time_ms < run["end_ms"] or rejected:
            continue
        previous = instance.previous_close
        position = next((D(fill["position_after"]) for fill in reversed(run["fills"])
                         if fill["time_ms"] <= bar.open_time_ms), D(0))
        latest = next((item for item in reversed(traces) if item["decision_time_ms"] <= now), None)
        event_active = latest is not None and latest["reason"] == "event:breakout-frozen"
        if (previous is not None and previous <= frame.dh < bar.close and not position
                and not event_active and frame.strength >= params.strong_threshold
                and not any(item["reason"] == "entry:D" and item["decision_time_ms"] == now for item in traces)):
            rejected = {"decision_time_ms": now, "frame": asdict(frame)}
    if rejected is None:
        raise ValueError("the snapshot does not contain the specified strong-trend no-entry illustration")
    cases = []
    titles = ("向上突破後收回：D 為什麼考慮做空", "向下突破後收回：D 為什麼考慮做多")
    for number, trip in enumerate((profitable, losing), 1):
        decision = trip["entry_ms"]
        entry_trace = next(item for item in traces if item["reason"] == "entry:D" and item["decision_time_ms"] == decision)
        event_trace = next(item for item in reversed(traces) if item["reason"] == "event:breakout-frozen" and item["decision_time_ms"] < decision)
        if entry_trace["reference_day_ms"] != event_trace["reference_day_ms"]:
            raise ValueError("entry/event reference mismatch")
        direction = 1 if trip["direction"] == "long" else -1
        frame = frames[event_trace["decision_time_ms"]]
        if str(frame.dc) != event_trace["dc"] or str(frame.atr) != event_trace["atr"]:
            raise ValueError("causal reconstruction differs from archived evidence")
        event_bars = [bar for bar in bars if event_trace["decision_time_ms"] - step <= bar.open_time_ms < decision]
        stop = (min(bar.low for bar in event_bars) - frame.atr * params.stop_buffer_atr if direction > 0
                else max(bar.high for bar in event_bars) + frame.atr * params.stop_buffer_atr)
        signal = by_time[decision - step]
        reward = direction * (frame.dc - signal.close)
        risk = direction * (signal.close - stop)
        if reward <= 0 or risk <= 0:
            raise ValueError("illustration has no positive target/invalidity distance")
        entry_fill = next(fill for fill in run["fills"] if fill["time_ms"] == decision)
        exit_fill = next(fill for fill in run["fills"] if fill["time_ms"] == trip["exit_ms"])
        exit_trace = next(item for item in traces if item["decision_time_ms"] == trip["exit_ms"] and item["reason"].startswith("exit:"))
        cases.append({"id": f"case-{number}", "title": titles[number - 1], "decision_time_ms": decision,
                      "event_time_ms": event_trace["decision_time_ms"], "direction": direction,
                      "frame": asdict(frame), "signal_close": signal.close, "stop": stop,
                      "target_distance": reward, "invalidation_distance": risk,
                      "distance_ratio": reward / risk, "round_trip": trip,
                      "entry_fill": entry_fill, "exit_fill": exit_fill, "exit_reason": exit_trace["reason"],
                      "selection": "first profitable completed short / first losing completed long in the existing D holdout run; post-hoc explanatory examples"})
    skip = {"id": "case-3", "title": "向上突破成立：D 為什麼先不做逆向單",
            "decision_time_ms": rejected["decision_time_ms"], "event_time_ms": rejected["decision_time_ms"],
            "direction": 0, "frame": rejected["frame"],
            "signal_close": by_time[rejected["decision_time_ms"] - step].close,
            "selection": "first strong upward DH close-cross while D is flat without an active event; post-hoc explanatory example"}
    cases.append(skip)
    return cases, params


def plot_case(case, bars, step, output, future):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    plt.rcParams.update({"font.family": "Microsoft JhengHei", "axes.unicode_minus": False})
    decision, event = case["decision_time_ms"], case["event_time_ms"]
    start = event - 6 * HOUR
    end = (case["round_trip"]["exit_ms"] + 2 * HOUR if "round_trip" in case else decision + 12 * HOUR) if future else decision
    visible = [bar for bar in bars if start <= bar.open_time_ms < end]
    if not visible or (not future and any(bar.open_time_ms + step > decision for bar in visible)):
        raise ValueError("before-decision figure contains future bars")
    fig, ax = plt.subplots(figsize=(14.4, 6.6), dpi=110, facecolor="#111820")
    ax.set_facecolor("#111820")
    for index, bar in enumerate(visible):
        up = bar.close >= bar.open
        color = "#4ad1a7" if up else "#ff8f86"
        # Rendering coordinates only. Source values and all comparisons are Decimal.
        ax.plot([index, index], [float(bar.low), float(bar.high)], color=color, linewidth=0.9)
        ax.add_patch(Rectangle((index - .3, float(min(bar.open, bar.close))), .6,
                               float(max(abs(bar.close - bar.open), D("0.1"))), facecolor=color, edgecolor=color))
    frame = case["frame"]
    for name, color in (("dh", "#ffbc73"), ("dc", "#b4a3ff"), ("dl", "#6dbce6")):
        ax.axhline(float(frame[name]), color=color, linewidth=1.1, linestyle="--",
                   label=f"{'事件凍結' if case['direction'] else '當日已知'} {name.upper()}  {D(frame[name]):,.2f}")
    if "stop" in case:
        ax.axhline(float(case["stop"]), color="#f18bc2", linestyle=":", label=f"收盤失效界線  {case['stop']:,.2f}")
    event_index = next(i for i, bar in enumerate(visible) if bar.open_time_ms + step == event)
    decision_index = next(i for i, bar in enumerate(visible) if bar.open_time_ms + step == decision)
    ax.axvline(event_index, color="#ffda7e", alpha=.7, linewidth=1, label="首次收盤突破")
    ax.axvline(decision_index, color="#f4f7fa", linewidth=1.2, label="AI 解讀時點（收盤）")
    ax.scatter([decision_index], [float(case["signal_close"])], color="white", s=65, zorder=5)
    if future:
        ax.axvspan(decision_index + .5, len(visible) - .5, color="#8db2e0", alpha=.08)
        if "entry_fill" in case:
            for name, marker, color, label in (("entry_fill", "^", "#5ce0c0", "次根開盤成交"),
                                                ("exit_fill", "v", "#ffd879", "次根開盤退出")):
                fill = case[name]
                index = next(i for i, bar in enumerate(visible) if bar.open_time_ms == fill["time_ms"])
                ax.scatter([index], [float(D(fill["price"]))], marker=marker, color=color, s=100, label=label, zorder=6)
    interval = max(1, len(visible) // 8)
    ticks = list(range(0, len(visible), interval))
    ax.set_xticks(ticks, [display_time(visible[i].open_time_ms) for i in ticks], fontsize=10)
    ax.tick_params(colors="#cdd8e3")
    for spine in ax.spines.values():
        spine.set_color("#394654")
    ax.grid(alpha=.12, color="#cdd8e3")
    ax.set_ylabel("BTC 價格（USDT）", color="#cdd8e3")
    ax.set_title(case["title"] + ("｜揭示後續" if future else "｜只看當時已知資料"), color="#e8edf4", pad=16)
    ax.legend(facecolor="#1c2733", labelcolor="#e2e8ef", edgecolor="#394654", fontsize=9, loc="best")
    fig.text(.5, .015, "BTC-USDT-SWAP · 15m · 時間 UTC+8 · OHLC 研究圖；非 TradingView 原指標截圖", color="#9baec1", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, .04, 1, 1))
    path = output / f"{case['id']}-{'after' if future else 'before'}.png"
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def explanation(case, params):
    f = case["frame"]
    known = (f"解讀時點 {display_time(case['decision_time_ms'])}（UTC+8）。訊號收盤 {case['signal_close']:,.2f}；"
             f"前日來源的 DH／DC／DL = {f['dh']:,.2f}／{f['dc']:,.2f}／{f['dl']:,.2f}。"
             f"20 日均線單日變化／14 日平均 TR = {f['strength']:.4f}。")
    if case["direction"] == 0:
        logic = (f"收盤確實從 DH 下方越過 DH，但事前趨勢值已達 {f['strength']:.4f}，高於本輪強同向閾值 {params.strong_threshold}。"
                 "D 此時不建立逆向突破失敗事件。突破成立與反轉成立是兩個不同條件；這裡只看見前者。")
        challenge = "閾值是否有區分力尚待跨期間驗證。可以將 A／B 當作另一個比較假說，不能以這一張圖認定趨勢策略較好。"
        outcome = "這是 D 沒有進場的例子。後續圖只展示行情，不捏造一筆『如果有做』的交易或損益。"
    else:
        side = "做多" if case["direction"] > 0 else "做空"
        boundary = "DL" if case["direction"] > 0 else "DH"
        logic = (f"先有獨立收盤突破 {boundary}，後續已收盤棒又收回區間；原突破方向不屬強同向環境，"
                 f"且價格尚未越過目標 DC。因此 D 產生 {side}意圖，下一根開盤才成交。"
                 f"目標凍結 DC {f['dc']:,.2f}，收盤失效界線 {case['stop']:,.2f}（事件極值加減 0.2 ATR）。")
        challenge = (f"在訊號收盤暫估，目標空間 {case['target_distance']:,.2f}，失效距離 {case['invalidation_distance']:,.2f}，"
                     f"兩者比值 {case['distance_ratio']:.2f}；尚未扣下一根開盤的跳空、費用與滑價。"
                     "收回可能只是短暫回踩，DC 也不是價格必然回歸的位置。這些是解讀的疑點，沒有事後加條件排除。")
        trip = case["round_trip"]
        reason = "收盤達到凍結 DC" if case["exit_reason"] == "exit:DC-target" else "收盤穿過失效界線"
        outcome = (f"後續：{reason}，在 {display_time(trip['exit_ms'])} 的下一根開盤退出。"
                   f"成交價 {case['entry_fill']['price']} → {case['exit_fill']['price']}；"
                   f"成本後淨損益 {D(trip['net_pnl']):+.4f} USDT（1 張 0.01 BTC，含費用與資金費近似）。"
                   "收盤失效判定並不保證以界線價格成交。")
    return known, logic, challenge, outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(args.snapshot.resolve()) or output.is_relative_to(args.report.parent.resolve()):
        raise ValueError("casebook output must be separate from immutable research inputs")
    manifest, datasets = load_snapshot(args.snapshot)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if digest(args.snapshot / "manifest.json") != report["preregistration"]["snapshot_manifest_sha256"]:
        raise ValueError("report and snapshot differ")
    root = Path(__file__).resolve().parent.parent
    for name, expected in report["preregistration"]["source_hashes"].items():
        if digest(root / name) != expected:
            raise ValueError("current research source differs from archived source")
    bars, config = datasets["15m"]
    with localcontext(_CONTEXT):
        cases, params = build_cases(report, bars, config.timeframe_ms)
        text = [explanation(case, params) for case in cases]
    args.output.mkdir(parents=True, exist_ok=False)
    for case in cases:
        for future in (False, True):
            plot_case(case, bars, config.timeframe_ms, args.output, future)
    cards = []
    esc = html.escape
    for case, paragraphs in zip(cases, text):
        known, logic, challenge, outcome = paragraphs
        cards.append(f"<article><h2>{esc(case['title'])}</h2><p>{esc(known)}</p><p>{esc(logic)}</p>"
                     f"<p class='question'>{esc(challenge)}</p><label><input type='checkbox' class='reveal'> 顯示後續走勢與實際結果</label>"
                     f"<img class='before' src='{case['id']}-before.png' alt='只顯示解讀時點以前的行情'>"
                     f"<img class='after' src='{case['id']}-after.png' alt='包含後續行情，實際交易才標成交'>"
                     f"<p class='outcome'>{esc(outcome)}</p><p class='prompt'>你只需判斷：這段理解合理嗎？哪個交易假設與你的認知不同？</p></article>")
    document = ("<!doctype html><html lang='zh-Hant'><meta charset='utf-8'><meta name='viewport' content='width=device-width'>"
                "<title>DCM：AI 先解讀，再由交易者校準</title><style>body{font:16px/1.7 system-ui;background:#111820;color:#dce5ee;"
                "margin:24px auto;padding:0 20px;max-width:1450px}h1{font-size:25px}h2{font-size:21px}article{margin:30px 0;padding:20px;"
                "border:1px solid #354251;border-radius:10px}img{width:100%;height:auto;margin-top:15px}.after,.outcome{display:none}"
                "article:has(.reveal:checked) .after,article:has(.reveal:checked) .outcome{display:block}"
                "article:has(.reveal:checked) .before{display:none}.question{color:#e5c996}.prompt{color:#91d3ed}label{cursor:pointer}</style>"
                "<h1>DCM：由 AI 解讀實際案例，再請交易者校準</h1><p>三個例子由 AI 從既有 BTC 研究挑選。"
                "預設只顯示當時可知的 K 線與規則，勾選後才揭示後續。你不需要先挑圖、補完整規則或替 AI 解題。</p>"
                "<p>這是已使用資料的事後解讀範例，含成功、失敗與不進場情境；不是新的樣本外測試、訊號建議或原 Pine 完整畫面。"
                "本輪未改策略、重新調參、重跑回測或下載資料。</p>" + "".join(cards) + "</html>")
    with (args.output / "index.html").open("x", encoding="utf-8") as handle:
        handle.write(document)
    with (args.output / "generator.py").open("xb") as handle:
        handle.write(Path(__file__).read_bytes())
    write_json(args.output / "cases.json", serial({"source_report_sha256": digest(args.report),
               "snapshot_sha256": digest(args.snapshot / "manifest.json"), "script_sha256": digest(__file__),
               "parameters": asdict(params), "cases": cases, "explanations": text,
               "new_backtests": 0, "new_downloads": 0, "plot_coordinate_float_only": True}))
    write_json(args.output / "evidence.json", {"files": {path.name: digest(path) for path in sorted(args.output.iterdir()) if path.is_file()}})
    print(json.dumps({"output": str(args.output.resolve()), "cases": len(cases), "new_backtests": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
