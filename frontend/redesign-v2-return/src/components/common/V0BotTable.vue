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
  baseOf,
  type Bot
} from '@/state/v0-engine';
import { usePreferences } from '@/state/usePreferences';

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

const { preferences, setTableDualLayer, setProEnglishLabels } = usePreferences();

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
  const w = 72;
  const h = 18;
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

function getBotPosSummary(bot: Bot) {
  const pos = positionsFor([bot]);
  if (!pos || pos.length === 0) {
    return {
      hasPos: false,
      side: 'idle',
      qtyText: '0',
      notionalText: '$0 Notional',
      upnlVal: 0,
      upnlPct: 0
    };
  }
  const p = pos[0];
  const totalUpnl = pos.reduce((s, x) => s + x.upnl, 0);
  const totalNotional = pos.reduce((s, x) => s + x.notional, 0);
  const upnlPct = p.upnlPct ?? (totalNotional > 0 ? (totalUpnl / (totalNotional / 3.0)) * 100 : 0);
  return {
    hasPos: true,
    side: p.side,
    qtyText: `${p.qty} ${baseOf(p.symbol)}`,
    notionalText: `$${Math.round(totalNotional).toLocaleString()} · 3x Cross`,
    upnlVal: totalUpnl,
    upnlPct: upnlPct
  };
}
</script>

<template>
  <div class="v0-bot-table-panel">
    <!-- Header 工具列 (含雙層/單層對比切換開關) -->
    <div v-if="showHeader" class="panel-header">
      <div class="header-left">
        <div class="title-row">
          <span class="v0-chip">V0 移植版</span>
          <h3 class="panel-title">
            {{ preferences.proEnglishLabels ? 'QUANT BOT MATRIX' : '量化策略矩陣' }}
          </h3>
        </div>
        <span class="panel-meta mono">
          {{ runningCount }} {{ preferences.proEnglishLabels ? 'LIVE' : '運作' }} ·
          {{ bots.length - runningCount }} {{ preferences.proEnglishLabels ? 'PAUSED' : '暫停' }}
        </span>
      </div>

      <div class="header-actions">
        <!-- 核心對比開關: 雙層高階版 vs 原版單層 -->
        <div class="layout-toggle-group" role="group" aria-label="排版風格對比">
          <button
            type="button"
            class="toggle-btn"
            :class="{ active: preferences.tableDualLayer }"
            @click="setTableDualLayer(true)"
            title="開啟 Zero-Waste 雙層高階版面 (如附圖)"
          >
            ✦ 雙層高階版 (Dual-Layer)
          </button>
          <button
            type="button"
            class="toggle-btn"
            :class="{ active: !preferences.tableDualLayer }"
            @click="setTableDualLayer(false)"
            title="還原原版 10 欄單層平鋪"
          >
            原版單層 (Single)
          </button>
        </div>
      </div>
    </div>

    <!-- Table Container -->
    <div class="table-container">
      <!-- 方案 A：✦ 雙層高階版 (6 欄 Zero-Waste 緊湊量化終端) -->
      <table v-if="preferences.tableDualLayer" class="bot-table dual-layer-table">
        <thead>
          <tr>
            <th class="th-bot">{{ preferences.proEnglishLabels ? 'BOT / STRATEGY' : '機器人 · 策略' }}</th>
            <th class="th-pos">{{ preferences.proEnglishLabels ? 'POSITION / NOTIONAL' : '持倉規模 · 名義' }}</th>
            <th class="th-pnl text-right">{{ preferences.proEnglishLabels ? 'UNREALIZED PnL' : '未實現損益' }}</th>
            <th class="th-today text-right">{{ preferences.proEnglishLabels ? 'DAILY PnL & RET' : '今日損益 · 報酬' }}</th>
            <th class="th-guard">{{ preferences.proEnglishLabels ? 'DD / P6 GUARD' : '回撤 / P6 停止線' }}</th>
            <th class="th-chart text-right">{{ preferences.proEnglishLabels ? 'TREND & ACTION' : '走勢 · 操作' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="bot in bots"
            :key="bot.id"
            class="bot-row dual-row"
            :class="{
              'is-paused': bot.status === 'paused',
              'is-focused': focusBotId === bot.id,
              'is-selected': selectedBotId === bot.id
            }"
            @mouseenter="setFocusBot(bot.id)"
            @mouseleave="setFocusBot(null)"
            @click="handleRowClick(bot)"
          >
            <!-- 1. 機器人與策略 (雙層) -->
            <td class="td-bot">
              <div class="bot-info-cell">
                <span
                  class="status-dot"
                  :class="bot.status === 'running' ? 'dot-running' : 'dot-paused'"
                ></span>
                <div class="bot-dual-text">
                  <div class="bot-name font-bold">{{ bot.name }}</div>
                  <div class="bot-sub-meta mono text-2xs text-muted">
                    <span class="symbol-accent">{{ bot.symbol }}</span>
                    <span class="tf-mini">{{ bot.timeframe }}</span>
                    <span>· {{ getStrategy(bot)?.file || bot.strategyId }}</span>
                  </div>
                </div>
              </div>
            </td>

            <!-- 2. 持倉規模與態勢 (雙層 + 定案 TV 幾何箭頭風格切換) -->
            <td class="td-pos">
              <div class="pos-dual-cell">
                <div class="pos-top-row">
                  <!-- 風格 2: TradingView 幾何箭頭 + 槓桿 (★ 使用者定案) -->
                  <!-- ★ 使用者定案：TradingView 幾何箭頭 -->
                  <span
                    class="badge-tv mono font-bold"
                    :class="getBotPosSummary(bot).side === 'long' ? 'is-long' : (getBotPosSummary(bot).side === 'short' ? 'is-short' : 'is-idle')"
                  >
                    {{ getBotPosSummary(bot).side === 'long' ? '▲ LONG' : (getBotPosSummary(bot).side === 'short' ? '▼ SHORT' : '○ FLAT') }}
                  </span>

                  <span class="qty-mono mono font-bold">{{ getBotPosSummary(bot).qtyText }}</span>
                </div>
                <div class="pos-sub-row mono text-2xs text-muted">
                  {{ getBotPosSummary(bot).notionalText }}
                </div>
              </div>
            </td>

            <!-- 3. 未實現損益 (雙層數值棧，對齊使用者附圖) -->
            <td class="td-pnl text-right mono">
              <div class="pnl-amount font-bold tabular-nums" :class="toneOf(getBotPosSummary(bot).upnlVal)">
                {{ formatUsd(getBotPosSummary(bot).upnlVal, true) }} USDT
              </div>
              <div class="pnl-pct text-2xs tabular-nums" :class="toneOf(getBotPosSummary(bot).upnlVal)">
                {{ getBotPosSummary(bot).upnlVal === 0 ? '0.00%' : formatPct(getBotPosSummary(bot).upnlPct) }}
              </div>
            </td>

            <!-- 4. 今日損益與週期報酬 (雙層合一) -->
            <td class="td-today text-right mono">
              <div class="today-pnl font-bold tabular-nums" :class="toneOf(todayChange(equitySeries(bot)).pnl)">
                {{ formatUsd(todayChange(equitySeries(bot)).pnl, true) }}
              </div>
              <div class="today-sub text-2xs" :class="toneOf(todayChange(equitySeries(bot)).pnl)">
                {{ formatPct(todayChange(equitySeries(bot)).pct) }} · {{ formatPct(viewFor(bot, period).ret) }} {{ period }}
              </div>
            </td>

            <!-- 5. 回撤 / P6 停止線 (雙層進度條) -->
            <td class="td-guard">
              <div class="guard-cell">
                <div class="guard-labels font-mono text-2xs flex justify-between">
                  <span class="text-neutral-400">DD {{ formatPct(viewFor(bot, '30D').ddNow) }}</span>
                  <span class="text-neutral-500">P6 / {{ bot.guard }}%</span>
                </div>
                <div class="meter-bar">
                  <div
                    class="meter-fill"
                    :style="{
                      width: `${Math.min(100, Math.max(0, (viewFor(bot, '30D').ddNow / bot.guard) * 100))}%`
                    }"
                    :class="(viewFor(bot, '30D').ddNow / bot.guard) >= 0.75 ? 'fill-danger' : 'fill-warn'"
                  ></div>
                  <div class="warn-line" style="left: 75%"></div>
                </div>
              </div>
            </td>

            <!-- 6. 走勢與操作 -->
            <td class="td-chart text-right">
              <div class="chart-action-cell">
                <svg width="72" height="18" class="sparkline-svg">
                  <line x1="0" x2="72" y1="9" y2="9" stroke="#282c31" stroke-dasharray="2 2" />
                  <path
                    :d="getSparklinePath(bot)"
                    fill="none"
                    :stroke="isSparklineGain(bot) ? '#65cba7' : '#ed7665'"
                    stroke-width="1.3"
                  />
                </svg>
                <button
                  type="button"
                  class="btn-pause-compact"
                  :title="bot.status === 'running' ? '暫停' : '繼續'"
                  @click="handlePauseClick($event, bot)"
                >
                  {{ bot.status === 'running' ? '⏸' : '▶' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 方案 B：原版單層平鋪表格 (10 欄) -->
      <table v-else class="bot-table original-table">
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
                {{ bot.status === 'running' ? '暫停' : '啟動' }}
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
  padding: 6px 12px;
  background: #111418;
  border-bottom: 1px solid #24282e;
  gap: 8px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.v0-chip {
  font-size: 9.5px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 2px;
  background: #181c21;
  color: #e8b45e;
  border: 1px solid #282c31;
  font-family: monospace;
}

.panel-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #e5e8ec;
}

.panel-meta {
  font-size: 10.5px;
  color: #90969d;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 雙層/單層對比開關 */
.layout-toggle-group {
  display: flex;
  background: #181c21;
  border: 1px solid #282c31;
  border-radius: 3px;
  padding: 2px;
  gap: 2px;
}

.toggle-btn {
  background: transparent;
  border: none;
  color: #90969d;
  font-size: 10px;
  font-family: var(--default-mono-font-family, monospace);
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 2px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}

.toggle-btn:hover {
  color: #e5e8ec;
}

.toggle-btn.active {
  background: #1f2732;
  color: #e8b45e;
  border: 1px solid rgba(232, 180, 94, 0.4);
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
  font-size: 11.5px;
}

.bot-table thead th {
  padding: 6px 10px;
  color: #90969d;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.03em;
  border-bottom: 1px solid #24282e;
  white-space: nowrap;
  background: #0f1216;
  position: sticky;
  top: 0;
  z-index: 2;
  font-family: var(--default-mono-font-family, monospace);
  text-align: left;
}

/* 確保各欄位表頭與資料格精準對齊 */
.th-bot, .td-bot { text-align: left; }
.th-pos, .td-pos { text-align: left; }
.th-guard, .td-guard { text-align: left; }
.th-pnl, .td-pnl { text-align: right; }
.th-today, .td-today { text-align: right; }
.th-chart, .td-chart { text-align: right; }

.bot-row {
  border-bottom: 1px solid #20242a;
  cursor: pointer;
  transition: background 0.15s ease;
}

.bot-row:hover {
  background: #181c22;
}

.bot-row.is-selected {
  background: #1c222b;
  border-left: 2px solid #e8b45e;
}

.bot-table td {
  padding: 6px 10px;
  vertical-align: middle;
  white-space: nowrap;
}

/* 雙層版面專屬樣式 */
.bot-info-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-running { background: #65cba7; box-shadow: 0 0 5px rgba(101, 203, 167, 0.4); }
.dot-paused { background: #90969d; }

.bot-dual-text {
  display: flex;
  flex-direction: column;
}

.symbol-accent {
  color: #e5e8ec;
  font-weight: 700;
}

.tf-mini {
  background: #181c21;
  color: #90969d;
  padding: 0 3px;
  border-radius: 2px;
  border: 1px solid #282c31;
  margin: 0 2px;
}

.pos-dual-cell {
  display: flex;
  flex-direction: column;
}

.pos-top-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.qty-mono {
  font-size: 11.5px;
}

.chart-action-cell {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.btn-pause-compact {
  background: #181c21;
  border: 1px solid #282c31;
  color: #90969d;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 2px;
  cursor: pointer;
}
.btn-pause-compact:hover {
  color: #e5e8ec;
  border-color: #3b424b;
}

/* ★ 使用者定案：TradingView 幾何箭頭 */
.badge-tv { font-size: 10.5px; }
.badge-tv.is-long { color: #65cba7; }
.badge-tv.is-short { color: #ed7665; }
.badge-tv.is-idle { color: #90969d; }

/* 守護進度條 */
.guard-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 90px;
}
.meter-bar {
  position: relative;
  height: 4px;
  background: #20242a;
  border-radius: 2px;
  overflow: hidden;
}
.meter-fill { height: 100%; border-radius: 2px; }
.fill-warn { background: #e8b45e; }
.fill-danger { background: #ed7665; }
.warn-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(255, 255, 255, 0.3);
}

/* 原版單層專用樣式 */
.symbol-tag {
  font-weight: 700;
  font-family: monospace;
  margin-right: 4px;
}
.tf-tag {
  background: #181c21;
  color: #90969d;
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 2px;
  border: 1px solid #282c31;
}
.legs-badge {
  background: #1f242b;
  color: #e5e8ec;
  font-size: 10.5px;
  padding: 1px 5px;
  border-radius: 2px;
}
.signal-tag {
  background: #181c21;
  color: #90969d;
  padding: 1px 5px;
  border-radius: 2px;
  border: 1px solid #282c31;
}
.btn-pause {
  background: #181c21;
  border: 1px solid #282c31;
  color: #90969d;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 2px;
  cursor: pointer;
}
.btn-pause:hover { color: #e5e8ec; border-color: #3b424b; }

.text-gain { color: #65cba7 !important; }
.text-risk { color: #ed7665 !important; }
.text-muted { color: #90969d; }
.text-2xs { font-size: 10px; }
.mono { font-family: var(--default-mono-font-family, ui-monospace, monospace); }
.text-right { text-align: right; }
</style>
