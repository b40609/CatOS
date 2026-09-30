/**
 * catOS Workspace Engine - OKX Institutional Seamless Tiling & Continuous Splitter Edition
 * 
 * 核心升級：
 * 1. OKX 原生級無縫瓦片 (Seamless Tiling & Zero Void)：
 *    - 徹底告別離散 12 欄與 76px 粗糙跳格斷落感。
 *    - 所有模組面板 100% 無縫貼合，天生自動填滿，絕無黑色孤島與空隙。
 * 2. 像素級連續平滑分割條 (Continuous Pixel-Level Splitters)：
 *    - 水平與垂直分割條支援 1px 解析度平滑連續拖曳。
 *    - 雙擊分割條 (Double Click) 一鍵重設對稱平衡比例。
 * 3. 智慧自動填滿 (Auto-Pack / Fill)：
 *    - 一鍵「⚡ 自動填滿」，依黃金比例與均分邏輯將所有可見面板完美鋪滿 100% 視窗。
 * 4. 面板一鍵最大化 (Maximize / Fullscreen Panel)。
 * 5. 跨預設集獨立記憶 (Executive / Research / Sentinel)。
 */

window.WorkspaceEngine = {
  isEditing: false,
  currentPresetId: 'executive',
  activePage: 'dashboard',
  _editSnapshot: null,
  _historyByLayout: {},
  _historyStack: [],
  hiddenWidgets: [],
  maximizedPaneId: null,
  _isBusyDragging: false,
  _resizeDebounceTimer: null,
  _splittersInitialized: false,

  // 1. Dashboard Widget Registry (約束與元數據)
  widgets: {
    kpi_grid: {
      id: 'kpi_grid',
      title: '核心指標',
      en: 'KPI TELEMETRY',
      desc: '執行訊號、合成成交、帳戶與風控接線狀態。',
      minW: 6,
      minH: 2,
      maxH: 4,
      defaultW: 12,
      defaultH: 2
    },
    equity_chart: {
      id: 'equity_chart',
      title: '研究權益走勢',
      en: 'EQUITY CURVE',
      desc: '已保存回測的研究權益曲線。',
      minW: 6,
      minH: 4,
      defaultW: 8,
      defaultH: 5
    },
    incident_timeline: {
      id: 'incident_timeline',
      title: '執行事件',
      en: 'INCIDENT STREAM',
      desc: 'R4 訊號、模擬成交與異常記錄，可開啟事件詳情。',
      minW: 4,
      minH: 4,
      defaultW: 4,
      defaultH: 5
    },
    active_bots: {
      id: 'active_bots',
      title: '本機執行隊列',
      en: 'ACTIVE BOTS',
      desc: 'R4 執行記錄、訊號與模擬成交。',
      minW: 3,
      minH: 3,
      defaultW: 4,
      defaultH: 4
    },
    research_tasks: {
      id: 'research_tasks',
      title: '近期研究任務',
      en: 'RESEARCH QUEUE',
      desc: '同一研究服務已保存的回測與參數搜尋。',
      minW: 3,
      minH: 3,
      defaultW: 4,
      defaultH: 4
    },
    yaozi_brief: {
      id: 'yaozi_brief',
      title: 'Yaozi 市場情報',
      en: 'YAOZI INTEL',
      desc: '情報接線狀態。',
      minW: 3,
      minH: 3,
      defaultW: 4,
      defaultH: 4
    }
  },

  // 2. 官方預設集 (包含相容格式與連續分割比例)
  presets: {
    executive: {
      id: 'executive',
      name: '戰情總覽',
      en: 'EXECUTIVE',
      splits: {
        upperHeightPct: 56,
        upperTier: { equity_chart: 66, incident_timeline: 34 },
        lowerTier: { active_bots: 33.33, research_tasks: 33.33, yaozi_brief: 33.34 }
      },
      desktop: [
        { id: 'kpi_grid', x: 0, y: 0, w: 12, h: 2 },
        { id: 'equity_chart', x: 0, y: 2, w: 8, h: 5 },
        { id: 'incident_timeline', x: 8, y: 2, w: 4, h: 5 },
        { id: 'active_bots', x: 0, y: 7, w: 4, h: 4 },
        { id: 'research_tasks', x: 4, y: 7, w: 4, h: 4 },
        { id: 'yaozi_brief', x: 8, y: 7, w: 4, h: 4 }
      ],
      compact: [
        { id: 'kpi_grid', x: 0, y: 0, w: 12, h: 2 },
        { id: 'equity_chart', x: 0, y: 2, w: 12, h: 5 },
        { id: 'incident_timeline', x: 0, y: 7, w: 12, h: 5 },
        { id: 'active_bots', x: 0, y: 12, w: 6, h: 4 },
        { id: 'research_tasks', x: 6, y: 12, w: 6, h: 4 },
        { id: 'yaozi_brief', x: 0, y: 16, w: 12, h: 4 }
      ]
    },
    research: {
      id: 'research',
      name: '研究模式',
      en: 'RESEARCH',
      splits: {
        upperHeightPct: 65,
        upperTier: { equity_chart: 100, incident_timeline: 0 },
        lowerTier: { active_bots: 0, research_tasks: 50, yaozi_brief: 50 }
      },
      desktop: [
        { id: 'equity_chart', x: 0, y: 0, w: 12, h: 6 },
        { id: 'research_tasks', x: 0, y: 6, w: 6, h: 4 },
        { id: 'yaozi_brief', x: 6, y: 6, w: 6, h: 4 },
        { id: 'kpi_grid', x: 0, y: 10, w: 12, h: 2 },
        { id: 'active_bots', x: 0, y: 12, w: 6, h: 4 },
        { id: 'incident_timeline', x: 6, y: 12, w: 6, h: 4 }
      ],
      compact: [
        { id: 'equity_chart', x: 0, y: 0, w: 12, h: 5 },
        { id: 'research_tasks', x: 0, y: 5, w: 12, h: 4 },
        { id: 'yaozi_brief', x: 0, y: 9, w: 12, h: 4 },
        { id: 'kpi_grid', x: 0, y: 13, w: 12, h: 2 },
        { id: 'active_bots', x: 0, y: 15, w: 12, h: 4 },
        { id: 'incident_timeline', x: 0, y: 19, w: 12, h: 4 }
      ]
    },
    sentinel: {
      id: 'sentinel',
      name: '夜間監控',
      en: 'SENTINEL',
      splits: {
        upperHeightPct: 52,
        upperTier: { incident_timeline: 50, active_bots: 50 },
        lowerTier: { equity_chart: 60, research_tasks: 0, yaozi_brief: 40 }
      },
      desktop: [
        { id: 'incident_timeline', x: 0, y: 0, w: 6, h: 6 },
        { id: 'active_bots', x: 6, y: 0, w: 6, h: 6 },
        { id: 'kpi_grid', x: 0, y: 6, w: 12, h: 2 },
        { id: 'equity_chart', x: 0, y: 8, w: 8, h: 4 },
        { id: 'yaozi_brief', x: 8, y: 8, w: 4, h: 4 },
        { id: 'research_tasks', x: 0, y: 12, w: 12, h: 3 }
      ],
      compact: [
        { id: 'incident_timeline', x: 0, y: 0, w: 12, h: 5 },
        { id: 'active_bots', x: 0, y: 5, w: 12, h: 5 },
        { id: 'kpi_grid', x: 0, y: 10, w: 12, h: 2 },
        { id: 'equity_chart', x: 0, y: 12, w: 12, h: 4 },
        { id: 'yaozi_brief', x: 0, y: 16, w: 12, h: 4 },
        { id: 'research_tasks', x: 0, y: 20, w: 12, h: 3 }
      ]
    }
  },

  // Mock Grid adapter for test suite compatibility
  grid: null,

  getStorageKey: function(presetId) {
    const isDesktop = (typeof window !== 'undefined') ? (window.innerWidth >= 1440) : true;
    const mode = isDesktop ? 'desktop' : 'compact';
    const targetPreset = presetId || this.currentPresetId || 'executive';
    return `catos_layout_${this.activePage}_${targetPreset}_${mode}_home_preview_v1`;
  },

  getPresetStorageKey: function() {
    return `catos_active_preset_${this.activePage}_home_preview_v1`;
  },

  getHiddenStorageKey: function(presetId) {
    const targetPreset = presetId || this.currentPresetId || 'executive';
    return `catos_hidden_${this.activePage}_${targetPreset}_home_preview_v1`;
  },

  /**
   * 初始化無縫連續分割引擎
   */
  init: function(containerId, pageId) {
    this.activePage = pageId || 'dashboard';
    this._editSnapshot = null;
    this._lastSnapshot = null;
    this.maximizedPaneId = null;

    // 建立向後相容的 GridStack Mock 橋接器，確保現有單元測試與環境完全順利，且平鋪佈局不發出找不到 .grid-stack 錯誤
    const self = this;
    const isMockEnv = typeof document === 'undefined' || typeof document.querySelector !== 'function';
    const hasGridStackDom = typeof document !== 'undefined' && typeof document.querySelector === 'function' && !!document.querySelector('.grid-stack');

    if ((hasGridStackDom || isMockEnv) && typeof window !== 'undefined' && window.GridStack && typeof window.GridStack.init === 'function') {
      try {
        this.grid = window.GridStack.init({
          column: 12,
          cellHeight: 76,
          animate: true,
          resizable: { handles: 'e, se, s, sw, w' }
        });
      } catch (e) {
        this.grid = null;
      }
    }

    if (!this.grid) {
      this.grid = {
        el: (typeof document !== 'undefined' && typeof document.getElementById === 'function') ? document.getElementById(containerId) : null,
        enableMove: (val) => {},
        enableResize: (val) => {},
        on: (evt, handler) => {},
        load: (items) => {
          self._loadedMockItems = items;
        },
        save: (val) => {
          return self._loadedMockItems || (self.presets[self.currentPresetId] ? self.presets[self.currentPresetId].desktop : []);
        },
        removeWidget: (el) => {},
        addWidget: (el, opts) => {},
        compact: () => {},
        destroy: () => {}
      };
    }

    // 讀取當前儲存的 Preset
    if (typeof localStorage !== 'undefined') {
      const savedPreset = localStorage.getItem(this.getPresetStorageKey());
      if (savedPreset && this.presets[savedPreset]) {
        this.currentPresetId = savedPreset;
      }

      // 讀取隱藏清單
      try {
        this.hiddenWidgets = JSON.parse(localStorage.getItem(this.getHiddenStorageKey()) || '[]');
      } catch (e) {
        this.hiddenWidgets = [];
      }
    }

    this.selectUndoHistory();
    // 載入版面配置
    this.loadLayout();

    // 預設鎖定，防止誤觸
    this.setEditing(false);

    // 掛載 OKX 像素級連續分割條事件與卡片標題拖曳換位事件
    if (typeof window !== 'undefined' && typeof document !== 'undefined') {
      setTimeout(() => {
        this.initSplitters();
        this.initCardDragAndDrop();
      }, 50);
    }
  },

  /**
   * 初始化 OKX 像素級分割條監聽器 (Continuous Dragging & Double Click Reset)
   */
  initSplitters: function() {
    if (typeof document === 'undefined') return;
    const splitters = document.querySelectorAll('.workspace-splitter');
    if (!splitters || splitters.length === 0) return;

    splitters.forEach(sp => {
      if (!sp || typeof sp.addEventListener !== 'function') return;
      if (sp._catosSplitterBound) return;
      sp._catosSplitterBound = true;
      // 雙擊重設比例
      sp.addEventListener('dblclick', (e) => {
        e.preventDefault();
        this.resetSingleSplitter(sp);
      });

      // 拖曳開始
      sp.addEventListener('mousedown', (e) => {
        e.preventDefault();
        this.startDraggingSplitter(sp, e);
      });

      // 觸控支援
      sp.addEventListener('touchstart', (e) => {
        if (e.touches && e.touches[0]) {
          this.startDraggingSplitter(sp, e.touches[0]);
        }
      }, { passive: false });
    });
  },

  /**
   * 連續拖曳核心運算 (OKX 1px 無級流暢縮放)
   */
  startDraggingSplitter: function(splitter, startEvent) {
    this.takePreOpSnapshot();
    this._isBusyDragging = true;
    const isVertical = splitter.classList.contains('vertical');
    const body = document.body;
    body.classList.add(isVertical ? 'is-resizing-v' : 'is-resizing-h');
    splitter.classList.add('is-active-dragging');

    const startX = startEvent.clientX;
    const startY = startEvent.clientY;

    if (isVertical) {
      // 垂直分割條：調整左右兩面板寬度
      const leftId = splitter.getAttribute('data-left');
      const rightId = splitter.getAttribute('data-right');
      const leftEl = document.getElementById(leftId);
      const rightEl = document.getElementById(rightId);
      if (!leftEl || !rightEl) return;

      const parentEl = leftEl.parentElement;
      const parentWidth = parentEl.getBoundingClientRect().width;
      const startLeftWidth = leftEl.getBoundingClientRect().width;
      const startRightWidth = rightEl.getBoundingClientRect().width;
      const totalWidth = startLeftWidth + startRightWidth;

      const onMouseMove = (moveEvent) => {
        const clientX = moveEvent.clientX || (moveEvent.touches && moveEvent.touches[0] ? moveEvent.touches[0].clientX : startX);
        const deltaX = clientX - startX;

        // 計算新寬度並施加最小 140px 邊界防禦
        let newLeftW = Math.max(140, Math.min(totalWidth - 140, startLeftWidth + deltaX));
        let newRightW = totalWidth - newLeftW;

        const leftPct = (newLeftW / parentWidth) * 100;
        const rightPct = (newRightW / parentWidth) * 100;

        leftEl.style.flex = `${leftPct.toFixed(2)} 1 0px`;
        rightEl.style.flex = `${rightPct.toFixed(2)} 1 0px`;
      };

      const onMouseUp = () => {
        this._isBusyDragging = false;
        body.classList.remove('is-resizing-v');
        splitter.classList.remove('is-active-dragging');
        window.removeEventListener('mousemove', onMouseMove);
        window.removeEventListener('mouseup', onMouseUp);
        window.removeEventListener('touchmove', onMouseMove);
        window.removeEventListener('touchend', onMouseUp);

        this.saveLayout();
        this.triggerSmoothChartResize();
      };

      window.addEventListener('mousemove', onMouseMove);
      window.addEventListener('mouseup', onMouseUp);
      window.addEventListener('touchmove', onMouseMove);
      window.addEventListener('touchend', onMouseUp);

    } else {
      // 水平分割條：調整上下兩層高度
      const topId = splitter.getAttribute('data-top');
      const bottomId = splitter.getAttribute('data-bottom');
      const topEl = document.getElementById(topId);
      const bottomEl = document.getElementById(bottomId);
      if (!topEl || !bottomEl) return;

      const parentEl = topEl.parentElement;
      const parentHeight = parentEl.getBoundingClientRect().height;
      const startTopH = topEl.getBoundingClientRect().height;
      const startBottomH = bottomEl.getBoundingClientRect().height;
      const totalH = startTopH + startBottomH;

      if (topId === 'widget-kpi_grid') {
        // 拖曳頂部 KPI 核心指標網格高度
        const onMouseMove = (moveEvent) => {
          const clientY = moveEvent.clientY || (moveEvent.touches && moveEvent.touches[0] ? moveEvent.touches[0].clientY : startY);
          const deltaY = clientY - startY;
          let newTopH = Math.max(76, Math.min(260, startTopH + deltaY));
          topEl.style.height = `${newTopH}px`;
          this.triggerSmoothChartResize();
        };

        const onMouseUp = () => {
          this._isBusyDragging = false;
          body.classList.remove('is-resizing-h');
          splitter.classList.remove('is-active-dragging');
          window.removeEventListener('mousemove', onMouseMove);
          window.removeEventListener('mouseup', onMouseUp);
          window.removeEventListener('touchmove', onMouseMove);
          window.removeEventListener('touchend', onMouseUp);

          this.saveLayout();
          this.triggerSmoothChartResize();
        };

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
        window.addEventListener('touchmove', onMouseMove);
        window.addEventListener('touchend', onMouseUp);

      } else {
        // 水平分割條：調整上下兩層高度
        const onMouseMove = (moveEvent) => {
          const clientY = moveEvent.clientY || (moveEvent.touches && moveEvent.touches[0] ? moveEvent.touches[0].clientY : startY);
          const deltaY = clientY - startY;

          let newTopH = Math.max(120, Math.min(totalH - 120, startTopH + deltaY));
          let newBottomH = totalH - newTopH;

          const topPct = (newTopH / parentHeight) * 100;
          const bottomPct = (newBottomH / parentHeight) * 100;

          topEl.style.height = `${topPct.toFixed(2)}%`;
          bottomEl.style.height = `${bottomPct.toFixed(2)}%`;
        };

        const onMouseUp = () => {
          this._isBusyDragging = false;
          body.classList.remove('is-resizing-h');
          splitter.classList.remove('is-active-dragging');
          window.removeEventListener('mousemove', onMouseMove);
          window.removeEventListener('mouseup', onMouseUp);
          window.removeEventListener('touchmove', onMouseMove);
          window.removeEventListener('touchend', onMouseUp);

          this.saveLayout();
          this.triggerSmoothChartResize();
        };

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
        window.addEventListener('touchmove', onMouseMove);
        window.addEventListener('touchend', onMouseUp);
      }
    }
  },

  /**
   * 雙擊分割條：自動重設為 50:50 或平均寬度
   */
  resetSingleSplitter: function(splitter) {
    this.takePreOpSnapshot();
    const isVertical = splitter.classList.contains('vertical');
    if (isVertical) {
      const leftId = splitter.getAttribute('data-left');
      const rightId = splitter.getAttribute('data-right');
      const leftEl = document.getElementById(leftId);
      const rightEl = document.getElementById(rightId);
      if (leftEl && rightEl) {
        leftEl.style.flex = '1 1 0px';
        rightEl.style.flex = '1 1 0px';
      }
    } else {
      const topId = splitter.getAttribute('data-top');
      const bottomId = splitter.getAttribute('data-bottom');
      const topEl = document.getElementById(topId);
      const bottomEl = document.getElementById(bottomId);
      if (topEl && bottomEl) {
        if (topId === 'widget-kpi_grid') {
          topEl.style.height = '';
        } else {
          topEl.style.height = '56%';
          bottomEl.style.height = '44%';
        }
      }
    }
    this.saveLayout();
    this.triggerSmoothChartResize();
  },

  /**
   * 取得當前上下兩排卡片清單與 flex 比例
   * @param {boolean} includeHidden 是否包含隱藏面板（快照復原時需全數保留）
   */
  getCurrentTierLists: function(includeHidden = false) {
    const parseTier = (tierEl) => {
      if (!tierEl) return [];
      const children = Array.from(tierEl.children || []);
      const panes = children.filter(c => {
        if (!c.classList || !c.classList.contains('tiling-pane')) return false;
        if (!includeHidden && c.style && c.style.display === 'none') return false;
        return true;
      });
      return panes.map(p => {
        const id = p.getAttribute('data-widget-id') || (p.id ? p.id.replace('widget-', '').replace('pane-', '') : '');
        let flexNum = 0;
        if (p.style && p.style.flex) {
          const parts = p.style.flex.trim().split(/\s+/);
          flexNum = parseFloat(parts[0]) || 0;
        }
        return { id, flex: flexNum };
      });
    };

    const upperTier = (typeof document !== 'undefined') ? document.getElementById('tiling-upper-tier') : null;
    const lowerTier = (typeof document !== 'undefined') ? document.getElementById('tiling-lower-tier') : null;

    return {
      upperWidgets: parseTier(upperTier),
      lowerWidgets: parseTier(lowerTier)
    };
  },

  /**
   * 擷取當前工作區完整快照（包含隱藏清單、各排面板排序、flex 比例、上下排高度與 KPI 高度）
   */
  captureCurrentState: function() {
    const tierLists = this.getCurrentTierLists(true);
    const upperTier = (typeof document !== 'undefined') ? document.getElementById('tiling-upper-tier') : null;
    const lowerTier = (typeof document !== 'undefined') ? document.getElementById('tiling-lower-tier') : null;
    const kpiEl = (typeof document !== 'undefined') ? document.getElementById('widget-kpi_grid') : null;

    // 快照以目前 DOM 為準，不能以先前保存的布局覆蓋尚未保存的尺寸。
    const splits = {
      kpiHeightPx: kpiEl && kpiEl.style.height ? parseFloat(kpiEl.style.height) : null,
      upperHeightPct: upperTier ? parseFloat(upperTier.style.height) || 56 : 56,
      upperWidgets: tierLists.upperWidgets,
      lowerWidgets: tierLists.lowerWidgets,
      upperTier: {},
      lowerTier: {}
    };
    tierLists.upperWidgets.forEach(w => { splits.upperTier[w.id] = w.flex; });
    tierLists.lowerWidgets.forEach(w => { splits.lowerTier[w.id] = w.flex; });

    return {
      presetId: this.currentPresetId,
      hidden: [...this.hiddenWidgets],
      upperH: upperTier ? upperTier.style.height : '56%',
      lowerH: lowerTier ? lowerTier.style.height : '44%',
      kpiH: (kpiEl && kpiEl.style.height) ? kpiEl.style.height : '',
      upperWidgets: JSON.parse(JSON.stringify(tierLists.upperWidgets || [])),
      lowerWidgets: JSON.parse(JSON.stringify(tierLists.lowerWidgets || [])),
      gridItems: this._loadedMockItems ? JSON.parse(JSON.stringify(this._loadedMockItems)) : null,
      splits: JSON.parse(JSON.stringify(splits))
    };
  },

  selectUndoHistory: function() {
    const key = this.getStorageKey();
    if (!this._historyByLayout[key]) this._historyByLayout[key] = [];
    if (this._undoLayoutKey !== key) {
      this._editSnapshot = null;
      this._lastSnapshot = null;
    }
    this._undoLayoutKey = key;
    this._historyStack = this._historyByLayout[key];
  },

  /**
   * 將快照推入還原堆疊，支援多步復原與操作前精確回滾
   */
  pushSnapshot: function() {
    if (this._isReverting) return;
    this.selectUndoHistory();
    const state = this.captureCurrentState();
    if (!this._historyStack) this._historyStack = [];
    const last = this._historyStack[this._historyStack.length - 1];
    if (last && JSON.stringify(last) === JSON.stringify(state)) return;
    this._historyStack.push(state);
    if (this._historyStack.length > 20) this._historyStack.shift();
    this._lastSnapshot = state;
  },

  /**
   * 於每一次操作（拖曳換位、縮放、自動補齊、隱藏）前自動建立還原點
   */
  takePreOpSnapshot: function() {
    this.pushSnapshot();
    if (this.isEditing && !this._editSnapshot) {
      this._editSnapshot = this._lastSnapshot;
    }
  },

  /**
   * 拖曳卡片標題換位 (將 sourceId 移動至 targetId 前方或後方)
   */
  handleDropOnCard: function(sourceId, targetId, position = 'after') {
    if (typeof document === 'undefined') return;
    const srcEl = document.getElementById(`widget-${sourceId}`) || document.getElementById(`pane-${sourceId}`);
    const tgtEl = document.getElementById(`widget-${targetId}`) || document.getElementById(`pane-${targetId}`);
    if (!srcEl || !tgtEl) return;
    if (srcEl === tgtEl) return;
    this.takePreOpSnapshot();

    const targetTier = tgtEl.parentElement;
    if (position === 'after') {
      if (tgtEl.nextSibling) {
        targetTier.insertBefore(srcEl, tgtEl.nextSibling);
      } else {
        targetTier.appendChild(srcEl);
      }
    } else {
      targetTier.insertBefore(srcEl, tgtEl);
    }

    const upperTier = document.getElementById('tiling-upper-tier');
    const lowerTier = document.getElementById('tiling-lower-tier');
    this.rebuildTierSplitters(upperTier);
    this.rebuildTierSplitters(lowerTier);

    const updateFlex = (tEl) => {
      if (!tEl) return;
      const panes = Array.from(tEl.children).filter(c => c.classList && c.classList.contains('tiling-pane') && c.style.display !== 'none');
      if (panes.length === 0) return;
      const pct = (100 / panes.length).toFixed(2);
      panes.forEach(p => {
        p.style.flex = `${pct} 1 0px`;
      });
    };
    updateFlex(upperTier);
    updateFlex(lowerTier);

    this.saveLayout();
    this.triggerSmoothChartResize();
    if (typeof this.initSplitters === 'function') {
      this.initSplitters();
    }
    if (typeof this.initCardDragAndDrop === 'function') {
      this.initCardDragAndDrop();
    }
    this.triggerLandAnimation(sourceId);
    const titleText = (this.widgets && this.widgets[sourceId]) ? this.widgets[sourceId].title : sourceId;
    this.showLayoutToast(`已將 [${titleText}] 重新排列至新位置`);
  },

  /**
   * 初始化卡片標題拖曳換位引擎 (Card Header Drag-to-Reorder)
   * 業界標準無把手設計：直接按住文字標題或卡片標頭即可流暢拖曳換位
   */
  initCardDragAndDrop: function() {
    if (typeof document === 'undefined') return;
    const self = this;
    const panes = document.querySelectorAll('.tiling-pane');
    if (!panes || panes.length === 0) return;

    panes.forEach(pane => {
      const widgetId = pane.getAttribute('data-widget-id') || (pane.id ? pane.id.replace('widget-', '').replace('pane-', '') : '');
      // KPI 核心指標網格為固定頂部總覽條，不參與排版換位
      if (widgetId === 'kpi_grid') return;

      const header = pane.querySelector('.widget-box-header');
      if (!header) return;

      // 防止重複綁定
      if (header._catosDragBound) return;
      header._catosDragBound = true;

      // 確保排除原生 HTML5 drag 干擾
      header.setAttribute('draggable', 'false');
      header.ondragstart = (e) => { e.preventDefault(); return false; };

      // 阻止卡片標頭內的互動按鈕觸發拖曳
      const interactiveElements = header.querySelectorAll('button, a, input, select, .time-btn, .time-range-selector');
      interactiveElements.forEach(el => {
        el.setAttribute('draggable', 'false');
        el.addEventListener('mousedown', (e) => e.stopPropagation());
      });

      // --- 高靈敏純滑鼠拖曳監聽器 (直接按住標題文字拖曳) ---
      header.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return; // 僅限滑鼠左鍵
        if (e.target.closest && e.target.closest('button, a, input, select, .time-btn, .time-range-selector')) {
          return;
        }

        // 阻止原生文字選取
        e.preventDefault();

        const startX = e.clientX;
        const startY = e.clientY;
        let isDragging = false;
        let ghostCard = null;

        const onMouseMove = (moveEvent) => {
          const deltaX = moveEvent.clientX - startX;
          const deltaY = moveEvent.clientY - startY;
          const dist = Math.sqrt(deltaX * deltaX + deltaY * deltaY);

          // 門檻 4px：防範正常點擊誤觸
          if (!isDragging && dist > 4) {
            isDragging = true;
            self._draggedWidgetId = widgetId;
            pane.classList.add('is-dragging-card');
            document.body.classList.add('is-card-dragging-active');

            // 建立高保真浮動預覽代理卡片 (Institutional Floating Proxy)
            ghostCard = document.createElement('div');
            ghostCard.id = 'catos-drag-ghost-card';
            ghostCard.style.cssText = `
              position: fixed;
              pointer-events: none;
              z-index: 100000;
              width: 230px;
              background: rgba(14, 18, 26, 0.92);
              backdrop-filter: blur(16px);
              -webkit-backdrop-filter: blur(16px);
              border: 1px solid rgba(212, 175, 55, 0.75);
              border-radius: 4px;
              box-shadow: 0 16px 40px rgba(0, 0, 0, 0.85), 0 0 16px rgba(212, 175, 55, 0.25);
              padding: 9px 12px;
              transform: translate(14px, 14px) rotate(1.5deg);
              user-select: none;
              left: ${moveEvent.clientX}px;
              top: ${moveEvent.clientY}px;
            `;

            const cardTitle = (self.widgets && self.widgets[widgetId]) ? self.widgets[widgetId].title : widgetId;
            const cardEn = (self.widgets && self.widgets[widgetId]) ? self.widgets[widgetId].en : '';
            ghostCard.innerHTML = `
              <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:4px;">
                <span style="font-size:9.5px; font-weight:700; color:#ffd700; background:rgba(212,175,55,0.18); padding:1px 5px; border-radius:2px; font-family:var(--font-mono); letter-spacing:0.5px;">
                  REORDER
                </span>
                <span style="font-size:10px; color:var(--text-muted); font-family:var(--font-mono);">${cardEn}</span>
              </div>
              <div style="font-size:12.5px; font-weight:600; color:#ffffff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                ${cardTitle}
              </div>
            `;
            document.body.appendChild(ghostCard);
          }

          if (isDragging) {
            moveEvent.preventDefault();
            if (ghostCard) {
              ghostCard.style.left = `${moveEvent.clientX}px`;
              ghostCard.style.top = `${moveEvent.clientY}px`;
            }
            self.detectHoverTarget(moveEvent.clientX, moveEvent.clientY, widgetId);
          }
        };

        const onKeyDown = (keyEvent) => {
          if (keyEvent.key === 'Escape') {
            cleanUpDrag(false);
          }
        };

        const cleanUpDrag = (applyDrop = true) => {
          window.removeEventListener('mousemove', onMouseMove);
          window.removeEventListener('mouseup', onMouseUp);
          window.removeEventListener('keydown', onKeyDown);
          document.body.classList.remove('is-card-dragging-active');

          if (ghostCard && ghostCard.parentElement) {
            ghostCard.parentElement.removeChild(ghostCard);
          }

          if (isDragging) {
            pane.classList.remove('is-dragging-card');
            const targetInfo = self._dropTargetInfo;
            self.clearDropIndicators();
            self._draggedWidgetId = null;
            self._dropTargetInfo = null;

            if (applyDrop && targetInfo) {
              if (targetInfo.targetWidgetId && targetInfo.targetWidgetId !== widgetId) {
                self.handleDropOnCard(widgetId, targetInfo.targetWidgetId, targetInfo.position);
              } else if (targetInfo.targetTier) {
                self.handleDropOnTier(widgetId, targetInfo.targetTier);
              }
            }
          }
        };

        const onMouseUp = () => {
          cleanUpDrag(true);
        };

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
        window.addEventListener('keydown', onKeyDown);
      });
    });
  },

  /**
   * 懸停探測與雷射放置指示線顯示 (極限消除無效死角、支援同排雙向即時磁吸換位)
   */
  detectHoverTarget: function(clientX, clientY, currentWidgetId) {
    if (typeof document === 'undefined') return;
    const panes = document.querySelectorAll('.tiling-pane');
    let hoveredPane = null;

    panes.forEach(p => {
      const pId = p.getAttribute('data-widget-id') || (p.id ? p.id.replace('widget-', '').replace('pane-', '') : '');
      if (pId === currentWidgetId || pId === 'kpi_grid' || p.style.display === 'none') return;
      if (typeof p.getBoundingClientRect === 'function') {
        const rect = p.getBoundingClientRect();
        // 擴展 4px 偵測範圍，完美銜接 8px 垂直分割條間隙，游標經過分割條時絕不閃爍或丟失
        if (clientX >= (rect.left - 4) && clientX <= (rect.right + 4) && clientY >= rect.top && clientY <= rect.bottom) {
          hoveredPane = p;
        }
      }
    });

    if (hoveredPane) {
      const targetId = hoveredPane.getAttribute('data-widget-id') || (hoveredPane.id ? hoveredPane.id.replace('widget-', '').replace('pane-', '') : '');
      if (targetId && targetId !== currentWidgetId) {
        const rect = hoveredPane.getBoundingClientRect();
        let position = 'after';

        const tierEl = hoveredPane.parentElement;
        const tierPanes = Array.from(tierEl.children).filter(c => c.classList && c.classList.contains('tiling-pane') && c.style.display !== 'none');
        const srcIdx = tierPanes.findIndex(p => {
          const id = p.getAttribute('data-widget-id') || (p.id ? p.id.replace('widget-', '').replace('pane-', '') : '');
          return id === currentWidgetId;
        });
        const tgtIdx = tierPanes.indexOf(hoveredPane);

        if (srcIdx !== -1 && tgtIdx !== -1) {
          // 同排換位：徹底解決「改變卡片位置後，往某一方向移動無法放置/沒反應」的死角 BUG
          if (tgtIdx === srcIdx + 1) {
            // 向右移到緊鄰卡片 -> 目標直接放置於其後 (after)
            position = 'after';
          } else if (tgtIdx === srcIdx - 1) {
            // 向左移到緊鄰卡片 -> 目標直接放置於其前 (before)
            position = 'before';
          } else if (tgtIdx > srcIdx) {
            // 向右跨多張卡片：左半部為插在目標前，右半部為插在目標後
            const isLeft = (clientX - rect.left) < (rect.width / 2);
            position = isLeft ? 'before' : 'after';
          } else {
            // 向左跨多張卡片：左半部為插在目標前，右半部為插在目標後
            const isLeft = (clientX - rect.left) < (rect.width / 2);
            position = isLeft ? 'before' : 'after';
          }
        } else {
          // 跨排移動：游標前半部為插在目標前 (before)，後半部為插在目標後 (after)
          const isLeft = (clientX - rect.left) < (rect.width / 2);
          position = isLeft ? 'before' : 'after';
        }

        this.showDropIndicator(hoveredPane, position);
        this._dropTargetInfo = {
          targetWidgetId: targetId,
          position: position
        };
        return;
      }
    }

    // 探測是否落在 Upper / Lower Tier 邊緣或空白區域 (排除原所屬 tier 內的自身區域)
    const srcEl = document.getElementById(`widget-${currentWidgetId}`) || document.getElementById(`pane-${currentWidgetId}`);
    const srcTier = srcEl ? srcEl.parentElement : null;

    const upperTier = document.getElementById('tiling-upper-tier');
    const lowerTier = document.getElementById('tiling-lower-tier');
    let matchedTier = null;

    [upperTier, lowerTier].forEach(tier => {
      if (!tier || typeof tier.getBoundingClientRect !== 'function') return;
      const rect = tier.getBoundingClientRect();
      if (clientX >= rect.left && clientX <= rect.right && clientY >= rect.top && clientY <= rect.bottom) {
        if (tier === srcTier) {
          // 游標在自己原有排內但未懸停於其他卡片，不誤亮整排放置提示
          return;
        }
        matchedTier = tier;
        tier.classList.add('drop-target-tier');
        this._dropTargetInfo = {
          targetTier: (tier.id === 'tiling-upper-tier') ? 'upper' : 'lower',
          position: 'end'
        };
      } else {
        tier.classList.remove('drop-target-tier');
      }
    });

    if (!matchedTier) {
      this.clearDropIndicators();
      this._dropTargetInfo = null;
    }
  },

  showDropIndicator: function(targetPane, position) {
    this.clearDropIndicators();
    targetPane.classList.add(position === 'before' ? 'drop-target-before' : 'drop-target-after');

    let indicator = document.getElementById('catos-tile-drop-indicator');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.id = 'catos-tile-drop-indicator';
      indicator.className = 'tile-drop-indicator';
    }
    if (position === 'before') {
      targetPane.parentElement.insertBefore(indicator, targetPane);
    } else {
      if (targetPane.nextSibling) {
        targetPane.parentElement.insertBefore(indicator, targetPane.nextSibling);
      } else {
        targetPane.parentElement.appendChild(indicator);
      }
    }
  },

  clearDropIndicators: function() {
    if (typeof document === 'undefined') return;
    const indicator = document.getElementById('catos-tile-drop-indicator');
    if (indicator && indicator.parentElement) {
      indicator.parentElement.removeChild(indicator);
    }
    document.querySelectorAll('.tiling-pane').forEach(p => {
      p.classList.remove('drop-target-before', 'drop-target-after');
    });
    document.querySelectorAll('.tiling-row-tier').forEach(t => {
      t.classList.remove('drop-target-tier');
    });
  },

  handleDropOnTier: function(sourceId, targetTierName) {
    if (typeof document === 'undefined') return;
    const srcEl = document.getElementById(`widget-${sourceId}`) || document.getElementById(`pane-${sourceId}`);
    const targetTier = document.getElementById(`tiling-${targetTierName}-tier`);
    if (!srcEl || !targetTier) return;
    if (srcEl.parentElement === targetTier) return;
    this.takePreOpSnapshot();

    targetTier.appendChild(srcEl);

    const upperTier = document.getElementById('tiling-upper-tier');
    const lowerTier = document.getElementById('tiling-lower-tier');
    this.rebuildTierSplitters(upperTier);
    this.rebuildTierSplitters(lowerTier);

    const updateFlex = (tEl) => {
      if (!tEl) return;
      const panes = Array.from(tEl.children).filter(c => c.classList && c.classList.contains('tiling-pane') && c.style.display !== 'none');
      if (panes.length === 0) return;
      const pct = (100 / panes.length).toFixed(2);
      panes.forEach(p => {
        p.style.flex = `${pct} 1 0px`;
      });
    };
    updateFlex(upperTier);
    updateFlex(lowerTier);

    this.saveLayout();
    this.triggerSmoothChartResize();
    if (typeof this.initSplitters === 'function') {
      this.initSplitters();
    }
    if (typeof this.initCardDragAndDrop === 'function') {
      this.initCardDragAndDrop();
    }
    this.triggerLandAnimation(sourceId);
    const titleText = (this.widgets && this.widgets[sourceId]) ? this.widgets[sourceId].title : sourceId;
    this.showLayoutToast(`已將 [${titleText}] 移至${targetTierName === 'upper' ? '上排' : '下排'}`);
  },

  triggerLandAnimation: function(widgetId) {
    if (typeof document === 'undefined') return;
    const el = document.getElementById(`widget-${widgetId}`) || document.getElementById(`pane-${widgetId}`);
    if (!el) return;
    el.classList.add('just-landed');
    setTimeout(() => {
      el.classList.remove('just-landed');
    }, 600);
  },

  showLayoutToast: function(msg) {
    if (typeof document === 'undefined') return;
    let toast = document.getElementById('catos-workspace-toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'catos-workspace-toast';
      toast.style.cssText = `
        position: fixed;
        top: 48px;
        right: 20px;
        z-index: 100001;
        padding: 6px 14px;
        background: rgba(14, 18, 24, 0.94);
        border: 1px solid var(--gold-primary);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.8), 0 0 12px rgba(212, 175, 55, 0.2);
        border-radius: 3px;
        color: #fff;
        font-size: 11.5px;
        font-weight: 500;
        pointer-events: none;
        opacity: 0;
        transform: translateY(-8px);
        transition: opacity 0.2s cubic-bezier(0.16, 1, 0.3, 1), transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        display: flex;
        align-items: center;
        gap: 6px;
      `;
      document.body.appendChild(toast);
    }
    toast.innerHTML = `<span style="color:var(--gold-primary); font-size:10px;">◆</span><span>${msg}</span>`;
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
    if (this._toastTimer) clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      if (toast) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-8px)';
      }
    }, 1800);
  },

  /**
   * 在同排相鄰面板之間精確動態重建 8px 實體垂直分割條
   */
  rebuildTierSplitters: function(tierEl) {
    if (!tierEl || typeof document === 'undefined' || typeof tierEl.querySelectorAll !== 'function') return;
    const oldSplitters = Array.from(tierEl.querySelectorAll('.workspace-splitter.vertical'));
    oldSplitters.forEach(sp => sp.remove());

    const panes = Array.from(tierEl.children).filter(c => c.classList && c.classList.contains('tiling-pane') && c.style.display !== 'none');
    for (let i = 0; i < panes.length - 1; i++) {
      const leftPane = panes[i];
      const rightPane = panes[i + 1];
      const splitter = document.createElement('div');
      splitter.className = 'workspace-splitter vertical';
      splitter.classList.add('workspace-splitter');
      splitter.classList.add('vertical');
      splitter.setAttribute('data-left', leftPane.id);
      splitter.setAttribute('data-right', rightPane.id);
      splitter.setAttribute('title', '拖曳自訂左右寬度 (雙擊恢復平衡比例)');
      tierEl.insertBefore(splitter, rightPane);
    }
    this.initSplitters();
  },

  /**
   * ⚡ 智慧自動補齊／填滿版面 (Auto-Pack / Fill)
   * 徹底解決舊網格留下空白孤島的 BUG：
   * 遍歷所有可見面板，依完美對稱與黃金比例 100% 填滿視窗，天生零空洞！
   */
  autoPackGrid: function(isInternal = false) {
    if (!isInternal) this.takePreOpSnapshot();
    if (typeof document === 'undefined') return;
    const upperTier = document.getElementById('tiling-upper-tier');
    const lowerTier = document.getElementById('tiling-lower-tier');
    const visiblePanes = tier => tier ? Array.from(tier.children).filter(
      pane => pane.classList.contains('tiling-pane') && pane.style.display !== 'none'
    ) : [];
    const upperPanes = visiblePanes(upperTier);
    const lowerPanes = visiblePanes(lowerTier);
    const packTier = (tier, panes, weights) => {
      if (!tier) return;
      tier.style.display = panes.length ? 'flex' : 'none';
      panes.forEach((pane, index) => {
        pane.style.flex = `${weights ? weights[index] : 1} 1 0px`;
      });
      this.rebuildTierSplitters(tier);
    };
    packTier(upperTier, upperPanes, upperPanes.length === 2 ? [66, 34] : null);
    packTier(lowerTier, lowerPanes);
    if (upperTier && lowerTier) {
      upperTier.style.height = lowerPanes.length ? '56%' : '100%';
      lowerTier.style.height = upperPanes.length ? '44%' : '100%';
    }
    const hSplitter = document.getElementById('splitter-h-main');
    if (hSplitter) hSplitter.style.display = upperPanes.length && lowerPanes.length ? 'flex' : 'none';

    this.saveLayout();
    this.triggerSmoothChartResize();

    // 視覺反饋
    const btn = document.getElementById('btn-workspace-autopack');
    if (btn) {
      btn.style.color = 'var(--gold-primary)';
      btn.style.borderColor = 'var(--gold-primary)';
      btn.style.boxShadow = '0 0 12px rgba(230, 184, 64, 0.4)';
      setTimeout(() => {
        btn.style.color = '';
        btn.style.borderColor = '';
        btn.style.boxShadow = '';
      }, 500);
    }
  },

  /**
   * 一鍵最大化 / 還原單一面板 (Maximize / Fullscreen)
   */
  toggleMaximize: function(widgetId) {
    const pane = document.getElementById(`pane-${widgetId}`) || document.getElementById(`widget-${widgetId}`);
    const container = document.getElementById('dashboard-tiling-workspace') || document.getElementById('dashboard-grid-stack');
    if (!pane) return;

    const ICON_MAX = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>`;
    const ICON_RESTORE = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14h6v6M20 10h-6V4M14 10l7-7M10 14l-7 7"/></svg>`;

    if (this.maximizedPaneId === widgetId) {
      // 還原
      pane.classList.remove('is-maximized');
      if (container) {
        container.classList.remove('has-maximized-pane', 'has-max-kpi', 'has-max-pane');
      }
      this.maximizedPaneId = null;
    } else {
      // 清除其他最大化
      if (this.maximizedPaneId) {
        const old = document.getElementById(`pane-${this.maximizedPaneId}`) || document.getElementById(`widget-${this.maximizedPaneId}`);
        if (old) old.classList.remove('is-maximized');
      }
      pane.classList.add('is-maximized');
      if (container) {
        container.classList.add('has-maximized-pane');
        if (widgetId === 'kpi_grid') {
          container.classList.add('has-max-kpi');
          container.classList.remove('has-max-pane');
        } else {
          container.classList.add('has-max-pane');
          container.classList.remove('has-max-kpi');
        }
      }
      this.maximizedPaneId = widgetId;
    }

    // 更新所有最大化按鈕的圖示與 Tooltip
    if (typeof document !== 'undefined') {
      const allMaxBtns = document.querySelectorAll('.btn-pane-maximize');
      allMaxBtns.forEach(btn => {
        const wId = btn.getAttribute('data-widget');
        const isCurrentMax = !!(this.maximizedPaneId && wId === this.maximizedPaneId);
        btn.classList.toggle('is-active', isCurrentMax);
        btn.innerHTML = isCurrentMax ? ICON_RESTORE : ICON_MAX;
        btn.setAttribute('title', isCurrentMax ? '還原面板' : '最大化面板');
        btn.setAttribute('aria-label', `${isCurrentMax ? '還原' : '放大'}${this.widgets[wId]?.title || '面板'}`);
      });
    }

    this.triggerSmoothChartResize();
  },

  /**
   * 進入 / 退出 編輯模式 (顯示分割調整手把與隱藏/新增按鈕)
   */
  setEditing: function(isEditing) {
    this.isEditing = !!isEditing;
    if (this.grid) {
      if (typeof this.grid.enableMove === 'function') this.grid.enableMove(this.isEditing);
      if (typeof this.grid.enableResize === 'function') this.grid.enableResize(this.isEditing);
    }

    const toolbar = document.getElementById('workspace-toolbar-bar');
    const editBtn = document.getElementById('btn-workspace-edit-toggle');
    const container = document.getElementById('dashboard-tiling-workspace') || document.getElementById('dashboard-grid-stack');

    if (toolbar) toolbar.classList.toggle('is-editing', this.isEditing);
    if (container) container.classList.toggle('is-editing', this.isEditing);

    if (editBtn) {
      editBtn.classList.toggle('is-active', this.isEditing);
      editBtn.textContent = this.isEditing ? '✓ 完成編輯' : '⚙ 調整版面';
      editBtn.setAttribute('aria-pressed', String(this.isEditing));
    }

    const editOnlyActions = document.querySelectorAll('.workspace-edit-only-action');
    editOnlyActions.forEach(el => {
      el.style.display = this.isEditing ? 'inline-flex' : 'none';
    });

    if (this.isEditing) {
      this._editSnapshot = this.captureCurrentState();
      this._lastSnapshot = this._editSnapshot;
    } else {
      this._editSnapshot = null;
      this.saveLayout();
    }
  },

  toggleEditing: function() {
    this.setEditing(!this.isEditing);
  },

  /**
   * 套用官方預設集 (Executive / Research / Sentinel)
   */
  applyPreset: function(presetId) {
    if (!this.presets[presetId]) return;
    this.currentPresetId = presetId;
    this.selectUndoHistory();
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(this.getPresetStorageKey(), presetId);
      try {
        this.hiddenWidgets = JSON.parse(localStorage.getItem(this.getHiddenStorageKey(presetId)) || '[]');
      } catch (e) {
        this.hiddenWidgets = [];
      }
    }

    const preset = this.presets[presetId];
    const isDesktop = (typeof window !== 'undefined') ? (window.innerWidth >= 1440) : true;
    const items = isDesktop ? preset.desktop : preset.compact;
    this._loadedMockItems = items;
    if (this.grid && typeof this.grid.load === 'function') {
      this.grid.load(items);
    }

    // 套用對應預設集的連續比例
    this.loadLayout();
    this.updateToolbarPresetPills();
    this.triggerSmoothChartResize();
  },

  /**
   * 載入佈局比例
   */
  loadLayout: function() {
    const preset = this.presets[this.currentPresetId] || this.presets.executive;
    const isDesktop = (typeof window !== 'undefined') ? (window.innerWidth >= 1440) : true;
    const defaultItems = isDesktop ? preset.desktop : preset.compact;
    this._loadedMockItems = defaultItems;

    let splits = preset.splits;
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem(this.getStorageKey());
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) {
            this._loadedMockItems = parsed;
          } else if (parsed && typeof parsed === 'object') {
            splits = parsed;
          }
        } catch (e) {}
      }
    }

    if (this.grid && typeof this.grid.load === 'function') {
      this.grid.load(this._loadedMockItems);
    }

    if (typeof document === 'undefined') return;

    // 1. 處理隱藏元件
    ['kpi_grid', 'equity_chart', 'incident_timeline', 'active_bots', 'research_tasks', 'yaozi_brief'].forEach(id => {
      const el = document.getElementById(`pane-${id}`) || document.getElementById(`widget-${id}`);
      if (el) {
        el.style.display = this.hiddenWidgets.includes(id) ? 'none' : 'flex';
      }
    });

    // 2. 載入比例 (若有 Tiling DOM)
    const kpiEl = document.getElementById('widget-kpi_grid');
    if (kpiEl) {
      if (splits && splits.kpiHeightPx) {
        kpiEl.style.height = `${splits.kpiHeightPx}px`;
      } else {
        kpiEl.style.height = '';
      }
    }

    const upperTier = document.getElementById('tiling-upper-tier');
    const lowerTier = document.getElementById('tiling-lower-tier');

    // 2. 還原卡片層級位置與比例
    if (splits && (splits.upperWidgets || splits.lowerWidgets) && upperTier && lowerTier) {
      if (Array.isArray(splits.upperWidgets)) {
        splits.upperWidgets.forEach(w => {
          const el = document.getElementById(`widget-${w.id}`) || document.getElementById(`pane-${w.id}`);
          if (el) {
            if (typeof upperTier.appendChild === 'function') upperTier.appendChild(el);
            el.style.flex = `${w.flex} 1 0px`;
          }
        });
      }
      if (Array.isArray(splits.lowerWidgets)) {
        splits.lowerWidgets.forEach(w => {
          const el = document.getElementById(`widget-${w.id}`) || document.getElementById(`pane-${w.id}`);
          if (el) {
            if (typeof lowerTier.appendChild === 'function') lowerTier.appendChild(el);
            el.style.flex = `${w.flex} 1 0px`;
          }
        });
      }
      this.rebuildTierSplitters(upperTier);
      this.rebuildTierSplitters(lowerTier);
    } else if (upperTier && lowerTier) {
      // 官方出廠預設集配置
      const defaultLayouts = {
        executive: {
          upper: ['equity_chart', 'incident_timeline'],
          lower: ['active_bots', 'research_tasks', 'yaozi_brief'],
          upperFlex: [66, 34],
          lowerFlex: [33.33, 33.33, 33.34]
        },
        research: {
          upper: ['equity_chart', 'research_tasks'],
          lower: ['active_bots', 'yaozi_brief', 'incident_timeline'],
          upperFlex: [66, 34],
          lowerFlex: [33.33, 33.33, 33.34]
        },
        sentinel: {
          upper: ['incident_timeline', 'active_bots'],
          lower: ['equity_chart', 'research_tasks', 'yaozi_brief'],
          upperFlex: [50, 50],
          lowerFlex: [33.33, 33.33, 33.34]
        }
      };
      const def = defaultLayouts[this.currentPresetId] || defaultLayouts.executive;
      def.upper.forEach((id, idx) => {
        const el = document.getElementById(`widget-${id}`) || document.getElementById(`pane-${id}`);
        if (el) {
          if (typeof upperTier.appendChild === 'function') upperTier.appendChild(el);
          el.style.flex = `${def.upperFlex[idx] || 50} 1 0px`;
        }
      });
      def.lower.forEach((id, idx) => {
        const el = document.getElementById(`widget-${id}`) || document.getElementById(`pane-${id}`);
        if (el) {
          if (typeof lowerTier.appendChild === 'function') lowerTier.appendChild(el);
          el.style.flex = `${def.lowerFlex[idx] || 33.33} 1 0px`;
        }
      });
      this.rebuildTierSplitters(upperTier);
      this.rebuildTierSplitters(lowerTier);
    }

    if (upperTier && lowerTier && splits && splits.upperHeightPct) {
      upperTier.style.height = `${splits.upperHeightPct}%`;
      lowerTier.style.height = `${100 - splits.upperHeightPct}%`;
    }

    this.updateToolbarPresetPills();
    this.triggerSmoothChartResize();
    if (typeof this.initCardDragAndDrop === 'function') {
      this.initCardDragAndDrop();
    }
  },

  /**
   * 儲存當前分割比例至 localStorage
   */
  saveLayout: function() {
    if (typeof localStorage === 'undefined' || typeof document === 'undefined') return;

    const hasTilingDom = typeof document.querySelector === 'function' && document.querySelector('.tiling-workspace-container');
    if (!hasTilingDom && this._loadedMockItems && Array.isArray(this._loadedMockItems)) {
      localStorage.setItem(this.getStorageKey(), JSON.stringify(this._loadedMockItems));
      localStorage.setItem(this.getHiddenStorageKey(), JSON.stringify(this.hiddenWidgets));
      return;
    }

    const upperTier = document.getElementById('tiling-upper-tier');
    const upperH = upperTier ? parseFloat(upperTier.style.height) || 56 : 56;

    const kpiEl = document.getElementById('widget-kpi_grid');
    const kpiH = (kpiEl && kpiEl.style.height) ? parseFloat(kpiEl.style.height) : null;

    const tierLists = this.getCurrentTierLists(true);

    const currentSplits = {
      kpiHeightPx: kpiH,
      upperHeightPct: upperH,
      upperWidgets: tierLists.upperWidgets,
      lowerWidgets: tierLists.lowerWidgets,
      upperTier: {},
      lowerTier: {}
    };
    tierLists.upperWidgets.forEach(w => {
      currentSplits.upperTier[w.id] = w.flex;
    });
    tierLists.lowerWidgets.forEach(w => {
      currentSplits.lowerTier[w.id] = w.flex;
    });

    localStorage.setItem(this.getStorageKey(), JSON.stringify(currentSplits));
    localStorage.setItem(this.getHiddenStorageKey(), JSON.stringify(this.hiddenWidgets));
  },

  /**
   * 完整復原版面（還原操作前的隱藏清單、各排面板尺寸與排序）
   */
  revertLayout: function() {
    this.selectUndoHistory();
    this._isReverting = true;
    let snapshot = null;
    if (this.isEditing && this._editSnapshot) {
      snapshot = this._editSnapshot;
    } else if (this._historyStack && this._historyStack.length > 0) {
      snapshot = this._historyStack.pop();
    }

    if (!snapshot) {
      this._isReverting = false;
      if (typeof this.showLayoutToast === 'function') {
        this.showLayoutToast('目前為初始狀態，無可復原的操作');
      }
      return;
    }

    // 1. 還原隱藏清單
    this.hiddenWidgets = [...(snapshot.hidden || [])];
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(this.getHiddenStorageKey(snapshot.presetId || this.currentPresetId), JSON.stringify(this.hiddenWidgets));
    }

    // 2. 還原測試用 GridStack Mock 項目
    if (snapshot.gridItems) {
      this._loadedMockItems = JSON.parse(JSON.stringify(snapshot.gridItems));
      if (this.grid && typeof this.grid.load === 'function') {
        this.grid.load(this._loadedMockItems);
      }
    }

    // 3. 還原平鋪 DOM 結構（排序與尺寸）
    const upperTier = (typeof document !== 'undefined') ? document.getElementById('tiling-upper-tier') : null;
    const lowerTier = (typeof document !== 'undefined') ? document.getElementById('tiling-lower-tier') : null;
    const kpiEl = (typeof document !== 'undefined') ? document.getElementById('widget-kpi_grid') : null;

    if (kpiEl) {
      kpiEl.style.height = snapshot.kpiH || '';
    }

    if (upperTier && lowerTier) {
      if (snapshot.upperH) upperTier.style.height = snapshot.upperH;
      if (snapshot.lowerH) lowerTier.style.height = snapshot.lowerH;

      // 還原上排卡片排序與 flex 尺寸
      if (Array.isArray(snapshot.upperWidgets) && snapshot.upperWidgets.length > 0) {
        snapshot.upperWidgets.forEach(w => {
          const el = document.getElementById(`widget-${w.id}`) || document.getElementById(`pane-${w.id}`);
          if (el && typeof upperTier.appendChild === 'function') {
            upperTier.appendChild(el);
            if (w.flex) el.style.flex = `${w.flex} 1 0px`;
          }
        });
      }

      // 還原下排卡片排序與 flex 尺寸
      if (Array.isArray(snapshot.lowerWidgets) && snapshot.lowerWidgets.length > 0) {
        snapshot.lowerWidgets.forEach(w => {
          const el = document.getElementById(`widget-${w.id}`) || document.getElementById(`pane-${w.id}`);
          if (el && typeof lowerTier.appendChild === 'function') {
            lowerTier.appendChild(el);
            if (w.flex) el.style.flex = `${w.flex} 1 0px`;
          }
        });
      }

      this.rebuildTierSplitters(upperTier);
      this.rebuildTierSplitters(lowerTier);
    }

    // 4. 重構並持久化 Splits 至 localStorage
    const tierLists = this.getCurrentTierLists(false);
    const restoredSplits = snapshot.splits ? snapshot.splits : {
      kpiHeightPx: snapshot.kpiH ? parseFloat(snapshot.kpiH) : null,
      upperHeightPct: snapshot.upperH ? parseFloat(snapshot.upperH) : 56,
      upperWidgets: tierLists.upperWidgets,
      lowerWidgets: tierLists.lowerWidgets,
      upperTier: {},
      lowerTier: {}
    };
    if (!snapshot.splits) {
      tierLists.upperWidgets.forEach(w => { restoredSplits.upperTier[w.id] = w.flex; });
      tierLists.lowerWidgets.forEach(w => { restoredSplits.lowerTier[w.id] = w.flex; });
    }

    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(this.getStorageKey(snapshot.presetId || this.currentPresetId), JSON.stringify(restoredSplits));
    }

    // 5. 確保顯隱與圖表連動更新
    this.loadLayout();
    this.triggerSmoothChartResize();
    this._isReverting = false;
    this._lastSnapshot = null;

    if (typeof this.showLayoutToast === 'function') {
      this.showLayoutToast('已完整復原操作前的尺寸與排序');
    }
  },

  resetLayout: function() {
    this.takePreOpSnapshot();

    const targetPreset = this.currentPresetId || 'executive';
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(this.getStorageKey(targetPreset));
      this.hiddenWidgets = [];
      localStorage.setItem(this.getHiddenStorageKey(targetPreset), '[]');
    }

    const kpiEl = document.getElementById('widget-kpi_grid');
    if (kpiEl) kpiEl.style.height = '';

    const preset = this.presets[targetPreset] || this.presets.executive;
    const defaultUpperH = (preset.splits && preset.splits.upperHeightPct) ? preset.splits.upperHeightPct : 56;

    const upperTier = document.getElementById('tiling-upper-tier');
    const lowerTier = document.getElementById('tiling-lower-tier');
    if (upperTier && lowerTier) {
      upperTier.style.height = `${defaultUpperH}%`;
      lowerTier.style.height = `${100 - defaultUpperH}%`;
    }

    this.loadLayout();
    this.triggerSmoothChartResize();

    if (typeof this.showLayoutToast === 'function') {
      this.showLayoutToast(`已重設為 [${preset.name || targetPreset}] 原廠出廠配置`);
    }
  },

  hideWidget: function(widgetId) {
    this.takePreOpSnapshot();
    if (!this.hiddenWidgets.includes(widgetId)) {
      this.hiddenWidgets.push(widgetId);
    }
    const el = document.getElementById(`pane-${widgetId}`) || document.getElementById(`widget-${widgetId}`);
    if (el) el.style.display = 'none';

    this.autoPackGrid(true);
    this.saveLayout();
  },

  restoreWidget: function(widgetId) {
    this.takePreOpSnapshot();
    this.hiddenWidgets = this.hiddenWidgets.filter(id => id !== widgetId);
    const el = document.getElementById(`pane-${widgetId}`) || document.getElementById(`widget-${widgetId}`);
    if (el) el.style.display = 'flex';

    this.autoPackGrid(true);
    this.saveLayout();
    this.renderWidgetLibraryList();
  },

  openWidgetLibrary: function() {
    const backdrop = document.getElementById('widget-library-backdrop');
    const panel = document.getElementById('widget-library-panel');
    if (backdrop && panel) {
      backdrop.classList.add('is-open');
      panel.classList.add('is-open');
      this.renderWidgetLibraryList();
    }
  },

  closeWidgetLibrary: function() {
    const backdrop = document.getElementById('widget-library-backdrop');
    const panel = document.getElementById('widget-library-panel');
    if (backdrop && panel) {
      backdrop.classList.remove('is-open');
      panel.classList.remove('is-open');
    }
  },

  renderWidgetLibraryList: function() {
    const container = document.getElementById('widget-library-body');
    if (!container) return;

    const allWidgets = Object.values(this.widgets);
    container.innerHTML = allWidgets.map(w => {
      const isHidden = this.hiddenWidgets.includes(w.id);
      return `
        <div class="widget-lib-card ${!isHidden ? 'is-active' : ''}">
          <div class="widget-lib-card-top">
            <div>
              <div class="widget-lib-title">${w.title}</div>
              <div style="font-size:11px; font-family:var(--font-mono); color:var(--text-muted); font-weight:500;">${w.en}</div>
            </div>
            <span class="badge ${!isHidden ? 'badge-green' : 'badge-ghost'}" style="font-size:11px; padding:1px 5px;">
              ${!isHidden ? '畫布中' : '已隱藏'}
            </span>
          </div>
          <div class="widget-lib-desc">${w.desc}</div>
          <div class="widget-lib-footer">
            ${isHidden ? `
              <button class="btn btn-sm btn-ghost" 
                      data-restore="${w.id}"
                      style="font-size:11.5px; color:var(--gold-primary); border-color:var(--border-gold-subtle); padding:2px 8px;">
                ＋ 加回畫布
              </button>
            ` : `
              <button class="btn btn-sm btn-ghost" 
                      data-hide="${w.id}"
                      style="font-size:11px; color:var(--text-muted);">
                隱藏元件
              </button>
            `}
          </div>
        </div>
      `;
    }).join('');
  },

  updateToolbarPresetPills: function() {
    if (typeof document === 'undefined') return;
    const pills = document.querySelectorAll('.workspace-preset-pill');
    pills.forEach(p => {
      const pId = p.getAttribute('data-preset');
      p.classList.toggle('active', pId === this.currentPresetId);
    });
  },

  setWidgetWidth: function(widgetId, targetCols) {
    const el = document.getElementById(`pane-${widgetId}`) || document.getElementById(`widget-${widgetId}`);
    if (!el) return;
    const pct = Math.round((targetCols / 12) * 100);
    el.style.flex = `0 0 ${pct}%`;
    this.saveLayout();
    this.triggerSmoothChartResize();
  },

  triggerSmoothChartResize: function() {
    if (this._resizeDebounceTimer) clearTimeout(this._resizeDebounceTimer);
    this._resizeDebounceTimer = setTimeout(() => {
      const raf = (typeof window !== 'undefined' && window.requestAnimationFrame) 
        ? window.requestAnimationFrame 
        : ((cb) => setTimeout(cb, 16));
      raf(() => {
        if (typeof window !== 'undefined') {
          if (window.dispatchEvent) {
            window.dispatchEvent(new Event('resize'));
          }
          if (window.ChartEngine && document.getElementById('dashboard-equity-chart')) {
            const timeBtn = document.querySelector('.time-range-selector .time-btn.active');
            const range = timeBtn ? timeBtn.innerText.trim() : '30D';
            const sc = (window.appState && window.appState.get) ? window.appState.get('scenario') : 'active';
            window.ChartEngine.renderDashboardEquity('dashboard-equity-chart', range, sc);
          }
        }
      });
    }, 40);
  }
};
