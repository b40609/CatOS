<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useV0Engine } from '@/state/v0-engine';
import { useRouter } from 'vue-router';
import MetricCard from '@/components/common/MetricCard.vue';
import RiskStatusCard from '@/components/common/RiskStatusCard.vue';
import SparklineArea from '@/components/common/SparklineArea.vue';
import DonutChart from '@/components/common/DonutChart.vue';
import RiskGauge from '@/components/common/RiskGauge.vue';
import StatusBadge from '@/components/common/StatusBadge.vue';
import EmptyState from '@/components/common/EmptyState.vue';
import AuditTimeline from '@/components/common/AuditTimeline.vue';
import BotQueueWidget from '@/components/common/BotQueueWidget.vue';
import PositionsWidget from '@/components/common/PositionsWidget.vue';
import EquityDrawdownHero from '@/components/common/EquityDrawdownHero.vue';
import AllocationUnifiedWidget, { type AllocationMode } from '@/components/common/AllocationUnifiedWidget.vue';
import ExposurePanel from '@/components/common/ExposurePanel.vue';
import ActivityPanel from '@/components/common/ActivityPanel.vue';
import RiskPanel from '@/components/common/RiskPanel.vue';
import V0AccountBand from '@/components/common/V0AccountBand.vue';
import V0BotTable from '@/components/common/V0BotTable.vue';
import V0EventFeed from '@/components/common/V0EventFeed.vue';
import V0Pipeline from '@/components/common/V0Pipeline.vue';
import BotDrawer, { type DrawerBotData } from '@/components/common/BotDrawer.vue';
import { useDashboard } from '@/state/useDashboard';
import { usePreferences } from '@/state/usePreferences';

const {
  kpis,
  equityPoints,
  exposureItems,
  auditEvents,
  riskState,
  botQueue,
  researchTasks,
  yaoziAlerts,
  isUnavailable,
  error
} = useDashboard();

const { preferences, setChartRange, setKpiDualLayer } = usePreferences();

const botPeriod = ref<'4H' | '1D' | '7D'>('7D');

// V0 Engine Shared State for Unified Header Actions
const {
  activityTab,
  eventFilter,
  positions: v0Positions,
  openOrders: v0Orders,
  fills: v0Fills,
  events: v0Events,
  period: v0Period,
  setPeriod: setV0Period
} = useV0Engine();

const pendingV0Events = computed(() => v0Events.value.filter((e: any) => !e.acked));

function isActivityCard(cardId: CardId) {
  return cardId === 'positions' || cardId === 'activity' || cardId === 'v0_activity';
}

function isEventsCard(cardId: CardId) {
  return cardId === 'events' || cardId === 'v0_events';
}

function isBotsCard(cardId: CardId) {
  return cardId === 'bots' || cardId === 'v0_bots';
}

function isEquityCard(cardId: CardId) {
  return cardId === 'v0_equity' || cardId === 'equity';
}

// 卡片模式
const botCardMode = ref<'new'>('new'); // 運行中 Bot 隊列全面套用新版態勢
const eventFilterMode = ref<'new' | 'old'>('old'); // 事件時間軸：預設全量，支援切換僅異常
const marketIntelMode = ref<'holding' | 'all'>('holding'); // 市場情報：預設持倉雷達，支援切換全部

// 保證金與曝險配置呈現模式 (預設依使用者偏好為 Donut 環，頂部按鈕可切換比對多空標尺與矩陣)
const allocationMode = ref<AllocationMode>('donut');

// 系統定案架構：Bloomberg 自由平鋪
export type BlueprintType = 'bloomberg';
const activeBlueprint = ref<BlueprintType>('bloomberg');

// 方案 1 Bloomberg 專用時間戳
const currentBbgTime = ref('');
function updateBbgTime() {
  const now = new Date();
  currentBbgTime.value = now.toLocaleTimeString('zh-TW', { hour12: false }) + ' (UTC+8)';
}
onMounted(() => {
  updateBbgTime();
  const timer = setInterval(updateBbgTime, 1000);
  onUnmounted(() => clearInterval(timer));
  loadAllProfiles();
});

// =========================================================================
// 方案 A (Bloomberg) & 方案 B (Linear) 多套版面存檔管理與即時縮放引擎
// =========================================================================
export type CardId =
  | 'v0_equity'
  | 'v0_bots'
  | 'v0_exposure'
  | 'v0_activity'
  | 'v0_risk'
  | 'v0_events'
  | 'v0_pipeline'
  | 'equity'
  | 'positions'
  | 'activity'
  | 'bots'
  | 'exposure'
  | 'risk'
  | 'events'
  | 'donut';

export interface SavedLayoutProfile {
  id: string;
  name: string;
  shortName?: string;
  ratioText?: string;
  icon?: string;
  desc?: string;
  isSystem?: boolean;
  blueprint: BlueprintType;
  allocationMode: AllocationMode;
  bbgLeftColWidth: number;
  bbgLeftUpperHeight: number;
  bbgRightWeights: number[];
  bbgPanes: { leftUpper: CardId; leftLower: CardId; right1: CardId; right2: CardId; right3: CardId };
  linearUpperHeight: number;
  linearUpperLeftWidth: number;
  linearLowerLeftWidth: number;
  linearPanes: { upperLeft: CardId; upperRight: CardId; lowerLeft: CardId; lowerRight: CardId };
  updatedAt: string;
}

const DEFAULT_PROFILES: SavedLayoutProfile[] = [
  {
    id: 'layout_b_quad',
    name: '舒展四分割 (60:40已定案)',
    shortName: '舒展四分割',
    ratioText: '60:40',
    icon: '🔲',
    desc: '左欄 60% 主視野 · 右欄 40% 輔助視野 (四角平衡 50:50) · 已定案佈局',
    isSystem: true,
    blueprint: 'bloomberg',
    allocationMode: 'donut',
    bbgLeftColWidth: 60,
    bbgLeftUpperHeight: 50,
    bbgRightWeights: [50, 50, 0],
    bbgPanes: {
      leftUpper: 'v0_equity',
      leftLower: 'v0_activity',
      right1: 'v0_bots',
      right2: 'v0_exposure',
      right3: 'v0_events'
    },
    linearUpperHeight: 50,
    linearUpperLeftWidth: 60,
    linearLowerLeftWidth: 60,
    linearPanes: { upperLeft: 'v0_equity', upperRight: 'v0_risk', lowerLeft: 'v0_bots', lowerRight: 'v0_activity' },
    updatedAt: '定案配置'
  },
  {
    id: 'layout_a_bloomberg',
    name: '方案 A · Bloomberg 經典 (62:38)',
    shortName: 'Bloomberg 經典',
    ratioText: '62:38',
    icon: '📊',
    desc: '左欄 62% (上走勢 52% / 下持倉 48%) · 右欄 38% (Bot 36% / 曝險 32% / 日誌 32%)',
    isSystem: true,
    blueprint: 'bloomberg',
    allocationMode: 'donut',
    bbgLeftColWidth: 62,
    bbgLeftUpperHeight: 52,
    bbgRightWeights: [36, 32, 32],
    bbgPanes: {
      leftUpper: 'v0_equity',
      leftLower: 'v0_activity',
      right1: 'v0_bots',
      right2: 'v0_exposure',
      right3: 'v0_events'
    },
    linearUpperHeight: 50,
    linearUpperLeftWidth: 64,
    linearLowerLeftWidth: 60,
    linearPanes: { upperLeft: 'v0_equity', upperRight: 'v0_exposure', lowerLeft: 'v0_bots', lowerRight: 'v0_risk' },
    updatedAt: '系統內建'
  },
  {
    id: 'layout_c_symmetric',
    name: '方案 C · 雙主對稱 (50:50)',
    shortName: '雙主對稱',
    ratioText: '50:50',
    icon: '⚖️',
    desc: '左右 50:50 等寬對稱 · 走勢與持倉並列頂部雙核心',
    isSystem: true,
    blueprint: 'bloomberg',
    allocationMode: 'donut',
    bbgLeftColWidth: 50,
    bbgLeftUpperHeight: 54,
    bbgRightWeights: [54, 46, 0],
    bbgPanes: {
      leftUpper: 'v0_equity',
      leftLower: 'v0_bots',
      right1: 'v0_activity',
      right2: 'v0_exposure',
      right3: 'v0_events'
    },
    linearUpperHeight: 50,
    linearUpperLeftWidth: 64,
    linearLowerLeftWidth: 60,
    linearPanes: { upperLeft: 'v0_equity', upperRight: 'v0_activity', lowerLeft: 'v0_bots', lowerRight: 'v0_exposure' },
    updatedAt: '系統內建'
  },
  {
    id: 'layout_d_risk_focus',
    name: '方案 D · 全景風控審計 (64:36)',
    shortName: '風控審計',
    ratioText: '64:36',
    icon: '🛡️',
    desc: '左欄 64% 寬大視野 · 右欄 36% 專注 Bot 33% / 風控 33% / 審計日誌 34%',
    isSystem: true,
    blueprint: 'bloomberg',
    allocationMode: 'donut',
    bbgLeftColWidth: 64,
    bbgLeftUpperHeight: 52,
    bbgRightWeights: [33, 33, 34],
    bbgPanes: {
      leftUpper: 'v0_equity',
      leftLower: 'v0_activity',
      right1: 'v0_bots',
      right2: 'v0_risk',
      right3: 'v0_events'
    },
    linearUpperHeight: 50,
    linearUpperLeftWidth: 64,
    linearLowerLeftWidth: 60,
    linearPanes: { upperLeft: 'v0_equity', upperRight: 'v0_risk', lowerLeft: 'v0_bots', lowerRight: 'v0_events' },
    updatedAt: '系統內建'
  }
];

const STORAGE_KEY_PROFILES = 'catos_saved_layout_profiles_v12';
const STORAGE_KEY_CURRENT_PROFILE = 'catos_current_profile_id_v12';

// 方案 A (Bloomberg) 比例狀態 (預設 60:40 舒展四分割定案)
const bbgLeftColWidth = ref<number>(60);
const bbgLeftUpperHeight = ref<number>(50);
const bbgRightWeights = ref<number[]>([50, 50, 0]);

// 方案 B (Linear) 比例狀態
const linearUpperHeight = ref<number>(50);
const linearUpperLeftWidth = ref<number>(64);
const linearLowerLeftWidth = ref<number>(60);

const bbgPanes = ref<{ leftUpper: CardId; leftLower: CardId; right1: CardId; right2: CardId; right3: CardId }>({
  leftUpper: 'v0_equity',
  leftLower: 'v0_activity',
  right1: 'v0_bots',
  right2: 'v0_exposure',
  right3: 'v0_events'
});

const linearPanes = ref<{ upperLeft: CardId; upperRight: CardId; lowerLeft: CardId; lowerRight: CardId }>({
  upperLeft: 'equity',
  upperRight: 'donut',
  lowerLeft: 'bots',
  lowerRight: 'events'
});

const CARD_META: Record<CardId, { title: string; subtitle: string; isV0: boolean; tag: string }> = {
  v0_equity: { title: '帳戶權益 (Equity)', subtitle: '', isV0: true, tag: '緊湊' },
  equity: { title: '帳戶權益 (Equity)', subtitle: '', isV0: false, tag: '動態' },
  v0_bots: { title: '量化機器人 (Bots)', subtitle: '', isV0: true, tag: '表格' },
  bots: { title: '量化機器人 (Bots)', subtitle: '', isV0: false, tag: '動態' },
  v0_exposure: { title: '多空曝險配置 (Exposure)', subtitle: '', isV0: true, tag: '標尺' },
  exposure: { title: '多空曝險配置 (Exposure)', subtitle: '', isV0: true, tag: '標尺' },
  donut: { title: '多空曝險配置 (Exposure)', subtitle: '', isV0: false, tag: '環形' },
  v0_activity: { title: '部位與活動 (Positions)', subtitle: '', isV0: true, tag: '明細' },
  activity: { title: '部位與活動 (Positions)', subtitle: '', isV0: true, tag: '明細' },
  positions: { title: '部位與活動 (Positions)', subtitle: '', isV0: false, tag: '持倉' },
  v0_risk: { title: '風控防護指標 (Risk Guard)', subtitle: '', isV0: true, tag: '限額' },
  risk: { title: '風控防護指標 (Risk Guard)', subtitle: '', isV0: false, tag: '儀表' },
  v0_events: { title: '系統日誌審計 (Audit Stream)', subtitle: '', isV0: true, tag: '串流' },
  events: { title: '系統日誌審計 (Audit Stream)', subtitle: '', isV0: false, tag: '時間軸' },
  v0_pipeline: { title: '策略研發看板 (Pipeline)', subtitle: '', isV0: true, tag: '看板' }
};

// 判斷當前卡片是否為 V0 版本
function isCardV0(cardId: CardId): boolean {
  return CARD_META[cardId]?.isV0 ?? false;
}

// 取得同類型另一版本 CardId（用於標題列一鍵秒切）
function getTwinVersionId(cardId: CardId): CardId {
  switch (cardId) {
    case 'v0_equity': return 'equity';
    case 'equity': return 'v0_equity';
    case 'v0_bots': return 'bots';
    case 'bots': return 'v0_bots';
    case 'v0_activity':
    case 'activity': return 'positions';
    case 'positions': return 'v0_activity';
    case 'v0_exposure':
    case 'exposure': return 'donut';
    case 'donut': return 'v0_exposure';
    case 'v0_risk': return 'risk';
    case 'risk': return 'v0_risk';
    case 'v0_events': return 'events';
    case 'events': return 'v0_events';
    case 'v0_pipeline': return 'equity';
    default: return cardId;
  }
}

// 快速切換某個槽位的版本
function setSlotCardVersion(slot: 'leftUpper' | 'leftLower' | 'right1' | 'right2' | 'right3', target: 'v0' | 'astra') {
  const current = bbgPanes.value[slot];
  const currentIsV0 = isCardV0(current);
  if ((target === 'v0' && currentIsV0) || (target === 'astra' && !currentIsV0)) {
    return; // 已經是該版本
  }
  bbgPanes.value[slot] = getTwinVersionId(current);
  saveBlueprintLayouts();
  showToast(`已切換此卡片為 ${target === 'v0' ? 'V0 移植版' : 'Astra 原版'}`);
}

const savedProfiles = ref<SavedLayoutProfile[]>([...DEFAULT_PROFILES]);
const currentProfileId = ref<string>('layout_b_quad');

// V0 抽屜交互狀態
const selectedDrawerBot = ref<DrawerBotData | null>(null);

function handleOpenBotDrawer(botId: string) {
  const mockBots: Record<string, DrawerBotData> = {
    'tabby-01': {
      id: 'tabby-01',
      name: 'Tabby',
      strategy: 'breakout_v2 v2.2',
      symbol: 'BTCUSDT',
      timeframe: '15m',
      state: 'running',
      lastSignal: '04:30 進場多',
      returnPct: '+0.68%',
      maxDrawdownPct: '-4.65%',
      winRatePct: '65%',
      guardPct: '-8.0%',
      drawdownNowPct: '-4.65%',
      drawdownRatio: 4.65 / 8.0,
      legs: [
        { symbol: 'BTCUSDT', side: '多', qty: '0.12', markPrice: '62,140.5', upnl: '+79.26', positive: true }
      ],
      recentTrades: [
        { time: '10/6 04:30', side: '多', price: '59,184.2', pnlPct: '+1.06%', positive: true },
        { time: '10/5 21:15', side: '空', price: '60,420.0', pnlPct: '-0.38%', positive: false }
      ]
    },
    'calico-02': {
      id: 'calico-02',
      name: 'Calico',
      strategy: 'trend_follow v1.8',
      symbol: 'ETHUSDT',
      timeframe: '1h',
      state: 'running',
      lastSignal: '10/5 06:00 進場多',
      returnPct: '-0.85%',
      maxDrawdownPct: '-3.80%',
      winRatePct: '58%',
      guardPct: '-10.0%',
      drawdownNowPct: '-3.80%',
      drawdownRatio: 3.8 / 10.0,
      legs: [
        { symbol: 'ETHUSDT', side: '多', qty: '2.40', markPrice: '2,450.2', upnl: '-143.52', positive: false }
      ],
      recentTrades: [
        { time: '10/6 05:12', side: '多', price: '2,488.5', pnlPct: '-1.20%', positive: false },
        { time: '10/5 18:00', side: '多', price: '2,510.0', pnlPct: '-0.85%', positive: false }
      ]
    },
    'mochi-03': {
      id: 'mochi-03',
      name: 'Mochi',
      strategy: 'grid_mm v1.4',
      symbol: 'SOLUSDT',
      timeframe: '5m',
      state: 'running',
      lastSignal: '09:04 網格開倉',
      returnPct: '+1.77%',
      maxDrawdownPct: '-1.80%',
      winRatePct: '72%',
      guardPct: '-5.0%',
      drawdownNowPct: '-0.30%',
      drawdownRatio: 0.3 / 5.0,
      legs: [
        { symbol: 'SOLUSDT', side: '多', qty: '18.0', markPrice: '152.8', upnl: '-23.40', positive: false }
      ],
      recentTrades: [
        { time: '10/6 05:12', side: '多', price: '152.4', pnlPct: '+0.15%', positive: true }
      ]
    },
    'shiro-04': {
      id: 'shiro-04',
      name: 'Shiro',
      strategy: 'pairs_btc_eth v0.9',
      symbol: 'BTC/ETH',
      timeframe: '1h',
      state: 'paused',
      lastSignal: '10/4 16:00 平倉',
      returnPct: '-2.17%',
      maxDrawdownPct: '-4.20%',
      winRatePct: '55%',
      guardPct: '-6.0%',
      drawdownNowPct: '-3.60%',
      drawdownRatio: 3.6 / 6.0,
      legs: [
        { symbol: 'BTCUSDT', side: '多', qty: '0.05', markPrice: '62,140.5', upnl: '-37.47', positive: false },
        { symbol: 'ETHUSDT', side: '空', qty: '1.30', markPrice: '2,450.2', upnl: '-24.31', positive: false }
      ],
      recentTrades: [
        { time: '10/4 16:00', side: '空', price: '0.0388', pnlPct: '+0.40%', positive: true }
      ]
    }
  };

  selectedDrawerBot.value = mockBots[botId] || mockBots['tabby-01'];
}

function handleToggleBotPause(botId: string) {
  if (selectedDrawerBot.value && selectedDrawerBot.value.id === botId) {
    selectedDrawerBot.value.state = selectedDrawerBot.value.state === 'running' ? 'paused' : 'running';
  }
}

const currentProfile = computed(() => {
  return savedProfiles.value.find(p => p.id === currentProfileId.value) || savedProfiles.value[0];
});

// 四大標準預設版面清單
const presetLayouts = computed(() => {
  return DEFAULT_PROFILES;
});

// 全域卡片風格狀態判斷
const isAllV0 = computed(() => {
  return (
    isCardV0(bbgPanes.value.leftLower) &&
    isCardV0(bbgPanes.value.right1) &&
    isCardV0(bbgPanes.value.right2) &&
    isCardV0(bbgPanes.value.right3)
  );
});

// 全域一鍵切換卡片風格 (V0 經典 vs Astra 原版)
function toggleAllCardsVersion(targetVer: 'v0' | 'astra') {
  // ★ 定案收斂：帳戶權益 (leftUpper) 已定案 V0，不隨全域切換變動！其他 4 個尚未定案槽位隨之切換
  bbgPanes.value.leftUpper = 'v0_equity';
  const slots: ('leftLower' | 'right1' | 'right2' | 'right3')[] = ['leftLower', 'right1', 'right2', 'right3'];
  for (const s of slots) {
    const cur = bbgPanes.value[s];
    const curIsV0 = isCardV0(cur);
    if (targetVer === 'v0' && !curIsV0) {
      bbgPanes.value[s] = getTwinVersionId(cur);
    } else if (targetVer === 'astra' && curIsV0) {
      bbgPanes.value[s] = getTwinVersionId(cur);
    }
  }
  saveBlueprintLayouts();
  showToast(targetVer === 'v0' ? '已將未定案卡片切換為 V0 經典風格' : '已將未定案卡片切換為 Astra 原版風格');
}

function loadAllProfiles() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_PROFILES);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        const custom = parsed.filter((p: SavedLayoutProfile) => !p.isSystem);
        savedProfiles.value = [...DEFAULT_PROFILES, ...custom];
      }
    } else {
      savedProfiles.value = [...DEFAULT_PROFILES];
    }
    currentProfileId.value = DEFAULT_PROFILES[0].id;
    applyProfile(currentProfileId.value, false);
    // 定案收斂保證：全面固化為 V0 典範版插槽
    bbgPanes.value = {
      leftUpper: 'v0_equity',
      leftLower: 'v0_activity',
      right1: 'v0_bots',
      right2: 'v0_exposure',
      right3: 'v0_events'
    };
  } catch (e) {
    savedProfiles.value = [...DEFAULT_PROFILES];
    currentProfileId.value = DEFAULT_PROFILES[0].id;
    applyProfile(currentProfileId.value, false);
    bbgPanes.value = {
      leftUpper: 'v0_equity',
      leftLower: 'v0_activity',
      right1: 'v0_bots',
      right2: 'v0_exposure',
      right3: 'v0_events'
    };
  }
}

function saveProfilesToStorage() {
  try {
    localStorage.setItem(STORAGE_KEY_PROFILES, JSON.stringify(savedProfiles.value));
    localStorage.setItem(STORAGE_KEY_CURRENT_PROFILE, currentProfileId.value);
  } catch (e) {}
}

function applyProfile(id: string, notify = true) {
  const target = savedProfiles.value.find(p => p.id === id);
  if (!target) return;
  currentProfileId.value = id;
  activeBlueprint.value = target.blueprint;
  allocationMode.value = target.allocationMode || 'donut';
  bbgLeftColWidth.value = target.bbgLeftColWidth;
  bbgLeftUpperHeight.value = target.bbgLeftUpperHeight;
  bbgRightWeights.value = [...target.bbgRightWeights];
  bbgPanes.value = { ...target.bbgPanes };
  linearUpperHeight.value = target.linearUpperHeight;
  linearUpperLeftWidth.value = target.linearUpperLeftWidth;
  linearLowerLeftWidth.value = target.linearLowerLeftWidth;
  linearPanes.value = { ...target.linearPanes };
  saveProfilesToStorage();
  if (notify) {
    showToast(`已套用版面方案：「${target.name}」`);
  }
}

// 另存為新版面方案
const isSaveModalOpen = ref(false);
const newProfileName = ref('');

function openSaveModal() {
  newProfileName.value = `自訂方案 #${savedProfiles.value.length + 1}`;
  isSaveModalOpen.value = true;
}

function confirmSaveNewProfile() {
  const name = newProfileName.value.trim() || `自訂方案 #${savedProfiles.value.length + 1}`;
  const newId = 'profile_' + Date.now();
  const nowStr = new Date().toLocaleTimeString('zh-TW', { hour12: false });
  const profile: SavedLayoutProfile = {
    id: newId,
    name,
    isSystem: false,
    blueprint: activeBlueprint.value,
    allocationMode: allocationMode.value,
    bbgLeftColWidth: bbgLeftColWidth.value,
    bbgLeftUpperHeight: bbgLeftUpperHeight.value,
    bbgRightWeights: [...bbgRightWeights.value],
    bbgPanes: { ...bbgPanes.value },
    linearUpperHeight: linearUpperHeight.value,
    linearUpperLeftWidth: linearUpperLeftWidth.value,
    linearLowerLeftWidth: linearLowerLeftWidth.value,
    linearPanes: { ...linearPanes.value },
    updatedAt: nowStr
  };

  savedProfiles.value.push(profile);
  currentProfileId.value = newId;
  saveProfilesToStorage();
  isSaveModalOpen.value = false;
  showToast(`已成功另存新版面方案：「${name}」`);
}

function updateCurrentProfile() {
  const target = savedProfiles.value.find(p => p.id === currentProfileId.value);
  if (!target) return;
  const nowStr = new Date().toLocaleTimeString('zh-TW', { hour12: false });
  target.blueprint = activeBlueprint.value;
  target.allocationMode = allocationMode.value;
  target.bbgLeftColWidth = bbgLeftColWidth.value;
  target.bbgLeftUpperHeight = bbgLeftUpperHeight.value;
  target.bbgRightWeights = [...bbgRightWeights.value];
  target.bbgPanes = { ...bbgPanes.value };
  target.linearUpperHeight = linearUpperHeight.value;
  target.linearUpperLeftWidth = linearUpperLeftWidth.value;
  target.linearLowerLeftWidth = linearLowerLeftWidth.value;
  target.linearPanes = { ...linearPanes.value };
  target.updatedAt = nowStr;

  saveProfilesToStorage();
  showToast(`已儲存變更至方案：「${target.name}」`);
}

function deleteProfile(id: string) {
  const idx = savedProfiles.value.findIndex(p => p.id === id);
  if (idx === -1) return;
  const p = savedProfiles.value[idx];
  if (p.isSystem) {
    showToast('系統預設方案受保護，無法刪除');
    return;
  }
  savedProfiles.value.splice(idx, 1);
  if (currentProfileId.value === id) {
    currentProfileId.value = savedProfiles.value[0].id;
    applyProfile(currentProfileId.value, false);
  }
  saveProfilesToStorage();
  showToast(`已刪除自訂方案：「${p.name}」`);
}

function saveBlueprintLayouts() {
  // 自動同步更新至當前 profile
  const target = savedProfiles.value.find(p => p.id === currentProfileId.value);
  if (target && !target.isSystem) {
    updateCurrentProfile();
  } else {
    saveProfilesToStorage();
  }
}

// 1. 方案 A 垂直主分欄分割線滑動 (左右拉伸寬度，需先解鎖)
function startBbgMainColSplitDrag(e: PointerEvent) {
  if (!isEditing.value) {
    showToast('請先點擊頂部「⚙ 調整版面」解鎖後，再微調比例');
    return;
  }
  e.preventDefault();
  isSplitterDragging.value = true;
  const startX = e.clientX;
  const startPct = bbgLeftColWidth.value;
  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerWidth = container.getBoundingClientRect().width;

  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';

  let rafId: number | null = null;

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isSplitterDragging.value) return;
    if (rafId !== null) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(() => {
      const deltaX = moveEvt.clientX - startX;
      const deltaPct = (deltaX / containerWidth) * 100;
      bbgLeftColWidth.value = Math.min(82, Math.max(35, Math.round(startPct + deltaPct)));
    });
  };

  const onPointerUp = () => {
    if (rafId !== null) cancelAnimationFrame(rafId);
    isSplitterDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveBlueprintLayouts();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

// 2. 方案 A 左欄水平分割線滑動 (走勢圖 vs 持倉部位 上下拉伸高度，需先解鎖 · 120 FPS rAF 節流)
function startBbgLeftSplitDrag(e: PointerEvent) {
  if (!isEditing.value) {
    showToast('請先點擊頂部「⚙ 調整版面」解鎖後，再微調比例');
    return;
  }
  e.preventDefault();
  isSplitterDragging.value = true;
  const startY = e.clientY;
  const startPct = bbgLeftUpperHeight.value;
  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerHeight = container.getBoundingClientRect().height;

  document.body.style.cursor = 'row-resize';
  document.body.style.userSelect = 'none';

  let rafId: number | null = null;

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isSplitterDragging.value) return;
    if (rafId !== null) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(() => {
      const deltaY = moveEvt.clientY - startY;
      const deltaPct = (deltaY / containerHeight) * 100;
      bbgLeftUpperHeight.value = Math.min(75, Math.max(25, Math.round(startPct + deltaPct)));
    });
  };

  const onPointerUp = () => {
    if (rafId !== null) cancelAnimationFrame(rafId);
    isSplitterDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveBlueprintLayouts();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

// 3. 方案 A 右欄水平分割線滑動 (Bot / Donut / Events，需先解鎖 · 120 FPS rAF 節流)
function startBbgRightSplitDrag(index: number, e: PointerEvent) {
  if (!isEditing.value) {
    showToast('請先點擊頂部「⚙ 調整版面」解鎖後，再微調比例');
    return;
  }
  e.preventDefault();
  isSplitterDragging.value = true;
  const startY = e.clientY;
  const initWeights = [...bbgRightWeights.value];
  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerHeight = container.getBoundingClientRect().height;

  document.body.style.cursor = 'row-resize';
  document.body.style.userSelect = 'none';

  let rafId: number | null = null;

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isSplitterDragging.value) return;
    if (rafId !== null) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(() => {
      const deltaY = moveEvt.clientY - startY;
      const deltaPct = (deltaY / containerHeight) * 100;
      const topIdx = index;
      const btmIdx = index + 1;

      const current = [...initWeights];
      const maxDelta = current[btmIdx] - 20;
      const minDelta = -(current[topIdx] - 20);
      const clampedDelta = Math.min(maxDelta, Math.max(minDelta, deltaPct));

      current[topIdx] += clampedDelta;
      current[btmIdx] -= clampedDelta;
      bbgRightWeights.value = current.map(w => Math.round(w));
    });
  };

  const onPointerUp = () => {
    if (rafId !== null) cancelAnimationFrame(rafId);
    isSplitterDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveBlueprintLayouts();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

// 4. 方案 B 上下排水平分割線滑動 (需先解鎖)
function startLinearRowSplitDrag(e: PointerEvent) {
  if (!isEditing.value) {
    showToast('請先點擊頂部「⚙ 調整版面」解鎖後，再微調比例');
    return;
  }
  e.preventDefault();
  isSplitterDragging.value = true;
  const startY = e.clientY;
  const startPct = linearUpperHeight.value;
  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerHeight = container.getBoundingClientRect().height;

  document.body.style.cursor = 'row-resize';
  document.body.style.userSelect = 'none';

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isSplitterDragging.value) return;
    const deltaY = moveEvt.clientY - startY;
    const deltaPct = (deltaY / containerHeight) * 100;
    linearUpperHeight.value = Math.min(75, Math.max(28, Math.round(startPct + deltaPct)));
  };

  const onPointerUp = () => {
    isSplitterDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveBlueprintLayouts();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

// 5. 方案 B 上排左右垂直分割線滑動 (需先解鎖)
function startLinearUpperColSplitDrag(e: PointerEvent) {
  if (!isEditing.value) {
    showToast('請先點擊頂部「⚙ 調整版面」解鎖後，再微調比例');
    return;
  }
  e.preventDefault();
  isSplitterDragging.value = true;
  const startX = e.clientX;
  const startPct = linearUpperLeftWidth.value;
  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerWidth = container.getBoundingClientRect().width;

  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isSplitterDragging.value) return;
    const deltaX = moveEvt.clientX - startX;
    const deltaPct = (deltaX / containerWidth) * 100;
    linearUpperLeftWidth.value = Math.min(80, Math.max(35, Math.round(startPct + deltaPct)));
  };

  const onPointerUp = () => {
    isSplitterDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveBlueprintLayouts();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

// 6. 方案 B 下排左右垂直分割線滑動 (需先解鎖)
function startLinearLowerColSplitDrag(e: PointerEvent) {
  if (!isEditing.value) {
    showToast('請先點擊頂部「⚙ 調整版面」解鎖後，再微調比例');
    return;
  }
  e.preventDefault();
  isSplitterDragging.value = true;
  const startX = e.clientX;
  const startPct = linearLowerLeftWidth.value;
  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerWidth = container.getBoundingClientRect().width;

  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isSplitterDragging.value) return;
    const deltaX = moveEvt.clientX - startX;
    const deltaPct = (deltaX / containerWidth) * 100;
    linearLowerLeftWidth.value = Math.min(80, Math.max(35, Math.round(startPct + deltaPct)));
  };

  const onPointerUp = () => {
    isSplitterDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveBlueprintLayouts();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

// 快速雙擊還原預設黃金比例 (60:40 舒展四分割定案)
function resetBbgSplits() {
  bbgLeftColWidth.value = 60;
  bbgLeftUpperHeight.value = 50;
  bbgRightWeights.value = [50, 50, 0];
  saveBlueprintLayouts();
  showToast('已還原 60:40 舒展四分割定案比例 (左 60% / 右 40%)');
}

function resetLinearSplits() {
  linearUpperHeight.value = 50;
  linearUpperLeftWidth.value = 64;
  linearLowerLeftWidth.value = 60;
  saveBlueprintLayouts();
  showToast('已還原 Linear 雙排黃金比例 (上下 50% 平衡)');
}

// 方案專屬卡片標題拖曳換位 (按住標題 Grip ⋮⋮ 即可與目標卡片對調，需先解鎖)
const activeDragSourceSlot = ref<string | null>(null);
const hoverDropTargetSlot = ref<string | null>(null);

function startSlotCardDrag(slotKey: string, e: MouseEvent) {
  if (e.button !== 0) return;
  if (!isEditing.value) {
    showToast('請先點擊頂部「⚙ 調整版面」解鎖後，再拖曳更換卡片位置');
    return;
  }
  if ((e.target as HTMLElement).closest('button, a, input, select, .toolbar-range-picker')) return;

  e.preventDefault();
  activeDragSourceSlot.value = slotKey;
  isCardDragging.value = true;
  document.body.style.cursor = 'grabbing';
  document.body.style.userSelect = 'none';

  const onMouseMove = (moveEvt: MouseEvent) => {
    ghostPosition.value = { x: moveEvt.clientX, y: moveEvt.clientY };
  };

  const onMouseUp = () => {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    isCardDragging.value = false;

    if (activeDragSourceSlot.value && hoverDropTargetSlot.value && activeDragSourceSlot.value !== hoverDropTargetSlot.value) {
      swapCardSlots(activeDragSourceSlot.value, hoverDropTargetSlot.value);
    }

    activeDragSourceSlot.value = null;
    hoverDropTargetSlot.value = null;
    ghostPosition.value = null;
  };

  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
}

function swapCardSlots(slotA: string, slotB: string) {
  if (activeBlueprint.value === 'bloomberg') {
    const cur = { ...bbgPanes.value };
    const temp = (cur as any)[slotA];
    (cur as any)[slotA] = (cur as any)[slotB];
    (cur as any)[slotB] = temp;
    bbgPanes.value = cur;
    saveBlueprintLayouts();
    showToast('卡片位置已成功對調');
  } else if (activeBlueprint.value === 'linear') {
    const cur = { ...linearPanes.value };
    const temp = (cur as any)[slotA];
    (cur as any)[slotA] = (cur as any)[slotB];
    (cur as any)[slotB] = temp;
    linearPanes.value = cur;
    saveBlueprintLayouts();
    showToast('卡片位置已成功對調');
  }
}

// 事件異常感知（專業金融終端標準：無數字、雙色分級微光指示）
const anomalyCount = computed(() => {
  return auditEvents.value.filter(e =>
    e.level === 'WARN' ||
    e.level === 'ERROR' ||
    e.category === 'RISK' ||
    e.category === 'ORDER'
  ).length;
});

// 嚴重度感知 (none: 正常健康, warn: 一般警告-琥珀金, critical: 致命阻斷-珊瑚紅呼吸微光)
const effectiveSeverity = computed<'none' | 'warn' | 'critical'>(() => {
  if (anomalyCount.value === 0) return 'none';
  const hasCritical = auditEvents.value.some(e =>
    e.level === 'ERROR' || e.category === 'RISK' || (riskState.value && riskState.value.status.includes('latch'))
  );
  return hasCritical ? 'critical' : 'warn';
});

const hasAnomaly = computed(() => effectiveSeverity.value !== 'none');

// 事件串流過濾：全部流水 vs 僅異常/風控阻斷
const filteredAuditEvents = computed(() => {
  if (eventFilterMode.value === 'old') {
    return auditEvents.value;
  }
  return auditEvents.value.filter(e =>
    e.level === 'WARN' ||
    e.level === 'ERROR' ||
    e.category === 'RISK' ||
    e.category === 'ORDER'
  );
});

// 市場情報：持倉雷達 vs 全部市場
const filteredMarketAlerts = computed(() => {
  const posSymbols = ['BTC', 'ETH', 'SOL'];
  const mapped = yaoziAlerts.value.map(a => {
    const isRelated = posSymbols.some(s => a.title.toUpperCase().includes(s) || a.summary.toUpperCase().includes(s));
    return {
      ...a,
      isHoldingRelated: isRelated
    };
  });
  if (marketIntelMode.value === 'all') return mapped;
  const holdingOnly = mapped.filter(a => a.isHoldingRelated);
  // 若持倉標的暫無快訊，展示宏觀大盤動態並保持不空
  return holdingOnly.length > 0 ? holdingOnly : mapped;
});

const riskBadgeText = computed(() => {
  if (!riskState.value || riskState.value.status === 'missing') return 'STATUS: UNAVAILABLE';
  if (riskState.value.status === 'normal') return 'LATCH: DISARMED';
  if (riskState.value.status === 'soft_latch') return 'SOFT LATCHED (-10%)';
  if (riskState.value.status === 'hard_latch') return 'HARD LATCHED (-20%)';
  return 'STATUS: UNKNOWN';
});

const riskBadgeClass = computed(() => {
  if (!riskState.value || riskState.value.status === 'missing') return 'badge-danger';
  if (riskState.value.status === 'normal') return 'badge-success';
  if (riskState.value.status === 'soft_latch') return 'badge-warning';
  if (riskState.value.status === 'hard_latch') return 'badge-danger';
  return 'badge-neutral';
});

const getIntelTagClass = (type: string) => {
  if (type.includes('費率') || type.includes('偏離')) return 'tag-rate';
  if (type.includes('巨鯨') || type.includes('異動')) return 'tag-whale';
  if (type.includes('鏈上') || type.includes('活躍')) return 'tag-chain';
  return 'tag-macro';
};

const router = useRouter();
function navigateToLogs() {
  router.push('/logs');
}
function navigateToBots() {
  router.push('/bots');
}

const expandedEventId = ref<string | null>(null);
function toggleEvent(id: string) {
  expandedEventId.value = expandedEventId.value === id ? null : id;
}

// 1. Dual-Mode State: View Mode (Locked) vs. Edit Mode (Unlocked)
const isEditing = ref(
  typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('edit') === 'true'
);
const isDrawerOpen = ref(false);

type PresetKey = 'executive';

interface WidgetMeta {
  id: string;
  title: string;
  en: string;
}

const WIDGETS_META: Record<string, WidgetMeta> = {
  equity: { id: 'equity', title: '帳戶權益追蹤', en: 'EQUITY TRACKING' },
  donut: { id: 'donut', title: '資產曝險配置', en: 'EXPOSURE ALLOCATION' },
  events: { id: 'events', title: '系統日誌動態', en: 'SYSTEM LOG STREAM' },
  risk: { id: 'risk', title: '帳戶風控指標', en: 'RISK CONTROL METRICS' },
  bots: { id: 'bots', title: '量化BOT動態', en: 'QUANT BOT ACTIVITY' },
  positions: { id: 'positions', title: '即時持倉部位', en: 'LIVE POSITIONS' },
  yaozi: { id: 'yaozi', title: '市場情報', en: 'MARKET INTEL' }
};

interface PresetDefinition {
  label: string;
  desc: string;
  upperPanes: string[];
  lowerPanes: string[];
  upperWeights?: number[];
  lowerWeights?: number[];
  upperHeightPct: number;
}

const presetsMap: Record<PresetKey, PresetDefinition> = {
  executive: {
    label: '戰情總覽 (Executive Desk)',
    desc: '標準均勻平衡 · 走勢圖與資產分佈並重 · 適合日常綜合盯盤',
    upperPanes: ['equity', 'donut', 'events'],
    lowerPanes: ['risk', 'bots', 'positions', 'yaozi'],
    upperWeights: [44, 25, 31],
    lowerWeights: [24, 34, 24, 18],
    upperHeightPct: 56
  }
};

const STORAGE_KEY_HYBRID = 'catos_hybrid_workspace_v1';

type KpiScheme = 'hud' | 'universal' | 'compact';

const KPI_META: Record<string, WidgetMeta> = {
  kpi_equity: { id: 'kpi_equity', title: '總權益淨值', en: 'TOTAL EQUITY' },
  kpi_pnl: { id: 'kpi_pnl', title: '今日損益', en: 'TODAY PNL' },
  kpi_bots: { id: 'kpi_bots', title: '部署機器人', en: 'DEPLOYED BOTS' },
  kpi_risk: { id: 'kpi_risk', title: '風控狀態', en: 'RISK STATUS' }
};

const ALL_WIDGETS_META = computed<Record<string, WidgetMeta>>(() => ({
  ...WIDGETS_META,
  ...KPI_META
}));

const kpiPropsMap = computed<Record<string, { label: string; value: string; unit?: string; subText?: string; subType?: 'pos' | 'neg' | 'neutral'; borderType?: 'accent' | 'warning' | 'danger' | 'success'; isEquity?: boolean }>>(() => ({
  kpi_equity: {
    label: '總權益淨值',
    value: isUnavailable.value ? '— USDT' : (kpis.value?.total_equity ? kpis.value.total_equity + ' USDT' : '--'),
    subText: isUnavailable.value ? '服務離線 · 無法讀取' : ('實時持倉估值 + 現金餘額 (' + (kpis.value?.equity_change_pct || '0.00%') + ')'),
    subType: isUnavailable.value ? 'neg' : 'pos',
    borderType: isUnavailable.value ? 'danger' : 'accent',
    isEquity: true
  },
  kpi_pnl: {
    label: '今日損益',
    value: isUnavailable.value ? '— USDT' : (kpis.value?.today_pnl ? kpis.value.today_pnl + ' USDT' : '--'),
    subText: isUnavailable.value ? '未知損益 · 需核對基線' : ('已實現 + 未實現浮動 (' + (kpis.value?.today_pnl_pct || '0.00%') + ')'),
    subType: isUnavailable.value ? 'neg' : ((kpis.value?.today_pnl?.startsWith('+')) ? 'pos' : 'neg'),
    borderType: isUnavailable.value ? 'danger' : ((kpis.value?.today_pnl?.startsWith('+')) ? 'success' : 'danger')
  },
  kpi_bots: {
    label: '部署機器人',
    value: isUnavailable.value ? '— / —' : (kpis.value ? `${kpis.value.running_bots_count} / ${kpis.value.total_bots_count}` : '--'),
    unit: '個策略實例',
    subText: isUnavailable.value ? '服務離線' : (kpis.value?.bots_summary_note || '無部署'),
    borderType: isUnavailable.value ? 'danger' : 'accent'
  },
  kpi_risk: {
    label: '風控狀態',
    value: isUnavailable.value ? 'UNAVAILABLE' : (kpis.value?.risk_status || 'UNKNOWN'),
    unit: isUnavailable.value ? '503 離線' : (kpis.value?.effective_leverage ? `${kpis.value.effective_leverage}x / 上限 ${kpis.value.leverage_limit}x` : ''),
    subText: isUnavailable.value ? '服務不可用 · 禁止增倉' : (kpis.value?.risk_sub_note || '狀態未知'),
    borderType: isUnavailable.value ? 'danger' : (kpis.value?.risk_status === 'NORMAL' ? 'accent' : 'warning')
  }
}));

interface StoredTierLayout {
  preset: PresetKey;
  topPanes: string[];
  topWeights: number[];
  topHeightPct: number;
  upperPanes: string[];
  lowerPanes: string[];
  hiddenPanes: string[];
  upperWeights: number[];
  lowerWeights: number[];
  upperHeightPct: number;
}

function loadStoredLayout(): StoredTierLayout {
  const defaultTopPanes = ['kpi_equity', 'kpi_pnl', 'kpi_bots', 'kpi_risk'];
  const p = presetsMap.executive;
  try {
    const raw = localStorage.getItem(STORAGE_KEY_HYBRID);
    if (!raw) {
      return {
        preset: 'executive',
        topPanes: [...defaultTopPanes],
        topWeights: [25, 25, 25, 25],
        topHeightPct: 22,
        upperPanes: [...p.upperPanes],
        lowerPanes: [...p.lowerPanes],
        hiddenPanes: [],
        upperWeights: p.upperWeights ? [...p.upperWeights] : [48, 28, 24],
        lowerWeights: p.lowerWeights ? [...p.lowerWeights] : [32, 23, 23, 22],
        upperHeightPct: p.upperHeightPct
      };
    }
    const parsed = JSON.parse(raw);
    const validPreset: PresetKey = 'executive';

    // Deduplication safeguard: Ensure each widget ID exists AT MOST ONCE across all tiers
    const seenIds = new Set<string>();
    const dedupeTier = (panes: any, weights: any, fallback: string[]): { panes: string[]; weights: number[] } => {
      const src = Array.isArray(panes) && panes.length > 0 ? panes : fallback;
      const cleanPanes: string[] = [];
      const cleanWeights: number[] = [];
      for (let i = 0; i < src.length; i++) {
        const id = src[i];
        if (typeof id === 'string' && id && !seenIds.has(id)) {
          seenIds.add(id);
          cleanPanes.push(id);
          if (Array.isArray(weights) && typeof weights[i] === 'number') {
            cleanWeights.push(weights[i]);
          }
        }
      }
      const len = cleanPanes.length || 1;
      const finalWeights = cleanWeights.length === cleanPanes.length
        ? cleanWeights
        : cleanPanes.map(() => Math.round(100 / len));
      return { panes: cleanPanes, weights: finalWeights };
    };

    const top = dedupeTier(parsed.topPanes || parsed.kpiPanes, parsed.topWeights || parsed.kpiWeights, defaultTopPanes);
    const upper = dedupeTier(parsed.upperPanes, parsed.upperWeights, presetsMap[validPreset].upperPanes);
    const lower = dedupeTier(parsed.lowerPanes, parsed.lowerWeights, presetsMap[validPreset].lowerPanes);
    const hidden = Array.isArray(parsed.hiddenPanes) ? parsed.hiddenPanes.filter((id: string) => !seenIds.has(id)) : [];

    // 若歷史快照中尚未納入 positions 卡片，自動平滑注入 lowerPanes
    if (!seenIds.has('positions') && !hidden.includes('positions')) {
      const botsIdx = lower.panes.indexOf('bots');
      if (botsIdx !== -1) {
        lower.panes.splice(botsIdx + 1, 0, 'positions');
      } else {
        lower.panes.push('positions');
      }
      const len = lower.panes.length;
      lower.weights = lower.panes.map(() => Math.round(100 / len));
      seenIds.add('positions');
    }

    // 依指令徹底濾除 research 研究任務卡片
    const stripResearch = (tierObj: { panes: string[]; weights: number[] }) => {
      const idx = tierObj.panes.indexOf('research');
      if (idx !== -1) {
        tierObj.panes.splice(idx, 1);
        const len = tierObj.panes.length || 1;
        tierObj.weights = tierObj.panes.map(() => Math.round(100 / len));
      }
    };
    stripResearch(lower);
    stripResearch(upper);
    stripResearch(top);

    return {
      preset: validPreset,
      topPanes: top.panes,
      topWeights: top.weights,
      topHeightPct: typeof parsed.topHeightPct === 'number' ? parsed.topHeightPct : 22,
      upperPanes: upper.panes,
      lowerPanes: lower.panes,
      hiddenPanes: hidden,
      upperWeights: upper.weights,
      lowerWeights: lower.weights,
      upperHeightPct: typeof parsed.upperHeightPct === 'number' ? parsed.upperHeightPct : 56
    };
  } catch {
    return {
      preset: 'executive',
      topPanes: [...defaultTopPanes],
      topWeights: [25, 25, 25, 25],
      topHeightPct: 22,
      upperPanes: [...p.upperPanes],
      lowerPanes: [...p.lowerPanes],
      hiddenPanes: [],
      upperWeights: [48, 28, 24],
      lowerWeights: [32, 23, 23, 22],
      upperHeightPct: 56
    };
  }
}

const layout = ref<StoredTierLayout>(loadStoredLayout());
const activePreset = ref<PresetKey>(layout.value.preset);

function saveLayout() {
  try {
    layout.value.preset = activePreset.value;
    localStorage.setItem(STORAGE_KEY_HYBRID, JSON.stringify(layout.value));
  } catch {}
}

// Undo Stack (15 levels)
const undoStack = ref<string[]>([]);
function pushHistory() {
  const snapshot = JSON.stringify(layout.value);
  if (undoStack.value.length === 0 || undoStack.value[undoStack.value.length - 1] !== snapshot) {
    undoStack.value.push(snapshot);
    if (undoStack.value.length > 15) undoStack.value.shift();
  }
}

function undo() {
  if (undoStack.value.length > 1) {
    undoStack.value.pop();
    const prev = undoStack.value[undoStack.value.length - 1];
    if (prev) {
      layout.value = JSON.parse(prev);
      saveLayout();
      showToast('已復原上一步版面狀態');
    }
  }
}

function applyPreset(key: PresetKey = 'executive') {
  pushHistory();
  activePreset.value = key;
  const p = presetsMap[key];
  const defaultTopPanes = ['kpi_equity', 'kpi_pnl', 'kpi_bots', 'kpi_risk'];
  layout.value = {
    preset: key,
    topPanes: layout.value.topPanes && layout.value.topPanes.length > 0 ? [...layout.value.topPanes] : [...defaultTopPanes],
    topWeights: layout.value.topWeights && layout.value.topWeights.length === (layout.value.topPanes?.length || 4)
      ? [...layout.value.topWeights]
      : [25, 25, 25, 25],
    topHeightPct: typeof layout.value.topHeightPct === 'number' ? layout.value.topHeightPct : 22,
    upperPanes: [...p.upperPanes],
    lowerPanes: [...p.lowerPanes],
    hiddenPanes: [],
    upperWeights: p.upperWeights ? [...p.upperWeights] : p.upperPanes.map(() => 100 / p.upperPanes.length),
    lowerWeights: p.lowerWeights ? [...p.lowerWeights] : p.lowerPanes.map(() => 100 / p.lowerPanes.length),
    upperHeightPct: p.upperHeightPct
  };
  saveLayout();
  showToast(`已套用 [${p.label.split(' ')[0]}] 實戰預設`);
}

function resetCurrentPreset() {
  applyPreset(activePreset.value);
}

// Toast notification
const toastMessage = ref<string | null>(null);
let toastTimer: any = null;
function showToast(msg: string) {
  toastMessage.value = msg;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastMessage.value = null;
  }, 2000);
}

// Micro-animation for recently landed card
const landedId = ref<string | null>(null);
function triggerLandAnimation(id: string) {
  landedId.value = id;
  setTimeout(() => {
    if (landedId.value === id) landedId.value = null;
  }, 600);
}

// Auto-Pack logic
function autoPack() {
  pushHistory();
  if (layout.value.topPanes && layout.value.topPanes.length > 0) {
    const topLen = layout.value.topPanes.length;
    layout.value.topWeights = layout.value.topPanes.map(() => Math.round(100 / topLen));
  }
  const upLen = layout.value.upperPanes.length;
  if (upLen === 2) layout.value.upperWeights = [66, 34];
  else if (upLen === 3) layout.value.upperWeights = [48, 28, 24];
  else layout.value.upperWeights = layout.value.upperPanes.map(() => Math.round(100 / upLen));

  const lowLen = layout.value.lowerPanes.length;
  layout.value.lowerWeights = layout.value.lowerPanes.map(() => Math.round(100 / lowLen));
  layout.value.topHeightPct = 22;
  layout.value.upperHeightPct = 56;
  saveLayout();
  showToast('⚡ 已一鍵自動補滿 100% 無縫平衡比例');
}

// Hide and Restore Widgets
function getWidgetMeta(id: string): WidgetMeta {
  return ALL_WIDGETS_META.value[id] || { id, title: id, en: id.toUpperCase() };
}

function hidePane(id: string) {
  pushHistory();
  let found = false;
  if (layout.value.topPanes) {
    const topIdx = layout.value.topPanes.indexOf(id);
    if (topIdx !== -1) {
      layout.value.topPanes.splice(topIdx, 1);
      if (layout.value.topWeights) layout.value.topWeights.splice(topIdx, 1);
      found = true;
    }
  }
  const upIdx = layout.value.upperPanes.indexOf(id);
  if (upIdx !== -1) {
    layout.value.upperPanes.splice(upIdx, 1);
    layout.value.upperWeights.splice(upIdx, 1);
    found = true;
  }
  const lowIdx = layout.value.lowerPanes.indexOf(id);
  if (lowIdx !== -1) {
    layout.value.lowerPanes.splice(lowIdx, 1);
    layout.value.lowerWeights.splice(lowIdx, 1);
    found = true;
  }
  if (found) {
    if (!layout.value.hiddenPanes.includes(id)) {
      layout.value.hiddenPanes.push(id);
    }
    normalizeWeights();
    saveLayout();
    showToast(`已隱藏 [${getWidgetMeta(id).title}]`);
  }
}

function restorePane(id: string) {
  pushHistory();
  const hIdx = layout.value.hiddenPanes.indexOf(id);
  if (hIdx !== -1) {
    layout.value.hiddenPanes.splice(hIdx, 1);
  }
  // Defensive deduplication: ensure removed from any tier first
  const removeId = (list?: string[], weights?: number[]) => {
    if (!list) return;
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i] === id) {
        list.splice(i, 1);
        if (weights && weights.length > i) weights.splice(i, 1);
      }
    }
  };
  removeId(layout.value.topPanes, layout.value.topWeights);
  removeId(layout.value.upperPanes, layout.value.upperWeights);
  removeId(layout.value.lowerPanes, layout.value.lowerWeights);

  if (id.startsWith('kpi_')) {
    if (!layout.value.topPanes) layout.value.topPanes = [];
    layout.value.topPanes.push(id);
  } else {
    layout.value.lowerPanes.push(id);
  }
  normalizeWeights();
  saveLayout();
  triggerLandAnimation(id);
  showToast(`已恢復 [${getWidgetMeta(id).title}]`);
}

function toggleWidgetVisibility(id: string) {
  if (layout.value.hiddenPanes.includes(id)) {
    restorePane(id);
  } else {
    hidePane(id);
  }
}

function normalizeWeights() {
  if (layout.value.topPanes && layout.value.topPanes.length > 0) {
    if (!layout.value.topWeights || layout.value.topWeights.length !== layout.value.topPanes.length) {
      layout.value.topWeights = layout.value.topPanes.map(() => Math.round(100 / layout.value.topPanes!.length));
    }
  }
  const upLen = layout.value.upperPanes.length;
  if (upLen > 0) {
    if (!layout.value.upperWeights || layout.value.upperWeights.length !== upLen) {
      layout.value.upperWeights = layout.value.upperPanes.map(() => Math.round(100 / upLen));
    }
  }
  const lowLen = layout.value.lowerPanes.length;
  if (lowLen > 0) {
    if (!layout.value.lowerWeights || layout.value.lowerWeights.length !== lowLen) {
      layout.value.lowerWeights = layout.value.lowerPanes.map(() => Math.round(100 / lowLen));
    }
  }
}

// 2. Continuous Splitters Dragging Engine (Horizontal & Vertical)
const isSplitterDragging = ref(false);

function startHorizontalSplitDrag(e: PointerEvent) {
  e.preventDefault();
  isSplitterDragging.value = true;
  const startY = e.clientY;
  const startPct = layout.value.upperHeightPct;
  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerHeight = container.getBoundingClientRect().height;

  document.body.style.cursor = 'row-resize';
  document.body.style.userSelect = 'none';

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isSplitterDragging.value) return;
    const deltaY = moveEvt.clientY - startY;
    const deltaPct = (deltaY / containerHeight) * 100;
    const newPct = Math.min(80, Math.max(25, Math.round(startPct + deltaPct)));
    layout.value.upperHeightPct = newPct;
  };

  const onPointerUp = () => {
    isSplitterDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveLayout();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

function resetHorizontalSplit() {
  layout.value.upperHeightPct = 56;
  saveLayout();
  showToast('已還原上/下排平衡比例 (56% / 44%)');
}

function startTopHorizontalSplitDrag(e: PointerEvent) {
  e.preventDefault();
  isSplitterDragging.value = true;
  const startY = e.clientY;
  const startPct = layout.value.topHeightPct || 22;
  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerHeight = container.getBoundingClientRect().height;

  document.body.style.cursor = 'row-resize';
  document.body.style.userSelect = 'none';

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isSplitterDragging.value) return;
    const deltaY = moveEvt.clientY - startY;
    const deltaPct = (deltaY / containerHeight) * 100;
    const newPct = Math.min(45, Math.max(15, Math.round(startPct + deltaPct)));
    layout.value.topHeightPct = newPct;
  };

  const onPointerUp = () => {
    isSplitterDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveLayout();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

function resetTopHorizontalSplit() {
  layout.value.topHeightPct = 22;
  saveLayout();
  showToast('已還原頂排高度比例 (22%)');
}

function startTierVerticalSplitDrag(tierName: 'top' | 'upper' | 'lower', index: number, e: PointerEvent) {
  e.preventDefault();
  isSplitterDragging.value = true;
  const startX = e.clientX;
  const initWeights = tierName === 'top'
    ? [...(layout.value.topWeights || [])]
    : tierName === 'upper'
    ? [...layout.value.upperWeights]
    : [...layout.value.lowerWeights];
  const numPanes = initWeights.length;
  if (numPanes < 2) return;

  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerWidth = container.getBoundingClientRect().width;

  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';

  // Dynamic safe minimum weight percentage per pane (e.g. 6% for 5 panes, 12% for 2 panes)
  const minWeight = Math.max(6, Math.floor(100 / (numPanes * 2.8)));

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isSplitterDragging.value) return;
    const deltaX = moveEvt.clientX - startX;
    const deltaPct = (deltaX / containerWidth) * 100;
    const leftIdx = index;
    const rightIdx = index + 1;

    const currentWeights = [...initWeights];

    if (deltaPct > 0) {
      // Dragging Right: Expand left card, shrink right cards cascadingly
      let availableRightToShrink = 0;
      for (let r = rightIdx; r < numPanes; r++) {
        availableRightToShrink += Math.max(0, currentWeights[r] - minWeight);
      }
      const actualDelta = Math.min(deltaPct, availableRightToShrink);

      let remainingDelta = actualDelta;
      for (let r = rightIdx; r < numPanes && remainingDelta > 0; r++) {
        const shrinkable = Math.max(0, currentWeights[r] - minWeight);
        const take = Math.min(shrinkable, remainingDelta);
        currentWeights[r] -= take;
        remainingDelta -= take;
      }
      currentWeights[leftIdx] += actualDelta;
    } else if (deltaPct < 0) {
      // Dragging Left: Expand right card, shrink left cards cascadingly
      const needToShrinkLeft = Math.abs(deltaPct);
      let availableLeftToShrink = 0;
      for (let l = leftIdx; l >= 0; l--) {
        availableLeftToShrink += Math.max(0, currentWeights[l] - minWeight);
      }
      const actualDelta = Math.min(needToShrinkLeft, availableLeftToShrink);

      let remainingDelta = actualDelta;
      for (let l = leftIdx; l >= 0 && remainingDelta > 0; l--) {
        const shrinkable = Math.max(0, currentWeights[l] - minWeight);
        const take = Math.min(shrinkable, remainingDelta);
        currentWeights[l] -= take;
        remainingDelta -= take;
      }
      currentWeights[rightIdx] += actualDelta;
    }

    // Strict 100% normalization: prevents any width overflow or cutoff on the rightmost card
    const sum = currentWeights.reduce((a, b) => a + b, 0);
    const normalized = currentWeights.map(w => Number(((w / sum) * 100).toFixed(2)));

    if (tierName === 'top') {
      layout.value.topWeights = normalized;
    } else if (tierName === 'upper') {
      layout.value.upperWeights = normalized;
    } else {
      layout.value.lowerWeights = normalized;
    }
  };

  const onPointerUp = () => {
    isSplitterDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveLayout();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

function resetTierVerticalSplits(tierName: 'top' | 'upper' | 'lower') {
  if (tierName === 'top') {
    const len = layout.value.topPanes?.length || 4;
    layout.value.topWeights = (layout.value.topPanes || []).map(() => Math.round(100 / len));
  } else if (tierName === 'upper') {
    const len = layout.value.upperPanes.length;
    layout.value.upperWeights = layout.value.upperPanes.map(() => Math.round(100 / len));
  } else {
    const len = layout.value.lowerPanes.length;
    layout.value.lowerWeights = layout.value.lowerPanes.map(() => Math.round(100 / len));
  }
  saveLayout();
  showToast(`已還原${tierName === 'top' ? '頂排' : tierName === 'upper' ? '上排' : '下排'}卡片均分比例`);
}

// 3. Card Header Drag-to-Reorder Engine (Finalized Scheme 1: Dynamic Ghost Slot Tile)
const isCardDragging = ref(false);
const draggedCardId = ref<string | null>(null);
const ghostPosition = ref<{ x: number; y: number } | null>(null);

interface DropTargetInfo {
  tier: 'top' | 'upper' | 'lower';
  index: number;
  targetPaneId?: string;
}
const dropTargetInfo = ref<DropTargetInfo | null>(null);

const previewDrag = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('previewDrag') === 'true';
if (previewDrag) {
  isEditing.value = true;
  isCardDragging.value = true;
  draggedCardId.value = 'bots';
  ghostPosition.value = { x: 760, y: 340 };
  dropTargetInfo.value = { tier: 'upper', index: 1, targetPaneId: 'donut' };
}

function startCardDrag(widgetId: string, e: MouseEvent) {
  if (!isEditing.value) return;
  if (e.button !== 0) return;
  // Ignore clicks on buttons/inputs
  if ((e.target as HTMLElement).closest('button, a, input, select, .btn-pane-action, .btn-tool')) return;

  e.preventDefault();
  const startX = e.clientX;
  const startY = e.clientY;
  let active = false;

  const onMouseMove = (moveEvt: MouseEvent) => {
    const dist = Math.hypot(moveEvt.clientX - startX, moveEvt.clientY - startY);
    if (!active && dist > 4) {
      active = true;
      isCardDragging.value = true;
      draggedCardId.value = widgetId;
      document.body.classList.add('is-card-dragging-active');
      pushHistory();
    }

    if (active) {
      moveEvt.preventDefault();
      ghostPosition.value = { x: moveEvt.clientX, y: moveEvt.clientY };
      detectHoverDrop(moveEvt.clientX, moveEvt.clientY, widgetId);
    }
  };

  const onMouseUp = () => {
    window.removeEventListener('mousemove', onMouseMove);
    window.removeEventListener('mouseup', onMouseUp);
    document.body.classList.remove('is-card-dragging-active');

    if (active) {
      if (dropTargetInfo.value) {
        executeCardDrop(widgetId, dropTargetInfo.value);
      }
    }

    isCardDragging.value = false;
    draggedCardId.value = null;
    ghostPosition.value = null;
    dropTargetInfo.value = null;
  };

  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
}

function detectHoverDrop(clientX: number, clientY: number, _srcId: string) {
  // 1. Identify which Tier the cursor is in vertically (with hysteresis / seamless boundaries)
  const topEl = document.getElementById('tiling-top-tier');
  const upperEl = document.getElementById('tiling-upper-tier');
  const lowerEl = document.getElementById('tiling-lower-tier');

  const tiers: { name: 'top' | 'upper' | 'lower'; el: HTMLElement | null; panes: string[] }[] = [
    { name: 'top', el: topEl, panes: layout.value.topPanes || [] },
    { name: 'upper', el: upperEl, panes: layout.value.upperPanes || [] },
    { name: 'lower', el: lowerEl, panes: layout.value.lowerPanes || [] }
  ];

  let matchedTier: { name: 'top' | 'upper' | 'lower'; el: HTMLElement; panes: string[] } | null = null;

  for (const t of tiers) {
    if (!t.el) continue;
    const r = t.el.getBoundingClientRect();
    // Expand vertical boundary slightly (+/- 6px) to cover splitter gaps seamlessly
    if (clientY >= r.top - 6 && clientY <= r.bottom + 6) {
      matchedTier = { name: t.name, el: t.el, panes: t.panes };
      break;
    }
  }

  if (!matchedTier) {
    dropTargetInfo.value = null;
    return;
  }

  const { name: tierName, el: tierEl, panes } = matchedTier;
  const numPanes = panes.length;

  if (numPanes === 0) {
    dropTargetInfo.value = { tier: tierName, index: 0 };
    return;
  }

  // 2. Query each pane's exact DOM element by ID (ignoring any transient ghost-slot-tile elements)
  interface PaneCardInfo {
    id: string;
    idx: number;
    rect: DOMRect;
    midX: number;
  }
  const paneCards: PaneCardInfo[] = [];

  for (let i = 0; i < numPanes; i++) {
    const pId = panes[i];
    const paneEl = tierEl.querySelector<HTMLElement>(`#pane-${pId}`);
    if (paneEl) {
      const r = paneEl.getBoundingClientRect();
      paneCards.push({
        id: pId,
        idx: i,
        rect: r,
        midX: r.left + r.width / 2
      });
    }
  }

  if (paneCards.length === 0) {
    dropTargetInfo.value = { tier: tierName, index: 0 };
    return;
  }

  // 3. Continuous Voronoi Partition along horizontal axis (Zero Dead-zones, Zero Jumping to Rightmost)
  // Check if cursor is to the left of the first card's midpoint: always drop at index 0
  if (clientX < paneCards[0].midX) {
    dropTargetInfo.value = {
      tier: tierName,
      index: 0,
      targetPaneId: paneCards[0].id
    };
    return;
  }

  // Check if cursor is to the right of the last card's midpoint: drop at end
  const lastCard = paneCards[paneCards.length - 1];
  if (clientX >= lastCard.midX) {
    dropTargetInfo.value = {
      tier: tierName,
      index: panes.length,
      targetPaneId: lastCard.id
    };
    return;
  }

  // Cursor is between first and last card centers: Find nearest card partition
  for (let i = 0; i < paneCards.length - 1; i++) {
    const cur = paneCards[i];
    const next = paneCards[i + 1];
    const splitX = (cur.midX + next.midX) / 2;

    if (clientX >= cur.midX && clientX < splitX) {
      dropTargetInfo.value = {
        tier: tierName,
        index: cur.idx + 1,
        targetPaneId: cur.id
      };
      return;
    } else if (clientX >= splitX && clientX < next.midX) {
      dropTargetInfo.value = {
        tier: tierName,
        index: next.idx,
        targetPaneId: next.id
      };
      return;
    }
  }

  // Fallback to closest card's index (strictly never jump to panes.length if on the left!)
  let closestCard = paneCards[0];
  let minDistance = Math.abs(clientX - closestCard.midX);
  for (let i = 1; i < paneCards.length; i++) {
    const dist = Math.abs(clientX - paneCards[i].midX);
    if (dist < minDistance) {
      minDistance = dist;
      closestCard = paneCards[i];
    }
  }

  const ratio = (clientX - closestCard.rect.left) / closestCard.rect.width;
  const targetIdx = ratio < 0.5 ? closestCard.idx : closestCard.idx + 1;

  dropTargetInfo.value = {
    tier: tierName,
    index: targetIdx,
    targetPaneId: closestCard.id
  };
}

function executeCardDrop(srcId: string, target: DropTargetInfo) {
  pushHistory();

  // 1. Identify which tier the card is currently in
  let srcTier: 'top' | 'upper' | 'lower' | null = null;
  let srcIdx = -1;
  let srcWeight = 25;

  if (layout.value.topPanes && layout.value.topPanes.includes(srcId)) {
    srcTier = 'top';
    srcIdx = layout.value.topPanes.indexOf(srcId);
    srcWeight = layout.value.topWeights?.[srcIdx] ?? 25;
  } else if (layout.value.upperPanes.includes(srcId)) {
    srcTier = 'upper';
    srcIdx = layout.value.upperPanes.indexOf(srcId);
    srcWeight = layout.value.upperWeights[srcIdx] ?? 33;
  } else if (layout.value.lowerPanes.includes(srcId)) {
    srcTier = 'lower';
    srcIdx = layout.value.lowerPanes.indexOf(srcId);
    srcWeight = layout.value.lowerWeights[srcIdx] ?? 25;
  }

  if (!srcTier || srcIdx === -1) return;

  // 2. Identify target list & weights
  if (!layout.value.topPanes) layout.value.topPanes = [];
  if (!layout.value.topWeights) layout.value.topWeights = [];

  let tgtList: string[];
  let tgtWeights: number[];
  if (target.tier === 'top') {
    tgtList = layout.value.topPanes;
    tgtWeights = layout.value.topWeights;
  } else if (target.tier === 'upper') {
    tgtList = layout.value.upperPanes;
    tgtWeights = layout.value.upperWeights;
  } else {
    tgtList = layout.value.lowerPanes;
    tgtWeights = layout.value.lowerWeights;
  }

  // 3. Remove ALL occurrences of srcId from ALL tiers first (ensures absolute zero duplication)
  const removeIdFromTier = (list: string[], weights?: number[]) => {
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i] === srcId) {
        list.splice(i, 1);
        if (weights && weights.length > i) weights.splice(i, 1);
      }
    }
  };
  removeIdFromTier(layout.value.topPanes, layout.value.topWeights);
  removeIdFromTier(layout.value.upperPanes, layout.value.upperWeights);
  removeIdFromTier(layout.value.lowerPanes, layout.value.lowerWeights);

  // 4. Calculate insert index in target tier
  let insertIdx = target.index;
  if (srcTier === target.tier && srcIdx < insertIdx) {
    insertIdx = Math.max(0, insertIdx - 1);
  }
  insertIdx = Math.min(tgtList.length, Math.max(0, insertIdx));

  // 5. Insert into target
  tgtList.splice(insertIdx, 0, srcId);

  if (srcTier === target.tier) {
    tgtWeights.splice(insertIdx, 0, srcWeight || Math.round(100 / tgtList.length));
  } else {
    // Cross-tier move: rebalance weights in both tiers
    normalizeWeights();
  }

  saveLayout();
  triggerLandAnimation(srcId);

  const title = getWidgetMeta(srcId).title;
  const tierLabel = target.tier === 'top' ? '頂排' : target.tier === 'upper' ? '上排' : '下排';
  if (srcTier === target.tier) {
    showToast(`已在 [${tierLabel}] 重新排序 [${title}]`);
  } else {
    showToast(`已將 [${title}] 移至 [${tierLabel}]`);
  }
}

// 4. Maximize Pane Feature
const maximizedId = ref<string | null>(null);
function toggleMaximize(id: string) {
  maximizedId.value = maximizedId.value === id ? null : id;
}

// Keyboard shortcuts (Esc to exit maximize or close drawer)
function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    if (maximizedId.value) maximizedId.value = null;
    if (isDrawerOpen.value) isDrawerOpen.value = false;
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown);
});
</script>

<template>
  <div
    class="workspace-hybrid"
    :class="{
      'mode-editing': isEditing,
      'is-dragging-active': isCardDragging,
      'is-splitter-active': isSplitterDragging
    }"
  >
        <!-- Top Executive Ribbon: 版面快捷切換、卡片風格與排版調整 -->
    <div class="hybrid-ribbon" :class="{ 'ribbon-edit-active': isEditing }">
      <div class="ribbon-left">
        <!-- 四大標準版面方案快捷切換膠囊 -->
        <div class="quick-layout-pills" role="tablist" aria-label="版面方案即時切換">
          <button
            v-for="p in presetLayouts"
            :key="p.id"
            type="button"
            class="layout-pill-btn"
            :class="{ active: currentProfileId === p.id }"
            @click="applyProfile(p.id)"
            :title="p.desc || p.name"
          >
            <span class="pill-icon">{{ p.icon }}</span>
            <span class="pill-name">{{ p.shortName }}</span>
            <span class="pill-ratio mono">{{ p.ratioText }}</span>
          </button>
        </div>

        <div class="ribbon-v-divider"></div>

        <!-- 全域卡片風格一鍵切換 (V0 經典 vs Astra 原版，排除已定案之帳戶權益) -->
        <div class="quick-theme-switcher" role="group" aria-label="全域卡片風格切換">
          <button
            type="button"
            class="btn-theme-toggle"
            :class="{ active: isAllV0 }"
            @click="toggleAllCardsVersion('v0')"
            title="將未定案卡片統一切換為 V0 經典風格"
          >
            🟢 V0 經典
          </button>
          <button
            type="button"
            class="btn-theme-toggle"
            :class="{ active: !isAllV0 }"
            @click="toggleAllCardsVersion('astra')"
            title="將未定案卡片統一切換為 Astra 原版風格"
          >
            💎 Astra 原版
          </button>
        </div>

        <div class="ribbon-v-divider"></div>

        <!-- 頂部 KPI 雙層緊湊 vs 原版三段切換開關 (眼見為憑) -->
        <div class="quick-theme-switcher" role="group" aria-label="KPI 雙層對比切換">
          <button
            type="button"
            class="btn-theme-toggle"
            :class="{ active: preferences.kpiDualLayer }"
            @click="setKpiDualLayer(!preferences.kpiDualLayer)"
            title="切換頂部核心指標雙層極簡高階數值棧"
          >
            {{ preferences.kpiDualLayer ? '✦ 雙層緊湊 KPI (58px)' : '標準三段 KPI (85px)' }}
          </button>
        </div>

        <!-- Live State Indicator Badge (Only in Edit Mode) -->
        <span v-if="isEditing" class="edit-state-pill" title="編輯微調中：可直接按住標題拖曳換位、滑動分割線縮放比例">
          <span class="edit-pulse-dot"></span>
          <span>版面微調中</span>
        </span>
      </div>

      <div class="ribbon-right">
        <!-- 版面方案切換器與存檔管理 (Saved Layout Profiles) -->
        <div class="layout-profile-picker" role="group" aria-label="版面方案管理">
          <span class="profile-picker-label text-white">版面方案:</span>
          <select
            v-model="currentProfileId"
            class="select-layout-profile"
            @change="applyProfile(currentProfileId)"
            title="切換已儲存的版面方案"
          >
            <option v-for="p in savedProfiles" :key="p.id" :value="p.id">
              {{ p.name }}
            </option>
          </select>

          <!-- 編輯解鎖模式下顯示的方案管理按鈕組 -->
          <template v-if="isEditing">
            <button
              type="button"
              class="btn btn-xs btn-outline-gold"
              @click="openSaveModal"
              title="將當前排版另存為全新自訂方案"
            >
              ＋ 另存新方案
            </button>
            <button
              v-if="!currentProfile?.isSystem"
              type="button"
              class="btn btn-xs btn-outline-cyan"
              @click="updateCurrentProfile"
              title="儲存變更覆蓋至當前方案"
            >
              💾 儲存變更
            </button>
            <button
              v-if="!currentProfile?.isSystem"
              type="button"
              class="btn btn-xs btn-danger-outline"
              @click="deleteProfile(currentProfileId)"
              title="刪除當前自訂方案"
            >
              ✕ 刪除
            </button>
          </template>
        </div>

        <div class="ribbon-v-divider"></div>

        <!-- 編輯解鎖控制按鈕 -->
        <template v-if="isEditing">
          <button
            type="button"
            class="btn btn-xs btn-primary btn-done-edit"
            @click="isEditing = false; isDrawerOpen = false; saveProfilesToStorage()"
            title="完成版面調整並重新鎖定工作台"
          >
            ✓ 完成鎖定
          </button>
        </template>
        <template v-else>
          <button
            type="button"
            class="btn btn-xs btn-secondary btn-enter-edit"
            @click="isEditing = true"
            title="解鎖工作台：拖移排序、微調比例、縮放卡片、儲存方案"
          >
            ⚙ 調整版面
          </button>
        </template>
      </div>
    </div>

    <!-- Edit Mode Interactive Guide Bar -->
    <div v-if="isEditing" class="edit-mode-guide-bar">
      <div class="guide-left">
        <span class="guide-icon">💡</span>
        <span class="guide-text">
          <strong>微調小撇步：</strong> 按住標題拖曳換位 · 拖動分割線縮放卡片寬高 · 點擊「✓ 完成鎖定」固化
        </span>
      </div>
      <button type="button" class="btn-guide-close" @click="isEditing = false">鎖定 ✕</button>
    </div>

    

    <!-- High-Fidelity Floating REORDER Ghost Card (Follows mouse) -->
    <div
      v-if="isCardDragging && ghostPosition && draggedCardId"
      class="catos-drag-ghost-card"
      :style="{ left: `${ghostPosition.x}px`, top: `${ghostPosition.y}px` }"
    >
      <div class="ghost-header">
        <span class="ghost-tag">REORDER</span>
        <span class="ghost-en">{{ getWidgetMeta(draggedCardId).en }}</span>
      </div>
      <div class="ghost-title">
        {{ getWidgetMeta(draggedCardId).title }}
      </div>
    </div>

    <!-- Maximized Fullscreen Overlay Mode -->
    <div v-if="maximizedId" class="maximized-overlay">
      <div class="maximized-header">
        <div class="header-left">
          <span class="maximized-label">🔍 旗艦全螢幕聚焦</span>
          <span class="pane-name">{{ WIDGETS_META[maximizedId]?.title }}</span>
        </div>
        <button type="button" class="btn btn-sm btn-primary" @click="maximizedId = null">
          ↙ 還原工作台 (Esc)
        </button>
      </div>
      <div class="maximized-body">
        <div v-if="maximizedId === 'equity'" class="card h-full">
          <SparklineArea :points="equityPoints" />
        </div>
        <div v-else-if="maximizedId === 'donut'" class="card h-full">
          <DonutChart :items="exposureItems" centerValue="1,420.50" centerLabel="名義曝險 USDT" />
        </div>
        <div v-else-if="maximizedId === 'events'" class="card h-full">
          <div class="card-header"><div class="card-title">重要事件時間軸 (全屏聚焦流)</div></div>
          <div class="card-body events-body p-4">
            <AuditTimeline :events="filteredAuditEvents" :showHeader="true" maxHeight="520px" />
          </div>
        </div>
        <div v-else-if="maximizedId === 'risk'" class="card h-full">
          <RiskGauge :risk="riskState" />
        </div>
        <div v-else-if="maximizedId === 'bots'" class="card h-full p-2">
          <BotQueueWidget :bots="botQueue" :showHeader="false" :period="botPeriod" mode="new" />
        </div>
        <div v-else-if="maximizedId === 'positions'" class="card h-full p-2">
          <PositionsWidget />
        </div>
        <div v-else-if="maximizedId === 'yaozi'" class="card h-full p-4 flex flex-col">
          <div class="card-header pb-3 mb-2 border-b border-border-secondary">
            <div class="card-title text-base font-bold text-foreground">市場情報</div>
          </div>
          <div class="card-body p-2 flex-1 overflow-y-auto">
            <div class="market-intel-stream">
              <div v-for="y in filteredMarketAlerts" :key="y.id" class="market-intel-item">
                <div class="intel-header">
                  <span class="intel-tag" :class="getIntelTagClass(y.type)">{{ y.type }}</span>
                  <span class="intel-time mono tabular-nums">{{ y.time }}</span>
                </div>
                <div class="intel-title">{{ y.title }}</div>
                <div class="intel-summary">{{ y.summary }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Widget Drawer Modal (Opens during Edit Mode) -->
    <div v-if="isDrawerOpen" class="widget-drawer-backdrop" @click.self="isDrawerOpen = false">
      <div class="widget-drawer">
        <div class="drawer-header">
          <div class="drawer-title">
            <span>＋ 元件庫抽屜</span>
            <span class="drawer-sub">自由勾選顯示或隱藏卡片模組</span>
          </div>
          <button type="button" class="btn-drawer-close" @click="isDrawerOpen = false">✕</button>
        </div>
        <div class="drawer-body">
          <div
            v-for="(meta, wId) in ALL_WIDGETS_META"
            :key="wId"
            class="drawer-item"
            :class="{ active: !layout.hiddenPanes.includes(wId as string) }"
            @click="toggleWidgetVisibility(wId as string)"
          >
            <div class="drawer-item-checkbox">
              <input
                type="checkbox"
                :checked="!layout.hiddenPanes.includes(wId as string)"
                @click.stop="toggleWidgetVisibility(wId as string)"
              />
            </div>
            <div class="drawer-item-info">
              <div class="drawer-item-title">{{ meta.title }}</div>
              <div class="drawer-item-desc">
                {{ meta.en }} · {{ (layout.topPanes && layout.topPanes.includes(wId as string)) ? '位於頂排' : (layout.upperPanes.includes(wId as string) ? '位於上排' : (layout.lowerPanes.includes(wId as string) ? '位於下排' : '目前已隱藏')) }}
              </div>
            </div>
            <div class="drawer-item-action">
              <span :class="['badge', !layout.hiddenPanes.includes(wId as string) ? 'badge-accent' : 'badge-secondary']">
                {{ !layout.hiddenPanes.includes(wId as string) ? '已顯示' : '已隱藏' }}
              </span>
            </div>
          </div>
        </div>
        <div class="drawer-footer">
          <button type="button" class="btn btn-sm btn-secondary" @click="autoPack">ϟ 自動排版</button>
          <button type="button" class="btn btn-sm btn-primary" @click="isDrawerOpen = false">完成設定</button>
        </div>
      </div>
    </div>

    <!-- 方案 1：Bloomberg Terminal 典範【極致高密度金融平鋪工作台】 -->
    <div v-if="activeBlueprint === 'bloomberg' && !maximizedId" class="bp-bloomberg-desk" :class="{ 'is-editing-active': isEditing }">

      <!-- 雙欄無縫平鋪 (左欄 bbgLeftColWidth% / 右欄 100-bbgLeftColWidth%) + 中間垂直分割線 -->
      <div class="bbg-grid-layout">
        <!-- 左欄：權益與水下回撤雙軌中樞 + 當前持倉部位 -->
        <div class="bbg-col-left" :style="{ flex: `${bbgLeftColWidth} 1 0px` }">
          <!-- 左上卡片槽 (leftUpper) -->
          <div
            class="bbg-card bbg-card-left-upper"
            :style="{ flex: `${bbgLeftUpperHeight} 1 0px` }"
            :class="{ 'is-drag-source': activeDragSourceSlot === 'leftUpper', 'is-drop-target': hoverDropTargetSlot === 'leftUpper' }"
            @mouseenter="isCardDragging ? hoverDropTargetSlot = 'leftUpper' : null"
            @mouseleave="hoverDropTargetSlot === 'leftUpper' ? hoverDropTargetSlot = null : null"
          >
            <div class="bbg-card-header">
              <div
                class="bbg-card-title"
                :class="{ 'is-draggable-grip': isEditing }"
                @mousedown="isEditing ? startSlotCardDrag('leftUpper', $event) : null"
                :title="isEditing ? '按住拖曳可與其他卡片對調位置' : ''"
              >
                <span v-if="isEditing" class="grip-dots">⋮⋮</span>
                <span class="bbg-title-text text-white">
                  {{ CARD_META[bbgPanes.leftUpper]?.title || '監控面板' }}
                </span>
                
              </div>
              <div class="header-right-actions flex items-center gap-2">
                <!-- 1. 部位與活動分頁切換按鈕 (持倉 / 掛單 / 成交) -->
                <div v-if="isActivityCard(bbgPanes.leftUpper)" class="card-header-segmented" role="group">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'positions' }"
                    @click.stop="activityTab = 'positions'"
                  >
                    持倉 <span class="badge-num mono">{{ v0Positions.length }}</span>
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'orders' }"
                    @click.stop="activityTab = 'orders'"
                  >
                    掛單 <span class="badge-num mono">{{ v0Orders.length }}</span>
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'fills' }"
                    @click.stop="activityTab = 'fills'"
                  >
                    成交 <span class="badge-num mono">{{ v0Fills.length }}</span>
                  </button>
                </div>

                <!-- 2. 事件與審計篩選按鈕 (全部 / 待處理) -->
                <div v-else-if="isEventsCard(bbgPanes.leftUpper)" class="card-header-segmented" role="group">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: eventFilter === 'all' }"
                    @click.stop="eventFilter = 'all'"
                  >
                    全部 ({{ v0Events.length }})
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: eventFilter === 'action' }"
                    @click.stop="eventFilter = 'action'"
                  >
                    待處理
                    <span v-if="pendingV0Events.length > 0" class="badge-num-risk">{{ pendingV0Events.length }}</span>
                  </button>
                </div>

                <!-- 3. 機器人週期選擇器 (4H / 1D / 7D) -->
                <div v-else-if="isBotsCard(bbgPanes.leftUpper)" class="card-header-segmented" role="group">
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '4H' }" @click.stop="botPeriod = '4H'">4H</button>
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '1D' }" @click.stop="botPeriod = '1D'">1D</button>
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '7D' }" @click.stop="botPeriod = '7D'">7D</button>
                </div>

                <!-- 4. 帳戶權益時間週期選擇 (24H / 7D / 30D) -->
                <div v-else-if="isEquityCard(bbgPanes.leftUpper)" class="card-header-segmented" role="group">
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '24H' }" @click.stop="setV0Period('24H')">24H</button>
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '7D' }" @click.stop="setV0Period('7D')">7D</button>
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '30D' }" @click.stop="setV0Period('30D')">30D</button>
                </div>
              </div>
            </div>
            <div class="bbg-card-body">
              <!-- V0 移植卡片 -->
              <V0AccountBand v-if="bbgPanes.leftUpper === 'v0_equity'" :showHeader="false" />
              <V0BotTable v-else-if="bbgPanes.leftUpper === 'v0_bots'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <ExposurePanel v-else-if="bbgPanes.leftUpper === 'v0_exposure' || bbgPanes.leftUpper === 'exposure'" :showHeader="false" :equity="Number(kpis?.total_equity) || 40272" @selectBot="handleOpenBotDrawer" />
              <ActivityPanel v-else-if="bbgPanes.leftUpper === 'v0_activity' || bbgPanes.leftUpper === 'activity'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <RiskPanel v-else-if="bbgPanes.leftUpper === 'v0_risk'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <V0EventFeed v-else-if="bbgPanes.leftUpper === 'v0_events'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <V0Pipeline v-else-if="bbgPanes.leftUpper === 'v0_pipeline'" :showHeader="false" @selectBot="handleOpenBotDrawer" />

              <!-- Astra 原版卡片 -->
              <EquityDrawdownHero v-else-if="bbgPanes.leftUpper === 'equity'" :showHeader="false" :points="equityPoints" :kpis="kpis" :riskState="riskState" />
              <PositionsWidget v-else-if="bbgPanes.leftUpper === 'positions'" />
              <BotQueueWidget v-else-if="bbgPanes.leftUpper === 'bots'" :bots="botQueue" :showHeader="false" :period="botPeriod" mode="new" @selectBot="handleOpenBotDrawer" />
              <RiskStatusCard v-else-if="bbgPanes.leftUpper === 'risk'" :risk="riskState" :kpis="kpis" />
              <AllocationUnifiedWidget v-else-if="bbgPanes.leftUpper === 'donut'" :mode="allocationMode" :items="exposureItems" :showHeader="false" />
              <AuditTimeline v-else-if="bbgPanes.leftUpper === 'events'" :events="filteredAuditEvents" :showHeader="false" :compact="true" maxHeight="100%" />
            </div>
          </div>

          <!-- 左欄水平分割線 (拖動走勢 vs 部位高度) -->
          <div
            class="bp-splitter-h"
            :class="{ 'is-locked': !isEditing }"
            @pointerdown="startBbgLeftSplitDrag"
            title="上下滑動微調左側上下高度比例 (需解鎖)"
          >
            <div class="splitter-line-h"></div>
          </div>

          <!-- 左下卡片槽 (leftLower) -->
          <div
            class="bbg-card bbg-card-left-lower"
            :style="{ flex: `${100 - bbgLeftUpperHeight} 1 0px` }"
            :class="{ 'is-drag-source': activeDragSourceSlot === 'leftLower', 'is-drop-target': hoverDropTargetSlot === 'leftLower' }"
            @mouseenter="isCardDragging ? hoverDropTargetSlot = 'leftLower' : null"
            @mouseleave="hoverDropTargetSlot === 'leftLower' ? hoverDropTargetSlot = null : null"
          >
            <div class="bbg-card-header">
              <div
                class="bbg-card-title"
                :class="{ 'is-draggable-grip': isEditing }"
                @mousedown="isEditing ? startSlotCardDrag('leftLower', $event) : null"
                :title="isEditing ? '按住拖曳可與其他卡片對調位置' : ''"
              >
                <span v-if="isEditing" class="grip-dots">⋮⋮</span>
                <span class="bbg-title-text text-white">
                  {{ CARD_META[bbgPanes.leftLower]?.title || '監控面板' }}
                </span>
                
              </div>
              <div class="header-right-actions flex items-center gap-2">
                <!-- 1. 部位與活動分頁切換按鈕 (持倉 / 掛單 / 成交) -->
                <div v-if="isActivityCard(bbgPanes.leftLower)" class="card-header-segmented" role="group">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'positions' }"
                    @click.stop="activityTab = 'positions'"
                  >
                    持倉 <span class="badge-num mono">{{ v0Positions.length }}</span>
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'orders' }"
                    @click.stop="activityTab = 'orders'"
                  >
                    掛單 <span class="badge-num mono">{{ v0Orders.length }}</span>
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'fills' }"
                    @click.stop="activityTab = 'fills'"
                  >
                    成交 <span class="badge-num mono">{{ v0Fills.length }}</span>
                  </button>
                </div>

                <!-- 2. 事件與審計篩選按鈕 (全部 / 待處理) -->
                <div v-else-if="isEventsCard(bbgPanes.leftLower)" class="card-header-segmented" role="group">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: eventFilter === 'all' }"
                    @click.stop="eventFilter = 'all'"
                  >
                    全部 ({{ v0Events.length }})
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: eventFilter === 'action' }"
                    @click.stop="eventFilter = 'action'"
                  >
                    待處理
                    <span v-if="pendingV0Events.length > 0" class="badge-num-risk">{{ pendingV0Events.length }}</span>
                  </button>
                </div>

                <!-- 3. 機器人週期選擇器 (4H / 1D / 7D) -->
                <div v-else-if="isBotsCard(bbgPanes.leftLower)" class="card-header-segmented" role="group">
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '4H' }" @click.stop="botPeriod = '4H'">4H</button>
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '1D' }" @click.stop="botPeriod = '1D'">1D</button>
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '7D' }" @click.stop="botPeriod = '7D'">7D</button>
                </div>

                <!-- 4. 帳戶權益時間週期選擇 (24H / 7D / 30D) -->
                <div v-else-if="isEquityCard(bbgPanes.leftLower)" class="card-header-segmented" role="group">
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '24H' }" @click.stop="setV0Period('24H')">24H</button>
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '7D' }" @click.stop="setV0Period('7D')">7D</button>
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '30D' }" @click.stop="setV0Period('30D')">30D</button>
                </div>
              
                <!-- 5. 雙版本快速切換膠囊 (未定案卡片隨時可切換) -->
                <div class="version-switch-pill" role="group">
                  <button
                    type="button"
                    class="btn-ver-pill"
                    :class="{ active: isCardV0(bbgPanes.leftLower) }"
                    @click.stop="setSlotCardVersion('leftLower', 'v0')"
                    title="切換為 V0 經典移植版"
                  >
                    V0
                  </button>
                  <button
                    type="button"
                    class="btn-ver-pill"
                    :class="{ active: !isCardV0(bbgPanes.leftLower) }"
                    @click.stop="setSlotCardVersion('leftLower', 'astra')"
                    title="切換為 Astra 原版"
                  >
                    原版
                  </button>
                </div>
              </div>
            </div>
            <div class="bbg-card-body">
              <!-- V0 移植卡片 -->
              <V0AccountBand v-if="bbgPanes.leftLower === 'v0_equity'" :showHeader="false" />
              <V0BotTable v-else-if="bbgPanes.leftLower === 'v0_bots'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <ExposurePanel v-else-if="bbgPanes.leftLower === 'v0_exposure' || bbgPanes.leftLower === 'exposure'" :showHeader="false" :equity="Number(kpis?.total_equity) || 40272" @selectBot="handleOpenBotDrawer" />
              <ActivityPanel v-else-if="bbgPanes.leftLower === 'v0_activity' || bbgPanes.leftLower === 'activity'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <RiskPanel v-else-if="bbgPanes.leftLower === 'v0_risk'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <V0EventFeed v-else-if="bbgPanes.leftLower === 'v0_events'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <V0Pipeline v-else-if="bbgPanes.leftLower === 'v0_pipeline'" :showHeader="false" @selectBot="handleOpenBotDrawer" />

              <!-- Astra 原版卡片 -->
              <EquityDrawdownHero v-else-if="bbgPanes.leftLower === 'equity'" :showHeader="false" :points="equityPoints" :kpis="kpis" :riskState="riskState" />
              <PositionsWidget v-else-if="bbgPanes.leftLower === 'positions'" />
              <BotQueueWidget v-else-if="bbgPanes.leftLower === 'bots'" :bots="botQueue" :showHeader="false" :period="botPeriod" mode="new" @selectBot="handleOpenBotDrawer" />
              <RiskStatusCard v-else-if="bbgPanes.leftLower === 'risk'" :risk="riskState" :kpis="kpis" />
              <AllocationUnifiedWidget v-else-if="bbgPanes.leftLower === 'donut'" :mode="allocationMode" :items="exposureItems" :showHeader="false" />
              <AuditTimeline v-else-if="bbgPanes.leftLower === 'events'" :events="filteredAuditEvents" :showHeader="false" :compact="true" maxHeight="100%" />
            </div>
          </div>
        </div>

        <!-- 左右主分欄垂直分割線 (拖動左欄 vs 右欄寬度，需解鎖) -->
        <div
          class="bp-splitter-v"
          :class="{ 'is-locked': !isEditing }"
          @pointerdown="startBbgMainColSplitDrag"
          @dblclick="isEditing ? resetBbgSplits() : null"
          title="左右滑動調整分欄寬度比例 · 雙擊還原預設黃金比例 (64% / 36%)"
        >
          <div class="splitter-line-v"></div>
        </div>

        <!-- 右欄：3 個卡片槽 (right1, right2, right3) -->
        <div class="bbg-col-right" :style="{ flex: `${100 - bbgLeftColWidth} 1 0px` }">
          <!-- 右欄卡片 1 (right1) -->
          <div
            class="bbg-card bbg-card-right-1"
            :style="{ flex: `${bbgRightWeights[0]} 1 0px` }"
            :class="{ 'is-drag-source': activeDragSourceSlot === 'right1', 'is-drop-target': hoverDropTargetSlot === 'right1' }"
            @mouseenter="isCardDragging ? hoverDropTargetSlot = 'right1' : null"
            @mouseleave="hoverDropTargetSlot === 'right1' ? hoverDropTargetSlot = null : null"
          >
            <div class="bbg-card-header">
              <div
                class="bbg-card-title"
                :class="{ 'is-draggable-grip': isEditing }"
                @mousedown="isEditing ? startSlotCardDrag('right1', $event) : null"
                :title="isEditing ? '按住拖曳可與其他卡片對調位置' : ''"
              >
                <span v-if="isEditing" class="grip-dots">⋮⋮</span>
                <span class="bbg-title-text text-white">
                  {{ CARD_META[bbgPanes.right1]?.title || '監控面板' }}
                </span>
                
              </div>
              <div class="header-right-actions flex items-center gap-2">
                <!-- 1. 部位與活動分頁切換按鈕 (持倉 / 掛單 / 成交) -->
                <div v-if="isActivityCard(bbgPanes.right1)" class="card-header-segmented" role="group">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'positions' }"
                    @click.stop="activityTab = 'positions'"
                  >
                    持倉 <span class="badge-num mono">{{ v0Positions.length }}</span>
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'orders' }"
                    @click.stop="activityTab = 'orders'"
                  >
                    掛單 <span class="badge-num mono">{{ v0Orders.length }}</span>
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'fills' }"
                    @click.stop="activityTab = 'fills'"
                  >
                    成交 <span class="badge-num mono">{{ v0Fills.length }}</span>
                  </button>
                </div>

                <!-- 2. 事件與審計篩選按鈕 (全部 / 待處理) -->
                <div v-else-if="isEventsCard(bbgPanes.right1)" class="card-header-segmented" role="group">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: eventFilter === 'all' }"
                    @click.stop="eventFilter = 'all'"
                  >
                    全部 ({{ v0Events.length }})
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: eventFilter === 'action' }"
                    @click.stop="eventFilter = 'action'"
                  >
                    待處理
                    <span v-if="pendingV0Events.length > 0" class="badge-num-risk">{{ pendingV0Events.length }}</span>
                  </button>
                </div>

                <!-- 3. 機器人週期選擇器 (4H / 1D / 7D) -->
                <div v-else-if="isBotsCard(bbgPanes.right1)" class="card-header-segmented" role="group">
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '4H' }" @click.stop="botPeriod = '4H'">4H</button>
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '1D' }" @click.stop="botPeriod = '1D'">1D</button>
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '7D' }" @click.stop="botPeriod = '7D'">7D</button>
                </div>

                <!-- 4. 帳戶權益時間週期選擇 (24H / 7D / 30D) -->
                <div v-else-if="isEquityCard(bbgPanes.right1)" class="card-header-segmented" role="group">
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '24H' }" @click.stop="setV0Period('24H')">24H</button>
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '7D' }" @click.stop="setV0Period('7D')">7D</button>
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '30D' }" @click.stop="setV0Period('30D')">30D</button>
                </div>
              
                <!-- 5. 雙版本快速切換膠囊 (未定案卡片隨時可切換) -->
                <div class="version-switch-pill" role="group">
                  <button
                    type="button"
                    class="btn-ver-pill"
                    :class="{ active: isCardV0(bbgPanes.right1) }"
                    @click.stop="setSlotCardVersion('right1', 'v0')"
                    title="切換為 V0 經典移植版"
                  >
                    V0
                  </button>
                  <button
                    type="button"
                    class="btn-ver-pill"
                    :class="{ active: !isCardV0(bbgPanes.right1) }"
                    @click.stop="setSlotCardVersion('right1', 'astra')"
                    title="切換為 Astra 原版"
                  >
                    原版
                  </button>
                </div>
              </div>
            </div>
            <div class="bbg-card-body">
              <!-- V0 移植卡片 -->
              <V0AccountBand v-if="bbgPanes.right1 === 'v0_equity'" :showHeader="false" />
              <V0BotTable v-else-if="bbgPanes.right1 === 'v0_bots'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <ExposurePanel v-else-if="bbgPanes.right1 === 'v0_exposure' || bbgPanes.right1 === 'exposure'" :showHeader="false" :equity="Number(kpis?.total_equity) || 40272" @selectBot="handleOpenBotDrawer" />
              <ActivityPanel v-else-if="bbgPanes.right1 === 'v0_activity' || bbgPanes.right1 === 'activity'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <RiskPanel v-else-if="bbgPanes.right1 === 'v0_risk'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <V0EventFeed v-else-if="bbgPanes.right1 === 'v0_events'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <V0Pipeline v-else-if="bbgPanes.right1 === 'v0_pipeline'" :showHeader="false" @selectBot="handleOpenBotDrawer" />

              <!-- Astra 原版卡片 -->
              <EquityDrawdownHero v-else-if="bbgPanes.right1 === 'equity'" :showHeader="false" :points="equityPoints" :kpis="kpis" :riskState="riskState" />
              <PositionsWidget v-else-if="bbgPanes.right1 === 'positions'" />
              <BotQueueWidget v-else-if="bbgPanes.right1 === 'bots'" :bots="botQueue" :showHeader="false" :period="botPeriod" mode="new" @selectBot="handleOpenBotDrawer" />
              <RiskStatusCard v-else-if="bbgPanes.right1 === 'risk'" :risk="riskState" :kpis="kpis" />
              <AllocationUnifiedWidget v-else-if="bbgPanes.right1 === 'donut'" :mode="allocationMode" :items="exposureItems" :showHeader="false" />
              <AuditTimeline v-else-if="bbgPanes.right1 === 'events'" :events="filteredAuditEvents" :showHeader="false" :compact="true" maxHeight="100%" />
            </div>
          </div>

          <!-- 右欄水平分割線 1 -->
          <div
            class="bp-splitter-h"
            :class="{ 'is-locked': !isEditing }"
            @pointerdown="e => startBbgRightSplitDrag(0, e)"
            title="上下滑動微調右側卡片高度比例 (需解鎖)"
          >
            <div class="splitter-line-h"></div>
          </div>

          <!-- 右欄卡片 2 (right2) -->
          <div
            class="bbg-card bbg-card-right-2"
            :style="{ flex: `${bbgRightWeights[1]} 1 0px` }"
            :class="{ 'is-drag-source': activeDragSourceSlot === 'right2', 'is-drop-target': hoverDropTargetSlot === 'right2' }"
            @mouseenter="isCardDragging ? hoverDropTargetSlot = 'right2' : null"
            @mouseleave="hoverDropTargetSlot === 'right2' ? hoverDropTargetSlot = null : null"
          >
            <div class="bbg-card-header">
              <div
                class="bbg-card-title"
                :class="{ 'is-draggable-grip': isEditing }"
                @mousedown="isEditing ? startSlotCardDrag('right2', $event) : null"
                :title="isEditing ? '按住拖曳可與其他卡片對調位置' : ''"
              >
                <span v-if="isEditing" class="grip-dots">⋮⋮</span>
                <span class="bbg-title-text text-white">
                  {{ CARD_META[bbgPanes.right2]?.title || '監控面板' }}
                </span>
                
              </div>
              <div class="header-right-actions flex items-center gap-2">
                <!-- 1. 部位與活動分頁切換按鈕 (持倉 / 掛單 / 成交) -->
                <div v-if="isActivityCard(bbgPanes.right2)" class="card-header-segmented" role="group">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'positions' }"
                    @click.stop="activityTab = 'positions'"
                  >
                    持倉 <span class="badge-num mono">{{ v0Positions.length }}</span>
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'orders' }"
                    @click.stop="activityTab = 'orders'"
                  >
                    掛單 <span class="badge-num mono">{{ v0Orders.length }}</span>
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'fills' }"
                    @click.stop="activityTab = 'fills'"
                  >
                    成交 <span class="badge-num mono">{{ v0Fills.length }}</span>
                  </button>
                </div>

                <!-- 2. 事件與審計篩選按鈕 (全部 / 待處理) -->
                <div v-else-if="isEventsCard(bbgPanes.right2)" class="card-header-segmented" role="group">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: eventFilter === 'all' }"
                    @click.stop="eventFilter = 'all'"
                  >
                    全部 ({{ v0Events.length }})
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: eventFilter === 'action' }"
                    @click.stop="eventFilter = 'action'"
                  >
                    待處理
                    <span v-if="pendingV0Events.length > 0" class="badge-num-risk">{{ pendingV0Events.length }}</span>
                  </button>
                </div>

                <!-- 3. 機器人週期選擇器 (4H / 1D / 7D) -->
                <div v-else-if="isBotsCard(bbgPanes.right2)" class="card-header-segmented" role="group">
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '4H' }" @click.stop="botPeriod = '4H'">4H</button>
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '1D' }" @click.stop="botPeriod = '1D'">1D</button>
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '7D' }" @click.stop="botPeriod = '7D'">7D</button>
                </div>

                <!-- 4. 帳戶權益時間週期選擇 (24H / 7D / 30D) -->
                <div v-else-if="isEquityCard(bbgPanes.right2)" class="card-header-segmented" role="group">
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '24H' }" @click.stop="setV0Period('24H')">24H</button>
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '7D' }" @click.stop="setV0Period('7D')">7D</button>
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '30D' }" @click.stop="setV0Period('30D')">30D</button>
                </div>
              
                <!-- 5. 雙版本快速切換膠囊 (未定案卡片隨時可切換) -->
                <div class="version-switch-pill" role="group">
                  <button
                    type="button"
                    class="btn-ver-pill"
                    :class="{ active: isCardV0(bbgPanes.right2) }"
                    @click.stop="setSlotCardVersion('right2', 'v0')"
                    title="切換為 V0 經典移植版"
                  >
                    V0
                  </button>
                  <button
                    type="button"
                    class="btn-ver-pill"
                    :class="{ active: !isCardV0(bbgPanes.right2) }"
                    @click.stop="setSlotCardVersion('right2', 'astra')"
                    title="切換為 Astra 原版"
                  >
                    原版
                  </button>
                </div>
              </div>
            </div>
            <div class="bbg-card-body">
              <!-- V0 移植卡片 -->
              <V0AccountBand v-if="bbgPanes.right2 === 'v0_equity'" :showHeader="false" />
              <V0BotTable v-else-if="bbgPanes.right2 === 'v0_bots'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <ExposurePanel v-else-if="bbgPanes.right2 === 'v0_exposure' || bbgPanes.right2 === 'exposure'" :showHeader="false" :equity="Number(kpis?.total_equity) || 40272" @selectBot="handleOpenBotDrawer" />
              <ActivityPanel v-else-if="bbgPanes.right2 === 'v0_activity' || bbgPanes.right2 === 'activity'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <RiskPanel v-else-if="bbgPanes.right2 === 'v0_risk'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <V0EventFeed v-else-if="bbgPanes.right2 === 'v0_events'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <V0Pipeline v-else-if="bbgPanes.right2 === 'v0_pipeline'" :showHeader="false" @selectBot="handleOpenBotDrawer" />

              <!-- Astra 原版卡片 -->
              <EquityDrawdownHero v-else-if="bbgPanes.right2 === 'equity'" :showHeader="false" :points="equityPoints" :kpis="kpis" :riskState="riskState" />
              <PositionsWidget v-else-if="bbgPanes.right2 === 'positions'" />
              <BotQueueWidget v-else-if="bbgPanes.right2 === 'bots'" :bots="botQueue" :showHeader="false" :period="botPeriod" mode="new" @selectBot="handleOpenBotDrawer" />
              <RiskStatusCard v-else-if="bbgPanes.right2 === 'risk'" :risk="riskState" :kpis="kpis" />
              <AllocationUnifiedWidget v-else-if="bbgPanes.right2 === 'donut'" :mode="allocationMode" :items="exposureItems" :showHeader="false" />
              <AuditTimeline v-else-if="bbgPanes.right2 === 'events'" :events="filteredAuditEvents" :showHeader="false" :compact="true" maxHeight="100%" />
            </div>
          </div>

          <!-- 右欄水平分割線 2 (僅在有第 3 張卡片時顯示) -->
          <div
            v-if="bbgRightWeights.length > 2 && bbgRightWeights[2] > 0"
            class="bp-splitter-h"
            :class="{ 'is-locked': !isEditing }"
            @pointerdown="e => startBbgRightSplitDrag(1, e)"
            title="上下滑動微調右側卡片高度比例 (需解鎖)"
          >
            <div class="splitter-line-h"></div>
          </div>

          <!-- 右欄卡片 3 (right3，僅在有第 3 張卡片時顯示) -->
          <div
            v-if="bbgRightWeights.length > 2 && bbgRightWeights[2] > 0"
            class="bbg-card bbg-card-right-3"
            :style="{ flex: `${bbgRightWeights[2]} 1 0px` }"
            :class="{ 'is-drag-source': activeDragSourceSlot === 'right3', 'is-drop-target': hoverDropTargetSlot === 'right3' }"
            @mouseenter="isCardDragging ? hoverDropTargetSlot = 'right3' : null"
            @mouseleave="hoverDropTargetSlot === 'right3' ? hoverDropTargetSlot = null : null"
          >
            <div class="bbg-card-header">
              <div
                class="bbg-card-title"
                :class="{ 'is-draggable-grip': isEditing }"
                @mousedown="isEditing ? startSlotCardDrag('right3', $event) : null"
                :title="isEditing ? '按住拖曳可與其他卡片對調位置' : ''"
              >
                <span v-if="isEditing" class="grip-dots">⋮⋮</span>
                <span class="bbg-title-text text-white">
                  {{ CARD_META[bbgPanes.right3]?.title || '監控面板' }}
                </span>
                
              </div>
              <div class="header-right-actions flex items-center gap-2">
                <!-- 1. 部位與活動分頁切換按鈕 (持倉 / 掛單 / 成交) -->
                <div v-if="isActivityCard(bbgPanes.right3)" class="card-header-segmented" role="group">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'positions' }"
                    @click.stop="activityTab = 'positions'"
                  >
                    持倉 <span class="badge-num mono">{{ v0Positions.length }}</span>
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'orders' }"
                    @click.stop="activityTab = 'orders'"
                  >
                    掛單 <span class="badge-num mono">{{ v0Orders.length }}</span>
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: activityTab === 'fills' }"
                    @click.stop="activityTab = 'fills'"
                  >
                    成交 <span class="badge-num mono">{{ v0Fills.length }}</span>
                  </button>
                </div>

                <!-- 2. 事件與審計篩選按鈕 (全部 / 待處理) -->
                <div v-else-if="isEventsCard(bbgPanes.right3)" class="card-header-segmented" role="group">
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: eventFilter === 'all' }"
                    @click.stop="eventFilter = 'all'"
                  >
                    全部 ({{ v0Events.length }})
                  </button>
                  <button
                    type="button"
                    class="seg-btn"
                    :class="{ active: eventFilter === 'action' }"
                    @click.stop="eventFilter = 'action'"
                  >
                    待處理
                    <span v-if="pendingV0Events.length > 0" class="badge-num-risk">{{ pendingV0Events.length }}</span>
                  </button>
                </div>

                <!-- 3. 機器人週期選擇器 (4H / 1D / 7D) -->
                <div v-else-if="isBotsCard(bbgPanes.right3)" class="card-header-segmented" role="group">
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '4H' }" @click.stop="botPeriod = '4H'">4H</button>
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '1D' }" @click.stop="botPeriod = '1D'">1D</button>
                  <button type="button" class="seg-btn" :class="{ active: botPeriod === '7D' }" @click.stop="botPeriod = '7D'">7D</button>
                </div>

                <!-- 4. 帳戶權益時間週期選擇 (24H / 7D / 30D) -->
                <div v-else-if="isEquityCard(bbgPanes.right3)" class="card-header-segmented" role="group">
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '24H' }" @click.stop="setV0Period('24H')">24H</button>
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '7D' }" @click.stop="setV0Period('7D')">7D</button>
                  <button type="button" class="seg-btn" :class="{ active: v0Period === '30D' }" @click.stop="setV0Period('30D')">30D</button>
                </div>
              
                <!-- 5. 雙版本快速切換膠囊 (未定案卡片隨時可切換) -->
                <div class="version-switch-pill" role="group">
                  <button
                    type="button"
                    class="btn-ver-pill"
                    :class="{ active: isCardV0(bbgPanes.right3) }"
                    @click.stop="setSlotCardVersion('right3', 'v0')"
                    title="切換為 V0 經典移植版"
                  >
                    V0
                  </button>
                  <button
                    type="button"
                    class="btn-ver-pill"
                    :class="{ active: !isCardV0(bbgPanes.right3) }"
                    @click.stop="setSlotCardVersion('right3', 'astra')"
                    title="切換為 Astra 原版"
                  >
                    原版
                  </button>
                </div>
              </div>
            </div>
            <div class="bbg-card-body">
              <!-- V0 移植卡片 -->
              <V0AccountBand v-if="bbgPanes.right3 === 'v0_equity'" :showHeader="false" />
              <V0BotTable v-else-if="bbgPanes.right3 === 'v0_bots'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <ExposurePanel v-else-if="bbgPanes.right3 === 'v0_exposure' || bbgPanes.right3 === 'exposure'" :showHeader="false" :equity="Number(kpis?.total_equity) || 40272" @selectBot="handleOpenBotDrawer" />
              <ActivityPanel v-else-if="bbgPanes.right3 === 'v0_activity' || bbgPanes.right3 === 'activity'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <RiskPanel v-else-if="bbgPanes.right3 === 'v0_risk'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <V0EventFeed v-else-if="bbgPanes.right3 === 'v0_events'" :showHeader="false" @selectBot="handleOpenBotDrawer" />
              <V0Pipeline v-else-if="bbgPanes.right3 === 'v0_pipeline'" :showHeader="false" @selectBot="handleOpenBotDrawer" />

              <!-- Astra 原版卡片 -->
              <EquityDrawdownHero v-else-if="bbgPanes.right3 === 'equity'" :showHeader="false" :points="equityPoints" :kpis="kpis" :riskState="riskState" />
              <PositionsWidget v-else-if="bbgPanes.right3 === 'positions'" />
              <BotQueueWidget v-else-if="bbgPanes.right3 === 'bots'" :bots="botQueue" :showHeader="false" :period="botPeriod" mode="new" @selectBot="handleOpenBotDrawer" />
              <RiskStatusCard v-else-if="bbgPanes.right3 === 'risk'" :risk="riskState" :kpis="kpis" />
              <AllocationUnifiedWidget v-else-if="bbgPanes.right3 === 'donut'" :mode="allocationMode" :items="exposureItems" :showHeader="false" />
              <AuditTimeline v-else-if="bbgPanes.right3 === 'events'" :events="filteredAuditEvents" :showHeader="false" :compact="true" maxHeight="100%" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 另存版面方案對話框 (Save Layout Profile Modal) -->
    <div v-if="isSaveModalOpen" class="catos-modal-backdrop" @click.self="isSaveModalOpen = false">
      <div class="catos-modal-dialog">
        <div class="catos-modal-header">
          <div class="catos-modal-title">
            <span class="modal-title-icon">💾</span>
            <span class="text-white">另存為新版面方案</span>
          </div>
          <button type="button" class="btn-modal-close" @click="isSaveModalOpen = false">✕</button>
        </div>
        <div class="catos-modal-body">
          <p class="modal-desc">
            將目前自訂的卡片排序、分欄比例與呈現模式儲存為個人專屬方案。未來可隨時於頂部下拉選單一鍵秒級切換。
          </p>
          <div class="modal-field">
            <label class="modal-label text-white">方案名稱</label>
            <input
              v-model="newProfileName"
              type="text"
              class="input-profile-name"
              placeholder="例如：自訂短線高頻監控、持倉盯盤特化..."
              @keydown.enter="confirmSaveNewProfile"
              autofocus
            />
          </div>
        </div>
        <div class="catos-modal-footer">
          <button type="button" class="btn btn-sm btn-secondary" @click="isSaveModalOpen = false">取消</button>
          <button type="button" class="btn btn-sm btn-primary" @click="confirmSaveNewProfile">確認儲存</button>
        </div>
      </div>
    </div>

    <!-- V0 機器人詳情抽屜 (BotDrawer) -->
    <BotDrawer
      :bot="selectedDrawerBot"
      @close="selectedDrawerBot = null"
      @togglePause="handleToggleBotPause"
    />
  </div>
</template>

<style scoped>
/* 雙版本切換膠囊樣式 */
.version-switch-pill {
  display: inline-flex;
  align-items: center;
  background: #11141b;
  border: 1px solid #232834;
  border-radius: 3px;
  padding: 1px;
  gap: 1px;
  margin-right: 4px;
}

.btn-ver-pill {
  background: transparent;
  border: none;
  font-size: 10px;
  font-family: monospace;
  font-weight: 600;
  color: #64748b;
  padding: 1px 6px;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.btn-ver-pill:hover {
  color: #cbd5e1;
}

.btn-ver-pill.active {
  background: #1d2126;
  color: #e8b45e;
  border-color: #e8b45e;
}

.workspace-hybrid {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: #0c0f12;
  color: #e5e8ec;
  font-family: var(--default-font-family, "IBM Plex Sans", "Noto Sans TC", sans-serif);
  overflow: hidden;
}

/* Top Ribbon Header */
.hybrid-ribbon {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 10px;
  height: 32px;
  min-height: 32px;
  background: #0d1014;
  border-bottom: 1px solid #1c2025;
  font-size: 11px;
  gap: 8px;
  transition: all 0.2s ease;
  z-index: 10;
  box-sizing: border-box;
}

.hybrid-ribbon.ribbon-edit-active {
  background: #1d2126;
  border-bottom-color: #e8b45e;
}

.ribbon-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* 四大版面方案快捷按鈕群組 */
.quick-layout-pills {
  display: inline-flex;
  align-items: center;
  background: #111418;
  border: 1px solid #24282e;
  border-radius: 3px;
  padding: 1px;
  gap: 2px;
}

.layout-pill-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: transparent;
  border: 1px solid transparent;
  color: #8b949e;
  padding: 3px 8px;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.layout-pill-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #e5e8ec;
}

.layout-pill-btn.active {
  background: #1f242d;
  color: #e8b45e;
  border-color: rgba(232, 180, 94, 0.4);
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

.pill-icon {
  font-size: 11px;
  line-height: 1;
}

.pill-name {
  font-size: 11px;
}

.pill-ratio {
  font-size: 9px;
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 4px;
  border-radius: 2px;
  color: #64748b;
}

.layout-pill-btn.active .pill-ratio {
  background: rgba(232, 180, 94, 0.15);
  color: #e8b45e;
}

/* 全域風格切換按鈕群組 */
.quick-theme-switcher {
  display: inline-flex;
  align-items: center;
  background: #11141b;
  border: 1px solid #282c31;
  border-radius: 4px;
  padding: 2px;
  gap: 2px;
}

.btn-theme-toggle {
  background: transparent;
  border: 1px solid transparent;
  color: #8b949e;
  padding: 3px 8px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.btn-theme-toggle:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #e5e8ec;
}

.btn-theme-toggle.active {
  background: #1a221f;
  color: #65cba7;
  border-color: rgba(101, 203, 167, 0.4);
}

.ribbon-v-divider {
  width: 1px;
  height: 18px;
  background: #282c31;
  margin: 0 4px;
}

.ribbon-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* =========================================================================
   方案 A / B 全域即時分割線與拖曳換位樣式 (Splitter & Drag Reorder)
   ========================================================================= */
.bp-splitter-v {
  width: 6px;
  cursor: col-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 5;
  background: transparent;
  transition: background 0.15s ease;
  user-select: none;
  flex-shrink: 0;
}

.bp-splitter-v:hover,
.bp-splitter-v:active {
  background: rgba(255, 255, 255, 0.04);
}

.splitter-line-v {
  width: 1px;
  height: 100%;
  background: #282c31;
  transition: all 0.15s ease;
}

.bp-splitter-v:hover .splitter-line-v,
.bp-splitter-v:active .splitter-line-v {
  width: 2px;
  background: #e8b45e;
}

.bp-splitter-h {
  height: 6px;
  cursor: row-resize;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 5;
  background: transparent;
  transition: background 0.15s ease;
  user-select: none;
  flex-shrink: 0;
}

.bp-splitter-h:hover,
.bp-splitter-h:active {
  background: rgba(255, 255, 255, 0.04);
}

.splitter-line-h {
  width: 100%;
  height: 1px;
  background: #282c31;
  transition: all 0.15s ease;
}

.bp-splitter-h:hover .splitter-line-h,
.bp-splitter-h:active .splitter-line-h {
  height: 2px;
  background: #e8b45e;
}

/* 標題握把與拖曳視覺反饋 */
.is-draggable-grip {
  cursor: grab;
  user-select: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.is-draggable-grip:active {
  cursor: grabbing;
}

.grip-dots {
  color: #718096;
  font-size: 13px;
  line-height: 1;
  transition: color 0.15s ease;
}

.is-draggable-grip:hover .grip-dots {
  color: #ffffff;
}

/* 拖曳中與落點高亮效果 */
.is-drag-source {
  opacity: 0.45;
  border-style: dashed !important;
  border-color: rgba(255, 255, 255, 0.3) !important;
}

.is-drop-target {
  border-color: #e5ad35 !important;
  box-shadow: 0 0 12px rgba(229, 173, 53, 0.4) !important;
  position: relative;
}

.is-drop-target::after {
  content: 'DROP TO SWAP';
  position: absolute;
  top: 8px;
  right: 12px;
  font-size: 9px;
  font-weight: 800;
  color: #e5ad35;
  background: rgba(0, 0, 0, 0.7);
  padding: 2px 6px;
  border-radius: 2px;
  border: 1px solid rgba(229, 173, 53, 0.5);
  pointer-events: none;
  z-index: 10;
}

/* =========================================================================
   3 套整體架構藍圖切換按鈕組 (Blueprint Selector)
   ========================================================================= */
.blueprint-switch-group {
  display: inline-flex;
  align-items: center;
  background: rgba(15, 18, 24, 0.85);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 6px;
  padding: 2px;
  gap: 2px;
}

.btn-bp-switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  color: #a0aec0;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
}

.btn-bp-switch:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
}

.btn-bp-switch.active {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.22);
  color: #ffffff;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.4);
}

.btn-bp-switch.finalized-badge {
  background: rgba(229, 173, 53, 0.12);
  border-color: rgba(229, 173, 53, 0.4);
  cursor: default;
}

.btn-bp-switch.finalized-badge .bp-badge {
  background: rgba(229, 173, 53, 0.2);
  color: #fbbf24;
}

.bp-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.bp-dot-gold { background: #e5ad35; box-shadow: 0 0 6px rgba(229, 173, 53, 0.6); }
.bp-dot-cyan { background: #38bdf8; box-shadow: 0 0 6px rgba(56, 189, 248, 0.6); }
.bp-dot-purple { background: #a855f7; box-shadow: 0 0 6px rgba(168, 85, 247, 0.6); }

.bp-label {
  font-family: var(--font-sans);
  color: #ffffff;
}

.bp-badge {
  font-size: 9px;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
  font-family: var(--font-mono);
}

.btn-bp-switch.active .bp-badge {
  background: rgba(255, 255, 255, 0.18);
  color: #ffffff;
}

.ribbon-v-divider {
  width: 1px;
  height: 20px;
  background: rgba(255, 255, 255, 0.12);
  margin: 0 4px;
}

/* =========================================================================
   方案 1：Bloomberg Terminal 典範【極致高密度平鋪工作台】
   ========================================================================= */
.bp-bloomberg-desk {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  min-height: 0;
  background: #0c0f12;
  overflow: hidden;
  gap: 4px;
  padding: 4px;
}

.bbg-grid-layout {
  display: flex;
  flex: 1;
  gap: 4px;
  min-height: 0;
  overflow: hidden;
}

.bbg-col-left {
  flex: 64 1 0px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  min-height: 0;
}

.bbg-col-right {
  flex: 36 1 0px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  min-height: 0;
}


.bbg-view-pill {
  font-size: 10px;
  font-family: var(--default-font-family, sans-serif);
  padding: 1px 5px;
  border-radius: 3px;
  letter-spacing: 0.2px;
  font-weight: 500;
  user-select: none;
  display: inline-flex;
  align-items: center;
  line-height: 1.2;
}

.bbg-view-pill.is-v0-tag {
  background: rgba(144, 150, 157, 0.12);
  color: #9ea4ab;
  border: 1px solid rgba(144, 150, 157, 0.25);
}

.bbg-view-pill.is-astra-tag {
  background: rgba(232, 180, 94, 0.12);
  color: #e8b45e;
  border: 1px solid rgba(232, 180, 94, 0.35);
}

.bbg-card {
  background: #13161a;
  border: 1px solid #24282e;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-radius: 4px;
}

.bbg-card-header {
  height: 28px;
  min-height: 28px;
  background: #16191e;
  border-bottom: 1px solid #24282e;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
}

.bbg-card-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
}

.bbg-title-text {
  color: #e5e8ec;
  font-family: var(--default-mono-font-family, "IBM Plex Mono", monospace);
  letter-spacing: 0.2px;
}

.bbg-header-badge {
  font-size: 10px;
  color: #90969d;
  font-family: var(--default-mono-font-family, "IBM Plex Mono", monospace);
}

.bbg-card-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: #13161a;
}

/* 拖曳分割線或卡片時，停用內部圖表/表格指針事件與文字選取，確保 120 FPS 流暢度不掉幀 */
.workspace-hybrid.is-splitter-active .bbg-card-body,
.workspace-hybrid.is-dragging-active .bbg-card-body,
.workspace-hybrid.is-splitter-active iframe,
.workspace-hybrid.is-splitter-active svg,
.workspace-hybrid.is-splitter-active canvas {
  pointer-events: none !important;
  user-select: none !important;
}

.bbg-card-equity { flex: 54 1 0px; }
.bbg-card-positions { flex: 46 1 0px; }
.bbg-card-bots { flex: 40 1 0px; }
.bbg-card-donut { flex: 28 1 0px; }
.bbg-card-events { flex: 32 1 0px; }

/* =========================================================================
   方案 2：TradingView / VS Code 典範【主畫布 + 抽屜停靠工作台】
   ========================================================================= */
.bp-tradingview-desk {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: calc(100vh - 46px);
  background: #0b0e14;
  overflow: hidden;
}

.tv-metrics-bar {
  height: 42px;
  min-height: 42px;
  background: #10141d;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 10px;
}

.tv-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 11px;
}

.tv-pill-label {
  color: #718096;
}

.tv-pill-val {
  font-weight: 700;
}

.tv-pill-tag {
  font-size: 10px;
  color: #a0aec0;
}

.tv-right-toggle-wrap {
  margin-left: auto;
}

.btn-tv-dock-toggle {
  background: rgba(56, 189, 248, 0.1);
  border: 1px solid rgba(56, 189, 248, 0.3);
  color: #ffffff;
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-tv-dock-toggle:hover {
  background: rgba(56, 189, 248, 0.2);
  border-color: rgba(56, 189, 248, 0.5);
}

.tv-stage-wrap {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.tv-main-canvas {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.tv-card {
  background: #0f131c;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tv-card-header {
  height: 32px;
  min-height: 32px;
  background: #141924;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
}

.tv-title-main {
  font-size: 12px;
  font-weight: 700;
  margin-right: 8px;
}

.tv-subtitle {
  font-size: 10px;
  color: #718096;
}

.tv-card-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.tv-card-hero-chart {
  flex: 55 1 0px;
}

.tv-sub-panels {
  flex: 45 1 0px;
  display: flex;
  gap: 4px;
  min-height: 0;
}

.tv-panel-half {
  flex: 1;
  min-width: 0;
}

.tv-docked-sidebar {
  width: 320px;
  background: #0f131c;
  border-left: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}

.tv-dock-header {
  height: 32px;
  background: #141924;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  font-size: 11px;
  font-weight: 700;
}

.tv-dock-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.btn-dock-filter {
  background: transparent;
  border: 1px solid transparent;
  color: #718096;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
}

.btn-dock-filter.active {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  border-color: rgba(255, 255, 255, 0.2);
}

/* 底部升降抽屜 */
.tv-bottom-drawer {
  background: #11151e;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
  flex-shrink: 0;
}

.tv-drawer-bar {
  height: 32px;
  min-height: 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  cursor: pointer;
  background: #141924;
  user-select: none;
}

.tv-drawer-bar:hover {
  background: #19202e;
}

.tv-drawer-left {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  overflow: hidden;
}

.tv-drawer-title {
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.tv-drawer-preview {
  font-size: 11px;
  color: #a0aec0;
  max-width: 50vw;
  font-family: var(--font-mono);
}

.tv-drawer-right {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.btn-drawer-chevron {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 3px;
  padding: 2px 8px;
  font-size: 10px;
  font-weight: 600;
  cursor: pointer;
}

.tv-drawer-content {
  height: 200px;
  padding: 8px 12px;
  overflow: hidden;
  background: #0d1017;
}

/* =========================================================================
   方案 3：Linear / Grafana 典範【時間聯動 + 指令驅動工作台】
   ========================================================================= */
.bp-linear-desk {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: calc(100vh - 46px);
  background: #0a0d13;
  overflow: hidden;
  gap: 4px;
  padding: 4px;
}

.linear-sync-toolbar {
  height: 38px;
  min-height: 38px;
  background: #10141d;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 16px;
}

.linear-sync-left {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.linear-sync-label {
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.linear-time-btns {
  display: inline-flex;
  gap: 3px;
}

.btn-linear-sync {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #a0aec0;
  font-size: 10px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-linear-sync:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.1);
}

.btn-linear-sync.active {
  background: rgba(168, 85, 247, 0.2);
  border-color: rgba(168, 85, 247, 0.5);
  color: #ffffff;
  font-weight: 700;
}

.linear-search-box {
  flex: 1;
  max-width: 380px;
  position: relative;
  display: flex;
  align-items: center;
}

.linear-search-icon {
  position: absolute;
  left: 8px;
  font-size: 11px;
  opacity: 0.6;
}

.input-linear-search {
  width: 100%;
  background: #0a0d13;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 4px;
  padding: 4px 24px 4px 26px;
  font-size: 11px;
  color: #ffffff;
  outline: none;
  transition: border-color 0.2s ease;
}

.input-linear-search:focus {
  border-color: rgba(168, 85, 247, 0.6);
  box-shadow: 0 0 6px rgba(168, 85, 247, 0.2);
}

.btn-clear-search {
  position: absolute;
  right: 6px;
  background: transparent;
  border: none;
  color: #718096;
  cursor: pointer;
  font-size: 10px;
}

.linear-view-controls {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.linear-control-label {
  font-size: 11px;
  color: #718096;
}

.btn-linear-view {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #a0aec0;
  font-size: 10px;
  padding: 3px 8px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-linear-view.active {
  background: rgba(255, 255, 255, 0.15);
  border-color: rgba(255, 255, 255, 0.3);
  color: #ffffff;
  font-weight: 700;
}

.linear-row-upper {
  flex: 48 1 0px;
  display: flex;
  gap: 4px;
  min-height: 0;
}

.linear-row-lower {
  flex: 52 1 0px;
  display: flex;
  gap: 4px;
  min-height: 0;
}

.linear-card {
  background: #0f131c;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.linear-card-header {
  height: 32px;
  min-height: 32px;
  background: #141924;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
}

.linear-card-title {
  font-size: 11px;
  font-weight: 700;
  color: #ffffff;
}

.linear-card-tag {
  font-size: 10px;
  color: #a0aec0;
  font-family: var(--font-mono);
}

.linear-card-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.linear-card-equity { flex: 60 1 0px; }
.linear-card-dual-gauges { flex: 40 1 0px; }
.linear-card-bots-grid { flex: 60 1 0px; }
.linear-card-events { flex: 40 1 0px; }

.linear-dual-body {
  display: flex;
  flex-direction: row;
}

.dual-gauge-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid rgba(255, 255, 255, 0.05);
}

.dual-gauge-col:last-child {
  border-right: none;
}

/* Bento Matrix Grid */
.linear-bento-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 8px;
  padding: 8px;
  overflow-y: auto;
}

.bento-bot-tile {
  background: #121722;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.bento-bot-tile:hover {
  background: #171d2b;
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.3);
}

.bento-tile-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.bento-symbol-group {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.bento-symbol {
  font-size: 12px;
  font-weight: 700;
  font-family: var(--font-mono);
}

.bento-strat-tag {
  font-size: 10px;
  padding: 1px 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  color: #cbd5e1;
}

.bento-tile-data {
  display: flex;
  justify-content: space-between;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 4px;
  padding: 6px 8px;
}

.bento-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.bento-metric-lbl {
  font-size: 9px;
  color: #718096;
}

.bento-metric-val {
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-mono);
}

.bento-tile-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 10px;
  color: #a0aec0;
}

.bento-action-btn {
  font-size: 10px;
  color: #38bdf8;
  font-weight: 600;
}

.linear-table-view {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.ribbon-layout-label {
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  user-select: none;
  display: inline-flex;
  align-items: center;
}

.preset-dot {
  font-size: 11px;
  margin-right: 4px;
  color: var(--text-muted);
  opacity: 0.6;
}

.preset-btn.active .preset-dot {
  color: var(--accent);
  opacity: 1;
}

/* View/Edit State Pills */
.view-state-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 1px 8px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  color: var(--text-muted);
}

.lock-icon {
  font-size: 10px;
}

.edit-state-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  padding: 1px 8px;
  background: var(--accent-subtle);
  border: 1px solid var(--accent-border);
  border-radius: 12px;
  color: var(--accent);
  font-weight: 600;
}

.edit-pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  opacity: 0.9;
}

/* Preset Switcher Pills */
.preset-pill-group {
  display: flex;
  align-items: center;
  gap: 3px;
  background: var(--bg-base);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  padding: 2px 4px;
}

.preset-group-label {
  font-size: 10px;
  color: var(--text-muted);
  margin-left: 2px;
}

.preset-btn {
  background: transparent;
  border: none;
  font-size: 11px;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: all 0.15s ease;
}

.preset-btn:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.04);
}

.preset-btn.active {
  background: var(--accent-subtle);
  color: var(--accent);
  font-weight: 600;
  border: 1px solid var(--accent-border);
}

.cat-tag-badge {
  background: #1e2433;
  color: #f1f5f9;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  margin-right: 6px;
  display: inline-block;
}

.cat-tag-desc {
  font-size: 11.5px;
  color: rgba(255, 255, 255, 0.65);
  font-weight: 400;
}

.btn-enter-edit {
  border-color: var(--accent-border);
  color: var(--accent);
  font-weight: 600;
}

.btn-enter-edit:hover {
  background: var(--accent-subtle);
}

.btn-done-edit {
  font-weight: 700;
}

/* Edit Mode Interactive Guide Bar */
.edit-mode-guide-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px var(--space-4);
  background: var(--accent-subtle);
  border-bottom: 1px solid var(--accent-border);
  font-size: 11px;
  color: var(--text-secondary);
  z-index: 10;
}

.guide-icon {
  margin-right: 6px;
}

.guide-text {
  flex: 1;
}

.guide-text strong {
  color: var(--accent);
}

.btn-guide-close {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  padding: 2px 6px;
}

.btn-guide-close:hover {
  color: var(--accent);
}

/* Floating Toast Notification */
.catos-workspace-toast {
  position: fixed;
  top: 48px;
  right: 20px;
  z-index: 100001;
  padding: 6px 14px;
  background: rgba(14, 18, 24, 0.94);
  border: 1px solid var(--accent);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.8), 0 0 12px rgba(212, 175, 55, 0.25);
  border-radius: var(--radius-xs);
  color: #fff;
  font-size: 11.5px;
  font-weight: 500;
  pointer-events: none;
  display: flex;
  align-items: center;
  gap: 6px;
  animation: toastFadeIn 0.2s ease-out;
}

.toast-diamond {
  color: var(--accent);
  font-size: 10px;
}

@keyframes toastFadeIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Error Banner */
.alert-banner-danger {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.4);
  padding: 10px var(--space-4);
  margin: var(--space-2) var(--space-4) 0;
  border-radius: var(--radius-sm);
  color: #fca5a5;
  font-size: var(--text-xs);
}

.alert-icon {
  font-size: 18px;
}



@keyframes pulseLaserGuide {
  0% {
    opacity: 0.75;
    filter: drop-shadow(0 0 4px rgba(230, 184, 64, 0.6));
  }
  100% {
    opacity: 1;
    filter: drop-shadow(0 0 14px rgba(255, 215, 0, 0.95));
  }
}

/* High-Fidelity Floating REORDER Ghost Card */
.catos-drag-ghost-card {
  position: fixed;
  pointer-events: none;
  z-index: 100000;
  width: 230px;
  background: rgba(14, 18, 26, 0.92);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(212, 175, 55, 0.75);
  border-radius: var(--radius-xs);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.85), 0 0 16px rgba(212, 175, 55, 0.25);
  padding: 9px 12px;
  transform: translate(14px, 14px) rotate(1.5deg);
  user-select: none;
}

.ghost-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}

.ghost-tag {
  font-size: 9.5px;
  font-weight: 700;
  color: #ffd700;
  background: rgba(212, 175, 55, 0.18);
  padding: 1px 5px;
  border-radius: 2px;
  font-family: var(--font-mono);
  letter-spacing: 0.5px;
}

.ghost-en {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.ghost-title {
  font-size: 12.5px;
  font-weight: 600;
  color: #ffffff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Main Tiling Layout Structure */
.tiling-grid-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: var(--space-3);
  gap: var(--space-2);
  overflow: hidden;
  height: 100%;
}

.kpi-tier-wrapper {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  gap: 0;
}

.tiling-kpi-row {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 0;
  width: 100%;
  min-height: 72px;
  max-height: 240px;
  overflow: hidden;
  position: relative;
  flex-shrink: 0;
}

.tiling-kpi-item {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  border: 1px solid var(--border-secondary);
  box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.05), 0 4px 12px rgba(0, 0, 0, 0.4);
  transition: opacity 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
}

.tiling-kpi-item.is-editing {
  border: 1px dashed var(--accent-border);
}

.tiling-kpi-item.is-editing:hover {
  border-color: var(--accent);
}

.tiling-kpi-item.is-dragging-card {
  opacity: 0.32 !important;
  border: 1px dashed var(--accent) !important;
  background: rgba(10, 14, 20, 0.55) !important;
  transform: scale(0.995);
  box-shadow: inset 0 0 24px rgba(0, 0, 0, 0.7) !important;
}

.tiling-kpi-item.just-landed {
  animation: justLandedPulse 0.6s ease-out;
}

.kpi-card-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 8px;
  background: var(--accent-subtle);
  border-bottom: 1px dashed var(--accent-border);
  font-size: 10.5px;
  cursor: grab;
  user-select: none;
}

.kpi-card-toolbar:active {
  cursor: grabbing;
}

.kpi-toolbar-title {
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kpi-toolbar-badge {
  font-size: 9.5px;
  color: var(--text-muted);
  background: rgba(0, 0, 0, 0.4);
  padding: 1px 4px;
  border-radius: 2px;
}

.kpi-card-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.kpi-card-content :deep(.kpi-card) {
  height: 100%;
  margin: 0;
  border: none;
  border-radius: 0;
  box-shadow: none;
  padding: 8px 12px;
  gap: 3px;
  justify-content: center;
}

.kpi-bottom-splitter {
  margin-top: 2px;
  margin-bottom: 2px;
}

/* Scheme 3: Compact Capsule Row */
.tiling-kpi-capsule-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  height: 44px;
  min-height: 44px;
  padding: 0;
  flex-shrink: 0;
  overflow-x: auto;
  overflow-y: hidden;
}

.kpi-capsule-item {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  white-space: nowrap;
  user-select: none;
  transition: all 0.2s ease;
  min-width: 170px;
}

.kpi-capsule-item.accent-border { border-left: 3px solid var(--accent); }
.kpi-capsule-item.success-border { border-left: 3px solid var(--success); }
.kpi-capsule-item.danger-border { border-left: 3px solid var(--danger); }
.kpi-capsule-item.warning-border { border-left: 3px solid var(--warning); }

.kpi-capsule-item.is-editing {
  cursor: grab;
  border-style: dashed;
  border-color: var(--accent-border);
}

.kpi-capsule-item.is-editing:hover {
  border-color: var(--accent);
  background: var(--accent-subtle);
}

.kpi-capsule-item.is-dragging-card {
  opacity: 0.35;
  transform: scale(0.98);
}

.kpi-capsule-item.just-landed {
  animation: justLandedPulse 0.6s ease-out;
}

.capsule-label {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 500;
}

.capsule-value {
  font-weight: 700;
  font-size: 12.5px;
  color: #ffffff;
}

.capsule-unit {
  font-size: 10px;
  color: var(--text-muted);
}

.capsule-sub {
  font-size: 10px;
  margin-left: auto;
  font-family: var(--font-mono);
}

.capsule-sub.pos { color: var(--success); }
.capsule-sub.neg { color: var(--danger); }
.capsule-sub.neutral { color: var(--text-muted); }



.tiling-main-viewport {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: transparent;
  border: none;
  box-shadow: none;
  position: relative;
}

.tiling-row-tier {
  display: flex;
  width: 100%;
  min-height: 0;
  gap: 0;
  overflow: hidden;
  position: relative;
  transition: outline 0.2s ease, background 0.2s ease;
}

.tiling-row-tier.drop-target-tier {
  outline: 1.5px dashed var(--accent);
  outline-offset: -2px;
  background: var(--accent-subtle);
}

/* Card Pane (獨立實體卡片，邊框與倒角對齊舊版與 KPI 卡片) */
.tiling-pane {
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
  min-height: 0;
  background: var(--bg-surface);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.05), 0 4px 12px rgba(0, 0, 0, 0.4);
  transition: opacity 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
  container-type: size;
  container-name: tile;
}

.tiling-pane:hover {
  border-color: var(--border-subtle);
}

.tiling-pane.is-editing {
  border: 1px dashed var(--accent-border);
}

.tiling-pane.is-editing:hover {
  border-color: var(--accent);
}

.tiling-pane.is-dragging-card {
  opacity: 0.32 !important;
  border: 1px dashed rgba(212, 175, 55, 0.75) !important;
  background: rgba(10, 14, 20, 0.55) !important;
  transform: scale(0.995);
  box-shadow: inset 0 0 24px rgba(0, 0, 0, 0.7) !important;
}

.tiling-pane.is-dragging-card > * {
  pointer-events: none !important;
}

.tiling-pane.just-landed {
  animation: justLandedPulse 0.6s ease-out;
}

@keyframes justLandedPulse {
  0% {
    border-color: var(--accent);
    background-color: var(--accent-subtle);
  }
  100% {
    border-color: var(--border-secondary);
    background-color: var(--bg-surface);
  }
}

.pane-inner {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.widget-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 28px;
  min-height: 28px;
  padding: 0 8px;
  background: var(--bg-surface-elevated);
  border-bottom: 1px solid var(--border-secondary);
  font-size: 11px;
  user-select: none;
}

.widget-toolbar.is-draggable {
  cursor: grab;
}

.widget-toolbar.is-draggable:active {
  cursor: grabbing;
}

.toolbar-drag-grip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: var(--text-secondary);
}

.grip-dots {
  color: var(--accent);
  font-size: 13px;
  line-height: 1;
}

.widget-title-text {
  font-size: 11px;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Range Picker inside Toolbar (7D / 30D / 90D) */
.toolbar-range-picker {
  display: inline-flex;
  align-items: center;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: var(--radius-xs);
  padding: 1px;
  gap: 1px;
}

.toolbar-range-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 10px;
  font-family: var(--font-mono);
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 2px;
  cursor: pointer;
  line-height: 14px;
  transition: all 0.12s ease;
}

.toolbar-range-btn:hover {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.08);
}

.toolbar-range-btn.active {
  color: var(--accent);
  background: var(--accent-subtle);
  font-weight: 700;
}

.toolbar-actions .badge-xs {
  font-size: 9.5px;
  padding: 1px 6px;
  line-height: 14px;
  letter-spacing: 0.3px;
  border-radius: 3px;
}

.btn-tool {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-xs);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 11px;
  transition: all 0.15s ease;
}

.btn-tool:hover {
  color: var(--accent);
  border-color: var(--accent-border);
  background: var(--accent-subtle);
}

.btn-tool-hide:hover {
  color: var(--color-danger);
  border-color: var(--color-danger-border);
  background: var(--color-danger-bg);
}

.pane-content-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  min-width: 0;
  min-height: 0;
  container-type: size;
  container-name: pane-body;
}

/* 徹底杜絕多層重複標題：卡片工具列已統一管理品名與快捷操作，卡內冗餘 Header 完全隱藏 */
.pane-content-body :deep(.card-header) {
  display: none !important;
}

/* 消除卡片嵌套的雙重背景與邊框擠壓，讓各圖表自然融入 Tiling 網格面板 */
.pane-content-body :deep(.card) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  height: 100% !important;
}

.pane-scrollable-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

/* Metric Cards inside Tiling Panes (頂部結構化對齊、共用數值基線、有界字級) */
.pane-content-body :deep(.kpi-card) {
  height: 100%;
  width: 100%;
  margin: 0;
  background: transparent;
  border: none;
  box-shadow: none;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: stretch;
  box-sizing: border-box;
  padding: 10px 14px 12px 14px;
  gap: 3px;
  overflow: hidden;
}

/* 隱藏重複標題：卡片工具列已清晰標示品名，移除卡內冗餘重複文字釋放高度 */
.pane-content-body :deep(.kpi-label) {
  display: none !important;
}

/* 數值列：排版流暢居左、基線對齊、禁止折行截斷 */
.pane-content-body :deep(.kpi-value-row) {
  display: flex;
  align-items: baseline;
  gap: 6px;
  width: 100%;
  overflow: hidden;
  line-height: 1.15;
  margin-top: 2px;
  margin-bottom: 4px;
  flex-shrink: 0;
}

/* 主數值：帳戶權益 26px，其餘 20px，穩定清晰 */
.pane-content-body :deep(.kpi-value) {
  font-size: 20px;
  font-weight: 500;
  font-family: var(--default-mono-font-family, "IBM Plex Mono", monospace);
  line-height: 1.15;
  color: var(--foreground, #e5e8ec);
  white-space: nowrap;
}

.pane-content-body :deep(.kpi-value.equity-val) {
  font-size: 26px;
  color: var(--foreground, #e5e8ec);
}

/* 單位文字：對齊基線 */
.pane-content-body :deep(.kpi-unit) {
  font-size: 11px;
  font-weight: 400;
  color: var(--muted-foreground, #90969d);
  font-family: var(--default-mono-font-family, "IBM Plex Mono", monospace);
  white-space: nowrap;
}

/* 說明輔助文字：單行防截斷保護 */
.pane-content-body :deep(.kpi-sub) {
  font-size: 11px;
  font-weight: 400;
  line-height: 1.45;
  color: var(--muted-foreground, #90969d);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
  flex-shrink: 0;
}

/* Splitter Bars (Continuous Physical Splitters: 精確 8px 實體分割縫隙，100% 絕對均勻等於 8px) */
.splitter {
  background: transparent;
  position: relative;
  z-index: 25;
  flex-shrink: 0;
  user-select: none;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 垂直分割條：實體 8px 寬度，左右卡片淨間距精確等於 8px */
.splitter.vertical {
  width: 8px !important;
  min-width: 8px !important;
  max-width: 8px !important;
  height: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
  cursor: col-resize;
  border: none !important;
  position: relative;
}

/* 中央 2px 科技金指示線 (居中於 8px 之中：left 3px, width 2px, right 3px) */
.splitter.vertical::after {
  content: "";
  position: absolute;
  top: 0;
  bottom: 0;
  left: 3px;
  width: 2px;
  border-radius: 1px;
  background-color: transparent;
  pointer-events: none;
  transition: background-color 0.15s ease, box-shadow 0.15s ease;
}

/* 水平分割條：實體 8px 高度，上下卡片淨間距精確等於 8px */
.splitter.horizontal {
  height: 8px !important;
  min-height: 8px !important;
  max-height: 8px !important;
  width: 100% !important;
  margin: 0 !important;
  padding: 0 !important;
  cursor: row-resize;
  border: none !important;
  position: relative;
}

/* 中央 2px 科技金指示線 (居中於 8px 之中：top 3px, height 2px, bottom 3px) */
.splitter.horizontal::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: 3px;
  height: 2px;
  border-radius: 1px;
  background-color: transparent;
  pointer-events: none;
  transition: background-color 0.15s ease, box-shadow 0.15s ease;
}

/* 懸停與拖曳時，在 8px 間隙正中央點亮科技金指示線 */
.splitter.vertical:hover::after,
.splitter.vertical:active::after,
.splitter.horizontal:hover::after,
.splitter.horizontal:active::after {
  background-color: var(--accent);
  opacity: 0.9;
}

.splitter-line,
.splitter-grip {
  display: none !important;
}

/* Event, Bot, Task, Yaozi Rows */
.hybrid-event-row {
  padding: 6px 8px;
  border-bottom: 1px solid var(--border-secondary);
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.hybrid-event-row:hover {
  background: rgba(255, 255, 255, 0.02);
}

.event-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
}

.event-time {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--text-muted);
}

.event-msg {
  color: var(--text-secondary);
}

.event-detail-box {
  margin-top: 4px;
  padding: 4px 6px;
  background: var(--bg-base);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
  font-size: 10px;
  color: var(--text-muted);
}

.hybrid-bot-row, .hybrid-task-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border, #282c31);
  font-size: 11px;
  transition: background-color 0.12s ease;
}

.hybrid-bot-row:hover, .hybrid-task-row:hover {
  background-color: var(--bg-surface-hover, #1d2126);
}

.bot-info-main, .task-info-main {
  display: flex;
  align-items: center;
  gap: 7px;
}

.bot-name, .task-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--foreground, #e5e8ec);
}

.bot-sym {
  font-size: 10px;
  color: var(--muted-foreground, #90969d);
  font-family: var(--default-mono-font-family, "IBM Plex Mono", monospace);
}

.bot-info-sub, .task-info-sub {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hybrid-yaozi-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border, #282c31);
  font-size: 11px;
  line-height: 1.5;
  transition: background-color 0.12s ease;
}

.hybrid-yaozi-row:hover {
  background-color: var(--bg-surface-hover, #1d2126);
}

/* Maximized Overlay */
.maximized-overlay {
  position: absolute;
  top: 36px;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--bg-base);
  z-index: 100;
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
}

.maximized-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-secondary);
  margin-bottom: var(--space-3);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.maximized-label {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--accent);
}

.pane-name {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.maximized-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Widget Drawer Modal */
.widget-drawer-backdrop {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(4px);
  z-index: 150;
  display: flex;
  justify-content: flex-end;
}

.widget-drawer {
  width: 360px;
  height: 100%;
  background: var(--bg-surface-elevated);
  border-left: 1px solid var(--border-primary);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  animation: slideInRight 0.2s ease-out;
}

@keyframes slideInRight {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-secondary);
}

.drawer-title {
  display: flex;
  flex-direction: column;
  font-weight: 700;
  color: var(--text-primary);
}

.drawer-sub {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: normal;
}

.btn-drawer-close {
  background: transparent;
  border: none;
  font-size: 14px;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
}

.btn-drawer-close:hover {
  color: var(--text-primary);
}

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.drawer-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: var(--bg-base);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}

.drawer-item:hover {
  border-color: var(--accent-border);
  background: var(--bg-surface);
}

.drawer-item.active {
  border-color: var(--accent-border);
}

.drawer-item-checkbox input {
  accent-color: var(--accent);
  cursor: pointer;
}

.drawer-item-info {
  flex: 1;
}

.drawer-item-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.drawer-item-desc {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 2px;
}

.drawer-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-secondary);
  background: var(--bg-surface);
}

/* Helper Utilities */
.btn-xs {
  padding: 2px 7px;
  font-size: 11px;
}

.btn-outline-gold {
  background: transparent;
  border: 1px solid var(--accent-border);
  color: var(--accent);
  font-size: 11px;
  padding: 2px 7px;
  border-radius: var(--radius-xs);
  cursor: pointer;
}

.btn-outline-gold:hover {
  background: var(--accent-subtle);
}

/* =========================================================================
   Finalized Scheme 1: Dynamic Ghost Slot Tile (Linear / TradingView Style)
   ========================================================================= */
.ghost-slot-tile {
  position: relative;
  flex: 0 0 170px !important;
  min-width: 170px !important;
  max-width: 170px !important;
  height: 100% !important;
  margin: 0 4px !important;
  border: 1.5px dashed var(--accent);
  background: rgba(245, 158, 11, 0.08);
  border-radius: var(--radius-sm);
  z-index: 40;
  pointer-events: none;
  overflow: hidden;
  animation: expandGhostSlot 0.24s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

@keyframes expandGhostSlot {
  0% {
    flex-basis: 0px;
    max-width: 0px;
    opacity: 0;
    transform: scaleX(0.7);
  }
  100% {
    flex-basis: 170px;
    max-width: 170px;
    opacity: 1;
    transform: scaleX(1);
  }
}

.ghost-slot-inner {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 8px;
  text-align: center;
}

.ghost-slot-laser {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, #ffd700, transparent);
  animation: pulseLaserGuide 1s infinite alternate;
}

.ghost-slot-tag {
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  color: var(--accent);
  background: var(--accent-subtle);
  border: 1px solid var(--accent-border);
  border-radius: 2px;
  padding: 1px 6px;
  letter-spacing: 0.5px;
}

.ghost-slot-title {
  font-size: 11.5px;
  font-weight: 600;
  color: #ffffff;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ghost-slot-hint {
  font-size: 10px;
  color: var(--accent);
  opacity: 0.85;
}

.sub-title-tag {
  font-size: 10px;
  color: #64748b;
  letter-spacing: 0.8px;
}

.btn-text-gold {
  background: transparent;
  border: none;
  color: #eab308;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  padding: 0 4px;
  margin-right: 4px;
  transition: all 0.15s ease;
}

.btn-text-gold:hover {
  color: #facc15;
  text-decoration: underline;
}

/* Master Compare Global Switcher */
.master-compare-picker {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 4px;
  padding: 2px 4px;
  backdrop-filter: blur(8px);
}

.compare-label {
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
  padding: 0 4px;
  letter-spacing: 0.3px;
}

.compare-tab-btn {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 3px;
  color: #94a3b8;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  cursor: pointer;
  transition: all 0.15s ease;
  line-height: 1.4;
}

.compare-tab-btn:hover {
  color: #f1f5f9;
  background: rgba(255, 255, 255, 0.04);
}

/* =========================================================================
   Market Intel Professional News Feed (彭博終端 / Linear 級別：單標籤+時間，結構清晰耐看，0 跑版)
   ========================================================================= */
.market-intel-stream {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px;
}

.market-intel-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: var(--radius-sm, 4px);
  transition: background-color 0.14s ease, border-color 0.14s ease;
}

.market-intel-item:hover {
  background: rgba(255, 255, 255, 0.04);
  border-color: rgba(255, 255, 255, 0.09);
}

.intel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 2px;
}

/* 啞光純色微標籤（零發光、低飽和度底色、微邊框） */
.intel-tag {
  display: inline-flex;
  align-items: center;
  font-size: 10px;
  font-weight: 500;
  line-height: 1.2;
  padding: 1.5px 5.5px;
  border-radius: 3px;
  letter-spacing: 0.2px;
  white-space: nowrap;
}

.intel-tag.tag-rate {
  background: rgba(217, 119, 6, 0.14);
  color: #f59e0b;
  border: 1px solid rgba(217, 119, 6, 0.28);
}

.intel-tag.tag-whale {
  background: rgba(99, 102, 241, 0.14);
  color: #818cf8;
  border: 1px solid rgba(99, 102, 241, 0.28);
}

.intel-tag.tag-chain {
  background: rgba(16, 185, 129, 0.14);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.28);
}

.intel-tag.tag-macro {
  background: rgba(148, 163, 184, 0.14);
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.25);
}

.intel-time {
  font-size: 10px;
  color: #64748b;
  font-family: var(--font-mono, monospace);
  flex-shrink: 0;
}

.intel-title {
  font-size: 11.5px;
  font-weight: 600;
  color: #f1f5f9;
  line-height: 1.4;
  word-break: break-word;
}

.intel-summary {
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.45;
  word-break: break-word;
}

/* =========================================================================
   專業金融交易終端與監控系統規範：即時脈衝通知提示（Radar Pulse Indicator）
   特性：
   - 徹底移除未讀數字，杜絕數字焦慮與排版抖動 (CLS = 0)
   - 字維持白色：異常標籤始終純白 (#ffffff)，不隨告警變色，保持字級冷靜
   - 即時脈衝效果：細緻同心水波紋擴散光環 (Ripple Ping)，周邊視覺即時捕捉
   - 嚴重度分級感知：WARN 琥珀金脈衝波 / CRITICAL 珊瑚紅脈衝波
   ========================================================================= */
.btn-anomaly-filter {
  display: inline-flex;
  align-items: center;
  gap: 4.5px;
  position: relative;
  color: #ffffff !important;
}

/* 文字始終維持白色 */
.btn-anomaly-filter .anomaly-label {
  color: #ffffff !important;
  font-weight: 600;
}

.btn-anomaly-filter:hover .anomaly-label,
.btn-anomaly-filter.active .anomaly-label {
  color: #ffffff !important;
}

/* 核心狀態指示微點 (Status Pip) */
.pip-indicator {
  width: 5.5px;
  height: 5.5px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-block;
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.pip-trailing {
  margin-left: 1px;
}

/* 即時脈衝核心點與雷達波紋容器 */
.pip-radar {
  position: relative;
}

.pip-radar.pip-warn {
  background-color: #f59e0b;
  box-shadow: 0 0 3px rgba(245, 158, 11, 0.5);
}

.pip-radar.pip-critical {
  background-color: #f87171;
  box-shadow: 0 0 4px rgba(248, 113, 113, 0.6);
}

/* 即時脈衝光環 (Ripple Ping) */
.radar-ping {
  position: absolute;
  inset: -1.5px;
  border-radius: 50%;
  pointer-events: none;
}

.pip-warn .radar-ping {
  border: 1.2px solid #f59e0b;
  animation: radar-wave-warn 1.8s cubic-bezier(0, 0, 0.2, 1) infinite;
}

.pip-critical .radar-ping {
  border: 1.2px solid #f87171;
  animation: radar-wave-crit 1.8s cubic-bezier(0, 0, 0.2, 1) infinite;
}

@keyframes radar-wave-warn {
  0% {
    transform: scale(0.9);
    opacity: 0.9;
  }
  80%, 100% {
    transform: scale(2.5);
    opacity: 0;
  }
}

@keyframes radar-wave-crit {
  0% {
    transform: scale(0.9);
    opacity: 0.9;
  }
  80%, 100% {
    transform: scale(2.5);
    opacity: 0;
  }
}

/* Active 狀態下維持微點清晰 */
.btn-anomaly-filter.active .pip-warn {
  box-shadow: 0 0 5px rgba(245, 158, 11, 0.85);
}

.btn-anomaly-filter.active .pip-critical {
  box-shadow: 0 0 6px rgba(248, 113, 113, 0.95);
}

/* =========================================================================
   鎖定模式保護：分割線完全鎖定、無指針互動、杜絕誤觸 (is-locked)
   ========================================================================= */
.bp-splitter-v.is-locked,
.bp-splitter-h.is-locked {
  cursor: default !important;
  pointer-events: none !important;
  opacity: 0.25;
}

.bp-splitter-v.is-locked:hover,
.bp-splitter-v.is-locked:active,
.bp-splitter-h.is-locked:hover,
.bp-splitter-h.is-locked:active {
  background: transparent !important;
}

.bp-splitter-v.is-locked .splitter-line-v,
.bp-splitter-h.is-locked .splitter-line-h {
  background: rgba(255, 255, 255, 0.08) !important;
  box-shadow: none !important;
  width: 1px !important;
  height: 100% !important;
}

/* =========================================================================
   版面方案切換器與存檔管理樣式 (Layout Profile Picker)
   ========================================================================= */
.layout-profile-picker {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #181c21;
  border: 1px solid #282c31;
  border-radius: 4px;
  padding: 2px 6px;
}

.profile-picker-label {
  font-size: 11px;
  font-weight: 500;
  color: #90969d;
  white-space: nowrap;
}

.select-layout-profile {
  background: #13161a;
  color: #e5e8ec;
  border: 1px solid #282c31;
  border-radius: 3px;
  padding: 2px 8px;
  font-size: 11px;
  font-family: var(--default-mono-font-family, "IBM Plex Mono", monospace);
  outline: none;
  cursor: pointer;
  max-width: 260px;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: border-color 0.15s ease;
}

.select-layout-profile:focus {
  border-color: #e8b45e;
  box-shadow: none;
}

.select-layout-profile option {
  background: #181c21;
  color: #e5e8ec;
}

.btn-outline-gold {
  background: #181c21;
  border: 1px solid #282c31;
  color: #e8b45e;
  font-weight: 600;
}

.btn-outline-gold:hover {
  background: #1d2126;
  border-color: #e8b45e;
  color: #ffffff;
}

.btn-outline-cyan {
  background: #181c21;
  border: 1px solid #282c31;
  color: #e5e8ec;
  font-weight: 500;
}

.btn-outline-cyan:hover {
  background: #1d2126;
  border-color: #282c31;
  color: #ffffff;
}

.btn-danger-outline {
  background: #181c21;
  border: 1px solid #282c31;
  color: #ed7665;
  font-weight: 600;
}

.btn-danger-outline:hover {
  background: rgba(237, 118, 101, 0.22);
  border-color: #ed7665;
  color: #ffffff;
}

/* =========================================================================
   另存版面方案 Modal 彈窗樣式 (Save Layout Profile Modal)
   ========================================================================= */
.catos-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99999;
  animation: modalFadeIn 0.18s ease-out;
}

.catos-modal-dialog {
  width: 90%;
  max-width: 440px;
  background: #181c21;
  border: 1px solid #282c31;
  border-radius: 6px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(232, 180, 94, 0.15);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: modalZoomIn 0.18s ease-out;
}

@keyframes modalFadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modalZoomIn {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.catos-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #181c21;
  border-bottom: 1px solid #282c31;
}

.catos-modal-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #e5e8ec;
}

.modal-title-icon {
  font-size: 15px;
}

.btn-modal-close {
  background: transparent;
  border: none;
  color: #90969d;
  font-size: 14px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.btn-modal-close:hover {
  color: #e5e8ec;
  background: #1d2126;
}

.catos-modal-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: #13161a;
}

.modal-desc {
  font-size: 12px;
  color: #90969d;
  line-height: 1.5;
  margin: 0;
}

.modal-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.modal-label {
  font-size: 11px;
  font-weight: 600;
  color: #e5e8ec;
}

.input-profile-name {
  background: #181c21;
  border: 1px solid #282c31;
  border-radius: 4px;
  padding: 8px 10px;
  font-size: 12px;
  color: #e5e8ec;
  outline: none;
  transition: border-color 0.2s ease;
}

.input-profile-name:focus {
  border-color: #e8b45e;
  box-shadow: 0 0 8px rgba(232, 180, 94, 0.3);
}

.catos-modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  background: #181c21;
  border-top: 1px solid #282c31;
}

/* 官方原版 CatOS 工作站 (原生轉編譯照搬) 容器與按鈕樣式 */
.bp-catos-native-desk {
  width: 100%;
  height: calc(100vh - 84px);
  min-height: 600px;
  background: #0d1117;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.catos-native-frame {
  width: 100%;
  height: 100%;
  border: none;
  background: #0d1117;
  display: block;
}

.bp-dot-emerald {
  background-color: #10b981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
}

.btn-bp-catos.active {
  background: rgba(16, 185, 129, 0.18) !important;
  border-color: rgba(16, 185, 129, 0.6) !important;
  color: #ffffff !important;
}

/* Card Header Segmented Controls (Unified Top-Right Tab Switchers) */
.card-header-segmented {
  display: inline-flex;
  align-items: center;
  background: #111418;
  border: 1px solid #24282e;
  border-radius: 4px;
  padding: 2px;
  gap: 2px;
}

.card-header-segmented .seg-btn {
  background: transparent;
  border: none;
  color: #9da4ad;
  font-size: 11px;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: 3px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.15s ease;
  white-space: nowrap;
  line-height: 1.2;
}

.card-header-segmented .seg-btn:hover {
  color: #ffffff;
  background: #161a20;
}

.card-header-segmented .seg-btn.active {
  background: #1c222b;
  color: var(--accent);
  font-weight: 700;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
}

.card-header-segmented .badge-num {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--accent);
  font-weight: 700;
}

.card-header-segmented .badge-num-risk {
  font-family: var(--font-mono);
  font-size: 9.5px;
  background: #ef4444;
  color: #ffffff;
  padding: 0 4px;
  border-radius: 10px;
  font-weight: 700;
  line-height: 14px;
}

</style>
