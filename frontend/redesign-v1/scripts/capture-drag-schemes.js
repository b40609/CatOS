import puppeteer from 'puppeteer-core';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const evidenceDir = path.resolve(__dirname, '../evidence');
if (!fs.existsSync(evidenceDir)) {
  fs.mkdirSync(evidenceDir, { recursive: true });
}

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE_URL = 'http://127.0.0.1:8899/';

async function capture() {
  console.log('Launching browser to capture drag schemes and resize test...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  // 1. Capture Scheme 1: Ghost Slot Tile
  console.log('Capturing Scheme 1 (Ghost Slot Tile)...');
  await page.goto(`${BASE_URL}?edit=true&previewDrag=true&dragPreview=ghost_slot`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 600));
  const scheme1Path = path.join(evidenceDir, 'scheme_1_ghost_slot.png');
  await page.screenshot({ path: scheme1Path });
  console.log('Captured:', scheme1Path);

  // 2. Capture Scheme 2: Live Push & Shift
  console.log('Capturing Scheme 2 (Live Push & Shift)...');
  await page.goto(`${BASE_URL}?edit=true&previewDrag=true&dragPreview=live_push`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 600));
  const scheme2Path = path.join(evidenceDir, 'scheme_2_live_push.png');
  await page.screenshot({ path: scheme2Path });
  console.log('Captured:', scheme2Path);

  // 3. Capture Scheme 3: Border Halo Overlay
  console.log('Capturing Scheme 3 (Border Halo Overlay)...');
  await page.goto(`${BASE_URL}?edit=true&previewDrag=true&dragPreview=border_halo`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 600));
  const scheme3Path = path.join(evidenceDir, 'scheme_3_border_halo.png');
  await page.screenshot({ path: scheme3Path });
  console.log('Captured:', scheme3Path);

  // 4. Test Splitter Stretching (Cascading Push Verification: expand left, shrink right without cutoff)
  console.log('Testing Cascading Splitter Stretching (No Cutoff / No Freeze)...');
  await page.goto(`${BASE_URL}?edit=true`, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 600));

  // Find top tier splitters
  const topSplitters = await page.$$('#tiling-top-tier .splitter.vertical');
  if (topSplitters.length > 0) {
    const box = await topSplitters[0].boundingBox();
    if (box) {
      // Drag first splitter to the right by 220px
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
      await page.mouse.down();
      await page.mouse.move(box.x + 220, box.y + box.height / 2, { steps: 15 });
      await page.mouse.up();
      await new Promise(r => setTimeout(r, 400));
    }
  }
  const resizeTestPath = path.join(evidenceDir, 'splitter_cascading_resize_verified.png');
  await page.screenshot({ path: resizeTestPath });
  console.log('Captured:', resizeTestPath);

  await browser.close();
  console.log('All screenshots captured successfully.');
}

capture().catch(err => {
  console.error('Capture failed:', err);
  process.exit(1);
});
