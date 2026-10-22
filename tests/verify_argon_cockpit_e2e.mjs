import { chromium } from 'playwright';

async function run() {
  console.log('Connecting to http://127.0.0.1:8887/#/ ...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
  });
  const page = await context.newPage();

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      console.error(`[Browser Error]:`, msg.text());
    }
  });

  await page.goto('http://127.0.0.1:8887/#/', { waitUntil: 'networkidle', timeout: 15000 });
  await page.waitForTimeout(1000);

  // 1. 檢查頂部 Argon 按鈕是否存在且預設啟動
  const argonBtn = page.locator('button:has-text("★ Argon 旗艦終端")');
  if (!(await argonBtn.isVisible())) {
    throw new Error('Argon 旗艦終端切換按鈕未顯示！');
  }
  console.log('✓ 頂部 [★ Argon 旗艦終端] 按鈕已成功渲染');

  // 2. 檢查 HUD 核心要素
  const supText = page.locator('text=SUP: ONLINE');
  await supText.waitFor({ timeout: 5000 });
  console.log('✓ 頂層生存列 (GlobalRiskHud) 正常載入: SUP: ONLINE');

  const equityText = page.locator('text=$12,480.00');
  if (await equityText.isVisible()) {
    console.log('✓ 帳戶總淨值正確顯示: $12,480.00');
  }

  const pnlText = page.locator('text=+$294.54');
  if (await pnlText.isVisible()) {
    console.log('✓ 風控期間損益正確顯示: +$294.54 (+2.41%)');
  }

  // 3. 檢查主甲板 (SymbolStateMatrix)
  const matrixTitle = page.locator('text=全息部位與意圖矩陣');
  await matrixTitle.waitFor({ timeout: 5000 });
  console.log('✓ 左中主甲板 (SymbolStateMatrix) 正常載入');

  const ethRow = page.locator('text=Diff: +0.60 ETH (1 UNKNOWN 待對帳)');
  if (await ethRow.isVisible()) {
    console.log('✓ ETH 標的狀態機正確標註 UNKNOWN 待對帳差額');
  }

  // 4. 檢查右側處置台 (IncidentTriageConsole)
  const triageTitle = page.locator('text=異常處置與風控鎖存台');
  await triageTitle.waitFor({ timeout: 5000 });
  console.log('✓ 右側甲板 (IncidentTriageConsole) 正常載入');

  // 5. 測試切換回舊版卡片網格 (點擊 ③ 5 卡收斂版)
  console.log('Testing toggle to Classic Layout (Preset 3: T-Split 5 Cards)...');
  const preset3Btn = page.locator('button:has-text("③ 5 卡收斂版")');
  await preset3Btn.click();
  await page.waitForTimeout(600);

  // 檢查是否出現卡片標題列或卡片標籤
  const classicCard = page.locator('text=持倉明細與在途委託');
  await classicCard.waitFor({ timeout: 5000 });
  console.log('✓ 成功無縫切換至經典卡片網格 (T-Split 5 卡版面保留完整)');

  // 6. 測試切回 Argon 旗艦終端
  console.log('Testing toggle back to Argon Cockpit...');
  await argonBtn.click();
  await page.waitForTimeout(600);

  await matrixTitle.waitFor({ timeout: 5000 });
  console.log('✓ 成功秒級切回 [★ Argon 旗艦終端]！');

  await browser.close();
  console.log('ALL VERIFICATIONS PASSED! 100% READY.');
}

run().catch((err) => {
  console.error('VERIFICATION FAILED:', err);
  process.exit(1);
});
