/**
 * Labels, grid checks and per-dataset defaults for the fixed research strategies.
 * Bounds and the warm-up rule come from the catalog; the backend
 * (catos/research_catalog.py) stays authoritative and repeats every check.
 */
import type { ResearchDatasetMeta, ResearchStrategyMeta } from '@/adapters/research-api-adapter';

export const SMA_ID = 'sma-trend';
export const DONCHIAN_ID = 'donchian-breakout';

export interface ParamSpec {
  name: string;
  min: number;
  max: number;
}

export interface Axis {
  low: number;
  high: number;
  step: number;
}

const LABELS: Record<string, string> = { period: 'SMA 週期', entry_bars: '進場通道', exit_bars: '出場通道' };
const SHORT_NAMES: Record<string, string> = { [SMA_ID]: 'SMA', [DONCHIAN_ID]: 'Donchian' };
// [lower, upper]: every parameter set keeps lower strictly below upper (a Donchian exit
// channel shorter than its entry channel), so every grid point is a valid request.
const ORDERED: Record<string, [string, string][]> = { [DONCHIAN_ID]: [['exit_bars', 'entry_bars']] };
const SYNTHETIC_SOURCE = 'synthetic_closed_bars';

export const paramLabel = (name: string) => LABELS[name] ?? name;
export const shortName = (strategyId?: string | null) => (strategyId && SHORT_NAMES[strategyId]) || strategyId || '未知策略';

/** The selected strategy, falling back to the first registered one when the id is unknown. */
export function pickStrategy(strategies: ResearchStrategyMeta[] | undefined, id: string | null) {
  return strategies?.find((s) => s.id === id) ?? strategies?.[0] ?? null;
}

/** Integer parameters in catalog (constructor) order; quantity is set separately. */
export function paramSpecs(meta: ResearchStrategyMeta): ParamSpec[] {
  return Object.entries(meta.parameters)
    .filter(([name]) => name !== 'quantity')
    .map(([name, bound]) => ({ name, min: bound.min ?? 0, max: bound.max ?? 0 }));
}

/** "entry_bars=192, exit_bars=48" from a request's parameters or a trial's [name, value] pairs. */
export function formatParams(params?: Record<string, unknown> | [string, unknown][] | null): string {
  if (!params) return '';
  const entries = Array.isArray(params) ? params : Object.entries(params).filter(([name]) => name !== 'quantity');
  return entries.map(([name, value]) => `${name}=${String(value)}`).join(', ');
}

/** Trial parameters without names when there is one ("32"), else as name=value pairs. */
export function formatTrialParams(params?: [string, unknown][] | Record<string, unknown> | null): string {
  if (!params) return '';
  const entries = Array.isArray(params) ? params : Object.entries(params);
  return entries.length === 1 ? String(entries[0][1]) : formatParams(entries);
}

/** "entry_bars 96~384/96 · exit_bars 24~72/24" from a request's search space. */
export function formatRanges(space?: Record<string, Axis> | null): string {
  if (!space) return '';
  return Object.entries(space).map(([name, axis]) => `${name} ${axis.low}~${axis.high}/${axis.step}`).join(' · ');
}

/** Problems with a warm-up that would leave no evaluation bar in the dataset. */
export function warmupBarsProblems(warmup: number, dataset: ResearchDatasetMeta | null): string[] {
  return dataset && warmup >= dataset.bars ? [`預熱根數 ${warmup} 需少於資料集的 ${dataset.bars} 根`] : [];
}

/** Problems with one parameter set and its warm-up; empty when the backtest can be submitted. */
export function paramProblems(meta: ResearchStrategyMeta, values: Record<string, number>, warmup: number): string[] {
  const problems: string[] = [];
  for (const spec of paramSpecs(meta)) {
    const value = values[spec.name];
    if (!Number.isInteger(value) || value < spec.min || value > spec.max) {
      problems.push(`${paramLabel(spec.name)}（${spec.name}）需為 ${spec.min}~${spec.max} 的整數`);
    }
  }
  for (const [lower, upper] of ORDERED[meta.id] ?? []) {
    if (values[lower] >= values[upper]) problems.push(`${paramLabel(lower)}需小於${paramLabel(upper)}`);
  }
  const covers = values[meta.warmup.covers];
  if (!Number.isInteger(warmup) || warmup < covers || warmup >= meta.warmup.below) {
    problems.push(`預熱根數需 ≥ ${paramLabel(meta.warmup.covers)}（${covers}）且小於 ${meta.warmup.below}`);
  }
  return problems;
}

/** Aligned value count on one axis, or null when it is outside the bounds or misaligned. */
export function axisCount(axis: Axis | undefined, spec: ParamSpec): number | null {
  if (!axis) return null;
  const { low, high, step } = axis;
  if (![low, high, step].every(Number.isInteger)) return null;
  if (low < spec.min || high > spec.max || high < low || step < 1 || step > spec.max - spec.min) return null;
  if ((high - low) % step) return null;
  return (high - low) / step + 1;
}

/** Grid size, or null when an axis is invalid. */
export function gridCount(meta: ResearchStrategyMeta, axes: Record<string, Axis>): number | null {
  let count = 1;
  for (const spec of paramSpecs(meta)) {
    const values = axisCount(axes[spec.name], spec);
    if (values === null) return null;
    count *= values;
  }
  return count;
}

/** Axis and ordering problems; every grid point must be a valid parameter set. */
export function gridProblems(meta: ResearchStrategyMeta, axes: Record<string, Axis>): string[] {
  const problems: string[] = [];
  for (const spec of paramSpecs(meta)) {
    if (axisCount(axes[spec.name], spec) === null) {
      problems.push(`${paramLabel(spec.name)}需在 ${spec.min}~${spec.max}、最大值不小於最小值，且差距為步進的整數倍`);
    }
  }
  for (const [lower, upper] of ORDERED[meta.id] ?? []) {
    if (axes[lower] && axes[upper] && axes[lower].high >= axes[upper].low) {
      problems.push(`${paramLabel(lower)}的最大值需小於${paramLabel(upper)}的最小值`);
    }
  }
  return problems;
}

/** Warm-up covering the grid's highest look-back value. */
export function gridWarmup(meta: ResearchStrategyMeta, axes: Record<string, Axis>): number {
  return axes[meta.warmup.covers]?.high ?? 0;
}

/** The lowest grid point: a valid base parameter set for the request's backtest block. */
export function gridBase(meta: ResearchStrategyMeta, axes: Record<string, Axis>): Record<string, number> {
  return Object.fromEntries(paramSpecs(meta).map((spec) => [spec.name, axes[spec.name]?.low ?? spec.min]));
}

/**
 * Donchian defaults per dataset. A fetched 15m dataset gets 1~4-day entry channels and
 * 6~18-hour exits (12 candidates); the 96-bar synthetic fixture gets channels it can fill.
 */
export function donchianAxes(dataset: ResearchDatasetMeta | null): Record<string, Axis> {
  return dataset?.source === SYNTHETIC_SOURCE || !dataset
    ? { entry_bars: { low: 4, high: 8, step: 2 }, exit_bars: { low: 2, high: 3, step: 1 } }
    : { entry_bars: { low: 96, high: 384, step: 96 }, exit_bars: { low: 24, high: 72, step: 24 } };
}

/** One Donchian parameter set per dataset for the backtest form. */
export function donchianParams(dataset: ResearchDatasetMeta | null): { params: Record<string, number>; warmup: number } {
  return dataset?.source === SYNTHETIC_SOURCE || !dataset
    ? { params: { entry_bars: 6, exit_bars: 3 }, warmup: 6 }
    : { params: { entry_bars: 192, exit_bars: 48 }, warmup: 192 };
}
