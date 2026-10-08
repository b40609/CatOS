import puppeteer from 'puppeteer-core';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const evidenceDir = path.resolve(__dirname, '../evidence/ux-audit');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = 'http://127.0.0.1:8899/';

async function testResizer() {
  console.log('Testing Sidebar Style D & Resizer interaction...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  // 1. Clear localStorage so default style D is applied
  await page.goto(APP_URL, { waitUntil: 'networkidle0' });
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 600));

  // Check sidebar style and initial width
  const initialWidth = await page.evaluate(() => {
    const aside = document.querySelector('.app-sidebar');
    return {
      styleClass: aside.className,
      width: aside.getBoundingClientRect().width,
      hasPortfolioCard: !!document.querySelector('.sidebar-portfolio-card')
    };
  });
  console.log('Initial State:', initialWidth);

  // Take screenshot of default Style D
  await page.screenshot({ path: path.join(evidenceDir, 'sidebar_d_default.png') });
  console.log('Saved sidebar_d_default.png');

  // 2. Test Dragging Resizer to Expand (Drag rightwards by +80px)
  const resizerBox = await page.evaluate(() => {
    const resizer = document.querySelector('.sidebar-resizer');
    const rect = resizer.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
  });
  console.log('Resizer coords:', resizerBox);

  await page.mouse.move(resizerBox.x, resizerBox.y);
  await new Promise(r => setTimeout(r, 200));
  await page.mouse.down();
  await page.mouse.move(resizerBox.x + 80, resizerBox.y, { steps: 10 });
  await page.mouse.up();
  await new Promise(r => setTimeout(r, 400));

  const expandedWidth = await page.evaluate(() => {
    const aside = document.querySelector('.app-sidebar');
    return aside.getBoundingClientRect().width;
  });
  console.log('Expanded Width after drag (+80px):', expandedWidth);

  await page.screenshot({ path: path.join(evidenceDir, 'sidebar_d_dragged.png') });
  console.log('Saved sidebar_d_dragged.png');

  // 3. Test Double Click to Reset
  await page.evaluate(() => {
    const resizer = document.querySelector('.sidebar-resizer');
    resizer.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }));
  });
  await new Promise(r => setTimeout(r, 400));

  const resetWidth = await page.evaluate(() => {
    const aside = document.querySelector('.app-sidebar');
    return aside.getBoundingClientRect().width;
  });
  console.log('Reset Width after double-click:', resetWidth);

  await page.screenshot({ path: path.join(evidenceDir, 'sidebar_d_reset.png') });
  console.log('Saved sidebar_d_reset.png');

  // 4. Test Dragging Left to Collapse (Snap to Folded Dock)
  console.log('4. Testing Drag Left to Collapse (< 135px)...');
  await page.mouse.move(245, 450);
  await new Promise(r => setTimeout(r, 100));
  await page.mouse.down();
  await page.mouse.move(110, 450, { steps: 10 });
  await page.mouse.up();
  await new Promise(r => setTimeout(r, 400));

  const collapsedState = await page.evaluate(() => {
    const aside = document.querySelector('.app-sidebar');
    return {
      isFolded: aside.classList.contains('is-folded'),
      width: aside.getBoundingClientRect().width
    };
  });
  console.log('State after collapse drag:', collapsedState);
  await page.screenshot({ path: path.join(evidenceDir, 'sidebar_d_collapsed_by_drag.png') });
  console.log('Saved sidebar_d_collapsed_by_drag.png');

  // 5. Test Dragging Right from Folded Dock to Expand (> 145px)
  console.log('5. Testing Drag Right from Folded Dock to Expand...');
  await page.mouse.move(64, 450);
  await new Promise(r => setTimeout(r, 100));
  await page.mouse.down();
  await page.mouse.move(260, 450, { steps: 10 });
  await page.mouse.up();
  await new Promise(r => setTimeout(r, 400));

  const reExpandedState = await page.evaluate(() => {
    const aside = document.querySelector('.app-sidebar');
    return {
      isFolded: aside.classList.contains('is-folded'),
      width: aside.getBoundingClientRect().width
    };
  });
  console.log('State after re-expand drag:', reExpandedState);
  await page.screenshot({ path: path.join(evidenceDir, 'sidebar_d_reexpanded.png') });
  console.log('Saved sidebar_d_reexpanded.png');

  await browser.close();
  console.log('All tests completed successfully!');
}

testResizer().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
