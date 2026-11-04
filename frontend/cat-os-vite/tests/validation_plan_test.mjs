// Unit tests for the walk-forward request helpers (no network, no browser).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';

let server, plan;
before(async () => {
  // No HMR socket: node --test runs this file beside state_adapter_test.mjs, which owns the default port.
  server = await createServer({ server: { middlewareMode: true, ws: false }, appType: 'custom', optimizeDeps: { noDiscovery: true, entries: [] } });
  plan = await server.ssrLoadModule('/src/lib/validation-plan.ts');
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
  max_bar_evaluations: 250_000, max_curve_points: 1_000, score_name: 'return_pct', direction: 'maximize', notice: '' };
const SYNTHETIC = { id: 'synthetic-btc-15m-v1', source: 'synthetic_closed_bars', bars: 96 };
const FETCHED = { id: 'okx-btc-usdt-swap-15m-20260806-20261104', source: 'okx_public_history', bars: 8640 };

test('synthetic defaults rebuild the catalog example request exactly', () => {
  const form = plan.defaultValidationForm(SYNTHETIC, EXAMPLE);
  assert.deepEqual(plan.buildValidationRequest(form), EXAMPLE);
  assert.deepEqual(plan.validationProblems(form, SYNTHETIC, LIMITS), []);
});

test('fetched defaults use every bar and stay inside the backend budgets', () => {
  const form = plan.defaultValidationForm(FETCHED, EXAMPLE);
  assert.deepEqual([form.periodLow, form.periodHigh, form.periodStep, form.windows], [8, 32, 8, 6]);
  assert.deepEqual([form.trainBars, form.testBars], [2152, 1076]);
  assert.equal(plan.barsUsed(form), FETCHED.bars);
  // windows x (candidates x (warmup + train) + warmup + test), the backend preflight formula
  assert.equal(plan.barEvaluations(form), 6 * (4 * (32 + 2152) + 32 + 1076));
  const request = plan.buildValidationRequest(form);
  assert.equal(request.backtest.dataset_id, FETCHED.id);
  assert.equal(request.backtest.warmup_bars, 32);
  assert.equal(request.max_candidates, 4);
  assert.equal(request.max_runs, 30);
  assert.deepEqual(request.regime_rule, EXAMPLE.regime_rule);
  assert.deepEqual(plan.validationProblems(form, FETCHED, LIMITS), []);
});

test('candidate grids must be aligned and hold at least two periods', () => {
  assert.equal(plan.candidateCount({ periodLow: 8, periodHigh: 32, periodStep: 8 }), 4);
  assert.equal(plan.candidateCount({ periodLow: 2, periodHigh: 5, periodStep: 2 }), null);
  assert.equal(plan.candidateCount({ periodLow: 4, periodHigh: 4, periodStep: 1 }), null);
  assert.equal(plan.candidateCount({ periodLow: 1, periodHigh: 4, periodStep: 1 }), null);
  assert.equal(plan.candidateCount({ periodLow: 2, periodHigh: 33, periodStep: 1 }), null);
});

test('problems mirror the backend preflight before submission', () => {
  const base = plan.defaultValidationForm(FETCHED, EXAMPLE);
  const heavy = { ...base, periodLow: 2, periodStep: 3, trainBars: 8000, testBars: 70, windows: 8 };
  assert.ok(plan.barEvaluations(heavy) > LIMITS.max_bar_evaluations);
  assert.ok(plan.validationProblems(heavy, FETCHED, LIMITS).some((p) => p.includes('計算量')));
  const long = { ...base, testBars: 2000 };
  assert.ok(plan.validationProblems(long, FETCHED, LIMITS).some((p) => p.includes('根 K 線')));
  const runs = { ...base, periodLow: 2, periodHigh: 21, periodStep: 1, windows: 5 };
  assert.ok(plan.validationProblems(runs, FETCHED, LIMITS).some((p) => p.includes('次回測')));
  const grid = { ...base, periodStep: 5 };
  assert.ok(plan.validationProblems(grid, FETCHED, LIMITS).some((p) => p.includes('候選週期')));
});
