<script setup lang="ts">
import { ref } from 'vue';

interface RuleItem {
  id: string;
  name: string;
  desc: string;
  val: number;
  unit: string;
  enabled: boolean;
  min: number;
  max: number;
}

const rules = ref<RuleItem[]>([
  { id: '1', name: '單一標的曝險上限', desc: '任一標的名目價值占淨值比重', val: 25, unit: '%', enabled: true, min: 10, max: 50 },
  { id: '2', name: '組合最大槓桿', desc: '總名目 / 淨值', val: 3, unit: 'x', enabled: true, min: 1, max: 10 },
  { id: '3', name: '日內停損', desc: '當日虧損達門檻即全平倉', val: 4, unit: '%', enabled: true, min: 1, max: 10 },
  { id: '4', name: '回撤熔斷', desc: '自高點回撤達門檻暫停所有機器人', val: 12, unit: '%', enabled: false, min: 5, max: 25 },
  { id: '5', name: '下單頻率上限', desc: '每分鐘最大委託數', val: 120, unit: '/min', enabled: true, min: 30, max: 300 }
]);

interface AlertItem {
  time: string;
  level: 'ERROR' | 'WARN' | 'INFO';
  msg: string;
}

const alerts = ref<AlertItem[]>([
  { time: '09:41:22', level: 'ERROR', msg: 'CAT-05 交易所連線逾時，已切換備援節點' },
  { time: '09:12:07', level: 'WARN', msg: 'SOL-PERP 單一曝險達 23.4%，接近 25% 上限' },
  { time: '08:55:44', level: 'WARN', msg: '組合槓桿 2.81x，過去 30 分鐘上升 0.4x' },
  { time: '08:30:00', level: 'INFO', msg: '日內風控參數已套用至 6 個機器人' },
  { time: '07:58:13', level: 'INFO', msg: '夜間風險快照完成，VaR(95%) 更新' }
]);
</script>

<template>
  <div class="relaxed-risk-view">
    <!-- Top Header Notice -->
    <div class="risk-top-header">
      <span class="header-sub-text">永續合約曝險、槓桿熔斷與鏈上風險追蹤，模擬數據</span>
    </div>

    <!-- 4 Half-Circle Gauge Cards -->
    <div class="gauges-grid">
      <!-- 1. Total Exposure -->
      <div class="gauge-card">
        <span class="gauge-label">TOTAL EXPOSURE</span>
        <div class="half-gauge-box">
          <svg viewBox="0 0 120 70" class="gauge-svg">
            <path d="M 15 65 A 45 45 0 0 1 105 65" fill="none" stroke="var(--os-border-subtle)" stroke-width="12" stroke-linecap="round"/>
            <path d="M 15 65 A 45 45 0 0 1 75 22" fill="none" stroke="var(--os-up)" stroke-width="12" stroke-linecap="round"/>
          </svg>
          <div class="gauge-center-text">
            <span class="gauge-value num">18.60M</span>
          </div>
        </div>
        <span class="gauge-limit num">限額 30M</span>
      </div>

      <!-- 2. Leverage -->
      <div class="gauge-card">
        <span class="gauge-label">LEVERAGE</span>
        <div class="half-gauge-box">
          <svg viewBox="0 0 120 70" class="gauge-svg">
            <path d="M 15 65 A 45 45 0 0 1 105 65" fill="none" stroke="var(--os-border-subtle)" stroke-width="12" stroke-linecap="round"/>
            <path d="M 15 65 A 45 45 0 0 1 95 40" fill="none" stroke="var(--os-up)" stroke-width="12" stroke-linecap="round"/>
          </svg>
          <div class="gauge-center-text">
            <span class="gauge-value num">2.85x</span>
          </div>
        </div>
        <span class="gauge-limit num">限額 3x</span>
      </div>

      <!-- 3. VaR 95% -->
      <div class="gauge-card">
        <span class="gauge-label">VAR 95% (1D)</span>
        <div class="half-gauge-box">
          <svg viewBox="0 0 120 70" class="gauge-svg">
            <path d="M 15 65 A 45 45 0 0 1 105 65" fill="none" stroke="var(--os-border-subtle)" stroke-width="12" stroke-linecap="round"/>
            <path d="M 15 65 A 45 45 0 0 1 60 20" fill="none" stroke="var(--os-up)" stroke-width="12" stroke-linecap="round"/>
          </svg>
          <div class="gauge-center-text">
            <span class="gauge-value num">410.95k</span>
          </div>
        </div>
        <span class="gauge-limit num">限額 800k</span>
      </div>

      <!-- 4. Concentration -->
      <div class="gauge-card">
        <span class="gauge-label">CONCENTRATION</span>
        <div class="half-gauge-box">
          <svg viewBox="0 0 120 70" class="gauge-svg">
            <path d="M 15 65 A 45 45 0 0 1 105 65" fill="none" stroke="var(--os-border-subtle)" stroke-width="12" stroke-linecap="round"/>
            <path d="M 15 65 A 45 45 0 0 1 90 35" fill="none" stroke="var(--os-up)" stroke-width="12" stroke-linecap="round"/>
          </svg>
          <div class="gauge-center-text">
            <span class="gauge-value num">23.62%</span>
          </div>
        </div>
        <span class="gauge-limit num">限額 25%</span>
      </div>
    </div>

    <!-- Middle 3 Metrics -->
    <div class="market-metrics-grid">
      <div class="metric-block">
        <p class="m-label">FUNDING RATE · 資金費率</p>
        <p class="m-val num text-up">+0.0088%</p>
        <p class="m-sub">永續合約 · 8 小時加權平均</p>
      </div>

      <div class="metric-block">
        <p class="m-label">OPEN INTEREST · 未平倉量</p>
        <p class="m-val num">20.90B</p>
        <p class="m-sub">BTC / ETH / SOL / DOGE 合計</p>
      </div>

      <div class="metric-block">
        <p class="m-label">LIQUIDATIONS · 爆倉量</p>
        <p class="m-val num text-down">149.5M</p>
        <p class="m-sub">24H · 多單 97.0M / 空單 52.5M</p>
      </div>
    </div>

    <!-- Bottom Row: Rules (Left) & Alert Timeline (Right) -->
    <div class="rules-alerts-grid">
      <!-- Left: Risk Rules with real sliders & toggle switches -->
      <div class="rules-card">
        <h3 class="box-title">risk rules · 風控規則</h3>

        <div class="rules-list">
          <div v-for="r in rules" :key="r.id" class="rule-row">
            <div class="rule-info-col">
              <div class="rule-head-line">
                <span class="rule-name">{{ r.name }}</span>
                <span class="rule-desc">{{ r.desc }}</span>
              </div>
              <input
                type="range"
                v-model.number="r.val"
                :min="r.min"
                :max="r.max"
                :disabled="!r.enabled"
                class="rule-slider"
              />
            </div>

            <div class="rule-ctrl-col">
              <span class="rule-val-badge num">{{ r.val }}{{ r.unit }}</span>
              <label class="switch-toggle">
                <input type="checkbox" v-model="r.enabled" />
                <span class="slider-round"></span>
              </label>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Alert Timeline -->
      <div class="timeline-card">
        <div class="timeline-header">
          <h3 class="box-title">alert timeline · 警報時間軸</h3>
          <span class="today-tag num">TODAY</span>
        </div>

        <ul class="timeline-list">
          <li v-for="(al, idx) in alerts" :key="idx" class="timeline-item">
            <div class="time-level-row">
              <span class="dot-alarm" :class="`dot-${al.level.toLowerCase()}`"></span>
              <span class="alert-time num">{{ al.time }}</span>
              <span class="alert-tag num" :class="`tag-${al.level.toLowerCase()}`">{{ al.level }}</span>
            </div>
            <p class="alert-msg">{{ al.msg }}</p>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.relaxed-risk-view {
  display: flex;
  flex-direction: column;
  gap: var(--os-space-gap);
  padding: 1.25rem 1.5rem;
  max-width: 1720px;
  margin: 0 auto;
  width: 100%;
}

.risk-top-header {
  margin-bottom: 0.15rem;
}

.header-sub-text {
  font-size: 0.72rem;
  color: var(--os-text-muted);
}

.gauges-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--os-space-gap);
}

.gauge-card {
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: var(--os-card-radius);
  padding: 1.15rem 1rem;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.gauge-label {
  font-size: 0.68rem;
  color: var(--os-text-muted);
  font-weight: 500;
  letter-spacing: 0.04em;
}

.half-gauge-box {
  position: relative;
  width: 140px;
  height: 80px;
  margin-top: 0.5rem;
}

.gauge-svg {
  width: 100%;
  height: 100%;
}

.gauge-center-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 5px;
}

.gauge-value {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--os-text-primary);
}

.gauge-limit {
  font-size: 0.68rem;
  color: var(--os-text-muted);
  margin-top: 0.4rem;
}

.market-metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: var(--os-card-radius);
  overflow: hidden;
}

.metric-block {
  padding: 1rem 1.35rem;
  border-right: 1px solid var(--os-border-subtle);
}

.metric-block:last-child {
  border-right: none;
}

.m-label {
  font-size: 0.68rem;
  color: var(--os-text-muted);
  font-weight: 500;
}

.m-val {
  font-size: 1.35rem;
  font-weight: 600;
  color: var(--os-text-primary);
  margin-top: 0.35rem;
}

.m-sub {
  font-size: 0.68rem;
  color: var(--os-text-muted);
  margin-top: 0.25rem;
}

.rules-alerts-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: var(--os-space-gap);
}

.rules-card, .timeline-card {
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: var(--os-card-radius);
  padding: 1.15rem 1.35rem;
}

.box-title {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--os-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 1rem;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 1.15rem;
}

.rule-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
}

.rule-info-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.rule-head-line {
  display: flex;
  align-items: baseline;
  gap: 0.65rem;
}

.rule-name {
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--os-text-primary);
}

.rule-desc {
  font-size: 0.68rem;
  color: var(--os-text-muted);
}

.rule-slider {
  width: 100%;
  accent-color: var(--os-up);
  cursor: pointer;
}

.rule-ctrl-col {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.rule-val-badge {
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--os-text-primary);
  min-width: 42px;
  text-align: right;
}

/* Switch Toggle Styling */
.switch-toggle {
  position: relative;
  display: inline-block;
  width: 34px;
  height: 18px;
}

.switch-toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider-round {
  position: absolute;
  cursor: pointer;
  inset: 0;
  background-color: var(--os-bg-surface);
  border: 1px solid var(--os-border);
  transition: .2s;
  border-radius: 20px;
}

.slider-round:before {
  position: absolute;
  content: "";
  height: 12px;
  width: 12px;
  left: 2px;
  bottom: 2px;
  background-color: var(--os-text-muted);
  transition: .2s;
  border-radius: 50%;
}

input:checked + .slider-round {
  background-color: var(--os-up);
  border-color: var(--os-up);
}

input:checked + .slider-round:before {
  transform: translateX(16px);
  background-color: #0c0f12;
}

.timeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.today-tag {
  font-size: 0.65rem;
  color: var(--os-text-muted);
  letter-spacing: 0.05em;
}

.timeline-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.timeline-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  border-bottom: 1px solid var(--os-border-subtle);
  padding-bottom: 0.75rem;
}

.timeline-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.time-level-row {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.7rem;
}

.dot-alarm {
  width: 5px;
  height: 5px;
  border-radius: 50%;
}

.dot-error { background: var(--os-down); }
.dot-warn { background: var(--os-warn); }
.dot-info { background: var(--os-info); }

.alert-time {
  color: var(--os-text-muted);
}

.alert-tag {
  font-size: 0.62rem;
  font-weight: 600;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  border: 1px solid;
}

.tag-error {
  color: var(--os-down);
  border-color: var(--os-down-border);
  background: var(--os-down-bg);
}

.tag-warn {
  color: var(--os-warn);
  border-color: rgba(251, 191, 36, 0.3);
  background: var(--os-warn-bg);
}

.tag-info {
  color: var(--os-info);
  border-color: rgba(96, 165, 250, 0.3);
  background: rgba(96, 165, 250, 0.1);
}

.alert-msg {
  font-size: 0.74rem;
  color: var(--os-text-secondary);
  line-height: 1.4;
  padding-left: 0.9rem;
}

.text-up { color: var(--os-up); }
.text-down { color: var(--os-down); }

@media (max-width: 1024px) {
  .gauges-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .market-metrics-grid {
    grid-template-columns: 1fr;
  }
  .rules-alerts-grid {
    grid-template-columns: 1fr;
  }
}
</style>
