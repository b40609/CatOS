import puppeteer from 'puppeteer-core';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const evidenceDir = path.resolve(__dirname, '../evidence');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = 'http://127.0.0.1:8899/?edit=true';

async function captureFinal() {
  console.log('Capturing Finalized Scheme 1 Workstation Screenshot...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  // 1. Capture clean edit mode (no style selector buttons)
  await page.goto(APP_URL, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 600));
  const cleanEditPath = path.join(evidenceDir, 'scheme_1_final_clean_guidebar.png');
  await page.screenshot({ path: cleanEditPath });
  console.log('Captured clean guidebar:', cleanEditPath);

  // 2. Capture dragging with ghost slot active
  const donutHeader = await page.$('#pane-donut .toolbar-drag-grip');
  if (donutHeader) {
    const box = await donutHeader.boundingBox();
    if (box) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await page.mouse.move(box.x - 320, box.y - 40, { steps: 10 });
      await new Promise(r => setTimeout(r, 300));
      const draggingPath = path.join(evidenceDir, 'scheme_1_final_ghost_slot_active.png');
      await page.screenshot({ path: draggingPath });
      console.log('Captured ghost slot active:', draggingPath);
      await page.mouse.up();
    }
  }

  await browser.close();
  console.log('Capture completed.');
}

captureFinal().catch(err => {
  console.error(err);
  process.exit(1);
});
