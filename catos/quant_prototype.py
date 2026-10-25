"""High-fidelity localhost-only quant workspace prototype.

The surface is deliberately self-contained: all research, optimization and
runtime interactions are browser-side mock state. It does not call exchange,
AI, trading, database, or strategy lifecycle mutation endpoints.
"""


def render_quant_prototype():
    return r'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>catOS · 策略研究原型</title>
<style>
:root{
  color-scheme:dark;
  --bg:#0D0E10;--panel:#17191C;--panel2:#121417;--panel3:#1d2024;
  --line:#2A2D31;--line2:#363A3F;--text:#ECEFF2;--muted:#8F969E;
  --gold:#C6AA62;--gold2:#9c8650;--green:#75B798;--red:#D37F79;--blue:#7F9EC5;
  --sans:"Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif;
  --mono:"SFMono-Regular",Consolas,"Liberation Mono",monospace;
}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:var(--bg);color:var(--text);font:14px/1.5 var(--sans)}
button,input,select{font:inherit}button{cursor:pointer}.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.app{min-height:100vh;background:var(--bg)}
.subnav{height:54px;border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 18px;gap:16px;background:#101214;position:sticky;top:0;z-index:20}
.nav-group,.segmented{display:flex;align-items:center;gap:2px}.nav-btn,.seg-btn{border:1px solid transparent;background:transparent;color:var(--muted);height:32px;padding:0 13px;border-radius:4px;font-weight:700}
.nav-btn.active,.seg-btn.active{color:var(--text);border-color:var(--line2);background:var(--panel3)}
.nav-btn.active{box-shadow:inset 0 -2px var(--gold)}
.spacer{flex:1}.mock-tag{font-size:11px;color:#a9a095;border:1px solid #494237;padding:3px 7px;border-radius:3px;letter-spacing:.08em}
.toolbar-label{color:var(--muted);font-size:12px}.toolbar-select{height:32px;background:var(--panel);border:1px solid var(--line2);color:var(--text);border-radius:4px;padding:0 28px 0 9px}
.workspace{min-height:calc(100vh - 54px);padding:14px;gap:14px}.workspace.layout-a{display:grid;grid-template-columns:248px minmax(0,1fr)}.workspace.layout-b{display:grid;grid-template-columns:minmax(340px,30%) minmax(0,1fr)}
.strategy-rail,.settings-panel,.results-panel,.runtime-panel{background:var(--panel);border:1px solid var(--line);border-radius:5px}
.strategy-rail{grid-column:1;min-width:0;overflow:hidden}.rail-head,.panel-head{display:flex;align-items:center;justify-content:space-between;padding:12px 13px;border-bottom:1px solid var(--line)}
.kicker{font-size:11px;color:var(--muted);letter-spacing:.08em}.title{font-size:15px;font-weight:800}.strategy-list{padding:7px}.strategy-card{width:100%;text-align:left;padding:11px;border:1px solid transparent;border-radius:4px;background:transparent;color:var(--text);margin-bottom:4px}
.strategy-card:hover{background:var(--panel3)}.strategy-card.active{border-color:#5a4f33;background:#1c1b17;box-shadow:inset 2px 0 var(--gold)}
.strategy-card .name{font-weight:800}.strategy-card .meta{color:var(--muted);font:11px var(--mono);margin-top:4px}.mini-badge{display:inline-flex;align-items:center;border:1px solid var(--line2);padding:1px 5px;border-radius:3px;color:var(--muted);font-size:10px;margin-left:5px}
.results-panel{grid-column:2;min-width:0;overflow:hidden}.result-head{padding:14px 16px 11px;border-bottom:1px solid var(--line)}
.result-topline{display:flex;align-items:flex-start;gap:12px}.strategy-heading{font-size:19px;font-weight:850;letter-spacing:.01em}.strategy-sub{color:var(--muted);font-size:12px;margin-top:3px}
.badge{display:inline-flex;align-items:center;gap:5px;height:22px;padding:0 7px;border:1px solid var(--line2);border-radius:3px;font-size:11px;color:var(--muted)}.badge.gold{color:#dbc681;border-color:#665a38}.badge.good{color:var(--green);border-color:#355848}.badge.warn{color:#d4b66d;border-color:#635730}
.head-actions{margin-left:auto;display:flex;gap:7px;align-items:center}.btn{height:34px;padding:0 12px;border-radius:4px;border:1px solid var(--line2);background:#1d2024;color:var(--text);font-weight:700}.btn:hover{border-color:#555b63;background:#22262b}.btn.primary{background:var(--gold);border-color:var(--gold);color:#16130c}.btn.primary:hover{background:#d2b86f}.btn.ghost{background:transparent}.btn.small{height:29px;padding:0 9px;font-size:12px}.btn.danger{color:#e5a39f;border-color:#664340;background:#211818}
.b-strategy-picker{display:none;margin-bottom:10px;align-items:center;gap:8px}.b-strategy-picker select{min-width:260px}
.consistency{display:flex;align-items:center;gap:9px;margin:10px 0 0;padding:8px 10px;border:1px solid #5f5333;background:#1c1a14;border-radius:4px;color:#d6c17d;font-size:12px}.consistency.hidden{display:none}.dot{width:7px;height:7px;border-radius:50%;background:var(--gold);flex:none}
.result-body{padding:14px 16px}.chart-card{border:1px solid var(--line);background:var(--panel2);border-radius:4px}.chart-head{height:45px;border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 12px;gap:8px}.chart-title{font-weight:800}.chart-meta{color:var(--muted);font:11px var(--mono)}
.chart-tabs{margin-left:auto}.chart-tabs button{height:27px;padding:0 9px;border:1px solid var(--line);background:transparent;color:var(--muted)}.chart-tabs button:first-child{border-radius:3px 0 0 3px}.chart-tabs button:last-child{border-radius:0 3px 3px 0}.chart-tabs button.active{color:#e6d39b;border-color:#766640;background:#211e16}
.chart-wrap{position:relative;height:330px;padding:16px 10px 8px}.chart-wrap svg{width:100%;height:100%;display:block;overflow:visible}.chart-grid{stroke:#292c30;stroke-width:1}.chart-line{fill:none;stroke:var(--gold);stroke-width:2}.draw-line{fill:none;stroke:#a36d69;stroke-width:2}.chart-fill{fill:url(#equityFill)}.hover-line{stroke:#656a70;stroke-width:1;stroke-dasharray:4 4}.hover-dot{fill:var(--gold);stroke:#111;stroke-width:2}.tooltip{position:absolute;display:none;pointer-events:none;min-width:148px;background:#0f1113;border:1px solid #4a4f55;border-radius:4px;padding:8px 9px;box-shadow:0 7px 24px #0008;font-size:11px}.tooltip strong{display:block;color:#f4e4b3;font:12px var(--mono);margin-bottom:2px}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:10px 0}.metric{border:1px solid var(--line);background:#141619;padding:10px 11px;border-radius:4px}.metric .label{color:var(--muted);font-size:11px}.metric .value{font:700 20px var(--mono);margin-top:4px}.metric .unit{font:11px var(--sans);color:var(--muted);margin-left:4px}.positive{color:var(--green)}.negative{color:var(--red)}
.run-meta{display:flex;gap:14px;flex-wrap:wrap;border:1px solid var(--line);background:#131518;padding:8px 10px;border-radius:4px;color:var(--muted);font-size:11px}.run-meta b{color:#c8cdd2;font-weight:600}.history-chips{margin-left:auto;display:flex;gap:5px}.history-chip{border:1px solid var(--line2);background:#17191c;color:#aaa;padding:1px 6px;border-radius:3px;font:10px var(--mono)}
.tabs-row{display:flex;gap:3px;border-bottom:1px solid var(--line);margin-top:14px}.tab{border:0;background:transparent;color:var(--muted);padding:9px 11px;border-bottom:2px solid transparent;font-weight:700}.tab.active{color:#ead9a8;border-bottom-color:var(--gold)}
.tab-panel{display:none;padding-top:10px}.tab-panel.active{display:block}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:4px}.data-table{width:100%;border-collapse:collapse;min-width:760px}.data-table th{position:sticky;top:0;text-align:left;background:#171a1e;color:var(--muted);font-size:11px;font-weight:700;padding:8px 10px;border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap}.data-table td{padding:8px 10px;border-bottom:1px solid #24272b;font:12px var(--mono);white-space:nowrap}.data-table tr:last-child td{border-bottom:0}.data-table tbody tr:hover{background:#1d2024}.sort-arrow{color:var(--gold);margin-left:3px}
.empty-state,.failed-state,.running-state{display:none;height:430px;align-items:center;justify-content:center;text-align:center;border:1px dashed #393d42;background:#111315;border-radius:4px}.state-box{max-width:420px;padding:24px}.state-icon{font:30px var(--mono);color:var(--muted)}.state-title{font-size:17px;font-weight:800;margin:8px}.state-copy{color:var(--muted);font-size:13px}.progress{height:6px;background:#24282c;border-radius:3px;overflow:hidden;margin:16px 0}.progress>span{display:block;height:100%;background:var(--gold);width:0;transition:width .25s linear}
.settings-panel{display:none}.layout-a .settings-panel{display:block;position:fixed;right:0;top:54px;bottom:0;width:420px;z-index:30;transform:translateX(100%);transition:transform .18s ease;border-radius:0;border-top:0;border-bottom:0;box-shadow:-14px 0 30px #0007;overflow:auto}.layout-a.settings-open .settings-panel{transform:translateX(0)}
.layout-b .strategy-rail{display:none}.layout-b .settings-panel{display:block;grid-column:1;grid-row:1;position:static;transform:none;width:auto;overflow:auto;max-height:calc(100vh - 82px);align-self:start;position:sticky;top:68px}.layout-b .results-panel{grid-column:2;grid-row:1}.layout-b .b-strategy-picker{display:flex}.layout-b .drawer-close{display:none}.layout-b .open-settings{display:none}
.settings-section{padding:13px;border-bottom:1px solid var(--line)}.section-title{font-weight:800;margin-bottom:9px}.section-note{color:var(--muted);font-size:11px}.rule-list{margin:0;padding:0;list-style:none;display:grid;gap:7px}.rule-list li{padding-left:14px;position:relative;color:#cfd3d6}.rule-list li:before{content:"›";position:absolute;left:0;color:var(--gold)}
.field-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px}.field{display:flex;flex-direction:column;gap:5px}.field.full{grid-column:1/-1}.field label{font-size:11px;color:var(--muted)}.field input,.field select{width:100%;height:34px;border:1px solid var(--line2);border-radius:4px;background:#111316;color:var(--text);padding:0 9px;font-family:var(--mono)}.field input:focus,.field select:focus{outline:1px solid var(--gold);border-color:var(--gold)}
.range-note{color:#7f868d;font-size:10px;font-family:var(--mono)}details{border-top:1px solid var(--line)}details summary{padding:10px 13px;cursor:pointer;color:#c3c8cc;font-weight:700}details>div{padding:0 13px 13px}.code{overflow:auto;background:#0f1113;border:1px solid var(--line);border-radius:4px;padding:11px;color:#c8cdd2;font:11px/1.7 var(--mono);white-space:pre}.code .kw{color:#d0b66e}.code .cm{color:#6f777f}
.opt-drawer{position:fixed;right:0;top:54px;bottom:0;width:520px;background:#15171a;border-left:1px solid var(--line2);z-index:50;transform:translateX(100%);transition:transform .18s ease;box-shadow:-15px 0 32px #0008;display:flex;flex-direction:column}.opt-drawer.open{transform:translateX(0)}.opt-body{padding:13px;overflow:auto}.opt-footer{margin-top:auto;padding:12px;border-top:1px solid var(--line);display:flex;justify-content:flex-end;gap:7px;background:#131518}.opt-progress{display:none;margin:12px 0}.candidate-area{display:none;margin-top:12px}.compare-box{display:none;margin-top:10px;border:1px solid #5b5031;background:#1b1914;padding:10px;border-radius:4px}.candidate-check{accent-color:var(--gold)}
.alert{position:fixed;right:18px;bottom:18px;z-index:80;width:360px;border:1px solid #675b38;background:#1d1b15;border-radius:5px;padding:11px 12px;box-shadow:0 10px 28px #0009;display:none}.alert.show{display:block}.alert-title{font-weight:800;color:#e6d59e}.alert-copy{font-size:12px;color:#b8b0a0;margin-top:3px}.alert-actions{display:flex;gap:6px;margin-top:9px}
.runtime{display:none;padding:14px;min-height:calc(100vh - 54px)}.runtime-panel{max-width:1240px;margin:auto}.runtime-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:12px;padding:13px}.status-strip{display:flex;align-items:center;gap:10px;padding:12px 13px;border-bottom:1px solid var(--line)}.status-pill{padding:3px 7px;border:1px solid var(--line2);border-radius:3px;color:var(--muted);font-size:11px}.status-pill.running{color:var(--green);border-color:#3d5d4d}.runtime-card{border:1px solid var(--line);background:#141619;border-radius:4px;padding:12px}.runtime-card h3{font-size:13px;margin:0 0 9px}.kv{display:grid;grid-template-columns:160px 1fr;gap:6px 10px;font-size:12px}.kv span:nth-child(odd){color:var(--muted)}.event-list{display:grid;gap:0}.event{display:grid;grid-template-columns:128px 90px 1fr;gap:8px;padding:8px 0;border-bottom:1px solid #25282c;font-size:11px}.event:last-child{border-bottom:0}.event time{font-family:var(--mono);color:#9299a1}.event b{font-family:var(--mono);font-weight:600}.event p{margin:0;color:#c5c9cd}
.notice{border:1px solid #454137;background:#191816;padding:9px 10px;color:#b8b2a8;border-radius:4px;font-size:12px}.reason{display:block;color:#8c939a;font-size:10px;margin-top:3px}.mobile-note{display:none}
@media(max-width:1050px){.workspace.layout-a{grid-template-columns:210px minmax(0,1fr)}.workspace.layout-b{display:block}.layout-b .settings-panel{position:static;max-height:none;margin-bottom:12px}.metrics{grid-template-columns:repeat(2,1fr)}.runtime-grid{grid-template-columns:1fr}.chart-wrap{height:290px}}
@media(max-width:760px){.workspace.layout-a{display:block}.layout-a .strategy-rail{display:none}.subnav{padding:0 9px;gap:7px}.toolbar-label,.mock-tag{display:none}.workspace{padding:8px}.result-topline{flex-wrap:wrap}.head-actions{margin-left:0;width:100%}.metrics{grid-template-columns:1fr 1fr}.chart-wrap{height:250px}.layout-a .settings-panel,.opt-drawer{width:min(94vw,520px)}.b-strategy-picker{display:flex!important}.mobile-note{display:block;color:var(--muted);font-size:11px}}
</style>
</head>
<body>
<div class="app">
  <header class="subnav">
    <nav class="nav-group" aria-label="量化交易區域">
      <button class="nav-btn active" data-view="research">策略研究</button>
      <button class="nav-btn" data-view="runtime">運行監控</button>
    </nav>
    <span class="mock-tag">示意資料</span>
    <div class="spacer"></div>
    <span class="toolbar-label">版型</span>
    <div class="segmented" aria-label="版型切換">
      <button id="layoutA" class="seg-btn active">A 曲線優先</button>
      <button id="layoutB" class="seg-btn">B 並排</button>
    </div>
    <span class="toolbar-label">結果狀態</span>
    <select id="resultStateSelect" class="toolbar-select" aria-label="示意結果狀態">
      <option value="complete">完成</option><option value="empty">空白</option><option value="running">執行中</option><option value="failed">失敗</option>
    </select>
  </header>

  <main id="researchView" class="workspace layout-a">
    <aside class="strategy-rail">
      <div class="rail-head"><div><div class="kicker">STRATEGIES</div><div class="title">策略清單</div></div><span class="mock-tag">2</span></div>
      <div class="strategy-list">
        <button class="strategy-card active" data-strategy="momentum"><div class="name">動能突破 15m</div><div class="meta">v1.2 · 已檢查 <span class="mini-badge">AI 工具</span></div></button>
        <button class="strategy-card" data-strategy="reversion"><div class="name">區間均值回歸</div><div class="meta">v0.7 · 草稿 <span class="mini-badge">手動</span></div></button>
      </div>
      <div class="settings-section"><div class="section-note">策略生命週期不受頁面切換影響。此原型不送單、不連交易所。</div></div>
    </aside>

    <aside id="settingsPanel" class="settings-panel">
      <div class="panel-head"><div><div class="kicker">RESEARCH CONFIG</div><div class="title">策略與研究設定</div></div><button class="btn small ghost drawer-close" id="closeSettings">關閉</button></div>
      <section class="settings-section">
        <div class="b-strategy-picker"><span class="toolbar-label">策略</span><select id="strategyPickerB" class="toolbar-select"><option value="momentum">動能突破 15m</option><option value="reversion">區間均值回歸</option></select></div>
        <div class="section-title">當前策略</div>
        <div style="display:flex;gap:6px;align-items:center;margin-bottom:9px"><b id="settingsStrategyName">動能突破 15m</b><span id="strategyStatusBadge" class="badge good">已檢查</span><span id="sourceBadge" class="badge">AI 工具</span></div>
        <div class="field full" style="margin-bottom:9px"><label>版本</label><select id="versionSelect"><option>v1.2</option><option>v1.1</option><option>v1.0</option></select></div>
        <ul class="rule-list" id="ruleList">
          <li>進場：收盤價突破近 20 根高點，且快線高於慢線。</li>
          <li>出場：收盤價跌破 10 根低點，或反向訊號成立。</li>
          <li>部位：單次僅持有一個方向；研究切片使用固定名目配置。</li>
        </ul>
      </section>
      <details>
        <summary>程式碼（預設收合）</summary>
        <div><pre class="code"><span class="kw">def</span> on_closed_bar(ctx, bar):
    fast = ctx.sma(12)
    slow = ctx.sma(36)
    breakout = bar.close &gt; ctx.highest(20)
    <span class="kw">if</span> breakout and fast &gt; slow:
        <span class="kw">return</span> TargetIntent("long")
    <span class="cm"># 示意程式碼，不執行</span></pre></div>
      </details>
      <section class="settings-section">
        <div class="section-title">研究設定</div>
        <div class="field-grid">
          <div class="field"><label>合約</label><select><option>BTC-USDT-SWAP</option></select></div>
          <div class="field"><label>週期</label><select><option>15m</option></select></div>
          <div class="field full"><label>資料集</label><select id="dataset"><option>OKX BTC 15m · 2025 H2</option><option>OKX BTC 15m · 2026 Q1</option></select><span class="range-note">涵蓋 2025-07-01 00:00 → 2025-12-31 23:45</span></div>
          <div class="field"><label>起始</label><input type="date" value="2025-07-01"></div>
          <div class="field"><label>結束</label><input type="date" value="2025-12-31"></div>
          <div class="field"><label>本金（USDT）</label><input class="dirty-input" data-param="capital" value="10000"></div>
          <div class="field"><label>預熱根數</label><input class="dirty-input" data-param="warmup" type="number" value="120"></div>
        </div>
      </section>
      <section class="settings-section">
        <div class="section-title">策略參數</div>
        <div class="field-grid">
          <div class="field"><label>快線 SMA</label><input id="fastParam" class="dirty-input" data-param="fast" type="number" value="12"></div>
          <div class="field"><label>慢線 SMA</label><input id="slowParam" class="dirty-input" data-param="slow" type="number" value="36"></div>
          <div class="field"><label>突破窗口（根）</label><input id="breakoutParam" class="dirty-input" data-param="breakout" type="number" value="20"></div>
          <div class="field"><label>出場窗口（根）</label><input class="dirty-input" data-param="exit" type="number" value="10"></div>
        </div>
      </section>
      <details>
        <summary>進階設定</summary>
        <div class="field-grid">
          <div class="field"><label>手續費（%）</label><input class="dirty-input" data-param="fee" value="0.05"></div>
          <div class="field"><label>滑價（bp）</label><input class="dirty-input" data-param="slippage" value="2"></div>
          <div class="field full"><label>成交模型</label><select class="dirty-input"><option>本根收盤決策 → 下一根開盤成交</option></select></div>
        </div>
      </details>
      <section class="settings-section">
        <div style="display:flex;gap:7px"><button id="runBacktest" class="btn primary" style="flex:1">執行回測</button><button id="openOptimization" class="btn" style="flex:1">參數優化</button></div>
        <div class="section-note" style="margin-top:8px">兩項操作皆為原型演示，只修改瀏覽器內 mock 狀態。</div>
      </section>
    </aside>

    <section class="results-panel">
      <div class="result-head">
        <div class="b-strategy-picker"><span class="toolbar-label">策略</span><select id="strategyPickerTop" class="toolbar-select"><option value="momentum">動能突破 15m</option><option value="reversion">區間均值回歸</option></select></div>
        <div class="result-topline">
          <div><div class="strategy-heading" id="resultStrategyName">動能突破 15m</div><div class="strategy-sub"><span id="resultVersion" class="mono">v1.2</span> · 已檢查 · 最後修改來源 <span id="resultSource">AI 工具</span></div></div>
          <span class="badge gold">研究結果</span><span class="badge">示意資料</span>
          <div class="head-actions"><button id="simulateAiUpdate" class="btn ghost">模擬 AI 更新策略</button><button id="openSettings" class="btn open-settings">研究設定</button><button id="runBacktestTop" class="btn primary">執行回測</button></div>
        </div>
        <div id="consistencyBanner" class="consistency hidden"><span class="dot"></span><b>設定已變更，尚未重跑</b><span>目前畫面仍顯示 Run #R-042 的舊結果，不會被覆蓋。</span></div>
      </div>
      <div class="result-body">
        <div id="completeState">
          <div class="chart-card">
            <div class="chart-head"><span class="chart-title">權益曲線</span><span id="chartRunLabel" class="chart-meta">RUN R-042 · 2025-07-01 → 2025-12-31</span><div class="chart-tabs"><button class="active" data-chart="equity">權益</button><button data-chart="drawdown">回撤</button></div></div>
            <div class="chart-wrap" id="chartWrap"><svg id="chartSvg" viewBox="0 0 900 280" preserveAspectRatio="none" aria-label="回測曲線"></svg><div id="chartTooltip" class="tooltip"></div></div>
          </div>
          <div class="metrics">
            <div class="metric"><div class="label">淨損益</div><div class="value positive">+1,842.60<span class="unit">USDT</span></div></div>
            <div class="metric"><div class="label">報酬率</div><div class="value positive">+18.43<span class="unit">%</span></div></div>
            <div class="metric"><div class="label">最大回撤</div><div class="value negative">-8.74<span class="unit">%</span></div></div>
            <div class="metric"><div class="label">成交筆數</div><div class="value">48<span class="unit">筆</span></div></div>
          </div>
          <div class="run-meta"><span>策略版本 <b id="metaVersion" class="mono">v1.2</b></span><span>資料區間 <b class="mono">2025-07-01 → 2025-12-31</b></span><span>參數 <b id="metaParams" class="mono">SMA 12/36 · breakout 20</b></span><span>執行時間 <b id="runTime" class="mono">2026-09-29 10:22:14</b></span><span>Sharpe <b>—</b><span class="reason">本研究切片未計算</span></span><div id="historyChips" class="history-chips"><span class="history-chip">R-041</span></div></div>
          <div class="tabs-row"><button class="tab active" data-tab="trades">成交明細</button><button class="tab" data-tab="logs">執行紀錄</button><button class="tab" data-tab="assumptions">設定與假設</button></div>
          <div id="trades" class="tab-panel active"><div class="table-wrap"><table id="tradeTable" class="data-table"><thead><tr><th data-key="time">時間 <span class="sort-arrow"></span></th><th data-key="side">方向</th><th data-key="entry">進場價</th><th data-key="exit">出場價</th><th data-key="qty">數量</th><th data-key="pnl">損益 USDT</th><th data-key="reason">出場原因</th></tr></thead><tbody></tbody></table></div></div>
          <div id="logs" class="tab-panel"><div class="table-wrap"><table class="data-table"><thead><tr><th>時間</th><th>階段</th><th>訊息</th></tr></thead><tbody><tr><td>10:22:14.028</td><td>prepare</td><td>載入 17,664 根已收盤 15m K 線</td></tr><tr><td>10:22:14.091</td><td>warmup</td><td>預熱 120 根，不執行交易決策</td></tr><tr><td>10:22:14.247</td><td>simulation</td><td>完成 48 筆模擬成交</td></tr><tr><td>10:22:14.251</td><td>complete</td><td>研究結果 R-042 已保留</td></tr></tbody></table></div></div>
          <div id="assumptions" class="tab-panel"><div class="notice">已收盤 K 線；下一根開盤加 2 bp 明示滑價成交；手續費 0.05%；預熱 120 根只更新指標。Sharpe 與樣本外結果未在本切片計算，因此顯示「—」，不視為 0。</div></div>
        </div>
        <div id="emptyState" class="empty-state"><div class="state-box"><div class="state-icon">[ ]</div><div class="state-title">尚無回測結果</div><div class="state-copy">設定已可執行。按「執行回測」會演示建立一份新的 mock 結果。</div><button class="btn primary state-run" style="margin-top:14px">執行回測</button></div></div>
        <div id="runningState" class="running-state"><div class="state-box"><div class="state-icon">···</div><div class="state-title">回測執行中</div><div class="state-copy mono" id="runningCopy">正在處理 15m closed bars · 62%</div><div class="progress"><span id="backtestProgress" style="width:62%"></span></div><div class="section-note">示意進度，不呼叫實際研究引擎。</div></div></div>
        <div id="failedState" class="failed-state"><div class="state-box"><div class="state-icon">!</div><div class="state-title">回測失敗</div><div class="state-copy">mock_data_gap：指定資料集在 2025-11-03 08:15 有缺口。舊結果仍保留，可修正設定後重跑。</div><button class="btn state-run" style="margin-top:14px">重新執行</button></div></div>
      </div>
    </section>
  </main>

  <section id="runtimeView" class="runtime">
    <div class="runtime-panel">
      <div class="status-strip"><div><div class="kicker">LOCAL SIMULATION</div><div class="title">運行監控</div></div><span id="runtimePill" class="status-pill">未啟動</span><span class="mock-tag">示意資料</span><div class="spacer"></div><button id="prepareSimulation" class="btn primary">準備模擬運行</button></div>
      <div class="runtime-grid">
        <div>
          <div class="runtime-card"><h3>固定運行上下文</h3><div class="kv"><span>策略版本</span><b id="runtimeVersion" class="mono">v1.2</b><span>研究結果</span><b id="runtimeRun" class="mono">R-042</b><span>合約 / 週期</span><b class="mono">BTC-USDT-SWAP / 15m</b><span>最後已收盤 K 線</span><b id="lastClosedBar" class="mono">—</b><span>目前訊號</span><b id="runtimeSignal">—</b><span>模擬持倉</span><b id="runtimePosition">—</b></div></div>
          <div class="runtime-card" style="margin-top:12px"><h3>風控狀態</h3><div class="kv"><span>模式</span><b>Local simulation</b><span>帳戶級風控</span><b id="riskState">未啟動</b><span>陌生部位 / 委託</span><b>無（示意）</b><span>實盤權限</span><b>未提供</b></div><div class="notice" style="margin-top:10px">研究結果只能準備本機模擬運行；此頁沒有一鍵轉實盤動作。</div></div>
        </div>
        <div class="runtime-card"><h3>事件紀錄</h3><div id="eventList" class="event-list"><div class="event"><time>10:22:14</time><b>RESEARCH</b><p>R-042 回測完成，可準備模擬運行。</p></div><div class="event"><time>10:18:03</time><b>VERSION</b><p>v1.2 已檢查；來源 AI 工具。</p></div></div></div>
      </div>
    </div>
  </section>
</div>

<aside id="optimizationDrawer" class="opt-drawer">
  <div class="panel-head"><div><div class="kicker">PARAMETER SEARCH</div><div class="title">參數優化</div></div><button id="closeOptimization" class="btn small ghost">關閉</button></div>
  <div class="opt-body">
    <div class="notice">示意搜尋。排名只是指定評分目標下的候選，不代表可獲利或可直接實盤。</div>
    <div class="settings-section" style="padding-left:0;padding-right:0"><div class="section-title">搜尋空間</div><div class="field-grid"><div class="field"><label>快線 SMA</label><input value="8 → 20"></div><div class="field"><label>慢線 SMA</label><input value="24 → 60"></div><div class="field"><label>突破窗口</label><input value="12 → 36"></div><div class="field"><label>搜尋次數</label><input id="trialCount" type="number" value="24"></div><div class="field full"><label>評分目標</label><select><option>報酬率 - 0.8 × 最大回撤</option><option>淨損益</option></select></div></div></div>
    <div style="display:flex;gap:7px"><button id="startOptimization" class="btn primary">開始示意優化</button><span class="badge warn">尚未樣本外驗證</span></div>
    <div id="optProgress" class="opt-progress"><div style="display:flex;justify-content:space-between"><b>搜尋進度</b><span id="optProgressLabel" class="mono">0 / 24</span></div><div class="progress"><span id="optProgressBar"></span></div></div>
    <div id="candidateArea" class="candidate-area"><div class="section-title">候選結果 <span class="section-note">最多選兩筆比較</span></div><div class="table-wrap"><table id="candidateTable" class="data-table" style="min-width:480px"><thead><tr><th>比較</th><th data-key="score">評分</th><th data-key="fast">快線</th><th data-key="slow">慢線</th><th data-key="ret">報酬率</th><th data-key="dd">最大回撤</th></tr></thead><tbody></tbody></table></div><div id="compareBox" class="compare-box"></div></div>
  </div>
  <div class="opt-footer"><button id="applyCandidate" class="btn primary" disabled>套用參數並重跑</button></div>
</aside>

<div id="aiAlert" class="alert"><div class="alert-title">AI 工具建立了新策略草稿</div><div class="alert-copy"><span id="newVersionLabel" class="mono">v1.3-draft</span> 已出現在版本清單。你目前查看的 R-042 與 v1.2 不會切換或消失。</div><div class="alert-actions"><button id="dismissAiAlert" class="btn small">留在目前結果</button><button id="switchNewVersion" class="btn small primary">切到新草稿</button></div></div>

<script>
const state={layout:'a',view:'research',result:'complete',strategy:'momentum',version:'v1.2',dirty:false,chart:'equity',runId:42,runHistory:[41],runtime:'idle',aiDraft:null,optSelected:[]};
const strategies={
 momentum:{name:'動能突破 15m',version:'v1.2',status:'已檢查',source:'AI 工具',rules:['進場：收盤價突破近 20 根高點，且快線高於慢線。','出場：收盤價跌破 10 根低點，或反向訊號成立。','部位：單次僅持有一個方向；研究切片使用固定名目配置。']},
 reversion:{name:'區間均值回歸',version:'v0.7',status:'草稿',source:'手動',rules:['進場：價格偏離 30 根中位區間後等待收盤確認。','出場：價格回到區間中線或風險條件成立。','部位：單方向模擬部位；不在同一根 K 線反向。']}
};
const equity=[10000,10080,10030,10190,10330,10260,10480,10610,10530,10790,11020,10910,11240,11160,11490,11320,11680,11590,11842.6];
const drawdown=[0,-.8,-1.3,-.4,0,-.7,0,0,-.75,0,0,-1.0,0,-.7,0,-1.5,0,-.8,0];
const trades=[
 {time:'2025-12-27 04:30',side:'LONG',entry:87240.1,exit:89118.4,qty:.012,pnl:21.93,reason:'exit window'},
 {time:'2025-12-19 17:45',side:'LONG',entry:85112.8,exit:86604.2,qty:.013,pnl:18.41,reason:'reverse signal'},
 {time:'2025-12-08 09:15',side:'SHORT',entry:92480.5,exit:90733.1,qty:.011,pnl:18.52,reason:'exit window'},
 {time:'2025-11-26 21:00',side:'LONG',entry:88402.0,exit:87511.6,qty:.012,pnl:-11.32,reason:'reverse signal'},
 {time:'2025-11-12 03:30',side:'LONG',entry:84620.7,exit:87190.3,qty:.013,pnl:32.67,reason:'exit window'},
 {time:'2025-10-30 14:45',side:'SHORT',entry:91005.3,exit:89762.9,qty:.011,pnl:12.94,reason:'exit window'}
];
const candidates=[
 {id:'C-07',score:14.92,fast:10,slow:42,breakout:24,ret:21.8,dd:-8.6},
 {id:'C-12',score:14.31,fast:12,slow:40,breakout:20,ret:20.1,dd:-7.2},
 {id:'C-03',score:13.74,fast:9,slow:36,breakout:28,ret:22.4,dd:-10.8},
 {id:'C-18',score:12.96,fast:14,slow:48,breakout:18,ret:18.7,dd:-7.1}
];
let tradeSort={key:'time',dir:-1},candidateSort={key:'score',dir:-1},runTimer=null,optTimer=null;

function postStatus(text){try{parent.postMessage({type:'catos-research-status',text},'*')}catch(e){}}
function setLayout(layout){state.layout=layout;const w=document.getElementById('researchView');w.classList.toggle('layout-a',layout==='a');w.classList.toggle('layout-b',layout==='b');w.classList.remove('settings-open');document.getElementById('layoutA').classList.toggle('active',layout==='a');document.getElementById('layoutB').classList.toggle('active',layout==='b');}
function setView(view){state.view=view;document.getElementById('researchView').style.display=view==='research'?(state.layout==='a'?'grid':'grid'):'none';document.getElementById('runtimeView').style.display=view==='runtime'?'block':'none';document.querySelectorAll('.nav-btn').forEach(b=>b.classList.toggle('active',b.dataset.view===view));}
function selectStrategy(key){state.strategy=key;const s=strategies[key];state.version=s.version;state.dirty=false;document.querySelectorAll('.strategy-card').forEach(b=>b.classList.toggle('active',b.dataset.strategy===key));['strategyPickerB','strategyPickerTop'].forEach(id=>document.getElementById(id).value=key);document.getElementById('settingsStrategyName').textContent=s.name;document.getElementById('resultStrategyName').textContent=s.name;document.getElementById('resultVersion').textContent=s.version;document.getElementById('metaVersion').textContent=s.version;document.getElementById('resultSource').textContent=s.source;document.getElementById('strategyStatusBadge').textContent=s.status;document.getElementById('strategyStatusBadge').className='badge '+(s.status==='已檢查'?'good':'warn');document.getElementById('sourceBadge').textContent=s.source;document.getElementById('ruleList').innerHTML=s.rules.map(x=>`<li>${x}</li>`).join('');const v=document.getElementById('versionSelect');v.innerHTML=key==='momentum'?'<option>v1.2</option><option>v1.1</option><option>v1.0</option>':'<option>v0.7</option><option>v0.6</option>';renderDirty();}
function renderDirty(){document.getElementById('consistencyBanner').classList.toggle('hidden',!state.dirty);}
function setDirty(){state.dirty=true;renderDirty();}
function setResult(result){state.result=result;['complete','empty','running','failed'].forEach(k=>document.getElementById(k+'State').style.display=k===result?(k==='complete'?'block':'flex'):'none');document.getElementById('resultStateSelect').value=result;postStatus(result==='running'?'回測執行中':result==='failed'?'回測失敗':result==='empty'?'尚無結果':'研究完成');}
function completeRun(){state.runId+=1;state.runHistory.unshift(state.runId-1);state.runHistory=state.runHistory.slice(0,4);state.dirty=false;setResult('complete');renderDirty();document.getElementById('chartRunLabel').textContent=`RUN R-${String(state.runId).padStart(3,'0')} · 2025-07-01 → 2025-12-31`;document.getElementById('runTime').textContent='2026-09-29 10:36:42';document.getElementById('metaVersion').textContent=state.version;document.getElementById('metaParams').textContent=`SMA ${document.getElementById('fastParam').value}/${document.getElementById('slowParam').value} · breakout ${document.getElementById('breakoutParam').value}`;document.getElementById('historyChips').innerHTML=state.runHistory.map(x=>`<span class="history-chip">R-${String(x).padStart(3,'0')}</span>`).join('');document.getElementById('runtimeRun').textContent=`R-${String(state.runId).padStart(3,'0')}`;renderChart();}
function runBacktest(){clearInterval(runTimer);setResult('running');let p=8;const bar=document.getElementById('backtestProgress'),copy=document.getElementById('runningCopy');bar.style.width=p+'%';runTimer=setInterval(()=>{p=Math.min(100,p+17);bar.style.width=p+'%';copy.textContent=`正在處理 15m closed bars · ${p}%`;if(p>=100){clearInterval(runTimer);setTimeout(completeRun,220)}},180)}
function renderChart(){const svg=document.getElementById('chartSvg');const values=state.chart==='equity'?equity:drawdown;const min=Math.min(...values),max=Math.max(...values);const pad=(max-min||1)*.12;const lo=min-pad,hi=max+pad;const W=900,H=280;const x=i=>35+i*(W-55)/(values.length-1);const y=v=>14+(hi-v)*(H-34)/(hi-lo);let grid='';for(let i=0;i<5;i++){const gy=20+i*58;grid+=`<line class="chart-grid" x1="35" x2="890" y1="${gy}" y2="${gy}"/>`};const pts=values.map((v,i)=>`${x(i)},${y(v)}`).join(' ');const path='M '+pts.replaceAll(' ',' L ');const fill=state.chart==='equity'?`${path} L ${x(values.length-1)},270 L 35,270 Z`:'';svg.innerHTML=`<defs><linearGradient id="equityFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#C6AA62" stop-opacity=".18"/><stop offset="100%" stop-color="#C6AA62" stop-opacity="0"/></linearGradient></defs>${grid}${fill?`<path class="chart-fill" d="${fill}"/>`:''}<path class="${state.chart==='equity'?'chart-line':'draw-line'}" d="${path}"/><line id="hoverLine" class="hover-line" x1="0" x2="0" y1="16" y2="270" style="display:none"/><circle id="hoverDot" class="hover-dot" r="4" style="display:none"/>`;}
function chartHover(ev){const wrap=document.getElementById('chartWrap'),rect=wrap.getBoundingClientRect(),svg=document.getElementById('chartSvg'),srect=svg.getBoundingClientRect();const rel=(ev.clientX-srect.left)/srect.width;const values=state.chart==='equity'?equity:drawdown;const i=Math.max(0,Math.min(values.length-1,Math.round(rel*(values.length-1))));const vx=35+i*(855)/(values.length-1);const min=Math.min(...values),max=Math.max(...values),pad=(max-min||1)*.12,lo=min-pad,hi=max+pad;const vy=14+(hi-values[i])*(246)/(hi-lo);svg.querySelector('#hoverLine').setAttribute('x1',vx);svg.querySelector('#hoverLine').setAttribute('x2',vx);svg.querySelector('#hoverLine').style.display='block';svg.querySelector('#hoverDot').setAttribute('cx',vx);svg.querySelector('#hoverDot').setAttribute('cy',vy);svg.querySelector('#hoverDot').style.display='block';const tip=document.getElementById('chartTooltip');tip.style.display='block';tip.style.left=Math.min(rect.width-165,Math.max(8,ev.clientX-rect.left+12))+'px';tip.style.top=Math.max(8,ev.clientY-rect.top-54)+'px';const month=String(7+Math.floor(i/3)).padStart(2,'0');tip.innerHTML=`<strong>${state.chart==='equity'?values[i].toFixed(2)+' USDT':values[i].toFixed(2)+'%'}</strong><span class="mono">2025-${month}-${String(3+(i*7)%27).padStart(2,'0')} 12:00</span>`;}
function chartLeave(){document.getElementById('chartTooltip').style.display='none';const a=document.getElementById('chartSvg').querySelector('#hoverLine'),b=document.getElementById('chartSvg').querySelector('#hoverDot');if(a)a.style.display='none';if(b)b.style.display='none';}
function renderTrades(){const rows=[...trades].sort((a,b)=>{const x=a[tradeSort.key],y=b[tradeSort.key];return (x<y?-1:x>y?1:0)*tradeSort.dir});document.querySelector('#tradeTable tbody').innerHTML=rows.map(r=>`<tr><td>${r.time}</td><td>${r.side}</td><td>${r.entry.toFixed(1)}</td><td>${r.exit.toFixed(1)}</td><td>${r.qty.toFixed(3)}</td><td class="${r.pnl>=0?'positive':'negative'}">${r.pnl>=0?'+':''}${r.pnl.toFixed(2)}</td><td>${r.reason}</td></tr>`).join('')}
function renderCandidates(){const rows=[...candidates].sort((a,b)=>(a[candidateSort.key]-b[candidateSort.key])*candidateSort.dir);document.querySelector('#candidateTable tbody').innerHTML=rows.map(r=>`<tr><td><input class="candidate-check" type="checkbox" data-id="${r.id}" ${state.optSelected.includes(r.id)?'checked':''}></td><td>${r.score.toFixed(2)}</td><td>${r.fast}</td><td>${r.slow}</td><td class="positive">+${r.ret.toFixed(1)}%</td><td class="negative">${r.dd.toFixed(1)}%</td></tr>`).join('');document.querySelectorAll('.candidate-check').forEach(c=>c.addEventListener('change',candidateToggle));}
function candidateToggle(ev){const id=ev.target.dataset.id;if(ev.target.checked){if(state.optSelected.length>=2){ev.target.checked=false;return}state.optSelected.push(id)}else state.optSelected=state.optSelected.filter(x=>x!==id);renderCompare()}
function renderCompare(){const box=document.getElementById('compareBox');box.style.display=state.optSelected.length?'block':'none';document.getElementById('applyCandidate').disabled=state.optSelected.length!==1;const rows=state.optSelected.map(id=>candidates.find(x=>x.id===id));box.innerHTML=rows.length?`<b>比較 ${rows.map(x=>x.id).join(' ↔ ')}</b><div class="section-note" style="margin-top:5px">${rows.map(x=>`${x.id}: SMA ${x.fast}/${x.slow} · 報酬率 +${x.ret}% · 回撤 ${x.dd}%`).join('<br>')}</div>${rows.length===2?'<div class="section-note" style="margin-top:6px">比較只呈現差異，不自動替你選定候選。</div>':''}`:'';}
function startOptimization(){clearInterval(optTimer);state.optSelected=[];renderCompare();document.getElementById('optProgress').style.display='block';document.getElementById('candidateArea').style.display='none';let n=0,total=Number(document.getElementById('trialCount').value)||24;optTimer=setInterval(()=>{n=Math.min(total,n+3);document.getElementById('optProgressLabel').textContent=`${n} / ${total}`;document.getElementById('optProgressBar').style.width=(n/total*100)+'%';if(n>=total){clearInterval(optTimer);document.getElementById('candidateArea').style.display='block';renderCandidates()}},140)}
function applyCandidate(){if(state.optSelected.length!==1)return;const c=candidates.find(x=>x.id===state.optSelected[0]);document.getElementById('fastParam').value=c.fast;document.getElementById('slowParam').value=c.slow;document.getElementById('breakoutParam').value=c.breakout;state.dirty=true;renderDirty();document.getElementById('optimizationDrawer').classList.remove('open');runBacktest()}
function simulateAi(){if(state.aiDraft){document.getElementById('aiAlert').classList.add('show');return}state.aiDraft='v1.3-draft';const sel=document.getElementById('versionSelect');sel.insertAdjacentHTML('afterbegin','<option>v1.3-draft</option>');sel.value=state.version;document.getElementById('newVersionLabel').textContent=state.aiDraft;document.getElementById('aiAlert').classList.add('show');postStatus('AI 新草稿待檢查')}
function switchAiDraft(){state.version=state.aiDraft;document.getElementById('versionSelect').value=state.version;document.getElementById('resultVersion').textContent=state.version;document.getElementById('strategyStatusBadge').textContent='草稿';document.getElementById('strategyStatusBadge').className='badge warn';state.dirty=true;renderDirty();document.getElementById('aiAlert').classList.remove('show')}
function prepareRuntime(){state.runtime=state.runtime==='idle'?'running':'idle';const running=state.runtime==='running';const pill=document.getElementById('runtimePill');pill.textContent=running?'本機模擬運行中':'未啟動';pill.classList.toggle('running',running);document.getElementById('prepareSimulation').textContent=running?'停止示意運行':'準備模擬運行';document.getElementById('lastClosedBar').textContent=running?'2026-09-29 10:15:00 +08:00':'—';document.getElementById('runtimeSignal').textContent=running?'LONG · 維持':'—';document.getElementById('runtimePosition').textContent=running?'BTC-USDT-SWAP +0.012 contracts（模擬）':'—';document.getElementById('riskState').textContent=running?'正常 · 無鎖存原因':'未啟動';if(running){document.getElementById('eventList').insertAdjacentHTML('afterbegin','<div class="event"><time>10:36:45</time><b>SIM START</b><p>以固定策略版本與 R-'+String(state.runId).padStart(3,'0')+' 準備本機模擬運行。</p></div>')}postStatus(running?'模擬運行中':'研究完成')}

document.getElementById('layoutA').onclick=()=>setLayout('a');document.getElementById('layoutB').onclick=()=>setLayout('b');
document.querySelectorAll('.nav-btn').forEach(b=>b.onclick=()=>setView(b.dataset.view));
document.querySelectorAll('.strategy-card').forEach(b=>b.onclick=()=>selectStrategy(b.dataset.strategy));
['strategyPickerB','strategyPickerTop'].forEach(id=>document.getElementById(id).onchange=e=>selectStrategy(e.target.value));
document.getElementById('resultStateSelect').onchange=e=>setResult(e.target.value);
document.querySelectorAll('.dirty-input').forEach(x=>x.addEventListener('input',setDirty));
document.getElementById('versionSelect').onchange=e=>{state.version=e.target.value;document.getElementById('resultVersion').textContent=state.version;setDirty()};
document.getElementById('openSettings').onclick=()=>document.getElementById('researchView').classList.add('settings-open');document.getElementById('closeSettings').onclick=()=>document.getElementById('researchView').classList.remove('settings-open');
['runBacktest','runBacktestTop'].forEach(id=>document.getElementById(id).onclick=runBacktest);document.querySelectorAll('.state-run').forEach(b=>b.onclick=runBacktest);
document.querySelectorAll('.chart-tabs button').forEach(b=>b.onclick=()=>{state.chart=b.dataset.chart;document.querySelectorAll('.chart-tabs button').forEach(x=>x.classList.toggle('active',x===b));document.querySelector('.chart-title').textContent=state.chart==='equity'?'權益曲線':'回撤曲線';renderChart()});
document.getElementById('chartWrap').addEventListener('mousemove',chartHover);document.getElementById('chartWrap').addEventListener('mouseleave',chartLeave);
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.tab-panel').forEach(p=>p.classList.toggle('active',p.id===b.dataset.tab))});
document.querySelectorAll('#tradeTable th[data-key]').forEach(th=>th.onclick=()=>{tradeSort.dir=tradeSort.key===th.dataset.key?-tradeSort.dir:-1;tradeSort.key=th.dataset.key;renderTrades()});
document.getElementById('openOptimization').onclick=()=>document.getElementById('optimizationDrawer').classList.add('open');document.getElementById('closeOptimization').onclick=()=>document.getElementById('optimizationDrawer').classList.remove('open');document.getElementById('startOptimization').onclick=startOptimization;document.getElementById('applyCandidate').onclick=applyCandidate;
document.querySelectorAll('#candidateTable th[data-key]').forEach(th=>th.onclick=()=>{candidateSort.dir=candidateSort.key===th.dataset.key?-candidateSort.dir:-1;candidateSort.key=th.dataset.key;renderCandidates()});
document.getElementById('simulateAiUpdate').onclick=simulateAi;document.getElementById('dismissAiAlert').onclick=()=>document.getElementById('aiAlert').classList.remove('show');document.getElementById('switchNewVersion').onclick=switchAiDraft;
document.getElementById('prepareSimulation').onclick=prepareRuntime;
renderTrades();renderChart();setResult('complete');selectStrategy('momentum');postStatus('研究完成');
</script>
</body></html>'''


def render_product_shell():
    return r'''<!doctype html>
<html lang="zh-Hant">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>catOS · Local Quant Workspace</title>
<style>
:root{color-scheme:dark;--bg:#0D0E10;--panel:#17191C;--line:#2A2D31;--text:#ECEFF2;--muted:#8F969E;--gold:#C6AA62;--green:#75B798;--sans:"Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif;--mono:Consolas,"SFMono-Regular",monospace}
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:var(--bg);color:var(--text);font:14px/1.4 var(--sans);overflow:hidden}body{display:grid;grid-template-rows:58px 1fr}.top{display:flex;align-items:center;border-bottom:1px solid var(--line);background:#101214;padding:0 18px;gap:17px}.brand{font-size:18px;font-weight:900;letter-spacing:.01em}.product-tabs{display:flex;height:100%;align-items:stretch}.product-tabs button{border:0;border-bottom:2px solid transparent;background:transparent;color:#959ca3;padding:0 18px;font-weight:800;cursor:pointer}.product-tabs button.active{color:#ead9a8;border-bottom-color:var(--gold);background:#17191c}.top-meta{display:flex;align-items:center;gap:14px;margin-left:auto}.meta-item{display:flex;flex-direction:column;gap:2px}.meta-label{color:#747b82;font-size:9px;letter-spacing:.08em}.meta-value{font-size:11px;font-weight:700}.mono{font-family:var(--mono)}.status{display:inline-flex;align-items:center;gap:5px}.status:before{content:"";width:6px;height:6px;border-radius:50%;background:var(--green)}.status.off:before{background:#777}.connect{height:29px;border:1px solid #42464b;background:#17191c;color:#d2d6da;border-radius:4px;padding:0 8px;cursor:pointer;font-size:11px}.mock{color:#a59d8c;border:1px solid #4d4639;border-radius:3px;padding:2px 6px;font-size:10px}.surface{width:100%;height:100%;border:0;background:var(--bg)}@media(max-width:900px){.top-meta .meta-item:first-child{display:none}.top{gap:8px}.product-tabs button{padding:0 10px}.mock{display:none}}
</style></head>
<body>
<header class="top"><div class="brand">catOS</div><nav class="product-tabs" aria-label="產品區域"><button id="quantTab" class="active" data-route="/quant">量化交易</button><button id="yaoziTab" data-route="/yaozi">Yaozi 情報</button></nav><span class="mock">示意資料</span><div class="top-meta"><div class="meta-item"><span class="meta-label">工作區</span><span class="meta-value mono">CatOS / localhost</span></div><div class="meta-item"><span class="meta-label">研究任務</span><span id="researchStatus" class="meta-value">研究完成</span></div><div class="meta-item"><span class="meta-label">AI 工具連線</span><span id="aiStatus" class="meta-value status">已連線（示意）</span></div><button id="aiToggle" class="connect">切換連線</button></div></header>
<iframe id="surface" class="surface" title="catOS surface" src="/quant"></iframe>
<script>
const frame=document.getElementById('surface');let connected=true;
function openSurface(route,key){frame.src=route;document.getElementById('quantTab').classList.toggle('active',key==='quant');document.getElementById('yaoziTab').classList.toggle('active',key==='yaozi');history.replaceState(null,'','#'+key)}
document.getElementById('quantTab').onclick=()=>openSurface('/quant','quant');document.getElementById('yaoziTab').onclick=()=>openSurface('/yaozi','yaozi');
document.getElementById('aiToggle').onclick=()=>{connected=!connected;const s=document.getElementById('aiStatus');s.textContent=connected?'已連線（示意）':'未連線（示意）';s.classList.toggle('off',!connected)};
window.addEventListener('message',e=>{if(e.data&&e.data.type==='catos-research-status')document.getElementById('researchStatus').textContent=e.data.text});
const initial=location.hash==='#yaozi'?['/yaozi','yaozi']:['/quant','quant'];openSurface(initial[0],initial[1]);
</script></body></html>'''


def render_yaozi_placeholder():
    return r'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Yaozi 情報</title><style>:root{color-scheme:dark}*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:#0D0E10;color:#ECEFF2;font:14px/1.5 "Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif}main{max-width:860px;margin:0 auto;padding:70px 28px}.tag{display:inline-block;border:1px solid #504838;color:#b6aa8b;padding:3px 7px;border-radius:3px;font-size:11px}.eyebrow{color:#C6AA62;font-size:11px;letter-spacing:.12em;margin-top:22px}h1{font-size:30px;margin:7px 0}p{color:#8F969E;max-width:650px}.panel{margin-top:24px;border:1px solid #2A2D31;background:#17191C;border-radius:5px;padding:18px}.line{height:1px;background:#2A2D31;margin:16px 0}.muted{color:#767e86}</style></head><body><main><span class="tag">示意資料</span><div class="eyebrow">YAOZI INTELLIGENCE</div><h1>Yaozi 情報</h1><p>本次原型只深入設計量化交易工作台。Yaozi 保留為同一 localhost 產品中的第二區域，不在此版本擴充情報操作。</p><div class="panel"><b>區域佔位</b><div class="line"></div><span class="muted">既有情報能力仍由原有 `/dashboard` 保留；此頁只示範頂層產品切換。</span></div></main></body></html>'''
