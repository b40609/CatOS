<script setup lang="ts">
import { ref, computed } from 'vue';
import { usePreferences } from '@/state/usePreferences';

const { preferences } = usePreferences();

function cleanDetail(detail?: string): string {
  if (!detail) return preferences.value.proEnglishLabels ? 'STANDBY' : '等待訊號';
  return detail.replace(/^(多|空)\s*/, '');
}

export type TimeframePeriod = '4H' | '1D' | '7D';

export interface PerformanceData {
  returnPct: string;
  returnUsdt: string;
  isPositive: boolean;
  sparkline: number[];
}

export interface BotQueueRow {
  id: string;
  name: string;
  strategy: string;
  state: 'running' | 'paused';
  unrealizedPnl: string;
  unrealizedPnlPositive: boolean;
  todayPnl: string;
  todayPnlPct: string;
  todayPnlPositive: boolean;
  // 3 種不同週期的表現數據
  perf: Record<TimeframePeriod, PerformanceData>;
  // 抽屜所需數據
  market: string;
  timeframe: string;
  maxDrawdownPct: string;
  winRatePct: string;
  markPrice: string;
  drawdownPct: string;
  stoplinePct: string;
  drawdownRatio: number;
  recentFills: Array<{
    time: string;
    side: '多' | '空';
    price: string;
    pnlPct: string;
    positive: boolean;
  }>;
  // 新版即時態勢資料
  liveState?: {
    type: 'long' | 'short' | 'idle';
    label: string;
    detail: string;
  };
}

export interface BotQueueProps {
  bots?: any[];
  showHeader?: boolean;
  period?: TimeframePeriod;
  mode?: 'new' | 'old';
}

const props = withDefaults(defineProps<BotQueueProps>(), {
  showHeader: false,
  period: '7D',
  mode: 'new'
});

const internalPeriod = ref<TimeframePeriod>('7D');
const activePeriod = computed<TimeframePeriod>(() => props.period || internalPeriod.value);

const bots = ref<BotQueueRow[]>([
  {
    id: 'tabby-01',
    name: 'Tabby',
    strategy: 'breakout_v2 v2.2',
    state: 'running',
    liveState: { type: 'long', label: '多頭持倉', detail: '多 0.12 BTC' },
    unrealizedPnl: '+79.26',
    unrealizedPnlPositive: true,
    todayPnl: '-50.09',
    todayPnlPct: '-0.45%',
    todayPnlPositive: false,
    perf: {
      '4H': {
        returnPct: '+0.18%',
        returnUsdt: '+18',
        isPositive: true,
        sparkline: [20, 22, 21, 24, 25, 28]
      },
      '1D': {
        returnPct: '-0.45%',
        returnUsdt: '-50',
        isPositive: false,
        sparkline: [35, 32, 28, 24, 22, 20, 22]
      },
      '7D': {
        returnPct: '+0.68%',
        returnUsdt: '+68',
        isPositive: true,
        sparkline: [10, 12, 15, 22, 28, 32, 40, 42, 38, 30, 24, 28, 26, 28]
      }
    },
    market: 'BTCUSDT',
    timeframe: '15m',
    maxDrawdownPct: '-4.65%',
    winRatePct: '65%',
    markPrice: '62,140.5',
    drawdownPct: '-4.3%',
    stoplinePct: '-8%',
    drawdownRatio: 4.3 / 8.0,
    recentFills: [
      { time: '10/6 04:57', side: '多', price: '59,184.2', pnlPct: '+0.25%', positive: true },
      { time: '10/5 17:57', side: '多', price: '63,232.2', pnlPct: '-0.56%', positive: false },
      { time: '10/5 12:57', side: '多', price: '62,425.8', pnlPct: '+0.50%', positive: true }
    ]
  },
  {
    id: 'calico-02',
    name: 'Calico',
    strategy: 'trend_follow v3.0',
    state: 'running',
    liveState: { type: 'long', label: '多頭持倉', detail: '多 2.40 ETH' },
    unrealizedPnl: '-206.93',
    unrealizedPnlPositive: false,
    todayPnl: '-144.28',
    todayPnlPct: '-1.37%',
    todayPnlPositive: false,
    perf: {
      '4H': {
        returnPct: '-0.85%',
        returnUsdt: '-85',
        isPositive: false,
        sparkline: [25, 22, 18, 15, 12, 10]
      },
      '1D': {
        returnPct: '-1.37%',
        returnUsdt: '-144',
        isPositive: false,
        sparkline: [30, 25, 20, 16, 12, 8, 6]
      },
      '7D': {
        returnPct: '-3.53%',
        returnUsdt: '-353',
        isPositive: false,
        sparkline: [35, 33, 30, 28, 25, 20, 22, 18, 14, 10, 8, 5, 4]
      }
    },
    market: 'ETHUSDT',
    timeframe: '1h',
    maxDrawdownPct: '-7.10%',
    winRatePct: '48%',
    markPrice: '2,450.2',
    drawdownPct: '-6.9%',
    stoplinePct: '-8%',
    drawdownRatio: 6.9 / 8.0,
    recentFills: [
      { time: '10/6 05:12', side: '多', price: '2,488.5', pnlPct: '-1.20%', positive: false },
      { time: '10/5 18:00', side: '多', price: '2,510.0', pnlPct: '-0.85%', positive: false }
    ]
  },
  {
    id: 'mochi-03',
    name: 'Mochi',
    strategy: 'grid_mm v1.4',
    state: 'running',
    liveState: { type: 'idle', label: '空倉待機', detail: '等待突破訊號' },
    unrealizedPnl: '-23.40',
    unrealizedPnlPositive: false,
    todayPnl: '-11.54',
    todayPnlPct: '-0.11%',
    todayPnlPositive: false,
    perf: {
      '4H': {
        returnPct: '+0.42%',
        returnUsdt: '+42',
        isPositive: true,
        sparkline: [15, 16, 18, 20, 22, 24]
      },
      '1D': {
        returnPct: '-0.11%',
        returnUsdt: '-11',
        isPositive: false,
        sparkline: [22, 20, 18, 19, 21, 20]
      },
      '7D': {
        returnPct: '+1.77%',
        returnUsdt: '+177',
        isPositive: true,
        sparkline: [12, 10, 14, 13, 16, 18, 15, 20, 22, 24, 25, 27]
      }
    },
    market: 'SOLUSDT',
    timeframe: '5m',
    maxDrawdownPct: '-1.80%',
    winRatePct: '72%',
    markPrice: '152.8',
    drawdownPct: '-0.3%',
    stoplinePct: '-5%',
    drawdownRatio: 0.3 / 5.0,
    recentFills: [
      { time: '10/6 05:12', side: '多', price: '152.4', pnlPct: '+0.15%', positive: true }
    ]
  },
  {
    id: 'shiro-04',
    name: 'Shiro',
    strategy: 'pairs_btc_eth v0.9',
    state: 'paused',
    unrealizedPnl: '-64.36',
    unrealizedPnlPositive: false,
    todayPnl: '0.00',
    todayPnlPct: '0.00%',
    todayPnlPositive: false,
    perf: {
      '4H': {
        returnPct: '0.00%',
        returnUsdt: '0',
        isPositive: false,
        sparkline: [10, 10, 10, 10, 10]
      },
      '1D': {
        returnPct: '0.00%',
        returnUsdt: '0',
        isPositive: false,
        sparkline: [10, 10, 10, 10, 10]
      },
      '7D': {
        returnPct: '-2.17%',
        returnUsdt: '-217',
        isPositive: false,
        sparkline: [25, 24, 22, 20, 18, 16, 17, 14, 12, 10, 9]
      }
    },
    market: 'BTC/ETH',
    timeframe: '1h',
    maxDrawdownPct: '-4.20%',
    winRatePct: '55%',
    markPrice: '0.0385',
    drawdownPct: '-3.6%',
    stoplinePct: '-6%',
    drawdownRatio: 3.6 / 6.0,
    recentFills: [
      { time: '10/4 16:00', side: '空', price: '0.0388', pnlPct: '+0.40%', positive: true }
    ]
  }
]);

const displayBots = computed(() => bots.value.filter(b => b.state === 'running'));

const emit = defineEmits<{
  (e: 'selectBot', botId: string): void;
  (e: 'focusBot', botId: string | null): void;
}>();

const selectedBotId = ref<string | null>(null);

function selectBot(b: BotQueueRow) {
  selectedBotId.value = b.id;
  emit('selectBot', b.id);
}

function generateSparklineSvg(points: number[]) {
  if (!points || points.length < 2) return '';
  const width = 68;
  const height = 20;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;

  const coords = points.map((val, idx) => {
    const x = (idx / (points.length - 1)) * (width - 4) + 2;
    const y = height - 2 - ((val - min) / range) * (height - 6);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return coords.join(' ');
}
</script>

<template>
  <div class="bot-queue-widget">
    <div class="table-container">
      <table class="bot-table">
        <thead>
          <tr>
            <th class="th-bot">{{ preferences.proEnglishLabels ? 'BOT · STRATEGY' : '機器人 · 策略' }}</th>
            <th v-if="mode === 'new'" class="th-state text-left">{{ preferences.proEnglishLabels ? 'POSTURE / SIDE' : '當前態勢' }}</th>
            <th v-else class="th-unrealized text-right">{{ preferences.proEnglishLabels ? 'uPnL' : '未實現' }}</th>
            <th class="th-today text-right">{{ preferences.proEnglishLabels ? 'DAILY PnL' : '今日' }}</th>
            <th class="th-return text-right">{{ preferences.proEnglishLabels ? 'RETURN' : '報酬' }}</th>
            <th class="th-trend text-right">{{ preferences.proEnglishLabels ? 'TREND' : '走勢' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="b in displayBots"
            :key="b.id"
            class="bot-row"
            :class="{ 'is-selected': selectedBotId === b.id }"
            @click="selectBot(b)"
          >
            <!-- 1. 機器人 · 策略 -->
            <td class="td-bot">
              <div class="bot-info-cell">
                <span
                  class="status-indicator"
                  :class="[
                    b.state === 'paused' ? 'is-paused' :
                    (b.drawdownRatio >= 0.6 ? 'is-warning' : 'is-running')
                  ]"
                  :title="b.state === 'paused' ? '已暫停' : (b.drawdownRatio >= 0.6 ? '回撤預警 (接近停損線)' : '正常運行')"
                ></span>
                <div class="bot-text-group">
                  <span class="bot-name">{{ b.name }}</span>
                  <span class="bot-strategy mono">{{ b.strategy }}</span>
                </div>
              </div>
            </td>

            <!-- 2. 當前態勢 (★ 定案：TradingView 幾何箭頭) vs 未實現損益 (舊版) -->
            <td v-if="mode === 'new'" class="td-state text-left">
              <div class="live-state-cell">
                <span
                  class="badge-tv mono font-bold"
                  :class="`is-${b.liveState?.type || 'idle'}`"
                >
                  {{ b.liveState?.type === 'long' ? '▲ LONG' : (b.liveState?.type === 'short' ? '▼ SHORT' : '○ IDLE') }}
                  <span class="tv-detail text-muted font-normal">{{ cleanDetail(b.liveState?.detail) }}</span>
                </span>
              </div>
            </td>
            <td v-else class="td-unrealized text-right">
              <span
                class="mono num-unrealized"
                :class="b.unrealizedPnlPositive ? 'text-green' : 'text-red'"
              >
                {{ b.unrealizedPnl }}
              </span>
            </td>

            <!-- 3. 今日損益 -->
            <td class="td-today text-right">
              <div class="today-cell">
                <span
                  class="mono num-today-val"
                  :class="b.todayPnl === '0.00' ? 'text-neutral' : (b.todayPnl.startsWith('-') ? 'text-red' : 'text-green')"
                >
                  {{ b.todayPnl }}
                </span>
                <span
                  class="mono num-today-pct"
                  :class="b.todayPnlPct === '0.00%' ? 'text-neutral' : (b.todayPnlPct.startsWith('-') ? 'text-red' : 'text-green')"
                >
                  {{ b.todayPnlPct }}
                </span>
              </div>
            </td>

            <!-- 4. 報酬 (支援 4H / 1D / 7D 切換) -->
            <td class="td-return text-right">
              <div class="return-cell">
                <span
                  class="mono return-pct font-bold"
                  :class="b.perf[activePeriod].returnPct === '0.00%' ? 'text-neutral' : (b.perf[activePeriod].isPositive ? 'text-green' : 'text-red')"
                >
                  {{ b.perf[activePeriod].returnPct }}
                </span>
                <span
                  class="mono return-usdt text-2xs"
                  :class="b.perf[activePeriod].returnUsdt === '0' ? 'text-neutral' : (b.perf[activePeriod].isPositive ? 'text-green' : 'text-red')"
                >
                  {{ b.perf[activePeriod].returnUsdt }}
                </span>
              </div>
            </td>

            <!-- 5. 走勢 (Sparkline) -->
            <td class="td-trend text-right">
              <div class="sparkline-wrapper">
                <svg class="sparkline-svg" viewBox="0 0 68 20" preserveAspectRatio="none">
                  <polyline
                    fill="none"
                    :stroke="b.perf[activePeriod].returnPct === '0.00%' ? 'var(--text-muted)' : (b.perf[activePeriod].isPositive ? 'var(--gain, #65cba7)' : 'var(--risk, #ed7665)')"
                    stroke-width="1.6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    :points="generateSparklineSvg(b.perf[activePeriod].sparkline)"
                  />
                </svg>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.bot-queue-widget {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  background: transparent;
  color: #e5e8ec;
  font-family: inherit;
  position: relative;
  overflow: hidden;
  container-type: inline-size;
  container-name: botqueue;
}

.table-container {
  flex: 1;
  overflow-x: auto;
  overflow-y: auto;
}

.bot-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

.bot-table thead th {
  padding: 7px 10px;
  color: #90969d;
  font-size: 11px;
  font-weight: 500;
  border-bottom: 1px solid #24282e;
  white-space: nowrap;
  background: #0f1216;
  position: sticky;
  top: 0;
  z-index: 2;
}

.bot-row {
  border-bottom: 1px solid #24282e;
  cursor: pointer;
  transition: background 0.15s ease;
}

.bot-row:hover {
  background: #1d2126;
}

.bot-row.is-selected {
  background: rgba(232, 180, 94, 0.12);
}

.bot-table td {
  padding: 8px 10px;
  vertical-align: middle;
  white-space: nowrap;
}

/* 1. 機器人 · 策略 */
.bot-info-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-indicator {
  width: 6.5px;
  height: 6.5px;
  border-radius: 50%;
  flex-shrink: 0;
  transition: all 0.15s ease;
}

.status-indicator.is-running {
  background: #65cba7;
  box-shadow: 0 0 3px rgba(101, 203, 167, 0.4);
}

.status-indicator.is-warning {
  background: #e8b45e;
  box-shadow: 0 0 4px rgba(232, 180, 94, 0.55);
}

.status-indicator.is-paused {
  background: transparent;
  border: 1.5px solid #90969d;
}

.bot-text-group {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.bot-name {
  font-size: 12px;
  font-weight: 600;
  color: #e5e8ec;
}

.bot-strategy {
  font-size: 10px;
  color: #90969d;
}

/* 2. 當前態勢 (新版) vs 未實現 (舊版) */
.live-state-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.live-state-badge {
  font-size: 9.5px;
  font-weight: 700;
  padding: 1.5px 5px;
  border-radius: 3px;
  line-height: 1.2;
}

.live-state-badge.is-long {
  background: rgba(101, 203, 167, 0.12);
  color: #65cba7;
  border: 1px solid rgba(101, 203, 167, 0.3);
}

.live-state-badge.is-short {
  background: rgba(237, 118, 101, 0.12);
  color: #ed7665;
  border: 1px solid rgba(237, 118, 101, 0.3);
}

.live-state-badge.is-idle {
  background: #181c21;
  color: #90969d;
  border: 1px solid #282c31;
}

/* ★ 定案：TradingView 幾何箭頭樣式 */
.badge-tv {
  font-size: 10.5px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.badge-tv.is-long { color: #65cba7; }
.badge-tv.is-short { color: #ed7665; }
.badge-tv.is-idle { color: #90969d; }

.live-state-detail {
  font-size: 11px;
  color: #90969d;
}

.num-unrealized {
  font-size: 12px;
  font-weight: 600;
}

/* 3. 今日 */
.today-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
}

.num-today-val {
  font-size: 11.5px;
  font-weight: 600;
}

.num-today-pct {
  font-size: 10px;
}

/* 4. 報酬 (數值) */
.return-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
}

.return-pct {
  font-size: 11.5px;
}

.return-usdt {
  font-size: 10px;
}

/* 5. 走勢 */
.td-trend {
  text-align: right;
}

.sparkline-wrapper {
  width: 68px;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
}

.sparkline-svg {
  width: 100%;
  height: 100%;
  overflow: visible;
}

/* ================= 抽屜 Inspector Drawer ================= */
.drawer-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(2px);
  z-index: 50;
  display: flex;
  justify-content: flex-end;
}

.inspector-drawer {
  width: 320px;
  height: 100%;
  background: #181c21;
  border-left: 1px solid #282c31;
  box-shadow: -6px 0 20px rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  padding: 12px;
  gap: 10px;
  overflow-y: auto;
  animation: slideDrawer 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes slideDrawer {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.drawer-tag-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.drawer-tag {
  background: #13161a;
  color: #e5e8ec;
  border: 1px solid #282c31;
  font-size: 10.5px;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 600;
}

.drawer-status-chip {
  font-size: 10.5px;
  color: #90969d;
  display: flex;
  align-items: center;
  gap: 4px;
}

.pulse-green {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #65cba7;
}

.btn-drawer-close {
  background: transparent;
  border: none;
  color: #90969d;
  cursor: pointer;
  font-size: 12px;
  padding: 2px 4px;
}

.btn-drawer-close:hover {
  color: #e5e8ec;
}

.drawer-bot-name {
  font-size: 16px;
  font-weight: 700;
  color: #e5e8ec;
}

.drawer-bot-meta {
  font-size: 10px;
  color: #90969d;
}

.drawer-kpi-row {
  display: flex;
  justify-content: space-between;
  padding: 6px 8px;
  background: #13161a;
  border: 1px solid #282c31;
  border-radius: 4px;
}

.kpi-box {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.kpi-lbl {
  font-size: 9.5px;
  color: #90969d;
}

.kpi-val {
  font-size: 12px;
  font-weight: 700;
  color: #e5e8ec;
}

.drawer-chart-card {
  background: #13161a;
  border: 1px solid #282c31;
  border-radius: 4px;
  padding: 6px;
}

.chart-svg {
  width: 100%;
  height: 90px;
}

.drawer-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.block-title {
  font-size: 11px;
  font-weight: 600;
  color: #90969d;
}

.fills-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-height: 120px;
  overflow-y: auto;
}

.fill-item {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  padding: 3px 6px;
  background: #13161a;
  border: 1px solid #282c31;
  border-radius: 3px;
}

.fill-left {
  display: flex;
  gap: 6px;
}

/* ================= 通用工具色 ================= */
.text-green {
  color: #65cba7 !important;
}

.text-red {
  color: #ed7665 !important;
}

.text-neutral {
  color: #90969d !important;
}

.text-muted {
  color: #90969d;
}

.text-right {
  text-align: right;
}

.text-left {
  text-align: left;
}

.mono {
  font-family: var(--default-mono-font-family, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
}

/* ================= 容器自適應優化 (< 580px / < 380px) ================= */
@container botqueue (max-width: 580px) {
  .th-trend,
  .td-trend {
    display: none !important;
  }

  .bot-table thead th,
  .bot-table td {
    padding: 6px 6px;
  }

  .today-cell,
  .return-cell {
    gap: 0;
  }

  .num-today-pct,
  .return-usdt {
    display: none;
  }
}

@container botqueue (max-width: 380px) {
  .live-state-detail {
    display: none !important;
  }

  .bot-strategy {
    display: none !important;
  }
}
</style>
