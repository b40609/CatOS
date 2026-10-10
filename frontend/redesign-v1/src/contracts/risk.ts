/**
 * Risk Control and Invariants contract
 * Fixed Tag: 41cb53c54d6dABDE
 * Strict Decimal string handling
 */

export type RiskStatus = 'normal' | 'soft_latch' | 'hard_latch' | 'missing';

export interface RiskState {
  status: RiskStatus;
  fixed_tag: '41cb53c54d6dABDE';
  effective_leverage: string; // e.g. "1.85"
  leverage_limit: string;     // e.g. "3.00"
  single_asset_budget_ratio: string; // e.g. "0.50" (50%)
  day_start_equity_usdt: string;    // e.g. "1000.00"
  current_equity_usdt: string;      // e.g. "1018.42"
  daily_pnl_usdt: string;           // e.g. "+18.42"
  daily_pnl_pct: string;            // e.g. "+1.84%"
  soft_loss_limit_pct: string;      // e.g. "-10.0%"
  hard_loss_limit_pct: string;      // e.g. "-20.0%"
  current_drawdown_pct: string;     // e.g. "-0.30%"
  exposure_nominal_usdt: string;    // e.g. "1420.50"
  exposure_budget_usdt: string;     // e.g. "3000.00"
  margin_used_usdt: string;         // e.g. "450.20"
  margin_available_usdt: string;    // e.g. "550.00"
  latched_reasons: string[];
}

export interface ExposureAllocationItem {
  label: string;
  nominal_usdt: string;
  pct_share: number;
  color: string;
}
