<script setup lang="ts">
import { ref } from 'vue';

interface BacktestRun {
  id: string;
  strategyName: string;
  symbol: string;
  timeframe: string;
  startDate: string;
  endDate: string;
  totalReturn: string;
  sharpe: string;
  maxDrawdown: string;
  winRate: string;
  tradesCount: number;
  status: 'completed' | 'running';
}

const historyRuns = ref<BacktestRun[]>([
  {
    id: 'bt-20261004-01',
    strategyName: 'EMA 雙均線突破',
    symbol: 'BTC-USDT-SWAP',
    timeframe: '15m (Closed Bar)',
    startDate: '2026-09-01',
    endDate: '2026-09-30',
    totalReturn: '+18.42%',
    sharpe: '2.14',
    maxDrawdown: '-4.15%',
    winRate: '58.3%',
    tradesCount: 48,
    status: 'completed'
  },
  {
    id: 'bt-20261004-02',
    strategyName: 'ATR 波動區間突破',
    symbol: 'ETH-USDT-SWAP',
    timeframe: '1h (Closed Bar)',
    startDate: '2026-08-15',
    endDate: '2026-09-30',
    totalReturn: '+12.08%',
    sharpe: '1.86',
    maxDrawdown: '-5.20%',
    winRate: '52.1%',
    tradesCount: 34,
    status: 'completed'
  },
  {
    id: 'bt-20261004-03',
    strategyName: 'RSI 均值回歸極值',
    symbol: 'SOL-USDT-SWAP',
    timeframe: '15m (Closed Bar)',
    startDate: '2026-09-15',
    endDate: '2026-09-30',
    totalReturn: '+7.85%',
    sharpe: '1.62',
    maxDrawdown: '-3.80%',
    winRate: '61.5%',
    tradesCount: 26,
    status: 'completed'
  }
]);

const selectedRun = ref<BacktestRun>(historyRuns.value[0]);
</script>

<template>
  <div class="backtest-page">
    <!-- Teleport Actions to Unified Header -->
    <Teleport to="#header-page-actions">
      <div class="header-actions-group">
        <button type="button" class="btn btn-sm btn-secondary">匯入歷史行情</button>
        <button type="button" class="btn btn-sm btn-primary">+ 發起新回測任務</button>
      </div>
    </Teleport>


    <!-- Top KPI Cards -->
    <div class="kpi-grid">
      <div class="card kpi-card highlight-card">
        <span class="kpi-label">累計總回報率</span>
        <span class="kpi-val text-profit font-mono">{{ selectedRun.totalReturn }}</span>
        <span class="kpi-sub font-mono text-muted">測試標的：{{ selectedRun.symbol }}</span>
      </div>

      <div class="card kpi-card">
        <span class="kpi-label">夏普比率 (Sharpe Ratio)</span>
        <span class="kpi-val font-mono text-accent">{{ selectedRun.sharpe }}</span>
        <span class="kpi-sub font-mono text-muted">無風險利率分母：2.0%</span>
      </div>

      <div class="card kpi-card">
        <span class="kpi-label">最大歷史回撤 (Max DD)</span>
        <span class="kpi-val text-loss font-mono">{{ selectedRun.maxDrawdown }}</span>
        <span class="kpi-sub font-mono text-muted">回撤安全臨界：-10.0%</span>
      </div>

      <div class="card kpi-card">
        <span class="kpi-label">交易勝率 / 總單數</span>
        <div class="kpi-val font-mono">{{ selectedRun.winRate }} <span class="val-sub">({{ selectedRun.tradesCount }} 筆)</span></div>
        <span class="kpi-sub font-mono text-muted">Profit Factor: 1.94</span>
      </div>
    </div>

    <!-- Main Content Layout -->
    <div class="backtest-layout">
      <!-- Left History Runs List -->
      <div class="runs-list-col card">
        <div class="card-header">
          <div class="card-title">回測歷史紀錄</div>
          <div class="card-actions-row">
            <span class="badge badge-neutral">{{ historyRuns.length }} 任務</span>
          </div>
        </div>
        <div class="card-body list-body">
          <div
            v-for="r in historyRuns"
            :key="r.id"
            :class="['run-item', { active: selectedRun.id === r.id }]"
            @click="selectedRun = r"
          >
            <div class="run-header">
              <span class="run-strat">{{ r.strategyName }}</span>
              <span class="badge badge-accent font-mono">{{ r.timeframe }}</span>
            </div>
            <div class="run-meta font-mono text-muted">
              <span>{{ r.symbol }}</span> · <span>{{ r.startDate }} ~ {{ r.endDate }}</span>
            </div>
            <div class="run-perf font-mono">
              <span class="text-profit">{{ r.totalReturn }}</span>
              <span class="perf-divider">|</span>
              <span>Sharpe {{ r.sharpe }}</span>
              <span class="perf-divider">|</span>
              <span class="text-loss">DD {{ r.maxDrawdown }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Detail / Simulation Chart Area -->
      <div class="run-detail-col card">
        <div class="card-header">
          <div class="card-title">
            <span>回測淨值曲線與模擬成交 ({{ selectedRun.strategyName }})</span>
            <span class="badge badge-neutral">Closed Bar Execution</span>
          </div>
          <div class="detail-actions">
            <button type="button" class="btn btn-sm btn-secondary">導出 CSV 報表</button>
            <button type="button" class="btn btn-sm btn-primary">轉化為 Bot 策略製品</button>
          </div>
        </div>
        <div class="card-body detail-body">
          <!-- Simulation Canvas Placeholder with Terminal Grid -->
          <div class="chart-canvas-box">
            <div class="canvas-header">
              <div class="canvas-title font-mono">EQUITY CURVE SIMULATION (15M TICKS)</div>
              <div class="canvas-legend">
                <span class="leg-item"><span class="leg-color leg-gold"></span> 策略淨值</span>
                <span class="leg-item"><span class="leg-color leg-gray"></span> 基準買入持有</span>
              </div>
            </div>
            <!-- SVG Curve Demo -->
            <div class="svg-container">
              <svg viewBox="0 0 700 220" class="backtest-svg" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="btGoldGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#dcb347" stop-opacity="0.25"/>
                    <stop offset="100%" stop-color="#dcb347" stop-opacity="0.0"/>
                  </linearGradient>
                </defs>
                <path d="M0 180 Q100 170 200 130 T400 100 T600 50 L700 30 L700 220 L0 220 Z" fill="url(#btGoldGrad)"/>
                <path d="M0 180 Q100 170 200 130 T400 100 T600 50 L700 30" fill="none" stroke="#dcb347" stroke-width="2.5"/>
                <path d="M0 180 Q150 190 300 160 T550 140 L700 120" fill="none" stroke="#506173" stroke-width="1.5" stroke-dasharray="4 4"/>
              </svg>
            </div>
          </div>

          <!-- Trade Details Table -->
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>時間 (收盤)</th>
                  <th>方向</th>
                  <th>進場價</th>
                  <th>出場價</th>
                  <th>部位張數</th>
                  <th>手續費 (USDT)</th>
                  <th>實現損益 (USDT)</th>
                  <th>累計淨值</th>
                </tr>
              </thead>
              <tbody class="font-mono">
                <tr>
                  <td>2026-09-30 23:45</td>
                  <td><span class="badge badge-neutral">LONG 平多</span></td>
                  <td>64,120.50</td>
                  <td>64,850.00</td>
                  <td>1.00</td>
                  <td>0.324</td>
                  <td class="text-profit">+72.95</td>
                  <td>1,184.20</td>
                </tr>
                <tr>
                  <td>2026-09-29 14:15</td>
                  <td><span class="badge badge-accent">SHORT 平空</span></td>
                  <td>65,300.00</td>
                  <td>64,920.00</td>
                  <td>1.00</td>
                  <td>0.326</td>
                  <td class="text-profit">+38.00</td>
                  <td>1,111.25</td>
                </tr>
                <tr>
                  <td>2026-09-28 08:30</td>
                  <td><span class="badge badge-neutral">LONG 止損</span></td>
                  <td>65,800.00</td>
                  <td>65,450.00</td>
                  <td>1.00</td>
                  <td>0.328</td>
                  <td class="text-loss">-35.00</td>
                  <td>1,073.25</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.backtest-page {
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


.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
}

.kpi-card {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.kpi-card.highlight-card {
  border-left: 3px solid var(--accent);
}
.kpi-label {
  font-size: 11px;
  color: var(--text-muted);
}
.kpi-val {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.val-sub {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: normal;
}
.kpi-sub {
  font-size: 10px;
}

.backtest-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: var(--space-4);
  flex: 1;
}

.runs-list-col {
  display: flex;
  flex-direction: column;
}

.run-item {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-secondary);
  cursor: pointer;
  transition: background-color 0.15s ease;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.run-item:hover {
  background-color: rgba(255, 255, 255, 0.03);
}
.run-item.active {
  background-color: rgba(220, 179, 71, 0.08);
  border-left: 2px solid var(--accent);
}

.run-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.run-strat {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.run-meta {
  font-size: 10.5px;
}
.run-perf {
  font-size: 11px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.perf-divider {
  color: #3b4856;
}

.run-detail-col {
  display: flex;
  flex-direction: column;
}
.detail-actions {
  display: flex;
  gap: 8px;
}
.detail-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.chart-canvas-box {
  background-color: #06080b;
  border: 1px solid var(--border-secondary);
  border-radius: 4px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.canvas-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.canvas-title {
  font-size: 11px;
  color: #7b8ea6;
  letter-spacing: 0.05em;
}
.canvas-legend {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #8b9eb5;
}
.leg-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.leg-color {
  width: 12px;
  height: 3px;
  border-radius: 1px;
}
.leg-gold { background-color: var(--accent); }
.leg-gray { background-color: #506173; }

.svg-container {
  height: 180px;
  width: 100%;
}
.backtest-svg {
  width: 100%;
  height: 100%;
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
  font-weight: 500;
  font-size: 11px;
}

.text-profit { color: var(--color-profit); }
.text-loss { color: var(--color-loss); }
.text-accent { color: var(--accent); }
.font-mono { font-family: var(--font-mono); }
</style>
