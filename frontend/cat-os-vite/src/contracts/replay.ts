/**
 * Read-only approvals and Bot replays (GET /api/workspace/replay, step 2).
 * Approving, revoking and starting a replay are CLI-only; nothing here mutates.
 */
import type { DecimalString } from './decimal';

export interface ReplayApprovalDTO {
  approval_id: string;
  state: 'active' | 'revoked';
  revoked_at: string | null;
  created_at: string;
  strategy_id: string;
  version: string;
  entry: string;
  source_sha256: string;
  manifest_sha256: string;
  /** "changed": the source or manifest no longer matches, so the approval cannot resolve. */
  source: 'current' | 'changed';
  research_basis: string | null;
  parameters: Record<string, number>;
  quantity: DecimalString;
  inst_id: string;
  timeframe_ms: number;
  warmup_bars: number;
  initial_balance: DecimalString;
  fee_rate: DecimalString;
  slippage_bps: DecimalString;
}

export interface ReplayRunDTO {
  run_id: string;
  created_at: string;
  approval_id: string;
  strategy_id: string;
  version: string;
  parameters: Record<string, number>;
  inst_id: string;
  timeframe_ms: number;
  dataset_id: string | null;
  bars: number;
  risk_limits: Record<string, DecimalString>;
  pace_seconds: number;
  state: 'running' | 'completed' | 'stopped' | 'failed' | 'unknown';
  bars_done: number;
  fills: number | null;
  stop_reason: string | null;
  last_time_ms: number | null;
  elapsed_seconds: number | null;
  final_equity: DecimalString | null;
  final_position: DecimalString | null;
  consistency: {
    passed: boolean | null;
    checks: Record<string, boolean> | null;
    research_fills: number | null;
    reversal_decisions: number | null;
  } | null;
}

export interface ReplayOverviewDTO {
  contract: 'catos.replay.v1';
  approvals_state: 'available' | 'unavailable';
  approvals_path: string;
  eligible: { strategy_id: string; version: string; source_sha256: string }[];
  approvals: ReplayApprovalDTO[];
  runs: ReplayRunDTO[];
  issues: string[];
  notice: string;
}
