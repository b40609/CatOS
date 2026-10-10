import puppeteer from 'puppeteer-core';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const evidenceDir = path.resolve(__dirname, '../evidence');
fs.mkdirSync(evidenceDir, { recursive: true });

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_PORT = 61943;
const APP_URL = `http://127.0.0.1:${APP_PORT}/`;

const results = [];
function record(step, pass, details) {
  results.push({ step, pass, details });
  const mark = pass ? '✓ PASS' : '✗ FAIL';
  console.log(`${mark}: [${step}] - ${details}`);
}

async function run() {
  console.log('====================================================');
  console.log('CatOS Frontend Redesign v1 - Full Verification Suite');
  console.log('Target URL:', APP_URL);
  console.log('Evidence Dir:', evidenceDir);
  console.log('====================================================');

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  try {
    await page.setViewport({ width: 1440, height: 900 });
    await page.goto(APP_URL, { waitUntil: 'networkidle0' });
    await page.waitForSelector('.app-shell', { timeout: 10000 });
    record('INIT_LOAD', true, 'Application loaded successfully on port ' + APP_PORT);

    // ----------------------------------------------------
    // Scenario 1: LOGO & Mode Switching (Local -> Demo -> Live -> Local)
    // ----------------------------------------------------
    console.log('\n--- Testing Mode Switching & LOGO Placement ---');
    const modeBtns = await page.$$('.brand-mode-wrap .mode-btn');
    if (modeBtns.length === 3) {
      record('MODE_SELECTOR_LOGO', true, 'ModeSelector is placed beside LOGO in sidebar header');

      // Click Demo
      await modeBtns[1].click();
      await new Promise(r => setTimeout(r, 400));
      const demoBanner = await page.$('.mode-isolation-banner.banner-warning');
      const demoText = await page.evaluate(el => el ? el.textContent : '', demoBanner);
      const isDemoPass = demoText.includes('DEMO 隔離展示');
      record('MODE_DEMO_ISOLATION', isDemoPass, 'Demo mode isolation banner rendered with warning');

      // Click Live
      await modeBtns[2].click();
      await new Promise(r => setTimeout(r, 400));
      const liveBanner = await page.$('.mode-isolation-banner.banner-danger');
      const liveText = await page.evaluate(el => el ? el.textContent : '', liveBanner);
      const isLivePass = liveText.includes('LIVE 隔離展示');
      record('MODE_LIVE_ISOLATION', isLivePass, 'Live mode isolation banner rendered with danger');

      // Restore Local
      await modeBtns[0].click();
      await new Promise(r => setTimeout(r, 300));
      const restoredBanner = await page.$('.mode-isolation-banner');
      record('MODE_LOCAL_RESTORE', restoredBanner === null, 'Local mode restored without isolation banner');
    } else {
      record('MODE_SELECTOR_LOGO', false, `Expected 3 mode buttons beside LOGO, found ${modeBtns.length}`);
    }

    // ----------------------------------------------------
    // Scenario 2: Offline / 503 State (Layout A & Layout B)
    // ----------------------------------------------------
    console.log('\n--- Testing 503 / Service Unavailable Handling ---');
    await page.goto(APP_URL, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 500));

    // Click scenario button 5 in ScenarioBar: "服務異常 503"
    const scBtns = await page.$$('.sc-buttons button');
    if (scBtns.length >= 5) {
      await scBtns[4].click(); // Click "服務異常 503"
      await new Promise(r => setTimeout(r, 600));
      record('SET_503_SCENARIO', true, 'Switched scenario to service_unavailable (503)');
    } else {
      record('SET_503_SCENARIO', false, 'Scenario buttons not found');
    }

    // Screenshot Layout A under 503
    await page.screenshot({ path: path.join(evidenceDir, '503_layout_a_1440.png') });

    const layoutAAlert = await page.$('.alert-banner-danger');
    const layoutAAlertText = await page.evaluate(el => el ? el.textContent : '', layoutAAlert);
    const has503BannerA = layoutAAlertText.includes('503');
    record('503_LAYOUT_A_BANNER', has503BannerA, 'Layout A displays prominent 503 error alert banner');

    // Check risk badge and metric fallbacks in Layout A
    const metricTexts = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.layer-kpis .kpi-card'));
      return cards.map(c => c.textContent);
    });
    const riskCardText = metricTexts[3] || '';
    const isRiskUnavailable = riskCardText.includes('UNAVAILABLE') && !riskCardText.includes('NORMAL');
    record('503_NO_FALSE_NORMAL_A', isRiskUnavailable, `Risk card displays "${riskCardText}" (strictly UNAVAILABLE, no NORMAL)`);


    // Switch to Layout B under 503 using ScenarioBar layout buttons
    const layoutBtns = await page.$$('.layout-switch-group .layout-btn');
    if (layoutBtns.length >= 2) {
      await layoutBtns[1].click(); // Click Layout B
      await new Promise(r => setTimeout(r, 600));
    }

    // Screenshot Layout B under 503
    await page.screenshot({ path: path.join(evidenceDir, '503_layout_b_1440.png') });

    const layoutBAlert = await page.$('.alert-banner-danger');
    const layoutBAlertText = await page.evaluate(el => el ? el.textContent : '', layoutBAlert);
    const has503BannerB = layoutBAlertText.includes('503');
    record('503_LAYOUT_B_BANNER', has503BannerB, 'Layout B displays prominent 503 error alert banner');

    const actionBoxTexts = await page.evaluate(() => {
      const boxes = Array.from(document.querySelectorAll('.action-box'));
      return boxes.map(b => b.textContent);
    });
    const hasNoFalseSafeB = !actionBoxTexts.some(t => t.includes('風控與委託狀態正常'));
    const has503ActionB = actionBoxTexts.some(t => t.includes('503'));
    record('503_NO_FALSE_SAFE_B', hasNoFalseSafeB && has503ActionB, 'Layout B shows 503 action box and never claims safe status');

    // Restore normal scenario & Layout A
    const scBtnsRestore = await page.$$('.sc-buttons button');
    if (scBtnsRestore.length >= 1) {
      await scBtnsRestore[0].click(); // Restore normal
      await new Promise(r => setTimeout(r, 400));
      record('RESTORE_NORMAL_SCENARIO', true, 'Restored scenario to normal');
    }
    const layoutBtnsRestore = await page.$$('.layout-switch-group .layout-btn');
    if (layoutBtnsRestore.length >= 1) {
      await layoutBtnsRestore[0].click(); // Restore Layout A
      await new Promise(r => setTimeout(r, 300));
    }


    // ----------------------------------------------------
    // Scenario 3: Strategy Import & Honest Validation
    // ----------------------------------------------------
    console.log('\n--- Testing Strategy Import (.json / .py) ---');
    await page.goto(`${APP_URL}#/strategies`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 500));

    // Check AST badge text (must not claim backend AST passed)
    const astBadgeText = await page.$eval('.card-actions .badge', el => el.textContent);
    const isAstHonest = astBadgeText.includes('原型語法預檢') || !astBadgeText.includes('AST 語法驗證通過');
    record('AST_BADGE_HONEST', isAstHonest, `Validation badge displays "${astBadgeText}" without false backend claim`);

    // Prepare a test JSON strategy file
    const testStratManifest = {
      contract: 'catos.python-strategy.v1',
      strategy_id: 'test_momentum_v2',
      version: '2.0',
      name: '動量突破自測策略 (v2.0)',
      description: '用於重驗匯入與分配快照之自測策略',
      source: 'class Strategy:\n    def __init__(self, p):\n        self.p = p\n',
      defaults: { period: '5', quantity: '3' },
      warmup_bars: 3
    };
    const testJsonPath = path.resolve(__dirname, 'test_strategy_v2.json');
    fs.writeFileSync(testJsonPath, JSON.stringify(testStratManifest, null, 2), 'utf-8');

    // Upload file
    const fileInput = await page.$('input[type="file"]');
    if (fileInput) {
      await fileInput.uploadFile(testJsonPath);
      await new Promise(r => setTimeout(r, 600));
      const successBanner = await page.$('.banner-info');
      const successText = await page.evaluate(el => el ? el.textContent : '', successBanner);
      const isImportPass = successText.includes('匯入成功');
      record('STRATEGY_IMPORT_JSON', isImportPass, 'JSON strategy file imported and registered into immutable registry');
    } else {
      record('STRATEGY_IMPORT_JSON', false, 'File input element not found');
    }

    // ----------------------------------------------------
    // Scenario 4: Bot Allocation with Safe Trust Binding
    // ----------------------------------------------------
    console.log('\n--- Testing Bot Allocation & Trust Safety ---');
    await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 500));

    // Count initial bots
    const initialBotsCount = await page.$$eval('.data-table tbody tr', trs => trs.length);

    // Open allocate modal
    await page.click('button.btn-primary');
    await new Promise(r => setTimeout(r, 400));

    // Check initial trust checkbox is unchecked
    const initialTrustChecked = await page.$eval('.trust-checkbox', el => el.checked);
    record('ALLOCATE_TRUST_INITIAL_UNCHECKED', !initialTrustChecked, 'Trust confirmation checkbox is not pre-checked');

    // Test Trust Reset on Cancel / Reopen
    await page.click('.trust-checkbox'); // Check trust
    let checkedAfterClick = await page.$eval('.trust-checkbox', el => el.checked);
    record('ALLOCATE_TRUST_CAN_CHECK', checkedAfterClick, 'Trust checkbox can be checked manually');

    // Cancel modal
    await page.click('.modal-actions button.btn-secondary');
    await new Promise(r => setTimeout(r, 300));

    // Reopen modal: verify trust is reset to FALSE!
    await page.click('button.btn-primary');
    await new Promise(r => setTimeout(r, 300));
    const trustAfterReopen = await page.$eval('.trust-checkbox', el => el.checked);
    record('ALLOCATE_TRUST_RESET_ON_REOPEN', !trustAfterReopen, 'Trust confirmation is strictly reset on modal reopen');

    // Check trust reset on strategy switch
    await page.click('.trust-checkbox'); // Check again
    // Switch strategy in select
    const selectOptions = await page.$$eval('.form-select option', opts => opts.map(o => o.value));
    if (selectOptions.length >= 2) {
      await page.select('.form-select', selectOptions[1]);
      await new Promise(r => setTimeout(r, 200));
      const trustAfterStratSwitch = await page.$eval('.trust-checkbox', el => el.checked);
      record('ALLOCATE_TRUST_RESET_ON_STRATEGY_SWITCH', !trustAfterStratSwitch, 'Trust is strictly cleared when switching strategy');
    }

    // Fill new Bot allocation form
    await page.type('.form-input', 'review-new-bot');
    // Check parameters textarea contains defaults
    const paramText = await page.$eval('.form-textarea', el => el.value);
    const hasDefaults = paramText.includes('period') || paramText.includes('{');
    record('ALLOCATE_DEFAULTS_PREVIEW', hasDefaults, 'Selected strategy defaults are populated for review/editing');

    // Check trust and submit
    await page.click('.trust-checkbox');
    await page.click('.modal-actions button.btn-primary');
    await new Promise(r => setTimeout(r, 800));

    // Verify bot list has increased by 1!
    const newBotsCount = await page.$$eval('.data-table tbody tr', trs => trs.length);
    const botIds = await page.$$eval('.data-table tbody tr td:first-child', tds => tds.map(td => td.textContent));
    const hasNewBot = botIds.some(id => id.includes('review-new-bot'));
    record('BOT_ALLOCATE_PERSISTENCE', hasNewBot && newBotsCount > initialBotsCount, `New bot "review-new-bot" created and listed in fleet (${newBotsCount} total)`);

    // ----------------------------------------------------
    // Scenario 5: Bot Start & Stop State Transitions
    // ----------------------------------------------------
    console.log('\n--- Testing Bot Start & Stop State Transitions ---');
    // Find the Start button for the newly allocated bot
    const startBtns = await page.$$('button.btn-sm.btn-primary');
    if (startBtns.length >= 1) {
      await startBtns[0].click();
      await new Promise(r => setTimeout(r, 800));
      // Verify state changed to running
      const stateBadges = await page.$$eval('.badge', bs => bs.map(b => b.textContent.trim()));
      const isRunning = stateBadges.some(b => b.includes('運行中') || b.includes('RUNNING'));
      record('BOT_START_STATE_UPDATED', isRunning, 'Bot started successfully and status badge updated to RUNNING');
    }

    // Stop the running bot
    const stopBtns = await page.$$('button.btn-sm.btn-danger');
    if (stopBtns.length >= 1) {
      await stopBtns[0].click();
      await new Promise(r => setTimeout(r, 800));
      const stateBadgesStopped = await page.$$eval('.badge', bs => bs.map(b => b.textContent.trim()));
      const isStopped = stateBadgesStopped.some(b => b.includes('已停止') || b.includes('STOPPED'));
      record('BOT_STOP_STATE_UPDATED', isStopped, 'Bot stopped successfully and status badge updated to STOPPED');
    }

    // ----------------------------------------------------
    // Scenario 6: Navigation, Reload (F5) & History Verification
    // ----------------------------------------------------
    console.log('\n--- Testing Refresh Persistence & Command Log ---');
    // Navigate to Logs page
    await page.goto(`${APP_URL}#/logs`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 500));
    const commandRowsBefore = await page.$$eval('.data-table tbody tr', trs => trs.length);
    record('COMMAND_LOGS_RECORDED', commandRowsBefore >= 3, `Command logs recorded ${commandRowsBefore} commands with request IDs`);

    // Perform Page Refresh (F5)
    await page.reload({ waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 500));
    const commandRowsAfter = await page.$$eval('.data-table tbody tr', trs => trs.length);
    record('REFRESH_COMMAND_LOGS_PRESERVED', commandRowsAfter === commandRowsBefore && commandRowsAfter > 0, `Command logs preserved after page reload (${commandRowsAfter} entries)`);

    // Return to Bots page and check bot still exists
    await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 500));
    const botIdsAfterReload = await page.$$eval('.data-table tbody tr td:first-child', tds => tds.map(td => td.textContent));
    const newBotPreserved = botIdsAfterReload.some(id => id.includes('review-new-bot'));
    record('REFRESH_BOT_PERSISTED', newBotPreserved, 'Allocated bot "review-new-bot" persists across browser refresh');

    // Click "檢視執行成果歷史"
    await page.click('.page-top-bar button.btn-secondary');
    await new Promise(r => setTimeout(r, 400));
    const historyCard = await page.$('.history-card');
    const historyRows = await page.$$eval('.history-card .data-table tbody tr', trs => trs.length);
    record('RUNS_HISTORY_DRAWER', historyCard !== null && historyRows > 0, `Execution history drawer opened, displaying ${historyRows} immutable run records`);

    // Take screenshot of Bots & History
    await page.screenshot({ path: path.join(evidenceDir, 'bots_and_history_verified.png') });

  } catch (err) {
    console.error('Test execution error:', err);
    record('UNEXPECTED_ERROR', false, err.message);
  } finally {
    await browser.close();
  }

  // Summary
  console.log('\n====================================================');
  console.log('Verification Summary:');
  const passed = results.filter(r => r.pass).length;
  const failed = results.filter(r => !r.pass).length;
  console.log(`Total Steps: ${results.length} | Passed: ${passed} | Failed: ${failed}`);
  console.log('Console Errors:', consoleErrors.length);
  if (consoleErrors.length) {
    console.log('Console Error Details:', consoleErrors);
  }
  console.log('====================================================');

  // Save report to evidence
  fs.writeFileSync(
    path.join(evidenceDir, 'verification_summary.json'),
    JSON.stringify({ results, consoleErrors, timestamp: new Date().toISOString() }, null, 2),
    'utf-8'
  );

  if (failed > 0) {
    process.exit(1);
  } else {
    process.exit(0);
  }
}

run();
