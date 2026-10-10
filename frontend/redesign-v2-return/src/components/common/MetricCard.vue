<script setup lang="ts">
import { computed } from 'vue';
import { usePreferences } from '@/state/usePreferences';

const props = defineProps<{
  label: string;
  value: string;
  unit?: string;
  subText?: string;
  subType?: 'pos' | 'neg' | 'neutral';
  borderType?: 'accent' | 'warning' | 'danger' | 'success';
  isEquity?: boolean;
  dualLayer?: boolean;
}>();

const { preferences } = usePreferences();

const isDual = computed(() => {
  if (props.dualLayer !== undefined) return props.dualLayer;
  return preferences.value.kpiDualLayer;
});
</script>

<template>
  <div
    class="kpi-card"
    :class="[
      borderType ? `${borderType}-border` : '',
      isEquity ? 'equity-card' : '',
      isDual ? 'is-dual-compact' : 'is-classic'
    ]"
  >
    <!-- 方案 A：✦ 雙層高階緊湊版 (Zero-Waste Stacked Metric) -->
    <template v-if="isDual">
      <div class="kpi-dual-top">
        <span class="kpi-dual-label">{{ label }}</span>
        <span v-if="unit" class="kpi-dual-unit mono">{{ unit }}</span>
      </div>
      <div class="kpi-dual-stack">
        <span
          class="kpi-dual-val mono tabular-nums"
          :class="[
            isEquity ? 'equity-val' : '',
            subType ? `val-${subType}` : ''
          ]"
        >
          {{ value }}
        </span>
        <div v-if="subText" class="kpi-dual-sub mono" :class="subType || 'neutral'">
          {{ subText }}
        </div>
      </div>
    </template>

    <!-- 方案 B：原版單層三段排版 (Classic 3-tier) -->
    <template v-else>
      <div class="kpi-header">
        <span class="kpi-label">{{ label }}</span>
      </div>

      <div class="kpi-value-row">
        <span
          class="kpi-value mono tabular-nums"
          :class="[
            isEquity ? 'equity-val' : '',
            subType ? `val-${subType}` : ''
          ]"
        >
          {{ value }}
        </span>
        <span v-if="unit" class="kpi-unit mono">{{ unit }}</span>
      </div>

      <div v-if="subText" class="kpi-sub" :class="subType || 'neutral'">
        {{ subText }}
      </div>
    </template>
  </div>
</template>

<style scoped>
.kpi-card {
  height: 100%;
  width: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: stretch;
  background: var(--card, #13161a);
  border: 1px solid var(--border, #282c31);
  border-radius: var(--radius, 4px);
  position: relative;
  overflow: hidden;
  transition: all 0.15s ease;
}

/* ================= 雙層高階緊湊版 (is-dual-compact) ================= */
.kpi-card.is-dual-compact {
  padding: 7px 10px;
  justify-content: space-between;
}

.kpi-dual-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  line-height: 1.1;
}

.kpi-dual-label {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--muted-foreground, #90969d);
  letter-spacing: 0.02em;
}

.kpi-dual-unit {
  font-size: 9.5px;
  color: #6c737c;
}

.kpi-dual-stack {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin-top: 2px;
}

.kpi-dual-val {
  font-size: 18px;
  font-weight: 700;
  color: var(--foreground, #e5e8ec);
  white-space: nowrap;
  letter-spacing: -0.02em;
  line-height: 1.1;
}

.kpi-dual-val.equity-val {
  font-size: 20px;
}

.kpi-dual-val.val-pos {
  color: var(--gain, #65cba7);
}

.kpi-dual-val.val-neg {
  color: var(--risk, #ed7665);
}

.kpi-dual-sub {
  font-size: 10px;
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kpi-dual-sub.pos {
  color: var(--gain, #65cba7);
}

.kpi-dual-sub.neg {
  color: var(--risk, #ed7665);
}

.kpi-dual-sub.neutral {
  color: var(--muted-foreground, #90969d);
}

/* ================= 原版三段排版 (is-classic) ================= */
.kpi-card.is-classic {
  padding: 12px 14px;
}

.kpi-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  flex-shrink: 0;
}

.kpi-label {
  font-size: 11px;
  font-weight: 500;
  color: var(--muted-foreground, #90969d);
  letter-spacing: 0.02em;
  line-height: 1.2;
}

.kpi-value-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  width: 100%;
  line-height: 1.15;
  margin-bottom: 6px;
  flex-shrink: 0;
  overflow: hidden;
}

.kpi-value {
  font-size: 20px;
  font-weight: 500;
  color: var(--foreground, #e5e8ec);
  white-space: nowrap;
  letter-spacing: -0.01em;
}

.kpi-value.equity-val {
  font-size: 26px;
  color: var(--foreground, #e5e8ec);
}

.kpi-value.val-pos {
  color: var(--gain, #65cba7);
}

.kpi-value.val-neg {
  color: var(--risk, #ed7665);
}

.kpi-unit {
  font-size: 11px;
  font-weight: 400;
  color: var(--muted-foreground, #90969d);
  white-space: nowrap;
}

.kpi-sub {
  font-size: 11px;
  font-weight: 400;
  line-height: 1.45;
  color: var(--muted-foreground, #90969d);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-shrink: 0;
}

.kpi-sub.pos {
  color: var(--gain, #65cba7);
}

.kpi-sub.neg {
  color: var(--risk, #ed7665);
}

.kpi-sub.neutral {
  color: var(--muted-foreground, #90969d);
}

/* 邊框強調 */
.kpi-card.accent-border {
  border-top: 2px solid var(--accent, #e8b45e);
}

.kpi-card.warning-border {
  border-top: 2px solid var(--primary, #e8b45e);
}

.kpi-card.danger-border {
  border-top: 2px solid var(--risk, #ed7665);
}

.kpi-card.success-border {
  border-top: 2px solid var(--gain, #65cba7);
}
</style>
