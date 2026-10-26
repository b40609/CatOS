更新：2026-10-26（Asia/Taipei）。目前工作包：純前端 UI/UX 打磨與視覺階層重構已完成，型別檢查、打包建置與狀態適配測試全數通過（PASS）。依使用者指示提交並推送至 Git，供明日於公司電腦接續開發。

## 目前基線

- 分支 `feature/catos-react-vite`，產品名稱為 CatOS。
- 執行與儲存底座僅 Python 3.11+、SQLite（WAL）；FastAPI 綁定 127.0.0.1。
- 2026-10-25 遠端倉庫已收斂至 `b40609/CatOS`，舊版歷史封存於 `archive/catos-v1`。
- `CatOS_Yaozi` 維持獨立工作目錄，不跨目錄 import、不整包覆蓋。

## 已完成／實際驗證（2026-10-26 前端進度）

1. **槓桿與資產曝險圓環（AllocationDonutCard）UI/UX 重構**：
   - **視覺硬傷根治**：移除刺眼粗笨的飽和亮橘與 `drop-shadow` 模糊霓虹光暈，軌道厚度自 13.5px 降至優雅的 9.5px，內徑自 134px 擴至 140.5px，徹底消除文字與內環碰撞問題。
   - **金錢直觀 HUD（Money-First）**：針對交易員對實質資本高度敏感的特性，將中央大數據設為「總名目持倉價值（如 `$105.0k`）」，搭配 3px 微型進度刻度槽（71.9% 水位）與底部「3x 上限 $146.1k · 餘 $41.1k (2.16x)」，雙錨定金錢實質與槓桿倍數。頂部支援 `[ 焦點: $ 金額 (推薦) | x 倍數 ]` 即時切換。
   - **新增【策略機器人】歸因維度**：Tab 擴充為 5 大維度（`幣種配置` | `策略機器人` | `多空敞口` | `保證金佔用` | `盈虧分佈`），點選機器人可依 Tabby（BTC）、Calico（ETH）、Machi（SOL）直觀拆解總預算消耗與可用緩衝。
2. **工作區卡片佈局與微型組件庫**：
   - 整合 `TopMarketTicker` 即時頂部行情走馬燈、`MicroWidgetStore` 微型組件狀態管理與 `WidgetGalleryDrawer` 抽屜。
   - 樹狀佈局分割器（`tree-splitter`）與自由拖曳佈局狀態正常。
3. **驗證與構建證據**：
   - `npm run typecheck` (`tsc --noEmit`)：0 錯誤。
   - `npm run build` (`vite build`)：0 錯誤打包通過。
   - `npm run test` (`node --test tests/state_adapter_test.mjs`)：8 項測試全數通過（PASS）。
   - Vite 8890 開發伺服器正常運行（`http://127.0.0.1:8890/#/`）。

## 尚未完成／邊界

- 完整 Bot／策略管理 HTTP、R1 HTTP／主頁帳戶風控串接尚未實作，待前端版面完全定案後推進。
- 不接觸真實金鑰環境變數、不讀取真實憑證、不對外發出實盤交易請求。

## 明日接續建議

- 在公司電腦拉取最新代碼（`git pull`）後，執行 `.\scripts\start-laptop-dev.ps1` 或 `npm run dev` 啟動前端。
- 檢視頂部行情列、卡片佈局及 AllocationDonutCard 金錢焦點與機器人維度，繼續進行各卡片細節微調或進入下一階段功能規劃。


