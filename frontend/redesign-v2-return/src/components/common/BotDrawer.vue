<script setup lang="ts">
import { ref, computed } from 'vue';

export interface DrawerBotData {
  id: string;
  name: string;
  strategy: string;
  symbol: string;
  timeframe: string;
  state: 'running' | 'paused';
  lastSignal: string;
  returnPct: string;
  maxDrawdownPct: string;
  winRatePct: string;
  guardPct: string; // e.g. -8.0%
  drawdownNowPct: string; // e.g. -4.65%
  drawdownRatio: number; // e.g. 4.65 / 8.0 = 0.58
  legs: Array<{
    symbol: string;
    side: '多' | '空';
    qty: string;
    markPrice: string;
    upnl: string;
    positive: boolean;
  }>;
  recentTrades: Array<{
    time: string;
    side: '多' | '空';
    price: string;
    pnlPct: string;
    positive: boolean;
  }>;
}

const props = defineProps<{
  bot: DrawerBotData | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'togglePause', botId: string): void;
}>();

const selectedPeriod = ref<'4H' | '1D' | '7D' | '30D'>('7D');

function handleClose() {
  emit('close');
}

function handleToggle() {
  if (props.bot) {
    emit('togglePause', props.bot.id);
  }
}

function getMeterColor(ratio: number): string {
  if (ratio >= 0.85) return 'var(--risk, #ef4444)';
  if (ratio >= 0.6) return 'var(--accent, #f59e0b)';
  return 'var(--gain, #10b981)';
}
</script>

<template>
  <div v-if="bot" class="bot-drawer-backdrop" @click.self="handleClose">
    <aside class="bot-drawer-panel" role="dialog" aria-labelledby="bot-drawer-title">
      <!-- 頂部 Header -->
      <header class="drawer-header">
        <div class="header-top-row">
          <div class="tag-group font-mono text-2xs">
            <span class="scope-tag">機器人</span>
            <span
              class="state-badge"
              :class="bot.state === 'running' ? 'is-running' : 'is-paused'"
            >
              <span class="status-dot"></span>
              {{ bot.state === 'running' ? '模擬中' : '已暫停' }}
            </span>
          </div>
          <button type="button" class="btn-close" @click="handleClose" title="關閉抽屜">✕</button>
        </div>

        <h2 id="bot-drawer-title" class="drawer-title">{{ bot.name }}</h2>
        <p class="drawer-subtitle mono text-2xs text-muted">
          {{ bot.strategy }} · {{ bot.symbol }} {{ bot.timeframe }} · 最後訊號 {{ bot.lastSignal }}
        </p>
      </header>

      <!-- 滾動主要內容 -->
      <div class="drawer-scroll-body">
        <!-- 1. 績效與圖表區 -->
        <section class="drawer-section">
          <div class="kpi-segmented-row">
            <div class="kpi-grid mono">
              <div class="kpi-item">
                <span class="kpi-lbl text-3xs text-muted">過去 7 天</span>
                <span class="kpi-val text-green font-medium">{{ bot.returnPct }}</span>
              </div>
              <div class="kpi-item">
                <span class="kpi-lbl text-3xs text-muted">最大回撤</span>
                <span class="kpi-val text-red font-medium">{{ bot.maxDrawdownPct }}</span>
              </div>
              <div class="kpi-item">
                <span class="kpi-lbl text-3xs text-muted">勝率</span>
                <span class="kpi-val font-medium">{{ bot.winRatePct }}</span>
              </div>
            </div>

            <!-- 期間切換器 -->
            <div class="period-segmented mono text-2xs" role="radiogroup">
              <button
                type="button"
                :class="{ active: selectedPeriod === '1D' }"
                @click="selectedPeriod = '1D'"
              >
                1D
              </button>
              <button
                type="button"
                :class="{ active: selectedPeriod === '7D' }"
                @click="selectedPeriod = '7D'"
              >
                7D
              </button>
              <button
                type="button"
                :class="{ active: selectedPeriod === '30D' }"
                @click="selectedPeriod = '30D'"
              >
                30D
              </button>
            </div>
          </div>

          <!-- 雙軌淨值與回撤走勢圖 (SVG) -->
          <div class="drawer-chart-container">
            <svg class="chart-svg" viewBox="0 0 380 140" preserveAspectRatio="none">
              <!-- 網格基準線 -->
              <line x1="0" y1="20" x2="380" y2="20" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3 3" />
              <line x1="0" y1="55" x2="380" y2="55" stroke="rgba(255,255,255,0.06)" stroke-dasharray="3 3" />
              <line x1="0" y1="80" x2="380" y2="80" stroke="rgba(255,255,255,0.12)" stroke-dasharray="2 2" />

              <!-- 淨值走勢白色曲線 -->
              <path
                d="M 10 70 Q 60 55, 110 40 T 190 25 T 260 45 T 320 35 T 370 28"
                fill="none"
                stroke="#ffffff"
                stroke-width="1.8"
              />

              <!-- 水下回撤紅色漸層面積圖 -->
              <defs>
                <linearGradient id="drawerRedGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="rgba(239, 68, 68, 0.45)" />
                  <stop offset="100%" stop-color="rgba(239, 68, 68, 0.05)" />
                </linearGradient>
              </defs>
              <path
                d="M 10 95 Q 70 98, 140 96 T 220 106 T 300 115 T 370 118 L 370 95 Z"
                fill="url(#drawerRedGrad)"
              />
              <path
                d="M 10 95 Q 70 98, 140 96 T 220 106 T 300 115 T 370 118"
                fill="none"
                stroke="#ef4444"
                stroke-width="1.2"
              />

              <!-- 自動暫停線 (紅色虛線) -->
              <line x1="0" y1="128" x2="380" y2="128" stroke="#ef4444" stroke-dasharray="3 3" opacity="0.8" />
              <text x="10" y="124" fill="#ef4444" font-size="9" font-family="monospace">自動暫停停止線 {{ bot.guardPct }}</text>
            </svg>
          </div>

          <!-- 回撤佔比 Meter 尺規 -->
          <div class="meter-group">
            <div class="meter-info mono text-2xs">
              <span class="text-muted">當前回撤 / 停止線</span>
              <span class="tabular-nums">
                <span class="text-red font-medium">{{ bot.drawdownNowPct }}</span>
                <span class="text-muted"> / {{ bot.guardPct }}</span>
              </span>
            </div>
            <div class="meter-track">
              <div
                class="meter-fill"
                :style="{
                  width: `${Math.min(100, Math.round(bot.drawdownRatio * 100))}%`,
                  backgroundColor: getMeterColor(bot.drawdownRatio)
                }"
              ></div>
            </div>
          </div>
        </section>

        <!-- 2. 持倉部位 -->
        <section class="drawer-section">
          <h3 class="section-title">
            持倉 <span class="mono text-2xs text-muted font-normal">({{ bot.legs.length }})</span>
          </h3>
          <div v-if="bot.legs.length > 0" class="legs-table-wrap">
            <table class="legs-table mono text-2xs">
              <thead>
                <tr>
                  <th class="text-left">標的</th>
                  <th class="text-left">方向</th>
                  <th class="text-right">數量</th>
                  <th class="text-right">標記價</th>
                  <th class="text-right">未實現</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(leg, i) in bot.legs" :key="i">
                  <td>{{ leg.symbol }}</td>
                  <td>
                    <span :class="leg.side === '多' ? 'text-green' : 'text-red'">{{ leg.side }}</span>
                  </td>
                  <td class="text-right">{{ leg.qty }}</td>
                  <td class="text-right">{{ leg.markPrice }}</td>
                  <td class="text-right" :class="leg.positive ? 'text-green' : 'text-red'">{{ leg.upnl }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="empty-hint mono text-2xs text-muted">無在倉部位</p>
        </section>

        <!-- 3. 最近成交紀錄 -->
        <section class="drawer-section">
          <h3 class="section-title">
            最近成交紀錄 <span class="mono text-2xs text-muted font-normal">({{ bot.recentTrades.length }} 筆)</span>
          </h3>
          <ul class="trades-list mono text-2xs">
            <li v-for="(t, i) in bot.recentTrades" :key="i" class="trade-row">
              <span class="trade-time text-muted">{{ t.time }}</span>
              <span class="trade-side" :class="t.side === '多' ? 'text-green' : 'text-red'">{{ t.side }}</span>
              <span class="trade-price text-right">{{ t.price }}</span>
              <span class="trade-pnl text-right" :class="t.positive ? 'text-green' : 'text-red'">{{ t.pnlPct }}</span>
            </li>
          </ul>
        </section>
      </div>

      <!-- 底部操作列 (Sticky Footer) -->
      <footer class="drawer-footer">
        <p class="footer-hint text-3xs text-muted">
          {{ bot.state === 'running' ? '暫停只停新訊號，不平倉。' : '暫停中：持倉仍計入帳戶曝險。' }}
        </p>
        <button
          type="button"
          class="btn-toggle-pause"
          :class="bot.state === 'running' ? 'is-pause-btn' : 'is-resume-btn'"
          @click="handleToggle"
        >
          <span>{{ bot.state === 'running' ? '⏸ 暫停' : '▶ 繼續' }}</span>
        </button>
      </footer>
    </aside>
  </div>
</template>

<style scoped>
.bot-drawer-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(2px);
  z-index: 100;
  display: flex;
  justify-content: flex-end;
  animation: fadeIn 0.15s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.bot-drawer-panel {
  width: 440px;
  max-width: 90vw;
  height: 100vh;
  background: #0f131a;
  border-left: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 24px rgba(0, 0, 0, 0.6);
  animation: slideIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.drawer-header {
  padding: 14px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.header-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tag-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.scope-tag {
  border: 1px solid rgba(255, 255, 255, 0.3);
  padding: 1px 4px;
  border-radius: 2px;
  color: #e5e8ec;
}

.state-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.state-badge.is-running .status-dot {
  background: var(--gain, #10b981);
}

.state-badge.is-paused .status-dot {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.4);
}

.btn-close {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.5);
  font-size: 14px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 2px;
}

.btn-close:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.08);
}

.drawer-title {
  margin: 4px 0 0 0;
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
}

.drawer-scroll-body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.drawer-section {
  padding: 14px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.kpi-segmented-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.kpi-grid {
  display: flex;
  gap: 16px;
}

.kpi-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.kpi-val {
  font-size: 13px;
}

.period-segmented {
  display: flex;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  padding: 2px;
  gap: 2px;
}

.period-segmented button {
  background: transparent;
  border: none;
  color: rgba(255, 255, 255, 0.5);
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 2px;
  cursor: pointer;
}

.period-segmented button.active {
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
  font-weight: 600;
}

.drawer-chart-container {
  width: 100%;
  height: 140px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 4px;
  overflow: hidden;
}

.chart-svg {
  width: 100%;
  height: 100%;
}

.meter-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meter-info {
  display: flex;
  justify-content: space-between;
}

.meter-track {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
  overflow: hidden;
}

.meter-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.section-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #ffffff;
}

.legs-table {
  width: 100%;
  border-collapse: collapse;
}

.legs-table th {
  padding: 4px 0;
  color: rgba(255, 255, 255, 0.45);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.legs-table td {
  padding: 6px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.trades-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.trade-row {
  display: grid;
  grid-template-columns: 80px 30px 1fr 60px;
  align-items: center;
  padding: 5px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.empty-hint {
  padding: 8px 0;
}

.drawer-footer {
  padding: 10px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #0b0e14;
}

.btn-toggle-pause {
  padding: 5px 12px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.06);
  color: #ffffff;
  transition: all 0.15s ease;
}

.btn-toggle-pause:hover {
  background: rgba(255, 255, 255, 0.12);
}

.text-muted {
  color: rgba(255, 255, 255, 0.45);
}

.text-green {
  color: var(--gain, #10b981);
}

.text-red {
  color: var(--risk, #ef4444);
}

.text-2xs {
  font-size: 10px;
}

.text-3xs {
  font-size: 9px;
}

.mono {
  font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;
}
</style>
