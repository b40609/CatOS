<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { RiskState } from '@/contracts';
import { activeAdapter } from '@/adapters/mock-adapter';
import RiskGauge from '@/components/common/RiskGauge.vue';

const risk = ref<RiskState | null>(null);

function triggerKillSwitch() {
  alert('【模擬安全提示】\n已觸發手動緊急 Kill-Switch！\n• 委託標籤：41cb53c54d6dABDE\n• 動作：市價全平倉已發出\n• 狀態：日損硬熔斷鎖存已生效 (Latch: ARMED)，禁止任何增倉委託。');
}

onMounted(async () => {
  risk.value = await activeAdapter.fetchRiskState();
});
</script>

<template>
  <div class="risk-page">
    <!-- Teleport Actions to Unified Header -->
    <Teleport to="#header-page-actions">
      <div class="header-actions-group">
        <span class="badge badge-accent">標籤 41cb53c54d6dABDE</span>
        <button type="button" class="btn btn-sm btn-danger ml-2" @click="triggerKillSwitch">
          🛑 緊急 Kill-Switch
        </button>
      </div>
    </Teleport>

    <div class="risk-grid">
      <!-- Safety Gauge Panel -->
      <div class="grid-col">
        <RiskGauge :risk="risk" />
      </div>

      <!-- Invariant Policy Specifications Card -->
      <div class="card grid-col">
        <div class="card-header">
          <div class="card-title">風控邊界與不變量 (Invariants)</div>
        </div>
        <div class="card-body">
          <div class="policy-list">
            <div class="policy-item">
              <strong>帳戶有效槓桿上限</strong>
              <p>上限 3.00x。總曝險預算 = 槓桿上限 × 風控權益。事前檢查包含在途委託與 UNKNOWN 狀態。</p>
            </div>
            <div class="policy-item">
              <strong>單幣曝險預算占比</strong>
              <p>預設上限 50%。單幣上限 = 總曝險預算 × 單幣預算占比。被動超限僅禁止增加曝險，合法減倉始終允許。</p>
            </div>
            <div class="policy-item">
              <strong>日損雙階熔斷機制</strong>
              <p>以台北時間每日 00:00 初權益為固定分母。Soft (-10%) 停止增倉；Hard (-20%) 觸發市價清倉與 Kill-Switch。</p>
            </div>
            <div class="policy-item">
              <strong>鎖存與人工恢復政策</strong>
              <p>日損鎖存不隨跨日、重啟或行情反彈自動解除。必須確認有效風險原因消失後由人工手動 Re-arm。</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Lower Grid: Asset Exposure & Terminal Protection -->
    <div class="risk-lower-grid">
      <!-- Asset Exposure Progress -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">單幣曝險預算實時追蹤 (Per-Asset Exposure Cap 50%)</div>
          <span class="badge badge-sm badge-success font-mono">有效槓桿 1.85x / 上限 3.00x</span>
        </div>
        <div class="card-body">
          <div class="exposure-list">
            <!-- BTC -->
            <div class="exposure-item">
              <div class="exp-head">
                <span class="exp-symbol mono">BTC-USDT-SWAP</span>
                <span class="exp-nums mono tabular-nums">598.50 / 1,500.00 USDT (39.9%)</span>
              </div>
              <div class="exp-bar-wrap">
                <div class="exp-bar" style="width: 39.9%; background-color: var(--accent);"></div>
              </div>
              <div class="exp-sub text-2xs text-muted">
                <span>單幣預算上限 50.0% · 距安全上限仍有 901.50 USDT</span>
                <span class="badge badge-2xs badge-success">正常 SAFE</span>
              </div>
            </div>

            <!-- ETH -->
            <div class="exposure-item">
              <div class="exp-head">
                <span class="exp-symbol mono">ETH-USDT-SWAP</span>
                <span class="exp-nums mono tabular-nums">213.75 / 1,500.00 USDT (14.3%)</span>
              </div>
              <div class="exp-bar-wrap">
                <div class="exp-bar" style="width: 14.3%; background-color: #58a6ff;"></div>
              </div>
              <div class="exp-sub text-2xs text-muted">
                <span>單幣預算上限 50.0% · 距安全上限仍有 1,286.25 USDT</span>
                <span class="badge badge-2xs badge-success">正常 SAFE</span>
              </div>
            </div>

            <!-- SOL -->
            <div class="exposure-item">
              <div class="exp-head">
                <span class="exp-symbol mono">SOL-USDT-SWAP</span>
                <span class="exp-nums mono tabular-nums">0.00 / 1,500.00 USDT (0.0%)</span>
              </div>
              <div class="exp-bar-wrap">
                <div class="exp-bar" style="width: 0%; background-color: #a2adb9;"></div>
              </div>
              <div class="exp-sub text-2xs text-muted">
                <span>未開倉 · 預算額度全數可用</span>
                <span class="badge badge-2xs badge-neutral">閒置 IDLE</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- OKX Terminal Protection & Emergency Kill-Switch -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">OKX 交易所端保全與熔斷狀態 (Terminal Protection)</div>
          <span class="badge badge-sm badge-neutral">MARK 觸發</span>
        </div>
        <div class="card-body">
          <div class="terminal-audit-list">
            <div class="audit-row">
              <div class="audit-info">
                <strong>P6 災難整倉停損</strong>
                <p>OKX 伺服器端條件委託已部署，斷線時自動觸發市價平倉。</p>
              </div>
              <span class="badge badge-sm badge-success">已部署 ACTIVE</span>
            </div>

            <div class="audit-row">
              <div class="audit-info">
                <strong>保證金與撮合模式</strong>
                <p>嚴格限制為 USDT-M SWAP、Cross (全倉) + Net Mode (單向持倉)。</p>
              </div>
              <span class="badge badge-sm badge-accent">CROSS + NET</span>
            </div>

            <div class="audit-row">
              <div class="audit-info">
                <strong>日初權益基準分母</strong>
                <p>Asia/Taipei 00:00 自動切日，日初基準: 1,000.00 USDT (Decimal)。</p>
              </div>
              <span class="badge badge-sm badge-neutral tabular-nums">1,000.00 USDT</span>
            </div>

            <div class="audit-row highlight-kill">
              <div class="audit-info">
                <strong class="text-danger">緊急手動 Kill-Switch</strong>
                <p>立即發出市價全平倉委託，並將日損硬熔斷鎖存 (Latch: ARMED)。</p>
              </div>
              <button type="button" class="btn btn-sm btn-danger" @click="triggerKillSwitch">
                啟動熔斷清倉
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.risk-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
  overflow-y: auto;
}



.risk-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.policy-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.policy-item {
  padding: 10px;
  background: var(--bg-surface-elevated);
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-secondary);
}

.policy-item strong {
  font-size: var(--text-xs);
  color: var(--accent);
}

.policy-item p {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 4px;
  line-height: 1.4;
}

@media (max-width: 1024px) {
  .risk-grid,
  .risk-lower-grid {
    grid-template-columns: 1fr;
  }
}

/* Lower Risk Grid */
.risk-lower-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.exposure-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.exposure-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.exp-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.exp-symbol {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-primary);
}

.exp-nums {
  font-size: var(--text-2xs);
  color: var(--text-secondary);
}

.exp-bar-wrap {
  width: 100%;
  height: 6px;
  background-color: var(--bg-base);
  border-radius: 3px;
  overflow: hidden;
  border: 1px solid var(--border-secondary);
}

.exp-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.exp-sub {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.badge-2xs {
  font-size: 9px;
  padding: 1px 4px;
}

/* Terminal Audit List */
.terminal-audit-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.audit-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xs);
}

.audit-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.audit-info strong {
  font-size: var(--text-xs);
  color: var(--text-primary);
}

.audit-info p {
  font-size: 10.5px;
  color: var(--text-secondary);
  line-height: 1.3;
}

.highlight-kill {
  border-color: rgba(248, 81, 73, 0.4);
  background: rgba(248, 81, 73, 0.08);
}
</style>
