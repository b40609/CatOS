<script setup lang="ts">
import DonutChart from './DonutChart.vue';
import type { ExposureAllocationItem } from '@/contracts';

export type AllocationMode = 'donut';

withDefaults(
  defineProps<{
    items?: ExposureAllocationItem[];
    showHeader?: boolean;
    mode?: string;
  }>(),
  {
    showHeader: false,
    mode: 'donut'
  }
);
</script>

<template>
  <div class="allocation-unified-root">
    <div class="alloc-view-body view-donut">
      <DonutChart :items="items" centerValue="1,420.50" centerLabel="名義曝險 USDT" :showHeader="false" />
    </div>
  </div>
</template>

<style scoped>
.allocation-unified-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

.alloc-view-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.view-donut {
  padding: 0;
}
</style>
