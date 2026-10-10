<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import MetricCard from '@/components/common/MetricCard.vue';
import SparklineArea from '@/components/common/SparklineArea.vue';
import DonutChart from '@/components/common/DonutChart.vue';
import RiskGauge from '@/components/common/RiskGauge.vue';
import StatusBadge from '@/components/common/StatusBadge.vue';
import EmptyState from '@/components/common/EmptyState.vue';
import { useDashboard } from '@/state/useDashboard';

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

const expandedEventId = ref<string | null>(null);
function toggleEvent(id: string) {
  expandedEventId.value = expandedEventId.value === id ? null : id;
}

// 1. Dual-Mode State: View Mode (Locked) vs. Edit Mode (Unlocked)
const isEditing = ref(
  typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('edit') === 'true'
);
const isDrawerOpen = ref(false);

type PresetKey = 'executive' | 'research' | 'sentinel';

interface WidgetMeta {
  id: string;
  title: string;
  en: string;
}

const WIDGETS_META: Record<string, WidgetMeta> = {
  equity: { id: 'equity', title: '帳戶淨值走勢', en: 'EQUITY TREND' },
  donut: { id: 'donut', title: '保證金與曝險配置', en: 'ALLOCATION' },
  events: { id: 'events', title: '重要事件時間軸', en: 'AUDIT EVENTS' },
  risk: { id: 'risk', title: '日損鎖存安全儀表', en: 'RISK SENTINEL' },
  bots: { id: 'bots', title: '運行中 Bot 隊列', en: 'ACTIVE BOTS' },
  research: { id: 'research', title: '近期研究任務', en: 'RESEARCH TASKS' },
  yaozi: { id: 'yaozi', title: 'Yaozi 市場情報', en: 'YAOZI INTEL' }
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
    lowerPanes: ['risk', 'bots', 'research', 'yaozi'],
    upperWeights: [48, 28, 24],
    lowerWeights: [32, 23, 23, 22],
    upperHeightPct: 56
  },
  research: {
    label: '策略研究 (Research Focus)',
    desc: '超大淨值走勢與回測研究任務居中 · 適合回測數據與模型分析',
    upperPanes: ['equity', 'research'],
    lowerPanes: ['bots', 'yaozi', 'donut', 'risk', 'events'],
    upperWeights: [68, 32],
    lowerWeights: [22, 22, 20, 18, 18],
    upperHeightPct: 60
  },
  sentinel: {
    label: '夜間監控 (Sentinel Patrol)',
    desc: '風控防線與異常審計時間軸置頂加寬 · 專注止損與系統異常警報',
    upperPanes: ['risk', 'events'],
    lowerPanes: ['equity', 'bots', 'donut', 'research', 'yaozi'],
    upperWeights: [50, 50],
    lowerWeights: [36, 18, 16, 15, 15],
    upperHeightPct: 48
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

const kpiPropsMap = computed<Record<string, { label: string; value: string; unit?: string; subText?: string; subType?: 'pos' | 'neg' | 'neutral'; borderType?: 'accent' | 'warning' | 'danger' | 'success' }>>(() => ({
  kpi_equity: {
    label: '總權益淨值',
    value: isUnavailable.value ? '— USDT' : (kpis.value?.total_equity ? kpis.value.total_equity + ' USDT' : '--'),
    subText: isUnavailable.value ? '服務離線 · 無法讀取' : ('實時持倉估值 + 現金餘額 (' + (kpis.value?.equity_change_pct || '0.00%') + ')'),
    subType: isUnavailable.value ? 'neg' : 'pos',
    borderType: isUnavailable.value ? 'danger' : 'accent'
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
    const validPreset: PresetKey = ['executive', 'research', 'sentinel'].includes(parsed.preset) ? parsed.preset : 'executive';

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

function applyPreset(key: PresetKey) {
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
    <!-- Top Executive Ribbon -->
    <div class="hybrid-ribbon" :class="{ 'ribbon-edit-active': isEditing }">
      <div class="ribbon-left">
        <span class="ribbon-layout-label font-mono">LAYOUT //</span>

        <!-- Preset Switcher Pill (Active in both modes) -->
        <div class="preset-pill-group">
          <button
            v-for="(cfg, key) in presetsMap"
            :key="key"
            type="button"
            :class="['preset-btn', { active: activePreset === key }]"
            @click="applyPreset(key as PresetKey)"
            :title="cfg.desc"
          >
            <span class="preset-dot">•</span>
            <span>{{ key === 'executive' ? '戰情總覽' : key === 'research' ? '策略研究' : '夜間監控' }}</span>
          </button>
        </div>


        <!-- Live State Indicator Badge (Only in Edit Mode) -->
        <span v-if="isEditing" class="edit-state-pill" title="編輯微調中：可直接按住標題拖曳換位、滑動分割線比例">
          <span class="edit-pulse-dot"></span>
          <span>版面微調中</span>
        </span>
      </div>

      <div class="ribbon-right">
        <!-- Edit Mode Exclusive Controls -->
        <template v-if="isEditing">
          <button
            type="button"
            class="btn btn-xs btn-outline-gold"
            @click="autoPack"
            title="一鍵自動對齊補滿 100% 無縫平衡比例，天生零空洞"
          >
            ⚡ 自動補滿
          </button>

          <button
            type="button"
            class="btn btn-xs btn-secondary"
            :disabled="undoStack.length <= 1"
            @click="undo"
            title="復原上一次版面調整"
          >
            ↶ 復原
          </button>

          <button
            type="button"
            class="btn btn-xs btn-secondary"
            @click="resetCurrentPreset"
            title="重設為當前預設的原始尺寸"
          >
            ↺ 重設
          </button>

          <button
            type="button"
            class="btn btn-xs btn-secondary"
            @click="isDrawerOpen = !isDrawerOpen"
            title="開啟元件庫抽屜，勾選顯示/隱藏卡片"
          >
            ＋ 元件庫 ({{ (7 - layout.hiddenPanes.length) }}/7)
          </button>

          <button
            type="button"
            class="btn btn-xs btn-primary btn-done-edit"
            @click="isEditing = false; isDrawerOpen = false; saveLayout()"
            title="儲存版面設定並鎖定為檢視模式"
          >
            ✓ 完成鎖定
          </button>
        </template>

        <!-- View Mode Unlock Button -->
        <template v-else>
          <button
            type="button"
            class="btn btn-xs btn-secondary btn-enter-edit"
            @click="isEditing = true"
            title="解鎖工作台：拖移排序、微調比例、增減卡片"
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
          <strong>微調小撇步：</strong> 按住標題拖曳換位 · 拖動分割線微調寬高 · 點擊「✓ 完成鎖定」固化
        </span>
      </div>
      <button type="button" class="btn-guide-close" @click="isEditing = false">鎖定 ✕</button>
    </div>

    <!-- Floating Toast Notification -->
    <div v-if="toastMessage" class="catos-workspace-toast">
      <span class="toast-diamond">◆</span>
      <span>{{ toastMessage }}</span>
    </div>

    <!-- Offline / Unavailable Error Alert Banner -->
    <div v-if="isUnavailable || error" class="alert-banner-danger">
      <div class="alert-icon">⚠️</div>
      <div class="alert-content">
        <strong>{{ error || '503 服務不可用：底座連線中斷或離線' }}</strong>
        <p>安全底線約束：禁止未知狀態轉零或正常。底座未確認連線前，禁止宣告安全並阻擋所有交易下單。</p>
      </div>
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
          <div class="card-header"><div class="card-title">重要事件時間軸 (聚焦流)</div></div>
          <div class="card-body events-body p-4">
            <div v-for="evt in auditEvents" :key="evt.id" class="event-item mb-2 p-2">
              <span class="badge badge-info mr-2">{{ evt.level }}</span>
              <span class="tabular-nums mr-2">{{ evt.timestamp }}</span>
              <span>{{ evt.message }}</span>
            </div>
          </div>
        </div>
        <div v-else-if="maximizedId === 'risk'" class="card h-full">
          <RiskGauge :risk="riskState" />
        </div>
        <div v-else-if="maximizedId === 'bots'" class="card h-full p-4">
          <div class="card-header"><div class="card-title">機器人詳細佇列</div></div>
          <div class="card-body p-4">
            <div v-for="b in botQueue" :key="b.bot_id" class="p-3 border-b border-border-secondary flex justify-between items-center">
              <div>
                <strong>{{ b.name }}</strong> ({{ b.symbol }})
                <div class="text-xs text-muted">ID: {{ b.bot_id }} · 狀態: {{ b.state }}</div>
              </div>
              <div>
                <span class="badge badge-accent mr-2">持倉 {{ b.position_contracts }} 張</span>
                <span class="tabular-nums text-success">{{ b.pnl_usdt }}</span>
              </div>
            </div>
          </div>
        </div>
        <div v-else-if="maximizedId === 'research'" class="card h-full p-4">
          <div class="card-header"><div class="card-title">研究與回測任務管理</div></div>
          <div class="card-body p-4">
            <div v-for="t in researchTasks" :key="t.id" class="p-3 border-b border-border-secondary">
              <strong>{{ t.name }}</strong> ({{ t.version }})
              <div class="text-xs text-muted">{{ t.description }} · 狀態: {{ t.status }} · Sharpe: {{ t.sharpe }}</div>
            </div>
          </div>
        </div>
        <div v-else-if="maximizedId === 'yaozi'" class="card h-full p-4">
          <div class="card-header"><div class="card-title">Yaozi 市場異動情報</div></div>
          <div class="card-body p-4">
            <div v-for="y in yaoziAlerts" :key="y.id" class="p-3 border-b border-border-secondary">
              <span class="badge badge-warning mr-2">{{ y.type }}</span>
              <strong>{{ y.title }}</strong> ({{ y.time }}): {{ y.summary }}
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

    <!-- Main Tier-Based Workstation (Zero Gaps, 100% Seamless Tiling) -->
    <div v-if="!maximizedId" class="tiling-grid-container">
      <!-- Main Workstation Viewport with Continuous Splitters -->
      <div class="tiling-main-viewport">
        <!-- Universal Top Tier (Seamless Tiles, Fully Resizable & Reorderable) -->
        <div
          id="tiling-top-tier"
          class="tiling-row-tier"
          :class="{
            'drop-target-tier': isCardDragging && dropTargetInfo?.tier === 'top' && (layout.topPanes?.length || 0) === 0
          }"
          :style="{ height: `calc(${layout.topHeightPct || 22}% - 4px)` }"
        >
          <template v-for="(paneId, idx) in layout.topPanes" :key="paneId">
            <!-- Dynamic Ghost Slot Preview Tile before card -->
            <div
              v-if="isCardDragging && dropTargetInfo?.tier === 'top' && dropTargetInfo?.index === idx"
              class="ghost-slot-tile"
            >
              <div class="ghost-slot-inner">
                <div class="ghost-slot-laser"></div>
                <span class="ghost-slot-tag">DROP TO INSERT</span>
                <span class="ghost-slot-title">{{ getWidgetMeta(draggedCardId!).title }}</span>
                <span class="ghost-slot-hint">放開即可插入</span>
              </div>
            </div>

            <div
              :id="`pane-${paneId}`"
              class="tiling-pane"
              :class="{
                'is-dragging-card': isCardDragging && draggedCardId === paneId,
                'just-landed': landedId === paneId,
                'is-editing': isEditing
              }"
              :style="{ flex: `${(layout.topWeights && layout.topWeights[idx]) || 1} 1 0px` }"
            >
              <div class="pane-inner">
                <div
                  class="widget-toolbar"
                  :class="{ 'is-draggable': isEditing }"
                  @mousedown="e => startCardDrag(paneId, e)"
                >
                  <div class="toolbar-drag-grip" :title="isEditing ? '按住拖曳重新排序或跨排插入' : getWidgetMeta(paneId).title">
                    <span v-if="isEditing" class="grip-dots">⋮⋮</span>
                    <span class="widget-title-text">{{ getWidgetMeta(paneId).title }}</span>
                  </div>
                  <div class="toolbar-actions">
                    <button v-if="!paneId.startsWith('kpi_')" type="button" class="btn-tool" @click="toggleMaximize(paneId)" title="最大化聚焦">↗</button>
                    <button v-if="isEditing" type="button" class="btn-tool btn-tool-hide" @click="hidePane(paneId)" title="隱藏此卡片">✕</button>
                  </div>
                </div>

                <div class="pane-content-body">
                  <MetricCard v-if="paneId.startsWith('kpi_')" v-bind="kpiPropsMap[paneId]" />
                  <SparklineArea v-else-if="paneId === 'equity'" :points="equityPoints" />
                  <DonutChart v-else-if="paneId === 'donut'" :items="exposureItems" centerValue="1,420.50" centerLabel="名義曝險 USDT" />
                  <div v-else-if="paneId === 'events'" class="pane-scrollable-body">
                    <div v-for="evt in auditEvents" :key="evt.id" class="hybrid-event-row" @click="toggleEvent(evt.id)">
                      <div class="event-meta">
                        <span :class="['badge badge-xs', evt.level === 'WARN' ? 'badge-warning' : 'badge-info']">{{ evt.level }}</span>
                        <span class="event-time">{{ evt.timestamp }}</span>
                      </div>
                      <div class="event-msg">{{ evt.message }}</div>
                      <div v-if="expandedEventId === evt.id" class="event-detail-box">
                        <code>{{ evt.details || 'Reconciliation check passed.' }}</code>
                      </div>
                    </div>
                  </div>
                  <RiskGauge v-else-if="paneId === 'risk'" :risk="riskState" />
                  <div v-else-if="paneId === 'bots'" class="pane-scrollable-body">
                    <div v-for="b in botQueue" :key="b.bot_id" class="hybrid-bot-row">
                      <div class="bot-info-main">
                        <span class="bot-name">{{ b.name }}</span>
                        <span class="bot-sym">{{ b.symbol }}</span>
                      </div>
                      <div class="bot-info-sub">
                        <span class="badge badge-xs badge-accent">持倉 {{ b.position_contracts }} 張</span>
                        <span class="bot-pnl tabular-nums text-success">{{ b.pnl_usdt }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="paneId === 'research'" class="pane-scrollable-body">
                    <div v-for="t in researchTasks" :key="t.id" class="hybrid-task-row">
                      <div class="task-info-main">
                        <span class="task-name">{{ t.name }}</span>
                        <span class="badge badge-xs badge-secondary">{{ t.version }}</span>
                      </div>
                      <div class="task-info-sub">
                        <span class="text-muted">Sharpe: {{ t.sharpe }}</span>
                        <span class="task-score text-accent">{{ t.status }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="paneId === 'yaozi'" class="pane-scrollable-body">
                    <div v-for="y in yaoziAlerts" :key="y.id" class="hybrid-yaozi-row">
                      <div class="yaozi-badge-col">
                        <span class="badge badge-xs badge-warning">{{ y.type }}</span>
                      </div>
                      <div class="yaozi-msg-col">
                        <strong>{{ y.title }}</strong>: {{ y.summary }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div
              v-if="idx < (layout.topPanes?.length || 0) - 1"
              class="splitter vertical"
              @pointerdown="e => startTierVerticalSplitDrag('top', idx, e)"
              @dblclick="() => resetTierVerticalSplits('top')"
              title="拖曳調整左右寬度 · 雙擊恢復均分"
            >
              <div class="splitter-line"></div>
              <div class="splitter-grip"></div>
            </div>
          </template>

          <!-- Dynamic Ghost Slot Preview at the end of Top Tier -->
          <div
            v-if="isCardDragging && dropTargetInfo?.tier === 'top' && dropTargetInfo?.index === (layout.topPanes?.length || 0)"
            class="ghost-slot-tile"
          >
            <div class="ghost-slot-inner">
              <div class="ghost-slot-laser"></div>
              <span class="ghost-slot-tag">DROP TO INSERT</span>
              <span class="ghost-slot-title">{{ getWidgetMeta(draggedCardId!).title }}</span>
              <span class="ghost-slot-hint">放開即可插入</span>
            </div>
          </div>
        </div>

        <!-- Continuous Horizontal Splitter Between Top and Upper Tiers -->
        <div
          class="splitter horizontal"
          @pointerdown="startTopHorizontalSplitDrag"
          @dblclick="resetTopHorizontalSplit"
          title="拖曳調整頂排高度比例 · 雙擊恢復預設 (22%)"
        >
          <div class="splitter-line"></div>
          <div class="splitter-grip horizontal"></div>
        </div>

        <!-- Tier 1: Upper Tier (Upper Row) -->
        <div
          id="tiling-upper-tier"
          class="tiling-row-tier"
          :class="{
            'drop-target-tier': isCardDragging && dropTargetInfo?.tier === 'upper' && layout.upperPanes.length === 0
          }"
          :style="{ height: `calc(${layout.upperHeightPct}% - 4px)` }"
        >
          <template v-for="(paneId, idx) in layout.upperPanes" :key="paneId">
            <!-- Dynamic Ghost Slot Preview Tile before card -->
            <div
              v-if="isCardDragging && dropTargetInfo?.tier === 'upper' && dropTargetInfo?.index === idx"
              class="ghost-slot-tile"
            >
              <div class="ghost-slot-inner">
                <div class="ghost-slot-laser"></div>
                <span class="ghost-slot-tag">DROP TO INSERT</span>
                <span class="ghost-slot-title">{{ getWidgetMeta(draggedCardId!).title }}</span>
                <span class="ghost-slot-hint">放開即可插入</span>
              </div>
            </div>

            <!-- Card Pane -->
            <div
              :id="`pane-${paneId}`"
              class="tiling-pane"
              :class="{
                'is-dragging-card': isCardDragging && draggedCardId === paneId,
                'just-landed': landedId === paneId,
                'is-editing': isEditing
              }"
              :style="{ flex: `${layout.upperWeights[idx] || 1} 1 0px` }"
            >
              <div class="pane-inner">
                <!-- Header Toolbar with Drag Surface -->
                <div
                  class="widget-toolbar"
                  :class="{ 'is-draggable': isEditing }"
                  @mousedown="e => startCardDrag(paneId, e)"
                >
                  <div class="toolbar-drag-grip" :title="isEditing ? '按住拖曳重新排序或跨排插入' : getWidgetMeta(paneId).title">
                    <span v-if="isEditing" class="grip-dots">⋮⋮</span>
                    <span class="widget-title-text">{{ getWidgetMeta(paneId).title }}</span>
                  </div>
                  <div class="toolbar-actions">
                    <button v-if="!paneId.startsWith('kpi_')" type="button" class="btn-tool" @click="toggleMaximize(paneId)" title="最大化聚焦">↗</button>
                    <button v-if="isEditing" type="button" class="btn-tool btn-tool-hide" @click="hidePane(paneId)" title="隱藏此卡片">✕</button>
                  </div>
                </div>

                <!-- Pane Content -->
                <div class="pane-content-body">
                  <MetricCard v-if="paneId.startsWith('kpi_')" v-bind="kpiPropsMap[paneId]" />
                  <SparklineArea v-else-if="paneId === 'equity'" :points="equityPoints" />
                  <DonutChart v-else-if="paneId === 'donut'" :items="exposureItems" centerValue="1,420.50" centerLabel="名義曝險 USDT" />
                  <div v-else-if="paneId === 'events'" class="pane-scrollable-body">
                    <div v-for="evt in auditEvents" :key="evt.id" class="hybrid-event-row" @click="toggleEvent(evt.id)">
                      <div class="event-meta">
                        <span :class="['badge badge-xs', evt.level === 'WARN' ? 'badge-warning' : 'badge-info']">{{ evt.level }}</span>
                        <span class="event-time">{{ evt.timestamp }}</span>
                      </div>
                      <div class="event-msg">{{ evt.message }}</div>
                      <div v-if="expandedEventId === evt.id" class="event-detail-box">
                        <code>{{ evt.details || 'Reconciliation check passed.' }}</code>
                      </div>
                    </div>
                  </div>
                  <RiskGauge v-else-if="paneId === 'risk'" :risk="riskState" />
                  <div v-else-if="paneId === 'bots'" class="pane-scrollable-body">
                    <div v-for="b in botQueue" :key="b.bot_id" class="hybrid-bot-row">
                      <div class="bot-info-main">
                        <span class="bot-name">{{ b.name }}</span>
                        <span class="bot-sym">{{ b.symbol }}</span>
                      </div>
                      <div class="bot-info-sub">
                        <span class="badge badge-xs badge-accent">持倉 {{ b.position_contracts }} 張</span>
                        <span class="bot-pnl tabular-nums text-success">{{ b.pnl_usdt }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="paneId === 'research'" class="pane-scrollable-body">
                    <div v-for="t in researchTasks" :key="t.id" class="hybrid-task-row">
                      <div class="task-info-main">
                        <span class="task-name">{{ t.name }}</span>
                        <span class="badge badge-xs badge-secondary">{{ t.version }}</span>
                      </div>
                      <div class="task-info-sub">
                        <span class="text-muted">Sharpe: {{ t.sharpe }}</span>
                        <span class="task-score text-accent">{{ t.status }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="paneId === 'yaozi'" class="pane-scrollable-body">
                    <div v-for="y in yaoziAlerts" :key="y.id" class="hybrid-yaozi-row">
                      <div class="yaozi-badge-col">
                        <span class="badge badge-xs badge-warning">{{ y.type }}</span>
                      </div>
                      <div class="yaozi-msg-col">
                        <strong>{{ y.title }}</strong>: {{ y.summary }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Vertical Splitter between cards -->
            <div
              v-if="idx < layout.upperPanes.length - 1"
              class="splitter vertical"
              @pointerdown="e => startTierVerticalSplitDrag('upper', idx, e)"
              @dblclick="() => resetTierVerticalSplits('upper')"
              title="拖曳調整左右寬度 · 雙擊恢復均分"
            >
              <div class="splitter-line"></div>
              <div class="splitter-grip"></div>
            </div>
          </template>

          <!-- Dynamic Ghost Slot Preview at the end of Upper Tier -->
          <div
            v-if="isCardDragging && dropTargetInfo?.tier === 'upper' && dropTargetInfo?.index === layout.upperPanes.length"
            class="ghost-slot-tile"
          >
            <div class="ghost-slot-inner">
              <div class="ghost-slot-laser"></div>
              <span class="ghost-slot-tag">DROP TO INSERT</span>
              <span class="ghost-slot-title">{{ getWidgetMeta(draggedCardId!).title }}</span>
              <span class="ghost-slot-hint">放開即可插入</span>
            </div>
          </div>
        </div>

        <!-- Continuous Horizontal Splitter Between Upper and Lower Tiers -->
        <div
          class="splitter horizontal"
          @pointerdown="startHorizontalSplitDrag"
          @dblclick="resetHorizontalSplit"
          title="拖曳調整上下排高度比例 · 雙擊恢復均分 (56% / 44%)"
        >
          <div class="splitter-line"></div>
          <div class="splitter-grip horizontal"></div>
        </div>

        <!-- Tier 2: Lower Tier (Lower Row) -->
        <div
          id="tiling-lower-tier"
          class="tiling-row-tier"
          :class="{
            'drop-target-tier': isCardDragging && dropTargetInfo?.tier === 'lower' && layout.lowerPanes.length === 0
          }"
          :style="{ height: `calc(${100 - layout.upperHeightPct}% - 4px)` }"
        >
          <template v-for="(paneId, idx) in layout.lowerPanes" :key="paneId">
            <!-- Dynamic Ghost Slot Preview Tile before card -->
            <div
              v-if="isCardDragging && dropTargetInfo?.tier === 'lower' && dropTargetInfo?.index === idx"
              class="ghost-slot-tile"
            >
              <div class="ghost-slot-inner">
                <div class="ghost-slot-laser"></div>
                <span class="ghost-slot-tag">DROP TO INSERT</span>
                <span class="ghost-slot-title">{{ getWidgetMeta(draggedCardId!).title }}</span>
                <span class="ghost-slot-hint">放開即可插入</span>
              </div>
            </div>

            <!-- Card Pane -->
            <div
              :id="`pane-${paneId}`"
              class="tiling-pane"
              :class="{
                'is-dragging-card': isCardDragging && draggedCardId === paneId,
                'just-landed': landedId === paneId,
                'is-editing': isEditing
              }"
              :style="{ flex: `${layout.lowerWeights[idx] || 1} 1 0px` }"
            >
              <div class="pane-inner">
                <!-- Header Toolbar with Drag Surface -->
                <div
                  class="widget-toolbar"
                  :class="{ 'is-draggable': isEditing }"
                  @mousedown="e => startCardDrag(paneId, e)"
                >
                  <div class="toolbar-drag-grip" :title="isEditing ? '按住拖曳重新排序或跨排插入' : getWidgetMeta(paneId).title">
                    <span v-if="isEditing" class="grip-dots">⋮⋮</span>
                    <span class="widget-title-text">{{ getWidgetMeta(paneId).title }}</span>
                  </div>
                  <div class="toolbar-actions">
                    <button v-if="!paneId.startsWith('kpi_')" type="button" class="btn-tool" @click="toggleMaximize(paneId)" title="最大化聚焦">↗</button>
                    <button v-if="isEditing" type="button" class="btn-tool btn-tool-hide" @click="hidePane(paneId)" title="隱藏此卡片">✕</button>
                  </div>
                </div>

                <!-- Pane Content -->
                <div class="pane-content-body">
                  <MetricCard v-if="paneId.startsWith('kpi_')" v-bind="kpiPropsMap[paneId]" />
                  <SparklineArea v-else-if="paneId === 'equity'" :points="equityPoints" />
                  <DonutChart v-else-if="paneId === 'donut'" :items="exposureItems" centerValue="1,420.50" centerLabel="名義曝險 USDT" />
                  <div v-else-if="paneId === 'events'" class="pane-scrollable-body">
                    <div v-for="evt in auditEvents" :key="evt.id" class="hybrid-event-row" @click="toggleEvent(evt.id)">
                      <div class="event-meta">
                        <span :class="['badge badge-xs', evt.level === 'WARN' ? 'badge-warning' : 'badge-info']">{{ evt.level }}</span>
                        <span class="event-time">{{ evt.timestamp }}</span>
                      </div>
                      <div class="event-msg">{{ evt.message }}</div>
                      <div v-if="expandedEventId === evt.id" class="event-detail-box">
                        <code>{{ evt.details || 'Reconciliation check passed.' }}</code>
                      </div>
                    </div>
                  </div>
                  <RiskGauge v-else-if="paneId === 'risk'" :risk="riskState" />
                  <div v-else-if="paneId === 'bots'" class="pane-scrollable-body">
                    <div v-for="b in botQueue" :key="b.bot_id" class="hybrid-bot-row">
                      <div class="bot-info-main">
                        <span class="bot-name">{{ b.name }}</span>
                        <span class="bot-sym">{{ b.symbol }}</span>
                      </div>
                      <div class="bot-info-sub">
                        <span class="badge badge-xs badge-accent">持倉 {{ b.position_contracts }} 張</span>
                        <span class="bot-pnl tabular-nums text-success">{{ b.pnl_usdt }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="paneId === 'research'" class="pane-scrollable-body">
                    <div v-for="t in researchTasks" :key="t.id" class="hybrid-task-row">
                      <div class="task-info-main">
                        <span class="task-name">{{ t.name }}</span>
                        <span class="badge badge-xs badge-secondary">{{ t.version }}</span>
                      </div>
                      <div class="task-info-sub">
                        <span class="text-muted">Sharpe: {{ t.sharpe }}</span>
                        <span class="task-score text-accent">{{ t.status }}</span>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="paneId === 'yaozi'" class="pane-scrollable-body">
                    <div v-for="y in yaoziAlerts" :key="y.id" class="hybrid-yaozi-row">
                      <div class="yaozi-badge-col">
                        <span class="badge badge-xs badge-warning">{{ y.type }}</span>
                      </div>
                      <div class="yaozi-msg-col">
                        <strong>{{ y.title }}</strong>: {{ y.summary }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Vertical Splitter between cards -->
            <div
              v-if="idx < layout.lowerPanes.length - 1"
              class="splitter vertical"
              @pointerdown="e => startTierVerticalSplitDrag('lower', idx, e)"
              @dblclick="() => resetTierVerticalSplits('lower')"
              title="拖曳調整左右寬度 · 雙擊恢復均分"
            >
              <div class="splitter-line"></div>
              <div class="splitter-grip"></div>
            </div>
          </template>

          <!-- Dynamic Ghost Slot Preview at the end of Lower Tier -->
          <div
            v-if="isCardDragging && dropTargetInfo?.tier === 'lower' && dropTargetInfo?.index === layout.lowerPanes.length"
            class="ghost-slot-tile"
          >
            <div class="ghost-slot-inner">
              <div class="ghost-slot-laser"></div>
              <span class="ghost-slot-tag">DROP TO INSERT</span>
              <span class="ghost-slot-title">{{ getWidgetMeta(draggedCardId!).title }}</span>
              <span class="ghost-slot-hint">放開即可插入</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workspace-hybrid {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: var(--bg-base);
  overflow: hidden;
}

/* Top Ribbon Header */
.hybrid-ribbon {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px var(--space-4);
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-secondary);
  font-size: var(--text-xs);
  flex-wrap: wrap;
  gap: var(--space-2);
  transition: all 0.2s ease;
  z-index: 10;
}

.hybrid-ribbon.ribbon-edit-active {
  background: rgba(220, 179, 71, 0.06);
  border-bottom-color: rgba(220, 179, 71, 0.35);
}

.ribbon-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.ribbon-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
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
  background: rgba(220, 179, 71, 0.15);
  border: 1px solid rgba(220, 179, 71, 0.4);
  border-radius: 12px;
  color: var(--accent);
  font-weight: 600;
}

.edit-pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent);
  animation: pulse-glow 1.5s infinite;
}

@keyframes pulse-glow {
  0% { transform: scale(0.9); opacity: 0.7; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.7; }
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
  box-shadow: 0 0 10px rgba(220, 179, 71, 0.3);
}

/* Edit Mode Interactive Guide Bar */
.edit-mode-guide-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px var(--space-4);
  background: rgba(220, 179, 71, 0.1);
  border-bottom: 1px solid rgba(220, 179, 71, 0.25);
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
  border: 1px dashed rgba(220, 179, 71, 0.45);
}

.tiling-kpi-item.is-editing:hover {
  border-color: rgba(220, 179, 71, 0.75);
}

.tiling-kpi-item.is-dragging-card {
  opacity: 0.32 !important;
  border: 1px dashed rgba(212, 175, 55, 0.75) !important;
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
  background: rgba(220, 179, 71, 0.12);
  border-bottom: 1px dashed rgba(220, 179, 71, 0.35);
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
  border-color: rgba(220, 179, 71, 0.5);
}

.kpi-capsule-item.is-editing:hover {
  border-color: var(--accent);
  background: rgba(220, 179, 71, 0.08);
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
  outline: 1.5px dashed rgba(230, 184, 64, 0.65);
  outline-offset: -2px;
  background: rgba(220, 179, 71, 0.04);
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
  border: 1px dashed rgba(220, 179, 71, 0.45);
}

.tiling-pane.is-editing:hover {
  border-color: rgba(220, 179, 71, 0.65);
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
    border-color: #ffd700;
    box-shadow: 0 0 20px rgba(255, 215, 0, 0.6), inset 0 0 15px rgba(255, 215, 0, 0.2);
  }
  100% {
    border-color: var(--border-secondary);
    box-shadow: none;
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
  gap: 4px;
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

.pane-scrollable-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

/* Fluid Responsive Metric Cards inside Tiling Panes (動態字級響應 & 無縫縮放) */
.pane-content-body :deep(.kpi-card) {
  height: 100%;
  width: 100%;
  margin: 0;
  background: transparent;
  border-top: none;
  border-right: none;
  border-bottom: none;
  border-radius: 0;
  box-shadow: none;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  box-sizing: border-box;
  padding: clamp(2px, 3cqh, 12px) clamp(8px, 2.5cqw, 18px);
  gap: clamp(1px, 2cqh, 6px);
  overflow: hidden;
}

/* 隱藏重複標題：卡片工具列已清晰標示品名，移除卡內冗餘重複文字釋放高度 */
.pane-content-body :deep(.kpi-label) {
  display: none !important;
}

/* 數值列：排版流暢居左、動態間距、禁止折行截斷 */
.pane-content-body :deep(.kpi-value-row) {
  display: flex;
  align-items: baseline;
  gap: clamp(3px, 1.2cqw, 8px);
  width: 100%;
  overflow: hidden;
  line-height: 1.1;
  flex-wrap: nowrap;
}

/* 動態自適應主數值：跟隨容器寬高流體縮放 (13px ~ 32px) */
.pane-content-body :deep(.kpi-value) {
  font-size: clamp(13px, min(8.5cqw, 28cqh), 32px);
  font-weight: 700;
  font-family: var(--font-mono);
  line-height: 1.1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 動態單位文字：跟隨主數值等比縮放 */
.pane-content-body :deep(.kpi-unit) {
  font-size: clamp(10px, min(3.8cqw, 13cqh), 14px);
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-weight: 600;
  white-space: nowrap;
}

/* 動態說明輔助文字：動態字級與單行防截斷保護 */
.pane-content-body :deep(.kpi-sub) {
  font-size: clamp(9px, min(3.2cqw, 12cqh), 12px);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 100%;
  line-height: 1.25;
}

/* 微高度極限響應：當高度極度壓縮 (<= 75px) 時自動轉為水平單列 inline 排版，徹底杜絕文字切頭切尾 */
@container pane-body (max-height: 75px) {
  .pane-content-body :deep(.kpi-card) {
    flex-direction: row !important;
    align-items: center !important;
    justify-content: space-between !important;
    padding: 2px 10px !important;
    gap: 8px !important;
  }
  .pane-content-body :deep(.kpi-value-row) {
    width: auto !important;
    flex-shrink: 0 !important;
  }
  .pane-content-body :deep(.kpi-value) {
    font-size: clamp(13px, 34cqh, 20px) !important;
  }
  .pane-content-body :deep(.kpi-sub) {
    width: auto !important;
    text-align: right !important;
    margin-left: auto !important;
    flex-shrink: 1 !important;
    font-size: clamp(9px, 20cqh, 11px) !important;
  }
}

/* 極窄寬度保護 (寬度 <= 180px) */
@container pane-body (max-width: 180px) {
  .pane-content-body :deep(.kpi-sub) {
    font-size: 10px !important;
  }
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
  box-shadow: 0 0 10px rgba(230, 184, 64, 0.75);
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
  padding: 6px 8px;
  border-bottom: 1px solid var(--border-secondary);
  font-size: 11px;
}

.bot-info-main, .task-info-main {
  display: flex;
  align-items: center;
  gap: 6px;
}

.bot-name, .task-name {
  font-weight: 600;
  color: var(--text-primary);
}

.bot-sym {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
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
  padding: 6px 8px;
  border-bottom: 1px solid var(--border-secondary);
  font-size: 11px;
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
  border-color: rgba(220, 179, 71, 0.4);
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
  border: 1.5px dashed rgba(230, 184, 64, 0.9);
  background: linear-gradient(135deg, rgba(220, 179, 71, 0.14) 0%, rgba(14, 18, 24, 0.85) 100%);
  border-radius: var(--radius-sm);
  box-shadow: 0 0 20px rgba(220, 179, 71, 0.3), inset 0 0 20px rgba(220, 179, 71, 0.15);
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
  color: #ffd700;
  background: rgba(220, 179, 71, 0.25);
  border: 1px solid rgba(220, 179, 71, 0.5);
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
</style>
