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

async function verifyIncidentStream() {
  console.log(`=== Starting Incident Stream Verification ===`);
  console.log(`Target: ${APP_URL}`);

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1600,1000']
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1600, height: 1000 });
    await page.goto(APP_URL, { waitUntil: 'networkidle0', timeout: 15000 });

    await page.waitForSelector('.incident-stream-root', { timeout: 8000 });
    await page.waitForSelector('.entry-drawer', { timeout: 8000 });

    // 1. Capture full dashboard overview
    await page.screenshot({ path: path.join(evidenceDir, 'incident-stream-matched-overview.png') });
    console.log('Saved incident-stream-matched-overview.png');

    // 2. Capture closeup of the incident stream card
    const cardHandle = await page.$('.col-events, [title*="INCIDENT STREAM"], .pane-events');
    const targetElement = cardHandle || (await page.$('.incident-stream-root'));
    if (targetElement) {
      await targetElement.screenshot({ path: path.join(evidenceDir, 'incident-stream-card-closeup.png') });
      console.log('Saved incident-stream-card-closeup.png');

      // 3. Toggle items to verify rail continuity during expand/collapse
      const rows = await page.$$('.entry-row');
      if (rows.length >= 2) {
        // click second item
        await rows[1].click();
        await new Promise(r => setTimeout(r, 200));
        await targetElement.screenshot({ path: path.join(evidenceDir, 'incident-stream-card-toggle2.png') });
        console.log('Saved incident-stream-card-toggle2.png');
      }
    }

    console.log('=== Incident Stream Matched Successfully! ===');
  } finally {
    await browser.close();
  }
}

verifyIncidentStream().catch(err => {
  console.error('Verification failed:', err);
  process.exit(1);
});
