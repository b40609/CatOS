/**
 * Research API Adapter (Strict Real HTTP Adapter)
 * Interfaces with CatOS R1 Research HTTP API:
 *   GET  /api/research/version
 *   GET  /api/research/catalog
 *   GET  /api/research/runs
 *   POST /api/research/backtests
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
  market_status: string;
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
  parameters: {
    period: { min: number; max: number };
    quantity: { unit: string };
  };
}

export interface ResearchDatasetMeta {
  id: string;
  source: string;
  sha256: string;
  name: string;
  symbol: string;
  timeframe: string;
  bars: number;
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
  parameters: {
    period: number;
    quantity: string; // Decimal string e.g. "2"
  };
  initial_balance: string; // Decimal string e.g. "1000"
  fee_rate: string; // Decimal string e.g. "0.0005"
  slippage_bps: string; // Decimal string e.g. "2"
  warmup_bars: number; // integer >= period and < 64
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
    example_request: any;
    max_candidates: number;
    max_runs: number;
    max_windows: number;
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
  search_space: {
    period: { low: number; high: number; step: number };
  };
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
}

export interface BacktestResultPayload {
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
  };
  drawdown_curve: DrawdownCurvePoint[];
  data_notice: string;
  trade_count_unit: string;
}

export interface OptimizationTrial {
  number: number;
  state: string;
  params: {
    period: number;
  };
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
   * - Search space constrained by catalog (SMA period low/high/step)
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
};
