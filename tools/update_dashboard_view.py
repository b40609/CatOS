# -*- coding: utf-8 -*-
import pathlib

FRONTEND_ROOT = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final')

def update_dashboard():
    p = FRONTEND_ROOT / 'js' / 'views' / 'dashboard.js'
    text = p.read_text(encoding='utf-8')

    # 1. 替換 Upper Tier 區塊
    upper_old_start = text.find('<!-- 上排面板群 (Upper Tier: 走勢圖 + 警報時間軸) -->')
    upper_old_end = text.find('<!-- 水平分割條 (調整上下兩排高度) -->')
    if upper_old_start == -1 or upper_old_end == -1:
        raise ValueError("Cannot locate Upper Tier in dashboard.js")

    upper_replacement = """<!-- 上排面板群 (Upper Tier: 走勢圖 + 帳戶保證金配置 + 警報時間軸) -->
            <div class="tiling-row-tier" id="tiling-upper-tier" style="height:54%;">
              
              <!-- Pane 1: 走勢圖 -->
              <div class="grid-stack-item tiling-pane" id="widget-equity_chart" gs-id="equity_chart" style="flex:0 0 48%;">
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
              <div class="workspace-splitter vertical" id="splitter-v-upper-1" data-left="widget-equity_chart" data-right="widget-allocation" title="拖曳自訂左右寬度 (雙擊恢復平衡比例)"></div>

              <!-- Pane 2: 帳戶保證金與曝險配置 (ALLOCATION 甜甜圈圓環圖) -->
              <div class="grid-stack-item tiling-pane" id="widget-allocation" gs-id="allocation" style="flex:0 0 28%;">
                <div class="tiling-pane-content panel-specular">
                  <div class="widget-box-header">
                    <div class="widget-title-wrap">
                      <span class="widget-drag-handle" style="display:none;" aria-hidden="true"></span>
                      <div class="th-dual-zh">:: ALLOCATION // 帳戶保證金與曝險配置</div>
                      <div class="th-dual-en">MARGIN & EXPOSURE ALLOCATION</div>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                      <span class="badge" id="btn-toggle-leverage" style="border:1px solid rgba(220,179,71,0.4); color:var(--gold-primary); font-family:var(--font-mono); font-size:10.5px; padding:2px 6px; cursor:pointer; background:rgba(220,179,71,0.08); border-radius:2px;" onclick="window.DashboardView.toggleLeverageBasis()" title="切換曝險上限 / 淨本金基準">基準: 3.0x 曝險</span>
                      <button class="btn-pane-maximize" data-widget="allocation" onclick="window.WorkspaceEngine.toggleMaximize('allocation')" title="最大化面板">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                      </button>
                      <button class="widget-btn-hide" onclick="window.WorkspaceEngine.hideWidget('allocation')" title="隱藏此元件">&times;</button>
                    </div>
                  </div>
                  <div class="widget-box-body" style="padding:10px 12px; display:flex; flex-direction:column; gap:8px; overflow-y:auto; flex:1;">
                    <!-- 4 態維度切換膠囊 -->
                    <div class="allocation-toolbar">
                      <div class="pill-switch-group" id="allocation-dimension-pills">
                        <button class="pill-switch-btn active" data-dim="margin" onclick="window.DashboardView.switchAllocationDim('margin')">保證金與曝險</button>
                        <button class="pill-switch-btn" data-dim="multi_asset" onclick="window.DashboardView.switchAllocationDim('multi_asset')">多幣組合總覽</button>
                        <button class="pill-switch-btn" data-dim="bots" onclick="window.DashboardView.switchAllocationDim('bots')">Bot 策略幣種</button>
                        <button class="pill-switch-btn" data-dim="positions" onclick="window.DashboardView.switchAllocationDim('positions')">實盤活躍倉位</button>
                      </div>
                      <div style="font-size:10px; color:var(--text-muted); font-family:var(--font-mono); white-space:nowrap;" id="allocation-dim-note">預設：帳戶持倉保證金、在途凍結與風控預算佔比</div>
                    </div>

                    <!-- 甜甜圈主體與右側圖例 -->
                    <div class="allocation-main-row">
                      <div class="donut-chart-container">
                        <svg class="donut-svg" viewBox="0 0 100 100" id="allocation-donut-svg"></svg>
                        <div class="donut-center-hud">
                          <span class="donut-center-label" id="donut-hud-label">總名義曝險</span>
                          <strong class="donut-center-val" id="donut-hud-val">1,420.50 USDT</strong>
                          <span class="donut-center-sub" id="donut-hud-sub">總曝險上限 3,000 USDT</span>
                        </div>
                      </div>

                      <div class="allocation-legend-list" id="allocation-legend-list">
                        <!-- 由 renderAllocation() 動態產生 -->
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 垂直分割條 2 (OKX Continuous Resizer) -->
              <div class="workspace-splitter vertical" id="splitter-v-upper-2" data-left="widget-allocation" data-right="widget-incident_timeline" title="拖曳自訂左右寬度 (雙擊恢復平衡比例)"></div>

              <!-- Pane 3: 警報時間軸 -->
              <div class="grid-stack-item tiling-pane" id="widget-incident_timeline" gs-id="incident_timeline" style="flex:0 0 24%;">
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
"""

    text = text[:upper_old_start] + upper_replacement + text[upper_old_end:]

    # 2. 替換 Lower Tier 區塊
    lower_old_start = text.find('<!-- 下排面板群 (Lower Tier: Bot 隊列 + 研究任務 + Yaozi 情報) -->')
    lower_old_end = text.find('<!-- 三、Widget Library 抽屜 (從右側滑出加回卡片) -->')
    if lower_old_start == -1 or lower_old_end == -1:
        raise ValueError("Cannot locate Lower Tier in dashboard.js")

    lower_replacement = """<!-- 下排面板群 (Lower Tier: 日損鎖存儀表 + Bot 隊列 + 研究任務 + Yaozi 情報) -->
            <div class="tiling-row-tier" id="tiling-lower-tier" style="height:46%;">
              
              <!-- Pane 4: 日損鎖存安全緩衝儀表 (RISK LATCH GAUGE) -->
              <div class="grid-stack-item tiling-pane" id="widget-risk_latch" gs-id="risk_latch" style="flex:0 0 34%;">
                <div class="tiling-pane-content panel-specular">
                  <div class="widget-box-header">
                    <div class="widget-title-wrap">
                      <span class="widget-drag-handle" style="display:none;" aria-hidden="true"></span>
                      <div class="th-dual-zh">:: RISK LATCH GAUGE // 日損鎖存安全緩衝儀表</div>
                      <div class="th-dual-en">DAILY LOSS LATCH & SAFETY BUFFER GAUGE</div>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px;">
                      <span class="badge ${isLatch ? 'badge-amber' : 'badge-green'}" style="font-size:11px; padding:1px 5px;">
                        ${isLatch ? 'SOFT-LATCH 鎖存' : '安全運行中'}
                      </span>
                      <button class="btn-pane-maximize" data-widget="risk_latch" onclick="window.WorkspaceEngine.toggleMaximize('risk_latch')" title="最大化面板">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                      </button>
                      <button class="widget-btn-hide" onclick="window.WorkspaceEngine.hideWidget('risk_latch')" title="隱藏此元件">&times;</button>
                    </div>
                  </div>
                  <div class="widget-box-body" style="padding:10px 12px; display:flex; flex-direction:column; gap:10px; overflow-y:auto; flex:1;">
                    <!-- 四大核心基準指標卡 -->
                    <div class="latch-metric-summary">
                      <div class="latch-summary-item">
                        <span class="latch-summary-label">日初權益基準</span>
                        <span class="latch-summary-val num">${isLatch ? '125,480.50' : '1,000.00'} USDT</span>
                      </div>
                      <div class="latch-summary-item">
                        <span class="latch-summary-label">當前浮動損益</span>
                        <span class="latch-summary-val num" style="color:${isLatch ? 'var(--color-red)' : 'var(--color-green)'};">
                          ${isLatch ? '-3,580.00 (-2.85%)' : '+18.42 (+1.84%)'}
                        </span>
                      </div>
                      <div class="latch-summary-item">
                        <span class="latch-summary-label">SOFT 禁增倉門檻</span>
                        <span class="latch-summary-val num" style="color:var(--gold-primary);">-10.0% (900.00)</span>
                      </div>
                      <div class="latch-summary-item">
                        <span class="latch-summary-label">HARD 硬熔斷門檻</span>
                        <span class="latch-summary-val num" style="color:var(--color-red);">-20.0% (800.00)</span>
                      </div>
                    </div>

                    <!-- 刻度軌道儀表 (Gauge Track) -->
                    <div class="gauge-track-wrapper">
                      <div class="gauge-track">
                        <div class="gauge-seg-hard" title="Hard Latch 熔斷區 (-20% 以下)"></div>
                        <div class="gauge-seg-soft" title="Soft Latch 警戒區 (-10% ~ -20%)"></div>
                        <div class="gauge-seg-normal" title="正常波動區 (0% ~ -10%)"></div>
                        <div class="gauge-seg-profit" title="盈利安全區 (> 0%)"></div>
                      </div>

                      <!-- 浮動指示氣泡 (Tooltip) -->
                      <div class="gauge-pointer" id="gauge-live-pointer" style="left:${isLatch ? '38%' : '74%'};">
                        <div class="gauge-pointer-arrow"></div>
                        <div class="gauge-pointer-tag">
                          ${isLatch ? '盤中最高回撤 -10.20% (軟限鎖存中 · 現反彈至 -2.85%)' : '當前淨值 +1.84% (安全緩衝 118.42 USDT)'}
                        </div>
                      </div>

                      <!-- 底部刻度標記 -->
                      <div class="gauge-scale-legend">
                        <span>Hard: -20% (800)</span>
                        <span>Soft: -10% (900)</span>
                        <span style="color:#ffffff;">基準: 0.0% (1,000)</span>
                        <span style="color:${isLatch ? 'var(--color-red)' : 'var(--color-green)'}; font-weight:600;">
                          ${isLatch ? '目前: -2.85% (121,900.50)' : '目前: +1.84% (1,018.42)'}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 垂直分割條 (OKX Continuous Resizer) -->
              <div class="workspace-splitter vertical" id="splitter-v-lower-1" data-left="widget-risk_latch" data-right="widget-active_bots" title="拖曳自訂寬度"></div>

              <!-- Pane 5: Bot 隊列 -->
              <div class="grid-stack-item tiling-pane" id="widget-active_bots" gs-id="active_bots" style="flex:0 0 22%;">
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

              <!-- 垂直分割條 (OKX Continuous Resizer) -->
              <div class="workspace-splitter vertical" id="splitter-v-lower-2" data-left="widget-active_bots" data-right="widget-research_tasks" title="拖曳自訂寬度"></div>

              <!-- Pane 6: 近期研究任務 -->
              <div class="grid-stack-item tiling-pane" id="widget-research_tasks" gs-id="research_tasks" style="flex:0 0 22%;">
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

              <!-- 垂直分割條 (OKX Continuous Resizer) -->
              <div class="workspace-splitter vertical" id="splitter-v-lower-3" data-left="widget-research_tasks" data-right="widget-yaozi_brief" title="拖曳自訂寬度"></div>

              <!-- Pane 7: Yaozi 市場情報快訊 -->
              <div class="grid-stack-item tiling-pane" id="widget-yaozi_brief" gs-id="yaozi_brief" style="flex:0 0 22%;">
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
"""

    text = text[:lower_old_start] + lower_replacement + text[lower_old_end:]

    # 3. 在 afterRender 中加入 renderAllocation() 呼叫
    after_render_needle = 'if (window.WorkspaceEngine) {'
    after_render_replacement = """if (window.WorkspaceEngine) {
      window.WorkspaceEngine.init('dashboard-grid-stack', 'dashboard');
    }

    // 渲染 ALLOCATION 甜甜圈圓環圖與圖例
    this.renderAllocation();"""
    text = text.replace("""if (window.WorkspaceEngine) {
      window.WorkspaceEngine.init('dashboard-grid-stack', 'dashboard');
    }""", after_render_replacement, 1)

    # 4. 在 DashboardView 物件末尾注入 allocation 的完整資料與方法
    allocation_methods = """
  // ================= ALLOCATION 甜甜圈配置圖數據與邏輯 =================
  allocationData: {
    margin: {
      title: '帳戶保證金與曝險配置',
      note: '預設：帳戶持倉保證金、在途凍結與風控預算佔比',
      hudMain: '1,420.50 USDT',
      hudSub: '總曝險上限 3,000 USDT',
      segments: [
        { name: 'BTC 永續持倉保證金', pct: 32, val: '320.00 USDT', color: '#e6b840' },
        { name: '委託在途凍結保證金', pct: 15, val: '150.00 USDT', color: '#38bdf8' },
        { name: '未佔用可用保證金', pct: 43, val: '430.00 USDT', color: '#34d399' },
        { name: '風控鎖存緩衝預留', pct: 10, val: '100.00 USDT', color: '#a78bfa' }
      ]
    },
    multi_asset: {
      title: '多幣組合總覽 (現貨+SWAP)',
      note: '視圖：帳戶各主流幣種持倉佔比與現金額度',
      hudMain: '2,450.00 USDT',
      hudSub: '3 幣種組合分散',
      segments: [
        { name: 'BTC-USDT SWAP', pct: 50, val: '1,225.00 USDT', color: '#e6b840' },
        { name: 'ETH-USDT SWAP', pct: 30, val: '735.00 USDT', color: '#38bdf8' },
        { name: 'SOL-USDT SWAP', pct: 20, val: '490.00 USDT', color: '#a78bfa' }
      ]
    },
    bots: {
      title: 'Bot 策略幣種分配額度',
      note: '視圖：運行中策略對應標的之分配額度',
      hudMain: '3,000.00 USDT',
      hudSub: '3 運行策略分配',
      segments: [
        { name: 'Bot-01 ATR-Trend (BTC)', pct: 50, val: '1,500.00 USDT', color: '#e6b840' },
        { name: 'Bot-02 Grid-Osc (ETH)', pct: 30, val: '900.00 USDT', color: '#34d399' },
        { name: 'Bot-03 Momentum (SOL)', pct: 20, val: '600.00 USDT', color: '#38bdf8' }
      ]
    },
    positions: {
      title: '實盤活躍倉位分布 (已進場)',
      note: '視圖：實時市場持倉名義價值比例',
      hudMain: '1,285.00 USDT',
      hudSub: '2 活躍部位 (Cross Net)',
      segments: [
        { name: 'BTC 多頭 (2張)', pct: 65, val: '835.25 USDT', color: '#e6b840' },
        { name: 'SOL 空頭 (10張)', pct: 35, val: '449.75 USDT', color: '#38bdf8' }
      ]
    }
  },

  currentAllocationDim: 'margin',
  leverageBasis: '3.0x',

  switchAllocationDim: function(dim) {
    if (!this.allocationData[dim]) return;
    this.currentAllocationDim = dim;
    if (typeof document !== 'undefined') {
      const pills = document.querySelectorAll('#allocation-dimension-pills .pill-switch-btn');
      pills.forEach(b => {
        b.classList.toggle('active', b.getAttribute('data-dim') === dim);
      });
    }
    this.renderAllocation();
  },

  toggleLeverageBasis: function() {
    this.leverageBasis = (this.leverageBasis === '3.0x') ? '1.0x' : '3.0x';
    const btn = document.getElementById('btn-toggle-leverage');
    if (btn) {
      btn.textContent = '基準: ' + this.leverageBasis + (this.leverageBasis === '3.0x' ? ' 曝險' : ' 本金');
    }
    this.renderAllocation();
  },

  renderAllocation: function() {
    if (typeof document === 'undefined') return;
    const data = this.allocationData[this.currentAllocationDim] || this.allocationData.margin;
    const dimNote = document.getElementById('allocation-dim-note');
    if (dimNote) dimNote.textContent = data.note;

    let hudMain = data.hudMain;
    let hudSub = data.hudSub;
    if (this.currentAllocationDim === 'margin') {
      hudSub = (this.leverageBasis === '3.0x') ? '總曝險上限 3,000 USDT' : '淨權益基準 1,000 USDT';
    }

    const hudLabel = document.getElementById('donut-hud-label');
    const hudVal = document.getElementById('donut-hud-val');
    const hudSubEl = document.getElementById('donut-hud-sub');
    if (hudLabel) hudLabel.textContent = (this.currentAllocationDim === 'margin') ? '總名義曝險' : '配置總值';
    if (hudVal) hudVal.textContent = hudMain;
    if (hudSubEl) hudSubEl.textContent = hudSub;

    // 繪製 SVG 甜甜圈圓環 (r=38, c=238.76, 1.5px 微米間隙)
    const svg = document.getElementById('allocation-donut-svg');
    if (svg) {
      svg.innerHTML = '';
      const r = 38;
      const c = 2 * Math.PI * r; // 約 238.761
      let currentOffset = 0;

      data.segments.forEach((seg, idx) => {
        const segLen = (seg.pct / 100) * c;
        const strokeLen = Math.max(0, segLen - 1.5); // 保留 1.5px 微米間隙
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', '50');
        circle.setAttribute('cy', '50');
        circle.setAttribute('r', String(r));
        circle.setAttribute('class', 'donut-segment');
        circle.setAttribute('stroke', seg.color);
        circle.setAttribute('stroke-dasharray', `${strokeLen.toFixed(2)} ${(c - strokeLen).toFixed(2)}`);
        circle.setAttribute('stroke-dashoffset', String(-currentOffset.toFixed(2)));
        circle.setAttribute('data-index', String(idx));
        circle.id = `donut-seg-${idx}`;

        // Hover 雙向聯動
        circle.addEventListener('mouseenter', () => {
          if (hudLabel) hudLabel.textContent = seg.name;
          if (hudVal) hudVal.textContent = seg.val;
          if (hudSubEl) hudSubEl.textContent = `${seg.pct}% 佔比`;
          this.highlightLegendRow(idx, true);
        });
        circle.addEventListener('mouseleave', () => {
          if (hudLabel) hudLabel.textContent = (this.currentAllocationDim === 'margin') ? '總名義曝險' : '配置總值';
          if (hudVal) hudVal.textContent = hudMain;
          if (hudSubEl) hudSubEl.textContent = hudSub;
          this.highlightLegendRow(idx, false);
        });

        svg.appendChild(circle);
        currentOffset += segLen;
      });
    }

    // 繪製右側圖例列表 (支援 Hover 雙向高亮)
    const listEl = document.getElementById('allocation-legend-list');
    if (listEl) {
      listEl.innerHTML = '';
      data.segments.forEach((seg, idx) => {
        const row = document.createElement('div');
        row.className = 'legend-item-row';
        row.id = `legend-row-${idx}`;
        row.innerHTML = `
          <div class="legend-left">
            <span class="legend-swatch" style="background:${seg.color};"></span>
            <span style="color:#d0d6e2; font-size:11.5px; font-weight:500;">${seg.name}</span>
          </div>
          <div class="legend-right">
            <span class="legend-amount num">${seg.val}</span>
            <span class="legend-pct num">(${seg.pct}%)</span>
          </div>
        `;

        // Hover 圖例時雙向聯動甜甜圈
        row.addEventListener('mouseenter', () => {
          if (hudLabel) hudLabel.textContent = seg.name;
          if (hudVal) hudVal.textContent = seg.val;
          if (hudSubEl) hudSubEl.textContent = `${seg.pct}% 佔比`;
          const segEl = document.getElementById(`donut-seg-${idx}`);
          if (segEl) segEl.classList.add('is-hovered');
          row.classList.add('is-hovered');
        });
        row.addEventListener('mouseleave', () => {
          if (hudLabel) hudLabel.textContent = (this.currentAllocationDim === 'margin') ? '總名義曝險' : '配置總值';
          if (hudVal) hudVal.textContent = hudMain;
          if (hudSubEl) hudSubEl.textContent = hudSub;
          const segEl = document.getElementById(`donut-seg-${idx}`);
          if (segEl) segEl.classList.remove('is-hovered');
          row.classList.remove('is-hovered');
        });

        listEl.appendChild(row);
      });
    }
  },

  highlightLegendRow: function(idx, isHover) {
    if (typeof document === 'undefined') return;
    const row = document.getElementById(`legend-row-${idx}`);
    if (row) {
      row.classList.toggle('is-hovered', isHover);
    }
  },
"""

    # 將方法插在 DashboardView 的最後（在最後一個閉合括號前）
    last_brace_idx = text.rfind('};')
    if last_brace_idx == -1:
        raise ValueError("Cannot locate closing brace of DashboardView")
    text = text[:last_brace_idx] + allocation_methods + "\n" + text[last_brace_idx:]

    p.write_text(text, encoding='utf-8')
    print("dashboard.js updated successfully.")

if __name__ == '__main__':
    update_dashboard()
