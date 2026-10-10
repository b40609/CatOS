<script setup lang="ts">
interface AssetSegment {
  name: string;
  pct: number;
  color: string;
}

const assets: AssetSegment[] = [
  { name: 'BTC 永續', pct: 42.0, color: 'var(--os-alloc-btc)' },
  { name: 'ETH 現貨', pct: 18.0, color: 'var(--os-alloc-eth)' },
  { name: 'SOL 永續', pct: 21.0, color: 'var(--os-alloc-sol)' },
  { name: '穩定幣套利', pct: 12.0, color: 'var(--os-alloc-arb)' },
  { name: 'USDT 儲備', pct: 7.0, color: 'var(--os-alloc-cash)' }
];

// Helper to compute SVG donut arc segments
const radius = 64;
const strokeWidth = 14;
const circumference = 2 * Math.PI * radius;

function getDashArray(pct: number): string {
  const dash = (pct / 100) * circumference;
  return `${dash} ${circumference - dash}`;
}

function getDashOffset(index: number): number {
  let prevTotal = 0;
  for (let i = 0; i < index; i++) {
    prevTotal += assets[i].pct;
  }
  return -((prevTotal / 100) * circumference);
}
</script>

<template>
  <div class="relaxed-donut-card">
    <div class="donut-header">
      <h3 class="card-title">Asset Allocation</h3>
      <span class="meta-badge">5 assets</span>
    </div>

    <div class="donut-body">
      <div class="donut-visual-box">
        <svg viewBox="0 0 160 160" class="donut-svg">
          <g transform="rotate(-90 80 80)">
            <!-- Base subtle ring -->
            <circle
              cx="80"
              cy="80"
              :r="radius"
              fill="none"
              stroke="var(--os-border-subtle)"
              :stroke-width="strokeWidth"
            />
            <!-- Segment arcs with smooth gap -->
            <circle
              v-for="(asset, idx) in assets"
              :key="asset.name"
              cx="80"
              cy="80"
              :r="radius"
              fill="none"
              :stroke="asset.color"
              :stroke-width="strokeWidth"
              :stroke-dasharray="getDashArray(asset.pct - 0.75)"
              :stroke-dashoffset="getDashOffset(idx)"
              stroke-linecap="round"
            />
          </g>
        </svg>

        <!-- Center floating label -->
        <div class="donut-center-info">
          <span class="center-sub">Total assets</span>
          <span class="center-val num">12.48M</span>
          <span class="center-unit">USDT</span>
        </div>
      </div>

      <!-- Asset breakdown list -->
      <ul class="asset-list">
        <li v-for="asset in assets" :key="asset.name" class="asset-row">
          <div class="asset-left">
            <span class="color-dot" :style="{ backgroundColor: asset.color }"></span>
            <span class="asset-name">{{ asset.name }}</span>
          </div>
          <span class="asset-pct num">{{ asset.pct.toFixed(1) }}<span class="pct-sign">%</span></span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.relaxed-donut-card {
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: var(--os-card-radius, 6px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
}

.donut-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--os-border);
}

.card-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--os-text-primary);
}

.meta-badge {
  font-size: 10px;
  color: var(--os-text-muted);
}

.donut-body {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  flex: 1;
}

.donut-visual-box {
  position: relative;
  width: 140px;
  height: 140px;
  margin: 0.5rem auto 0.75rem auto;
}

.donut-svg {
  width: 100%;
  height: 100%;
}

.donut-center-info {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.center-sub {
  font-size: 0.62rem;
  color: var(--os-text-muted);
}

.center-val {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--os-text-primary);
  line-height: 1.2;
}

.center-unit {
  font-size: 0.62rem;
  color: var(--os-text-muted);
}

.asset-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.asset-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.74rem;
}

.asset-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.color-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.asset-name {
  color: var(--os-text-secondary);
}

.asset-pct {
  font-weight: 500;
  color: var(--os-text-primary);
}

.pct-sign {
  color: var(--os-text-muted);
  font-size: 0.65rem;
}
</style>
