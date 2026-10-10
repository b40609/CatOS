/**
 * Simulation Run and Execution Results contract
 */
import type { BotControlState } from './bot';

export interface RunAccountDTO {
  equity: string;
  position: string;
  balance: string;
  realized_pnl: string;
  fees: string;
  funding_paid?: string;
}

/**
 * Raw Run snapshot DTO from GET /api/workspace/simulation/runs/{run_id}
 */
export interface RunDTO {
  contract: string;
  run_id: string;
  bot_id?: string;
  template_id?: string;
  control_state: BotControlState;
  cleanup_confirmed: boolean;
  stop_requested: boolean;
  request_id: string;
  build_id: string;
  instance_id: string;
  bars: number;
  warmup_bars: number;
  fills: number;
  events: any[];
  events_omitted: number;
  worker_closed: boolean;
  error: string | null;
  created_at: string;
  finished_at: string | null;
  stop_requested_at: string | null;
  still_finishing: boolean;
  last_signal?: any;
  last_fill?: any;
  account?: RunAccountDTO;
  artifact_hash?: string;
  binding?: {
    artifact_hash: string;
    artifact?: any;
    parameters?: any;
  };
  symbol?: string;
  period?: string;
  slippage_bps?: string;
}

export interface RunsResponseDTO {
  items: RunDTO[];
  state: 'available' | 'unavailable' | 'error';
  issues: string[];
}

/**
 * Presentation View Model for UI components
 */
export interface SimulationRun {
  run_id: string;
  bot_id: string;
  strategy_id: string;
  artifact_hash: string;
  control_state: BotControlState;
  symbol: string;
  period: string; // e.g. "15m"
  warmup_bars: number;
  total_bars: number;
  current_bar: number;
  trade_count: number;
  position_contracts: string; // Decimal string, e.g. "0", "-1"
  equity_usdt: string;        // Decimal string, e.g. "1000.00385505"
  fee_usdt: string;           // Decimal string, e.g. "0.00404495"
  pnl_usdt: string;           // Decimal string
  slippage_bps: string;       // Decimal string, e.g. "2"
  ownership_retained: boolean; // stopped with position retains exclusive contract
  risk_retained: boolean;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  error_message?: string;
}

export interface SimulationResultSummary {
  run_id: string;
  bot_id: string;
  status: BotControlState;
  final_equity: string;
  total_trades: number;
  final_position: string;
  total_fee: string;
  bars_processed: number;
  stopped_reason?: string;
}

