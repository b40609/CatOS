<script setup lang="ts">
import RelaxedPageHead from '@/components/relaxed/RelaxedPageHead.vue';
import RelaxedTickerBar from '@/components/relaxed/RelaxedTickerBar.vue';
import RelaxedKpiGrid from '@/components/relaxed/RelaxedKpiGrid.vue';
import RelaxedRiskBanner from '@/components/relaxed/RelaxedRiskBanner.vue';
import RelaxedEquityChart from '@/components/relaxed/RelaxedEquityChart.vue';
import RelaxedAssetDonut from '@/components/relaxed/RelaxedAssetDonut.vue';
import RelaxedPositionsTable from '@/components/relaxed/RelaxedPositionsTable.vue';
import RelaxedRecentFills from '@/components/relaxed/RelaxedRecentFills.vue';
</script>

<template>
  <div class="workspace-relaxed-view">
    <!-- 0. PageHead with Overview / Dashboard title, desc and export snapshot -->
    <RelaxedPageHead />

    <!-- 1. Top Realtime Ticker Bar (42px compact) -->
    <RelaxedTickerBar />

    <!-- 2. Core 4 KPI Metrics (Unified strip) -->
    <RelaxedKpiGrid />

    <!-- 3. Risk Sentinel Banner -->
    <RelaxedRiskBanner />

    <!-- 4. Middle Section (7:3 Chart & Asset Donut) -->
    <div class="relaxed-grid-split">
      <div class="grid-col-primary">
        <RelaxedEquityChart />
      </div>
      <div class="grid-col-secondary">
        <RelaxedAssetDonut />
      </div>
    </div>

    <!-- 5. Bottom Section (7:3 Positions Table & Recent Fills Stream) -->
    <div class="relaxed-grid-split">
      <div class="grid-col-primary">
        <RelaxedPositionsTable />
      </div>
      <div class="grid-col-secondary">
        <RelaxedRecentFills />
      </div>
    </div>
  </div>
</template>

<style scoped>
.workspace-relaxed-view {
  display: flex;
  flex-direction: column;
  padding: 1.25rem 1.75rem 2.5rem 1.75rem;
  max-width: 1700px;
  margin: 0 auto;
  width: 100%;
}

.relaxed-grid-split {
  display: grid;
  grid-template-columns: minmax(0, 2.25fr) minmax(270px, 1fr);
  gap: 1rem;
  margin-bottom: 1rem;
  align-items: stretch;
}

.grid-col-primary {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.grid-col-secondary {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

@media (max-width: 1180px) {
  .relaxed-grid-split {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .workspace-relaxed-view {
    padding: 0.85rem 0.75rem;
    gap: 0.85rem;
  }
}
</style>
