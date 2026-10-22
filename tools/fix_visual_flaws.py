# -*- coding: utf-8 -*-
"""
Fix visual flaws:
1. Popover stacking context & z-index to float above content viewport.
2. Risk latch gauge pointer placement above track to prevent overlapping with scale legend.
3. Allocation panel title and compact spacing.
"""
import pathlib

FRONTEND_ROOT = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final')

def fix_css():
    p = FRONTEND_ROOT / 'css' / 'views.css'
    text = p.read_text(encoding='utf-8')

    # 1. 修正 header 和 popover z-index
    header_fix = """
/* Stacking Context Fix for Popover */
#app-header-container {
  position: relative;
  z-index: 9999;
}
.app-header {
  position: relative;
  z-index: 9999 !important;
}
.status-popover-trigger {
  position: relative;
  z-index: 10000;
}
.status-popover-menu {
  position: absolute;
  top: calc(100% + 10px);
  left: 50%;
  transform: translateX(-50%) translateY(-4px);
  width: 360px;
  background: #0a0d12 !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid #1F242D !important;
  border-radius: var(--border-radius);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.95), 0 0 1px rgba(220, 179, 71, 0.3) !important;
  padding: 14px 16px;
  z-index: 999999 !important;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.status-popover-menu.open {
  opacity: 1 !important;
  pointer-events: auto !important;
  transform: translateX(-50%) translateY(0) !important;
}
"""
    if "/* Stacking Context Fix for Popover */" not in text:
        text += header_fix

    # 2. 修正 Gauge 指針放置於軌道上方，徹底消滅疊字！
    old_gauge_css = """.gauge-track-wrapper {
  position: relative;
  padding: 8px 0 20px;
}
.gauge-track {
  height: 14px;
  width: 100%;
  background: #0b0e14;
  border: 1px solid #1e2736;
  border-radius: 2px;
  display: flex;
  overflow: hidden;
  position: relative;
}
.gauge-seg-hard {
  width: 25%;
  background: repeating-linear-gradient(45deg, #380d12, #380d12 4px, #4c1117 4px, #4c1117 8px);
  border-right: 1px solid #f87171;
}
.gauge-seg-soft {
  width: 20%;
  background: repeating-linear-gradient(45deg, #2b1f06, #2b1f06 4px, #3d2c08 4px, #3d2c08 8px);
  border-right: 1px solid #fbbf24;
}
.gauge-seg-normal {
  width: 25%;
  background: #111722;
  border-right: 1px solid #334155;
}
.gauge-seg-profit {
  width: 30%;
  background: #0b2219;
}
.gauge-pointer {
  position: absolute;
  top: 2px;
  left: 74%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
  transition: left 0.3s ease;
  z-index: 5;
}
.gauge-pointer-arrow {
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 6px solid var(--gold-primary);
}
.gauge-pointer-tag {
  background: #151208;
  border: 1px solid var(--gold-primary);
  color: var(--gold-primary);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 2px;
  white-space: nowrap;
  margin-top: 14px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.85);
}
.gauge-scale-legend {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  margin-top: 8px;
}"""

    new_gauge_css = """.gauge-track-wrapper {
  position: relative;
  padding: 28px 0 10px;
}
.gauge-track {
  height: 12px;
  width: 100%;
  background: #0b0e14;
  border: 1px solid #1e2736;
  border-radius: 2px;
  display: flex;
  overflow: hidden;
  position: relative;
}
.gauge-seg-hard {
  width: 25%;
  background: repeating-linear-gradient(45deg, #380d12, #380d12 4px, #4c1117 4px, #4c1117 8px);
  border-right: 1px solid #f87171;
}
.gauge-seg-soft {
  width: 20%;
  background: repeating-linear-gradient(45deg, #2b1f06, #2b1f06 4px, #3d2c08 4px, #3d2c08 8px);
  border-right: 1px solid #fbbf24;
}
.gauge-seg-normal {
  width: 25%;
  background: #111722;
  border-right: 1px solid #334155;
}
.gauge-seg-profit {
  width: 30%;
  background: #0b2219;
}
.gauge-pointer {
  position: absolute;
  top: 0;
  left: 74%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
  transition: left 0.3s ease;
  z-index: 5;
}
.gauge-pointer-tag {
  background: #151208;
  border: 1px solid var(--gold-primary);
  color: var(--gold-primary);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  padding: 1px 7px;
  border-radius: 2px;
  white-space: nowrap;
  box-shadow: 0 4px 12px rgba(0,0,0,0.9);
}
.gauge-pointer-arrow {
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid var(--gold-primary);
  margin-top: 2px;
}
.gauge-scale-legend {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  margin-top: 8px;
}"""

    if old_gauge_css in text:
        text = text.replace(old_gauge_css, new_gauge_css)

    # 3. 調整甜甜圈容器尺寸
    old_donut_css = """.donut-chart-container {
  position: relative;
  width: 150px;
  height: 150px;
  margin: 0 auto;
  flex-shrink: 0;
}"""
    new_donut_css = """.donut-chart-container {
  position: relative;
  width: 130px;
  height: 130px;
  margin: 0 auto;
  flex-shrink: 0;
}"""
    text = text.replace(old_donut_css, new_donut_css)

    # 確保 LF 結尾
    text = text.replace('\r\n', '\n')
    p.write_text(text, encoding='utf-8')
    print("views.css visual fixes applied.")

def fix_dashboard():
    p = FRONTEND_ROOT / 'js' / 'views' / 'dashboard.js'
    text = p.read_text(encoding='utf-8')

    # 修正 ALLOCATION 標題列文字排版，防止截斷
    old_alloc_header = """                  <div class="widget-box-header">
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
                  </div>"""

    new_alloc_header = """                  <div class="widget-box-header">
                    <div class="widget-title-wrap" style="flex:1; min-width:0; overflow:hidden;">
                      <span class="widget-drag-handle" style="display:none;" aria-hidden="true"></span>
                      <div class="th-dual-zh" style="font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">:: ALLOCATION // 保證金與曝險</div>
                      <div class="th-dual-en" style="font-size:10px;">MARGIN & EXPOSURE ALLOCATION</div>
                    </div>
                    <div style="display:flex; align-items:center; gap:6px; flex-shrink:0;">
                      <span class="badge" id="btn-toggle-leverage" style="border:1px solid rgba(220,179,71,0.4); color:var(--gold-primary); font-family:var(--font-mono); font-size:10px; padding:2px 6px; cursor:pointer; background:rgba(220,179,71,0.08); border-radius:2px;" onclick="window.DashboardView.toggleLeverageBasis()" title="切換曝險上限 / 淨本金基準">基準: 3.0x 曝險</span>
                      <button class="btn-pane-maximize" data-widget="allocation" onclick="window.WorkspaceEngine.toggleMaximize('allocation')" title="最大化面板">
                        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                      </button>
                      <button class="widget-btn-hide" onclick="window.WorkspaceEngine.hideWidget('allocation')" title="隱藏此元件">&times;</button>
                    </div>
                  </div>"""

    text = text.replace(old_alloc_header, new_alloc_header, 1)

    # 確保 LF
    text = text.replace('\r\n', '\n')
    p.write_text(text, encoding='utf-8')
    print("dashboard.js visual fixes applied.")

if __name__ == '__main__':
    fix_css()
    fix_dashboard()
