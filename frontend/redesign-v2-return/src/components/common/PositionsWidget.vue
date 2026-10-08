<script setup lang="ts">
import { ref, computed } from 'vue';

export interface PositionItem {
  id: string;
  symbol: string;
  timeframe: string;
  botName: string;
  side: '多' | '空';
  amount: string;
  unit: string;
  entryPrice: string;
  markPrice: string;
  unrealizedPnl: string;
  pnlPct: string;
  isPositive: boolean;
  leverage: string;
  marginUsdt: string;
}

const positions = ref<PositionItem[]>([
  {
    id: 'pos-btc',
    symbol: 'BTCUSDT',
    timeframe: '15m',
    botName: 'Tabby',
    side: '多',
    amount: '0.12',
    unit: 'BTC',
    entryPrice: '59,184.2',
    markPrice: '62,140.5',
    unrealizedPnl: '+79.26',
    pnlPct: '+1.06%',
    isPositive: true,
    leverage: '3.0x',
    marginUsdt: '248.50'
  },
  {
    id: 'pos-eth',
    symbol: 'ETHUSDT',
    timeframe: '1h',
    botName: 'Calico',
    side: '多',
    amount: '2.40',
    unit: 'ETH',
    entryPrice: '2,510.0',
    markPrice: '2,450.2',
    unrealizedPnl: '-143.52',
    pnlPct: '-2.38%',
    isPositive: false,
    leverage: '3.0x',
    marginUsdt: '196.00'
  },
  {
    id: 'pos-sol',
    symbol: 'SOLUSDT',
    timeframe: '5m',
    botName: 'Mochi',
    side: '多',
    amount: '18.0',
    unit: 'SOL',
    entryPrice: '154.1',
    markPrice: '152.8',
    unrealizedPnl: '-23.40',
    pnlPct: '-0.84%',
    isPositive: false,
    leverage: '2.0x',
    marginUsdt: '137.50'
  }
]);

const totalNominal = computed(() => {
  return '7,452.40';
});
</script>

<template>
  <div class="positions-widget">
    <div class="positions-table-wrap">
      <table class="positions-table">
        <thead>
          <tr>
            <th class="th-sym">標的 / 策略</th>
            <th class="th-side">方向</th>
            <th class="th-qty text-right">持倉量</th>
            <th class="th-price text-right">開倉 / 標記價</th>
            <th class="th-pnl text-right">未實現損益</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in positions" :key="p.id" class="pos-row">
            <!-- 標的 / 策略 -->
            <td class="td-sym">
              <div class="sym-group">
                <span class="sym-name mono">{{ p.symbol }}</span>
                <span class="tf-badge mono">{{ p.timeframe }}</span>
              </div>
              <div class="bot-owner text-muted">{{ p.botName }}</div>
            </td>

            <!-- 方向 -->
            <td class="td-side">
              <span class="side-pill" :class="p.side === '多' ? 'is-long' : 'is-short'">
                {{ p.side }}
              </span>
            </td>

            <!-- 持倉量 -->
            <td class="td-qty text-right mono">
              <div class="qty-val font-bold">{{ p.amount }} {{ p.unit }}</div>
              <div class="text-2xs text-muted">{{ p.leverage }} Cross</div>
            </td>

            <!-- 開倉 / 標記價 -->
            <td class="td-price text-right mono">
              <div class="text-xs text-muted">E: {{ p.entryPrice }}</div>
              <div class="text-xs text-primary font-bold">M: {{ p.markPrice }}</div>
            </td>

            <!-- 未實現損益 -->
            <td class="td-pnl text-right mono">
              <div class="pnl-amount font-bold" :class="p.isPositive ? 'text-green' : 'text-red'">
                {{ p.unrealizedPnl }} USDT
              </div>
              <div class="pnl-pct text-2xs" :class="p.isPositive ? 'text-green' : 'text-red'">
                {{ p.pnlPct }}
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.positions-widget {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  background: transparent;
  color: #e5e8ec;
  font-family: inherit;
  overflow: hidden;
}

.positions-table-wrap {
  flex: 1;
  overflow-x: auto;
  overflow-y: auto;
}

.positions-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

.positions-table thead th {
  padding: 8px 10px;
  color: #90969d;
  font-size: 11px;
  font-weight: 500;
  border-bottom: 1px solid #282c31;
  white-space: nowrap;
  background: #0f1216;
  position: sticky;
  top: 0;
  z-index: 2;
}

.pos-row {
  border-bottom: 1px solid #282c31;
  transition: background 0.15s ease;
}

.pos-row:hover {
  background: #1d2126;
}

.positions-table td {
  padding: 8px 10px;
  vertical-align: middle;
  white-space: nowrap;
}

.sym-group {
  display: flex;
  align-items: center;
  gap: 5px;
}

.sym-name {
  font-size: 12px;
  font-weight: 700;
  color: #e5e8ec;
}

.tf-badge {
  font-size: 9.5px;
  background: #181c21;
  color: #90969d;
  border: 1px solid #282c31;
  padding: 1px 4px;
  border-radius: 2px;
}

.bot-owner {
  font-size: 10.5px;
  margin-top: 1px;
  color: #90969d;
}

.side-pill {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  display: inline-block;
}

.side-pill.is-long {
  background: rgba(101, 203, 167, 0.12);
  color: #65cba7;
  border: 1px solid rgba(101, 203, 167, 0.3);
}

.side-pill.is-short {
  background: rgba(237, 118, 101, 0.12);
  color: #ed7665;
  border: 1px solid rgba(237, 118, 101, 0.3);
}

.pnl-amount {
  font-size: 12px;
}

.text-primary {
  color: #e8b45e !important;
}

.text-green {
  color: #65cba7 !important;
}

.text-red {
  color: #ed7665 !important;
}

.text-right {
  text-align: right;
}

.text-muted {
  color: #90969d;
}

.text-2xs {
  font-size: 10px;
}

.mono {
  font-family: var(--default-mono-font-family, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
}
</style>
