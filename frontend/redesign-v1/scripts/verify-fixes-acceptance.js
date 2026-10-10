import puppeteer from 'puppeteer-core';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const evidenceDir = path.resolve(__dirname, '../evidence');
fs.mkdirSync(evidenceDir, { recursive: true });

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = 'http://127.0.0.1:8899/';
const SAMPLE_PY_PATH = path.resolve(__dirname, 'sample_test_strategy.py');

const report = {
  timestamp: new Date().toISOString(),
  targetUrl: APP_URL,
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

async function runAcceptance() {
  console.log('=== Starting Acceptance Verification for 7 Reported Issues ===');
  console.log('App URL:', APP_URL);
  console.log('Sample Python File:', SAMPLE_PY_PATH);

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.error('[Browser Error]:', msg.text());
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
  // TEST 1: Demo 顯示控制已鎖定，仍能啟動 Bot
  // -------------------------------------------------------------
  console.log('\n[TEST 1] Verifying Demo Mode Controls & Locking...');
  try {
    await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));

    // Initially in local mode: Allocate button should be enabled
    const allocateBtnInitial = await page.$('.header-actions-group button.btn-primary');
    const allocateDisabledInitial = await page.evaluate(el => el.disabled, allocateBtnInitial);
    assert(!allocateDisabledInitial, 'Allocate button should be enabled in Local mode');

    // Switch to Demo mode
    const modeBtns = await page.$$('.mode-btn');
    let demoBtn = null;
    for (const btn of modeBtns) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text.includes('Demo')) {
        demoBtn = btn;
        break;
      }
    }
    assert(demoBtn !== null, 'Demo mode button found');
    await demoBtn.click();
    await new Promise(r => setTimeout(r, 400));

    // Verify Read-only alert banner appears
    const bannerText = await page.evaluate(() => {
      const b = document.querySelector('.banner-warning');
      return b ? b.textContent : '';
    });
    assert(bannerText.includes('唯讀') || bannerText.includes('DEMO'), 'Demo read-only banner displayed');

    // Verify Allocate button is disabled
    const allocateBtnDemo = await page.$('.header-actions-group button.btn-primary');
    const allocateDisabledDemo = await page.evaluate(el => el.disabled, allocateBtnDemo);
    assert(allocateDisabledDemo, 'Allocate button is disabled in Demo mode');

    // Verify Start and Stop buttons are all disabled
    const actionBtns = await page.$$('.data-table button.btn');
    for (const btn of actionBtns) {
      const isDisabled = await page.evaluate(el => el.disabled, btn);
      assert(isDisabled, 'All table action buttons must be disabled in Demo mode');
    }

    // Verify Adapter level rejection in Demo mode
    const adapterRejection = await page.evaluate(async () => {
      try {
        const adapter = window.__CATOS_ADAPTER__;
        await adapter.startBot('test-req-demo', 'bot-btc-trend-01');
        return { rejected: false };
      } catch (e) {
        return { rejected: true, message: e.message };
      }
    });
    assert(adapterRejection.rejected, 'Adapter must reject startBot in Demo mode');
    assert(adapterRejection.message.includes('唯讀') || adapterRejection.message.includes('DEMO') || adapterRejection.message.includes('DEMO_MODE_LOCKED'), 'Rejection mentions read-only mode');

    await page.screenshot({ path: path.join(evidenceDir, 'acceptance_demo_mode_locked.png') });
    console.log('✓ TEST 1 PASSED: Demo mode properly locks UI buttons and adapter execution');
    report.results.test1_demo_mode_locked = { passed: true, evidence: 'acceptance_demo_mode_locked.png' };
    report.passed++;

    // Switch back to Local mode for subsequent tests
    let localBtn = null;
    for (const btn of modeBtns) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text.includes('本機')) {
        localBtn = btn;
        break;
      }
    }
    if (localBtn) await localBtn.click();
    await new Promise(r => setTimeout(r, 400));
  } catch (err) {
    console.error('✗ TEST 1 FAILED:', err.message);
    report.results.test1_demo_mode_locked = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 1: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 2: 啟動 ETH 後，原本持倉的 BTC 被篡改成「已完成」；刷新後錯誤狀態仍保留
  // -------------------------------------------------------------
  console.log('\n[TEST 2] Verifying Single Simulation Slot Occupancy & Retention (BTC not mutated to completed)...');
  try {
    await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));

    // Verify initial BTC bot is RUNNING with position 1 (Column index 4 is position)
    const initialBtcState = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('.data-table tbody tr'));
      for (const row of rows) {
        if (row.textContent.includes('bot-btc-trend-01')) {
          return {
            text: row.textContent,
            isRunning: row.textContent.includes('RUNNING') || row.textContent.includes('運行中'),
            position: row.children[4]?.textContent?.trim() || ''
          };
        }
      }
      return null;
    });
    assert(initialBtcState !== null, 'BTC bot found in table');
    assert(initialBtcState.isRunning, 'BTC bot initially RUNNING');
    assert(initialBtcState.position.includes('1'), 'BTC bot holds 1 contract position');

    // Attempt to start ETH bot (bot-eth-grid-02)
    const ethStartClicked = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('.data-table tbody tr'));
      for (const row of rows) {
        if (row.textContent.includes('bot-eth-grid-02')) {
          const btn = row.querySelector('button.btn-primary');
          if (btn) {
            btn.click();
            return true;
          }
        }
      }
      return false;
    });
    assert(ethStartClicked, 'Found and clicked start on ETH bot');
    await new Promise(r => setTimeout(r, 600));

    // Verify 409 conflict error banner appears
    const errorBannerText = await page.evaluate(() => {
      const b = document.querySelector('.banner-danger');
      return b ? b.textContent : '';
    });
    assert(errorBannerText.includes('409') || errorBannerText.includes('simulation_slot_occupied') || errorBannerText.includes('正在運行中'), '409 Slot occupied conflict displayed');

    // CRITICAL CHECK: BTC bot MUST STILL BE RUNNING with position 1, NOT 'completed' or '已完成'!
    const btcStateAfterEthAttempt = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('.data-table tbody tr'));
      for (const row of rows) {
        if (row.textContent.includes('bot-btc-trend-01')) {
          return {
            text: row.textContent,
            isRunning: row.textContent.includes('RUNNING') || row.textContent.includes('運行中'),
            isCompleted: row.textContent.includes('COMPLETED') || row.textContent.includes('已完成'),
            position: row.children[4]?.textContent?.trim() || ''
          };
        }
      }
      return null;
    });
    assert(btcStateAfterEthAttempt.isRunning, 'BTC bot MUST REMAIN RUNNING');
    assert(!btcStateAfterEthAttempt.isCompleted, 'BTC bot MUST NOT BE COMPLETED');
    assert(btcStateAfterEthAttempt.position.includes('1'), 'BTC bot position must remain 1');

    await page.screenshot({ path: path.join(evidenceDir, 'acceptance_slot_conflict_btc_retained.png') });

    // Refresh page (F5) to verify persistence across reloads
    console.log('Reloading page (F5) to verify state persistence...');
    await page.reload({ waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));

    const btcStateAfterReload = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('.data-table tbody tr'));
      for (const row of rows) {
        if (row.textContent.includes('bot-btc-trend-01')) {
          return {
            text: row.textContent,
            isRunning: row.textContent.includes('RUNNING') || row.textContent.includes('運行中'),
            isCompleted: row.textContent.includes('COMPLETED') || row.textContent.includes('已完成'),
            position: row.children[4]?.textContent?.trim() || ''
          };
        }
      }
      return null;
    });
    assert(btcStateAfterReload.isRunning, 'BTC bot STILL RUNNING after reload');
    assert(!btcStateAfterReload.isCompleted, 'BTC bot NOT completed after reload');
    assert(btcStateAfterReload.position.includes('1'), 'BTC bot position still 1 after reload');

    // Now cleanly stop BTC bot and verify retention
    console.log('Stopping BTC bot cleanly and verifying position retention...');
    const btcStopClicked = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('.data-table tbody tr'));
      for (const row of rows) {
        if (row.textContent.includes('bot-btc-trend-01')) {
          const btn = row.querySelector('button.btn-danger');
          if (btn) {
            btn.click();
            return true;
          }
        }
      }
      return false;
    });
    assert(btcStopClicked, 'Clicked stop on BTC bot');
    await new Promise(r => setTimeout(r, 600));

    // Verify BTC bot is now STOPPED, but position 1 is RETAINED!
    const btcStateStopped = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('.data-table tbody tr'));
      for (const row of rows) {
        if (row.textContent.includes('bot-btc-trend-01')) {
          return {
            isStopped: row.textContent.includes('STOPPED') || row.textContent.includes('已停止'),
            position: row.children[4]?.textContent?.trim() || ''
          };
        }
      }
      return null;
    });
    assert(btcStateStopped.isStopped, 'BTC bot is now STOPPED');
    assert(btcStateStopped.position.includes('1'), 'BTC position is RETAINED (1 contract) after stop');

    // Reload again to verify stopped + retained position persists
    await page.reload({ waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));
    const btcStateStoppedAfterReload = await page.evaluate(() => {
      const rows = Array.from(document.querySelectorAll('.data-table tbody tr'));
      for (const row of rows) {
        if (row.textContent.includes('bot-btc-trend-01')) {
          return {
            isStopped: row.textContent.includes('STOPPED') || row.textContent.includes('已停止'),
            position: row.children[4]?.textContent?.trim() || ''
          };
        }
      }
      return null;
    });
    assert(btcStateStoppedAfterReload.isStopped, 'BTC bot is STOPPED after reload');
    assert(btcStateStoppedAfterReload.position.includes('1'), 'BTC position 1 preserved after reload');

    await page.screenshot({ path: path.join(evidenceDir, 'acceptance_btc_stopped_retained_after_reload.png') });
    console.log('✓ TEST 2 PASSED: 409 slot occupancy prevents corrupting BTC run; position retained across reloads');
    report.results.test2_slot_occupancy_btc_retained = { passed: true, evidence: 'acceptance_slot_conflict_btc_retained.png' };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 2 FAILED:', err.message);
    report.results.test2_slot_occupancy_btc_retained = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 2: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 3: 錯 hash 自動綁第一個策略
  // -------------------------------------------------------------
  console.log('\n[TEST 3] Verifying Invalid Strategy Hash Rejection (No Fallback to Strategy 0)...');
  try {
    const invalidHashResult = await page.evaluate(async () => {
      const adapter = window.__CATOS_ADAPTER__;
      const badHash = '0000000000000000000000000000000000000000000000000000000000000000';
      try {
        await adapter.allocateBot('req-bad-hash-test', {
          bot_id: 'bot-invalid-hash-test',
          artifact_hash: badHash,
          parameters: {},
          trusted: true,
          mode: 'local'
        });
        return { threw: false };
      } catch (e) {
        return { threw: true, message: e.message };
      }
    });

    assert(invalidHashResult.threw, 'Allocating bot with unknown hash MUST throw error');
    assert(invalidHashResult.message.includes('STRATEGY_NOT_FOUND'), `Error should be STRATEGY_NOT_FOUND, got: ${invalidHashResult.message}`);

    console.log('✓ TEST 3 PASSED: Invalid strategy hash strictly rejected with STRATEGY_NOT_FOUND, no silent fallback');
    report.results.test3_invalid_hash_no_fallback = { passed: true };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 3 FAILED:', err.message);
    report.results.test3_invalid_hash_no_fallback = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 3: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 4: 隨機生成版本 hash
  // -------------------------------------------------------------
  console.log('\n[TEST 4] Verifying Real Deterministic SHA-256 Version Hash Calculation...');
  try {
    const hashCheck = await page.evaluate(async () => {
      const computeSha256 = window.__CATOS_SHA256__;
      const adapter = window.__CATOS_ADAPTER__;
      const testContent = 'class Strategy: pass';
      const hash1 = await computeSha256(testContent);
      const hash2 = await computeSha256(testContent);

      // Verify deterministic: identical inputs yield identical hashes
      const deterministic = (hash1 === hash2) && (hash1.length === 64);

      // Test createStrategy returns 64 hex sha256
      const created = await adapter.createStrategy('req-sha256-test', {
        contract: 'catos.python-strategy.v1',
        strategy_id: 'sha256-test-strat',
        version: 'file-v1',
        name: 'SHA256 Test Strategy',
        description: 'Testing sha256 hashing',
        source: testContent,
        defaults: { period: '15m' },
        warmup_bars: 2
      });

      return {
        deterministic,
        hash1,
        createdHash: created.artifact_hash,
        is64Hex: /^[a-f0-9]{64}$/.test(created.artifact_hash)
      };
    });

    assert(hashCheck.deterministic, 'SHA-256 calculation must be deterministic');
    assert(hashCheck.is64Hex, 'Created strategy artifact_hash must be 64-char lowercase hex');
    console.log('✓ TEST 4 PASSED: Strategy version hash uses real SHA-256 (64 hex characters):', hashCheck.createdHash.slice(0, 16) + '...');
    report.results.test4_real_sha256_hash = { passed: true, sampleHash: hashCheck.createdHash };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 4 FAILED:', err.message);
    report.results.test4_real_sha256_hash = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 4: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 5: .py 匯入版本不符核心契約 & 匯入測試沒有實際上傳
  // -------------------------------------------------------------
  console.log('\n[TEST 5] Verifying Real File Upload of .py Strategy & Core Contract Compliance (file-v1)...');
  try {
    await page.goto(`${APP_URL}#/strategies`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));

    const initialStrategyCount = await page.$$eval('.strat-item', els => els.length);

    // Locate the hidden file input
    const fileInput = await page.$('input[type="file"][accept*=".py"]');
    assert(fileInput !== null, 'File input element found on Strategies page');

    // Real file upload via Puppeteer
    await fileInput.uploadFile(SAMPLE_PY_PATH);
    await page.evaluate(el => el.dispatchEvent(new Event('change', { bubbles: true })), fileInput);
    await page.waitForSelector('.banner-success', { timeout: 5000 });

    // Verify success banner appears
    const successMsgText = await page.evaluate(() => {
      const b = document.querySelector('.banner-success');
      return b ? b.textContent : '';
    });
    assert(successMsgText.includes('匯入成功') || successMsgText.includes('Counter Python Strategy'), `Import success banner displayed, got: ${successMsgText}`);

    // Verify new strategy appears in list
    const newStrategyCount = await page.$$eval('.strat-item', els => els.length);
    assert(newStrategyCount === initialStrategyCount + 1, `Strategy count increased by 1 (was ${initialStrategyCount}, now ${newStrategyCount})`);

    // Verify the newly uploaded strategy details in the right pane
    const uploadedDetails = await page.evaluate(() => {
      const items = Array.from(document.querySelectorAll('.strat-item'));
      const counterItem = items.find(i => i.textContent.includes('Counter Python Strategy'));
      if (counterItem) counterItem.click();

      const detailText = document.querySelector('.strategy-detail-col')?.textContent || '';
      return {
        foundInList: !!counterItem,
        detailText,
        hasFileV1: detailText.includes('file-v1'),
        hasCounterPython: detailText.includes('counter-python'),
        hasWarmup2: detailText.includes('2')
      };
    });

    assert(uploadedDetails.foundInList, 'Uploaded strategy present in sidebar list');
    assert(uploadedDetails.hasFileV1, 'Strategy version is file-v1 (conforming to CatOS core contract)');
    assert(uploadedDetails.hasCounterPython, 'Strategy ID is counter-python');

    // Reload page (F5) and verify uploaded strategy persists
    await page.reload({ waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));
    const persistedAfterReload = await page.evaluate(() => {
      return document.body.innerText.includes('Counter Python Strategy') && document.body.innerText.includes('file-v1');
    });
    assert(persistedAfterReload, 'Uploaded .py strategy persists after page reload');

    await page.screenshot({ path: path.join(evidenceDir, 'acceptance_py_strategy_uploaded_file_v1.png') });
    console.log('✓ TEST 5 PASSED: Real .py file uploaded, parsed with version file-v1, rendered and persisted');
    report.results.test5_real_py_upload_contract = { passed: true, evidence: 'acceptance_py_strategy_uploaded_file_v1.png' };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 5 FAILED:', err.message);
    report.results.test5_real_py_upload_contract = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 5: ${err.message}`);
  }

  // -------------------------------------------------------------
  // TEST 6: 重送缺乏冪等處理
  // -------------------------------------------------------------
  console.log('\n[TEST 6] Verifying Command Idempotency (replay identical vs 409 conflict on different body)...');
  try {
    const idempotencyTest = await page.evaluate(async () => {
      const adapter = window.__CATOS_ADAPTER__;
      const testReqId = 'test-idempotency-fixed-req-id-888';
      const stratHash = (await adapter.fetchStrategies())[0].artifact_hash;

      // 1. First execution
      const res1 = await adapter.allocateBot(testReqId, {
        bot_id: 'bot-idempotency-test-01',
        artifact_hash: stratHash,
        parameters: { period: '15m' },
        trusted: true,
        mode: 'local'
      });

      // 2. Replay with identical reqId and same bot_id -> MUST return identical response
      const res2 = await adapter.allocateBot(testReqId, {
        bot_id: 'bot-idempotency-test-01',
        artifact_hash: stratHash,
        parameters: { period: '15m' },
        trusted: true,
        mode: 'local'
      });
      const identicalReplay = (res1.bot_id === res2.bot_id);

      // 3. Send same reqId with DIFFERENT bot_id -> MUST throw 409 Conflict
      let conflictDetected = false;
      let conflictMsg = '';
      try {
        await adapter.allocateBot(testReqId, {
          bot_id: 'bot-idempotency-conflict-02',
          artifact_hash: stratHash,
          parameters: { period: '15m' },
          trusted: true,
          mode: 'local'
        });
      } catch (e) {
        conflictDetected = true;
        conflictMsg = e.message;
      }

      return {
        identicalReplay,
        conflictDetected,
        conflictMsg,
        res1BotId: res1.bot_id
      };
    });

    assert(idempotencyTest.identicalReplay, 'Replaying identical request with same request_id must return identical response');
    assert(idempotencyTest.conflictDetected, 'Reusing request_id for different command must throw 409 Conflict');
    assert(idempotencyTest.conflictMsg.includes('409') || idempotencyTest.conflictMsg.includes('conflict'), 'Conflict message mentions 409 conflict');

    console.log('✓ TEST 6 PASSED: Request ID idempotency verified: identical replay returns cached response, divergent body throws 409');
    report.results.test6_idempotency_handling = { passed: true };
    report.passed++;
  } catch (err) {
    console.error('✗ TEST 6 FAILED:', err.message);
    report.results.test6_idempotency_handling = { passed: false, error: err.message };
    report.failed++;
    report.errors.push(`TEST 6: ${err.message}`);
  }

  // Summary
  await browser.close();
  const reportPath = path.join(evidenceDir, 'acceptance_verification_report.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf-8');

  console.log('\n=============================================================');
  console.log(`ACCEPTANCE SUMMARY: ${report.passed} PASSED, ${report.failed} FAILED`);
  console.log('Report saved to:', reportPath);
  console.log('=============================================================');

  if (report.failed > 0) {
    process.exit(1);
  }
}

runAcceptance().catch(err => {
  console.error('Fatal execution error:', err);
  process.exit(1);
});
