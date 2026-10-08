import puppeteer from 'puppeteer-core';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const evidenceDir = path.resolve(__dirname, '../evidence');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = 'http://127.0.0.1:8899/?edit=true';

async function testDragToLeft() {
  console.log('Testing Drag To Left for any jumping-to-rightmost anomaly...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto(APP_URL, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 600));

  // Find 'donut' pane (保證金與曝險配置) in Upper Tier
  const donutHeader = await page.$('#pane-donut .toolbar-drag-grip');
  if (!donutHeader) {
    throw new Error('Could not find #pane-donut header');
  }

  const box = await donutHeader.boundingBox();
  if (!box) throw new Error('Could not get bounding box for donut header');

  const startX = box.x + box.width / 2;
  const startY = box.y + box.height / 2;

  // Move to donut header and press down
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  await new Promise(r => setTimeout(r, 100));

  // Drag left step-by-step from startX towards x = 260px (top left)
  const steps = 30;
  const anomalies = [];

  for (let i = 1; i <= steps; i++) {
    const curX = startX - (startX - 260) * (i / steps);
    const curY = startY - 100 * (i / steps); // slightly moving towards top tier / left
    await page.mouse.move(curX, curY);
    await new Promise(r => setTimeout(r, 30));

    // Evaluate dropTargetInfo inside Vue component
    const dropInfo = await page.evaluate(() => {
      // @ts-ignore
      const comp = document.querySelector('.workspace-hybrid');
      // check DOM for ghost-slot-tile position
      const ghost = document.querySelector('.ghost-slot-tile');
      const parentTier = ghost ? ghost.parentElement?.id : null;
      // Get all child elements in top tier
      const topTier = document.getElementById('tiling-top-tier');
      let ghostPosInTop = -1;
      if (topTier && ghost) {
        const children = Array.from(topTier.children);
        ghostPosInTop = children.indexOf(ghost);
      }
      return { parentTier, ghostPosInTop };
    });

    // If curX is far to the left (e.g. curX < 600), but ghost is placed at the end of tier, record anomaly
    if (curX < 550 && dropInfo.ghostPosInTop > 4) {
      anomalies.push({ step: i, curX, curY, dropInfo });
    }
  }

  // Screenshot while holding at the far left
  const screenshotPath = path.join(evidenceDir, 'drag_to_left_verified_no_jump.png');
  await page.screenshot({ path: screenshotPath });
  console.log('Captured screenshot while holding at left:', screenshotPath);

  await page.mouse.up();
  await browser.close();

  console.log(`Drag test completed. Anomalies detected: ${anomalies.length}`);
  if (anomalies.length > 0) {
    console.error('Anomalies detail:', JSON.stringify(anomalies, null, 2));
    process.exit(1);
  } else {
    console.log('SUCCESS: No jumping-to-rightmost anomalies detected during full left drag!');
  }
}

testDragToLeft().catch(err => {
  console.error(err);
  process.exit(1);
});
