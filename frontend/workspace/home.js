/* Homepage comparison: existing research reader + bounded R4 evidence reader. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const raw = value => typeof value === 'string' ? value : '—';
  const count = value => Number.isSafeInteger(value) && value >= 0 ? value : '—';
  const validId = value => typeof value === 'string' && /^[0-9a-f]{32}$/.test(value);
  const labels = {running:'運行中',complete:'已完成',completed:'已完成',failed:'失敗',stopped:'已停止',queued:'排隊中',available:'已連線',partial:'資料不完整',stale:'資料過期',empty:'無資料',error:'讀取失敗',unavailable:'未接入'};
  const label = value => labels[value] || '待確認';
  const clock = value => {
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date.toLocaleTimeString('zh-TW', {timeZone:'Asia/Taipei',hour12:false}) : '—';
  };
  const state = {runs:[],runtime:null,result:null,selected:null,researchVersion:null,workspaceVersion:null,errors:{},busy:false,ticket:0,libraryFocus:null};
  const engine = window.WorkspaceEngine;
  const json = value => `<pre>${esc(JSON.stringify(value, null, 2))}</pre>`;
  const detail = (title, body) => {
    $('detail-title').textContent = title;
    $('detail-body').innerHTML = body;
    if (!$('detail-dialog').open) $('detail-dialog').showModal();
  };
  async function read(path) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(path, {cache:'no-store',signal:controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } finally { clearTimeout(timeout); }
  }
  function renderRuntime() {
    const runtime = state.runtime, status = runtime?.status || {}, manifest = runtime?.manifest || {};
    const available = runtime?.state === 'available';
    const anomaly = count(status.anomalies);
    const phase = runtime ? (available ? label(status.state) : label(runtime.state)) : (state.errors.runtime ? '讀取失敗' : '無執行記錄');
    $('runtime-badge').textContent = phase;
    $('runtime-badge').className = `badge badge-${available && status.state === 'running' ? 'green' : status.state === 'failed' || (typeof anomaly === 'number' && anomaly > 0) ? 'red' : 'amber'}`;
    $('runtime-progress').innerHTML = `${count(status.bars)} / ${count(manifest.bars)} <small>根訊號</small>`;
    $('runtime-summary').textContent = `合成成交 ${count(status.fills)} · 已記錄異常 ${anomaly}`;
    $('runtime-connection').textContent = runtime ? label(runtime.state) : state.errors.runtime ? '失敗' : '無資料';
    const monitor = $('monitor-status').parentElement;
    monitor.dataset.state = runtime?.state || (state.errors.runtime ? 'error' : 'empty');
    monitor.dataset.anomaly = String(typeof anomaly === 'number' && anomaly > 0);
    $('monitor-status').textContent = `R4 ${phase} · 已記錄異常 ${anomaly} · 風控未接入`;
    $('monitor-time').textContent = runtime ? `心跳 ${clock(status.heartbeat_at)}` : '—';
    if (!runtime) {
      $('runtime-queue').innerHTML = `<div class="empty">${esc(phase)}</div>`;
      $('event-stream').innerHTML = `<div class="empty">${esc(phase)}</div>`;
      return;
    }
    const progress = typeof status.bars === 'number' && typeof manifest.bars === 'number' && manifest.bars > 0 ? Math.min(100, status.bars / manifest.bars * 100) : 0;
    const signal = runtime.last_signal, fill = runtime.last_fill;
    const minutes = Number.isSafeInteger(manifest.worker_config?.timeframe_ms) ? manifest.worker_config.timeframe_ms / 60000 : '—';
    $('runtime-queue').innerHTML = `<button class="record-card" data-detail="runtime">
      <span class="record-heading"><strong>${esc(manifest.worker_config?.contract?.inst_id || 'R4')}</strong><span class="badge badge-gold">${esc(phase)}</span></span>
      <div class="record-sub">SMA · ${esc(minutes)}m · 本機合成<br>最後目標 ${esc(raw(signal?.target))} 張 · 訊號 ${esc(clock(signal?.wall_time))}</div>
      <div class="record-stats"><span>訊號 <b class="mono">${count(status.bars)} / ${count(manifest.bars)}</b></span><span>成交 <b class="mono">${count(status.fills)}</b></span></div>
      <div class="progress"><span style="width:${progress}%"></span></div></button>
      <div class="record-sub">最近成交 ${fill ? esc(fill.request?.side === 'buy' ? '買入' : fill.request?.side === 'sell' ? '賣出' : '方向待確認') + ' ' + esc(raw(fill.fill?.quantity)) + ' 張 @ ' + esc(raw(fill.fill?.price)) : '—'}<br>預計結束 ${esc(clock(status.expected_finish_at))}</div>`;
    const events = Array.isArray(runtime.events) ? runtime.events : [];
    // Keep anomalies in view even when the latest routine signals are more recent.
    const important = events.filter(event => event.kind === 'anomaly').slice(-3);
    const recent = [...new Set([...important, ...events.slice(-8)])].sort((a,b) => (b.line_number || 0) - (a.line_number || 0));
    $('event-stream').innerHTML = recent.length ? `<div class="timeline">${recent.map(event => {
      const index = events.indexOf(event);
      const title = event.kind === 'fill' ? `合成成交 · ${event.request?.side === 'buy' ? '買入' : event.request?.side === 'sell' ? '賣出' : '待確認'} ${raw(event.fill?.quantity)} 張`
        : event.kind === 'signal' ? `訊號 #${count(event.seq)} · 目標 ${raw(event.target)} 張`
        : event.kind === 'anomaly' ? '執行異常' : event.kind === 'started' ? 'R4 已開始' : label(event.kind);
      const summary = event.kind === 'fill' ? `成交價 ${raw(event.fill?.price)} · 費用 ${raw(event.fill?.fee)}`
        : event.kind === 'signal' ? (event.disposition === 'NO_CHANGE' ? '目標不變' : event.disposition === 'RESERVED_SIMULATION' ? '模擬額度已保留' : event.disposition || '—') : event.reason || event.message || event.kind;
      return `<div class="event-item ${esc(event.kind === 'anomaly' ? 'anomaly' : event.kind === 'fill' ? 'fill' : '')}"><button class="event-button" data-event="${index}"><span class="mono">${esc(clock(event.wall_time))}</span><span class="event-title">${esc(title)}</span></button><div class="event-detail">${esc(summary)}</div></div>`;
    }).join('')}</div>` : '<div class="empty">尚無事件</div>';
  }
  function renderRuns() {
    const runs = state.runs;
    const backtests = runs.filter(run => validId(run.run_id) && run.kind === 'backtest' && run.status === 'complete');
    if (!backtests.some(run => run.run_id === state.selected)) state.selected = backtests[0]?.run_id || null;
    $('chart-run').innerHTML = backtests.length ? backtests.map(run => `<option value="${run.run_id}">${esc(clock(run.created_at))} · SMA ${esc(count(run.request?.parameters?.period))}</option>`).join('') : '<option value="">無已保存回測</option>';
    $('chart-run').value = state.selected || '';
    $('chart-run').disabled = !backtests.length;
    $('research-queue').innerHTML = runs.length ? runs.slice(0,5).map(run => {
      if (!validId(run.run_id)) return '';
      const request = run.request?.backtest || run.request || {};
      return `<button class="record-card" data-run="${run.run_id}"><span class="record-heading"><strong>${run.kind === 'optimization' ? '參數搜尋' : 'SMA 回測'}</strong><span class="badge badge-${run.status === 'complete' ? 'green' : run.status === 'failed' ? 'red' : 'amber'}">${esc(label(run.status))}</span></span><span class="queue-row record-sub"><span>${run.kind === 'optimization' ? esc(count(run.request?.n_trials)) + ' 次試驗' : '週期 ' + esc(count(request.parameters?.period)) + ' · ' + esc(raw(request.parameters?.quantity)) + ' 張'}</span><span class="mono">${esc(clock(run.created_at))}</span></span></button>`;
    }).join('') : `<div class="empty">${state.errors.runs ? '研究讀取失敗' : '尚無研究任務'}</div>`;
  }
  function drawChart(payload) {
    const result = payload?.result, performance = result?.performance;
    $('report-link').hidden = !payload || !validId(payload.run_id);
    if (!$('report-link').hidden) $('report-link').href = `/api/research/runs/${payload.run_id}/report`;
    if (!performance || !Array.isArray(result.equity_curve) || !result.equity_curve.length) {
      $('chart-summary').textContent = state.errors.result ? '結果讀取失敗' : '尚無已保存回測';
      $('research-chart').innerHTML = '<div class="empty">研究曲線未提供</div>';
      $('chart-footer').textContent = '—';
      return;
    }
    $('chart-summary').innerHTML = `<span>淨損益 <strong class="mono ${raw(performance.net_pnl).startsWith('-') ? 'negative' : 'positive'}">${esc(raw(performance.net_pnl))}</strong> USDT</span><span>成交 <strong class="mono">${count(performance.trade_count)}</strong></span>`;
    $('chart-footer').textContent = `${count(result.warmup_bars)} 根預熱 · ${result.equity_curve.length} 根評估`;
    // Float is confined to derived SVG coordinates; all money labels use original strings.
    const points = result.equity_curve.map(point => ({value:Number(point.equity),raw:raw(point.equity),time:point.time_ms}));
    if (points.some(point => !Number.isFinite(point.value) || point.raw === '—')) {
      $('research-chart').innerHTML = '<div class="empty">曲線資料不完整</div>'; return;
    }
    const values = points.map(point => point.value), low = Math.min(...values), high = Math.max(...values), span = high - low || 1;
    const width = 760, height = 250, left = 20, right = 96, top = 18, bottom = 28;
    const x = index => left + index / Math.max(1, points.length - 1) * (width - left - right);
    const y = value => top + (high - value) / span * (height - top - bottom);
    const path = points.map((point,index) => `${index ? 'L' : 'M'}${x(index).toFixed(2)} ${y(point.value).toFixed(2)}`).join(' ');
    const area = `${path} L${x(points.length-1)} ${height-bottom} L${left} ${height-bottom} Z`;
    const highPoint = points.find(point => point.value === high), lowPoint = points.find(point => point.value === low), last = points[points.length-1];
    $('research-chart').innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="已保存合成回測權益曲線；初值 ${esc(points[0].raw)}，末值 ${esc(last.raw)} USDT"><defs><linearGradient id="equity-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#cfab4c" stop-opacity=".19"/><stop offset="100%" stop-color="#cfab4c" stop-opacity=".01"/></linearGradient></defs>${[0,.25,.5,.75,1].map(t => `<line x1="${left}" x2="${width-right}" y1="${top+t*(height-top-bottom)}" y2="${top+t*(height-top-bottom)}" stroke="#29303e" stroke-dasharray="3 4"/>`).join('')}<path d="${area}" fill="url(#equity-fill)"/><path d="${path}" fill="none" stroke="#cfab4c" stroke-width="1.8" vector-effect="non-scaling-stroke"/></svg><span class="chart-scale chart-high">${esc(highPoint.raw)}</span><span class="chart-scale chart-low">${esc(lowPoint.raw)}</span><span class="chart-scale chart-start">${esc(clock(points[0].time))}</span><span class="chart-scale chart-end">${esc(clock(last.time))}</span>`;
  }
  async function loadResult() {
    if (state.result?.run_id === state.selected) return;
    const id = state.selected, ticket = ++state.ticket;
    state.result = null; delete state.errors.result;
    if (!validId(id)) { drawChart(null); return; }
    $('chart-summary').textContent = '讀取已保存回測…';
    $('report-link').hidden = true;
    $('research-chart').innerHTML = '<div class="empty">讀取中</div>';
    try {
      const payload = await read(`/api/research/runs/${id}/result`);
      if (ticket !== state.ticket) return;
      if (payload.run_id !== id) throw new Error('result_run_mismatch');
      state.result = payload;
    } catch (error) {
      if (ticket !== state.ticket) return;
      state.errors.result = error.message;
    }
    drawChart(state.result);
  }
  async function refresh() {
    if (state.busy) return;
    state.busy = true; $('refresh').disabled = true;
    const keys = ['runs','researchVersion','workspaceVersion','runtime'];
    const paths = ['/api/research/runs','/api/research/version','/api/workspace/version','/api/workspace/local-sim/runs'];
    try {
      const replies = await Promise.allSettled(paths.map(read));
      for (let i = 0; i < replies.length; i++) {
        const key = keys[i], reply = replies[i];
        delete state.errors[key];
        if (reply.status === 'rejected') {
          state.errors[key] = reply.reason.message;
          if (key === 'runs') state.runs = [];
          else state[key] = null;
        } else if (key === 'runs') {
          state.runs = Array.isArray(reply.value.items) ? reply.value.items : [];
        } else if (key === 'runtime') {
          const runs = Array.isArray(reply.value.items) ? reply.value.items : [];
          const active = runs.filter(run => run.profile === 'eight-hour' && run.state === 'running');
          const run = active.length === 1 ? active[0] : active.length > 1 ? null : runs.find(run => run.profile === 'eight-hour');
          state.runtime = null;
          if (active.length > 1) state.errors.runtime = 'ambiguous_active_r4';
          else if (run && validId(run.run_id)) {
            try { state.runtime = await read(`/api/workspace/local-sim/runs/${run.run_id}`); }
            catch (error) { state.errors.runtime = error.message; }
          } else if (reply.value.state === 'error') state.errors.runtime = 'evidence_unavailable';
        } else state[key] = reply.value;
      }
      $('research-connection').textContent = state.researchVersion ? (state.researchVersion.restart_required ? '版本待更新' : '已連線') : '失敗';
      $('connection-label').textContent = Object.keys(state.errors).length ? '部分資料' : '已連線';
      renderRuntime(); renderRuns(); await loadResult();
    } finally { state.busy = false; $('refresh').disabled = false; }
  }
  function showDetail(kind) {
    if (kind === 'source') detail('資料來源與交付狀態', `<dl><dt>首頁範圍</dt><dd>Gemini 畫面、密度、導航與工作台操作；首頁方向已確認；策略、機器人、風控、日誌、情報與設定已展開。</dd><dt>資料</dt><dd>既有研究服務保存結果；R4 manifest／status／完整事件行的只讀快照。每 15 秒更新。</dd><dt>帳戶／風控</dt><dd>未接入；不將研究或合成權益冒充帳戶權益。</dd><dt>比較</dt><dd>Gemini／上一版為 2026-09-30 保存的畫面截圖，附互動版本入口。</dd><dt>驗收</dt><dd>首頁方向已由使用者確認；指定 5.6 Sol (Web) 獨立驗收待執行。R4 八小時結果未由此首頁驗收。</dd><dt>執行邊界</dt><dd>首頁只讀；版型、隱藏與頁面切換只改畫面。研究仍由原 8770 寫入。</dd></dl><details><summary>版本、來源與讀取問題</summary>${json({research:state.researchVersion,workspace:state.workspaceVersion,errors:state.errors})}</details>`);
    else if (kind === 'account') detail('帳戶與風控', '<p>帳戶快照、當日損益基準、有效槓桿、Soft／Hard 鎖存與未決責任尚未接入。</p><p>R4 為本機合成執行；研究回測結果另有標示，帳戶資料保持「—」。</p>');
    else if (kind === 'runtime') detail('R4 本機執行詳情', `<p>只讀合成執行記錄。心跳或零異常不代表 Worker 存活、帳戶風控正常或八小時驗收通過。</p>${json(state.runtime ? {...state.runtime,events:undefined} : {state:state.errors.runtime ? 'error' : 'empty',issue:state.errors.runtime})}`);
    else if (kind === 'research') detail('已保存回測詳情', state.result ? `<p>所有金額與百分比顯示原始 Decimal 字串；繪圖座標為衍生值。</p>${json({...state.result,result:{...state.result.result,equity_curve:undefined,trades:undefined}})}<a href="/api/research/runs/${state.result.run_id}/report" target="_blank" rel="noopener">開啟完整報告 ↗</a>` : '<p>尚無可讀取的回測結果。</p>');
  }
  function library(open) {
    if (open) {
      state.libraryFocus = document.activeElement;
      $('widget-library-panel').inert = false;
      engine.openWidgetLibrary();
      document.querySelector('[data-layout="close-library"]').focus();
    } else {
      engine.closeWidgetLibrary(); $('widget-library-panel').inert = true;
      state.libraryFocus?.focus();
    }
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.dataset.detail) showDetail(button.dataset.detail);
    if (button.hasAttribute('data-event')) {
      const item = state.runtime?.events?.[Number(button.dataset.event)];
      if (item) detail('事件原始記錄', json(item));
    }
    if (button.dataset.run) {
      const run = state.runs.find(item => item.run_id === button.dataset.run);
      if (run) detail(run.kind === 'optimization' ? '參數搜尋任務' : '回測任務', `${json(run)}${run.status === 'complete' ? `<a href="/api/research/runs/${run.run_id}/report" target="_blank" rel="noopener">開啟完整報告 ↗</a>` : ''}`);
    }
    if (button.dataset.preset) engine.applyPreset(button.dataset.preset);
    if (button.dataset.widget) engine.toggleMaximize(button.dataset.widget);
    if (button.dataset.hide) engine.hideWidget(button.dataset.hide);
    if (button.dataset.restore) engine.restoreWidget(button.dataset.restore);
    const action = button.dataset.layout;
    if (action === 'edit') engine.toggleEditing();
    if (action === 'pack') engine.autoPackGrid();
    if (action === 'undo') engine.revertLayout();
    if (action === 'reset') engine.resetLayout();
    if (action === 'library') library(true);
    if (action === 'close-library') library(false);
    if (button.dataset.compare) {
      library(false);
      const comparison = button.dataset.compare, live = comparison === 'live';
      $('live-page').hidden = !live; $('reference-page').hidden = live;
      document.querySelectorAll('[data-compare]').forEach(item => {item.classList.toggle('active',item === button);item.setAttribute('aria-pressed',String(item === button));});
      if (!live) {
        $('reference-image').src = `/workspace/reference/${comparison}`;
        $('reference-label').textContent = `${comparison === 'gemini' ? 'Gemini 原版' : '上一版 F1'} · 保存畫面（2026-09-30）`;
        $('reference-open').href = comparison === 'gemini' ? 'http://127.0.0.1:8791/' : '/workspace/#home';
      }
    }
  });
  $('widget-library-backdrop').addEventListener('click', () => library(false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && $('widget-library-panel').classList.contains('is-open')) {library(false);event.preventDefault();}
    else if (event.key === 'Escape' && engine.maximizedPaneId && !$('detail-dialog').open) engine.toggleMaximize(engine.maximizedPaneId);
    if (event.key === 'Tab' && $('widget-library-panel').classList.contains('is-open')) {
      const items = [...$('widget-library-panel').querySelectorAll('button:not(:disabled)')], first = items[0], last = items[items.length-1];
      if (event.shiftKey && document.activeElement === first) {last?.focus();event.preventDefault();}
      else if (!event.shiftKey && document.activeElement === last) {first?.focus();event.preventDefault();}
    }
  });
  $('detail-close').addEventListener('click', () => $('detail-dialog').close());
  $('refresh').addEventListener('click', refresh);
  $('chart-run').addEventListener('change', () => {state.selected = $('chart-run').value;loadResult();});
  engine.init('dashboard-tiling-workspace','home');
  refresh();
  setInterval(() => {if (!document.hidden) refresh();}, 15000);
})();
