import puppeteer from 'puppeteer-core';
import path from 'path';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const ARTIFACT_DIR = 'C:\\Users\\user\\.gemini\\antigravity-ide\\brain\\7318040a-049d-42b2-a235-7a3abed7f3c8';

async function testAndCapture() {
  const browser = await puppeteer.launch({ executablePath: CHROME_PATH, headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1050, deviceScaleFactor: 2 });

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });
  page.on('pageerror', err => errors.push(err.toString()));

  await page.goto('http://127.0.0.1:8910/', { waitUntil: 'networkidle0' });

  // 1. Check comparison buttons
  const dcbButtons = await page.$$('.dcb-btn');
  console.log('Found design comparison buttons count:', dcbButtons.length);
  if (dcbButtons.length !== 4) {
    throw new Error(`Expected 4 design comparison buttons, but found ${dcbButtons.length}`);
  }

  const variantFileNames = [
    'variant_0_original',
    'variant_a_precision_gauge',
    'variant_b_cyber_neon',
    'variant_c_ultimate_ops'
  ];

  for (let i = 0; i < dcbButtons.length; i++) {
    const text = await page.evaluate(el => el.textContent.trim(), dcbButtons[i]);
    await dcbButtons[i].click();
    await new Promise(r => setTimeout(r, 250));

    const isActive = await page.evaluate(el => el.classList.contains('active'), dcbButtons[i]);
    console.log(`[${i + 1}/4] Clicked: "${text}", active: ${isActive}`);

    const card = await page.$('.donut-card');
    if (card) {
      const cardPath = path.join(ARTIFACT_DIR, `${variantFileNames[i]}_card.png`);
      await card.screenshot({ path: cardPath });
      console.log(`Saved screenshot: ${cardPath}`);
    }
  }

  if (errors.length > 0) {
    console.error('Console errors detected:', errors);
    process.exit(1);
  }

  // Final full dashboard screenshot
  const fullDashPath = path.join(ARTIFACT_DIR, 'dashboard_design_variants.png');
  await page.screenshot({ path: fullDashPath });
  console.log(`Saved full dashboard: ${fullDashPath}`);

  await browser.close();
}

testAndCapture().catch(err => {
  console.error('Test and capture failed:', err);
  process.exit(1);
});
