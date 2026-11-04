/**
 * Bot contract (GET /api/workspace/simulation/bots, /bots/{bot_id}).
 * Field names follow docs/simulation-api-contract-draft.md section 8.1.
 */
import type { DecimalString } from './decimal';

export type BotMode = 'local' | 'demo' | 'live';

export type BotControlState =
  | 'starting'
  | 'running'
  | 'stopping'
  | 'completed'
  | 'stopped'
  | 'failed'
  | 'recovery_required';

export const ACTIVE_STATES: ReadonlySet<BotControlState> = new Set(['starting', 'running', 'stopping']);

export interface ContractSpecDTO {
  inst_id: string;
  base_per_contract: DecimalString;
  tick_size: DecimalString;
  lot_size: DecimalString;
  min_size: DecimalString;
}

export type AccountSource = 'final_account' | 'signal' | 'signal_fill' | null;

export interface BotViewDTO {
  version: number;
  bot_id: string;
  mode: 'local';
  strategy_id: string;
  strategy_version: string;
  strategy_name: string;
  artifact_hash: string;
  parameters: Record<string, string | number>;
  inst_id: string | null;
  symbol: string | null;
  contract: ContractSpecDTO | null;
  timeframe_ms: number;
  trusted: true;
  created_at_ms: number;
  state: BotControlState;
  current_run_id: string | null;
  active: boolean;
  run_count: number;
  worker_pid: number | null;
  bars: number;
  warmup_bars: number;
  fills: number;
  last_synthetic_time_ms: number | null;
  run_created_at_ms: number | null;
  finished_at_ms: number | null;
  account_source: AccountSource;
  position: DecimalString | null;
  average_entry: DecimalString | null;
  balance: DecimalString | null;
  realized_pnl: DecimalString | null;
  unrealized_pnl: DecimalString | null;
  equity: DecimalString | null;
  fees: DecimalString | null;
  funding_paid: DecimalString | null;
  mark: DecimalString | null;
  last_disposition: string | null;
  last_reason: string | null;
  ownership_retained: boolean;
  error: string | null;
}
