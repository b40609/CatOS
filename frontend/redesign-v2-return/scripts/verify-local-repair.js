import http from 'node:http';
import net from 'node:net';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import puppeteer from 'puppeteer-core';
import assert from 'node:assert/strict';

// Fresh, frontend-only fixture. No Vite child server or forced process cleanup.
const root = process.cwd();
const build = path.resolve(root, process.argv[2] || 'dist-codex-repair');
assert(build.startsWith(root + path.sep) && fs.existsSync(path.join(build, 'index.html')));
const instance = crypto.randomUUID();
const evidence = path.join(root, 'evidence', `codex-repair-${instance}`);
fs.mkdirSync(evidence, { recursive: true });
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]);
const files = [...walk(path.join(root, 'src')), ...walk(build), path.join(root, 'scripts/verify-local-repair.js'), ...['package.json', 'package-lock.json', 'vite.config.ts', 'index.html'].map(f => path.join(root, f))];
const baseline = Object.fromEntries(files.map(f => [path.relative(root, f).replaceAll('\\', '/'), hash(f)]));
const write = (name, data) => fs.writeFileSync(path.join(evidence, name), JSON.stringify(data, null, 2));
write('hashes.json', baseline);
const log = [], results = [], errors = [];
const lifecycle = { instance, owner_pid: process.pid, build_index_sha256: hash(path.join(build, 'index.html')), started_at: new Date().toISOString(), frontend_only: true };
const note = action => log.push({ at: new Date().toISOString(), action });
let browser, server, port;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function test(name, fn) {
  note(name);
  try { await fn(); results.push({ name, passed: true }); }
  catch (e) { results.push({ name, passed: false, error: String(e.stack) }); throw e; }
}
async function clickText(page, selector, text) {
  const handles = await page.$$(selector);
  for (const h of handles) {
    if ((await h.evaluate(e => e.textContent)).includes(text)) { await h.click(); note(`click ${selector}: ${text}`); return; }
  }
  throw new Error(`Button not found: ${selector} / ${text}`);
}
async function mode(page, value) {
  if (await page.$('.mode-btn')) await clickText(page, '.mode-btn', { local: '本機', demo: 'Demo', live: 'Live' }[value]);
  else { await page.click('.mode-badge-btn'); await clickText(page, '.dropdown-popover-item', { local: '本機', demo: 'Demo', live: 'Live' }[value]); }
  await page.waitForFunction(v => window.__CATOS_ADAPTER__.currentMode === v, {}, value);
  await pause(120);
}
async function route(page, value) { await page.evaluate(v => { location.hash = v; }, value); note(`route ${value}`); await pause(180); }
try {
  // Reserve a new loopback port, release, then bind fail-closed if another owner wins.
  const probe = net.createServer();
  await new Promise((resolve, reject) => { probe.once('error', reject); probe.listen(0, '127.0.0.1', resolve); });
  port = probe.address().port;
  await new Promise(resolve => probe.close(resolve));
  lifecycle.port = port; lifecycle.preflight = 'free: successful exclusive loopback bind';
  server = http.createServer((req, res) => {
    let file;
    try { file = path.resolve(build, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname)); } catch { res.writeHead(400).end(); return; }
    if (file === build) file = path.join(build, 'index.html');
    if (!file.startsWith(build + path.sep)) { res.writeHead(403).end(); return; }
    try {
      res.setHeader('Content-Type', { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' }[path.extname(file)] || 'application/octet-stream');
      res.end(fs.readFileSync(file));
    } catch { res.writeHead(404).end(); }
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', resolve); });
  lifecycle.os_listener = execFileSync('powershell.exe', ['-NoProfile', '-Command', `Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction Stop | Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json -Compress`], { encoding: 'utf8' }).trim();
  assert.equal(JSON.parse(lifecycle.os_listener).OwningProcess, process.pid);
  browser = await puppeteer.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000 });
  page.on('pageerror', e => errors.push(String(e)));
  await page.setRequestInterception(true);
  page.on('request', req => req.url().startsWith(`http://127.0.0.1:${port}/`) || /^(data:|blob:)/.test(req.url()) ? req.continue() : req.abort());
  await page.goto(`http://127.0.0.1:${port}/?enable_test_adapter=1#/`, { waitUntil: 'networkidle0' });
  await page.waitForFunction(() => !!window.__CATOS_ADAPTER__);
  await test('UI: all three routes Local → Demo → Live → Local, no control mutations', async () => {
    const before = await page.evaluate(() => JSON.stringify(window.__CATOS_ADAPTER__.runs));
    for (const r of ['/', '/bots', '/risk']) {
      await route(page, r);
      for (const m of ['demo', 'live']) {
        await mode(page, m);
        const data = await page.evaluate(async () => {
          const a = window.__CATOS_ADAPTER__;
          return { runs: await a.fetchRuns(), bots: await a.fetchBotQueue(), audit: await a.fetchAuditEvents(), research: await a.fetchResearchTasks(), yaozi: await a.fetchYaoziAlerts(), risk: await a.fetchRiskState(), text: document.body.innerText };
        });
        for (const field of ['runs', 'bots', 'audit', 'research', 'yaozi']) assert.equal(data[field].length, 0);
        for (const field of ['daily_pnl_usdt', 'exposure_nominal_usdt', 'margin_used_usdt']) assert.equal(data.risk[field], '--');
        assert(!data.text.includes('已部署 ACTIVE'));
        if (r === '/bots') assert(await page.$eval('.header-actions-group .btn-primary', e => e.disabled));
        if (r === '/risk') {
          assert(data.text.includes('沒有曝險或交易所保護資料'));
          assert(await page.$eval('.header-actions-group .btn-danger', e => e.disabled));
        }
        await page.screenshot({ path: path.join(evidence, `mode-${r.replace('/', '') || 'dashboard'}-${m}.png`), fullPage: true });
      }
      await mode(page, 'local');
    }
    assert.equal(await page.evaluate(() => JSON.stringify(window.__CATOS_ADAPTER__.runs)), before);
  });
  await test('UI: actual .py upload persists immutable version (Mock only)', async () => {
    const source = '# strategy_id: codex-upload\n# version: file-v1\n# name: Codex Upload\n# description: Frontend upload fixture only\n# warmup_bars: 2\n# defaults: {}\nclass Strategy:\n    pass\n';
    const input = path.join(evidence, 'upload-fixture.py');
    fs.writeFileSync(input, source); write('input-hashes.json', { 'upload-fixture.py': hash(input) });
    await route(page, '/strategies');
    const chooser = await page.$('input[type=file]');
    await chooser.uploadFile(input); note('actual file input upload: upload-fixture.py');
    await page.waitForFunction(() => window.__CATOS_ADAPTER__.strategies.some(s => s.artifact.strategy_id === 'codex-upload'));
    const before = await page.evaluate(() => window.__CATOS_ADAPTER__.strategies.find(s => s.artifact.strategy_id === 'codex-upload'));
    await page.reload({ waitUntil: 'networkidle0' });
    assert.deepEqual(await page.evaluate(() => window.__CATOS_ADAPTER__.strategies.find(s => s.artifact.strategy_id === 'codex-upload')), before);
    await page.screenshot({ path: path.join(evidence, 'python-upload.png'), fullPage: true });
    const conflict = await page.evaluate(async () => {
      const a = window.__CATOS_ADAPTER__, s = a.strategies.find(s => s.artifact.strategy_id === 'codex-upload');
      try { await a.createStrategy('immutable-conflict', { ...s.artifact, source: s.artifact.source + '# changed\n' }); return false; }
      catch (e) { return String(e).includes('immutable_version_conflict'); }
    });
    assert(conflict);
  });
  await test('UI: checked trust resets on close/reopen; allocation persists after refresh', async () => {
    await route(page, '/bots');
    await page.click('.header-actions-group .btn-primary');
    assert(await page.$eval('.modal-actions .btn-primary', e => e.disabled));
    await page.click('.trust-checkbox');
    assert(!(await page.$eval('.modal-actions .btn-primary', e => e.disabled)));
    await page.click('.modal-box .btn-close');
    await page.click('.header-actions-group .btn-primary');
    assert(!(await page.$eval('.trust-checkbox', e => e.checked)));
    assert(await page.$eval('.modal-actions .btn-primary', e => e.disabled));
    await page.type('.modal-box .form-input', 'codex-ui-bot');
    await page.click('.trust-checkbox');
    await page.click('.modal-actions .btn-primary');
    await page.waitForFunction(() => !document.querySelector('.modal-box'));
    await page.reload({ waitUntil: 'networkidle0' }); note('reload after allocation');
    await page.waitForFunction(() => document.body.innerText.includes('codex-ui-bot'));
    await page.screenshot({ path: path.join(evidence, 'trust-allocation-refresh.png'), fullPage: true });
  });
  await test('UI: start/stop buttons, retained position, history after refresh', async () => {
    // Remove seeded fake runs before starting this synthetic case; no product data.
    await page.evaluate(() => { const a = window.__CATOS_ADAPTER__; a.runs = []; a.saveState(); });
    await page.reload({ waitUntil: 'networkidle0' });
    async function clickBotAction(text) {
      const rows = await page.$$('.data-table tbody tr');
      for (const row of rows) {
        if ((await row.evaluate(e => e.innerText)).includes('codex-ui-bot')) {
          const buttons = await row.$$('.action-buttons button');
          for (const b of buttons) if ((await b.evaluate(e => e.innerText)).trim() === text) { await b.click(); note(`bot codex-ui-bot: ${text}`); return; }
        }
      }
      throw Error('bot action unavailable: ' + text);
    }
    await clickBotAction('啟動');
    await page.waitForFunction(() => window.__CATOS_ADAPTER__.runs.some(r => r.bot_id === 'codex-ui-bot' && r.control_state === 'running'));
    await pause(120); await clickBotAction('停止');
    await page.waitForFunction(() => window.__CATOS_ADAPTER__.runs.some(r => r.bot_id === 'codex-ui-bot' && r.control_state === 'stopped'));
    const before = await page.evaluate(() => window.__CATOS_ADAPTER__.fetchRuns());
    assert.equal(before[0].ownership_retained, true);
    await page.reload({ waitUntil: 'networkidle0' }); note('reload after UI stop');
    assert.deepEqual(await page.evaluate(() => window.__CATOS_ADAPTER__.fetchRuns()), before);
    await clickText(page, '.header-actions-group .btn-secondary', '執行成果歷史');
    await page.waitForFunction(() => document.body.innerText.includes('409 鎖定'));
    await page.screenshot({ path: path.join(evidence, 'ui-stop-history.png'), fullPage: true });
  });
  await test('Adapter: four 503 routes, altered-payload 409, same-command recovery', async () => {
    const checks = await page.evaluate(async () => {
      const a = window.__CATOS_ADAPTER__, checks = [];
      a.runs = []; a.commandLogs = []; a.setMode('local');
      const artifact = { ...a.strategies[0].artifact, strategy_id: 'codex-retry', version: 'v1' };
      async function transient(name, invoke, conflict) {
        a.setScenario('service_unavailable');
        try { await invoke(); throw Error('expected 503'); } catch (e) { if (!String(e).includes('503')) throw e; }
        const pending = JSON.stringify(a.getPendingCommand());
        try { await conflict(); throw Error('expected 409'); } catch (e) { if (!String(e).includes('409')) throw e; }
        if (JSON.stringify(a.getPendingCommand()) !== pending) throw Error('pending changed');
        a.setScenario('normal'); const result = await a.retryPendingCommand();
        if (a.getPendingCommand()) throw Error('pending not cleared');
        checks.push(name); return result;
      }
      const s = await transient('create', () => a.createStrategy('r-create', artifact), () => a.createStrategy('r-create', { ...artifact, description: 'changed' }));
      const payload = { bot_id: 'codex-retry-bot', artifact_hash: s.artifact_hash, parameters: {}, trusted: true, mode: 'local' };
      await transient('allocate', () => a.allocateBot('r-allocate', payload), () => a.allocateBot('r-allocate', { ...payload, parameters: { n: 2 } }));
      const run = await transient('start', () => a.startBot('r-start', payload.bot_id), () => a.startBot('r-start', 'other-bot'));
      await transient('stop', () => a.stopBot('r-stop', run.run_id), () => a.stopBot('r-stop', 'other-run'));
      const repeat = await a.stopBot('r-stop', run.run_id);
      if (repeat.run_id !== run.run_id || a.runs.length !== 1) throw Error('duplicate side effect');
      try { await a.startBot('r-retained', payload.bot_id); throw Error('expected retained'); } catch (e) { if (!String(e).includes('simulation_ownership_or_risk_retained')) throw e; }
      return checks;
    });
    assert.deepEqual(checks, ['create', 'allocate', 'start', 'stop']);
    write('retry-checks.json', checks);
  });
  await test('Adapter + UI refresh: snapshot mismatch, absent data, unknown stop stays locked', async () => {
    const result = await page.evaluate(async () => {
      const a = window.__CATOS_ADAPTER__, r = a.runs[0];
      r.artifact_hash = 'a'.repeat(64); r.binding.artifact_hash = r.artifact_hash;
      r.symbol = 'ETH-USDT-SWAP'; r.period = '1h'; r.slippage_bps = '7'; r.account.equity = '777.123';
      r.control_state = 'completed';
      a.bots.find(b => b.bot_id === r.bot_id).binding.artifact_hash = 'b'.repeat(64);
      const missing = { ...r, run_id: 'missing-history', control_state: 'running', artifact_hash: undefined, binding: undefined, symbol: undefined, period: undefined, slippage_bps: undefined, account: undefined };
      a.runs.push(missing);
      const repeatedStart = await a.startBot('snapshot-running', missing.bot_id);
      if (repeatedStart.artifact_hash !== 'unknown') throw Error('running response borrowed bot');
      const stopped = await a.stopBot('snapshot-stop', missing.run_id);
      if (stopped.artifact_hash !== 'unknown' || stopped.period !== 'unknown' || stopped.equity_usdt !== '--' || !stopped.ownership_retained || missing.account !== undefined) throw Error('missing snapshot fabricated');
      a.saveState(); return await a.fetchRuns();
    });
    assert.equal(result[0].artifact_hash, 'a'.repeat(64));
    assert.equal(result[0].equity_usdt, '777.123');
    await page.reload({ waitUntil: 'networkidle0' }); note('reload persisted history');
    const restored = await page.evaluate(() => window.__CATOS_ADAPTER__.fetchRuns());
    assert.deepEqual(restored, result);
    await clickText(page, '.header-actions-group .btn-secondary', '執行成果歷史');
    await page.waitForFunction(() => document.body.innerText.includes('777.123'));
    await page.screenshot({ path: path.join(evidence, 'history-restored.png'), fullPage: true });
  });
  await test('UI: delayed Local risk response cannot overwrite Demo', async () => {
    await page.evaluate(() => {
      const a = window.__CATOS_ADAPTER__, original = a.fetchRiskState.bind(a);
      a.fetchRiskState = async () => { const r = await original(); if (a.currentMode === 'local') { r.day_start_equity_usdt = '987654321.123'; await new Promise(resolve => setTimeout(resolve, 650)); } return r; };
    });
    await route(page, '/risk'); await mode(page, 'demo'); await pause(750);
    assert(!(await page.evaluate(() => document.body.innerText)).includes('987654321.123'));
    await page.screenshot({ path: path.join(evidence, 'risk-race.png'), fullPage: true });
  });
  assert.deepEqual(errors, []);
} catch (e) {
  process.exitCode = 1;
  lifecycle.failure = String(e.stack);
} finally {
  if (browser) await browser.close();
  if (server?.listening) { server.closeIdleConnections(); await new Promise(resolve => server.close(resolve)); }
  lifecycle.server_closed = !server?.listening;
  const drift = files.filter(f => hash(f) !== baseline[path.relative(root, f).replaceAll('\\', '/')]);
  lifecycle.source_drift = drift;
  if (drift.length) process.exitCode = 1;
  lifecycle.os_listener_after = port ? execFileSync('powershell.exe', ['-NoProfile', '-Command', `@(Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue).Count`], { encoding: 'utf8' }).trim() : 'not-started';
  if (port && lifecycle.os_listener_after !== '0') process.exitCode = 1;
  lifecycle.finished_at = new Date().toISOString();
  write('interactions.json', log); write('report.json', { results, browser_errors: errors }); write('lifecycle.json', lifecycle);
  process.on('exit', code => { lifecycle.process_exit_code = code; write('lifecycle.json', lifecycle); });
  console.log(JSON.stringify({ evidence, passed: results.filter(r => r.passed).length, total: results.length, exitCode: process.exitCode || 0, failure: lifecycle.failure }));
}
