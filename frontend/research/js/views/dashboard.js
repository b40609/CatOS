/**
 * catOS Prototype - Dashboard View (High Performance 12-Column Grid Workspace)
 *
 * 核心視覺與流暢度升級：
 * 1. 消除壓扁：高度飽滿舒展 (cellHeight 76px)，走勢圖與事件軸大氣擴展，消滅底部多餘黑塊。
 * 2. 60fps OS 流暢感：拖曳期間凍結重繪防抖，Apple 物理吸附曲線。
 * 3. 智慧自動補齊：階梯磁吸 (3/4/6/8/12) 與頂部工具列「⚡ 自動補齊 (Auto-Pack)」一鍵對齊。
 * 4. 嚴格鎖定防誤觸，點擊「⚙ 編輯版面」才展開控制點。
 */

window.DashboardView = {
  render: function(state) {
    const data = window.CATOS_DATA;
    const scenario = state.scenario || 'active';
    const isEmpty = scenario === 'empty';
    const isLatch = scenario === 'risk_latch';
    const expandedIncId = state.expandedIncidentId;

    const equityVal = isEmpty ? '— USDT' : (isLatch ? '121,900.50 USDT' : data.risk.totalAccountEquity);
    const pnlVal = isEmpty ? '0.00 USDT' : (isLatch ? '-3,580.00 USDT (-2.85%)' : data.risk.dailyLoss);
    const runningBotsCount = isEmpty ? '0' : '1';
    const riskStatusLabel = isEmpty ? '—' : (isLatch ? 'SOFT-TRIP 鎖存' : 'NORMAL');
    const riskBadgeClass = isEmpty ? 'badge' : (isLatch ? 'badge-amber' : 'badge-green');

    return `
      <div class="dashboard-view-container" style="position:relative;">

        <!-- 一、頂部 Workspace 控制列 (Presets, Edit Mode, Actions) -->
        <div class="workspace-toolbar-bar" id="workspace-toolbar-bar">
          <!-- 左側：官方預設集切換 -->
          <div class="workspace-presets-group">
            <span style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono); margin-right:4px;">
              LAYOUT //
            </span>
            <div class="workspace-preset-pill active" data-preset="executive" onclick="window.WorkspaceEngine.applyPreset('executive')" title="官方平衡版面：KPI + 走勢(8欄) + 事件(4欄)">
              <span class="badge-dot green" style="width:5px; height:5px;"></span>
              <span>戰情總覽</span>
            </div>
            <div class="workspace-preset-pill" data-preset="research" onclick="window.WorkspaceEngine.applyPreset('research')" title="研究員模式：走勢大圖全寬置頂 + 任務情報">
              <span class="badge-dot" style="background:#5c9cff; width:5px; height:5px;"></span>
              <span>研究模式</span>
            </div>
            <div class="workspace-preset-pill" data-preset="sentinel" onclick="window.WorkspaceEngine.applyPreset('sentinel')" title="夜間監控模式：警報時間軸與活躍 Bot 監看置頂">
              <span class="badge-dot amber" style="width:5px; height:5px;"></span>
              <span>夜間監控</span>
            </div>
          </div>

          <!-- 右側：版面快速輔助操作 (可直接移動縮放，無需多餘的切換模式) -->
          <div class="workspace-actions-group">
            <!-- ⚡ 智慧自動補齊按鈕 (常態可用) -->
            <button class="btn-autopack"
                    id="btn-workspace-autopack"
                    onclick="window.WorkspaceEngine.autoPackGrid()"
                    title="一鍵消除水平畸零空白與垂直空洞，將面板完美均分填滿視窗">
              <span>⚡ 自動補滿</span>
            </button>

            <!-- ↶ 復原按鈕 (常態可用，還原操作前的尺寸與排序) -->
            <button class="btn btn-sm btn-ghost"
                    id="btn-workspace-revert"
                    onclick="window.WorkspaceEngine.revertLayout()"
                    style="font-size:11px; gap:4px; height:26px; color:var(--text-muted);"
                    title="復原至操作前的尺寸與排序">
              <span>↶ 復原</span>
            </button>

            <!-- ⟲ 重設按鈕 (常態可用) -->
            <button class="btn btn-sm btn-ghost"
                    id="btn-workspace-reset"
                    onclick="window.WorkspaceEngine.resetLayout()"
                    style="font-size:11px; gap:4px; height:26px; color:var(--text-muted);"
                    title="重設為當前預設集的標準配置">
              <span>⟲ 重設</span>
            </button>

            <!-- 隱藏的按鈕相容自動化測試 -->
            <button class="btn btn-sm btn-ghost btn-edit-mode"
                    id="btn-workspace-edit-toggle"
                    onclick="window.WorkspaceEngine.toggleEditing()"
                    style="display:none;">
              <span>⚙ 編輯版面</span>
            </button>
          </div>
        </div>

        <!-- 二、OKX 原生級 Seamless Tiling Multi-Pane 主畫布容器 (支援連續任意像素拖曳與一鍵填滿) -->
        <div class="catos-grid-stack tiling-workspace-container" id="dashboard-grid-stack">

          <!-- Top Fixed/Foldable Tier: KPI 核心指標網格 -->
          <div class="grid-stack-item tiling-top-panel tiling-pane" id="widget-kpi_grid" gs-id="kpi_grid" gs-w="12" gs-h="2">
            <div class="grid-stack-item-content panel-specular" style="position:relative; top:0; left:0; right:0; bottom:0;">
              <div class="widget-box-header" style="height:32px;">
                <div class="widget-title-wrap">
                  <span class="widget-drag-handle" style="display:none;" aria-hidden="true"></span>
                  <div class="th-dual-zh">帳戶核心指標網格</div>
                  <div class="th-dual-en">KPI TELEMETRY</div>
                </div>
                <div style="display:flex; align-items:center; gap:6px;">
                  <button class="btn-pane-maximize" data-widget="kpi_grid" onclick="window.WorkspaceEngine.toggleMaximize('kpi_grid')" title="最大化面板">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                  </button>
                  <button class="widget-btn-hide" onclick="window.WorkspaceEngine.hideWidget('kpi_grid')" title="隱藏此元件 (可從元件庫重新加回)">&times;</button>
                </div>
              </div>
              <div class="widget-box-body" style="padding:8px 12px; justify-content:center;">
                <div class="kpi-grid" style="margin-bottom:0; gap:8px; height:100%; align-items:stretch;">
                  <!-- KPI 1: Account Equity -->
                  <div class="kpi-card gold-accent" style="padding:8px 12px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div class="kpi-label" style="font-size:11.5px; font-weight:600;">
                      <span>總權益淨值</span>
                    </div>
                    <div class="kpi-value num" style="font-size:18px; margin:2px 0; font-weight:600;">${equityVal}</div>
                    <div class="kpi-sub" style="font-size:11px; line-height:1.25;">實時持倉估值 + 現金餘額</div>
                  </div>
                  <!-- KPI 2: Daily PnL -->
                  <div class="kpi-card" style="padding:8px 12px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div class="kpi-label" style="font-size:11.5px; font-weight:600;">
                      <span>今日損益</span>
                    </div>
                    <div class="kpi-value num" style="font-size:18px; margin:2px 0; font-weight:600; color:${isEmpty ? '' : (isLatch ? 'var(--color-red)' : 'var(--color-green)')};">
                      ${pnlVal}
                    </div>
                    <div class="kpi-sub" style="font-size:11px; line-height:1.25;">今日已實現 + 未實現損益合計</div>
                  </div>
                  <!-- KPI 3: Active Bots -->
                  <div class="kpi-card mini-summary-card" onclick="window.appState.set({ activePage: 'bots' })" style="padding:8px 12px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div class="kpi-label" style="font-size:11.5px; font-weight:600;">
                      <span>運行 Bot 數</span>
                      <span style="font-size:10.5px; color:var(--gold-primary);">機器人 &rarr;</span>
                    </div>
                    <div class="kpi-value num" style="font-size:18px; margin:2px 0; font-weight:600;">
                      1 <span style="font-size:12px; font-weight:normal; color:var(--text-muted);">/ 3 部署總計</span>
                    </div>
                    <div class="kpi-sub" style="font-size:11px; line-height:1.25;">
                      1 運行中 · 1 需處理 · 1 已停止
                    </div>
                  </div>
                  <!-- KPI 4: Risk Status -->
                  <div class="kpi-card mini-summary-card" onclick="window.appState.set({ activePage: 'risk' })" style="padding:8px 12px; display:flex; flex-direction:column; justify-content:space-between;">
                    <div class="kpi-label" style="font-size:11.5px; font-weight:600;">
                      <span>風控狀態</span>
                      <span class="badge ${riskBadgeClass}" style="font-size:10.5px; padding:1px 5px;">${riskStatusLabel}</span>
                    </div>
                    <div class="kpi-value num" style="font-size:16px; margin:2px 0; font-weight:600;">
                      槓桿 ${isEmpty ? '—' : data.risk.effectiveLeverage} <span style="font-size:11.5px; color:var(--text-muted); font-weight:normal;">/ 上限 ${data.risk.maxAllowedLeverage}</span>
                    </div>
                    <div class="kpi-sub" style="font-size:11px; line-height:1.25;">
                      ${isEmpty ? '風控待命中' : (isLatch ? '曾觸發軟限 (-10.20%) 鎖存中 · 現反彈至 -2.85%' : '日損軟限 10.0% · 當前回撤 -0.30%')}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 頂部 KPI 卡片下方水平分割條 (OKX Continuous Resizer) -->
          <div class="workspace-splitter horizontal" id="splitter-h-top" data-top="widget-kpi_grid" data-bottom="tiling-main-area" title="拖曳自訂帳戶核心指標網格高度 (雙擊恢復標準高度)"></div>

          <!-- Main Continuous Split Area (OKX Seamless Tiling) -->
          <div class="tiling-main-area" id="tiling-main-area">

            <!-- 上排面板群 (Upper Tier: 走勢圖 + 警報時間軸) -->
            <div class="tiling-row-tier" id="tiling-upper-tier" style="height:56%;">

              <!-- Pane 1: 走勢圖 -->
              <div class="grid-stack-item tiling-pane" id="widget-equity_chart" gs-id="equity_chart" style="flex:0 0 66%;">
                <div class="tiling-pane-content panel-specular">
                  <div class="widget-box-header">
                    <div class="widget-title-wrap">
                      <span class="widget-drag-handle" style="display:none;" aria-hidden="true"></span>
                      <div class="th-dual-zh">帳戶淨值走勢</div>
                      <div class="th-dual-en">EQUITY CURVE</div>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                      <div class="time-range-selector">
                        <button class="time-btn" onclick="window.DashboardView.changeTimeRange('7D')">7D</button>
                        <button class="time-btn active" onclick="window.DashboardView.changeTimeRange('30D')">30D</button>
                        <button class="time-btn" onclick="window.DashboardView.changeTimeRange('90D')">90D</button>
                      </div>
                      <button class="btn-pane-maximize" data-widget="equity_chart" onclick="window.WorkspaceEngine.toggleMaximize('equity_chart')" title="最大化面板">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                      </button>
                      <button class="widget-btn-hide" onclick="window.WorkspaceEngine.hideWidget('equity_chart')" title="隱藏此元件">&times;</button>
                    </div>
                  </div>
                  <div class="widget-box-body" style="display:flex; flex-direction:column; padding:12px 14px; flex:1; min-height:0;">
                    <div id="dashboard-equity-chart" class="chart-canvas-box" style="flex:1; width:100%; min-height:180px;"></div>
                    <div style="display:flex; justify-content:space-between; font-size:11px; color:var(--text-muted); margin-top:6px; padding-top:4px; border-top:1px solid var(--border-subtle); flex-shrink:0;">
                      <span>撮合基準：離線歷史模擬數據 (未連線真實交易所)</span>
                      <span>滑價損耗模型啟用</span>
                      <span>更新頻率：每 1m K 線收盤</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 垂直分割條 1 (OKX Continuous Resizer) -->
              <div class="workspace-splitter vertical" id="splitter-v-upper" data-left="widget-equity_chart" data-right="widget-incident_timeline" title="拖曳自訂左右寬度 (雙擊恢復平衡比例)"></div>

              <!-- Pane 2: 警報時間軸 -->
              <div class="grid-stack-item tiling-pane" id="widget-incident_timeline" gs-id="incident_timeline" style="flex:0 0 34%;">
                <div class="tiling-pane-content panel-specular">
                  <div class="widget-box-header">
                    <div class="widget-title-wrap">
                      <span class="widget-drag-handle" style="display:none;" aria-hidden="true"></span>
                      <div class="th-dual-zh">系統警報與事件時間軸</div>
                      <div class="th-dual-en">INCIDENT STREAM</div>
                    </div>
                    <div style="display:flex; align-items:center; gap:8px;">
                      <span style="font-size:11px; color:var(--gold-primary); cursor:pointer;" onclick="window.appState.set({ activePage: 'logs' })">完整日誌 &rarr;</span>
                      <button class="btn-pane-maximize" data-widget="incident_timeline" onclick="window.WorkspaceEngine.toggleMaximize('incident_timeline')" title="最大化面板">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                      </button>
                      <button class="widget-btn-hide" onclick="window.WorkspaceEngine.hideWidget('incident_timeline')" title="隱藏此元件">&times;</button>
                    </div>
                  </div>
                  <div class="widget-box-body" style="overflow-y:auto; padding:12px 14px; flex:1;">
                    ${isEmpty ? `
                      <div class="empty-state-notice" style="padding:24px 8px;">
                        <div class="title">無待處理事件</div>
                        <div style="font-size:12px;">系統待命中，尚無異常事件觸發。</div>
                      </div>
                    ` : `
                      <div class="timeline-rail-wrap">
                        ${data.meta.incidents.map(inc => {
                          const isExp = expandedIncId === inc.id;
                          return `
                            <div class="timeline-node-item ${isExp ? 'is-expanded' : ''}" data-incident-id="${inc.id}" onclick="window.DashboardView.toggleIncident('${inc.id}', event)">
                              <div class="timeline-node-dot ${inc.severity}"></div>
                              <div class="timeline-item-header">
                                <span class="num" style="font-size:11px; color:#8c94a4;">${inc.time}</span>
                                <span class="badge ${inc.severity === 'WARN' ? 'badge-amber' : (inc.severity === 'CRIT' ? 'badge-red' : 'badge-cyan')}" style="font-size:11px; padding:1px 5px;">
                                  ${inc.severity}
                                </span>
                                <span class="timeline-item-title" style="font-size:12.5px;">${inc.title}</span>
                                <span class="incident-arrow" style="font-size:10.5px; color:var(--text-muted); margin-left:auto;">${isExp ? '▲' : '▼'}</span>
                              </div>
                              <div class="timeline-expanded-box" onclick="event.stopPropagation();" style="display:${isExp ? 'block' : 'none'}; margin-top:6px; padding:8px 10px;">
                                <div style="margin-bottom:6px; color:var(--text-primary); font-size:12.5px;">${inc.reason}</div>
                                <div style="display:flex; align-items:center; gap:8px; font-size:11px; border-top:1px solid var(--border-subtle); padding-top:5px;">
                                  <span>來源: <code class="mono">${inc.source}</code></span>
                                  ${inc.targetBotId ? `
                                    <a href="javascript:void(0)" onclick="window.appState.set({ activePage: 'bots', selectedBotId: '${inc.targetBotId}', botDrawerOpen: true })" style="color:var(--gold-primary); font-weight:500;">
                                      查看 Bot 詳情 &rarr;
                                    </a>
                                  ` : ''}
                                  <a href="javascript:void(0)" onclick="window.appState.set({ activePage: 'logs', logsFilter: { ...window.appState.get('logsFilter'), target: '${inc.logQuery}' } })" style="color:var(--text-muted);">
                                    相關日誌 &rarr;
                                  </a>
                                </div>
                              </div>
                            </div>
                          `;
                        }).join('')}
                      </div>
                    `}
                  </div>
                </div>
              </div>

            </div>

            <!-- 水平分割條 (調整上下兩排高度) -->
            <div class="workspace-splitter horizontal" id="splitter-h-main" data-top="tiling-upper-tier" data-bottom="tiling-lower-tier" title="拖曳自訂上下高度 (雙擊恢復平衡比例)"></div>

            <!-- 下排面板群 (Lower Tier: Bot 隊列 + 研究任務 + Yaozi 情報) -->
            <div class="tiling-row-tier" id="tiling-lower-tier" style="height:44%;">

              <!-- Pane 3: Bot 隊列 -->
              <div class="grid-stack-item tiling-pane" id="widget-active_bots" gs-id="active_bots" style="flex:0 0 33.33%;">
                <div class="tiling-pane-content panel-specular">
                  <div class="widget-box-header">
                    <div class="widget-title-wrap">
                      <span class="widget-drag-handle" style="display:none;" aria-hidden="true"></span>
                      <div class="th-dual-zh">運行中 Bot 隊列</div>
                      <div class="th-dual-en">ACTIVE BOTS</div>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                      <span class="badge ${isEmpty ? '' : 'badge-green'}" style="font-size:11px; padding:2px 6px;">1 運行中 · 1 需處理</span>
                      <button class="btn-pane-maximize" data-widget="active_bots" onclick="window.WorkspaceEngine.toggleMaximize('active_bots')" title="最大化面板">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                      </button>
                      <button class="widget-btn-hide" onclick="window.WorkspaceEngine.hideWidget('active_bots')" title="隱藏此元件">&times;</button>
                    </div>
                  </div>
                  <div class="widget-box-body" style="padding:10px 12px; overflow-y:auto; flex:1;">
                    <div style="display:flex; flex-direction:column; gap:8px;">
                      ${data.bots.filter(b => b.status === 'RUNNING' || b.status === 'WARNING').slice(0, 3).map((b) => `
                        <div style="display:flex; align-items:center; justify-content:space-between; padding:8px 10px; background:var(--bg-surface); border-radius:2px; border:1px solid var(--border-subtle); cursor:pointer;" onclick="window.appState.set({ activePage: 'bots', selectedBotId: '${b.id}', botDrawerOpen: true })">
                          <div>
                            <div style="font-size:13px; font-weight:600; color:var(--text-primary); white-space:nowrap;">${b.name}</div>
                            <div style="font-size:11.5px; color:var(--text-muted); margin-top:2px;">${b.symbol} • ${b.position.direction} ${b.position.amount}</div>
                          </div>
                          <div style="text-align:right;">
                            <div class="num" style="font-size:13px; font-weight:600; color:${parseFloat(b.dailyPnl) >= 0 ? 'var(--color-green)' : 'var(--color-red)'};">${b.dailyPnl}</div>
                            <span class="badge ${b.status === 'RUNNING' ? 'badge-green' : 'badge-amber'}" style="font-size:11px; padding:1px 5px; margin-top:2px; display:inline-block;">${b.status}</span>
                          </div>
                        </div>
                      `).join('')}
                    </div>
                  </div>
                </div>
              </div>

              <!-- 垂直分割條 2 -->
              <div class="workspace-splitter vertical" id="splitter-v-lower-1" data-left="widget-active_bots" data-right="widget-research_tasks" title="拖曳自訂寬度"></div>

              <!-- Pane 4: 近期研究任務 -->
              <div class="grid-stack-item tiling-pane" id="widget-research_tasks" gs-id="research_tasks" style="flex:0 0 33.33%;">
                <div class="tiling-pane-content panel-specular">
                  <div class="widget-box-header">
                    <div class="widget-title-wrap">
                      <span class="widget-drag-handle" style="display:none;" aria-hidden="true"></span>
                      <div class="th-dual-zh">近期研究任務</div>
                      <div class="th-dual-en">RESEARCH QUEUE</div>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                      <span class="badge badge-gold" style="font-size:11px; padding:2px 6px;">回測/優化</span>
                      <button class="btn-pane-maximize" data-widget="research_tasks" onclick="window.WorkspaceEngine.toggleMaximize('research_tasks')" title="最大化面板">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                      </button>
                      <button class="widget-btn-hide" onclick="window.WorkspaceEngine.hideWidget('research_tasks')" title="隱藏此元件">&times;</button>
                    </div>
                  </div>
                  <div class="widget-box-body" style="padding:10px 12px; display:flex; flex-direction:column; gap:8px; overflow-y:auto; flex:1;">
                    <div style="padding:8px 10px; background:var(--bg-surface); border-radius:2px; border:1px solid var(--border-subtle); cursor:pointer;" onclick="window.appState.set({ activePage: 'strategy', strategySubTab: 'backtest' })">
                      <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                        <span style="font-size:12.5px; font-weight:600; color:var(--text-primary);">ATR 動量突破 v1.1 歷史回測</span>
                        <span class="badge badge-green" style="font-size:11px; padding:1px 5px;">完成 100%</span>
                      </div>
                      <div style="font-size:11.5px; color:var(--text-muted);">夏普 2.14 • 淨利 +36.84% • 124 筆撮合</div>
                    </div>

                    <div style="padding:8px 10px; background:var(--bg-surface); border-radius:2px; border:1px solid var(--border-subtle); cursor:pointer;" onclick="window.appState.set({ activePage: 'strategy', strategySubTab: 'optimize' })">
                      <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                        <span style="font-size:12.5px; font-weight:600; color:var(--text-primary);">參數網格優化 (48 迭代)</span>
                        <span class="badge badge-gold" style="font-size:11px; padding:1px 5px;">候選完成</span>
                      </div>
                      <div style="font-size:11.5px; color:var(--text-muted);">最優解 Sharpe 2.38 • 提示：需樣本外檢驗</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 垂直分割條 3 -->
              <div class="workspace-splitter vertical" id="splitter-v-lower-2" data-left="widget-research_tasks" data-right="widget-yaozi_brief" title="拖曳自訂寬度"></div>

              <!-- Pane 5: Yaozi 市場情報快訊 -->
              <div class="grid-stack-item tiling-pane" id="widget-yaozi_brief" gs-id="yaozi_brief" style="flex:0 0 33.34%;">
                <div class="tiling-pane-content panel-specular">
                  <div class="widget-box-header">
                    <div class="widget-title-wrap">
                      <span class="widget-drag-handle" style="display:none;" aria-hidden="true"></span>
                      <div class="th-dual-zh">Yaozi 市場情報快訊</div>
                      <div class="th-dual-en">YAOZI INTEL</div>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                      <span class="badge badge-cyan" style="font-size:11px; padding:2px 6px;">研究參考</span>
                      <button class="btn-pane-maximize" data-widget="yaozi_brief" onclick="window.WorkspaceEngine.toggleMaximize('yaozi_brief')" title="最大化面板">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                      </button>
                      <button class="widget-btn-hide" onclick="window.WorkspaceEngine.hideWidget('yaozi_brief')" title="隱藏此元件">&times;</button>
                    </div>
                  </div>
                  <div class="widget-box-body" style="padding:10px 12px; display:flex; flex-direction:column; gap:8px; overflow-y:auto; flex:1;">
                    ${data.yaozi.slice(0, 2).map(y => `
                      <div style="padding:8px 10px; background:var(--bg-surface); border-radius:2px; border:1px solid var(--border-subtle); cursor:pointer;" onclick="window.appState.set({ activePage: 'yaozi' })">
                        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:2px;">
                          <span class="badge badge-gold" style="font-size:11px; padding:1px 5px;">${y.categoryTag}</span>
                          <span class="num" style="font-size:11px; color:var(--text-muted);">${y.timestamp.split(' ')[1]}</span>
                        </div>
                        <div style="font-size:12.5px; font-weight:600; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${y.title}</div>
                      </div>
                    `).join('')}
                  </div>
                </div>
              </div>

            </div>
          </div>
        </div>

        <!-- 三、Widget Library 抽屜 (從右側滑出加回卡片) -->
        <div class="widget-library-backdrop" id="widget-library-backdrop" onclick="window.WorkspaceEngine.closeWidgetLibrary()"></div>
        <div class="widget-library-panel" id="widget-library-panel">
          <div class="widget-library-header">
            <div>
              <div class="th-dual-zh" style="font-size:13.5px;">元件庫管理</div>
              <div class="th-dual-en" style="font-size:11px;">WIDGET LIBRARY // REPOSITORY</div>
            </div>
            <button class="btn btn-sm btn-ghost" onclick="window.WorkspaceEngine.closeWidgetLibrary()" style="font-size:16px; height:24px; padding:0 6px; color:var(--text-muted);">
              &times;
            </button>
          </div>
          <div class="widget-library-body" id="widget-library-body">
            <!-- 由 WorkspaceEngine.renderWidgetLibraryList() 動態填充 -->
          </div>
        </div>

      </div>
    `;
  },

  afterRender: function(state) {
    // 1. 初始化平鋪工作台 Workspace
    if (window.WorkspaceEngine) {
      window.WorkspaceEngine.init('dashboard-grid-stack', 'dashboard');
    }

    // 2. 渲染權益曲線圖
    if (window.ChartEngine) {
      window.ChartEngine.renderDashboardEquity('dashboard-equity-chart', '30D', state.scenario);
    }

    // 3. 掛載 ResizeObserver 確保走勢圖在卡片拖曳與最大化時同步 100% 響應縮放
    const chartContainer = document.getElementById('dashboard-equity-chart');
    if (chartContainer && typeof ResizeObserver !== 'undefined') {
      if (this._chartResizeObserver) {
        this._chartResizeObserver.disconnect();
      }
      this._chartResizeObserver = new ResizeObserver(() => {
        if (window.ChartEngine && document.getElementById('dashboard-equity-chart')) {
          const timeBtn = document.querySelector('.time-range-selector .time-btn.active');
          const range = timeBtn ? timeBtn.innerText.trim() : '30D';
          window.ChartEngine.renderDashboardEquity('dashboard-equity-chart', range, window.appState ? window.appState.get('scenario') : 'active');
        }
      });
      this._chartResizeObserver.observe(chartContainer);
    }

    // 4. URL 深度連結支援 (例如 ?max=kpi_grid 或 ?max=equity_chart 進入時直接最大化特定面板)
    if (typeof window !== 'undefined' && window.location) {
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const maxParam = urlParams.get('max');
        if (maxParam && window.WorkspaceEngine && !window.WorkspaceEngine.maximizedPaneId) {
          setTimeout(() => {
            window.WorkspaceEngine.toggleMaximize(maxParam);
          }, 100);
        }
      } catch (e) {}
    }
  },

  changeTimeRange: function(range) {
    const btns = document.querySelectorAll('.time-range-selector .time-btn');
    btns.forEach(b => {
      b.classList.toggle('active', b.innerText === range);
    });
    if (window.ChartEngine) {
      window.ChartEngine.renderDashboardEquity('dashboard-equity-chart', range, window.appState.get('scenario'));
    }
  },

  toggleIncident: function(incId, event) {
    if (event) {
      if (typeof event.stopPropagation === 'function') event.stopPropagation();
      if (typeof event.preventDefault === 'function') event.preventDefault();
    }
    const curr = (window.appState && window.appState.get) ? window.appState.get('expandedIncidentId') : null;
    const newId = curr === incId ? null : incId;

    // 更新狀態但不觸發全局重新 render，保護已調整之版面尺寸
    if (window.appState && window.appState.state) {
      window.appState.state.expandedIncidentId = newId;
    }

    const timelineWrap = document.querySelector('.timeline-rail-wrap');
    if (!timelineWrap) return;

    // 就地切換 DOM，零畫面抖動，卡片尺寸 100% 保持不動
    const allNodes = timelineWrap.querySelectorAll('.timeline-node-item');
    allNodes.forEach(node => {
      const isTarget = node.getAttribute('data-incident-id') === incId;
      const arrow = node.querySelector('.incident-arrow');
      const box = node.querySelector('.timeline-expanded-box');
      if (isTarget) {
        const willExpand = (newId === incId);
        if (box) box.style.display = willExpand ? 'block' : 'none';
        if (arrow) arrow.innerText = willExpand ? '▲' : '▼';
        node.classList.toggle('is-expanded', willExpand);
      } else {
        if (box) box.style.display = 'none';
        if (arrow) arrow.innerText = '▼';
        node.classList.remove('is-expanded');
      }
    });
  }
};
