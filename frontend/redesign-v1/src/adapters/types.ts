/**
 * Adapter interface for catOS Workspace
 * All page and component interactions go through this interface.
 * UI components never directly call fetch or mutate backend state.
 */
import type {
  StrategyEntry,
  StrategyArtifact,
  Bot,
  SimulationRun,
  RiskState,
  ExposureAllocationItem,
  AuditLogItem,
  TelemetryState,
  CommandRecord,
  BotMode
} from '@/contracts';

export type ScenarioType =
  | 'normal'
  | 'soft_loss'
  | 'hold_stopped_409'
  | 'empty'
  | 'service_unavailable'
  | 'demo_live_locked';

export interface DashboardKPIs {
  total_equity: string;        // Decimal string, e.g. "125480.50"
  equity_change_pct: string;   // e.g. "+1.00%"
  today_pnl: string;           // Decimal string, e.g. "+1240.80"
  today_pnl_pct: string;       // e.g. "+1.00%"
  running_bots_count: number;  // e.g. 1
  total_bots_count: number;    // e.g. 3
  bots_summary_note: string;   // e.g. "1 運行中 · 1 需處理 · 1 已停止"
  risk_status: 'NORMAL' | 'SOFT_LATCH' | 'HARD_LATCH' | 'MISSING' | 'UNAVAILABLE' | 'UNKNOWN';
  effective_leverage: string;  // e.g. "1.85"
  leverage_limit: string;      // e.g. "3.00"
  risk_sub_note: string;       // e.g. "日損軟限 10.0% · 當前回撤 -0.30%"
}

export interface EquityPoint {
  timestamp: string;
  timeLabel: string;
  equity: number; // presentation copy only
  equity_str: string; // Decimal string
}

export interface ResearchTask {
  id: string;
  name: string;
  version: string;
  status: 'COMPLETED' | 'RUNNING' | 'PENDING' | 'FAILED';
  progress_pct: number;
  sharpe: string;
  description: string;
}

export interface YaoziAlert {
  id: string;
  time: string;
  type: string;
  title: string;
  tag: string;
  status: string;
  summary: string;
}

export interface WorkspaceAdapter {
  scenario: ScenarioType;
  setScenario(s: ScenarioType): void;
  getCommandLogs(): CommandRecord[];
  getPendingCommand(): import('@/contracts').PendingCommand | null;
  retryPendingCommand(): Promise<any>;
  clearPendingCommand(): void;
  resetStorage(): void;

  fetchVersion(): Promise<import('@/contracts').VersionDTO>;
  fetchTelemetry(): Promise<TelemetryState>;
  fetchDashboardKPIs(): Promise<DashboardKPIs>;
  fetchEquityCurve(range: '7D' | '30D' | '90D'): Promise<EquityPoint[]>;
  fetchExposureAllocation(): Promise<ExposureAllocationItem[]>;
  fetchAuditEvents(): Promise<AuditLogItem[]>;
  fetchRiskState(): Promise<RiskState>;
  fetchBotQueue(): Promise<Bot[]>;
  fetchResearchTasks(): Promise<ResearchTask[]>;
  fetchYaoziAlerts(): Promise<YaoziAlert[]>;

  fetchStrategies(): Promise<StrategyEntry[]>;
  fetchRuns(): Promise<SimulationRun[]>;

  createStrategy(requestId: string, artifact: StrategyArtifact): Promise<StrategyEntry>;
  allocateBot(
    requestId: string,
    payload: {
      bot_id: string;
      artifact_hash: string;
      parameters: Record<string, any>;
      trusted: boolean;
      mode?: BotMode;
    }
  ): Promise<Bot>;
  startBot(requestId: string, botId: string): Promise<SimulationRun>;
  stopBot(requestId: string, runId: string): Promise<SimulationRun>;
  setMode?(m: BotMode): void;
}

