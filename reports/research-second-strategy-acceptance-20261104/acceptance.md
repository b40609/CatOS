# 第二個研究策略 Donchian 通道突破 獨立驗收報告

- 日期：2026-11-04（Asia/Taipei）
- 驗收者：Claude Opus 5.5，獨立驗收子代理。沒有參與本工作包的開發，也沒有撰寫任何 commit，具 AGENTS.md「DEVELOPMENT WORKFLOW」所定的獨驗資格。
- 範圍：worktree `C:\Users\kai\Desktop\CatOS\.claude\worktrees\second-strategy`，分支 `feat/research-second-strategy`，`2d9d6cb..a1e54ba`（1 個 commit，25 個檔案，+1331／−359）。
- 結論：**PASS（7／7）**，沒有阻斷缺陷，附 7 項非阻斷觀察（O1～O7）。依指示不 commit、不 push、不 merge。
- 自寫腳本與證據在本會話暫存目錄 `C:\Users\kai\AppData\Local\Temp\claude\C--Users-kai-Desktop-CatOS\7773c9f0-e321-4239-a3e6-bd95de1760f4\scratchpad\`（不在 repo，會話結束後可能被清掉；關鍵輸出已抄進本報告）。

## 驗收限制與隔離

- 沒有對 OKX 或任何外部服務發請求，沒有抓資料；`data/okx` 只讀。四個資料檔的 sha256 與開發者證據相同（candles `a127a291…`、funding `3969db2d…`、instrument `248697dd…`、manifest `e8fa6cc7…`）。
- 沒有修改程式、測試或文件，只新增本報告。沒有 commit、push、merge、切換分支或 stash。
- 基底比對用 `git archive 2d9d6cb` 匯出到暫存目錄，不動 git 狀態。竄改測試只改 `git archive a1e54ba` 的暫存副本。
- 只用 18870／18890。每次啟動前都確認兩埠沒有監聽。整合測試、研究服務量測、UI 驗收環境各啟停一次，結束後兩埠都沒有監聽，也沒有殘留的 fixture 或 harness 程序。沒有碰 8770／8771／8890。
- `catos` 匯入路徑指向 worktree（`...\second-strategy\catos\__init__.py`），Python 3.12.10。`git ls-files --eol`：571 個追蹤檔，0 個 CRLF。
- 執行過程在 worktree 留下的都是 git 忽略的產物：`frontend/cat-os-vite/dist`（build）、`catos/__pycache__`，以及後端套件自己寫的 `outputs/workspace-w6-fixture-test-d4e74ab9…`、`outputs/workspace-w8-fixture-test-cf4b188f…`。依指示沒有刪除。`git status` 乾淨，HEAD 仍是 `a1e54ba`。

## 總表

| # | 項目 | 結果 |
| --- | --- | --- |
| 1 | 策略規則正確、沒有偷看未來 | PASS（文件用語見 O1） |
| 2 | 只供研究的隔離；SMA 製品與 local-sim 路徑不變 | PASS（版本雜湊變動見 O5） |
| 3 | 請求驗證與預檢；SMA 契約相容 | PASS（預檢缺口見 O2） |
| 4 | 執行結果與核心引擎一致 | PASS |
| 5 | 真實資料量測的說法 | PASS（證據備註見 O7） |
| 6 | 前端 | PASS（用語見 O6） |
| 7 | 文件 | PASS（見 O1、O7；程式面觀察 O3、O4） |

## 1. 策略規則正確、沒有偷看未來：PASS

程式：`catos/research_donchian.py`。

- 決策當根不進通道：`update_indicators` 先在 `ready` 時取出四條通道值（:48-50），再把本根的 high／low 推進去（:51-53）。`on_bar` 只拿本根收盤和前一刻的通道比較（:63-71）。
- 規則：收盤 > 前 N 根最高價做多、< 最低價做空（:64-67），反向部位直接反手；多單收盤 < 前 M 根最低價、空單收盤 > 前 M 根最高價就平倉（:68-71）；其餘回 `None`。比較都是嚴格不等號。
- 預熱與 ready：`ready` 是四個極值佇列都已累積滿各自長度（:56-58）。引擎在預熱結束時要求 ready（`catos/research.py:342-343`），所以 warmup < entry_bars 會被拒絕；warmup = entry_bars 時，第一根評估 K 線就用滿 N 根的通道。
- 只用 Decimal：AST 掃描沒有 float 常數或 `float()`；只有兩處 BinOp，一處是索引運算（:24），一處是型別註記 `Decimal | None`（:60）。引擎開著 FloatOperation trap。

自寫 `check_rules.py` 的輸出：

```text
PASS hand: breakout vs prior-3 high (decision bar's own high 20 excluded) fills long at next open
PASS hand: close == prior high is not a breakout (strict comparison)
PASS hand: first evaluation bar breaks the warm-up channel low -> short at next open
PASS hand: warm-up 3 < entry 4 rejected (not ready)
PASS hand: warm-up 4 > entry 3: bar 0 (high 50) is outside the 3-bar channel, close 15.5 > 14 enters
PASS hand: gap through both channels while long reverses to -1 in one fill (delta -2)
PASS brute force == RegisteredDonchian on 250 random series (every BacktestResult field)
  total simulated fills compared: 4145
PASS look-ahead: 920 truncations, earlier fills and the pending decision never change
PASS look-ahead: perturbing every bar after t never changes decisions made at or before t
PASS static: no float literal or float() in research_donchian.py
PASS result values are Decimal
FAILURES: none
```

- 暴力法：另寫一個參考策略，用串列切片取「前 N 根」，不用 deque；規則照文件寫。250 組隨機參數（N 2～40、M < N、warmup N～N+10），在 tick 0.1 的隨機 Decimal K 線上，跟 `RegisteredDonchian` 一起跑 `catos.research.backtest`，`BacktestResult` 每個欄位都相同（共 4,145 筆成交）。
- 偷看未來：
  - 把資料截到第 k 根，前面的成交與最後一根的待成交意圖，都和完整資料的結果相同（920 次截斷）。
  - 把第 t 根之後的 K 線全部換掉，t 以前做出的決策完全不變（30 組）。
- 手算案例「多單時一根收盤同時跌破出場與進場通道」：程式直接反手，一筆 −2 張。這和 docstring、README:70 的描述一致，但和方案文件的一句話有出入，見 O1。

## 2. 只供研究的隔離：PASS（附 O5）

自寫 `check_isolation.py`，加上 git 比對：

```text
PASS worker registry manifests() keys :: [('sma-trend', 'sma-parameters-v1')]
PASS registry.resolve('donchian-breakout',) rejected :: unknown_strategy
PASS registry.resolve('donchian-breakout', 'donchian-parameters-v1') rejected :: unknown_strategy
PASS ipc.from_wire donchian artifact=None rejected :: unregistered strategy: unknown_strategy
PASS ipc.from_wire donchian artifact=donchian-parameters-v1 rejected :: unregistered strategy: unknown_strategy
PASS ipc.from_wire donchian artifact=sma-parameters-v1 rejected :: unregistered strategy: unknown_strategy
PASS ipc.from_wire default SMA still accepted :: sma-trend
PASS worker manifest directory listing :: ['sma-trend-sma-parameters-v1.json']
PASS SMA source hash == pinned == manifest :: 3b411bb170572445bc8d4a28c5647387ed08cc3846b03c0c0b36949052f92cf2
PASS Donchian source hash == pinned == manifest :: 1596e3ace639379086f6fd5ff2ba73948697c2b34884366c3b32b15ba9ba6817
```

- Worker 登錄表只 glob `catos/research_artifacts/*.json`（`catos/strategy_registry.py:25`、`:197`）。Donchian 的 manifest 在 `catos/research_only_artifacts/`，所以 `resolve` 回 `unknown_strategy`，`WorkerConfig.from_wire`（`catos/ipc.py:238-242`）回 `unregistered strategy`。即使帶上 `strategy_artifact` 也一樣。
- `strategy_registry.resolve('sma-trend').instantiate()` 仍是 `RegisteredSMA`，`closes.maxlen` 2、`quantity` 2。策略模組沒有進 `sys.modules`。
- SMA 製品沒變：
  - `git diff --stat 2d9d6cb..a1e54ba` 對下列檔案是空的：`catos/research_artifacts`、`catos/research_strategy.py`、`examples/closed_bar_demo.py`、`catos/strategy_registry.py`、`catos/ipc.py`、`catos/worker.py`、`catos/supervisor.py`、`catos/simulation_catalog.py`、`catos/local_sim*`、`catos/workspace_api.py`、`catos/research_api.py`。
  - 三個 SMA 檔的 blob 在兩個 commit 相同：manifest `add6fcf5…`、research_strategy `219b479d…`、closed_bar_demo `8a348049…`。
  - catalog 的 SMA 項目在基底與新版逐字相同（比較時去掉新增的 `warmup` 欄），含 `sha256` 與 manifest 檔雜湊 `401a8fcc…`。
- local-sim 呼叫 `validate_request(DEFAULT_REQUEST)` 的四處（`catos/local_sim_control.py:415`、`catos/local_sim_control_runner.py:52`、`catos/local_sim_r4.py:204`、`catos/local_sim_r4_verify.py:89`）都只取回傳的第 0、1 項。第 2 項從 `period` 改成參數 dict 不影響它們。
- 執行 Donchian 程式碼的只有研究子程序：`execute_*` 只由 `catos/research_worker.py:43-51` 呼叫，web 程序只驗雜湊、不 exec。
- 全庫搜尋，`donchian` 只出現在 `research_catalog.py`、`research_validation_job.py`（經由 `strategy_spec`）、`research_donchian.py`、研究專用 manifest、前端研究頁與文件。

## 3. 請求驗證與預檢：PASS（附 O2）

自寫 `check_requests.py`，同一組請求分別在基底匯出與 worktree 上跑，再用 `compare_requests.py` 比對：

```text
shared cases: 92; differing: 0
missing in head: []
```

- **SMA 完全相容**：92 個共同案例的結果字串完全相同，涵蓋回測、優化、滾動驗證的正常請求、欄位缺漏或多餘、範圍、型別（`"2"`、`True`、`2.0`）、對齊、步進上限 30、預熱、`max_candidates`、`max_runs`、計算量、資料不足與 lookback 513，以及 catalog 的 SMA 項目、defaults、範例請求。例如 `period: integer in [2, 32] required`、`warmup_bars: integer >= period and < 64 required`、`search_space: only registered period range is supported`、`low: integer in [2, 32] required`、`period: at least two aligned candidates required` 都沒變。
- **Donchian**（只在新版跑，44 個案例，結果都符合文件）：
  - 參數範圍：`entry_bars: integer in [2, 960] required`、`exit_bars: integer in [1, 959] required`、`exit_bars: must be below entry_bars`（6／6、6／7）。960／959 與 2／1 可以通過。
  - 預熱：`warmup_bars: integer >= entry_bars and < 961 required`（5、961）。
  - 每個格點都要 exit < entry：`exit_bars: highest searched value must be below lowest entry_bars`。優化與驗證都檢查，`exit.high == entry.low` 也拒絕。
  - 格點預熱：`warmup_bars: must cover highest searched entry_bars`。
  - 多參數的欄名：`entry_bars.low: integer in [2, 960] required`、`exit_bars.step: integer in [1, 958] required`、`entry_bars: aligned range required`、`search_space: at least two candidates required`。
  - 名稱不符：`search_space: only registered entry_bars and exit_bars ranges are supported`、`parameters: entry_bars, exit_bars and quantity required`。
  - 計算量：203,920 通過；282,320 → `walk-forward exceeds max_bar_evaluations before execution`。資料不足與 `max_runs` 也會拒絕。
- **未知策略**：`"SMA"`、`""`、`1`、`None`、`["sma-trend"]`、`"donchian"` 都回 `unknown_strategy`（`catos/research_catalog.py:83-87`）。
- **請求與來源綁定的策略不一致**：`registered_factory` 在載入前就以 `strategy_source_mismatch` 拒絕（`catos/research_catalog.py:481-484`）。開發者測試 `tests/test_research_donchian.py:147-155` 涵蓋兩個方向。服務送出時依請求的 `strategy_id` 算來源（`catos/research_service.py:152-153`），完成時再核對一次（`:242-245`）。
- **HTTP 層**（18870 fixture）：未知策略、exit = entry、格點重疊、計算量超限、SMA period 33 都回 422，訊息與上面相同。
- 缺口：回測與優化不檢查 warmup 是否小於資料集根數，Donchian 在 96 根合成資料上會 202 後才失敗，見 O2。

## 4. 執行結果與核心引擎一致：PASS

自寫 `check_consistency.py`：每條執行路徑都和直接呼叫 `catos.research.backtest`（策略直接 import `RegisteredDonchian`／`RegisteredSMA`）比對。

```text
PASS synthetic Donchian backtest payload['result'] == asdict(direct) (no sampling) :: trades=39
PASS OKX Donchian backtest 192/48: every non-curve result field equals direct backtest
PASS OKX Donchian backtest 192/48: 1690 returned curve points are exact direct points (total 8449)
PASS OKX optimization: 20 trials (10 distinct) equal direct backtests
PASS OKX optimization: best_trial_number is the max Decimal score :: 6 vs 6
PASS OKX optimization report shows params as name=value and the dataset notice
PASS synthetic Donchian validation: every training trial equals a direct backtest on its training slice
PASS synthetic Donchian validation: every OOS window equals a direct backtest on its test slice
PASS OKX Donchian validation 12-grid: every training trial equals a direct backtest on its training slice
PASS OKX Donchian validation 12-grid: every OOS window equals a direct backtest on its test slice
PASS OKX SMA validation (2026-11-04 SMA plan): every training trial equals a direct backtest on its training slice
PASS OKX SMA validation (2026-11-04 SMA plan): every OOS window equals a direct backtest on its test slice
FAILURES: none
```

- 回測：
  - 合成資料：`payload["result"]` 與 `asdict(direct)` 完全相等。
  - OKX：曲線以外的欄位全部相等（trades、funding、performance、pending_intent、config、assumptions）；1,690 個取樣點都是直接回測曲線上的原點，總點數 8,449。
- 優化：20 個 trial 的 performance 與 `score_decimal` 都等於直接回測，最佳 trial 是 Decimal 分數最大者。
- 滾動驗證：每窗的訓練格點（12 個）與 OOS 結果，都等於在 `bars[start − warmup : end]` 加上窗內資金費事件的切片上直接回測。Donchian 與 SMA 都驗過。
- 服務端：經 18870 研究服務跑的 5 個 Donchian 案例完成後，`result.json` 與開發者證據比對，見第 5 項。

## 5. 真實資料量測的說法：PASS（附 O7）

**開發者證據核對**：`measure-20261104/measure.json` 的 started → finished 差值是 0.7515／4.2604／4.8491／5.2468 秒，bytes 是 686,169、13,254、556,397、471,763（report 151,629、25,782、10,377、7,159），與 `docs/research-real-data-plan.md:213-216` 一致。

**證據就是目前的程式產生的**：在程序內重跑同樣 4 個案例，與開發者保存的 4 份 `*.result.json` 比對，除了 `run_id`、`created_at`、`build_id` 之外完全相同。保存檔較小（例如 643,502 對 686,169），是因為那是 HTTP 回應的精簡 JSON；內容相同。

**隔離埠重跑**（自寫 `measure_service.py`）：18870 起 `tests.integration_http_fixture`，用全新輸出根，經 HTTP 送出，結束後 `port_released: true`。

| 案例 | 任務耗時（本次） | 文件 | result.json（本次） | report.html | 與開發者結果相同 |
| --- | --- | --- | --- | --- | --- |
| 回測 192／48、預熱 192 | 0.80 秒 | 0.75 秒 | 686,169 | 151,629 | 是 |
| 優化 12 格點、20 trials | 4.20 秒 | 4.26 秒 | 13,254 | 25,782 | 是 |
| 滾動驗證 12 格點、2000／1000／6 窗 | 4.82 秒 | 4.85 秒 | 556,397 | 10,377 | 是 |
| 計算量邊緣 20 格點、預熱 960、4000／1800／2 窗 | 5.10 秒 | 5.25 秒 | 471,763 | 7,159 | 是 |
| 前端預設（由前端程式產生請求） | 4.77 秒 | 5.17 秒 | 562,531 | 10,365 | 沒有原始證據可比，見 O7 |
| SMA 同計畫（對照） | 2.69 秒 | — | 601,369 | 10,036 | — |

- 所有案例都遠低於 30 秒逾時與 2,000,000 bytes 輸出上限。最大 result.json 是 0.69 MB，最慢 5.25 秒（開發者）／5.10 秒（本次），與 `docs/next-steps.md` 一致。
- 「前端預設」的請求用前端自己的 `defaultValidationForm`／`buildValidationRequest`（Vite `ssrLoadModule`）和真實 catalog 產生：2 張、本金 1000、`warmup_bars` 384、2064／1032／6 窗、`max_candidates` 12、`max_runs` 78，計算量 184,752，`validationProblems` 為空。
- **SMA 對 Donchian 的比較**：程序內重跑兩個策略，逐窗加總：

```text
SMA      totals: fills 582 fees 236.39 est.slippage 94.56 funding 3.70 gross(after slippage) -98.42 price-before-costs -3.86 net -338.51 positive 1/6
Donchian totals: fills 55 fees 24.28 est.slippage 9.71 funding -0.33 gross(after slippage) -34.57 price-before-costs -24.86 net -58.52 positive 2/6
Donchian 各窗選定：288/24、288/24、96/24、96/72、384/24、288/24
Donchian 各窗 OOS：-0.015%、+0.140%、-0.075%、-0.281%、-0.393%、+0.038%
前端預設各窗 OOS：-0.7179%、+10.0714%、-8.4225%、-6.6394%、-2.3002%、-1.0732%（1/6 為正）
SMA 各窗選定 6 × 32；SMA 各窗 OOS：-0.794%、-0.729%、+0.042%、-0.569%、-1.042%、-0.293%
```

  - 估計滑價 = 手續費 × 0.4（名目 = 手續費 ÷ 0.0005，再乘 2 bps）；扣成本前的價格損益 = 淨損益 + 手續費 + 估計滑價 + 資金費。
  - 文件 `docs/research-real-data-plan.md:177`、`:221-234`、README:70、`docs/next-steps.md` 第 4 項的數字都相符：582 → 55、236.39／24.28、94.56／9.71、3.70／−0.33、−3.86／−24.86、−338.51／−58.52、1／6 對 2／6、4 種參數組合、331 → 34。
  - 「OOS 起點晚 352 根、約 3.7 天」：384 − 32 = 352 根 × 15 分 ≈ 3.67 天。
- 結論文字「Donchian 沒有顯示出值得上線的優勢」與數字相符，沒有誇大。

## 6. 前端：PASS（附 O6）

指令與結果：

| 指令 | 結果 |
| --- | --- |
| `npm --prefix frontend/cat-os-vite run typecheck` | exit 0（6 秒） |
| `npm --prefix frontend/cat-os-vite test` | `check:tokens` 通過；tests 19、pass 19、fail 0（3 秒）。第一次執行就完成，沒有卡住；本次沒有重跑 `npm ci`，所以開發者說的「剛 `npm ci` 完第一次會卡住」沒有重現條件 |
| `npm --prefix frontend/cat-os-vite run build` | exit 0，`tsc` 無錯，`✓ built in 10.49s`；只有既有的 chunk > 500 kB 警告 |
| `node frontend/cat-os-vite/tests/simulation_integration_test.mjs C:/Users/kai/Desktop/CatOS/.venv/Scripts/python.exe` | exit 0，37 秒，12 PASS（含 `backtest page shows a Donchian run submitted through the proxy`、`validation page shows a Donchian walk-forward with its selected channels`）；證據 `%TEMP%\catos-sim-integration-gdp4tY\result.json`；結束後兩埠沒有監聽 |

**程式核對**：

- 參數欄位由 catalog 的 `parameters` 產生（`src/lib/research-strategies.ts:39-43`）。
- 問題檢查：`paramProblems`（:66-82）、`gridProblems`（:106-119），規則與後端相同：exit < entry、每格點 exit 最大值 < entry 最小值、步進上限 = max − min、預熱 ≥ covers 且 < below。
- 三頁送出按鈕在有問題時停用：`backtest.tsx:403` 加上 `disabled={submitting || formProblems.length > 0}`，`optimization.tsx:74`，`validation.tsx` 透過 `validationProblems`。
- 請求組裝：base 參數取格點最低點、預熱取 covers 軸最大值。SMA 維持 period 2 與 `max(8, high)`。
- `validation_plan_test.mjs` 的「synthetic defaults rebuild the catalog example request exactly」確認 SMA 的請求與 catalog 範例完全相同。

**瀏覽器實操**：自寫 `ui_harness.mjs`，18870 起 fixture、18890 起 Vite 代理；用內建瀏覽器實際點擊與輸入，再以 DOM 讀回。

| 頁面 | 操作 | 結果 |
| --- | --- | --- |
| 回測 | 開對話框 | 策略單選 SMA／Donchian，SMA 預設：period 2、預熱 2 |
| 回測 | 選 Donchian（合成） | 欄位換成「進場通道 (entry_bars: 2~960)」6、「出場通道 (exit_bars: 1~959)」3、預熱 6，標籤改為「warmup: >= entry_bars」 |
| 回測 | 切 OKX | 192／48／192，無問題、可送出 |
| 回測 | exit 改 192 | 「出場通道需小於進場通道」，送出停用 |
| 回測 | 預熱改 100 | 「預熱根數需 ≥ 進場通道（192）且小於 961」，送出停用 |
| 回測 | 恢復後送出（只送到隔離 fixture） | 請求為 donchian-breakout、OKX、192／48、2 張、1000 USDT、預熱 192，complete、77 筆。淨損益 25.2296 USDT，正好是 1 張、本金 10,000 時 12.6148 的兩倍。清單顯示「Donchian 回測 · entry_bars=192, exit_bars=48」，約束區顯示「策略參數 (Donchian)」，成交流標題 `donchian-breakout`，有 −4 的反手成交 |
| 優化 | 開對話框 | SMA 2~8/1、預熱 8 |
| 優化 | 選 Donchian（合成） | 4~8/2 × 2~3/1、預熱 8 |
| 優化 | 切 OKX | 96~384/96 × 24~72/24、預熱 384 |
| 優化 | 出場最大值改 96 | 「出場通道的最大值需小於進場通道的最小值」，送出停用 |
| 優化 | 再把進場最大值改 380 | 加列「進場通道需在 2~960、最大值不小於最小值，且差距為步進的整數倍」 |
| 優化 | 切回 SMA | 恢復 2~8/1，問題清空 |
| 滾動驗證 | 開對話框 | SMA 合成：3 候選、76／96 根、12 次、計算量 312 |
| 滾動驗證 | 選 Donchian（合成） | 6 候選、預熱 8、80／96 根、21 次、648 |
| 滾動驗證 | 切 OKX | 12 候選、預熱 384、2064／1032／6、8,640／8,640 根、78 次、184,752 |
| 滾動驗證 | 出場最大值改 96 | 重疊提示，送出停用 |
| 滾動驗證 | 進場最大值改 960 | 同時列出「候選數 30 超過上限 20」「需要 186 次回測，超過上限 100」「需要 9,216 根 K 線，資料集只有 8,640 根」「計算量 556,272 超過上限 250,000」 |
| 滾動驗證 | 切回 SMA | 8~32/8、2152／1076／6、59,064 |

## 7. 文件：PASS（附 O1、O7）

逐句和程式、證據核對：

- **README**：
  - :12 Bot 只用 SMA、研究另有 Donchian、manifest 在 Worker 不讀的目錄。
  - :15 三種研究都可選策略與資料集。
  - :70 規則、範圍、預熱，以及 4.85 秒、556,397 bytes、582 → 55、338.51 → 58.52、2／6。
  - :76 後端 1408 tests、skipped 11 或 12（本次 1408、skipped 12）。
  - :102 整合測試共 12 項。
  - 以上都相符。:68 的 SMA 舊數字見 O7。
- **`docs/research-real-data-plan.md` 第二個策略一節**：
  - :177 SMA 成本拆解；:192-197 規則；:201-205 實作；:209-217 實測表；:219-234 比較與結論；:238 前端預設值與提示；:240-246 未涵蓋。
  - 都與程式和重跑結果相符。:196 的「出場一定比反手先觸發」不精確，見 O1。
  - :179、:183-188 的外部文獻與「選定前沒有試跑」屬於外部資料與流程陳述；依限制沒有上網核對，見「未涵蓋」。
- **`docs/research-validation-api.md`**：新增的策略表、對齊規則、單參數沿用 `low／high／step` 欄名、多參數用 `entry_bars.low` 欄名、報表「選定參數」以 `name=value` 列出，都與第 3 項實測一致。
- **`docs/next-steps.md`** 第 4 項：
  - 數字、「最慢 5.25 秒、最大 0.69 MB」、「尚未獨立驗收，未合併」都符合當時狀態。
  - 「優化 HTML 報表內文仍寫合成資料」改為已處理：報表改用 `payload['data_notice']`（`catos/research_optimization.py:53`），第 4 項已驗證報表不含「合成資料樣本內搜尋」。
- **`docs/worker.md`**：`WorkerConfig.from_wire` 以 `unregistered strategy` 拒絕 Donchian，測試在 `tests/test_research_donchian.py:139-145`，與實測一致。
- **AGENTS.md P1 新增句**（:51）：Donchian 只供研究、manifest 在 Worker 不讀的目錄、`research_catalog.py` 以固定白名單核對 sha256、local-sim Bot 與 IPC 解析不到。與第 2 項一致，沒有擴大權限。
- **`docs/backend-frontend-integration-map.md`**：「策略可選 SMA 或 Donchian」「後端搜尋 SMA period 或 Donchian entry_bars／exit_bars」與程式一致。
- 合併與獨驗完成後，各文件的「尚未獨立驗收」需要由開發者或 Git 核對角色更新；本報告不改文件。

## 實際執行的命令與結果

代號：`<wt>` 指 worktree；`<py>` 指 `C:\Users\kai\Desktop\CatOS\.venv\Scripts\python.exe`；`<s>` 指上面的暫存目錄。

| 命令 | 位置 | 結果 |
| --- | --- | --- |
| `git diff --stat 2d9d6cb..a1e54ba`；`git log --oneline -5`；`git status` | `<wt>` | 25 個檔案 +1331／−359；工作樹乾淨 |
| `<py> -c "import catos; print(catos.__file__)"` | `<wt>` | `...\second-strategy\catos\__init__.py`，3.12.10 |
| `<py> -m unittest discover -s tests -p "test_*.py"` | `<wt>` | `Ran 1408 tests in 217.167s`、`OK (skipped=12)`，exit 0；含預期的 `Port 61405 already in use...` |
| `<py> -m unittest discover -s tests -p "test_research_donchian.py" -v` | `<wt>` | `Ran 15 tests`、`OK`（1393 + 15 = 1408） |
| `<py> -B <s>\check_rules.py` | `<wt>` | 12 項 PASS（見第 1 項） |
| `<py> -B <s>\check_isolation.py`；`strategy_registry.resolve('sma-trend').instantiate()` | `<wt>` | 見第 2 項；`RegisteredSMA 2 2`，不進 `sys.modules`。腳本中一項 instantiate 檢查原本誤用 `period` 屬性名而顯示 FAIL，改核對 `closes.maxlen` 後通過，屬腳本本身的錯 |
| `git archive 2d9d6cb catos examples tests`，加上 `data/okx` 副本 | `<s>\base` | 基底匯出 |
| `<py> -B <s>\check_requests.py`（基底、新版各一次）＋ `compare_requests.py` | `<s>\base`、`<wt>` | `shared cases: 92; differing: 0`；Donchian 44 案例 |
| `<py> -B <s>\check_consistency.py <開發者 measure-20261104> <s>\consistency_out` | `<wt>` | 全部 PASS（見第 4、5 項） |
| `node <s>\gen_frontend_request.mjs` | `<wt>` | 前端預設 Donchian 請求，`validationProblems` 為空，計算量 184,752 |
| `<py> -B <s>\measure_service.py`（18870） | `<wt>` | 見第 5 項的表；422 案例 5 個；`port_released: true` |
| `npm --prefix frontend/cat-os-vite run typecheck`／`test`／`run build` | `<wt>` | exit 0／19 pass／exit 0 |
| `node frontend/cat-os-vite/tests/simulation_integration_test.mjs <py>` | `<wt>` | 12 PASS，exit 0 |
| `node <s>\ui_harness.mjs`（18870＋18890）配合內建瀏覽器 | `<wt>` | 見第 6 項；結束後兩埠沒有監聽、沒有殘留程序 |
| `<py> -B <s>\check_edges.py warmup_vs_dataset`／`build_files`／`tampered_donchian` | `<wt>`、`<s>\head_tampered` | 見 O2、O3、O4 |
| `<py> -B <s>\sma_size.py`（基底、新版） | `<s>\base`、`<wt>` | 見 O7 |
| local-sim `files_hash(RUNTIME_FILES)`、`build_id()`（基底、新版） | `<s>\base`、`<wt>` | 見 O5 |

## 非阻斷觀察

- **O1（方案文件一句用語不精確）**
  - `docs/research-real-data-plan.md:196` 寫「`exit_bars` 必須小於 `entry_bars`，所以出場一定比反手先觸發」。
  - 出場通道是進場通道的子區間，所以出場條件**不晚於**反手條件成立。但同一根收盤同時穿過兩條通道時，程式先檢查進場（`catos/research_donchian.py:64-67`），會直接反手，不是先平倉。
  - 開發者測試 `tests/test_research_donchian.py:72` 的第 8 根就是這種情況：空單時收盤 14.5 同時高於出場上緣 13 與進場上緣 14，結果反手。本次手算的多單跳空案例也一樣（一筆 −2 張）。
  - 程式、docstring 與 README:70 一致，只有這一句容易讓人以為不會直接反手。建議改成「出場條件不晚於反手；同一根同時成立時直接反手」。
- **O2（回測與優化不預檢預熱根數是否超過資料長度；fail-closed）**
  - `validate_request` 只要求 `entry_bars ≤ warmup < 961`（`catos/research_catalog.py:325-327`）；優化只多檢查 `check_search_grid`（`:357-362`、`:379-380`）。
  - SMA 的預熱 < 64，小於合成資料的 96 根，以前碰不到。Donchian 在 96 根合成資料上可以送出預熱 96～960。
  - 實測：entry 200／預熱 200 → `validate_request` 接受、`service.submit` 回 queued，任務以 `ResearchError: ValueError: candles must include warm-up and at least one evaluation bar` 失敗。優化 96~192 同樣被接受，在 `optimize` 預檢失敗。
  - 前端回測與優化對話框也不檢查資料長度（`frontend/cat-os-vite/src/lib/research-strategies.ts:66-82`、`src/pages/optimization.tsx:74`）。滾動驗證兩端都有檢查。
  - 不會寫出錯誤數字，只是 202 之後才失敗。建議後端加 `warmup_bars < 資料根數`，前端同步提示。
- **O3（研究 build 綁定沒有涵蓋 Donchian 檔案）**
  - `catos/research_api.py:21-30` 的 `RUNTIME_FILES`（`build_id`／`restart_required` 的來源）列了 SMA 的 `research_strategy.py` 與 manifest，但沒有 `catos/research_donchian.py` 與研究專用 manifest。`build_files()` 實測這兩個都是 False。
  - 改了 Donchian 原始碼，仍會因為 `catos/research_catalog.py:40` 釘住的 `DONCHIAN_SHA256` 而以 422 `artifact_hash_mismatch` fail-closed，不是安全缺口。只是「需要重啟」的訊號不涵蓋這兩個檔案，和 SMA 不一致。
- **O4（catalog 的耦合）**
  - `catalog()`（`catos/research_catalog.py:390-397`）對每個白名單策略都驗 manifest。
  - 在暫存副本的 `research_donchian.py` 結尾加一行後：`catalog()` → `ValueError: artifact_hash_mismatch`，GET `/api/research/catalog` 會失敗，三個研究頁都拿不到 catalog。`validate_request(SMA)` 仍然 OK；`validate_request(Donchian)` → `artifact_hash_mismatch`。
  - 這是 fail-closed，但研究專用的製品出問題時，SMA 研究頁也會一起無法載入。
- **O5（local-sim 的版本雜湊會變；預期，不是缺陷）**
  - SMA 製品與 local-sim 路徑的檔案都沒改。但 `catos/research_catalog.py` 在 local-sim 的 `RUNTIME_FILES`（`catos/local_sim_r4.py:27-35`）與 `BUILD_FILES`（`catos/local_sim_control.py:34-40`）裡。
  - 所以 runtime digest 從 `7e5a7879…` 變成 `67927fce…`，`build_id` 從 `b5d9d905…` 變成 `0a5fa9f5…`。
  - 合併後 8770 要重啟才會對上新的 build；用新程式重驗舊的 R4 證據會得到 `runtime_digest_changed`。
- **O6（前端兩處用語）**
  - 回測頁沒選任務時，約束區顯示「策略參數 (未知策略)」（`src/pages/backtest.tsx:647`；`shortName(undefined)` 回「未知策略」，`src/lib/research-strategies.ts:31`）。舊版顯示的是「週期參數 (period)」。
  - 滾動驗證對話框遇到出場與進場通道重疊時，標題顯示「候選未對齊」，摘要行顯示「候選參數未對齊」（`src/pages/validation.tsx:643`；`gridProblems` 不為空時 `candidateCount` 回 null，`src/lib/validation-plan.ts:48-52`）。實際上格點是對齊的；問題清單列出的原因正確。
- **O7（證據與歷史數字）**
  - `docs/research-real-data-plan.md:217`「前端預設」列（5.17 秒，從瀏覽器送出）在開發者證據資料夾沒有對應的原始檔。本次用前端程式產生同一請求重跑：result.json 562,531、report.html 10,365 bytes 與 6 窗報酬都相同，耗時 4.77 秒。
  - README:68 與 `docs/research-real-data-plan.md:147` 的 SMA「4.35 秒、599,573 bytes」是上一個工作包的歷史量測，上一份驗收的 O3 已說明其中 CRLF 造成的膨脹。本 commit 同一個 SMA 請求是 601,369 bytes、2.69 秒。
  - 拆開來看，result 本體 449,460 bytes 與基底相同；多出的 5,814 bytes 全部是來源快照內嵌的引擎原始碼，例如 `research_catalog.py` 從 21,094 變成 26,253 bytes。不影響「約 0.6 MB」，也不影響 Donchian 對 SMA 的比較數字。

## 未涵蓋

- **外部文獻與流程陳述**：依「不對外部服務發請求」的限制，沒有開啟核對方案文件引用的論文、Jesse 與 NautilusTrader 範例，以及候選比較的外部證據。「選定前沒有在 90 天資料上試跑任何候選」是流程陳述，repo 內沒有可核對的證據。使用者是否選定 Donchian，以任務說明與文件記載為準。
- **後端套件的環境**：只在有 `data/okx` 的 worktree 跑過，沒有另外開乾淨 clone；工作樹已確認 0 個 CRLF。沒有重做 `npm ci`。
- **視覺**：瀏覽器實操只核對 DOM 的欄位值、提示與按鈕狀態，以及一次送出，沒有檢查版面、圖表與動畫。視覺由使用者自行在網頁驗收。
- **其他機器與逾時、超限路徑**：沒有在另一台機器量測；沒有實際觸發 30 秒逾時與 2 MB 輸出超限，這兩段處理程式不在本次改動內。
