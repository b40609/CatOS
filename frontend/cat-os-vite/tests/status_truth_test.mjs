// Regression tests for frontend status truthfulness (CAT-BX-03, CAT-BX-04, CAT-BX-10, CAT-B-06, CAT-B-24).
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const frontend = fileURLToPath(new URL('..', import.meta.url));
let server;

before(async () => {
  server = await createServer({
    root: frontend,
    server: { middlewareMode: true },
    appType: 'custom',
    optimizeDeps: { noDiscovery: true, entries: [] },
  });
});

after(async () => {
  await server?.close();
});

test('CAT-BX-03 & CAT-B-24: sidebar has no hardcoded green pulse and PulseBeacon has no infinite breathe/ping animation', async () => {
  const shellSrc = await fs.readFile(path.join(frontend, 'src/components/catos/shell.tsx'), 'utf8');
  assert.ok(!shellSrc.includes('狀態正常運行中'), 'shell.tsx still hardcodes 狀態正常運行中');
  assert.ok(!shellSrc.includes('hasPulse: true'), 'shell.tsx still hardcodes hasPulse: true on /bots');

  const beaconSrc = await fs.readFile(path.join(frontend, 'src/components/catos/pulse-beacon.tsx'), 'utf8');
  assert.ok(!beaconSrc.includes('animate-ping'), 'PulseBeacon still uses animate-ping');
  assert.ok(!beaconSrc.includes('status-breathe'), 'PulseBeacon still uses status-breathe');
});

test('CAT-BX-10 / G-15: settings page does not claim synced or active injection while backend is offline', async () => {
  const settingsSrc = await fs.readFile(path.join(frontend, 'src/pages/settings.tsx'), 'utf8');
  assert.ok(!settingsSrc.includes('靜默注入啟用中'), 'settings.tsx still hardcodes 靜默注入啟用中');
  const truth = await server.ssrLoadModule('/src/lib/status-truth.ts');
  assert.equal(truth.backendSyncText(false, null, null), '不適用（後端未連接）');
  assert.equal(
    truth.backendSyncText(true, { restart_required: false }, { restart_required: true }),
    '源碼已異動（需重啟服務）'
  );
  assert.equal(
    truth.backendSyncText(true, { restart_required: false }, { restart_required: false }),
    '與磁碟源碼一致'
  );
});

test('CAT-B-06: cushion status honors authoritative soft_latch / hard_latch even after PnL rebounds', async () => {
  const truth = await server.ssrLoadModule('/src/lib/status-truth.ts');
  // Rebounded to -1.5% (above -5% Soft), but backend is still soft_latch -> must say Soft 鎖住, never 距 Soft 3.50%
  const latched = truth.deriveCushionStatus({
    currentPct: -1.5,
    softPct: 5,
    hardPct: 10,
    riskStatus: 'soft_latch',
    riskMode: 'NO_INCREASE',
    killEngaged: false,
  });
  assert.equal(latched.statusText, 'Soft 鎖住');

  const hard = truth.deriveCushionStatus({
    currentPct: -2.0,
    softPct: 5,
    hardPct: 10,
    riskStatus: 'hard_latch',
    riskMode: 'FLAT',
    killEngaged: true,
  });
  assert.equal(hard.statusText, 'Hard 鎖住');

  const normal = truth.deriveCushionStatus({
    currentPct: -1.5,
    softPct: 5,
    hardPct: 10,
    riskStatus: 'normal',
    riskMode: 'RUN',
    killEngaged: false,
  });
  assert.equal(normal.statusText, '距 Soft 3.50%');
});

test('CAT-BX-04: abnormal stopped runs, read failures, and stale runs with positions are surfaced accurately', async () => {
  const truth = await server.ssrLoadModule('/src/lib/status-truth.ts');
  assert.equal(truth.isOperatorStop('operator_stop_file'), true);
  assert.equal(truth.isOperatorStop('operator_stop'), true);
  assert.equal(truth.isOperatorStop('interrupted'), true);
  assert.equal(truth.isOperatorStop('position_mismatch:okx=1:ledger=0'), false);
  assert.equal(truth.isOperatorStop('okx_read_failed:50001'), false);
  assert.equal(truth.isOperatorStop(null), false);

  const items = truth.buildDemoBotActionItems({
    runs: [
      {
        run_id: '1'.repeat(32),
        created_at_ms: 200,
        state: 'stopped',
        stale: false,
        stop_reason: 'position_mismatch:okx=1:ledger=0',
        bars: 10,
        fills: 1,
        position: '1',
        updated_at_ms: 200,
        strategy_id: 'donchian-breakout',
      },
      {
        run_id: '2'.repeat(32),
        created_at_ms: 300,
        state: 'running',
        stale: true,
        stop_reason: null,
        bars: 20,
        fills: 1,
        position: '-1',
        updated_at_ms: 300,
        strategy_id: 'sma-trend',
      },
    ],
    demoBotError: null,
  });
  const mismatch = items.find((x) => x.id.includes('11111111'));
  const staleOpen = items.find((x) => x.id.includes('22222222'));
  assert.ok(mismatch, 'abnormal stopped run must produce an action item');
  assert.equal(mismatch.sev, 'p0');
  assert.ok(staleOpen, 'stale run with open position must produce an action item');
  assert.equal(staleOpen.sev, 'p0');

  const errItems = truth.buildDemoBotActionItems({ runs: [], demoBotError: 'http_503' });
  assert.equal(errItems.length, 1);
  assert.equal(errItems[0].title, '讀不到模擬盤 Bot');
});
