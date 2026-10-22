# -*- coding: utf-8 -*-
import pathlib

FRONTEND_ROOT = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final')

def fix_autopack():
    p = FRONTEND_ROOT / 'js' / 'workspace.js'
    text = p.read_text(encoding='utf-8')

    old_autopack = """    const upperTier = document.getElementById('tiling-upper-tier');
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

    new_autopack = """    const upperTier = document.getElementById('tiling-upper-tier');
    const lowerTier = document.getElementById('tiling-lower-tier');
    const hSplitter = document.getElementById('splitter-h-main');

    // 1. 動態處理上排可見面板 (兼顧真實 DOM 與 Mock DOM)
    const upperIds = ['equity_chart', 'allocation', 'incident_timeline'];
    let upperPanes = [];
    if (upperTier && upperTier.children && (Array.isArray(upperTier.children) || typeof upperTier.children[Symbol.iterator] === 'function')) {
      upperPanes = Array.from(upperTier.children).filter(c => c.classList && c.classList.contains('tiling-pane') && c.style && c.style.display !== 'none');
    } else {
      upperPanes = upperIds.map(id => getPane(id)).filter(el => el && el.style && el.style.display !== 'none');
    }

    if (upperPanes.length === 0) {
      if (upperTier && lowerTier) {
        upperTier.style.height = '0%';
        upperTier.style.display = 'none';
        lowerTier.style.height = '100%';
      }
      if (hSplitter) hSplitter.style.display = 'none';
    } else if (upperPanes.length === 1) {
      if (upperPanes[0].style) upperPanes[0].style.flex = '1 0 100%';
    } else if (upperPanes.length === 2) {
      if (upperPanes[0].style) upperPanes[0].style.flex = '0 0 66%';
      if (upperPanes[1].style) upperPanes[1].style.flex = '0 0 34%';
    } else if (upperPanes.length === 3) {
      if (upperPanes[0].style) upperPanes[0].style.flex = '0 0 48%';
      if (upperPanes[1].style) upperPanes[1].style.flex = '0 0 28%';
      if (upperPanes[2].style) upperPanes[2].style.flex = '0 0 24%';
    } else {
      const pct = (100 / upperPanes.length).toFixed(2);
      upperPanes.forEach(p => { if (p.style) p.style.flex = `0 0 ${pct}%`; });
    }
    if (upperTier && typeof upperTier.querySelectorAll === 'function') this.rebuildTierSplitters(upperTier);

    // 2. 動態處理下排可見面板 (兼顧真實 DOM 與 Mock DOM)
    const lowerIds = ['risk_latch', 'active_bots', 'research_tasks', 'yaozi_brief'];
    let lowerPanes = [];
    if (lowerTier && lowerTier.children && (Array.isArray(lowerTier.children) || typeof lowerTier.children[Symbol.iterator] === 'function')) {
      lowerPanes = Array.from(lowerTier.children).filter(c => c.classList && c.classList.contains('tiling-pane') && c.style && c.style.display !== 'none');
    } else {
      lowerPanes = lowerIds.map(id => getPane(id)).filter(el => el && el.style && el.style.display !== 'none');
    }"""

    if old_autopack in text:
        text = text.replace(old_autopack, new_autopack, 1)
    else:
        print("old_autopack not found, checking...")

    # 同時檢查下排 rebuildTierSplitters
    old_lower_rebuild = "if (lowerTier) this.rebuildTierSplitters(lowerTier);"
    new_lower_rebuild = "if (lowerTier && typeof lowerTier.querySelectorAll === 'function') this.rebuildTierSplitters(lowerTier);"
    text = text.replace(old_lower_rebuild, new_lower_rebuild)

    p.write_text(text, encoding='utf-8')
    print("workspace.js autopack fixed.")

if __name__ == '__main__':
    fix_autopack()
