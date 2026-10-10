/**
 * Bot contract definition
 * Strict adherence to catOS v1:
 * Single bot exclusive swap contract, cross + net_mode, Decimal values
 */
import type { StrategyArtifact, BoundedJsonValue } from './strategy';

export type BotMode = 'local' | 'demo' | 'live';

export type BotControlState =
  | 'starting'
  | 'running'
  | 'stopping'
  | 'completed'
  | 'stopped'
  | 'failed'
  | 'recovery_required';

export interface BotBinding {
  artifact: StrategyArtifact;
  artifact_hash: string;
  parameters: Record<string, BoundedJsonValue>;
}

/**
 * Raw Bot metadata returned from GET /api/workspace/simulation/bots
 * Pure static binding, no runtime state
 */
export interface BotDTO {
  bot_id: string;
  mode: BotMode;
  binding: BotBinding;
  trusted: boolean; // Must be manually confirmed, cannot be pre-checked
  created_at: string;
}

/**
 * View Model for UI components, merged from BotDTO and latest RunDTO
 */
export interface Bot extends BotDTO {
  name?: string;
  symbol: string; // e.g. "BTC-USDT-SWAP"
  state: BotControlState;
  current_run_id?: string;
  pnl_usdt?: string; // Decimal string
  position_contracts?: string; // Decimal string, e.g. "0", "-1"
  equity_usdt?: string;
  fee_usdt?: string;
  ownership_retained?: boolean;
  risk_retained?: boolean;
  last_signal?: any;
  last_fill?: any;
}

