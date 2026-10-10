<script setup lang="ts">
import { ref } from 'vue';

const props = withDefaults(
  defineProps<{
    code?: string;
    title?: string;
    desc?: string;
    dateText?: string;
  }>(),
  {
    code: 'OVERVIEW / 戰情總覽',
    title: 'Dashboard',
    desc: 'Your portfolio. Every position. One view.',
    dateText: 'Oct 10, 2026'
  }
);

const isExported = ref(false);

function handleExport() {
  const rows = [
    'Symbol,Side,Size,Entry Price,Mark Price,Unrealized PnL',
    'BTC-PERP,LONG,1.24,62840,64183,1664.70',
    'ETH-PERP,SHORT,4.20,3228,3183,192.36',
    'SOL-PERP,LONG,18.50,139,142,67.71',
    'ETH-USDT,LONG,2.80,3202,3183,-53.76'
  ];
  const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'catos-portfolio-snapshot.csv';
  a.click();
  URL.revokeObjectURL(url);

  isExported.value = true;
  setTimeout(() => {
    isExported.value = false;
  }, 2200);
}
</script>

<template>
  <div class="relaxed-page-head">
    <div class="head-left">
      <p class="head-code">{{ code }}</p>
      <h1 class="head-title">{{ title }}</h1>
      <p class="head-desc">{{ desc }}</p>
    </div>

    <div class="head-right">
      <span class="head-date">{{ dateText }}</span>
      <button
        type="button"
        class="head-export-btn"
        @click="handleExport"
        :title="isExported ? '已匯出' : '匯出當前持倉快照 (CSV)'"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        <span>{{ isExported ? 'Exported' : 'Export snapshot' }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.relaxed-page-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.head-left {
  display: flex;
  flex-direction: column;
}

.head-code {
  font-size: 10px;
  text-transform: uppercase;
  color: var(--os-text-muted);
  letter-spacing: 0.06em;
  margin-bottom: 0.25rem;
  font-weight: 500;
}

.head-title {
  font-size: 1.55rem;
  font-weight: 600;
  color: var(--os-text-primary);
  line-height: 1.15;
  letter-spacing: -0.02em;
}

.head-desc {
  font-size: 11.5px;
  color: var(--os-text-muted);
  margin-top: 0.35rem;
  line-height: 1.4;
}

.head-right {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.head-date {
  font-size: 11px;
  color: var(--os-text-muted);
}

.head-export-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  height: 30px;
  padding: 0 0.75rem;
  border-radius: var(--os-card-radius, 6px);
  border: 1px solid var(--os-border);
  background: var(--os-bg-card);
  color: var(--os-text-primary);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.head-export-btn:hover {
  background: var(--os-bg-card-hover);
  border-color: rgba(255, 255, 255, 0.15);
}

@media (max-width: 640px) {
  .relaxed-page-head {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.75rem;
  }
  .head-right {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
