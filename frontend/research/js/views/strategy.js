/* Registered research view; retains the prototype shell and panel styles. */
window.StrategyView = {
  render(state) {
    const lab = window.Research;
    if (!lab || !lab.catalog) return `<div class="research-status">${lab?.error ? lab.escape(lab.error) : '載入研究策略與資料…'}</div>`;
    const strategy = lab.catalog.strategies[0];
    if (!state.strategyInDetail) {
      return `<div class="strategy-library-container">
        <div class="research-notice">正式研究回測 · 合成資料。選定受信版本後執行 Decimal 核心；其他主頁仍為原型示意。</div>
        <div class="strategy-cards-grid"><div class="strategy-card" role="button" tabindex="0"
          onclick="window.StrategyView.openDetail()" onkeydown="if(event.key==='Enter')window.StrategyView.openDetail()">
          <div class="panel-header"><span>${lab.escape(strategy.name)}</span><span class="badge badge-gold">受信研究版本</span></div>
          <div class="research-details">BTC-USDT-SWAP · 15m · Long / Flat<br>
          版本 ${lab.escape(strategy.version)}<br>SHA256 ${strategy.sha256.slice(0,12)}<br><br>
          已收盤 K 線決策，下一根開盤成交。<br>不連交易所；不建立 Bot。</div>
        </div></div>
      </div>`;
    }
    const tab = state.strategySubTab || 'strategy';
    return `<div class="strategy-detail-container">
      <div class="research-notice"><button class="btn btn-sm btn-ghost" onclick="window.StrategyView.back()">← 策略中心</button>
        ${lab.escape(strategy.name)} · ${lab.escape(strategy.version)} · 合成研究</div>
      <div class="sub-tabs-bar">
        ${[['strategy','策略'],['backtest','回測'],['optimize','參數優化']].map(([id,label]) =>
          `<button class="sub-tab-btn ${tab === id ? 'active' : ''}" onclick="window.StrategyView.switchSubTab('${id}')">${label}</button>`).join('')}
      </div>
      ${tab === 'strategy' ? `<div class="panel research-details">
        <h3>SMA 趨勢 · 受信製品</h3><p>沿用既有 SMATrend 的 Long / Flat 規則：收盤價高於 SMA 時目標為指定張數，否則空倉。</p>
        <p>可設定 SMA 週期與目標張數。預熱只更新指標；績效不含預熱。單合約、單週期、市價意圖。</p>
        <p>合約規格為合成研究 fixture：每張 0.01 BTC、tick 0.01、lot 1、最小 1 張。資金費事件明示為空。</p>
        <p>不含保證金、強平與帳戶級風控；最後一筆意圖可能未成交，終點不自動平倉。</p>
        <p class="num">SHA256 ${strategy.sha256}</p>
        <button class="btn btn-gold" onclick="window.StrategyView.switchSubTab('backtest')">設定並執行回測</button>
      </div>` : ''}
      ${tab === 'backtest' ? lab.renderBacktest(state) : ''}
      ${tab === 'optimize' ? lab.renderOptimization(state) : ''}
    </div>`;
  },
  afterRender(state) {
    if (state.strategyInDetail && state.strategySubTab === 'backtest') window.Research.drawCurve();
  },
  openDetail() { window.appState.set({strategyInDetail:true, selectedStrategyId:'sma-trend', strategySubTab:'strategy'}); },
  back() { window.appState.set({strategyInDetail:false}); },
  switchSubTab(tab) { window.appState.set({strategySubTab:tab}); }
};
