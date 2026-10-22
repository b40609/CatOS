# -*- coding: utf-8 -*-
"""
create_prototype_b.py - Generates Strategy Center Prototype B (Strategy Control Center)
Layout: Control Center (Top Overview Table, Bottom Full Detail Sections)
Visual Reference: Tabler Design System (Cards, Tables, Badges, Activity, Forms)
"""
import pathlib
import shutil

CONTENT_B = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>catOS - Strategy Control Center (Prototype B)</title>
  
  <!-- Fonts: Inter & JetBrains Mono -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

  <style>
    /* ==========================================================================
       catOS Semantic Design Tokens (Tabler Reference, Fully Customizable)
       ========================================================================== */
    :root {
      /* Background Tokens */
      --bg-app: #080a0d;
      --bg-sidebar: #0a0d12;
      --bg-surface: #0e1218;
      --bg-surface-subtle: #121720;
      --bg-surface-hover: #181e2a;
      --bg-surface-active: #1f2736;
      --bg-code: #05070a;
      --bg-input: #080b0f;

      /* Border Tokens */
      --border-color: #1f2633;
      --border-subtle: #151a24;
      --border-focus: #dcb347;

      /* Text Tokens */
      --text-primary: #e6edf3;
      --text-secondary: #8b949e;
      --text-muted: #57606a;
      --text-inverse: #080a0d;

      /* Accent & Brand Tokens (catOS Obsidian Gold Default) */
      --color-accent: #dcb347;
      --color-accent-hover: #e8c25b;
      --color-accent-subtle: rgba(220, 179, 71, 0.10);
      --color-accent-border: rgba(220, 179, 71, 0.35);

      /* Semantic Status Tokens (Tabler Spec) */
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

      /* Typography Tokens */
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      
      --font-size-xs: 11px;
      --font-size-sm: 12px;
      --font-size-base: 13px;
      --font-size-md: 14px;
      --font-size-lg: 16px;
      --font-size-xl: 18px;

      /* Spacing Tokens */
      --space-1: 4px;
      --space-2: 8px;
      --space-3: 12px;
      --space-4: 16px;
      --space-5: 20px;
      --space-6: 24px;

      /* Radius Tokens (Strict Tabler Low-Radius) */
      --radius-sm: 2px;
      --radius-md: 4px;
      --radius-lg: 6px;

      /* Dimensions */
      --sidebar-width: 210px;
      --header-height: 44px;
    }

    /* Reset & Base */
    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-app);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: var(--font-size-base);
      line-height: 1.45;
      height: 100vh;
      overflow: hidden;
      display: flex;
    }

    /* Scrollbars */
    ::-webkit-scrollbar {
      width: 6px;
      height: 6px;
    }
    ::-webkit-scrollbar-track {
      background: var(--bg-app);
    }
    ::-webkit-scrollbar-thumb {
      background: var(--border-color);
      border-radius: var(--radius-sm);
    }
    ::-webkit-scrollbar-thumb:hover {
      background: var(--text-muted);
    }

    /* ==========================================================================
       Attached Sidebar (Tabler-style)
       ========================================================================== */
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
      padding: 0 var(--space-4);
      display: flex;
      align-items: center;
      gap: var(--space-2);
      border-bottom: 1px solid var(--border-subtle);
    }

    .brand-logo-badge {
      width: 18px;
      height: 18px;
      background: var(--color-accent-subtle);
      border: 1px solid var(--color-accent-border);
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 700;
      color: var(--color-accent);
    }

    .brand-title {
      font-size: var(--font-size-md);
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
      padding: var(--space-3) var(--space-2);
      display: flex;
      flex-direction: column;
      gap: 2px;
      overflow-y: auto;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: var(--space-3);
      padding: var(--space-2) var(--space-3);
      border-radius: var(--radius-md);
      color: var(--text-secondary);
      text-decoration: none;
      font-size: var(--font-size-sm);
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

    .nav-icon {
      width: 15px;
      height: 15px;
      stroke-width: 2;
    }

    .sidebar-footer {
      padding: var(--space-3) var(--space-4);
      border-top: 1px solid var(--border-subtle);
      font-size: var(--font-size-xs);
      color: var(--text-muted);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    /* ==========================================================================
       Main App Layout (Control Center Viewport)
       ========================================================================== */
    .app-main {
      flex: 1;
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      min-width: 0;
    }

    .app-header {
      height: var(--header-height);
      background-color: var(--bg-surface);
      border-bottom: 1px solid var(--border-color);
      padding: 0 var(--space-5);
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
    }

    .header-breadcrumb {
      display: flex;
      align-items: center;
      gap: var(--space-2);
      font-size: var(--font-size-sm);
    }

    .breadcrumb-root {
      color: var(--text-muted);
      font-weight: 500;
    }

    .breadcrumb-sep {
      color: var(--text-muted);
    }

    .breadcrumb-current {
      color: var(--text-primary);
      font-weight: 600;
    }

    .header-badge-group {
      display: flex;
      align-items: center;
      gap: var(--space-3);
    }

    /* Control Center Scrollable Container */
    .control-center-scroll {
      flex: 1;
      overflow-y: auto;
      padding: var(--space-5);
      display: flex;
      flex-direction: column;
      gap: var(--space-5);
    }

    /* ==========================================================================
       Tabler Component Library Styles (Cards, Tables, Badges, Buttons, Forms)
       ========================================================================== */
    
    /* Card */
    .card {
      background-color: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      display: flex;
      flex-direction: column;
      position: relative;
    }

    .card-header {
      padding: var(--space-3) var(--space-4);
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 42px;
      gap: var(--space-3);
    }

    .card-title {
      font-size: var(--font-size-base);
      font-weight: 600;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: var(--space-2);
      letter-spacing: -0.01em;
    }

    .card-actions {
      display: flex;
      align-items: center;
      gap: var(--space-2);
    }

    .card-body {
      padding: var(--space-4);
    }

    .card-footer {
      padding: var(--space-3) var(--space-4);
      border-top: 1px solid var(--border-subtle);
      background-color: var(--bg-surface-subtle);
      font-size: var(--font-size-xs);
      color: var(--text-muted);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    /* Badges */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 600;
      line-height: 1.2;
      border-radius: var(--radius-sm);
      letter-spacing: 0.02em;
    }

    .badge-secondary {
      background: var(--bg-surface-subtle);
      color: var(--text-secondary);
      border: 1px solid var(--border-color);
    }

    .badge-info {
      background: var(--color-info-subtle);
      color: var(--color-info);
      border: 1px solid var(--color-info-border);
    }

    .badge-success {
      background: var(--color-success-subtle);
      color: var(--color-success);
      border: 1px solid var(--color-success-border);
    }

    .badge-warning {
      background: var(--color-warning-subtle);
      color: var(--color-warning);
      border: 1px solid var(--color-warning-border);
    }

    .badge-danger {
      background: var(--color-danger-subtle);
      color: var(--color-danger);
      border: 1px solid var(--color-danger-border);
    }

    .badge-accent {
      background: var(--color-accent-subtle);
      color: var(--color-accent);
      border: 1px solid var(--color-accent-border);
    }

    .badge-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      display: inline-block;
      flex-shrink: 0;
    }

    .dot-success { background-color: var(--color-success); }
    .dot-warning { background-color: var(--color-warning); }
    .dot-danger { background-color: var(--color-danger); }
    .dot-accent { background-color: var(--color-accent); }
    .dot-info { background-color: var(--color-info); }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      height: 28px;
      padding: 0 12px;
      font-family: var(--font-sans);
      font-size: var(--font-size-sm);
      font-weight: 500;
      border-radius: var(--radius-sm);
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
      white-space: nowrap;
      user-select: none;
    }

    .btn-sm {
      height: 24px;
      padding: 0 8px;
      font-size: var(--font-size-xs);
    }

    .btn-primary {
      background-color: var(--color-accent);
      border: 1px solid var(--color-accent);
      color: var(--text-inverse);
      font-weight: 600;
    }

    .btn-primary:hover:not(:disabled) {
      background-color: var(--color-accent-hover);
      border-color: var(--color-accent-hover);
    }

    .btn-outline {
      background: transparent;
      border: 1px solid var(--border-color);
      color: var(--text-primary);
    }

    .btn-outline:hover:not(:disabled) {
      background: var(--bg-surface-hover);
      border-color: var(--text-secondary);
    }

    .btn-outline-danger {
      background: transparent;
      border: 1px solid var(--color-danger-border);
      color: var(--color-danger);
    }

    .btn-outline-danger:hover:not(:disabled) {
      background: var(--color-danger-subtle);
    }

    .btn-ghost {
      background: transparent;
      border: 1px solid transparent;
      color: var(--text-secondary);
    }

    .btn-ghost:hover:not(:disabled) {
      background: var(--bg-surface-hover);
      color: var(--text-primary);
    }

    .btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }

    /* Tabler Form Controls */
    .form-control {
      height: 28px;
      background-color: var(--bg-input);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: var(--font-size-sm);
      padding: 0 10px;
      outline: none;
      transition: border-color 0.15s ease;
    }

    .form-control:focus {
      border-color: var(--border-focus);
    }

    .form-control:disabled {
      background-color: rgba(255, 255, 255, 0.02);
      color: var(--text-muted);
      cursor: not-allowed;
    }

    .form-select {
      height: 28px;
      background-color: var(--bg-input);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: var(--font-size-sm);
      padding: 0 8px;
      outline: none;
      cursor: pointer;
    }

    .form-select:focus {
      border-color: var(--border-focus);
    }

    .form-label {
      font-size: var(--font-size-xs);
      font-weight: 500;
      color: var(--text-secondary);
      margin-bottom: 4px;
      display: block;
    }

    .form-hint {
      font-size: 11px;
      color: var(--text-muted);
      margin-top: 3px;
    }

    .form-check {
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      user-select: none;
    }

    .form-check input[type="checkbox"] {
      cursor: pointer;
      accent-color: var(--color-accent);
    }

    /* Tabler Tables */
    .table-responsive {
      overflow-x: auto;
      width: 100%;
    }

    .table {
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: var(--font-size-sm);
    }

    .table th {
      padding: 8px 12px;
      background-color: var(--bg-surface-subtle);
      color: var(--text-secondary);
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.03em;
      border-bottom: 1px solid var(--border-color);
      white-space: nowrap;
    }

    .table td {
      padding: 9px 12px;
      border-bottom: 1px solid var(--border-subtle);
      color: var(--text-primary);
      vertical-align: middle;
    }

    .table tbody tr {
      cursor: pointer;
      transition: background-color 0.15s ease, border-color 0.15s ease;
      position: relative;
    }

    .table tbody tr:hover {
      background-color: var(--bg-surface-hover);
    }

    .table tbody tr.is-selected {
      background-color: var(--bg-surface-active);
    }

    .table tbody tr.is-selected td:first-child {
      border-left: 3px solid var(--color-accent);
      padding-left: 9px;
    }

    /* Status Metric Widgets */
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: var(--space-3);
    }

    @media (max-width: 1100px) {
      .metric-grid {
        grid-template-columns: repeat(2, 1fr);
      }
    }

    .metric-card {
      background-color: var(--bg-surface-subtle);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      padding: var(--space-3);
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .metric-label {
      font-size: 11px;
      font-weight: 500;
      color: var(--text-secondary);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    .metric-value {
      font-family: var(--font-mono);
      font-size: var(--font-size-sm);
      font-weight: 600;
      color: var(--text-primary);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    /* Section Division / Anchor Banner */
    .section-anchor-banner {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: var(--space-2) var(--space-4);
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      border-left: 3px solid var(--color-accent);
    }

    .anchor-title {
      font-size: 12px;
      font-weight: 700;
      color: var(--color-accent);
      letter-spacing: 0.04em;
      text-transform: uppercase;
      display: flex;
      align-items: center;
      gap: var(--space-2);
    }

    .anchor-context {
      font-size: 12px;
      color: var(--text-secondary);
      font-weight: 500;
    }

    /* Hero Strategy Banner in Detail */
    .detail-hero-card {
      background-color: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      padding: var(--space-4);
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
    }

    .hero-top-row {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: var(--space-4);
      flex-wrap: wrap;
    }

    .hero-title-area {
      flex: 1;
      min-width: 300px;
    }

    .hero-name {
      font-size: var(--font-size-xl);
      font-weight: 700;
      color: var(--text-primary);
      letter-spacing: -0.01em;
      line-height: 1.3;
      margin-bottom: 6px;
      word-break: break-word;
    }

    .hero-meta-row {
      display: flex;
      align-items: center;
      gap: var(--space-3);
      flex-wrap: wrap;
      font-size: var(--font-size-xs);
      color: var(--text-secondary);
    }

    .hero-actions-area {
      display: flex;
      align-items: center;
      gap: var(--space-2);
      flex-shrink: 0;
    }

    /* Two-Column Detail Grid */
    .detail-grid {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: var(--space-5);
    }

    @media (max-width: 1200px) {
      .detail-grid {
        grid-template-columns: 1fr;
      }
    }

    /* Tabler Code Box */
    .code-card {
      background-color: var(--bg-code);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .code-card-header {
      background-color: var(--bg-surface);
      border-bottom: 1px solid var(--border-color);
      padding: var(--space-2) var(--space-3);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: var(--font-size-xs);
    }

    .code-scroll-pane {
      max-height: 480px;
      overflow-y: auto;
      padding: var(--space-3);
      font-family: var(--font-mono);
      font-size: 11.5px;
      line-height: 1.6;
      color: #c9d1d9;
      white-space: pre;
    }

    /* Tabler Activity Stream */
    .activity-stream {
      position: relative;
      padding-left: 18px;
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
    }

    .activity-stream::before {
      content: "";
      position: absolute;
      left: 5px;
      top: 4px;
      bottom: 4px;
      width: 1px;
      background-color: var(--border-color);
    }

    .activity-node {
      position: relative;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .activity-dot {
      position: absolute;
      left: -18px;
      top: 4px;
      width: 9px;
      height: 9px;
      border-radius: 50%;
      border: 2px solid var(--bg-surface);
      background-color: var(--text-muted);
    }

    .activity-node.is-success .activity-dot { background-color: var(--color-success); }
    .activity-node.is-warning .activity-dot { background-color: var(--color-warning); }
    .activity-node.is-info .activity-dot { background-color: var(--color-info); }

    .activity-title {
      font-size: 12px;
      font-weight: 500;
      color: var(--text-primary);
    }

    .activity-time {
      font-size: 11px;
      font-family: var(--font-mono);
      color: var(--text-muted);
    }

    /* Copyable Hash Button */
    .hash-snippet {
      font-family: var(--font-mono);
      font-size: 11px;
      background: var(--bg-app);
      border: 1px solid var(--border-subtle);
      padding: 1px 6px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      color: var(--text-primary);
      transition: border-color 0.15s ease;
    }

    .hash-snippet:hover {
      border-color: var(--color-accent);
      color: var(--color-accent);
    }

    /* Toast Notification */
    .toast-pill {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background-color: var(--bg-surface-active);
      color: var(--text-primary);
      border: 1px solid var(--color-accent-border);
      padding: 8px 16px;
      border-radius: var(--radius-sm);
      font-size: var(--font-size-sm);
      font-weight: 500;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
      display: none;
      z-index: 9999;
      pointer-events: none;
    }
  </style>
</head>
<body>

  <!-- ================= 1. Attached Sidebar (Tabler) ================= -->
  <aside class="app-sidebar">
    <div class="sidebar-brand">
      <div class="brand-logo-badge">C</div>
      <div class="brand-title">catOS</div>
      <div class="brand-version">v1.2</div>
    </div>

    <nav class="sidebar-nav">
      <div class="nav-item">
        <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
        <span>戰情總覽</span>
      </div>
      <div class="nav-item active">
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

    <div class="sidebar-footer">
      <span>LOCAL ENGINE</span>
      <span class="badge badge-success" style="font-size:10px; padding:1px 5px;">ONLINE</span>
    </div>
  </aside>

  <!-- ================= 2. App Main Viewport ================= -->
  <main class="app-main">
    
    <!-- Topbar -->
    <header class="app-header">
      <div class="header-breadcrumb">
        <span class="breadcrumb-root">策略中心</span>
        <span class="breadcrumb-sep">/</span>
        <span class="breadcrumb-current">控制台總覽 (Control Center)</span>
      </div>

      <div class="header-badge-group">
        <span class="badge badge-secondary">PROTOTYPE B · CONTROL CENTER</span>
        <span class="badge badge-info">
          <span class="badge-dot dot-success"></span>
          <span>MCP LOCAL MODE</span>
        </span>
      </div>
    </header>

    <!-- Scrollable Control Center Container -->
    <div class="control-center-scroll">
      
      <!-- ================= TOP SECTION: Overview Table Card ================= -->
      <section class="card">
        <div class="card-header">
          <div class="card-title">
            <span>本機策略製品總覽 (REGISTERED STRATEGIES)</span>
            <span class="badge badge-secondary" id="table-count-badge">3 個策略</span>
          </div>

          <div class="card-actions">
            <!-- Search -->
            <input type="text" class="form-control" id="table-search-input" placeholder="搜尋策略名稱、版本或指紋..." style="width: 220px;" oninput="handleTableFilter()">
            
            <!-- Filter Tabs -->
            <div style="display:flex; gap:2px; background:var(--bg-app); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); padding:2px;">
              <button class="btn btn-sm btn-ghost filter-tab-btn active" onclick="setTableFilter('ALL', this)">全部</button>
              <button class="btn btn-sm btn-ghost filter-tab-btn" onclick="setTableFilter('TRUSTED', this)">已信任</button>
              <button class="btn btn-sm btn-ghost filter-tab-btn" onclick="setTableFilter('UNTRUSTED', this)">待審核</button>
            </div>

            <!-- Reload / MCP Sync button -->
            <button class="btn btn-sm btn-outline" onclick="showToast('已同步本機 MCP 註冊表最新狀態')">
              ↻ 重新整理
            </button>
          </div>
        </div>

        <div class="table-responsive">
          <table class="table" id="strategy-overview-table">
            <thead>
              <tr>
                <th style="width: 130px;">信任狀態</th>
                <th style="min-width: 240px;">策略名稱 / 識別碼</th>
                <th style="width: 100px;">作用版本</th>
                <th style="width: 110px;">執行模式</th>
                <th style="width: 110px;">綁定 Bot 數</th>
                <th style="width: 190px;">製品指紋 (SHA-256)</th>
                <th style="width: 160px;">最後審查時間</th>
                <th style="width: 110px; text-align: right;">操作</th>
              </tr>
            </thead>
            <tbody id="strategy-table-body">
              <!-- Dynamically populated -->
            </tbody>
          </table>
        </div>

        <div class="card-footer">
          <span>提示：點擊任一列即可在下方展開該策略之完整源碼、參數矩陣、信任審查及 Bot 綁定面板。</span>
          <span style="font-family:var(--font-mono);">LOCAL WAL ENGINE ACTIVE</span>
        </div>
      </section>

      <!-- ================= SECTION DIVISION ANCHOR ================= -->
      <div class="section-anchor-banner">
        <div class="anchor-title">
          <span>❖ 策略深入檢視與配置 (DEEP DIVE CONSOLE)</span>
        </div>
        <div class="anchor-context" id="anchor-current-context">
          目前聚焦策略：<strong id="anchor-strategy-name" style="color:var(--text-primary); font-family:var(--font-mono);">—</strong>
        </div>
      </div>

      <!-- ================= BOTTOM SECTION: Full Detail Sections ================= -->
      <section id="detail-section-container" style="display:flex; flex-direction:column; gap:var(--space-5);">
        <!-- Dynamically rendered by renderDetailSection() -->
      </section>

    </div>
  </main>

  <div class="toast-pill" id="toast-pill">通知訊息</div>

  <!-- ================= SCRIPT & DATA LOGIC ================= -->
  <script>
    // ==========================================================================
    // Real catOS Strategy Data (Identical to Prototype A for absolute consistency)
    // ==========================================================================
    const STRATEGY_DATA = [
      {
        id: "counter-python",
        name: "Counter Python",
        version: "mcp-v3",
        allVersions: ["mcp-v3", "mcp-v2", "mcp-v1"],
        mode: "LOCAL",
        sourceUri: "mcp://strategies/counter/v3",
        artifactHash: "8bb79f5f0bca9076c1006815bdae7846bbb6ca89e2e604f3214c7fd5241b31a2",
        isTrusted: true,
        trustedBy: "Ryan Cheng (Local Signer)",
        trustedAt: "2026-10-02 14:22:08",
        description: "CatOS 基準高頻反轉策略，專注於已收盤 K 線撮合，強制注入專屬 tag 與鎖存機制防護。",
        parameters: [
          { key: "quantity", type: "Decimal", val: "-1", desc: "單次委託目標合約張數 (負數為反向空單)" },
          { key: "hold", type: "bool", val: "false", desc: "鎖定持倉不換倉開關" },
          { key: "risk_budget", type: "Decimal", val: "0.015", desc: "單筆風險預算占比 (1.5%)" },
          { key: "slippage_model", type: "string", val: "strict_taker", desc: "下一根 Bar 開盤加明示滑價損耗模型" }
        ],
        sourceCode: `from decimal import Decimal
import time

class Strategy:
    \"\"\"
    CatOS Minimal Production Strategy - Closed Bar Only
    Strict Decimal Arithmetic | OKX SWAP Direct Execution
    \"\"\"
    def __init__(self, params: dict):
        self.quantity = Decimal(str(params.get("quantity", "-1")))
        self.hold = bool(params.get("hold", False))
        self.risk_budget = Decimal(str(params.get("risk_budget", "0.015")))
        self.last_bar_ts = 0

    def on_bar_closed(self, bar: dict, account_state: dict) -> dict:
        \"\"\"
        Invoked strictly on closed bar. Returns pure target intent.
        Supervisor checks account Soft/Hard Latch before execution.
        \"\"\"
        if self.hold:
            return {"action": "HOLD", "target_pos": Decimal("0")}
        
        # Pure signal logic (Supervisor injects invariant tag and checks Latch)
        target_amount = self.quantity
        return {
            "action": "TARGET_INTENT",
            "target_amount": target_amount,
            "order_type": "MARKET",
            "reason": f"Signal generated on bar {bar.get('timestamp')}"
        }`,
        botBindings: [
          { botId: "counter-final", status: "RUNNING", uptime: "14h 22m", symbol: "BTC-USDT-SWAP" },
          { botId: "counter-standby", status: "STOPPED", uptime: "—", symbol: "BTC-USDT-SWAP" }
        ],
        activity: [
          { title: "Bot counter-final 已指派綁定至 Counter Python (mcp-v3)", time: "2026-10-02 14:25:10", type: "success" },
          { title: "策略版本 mcp-v3 經人工審核代碼安全，標記為 TRUSTED", time: "2026-10-02 14:22:08", type: "success" },
          { title: "自 MCP 來源編譯製品 mcp://strategies/counter/v3 (SHA: 8bb79f5...)", time: "2026-10-02 14:18:30", type: "info" },
          { title: "建立初始策略草稿 counter-v1", time: "2026-09-28 09:12:00", type: "info" }
        ]
      },
      {
        id: "atr-momentum-breakout-extended",
        name: "ATR Momentum Breakout v1.1 Alpha Extended Realtime Production Strategy",
        version: "v1.1",
        allVersions: ["v1.1", "v1.0"],
        mode: "LOCAL",
        sourceUri: "mcp://strategies/momentum/atr-breakout-v11",
        artifactHash: "41cb53c54d6dabde789214ef567812903412abef019234871234908123456789",
        isTrusted: false,
        trustedBy: null,
        trustedAt: null,
        description: "高波動突破跟隨模型。目前為新上傳版本，尚未完成人工安全簽核，禁止直接綁定實盤 Bot。",
        parameters: [
          { key: "atr_period", type: "int", val: "22", desc: "ATR 平均真實波幅窗口週期" },
          { key: "atr_multiplier", type: "Decimal", val: "2.30", desc: "突破通道外擴乘數" },
          { key: "risk_per_trade", type: "Decimal", val: "0.015", desc: "單筆停損最大風險承受度" },
          { key: "trailing_stop_pct", type: "Decimal", val: "0.028", desc: "災難停損保護閥值 (2.8%)" }
        ],
        sourceCode: `from decimal import Decimal

class ATRBreakoutStrategy:
    \"\"\"
    ATR Volatility Breakout Model
    Generates dynamic trailing channels on 15m closed bars.
    \"\"\"
    def __init__(self, params: dict):
        self.atr_period = int(params.get("atr_period", 22))
        self.atr_multiplier = Decimal(str(params.get("atr_multiplier", "2.30")))
        self.risk_per_trade = Decimal(str(params.get("risk_per_trade", "0.015")))
        self.trailing_stop_pct = Decimal(str(params.get("trailing_stop_pct", "0.028")))

    def on_bar_closed(self, bar: dict, account_state: dict) -> dict:
        close_px = Decimal(str(bar["close"]))
        high_px = Decimal(str(bar["high"]))
        low_px = Decimal(str(bar["low"]))
        
        # Calculation truncated for safety verification
        return {"action": "OBSERVE", "price": close_px}`,
        botBindings: [],
        activity: [
          { title: "自 MCP 來源接收到新製品，處於待審查狀態 (UNTRUSTED)", time: "2026-10-03 10:15:22", type: "warning" },
          { title: "發布者登記新版本 v1.1", time: "2026-10-03 10:14:00", type: "info" }
        ]
      },
      {
        id: "dual-ma-cross",
        name: "Dual MA Crossover Simulation Model",
        version: "v0.9-beta",
        allVersions: ["v0.9-beta"],
        mode: "LOCAL",
        sourceUri: "mcp://strategies/ma_cross/v09",
        artifactHash: "9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b",
        isTrusted: true,
        trustedBy: "Ryan Cheng (Local Signer)",
        trustedAt: "2026-09-30 18:05:00",
        description: "雙均線金叉死叉趨勢模型，適用於 ETH-USDT-SWAP 震盪偏多行情。",
        parameters: [
          { key: "fast_period", type: "int", val: "9", desc: "快線 SMA 週期 (9 Bars)" },
          { key: "slow_period", type: "int", val: "21", desc: "慢線 SMA 週期 (21 Bars)" },
          { key: "max_leverage_limit", type: "Decimal", val: "2.0", desc: "本策略專屬有效槓桿上限 (2.0x)" }
        ],
        sourceCode: `from decimal import Decimal

class DualMACross:
    def __init__(self, params: dict):
        self.fast_p = int(params.get("fast_period", 9))
        self.slow_p = int(params.get("slow_period", 21))
        
    def on_bar_closed(self, bar: dict, account_state: dict) -> dict:
        return {"action": "HOLD"}`,
        botBindings: [
          { botId: "trend-bot-01", status: "STOPPED", uptime: "—", symbol: "ETH-USDT-SWAP" }
        ],
        activity: [
          { title: "trend-bot-01 經由人工指令停止運行", time: "2026-10-01 08:00:00", type: "info" },
          { title: "版本 v0.9-beta 標記為 TRUSTED", time: "2026-09-30 18:05:00", type: "success" }
        ]
      }
    ];

    let currentStrategyId = "counter-python";
    let activeTableFilter = "ALL";

    // ==========================================================================
    // Render Functions
    // ==========================================================================
    function renderOverviewTable() {
      const tbody = document.getElementById("strategy-table-body");
      const query = (document.getElementById("table-search-input")?.value || "").toLowerCase();

      const filtered = STRATEGY_DATA.filter(s => {
        if (activeTableFilter === "TRUSTED" && !s.isTrusted) return false;
        if (activeTableFilter === "UNTRUSTED" && s.isTrusted) return false;
        if (query && !s.name.toLowerCase().includes(query) && !s.id.toLowerCase().includes(query) && !s.artifactHash.toLowerCase().includes(query)) return false;
        return true;
      });

      document.getElementById("table-count-badge").textContent = `${filtered.length} 個策略`;

      tbody.innerHTML = filtered.map(s => {
        const isSelected = s.id === currentStrategyId;
        return `
          <tr class="${isSelected ? 'is-selected' : ''}" onclick="selectStrategy('${s.id}')">
            <!-- 1. Status / Trust -->
            <td>
              ${s.isTrusted 
                ? `<span class="badge badge-success"><span class="badge-dot dot-success"></span>已信任</span>` 
                : `<span class="badge badge-warning"><span class="badge-dot dot-warning"></span>待審核</span>`}
            </td>

            <!-- 2. Strategy Name & ID -->
            <td>
              <div style="font-weight:600; color:var(--text-primary); font-size:13px; line-height:1.3; max-width:340px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${s.name}">
                ${s.name}
              </div>
              <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted); margin-top:2px;">
                ID: ${s.id}
              </div>
            </td>

            <!-- 3. Active Version -->
            <td>
              <span class="badge badge-secondary" style="font-family:var(--font-mono); font-size:11px;">${s.version}</span>
            </td>

            <!-- 4. Execution Mode -->
            <td>
              <span class="badge badge-info" style="font-size:11px;">${s.mode}</span>
            </td>

            <!-- 5. Bound Bots Count -->
            <td>
              ${s.botBindings.length > 0 
                ? `<span class="badge badge-accent" style="font-family:var(--font-mono);">${s.botBindings.length} 個 Bot</span>`
                : `<span style="color:var(--text-muted); font-size:12px;">無綁定</span>`}
            </td>

            <!-- 6. Artifact SHA-256 Snippet -->
            <td>
              <span class="hash-snippet" onclick="event.stopPropagation(); copyHash('${s.artifactHash}')" title="點擊複製完整 SHA-256">
                ${s.artifactHash.substring(0, 16)}... ⎘
              </span>
            </td>

            <!-- 7. Last Audited -->
            <td style="font-family:var(--font-mono); font-size:11.5px; color:var(--text-secondary);">
              ${s.trustedAt ? s.trustedAt.substring(0, 16) : '<span style="color:var(--text-muted);">尚未審核</span>'}
            </td>

            <!-- 8. Actions -->
            <td style="text-align:right;">
              ${isSelected 
                ? `<span class="badge badge-accent" style="font-size:11px; padding:3px 8px;">作用中</span>` 
                : `<button class="btn btn-sm btn-outline" onclick="event.stopPropagation(); selectStrategy('${s.id}')">檢視</button>`}
            </td>
          </tr>
        `;
      }).join('');
    }

    function renderDetailSection() {
      const container = document.getElementById("detail-section-container");
      const s = STRATEGY_DATA.find(x => x.id === currentStrategyId);

      if (!s) {
        container.innerHTML = `<div class="card"><div class="card-body" style="color:var(--text-muted);">請由上方列表中選擇一個策略進行檢視。</div></div>`;
        return;
      }

      // Update anchor banner
      document.getElementById("anchor-strategy-name").textContent = `${s.name} (${s.version})`;

      container.innerHTML = `
        <!-- 1. Hero Summary & Verification Banner -->
        <div class="detail-hero-card">
          <div class="hero-top-row">
            <div class="hero-title-area">
              <div class="hero-name">${s.name}</div>
              <div class="hero-meta-row">
                <div style="display:flex; align-items:center; gap:6px;">
                  <span>版本:</span>
                  <select class="form-select" style="height:24px; font-size:11px; font-family:var(--font-mono);" onchange="switchVersion('${s.id}', this.value)">
                    ${s.allVersions.map(v => `<option value="${v}" ${v === s.version ? 'selected' : ''}>${v}</option>`).join('')}
                  </select>
                </div>
                <span>•</span>
                <div>來源: <span style="font-family:var(--font-mono); color:var(--text-primary);">${s.sourceUri}</span></div>
                <span>•</span>
                <div>模式: <span class="badge badge-info">${s.mode}</span></div>
                <span>•</span>
                <div>
                  狀態: 
                  ${s.isTrusted 
                    ? `<span class="badge badge-success"><span class="badge-dot dot-success"></span>已信任 (TRUSTED)</span>` 
                    : `<span class="badge badge-warning"><span class="badge-dot dot-warning"></span>待審查 (UNTRUSTED)</span>`}
                </div>
              </div>
            </div>

            <!-- Primary Action Buttons -->
            <div class="hero-actions-area">
              ${s.isTrusted ? `
                <button class="btn btn-outline-danger" onclick="revokeTrust('${s.id}')">
                  🔒 撤銷信任 (Revoke)
                </button>
                <button class="btn btn-primary" onclick="focusBotAllocation()">
                  🤖 分配機器人 (Assign)
                </button>
                <button class="btn btn-ghost" onclick="goToBotManager()">
                  ↗ 前往 Bots Fleet
                </button>
              ` : `
                <div style="display:flex; align-items:center; gap:8px;">
                  <label class="form-check" style="font-size:12px; color:var(--text-secondary);">
                    <input type="checkbox" id="hero-trust-checkbox" onchange="toggleHeroTrustBtn(this.checked)">
                    <span>已複核代碼與依賴</span>
                  </label>
                  <button class="btn btn-primary" id="btn-hero-sign-trust" disabled onclick="grantTrust('${s.id}')">
                    🛡️ 審核並簽署信任 (Sign Trust)
                  </button>
                </div>
              `}
            </div>
          </div>

          <!-- Description -->
          <div style="font-size:var(--font-size-sm); color:var(--text-secondary); line-height:1.5;">
            ${s.description}
          </div>

          <!-- Metric Grid (Technical Invariants & Footprints) -->
          <div class="metric-grid">
            <div class="metric-card">
              <div class="metric-label">
                <span>製品 SHA-256 指紋</span>
                <span class="hash-snippet" onclick="copyHash('${s.artifactHash}')" title="複製完整指紋">⎘ 複製</span>
              </div>
              <div class="metric-value" title="${s.artifactHash}">
                ${s.artifactHash.substring(0, 20)}...
              </div>
            </div>

            <div class="metric-card">
              <div class="metric-label">
                <span>MCP 端點協議</span>
                <span class="badge badge-success" style="font-size:10px; padding:1px 4px;">ACTIVE</span>
              </div>
              <div class="metric-value">${s.sourceUri}</div>
            </div>

            <div class="metric-card">
              <div class="metric-label">
                <span>交易協議約束</span>
                <span class="badge badge-secondary" style="font-size:10px; padding:1px 4px;">INVARIANT</span>
              </div>
              <div class="metric-value">cross / net_mode · tag: 41cb53c5</div>
            </div>

            <div class="metric-card">
              <div class="metric-label">
                <span>安全簽核人員</span>
                <span class="badge badge-secondary" style="font-size:10px; padding:1px 4px;">SIGNER</span>
              </div>
              <div class="metric-value" style="font-family:var(--font-sans);">
                ${s.trustedBy || '<span style="color:var(--text-muted); font-family:var(--font-mono);">NONE (UNAUDITED)</span>'}
              </div>
            </div>
          </div>
        </div>

        <!-- 2. Two-Column Workspace (Code Viewer vs Parameters & Bot Bindings) -->
        <div class="detail-grid">
          
          <!-- LEFT COLUMN: Tabler Code Card -->
          <div class="code-card">
            <div class="code-card-header">
              <div style="display:flex; align-items:center; gap:8px;">
                <span class="badge badge-secondary" style="font-family:var(--font-mono); font-size:10px;">PYTHON 3.11+</span>
                <span style="font-weight:600; color:var(--text-primary); font-family:var(--font-mono);">strategy.py</span>
                <span style="color:var(--text-muted);">(${s.version})</span>
              </div>
              <div style="display:flex; align-items:center; gap:6px;">
                <span class="badge badge-secondary" style="font-family:var(--font-mono); font-size:10.5px;">CLOSED BAR ONLY</span>
                <button class="btn btn-sm btn-outline" onclick="copyCode()">
                  ⎘ 複製源碼
                </button>
              </div>
            </div>
            
            <pre class="code-scroll-pane"><code>${escapeHtml(s.sourceCode)}</code></pre>

            <div class="card-footer" style="background:var(--bg-surface-subtle); border-top:1px solid var(--border-color);">
              <span>約束：僅使用 Closed Bar • 金額計算強制 Decimal • Supervisor 獨佔執行出口</span>
              <span style="font-family:var(--font-mono);">Lines: 32 · UTF-8</span>
            </div>
          </div>

          <!-- RIGHT COLUMN: Parameters & Bot Allocation -->
          <div style="display:flex; flex-direction:column; gap:var(--space-5);">
            
            <!-- Parameters Card -->
            <div class="card">
              <div class="card-header">
                <div class="card-title">
                  <span>策略參數矩陣 (PARAMETERS)</span>
                  <span class="badge badge-secondary" style="font-family:var(--font-mono); font-size:11px;">${s.parameters.length} 參數</span>
                </div>
                <div class="card-actions">
                  <button class="btn btn-sm btn-ghost" onclick="showToast('已重設參數為原始預設值')">重設預設</button>
                  <button class="btn btn-sm btn-primary" onclick="showToast('參數本機設定已儲存')">儲存變更</button>
                </div>
              </div>

              <div class="card-body" style="display:flex; flex-direction:column; gap:var(--space-3); padding:var(--space-3) var(--space-4);">
                ${s.parameters.map((p, idx) => `
                  <div style="display:flex; flex-direction:column; gap:2px; border-bottom: ${idx < s.parameters.length - 1 ? '1px solid var(--border-subtle)' : 'none'}; padding-bottom:8px;">
                    <div style="display:flex; align-items:center; justify-content:space-between;">
                      <label class="form-label" style="font-family:var(--font-mono); color:var(--text-primary); font-size:12px; margin:0;">
                        ${p.key}
                      </label>
                      <span class="badge badge-secondary" style="font-size:10px; font-family:var(--font-mono);">${p.type}</span>
                    </div>
                    <div style="display:flex; gap:var(--space-2); align-items:center;">
                      <input type="text" class="form-control" value="${p.val}" style="font-family:var(--font-mono); font-size:12px; flex:1;" onchange="showToast('參數已修改 (待儲存)')">
                      <span style="font-size:11px; color:var(--text-muted); width:70px; text-align:right;">✓ 格式有效</span>
                    </div>
                    <div class="form-hint">${p.desc}</div>
                  </div>
                `).join('')}
              </div>
            </div>

            <!-- Bot Fleet Allocation Card -->
            <div class="card" id="card-bot-allocation">
              <div class="card-header">
                <div class="card-title">
                  <span>本機 Bot 綁定調度 (FLEET BINDINGS)</span>
                </div>
                <a href="javascript:void(0)" onclick="goToBotManager()" style="font-size:11.5px; color:var(--color-accent); text-decoration:none;">前往機器人管理 &rarr;</a>
              </div>

              <div class="card-body" style="display:flex; flex-direction:column; gap:var(--space-3);">
                <!-- New Assignment Input Group -->
                <div>
                  <label class="form-label">指派至新 Bot (Bot ID)</label>
                  <div style="display:flex; gap:var(--space-2);">
                    <input type="text" class="form-control" id="control-input-bot-id" placeholder="例如: bot-sol-trend-01" style="flex:1;" ${!s.isTrusted ? 'disabled' : ''}>
                    <button class="btn btn-primary" ${!s.isTrusted ? 'disabled' : ''} onclick="allocateBot('${s.id}')">
                      綁定 Bot
                    </button>
                  </div>
                  ${!s.isTrusted ? `
                    <div style="font-size:11.5px; color:var(--color-warning); margin-top:5px; display:flex; align-items:center; gap:4px;">
                      <span>⚠</span> 策略尚未獲得本機信任簽核，受金融風控規則防護，禁止分配 Bot。
                    </div>
                  ` : ''}
                </div>

                <!-- Bound Bots List -->
                <div>
                  <div style="font-size:11px; color:var(--text-muted); font-weight:600; text-transform:uppercase; margin-bottom:6px;">
                    已綁定之執行 Bot (${s.botBindings.length})
                  </div>
                  
                  ${s.botBindings.length === 0 ? `
                    <div style="padding:14px; background:var(--bg-app); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); font-size:12px; color:var(--text-muted); text-align:center;">
                      目前此策略無任何綁定之 Bot。信任簽核後可自由指派。
                    </div>
                  ` : `
                    <div style="display:flex; flex-direction:column; gap:6px;">
                      ${s.botBindings.map(b => `
                        <div style="display:flex; align-items:center; justify-content:space-between; padding:8px 10px; background:var(--bg-surface-subtle); border:1px solid var(--border-color); border-radius:var(--radius-sm);">
                          <div>
                            <div style="font-weight:600; font-family:var(--font-mono); font-size:12.5px; color:var(--text-primary);">${b.botId}</div>
                            <div style="font-size:11px; color:var(--text-muted);">${b.symbol} · ${b.uptime || '已常駐'}</div>
                          </div>
                          <div style="display:flex; align-items:center; gap:8px;">
                            ${b.status === 'RUNNING' 
                              ? '<span class="badge badge-success"><span class="badge-dot dot-success"></span>Running</span>' 
                              : '<span class="badge badge-secondary">Stopped</span>'}
                            <button class="btn btn-sm btn-outline" onclick="goToBotManager('${b.botId}')">檢視 &rarr;</button>
                          </div>
                        </div>
                      `).join('')}
                    </div>
                  `}
                </div>
              </div>
            </div>

          </div>
        </div>

        <!-- 3. Audit Activity Timeline Card -->
        <div class="card">
          <div class="card-header">
            <div class="card-title">
              <span>審計活動軌跡 (AUDIT TRAIL & ACTIVITY LOG)</span>
              <span class="badge badge-secondary" style="font-family:var(--font-mono); font-size:11px;">${s.activity.length} 筆紀錄</span>
            </div>
            <span style="font-size:11px; color:var(--text-muted);">本機 SQLite WAL 自動歸檔</span>
          </div>

          <div class="card-body">
            <div class="activity-stream">
              ${s.activity.map(act => `
                <div class="activity-node is-${act.type}">
                  <div class="activity-dot"></div>
                  <div class="activity-title">${act.title}</div>
                  <div class="activity-time">${act.time}</div>
                </div>
              `).join('')}
            </div>
          </div>
        </div>
      `;
    }

    // ==========================================================================
    // Interaction Handlers
    // ==========================================================================
    function selectStrategy(id) {
      currentStrategyId = id;
      renderOverviewTable();
      renderDetailSection();
    }

    function setTableFilter(filter, btn) {
      activeTableFilter = filter;
      document.querySelectorAll('.filter-tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderOverviewTable();
    }

    function handleTableFilter() {
      renderOverviewTable();
    }

    function toggleHeroTrustBtn(isChecked) {
      const btn = document.getElementById("btn-hero-sign-trust");
      if (btn) btn.disabled = !isChecked;
    }

    function grantTrust(id) {
      const s = STRATEGY_DATA.find(x => x.id === id);
      if (s) {
        s.isTrusted = true;
        s.trustedBy = "Ryan Cheng (Local Signer)";
        s.trustedAt = new Date().toISOString().replace('T', ' ').substring(0, 19);
        s.activity.unshift({
          title: `策略版本 ${s.version} 經人工審核代碼安全，標記為 TRUSTED`,
          time: s.trustedAt,
          type: "success"
        });
        showToast("已成功簽署信任標記！可開始分配 Bot。");
        renderOverviewTable();
        renderDetailSection();
      }
    }

    function revokeTrust(id) {
      const s = STRATEGY_DATA.find(x => x.id === id);
      if (s) {
        s.isTrusted = false;
        s.trustedBy = null;
        s.trustedAt = null;
        s.activity.unshift({
          title: `策略版本 ${s.version} 人工信任標記已撤銷 (UNTRUSTED)`,
          time: new Date().toISOString().replace('T', ' ').substring(0, 19),
          type: "warning"
        });
        showToast("已撤銷信任標記！已關閉指派功能。");
        renderOverviewTable();
        renderDetailSection();
      }
    }

    function switchVersion(id, ver) {
      const s = STRATEGY_DATA.find(x => x.id === id);
      if (s) {
        s.version = ver;
        showToast(`已切換檢視版本至 ${ver}`);
        renderOverviewTable();
        renderDetailSection();
      }
    }

    function allocateBot(id) {
      const input = document.getElementById("control-input-bot-id");
      const val = (input?.value || "").trim();
      if (!val) {
        showToast("請輸入目標 Bot 識別碼");
        return;
      }
      const s = STRATEGY_DATA.find(x => x.id === id);
      if (s) {
        s.botBindings.push({
          botId: val,
          status: "RUNNING",
          uptime: "剛剛指派",
          symbol: "BTC-USDT-SWAP"
        });
        s.activity.unshift({
          title: `Bot ${val} 已指派綁定至 ${s.name} (${s.version})`,
          time: new Date().toISOString().replace('T', ' ').substring(0, 19),
          type: "success"
        });
        showToast(`成功綁定 Bot: ${val}`);
        renderOverviewTable();
        renderDetailSection();
      }
    }

    function focusBotAllocation() {
      const card = document.getElementById("card-bot-allocation");
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const input = document.getElementById("control-input-bot-id");
        if (input) input.focus();
      }
    }

    function copyHash(hash) {
      navigator.clipboard.writeText(hash).then(() => {
        showToast("已複製 SHA-256 製品指紋至剪貼簿");
      }).catch(() => {
        showToast("複製失敗，請手動複製");
      });
    }

    function copyCode() {
      const s = STRATEGY_DATA.find(x => x.id === currentStrategyId);
      if (s) {
        navigator.clipboard.writeText(s.sourceCode).then(() => {
          showToast("已複製策略 Python 源碼至剪貼簿");
        });
      }
    }

    function goToBotManager(botId) {
      alert(`[導航展示] 即將跳轉至機器人管理分頁 (Bots Fleet)${botId ? '，並聚焦 Bot: ' + botId : ''}`);
    }

    function showToast(msg) {
      const toast = document.getElementById("toast-pill");
      if (toast) {
        toast.textContent = msg;
        toast.style.display = "block";
        setTimeout(() => { toast.style.display = "none"; }, 2500);
      }
    }

    function escapeHtml(str) {
      return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Init
    renderOverviewTable();
    renderDetailSection();
  </script>
</body>
</html>
"""

# 1. Output to catOS-Frontend-Final/prototypes/strategy-center-b.html
p1 = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final\prototypes\strategy-center-b.html')
p1.write_bytes(CONTENT_B.encode('utf-8'))
print("strategy-center-b.html written to catOS-Frontend-Final successfully.")

# 2. Sync to CatOS_Astra/frontend/prototypes/strategy-center-b.html
p2 = pathlib.Path(r'c:\Users\user\Desktop\CatOS_Astra\frontend\prototypes\strategy-center-b.html')
p2.write_bytes(CONTENT_B.encode('utf-8'))
print("strategy-center-b.html written to CatOS_Astra successfully.")
