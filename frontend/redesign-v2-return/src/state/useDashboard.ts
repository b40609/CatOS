import { ref, watch } from 'vue';
import type {
  DashboardKPIs,
  EquityPoint,
  ResearchTask,
  YaoziAlert
} from '@/adapters/types';
import type {
  RiskState,
  ExposureAllocationItem,
  AuditLogItem,
  Bot
} from '@/contracts';
import { activeAdapter } from '@/adapters/mock-adapter';
import { useWorkspace } from './useWorkspace';
import { usePreferences } from './usePreferences';

export function useDashboard() {
  const { activeScenario, currentMode } = useWorkspace();
  const { preferences } = usePreferences();

  const loading = ref<boolean>(false);
  const error = ref<string | null>(null);
  const isUnavailable = ref<boolean>(false);

  const kpis = ref<DashboardKPIs | null>(null);
  const equityPoints = ref<EquityPoint[]>([]);
  const exposureItems = ref<ExposureAllocationItem[]>([]);
  const auditEvents = ref<AuditLogItem[]>([]);
  const riskState = ref<RiskState | null>(null);
  const botQueue = ref<Bot[]>([]);
  const researchTasks = ref<ResearchTask[]>([]);
  const yaoziAlerts = ref<YaoziAlert[]>([]);

  let currentLoadToken = 0;

  async function loadData() {
    const token = ++currentLoadToken;
    loading.value = true;
    error.value = null;

    // Immediately clear local mode simulation state on mode switch
    if (currentMode.value !== 'local') {
      kpis.value = null;
      riskState.value = null;
      auditEvents.value = [];
      researchTasks.value = [];
      yaoziAlerts.value = [];
      botQueue.value = [];
      equityPoints.value = [];
      exposureItems.value = [];
    }

    try {
      // If service is unavailable, fetchDashboardKPIs throws 503
      const newKpis = await activeAdapter.fetchDashboardKPIs();
      if (token !== currentLoadToken) return;
      kpis.value = newKpis;

      const newEquity = await activeAdapter.fetchEquityCurve(preferences.value.chartRange);
      if (token !== currentLoadToken) return;
      equityPoints.value = newEquity;

      const newExposure = await activeAdapter.fetchExposureAllocation();
      if (token !== currentLoadToken) return;
      exposureItems.value = newExposure;

      const newAudit = await activeAdapter.fetchAuditEvents();
      if (token !== currentLoadToken) return;
      auditEvents.value = newAudit;

      const newRisk = await activeAdapter.fetchRiskState();
      if (token !== currentLoadToken) return;
      riskState.value = newRisk;

      const newBots = await activeAdapter.fetchBotQueue();
      if (token !== currentLoadToken) return;
      botQueue.value = newBots;

      const newTasks = await activeAdapter.fetchResearchTasks();
      if (token !== currentLoadToken) return;
      researchTasks.value = newTasks;

      const newAlerts = await activeAdapter.fetchYaoziAlerts();
      if (token !== currentLoadToken) return;
      yaoziAlerts.value = newAlerts;

      isUnavailable.value = false;
    } catch (err: any) {
      if (token !== currentLoadToken) return;
      error.value = err.message || '資料讀取失敗：底座連線中斷或 503 不可用';
      isUnavailable.value = true;
      // Invariant: MUST NOT retain stale data to pretend safety!
      kpis.value = {
        total_equity: '--',
        equity_change_pct: '--',
        today_pnl: '--',
        today_pnl_pct: '--',
        running_bots_count: 0,
        total_bots_count: 0,
        bots_summary_note: '服務離線 · 無法讀取狀態',
        risk_status: 'UNAVAILABLE',
        effective_leverage: '--',
        leverage_limit: '3.00',
        risk_sub_note: '服務不可用 · 需人工檢查'
      };
      equityPoints.value = [];
      exposureItems.value = [];
      riskState.value = {
        status: 'missing',
        fixed_tag: '41cb53c54d6dABDE',
        effective_leverage: '--',
        leverage_limit: '3.00',
        single_asset_budget_ratio: '0.50',
        day_start_equity_usdt: '--',
        current_equity_usdt: '--',
        daily_pnl_usdt: '--',
        daily_pnl_pct: '--',
        soft_loss_limit_pct: '-10.0%',
        hard_loss_limit_pct: '-20.0%',
        current_drawdown_pct: '--',
        exposure_nominal_usdt: '--',
        exposure_budget_usdt: '--',
        margin_used_usdt: '--',
        margin_available_usdt: '--',
        latched_reasons: ['SERVICE_UNAVAILABLE_503']
      };

      botQueue.value = [];
    } finally {
      if (token === currentLoadToken) {
        loading.value = false;
      }
    }
  }

  watch(
    () => activeScenario.value,
    () => {
      loadData();
    },
    { immediate: true }
  );

  watch(
    () => currentMode.value,
    () => {
      loadData();
    }
  );

  watch(
    () => preferences.value.chartRange,
    async (newRange) => {
      const token = currentLoadToken;
      const mode = currentMode.value;
      if (!isUnavailable.value && mode === 'local') {
        const points = await activeAdapter.fetchEquityCurve(newRange);
        if (token === currentLoadToken && mode === currentMode.value && newRange === preferences.value.chartRange) {
          equityPoints.value = points;
        }
      }
    }
  );

  return {
    loading,
    error,
    isUnavailable,
    kpis,
    equityPoints,
    exposureItems,
    auditEvents,
    riskState,
    botQueue,
    researchTasks,
    yaoziAlerts,
    refresh: loadData
  };
}
