<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useV0Engine } from '@/state/v0-engine';

const { fills: engineFills } = useV0Engine();

interface FillItem {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  qty: number;
  price: number;
  pnl: number;
  time: string;
}

const fallbackFills = ref<FillItem[]>([
  { id: '1', symbol: 'ETH-PERP', side: 'BUY', qty: 1.70, price: 3182.60, pnl: 35.20, time: '12:32:31' },
  { id: '2', symbol: 'BTC-PERP', side: 'SELL', qty: 0.62, price: 64182.50, pnl: 22.40, time: '12:31:18' },
  { id: '3', symbol: 'SOL-PERP', side: 'BUY', qty: 15.00, price: 148.90, pnl: -12.10, time: '12:28:44' },
  { id: '4', symbol: 'DOGE-PERP', side: 'BUY', qty: 8000, price: 0.174, pnl: 18.90, time: '12:25:02' }
]);

let timer: any = null;

onMounted(() => {
  timer = setInterval(() => {
    // Occasionally simulate live incoming tick fill
    const isBuy = Math.random() > 0.45;
    const isBtc = Math.random() > 0.5;
    const now = new Date();
    const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
    const newFill: FillItem = {
      id: String(Date.now()),
      symbol: isBtc ? 'BTC-PERP' : 'ETH-PERP',
      side: isBuy ? 'BUY' : 'SELL',
      qty: Number((Math.random() * 1.5 + 0.5).toFixed(2)),
      price: isBtc ? Number((64100 + Math.random() * 100).toFixed(2)) : Number((3180 + Math.random() * 10).toFixed(2)),
      pnl: Number(((Math.random() - 0.3) * 60).toFixed(2)),
      time: timeStr
    };
    fallbackFills.value.unshift(newFill);
    if (fallbackFills.value.length > 4) fallbackFills.value.pop();
  }, 4500);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});

function formatPrice(val: number): string {
  return val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
</script>

<template>
  <div class="relaxed-fills-card">
    <div class="card-header-bar">
      <h3 class="card-title">Recent Fills</h3>
      <span class="live-pill">
        <span class="live-dot"></span>
        LIVE
      </span>
    </div>

    <ul class="fills-list">
      <li v-for="fill in fallbackFills" :key="fill.id" class="fill-row">
        <!-- Square direction badge with arrow -->
        <div class="fill-side-box" :class="fill.side === 'BUY' ? 'box-buy' : 'box-sell'">
          <svg v-if="fill.side === 'BUY'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <line x1="7" y1="17" x2="17" y2="7"/>
            <polyline points="17 17 7 17 7 7"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
            <line x1="7" y1="17" x2="17" y2="7"/>
            <polyline points="7 7 17 7 17 17"/>
          </svg>
        </div>

        <div class="fill-info-left">
          <p class="fill-symbol num">
            {{ fill.symbol }}
            <span class="side-tag num" :class="fill.side === 'BUY' ? 'text-up' : 'text-down'">
              {{ fill.side }}
            </span>
          </p>
          <p class="fill-price-qty num">
            {{ fill.qty }} @ {{ formatPrice(fill.price) }}
          </p>
        </div>

        <div class="fill-info-right text-right">
          <p class="fill-pnl num" :class="fill.pnl >= 0 ? 'text-up' : 'text-down'">
            {{ fill.pnl >= 0 ? '+' : '' }}{{ fill.pnl.toFixed(2) }}
          </p>
          <p class="fill-time num">{{ fill.time }}</p>
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.relaxed-fills-card {
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: var(--os-card-radius, 6px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.card-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--os-border);
}

.card-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--os-text-primary);
}

.live-pill {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 9px;
  font-weight: 500;
  color: var(--os-up);
}

.live-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--os-up);
  animation: pulse 2s infinite ease-in-out;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.85); }
}

.fills-list {
  list-style: none;
  padding: 0 1rem;
  margin: 0;
  display: flex;
  flex-direction: column;
}

.fill-row {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  padding: 0.625rem 0;
  border-bottom: 1px solid var(--os-border-subtle);
  transition: background 0.15s ease;
}

.fill-row:last-child {
  border-bottom: none;
}

.fill-side-box {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  flex-shrink: 0;
}

.box-buy {
  background: var(--os-up-bg);
  color: var(--os-up);
}

.box-sell {
  background: var(--os-down-bg);
  color: var(--os-down);
}

.fill-info-left {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.fill-symbol {
  font-size: 10px;
  font-weight: 500;
  color: var(--os-text-primary);
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.side-tag {
  font-size: 9px;
  font-weight: 500;
}

.fill-price-qty {
  font-size: 9px;
  color: var(--os-text-muted);
  margin-top: 2px;
}

.fill-info-right {
  margin-left: auto;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.fill-pnl {
  font-size: 0.78rem;
  font-weight: 500;
}

.fill-time {
  font-size: 0.68rem;
  color: var(--os-text-muted);
  margin-top: 0.15rem;
}

.text-up {
  color: var(--os-up);
}

.text-down {
  color: var(--os-down);
}
</style>
