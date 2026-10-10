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

// 1. Tiling Splitter Dimensions & Percentages (Saved to localStorage)
const STORAGE_KEY_TILING = 'catos_tiling_splits_v1';

interface TilingSplits {
  middleHeightPct: number; // Percentage of main area (default 56%)
  middleWidths: [number, number, number]; // [equity, donut, events], default [48, 28, 24]
  lowerWidths: [number, number, number, number]; // [risk, bots, research, yaozi], default [32, 23, 23, 22]
}

const defaultSplits: TilingSplits = {
  middleHeightPct: 56,
  middleWidths: [48, 28, 24],
  lowerWidths: [32, 23, 23, 22]
};

function loadSplits(): TilingSplits {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_TILING);
    if (!raw) return { ...defaultSplits };
    const p = JSON.parse(raw);
    return {
      middleHeightPct: typeof p.middleHeightPct === 'number' ? p.middleHeightPct : 56,
      middleWidths: Array.isArray(p.middleWidths) && p.middleWidths.length === 3 ? p.middleWidths : [48, 28, 24],
      lowerWidths: Array.isArray(p.lowerWidths) && p.lowerWidths.length === 4 ? p.lowerWidths : [32, 23, 23, 22]
    };
  } catch {
    return { ...defaultSplits };
  }
}

const splits = ref<TilingSplits>(loadSplits());

function saveSplits() {
  try {
    localStorage.setItem(STORAGE_KEY_TILING, JSON.stringify(splits.value));
  } catch {}
}

function resetAllSplits() {
  splits.value = { ...defaultSplits };
  saveSplits();
}

// 2. Maximized Pane State
const maximizedPane = ref<string | null>(null);

function toggleMaximize(paneId: string) {
  maximizedPane.value = maximizedPane.value === paneId ? null : paneId;
}

// 3. Continuous Splitter Dragging Engine (120 FPS Direct DOM calculations)
const isDragging = ref(false);

function startHorizontalSplitDrag(e: PointerEvent) {
  e.preventDefault();
  isDragging.value = true;
  const startY = e.clientY;
  const startPct = splits.value.middleHeightPct;
  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerHeight = container.getBoundingClientRect().height;

  document.body.style.cursor = 'row-resize';
  document.body.style.userSelect = 'none';

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isDragging.value) return;
    const deltaY = moveEvt.clientY - startY;
    const deltaPct = (deltaY / containerHeight) * 100;
    const newPct = Math.min(80, Math.max(25, Math.round(startPct + deltaPct)));
    splits.value.middleHeightPct = newPct;
  };

  const onPointerUp = () => {
    isDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveSplits();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

function resetHorizontalSplit() {
  splits.value.middleHeightPct = 56;
  saveSplits();
}

function startMiddleVerticalSplitDrag(index: 0 | 1, e: PointerEvent) {
  e.preventDefault();
  isDragging.value = true;
  const startX = e.clientX;
  const w = [...splits.value.middleWidths] as [number, number, number];
  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerWidth = container.getBoundingClientRect().width;

  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isDragging.value) return;
    const deltaX = moveEvt.clientX - startX;
    const deltaPct = (deltaX / containerWidth) * 100;

    if (index === 0) {
      // Split between Col 0 (Equity) and Col 1 (Donut)
      const new0 = Math.min(70, Math.max(20, Math.round(w[0] + deltaPct)));
      const diff = new0 - w[0];
      const new1 = Math.max(15, w[1] - diff);
      splits.value.middleWidths[0] = new0;
      splits.value.middleWidths[1] = new1;
    } else {
      // Split between Col 1 (Donut) and Col 2 (Events)
      const new1 = Math.min(60, Math.max(15, Math.round(w[1] + deltaPct)));
      const diff = new1 - w[1];
      const new2 = Math.max(15, w[2] - diff);
      splits.value.middleWidths[1] = new1;
      splits.value.middleWidths[2] = new2;
    }
  };

  const onPointerUp = () => {
    isDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveSplits();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

function resetMiddleVerticalSplits() {
  splits.value.middleWidths = [48, 28, 24];
  saveSplits();
}

function startLowerVerticalSplitDrag(index: 0 | 1 | 2, e: PointerEvent) {
  e.preventDefault();
  isDragging.value = true;
  const startX = e.clientX;
  const w = [...splits.value.lowerWidths] as [number, number, number, number];
  const container = (e.currentTarget as HTMLElement).parentElement;
  if (!container) return;
  const containerWidth = container.getBoundingClientRect().width;

  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';

  const onPointerMove = (moveEvt: PointerEvent) => {
    if (!isDragging.value) return;
    const deltaX = moveEvt.clientX - startX;
    const deltaPct = (deltaX / containerWidth) * 100;
    const leftIdx = index;
    const rightIdx = index + 1;

    const newLeft = Math.min(60, Math.max(12, Math.round(w[leftIdx] + deltaPct)));
    const diff = newLeft - w[leftIdx];
    const newRight = Math.max(12, w[rightIdx] - diff);

    splits.value.lowerWidths[leftIdx] = newLeft;
    splits.value.lowerWidths[rightIdx] = newRight;
  };

  const onPointerUp = () => {
    isDragging.value = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    saveSplits();
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

function resetLowerVerticalSplits() {
  splits.value.lowerWidths = [32, 23, 23, 22];
  saveSplits();
}
</script>

<template>
  <div class="workspace-tiling" :class="{ 'is-dragging': isDragging }">
    <!-- Top Mode Helper Ribbon -->
    <div class="tiling-ribbon">
      <div class="ribbon-left">
        <span class="ribbon-tag">方案 A</span>
        <span class="ribbon-title">OKX / TradingView 無縫連續分割瓦片 (Seamless Tiling)</span>
        <span class="ribbon-hint">拖曳卡片邊界金色分割線調整比例 · 雙擊分割線自動均分 · 點擊 ↗ 最大化</span>
      </div>
      <div class="ribbon-actions">
        <button type="button" class="btn btn-xs btn-secondary" @click="resetAllSplits" title="還原所有分割比例">
          ⟲ 還原平衡比例
        </button>
      </div>
    </div>

    <!-- Offline / Unavailable Error Alert Banner -->
    <div v-if="isUnavailable || error" class="alert-banner-danger">
      <div class="alert-icon">⚠️</div>
      <div class="alert-content">
        <strong>{{ error || '503 服務不可用：底座連線中斷或離線' }}</strong>
        <p>安全底線約束：禁止未知狀態轉零或正常。底座未確認連線前，禁止宣告安全並阻擋所有交易下單。</p>
      </div>
    </div>

    <!-- Maximized Fullscreen Overlay Mode -->
    <div v-if="maximizedPane" class="maximized-overlay">
      <div class="maximized-header">
        <span class="maximized-label">🔍 聚焦檢視模式</span>
        <button type="button" class="btn btn-sm btn-primary" @click="maximizedPane = null">
          ↙ 還原多面工作台 (Esc)
        </button>
      </div>
      <div class="maximized-body">
        <div v-if="maximizedPane === 'equity'" class="card h-full">
          <SparklineArea :points="equityPoints" />
        </div>
        <div v-else-if="maximizedPane === 'donut'" class="card h-full">
          <DonutChart :items="exposureItems" centerValue="1,420.50" centerLabel="名義曝險 USDT" />
        </div>
        <div v-else-if="maximizedPane === 'events'" class="card h-full">
          <div class="card-header"><div class="card-title">重要事件時間軸 (聚焦流)</div></div>
          <div class="card-body events-body p-4">
            <div v-for="evt in auditEvents" :key="evt.id" class="event-item mb-2 p-2">
              <span class="badge badge-info mr-2">{{ evt.level }}</span>
              <span class="tabular-nums mr-2">{{ evt.timestamp }}</span>
              <span>{{ evt.message }}</span>
            </div>
          </div>
        </div>
        <div v-else-if="maximizedPane === 'risk'" class="card h-full">
          <RiskGauge :risk="riskState" />
        </div>
        <div v-else-if="maximizedPane === 'bots'" class="card h-full p-4">
          <h3>機器人詳細佇列</h3>
          <div v-for="b in botQueue" :key="b.bot_id" class="p-3 border-b border-border-secondary">
            <strong>{{ b.name }}</strong> ({{ b.symbol }}) - 持倉 {{ b.position_contracts }} 張
          </div>
        </div>
      </div>
    </div>

    <!-- Regular Tiling Layout (When Not Maximized) -->
    <div v-else class="tiling-grid-container">
      <!-- Tier 1: 4 KPI Cards -->
      <div class="tiling-kpi-row">
        <MetricCard
          label="總權益淨值"
          :value="isUnavailable ? '— USDT' : (kpis?.total_equity ? kpis.total_equity + ' USDT' : '--')"
          :subText="isUnavailable ? '服務離線 · 無法讀取' : ('實時持倉估值 + 現金餘額 (' + (kpis?.equity_change_pct || '0.00%') + ')')"
          :subType="isUnavailable ? 'neg' : 'pos'"
          :borderType="isUnavailable ? 'danger' : 'accent'"
        />
        <MetricCard
          label="今日損益"
          :value="isUnavailable ? '— USDT' : (kpis?.today_pnl ? kpis.today_pnl + ' USDT' : '--')"
          :subText="isUnavailable ? '未知損益 · 需核對基線' : ('已實現 + 未實現浮動 (' + (kpis?.today_pnl_pct || '0.00%') + ')')"
          :subType="isUnavailable ? 'neg' : ((kpis?.today_pnl?.startsWith('+')) ? 'pos' : 'neg')"
          :borderType="isUnavailable ? 'danger' : ((kpis?.today_pnl?.startsWith('+')) ? 'success' : 'danger')"
        />
        <MetricCard
          label="部署機器人"
          :value="isUnavailable ? '— / —' : (kpis ? `${kpis.running_bots_count} / ${kpis.total_bots_count}` : '--')"
          unit="個策略實例"
          :subText="isUnavailable ? '服務離線' : (kpis?.bots_summary_note || '無部署')"
          :borderType="isUnavailable ? 'danger' : 'accent'"
        />
        <MetricCard
          label="風控狀態"
          :value="isUnavailable ? 'UNAVAILABLE' : (kpis?.risk_status || 'UNKNOWN')"
          :unit="isUnavailable ? '503 離線' : (kpis?.effective_leverage ? `${kpis.effective_leverage}x / 上限 ${kpis.leverage_limit}x` : '')"
          :subText="isUnavailable ? '服務不可用 · 禁止增倉' : (kpis?.risk_sub_note || '狀態未知')"
          :borderType="isUnavailable ? 'danger' : (kpis?.risk_status === 'NORMAL' ? 'accent' : 'warning')"
        />
      </div>

      <!-- Main Workstation Panes Container with Horizontal Splitter -->
      <div class="tiling-main-viewport">
        <!-- Middle Row (Upper Tier) -->
        <div
          class="tiling-row-tier"
          :style="{ height: `${splits.middleHeightPct}%` }"
        >
          <!-- Pane 1: Equity Trend -->
          <div
            class="tiling-pane pane-equity"
            :style="{ width: `${splits.middleWidths[0]}%` }"
          >
            <div class="pane-inner">
              <div class="pane-header-actions">
                <button type="button" class="btn-pane-action" @click="toggleMaximize('equity')" title="最大化聚焦">↗</button>
              </div>
              <SparklineArea :points="equityPoints" />
            </div>
          </div>

          <!-- Vertical Splitter 1 -->
          <div
            class="splitter vertical"
            @pointerdown="e => startMiddleVerticalSplitDrag(0, e)"
            @dblclick="resetMiddleVerticalSplits"
            title="拖曳調整走勢圖與配置圖寬度 · 雙擊均分"
          >
            <div class="splitter-line"></div>
            <div class="splitter-grip"></div>
          </div>

          <!-- Pane 2: Margin & Donut -->
          <div
            class="tiling-pane pane-donut"
            :style="{ width: `${splits.middleWidths[1]}%` }"
          >
            <div class="pane-inner">
              <div class="pane-header-actions">
                <button type="button" class="btn-pane-action" @click="toggleMaximize('donut')" title="最大化聚焦">↗</button>
              </div>
              <DonutChart
                v-if="exposureItems.length"
                :items="exposureItems"
                centerValue="1,420.50"
                centerLabel="名義曝險 USDT"
              />
              <div v-else class="card h-full">
                <div class="card-header"><div class="card-title">保證金與曝險配置</div></div>
                <div class="card-body"><EmptyState title="暫無持倉與保證金佔用" description="當前無運行中的合約持倉" /></div>
              </div>
            </div>
          </div>

          <!-- Vertical Splitter 2 -->
          <div
            class="splitter vertical"
            @pointerdown="e => startMiddleVerticalSplitDrag(1, e)"
            @dblclick="resetMiddleVerticalSplits"
            title="拖曳調整配置圖與事件日誌寬度 · 雙擊均分"
          >
            <div class="splitter-line"></div>
            <div class="splitter-grip"></div>
          </div>

          <!-- Pane 3: Audit Events Timeline -->
          <div
            class="tiling-pane pane-events"
            :style="{ width: `${splits.middleWidths[2]}%` }"
          >
            <div class="pane-inner card">
              <div class="card-header">
                <div class="card-title">重要事件時間軸</div>
                <div class="card-actions">
                  <span class="badge badge-neutral">即時串流</span>
                  <button type="button" class="btn-pane-action ml-1" @click="toggleMaximize('events')" title="最大化聚焦">↗</button>
                </div>
              </div>
              <div class="card-body events-body">
                <div v-if="auditEvents.length" class="events-list">
                  <div
                    v-for="evt in auditEvents"
                    :key="evt.id"
                    class="event-item"
                    :class="{ expanded: expandedEventId === evt.id }"
                    @click="toggleEvent(evt.id)"
                  >
                    <div class="event-summary-row">
                      <span :class="['badge badge-sm', evt.level === 'WARN' ? 'badge-warning' : 'badge-info']">
                        {{ evt.level }}
                      </span>
                      <span class="event-time tabular-nums">{{ evt.timestamp }}</span>
                      <span class="event-msg">{{ evt.message }}</span>
                    </div>
                    <div v-if="expandedEventId === evt.id && evt.details" class="event-details mono">
                      <pre>{{ JSON.stringify(evt.details, null, 2) }}</pre>
                    </div>
                  </div>
                </div>
                <EmptyState v-else title="暫無重大事件" description="最近無警告或異常通知" />
              </div>
            </div>
          </div>
        </div>

        <!-- Horizontal Main Splitter between Middle and Lower Tier -->
        <div
          class="splitter horizontal"
          @pointerdown="startHorizontalSplitDrag"
          @dblclick="resetHorizontalSplit"
          title="上下拖曳調整上下工作區高度比例 · 雙擊還原 56:44"
        >
          <div class="splitter-line"></div>
          <div class="splitter-grip horizontal"></div>
        </div>

        <!-- Lower Row (Lower Tier: 4 Monitoring Cards) -->
        <div
          class="tiling-row-tier"
          :style="{ height: `${100 - splits.middleHeightPct}%` }"
        >
          <!-- Pane 4: Risk Gauge -->
          <div
            class="tiling-pane pane-gauge"
            :style="{ width: `${splits.lowerWidths[0]}%` }"
          >
            <div class="pane-inner">
              <div class="pane-header-actions">
                <button type="button" class="btn-pane-action" @click="toggleMaximize('risk')" title="最大化聚焦">↗</button>
              </div>
              <RiskGauge :risk="riskState" />
            </div>
          </div>

          <!-- Vertical Splitter 3 -->
          <div
            class="splitter vertical"
            @pointerdown="e => startLowerVerticalSplitDrag(0, e)"
            @dblclick="resetLowerVerticalSplits"
            title="調整風控儀表與機器人佇列寬度 · 雙擊均分"
          >
            <div class="splitter-line"></div>
          </div>

          <!-- Pane 5: Bot Queue -->
          <div
            class="tiling-pane pane-bots"
            :style="{ width: `${splits.lowerWidths[1]}%` }"
          >
            <div class="pane-inner card">
              <div class="card-header">
                <div class="card-title">機器人隊列</div>
                <div class="card-actions">
                  <span class="badge badge-accent">{{ botQueue.length }} 實例</span>
                  <button type="button" class="btn-pane-action ml-1" @click="toggleMaximize('bots')" title="最大化聚焦">↗</button>
                </div>
              </div>
              <div class="card-body bots-body">
                <div v-if="botQueue.length" class="bots-list">
                  <div v-for="b in botQueue" :key="b.bot_id" class="bot-row">
                    <div class="bot-info">
                      <div class="bot-name">{{ b.name || b.bot_id }}</div>
                      <div class="bot-sub mono">{{ b.symbol }} · 持倉 {{ b.position_contracts || '0' }} 張</div>
                    </div>
                    <div class="bot-status-col">
                      <StatusBadge :status="b.state" />
                      <div
                        v-if="b.pnl_usdt"
                        class="bot-pnl tabular-nums"
                        :class="b.pnl_usdt.startsWith('+') ? 'text-success' : (b.pnl_usdt === '0.00' ? '' : 'text-danger')"
                      >
                        {{ b.pnl_usdt }} USDT
                      </div>
                    </div>
                  </div>
                </div>
                <EmptyState v-else title="無部署機器人" description="請前往機器人管理分配策略實例" />
              </div>
            </div>
          </div>

          <!-- Vertical Splitter 4 -->
          <div
            class="splitter vertical"
            @pointerdown="e => startLowerVerticalSplitDrag(1, e)"
            @dblclick="resetLowerVerticalSplits"
            title="調整機器人佇列與研究任務寬度 · 雙擊均分"
          >
            <div class="splitter-line"></div>
          </div>

          <!-- Pane 6: Research Tasks -->
          <div
            class="tiling-pane pane-research"
            :style="{ width: `${splits.lowerWidths[2]}%` }"
          >
            <div class="pane-inner card">
              <div class="card-header">
                <div class="card-title">近期研究任務</div>
                <div class="card-actions">
                  <span class="badge badge-neutral">Jesse 核心</span>
                </div>
              </div>
              <div class="card-body research-body">
                <div v-if="researchTasks.length" class="research-list">
                  <div v-for="t in researchTasks" :key="t.id" class="task-card">
                    <div class="task-header-row">
                      <strong class="task-name">{{ t.name }}</strong>
                      <span class="badge badge-sm badge-info">{{ t.version }}</span>
                    </div>
                    <div class="task-progress-bar">
                      <div class="progress-fill" :style="{ width: t.progress_pct + '%' }"></div>
                    </div>
                    <div class="task-footer-row">
                      <span class="task-desc">{{ t.description }}</span>
                      <span class="task-sharpe tabular-nums">Sharpe {{ t.sharpe }}</span>
                    </div>
                  </div>
                </div>
                <EmptyState v-else title="無研究任務" description="請前往策略中心啟動回測" />
              </div>
            </div>
          </div>

          <!-- Vertical Splitter 5 -->
          <div
            class="splitter vertical"
            @pointerdown="e => startLowerVerticalSplitDrag(2, e)"
            @dblclick="resetLowerVerticalSplits"
            title="調整研究任務與市場情報寬度 · 雙擊均分"
          >
            <div class="splitter-line"></div>
          </div>

          <!-- Pane 7: Yaozi Market Intelligence -->
          <div
            class="tiling-pane pane-yaozi"
            :style="{ width: `${splits.lowerWidths[3]}%` }"
          >
            <div class="pane-inner card">
              <div class="card-header">
                <div class="card-title">Yaozi 市場情報</div>
                <div class="card-actions">
                  <span class="badge badge-neutral tag-dev">開發中</span>
                </div>
              </div>
              <div class="card-body yaozi-body">
                <div v-if="yaoziAlerts.length" class="yaozi-list">
                  <div v-for="y in yaoziAlerts" :key="y.id" class="yaozi-item">
                    <div class="yaozi-header-row">
                      <span class="yaozi-title text-warning">{{ y.title }}</span>
                      <span class="yaozi-time tabular-nums">{{ y.time }}</span>
                    </div>
                    <div class="yaozi-summary">{{ y.summary }}</div>
                  </div>
                </div>
                <EmptyState v-else title="無情報快訊" description="目前未偵測到市場異常" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workspace-tiling {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: hidden;
  position: relative;
  background-color: var(--bg-base);
}

.tiling-ribbon {
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

.tiling-grid-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 6px 12px 10px 12px;
  gap: 4px;
}

.tiling-kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  flex-shrink: 0;
}

.tiling-main-viewport {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.tiling-row-tier {
  display: flex;
  width: 100%;
  overflow: hidden;
  min-height: 140px;
}

.tiling-pane {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  min-width: 120px;
  height: 100%;
}
.pane-inner {
  width: 100%;
  height: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.pane-header-actions {
  position: absolute;
  top: 6px;
  right: 8px;
  z-index: 10;
  display: flex;
  gap: 4px;
}
.btn-pane-action {
  background: rgba(14, 18, 24, 0.7);
  border: 1px solid rgba(220, 179, 71, 0.2);
  color: #8b9bb4;
  border-radius: 3px;
  width: 20px;
  height: 20px;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-pane-action:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: rgba(220, 179, 71, 0.15);
}

/* Continuous Splitter Bars */
.splitter {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
  touch-action: none;
  z-index: 15;
  transition: background-color 0.15s ease;
}
.splitter.vertical {
  width: 6px;
  cursor: col-resize;
  margin: 0 1px;
}
.splitter.horizontal {
  height: 6px;
  cursor: row-resize;
  margin: 1px 0;
  width: 100%;
}

.splitter .splitter-line {
  position: absolute;
  background-color: rgba(220, 179, 71, 0.12);
  transition: background-color 0.15s ease, box-shadow 0.15s ease;
}
.splitter.vertical .splitter-line {
  top: 0;
  bottom: 0;
  left: 2px;
  width: 2px;
}
.splitter.horizontal .splitter-line {
  left: 0;
  right: 0;
  top: 2px;
  height: 2px;
}

.splitter:hover .splitter-line,
.workspace-tiling.is-dragging .splitter .splitter-line {
  background-color: var(--accent);
  box-shadow: 0 0 8px rgba(220, 179, 71, 0.7);
}

.splitter-grip {
  width: 2px;
  height: 18px;
  border-radius: 1px;
  background-color: rgba(220, 179, 71, 0.4);
  opacity: 0;
  transition: opacity 0.15s ease;
}
.splitter-grip.horizontal {
  width: 18px;
  height: 2px;
}
.splitter:hover .splitter-grip {
  opacity: 1;
  background-color: var(--accent);
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

/* Cards & lists inside panes */
.events-body, .bots-body, .research-body, .yaozi-body {
  overflow-y: auto;
  padding: 6px 10px;
}
.events-list, .bots-list, .research-list, .yaozi-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.event-item {
  padding: 4px 6px;
  border-radius: 3px;
  background: rgba(14, 18, 24, 0.4);
  cursor: pointer;
  border: 1px solid transparent;
}
.event-item:hover {
  border-color: rgba(220, 179, 71, 0.2);
  background: rgba(220, 179, 71, 0.05);
}
.event-summary-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}
.event-time {
  color: var(--text-muted);
  font-size: 10px;
}
.event-msg {
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-details {
  margin-top: 4px;
  padding: 4px 6px;
  background: #090c10;
  font-size: 9px;
  border-radius: 3px;
  color: #8b9bb4;
}
.bot-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 6px;
  border-radius: 3px;
  background: rgba(14, 18, 24, 0.4);
}
.bot-name {
  font-size: 11.5px;
  font-weight: 600;
}
.bot-sub {
  font-size: 9.5px;
  color: var(--text-muted);
}
.bot-status-col {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}
.bot-pnl {
  font-size: 10px;
  font-weight: 600;
}
.task-card {
  padding: 4px 6px;
  border-radius: 3px;
  background: rgba(14, 18, 24, 0.4);
}
.task-header-row, .task-footer-row {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
}
.task-progress-bar {
  height: 3px;
  background: #1a2230;
  border-radius: 2px;
  margin: 3px 0;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: var(--accent);
}
.task-sharpe {
  color: var(--accent);
  font-weight: 600;
}
.yaozi-item {
  padding: 4px 6px;
  border-radius: 3px;
  background: rgba(14, 18, 24, 0.4);
}
.yaozi-header-row {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
}
.yaozi-title {
  font-weight: 600;
}
.yaozi-time {
  color: var(--text-muted);
}
.yaozi-summary {
  font-size: 9.5px;
  color: var(--text-secondary);
  margin-top: 2px;
}
</style>
