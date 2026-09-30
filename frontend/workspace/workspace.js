/* F1: browser preferences and projections; research submits use the sole owner. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '尚未讀取').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const hex = value => typeof value === 'string' && /^[0-9a-f]{32}$/.test(value);
  const time = value => {
    if (value == null || value === '') return '尚未讀取';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '時間無效' : date.toLocaleString('zh-TW', {timeZone:'Asia/Taipei',hour12:false});
  };
  const states = {loading:'讀取中',available:'可讀取',empty:'尚無紀錄',partial:'部分資料／同步中',stale:'心跳過期',unavailable:'資料不可用',error:'讀取失敗'};
  const runStates = {running:'記錄為運行中',complete:'執行完成 · 尚須獨立驗收',completed:'執行完成 · 尚須獨立驗收',failed:'執行失敗',stopped:'已停止 · 不代表平倉'};
  const issueLabels = {incomplete_tail:'追加中的末行未納入',status_events_syncing:'status 與 events 計數尚未同步',heartbeat_over_120s:'心跳已超過 120 秒',heartbeat_in_future:'來源時間超前',evidence_not_ready:'證據尚未完整建立'};
  const pages = {
    home:['OPERATIONS','運行與異常','先看需處理的事件，再看當前執行。','監看預設'],
    research:['RESEARCH','策略研究','草稿、策略製品與保存結果分別追蹤。','研究預設'],
    execution:['RUNTIME','執行工作台','從已收盤訊號追查裁決、委託與模擬成交。','執行監看預設'],
    risk:['ACCOUNT & RISK','帳戶與風控','有效基準與責任尚未載入，保留不可判定。','資料邊界'],
    events:['EVENTS','事件紀錄','同一執行 run 的完整列；可查看原始事件。','事件檢視'],
    yaozi:['INTELLIGENCE','Yaozi 情報','共用網站；情報品質不改變策略生命週期。','情報工作區'],
    settings:['SYSTEM','系統與 Agent','服務版本與來源在需要時查看。','系統詳情']
  };
  const storageKey = 'catos_f1_workspace_v1';
  let preferences = {};
  try { preferences = JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch (_) { /* defaults */ }
  if (!preferences || typeof preferences !== 'object' || Array.isArray(preferences)) preferences = {};
  const layouts = preferences.layouts && typeof preferences.layouts === 'object' && !Array.isArray(preferences.layouts) ? preferences.layouts : {};
  let active = pages[location.hash.slice(1)] ? location.hash.slice(1) : 'home';
  let runId = hex(preferences.runId) ? preferences.runId : null;
  let runtime = {state:'loading'}, runtimeList = {state:'loading',items:[]};
  let researchVersion = null, workspaceVersion = null, catalog = null, catalogError = null;
  let researchRuns = [], researchError = null, selectedResearch = null, result = null, resultState = 'empty';
  let submitting = false, refreshing = false, researchRefreshing = false, resultTicket = 0, drawerFocus = null;
  const message = (id, text, bad=false) => { $(id).textContent=text; $(id).classList.toggle('error', bad); };
  const jsonDetail = data => `<pre class="content-json">${esc(JSON.stringify(data,null,2))}</pre>`;
  const rows = data => `<dl class="details">${data.map(([label,value]) => `<div><dt>${esc(label)}</dt><dd class="wrap">${esc(value)}</dd></div>`).join('')}</dl>`;
  const empty = text => `<div class="empty">${esc(text)}</div>`;
  function save() {
    try { localStorage.setItem(storageKey,JSON.stringify({layouts,runId,draft:readDraft(false)})); } catch (_) { /* optional preference persistence */ }
  }
  function layout() {
    const value = layouts[active] || {};
    return {split:Number.isFinite(value.split) && value.split>=50 && value.split<=70 ? value.split : 62,secondary:typeof value.secondary==='boolean' ? value.secondary : true};
  }
  function applyLayout() {
    const value=layout();
    document.documentElement.style.setProperty('--split',value.split+'%');
    $('split-range').value=String(value.split); $('split-value').textContent=value.split+'%';
    $('secondary-toggle').checked=value.secondary;
    document.querySelectorAll(`#view-${active} .secondary-panel`).forEach(panel => panel.classList.toggle('hidden',!value.secondary));
  }
  function collapse() {
    document.querySelectorAll('.panel.is-expanded').forEach(panel => { panel.classList.remove('is-expanded'); panel.querySelector('[data-expand]').textContent='放大面板'; });
    document.body.classList.remove('has-expanded');
  }
  function show(page) {
    if (!pages[page]) return;
    collapse(); active=page;
    document.querySelectorAll('.view').forEach(view => view.classList.toggle('active',view.id==='view-'+page));
    document.querySelectorAll('.nav [data-page]').forEach(button => button.classList.toggle('active',button.dataset.page===page));
    const [kicker,title,description,preset]=pages[page];
    $('page-kicker').textContent=kicker; $('page-title').textContent=title; $('page-description').textContent=description; $('preset-label').textContent=preset;
    $('quant-tab').classList.toggle('active',page!=='yaozi'); $('intel-tab').classList.toggle('active',page==='yaozi');
    $('workspace-tools').classList.toggle('hidden',!['home','research','execution'].includes(page));
    document.title='catOS · '+title; history.replaceState(null,'','#'+page); applyLayout();
  }
  async function api(path, options={}) {
    const controller=new AbortController(); const timeout=setTimeout(() => controller.abort(),6500);
    try {
      const response=await fetch(path,{cache:'no-store',credentials:'same-origin',...options,signal:controller.signal});
      const value=await response.json();
      if (!response.ok) throw new Error(typeof value.detail==='string' ? value.detail : JSON.stringify(value.detail));
      return value;
    } finally { clearTimeout(timeout); }
  }
  function researchEnabled() {
    const usable=!!catalog && !!researchVersion && !!workspaceVersion && !researchVersion.restart_required && !workspaceVersion.restart_required && !submitting && !researchVersion.active_run_id;
    $('submit-backtest').disabled=!usable; $('submit-optimization').disabled=!usable;
  }
  function eventSummary(event) {
    if (event.kind==='signal') return `訊號 #${event.seq} · 目標 ${event.target} 張 · ${event.disposition} · ${event.reason}`;
    if (event.kind==='fill') return `${event.fill.trade_id} · ${event.request.side} ${event.fill.quantity} 張 @${event.fill.price} · 費用 ${event.fill.fee} USDT · ${event.state}`;
    if (event.kind==='warmup') return `預熱 #${event.seq} · ${event.disposition} · 無交易意圖`;
    if (event.kind==='anomaly') return `異常 · ${event.reason || event.error || '查看原始事件'}`;
    return `${event.kind} · 查看原始證據`;
  }
  function timeline(events, detailed=false) {
    if (!events.length) return empty('這次讀取沒有完整事件列。');
    return `<ol class="timeline">${events.map(event => `<li><span class="time">${esc(time(event.wall_time))}</span><div class="wrap">${esc(eventSummary(event))}<small>完整列 #${event.line_number}${event.synthetic_time_ms ? ' · 合成時間 '+esc(time(event.synthetic_time_ms)) : ''}</small>${detailed ? `<button data-event="${event.line_number}">原始事件</button>` : ''}</div></li>`).join('')}</ol>`;
  }
  function renderRuntime() {
    const usable=!!runtime.status, status=runtime.status, manifest=runtime.manifest, events=runtime.events || [];
    $('connection-state').textContent=states[runtime.state] || '資料狀態未知';
    $('source-time').textContent=usable ? '心跳 '+time(status.heartbeat_at) : '心跳尚未讀取';
    $('anomaly-status').textContent=usable ? `所選 run 已記錄異常 ${status.anomalies} · ${states[runtime.state]}` : '執行異常尚未讀取 · '+(states[runtime.state] || '未知');
    $('source-note').textContent=usable ? `來源：${runtime.run_id} · 心跳 ${time(status.heartbeat_at)} · 本次讀取 ${time(runtime.observed_at)}（台灣時間） · 每 15 秒更新；資料不是市場報價。` : `R4 ${states[runtime.state] || '未知'}：${(runtime.issues || []).join('、') || '尚未取得證據'}。`;
    const limitations=`<div class="reason-row"><h3 class="alert">風控與未決責任不可判定</h3><p>未讀有效日基準、latch、在途與 UNKNOWN。不能依 anomalies=0 宣告可增倉。</p></div><div class="reason-row"><h3>Worker 即時存活尚未讀取</h3><p>status 是最後報告，不是程序探測；事件部位也不是目前完整帳戶。</p></div>`;
    $('visibility-body').innerHTML=`<div class="reason-row"><h3 class="${runtime.state==='available' ? '' : 'alert'}">${esc(states[runtime.state])}</h3><p>${esc((runtime.issues || []).map(issue => issueLabels[issue] || issue).join('；') || 'status／events 已完整讀取；仍非完整帳戶驗收。')}</p></div>`+limitations;
    if (!usable) {
      ['home-runtime-body','home-signals-body','execution-run-body','execution-fills-body','events-body'].forEach(id => $(id).innerHTML=empty(states[runtime.state]+' · 沒有可顯示的有效執行快照。'));
      return;
    }
    const signal=runtime.last_signal, planned=manifest.bars;
    const signalFill=signal ? events.find(event => event.kind==='fill' && event.seq===signal.seq) : null;
    $('home-runtime-body').innerHTML=`<div class="bot-title"><div><strong>SMA 趨勢</strong><p class="muted small">${esc(manifest.worker_config?.contract?.inst_id)} · 15m Closed Bar</p></div><span class="chip">${esc(runStates[status.state] || status.state)}</span></div>`+rows([
      ['固定策略版本',manifest.provenance?.strategy?.version],['最後正式訊號',signal ? `${time(signal.wall_time)} · 目標 ${signal.target} 張` : '尚無訊號'],['訊號進度',`${status.bars} / ${planned} 根 · 預熱 ${status.warmup_bars} 根`],['預計結束',time(status.expected_finish_at)]
    ])+`<div class="progress" aria-label="正式訊號進度"><span style="width:${Math.min(100,planned>0 ? status.bars/planned*100 : 0)}%"></span></div><p class="muted small">${esc(runtime.run_id)} · 此頁不判定 8h PASS。</p><div class="cluster"><button class="gold-btn" data-page="execution">查看執行工作台</button><button data-page="events">查看事件</button></div>`;
    $('home-signals-body').innerHTML=`<div class="stats">${[['正式訊號',status.bars],['模擬成交',status.fills],['已記錄異常',status.anomalies]].map(([label,value]) => `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`).join('')}</div>`+timeline(events.filter(event => ['signal','fill','anomaly'].includes(event.kind)).slice(-4).reverse());
    $('execution-run-body').innerHTML=rows([['執行 run',runtime.run_id],['正式訊號',`${status.bars} / ${planned}`],['來源心跳',time(status.heartbeat_at)],['完整事件列',`${runtime.complete_event_lines} · 最後 seq ${runtime.last_event_seq ?? '尚無'}`]])+(signal ? `<div class="steps"><div class="step">已收盤 K 線<span>${esc(time(signal.synthetic_time_ms))}</span></div><div class="step">目標 ${esc(signal.target)} 張<span>訊號 #${signal.seq}</span></div><div class="step">${esc(signal.disposition)}<span>${esc(signal.reason)}</span></div><div class="step">已記錄委託<span>${signalFill ? esc(signalFill.request.side)+' '+esc(signalFill.request.sz || signalFill.fill.quantity)+' 張' : '此次沒有成交事件證據'}</span></div><div class="step">同 seq 成交<span>${signalFill ? esc(signalFill.fill.trade_id)+' · '+esc(signalFill.state) : '尚無同 seq 成交'}</span></div></div><div class="notice">最後訊號決策前視圖：部位 ${esc(signal.account?.position)} 張；權益 ${esc(signal.account?.equity)} USDT。這是 ${esc(time(signal.wall_time))} 的合成記錄。</div>` : empty('尚無正式訊號。'));
    const fills=events.filter(event => event.kind==='fill');
    $('execution-fills-body').innerHTML=fills.length ? `<div class="table-wrap"><table><thead><tr><th>時間／seq</th><th>方向／張數</th><th>價格（USDT）</th><th>費用（USDT）</th><th>回報</th><th>成交後部位</th></tr></thead><tbody>${fills.map(event => `<tr><td>${esc(time(event.wall_time))} / ${event.seq}</td><td>${esc(event.request.side)} ${esc(event.fill.quantity)}</td><td class="num">${esc(event.fill.price)}</td><td class="num">${esc(event.fill.fee)}</td><td>${esc(event.state)}</td><td class="num">${esc(event.position)}</td></tr>`).join('')}</tbody></table></div><p class="muted small">合成價格；完整費用文字。每筆 request／固定 tag 可於事件詳情查看。成交後部位只屬該事件時點。</p>` : empty('尚未記錄完整模擬成交。');
    $('events-body').innerHTML=`<p class="run-meta">${esc(runtime.run_id)} · ${runtime.complete_event_lines} 完整列 · 本次顯示 ${events.length} 列／省略 ${runtime.events_omitted} 列。status 訊號 ${status.bars}；實讀 ${runtime.event_counts.signal}。截斷末行不納入。</p><div class="divider"></div>`+timeline([...events].reverse(),true);
  }
  async function refreshRuntime() {
    if (refreshing) return;
    refreshing=true; $('refresh').disabled=true; let changed=false;
    try {
      runtimeList=await api('/api/workspace/local-sim/runs');
      if (!runtimeList.items.some(item => item.run_id===runId)) runId=runtimeList.items.find(item => item.profile==='eight-hour' && item.state==='running')?.run_id || runtimeList.items[0]?.run_id || null;
      $('run-select').innerHTML=runtimeList.items.length ? runtimeList.items.map(item => `<option value="${esc(item.run_id)}">${esc(item.profile)} · ${esc(item.state)} · ${esc(item.run_id)}</option>`).join('') : '<option>尚無可讀執行 run</option>';
      if (runId) $('run-select').value=runId;
      const requested=runId;
      const value=requested ? await api('/api/workspace/local-sim/runs/'+requested) : {state:runtimeList.state,issues:runtimeList.issues?.map(issue => issue.reason || issue)};
      if (requested===runId) runtime=value; else changed=true;
      save();
    } catch (error) { runtime={state:'error',issues:[error.message]}; }
    finally { refreshing=false; $('refresh').disabled=false; renderRuntime(); if (changed) refreshRuntime(); }
  }
  function readDraft(validate=true) {
    const form=$('draft-form').elements;
    function integer(name) {
      const text=form.namedItem(name).value.trim();
      if (validate && !/^\d+$/.test(text)) throw new Error(`${name} 必須是整數`);
      return validate ? Number(text) : text;
    }
    return {strategy_id:form.strategy_id.value,dataset_id:form.dataset_id.value,parameters:{period:integer('period'),quantity:form.quantity.value.trim()},warmup_bars:integer('warmup_bars'),initial_balance:form.initial_balance.value.trim(),fee_rate:form.fee_rate.value.trim(),slippage_bps:form.slippage_bps.value.trim()};
  }
  function fillDraft(value) {
    if (!value?.parameters) return;
    const form=$('draft-form').elements;
    for (const name of ['strategy_id','dataset_id','warmup_bars','initial_balance','fee_rate','slippage_bps']) if (value[name]!=null) form.namedItem(name).value=String(value[name]);
    if (value.parameters.period!=null) form.period.value=String(value.parameters.period);
    if (value.parameters.quantity!=null) form.quantity.value=String(value.parameters.quantity);
  }
  function renderHistory() {
    $('research-history').innerHTML=researchError ? empty('研究紀錄讀取失敗：'+researchError) : researchRuns.length ? researchRuns.map(task => `<button class="task ${task.run_id===selectedResearch ? 'selected' : ''}" data-research="${esc(task.run_id)}">${task.kind==='optimization' ? '參數搜尋' : '合成回測'} · ${esc(task.status)}<span>${esc(time(task.created_at))} · ${esc(task.run_id)}</span><span>${esc(task.error || (task.request?.parameters ? `週期 ${task.request.parameters.period} · 目標 ${task.request.parameters.quantity} 張` : '設定保存於來源詳情'))}</span></button>`).join('') : empty('尚無研究紀錄。');
    const latest=researchRuns[0];
    $('recent-research').innerHTML=researchError ? empty('研究資料不可用') : latest ? `<button class="task" data-research="${esc(latest.run_id)}">${latest.kind==='optimization' ? '參數搜尋' : '合成回測'} · ${esc(latest.status)}<span>${esc(time(latest.created_at))}</span><span class="mono">${esc(latest.run_id)}</span></button>` : empty('尚無研究紀錄。');
  }
  function equityChart(points) {
    // Float conversion is solely a derived plotting coordinate. Account and
    // performance values are displayed from their Decimal strings unchanged.
    const data=points.map(point => Number(point.equity)).filter(Number.isFinite);
    if (data.length<2) return '';
    const low=Math.min(...data), high=Math.max(...data), spread=high-low || 1;
    const coords=data.map((value,index) => `${20+index/(data.length-1)*560},${150-(value-low)/spread*120}`).join(' ');
    return `<svg class="chart" viewBox="0 0 600 180" role="img" aria-label="研究權益曲線，僅衍生繪圖座標"><polyline points="${coords}"/><text x="20" y="174">研究期間 →</text></svg>`;
  }
  function renderResult() {
    if (resultState!=='available' || !result) { $('research-result-body').innerHTML=empty(states[resultState]+' · '+(result?.error || '選擇已保存研究紀錄。')); return; }
    const task=researchRuns.find(item => item.run_id===selectedResearch);
    const report=`<a href="/api/research/runs/${selectedResearch}/report" target="_blank" rel="noopener">開啟已保存報告 ↗</a>`;
    const source=`<p class="mono wrap small">${esc(result.run_id)}</p><details><summary>此結果的固定設定與來源</summary>${jsonDetail({request:result.request,provenance:result.provenance,build_id:result.build_id})}</details>`;
    if (result.kind==='optimization') {
      $('research-result-body').innerHTML=source+`<p class="muted small">樣本內搜尋 · ${esc(result.objective?.name)} · ${esc(result.objective?.direction)}。候選不更改 R4。</p><div class="table-wrap"><table><thead><tr><th>試驗</th><th>週期</th><th>評分（Decimal）</th><th>淨損益（USDT）</th><th>狀態</th><th>新草稿</th></tr></thead><tbody>${result.trials.map(trial => `<tr><td>${trial.number}</td><td>${esc(trial.params?.period)}</td><td class="num">${esc(trial.score_decimal)}</td><td class="num">${esc(trial.performance?.net_pnl)}</td><td>${esc(trial.state)}</td><td>${trial.state==='COMPLETE' ? `<button data-candidate="${trial.number}">帶入草稿</button>` : esc(trial.error)}</td></tr>`).join('')}</tbody></table></div>`+report;
      return;
    }
    const performance=result.result.performance;
    $('research-result-body').innerHTML=source+`<p class="muted small" id="result-settings">固定設定：週期 ${esc(result.request.parameters.period)} · 目標 ${esc(result.request.parameters.quantity)} 張 · 預熱 ${esc(result.request.warmup_bars)} · 初始研究權益 ${esc(result.request.initial_balance)} USDT</p><div class="result-grid">${[['淨損益（USDT）',performance.net_pnl],['期末權益（USDT）',performance.final_equity],['最大回撤（%）',performance.max_drawdown_pct],['模擬成交筆數',performance.trade_count],['手續費（USDT）',performance.fees],['報酬率（%）',performance.return_pct]].map(([label,value]) => `<div><span>${label}</span><strong class="${String(value).startsWith('-') ? 'loss' : ''}">${esc(value)}</strong></div>`).join('')}</div>`+equityChart(result.result.equity_curve)+`<details><summary>模擬成交（${performance.trade_count} 筆）</summary><div class="table-wrap"><table><thead><tr><th>合成時間</th><th>張數</th><th>價格（USDT）</th><th>費用（USDT）</th><th>成交後部位</th></tr></thead><tbody>${result.result.trades.map(trade => `<tr><td>${esc(time(trade.time_ms))}</td><td class="num">${esc(trade.quantity)}</td><td class="num">${esc(trade.price)}</td><td class="num">${esc(trade.fee)}</td><td class="num">${esc(trade.position_after)}</td></tr>`).join('')}</tbody></table></div></details><p class="muted small">${esc(result.data_notice)} · Closed Bar 決策／下一根開盤成交；期末不強制平倉。此結果不代表執行帳戶。</p>`+report;
  }
  async function selectResearch(id) {
    if (!hex(id)) return;
    selectedResearch=id; const ticket=++resultTicket; result=null; resultState='loading'; renderHistory(); renderResult();
    try {
      const task=await api('/api/research/runs/'+id);
      if (ticket!==resultTicket) return;
      if (task.status!=='complete') { result={error:`${task.status}${task.error ? ' · '+task.error : ''}`}; resultState=task.status==='failed' ? 'error' : 'partial'; }
      else { const value=await api('/api/research/runs/'+id+'/result'); if (ticket!==resultTicket) return; result=value; resultState='available'; }
    } catch (error) { if (ticket!==resultTicket) return; result={error:error.message}; resultState='error'; }
    renderResult();
  }
  function renderSystem() {
    $('settings-body').innerHTML=`<div class="reason-row"><h3>研究服務</h3><p>${researchVersion ? `PID ${researchVersion.pid} · ${researchVersion.restart_required ? '來源已變更，須重啟研究服務' : '服務版本一致'} · 任務 ${esc(researchVersion.active_run_id || '目前空閒')}` : '讀取失敗，研究提交不可用'}</p></div><div class="reason-row"><h3>工作台</h3><p>${workspaceVersion?.preview ? '8771 暫時預覽；研究請求仍交原 8770 唯一 writer。R4 程序獨立運行。' : '同一 FastAPI／ResearchService。'}${workspaceVersion?.restart_required ? ' 工作台 source 已變更，請重啟預覽程序。' : ''}</p><a href="/workspace/design" target="_blank" rel="noopener">開啟原設計樣稿 ↗</a></div><div class="reason-row"><h3>Agent / MCP</h3><p>沿用七個研究工具與同一任務紀錄。此處不宣告 Agent 即時連線。</p></div><details><summary>完整服務版本</summary>${jsonDetail({workspace:workspaceVersion,research:researchVersion,catalog_error:catalogError})}</details>`;
    $('yaozi-body').innerHTML=researchVersion?.market_status==='ready' && !workspaceVersion?.preview ? '<p>已物化情報來源；切頁不控制策略。</p><iframe class="intel" title="Yaozi 已物化情報" src="/dashboard"></iframe>' : empty('此工作台目前沒有接入可用的 Yaozi 情報畫面。既有研究服務來源：'+(researchVersion?.market_status || '尚未讀取')+'。情報缺資料不改變 R4。');
  }
  async function refreshResearch(initial=false) {
    if (researchRefreshing) return;
    researchRefreshing=true;
    const responses=await Promise.allSettled([api('/api/research/version'),api('/api/workspace/version'),api('/api/research/runs'),...(initial ? [api('/api/research/catalog')] : [])]);
    researchVersion=responses[0].status==='fulfilled' ? responses[0].value : null;
    workspaceVersion=responses[1].status==='fulfilled' ? responses[1].value : null;
    if (responses[2].status==='fulfilled') { researchRuns=responses[2].value.items; researchError=null; } else { researchRuns=[]; researchError=responses[2].reason.message; }
    if (initial) {
      if (responses[3].status==='fulfilled') {
        catalog=responses[3].value; catalogError=null;
        $('strategy-select').innerHTML=catalog.strategies.map(item => `<option value="${esc(item.id)}">${esc(item.name)} / ${esc(item.version)}</option>`).join('');
        $('dataset-select').innerHTML=catalog.datasets.map(item => `<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('');
        $('catalog-label').textContent='核可策略與資料來自 registry；無任意策略或上傳入口。';
        fillDraft(catalog.defaults); fillDraft(preferences.draft); save();
      } else { catalog=null; catalogError=responses[3].reason.message; $('catalog-label').textContent='registry 不可用：'+catalogError; }
    }
    renderHistory(); researchEnabled(); renderSystem(); researchRefreshing=false;
    if (!selectedResearch && researchRuns.length) await selectResearch(researchRuns.find(task => task.status==='complete')?.run_id || researchRuns[0].run_id);
    else if (selectedResearch && ['partial','loading'].includes(resultState)) await selectResearch(selectedResearch);
  }
  async function submit(kind) {
    if (submitting || !catalog || !researchVersion || !workspaceVersion || researchVersion.restart_required || workspaceVersion.restart_required || researchVersion.active_run_id) return;
    try {
      let request=readDraft();
      if (kind==='optimizations') {
        const form=$('optimization-form').elements;
        const integer=name => { const text=form.namedItem(name).value.trim(); if (!/^\d+$/.test(text)) throw new Error(name+' 必須是整數'); return Number(text); };
        request={backtest:request,search_space:{period:{low:integer('low'),high:integer('high'),step:integer('step')}},n_trials:integer('n_trials'),seed:integer('seed')};
      }
      submitting=true; researchEnabled(); message('submission-message','正在提交合成研究…');
      const task=await api('/api/research/'+kind,{method:'POST',headers:{'Content-Type':'application/json','X-CatOS-Build':researchVersion.build_id},body:JSON.stringify(request)});
      message('submission-message','已建立研究任務 '+task.run_id+'；R4 設定不變。'); $('draft-status').textContent='已提交快照 · 草稿可繼續修改';
      await refreshResearch(); await selectResearch(task.run_id);
    } catch (error) { message('submission-message','提交失敗：'+error.message,true); }
    finally { submitting=false; researchEnabled(); }
  }
  function drawer(data,title='來源與版本') {
    drawerFocus=document.activeElement; $('drawer-title').textContent=title; $('drawer-content').innerHTML=jsonDetail(data); $('drawer-backdrop').classList.add('open'); $('drawer-close').focus();
  }
  function closeDrawer() { $('drawer-backdrop').classList.remove('open'); drawerFocus?.focus(); }
  document.addEventListener('click',async event => {
    const button=event.target.closest('button'); if (!button) return;
    if (button.dataset.page) show(button.dataset.page);
    if (button.dataset.expand) { const panel=$(button.dataset.expand), was=panel.classList.contains('is-expanded'); collapse(); panel.classList.toggle('is-expanded',!was); document.body.classList.toggle('has-expanded',!was); button.textContent=was ? '放大面板' : '還原面板'; }
    if (button.dataset.research) { show('research'); await selectResearch(button.dataset.research); }
    if (button.dataset.candidate && result?.kind==='optimization') {
      const trial=result.trials.find(item => String(item.number)===button.dataset.candidate);
      if (trial?.state==='COMPLETE') { const draft=structuredClone(result.request.backtest); draft.parameters.period=trial.params.period; fillDraft(draft); $('draft-status').textContent='候選已帶入新草稿 · 保存結果不變'; save(); message('submission-message','提交新回測後才產生另一筆結果；未改 R4。'); }
    }
    if (button.dataset.event) { const record=runtime.events?.find(item => String(item.line_number)===button.dataset.event); if (record) drawer(record,'原始事件與時點'); }
    if (button.dataset.detail) drawer(button.dataset.detail==='runtime' ? {manifest:runtime.manifest,status:runtime.status,observed_at:runtime.observed_at,event_counts:runtime.event_counts,risk:runtime.risk,worker_alive:runtime.worker_alive} : {workspace:workspaceVersion,research:researchVersion,runtime_source:runtime.source,observed_at:runtime.observed_at,state:runtime.state,issues:runtime.issues});
  });
  $('split-range').addEventListener('input',event => { layouts[active]={...layout(),split:Number(event.target.value)}; applyLayout(); save(); });
  $('secondary-toggle').addEventListener('change',event => { layouts[active]={...layout(),secondary:event.target.checked}; applyLayout(); save(); });
  $('reset-layout').addEventListener('click',() => { layouts[active]={split:62,secondary:true}; collapse(); applyLayout(); save(); });
  $('reset-draft').addEventListener('click',() => { if (catalog) { fillDraft(catalog.defaults); $('draft-status').textContent='草稿 · 研究預設'; save(); } });
  $('draft-form').addEventListener('input',() => { $('draft-status').textContent='草稿已修改 · 保存結果不變'; save(); });
  $('draft-form').addEventListener('submit',event => { event.preventDefault(); submit('backtests'); });
  $('optimization-form').addEventListener('submit',event => { event.preventDefault(); submit('optimizations'); });
  $('run-select').addEventListener('change',event => { if (hex(event.target.value)) { runId=event.target.value; runtime={state:'loading'}; renderRuntime(); refreshRuntime(); } });
  $('refresh').addEventListener('click',() => { refreshRuntime(); refreshResearch(!catalog); });
  $('refresh-research').addEventListener('click',() => refreshResearch(!catalog));
  $('drawer-close').addEventListener('click',closeDrawer);
  $('drawer-backdrop').addEventListener('click',event => { if (event.target===$('drawer-backdrop')) closeDrawer(); });
  document.addEventListener('keydown',event => {
    if (event.key==='Escape') { closeDrawer(); collapse(); }
    if (event.key==='Tab' && $('drawer-backdrop').classList.contains('open')) { event.preventDefault(); $('drawer-close').focus(); }
  });
  window.addEventListener('hashchange',() => show(location.hash.slice(1)));
  new ResizeObserver(entries => document.documentElement.style.setProperty('--bar-height',entries[0].contentRect.height+24+'px')).observe(document.querySelector('.topbar'));
  show(active); renderRuntime(); refreshRuntime(); refreshResearch(true);
  setInterval(() => { if (!document.hidden) { refreshRuntime(); refreshResearch(!catalog); } },15000);
})();
