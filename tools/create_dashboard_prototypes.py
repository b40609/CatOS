# -*- coding: utf-8 -*-
"""
create_dashboard_prototypes.py
Generates catOS Dashboard Prototypes A and B based on the user's requirements:
- Prototype A: Multi-Pane Workstation (Refined classic layout: KPI -> Trend/Allocation/Incident -> Latch/Bots/Research/Yaozi)
- Prototype B: Trend-First Overview (Large Trend Stage + Attention Hub -> Fleet/Allocation/Research)
Includes 5-state switcher, Technical details in Popover, clean Tabler components, zero console errors.
"""
import pathlib
import os

# ==============================================================================
# PROTOTYPE A: Multi-Pane Workstation (沿用舊版的多面板工作區，改善擁擠與可讀性)
# ==============================================================================
HTML_A = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>catOS · 戰情總覽 Prototype A (多面板工作區 Multi-Pane Workstation)</title>
  
  <!-- Fonts: Inter, JetBrains Mono, Noto Sans TC -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;600;700&display=swap" rel="stylesheet">

  <style>
    /* ==========================================================================
       catOS Semantic Design Tokens (Tabler Reference, Fully Modular)
       ========================================================================== */
    :root {
      /* Background Tokens */
      --bg-base: #080a0d;
      --bg-sidebar: #0a0d12;
      --bg-surface: #0e1218;
      --bg-surface-subtle: #121720;
      --bg-surface-hover: #181e2a;
      --bg-surface-active: #1f2736;
      --bg-input: #080b0f;
      --bg-code: #05070a;

      /* Border Tokens */
      --border-color: #1f2633;
      --border-subtle: #151a24;
      --border-focus: #dcb347;

      /* Text Tokens */
      --text-primary: #e6edf3;
      --text-secondary: #8b949e;
      --text-muted: #57606a;
      --text-inverse: #080a0d;

      /* Accent & Brand Tokens (catOS Obsidian Gold) */
      --color-accent: #dcb347;
      --color-accent-hover: #e8c25b;
      --color-accent-subtle: rgba(220, 179, 71, 0.10);
      --color-accent-border: rgba(220, 179, 71, 0.35);

      /* Semantic Status Tokens */
      --color-success: #2ea043;
      --color-success-subtle: rgba(46, 160, 67, 0.12);
      --color-success-border: rgba(46, 160, 67, 0.40);

      --color-warning: #d29922;
      --color-warning-subtle: rgba(210, 153, 34, 0.12);
      --color-warning-border: rgba(210, 153, 34, 0.40);

      --color-danger: #f85149;
      --color-danger-subtle: rgba(248, 81, 73, 0.12);
      --color-danger-border: rgba(248, 81, 73, 0.40);

      --color-info: #58a6ff;
      --color-info-subtle: rgba(88, 166, 255, 0.12);
      --color-info-border: rgba(88, 166, 255, 0.40);

      /* Typography */
      --font-sans: 'Inter', 'Noto Sans TC', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', SFMono-Regular, Menlo, Monaco, Consolas, monospace;

      /* Low Radius */
      --radius-sm: 2px;
      --radius-md: 4px;
      --radius-lg: 6px;

      /* Dimensions */
      --sidebar-width: 200px;
      --header-height: 48px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      background-color: var(--bg-base);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: 13px;
      line-height: 1.45;
      height: 100vh;
      overflow: hidden;
      display: flex;
    }

    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: var(--bg-base); }
    ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: var(--radius-sm); }
    ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

    /* Attached Sidebar */
    .app-sidebar {
      width: var(--sidebar-width);
      background-color: var(--bg-sidebar);
      border-right: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      height: 100vh;
    }

    .sidebar-brand {
      height: var(--header-height);
      padding: 0 16px;
      display: flex;
      align-items: center;
      gap: 8px;
      border-bottom: 1px solid var(--border-subtle);
    }

    .brand-logo-badge {
      width: 20px;
      height: 20px;
      background: var(--color-accent-subtle);
      border: 1px solid var(--color-accent-border);
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      color: var(--color-accent);
    }

    .brand-title {
      font-size: 14px;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: var(--text-primary);
    }

    .brand-version {
      font-family: var(--font-mono);
      font-size: 10px;
      color: var(--text-muted);
      border: 1px solid var(--border-color);
      padding: 1px 4px;
      border-radius: var(--radius-sm);
      margin-left: auto;
    }

    .sidebar-nav {
      flex: 1;
      padding: 12px 8px;
      display: flex;
      flex-direction: column;
      gap: 2px;
      overflow-y: auto;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border-radius: var(--radius-md);
      color: var(--text-secondary);
      text-decoration: none;
      font-size: 12.5px;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.15s ease, color 0.15s ease;
    }

    .nav-item:hover {
      background: var(--bg-surface-hover);
      color: var(--text-primary);
    }

    .nav-item.active {
      background: var(--color-accent-subtle);
      color: var(--color-accent);
      border: 1px solid var(--color-accent-border);
      font-weight: 600;
    }

    .nav-icon { width: 15px; height: 15px; stroke-width: 2; }

    /* App Main */
    .app-main {
      flex: 1;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      min-width: 0;
    }

    /* Topbar */
    .app-header {
      height: var(--header-height);
      background-color: var(--bg-surface);
      border-bottom: 1px solid var(--border-color);
      padding: 0 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      position: relative;
    }

    .header-breadcrumb {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
    }

    .breadcrumb-title { font-weight: 700; color: var(--text-primary); }
    .badge-prototype {
      background: var(--color-accent-subtle);
      border: 1px solid var(--color-accent-border);
      color: var(--color-accent);
      font-size: 10.5px;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: var(--radius-sm);
    }

    /* Header Controls */
    .header-controls {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .state-switcher {
      display: flex;
      align-items: center;
      gap: 4px;
      background: var(--bg-base);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      padding: 2px;
    }

    .state-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 11px;
      padding: 3px 8px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-weight: 500;
      transition: all 0.15s ease;
    }

    .state-btn.active {
      background: var(--bg-surface-active);
      color: var(--text-primary);
      font-weight: 600;
    }

    /* Technical Popover Trigger */
    .status-popover-trigger {
      position: relative;
    }

    .service-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-color);
      background: var(--bg-surface-subtle);
      cursor: pointer;
      font-size: 11px;
      color: var(--text-secondary);
      transition: border-color 0.15s ease;
    }

    .service-pill:hover {
      border-color: var(--color-accent);
      color: var(--text-primary);
    }

    .status-popover-menu {
      display: none;
      position: absolute;
      top: calc(100% + 8px);
      right: 0;
      width: 320px;
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.7);
      padding: 12px;
      z-index: 999;
    }

    .status-popover-menu.open { display: block; }

    .popover-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
      font-weight: 600;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--border-subtle);
      margin-bottom: 8px;
    }

    .popover-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 11.5px;
      padding: 3px 0;
    }

    .popover-item .label { color: var(--text-muted); }
    .popover-item .val { font-family: var(--font-mono); color: var(--text-primary); }

    /* Workstation Canvas (Scrollable) */
    .workstation-canvas {
      flex: 1;
      overflow-y: auto;
      padding: 12px 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    /* Tabler Card Base */
    .card {
      background-color: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      display: flex;
      flex-direction: column;
      position: relative;
    }

    .card-header {
      padding: 8px 12px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 36px;
    }

    .card-title {
      font-size: 12.5px;
      font-weight: 600;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .card-actions {
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .card-body {
      padding: 12px;
    }

    /* Badges & Dots */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 6px;
      font-size: 10.5px;
      font-weight: 600;
      border-radius: var(--radius-sm);
    }

    .badge-success { background: var(--color-success-subtle); color: var(--color-success); border: 1px solid var(--color-success-border); }
    .badge-warning { background: var(--color-warning-subtle); color: var(--color-warning); border: 1px solid var(--color-warning-border); }
    .badge-danger { background: var(--color-danger-subtle); color: var(--color-danger); border: 1px solid var(--color-danger-border); }
    .badge-info { background: var(--color-info-subtle); color: var(--color-info); border: 1px solid var(--color-info-border); }
    .badge-secondary { background: var(--bg-surface-subtle); color: var(--text-secondary); border: 1px solid var(--border-color); }
    .badge-accent { background: var(--color-accent-subtle); color: var(--color-accent); border: 1px solid var(--color-accent-border); }

    .badge-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
    .dot-success { background: var(--color-success); }
    .dot-warning { background: var(--color-warning); }
    .dot-danger { background: var(--color-danger); }

    /* Button */
    .btn {
      height: 24px;
      padding: 0 8px;
      font-size: 11px;
      font-weight: 500;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-color);
      background: var(--bg-surface-subtle);
      color: var(--text-primary);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      text-decoration: none;
      transition: all 0.15s ease;
    }

    .btn:hover { background: var(--bg-surface-hover); border-color: var(--text-secondary); }
    .btn-primary { background: var(--color-accent); border-color: var(--color-accent); color: var(--text-inverse); font-weight: 600; }
    .btn-primary:hover { background: var(--color-accent-hover); }

    /* Number & Mono */
    .num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

    /* ==========================================================================
       LAYER 1: KPI Telemetry Grid (4 Cards)
       ========================================================================== */
    .kpi-row {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
    }

    .kpi-card {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      padding: 10px 14px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      height: 82px;
      position: relative;
    }

    .kpi-card.accent-border {
      border-left: 3px solid var(--color-accent);
    }

    .kpi-label-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11.5px;
      font-weight: 600;
      color: var(--text-secondary);
    }

    .kpi-val {
      font-size: 19px;
      font-weight: 700;
      color: var(--text-primary);
      margin: 2px 0;
    }

    .kpi-sub {
      font-size: 11px;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    /* ==========================================================================
       LAYER 2: Visual Core (Equity Chart, Allocation Donut, Incident Stream)
       ========================================================================== */
    .visual-core-row {
      display: grid;
      grid-template-columns: 1.25fr 0.75fr 0.65fr;
      gap: 10px;
      min-height: 280px;
    }

    /* Equity Curve Box */
    .equity-chart-box {
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }

    .chart-svg-container {
      width: 100%;
      height: 180px;
      position: relative;
    }

    .chart-footer-notes {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-top: 8px;
      border-top: 1px solid var(--border-subtle);
      font-size: 11px;
      color: var(--text-muted);
    }

    /* Allocation Donut */
    .donut-layout {
      display: grid;
      grid-template-columns: 140px 1fr;
      gap: 12px;
      align-items: center;
    }

    .donut-svg-wrap {
      position: relative;
      width: 130px;
      height: 130px;
      margin: 0 auto;
    }

    .donut-hud-center {
      position: absolute;
      inset: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      pointer-events: none;
      text-align: center;
    }

    .donut-legend-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 4px 6px;
      border-radius: var(--radius-sm);
      background: var(--bg-surface-subtle);
      border: 1px solid var(--border-subtle);
      font-size: 11px;
      margin-bottom: 4px;
    }

    /* Incident Stream */
    .incident-list {
      display: flex;
      flex-direction: column;
      gap: 6px;
      overflow-y: auto;
      max-height: 220px;
    }

    .incident-item {
      padding: 6px 8px;
      border-radius: var(--radius-sm);
      background: var(--bg-surface-subtle);
      border: 1px solid var(--border-subtle);
      cursor: pointer;
      transition: background 0.15s ease;
    }

    .incident-item:hover { background: var(--bg-surface-hover); }

    .incident-item-header {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 11px;
    }

    .incident-reason-box {
      display: none;
      margin-top: 5px;
      padding-top: 5px;
      border-top: 1px solid var(--border-subtle);
      font-size: 10.5px;
      color: var(--text-secondary);
    }

    .incident-item.open .incident-reason-box { display: block; }

    /* ==========================================================================
       LAYER 3: Execution & Research Summary (4 Cards)
       ========================================================================== */
    .execution-summary-row {
      display: grid;
      grid-template-columns: 1.15fr 0.95fr 0.95fr 0.95fr;
      gap: 10px;
    }

    /* Risk Latch Gauge */
    .latch-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 6px;
      margin-bottom: 10px;
    }

    .latch-stat-card {
      background: var(--bg-surface-subtle);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 6px;
      text-align: center;
    }

    .latch-stat-card .label { font-size: 10px; color: var(--text-muted); }
    .latch-stat-card .val { font-size: 12px; font-weight: 700; margin-top: 2px; }

    .gauge-track-box {
      position: relative;
      margin-top: 10px;
      padding-bottom: 18px;
    }

    .gauge-bar {
      height: 7px;
      width: 100%;
      border-radius: 3px;
      display: flex;
      overflow: hidden;
      background: var(--bg-base);
    }

    .gauge-seg-hard { width: 20%; background: #f85149; }
    .gauge-seg-soft { width: 15%; background: #d29922; }
    .gauge-seg-normal { width: 35%; background: #30363d; }
    .gauge-seg-profit { width: 30%; background: #2ea043; }

    .gauge-needle {
      position: absolute;
      top: -3px;
      width: 2px;
      height: 13px;
      background: #ffffff;
      box-shadow: 0 0 5px #ffffff;
      transition: left 0.3s ease;
    }

    .gauge-needle::after {
      content: attr(data-label);
      position: absolute;
      top: 15px;
      left: 50%;
      transform: translateX(-50%);
      font-family: var(--font-mono);
      font-size: 10px;
      color: var(--text-primary);
      white-space: nowrap;
    }

    /* Bot List Card */
    .bot-item-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 7px 8px;
      border-radius: var(--radius-sm);
      background: var(--bg-surface-subtle);
      border: 1px solid var(--border-subtle);
      margin-bottom: 6px;
    }

    /* Research Queue Item */
    .research-item-row {
      padding: 7px 8px;
      border-radius: var(--radius-sm);
      background: var(--bg-surface-subtle);
      border: 1px solid var(--border-subtle);
      margin-bottom: 6px;
    }

    /* Yaozi Item */
    .yaozi-item-row {
      padding: 7px 8px;
      border-radius: var(--radius-sm);
      background: var(--bg-surface-subtle);
      border: 1px solid var(--border-subtle);
      margin-bottom: 6px;
      font-size: 11.5px;
    }

    /* Responsive */
    @media (max-width: 1200px) {
      .visual-core-row { grid-template-columns: 1fr; }
      .execution-summary-row { grid-template-columns: 1fr 1fr; }
      .kpi-row { grid-template-columns: 1fr 1fr; }
    }

    @media (max-width: 768px) {
      body { flex-direction: column; height: auto; overflow: auto; }
      .app-sidebar { width: 100%; height: auto; }
      .workstation-canvas { overflow: visible; }
      .execution-summary-row { grid-template-columns: 1fr; }
      .kpi-row { grid-template-columns: 1fr; }
      .donut-layout { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

  <!-- 1. Attached Sidebar -->
  <aside class="app-sidebar">
    <div class="sidebar-brand">
      <div class="brand-logo-badge">C</div>
      <div class="brand-title">catOS</div>
      <div class="brand-version">v1.2</div>
    </div>

    <nav class="sidebar-nav">
      <div class="nav-item active">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
        <span>戰情總覽</span>
      </div>
      <div class="nav-item">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        <span>策略中心</span>
      </div>
      <div class="nav-item">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="15" x2="15" y2="15"/></svg>
        <span>機器人管理</span>
      </div>
      <div class="nav-item">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        <span>風險控管</span>
      </div>
      <div class="nav-item">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/></svg>
        <span>系統日誌</span>
      </div>
      <div class="nav-item">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        <span>偏好設定</span>
      </div>
    </nav>
  </aside>

  <!-- 2. Main Viewport -->
  <main class="app-main">
    
    <!-- Topbar -->
    <header class="app-header">
      <div class="header-breadcrumb">
        <span class="breadcrumb-title">戰情總覽</span>
        <span class="badge-prototype">產品原型 · 示意資料</span>
        <span class="badge badge-secondary" style="font-size:10.5px;">PROTOTYPE A · 多面板工作區</span>
      </div>

      <div class="header-controls">
        <!-- Interactive Scenario Switcher -->
        <div class="state-switcher">
          <button class="state-btn active" onclick="switchState('NORMAL', this)">正常連線</button>
          <button class="state-btn" onclick="switchState('SOFT_LATCH', this)">日損軟限</button>
          <button class="state-btn" onclick="switchState('RETAINED_409', this)">持倉停止 (409)</button>
          <button class="state-btn" onclick="switchState('EMPTY', this)">空資料</button>
          <button class="state-btn" onclick="switchState('RECOVERY', this)">服務異常</button>
        </div>

        <!-- Technical Telemetry Popover -->
        <div class="status-popover-trigger">
          <div class="service-pill" onclick="togglePopover()">
            <span class="badge-dot dot-success" id="popover-dot"></span>
            <span id="popover-btn-label">底座連線正常 · 16ms</span>
            <span style="font-size:9px;">▾</span>
          </div>

          <div class="status-popover-menu" id="status-popover-menu">
            <div class="popover-header">
              <span>底座核心遙測狀態</span>
              <span class="badge badge-accent">LOCAL SIM / PASS</span>
            </div>
            <div class="popover-item">
              <span class="label">1. Supervisor 核心程序</span>
              <span class="val" style="color:var(--color-success);">PID 4821 (ONLINE)</span>
            </div>
            <div class="popover-item">
              <span class="label">2. WebSocket 行情延遲</span>
              <span class="val">16ms (極低延遲)</span>
            </div>
            <div class="popover-item">
              <span class="label">3. OKX REST 頻率額度</span>
              <span class="val">58 / 60 req/min</span>
            </div>
            <div class="popover-item">
              <span class="label">4. 委託成交標籤 (Tag)</span>
              <span class="val">41cb53c54d6dABDE</span>
            </div>
            <div class="popover-item">
              <span class="label">5. 合約保證金模式</span>
              <span class="val">全倉淨額 (Cross Net)</span>
            </div>
            <div class="popover-item">
              <span class="label">6. 金融數值核心</span>
              <span class="val">Decimal Core (拒絕浮點)</span>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- Scrollable Workstation Canvas -->
    <div class="workstation-canvas">
      
      <!-- ================= LAYER 1: Core KPI Telemetry ================= -->
      <section class="kpi-row" id="kpi-row-container">
        <!-- 1. Total Account Equity -->
        <div class="kpi-card accent-border">
          <div class="kpi-label-row">
            <span>總權益淨值</span>
            <span class="badge badge-secondary" style="font-size:10px;">即時估值</span>
          </div>
          <div class="kpi-val num" id="kpi-equity-val">125,480.50 <span style="font-size:13px; font-weight:normal; color:var(--text-secondary);">USDT</span></div>
          <div class="kpi-sub">
            <span>實時持倉估值 + 現金餘額</span>
            <span class="num" style="color:var(--color-success);" id="kpi-equity-diff">+1.00%</span>
          </div>
        </div>

        <!-- 2. Daily PnL -->
        <div class="kpi-card">
          <div class="kpi-label-row">
            <span>今日損益</span>
            <span style="font-size:10.5px; color:var(--text-muted);">00:00 (UTC+8) 起算</span>
          </div>
          <div class="kpi-val num" id="kpi-pnl-val" style="color:var(--color-success);">+1,240.80 <span style="font-size:13px; font-weight:normal;">USDT</span></div>
          <div class="kpi-sub">
            <span>已實現損益 + 未實現浮盈</span>
            <span class="num" id="kpi-pnl-rate">+1.00%</span>
          </div>
        </div>

        <!-- 3. Active Bots -->
        <div class="kpi-card">
          <div class="kpi-label-row">
            <span>運行中機器人</span>
            <span class="badge badge-success" id="kpi-bots-badge">1 運行中</span>
          </div>
          <div class="kpi-val num" id="kpi-bots-val">1 <span style="font-size:13px; font-weight:normal; color:var(--text-muted);">/ 3 部署總計</span></div>
          <div class="kpi-sub">
            <span id="kpi-bots-detail">1 運行中 · 1 需處理 · 1 已停止</span>
            <a href="javascript:void(0)" style="color:var(--color-accent); text-decoration:none;">機器人 &rarr;</a>
          </div>
        </div>

        <!-- 4. Risk Status -->
        <div class="kpi-card">
          <div class="kpi-label-row">
            <span>風控狀態</span>
            <span class="badge badge-success" id="kpi-risk-badge">NORMAL</span>
          </div>
          <div class="kpi-val num" id="kpi-leverage-val">1.85x <span style="font-size:13px; font-weight:normal; color:var(--text-muted);">/ 上限 3.00x</span></div>
          <div class="kpi-sub">
            <span id="kpi-risk-detail">日損軟限 10.0% · 當前回撤 -0.30%</span>
            <a href="javascript:void(0)" style="color:var(--color-accent); text-decoration:none;">風控 &rarr;</a>
          </div>
        </div>
      </section>

      <!-- ================= LAYER 2: Visual Core (Equity Chart, Allocation, Incident Stream) ================= -->
      <section class="visual-core-row">
        
        <!-- Left: Equity Curve (48%) -->
        <div class="card" style="display:flex; flex-direction:column;">
          <div class="card-header">
            <div class="card-title">
              <span>帳戶淨值走勢</span>
              <span class="badge badge-secondary" style="font-size:10px;">EQUITY CURVE</span>
            </div>
            <div class="card-actions">
              <div style="display:flex; gap:2px; background:var(--bg-base); border:1px solid var(--border-color); border-radius:var(--radius-sm); padding:1px;">
                <button class="btn" style="height:20px; font-size:10px;" onclick="setTimeRange('7D', this)">7D</button>
                <button class="btn btn-primary" style="height:20px; font-size:10px;" onclick="setTimeRange('30D', this)">30D</button>
                <button class="btn" style="height:20px; font-size:10px;" onclick="setTimeRange('90D', this)">90D</button>
              </div>
            </div>
          </div>

          <div class="card-body equity-chart-box">
            <div class="chart-svg-container">
              <svg width="100%" height="100%" viewBox="0 0 600 180" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="goldGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#dcb347" stop-opacity="0.35"/>
                    <stop offset="100%" stop-color="#dcb347" stop-opacity="0.0"/>
                  </linearGradient>
                </defs>
                <!-- Grid Lines -->
                <line x1="0" y1="30" x2="600" y2="30" stroke="#151a24" stroke-dasharray="3,3"/>
                <line x1="0" y1="80" x2="600" y2="80" stroke="#151a24" stroke-dasharray="3,3"/>
                <line x1="0" y1="130" x2="600" y2="130" stroke="#151a24" stroke-dasharray="3,3"/>

                <!-- Area Fill -->
                <polygon points="0,150 50,145 120,138 200,142 280,120 360,105 450,60 540,40 600,32 600,180 0,180" fill="url(#goldGradient)"/>
                
                <!-- Stroke Curve -->
                <polyline id="equity-line-path" fill="none" stroke="#dcb347" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"
                          points="0,150 50,145 120,138 200,142 280,120 360,105 450,60 540,40 600,32"/>
                
                <!-- Current Dot -->
                <circle cx="600" cy="32" r="4" fill="#ffffff" stroke="#dcb347" stroke-width="2"/>

                <!-- Axis Labels -->
                <text x="10" y="24" fill="#57606a" font-size="10" font-family="JetBrains Mono">126,000</text>
                <text x="10" y="74" fill="#57606a" font-size="10" font-family="JetBrains Mono">122,000</text>
                <text x="10" y="124" fill="#57606a" font-size="10" font-family="JetBrains Mono">118,000</text>
                
                <text x="10" y="172" fill="#57606a" font-size="10" font-family="JetBrains Mono">09-01</text>
                <text x="180" y="172" fill="#57606a" font-size="10" font-family="JetBrains Mono">09-10</text>
                <text x="360" y="172" fill="#57606a" font-size="10" font-family="JetBrains Mono">09-20</text>
                <text x="540" y="172" fill="#57606a" font-size="10" font-family="JetBrains Mono">09-30</text>
              </svg>
            </div>

            <div class="chart-footer-notes">
              <span>撮合基準：離線歷史模擬數據 (未連線真實交易所)</span>
              <span>滑價損耗模型啟用</span>
              <span>[設計提案: 待接即時帳戶權益時序]</span>
            </div>
          </div>
        </div>

        <!-- Middle: Allocation Donut (28%) -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>保證金與曝險配置</span>
              <span class="badge badge-accent" style="font-size:10px;">3.0x 槓桿基準</span>
            </div>
            <div class="card-actions">
              <span style="font-size:11px; color:var(--text-muted);">CROSS NET</span>
            </div>
          </div>

          <div class="card-body">
            <div class="donut-layout">
              <div class="donut-svg-wrap">
                <svg width="100%" height="100%" viewBox="0 0 100 100">
                  <!-- Segments (stroke-dasharray based on 2 * PI * r = 251.2 for r=40) -->
                  <!-- Total 251.2: 32% (80.3), 15% (37.7), 43% (108.0), 10% (25.1) -->
                  <circle cx="50" cy="50" r="38" fill="none" stroke="#2ea043" stroke-width="12"
                          stroke-dasharray="80.3 170.9" stroke-dashoffset="0" transform="rotate(-90 50 50)"/>
                  <circle cx="50" cy="50" r="38" fill="none" stroke="#58a6ff" stroke-width="12"
                          stroke-dasharray="37.7 213.5" stroke-dashoffset="-80.3" transform="rotate(-90 50 50)"/>
                  <circle cx="50" cy="50" r="38" fill="none" stroke="#dcb347" stroke-width="12"
                          stroke-dasharray="108.0 143.2" stroke-dashoffset="-118" transform="rotate(-90 50 50)"/>
                  <circle cx="50" cy="50" r="38" fill="none" stroke="#a371f7" stroke-width="12"
                          stroke-dasharray="25.1 226.1" stroke-dashoffset="-226" transform="rotate(-90 50 50)"/>
                </svg>
                <div class="donut-hud-center">
                  <div style="font-size:9.5px; color:var(--text-muted); font-family:var(--font-mono);">總名義曝險</div>
                  <div class="num" style="font-size:12.5px; font-weight:700; color:#fff;" id="donut-exposure-val">1,420.50</div>
                  <div style="font-size:9px; color:var(--color-accent); font-family:var(--font-mono);">上限 3,000</div>
                </div>
              </div>

              <!-- Legend List -->
              <div>
                <div class="donut-legend-item">
                  <span style="display:flex; align-items:center; gap:5px;">
                    <span style="width:7px; height:7px; border-radius:1px; background:#2ea043;"></span>
                    <span>BTC 永續持倉</span>
                  </span>
                  <span class="num" style="font-weight:600;">320.00 (32%)</span>
                </div>
                <div class="donut-legend-item">
                  <span style="display:flex; align-items:center; gap:5px;">
                    <span style="width:7px; height:7px; border-radius:1px; background:#58a6ff;"></span>
                    <span>委託在途凍結</span>
                  </span>
                  <span class="num" style="font-weight:600;">150.00 (15%)</span>
                </div>
                <div class="donut-legend-item">
                  <span style="display:flex; align-items:center; gap:5px;">
                    <span style="width:7px; height:7px; border-radius:1px; background:#dcb347;"></span>
                    <span>未佔用可用</span>
                  </span>
                  <span class="num" style="font-weight:600;">430.00 (43%)</span>
                </div>
                <div class="donut-legend-item">
                  <span style="display:flex; align-items:center; gap:5px;">
                    <span style="width:7px; height:7px; border-radius:1px; background:#a371f7;"></span>
                    <span>風控緩衝預留</span>
                  </span>
                  <span class="num" style="font-weight:600;">100.00 (10%)</span>
                </div>
              </div>
            </div>
            <div style="font-size:10.5px; color:var(--text-muted); margin-top:8px; border-top:1px solid var(--border-subtle); padding-top:4px;">
              [設計提案: 需由 Supervisor 提供保證金快照 API · 單幣預算占比 50%]
            </div>
          </div>
        </div>

        <!-- Right: Incident Stream (24%) -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>重要事件時間軸</span>
              <span class="badge badge-secondary" style="font-size:10px;">3 則</span>
            </div>
            <div class="card-actions">
              <a href="javascript:void(0)" style="font-size:11px; color:var(--color-accent); text-decoration:none;">完整日誌 &rarr;</a>
            </div>
          </div>

          <div class="card-body" style="padding:8px 10px;">
            <div class="incident-list">
              <div class="incident-item open" onclick="toggleIncident(this)">
                <div class="incident-item-header">
                  <span class="num" style="color:var(--text-muted);">11:10:02</span>
                  <span class="badge badge-warning">WARN</span>
                  <span style="font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">ETH 震盪網格 Alpha 03 撮合滑價</span>
                </div>
                <div class="incident-reason-box">
                  市況瞬時流動性枯竭，滑價達 2.8 bps；低於災難停損閾值，策略維持觀察。
                </div>
              </div>

              <div class="incident-item" onclick="toggleIncident(this)">
                <div class="incident-item-header">
                  <span class="num" style="color:var(--text-muted);">10:24:15</span>
                  <span class="badge badge-info">INFO</span>
                  <span style="font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">外部 Agent 生成新研究草稿</span>
                </div>
                <div class="incident-reason-box">
                  已將 ATR-v1.2 成果提交至策略中心等待人工代碼安全簽核。
                </div>
              </div>

              <div class="incident-item" onclick="toggleIncident(this)">
                <div class="incident-item-header">
                  <span class="num" style="color:var(--text-muted);">09:30:10</span>
                  <span class="badge badge-secondary">INFO</span>
                  <span style="font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">SOL 試驗波段 04 切換為手動</span>
                </div>
                <div class="incident-reason-box">
                  操作員手動停機，該 Bot 部位已歸零 (空倉)。
                </div>
              </div>
            </div>
          </div>
        </div>

      </section>

      <!-- ================= LAYER 3: Execution & Research Summary ================= -->
      <section class="execution-summary-row">
        
        <!-- Card 1: Risk Latch Gauge (34%) -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>日損鎖存安全儀表</span>
              <span class="badge badge-success" id="latch-status-badge">安全運行中</span>
            </div>
            <span style="font-size:10px; font-family:var(--font-mono); color:var(--text-muted);">LATCH LOCKED</span>
          </div>

          <div class="card-body">
            <div class="latch-grid">
              <div class="latch-stat-card">
                <div class="label">日初權益基準</div>
                <div class="val num">1,000.00</div>
              </div>
              <div class="latch-stat-card">
                <div class="label">當前浮動損益</div>
                <div class="val num" id="latch-pnl-val" style="color:var(--color-success);">+18.42 (+1.8%)</div>
              </div>
              <div class="latch-stat-card">
                <div class="label">SOFT 禁增倉</div>
                <div class="val num" style="color:var(--color-warning);">-10% (900)</div>
              </div>
              <div class="latch-stat-card">
                <div class="label">HARD 硬熔斷</div>
                <div class="val num" style="color:var(--color-danger);">-20% (800)</div>
              </div>
            </div>

            <div class="gauge-track-box">
              <div class="gauge-bar">
                <div class="gauge-seg-hard"></div>
                <div class="gauge-seg-soft"></div>
                <div class="gauge-seg-normal"></div>
                <div class="gauge-seg-profit"></div>
              </div>
              <div class="gauge-needle" id="gauge-needle" style="left:76%;" data-label="目前: +1.84% (安全緩衝 118.42 USDT)"></div>
            </div>
            <div style="font-size:10px; color:var(--text-muted); margin-top:8px;">
              約束：Soft 鎖存當日不重設，僅限人工恢復；服務連線正常不等於風控正常。
            </div>
          </div>
        </div>

        <!-- Card 2: Active Bots Fleet (22%) -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>運行中機器人</span>
              <span class="badge badge-secondary" style="font-size:10px;">1 運行 · 1 需處理</span>
            </div>
            <a href="javascript:void(0)" style="font-size:11px; color:var(--color-accent); text-decoration:none;">管理 &rarr;</a>
          </div>

          <div class="card-body" style="padding:8px 10px;">
            <!-- Bot 1 -->
            <div class="bot-item-row">
              <div>
                <div style="font-weight:600; font-size:12px;">BTC 趨勢突破主線</div>
                <div style="font-size:10.5px; color:var(--text-muted);">BTC-USDT-SWAP · 多 0.20 BTC</div>
              </div>
              <div style="text-align:right;">
                <div class="num" style="font-weight:700; color:var(--color-success); font-size:12px;">+812.40</div>
                <span class="badge badge-success" style="font-size:9.5px;">RUNNING</span>
              </div>
            </div>

            <!-- Bot 2 -->
            <div class="bot-item-row" id="bot-eth-row">
              <div>
                <div style="font-weight:600; font-size:12px;">ETH 動態震盪網格</div>
                <div style="font-size:10.5px; color:var(--text-warning);">ETH-USDT-SWAP · 空 2.40 ETH</div>
              </div>
              <div style="text-align:right;">
                <div class="num" style="font-weight:700; color:var(--color-danger); font-size:12px;">-318.20</div>
                <span class="badge badge-warning" style="font-size:9.5px;">WARNING</span>
              </div>
            </div>

            <!-- Bot 3 -->
            <div class="bot-item-row" style="margin-bottom:0;">
              <div>
                <div style="font-weight:600; font-size:12px;">SOL 試驗波段 04</div>
                <div style="font-size:10.5px; color:var(--text-muted);">SOL-USDT-SWAP · 空倉 0</div>
              </div>
              <div style="text-align:right;">
                <div class="num" style="color:var(--text-muted); font-size:12px;">0.00</div>
                <span class="badge badge-secondary" style="font-size:9.5px;">STOPPED</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Card 3: Research Queue (22%) -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>近期研究任務</span>
              <span class="badge badge-secondary" style="font-size:10px;">回測/優化</span>
            </div>
            <a href="javascript:void(0)" style="font-size:11px; color:var(--color-accent); text-decoration:none;">回測庫 &rarr;</a>
          </div>

          <div class="card-body" style="padding:8px 10px;">
            <div class="research-item-row">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:600; font-size:12px;">ATR 動量突破 v1.1</span>
                <span class="badge badge-success" style="font-size:9.5px;">完成 100%</span>
              </div>
              <div style="font-size:10.5px; color:var(--text-secondary); margin-top:3px;">
                夏普 2.14 · 淨利 <span class="num" style="color:var(--color-success);">+36.84%</span> · 124 筆撮合
              </div>
            </div>

            <div class="research-item-row" style="margin-bottom:0;">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:600; font-size:12px;">參數網格優化 (48 迭代)</span>
                <span class="badge badge-accent" style="font-size:9.5px;">候選完成</span>
              </div>
              <div style="font-size:10.5px; color:var(--text-secondary); margin-top:3px;">
                最優解 Sharpe 2.38 · 提示: 需標本外檢驗
              </div>
            </div>
          </div>
        </div>

        <!-- Card 4: Yaozi Intel (22%) -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>Yaozi 市場情報快訊</span>
              <span class="badge badge-info" style="font-size:10px;">研究參考</span>
            </div>
            <span style="font-size:10px; color:var(--text-muted);">開發中</span>
          </div>

          <div class="card-body" style="padding:8px 10px;">
            <div class="yaozi-item-row">
              <div style="display:flex; justify-content:space-between; color:var(--color-warning); font-weight:600;">
                <span>[待確認: 費率偏離]</span>
                <span class="num" style="color:var(--text-muted);">10:45</span>
              </div>
              <div style="color:var(--text-primary); margin-top:2px;">OKX BTC 永續資金費率異常飆升警訊</div>
            </div>

            <div class="yaozi-item-row" style="margin-bottom:0;">
              <div style="display:flex; justify-content:space-between; color:var(--color-info); font-weight:600;">
                <span>[待確認: 鏈上異動]</span>
                <span class="num" style="color:var(--text-muted);">08:30</span>
              </div>
              <div style="color:var(--text-primary); margin-top:2px;">ETH 鏈上大額巨鯨集中轉入主要交易所</div>
            </div>
          </div>
        </div>

      </section>

    </div>
  </main>

  <script>
    // Toggle Technical Popover
    function togglePopover() {
      const el = document.getElementById("status-popover-menu");
      el.classList.toggle("open");
    }

    // Close popover when clicked outside
    document.addEventListener("click", function(e) {
      const trigger = document.querySelector(".status-popover-trigger");
      if (trigger && !trigger.contains(e.target)) {
        document.getElementById("status-popover-menu")?.classList.remove("open");
      }
    });

    // Toggle Incident Accordion
    function toggleIncident(el) {
      el.classList.toggle("open");
    }

    // Switch Time Range
    function setTimeRange(range, btn) {
      btn.parentElement.querySelectorAll("button").forEach(b => b.className = "btn");
      btn.className = "btn btn-primary";
    }

    // 5-State Interactive Scenario Switcher
    function switchState(state, btn) {
      document.querySelectorAll(".state-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const eqVal = document.getElementById("kpi-equity-val");
      const pnlVal = document.getElementById("kpi-pnl-val");
      const botsBadge = document.getElementById("kpi-bots-badge");
      const riskBadge = document.getElementById("kpi-risk-badge");
      const latchBadge = document.getElementById("latch-status-badge");
      const latchPnl = document.getElementById("latch-pnl-val");
      const needle = document.getElementById("gauge-needle");
      const popDot = document.getElementById("popover-dot");
      const popLabel = document.getElementById("popover-btn-label");

      if (state === 'NORMAL') {
        eqVal.innerHTML = '125,480.50 <span style="font-size:13px; font-weight:normal; color:var(--text-secondary);">USDT</span>';
        pnlVal.innerHTML = '+1,240.80 <span style="font-size:13px; font-weight:normal;">USDT</span>';
        pnlVal.style.color = "var(--color-success)";
        botsBadge.className = "badge badge-success";
        botsBadge.textContent = "1 運行中";
        riskBadge.className = "badge badge-success";
        riskBadge.textContent = "NORMAL";
        latchBadge.className = "badge badge-success";
        latchBadge.textContent = "安全運行中";
        latchPnl.innerHTML = "+18.42 (+1.8%)";
        latchPnl.style.color = "var(--color-success)";
        needle.style.left = "76%";
        needle.setAttribute("data-label", "目前: +1.84% (安全緩衝 118.42 USDT)");
        popDot.className = "badge-dot dot-success";
        popLabel.textContent = "底座連線正常 · 16ms";
      } else if (state === 'SOFT_LATCH') {
        eqVal.innerHTML = '121,900.50 <span style="font-size:13px; font-weight:normal; color:var(--text-secondary);">USDT</span>';
        pnlVal.innerHTML = '-3,580.00 <span style="font-size:13px; font-weight:normal;">USDT</span>';
        pnlVal.style.color = "var(--color-danger)";
        botsBadge.className = "badge badge-warning";
        botsBadge.textContent = "1 軟限受阻";
        riskBadge.className = "badge badge-warning";
        riskBadge.textContent = "SOFT LATCH";
        latchBadge.className = "badge badge-warning";
        latchBadge.textContent = "SOFT LATCH 鎖存";
        latchPnl.innerHTML = "-3,580.00 (-2.85%)";
        latchPnl.style.color = "var(--color-danger)";
        needle.style.left = "38%";
        needle.setAttribute("data-label", "最高回撤 -10.20% (軟限鎖存中 · 反彈至 -2.85%)");
        popDot.className = "badge-dot dot-warning";
        popLabel.textContent = "日損軟限鎖存中";
      } else if (state === 'RETAINED_409') {
        eqVal.innerHTML = '124,110.00 <span style="font-size:13px; font-weight:normal; color:var(--text-secondary);">USDT</span>';
        pnlVal.innerHTML = '-210.00 <span style="font-size:13px; font-weight:normal;">USDT</span>';
        pnlVal.style.color = "var(--color-warning)";
        botsBadge.className = "badge badge-danger";
        botsBadge.textContent = "409 獨佔鎖定";
        riskBadge.className = "badge badge-warning";
        riskBadge.textContent = "ATTENTION";
        latchBadge.className = "badge badge-warning";
        latchBadge.textContent = "部位未清";
        needle.style.left = "62%";
        needle.setAttribute("data-label", "Bot 手動停止但仍持倉 -1 張 (409 阻擋新案例)");
      } else if (state === 'EMPTY') {
        eqVal.innerHTML = '— <span style="font-size:13px; font-weight:normal; color:var(--text-secondary);">USDT</span>';
        pnlVal.innerHTML = '0.00 <span style="font-size:13px; font-weight:normal;">USDT</span>';
        pnlVal.style.color = "var(--text-muted)";
        botsBadge.className = "badge badge-secondary";
        botsBadge.textContent = "0 運行中";
        riskBadge.className = "badge badge-secondary";
        riskBadge.textContent = "STANDBY";
        latchBadge.className = "badge badge-secondary";
        latchBadge.textContent = "待命中";
        needle.style.left = "50%";
        needle.setAttribute("data-label", "尚未人工指派 Bot");
      } else if (state === 'RECOVERY') {
        eqVal.innerHTML = '125,480.50 <span style="font-size:13px; font-weight:normal; color:var(--text-secondary);">USDT</span>';
        pnlVal.innerHTML = 'UNKNOWN';
        pnlVal.style.color = "var(--color-danger)";
        botsBadge.className = "badge badge-danger";
        botsBadge.textContent = "RECOVERY";
        riskBadge.className = "badge badge-danger";
        riskBadge.textContent = "RECOVERY_REQUIRED";
        latchBadge.className = "badge badge-danger";
        latchBadge.textContent = "來源漂移 / 需人工核對";
        needle.style.left = "20%";
        needle.setAttribute("data-label", "服務異常: 需核對代碼與重啟本機服務");
        popDot.className = "badge-dot dot-danger";
        popLabel.textContent = "需人工檢查 · 409";
      }
    }
  </script>
</body>
</html>
"""

# ==============================================================================
# PROTOTYPE B: Trend-First Overview (趨勢主導的總覽)
# 大趨勢主導 (68% 走勢區 + 32% 待辦與焦點警報 Attention Hub) -> 下方呈現配置、Bot 隊列與研究
# ==============================================================================
HTML_B = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>catOS · 戰情總覽 Prototype B (趨勢主導總覽 Trend-First Overview)</title>
  
  <!-- Fonts: Inter, JetBrains Mono, Noto Sans TC -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Noto+Sans+TC:wght@400;500;600;700&display=swap" rel="stylesheet">

  <style>
    :root {
      --bg-base: #080a0d;
      --bg-sidebar: #0a0d12;
      --bg-surface: #0e1218;
      --bg-surface-subtle: #121720;
      --bg-surface-hover: #181e2a;
      --bg-surface-active: #1f2736;
      --bg-input: #080b0f;
      --bg-code: #05070a;

      --border-color: #1f2633;
      --border-subtle: #151a24;
      --border-focus: #dcb347;

      --text-primary: #e6edf3;
      --text-secondary: #8b949e;
      --text-muted: #57606a;
      --text-inverse: #080a0d;

      --color-accent: #dcb347;
      --color-accent-hover: #e8c25b;
      --color-accent-subtle: rgba(220, 179, 71, 0.10);
      --color-accent-border: rgba(220, 179, 71, 0.35);

      --color-success: #2ea043;
      --color-success-subtle: rgba(46, 160, 67, 0.12);
      --color-success-border: rgba(46, 160, 67, 0.40);

      --color-warning: #d29922;
      --color-warning-subtle: rgba(210, 153, 34, 0.12);
      --color-warning-border: rgba(210, 153, 34, 0.40);

      --color-danger: #f85149;
      --color-danger-subtle: rgba(248, 81, 73, 0.12);
      --color-danger-border: rgba(248, 81, 73, 0.40);

      --color-info: #58a6ff;
      --color-info-subtle: rgba(88, 166, 255, 0.12);
      --color-info-border: rgba(88, 166, 255, 0.40);

      --font-sans: 'Inter', 'Noto Sans TC', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', SFMono-Regular, Menlo, Monaco, Consolas, monospace;

      --radius-sm: 2px;
      --radius-md: 4px;
      --radius-lg: 6px;

      --sidebar-width: 200px;
      --header-height: 48px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      background-color: var(--bg-base);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: 13px;
      line-height: 1.45;
      height: 100vh;
      overflow: hidden;
      display: flex;
    }

    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: var(--bg-base); }
    ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: var(--radius-sm); }
    ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

    /* Sidebar */
    .app-sidebar {
      width: var(--sidebar-width);
      background-color: var(--bg-sidebar);
      border-right: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      height: 100vh;
    }

    .sidebar-brand {
      height: var(--header-height);
      padding: 0 16px;
      display: flex;
      align-items: center;
      gap: 8px;
      border-bottom: 1px solid var(--border-subtle);
    }

    .brand-logo-badge {
      width: 20px;
      height: 20px;
      background: var(--color-accent-subtle);
      border: 1px solid var(--color-accent-border);
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: var(--font-mono);
      font-size: 11px;
      font-weight: 700;
      color: var(--color-accent);
    }

    .brand-title {
      font-size: 14px;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: var(--text-primary);
    }

    .brand-version {
      font-family: var(--font-mono);
      font-size: 10px;
      color: var(--text-muted);
      border: 1px solid var(--border-color);
      padding: 1px 4px;
      border-radius: var(--radius-sm);
      margin-left: auto;
    }

    .sidebar-nav {
      flex: 1;
      padding: 12px 8px;
      display: flex;
      flex-direction: column;
      gap: 2px;
      overflow-y: auto;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border-radius: var(--radius-md);
      color: var(--text-secondary);
      text-decoration: none;
      font-size: 12.5px;
      font-weight: 500;
      cursor: pointer;
      transition: background 0.15s ease, color 0.15s ease;
    }

    .nav-item:hover { background: var(--bg-surface-hover); color: var(--text-primary); }
    .nav-item.active { background: var(--color-accent-subtle); color: var(--color-accent); border: 1px solid var(--color-accent-border); font-weight: 600; }
    .nav-icon { width: 15px; height: 15px; stroke-width: 2; }

    /* Main Viewport */
    .app-main {
      flex: 1;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      min-width: 0;
    }

    /* Topbar */
    .app-header {
      height: var(--header-height);
      background-color: var(--bg-surface);
      border-bottom: 1px solid var(--border-color);
      padding: 0 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      position: relative;
    }

    .header-breadcrumb {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
    }

    .breadcrumb-title { font-weight: 700; color: var(--text-primary); }
    .badge-prototype {
      background: var(--color-accent-subtle);
      border: 1px solid var(--color-accent-border);
      color: var(--color-accent);
      font-size: 10.5px;
      font-weight: 600;
      padding: 2px 6px;
      border-radius: var(--radius-sm);
    }

    .header-controls {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .state-switcher {
      display: flex;
      align-items: center;
      gap: 4px;
      background: var(--bg-base);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      padding: 2px;
    }

    .state-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      font-size: 11px;
      padding: 3px 8px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-weight: 500;
      transition: all 0.15s ease;
    }

    .state-btn.active {
      background: var(--bg-surface-active);
      color: var(--text-primary);
      font-weight: 600;
    }

    /* Popover */
    .status-popover-trigger { position: relative; }
    .service-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-color);
      background: var(--bg-surface-subtle);
      cursor: pointer;
      font-size: 11px;
      color: var(--text-secondary);
    }
    .service-pill:hover { border-color: var(--color-accent); color: var(--text-primary); }

    .status-popover-menu {
      display: none;
      position: absolute;
      top: calc(100% + 8px);
      right: 0;
      width: 320px;
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.7);
      padding: 12px;
      z-index: 999;
    }
    .status-popover-menu.open { display: block; }

    /* Canvas Scroll */
    .trend-canvas {
      flex: 1;
      overflow-y: auto;
      padding: 14px 18px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    /* Cards */
    .card {
      background-color: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      display: flex;
      flex-direction: column;
      position: relative;
    }

    .card-header {
      padding: 9px 14px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 38px;
    }

    .card-title {
      font-size: 13px;
      font-weight: 600;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .card-body { padding: 14px; }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 6px;
      font-size: 10.5px;
      font-weight: 600;
      border-radius: var(--radius-sm);
    }
    .badge-success { background: var(--color-success-subtle); color: var(--color-success); border: 1px solid var(--color-success-border); }
    .badge-warning { background: var(--color-warning-subtle); color: var(--color-warning); border: 1px solid var(--color-warning-border); }
    .badge-danger { background: var(--color-danger-subtle); color: var(--color-danger); border: 1px solid var(--color-danger-border); }
    .badge-info { background: var(--color-info-subtle); color: var(--color-info); border: 1px solid var(--color-info-border); }
    .badge-secondary { background: var(--bg-surface-subtle); color: var(--text-secondary); border: 1px solid var(--border-color); }
    .badge-accent { background: var(--color-accent-subtle); color: var(--color-accent); border: 1px solid var(--color-accent-border); }

    .badge-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
    .dot-success { background: var(--color-success); }
    .dot-warning { background: var(--color-warning); }
    .dot-danger { background: var(--color-danger); }

    .btn {
      height: 24px;
      padding: 0 8px;
      font-size: 11px;
      font-weight: 500;
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-color);
      background: var(--bg-surface-subtle);
      color: var(--text-primary);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      text-decoration: none;
    }
    .btn:hover { background: var(--bg-surface-hover); }
    .btn-primary { background: var(--color-accent); border-color: var(--color-accent); color: var(--text-inverse); font-weight: 600; }

    .num { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

    /* ==========================================================================
       PROTOTYPE B TOP STAGE: Large Trend Hero (68%) + Attention Hub (32%)
       ========================================================================== */
    .top-stage-grid {
      display: grid;
      grid-template-columns: 1.45fr 0.85fr;
      gap: 12px;
      min-height: 340px;
    }

    /* Trend Stage Card */
    .trend-hero-card {
      display: flex;
      flex-direction: column;
    }

    .trend-stats-bar {
      display: flex;
      align-items: center;
      gap: 24px;
      padding: 10px 14px;
      background: var(--bg-surface-subtle);
      border-bottom: 1px solid var(--border-subtle);
    }

    .trend-stat-unit .label {
      font-size: 11px;
      color: var(--text-muted);
      margin-bottom: 2px;
    }

    .trend-stat-unit .val {
      font-size: 20px;
      font-weight: 700;
      color: var(--text-primary);
    }

    .trend-svg-area {
      flex: 1;
      min-height: 200px;
      position: relative;
      padding: 10px 14px 4px 14px;
    }

    /* Attention Hub Card (需處理事項與焦點監控) */
    .attention-hub-card {
      border-top: 3px solid var(--color-warning);
      display: flex;
      flex-direction: column;
    }

    .action-alert-banner {
      background: var(--color-warning-subtle);
      border: 1px solid var(--color-warning-border);
      border-radius: var(--radius-sm);
      padding: 8px 10px;
      margin-bottom: 10px;
      font-size: 12px;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .attention-item {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 8px 10px;
      border-radius: var(--radius-sm);
      background: var(--bg-surface-subtle);
      border: 1px solid var(--border-subtle);
      margin-bottom: 6px;
      font-size: 12px;
    }

    /* Mini Latch in Attention Hub */
    .mini-latch-bar-box {
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid var(--border-subtle);
    }

    /* ==========================================================================
       PROTOTYPE B BOTTOM STAGE: Fleet (38%) + Allocation (32%) + Research (30%)
       ========================================================================== */
    .bottom-stage-grid {
      display: grid;
      grid-template-columns: 1.15fr 0.95fr 0.90fr;
      gap: 12px;
    }

    /* Table in Fleet */
    .fleet-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }

    .fleet-table th {
      text-align: left;
      padding: 6px 8px;
      color: var(--text-muted);
      font-size: 11px;
      border-bottom: 1px solid var(--border-color);
      font-weight: 500;
    }

    .fleet-table td {
      padding: 8px 8px;
      border-bottom: 1px solid var(--border-subtle);
      vertical-align: middle;
    }

    /* Responsive */
    @media (max-width: 1200px) {
      .top-stage-grid { grid-template-columns: 1fr; }
      .bottom-stage-grid { grid-template-columns: 1fr 1fr; }
    }

    @media (max-width: 768px) {
      body { flex-direction: column; height: auto; overflow: auto; }
      .app-sidebar { width: 100%; height: auto; }
      .trend-canvas { overflow: visible; }
      .bottom-stage-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

  <!-- 1. Attached Sidebar -->
  <aside class="app-sidebar">
    <div class="sidebar-brand">
      <div class="brand-logo-badge">C</div>
      <div class="brand-title">catOS</div>
      <div class="brand-version">v1.2</div>
    </div>

    <nav class="sidebar-nav">
      <div class="nav-item active">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
        <span>戰情總覽</span>
      </div>
      <div class="nav-item">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        <span>策略中心</span>
      </div>
      <div class="nav-item">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="15" x2="15" y2="15"/></svg>
        <span>機器人管理</span>
      </div>
      <div class="nav-item">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        <span>風險控管</span>
      </div>
      <div class="nav-item">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/></svg>
        <span>系統日誌</span>
      </div>
      <div class="nav-item">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        <span>偏好設定</span>
      </div>
    </nav>
  </aside>

  <!-- 2. Main Viewport -->
  <main class="app-main">
    
    <!-- Topbar -->
    <header class="app-header">
      <div class="header-breadcrumb">
        <span class="breadcrumb-title">戰情總覽</span>
        <span class="badge-prototype">產品原型 · 示意資料</span>
        <span class="badge badge-secondary" style="font-size:10.5px;">PROTOTYPE B · 趨勢主導總覽</span>
      </div>

      <div class="header-controls">
        <div class="state-switcher">
          <button class="state-btn active" onclick="switchState('NORMAL', this)">正常連線</button>
          <button class="state-btn" onclick="switchState('SOFT_LATCH', this)">日損軟限</button>
          <button class="state-btn" onclick="switchState('RETAINED_409', this)">持倉停止 (409)</button>
          <button class="state-btn" onclick="switchState('EMPTY', this)">空資料</button>
          <button class="state-btn" onclick="switchState('RECOVERY', this)">服務異常</button>
        </div>

        <div class="status-popover-trigger">
          <div class="service-pill" onclick="togglePopover()">
            <span class="badge-dot dot-success" id="popover-dot"></span>
            <span id="popover-btn-label">底座連線正常 · 16ms</span>
            <span style="font-size:9px;">▾</span>
          </div>

          <div class="status-popover-menu" id="status-popover-menu">
            <div class="popover-header">
              <span>底座核心遙測狀態</span>
              <span class="badge badge-accent">LOCAL SIM / PASS</span>
            </div>
            <div class="popover-item"><span class="label">Supervisor PID</span><span class="val" style="color:var(--color-success);">4821 (ONLINE)</span></div>
            <div class="popover-item"><span class="label">WS 延遲</span><span class="val">16ms</span></div>
            <div class="popover-item"><span class="label">OKX 頻率</span><span class="val">58 / 60</span></div>
            <div class="popover-item"><span class="label">Invariant Tag</span><span class="val">41cb53c54d6dABDE</span></div>
            <div class="popover-item"><span class="label">保證金模式</span><span class="val">Cross Net (USDT-M)</span></div>
            <div class="popover-item"><span class="label">運算核心</span><span class="val">Decimal Only</span></div>
          </div>
        </div>
      </div>
    </header>

    <!-- Scrollable Trend Canvas -->
    <div class="trend-canvas">
      
      <!-- ================= TOP STAGE: Trend Hero (68%) + Attention Hub (32%) ================= -->
      <section class="top-stage-grid">
        
        <!-- Left: Trend Hero Card -->
        <div class="card trend-hero-card">
          <div class="card-header">
            <div class="card-title">
              <span>帳戶權益與成果趨勢 (EQUITY & RESULT TREND)</span>
            </div>
            <div class="card-actions">
              <button class="btn" onclick="setTimeRange('7D', this)">7D</button>
              <button class="btn btn-primary" onclick="setTimeRange('30D', this)">30D</button>
              <button class="btn" onclick="setTimeRange('90D', this)">90D</button>
            </div>
          </div>

          <!-- Top Stats Bar -->
          <div class="trend-stats-bar">
            <div class="trend-stat-unit">
              <div class="label">總權益淨值 (USDT)</div>
              <div class="val num" id="hero-equity-val">125,480.50</div>
            </div>
            <div class="trend-stat-unit">
              <div class="label">今日累計損益 (00:00起)</div>
              <div class="val num" id="hero-pnl-val" style="color:var(--color-success);">+1,240.80 (+1.00%)</div>
            </div>
            <div class="trend-stat-unit">
              <div class="label">有效槓桿倍數</div>
              <div class="val num" id="hero-leverage-val">1.85x <span style="font-size:12px; color:var(--text-muted); font-weight:normal;">/ 上限 3.00x</span></div>
            </div>
            <div class="trend-stat-unit">
              <div class="label">風控基準狀態</div>
              <div style="margin-top:2px;"><span class="badge badge-success" id="hero-risk-badge">NORMAL</span></div>
            </div>
          </div>

          <!-- Large Curve SVG -->
          <div class="trend-svg-area">
            <svg width="100%" height="100%" viewBox="0 0 750 200" preserveAspectRatio="none">
              <defs>
                <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#dcb347" stop-opacity="0.30"/>
                  <stop offset="100%" stop-color="#dcb347" stop-opacity="0.0"/>
                </linearGradient>
              </defs>
              <line x1="0" y1="40" x2="750" y2="40" stroke="#151a24" stroke-dasharray="3,3"/>
              <line x1="0" y1="90" x2="750" y2="90" stroke="#151a24" stroke-dasharray="3,3"/>
              <line x1="0" y1="140" x2="750" y2="140" stroke="#151a24" stroke-dasharray="3,3"/>

              <polygon points="0,160 80,152 180,146 290,150 400,125 500,108 610,65 690,44 750,35 750,200 0,200" fill="url(#trendGradient)"/>
              <polyline fill="none" stroke="#dcb347" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
                        points="0,160 80,152 180,146 290,150 400,125 500,108 610,65 690,44 750,35"/>
              <circle cx="750" cy="35" r="4.5" fill="#ffffff" stroke="#dcb347" stroke-width="2"/>

              <text x="10" y="34" fill="#57606a" font-size="10.5" font-family="JetBrains Mono">126,000</text>
              <text x="10" y="84" fill="#57606a" font-size="10.5" font-family="JetBrains Mono">122,000</text>
              <text x="10" y="134" fill="#57606a" font-size="10.5" font-family="JetBrains Mono">118,000</text>

              <text x="10" y="190" fill="#57606a" font-size="10.5" font-family="JetBrains Mono">09-01</text>
              <text x="240" y="190" fill="#57606a" font-size="10.5" font-family="JetBrains Mono">09-10</text>
              <text x="480" y="190" fill="#57606a" font-size="10.5" font-family="JetBrains Mono">09-20</text>
              <text x="680" y="190" fill="#57606a" font-size="10.5" font-family="JetBrains Mono">09-30</text>
            </svg>
          </div>

          <div style="padding:8px 14px; font-size:11px; color:var(--text-muted); border-top:1px solid var(--border-subtle); display:flex; justify-content:space-between;">
            <span>撮合基準：離線歷史模擬數據 · 滑價損耗模型啟用</span>
            <span>[設計提案: 待接即時帳戶權益時序]</span>
          </div>
        </div>

        <!-- Right: Attention Hub Card (32%) -->
        <div class="card attention-hub-card">
          <div class="card-header">
            <div class="card-title">
              <span>需處理事項與焦點監控</span>
              <span class="badge badge-warning" id="attention-count-badge">1 項待辦</span>
            </div>
            <span style="font-size:11px; color:var(--text-muted);">ATTENTION HUB</span>
          </div>

          <div class="card-body" style="padding:10px 12px; display:flex; flex-direction:column; justify-content:space-between;">
            <div>
              <!-- Action Alert Banner -->
              <div class="action-alert-banner" id="hub-action-banner">
                <div>
                  <strong>ETH 震盪網格 Alpha 03</strong>
                  <div style="font-size:11px; margin-top:2px;">價格逼近網格上限 $2,780，需補足可用保證金</div>
                </div>
                <button class="btn btn-primary" style="height:22px; font-size:10.5px;">處理</button>
              </div>

              <!-- Stream items -->
              <div class="attention-item">
                <span class="badge badge-warning" style="font-size:9.5px;">11:10</span>
                <div>
                  <div style="font-weight:600;">ETH 撮合滑價偏高 (2.8 bps)</div>
                  <div style="font-size:11px; color:var(--text-muted);">市況瞬時流動性枯竭，策略維持觀察</div>
                </div>
              </div>

              <div class="attention-item">
                <span class="badge badge-info" style="font-size:9.5px;">10:24</span>
                <div>
                  <div style="font-weight:600;">新策略草稿已由 Agent 生成</div>
                  <div style="font-size:11px; color:var(--text-muted);">ATR-v1.2 待策略中心人工安全簽核</div>
                </div>
              </div>
            </div>

            <!-- Mini Latch Status inside Attention Hub -->
            <div class="mini-latch-bar-box">
              <div style="display:flex; justify-content:space-between; align-items:center; font-size:11.5px; margin-bottom:6px;">
                <span style="font-weight:600;">日損鎖存安全緩衝</span>
                <span class="badge badge-success" id="hub-latch-badge">安全緩衝 118.42 USDT</span>
              </div>
              <div style="height:6px; background:var(--bg-base); border-radius:3px; overflow:hidden; display:flex; position:relative;">
                <div style="width:20%; background:#f85149;"></div>
                <div style="width:15%; background:#d29922;"></div>
                <div style="width:35%; background:#30363d;"></div>
                <div style="width:30%; background:#2ea043;"></div>
              </div>
              <div style="display:flex; justify-content:space-between; font-size:10px; font-family:var(--font-mono); color:var(--text-muted); margin-top:4px;">
                <span>Hard -20%</span>
                <span>Soft -10%</span>
                <span>基準 0.0%</span>
                <span style="color:var(--color-success);" id="hub-latch-text">目前 +1.84%</span>
              </div>
            </div>

          </div>
        </div>

      </section>

      <!-- ================= BOTTOM STAGE: Fleet (38%) + Allocation (32%) + Research (30%) ================= -->
      <section class="bottom-stage-grid">
        
        <!-- Left: Fleet Manager (38%) -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>機器人隊列與部位監控 (FLEET BINDINGS)</span>
              <span class="badge badge-secondary" id="fleet-count-badge">3 部署</span>
            </div>
            <a href="javascript:void(0)" style="font-size:11px; color:var(--color-accent); text-decoration:none;">前往機器人管理 &rarr;</a>
          </div>

          <div class="card-body" style="padding:0;">
            <table class="fleet-table">
              <thead>
                <tr>
                  <th>機器人名稱</th>
                  <th>合約 / 部位方向</th>
                  <th>今日損益</th>
                  <th>狀態 / 限制</th>
                  <th style="text-align:right;">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>
                    <div style="font-weight:600;">BTC 趨勢突破主線</div>
                    <div style="font-size:10px; font-family:var(--font-mono); color:var(--text-muted);">strat-atr-v1</div>
                  </td>
                  <td>BTC-USDT-SWAP <br><span class="badge badge-success" style="font-size:9.5px;">多 0.20 BTC</span></td>
                  <td class="num" style="font-weight:600; color:var(--color-success);">+812.40</td>
                  <td><span class="badge badge-success">RUNNING</span></td>
                  <td style="text-align:right;"><button class="btn">檢視</button></td>
                </tr>
                <tr id="fleet-eth-row">
                  <td>
                    <div style="font-weight:600;">ETH 動態震盪網格</div>
                    <div style="font-size:10px; font-family:var(--font-mono); color:var(--text-muted);">strat-grid-v2</div>
                  </td>
                  <td>ETH-USDT-SWAP <br><span class="badge badge-warning" style="font-size:9.5px;">空 2.40 ETH</span></td>
                  <td class="num" style="font-weight:600; color:var(--color-danger);">-318.20</td>
                  <td><span class="badge badge-warning">WARNING</span></td>
                  <td style="text-align:right;"><button class="btn btn-primary" style="height:20px;">處理</button></td>
                </tr>
                <tr>
                  <td>
                    <div style="font-weight:600;">SOL 試驗波段 04</div>
                    <div style="font-size:10px; font-family:var(--font-mono); color:var(--text-muted);">strat-counter-v3</div>
                  </td>
                  <td>SOL-USDT-SWAP <br><span class="badge badge-secondary" style="font-size:9.5px;">空倉 0</span></td>
                  <td class="num" style="color:var(--text-muted);">0.00</td>
                  <td><span class="badge badge-secondary">STOPPED</span></td>
                  <td style="text-align:right;"><button class="btn">啟動</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Middle: Margin Allocation (32%) -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>保證金與曝險配置 (ALLOCATION)</span>
            </div>
            <span class="badge badge-secondary" style="font-size:10px;">名義: 1,420.50</span>
          </div>

          <div class="card-body" style="padding:10px 14px;">
            <div style="display:flex; flex-direction:column; gap:8px;">
              <div>
                <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:3px;">
                  <span>BTC 永續持倉保證金</span>
                  <span class="num" style="font-weight:600;">320.00 USDT (32%)</span>
                </div>
                <div style="height:5px; background:var(--bg-base); border-radius:2px; overflow:hidden;">
                  <div style="width:32%; height:100%; background:#2ea043;"></div>
                </div>
              </div>

              <div>
                <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:3px;">
                  <span>委託在途凍結保證金</span>
                  <span class="num" style="font-weight:600;">150.00 USDT (15%)</span>
                </div>
                <div style="height:5px; background:var(--bg-base); border-radius:2px; overflow:hidden;">
                  <div style="width:15%; height:100%; background:#58a6ff;"></div>
                </div>
              </div>

              <div>
                <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:3px;">
                  <span>未佔用可用保證金</span>
                  <span class="num" style="font-weight:600;">430.00 USDT (43%)</span>
                </div>
                <div style="height:5px; background:var(--bg-base); border-radius:2px; overflow:hidden;">
                  <div style="width:43%; height:100%; background:#dcb347;"></div>
                </div>
              </div>

              <div>
                <div style="display:flex; justify-content:space-between; font-size:11px; margin-bottom:3px;">
                  <span>風控緩衝預留</span>
                  <span class="num" style="font-weight:600;">100.00 USDT (10%)</span>
                </div>
                <div style="height:5px; background:var(--bg-base); border-radius:2px; overflow:hidden;">
                  <div style="width:10%; height:100%; background:#a371f7;"></div>
                </div>
              </div>
            </div>

            <div style="font-size:10.5px; color:var(--text-muted); margin-top:10px; border-top:1px solid var(--border-subtle); padding-top:4px;">
              [設計提案: 依據有效槓桿 3.0x 與單幣 50% 曝險預算計算]
            </div>
          </div>
        </div>

        <!-- Right: Research & Yaozi Tabs (30%) -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>研究成果與市場情報</span>
            </div>
            <div class="card-actions">
              <span class="badge badge-accent" style="font-size:10px;">回測 / INTEL</span>
            </div>
          </div>

          <div class="card-body" style="padding:10px 12px; display:flex; flex-direction:column; gap:8px;">
            <div style="padding:6px 8px; border-radius:var(--radius-sm); background:var(--bg-surface-subtle); border:1px solid var(--border-subtle);">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:600; font-size:12px;">ATR 動量突破 v1.1 回測</span>
                <span class="badge badge-success" style="font-size:9.5px;">完成 100%</span>
              </div>
              <div style="font-size:11px; color:var(--text-secondary); margin-top:2px;">
                夏普 2.14 · 淨利 <span class="num" style="color:var(--color-success);">+36.84%</span> · 124 筆撮合
              </div>
            </div>

            <div style="padding:6px 8px; border-radius:var(--radius-sm); background:var(--bg-surface-subtle); border:1px solid var(--border-subtle);">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-weight:600; font-size:12px;">網格參數優化 (48 迭代)</span>
                <span class="badge badge-accent" style="font-size:9.5px;">候選完成</span>
              </div>
              <div style="font-size:11px; color:var(--text-secondary); margin-top:2px;">
                最優解 Sharpe 2.38 · 提示: 需標本外檢驗
              </div>
            </div>

            <div style="padding:6px 8px; border-radius:var(--radius-sm); background:var(--bg-surface-subtle); border:1px solid var(--border-subtle);">
              <div style="display:flex; justify-content:space-between; color:var(--color-warning); font-size:11px; font-weight:600;">
                <span>[Yaozi 警訊: 費率偏離]</span>
                <span class="num" style="color:var(--text-muted);">10:45</span>
              </div>
              <div style="font-size:11.5px; color:var(--text-primary); margin-top:2px;">OKX BTC 永續資金費率異常飆升警訊</div>
            </div>
          </div>
        </div>

      </section>

    </div>
  </main>

  <script>
    function togglePopover() {
      document.getElementById("status-popover-menu").classList.toggle("open");
    }

    document.addEventListener("click", function(e) {
      const trigger = document.querySelector(".status-popover-trigger");
      if (trigger && !trigger.contains(e.target)) {
        document.getElementById("status-popover-menu")?.classList.remove("open");
      }
    });

    function setTimeRange(range, btn) {
      btn.parentElement.querySelectorAll("button").forEach(b => b.className = "btn");
      btn.className = "btn btn-primary";
    }

    function switchState(state, btn) {
      document.querySelectorAll(".state-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      const eqVal = document.getElementById("hero-equity-val");
      const pnlVal = document.getElementById("hero-pnl-val");
      const riskBadge = document.getElementById("hero-risk-badge");
      const popDot = document.getElementById("popover-dot");
      const popLabel = document.getElementById("popover-btn-label");
      const hubAction = document.getElementById("hub-action-banner");
      const hubBadge = document.getElementById("attention-count-badge");

      if (state === 'NORMAL') {
        eqVal.textContent = "125,480.50";
        pnlVal.textContent = "+1,240.80 (+1.00%)";
        pnlVal.style.color = "var(--color-success)";
        riskBadge.className = "badge badge-success";
        riskBadge.textContent = "NORMAL";
        popDot.className = "badge-dot dot-success";
        popLabel.textContent = "底座連線正常 · 16ms";
        hubAction.style.display = "flex";
        hubBadge.textContent = "1 項待辦";
      } else if (state === 'SOFT_LATCH') {
        eqVal.textContent = "121,900.50";
        pnlVal.textContent = "-3,580.00 (-2.85%)";
        pnlVal.style.color = "var(--color-danger)";
        riskBadge.className = "badge badge-warning";
        riskBadge.textContent = "SOFT LATCH";
        popDot.className = "badge-dot dot-warning";
        popLabel.textContent = "日損軟限鎖存中";
        hubBadge.textContent = "2 項待辦";
      } else if (state === 'RETAINED_409') {
        eqVal.textContent = "124,110.00";
        pnlVal.textContent = "-210.00 (-0.17%)";
        pnlVal.style.color = "var(--color-warning)";
        riskBadge.className = "badge badge-warning";
        riskBadge.textContent = "ATTENTION";
        hubBadge.textContent = "409 獨佔鎖定";
      } else if (state === 'EMPTY') {
        eqVal.textContent = "—";
        pnlVal.textContent = "0.00";
        pnlVal.style.color = "var(--text-muted)";
        riskBadge.className = "badge badge-secondary";
        riskBadge.textContent = "STANDBY";
        hubBadge.textContent = "無待辦";
        hubAction.style.display = "none";
      } else if (state === 'RECOVERY') {
        eqVal.textContent = "125,480.50";
        pnlVal.textContent = "UNKNOWN";
        pnlVal.style.color = "var(--color-danger)";
        riskBadge.className = "badge badge-danger";
        riskBadge.textContent = "RECOVERY_REQUIRED";
        popDot.className = "badge-dot dot-danger";
        popLabel.textContent = "需人工檢查 · 409";
        hubBadge.textContent = "需要重啟";
      }
    }
  </script>
</body>
</html>
"""

# Output locations
out_pairs = [
    (r"C:\Users\user\Desktop\catOS-Frontend-Final\prototypes\dashboard-prototype-a.html", HTML_A),
    (r"c:\Users\user\Desktop\CatOS_Astra\outputs\dashboard-prototype-a.html", HTML_A),
    (r"C:\Users\user\Desktop\catOS-Frontend-Final\prototypes\dashboard-prototype-b.html", HTML_B),
    (r"c:\Users\user\Desktop\CatOS_Astra\outputs\dashboard-prototype-b.html", HTML_B)
]

for filepath, content in out_pairs:
    p = pathlib.Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content.encode('utf-8'))
    print(f"Written: {filepath} ({len(content)} bytes)")

print("All Dashboard prototypes created successfully.")
