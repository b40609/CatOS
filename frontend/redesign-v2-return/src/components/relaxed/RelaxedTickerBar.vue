<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';

interface MarketQuote {
  code: string;
  name: string;
  symbol: string;
  price: number;
  change: number;
}

const markets = ref<MarketQuote[]>([
  { code: 'BTC', name: 'BTC/USDT', symbol: '₿', price: 64188.50, change: 2.82 },
  { code: 'ETH', name: 'ETH/USDT', symbol: 'Ξ', price: 3183.20, change: 1.44 },
  { code: 'SOL', name: 'SOL/USDT', symbol: '◎', price: 142.45, change: -1.92 },
  { code: 'DOGE', name: 'DOGE/USDT', symbol: 'Ð', price: 0.1742, change: 4.21 }
]);

let timer: any = null;

onMounted(() => {
  timer = setInterval(() => {
    markets.value.forEach(m => {
      const delta = (Math.random() - 0.49) * 0.0006;
      m.price = Number((m.price * (1 + delta)).toFixed(m.price < 1 ? 4 : 2));
    });
  }, 3200);
});

onUnmounted(() => {
  if (timer) clearInterval(timer);
});

function formatPrice(val: number): string {
  if (val < 1) return val.toFixed(4);
  return val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
</script>

<template>
  <div class="relaxed-ticker-bar">
    <div
      v-for="m in markets"
      :key="m.code"
      class="ticker-item"
    >
      <div class="ticker-left">
        <span class="coin-badge">{{ m.symbol }}</span>
        <div class="ticker-labels">
          <span class="coin-code">{{ m.code }}<span class="coin-pair">/USDT</span></span>
        </div>
      </div>
      <div class="ticker-right">
        <span class="coin-price num">{{ formatPrice(m.price) }}</span>
        <span class="coin-change num" :class="m.change >= 0 ? 'text-up' : 'text-down'">
          {{ m.change >= 0 ? '+' : '' }}{{ m.change.toFixed(2) }}%
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.relaxed-ticker-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: var(--os-card-radius, 6px);
  overflow: hidden;
  margin-bottom: 1rem;
}

.ticker-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.625rem 1rem;
  border-right: 1px solid var(--os-border);
  transition: background 0.15s ease;
  min-width: 0;
}

.ticker-item:last-child {
  border-right: none;
}

.ticker-item:hover {
  background: var(--os-bg-card-hover);
}

.ticker-left {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.coin-badge {
  display: grid;
  place-items: center;
  width: 1.6rem;
  height: 1.6rem;
  border-radius: 50%;
  background: var(--os-bg-surface);
  border: 1px solid var(--os-border);
  font-size: 0.75rem;
  color: var(--os-text-primary);
  font-family: var(--font-mono);
}

.ticker-labels {
  display: flex;
  flex-direction: column;
}

.coin-code {
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--os-text-primary);
}

.coin-pair {
  color: var(--os-text-muted);
  font-size: 0.7rem;
}

.ticker-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.coin-price {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--os-text-primary);
}

.coin-change {
  font-size: 0.68rem;
  font-weight: 500;
}

.text-up {
  color: var(--os-up);
}

.text-down {
  color: var(--os-down);
}

@media (max-width: 900px) {
  .relaxed-ticker-bar {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 500px) {
  .relaxed-ticker-bar {
    grid-template-columns: 1fr;
  }
}
</style>
