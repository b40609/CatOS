/**
 * Workspace aggregate (GET /api/workspace/simulation/state) and the pieces it
 * is assembled from. Domain versions let each store slice apply its own
 * monotonic guard.
 */
import type { BotViewDTO } from './bot';
import type { DecimalString } from './decimal';
import type { KillSwitchDTO, PositionDTO, RiskSnapshotDTO, RiskStatus } from './risk';
import type { RunDTO } from './run';
import type { RegisteredStrategyDTO } from './strategy';

export interface VersionDTO {
  contract: 'catos.simulation.v1';
  mode: string;
  build_id: string;
  current_build_id: string;
  restart_required: boolean;
  instance_id: string;
  slot: 'idle' | 'starting' | 'running' | 'stopping' | 'recovery_required' | 'unavailable';
  active_run_id: string | null;
  capabilities: { start: boolean; stop: boolean };
  unavailable_reason: string | null;
  config: Record<string, unknown>;
}

export interface SummaryDTO {
  equity: DecimalString;
  realized_pnl: DecimalString;
  unrealized_pnl: DecimalString;
  fees: DecimalString;
  period_pnl: DecimalString | null;
  period_pnl_ratio: DecimalString | null;
  period_start_ms: number | null;
  basis_equity: DecimalString | null;
  running_bots: number;
  total_bots: number;
  risk_status: RiskStatus | null;
  effective_leverage: DecimalString | null;
  leverage_limit: DecimalString;
  invariants: { fixed_tag: string; settlement: string; arithmetic: string };
}

export type EventKind =
  | 'run_state'
  | 'stop_requested'
  | 'warmup'
  | 'day_basis'
  | 'signal'
  | 'fill'
  | 'final_account'
  | 'stop'
  | 'anomaly'
  | 'kill_switch'
  | (string & {});

export type EventLevel = 'INFO' | 'WARN' | 'ERROR';
export type EventCategory = 'SUPERVISOR' | 'WORKER' | 'RISK' | 'ORDER' | 'SYSTEM';

export interface EventDTO {
  seq: number;            // global sequence per data root, monotonic across runs
  run_id: string;
  bot_id: string;
  kind: EventKind;
  wall_time_ms: number | null;
  synthetic_time_ms: number | null;
  level: EventLevel;
  category: EventCategory;
  payload: Record<string, unknown>;
}

export interface EventsPageDTO {
  items: EventDTO[];
  next_since: number;
  more: boolean;
  version: number;
  omitted: number;
}

export const STATE_DOMAINS = ['service', 'bots', 'risk', 'positions', 'events'] as const;
export type StateDomain = (typeof STATE_DOMAINS)[number];

export interface WorkspaceStateDTO {
  contract: 'catos.simulation.v1';
  version: number;
  instance_id: string;
  observed_at_ms: number;
  unchanged: false;
  service: VersionDTO;
  strategies: RegisteredStrategyDTO[];
  bots: BotViewDTO[];
  risk: RiskSnapshotDTO | null;
  positions: PositionDTO[];
  summary: SummaryDTO | null;
  events: { items: EventDTO[]; next_since: number; omitted: number };
  domains: Record<StateDomain, number>;
  // Work package B; versioned with the `risk` domain. Absent from older backends.
  kill_switch?: KillSwitchDTO;
}

export interface WorkspaceUnchangedDTO {
  contract: 'catos.simulation.v1';
  version: number;
  instance_id: string;
  observed_at_ms: number;
  unchanged: true;
}

export type WorkspaceStateResponse = WorkspaceStateDTO | WorkspaceUnchangedDTO;

export interface StartBotResponseDTO {
  run: RunDTO;
  bot: BotViewDTO;
  version: number;
}
