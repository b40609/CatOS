/**
 * Risk and position projections (GET /risk, GET /positions).
 * Everything monetary is a Decimal string computed by the backend; the UI
 * only formats. Fields the local simulation cannot know are `null`, and the
 * UI renders them as "not applicable", never as 0 or a placeholder number.
 */
import type { BotControlState } from './bot';
import type { DecimalString } from './decimal';

export type RiskStatus = 'normal' | 'soft_latch' | 'hard_latch' | 'missing';

export interface RiskLimitsDTO {
  leverage: DecimalString;
  symbol_share: DecimalString;
  soft_loss: DecimalString;
  hard_loss: DecimalString;
}

export interface RiskBasisDTO {
  day: number;
  equity: DecimalString;
  evidence_id: string;
  account_alias?: string;
  environment?: string;
  source?: string;
  digest?: string;
  evidence?: Record<string, unknown>;
  period_start_ms: number;
}

export interface RiskObservationDTO {
  seq: number;
  time_ms: number;
  valid_until_ms: number;
  equity: DecimalString;
  risk_equity: DecimalString;
  position: DecimalString;
  mark: DecimalString;
  pending_buy: DecimalString;
  pending_sell: DecimalString;
  other_notional: DecimalString;
  external_net: DecimalString;
  valuation_known: boolean;
  flows_known: boolean;
  margin_ok: boolean;
  position_verified: boolean;
  reduction_conflict: boolean;
  flow_basis_id: string | null;
  flow_start_ms: number | null;
}

export interface RiskDerivedDTO {
  period_pnl: DecimalString | null;
  period_pnl_ratio: DecimalString | null;
  notional: DecimalString | null;
  effective_leverage: DecimalString | null;
  exposure_budget: DecimalString | null;
  symbol_budget: DecimalString | null;
  can_increase: boolean;
  status: RiskStatus;
}

export interface RiskSnapshotDTO {
  version: number;
  run_id: string;
  bot_id: string;
  run_state: BotControlState;
  seq: number;
  time_ms: number;
  mode: 'RUN' | 'NO_INCREASE' | 'FLAT';
  health: 'RECONCILING' | 'HEALTHY' | 'DEGRADED';
  phase: 'IDLE' | 'WORKING' | 'VERIFY' | 'WAIT' | 'DONE';
  reasons: string[];
  epoch: number;
  limits: RiskLimitsDTO;
  basis: RiskBasisDTO | null;
  snapshot: RiskObservationDTO | null;
  derived: RiskDerivedDTO;
}

export interface PositionDTO {
  bot_id: string;
  run_id: string;
  run_state: BotControlState;
  inst_id: string | null;
  symbol: string | null;
  position: DecimalString;
  average_entry: DecimalString;
  mark: DecimalString | null;
  unrealized_pnl: DecimalString;
  notional: DecimalString | null;
  verified: boolean | null;
  protection: null;
  funding_interval_ms: null;
  funding_rate: null;
  liquidation_price: null;
  margin: null;
}
