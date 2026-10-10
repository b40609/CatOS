<script setup lang="ts">
defineProps<{
  label: string;
  value: string;
  unit?: string;
  subText?: string;
  subType?: 'pos' | 'neg' | 'neutral';
  borderType?: 'accent' | 'warning' | 'danger' | 'success';
}>();
</script>

<template>
  <div :class="['kpi-card', borderType ? `${borderType}-border` : '']">
    <div class="kpi-label">{{ label }}</div>
    <div class="kpi-value-row">
      <span class="kpi-value">{{ value }}</span>
      <span v-if="unit" class="kpi-unit">{{ unit }}</span>
    </div>
    <div v-if="subText" :class="['kpi-sub', subType || 'neutral']">
      {{ subText }}
    </div>
  </div>
</template>

<style scoped>
.kpi-unit {
  font-size: var(--text-xs);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-weight: 500;
}
</style>
