# catOS 新前端 (redesign-v1)

本目錄為 catOS 本機量化交易系統的前端架構，採用 **Vue 3 + TypeScript (strict) + Vite + Vue Router** 構建，樣式完全採用原生 CSS 與 CSS Variables 設計系統（對齊 `catOS-Frontend-Final` 經典深色板岩 Slate + 曜石香檳金 Obsidian Champagne Gold）。

交付形式為靜態打包檔（Static Build Artifacts），由既有 Python localhost 服務直接托管，不需常駐 Node.js 服務，不引進 SSR、Docker 或第二個後端。

---

## 一、技術棧與架構

- **框架**：Vue 3 (Composition API / `<script setup>`)
- **語言**：TypeScript (啟用 `strict: true`、`noEmit: true`)
- **建置工具**：Vite 6 (`base: './'`, `host: '127.0.0.1'`, `strictPort: true`)
- **路由**：Vue Router 4 (Hash History `createWebHashHistory`，確保靜態伺服器零重寫依賴)
- **設計系統**：原生 CSS 與 CSS Variables（`tokens.css`、`base.css`、`components.css`）
- **字體規範**：
  - 介面文字：`Inter`、`Noto Sans TC`
  - 數值／點位／時間戳：`JetBrains Mono`（強制 `font-variant-numeric: tabular-nums`）
- **金融原則**：金額、價格、部位、費用與保證金均以字串處理，前端不重算風控、不作為金融真值。

---

## 二、目錄結構

```
frontend/redesign-v1/
├── index.html              # Vite 靜態首頁入口
├── package.json            # 依賴與腳本定義
├── package-lock.json       # 精確鎖定版本
├── tsconfig.json           # TypeScript strict 配置
├── tsconfig.node.json      # Node/Vite TS 配置
├── vite.config.ts          # Vite 配置（嚴格綁定 127.0.0.1:8899）
├── src/
│   ├── env.d.ts            # 環境型別聲明
│   ├── main.ts             # 應用程式掛載入口
│   ├── App.vue             # 外層工作區 Shell（側邊欄 + 頂部導航）
│   ├── contracts/          # 後端資料與控制契約 (TypeScript)
│   │   ├── strategy.ts     # catos.python-strategy.v1 契約
│   │   ├── bot.ts          # Bot 狀態、生命週期與綁定契約
│   │   ├── run.ts          # 模擬執行成果契約 (Decimal 字串)
│   │   ├── risk.ts         # 風控與日損鎖存契約 (固定 Tag 41cb53c54d6dABDE)
│   │   ├── command.ts      # 冪等控制命令與稽核日誌契約
│   │   ├── workspace.ts    # 遙測與工作區模式契約
│   │   └── index.ts
│   ├── adapters/           # 資料獲取與控制 Adapter
│   │   ├── types.ts        # WorkspaceAdapter 統一介面
│   │   ├── mock-adapter.ts # Mock Adapter (情境切換、命令防誤觸追蹤)
│   │   └── index.ts
│   ├── state/              # Vue Reactive Composables
│   │   ├── useWorkspace.ts # 工作區模式、遙測狀態
│   │   ├── usePreferences.ts # localStorage 展示偏好 (版本化、無效值回退)
│   │   ├── useDashboard.ts # 儀表板資料載入與監聽
│   │   └── useCommandLog.ts# 控制命令追蹤
│   ├── styles/             # 設計系統樣式
│   │   ├── tokens.css      # 色彩、圓角、間距、字體 Tokens
│   │   ├── base.css        # Reset、捲軸、字體設定
│   │   └── components.css  # 卡片、按鈕、表格、標籤、彈窗等
│   ├── components/         # 共用組件
│   │   ├── common/
│   │   │   ├── StatusBadge.vue    # 狀態標籤 (語意色解耦)
│   │   │   ├── ModeSelector.vue   # 本機 / Demo / Live 切換
│   │   │   ├── TelemetryPopover.vue # 核心底座遙測彈出面板
│   │   │   ├── MetricCard.vue     # KPI 數值卡片
│   │   │   ├── SparklineArea.vue  # SVG 淨值平滑面積折線圖
│   │   │   ├── DonutChart.vue     # SVG 甜甜圈比例圖
│   │   │   ├── RiskGauge.vue      # 4 段式彩條日損安全儀表
│   │   │   ├── ScenarioBar.vue    # 5 態展示情境與 A/B 布局切換列
│   │   │   └── EmptyState.vue     # 乾淨空狀態組件
│   │   └── dashboard/
│   │       ├── DashboardLayoutA.vue # 布局 A：完整多面板工作區
│   │       └── DashboardLayoutB.vue # 布局 B：閱讀焦點集中
│   └── pages/              # 各產品頁面
│       ├── DashboardPage.vue      # 戰情總覽首頁
│       ├── StrategiesPage.vue     # 策略中心 (不可變版本審查)
│       ├── BotsPage.vue           # 機器人管理 (人工信任分配與啟停)
│       ├── RiskPage.vue           # 風險控管
│       ├── LogsPage.vue           # 系統日誌與稽核日誌
│       ├── MarketIntelPage.vue    # 市場情報 / Yaozi (標註開發中)
│       └── SettingsPage.vue       # 系統設定 (重設展示偏好入口)
├── scripts/
│   └── verify-ui.js        # Puppeteer 自動化驗證與多解析度截圖腳本
├── evidence/               # 驗收截圖存證目錄
└── legacy_vanilla/         # 歷史原生 JS 原型完整封存
```

---

## 三、常用指令

### 1. 安裝依賴
```powershell
npm install
```

### 2. 本地開發伺服器 (Vite Dev Server)
嚴格綁定 `127.0.0.1:8899`，啟用 `strictPort: true`：
```powershell
npm run dev
```

### 3. TypeScript 嚴格檢查 (Strict Mode)
```powershell
npm run typecheck
```

### 4. 正式打包 (Production Build)
輸出至 `dist/`，包含 HTML、CSS 與 JS：
```powershell
npm run build
```

### 5. 本機預覽 (Preview Production Build)
```powershell
npm run preview
```

### 6. 自動化 UI 渲染與截圖驗證
透過本地 Chrome 進行全功能與多解析度截圖驗證：
```powershell
node scripts/verify-ui.js
```
