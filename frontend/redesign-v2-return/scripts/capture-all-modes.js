import puppeteer from 'puppeteer-core';
import path from 'path';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const ARTIFACT_DIR = 'C:\\Users\\user\\.gemini\\antigravity-ide\\brain\\7318040a-049d-42b2-a235-7a3abed7f3c8';

async function capture() {
  const browser = await puppeteer.launch({ executablePath: CHROME_PATH, headless: true });
  const page = await browser.newPage();
  await page.setViewport({ width: 1600, height: 1050, deviceScaleFactor: 2 });
  await page.goto('http://127.0.0.1:8910/', { waitUntil: 'networkidle0' });

  const buttons = await page.$$('.mode-tab-btn');
  const modeNames = ['mode_1_leveraged', 'mode_2_margin', 'mode_3_ranking', 'mode_4_compare'];

  for (let i = 0; i < buttons.length; i++) {
    await buttons[i].click();
    await new Promise(r => setTimeout(r, 300));
    
    // Find the donut card element
    const donutCard = await page.$('.donut-card');
    if (donutCard) {
      const cardPath = path.join(ARTIFACT_DIR, `${modeNames[i]}_card.png`);
      await donutCard.screenshot({ path: cardPath });
      console.log(`Saved card screenshot: ${cardPath}`);
    }
  }

  // Full page screenshot of current mode (compare_all)
  const fullPagePath = path.join(ARTIFACT_DIR, 'dashboard_compare_all.png');
  await page.screenshot({ path: fullPagePath });
  console.log(`Saved full page screenshot: ${fullPagePath}`);

  await browser.close();
}

capture().catch(err => {
  console.error(err);
  process.exit(1);
});
