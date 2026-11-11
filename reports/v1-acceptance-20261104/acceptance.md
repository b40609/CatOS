# CatOS v1 獨立驗收報告（正式）

- 日期：2026-11-04（Asia/Taipei）
- 驗收者：Claude Opus 5.5，獨立驗收會話（筆電）。未撰寫範圍內任何 commit，具 AGENTS.md「DEVELOPMENT WORKFLOW」所定的獨驗資格。
- 範圍：`feature/catos-v1-sim` 的 `2633a59..93edeb4`，共 24 個 commit（216 檔，+5830／−32808）。其中 `b77d6b7` 是預審報告（本檔前一版），`93edeb4` 是 D1 修正。
- 結論：**PASS（6／6）**。預審發現的缺陷 D1 已由 `93edeb4` 修正，本輪覆驗通過。

## 預審報告的性質

- `b77d6b7` 是另一台 PC 上的會話撰寫的報告，判定 FAIL（5／6，缺陷 D1）。該會話撰寫過範圍內的 `5858bd2`、`8d8dd3f`，依 `835095f` 起的規定不具獨驗資格，所以那份報告只算**預審**。本檔取代它，成為正式驗收結論。
- 預審找到的 D1 經本驗收者確認屬實，並列入下方第 5 項。預審的其他敘述只作為線索；本報告的結論都以本驗收者的原始碼核對與實際執行結果為準。
- 開發者自測（後端 1373／0 FAIL、前端 typecheck 0 錯、`npm test` 10 通過、build、整合測試 5 PASS；D1 修正另附瀏覽器實點）同樣只當參考。

## 隔離方式

- 所有重跑都在暫存區的乾淨 clone 進行（`git clone -b feature/catos-v1-sim`，系統 `core.autocrlf=true`），避開使用者工作樹的未追蹤檔。Python 使用 repo 的 `.venv`（3.12.10），Node 使用 24.19.0。
- 只用合成資料，沒有讀取憑證，沒有連 OKX，也沒有碰 8770／8771／8890；瀏覽器實測使用隔離埠 18870／18890，結束後已關閉。

## 總表

| # | 項目 | 結果 |
| --- | --- | --- |
| 1 | `risk.Snapshot` 四個事實旗標 fail-closed，只有 local-sim 傳 True | PASS |
| 2 | 策略登錄、雜湊核對、Worker 不寫死、IPC 身分驗證、LF 固定 | PASS |
| 3 | 金額／價格／部位全程 Decimal 字串，前端不以 float 計算 | PASS（附觀察 O1） |
| 4 | 無 Demo／Live 下單、撤單、帳戶修改或憑證讀取路徑；只綁 127.0.0.1 | PASS |
| 5 | 戰情台、實例頁、側欄讀 local-sim 真資料；沒有 mock store，也沒有假登入 | PASS（D1 已修） |
| 6 | `tests/test_python_strategy_*.py` 的 skip 屬 v2 範圍 | PASS |

第 1–4、6 項在 `835095f` 上驗過（見「實際執行的命令與結果」）。`93edeb4` 只改 `README.md`、`personal-os-modal.tsx`、`personalOsStore.ts`，這幾項依據的程式都沒有變，所以不重做；第 5 項與 D1 在 `93edeb4` 上重驗。

## 1. Snapshot 事實旗標 fail-closed：PASS

依據：
- `catos/risk.py` `Snapshot`：`valuation_known`、`flows_known`、`margin_ok`、`position_verified` 預設都是 `False`（`f809f5a`），`__post_init__` 要求型別必須是 `bool`。
- 產品碼中唯一直接建構 `risk.Snapshot(...)` 的地方是 `catos/local_sim_r4.py` `observe()`。它明示傳入四個 `True`，並附 FakeExchange 為何成立的註解。
- 其他產生路徑：
  - `Supervisor.observe_risk_period()`（`catos/supervisor.py`）以 `dataclasses.replace` 沿用呼叫端快照的旗標，不會自行補 True。
  - `Snapshot.from_wire()` 遇到缺欄時落回預設 False。
- 在 `catos/` 搜尋 `Snapshot(`，其餘命中都是其他類別（`market_*`、`reconciliation_gate`）。
- 測試端（`tests/test_risk.py`、`test_risk_period_r1.py`、`test_simulation_workspace_api.py`）都改為明示傳入 `KNOWN` 旗標。

本驗收者自寫的驗證腳本 `snapshot_failclosed.py`，實際輸出：

```text
defaults: {'valuation_known': False, 'flows_known': False, 'margin_ok': False, 'position_verified': False}
未宣告: health=DEGRADED increase_accepted=False reason=position_not_verified
全部宣告 True: health=HEALTHY increase_accepted=True reason=exposure_reserved
僅 valuation_known=False: health=DEGRADED increase_accepted=False reason=increase_gate_closed
僅 flows_known=False: health=DEGRADED increase_accepted=False reason=increase_gate_closed
僅 margin_ok=False: health=DEGRADED increase_accepted=False reason=increase_gate_closed
僅 position_verified=False: health=HEALTHY increase_accepted=False reason=position_not_verified
缺旗標的舊 wire 還原: {全部 False}
```

任一旗標沒有宣告，都會禁止增倉；只有四項全部明示，才會放行。

## 2. 策略登錄與雜湊：PASS

依據：
- `catos/strategy_registry.py`：
  - `RegisteredStrategy.load()` 先檢查是否 `approved`，再由 `verified_sources()` 讀取原始檔。它會拒絕 symlink 與跳出 root 的路徑，接著比對聯合 sha256，不符就丟出 `RegistryError("artifact_hash_mismatch")`。
  - 執行時只用已驗證的記憶體位元組（`exec(compile(...))`），也不寫入 `sys.modules`。
  - `resolve()` 遇到未核准的策略丟出 `artifact_not_approved`，遇到未知身分丟出 `unknown_strategy`，不會退回預設策略。
  - `read_manifest()` 要求欄位完全相符，並拒絕重複鍵與非有限常數。
- `catos/worker.py`：已移除 `examples.sma_state` 的寫死匯入，改用 `strategy_registry.resolve(config.strategy_id, config.strategy_artifact)` 取得策略，再呼叫 `restore(checkpoint)`。
- `catos/ipc.py` `WorkerConfig.from_wire()`：身分必須通過 `strategy_registry.resolve()`，失敗時轉成 `ProtocolError("unregistered strategy: …")`。
- `.gitattributes`：`* text=auto eol=lf`，二進位格式設為 `-text`。唯一的 manifest 是 `catos/research_artifacts/sma-trend-sma-parameters-v1.json`，狀態為 `approved`。

本驗收者自寫的驗證腳本 `registry_check.py` 會在暫存目錄複製 manifest 與原始檔後竄改。實際輸出：

```text
real load: RegisteredSMA
copy load: RegisteredSMA
PASS source tampered: RegistryError(artifact_hash_mismatch)        # 只把一個 \n 換成 \r\n
PASS unapproved resolve: RegistryError(artifact_not_approved)
PASS unapproved direct load: RegistryError(artifact_not_approved)
PASS unknown id: RegistryError(unknown_strategy)
PASS wire unknown strategy_id: ProtocolError(unregistered strategy: unknown_strategy)
PASS wire unknown artifact: ProtocolError(unregistered strategy: unknown_strategy)
wire ok: sma-trend
strategy modules in sys.modules after load: []
```

LF 實測：在系統 `core.autocrlf=true` 的環境做乾淨 clone，`git ls-files --eol` 顯示 556 檔是 `w/lf`，`w/crlf` 為 0 檔。

## 3. Decimal 全程：PASS（附觀察 O1）

依據：
- 後端：新增的投影 `catos/simulation_catalog.py` 全部用 `Decimal`，例如 `period_pnl_ratio = str(pnl / Decimal(basis["equity"]))`。`local_sim_control.py`、`local_sim_control_api.py` 的新增碼沒有 `float(` 或 `round(`。
- `src/contracts/decimal.ts`：`DecimalString = string`。
- `src/lib/format.ts`：
  - `formatDecimal` 與 `roundTo` 用字串和 `BigInt` 做四捨五入；`shiftDecimal` 直接在字串上移動小數點；`signOf`／`toneOf` 用字串判斷正負。
  - 唯一的 float 轉換是 `toPlotNumber`，註明只供繪圖幾何使用。
- `src/state/stateAdapter.ts`：只做版本比較與事件游標的整數運算，不碰金額。
- 前端搜尋 `parseFloat|Number(` 的命中：
  - `account-equity-band`、`allocation-donut-card`、`v0-bot-table` 都經 `toPlotNumber`，只用來算座標。
  - `backtest.tsx` 與 `backtest-underwater-chart.tsx` 的 `parseFloat` 只用於判斷正負號和畫圖，而且在 `2633a59` 之前就存在，不是本範圍新增。
- 整合測試斷言 `bot.equity === '999.91375990'`、`fees === '0.00404010'`，所有 Decimal 欄位都是字串，且符合 `^-?\d+(\.\d+)?$`。

## 4. 無交易出口，只綁 127.0.0.1：PASS

依據：
- 後端只改了 9 個 `catos/*.py`，`tools/` 與 `scripts/` 沒有變更。對差異的新增行搜尋 `os.environ|getenv|api_key|secret|passphrase|credential|/api/v5/trade|place_order|cancel|requests.|httpx|urlopen|0.0.0.0|host=`，結果為 0 筆。
- 新增的路由都在 `local_sim_control_api.py`：
  - GET `/state`、`/strategies`、`/bots`、`/bots/{id}`、`/risk`、`/positions`、`/events`，以及 POST `/bots/start`。
  - `/bots/start` 會拒絕 `mode != "local"`；檔內定義 `FORBIDDEN_MODES = {"demo","live"}`。
  - 沒有 POST `/strategies` 或 POST `/bots`。
- 綁定位址：`catos/workspace_api.py` 用 `listener.bind(("127.0.0.1", port))`，並設 `uvicorn.Config(host="127.0.0.1")`；`catos/research_api.py` 同樣只綁 `127.0.0.1`。
- 前端 `simulation-api-adapter.ts` 在 demo／live 模式下不發請求，只回 `mode_not_open`。`npm test` 的 live 案例實測確認：不送請求，變更類操作回 403。
- `93edeb4` 移除了前端的 `setApiCredentials`，前端從此沒有任何輸入或保存金鑰的程式。

## 5. 前端讀真資料、無 mock store、無假登入：PASS（D1 已修）

已刪除的檔案：`src/adapters/mock-adapter.ts`、`src/mock/default-data.ts`、`src/lib/mock/market-tape-10m.ts`、`src/lib/mock/unified-events.ts`、`src/lib/v0-engine.ts`、`src/lib/auth.tsx`、`src/pages/profile.tsx`。

在 `93edeb4` 對整個 `src/` 搜尋 `mock-adapter`、`default-data`、`INSPECTOR_BOTS`、`usePreviewStore`、`liveMarketStore`、`MARKET_TAPE`、`useAuth`、`login`，結果為 0 筆。

各畫面的資料來源：
- 戰情台：`src/pages/index.tsx` `renderCard` 的 7 張卡片分別由 `AccountEquityBand`、`ActivityPanel`、`V0BotTable`、`AllocationDonutCard`、`UnifiedIncidentActivityCard` 呈現，這些元件都是 `useCatStore`／`StateAdapter` 的消費者。
- 實例頁 `src/pages/bots.tsx`、側欄 `simulation-status-strip.tsx`（由 `shell.tsx` 掛載）與 `account-menu.tsx` 同樣讀 store；`App.tsx` 啟動 `stateAdapter`。
- 假登入已移除，`account-menu` 顯示「本機單人終端 · 無登入」。

README 的「v1 範圍」已如實揭露：策略中心、風控中心、日誌、設定、市場情報仍是展示資料。這些頁面不屬於本項的「戰情台／實例頁／側欄」範圍。

### D1（預審發現，已修正、已覆驗）

缺陷內容：側欄帳戶選單 →「OKX 專用子帳戶 API」分頁（`personal-os-modal.tsx`，`activeTab === "api"`）出現以下假狀態：
- 假金鑰 `okx_api_••••••••38f2` 與 Passphrase，預設值來自 `personalOsStore.ts`。
- 預設 `environment: "live"`，畫面以綠色高亮「LIVE 實盤」。
- 寫死的 `ping: 18`，綠字顯示「18 ms」。
- 主題預覽卡上的「18ms WS」標示。

這些內容與 v1「不接 Demo／Live、不碰憑證」不符。

修正 `93edeb4` 的核對結果：
- `src/state/personalOsStore.ts`：
  - `PersonalOsState` 移除 `apiKey`、`passphrase`、`environment`、`ping` 與 `setApiCredentials`、`setEnvironment`。
  - store 預設值不再有這些欄位，`save()` 寫入 localStorage 的 payload 也不再包含它們。
- `src/components/catos/personal-os-modal.tsx`：
  - API 分頁改為 `ShieldOff`，標題「OKX 專用子帳戶 API · v1 未接線」，說明 v1 不載入金鑰、沒有 Demo／Live 下單路徑。
  - 「本地服務狀態」改讀 `useCatStore` 的 `connection.status` 與 `service.instance_id`／`slot`。
  - 主題預覽卡上的「18ms WS」已移除。
- 對 `src/` 搜尋 `apiKey|passphrase|Passphrase|setEnvironment|setApiCredentials|38f2|\bping\b|18ms|18 ms|WS 延遲|LIVE 實盤`：只剩 CSS 的 `animate-ping` 與 `src/lib/mock/data.ts` 的日誌頁展示字串（屬於 README 已揭露的展示頁），API 分頁與側欄不再有命中。
- 瀏覽器實測：在乾淨 clone 以 `tests.integration_http_fixture` 在 18870 起 local-sim 後端、在 18890 起 Vite proxy，在內建瀏覽器開啟後點「帳戶選單 →『OKX 專用子帳戶 API』」。
  - 實測前先在 localStorage 塞入修正前格式的舊值（`apiKey: okx_api_STALE_9999`、`environment: live`），模擬舊使用者。
  - 分頁實際文字：「OKX 專用子帳戶 API · v1 未接線」、「連線 ok」、「instance 51501dc3… · slot idle」。
  - 全頁搜尋 `STALE|38f2|LIVE 實盤|18 ms|18ms|Passphrase`：`false`。舊的 localStorage 值仍留在瀏覽器中，但不會被讀取或顯示，下次儲存偏好時就會被覆寫掉。

## 6. python_strategy 的 skip 屬 v2：PASS

依據：
- `4133d37` 只在 `PythonApiTests`、`PythonWorkerTests`、`LibraryAndRunTests` 三個類別加上 `@unittest.skip("v2 候選：…Q1")`，測試本體沒有修改。
- 本驗收者把 skip 拿掉後實跑（`unskip_python_strategy.py`）：11 個測試中 8 個 ERROR、2 個 FAIL，原因全部是功能未實作：

```text
4 TypeError: WorkerConfig.__init__() got an unexpected keyword argument 'python_strategy'
3 AttributeError: 'LocalSimControlService' object has no attribute 'library'
1 KeyError: 'artifact_hash'          # POST /strategies 回 405，取不到建立結果
1 AssertionError: 405 != 201         # POST /strategies 未掛載
1 AssertionError: 405 != 409         # 同上
```

- `git log --all -S'self.library' -- catos` 查無任何提交，可見上傳製品與 allocate 控制面從未存在，不是被 v1 改壞。這與契約文件第 0 節第 2 點及 Q1 的定案一致。
- 跳過數是 11 或 12：另 1 個是 `test_lot_scenario_demo` 在無權建立 symlink 時呼叫 `skipTest`。本機實測為 12，與 `93edeb4` 修正後的 README 說法一致。

## 實際執行的命令與結果

`<clone>` 指 `835095f` 的乾淨 clone，`<clone2>` 指 `93edeb4` 的乾淨 clone；`.venv` 是 `C:\Users\kai\Desktop\CatOS\.venv`。

| 命令 | 位置／版本 | 結果 |
| --- | --- | --- |
| `git clone` 後 `git ls-files --eol` | `<clone>` `835095f` | 556 檔 `w/lf`，0 檔 `w/crlf` |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"` | `<clone>` `835095f` | `Ran 1373 tests in 268.952s`、`OK (skipped=12)` |
| `npm run typecheck`／`npm test`／`npm run build` | `<clone>` `835095f` | exit 0／10 pass 0 fail／exit 0 |
| `node tests/simulation_integration_test.mjs <.venv python>` | `<clone>` `835095f` | 5 PASS |
| `snapshot_failclosed.py`、`registry_check.py`、`unskip_python_strategy.py` | repo 根目錄，`PYTHONPATH=.;tests` | 輸出見第 1、2、6 項 |
| `npm run typecheck` | `<clone2>` `93edeb4` | exit 0 |
| `npm test` | `<clone2>` `93edeb4` | tests 10、pass 10、fail 0 |
| `npm run build` | `<clone2>` `93edeb4` | exit 0 |
| `node tests/simulation_integration_test.mjs <.venv python>` | `<clone2>` `93edeb4` | exit 0，5 PASS（`/state` 經 proxy、合成 run 全 Decimal 字串、`since_version` unchanged、戰情台 DOM、實例頁 DOM 無 NaN／mock 值） |
| 瀏覽器實點 API 分頁（18870／18890） | `<clone2>` `93edeb4` | 見第 5 項 D1 |

後端在 `93edeb4` 沒有變更（`git diff 835095f..93edeb4 -- catos tests` 為空），所以 `835095f` 的完整套件結果適用。合併 main 之後的重跑，記錄在合併 commit 之後的回報中。

## 非阻斷觀察

- **O1（前端顯示）**：`account-equity-band.tsx` 懸停標籤的百分比是用 float 算的（第 84 行 `(v / base - 1) * 100`，第 147 行 `toFixed(2)`）。`allocation-donut-card` 的占比 `%` 也一樣。它們不是金額、價格或部位，也不會回流帳務或風控，但與 `toPlotNumber` 註解的精神不一致。建議之後改用字串計算。
- **O2（模式選單文案）**：`mode-selector.tsx` 的 `MODES` 把 Demo／Live 描述成「OKX 模擬交易」「OKX 實盤連線 · 真實 USDT-M SWAP 交易」，沒有標示 v1 未開放。實際選取後不會發出任何請求，側欄狀態列顯示「LIVE · 模式未開放」，戰情台與實例頁顯示「此模式未開放（demo/live 不在 v1 範圍）」。因為選取後的狀態是如實呈現的，不同於 D1 那種「預設就假裝已連線」，所以不判 FAIL。建議在選單文案加上「v1 未開放」。
- **O3（固定標籤）**：API 分頁的「本地服務埠 127.0.0.1:8770」是寫死的文字，在隔離埠或 8771 preview 下不會反映實際的埠。這屬於靜態說明，不影響判定。
- **O4（信任邊界，符合 P1）**：manifest 雜湊只涵蓋 `source_files`；策略匯入的 `catos.research` 等執行期模組照一般方式從磁碟載入，不在雜湊範圍內。這符合 AGENTS.md P1「受信策略邊界」，在此記錄以免被誤讀為完整的供應鏈驗證。
- 補充：`.gitignore` 第 47 行 `/reports/*` 會忽略本報告，提交時以 `git add -f` 單獨加入此檔。

## 未涵蓋

- 沒有逐頁人工檢視畫面。UI 以程式碼核對、整合測試（headless DOM）與 API 分頁的單點實測為證據；整體視覺由使用者自行驗收。
- 沒有跑 `tests/integration_baseline_test.mjs`（需要 playwright，未納入依賴），也沒有跑 `start-laptop-dev.bat`。
- 沒有啟動 8770／8771 正式服務、沒有使用既有資料根，也沒有做全市場回測、採集或 Demo／Live。
- 沒有在 macOS／Linux 驗證（`AccountLock` 只支援 win32）。
