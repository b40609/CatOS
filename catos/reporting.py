"""Pure-function research report generator for catOS.

Uses only Python standard library.
Generates self-contained, standalone Traditional Chinese HTML with embedded SVG equity curve.
Coordinates and values are calculated strictly using Decimal/integers without float conversion.
Does not write files, start servers, or reference external CDN, scripts, or images.
"""

from decimal import Decimal, localcontext
import html

from catos.research import (
    AccountView,
    BacktestResult,
    FundingPayment,
    Trade,
    _CONTEXT,
)


def _format_decimal(val: Decimal | int | str) -> str:
    """Format Decimal strictly in full-precision fixed-point without scientific notation."""
    if isinstance(val, Decimal):
        return f"{val:f}"
    return str(val)


def _render_svg(curve: tuple[AccountView, ...]) -> str:
    """Render an embedded SVG equity curve using only Decimal and integer arithmetic."""
    with localcontext(_CONTEXT):
        width = Decimal("800")
        height = Decimal("300")
        pad_left = Decimal("90")
        pad_right = Decimal("30")
        pad_top = Decimal("30")
        pad_bottom = Decimal("40")
        if curve:
            low, high = min(pt.equity for pt in curve), max(pt.equity for pt in curve)
            labels = (low, high, (low + high) / Decimal("2"))
            pad_left = max(pad_left, Decimal(max(len(_format_decimal(v)) for v in labels) * 7 + 20))
            width = pad_left + Decimal("710")
        plot_w = width - pad_left - pad_right  # 680
        plot_h = height - pad_top - pad_bottom  # 230

        if not curve:
            return (
                f'<svg viewBox="0 0 {width} 300" class="chart-svg" xmlns="http://www.w3.org/2000/svg">'
                f'<rect width="{width}" height="300" fill="#161b22" rx="6"/>'
                '<text x="400" y="150" text-anchor="middle" fill="#8b949e" font-size="14">'
                '無權益曲線資料'
                '</text>'
                '</svg>'
            )

        if len(curve) == 1:
            x_mid = pad_left + plot_w / Decimal("2")
            y_mid = pad_top + plot_h / Decimal("2")
            x_str = _format_decimal(x_mid.quantize(Decimal("0.1")))
            y_str = _format_decimal(y_mid.quantize(Decimal("0.1")))
            eq_str = html.escape(_format_decimal(curve[0].equity))
            return (
                f'<svg viewBox="0 0 {width} 300" class="chart-svg" xmlns="http://www.w3.org/2000/svg">'
                f'<rect width="{width}" height="300" fill="#161b22" rx="6"/>'
                f'<line x1="{pad_left}" y1="{y_str}" x2="{pad_left + plot_w}" y2="{y_str}" stroke="#30363d" stroke-dasharray="4,4"/>'
                f'<circle cx="{x_str}" cy="{y_str}" r="5" fill="#58a6ff"/>'
                f'<text x="{x_str}" y="{str((y_mid - Decimal("12")).quantize(Decimal("0.1")))}" text-anchor="middle" fill="#c9d1d9" font-size="12">{eq_str}</text>'
                f'<text x="{pad_left - Decimal("10")}" y="{str((y_mid + Decimal("4")).quantize(Decimal("0.1")))}" text-anchor="end" fill="#8b949e" font-size="11">{eq_str}</text>'
                '</svg>'
            )

        equities = [pt.equity for pt in curve]
        min_eq = min(equities)
        max_eq = max(equities)
        n = len(curve)
        divisor = Decimal(n - 1)

        # Handle horizontal curve (constant equity)
        if min_eq == max_eq:
            y_mid = pad_top + plot_h / Decimal("2")
            y_str = str(y_mid.quantize(Decimal("0.1")))
            pts = []
            for i in range(n):
                x = pad_left + (Decimal(i) * plot_w) / divisor
                pts.append(f"{x.quantize(Decimal('0.1'))},{y_str}")
            points_attr = " ".join(pts)
            eq_str = html.escape(_format_decimal(min_eq))
            return (
                f'<svg viewBox="0 0 {width} 300" class="chart-svg" xmlns="http://www.w3.org/2000/svg">'
                f'<rect width="{width}" height="300" fill="#161b22" rx="6"/>'
                f'<line x1="{pad_left}" y1="{y_str}" x2="{pad_left + plot_w}" y2="{y_str}" stroke="#30363d" stroke-dasharray="4,4"/>'
                f'<polyline points="{points_attr}" fill="none" stroke="#58a6ff" stroke-width="2"/>'
                f'<text x="{pad_left - Decimal("10")}" y="{str((y_mid + Decimal("4")).quantize(Decimal("0.1")))}" text-anchor="end" fill="#8b949e" font-size="11">{eq_str}</text>'
                '</svg>'
            )

        # Normal curve with range > 0 (supports negative and positive equity)
        eq_range = max_eq - min_eq
        pts = []
        for i, pt in enumerate(curve):
            x = pad_left + (Decimal(i) * plot_w) / divisor
            y = pad_top + plot_h - ((pt.equity - min_eq) * plot_h) / eq_range
            pts.append(f"{x.quantize(Decimal('0.1'))},{y.quantize(Decimal('0.1'))}")
        points_attr = " ".join(pts)

        # Grid reference lines (Top, Mid, Bottom)
        y_top = pad_top
        y_mid = pad_top + plot_h / Decimal("2")
        y_bot = pad_top + plot_h

        mid_eq = (max_eq + min_eq) / Decimal("2")

        max_str = html.escape(_format_decimal(max_eq))
        mid_str = html.escape(_format_decimal(mid_eq))
        min_str = html.escape(_format_decimal(min_eq))

        # Zero reference line if crossing zero
        zero_line_svg = ""
        if min_eq < Decimal("0") < max_eq:
            y_zero = pad_top + plot_h - ((Decimal("0") - min_eq) * plot_h) / eq_range
            y_zero_str = str(y_zero.quantize(Decimal("0.1")))
            zero_line_svg = (
                f'<line x1="{pad_left}" y1="{y_zero_str}" x2="{pad_left + plot_w}" y2="{y_zero_str}" stroke="#f85149" stroke-dasharray="3,3" stroke-width="1"/>'
                f'<text x="{pad_left - Decimal("10")}" y="{str((y_zero + Decimal("4")).quantize(Decimal("0.1")))}" text-anchor="end" fill="#f85149" font-size="11">0</text>'
            )

        return (
            f'<svg viewBox="0 0 {width} 300" class="chart-svg" xmlns="http://www.w3.org/2000/svg">'
            f'<rect width="{width}" height="300" fill="#161b22" rx="6"/>'
            f'<line x1="{pad_left}" y1="{y_top}" x2="{pad_left + plot_w}" y2="{y_top}" stroke="#21262d" stroke-dasharray="2,2"/>'
            f'<line x1="{pad_left}" y1="{y_mid}" x2="{pad_left + plot_w}" y2="{y_mid}" stroke="#21262d" stroke-dasharray="2,2"/>'
            f'<line x1="{pad_left}" y1="{y_bot}" x2="{pad_left + plot_w}" y2="{y_bot}" stroke="#21262d" stroke-dasharray="2,2"/>'
            f'{zero_line_svg}'
            f'<polyline points="{points_attr}" fill="none" stroke="#58a6ff" stroke-width="2"/>'
            f'<text x="{pad_left - Decimal("10")}" y="{str((y_top + Decimal("4")).quantize(Decimal("0.1")))}" text-anchor="end" fill="#8b949e" font-size="11">{max_str}</text>'
            f'<text x="{pad_left - Decimal("10")}" y="{str((y_mid + Decimal("4")).quantize(Decimal("0.1")))}" text-anchor="end" fill="#8b949e" font-size="11">{mid_str}</text>'
            f'<text x="{pad_left - Decimal("10")}" y="{str((y_bot + Decimal("4")).quantize(Decimal("0.1")))}" text-anchor="end" fill="#8b949e" font-size="11">{min_str}</text>'
            '</svg>'
        )


def _render_trades_table(trades: tuple[Trade, ...]) -> str:
    if not trades:
        return '<tr><td colspan="7" class="text-center empty-cell">無模擬成交紀錄</td></tr>'

    rows = []
    for t in trades:
        rows.append(
            f"<tr>"
            f"<td>{html.escape(str(t.time_ms))}</td>"
            f"<td>{html.escape(str(t.decision_time_ms))}</td>"
            f"<td>{html.escape(_format_decimal(t.quantity))}</td>"
            f"<td>{html.escape(_format_decimal(t.price))}</td>"
            f"<td>{html.escape(_format_decimal(t.fee))}</td>"
            f"<td>{html.escape(_format_decimal(t.realized_pnl))}</td>"
            f"<td>{html.escape(_format_decimal(t.position_after))}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _render_funding_table(funding: tuple[FundingPayment, ...]) -> str:
    if not funding:
        return '<tr><td colspan="5" class="text-center empty-cell">無資金費紀錄</td></tr>'

    rows = []
    for f in funding:
        rows.append(
            f"<tr>"
            f"<td>{html.escape(str(f.time_ms))}</td>"
            f"<td>{html.escape(_format_decimal(f.position))}</td>"
            f"<td>{html.escape(_format_decimal(f.rate))}</td>"
            f"<td>{html.escape(_format_decimal(f.mark_price))}</td>"
            f"<td>{html.escape(_format_decimal(f.amount_paid))}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def render_report(result: BacktestResult) -> str:
    """Render a self-contained Traditional Chinese HTML research backtest report.

    Parameters
    ----------
    result : BacktestResult
        The backtest execution result object.

    Returns
    -------
    str
        Self-contained HTML string.
    """
    if not isinstance(result, BacktestResult):
        raise TypeError("result must be BacktestResult")

    cfg = result.config
    spec = cfg.contract
    perf = result.performance

    # Final position and intent
    final_pos = result.equity_curve[-1].position if result.equity_curve else "無資料"
    final_entry = result.equity_curve[-1].average_entry if result.equity_curve else "無資料"
    pending_intent_str = "無"
    if result.pending_intent is not None:
        pending_intent_str = (
            f"目標張數: {html.escape(_format_decimal(result.pending_intent.target_position))} "
            f"(決策時間: {html.escape(str(result.pending_intent.decision_time_ms))})"
        )

    svg_chart = _render_svg(result.equity_curve)
    trades_rows = _render_trades_table(result.trades)
    funding_rows = _render_funding_table(result.funding)

    assumptions_items = "\n".join(
        f"<li>{html.escape(a)}</li>" for a in result.assumptions
    )

    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>catOS 研究回測報告 - {html.escape(spec.inst_id)}</title>
<style>
:root {{
  --bg-color: #0d1117;
  --panel-bg: #161b22;
  --border-color: #30363d;
  --text-main: #c9d1d9;
  --text-muted: #8b949e;
  --accent-blue: #58a6ff;
  --accent-green: #3fb950;
  --accent-red: #f85149;
  --accent-warn: #d29922;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background-color: var(--bg-color);
  color: var(--text-main);
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang TC", "Microsoft JhengHei", sans-serif;
  line-height: 1.6;
  padding: 24px;
}}
.container {{
  max-width: 1100px;
  margin: 0 auto;
}}
header {{
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 16px;
  margin-bottom: 24px;
}}
h1 {{
  font-size: 24px;
  color: #f0f6fc;
  margin-bottom: 8px;
}}
.boundary-banner {{
  background-color: rgba(210, 153, 34, 0.15);
  border: 1px solid var(--accent-warn);
  color: #e3b341;
  padding: 12px 16px;
  border-radius: 6px;
  font-size: 14px;
  margin-bottom: 24px;
}}
.section-title {{
  font-size: 18px;
  color: #f0f6fc;
  border-left: 4px solid var(--accent-blue);
  padding-left: 8px;
  margin: 28px 0 14px 0;
}}
.card-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}}
.card {{
  background-color: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 14px 18px;
}}
.card-label {{
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 4px;
}}
.card-value {{
  font-size: 18px;
  font-weight: 600;
  color: #f0f6fc;
  word-break: break-all;
}}
.table-container {{
  background-color: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  overflow-x: auto;
  margin-bottom: 24px;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 14px;
}}
th, td {{
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}}
th {{
  background-color: #1f242c;
  color: #f0f6fc;
  font-weight: 600;
}}
tr:last-child td {{
  border-bottom: none;
}}
.text-center {{
  text-align: center;
}}
.empty-cell {{
  color: var(--text-muted);
  padding: 24px;
}}
.chart-container {{
  overflow-x: auto;
  background-color: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 24px;
}}
.chart-svg {{
  width: 100%;
  min-width: 800px;
  height: auto;
  display: block;
}}
.chart-svg text {{ font-family: monospace; }}
@media (max-width: 560px) {{
  body {{ padding: 16px; }}
  .card-grid {{ grid-template-columns: minmax(0, 1fr); }}
}}
ul.assumptions-list {{
  background-color: var(--panel-bg);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 16px 20px 16px 36px;
  font-size: 14px;
  color: var(--text-muted);
}}
ul.assumptions-list li {{
  margin-bottom: 6px;
}}
ul.assumptions-list li:last-child {{
  margin-bottom: 0;
}}
footer {{
  margin-top: 36px;
  padding-top: 16px;
  border-top: 1px solid var(--border-color);
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
}}
</style>
</head>
<body>
<div class="container">
<header>
  <h1>catOS 研究回測報告 - {html.escape(spec.inst_id)}</h1>
  <div class="boundary-banner">
    <strong>聲明：</strong>本報告為純記憶體 Closed Bar 模型之研究結果，非 Demo／Live 執行器。交易筆數指模擬成交筆數，不宣稱往返交易數。未建立保證金、強平或交易所端狀態機模型。
  </div>
</header>

<h2 class="section-title">回測與合約設定</h2>
<div class="card-grid">
  <div class="card">
    <div class="card-label">合約標的 (inst_id)</div>
    <div class="card-value">{html.escape(spec.inst_id)}</div>
  </div>
  <div class="card">
    <div class="card-label">K 線週期 (timeframe_ms)</div>
    <div class="card-value">{html.escape(str(cfg.timeframe_ms))} ms</div>
  </div>
  <div class="card">
    <div class="card-label">預熱根數 (warmup_bars)</div>
    <div class="card-value">{html.escape(str(result.warmup_bars))}</div>
  </div>
  <div class="card">
    <div class="card-label">正式評估起訖時間 (ms)</div>
    <div class="card-value">{html.escape(str(result.evaluation_start_ms))} ~ {html.escape(str(result.evaluation_end_ms))}</div>
  </div>
  <div class="card">
    <div class="card-label">每張合約標的幣數 (base_per_contract)</div>
    <div class="card-value">{html.escape(_format_decimal(spec.base_per_contract))}</div>
  </div>
  <div class="card">
    <div class="card-label">Tick Size / Lot Size</div>
    <div class="card-value">{html.escape(_format_decimal(spec.tick_size))} / {html.escape(_format_decimal(spec.lot_size))}</div>
  </div>
  <div class="card">
    <div class="card-label">最小委託張數 (min_size)</div>
    <div class="card-value">{html.escape(_format_decimal(spec.min_size))}</div>
  </div>
  <div class="card">
    <div class="card-label">費率 / 滑價</div>
    <div class="card-value">{html.escape(_format_decimal(cfg.fee_rate))} / {html.escape(_format_decimal(cfg.slippage_bps))} bps</div>
  </div>
</div>

<h2 class="section-title">績效指標</h2>
<div class="card-grid">
  <div class="card">
    <div class="card-label">初始權益 (initial_equity)</div>
    <div class="card-value">{html.escape(_format_decimal(perf.initial_equity))}</div>
  </div>
  <div class="card">
    <div class="card-label">期末權益 (final_equity)</div>
    <div class="card-value">{html.escape(_format_decimal(perf.final_equity))}</div>
  </div>
  <div class="card">
    <div class="card-label">淨損益 (net_pnl)</div>
    <div class="card-value">{html.escape(_format_decimal(perf.net_pnl))}</div>
  </div>
  <div class="card">
    <div class="card-label">總報酬率 (return_pct)</div>
    <div class="card-value">{html.escape(_format_decimal(perf.return_pct))}%</div>
  </div>
  <div class="card">
    <div class="card-label">已實現損益 (realized_pnl)</div>
    <div class="card-value">{html.escape(_format_decimal(perf.realized_pnl))}</div>
  </div>
  <div class="card">
    <div class="card-label">未實現損益 (unrealized_pnl)</div>
    <div class="card-value">{html.escape(_format_decimal(perf.unrealized_pnl))}</div>
  </div>
  <div class="card">
    <div class="card-label">手續費支出 (fees)</div>
    <div class="card-value">{html.escape(_format_decimal(perf.fees))}</div>
  </div>
  <div class="card">
    <div class="card-label">資金費支出 (funding_paid)</div>
    <div class="card-value">{html.escape(_format_decimal(perf.funding_paid))}</div>
  </div>
  <div class="card">
    <div class="card-label">收盤最大回撤 (max_drawdown_pct)</div>
    <div class="card-value">{html.escape(_format_decimal(perf.max_drawdown_pct))}%</div>
  </div>
  <div class="card">
    <div class="card-label">模擬成交筆數 (trade_count)</div>
    <div class="card-value">{html.escape(str(perf.trade_count))}</div>
  </div>
</div>

<h2 class="section-title">期末部位與委託狀態</h2>
<div class="card-grid">
  <div class="card">
    <div class="card-label">期末持倉張數</div>
    <div class="card-value">{html.escape(_format_decimal(final_pos))}</div>
  </div>
  <div class="card">
    <div class="card-label">期末持倉均價</div>
    <div class="card-value">{html.escape(_format_decimal(final_entry))}</div>
  </div>
  <div class="card" style="grid-column: 1 / -1;">
    <div class="card-label">末根未成交意圖 (pending_intent)</div>
    <div class="card-value" style="font-size: 15px;">{pending_intent_str}</div>
  </div>
</div>

<h2 class="section-title">收盤權益曲線</h2>
<p>窄視窗可左右捲動圖表與下方明細表。</p>
<div class="chart-container">
  {svg_chart}
</div>

<h2 class="section-title">模擬逐筆成交明細 ({len(result.trades)})</h2>
<div class="table-container">
  <table>
    <thead>
      <tr>
        <th>成交時間 (ms)</th>
        <th>決策時間 (ms)</th>
        <th>成交張數</th>
        <th>成交價格</th>
        <th>手續費</th>
        <th>實現損益</th>
        <th>成交後持倉</th>
      </tr>
    </thead>
    <tbody>
{trades_rows}
    </tbody>
  </table>
</div>

<h2 class="section-title">資金費分錄 ({len(result.funding)})</h2>
<div class="table-container">
  <table>
    <thead>
      <tr>
        <th>結算時間 (ms)</th>
        <th>結算持倉張數</th>
        <th>資金費率</th>
        <th>標記價格</th>
        <th>支付金額 (+扣款/-入帳)</th>
      </tr>
    </thead>
    <tbody>
{funding_rows}
    </tbody>
  </table>
</div>

<h2 class="section-title">模型假設與界線</h2>
<ul class="assumptions-list">
{assumptions_items}
</ul>

<footer>
  catOS v1 研究核心 &bull; 自包含離線報告 &bull; 嚴格十進位數值模型
</footer>
</div>
</body>
</html>
"""
