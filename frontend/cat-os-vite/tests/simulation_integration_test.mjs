// Run from this frontend: node tests/simulation_integration_test.mjs [python] [chrome.exe]
// Starts an isolated backend fixture (real bounded synthetic runner) on 18870 and the real
// Vite proxy on 18890, drives the production simulation adapter + store against it through
// the proxy, then loads the dashboard, bots, risk, logs, strategies and review pages in headless
// Chrome and checks the DOM. Finally it submits the synthetic walk-forward example, a Donchian
// backtest and a Donchian walk-forward through the proxy and checks the backtest and validation pages.
// 8770/8771/8890 and outputs/local-sim-control are never touched.
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs/promises';
import { existsSync, readdirSync } from 'node:fs';
import os from 'node:os';
import net from 'node:net';
import { spawn, execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { setTimeout as delay } from 'node:timers/promises';
import { createServer, loadConfigFromFile } from 'vite';
import ts from 'typescript';

const frontend = fileURLToPath(new URL('..', import.meta.url));
const repo = path.resolve(frontend, '../..');
const python = process.argv[2] ?? path.join(repo, '.venv', 'Scripts', 'python.exe');
// Newer desktop Chrome can print an empty --dump-dom, so prefer Playwright's chrome-headless-shell.
function headlessShell() {
  const root = path.join(process.env.LOCALAPPDATA ?? '', 'ms-playwright');
  if (!existsSync(root)) return undefined;
  const dir = readdirSync(root).filter(d => d.startsWith('chromium_headless_shell-')).sort().pop();
  const exe = dir && path.join(root, dir, 'chrome-headless-shell-win64', 'chrome-headless-shell.exe');
  return exe && existsSync(exe) ? exe : undefined;
}
const chrome = process.argv[3] ?? process.env.CATOS_CHROME ?? headlessShell()
  ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe';
// Short default dir: Chrome cannot write a screenshot path over the 260-char Windows limit.
const screens = process.env.CATOS_SCREENS ?? path.join(os.tmpdir(), 'catos-screens');
const evidence = await fs.mkdtemp(path.join(os.tmpdir(), 'catos-sim-integration-'));
const origin = 'http://127.0.0.1:18890';
const passed = [];
let backend, vite;
async function check(name, body) { await body(); passed.push(name); console.log(`PASS ${name}`); }
async function waitFor(body, message, timeout = 15000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { if (await body()) return; await delay(100); }
  throw new Error(message);
}
async function portFree(port) {
  const probe = net.createServer();
  await new Promise((resolve, reject) => probe.once('error', reject).listen(port, '127.0.0.1', resolve));
  await new Promise(resolve => probe.close(resolve));
}
const DECIMAL = /^-?\d+(\.\d+)?$/;
try {
  await portFree(18870); await portFree(18890);
  backend = spawn(python, ['-B', '-m', 'tests.integration_http_fixture', evidence, '18870', 'real'],
    { cwd: repo, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  let backendLog = '';
  backend.stdout.on('data', x => { backendLog += x; });
  backend.stderr.on('data', x => { backendLog += x; });
  await waitFor(async () => {
    if (backend.exitCode !== null) throw new Error(`fixture exited: ${backendLog}`);
    return fetch('http://127.0.0.1:18870/api/workspace/simulation/version').then(r => r.ok).catch(() => false);
  }, 'fixture readiness timeout');

  const source = await fs.readFile(path.join(frontend, 'vite.local-integration.ts'), 'utf8');
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  const { localIntegration } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
  const loaded = await loadConfigFromFile({}, path.join(frontend, 'vite.config.ts'));
  vite = await createServer({ ...loaded.config, root: frontend, configFile: false,
    plugins: [...loaded.config.plugins.filter(p => p.name !== 'catos-local-integration'), localIntegration(18870)],
    server: { host: '127.0.0.1', port: 18890, strictPort: true } });
  await vite.listen();

  const { useCatStore: store } = await vite.ssrLoadModule('/src/state/catStore.ts');
  const { StateAdapter } = await vite.ssrLoadModule('/src/state/stateAdapter.ts');
  const { SimulationApiAdapter } = await vite.ssrLoadModule('/src/adapters/simulation-api-adapter.ts');
  const storageMap = new Map();
  const api = new SimulationApiAdapter({
    fetch: (url, init) => fetch(origin + url, init),
    storage: { getItem: k => storageMap.get(k) ?? null, setItem: (k, v) => storageMap.set(k, v), removeItem: k => storageMap.delete(k) },
  });
  const adapter = new StateAdapter(api);

  await check('adapter loads /state through the real Vite proxy', async () => {
    await adapter.init();
    adapter.stopPolling();
    const s = store.getState();
    assert.equal(s.connection.status, 'ok', JSON.stringify(s.connection));
    assert.equal(s.bots.length, 1);
    assert.equal(s.bots[0].bot_id, 'sim-control-sma');
    assert.equal(s.bots[0].state, 'stopped');
    assert.equal(s.summary, null);
    assert.equal(s.strategies[0].strategy_id, 'sma-trend');
    assert.equal(s.service.slot, 'idle');
  });

  await check('startBot runs a real synthetic case to completion with Decimal strings everywhere', async () => {
    await adapter.startBot('sim-control-sma');
    assert.equal(store.getState().commandHistory[0].status, 'success');
    await waitFor(async () => {
      await adapter.refreshNowFull();
      return store.getState().bots[0]?.state === 'completed';
    }, `run did not complete: ${JSON.stringify(store.getState().bots[0])}`, 90000);
    const s = store.getState();
    const bot = s.bots[0];
    assert.equal(bot.equity, '999.91375990');
    assert.equal(bot.fees, '0.00404010');
    assert.equal(bot.account_source, 'final_account');
    assert.equal(bot.bars, 8); assert.equal(bot.warmup_bars, 2); assert.equal(bot.fills, 4);
    assert.equal(s.summary.equity, '999.91375990');
    for (const v of [s.summary.realized_pnl, s.summary.unrealized_pnl, s.summary.fees, s.summary.period_pnl, s.summary.period_pnl_ratio,
                     s.risk.derived.notional, s.risk.derived.exposure_budget, s.risk.limits.leverage, s.risk.snapshot.mark]) {
      assert.equal(typeof v, 'string'); assert.match(v, DECIMAL);
    }
    assert.equal(s.risk.derived.status, 'normal');
    const signals = s.events.filter(e => e.kind === 'signal' && e.run_id === bot.current_run_id);
    assert.equal(signals.length, 8);
    for (const e of signals) { assert.match(e.payload.mark, DECIMAL); assert.equal(e.payload.risk_state.mode, 'RUN'); }
    assert.equal(StateAdapter.equityCurve(s.events, bot.current_run_id).length, 8);
    assert.ok(s.events.some(e => e.kind === 'run_state' && e.payload.state === 'completed'));
    assert.equal(s.eventsOmitted, 0);
    assert.equal(s.positions.length, /^-?0+(\.0*)?$/.test(bot.position) ? 0 : 1);
    assert.ok(s.versionMap.global > 1);
  });

  await check('polling with since_version returns unchanged and keeps projections', async () => {
    const before = store.getState();
    const result = await api.fetchState(before.versionMap.global);
    assert.equal(result.available, true);
    assert.equal(result.data.unchanged, true);
    assert.equal(result.data.version, before.versionMap.global);
  });

  await fs.mkdir(screens, { recursive: true });
  const FORBIDDEN = ['NaN', 'undefined', 'tabby', 'calico', 'mochi', 'shiro', 'BOT-BTC-15M', '61,480', '74,535', '125,480', '$69,888', '--'];
  async function page(route, name) {
    const shot = path.join(screens, `step4-${name}.png`);
    assert.ok(shot.length < 260, `screenshot path over 260 chars, set a shorter CATOS_SCREENS: ${shot}`);
    const run = (args) => promisify(execFile)(chrome, ['--headless=new', '--disable-gpu', '--no-first-run', '--hide-scrollbars',
      '--window-size=1440,900', '--force-device-scale-factor=1', '--virtual-time-budget=20000', ...args, `${origin}/#${route}`],
      { maxBuffer: 64 * 1024 * 1024, windowsHide: true });
    const { stdout } = await run(['--dump-dom']);
    await run([`--screenshot=${shot}`]);
    const text = stdout.replace(/<script[\s\S]*?<\/script>/g, '').replace(/<style[\s\S]*?<\/style>/g, '').replace(/<[^>]+>/g, ' ');
    await fs.writeFile(path.join(evidence, `dom-${name}.txt`), text);
    return { text, shot };
  }
  await check('dashboard DOM shows the real run and no NaN / mock values', async () => {
    const { text, shot } = await page('/', 'dashboard');
    for (const bad of FORBIDDEN) assert.ok(!text.includes(bad), `dashboard contains "${bad}"`);
    assert.ok(text.includes('999.91'), 'dashboard equity missing');
    assert.ok(text.includes('sim-control-sma'), 'dashboard bot id missing');
    // Unwired/N-A states are explicit text, never placeholders (positions may be empty at a flat terminal state).
    assert.ok(text.includes('未接線'), 'unwired close path not marked');
    console.log(`screenshot ${shot}`);
  });
  await check('bots page DOM shows the real run and no NaN / mock values', async () => {
    const { text, shot } = await page('/bots', 'bots');
    for (const bad of FORBIDDEN) assert.ok(!text.includes(bad), `bots page contains "${bad}"`);
    assert.ok(text.includes('999.91'), 'bots equity missing');
    assert.ok(text.includes('sim-control-sma') && text.includes('BTC-USDT-SWAP'), 'bots identity missing');
    assert.ok(text.includes('未接線'), 'kill-switch / restart not marked as unwired');
    console.log(`screenshot ${shot}`);
  });
  // v1.1: the remaining pages read the same projections; the old mock values must be gone.
  const final = store.getState();
  await check('risk page DOM shows the real risk projection and no mock values', async () => {
    const { text, shot } = await page('/risk', 'risk');
    for (const bad of [...FORBIDDEN, '12,500', '427.5', '展示資料', '197/197']) assert.ok(!text.includes(bad), `risk page contains "${bad}"`);
    assert.match(text, /正常 · (可|禁)增倉/, 'risk status chip missing');
    assert.ok(text.includes(`seq ${final.risk.seq}`), 'risk observation seq missing');
    assert.ok(text.includes('Soft 10.00%') && text.includes('Hard 20.00%'), 'loss limits missing');
    assert.ok(text.includes('未接線'), 're-arm not marked as unwired');
    console.log(`screenshot ${shot}`);
  });
  await check('logs page DOM shows the real event stream and no mock values', async () => {
    const { text, shot } = await page('/logs', 'logs');
    for (const bad of [...FORBIDDEN, 'catnet', 'whisker', 'venue=okx']) assert.ok(!text.includes(bad), `logs page contains "${bad}"`);
    assert.ok(text.includes('TRADE') && text.includes('BTC-USDT-SWAP'), 'fill lines missing');
    assert.ok(text.includes('最終帳戶'), 'final account event missing');
    assert.ok(text.includes(`${final.events.length} / ${final.events.length} lines`), 'line count does not match the store');
    console.log(`screenshot ${shot}`);
  });
  await check('strategies page DOM shows the registered strategy and no mock values', async () => {
    const { text, shot } = await page('/strategies', 'strategies');
    for (const bad of [...FORBIDDEN, 'catnet', '組合夏普']) assert.ok(!text.includes(bad), `strategies page contains "${bad}"`);
    assert.ok(text.includes('sma-trend') && text.includes('sma-parameters-v1') && text.includes('approved'), 'registry entry missing');
    assert.ok(text.includes('999.91'), 'bound bot equity missing');
    console.log(`screenshot ${shot}`);
  });
  await check('review page is marked not enabled and shows no demo numbers', async () => {
    const { text, shot } = await page('/review', 'review');
    for (const bad of [...FORBIDDEN, '12,483,920', '34.80', '實盤淨值']) assert.ok(!text.includes(bad), `review page contains "${bad}"`);
    assert.ok(text.includes('v1 未啟用'), 'review page not marked as not enabled');
    console.log(`screenshot ${shot}`);
  });
  await check('validation page shows a real walk-forward run submitted through the proxy', async () => {
    const getJson = async (route) => (await fetch(origin + route)).json();
    const version = await getJson('/api/research/version');
    const { validation } = await getJson('/api/research/catalog');
    const submitted = await fetch(`${origin}/api/research/validations`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CatOS-Build': version.build_id },
      body: JSON.stringify(validation.example_request) });
    const body = await submitted.text();
    assert.equal(submitted.status, 202, body);
    const { run_id: runId } = JSON.parse(body);
    await waitFor(async () => (await getJson(`/api/research/runs/${runId}`)).status === 'complete',
      'validation run did not complete', 60000);
    const result = await getJson(`/api/research/runs/${runId}/result`);
    assert.equal(result.schema, 'catos.research.validation-result.v2');
    assert.ok(!('labels' in result.result), 'v2 result still carries per-bar labels');
    const { formatDecimal } = await vite.ssrLoadModule('/src/lib/format.ts');
    const { text, shot } = await page('/validation', 'validation');
    for (const bad of FORBIDDEN) assert.ok(!text.includes(bad), `validation page contains "${bad}"`);
    assert.ok(text.includes(`#${runId.slice(0, 8)}`), 'validation run missing from the list');
    const windows = result.result.validation.windows;
    assert.ok(text.includes(`${windows.length} / ${windows.length} COMPLETE`), 'window status HUD missing');
    assert.ok(text.includes('maximin_axis_neighbors_v1'), 'selection rule missing');
    for (const window of windows) {
      const pnl = formatDecimal(window.out_of_sample.performance.net_pnl, { digits: 2, sign: true });
      assert.ok(text.includes(pnl), `window ${window.number} net PnL ${pnl} missing`);
    }
    assert.ok(text.includes('合計') && text.includes('與樣本外帳務核對一致'), 'regime attribution missing');
    console.log(`screenshot ${shot}`);
  });
  // Submit a research run through the proxy exactly like the pages do and wait for its archive.
  async function researchRun(kind, request) {
    const getJson = async (route) => (await fetch(origin + route)).json();
    const version = await getJson('/api/research/version');
    const submitted = await fetch(`${origin}/api/research/${kind}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CatOS-Build': version.build_id },
      body: JSON.stringify(request) });
    const body = await submitted.text();
    assert.equal(submitted.status, 202, body);
    const { run_id: runId } = JSON.parse(body);
    await waitFor(async () => (await getJson(`/api/research/runs/${runId}`)).status === 'complete',
      `${kind} run did not complete`, 60000);
    return { runId, result: await getJson(`/api/research/runs/${runId}/result`) };
  }
  const DONCHIAN = { strategy_id: 'donchian-breakout', parameters: { entry_bars: 6, exit_bars: 3, quantity: '1' },
    warmup_bars: 6 };
  await check('backtest page shows a Donchian run submitted through the proxy', async () => {
    const catalog = await (await fetch(`${origin}/api/research/catalog`)).json();
    // Later research strategies are appended; this check needs only the first two.
    assert.deepEqual(catalog.strategies.map((s) => s.id).slice(0, 2), ['sma-trend', 'donchian-breakout']);
    const { runId, result } = await researchRun('backtests', { ...catalog.defaults, ...DONCHIAN });
    assert.equal(result.provenance.strategy.id, 'donchian-breakout');
    const { formatDecimal } = await vite.ssrLoadModule('/src/lib/format.ts');
    const { text, shot } = await page('/backtest', 'backtest-donchian');
    // The backtest page keeps "--" placeholders for absent fields, so only NaN/undefined are checked here.
    for (const bad of ['NaN', 'undefined']) assert.ok(!text.includes(bad), `backtest page contains "${bad}"`);
    assert.ok(text.includes('Donchian 回測 · entry_bars=6, exit_bars=3'), `run ${runId} label missing`);
    assert.ok(text.includes('Donchian 通道突破（Long / Short）'), 'strategy name missing');
    const returnPct = formatDecimal(result.result.performance.return_pct, { digits: 2, sign: true, suffix: '%' });
    assert.ok(text.includes(returnPct), `return ${returnPct} missing`);
    console.log(`screenshot ${shot}`);
  });
  await check('validation page shows a Donchian walk-forward with its selected channels', async () => {
    const { validation } = await (await fetch(`${origin}/api/research/catalog`)).json();
    const { runId, result } = await researchRun('validations', {
      ...validation.example_request, backtest: { ...validation.example_request.backtest, ...DONCHIAN },
      search_space: { entry_bars: { low: 4, high: 6, step: 2 }, exit_bars: { low: 2, high: 3, step: 1 } },
      max_candidates: 4, max_runs: 15 });
    const { formatDecimal } = await vite.ssrLoadModule('/src/lib/format.ts');
    const { text, shot } = await page('/validation', 'validation-donchian');
    for (const bad of FORBIDDEN) assert.ok(!text.includes(bad), `validation page contains "${bad}"`);
    assert.ok(text.includes(`#${runId.slice(0, 8)}`), 'Donchian validation run missing from the list');
    assert.ok(text.includes('Donchian entry_bars 4~6/2 · exit_bars 2~3/1'), 'Donchian run summary missing');
    for (const window of result.result.validation.windows) {
      const chosen = window.training.trials[window.training.selected_trial_number].params;
      const label = chosen.map(([name, value]) => `${name}=${value}`).join(', ');
      assert.ok(text.includes(label), `window ${window.number} selected ${label} missing`);
      const pnl = formatDecimal(window.out_of_sample.performance.net_pnl, { digits: 2, sign: true });
      assert.ok(text.includes(pnl), `window ${window.number} net PnL ${pnl} missing`);
    }
    console.log(`screenshot ${shot}`);
  });
  await fs.writeFile(path.join(evidence, 'result.json'), JSON.stringify({ passed, backendLog, ports: [18870, 18890] }, null, 2));
  console.log(`Evidence: ${evidence}`);
} catch (error) {
  await fs.writeFile(path.join(evidence, 'failure.json'), JSON.stringify({ passed, error: error.stack }, null, 2));
  throw error;
} finally {
  await vite?.close();
  if (backend && backend.exitCode === null) { backend.kill(); await new Promise(resolve => backend.once('exit', resolve)); }
}
