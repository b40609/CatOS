<script setup lang="ts">
import { computed } from 'vue';
import {
  useV0Engine,
  formatPct,
  formatMoney,
  viewFor,
  equitySeries,
  todayChange,
  todayTradeCount,
  lastSignal,
  positionsFor,
  type Bot
} from '@/state/v0-engine';

const props = withDefaults(
  defineProps<{
    showHeader?: boolean;
  }>(),
  {
    showHeader: true
  }
);

const emit = defineEmits<{
  (e: 'selectBot', botId: string): void;
}>();

const {
  bots,
  period,
  focusBotId,
  selectedBotId,
  strategies,
  togglePause,
  setFocusBot,
  selectBot
} = useV0Engine();

const runningCount = computed(() => bots.value.filter((b: Bot) => b.status === 'running').length);

function getStrategy(bot: Bot) {
  return strategies.value.find(s => s.id === bot.strategyId);
}

function handleRowClick(bot: Bot) {
  selectBot(bot.id);
  emit('selectBot', bot.id);
}

function handlePauseClick(e: Event, bot: Bot) {
  e.stopPropagation();
  togglePause(bot.id);
}

function toneOf(v: number) {
  if (v > 0) return 'text-gain';
  if (v < 0) return 'text-risk';
  return 'text-muted-foreground';
}

function formatUsd(v: number, withSign = false) {
  if (Number.isNaN(v)) return '—';
  const sign = withSign && v > 0 ? '+' : withSign && v < 0 ? '−' : '';
  return `${sign}$${Math.abs(v).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })}`;
}

// Sparkline SVG 繪製路徑
function getSparklinePath(bot: Bot) {
  const v = viewFor(bot, period.value);
  const pts = v.points.filter(p => !Number.isNaN(p));
  if (pts.length < 2) return '';
  const lo = Math.min(0, ...pts);
  const hi = Math.max(0, ...pts);
  const span = hi - lo || 1;
  const w = 84;
  const h = 20;
  const n = pts.length;
  let d = '';
  pts.forEach((pt, k) => {
    const x = (k / (n - 1)) * w;
    const y = 2 + ((hi - pt) / span) * (h - 4);
    d += `${k === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return d;
}

function isSparklineGain(bot: Bot) {
  const v = viewFor(bot, period.value);
  return v.ret >= 0;
}
</script>

<template>
  <div class="v0-bot-table-panel">
    <!-- Header (獨立展示時才渲染) -->
    <div v-if="showHeader" class="panel-header">
      <div class="header-left">
        <div class="title-row">
          <span class="v0-chip">V0 移植版</span>
          <h3 class="panel-title">量化策略矩陣</h3>
        </div>
        <span class="panel-meta">
          {{ runningCount }} 運作 · {{ bots.length - runningCount }} 暫停
        </span>
      </div>
    </div>

    <!-- Table Container -->
    <div class="table-container">
      <table class="bot-table">
        <thead>
          <tr>
            <th class="th-bot">機器人 · 策略</th>
            <th class="th-market">市場</th>
            <th class="th-legs">持倉</th>
            <th class="th-right">未實現</th>
            <th class="th-right">今日損益</th>
            <th class="th-right">{{ period }} 報酬</th>
            <th class="th-chart">{{ period }} 走勢</th>
            <th class="th-guard">回撤 / 停止線</th>
            <th class="th-right">今日成交</th>
            <th class="th-signal">最後訊號</th>
            <th class="th-action">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="bot in bots"
            :key="bot.id"
            class="bot-row"
            :class="{
              'is-paused': bot.status === 'paused',
              'is-focused': focusBotId === bot.id,
              'is-selected': selectedBotId === bot.id
            }"
            @mouseenter="setFocusBot(bot.id)"
            @mouseleave="setFocusBot(null)"
            @click="handleRowClick(bot)"
          >
            <!-- 機器人名稱與狀態 -->
            <td class="td-bot">
              <div class="bot-info-cell">
                <span
                  class="status-dot"
                  :class="bot.status === 'running' ? 'dot-running' : 'dot-paused'"
                ></span>
                <div class="bot-names">
                  <div class="bot-name">{{ bot.name }}</div>
                  <div class="strategy-name">{{ getStrategy(bot)?.file || bot.strategyId }}</div>
                </div>
              </div>
            </td>

            <!-- 市場標的 -->
            <td class="td-market">
              <div class="market-cell">
                <span class="symbol-tag">{{ bot.symbol }}</span>
                <span class="tf-tag">{{ bot.timeframe }}</span>
              </div>
            </td>

            <!-- 持倉腿數 -->
            <td class="td-legs">
              <span v-if="positionsFor([bot]).length > 0" class="legs-badge">
                {{ positionsFor([bot]).length }} 筆
              </span>
              <span v-else class="text-neutral-600 font-mono text-xs">無</span>
            </td>

            <!-- 未實現 -->
            <td class="td-right">
              <span
                class="font-mono text-xs tabular-nums"
                :class="toneOf(positionsFor([bot]).reduce((s, p) => s + p.upnl, 0))"
              >
                {{ formatUsd(positionsFor([bot]).reduce((s, p) => s + p.upnl, 0), true) }}
              </span>
            </td>

            <!-- 今日損益 -->
            <td class="td-right">
              <div class="today-pnl font-mono text-xs tabular-nums" :class="toneOf(todayChange(equitySeries(bot)).pnl)">
                {{ formatUsd(todayChange(equitySeries(bot)).pnl, true) }}
                <span class="sub-pct">{{ formatPct(todayChange(equitySeries(bot)).pct) }}</span>
              </div>
            </td>

            <!-- 週期報酬 -->
            <td class="td-right">
              <span class="font-mono text-xs tabular-nums font-bold" :class="toneOf(viewFor(bot, period).ret)">
                {{ formatPct(viewFor(bot, period).ret) }}
              </span>
            </td>

            <!-- Sparkline 微圖 -->
            <td class="td-chart">
              <svg width="84" height="20" class="sparkline-svg">
                <line x1="0" x2="84" y1="10" y2="10" stroke="#282c31" stroke-dasharray="2 2" />
                <path
                  :d="getSparklinePath(bot)"
                  fill="none"
                  :stroke="isSparklineGain(bot) ? '#65cba7' : '#ed7665'"
                  stroke-width="1.3"
                />
              </svg>
            </td>

            <!-- 回撤 / 停止線 Meter -->
            <td class="td-guard">
              <div class="guard-cell">
                <div class="meter-bar">
                  <div
                    class="meter-fill"
                    :style="{
                      width: `${Math.min(100, Math.max(0, (viewFor(bot, '30D').ddNow / bot.guard) * 100))}%`
                    }"
                    :class="(viewFor(bot, '30D').ddNow / bot.guard) >= 0.75 ? 'fill-danger' : 'fill-warn'"
                  ></div>
                  <!-- 75% 警戒標線 -->
                  <div class="warn-line" style="left: 75%"></div>
                </div>
                <div class="guard-labels font-mono text-[10px]">
                  <span class="text-neutral-400">{{ formatPct(viewFor(bot, '30D').ddNow) }}</span>
                  <span class="text-neutral-500">/ {{ bot.guard }}%</span>
                </div>
              </div>
            </td>

            <!-- 今日成交 -->
            <td class="td-right font-mono text-xs text-neutral-300">
              {{ todayTradeCount(bot) }} 筆
            </td>

            <!-- 最後訊號 -->
            <td class="td-signal font-mono text-xs">
              <span class="signal-tag">{{ lastSignal(bot) }}</span>
            </td>

            <!-- 操作 -->
            <td class="td-action">
              <button
                type="button"
                class="btn-pause"
                :title="bot.status === 'running' ? '暫停機器人' : '繼續運行'"
                @click="handlePauseClick($event, bot)"
              >
                {{ bot.status === 'running' ? '⏸ 暫停' : '▶ 啟動' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.v0-bot-table-panel {
  display: flex;
  flex-direction: column;
  background: transparent;
  border: none;
  border-radius: 4px;
  overflow: hidden;
  height: 100%;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #181c21;
  border-bottom: 1px solid #282c31;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.v0-chip {
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  background: #181c21;
  color: #e8b45e;
  border: 1px solid #282c31;
  font-family: monospace;
}

.panel-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #e5e8ec;
}

.panel-meta {
  font-size: 11px;
  color: #90969d;
  font-family: monospace;
}

.badge-hint {
  font-size: 10px;
  color: #90969d;
  background: #13161a;
  border: 1px solid #282c31;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: monospace;
}

.table-container {
  flex: 1;
  overflow-x: auto;
  overflow-y: auto;
  background: #13161a;
}

.bot-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  min-width: 920px;
}

.bot-table thead tr {
  background: #0f1216;
  border-bottom: 1px solid #24282e;
  position: sticky;
  top: 0;
  z-index: 2;
}

.bot-table th {
  padding: 7px 10px;
  font-size: 11px;
  font-family: inherit;
  font-weight: 500;
  color: #90969d;
  white-space: nowrap;
  border-bottom: 1px solid #24282e;
}

.th-right {
  text-align: right;
}

.bot-row {
  border-bottom: 1px solid #24282e;
  transition: background 0.15s;
  cursor: pointer;
}

.bot-row:hover {
  background: #1d2126;
}

.bot-row.is-focused,
.bot-row.is-selected {
  background: rgba(232, 180, 94, 0.12);
  border-left: 2px solid #e8b45e;
}

.bot-row.is-paused {
  opacity: 0.6;
}

.bot-table td {
  padding: 8px 10px;
  white-space: nowrap;
}

.td-right {
  text-align: right;
}

.bot-info-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-running {
  background: #65cba7;
  box-shadow: 0 0 6px rgba(101, 203, 167, 0.6);
}

.dot-paused {
  background: #90969d;
}

.bot-names {
  display: flex;
  flex-direction: column;
}

.bot-name {
  font-size: 12px;
  font-weight: 600;
  color: #e5e8ec;
}

.strategy-name {
  font-size: 10px;
  font-family: monospace;
  color: #90969d;
}

.market-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: monospace;
}

.symbol-tag {
  font-size: 11px;
  color: #e5e8ec;
  font-weight: 600;
}

.tf-tag {
  font-size: 10px;
  color: #90969d;
}

.legs-badge {
  font-family: monospace;
  font-size: 11px;
  background: #181c21;
  color: #e8b45e;
  padding: 1px 6px;
  border-radius: 3px;
  border: 1px solid #282c31;
}

.today-pnl {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.sub-pct {
  font-size: 10px;
  color: #90969d;
}

.sparkline-svg {
  display: block;
}

.guard-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: 110px;
}

.meter-bar {
  position: relative;
  height: 5px;
  background: #181c21;
  border: 1px solid #282c31;
  border-radius: 3px;
  overflow: hidden;
}

.meter-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s;
}

.fill-warn {
  background: #e8b45e;
}

.fill-danger {
  background: #ed7665;
}

.warn-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: #90969d;
}

.guard-labels {
  display: flex;
  justify-content: space-between;
}

.signal-tag {
  color: #90969d;
  font-size: 11px;
}

.btn-pause {
  background: #181c21;
  border: 1px solid #282c31;
  color: #90969d;
  font-size: 10px;
  font-family: monospace;
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-pause:hover {
  background: #1d2126;
  color: #e5e8ec;
  border-color: #e8b45e;
}

.text-gain {
  color: #65cba7 !important;
}

.text-risk {
  color: #ed7665 !important;
}
</style>
