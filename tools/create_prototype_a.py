# -*- coding: utf-8 -*-
import pathlib

CONTENT_A = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>catOS - Strategy Workstation (Prototype A)</title>
  
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
      --master-pane-width: 320px;
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
      width: 5px;
      height: 5px;
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
       Main Workstation Layout (Master-Detail Split Pane)
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

    /* Workstation Master-Detail Container */
    .workstation-container {
      flex: 1;
      display: flex;
      overflow: hidden;
      position: relative;
    }

    /* Master Pane (Left Strategy List) */
    .master-pane {
      width: var(--master-pane-width);
      background-color: var(--bg-sidebar);
      border-right: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
      height: calc(100vh - var(--header-height));
    }

    .master-header {
      padding: var(--space-3) var(--space-3);
      border-bottom: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      gap: var(--space-2);
    }

    .search-input-wrap {
      position: relative;
      display: flex;
      align-items: center;
    }

    .search-input {
      width: 100%;
      height: 28px;
      background-color: var(--bg-input);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: var(--font-size-sm);
      padding: 0 var(--space-2) 0 24px;
      outline: none;
      transition: border-color 0.15s ease;
    }

    .search-input:focus {
      border-color: var(--border-focus);
    }

    .search-icon {
      position: absolute;
      left: 7px;
      width: 12px;
      height: 12px;
      color: var(--text-muted);
      pointer-events: none;
    }

    .filter-tabs {
      display: flex;
      gap: 2px;
      background: var(--bg-app);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 2px;
    }

    .filter-btn {
      flex: 1;
      height: 22px;
      font-size: var(--font-size-xs);
      font-weight: 500;
      color: var(--text-muted);
      background: transparent;
      border: none;
      border-radius: var(--radius-sm);
      cursor: pointer;
      transition: all 0.15s ease;
    }

    .filter-btn.active {
      background: var(--bg-surface-active);
      color: var(--text-primary);
      font-weight: 600;
    }

    .master-list {
      flex: 1;
      overflow-y: auto;
      padding: var(--space-2);
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .strategy-item-card {
      padding: var(--space-3);
      background-color: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      cursor: pointer;
      transition: border-color 0.15s ease, background-color 0.15s ease;
      position: relative;
    }

    .strategy-item-card:hover {
      background-color: var(--bg-surface-hover);
      border-color: var(--border-focus);
    }

    .strategy-item-card.is-selected {
      background-color: var(--bg-surface-active);
      border-color: var(--color-accent);
    }

    .strategy-item-card.is-selected::before {
      content: "";
      position: absolute;
      left: -1px;
      top: -1px;
      bottom: -1px;
      width: 3px;
      background-color: var(--color-accent);
      border-top-left-radius: var(--radius-sm);
      border-bottom-left-radius: var(--radius-sm);
    }

    .item-header-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: var(--space-2);
      margin-bottom: 4px;
    }

    .item-name {
      font-size: var(--font-size-sm);
      font-weight: 600;
      color: var(--text-primary);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .item-version-tag {
      font-family: var(--font-mono);
      font-size: 10px;
      color: var(--text-muted);
      border: 1px solid var(--border-color);
      padding: 1px 4px;
      border-radius: var(--radius-sm);
      flex-shrink: 0;
    }

    .item-sub-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: var(--font-size-xs);
      color: var(--text-secondary);
      margin-top: 4px;
    }

    .hash-preview {
      font-family: var(--font-mono);
      font-size: 10.5px;
      color: var(--text-muted);
    }

    /* Detail Pane (Right Fixed Pane) */
    .detail-pane {
      flex: 1;
      background-color: var(--bg-app);
      display: flex;
      flex-direction: column;
      overflow-y: auto;
      height: calc(100vh - var(--header-height));
      padding: var(--space-4);
      gap: var(--space-4);
    }

    /* Tabler Style Card Standards */
    .card {
      background-color: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      display: flex;
      flex-direction: column;
    }

    .card-header {
      padding: var(--space-3) var(--space-4);
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 40px;
    }

    .card-title {
      font-size: var(--font-size-sm);
      font-weight: 600;
      color: var(--text-primary);
      display: flex;
      align-items: center;
      gap: var(--space-2);
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
      border-top: 1px solid var(--border-color);
      background-color: var(--bg-surface-subtle);
    }

    /* Detail Header Card */
    .strategy-headline-card {
      padding: var(--space-4);
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
    }

    .headline-top-row {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: var(--space-4);
    }

    .headline-title-block {
      flex: 1;
      min-width: 0;
    }

    .headline-title {
      font-size: var(--font-size-lg);
      font-weight: 700;
      color: var(--text-primary);
      word-break: break-word;
      line-height: 1.3;
    }

    .headline-meta-strip {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: var(--space-3);
      margin-top: var(--space-2);
      font-size: var(--font-size-xs);
      color: var(--text-secondary);
    }

    .meta-item {
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .hash-copyable {
      font-family: var(--font-mono);
      background: var(--bg-app);
      border: 1px solid var(--border-color);
      padding: 1px 6px;
      border-radius: var(--radius-sm);
      color: var(--text-primary);
      cursor: pointer;
      transition: border-color 0.15s ease;
    }

    .hash-copyable:hover {
      border-color: var(--color-accent);
    }

    /* Badges */
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 600;
      border-radius: var(--radius-sm);
      line-height: 1.2;
    }

    .badge-success {
      background: var(--color-success-subtle);
      border: 1px solid var(--color-success-border);
      color: var(--color-success);
    }

    .badge-warning {
      background: var(--color-warning-subtle);
      border: 1px solid var(--color-warning-border);
      color: var(--color-warning);
    }

    .badge-info {
      background: var(--color-info-subtle);
      border: 1px solid var(--color-info-border);
      color: var(--color-info);
    }

    .badge-secondary {
      background: var(--bg-surface-active);
      border: 1px solid var(--border-color);
      color: var(--text-secondary);
    }

    .badge-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
    }

    .dot-success { background: var(--color-success); }
    .dot-warning { background: var(--color-warning); }
    .dot-danger { background: var(--color-danger); }

    /* Buttons (Tabler Standards) */
    .btn {
      height: 28px;
      padding: 0 10px;
      font-family: var(--font-sans);
      font-size: var(--font-size-sm);
      font-weight: 500;
      border-radius: var(--radius-sm);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
      border: 1px solid transparent;
      outline: none;
    }

    .btn-primary {
      background-color: var(--color-accent);
      color: var(--text-inverse);
      font-weight: 600;
      border-color: var(--color-accent);
    }

    .btn-primary:hover:not(:disabled) {
      background-color: var(--color-accent-hover);
      border-color: var(--color-accent-hover);
    }

    .btn-outline {
      background-color: transparent;
      border-color: var(--border-color);
      color: var(--text-primary);
    }

    .btn-outline:hover:not(:disabled) {
      background-color: var(--bg-surface-hover);
      border-color: var(--border-focus);
    }

    .btn-ghost {
      background-color: transparent;
      color: var(--text-secondary);
    }

    .btn-ghost:hover:not(:disabled) {
      background-color: var(--bg-surface-hover);
      color: var(--text-primary);
    }

    .btn-danger-outline {
      background-color: transparent;
      border-color: var(--color-danger-border);
      color: var(--color-danger);
    }

    .btn-danger-outline:hover:not(:disabled) {
      background-color: var(--color-danger-subtle);
    }

    .btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
      pointer-events: none;
    }

    /* Form Controls */
    .form-control, .form-select {
      height: 28px;
      background-color: var(--bg-input);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-sm);
      color: var(--text-primary);
      font-family: var(--font-sans);
      font-size: var(--font-size-sm);
      padding: 0 var(--space-2);
      outline: none;
      transition: border-color 0.15s ease;
    }

    .form-control:focus, .form-select:focus {
      border-color: var(--border-focus);
    }

    .form-control:disabled, .form-select:disabled {
      opacity: 0.45;
      cursor: not-allowed;
      background-color: var(--bg-app);
    }

    /* Tabler Checkbox */
    .form-check {
      display: flex;
      align-items: center;
      gap: var(--space-2);
      cursor: pointer;
      user-select: none;
    }

    .form-check input[type="checkbox"] {
      width: 14px;
      height: 14px;
      accent-color: var(--color-accent);
      cursor: pointer;
    }

    .form-check-label {
      font-size: var(--font-size-sm);
      color: var(--text-primary);
    }

    /* Two-Column Detail Grid */
    .detail-two-col {
      display: grid;
      grid-template-columns: 1fr 380px;
      gap: var(--space-4);
      align-items: start;
    }

    /* Code Viewer Card */
    .code-box {
      background-color: var(--bg-code);
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }

    .code-header {
      padding: var(--space-2) var(--space-3);
      background-color: var(--bg-surface-subtle);
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: var(--font-size-xs);
      color: var(--text-secondary);
    }

    .code-scroll-area {
      max-height: 480px;
      overflow-y: auto;
      overflow-x: auto;
      padding: var(--space-3);
      font-family: var(--font-mono);
      font-size: 11.5px;
      line-height: 1.6;
      color: #cbd5e1;
    }

    /* Strategy Parameters Table */
    .table-clean {
      width: 100%;
      border-collapse: collapse;
      font-size: var(--font-size-sm);
    }

    .table-clean th {
      text-align: left;
      padding: var(--space-2) var(--space-3);
      background-color: var(--bg-surface-subtle);
      color: var(--text-secondary);
      font-size: var(--font-size-xs);
      font-weight: 600;
      border-bottom: 1px solid var(--border-color);
    }

    .table-clean td {
      padding: var(--space-2) var(--space-3);
      border-bottom: 1px solid var(--border-subtle);
      vertical-align: middle;
    }

    .table-clean tr:last-child td {
      border-bottom: none;
    }

    .table-clean tr:hover td {
      background-color: var(--bg-surface-hover);
    }

    .mono-val {
      font-family: var(--font-mono);
      font-size: 11.5px;
      color: var(--color-accent);
    }

    /* Trust Verification Banner */
    .trust-box {
      border: 1px solid var(--border-color);
      border-radius: var(--radius-md);
      padding: var(--space-3);
      display: flex;
      flex-direction: column;
      gap: var(--space-2);
    }

    .trust-box.untrusted {
      border-color: var(--color-warning-border);
      background-color: var(--color-warning-subtle);
    }

    .trust-box.trusted {
      border-color: var(--color-success-border);
      background-color: var(--color-success-subtle);
    }

    /* Activity Stream */
    .activity-list {
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
      position: relative;
    }

    .activity-list::before {
      content: "";
      position: absolute;
      left: 7px;
      top: 6px;
      bottom: 6px;
      width: 1px;
      background: var(--border-color);
    }

    .activity-item {
      display: flex;
      align-items: flex-start;
      gap: var(--space-3);
      position: relative;
      font-size: var(--font-size-xs);
    }

    .activity-dot {
      width: 15px;
      height: 15px;
      border-radius: 50%;
      background: var(--bg-surface);
      border: 2px solid var(--border-color);
      z-index: 1;
      margin-top: 1px;
      flex-shrink: 0;
    }

    .activity-item.is-success .activity-dot {
      border-color: var(--color-success);
    }

    .activity-item.is-warning .activity-dot {
      border-color: var(--color-warning);
    }

    .activity-text {
      color: var(--text-primary);
    }

    .activity-time {
      color: var(--text-muted);
      margin-top: 1px;
      font-family: var(--font-mono);
    }

    /* Toast Notification */
    .toast-pill {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: var(--bg-surface);
      border: 1px solid var(--color-accent-border);
      color: var(--text-primary);
      padding: var(--space-2) var(--space-4);
      border-radius: var(--radius-sm);
      font-size: var(--font-size-xs);
      font-family: var(--font-mono);
      box-shadow: 0 4px 16px rgba(0,0,0,0.6);
      display: none;
      z-index: 1000;
    }
  </style>
</head>
<body>

  <!-- ================= 1. Attached Sidebar (Tabler Standard) ================= -->
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
        <span class="breadcrumb-current" id="header-strategy-breadcrumb">Counter Python</span>
      </div>

      <div class="header-badge-group">
        <span class="badge badge-secondary">PROTOTYPE A · MASTER-DETAIL</span>
        <span class="badge badge-info">
          <span class="badge-dot dot-success"></span>
          <span>MCP LOCAL MODE</span>
        </span>
      </div>
    </header>

    <!-- Master-Detail Workstation Layout -->
    <div class="workstation-container">
      
      <!-- Left Master Pane: Strategy List -->
      <section class="master-pane">
        <div class="master-header">
          <div class="search-input-wrap">
            <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" class="search-input" id="search-strategies" placeholder="搜尋策略名稱或標籤..." oninput="filterStrategies()">
          </div>
          <div class="filter-tabs">
            <button class="filter-btn active" onclick="setFilter('ALL', this)">全部 (3)</button>
            <button class="filter-btn" onclick="setFilter('TRUSTED', this)">已信任 (2)</button>
            <button class="filter-btn" onclick="setFilter('UNTRUSTED', this)">待審核 (1)</button>
          </div>
        </div>

        <div class="master-list" id="master-strategy-list">
          <!-- Dynamically populated by JS -->
        </div>
      </section>

      <!-- Right Detail Pane: Strategy Inspector & Controls -->
      <section class="detail-pane" id="detail-pane">
        <!-- Rendered by renderDetail() -->
      </section>

    </div>
  </main>

  <div class="toast-pill" id="toast-pill">通知訊息</div>

  <script>
    // ==========================================================================
    // Real catOS Strategy Data
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
    let activeFilter = "ALL";

    // ==========================================================================
    // Render Functions
    // ==========================================================================
    function renderMasterList() {
      const listEl = document.getElementById("master-strategy-list");
      const query = (document.getElementById("search-strategies")?.value || "").toLowerCase();

      const filtered = STRATEGY_DATA.filter(s => {
        if (activeFilter === "TRUSTED" && !s.isTrusted) return false;
        if (activeFilter === "UNTRUSTED" && s.isTrusted) return false;
        if (query && !s.name.toLowerCase().includes(query) && !s.version.toLowerCase().includes(query)) return false;
        return true;
      });

      listEl.innerHTML = filtered.map(s => {
        const isSel = s.id === currentStrategyId;
        const shortHash = s.artifactHash.substring(0, 14) + "...";
        return `
          <div class="strategy-item-card ${isSel ? 'is-selected' : ''}" onclick="selectStrategy('${s.id}')">
            <div class="item-header-row">
              <span class="item-name" title="${s.name}">${s.name}</span>
              <span class="item-version-tag">${s.version}</span>
            </div>
            <div class="item-sub-row">
              <span class="hash-preview" title="${s.artifactHash}">${shortHash}</span>
              ${s.isTrusted 
                ? '<span class="badge badge-success"><span class="badge-dot dot-success"></span>已信任</span>' 
                : '<span class="badge badge-warning"><span class="badge-dot dot-warning"></span>待審核</span>'}
            </div>
          </div>
        `;
      }).join('');
    }

    function renderDetail() {
      const s = STRATEGY_DATA.find(x => x.id === currentStrategyId) || STRATEGY_DATA[0];
      const detailEl = document.getElementById("detail-pane");
      document.getElementById("header-strategy-breadcrumb").textContent = s.name;

      detailEl.innerHTML = `
        <!-- Top Headline Card -->
        <div class="card strategy-headline-card">
          <div class="headline-top-row">
            <div class="headline-title-block">
              <h1 class="headline-title">${s.name}</h1>
              <div class="headline-meta-strip">
                <div class="meta-item">
                  <span>版本:</span>
                  <select class="form-select" style="height:22px; font-size:11px; padding:0 6px;" onchange="changeVersion(this.value)">
                    ${s.allVersions.map(v => `<option value="${v}" ${v === s.version ? 'selected' : ''}>${v}</option>`).join('')}
                  </select>
                </div>
                <div class="meta-item">
                  <span>來源:</span>
                  <code style="font-family:var(--font-mono); color:var(--text-primary);">${s.sourceUri}</code>
                </div>
                <div class="meta-item">
                  <span>模式:</span>
                  <span class="badge badge-secondary">${s.mode}</span>
                </div>
                <div class="meta-item">
                  <span>製品指紋:</span>
                  <span class="hash-copyable" onclick="copyHash('${s.artifactHash}')" title="點擊複製完整 SHA-256 指紋">${s.artifactHash.substring(0, 16)}... ⎘</span>
                </div>
              </div>
            </div>

            <div style="text-align:right;">
              ${s.isTrusted 
                ? `<span class="badge badge-success" style="font-size:12px; padding:4px 10px;">
                    <span class="badge-dot dot-success"></span> 代碼已信任 (TRUSTED)
                   </span>
                   <div style="font-size:10.5px; color:var(--text-muted); margin-top:4px;">簽核人: ${s.trustedBy}</div>` 
                : `<span class="badge badge-warning" style="font-size:12px; padding:4px 10px;">
                    <span class="badge-dot dot-warning"></span> 待審查 (UNTRUSTED)
                   </span>
                   <div style="font-size:10.5px; color:var(--color-warning); margin-top:4px;">尚未取得本機運行授權</div>`}
            </div>
          </div>
          <p style="font-size:var(--font-size-sm); color:var(--text-secondary); margin-top:2px;">${s.description}</p>
        </div>

        <!-- Two Column Main Body (Workstation Grid) -->
        <div class="detail-two-col">
          
          <!-- Left Col: Code Card -->
          <div class="card code-box">
            <div class="code-header">
              <div style="display:flex; align-items:center; gap:8px;">
                <span class="badge badge-secondary" style="font-family:var(--font-mono); font-size:10px;">PYTHON</span>
                <span style="font-weight:600; color:var(--text-primary);">strategy.py</span>
                <span>(${s.version})</span>
              </div>
              <button class="btn btn-outline" style="height:22px; font-size:11px; padding:0 8px;" onclick="copyCode()">
                ⎘ 複製代碼
              </button>
            </div>
            <pre class="code-scroll-area"><code>${escapeHtml(s.sourceCode)}</code></pre>
          </div>

          <!-- Right Col: Controls, Trust, Parameters, Bot Binding -->
          <div style="display:flex; flex-direction:column; gap:var(--space-4);">
            
            <!-- 1. Trust Gate Box -->
            <div class="card">
              <div class="card-header">
                <span class="card-title">安全信任審核 (TRUST GATE)</span>
                ${s.isTrusted 
                  ? `<span class="badge badge-success">VERIFIED</span>` 
                  : `<span class="badge badge-warning">AUDIT REQUIRED</span>`}
              </div>
              <div class="card-body">
                ${s.isTrusted ? `
                  <div class="trust-box trusted">
                    <div style="font-weight:600; color:var(--color-success); font-size:12.5px;">✓ 此策略製品已獲本機授權</div>
                    <div style="font-size:11.5px; color:var(--text-secondary);">
                      簽核時間：${s.trustedAt}<br>
                      簽核者：${s.trustedBy}
                    </div>
                    <div style="margin-top:6px;">
                      <button class="btn btn-danger-outline" style="width:100%;" onclick="revokeTrust('${s.id}')">
                        撤銷信任標記 (Revoke Trust)
                      </button>
                    </div>
                  </div>
                ` : `
                  <div class="trust-box untrusted">
                    <div style="font-weight:600; color:var(--color-warning); font-size:12.5px;">⚠ 未受信任策略</div>
                    <div style="font-size:11.5px; color:var(--text-secondary);">
                      依據 catOS 安全邊界規範，未簽核代碼禁止指派至任何本機交易 Bot。
                    </div>
                    <div style="margin-top:8px;">
                      <label class="form-check">
                        <input type="checkbox" id="check-trust-agreement" onchange="toggleTrustButton(this.checked)">
                        <span class="form-check-label" style="font-size:12px; font-weight:500;">我已檢查此版本代碼及其所有依賴</span>
                      </label>
                      <button class="btn btn-primary" id="btn-confirm-trust" style="width:100%; margin-top:8px;" disabled onclick="grantTrust('${s.id}')">
                        確認並簽署信任 (Sign Trust)
                      </button>
                    </div>
                  </div>
                `}
              </div>
            </div>

            <!-- 2. Parameters Card -->
            <div class="card">
              <div class="card-header">
                <span class="card-title">策略參數矩陣 (PARAMETERS)</span>
                <span style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">${s.parameters.length} 項參數</span>
              </div>
              <div style="padding:0;">
                <table class="table-clean">
                  <thead>
                    <tr>
                      <th>參數鍵名</th>
                      <th>型別</th>
                      <th>預設值</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${s.parameters.map(p => `
                      <tr>
                        <td style="font-weight:600; color:var(--text-primary); font-family:var(--font-mono); font-size:11.5px;">${p.key}</td>
                        <td style="color:var(--text-secondary); font-size:11px;">${p.type}</td>
                        <td class="mono-val">${p.val}</td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            </div>

            <!-- 3. Bot Allocation Card -->
            <div class="card">
              <div class="card-header">
                <span class="card-title">分配至本機 Bot (BOT ALLOCATION)</span>
                <a href="javascript:void(0)" onclick="goToBotManager()" style="font-size:11px; color:var(--color-accent); text-decoration:none;">前往機器人管理 &rarr;</a>
              </div>
              <div class="card-body" style="display:flex; flex-direction:column; gap:var(--space-3);">
                <div>
                  <label style="font-size:11px; color:var(--text-secondary); margin-bottom:4px; display:block;">目標 Bot 識別碼 (Bot ID)</label>
                  <div style="display:flex; gap:var(--space-2);">
                    <input type="text" class="form-control" id="input-allocate-bot-id" placeholder="例如: bot-trend-btc" style="flex:1;" ${!s.isTrusted ? 'disabled' : ''}>
                    <button class="btn btn-primary" id="btn-allocate-bot" ${!s.isTrusted ? 'disabled' : ''} onclick="allocateBot('${s.id}')">
                      分配本機 Bot
                    </button>
                  </div>
                  ${!s.isTrusted ? `
                    <div style="font-size:11px; color:var(--color-warning); margin-top:4px;">
                      ※ 需先於上方完成「安全信任審核」方可指派 Bot。
                    </div>
                  ` : ''}
                </div>

                <!-- Existing Bot Bindings -->
                <div style="margin-top:var(--space-2);">
                  <div style="font-size:11px; color:var(--text-muted); margin-bottom:6px; font-weight:600;">已綁定之執行 Bot (${s.botBindings.length})</div>
                  ${s.botBindings.length === 0 ? `
                    <div style="padding:10px; background:var(--bg-app); border:1px solid var(--border-subtle); border-radius:var(--radius-sm); font-size:11.5px; color:var(--text-muted); text-align:center;">
                      目前尚無綁定 Bot。
                    </div>
                  ` : `
                    <div style="display:flex; flex-direction:column; gap:6px;">
                      ${s.botBindings.map(b => `
                        <div style="display:flex; align-items:center; justify-content:space-between; padding:6px 8px; background:var(--bg-surface-subtle); border:1px solid var(--border-color); border-radius:var(--radius-sm);">
                          <div>
                            <div style="font-weight:600; font-family:var(--font-mono); font-size:12px; color:var(--text-primary);">${b.botId}</div>
                            <div style="font-size:10.5px; color:var(--text-muted);">${b.symbol}</div>
                          </div>
                          <div style="display:flex; align-items:center; gap:8px;">
                            ${b.status === 'RUNNING' 
                              ? '<span class="badge badge-success"><span class="badge-dot dot-success"></span>Running</span>' 
                              : '<span class="badge badge-secondary">Stopped</span>'}
                            <button class="btn btn-outline" style="height:20px; font-size:10.5px; padding:0 6px;" onclick="goToBotManager('${b.botId}')">檢視 &rarr;</button>
                          </div>
                        </div>
                      `).join('')}
                    </div>
                  `}
                </div>
              </div>
            </div>

            <!-- 4. Activity Stream Card -->
            <div class="card">
              <div class="card-header">
                <span class="card-title">審計活動軌跡 (ACTIVITY)</span>
              </div>
              <div class="card-body">
                <div class="activity-list">
                  ${s.activity.map(act => `
                    <div class="activity-item is-${act.type}">
                      <div class="activity-dot"></div>
                      <div>
                        <div class="activity-text">${act.title}</div>
                        <div class="activity-time">${act.time}</div>
                      </div>
                    </div>
                  `).join('')}
                </div>
              </div>
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
      renderMasterList();
      renderDetail();
    }

    function setFilter(filter, btn) {
      activeFilter = filter;
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderMasterList();
    }

    function filterStrategies() {
      renderMasterList();
    }

    function toggleTrustButton(isChecked) {
      const btn = document.getElementById("btn-confirm-trust");
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
        showToast("已成功簽署信任標記！可指派 Bot。");
        renderMasterList();
        renderDetail();
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
        showToast("已撤銷信任標記！");
        renderMasterList();
        renderDetail();
      }
    }

    function allocateBot(id) {
      const input = document.getElementById("input-allocate-bot-id");
      const val = (input?.value || "").trim();
      if (!val) {
        showToast("請輸入有效的 Bot 識別碼！");
        if (input) input.focus();
        return;
      }
      const s = STRATEGY_DATA.find(x => x.id === id);
      if (s) {
        s.botBindings.push({
          botId: val,
          status: "STOPPED",
          uptime: "—",
          symbol: "BTC-USDT-SWAP"
        });
        s.activity.unshift({
          title: `指派新 Bot ${val} 至策略 ${s.name} (${s.version})`,
          time: new Date().toISOString().replace('T', ' ').substring(0, 19),
          type: "success"
        });
        showToast(`成功指派 Bot: ${val}`);
        renderDetail();
      }
    }

    function changeVersion(ver) {
      const s = STRATEGY_DATA.find(x => x.id === currentStrategyId);
      if (s) {
        s.version = ver;
        showToast(`已切換版本至 ${ver}`);
        renderDetail();
      }
    }

    function copyHash(hash) {
      navigator.clipboard?.writeText(hash).then(() => {
        showToast("已複製 SHA-256 指紋！");
      }).catch(() => {
        showToast("指紋: " + hash.substring(0, 16) + "...");
      });
    }

    function copyCode() {
      const s = STRATEGY_DATA.find(x => x.id === currentStrategyId);
      if (s && navigator.clipboard) {
        navigator.clipboard.writeText(s.sourceCode).then(() => {
          showToast("已複製 Python 原始碼！");
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
    renderMasterList();
    renderDetail();
  </script>
</body>
</html>
"""

p = pathlib.Path(r'C:\Users\user\Desktop\catOS-Frontend-Final\prototypes\strategy-center-a.html')
p.write_bytes(CONTENT_A.encode('utf-8'))
print("strategy-center-a.html created successfully.")
