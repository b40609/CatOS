# catOS React 19 + Vite Frontend Handoff for GPT-6.1

## 1. 專案概述 (Project Overview)
本目錄 `frontend/cat-os-vite/` 是依據最新 `frontend/lovable-reference/`（Crypto Zen Terminal）視覺基準完成的 **React 19 + Vite 6 + Tailwind CSS v4 + Radix UI** 純靜態 SPA，專為本機量化交易終端 catOS 設計。

- **建置產物**：純靜態 HTML/CSS/JS（`dist/`），可直接由 FastAPI (`127.0.0.1`) 靜態託管，**禁止常駐 Node.js 或 SSR**。
- **路由機制**：採用零依賴 Hash Router（`#/`, `#/bots`, `#/risk` 等），與 FastAPI static mount 天然相容，徹底杜絕 SPA 重新整理 404 問題。
- **金融底線**：所有金額、部位與槓桿數值在前端一律以 **Decimal 字串** 傳遞，嚴格禁止任何浮點數 (`float`) 算術回流為帳務依據。

---

## 2. 目錄結構與關鍵模組 (Directory Structure)

```text
frontend/cat-os-vite/
├── index.html                  # SPA HTML 入口 (包含 JetBrains Mono & Work Sans 字型)
├── vite.config.ts              # Vite 6 + Tailwind v4 配置，支援 @/ 別名與路由 alias
├── tsconfig.json               # TypeScript Strict 嚴格模式
├── package.json                # React 19, Radix UI, Zustand, Lightweight Charts
└── src/
    ├── main.tsx                # React Root 掛載
    ├── App.tsx                 # 頁面路由分發與 StateAdapter 初始化
    ├── styles/
    │   └── globals.css         # catOS Noir & Gold 設計系統 (Tailwind v4 @theme inline)
    ├── contracts/              # 8 大金融資料契約 (與 Python Supervisor 契約嚴格對齊)
    │   ├── bot.ts              # Bot 實例模型、BotMode ('local' | 'demo' | 'live')
    │   ├── risk.ts             # RiskState、日損鎖存標記、槓桿預算
    │   ├── strategy.ts         # StrategyArtifact、參數模型、Canonical JSON
    │   ├── validator.ts        # 嚴格驗證器 (禁止 float、深度 <= 2、SHA-256)
    │   └── workspace.ts        # TelemetryState、VersionDTO
    ├── adapters/
    │   ├── types.ts            # WorkspaceAdapter 介面、DashboardKPIs、ScenarioType
    │   └── mock-adapter.ts     # 6 大隔離模擬情境 (normal, soft_loss, hold_stopped_409 等)
    ├── state/
    │   ├── catStore.ts         # Zustand 集中式狀態儲存，支援細粒度 Selector
    │   └── stateAdapter.ts     # 防錯序 State Adapter (Monotonic Version Guard)
    ├── pages/                  # 10 大完整分頁 (直接繼承 Lovable 視覺)
    │   ├── index.tsx           # Dashboard (戰情總覽、報價條、持倉表、即時成交)
    │   ├── bots.tsx            # Bots (機器人管理、部署彈窗、啟停控制)
    │   ├── risk.tsx            # Risk (風控中心、槓桿滑桿、熔斷警報)
    │   ├── strategies.tsx      # Strategies (策略庫、年化報酬、夏普比率)
    │   ├── logs.tsx            # Logs (系統審計串流、關鍵字過濾)
    │   └── ...                 # Backtest, Optimization, Market Intel, Settings
    ├── components/
    │   ├── catos/              # 終端機 Shell、AccountMenu、導覽列
    │   └── ui/                 # 46 個完整 Radix UI 視覺元件
    └── lib/
        ├── router.tsx          # 輕量 Hash Router 實作
        └── utils.ts            # cn() 與 ClassName 工具
```

---

## 3. 接手指南：GPT-6.1 如何接入真實後端？(Integration Guide for GPT-6.1)

目前前端已封裝好完整的狀態適配層，GPT-6.1 接手後**不需要重構 UI**，只需按以下步驟接線：

### A. 實作真實 WebSocket 串接
在 `src/state/stateAdapter.ts` 接入 WebSocket 客戶端：
```typescript
// 當收到 WebSocket 行情或狀態事件時：
stateAdapter.handleEvent({
  domain: 'bots', // 或 'risk', 'kpis', 'telemetry'
  version: incomingEvent.version, // 後端單調遞增版本號
  payload: incomingEvent.data,
});
```
> **安全機制**：State Adapter 內建 `applyAuthoritativeUpdate`，如果舊的 REST 回應比 WebSocket 慢抵達，版本檢查會自動阻擋過期資料，保證前端畫面不會回彈。

### B. 實作 REST 命令呼叫
在 `src/adapters/` 建立 `real-adapter.ts` 實作 `WorkspaceAdapter` 介面（可參考 `mock-adapter.ts`），將 `fetchBotQueue()`、`startBot()`、`stopBot()` 替換為真實 `fetch('http://127.0.0.1:8770/api/...')`。

---

## 4. 本地自測命令 (Verification Commands)

在 `frontend/cat-os-vite/` 目錄下執行：
* **型別檢查**：`npm run typecheck`（當前：0 錯誤，Strict 通過）
* **正式打包**：`npm run build`（當前：11.9s 成功輸出至 `dist/`，模組數 2330）
* **本機開發**：`npm run dev`
* **本機預覽**：`npm run preview`（預設運行於 8890 埠）
* **單元測試**：`node tests/state_adapter_test.mjs`（當前：3/3 PASS）
