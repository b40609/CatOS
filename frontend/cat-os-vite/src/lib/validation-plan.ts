/**
 * Walk-forward request helpers for the validation page. The backend preflight
 * (catos/research_validation_job.py) is authoritative; these mirror its arithmetic
 * so the dialog can show the bar budget before submitting.
 */
import type { ResearchCatalog, ResearchDatasetMeta, ValidationRequest } from '@/adapters/research-api-adapter';

export interface ValidationForm {
  datasetId: string;
  periodLow: number;
  periodHigh: number;
  periodStep: number;
  trainBars: number;
  testBars: number;
  windows: number;
  lookbackBars: number;
  trendEfficiency: string;
  highVolatilityBps: string;
}

// Same fixed account as the optimization page: 2 contracts on 1,000 USDT.
export const VALIDATION_BACKTEST = {
  strategy_id: 'sma-trend',
  quantity: '2',
  initial_balance: '1000',
  fee_rate: '0.0005',
  slippage_bps: '2',
} as const;

const SYNTHETIC_SOURCE = 'synthetic_closed_bars';
const FETCHED_WINDOWS = 6;

/** Aligned candidate count of the SMA period grid, or null when the grid is not valid. */
export function candidateCount(form: Pick<ValidationForm, 'periodLow' | 'periodHigh' | 'periodStep'>): number | null {
  const { periodLow: low, periodHigh: high, periodStep: step } = form;
  if (![low, high, step].every(Number.isInteger)) return null;
  if (low < 2 || high > 32 || high <= low || step < 1 || step > 30 || (high - low) % step) return null;
  return (high - low) / step + 1;
}

/** Warm-up must cover the highest searched period (and stay below 64). */
export function warmupBars(form: Pick<ValidationForm, 'periodHigh'>): number {
  return form.periodHigh;
}

export function barsUsed(form: ValidationForm): number {
  return warmupBars(form) + form.trainBars + form.windows * form.testBars;
}

/** Bars replayed by every training trial and OOS run: the backend's preflight cost. */
export function barEvaluations(form: ValidationForm): number | null {
  const count = candidateCount(form);
  if (count === null) return null;
  const warmup = warmupBars(form);
  return form.windows * (count * (warmup + form.trainBars) + warmup + form.testBars);
}

export function requiredRuns(form: ValidationForm): number | null {
  const count = candidateCount(form);
  return count === null ? null : form.windows * (count + 1);
}

/**
 * Defaults per dataset. The synthetic fixture keeps the catalog example; a fetched
 * dataset gets SMA 8~32 step 8 and six windows sized to use every bar (train = 2 × test).
 * The regime thresholds stay the catalog's demonstration values for every dataset.
 */
export function defaultValidationForm(dataset: ResearchDatasetMeta, example: ValidationRequest): ValidationForm {
  const rule = {
    lookbackBars: example.regime_rule.lookback_bars,
    trendEfficiency: example.regime_rule.trend_efficiency,
    highVolatilityBps: example.regime_rule.high_volatility_bps,
  };
  if (dataset.source === SYNTHETIC_SOURCE) {
    const { low, high, step } = example.search_space.period;
    return {
      datasetId: dataset.id, periodLow: low, periodHigh: high, periodStep: step,
      trainBars: example.plan.train_bars, testBars: example.plan.test_bars, windows: example.plan.windows, ...rule,
    };
  }
  const periodHigh = 32;
  const testBars = Math.max(1, Math.floor((dataset.bars - periodHigh) / (FETCHED_WINDOWS + 2)));
  return {
    datasetId: dataset.id, periodLow: 8, periodHigh, periodStep: 8,
    trainBars: 2 * testBars, testBars, windows: FETCHED_WINDOWS, ...rule,
  };
}

/** Problems the backend would reject before execution; empty when the form can be submitted. */
export function validationProblems(
  form: ValidationForm,
  dataset: ResearchDatasetMeta | null,
  limits: ResearchCatalog['validation'] | undefined,
): string[] {
  const problems: string[] = [];
  const count = candidateCount(form);
  if (count === null) {
    problems.push('候選週期需在 2~32、最大值大於最小值，且差距為步進的整數倍');
  } else if (limits && count > limits.max_candidates) {
    problems.push(`候選數 ${count} 超過上限 ${limits.max_candidates}`);
  }
  if (!Number.isInteger(form.windows) || form.windows < 1 || (limits && form.windows > limits.max_windows)) {
    problems.push(`視窗數需在 1~${limits?.max_windows ?? 8}`);
  }
  if (!Number.isInteger(form.trainBars) || form.trainBars < 1 || !Number.isInteger(form.testBars) || form.testBars < 1) {
    problems.push('訓練與測試根數需為正整數');
  }
  const runs = requiredRuns(form);
  if (runs !== null && limits && runs > limits.max_runs) {
    problems.push(`需要 ${runs} 次回測，超過上限 ${limits.max_runs}`);
  }
  if (dataset && barsUsed(form) > dataset.bars) {
    problems.push(`需要 ${barsUsed(form).toLocaleString()} 根 K 線，資料集只有 ${dataset.bars.toLocaleString()} 根`);
  }
  const work = barEvaluations(form);
  if (work !== null && limits && work > limits.max_bar_evaluations) {
    problems.push(`計算量 ${work.toLocaleString()} 超過上限 ${limits.max_bar_evaluations.toLocaleString()}（避免超過 30 秒逾時）`);
  }
  if (!Number.isInteger(form.lookbackBars) || form.lookbackBars < 1) {
    problems.push('環境回看根數需為正整數');
  }
  return problems;
}

/** The exact request; max_candidates / max_runs are set to what the plan needs, never more. */
export function buildValidationRequest(form: ValidationForm): ValidationRequest {
  const count = candidateCount(form) ?? 0;
  return {
    backtest: {
      strategy_id: VALIDATION_BACKTEST.strategy_id,
      dataset_id: form.datasetId,
      parameters: { period: form.periodLow, quantity: VALIDATION_BACKTEST.quantity },
      initial_balance: VALIDATION_BACKTEST.initial_balance,
      fee_rate: VALIDATION_BACKTEST.fee_rate,
      slippage_bps: VALIDATION_BACKTEST.slippage_bps,
      warmup_bars: warmupBars(form),
    },
    search_space: { period: { low: form.periodLow, high: form.periodHigh, step: form.periodStep } },
    plan: { train_bars: form.trainBars, test_bars: form.testBars, windows: form.windows },
    regime_rule: {
      lookback_bars: form.lookbackBars,
      trend_efficiency: form.trendEfficiency.trim(),
      high_volatility_bps: form.highVolatilityBps.trim(),
    },
    max_candidates: count,
    max_runs: form.windows * (count + 1),
  };
}
