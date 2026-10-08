<script setup lang="ts">
import { computed } from 'vue';
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

const actionItems = computed(() => {
  const items = [];

  if (isUnavailable.value || error.value) {
    items.push({
      id: 'act-err',
      level: 'DANGER',
      title: '503 服務不可用（底座連線中斷）',
      desc: error.value || '底座遙測服務中斷，禁止未知狀態轉零或宣告安全。已阻擋所有交易下單與增倉控制。'
    });
    return items;
  }

  if (riskState.value?.status === 'soft_latch') {
    items.push({
      id: 'act-1',
      level: 'WARN',
      title: '日損軟限鎖存中 (-10.0%)',
      desc: '帳戶已觸發 Soft 軟限，目前僅允許合法減倉，已停止增倉。需等待每日 00:00 切日或人工解除。'
    });
  }
  const stoppedBotWithPos = botQueue.value.find(b => b.state === 'stopped' && b.position_contracts !== '0');
  if (stoppedBotWithPos) {
    items.push({
      id: 'act-2',
      level: 'DANGER',
      title: `合約獨佔未釋放 (${stoppedBotWithPos.symbol})`,
      desc: `Bot ${stoppedBotWithPos.name || stoppedBotWithPos.bot_id} 已停止但仍持有 ${stoppedBotWithPos.position_contracts} 張部位。禁止新 Bot 綁定此合約 (409)。`
    });
  }
  if (!items.length) {
    items.push({
      id: 'act-ok',
      level: 'INFO',
      title: '風控與委託狀態正常',
      desc: '所有運行中機器人均符合單幣與總帳戶槓桿預算，無在途異常委託。'
    });
  }
  return items;
});
</script>

<template>
  <div class="layout-b-container">
    <!-- Offline / Unavailable Error Alert Banner -->
    <div v-if="isUnavailable || error" class="alert-banner-danger">
      <div class="alert-icon">⚠️</div>
      <div class="alert-content">
        <strong>{{ error || '503 服務不可用：底座連線中斷或離線' }}</strong>
        <p>安全底線約束：禁止未知狀態轉零或正常。底座未確認連線前，禁止宣告安全並阻擋所有交易下單。</p>
      </div>
    </div>

    <!-- Top KPI Strip -->
    <div class="kpi-strip">
      <div class="strip-item">
        <span class="st-lbl">總權益淨值</span>
        <span class="st-val tabular-nums text-accent">
          {{ isUnavailable ? '— USDT' : (kpis?.total_equity ? kpis.total_equity + ' USDT' : '--') }}
        </span>
        <span class="st-sub" :class="isUnavailable ? 'text-danger' : 'text-success'">
          ({{ isUnavailable ? 'OFFLINE' : (kpis?.equity_change_pct || '0.0%') }})
        </span>
      </div>
      <div class="strip-divider"></div>
      <div class="strip-item">
        <span class="st-lbl">今日損益</span>
        <span
          class="st-val tabular-nums"
          :class="isUnavailable ? 'text-danger' : (kpis?.today_pnl?.startsWith('+') ? 'text-success' : 'text-danger')"
        >
          {{ isUnavailable ? '— USDT' : (kpis?.today_pnl || '--') }}
        </span>
      </div>
      <div class="strip-divider"></div>
      <div class="strip-item">
        <span class="st-lbl">運行中 Bot</span>
        <span class="st-val tabular-nums">
          {{ isUnavailable ? '— / —' : `${kpis?.running_bots_count ?? 0} / ${kpis?.total_bots_count ?? 0}` }}
        </span>
      </div>
      <div class="strip-divider"></div>
      <div class="strip-item">
        <span class="st-lbl">有效槓桿</span>
        <span class="st-val tabular-nums">
          {{ isUnavailable ? '—' : `${kpis?.effective_leverage || '--'}x / 3.00x` }}
        </span>
      </div>
    </div>


    <!-- Main Workspace Split: 68% Left Focus / 32% Right Actions & Diagnostics -->
    <div class="layout-b-main">
      <!-- 68% Left Focus: Large Trend + Bot Queue -->
      <div class="left-focus-col">
        <!-- Large Trend Area -->
        <div class="large-trend-box">
          <SparklineArea :points="equityPoints" title="帳戶整體淨值走勢（大視圖焦點）" />
        </div>

        <!-- Bot Management & Runs Table -->
        <div class="bots-table-card card">
          <div class="card-header">
            <div class="card-title">
              <span>機器人實例與持倉監控</span>
            </div>
            <div class="card-actions">
              <span class="badge badge-accent">{{ botQueue.length }} 實例</span>
            </div>
          </div>

          <div class="card-body p-0">
            <div v-if="botQueue.length" class="data-table-container">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>機器人名稱</th>
                    <th>合約代碼</th>
                    <th>策略版本</th>
                    <th>持倉張數</th>
                    <th>當前損益</th>
                    <th>狀態</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="b in botQueue" :key="b.bot_id">
                    <td>
                      <strong>{{ b.name || b.bot_id }}</strong>
                      <div class="mono text-muted text-2xs">{{ b.bot_id }}</div>
                    </td>
                    <td class="mono">{{ b.symbol }}</td>
                    <td class="mono">{{ b.binding.artifact.version }}</td>
                    <td class="tabular-nums">
                      <span :class="b.position_contracts !== '0' ? 'text-accent' : ''">
                        {{ b.position_contracts || '0' }} 張
                      </span>
                    </td>
                    <td class="tabular-nums">
                      <span :class="b.pnl_usdt?.startsWith('+') ? 'text-success' : 'text-danger'">
                        {{ b.pnl_usdt }} USDT
                      </span>
                    </td>
                    <td>
                      <StatusBadge :status="b.state" />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <EmptyState v-else title="暫無部署機器人" description="請前往機器人管理頁面建立新實例" />
          </div>
        </div>

        <!-- Research Tasks Row -->
        <div class="research-summary-card card">
          <div class="card-header">
            <div class="card-title">研究與回測任務摘要</div>
          </div>
          <div class="card-body">
            <div class="res-grid">
              <div v-for="t in researchTasks" :key="t.id" class="res-item">
                <div class="res-top">
                  <strong>{{ t.name }}</strong>
                  <span class="badge badge-sm badge-info">{{ t.version }}</span>
                </div>
                <div class="res-desc">{{ t.description }}</div>
                <div class="res-bottom">
                  <span>進度: {{ t.progress_pct }}%</span>
                  <span class="text-accent tabular-nums">Sharpe {{ t.sharpe }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 32% Right Focused Column: Action Items, Safety Gauge, Donut -->
      <div class="right-focus-col">
        <!-- Urgent Action Items / Alerts -->
        <div class="actions-card card">
          <div class="card-header">
            <div class="card-title">
              <span>需處理事項與預警</span>
            </div>
            <div class="card-actions">
              <span class="badge badge-warning">{{ actionItems.length }} 事項</span>
            </div>
          </div>
          <div class="card-body actions-body">
            <div
              v-for="act in actionItems"
              :key="act.id"
              :class="['action-box', act.level === 'DANGER' ? 'act-danger' : (act.level === 'WARN' ? 'act-warn' : 'act-info')]"
            >
              <div class="act-header">
                <span class="act-icon">⚠</span>
                <strong class="act-title">{{ act.title }}</strong>
              </div>
              <div class="act-desc">{{ act.desc }}</div>
            </div>
          </div>
        </div>

        <!-- Daily Loss Safety Gauge -->
        <div class="gauge-box">
          <RiskGauge :risk="riskState" />
        </div>

        <!-- Exposure Allocation Donut -->
        <div class="donut-box">
          <DonutChart :items="exposureItems" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.layout-b-container {
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


/* KPI Top Strip */
.kpi-strip {
  display: flex;
  align-items: center;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  padding: 10px var(--space-5);
  gap: var(--space-5);
}

.strip-item {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.st-lbl {
  font-size: var(--text-xs);
  color: var(--text-muted);
}

.st-val {
  font-size: var(--text-md);
  font-weight: 700;
  color: var(--text-primary);
}

.st-sub {
  font-size: var(--text-2xs);
}

.strip-divider {
  width: 1px;
  height: 20px;
  background: var(--border-secondary);
}

/* Main Split (68% : 32%) */
.layout-b-main {
  display: grid;
  grid-template-columns: 68fr 32fr;
  gap: var(--space-4);
}

.left-focus-col {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.large-trend-box {
  min-height: 260px;
}

.p-0 {
  padding: 0 !important;
}

.res-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.res-item {
  background: var(--bg-surface-elevated);
  padding: 10px;
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-secondary);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.res-top, .res-bottom {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
}

.res-desc {
  font-size: 11px;
  color: var(--text-secondary);
}

/* Right Focused Column */
.right-focus-col {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.actions-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.action-box {
  padding: 10px 12px;
  border-radius: var(--radius-xs);
  font-size: var(--text-xs);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.act-warn {
  background: var(--color-warning-bg);
  border: 1px solid var(--color-warning-border);
  color: #ffe6b0;
}

.act-danger {
  background: var(--color-danger-bg);
  border: 1px solid var(--color-danger-border);
  color: #ffc2bf;
}

.act-info {
  background: var(--color-info-bg);
  border: 1px solid var(--color-info-border);
  color: #c4e1ff;
}

.act-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.act-desc {
  font-size: 11px;
  opacity: 0.9;
  line-height: 1.4;
}

.text-accent { color: var(--accent); }
.text-success { color: var(--color-success); }
.text-danger { color: var(--color-danger); }
.text-muted { color: var(--text-muted); }

@media (max-width: 1024px) {
  .layout-b-main {
    grid-template-columns: 1fr;
  }
}
</style>
