/**
 * catOS Prototype - Risk Management View
 * Strictly adheres to CatOS Quantitative Risk Architecture:
 * - Effective Leverage, Per-Asset Exposure Budgets, Daily Loss
 * - Soft Loss Threshold (Warn + Halt new orders), Hard Loss Threshold (Circuit breaker + Liquidate)
 * - Latch Status & Incident Reasons
 * - Distinction between Threshold Edits (Config) and Manual Unlatch (Recovery Action)
 * - NO invented VaR or ungrounded financial rules.
 * - Missing data displays '—' with explicit reason.
 */

window.RiskView = {
  render: function(state) {
    const data = window.CATOS_DATA;
    const scenario = state.scenario || 'active';
    const isEmpty = scenario === 'empty';
    const isLatch = scenario === 'risk_latch';

    // Status derivation
    const latchStatus = isEmpty ? 'NORMAL' : (isLatch ? 'SOFT_LATCH' : data.risk.latchState);
    const latchReason = isEmpty ? '無運行中持倉數據' : (isLatch ? '觸發紀錄：盤中曾達 -10.20%，超過 Soft 限額 (-10.0%)，現反彈至 -2.85%，依風控鎖存安全機制持續禁止新開倉。' : data.risk.latchReason);

    const effectiveLev = isEmpty ? '—' : (isLatch ? '2.10x' : data.risk.effectiveLeverage);
    const effectiveLevReason = isEmpty ? '（Supervisor 尚無持倉數據）' : '';

    const dailyLossVal = isEmpty ? '0.00 USDT' : (isLatch ? '-3,580.00 USDT (-2.85%)' : data.risk.dailyLoss);
    const dailyLossColor = isEmpty ? '' : (isLatch ? 'var(--color-red)' : 'var(--text-primary)');

    const draft = state.riskDraft || data.risk.settings;
    const hasChanges = state.riskDraftChanged || false;

    return `
      <div class="risk-view-container">
        <!-- Latch Status Alert Banner -->
        ${latchStatus !== 'NORMAL' ? `
          <div class="alert-banner alert-banner-danger" style="margin-bottom:8px;">
            <div style="display:flex; align-items:center; gap:10px;">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <div>
                <div style="font-weight:700; font-size:14px;">風控鎖存警報觸發：${latchStatus} (禁止新委託)</div>
                <div style="font-size:12px; opacity:0.9; margin-top:2px;">${latchReason}</div>
              </div>
            </div>
            <div style="display:flex; gap:8px;">
              <button class="btn btn-sm btn-solid-gold" onclick="window.RiskView.openUnlatchModal()">
                人工審核解鎖 (Manual Unlatch)
              </button>
            </div>
          </div>
        ` : `
          <div class="alert-banner alert-banner-info" style="margin-bottom:8px;">
            <div style="display:flex; align-items:center; gap:8px;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              <span><strong>風控引擎狀態正常：</strong>全部持倉與當日損益均在設定之 Soft / Hard 門檻安全邊界內。</span>
            </div>
            <span class="badge badge-green">鎖存狀態: NORMAL</span>
          </div>
        `}

        <!-- 4 Key Risk KPI Cards -->
        <div class="risk-kpi-grid">
          <div class="kpi-card">
            <div class="kpi-label">有效帳戶槓桿 (Effective Leverage)</div>
            <div class="kpi-value num">${effectiveLev} <span style="font-size:12px; color:var(--text-muted); font-weight:normal;">/ 限制 ${data.risk.maxAllowedLeverage}</span></div>
            <div class="kpi-sub">${effectiveLevReason || '總部位市值 / 帳戶淨值'}</div>
          </div>

          <div class="kpi-card">
            <div class="kpi-label">今日累積虧損 (Daily Loss)</div>
            <div class="kpi-value num" style="color:${dailyLossColor};">${dailyLossVal}</div>
            <div class="kpi-sub">${isLatch ? '盤中最高回撤 -10.20% · 觸發軟限鎖存' : '基準重設時間: 00:00:00 UTC+8'}</div>
          </div>

          <div class="kpi-card">
            <div class="kpi-label">Soft 警報門檻 (Soft Limit)</div>
            <div class="kpi-value num" style="color:var(--color-amber);">${data.risk.softLossThreshold}</div>
            <div class="kpi-sub">觸發行動：發送警示，禁止所有新開倉</div>
          </div>

          <div class="kpi-card">
            <div class="kpi-label">Hard 停機門檻 (Hard Circuit)</div>
            <div class="kpi-value num" style="color:var(--color-red);">${data.risk.hardLossThreshold}</div>
            <div class="kpi-sub">觸發行動：全自動市價清倉並硬鎖存</div>
          </div>
        </div>

        <!-- 2 Column Layout: Left Asset Exposure Budget & Right Config Editor -->
        <div class="risk-editor-grid">
          <!-- Left: Single-Asset Exposure Budgets -->
          <div class="panel">
            <div class="panel-header">
              <div class="panel-title">
                <span>單幣曝險預算監控 (Per-Asset Exposure)</span>
                <span class="badge badge-gold">即時保證金分配</span>
              </div>
            </div>
            <div class="panel-body" style="padding:0;">
              ${isEmpty ? `
                <div class="empty-state-notice" style="padding:36px;">
                  <div class="title">無資產曝險數據</div>
                  <div style="font-size:12px;">原因：目前尚未啟動任何 Bot，帳戶無活躍持倉。</div>
                </div>
              ` : `
                <table class="data-table" style="border:none;">
                  <thead>
                    <tr>
                      <th>標的幣種</th>
                      <th>持倉名義價值 (USDT)</th>
                      <th>當前曝險比率</th>
                      <th>預算上限</th>
                      <th>狀態</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${data.risk.assetAllocations.map(a => `
                      <tr>
                        <td style="font-weight:600; color:var(--text-primary);">${a.asset}</td>
                        <td class="num">${a.valueUsdt}</td>
                        <td class="num" style="font-weight:600;">${a.currentExposure}</td>
                        <td class="num" style="color:var(--text-muted);">${a.budgetLimit}</td>
                        <td>
                          <span class="badge ${a.status === 'Normal' ? 'badge-green' : 'badge-cyan'}">
                            ${a.status}
                          </span>
                        </td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              `}
            </div>
          </div>

          <!-- Right: Risk Config Editor & Change Summary (Modern Institutional Property Rows) -->
          <div class="panel">
            <div class="panel-header">
              <div class="panel-title">
                <span>風控參數設定 (Risk Parameters)</span>
                ${hasChanges ? `<span class="badge badge-amber">有未套用之變更</span>` : '<span class="badge" style="font-size:10px;">SUPERVISOR SYNC</span>'}
              </div>
            </div>
            <div class="panel-body" style="padding:14px;">

              <!-- 1. Soft Loss Property Row -->
              <div class="property-row-card">
                <div class="property-info">
                  <div class="property-title">
                    <span>Soft Loss 警戒日損門檻</span>
                    <span class="badge badge-amber" style="font-size:10px; padding:1px 5px;">警告鎖存</span>
                  </div>
                  <div class="property-desc">觸發時鎖存禁止新開倉，持倉平倉不受限</div>
                  <div class="property-calc-hint">
                    折合虧損達 <strong>-${((125480 * parseFloat(draft.softLossPct || 10)) / 100).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})} USDT</strong> 時觸發
                  </div>
                </div>

                <div class="property-controls">
                  <div class="property-presets">
                    <span class="preset-chip ${draft.softLossPct === '5.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('softLossPct', '5.0')">5%</span>
                    <span class="preset-chip ${draft.softLossPct === '10.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('softLossPct', '10.0')">10%</span>
                    <span class="preset-chip ${draft.softLossPct === '15.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('softLossPct', '15.0')">15%</span>
                  </div>

                  <div class="stepper-input-group">
                    <button class="stepper-btn" onclick="window.RiskView.stepDraft('softLossPct', -0.5, 1.0, 50.0)" title="減少 0.5%">−</button>
                    <input type="text" class="stepper-input" value="${draft.softLossPct}" oninput="window.RiskView.onDraftChange('softLossPct', this.value)">
                    <button class="stepper-btn" onclick="window.RiskView.stepDraft('softLossPct', 0.5, 1.0, 50.0)" title="增加 0.5%">+</button>
                    <span class="stepper-unit">%</span>
                  </div>
                </div>
              </div>

              <!-- 2. Hard Loss Property Row -->
              <div class="property-row-card">
                <div class="property-info">
                  <div class="property-title">
                    <span>Hard Loss 停機日損門檻</span>
                    <span class="badge badge-red" style="font-size:10px; padding:1px 5px;">強制清倉</span>
                  </div>
                  <div class="property-desc">觸發時強制全數平倉並全面切斷委託路由</div>
                  <div class="property-calc-hint">
                    折合虧損達 <strong>-${((125480 * parseFloat(draft.hardLossPct || 15)) / 100).toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})} USDT</strong> 時觸發
                  </div>
                </div>

                <div class="property-controls">
                  <div class="property-presets">
                    <span class="preset-chip ${draft.hardLossPct === '10.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('hardLossPct', '10.0')">10%</span>
                    <span class="preset-chip ${draft.hardLossPct === '15.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('hardLossPct', '15.0')">15%</span>
                    <span class="preset-chip ${draft.hardLossPct === '20.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('hardLossPct', '20.0')">20%</span>
                  </div>

                  <div class="stepper-input-group">
                    <button class="stepper-btn" onclick="window.RiskView.stepDraft('hardLossPct', -0.5, 2.0, 80.0)" title="減少 0.5%">−</button>
                    <input type="text" class="stepper-input" value="${draft.hardLossPct}" oninput="window.RiskView.onDraftChange('hardLossPct', this.value)">
                    <button class="stepper-btn" onclick="window.RiskView.stepDraft('hardLossPct', 0.5, 2.0, 80.0)" title="增加 0.5%">+</button>
                    <span class="stepper-unit">%</span>
                  </div>
                </div>
              </div>

              <!-- 3. Max Leverage Property Row -->
              <div class="property-row-card">
                <div class="property-info">
                  <div class="property-title">
                    <span>全帳戶最大有效槓桿上限</span>
                  </div>
                  <div class="property-desc">限制總部位名義價值相對於帳戶淨值之最高倍率</div>
                  <div class="property-calc-hint">
                    最高允許名義持倉：<strong>${((125480 * parseFloat(draft.maxLeverage || 3))).toLocaleString('en-US', {minimumFractionDigits:0, maximumFractionDigits:0})} USDT</strong>
                  </div>
                </div>

                <div class="property-controls">
                  <div class="property-presets">
                    <span class="preset-chip ${draft.maxLeverage === '2.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('maxLeverage', '2.0')">2.0x</span>
                    <span class="preset-chip ${draft.maxLeverage === '3.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('maxLeverage', '3.0')">3.0x</span>
                    <span class="preset-chip ${draft.maxLeverage === '5.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('maxLeverage', '5.0')">5.0x</span>
                  </div>

                  <div class="stepper-input-group">
                    <button class="stepper-btn" onclick="window.RiskView.stepDraft('maxLeverage', -0.5, 1.0, 20.0)" title="減少 0.5x">−</button>
                    <input type="text" class="stepper-input" value="${draft.maxLeverage}" oninput="window.RiskView.onDraftChange('maxLeverage', this.value)">
                    <button class="stepper-btn" onclick="window.RiskView.stepDraft('maxLeverage', 0.5, 1.0, 20.0)" title="增加 0.5x">+</button>
                    <span class="stepper-unit">x</span>
                  </div>
                </div>
              </div>

              <!-- 4. Max Single Asset Exposure Property Row -->
              <div class="property-row-card">
                <div class="property-info">
                  <div class="property-title">
                    <span>單幣最大曝險預算上限</span>
                  </div>
                  <div class="property-desc">單一標的持倉佔帳戶總資產權益之最高比例</div>
                  <div class="property-calc-hint">
                    單幣持倉上限額度：<strong>${((125480 * parseFloat(draft.maxSingleAssetExposurePct || 50)) / 100).toLocaleString('en-US', {minimumFractionDigits:0, maximumFractionDigits:0})} USDT</strong>
                  </div>
                </div>

                <div class="property-controls">
                  <div class="property-presets">
                    <span class="preset-chip ${draft.maxSingleAssetExposurePct === '30.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('maxSingleAssetExposurePct', '30.0')">30%</span>
                    <span class="preset-chip ${draft.maxSingleAssetExposurePct === '50.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('maxSingleAssetExposurePct', '50.0')">50%</span>
                    <span class="preset-chip ${draft.maxSingleAssetExposurePct === '70.0' ? 'active' : ''}" onclick="window.RiskView.setPreset('maxSingleAssetExposurePct', '70.0')">70%</span>
                  </div>

                  <div class="stepper-input-group">
                    <button class="stepper-btn" onclick="window.RiskView.stepDraft('maxSingleAssetExposurePct', -5.0, 5.0, 100.0)" title="減少 5%">−</button>
                    <input type="text" class="stepper-input" value="${draft.maxSingleAssetExposurePct}" oninput="window.RiskView.onDraftChange('maxSingleAssetExposurePct', this.value)">
                    <button class="stepper-btn" onclick="window.RiskView.stepDraft('maxSingleAssetExposurePct', 5.0, 5.0, 100.0)" title="增加 5%">+</button>
                    <span class="stepper-unit">%</span>
                  </div>
                </div>
              </div>

              <!-- Change Summary Alert -->
              ${hasChanges ? `
                <div style="background:rgba(230, 184, 64, 0.08); border:1px solid var(--border-gold-subtle); border-radius:var(--border-radius-sm); padding:10px 12px; margin-top:12px; margin-bottom:12px;">
                  <div style="font-size:12px; font-weight:600; color:var(--gold-primary); margin-bottom:2px;">變更待確認 (Pending Changes)：</div>
                  <div style="font-size:11.5px; color:var(--text-secondary);">
                    風控設定已修改，尚未寫入 Supervisor 記憶體。點擊下方「套用風控設定」生效。
                  </div>
                </div>
              ` : ''}

              <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:14px;">
                <button class="btn btn-sm btn-ghost" onclick="window.RiskView.resetDraft()" ${!hasChanges ? 'disabled' : ''}>放棄變更</button>
                <button class="btn btn-sm btn-solid-gold" onclick="window.RiskView.applySettings()" ${!hasChanges ? 'disabled' : ''}>
                  套用風控設定 (Apply Rules)
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Distinct Action: Manual Unlatch Modal -->
        <div class="modal-overlay ${state.unlatchModalOpen ? 'open' : ''}" onclick="window.RiskView.closeUnlatchModal()">
          <div class="modal-dialog" onclick="event.stopPropagation();">
            <div class="modal-header">
              <div class="modal-title" style="color:var(--color-amber);">人工解除風控鎖存二次確認 (Manual Unlatch)</div>
              <button class="btn btn-sm btn-ghost" onclick="window.RiskView.closeUnlatchModal()">✕</button>
            </div>
            <div class="modal-body">
              <div style="font-size:13px; color:var(--text-primary); line-height:1.5; margin-bottom:14px;">
                【操作警告】此操作與「修改風控門檻」不同。解除鎖存將重新允許所有 Bot 向 OKX 交易所提交開倉訂單。
              </div>
              <div style="background:var(--bg-surface); padding:10px; border-radius:var(--border-radius-sm); border:1px solid var(--border-subtle); font-size:12px; color:var(--text-secondary); margin-bottom:14px;">
                <strong>觸發原因紀錄：</strong>${latchReason}
              </div>
              <div class="form-group">
                <label class="form-label">請輸入操作原因備註 (必填，將記入 Audit 日誌)：</label>
                <input type="text" id="unlatch-reason-input" class="form-input" placeholder="例如：人工已核查行情波動已平緩，恢復正常排程">
              </div>
            </div>
            <div class="modal-footer">
              <button class="btn btn-ghost" onclick="window.RiskView.closeUnlatchModal()">取消</button>
              <button class="btn btn-solid-gold" onclick="window.RiskView.confirmUnlatch()">
                確認解除鎖存並恢復交易
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  },

  onDraftChange: function(field, val) {
    const draft = Object.assign({}, window.appState.get('riskDraft') || window.CATOS_DATA.risk.settings);
    draft[field] = val;
    window.appState.set({
      riskDraft: draft,
      riskDraftChanged: true
    });
  },

  setPreset: function(field, val) {
    this.onDraftChange(field, String(val));
  },

  stepDraft: function(field, delta, min, max) {
    const draft = Object.assign({}, window.appState.get('riskDraft') || window.CATOS_DATA.risk.settings);
    let curr = parseFloat(draft[field]) || 0;
    let next = Math.min(Math.max(curr + delta, min), max);
    draft[field] = next.toFixed(1);
    window.appState.set({
      riskDraft: draft,
      riskDraftChanged: true
    });
  },

  resetDraft: function() {
    window.appState.set({
      riskDraft: window.CATOS_DATA.risk.settings,
      riskDraftChanged: false
    });
  },

  applySettings: function() {
    const draft = window.appState.get('riskDraft');
    window.CATOS_DATA.risk.settings = Object.assign({}, draft);
    window.CATOS_DATA.risk.softLossThreshold = `-${draft.softLossPct}%`;
    window.CATOS_DATA.risk.hardLossThreshold = `-${draft.hardLossPct}%`;
    window.CATOS_DATA.risk.maxAllowedLeverage = `${draft.maxLeverage}x`;
    window.appState.set({ riskDraftChanged: false });
    alert('風控參數已成功套用並廣播至 Supervisor 內核。');
  },

  openUnlatchModal: function() {
    window.appState.set({ unlatchModalOpen: true });
  },

  closeUnlatchModal: function() {
    window.appState.set({ unlatchModalOpen: false });
  },

  confirmUnlatch: function() {
    const input = document.getElementById('unlatch-reason-input');
    const reason = input ? input.value.trim() : '';
    if (!reason) {
      alert('請務必輸入操作原因備註！');
      return;
    }
    alert(`【解鎖成功】已寫入審計日誌。\n原因：${reason}\n系統恢復 NORMAL 狀態。`);
    window.appState.set({
      unlatchModalOpen: false,
      scenario: 'active'
    });
  }
};
