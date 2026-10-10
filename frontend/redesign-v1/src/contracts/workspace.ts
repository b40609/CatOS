/**
 * Workspace and Telemetry Contracts
 */
import type { BotMode } from './bot';

export interface TelemetryState {
  connected: boolean;
  supervisor_pid: number;
  latency_ms: number;
  fixed_tag: '41cb53c54d6dABDE';
  settlement_mode: 'cross_net_mode';
  core_arithmetic: 'Decimal_SQLite_TEXT';
  last_heartbeat: string;
}

export interface VersionDTO {
  contract: 'catos.simulation.v1';
  mode: string;
  build_id: string;
  current_build_id: string;
  restart_required: boolean;
  instance_id: string;
  slot: string;
  active_run_id: string | null;
  capabilities: {
    start: boolean;
    stop: boolean;
  };
  unavailable_reason: string | null;
  config: Record<string, any>;
}

export interface WorkspaceState {
  mode: BotMode;
  telemetry: TelemetryState;
  active_scenario: string;
}

