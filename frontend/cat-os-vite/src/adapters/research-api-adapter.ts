/**
 * Research API Adapter (Strict Real HTTP Adapter)
 * Interfaces with CatOS R1 Research HTTP API:
 *   GET  /api/research/version
 *   GET  /api/research/catalog
 *   GET  /api/research/runs
 *   POST /api/research/backtests
 *   POST /api/research/optimizations
 *   POST /api/research/validations
 *   GET  /api/research/runs/{run_id}
 *   GET  /api/research/runs/{run_id}/result
 *   GET  /api/research/runs/{run_id}/report
 *
 * Invariants:
 * 1. Strict Decimal string protocol on all monetary & ratio fields.
 * 2. Real API mode NEVER falls back to fixture on network/parse error.
 * 3. POST failure NEVER creates fake run_id, fake success, or auto-retry.
 * 4. Preserves 403, 409 (busy/restart), 413, 415, 422, 503 error details.
 */

export interface ResearchVersion {
  instance_id: string;
  pid: number;
  started_at: string;
  workspace: string;
  build_id: string;
  current_build_id: string;
  restart_required: boolean;
  active_run_id: string | null;
  mode: string;
  cache_policy: string;
}

export interface ResearchStrategyMeta {
  id: string;
  version: string;
  sha256: string;
  source: string;
  source_files: string[];
  entry: string;
  approval_state: string;
  name: string;
  // Integer parameters carry min/max (constructor order); quantity carries its unit.
  parameters: Record<string, { min?: number; max?: number; unit?: string }>;
  // warmup_bars >= the named parameter and < below; daily strategies also need min_days of bars.
  warmup: { covers: string; below: number; min_days?: number };
  // "vol_target": quantity caps contracts sized from equity; "fixed": quantity is traded as is.
  sizing?: 'fixed' | 'vol_target';
  // Preregistered strategies (package E) carry their frontend defaults.
  preset?: { parameters: Record<string, number>; quantity: string; warmup_days: number } | null;
}

export interface ResearchDatasetMeta {
  id: string;
  source: string;
  sha256: string;
  name: string;
  symbol: string;
  timeframe: string;
  bars: number;
  // Fetched OKX datasets also carry their range, funding flag, notice and per-file hashes.
  start_ms?: number | null;
  end_ms?: number | null;
  funding?: boolean;
  // How funding is counted: OKX keeps ~3 months, so a long dataset starts funding late.
  funding_coverage?: FundingCoverage;
  margin_model?: MarginModelSummary;
  notice?: string;
  files?: Record<string, string>;
  contract: {
    inst_id: string;
    base_per_contract: string;
    tick_size: string;
    lot_size: string;
    min_size: string;
  };
}

export interface BacktestRequest {
  strategy_id: string;
  dataset_id: string;
  // The strategy's integer parameters (SMA: period; Donchian: entry_bars, exit_bars)
  // plus quantity as a Decimal string e.g. "2".
  parameters: { quantity: string; [name: string]: number | string };
  initial_balance: string; // Decimal string e.g. "1000"
  fee_rate: string; // Decimal string e.g. "0.0005"
  slippage_bps: string; // Decimal string e.g. "2"
  warmup_bars: number; // integer >= the strategy's warmup.covers parameter and < warmup.below
}

export interface SearchRange {
  low: number;
  high: number;
  step: number;
}

export interface ResearchCatalog {
  strategies: ResearchStrategyMeta[];
  datasets: ResearchDatasetMeta[];
  defaults: BacktestRequest;
  optimization: {
    defaults: any;
    max_trials: number;
    score_name: string;
    direction: string;
    notice: string;
  };
  validation: {
    example_request: ValidationRequest;
    max_candidates: number;
    max_runs: number;
    max_windows: number;
    // windows × (candidates × (warmup + train) + warmup + test), checked before execution
    max_bar_evaluations: number;
    // Upper bound of regime_rule.lookback_bars (the classifier sums its window at every bar)
    max_lookback_bars: number;
    // OOS equity points kept per payload, shared by its windows
    max_curve_points: number;
    score_name: string;
    direction: string;
    notice: string;
  };
  limits: {
    concurrent_tasks: number;
    max_bars: number;
    timeout_seconds: number;
    max_runs: number;
    max_output_bytes: number;
  };
  model: string;
}

export interface OptimizationRequest {
  backtest: BacktestRequest;
  search_space: Record<string, SearchRange>; // one range per integer parameter
  n_trials: number;
  seed: number;
}

export interface ResearchRunStatus {
  run_id: string;
  kind: 'backtest' | 'optimization' | 'validation';
  status: 'queued' | 'running' | 'complete' | 'failed';
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  request: BacktestRequest | OptimizationRequest | any;
  provenance: any;
  build_id: string;
}

export interface TradeItem {
  time_ms: number;
  decision_time_ms: number;
  quantity: string; // Signed Decimal string: positive buy, negative sell
  price: string;
  fee: string;
  realized_pnl: string;
  position_after: string;
}

export interface EquityCurvePoint {
  time_ms: number;
  position: string;
  average_entry: string;
  balance: string;
  realized_pnl: string;
  unrealized_pnl: string;
  equity: string;
  fees: string;
  funding_paid: string;
}

export interface DrawdownCurvePoint {
  time_ms: number;
  drawdown_pct: string; // Decimal magnitude >= 0
}

export interface BacktestPerformance {
  initial_equity: string;
  final_equity: string;
  net_pnl: string;
  return_pct: string;
  realized_pnl: string;
  unrealized_pnl: string;
  fees: string;
  funding_paid: string;
  max_drawdown_pct: string;
  trade_count: number; // Exact integer simulated fills, not round trips
  // Margin model: clearance fee minus any security-fund cover; absent on older runs.
  liquidation_cost?: string;
}

// docs/research-margin-model.md: single-contract cross margin from OKX position tiers.
export interface MarginModelSummary {
  enabled: boolean;
  reason: string | null; // why it is off: "no_position_tiers" | "synthetic_fixture"
  reason_text: string | null;
  tiers_path: string | null;
  tiers_sha256: string | null;
  tiers: number | null;
  tiers_fetched_at_ms: number | null;
  leverage: string | null;
}

// The forced close (result.trades ends with its fill); null when the run was not liquidated.
export interface LiquidationRecord {
  time_ms: number;
  bar_open_time_ms: number;
  trigger: 'open' | 'adverse_extreme' | 'after_funding';
  trigger_price: string;
  liquidation_price: string;
  fill_price: string;
  gapped: boolean;
  position: string;
  average_entry: string;
  tier: number;
  maintenance_rate: string;
  balance_before: string;
  realized_pnl: string;
  clearance_fee: string;
  liquidation_fee: string;
  fee_charged: string;
  clearance_charged: string;
  deficit_covered: string;
  balance_after: string;
}

export interface FundingCoverage {
  source: 'dataset' | 'none';
  complete: boolean;
  from_ms: number | null; // first real funding event
  interval_ms: number | null;
}

// catos/research_costs.py: price_pnl = net_pnl + fees + slippage + funding_paid, valued at fill-bar opens.
export interface CostBreakdown {
  price_pnl: string;
  fees: string;
  slippage: string;
  funding_paid: string; // dataset funding actually applied; positive is a debit
  net_pnl: string;
  traded_notional: string;
  fill_count: number;
  cost_bps_per_side: string | null;
  break_even_bps_per_side: string | null;
  liquidation_cost?: string; // margin model only; absent on older runs
  buy_hold: {
    quantity: string;
    entry_open: string;
    exit_close: string;
    pnl: string; // before costs and funding
    underlying_return_pct: string;
  };
  // An assumption, never ledger data: fixed rate over the period real funding does not cover.
  funding_scenario: {
    rate: string;
    interval_ms: number;
    uncovered_start_ms: number;
    uncovered_end_ms: number;
    events: number;
    assumed_paid: string;
    net_pnl_with_assumption: string;
    notice: string;
  } | null;
}

// Sum of independent walk-forward OOS windows; ratios recomputed on the sums.
export interface CostTotal {
  windows: number;
  price_pnl: string;
  fees: string;
  slippage: string;
  funding_paid: string;
  net_pnl: string;
  traded_notional: string;
  fill_count: number;
  cost_bps_per_side: string | null;
  break_even_bps_per_side: string | null;
  liquidation_cost?: string; // margin model only; absent on older runs
  buy_hold_pnl: string;
  assumed_funding_paid: string | null;
  assumed_funding_events: number | null;
}

// catos/research_overfit.py: statistics only (fixed-digit strings), never money.
export interface OverfittingReport {
  method: string;
  distinct_trials: number; // this run only; earlier searches on the same data are not counted
  bars: number;
  // Trials whose equity reached <= 0 (no liquidation model): counted in N, left out of
  // the Sharpe variance and PBO. Absent before the 2026-11-08 F follow-up.
  wiped_out_trials?: number;
  best: {
    params: [string, number | string][];
    wiped_out?: boolean;
    // null when the selected trial itself was wiped out
    sharpe_per_bar: string | null;
    sharpe_annualized: string | null;
    skew: string | null;
    kurtosis: string | null; // non-excess
  };
  // null when fewer than two trials survived a search, so the variance is unknown
  trial_sharpe_variance: string | null;
  expected_max_sharpe_per_bar: string | null;
  expected_max_sharpe_annualized: string | null;
  psr_vs_zero: string | null;
  dsr: string | null;
  pbo: {
    pbo: string;
    logit_median: string;
    prob_oos_loss: string;
    splits: number;
    blocks: number;
    bars_per_block: number;
    // Share of splits whose winner sat exactly at the OOS median; absent before 2026-11-06 follow-up.
    logit_zero_share?: string;
  } | null;
  trials: { params: [string, number | string][]; sharpe_annualized: string | null; wiped_out?: boolean }[];
  verdict: string;
  notice: string;
}

export interface SelectionEdges {
  windows_with_selection: number;
  windows_at_edge: number;
  params: Record<string, { at_low: number; at_high: number }>;
  // On/off parameters (two values) are always on a boundary, so they are not counted.
  excluded_switch_params?: string[];
  notice: string;
}

// catos/research_trades.py: closed round trips after fees, slippage and funding (Decimal strings).
export interface TradeStats {
  closed_trips: number;
  wins: number;
  losses: number;
  breakeven: number;
  win_rate: string | null;
  average_win: string | null;
  average_loss: string | null;
  payoff_ratio: string | null;
  profit_factor: string | null;
  expectancy: string | null;
  largest_win: string | null;
  largest_loss: string | null;
  max_consecutive_losses: number;
  average_hold_hours: string | null;
  long: { trips: number; wins: number; win_rate: string | null; net_pnl: string };
  short: { trips: number; wins: number; win_rate: string | null; net_pnl: string };
  open_trip: { side: number; open_time_ms: number; net_pnl_with_unrealized: string } | null;
  notice: string;
}

// First close where equity reached <= 0, or the liquidation when the margin model is on.
export interface EquityWipedOut {
  time_ms: number;
  min_equity: string;
  liquidated?: boolean; // absent on runs archived before the margin model (2026-11-12)
  notice: string;
}

// Days of the run that would hit the account Soft/Hard daily-loss limits (catos/research_loss_limits.py).
export interface DailyLossLimitCount {
  limit_pct: string;
  days: number;
  per_year: string | null;
  first_day: string | null;
  listed: { day: string; loss_pct: string }[];
  truncated: boolean;
}

export interface DailyLossLimits {
  method: string;
  days_evaluated: number;
  span_days: number;
  years: string | null;
  first_day: string | null;
  last_day: string | null;
  max_daily_loss: { day: string; loss_pct: string; basis: string; low_equity: string; low_bar_open_ms: number } | null;
  stopped: { day: string; reason: "liquidation" | "equity_non_positive" } | null;
  straddling_bars: number;
  thresholds: {
    key: "current" | "legacy" | "proposed"; // "proposed": results archived before 2026-11-14
    label: string;
    applied_to_risk: boolean;
    soft: DailyLossLimitCount;
    hard: DailyLossLimitCount;
  }[];
  max_listed_days: number;
  notice: string[];
}

export interface BacktestResultPayload {
  // Absent on runs archived before the daily-loss diagnostic (2026-11-12).
  daily_loss_limits?: DailyLossLimits;
  // Absent on runs archived before round-trip statistics existed (2026-11-07).
  trade_stats?: TradeStats;
  // null when equity stayed above 0; absent on runs archived before 2026-11-08.
  equity_wiped_out?: EquityWipedOut | null;
  // Absent on runs archived before cost attribution existed.
  costs?: CostBreakdown;
  funding_coverage?: FundingCoverage;
  // Absent on runs archived before the margin model (2026-11-12): those ran without it.
  margin_model?: MarginModelSummary;
  run_id?: string;
  created_at?: string;
  build_id?: string;
  request: BacktestRequest;
  provenance: any;
  result: {
    config: any;
    warmup_bars: number;
    evaluation_start_ms: number;
    evaluation_end_ms: number;
    trades: TradeItem[];
    funding: any[];
    equity_curve: EquityCurvePoint[];
    performance: BacktestPerformance;
    pending_intent: any | null;
    assumptions: string[];
    liquidation?: LiquidationRecord | null;
    margin_rejection_count?: number;
  };
  drawdown_curve: DrawdownCurvePoint[];
  data_notice: string;
  trade_count_unit: string;
  // Present only when the curves were thinned for the payload; performance uses every bar.
  curve_sampling?: { total_points: number; returned_points: number; method: string };
}

export interface OptimizationTrial {
  number: number;
  state: string;
  params: Record<string, number>;
  score_decimal: string; // Exact Decimal string
  performance: BacktestPerformance | null;
  error: string | null;
}

export interface OptimizationResultPayload {
  kind: 'optimization';
  request: OptimizationRequest;
  provenance: any;
  trials: OptimizationTrial[];
  best_trial_number: number | null;
  objective: {
    name: string;
    direction: string;
    formula?: string;
  };
  seed: number;
  optuna_version: string;
  // Exact attribution of the best trial (one deterministic re-run); absent on older runs.
  best_costs?: CostBreakdown | null;
  // DSR / PBO over the distinct parameter sets of this run; absent on older runs.
  overfitting?: OverfittingReport | null;
  funding_coverage?: FundingCoverage;
  data_notice: string;
  run_id?: string;
  created_at?: string;
  build_id?: string;
}

export interface ValidationRequest {
  backtest: BacktestRequest;
  search_space: Record<string, SearchRange>; // one range per integer parameter
  plan:{ train_bars: number; test_bars: number; windows: number };
  regime_rule: {
    lookback_bars: number;
    trend_efficiency: string; // Decimal string in (0, 1]
    high_volatility_bps: string; // Decimal string > 0
  };
  max_candidates: number;
  max_runs: number;
}

export interface ValidationTrial {
  number: number;
  indices: number[];
  params: [string, number | string][]; // Name/value pairs, unlike the optimization object
  score: string | null;
  performance: BacktestPerformance | null;
  terminal_position: string | null;
  pending_intent: any | null;
  error: string | null;
}

export interface ValidationNeighborhood {
  trial_number: number;
  members: number[]; // Includes the center; axis neighbors only
  complete: boolean;
  worst_score: string | null;
  mean_score: string | null;
}

export interface ValidationWindow {
  number: number;
  train_start_ms: number;
  train_end_ms: number;
  test_start_ms: number;
  test_end_ms: number;
  status: 'COMPLETE' | 'NO_SELECTION' | 'OOS_FAILED';
  error: string | null;
  training: {
    selection_rule: string;
    selected_trial_number: number | null;
    trials: ValidationTrial[];
    neighborhoods: ValidationNeighborhood[];
    warmup_bars: number;
    evaluation_start_ms: number;
    evaluation_end_ms: number;
  };
  // Null when no candidate was selected or the OOS run failed; never a zero result.
  out_of_sample: {
    evaluation_start_ms: number;
    evaluation_end_ms: number;
    trades: TradeItem[];
    funding: any[];
    equity_curve: EquityCurvePoint[];
    performance: BacktestPerformance;
    pending_intent: any | null;
  } | null;
  // Present only when this window's OOS curve was thinned; performance uses every bar.
  curve_sampling?: { total_points: number; returned_points: number; method: string };
}

export interface RegimeSummary {
  regime: string;
  bar_count: number;
  positive_bars: number;
  negative_bars: number;
  zero_bars: number;
  fill_count: number;
  funding_payment_count: number;
  net_pnl: string;
  gross_pnl: string;
  fees: string;
  funding_paid: string;
}

export interface ValidationResultPayload {
  schema: string; // catos.research.validation-result.v2
  kind: 'validation';
  request: ValidationRequest;
  provenance: any;
  reproduction: any;
  objective: { name: string; direction: string; formula?: string };
  result: {
    rule: ValidationRequest['regime_rule'];
    rule_version: string;
    validation: {
      plan: { train_bars: number; test_bars: number; windows: number; warmup_bars: number };
      max_runs: number;
      required_runs: number;
      attempted_runs: number;
      unused_bars: number;
      complete: boolean;
      windows: ValidationWindow[];
    };
    windows: {
      number: number;
      status: string;
      selected_trial_number: number | null;
      error: string | null;
      evaluation: {
        summaries: RegimeSummary[];
        total: RegimeSummary;
        core_net_rounding_residual: string;
        reconciled: boolean;
      } | null;
    }[];
    // v2: per-bar labels and interval attribution are omitted; these totals remain.
    label_counts: { regime: string; bar_count: number }[];
    omitted_detail: string[];
    complete: boolean;
  };
  evaluation_complete: boolean;
  // Exact attribution per completed OOS window and their sum; absent on older runs.
  costs?: {
    windows: { number: number; costs: CostBreakdown }[];
    total: CostTotal | null;
    funding_coverage: FundingCoverage;
  };
  // Walk-forward choices on the boundary of the searched range; absent on older runs.
  selection_edges?: SelectionEdges;
  data_notice: string;
  run_id?: string;
  created_at?: string;
  build_id?: string;
}

// ==================== Error Definition ====================

export class ResearchApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    message?: string
  ) {
    super(message || `[HTTP ${status}] ${detail}`);
    this.name = 'ResearchApiError';
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText || 'Unknown Error';
    try {
      const data = await res.json();
      if (data && typeof data === 'object') {
        detail = data.detail || data.reason || JSON.stringify(data);
      }
    } catch {
      // Non-JSON error body
    }
    throw new ResearchApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

// ==================== Strict Real HTTP Client ====================

export const researchApi = {
  /**
   * Fetch current research service version and build identity
   */
  async getVersion(signal?: AbortSignal): Promise<ResearchVersion> {
    try {
      const res = await fetch('/api/research/version', {
        headers: { Accept: 'application/json' },
        signal,
      });
      return await handleResponse<ResearchVersion>(res);
    } catch (err: any) {
      if (err instanceof ResearchApiError) throw err;
      if (err.name === 'AbortError') throw err;
      throw new ResearchApiError(0, 'network_error', '無法連線至研究 API 服務 (127.0.0.1:8770)');
    }
  },

  /**
   * Fetch registered catalog, strategy metadata, limits, and defaults
   */
  async getCatalog(signal?: AbortSignal): Promise<ResearchCatalog> {
    try {
      const res = await fetch('/api/research/catalog', {
        headers: { Accept: 'application/json' },
        signal,
      });
      return await handleResponse<ResearchCatalog>(res);
    } catch (err: any) {
      if (err instanceof ResearchApiError) throw err;
      if (err.name === 'AbortError') throw err;
      throw new ResearchApiError(0, 'network_error', '無法載入研究目錄契約');
    }
  },

  /**
   * Fetch historical research task items (backtests, optimizations, validations)
   */
  async getRuns(signal?: AbortSignal): Promise<ResearchRunStatus[]> {
    try {
      const res = await fetch('/api/research/runs', {
        headers: { Accept: 'application/json' },
        signal,
      });
      const data = await handleResponse<{ items: ResearchRunStatus[] }>(res);
      return data.items || [];
    } catch (err: any) {
      if (err instanceof ResearchApiError) throw err;
      if (err.name === 'AbortError') throw err;
      throw new ResearchApiError(0, 'network_error', '無法取得歷史研究任務清單');
    }
  },

  /**
   * Poll status of an active or completed research task
   */
  async getRunStatus(runId: string, signal?: AbortSignal): Promise<ResearchRunStatus> {
    try {
      const res = await fetch(`/api/research/runs/${encodeURIComponent(runId)}`, {
        headers: { Accept: 'application/json' },
        signal,
      });
      return await handleResponse<ResearchRunStatus>(res);
    } catch (err: any) {
      if (err instanceof ResearchApiError) throw err;
      if (err.name === 'AbortError') throw err;
      throw new ResearchApiError(0, 'network_error', `無法查詢任務狀態 [${runId}]`);
    }
  },

  /**
   * Fetch complete JSON result for a completed task (requires status === 'complete')
   */
  async getRunResult<T = BacktestResultPayload>(runId: string, signal?: AbortSignal): Promise<T> {
    try {
      const res = await fetch(`/api/research/runs/${encodeURIComponent(runId)}/result`, {
        headers: { Accept: 'application/json' },
        signal,
      });
      return await handleResponse<T>(res);
    } catch (err: any) {
      if (err instanceof ResearchApiError) throw err;
      if (err.name === 'AbortError') throw err;
      throw new ResearchApiError(0, 'network_error', `無法讀取研究結果 JSON [${runId}]`);
    }
  },

  /**
   * Submit a new backtest request
   * Strict invariants:
   * - Must supply X-CatOS-Build
   * - Never creates fake run_id or auto-retries on failure
   */
  async submitBacktest(
    request: BacktestRequest,
    buildId: string,
    signal?: AbortSignal
  ): Promise<ResearchRunStatus> {
    try {
      const res = await fetch('/api/research/backtests', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CatOS-Build': buildId,
          Accept: 'application/json',
        },
        body: JSON.stringify(request),
        signal,
      });
      return await handleResponse<ResearchRunStatus>(res);
    } catch (err: any) {
      if (err instanceof ResearchApiError) throw err;
      if (err.name === 'AbortError') throw err;
      throw new ResearchApiError(0, 'network_error', '回測提交請求發送失敗，請先檢查任務清單確認狀態，勿盲目重送');
    }
  },

  /**
   * Submit a new optimization search request
   * Strict invariants:
   * - Must supply X-CatOS-Build
   * - Search space constrained by catalog (one low/high/step range per strategy parameter)
   * - Never creates fake run_id or auto-retries on failure
   */
  async submitOptimization(
    request: OptimizationRequest,
    buildId: string,
    signal?: AbortSignal
  ): Promise<ResearchRunStatus> {
    try {
      const res = await fetch('/api/research/optimizations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CatOS-Build': buildId,
          Accept: 'application/json',
        },
        body: JSON.stringify(request),
        signal,
      });
      return await handleResponse<ResearchRunStatus>(res);
    } catch (err: any) {
      if (err instanceof ResearchApiError) throw err;
      if (err.name === 'AbortError') throw err;
      throw new ResearchApiError(0, 'network_error', '優化搜尋提交失敗，請先檢查任務清單確認狀態，勿盲目重送');
    }
  },

  /**
   * Submit a walk-forward validation (exhaustive grid, independent OOS windows)
   * Strict invariants:
   * - Must supply X-CatOS-Build
   * - max_candidates / max_runs are explicit budgets; the backend never extends them
   * - Never creates fake run_id or auto-retries on failure
   */
  async submitValidation(
    request: ValidationRequest,
    buildId: string,
    signal?: AbortSignal
  ): Promise<ResearchRunStatus> {
    try {
      const res = await fetch('/api/research/validations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CatOS-Build': buildId,
          Accept: 'application/json',
        },
        body: JSON.stringify(request),
        signal,
      });
      return await handleResponse<ResearchRunStatus>(res);
    } catch (err: any) {
      if (err instanceof ResearchApiError) throw err;
      if (err.name === 'AbortError') throw err;
      throw new ResearchApiError(0, 'network_error', '滾動驗證提交失敗，請先檢查任務清單確認狀態，勿盲目重送');
    }
  },
};
