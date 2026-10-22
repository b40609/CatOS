# -*- coding: utf-8 -*-
import pathlib

FRONTEND_ROOT = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final')

def update_router():
    p = FRONTEND_ROOT / 'js' / 'router.js'
    text = p.read_text(encoding='utf-8')

    center_old_start = text.find('<div class="header-center">')
    center_old_end = text.find('<div class="header-right">')
    if center_old_start == -1 or center_old_end == -1:
        raise ValueError("Cannot locate header-center in router.js")

    center_replacement = """<div class="header-center">
          <!-- Single Consolidated Technical Status Popover Entry (Dual-Tier) -->
          <div class="status-popover-trigger">
            <button class="btn btn-sm btn-ghost service-pill-dual" onclick="window.AppRouter.toggleServicePopover(event)" id="btn-service-popover" title="點擊查看底座核心遙測狀態">
              <span class="badge-dot green" style="width:7px; height:7px;"></span>
              <div style="display:flex; flex-direction:column; text-align:left; line-height:1.2;">
                <span style="font-size:12px; font-weight:600; color:var(--text-primary); display:flex; align-items:center; gap:4px;">
                  🟢 底座連線正常 · 16ms <span style="font-size:9px; color:var(--color-green);">${state.serviceStatusPopoverOpen ? '▲' : '▼'}</span>
                </span>
                <span style="font-size:10px; font-family:var(--font-mono); color:var(--text-muted); font-weight:500;">SUPERVISOR // WAL READY</span>
              </div>
            </button>

            <!-- 點擊展開之深黑磨砂浮層面板 (Popover Menu) -->
            <div class="status-popover-menu ${state.serviceStatusPopoverOpen ? 'open' : ''}" onclick="event.stopPropagation()">
              <div class="status-popover-header">
                <div style="font-size:12.5px; font-weight:600; color:var(--text-primary);">底座核心遙測狀態</div>
                <span class="badge" style="border:1px solid var(--gold-primary); color:var(--gold-primary); font-family:var(--font-mono); font-size:10px; padding:1px 6px; background:rgba(220,179,71,0.08); border-radius:2px;">LOCAL SIM // PASS</span>
              </div>
              <div style="display:flex; flex-direction:column; gap:8px; font-size:11.5px;">
                <div class="status-popover-item">
                  <span class="label">1. Supervisor 核心程序:</span>
                  <span class="val num" style="color:var(--color-green);">PID 4821 (ONLINE)</span>
                </div>
                <div class="status-popover-item">
                  <span class="label">2. WebSocket 行情報價延遲:</span>
                  <span class="val num" style="color:var(--color-green);">16ms (極低延遲)</span>
                </div>
                <div class="status-popover-item">
                  <span class="label">3. OKX REST API 頻率餘量:</span>
                  <span class="val num" style="color:var(--text-primary);">58 / 60 req/min (充足)</span>
                </div>
                <div class="status-popover-item">
                  <span class="label">4. 專屬委託成交標籤 (Tag):</span>
                  <span class="val num" style="color:var(--gold-primary); font-weight:600;">41cb53c54d6dABDE (自動注入)</span>
                </div>
                <div class="status-popover-item">
                  <span class="label">5. 合約持倉保證金模式:</span>
                  <span class="val" style="color:#38bdf8; font-weight:500;">全倉淨額 (Cross Net · USDT-M)</span>
                </div>
                <div class="status-popover-item">
                  <span class="label">6. 高精準金融數值核心:</span>
                  <span class="val" style="color:var(--text-secondary); font-family:var(--font-mono);">Decimal Core (拒絕浮點損失)</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        """

    text = text[:center_old_start] + center_replacement + text[center_old_end:]

    # 更新 toggleServicePopover 方法
    if 'toggleServicePopover: function' not in text:
        popover_code = """
  toggleServicePopover: function(event) {
    if (event && typeof event.stopPropagation === 'function') event.stopPropagation();
    const curr = window.appState.get('serviceStatusPopoverOpen');
    window.appState.set({ serviceStatusPopoverOpen: !curr });
  },
"""
        last_brace = text.rfind('};')
        text = text[:last_brace] + popover_code + "\n" + text[last_brace:]

    # 在 init 加上點擊外部關閉 popover
    if 'closest(".status-popover-trigger")' not in text:
        init_needle = 'window.appState.subscribe((state) => {'
        init_replacement = """// 點擊頁面外部關閉底座遙測 Popover
    if (typeof document !== 'undefined') {
      document.addEventListener('click', (e) => {
        if (!e.target || !e.target.closest || !e.target.closest('.status-popover-trigger')) {
          if (window.appState.get('serviceStatusPopoverOpen')) {
            window.appState.set({ serviceStatusPopoverOpen: false });
          }
        }
      });
    }

    window.appState.subscribe((state) => {"""
        text = text.replace(init_needle, init_replacement, 1)

    p.write_text(text, encoding='utf-8')
    print("router.js updated successfully.")

if __name__ == '__main__':
    update_router()
