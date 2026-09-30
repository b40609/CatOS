/**
 * catOS Prototype - Reactive State Management with LocalStorage Persistence
 * Handles:
 * - Page navigation & routing
 * - Sub-tab states (strategy / backtest / optimize)
 * - Selected items for details (strategy, bot, backtest, yaozi)
 * - Filter criteria (logs, strategy search)
 * - Prototype scenarios ('active', 'empty', 'risk_latch')
 * - Dirty state tracking for uncommitted backtest configs
 */

const STORAGE_KEY = 'catos_research_state_v1';

class AppState {
  constructor() {
    this.listeners = new Set();
    this.state = this.loadInitialState();
    this.applyAppearanceToDom();
  }

  getDefaults() {
    return {
      activePage: 'dashboard', // 'dashboard' | 'strategy' | 'bots' | 'risk' | 'logs' | 'yaozi' | 'settings'

      // Sidebar Style Switcher (Locked to 'devtools_dual' as selected by user)
      sidebarStyle: 'devtools_dual',
      botDrawerOpen: false,
      botDrawerSubTab: 'position', // 'position' | 'events' | 'orders'
      botFullDetailView: false,     // false: Full-width Table + Drawer; true: Dedicated Full Detail Page
      selectedBotId: 'bot_btc_trend',
      botsStatusFilter: 'ALL',      // 'ALL' | 'RUNNING' | 'WARNING' | 'STOPPED'
      lastFocusedButtonId: null,    // For restoring keyboard focus on drawer close
      expandedBotEventIndex: null,  // Index of event with details expanded on demand

      // Vertical timeline expanded incident
      expandedIncidentId: null,
      serviceStatusPopoverOpen: false,

      strategyView: 'cards',   // 'cards' | 'table'
      strategySearch: '',
      strategyFilterCategory: 'ALL',
      selectedStrategyId: 'strat_atr_breakout',
      strategySubTab: 'strategy', // 'strategy' | 'backtest' | 'optimize'
      selectedStrategyVersion: 'v1.1',

      // Backtest state
      selectedBacktestId: 'bt_run_20260928_01',
      backtestConfigDrawerOpen: false,
      backtestFormDirty: false,
      backtestConfig: {
        symbol: 'BTC-USDT-SWAP',
        timeframe: '1h',
        startDate: '2025-06-01',
        endDate: '2026-03-01',
        initialCapital: '50000.00',
        makerFee: '0.02',
        takerFee: '0.05',
        slippagePct: '0.05',
        warmupBars: 100
      },

      // Optimization state
      optimizeComparingCandidates: ['opt_cand_01', 'opt_cand_02'],
      optimizationRunning: false,
      optimizationProgress: 100,

      // Risk state (Standardized to 10.0% Soft Loss / 15.0% Hard Circuit Breaker)
      unlatchModalOpen: false,
      riskDraftChanged: false,
      riskDraft: {
        softLossPct: '10.0',
        hardLossPct: '15.0',
        maxLeverage: '3.0',
        maxSingleAssetExposurePct: '50.0'
      },

      // Logs state
      logsFilter: {
        severity: 'ALL',
        source: 'ALL',
        target: '',
        search: ''
      },
      expandedLogId: null,

      // Yaozi state
      selectedYaoziId: 'yz_item_01',

      // Demo Scenario Control
      scenario: 'active', // 'active' | 'empty' | 'risk_latch'

      // Code view toggle in strategy
      codeDrawerOpen: false,
      versionHistoryOpen: false,

      // Appearance & Theme Customization System (Presets + Continuous Hardware Sliders)
      appearance: {
        preset: 'muted_charcoal',
        bgTone: 'charcoal',
        textContrast: 'soft',          // 'soft' | 'standard' | 'crisp' | 'custom'
        textContrastValue: 88,         // 55 ~ 100 (%)
        accentSaturation: 'muted',     // 'muted' | 'standard' | 'vibrant' | 'custom'
        accentSaturationValue: 72,     // 30 ~ 100 (%)
        translucency: 'subtle_glow',   // 'solid' | 'subtle_glow' | 'aero_frost' | 'cyber_glow' | 'custom'
        translucencyValue: 80,         // 30 ~ 100 (%)
        elevation: 'subtle',
        fontScale: '100',              // '88' | '100' | '112' | '125' | 'custom'
        fontScaleValue: 100,           // 80 ~ 130 (%)
        tableDensity: 'standard',      // 'ultra' | 'compact' | 'standard' | 'relaxed' | 'custom'
        tableDensityValue: 38,         // 24 ~ 54 (px)
        sidebarWidth: 238,             // 58 ~ 280 (px)
        tabularMono: true,
        pnlPalette: 'traditional',
        chartGridOpacity: '50',
        zenSidebar: false
      }
    };
  }

  applyAppearanceToDom() {
    if (typeof document === 'undefined' || !document.documentElement || !document.documentElement.setAttribute) return;
    const a = (this.state && this.state.appearance) ? this.state.appearance : this.getDefaults().appearance;
    const root = document.documentElement;

    // 1. Preset & Base Attributes
    root.setAttribute('data-theme-preset', a.preset || 'muted_charcoal');
    root.setAttribute('data-text-contrast', a.textContrast || 'soft');
    root.setAttribute('data-accent-sat', a.accentSaturation || 'muted');
    root.setAttribute('data-pnl-palette', a.pnlPalette || 'traditional');
    root.setAttribute('data-translucency', a.translucency || 'subtle_glow');
    root.setAttribute('data-density', a.tableDensity || 'standard');
    root.setAttribute('data-font-scale', a.fontScale || '100');

    // 2. Zen Mode & Sidebar Width
    const sidebarW = parseInt(a.sidebarWidth || (a.zenSidebar ? 58 : 238), 10);
    const isZen = Boolean(a.zenSidebar || sidebarW < 100);
    root.setAttribute('data-zen-sidebar', isZen ? 'true' : 'false');
    root.style.setProperty('--sidebar-width', `${isZen ? 58 : sidebarW}px`);

    // 3. Continuous Dynamic Font & UI Zoom (80% ~ 130%)
    const fontVal = parseInt(a.fontScaleValue || (a.fontScale === 'custom' ? 100 : a.fontScale) || 100, 10);
    root.style.setProperty('--ui-font-scale', (fontVal / 100).toFixed(2));

    // 4. Continuous Table & Log Density (24px ~ 54px)
    const densityVal = parseInt(a.tableDensityValue || 38, 10);
    const padY = Math.max(2, Math.round((densityVal - 20) / 2));
    root.style.setProperty('--table-row-height', `${densityVal}px`);
    root.style.setProperty('--table-cell-padding-y', `${padY}px`);
    root.style.setProperty('--log-row-padding-y', `${Math.max(3, padY - 1)}px`);

    // 5. Continuous Text Luminance / Contrast (55% ~ 100%)
    const textVal = parseInt(a.textContrastValue || 88, 10);
    const textLum = (textVal / 100).toFixed(2);
    root.style.setProperty('--text-primary-alpha', textLum);
    if (a.textContrast === 'custom') {
      const primaryRgb = Math.round(240 * (textVal / 100));
      root.style.setProperty('--text-primary', `rgb(${primaryRgb}, ${primaryRgb}, ${Math.min(255, primaryRgb + 4)})`);
      root.style.setProperty('--text-secondary', `rgb(${Math.round(primaryRgb * 0.76)}, ${Math.round(primaryRgb * 0.79)}, ${Math.round(primaryRgb * 0.84)})`);
    }

    // 6. Continuous Accent Saturation (30% ~ 100%)
    const satVal = parseInt(a.accentSaturationValue || 75, 10);
    if (a.accentSaturation === 'custom') {
      root.style.setProperty('--gold-primary', `hsl(43, ${satVal}%, ${46 + Math.round((satVal - 40) * 0.08)}%)`);
      root.style.setProperty('--gold-hover', `hsl(43, ${Math.min(100, satVal + 12)}%, 56%)`);
      root.style.setProperty('--gold-dim', `hsl(43, ${Math.max(20, satVal - 25)}%, 36%)`);
      root.style.setProperty('--border-gold', `hsla(43, ${satVal}%, 50%, 0.38)`);
      root.style.setProperty('--gold-bg', `hsla(43, ${satVal}%, 50%, 0.09)`);
    }

    // 7. Continuous Translucency & Material (30% ~ 100%)
    const transVal = parseInt(a.translucencyValue || 80, 10);
    const alpha = (transVal / 100).toFixed(2);
    const blurPx = Math.round((1 - transVal / 100) * 24);
    root.style.setProperty('--header-opacity', alpha);
    root.style.setProperty('--header-blur', `${blurPx}px`);
  }

  loadInitialState() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        const state = Object.assign(this.getDefaults(), parsed);
        if (!state.riskDraftChanged && window.CATOS_DATA && window.CATOS_DATA.risk) {
          state.riskDraft = Object.assign({}, window.CATOS_DATA.risk.settings);
        }
        return state;
      }
    } catch (e) {
      console.warn('Failed to load saved state from localStorage:', e);
    }
    return this.getDefaults();
  }

  saveState() {
    try {
      // Avoid saving transient animations or modals
      const toSave = Object.assign({}, this.state);
      toSave.unlatchModalOpen = false;
      toSave.optimizationRunning = false;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
    } catch (e) {
      console.warn('Failed to persist state:', e);
    }
  }

  get(key) {
    if (!key) return this.state;
    return this.state[key];
  }

  set(updates, shouldNotify = true) {
    let changed = false;
    for (const [key, value] of Object.entries(updates)) {
      if (this.state[key] !== value) {
        this.state[key] = value;
        changed = true;
      }
    }
    if (changed) {
      if (updates.appearance) {
        this.applyAppearanceToDom();
      }
      this.saveState();
      if (shouldNotify) {
        this.notify();
      }
    }
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      try {
        listener(this.state);
      } catch (err) {
        console.error('State listener error:', err);
      }
    }
  }

  resetAll() {
    this.state = this.getDefaults();
    localStorage.removeItem(STORAGE_KEY);
    this.notify();
  }
}

window.appState = new AppState();
