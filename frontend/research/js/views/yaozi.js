/**
 * catOS Prototype - Yaozi Market Intelligence View
 * Integrated strictly into the same fixed left sidebar.
 * Features:
 * - Intelligence Overview list (Source, Timestamp, Category)
 * - Category labels explicitly marked with [待確認示意]
 * - Detailed analysis pane on select
 * - Explicit boundary notice: Intelligence DOES NOT auto-modify strategies or trigger orders.
 */

window.YaoziView = {
  render: function(state) {
    const data = window.CATOS_DATA;
    const selectedId = state.selectedYaoziId || data.yaozi[0].id;
    const currentItem = data.yaozi.find(y => y.id === selectedId) || data.yaozi[0];

    return `
      <div class="yaozi-view-container">
        <!-- System Boundary Alert Notice -->
        <div class="alert-banner alert-banner-info" style="margin-bottom:8px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            <span><strong>Yaozi 情報架構隔離規範：</strong>本模組情報僅供量化研究員宏觀參考，未直連自動交易管線，絕不自動修改在線策略或觸發委託。</span>
          </div>
          <span class="badge badge-gold">[待確認示意 Prototype]</span>
        </div>

        <!-- 2 Column Layout: Left List + Right Detail Pane -->
        <div class="yaozi-layout">
          <!-- Left List (340px) -->
          <div class="yaozi-list">
            <div style="font-size:12px; font-weight:600; color:var(--text-secondary); margin-bottom:4px; display:flex; justify-content:space-between;">
              <span>情報快報總覽</span>
              <span class="num">${data.yaozi.length} 則</span>
            </div>

            ${data.yaozi.map(item => `
              <div class="yaozi-card ${item.id === selectedId ? 'active' : ''}" onclick="window.YaoziView.selectItem('${item.id}')">
                <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
                  <span class="badge ${item.urgency === 'HIGH' ? 'badge-amber' : 'badge-gold'}" style="font-size:10px;">
                    ${item.categoryTag}
                  </span>
                  <span class="num" style="font-size:11px; color:var(--text-muted);">${item.timestamp.split(' ')[1]}</span>
                </div>
                <div style="font-size:13.5px; font-weight:600; color:var(--text-primary); margin-bottom:6px; line-height:1.35;">
                  ${item.title}
                </div>
                <div style="font-size:12px; color:var(--text-secondary); line-height:1.4; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">
                  ${item.summary}
                </div>
                <div style="display:flex; align-items:center; justify-content:space-between; margin-top:8px; font-size:11px; color:var(--text-muted); border-top:1px solid var(--border-subtle); padding-top:6px;">
                  <span>來源: ${item.source}</span>
                  <span style="color:var(--gold-primary);">查看分析 &rarr;</span>
                </div>
              </div>
            `).join('')}
          </div>

          <!-- Right Detail Pane -->
          <div class="yaozi-detail-pane">
            <div style="display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:12px; border-bottom:1px solid var(--border-subtle); padding-bottom:12px;">
              <div>
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
                  <span class="badge badge-gold">${currentItem.categoryTag}</span>
                  <span class="badge ${currentItem.urgency === 'HIGH' ? 'badge-amber' : 'badge'}">急迫度: ${currentItem.urgency}</span>
                  <span class="num" style="color:var(--text-muted); font-size:12px;">${currentItem.timestamp}</span>
                </div>
                <div style="font-size:18px; font-weight:700; color:var(--text-primary); line-height:1.3;">
                  ${currentItem.title}
                </div>
                <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">情報來源: ${currentItem.source}</div>
              </div>

              <div>
                <button class="btn btn-sm btn-ghost" onclick="alert('已將情報標記並發送至歷史研究筆記本')">收藏備份</button>
              </div>
            </div>

            <!-- Key Metric Indicators of the Intelligence -->
            <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin-bottom:8px;">
              ${Object.entries(currentItem.metrics).map(([key, val]) => `
                <div style="padding:10px 12px; background:var(--bg-surface); border-radius:var(--border-radius-sm); border:1px solid var(--border-subtle);">
                  <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px; text-transform:uppercase;">${key}</div>
                  <div class="num" style="font-size:15px; font-weight:700; color:var(--gold-primary);">${val}</div>
                </div>
              `).join('')}
            </div>

            <!-- Detailed Analysis Content -->
            <div class="panel" style="margin-bottom:8px;">
              <div class="panel-header">
                <div class="panel-title">市場情報深度剖析與量化相關性</div>
              </div>
              <div class="panel-body">
                <pre class="code-text" style="font-size:13px; color:var(--text-primary); line-height:1.6; white-space:pre-wrap; font-family:var(--font-sans);">${escapeHtml(currentItem.analysisDetail)}</pre>
              </div>
            </div>

            <!-- Action Prompt for Research without Direct Trading Integration -->
            <div style="padding:12px 14px; background:var(--bg-surface); border-radius:var(--border-radius); border:1px solid var(--border-default); display:flex; align-items:center; justify-content:space-between;">
              <div>
                <div style="font-size:13px; font-weight:600; color:var(--text-primary);">是否將此情報之特徵假設轉化為策略濾網？</div>
                <div style="font-size:12px; color:var(--text-muted);">可於策略中心開展新草稿回測驗證，不直接對生產 Bot 造成變更。</div>
              </div>
              <button class="btn btn-sm btn-gold" onclick="window.appState.set({ activePage: 'strategy', strategySubTab: 'optimize' })">
                前往策略中心驗證濾網
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  },

  selectItem: function(itemId) {
    window.appState.set({ selectedYaoziId: itemId });
  }
};
