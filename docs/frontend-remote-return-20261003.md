# catOS v1 前端重開發成果回傳與交接報告

- **日期**：2026-10-03
- **執行角色**：Antigravity（前端重開發）
- **整合接收端**：本機 Codex（正式 API/DOM 接線與全新隔離核心 UI 自測）、WorkBuddy（獨立驗收與 Git 核對）
- **交付目錄**：`frontend/redesign-v1/`（純靜態建置輸出與原始碼，無常駐 Node.js、無 SSR、無 Docker、無外掛後端）
- **工作路徑確認**：`c:\Users\kai\Desktop\CatOS_Astra`

---

## 一、技術方向與架構升級摘要

使用者指令已明確解除原先「不新增框架、只用原生 HTML/CSS/JS」的限制，指示建立可持續維護、擴充的前端架構。本輪全面以現代化工程標準完成重構：

1. **核心技術選型**：
   - **Vue 3** (Composition API, `<script setup>`)
   - **TypeScript**：啟用嚴格模式 (`strict: true`, `noImplicitAny: true`, `strictNullChecks: true`)
   - **Vite 6**：極速本機開發伺服器與 Rollup 正式建置打包
   - **Vue Router 4**：採用 **Hash History** (`createWebHashHistory`)，與 Python localhost 靜態檔案伺服器無縫對接，切換路由不觸發任何後端交易命令
   - **原生 CSS 與 CSS Variables**：拒絕臃腫大型 UI 庫，百分之百使用純 CSS 自行維護 Design Tokens 與元件樣式

2. **既有成果與資產保護**：
   - 舊版原生 JS/HTML 原型已完整移至 `frontend/redesign-v1/legacy_vanilla/` 妥善保存，未覆蓋、未刪除既有成果。
   - 所有 Python 核心代碼、資料庫、憑證、歷史工作區維持唯讀，無任何破壞性變更。

---

## 二、Dashboard 候選版面深入對比與選版指引

使用者指出不滿意空洞卡片或純工程診斷式首頁，要求重現高資訊密度與多面板工作區感。本輪實作了使用相同 Design Tokens、資料模型與元件的兩套候選版面供使用者決策：

### 布局 A：完整多面板工作區（Multi-Pane Workstation）
- **設計理念**：經典多視窗監控台，強調水平維度的全景展開與多維度資訊並行比對。
- **排版結構**：
  - **頂部核心 KPI (4 Cards)**：總權益淨值（曜石金左邊框突出）、今日損益、機器人狀態隊列、風控當前槓桿。
  - **中層三欄核心圖表 (48% : 28% : 24%)**：
    - 帳戶淨值走勢（平滑面積 SVG 折線，支援 7D/30D/90D 視圖切換）
    - 保證金與曝險配置（SVG 甜甜圈圖 + 四段比例圖例）
    - 重要事件時間軸（卡片手風琴展開日誌）
  - **底層四欄狀態矩陣 (34% : 22% : 22% : 22%)**：
    - 日損鎖存安全儀表（2x2 基準數值 + 4 段式彩條 Gauge 軌道與白光指針）
    - 運行中機器人隊列（BTC/ETH/SOL 狀態、浮盈、合約標的）
    - 近期研究任務（策略回測進度、Sharpe 比率）
    - Yaozi 市場情報快訊（費率偏離、鏈上警示）
- **截圖存證**：
  - 1440px 桌面：[`frontend/redesign-v1/evidence/layout_a_vue_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/layout_a_vue_1440.png)
  - 1280px 筆電：[`frontend/redesign-v1/evidence/layout_a_vue_1280.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/layout_a_vue_1280.png)
  - 768px 窄屏自適應：[`frontend/redesign-v1/evidence/layout_a_vue_768.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/layout_a_vue_768.png)
  - 頂部底座遙測 Popover 展開：[`frontend/redesign-v1/evidence/layout_a_popover_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/layout_a_popover_1440.png)

### 布局 B：閱讀焦點集中（Focus Stream）
- **設計理念**：縱向滾動流，將使用者的主要視覺焦點集中在主趨勢圖與當前最緊迫的待辦/警示項目上。
- **排版結構**：
  - **頂部緊湊 KPI Strip**：橫向排列的 4 格精簡指標。
  - **左側主視圖 (68%)**：
    - 大型淨值走勢畫布（放大高度與細節刻度）
    - 機器人實例表格（含即時損益、持倉方向、操作按鈕）
    - 研究與優化成果摘要（迭代批次、驗收結果）
  - **右側操作與風控側欄 (32%)**：
    - 需處理事項清單（日損軟限警告、合約獨佔鎖定提醒、斷線警告）
    - 日損鎖存安全儀表
    - 保證金配置甜甜圈圖
- **截圖存證**：
  - 1440px 桌面：[`frontend/redesign-v1/evidence/layout_b_vue_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/layout_b_vue_1440.png)

---

## 三、設計系統規範（Design System）

本輪完整對齊 `catOS-Frontend-Final` 之品牌精神與視覺質感：

1. **色彩體系**：
   - **底色 (Slate Dark)**：畫布主底色 `#080a0d`、側邊欄 `#0a0d12`、卡片主體 `#0e1218`、懸停 `#181e2a`、邊框 `#1f2633`。
   - **品牌曜石香檳金 (Accent)**：`#dcb347`（常規）、`#e8c25b`（懸停）、`rgba(220, 179, 71, 0.10)`（柔和背景）、`rgba(220, 179, 71, 0.35)`（重點邊框）。
   - **語意狀態色（嚴格與 Accent 分離）**：
     - 正常 / 盈利 / 運行：`#2ea043`
     - 警示 / 日損軟限：`#d29922`
     - 危險 / 硬熔斷 / 409 鎖定：`#f85149`
     - 資訊 / 遙測：`#58a6ff`
2. **字體與排版**：
   - UI 內文：`Inter`, `Noto Sans TC`，層級清晰。
   - 數值 / 金額 / 時間戳 / Hash / Tag：`JetBrains Mono` (啟用 Tabular Numerals `font-variant-numeric: tabular-nums`)，保證表格與指標對齊。
3. **低圓角與低裝飾**：
   - 統一使用 `border-radius: 4px ~ 6px`，消除過度圓角與浮誇玻璃擬態（Glassmorphism），呈現專業量化交易工作區的沉穩質感。

---

## 四、前端架構切分說明

目錄遵循高度解耦、職責單一原則：

```
frontend/redesign-v1/
├── index.html                 # 應用入口 HTML
├── package.json               # 依賴定義
├── tsconfig.json              # TypeScript 嚴格配置
├── vite.config.ts             # Vite 配置（含 @ 別名解析）
├── src/
│   ├── main.ts                # Vue 應用初始化
│   ├── App.vue                # 根元件（含全域 Sidebar、Header、版面與場景控制列）
│   ├── styles/                # CSS 設計系統
│   │   ├── tokens.css         # 設計變數集中管理
│   │   ├── base.css           # 基礎排版與重設
│   │   └── components.css     # 卡片、按鈕、表格、徽章等共通樣式
│   ├── contracts/             # TypeScript 領域模型契約（對齊 Python Serializer）
│   │   ├── strategy.ts        # catos.python-strategy.v1 契約
│   │   ├── bot.ts             # Bot 實例與狀態（含 409 衝突模型）
│   │   ├── risk.ts            # 風控指標與日損鎖存模型
│   │   ├── run.ts             # 回測與模擬成果
│   │   └── command.ts         # 控制命令審計日誌契約
│   ├── adapters/              # 資料存取層
│   │   ├── types.ts           # Adapter 抽象介面
│   │   └── mock-adapter.ts    # 具備 5 大場景與命令審計之 Mock 實作
│   ├── state/                 # Composables 響應式狀態
│   │   ├── useWorkspace.ts    # 全域資料與當前場景
│   │   ├── usePreferences.ts  # 展示偏好與 localStorage 版本化管理
│   │   ├── useDashboard.ts    # Dashboard 專屬指標運算
│   │   └── useCommandLog.ts   # 控制命令執行審計
│   ├── components/            # Vue 元件
│   │   ├── common/            # 共用元件（徽章、模式切換、遙測彈窗、SVG 圖表、安全儀表）
│   │   └── dashboard/         # DashboardLayoutA.vue 與 DashboardLayoutB.vue
│   ├── pages/                 # 各大功能頁面
│   │   ├── DashboardPage.vue  # 戰情總覽（支援 A/B 布局無縫切換）
│   │   ├── StrategiesPage.vue # 策略中心（不可變版本列表、Python 原始碼檢視）
│   │   ├── BotsPage.vue       # 機器人管理（分配彈窗含【人工信任確認】未預勾校驗）
│   │   ├── RiskPage.vue       # 風控中心（Soft/Hard 日損鎖存、槓桿限額、熔斷記錄）
│   │   ├── LogsPage.vue       # 系統日誌（Supervisor 遙測、Worker 事件）
│   │   ├── MarketIntelPage.vue# Yaozi 市場情報（標記【開發中】）
│   │   └── SettingsPage.vue   # 系統設定（展示偏好設定與重設回退）
│   └── router/
│       └── index.ts           # Hash 路由定義
├── dist/                      # 生產環境純靜態打包檔（可直接由 Python HTTP Server 托管）
└── evidence/                  # 自動化測試與真實瀏覽器驗證截圖
```

---

## 五、金融、安全與不可變業務契約遵守證明

1. **不可變策略製品與信任邊界**：
   - 嚴格落實 `contract: "catos.python-strategy.v1"`。
   - 策略原始碼為不可變版本，任何修改均建立新版本。
   - 在 `BotsPage.vue` 分配 Bot 彈窗中，**「人工檢查並確認信任此策略版本」之核取方塊預設嚴格為 `false`（禁止預勾）**，未勾選前「確認分配機器人」按鈕完全處於 `disabled` 狀態，防範未經審查之策略載入。
2. **交易出口與合約獨佔**：
   - 遙測與底座合規資訊明示 OKX SWAP 委託強制注入固定 Tag `41cb53c54d6dABDE`。
   - 單合約由單一 Bot 獨佔，提供 **持倉停止 (409 衝突)** 之完整展示情境，證明 Worker 停止不代表合約已釋放。
3. **Decimal 字串與風控純度**：
   - 價格、金額、部位、費用與保證金一律維持 String 型別，前端不以 JavaScript Float 進行算術推演或重算風控。
4. **命令隔離與零副作用**：
   - 經 `useCommandLog` 與 `mock-adapter` 追蹤，**切換路由、刷新頁面、切換 本機/Demo/Live 模式均不產生任何後端控制請求**（審計日誌維持 0 筆未授權發送）。
5. **偏好設定防護**：
   - `localStorage` 僅儲存使用者視覺布局偏好（如 A/B 選擇、走勢週期），具備 Schema 版本檢查與無效值自動回退，並於設定頁提供「重設為預設展示偏好」按鈕，絕不干擾後端真實狀態。

---

## 六、測試、建置與瀏覽器自動化驗證

1. **TypeScript 嚴格型別檢查**：
   - 命令：`npx vue-tsc --noEmit`
   - 結果：`0 errors`，全模組、契約與頁面通過嚴格型別審查。
2. **正式生產建置**：
   - 命令：`npm run build` (Vite Rollup)
   - 輸出：產出至 `frontend/redesign-v1/dist/`，包含 `index.html`、`index-[hash].css` (34.2 KB) 與 `index-[hash].js` (156.4 KB)，無外部運行時依賴。
3. **真實瀏覽器 (Puppeteer + Google Chrome) 自動化驗收**：
   - 自動化腳本：`scripts/verify-ui.js`
   - 驗證解析度：1440x900 (Desktop)、1280x800 (Laptop)、768x1024 (Tablet 垂直窄屏)。
   - 驗證場景：
     - NORMAL（正常運行）
     - SOFT_LOSS（日損軟限警告）
     - HOLD_STOPPED（持倉停止 409 衝突）
     - EMPTY（空資料待命）
     - UNAVAILABLE（後端服務異常）
   - 控制台檢查：**Console 0 Errors, 0 Warnings** 通過。
4. **測試服務與連接埠管理**：
   - 測試伺服器全程綁定 `127.0.0.1:8899`（嚴格隔離，未佔用正式 8770/8771）。
   - 驗證完成後已透過任務管理正常終止行程，`Get-NetTCPConnection -LocalPort 8899` 確認埠號已乾淨釋放。

---

## 七、截圖索引

| 截圖檔案路徑 | 視圖 / 狀態 | 驗證重點 |
| :--- | :--- | :--- |
| [`evidence/layout_a_vue_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/layout_a_vue_1440.png) | 布局 A (1440px) | 完整多面板：4 KPI、三欄中層圖表、四欄底層矩陣 |
| [`evidence/layout_b_vue_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/layout_b_vue_1440.png) | 布局 B (1440px) | 閱讀焦點集中：大型走勢區、右側待辦、下方實例表格 |
| [`evidence/layout_a_popover_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/layout_a_popover_1440.png) | 遙測 Popover | 展開底座核心參數（PID、Tag、Decimal 核心說明） |
| [`evidence/bots_modal_vue_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/bots_modal_vue_1440.png) | Bot 分配彈窗 | 驗證人工信任核取方塊未勾選、確認按鈕禁用狀態 |
| [`evidence/scenario_soft_loss_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/scenario_soft_loss_1440.png) | 日損軟限場景 | 橘黃色警告橫幅、指標高亮、日損安全儀表指針偏右 |
| [`evidence/scenario_hold_stopped_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/scenario_hold_stopped_1440.png) | 409 持倉停止場景 | 紅色警報橫幅、合約獨佔未釋放警告、衝突標記 |
| [`evidence/scenario_empty_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/scenario_empty_1440.png) | 空資料待命場景 | 乾淨空狀態導引、無 NaN 或虛假補零 |
| [`evidence/strategies_vue_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/strategies_vue_1440.png) | 策略中心頁面 | 不可變版本清單、原始碼預覽、建立版本入口 |
| [`evidence/bots_vue_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/bots_vue_1440.png) | 機器人管理頁面 | 機器人卡片、狀態標籤、啟停操作區 |
| [`evidence/risk_vue_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/risk_vue_1440.png) | 風險控管頁面 | 日損 Soft/Hard 門檻、有效槓桿上限、熔斷紀錄 |
| [`evidence/logs_vue_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/logs_vue_1440.png) | 系統日誌頁面 | 日誌級別過濾、Worker 與 Supervisor 分類日誌 |
| [`evidence/market_intel_vue_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/market_intel_vue_1440.png) | Yaozi 市場情報 | 完整入口佈局，明確標記【開發中】 |
| [`evidence/settings_vue_1440.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/settings_vue_1440.png) | 系統設定頁面 | 本地偏好重設、遙測合規參數 |
| [`evidence/layout_a_vue_1280.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/layout_a_vue_1280.png) | 布局 A (1280px) | 筆電解析度適應驗證 |
| [`evidence/layout_a_vue_768.png`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/evidence/layout_a_vue_768.png) | 布局 A (768px) | 垂直堆疊自適應排版驗證（無任何重疊溢出） |

---

## 八、回傳檔案完整 SHA-256 校驗清單

### 1. 核心原始碼 (`src/` - 40 檔)
| 相對路徑 | SHA-256 雜湊碼 | 大小 (Bytes) |
| :--- | :--- | :--- |
| `frontend/redesign-v1/src/adapters/index.ts` | `1fc9fea23ab321d0bc9a304c27ccdefd2404f0914a46f896b56df761841fc523` | 57 |
| `frontend/redesign-v1/src/adapters/mock-adapter.ts` | `dc0aae94e9b9d953573905bce245e3090740f016da3ca97dd65ebf2bd9b0dbac` | 8,746 |
| `frontend/redesign-v1/src/adapters/types.ts` | `f5f54931c567be2d0cf18bb7ed7260566c8aca838fce45d6547d1ddd58b06835` | 2,765 |
| `frontend/redesign-v1/src/App.vue` | `2121129758201c891f7d30b873e31dc0e59027f0b8752c5bd77694ecdd5ae738` | 2,841 |
| `frontend/redesign-v1/src/components/common/DonutChart.vue` | `034c5b4dd62bc8b404f7a6f6ebc0fa907ff4ca9ba93c09dcffebb21428be0938` | 3,666 |
| `frontend/redesign-v1/src/components/common/EmptyState.vue` | `4acb22b82ce553bf380fc32e0db7c8723a32974260acbe339a0d24a29e526e66` | 1,002 |
| `frontend/redesign-v1/src/components/common/MetricCard.vue` | `d96755e07a1a55d3751c6fdf318c4e491666041b6fa845efbaa7bb15a688f3d5` | 774 |
| `frontend/redesign-v1/src/components/common/ModeSelector.vue` | `4be61aed13126dbb8a6cca6d19a9849a1a5e1b81f4999ce1c0663a8e661e9037` | 1,059 |
| `frontend/redesign-v1/src/components/common/RiskGauge.vue` | `ba049d5b2647834d6ba958a39d935a9ab10d2e25fcfef5f152dce6a5e57b42b2` | 4,921 |
| `frontend/redesign-v1/src/components/common/ScenarioBar.vue` | `412a2552cec7b0ea6424ce93e85314c16e776dc00e5c0a3fccefaa024f11d8b1` | 3,131 |
| `frontend/redesign-v1/src/components/common/SparklineArea.vue` | `ff1f5a64d1a572a7621f80f7f776c6306fbae1e030d2101e3d89b4710f4fa313` | 7,186 |
| `frontend/redesign-v1/src/components/common/StatusBadge.vue` | `58a7d10afe48ec4bb9c7849ba5bbe643d3a9aa24316d6f42a96e39e28e3b10c5` | 1,384 |
| `frontend/redesign-v1/src/components/common/TelemetryPopover.vue` | `5669bd9d0c72a0768e6b2a5bea084d82aab58824b6d24a4698b682918ed2677a` | 3,570 |
| `frontend/redesign-v1/src/components/dashboard/DashboardLayoutA.vue` | `ce1aa8feb101ed52e73766805bc8cc0a447c599bf3852e5a21a33486b13f5ecc` | 12,918 |
| `frontend/redesign-v1/src/components/dashboard/DashboardLayoutB.vue` | `7df550a99f7d6e19b0ae1dd5c4ee7626e4a2a28291ef7be9cf48afd48b5300d7` | 10,456 |
| `frontend/redesign-v1/src/contracts/bot.ts` | `95901f6baf53024f881118e12471726f85c6858f4c2544da352b7594c2271d4b` | 925 |
| `frontend/redesign-v1/src/contracts/command.ts` | `803116523c16ed90e1d1e2c4957d356759365d513b7e0ab100539cc2579747ca` | 786 |
| `frontend/redesign-v1/src/contracts/index.ts` | `6f9228409c68af3d2d047ec28fc6a3b0dbcb62cffe39ad536748686fd2d114d1` | 154 |
| `frontend/redesign-v1/src/contracts/risk.ts` | `bf22ed203ffbb4145fa34ce0011657e1a9bb8ef5bac6597bdbe655d7e68847c5` | 1,166 |
| `frontend/redesign-v1/src/contracts/run.ts` | `639e0cf726a870f3418790ade27b17ef76dcb97127dcfb8027ed382b0b837b2f` | 1,166 |
| `frontend/redesign-v1/src/contracts/strategy.ts` | `f010ae40e3a48ff05a0996378134e873da22fc26ebcd79ce3fb620f44cb64904` | 953 |
| `frontend/redesign-v1/src/contracts/workspace.ts` | `6cd4330ae2faf414663ccc587ef3733488d5742adc60ad4f1de3e6a60f86389a` | 438 |
| `frontend/redesign-v1/src/env.d.ts` | `f67c074bdc1b82f2a34f0766fff44f05173663ffa50ee850320920b5545c308b` | 189 |
| `frontend/redesign-v1/src/main.ts` | `3e0be66a407cac5ebdab8c928df3317c5b9792bc8fbf4e792638a03ac0da459d` | 220 |
| `frontend/redesign-v1/src/mock/default-data.ts` | `9a75652d7efb727e8e1c478a90e36fc578c4d95f324f774b01ff181b4968be76` | 11,641 |
| `frontend/redesign-v1/src/pages/BotsPage.vue` | `27069168f3f02b9f29c2cd511bc032fe74ad2139af628199e81d5cdd8742be8b` | 10,815 |
| `frontend/redesign-v1/src/pages/DashboardPage.vue` | `b2c8364c732240742ad46e210813f81b9d74a27784dbf54cf453a6aa91a93f84` | 1,141 |
| `frontend/redesign-v1/src/pages/LogsPage.vue` | `4b801950c370845be3bcc265b472a2ffbd1e7677380eece81f7f1bb5f2e001b6` | 4,248 |
| `frontend/redesign-v1/src/pages/MarketIntelPage.vue` | `4f1648a24cd5be3e16c6ef48c96dfa3a8d4804f4e0bb1f15dab64052c7220e0d` | 2,386 |
| `frontend/redesign-v1/src/pages/RiskPage.vue` | `ad795bc00e4cd6dfd41c3606b35472c71afdbf6288be2e1e824cf2e21256380e` | 3,199 |
| `frontend/redesign-v1/src/pages/SettingsPage.vue` | `3262d675607b6f908673f91aebe3e9ab927bb3d21202574162dac3a6528dfe32` | 4,115 |
| `frontend/redesign-v1/src/pages/StrategiesPage.vue` | `9bb6747fa91be648710dff5bb6080e669f2684d2ccb7f38b9449e18dbb56a7a9` | 6,230 |
| `frontend/redesign-v1/src/router/index.ts` | `8154ea3e86a805da8158f50ecb3c2cb88e588c28f4baa61015c3a62dfe81a3e2` | 1,607 |
| `frontend/redesign-v1/src/state/useCommandLog.ts` | `4f595f37b03ce6b48ffbf7e0f9eb1c6c81c0fe9ae4869864b72caea9b093b380` | 385 |
| `frontend/redesign-v1/src/state/useDashboard.ts` | `17d1d2364fcf1982a693571772ae1f3e01ecbde1061958479917bff744cf57de` | 2,220 |
| `frontend/redesign-v1/src/state/usePreferences.ts` | `0376356294b0105ffd0b0c079af581a7fa190ba8e76958ad641118ece07a1a91` | 1,430 |
| `frontend/redesign-v1/src/state/useWorkspace.ts` | `a5409549c4420837a07e6c28a885c6aa9574a761303353056a4981fff108f028` | 1,604 |
| `frontend/redesign-v1/src/styles/base.css` | `66236f3454ce81ad94eda7da4f57f1edb9fd061f9aed242945c2f4d6ba2e02a4` | 1,645 |
| `frontend/redesign-v1/src/styles/components.css` | `907686e8f9a38961ee0034675770a66110f236263d1ac5251aa95d53ef67601f` | 9,561 |
| `frontend/redesign-v1/src/styles/tokens.css` | `9daf17a7c9ddae68513d8efac25650fe8c5c15d194a55bb2a841d9b885f7051d` | 2,244 |


### 2. 生產建置打包檔 (`dist/` - 3 檔)
| 相對路徑 | SHA-256 雜湊碼 | 大小 (Bytes) |
| :--- | :--- | :--- |
| `frontend/redesign-v1/dist/assets/index-CKWUyW5p.css` | `f471770e846b7bb36de08cc62c108aa0eb06f61c982db76c256d17ad1a55f3da` | 34,196 |
| `frontend/redesign-v1/dist/assets/index-Dd1ePWGR.js` | `925e9456a2f48ec93850312f577efd7cda58b3114c85d4a3365b9fb78a7659d9` | 156,433 |
| `frontend/redesign-v1/dist/index.html` | `70ab179ed0380a9d6808efcbe5f02cd8db404f6f0c5c80d79ca138bbf04a4102` | 900 |


### 3. 配置檔與文檔 (20 檔)
| 相對路徑 | SHA-256 雜湊碼 | 大小 (Bytes) |
| :--- | :--- | :--- |
| `frontend/redesign-v1/HANDOFF.md` | `7a97147141238c7c7429e5591a9f5c176463b73f3d977091a529a01394e215cb` | 4,993 |
| `frontend/redesign-v1/index.html` | `105b7c31b2020c45590dd5cd3bf6400ec05ed448f365e06e0cdff418ebd5c9a0` | 801 |
| `frontend/redesign-v1/js/api-adapter-spec.js` | `639ced4d66180d218f8d1e452152e92db05ba24fe4ea775557cef3019b50c71a` | 2,855 |
| `frontend/redesign-v1/js/app.js` | `88ceb631c0e257961bf703b19bc91c9379ea0ed103bd54e057d08d69e39fe81b` | 6,478 |
| `frontend/redesign-v1/js/charts.js` | `864bae4c44e2debbb40d678ee0d55216c3f2132dc01d989674ca60bfbc9aff25` | 6,431 |
| `frontend/redesign-v1/js/components.js` | `0973058e8039e2ed349edf02460b6675c72334a9c9076f4dc3f1a7e7317ab534` | 1,551 |
| `frontend/redesign-v1/js/mock-adapter.js` | `2a01b46349f2ca26a2485e268755a4f88c86ada564c42dfe2b3bb03ec7563218` | 2,442 |
| `frontend/redesign-v1/mock/models.js` | `59dd321e7445551bd3815869776322af18009aafb2f26e5ef81021f0a4e50d35` | 1,899 |
| `frontend/redesign-v1/mock/scenarios.js` | `fb6041fb8d6699d04dc534f4382026c325f20d67e17c8094b4409d866094dfda` | 14,631 |
| `frontend/redesign-v1/package-lock.json` | `524e1bf5f3a43984555e139defd7cf377abc7f2c5ec138c06a4952a03a347769` | 64,087 |
| `frontend/redesign-v1/package.json` | `08d11f2ae5d25684dfe3dc7358f15768f683ba3b5f1450d21c7f03fba8451cce` | 560 |
| `frontend/redesign-v1/README.md` | `d3cd64af1d17f564bad6eea68e96427bde83a821353799ab059ec00ba99403b8` | 5,896 |
| `frontend/redesign-v1/scripts/verify-ui.js` | `c845e0d40387e149dc3590c32dcc183f318d14310c4e4bec0a8599dbb1f5b24a` | 6,705 |
| `frontend/redesign-v1/styles/components.css` | `15c367b3af05adb2304334b0153955ced5d9e1f783cb9f3ee51018b992b49f92` | 14,542 |
| `frontend/redesign-v1/styles/layout-a.css` | `5103cc627e260a2ebe5812ee453a93398cd36d69f92441df6ba08aabf2aa81f7` | 2,963 |
| `frontend/redesign-v1/styles/layout-b.css` | `d585586f577f5307cbed3654eabe6ef7d8b44c6080721e8e031b98a4e6192865` | 4,257 |
| `frontend/redesign-v1/styles/theme.css` | `a1eab9561d5da1ee5117c3640209c3706ad45e7cdcff24bfd242e20aa389711b` | 3,211 |
| `frontend/redesign-v1/tsconfig.json` | `c17ec21d3ce6290df3180d1c648914c50a19ea7dfb8b11c063966caf351536a5` | 572 |
| `frontend/redesign-v1/tsconfig.node.json` | `b5805e4738367879e03012a1807daba34fc4dfbfab445472529f2611d4d41fb0` | 233 |
| `frontend/redesign-v1/vite.config.ts` | `fc54f178691dd4f6d22808ecad04ce6c09dc428fc72d02ae19b07ff08a205395` | 560 |


### 4. 瀏覽器截圖與證據 (`evidence/` - 28 檔)
| 相對路徑 | SHA-256 雜湊碼 | 大小 (Bytes) |
| :--- | :--- | :--- |
| `frontend/redesign-v1/evidence/bots_modal_vue_1440.png` | `74ef793d9a4c98c1e7788870dd5bfa1f6e3c2dce6e01527cce7205ceca3d6f21` | 111,688 |
| `frontend/redesign-v1/evidence/bots_vue_1440.png` | `5bbcfcf870c553efd5c1eba19036b99045d5b7a22a69630e4792e3b28b8f8021` | 92,262 |
| `frontend/redesign-v1/evidence/layout_a_1280.png` | `d42f883861dd2a279f2398c8c1582ae168e1ea90c5efc53ed42fce2fb6077348` | 145,540 |
| `frontend/redesign-v1/evidence/layout_a_1440.png` | `44398819d17b241d406b7ea3186e5fa25be973a84054e5b8c2aeeeb8a7904137` | 194,647 |
| `frontend/redesign-v1/evidence/layout_a_409_locked_1440.png` | `80fdab7f836dc54d70edd107540c4e4d1eefc1262c38124b1e95bb57e7c6914b` | 169,386 |
| `frontend/redesign-v1/evidence/layout_a_768.png` | `1fcb11520afbe8ff17ace9386607bb7d5aa0b44eb4794009e947e3d866215503` | 155,471 |
| `frontend/redesign-v1/evidence/layout_a_authentic_1280.png` | `598ae0f131558d58e136852ed5217ddc59808ccae1cf7b41151869283f9078e9` | 219,600 |
| `frontend/redesign-v1/evidence/layout_a_authentic_1440.png` | `bc05dc8cddce2b34f36afe7c2dd32bbfeac1a3587e6a0b754ee852a49f644d08` | 224,093 |
| `frontend/redesign-v1/evidence/layout_a_authentic_768.png` | `4cd726d04058265e91772992adc73684a38fe2d2eaf97d835c570ccf2b35ccf9` | 200,794 |
| `frontend/redesign-v1/evidence/layout_a_authentic_popover_1440.png` | `33abf71488d1b2b375f8330577ac841b7afa25532905fff52ff7763335944a78` | 238,411 |
| `frontend/redesign-v1/evidence/layout_a_empty_standby_1440.png` | `e42d34fb57188b9421eecb311eeb6a8ae36bb91bfd2b07f9e591c8677d43ec70` | 120,776 |
| `frontend/redesign-v1/evidence/layout_a_popover_1440.png` | `6d1b85bdee521f98a3d5f6606ba5f4b9441ec7dc6d085815e4aa76efc7d8599a` | 210,640 |
| `frontend/redesign-v1/evidence/layout_a_recovery_1440.png` | `076644796e6b14fd73aed9d615aaf30f79d533f247e8bff8090b44dd8cf0cf93` | 160,953 |
| `frontend/redesign-v1/evidence/layout_a_vue_1280.png` | `e7dfddeb6adb1f64b131086dafe4615c6ba71ae5402914d9e1098125856bdff4` | 156,776 |
| `frontend/redesign-v1/evidence/layout_a_vue_1440.png` | `04050915f715cdfbb44ca472891f81e4416284234af369633fcb1a9e810eb13f` | 204,940 |
| `frontend/redesign-v1/evidence/layout_a_vue_768.png` | `239c7405c517d36bccde1e2c37d7715ca41a5b3be54f67b91b79fee3ce2c3b6c` | 131,483 |
| `frontend/redesign-v1/evidence/layout_b_1280.png` | `fa8fabbd2010a6db7a503014efca89577d76b89d25e91582ae8a274cf20ac3f4` | 139,406 |
| `frontend/redesign-v1/evidence/layout_b_1440.png` | `0b45168bf44a4f4958ca33b9b9d17b7f989711a744b7057e835c3b3d5a5ee4c7` | 153,587 |
| `frontend/redesign-v1/evidence/layout_b_768.png` | `38cba4e1ef5287b548d6960fdd1b5cdc34621471b2d56fafaec6e4d70a454aaf` | 131,466 |
| `frontend/redesign-v1/evidence/layout_b_vue_1440.png` | `3e973836de081ea80c0b34d3ca4aabcd45f270a439fcd55b6450684cb0226168` | 189,612 |
| `frontend/redesign-v1/evidence/logs_vue_1440.png` | `f018cc6d1f368e7d3b7f0faaedd95f9f9de3b388e13608e8b4556018d5dc3ef5` | 90,535 |
| `frontend/redesign-v1/evidence/market_intel_vue_1440.png` | `0c224aa6697cb3a263c9af22eefd56a79f297ff8ebc1656076bf06e9713f7aca` | 80,999 |
| `frontend/redesign-v1/evidence/risk_vue_1440.png` | `4fb40b7ec27eda776bc6cf7a0522bcef89602dcddca656f39eb0f7fdf7c8eb4a` | 117,647 |
| `frontend/redesign-v1/evidence/scenario_empty_1440.png` | `1a329b5f17ef54405c95ad67007353eaa5a77e9b3d47c77a55487a604bff7471` | 144,619 |
| `frontend/redesign-v1/evidence/scenario_hold_stopped_1440.png` | `237d2d839b548426ea3df81c4757d21791b795454f4f9d4db1ed5094e1226429` | 205,765 |
| `frontend/redesign-v1/evidence/scenario_soft_loss_1440.png` | `9cc98145c7398b8eab0390aebab807ec0fa48ebbd285416c67c33ab5502fda2b` | 207,188 |
| `frontend/redesign-v1/evidence/settings_vue_1440.png` | `45becbca7ad74cad413a91745d5e3d9fa07c1146beb381f419069dc6d3b3b2b6` | 86,836 |
| `frontend/redesign-v1/evidence/strategies_vue_1440.png` | `b684b0e575496a3b8a0c4fab2d7dfb576d0a9075f1e1fa8a74536b82929271e1` | 117,806 |


### 5. 舊版備份檔案 (`legacy_vanilla/` - 14 檔)
| 相對路徑 | SHA-256 雜湊碼 | 大小 (Bytes) |
| :--- | :--- | :--- |
| `frontend/redesign-v1/legacy_vanilla/HANDOFF.md` | `bfd613549376057224e918dfbadb25d00783f729fdebfe0242795b20dc7d0a9c` | 3,814 |
| `frontend/redesign-v1/legacy_vanilla/index.html` | `771cbdc1df6db0d4daace1ea0e07145107b43afaeda0b179150ca8e1506c934b` | 28,336 |
| `frontend/redesign-v1/legacy_vanilla/js/api-adapter-spec.js` | `639ced4d66180d218f8d1e452152e92db05ba24fe4ea775557cef3019b50c71a` | 2,855 |
| `frontend/redesign-v1/legacy_vanilla/js/app.js` | `88ceb631c0e257961bf703b19bc91c9379ea0ed103bd54e057d08d69e39fe81b` | 6,478 |
| `frontend/redesign-v1/legacy_vanilla/js/charts.js` | `864bae4c44e2debbb40d678ee0d55216c3f2132dc01d989674ca60bfbc9aff25` | 6,431 |
| `frontend/redesign-v1/legacy_vanilla/js/components.js` | `0973058e8039e2ed349edf02460b6675c72334a9c9076f4dc3f1a7e7317ab534` | 1,551 |
| `frontend/redesign-v1/legacy_vanilla/js/mock-adapter.js` | `2a01b46349f2ca26a2485e268755a4f88c86ada564c42dfe2b3bb03ec7563218` | 2,442 |
| `frontend/redesign-v1/legacy_vanilla/mock/models.js` | `59dd321e7445551bd3815869776322af18009aafb2f26e5ef81021f0a4e50d35` | 1,899 |
| `frontend/redesign-v1/legacy_vanilla/mock/scenarios.js` | `fb6041fb8d6699d04dc534f4382026c325f20d67e17c8094b4409d866094dfda` | 14,631 |
| `frontend/redesign-v1/legacy_vanilla/README.md` | `024e0b7e8e80b995b8a6937c573ae3984216e991e51dfbef48d21b7cdc6e5375` | 3,614 |
| `frontend/redesign-v1/legacy_vanilla/styles/components.css` | `15c367b3af05adb2304334b0153955ced5d9e1f783cb9f3ee51018b992b49f92` | 14,542 |
| `frontend/redesign-v1/legacy_vanilla/styles/layout-a.css` | `5103cc627e260a2ebe5812ee453a93398cd36d69f92441df6ba08aabf2aa81f7` | 2,963 |
| `frontend/redesign-v1/legacy_vanilla/styles/layout-b.css` | `d585586f577f5307cbed3654eabe6ef7d8b44c6080721e8e031b98a4e6192865` | 4,257 |
| `frontend/redesign-v1/legacy_vanilla/styles/theme.css` | `a1eab9561d5da1ee5117c3640209c3706ad45e7cdcff24bfd242e20aa389711b` | 3,211 |


---

## 九、可供第三方重現驗證之前端 ZIP 交付包

為使接手開發者（本機 Codex / WorkBuddy / 外部驗證角色）能夠在純淨環境下完整重現建置與自動化驗證，已打包封裝獨立交付 ZIP：

- **ZIP 檔案相對路徑**：`frontend/catos-frontend-redesign-v1.zip`
- **檔案大小**：`4,475,257 Bytes`（約 4.27 MB）
- **SHA-256 雜湊碼**：`4ee07bb80eca1f172c04a28bc17fab0321ed9a0e0d82b0887a0c4155043cc897`
- **封裝內容驗證**：
  - ✅ 包含全部原始碼 (`src/`)、樣式 (`styles/`)、契約模型 (`contracts/`)、Mock Adapter (`adapters/`)、狀態管理 (`state/`)、頁面與元件。
  - ✅ 包含生產打包輸出 (`dist/`)、依賴鎖定檔 (`package.json`, `package-lock.json`)、設定檔 (`tsconfig.json`, `vite.config.ts`, `index.html`)。
  - ✅ 包含說明與指引文檔 (`README.md`, `HANDOFF.md`, `VERIFICATION_RUN.md`)。
  - ✅ 包含瀏覽器自動化驗證腳本 (`scripts/verify-ui.js`) 與截圖存證 (`evidence/*.png`)。
  - ✅ 包含舊版原生 JS 原型備份 (`legacy_vanilla/`)。
  - ❌ **嚴格排除**：`node_modules/`（零殘留）、`.git/`、任何 SQLite 資料庫檔 (`*.db`, `*.sqlite`, `*.sqlite3`, `*-wal`, `*-shm`)、任何憑證/金鑰、`.env`。已由 `scripts/check-zip.ps1` 驗證 `Bad/Sensitive entries in zip: 0`。

### 🚨 誠實明示本輪所有未驗項目（Unverified Items Declaration）

依 `AGENTS.md` 規範，本輪僅為純前端重構與瀏覽器渲染驗證，**絕不以 Mock 或 build 通過宣稱核心流程通過**。以下核心項目完全未經本輪驗證：

1. **真實 FastAPI/HTTP API 端點對接**：尚未對真實 `http://127.0.0.1:8770` 或 `8771` 進行實測。
2. **真實 Worker 行程生命週期與 IPC 通訊**：Worker 的啟動、監視、退場與 JSON IPC 未經真實進程驗證。
3. **真實 OKX 交易所連線與 SWAP 下單**：未對 OKX 發送真實或模擬網路請求；固定委託標籤 `"tag": "41cb53c54d6dABDE"` 尚未於交易所端反射驗證。
4. **真實 SQLite WAL 交易流水與快照對帳**：未進行資料庫持久化、WAL 併發或重啟對帳實測。
5. **真實日損 Soft/Hard 熔斷連鎖反應**：日損儀表展示未與 Supervisor 市價清倉、Kill-Switch 鎖存聯動實測。
6. **真實合約獨佔（409 衝突）後端拒絕**：合約獨佔未釋放展示未經後端交易層實際 HTTP 409 回應檢驗。
7. **真實 MCP 策略製品建立與匯入**：外部 AI 經 MCP 建立 `catos.python-strategy.v1` 之完整工具鏈未在本輪執行。
8. **真實帳戶與資金安全保證**：高精度 Decimal 字串未在後端對帳系統進行跨進程數值精確度驗證。

---

## 十、後續整合與交接建議

1. **請使用者選定 Dashboard 布局**：
   - **偏好「多視圖並行比對」**：推薦 **布局 A（完整多面板）**。
   - **偏好「大圖表流暢聚焦」**：推薦 **布局 B（閱讀焦點集中）**。
2. **靜態檔案托管接線 (本機 Codex)**：
   - 現有 Python localhost 服務可直接將靜態檔案根目錄指定至 `frontend/redesign-v1/dist/`，或在開發環境直接執行 `npm run preview`（或 `npm run dev`）。
3. **HTTP Adapter 替換**：
   - 既有 `src/adapters/types.ts` 定義了完整資料與控制介面，日後只需實作 `http-adapter.ts` 呼叫既有 FastAPI 端點，即可完成無縫切換，頁面與元件層無須變更任何代碼。
4. **獨立驗收與 Git 核對 (WorkBuddy)**：
   - 本次回傳不含任何 Git commit 操作；所有檔案均就緒於工作目錄，靜候 WorkBuddy 進行規格與雜湊核對。

