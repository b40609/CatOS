# catOS v1 前端重開發第二版驗證執行紀錄與重現指引 (VERIFICATION_RUN.md)

本文件專為接手開發者（本機 Codex / WorkBuddy / 獨立驗收角色）提供完整且可重現的驗證步驟、實際執行記錄，以及**誠實明示之未驗項目**。

---

## 一、免責與邊界聲明：Mock 與建置通過 ≠ 核心交易通過

依據 `AGENTS.md` 規範：
> 「字串斷言不能稱真實 UI 互動通過。Mock 通過不能稱 Worker／MCP／交易核心通過。明示所有未驗項目，不以 Mock 或 build 通過宣稱核心流程通過。」

### 🚨 明示本輪所有未驗項目（Unverified Items）

本輪前端重開發僅在**純前端（UI/UX、Vue 3 元件架構、TypeScript 契約、原生 CSS 設計系統、前端 Mock Adapter、瀏覽器自動化渲染）**層級完成第二版封閉式修復與自測驗證，以下底層與後端核心能力**完全未經本輪驗證，亦不可視為已通過**：

1. **真實 FastAPI / HTTP API 端點對接**：
   - 目前所有資料與命令均經由 `src/adapters/mock-adapter.ts` 提供；
   - 尚未對真實的 `http://127.0.0.1:8770` 或 `8771` 進行網路請求或端點整合測試（待 Codex 下一階段完成正式接線）。
2. **真實 Worker 行程生命週期與 IPC 通訊**：
   - 策略執行時 Worker 的啟動、監視、SIGTERM/SIGKILL 退場、以及 JSON IPC 通訊未經真實進程驗證；
   - 前端所呈現之 Worker 狀態均為 Mock 資料映射。
3. **真實 OKX 交易所連線與 SWAP 下單**：
   - 未發送任何真實或模擬盤（Demo/Live）網路請求至 OKX API；
   - 固定委託標籤 `"tag": "41cb53c54d6dABDE"` 在交易所端的實際反射與驗證未執行。
4. **真實 SQLite WAL 交易流水與快照對帳**：
   - 前端未讀寫任何實際資料庫，未進行資料庫鎖定、WAL 併發寫入或重啟對帳驗證。
5. **真實日損 Soft / Hard 熔斷連鎖反應**：
   - 日損安全儀表之指針偏移與橫幅告警為 UI 狀態展示，未與 Supervisor 之市價清倉、Kill-Switch 鎖存進行聯動實測。
6. **真實合約獨佔（409 衝突）後端拒絕**：
   - 409 持倉停止為前端場景模擬，未測試後端 Supervisor 在同一合約已由其他 Bot 佔用時的實際 HTTP 409 回應處理。
7. **真實 MCP 策略製品建立與匯入**：
   - `catos.python-strategy.v1` 契約在前端完成 TypeScript 型別定義與靜態檢查，但外部 AI 透過 MCP 協議建立策略、版本比對的整套工具鏈未在本輪執行。
8. **真實帳戶與資金安全保證**：
   - 前端金額/價格全以 String/Decimal 處理，但本輪並未驗證高精度運算在後端對帳系統的數值一致性。

---

## 二、實際命令執行與驗證結果日誌 (v2 全功能驗證)

本輪重開發於 Windows (x64) 本地環境執行，所有指令均由終端直接執行並取得確定結果：

### 1. TypeScript 嚴格型別檢查 (`typecheck`)
- **執行指令**：
  ```bash
  npm run typecheck
  # 實際執行: vue-tsc --noEmit
  ```
- **執行結果**：
  - Exit Code: `0`
  - 終端無任何報錯輸出，全專案 TypeScript / Vue 檔案通過嚴格型別校驗（含 `strictNullChecks`, `noImplicitAny`）。

### 2. 生產環境建置打包 (`build`)
- **執行指令**：
  ```bash
  npm run build
  # 實際執行: vue-tsc --noEmit && vite build
  ```
- **執行結果**：
  - Exit Code: `0`
  - 產出目錄：`dist/`
  - 打包產物健全，無警告、無缺少別名或模組未解析錯誤。

### 3. 本地 Chrome 真實瀏覽器自動化測試 (`scripts/verify-full-suite.js`)
- **執行指令**：
  ```bash
  node scripts/verify-full-suite.js
  ```
- **測試環境**：
  - 瀏覽器：Google Chrome 本地實體安裝版 (`C:\Program Files\Google\Chrome\Application\chrome.exe`)
  - 驅動機制：Puppeteer Core 連接本地 Chrome，解析度 1440x900
  - 本地服務：Vite 測試服務運行於 `http://127.0.0.1:61943/`（嚴格綁定本地獨立測試埠）
- **執行結果**：
  - Exit Code: `0`
  - **步驟總數**：25 項全部通過（25/25 PASS, 0 FAIL）
  - **Console 錯誤檢查**：`0 console errors`，`0 console warnings` 通過。
  - **驗收存證產出**：
    - `evidence/verification_summary.json`
    - `evidence/503_layout_a_1440.png`（佈局 A 503 錯誤展示與 UNAVAILABLE 風控）
    - `evidence/503_layout_b_1440.png`（佈局 B 503 處理箱展示，無誤報安全）
    - `evidence/bots_and_history_verified.png`（Bot 成功入庫、啟停狀態轉換、重新整理持久化、成果歷史抽屜）

### 4. 測試連接埠釋放驗證
- **執行指令**：
  ```powershell
  Get-NetTCPConnection -LocalPort 61943 -ErrorAction SilentlyContinue
  ```
- **執行結果**：
  - Exit Code: `1`（無連線），確認測試伺服器已徹底終止，埠號 61943 乾淨釋放，無殘留背景進程。

---

## 三、接手開發者重現指引 (Step-by-Step)

另一位開發者獲取原始碼後，可依下列步驟在乾淨目錄重現完整建置與驗證：

### 前置需求
- **Node.js**: v18+（建議 v20 或 v22 LTS）
- **Google Chrome**: 本地標準安裝（若需重跑自動化測試腳本）

### 重現步驟
1. **安裝依賴（使用鎖定版本）**：
   ```bash
   npm ci
   ```
2. **執行型別檢查**：
   ```bash
   npm run typecheck
   ```
   預期輸出：無報錯直接退出（Exit Code 0）。

3. **執行正式建置打包**：
   ```bash
   npm run build
   ```
   預期輸出：生成 `dist/` 目錄，內含靜態 HTML、JS、CSS。

4. **啟動獨立預覽伺服器並執行自動化驗證腳本**：
   ```bash
   # 啟動 61943 預覽服務
   npx vite preview --host 127.0.0.1 --port 61943 --strictPort
   
   # 另開終端執行全功能驗證套件
   node scripts/verify-full-suite.js
   ```
   預期輸出：25 個測試項目全數通過，產生 `evidence/verification_summary.json`。
