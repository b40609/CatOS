<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import type { EquityPoint } from '@/adapters/types';
import { usePreferences } from '@/state/usePreferences';

const props = withDefaults(
  defineProps<{
    points: EquityPoint[];
    title?: string;
    showHeader?: boolean;
  }>(),
  {
    showHeader: true,
  }
);

const { preferences, setChartRange } = usePreferences();
const hoveredPoint = ref<EquityPoint | null>(null);

const containerRef = ref<HTMLDivElement | null>(null);
const containerWidth = ref(600);
const containerHeight = ref(200);

let resizeObserver: ResizeObserver | null = null;

function updateDimensions() {
  if (!containerRef.value) return;
  const rect = containerRef.value.getBoundingClientRect();
  if (rect.width > 0) containerWidth.value = Math.round(rect.width);
  if (rect.height > 0) containerHeight.value = Math.round(rect.height);
}

onMounted(() => {
  updateDimensions();
  if (containerRef.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      updateDimensions();
    });
    resizeObserver.observe(containerRef.value);
  }
});

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});

// Fixed padding ensures text and axis labels never clip and stay crisp
const padding = { top: 16, right: 20, bottom: 26, left: 58 };

const chartWidth = computed(() => Math.max(80, containerWidth.value - padding.left - padding.right));
const chartHeight = computed(() => Math.max(40, containerHeight.value - padding.top - padding.bottom));

const minEquity = computed(() => {
  if (!props.points.length) return 100000;
  return Math.min(...props.points.map(p => p.equity)) * 0.995;
});

const maxEquity = computed(() => {
  if (!props.points.length) return 130000;
  return Math.max(...props.points.map(p => p.equity)) * 1.005;
});

const midEquity = computed(() => (minEquity.value + maxEquity.value) / 2);

const pointsCoords = computed(() => {
  if (!props.points.length) return [];
  const rangeY = maxEquity.value - minEquity.value || 1;
  const total = props.points.length;
  const stepX = total > 1 ? chartWidth.value / (total - 1) : chartWidth.value;

  return props.points.map((pt, idx) => {
    const x = padding.left + (total > 1 ? idx * stepX : chartWidth.value / 2);
    const y = padding.top + chartHeight.value - ((pt.equity - minEquity.value) / rangeY) * chartHeight.value;
    return { x, y, pt, idx };
  });
});

const pathD = computed(() => {
  const coords = pointsCoords.value;
  if (!coords.length) return '';
  return coords.reduce((acc, curr, idx) => {
    return idx === 0 ? `M ${curr.x.toFixed(1)},${curr.y.toFixed(1)}` : `${acc} L ${curr.x.toFixed(1)},${curr.y.toFixed(1)}`;
  }, '');
});

const areaD = computed(() => {
  const coords = pointsCoords.value;
  if (!coords.length) return '';
  const first = coords[0];
  const last = coords[coords.length - 1];
  const bottomY = padding.top + chartHeight.value;
  return `${pathD.value} L ${last.x.toFixed(1)},${bottomY.toFixed(1)} L ${first.x.toFixed(1)},${bottomY.toFixed(1)} Z`;
});

// Select sparse non-overlapping X-axis ticks (at most 5 labels)
const visibleXAxisTicks = computed(() => {
  const coords = pointsCoords.value;
  const total = coords.length;
  if (total === 0) return [];
  if (total <= 4) return coords;

  const maxTicks = containerWidth.value < 450 ? 3 : 5;
  const step = Math.floor((total - 1) / (maxTicks - 1));
  const ticks = [];
  for (let i = 0; i < total; i += step) {
    ticks.push(coords[i]);
  }
  // Ensure the very last point is included
  if (ticks[ticks.length - 1]?.idx !== total - 1) {
    ticks.push(coords[total - 1]);
  }
  return ticks;
});
</script>

<template>
  <div class="equity-chart-card card pane-chart" :class="{ 'no-header': !showHeader }">
    <div v-if="showHeader" class="card-header">
      <div class="card-title">
        <span>{{ title || '帳戶淨值走勢' }}</span>
        <span class="sub-legend mono tabular-nums" v-if="hoveredPoint">
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

    <div ref="containerRef" class="chart-container">
      <!-- Floating hover tooltip when header is hidden -->
      <div v-if="hoveredPoint && !showHeader" class="floating-hover-badge mono tabular-nums">
        {{ hoveredPoint.timeLabel }}: {{ hoveredPoint.equity_str }} USDT
      </div>

      <svg
        :viewBox="`0 0 ${containerWidth} ${containerHeight}`"
        class="chart-svg"
      >
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="0%"
              stop-color="var(--accent, #e8b45e)"
              :stop-opacity="preferences.chartStyle === 'minimal' ? 0 : 0.22"
            />
            <stop offset="100%" stop-color="var(--accent, #e8b45e)" stop-opacity="0.0" />
          </linearGradient>
        </defs>

        <!-- Horizontal Grid lines -->
        <line
          :x1="padding.left"
          :y1="padding.top"
          :x2="containerWidth - padding.right"
          :y2="padding.top"
          stroke="var(--border-secondary, #282c31)"
          stroke-dasharray="3,3"
          stroke-width="1"
        />
        <line
          :x1="padding.left"
          :y1="padding.top + chartHeight / 2"
          :x2="containerWidth - padding.right"
          :y2="padding.top + chartHeight / 2"
          stroke="var(--border-secondary, #282c31)"
          stroke-dasharray="3,3"
          stroke-width="1"
        />
        <line
          :x1="padding.left"
          :y1="padding.top + chartHeight"
          :x2="containerWidth - padding.right"
          :y2="padding.top + chartHeight"
          stroke="var(--border-primary, #282c31)"
          stroke-width="1"
        />

        <!-- Y Axis Numeric Labels (Fixed 10px, crisp, non-distorted) -->
        <text
          :x="padding.left - 8"
          :y="padding.top + 4"
          text-anchor="end"
          class="axis-label mono tabular-nums"
        >
          {{ maxEquity.toFixed(0) }}
        </text>
        <text
          :x="padding.left - 8"
          :y="padding.top + chartHeight / 2 + 4"
          text-anchor="end"
          class="axis-label mono tabular-nums"
        >
          {{ midEquity.toFixed(0) }}
        </text>
        <text
          :x="padding.left - 8"
          :y="padding.top + chartHeight + 4"
          text-anchor="end"
          class="axis-label mono tabular-nums"
        >
          {{ minEquity.toFixed(0) }}
        </text>

        <!-- X Axis Date/Time Labels (Sparse & Non-overlapping) -->
        <text
          v-for="tick in visibleXAxisTicks"
          :key="tick.pt.timestamp"
          :x="tick.x"
          :y="padding.top + chartHeight + 18"
          text-anchor="middle"
          class="axis-label mono tabular-nums"
        >
          {{ tick.pt.timeLabel }}
        </text>

        <!-- Area Fill -->
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
          stroke="var(--accent, #e8b45e)"
          :stroke-width="preferences.chartStyle === 'minimal' ? 1.6 : 2.0"
          stroke-linejoin="round"
          stroke-linecap="round"
        />

        <!-- Hover Guideline -->
        <line
          v-if="hoveredPoint"
          :x1="pointsCoords.find(c => c.pt.timestamp === hoveredPoint?.timestamp)?.x || 0"
          :y1="padding.top"
          :x2="pointsCoords.find(c => c.pt.timestamp === hoveredPoint?.timestamp)?.x || 0"
          :y2="padding.top + chartHeight"
          stroke="var(--accent, #e8b45e)"
          stroke-dasharray="2,2"
          stroke-width="1"
          opacity="0.6"
          style="pointer-events: none;"
        />

        <!-- Interactive Data Dots -->
        <g v-for="c in pointsCoords" :key="c.pt.timestamp">
          <circle
            :cx="c.x"
            :cy="c.y"
            :r="hoveredPoint?.timestamp === c.pt.timestamp ? 4.5 : 2.5"
            :fill="hoveredPoint?.timestamp === c.pt.timestamp ? 'var(--accent, #e8b45e)' : 'var(--card, #13161a)'"
            stroke="var(--accent, #e8b45e)"
            :stroke-width="hoveredPoint?.timestamp === c.pt.timestamp ? 2 : 1.5"
            class="data-dot"
            @mouseenter="hoveredPoint = c.pt"
            @mouseleave="hoveredPoint = null"
          />
        </g>
      </svg>
    </div>

    <div class="chart-footer">
      <span class="footer-note">撮合基準：OKX USDT-M SWAP · 已收盤 K 線估值 · 點位精度 Decimal</span>
      <span class="footer-status mono tabular-nums" v-if="points.length">
        當前: {{ points[points.length - 1].equity_str }} USDT
      </span>
    </div>
  </div>
</template>

<style scoped>
.equity-chart-card {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--card, #13161a);
  border: 1px solid var(--border, #282c31);
  border-radius: var(--radius, 6px);
}

.sub-legend {
  font-size: 11px;
  color: var(--accent, #e8b45e);
  margin-left: var(--space-2);
  font-weight: 500;
}

.chart-range-picker {
  display: inline-flex;
  align-items: center;
  background: var(--bg-surface-elevated, #181c21);
  border: 1px solid var(--border, #282c31);
  border-radius: 4px;
  padding: 1.5px;
  gap: 2px;
}

.range-btn {
  padding: 2px 7px;
  font-size: 10px;
  color: var(--muted-foreground, #90969d);
  background: transparent;
  border: none;
  border-radius: 2px;
  font-family: var(--font-mono, monospace);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.range-btn:hover {
  color: var(--foreground, #e5e8ec);
  background: var(--bg-surface-hover, #1d2126);
}

.range-btn.active {
  background: var(--accent, #e8b45e);
  color: #1f1306;
  font-weight: 600;
}

.chart-container {
  flex: 1;
  min-height: 120px;
  padding: 0;
  position: relative;
  overflow: hidden;
}

.chart-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.axis-label {
  font-size: 10px;
  fill: var(--muted-foreground, #90969d);
  user-select: none;
}

.data-dot {
  cursor: pointer;
  transition: r 0.15s ease;
}

.chart-footer {
  padding: 6px 14px;
  border-top: 1px solid var(--border, #282c31);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  color: var(--muted-foreground, #90969d);
  background-color: var(--bg-surface-elevated, #181c21);
  flex-shrink: 0;
}

.no-header {
  border: none;
  background: transparent;
  box-shadow: none;
}

.floating-hover-badge {
  position: absolute;
  top: 8px;
  right: 12px;
  background: rgba(19, 22, 26, 0.92);
  border: 1px solid var(--accent, #e8b45e);
  color: var(--accent, #e8b45e);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  pointer-events: none;
  z-index: 10;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
}

.footer-note {
  font-size: 10px;
  color: var(--muted-foreground, #90969d);
}

.footer-status {
  font-size: 11px;
  font-weight: 500;
  color: var(--foreground, #e5e8ec);
}
</style>
