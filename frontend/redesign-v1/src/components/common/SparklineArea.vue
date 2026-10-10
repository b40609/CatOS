<script setup lang="ts">
import { computed, ref } from 'vue';
import type { EquityPoint } from '@/adapters/types';
import { usePreferences } from '@/state/usePreferences';

const props = defineProps<{
  points: EquityPoint[];
  title?: string;
}>();

const { preferences, setChartRange } = usePreferences();
const hoveredPoint = ref<EquityPoint | null>(null);

const width = 600;
const height = 220;
const padding = { top: 20, right: 30, bottom: 35, left: 60 };

const chartWidth = width - padding.left - padding.right;
const chartHeight = height - padding.top - padding.bottom;

const minEquity = computed(() => {
  if (!props.points.length) return 100000;
  return Math.min(...props.points.map(p => p.equity)) * 0.995;
});

const maxEquity = computed(() => {
  if (!props.points.length) return 130000;
  return Math.max(...props.points.map(p => p.equity)) * 1.005;
});

const pointsCoords = computed(() => {
  if (!props.points.length) return [];
  const rangeY = maxEquity.value - minEquity.value || 1;
  const stepX = chartWidth / (props.points.length - 1 || 1);

  return props.points.map((pt, idx) => {
    const x = padding.left + idx * stepX;
    const y = padding.top + chartHeight - ((pt.equity - minEquity.value) / rangeY) * chartHeight;
    return { x, y, pt };
  });
});

const pathD = computed(() => {
  const coords = pointsCoords.value;
  if (!coords.length) return '';
  return coords.reduce((acc, curr, idx) => {
    return idx === 0 ? `M ${curr.x},${curr.y}` : `${acc} L ${curr.x},${curr.y}`;
  }, '');
});

const areaD = computed(() => {
  const coords = pointsCoords.value;
  if (!coords.length) return '';
  const first = coords[0];
  const last = coords[coords.length - 1];
  const bottomY = padding.top + chartHeight;
  return `${pathD.value} L ${last.x},${bottomY} L ${first.x},${bottomY} Z`;
});
</script>

<template>
  <div class="equity-chart-card card">
    <div class="card-header">
      <div class="card-title">
        <span>{{ title || '帳戶淨值走勢' }}</span>
        <span class="sub-legend tabular-nums" v-if="hoveredPoint">
          {{ hoveredPoint.timeLabel }}: {{ hoveredPoint.equity_str }} USDT
        </span>
      </div>
      <div class="card-actions">
        <div class="chart-range-picker" role="group" aria-label="時間範圍切換">
          <button
            type="button"
            :class="['range-btn', { active: preferences.chartRange === '7D' }]"
            @click="setChartRange('7D')"
          >
            7D
          </button>
          <button
            type="button"
            :class="['range-btn', { active: preferences.chartRange === '30D' }]"
            @click="setChartRange('30D')"
          >
            30D
          </button>
          <button
            type="button"
            :class="['range-btn', { active: preferences.chartRange === '90D' }]"
            @click="setChartRange('90D')"
          >
            90D
          </button>
        </div>
      </div>
    </div>

    <div class="chart-container">
      <svg :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="none" class="chart-svg">
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="0%"
              stop-color="#dcb347"
              :stop-opacity="preferences.chartStyle === 'refined' ? 0.45 : (preferences.chartStyle === 'minimal' ? 0 : 0.30)"
            />
            <stop offset="100%" stop-color="#dcb347" stop-opacity="0.0" />
          </linearGradient>
        </defs>

        <!-- Grid lines -->
        <line
          :x1="padding.left"
          :y1="padding.top"
          :x2="width - padding.right"
          :y2="padding.top"
          stroke="#1f2633"
          stroke-dasharray="3,3"
        />
        <line
          :x1="padding.left"
          :y1="padding.top + chartHeight / 2"
          :x2="width - padding.right"
          :y2="padding.top + chartHeight / 2"
          stroke="#1f2633"
          stroke-dasharray="3,3"
        />
        <line
          :x1="padding.left"
          :y1="padding.top + chartHeight"
          :x2="width - padding.right"
          :y2="padding.top + chartHeight"
          stroke="#1f2633"
        />

        <!-- Y Axis Labels -->
        <text
          :x="padding.left - 8"
          :y="padding.top + 4"
          text-anchor="end"
          class="axis-label tabular-nums"
        >
          {{ maxEquity.toFixed(0) }}
        </text>
        <text
          :x="padding.left - 8"
          :y="padding.top + chartHeight + 4"
          text-anchor="end"
          class="axis-label tabular-nums"
        >
          {{ minEquity.toFixed(0) }}
        </text>

        <!-- Area Fill (hidden in minimal mode) -->
        <path
          v-if="areaD && preferences.chartStyle !== 'minimal'"
          :d="areaD"
          fill="url(#equityGrad)"
        />

        <!-- Line Stroke -->
        <path
          v-if="pathD"
          :d="pathD"
          fill="none"
          stroke="#dcb347"
          :stroke-width="preferences.chartStyle === 'refined' ? 2.4 : (preferences.chartStyle === 'minimal' ? 1.8 : 2.0)"
          stroke-linejoin="round"
          stroke-linecap="round"
          :class="{ 'stroke-glow': preferences.chartStyle === 'refined' }"
        />

        <!-- Interactive Data Points -->
        <g v-for="c in pointsCoords" :key="c.pt.timestamp">
          <circle
            :cx="c.x"
            :cy="c.y"
            r="3.5"
            fill="#080a0d"
            stroke="#dcb347"
            stroke-width="2"
            class="data-dot"
            @mouseenter="hoveredPoint = c.pt"
            @mouseleave="hoveredPoint = null"
          />
          <text
            :x="c.x"
            :y="padding.top + chartHeight + 20"
            text-anchor="middle"
            class="axis-label"
          >
            {{ c.pt.timeLabel }}
          </text>
        </g>
      </svg>
    </div>

    <div class="chart-footer">
      <span class="footer-note">撮合基準：OKX USDT-M SWAP · 已收盤 K 線估值 · 點位精度 Decimal</span>
      <span class="footer-status tabular-nums" v-if="points.length">
        當前: {{ points[points.length - 1].equity_str }} USDT
      </span>
    </div>
  </div>
</template>

<style scoped>
.equity-chart-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sub-legend {
  font-size: var(--text-xs);
  color: var(--accent);
  margin-left: var(--space-2);
  font-weight: 500;
}

.chart-range-picker {
  display: flex;
  background: var(--bg-base);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
  padding: 1px;
}

.range-btn {
  padding: 2px 8px;
  font-size: var(--text-2xs);
  color: var(--text-muted);
  border-radius: var(--radius-xs);
  font-family: var(--font-mono);
}

.range-btn.active {
  background: var(--bg-surface-elevated);
  color: var(--accent);
  font-weight: 600;
}

.chart-container {
  flex: 1;
  min-height: 170px;
  padding: var(--space-2) var(--space-3);
  position: relative;
}

.chart-svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}

.axis-label {
  font-size: 10px;
  fill: var(--text-muted);
  font-family: var(--font-mono);
}

.data-dot {
  cursor: pointer;
  transition: r 0.15s ease;
}

.data-dot:hover {
  r: 5.5;
  stroke: #ffffff;
}

.chart-footer {
  padding: 6px var(--space-4);
  border-top: 1px solid var(--border-secondary);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--text-2xs);
  color: var(--text-muted);
  background-color: var(--bg-surface-elevated);
}

.stroke-glow {
  filter: drop-shadow(0 0 3px rgba(220, 179, 71, 0.45));
}
</style>
