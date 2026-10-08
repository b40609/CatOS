const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const artifactDir = 'C:\\Users\\user\\.gemini\\antigravity-ide\\brain\\7318040a-049d-42b2-a235-7a3abed7f3c8';
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: 'dark'
  });
  const page = await context.newPage();

  console.log('Opening http://127.0.0.1:8910/ ...');
  await page.goto('http://127.0.0.1:8910/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1000);

  // 定位 DonutCard 元件
  const card = page.locator('.donut-card.tabler-donut-style').first();
  if (await card.count() === 0) {
    console.log('Donut card not found!');
    await browser.close();
    return;
  }

  await card.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  // 1. 截取全覽總圖
  await card.screenshot({ path: path.join(artifactDir, 'tabler_palette_1_amber.png') });
  console.log('Saved tabler_palette_1_amber.png');

  // 2. 切換至經典科技藍
  const blueBtn = card.locator('button:has-text("科技藍")').first();
  if (await blueBtn.count() > 0) {
    await blueBtn.click();
    await page.waitForTimeout(400);
    await card.screenshot({ path: path.join(artifactDir, 'tabler_palette_2_blue.png') });
    console.log('Saved tabler_palette_2_blue.png');
  }

  // 3. 切換至翡翠極光綠
  const greenBtn = card.locator('button:has-text("翡翠極光綠")').first();
  if (await greenBtn.count() > 0) {
    await greenBtn.click();
    await page.waitForTimeout(400);
    await card.screenshot({ path: path.join(artifactDir, 'tabler_palette_3_emerald.png') });
    console.log('Saved tabler_palette_3_emerald.png');
  }

  // 4. 切換至多幣種專屬
  const cryptoBtn = card.locator('button:has-text("多幣種專屬")').first();
  if (await cryptoBtn.count() > 0) {
    await cryptoBtn.click();
    await page.waitForTimeout(400);
    await card.screenshot({ path: path.join(artifactDir, 'tabler_palette_4_crypto.png') });
    console.log('Saved tabler_palette_4_crypto.png');
  }

  // 5. 切換至電光霓虹紫
  const purpleBtn = card.locator('button:has-text("電光霓虹紫")').first();
  if (await purpleBtn.count() > 0) {
    await purpleBtn.click();
    await page.waitForTimeout(400);
    await card.screenshot({ path: path.join(artifactDir, 'tabler_palette_5_purple.png') });
    console.log('Saved tabler_palette_5_purple.png');
  }

  // 6. 測試點擊「中央：純淨留空」切換至「中央：顯示數值」，以附圖款為例
  const amberBtn = card.locator('button:has-text("琥珀金橙")').first();
  await amberBtn.click();
  const toggleBtn = card.locator('.center-toggle-btn').first();
  if (await toggleBtn.count() > 0) {
    await toggleBtn.click();
    await page.waitForTimeout(400);
    await card.screenshot({ path: path.join(artifactDir, 'tabler_palette_1_amber_with_center.png') });
    console.log('Saved tabler_palette_1_amber_with_center.png');
  }

  await browser.close();
  console.log('All palette screenshots captured successfully!');
})();
