import puppeteer from 'puppeteer-core';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const evidenceDir = path.resolve(__dirname, '../evidence');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = 'http://127.0.0.1:8899/';

async function captureVariants() {
  console.log('Capturing all 4 Mode Switcher placement options from:', APP_URL);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });

  // 1. Capture Option 1: Sidebar Stack (Default)
  console.log('1. Capturing Option 1: Sidebar Stack (Linear / macOS)...');
  await page.goto(APP_URL, { waitUntil: 'networkidle0' });
  await page.waitForSelector('.sidebar-header');
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: path.join(evidenceDir, 'mode_placement_opt1_sidebar_stack.png') });
  console.log('Captured mode_placement_opt1_sidebar_stack.png');

  // Helper to navigate to Settings via user profile popover or route
  async function goToSettings() {
    const profileBtn = await page.$('.profile-trigger-sidebar') || await page.$('.profile-trigger-header');
    if (profileBtn) {
      await profileBtn.click();
      await new Promise(r => setTimeout(r, 200));
      const link = await page.$('a[href="#/settings"]');
      if (link) {
        await link.click();
        await new Promise(r => setTimeout(r, 350));
        return;
      }
    }
    await page.goto(APP_URL + '#/settings', { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 350));
  }

  // Go to Settings page
  await goToSettings();

  // 2. Select Option 2: Top Header Right
  console.log('2. Switching to Option 2: Top Header Right (OKX / TradingView)...');
  const opt2Card = (await page.$$('.placement-option-card'))[1];
  if (opt2Card) {
    await opt2Card.click();
    await new Promise(r => setTimeout(r, 350));
    // Return to dashboard to see full header layout
    await page.click('a[href="#/"]');
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(evidenceDir, 'mode_placement_opt2_top_header.png') });
    console.log('Captured mode_placement_opt2_top_header.png');
  }

  // 3. Select Option 3: Dropdown Badge beside Logo
  console.log('3. Switching to Option 3: Dropdown Badge (Raycast / Slack)...');
  await goToSettings();
  const opt3Card = (await page.$$('.placement-option-card'))[2];
  if (opt3Card) {
    await opt3Card.click();
    await new Promise(r => setTimeout(r, 350));
    await page.click('a[href="#/"]');
    await new Promise(r => setTimeout(r, 400));
    // Open the dropdown menu
    const badgeBtn = await page.$('.mode-badge-btn');
    if (badgeBtn) {
      await badgeBtn.click();
      await new Promise(r => setTimeout(r, 200));
    }
    await page.screenshot({ path: path.join(evidenceDir, 'mode_placement_opt3_dropdown_badge.png') });
    console.log('Captured mode_placement_opt3_dropdown_badge.png');
  }

  // 4. Select Option 4: Sidebar Footer Terminal Dock
  console.log('4. Switching to Option 4: Sidebar Footer Dock (Terminal Dock)...');
  await goToSettings();
  const opt4Card = (await page.$$('.placement-option-card'))[3];
  if (opt4Card) {
    await opt4Card.click();
    await new Promise(r => setTimeout(r, 350));
    await page.click('a[href="#/"]');
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(evidenceDir, 'mode_placement_opt4_sidebar_footer.png') });
    console.log('Captured mode_placement_opt4_sidebar_footer.png');
  }

  // Also capture Settings page showing the 4 options grid
  await goToSettings();
  // Restore Option 1 as recommended default
  const restoreOpt1 = (await page.$$('.placement-option-card'))[0];
  if (restoreOpt1) await restoreOpt1.click();
  await new Promise(r => setTimeout(r, 300));
  await page.screenshot({ path: path.join(evidenceDir, 'settings_mode_options_grid.png') });
  console.log('Captured settings_mode_options_grid.png');

  await browser.close();
  console.log('All 4 Mode Switcher placement captures completed successfully!');
}

captureVariants().catch(err => {
  console.error('Capture failed:', err);
  process.exit(1);
});
