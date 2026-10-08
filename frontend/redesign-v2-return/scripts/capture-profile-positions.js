import puppeteer from 'puppeteer-core';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const outDir = path.resolve(__dirname, '../evidence/profile-positions');
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = 'http://127.0.0.1:8899/';

async function run() {
  console.log('🚀 Starting User Profile Positions Verification...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

  await page.goto(APP_URL, { waitUntil: 'networkidle0' });
  await new Promise(r => setTimeout(r, 600));

  // 1. Initial State: Both positions active (default: 'both')
  console.log('📸 1. Capturing Initial Overview (Both Positions Active)...');
  await page.screenshot({ path: path.join(outDir, '01_both_positions_overview.png'), fullPage: false });

  // 2. Open Bottom-Left Popover
  console.log('📸 2. Clicking Bottom-Left User Profile Trigger...');
  const bottomLeftBtn = await page.$('.profile-trigger-sidebar');
  if (bottomLeftBtn) {
    await bottomLeftBtn.click();
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(outDir, '02_bottom_left_popover_open.png'), fullPage: false });
  } else {
    console.error('❌ Could not find .profile-trigger-sidebar');
  }

  // 3. Click "前往「系統設定」" from Popover
  console.log('📸 3. Clicking "前往「系統設定」" inside Popover...');
  const settingsEntry = await page.$('.popover-settings-entry');
  if (settingsEntry) {
    await settingsEntry.click();
    await new Promise(r => setTimeout(r, 500));
    console.log('Current URL after click:', page.url());
    await page.screenshot({ path: path.join(outDir, '03_navigated_to_settings.png'), fullPage: false });
  } else {
    console.error('❌ Could not find .popover-settings-entry');
  }

  // 4. Test Top-Right Popover
  console.log('📸 4. Clicking Top-Right Header User Profile Trigger...');
  const topRightBtn = await page.$('.profile-trigger-header');
  if (topRightBtn) {
    await topRightBtn.click();
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(outDir, '04_top_right_popover_open.png'), fullPage: false });
    // Close it
    await page.click('.popover-close-btn');
    await new Promise(r => setTimeout(r, 300));
  } else {
    console.error('❌ Could not find .profile-trigger-header');
  }

  // 5. Switch to Option 1: Bottom-Left Only
  console.log('📸 5. Testing Option 1: Bottom-Left Only...');
  const opt1 = await page.$$('.profile-placement-card .placement-option-card');
  if (opt1.length >= 1) {
    await opt1[0].click(); // Bottom-Left
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(outDir, '05_bottom_left_only_mode.png'), fullPage: false });
  }

  // 6. Switch to Option 2: Top-Right Only
  console.log('📸 6. Testing Option 2: Top-Right Only...');
  if (opt1.length >= 2) {
    await opt1[1].click(); // Top-Right
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(outDir, '06_top_right_only_mode.png'), fullPage: false });
  }

  // 7. Reset to Option 1: Bottom-Left Only (User Finalized Choice)
  if (opt1.length >= 1) {
    await opt1[0].click(); // Bottom-Left
    await new Promise(r => setTimeout(r, 400));
  }

  // 8. Test Folded Sidebar Mode via Modern Header Toggle Button
  console.log('📸 7. Testing Folded Sidebar Mode (64px) via .sidebar-toggle-btn...');
  await page.click('.sidebar-toggle-btn');
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: path.join(outDir, '07_folded_sidebar_overview.png'), fullPage: false });

  // Open folded bottom-left popover
  const foldedTrigger = await page.$('.profile-trigger-folded');
  if (foldedTrigger) {
    await foldedTrigger.click();
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(outDir, '08_folded_sidebar_flyout_popover.png'), fullPage: false });
  }

  await browser.close();
  console.log('✅ User Profile Positions Verification Completed successfully!');
}

run().catch(err => {
  console.error('Test execution failed:', err);
  process.exit(1);
});
