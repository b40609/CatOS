# catOS 前端搬移返還交接文件 (Frontend Return Handoff)

- **交接日期**：2026-10-04
- **當前開發完成度**：約 65%（前端架構、視覺系統、九大分頁、零浪費佈局、拖曳幽靈磚與狀態化 Mock 已完整成型，後端真實接線、回測核心與進階歷史還原待原電腦接續）
- **交付目標**：提供明天搬回原本 Windows 電腦繼續開發的完整整理、客觀完成度記錄、驗證證據與無污染乾淨原始碼打包。
- **嚴守邊界**：無擅自重構、無破壞性修改、維持現有 Vue 3 + TypeScript strict + Vite + 原生 CSS Variables 架構；不把 Mock 成功冒稱為後端整合通過。

---

## 一、目前使用之來源目錄、入口與啟動方式

1. **目前專案絕對路徑**：
   - 本機路徑：`C:\Users\kai\Desktop\CatOS_Astra`
2. **目前實際使用之新前端來源目錄**：
   - 目錄路徑：`C:\Users\kai\Desktop\CatOS_Astra\frontend\redesign-v1`
   - *（註：同專案下 `frontend/workspace` 為舊版 Vanilla JS 工作區，`frontend/research` 為舊版研究切片，目前主要活躍重做版本唯一為 `frontend/redesign-v1`）*
3. **首頁入口**：
   - 原始碼入口：`frontend/redesign-v1/index.html` -> `frontend/redesign-v1/src/main.ts` -> `App.vue`
   - 路由入口：`src/router/index.ts`（使用 Hash 路由 `/#/`，首頁對應 `DashboardPage.vue`）
4. **當前預覽服務狀況與啟動命令**：
   - 目前運行中服務：`http://127.0.0.1:8899/`
   - 運行程序 PID：`5140`（Command: `"node" ...\vite\bin\vite.js preview --host 127.0.0.1 --port 8899`，工作目錄 `frontend/redesign-v1`）
   - 開發環境啟動命令（原電腦）：
     ```bash
     cd frontend/redesign-v1
     npm run dev
     # 或本機預覽既有 build:
     npm run preview
     ```

---

## 二、各頁面詳細完成狀態矩陣

| 頁面名稱 | 路由路徑 | 視覺狀態 | 互動狀態 | 資料模式 | 後端接線與驗證 | 綜合狀態評定 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **系統總覽 (Dashboard)** | `#/` | **已完成** (Zero-Waste 頂部合一) | **已完成** (方案1幽靈磚拖曳、分割縮放、雙模式切換、情境切換) | **僅 Mock** (`useDashboard`, `useWorkspace`) | **未接後端** (未連接真實 Supervisor/8770) | **視覺與互動已完成 / 僅 Mock** |
| **策略中心 (Strategies)** | `#/strategies` | **已完成** (左側版本清單 + 右側不可變製品詳情) | **已完成** (檔案上傳讀取、解析、原型預檢、新增版本入庫) | **僅 Mock** (Local Client Storage) | **未接後端** (未送後端 AST 驗證，徽章標註示意) | **視覺與互動已完成 / 僅 Mock** |
| **機器人管理 (Bots)** | `#/bots` | **已完成** (實例表格 + Worker 監視 + 即時串流 + 歷史抽屜) | **已完成** (分配表單、信任重置、啟動/停止、原命令重送) | **僅 Mock** (`catos_mock_storage_v2`) | **未接後端** (無真實 Python Worker 進程) | **視覺與互動已完成 / 僅 Mock** |
| **風控中心 (Risk)** | `#/risk` | **已完成** (安全儀表板 + 不變量清單 + 單幣預算進度) | **已完成** (緊急 Kill-Switch 模擬彈窗、多幣種曝險計算) | **僅 Mock** (預設與情境驅動) | **未接後端** (未連接真實風控底座) | **視覺與互動已完成 / 僅 Mock** |
| **系統日誌 (Logs)** | `#/logs` | **已完成** (雙欄：審計串流 + 前端發送命令紀錄) | **已完成** (類別篩選 ALL/RISK/ORDER/WORKER、即時關鍵字搜尋) | **僅 Mock** (客戶端命令日誌捕獲) | **未接後端** (未接真實 SQLite journal) | **視覺與互動已完成 / 僅 Mock** |
| **市場情報 (Market Intel)** | `#/market-intel` | **已完成** (Yaozi 預警卡片 + 資金費率矩陣 + 巨鯨流) | **已完成** (獨立情報分頁標籤、列表捲動) | **僅 Mock** (靜態情資展示) | **未接後端** (未接 Yaozi 實時爬蟲或 websocket) | **視覺完成 / 僅 Mock** |
| **系統設定 (Settings)** | `#/settings` | **已完成** (佈局引擎切換、側邊欄樣式、圖表範圍等) | **已完成** (偏好即時響應、持久化儲存、一鍵重設) | **純前端狀態** (`usePreferences`) | **無須後端** (純前端偏好管理) | **功能完整** |
| **歷史回測 (Backtest)** | `#/backtest` | **已完成** (頂部 KPI + 歷史清單 + 淨值走勢與明細) | **尚未完成** (僅支援點選歷史項目切換展示，無回測發起) | **僅 Mock** (靜態範例資料) | **未接後端** (未接 Jesse/Decimal 回測核心) | **僅 Mock / 開發中** |
| **參數優化 (Optimization)** | `#/optimization` | **已完成** (目標策略總覽 + 搜尋空間定義 + 排行榜) | **尚未完成** (無任務發起與 Optuna 引擎排程) | **僅 Mock** (靜態 trial 數值) | **未接後端** (未接 Optuna 最佳化) | **僅 Mock / 開發中** |

---

## 三、已確認滿意、必須完整保留的設計

1. **頂部合一資訊架構 (Zero-Waste Layout - 方案 A 定案)**：
   - 側邊欄與全域 Header 一體化，微型標題 + Teleport 動作按鈕置於頂部 Header 右側。
   - 徹底消除頁面內部重複的巨大 H2 標題與橫幅（零 Triple Redundancy），釋放 80px 垂直視野。
2. **工作台卡片佈局與互動（方案 1：✦ 動態幽靈佔位磚 定案）**：
   - 拖曳卡片時動態展開 170px 金屬半透明發光佔位磚（`expandGhostSlot` 動畫），兩側自然撐開。
   - 連續無死區中點分區演算法（Continuous Voronoi Midpoint Partitioning），左拖平滑無跳躍。
   - 連續無縫分割線推擠縮放（Splitter Cascading Resize）與右上角單卡最大化聚焦。
   - 雙模式切換：平常「檢視鎖定模式」防誤觸，點擊「微調編輯」解鎖把手與對齊導軌。
3. **視覺語彙與主題**：
   - 極致深邃黑底（`#080a0d` / `#0e1218`）搭配黑曜石香檳金（Obsidian Champagne Gold `#dcb347`）。
   - 語意顏色（成功綠 `#2ea043`、危險紅 `#f85149`、預警黃 `#d29922`、資訊藍 `#58a6ff`）與主色調嚴格解耦。
   - 等寬數字與表格字元排版（Tabular Numerals，`JetBrains Mono`）。
4. **側邊欄微互動與彈性縮放**：
   - 側邊欄右側邊界指針拖曳調整寬度（190px ~ 420px，雙擊還原 245px，小於 135px 自動折疊）。
   - 模式切換器（Local / Demo / Live）緊密置於側邊欄 LOGO 旁，切換時具有專屬隔離警示。

---

## 四、尚待微調項目與已知 Bug（附重現步驟）

1. **Bug 1：index.html 存在外部 Google Fonts 外鏈**
   - **重現步驟**：開啟 `frontend/redesign-v1/index.html` 第 8~10 行。
   - **現象**：包含 `fonts.googleapis.com` 連結。雖然 `base.css` 與 `tokens.css` 已配置本機系統字型 fallback，但在完全離線無網環境下，外部連線請求會超時或報錯。
   - **微調建議**：原電腦接續時，可將 Google Fonts `<link>` 移除，完全依賴本機無襯線/等寬字型堆疊。
2. **Bug 2：歷史回測與參數優化按鈕點擊無回饋**
   - **重現步驟**：進入 `#/backtest` 或 `#/optimization`，點擊頂部「+ 發起新回測任務」或「+ 發起優化任務」。
   - **現象**：按鈕無綁定點擊事件（未出現 modal 或執行狀態），頁面停留在 Mock 靜態成果。
   - **微調建議**：原電腦應加上「功能開發中」提示 Modal 或連接後端研究 CLI / Optuna 任務通道。
3. **Bug 3：側邊欄快速收合時的微小閃爍**
   - **重現步驟**：拖曳側邊欄寬度低於 135px 觸發自動折疊，再快速雙擊展開。
   - **現象**：寬度轉換動畫有約 50ms 的寬度突變。
   - **微調建議**：微調 `transition: width 0.2s cubic-bezier(0.4, 0, 0.2, 1)`。

---

## 五、Mock 與真實 API 的切換位置與預設模式

1. **切換進入點**：
   - 檔案路徑：`frontend/redesign-v1/src/adapters/index.ts`
   - 目前內容：
     ```typescript
     export * from './types';
     export * from './mock-adapter';
     ```
2. **當前預設模式**：
   - **純 Mock 狀態**（導出 `activeAdapter = new MockWorkspaceAdapter('normal')`）。
   - 本地儲存鍵值：LocalStorage `catos_mock_storage_v2`，SessionStorage `catos_simulation_pending_v1`。
3. **切換為真實 API 之對接架構**：
   - 依據 `HANDOFF.md` 第二節設計，需建立 `src/adapters/http-adapter.ts` 實作 `WorkspaceAdapter` 介面。
   - 該 Adapter 負責對接真實 FastAPI 端點（`GET /version`, `GET /strategies`, `GET /bots`, `GET /runs`, `POST /bots`, `POST /runs/{id}/stop`），並將 Raw DTO 映射轉換為 View Model。
   - 頁面元件（`BotsPage.vue` 等）僅消費抽象介面，不直接依賴 concrete Mock。

---

## 六、原電腦接續開發所需指令與工具版本

1. **開發環境必要版本**：
   - 作業系統：Windows 10 / 11
   - Node.js：`>= v20.x`（本機實測通過環境為 `v24.19.0`）
   - npm：`>= 10.x`（本機實測通過環境為 `11.17.0`）
   - TypeScript：`^5.7.2`
   - Vite：`^6.0.1`
2. **解壓後接續步驟**：
   ```bash
   # 1. 進入解壓目錄（假設為獨立目錄，例如 catos-frontend-return/）
   cd catos-frontend-return

   # 2. 乾淨安裝相依套件（依據 package-lock.json）
   npm ci --no-audit --no-fund

   # 3. 執行 TypeScript strict 型別檢查
   npm run typecheck
   # 或直接執行: node node_modules/vue-tsc/bin/vue-tsc.js --noEmit

   # 4. 執行 production build
   npm run build

   # 5. 啟動本機開發伺服器
   npm run dev
   # 預設開啟於 127.0.0.1:8899
   ```

---

## 七、硬編碼磁碟路徑、埠、遠端字體、CDN 與跨電腦依賴清查

| 依賴項目 | 檔案與位置 | 現狀描述 | 跨電腦影響與處理指引 |
| :--- | :--- | :--- | :--- |
| **遠端字體 (Google Fonts)** | `index.html:10` | 引用 Google Fonts (Inter, JetBrains Mono, Noto Sans TC) | 離線環境可能連線超時，需 fallback 至本機系統字型或移除 |
| **固定通訊埠 8899** | `vite.config.ts:16, 21` | `server.port: 8899`, `preview.port: 8899`, `strictPort: true` | 若原電腦 8899 被占用需釋放，或改用動態埠 |
| **遠端 CDN / 第三方庫** | 全專案清查 | **無任何外部 CDN 引用**（無 unpkg, cdnjs, tailwind cdn） | 零安全隱患 |
| **硬編碼本機絕對路徑** | 驗證腳本 (`scripts/*.js`) | `CHROME_PATH = 'C:\\Program Files\\Google\\Chrome...'` | 僅測試腳本有 Chrome 預設路徑，若原電腦路徑不同需適配 |
| **生產構建產物路徑** | `vite.config.ts:8` | `base: './'`（相對路徑） | **優良**：產物可任意目錄掛載，無絕對路徑綁定 |

---

## 八、既有核心問題現況檢查與本輪實證（附真實自動化檢驗證據）

本輪透過全新無副作用自動化檢驗腳本 `scripts/verify-return-inspection.js`，於運行中預覽服務 `http://127.0.0.1:8899/` 進行瀏覽器實景檢驗（記錄於 `evidence/return_inspection_summary.json`）：

### 1. 建立 Bot 是否真的新增資料？
- **狀態**：**已通過 (前端 Mock 狀態化)**
- **實測證據**：初始 Bot 數量為 3，開啟分配 Modal 建立新 Bot `test-bot-1350` 後，列表列數即時變為 4（`botAdded: true`）。
- **限制說明**：此資料寫入前端 LocalStorage（`catos_mock_storage_v2`），尚未向 Python 後端發送 `/bots` 請求。

### 2. 啟動／停止是否真的更新狀態？
- **狀態**：**已通過 (前端 Mock 狀態化)**
- **實測證據**：
  - 點擊「啟動」後，Bot 狀態即時轉為 `RUNNING`（綠色徽章），指派真實 32-char hex `run_id`（`botStartRunning: true`）。
  - 點擊「停止」後，傳遞真實 `run_id` 呼叫停止，狀態即時轉為 `STOPPED`，持倉數維持 `-1 張`，標記 `409 鎖定`（`botStopStopped: true`）。
- **限制說明**：純前端模擬 Worker 狀態流轉，無作業系統層 Python 子程序啟停。

### 3. 刷新後命令紀錄是否保留？
- **狀態**：**已通過 (前端 Mock 持久化)**
- **實測證據**：執行分配、啟動、停止後，對瀏覽器發送 `page.reload()` 刷新頁面，重新導航至 `#/logs`，命令記錄完整保留 3 筆（`commandLogsPreserved: true`, `commandCount: 3`）。

### 4. .py／契約檔案匯入是否有實際處理？
- **狀態**：**已通過 (純前端解析與註冊)**
- **實測證據**：`StrategiesPage.vue` 實作了 `<input type="file" accept=".py,.json">`（`fileInputConfigured: true`），能讀取文本解析 manifest 或 python source，生成新 hash 並推入版本庫清單；右側徽章誠實標註為「原型語法預檢 (示意)」，不冒充後端 AST 驗證（`astBadgeHonest: true`）。

### 5. 服務不可用時是否仍錯誤顯示正常連線？
- **狀態**：**已通過 (前端 503 嚴格邊界)**
- **實測證據**：切換為情境 5（服務異常 503）後，頁面頂部立即彈出離線警告橫幅，儀表板風控狀態嚴格轉為 `UNAVAILABLE`，淨值與損益全部以 `--` 顯示（`noFalseNormal: true`, `displayedUnavailable: true`），完全杜絕了偽報 NORMAL 或宣稱風控安全。

### 6. 策略版本、hash、參數預設與 Bot 快照是否一致？
- **狀態**：**已通過 (製品凍結機制)**
- **實測證據**：`BotsPage.vue` 表單監聽 `selectedStrategyHash`，切換時即時拉取該製品的 `defaults`（有界 JSON 格式，禁 float）填入參數編輯框；`mock-adapter.ts` 依所選 hash 進行深拷貝快照凍結，舊 Bot 不受後續新策略版本影響。

### 7. 信任勾選是否會跨策略或重開視窗殘留？
- **狀態**：**已通過 (強制重設保護)**
- **實測證據**：
  - Modal 初始開啟時，信任核取方塊為未勾選（`trustInitialUnchecked: true`）。
  - 手動勾選信任後，關閉 Modal 再重開，方塊強制還原為未勾選（`trustResetOnReopen: true`）。
  - 手動勾選信任後，在表單下拉選單切換至另一策略，方塊強制還原為未勾選（`trustResetOnSwitch: true`）。
  - 徹底杜絕了使用者誤沿用信任授權的金融與資安風險。

### 8. 成果歷史是否能讀取與還原？
- **狀態**：**部分完成 (前端抽屜可展開讀取，還原未實裝)**
- **實測證據**：`BotsPage.vue` 頂部點擊「執行成果歷史」可成功展開歷史抽屜，展示目前儲存的 2 筆 Runs 紀錄（`drawerOpened: true`, `runsCount: 2`）；但點擊個別 Run 還原為當前工作區狀態之功能標示為**未實裝／未驗證**。

---

## 十、第二版（v2）審查修復成果與契約對齊（2026-10-05 修復 7 項重大問題）

依據真實瀏覽器互動審查意見（`docs/frontend-review-20261004.md`），已徹底修復 2 大重大問題與 5 項契約/功能缺陷，並全數通過全新真實瀏覽器端對端驗收測試（`scripts/verify-fixes-acceptance.js`，6/6 PASSED）：

| 編號 | 缺陷描述 | 根因定位 | 修復方案與契約對齊 | 驗證證據 |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **Demo 顯示控制已鎖定，仍能啟動 Bot** | 前端按鈕未與 `currentMode` 聯動 disabled；Adapter 未做模式守護。 | 1. `WorkspaceAdapter` 新增 `setMode(m)`，與 `useWorkspace` 雙向同步。<br>2. `BotsPage.vue` 頂部加入唯讀警示橫幅，分配按鈕、列表「啟動」「停止」按鈕全數綁定 `:disabled="currentMode !== 'local'"` 與鎖定 title。<br>3. `mock-adapter.ts` 的 `allocateBot`、`startBot`、`stopBot` 進入點強制校驗 `currentMode === 'local'`，非本機模式一律拋出 `DEMO_MODE_LOCKED`。 | `acceptance_demo_mode_locked.png`：Demo 下全部按鈕 disabled，API 調用被拒。 |
| **2** | **啟動 ETH 後，持倉的 BTC 被篡改成「已完成」；刷新後保留** | 舊版 `startBot` 內粗暴執行 `for (const r of this.runs) { if (r.control_state === 'running') r.control_state = 'completed'; }` 並持久化。 | 1. **徹底移除**將其他 run 改為 completed 的錯誤代碼。<br>2. 嚴格對齊 `catos/local_sim_control.py:254` 單模擬槽位契約：若已有 Bot 正在 running，啟動另一 Bot 嚴格拋出 409 Conflict `SIMULATION_SLOT_OCCUPIED`。<br>3. 保持 BTC 運行狀態與 1 張持倉不受干擾；手動停止 BTC 時保留持倉（`position_contracts = '1'`, `ownership_retained = true`），F5 刷新後完美保持。 | `acceptance_slot_conflict_btc_retained.png`、`acceptance_btc_stopped_retained_after_reload.png`：ETH 啟動被 409 阻擋，BTC 持倉與狀態完全保留。 |
| **3** | **錯 hash 自動綁第一個策略** | `mock-adapter.ts:allocateBot` 中存在 `|| this.strategies[0]` 靜默降級。 | **徹底刪除 `|| this.strategies[0]`**。找不到策略製品快照時，拋出 `STRATEGY_NOT_FOUND`，絕不盲目綁定預設策略。 | Test 3 自動化攔截驗證通過。 |
| **4** | **隨機生成版本 hash** | 使用 `generateHex(64)` 偽造隨機字串。 | 實作 `computeSha256`（Web Crypto API），對製品規範內容計算真實 64-char 十六進位 SHA-256 哈希值，確保決定性與快照不可變性。 | Test 4 決定性驗證通過（64 hex）。 |
| **5** | **.py 匯入版本不符核心契約** | 舊版 StrategiesPage 寫死版本為 `1.0`。 | 1. 解析標頭註解 `# strategy_id:`, `# version:`, `# defaults:`, `# warmup_bars:`。<br>2. 預設版本對齊核心規範為 `file-v1`。<br>3. 契約預檢：限制大小 <= 12,000 bytes，檢查 `class Strategy`。 | `acceptance_py_strategy_uploaded_file_v1.png`：成功匯入並解析為 `file-v1`。 |
| **6** | **重送缺乏冪等處理** | 未記錄與比對 `request_id` 與 body。 | 全域命令日誌實作冪等校驗：同 `request_id` 且同 payload 重送直接回傳既有快照；同 `request_id` 用於不同命令拋出 409 Conflict `request_id_conflict`。 | Test 6 冪等重放與 409 衝突攔截通過。 |
| **7** | **匯入測試只檢查檔案欄位，沒有實際上傳** | 舊測試僅檢查 DOM 存在 input 元素。 | 編寫 `scripts/verify-fixes-acceptance.js`，以 Chrome Puppeteer 進行真實 `uploadFile('scripts/sample_test_strategy.py')`，派發 `change` 事件完整觸發入庫，並於 DOM 實證 Banner、列表新增、版本詳情與 F5 刷新後持久化。 | Test 5 真實上傳全鏈路驗收通過。 |

---

## 十一、搬移與接續風險提示

1. **不要直接整包覆蓋原專案**：原電腦應解壓至新目錄，經 Codex 檢查後再對比整合。
2. **本輪驗證性質定位**：本輪型別檢查、build 與瀏覽器測試為**開發自測存證**，非 WorkBuddy 獨立驗收，亦非全市場回測或實盤通過。
3. **Demo / Live 交易政策**：前端僅提供帶有醒目隔離警示的切換展示，底層嚴格禁止對外連接交易所與實盤憑證。

