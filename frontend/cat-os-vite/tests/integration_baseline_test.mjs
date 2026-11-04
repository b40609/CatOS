// Run from this frontend: node tests/integration_baseline_test.mjs <playwright module directory> [python]
// All HTTP writes target a new fixture root on 18870; 8770/8771 are never contacted.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs/promises';
import net from 'node:net';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { createServer, loadConfigFromFile } from 'vite';
import ts from 'typescript';

const frontend = fileURLToPath(new URL('..', import.meta.url));
const repo = path.resolve(frontend, '../..');
const evidence = await fs.mkdtemp(path.join(repo, 'outputs/integration-baseline-20261024/fixture-'));
const { chromium } = createRequire(path.join(path.resolve(process.argv[2]), 'package.json'))('playwright');
const origin = 'http://127.0.0.1:18890';
const passed = [];
let backend, vite, browser;
async function check(name, body) { await body(); passed.push(name); console.log(`PASS ${name}`); }
async function waitFor(body, message, timeout = 12000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { if (await body()) return; await delay(80); }
  throw new Error(message);
}
async function portFree(port) {
  const probe = net.createServer();
  await new Promise((resolve, reject) => probe.once('error', reject).listen(port, '127.0.0.1', resolve));
  await new Promise(resolve => probe.close(resolve));
}
try {
  await portFree(18870); await portFree(18890);
  backend = spawn(process.argv[3] ?? 'python', ['-B', '-m', 'tests.integration_http_fixture', evidence, '18870'], { cwd: repo, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  let backendLog = '';
  backend.stdout.on('data', x => { backendLog += x; });
  backend.stderr.on('data', x => { backendLog += x; });
  await waitFor(async () => {
    if (backend.exitCode !== null) throw new Error(`fixture exited: ${backendLog}`);
    return fetch('http://127.0.0.1:18870/api/research/version').then(r => r.ok).catch(() => false);
  }, 'fixture readiness timeout');
  const source = await fs.readFile(path.join(frontend, 'vite.local-integration.ts'), 'utf8');
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
  const { localIntegration } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
  const loaded = await loadConfigFromFile({}, path.join(frontend, 'vite.config.ts'));
  vite = await createServer({ ...loaded.config, root: frontend, configFile: false,
    plugins: [...loaded.config.plugins.filter(p => p.name !== 'catos-local-integration'), localIntegration(18870)],
    server: { host: '127.0.0.1', port: 18890, strictPort: true } });
  await vite.listen();
  const request = (url, options) => fetch(origin + url, options);
  const prefix = '/api/workspace/simulation';
  const version = await (await request(prefix + '/version')).json();
  const headers = { 'Content-Type': 'application/json', Origin: origin, 'X-CatOS-Build': version.build_id, 'X-CatOS-Instance': version.instance_id };
  const body = JSON.stringify({ request_id: 'a'.repeat(32), template_id: 'sma-synthetic-smoke-v1' });
  await check('proxy identity, research and workspace GET', async () => {
    assert.equal((await (await request('/__catos/frontend')).json()).root.toLowerCase(), frontend.replace(/[\\/]$/, '').toLowerCase());
    for (const url of ['/api/research/catalog', '/api/workspace/version']) assert.equal((await request(url)).status, 200);
  });
  await check('foreign Origin and Host are rejected before rewrite', async () => {
    assert.equal((await request(prefix + '/start', { method: 'POST', headers: { ...headers, Origin: 'https://external.invalid' }, body })).status, 403);
    const status = await new Promise((resolve, reject) => {
      const req = http.get(origin + prefix + '/version', { headers: { Host: 'external.invalid' } }, res => { res.resume(); resolve(res.statusCode); });
      req.on('error', reject);
    });
    assert.equal(status, 403);
  });
  await check('backend build/instance guards survive Vite proxy', async () => {
    for (const key of ['X-CatOS-Build', 'X-CatOS-Instance']) {
      assert.equal((await request(prefix + '/start', { method: 'POST', headers: { ...headers, [key]: 'old' }, body })).status, 409);
    }
  });
  await check('same-origin POST and idempotent replay through real proxy', async () => {
    const first = await request(prefix + '/start', { method: 'POST', headers, body });
    assert.equal(first.status, 202, await first.clone().text());
    const run = await first.json();
    const replayHeaders = { ...headers }; delete replayHeaders.Origin;
    const replay = await request(prefix + '/start', { method: 'POST', headers: replayHeaders, body });
    assert.equal(replay.status, 202);
    assert.equal((await replay.json()).run_id, run.run_id);
    const stop = await request(prefix + '/runs/' + run.run_id + '/stop', { method: 'POST', headers, body: JSON.stringify({ request_id: 'b'.repeat(32) }) });
    assert.equal(stop.status, 202);
  });

  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  const A = 'a'.repeat(32), B = 'b'.repeat(32), C = 'c'.repeat(32), D = 'd'.repeat(32);
  let active = C, cStatus = 'running', resultAWait = null, aRequested = false, versionReads = 0, posts = 0;
  const run = (id, status = 'complete', kind = 'optimization') => ({ run_id: id, kind, status, error: null, request: {}, created_at: '2026-10-24T00:00:00Z', started_at: null, finished_at: null, provenance: {}, build_id: 'fixture' });
  const result = id => ({ run_id: id, kind: 'optimization', request: {}, provenance: {}, trials: [], best_trial_number: null,
    objective: { name: `objective-${id[0]}`, direction: 'maximize' }, seed: 42, optuna_version: 'fixture', data_notice: 'synthetic fixture' });
  await page.route('**/api/research/**', async route => {
    const url = new URL(route.request().url()).pathname;
    let json;
    if (route.request().method() === 'POST') { posts++; json = run(C, 'queued'); active = C; cStatus = 'queued'; }
    else if (url.endsWith('/version')) { versionReads++; json = { build_id: 'fixture', restart_required: false, active_run_id: active, mode: 'local_research_synthetic' }; }
    else if (url.endsWith('/catalog')) json = { optimization: { max_trials: 20 }, defaults: {}, strategies: [], datasets: [] };
    else if (url.endsWith('/runs')) json = { items: [run(C, cStatus), run(A), run(B), ...(active === D ? [run(D, 'running', 'backtest')] : [])] };
    else if (url.endsWith('/result')) {
      const id = url.split('/').at(-2);
      if (id === A && resultAWait) { aRequested = true; await resultAWait; }
      json = result(id);
    } else throw new Error(`unexpected API: ${url}`);
    await route.fulfill({ json }).catch(error => { if (!/closed|cancel|abort/i.test(error.message)) throw error; });
  });
  await page.goto(origin + '/#/optimization');
  await page.getByText('#cccccccc', { exact: true }).waitFor();
  await check('reloaded active task polls and retains busy until backend releases slot', async () => {
    await waitFor(() => page.getByRole('button', { name: '後端計算中...' }).isDisabled(), 'active slot was not busy');
    await page.getByText('#bbbbbbbb', { exact: true }).click();
    await page.getByText('objective-b', { exact: true }).waitFor();
    const before = versionReads; cStatus = 'complete';
    await waitFor(() => versionReads >= before + 2, 'polling did not resume');
    assert.equal(await page.getByRole('button', { name: '後端計算中...' }).isDisabled(), true);
    active = null;
    await waitFor(() => page.getByRole('button', { name: '發起 SMA 優化任務' }).isEnabled(), 'released slot stayed busy');
    assert.equal(await page.getByText('objective-b', { exact: true }).isVisible(), true);
  });
  await check('late result A cannot replace the user-selected B', async () => {
    let release; resultAWait = new Promise(resolve => { release = resolve; }); aRequested = false;
    await page.getByText('#aaaaaaaa', { exact: true }).click();
    await waitFor(() => aRequested, 'result A request missing');
    await page.getByText('#bbbbbbbb', { exact: true }).click();
    await page.getByText('objective-b', { exact: true }).waitFor();
    release(); resultAWait = null;
    await delay(200);
    assert.equal(await page.getByText('objective-a', { exact: true }).count(), 0);
    assert.equal(await page.getByText('objective-b', { exact: true }).isVisible(), true);
  });
  await check('another research kind owning the slot is followed until release', async () => {
    active = D; await page.reload();
    await waitFor(() => page.getByRole('button', { name: '後端計算中...' }).isDisabled(), 'backtest ownership ignored');
    active = null;
    await waitFor(() => page.getByRole('button', { name: '發起 SMA 優化任務' }).isEnabled(), 'foreign slot completion was not followed');
  });
  await check('submitting optimization creates exactly one POST and busy state', async () => {
    await page.getByRole('button', { name: '發起 SMA 優化任務' }).click();
    const dialog = page.getByRole('dialog');
    const buttons = await dialog.getByRole('button').allTextContents();
    const submitButton = dialog.getByRole('button', { name: '確認發起優化', exact: true });
    assert.equal(await submitButton.count(), 1, JSON.stringify(buttons));
    await submitButton.click();
    await waitFor(() => posts === 1, 'POST not submitted');
    await waitFor(() => page.getByRole('button', { name: '後端計算中...' }).isDisabled(), 'submitted slot not busy');
    assert.equal(posts, 1);
  });
  await check('dashboard labels mock authority and renders unconfirmed P6 state', async () => {
    await page.goto(origin + '/#/');
    await page.getByText('P6 展示', { exact: false }).waitFor();
    assert.ok(await page.getByText('更新待確認', { exact: true }).count() > 0);
    assert.equal(await page.getByText('P6 交易所端 100% 錨定', { exact: true }).count(), 0);
    assert.ok(await page.getByLabel('展示環境模式切換').count() > 0);
  });
  await check('real mode buttons replace Local v10 projections with locked Demo/Live and reload Local', async () => {
    await page.evaluate(async () => {
      const { useCatStore } = await import('/src/state/catStore.ts');
      const { stateAdapter } = await import('/src/state/stateAdapter.ts');
      const state = useCatStore.getState();
      stateAdapter.handleEvent({ domain: 'bots', version: 10, payload: state.bots });
      stateAdapter.handleEvent({ domain: 'kpis', version: 10, payload: { ...state.kpis, total_equity: '12345' } });
    });
    const modes = page.getByRole('group', { name: '展示環境模式切換', exact: true }).first();
    for (const mode of ['demo', 'live']) {
      await modes.getByRole('button', { name: mode === 'demo' ? 'Demo' : 'Live', exact: true }).click();
      await waitFor(() => page.evaluate(async (expectedMode) => {
        const { useCatStore } = await import('/src/state/catStore.ts');
        const state = useCatStore.getState();
        return state.mode === expectedMode && state.kpis?.total_equity === '--' && state.bots.length === 0 &&
          state.versionMap.bots === 1 && state.pendingCommands.length === 0 && state.commandHistory.length === 0;
      }, mode), `${mode} retained previous Local projections`);
    }
    await modes.getByRole('button', { name: '本機', exact: true }).click();
    await waitFor(() => page.evaluate(async () => {
      const { useCatStore } = await import('/src/state/catStore.ts');
      const state = useCatStore.getState();
      return state.mode === 'local' && state.bots.length > 0 && /^\d+\.\d+$/.test(state.kpis?.total_equity ?? '') &&
        state.versionMap.bots === 1;
    }), 'Local projections were not reloaded by the real mode button');
  });
  assert.deepEqual(errors, []);
  await fs.writeFile(path.join(evidence, 'result.json'), JSON.stringify({ passed, errors, backendLog, ports: [18870, 18890] }, null, 2));
  console.log(`Evidence: ${evidence}`);
} catch (error) {
  await fs.writeFile(path.join(evidence, 'failure.json'), JSON.stringify({ passed, error: error.stack }, null, 2));
  throw error;
} finally {
  await browser?.close(); await vite?.close();
  if (backend && backend.exitCode === null) { backend.kill(); await new Promise(resolve => backend.once('exit', resolve)); }
}
