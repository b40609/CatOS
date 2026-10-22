# -*- coding: utf-8 -*-
import pathlib

FRONTEND_ROOT = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final')

def append_views_css():
    p = FRONTEND_ROOT / 'css' / 'views.css'
    text = p.read_text(encoding='utf-8')
    
    extra_css = """
/* ==========================================================================
   ALLOCATION 甜甜圈配置圖樣式 (黑曜石 OLED 質感)
   ========================================================================== */
.donut-chart-container {
  position: relative;
  width: 150px;
  height: 150px;
  margin: 0 auto;
  flex-shrink: 0;
}
.donut-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}
.donut-segment {
  fill: transparent;
  stroke-width: 24;
  transition: stroke-width 0.2s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.2s ease;
  cursor: pointer;
}
.donut-segment:hover,
.donut-segment.is-hovered {
  stroke-width: 28;
  opacity: 0.95;
  filter: drop-shadow(0 0 6px rgba(220, 179, 71, 0.4));
}
.donut-center-hud {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  text-align: center;
}
.donut-center-label {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-muted);
  letter-spacing: 0.05em;
  transition: color 0.15s ease;
}
.donut-center-val {
  font-size: 14px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: #ffffff;
  margin-top: 2px;
  letter-spacing: -0.02em;
  transition: color 0.15s ease;
}
.donut-center-sub {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--gold-primary);
  margin-top: 2px;
}
.allocation-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--border-subtle);
}
.pill-switch-group {
  display: inline-flex;
  background: #080a0f;
  border: 1px solid var(--border-default);
  border-radius: var(--border-radius-sm);
  padding: 2px;
  gap: 2px;
}
.pill-switch-btn {
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  font-family: var(--font-sans);
  padding: 2px 7px;
  border-radius: 2px;
  cursor: pointer;
  transition: all var(--transition-fast);
}
.pill-switch-btn:hover {
  color: var(--text-primary);
  background: var(--bg-surface-hover);
}
.pill-switch-btn.active {
  background: #181d26;
  color: var(--gold-primary);
  font-weight: 600;
  border: 1px solid rgba(220, 179, 71, 0.4);
}
.allocation-main-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex: 1;
}
.allocation-legend-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.legend-item-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
  background: rgba(18, 22, 31, 0.5);
  border: 1px solid var(--border-subtle);
  border-radius: 2px;
  font-size: 11.5px;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease;
}
.legend-item-row:hover,
.legend-item-row.is-hovered {
  background: rgba(27, 32, 44, 0.85);
  border-color: rgba(220, 179, 71, 0.5);
}
.legend-left {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.legend-swatch {
  width: 7px;
  height: 7px;
  border-radius: 1px;
  flex-shrink: 0;
}
.legend-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  font-family: var(--font-mono);
}
.legend-amount {
  color: #d0d6e2;
  font-size: 11.5px;
  font-weight: 500;
}
.legend-pct {
  color: var(--text-muted);
  font-size: 11px;
  width: 32px;
  text-align: right;
}

/* ==========================================================================
   日損鎖存安全緩衝儀表樣式 (RISK LATCH GAUGE)
   ========================================================================== */
.latch-metric-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  background: #07090e;
  border: 1px solid #171d27;
  padding: 8px 10px;
  border-radius: 2px;
}
.latch-summary-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.latch-summary-label {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  text-transform: uppercase;
}
.latch-summary-val {
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: #ffffff;
}
.gauge-track-wrapper {
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
}

/* ==========================================================================
   頂部底座遙測 Popover 深黑磨砂浮層面板
   ========================================================================== */
.status-popover-trigger {
  position: relative;
}
.status-popover-menu {
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%) translateY(-6px);
  width: 340px;
  background: rgba(10, 13, 18, 0.96);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border: 1px solid #1F242D;
  border-radius: var(--border-radius);
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.85), 0 0 1px rgba(220, 179, 71, 0.2);
  padding: 12px 14px;
  z-index: 999;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s cubic-bezier(0.16, 1, 0.3, 1), transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.status-popover-menu.open {
  opacity: 1;
  pointer-events: auto;
  transform: translateX(-50%) translateY(0);
}
.status-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--border-subtle);
  padding-bottom: 8px;
}
.status-popover-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11.5px;
  padding: 2px 0;
}
.status-popover-item .label {
  color: var(--text-muted);
}
.status-popover-item .val {
  font-family: var(--font-mono);
  font-weight: 500;
}
"""
    if "/* ================= 1. ALLOCATION 甜甜圈配置圖樣式" not in text and ".donut-chart-container" not in text:
        text += extra_css
        p.write_text(text, encoding='utf-8')
        print("views.css updated with allocation, latch gauge, and popover styles.")
    else:
        print("views.css already contains styles.")

if __name__ == '__main__':
    append_views_css()
