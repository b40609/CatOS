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

const verificationReport = {
  timestamp: new Date().toISOString(),
  targetUrl: APP_URL,
  viewport: { width: 1440, height: 900 },
  pagesChecked: [],
  issuesVerification: {},
  failedRequests: [],
  consoleErrors: []
};

async function inspect() {
  console.log('Connecting Chrome to inspect:', APP_URL);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport(verificationReport.viewport);

  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.error('[Browser Console Error]:', msg.text());
      verificationReport.consoleErrors.push(msg.text());
    }
  });

  page.on('requestfailed', req => {
    console.warn('[Request Failed]:', req.url(), req.failure()?.errorText);
    verificationReport.failedRequests.push({
      url: req.url(),
      error: req.failure()?.errorText
    });
  });

  // 1. Visit each page and capture screenshot
  const pages = [
    { route: '#/', name: 'dashboard', title: '系統總覽' },
    { route: '#/strategies', name: 'strategies', title: '策略中心' },
    { route: '#/bots', name: 'bots', title: '機器人管理' },
    { route: '#/risk', name: 'risk', title: '風控中心' },
    { route: '#/market-intel', name: 'market-intel', title: '市場情報' },
    { route: '#/logs', name: 'logs', title: '系統日誌' },
    { route: '#/settings', name: 'settings', title: '系統設定' },
    { route: '#/backtest', name: 'backtest', title: '歷史回測' },
    { route: '#/optimization', name: 'optimization', title: '參數優化' }
  ];

  for (const p of pages) {
    const fullUrl = `${APP_URL}${p.route}`;
    await page.goto(fullUrl, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 400));

    const title = await page.title();
    const docTitle = await page.evaluate(() => document.title);
    const screenshotName = `return_inspect_${p.name}_1440.png`;
    const screenshotPath = path.join(evidenceDir, screenshotName);
    await page.screenshot({ path: screenshotPath });

    verificationReport.pagesChecked.push({
      route: p.route,
      name: p.name,
      title: docTitle,
      screenshot: screenshotName,
      status: 'LOADED'
    });
    console.log(`✓ Page checked: [${p.title}] -> ${screenshotName}`);
  }

  // 2. Specific Verification Tests for Known Issues

  // A. Check Trust Reset on Reopen & Strategy Switch
  console.log('\n--- Verifying Trust Checkbox Reset Behavior ---');
  await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 400));

  // Open modal
  const openAllocateBtn = await page.$('.header-actions-group button.btn-primary');
  if (openAllocateBtn) {
    await openAllocateBtn.click();
    await new Promise(r => setTimeout(r, 300));

    // Verify initial unchecked
    let trustChecked = await page.$eval('.trust-checkbox', el => el.checked);
    const initialUnchecked = !trustChecked;

    // Check it
    await page.click('.trust-checkbox');
    trustChecked = await page.$eval('.trust-checkbox', el => el.checked);

    // Switch strategy dropdown
    const selectOptions = await page.$$eval('.form-select option', opts => opts.map(o => o.value));
    if (selectOptions.length > 1) {
      await page.select('.form-select', selectOptions[1]);
      await new Promise(r => setTimeout(r, 200));
      const trustAfterSwitch = await page.$eval('.trust-checkbox', el => el.checked);
      verificationReport.issuesVerification.trustResetOnSwitch = !trustAfterSwitch;
    } else {
      verificationReport.issuesVerification.trustResetOnSwitch = 'only_1_strategy_present';
    }

    // Close and reopen modal
    await page.click('.btn-close');
    await new Promise(r => setTimeout(r, 200));
    await openAllocateBtn.click();
    await new Promise(r => setTimeout(r, 200));
    const trustAfterReopen = await page.$eval('.trust-checkbox', el => el.checked);
    verificationReport.issuesVerification.trustResetOnReopen = !trustAfterReopen;
    verificationReport.issuesVerification.trustInitialUnchecked = initialUnchecked;

    await page.click('.btn-close');
  }

  // B. Bot Allocation & Persistence
  console.log('\n--- Verifying Bot Allocation & Persistence ---');
  await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 400));
  const initialBotCount = await page.$$eval('.data-table tbody tr', trs => trs.length);
  
  let testBotId = `test-bot-${Date.now().toString().slice(-4)}`;
  const allocateBtn2 = await page.waitForSelector('.header-actions-group button.btn-primary', { timeout: 5000 });
  if (allocateBtn2) {
    await allocateBtn2.click();
    await page.waitForSelector('.modal-box', { timeout: 5000 });
    await new Promise(r => setTimeout(r, 200));

    await page.type('.form-input', testBotId);
    await page.click('.trust-checkbox');
    await page.click('.modal-actions button.btn-primary');
    await new Promise(r => setTimeout(r, 600));

    const newBotCount = await page.$$eval('.data-table tbody tr', trs => trs.length);
    const botAdded = newBotCount === initialBotCount + 1;
    verificationReport.issuesVerification.botAllocation = {
      initialBotCount,
      newBotCount,
      botAdded,
      testBotId
    };
  }

  // C. Start and Stop Bot
  console.log('\n--- Verifying Start & Stop Bot State ---');
  // Find test bot row and click Start
  let startSuccess = false;
  let stopSuccess = false;
  const botRows = await page.$$('.data-table tbody tr');
  for (const row of botRows) {
    const text = await row.evaluate(el => el.textContent || '');
    if (text.includes(testBotId)) {
      const startBtn = await row.$('button.btn-primary');
      if (startBtn) {
        await startBtn.click();
        await new Promise(r => setTimeout(r, 500));
        startSuccess = true;
      }
      break;
    }
  }

  // Verify status updated to running
  await new Promise(r => setTimeout(r, 300));
  for (const row of await page.$$('.data-table tbody tr')) {
    const text = await row.evaluate(el => el.textContent || '');
    if (text.includes(testBotId)) {
      const isRunning = text.includes('RUNNING') || text.includes('運行中');
      verificationReport.issuesVerification.botStartRunning = isRunning;
      const stopBtn = await row.$('button.btn-danger');
      if (stopBtn) {
        await stopBtn.click();
        await new Promise(r => setTimeout(r, 500));
        stopSuccess = true;
      }
      break;
    }
  }

  // Verify status updated to stopped with retained position
  await new Promise(r => setTimeout(r, 300));
  for (const row of await page.$$('.data-table tbody tr')) {
    const text = await row.evaluate(el => el.textContent || '');
    if (text.includes(testBotId)) {
      const isStopped = text.includes('STOPPED') || text.includes('已停止');
      verificationReport.issuesVerification.botStopStopped = isStopped;
      break;
    }
  }

  // D. Refresh Page and Check Persistence
  console.log('\n--- Verifying Refresh Persistence ---');
  await page.reload({ waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 500));
  const botPersistedAfterReload = await page.evaluate(id => {
    return document.body.innerText.includes(id);
  }, testBotId);
  verificationReport.issuesVerification.botPersistedAfterRefresh = botPersistedAfterReload;

  // E. Check Command Logs Preservation
  console.log('\n--- Verifying Command Logs Preservation ---');
  await page.goto(`${APP_URL}#/logs`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 400));
  const commandCount = await page.$$eval('.command-card .data-table tbody tr', trs => trs.length);
  verificationReport.issuesVerification.commandLogsPreserved = commandCount > 0;
  verificationReport.issuesVerification.commandCount = commandCount;

  // F. Execution Results History Drawer
  console.log('\n--- Verifying History Drawer ---');
  await page.goto(`${APP_URL}#/bots`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 400));
  const historyToggleBtn = await page.$('.header-actions-group button.btn-secondary');
  let historyDrawerOpened = false;
  let runsCount = 0;
  if (historyToggleBtn) {
    await historyToggleBtn.click();
    await new Promise(r => setTimeout(r, 300));
    const historyCard = await page.$('.history-card');
    historyDrawerOpened = !!historyCard;
    if (historyCard) {
      runsCount = await historyCard.$$eval('.data-table tbody tr', trs => trs.length);
    }
  }
  verificationReport.issuesVerification.runsHistory = {
    drawerOpened: historyDrawerOpened,
    runsCount
  };

  // G. Strategy Import Input
  console.log('\n--- Verifying Strategy Import Handler ---');
  await page.goto(`${APP_URL}#/strategies`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 400));
  const fileInputExists = await page.$('input[type="file"][accept*=".py"]') !== null;
  const astBadgeText = await page.$eval('.strategy-detail-col .card-actions', el => el.textContent?.trim() || '');
  verificationReport.issuesVerification.strategyImport = {
    fileInputConfigured: fileInputExists,
    astBadgeHonest: astBadgeText.includes('示意') || astBadgeText.includes('原型')
  };

  // H. 503 Unavailable Handling
  console.log('\n--- Verifying 503 Unavailable Handling ---');
  await page.goto(`${APP_URL}#/`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 400));
  const scenario503Btn = await page.$('.sc-buttons button:nth-child(5)');
  if (scenario503Btn) {
    await scenario503Btn.click();
    await new Promise(r => setTimeout(r, 600));
    const is503Banner = await page.$('.offline-banner') !== null || (await page.evaluate(() => document.body.innerText.includes('503')));
    const bodyText = await page.evaluate(() => document.body.innerText);
    const noFalseNormal = !bodyText.includes('正常 NORMAL') && bodyText.includes('UNAVAILABLE');
    verificationReport.issuesVerification.serviceUnavailable503 = {
      is503Banner,
      noFalseNormal,
      displayedUnavailable: bodyText.includes('UNAVAILABLE')
    };

    // Restore scenario to normal
    const normalBtn = await page.$('.sc-buttons button:first-child');
    if (normalBtn) await normalBtn.click();
  }

  await browser.close();

  // Save report
  const reportPath = path.join(evidenceDir, 'return_inspection_summary.json');
  fs.writeFileSync(reportPath, JSON.stringify(verificationReport, null, 2), 'utf-8');
  console.log('\nVerification completed. Report saved to:', reportPath);
}

inspect().catch(err => {
  console.error('Inspection failed:', err);
  process.exit(1);
});
