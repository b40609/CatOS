<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { activeAdapter } from '@/adapters/mock-adapter';
import type { YaoziAlert } from '@/adapters/types';

const alerts = ref<YaoziAlert[]>([]);

onMounted(async () => {
  alerts.value = await activeAdapter.fetchYaoziAlerts();
});
</script>

<template>
  <div class="market-intel-page">
    <!-- Teleport Actions to Unified Header -->
    <Teleport to="#header-page-actions">
      <div class="header-actions-group">
        <span class="badge badge-accent">DEV · 獨立情報源</span>
      </div>
    </Teleport>

    <div class="banner banner-info">
      <span>提示：市場情報為獨立模組，整合至同一 localhost 分頁交付，切換頁面不控制策略生命週期。</span>
    </div>

    <div class="intel-grid">
      <div v-for="a in alerts" :key="a.id" class="card intel-card">
        <div class="card-header">
          <div class="card-title text-warning">{{ a.title }}</div>
          <span class="badge badge-sm badge-neutral tabular-nums">{{ a.time }}</span>
        </div>
        <div class="card-body">
          <p class="intel-text">{{ a.summary }}</p>
          <div class="intel-footer">
            <span class="badge badge-sm badge-info">{{ a.tag }}</span>
            <span class="badge badge-sm badge-neutral">{{ a.status }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Secondary Intelligence Grid -->
    <div class="intel-lower-grid">
      <!-- Funding Rate Arbitrage Monitor -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">資金費率偏離與套利監測 (Funding Rate Matrix)</div>
          <span class="badge badge-sm badge-accent">8H 結算</span>
        </div>
        <div class="card-body p-0">
          <table class="data-table">
            <thead>
              <tr>
                <th>標的合約</th>
                <th>OKX 費率</th>
                <th>Binance 費率</th>
                <th>偏離基差</th>
                <th>年化 APR</th>
                <th>訊號狀態</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="mono font-bold">BTC-USDT</td>
                <td class="mono tabular-nums text-success">+0.0100%</td>
                <td class="mono tabular-nums text-success">+0.0125%</td>
                <td class="mono tabular-nums text-muted">-0.0025%</td>
                <td class="mono tabular-nums">10.95%</td>
                <td><span class="badge badge-sm badge-neutral">正常</span></td>
              </tr>
              <tr>
                <td class="mono font-bold">ETH-USDT</td>
                <td class="mono tabular-nums text-danger font-bold">+0.0350%</td>
                <td class="mono tabular-nums text-success">+0.0180%</td>
                <td class="mono tabular-nums text-danger font-bold">+0.0170%</td>
                <td class="mono tabular-nums text-danger font-bold">38.32%</td>
                <td><span class="badge badge-sm badge-warning">多頭擁擠預警</span></td>
              </tr>
              <tr>
                <td class="mono font-bold">SOL-USDT</td>
                <td class="mono tabular-nums text-accent">-0.0050%</td>
                <td class="mono tabular-nums text-success">+0.0020%</td>
                <td class="mono tabular-nums text-accent">-0.0070%</td>
                <td class="mono tabular-nums">-5.47%</td>
                <td><span class="badge badge-sm badge-info">空頭貼水</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Whale Transfers Feed -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">鏈上巨鯨異動即時流 (Whale Activity Feed)</div>
          <span class="badge badge-sm badge-neutral">門檻 > $10M</span>
        </div>
        <div class="card-body p-0">
          <div class="whale-feed-list">
            <div class="whale-feed-item">
              <span class="whale-time mono tabular-nums text-muted text-2xs">10:45:12</span>
              <div class="whale-main">
                <div class="whale-title">
                  <span class="whale-amount font-bold text-accent">42,000,000 USDT</span>
                  <span class="whale-flow text-2xs">轉入 OKX 充值熱錢包</span>
                </div>
                <span class="whale-tag badge badge-2xs badge-warning">交易所充值</span>
              </div>
            </div>

            <div class="whale-feed-item">
              <span class="whale-time mono tabular-nums text-muted text-2xs">09:30:15</span>
              <div class="whale-main">
                <div class="whale-title">
                  <span class="whale-amount font-bold text-success">1,250 BTC</span>
                  <span class="whale-flow text-2xs">Coinbase Prime 提幣至未知冷錢包</span>
                </div>
                <span class="whale-tag badge badge-2xs badge-success">機構囤幣託管</span>
              </div>
            </div>

            <div class="whale-feed-item">
              <span class="whale-time mono tabular-nums text-muted text-2xs">08:14:02</span>
              <div class="whale-main">
                <div class="whale-title">
                  <span class="whale-amount font-bold text-info">15,000 ETH</span>
                  <span class="whale-flow text-2xs">Lido 質押合約大額贖回</span>
                </div>
                <span class="whale-tag badge badge-2xs badge-neutral">質押異動</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.market-intel-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
  overflow-y: auto;
}

.title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.title-row h2 {
  font-size: var(--text-lg);
  font-weight: 700;
}

.subtitle {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.intel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-4);
}

.intel-text {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  line-height: 1.5;
}

.intel-footer {
  display: flex;
  justify-content: space-between;
  margin-top: var(--space-3);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border-secondary);
}

.text-warning { color: var(--color-warning); }

.intel-lower-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  margin-top: var(--space-2);
}

@media (max-width: 1024px) {
  .intel-lower-grid {
    grid-template-columns: 1fr;
  }
}

.whale-feed-list {
  display: flex;
  flex-direction: column;
}

.whale-feed-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-secondary);
  transition: background-color 0.15s ease;
}

.whale-feed-item:hover {
  background-color: var(--bg-surface-hover);
}

.whale-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex: 1;
}

.whale-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.whale-amount {
  font-size: var(--text-xs);
  letter-spacing: 0.02em;
}

.badge-2xs {
  font-size: 9px;
  padding: 1px 4px;
}
</style>
