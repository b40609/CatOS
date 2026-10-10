<script setup lang="ts">
import { ref, computed } from 'vue';

type DashboardRange = '1D' | '7D' | '30D' | 'YTD';
const selectedRange = ref<DashboardRange>('30D');
const ranges: DashboardRange[] = ['1D', '7D', '30D', 'YTD'];

const rangeDays: Record<DashboardRange, number> = { '1D': 1, '7D': 7, '30D': 30, YTD: 283 };
const rangeReturns: Record<DashboardRange, number> = { '1D': 0.0047, '7D': 0.0382, '30D': 0.1246, YTD: 0.348 };

// 1:1 mathematical formula ported directly from Lovable terminal.ts
const series = computed(() => {
  const range = selectedRange.value;
  const end = 12_483_920;
  const start = end / (1 + rangeReturns[range]);
  let peak = start;
  const count = 72;
  const out: { label: string; equity: number; drawdown: number; x: number; yEq: number; yDd: number }[] = [];

  const leftMargin = 55;
  const rightMargin = 555;
  const chartWidth = rightMargin - leftMargin;

  // Domain min/max
  const eqMin = start * 0.985;
  const eqMax = end * 1.025;
  const eqSpan = eqMax - eqMin;

  for (let i = 0; i < count; i++) {
    const t = i / (count - 1);
    const wave = (Math.sin(i * 0.71) * 0.32 + Math.sin(i * 0.21) * 0.64) * Math.sin(t * Math.PI);
    const equity = Math.round(start + (end - start) * (t + wave * 0.14));
    peak = Math.max(peak, equity);
    const date = new Date(Date.UTC(2026, 9, 10) - (1 - t) * rangeDays[range] * 86400000);
    const label = range === '1D' ? date.toISOString().slice(11, 16) : date.toISOString().slice(5, 10).replace('-', '/');
    const drawdown = Number(((equity / peak - 1) * 100).toFixed(3));

    const x = leftMargin + t * chartWidth;
    // Map equity from eqMin -> eqMax to y: 155 -> 22
    const yEq = 155 - ((equity - eqMin) / eqSpan) * 133;
    // Map drawdown 0% -> -8% to y: 175 -> 205
    const yDd = 175 + (Math.abs(drawdown) / 8) * 30;

    out.push({ label, equity, drawdown, x, yEq, yDd });
  }
  return out;
});

const returnPctText = computed(() => {
  const ret = rangeReturns[selectedRange.value] * 100;
  return `+${ret.toFixed(2)}%`;
});

const equityPath = computed(() => {
  if (!series.value.length) return '';
  return series.value.reduce((acc, p, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.yEq.toFixed(1)}`, '');
});

const equityAreaPath = computed(() => {
  if (!series.value.length) return '';
  const first = series.value[0];
  const last = series.value[series.value.length - 1];
  return `${equityPath.value} L ${last.x.toFixed(1)},172 L ${first.x.toFixed(1)},172 Z`;
});

const drawdownPath = computed(() => {
  if (!series.value.length) return '';
  return series.value.reduce((acc, p, i) => `${acc} ${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.yDd.toFixed(1)}`, '');
});

const drawdownAreaPath = computed(() => {
  if (!series.value.length) return '';
  const first = series.value[0];
  const last = series.value[series.value.length - 1];
  return `${drawdownPath.value} L ${last.x.toFixed(1)},175 L ${first.x.toFixed(1)},175 Z`;
});

// X-axis ticks (5 evenly spaced date labels)
const xTicks = computed(() => {
  if (!series.value.length) return [];
  const s = series.value;
  return [
    { label: s[0].label, x: s[0].x },
    { label: s[Math.floor(s.length * 0.25)].label, x: s[Math.floor(s.length * 0.25)].x },
    { label: s[Math.floor(s.length * 0.5)].label, x: s[Math.floor(s.length * 0.5)].x },
    { label: s[Math.floor(s.length * 0.75)].label, x: s[Math.floor(s.length * 0.75)].x },
    { label: s[s.length - 1].label, x: s[s.length - 1].x }
  ];
});
</script>

<template>
  <div class="relaxed-equity-card">
    <div class="card-top-header">
      <div class="header-left">
        <h3 class="card-title">Equity & Drawdown</h3>
      </div>
      <div class="range-tabs">
        <button
          v-for="r in ranges"
          :key="r"
          type="button"
          class="range-btn num"
          :class="{ active: selectedRange === r }"
          @click="selectedRange = r"
        >
          {{ r }}
        </button>
      </div>
    </div>

    <div class="stats-headline">
      <div class="val-group">
        <div class="val-row">
          <span class="main-val num">12,483,920.00</span>
          <span class="val-unit">USDT</span>
        </div>
        <p class="growth-sub num text-up">
          {{ returnPctText }} <span class="period-text">this period</span>
        </p>
      </div>

      <div class="legend-group">
        <span class="legend-item">
          <span class="legend-bar bg-equity"></span>
          Equity
        </span>
        <span class="legend-item">
          <span class="legend-bar bg-drawdown"></span>
          Drawdown
        </span>
      </div>
    </div>

    <div class="chart-viewport">
      <svg viewBox="0 0 600 215" preserveAspectRatio="none" class="chart-svg">
        <defs>
          <linearGradient id="eq-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--os-up)" stop-opacity="0.22" />
            <stop offset="100%" stop-color="var(--os-up)" stop-opacity="0.01" />
          </linearGradient>
          <linearGradient id="dd-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="var(--os-down)" stop-opacity="0.03" />
            <stop offset="100%" stop-color="var(--os-down)" stop-opacity="0.20" />
          </linearGradient>
        </defs>

        <!-- Y-axis gridlines & labels (Equity Left) -->
        <g class="grid-lines">
          <line x1="55" y1="30" x2="555" y2="30" stroke="var(--os-border)" stroke-dasharray="3 4" stroke-opacity="0.6" />
          <text x="48" y="33" text-anchor="end" fill="var(--os-text-muted)" font-size="9" class="num">12.6M</text>

          <line x1="55" y1="75" x2="555" y2="75" stroke="var(--os-border)" stroke-dasharray="3 4" stroke-opacity="0.6" />
          <text x="48" y="78" text-anchor="end" fill="var(--os-text-muted)" font-size="9" class="num">12.2M</text>

          <line x1="55" y1="120" x2="555" y2="120" stroke="var(--os-border)" stroke-dasharray="3 4" stroke-opacity="0.6" />
          <text x="48" y="123" text-anchor="end" fill="var(--os-text-muted)" font-size="9" class="num">11.8M</text>

          <line x1="55" y1="155" x2="555" y2="155" stroke="var(--os-border)" stroke-dasharray="3 4" stroke-opacity="0.6" />
          <text x="48" y="158" text-anchor="end" fill="var(--os-text-muted)" font-size="9" class="num">11.5M</text>

          <!-- Drawdown Right Y-axis labels -->
          <line x1="55" y1="175" x2="555" y2="175" stroke="var(--os-border)" stroke-opacity="0.8" />
          <text x="562" y="178" text-anchor="start" fill="var(--os-text-muted)" font-size="8.5" class="num">0%</text>
          <text x="562" y="195" text-anchor="start" fill="var(--os-text-muted)" font-size="8.5" class="num">-4%</text>
        </g>

        <!-- Drawdown Area & Line -->
        <path :d="drawdownAreaPath" fill="url(#dd-grad)" />
        <path :d="drawdownPath" fill="none" stroke="var(--os-down)" stroke-width="1.2" stroke-opacity="0.75" />

        <!-- Equity Area & Line -->
        <path :d="equityAreaPath" fill="url(#eq-grad)" />
        <path :d="equityPath" fill="none" stroke="var(--os-up)" stroke-width="2" stroke-linejoin="round" />

        <!-- X-axis date labels along bottom -->
        <g class="x-ticks">
          <text
            v-for="(t, idx) in xTicks"
            :key="idx"
            :x="t.x"
            y="208"
            :text-anchor="idx === 0 ? 'start' : idx === xTicks.length - 1 ? 'end' : 'middle'"
            fill="var(--os-text-muted)"
            font-size="9"
            class="num"
          >
            {{ t.label }}
          </text>
        </g>
      </svg>
    </div>

    <div class="card-bottom-footer">
      <span class="footer-note">Portfolio performance · {{ selectedRange }}</span>
      <span class="live-status">
        <span class="live-dot"></span>
        Updated just now
      </span>
    </div>
  </div>
</template>

<style scoped>
.relaxed-equity-card {
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: var(--os-card-radius, 6px);
  padding: 1.15rem 1.35rem 0.95rem 1.35rem;
  display: flex;
  flex-direction: column;
}

.card-top-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
  border-bottom: 1px solid var(--os-border);
  padding-bottom: 0.75rem;
  margin: -1.15rem -1.35rem 0.85rem -1.35rem;
  padding: 0.75rem 1.35rem;
}

.card-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--os-text-primary);
}

.range-tabs {
  display: flex;
  background: var(--os-bg-base);
  border-radius: 4px;
  padding: 2px;
  gap: 2px;
}

.range-btn {
  background: transparent;
  border: none;
  color: var(--os-text-muted);
  font-size: 10px;
  height: 24px;
  padding: 0 8px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.range-btn:hover {
  color: var(--os-text-primary);
}

.range-btn.active {
  background: var(--os-bg-card-hover);
  color: var(--os-text-primary);
  font-weight: 500;
}

.stats-headline {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 0.85rem;
}

.val-group {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.val-row {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
}

.main-val {
  font-size: 20px;
  font-weight: 500;
  color: var(--os-text-primary);
  line-height: 1.2;
}

.val-unit {
  font-size: 10px;
  color: var(--os-text-muted);
}

.growth-sub {
  font-size: 10px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.period-text {
  font-size: 10px;
  color: var(--os-text-muted);
  font-weight: 400;
}

.legend-group {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding-top: 0.35rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 9px;
  color: var(--os-text-muted);
}

.legend-bar {
  display: inline-block;
  width: 12px;
  height: 2px;
  border-radius: 1px;
}

.bg-equity {
  background: var(--os-up);
}

.bg-drawdown {
  background: var(--os-down);
}

.chart-viewport {
  width: 100%;
  height: 230px;
}

.chart-svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}

.card-bottom-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.65rem;
  padding-top: 0.65rem;
  border-top: 1px solid var(--os-border);
}

.footer-note {
  font-size: 10px;
  color: var(--os-text-muted);
}

.live-status {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 9px;
  color: var(--os-text-muted);
}

.live-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--os-up);
}

.text-up {
  color: var(--os-up);
}
</style>
