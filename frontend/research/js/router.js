/**
 * catOS Prototype - Core Router & Layout Renderer
 * Coordinates:
 * - Fixed Left Sidebar (Dashboard, Strategy, Bots, Risk, Logs, Yaozi, Settings)
 * - Minimalist Header (Page Name, Current Env, Service Heartbeats, Essential Actions)
 * - Restores last page, selected items, sub-tabs and filters from localStorage
 * - Seamless page rendering without full reloads
 */

window.AppRouter = {
  routes: {
    dashboard: window.DashboardView,
    strategy: window.StrategyView,
    bots: window.BotsView,
    risk: window.RiskView,
    logs: window.LogsView,
    yaozi: window.YaoziView,
    settings: window.SettingsView
  },

  pageTitles: {
    dashboard: 'Dashboard 戰情總覽',
    strategy: 'Strategy 策略中心',
    bots: 'Bots 機器人管理',
    risk: 'Risk 風險控管',
    logs: 'Logs 系統日誌',
    yaozi: 'Yaozi 市場情報',
    settings: 'Settings 設定與連線'
  },

  init: function() {
    // Subscribe to state changes
    window.appState.subscribe((state) => {
      this.renderApp(state);
    });

    // Initial render
    this.renderApp(window.appState.state);
  },

  renderApp: function(state) {
    const activePage = state.activePage || 'dashboard';
    const viewModule = this.routes[activePage] || this.routes.dashboard;

    // 1. Render Sidebar
    const sidebarContainer = document.getElementById('app-sidebar-container');
    if (sidebarContainer) {
      sidebarContainer.innerHTML = this.renderSidebar(state, activePage);
    }

    // 2. Render Header
    const headerContainer = document.getElementById('app-header-container');
    if (headerContainer) {
      headerContainer.innerHTML = this.renderHeader(state, activePage);
    }

    // 3. Render Content Viewport
    const viewport = document.getElementById('app-viewport');
    if (viewport && viewModule) {
      viewport.innerHTML = viewModule.render(state);
      if (typeof viewModule.afterRender === 'function') {
        // Run after DOM has painted
        requestAnimationFrame(() => {
          viewModule.afterRender(state);
        });
      }
    }
  },

  renderSidebar: function(state, activePage) {
    const data = window.CATOS_DATA;

    // --- 1. Brand Section (定案：雙層工作台品牌) ---
    const brandHtml = `
      <div class="sidebar-brand">
        <div class="brand-wrapper">
          <div class="brand-micro-glyph" style="background:#090a0d; border-color:var(--gold-primary);"></div>
          <div>
            <div class="brand-title-text">
              <span>catOS</span>
              <span style="font-size:11px; color:var(--gold-primary); font-family:var(--font-mono); border:1px solid var(--border-gold-subtle); padding:1px 5px; border-radius:2px; font-weight:600;">v1.1.2</span>
            </div>
            <div class="brand-sub-caption">TRADING WORKSTATION</div>
          </div>
        </div>
      </div>
    `;

    // --- 2. Nav Items Definition (定案：主行繁中 13.5px + 次行 11px Monospace 英文代號) ---
    const navItems = [
      { id: 'dashboard', zh: '戰情總覽', en: 'DASHBOARD', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>' },
      { id: 'strategy', zh: '策略中心', en: 'STRATEGY LAB', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>' },
      { id: 'bots', zh: '機器人管理', en: 'BOTS FLEET', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/></svg>' },
      { id: 'risk', zh: '風險控管', en: 'RISK LATCH', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>' },
      { id: 'logs', zh: '系統日誌', en: 'AUDIT LOGS', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>' },
      { id: 'yaozi', zh: '市場情報', en: 'YAOZI INTEL', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>' },
      { id: 'settings', zh: '系統設定', en: 'CONFIGURATION', icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>' }
    ];

    const navListHtml = navItems.map(item => `
      <div class="nav-item ${activePage === item.id ? 'active' : ''}" onclick="window.AppRouter.navigate('${item.id}')">
        ${item.icon}
        <div class="nav-dual-wrap">
          <span class="nav-dual-title">${item.zh}</span>
          <span class="nav-dual-sub">${item.en}</span>
        </div>
      </div>
    `).join('');

    // --- 3. Supervisor 遙測晶片 ---
    const middleHtml = `
      <div class="sidebar-telemetry-chip">
        <div style="display:flex; justify-content:space-between; margin-bottom:4px; font-size:11px; color:var(--text-muted); font-weight:500;">
          <span>SUPERVISOR TELEMETRY</span>
          <span style="color:var(--color-green); font-weight:600;">ACTIVE</span>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:11.5px; color:var(--text-secondary); font-family:var(--font-mono);">
          <span>CPU 12%</span>
          <span>MEM 342M</span>
          <span>WSS 21ms</span>
        </div>
      </div>
    `;

    // --- 4. 側邊欄底座狀態 (定案：移除切換條，純淨連線狀態) ---
    const footerHtml = `
      <div class="sidebar-status-line">
        <div style="display:flex; align-items:center; gap:6px;">
          <span class="badge-dot green" style="width:6px; height:6px;"></span>
          <span style="color:var(--text-primary); font-weight:500;">OKX Sandbox</span>
        </div>
        <span style="color:var(--color-green); font-weight:500;">21 ms</span>
      </div>
    `;

    return `
      <div class="app-sidebar">
        <!-- Brand -->
        ${brandHtml}

        <!-- Navigation items -->
        <div class="sidebar-nav">
          ${navListHtml}
        </div>

        <!-- Supervisor Telemetry -->
        ${middleHtml}

        <!-- Sidebar Footer (定案純淨狀態) -->
        <div class="sidebar-footer">
          ${footerHtml}
        </div>
      </div>
    `;
  },

  pageDualHeaders: {
    dashboard: { zh: '戰情總覽', en: 'EXECUTIVE OVERVIEW // ACCOUNT TELEMETRY' },
    strategy: { zh: '策略中心', en: 'STRATEGY LAB // CODE & BACKTEST' },
    bots: { zh: '機器人管理', en: 'BOTS FLEET // RUNTIME MONITOR' },
    risk: { zh: '風險控管', en: 'RISK ENGINE // HARD-LATCH CIRCUIT' },
    logs: { zh: '系統日誌', en: 'AUDIT LOGS // EVENT STREAM' },
    yaozi: { zh: '市場情報', en: 'YAOZI INTEL // ALPHA SIGNALS' },
    settings: { zh: '系統設定', en: 'PREFERENCES // CONNECTION NODES' }
  },

  renderHeader: function(state, activePage) {
    const data = window.CATOS_DATA;
    let headerInfo = this.pageDualHeaders[activePage] || { zh: 'catOS 工作台', en: 'WORKSTATION' };

    if (activePage === 'strategy' && state.strategyInDetail) {
      const strat = data.strategies.find(s => s.id === state.selectedStrategyId) || data.strategies[0];
      headerInfo = { zh: `策略中心 / ${strat.name}`, en: `STRATEGY // ${strat.id.toUpperCase()}` };
    } else if (activePage === 'bots' && state.botFullDetailView) {
      const bot = data.bots.find(b => b.id === state.selectedBotId) || data.bots[0];
      headerInfo = { zh: `機器人工作台 / ${bot.name}`, en: `BOT WORKSPACE // ${bot.id.toUpperCase()}` };
    }

    return `
      <header class="app-header">
        <div class="header-left">
          <div class="header-dual-title">
            <div class="header-dual-title-main">${headerInfo.zh}</div>
            <div class="header-dual-title-sub">${headerInfo.en}</div>
          </div>
          <div class="env-pill-dual">
            <span class="env-dual-zh" style="color:var(--gold-primary);">原型・示意資料</span>
            <span class="env-dual-en">PROTOTYPE // MOCK</span>
          </div>
        </div>

        <div class="header-center">
          <!-- Single Consolidated Technical Status Popover Entry (Dual-Tier) -->
          <div class="status-popover-trigger">
            <button class="btn btn-sm btn-ghost service-pill-dual" onclick="window.AppRouter.toggleServicePopover()">
              <span class="badge-dot green" style="width:6px; height:6px;"></span>
              <div style="display:flex; flex-direction:column; text-align:left; line-height:1.2;">
                <span style="font-size:12px; font-weight:600; color:var(--text-primary);">底座模擬就緒</span>
                <span style="font-size:11px; font-family:var(--font-mono); color:var(--text-muted); font-weight:500;">SUPERVISOR // SIMULATED</span>
              </div>
              <span style="font-size:10px; color:var(--text-muted); margin-left:4px;">${state.serviceStatusPopoverOpen ? '▲' : '▼'}</span>
            </button>

            <!-- Technical Status Popover Menu -->
            <div class="status-popover-menu ${state.serviceStatusPopoverOpen ? 'open' : ''}">
              <div style="font-size:12.5px; font-weight:600; color:var(--text-primary); margin-bottom:8px; border-bottom:1px solid var(--border-subtle); padding-bottom:6px;">
                底座運作狀態 <span style="font-size:11px; color:var(--gold-primary); font-family:var(--font-mono); font-weight:normal;">[原型模擬 · 未連真實交易所]</span>
              </div>
              <div style="display:flex; flex-direction:column; gap:6px; font-size:11.5px;">
                <div style="display:flex; justify-content:space-between;">
                  <span style="color:var(--text-muted);">Supervisor 進程:</span>
                  <span class="num font-weight:600;" style="color:var(--color-green);">PID ${data.meta.supervisor.pid} (ONLINE)</span>
                </div>
                <div style="display:flex; justify-content:space-between;">
                  <span style="color:var(--text-muted);">OKX WebSocket:</span>
                  <span class="num" style="color:var(--color-green);">${data.meta.supervisor.latency}</span>
                </div>
                <div style="display:flex; justify-content:space-between;">
                  <span style="color:var(--text-muted);">Worker 訊號計算:</span>
                  <span style="color:var(--gold-primary); font-weight:500;">Zero-Net Active</span>
                </div>
                <div style="display:flex; justify-content:space-between;">
                  <span style="color:var(--text-muted);">記憶體佔用:</span>
                  <span class="num">${data.meta.supervisor.memoryUsage}</span>
                </div>
                <div style="display:flex; justify-content:space-between;">
                  <span style="color:var(--text-muted);">持續運作:</span>
                  <span class="num">${data.meta.supervisor.uptime}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="header-right">
          <button class="btn btn-sm btn-ghost" title="自訂外觀配色、對比與字級" onclick="window.AppRouter.navigate('settings')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 2a7 7 0 0 0 0 14v6"/></svg>
            <span>外觀調色</span>
          </button>
          <button class="btn btn-sm btn-ghost" title="切換情境設定" onclick="window.AppRouter.navigate('settings')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
            展示情境
          </button>
          <button class="btn btn-sm btn-ghost" onclick="alert('全域狀態同步完畢。當前為最新 K 線收盤數據。')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            刷新
          </button>
        </div>
      </header>
    `;
  },

  navigate: function(page) {
    if (this.routes[page]) {
      window.appState.set({ activePage: page });
    }
  }
};
