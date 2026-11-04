# CatOS v1 獨立驗收報告

- 日期：2026-11-04（Asia/Taipei）
- 範圍：`feature/catos-v1-sim`，`5a101d4..ba51c1b`，共 21 個 commit（214 檔，+5669／-32714）
- 驗收者：Claude Opus 5.5（由使用者在本次提示詞指定）
- 結論：**FAIL**（6 項中 5 項 PASS，第 5 項 FAIL）。依指示只 commit 本報告到 `feature/catos-v1-sim`，不動 `main`。

## 利益揭露與角色

- AGENTS.md「DEVELOPMENT WORKFLOW」與「SESSION HANDOFF」記載的獨驗角色是 GPT-6 Sol。本次由使用者在提示詞中另行指定驗收者，本報告不代表 GPT-6 Sol 的獨驗。
- 範圍內 `faefef15`（test_research_cli UTF-8）與 `ba51c1b8`（整合測試可攜性＋README）由本驗收者在前一工作包撰寫，只改測試與文件。這兩個 commit 不影響下列 6 項結論的依據，但它們本身不算獨立驗收。
- **資格限制**：本報告寫完後，遠端出現 `cc2433d3`（2026-11-04 09:50，只改 AGENTS.md），規定「獨立驗收由未參與該工作包開發的另一個 Claude 會話或子代理執行」、「不得由同一工作包的開發會話自行充任」。本驗收者與上述兩個 commit 出自同一會話，依新規定**不具獨驗資格**。本報告應視為預審，正式獨驗請改由另一個未參與開發的 Claude 會話或子代理重做。`cc2433d3` 本身只改文件，不在本次核對範圍內。
- 開發者自測（後端 1373／0 失敗、前端 typecheck、10 個前端測試、整合 5/5）只當參考。下列結論依原始碼核對與本輪實際執行。

## 總表

| # | 項目 | 結果 |
|---|---|---|
| 1 | risk.Snapshot 四旗標 fail-closed，只有 local-sim 傳 True | PASS |
| 2 | strategy_registry 只收 approved、sha256 核對、worker 不寫死、LF | PASS |
| 3 | 金額／價格／部位全程 Decimal 與字串，前端不用 float 計算 | PASS（附觀察） |
| 4 | 無新增 Demo／Live 下單、撤單、帳戶修改、憑證讀取；只綁 127.0.0.1 | PASS |
| 5 | 戰情台、實例頁、側欄接 local-sim 真資料，無殘留 mock 或假登入 | **FAIL** |
| 6 | 被 skip 的 python_strategy 測試屬 v2，不是掩蓋失敗 | PASS |

## 1. risk.Snapshot 四旗標：PASS

依據：
- `catos/risk.py` `Snapshot`：`valuation_known`、`flows_known`、`margin_ok`、`position_verified` 預設皆為 `False`（commit `479f9a69`，原為 `True`）。`__post_init__` 要求型別必須是 `bool`。
- 正式程式中建構 `risk.Snapshot(` 的地方只有一處：`catos/local_sim_r4.py` `observe()`。這裡明示傳入四個 `True`，路徑是 FakeExchange（`local_sim_control_runner.py` 從 `local_sim_r4` 匯入 `observe`，交易所是 `catos.fake_exchange.FakeExchange`）。
- 其他產生路徑：
  - `Snapshot.from_wire()` 用 `cls(**values)`，而 `to_wire()` 以 `vars(self)` 寫出全部欄位，所以已持久化的快照都帶明示旗標；欄位缺漏時會落到預設 `False`，也就是 fail-closed。
  - `catos/supervisor.py` `observe_risk_period()` 用 `replace(snapshot, ...)`，保留呼叫端的旗標，不會自行補 `True`。正式程式中沒有呼叫端，只有測試呼叫，且已明示傳入（`tests/test_risk_period_r1.py`）。
  - `catos/journal.py:297` 還原時設 `snapshot=None`。
- 讀取端：`risk.py`（health 判定、禁增倉條件）、`journal.py:645`、`protection.py:195` 都把 `False` 當成未知而降級。
- 全庫搜尋 `Snapshot(`（排除 tests／outputs／frontend）後，其餘結果都是其他類別（`VenueMarketSnapshot`、`OwnershipSnapshot` 等），或 `workbench_prototype.py` 內嵌的 JS 字串，與此無關。

實際執行：
- `.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_risk*.py"` → `Ran 48 tests … OK`
- `… -p "test_local_sim_control*.py"` → `Ran 28 tests … OK`
- `… -p "test_simulation_workspace_api.py"` → `Ran 14 tests … OK`

## 2. strategy_registry／LF：PASS

依據：
- `catos/strategy_registry.py`：
  - `resolve()` 只回傳 `approved`；沒有 approved 時丟出 `artifact_not_approved`，多個 approved 時丟出 `ambiguous_strategy_version`。
  - `RegisteredStrategy.load()` 先檢查 `approved`，再呼叫 `verified_sources()` 計算 source_files 的聯合 sha256，不符時丟出 `artifact_hash_mismatch`。
  - 執行用的是已驗證的 bytes（`exec(compile(snapshot[...]))`），驗證後檔案被換掉也不會執行到新內容，沒有 TOCTOU 問題；也不寫入 `sys.modules`。
  - `read_manifest()` 要求欄位完全相符、拒絕重複鍵與 NaN 類常數、拒絕 symlink 與跳出 root 的路徑；任何一份 manifest 無效，整個 registry 就 fail-closed。
- `catos/worker.py` `run()`：用 `strategy_registry.resolve(config.strategy_id, config.strategy_artifact)` 取得策略；已移除寫死的 `examples/sma_state.py`（commit `be72e70f` 刪檔）。`catos/ipc.py` `WorkerConfig.from_wire` 也經由 registry 驗證身分。
- `.gitattributes`：`* text=auto eol=lf`，二進位格式設 `-text`。`git ls-files --eol` 中 `i/crlf` 或 `w/crlf` 為 0 筆；`git check-attr eol` 對兩個策略原始檔回報 `lf`。
- 唯一 manifest：`catos/research_artifacts/sma-trend-sma-parameters-v1.json`，`approval_state: approved`，sha256 `3b411bb1…2cf2`。

實際執行：
- 獨立竄改探針（本驗收者撰寫，放在 repo 外的 scratchpad 目錄，以 `directory`／`root` 參數指向暫存複本，不改動 repo）：

  ```
  PASS baseline loaded
  PASS crlf artifact_hash_mismatch
  PASS one_byte artifact_hash_mismatch
  PASS pending artifact_not_approved
  PASS wrong_sha artifact_hash_mismatch
  PASS extra_field artifact_manifest_exact_fields_required
  repo_tree PASS
  ```
- `… -p "test_strategy_registry.py"` → `Ran 6 tests … OK`；`test_ipc.py` → `Ran 11 … OK`；`test_worker*.py` → `Ran 15 … OK`

## 3. Decimal 與字串：PASS（附觀察）

依據：
- 後端：範圍內改到的 9 個 `catos/*.py` 都沒有 `float(` 或 `: float`。`simulation_catalog.py` 以 `str(Decimal)` 輸出；整合測試對 `summary`、`risk.derived`、`risk.limits`、`risk.snapshot.mark` 與每筆 signal 的 `mark` 斷言型別為字串且符合 `^-?\d+(\.\d+)?$`。
- 前端契約 `src/contracts/*.ts`：金額欄位是 `DecimalString`；型別為 `number` 的只有版本、序號、計數與時間戳。
- `src/lib/format.ts`：`formatDecimal`、`roundTo`（BigInt 四捨五入）、`shiftDecimal`、`signOf` 都用字串或整數運算。唯一的 float 轉換點是 `toPlotNumber`，註明只供繪圖。
- 戰情台與實例頁的金額標籤（`allocation-donut-card.tsx` 的 `amountStr`、`v0-bot-table.tsx`）全部來自 `formatDecimal(後端字串)`。

觀察（不構成 FAIL，屬於顯示用衍生比例，不是帳務或風控依據）：
- `account-equity-band.tsx:81-147`：hover 與 Y 軸上的「報酬 %」標籤，是先用 `toPlotNumber(equity)` 轉成 float，再算 `(v / base - 1) * 100` 後以 `toFixed(2)` 顯示。這與 `toPlotNumber` 註解「結果不得格式化回標籤」的精神不一致，只是數字是比例、不是金額。
- `allocation-donut-card.tsx:444, 563, 845, 895`：占比 `pct_share.toFixed(1)%` 同樣由 float 算出。
- 非 v1 範圍的頁面（`pages/backtest.tsx`、`components/catos/backtest-underwater-chart.tsx`）用 `parseFloat` 判斷正負號與畫圖，`displayMaxDd` 會把 float 重新顯示成文字。這些頁面屬於研究頁，不在本項的戰情台與實例頁範圍。

## 4. 無新增交易／憑證路徑，只綁 127.0.0.1：PASS

依據：
- 對範圍內新增行（`catos`、`examples`、`scripts`、`frontend/cat-os-vite/src`、`vite*.ts`）搜尋 `okx.com|/api/v5|place_order|cancel_order|amend|api_key|secret|passphrase|credential|os.environ|getenv|requests|httpx|urllib|socket.|aiohttp|websocket|host=|0.0.0.0|uvicorn.run|withdraw|transfer`：只命中 1 行，是 `personal-os-modal.tsx` 中 `Passphrase` 標籤的字級 class 變更（原本就存在的唯讀顯示，見第 5 項）。
- 新增的 HTTP 路由（`catos/local_sim_control_api.py`）：GET `/state`、`/strategies`、`/bots`、`/bots/{id}`、`/risk`、`/positions`、`/events`，以及 POST `/bots/start`。POST 只啟動 FakeExchange 合成案例：`local_sim_control_runner.py` 只匯入 `catos.fake_exchange`，沒有 OKX client。控制面模組中沒有 `environ`、`getenv` 或憑證存取。
- 綁定位址：
  - `catos/workspace_api.py:203` `listener.bind(("127.0.0.1", port))` 搭配 `uvicorn.Config(host="127.0.0.1")`，控制面經 `mount_simulation` 掛在這裡。
  - `catos/research_api.py:212, 222` 同樣只綁 127.0.0.1。
  - `frontend/cat-os-vite/vite.config.ts` 設 `host: '127.0.0.1'`、`strictPort`。
- 既有、範圍外的項目：`catos/market_api.py` `serve(host="127.0.0.1")` 可帶參數，但全庫沒有呼叫端傳入其他 host（Yaozi 已凍結）。`catos/demo_collection.py` 是既有的 I-b-4 唯讀採集，本範圍未修改。

## 5. 前端真資料／無 mock、無假登入：FAIL

通過的部分：
- 戰情台（`#/`）與實例頁（`#/bots`）：整合測試在真實 local-sim fixture 與 Vite proxy 下，用 headless 瀏覽器讀取 DOM：權益 `999.91` 與 bot id `sim-control-sma` 出現，沒有 NaN、`undefined`、舊 mock 字串（`tabby`、`BOT-BTC-15M`、`$69,888` 等），未接線項目明確標示「未接線」。
- 側欄狀態列：`simulation-status-strip.tsx` 讀取 store 的 service 與 connection；`account-menu.tsx` 頂部顯示 `build`、`slot`、`connection.status`。
- 假登入已移除：`account-menu.tsx:281-283` 顯示「本機單人終端 · 無登入」（commit `e87b6cc4`）。
- 戰情台、實例頁與側欄的元件都沒有匯入 `lib/mock` 或 `use-live`。

缺陷 D1（造成 FAIL）：側欄帳戶選單 →「OKX 專用子帳戶 API」開啟的偏好設定分頁，仍呈現 mock 的連線狀態。
- 入口：`src/components/catos/account-menu.tsx:231-240`，選單項目本身標示「未接線」。
- 內容：`src/components/catos/personal-os-modal.tsx`（`activeTab === "api"` 區塊，約 632-713 行）：
  - 綠色 ShieldCheck 加上標題「OKX 專用子帳戶金鑰連線」。
  - 唯讀顯示假金鑰 `okx_api_••••••••38f2` 與 Passphrase `••••••••`，來源是 `src/state/personalOsStore.ts:510-511` 的預設值。
  - 環境切換預設 `"live"`（`personalOsStore.ts:512`），畫面以綠色高亮「LIVE 實盤」。
  - 「WS 延遲 (Ping)」以綠字顯示 `18 ms`，數值寫死在 `personalOsStore.ts:513` `ping: 18`，全庫沒有任何地方更新它。
- 情境：使用者打開這個分頁，會看到「已連上 OKX、LIVE 實盤、延遲 18 ms」的假狀態，與 v1「不接 Demo／Live、不碰憑證」不符，也與選單上的「未接線」標示矛盾。
- 嚴重度：中低。只影響顯示，沒有網路請求，也沒有寫入或讀取真實憑證（`setApiCredentials` 全庫沒有呼叫端）。
- 建議修法（最小）：把 api 分頁改成「v1 未接線」的說明，移除假金鑰、LIVE／SIM 切換與 ping 顯示，並刪掉 `personalOsStore` 中 `apiKey`、`passphrase`、`environment`、`ping` 的預設假值。

範圍外但需知悉：README 第 15 行已揭露，策略中心、風控中心、日誌、設定、市場情報頁仍是展示資料（例如 `pages/risk.tsx` 用 `useLiveNumber` 產生隨機數，並標示「展示資料 · 本地風控模擬」）。這些頁面不屬於本項範圍，不計入 FAIL。

實際執行：
- `node frontend/cat-os-vite/tests/simulation_integration_test.mjs` → 5 項全部 PASS（自動選到 Playwright chrome-headless-shell），證據目錄 `%TEMP%\catos-sim-integration-8hzDxL`。
- `npm --prefix frontend/cat-os-vite run typecheck` → 0 錯誤。
- `npm --prefix frontend/cat-os-vite test` → `tests 10, pass 10, fail 0`。

## 6. python_strategy skip：PASS

依據：
- skip 只出現在 `tests/test_python_strategy_api.py` `PythonApiTests`，以及 `tests/test_python_strategy_v1.py` 的 `PythonWorkerTests` 與 `LibraryAndRunTests`，合計 11 個測試，與全套件的 `skipped=11` 相符。理由註明為 v2 候選，見 `docs/simulation-api-contract-draft.md`（第 1 節「不提供（v1）：POST /strategies、POST /bots」與第 6 節 Q1）。
- 本驗收者把 `@unittest.skip` 去掉後執行複本（放在 scratchpad，不改動 repo）：`Ran 11 tests … FAILED (failures=2, errors=8)`，原因全部是正式功能不存在：
  - `TypeError: WorkerConfig.__init__() got an unexpected keyword argument 'python_strategy'`（4 個）
  - `AttributeError: 'LocalSimControlService' object has no attribute 'library'`（3 個）
  - `KeyError: 'artifact_hash'`（1 個）
  - `POST /strategies` 回 `405`（2 個）
- 這些功能在 `5a101d4` 與 `ba51c1b` 都不存在，`git log --all -S"python_strategy=" -- catos/ipc.py` 也沒有任何結果，可見它們從未存在於任何分支。測試檔最早由 `2290593f`（2026-10-22）加入，當時就無法通過，所以這些 skip 不是在掩蓋 v1 的回歸。
- 其他 skip（`skipUnless win32`、symlink 不可用時的 `skipTest`）在本機都沒有觸發。

## 本輪未涵蓋

- 完整後端套件：本輪沒有重跑，只跑了上列受影響的 7 組。上一工作包在 `b2c9ce27` 跑過完整套件（`Ran 1373 tests … OK (skipped=11)`，屬歷史證據）；之後 `faefef15`、`ba51c1b8` 只改測試與 README。
- README 寫「12 skipped」，本機實測是 11，可能是筆電上 symlink 不可用而多出 1 個 skip。這是文件與實測的差異，未修正。
- 沒有逐檔審查 73 個被刪除的前端檔案。只確認戰情台、實例頁與側欄沒有匯入任何殘留的 mock 模組，以及 typecheck 通過。
- `strategy_registry` 的 `hooked_import` 只攔截 manifest 列出的模組，策略匯入的其他模組照一般 import 從磁碟載入，不經雜湊核對。這符合 AGENTS.md P1「受信策略邊界」，不屬於沙箱保證。
- `research_catalog.py` 仍有一套平行的固定 SMA 載入器（`_strategy_from_verified_snapshot`、`APPROVED_STRATEGY_SHA256`），只供研究路徑使用，也會檢查 approved 與 sha256。它與 registry 重複，但不屬於本項「worker 不寫死」的範圍。
- 沒有做人工視覺驗收（依 AGENTS.md「交付驗收鐵律」由使用者自行驗收畫面）。
- 沒有連 OKX、沒有讀取憑證或環境變數中的機密。
