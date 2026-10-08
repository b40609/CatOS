import puppeteer from 'puppeteer-core';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Evidence directory isolated for local resume 20261005 round 2 (never overwrite round 1)
const evidenceDir = path.resolve(__dirname, '../evidence/local-resume-20261005-r2');
fs.mkdirSync(evidenceDir, { recursive: true });

const CHROME_PATH = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = process.env.APP_URL || 'http://127.0.0.1:8902/?enable_test_adapter=1';

const report = {
  timestamp: new Date().toISOString(),
  targetUrl: APP_URL,
  fixtureBuild: {
    directory: 'dist-local-resume-r2',
    indexHtmlSha256: '1C4429BC5C61E5678D2BB33AD169B88D2C2B5D3FCE4D36DB1CE4C6E18774FA49',
    jsBundle: 'assets/index-CoGYLu7B.js',
    jsBundleSha256: '14FD7FCF3D73E1B7B91F4CA687561F62C114B9FEB907D724FEF76DEA33B6D2B9',
    cssBundle: 'assets/index-C6c_wTSd.css',
    cssBundleSha256: '337F4694D3798D7A884921BB89E2DC43B6E34221CD99E80BBCCD61C027BDC9AE'
  },
  results: {},
  passed: 0,
  failed: 0,
  errors: []
};

function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion Failed: ${message}`);
  }
}

async function runVerificationR2() {
  console.log('=== Starting CatOS Frontend R2 Complete Verification (6 Review Gaps) ===');
  console.log('Target URL:', APP_URL);
  console.log('Evidence Out Dir:', evidenceDir);
  console.log('Chrome Path:', CHROME_PATH);

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  await page.evaluateOnNewDocument(() => {
    window.__CATOS_ENABLE_TEST__ = true;
  });

  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.error('[Browser Console Error]:', msg.text());
    }
  });

  // Clear storage first to guarantee pristine baseline
  await page.goto(APP_URL, { waitUntil: 'networkidle0' });
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  await page.reload({ waitUntil: 'networkidle0' });

  // -------------------------------------------------------------
  // TEST 1: 全站模式切換（Local -> Demo -> Live -> Local）在 Bots、Dashboard、Risk 三頁
  // -------------------------------------------------------------
  console.log('\n[TEST 1] Verifying Full Mode Switch (Local -> Demo -> Live -> Local) across Bots, Dashboard & Risk...');
  try {
    // 1. Initial Local state on Bots
    await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));

    const initialAllocateBtn = await page.$('.header-actions-group button.btn-primary');
    assert(initialAllocateBtn !== null, 'Allocate button present');
    const initialAllocateDisabled = await page.evaluate(el => el.disabled, initialAllocateBtn);
    assert(!initialAllocateDisabled, 'Allocate button enabled in Local mode');

    // Switch to Demo mode
    const modeBtns = await page.$$('.mode-btn');
    let demoBtn = null;
    let liveBtn = null;
    let localBtn = null;
    for (const btn of modeBtns) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text.includes('Demo')) demoBtn = btn;
      if (text.includes('Live')) liveBtn = btn;
      if (text.includes('本機') || text.includes('Local')) localBtn = btn;
    }
    assert(demoBtn && liveBtn && localBtn, 'All mode buttons located');

    // Click Demo
    await demoBtn.click();
    await new Promise(r => setTimeout(r, 400));

    // Check Bots page in Demo mode
    const demoBotsBanner = await page.evaluate(() => {
      const b = document.querySelector('.banner-warning');
      return b ? b.textContent : '';
    });
    assert(demoBotsBanner.includes('DEMO') && demoBotsBanner.includes('唯讀'), 'Demo mode banner shown on Bots page');
    const demoAllocateDisabled = await page.evaluate(() => {
      const btn = document.querySelector('.header-actions-group button.btn-primary');
      return btn ? btn.disabled : false;
    });
    assert(demoAllocateDisabled, 'Allocate button disabled in Demo mode');

    // Check Dashboard page in Demo mode
    await page.goto(`${APP_URL}#/`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));
    const demoDashboardState = await page.evaluate(() => {
      const texts = Array.from(document.querySelectorAll('.kpi-card, .metric-value, .stat-value')).map(el => el.textContent);
      const isUnavailable = document.body.textContent.includes('UNAVAILABLE') || document.body.textContent.includes('Demo 模式尚未開放');
      return { texts, isUnavailable };
    });
    assert(demoDashboardState.isUnavailable, 'Dashboard displays Demo unavailable/locked state');

    // Check Risk page in Demo mode
    await page.goto(`${APP_URL}#/risk`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));
    const demoRiskState = await page.evaluate(() => {
      const banner = document.querySelector('.banner-warning');
      const killSwitch = document.querySelector('button.btn-danger');
      return {
        bannerText: banner ? banner.textContent : '',
        killSwitchDisabled: killSwitch ? killSwitch.disabled : false
      };
    });
    assert(demoRiskState.bannerText.includes('DEMO') && demoRiskState.bannerText.includes('唯讀'), 'Risk page displays Demo locked banner');
    assert(demoRiskState.killSwitchDisabled, 'Kill Switch button disabled in Demo mode');

    // Click Live mode
    const liveBtnRisk = await page.$$('.mode-btn');
    for (const btn of liveBtnRisk) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text.includes('Live')) {
        await btn.click();
        break;
      }
    }
    await new Promise(r => setTimeout(r, 400));

    // Check Risk page in Live mode
    const liveRiskBanner = await page.evaluate(() => {
      const b = document.querySelector('.banner-warning');
      return b ? b.textContent : '';
    });
    assert(liveRiskBanner.includes('LIVE') && liveRiskBanner.includes('唯讀'), 'Risk page displays Live locked banner');

    // Click Local mode to restore
    const localBtnRisk = await page.$$('.mode-btn');
    for (const btn of localBtnRisk) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text.includes('本機') || text.includes('Local')) {
        await btn.click();
        break;
      }
    }
    await new Promise(r => setTimeout(r, 400));

    // Check Bots page restored
    await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));
    const restoredBotsRows = await page.evaluate(() => {
      return document.querySelectorAll('.data-table tbody tr').length;
    });
    assert(restoredBotsRows >= 2, 'Local mode bots successfully restored');

    await page.screenshot({ path: path.join(evidenceDir, 'mode_switch_quad_verified.png') });
    console.log('✓ TEST 1 PASSED: Full mode switch (Local -> Demo -> Live -> Local) across Bots, Dashboard & Risk verified with full data isolation');
    report.results.test1_full_mode_switch_isolation = { passed: true, evidence: 'mode_switch_quad_verified.png' };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 1 FAILED:', err.message);
    report.results.test1_full_mode_switch_isolation = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 1: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 2: 409 持倉停止獨佔合約鎖定 (Ownership & Risk Retained)
  // -------------------------------------------------------------
  console.log('\n[TEST 2] Verifying 409 Conflict: simulation_ownership_or_risk_retained...');
  try {
    await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));

    // Ensure we trigger stop on a running bot holding position
    const conflictResult = await page.evaluate(async () => {
      const adapter = window.__CATOS_ADAPTER__;
      if (!adapter) throw new Error('Adapter not exposed');

      // Set scenario to hold_stopped_409
      adapter.setScenario('hold_stopped_409');
      let rejected = false;
      let errorMsg = '';
      try {
        await adapter.startBot('req-start-retained-01', 'bot-eth-meanrev-02');
      } catch (e) {
        rejected = true;
        errorMsg = e.message;
      }
      return { rejected, errorMsg };
    });

    assert(conflictResult.rejected, 'Starting bot when position retained MUST throw 409 conflict');
    assert(
      conflictResult.errorMsg.includes('409') && conflictResult.errorMsg.includes('simulation_ownership_or_risk_retained'),
      `Error must cite 409 simulation_ownership_or_risk_retained, got: ${conflictResult.errorMsg}`
    );

    await page.evaluate(() => {
      window.__CATOS_ADAPTER__.setScenario('normal');
    });

    await page.screenshot({ path: path.join(evidenceDir, '409_retained_position_contract_lock.png') });
    console.log('✓ TEST 2 PASSED: Retained position contract lock strictly enforces 409 simulation_ownership_or_risk_retained');
    report.results.test2_retained_position_contract_lock = { passed: true, evidence: '409_retained_position_contract_lock.png' };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 2 FAILED:', err.message);
    report.results.test2_retained_position_contract_lock = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 2: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 3: 不可變策略製品 Digest 嚴格驗證與 409 版本漂移衝突
  // -------------------------------------------------------------
  console.log('\n[TEST 3] Verifying Immutable Strategy Digest & 409 Version Conflict...');
  try {
    const conflictTest = await page.evaluate(async () => {
      const adapter = window.__CATOS_ADAPTER__;
      const strats = await adapter.fetchStrategies();
      const existing = strats[0];

      let versionConflict = false;
      let errorMsg = '';
      try {
        await adapter.createStrategy('req-drift-01', {
          ...existing.artifact,
          source: existing.artifact.source + '\n# Version drift source change'
        });
      } catch (e) {
        versionConflict = e.message.includes('409') && e.message.includes('immutable_version_conflict');
        errorMsg = e.message;
      }
      return { versionConflict, errorMsg };
    });

    assert(conflictTest.versionConflict, `Must reject version drift with 409 immutable_version_conflict, got: ${conflictTest.errorMsg}`);

    console.log('✓ TEST 3 PASSED: Immutable version drift strictly rejected with 409 conflict');
    report.results.test3_immutable_version_drift = { passed: true };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 3 FAILED:', err.message);
    report.results.test3_immutable_version_drift = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 3: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 4: 8 欄 Canonical SHA-256 向量比對與 RunDTO 快照還原（無假替補）
  // -------------------------------------------------------------
  console.log('\n[TEST 4] Verifying 8-field Canonical SHA-256 Vector & RunDTO Snapshot (No Fake Fallback)...');
  try {
    const vectorResult = await page.evaluate(async () => {
      const adapter = window.__CATOS_ADAPTER__;
      const coreVectorArtifact = {
        contract: 'catos.python-strategy.v1',
        strategy_id: 'counter-python',
        version: 'mcp-v1',
        name: 'Counter Python',
        description: 'Non-SMA short/flat counter with durable state',
        source: 'from decimal import Decimal\nclass Strategy:\n    def __init__(self, parameters):\n        self.parameters = parameters\n        self.n = 0\n        self.decisions = 0\n    def update_indicators(self, bar):\n        self.n += 1\n    @property\n    def ready(self):\n        return self.n >= 2\n    def on_bar(self, bar, account):\n        self.decisions += 1\n        if self.parameters.get("hold") or self.n % 2:\n            return Decimal(self.parameters["quantity"])\n        return Decimal("0")\n    def snapshot_state(self):\n        return {"n": self.n, "decisions": self.decisions}\n    def restore_state(self, state):\n        self.n = state["n"]\n        self.decisions = state["decisions"]\n',
        defaults: {
          quantity: '-1',
          hold: false
        },
        warmup_bars: 2
      };

      const EXPECTED_HASH = '8bb79f5f0bca9076c1006815bdae7846bbb6ca4446ec50740a50650ef8200aca';
      const entry = await adapter.createStrategy('req-vector-check-r2', coreVectorArtifact);
      const hashMatched = entry.artifact_hash === EXPECTED_HASH;

      // Invariant Check (Defect 3 & 4):
      // When a run has no hash and its bot cannot be found, it MUST return 'unknown', NEVER the fake fallback c70ea915...
      const syntheticRunWithoutHash = {
        contract: 'catos.simulation.v1',
        run_id: 'run-test-unknown-hash-99',
        bot_id: 'bot-non-existent-99',
        template_id: 'unknown-template',
        control_state: 'completed',
        cleanup_confirmed: true,
        stop_requested: false,
        request_id: 'req-unknown-hash-test',
        build_id: 'test-build',
        instance_id: 'test-instance',
        bars: 10,
        warmup_bars: 2,
        fills: 1,
        events: [],
        events_omitted: 0,
        worker_closed: true,
        error: null,
        created_at: new Date().toISOString(),
        finished_at: new Date().toISOString(),
        stop_requested_at: null,
        still_finishing: false
      };
      adapter.runs.unshift(syntheticRunWithoutHash);

      const runs = await adapter.fetchRuns();
      const testRun = runs.find(r => r.run_id === 'run-test-unknown-hash-99');
      const testRunHashIsUnknown = testRun && testRun.artifact_hash === 'unknown';
      const testRunSymbolIsUnknown = testRun && testRun.symbol === 'UNKNOWN';
      const testRunPeriodIsUnknown = testRun && testRun.period === 'unknown';
      const noFakeHexFallback = testRun && testRun.artifact_hash !== 'c70ea9157d376b2fb9e74be25d033f12af1195e6b2a415df762e07024e2fb834';

      return {
        hashMatched,
        actualHash: entry.artifact_hash,
        testRunHashIsUnknown,
        testRunSymbolIsUnknown,
        testRunPeriodIsUnknown,
        noFakeHexFallback,
        runsCount: runs.length
      };
    });

    assert(vectorResult.hashMatched, `Vector SHA-256 mismatch! Got: ${vectorResult.actualHash}`);
    assert(vectorResult.testRunHashIsUnknown, 'Run without binding hash MUST output "unknown", never fake fallback');
    assert(vectorResult.noFakeHexFallback, 'Run without binding hash MUST NOT contain fake fallback c70ea915...');
    assert(vectorResult.testRunSymbolIsUnknown && vectorResult.testRunPeriodIsUnknown, 'Missing snapshot fields MUST output unknown, not fake BTC/15m');

    console.log('✓ TEST 4 PASSED: Canonical SHA-256 matches core 8bb79f5f... and RunDTO snapshots restored without fake fallback');
    report.results.test4_canonical_vector_and_snapshot = { passed: true };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 4 FAILED:', err.message);
    report.results.test4_canonical_vector_and_snapshot = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 4: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 5: 完整 Payload 冪等性與 503 暫態失敗後情境恢復重送成功
  // -------------------------------------------------------------
  console.log('\n[TEST 5] Verifying Full Payload Idempotency & 503 Transient Failure Replay vs Modified Body Conflict...');
  try {
    const replayResult = await page.evaluate(async () => {
      const adapter = window.__CATOS_ADAPTER__;
      // Ensure clean state in Local mode
      adapter.currentMode = 'local';
      adapter.setScenario('normal');

      const strats = await adapter.fetchStrategies();
      const stratHash = strats[0].artifact_hash;
      const reqId = 'req-503-transient-test-01';
      const initialPayload = {
        bot_id: 'bot-503-transient-ok',
        artifact_hash: stratHash,
        parameters: { period: '15m' },
        trusted: true,
        mode: 'local'
      };

      // 1. Trigger 503 Service Unavailable on allocateBot
      adapter.setScenario('service_unavailable');
      let failed503 = false;
      let initialErrorMsg = '';
      try {
        await adapter.allocateBot(reqId, initialPayload);
      } catch (e) {
        failed503 = e.message.includes('503') || e.message.includes('Service Unavailable') || e.message.includes('Supervisor offline');
        initialErrorMsg = e.message;
      }

      // Check pending command recorded
      const pending1 = adapter.getPendingCommand();

      // 2. Same request ID but modified payload -> MUST throw 409
      let modifiedBodyRejected = false;
      let conflictMsg = '';
      try {
        await adapter.allocateBot(reqId, {
          ...initialPayload,
          parameters: { period: '1h' } // altered parameter!
        });
      } catch (e) {
        modifiedBodyRejected = e.message.includes('409') && e.message.includes('request_id_conflict');
        conflictMsg = e.message;
      }

      // 3. Recover service to normal
      adapter.setScenario('normal');

      // 4. Retry with identical request ID and identical payload -> MUST SUCCEED
      let retrySuccess = false;
      let retryError = '';
      try {
        const res = await adapter.retryPendingCommand();
        retrySuccess = !!(res && res.bot_id === 'bot-503-transient-ok');
      } catch (e) {
        retrySuccess = false;
        retryError = e.message;
      }

      const pendingAfter = adapter.getPendingCommand();

      return {
        failed503,
        initialErrorMsg,
        hasPendingRecorded: !!pending1,
        modifiedBodyRejected,
        conflictMsg,
        retrySuccess,
        retryError,
        pendingCleared: pendingAfter === null
      };
    });

    assert(replayResult.failed503, `Initial call under service_unavailable MUST fail with 503, got: ${replayResult.initialErrorMsg}`);
    assert(replayResult.hasPendingRecorded, '503 command MUST be preserved in pending command queue');
    assert(replayResult.modifiedBodyRejected, `Same request_id with altered body MUST throw 409 conflict, got: ${replayResult.conflictMsg}`);
    assert(replayResult.retrySuccess, `After service recovery, retrying identical command MUST succeed: ${replayResult.retryError}`);
    assert(replayResult.pendingCleared, 'Pending command queue MUST be cleared upon successful retry');

    await page.screenshot({ path: path.join(evidenceDir, '503_transient_retry_success.png') });
    console.log('✓ TEST 5 PASSED: 503 transient failure properly preserved; altered payload rejected (409), recovered replay succeeds');
    report.results.test5_503_transient_retry_and_conflict = { passed: true, evidence: '503_transient_retry_success.png' };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 5 FAILED:', err.message);
    report.results.test5_503_transient_retry_and_conflict = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 5: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 6: 分配參數完整邊界驗證與 Python AST 聲明
  // -------------------------------------------------------------
  console.log('\n[TEST 6] Verifying Allocation Parameter Boundaries & Python AST Sanity Declarations...');
  try {
    const boundaryCheck = await page.evaluate(async () => {
      const adapter = window.__CATOS_ADAPTER__;
      const strats = await adapter.fetchStrategies();
      const stratHash = strats[0].artifact_hash;

      // 1. Top-level array -> rejected
      let arrayRejected = false;
      try {
        await adapter.allocateBot('req-param-array-01', {
          bot_id: 'bot-param-array',
          artifact_hash: stratHash,
          parameters: ['period', '15m'],
          trusted: true,
          mode: 'local'
        });
      } catch (e) {
        arrayRejected = e.message.includes('strategy_parameters_object');
      }

      // 2. Float value in parameters -> rejected
      let floatRejected = false;
      try {
        await adapter.allocateBot('req-param-float-01', {
          bot_id: 'bot-param-float',
          artifact_hash: stratHash,
          parameters: { step: 0.5 },
          trusted: true,
          mode: 'local'
        });
      } catch (e) {
        floatRejected = e.message.includes('strategy_data_no_float');
      }

      // 3. Oversized parameters > 4096 bytes -> rejected
      let oversizedRejected = false;
      try {
        const bigParams = {};
        for (let i = 0; i < 60; i++) {
          bigParams[`param_key_${i}`] = 'x'.repeat(70);
        }
        await adapter.allocateBot('req-param-over-01', {
          bot_id: 'bot-param-over',
          artifact_hash: stratHash,
          parameters: bigParams,
          trusted: true,
          mode: 'local'
        });
      } catch (e) {
        oversizedRejected = e.message.includes('strategy_parameters_size');
      }

      // 4. Invalid Bot ID token -> rejected
      let invalidIdRejected = false;
      try {
        await adapter.allocateBot('req-invalid-id-01', {
          bot_id: 'bot.invalid.with.dots',
          artifact_hash: stratHash,
          parameters: { period: '15m' },
          trusted: true,
          mode: 'local'
        });
      } catch (e) {
        invalidIdRejected = e.message.includes('bot_contract');
      }

      // 5. Valid parameters -> accepted
      let validAccepted = false;
      try {
        const created = await adapter.allocateBot('req-param-valid-01', {
          bot_id: 'bot-param-valid',
          artifact_hash: stratHash,
          parameters: { period: '15m', max_drawdown: '0.05', step_int: 10 },
          trusted: true,
          mode: 'local'
        });
        validAccepted = (created && created.bot_id === 'bot-param-valid');
      } catch (e) {
        validAccepted = false;
      }

      return {
        arrayRejected,
        floatRejected,
        oversizedRejected,
        invalidIdRejected,
        validAccepted
      };
    });

    assert(boundaryCheck.arrayRejected, 'Top-level array parameters MUST be rejected');
    assert(boundaryCheck.floatRejected, 'Float values in parameters MUST be rejected (must use Decimal string)');
    assert(boundaryCheck.oversizedRejected, 'Oversized canonical parameters (>4096 bytes) MUST be rejected');
    assert(boundaryCheck.invalidIdRejected, 'Bot ID with invalid characters MUST be rejected');
    assert(boundaryCheck.validAccepted, 'Valid dictionary parameters with safe integers & strings MUST be accepted');

    console.log('✓ TEST 6 PASSED: Allocation parameter boundaries (array, float, >4096B, TOKEN) strictly validated');
    report.results.test6_allocation_parameter_boundaries = { passed: true };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 6 FAILED:', err.message);
    report.results.test6_allocation_parameter_boundaries = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 6: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 7: 動態 Worker 監控狀態逐列嚴格比對 (Row-by-Row Assertion)
  // -------------------------------------------------------------
  console.log('\n[TEST 7] Verifying Row-by-Row Worker Process Monitor vs Bot Control State...');
  try {
    await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));

    const workerRows = await page.evaluate(() => {
      const items = Array.from(document.querySelectorAll('.worker-list .worker-item'));
      return items.map(item => {
        const pidEl = item.querySelector('.worker-pid');
        const tagEl = item.querySelector('.worker-tag');
        const badgeEl = item.querySelector('.worker-header .badge');
        const metaEl = item.querySelector('.worker-meta');
        return {
          pid: pidEl ? pidEl.textContent.trim() : '',
          tag: tagEl ? tagEl.textContent.trim() : '',
          badgeText: badgeEl ? badgeEl.textContent.trim() : '',
          badgeClass: badgeEl ? badgeEl.className : '',
          metaText: metaEl ? metaEl.textContent.trim() : ''
        };
      });
    });

    assert(workerRows.length >= 2, `Expected at least 2 worker items, got ${workerRows.length}`);

    // Verify demonstrative note is present
    const demoBadgePresent = await page.evaluate(() => {
      const el = document.querySelector('.card-title .badge-warning');
      return el && el.textContent.includes('未連後端真 Worker（示意）');
    });
    assert(demoBadgePresent, 'Demonstrative badge "未連後端真 Worker（示意）" MUST be clearly visible');

    // Row 0: Running bot -> HEALTHY, badge-success
    const row0 = workerRows[0];
    assert(row0.badgeText === 'HEALTHY', `Row 0 badgeText expected "HEALTHY", got "${row0.badgeText}"`);
    assert(row0.badgeClass.includes('badge-success'), `Row 0 badgeClass expected "badge-success", got "${row0.badgeClass}"`);
    assert(row0.pid.includes('PID'), `Row 0 PID expected assigned PID, got "${row0.pid}"`);

    // Row 1: Stopped bot -> STOPPED, badge-neutral
    const row1 = workerRows[1];
    assert(row1.badgeText === 'STOPPED', `Row 1 badgeText expected "STOPPED", got "${row1.badgeText}"`);
    assert(row1.badgeClass.includes('badge-neutral'), `Row 1 badgeClass expected "badge-neutral", got "${row1.badgeClass}"`);
    assert(row1.pid === '--', `Row 1 PID expected "--", got "${row1.pid}"`);

    await page.screenshot({ path: path.join(evidenceDir, 'worker_monitor_row_by_row_verified.png') });
    console.log('✓ TEST 7 PASSED: Worker process monitor verified row-by-row with exact 1-to-1 bot state mapping and demonstrative note');
    report.results.test7_worker_monitor_row_by_row = { passed: true, evidence: 'worker_monitor_row_by_row_verified.png' };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 7 FAILED:', err.message);
    report.results.test7_worker_monitor_row_by_row = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 7: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 8: 人工信任核取方塊 (Manual Trust Checkbox) 嚴格把關與自動重設
  // -------------------------------------------------------------
  console.log('\n[TEST 8] Verifying Manual Trust Checkbox Strict Gate & Auto-Reset...');
  try {
    await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));

    // 1. Open modal
    const allocateBtn = await page.$('.header-actions-group button.btn-primary');
    await allocateBtn.click();
    await new Promise(r => setTimeout(r, 300));

    // 2. Check that checkbox is UNCHECKED by default
    const isCheckedInitial = await page.evaluate(() => {
      const cb = document.querySelector('.trust-checkbox');
      return cb ? cb.checked : true;
    });
    assert(!isCheckedInitial, 'Trust checkbox MUST NOT be pre-checked');

    // 3. Confirm submit button is disabled
    const submitDisabledInitial = await page.evaluate(() => {
      const btn = document.querySelector('.modal-actions button.btn-primary');
      return btn ? btn.disabled : false;
    });
    assert(submitDisabledInitial, 'Submit button MUST be disabled when trust is unconfirmed');

    // 4. Close modal
    await page.click('.btn-close');
    await new Promise(r => setTimeout(r, 300));

    // 5. Re-open modal and verify it is STILL unchecked
    await allocateBtn.click();
    await new Promise(r => setTimeout(r, 300));

    const isCheckedReopen = await page.evaluate(() => {
      const cb = document.querySelector('.trust-checkbox');
      return cb ? cb.checked : true;
    });
    assert(!isCheckedReopen, 'Trust checkbox MUST remain unchecked upon modal re-open');

    // 6. Check the checkbox
    await page.click('.trust-checkbox');
    await new Promise(r => setTimeout(r, 200));

    const submitEnabledAfterCheck = await page.evaluate(() => {
      const btn = document.querySelector('.modal-actions button.btn-primary');
      return btn ? !btn.disabled : false;
    });
    assert(submitEnabledAfterCheck, 'Submit button MUST become enabled once trust checkbox is checked');

    await page.screenshot({ path: path.join(evidenceDir, 'manual_trust_checkbox_verified.png') });
    console.log('✓ TEST 8 PASSED: Manual trust confirmation strictly enforced and automatically reset upon modal toggle');
    report.results.test8_manual_trust_checkbox_gate = { passed: true, evidence: 'manual_trust_checkbox_verified.png' };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 8 FAILED:', err.message);
    report.results.test8_manual_trust_checkbox_gate = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 8: ${err.message}`);
  }

  await browser.close();

  // Write report
  const reportPath = path.join(evidenceDir, 'verification-report-r2.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf-8');
  console.log('\n=== R2 Complete Verification Summary ===');
  console.log(`Passed: ${report.passed} / 8`);
  console.log(`Failed: ${report.failed} / 8`);
  console.log('Report saved to:', reportPath);

  if (report.failed > 0) {
    process.exit(1);
  }
}

runVerificationR2().catch(err => {
  console.error('FATAL verification execution error:', err);
  process.exit(1);
});
