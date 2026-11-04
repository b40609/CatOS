/**
 * Walk-forward request helpers for the validation page. The backend preflight
 * (catos/research_validation_job.py) is authoritative; these mirror its arithmetic
 * so the dialog can show the bar budget before submitting.
 */
import type {
  ResearchCatalog, ResearchDatasetMeta, ResearchStrategyMeta, ValidationRequest,
} from '@/adapters/research-api-adapter';
import { compareDecimal, signOf } from '@/lib/format';
import {
  type Axis, DONCHIAN_ID, donchianAxes, gridBase, gridCount, gridProblems, gridWarmup, paramSpecs,
} from '@/lib/research-strategies';

export interface ValidationForm {
  datasetId: string;
  strategyId: string;
  axes: Record<string, Axis>; // one range per integer parameter of the strategy
  trainBars: number;
  testBars: number;
  windows: number;
  lookbackBars: number;
  trendEfficiency: string;
  highVolatilityBps: string;
}

// Same fixed account as the optimization page: 2 contracts on 1,000 USDT.
export const VALIDATION_BACKTEST = {
  quantity: '2',
  initial_balance: '1000',
  fee_rate: '0.0005',
  slippage_bps: '2',
} as const;

const SYNTHETIC_SOURCE = 'synthetic_closed_bars';
const FETCHED_WINDOWS = 6;
// Plain positive Decimal text as typed in the dialog; the backend accepts at most 64 characters.
const PLAIN_DECIMAL = /^\d+(\.\d+)?$/;

function positiveDecimal(text: string): boolean {
  const value = text.trim();
  return value.length <= 64 && PLAIN_DECIMAL.test(value) && signOf(value) === 'positive';
}

/**
 * Aligned candidate count, or null when the grid is not valid. A single-parameter
 * grid needs two values on its axis; a multi-parameter grid needs two points in total.
 */
export function candidateCount(form: Pick<ValidationForm, 'axes'>, strategy: ResearchStrategyMeta): number | null {
  const count = gridCount(strategy, form.axes);
  if (count === null || count < 2 || gridProblems(strategy, form.axes).length) return null;
  return count;
}

/** Warm-up must cover the grid's highest look-back value (and stay below the catalog limit). */
export function warmupBars(form: Pick<ValidationForm, 'axes'>, strategy: ResearchStrategyMeta): number {
  return gridWarmup(strategy, form.axes);
}

export function barsUsed(form: ValidationForm, strategy: ResearchStrategyMeta): number {
  return warmupBars(form, strategy) + form.trainBars + form.windows * form.testBars;
}

/** Bars replayed by every training trial and OOS run: the backend's preflight cost. */
export function barEvaluations(form: ValidationForm, strategy: ResearchStrategyMeta): number | null {
  const count = candidateCount(form, strategy);
  if (count === null) return null;
  const warmup = warmupBars(form, strategy);
  return form.windows * (count * (warmup + form.trainBars) + warmup + form.testBars);
}

export function requiredRuns(form: ValidationForm, strategy: ResearchStrategyMeta): number | null {
  const count = candidateCount(form, strategy);
  return count === null ? null : form.windows * (count + 1);
}

/**
 * Defaults per dataset and strategy. SMA on the synthetic fixture keeps the catalog
 * example; on a fetched dataset it gets 8~32 step 8. Donchian uses donchianAxes. A
 * fetched dataset gets six windows sized to use every bar (train = 2 × test). The
 * regime thresholds stay the catalog's demonstration values for every dataset.
 */
export function defaultValidationForm(
  dataset: ResearchDatasetMeta, example: ValidationRequest, strategy: ResearchStrategyMeta,
): ValidationForm {
  const rule = {
    lookbackBars: example.regime_rule.lookback_bars,
    trendEfficiency: example.regime_rule.trend_efficiency,
    highVolatilityBps: example.regime_rule.high_volatility_bps,
  };
  const synthetic = dataset.source === SYNTHETIC_SOURCE;
  const axes = strategy.id === DONCHIAN_ID ? donchianAxes(dataset)
    : synthetic ? { ...example.search_space } : { period: { low: 8, high: 32, step: 8 } };
  const base = { datasetId: dataset.id, strategyId: strategy.id, axes, ...rule };
  if (synthetic) {
    return { ...base, trainBars: example.plan.train_bars, testBars: example.plan.test_bars, windows: example.plan.windows };
  }
  const testBars = Math.max(1, Math.floor((dataset.bars - gridWarmup(strategy, axes)) / (FETCHED_WINDOWS + 2)));
  return { ...base, trainBars: 2 * testBars, testBars, windows: FETCHED_WINDOWS };
}

/** Problems the backend would reject before execution; empty when the form can be submitted. */
export function validationProblems(
  form: ValidationForm,
  dataset: ResearchDatasetMeta | null,
  limits: ResearchCatalog['validation'] | undefined,
  strategy: ResearchStrategyMeta,
): string[] {
  const problems = gridProblems(strategy, form.axes);
  const total = gridCount(strategy, form.axes);
  if (!problems.length && total !== null && total < 2) {
    problems.push('候選組合至少需要 2 組');
  }
  const count = candidateCount(form, strategy);
  if (count !== null && limits && count > limits.max_candidates) {
    problems.push(`候選數 ${count} 超過上限 ${limits.max_candidates}`);
  }
  const warmup = warmupBars(form, strategy);
  if (warmup >= strategy.warmup.below) {
    problems.push(`預熱根數 ${warmup} 需小於 ${strategy.warmup.below}`);
  }
  if (!Number.isInteger(form.windows) || form.windows < 1 || (limits && form.windows > limits.max_windows)) {
    problems.push(`視窗數需在 1~${limits?.max_windows ?? 8}`);
  }
  if (!Number.isInteger(form.trainBars) || form.trainBars < 1 || !Number.isInteger(form.testBars) || form.testBars < 1) {
    problems.push('訓練與測試根數需為正整數');
  }
  const runs = requiredRuns(form, strategy);
  if (runs !== null && limits && runs > limits.max_runs) {
    problems.push(`需要 ${runs} 次回測，超過上限 ${limits.max_runs}`);
  }
  if (dataset && barsUsed(form, strategy) > dataset.bars) {
    problems.push(`需要 ${barsUsed(form, strategy).toLocaleString()} 根 K 線，資料集只有 ${dataset.bars.toLocaleString()} 根`);
  }
  const work = barEvaluations(form, strategy);
  if (work !== null && limits && work > limits.max_bar_evaluations) {
    problems.push(`計算量 ${work.toLocaleString()} 超過上限 ${limits.max_bar_evaluations.toLocaleString()}（避免超過 30 秒逾時）`);
  }
  const maxLookback = limits?.max_lookback_bars ?? 512;
  if (!Number.isInteger(form.lookbackBars) || form.lookbackBars < 1 || form.lookbackBars > maxLookback) {
    problems.push(`環境回看根數需在 1~${maxLookback}`);
  }
  if (!positiveDecimal(form.trendEfficiency) || compareDecimal(form.trendEfficiency.trim(), '1') === 1) {
    problems.push('趨勢效率門檻需為大於 0、不超過 1 的小數（例如 0.5）');
  }
  if (!positiveDecimal(form.highVolatilityBps)) {
    problems.push('高波動門檻需為大於 0 的數字（bps，例如 25）');
  }
  return problems;
}

/** The exact request; max_candidates / max_runs are set to what the plan needs, never more. */
export function buildValidationRequest(form: ValidationForm, strategy: ResearchStrategyMeta): ValidationRequest {
  const count = candidateCount(form, strategy) ?? 0;
  return {
    backtest: {
      strategy_id: strategy.id,
      dataset_id: form.datasetId,
      parameters: { ...gridBase(strategy, form.axes), quantity: VALIDATION_BACKTEST.quantity },
      initial_balance: VALIDATION_BACKTEST.initial_balance,
      fee_rate: VALIDATION_BACKTEST.fee_rate,
      slippage_bps: VALIDATION_BACKTEST.slippage_bps,
      warmup_bars: warmupBars(form, strategy),
    },
    search_space: Object.fromEntries(paramSpecs(strategy).map((spec) => [spec.name, { ...form.axes[spec.name] }])),
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
