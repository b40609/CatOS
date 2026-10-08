import puppeteer from 'puppeteer-core';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const evidenceDir = path.resolve(__dirname, '../evidence/timeline-enhancement-20261005');
fs.mkdirSync(evidenceDir, { recursive: true });

const CHROME_PATH = process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = process.env.APP_URL || 'http://127.0.0.1:8910/';

function assert(condition, message) {
  if (!condition) {
    throw new Error(`Assertion Failed: ${message}`);
  }
}

async function verifyAllVariants() {
  console.log(`=== Starting CatOS Audit Timeline A/B/C Multi-Variant Verification ===`);
  console.log(`Target: ${APP_URL}`);
  console.log(`Evidence Out: ${evidenceDir}`);

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1600,1000']
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1600, height: 1000 });
    await page.goto(APP_URL, { waitUntil: 'networkidle0', timeout: 15000 });

    await page.waitForSelector('.audit-timeline-root', { timeout: 8000 });

    // ==========================================
    // 1. Variant A (時序骨架軸線)
    // ==========================================
    console.log('[Variant A] Verifying Spine Timeline...');
    const btnA = await page.$('.btn-style-pill:nth-child(1)');
    if (btnA) await btnA.click();
    await new Promise(r => setTimeout(r, 400));

    await page.waitForSelector('.timeline-track', { timeout: 3000 });
    await page.screenshot({ path: path.join(evidenceDir, 'variant-A-spine-overview.png') });
    console.log('Saved variant-A-spine-overview.png');

    // Expand first item in Variant A
    const firstItemA = await page.$('.timeline-item');
    if (firstItemA) {
      await firstItemA.click();
      await new Promise(r => setTimeout(r, 400));
      await page.waitForSelector('.card-details-panel', { timeout: 3000 });
      await page.screenshot({ path: path.join(evidenceDir, 'variant-A-spine-expanded.png') });
      console.log('Saved variant-A-spine-expanded.png');
      // Collapse back
      await firstItemA.click();
      await new Promise(r => setTimeout(r, 300));
    }

    // ==========================================
    // 2. Variant B (極簡高密度終端日誌流)
    // ==========================================
    console.log('[Variant B] Verifying Terminal Log Stream...');
    const btnB = await page.$('.btn-style-pill:nth-child(2)');
    if (btnB) await btnB.click();
    await new Promise(r => setTimeout(r, 500));

    await page.waitForSelector('.terminal-log-container', { timeout: 3000 });
    await page.screenshot({ path: path.join(evidenceDir, 'variant-B-terminal-stream.png') });
    console.log('Saved variant-B-terminal-stream.png');

    // Expand first item in Variant B (Inspector)
    const firstItemB = await page.$('.terminal-row');
    if (firstItemB) {
      await firstItemB.click();
      await new Promise(r => setTimeout(r, 400));
      await page.waitForSelector('.terminal-inspector', { timeout: 3000 });
      await page.screenshot({ path: path.join(evidenceDir, 'variant-B-terminal-inspected.png') });
      console.log('Saved variant-B-terminal-inspected.png');
      // Collapse back
      await firstItemB.click();
      await new Promise(r => setTimeout(r, 300));
    }

    // ==========================================
    // 3. Variant C (模組獨立卡片徽章流)
    // ==========================================
    console.log('[Variant C] Verifying Modular Activity Cards...');
    const btnC = await page.$('.btn-style-pill:nth-child(3)');
    if (btnC) await btnC.click();
    await new Promise(r => setTimeout(r, 500));

    await page.waitForSelector('.modular-cards-container', { timeout: 3000 });
    await page.screenshot({ path: path.join(evidenceDir, 'variant-C-modular-cards.png') });
    console.log('Saved variant-C-modular-cards.png');

    // Expand first item in Variant C
    const firstItemC = await page.$('.mod-card');
    if (firstItemC) {
      await firstItemC.click();
      await new Promise(r => setTimeout(r, 400));
      await page.waitForSelector('.mod-details-box', { timeout: 3000 });
      await page.screenshot({ path: path.join(evidenceDir, 'variant-C-modular-expanded.png') });
      console.log('Saved variant-C-modular-expanded.png');
    }

    console.log('=== All 3 Variants (A, B, C) Verified and Captured Successfully! ===');
  } finally {
    await browser.close();
  }
}

verifyAllVariants().catch((err) => {
  console.error('Multi-Variant Verification FAILED:', err);
  process.exit(1);
});
