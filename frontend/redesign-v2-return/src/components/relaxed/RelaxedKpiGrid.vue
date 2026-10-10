<script setup lang="ts">
import { computed } from 'vue';
import { useV0Engine } from '@/state/v0-engine';
import { useDashboard } from '@/state/useDashboard';

const { snapshot, bots } = useV0Engine();
const { kpis } = useDashboard();

const runningCount = computed(() => bots.value.filter((b: any) => b.status === 'running').length);
const totalBots = computed(() => bots.value.length || 6);

const totalEquity = computed(() => {
  if (kpis.value?.total_equity && kpis.value.total_equity !== '--') {
    return Number(kpis.value.total_equity).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return snapshot.value.equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
});

const todayPnl = computed(() => {
  if (kpis.value?.today_pnl && kpis.value.today_pnl !== '--') {
    const val = Number(kpis.value.today_pnl);
    const sign = val >= 0 ? '+' : '';
    return `${sign}${val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return '+58,448.25';
});

const todayPnlPct = computed(() => {
  if (kpis.value?.today_pnl_pct && kpis.value.today_pnl_pct !== '--' && !kpis.value.today_pnl_pct.includes('NaN')) {
    const val = Number(kpis.value.today_pnl_pct.replace('%', ''));
    if (!isNaN(val)) return `↗ +${val.toFixed(1)}%`;
  }
  return '↗ +12.8%';
});
</script>

<template>
  <div class="relaxed-kpi-grid">
    <!-- Card 1: Total Equity -->
    <div class="kpi-card">
      <div class="card-header-row">
        <span class="card-title">Total equity</span>
        <span class="card-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <rect x="2" y="5" width="20" height="14" rx="2"/>
            <line x1="2" y1="10" x2="22" y2="10"/>
          </svg>
        </span>
      </div>
      <div class="card-value-row">
        <span class="kpi-number num">12,482,114.05</span>
        <span class="kpi-unit">USDT</span>
      </div>
      <div class="card-footer-row">
        <span class="trend-badge text-up num">↗ +0.47%</span>
        <span class="footer-note">vs. yesterday</span>
      </div>
    </div>

    <!-- Card 2: Today's PnL -->
    <div class="kpi-card">
      <div class="card-header-row">
        <span class="card-title">Today's PnL</span>
        <span class="card-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
            <polyline points="17 6 23 6 23 12"/>
          </svg>
        </span>
      </div>
      <div class="card-value-row">
        <span class="kpi-number num text-up">+58,447.77</span>
        <span class="kpi-unit">USDT</span>
      </div>
      <div class="card-footer-row">
        <span class="trend-badge text-up num">↗ +12.0%</span>
        <span class="footer-note">vs. yesterday</span>
      </div>
    </div>

    <!-- Card 3: Active Bots -->
    <div class="kpi-card">
      <div class="card-header-row">
        <span class="card-title">Active bots</span>
        <span class="card-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <rect x="3" y="11" width="18" height="10" rx="2"/>
            <circle cx="12" cy="5" r="2"/>
            <path d="M12 7v4"/>
            <line x1="8" y1="16" x2="8" y2="16"/>
            <line x1="16" y1="16" x2="16" y2="16"/>
          </svg>
        </span>
      </div>
      <div class="card-value-row">
        <span class="kpi-number num">4</span>
        <span class="kpi-sub-total num">/ 6</span>
      </div>
      <div class="card-footer-row">
        <span class="trend-badge text-up num">4 running</span>
        <span class="footer-note">1 paused · 1 attention</span>
      </div>
    </div>

    <!-- Card 4: Max Drawdown -->
    <div class="kpi-card">
      <div class="card-header-row">
        <span class="card-title">Max drawdown</span>
        <span class="card-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
        </span>
      </div>
      <div class="card-value-row">
        <span class="kpi-number num">-8.43</span>
        <span class="kpi-unit">%</span>
      </div>
      <div class="card-footer-row">
        <span class="trend-badge text-down num">↘ 1.24%</span>
        <span class="footer-note">year to date</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.relaxed-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: var(--os-card-radius, 6px);
  overflow: hidden;
  margin-bottom: 1rem;
}

.kpi-card {
  padding: 1rem 1.25rem;
  border-right: 1px solid var(--os-border);
  display: flex;
  flex-direction: column;
  transition: background 0.15s ease;
  min-width: 0;
}

.kpi-card:last-child {
  border-right: none;
}

.kpi-card:hover {
  background: var(--os-bg-card-hover);
}

.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 11px;
  color: var(--os-text-muted);
  font-weight: 400;
}

.card-icon {
  color: var(--os-text-muted);
}

.card-value-row {
  margin-top: 0.65rem;
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
}

.kpi-number {
  font-size: 24px;
  font-weight: 500;
  line-height: 1.2;
  color: var(--os-text-primary);
  letter-spacing: -0.02em;
}

.kpi-unit, .kpi-sub-total {
  font-size: 0.8rem;
  color: var(--os-text-muted);
}

.card-footer-row {
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.7rem;
}

.trend-badge {
  font-weight: 500;
}

.footer-note {
  color: var(--os-text-muted);
}

.text-up {
  color: var(--os-up);
}

.text-down {
  color: var(--os-down);
}

@media (max-width: 1024px) {
  .relaxed-kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .relaxed-kpi-grid {
    grid-template-columns: 1fr;
  }
}
</style>
