/* Server-owned results. Decimal strings convert to Number only for SVG coordinates. */
window.Research = {
  catalog:null, runs:[], results:{}, version:null, error:'', optError:'', ready:false,
  escape(value) {
    return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  },
  async api(path, options={}) {
    const response = await fetch('/api/research/' + path, {cache:'no-store', ...options});
    const value = await response.json();
    if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : JSON.stringify(value.detail));
    return value;
  },
  date(ms) { return new Date(ms).toISOString().replace('T',' ').slice(0,16) + ' UTC'; },
  status(value) { return ({queued:'排隊',running:'執行中',complete:'完成',failed:'失敗'})[value] || value; },
  selected() {
    const id = window.appState.get('researchRunId');
    const runs = this.runs.filter(run => !run.kind || run.kind === 'backtest');
    return runs.find(run => run.run_id === id) || runs[0];
  },
  selectedOptimization() {
    const id = window.appState.get('optimizationRunId');
    const runs = this.runs.filter(run => run.kind === 'optimization');
    return runs.find(run => run.run_id === id) || runs[0];
  },
  edit(name, value) {
    const config = {...(window.appState.get('researchConfig') || this.catalog.defaults)};
    config.parameters = {...config.parameters};
    if (name === 'period') config.parameters.period = Number(value);
    else if (name === 'quantity') config.parameters.quantity = value;
    else config[name] = name === 'warmup_bars' ? Number(value) : value;
    window.appState.set({researchConfig:config, researchDirty:true}, false);
    const dirty = document.getElementById('research-dirty');
    if (dirty) dirty.textContent = '設定已變更，尚未重跑；目前結果維持原快照';
  },
  renderBacktest(state) {
    const e = value => this.escape(value);
    const config = state.researchConfig || this.catalog.defaults;
    const selected = this.selected();
    const payload = selected && this.results[selected.run_id];
    const backtests = this.runs.filter(run => !run.kind || run.kind === 'backtest');
    const busy = this.runs.some(run => ['queued','running'].includes(run.status));
    const blocked = !this.ready || !this.version || this.version.restart_required ||
      this.version.build_id !== window.CATOS_RESEARCH_BOOT.build_id || busy;
    const field = (name,label,value,type='text',extra='') => `<div><label class="form-label" for="research-${name}">${label}</label>
      <input class="form-input" id="research-${name}" name="${name}" type="${type}" value="${e(value)}" ${extra}
      oninput="window.Research.edit('${name}',this.value)"></div>`;
    return `<div class="backtest-layout">
      <div class="research-notice">合成 Closed Bar · 明示成本與預熱。執行後設定固定，表單修改不更動已完成結果。</div>
      <div class="panel">
        <div class="panel-header"><span>回測設定</span><span id="research-dirty" class="badge badge-amber">${state.researchDirty ? '設定已變更，尚未重跑' : '執行時保存完整快照'}</span></div>
        <form id="research-form" onsubmit="event.preventDefault();window.Research.submit(this)">
          <div class="research-form">
            <div><label class="form-label">策略版本</label><select class="form-input" name="strategy_id"><option value="sma-trend">SMA · ${e(this.catalog.strategies[0].version)}</option></select></div>
            <div><label class="form-label">資料</label><select class="form-input" name="dataset_id"><option value="synthetic-btc-15m-v1">合成 BTC · 15m · 96 bars</option></select></div>
            ${field('period','SMA 週期（根）',config.parameters.period,'number','min="2" max="32" step="1" required')}
            ${field('quantity','目標張數（contracts）',config.parameters.quantity,'text','inputmode="decimal" required')}
            ${field('initial_balance','初始權益（USDT）',config.initial_balance,'text','inputmode="decimal" required')}
            ${field('fee_rate','市價手續費率（比例；0.0005 = 0.05%）',config.fee_rate,'text','inputmode="decimal" required')}
            ${field('slippage_bps','滑價（bps；2 = 0.02%）',config.slippage_bps,'text','inputmode="decimal" required')}
            ${field('warmup_bars','預熱根數（>= SMA 週期、<64）',config.warmup_bars,'number','min="2" max="63" step="1" required')}
            <div><label class="form-label">執行模型</label><div class="research-status">下一根開盤 · 逆向滑價 · 資金費 0 事件</div></div>
          </div>
          <div class="research-details"><button class="btn btn-gold" type="submit" ${blocked ? 'disabled' : ''}>${busy ? '回測執行中…' : '執行真實回測'}</button>
          <span style="margin-left:12px;">一次一個任務 · 30 秒上限 · 關閉分頁仍由後端完成</span>
          ${this.error ? `<div class="research-error" role="alert">${e(this.error)}</div>` : ''}</div>
        </form>
      </div>
      <div class="research-results">
        <div class="panel"><div class="panel-header">回測紀錄 · ${backtests.length} 筆</div>
          ${backtests.length ? backtests.map(run => `<button class="research-record ${selected?.run_id === run.run_id ? 'active' : ''}"
            onclick="window.Research.select('${run.run_id}')"><span class="num">${run.run_id.slice(0,12)}</span><br>
            ${this.status(run.status)} · SMA ${run.request.parameters.period}<br>${e(run.created_at.slice(0,19))} UTC</button>`).join('') : '<div class="research-status">尚無回測。設定後建立第一筆。</div>'}
        </div>
        <div class="panel">
          ${!selected ? '<div class="research-status">尚無結果</div>' : `<div class="panel-header"><span>固定結果 · ${selected.run_id.slice(0,12)}</span><span>${this.status(selected.status)}</span></div>
            ${selected.status === 'failed' ? `<div class="research-details research-error">${e(selected.error)}</div>` : ''}
            ${['queued','running'].includes(selected.status) ? '<div class="research-status">後端計算中；完成後自動讀取。重新整理可接續查看。</div>' : ''}
            ${selected.status === 'complete' && !payload ? '<div class="research-status">讀取保存結果…</div>' : ''}
            ${payload ? this.renderResult(payload) : ''}`}
        </div>
      </div>
    </div>`;
  },
  optimizationConfig(state) {
    return state.optimizationConfig || this.catalog.optimization.defaults;
  },
  editOptimization(name,value) {
    const previous = this.optimizationConfig(window.appState.state);
    const config = {...previous, backtest:{...previous.backtest},
      search_space:{period:{...previous.search_space.period}}};
    const integer = ['low','high','step','n_trials','seed','warmup_bars'].includes(name);
    const parsed = integer ? Number(value) : value;
    if (['low','high','step'].includes(name)) config.search_space.period[name] = parsed;
    else if (name === 'warmup_bars' || name === 'quantity') config.backtest[name === 'quantity' ? 'parameters' : name] =
      name === 'quantity' ? {...config.backtest.parameters, quantity:parsed} : parsed;
    else if (name === 'initial_balance' || name === 'fee_rate' || name === 'slippage_bps') config.backtest[name] = parsed;
    else config[name] = parsed;
    window.appState.set({optimizationConfig:config,optimizationDirty:true},false);
    const dirty = document.getElementById('optimization-dirty');
    if (dirty) dirty.textContent = '設定已變更，既有候選仍保留原快照';
  },
  renderOptimization(state) {
    const e = value => this.escape(value);
    const config = this.optimizationConfig(state);
    const selected = this.selectedOptimization();
    const payload = selected && this.results[selected.run_id];
    const optimizations = this.runs.filter(run => run.kind === 'optimization');
    const busy = this.runs.some(run => ['queued','running'].includes(run.status));
    const blocked = !this.ready || !this.version || this.version.restart_required ||
      this.version.build_id !== window.CATOS_RESEARCH_BOOT.build_id || busy;
    const field = (name,label,value,extra='') => `<div><label class="form-label" for="optimization-${name}">${label}</label>
      <input class="form-input" id="optimization-${name}" name="${name}" type="${['low','high','step','n_trials','seed','warmup_bars'].includes(name) ? 'number' : 'text'}"
        value="${e(value)}" ${extra} oninput="window.Research.editOptimization('${name}',this.value)"></div>`;
    return `<div class="backtest-layout">
      <div class="research-notice">Optuna · 註冊 SMA 週期搜尋 · 固定合成 15m 資料。只做樣本內搜尋，未執行樣本外檢驗；候選績效不代表市場績效。</div>
      <div class="panel"><div class="panel-header"><span>搜尋設定</span><span id="optimization-dirty" class="badge badge-amber">${state.optimizationDirty ? '設定已變更' : '執行時保存完整快照'}</span></div>
        <form onsubmit="event.preventDefault();window.Research.submitOptimization(this)"><div class="research-form">
          ${field('low','SMA 週期下限',config.search_space.period.low,'min="2" max="32" step="1" required')}
          ${field('high','SMA 週期上限',config.search_space.period.high,'min="2" max="32" step="1" required')}
          ${field('step','週期步長',config.search_space.period.step,'min="1" max="30" step="1" required')}
          ${field('n_trials','Trial 預算（1–20）',config.n_trials,'min="1" max="20" step="1" required')}
          ${field('seed','隨機種子',config.seed,'min="0" max="4294967295" step="1" required')}
          ${field('quantity','固定目標張數',config.backtest.parameters.quantity,'inputmode="decimal" required')}
          ${field('warmup_bars','預熱根數（>= 週期上限）',config.backtest.warmup_bars,'min="2" max="63" step="1" required')}
          ${field('initial_balance','初始權益（USDT）',config.backtest.initial_balance,'inputmode="decimal" required')}
          ${field('fee_rate','市價手續費率（比例）',config.backtest.fee_rate,'inputmode="decimal" required')}
          ${field('slippage_bps','滑價（bps）',config.backtest.slippage_bps,'inputmode="decimal" required')}
        </div><div class="research-details"><p>目標：最大化 Decimal 報酬率（%）。Float 僅交給 Optuna 排序；原始績效保留 Decimal 字串。</p>
          <button class="btn btn-gold" type="submit" ${blocked ? 'disabled' : ''}>${busy ? '研究任務執行中…' : '開始參數優化'}</button>
          <span style="margin-left:12px;">與回測共用單一任務槽 · 30 秒上限</span>
          ${this.optError ? `<div class="research-error" role="alert">${e(this.optError)}</div>` : ''}</div></form></div>
      <div class="research-results"><div class="panel"><div class="panel-header">優化紀錄 · ${optimizations.length} 筆</div>
        ${optimizations.length ? optimizations.map(run => `<button class="research-record ${selected?.run_id === run.run_id ? 'active' : ''}"
          onclick="window.Research.selectOptimization('${run.run_id}')"><span class="num">${run.run_id.slice(0,12)}</span><br>
          ${this.status(run.status)} · ${e(run.request.n_trials)} trials · seed ${e(run.request.seed)}<br>${e(run.created_at.slice(0,19))} UTC</button>`).join('') : '<div class="research-status">尚無優化紀錄。</div>'}</div>
        <div class="panel">${!selected ? '<div class="research-status">尚無候選</div>' : `<div class="panel-header"><span>固定候選 · ${selected.run_id.slice(0,12)}</span><span>${this.status(selected.status)}</span></div>
          ${selected.status === 'failed' ? `<div class="research-details research-error">${e(selected.error)}</div>` : ''}
          ${['queued','running'].includes(selected.status) ? '<div class="research-status">後端計算中；完成後自動讀取，重整仍可查看。</div>' : ''}
          ${selected.status === 'complete' && !payload ? '<div class="research-status">讀取候選…</div>' : ''}
          ${payload ? this.renderOptimizationResult(payload,blocked) : ''}`}</div></div></div>`;
  },
  renderOptimizationResult(payload,blocked) {
    const e = value => this.escape(value);
    const best = payload.best_trial_number;
    return `<div class="research-details">${e(payload.data_notice)}<br>目標 ${e(payload.objective.name)} · ${e(payload.objective.direction)} · seed ${e(payload.seed)} · Optuna ${e(payload.optuna_version)}
      <br>最佳 trial：${best === null ? '無可用候選' : e(best)}</div>
      <div class="research-trades"><table class="data-table"><thead><tr><th>Trial</th><th>SMA 週期</th><th>狀態</th><th>報酬率（%）</th><th>期末權益（USDT）</th><th>最大回撤（%）</th><th>操作</th></tr></thead><tbody>
      ${payload.trials.map(trial => `<tr><td>${trial.number}${trial.number === best ? ' ★' : ''}</td>
        <td class="num">${e(trial.params.period ?? '—')}</td><td>${e(trial.state)}</td>
        <td class="num">${e(trial.performance?.return_pct ?? '—')}</td>
        <td class="num">${e(trial.performance?.final_equity ?? '—')}</td>
        <td class="num">${e(trial.performance?.max_drawdown_pct ?? '—')}</td>
        <td>${trial.state === 'COMPLETE' ? `<button class="btn btn-sm btn-ghost" onclick="window.Research.applyCandidate('${payload.run_id}',${trial.number})" ${blocked ? 'disabled' : ''}>套用並新建回測</button>` : e(trial.error ?? '—')}</td></tr>`).join('')}</tbody></table></div>
      <div class="research-details"><a class="btn btn-sm btn-ghost" target="_blank" rel="noopener" href="/api/research/runs/${payload.run_id}/report">開啟候選報告</a>
        <a class="btn btn-sm btn-ghost" target="_blank" rel="noopener" href="/api/research/runs/${payload.run_id}/result">原始 JSON</a>
        <details><summary>固定搜尋設定與來源</summary><pre>${e(JSON.stringify({request:payload.request,provenance:payload.provenance,objective:payload.objective},null,2))}</pre></details></div>`;
  },
  renderResult(payload) {
    const e = value => this.escape(value);
    const result = payload.result;
    const performance = result.performance;
    const metrics = [['初始權益（USDT）','initial_equity'],['期末權益（USDT）','final_equity'],
      ['淨損益（USDT）','net_pnl'],['報酬（%）','return_pct'],['最大回撤（%）','max_drawdown_pct'],
      ['模擬成交筆數（非完整交易）','trade_count'],['已實現損益（USDT）','realized_pnl'],
      ['未實現損益（USDT）','unrealized_pnl'],['手續費（USDT）','fees'],['資金費（USDT）','funding_paid']];
    return `<div class="research-metrics">${metrics.map(([label,key]) => `<div class="research-metric">
      <span>${label}</span><span class="num" data-metric="${key}">${e(performance[key])}</span></div>`).join('')}</div>
      <div class="research-details">${e(payload.data_notice)}<br>評估：${this.date(result.evaluation_start_ms)} → ${this.date(result.evaluation_end_ms)} · 預熱 ${result.warmup_bars} 根</div>
      <div class="panel-header">研究權益與回撤（獨立於運行帳戶）</div><div id="research-curve" class="research-curve"></div>
      <div class="research-details"><a class="btn btn-sm btn-ghost" target="_blank" rel="noopener" href="/api/research/runs/${payload.run_id}/report">開啟 HTML 報告</a>
        <a class="btn btn-sm btn-ghost" target="_blank" rel="noopener" href="/api/research/runs/${payload.run_id}/result">原始 JSON</a></div>
      <div class="panel-header">模擬成交 · ${result.trades.length} 筆</div>
      <div class="research-trades"><table class="data-table"><thead><tr><th>成交時間</th><th>決策時間</th><th>張數</th><th>價格（USDT）</th><th>費用（USDT）</th><th>已實現損益（USDT）</th><th>成交後部位</th></tr></thead>
        <tbody>${result.trades.map(trade => `<tr><td>${this.date(trade.time_ms)}</td><td>${this.date(trade.decision_time_ms)}</td>
          ${['quantity','price','fee','realized_pnl','position_after'].map(key => `<td class="num">${e(trade[key])}</td>`).join('')}</tr>`).join('') || '<tr><td colspan="7">無成交</td></tr>'}</tbody></table></div>
      <div class="research-details"><details><summary>固定設定、來源與模型假設</summary>
        <pre>${e(JSON.stringify({run_id:payload.run_id,request:payload.request,provenance:payload.provenance,
          config:result.config,pending_intent:result.pending_intent,assumptions:result.assumptions},null,2))}</pre>
      </details><p>金額與原始績效均為 Decimal 字串；曲線轉換僅供繪圖。</p></div>`;
  },
  drawCurve() {
    const selected = this.selected();
    const payload = selected && this.results[selected.run_id];
    const element = document.getElementById('research-curve');
    if (!payload || !element) return;
    const points = payload.result.equity_curve;
    const equities = points.map(point => Number(point.equity));
    const drawdowns = payload.drawdown_curve.map(point => Number(point.drawdown_pct));
    const low = Math.min(...equities), high = Math.max(...equities);
    const range = high-low || 1;
    const maxDD = Math.max(...drawdowns) || 1;
    const x = i => 90 + i / Math.max(1,points.length-1)*680;
    const y = i => 115-(equities[i]-low)/range*95;
    const dd = i => 145+drawdowns[i]/maxDD*35;
    element.innerHTML = `<svg viewBox="0 0 800 210" width="100%" height="100%" aria-label="研究權益與回撤">
      <text x="8" y="16" fill="var(--text-muted)" font-size="11">${this.escape(points[equities.indexOf(high)].equity)}</text>
      <text x="8" y="115" fill="var(--text-muted)" font-size="11">${this.escape(points[equities.indexOf(low)].equity)}</text>
      <line x1="90" y1="145" x2="770" y2="145" stroke="var(--border-subtle)"/>
      <text x="8" y="172" fill="var(--text-muted)" font-size="11">回撤 %</text>
      <polyline points="${points.map((_,i)=>`${x(i)},${y(i)}`).join(' ')}" fill="none" stroke="var(--gold-primary)" stroke-width="1.8"/>
      <polyline points="${points.map((_,i)=>`${x(i)},${dd(i)}`).join(' ')}" fill="none" stroke="var(--color-red)" stroke-width="1.4"/>
      ${points.map((point,i) => `<circle cx="${x(i)}" cy="${y(i)}" r="3" fill="transparent"><title>${this.date(point.time_ms)} · 權益 ${this.escape(point.equity)} USDT · 回撤 ${this.escape(payload.drawdown_curve[i].drawdown_pct)}%</title></circle>`).join('')}
      <text x="90" y="205" fill="var(--text-muted)" font-size="10">${this.date(points[0].time_ms)}</text>
      <text x="770" y="205" text-anchor="end" fill="var(--text-muted)" font-size="10">${this.date(points.at(-1).time_ms)}</text>
    </svg>`;
  },
  async submit(form) {
    if (this.submitting) return;
    this.submitting = true;
    this.error = '';
    try {
      const fields = new FormData(form);
      const request = {strategy_id:fields.get('strategy_id'), dataset_id:fields.get('dataset_id'),
        parameters:{period:Number(fields.get('period')),quantity:fields.get('quantity')},
        initial_balance:fields.get('initial_balance'),fee_rate:fields.get('fee_rate'),
        slippage_bps:fields.get('slippage_bps'),warmup_bars:Number(fields.get('warmup_bars'))};
      const task = await this.api('backtests', {method:'POST',headers:{'Content-Type':'application/json',
        'X-CatOS-Build':window.CATOS_RESEARCH_BOOT.build_id},body:JSON.stringify(request)});
      this.runs.unshift(task);
      window.appState.set({researchRunId:task.run_id,researchConfig:request,researchDirty:false});
      await this.refresh();
    } catch (error) {
      this.error = error.message;
      window.appState.notify();
    } finally { this.submitting = false; }
  },
  async submitOptimization(form) {
    if (this.submitting) return;
    this.submitting = true;
    this.optError = '';
    try {
      const fields = new FormData(form);
      const previous = this.optimizationConfig(window.appState.state);
      const request = {backtest:{...previous.backtest,parameters:{...previous.backtest.parameters,
        quantity:fields.get('quantity')},warmup_bars:Number(fields.get('warmup_bars')),
        initial_balance:fields.get('initial_balance'),fee_rate:fields.get('fee_rate'),
        slippage_bps:fields.get('slippage_bps')},
        search_space:{period:{low:Number(fields.get('low')),high:Number(fields.get('high')),
          step:Number(fields.get('step'))}},n_trials:Number(fields.get('n_trials')),seed:Number(fields.get('seed'))};
      const task = await this.api('optimizations',{method:'POST',headers:{'Content-Type':'application/json',
        'X-CatOS-Build':window.CATOS_RESEARCH_BOOT.build_id},body:JSON.stringify(request)});
      this.runs.unshift(task);
      window.appState.set({optimizationRunId:task.run_id,optimizationConfig:request,optimizationDirty:false});
      await this.refresh();
    } catch(error) { this.optError = error.message; window.appState.notify(); }
    finally { this.submitting = false; }
  },
  async selectOptimization(runId) {
    window.appState.set({optimizationRunId:runId});
    try { await this.loadResult(this.selectedOptimization()); }
    catch(error) { this.optError = `候選讀取失敗：${error.message}`; }
    finally { window.appState.notify(); }
  },
  async applyCandidate(runId,number) {
    if (this.submitting) return;
    this.submitting = true;
    this.optError = '';
    try {
      const payload = this.results[runId];
      const trial = payload?.trials.find(item => item.number === number);
      if (!trial || trial.state !== 'COMPLETE') throw new Error('candidate_not_complete');
      const request = {...payload.request.backtest,parameters:{...payload.request.backtest.parameters,
        period:trial.params.period}};
      const task = await this.api('backtests',{method:'POST',headers:{'Content-Type':'application/json',
        'X-CatOS-Build':window.CATOS_RESEARCH_BOOT.build_id},body:JSON.stringify(request)});
      this.runs.unshift(task);
      window.appState.set({researchRunId:task.run_id,researchConfig:request,researchDirty:false,strategySubTab:'backtest'});
      await this.refresh();
    } catch(error) { this.optError = error.message; window.appState.notify(); }
    finally { this.submitting = false; }
  },
  async select(runId) {
    window.appState.set({researchRunId:runId});
    try { await this.loadResult(this.selected()); }
    catch (error) { this.error = `結果讀取失敗：${error.message}`; }
    finally { window.appState.notify(); }
  },
  async loadResult(task) {
    if (task?.status === 'complete' && !this.results[task.run_id]) {
      this.results[task.run_id] = await this.api(`runs/${task.run_id}/result`);
      return true;
    }
    return false;
  },
  async checkVersion() {
    const version = await this.api('version');
    const previous = this.version;
    this.version = version;
    const element = document.getElementById('research-version');
    const changed = version.build_id !== window.CATOS_RESEARCH_BOOT.build_id;
    element.classList.toggle('stale',version.restart_required || changed);
    element.textContent = `研究 ${version.build_id.slice(0,12)} · PID ${version.pid} · 實例 ${version.instance_id.slice(0,8)} · ` +
      (version.restart_required ? (version.active_run_id ? '發現程式更新；等待任務結束後手動重啟服務' : '發現程式更新；請手動重啟服務再重新整理') :
        changed ? '服務已換版，請重新整理頁面' : '目前服務版本一致');
    element.title = `${version.workspace}\n啟動 ${version.started_at}\n目前原始碼 ${version.current_build_id}`;
    return !previous || previous.restart_required !== version.restart_required || previous.build_id !== version.build_id;
  },
  async refresh() {
    if (this.refreshing) return;
    this.refreshing = true;
    try {
      const runs = (await this.api('runs')).items;
      let changed = JSON.stringify(runs) !== JSON.stringify(this.runs);
      this.runs = runs;
      changed = await this.loadResult(this.selected()) || changed;
      changed = await this.loadResult(this.selectedOptimization()) || changed;
      if (!this.ready) { this.ready = true; changed = true; }
      if (changed) window.appState.notify();
    } catch (error) {
      this.ready = false;
      this.error = `研究服務無法讀取：${error.message}`;
      window.appState.notify();
    } finally { this.refreshing = false; }
  },
  async init() {
    const sidebar = window.AppRouter.renderSidebar;
    window.AppRouter.renderSidebar = function(state,page) {
      return sidebar.call(this,state,page).replace('SUPERVISOR TELEMETRY','原型示意 TELEMETRY')
        .replace('>ACTIVE<','>MOCK<').replace('OKX Sandbox','未連交易所 · 示意')
        .replace('CPU 12%','CPU —').replace('MEM 342M','MEM —').replaceAll('21 ms','—').replace('WSS 21ms','WSS —');
    };
    window.AppRouter.renderHeader = function(state,page) {
      const label = this.pageTitles[page] || 'catOS';
      return `<header class="app-header"><div class="header-left"><div class="header-dual-title">
        <div class="header-dual-title-main">${window.Research.escape(label)}</div>
        <div class="header-dual-title-sub">CATOS // LOCAL RESEARCH</div></div>
        <div class="env-pill-dual"><span class="env-dual-zh">${page === 'strategy' ? '正式回測 · 合成資料' : '原型 · 示意資料'}</span></div></div>
        <div class="header-right"><button class="btn btn-sm btn-ghost" onclick="window.AppRouter.navigate('settings')">外觀設定</button>
        <button class="btn btn-sm btn-ghost" onclick="window.Research.refresh()">刷新研究任務</button></div></header>`;
    };
    window.appState.state.selectedStrategyId = 'sma-trend';
    if (!window.appState.get('researchInitialized')) {
      window.appState.set({activePage:'strategy',strategyInDetail:false,researchInitialized:true},false);
    }
    window.AppRouter.init();
    try {
      this.catalog = await this.api('catalog');
      window.CATOS_DATA.strategies = this.catalog.strategies;
      if (!window.appState.get('researchConfig')) window.appState.set({researchConfig:this.catalog.defaults},false);
      await this.checkVersion();
      await this.refresh();
      window.appState.notify();
    } catch (error) {
      this.error = `研究服務連線失敗：${error.message}`;
      document.getElementById('research-version').textContent = `研究服務連線失敗：${error.message}`;
      window.appState.notify();
    }
    this.pollTimer = setInterval(() => this.refresh(),1500);
    this.versionTimer = setInterval(async () => {
      try { if (await this.checkVersion()) window.appState.notify(); }
      catch (error) {
        this.version = null;
        this.ready = false;
        document.getElementById('research-version').textContent = '研究服務離線；請啟動固定研究服務';
        window.appState.notify();
      }
    },5000);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) { this.refresh(); this.checkVersion().catch(()=>{}); }
    });
  }
};
document.addEventListener('DOMContentLoaded', () => window.Research.init());
