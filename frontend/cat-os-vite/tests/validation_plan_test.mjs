// Unit tests for the walk-forward request helpers (no network, no browser).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';

let server, plan, strategies;
before(async () => {
  // No HMR socket: node --test runs this file beside state_adapter_test.mjs, which owns the default port.
  server = await createServer({ server: { middlewareMode: true, ws: false }, appType: 'custom', optimizeDeps: { noDiscovery: true, entries: [] } });
  plan = await server.ssrLoadModule('/src/lib/validation-plan.ts');
  strategies = await server.ssrLoadModule('/src/lib/research-strategies.ts');
});
after(async () => { await server?.close(); });

// catalog().validation.example_request (catos/research_catalog.py DEFAULT_VALIDATION)
const EXAMPLE = {
  backtest: { strategy_id: 'sma-trend', dataset_id: 'synthetic-btc-15m-v1', parameters: { period: 2, quantity: '2' },
    initial_balance: '1000', fee_rate: '0.0005', slippage_bps: '2', warmup_bars: 4 },
  search_space: { period: { low: 2, high: 4, step: 1 } },
  plan: { train_bars: 24, test_bars: 16, windows: 3 },
  regime_rule: { lookback_bars: 4, trend_efficiency: '0.5', high_volatility_bps: '250' },
  max_candidates: 3, max_runs: 12,
};
const LIMITS = { example_request: EXAMPLE, max_candidates: 20, max_runs: 100, max_windows: 8,
  max_bar_evaluations: 250_000, max_lookback_bars: 512, max_curve_points: 1_000,
  score_name: 'return_pct', direction: 'maximize', notice: '' };
const SYNTHETIC = { id: 'synthetic-btc-15m-v1', source: 'synthetic_closed_bars', bars: 96 };
const FETCHED = { id: 'okx-btc-usdt-swap-15m-20260806-20261104', source: 'okx_public_history', bars: 8640 };
// catalog().strategies entries (parameters and warmup only)
const SMA = { id: 'sma-trend', parameters: { period: { min: 2, max: 32 }, quantity: { unit: 'contracts' } },
  warmup: { covers: 'period', below: 64 } };
const DONCHIAN = { id: 'donchian-breakout',
  parameters: { entry_bars: { min: 2, max: 960 }, exit_bars: { min: 1, max: 959 }, quantity: { unit: 'contracts' } },
  warmup: { covers: 'entry_bars', below: 961 } };
const period = (low, high, step) => ({ axes: { period: { low, high, step } } });

test('synthetic defaults rebuild the catalog example request exactly', () => {
  const form = plan.defaultValidationForm(SYNTHETIC, EXAMPLE, SMA);
  assert.deepEqual(plan.buildValidationRequest(form, SMA), EXAMPLE);
  assert.deepEqual(plan.validationProblems(form, SYNTHETIC, LIMITS, SMA), []);
});

test('fetched defaults use every bar and stay inside the backend budgets', () => {
  const form = plan.defaultValidationForm(FETCHED, EXAMPLE, SMA);
  assert.deepEqual([form.axes.period, form.windows], [{ low: 8, high: 32, step: 8 }, 6]);
  assert.deepEqual([form.trainBars, form.testBars], [2152, 1076]);
  assert.equal(plan.barsUsed(form, SMA), FETCHED.bars);
  // windows x (candidates x (warmup + train) + warmup + test), the backend preflight formula
  assert.equal(plan.barEvaluations(form, SMA), 6 * (4 * (32 + 2152) + 32 + 1076));
  const request = plan.buildValidationRequest(form, SMA);
  assert.equal(request.backtest.dataset_id, FETCHED.id);
  assert.equal(request.backtest.warmup_bars, 32);
  assert.equal(request.max_candidates, 4);
  assert.equal(request.max_runs, 30);
  assert.deepEqual(request.regime_rule, EXAMPLE.regime_rule);
  assert.deepEqual(plan.validationProblems(form, FETCHED, LIMITS, SMA), []);
});

test('candidate grids must be aligned and hold at least two periods', () => {
  assert.equal(plan.candidateCount(period(8, 32, 8), SMA), 4);
  assert.equal(plan.candidateCount(period(2, 5, 2), SMA), null);
  assert.equal(plan.candidateCount(period(4, 4, 1), SMA), null);
  assert.equal(plan.candidateCount(period(1, 4, 1), SMA), null);
  assert.equal(plan.candidateCount(period(2, 33, 1), SMA), null);
});

test('problems mirror the backend preflight before submission', () => {
  const base = plan.defaultValidationForm(FETCHED, EXAMPLE, SMA);
  const heavy = { ...base, ...period(2, 32, 3), trainBars: 8000, testBars: 70, windows: 8 };
  assert.ok(plan.barEvaluations(heavy, SMA) > LIMITS.max_bar_evaluations);
  assert.ok(plan.validationProblems(heavy, FETCHED, LIMITS, SMA).some((p) => p.includes('計算量')));
  const long = { ...base, testBars: 2000 };
  assert.ok(plan.validationProblems(long, FETCHED, LIMITS, SMA).some((p) => p.includes('根 K 線')));
  const runs = { ...base, ...period(2, 21, 1), windows: 5 };
  assert.ok(plan.validationProblems(runs, FETCHED, LIMITS, SMA).some((p) => p.includes('次回測')));
  const grid = { ...base, ...period(8, 32, 5) };
  assert.ok(plan.validationProblems(grid, FETCHED, LIMITS, SMA).some((p) => p.includes('SMA 週期需在 2~32')));
});

test('regime rule fields are checked as exact Decimal text and a bounded lookback', () => {
  const base = plan.defaultValidationForm(FETCHED, EXAMPLE, SMA);
  const problems = (over) => plan.validationProblems({ ...base, ...over }, FETCHED, LIMITS, SMA);
  assert.deepEqual(problems({ lookbackBars: 512, trendEfficiency: '1', highVolatilityBps: '0.000001' }), []);
  assert.ok(problems({ lookbackBars: 513 }).some((p) => p.includes('回看根數需在 1~512')));
  assert.ok(problems({ lookbackBars: 0 }).some((p) => p.includes('回看根數')));
  for (const bad of ['0', '1.0000000000000000000001', 'abc', '0.5.1', '-0.5', '']) {
    assert.ok(problems({ trendEfficiency: bad }).some((p) => p.includes('趨勢效率門檻')), bad);
  }
  for (const bad of ['0', '0.0', '1e3', 'NaN', '25bps', '']) {
    assert.ok(problems({ highVolatilityBps: bad }).some((p) => p.includes('高波動門檻')), bad);
  }
  assert.ok(problems({ highVolatilityBps: '1'.repeat(65) }).some((p) => p.includes('高波動門檻')));
});

test('Donchian fetched defaults search 12 channel pairs inside the budgets', () => {
  const form = plan.defaultValidationForm(FETCHED, EXAMPLE, DONCHIAN);
  assert.deepEqual(form.axes, { entry_bars: { low: 96, high: 384, step: 96 }, exit_bars: { low: 24, high: 72, step: 24 } });
  assert.equal(plan.candidateCount(form, DONCHIAN), 12);
  assert.equal(plan.warmupBars(form, DONCHIAN), 384);
  assert.deepEqual([form.trainBars, form.testBars, form.windows], [2064, 1032, 6]);
  assert.ok(plan.barsUsed(form, DONCHIAN) <= FETCHED.bars);
  assert.equal(plan.barEvaluations(form, DONCHIAN), 6 * (12 * (384 + 2064) + 384 + 1032));
  assert.deepEqual(plan.validationProblems(form, FETCHED, LIMITS, DONCHIAN), []);
  const request = plan.buildValidationRequest(form, DONCHIAN);
  assert.deepEqual(request.backtest.parameters, { entry_bars: 96, exit_bars: 24, quantity: '2' });
  assert.equal(request.backtest.strategy_id, 'donchian-breakout');
  assert.equal(request.backtest.warmup_bars, 384);
  assert.deepEqual(Object.keys(request.search_space), ['entry_bars', 'exit_bars']);
  assert.deepEqual([request.max_candidates, request.max_runs], [12, 78]);
});

test('Donchian grids keep every exit channel below every entry channel', () => {
  const base = plan.defaultValidationForm(FETCHED, EXAMPLE, DONCHIAN);
  const overlap = { ...base, axes: { ...base.axes, exit_bars: { low: 24, high: 96, step: 24 } } };
  assert.equal(plan.candidateCount(overlap, DONCHIAN), null);
  assert.ok(plan.validationProblems(overlap, FETCHED, LIMITS, DONCHIAN).some((p) => p.includes('出場通道的最大值需小於進場通道的最小值')));
  const single = { ...base, axes: { entry_bars: { low: 96, high: 96, step: 1 }, exit_bars: { low: 24, high: 24, step: 1 } } };
  assert.ok(plan.validationProblems(single, FETCHED, LIMITS, DONCHIAN).some((p) => p.includes('至少需要 2 組')));
  const wide = { ...base, axes: { entry_bars: { low: 96, high: 960, step: 96 }, exit_bars: { low: 24, high: 72, step: 24 } } };
  assert.ok(plan.validationProblems(wide, FETCHED, LIMITS, DONCHIAN).some((p) => p.includes('候選數 30 超過上限 20')));
  const synthetic = plan.defaultValidationForm(SYNTHETIC, EXAMPLE, DONCHIAN);
  assert.deepEqual(plan.validationProblems(synthetic, SYNTHETIC, LIMITS, DONCHIAN), []);
});

test('backtest parameter checks follow the catalog bounds and the Donchian ordering', () => {
  assert.deepEqual(strategies.paramProblems(DONCHIAN, { entry_bars: 192, exit_bars: 48 }, 192), []);
  assert.ok(strategies.paramProblems(DONCHIAN, { entry_bars: 48, exit_bars: 48 }, 48).some((p) => p.includes('出場通道需小於進場通道')));
  assert.ok(strategies.paramProblems(DONCHIAN, { entry_bars: 192, exit_bars: 48 }, 191).some((p) => p.includes('預熱根數')));
  assert.ok(strategies.paramProblems(DONCHIAN, { entry_bars: 961, exit_bars: 48 }, 961).some((p) => p.includes('2~960')));
  assert.deepEqual(strategies.paramProblems(SMA, { period: 2 }, 2), []);
  assert.ok(strategies.paramProblems(SMA, { period: 8 }, 64).some((p) => p.includes('小於 64')));
  assert.equal(strategies.formatParams({ entry_bars: 192, exit_bars: 48, quantity: '1' }), 'entry_bars=192, exit_bars=48');
  assert.equal(strategies.formatTrialParams([['period', 32]]), '32');
  assert.equal(strategies.formatTrialParams([['entry_bars', 96], ['exit_bars', 24]]), 'entry_bars=96, exit_bars=24');
  assert.equal(strategies.formatRanges({ entry_bars: { low: 96, high: 384, step: 96 } }), 'entry_bars 96~384/96');
  // A warm-up must leave evaluation bars; the backend rejects it with 422 before queueing.
  assert.deepEqual(strategies.warmupBarsProblems(95, SYNTHETIC), []);
  assert.ok(strategies.warmupBarsProblems(96, SYNTHETIC).some((p) => p.includes('需少於資料集的 96 根')));
  assert.deepEqual(strategies.warmupBarsProblems(960, FETCHED), []);
});
