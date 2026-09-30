/**
 * catOS Prototype - Pure SVG Chart Engine
 * Lightweight, zero-dependency, ultra crisp vector charts.
 * Adheres strictly to visual constraints:
 * - Controlled height (does not exceed 50% of viewport content height).
 * - Separates production/demo equity from backtest curves explicitly.
 * - Monospace axis markers and clean tooltips.
 */

window.ChartEngine = {
  /**
   * Render Dashboard Equity Curve
   */
  renderDashboardEquity: function(containerId, timeRange = '30D', scenario = 'active') {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (scenario === 'empty') {
      container.innerHTML = `
        <div style="height:100%; display:flex; flex-direction:column; align-items:center; justify-content:center; color:var(--text-muted); border:1px dashed var(--border-default); border-radius:var(--border-radius);">
          <span style="font-size:13px; font-weight:500; margin-bottom:4px;">尚無運行帳戶資產曲線</span>
          <span style="font-size:11px;">請先由策略中心建立回測並配置啟動 Bot</span>
        </div>
      `;
      return;
    }

    // Dataset based on time range
    const pointsMap = {
      '7D': [
        { label: '09-23', val: 122100 },
        { label: '09-24', val: 123400 },
        { label: '09-25', val: 122800 },
        { label: '09-26', val: 124100 },
        { label: '09-27', val: 123900 },
        { label: '09-28', val: 124600 },
        { label: '09-29', val: 125480.5 }
      ],
      '30D': [
        { label: '09-01', val: 114500 },
        { label: '09-06', val: 116200 },
        { label: '09-11', val: 115100 },
        { label: '09-16', val: 118400 },
        { label: '09-21', val: 121000 },
        { label: '09-26', val: 123800 },
        { label: '09-29', val: 125480.5 }
      ],
      '90D': [
        { label: '07-01', val: 100000 },
        { label: '07-20', val: 104200 },
        { label: '08-10', val: 108900 },
        { label: '08-30', val: 112400 },
        { label: '09-15', val: 119500 },
        { label: '09-29', val: 125480.5 }
      ]
    };

    const data = pointsMap[timeRange] || pointsMap['30D'];
    const minVal = Math.min(...data.map(d => d.val)) * 0.985;
    const maxVal = Math.max(...data.map(d => d.val)) * 1.015;

    const width = Math.max(300, container.clientWidth || 600);
    const height = Math.max(160, container.clientHeight || 200);
    const padding = { top: 15, right: 20, bottom: 25, left: 65 };

    const plotW = width - padding.left - padding.right;
    const plotH = height - padding.top - padding.bottom;

    const getX = (idx) => padding.left + (idx / (data.length - 1)) * plotW;
    const getY = (val) => padding.top + plotH - ((val - minVal) / (maxVal - minVal)) * plotH;

    let pathD = `M ${getX(0)} ${getY(data[0].val)}`;
    let areaD = `M ${getX(0)} ${padding.top + plotH} L ${getX(0)} ${getY(data[0].val)}`;

    data.forEach((d, i) => {
      if (i > 0) {
        // Smooth bezier curve
        const prevX = getX(i - 1);
        const prevY = getY(data[i - 1].val);
        const currX = getX(i);
        const currY = getY(d.val);
        const cpX1 = prevX + (currX - prevX) / 2;
        const cpX2 = cpX1;
        pathD += ` C ${cpX1} ${prevY}, ${cpX2} ${currY}, ${currX} ${currY}`;
        areaD += ` C ${cpX1} ${prevY}, ${cpX2} ${currY}, ${currX} ${currY}`;
      }
    });

    areaD += ` L ${getX(data.length - 1)} ${padding.top + plotH} Z`;

    // Horizontal grid lines
    const gridLines = [0.25, 0.5, 0.75].map(ratio => {
      const y = padding.top + plotH * ratio;
      const val = (maxVal - ratio * (maxVal - minVal)).toFixed(0);
      return `
        <line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="var(--border-subtle)" stroke-dasharray="3,3" />
        <text x="${padding.left - 8}" y="${y + 3}" fill="var(--text-muted)" font-size="10" font-family="var(--font-mono)" text-anchor="end">${Number(val).toLocaleString()} </text>
      `;
    }).join('');

    // X axis labels
    const xLabels = data.map((d, i) => `
      <text x="${getX(i)}" y="${height - 6}" fill="var(--text-muted)" font-size="10" font-family="var(--font-mono)" text-anchor="middle">${d.label}</text>
    `).join('');

    container.innerHTML = `
      <svg width="100%" height="100%" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="overflow:visible; display:block;">
        <defs>
          <linearGradient id="goldGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#d4af37" stop-opacity="0.28"/>
            <stop offset="100%" stop-color="#d4af37" stop-opacity="0.0"/>
          </linearGradient>
        </defs>
        ${gridLines}
        <path d="${areaD}" fill="url(#goldGradient)" />
        <path d="${pathD}" fill="none" stroke="#d4af37" stroke-width="2" stroke-linecap="round" />
        ${xLabels}
        <!-- Last point dot -->
        <circle cx="${getX(data.length - 1)}" cy="${getY(data[data.length - 1].val)}" r="3.5" fill="#d4af37" stroke="#000" stroke-width="1.5" />
      </svg>
    `;
  },

  /**
   * Render Multi-Dimensional Alpha Comparison Chart (Portfolio vs BTC Benchmark)
   */
  renderDashboardAlphaComparison: function(containerId, timeRange = '30D') {
    const container = document.getElementById(containerId);
    if (!container) return;

    const data = [
      { label: '09-01', portPct: 0.0, btcPct: 0.0 },
      { label: '09-06', portPct: 1.5, btcPct: -2.1 },
      { label: '09-11', portPct: 0.6, btcPct: -3.8 },
      { label: '09-16', portPct: 3.4, btcPct: -1.2 },
      { label: '09-21', portPct: 5.7, btcPct: 1.0 },
      { label: '09-26', portPct: 8.1, btcPct: 2.4 },
      { label: '09-29', portPct: 9.6, btcPct: 3.1 }
    ];

    const width = container.clientWidth || 600;
    const height = 190;
    const padding = { top: 20, right: 30, bottom: 25, left: 60 };

    const plotW = width - padding.left - padding.right;
    const plotH = height - padding.top - padding.bottom;

    const minPct = -5.0;
    const maxPct = 12.0;

    const getX = (i) => padding.left + (i / (data.length - 1)) * plotW;
    const getY = (val) => padding.top + plotH - ((val - minPct) / (maxPct - minPct)) * plotH;
    const zeroY = getY(0);

    // Portfolio Path (Gold)
    let portD = `M ${getX(0)} ${getY(data[0].portPct)}`;
    data.forEach((d, i) => { if (i > 0) portD += ` L ${getX(i)} ${getY(d.portPct)}`; });

    // BTC Benchmark Path (Cyan / Dashed)
    let btcD = `M ${getX(0)} ${getY(data[0].btcPct)}`;
    data.forEach((d, i) => { if (i > 0) btcD += ` L ${getX(i)} ${getY(d.btcPct)}`; });

    const xLabels = data.map((d, i) => `
      <text x="${getX(i)}" y="${height - 6}" fill="var(--text-muted)" font-size="10" font-family="var(--font-mono)" text-anchor="middle">${d.label}</text>
    `).join('');

    container.innerHTML = `
      <svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
        <!-- Zero Benchmark Baseline -->
        <line x1="${padding.left}" y1="${zeroY}" x2="${width - padding.right}" y2="${zeroY}" stroke="var(--border-focus)" stroke-dasharray="2,2" />
        <text x="${padding.left - 6}" y="${zeroY + 3}" fill="var(--text-muted)" font-size="9" font-family="var(--font-mono)" text-anchor="end">0.0%</text>

        <text x="${padding.left - 6}" y="${padding.top + 8}" fill="var(--color-green)" font-size="9" font-family="var(--font-mono)" text-anchor="end">+12%</text>
        <text x="${padding.left - 6}" y="${padding.top + plotH}" fill="var(--color-red)" font-size="9" font-family="var(--font-mono)" text-anchor="end">-5%</text>

        <!-- BTC Path -->
        <path d="${btcD}" fill="none" stroke="#38bdf8" stroke-width="1.6" stroke-dasharray="4,4" opacity="0.75" />

        <!-- Portfolio Alpha Path -->
        <path d="${portD}" fill="none" stroke="#d4af37" stroke-width="2.2" stroke-linecap="round" />

        ${xLabels}

        <!-- Legend inside chart -->
        <g transform="translate(${padding.left + 10}, ${padding.top + 8})">
          <circle cx="4" cy="4" r="3" fill="#d4af37" />
          <text x="12" y="7" fill="var(--gold-primary)" font-size="10.5" font-family="var(--font-sans)" font-weight="600">catOS 投資組合 (+9.6%)</text>

          <line x1="140" y1="4" x2="155" y2="4" stroke="#38bdf8" stroke-dasharray="3,3" stroke-width="2" />
          <text x="162" y="7" fill="#38bdf8" font-size="10.5" font-family="var(--font-sans)">BTC 基準 (+3.1% | Alpha: +6.5%)</text>
        </g>
      </svg>
    `;
  },

  /**
   * Render Micro Sparkline (for tables and cards)
   */
  renderSparkline: function(containerId, points, color = '#d4af37') {
    const el = document.getElementById(containerId);
    if (!el || !points || points.length === 0) return;
    const min = Math.min(...points);
    const max = Math.max(...points) || 1;
    const w = 70;
    const h = 20;
    const getX = (i) => (i / (points.length - 1)) * w;
    const getY = (val) => h - ((val - min) / (max - min || 1)) * (h - 4) - 2;

    let path = `M 0 ${getY(points[0])}`;
    for (let i = 1; i < points.length; i++) {
      path += ` L ${getX(i)} ${getY(points[i])}`;
    }

    el.innerHTML = `
      <svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
        <path d="${path}" fill="none" stroke="${color}" stroke-width="1.4" stroke-linecap="round" />
      </svg>
    `;
  },

  /**
   * Render Backtest Dual Curve (Equity + Drawdown)
   * Controlled height strictly under 50% viewport content (around 190px total).
   */
  renderBacktestDualChart: function(containerId, equityCurveData) {
    const container = document.getElementById(containerId);
    if (!container || !equityCurveData || equityCurveData.length === 0) return;

    const width = container.clientWidth || 700;
    const height = 180;
    const padding = { top: 12, right: 25, bottom: 22, left: 65 };

    const plotW = width - padding.left - padding.right;
    // Top 70% for Equity, Bottom 30% for Drawdown
    const eqH = 105;
    const ddH = 45;
    const gap = 8;

    const eqValues = equityCurveData.map(d => d.equity);
    const ddValues = equityCurveData.map(d => d.drawdown);

    const minEq = Math.min(...eqValues) * 0.98;
    const maxEq = Math.max(...eqValues) * 1.02;

    const minDd = Math.min(...ddValues, -15); // Drawdown is negative
    const maxDd = 0;

    const getX = (idx) => padding.left + (idx / (equityCurveData.length - 1)) * plotW;
    const getEqY = (val) => padding.top + eqH - ((val - minEq) / (maxEq - minEq)) * eqH;
    const getDdY = (val) => padding.top + eqH + gap + ddH - ((val - minDd) / (maxDd - minDd)) * ddH;

    // Build Equity Path
    let eqPath = `M ${getX(0)} ${getEqY(equityCurveData[0].equity)}`;
    let eqArea = `M ${getX(0)} ${padding.top + eqH} L ${getX(0)} ${getEqY(equityCurveData[0].equity)}`;

    equityCurveData.forEach((d, i) => {
      if (i > 0) {
        eqPath += ` L ${getX(i)} ${getEqY(d.equity)}`;
        eqArea += ` L ${getX(i)} ${getEqY(d.equity)}`;
      }
    });
    eqArea += ` L ${getX(equityCurveData.length - 1)} ${padding.top + eqH} Z`;

    // Build Drawdown Path (Underwater chart)
    const zeroDdY = getDdY(0);
    let ddPath = `M ${getX(0)} ${getDdY(equityCurveData[0].drawdown)}`;
    let ddArea = `M ${getX(0)} ${zeroDdY} L ${getX(0)} ${getDdY(equityCurveData[0].drawdown)}`;

    equityCurveData.forEach((d, i) => {
      if (i > 0) {
        ddPath += ` L ${getX(i)} ${getDdY(d.drawdown)}`;
        ddArea += ` L ${getX(i)} ${getDdY(d.drawdown)}`;
      }
    });
    ddArea += ` L ${getX(equityCurveData.length - 1)} ${zeroDdY} Z`;

    // Date labels
    const dateLabels = equityCurveData.filter((_, i) => i % 2 === 0 || i === equityCurveData.length - 1).map(d => {
      const idx = equityCurveData.indexOf(d);
      return `<text x="${getX(idx)}" y="${height - 4}" fill="var(--text-muted)" font-size="9.5" font-family="var(--font-mono)" text-anchor="middle">${d.date}</text>`;
    }).join('');

    container.innerHTML = `
      <svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
        <defs>
          <linearGradient id="btEqGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#d4af37" stop-opacity="0.22"/>
            <stop offset="100%" stop-color="#d4af37" stop-opacity="0.0"/>
          </linearGradient>
          <linearGradient id="btDdGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#f87171" stop-opacity="0.05"/>
            <stop offset="100%" stop-color="#f87171" stop-opacity="0.35"/>
          </linearGradient>
        </defs>

        <!-- Divider line between equity & drawdown -->
        <line x1="${padding.left}" y1="${padding.top + eqH + gap/2}" x2="${width - padding.right}" y2="${padding.top + eqH + gap/2}" stroke="var(--border-subtle)" />

        <!-- Equity Axis labels -->
        <text x="${padding.left - 6}" y="${padding.top + 10}" fill="var(--text-muted)" font-size="9" font-family="var(--font-mono)" text-anchor="end">${(maxEq/1000).toFixed(1)}k</text>
        <text x="${padding.left - 6}" y="${padding.top + eqH}" fill="var(--text-muted)" font-size="9" font-family="var(--font-mono)" text-anchor="end">${(minEq/1000).toFixed(1)}k</text>

        <!-- Drawdown Axis labels -->
        <text x="${padding.left - 6}" y="${zeroDdY + 3}" fill="var(--text-muted)" font-size="9" font-family="var(--font-mono)" text-anchor="end">0%</text>
        <text x="${padding.left - 6}" y="${padding.top + eqH + gap + ddH}" fill="var(--color-red)" font-size="9" font-family="var(--font-mono)" text-anchor="end">${minDd.toFixed(0)}%</text>

        <!-- Equity Line & Area -->
        <path d="${eqArea}" fill="url(#btEqGrad)" />
        <path d="${eqPath}" fill="none" stroke="#d4af37" stroke-width="1.8" />

        <!-- Drawdown Line & Area -->
        <path d="${ddArea}" fill="url(#btDdGrad)" />
        <path d="${ddPath}" fill="none" stroke="#f87171" stroke-width="1.2" />

        <!-- Zero Drawdown line -->
        <line x1="${padding.left}" y1="${zeroDdY}" x2="${width - padding.right}" y2="${zeroDdY}" stroke="var(--border-default)" stroke-dasharray="2,2" />

        ${dateLabels}
      </svg>
    `;
  }
};
