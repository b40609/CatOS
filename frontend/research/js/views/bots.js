/**
 * catOS Prototype - Bots Management View (Institutional Quantitative Workstation)
 *
 * 嚴格遵循專業量化交易工作台規範：
 * - 黑灰底、低飽和霧金、細框線、monospace 數據風格。
 * - 冷靜、精密、有層次，無大圓角、無大卡片、無玻璃模糊、無華麗動畫。
 * - 結構：頁首 -> 運行概況 (低高度 status strip) -> 全寬 Bot 列表 -> 560px Quick Inspector -> 完整 Bot Detail。
 * - 示意資料固定為 3 個 Bot (BTC, ETH, SOL)，數值與統計 (全部 3, 運行中 1, 需處理 1, 已停止 1) 完全同步閉環。
 */

window.BotsView = {
  render: function(state) {
    state = state || (window.appState ? window.appState.get() : {});
    const data = window.CATOS_DATA;

    // Check if user navigated to dedicated full detail page
    if (state.botFullDetailView) {
      const selectedBot = data.bots.find(b => b.id === state.selectedBotId) || data.bots[0];
      return this.renderFullDetailPage(state, selectedBot);
    }

    return this.renderListView(state);
  },

  /**
   * Main Full-Width Table & Quick Inspector View
   */
  renderListView: function(state) {
    const data = window.CATOS_DATA;
    const filter = state.botsStatusFilter || 'ALL';
    const isDrawerOpen = state.botDrawerOpen || false;
    const selectedBotId = state.selectedBotId;

    // Calculate exact counts (Strictly 3 bots: RUNNING 1, WARNING 1, STOPPED 1)
    const totalCount = data.bots.length;
    const runningCount = data.bots.filter(b => b.status === 'RUNNING').length;
    const warningCount = data.bots.filter(b => b.status === 'WARNING').length;
    const stoppedCount = data.bots.filter(b => b.status === 'STOPPED').length;

    // Filtered bots list
    const filteredBots = data.bots.filter(b => {
      if (filter === 'ALL') return true;
      return b.status === filter;
    });

    const selectedBot = data.bots.find(b => b.id === selectedBotId);
    const drawerSubTab = state.botDrawerSubTab || 'position';
    const expandedEventIdx = state.expandedBotEventIndex;

    return `
      <div class="bots-view-container" style="position:relative;">

        <!-- 一、頁首 (Left: Title & Secondary note; Right: 建立 Bot 尚未接線) -->
        <div style="display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:8px;">
          <div>
            <div style="display:flex; align-items:baseline; gap:8px;">
              <span style="font-family:var(--font-mono); font-size:12px; color:var(--gold-primary); text-transform:uppercase; letter-spacing:0.05em; font-weight:600;">Bots</span>
              <h1 style="font-size:16px; font-weight:700; color:var(--text-primary); margin:0; line-height:1.2;">
                機器人管理
              </h1>
            </div>
            <div style="font-size:12px; color:var(--text-muted); margin-top:3px;">
              監看已部署 Bot、固定運行版本與異常事件
            </div>
          </div>

          <div style="display:flex; align-items:center; gap:8px;">
            <button class="btn btn-sm btn-ghost"
                    onclick="alert('[尚未接線 - 原型展示階段，無法建立真實交易 Bot]')"
                    style="font-size:12px; height:28px; padding:0 10px; border-color:var(--border-default); color:var(--text-secondary); cursor:not-allowed;"
                    title="原型功能尚未接線">
              ＋建立 Bot <span style="font-size:10px; color:var(--text-muted); margin-left:2px;">(尚未接線)</span>
            </button>
          </div>
        </div>

        <!-- 二、運行概況 (低高度 status strip，不是三張大型 KPI 卡) -->
        <div class="bot-status-strip-bar">
          <!-- 全部 3 -->
          <div class="bot-status-pill ${filter === 'ALL' ? 'active' : ''}"
               onclick="window.BotsView.setStatusFilter('ALL')"
               title="顯示全部 Bot">
            <span>全部</span>
            <span class="num" style="font-size:11.5px; font-weight:600;">${totalCount}</span>
          </div>

          <span style="color:var(--border-default); font-size:11px;">|</span>

          <!-- ● 運行中 1 -->
          <div class="bot-status-pill ${filter === 'RUNNING' ? 'active' : ''}"
               onclick="window.BotsView.setStatusFilter('RUNNING')"
               title="篩選運行中 Bot">
            <span class="bot-status-dot green"></span>
            <span>運行中</span>
            <span class="num" style="font-size:11.5px; font-weight:600; color:var(--color-green);">${runningCount}</span>
          </div>

          <!-- ● 需處理 1 -->
          <div class="bot-status-pill ${filter === 'WARNING' ? 'active' : ''}"
               onclick="window.BotsView.setStatusFilter('WARNING')"
               title="篩選需處理 Bot">
            <span class="bot-status-dot amber"></span>
            <span>需處理</span>
            <span class="num" style="font-size:11.5px; font-weight:600; color:var(--color-amber);">${warningCount}</span>
          </div>

          <!-- ● 已停止 1 (中性灰，非故障) -->
          <div class="bot-status-pill ${filter === 'STOPPED' ? 'active' : ''}"
               onclick="window.BotsView.setStatusFilter('STOPPED')"
               title="篩選已停止 Bot">
            <span class="bot-status-dot grey"></span>
            <span>已停止</span>
            <span class="num" style="font-size:11.5px; font-weight:600; color:#9da5b4;">${stoppedCount}</span>
          </div>

          ${filter !== 'ALL' ? `
            <div style="margin-left:auto; display:flex; align-items:center; gap:6px; font-size:11px; color:var(--text-muted); padding-right:6px;">
              <span>篩選結果: <strong style="color:var(--text-primary); font-family:var(--font-mono);">${filteredBots.length}</strong> 筆</span>
              <a href="javascript:void(0)" onclick="window.BotsView.setStatusFilter('ALL')" style="color:var(--gold-primary); text-decoration:none; margin-left:4px;">[重設]</a>
            </div>
          ` : `
            <div style="margin-left:auto; font-size:11px; color:var(--text-muted); padding-right:6px;">
              共 <span class="num" style="color:var(--text-primary);">${filteredBots.length}</span> 支 Bot 部署
            </div>
          `}
        </div>

        <!-- 三、全寬 Bot 列表 (固定 7 欄位，嚴格比例分配，消滅空白斷層) -->
        <div class="data-table-container panel-specular" style="width:100%; overflow-x:auto;">
          <table class="data-table" style="width:100%; border:none; table-layout:fixed;">
            <thead>
              <tr>
                <th style="width:100px; text-align:left; vertical-align:bottom;">
                  <div class="th-dual-zh">狀態</div>
                  <div class="th-dual-en">STATUS</div>
                </th>
                <th style="width:300px; text-align:left; vertical-align:bottom;">
                  <div class="th-dual-zh">機器人／策略</div>
                  <div class="th-dual-en">INSTANCE &amp; STRATEGY</div>
                </th>
                <th style="width:180px; text-align:left; vertical-align:bottom;">
                  <div class="th-dual-zh">交易標的</div>
                  <div class="th-dual-en">INSTRUMENT // TF</div>
                </th>
                <th class="col-compact-hide" style="width:160px; text-align:left; vertical-align:bottom;">
                  <div class="th-dual-zh">持倉部位</div>
                  <div class="th-dual-en">NET POSITION</div>
                </th>
                <th style="width:170px; text-align:left; vertical-align:bottom;">
                  <div class="th-dual-zh">今日損益</div>
                  <div class="th-dual-en">24H PNL (USDT)</div>
                </th>
                <th class="col-compact-hide" style="width:190px; text-align:left; vertical-align:bottom;">
                  <div class="th-dual-zh">行情時戳</div>
                  <div class="th-dual-en">LAST BAR TIMESTAMP</div>
                </th>
                <th style="width:120px; text-align:right; vertical-align:bottom;">
                  <div class="th-dual-zh">檢視</div>
                  <div class="th-dual-en">ACTION</div>
                </th>
              </tr>
            </thead>
            <tbody>
              ${filteredBots.length > 0 ? filteredBots.map(bot => {
                const isSelected = isDrawerOpen && bot.id === selectedBotId;
                const isWarning = bot.status === 'WARNING';

                // 狀態顯示 (運行中=綠, 需處理=琥珀, 已停止=中性灰)
                let statusBadgeHtml = '';
                if (bot.status === 'RUNNING') {
                  statusBadgeHtml = `<span class="badge badge-green bot-nowrap" style="padding:1px 6px; font-size:11px;"><span class="badge-dot green"></span>運行中</span>`;
                } else if (bot.status === 'WARNING') {
                  statusBadgeHtml = `<span class="badge badge-amber bot-nowrap" style="padding:1px 6px; font-size:11px;"><span class="badge-dot amber"></span>需處理</span>`;
                } else if (bot.status === 'STOPPED') {
                  statusBadgeHtml = `<span class="badge badge-stopped bot-nowrap" style="padding:1px 6px; font-size:11px;"><span class="badge-dot" style="background-color:#9da5b4;"></span>已停止</span>`;
                }

                // 今日損益顏色 (正值綠、負值紅、零值灰)
                const pnlNum = parseFloat(bot.dailyPnl.replace(/[^\d.-]/g, ''));
                let pnlColor = '#9da5b4'; // 零值中性灰
                if (pnlNum > 0) pnlColor = 'var(--color-green)';
                else if (pnlNum < 0) pnlColor = 'var(--color-red)';

                // 持倉 (多 0.20 BTC / 空 2.40 ETH / 空倉中性灰)
                let positionHtml = '';
                if (bot.position.direction === '空倉') {
                  positionHtml = `<span style="color:#9da5b4;">空倉</span>`;
                } else {
                  positionHtml = `<span style="font-weight:600; color:var(--text-primary); font-family:var(--font-mono);">${bot.position.direction} ${bot.position.amount}</span>`;
                }

                // 最後 K 線新鮮度提醒 (僅超時才顯示琥珀提醒)
                const staleWarningHtml = bot.isBarStale
                  ? `<span class="badge badge-amber" style="font-size:11px; padding:1px 5px; margin-left:4px;">延遲</span>`
                  : '';

                return `
                  <tr class="bot-row-item ${isSelected ? 'selected' : ''}"
                      id="bot-row-${bot.id}"
                      onclick="window.BotsView.openDrawer('${bot.id}', 'bot-row-${bot.id}')">

                    <!-- 1. 狀態 -->
                    <td class="bot-nowrap">
                      ${statusBadgeHtml}
                    </td>

                    <!-- 2. Bot／策略 (第一行 Bot 名稱，第二行 策略 · 固定運行版本) -->
                    <td class="bot-nowrap">
                      <div style="font-weight:600; color:var(--text-primary); font-size:13.5px; line-height:1.25; display:flex; align-items:center;">
                        ${isWarning ? '<span class="bot-warning-marker" title="此 Bot 存在運行警報"></span>' : ''}
                        <span>${bot.name}</span>
                      </div>
                      <div class="bot-subtext" style="font-size:11.5px; color:var(--text-muted); margin-top:2px;">
                        ${bot.boundStrategyVersion}
                      </div>
                    </td>

                    <!-- 3. 合約／週期 (BTC-USDT-SWAP, 15m 不得折行) -->
                    <td class="bot-nowrap">
                      <span class="num" style="font-weight:600; color:var(--text-primary); font-size:13px;">${bot.symbol}</span>
                      <span style="font-size:11px; color:var(--text-muted); margin-left:4px; font-family:var(--font-mono);">${bot.timeframe}</span>
                    </td>

                    <!-- 4. 持倉 (窄版收納至右側 Inspector) -->
                    <td class="bot-nowrap num col-compact-hide" style="font-size:13px;">
                      ${positionHtml}
                    </td>

                    <!-- 5. 今日損益 (monospace number) -->
                    <td class="bot-nowrap num" style="font-weight:600; font-size:13px; color:${pnlColor};">
                      ${bot.dailyPnl}
                    </td>

                    <!-- 6. 最後 K 線 (窄版收納至右側 Inspector) -->
                    <td class="bot-nowrap col-compact-hide">
                      <div class="num" style="font-size:12px; color:var(--text-primary); font-weight:500;">
                        ${bot.lastBarTime} ${staleWarningHtml}
                      </div>
                      <div style="font-size:10.5px; color:var(--text-muted); margin-top:1px;">
                        ${bot.lastBarDate} · ${bot.lastBarRelative}
                      </div>
                    </td>

                    <!-- 7. 操作 (只保留「查看詳情 →」) -->
                    <td class="bot-nowrap" style="text-align:right;" onclick="event.stopPropagation();">
                      <button class="btn btn-sm btn-ghost"
                              id="btn-inspect-${bot.id}"
                              onclick="window.BotsView.openDrawer('${bot.id}', 'btn-inspect-${bot.id}')"
                              style="font-size:11.5px; padding:0 8px; color:var(--gold-primary); height:24px; border:none; background:transparent;">
                        查看詳情 &rarr;
                      </button>
                    </td>
                  </tr>
                `;
              }).join('') : `
                <tr>
                  <td colspan="7" style="text-align:center; padding:32px; color:var(--text-muted); font-size:12.5px;">
                    此狀態下尚無 Bot 項目
                  </td>
                </tr>
              `}
            </tbody>
          </table>
        </div>

        <!-- 少量 Bot 自然留白，不塞入裝飾性圖表 -->

        <!-- 四、Quick Inspector (560px 寬，低強度暗色 overlay，無 backdrop blur) -->
        <div class="drawer-backdrop ${isDrawerOpen ? 'open' : ''}"
             onclick="window.BotsView.closeDrawer()"></div>

        <div class="bot-drawer ${isDrawerOpen ? 'open' : ''}"
             role="dialog"
             aria-modal="true"
             aria-labelledby="inspector-bot-title"
             style="width:560px;"
             onclick="event.stopPropagation();">

          ${selectedBot ? `
            <!-- Inspector Header -->
            <div class="bot-drawer-header">
              <div>
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:3px;">
                  <span id="inspector-bot-title" style="font-size:15px; font-weight:700; color:var(--text-primary);">${selectedBot.name}</span>
                  ${selectedBot.status === 'RUNNING'
                    ? `<span class="badge badge-green" style="font-size:10px; padding:1px 5px;"><span class="badge-dot green"></span>運行中</span>`
                    : (selectedBot.status === 'WARNING'
                      ? `<span class="badge badge-amber" style="font-size:10px; padding:1px 5px;"><span class="badge-dot amber"></span>需處理</span>`
                      : `<span class="badge badge-stopped" style="font-size:10px; padding:1px 5px;"><span class="badge-dot" style="background-color:#9da5b4;"></span>已停止</span>`)}
                </div>

                <!-- 次行：策略名稱、固定運行版本、合約 · timeframe -->
                <div style="font-size:11.5px; color:var(--text-muted); line-height:1.4;">
                  <strong style="color:var(--text-secondary);">${selectedBot.strategyName}</strong> · ${selectedBot.strategyVersion} (固定版本) •
                  <span class="num">${selectedBot.symbol}</span> · ${selectedBot.timeframe}
                </div>
              </div>

              <!-- 右上：完整詳情 ↗ 與 關閉 × -->
              <div style="display:flex; align-items:center; gap:6px;">
                <button class="btn btn-sm btn-ghost"
                        onclick="window.BotsView.openFullDetail('${selectedBot.id}')"
                        title="開啟完整詳情頁面"
                        style="font-size:11px; padding:0 8px; color:var(--gold-primary); height:24px; border:1px solid var(--border-default);">
                  完整詳情 ↗
                </button>
                <button class="btn btn-sm btn-ghost"
                        onclick="window.BotsView.closeDrawer()"
                        title="關閉 (ESC)"
                        style="font-size:14px; padding:0 8px; height:24px; color:var(--text-muted);">
                  &times;
                </button>
              </div>
            </div>

            <!-- Inspector 內容區 (三個 sub-tab) -->
            <div class="bot-drawer-body">

              <!-- Tab 切換列 -->
              <div class="drawer-tab-bar">
                <button class="drawer-tab-btn ${drawerSubTab === 'position' ? 'active' : ''}" onclick="window.BotsView.switchDrawerTab('position')">
                  持倉
                </button>
                <button class="drawer-tab-btn ${drawerSubTab === 'events' ? 'active' : ''}" onclick="window.BotsView.switchDrawerTab('events')">
                  事件 (${selectedBot.events.length})
                </button>
                <button class="drawer-tab-btn ${drawerSubTab === 'orders' ? 'active' : ''}" onclick="window.BotsView.switchDrawerTab('orders')">
                  委託與成交 (${selectedBot.orders.length})
                </button>
              </div>

              <!-- 1. 持倉 Tab -->
              ${drawerSubTab === 'position' ? `
                <div style="display:flex; flex-direction:column; gap:12px;">

                  <!-- 上方三個主要數值 (Dual-Tier Metric Cards) -->
                  <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; padding:10px 12px; background:var(--bg-surface); border:1px solid var(--border-subtle); border-radius:2px;">
                    <div>
                      <div class="th-dual-zh" style="font-size:11px; margin-bottom:1px;">目前持倉</div>
                      <div class="th-dual-en" style="font-size:8.5px; margin-bottom:4px;">NET POSITION</div>
                      <div class="num" style="font-size:13.5px; font-weight:700; color:var(--text-primary);">
                        ${selectedBot.position.direction === '空倉' ? '<span style="color:#9da5b4;">空倉</span>' : `${selectedBot.position.direction} ${selectedBot.position.amount}`}
                      </div>
                    </div>

                    <div>
                      <div class="th-dual-zh" style="font-size:11px; margin-bottom:1px;">未實現損益</div>
                      <div class="th-dual-en" style="font-size:8.5px; margin-bottom:4px;">UNREALIZED MTM</div>
                      <div class="num" style="font-size:13.5px; font-weight:700; color:${parseFloat(selectedBot.position.unrealizedPnl.replace(/[^\d.-]/g, '')) > 0 ? 'var(--color-green)' : (parseFloat(selectedBot.position.unrealizedPnl.replace(/[^\d.-]/g, '')) < 0 ? 'var(--color-red)' : '#9da5b4')};">
                        ${selectedBot.position.unrealizedPnl}
                      </div>
                    </div>

                    <div>
                      <div class="th-dual-zh" style="font-size:11px; margin-bottom:1px;">今日損益</div>
                      <div class="th-dual-en" style="font-size:8.5px; margin-bottom:4px;">SETTLED PNL</div>
                      <div class="num" style="font-size:13.5px; font-weight:700; color:${parseFloat(selectedBot.dailyPnl.replace(/[^\d.-]/g, '')) > 0 ? 'var(--color-green)' : (parseFloat(selectedBot.dailyPnl.replace(/[^\d.-]/g, '')) < 0 ? 'var(--color-red)' : '#9da5b4')};">
                        ${selectedBot.dailyPnl}
                      </div>
                    </div>
                  </div>

                  <!-- 下方 compact key/value 清單 -->
                  <div style="background:var(--bg-panel); border:1px solid var(--border-default); border-radius:2px; padding:10px 12px;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:8px; border-bottom:1px solid var(--border-subtle); padding-bottom:5px;">
                      <div>
                        <div class="th-dual-zh" style="color:var(--text-secondary); font-size:12.5px;">部位參數詳情</div>
                        <div class="th-dual-en" style="font-size:11px;">POSITION PARAMETERS // RISK</div>
                      </div>
                      <span class="tag tag-mono" style="font-size:11px; padding:1px 6px; color:var(--gold-primary); border-color:var(--border-gold-subtle);">LIVE MTM</span>
                    </div>

                    <div class="kv-row">
                      <span class="kv-label">方向</span>
                      <span class="kv-value">${selectedBot.position.direction}</span>
                    </div>

                    <div class="kv-row">
                      <span class="kv-label">數量</span>
                      <span class="kv-value">${selectedBot.position.amount}</span>
                    </div>

                    <div class="kv-row">
                      <span class="kv-label">平均成本</span>
                      <span class="kv-value">${selectedBot.position.entryPrice}</span>
                    </div>

                    <div class="kv-row">
                      <span class="kv-label">最新標記價</span>
                      <span class="kv-value">${selectedBot.position.markPrice}</span>
                    </div>

                    <div class="kv-row">
                      <span class="kv-label">有效槓桿</span>
                      <span class="kv-value" style="color:var(--gold-primary);">${selectedBot.position.leverage}</span>
                    </div>

                    <div class="kv-row">
                      <span class="kv-label">最後更新時間</span>
                      <span class="kv-value">${selectedBot.position.valuationTime}</span>
                    </div>
                  </div>
                </div>
              ` : ''}

              <!-- 2. 事件 Tab (Alert Timeline: 細垂直線、小圓點、timestamp、小型 severity label、摘要、展開原因) -->
              ${drawerSubTab === 'events' ? `
                <div style="display:flex; flex-direction:column; gap:10px;">
                  <div class="timeline-rail-wrap" style="padding-left:18px; margin-top:4px;">
                    ${selectedBot.events.map((ev, idx) => {
                      const isExpanded = expandedEventIdx === idx;
                      return `
                        <div class="timeline-node-item" style="margin-bottom:14px;">
                          <!-- 小圓點 (INFO / WARN / ERROR 清楚區分) -->
                          <div class="timeline-node-dot ${ev.severity}"></div>

                          <!-- Header: timestamp + severity label + 事件摘要 -->
                          <div class="timeline-item-header" style="display:flex; align-items:baseline; justify-content:space-between;">
                            <div style="display:flex; align-items:center; gap:8px;">
                              <span class="num" style="font-size:11px; color:#8c94a4;">${ev.time}</span>
                              <span class="badge ${ev.severity === 'WARN' ? 'badge-amber' : 'badge-ghost'}" style="font-size:11px; padding:1px 5px; font-weight:600;">
                                ${ev.severity}
                              </span>
                              <span class="timeline-item-title" style="font-size:12.5px; font-weight:600; color:var(--text-primary);">
                                ${ev.summary}
                              </span>
                            </div>

                            <button class="btn btn-sm btn-ghost"
                                    onclick="window.BotsView.toggleEventDetail(${idx})"
                                    style="font-size:11px; padding:0 4px; color:var(--gold-primary); height:20px; border:none; background:transparent;">
                              ${isExpanded ? '收合原因 ↑' : '查看原因 ↓'}
                            </button>
                          </div>

                          <!-- 展開後才顯示：實際觀察值、觸發條件、相關 Log 入口 (乾淨精緻微邊框) -->
                          ${isExpanded ? `
                            <div style="margin-top:6px; padding:8px 10px; background:var(--bg-surface); border:1px solid var(--border-default); border-radius:var(--border-radius-sm); font-size:11.5px; line-height:1.5;">
                              <div style="color:var(--text-secondary); margin-bottom:4px;">
                                ${ev.detail}
                              </div>
                              ${ev.observed ? `
                                <div style="color:var(--text-muted); margin-top:2px;">
                                  <span style="color:var(--text-secondary);">實際觀察值：</span><code class="mono" style="color:var(--text-primary);">${ev.observed}</code>
                                </div>
                              ` : ''}
                              ${ev.condition ? `
                                <div style="color:var(--text-muted); margin-top:2px;">
                                  <span style="color:var(--text-secondary);">觸發條件：</span>${ev.condition}
                                </div>
                              ` : ''}
                              <div style="margin-top:6px; padding-top:4px; border-top:1px dashed var(--border-subtle);">
                                <a href="javascript:void(0)"
                                   onclick="window.appState.set({ activePage: 'logs', logsFilter: { severity: '${ev.severity}', target: '${selectedBot.id}', search: '' } })"
                                   style="font-size:11px; color:var(--gold-primary); text-decoration:none;">
                                  前往系統日誌檢視 (Target: ${selectedBot.id}) &rarr;
                                </a>
                              </div>
                            </div>
                          ` : ''}
                        </div>
                      `;
                    }).join('')}
                  </div>
                </div>
              ` : ''}

              <!-- 3. 委託與成交 Tab (compact table, 標註示意資料, 無自創 OKX tag) -->
              ${drawerSubTab === 'orders' ? `
                <div style="display:flex; flex-direction:column; gap:8px;">
                  <div style="display:flex; justify-content:space-between; align-items:center; font-size:11.5px; color:var(--text-muted);">
                    <span style="font-weight:500;">撮合歷史表記錄</span>
                    <span style="font-size:11px; color:var(--gold-primary); font-family:var(--font-mono);">
                      [示意資料 · 未連線交易所]
                    </span>
                  </div>

                  <div style="border:1px solid var(--border-default); border-radius:2px; overflow:hidden;">
                    <table class="data-table" style="border:none; font-size:11.5px; width:100%;">
                      <thead>
                        <tr>
                          <th style="padding:6px 8px; vertical-align:bottom;">
                            <div class="th-dual-zh">時間</div>
                            <div class="th-dual-en">TIMESTAMP</div>
                          </th>
                          <th style="padding:6px 8px; vertical-align:bottom;">
                            <div class="th-dual-zh">方向</div>
                            <div class="th-dual-en">SIDE</div>
                          </th>
                          <th style="padding:6px 8px; vertical-align:bottom;">
                            <div class="th-dual-zh">狀態</div>
                            <div class="th-dual-en">STATE</div>
                          </th>
                          <th style="padding:6px 8px; vertical-align:bottom;">
                            <div class="th-dual-zh">數量</div>
                            <div class="th-dual-en">SIZE</div>
                          </th>
                          <th style="padding:6px 8px; vertical-align:bottom;">
                            <div class="th-dual-zh">成交均價</div>
                            <div class="th-dual-en">AVG PRICE</div>
                          </th>
                          <th style="padding:6px 8px; text-align:right; vertical-align:bottom;">
                            <div class="th-dual-zh">手續費</div>
                            <div class="th-dual-en">FEE</div>
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        ${selectedBot.orders.length > 0 ? selectedBot.orders.map(o => `
                          <tr>
                            <td class="num" style="font-size:11.5px; padding:5px 8px;">${o.time.split(' ')[1] || o.time}</td>
                            <td class="bot-nowrap" style="padding:5px 8px;">
                              <span class="badge ${o.side === '買入' ? 'badge-green' : 'badge-red'}" style="font-size:11px; padding:1px 5px; font-weight:600;">
                                ${o.side}
                              </span>
                            </td>
                            <td class="bot-nowrap" style="font-size:11px; color:${o.status === '完全成交' ? 'var(--color-green)' : 'var(--color-amber)'}; padding:5px 8px;">
                              ${o.status}
                            </td>
                            <td class="num" style="padding:5px 8px;">${o.size}</td>
                            <td class="num" style="padding:5px 8px;">${o.avgPrice}</td>
                            <td class="num" style="color:var(--text-muted); font-size:11px; padding:5px 8px; text-align:right;">${o.fee}</td>
                          </tr>
                        `).join('') : `
                          <tr><td colspan="6" style="text-align:center; padding:16px; color:var(--text-muted);">目前無委託與成交記錄</td></tr>
                        `}
                      </tbody>
                    </table>
                  </div>
                </div>
              ` : ''}
            </div>
          ` : `
            <div style="padding:32px; text-align:center; color:var(--text-muted); font-size:12.5px;">
              請選擇 Bot 查看 Inspector 詳情
            </div>
          `}
        </div>
      </div>
    `;
  },

  /**
   * Dedicated Full Bot Detail Workspace (保留左側主導覽，點「← 返回機器人列表」返回)
   */
  renderFullDetailPage: function(state, bot) {
    return `
      <div class="bot-full-detail-container" style="max-width:1200px; margin:0 auto;">

        <!-- 頂部返回導覽 -->
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; border-bottom:1px solid var(--border-default); padding-bottom:10px;">
          <div style="display:flex; align-items:center; gap:10px;">
            <button class="btn btn-sm btn-ghost"
                    onclick="window.BotsView.closeFullDetail()"
                    style="gap:5px; font-size:12px; height:26px; padding:0 8px;">
              &larr; 返回機器人列表
            </button>
            <span style="color:var(--border-default);">|</span>
            <span style="font-size:15px; font-weight:700; color:var(--text-primary);">${bot.name}</span>
            <span class="badge ${bot.status === 'RUNNING' ? 'badge-green' : (bot.status === 'WARNING' ? 'badge-amber' : 'badge-stopped')}" style="font-size:10.5px;">
              ${bot.status === 'RUNNING' ? '運行中' : (bot.status === 'WARNING' ? '需處理' : '已停止')}
            </span>
          </div>

          <div style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">
            標的：${bot.symbol} · ${bot.timeframe}
          </div>
        </div>

        <!-- 1. 運行摘要與指標網格 (Dual-Tier Metric Cards) -->
        <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; margin-bottom:14px;">
          <div class="panel panel-specular" style="padding:12px;">
            <div class="th-dual-zh">固定策略版本</div>
            <div class="th-dual-en">LOCKED VERSION</div>
            <div style="font-size:13.5px; font-weight:600; color:var(--text-primary); margin-top:4px;">
              ${bot.boundStrategyVersion}
            </div>
            <div style="font-size:10.5px; color:var(--text-muted); margin-top:2px;">生產環境鎖定中</div>
          </div>

          <div class="panel panel-specular" style="padding:12px;">
            <div class="th-dual-zh">目前持倉</div>
            <div class="th-dual-en">NET POSITION</div>
            <div class="num" style="font-size:14px; font-weight:700; color:var(--text-primary); margin-top:4px;">
              ${bot.position.direction === '空倉' ? '<span style="color:#9da5b4;">空倉</span>' : `${bot.position.direction} ${bot.position.amount}`}
            </div>
            <div style="font-size:10.5px; color:var(--text-muted); margin-top:2px;">槓桿：<span class="num">${bot.position.leverage}</span></div>
          </div>

          <div class="panel panel-specular" style="padding:12px;">
            <div class="th-dual-zh">未實現損益</div>
            <div class="th-dual-en">UNREALIZED MTM</div>
            <div class="num" style="font-size:14px; font-weight:700; color:${parseFloat(bot.position.unrealizedPnl.replace(/[^\d.-]/g, '')) > 0 ? 'var(--color-green)' : (parseFloat(bot.position.unrealizedPnl.replace(/[^\d.-]/g, '')) < 0 ? 'var(--color-red)' : '#9da5b4')}; margin-top:4px;">
              ${bot.position.unrealizedPnl}
            </div>
            <div class="num" style="font-size:10.5px; color:var(--text-muted); margin-top:2px;">${bot.position.unrealizedPnlPct}</div>
          </div>

          <div class="panel panel-specular" style="padding:12px;">
            <div class="th-dual-zh">今日結算損益</div>
            <div class="th-dual-en">SETTLED PNL</div>
            <div class="num" style="font-size:14px; font-weight:700; color:${parseFloat(bot.dailyPnl.replace(/[^\d.-]/g, '')) > 0 ? 'var(--color-green)' : (parseFloat(bot.dailyPnl.replace(/[^\d.-]/g, '')) < 0 ? 'var(--color-red)' : '#9da5b4')}; margin-top:4px;">
              ${bot.dailyPnl}
            </div>
            <div style="font-size:10.5px; color:var(--text-muted); margin-top:2px;">最後 K 線：${bot.lastBarTime}</div>
          </div>
        </div>

        <!-- 2. 雙欄配置：左欄持倉明細與事件歷史、右欄撮合委託明細與 Bot 控制 -->
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">

          <!-- 左欄 -->
          <div style="display:flex; flex-direction:column; gap:14px;">
            <!-- 目前持倉明細 -->
            <div class="panel panel-specular" style="padding:14px;">
              <div style="font-size:12px; font-weight:600; color:var(--text-primary); margin-bottom:8px;">
                部位參數明細
              </div>
              <div class="kv-row">
                <span class="kv-label">方向</span>
                <span class="kv-value">${bot.position.direction}</span>
              </div>
              <div class="kv-row">
                <span class="kv-label">數量</span>
                <span class="kv-value">${bot.position.amount}</span>
              </div>
              <div class="kv-row">
                <span class="kv-label">平均成本</span>
                <span class="kv-value">${bot.position.entryPrice}</span>
              </div>
              <div class="kv-row">
                <span class="kv-label">最新標記價</span>
                <span class="kv-value">${bot.position.markPrice}</span>
              </div>
              <div class="kv-row">
                <span class="kv-label">實時有效槓桿</span>
                <span class="kv-value" style="color:var(--gold-primary);">${bot.position.leverage}</span>
              </div>
              <div class="kv-row">
                <span class="kv-label">部位估值時間</span>
                <span class="kv-value">${bot.position.valuationTime}</span>
              </div>
            </div>

            <!-- 運行事件歷史 (Alert Timeline) -->
            <div class="panel panel-specular" style="padding:14px;">
              <div style="font-size:12px; font-weight:600; color:var(--text-primary); margin-bottom:10px;">
                運行事件歷史
              </div>
              <div class="timeline-rail-wrap" style="padding-left:18px;">
                ${bot.events.map(ev => `
                  <div class="timeline-node-item" style="margin-bottom:12px;">
                    <div class="timeline-node-dot ${ev.severity}"></div>
                    <div class="timeline-item-header" style="display:flex; align-items:center; gap:8px;">
                      <span class="num" style="font-size:11px; color:#8c94a4;">${ev.time}</span>
                      <span class="badge ${ev.severity === 'WARN' ? 'badge-amber' : 'badge-ghost'}" style="font-size:11px; padding:1px 5px; font-weight:600;">
                        ${ev.severity}
                      </span>
                      <span class="timeline-item-title" style="font-weight:600; font-size:12.5px;">${ev.summary}</span>
                    </div>
                    <div style="font-size:11.5px; color:var(--text-secondary); line-height:1.45; margin-top:3px;">
                      ${ev.detail}
                    </div>
                    ${ev.observed ? `
                      <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">
                        觀察值: <code class="mono" style="color:var(--text-primary);">${ev.observed}</code>
                      </div>
                    ` : ''}
                  </div>
                `).join('')}
              </div>
            </div>
          </div>

          <!-- 右欄 -->
          <div style="display:flex; flex-direction:column; gap:14px;">
            <!-- 撮合委託明細 -->
            <div class="panel panel-specular" style="padding:14px;">
              <div style="font-size:12px; font-weight:600; color:var(--text-primary); margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;">
                <span>撮合委託明細</span>
                <span style="font-size:11px; color:var(--gold-primary); font-family:var(--font-mono);">[示意資料 · 未連線交易所]</span>
              </div>
              <div style="border:1px solid var(--border-subtle); border-radius:2px; overflow:hidden;">
                <table class="data-table" style="border:none; font-size:11.5px; width:100%;">
                  <thead>
                    <tr>
                      <th style="padding:6px 8px; vertical-align:bottom;">
                        <div class="th-dual-zh">時間</div>
                        <div class="th-dual-en">TIMESTAMP</div>
                      </th>
                      <th style="padding:6px 8px; vertical-align:bottom;">
                        <div class="th-dual-zh">方向</div>
                        <div class="th-dual-en">SIDE</div>
                      </th>
                      <th style="padding:6px 8px; vertical-align:bottom;">
                        <div class="th-dual-zh">狀態</div>
                        <div class="th-dual-en">STATE</div>
                      </th>
                      <th style="padding:6px 8px; vertical-align:bottom;">
                        <div class="th-dual-zh">數量</div>
                        <div class="th-dual-en">SIZE</div>
                      </th>
                      <th style="padding:6px 8px; vertical-align:bottom;">
                        <div class="th-dual-zh">價格</div>
                        <div class="th-dual-en">PRICE</div>
                      </th>
                      <th style="padding:6px 8px; text-align:right; vertical-align:bottom;">
                        <div class="th-dual-zh">費用</div>
                        <div class="th-dual-en">FEE</div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    ${bot.orders.length > 0 ? bot.orders.map(o => `
                      <tr>
                        <td class="num" style="font-size:11.5px; padding:5px 8px;">${o.time.split(' ')[1] || o.time}</td>
                        <td class="bot-nowrap" style="padding:5px 8px;">
                          <span class="badge ${o.side === '買入' ? 'badge-green' : 'badge-red'}" style="font-size:11px; padding:1px 5px; font-weight:600;">${o.side}</span>
                        </td>
                        <td class="bot-nowrap" style="font-size:11px; color:${o.status === '完全成交' ? 'var(--color-green)' : 'var(--color-amber)'}; padding:5px 8px;">
                          ${o.status}
                        </td>
                        <td class="num" style="padding:5px 8px;">${o.size}</td>
                        <td class="num" style="padding:5px 8px;">${o.avgPrice}</td>
                        <td class="num" style="color:var(--text-muted); font-size:11px; padding:5px 8px; text-align:right;">${o.fee}</td>
                      </tr>
                    `).join('') : `
                      <tr><td colspan="6" style="text-align:center; padding:16px; color:var(--text-muted);">無委託與成交記錄</td></tr>
                    `}
                  </tbody>
                </table>
              </div>
            </div>

            <!-- 十、生命週期控制 (全部 disabled，標示「執行控制尚未接線」) -->
            <div class="panel panel-specular" style="padding:14px;">
              <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
                <div style="font-size:12px; font-weight:600; color:var(--text-primary);">Bot 生命週期控制</div>
                <span class="badge" style="font-size:10px; color:var(--color-amber); background:rgba(251,191,36,0.1); border:1px solid rgba(251,191,36,0.2);">
                  執行控制尚未接線
                </span>
              </div>
              <div style="font-size:11px; color:var(--text-muted); margin-bottom:10px; line-height:1.4;">
                生產環境中需經過 Supervisor 交易授權與風控 Latch 解除程序方可調整。原型階段控制項全數鎖定。
              </div>
              <div style="display:flex; gap:8px;">
                <button class="btn btn-sm btn-ghost disabled" style="cursor:not-allowed; opacity:0.5; font-size:11.5px;" disabled title="執行控制尚未接線">
                  暫停委託
                </button>
                <button class="btn btn-sm btn-ghost disabled" style="cursor:not-allowed; opacity:0.5; font-size:11.5px;" disabled title="執行控制尚未接線">
                  恢復交易
                </button>
                <button class="btn btn-sm btn-ghost disabled" style="cursor:not-allowed; opacity:0.5; font-size:11.5px;" disabled title="執行控制尚未接線">
                  重啟 Worker
                </button>
                <button class="btn btn-sm btn-danger disabled" style="cursor:not-allowed; opacity:0.5; font-size:11.5px;" disabled title="執行控制尚未接線">
                  緊急平倉
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  },

  /**
   * 狀態篩選處理
   * 規範三：當篩選排除目前 Inspector 正在看的 Bot 時，立即關閉 Inspector 並清除 selected row。
   */
  setStatusFilter: function(status) {
    const data = window.CATOS_DATA;
    const currSelectedId = window.appState.get('selectedBotId');
    const isDrawerOpen = window.appState.get('botDrawerOpen');

    let shouldCloseDrawer = false;
    if (isDrawerOpen && currSelectedId) {
      const currBot = data.bots.find(b => b.id === currSelectedId);
      if (currBot && status !== 'ALL' && currBot.status !== status) {
        shouldCloseDrawer = true;
      }
    }

    const updates = { botsStatusFilter: status };
    if (shouldCloseDrawer) {
      updates.botDrawerOpen = false;
      updates.selectedBotId = null;
    }

    window.appState.set(updates);
  },

  openDrawer: function(botId, triggerElementId) {
    window.appState.set({
      selectedBotId: botId,
      botDrawerOpen: true,
      lastFocusedButtonId: triggerElementId || null
    });
  },

  closeDrawer: function() {
    const lastFocusedId = window.appState.get('lastFocusedButtonId');
    window.appState.set({
      botDrawerOpen: false
    });

    // 焦點返回原本的詳情按鈕或列 (Accessibility Focus Restoration)
    if (lastFocusedId) {
      setTimeout(() => {
        const el = document.getElementById(lastFocusedId);
        if (el) el.focus();
      }, 50);
    }
  },

  switchDrawerTab: function(tabName) {
    window.appState.set({ botDrawerSubTab: tabName });
  },

  toggleEventDetail: function(index) {
    const curr = window.appState.get('expandedBotEventIndex');
    window.appState.set({
      expandedBotEventIndex: curr === index ? null : index
    });
  },

  openFullDetail: function(botId) {
    window.appState.set({
      selectedBotId: botId,
      botDrawerOpen: false,
      botFullDetailView: true
    });
  },

  closeFullDetail: function() {
    window.appState.set({
      botFullDetailView: false
    });
  }
};
