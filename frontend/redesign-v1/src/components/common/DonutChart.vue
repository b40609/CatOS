<script setup lang="ts">
import { computed } from 'vue';
import type { ExposureAllocationItem } from '@/contracts';
import { usePreferences } from '@/state/usePreferences';

const props = defineProps<{
  items: ExposureAllocationItem[];
  centerValue?: string;
  centerLabel?: string;
}>();

const { preferences } = usePreferences();

const size = 130;
const strokeWidth = computed(() => {
  if (preferences.value.chartStyle === 'refined') return 11;
  if (preferences.value.chartStyle === 'minimal') return 10;
  return 14;
});
const radius = computed(() => (size - strokeWidth.value) / 2);
const circumference = computed(() => 2 * Math.PI * radius.value);

const slices = computed(() => {
  let accumulated = 0;
  return props.items.map((item) => {
    const strokeDasharray = `${(item.pct_share / 100) * circumference.value} ${circumference.value}`;
    const strokeDashoffset = -((accumulated / 100) * circumference.value);
    accumulated += item.pct_share;
    return {
      ...item,
      strokeDasharray,
      strokeDashoffset
    };
  });
});
</script>

<template>
  <div class="donut-card card">
    <div class="card-header">
      <div class="card-title">保證金與曝險配置</div>
      <div class="card-actions">
        <span class="badge badge-neutral">槓桿上限 3.0x</span>
      </div>
    </div>

    <div class="donut-body">
      <div class="donut-graphic">
        <svg :width="size" :height="size" class="donut-svg">
          <circle
            :cx="size / 2"
            :cy="size / 2"
            :r="radius"
            fill="none"
            stroke="#151a24"
            :stroke-width="strokeWidth"
          />
          <circle
            v-for="s in slices"
            :key="s.label"
            :cx="size / 2"
            :cy="size / 2"
            :r="radius"
            fill="none"
            :stroke="s.color"
            :stroke-width="strokeWidth"
            :stroke-dasharray="s.strokeDasharray"
            :stroke-dashoffset="s.strokeDashoffset"
            stroke-linecap="butt"
            class="donut-slice"
          />
        </svg>
        <div class="donut-center-info">
          <div class="d-val tabular-nums">{{ centerValue || '1,420.50' }}</div>
          <div class="d-lbl">{{ centerLabel || '名義曝險 USDT' }}</div>
        </div>
      </div>

      <div class="donut-legend">
        <div v-for="item in items" :key="item.label" class="legend-row">
          <div class="legend-color-tag" :style="{ backgroundColor: item.color }"></div>
          <span class="legend-name">{{ item.label }}</span>
          <span class="legend-pct tabular-nums">{{ item.pct_share }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.donut-card {
  height: 100%;
  min-height: 220px;
}

@media (max-width: 640px) {
  .donut-body {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
}

.donut-body {
  padding: var(--space-4);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex: 1;
}

.donut-graphic {
  position: relative;
  width: 130px;
  height: 130px;
  min-width: 130px;
}

.donut-svg {
  transform: rotate(-90deg);
}

.donut-center-info {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
}

.d-val {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--text-primary);
  font-family: var(--font-mono);
  line-height: 1.1;
}

.d-lbl {
  font-size: 9px;
  color: var(--text-muted);
  margin-top: 2px;
}

.donut-legend {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--text-xs);
}

.legend-color-tag {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-xs);
}

.legend-name {
  color: var(--text-secondary);
  flex: 1;
}

.legend-pct {
  font-family: var(--font-mono);
  color: var(--text-primary);
  font-weight: 600;
}
</style>
