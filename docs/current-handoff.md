# CatOS 目前接續入口

**更新時間**：2026-10-23 23:35 (UTC+8；拍板捨棄 8887 全部功能，徹底清除 isIntegratedPreview、抽屜跳轉、意圖微摘要與相關分支，唯一正式服務 8890 常駐運行中)
**當前負責者**：前端視覺與互動開發者 (Antigravity) · 獨立驗收者 (GPT-6 Sol)
**工作目錄**：C:/Users/user/Desktop/CatOS_Astra
**GitHub 倉庫**：https://github.com/b40609/CatOS (Public)
**Git 分支**：`feature/catos-react-vite` / `main`
**下一成果**：提供 GitHub 網址給 HR 檢視。

---

## 徹底捨棄 8887 過渡功能與全面回歸正式純粹終端（2026-10-23）
1. **依使用者指示「8887 的功能都是我不要的 可以捨棄了」徹底執行收斂清除**：
   - **終止 8887 獨立預覽台進程**：全面停止 Port 8887 監聽服務，正式環境唯一鎖定 `http://127.0.0.1:8890/`。
   - **量化機器人矩陣徹底純化**（[v0-bot-table.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/v0-bot-table.tsx)）：
     - 徹底移除策略名稱下額外塞入的「意圖微摘要」行（如「續抱 · 等待 11:15 收盤」等），回歸極致高密度雙層排版。
     - 徹底移除操作按鈕上的 `(模擬)` 標記與冗餘文字。
     - 徹底移除 `isIntegratedPreview` prop 與跨卡高亮標記。
   - **持倉明細與在途防線徹底純化**（[activity-panel.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/activity-panel.tsx)）：
     - 徹底移除 P6 欄位上的 `[▲ 更新待確認 (詳情 ↗)]` 與 `[● 已確認 (詳情 ↗)]` 抽屜按鈕，回歸純粹的 `OKX 向上取整` 綠燈標記。
     - Header 徽章固化為純粹綠燈 `P6 交易所端 100% 錨定`。
     - 徹底移除掛單頁的跨卡跳轉高亮分支。
   - **風險警報與交易日誌徹底純化**（[unified-incident-activity-card.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/unified-incident-activity-card.tsx)）：
     - 徹底移除每筆事件底部的「定位 Bot」與「共用詳情 ↗」抽屜觸發按鈕，去除無效的抽屜呼叫。
     - 保持方案 C macOS 晶透黑曜石微膠囊美學，純粹呈現時序湧動與事件核心。
   - **通用活動日誌純化**（[unified-activity-deck-card.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/unified-activity-deck-card.tsx)）：
     - 徹底清除 `isIntegratedPreview` prop、`openInspector` 呼叫與 `[詳情 ↗]` 標記。
2. **驗證與運行狀態**：
   - 8890 主戰情台（PID 20116）常駐監聽於 `http://127.0.0.1:8890/`。
   - 8887 預覽服務已完全終止關閉。
   - `npx tsc --noEmit`：0 錯誤通過。
   - `npm run build`：0 錯誤通過（6.94s）。

---

## 風險警報與交易日誌視覺風格定案：方案 C macOS 晶透（2026-10-23）
1. **使用者正式拍板定案「方案 C（macOS Sequoia 晶透黑曜石微膠囊風格）」**：
   - 全面固化 Apple HIG 晶透質感：
     - **未解除異常 (WARN)**：`bg-amber-500/15 border border-amber-500/30 text-amber-200 rounded-full px-2 backdrop-blur-xs`，搭配琥珀金光學呼吸核心。
     - **已解除警報 (RESOLVED)**：`bg-white/[0.04] text-zinc-400 border border-white/[0.06] rounded-full px-2 backdrop-blur-xs`。
     - **成交 (FILLS)**：買多 `emerald` / 賣空 `rose` 晶透微膠囊圓角標籤，搭配專屬光子次表面暈彩。
     - **心跳 (OK)**：`bg-slate-500/15 text-slate-300 border border-slate-500/25 rounded-full px-2 backdrop-blur-xs`。
     - **風控衝擊卡片**：`rounded-lg bg-amber-500/10 border border-amber-500/25 backdrop-blur-xs`，深沉黑曜石玻璃質感。
2. **依「定案固化 SOP」徹底刪除過渡分支與臨時開關**：
   - 在 [unified-incident-activity-card.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/unified-incident-activity-card.tsx) 中徹底刪除 Header 右側「風格選項：方案 A Linear 冰晶 | 方案 B Bloomberg 終端 | 方案 C macOS 晶透」切換按鈕。
   - 徹底移除 `colorTheme` state 與 `ColorThemeMode` 類型定義，清除方案 A 與方案 B 的分支條件程式碼。
   - Header 右側還原純淨專業微標籤 `SQLite (WAL) 同步`，實現 Zero-Waste 純資料密度。
3. **驗證與運行狀態**：
   - 8890 主戰情台（PID 20116）與 8887 預覽台（PID 20732）背景常駐運行熱更。
   - `npx tsc --noEmit`、`npx tsc --project tsconfig.dashboard-preview.json` 0 錯誤通過。
   - `npm run build` 與 `npx vite build --config vite.dashboard-preview.config.ts` 0 錯誤通過。

---

## 徹底清除生造符號與介面快捷鍵文字（2026-10-23）
1. **依使用者指示徹底清除 5 大雜質元素**：
   - 徹底移除頂部導航列之 `搜尋或跳轉... Ctrl K` 按鈕（[shell.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/shell.tsx)）。
   - 徹底移除未經設計的生造科技雙斜線符號 `//`（[widget-gallery-drawer.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/widget-gallery-drawer.tsx)）。
   - 徹底移除生造英文裝飾字 `MODULE HUB` 與自嗨狀態條 `SUPERVISOR ACTIVE | WAL 日誌防護 | 100% DECIMAL 核心`。
   - 徹底移除彈窗與按鈕上的快捷鍵文字標籤（`按 ESC 關閉`、`<kbd>Alt+M</kbd>`、`<kbd>Ctrl K</kbd>`），快捷鍵回歸底層靜態監聽，介面徹底乾淨純粹。
2. **模組庫純淨收斂**：
   - 標題回歸樸素克制的「工作區模組庫 (N/9 掛載中)」，右上角保留純粹的關閉 `X` 按鈕。
   - 側邊欄保留純粹的分類標籤與出廠配置切換。
3. **驗證與運行狀態**：
   - 8890 主戰情台（PID 20116）與 8887 預覽台（PID 20732）背景常駐運行熱更。
   - `npx tsc --noEmit`、`npx tsc --project tsconfig.dashboard-preview.json` 0 錯誤通過。
   - `npm run build` 與 `npx vite build --config vite.dashboard-preview.config.ts` 0 錯誤通過。

---

## 全域戰情日誌分類定案：詞組 2 極限二字零浪費（2026-10-23）
1. **使用者正式拍板定案「方案 A 詞組 2（極限二字零浪費風格）」**：
   - 徹底根除「成交流水、風控保護、委託執行、系統對帳」四字生造湊詞。
   - 固化為 6 大極簡終端 Tabs：
     1. **`未解除`**（置頂待辦異常，如 UNKNOWN 委託、P6 待確認）
     2. **`全部`**（全域時序流水）
     3. **`風控`**（3.0x 槓桿超限、日損 Soft/Hard 熔斷、P6 災難停損保護）
     4. **`成交`**（SWAP 開平倉撮合、8H 永續資金費結算、外部返佣）
     5. **`委託`**（委託提交、撤單、UNKNOWN 逾時鎖定、滑價偏離）
     6. **`系統`**（對帳門禁審計、Bot 啟停生命週期、Closed Bar 延遲恢復）
2. **依「定案固化 SOP」徹底刪除過渡分支與臨時按鈕**：
   - 徹底刪除分類架構方案 A/B/C 及用詞風格 1/2/3 臨時切換按鈕。
   - 程式碼收斂寫死為正式定案邏輯，右側還原為純淨時序湧動微標，無任何過渡冗餘。
3. **驗證與運行狀態**：
   - 8890 主戰情台與 8887 預覽台背景常駐運行熱更。
   - `npx tsc --noEmit`、`npx tsc --project tsconfig.dashboard-preview.json` 0 錯誤通過。
   - `npm run build` 與 `npx vite build --config vite.dashboard-preview.config.ts` 0 錯誤通過。

---
1. **依指示徹底移除頁面底部狀態列（Grounded Footer Purge）**：
   - 在 [shell.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/shell.tsx) 中徹底移除 `footer` 元素及其回放進度綁定。
   - 釋放垂直高度，杜絕非必要的心跳列與回放進度條佔位，全螢幕每一像素皆服務於量化核心交易數據。
2. **驗證與運行狀態**：
   - 8890 主戰情台與 8887 預覽台背景常駐運行熱更。
   - `npm run build` 與 `npx vite build --config vite.dashboard-preview.config.ts` 0 錯誤通過。

---

## 前端核心收斂：徹底移除右側檢驗抽屜（Inspector Drawer Purge）
1. **依指示徹底移除右側抽屜（Zero-Waste 零浪費純資料密度）**：
   - 移除常駐的 36px 垂直微型錨定條 (Inspector Rail)。
   - 移除推擠式 380px 檢驗抽屜 (Inspector Drawer) 與主工作區之寬度擠壓。
   - 主工作區 Layout Tree 恢復 100% 滿版無干擾寬度。
   - 保留卡片 Tab 堆疊 (Tabbed Container) 與 Bot 表格內行內展開能力。
2. **驗證與運行狀態**：
   - 8890 主戰情台與 8887 預覽台背景常駐運行熱更。
   - `npm run build` 與 `npx vite build --config vite.dashboard-preview.config.ts` 0 錯誤通過。

---

## 資產曝險卡片定案固化：TradingView 極簡甜甜圈 C 參數（2026-10-22）
1. **定案參數固化（Solidify）**：
   - `donutRatio: 51`（左側圓環寬度佔比 51%，右側資訊棧 49%）
   - `radius: 66`（圓環外半徑 66px，大氣舒展）
   - `strokeWidth: 10`（精緻雅緻 10px 環身）
   - `sliceGap: 2`（2px 物理微隙）
   - `hudFontSize: 28`（28px TradingView 醒目 Hero 主數值）
   - `hudYOffset: -13`（-13px 垂直位移完美置中與右側資訊棧齊平）
   - `barHeight: 3`（3px 極簡微軌道）
   - `limitMarkLength: 0`（完全隱藏 50% 冗餘刻度，保持純淨）
2. **除錯分支與臨時控制徹底刪除（Purge on Decision）**：
   - 依「定案固化 SOP」徹底刪除候選模式切換（A 膠囊容量、B 半圓儀表、D 多空標尺）及冗餘資料計算。
   - 徹底刪除 8 大滑桿微調面板、預設按鈕、複製/重置按鈕與相關 localStorage 狀態。
   - 程式碼自 1417 行精簡至 234 行，零冗餘純粹高密度呈現。
3. **驗證與運行狀態**：
   - 8890 主戰情台與 8887 預覽台背景常駐運行熱更。
   - `npm run build` 與 `npx vite build --config vite.dashboard-preview.config.ts` 0 錯誤通過。


## 散戶 v1 精簡與 R1 定案（2026-10-20）

- [完整評估與已定案 R1](retail-v1-simplification-assessment-20261020.md)：以 1,000～10,000 USDT、本機自用為尺度，列出保留／延後／警告／阻擋動作、原與新保證、漏判案例及必要測試。核對現行程式後確認：沒有每單全歷史重播；合法減倉已有條件分流；S9／S10 尚未接交易或 funding，不能宣稱已具備背景實盤補帳。
- 前次評估已修正 [gate 契約](reconciliation-gate-contract.md) 中過時分類／identity 敘述；本次同步 R1 local-sim 契約，舊 Demo／Q1 來源路徑保留。歷史 evidence 不代表當前帳戶或本輪採集。
- 建議後續首個交易閉環不以多 Lot／精細費用分攤／進階研究為前提；UI 後續沿用 Bot／日誌元件呈現可做動作、主因與恢復指引，不由 UI 自行授權交易。此建議不取代下方已交辦的前端工作。
- **已定案 R1**：使用者已明確同意每日首次合格觀測建立固定「風控期間基準」，取代精確午夜 E0 強制前置與首次暫缺即封鎖整天的 E1；不涵蓋起算前損失。同日基準不得刷新，起算後外部流須證明歸屬，全部 latch 與其他安全條件保留；完整契約見評估第 5 節。舊 Q1 能力及歷史證據保留，不再作 R1 首次基準的強制條件。
- **實作／差異**：[R1 交付](risk-period-r1-local-sim.md)。新增 `catos/risk_period.py`、`tests/test_risk_period_r1.py`；修改 `risk.py`／`journal.py`／`supervisor.py`／`reconciliation_gate.py` 與 `tests/test_risk.py`，同步政策、風控／gate 契約及本入口。單 writer 原子建立、同日不可刷新、首次暫缺重試、跨日／重啟 latch、期間外部流／報告摘要均已接通 local-sim；COMMIT 後 ACK 遺失保持失敗且不覆寫已保存基準。
- **自測／基線**：Python 3.14.6，全新 TemporaryDirectory 既有 schema DB、合成報告／固定 clock／FakeExchange；21 項 R1＋176 項受影響回歸，197／197、0 failure／error／skip。[原始日誌](../reports/risk-period-r1-local-sim-20261020/unittest.log)／[來源 SHA-256 與模組計數](../reports/risk-period-r1-local-sim-20261020/summary.json)。這是開發自測，沒有獨驗或 Git 狀態核對；工作樹仍含其他並行內容，不整理或提交。
- **GPT-6 Sol 獨立驗收（2026-10-20）**：[報告與範圍](../reports/risk-period-r1-independent-acceptance-20261020-gpt6sol/acceptance.md)。逐檔 SHA-256 17／17 一致；獨立重跑 12 模組 197／197，額外 3 個邊界案例通過；檢查分支、HEAD、未暫存差異與空暫存區。**R1 local-sim PASS**，無 stage／commit／push。全工作樹 `git diff --check` 有本入口第 3–6 行尾端空白；僅 R1 相關程式、測試及契約的檢查通過。
- **邊界／下一成果**：無 schema／既有 DB 遷移，未動產品 DB／憑證／前端／Yaozi／正式服務，未採集或交易。R1 僅合成 USDT 無負債 scope，未接 HTTP／UI／Demo／Live；報告不宣稱完整台北日日損。獨驗完成，後續最有價值成果是另行授權的 HTTP／UI 或 Demo 串接；commit／push、新採集及 Demo／Live 仍須另有授權。前次僅文件定案的紀錄保留於評估第 7 節，不冒充當時已測。

---




## 實機並排對照快捷組（2026-10-20；提供肉眼可視化比對）

- **頂部 Header 常駐實機對照按鈕群**：
  直接在頁面頂端右上角工具列（`[卡片管理]` 左側）掛載 4 個高對比度快捷按鈕，無須深入選單：
  1. **`[① 策略 vs 意圖]`**：左右 50:50 並排。左邊展示「策略機器人矩陣」（點擊展開看內嵌意圖與五階段鏈），右邊展示獨立的「策略目標與訊號強度」看板，供肉眼實機對照資訊是否重複。
  2. **`[② 日誌 vs 流水警報]`**：左右 50:50 並排。左邊展示「交易日誌與風險事件」（點選成交/警報/未解除），右邊展示獨立的「即時成交流水」與「風險警報與異常事件」，供肉眼實機對照日誌是否已涵蓋右側兩卡。
  3. **`[③ 5 卡收斂版]`**：一鍵還原為收斂後定案的 5 卡黃金戰情排版（T-Split 上下解耦，零冗餘）。
  4. **`[④ 9 卡全開]`**：將全部 9 張卡片同時並存於同一工作區，體驗多工視窗與空間壓迫感。
- **自測與自動化驗證**：
  - `npx tsc --project tsconfig.dashboard-preview.json` 與 `npx tsc --noEmit`：0 錯誤。
  - Playwright 端到端驗證（4 個按鈕存在性、點擊即時切換卡片數 2/3/9/5、元件渲染正確、Console Errors 為 0）：全部 PASS。
  - 8887 預覽服務背景持續運行中。

## 全域卡片標題重構與統一命名（2026-10-20；使用者拍板定案）

- **全面廢除中英括號混雜、多重名詞堆疊與軍事中二感**：
  依據「一眼看懂卡片提供哪些核心資訊」與專業金融終端標準，全域 9 大卡片完成正式固化命名：
  1. `equity` ➜ **「帳戶權益與損益」**（總資產淨值、今日損益、回撤走勢）
  2. `positions` ➜ **「持倉明細與在途委託」**（多空持倉、P6 停損防線、盤口在途掛單）
  3. `bots` ➜ **「策略機器人矩陣」**（4 隻量化 Bot 狀態、策略意圖微摘要、手動暫停/啟用）
  4. `allocation` ➜ **「槓桿倍數與資產曝險」**（有效槓桿 1.46x / 3.0x、幣種曝險 Donut 環圖）
  5. `activity_deck` ➜ **「交易日誌與風險事件」**（成交流水、風控未解除警報、一鍵跨卡定位）
  6. `market_watch` ➜ **「標的行情與資金費率」**（BTC/ETH/SOL 即時報價、OKX 資金費率結算）
  7. `strategy_intents` ➜ **「策略目標與訊號強度」**（策略大腦純資料目標意圖、多空指標強度）
  8. `incidents` ➜ **「風險警報與異常事件」**（撮合滑價偏離、P6 更新未確認、風控鎖存警報）
  9. `fills` ➜ **「即時成交流水」**（OKX SWAP 逐筆實時成交流水與盈虧跳動）
- **同步更新範圍**：
  - [layoutStore.ts](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/state/layoutStore.ts)：`CARD_TITLES`、`RECOMMENDED_PRESETS`、`DEFAULT_PROFILES`。
  - [card-manager-dropdown.tsx](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/card-manager-dropdown.tsx)：`ALL_CARDS`。
  - [i18n.ts](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/i18n.ts)：`recent_fills`。
  - 各卡片 Header 元件：`account-equity-band.tsx`、`activity-panel.tsx`、`v0-bot-table.tsx`、`allocation-donut-card.tsx`、`unified-activity-deck-card.tsx`、`market-watch-card.tsx`、`strategy-intents-radar-card.tsx`、`incident-timeline-card.tsx`、`preview/main.tsx`。
- **自測與自動化驗證**：
  - `npx tsc --project tsconfig.dashboard-preview.json` 與 `npx tsc --noEmit`：0 錯誤。
  - Playwright 端到端驗證（主畫面 5 卡新標題可見度、卡片管理面板 9 卡項目可見度、Console Errors 為 0）：全部 PASS。
  - 8887 預覽服務背景持續運行中。

## 卡片全數關閉與推薦預設排版支援（2026-10-20；使用者最新指示）

- **解除強制留卡限制**：
  - 在 `tree-ops.ts` 與 `layoutStore.ts` 中，將卡片節點刪除演算法支援刪除最後 1 張根葉子節點（平滑返回 `null`），徹底移除原本「最後一張核心卡片受保護無法關閉」之限制。
  - 卡片庫下拉選單 `CardManagerDropdown` 支援自由將主畫面卡片清空至 0 張，並新增「一鍵清空主畫面」快捷按鈕。
  - 在卡片標題列 `CardHeaderTitle` 增加 Hover 浮現的微型關閉按鈕 (`X`)，按住卡片本體可拖曳，點擊 `X` 即可直接關閉該卡片，零浪費純粹美學。
- **工作區空狀態引導面板 (Empty Workspace Prompt)**：
  - 當所有卡片皆被關閉時，主工作區不會崩潰或黑屏，而是渲染專業質感的 `EmptyWorkspacePrompt` 面板。
  - 面板標註「工作區目前已清空 · 自由自訂模式」，提供精選的推薦預設排版一鍵就位，並提供全部 9 張核心卡片的快捷單點加入 Chips。
- **新增推薦預設排版（不止 T-Split）**：
  1. **5卡標準戰情 (T-Split)**：權益 · 機器人 · 資產配置 / 持倉防線 · 戰情日誌（上下解耦定案版）。
  2. **4卡象限盯盤 (雙欄經典對稱)**：左欄 50%（權益+持倉防線）/ 右欄 50%（機器人+戰情日誌），極致平衡。
  3. **3卡風控防線專注 (盤口 60% 主視野)**：左側 60% 廣角持倉與在途防線 / 右側 40% 機器人意圖與戰情日誌。
  4. **6卡操盤旗艦 (全景全功能監控)**：上層（權益+機器人+行情時鐘）/ 下層（持倉防線+戰情日誌+成交流）。
  5. **單卡滿版專注 (部位與防線全螢幕)**：100% 滿版展示持倉活動、在途掛單撤單與 P6 災難停損防線。
  6. **一鍵清空 (從零自訂模式)**：完全清空工作區，自由組裝。
- **自測與驗證**：
  - `npx tsc --project tsconfig.dashboard-preview.json` 與 `npx tsc --noEmit`：0 錯誤。
  - Playwright 端到端驗證（清空主畫面 ➜ 空狀態面板 ➜ 套用雙欄對稱 4 卡 ➜ 再次清空 ➜ 單卡加入 ➜ 標題列關閉卡片 ➜ 套用操盤旗艦 6 卡 ➜ 還原 T-Split 5 卡 ➜ Console Errors 為 0）：全部 PASS。
  - 8887 背景服務正常運作於 `http://127.0.0.1:8887/#/`。

## 原生 Dashboard 整合預覽（2026-10-20；獨立 8887 可互動預覽）

- 依使用者最新要求，徹底移除未獲接受之 A/B 展示過渡列與固定 CSS 網格，在 `http://127.0.0.1:8887/#/` 做收斂整合預覽；不將候選套用至 8890。
- 沿用 8890 原生 `WorkspaceGrid` 二元空間佈局樹機制、字體、色彩、列高、按鈕與卡片配置，保留原有 T-Split 5 卡黃金戰情樹（`equity`、`bots`、`allocation`、`positions`、`activity_deck`）。
- **Bot 卡增量整合**：以原 `V0BotTable` 為基礎，保留身分、週期、策略、部位、損益、MAX DD / 停損錨定、走勢微圖、3x Cross 及運行數量統計。策略名稱下增量一行簡短意圖（如「續抱 · 等待 11:15 收盤」、「目標 3 ETH · 委託待對帳」、「保護更新待確認 · 禁增倉」、「已暫停 · 不產生新策略意圖」）。點擊 Bot 名稱或詳情開啟共用側邊面板（Sheet），展示資料時間、目前/目標部位、判定條件、風控限制、委託對帳及五階段流程鏈（資料 → 意圖 → 風控 → 委託 → 對帳），並支援跳轉相關委託與保護。原暫停／啟用按鈕在預覽中有效，同步切換本地狀態、運作數量並即時追加模擬日誌；暫停不代表平倉，啟用不得解除風控限制或 UNKNOWN，按鈕標明本地模擬。
- **戰情日誌增量整合**：`UnifiedActivityDeckCard` 沿用原時間軸與分類，增加「未解除 (2)」篩選標籤及數量徽章，未解除事件置頂顯示，已解除保留歷史。點擊事件開啟共用詳情面板，呈現時間、來源、原因、影響評估、處置指引及關聯 Bot／委託／部位；提供「查看 Bot（高亮選中）」、「查看委託（自動切至掛單頁並高亮）」、「查看保護（自動切至持倉頁並高亮）」有效跳轉。絕無「已讀」解除風險按鈕，無偽重送/恢復操作。
- **部位保護增量整合**：`ActivityPanel` 保留原部位表、價格、損益、強平距離與槓桿。原 P6 欄位整合「已確認 / 待確認 / 未啟用」狀態與按鈕，點擊開啟共用面板查看已確認生效價、更新目標價、覆蓋數量、確認時間與來源；更新目標不冒充生效價（Mochi 生效價標為「未知 (未取得終態)」），覆蓋數量顯示「待確認」，Header 防線徽章正確顯示「P6 已確認 2/3 · 1 待確認」，絕無顯示全體保護完成；掛單頁完整展示 Calico 的 UNKNOWN 待對帳增倉委託（`cat_calico_unknown_01`，凍結額 $474.75，額度保留禁盲目重送）。
- **資料與互動一致性**：由 `src/preview/preview-store.ts` 集中管理四個情境（正常續抱、UNKNOWN 待對帳、保護待確認、暫停），金額採十進位字串，各卡數值（總資產 $12,500.00、總曝險 $18,307、有效槓桿 1.46x / 3.0x）相互吻合一致，關閉隨機跳動；側欄路由邊界核對，點擊非預覽子頁面顯示明確說明並引導返回戰情總覽。
- **自測與自動化驗證**：
  - `npx tsc --project tsconfig.dashboard-preview.json` 與 `npx tsc --noEmit` exit 0。
  - Playwright 端到端腳本 (`scratch/test-e2e-preview.js`) 7 大驗證項全部通過：Bot 意圖標註與抽屜、抽屜跳轉掛單 UNKNOWN 高亮、日誌未解除篩選、日誌跳轉保護高亮、暫停/重啟切換與數量日誌連動、路由邊界說明、1100px / 768px 窄螢幕無橫向溢出、Console Errors 為 0。
  - 8887 預覽服務保持監聽運行中 (`http://127.0.0.1:8887/#/`)。未獨驗、未截圖、未操作 Git。
- **邊界與尚未串接部分**：目前為本機純前端合成情境模擬，未串接後端 Python Supervisor/Worker、未連接真實產品 DB、未取得真實 API 憑證、未連接 OKX 交易所或外部行情 provider。

---

## 0. 後端研究並行交付（2026-10-19；封存／查詢工作包就緒）

- **GPT-6 Sol 獨立驗收結果（2026-10-19）**：參數穩定度／Walk-Forward、分市場環境評估、研究驗證封存／後端查詢三包 **PASS（合成與隔離後端範圍）**。已直接讀取本目錄 `AGENTS.md` 與本入口，來源 SHA-256 三組 8／11／25 均零漂移、14 份封存快照一致。本輪專屬測試 22／22、26／26、10／10，另 8 模組 126／126、0 failure／error／skip；逐窗 Decimal 損益／費用／資金費歸屬皆核對成功。唯讀 Git 檢查完成，`git diff --check` 通過，沒有 stage／commit／push。[獨驗報告與原始日誌](../reports/research-independent-acceptance-20261019-gpt6sol/acceptance.md)。此判定不包含實際 8770／8771 更新、真實行情或前端。
- **授權／分工**：使用者同意推進前端以外的進度；Antigravity IDE 繼續前端。後端開發者完成工作包，GPT-6 Sol 已完成後端獨驗及唯讀 Git 核對；2026-10-19 使用者明確更新驗收模型，取代原 5.6 Sol Web 與舊版禁止 6 Sol 替代的限制。未執行 stage／commit／push。
- **本輪成果**：新增 `catos/research_validation_job.py`、10 項專屬測試；修改 catalog／service／worker／research API 與 preview POST 白名單。POST `/api/research/validations` 沿用既有 writer、封存及查詢路徑，保存訓練穩定區、OOS、分環境結果、14 份固定來源／資料快照與版本；提交回覆巢狀物件改為獨立副本，避免污染執行中任務。[完整契約／證據](research-validation-api.md)。未更改前端檔案。
- **邊界／待辦**：示範分類門檻須明示，非通用市場預設／部署門檻；OOS 空倉獨立起跑、期末估值，不是連續投資組合。任務 complete 不代表所有 OOS 成功，前端須讀 evaluation_complete 與各窗狀態。
- **前端回測 Web UI 隔離瀏覽器 E2E 完整收尾（2026-10-20；100% 隔離驗證通過）**：[日誌與摘要](../reports/browser-backtest-e2e-20261020/summary.json)。
  - **架構修正**：徹底移除 `backtest.tsx` 在任務完成時強制將後端 `version.active_run_id` 設為 null 的偽造邏輯；任務 complete 與忙碌槽釋放嚴格解耦，持續向後端讀取 `version`，直到後端確認釋放才解鎖提交按鈕。忙碌輪詢間隔縮短至 300ms，在後端釋放時迅速解鎖。`BacktestResultPayload` 補齊 `run_id`、`created_at`、`build_id` 欄位。
  - **三項補強測試實機通過（tests/verify_e2e_browser_test.mjs + tests/test_browser_backtest_e2e.py）**：
    1. **快速切換**：歷史任務間快速點擊切換 6 次，斷言最後選取 `data-run-id`（59c00d01）、結果容器 `data-result-run-id`（59c00d01）與顯示的約束／損益數值（period=2, pnl=-0.79532090）嚴格一致，舊請求遲到回應被乾淨丟棄。
    2. **重新整理**：透過隔離端點注入 3.5s 可控制計算延遲，確保在任務仍處於 running 時觸發 `Page.reload`；斷言重載後後端版本與清單正確保持 running，前端重新發出狀態查詢輪詢（`reQueryObserved=true`），並在延遲結束後自動平滑 complete。
    3. **離頁／卸載**：在請求／輪詢活躍時導航離頁至 `#/`，斷言卸載後不再排程後續輪詢（`subsequentPollsAfterUnmount=0`），延遲回應被 `!isMountedRef.current` 丟棄，Console 0 報錯（`consoleErrors=0`），重回頁面正常。
  - **落存與驗證**：測試腳本保存於 `tests/test_browser_backtest_e2e.py` 與 `tests/verify_e2e_browser_test.mjs`；實際日誌存於 `reports/browser-backtest-e2e-20261020/e2e_browser_verification.log`。11 / 11 測試全數 PASS。前端 `tsc --noEmit` 與 `npm run build` 0 錯誤通過（6.11s）。
  - **實際覆蓋與未覆蓋項目**：
    - **實際覆蓋**：Web UI 初始渲染、回測提交與輪詢、結果展示與 Decimal 結算、忙碌槽釋放需後端確認、歷史清單累積、快速切換一致性、背景完成不搶檢視、可控延遲重載自動恢復輪詢、離頁無後續輪詢與安全卸載、重新進入回測頁、斷線無假資料回退。
    - **未覆蓋項目**：未碰 8770/8771 正式服務或產品 DB；未執行全市場回測或 OKX 真實連線；未覆蓋超參數優化與 Walk-Forward 前端 UI 串接；未操作 Git stage/commit/push。
- **後端能力盤點／前端串接交接（2026-10-20；只讀靜態核對）**：[能力表、API 範例與問題清單](backend-frontend-integration-map.md)。React 回測頁已完成版本、清單、提交、輪詢、結果、快速切換、可控延遲重載與離頁之 100% 隔離 CDP 端到端測試；優化與驗證後端 API 已備妥，React 端待後續 Phase 3/4 推進。本輪未改後端核心、未動產品 DB／憑證。

---

## 1. 最新定案固化：【T-Split 佈局全面固化】與過渡預設清除 (2026-10-20)

使用者正式拍板「定案 T」，依據「定案固化 SOP（Solidify & Purge）」全面收斂佈局系統：

### A. 佈局重置收斂固化 (Card Manager Dropdown)
1. **未採用選項徹底刪除**：
   - 移除卡片管理器底部過渡期選項「三分割」與「雙分欄」。
   - 重置動作固化為單一明確的 `[T-Split (定案)]` 按鈕，點擊即精確恢復為 5 卡黃金戰情樹。
2. **底層代碼收斂**：
   - `tree-ops.ts` 徹底刪除未採用的 `createTriSplitTree` 與 `createDualSplitTree` 生成器。
   - `layoutStore.ts` 移除 `layout_tri_focus` 與 `layout_dual_split` 系統預設，只保留定案 `layout_tsplit_v1_core`。
   - 快取鍵升級至 `v8_tsplit`，保證前端載入即為純淨定案樹。
3. **建置驗證**：
   - `tsc && vite build` **0 錯誤** 通過（3.83s）。

### B. 資產配置額度視圖冗餘清除 (Allocation Donut Card)
- **使用者指示**：圓圈內 HUD 已標明有效槓桿與已用百分比，底部 `[保證金佔用率 14.2% SAFE] [總預算上限 (3x) $37,500.00]` 屬資訊冗餘，依指示予以徹底移除。
- **清除成效**：消除重複數據密度干擾，釋放垂直高度予上層環圖與 5 條水平進度長條。
- **建置驗證**：`tsc && vite build` **0 錯誤** 通過（5.19s）。

使用者的前期拍板**定案方案 2**已完成固化：

### A. 定案核心架構：5 卡黃金戰情台 (T-Split 解耦佈局)
1. **右下卡片：常態常駐【全域戰情日誌台】([unified-activity-deck-card.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/unified-activity-deck-card.tsx)，CardId: `activity_deck`)**
   - **整合範圍**：將即時成交流水（Fills）、風控警報（Risk Alerts）與系統事件（System Lifecycle）三大日誌源合併為單一高密度戰情時間軸。
   - **分類篩選**：頂部一體化提供 `[全部 (9)]`、`[成交流 (4)]`、`[風控警報 (1)]`、`[系統事件 (4)]`，並配備 `● 共 9 筆事件 · 1 異常告警` 微光膠囊。
   - **點擊展開**：點擊任意事件平滑展開詳情與風控細節，右側精確標註已平倉損益（如 `+$142.50`）或告警狀態。
   - **底座指示**：底部標註「全域戰情日誌：成交流水 + 風控警報 + 系統生命週期 · 同步持久化 SQLite (WAL)」。
   - **解決痛點**：成交流水不再散落各處，風控警報不再被隱藏，右下卡片視野寬廣，交易員可滾動監控高頻撮合與異常。

2. **左下卡片：收斂為純粹的【持倉與在途盤口防線】([activity-panel.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/activity-panel.tsx))**
   - **過渡清除**：徹底移除「動態流水 (方案 1)」Tab 3，代碼不留任何未使用的變數或分支。
   - **`[持倉]` 分頁**：聚焦合約部位、持倉量、開倉/標記價、未實現損益、強平距離，並深度整合 **OKX 交易所端 P6 災難停損**（觸發價、幅度、向上/向下取整方向、保護中狀態）。
   - **`[掛單]` 分頁**：升級為在途盤口作戰台（Client Order ID、方向、限價/POST_ONLY、距現價 Ticks / %、凍結保證金、單筆撤單），底部提供總凍結額與「一鍵全撤在途單」。

3. **系統佈局與快取升級**：
   - [tree-ops.ts](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/tree-ops.ts)：`createDefaultTree()` 正式寫死為 5 卡黃金配置（上半部：`equity` 0.58 | `bots` | `allocation`；下半部：`positions` 0.52 | `activity_deck` 0.48）。
   - [layoutStore.ts](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/state/layoutStore.ts)：快取鍵升級至 `v7_clean`，確保瀏覽器重新整理即載入定案排版。
   - [card-manager-dropdown.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/card-manager-dropdown.tsx)：全卡片選單正式固化 `activity_deck` 標題為 `全域戰情日誌`。

---

## 2. 明日公司電腦接續開工指引 (Quick Resume Guide)

### A. 當前工作區狀態與遠端同步
**Git 分支**：`feature/catos-react-vite`
- **待提交變更清單**（符合開發自測與固化 SOP，尚未 commit/push）：
  - 核心修改：`activity-panel.tsx`、`unified-activity-deck-card.tsx`、`unified-events.ts`、`v0-bot-table.tsx`、`tree-ops.ts`、`layoutStore.ts`、`card-manager-dropdown.tsx`、`index.tsx`、`bots.tsx`、`current-handoff.md`。
  - 廢棄清除：`exposure-panel.tsx`、`working-orders-safety-card.tsx`。
- **明日公司接續方式**：
  - **情境 1（在家先完成提交與推送）**：若今晚使用者指示將當前工作區 commit 並 push 至遠端，明天到公司電腦只需執行：
    ```bash
**Git 分支**：`feature/catos-react-vite`
**Git 分支**：`feature/catos-react-vite`
    cd frontend/cat-os-vite
    npm run dev
    ```
  - **情境 2（保持現狀明早直接接續）**：若維持現有本機分支未推，明天可直接在公司接續指令中指引。

### B. 明日公司啟動與檢驗指令
```bash
# 1. 檢查並編譯前端 (tsc + vite build)
cd frontend/cat-os-vite
npm run build

# 2. 啟動前端開發伺服器 (若未常駐)
npm run dev
# 瀏覽器訪問：http://127.0.0.1:8890/
```

### C. 明日接續 Prompt（可直接複製使用）
> 「你好，我是 Kai。我已在公司電腦打開 CatOS 專案。昨晚我們已經拍板並定案了【方案 2：全域戰情日誌 (Activity Deck)】，且完成 5 卡戰情台的收斂固化，前端運行於 http://127.0.0.1:8890/。請先讀取 `docs/current-handoff.md` 與 `AGENTS.md`，向我報告目前定案後的系統狀態，並協助我推進今日的工作。」

---

## 2. 前期定案收斂成果 (方案 A、做法 1、建議 2 & 3)

依據使用者指示「定案方案 A、1. 定案做法 1、2. 同意建議、3. 同意建議、4. 請給我看到畫面後我再決定」，已全面執行收斂固化（Solidify & Purge）：

### A. 定案方案 A：P6 災難防線深度整合至【部位與活動】卡片
1. **[activity-panel.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/activity-panel.tsx)（部位活動與盤口防線）**：
   - **`[持倉]` Tab 深度整合 P6**：每筆持倉清晰標註 `P6 災難停損` 觸發價與距現價幅度（BTC `$59,500.00 (-4.24%)`、ETH `$3,210.00 (-4.89%)`、SOL `$142.00 (-7.06%)`），配備 `● OKX 向上取整` 綠燈標籤。
   - **`[掛單]` Tab 升級為在途盤口作戰台**：Client Order ID、方向、限價/POST_ONLY、距現價 Ticks / %、凍結保證金、單筆撤單，底部提供總凍結額（`$1,430.00`）與「一鍵全撤在途單」按鈕。
   - **`[成交流]` Tab**：整合即時成交流水，徹底清除 TAG 欄位與標籤。
2. **[v0-bot-table.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/v0-bot-table.tsx)（量化機器人矩陣）收斂**：
   - 移除過渡期的 P6 臨時指示微徽章，標題欄還原純淨 `4 運作 · 0 暫停`。
   - 移除底部佔用垂直高度的重複 P6 說明橫條，釋放空間給核心數據。
   - 矩陣第 5 欄正式固化為 `MAX DD / 停損錨定`（如 `DD: -1.24% · 停損: $59,500.00 (-3.22%)`），專注於 Bot 健康指標。

### B. 定案做法 1：杜絕成交流雙重重複，K 線倒數行情進駐主戰情台
1. **預設佈局調整 ([tree-ops.ts](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/tree-ops.ts))**：
   - 在 `createDefaultTree()` 中，將原本重複的 `leaf-fills` 正式替換為 `leaf-market-watch` (`cardId: "market_watch"`)。
   - 主畫面 5 卡黃金佈局：【帳戶權益】+【量化機器人】+【資產配置 Donut】+【部位活動與盤口防線】+【標的行情與 K 線倒數】。
   - 成交流水完全由【部位活動卡】Tab 3 承接，不浪費獨立視窗，避免同一畫面重複出現兩份成交流。
2. **[market-watch-card.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/market-watch-card.tsx)**：
   - 15m/1H/4H Closed Bar 秒級倒數定時器、收盤前 45 秒琥珀金呼吸波、8H 資金費率倒數、OKX SWAP 高密度報價矩陣。

### C. 同意建議 2 & 3：過時殭屍卡片徹底清理 (依定案固化 SOP)
1. **清理 `exposure-panel.tsx`**：
   - 實體檔案已刪除。
   - `pages/index.tsx`、`layoutStore.ts`、`card-manager-dropdown.tsx` 徹底移除 `exposure` 類型、組件引用與 switch case。
   - 多空雙向標尺統一由 `allocation-donut-card.tsx` 內部 `[標尺]` 分頁承接。
2. **清理 `working-orders-safety-card.tsx`**：
   - 實體檔案已刪除。
   - `pages/index.tsx`、`layoutStore.ts`、`card-manager-dropdown.tsx` 徹底移除 `working_orders` 類型、組件引用與 switch case。
3. **佈局快取升級**：
   - `layoutStore.ts` 快取鍵升級至 `v6_clean`，確保瀏覽器立即載入最新的定案排版。

### D. 第 4 點待定項目（視覺先行導引）
- 依據視覺決策鐵律「我沒有看到畫面是不會選的（No Visual Evidence, No Selection）」，不要求使用者進行純文字盲選。
- 前端已將首頁與各子頁面完整構建，服務持續運行於 `http://127.0.0.1:8890/`。
- 使用者可直接於瀏覽器實機切換檢視：
  - 首頁：`http://127.0.0.1:8890/#/`（Live Flight Deck 即時作戰台）
  - 風控中心：`http://127.0.0.1:8890/#/risk`（深層 4 大儀表盤、風控滑桿調整、警報時間軸）
  - 機器人管理：`http://127.0.0.1:8890/#/bots`（部署 Dialog、集群延遲與契約規範）
  看完畫面後再指示首頁與子頁面的劃分是否需要進一步微調。

### E. 全域去 Tag 鐵律全面固化
- 徹底清除 `bots.tsx` 對話框中的 Tag 字串。
- 徹底清除 `activity-panel.tsx` 中的數據結構殘餘。
- 前端全界面 100% 絕跡。

### A. 三大卡片組件核心亮點
1. **[market-watch-card.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/market-watch-card.tsx) · 標的行情與 K 線收盤倒數 (Market Watch & Bar Timer)**：
   - 專為 Closed Bar 策略打造的即時收盤倒數定時器（支援 `15m`、`1H`、`4H` 秒級流暢倒數）。
   - 收盤前 45 秒自適應切換為琥珀金色呼吸波（提示「次根開盤訊號發動預備」），杜絕盤中提前撮合。
   - 整合 OKX 8H 資金費率結算倒數（00:00/08:00/16:00 UTC）與高密度 SWAP 報價矩陣（BTC/ETH/SOL/DOGE 微鋸齒跳動）。
   - 底部明示 `Closed Bar 約束：已收盤 K 線決策 · 次根開盤市價撮合`。

2. **[working-orders-safety-card.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/working-orders-safety-card.tsx) · 在途掛單與 P6 災難停損防線 (Working Orders & P6 Desk)**：
   - 獨立於部位活動卡的高密度盤口掛單列表（掛單價、距現價 Ticks / %、凍結保證金、開平多空、單筆撤單）。
   - OKX 交易所端整倉災難停損（P6 Disaster Stop Loss）專用監控台：呈現 3 幣種（BTC/ETH/SOL）停損錨定狀態、提早取整方向（多倉向上 CEIL）、Mark 觸發源與保護名目資產。
   - 底部總計凍結保證金總額與「一鍵全撤單」操作反饋。

3. **[strategy-intents-radar-card.tsx](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/strategy-intents-radar-card.tsx) · 策略目標意圖信號看板 (Worker Intents & Radar)**：
   - 貫徹 Supervisor-Worker 架構：Worker 僅輸出純資料目標意圖（Target Intent），無金鑰、不主動連網；Supervisor 獨佔交易與風控。
   - 展示 4 隻策略 Worker 實例（Tabby 15m 獵貓動能、Calico 1H 夜視回歸、Mochi 15m 波動突破、Shiro 4H 宏觀避險）。
   - 呈現目標持倉意圖增減（`LONG 0.12 BTC → 0.20 BTC`）、雙向訊號強度長條、三點關鍵指標距離（唐奇安上軌/均線成本/下軌防線）與次根開盤預備委託動作。

### B. 系統佈局與卡片庫完整整合
- 在 `layoutStore.ts` 註冊 `market_watch`、`working_orders`、`strategy_intents` 之 CardId 與對應標題。
- 在 `card-manager-dropdown.tsx` 擴充 `ALL_CARDS` 元數據（共 9 張卡片庫），支援自由增刪與動態開關。
- 在 `pages/index.tsx` 擴充工廠渲染分支，支援拖曳分裂落位與原地切換。

### C. 建置驗證
- `npm run build` (tsc + vite build)：**0 錯誤** 通過（11.40s）。
- 本機前端服務正常監聽於 `http://127.0.0.1:8890/`。

### D. 前端 UI 鐵律：徹底清除所有用戶界面 TAG 標籤 (2026-10-19 固化)
- **使用者核心指示**：`"tag": "41cb53c54d6dABDE"` 僅為後端 Supervisor 向 OKX 交易所發出 SWAP 委託時強制注入之底層 API 路由/返佣參數，**純屬後端底層契約，絕非前端視覺元素，不得顯示給用戶看**。
- **全域清除處**：
  1. `market-watch-card.tsx`：移除底部右下角 `Tag: 41cb53c5` 標籤，還原純淨 `Asia/Taipei` 時區標註。
  2. `working-orders-safety-card.tsx`：移除 Header 副標題 `Tag: 41cb53c5` 與撤單 Toast 提示中的 Tag 字串。
  3. `strategy-intents-radar-card.tsx`：移除底部右下角 `Tag: 41cb53c5` 標籤，替換為純架構協議 `JSON IPC v2`。
  4. `pages/index.tsx`：成交流卡片移除 Header `Tag: 41cb53c5` 徽章、移除副標題 `· KOL Tag`，每筆成交流移除末端 `· Tag: 41cb53c5`。
  5. `activity-panel.tsx`：成交流列表徹底刪除 `TAG` 欄位與 `Tag: 41cb53c5` 膠囊。
  6. `bots.tsx`：移除工具列與對話框中的 `tag: 41cb53c5` 標籤。
  7. `personal-os-modal.tsx`：連線面板中的 `固定交易 Tag` 改為 `資料儲存底座: SQLite (WAL)`。
- 後續所有前端卡片與頁面嚴禁再次於 UI 渲染此類底層參數。

1. **[額度]（方案 A 核心，預設第一頁）**：
   - **槓桿使用率 (Leverage Utilization) 圓環池**：以「總權益 × 最大槓桿上限 3.0x（總曝險預算 Capacity = $37,500）」為 100% 完整基底。
   - **中央智慧 HUD**：
     - 上標籤：`有效槓桿 / 上限`
     - 主數值：`0.43x / 3.0x`（大氣粗體金色 16px）
     - 下標籤：`已用 14.3% · 剩餘可開`
   - **下半部 5 條獨立水平進度長條（全展開零滾動）**：
     - `BTC (已開倉 (0.84x))`：$10,564.0 (28.2%)
     - `ETH (已開倉 (0.22x))`：$2,695.0 (7.2%)
     - `SOL (已開倉 (0.22x))`：$2,750.0 (7.3%)
     - `在途 (掛單中 (0.11x))`：$1,430.0 (3.8%)
     - `可用 (可用額度 (1.61x))`：$20,061.0 (53.5%)
     嚴格數學加總 100.0%！
   - **底部結構化風控微卡**：
     - 左欄：`保證金佔用率 14.2% SAFE`
     - 右欄：`總預算上限 (3x) $37,500.00`
     回答交易員「我離 3 倍上限還剩多少空間能開倉」的終極問題。

2. **[標尺]（多空雙向標尺）**：
   - 表頭標尺刻度重構：`← 空頭`、`0 基準 (±50%)`、`多頭 →` 絕對居中對齊中線，徹底消除表頭文字擠壓重疊。
   - 中段雙向尺規：向左紅色空頭積木塊、向右綠色多頭積木塊、中央金色淨曝險指針。
   - 底部 4 格微卡：多頭總額 ($19,195)、空頭總額 ($3,185)、淨槓桿比率 (0.40x / 3.0x)、可用保證金 ($37,587)，自適應高度不切邊。

3. **[幣種]（標的持倉相對配比）**：
   - 呈現 BTC (73.7%)、ETH (26.3%)、SOL (0.0%) 之部位相對規模與單幣防線 (BTC 28%/50% SAFE)。

4. **[Bot]（機器人策略視角）**：
   - 呈現 Tabby (56.8%)、Calico (20.3%)、Shiro (22.9%) 掌管資產規模與多空主力/避險角色。

5. **定案固化清除**：
   - 徹底刪除多空分母不一相加高達 122.9% 且文字擠壓嚴重的「矩陣」分頁。
   - 徹底清除未採用的獨立「水位」分頁（已完美融合進「額度」視圖中）。

### B. 交付驗收鐵律（2026-10-19 使用者最新定案）
- **完工後不需要截圖給使用者看，使用者會親自至網頁 (http://127.0.0.1:8890/) 驗收**。
- 開發者完成修改後，只需確認服務正常運行、build 0 錯誤並說明修改差異即可交付，禁止在對話中主動貼圖或截圖。

### C. 建置驗證
- `npm run build` (tsc + vite build)：**0 錯誤** 通過（12.36s）。
- 前端本機服務運行於 `http://127.0.0.1:8890/`。


---

## 2. 前期核心成果：資產曝險配置環圖 (Allocation Donut) 完美收斂定案 (2026-10-18)

針對使用者指示「顯示比例問題」與「卡片縮放未跟隨、太大了頂天立地、字體跑版切邊」等問題，已徹底完成全方位幾何重構與收斂固化：

1. **中心純淨留空（方案 1 定案）**：中央維持沉穩留空，資訊全面移至外部標註，杜絕中央擁擠雜亂。
2. **外置微折短鉤（方案 A 定案）**：徹底廢除長水平托盤底線，採用 8~14px 雅緻 45° 肘點 + 微折短鉤，引線絕不穿透切割文字。
3. **全響應式流體幾何架構 (Fluid ResizeObserver)**：
   - 根除寫死 `max-h-[260px]` 與固定 `viewBox`；由容器 `ResizeObserver` 60 FPS 即時捕捉卡片寬高 `(W, H)`，拖曳卡片邊界時圓環與線條平滑等比縮放。
   - **黃金比例收斂（解決「太大了」）**：圓環半徑嚴格限縮至最大 75px（外直徑約 170px，維持容器高度約 50%~55% 黃金佔比），環身厚度收斂在 12~24px，兼顧厚實份量與深黑呼吸留白。
   - **垂直防溢出安全夾持（解決「真實本金字體切邊跑版」）**：針對 12 點鐘（`佔用 0.1%`）與 6 點鐘（`可用 99.9%`）等垂直切片，肘點強制向外側展 16px，文字 Y 軸座標嚴格鎖定在 `[18px, H - 24px]` 安全區間內，絕不切字或跌入底部麵板。
   - **底部量化指標徹底防折行**：全面鎖定單行等寬微標（`whitespace-nowrap`），各尺寸視窗下嚴格防擠壓疊字。
4. **收斂固化 SOP**：徹底移除所有臨時開關、對照開關與過渡狀態，還原為高質感單一正式組件，頂部配備 `即時同步` 微光指示。
5. **編譯自測**：`npm run build` (tsc + vite build) **0 錯誤** 通過（7.39s），全視圖截圖已存證。

---

## 2. 既有研究與前端架構基線 (維持完整保留)

- 目標：理解 Pine → 多候選與反例 → 多週期成本後比較 → 按證據討論。允許隔夜，策略可演化；使用者看過證據後已確認保留 D 雙向反轉研究，不需重問。前端不作本次評估依據。
- 已校準：由 AI 解釋、選例、畫圖與提出疑點，用戶判斷合理性；不要求用戶先準備交易情境。新增 [三張可切換圖例](../artifacts/dcm-20261011-casebook-final/index.html)，復用已使用資料，新增下載／回測 0。當時／後續切換與六圖載入已用隔離 Edge 實際驗證，證據與命令見研究紀錄；未改 Antigravity 前端。
- 圖例回饋已更新：使用者認同假突破做空、假跌破做多；台股盤中跌破 DL 後等收盤站回買多。DH 收盤突破視為強多發動，之後幾天等 DC／DL／周／月成本回踩。回踩處若有 POC、EMA、SNR、OB／FVG 等同方向支撐／壓力共振，觸價進場；沒有共振則等收盤守住／站回，多空同理。空單退出可看 DL 或日 K 站上 DC／DH。點位固定／更新及各共振的精確定義仍待圖例收斂；觸價是已確認偏好，不能再重問。現行核心只支援收盤決策、次根開盤，未實作觸價撮合；詳見研究紀錄末節。
- 已完成：`catos/dcm.py`、`dcm_public_data.py`、`dcm_study.py` 與 23 個隔離 DCM 測試；沿用既有 Decimal／Closed Bar／下一根開盤／資金費核心，未改 DB schema、HTTP／MCP catalog 或交易底座。
- 公開資料：使用者本輪授權上網取得；僅 BTC-USDT-SWAP，2026-07-17 至 10-10 UTC，15m／1H／4H 共 10,710 根、256 資金費事件。公開 GET 135 次；無帳戶／憑證／產品 DB／交易請求。資金費 mark 是對應 1H mark 開盤近似，費率／滑價為明示假設。
- 研究結果：36 種家族／週期／限幅組合，150 個固定試驗、無最佳化；沒有候選通過事前探索門檻。最後段 D-15m 正損益但樣本小且開發段虧損；E 樣本不足、B 最後段虧損，不選定部署策略。最後段已使用，不再當新的未使用資料。
- 驗證：72 個開發自測 PASS；封存修改後 23 個受影響測試再 PASS。封存來源離線重跑後 report／selection bytes 相同；共 450 次市場回測執行，均為同一 150 試驗的初次／封存／再現，未新增調參。不是獨驗；Git 未執行。
- 詳細規則、失敗修復、實際命令、結果與未涵蓋項目：[研究紀錄](dcm-research-plan.md)。製品：[報告](../artifacts/dcm-20261011-study-final/report.html)、[再現證據](../artifacts/dcm-20261011-selftest/replay-verification.json)；原 Pine／完整執行程式已封存，市場資料與證據位於 gitignore 的 `artifacts/dcm-*/`，跨機接續需另外保留。
- 下一成果建議：依最新意圖提供發動後成本回踩的共振證據，先比較單一共振與收盤確認，再另設計觸價研究的撮合契約；舊 D／B／C 結果不能視為此框架已驗證。較長期間事件證據及 MCP 製品／快照接入仍待辦。未來聊天建議快照共用＋精確結果快取＋持久研究意圖，詳見研究紀錄；目前尚未接入或實作同步常駐功能。
- 指定 `chatgpt-web/gpt-5.6-sol` 獨驗差異與必要證據，commit／push 另授權。研究本輪未動前端、8770／8771、Demo／Live、產品資料根及其他目錄。以下前端為並行開發者最新交接，未由研究本輪核對或重驗。

## 1. 前端並行成果：8890 (React 19) 視覺瑕疵根除與全子頁面 Noir & Gold 終端化

針對先前斷網與上下文幻覺導致的程式碼混亂、8890 雙層邊框瑕疵及子頁面佔位符問題，已依據 ChatGPT 歷史共識全面完成下列修復與升級：

1. **消除雙層邊框與右下卡片溢出（截圖瑕疵根因解決）**：
   - 在 [`workspace-grid.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/workspace-grid.tsx) 外層定義單一 `rounded-xl border border-border/80 bg-surface/90 backdrop-blur-md`，並引入 `[&_.panel]:border-0 [&_.panel]:rounded-none [&_.panel]:bg-transparent`，徹底根除內部組件 `.panel` 導致的「框中框／雙重圓角」嵌套瑕疵。
   - 在 [`shell.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/shell.tsx) 的 `Panel` 與 [`index.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/index.tsx) 的 `allocation` / `fills` 容器加上 `flex-1 min-h-0 overflow-y-auto`，右下成交流完美自適應滾動，不再切斷底部行情。

2. **全子頁面終端化（徹底消除 "Coming next" 骨架感）**：
   - [`backtest.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/backtest.tsx)：4 大 KPI 卡、歷史任務清單（選中高亮）、Closed Bar 與 Decimal 執行約束橫幅、逐筆模擬成交流表格。
   - [`optimization.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/optimization.tsx)：Optuna TPE 任務狀態卡、3 參數搜尋空間、一鍵導出 Trial #42、帕累托最優 Top Trials 排行榜。
   - [`market-intel.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/market-intel.tsx)：獨立情報源架構約定橫幅、Yaozi 哨兵清算/偏離預警卡、跨所（OKX vs Binance）8H 資金費率偏離套利矩陣。
   - [`settings.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/settings.tsx)：OKX KOL 返佣 Tag (`"tag": "41cb53c54d6dABDE"`) 一鍵複製、cross + net_mode 保證金約束、本機 Localhost 執行底座說明。
   - [`bots.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/bots.tsx)：1 Bot : 1 SWAP 獨佔合約約定橫幅、OKX USDT-M SWAP 合約規範（`BTC-USDT-SWAP` 等）、Supervisor 強制注入 Tag 審計面板、集群狀態與損益動態匯總。
   - [`risk.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/risk.tsx)：E_risk = E_verified 風控約定、4 大動態儀表盤（總曝險、槓桿 2.81x/3.0x、單幣上限 42.8%/50%、日損 3.42%/10%）、Asia/Taipei 00:00 Soft 10% 停止增倉 / Hard 20% 市價清倉與 Kill-Switch 鎖存規則。

3. **Mock 數據與契約嚴格校準 (Mock Alignment)**：
   - 全面替換 `data.ts` 中的 PERP / Spot 標的為 OKX SWAP 標準合約（`BTC-USDT-SWAP`、`ETH-USDT-SWAP`、`SOL-USDT-SWAP` 等）。
   - 成交流注入 Supervisor 強制標記 `tag: "41cb53c54d6dABDE"`，完全契合 OKX KOL 返佣架構。

4. **四分割工作台定案方案 3（常態拖曳零按鈕 · Zero-UI）**：
   - 彻底移除頂部 4 張笨重靜態 KPI 卡片（`UnifiedKpiStrip`）與中間佔位橫條（`LayoutRibbon`）。
   - 徹底杜絕自我說明廢話，全域 Header 保持極致純淨，0 額外按鈕佔位。
   - 工作區高度自適應延展至 `h-[820px] lg:h-[calc(100vh-80px)]`，視野 100% 留給核心四分割數據。
   - 四卡片常態支援自由拉伸（120 FPS rAF 流暢縮放），雙擊中央分割線自動還原 60:40，雙擊水平分割線還原 50:50。

5. **帳戶權益卡片縮放排版瑕疵修復與方案 B 定案（Bloomberg 緊湊側欄 + 自適應圖表）**：
   - **根除高度寫死黑洞**：走勢圖徹底擺脫寫死 `height = 210`，改由 `ResizeObserver` 雙向測量寬高，SVG 折線與漸層面積 100% 垂直隨容器自適應延展。
   - **消除雙層 Header 冗餘**：徹底移除外層 28px 冗餘握把條（「按住拖曳換位 ⇄」），將拖曳換位事件直接掛於卡片頂部 Header（距離頂部 42px 內），全卡片 Header 一體化收斂為 34px 單層結構，帶金色 `⋮⋮` 抓手圖示。
   - **消除指標撕裂感**：左側 KPI 欄移除 `justify-between` 撕裂拉扯，改為頂部自然緊湊排列；拉高時自然展現「保證金使用率」與「最大歷史回撤」等深層指標，消除下方空洞。
   - **方案 B 徹底定案落地**：移除所有多方案切換代碼，固定為 Bloomberg AIM / TradingView 風格緊湊側欄 + 自適應圖表佈局，標頭保持純淨：`⋮⋮ 帳戶權益 (Equity & Drawdown)` 與 `[24H] [7D] [30D]`。

6. **業務內容全盤校準 (Option A 一次到位) 與 8899 v0 核心三大卡片完整移植落地**：
   - **右上卡片（多空曝險配置 · Exposure）**：移植 8899 雙向標尺尺規組件 [`exposure-panel.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/exposure-panel.tsx)。
   - **右下卡片（量化機器人矩陣 · Bots Matrix）**：移植 8899 雙層高階版表格組件 [`v0-bot-table.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/v0-bot-table.tsx)。
   - **左下卡片（部位與活動 · Positions & Activity）**：移植 8899 三 Tab 綜合組件 [`activity-panel.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/activity-panel.tsx)。
   - **左上卡片（帳戶權益 · Equity）**：在方案 B 左側欄底部注入有效槓桿與 Asia/Taipei 00:00 風控防線。

7. **自研輕量級 Layout Tree 引擎落地（2026-10-13 交付）**：
   - **二元分割空間樹 (Binary Layout Tree)**：在 [`types.ts`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/types.ts) 與 [`tree-ops.ts`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/tree-ops.ts) 實作純函數樹引擎，0 外置笨重依賴，全面支援遞迴分割與持久化。
   - **接縫感應提示條 (Drop Seam Sensing · 方案 A 定案)**：使用者已確認採「VS Code 扇區模式」，徹底廢除大面積 Center Swap 誤觸。在 [`drop-indicator.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/drop-indicator.tsx) 與 [`tree-node-renderer.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/tree-node-renderer.tsx) 依主對角線 100% 劃分上、下、左、右四向扇區，專注接縫分裂；琥珀金光柱 (`bg-primary animate-pulse`) 與方向徽章指示（`← 插入左側`、`→ 插入右側`、`↑ 插入上方`、`↓ 插入下方`）。
   - **高對比落位槽與自定義微型 DragImage（徹底根除幽靈重疊 BUG）**：
     - 在 [`drop-indicator.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/drop-indicator.tsx) 中引入 `bg-background/92` 實體遮罩 + CAD 工程幾何斜紋與 3px 雷射光柱，解決原 15% 透明度太淡導致底層文字穿透混亂問題。
     - 在 [`tree-node-renderer.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/tree-node-renderer.tsx) 透過 `setDragImage` 建立微型金黑膠囊，徹底杜絕瀏覽器原生抓取整張大卡片 DOM 造成的「雙重文字幽靈重疊 BUG」；並將操作膠囊居中（`left-1/2 -translate-x-1/2`），根除長標題與右側按鈕撞車。
   - **插入分裂 (2卡變3卡) 與移除自動合併 (Auto-Merge)**：支援卡片一鍵快速分裂選單及拖曳分裂；關閉卡片時兄弟節點直接平滑取代父容器填滿空間，0 留白空洞。
   - **每條分割線自由拉伸 (120 FPS rAF)**：在 [`tree-splitter.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/tree-splitter.tsx) 與 [`workspace-grid.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/workspace-grid.tsx) 實作獨立節點 rAF 拉伸，雙擊自動還原 50:50。
   - **預設佈局秒切**：工作台頂部整合四分割 (60:40)、三分割 (左一右二)、雙分欄 (50:50) 與新增卡片快捷列。

8. **雙端建置與驗證狀態**：
   - `frontend/cat-os-vite` (8890, React 19 + Tailwind v4 + Radix UI)：`tsc && vite build` **0 錯誤** 通過（11.25s）。
   - 實機截圖存證：四分割 [`layout_tree_vscode_sectors.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/c33cb8e1-6de3-4e28-bf1a-9e3034043165/layout_tree_vscode_sectors.png)、三分割 [`layout_tree_tri_split.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/c33cb8e1-6de3-4e28-bf1a-9e3034043165/layout_tree_tri_split.png)、雙分欄 [`layout_tree_dual_split.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/c33cb8e1-6de3-4e28-bf1a-9e3034043165/layout_tree_dual_split.png)。

9. **8890 卡片移動所有相關 BUG 全面根除 (2026-10-14 交付)**：
   - **根除拖曳即時取消與無法移動的毀滅性 BUG**：原先 `workspace-grid.tsx` 中的 `isLiveMorphing` 在拖曳 `dragover` 期間即時替換樹結構，導致瀏覽器 HTML5 拖曳來源 DOM 節點被 React 卸載（Unmount），瀏覽器依規範強制中斷拖曳（觸發 `dragend`）。現改為拖曳期間保持樹結構穩定，由 `DropIndicator` 提供藍圖骨架預覽，放開滑鼠（`drop`）時精準提交並持久化，徹底根除無法移動問題。
   - **完整支援中央對調換位 (Center Swap ⇄) 與四向邊緣接縫分裂 (Edge Split ⊞)**：擴充 `types.ts` 納入 `"center"`；中央 56% 區域判定為對調換位（Swap Panes ⇄），兩張卡片內容與身份乾淨互換，不破壞四分割樹比例；外圍 22% 邊緣判定為四向分裂插入（Dock / Split ⊞）。
   - **杜絕按鈕與分頁標籤誤觸拖曳**：在 `handleDragStart` 過濾 `button`、`input`、`select`、`[role='button']`，點擊週期按鈕（24H/7D/30D）與持倉標籤不再誤觸卡片拖曳。
   - **自定義金色微型 DragImage 與直觀抓手**：修正 `setDragImage` 膠囊建立與非同步安全清理；四大卡片標題列抓手注入 `cursor-grab active:cursor-grabbing`。
   - **開發自測通過**：隔離測試腳本覆蓋中央對調、邊緣分裂、兄弟節點對調及樹剪枝全部 PASS，`tsc && vite build` 0 錯誤通過。

---

## 2. 前端全面收斂固化與開發 SOP 定案 (2026-10-18 交付)

本輪前端優化實驗與版面評選經使用者逐項審閱後，已依使用者指示全面執行**收斂固化（Solidification）**與代碼清理：

1. **8899 工作台 (Vue 3, `redesign-v2-return`) 固化**：
   - 永久定案為「方案一：舒展四分割 (60:40) 定案純淨視圖」。
   - 徹底刪除方案 A/C/D、頂部切換膠囊按鈕（`style-toggle-pill`）、次級工具條（`hybrid-ribbon`，含「⚙ 調整版面」與「🔲 舒展四分割」狀態牌）、四卡片標題列上的版本膠囊（`V0 | 原版`），四張核心卡片 100% 垂直頂滿視野，實現極致零浪費純淨四分割。

2. **8890 主終端 (React 19, `cat-os-vite`) 固化**：
   - **開關 1 (頂部態勢帶)**：徹底拔除，全域 Header 保持純淨純寬裕，資產回歸【系統總覽】首頁。
   - **開關 2 (子頁面佈局)**：全面固化「方案 B（零浪費頂滿首屏）」，子頁面（Bots、Risk、Market Intel、Backtest、Optimization）統一採用精簡工具列，釋放 200px 垂直高度。
   - **開關 3 (盤口 Tick 閃爍)**：正式固化，微光漸層呼吸跳動直接常態啟用。
   - **開關 4 (部位深度指標)**：正式固化，採用 OKX 官方標準「預估強平價」、「距爆倉」與純粹白話「停損價」，徹底拋棄 P6 等工程晦澀詞。
   - **開關 5 (回測水下載回撤與熱力圖)**：正式固化為默認圖表組件。
   - **開關 6 (超參數優化帕累托散佈圖)**：正式固化為默認圖表組件。
   - **開關 7 (全域命令面板)**：不採用，徹底刪除。
   - **過渡元件徹底刪除**：已刪除 `optimization-labs.tsx`（實驗室彈窗）、`optimizationStore.ts`、`global-telemetry-bar.tsx`、`command-palette.tsx`，並拔除所有卡片標題列上的 `X` 關閉按鈕（`從主畫面關閉此卡片`）與「新增卡片 (4/6)」下拉選單，四分割版面鎖定。

3. **視覺決策定案 SOP 正式寫入 `AGENTS.md`**：
   - **定案固化 SOP（Solidify & Purge on Decision）**：使用者一旦對 UI/UX 方案拍板定案，下一階段開發即刻執行收斂固化——直接寫死為正式代碼，第一時間徹底清除所有臨時對照開關、實驗室彈窗、過渡期分支代碼與冗餘自訂按鈕，嚴禁在交付環境中繼續殘留已決策之過渡調試選項。
   - 型別驗證：`npx tsc --noEmit` 0 錯誤通過；全域實機截圖已完成存證。

---

## 3. 交易帳戶模式恢復與 TradingView / 台灣 XQ 工作台多階段落地 (2026-10-18 Stage 1 交付)

針對使用者指示「切換 (本機 Demo Live) 交易帳戶模式是 CatOS 開發文件內的最基礎需求」以及「參考台灣 XQ 或 TradingView 的靈活多階段套用」，已完成 **Stage 1 (第一階段)** 實作與實機截圖存證：

1. **核心交易帳戶切換器 (`[本機] [Demo] [Live]`) 正式恢復並連動**：
   - 新增 [`mode-selector.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/mode-selector.tsx)，直接嵌入全域 Header 右側。
   - 雙向連動 `useCatStore` 與 `stateAdapter.setMode`，提供三色專屬狀態：
     - **本機 (Local Sim)**：琥珀金呼吸微光 (`bg-amber-500/15 text-amber-400 border-amber-500/40`)，可自由啟動/停止策略進行本機模擬。
     - **Demo (模擬盤)**：青空藍標示 (`bg-cyan-500/15 text-cyan-400 border-cyan-500/40`)，唯讀隔離展示，禁止增倉與下單。
     - **Live (實盤)**：警示紅標示 (`bg-rose-500/15 text-rose-400 border-rose-500/40`)，依 INVARIANTS 嚴格鎖定防護，禁止真實金鑰。

2. **Stage 1：台灣 XQ / TradingView 風格卡片原地模組切換 (In-Place Module Swap)**：
   - 解決痛點：不需破壞已調校好的 60:40 或自訂分割線，任何視窗皆可原地秒切為交易員當前最想看的量化視窗。
   - 在 [`card-header-title.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/card-header-title.tsx) 引入微型下拉標記 `▾`，點擊即展開快速切換選單：
     - 📈 帳戶權益 (Equity & Drawdown)
     - 📊 部位與活動 (Positions & Activity)
     - 📐 多空曝險配置 (Exposure & Margin)
     - 🤖 量化機器人 (Bots Matrix)
     - 🪙 資產配置比例 (Asset Allocation Donut)
     - ⚡ 即時成交流 (Recent Fills)
   - 呼叫 `layoutStore.replaceLeafNode(leafId, newCardId)` 原地替換，即時生效並持久化。

3. **動態自由增刪卡片功能正式啟用 (Add & Remove Card Controls)**：
   - 使用者明確指示「要的是原本可以新增或刪減單張卡片的選項」，讓用戶有打造屬於自己 OS 的高度自由：
   - **新增卡片 (Add Card)**：在 [`shell.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/shell.tsx) 頂部 Header 正式掛載 [`card-manager-dropdown.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/card-manager-dropdown.tsx)，呈現 `[+ 新增卡片 4/6]` 即時狀態指示。點擊展開「主畫面卡片庫」，可一鍵將未在畫面上的卡片加入排版，或快速點擊「四分割／三分割／雙分欄」佈局預設。
   - **刪減卡片 (Remove Card)**：在 [`card-header-title.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/card-header-title.tsx) 為每張卡片常態提供微型 `✕` 關閉按鈕（以及標題下拉選單內的「關閉此卡片」選項）。當畫面卡片數 > 1 時，點擊即可刪減單張卡片，其餘卡片自動觸發 Auto-Merge 平滑填滿視野空間，0 空白空洞；最後 1 張核心卡片受防誤刪保護。

4. **實機截圖存證（眼見為憑）**：
   - 頂部 `[+ 新增卡片 4/6]` 與每張卡片 `✕` 關閉按鈕總覽：[`catos_8890_add_remove_overview.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/57b93e2d-f876-4b94-891c-5b6f304c8966/catos_8890_add_remove_overview.png)
   - 點擊展開「主畫面卡片庫」面板（自由選擇 6 大卡片開關）：[`catos_8890_card_manager_open.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/57b93e2d-f876-4b94-891c-5b6f304c8966/catos_8890_card_manager_open.png)
   - 點擊 `✕` 刪減卡片後：自動平滑合併為三分割（按鈕即時變為 `3/6`）：[`catos_8890_card_removed_tri.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/57b93e2d-f876-4b94-891c-5b6f304c8966/catos_8890_card_removed_tri.png)
   - Demo 模式切換狀態：[`catos_8890_stage1_demo_mode.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/57b93e2d-f876-4b94-891c-5b6f304c8966/catos_8890_stage1_demo_mode.png)

5. **後續階段規劃**：
   - **Stage 2 (第二階段)**：台灣 XQ 風格頂部微型佈局快捷板（四分割 60:40 / 大圖三分割 / 對等雙分割 / 單窗聚焦）一鍵切換與自訂比例一鍵復位。
   - **Stage 3 (第三階段)**：台灣 XQ 多分頁自訂桌面系統（例如「我的盯盤版面」、「極速下單版面」等）自訂命名與本機儲存。

---

## 4. 政策邊界與不可碰事項

- **嚴禁事項**：禁止接觸真實 OKX API Key、禁止向外發出實盤交易請求、禁止引入 Docker / PostgreSQL / Redis 等外置依賴。
- **金融底線**：交易計算嚴格維持 Decimal / SQLite TEXT；SWAP 委託強制包含 tag: `41cb53c54d6dABDE`；OKX 子帳戶專用，禁止陌生部位處置。

---

## 5. 明日公司電腦接續指引 (Quick Resume Guide)

### 1. 取得最新程式碼
若已提交並推送到遠端：
```bash
**Git 分支**：`feature/catos-react-vite`
**Git 分支**：`feature/catos-react-vite`
```

### 2. 啟動本機前端服務
```bash
cd frontend/cat-os-vite
npm install
npm run dev -- --port 8890
```
瀏覽器訪問：`http://127.0.0.1:8890/#/` 即可即時預覽並接續開發。

### 3. 明日新對話接續指令 (可以直接貼給 AI)
```text
**Git 分支**：`feature/catos-react-vite`
```

