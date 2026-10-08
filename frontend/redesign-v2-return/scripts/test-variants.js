import puppeteer from 'puppeteer-core';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function testButtons() {
  const browser = await puppeteer.launch({ executablePath: CHROME_PATH, headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1000 });
  await page.goto('http://127.0.0.1:8910/', { waitUntil: 'networkidle0' });

  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });
  page.on('pageerror', err => {
    errors.push(err.toString());
  });

  const buttons = await page.$$('.mode-tab-btn');
  console.log('Found switcher buttons count:', buttons.length);
  if (buttons.length === 0) {
    throw new Error('No .mode-tab-btn buttons found!');
  }

  for (let i = 0; i < buttons.length; i++) {
    const text = await page.evaluate(el => el.textContent.trim(), buttons[i]);
    await buttons[i].click();
    await new Promise(r => setTimeout(r, 200));
    const isActive = await page.evaluate(el => el.classList.contains('active'), buttons[i]);
    console.log(`[${i + 1}/${buttons.length}] Switched to: ${text}, Active: ${isActive}`);
  }

  if (errors.length > 0) {
    console.error('Console errors detected during switching:', errors);
    process.exit(1);
  } else {
    console.log('All 4 view mode tabs tested successfully without console errors!');
  }
  await browser.close();
}

testButtons().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
