<script setup lang="ts">
import { ref } from 'vue';

interface OptTrial {
  trialNumber: number;
  fastPeriod: number;
  slowPeriod: number;
  atrMultiplier: number;
  sharpe: string;
  totalReturn: string;
  maxDrawdown: string;
  isBest: boolean;
}

const trials = ref<OptTrial[]>([
  { trialNumber: 42, fastPeriod: 12, slowPeriod: 34, atrMultiplier: 2.5, sharpe: '2.45', totalReturn: '+26.8%', maxDrawdown: '-3.8%', isBest: true },
  { trialNumber: 28, fastPeriod: 10, slowPeriod: 30, atrMultiplier: 2.0, sharpe: '2.21', totalReturn: '+22.4%', maxDrawdown: '-4.2%', isBest: false },
  { trialNumber: 65, fastPeriod: 14, slowPeriod: 38, atrMultiplier: 3.0, sharpe: '2.08', totalReturn: '+19.6%', maxDrawdown: '-3.5%', isBest: false },
  { trialNumber: 15, fastPeriod: 8, slowPeriod: 25, atrMultiplier: 1.8, sharpe: '1.92', totalReturn: '+17.3%', maxDrawdown: '-5.1%', isBest: false },
  { trialNumber: 84, fastPeriod: 16, slowPeriod: 45, atrMultiplier: 2.8, sharpe: '1.75', totalReturn: '+14.1%', maxDrawdown: '-4.6%', isBest: false }
]);
</script>

<template>
  <div class="opt-page">
    <!-- Teleport Actions to Unified Header -->
    <Teleport to="#header-page-actions">
      <div class="header-actions-group">
        <button type="button" class="btn btn-sm btn-secondary">載入搜尋空間設定</button>
        <button type="button" class="btn btn-sm btn-primary">+ 發起優化任務</button>
      </div>
    </Teleport>

    <!-- Optimization Overview Status -->
    <div class="opt-header-card card">
      <div class="opt-status-row">
        <div class="opt-metric">
          <span class="m-label">目標策略</span>
          <span class="m-val text-accent">EMA-ATR-Breakout</span>
        </div>
        <div class="opt-metric">
          <span class="m-label">搜尋演算法</span>
          <span class="m-val font-mono">TPE (Tree-structured Parzen)</span>
        </div>
        <div class="opt-metric">
          <span class="m-label">試驗進度 (Trials)</span>
          <span class="m-val font-mono">100 / 100 <span class="m-badge badge-neutral">COMPLETED</span></span>
        </div>
        <div class="opt-metric">
          <span class="m-label">最佳目標評分 (Sharpe)</span>
          <span class="m-val text-profit font-mono">2.45 (Trial #42)</span>
        </div>
      </div>
    </div>

    <div class="opt-grid">
      <!-- Search Space Definition -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">搜尋空間參數範圍 (Search Space)</div>
          <span class="badge badge-neutral">3 參數維度</span>
        </div>
        <div class="card-body">
          <div class="space-list">
            <div class="space-item">
              <div class="space-name font-mono">fast_ema_period</div>
              <div class="space-range font-mono text-muted">IntRange(5, 25, step=1)</div>
              <div class="space-best font-mono text-accent">最佳值: 12</div>
            </div>
            <div class="space-item">
              <div class="space-name font-mono">slow_ema_period</div>
              <div class="space-range font-mono text-muted">IntRange(20, 60, step=2)</div>
              <div class="space-best font-mono text-accent">最佳值: 34</div>
            </div>
            <div class="space-item">
              <div class="space-name font-mono">atr_stop_multiplier</div>
              <div class="space-range font-mono text-muted">FloatRange(1.5, 4.0, step=0.5)</div>
              <div class="space-best font-mono text-accent">最佳值: 2.5</div>
            </div>
          </div>

          <div class="export-box">
            <button type="button" class="btn btn-sm btn-primary w-full">
              ★ 導出 Trial #42 為新策略製品版本 (v1.3)
            </button>
          </div>
        </div>
      </div>

      <!-- Trials Leaderboard -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">優化試驗排行榜 (Top Trials)</div>
          <span class="badge badge-accent">帕累托最優</span>
        </div>
        <div class="card-body table-wrap">
          <table class="data-table font-mono">
            <thead>
              <tr>
                <th>Trial #</th>
                <th>Fast / Slow</th>
                <th>ATR</th>
                <th>Sharpe</th>
                <th>總回報</th>
                <th>最大回撤</th>
                <th>狀態</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in trials" :key="t.trialNumber" :class="{ 'row-best': t.isBest }">
                <td>#{{ t.trialNumber }}</td>
                <td>{{ t.fastPeriod }} / {{ t.slowPeriod }}</td>
                <td>{{ t.atrMultiplier }}x</td>
                <td class="text-accent font-bold">{{ t.sharpe }}</td>
                <td class="text-profit">{{ t.totalReturn }}</td>
                <td class="text-loss">{{ t.maxDrawdown }}</td>
                <td>
                  <span v-if="t.isBest" class="badge badge-accent">BEST</span>
                  <span v-else class="text-muted">PASS</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.opt-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  overflow-y: auto;
  flex: 1;
}

.page-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}


.opt-header-card {
  padding: 16px 20px;
}
.opt-status-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4);
}
.opt-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.m-label {
  font-size: 11px;
  color: var(--text-muted);
}
.m-val {
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}
.m-badge {
  font-size: 10px;
}

.opt-grid {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: var(--space-4);
  flex: 1;
}

.space-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.space-item {
  padding: 10px 12px;
  background-color: #06080b;
  border: 1px solid var(--border-secondary);
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.space-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.space-range {
  font-size: 11px;
}
.space-best {
  font-size: 11.5px;
  margin-top: 4px;
}

.export-box {
  margin-top: 16px;
}
.w-full {
  width: 100%;
}

.table-wrap {
  overflow-x: auto;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.data-table th, .data-table td {
  padding: 9px 12px;
  border-bottom: 1px solid var(--border-secondary);
  text-align: left;
}
.data-table th {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 500;
}
.row-best {
  background-color: rgba(220, 179, 71, 0.08);
}

.text-profit { color: var(--color-profit); }
.text-loss { color: var(--color-loss); }
.text-accent { color: var(--accent); }
.font-mono { font-family: var(--font-mono); }
.font-bold { font-weight: 700; }
</style>
