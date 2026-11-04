# CatOS v1

CatOS 是一套本機專用（127.0.0.1）的量化交易系統，目標是分鐘至小時級、已收盤 K 線的策略研究與受控執行。v1 的交付範圍是**本機合成模擬**：同一套 Supervisor／Worker／Journal／風控程式在 FakeExchange 上跑完整的策略 → 意圖 → 風控 → 成交 → 帳務流程，並由 React 戰情台讀取真實投影資料。以下只寫 v1 實際存在並經驗證的能力；願景與歷史規劃見 `docs/archive/`。

v1 已於 2026-11-04 通過正式獨立驗收（`reports/v1-acceptance-20261104/acceptance.md`）並合併進 `main`。下一步與候選工作包見 `docs/next-steps.md`。

## v1 範圍

| 項目 | v1 實況 |
| --- | --- |
| 執行環境 | 僅 local-sim：`catos/fake_exchange.py` 合成撮合，固定模板 8 根＋2 根預熱的合成 15m K 線 |
| 策略 | 一個登錄策略 `sma-trend`／`sma-parameters-v1`（SMA 長／平），由 `catos/research_artifacts/*.json` manifest 驅動：`catos/strategy_registry.py` 只接受 `approval_state == "approved"`，載入前核對 `source_files` 的 sha256，不符即拒絕，不退回預設策略 |
| Bot | 單一 Bot `sim-control-sma`，單合約獨佔（`BTC-USDT-SWAP`，`cross`＋`net_mode`），單槽控制面 |
| OKX | 只有 GET 唯讀證據模組（`catos/okx_readonly.py` 離線核對、`catos/okx_http.py` 單次 GET adapter）與研究資料抓取工具 `tools/fetch_okx_candles.py`（三個公開端點、不用金鑰）。**沒有** Demo／Live 下單、撤單或帳戶修改路徑 |
| 研究資料 | 內建 96 根合成資料集，加上經授權抓取的 OKX 公開歷史資料（已收盤 K 線、實際資金費率、合約規格），存在本機 `data/okx/`（git 忽略）。研究端只接受 manifest 雜湊相符、無缺口、資金費完整的資料集，不符即拒絕。回測、優化與滾動驗證都可選資料集；滾動驗證結果 v2 不保存逐根明細，在 8,640 根上約 0.6 MB。見 `docs/research-real-data-plan.md` |
| 風控 | R1 台北日固定基準、Soft／Hard 日損鎖存（預設 10%／20%）、有效槓桿與單幣曝險預算（3.0x／50%）、P6 災難停損設定；`risk.Snapshot` 的事實旗標預設 fail-closed（未宣告即視為未知） |
| HTTP | 研究 API 與 local-sim 控制面投影（見下方）；**沒有** Kill-Switch／re-arm HTTP，前端對應按鈕標示「未接線」 |
| 前端 | 戰情台、實例監控、風控中心、策略中心、系統日誌與側欄狀態列讀取控制面真資料；回測／優化／滾動驗證頁接研究 HTTP；設定頁讀取服務版本；策略覆盤與市場情報頁標示「v1 未啟用」 |

## 平台與環境需求

- **作業系統**：目前只在 Windows 驗證。`catos/account_lock.py` 的 `AccountLock.acquire()` 在非 `win32` 直接 `RuntimeError`（使用 `msvcrt` 檔案鎖），因此 local-sim 在 macOS／Linux 無法啟動。
- **Python**：3.11 以上；本文件的驗證使用 `.venv`（Python 3.12.10）。執行與儲存底座只有 Python 與 SQLite（WAL），不使用 Docker、PostgreSQL、Redis。
- **Node.js**：`frontend/cat-os-vite/package.json` 未宣告 `engines`；本文件的驗證使用 Node 24.19.0，Vite 6 需要 Node 18 以上。
- **換行與策略雜湊**：策略製品的 sha256 直接算在檔案位元組上，`.gitattributes` 已固定所有文字檔為 LF。Windows 使用者請設 `git config core.autocrlf false`（本 repo 已含 `.gitattributes`，兩者擇一即可）；若工作樹被轉成 CRLF，`research_catalog`／`strategy_registry` 會以 `artifact_hash_mismatch` 拒絕載入策略，測試也會失敗。

## 安裝

後端（repo 根目錄）：

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python.exe -m pip install -r requirements-http.txt
```

`requirements-http.txt` 會一併安裝 `requirements-research.txt`（optuna、mcp、tzdata）。`tzdata` 是 Windows 上 `Asia/Taipei` 時區的必要套件。

前端：

```bash
npm --prefix frontend/cat-os-vite ci
```

## 啟動

| 服務 | 埠 | 指令 |
| --- | --- | --- |
| 後端（研究 API＋local-sim 控制面＋工作台） | `127.0.0.1:8770` | `.venv/Scripts/python.exe -B -m catos.workspace_api` |
| 後端臨時預覽（研究仍由既有 8770 擁有） | `127.0.0.1:8771` | 同上加 `--preview` |
| 前端 Vite 開發伺服器（`strictPort`） | `127.0.0.1:8890` | `npm --prefix frontend/cat-os-vite run dev` |
| 整合測試隔離埠 | `18870`／`18890` | 由 `tests/simulation_integration_test.mjs` 自行啟停，不碰 8770／8890 |

FastAPI 只綁定 `127.0.0.1`。`start-laptop-dev.bat`（呼叫 `scripts/start-laptop-dev.ps1`）會核對 8890 的前端身分並在未啟動時以 Vite 啟動前端後開瀏覽器；遇到不明 owner 不接管。該腳本本輪未執行驗證。

## 研究資料

抓取需要授權（AGENTS.md：採集不因工作包自動授權）。2026-11-04 已授權的範圍是 BTC-USDT-SWAP、15m、90 天，只呼叫三個公開端點。另一台機器要用同一份資料時，以 `--end-ms` 重抓同一區間；資料集 id 相同，`candles.csv` 與 `funding.csv` 的雜湊應一致（`instrument.json` 可能因 OKX 更新欄位而不同）：

```bash
.venv/Scripts/python.exe -B tools/fetch_okx_candles.py --inst-id BTC-USDT-SWAP --bar 15m --days 90 --end-ms 1793764800000
```

工具每次請求至少間隔 0.25 秒、單次最多 150 次請求，遇到缺口、未收盤 K 線、分頁行為不符或資金費不完整就停止，不寫入任何檔案。

滾動驗證（walk-forward）可直接用這份資料：前端「滾動驗證」頁（`#/validation`）或 POST `/api/research/validations`。結果 schema 是 `catos.research.validation-result.v2`：逐根環境標籤改為各環境的 K 線數，逐根歸屬只留各環境彙總，各窗樣本外權益曲線超過上限時取樣，`data/okx` 的檔案在來源快照裡只記路徑與 sha256；績效與分環境合計仍以全部 K 線計算。送出時另檢查計算量 `windows × (候選數 × (warmup + train) + warmup + test) <= 250,000`，環境分類的回看根數上限 512，避免超過 30 秒逾時。本機以研究服務實測（6 窗、4 個候選、train 2000／test 1000）：4.35 秒，result.json 599,573 bytes。欄位見 `docs/research-validation-api.md`，方案比較與更多量測見 `docs/research-real-data-plan.md`。

## 測試

以下每條指令都實際執行過（2026-11-04）。

後端完整套件（約 4.5 分鐘；本輪結果 1393 tests、0 FAIL、0 ERROR、11 或 12 skipped：11 個是 v2 候選的 python_strategy 兩個模組，另 1 個是 `test_lot_scenario_demo` 在 Windows 無權建立 symlink（未開開發人員模式）時跳過）：

```bash
.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"
```

後端示範回測（純標準函式庫，印出合成 SMA 回測 JSON）：

```bash
.venv/Scripts/python.exe -B -m examples.closed_bar_demo
```

前端型別檢查、單元測試與建置：

```bash
npm --prefix frontend/cat-os-vite run typecheck
```

```bash
npm --prefix frontend/cat-os-vite test
```

```bash
npm --prefix frontend/cat-os-vite run build
```

端到端整合測試（以 `.venv` 的 Python 在 18870 起真實 local-sim 後端、18890 起 Vite proxy，用 headless Chrome 讀戰情台、實例監控、風控中心、系統日誌、策略中心與策略覆盤頁，驗證 Decimal 字串、無 NaN 與無展示假值；最後經代理送出一次合成資料的滾動驗證，讀滾動驗證頁核對各窗淨損益）：

```bash
node frontend/cat-os-vite/tests/simulation_integration_test.mjs
```

需要本機可用的 Chrome／Edge headless 與已建好的 `.venv`。Chrome 156（本機 156.0.8078.80 實測）的 `--dump-dom` 輸出空白，請用 `npx playwright install --only-shell chromium` 安裝 Playwright 的 `chrome-headless-shell`；測試會自動找 `%LOCALAPPDATA%\ms-playwright` 下的版本，也可用環境變數 `CATOS_CHROME` 指定路徑；截圖預設寫到系統暫存目錄的 `catos-screens`，可用 `CATOS_SCREENS` 覆寫。`frontend/cat-os-vite/tests/integration_baseline_test.mjs` 需要 playwright（未納入依賴），本輪未執行。

## 架構

```text
React 19 / Vite (8890)
   │  GET /api/workspace/simulation/{state,strategies,bots,bots/{id},risk,positions,events}
   │  POST /api/workspace/simulation/{bots/start,runs/{run_id}/stop}
   │  研究 HTTP /api/research/*
   ▼
FastAPI (127.0.0.1:8770)  catos/workspace_api.py
   ├─ local-sim 控制面  catos/local_sim_control*.py（單槽、request_id 冪等、state_version／domains）
   │     └─ runner → LocalSupervisor（catos/supervisor.py）
   │            ├─ Worker 子程序：catos/worker.py，JSON IPC（catos/ipc.py），只回純資料意圖
   │            │     └─ 策略由 catos/strategy_registry.py 依 manifest 驗證雜湊後載入
   │            ├─ 風控：catos/risk.py（R1 日基準、Soft／Hard 鎖存、曝險預算）、catos/protection.py（P6）
   │            ├─ 執行：catos/execution.py → catos/fake_exchange.py（v1 唯一交易所）
   │            └─ 帳本：catos/journal.py，SQLite WAL，schema 7，所有金額為 Decimal 字串（TEXT）
   └─ 研究：catos/research*.py（Closed Bar Decimal 回測、Optuna、OOS 驗證）
```

不變量：所有金額、價格、部位以 `Decimal`／SQLite `TEXT` 處理，禁止 float；Supervisor 獨佔交易出口、風控與寫庫，Worker 不持憑證、不連網；風控鎖存只能人工解除。完整規則見 `AGENTS.md`。

## v1 不包含

- `catos/python_strategy.py`／`strategy_library.py` 的上傳製品與 allocate 控制面（v2 候選；對應測試已 `unittest.skip`，見 `docs/simulation-api-contract-draft.md` Q1）。
- OKX Demo／Live 下單、撤單、帳戶修改與憑證載入；前端 demo／live 模式只回「未開放」。
- Yaozi 市場情報線（`catos/market_*.py`）：v1 凍結，無排程器、不主動更新，程式與測試保留；前端「市場情報」頁標示「v1 未啟用」。見 `docs/market-intel.md`。
- 策略覆盤：需要 Demo／實盤的成交與權益歷史；前端「策略覆盤」頁標示「v1 未啟用」，不顯示任何示範數字。
- 多 Bot、多合約、Kill-Switch／re-arm HTTP、P6 交易所端實際掛單。

## 文件索引

- `AGENTS.md`：專案規則、不變量、授權邊界與工作流程。
- `docs/simulation-api-contract-draft.md`：local-sim 控制面投影 HTTP 契約與第 3／4 步、v1.1 實作紀錄。
- `docs/next-steps.md`：v1 之後的候選工作包、建議順序與收尾雜項。
- `docs/research-real-data-plan.md`：研究線（真實歷史 K 線）方案、採集授權範圍與實作紀錄。
- `docs/research-validation-api.md`：滾動驗證任務的請求、限制與結果欄位（v2）。
- `docs/backend-frontend-integration-map.md`：後端路由與前端頁面的對應。
- `docs/worker.md`：Worker／IPC 契約與策略登錄。
- `docs/market-intel.md`：Yaozi 市場情報線（v1 凍結）。
- `docs/archive/`：落後 v1 實作的歷史文件（架構評估、工作計畫、交接）。

## 授權

MIT License，見 `LICENSE`。本專案僅供研究與本機模擬，不構成投資建議，使用風險自負。
