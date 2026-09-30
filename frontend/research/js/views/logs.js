/**
 * catOS Prototype - Logs & Audit Viewer (Institutional Diagnostic Terminal)
 * Features:
 * - Multi-dimensional filtering: Modern Segmented Pills, Custom Dark Popover Select, Target/Keyword Search
 * - Fully custom Dark Theme Popover (Zero native OS select elements, zero bright blue artifacts)
 * - Structured Log Row with aligned metadata columns (Prevents vacant whitespace gaps)
 * - Expandable raw JSON technical payload details
 * - Auto-populates filters when deep-linked from Strategy or Bot view
 */

window.LogsView = {
  _sourceDropdownOpen: false,

  render: function(state) {
    const data = window.CATOS_DATA;
    const filter = state.logsFilter || { severity: 'ALL', source: 'ALL', target: '', search: '' };
    const expandedId = state.expandedLogId;
    const isSourceOpen = this._sourceDropdownOpen || false;

    // Severity counts
    const totalCount = data.logs.length;
    const infoCount = data.logs.filter(l => l.severity === 'INFO').length;
    const warnCount = data.logs.filter(l => l.severity === 'WARN').length;
    const errorCount = data.logs.filter(l => l.severity === 'ERROR').length;

    const filteredLogs = data.logs.filter(log => {
      const matchSeverity = filter.severity === 'ALL' || log.severity === filter.severity;
      const matchSource = filter.source === 'ALL' || log.source === filter.source;
      const matchTarget = !filter.target || (log.target && log.target.toLowerCase().includes(filter.target.toLowerCase()));
      const matchSearch = !filter.search || (
        log.summary.toLowerCase().includes(filter.search.toLowerCase()) ||
        JSON.stringify(log.details).toLowerCase().includes(filter.search.toLowerCase())
      );
      return matchSeverity && matchSource && matchTarget && matchSearch;
    });

    const sourceOptions = [
      { id: 'ALL', label: '全部來源模組' },
      { id: 'Supervisor', label: 'Supervisor (主控路由)' },
      { id: 'Worker-01', label: 'Worker-01 (運算核心)' },
      { id: 'RiskEngine', label: 'RiskEngine (風控引擎)' },
      { id: 'MCP-Server', label: 'MCP-Server (外部代理)' }
    ];
    const currentSource = sourceOptions.find(o => o.id === filter.source) || sourceOptions[0];

    return `
      <div class="logs-view-container" onclick="window.LogsView.closeDropdowns(event)">
        <!-- Filter Toolbar -->
        <div class="panel" style="margin-bottom:8px;">
          <div class="panel-body" style="padding:12px 16px;">
            <div class="logs-filter-bar" style="margin-bottom:0;">

              <!-- Search box -->
              <div class="search-box" style="width:230px;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <input type="text" class="form-input" placeholder="搜尋日誌摘要或 Payload..." value="${filter.search || ''}" oninput="window.LogsView.onSearch(this.value)">
              </div>

              <!-- 1. Modern Segmented Pills for Severity Filter (Zero OS Select) -->
              <div class="segmented-pill-group">
                <div class="segmented-pill ${filter.severity === 'ALL' ? 'active-all' : ''}"
                     onclick="window.LogsView.setFilter('severity', 'ALL')">
                  <span>全部</span>
                  <span class="pill-count">${totalCount}</span>
                </div>
                <div class="segmented-pill ${filter.severity === 'INFO' ? 'active-info' : ''}"
                     onclick="window.LogsView.setFilter('severity', 'INFO')">
                  <span>INFO</span>
                  <span class="pill-count">${infoCount}</span>
                </div>
                <div class="segmented-pill ${filter.severity === 'WARN' ? 'active-warn' : ''}"
                     onclick="window.LogsView.setFilter('severity', 'WARN')">
                  <span>WARN</span>
                  <span class="pill-count">${warnCount}</span>
                </div>
                <div class="segmented-pill ${filter.severity === 'ERROR' ? 'active-error' : ''}"
                     onclick="window.LogsView.setFilter('severity', 'ERROR')">
                  <span>ERROR</span>
                  <span class="pill-count">${errorCount}</span>
                </div>
              </div>

              <!-- 2. Custom Dark Popover Select for Source Filter (Zero OS Select) -->
              <div class="custom-select-container">
                <div class="custom-select-trigger ${isSourceOpen ? 'open' : ''}"
                     onclick="event.stopPropagation(); window.LogsView.toggleSourceDropdown();"
                     title="篩選來源模組">
                  <span style="color:var(--text-muted); font-size:11px;">來源:</span>
                  <span style="font-weight:600;">${currentSource.id === 'ALL' ? '全部模組' : currentSource.id}</span>
                  <span class="custom-select-arrow">▼</span>
                </div>

                <div class="custom-select-dropdown ${isSourceOpen ? 'open' : ''}" onclick="event.stopPropagation();">
                  ${sourceOptions.map(opt => `
                    <div class="custom-select-option ${filter.source === opt.id ? 'selected' : ''}"
                         onclick="window.LogsView.selectSource('${opt.id}')">
                      <span>${opt.label}</span>
                      ${filter.source === opt.id ? '<span class="custom-select-option-check">✓</span>' : ''}
                    </div>
                  `).join('')}
                </div>
              </div>

              <!-- 3. Target/Bot Filter -->
              <div style="display:flex; align-items:center; gap:6px;">
                <span style="font-size:11.5px; color:var(--text-muted); font-family:var(--font-mono);">關聯目標:</span>
                <input type="text" class="form-input mono" style="width:130px; height:30px;" placeholder="Bot / 策略 ID" value="${filter.target || ''}" oninput="window.LogsView.setFilter('target', this.value)">
              </div>

              <!-- Clear Filters -->
              ${(filter.severity !== 'ALL' || filter.source !== 'ALL' || filter.target || filter.search) ? `
                <button class="btn btn-sm btn-ghost" onclick="window.LogsView.clearFilters()" style="height:30px; padding:0 8px; font-size:11.5px;">清除篩選</button>
              ` : ''}

              <!-- Count Status -->
              <div style="margin-left:auto; font-size:12px; color:var(--text-muted); display:flex; align-items:center; gap:4px;">
                <span>顯示</span>
                <span class="num" style="color:var(--gold-primary); font-weight:700;">${filteredLogs.length}</span>
                <span>/ ${totalCount} 條日誌</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Log List (Structured Columns Eliminates Vacant Space) -->
        <div class="panel">
          <div class="panel-body" style="padding:0;">
            ${filteredLogs.length > 0 ? filteredLogs.map(log => `
              <div class="log-entry-row ${expandedId === log.id ? 'expanded' : ''}" onclick="window.LogsView.toggleExpand('${log.id}')">
                <div class="log-entry-header">
                  <!-- Col 1: Severity Badge -->
                  <div class="log-col-sev">
                    <span class="badge ${log.severity === 'INFO' ? 'badge-cyan' : (log.severity === 'WARN' ? 'badge-amber' : 'badge-red')}" style="width:100%; justify-content:center;">
                      ${log.severity}
                    </span>
                  </div>

                  <!-- Col 2: Timestamp -->
                  <div class="log-col-time">${log.timestamp}</div>

                  <!-- Col 3: Source Module -->
                  <div class="log-col-source">
                    <span class="badge" style="width:100%; justify-content:center; font-family:var(--font-mono);">${log.source}</span>
                  </div>

                  <!-- Col 4: Target Bot / Strategy -->
                  <div class="log-col-target">
                    ${log.target ? `<span class="strat-version" style="font-size:11px;">${log.target}</span>` : `<span style="color:var(--text-muted); font-size:11px; padding-left:4px;">—</span>`}
                  </div>

                  <!-- Col 5: Event Summary + Category Tag -->
                  <div class="log-col-summary">
                    <span>${log.summary}</span>
                    <span class="log-category-tag">${log.category}</span>
                  </div>

                  <!-- Col 6: Action Button -->
                  <div class="log-col-action">
                    <button class="log-expand-btn" onclick="event.stopPropagation(); window.LogsView.toggleExpand('${log.id}');">
                      <span>JSON</span>
                      <span style="font-size:9px;">${expandedId === log.id ? '▲' : '▼'}</span>
                    </button>
                  </div>
                </div>

                <!-- Expanded Technical JSON Payload -->
                ${expandedId === log.id ? `
                  <div class="log-details-box" onclick="event.stopPropagation();">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; padding-bottom:6px; border-bottom:1px solid var(--border-subtle); font-size:11.5px; color:var(--gold-primary);">
                      <div style="display:flex; align-items:center; gap:8px;">
                        <span style="font-weight:600;">結構化技術 Payload (JSON)</span>
                        <span class="badge badge-gold" style="font-size:10px;">ID: ${log.id}</span>
                      </div>
                      <span class="num" style="color:var(--text-secondary);">Event: ${log.category}</span>
                    </div>
                    <pre class="code-text" style="font-size:11.5px; line-height:1.5; overflow-x:auto; margin:0;">${escapeHtml(JSON.stringify(log.details, null, 2))}</pre>
                  </div>
                ` : ''}
              </div>
            `).join('') : `
              <div class="empty-state-notice" style="padding:36px;">
                <div class="title">無符合條件之日誌</div>
                <div style="font-size:12px;">請調整上方嚴重度膠囊、來源篩選器或清空搜尋關鍵字。</div>
              </div>
            `}
          </div>
        </div>
      </div>
    `;
  },

  toggleSourceDropdown: function() {
    this._sourceDropdownOpen = !this._sourceDropdownOpen;
    window.appState.notify();
  },

  selectSource: function(sourceId) {
    this._sourceDropdownOpen = false;
    this.setFilter('source', sourceId);
  },

  closeDropdowns: function(e) {
    if (this._sourceDropdownOpen) {
      this._sourceDropdownOpen = false;
      window.appState.notify();
    }
  },

  onSearch: function(val) {
    const filter = Object.assign({}, window.appState.get('logsFilter'));
    filter.search = val;
    window.appState.set({ logsFilter: filter }, false);
    clearTimeout(this._searchTimer);
    this._searchTimer = setTimeout(() => {
      window.appState.notify();
    }, 200);
  },

  setFilter: function(field, val) {
    const filter = Object.assign({}, window.appState.get('logsFilter'));
    filter[field] = val;
    window.appState.set({ logsFilter: filter });
  },

  clearFilters: function() {
    this._sourceDropdownOpen = false;
    window.appState.set({
      logsFilter: { severity: 'ALL', source: 'ALL', target: '', search: '' }
    });
  },

  toggleExpand: function(logId) {
    const curr = window.appState.get('expandedLogId');
    window.appState.set({ expandedLogId: curr === logId ? null : logId });
  }
};
