<script setup lang="ts">
import { ref } from 'vue';

export type ActivityTab = 'positions' | 'orders' | 'fills';

export interface PositionItem {
  id: string;
  botId: string;
  botName: string;
  symbol: string;
  side: 'long' | 'short';
  qty: string;
  entry: string;
  mark: string;
  notional: string;
  upnl: string;
  upnlPct: string;
  positive: boolean;
  opened: string;
  isPaused?: boolean;
}

export interface OrderItem {
  id: string;
  botId: string;
  botName: string;
  symbol: string;
  side: 'buy' | 'sell';
  type: '限價' | '停損';
  price: string;
  qty: string;
  distPct: string;
  placed: string;
}

export interface FillItem {
  id: string;
  botId: string;
  botName: string;
  symbol: string;
  action: '平多' | '平空' | '開多' | '開空';
  qty: string;
  price: string;
  pnl: string;
  positive: boolean;
  time: string;
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
}>();

const currentTab = ref<ActivityTab>('positions');

const positions = ref<PositionItem[]>([
  {
    id: 'p1',
    botId: 'tabby-01',
    botName: 'Tabby',
    symbol: 'BTCUSDT',
    side: 'long',
    qty: '0.12',
    entry: '59,184.2',
    mark: '62,140.5',
    notional: '7,456',
    upnl: '+79.26',
    upnlPct: '+1.06%',
    positive: true,
    opened: '04:30',
    isPaused: false
  },
  {
    id: 'p2',
    botId: 'calico-02',
    botName: 'Calico',
    symbol: 'ETHUSDT',
    side: 'long',
    qty: '2.40',
    entry: '2,510.0',
    mark: '2,450.2',
    notional: '5,880',
    upnl: '-143.52',
    upnlPct: '-2.38%',
    positive: false,
    opened: '10/5 06:00',
    isPaused: false
  },
  {
    id: 'p3',
    botId: 'mochi-03',
    botName: 'Mochi',
    symbol: 'SOLUSDT',
    side: 'long',
    qty: '18.0',
    entry: '154.1',
    mark: '152.8',
    notional: '2,750',
    upnl: '-23.40',
    upnlPct: '-0.84%',
    positive: false,
    opened: '09:04',
    isPaused: false
  },
  {
    id: 'p4',
    botId: 'shiro-04',
    botName: 'Shiro',
    symbol: 'BTCUSDT',
    side: 'long',
    qty: '0.05',
    entry: '62,890.0',
    mark: '62,140.5',
    notional: '3,107',
    upnl: '-37.47',
    upnlPct: '-1.19%',
    positive: false,
    opened: '10/4 03:00',
    isPaused: true
  },
  {
    id: 'p5',
    botId: 'shiro-04',
    botName: 'Shiro',
    symbol: 'ETHUSDT',
    side: 'short',
    qty: '1.30',
    entry: '2,431.5',
    mark: '2,450.2',
    notional: '3,185',
    upnl: '-24.31',
    upnlPct: '-0.77%',
    positive: false,
    opened: '10/4 03:00',
    isPaused: true
  }
]);

const orders = ref<OrderItem[]>([
  {
    id: 'o1',
    botId: 'mochi-03',
    botName: 'Mochi',
    symbol: 'SOLUSDT',
    side: 'buy',
    type: '限價',
    price: '147.8',
    qty: '6.0',
    distPct: '-3.27%',
    placed: '09:30'
  },
  {
    id: 'o2',
    botId: 'mochi-03',
    botName: 'Mochi',
    symbol: 'SOLUSDT',
    side: 'buy',
    type: '限價',
    price: '146.9',
    qty: '6.0',
    distPct: '-3.86%',
    placed: '09:30'
  },
  {
    id: 'o3',
    botId: 'tabby-01',
    botName: 'Tabby',
    symbol: 'BTCUSDT',
    side: 'sell',
    type: '停損',
    price: '60,560.0',
    qty: '0.12',
    distPct: '-2.54%',
    placed: '09:15'
  },
  {
    id: 'o4',
    botId: 'calico-02',
    botName: 'Calico',
    symbol: 'ETHUSDT',
    side: 'sell',
    type: '停損',
    price: '2,350.0',
    qty: '2.40',
    distPct: '-4.09%',
    placed: '10/5 06:00'
  }
]);

const fills = ref<FillItem[]>([
  {
    id: 'f1',
    botId: 'tabby-01',
    botName: 'Tabby',
    symbol: 'BTCUSDT',
    action: '開多',
    qty: '0.12',
    price: '59,184.2',
    pnl: '+42.50',
    positive: true,
    time: '10/6 04:30'
  },
  {
    id: 'f2',
    botId: 'calico-02',
    botName: 'Calico',
    symbol: 'ETHUSDT',
    action: '平多',
    qty: '1.20',
    price: '2,510.0',
    pnl: '-18.20',
    positive: false,
    time: '10/5 18:00'
  },
  {
    id: 'f3',
    botId: 'mochi-03',
    botName: 'Mochi',
    symbol: 'SOLUSDT',
    action: '開多',
    qty: '18.0',
    price: '154.1',
    pnl: '+15.40',
    positive: true,
    time: '10/5 09:04'
  },
  {
    id: 'f4',
    botId: 'shiro-04',
    botName: 'Shiro',
    symbol: 'BTCUSDT',
    action: '平空',
    qty: '0.05',
    price: '62,890.0',
    pnl: '+24.10',
    positive: true,
    time: '10/4 16:00'
  }
]);

function openBot(botId: string) {
  emit('selectBot', botId);
}
</script>

<template>
  <div class="activity-panel-root">
    <!-- Header (獨立展示時渲染完整標題與切換) -->
    <div v-if="showHeader" class="panel-header">
      <div class="header-left">
        <span class="scope-tag">機器人</span>
        <h3 class="panel-title">部位與成交</h3>
      </div>

      <!-- Segmented Switcher (持倉 / 掛單 / 成交) -->
      <div class="header-actions">
        <div class="tab-segmented" role="radiogroup">
          <button
            type="button"
            class="tab-btn"
            :class="{ active: currentTab === 'positions' }"
            @click="currentTab = 'positions'"
          >
            持倉 <span class="badge-num mono">{{ positions.length }}</span>
          </button>
          <button
            type="button"
            class="tab-btn"
            :class="{ active: currentTab === 'orders' }"
            @click="currentTab = 'orders'"
          >
            掛單 <span class="badge-num mono">{{ orders.length }}</span>
          </button>
          <button
            type="button"
            class="tab-btn"
            :class="{ active: currentTab === 'fills' }"
            @click="currentTab = 'fills'"
          >
            成交 <span class="badge-num mono">{{ fills.length }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 嵌入卡片模式：僅保留緊湊三態切換條 -->
    <div v-else class="compact-tab-bar">
      <div class="tab-segmented" role="radiogroup">
        <button
          type="button"
          class="tab-btn"
          :class="{ active: currentTab === 'positions' }"
          @click="currentTab = 'positions'"
        >
          持倉 <span class="badge-num mono">{{ positions.length }}</span>
        </button>
        <button
          type="button"
          class="tab-btn"
          :class="{ active: currentTab === 'orders' }"
          @click="currentTab = 'orders'"
        >
          掛單 <span class="badge-num mono">{{ orders.length }}</span>
        </button>
        <button
          type="button"
          class="tab-btn"
          :class="{ active: currentTab === 'fills' }"
          @click="currentTab = 'fills'"
        >
          成交 <span class="badge-num mono">{{ fills.length }}</span>
        </button>
      </div>
    </div>

    <!-- Body Tables -->
    <div class="panel-body">
      <!-- 1. 持倉表格 (Positions) -->
      <div v-if="currentTab === 'positions'" class="table-container">
        <table class="act-table">
          <thead>
            <tr>
              <th class="th-bot">機器人</th>
              <th class="th-sym">標的</th>
              <th class="th-side">方向</th>
              <th class="th-qty text-right">數量</th>
              <th class="th-entry text-right">開倉價</th>
              <th class="th-mark text-right">標記價</th>
              <th class="th-notional text-right">名目 USDT</th>
              <th class="th-upnl text-right">未實現損益</th>
              <th class="th-time text-right">開倉時間</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in positions"
              :key="p.id"
              class="act-row"
              @click="openBot(p.botId)"
            >
              <td class="td-bot">
                <span class="bot-link">{{ p.botName }}</span>
                <span v-if="p.isPaused" class="paused-pill">暫停</span>
              </td>
              <td class="td-sym mono">{{ p.symbol }}</td>
              <td class="td-side">
                <span :class="p.side === 'long' ? 'text-green' : 'text-red'">
                  {{ p.side === 'long' ? '多' : '空' }}
                </span>
              </td>
              <td class="td-qty mono text-right">{{ p.qty }}</td>
              <td class="td-entry mono text-right">{{ p.entry }}</td>
              <td class="td-mark mono text-right">{{ p.mark }}</td>
              <td class="td-notional mono text-right">{{ p.notional }}</td>
              <td class="td-upnl mono text-right">
                <span :class="p.positive ? 'text-green' : 'text-red'">
                  {{ p.upnl }}
                </span>
                <span class="upnl-pct text-muted">({{ p.upnlPct }})</span>
              </td>
              <td class="td-time mono text-muted text-right">{{ p.opened }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 2. 掛單表格 (Orders) -->
      <div v-else-if="currentTab === 'orders'" class="table-container">
        <table class="act-table">
          <thead>
            <tr>
              <th class="th-bot">機器人</th>
              <th class="th-sym">標的</th>
              <th class="th-side">方向</th>
              <th class="th-type">類型</th>
              <th class="th-price text-right">掛單價格</th>
              <th class="th-qty text-right">數量</th>
              <th class="th-dist text-right">距市價</th>
              <th class="th-time text-right">下單時間</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="o in orders"
              :key="o.id"
              class="act-row"
              @click="openBot(o.botId)"
            >
              <td class="td-bot">
                <span class="bot-link">{{ o.botName }}</span>
              </td>
              <td class="td-sym mono">{{ o.symbol }}</td>
              <td class="td-side">
                <span :class="o.side === 'buy' ? 'text-green' : 'text-red'">
                  {{ o.side === 'buy' ? '買入' : '賣出' }}
                </span>
              </td>
              <td class="td-type">
                <span :class="o.type === '停損' ? 'type-stop' : 'type-limit'">
                  {{ o.type }}
                </span>
              </td>
              <td class="td-price mono text-right">{{ o.price }}</td>
              <td class="td-qty mono text-right">{{ o.qty }}</td>
              <td class="td-dist mono text-muted text-right">{{ o.distPct }}</td>
              <td class="td-time mono text-muted text-right">{{ o.placed }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 3. 成交表格 (Fills) -->
      <div v-else class="table-container">
        <table class="act-table">
          <thead>
            <tr>
              <th class="th-bot">機器人</th>
              <th class="th-sym">標的</th>
              <th class="th-action">動作</th>
              <th class="th-qty text-right">數量</th>
              <th class="th-price text-right">成交價</th>
              <th class="th-pnl text-right">損益</th>
              <th class="th-time text-right">時間</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="f in fills"
              :key="f.id"
              class="act-row"
              @click="openBot(f.botId)"
            >
              <td class="td-bot">
                <span class="bot-link">{{ f.botName }}</span>
              </td>
              <td class="td-sym mono">{{ f.symbol }}</td>
              <td class="td-action">
                <span :class="f.action.includes('多') ? 'text-green' : 'text-red'">
                  {{ f.action }}
                </span>
              </td>
              <td class="td-qty mono text-right">{{ f.qty }}</td>
              <td class="td-price mono text-right">{{ f.price }}</td>
              <td class="td-pnl mono text-right">
                <span :class="f.positive ? 'text-green' : 'text-red'">
                  {{ f.pnl }}
                </span>
              </td>
              <td class="td-time mono text-muted text-right">{{ f.time }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.activity-panel-root {
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

.compact-tab-bar {
  display: flex;
  align-items: center;
  padding: 4px 10px;
  background: #181c21;
  border-bottom: 1px solid #282c31;
}

.tab-segmented {
  display: flex;
  background: #13161a;
  border: 1px solid #282c31;
  border-radius: 4px;
  padding: 2px;
  gap: 2px;
}

.tab-btn {
  background: transparent;
  border: none;
  color: #90969d;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s ease;
}

.tab-btn:hover {
  color: #e5e8ec;
}

.tab-btn.active {
  background: #1d2126;
  color: #e8b45e;
  font-weight: 600;
}

.badge-num {
  font-size: 9.5px;
  color: #e8b45e;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: auto;
}

.table-container {
  width: 100%;
}

.act-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
}

.act-table thead th {
  padding: 7px 10px;
  color: #90969d;
  font-size: 10.5px;
  font-weight: 500;
  border-bottom: 1px solid #282c31;
  white-space: nowrap;
  background: #0f1216;
  position: sticky;
  top: 0;
  z-index: 2;
}

.act-row {
  border-bottom: 1px solid #282c31;
  cursor: pointer;
  transition: background 0.12s ease;
}

.act-row:hover {
  background: #1d2126;
}

.act-table td {
  padding: 7px 10px;
  vertical-align: middle;
  white-space: nowrap;
}

.bot-link {
  font-weight: 600;
  color: #e5e8ec;
  text-decoration: underline;
  text-decoration-color: rgba(255, 255, 255, 0.25);
  text-underline-offset: 2px;
}

.bot-link:hover {
  text-decoration-color: #ffffff;
}

.paused-pill {
  margin-left: 6px;
  font-size: 9px;
  background: rgba(232, 180, 94, 0.15);
  color: #e8b45e;
  border: 1px solid rgba(232, 180, 94, 0.3);
  padding: 1px 4px;
  border-radius: 2px;
}

.type-stop {
  color: #ed7665;
  font-weight: 500;
}

.type-limit {
  color: #90969d;
}

.upnl-pct {
  margin-left: 4px;
  font-size: 10px;
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

.mono {
  font-family: 'JetBrains Mono', 'IBM Plex Mono', monospace;
}
</style>
