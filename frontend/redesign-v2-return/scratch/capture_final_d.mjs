import puppeteer from 'puppeteer-core';
import path from 'path';

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

  await page.goto('http://127.0.0.1:8890/#/', { waitUntil: 'networkidle2' });
  await new Promise(r => setTimeout(r, 1000));

  const out = path.join('C:\\Users\\kai\\.gemini\\antigravity-ide\\brain\\11ac30d8-e78e-4bcb-b8a2-c5c78cbaadf4', 'option_d_finalized.png');
  await page.screenshot({ path: out });
  console.log('Saved option_d_finalized.png');

  await browser.close();
}

main().catch(console.error);
