# -*- coding: utf-8 -*-
import pathlib

FRONTEND_ROOT = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final')

def update_workspace():
    p = FRONTEND_ROOT / 'js' / 'workspace.js'
    text = p.read_text(encoding='utf-8')

    # 1. 註冊 allocation 與 risk_latch 到 widgets
    widgets_needle = """    yaozi_brief: {
      id: 'yaozi_brief',
      title: 'Yaozi 市場情報快訊',
      en: 'YAOZI INTEL',
      desc: '即時鏈上異動、社群情緒與 Alpha 訊號速報。',
      minW: 3,
      minH: 3,
      defaultW: 4,
      defaultH: 4
    }"""

    widgets_replacement = """    yaozi_brief: {
      id: 'yaozi_brief',
      title: 'Yaozi 市場情報快訊',
      en: 'YAOZI INTEL',
      desc: '即時鏈上異動、社群情緒與 Alpha 訊號速報。',
      minW: 3,
      minH: 3,
      defaultW: 4,
      defaultH: 4
    },
    allocation: {
      id: 'allocation',
      title: '帳戶保證金與曝險配置',
      en: 'ALLOCATION // 3.0x',
      desc: '帳戶持倉保證金、在途凍結與風控預算佔比圓環圖。',
      minW: 3,
      minH: 3,
      defaultW: 4,
      defaultH: 5
    },
    risk_latch: {
      id: 'risk_latch',
      title: '日損鎖存安全緩衝儀表',
      en: 'RISK LATCH GAUGE',
      desc: '日損門檻、Soft/Hard 熔斷刻度條與即時淨值安全緩衝。',
      minW: 4,
      minH: 3,
      defaultW: 4,
      defaultH: 4
    }"""

    if "'allocation':" not in text and "allocation: {" not in text:
        text = text.replace(widgets_needle, widgets_replacement, 1)

    # 2. 更新 presets.executive
    preset_needle = """      splits: {
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
      ]"""

    preset_replacement = """      splits: {
        upperHeightPct: 54,
        upperTier: { equity_chart: 48, allocation: 28, incident_timeline: 24 },
        lowerTier: { risk_latch: 34, active_bots: 22, research_tasks: 22, yaozi_brief: 22 }
      },
      desktop: [
        { id: 'kpi_grid', x: 0, y: 0, w: 12, h: 2 },
        { id: 'equity_chart', x: 0, y: 2, w: 6, h: 5 },
        { id: 'allocation', x: 6, y: 2, w: 3, h: 5 },
        { id: 'incident_timeline', x: 9, y: 2, w: 3, h: 5 },
        { id: 'risk_latch', x: 0, y: 7, w: 4, h: 4 },
        { id: 'active_bots', x: 4, y: 7, w: 3, h: 4 },
        { id: 'research_tasks', x: 7, y: 7, w: 3, h: 4 },
        { id: 'yaozi_brief', x: 10, y: 7, w: 2, h: 4 }
      ],
      compact: [
        { id: 'kpi_grid', x: 0, y: 0, w: 12, h: 2 },
        { id: 'equity_chart', x: 0, y: 2, w: 12, h: 5 },
        { id: 'allocation', x: 0, y: 7, w: 12, h: 5 },
        { id: 'incident_timeline', x: 0, y: 12, w: 12, h: 5 },
        { id: 'risk_latch', x: 0, y: 17, w: 12, h: 4 },
        { id: 'active_bots', x: 0, y: 21, w: 6, h: 4 },
        { id: 'research_tasks', x: 6, y: 21, w: 6, h: 4 },
        { id: 'yaozi_brief', x: 0, y: 25, w: 12, h: 4 }
      ]"""

    if "upperTier: { equity_chart: 48, allocation: 28" not in text:
        text = text.replace(preset_needle, preset_replacement, 1)

    # 3. 更新 loadLayout 隱藏元件處理
    hide_needle = "['kpi_grid', 'equity_chart', 'incident_timeline', 'active_bots', 'research_tasks', 'yaozi_brief'].forEach(id => {"
    hide_replacement = "Object.keys(this.widgets).forEach(id => {"
    text = text.replace(hide_needle, hide_replacement, 1)

    # 4. 更新 loadLayout 中的 defaultLayouts
    default_layouts_needle = """      const defaultLayouts = {
        executive: {
          upper: ['equity_chart', 'incident_timeline'],
          lower: ['active_bots', 'research_tasks', 'yaozi_brief'],
          upperFlex: [66, 34],
          lowerFlex: [33.33, 33.33, 33.34]
        },"""

    default_layouts_replacement = """      const hasAlloc = (typeof document !== 'undefined' && document.getElementById('widget-allocation'));
      const defaultLayouts = {
        executive: hasAlloc ? {
          upper: ['equity_chart', 'allocation', 'incident_timeline'],
          lower: ['risk_latch', 'active_bots', 'research_tasks', 'yaozi_brief'],
          upperFlex: [48, 28, 24],
          lowerFlex: [34, 22, 22, 22]
        } : {
          upper: ['equity_chart', 'incident_timeline'],
          lower: ['active_bots', 'research_tasks', 'yaozi_brief'],
          upperFlex: [66, 34],
          lowerFlex: [33.33, 33.33, 33.34]
        },"""

    text = text.replace(default_layouts_needle, default_layouts_replacement, 1)

    # 5. 優化 autoPackGrid 處理多面板
    autopack_needle = """    // 1. 處理上排可見面板
    const upperIds = ['equity_chart', 'incident_timeline'];
    const upperPanes = upperIds
      .map(id => ({ id, el: getPane(id) }))
      .filter(p => p.el && p.el.style.display !== 'none');

    const vSplitterUpper = document.getElementById('splitter-v-upper');

    if (upperPanes.length === 0) {
      const upperTier = document.getElementById('tiling-upper-tier');
      const lowerTier = document.getElementById('tiling-lower-tier');
      const hSplitter = document.getElementById('splitter-h-main');
      if (upperTier && lowerTier) {
        upperTier.style.height = '0%';
        upperTier.style.display = 'none';
        lowerTier.style.height = '100%';
      }
      if (hSplitter) hSplitter.style.display = 'none';
    } else if (upperPanes.length === 1) {
      upperPanes[0].el.style.flex = '1 0 100%';
      if (vSplitterUpper) vSplitterUpper.style.display = 'none';
    } else if (upperPanes.length === 2) {
      upperPanes[0].el.style.flex = '0 0 66%';
      upperPanes[1].el.style.flex = '0 0 34%';
      if (vSplitterUpper) vSplitterUpper.style.display = 'flex';
    }

    // 2. 處理下排可見面板
    const lowerIds = ['active_bots', 'research_tasks', 'yaozi_brief'];
    const lowerPanes = lowerIds
      .map(id => ({ id, el: getPane(id) }))
      .filter(p => p.el && p.el.style.display !== 'none');"""

    autopack_replacement = """    const upperTier = document.getElementById('tiling-upper-tier');
    const lowerTier = document.getElementById('tiling-lower-tier');
    const hSplitter = document.getElementById('splitter-h-main');

    // 1. 動態處理上排可見面板
    const upperPanes = upperTier ? Array.from(upperTier.children).filter(c => c.classList && c.classList.contains('tiling-pane') && c.style.display !== 'none') : [];

    if (upperPanes.length === 0) {
      if (upperTier && lowerTier) {
        upperTier.style.height = '0%';
        upperTier.style.display = 'none';
        lowerTier.style.height = '100%';
      }
      if (hSplitter) hSplitter.style.display = 'none';
    } else if (upperPanes.length === 1) {
      upperPanes[0].style.flex = '1 0 100%';
    } else if (upperPanes.length === 2) {
      upperPanes[0].style.flex = '0 0 66%';
      upperPanes[1].style.flex = '0 0 34%';
    } else if (upperPanes.length === 3) {
      upperPanes[0].style.flex = '0 0 48%';
      upperPanes[1].style.flex = '0 0 28%';
      upperPanes[2].style.flex = '0 0 24%';
    } else {
      const pct = (100 / upperPanes.length).toFixed(2);
      upperPanes.forEach(p => { p.style.flex = `0 0 ${pct}%`; });
    }
    if (upperTier) this.rebuildTierSplitters(upperTier);

    // 2. 動態處理下排可見面板
    const lowerPanes = lowerTier ? Array.from(lowerTier.children).filter(c => c.classList && c.classList.contains('tiling-pane') && c.style.display !== 'none') : [];"""

    text = text.replace(autopack_needle, autopack_replacement, 1)

    # 下排 autoPackGrid 收尾
    autopack_lower_needle = """    if (lowerPanes.length === 0) {
      const upperTier = document.getElementById('tiling-upper-tier');
      const lowerTier = document.getElementById('tiling-lower-tier');
      const hSplitter = document.getElementById('splitter-h-main');
      if (upperTier && lowerTier) {
        upperTier.style.height = '100%';
        lowerTier.style.height = '0%';
        lowerTier.style.display = 'none';
      }
      if (hSplitter) hSplitter.style.display = 'none';
    } else if (lowerPanes.length === 1) {
      lowerPanes[0].el.style.flex = '1 0 100%';
      if (splitLower1) splitLower1.style.display = 'none';
      if (splitLower2) splitLower2.style.display = 'none';
    } else if (lowerPanes.length === 2) {
      lowerPanes[0].el.style.flex = '0 0 50%';
      lowerPanes[1].el.style.flex = '0 0 50%';
      if (splitLower1) splitLower1.style.display = 'flex';
      if (splitLower2) splitLower2.style.display = 'none';
    } else if (lowerPanes.length === 3) {
      lowerPanes[0].el.style.flex = '0 0 33.33%';
      lowerPanes[1].el.style.flex = '0 0 33.33%';
      lowerPanes[2].el.style.flex = '0 0 33.34%';
      if (splitLower1) splitLower1.style.display = 'flex';
      if (splitLower2) splitLower2.style.display = 'flex';
    }"""

    autopack_lower_replacement = """    if (lowerPanes.length === 0) {
      if (upperTier && lowerTier) {
        upperTier.style.height = '100%';
        lowerTier.style.height = '0%';
        lowerTier.style.display = 'none';
      }
      if (hSplitter) hSplitter.style.display = 'none';
    } else if (lowerPanes.length === 1) {
      lowerPanes[0].style.flex = '1 0 100%';
    } else if (lowerPanes.length === 2) {
      lowerPanes[0].style.flex = '0 0 50%';
      lowerPanes[1].style.flex = '0 0 50%';
    } else if (lowerPanes.length === 3) {
      lowerPanes[0].style.flex = '0 0 33.33%';
      lowerPanes[1].style.flex = '0 0 33.33%';
      lowerPanes[2].style.flex = '0 0 33.34%';
    } else if (lowerPanes.length === 4) {
      lowerPanes[0].style.flex = '0 0 34%';
      lowerPanes[1].style.flex = '0 0 22%';
      lowerPanes[2].style.flex = '0 0 22%';
      lowerPanes[3].style.flex = '0 0 22%';
    } else {
      const pct = (100 / lowerPanes.length).toFixed(2);
      lowerPanes.forEach(p => { p.style.flex = `0 0 ${pct}%`; });
    }
    if (lowerTier) this.rebuildTierSplitters(lowerTier);"""

    text = text.replace(autopack_lower_needle, autopack_lower_replacement, 1)

    p.write_text(text, encoding='utf-8')
    print("workspace.js updated successfully.")

if __name__ == '__main__':
    update_workspace()
