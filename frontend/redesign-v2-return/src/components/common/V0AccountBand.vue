<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import {
  useV0Engine,
  PERIODS,
  PERIOD_LABEL,
  timeAt,
  formatPct,
  formatTime,
  equitySeries,
  type Period,
  type Bot
} from '@/state/v0-engine';

const props = withDefaults(
  defineProps<{
    showHeader?: boolean;
  }>(),
  {
    showHeader: true
  }
);

const {
  snapshot: snap,
  series,
  period,
  periodView: periodSum,
  bots,
  focusBotId,
  setPeriod
} = useV0Engine();

const chartContainer = ref<HTMLDivElement | null>(null);
const chartWidth = ref(600);
const hoverIdx = ref<number | null>(null);

function updateWidth() {
  if (chartContainer.value) {
    chartWidth.value = chartContainer.value.clientWidth || 600;
  }
}

let resizeObs: ResizeObserver | null = null;
onMounted(() => {
  updateWidth();
  if (chartContainer.value) {
    resizeObs = new ResizeObserver(() => updateWidth());
    resizeObs.observe(chartContainer.value);
  }
});

onUnmounted(() => {
  if (resizeObs) resizeObs.disconnect();
});

const height = 210;
const axisW = 54;
const xAxisH = 18;
const gap = 10;
const plotW = computed(() => Math.max(1, chartWidth.value - axisW));
const topH = Math.round((height - xAxisH - gap) * 0.68);
const ddTop = topH + gap;
const ddH = height - xAxisH - gap - topH;

const ddLimit = -15; // 帳戶最大回撤上限 -15%

// 焦點機器人
const focusBot = computed(() => bots.value.find((b: Bot) => b.id === focusBotId.value));

function formatUsd(v: number, withSign = false, decimals = 2) {
  if (Number.isNaN(v)) return '—';
  const sign = withSign && v > 0 ? '+' : withSign && v < 0 ? '−' : '';
  return `${sign}$${Math.abs(v).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  })}`;
}

function toneOf(v: number) {
  if (v > 0) return 'text-gain font-semibold';
  if (v < 0) return 'text-risk font-semibold';
  return 'text-muted-foreground';
}

function niceStep(span: number) {
  const raw = span / 3;
  const mag = 10 ** Math.floor(Math.log10(raw || 1));
  const n = raw / mag;
  return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * mag;
}

const n = computed(() => periodSum.value.indices.length);
const base = computed(() => series.value[periodSum.value.baseIndex] || 1);

const validPoints = computed(() => periodSum.value.points.filter((v: number) => !Number.isNaN(v)));

const yBounds = computed(() => {
  const pts = validPoints.value;
  let lo = Math.min(0, ...pts);
  let hi = Math.max(0, ...pts);
  const span = hi - lo || 1;
  hi += span * 0.14;
  lo -= span * 0.14;
  const step = niceStep(hi - lo);
  const ticks: number[] = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) {
    ticks.push(Number(t.toFixed(4)));
  }
  return { lo, hi, ticks, step };
});

const minDD = computed(() => Math.min(-0.5, ...periodSum.value.dd.filter((v: number) => !Number.isNaN(v))));
const limitVisible = computed(() => ddLimit >= minDD.value * 1.8);
const ddMin = computed(() => (limitVisible.value ? Math.min(minDD.value * 1.25, ddLimit * 1.12) : minDD.value * 1.3));

function getX(k: number) {
  return n.value > 1 ? (k / (n.value - 1)) * plotW.value : 0;
}

function getY(v: number) {
  const { lo, hi } = yBounds.value;
  return 4 + ((hi - v) / (hi - lo)) * (topH - 8);
}

function getYd(v: number) {
  return ddTop + (v / (ddMin.value || 1)) * ddH;
}

function generateLine(vals: number[], fy: (v: number) => number) {
  let d = '';
  let pen = false;
  vals.forEach((v, k) => {
    if (Number.isNaN(v)) {
      pen = false;
      return;
    }
    d += `${pen ? 'L' : 'M'}${getX(k).toFixed(1)},${fy(v).toFixed(1)}`;
    pen = true;
  });
  return d;
}

const eqLinePath = computed(() => generateLine(periodSum.value.points, getY));

const eqAreaPath = computed(() => {
  const firstK = periodSum.value.points.findIndex((v: number) => !Number.isNaN(v));
  if (firstK < 0) return '';
  return `${eqLinePath.value}L${getX(n.value - 1).toFixed(1)},${getY(0).toFixed(1)}L${getX(firstK).toFixed(1)},${getY(0).toFixed(1)}Z`;
});

const ddLinePath = computed(() => generateLine(periodSum.value.dd, getYd));

const ddAreaPath = computed(() => {
  const firstK = periodSum.value.points.findIndex((v: number) => !Number.isNaN(v));
  if (firstK < 0) return '';
  return `${ddLinePath.value}L${getX(n.value - 1).toFixed(1)},${ddTop}L${getX(firstK).toFixed(1)},${ddTop}Z`;
});

const xTicks = computed(() => [0, 0.25, 0.5, 0.75, 1].map(f => Math.round(f * (n.value - 1))));

const lastPoint = computed(() => periodSum.value.points[n.value - 1] ?? 0);

function handlePointerMove(e: PointerEvent) {
  if (!chartContainer.value) return;
  const rect = chartContainer.value.getBoundingClientRect();
  const px = e.clientX - rect.left;
  if (px > plotW.value || px < 0) {
    hoverIdx.value = null;
    return;
  }
  hoverIdx.value = Math.max(0, Math.min(n.value - 1, Math.round((px / plotW.value) * (n.value - 1))));
}

function handlePointerLeave() {
  hoverIdx.value = null;
}

// 鼠標懸停時各機器人回報
const hoverData = computed(() => {
  if (hoverIdx.value === null) return null;
  const rawIdx = periodSum.value.indices[hoverIdx.value];
  const timeStr = formatTime(timeAt(rawIdx), true);
  const val = periodSum.value.points[hoverIdx.value];
  const ddVal = periodSum.value.dd[hoverIdx.value];
  return { timeStr, val, ddVal };
});
</script>

<template>
  <div class="v0-account-band">
    <!-- Panel Header (獨立展示時才渲染) -->
    <div v-if="showHeader" class="panel-header">
      <div class="header-left">
        <div class="title-row">
          <span class="v0-chip">V0 移植版</span>
          <h3 class="panel-title">SIM-01 本機模擬帳戶</h3>
        </div>
      </div>

      <div class="header-actions">
        <!-- 期間選擇器 -->
        <div class="segmented-control" role="group" aria-label="時間範圍">
          <button
            v-for="p in PERIODS"
            :key="p"
            type="button"
            class="seg-btn"
            :class="{ active: period === p }"
            @click="setPeriod(p)"
          >
            {{ p }}
          </button>
        </div>
      </div>
    </div>

    <!-- Panel Body -->
    <div class="band-body">
      <!-- Left: 6 KPI Stats Grid -->
      <div class="kpi-column">
        <div class="equity-hero">
          <span class="stat-label">帳戶權益</span>
          <div class="equity-number">{{ formatUsd(snap.equity) }}</div>
          <div class="equity-sub" :class="toneOf(snap.totalPnl)">
            {{ formatUsd(snap.totalPnl, true) }} ({{ formatPct((snap.totalPnl / snap.capital) * 100) }}) 自啟用
          </div>
        </div>

        <dl class="stat-grid">
          <div class="stat-item">
            <dt class="stat-label">今日損益</dt>
            <dd class="stat-val" :class="toneOf(snap.todayPnl)">
              {{ formatUsd(snap.todayPnl, true) }}
              <span class="stat-sub">{{ formatPct(snap.todayPct) }}</span>
            </dd>
          </div>

          <div class="stat-item">
            <dt class="stat-label">{{ period }} 損益</dt>
            <dd class="stat-val" :class="toneOf(periodSum.pnl)">
              {{ formatUsd(periodSum.pnl, true) }}
              <span class="stat-sub">{{ formatPct(periodSum.ret) }}</span>
            </dd>
          </div>

          <div class="stat-item">
            <dt class="stat-label">未實現</dt>
            <dd class="stat-val" :class="toneOf(snap.upnl)">
              {{ formatUsd(snap.upnl, true) }}
              <span class="stat-sub">{{ snap.positions.length }} 筆部位</span>
            </dd>
          </div>

          <div class="stat-item">
            <dt class="stat-label">已實現（累計）</dt>
            <dd class="stat-val" :class="toneOf(snap.realized)">
              {{ formatUsd(snap.realized, true) }}
            </dd>
          </div>

          <div class="stat-item">
            <dt class="stat-label">淨曝險</dt>
            <dd class="stat-val text-white">
              {{ formatUsd(snap.net, false, 0) }}
              <span class="stat-sub">{{ ((snap.net / snap.equity) * 100).toFixed(1) }}% 權益</span>
            </dd>
          </div>

          <div class="stat-item">
            <dt class="stat-label">可用現金</dt>
            <dd class="stat-val text-white">
              {{ formatUsd(snap.cash, false, 0) }}
              <span class="stat-sub">槓桿 {{ snap.leverage.toFixed(2) }}x</span>
            </dd>
          </div>
        </dl>
      </div>

      <!-- Right: SVG Equity & Drawdown Chart -->
      <div class="chart-column">
        <div class="chart-legend">
          <span class="legend-item">
            <span class="line-swatch bg-white"></span>
            帳戶權益 · {{ PERIOD_LABEL[period] }}
          </span>
          <span class="legend-item text-risk">
            <span class="block-swatch bg-risk"></span>
            自高點回撤 · 最大 {{ formatPct(periodSum.maxDD) }} · 上限 {{ ddLimit }}%
          </span>
          <span v-if="hoverData" class="hover-info text-cyan-300">
            [{{ hoverData.timeStr }}] 報酬率: {{ formatPct(hoverData.val) }} | 回撤: {{ formatPct(hoverData.ddVal) }}
          </span>
          <span v-else class="text-neutral-500 text-xs">
            移動滑鼠可查看歷史時刻各節點
          </span>
          <!-- 當外層 Header 隱藏時，在圖表右上方保留緊湊期間選擇器 -->
          <div v-if="!showHeader" class="mini-period-segmented ml-auto flex items-center gap-1" role="group">
            <button
              v-for="p in PERIODS"
              :key="p"
              type="button"
              class="seg-btn-mini"
              :class="{ active: period === p }"
              @click="setPeriod(p)"
            >
              {{ p }}
            </button>
          </div>
        </div>

        <div
          ref="chartContainer"
          class="chart-render-area"
          :style="{ height: `${height}px` }"
          @pointermove="handlePointerMove"
          @pointerleave="handlePointerLeave"
        >
          <svg
            v-if="chartWidth > 0"
            :width="chartWidth"
            :height="height"
            class="chart-svg"
          >
            <defs>
              <linearGradient id="v0EqGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#e5e8ec" stop-opacity="0.1" />
                <stop offset="100%" stop-color="#e5e8ec" stop-opacity="0.0" />
              </linearGradient>
              <linearGradient id="v0DdGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#ed7665" stop-opacity="0.0" />
                <stop offset="100%" stop-color="#ed7665" stop-opacity="0.25" />
              </linearGradient>
            </defs>

            <!-- Y Axis Horizontal Grid Lines -->
            <g v-for="t in yBounds.ticks" :key="t">
              <line
                :x1="0"
                :x2="plotW"
                :y1="getY(t)"
                :y2="getY(t)"
                :stroke="t === 0 ? '#353a41' : '#282c31'"
                :stroke-dasharray="t === 0 ? '3 3' : undefined"
                stroke-width="1"
              />
              <text
                :x="plotW + 8"
                :y="getY(t) + 3.5"
                fill="#90969d"
                font-family="monospace"
                font-size="9"
              >
                {{ formatPct(t, yBounds.step < 1 ? 1 : 0) }}
              </text>
            </g>

            <!-- Equity Area & Line -->
            <path :d="eqAreaPath" fill="url(#v0EqGrad)" />
            <path :d="eqLinePath" fill="none" stroke="#e5e8ec" stroke-width="1.6" stroke-linejoin="round" />

            <!-- Drawdown Separator -->
            <line :x1="0" :x2="plotW" :y1="ddTop" :y2="ddTop" stroke="#282c31" stroke-width="1" />

            <!-- Drawdown Area & Line -->
            <path :d="ddAreaPath" fill="url(#v0DdGrad)" />
            <path :d="ddLinePath" fill="none" stroke="#ed7665" stroke-width="1.2" />

            <!-- Max DD Limit Threshold Line -->
            <g v-if="limitVisible">
              <line
                :x1="0"
                :x2="plotW"
                :y1="getYd(ddLimit)"
                :y2="getYd(ddLimit)"
                stroke="#ed7665"
                stroke-dasharray="4 3"
                stroke-width="1"
              />
              <text :x="4" :y="getYd(ddLimit) - 4" fill="#ed7665" font-family="monospace" font-size="10">
                帳戶上限
              </text>
              <text :x="plotW + 8" :y="getYd(ddLimit) + 3.5" fill="#ed7665" font-family="monospace" font-size="10">
                {{ ddLimit }}%
              </text>
            </g>

            <!-- X Axis Timestamps -->
            <g v-for="(k, idx) in xTicks" :key="k">
              <text
                :x="getX(k)"
                :y="height - 4"
                :text-anchor="idx === 0 ? 'start' : idx === xTicks.length - 1 ? 'end' : 'middle'"
                fill="#90969d"
                font-family="monospace"
                font-size="9"
              >
                {{ formatTime(timeAt(periodSum.indices[k]), period !== '24H') }}
              </text>
            </g>

            <!-- Current / Hover Marker -->
            <g v-if="hoverIdx !== null" style="pointer-events: none;">
              <line
                :x1="getX(hoverIdx)"
                :x2="getX(hoverIdx)"
                :y1="0"
                :y2="height - xAxisH"
                stroke="#90969d"
                stroke-dasharray="2 2"
                stroke-width="1"
              />
              <circle
                :cx="getX(hoverIdx)"
                :cy="getY(periodSum.points[hoverIdx])"
                r="3.5"
                fill="#e8b45e"
                stroke="#13161a"
                stroke-width="1.5"
              />
            </g>
            <g v-else-if="!Number.isNaN(lastPoint)" style="pointer-events: none;">
              <circle
                :cx="getX(n - 1)"
                :cy="getY(lastPoint)"
                r="3.5"
                :fill="lastPoint >= 0 ? '#65cba7' : '#ed7665'"
              />
              <rect
                :x="plotW + 3"
                :y="getY(lastPoint) - 8"
                width="48"
                height="16"
                rx="2"
                :fill="lastPoint >= 0 ? '#65cba7' : '#ed7665'"
              />
              <text
                :x="plotW + 27"
                :y="getY(lastPoint) + 3.5"
                :fill="lastPoint >= 0 ? '#0c0f12' : '#ffffff'"
                font-family="monospace"
                font-size="10"
                font-weight="800"
                text-anchor="middle"
              >
                {{ formatPct(lastPoint) }}
              </text>
            </g>
          </svg>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.v0-account-band {
  display: flex;
  flex-direction: column;
  background: transparent;
  border: none;
  border-radius: 4px;
  overflow: hidden;
  height: 100%;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #181c21;
  border-bottom: 1px solid #282c31;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.v0-chip {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  background: #181c21;
  color: #e8b45e;
  border: 1px solid #282c31;
  font-family: monospace;
}

.panel-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #e5e8ec;
}

.panel-meta {
  font-size: 11px;
  color: #90969d;
  font-family: monospace;
}

.segmented-control {
  display: flex;
  background: #13161a;
  border: 1px solid #282c31;
  border-radius: 3px;
  padding: 2px;
  gap: 2px;
}

.seg-btn {
  background: transparent;
  border: none;
  color: #90969d;
  font-size: 11px;
  font-family: monospace;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s;
}

.seg-btn:hover {
  color: #e5e8ec;
}

.seg-btn.active {
  background: #1d2126;
  color: #e8b45e;
  border: 1px solid #282c31;
}

.band-body {
  display: grid;
  grid-template-columns: 260px 1fr;
  flex: 1;
  min-height: 0;
  background: #13161a;
}

@media (max-width: 900px) {
  .band-body {
    grid-template-columns: 1fr;
  }
}

.kpi-column {
  padding: 12px;
  border-right: 1px solid #282c31;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #13161a;
}

.equity-hero {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.equity-number {
  font-family: monospace;
  font-size: 26px;
  font-weight: 700;
  color: #e5e8ec;
  letter-spacing: -0.5px;
}

.equity-sub {
  font-family: monospace;
  font-size: 12px;
}

.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 8px;
  margin: 0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-label {
  font-size: 11px;
  color: #90969d;
  margin: 0;
}

.stat-val {
  font-family: monospace;
  font-size: 12px;
  font-weight: 600;
  margin: 0;
  line-height: 1.2;
}

.stat-sub {
  display: block;
  font-size: 10px;
  color: #90969d;
  font-weight: normal;
}

.chart-column {
  padding: 10px 14px 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  background: #13161a;
}

.chart-legend {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 12px;
  font-size: 11px;
  font-family: monospace;
  color: #90969d;
  height: 26px;
  overflow: hidden;
  white-space: nowrap;
}

.mini-period-segmented {
  margin-left: auto;
  display: flex;
  gap: 3px;
  background: #181c21;
  padding: 2px 4px;
  border-radius: 4px;
  border: 1px solid #282c31;
}

.seg-btn-mini {
  padding: 1px 6px;
  font-size: 10px;
  font-family: monospace;
  border-radius: 3px;
  border: none;
  background: transparent;
  color: #90969d;
  cursor: pointer;
  transition: all 0.15s ease;
}

.seg-btn-mini:hover {
  color: #e5e8ec;
}

.seg-btn-mini.active {
  background: #1d2126;
  color: #e8b45e;
  font-weight: bold;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #90969d;
}

.line-swatch {
  display: inline-block;
  width: 12px;
  height: 2px;
  background: #e5e8ec;
}

.block-swatch {
  display: inline-block;
  width: 10px;
  height: 6px;
  background: #ed7665;
  border-radius: 1px;
}

.hover-info {
  color: #e8b45e;
}

.chart-render-area {
  position: relative;
  width: 100%;
  cursor: crosshair;
  touch-action: none;
}

.chart-svg {
  display: block;
  overflow: visible;
}

.axis-text {
  font-size: 9px;
  font-family: monospace;
  fill: #90969d;
}

.text-gain {
  color: #65cba7 !important;
}

.text-risk {
  color: #ed7665 !important;
}
</style>
