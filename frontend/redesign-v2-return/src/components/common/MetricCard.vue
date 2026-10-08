<script setup lang="ts">
defineProps<{
  label: string;
  value: string;
  unit?: string;
  subText?: string;
  subType?: 'pos' | 'neg' | 'neutral';
  borderType?: 'accent' | 'warning' | 'danger' | 'success';
  isEquity?: boolean;
}>();
</script>

<template>
  <div
    class="kpi-card"
    :class="[
      borderType ? `${borderType}-border` : '',
      isEquity ? 'equity-card' : ''
    ]"
  >
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
  padding: 12px 14px;
  background: var(--card, #13161a);
  border: 1px solid var(--border, #282c31);
  border-radius: var(--radius, 6px);
  position: relative;
  overflow: hidden;
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

/* 邊框強調 (極簡 1px 高光，不使用過粗大漸層) */
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
