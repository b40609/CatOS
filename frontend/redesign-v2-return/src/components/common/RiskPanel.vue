<script setup lang="ts">
import { ref, computed } from 'vue';

export interface RiskLimitRow {
  key: string;
  label: string;
  value: string;
  limit: string;
  ratio: number; // 0.0 ~ 1.0+
}

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
  (e: 'killSwitch'): void;
}>();

const confirmingKillSwitch = ref(false);
let confirmTimer: any = null;

function handleKillSwitchClick() {
  if (!confirmingKillSwitch.value) {
    confirmingKillSwitch.value = true;
    confirmTimer = setTimeout(() => {
      confirmingKillSwitch.value = false;
    }, 4000);
  } else {
    clearTimeout(confirmTimer);
    confirmingKillSwitch.value = false;
    emit('killSwitch');
  }
}

const riskRows = ref<RiskLimitRow[]>([
  {
    key: 'daily',
    label: '今日虧損水位',
    value: '0 USDT (獲利中)',
    limit: '4,000 USDT',
    ratio: 0 / 4000
  },
  {
    key: 'dd',
    label: '帳戶回撤水位',
    value: '-0.85%',
    limit: '-10.0%',
    ratio: 0.85 / 10.0
  },
  {
    key: 'lev',
    label: '總槓桿',
    value: '0.71x',
    limit: '1.50x',
    ratio: 0.71 / 1.50 // 0.473
  },
  {
    key: 'conc',
    label: '單一標的 · BTC',
    value: '26.2%',
    limit: '40.0%',
    ratio: 26.2 / 40.0 // 0.655
  }
]);

const nearestBot = ref({
  id: 'tabby-01',
  name: 'Tabby',
  ddNow: '-4.65%',
  stopline: '-8.0%',
  ratio: 4.65 / 8.0 // 0.58
});

const breachesCount = computed(() => {
  return riskRows.value.filter(r => r.ratio >= 1).length;
});

function getMeterColor(ratio: number) {
  if (ratio >= 0.85) return '#ed7665';
  if (ratio >= 0.6) return '#e8b45e';
  return '#90969d';
}
</script>

<template>
  <div class="risk-panel-root">
    <!-- Header -->
    <div v-if="showHeader" class="panel-header">
      <div class="header-left">
        <span class="scope-tag">帳戶</span>
        <h3 class="panel-title">風控限額</h3>
        <span class="panel-meta mono">
          {{ breachesCount > 0 ? `${breachesCount} 項超限` : `${riskRows.length}/${riskRows.length} 在限內` }}
        </span>
      </div>
    </div>

    <!-- Rows List -->
    <div class="panel-body">
      <ul class="risk-list">
        <li v-for="r in riskRows" :key="r.key" class="risk-item">
          <div class="risk-item-top">
            <span class="risk-label">{{ r.label }}</span>
            <div class="risk-values mono">
              <span
                class="current-val font-semibold"
                :class="{
                  'text-red': r.ratio >= 0.85,
                  'text-amber': r.ratio >= 0.6 && r.ratio < 0.85
                }"
              >
                {{ r.value }}
              </span>
              <span class="limit-val text-muted">/ {{ r.limit }}</span>
            </div>
          </div>

          <!-- Meter Progress Bar -->
          <div class="meter-track">
            <div
              class="meter-fill"
              :style="{
                width: `${Math.min(100, Math.round(r.ratio * 100))}%`,
                backgroundColor: getMeterColor(r.ratio)
              }"
            ></div>
          </div>
        </li>

        <!-- Nearest Stopline Bot -->
        <li v-if="nearestBot" class="risk-item is-nearest">
          <div class="risk-item-top">
            <span class="risk-label">
              最接近停止線 ·
              <button
                type="button"
                class="bot-name-btn"
                @click="emit('selectBot', nearestBot.id)"
              >
                {{ nearestBot.name }}
              </button>
            </span>
            <div class="risk-values mono">
              <span
                class="current-val font-semibold"
                :class="nearestBot.ratio >= 0.85 ? 'text-red' : (nearestBot.ratio >= 0.6 ? 'text-amber' : '')"
              >
                {{ nearestBot.ddNow }}
              </span>
              <span class="limit-val text-muted">/ {{ nearestBot.stopline }}</span>
            </div>
          </div>

          <!-- Meter Progress Bar -->
          <div class="meter-track">
            <div
              class="meter-fill"
              :style="{
                width: `${Math.min(100, Math.round(nearestBot.ratio * 100))}%`,
                backgroundColor: getMeterColor(nearestBot.ratio)
              }"
            ></div>
          </div>
        </li>
      </ul>

      <!-- Kill Switch Button (V0 Emergency Action) -->
      <div class="risk-footer">
        <button
          type="button"
          class="btn-kill-switch"
          :class="{ 'is-confirming': confirmingKillSwitch }"
          @click="handleKillSwitchClick"
        >
          <span class="btn-icon">🛑</span>
          <span class="btn-text">
            {{ confirmingKillSwitch ? '再次點擊確認停止' : '暫停所有機器人' }}
          </span>
        </button>
        <span class="kill-hint text-3xs text-muted">
          {{ confirmingKillSwitch ? '4 秒內無確認將自動取消' : '緊急通道 · 保留現有倉位並終止委託' }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.risk-panel-root {
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
  padding: 8px 12px;
  gap: 12px;
  overflow-y: auto;
}

.risk-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.risk-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 7px 0;
  border-bottom: 1px solid #282c31;
}

.risk-item:last-child {
  border-bottom: none;
}

.risk-item-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.risk-label {
  font-size: 12px;
  color: #e5e8ec;
}

.bot-name-btn {
  background: none;
  border: none;
  color: #e8b45e;
  text-decoration: underline;
  text-decoration-color: rgba(232, 180, 94, 0.4);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.bot-name-btn:hover {
  text-decoration-color: #e8b45e;
}

.risk-values {
  font-size: 11px;
}

.current-val {
  margin-right: 4px;
}

.meter-track {
  width: 100%;
  height: 4px;
  background: #181c21;
  border: 1px solid #282c31;
  border-radius: 2px;
  overflow: hidden;
}

.meter-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease, background-color 0.2s ease;
}

.risk-footer {
  margin-top: auto;
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.btn-kill-switch {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 12px;
  background: rgba(237, 118, 101, 0.12);
  border: 1px solid rgba(237, 118, 101, 0.35);
  border-radius: 4px;
  color: #ed7665;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-kill-switch:hover {
  background: rgba(237, 118, 101, 0.22);
  border-color: rgba(237, 118, 101, 0.6);
}

.btn-kill-switch.is-confirming {
  background: #ed7665;
  color: #0c0f12;
  border-color: #ed7665;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.8; }
}

.kill-hint {
  text-align: center;
}

.text-muted {
  color: #90969d;
}

.text-red {
  color: #ed7665 !important;
}

.text-amber {
  color: #e8b45e !important;
}

.text-3xs {
  font-size: 9.5px;
}

.mono {
  font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;
}
</style>
