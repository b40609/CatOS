/* True research contracts and read-only local-sim evidence in the accepted shell. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const raw = value => typeof value === 'string' ? value : '—';
  const count = value => Number.isSafeInteger(value) && value >= 0 ? value : '—';
  const validId = value => typeof value === 'string' && /^[0-9a-f]{32}$/.test(value);
  const time = value => { const d = new Date(value); return Number.isFinite(d.getTime()) ? d.toLocaleString('zh-TW',{timeZone:'Asia/Taipei',hour12:false}) : '—'; };
  const labels = {running:'運行中',complete:'已完成',completed:'已完成',failed:'失敗',stopped:'已停止',queued:'排隊中',available:'已連線',partial:'資料不完整',stale:'資料過期',empty:'無資料',error:'讀取失敗',signal:'訊號',fill:'合成成交',warmup:'預熱',anomaly:'異常',started:'開始',finished:'結束'};
  const label = value => labels[value] || value || '—';
  const badge = (value, tone='ghost') => '<span class="badge badge-'+tone+'">'+esc(label(value))+'</span>';
  const button = (text, attr, style='plain') => '<button class="'+style+'" '+attr+'>'+esc(text)+'</button>';
  const empty = text => '<div class="block-state"><strong>'+esc(text)+'</strong></div>';
  const json = value => '<pre>'+esc(JSON.stringify(value,null,2))+'</pre>';
  const dl = pairs => '<dl class="detail-list">'+pairs.map(([k,v])=>'<dt>'+esc(k)+'</dt><dd>'+esc(v)+'</dd>').join('')+'</dl>';
  const table = (headers, rows) => '<div class="table-wrap"><table class="data-table"><thead><tr>'+headers.map(h=>'<th>'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.join('')+'</tbody></table></div>';
  const row = cells => '<tr>'+cells.map(c=>'<td>'+c+'</td>').join('')+'</tr>';
  const ids = ['kpi_grid','equity_chart','incident_timeline','active_bots','research_tasks','yaozi_brief'];
  const pages = {
    research:{title:'策略中心',en:'STRATEGY LAB',tiles:['研究概況','回測結果','研究歷史','成交明細','草稿設定','策略庫']},
    execution:{title:'機器人管理',en:'BOTS FLEET',tiles:['執行概況','本機執行隊列','執行檢視','訊號裁決','模擬成交','最近事件']},
    risk:{title:'風險控管',en:'RISK LATCH',tiles:['帳戶風控','風控快照','執行異常','曝險政策','日損政策','災難停損']},
    events:{title:'系統日誌',en:'AUDIT LOGS',tiles:['事件概況','事件紀錄','事件檢視','訊號記錄','成交記錄','讀取狀態']},
    yaozi:{title:'市場情報',en:'YAOZI INTEL',tiles:['情報概況','市場雷達','今日情報','關注標的','來源覆蓋','交易連動']},
    settings:{title:'系統設定',en:'CONFIGURATION',tiles:['連線概況','服務連線','介面偏好','工作台布局','Agent 研究介面','執行環境']}
  };
  const page = location.pathname.split('/').pop();
  if (!pages[page]) return;
  const config = pages[page], engine = window.WorkspaceEngine;
  const draftKey = 'catos_desk_research_draft_v1', preferenceKey = 'catos_desk_preferences_v1';
  const defaults = {strategy_id:'sma-trend',dataset_id:'synthetic-btc-15m-v1',parameters:{period:2,quantity:'2'},warmup_bars:2,initial_balance:'1000',fee_rate:'0.0005',slippage_bps:'2'};
  const searchDefaults = {low:2,high:8,step:1,n_trials:3,seed:42};
  const state = {runs:[],runtimeRuns:[],runtime:null,monitor:null,runtimeId:null,runtimeManual:false,runId:null,result:null,tab:'backtest',catalog:null,researchVersion:null,workspaceVersion:null,errors:{},busy:false,submitting:false,ticket:0,eventIndex:null,filter:'all',query:'',message:'',draft:structuredClone(defaults),search:{...searchDefaults},libraryFocus:null};
  function readLocal(key) { try { return JSON.parse(localStorage.getItem(key)||'null'); } catch { return null; } }
  function writeLocal(key,value) { try { localStorage.setItem(key,JSON.stringify(value)); } catch { state.errors.preferences='local_storage_unavailable'; } }
  const saved = readLocal(draftKey);
  if (saved?.draft?.strategy_id === defaults.strategy_id && saved.draft.dataset_id === defaults.dataset_id) {
    state.draft = {...defaults,...saved.draft,parameters:{...defaults.parameters,...saved.draft.parameters}};
    state.search = {...searchDefaults,...saved.search};
  }
  document.body.dataset.density = readLocal(preferenceKey)?.density === 'comfortable' ? 'comfortable' : 'dense';
  document.body.dataset.page = page;
  document.title = 'catOS｜'+config.title;
  $('page-title').textContent=config.title; $('page-en').textContent=config.en;
  document.querySelectorAll('.nav-item').forEach(a=>{const active=a.getAttribute('href')===location.pathname;a.classList.toggle('active',active);if(active)a.setAttribute('aria-current','page');});
  ids.forEach((id,i)=> {
    $('title-'+id).textContent=config.tiles[i]; $('en-'+id).textContent=i===0?'TELEMETRY':config.en;
    $('widget-'+id).setAttribute('aria-label',config.tiles[i]);
    const max=$('widget-'+id).querySelector('[data-widget]'); max.setAttribute('aria-label','放大'+config.tiles[i]);
    $('widget-'+id).querySelector('[data-hide]')?.setAttribute('aria-label','隱藏'+config.tiles[i]);
    Object.assign(engine.widgets[id],{title:config.tiles[i],en:config.en,desc:config.tiles[i]+'；依本頁資料來源顯示。'});
  });
  // Each page keeps its own layouts; homepage settings are untouched.
  const layouts = [
    {upperHeightPct:65,upperWidgets:[{id:'equity_chart',flex:72},{id:'incident_timeline',flex:28}],lowerWidgets:ids.slice(3).map(id=>({id,flex:1}))},
    {upperHeightPct:76,upperWidgets:[{id:'equity_chart',flex:82},{id:'research_tasks',flex:18}],lowerWidgets:[{id:'active_bots',flex:1},{id:'yaozi_brief',flex:1},{id:'incident_timeline',flex:1}]},
    {upperHeightPct:56,upperWidgets:[{id:'equity_chart',flex:1},{id:'incident_timeline',flex:1}],lowerWidgets:ids.slice(3).map(id=>({id,flex:1}))}
  ];
  ['executive','research','sentinel'].forEach((key,i)=>engine.presets[key].splits=layouts[i]);
  engine.init('dashboard-tiling-workspace','desk_'+page);
  const body = (index,html) => { $('body-'+ids[index]).innerHTML=html; };
  function metrics(items) { body(0,'<div class="metric-strip">'+items.map(([k,v,n])=>'<div class="metric"><label>'+esc(k)+'</label><strong>'+esc(v)+'</strong><small>'+esc(n||'')+'</small></div>').join('')+'</div>'); }
  function detail(title,html) { $('detail-title').textContent=title;$('detail-body').innerHTML=html;if(!$('detail-dialog').open)$('detail-dialog').showModal(); }
  async function request(path, options={}) {
    const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),8000);
    try {
      const response=await fetch(path,{cache:'no-store',...options,signal:controller.signal});
      const data=await response.json();
      if(!response.ok) throw new Error(typeof data.detail==='string'?data.detail:'HTTP '+response.status);
      return data;
    } finally {clearTimeout(timer);}
  }
  function gate() {
    if(state.submitting)return '提交中';
    if(!state.catalog||!state.researchVersion||!state.workspaceVersion)return '服務未連線';
    if(state.researchVersion.restart_required||state.workspaceVersion.restart_required)return '服務版本待更新';
    if(state.researchVersion.active_run_id)return '研究服務忙碌';
    return '';
  }
  function updateGate() {
    const reason=gate();
    document.querySelectorAll('[data-submit]').forEach(b=>{b.disabled=!!reason;b.title=reason;});
    const note=$('submit-status');if(note)note.textContent=state.message||reason||'可提交合成研究';
  }
  function controls() {
    if(page==='research') {
      $('page-controls').innerHTML='<div role="group" aria-label="研究分頁">'+[['strategy','策略'],['backtest','回測'],['optimization','參數優化']].map(([key,name])=>button(name,'data-tab="'+key+'" aria-pressed="'+(state.tab===key)+'"','tab-button'+(state.tab===key?' active':''))).join('')+'</div><div class="controls-end"><span id="submit-status" class="row-note"></span>'+button('研究設定','data-action="draft"')+button('執行回測','data-submit="backtest"','gold-button')+button('參數搜尋','data-submit="optimization"','gold-button')+'</div>';
    } else if(page==='execution'||page==='events') {
      $('page-controls').innerHTML='<div class="filter-bar"><label for="runtime-select">執行記錄</label><select id="runtime-select" aria-label="選擇執行記錄"></select>'+
      (page==='events'?'<select id="event-filter" aria-label="事件類型"><option value="all">全部事件</option><option value="signal">訊號</option><option value="fill">成交</option><option value="anomaly">異常</option><option value="warmup">預熱</option></select><input id="event-query" aria-label="搜尋事件" placeholder="搜尋目標、裁決、原因">':'')+'</div><div class="controls-end">'+badge('本機合成','amber')+button('執行詳情','data-detail="runtime"')+(page==='execution'?badge('啟停未接入'):'')+'</div>';
    } else {
      $('page-controls').innerHTML='<span class="eyebrow">'+esc(config.en)+' //</span><div class="controls-end">'+badge(page==='risk'?'帳戶快照未接入':page==='yaozi'?'情報未接入':'本機偏好')+button('資料詳情','data-detail="source"')+'</div>';
    }
    updateGate();
  }
  controls();
  function drawCurve(points) {
    if(!Array.isArray(points)||!points.length)return empty('曲線未提供');
    // Numbers are derived drawing coordinates only; labels and accounting stay Decimal strings.
    const values=points.map(p=>Number(p.equity));
    if(values.some(v=>!Number.isFinite(v))||points.some(p=>typeof p.equity!=='string'))return empty('曲線資料不完整');
    const low=Math.min(...values),high=Math.max(...values),span=high-low||1;
    const line=values.map((v,i)=>(i?'L':'M')+(20+i/Math.max(1,values.length-1)*700).toFixed(2)+' '+(12+(high-v)/span*172).toFixed(2)).join(' ');
    return '<div class="result-chart"><svg viewBox="0 0 760 210" preserveAspectRatio="none" role="img" aria-label="合成研究權益曲線；末值 '+esc(points.at(-1).equity)+' USDT">'+[12,55,98,141,184].map(y=>'<line x1="20" x2="720" y1="'+y+'" y2="'+y+'" stroke="#29303e" stroke-dasharray="3 4"/>').join('')+'<path d="'+line+'" fill="none" stroke="#cfab4c" stroke-width="1.8" vector-effect="non-scaling-stroke"/></svg></div>';
  }
  function strategyCard() {
    return '<div class="strategy-card"><h3>SMA 趨勢策略</h3><div class="tags">'+badge('已核可','green')+badge('Long / Flat')+badge('Closed Bar')+'</div><p>以均線產生持有／空倉目標；本根收盤決策，下一根開盤加明示滑價成交。</p>'+dl([['合約／週期','BTC-USDT-SWAP · 15m'],['資料','固定合成已收盤 K 線'],['參數','均線週期、委託張數']])+'<div class="source-link">'+button('開啟回測','data-tab="backtest"','gold-button')+' '+button('策略詳情','data-detail="strategy"')+'</div></div>';
  }
  function renderResearch() {
    const backtests=state.runs.filter(r=>r.kind==='backtest'&&r.status==='complete').length;
    const optimizations=state.runs.filter(r=>r.kind==='optimization'&&r.status==='complete').length;
    metrics([['核可策略',state.catalog?state.catalog.strategies.length:'—','策略庫'],['已保存回測',backtests,'合成研究'],['參數搜尋',optimizations,'已完成'],['研究服務',gate()||'可用','單一任務']]);
    const kind=state.tab==='optimization'?'optimization':'backtest';
    const history=state.runs.filter(r=>state.tab==='strategy'||r.kind===kind);
    body(2,history.length?table(['任務','狀態','時間'],history.map(r=>'<tr class="'+(r.run_id===state.runId?'selected':'')+'"><td>'+button(r.kind==='optimization'?'參數搜尋':'SMA '+count(r.request?.parameters?.period),'data-run="'+esc(r.run_id)+'"')+'</td><td>'+badge(r.status,r.status==='complete'?'green':r.status==='failed'?'red':'amber')+'</td><td class="mono">'+esc(time(r.created_at).split(' ')[1]||time(r.created_at))+'</td></tr>')):empty(state.errors.runs?'研究讀取失敗':'尚無研究任務'));
    body(4,'<div class="section-line"><span>下一次提交</span>'+button('編輯','data-action="draft"')+'</div>'+dl([['均線週期',state.draft.parameters.period],['委託張數',raw(state.draft.parameters.quantity)],['預熱根數',state.draft.warmup_bars],['初始權益',raw(state.draft.initial_balance)+' USDT'],['手續費率',raw(state.draft.fee_rate)],['滑價',raw(state.draft.slippage_bps)+' bps']])+'<p class="row-note">草稿獨立保存；不改變已保存結果或 R4。</p>');
    body(5,state.catalog?strategyCard():empty('策略庫未連線'));
    $('title-equity_chart').textContent=state.tab==='strategy'?'策略工作區':state.tab==='optimization'?'參數優化結果':'回測結果';
    if(state.tab==='strategy') {body(1,state.catalog?strategyCard():empty('策略庫未連線'));body(3,dl([['回測','下一根開盤成交'],['預熱','僅更新指標'],['資金費','合成模型為零'],['用途','研究與本機模擬']])+'<a class="source-link" href="#" data-strategy-detail>查看模型與製品詳情 →</a>');updateGate();return;}
    const run=state.runs.find(r=>r.run_id===state.runId), result=state.result;
    if(!result||run?.kind!==kind) {
      body(1,empty(run?label(run.status):state.errors.result?'結果讀取失敗':'選擇已保存結果'));
      if(run?.error)body(1,empty('研究失敗')+button('查看錯誤','data-detail="task"'));
      body(3,empty(kind==='optimization'?'候選尚未提供':'成交尚未提供'));updateGate();return;
    }
    const fixed=result.request?.backtest||result.request;
    const heading='<div class="section-line"><span>已保存 · '+esc(result.run_id.slice(0,8))+' · 預熱 '+esc(count(fixed?.warmup_bars))+' 根</span>'+button('設定與來源','data-detail="result"')+'</div>';
    if(kind==='backtest') {
      const perf=result.result?.performance||{},trades=result.result?.trades||[];
      body(1,heading+'<div class="result-metrics">'+[['淨損益 USDT',perf.net_pnl],['最終權益 USDT',perf.final_equity],['最大回撤 %',perf.max_drawdown_pct],['成交數',count(perf.trade_count)]].map(([k,v])=>'<span>'+esc(k)+'<b>'+esc(typeof v==='number'?v:raw(v))+'</b></span>').join('')+'</div>'+drawCurve(result.result?.equity_curve)+'<div class="chart-footer"><span>合成研究 · SMA '+esc(count(fixed?.parameters?.period))+'</span><a href="/api/research/runs/'+result.run_id+'/report" target="_blank" rel="noopener">完整報告 ↗</a></div>');
      body(3,trades.length?table(['時間','張數','成交價','費用 USDT','成交後部位'],trades.map(t=>row([esc(time(t.time_ms)),esc(raw(t.quantity)),esc(raw(t.price)),esc(raw(t.fee)),esc(raw(t.position_after))]))):empty('無成交'));
    } else {
      const trials=Array.isArray(result.trials)?result.trials:[];
      body(1,heading+'<div class="section-line"><span>目標 '+esc(result.objective?.name)+' · '+esc(result.objective?.direction)+'</span><a href="/api/research/runs/'+result.run_id+'/report" target="_blank" rel="noopener">完整報告 ↗</a></div>'+table(['試驗','SMA 週期','搜尋分數','淨損益 USDT','狀態','操作'],trials.map(t=>row([esc(t.number),esc(count(t.params?.period)),esc(raw(t.score_decimal)),esc(raw(t.performance?.net_pnl)),badge(t.state),t.state==='COMPLETE'?button('帶入草稿','data-candidate="'+esc(t.number)+'"'):button('詳情','data-trial="'+esc(t.number)+'"')]))));
      body(3,'<div class="draft-summary">已保存搜尋：'+esc(count(result.request?.n_trials))+' 次試驗<br>目前新草稿 SMA <b>'+esc(state.draft.parameters.period)+'</b><br>候選帶入後可開啟設定比較，再提交新回測。</div>'+button('開啟草稿設定','data-action="draft"','gold-button'));
    }
    updateGate();
  }
  function runtimePhase(runtime=state.runtime) {return runtime?.state==='available'?label(runtime.status?.state):runtime?label(runtime.state):'資料未提供';}
  function eventRows(events, type=null) {
    return events.filter(e=>!type||e.kind===type).slice().reverse().map(e=>row([esc(time(e.wall_time)),button(label(e.kind)+' #'+(e.seq??'—'),'data-event="'+state.runtime.events.indexOf(e)+'"'),esc(e.kind==='signal'?raw(e.target):e.kind==='fill'?raw(e.fill?.quantity):e.reason||e.kind),esc(e.disposition||e.request?.side||e.message||'—')]));
  }
  function runtimeDetail() {
    const r=state.runtime,m=r?.manifest,s=r?.status;
    return r?dl([['合約',m?.worker_config?.contract?.inst_id],['策略','SMA · 本機合成'],['正式訊號',count(s?.bars)+' / '+count(m?.bars)],['預熱',count(s?.warmup_bars)+' 根'],['合成成交',count(s?.fills)],['記錄異常',count(s?.anomalies)],['心跳',time(s?.heartbeat_at)],['預計結束',time(s?.expected_finish_at)],['Worker 存活','未提供'],['帳戶風控','未接入']])+button('完整記錄','data-detail="runtime"'):empty(runtimePhase());
  }
  function runtimeMetrics() {const s=state.runtime?.status,m=state.runtime?.manifest;metrics([['執行狀態',runtimePhase(),'R4 · 本機合成'],['正式訊號',count(s?.bars)+' / '+count(m?.bars),'不含預熱'],['合成成交',count(s?.fills),'FakeExchange'],['已記錄異常',count(s?.anomalies),'不代表帳戶風控']]);}
  function renderExecution() {
    runtimeMetrics();
    body(1,state.runtimeRuns.length?table(['執行','合約','狀態','進度','查看'],state.runtimeRuns.map(r=>'<tr class="'+(r.run_id===state.runtimeId?'selected':'')+'"><td class="mono">'+esc(r.run_id.slice(0,8))+'</td><td>BTC-USDT-SWAP</td><td>'+badge(r.state,r.state==='running'?'green':'ghost')+'</td><td>'+esc(count(r.bars))+'</td><td>'+button('檢視','data-runtime="'+esc(r.run_id)+'"')+'</td></tr>')):empty('無執行記錄'));
    body(2,runtimeDetail());
    const r=state.runtime,signal=r?.last_signal,fill=r?.last_fill,events=r?.events||[];
    body(3,signal?'<div class="flow-step"><small>Closed Bar → 訊號</small>目標 <b>'+esc(raw(signal.target))+'</b> 張</div><div class="flow-step"><small>Supervisor 裁決</small>'+esc(signal.disposition)+'<br>'+esc(signal.reason||'—')+'</div><div class="flow-step"><small>決策前部位</small><b>'+esc(raw(signal.account?.position))+'</b> 張</div>'+button('訊號詳情','data-event="'+events.findIndex(e=>e.line_number===signal.line_number)+'"'):empty('尚無訊號'));
    body(4,fill?dl([['方向',fill.request?.side],['張數',raw(fill.fill?.quantity)],['成交價',raw(fill.fill?.price)],['費用 USDT',raw(fill.fill?.fee)],['成交後部位',raw(fill.position)],['時間',time(fill.wall_time)]]):empty('尚無模擬成交'));
    body(5,events.length?table(['時間','事件','內容','裁決'],eventRows(events.slice(-8))):empty('尚無事件'));
  }
  function selectedEvent() {return state.runtime?.events?.[state.eventIndex];}
  function renderEvents() {
    const r=state.runtime,events=r?.events||[],counts=r?.event_counts||{};
    metrics([['完整事件行',count(r?.complete_event_lines),'此執行記錄'],['訊號',count(counts.signal),'已記錄'],['成交',count(counts.fill),'已記錄'],['異常',count(counts.anomaly),'已記錄']]);
    const matching=events.filter(e=>(state.filter==='all'||e.kind===state.filter)&&(!state.query||JSON.stringify(e).toLowerCase().includes(state.query.toLowerCase())));
    body(1,'<div class="section-line"><span>'+matching.length+' / '+events.length+' 筆載入事件</span><span>最新在上</span></div>'+(matching.length?table(['時間','事件','目標／張數','裁決／原因'],eventRows(matching)):empty(r?'無符合事件':runtimePhase())));
    const e=selectedEvent();body(2,e?dl([['類型',label(e.kind)],['行號',count(e.line_number)],['序號',count(e.seq)],['時間',time(e.wall_time)],['裁決',e.disposition||'—'],['原因',e.reason||'—']])+button('原始記錄','data-event="'+state.eventIndex+'"'):empty('點選事件查看'));
    body(3,events.some(e=>e.kind==='signal')?table(['時間','事件','目標','裁決'],eventRows(events,'signal')):empty('尚無訊號'));
    body(4,events.some(e=>e.kind==='fill')?table(['時間','事件','張數','方向'],eventRows(events,'fill')):empty('尚無成交'));
    body(5,dl([['快照',r?label(r.state):runtimePhase()],['完整行',count(r?.complete_event_lines)],['未載入事件',count(r?.events_omitted)],['上限','最新 200 筆'],['局部行','不納入完整事件']])+button('讀取詳情','data-detail="runtime"'));
  }
  function renderRisk() {
    metrics([['有效槓桿','—','未接入'],['當日日損','—','基準未接入'],['單幣預算占比','—','曝險未接入'],['風控鎖存','—','未接入']]);
    body(1,empty('帳戶快照未接入')+dl([['風控權益','—'],['日初權益','—'],['在途／UNKNOWN','—'],['允許增倉','未提供'],['Soft／Hard 鎖存','未提供']]));
    const anomalies=(state.runtime?.events||[]).filter(e=>e.kind==='anomaly');
    body(2,'<div class="section-line"><span>R4 '+esc(runtimePhase())+'</span>'+badge('已記錄 '+count(state.runtime?.status?.anomalies)+' 個異常')+'</div>'+(anomalies.length?table(['時間','事件','原因','內容'],eventRows(anomalies)):empty(state.runtime?'目前載入事件無異常':'執行資料未提供'))+button('執行詳情','data-detail="runtime"'));
    body(3,'<div class="policy-row"><span>有效槓桿上限預設</span><strong>3.0x</strong></div><div class="policy-row"><span>單幣預算占比預設</span><strong>50%</strong></div><p class="row-note">預設政策；目前生效參數未接入。</p>'+button('政策詳情','data-detail="policy"'));
    body(4,'<div class="policy-row"><span>Soft 預設</span><strong>10%</strong></div><div class="policy-row"><span>Hard 預設</span><strong>20%</strong></div><p class="row-note">Asia/Taipei 切日 · 人工恢復鎖存</p>'+button('日損詳情','data-detail="policy"'));
    body(5,empty('保護狀態未接入')+'<p class="row-note">Bot 預設 0% · 交易所保護狀態未提供。</p>'+button('保護詳情','data-detail="policy"'));
  }
  function renderYaozi() {
    metrics([['情報連線','未接入','資料庫未提供'],['市場候選','—','未接入'],['今日情報','—','未接入'],['資料新鮮度','—','未提供']]);
    body(1,empty('市場雷達未接入')+'<p class="row-note">接入後顯示既有 Yaozi 雷達與候選。</p>'+button('接入詳情','data-detail="intel"'));
    body(2,empty('今日情報未接入'));body(3,empty('關注資料未提供'));
    body(4,empty('來源覆蓋未提供')+button('服務狀態','data-detail="intel"'));
    body(5,empty('情報與交易獨立')+'<p class="row-note">切換情報頁不影響策略生命週期。</p>');
    if(state.researchVersion?.market_status==='ready') {
      body(1,'<div class="block-state"><strong>情報服務可用</strong><a href="'+(state.workspaceVersion?.preview?'http://127.0.0.1:8770':'')+'/dashboard" target="_blank" rel="noopener">開啟既有情報工作區 ↗</a></div>');
    }
  }
  function renderSettings() {
    const rv=state.researchVersion,wv=state.workspaceVersion;
    metrics([['研究服務',rv?(rv.restart_required?'版本待更新':'已連線'):'未連線','8770'],['工作台',wv?(wv.restart_required?'版本待更新':'已連線'):'未連線','本機'],['執行資料',runtimePhase(),'R4 只讀'],['情報服務',rv?.market_status==='ready'?'可用':'未接入','Yaozi']]);
    body(1,[['研究服務',rv?'已連線':'未連線'],['研究提交',gate()||'可用'],['本機執行快照',runtimePhase()],['情報資料',rv?.market_status==='ready'?'可用':'未接入']].map(([k,v])=>'<div class="service-row"><span>'+esc(k)+'</span>'+badge(v)+'</div>').join('')+button('版本與診斷','data-detail="source"'));
    body(2,'<label class="section-line" for="density">表格密度<select id="density"><option value="dense">緊湊</option><option value="comfortable">舒適</option></select></label><p class="row-note">僅儲存在此瀏覽器；不影響帳務與執行。</p>');
    $('density').value=document.body.dataset.density;
    body(3,'<p class="row-note">每頁、每種預設獨立保存。使用上方工具拖曳、調整分隔、隱藏或加回面板。</p>'+button('開啟元件庫','data-layout="library"','gold-button')+' '+button('還原本頁版面','data-layout="reset"'));
    body(4,dl([['研究入口','原 8770 ResearchService'],['協定','既有七工具契約'],['Agent 連線','未提供'],['任務歷史','與研究頁共用']])+button('介面詳情','data-detail="agent"'));
    body(5,dl([['環境','Localhost only'],['模式','合成研究／本機模擬'],['Demo／Live','未接入'],['Bot 啟停','未接入']])+button('執行詳情','data-detail="runtime"'));
  }
  function render() {
    ({research:renderResearch,execution:renderExecution,risk:renderRisk,events:renderEvents,yaozi:renderYaozi,settings:renderSettings}[page])();
    const s=state.monitor?.status;
    $('monitor-status').textContent='R4 '+runtimePhase(state.monitor)+' · 已記錄異常 '+count(s?.anomalies)+' · 帳戶風控未接入';
    $('monitor-time').textContent='心跳 '+time(s?.heartbeat_at);
    $('monitor-status').parentElement.dataset.state=state.monitor?.state||(state.errors.monitor?'error':'empty');
    $('monitor-status').parentElement.dataset.anomaly=String(Number.isInteger(s?.anomalies)&&s.anomalies>0);
    $('connection-label').textContent=Object.keys(state.errors).length?'部分資料':'已連線';
    $('research-connection').textContent=state.researchVersion?'已連線':'失敗';
    $('runtime-connection').textContent=runtimePhase(state.monitor);
    const selector=$('runtime-select');
    if(selector) {
      selector.innerHTML=state.runtimeRuns.length?state.runtimeRuns.map(r=>'<option value="'+esc(r.run_id)+'">'+esc(r.run_id.slice(0,8)+' · '+label(r.state)+' · '+r.profile)+'</option>').join(''):'<option value="">無執行記錄</option>';
      selector.value=state.runtimeId||'';selector.disabled=!state.runtimeRuns.length;
    }
  }
  async function loadResult() {
    const id=state.runId,run=state.runs.find(r=>r.run_id===id);
    if(state.result?.run_id===id)return;
    const ticket=++state.ticket;state.result=null;delete state.errors.result;
    if(!validId(id)||run?.status!=='complete')return;
    try {const result=await request('/api/research/runs/'+id+'/result');if(ticket!==state.ticket)return;if(result.run_id!==id)throw new Error('result_run_mismatch');state.result=result;}
    catch(error){if(ticket===state.ticket)state.errors.result=error.message;}
  }
  async function loadRuntime(id) {
    state.runtime=null;delete state.errors.runtime;state.eventIndex=null;
    if(!validId(id))return;
    try {const runtime=await request('/api/workspace/local-sim/runs/'+id);if(state.runtimeId===id)state.runtime=runtime;}
    catch(error){if(state.runtimeId===id)state.errors.runtime=error.message;}
  }
  async function refresh() {
    if(state.busy)return;state.busy=true;$('refresh').disabled=true;
    const keys=['researchVersion','workspaceVersion','runs','runtimeRuns','catalog'];
    try {
      const responses=await Promise.allSettled(['/api/research/version','/api/workspace/version','/api/research/runs','/api/workspace/local-sim/runs','/api/research/catalog'].map(p=>request(p)));
      responses.forEach((reply,i)=>{const key=keys[i];delete state.errors[key];if(reply.status==='rejected'){state.errors[key]=reply.reason.message;state[key]=key==='runs'||key==='runtimeRuns'?[]:null;}else state[key]=key==='runs'||key==='runtimeRuns'?(reply.value.items||[]).filter(r=>validId(r.run_id)):reply.value;});
      const active=state.runtimeRuns.filter(r=>r.profile==='eight-hour'&&r.state==='running');
      const chosen=active.length===1?active[0]:active.length>1?null:state.runtimeRuns.find(r=>r.profile==='eight-hour');
      delete state.errors.monitor;
      if(active.length>1)state.errors.monitor='ambiguous_active_r4';
      if(!state.runtimeManual)state.runtimeId=chosen?.run_id||null;
      const previousLine=selectedEvent()?.line_number;
      if(state.runtimeId)await loadRuntime(state.runtimeId);else state.runtime=null;
      state.monitor=null;
      if(chosen?.run_id===state.runtimeId)state.monitor=state.runtime;
      else if(chosen) {
        try {state.monitor=await request('/api/workspace/local-sim/runs/'+chosen.run_id);}
        catch(error){state.errors.monitor=error.message;}
      }
      const previousIndex=state.runtime?.events?.findIndex(e=>e.line_number===previousLine);
      state.eventIndex=previousIndex>=0?previousIndex:null;
      if(page==='research') {
        if(!state.runs.some(r=>r.run_id===state.runId))state.runId=state.runs.find(r=>r.status==='complete'&&r.kind===(state.tab==='optimization'?'optimization':'backtest'))?.run_id||null;
        await loadResult();
      }
      render();
    } finally {state.busy=false;$('refresh').disabled=false;}
  }
  function draftDialog() {
    if(!$('draft-dialog')) {
      const dialog=document.createElement('dialog');dialog.id='draft-dialog';dialog.setAttribute('aria-label','研究設定');
      dialog.innerHTML='<header><strong>研究設定 · 新草稿</strong>'+button('×','data-action="close-draft" aria-label="關閉研究設定"')+'</header><form id="draft-form" class="settings-body"><p>固定 SMA 策略／合成 BTC 15m；以下設定只用於下一次提交。</p><div class="form-grid">'+[['period','均線週期'],['quantity','委託張數'],['warmup_bars','預熱根數'],['initial_balance','初始權益 USDT'],['fee_rate','手續費率'],['slippage_bps','滑價 bps']].map(([key,title])=>'<label>'+title+'<input name="'+key+'" required autocomplete="off" '+(key==='period'||key==='warmup_bars'?'inputmode="numeric"':'inputmode="decimal"')+'></label>').join('')+'</div><details id="search-settings"><summary>參數搜尋設定</summary><div class="form-grid">'+[['low','週期下限'],['high','週期上限'],['step','搜尋步長'],['n_trials','試驗次數'],['seed','隨機種子']].map(([key,title])=>'<label>'+title+'<input name="'+key+'" required inputmode="numeric" autocomplete="off"></label>').join('')+'</div><p>搜尋時預熱根數需 >= 週期上限。</p></details><div id="draft-error" role="status" class="row-note"></div><div class="form-actions">'+button('取消','type="button" data-action="close-draft"')+'<button type="submit" class="gold-button">儲存草稿</button></div></form>';
      document.body.append(dialog);
      $('draft-form').addEventListener('submit',e=>{e.preventDefault();try{saveForm();dialog.close();renderResearch();}catch(error){$('draft-error').textContent=error.message;}});
    }
    const form=$('draft-form');
    for(const [key,value] of Object.entries({...state.draft,...state.draft.parameters,...state.search}))if(form.elements.namedItem(key))form.elements.namedItem(key).value=value;
    $('draft-error').textContent='';$('search-settings').open=state.tab==='optimization';$('draft-dialog').showModal();
  }
  function saveForm() {
    const form=$('draft-form'),value=key=>form.elements.namedItem(key).value.trim();
    const integer=key=>{const s=value(key);if(!/^\d+$/.test(s)||!Number.isSafeInteger(Number(s)))throw new Error('請填寫有效整數：'+key);return Number(s);};
    const decimal=key=>{const s=value(key);if(!/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(s))throw new Error('請填寫十進位字串：'+key);return s;};
    const period=integer('period'),warmup=integer('warmup_bars');
    const search=Object.fromEntries(Object.keys(searchDefaults).map(key=>[key,integer(key)]));
    if(period<2||period>32||warmup<period||warmup>512)throw new Error('均線週期須為 2–32；預熱根數須 >= 均線週期且 <= 512。');
    if(search.low<2||search.high>32||search.low>search.high||search.step<1||search.n_trials<1||search.n_trials>20)throw new Error('請檢查搜尋範圍；試驗次數須為 1–20。');
    state.draft={...defaults,parameters:{period,quantity:decimal('quantity')},warmup_bars:warmup,initial_balance:decimal('initial_balance'),fee_rate:decimal('fee_rate'),slippage_bps:decimal('slippage_bps')};
    state.search=search;writeLocal(draftKey,{draft:state.draft,search:state.search});state.message='草稿已保存';
  }
  async function submit(kind) {
    if(gate())return;
    if(kind==='optimization'&&state.draft.warmup_bars<state.search.high){state.message='請提高預熱根數至搜尋上限';updateGate();draftDialog();return;}
    const backtest=structuredClone(state.draft),search=state.search;
    const payload=kind==='optimization'?{backtest,search_space:{period:{low:search.low,high:search.high,step:search.step}},n_trials:search.n_trials,seed:search.seed}:backtest;
    state.submitting=true;state.message='提交中';updateGate();
    try {
      const task=await request('/api/research/'+(kind==='optimization'?'optimizations':'backtests'),{method:'POST',headers:{'Content-Type':'application/json','X-CatOS-Build':state.researchVersion.build_id},body:JSON.stringify(payload)});
      if(!validId(task.run_id))throw new Error('invalid_run_id');
      state.runId=task.run_id;state.result=null;state.tab=kind;state.message='研究已提交';delete state.errors.submit;controls();await refresh();
    } catch(error){state.errors.submit=error.message;state.message='提交失敗，查看詳情';}
    finally{state.submitting=false;updateGate();}
  }
  function showDetail(kind) {
    if(kind==='source')detail('來源、版本與驗收', '<p>已確認的 Gemini 畫面與工作台操作；研究共用原 8770，R4 僅讀 manifest／status／完整 JSONL 事件。15 秒更新。</p><p>頁面切換、隱藏與瀏覽器關閉不控制研究或策略生命週期。帳戶快照與目前情報資料未提供；指定 5.6 Sol (Web) 獨立驗收另行執行。</p><details open><summary>版本與讀取問題</summary>'+json({research:state.researchVersion,workspace:state.workspaceVersion,errors:state.errors})+'</details>');
    else if(kind==='runtime'||kind==='monitor') {
      const runtime=kind==='monitor'?state.monitor:state.runtime;
      detail('本機執行來源', '<p>R4 合成執行只讀快照；訊號 account 是決策前視圖，fill 是成交後記錄。已記錄零異常不代表帳戶風控正常、Worker 存活或八小時驗收通過。</p>'+json(runtime?{...runtime,events:undefined}:{state:'unavailable',issues:state.errors}));
    }
    else if(kind==='result')detail('已保存結果設定與來源', state.result?'<p>此設定屬於已保存結果，與下一次提交草稿分開。帳務文字維持原始 Decimal；Float 僅衍生繪圖座標。</p>'+json({...state.result,result:state.result.result?{...state.result.result,equity_curve:undefined,trades:undefined}:undefined,trials:undefined})+'<a href="/api/research/runs/'+state.result.run_id+'/report" target="_blank" rel="noopener">完整報告 ↗</a>':empty('結果未提供'));
    else if(kind==='task')detail('研究任務',json(state.runs.find(r=>r.run_id===state.runId)));
    else if(kind==='strategy')detail('核可策略與模型', '<p>只使用 registry 核可 SMA／固定合成資料；不提供任意策略、CSV 或 URL 匯入。預熱只更新指標，不產生委託；下一根開盤加明示滑價成交。</p>'+json(state.catalog));
    else if(kind==='policy')detail('已確認預設政策', '<p>有效槓桿上限預設 3.0x；單幣預算上限為總曝險預算的 50%。風控權益採已驗證權益，事前曝險包含在途與 UNKNOWN。</p><p>日損固定日初權益分母，Asia/Taipei 00:00 切日；Soft 10% 停增倉，Hard 20% 啟動清倉與 Kill。鎖存不因反彈、切日、重啟或入金解除；人工恢復不得覆蓋有效風險原因。</p><p>Bot 災難停損預設 0% 不啟用；非零使用 mark 交易所整倉保護。此頁未讀取生效配置，不提供修改、恢復或交易控制。</p>');
    else if(kind==='intel')detail('Yaozi 接入狀態', '<p>同站情報／量化分頁保持獨立生命週期。既有情報資料庫未提供時不產生替代行情；目前服務狀態如下。接入可用資料後沿用既有情報契約，不跨工作目錄匯入。</p>'+json({market_status:state.researchVersion?.market_status,preview:state.workspaceVersion?.preview}));
    else if(kind==='agent')detail('Agent 研究介面', '<p>沿用原七工具與 exact binding；Agent 與本頁使用同一 ResearchService、registry、合成資料與保存結果。頁面未探測任何 Agent client，不把契約存在當作 client 已連線。</p>');
  }
  function library(open) {if(open){state.libraryFocus=document.activeElement;$('widget-library-panel').inert=false;engine.openWidgetLibrary();document.querySelector('[data-layout="close-library"]').focus();}else{engine.closeWidgetLibrary();$('widget-library-panel').inert=true;state.libraryFocus?.focus();}}
  async function selectRun(id) {
    const run=state.runs.find(r=>r.run_id===id);if(!run)return;
    state.runId=id;state.tab=run.kind==='optimization'?'optimization':'backtest';controls();await loadResult();renderResearch();
  }
  document.addEventListener('click',async event=>{
    if(event.target.closest('[data-strategy-detail]')){event.preventDefault();showDetail('strategy');return;}
    const b=event.target.closest('button');if(!b)return;
    if(b.dataset.detail)showDetail(b.dataset.detail);
    if(b.dataset.action==='draft')draftDialog();
    if(b.dataset.action==='close-draft')$('draft-dialog')?.close();
    if(b.dataset.submit)await submit(b.dataset.submit);
    if(b.dataset.tab){
      state.tab=b.dataset.tab;state.message='';controls();
      if(state.tab!=='strategy'&&state.runs.find(r=>r.run_id===state.runId)?.kind!==state.tab){state.runId=state.runs.find(r=>r.kind===state.tab&&r.status==='complete')?.run_id||null;await loadResult();}
      renderResearch();
    }
    if(b.dataset.run)await selectRun(b.dataset.run);
    if(b.hasAttribute('data-candidate')){
      const t=state.result?.trials?.find(t=>String(t.number)===b.dataset.candidate);
      if(t?.state==='COMPLETE'&&Number.isSafeInteger(t.params?.period)){
        state.draft=structuredClone(state.result.request.backtest);state.draft.parameters.period=t.params.period;
        writeLocal(draftKey,{draft:state.draft,search:state.search});state.message='候選已帶入新草稿';renderResearch();draftDialog();
      }
    }
    if(b.hasAttribute('data-trial')){const trial=state.result?.trials?.find(t=>String(t.number)===b.dataset.trial);if(trial)detail('試驗詳情',json(trial));}
    if(b.dataset.runtime){state.runtimeManual=true;state.runtimeId=b.dataset.runtime;await loadRuntime(state.runtimeId);render();}
    if(b.hasAttribute('data-event')){const i=Number(b.dataset.event),e=state.runtime?.events?.[i];if(e){state.eventIndex=i;if(page==='events')renderEvents();detail('事件原始記錄',json(e));}}
    if(b.dataset.preset)engine.applyPreset(b.dataset.preset);
    if(b.dataset.widget)engine.toggleMaximize(b.dataset.widget);
    if(b.dataset.hide)engine.hideWidget(b.dataset.hide);
    if(b.dataset.restore)engine.restoreWidget(b.dataset.restore);
    const a=b.dataset.layout;
    if(a==='edit')engine.toggleEditing();if(a==='pack')engine.autoPackGrid();if(a==='undo')engine.revertLayout();if(a==='reset')engine.resetLayout();if(a==='library')library(true);if(a==='close-library')library(false);
  });
  document.addEventListener('change',async e=>{
    if(e.target.id==='runtime-select'){state.runtimeManual=true;state.runtimeId=e.target.value;await loadRuntime(state.runtimeId);render();}
    if(e.target.id==='event-filter'){state.filter=e.target.value;renderEvents();}
    if(e.target.id==='density'){document.body.dataset.density=e.target.value;writeLocal(preferenceKey,{density:e.target.value});}
  });
  $('event-query')?.addEventListener('input',e=>{state.query=e.target.value;renderEvents();});
  $('widget-library-backdrop').addEventListener('click',()=>library(false));
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&$('widget-library-panel').classList.contains('is-open')){library(false);event.preventDefault();}
    else if(event.key==='Escape'&&engine.maximizedPaneId&&!$('detail-dialog').open&&!$('draft-dialog')?.open)engine.toggleMaximize(engine.maximizedPaneId);
    if(event.key==='Tab'&&$('widget-library-panel').classList.contains('is-open')){
      const buttons=[...$('widget-library-panel').querySelectorAll('button:not(:disabled)')],first=buttons[0],last=buttons.at(-1);
      if(event.shiftKey&&document.activeElement===first){last?.focus();event.preventDefault();}
      else if(!event.shiftKey&&document.activeElement===last){first?.focus();event.preventDefault();}
    }
  });
  $('detail-close').addEventListener('click',()=>$('detail-dialog').close());
  $('refresh').addEventListener('click',refresh);
  refresh();
  setInterval(()=>{if(!document.hidden&&!$('draft-dialog')?.open&&!$('widget-library-panel').classList.contains('is-open')&&!engine.isEditing)refresh();},15000);
})();
