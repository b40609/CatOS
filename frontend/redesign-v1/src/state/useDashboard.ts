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
  const { activeScenario } = useWorkspace();
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

  async function loadData() {
    loading.value = true;
    error.value = null;
    try {
      // If service is unavailable, fetchDashboardKPIs throws 503
      kpis.value = await activeAdapter.fetchDashboardKPIs();
      equityPoints.value = await activeAdapter.fetchEquityCurve(preferences.value.chartRange);
      exposureItems.value = await activeAdapter.fetchExposureAllocation();
      auditEvents.value = await activeAdapter.fetchAuditEvents();
      riskState.value = await activeAdapter.fetchRiskState();
      botQueue.value = await activeAdapter.fetchBotQueue();
      researchTasks.value = await activeAdapter.fetchResearchTasks();
      yaoziAlerts.value = await activeAdapter.fetchYaoziAlerts();
      isUnavailable.value = false;
    } catch (err: any) {
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
      loading.value = false;
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
    () => preferences.value.chartRange,
    async (newRange) => {
      if (!isUnavailable.value) {
        equityPoints.value = await activeAdapter.fetchEquityCurve(newRange);
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
