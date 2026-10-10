<script setup lang="ts">
import { ref, computed } from 'vue';
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

// 1. Freeform Grid Widget Item Interface
interface GridWidget {
  id: string;
  title: string;
  colSpan: number; // 3 to 12
  minCol: number;
  maxCol: number;
  heightPx: number; // Min 140px, Max 450px
  order: number;
  visible: boolean;
}

const STORAGE_KEY_FREEFORM = 'catos_freeform_layout_v1';

const defaultWidgets: GridWidget[] = [
  { id: 'kpi_bar', title: '核心指標速覽', colSpan: 12, minCol: 6, maxCol: 12, heightPx: 104, order: 0, visible: true },
  { id: 'equity', title: '帳戶淨值走勢', colSpan: 6, minCol: 4, maxCol: 12, heightPx: 250, order: 1, visible: true },
  { id: 'donut', title: '保證金與曝險配置', colSpan: 3, minCol: 3, maxCol: 6, heightPx: 250, order: 2, visible: true },
  { id: 'events', title: '重要事件時間軸', colSpan: 3, minCol: 3, maxCol: 6, heightPx: 250, order: 3, visible: true },
  { id: 'risk', title: '日損鎖存安全儀表', colSpan: 4, minCol: 3, maxCol: 8, heightPx: 230, order: 4, visible: true },
  { id: 'bots', title: '機器人隊列', colSpan: 3, minCol: 3, maxCol: 6, heightPx: 230, order: 5, visible: true },
  { id: 'research', title: '近期研究任務', colSpan: 3, minCol: 3, maxCol: 6, heightPx: 230, order: 6, visible: true },
  { id: 'yaozi', title: 'Yaozi 市場情報', colSpan: 2, minCol: 2, maxCol: 6, heightPx: 230, order: 7, visible: true }
];

function loadWidgets(): GridWidget[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_FREEFORM);
    if (!raw) return JSON.parse(JSON.stringify(defaultWidgets));
    const p = JSON.parse(raw);
    if (Array.isArray(p) && p.length > 0) {
      p.forEach((w: GridWidget) => {
        if (w.id === 'kpi_bar' && w.heightPx < 104) w.heightPx = 104;
      });
      return p;
    }
    return JSON.parse(JSON.stringify(defaultWidgets));
  } catch {
    return JSON.parse(JSON.stringify(defaultWidgets));
  }
}

const widgets = ref<GridWidget[]>(loadWidgets());

function saveWidgets() {
  try {
    localStorage.setItem(STORAGE_KEY_FREEFORM, JSON.stringify(widgets.value));
  } catch {}
}

const sortedWidgets = computed(() => {
  return [...widgets.value].filter(w => w.visible).sort((a, b) => a.order - b.order);
});

const hiddenWidgets = computed(() => {
  return widgets.value.filter(w => !w.visible);
});

function resetLayout() {
  widgets.value = JSON.parse(JSON.stringify(defaultWidgets));
  saveWidgets();
}

function restoreWidget(id: string) {
  const w = widgets.value.find(item => item.id === id);
  if (w) {
    w.visible = true;
    saveWidgets();
  }
}

function hideWidget(id: string) {
  const w = widgets.value.find(item => item.id === id);
  if (w) {
    w.visible = false;
    saveWidgets();
  }
}

// 2. Drag & Drop Reordering (HTML5 Drag & Pointer Native)
const draggedWidgetId = ref<string | null>(null);
const dropTargetId = ref<string | null>(null);

function handleDragStart(id: string, e: DragEvent) {
  draggedWidgetId.value = id;
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', id);
  }
}

function handleDragOver(id: string, e: DragEvent) {
  e.preventDefault();
  if (draggedWidgetId.value && draggedWidgetId.value !== id) {
    dropTargetId.value = id;
  }
}

function handleDragLeave(id: string) {
  if (dropTargetId.value === id) {
    dropTargetId.value = null;
  }
}

function handleDrop(targetId: string, e: DragEvent) {
  e.preventDefault();
  if (!draggedWidgetId.value || draggedWidgetId.value === targetId) {
    draggedWidgetId.value = null;
    dropTargetId.value = null;
    return;
  }

  const sourceIdx = widgets.value.findIndex(w => w.id === draggedWidgetId.value);
  const targetIdx = widgets.value.findIndex(w => w.id === targetId);

  if (sourceIdx !== -1 && targetIdx !== -1) {
    const tempOrder = widgets.value[sourceIdx].order;
    widgets.value[sourceIdx].order = widgets.value[targetIdx].order;
    widgets.value[targetIdx].order = tempOrder;
    saveWidgets();
  }

  draggedWidgetId.value = null;
  dropTargetId.value = null;
}

function handleDragEnd() {
  draggedWidgetId.value = null;
  dropTargetId.value = null;
}

// 3. Interactive Corner Resizing (Pointer Direct Engine)
const resizingWidgetId = ref<string | null>(null);
const resizeFeedback = ref<{ id: string; col: number; height: number } | null>(null);

function startResize(w: GridWidget, e: PointerEvent) {
  e.preventDefault();
  e.stopPropagation();
  resizingWidgetId.value = w.id;
  const startX = e.clientX;
  const startY = e.clientY;
  const startCol = w.colSpan;
  const startH = w.heightPx;

  // Approximate pixel width of 1 column based on current 12-col container width
  const container = document.querySelector('.freeform-grid-viewport');
  const containerWidth = container ? container.getBoundingClientRect().width : 1200;
  const colWidthPx = containerWidth / 12;

  document.body.style.cursor = 'se-resize';
  document.body.style.userSelect = 'none';

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!resizingWidgetId.value) return;
    const deltaX = moveEvt.clientX - startX;
    const deltaY = moveEvt.clientY - startY;

    // Calculate column delta
    const colDelta = Math.round(deltaX / colWidthPx);
    const newCol = Math.min(w.maxCol, Math.max(w.minCol, startCol + colDelta));

    // Calculate height delta
    const newH = Math.min(480, Math.max(130, Math.round(startH + deltaY)));

    w.colSpan = newCol;
    w.heightPx = newH;
    resizeFeedback.value = { id: w.id, col: newCol, height: newH };
  };

  const onPointerUp = () => {
    resizingWidgetId.value = null;
    resizeFeedback.value = null;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveWidgets();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

// 4. Auto-Pack (ϟ 一鍵智慧自動緊湊)
function autoPack() {
  // Re-balance columns so rows sum to 12
  const list = widgets.value.filter(w => w.visible);
  let currentRowSum = 0;
  list.forEach(w => {
    if (w.id === 'kpi_bar') {
      w.colSpan = 12;
      return;
    }
    // Balance into 6-6, 4-4-4, or 3-3-3-3
    if (w.id === 'equity') w.colSpan = 6;
    else if (w.id === 'donut' || w.id === 'events') w.colSpan = 3;
    else if (w.id === 'risk') w.colSpan = 4;
    else if (w.id === 'bots' || w.id === 'research') w.colSpan = 3;
    else if (w.id === 'yaozi') w.colSpan = 2;
  });
  saveWidgets();
}

// 5. Maximize Pane
const maximizedId = ref<string | null>(null);
function toggleMaximize(id: string) {
  maximizedId.value = maximizedId.value === id ? null : id;
}
</script>

<template>
  <div class="workspace-freeform">
    <!-- Top Action Ribbon -->
    <div class="freeform-ribbon">
      <div class="ribbon-left">
        <span class="ribbon-tag">方案 B</span>
        <span class="ribbon-title">Grafana 模組化 12 欄自由拖曳與縮放網格 (Freeform Grid)</span>
        <span class="ribbon-hint">拖曳標題把手 ⋮⋮ 交換順序 · 拖曳右下角 ⤡ 任意縮放欄寬與高</span>
      </div>
      <div class="ribbon-actions">
        <!-- Hidden widgets restore pill -->
        <span v-if="hiddenWidgets.length" class="hidden-pill-wrap">
          <span class="text-muted text-xs">已隱藏：</span>
          <button
            v-for="hw in hiddenWidgets"
            :key="hw.id"
            type="button"
            class="btn btn-xs btn-outline-gold"
            @click="restoreWidget(hw.id)"
            :title="`點擊恢復 ${hw.title}`"
          >
            ＋ {{ hw.title }}
          </button>
        </span>
        <button type="button" class="btn btn-xs btn-primary" @click="autoPack" title="一鍵整理行寬，消除間隙">
          ϟ 自動補滿 (Auto-Pack)
        </button>
        <button type="button" class="btn btn-xs btn-secondary" @click="resetLayout" title="恢復預設佈局">
          ⟲ 重設佈局
        </button>
      </div>
    </div>

    <!-- Maximized Fullscreen Overlay Mode -->
    <div v-if="maximizedId" class="maximized-overlay">
      <div class="maximized-header">
        <span class="maximized-label">🔍 聚焦檢視模式 (方案 B)</span>
        <button type="button" class="btn btn-sm btn-primary" @click="maximizedId = null">
          ↙ 還原多面工作台 (Esc)
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
      </div>
    </div>

    <!-- 12-Column Responsive CSS Grid Viewport -->
    <div v-else class="freeform-grid-viewport">
      <template v-for="w in sortedWidgets" :key="w.id">
        <div
          class="grid-card-widget"
          :class="{
            'is-dragging': draggedWidgetId === w.id,
            'is-drop-target': dropTargetId === w.id,
            'is-resizing': resizingWidgetId === w.id
          }"
          :style="{
            gridColumn: `span ${w.colSpan}`,
            height: `${w.heightPx}px`
          }"
          draggable="true"
          @dragstart="e => handleDragStart(w.id, e)"
          @dragover="e => handleDragOver(w.id, e)"
          @dragleave="() => handleDragLeave(w.id)"
          @drop="e => handleDrop(w.id, e)"
          @dragend="handleDragEnd"
        >
          <!-- Card Control Bar -->
          <div class="widget-toolbar">
            <div class="toolbar-drag-grip" title="按住拖曳交換卡片位置">
              <span class="grip-dots">⋮⋮</span>
              <span class="widget-title-text">{{ w.title }}</span>
            </div>
            <div class="toolbar-actions">
              <span v-if="resizeFeedback?.id === w.id" class="resize-badge">
                {{ w.colSpan }} 欄 × {{ w.heightPx }}px
              </span>
              <button type="button" class="btn-tool" @click="toggleMaximize(w.id)" title="最大化聚焦">↗</button>
              <button type="button" class="btn-tool" @click="hideWidget(w.id)" title="隱藏此卡片">×</button>
            </div>
          </div>

          <!-- Card Content Body -->
          <div class="widget-content-body">
            <!-- 1. KPI Bar -->
            <div v-if="w.id === 'kpi_bar'" class="freeform-kpi-inner">
              <MetricCard
                label="總權益淨值"
                :value="isUnavailable ? '— USDT' : (kpis?.total_equity ? kpis.total_equity + ' USDT' : '--')"
                :subText="isUnavailable ? '服務離線' : ('實時持倉估值 + 現金餘額 (' + (kpis?.equity_change_pct || '0.00%') + ')')"
                borderType="accent"
              />
              <MetricCard
                label="今日損益"
                :value="isUnavailable ? '— USDT' : (kpis?.today_pnl ? kpis.today_pnl + ' USDT' : '--')"
                :subText="isUnavailable ? '未知損益' : ('已實現 + 未實現浮動 (' + (kpis?.today_pnl_pct || '0.00%') + ')')"
                borderType="success"
              />
              <MetricCard
                label="部署機器人"
                :value="isUnavailable ? '— / —' : (kpis ? `${kpis.running_bots_count} / ${kpis.total_bots_count}` : '--')"
                unit="個策略實例"
                borderType="accent"
              />
              <MetricCard
                label="風控狀態"
                :value="isUnavailable ? 'UNAVAILABLE' : (kpis?.risk_status || 'UNKNOWN')"
                :unit="isUnavailable ? '503' : (kpis?.effective_leverage ? `${kpis.effective_leverage}x / ${kpis.leverage_limit}x` : '')"
                borderType="accent"
              />
            </div>

            <!-- 2. Equity Chart -->
            <SparklineArea v-else-if="w.id === 'equity'" :points="equityPoints" />

            <!-- 3. Margin Donut -->
            <DonutChart
              v-else-if="w.id === 'donut'"
              :items="exposureItems"
              centerValue="1,420.50"
              centerLabel="名義曝險 USDT"
            />

            <!-- 4. Events Stream -->
            <div v-else-if="w.id === 'events'" class="events-scroll-wrap">
              <div v-if="auditEvents.length" class="events-list">
                <div
                  v-for="evt in auditEvents"
                  :key="evt.id"
                  class="event-item"
                  :class="{ expanded: expandedEventId === evt.id }"
                  @click="toggleEvent(evt.id)"
                >
                  <div class="event-summary-row">
                    <span :class="['badge badge-sm', evt.level === 'WARN' ? 'badge-warning' : 'badge-info']">{{ evt.level }}</span>
                    <span class="event-time tabular-nums">{{ evt.timestamp }}</span>
                    <span class="event-msg">{{ evt.message }}</span>
                  </div>
                </div>
              </div>
              <EmptyState v-else title="暫無重大事件" description="最近無警告通知" />
            </div>

            <!-- 5. Risk Gauge -->
            <RiskGauge v-else-if="w.id === 'risk'" :risk="riskState" />

            <!-- 6. Bot Queue -->
            <div v-else-if="w.id === 'bots'" class="bots-scroll-wrap">
              <div v-if="botQueue.length" class="bots-list">
                <div v-for="b in botQueue" :key="b.bot_id" class="bot-row">
                  <div class="bot-info">
                    <div class="bot-name">{{ b.name }}</div>
                    <div class="bot-sub mono">{{ b.symbol }} · {{ b.position_contracts }} 張</div>
                  </div>
                  <div class="bot-status-col">
                    <StatusBadge :status="b.state" />
                    <span class="bot-pnl tabular-nums text-success">{{ b.pnl_usdt }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 7. Research Tasks -->
            <div v-else-if="w.id === 'research'" class="research-scroll-wrap">
              <div v-for="t in researchTasks" :key="t.id" class="task-card mb-1">
                <div class="task-header-row">
                  <strong>{{ t.name }}</strong>
                  <span class="badge badge-sm badge-info">{{ t.version }}</span>
                </div>
                <div class="task-footer-row text-xs mt-1">
                  <span>{{ t.description }}</span>
                  <span class="text-accent">Sharpe {{ t.sharpe }}</span>
                </div>
              </div>
            </div>

            <!-- 8. Yaozi Market Intel -->
            <div v-else-if="w.id === 'yaozi'" class="yaozi-scroll-wrap">
              <div v-for="y in yaoziAlerts" :key="y.id" class="yaozi-item mb-1">
                <div class="yaozi-header-row">
                  <span class="text-warning">{{ y.title }}</span>
                  <span class="text-muted">{{ y.time }}</span>
                </div>
                <div class="text-2xs text-muted mt-1">{{ y.summary }}</div>
              </div>
            </div>
          </div>

          <!-- Bottom Right Resize Handle -->
          <div
            class="widget-resize-handle"
            @pointerdown="e => startResize(w, e)"
            title="按住拖曳調整寬度 (欄) 與高度"
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <path d="M8 2L2 8M9 5L5 9M9 8L8 9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.workspace-freeform {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: hidden;
  background-color: var(--bg-base);
}

.freeform-ribbon {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 12px;
  background: rgba(14, 18, 24, 0.7);
  border-bottom: 1px solid rgba(220, 179, 71, 0.15);
  font-size: 11px;
}
.ribbon-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ribbon-tag {
  background-color: rgba(220, 179, 71, 0.18);
  color: var(--accent);
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: 700;
  font-size: 10px;
}
.ribbon-title {
  color: var(--text-primary);
  font-weight: 600;
}
.ribbon-hint {
  color: var(--text-muted);
  font-size: 10.5px;
}
.ribbon-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.hidden-pill-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
}
.btn-outline-gold {
  background: transparent;
  border: 1px dashed rgba(220, 179, 71, 0.4);
  color: var(--accent);
  padding: 1px 6px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 10px;
}
.btn-outline-gold:hover {
  background: rgba(220, 179, 71, 0.15);
  border-style: solid;
}

/* 12-Column Responsive CSS Grid Viewport */
.freeform-grid-viewport {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 8px;
  padding: 8px 12px 14px 12px;
  overflow-y: auto;
  overflow-x: hidden;
  align-content: start;
}

.grid-card-widget {
  background: var(--bg-surface);
  border: 1px solid var(--border-secondary);
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
  transition: box-shadow 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.grid-card-widget:hover {
  border-color: rgba(220, 179, 71, 0.3);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.grid-card-widget.is-dragging {
  opacity: 0.45;
  border: 1px dashed var(--accent);
  transform: scale(0.98);
}

.grid-card-widget.is-drop-target {
  border: 2px dashed var(--accent);
  box-shadow: 0 0 16px rgba(220, 179, 71, 0.5);
}

.grid-card-widget.is-resizing {
  border-color: var(--accent);
  box-shadow: 0 0 14px rgba(220, 179, 71, 0.4);
}

/* Widget Top Control Bar */
.widget-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 8px;
  background: rgba(14, 18, 24, 0.85);
  border-bottom: 1px solid var(--border-secondary);
  cursor: grab;
  user-select: none;
}
.widget-toolbar:active {
  cursor: grabbing;
}

.toolbar-drag-grip {
  display: flex;
  align-items: center;
  gap: 6px;
}
.grip-dots {
  color: var(--accent);
  font-size: 11px;
  opacity: 0.6;
}
.widget-title-text {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.resize-badge {
  font-size: 9px;
  color: var(--accent);
  background: rgba(220, 179, 71, 0.15);
  padding: 1px 4px;
  border-radius: 2px;
  font-family: var(--font-mono);
}
.btn-tool {
  background: transparent;
  border: none;
  color: #8b9bb4;
  font-size: 11px;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 2px;
}
.btn-tool:hover {
  color: var(--accent);
  background: rgba(220, 179, 71, 0.15);
}

.widget-content-body {
  flex: 1;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}

.freeform-kpi-inner {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  height: 100%;
}

.events-scroll-wrap, .bots-scroll-wrap, .research-scroll-wrap, .yaozi-scroll-wrap {
  padding: 6px 8px;
  overflow-y: auto;
  height: 100%;
}

/* Bottom Right Resize Handle */
.widget-resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 14px;
  height: 14px;
  cursor: se-resize;
  color: rgba(220, 179, 71, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  transition: color 0.15s ease;
}
.widget-resize-handle:hover,
.grid-card-widget.is-resizing .widget-resize-handle {
  color: var(--accent);
}

/* Maximized Overlay */
.maximized-overlay {
  position: absolute;
  top: 36px;
  left: 8px;
  right: 8px;
  bottom: 8px;
  background: var(--bg-base);
  z-index: 50;
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(220, 179, 71, 0.35);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.8);
  border-radius: 4px;
}
.maximized-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 14px;
  background: rgba(14, 18, 24, 0.9);
  border-bottom: 1px solid rgba(220, 179, 71, 0.2);
}
.maximized-label {
  font-weight: 700;
  color: var(--accent);
  font-size: 13px;
}
.maximized-body {
  flex: 1;
  overflow: auto;
  padding: 10px;
}
</style>
