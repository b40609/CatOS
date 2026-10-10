<script setup lang="ts">
import { ref, computed } from 'vue';
import { usePreferences } from '@/state/usePreferences';

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

const { preferences } = usePreferences();

const positions = ref<PositionItem[]>([
  {
    id: 'pos-btc',
    symbol: 'BTCUSDT',
    timeframe: '15m',
    botName: 'Tabby · breakout_v2',
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
    botName: 'Calico · trend_follow',
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
    botName: 'Mochi · mean_revert',
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
</script>

<template>
  <div class="positions-widget">
    <!-- 即時持倉態勢表格 (已定案：TradingView 幾何箭頭，零浪費直出) -->
    <div class="positions-table-wrap">
      <table class="positions-table">
        <thead>
          <tr>
            <th class="th-sym">{{ preferences.language === 'en' ? 'MARKET / STRATEGY' : '標的 / 策略' }}</th>
            <th class="th-side">{{ preferences.language === 'en' ? 'SIDE / DIRECTION' : '方向 / 態勢' }}</th>
            <th class="th-qty text-right">{{ preferences.language === 'en' ? 'QTY / MARGIN' : '持倉量 / 保證金' }}</th>
            <th class="th-price text-right">{{ preferences.language === 'en' ? 'MARK / ENTRY' : '標記 / 開倉價' }}</th>
            <th class="th-pnl text-right">{{ preferences.language === 'en' ? 'UNREALIZED PnL' : '未實現損益' }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in positions" :key="p.id" class="pos-row">
            <!-- 標的 / 策略 (雙層) -->
            <td class="td-sym">
              <div class="sym-group">
                <span class="sym-name mono">{{ p.symbol }}</span>
                <span class="tf-badge mono">{{ p.timeframe }}</span>
              </div>
              <div class="bot-owner text-muted mono text-2xs">{{ p.botName }}</div>
            </td>

            <!-- 方向態勢 (★ 使用者定案：TradingView 幾何箭頭) -->
            <td class="td-side">
              <span
                class="badge-tv mono font-bold"
                :class="p.side === '多' ? 'is-long' : 'is-short'"
              >
                {{ p.side === '多' ? '▲ LONG' : '▼ SHORT' }}
                <span class="tv-lev">{{ p.leverage }}</span>
              </span>
            </td>

            <!-- 持倉量與名義保證金 (雙層) -->
            <td class="td-qty text-right mono">
              <div class="qty-val font-bold">{{ p.amount }} {{ p.unit }}</div>
              <div class="text-2xs text-muted">{{ p.marginUsdt }} USDT ({{ p.leverage }})</div>
            </td>

            <!-- 標記價與開倉價 (雙層) -->
            <td class="td-price text-right mono">
              <div class="text-xs text-primary font-bold">{{ p.markPrice }}</div>
              <div class="text-2xs text-muted">{{ p.entryPrice }} entry</div>
            </td>

            <!-- 未實現損益 (雙層數值棧，對齊使用者附圖) -->
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
.th-sym, .td-sym { text-align: left; }
.th-side, .td-side { text-align: left; }
.th-qty, .td-qty { text-align: right; }
.th-price, .td-price { text-align: right; }
.th-pnl, .td-pnl { text-align: right; }

.pos-row {
  border-bottom: 1px solid #20242a;
  transition: background 0.15s ease;
}

.pos-row:hover {
  background: #181c22;
}

.positions-table td {
  padding: 6px 10px;
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
  padding: 0px 4px;
  border-radius: 2px;
}

.bot-owner {
  margin-top: 1px;
}

/* ★ 使用者定案：TradingView 幾何箭頭 + 槓桿 */
.badge-tv {
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.badge-tv.is-long {
  color: #65cba7;
}
.badge-tv.is-short {
  color: #ed7665;
}
.tv-lev {
  font-size: 9px;
  background: #1f242b;
  color: #90969d;
  padding: 0 3px;
  border-radius: 2px;
  border: 1px solid #282c31;
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
