import puppeteer from 'puppeteer-core';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const evidenceDir = path.resolve(__dirname, '../evidence');
const artifactDir = 'C:\\Users\\kai\\.gemini\\antigravity-ide\\brain\\ce1f65a3-67d9-402c-b4d8-599f56b25cf8';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = 'http://127.0.0.1:8899/';

async function captureUnifiedFinal() {
  console.log('Capturing Scheme A Unified Topbar Final across all pages from:', APP_URL);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  const pagesToCapture = [
    { route: '#/', name: 'dashboard', title: '系統總覽' },
    { route: '#/strategies', name: 'strategies', title: '策略中心' },
    { route: '#/backtest', name: 'backtest', title: '歷史回測' },
    { route: '#/optimization', name: 'optimization', title: '參數優化' },
    { route: '#/bots', name: 'bots', title: '機器人管理' },
    { route: '#/risk', name: 'risk', title: '風控中心' },
    { route: '#/market-intel', name: 'market_intel', title: '市場情報' },
    { route: '#/logs', name: 'logs', title: '系統日誌' },
    { route: '#/settings', name: 'settings', title: '設定中心' }
  ];

  for (const p of pagesToCapture) {
    console.log(`\nCapturing [${p.title}] -> ${p.route}`);
    await page.goto(`${APP_URL}${p.route}`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 500));

    // Verify header title
    const headerTitle = await page.$eval('.header-title', el => el.textContent?.trim());
    console.log(`  Header Title rendered: "${headerTitle}"`);

    // Verify absence of redundant page-top-bar
    const inPageTopBarCount = await page.$$eval('.page-top-bar', els => els.length);
    console.log(`  In-page .page-top-bar count: ${inPageTopBarCount} (Expected: 0)`);

    // Verify teleport action container has content if applicable
    const actionsHtml = await page.$eval('#header-page-actions', el => el.innerHTML.trim());
    console.log(`  Header Actions present: ${actionsHtml.length > 0}`);

    const fileName = `unified_final_${p.name}.png`;
    const outFile = path.join(evidenceDir, fileName);
    await page.screenshot({ path: outFile });
    console.log(`  Saved to evidence: ${fileName}`);

    // Also copy to brain artifact dir for immediate review
    try {
      const artifactOut = path.join(artifactDir, fileName);
      fs.copyFileSync(outFile, artifactOut);
      console.log(`  Copied to artifact dir: ${artifactOut}`);
    } catch (e) {
      console.warn(`  Failed to copy to artifact dir:`, e.message);
    }
  }

  await browser.close();
  console.log('\nAll Scheme A Unified Topbar final screenshots successfully captured!');
}

captureUnifiedFinal().catch(err => {
  console.error('Failed to capture unified final:', err);
  process.exit(1);
});
