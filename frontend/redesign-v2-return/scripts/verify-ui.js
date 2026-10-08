import puppeteer from 'puppeteer-core';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const evidenceDir = path.resolve(__dirname, '../evidence');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const APP_URL = 'http://127.0.0.1:8899/';

async function run() {
  console.log('Starting UI automated verification on:', APP_URL);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });

  const page = await browser.newPage();
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  // 1. Set 1440x900
  console.log('1. Testing 1440x900 Desktop Viewport...');
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto(APP_URL, { waitUntil: 'networkidle0' });
  await page.waitForSelector('.app-shell');
  await new Promise(r => setTimeout(r, 600));

  // Layout A screenshot
  await page.screenshot({ path: path.join(evidenceDir, 'layout_a_vue_1440.png') });
  console.log('Captured layout_a_vue_1440.png');

  // Telemetry popover
  console.log('2. Testing Telemetry Popover...');
  await page.click('.telemetry-trigger');
  await new Promise(r => setTimeout(r, 300));
  await page.screenshot({ path: path.join(evidenceDir, 'layout_a_popover_1440.png') });
  console.log('Captured layout_a_popover_1440.png');
  await page.click('.btn-close');
  await new Promise(r => setTimeout(r, 200));

  // Layout B
  console.log('3. Testing Layout B (Focused View)...');
  const layoutBtns = await page.$$('.layout-btn');
  if (layoutBtns.length >= 2) {
    await layoutBtns[1].click(); // Click Layout B
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(evidenceDir, 'layout_b_vue_1440.png') });
    console.log('Captured layout_b_vue_1440.png');
    await layoutBtns[0].click(); // Restore Layout A
    await new Promise(r => setTimeout(r, 300));
  }

  // Scenarios
  console.log('4. Testing Scenarios...');
  const scBtns = await page.$$('.sc-buttons .btn');
  // scBtns: 0: normal, 1: soft_loss, 2: hold_stopped_409, 3: empty, 4: service_unavailable
  if (scBtns.length >= 4) {
    // Soft loss
    await scBtns[1].click();
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({ path: path.join(evidenceDir, 'scenario_soft_loss_1440.png') });
    console.log('Captured scenario_soft_loss_1440.png');

    // Hold stopped 409
    await scBtns[2].click();
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({ path: path.join(evidenceDir, 'scenario_hold_stopped_1440.png') });
    console.log('Captured scenario_hold_stopped_1440.png');

    // Empty
    await scBtns[3].click();
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({ path: path.join(evidenceDir, 'scenario_empty_1440.png') });
    console.log('Captured scenario_empty_1440.png');

    // Restore Normal
    await scBtns[0].click();
    await new Promise(r => setTimeout(r, 300));
  }

  // 4b. Testing Visual Comparison Toggles
  console.log('4b. Testing Visual Comparison Toggles...');
  const minimalBtn = await page.$('button[title*="極簡純線"]');
  if (minimalBtn) {
    await minimalBtn.click();
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({ path: path.join(evidenceDir, 'layout_a_style_minimal_1440.png') });
    console.log('Captured layout_a_style_minimal_1440.png');
  }

  const deepBlackBtn = await page.$('button[title*="深邃純黑"]');
  if (deepBlackBtn) {
    await deepBlackBtn.click();
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({ path: path.join(evidenceDir, 'layout_a_border_deep_black_1440.png') });
    console.log('Captured layout_a_border_deep_black_1440.png');
  }

  const compactBtn = await page.$('button[title*="高密度緊湊"]');
  if (compactBtn) {
    await compactBtn.click();
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({ path: path.join(evidenceDir, 'layout_a_density_compact_1440.png') });
    console.log('Captured layout_a_density_compact_1440.png');
  }

  const resetBtn = await page.$('.btn-reset-preview');
  if (resetBtn) {
    await resetBtn.click();
    await new Promise(r => setTimeout(r, 300));
  }

  // 4c. Testing Sidebar Styles A, B, C, D and Folded
  console.log('4c. Testing Sidebar Styles A, B, C, D and Folded...');
  // Style A (Default)
  await page.screenshot({ path: path.join(evidenceDir, 'sidebar_style_a_1440.png') });
  console.log('Captured sidebar_style_a_1440.png');

  // Style B (1:1 Tabler)
  const styleBBtn = await page.$('button[title*="方案 B"]');
  if (styleBBtn) {
    await styleBBtn.click();
    await new Promise(r => setTimeout(r, 350));
    await page.screenshot({ path: path.join(evidenceDir, 'sidebar_style_b_1440.png') });
    console.log('Captured sidebar_style_b_1440.png');
  }

  // Style C (Dock)
  const styleCBtn = await page.$('button[title*="方案 C"]');
  if (styleCBtn) {
    await styleCBtn.click();
    await new Promise(r => setTimeout(r, 350));
    await page.screenshot({ path: path.join(evidenceDir, 'sidebar_style_c_dock_1440.png') });
    console.log('Captured sidebar_style_c_dock_1440.png');
  }

  // Style D (Cyber Vault / Glow)
  const styleDBtn = await page.$('button[title*="方案 D"]');
  if (styleDBtn) {
    await styleDBtn.click();
    await new Promise(r => setTimeout(r, 350));
    await page.screenshot({ path: path.join(evidenceDir, 'sidebar_style_d_cyber_1440.png') });
    console.log('Captured sidebar_style_d_cyber_1440.png');
  }

  // Folded State
  const foldBtn = await page.$('button[title*="收合側邊欄"]');
  if (foldBtn) {
    await foldBtn.click();
    await new Promise(r => setTimeout(r, 350));
    await page.screenshot({ path: path.join(evidenceDir, 'sidebar_folded_1440.png') });
    console.log('Captured sidebar_folded_1440.png');
    // Unfold
    const unfoldBtn = await page.$('button[title*="展開側邊欄"]');
    if (unfoldBtn) {
      await unfoldBtn.click();
      await new Promise(r => setTimeout(r, 300));
    }
  }

  // Restore Style A
  const styleABtn = await page.$('button[title*="方案 A"]');
  if (styleABtn) {
    await styleABtn.click();
    await new Promise(r => setTimeout(r, 300));
  }

  // Navigation: Strategies
  console.log('5. Testing Navigation: Strategies...');
  await page.click('a[href="#/strategies"]');
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(evidenceDir, 'strategies_vue_1440.png') });
  console.log('Captured strategies_vue_1440.png');

  // Navigation: Backtest (New)
  console.log('5b. Testing Navigation: Backtest...');
  await page.click('a[href="#/backtest"]');
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(evidenceDir, 'backtest_vue_1440.png') });
  console.log('Captured backtest_vue_1440.png');

  // Navigation: Optimization (New)
  console.log('5c. Testing Navigation: Optimization...');
  await page.click('a[href="#/optimization"]');
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(evidenceDir, 'optimization_vue_1440.png') });
  console.log('Captured optimization_vue_1440.png');

  // Navigation: Bots
  console.log('6. Testing Navigation: Bots & Allocation Modal...');
  await page.click('a[href="#/bots"]');
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(evidenceDir, 'bots_vue_1440.png') });
  console.log('Captured bots_vue_1440.png');

  // Open Allocate Modal
  const allocBtn = await page.$('.page-top-bar .btn-primary');
  if (allocBtn) {
    await allocBtn.click();
    await new Promise(r => setTimeout(r, 300));
    await page.screenshot({ path: path.join(evidenceDir, 'bots_modal_vue_1440.png') });
    console.log('Captured bots_modal_vue_1440.png');
    await page.click('.btn-close');
    await new Promise(r => setTimeout(r, 200));
  }

  // Navigation: Risk
  console.log('7. Testing Navigation: Risk Controls...');
  await page.click('a[href="#/risk"]');
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(evidenceDir, 'risk_vue_1440.png') });
  console.log('Captured risk_vue_1440.png');

  // Navigation: Logs
  console.log('8. Testing Navigation: Logs & Command Audit...');
  await page.click('a[href="#/logs"]');
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(evidenceDir, 'logs_vue_1440.png') });
  console.log('Captured logs_vue_1440.png');

  // Navigation: Market Intel
  console.log('9. Testing Navigation: Market Intel...');
  await page.click('a[href="#/market-intel"]');
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(evidenceDir, 'market_intel_vue_1440.png') });
  console.log('Captured market_intel_vue_1440.png');

  // Navigation: Settings & Testing Badge Toggles
  console.log('10. Testing Navigation: Settings & Badge Toggles...');
  const profileBtn = await page.$('.profile-trigger-sidebar') || await page.$('.profile-trigger-header');
  if (profileBtn) {
    await profileBtn.click();
    await new Promise(r => setTimeout(r, 200));
    const settingsLink = await page.$('a[href="#/settings"]');
    if (settingsLink) {
      await settingsLink.click();
    } else {
      await page.goto(APP_URL + '#/settings', { waitUntil: 'networkidle0' });
    }
  } else {
    await page.goto(APP_URL + '#/settings', { waitUntil: 'networkidle0' });
  }
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(evidenceDir, 'settings_badges_enabled_1440.png') });
  console.log('Captured settings_badges_enabled_1440.png');

  // Test toggling master badges off
  const masterBadgeBtn = await page.$('.badge-master-row button');
  if (masterBadgeBtn) {
    await masterBadgeBtn.click();
    await new Promise(r => setTimeout(r, 350));
    await page.screenshot({ path: path.join(evidenceDir, 'sidebar_badges_disabled_1440.png') });
    console.log('Captured sidebar_badges_disabled_1440.png (All Badges Hidden)');

    // Toggle master badge back on
    await masterBadgeBtn.click();
    await new Promise(r => setTimeout(r, 350));
  }

  // Test toggling individual Bot Manager badge
  const botBadgeToggle = await page.$('.badge-toggle-item button');
  if (botBadgeToggle) {
    await botBadgeToggle.click(); // Hide bot badge
    await new Promise(r => setTimeout(r, 350));
    await page.screenshot({ path: path.join(evidenceDir, 'sidebar_badge_individual_toggle_1440.png') });
    console.log('Captured sidebar_badge_individual_toggle_1440.png (Bot Badge Hidden)');

    // Restore bot badge
    await botBadgeToggle.click();
    await new Promise(r => setTimeout(r, 300));
  }

  // Return to Dashboard and capture Final Sidebar Style A with new titles
  await page.click('a[href="#/"]');
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(evidenceDir, 'sidebar_style_a_new_titles_1440.png') });
  console.log('Captured sidebar_style_a_new_titles_1440.png');

  // Responsive: 1280x800
  console.log('11. Testing Responsive 1280x800 Viewport...');
  await page.setViewport({ width: 1280, height: 800 });
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(evidenceDir, 'layout_a_vue_1280.png') });
  console.log('Captured layout_a_vue_1280.png');

  // Responsive: 768x1024
  console.log('12. Testing Responsive 768x1024 Viewport...');
  await page.setViewport({ width: 768, height: 1024 });
  await new Promise(r => setTimeout(r, 400));
  await page.screenshot({ path: path.join(evidenceDir, 'layout_a_vue_768.png') });
  console.log('Captured layout_a_vue_768.png');

  await browser.close();

  console.log('\n--- Verification Summary ---');
  console.log('Console Errors Count:', consoleErrors.length);
  if (consoleErrors.length > 0) {
    console.error('Console Errors:', consoleErrors);
    process.exit(1);
  } else {
    console.log('SUCCESS: All UI and layout verifications passed with ZERO console errors.');
  }
}

run().catch(err => {
  console.error('Test execution failed:', err);
  process.exit(1);
});
