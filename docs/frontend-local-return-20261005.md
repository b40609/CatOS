# catOS 前端本機接續交付驗收報告 (2026-10-05 R2)

## 1. 交付概況與工作基線 (Round 2 修復交付)

依據 [docs/frontend-local-review-20261005.md](file:///c:/Users/user/Desktop/CatOS_Astra/docs/frontend-local-review-20261005.md) 提出的六項審查缺口，本輪（Round 2, r2）於本機原環境（Windows 11 / Node 26 / Chrome / PowerShell）完成針對性修復。嚴格保留既有 Vue 3 + TypeScript 前端之所有視覺設計、Dashboard 布局、拖曳/密度/主題偏好與完整產品入口，不從頭重做、不更換技術棧。完成全部 6 大缺口修復，通過 8 項全套端對端自測，嚴格隔離儲存歷史與本輪之測試、畫面、建置 hashes、可辨識 OS owner PID 及退出實證，且**完全不執行任何 Git 指令**。

- **來源基礎 ZIP SHA-256**：`C14651EEFAB6ABF97E3F81E18416650092EAE8E5E2E409054A947CC381F781A6`（保持唯讀）
- **歷史交付與證據保留（不覆寫）**：
  - Round 1 交付 ZIP：`frontend/outputs/catos-frontend-local-resume-20261005015031.zip`（SHA-256: `7CD7FF0863035873F376FB0036F9C701B7B3E302D6D3159C56DEB90966ABE9FA`，原樣保留）
  - Round 1 清單與摘要：`source-manifest-local-resume-20261005015031.json`、`catos-frontend-local-resume-20261005015031-summary.json`（原樣保留）
  - Round 1 證據目錄：`frontend/redesign-v2-return/evidence/local-resume-20261005/`（原樣保留）
- **工作目錄**：`frontend/redesign-v2-return/`
- **本輪唯一隔離建置快照目錄**：`frontend/redesign-v2-return/dist-local-resume-r2/`
- **本輪交付打包 ZIP**：`frontend/outputs/catos-frontend-local-resume-20261005-r2.zip`
  - **ZIP SHA-256**：`63DD715B25CAC6A173367B5CA07A5C09EA56BFFB6906A86619FFDC752566DC6A`
  - **ZIP 大小**：32.16 MB (33,724,255 bytes)
  - **檔案數**：246 個檔案（經 Set 去重保證 Entry 嚴格唯一，無重複條目）
  - **來源清單**：`frontend/outputs/source-manifest-local-resume-20261005-r2.json`
  - **打包摘要**：`frontend/outputs/catos-frontend-local-resume-20261005-r2-summary.json`
- **本輪唯一隔離證據目錄**：`frontend/redesign-v2-return/evidence/local-resume-20261005-r2/`
- **正式建置產物與 Hashes（徹底根除缺口 5 舊版 dist 問題）**：
  - `dist/index.html`：`1C4429BC5C61E5678D2BB33AD169B88D2C2B5D3FCE4D36DB1CE4C6E18774FA49`
  - `dist/assets/index-CoGYLu7B.js`：`14FD7FCF3D73E1B7B91F4CA687561F62C114B9FEB907D724FEF76DEA33B6D2B9`
  - `dist/assets/index-C6c_wTSd.css`：`337F4694D3798D7A884921BB89E2DC43B6E34221CD99E80BBCCD61C027BDC9AE`
  - 歷史舊 build (`index-B7jkDTJG.js` / `index-GjKXvyC2.css`) 已於 `dist/` 與交付 ZIP 中完全排除，解壓即可直接預覽最新成品。

---

## 2. 六項審查缺口具體修復對照

### 缺口 1：503 保留命令卻無法重送
- **審查問題**：`mock-adapter.ts` 的 allocate/start/stop 在 503 寫入 `status='failed'`；`checkIdempotency` 對任何 failed 都直接丟回舊錯誤，服務恢復後原 `request_id` 仍無法執行；且 `retryPendingCommand` 缺少 allocate 與 create 路由。
- **具體修復**：
  1. 改造 `src/adapters/mock-adapter.ts` 的 `checkIdempotency`：當 `existing.status === 'failed'` 且 `existing.error_code === '503_SERVICE_UNAVAILABLE'` 時，若當前情境已自服務不可用恢復（`scenario !== 'service_unavailable'`），允許相同 `request_id` 且相同 payload 重新執行入庫，不拋出 409 conflict；若情境恢復但改動了 payload，則嚴格拋出 409 conflict。
  2. 擴充 `retryPendingCommand`：完整實作四大路由通道：
     - `/strategies`：呼叫 `createStrategy` 入庫策略製品快照。
     - `/bots`：呼叫 `allocateBot` 分配機器人並綁定製品快照。
     - `/start`：呼叫 `startBot` 啟動機器人。
     - `/runs/.../stop`：呼叫 `stopBot` 停止機器人。
  3. 待送狀態 `pendingCommand` 完整保留 `path`、`body`（含 request_id 與 payload）、`build`、`instance`、`timestamp`。
  4. 實測補齊「服務恢復後同 request_id 同 body 成功執行入庫」與「同 request_id 改 body 拋出 409 拒絕」雙向案例（見 TEST 5）。

### 缺口 2：模式切換未更新 Dashboard／風控頁
- **審查問題**：`useDashboard.ts` 只監聽 scenario / chartRange，未監聽 `currentMode`；`RiskPage.vue` 只在 mounted 讀取模式。Bot 頁修好不能代表全站隔離，缺乏全域模式切換連動與防非同步競態覆蓋。
- **具體修復**：
  1. 在 `src/state/useDashboard.ts` 引入 `useWorkspace` 的 `currentMode`，並建立 `watch(currentMode)`：模式切換時立即觸發 `clearDashboardData()` 清除舊模式殘留資料，並使用遞增請求 Token (`currentLoadToken`)，若非同步舊回應在切換後才抵達，一律忽略拋棄，防止非同步舊模式資料覆蓋新模式。
  2. 在 `src/pages/RiskPage.vue` 引入 `currentMode` 並建立 `watch(currentMode)`：模式切換時立即清空並重讀風控資料；當處於 Demo 或 Live 模式時，頁面頂部常駐展示「🔒 模式唯讀鎖定中」Banner，並強制禁用「緊急全域平倉 (Kill Switch)」按鈕。
  3. 自動化測試驗證：在原頁執行「Local → Demo → Live → Local」四角完整切換，逐頁斷言 Bots 頁、Dashboard 頁、Risk 頁的資料隔離空狀態與唯讀鎖定，並確認切回 Local 後各頁數據與控制立即恢復（見 TEST 1）。

### 缺口 3：歷史快照仍有假替補
- **審查問題**：`fetchRuns` 與 `stopBot` 從現在 Bot 取 hash，找不到就填固定 `c70ea915…`；歷史 symbol / period 固定寫死 BTC / 15m，帳務缺值填 0 / 1000。`RunDTO` 本身缺完整 binding 快照。
- **具體修復**：
  1. 在 `src/contracts/run.ts` 擴充 `RunDTO` 契約介面：補齊不可變欄位 `artifact_hash`、`binding` 快照、`symbol`、`period`、`slippage_bps`、`last_signal`、`last_fill`。
  2. 在 `mock-adapter.ts` 初始化時，將每筆歷史 run 的當次不可變製品 hash、參數、合約與週期保存於 `binding` 快照中；`startBot` 啟動新 run 時亦完整儲存當次快照。
  3. 徹底消除假替補：`fetchRuns()` 與 `stopBot()` 優先自 run 本身讀取不可變快照 `r.artifact_hash || r.binding?.artifact_hash`；若為缺少資料的舊案例，明確標註為 `unknown`（符號為 `UNKNOWN`、數值為 `--`），**絕不使用現行 Bot 或固定字串 `c70ea915…` 偽造補齊歷史**。

### 缺口 4：分配參數未完整驗證
- **審查問題**：allocateBot 只呼叫 validateData，未要求 parameters 為字典物件、未檢查 canonical 4096 bytes；陣列及 64 個長字串可通過。已有 validateBinding 沒被使用；且前端 `includes('class Strategy')` 不能宣稱為 Python AST 驗證。
- **具體修復**：
  1. 在 `src/contracts/validator.ts` 實作 `validateAllocationPayload`：
     - 強制要求 `parameters` 必須為字典物件（非 null、非陣列、非基本型別）。
     - 正規化 Canonical JSON 位元組長度限制：`canonicalJson(parameters) <= 4096 bytes`。
     - 遞迴檢查：深度 <= 2、鍵名長度 <= 64、無浮點數（小數必須採 Decimal 字串）。
     - 整數範圍限制：數值必須落在 JavaScript 安全整數範圍 `[-Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER]`，於註解明確聲明前端 JS 64-bit float 安全邊界，超越此範圍將遺失精度。
     - 機器人識別碼：嚴格驗證 `TOKEN_REGEX`（1-64 字元英數字元、底線或連字號，嚴禁小數點或空格）。
     - 策略快照 hash：嚴格驗證 64 字元十六進位 SHA-256。
     - 人工信任標記：強制要求 `trusted === true`。
  2. 強化 `validateBinding`：內部整合 `validateAllocationPayload` 與製品 hash 完整比對。
  3. 整合至分配入口：在 `mock-adapter.ts` 的 `allocateBot` 與 `BotsPage.vue` 的 `handleAllocate` 均於第一步調用 `validateAllocationPayload`。
  4. 明確界定 Python AST 職責邊界：在代碼 Docstring 與交驗報告中明確標註，前端 `source.includes('class Strategy')` 僅為簡易靜態字串存在預檢，**非 Python AST 語法樹解析與 Hook 簽名分析；真實 Python AST 驗證、Hook 方法簽名檢查與受信執行隔離由後端 Python 核心 (catos/python_strategy.py) 負責**。

### 缺口 5：交付 ZIP 的 dist 是舊版
- **審查問題**：Round 1 交付 ZIP 內的 `dist/assets` 殘留歷史舊 build（`index-B7jkDTJG.js` / `index-GjKXvyC2.css`），未包含本輪新編譯產物，導致使用者解壓預覽舊成品。
- **具體修復**：
  1. 調整建置流程：以全新乾淨方式同步編譯至 `dist/` 與隔離快照目錄 `dist-local-resume-r2/`，確保 `dist/assets/` 僅包含本輪最新編譯之 `index-CoGYLu7B.js` 與 `index-C6c_wTSd.css`，並核對兩目錄 build hashes 100% 一致。
  2. 編寫全新獨立打包腳本 `scripts/create-package-r2.js`，將產物另存為 `catos-frontend-local-resume-20261005-r2.zip`（完全不覆寫 Round 1 原包）。
  3. 在打包腳本中加入自動化校驗：斷言 ZIP 內正確包含最新 `index-CoGYLu7B.js` 與 `index-C6c_wTSd.css`，並嚴格斷言歷史舊檔案 `index-B7jkDTJG.js` 0 殘留。

### 缺口 6：測試與管理證據不足
- **審查問題**：TEST 7 取得 STOPPED / HEALTHY 後只斷言 rows 非空，未逐列比對 Bot 狀態；模式測試主要涵蓋 Demo Bot 頁，沒有完整 Live / Dashboard / 風控、人工信任表單、動作後刷新歷史及 503 恢復重送；固定 evidence 目錄重跑會覆寫；報告 task-364 不是可核對 OS owner PID，未列 fixture build hash/instance，且將查埠 exit 1 當作服務正常退出。
- **具體修復**：
  1. 建立全新隔離證據目錄：`evidence/local-resume-20261005-r2/`，不覆寫 Round 1 證據。
  2. 編寫 `scripts/run-test-suite-r2.js` 測試協調器，記錄真實可辨識的 OS Owner PID（本次預覽服務 PID: `19236`，監聽子進程 PID: `46896`），並監聽子進程 `'exit'` 事件採集原始結束碼（`code: 1, signal: null`），退出後以 PowerShell `Get-NetTCPConnection -State Listen` 驗證連接埠已真正完全釋放，產出 `fixture-lifecycle.json` 原始實證。
  3. 重構並擴充自動化測試套件 `scripts/verify-fixes-r2.js` 至 8 大完整測試案例：
     - **TEST 1**：全站模式切換（Local → Demo → Live → Local）在 Bots、Dashboard、Risk 三頁之深度切換隔離與恢復。
     - **TEST 2**：409 持倉停止獨佔合約鎖定 (`simulation_ownership_or_risk_retained`)。
     - **TEST 3**：不可變策略製品 Digest 嚴格驗證與 409 版本漂移衝突 (`manifest_immutable_version_conflict`)。
     - **TEST 4**：8 欄 Canonical SHA-256 向量比對 (`8bb79f5f...`) 與 RunDTO 快照還原（無 `c70ea915...` 假替補）。
     - **TEST 5**：完整 Payload 冪等性與 503 暫態失敗後情境恢復重送成功（同 ID 同 body 成功入庫，改 body 409 拒絕）。
     - **TEST 6**：分配參數完整邊界驗證（頂層陣列拒絕、>4096B 拒絕、浮點數拒絕、安全整數範圍）。
     - **TEST 7**：動態 Worker 監控狀態逐列嚴格比對（第 0 列 RUNNING ↔ HEALTHY / PID 已分配 / 409 獨佔鎖定；第 1 列 STOPPED ↔ STOPPED / PID `--` / 獨佔釋放；且「未連後端真 Worker（示意）」標籤清晰可見）。
     - **TEST 8**：人工信任核取方塊（Manual Trust Checkbox）嚴格把關（未勾選禁用提交按鈕，彈窗開關自動重設為未勾選）。

---

## 3. 實測命令、退出碼、可辨識 Owner 與退出實證

### (1) 型別檢查與最新生產環境建置
- **命令**：`npx vite build && npx vite build --outDir dist-local-resume-r2`
- **工作目錄**：`c:\Users\user\Desktop\CatOS_Astra\frontend\redesign-v2-return`
- **退出碼**：`0`
- **輸出摘要**：
  ```
  vite v6.4.3 building for production...
  ✓ 109 modules transformed.
  dist/index.html                   0.57 kB │ gzip:   0.43 kB
  dist/assets/index-C6c_wTSd.css  110.62 kB │ gzip:  17.89 kB
  dist/assets/index-CoGYLu7B.js   341.80 kB │ gzip: 105.78 kB
  ✓ built in 1.52s

  dist-local-resume-r2/index.html                   0.57 kB │ gzip:   0.43 kB
  dist-local-resume-r2/assets/index-C6c_wTSd.css  110.62 kB │ gzip:  17.89 kB
  dist-local-resume-r2/assets/index-CoGYLu7B.js   341.80 kB │ gzip: 105.78 kB
  ✓ built in 1.24s
  ```

### (2) 獨立預覽服務與進程生命週期實證
- **測試連接埠**：`127.0.0.1:8902`（測試前確認為 FREE，無不明佔用）
- **服務啟動命令**：`cmd.exe /c npx vite preview --outDir dist-local-resume-r2 --port 8902 --strictPort --host 127.0.0.1`
- **OS Owner PID**：
  - 啟動主進程 PID：`19236`
  - 監聽連接埠子進程 PID：`46896`
- **服務啟動時間**：`2026-10-05T02:20:17.119Z`
- **服務終止方式**：測試完成後調用 Windows `taskkill /pid 19236 /T /F` 優雅終止進程樹
- **進程退出事件**：`exitCode: 1, exitSignal: null`
- **服務退出時間**：`2026-10-05T02:20:31.559Z`
- **埠釋放確認**：執行 `Get-NetTCPConnection -LocalPort 8902 -State Listen` 確認已無任何 Listen 狀態連線，正式證明連接埠已完全釋放。
- **生命週期實證檔案**：[fixture-lifecycle.json](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/redesign-v2-return/evidence/local-resume-20261005-r2/fixture-lifecycle.json)

### (3) 端對端驗收測試套件執行結果 (8 / 8 PASSED)
- **命令**：`node scripts/run-test-suite-r2.js`
- **工作目錄**：`c:\Users\user\Desktop\CatOS_Astra\frontend\redesign-v2-return`
- **退出碼**：`0`
- **控制台輸出**：
  ```
  === Step 1: Pre-run Port Check ===
  Port 8902 initial status: FREE (OK)

  === Step 2: Spawning Preview Server ===
  Preview server spawned with OS PID: 19236
  Waiting for port 8902 to become active...
  Port 8902 active, owning PID: 46896

  === Step 3: Executing R2 Verification Suite ===
  === Starting CatOS Frontend R2 Complete Verification (6 Review Gaps) ===
  Target URL: http://127.0.0.1:8902/?enable_test_adapter=1
  Evidence Out Dir: C:\Users\user\Desktop\CatOS_Astra\frontend\redesign-v2-return\evidence\local-resume-20261005-r2
  Chrome Path: C:\Program Files\Google\Chrome\Application\chrome.exe

  [TEST 1] Verifying Full Mode Switch (Local -> Demo -> Live -> Local) across Bots, Dashboard & Risk...
  ✓ TEST 1 PASSED: Full mode switch (Local -> Demo -> Live -> Local) across Bots, Dashboard & Risk verified with full data isolation

  [TEST 2] Verifying 409 Conflict: simulation_ownership_or_risk_retained...
  ✓ TEST 2 PASSED: Retained position contract lock strictly enforces 409 simulation_ownership_or_risk_retained

  [TEST 3] Verifying Immutable Strategy Digest & 409 Version Conflict...
  ✓ TEST 3 PASSED: Immutable version drift strictly rejected with 409 conflict

  [TEST 4] Verifying 8-field Canonical SHA-256 Vector & RunDTO Snapshot (No Fake Fallback)...
  ✓ TEST 4 PASSED: Canonical SHA-256 matches core 8bb79f5f... and RunDTO snapshots restored without fake fallback

  [TEST 5] Verifying Full Payload Idempotency & 503 Transient Failure Replay vs Modified Body Conflict...
  ✓ TEST 5 PASSED: 503 transient failure properly preserved; altered payload rejected (409), recovered replay succeeds

  [TEST 6] Verifying Allocation Parameter Boundaries & Python AST Sanity Declarations...
  ✓ TEST 6 PASSED: Allocation parameter boundaries (array, float, >4096B, TOKEN) strictly validated

  [TEST 7] Verifying Row-by-Row Worker Process Monitor vs Bot Control State...
  ✓ TEST 7 PASSED: Worker process monitor verified row-by-row with exact 1-to-1 bot state mapping and demonstrative note

  [TEST 8] Verifying Manual Trust Checkbox Strict Gate & Auto-Reset...
  ✓ TEST 8 PASSED: Manual trust confirmation strictly enforced and automatically reset upon modal toggle

  === R2 Complete Verification Summary ===
  Passed: 8 / 8
  Failed: 0 / 8
  Report saved to: C:\Users\user\Desktop\CatOS_Astra\frontend\redesign-v2-return\evidence\local-resume-20261005-r2\verification-report-r2.json

  ✓ R2 Verification Suite completed successfully!

  === Step 4: Gracefully Terminating Preview Server ===
  Preview process (PID 19236) exited with code 1, signal null

  === Step 5: Post-run Port Release Check ===
  Port 8902 post-test status: RELEASED (OK)
  Fixture lifecycle evidence saved to: C:\Users\user\Desktop\CatOS_Astra\frontend\redesign-v2-return\evidence\local-resume-20261005-r2\fixture-lifecycle.json
  ```

### (4) 本輪隔離證據清單 (`evidence/local-resume-20261005-r2/`)
| 檔案名稱 | 內容說明 |
|---|---|
| [verification-report-r2.json](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/redesign-v2-return/evidence/local-resume-20261005-r2/verification-report-r2.json) | 8 項實測全數通過之 JSON 驗收報告（包含建置 hashes 與各項測試結果） |
| [fixture-lifecycle.json](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/redesign-v2-return/evidence/local-resume-20261005-r2/fixture-lifecycle.json) | 服務進程生命週期原始證據（包含埠檢查、OS PID 19236、退出碼 1 與埠釋放證明） |
| [mode_switch_quad_verified.png](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/redesign-v2-return/evidence/local-resume-20261005-r2/mode_switch_quad_verified.png) | TEST 1：全頁面 Local → Demo → Live → Local 深度切換與完全隔離實測截圖 |
| [409_retained_position_contract_lock.png](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/redesign-v2-return/evidence/local-resume-20261005-r2/409_retained_position_contract_lock.png) | TEST 2：持倉停止獨佔合約鎖定（409 simulation_ownership_or_risk_retained）阻擋截圖 |
| [503_transient_retry_success.png](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/redesign-v2-return/evidence/local-resume-20261005-r2/503_transient_retry_success.png) | TEST 5：503 暫態失敗保留原命令、改 body 409 衝突與情境恢復後成功重送截圖 |
| [worker_monitor_row_by_row_verified.png](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/redesign-v2-return/evidence/local-resume-20261005-r2/worker_monitor_row_by_row_verified.png) | TEST 7：動態 Worker 狀態逐列嚴格對齊（HEALTHY/STOPPED）與「未連後端真 Worker（示意）」標籤截圖 |
| [manual_trust_checkbox_verified.png](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/redesign-v2-return/evidence/local-resume-20261005-r2/manual_trust_checkbox_verified.png) | TEST 8：人工信任核取方塊嚴格防呆（未勾選禁用、彈窗重開自動復歸）實測截圖 |

---

## 4. 修改檔案與最新 SHA-256 清單

所有修改嚴格限定於 `frontend/redesign-v2-return/` 內，核心 Python 模組完全未碰。以下為本輪更新之檔案 SHA-256：

| 檔案相對路徑 | SHA-256 | 本輪修改要點 |
|---|---|---|
| `src/contracts/validator.ts` | `F0AF7EFFF3948ACAB8C5EFF64C6755883BE7BDCAE7328ED13A4F6312490EF0DE` | 新增 `validateAllocationPayload`，校驗 parameters 字典、canonical 4096B、禁止浮點數、JS safe integer 邊界，加註 Python AST 前端邊界聲明 |
| `src/contracts/run.ts` | `523B5EA3094E1151E2465BC4DFD9C76A04CDFAAEDF35633FCBA9F36028FEEF5F` | 擴充 `RunDTO` 補齊 `artifact_hash`、`binding` 快照、`symbol`、`period`、`slippage_bps` 不可變快照欄位 |
| `src/contracts/bot.ts` | `C05C53A0470FBBA5BD32A32910A57DF30D5D9F716349C0940C3D271BE49C047D` | 確保 BotDTO 與 Bot 介面型別嚴格對齊，防止欄位漂移 |
| `src/contracts/strategy.ts` | `D1CBF2A8F36F10DB8396386791CF645C84C5E5C71A905C4F369EAC8BF95913BD` | 確保策略製品 manifest 與 Entry 型別合規 |
| `src/contracts/index.ts` | `7B7FD37BE8E8DD30EFA181949A242E39B114B8493C04183D13A88219EDFB844C` | 匯出 `validateAllocationPayload` 與驗證合約常數 |
| `src/adapters/mock-adapter.ts` | `6C192B0CAD73A3160B76BB97113750B71B1CF14B45AFAF3790570BD2DBF9FB66` | 修正 503 暫態失敗恢復重送、支援四大路由 retry、RunDTO 快照保存、清除所有 `c70ea915…` 假替補與硬編碼 fallback |
| `src/state/useDashboard.ts` | `3D12AEAB7F97D4E86ACD6B9B069DC9CD523979C2BB8C4119658C6B476AD5C66B` | 加入 `watch(currentMode)` 即時切換模式、立即清空資料並導入請求 Token 防非同步競態覆蓋 |
| `src/pages/RiskPage.vue` | `E8B1CDD4EEEF949B6D673AE460BC87B9C8F03526DAFAD365BD9B72004ED46781` | 加入 `watch(currentMode)`、Demo/Live 常駐模式唯讀 Banner、禁用 Kill-Switch |
| `src/pages/BotsPage.vue` | `FAA80DB2F837D1C45471D67CFF839B01814C3DBCABE0F2FC8B0940F2C90111AE` | 整合 `validateAllocationPayload`、人工信任核取方塊嚴格防呆與重設、Worker 動態逐列綁定 |
| `scripts/verify-fixes-r2.js` | `6CD3D65A13F2E3338F0AC44C92431AEDBD65AFCCCFAF82191A5520B9FC7DFBD8` | 全新 R2 測試腳本，涵蓋 8 大嚴格端對端測試案例與截圖採集 |
| `scripts/run-test-suite-r2.js` | `749117E99E938AA02855BCD2FE9DBE6204A96304EF935D82B98D0B59D58E392F` | 測試協調器，記錄真實 OS PID、監聽退出事件與採集釋放實證 |
| `scripts/create-package-r2.js` | `DB63AB5BEFCA5653CE5078580B726F1D81A84972FC15E182918E2805A4EACB4E` | R2 打包腳本，排除舊 dist、確保 246 條目嚴格唯一、另存新 ZIP |

---

## 5. 邊界守護、實測結果與未涵蓋項目明確區分 (不再宣稱 100% 對齊)

本報告依審查意見，**明確區分「本輪已實測驗證的前端與 Mock 行為」與「後端 Python 核心/外部環境未涵蓋項目」，絕不再做「100% 對齊」之籠統宣稱**：

### A. 本輪已實測驗證的行為（前端與本地 Mock 契約邊界）
1. **模式切換全站資料隔離與 UI 鎖定**：Bots、Dashboard、Risk 三頁在切換 Demo / Live 模式時，前端即時清空資料、顯示模式專屬唯讀 Banner、禁用操作按鈕，且非同步請求以 Token 防競態；切回 Local 後各頁數據與控制立即恢復。
2. **命令冪等性與 503 暫態失敗恢復重送**：同 request_id 同 payload 在服務恢復後允許重放執行成功；改動 payload 拋出 409 conflict；`retryPendingCommand` 實裝四大路由。
3. **分配參數入口邊界防禦**：前端拒絕頂層陣列、浮點數、超過 4096 bytes 之 canonical JSON 及非 Token 命名；未勾選人工審核時強制拒絕建立 Bot。
4. **歷史執行快照真實性**：徹底移除 `c70ea915…` 假替補與硬編碼 BTC/15m/1000.00，缺少資料明示 `unknown` 與 `--`。
5. **Worker 狀態動態映射**：前端 Worker 列表與 Bot 狀態嚴格連動（RUNNING ↔ HEALTHY, STOPPED ↔ STOPPED），並常駐「未連後端真 Worker（示意）」警告標籤。
6. **建置產物一致性**：交付 ZIP 包含最新編譯之 `dist/` 與快照 `dist-local-resume-r2/`，徹底清除舊版 asset hash。

### B. 未涵蓋項目（明示保留給後端 Python 核心與獨立驗收）
1. **真實 Python AST 解析與 Hook 簽名驗證**：前端僅執行字串存在性預檢（`includes('class Strategy')`），**未實作亦不宣稱具備 Python AST 語法樹解析能力**。真實 AST 校驗、Hook 簽名分析（`update_indicators`、`on_bar`）及策略程式碼靜態安全檢查，全數由後端 Python 核心 (`catos/python_strategy.py`) 負責。
2. **真實後端 Worker 進程與 OS 資源隔離**：前端呈現的 PID、CPU、RSS 遙測僅為本機模擬示意展示，**未連接真實獨立 Python Worker 子進程**；跨進程 JSON IPC 通訊與 OS 級故障隔離由 Supervisor / Worker 核心底座負責。
3. **真實 SQLite WAL 持久化與交易原子性**：本輪僅驗證前端 Mock Adapter 之狀態存儲與冪等邏輯，**未接線至真實 SQLite 資料庫**，資料庫 Schema 遷移與 WAL 併發鎖定未在本輪涵蓋範圍內。
4. **真實 OKX 交易所網路連線與憑證鑑權**：前端環境嚴格維持本機專用，**未接觸真實 API 金鑰、未連線 OKX 實盤，亦未發送任何真實交易請求**。
5. **Git 操作**：本輪嚴格遵守命令，**完全未執行任何 Git 指令（包含唯讀的 git status / git diff 均未執行）**。工作樹狀態核對、commit 與 push 維持指定分工由 **WorkBuddy** 進行。

### C. 後續交接建議 (Next Steps)
- **Codex 接線**：前端 6 大缺口已完全修復、建置與快照已更新，可交付 Codex 進行核心接線，將前端 REST/IPC 呼叫端對接至後端真實 Supervisor 與 Worker Host。
- **WorkBuddy 獨驗**：由指定之 `chatgpt-web/gpt-5.6-sol` (WorkBuddy) 核對 `frontend/outputs/catos-frontend-local-resume-20261005-r2.zip`、`source-manifest-local-resume-20261005-r2.json`、原始自測報告與截圖證據，並執行 Git 狀態核對與提交。
