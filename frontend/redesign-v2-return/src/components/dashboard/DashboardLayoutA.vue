<script setup lang="ts">
import { ref } from 'vue';
import MetricCard from '@/components/common/MetricCard.vue';
import SparklineArea from '@/components/common/SparklineArea.vue';
import DonutChart from '@/components/common/DonutChart.vue';
import RiskGauge from '@/components/common/RiskGauge.vue';
import StatusBadge from '@/components/common/StatusBadge.vue';
import EmptyState from '@/components/common/EmptyState.vue';
import AuditTimeline from '@/components/common/AuditTimeline.vue';
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
</script>

<template>
  <div class="layout-a-container">
    <!-- Offline / Unavailable Error Alert Banner -->
    <div v-if="isUnavailable || error" class="alert-banner-danger">
      <div class="alert-icon">⚠️</div>
      <div class="alert-content">
        <strong>{{ error || '503 服務不可用：底座連線中斷或離線' }}</strong>
        <p>安全底線約束：禁止未知狀態轉零或正常。底座未確認連線前，禁止宣告安全並阻擋所有交易下單。</p>
      </div>
    </div>

    <!-- Layer 1: 4 Key Performance Indicators -->
    <div class="layer-kpis">
      <MetricCard
        label="總權益淨值"
        :value="isUnavailable ? '— USDT' : (kpis?.total_equity ? kpis.total_equity + ' USDT' : '--')"
        :subText="isUnavailable ? '服務離線 · 無法讀取' : ('實時持倉估值 + 現金餘額 (' + (kpis?.equity_change_pct || '0.00%') + ')')"
        :subType="isUnavailable ? 'neg' : 'pos'"
        :borderType="isUnavailable ? 'danger' : 'accent'"
        :isEquity="true"
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


    <!-- Layer 2: 3-column Visual Core (48% : 28% : 24%) -->
    <div class="layer-core">
      <!-- 48% Equity Trend -->
      <div class="col-equity">
        <SparklineArea :points="equityPoints" />
      </div>

      <!-- 28% Margin & Exposure Donut -->
      <div class="col-donut">
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

      <!-- 24% Events Timeline -->
      <div class="col-events card p-3">
        <AuditTimeline :events="auditEvents" :showHeader="true" maxHeight="280px" />
      </div>
    </div>

    <!-- Layer 3: 4-column Execution & Research Summary (34% : 22% : 22% : 22%) -->
    <div class="layer-summary">
      <!-- 34% Risk Safety Gauge -->
      <div class="col-gauge">
        <RiskGauge :risk="riskState" />
      </div>

      <!-- 22% Bot Queue -->
      <div class="col-bots card">
        <div class="card-header">
          <div class="card-title">
            <span>機器人隊列</span>
          </div>
          <div class="card-actions">
            <span class="badge badge-accent">{{ botQueue.length }} 實例</span>
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

      <!-- 22% Research Tasks -->
      <div class="col-research card">
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

      <!-- 22% Yaozi Market Intelligence -->
      <div class="col-yaozi card">
        <div class="card-header">
          <div class="card-title">市場情報</div>
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
</template>

<style scoped>
.layout-a-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  padding: var(--space-4);
  overflow-y: auto;
  flex: 1;
}

.alert-banner-danger {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-md);
  color: #fca5a5;
  font-size: var(--text-sm);
  line-height: 1.4;
}

.alert-banner-danger strong {
  color: #f87171;
  font-size: var(--text-base);
  display: block;
  margin-bottom: 2px;
}

.alert-icon {
  font-size: 20px;
  flex-shrink: 0;
}


.layer-kpis, .layer-core, .layer-summary {
  flex-shrink: 0;
}

.col-equity, .col-donut, .col-events, .col-gauge, .col-bots, .col-research, .col-yaozi {
  flex-shrink: 0;
}

/* Layer 1: 4 KPIs Grid */
.layer-kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
}

/* Layer 2: 3-column (48% : 28% : 24%) */
.layer-core {
  display: grid;
  grid-template-columns: 48fr 28fr 24fr;
  gap: var(--space-3);
  min-height: 250px;
}

.events-body {
  overflow-y: auto;
  max-height: 220px;
  padding: var(--space-2) var(--space-3);
}

.events-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.event-item {
  padding: 6px 8px;
  background: var(--bg-surface-elevated);
  border-radius: var(--radius-xs);
  border-left: 2px solid var(--border-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.event-item:hover {
  background: var(--bg-surface-hover);
  border-left-color: var(--accent);
}

.event-summary-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-xs);
}

.event-time {
  color: var(--text-muted);
  font-size: 10px;
}

.event-msg {
  color: var(--text-secondary);
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.event-details {
  margin-top: 6px;
  padding: 6px;
  background: var(--bg-base);
  border-radius: var(--radius-xs);
  font-size: 10px;
  color: var(--text-secondary);
}

/* Layer 3: 4-column (34% : 22% : 22% : 22%) */
.layer-summary {
  display: grid;
  grid-template-columns: 34fr 22fr 22fr 22fr;
  gap: var(--space-3);
  min-height: 230px;
}

.bots-body, .research-body, .yaozi-body {
  overflow-y: auto;
  max-height: 210px;
  padding: var(--space-3);
}

.bots-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bot-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 8px;
  background: var(--bg-surface-elevated);
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-secondary);
}

.bot-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.bot-name {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-primary);
}

.bot-sub {
  font-size: 10px;
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

/* Research Task Cards */
.research-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-card {
  padding: 8px;
  background: var(--bg-surface-elevated);
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-secondary);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-name {
  font-size: var(--text-xs);
  color: var(--text-primary);
}

.task-progress-bar {
  width: 100%;
  height: 4px;
  background: var(--bg-base);
  border-radius: var(--radius-xs);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
}

.task-footer-row {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text-muted);
}

.task-sharpe {
  color: var(--accent);
  font-weight: 600;
}

/* Yaozi Alerts */
.yaozi-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.yaozi-item {
  padding: 8px;
  background: var(--bg-surface-elevated);
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-secondary);
}

.yaozi-header-row {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 4px;
}

.yaozi-time {
  font-size: 10px;
  color: var(--text-muted);
}

.yaozi-summary {
  font-size: 10px;
  color: var(--text-secondary);
  line-height: 1.4;
}

.text-success { color: var(--color-success); }
.text-danger { color: var(--color-danger); }
.text-warning { color: var(--color-warning); }

/* Responsive adjustments for 1280px and 1024px */
@media (max-width: 1280px) {
  .layer-core {
    grid-template-columns: 55fr 45fr;
    height: auto;
  }
  .col-events {
    grid-column: span 2;
  }
  .layer-summary {
    grid-template-columns: 1fr 1fr;
    height: auto;
  }
}

@media (max-width: 1024px) {
  .layer-kpis {
    grid-template-columns: 1fr 1fr;
  }
  .layer-core {
    display: flex !important;
    flex-direction: column !important;
    height: auto !important;
  }
  .layer-summary {
    display: flex !important;
    flex-direction: column !important;
    height: auto !important;
  }
  .col-events {
    grid-column: auto !important;
  }
}
</style>

