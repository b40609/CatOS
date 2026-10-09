<script setup lang="ts">
import { ref, computed } from 'vue';

export interface PositionLeg {
  id: string;
  botId: string;
  botName: string;
  side: 'long' | 'short';
  notional: number;
  isPaused?: boolean;
}

export interface SymbolExposure {
  symbol: string;
  base: string;
  chg: number;
  mark: number;
  legs: PositionLeg[];
  long: number;
  short: number;
  net: number;
}

const props = withDefaults(
  defineProps<{
    showHeader?: boolean;
    equity?: number;
    concentrationLimitPct?: number;
  }>(),
  {
    showHeader: true,
    equity: 40272.50,
    concentrationLimitPct: 35
  }
);

const emit = defineEmits<{
  (e: 'selectBot', botId: string): void;
  (e: 'focusBot', botId: string | null): void;
}>();

const focusedBotId = ref<string | null>(null);

const symbols = ref<SymbolExposure[]>([
  {
    symbol: 'BTCUSDT',
    base: 'BTC',
    chg: 1.42,
    mark: 62140.5,
    legs: [
      { id: 'l1', botId: 'tabby-01', botName: 'Tabby', side: 'long', notional: 7456.86, isPaused: false },
      { id: 'l2', botId: 'shiro-04', botName: 'Shiro', side: 'long', notional: 3107.03, isPaused: true }
    ],
    long: 10563.89,
    short: 0,
    net: 10563.89
  },
  {
    symbol: 'ETHUSDT',
    base: 'ETH',
    chg: -0.85,
    mark: 2450.2,
    legs: [
      { id: 'l3', botId: 'calico-02', botName: 'Calico', side: 'long', notional: 5880.48, isPaused: false },
      { id: 'l4', botId: 'shiro-04', botName: 'Shiro', side: 'short', notional: 3185.26, isPaused: true }
    ],
    long: 5880.48,
    short: 3185.26,
    net: 2695.22
  },
  {
    symbol: 'SOLUSDT',
    base: 'SOL',
    chg: 3.10,
    mark: 152.8,
    legs: [
      { id: 'l5', botId: 'mochi-03', botName: 'Mochi', side: 'long', notional: 2750.40, isPaused: false }
    ],
    long: 2750.40,
    short: 0,
    net: 2750.40
  }
]);

const SCALE_PCT = 50;

const totalGross = computed(() => {
  return symbols.value.reduce((acc, s) => acc + s.long + s.short, 0);
});

const totalNet = computed(() => {
  return symbols.value.reduce((acc, s) => acc + s.net, 0);
});

const availableCash = computed(() => {
  return 26390;
});

const currentLeverage = computed(() => {
  return (Math.abs(totalNet.value) / props.equity).toFixed(2);
});

const totalLong = computed(() => {
  return symbols.value.reduce((acc, s) => acc + s.long, 0);
});

const totalShort = computed(() => {
  return symbols.value.reduce((acc, s) => acc + s.short, 0);
});

const grossLeverage = computed(() => {
  return (totalGross.value / props.equity).toFixed(2);
});

function getPct(usd: number) {
  return (usd / props.equity) * 100;
}

function getSegmentWidth(notional: number) {
  const p = getPct(notional);
  const clamped = Math.min(p, SCALE_PCT);
  return `${((clamped / SCALE_PCT) * 100).toFixed(1)}%`;
}

function getPointerLeft(netPct: number) {
  const clamped = Math.max(-SCALE_PCT, Math.min(SCALE_PCT, netPct));
  return `${(50 + (clamped / SCALE_PCT) * 50).toFixed(1)}%`;
}

function handleBotHover(botId: string | null) {
  focusedBotId.value = botId;
  emit('focusBot', botId);
}

function handleBotClick(botId: string) {
  emit('selectBot', botId);
}
</script>

<template>
  <div class="exposure-panel-root">
    <!-- Header (if shown) -->
    <div v-if="showHeader" class="panel-header">
      <div class="header-left">
        <span class="scope-tag">帳戶</span>
        <h3 class="panel-title">曝險 · 依標的</h3>
        <span class="panel-meta mono">總 {{ totalGross.toLocaleString('en-US', { maximumFractionDigits: 0 }) }} USDT · {{ grossLeverage }}x</span>
      </div>
      <div class="header-right font-mono text-2xs text-muted">
        集中度上限 ±{{ concentrationLimitPct }}%
      </div>
    </div>

    <!-- Scale Ruler & List -->
    <div class="panel-body">
      <!-- 標尺刻度 -->
      <div class="ruler-row mono text-2xs text-muted">
        <span class="col-symbol"></span>
        <div class="ruler-bar-labels">
          <span class="label-short">← 空頭</span>
          <span class="label-center">±{{ SCALE_PCT }}% 權益</span>
          <span class="label-long">多頭 →</span>
        </div>
        <span class="col-net-label text-right">淨額 · 佔比</span>
      </div>

      <!-- 標的列表 -->
      <div class="symbol-list">
        <div v-for="s in symbols" :key="s.symbol" class="symbol-row">
          <!-- 1. 標的與 24h 漲跌 -->
          <div class="symbol-meta">
            <span class="symbol-base mono">{{ s.base }}</span>
            <span
              class="symbol-chg mono text-2xs"
              :class="s.chg >= 0 ? 'text-green' : 'text-red'"
            >
              {{ s.chg >= 0 ? '+' : '' }}{{ s.chg.toFixed(2) }}%
            </span>
          </div>

          <!-- 2. 雙向長條尺規 -->
          <div class="exposure-bar-wrap">
            <!-- 空頭區 (向左) -->
            <div class="bar-half bar-shorts">
              <div
                v-for="leg in s.legs.filter(l => l.side === 'short')"
                :key="leg.id"
                class="segment-block is-short"
                :class="{
                  'is-paused': leg.isPaused,
                  'is-focused': focusedBotId === leg.botId
                }"
                :style="{ width: getSegmentWidth(leg.notional) }"
                :title="`${leg.botName} · 空 ${leg.notional.toLocaleString('en-US', { maximumFractionDigits: 0 })} USDT`"
                @mouseenter="handleBotHover(leg.botId)"
                @mouseleave="handleBotHover(null)"
                @click="handleBotClick(leg.botId)"
              >
                <span class="segment-label">{{ leg.botName }}</span>
              </div>
            </div>

            <!-- 多頭區 (向右) -->
            <div class="bar-half bar-longs">
              <div
                v-for="leg in s.legs.filter(l => l.side === 'long')"
                :key="leg.id"
                class="segment-block is-long"
                :class="{
                  'is-paused': leg.isPaused,
                  'is-focused': focusedBotId === leg.botId
                }"
                :style="{ width: getSegmentWidth(leg.notional) }"
                :title="`${leg.botName} · 多 ${leg.notional.toLocaleString('en-US', { maximumFractionDigits: 0 })} USDT`"
                @mouseenter="handleBotHover(leg.botId)"
                @mouseleave="handleBotHover(null)"
                @click="handleBotClick(leg.botId)"
              >
                <span class="segment-label">{{ leg.botName }}</span>
              </div>
            </div>

            <!-- 中央 0 基準線 -->
            <span class="center-axis"></span>

            <!-- ±集中度上限警戒線 (紅線) -->
            <span
              class="limit-line is-short-limit"
              :style="{ left: `${50 - (concentrationLimitPct / SCALE_PCT) * 50}%` }"
              title="空頭集中度上限"
            ></span>
            <span
              class="limit-line is-long-limit"
              :style="{ left: `${50 + (concentrationLimitPct / SCALE_PCT) * 50}%` }"
              title="多頭集中度上限"
            ></span>

            <!-- 淨曝險三角指針 -->
            <span
              v-if="s.legs.length > 0"
              class="net-pointer"
              :style="{ left: getPointerLeft(getPct(s.net)) }"
              :title="`淨曝險 ${getPct(s.net).toFixed(1)}%`"
            ></span>
          </div>

          <!-- 3. 淨額與佔比數值 -->
          <div class="symbol-values mono text-right">
            <span class="net-usd text-xs">
              {{ s.net >= 0 ? '+' : '' }}{{ Math.round(s.net).toLocaleString('en-US') }}
            </span>
            <span
              class="net-pct text-2xs"
              :class="Math.abs(getPct(s.net)) >= concentrationLimitPct * 0.85 ? 'text-red font-bold' : 'text-muted'"
            >
              {{ getPct(s.net).toFixed(1) }}%
            </span>
          </div>
        </div>
      </div>

      <!-- 底部彙整清單 (專門完整呈現多空彙整、淨曝險與可用現金) -->
      <div class="exposure-footer">
        <div class="summary-grid mono text-2xs">
          <div class="summary-item">
            <span class="lbl text-muted">多方:</span>
            <span class="val text-green font-medium">+{{ Math.round(totalLong).toLocaleString('en-US') }}</span>
          </div>
          <div class="summary-item">
            <span class="lbl text-muted">空方:</span>
            <span class="val text-red font-medium">-{{ Math.round(totalShort).toLocaleString('en-US') }}</span>
          </div>
          <div class="summary-item">
            <span class="lbl text-muted">淨曝險:</span>
            <span class="val font-medium" :class="totalNet >= 0 ? 'text-green' : 'text-red'">
              {{ totalNet >= 0 ? '+' : '' }}{{ Math.round(totalNet).toLocaleString('en-US') }}
              <span class="pct-hint text-3xs text-muted">({{ ((totalNet / props.equity) * 100).toFixed(1) }}%)</span>
            </span>
          </div>
          <div class="summary-item">
            <span class="lbl text-muted">可用現金:</span>
            <span class="val text-white font-medium">
              {{ availableCash.toLocaleString('en-US') }}
              <span class="pct-hint text-3xs text-muted">({{ currentLeverage }}x)</span>
            </span>
          </div>
        </div>

        <!-- 圖例說明 -->
        <div class="legend-row text-3xs text-muted">
          <span class="legend-item">
            <span class="legend-box is-long-box"></span> 各機器人多方持倉
          </span>
          <span class="legend-item">
            <span class="legend-box is-short-box"></span> 空方持倉
          </span>
          <span class="legend-item">
            <span class="legend-line is-limit-line"></span> 上限 ±{{ concentrationLimitPct }}%
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.exposure-panel-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: transparent;
  color: #e5e8ec;
  font-family: inherit;
  overflow: hidden;
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
  align-items: center;
  gap: 8px;
}

.scope-tag {
  background: #e8b45e;
  color: #0c0f12;
  font-size: 9.5px;
  font-weight: 700;
  padding: 1px 5px;
  border-radius: 2px;
  text-transform: uppercase;
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
}

.panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 10px 12px;
  gap: 10px;
  overflow-y: auto;
}

.ruler-row {
  display: grid;
  grid-template-columns: 52px 1fr 88px;
  align-items: center;
  gap: 10px;
}

.ruler-bar-labels {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
}

.symbol-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.symbol-row {
  display: grid;
  grid-template-columns: 52px 1fr 88px;
  align-items: center;
  gap: 10px;
}

.symbol-meta {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.symbol-base {
  font-size: 12px;
  font-weight: 600;
  color: #e5e8ec;
}

.exposure-bar-wrap {
  position: relative;
  height: 24px;
  background: #181c21;
  border-radius: 3px;
  border: 1px solid #282c31;
  overflow: visible;
}

.bar-half {
  position: absolute;
  top: 0;
  bottom: 0;
  display: flex;
  gap: 1px;
}

.bar-shorts {
  left: 0;
  width: 50%;
  flex-direction: row-reverse;
}

.bar-longs {
  left: 50%;
  width: 50%;
  flex-direction: row;
}

.segment-block {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
  overflow: hidden;
}

.segment-block.is-long {
  background: #65cba7;
  color: #0c0f12;
}

.segment-block.is-long:hover,
.segment-block.is-long.is-focused {
  background: #64d6af;
  box-shadow: 0 0 6px rgba(101, 203, 167, 0.6);
}

.segment-block.is-short {
  background: #ed7665;
  color: #0c0f12;
}

.segment-block.is-short:hover,
.segment-block.is-short.is-focused {
  background: #fa8469;
  box-shadow: 0 0 6px rgba(237, 118, 101, 0.6);
}

.segment-block.is-paused {
  background-image: repeating-linear-gradient(135deg, transparent 0 3px, rgba(0, 0, 0, 0.4) 3px 6px);
}

.segment-label {
  font-size: 9.5px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding: 0 3px;
}

.center-axis {
  position: absolute;
  top: -3px;
  bottom: -3px;
  left: 50%;
  width: 1px;
  background: #282c31;
  pointer-events: none;
  z-index: 2;
}

.limit-line {
  position: absolute;
  top: -3px;
  bottom: -3px;
  width: 1px;
  background: #ed7665;
  pointer-events: none;
  z-index: 2;
}

.net-pointer {
  position: absolute;
  bottom: -4px;
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-bottom: 5px solid #e8b45e;
  transform: translateX(-50%);
  pointer-events: none;
  z-index: 3;
}

.symbol-values {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.net-usd {
  color: #e5e8ec;
  font-weight: 500;
}

.exposure-footer {
  margin-top: auto;
  border-top: 1px solid #282c31;
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-row {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 9.5px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.legend-box {
  width: 8px;
  height: 8px;
  border-radius: 1px;
}

.is-long-box {
  background: #65cba7;
}

.is-short-box {
  background: #ed7665;
}

.legend-line {
  width: 1px;
  height: 8px;
  background: #ed7665;
}

.text-muted {
  color: #90969d;
}

.text-green {
  color: #65cba7 !important;
}

.text-red {
  color: #ed7665 !important;
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
