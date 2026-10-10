<script setup lang="ts">
import { ref } from 'vue';

interface BotItem {
  id: string;
  name: string;
  location: string;
  strategy: string;
  market: string;
  position: string;
  pnl: number;
  latency: number;
  uptime: number;
  status: 'running' | 'paused' | 'error';
}

const bots = ref<BotItem[]>([
  { id: '1', name: 'CAT-01', location: 'TOKYO', strategy: '趨勢追蹤', market: 'BTC-PERP', position: 'LONG 1.24 BTC', pnl: 5051.92, latency: 19, uptime: 412, status: 'running' },
  { id: '2', name: 'CAT-02', location: 'TAIPEI', strategy: '均值回歸', market: 'ETH-USDT 現貨', position: 'SHORT 2.8 ETH', pnl: -1012.87, latency: 46, uptime: 189, status: 'running' },
  { id: '3', name: 'CAT-03', location: 'SINGAPORE', strategy: '跨所套利', market: 'BTC 現貨/永續', position: 'HEDGED 0.35 BTC', pnl: 1169.90, latency: 20, uptime: 962, status: 'running' },
  { id: '4', name: 'CAT-04', location: 'FRANKFURT', strategy: '做市做爪', market: 'SOL-PERP', position: 'FLAT', pnl: 0.00, latency: 8, uptime: 8, status: 'paused' },
  { id: '5', name: 'CAT-05', location: 'SEOUL', strategy: '異常捕捉', market: 'BTC / SOL 現貨', position: 'LONG 18.5 SOL', pnl: -2450.80, latency: 214, uptime: 27, status: 'error' },
  { id: '6', name: 'CAT-06', location: 'LONDON', strategy: '波動獵手', market: 'ETH-PERP', position: 'SHORT 4.2 ETH', pnl: 3150.04, latency: 13, uptime: 331, status: 'running' }
]);

const showModal = ref(false);

function toggleBotStatus(b: BotItem) {
  if (b.status === 'running') {
    b.status = 'paused';
  } else {
    b.status = 'running';
  }
}
</script>

<template>
  <div class="relaxed-bots-view">
    <!-- Top Header -->
    <div class="page-top-bar">
      <div>
        <span class="sub-module-label">MODULE / BOT-MANAGEMENT</span>
        <h1 class="page-title">機器人管理</h1>
        <p class="page-desc">交易所節點、架構排查與 24/7 運行指標 · 模擬數據</p>
      </div>

      <button type="button" class="add-bot-btn" @click="showModal = true">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19"/>
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        <span>新增機器人</span>
      </button>
    </div>

    <!-- Status Cards: 4 RUNNING | 1 PAUSED | 1 ERROR -->
    <div class="status-summary-grid">
      <div class="summary-card">
        <span class="status-dot-wrap text-up">
          <span class="dot bg-up"></span>
          RUNNING
        </span>
        <span class="summary-num num">4</span>
      </div>

      <div class="summary-card">
        <span class="status-dot-wrap text-muted">
          <span class="dot bg-muted"></span>
          PAUSED
        </span>
        <span class="summary-num num">1</span>
      </div>

      <div class="summary-card">
        <span class="status-dot-wrap text-down">
          <span class="dot bg-down"></span>
          ERROR
        </span>
        <span class="summary-num num">1</span>
      </div>
    </div>

    <!-- Bot Fleet Table -->
    <div class="bots-card-panel">
      <div class="table-scroll">
        <table class="bots-table">
          <thead>
            <tr>
              <th>狀態</th>
              <th>機器人</th>
              <th>策略</th>
              <th>市場</th>
              <th>持倉</th>
              <th class="text-right">今日損益</th>
              <th class="text-right">延遲</th>
              <th class="text-right">運行時間</th>
              <th class="text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in bots" :key="b.id" class="bot-row">
              <td>
                <span class="status-tag" :class="`tag-${b.status}`">
                  <span class="dot-inner"></span>
                  {{ b.status.toUpperCase() }}
                </span>
              </td>
              <td>
                <span class="bot-name num">{{ b.name }}</span>
                <span class="bot-loc num">/ {{ b.location }}</span>
              </td>
              <td class="strat-cell">{{ b.strategy }}</td>
              <td class="market-cell num">{{ b.market }}</td>
              <td class="pos-cell num">{{ b.position }}</td>
              <td class="text-right num" :class="b.pnl >= 0 ? 'text-up' : 'text-down'">
                {{ b.pnl >= 0 ? '+' : '' }}{{ b.pnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
              </td>
              <td class="text-right num">{{ b.latency }} ms</td>
              <td class="text-right num">{{ b.uptime }} h</td>
              <td class="text-right">
                <div class="actions-group">
                  <button type="button" class="act-btn" @click="toggleBotStatus(b)" :title="b.status === 'running' ? '暫停' : '啟動'">
                    <svg v-if="b.status === 'running'" width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                      <rect x="6" y="4" width="4" height="16"/>
                      <rect x="14" y="4" width="4" height="16"/>
                    </svg>
                    <svg v-else width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                      <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                  </button>
                  <button type="button" class="act-btn" title="重新載入">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="23 4 23 10 17 10"/>
                      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="bots-footer">
        <span class="node-pings">
          <span class="dot bg-up"></span>
          Binance <span class="num">18ms</span>
          <span class="pipe">|</span>
          OKX <span class="num">24ms</span>
        </span>
        <span class="terminal-note">catOS Terminal · Simulated market data</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.relaxed-bots-view {
  display: flex;
  flex-direction: column;
  gap: var(--os-space-gap);
  padding: 1.25rem 1.5rem;
  max-width: 1720px;
  margin: 0 auto;
  width: 100%;
}

.page-top-bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 0.25rem;
}

.sub-module-label {
  font-size: 0.65rem;
  color: var(--os-text-muted);
  letter-spacing: 0.05em;
}

.page-title {
  font-size: 1.45rem;
  font-weight: 600;
  color: var(--os-text-primary);
  margin-top: 0.2rem;
}

.page-desc {
  font-size: 0.75rem;
  color: var(--os-text-muted);
  margin-top: 0.2rem;
}

.add-bot-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--os-up-bg);
  border: 1px solid var(--os-up-border);
  color: var(--os-up);
  padding: 0.45rem 0.85rem;
  border-radius: var(--os-card-radius);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.add-bot-btn:hover {
  background: rgba(52, 211, 153, 0.2);
}

.status-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--os-space-gap);
}

.summary-card {
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: var(--os-card-radius);
  padding: 1rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.status-dot-wrap {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.72rem;
  font-weight: 600;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.bg-up { background: var(--os-up); }
.bg-muted { background: var(--os-text-muted); }
.bg-down { background: var(--os-down); }

.summary-num {
  font-size: 1.35rem;
  font-weight: 600;
  color: var(--os-text-primary);
}

.bots-card-panel {
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: var(--os-card-radius);
  overflow: hidden;
}

.table-scroll {
  overflow-x: auto;
}

.bots-table {
  width: 100%;
  border-collapse: collapse;
}

.bots-table th {
  padding: 0.75rem 1rem;
  font-size: 0.7rem;
  color: var(--os-text-muted);
  font-weight: 400;
  border-bottom: 1px solid var(--os-border-subtle);
  background: rgba(0, 0, 0, 0.15);
}

.bot-row {
  border-bottom: 1px solid var(--os-border-subtle);
  transition: background 0.15s ease;
}

.bot-row:last-child {
  border-bottom: none;
}

.bot-row:hover {
  background: var(--os-bg-card-hover);
}

.bots-table td {
  padding: 0.85rem 1rem;
  font-size: 0.78rem;
}

.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.68rem;
  font-weight: 600;
}

.dot-inner {
  width: 5px;
  height: 5px;
  border-radius: 50%;
}

.tag-running {
  color: var(--os-up);
}
.tag-running .dot-inner { background: var(--os-up); }

.tag-paused {
  color: var(--os-text-muted);
}
.tag-paused .dot-inner { background: var(--os-text-muted); }

.tag-error {
  color: var(--os-down);
}
.tag-error .dot-inner { background: var(--os-down); }

.bot-name {
  font-weight: 500;
  color: var(--os-text-primary);
}

.bot-loc {
  font-size: 0.7rem;
  color: var(--os-text-muted);
  margin-left: 0.25rem;
}

.strat-cell, .market-cell, .pos-cell {
  color: var(--os-text-secondary);
}

.actions-group {
  display: inline-flex;
  gap: 0.4rem;
}

.act-btn {
  background: var(--os-bg-surface);
  border: 1px solid var(--os-border-subtle);
  color: var(--os-text-secondary);
  width: 1.6rem;
  height: 1.6rem;
  border-radius: 4px;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: all 0.15s ease;
}

.act-btn:hover {
  color: var(--os-text-primary);
  border-color: var(--os-border-highlight);
}

.bots-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.25rem;
  border-top: 1px solid var(--os-border-subtle);
  font-size: 0.7rem;
  color: var(--os-text-muted);
}

.node-pings {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.pipe {
  margin: 0 0.25rem;
  color: var(--os-border-subtle);
}

.text-up { color: var(--os-up); }
.text-down { color: var(--os-down); }
.text-muted { color: var(--os-text-muted); }
</style>
