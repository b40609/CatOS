# 滾動驗證接上真實資料 獨立驗收報告

- 日期：2026-11-04（Asia/Taipei）
- 驗收者：Claude Opus 5.5，獨立驗收會話（筆電）。沒有撰寫本工作包任何 commit，具 AGENTS.md「DEVELOPMENT WORKFLOW」所定的獨驗資格。開發者是另一個 Claude 會話。
- 範圍：`feat/research-validation-real-data` 的 `3f5ee9b..280dff4`，2 個 commit：
  - `2b47779`：本工作包，20 個檔案（+1704／−226）。
  - `280dff4`：只改 `docs/next-steps.md` 的「收尾雜項」表格（+9／−9）。
- 結論：**PASS（7／7）**，附 4 項非阻斷觀察。依指示只 commit 本報告，不合併、不 push。
- 自寫腳本與證據放在群組筆記資料夾 `side-session-notes\local_d1eea98d-4f4a-472b-94b3-c4e5ceebedff\validation-real-data-acceptance\`（不在 repo）。

## 驗收限制與隔離

- **沒有對 OKX 發出任何請求。** 研究服務 fixture 只綁 127.0.0.1，資料都來自本機副本。
- **沒有修改 `data/okx`。**
  - 資料集複製到暫存 clone 使用；竄改測試只改暫存 clone 裡的副本，測完還原。
  - 驗收結束時，四個原始檔的 sha256 與修改時間（12:11:38.93）都沒有變。
- **重驗都在乾淨 clone 上做**：`git clone -c core.autocrlf=false`，分支 HEAD `280dff4`、main `3f5ee9b`，`git ls-files --eol` 為 563 個 LF。
  - Python 用 repo 的 `.venv`（3.12.10）；Node 24.19.0、npm 11.17.0。
  - 前端以 `npm ci` 全新安裝。
- **只用 18870／18890。** 開始前確認兩埠沒有監聽；用完關閉，確認兩埠都能重新綁定、fixture 程序已結束。
- **沒有碰** 8770／8771／8890、既有資料根或憑證；共用工作目錄沒有切分支、stash 或 reset。

## 總表

| # | 項目 | 結果 |
| --- | --- | --- |
| 1 | 合成資料語義不變（v1 → v2） | PASS |
| 2 | 真實資料正確性（逐窗重播、取樣曲線） | PASS |
| 3 | 計算量預檢、30 秒逾時、2,000,000 bytes 上限 | PASS（附觀察 O1、O2） |
| 4 | 來源快照與報表頁尾 | PASS |
| 5 | 前端 | PASS（附觀察 O4） |
| 6 | 後端完整套件 | PASS |
| 7 | 文件與實測一致、收尾表格 | PASS（附觀察 O3） |

## 1. 合成資料語義不變：PASS

在 main 與分支的乾淨 clone 各跑一次 `execute_validation(DEFAULT_VALIDATION, provenance())`，再逐欄比對（自寫 `run_default_validation.py`、`compare_v1_v2.py`）。預期值是 v1 result 刪掉 `labels` 與各窗 `evaluation.intervals`，再加上 `label_counts`（v1 labels 依七類計數）與 `omitted_detail`：

```text
schema catos.research.validation-result.v1 -> catos.research.validation-result.v2
v1 labels 96 | v1 intervals removed 48
label_counts == Counter(v1 labels) True sum 96
curve_sampling present in v2 [None, None, None]
RESULT diff (expected-from-v1 vs v2): 0
top-level data_notice / evaluation_complete / kind / objective / request: 0 diffs
top-level provenance: 1 diff   $.provenance.engine_sha256
top-level reproduction: 5 diffs files[3] research_catalog.py、files[9] research_validation_job.py 的內容與雜湊；新增 referenced_files
```

- result 逐欄 0 差異。
- 其他差異只有三種，都是預期的：
  - `schema`。
  - `engine_sha256`：`ENGINE_FILES` 裡有兩個檔案改了。
  - 來源快照裡這兩個檔案的內容。
- `referenced_files` 是 `[]`；合成 CSV `examples/research-web-synthetic.csv` 仍內嵌。

補充兩項比對：

- **真實資料上的 v1 對 v2**：main 在程序內暫時把 `DATASET_ID` 換成 OKX 資料集，只為了解除 `validation_supports_synthetic_dataset_only` 檢查來量測。用量測設定跑：
  - result 差異為 0（v1 曲線換成 v2 的取樣點之後）。
  - 6 窗的 v2 曲線都是 v1 完整曲線（1,001 點）的子序列，含起點與終點。
  - `label_counts` 合計 8,640。
- **回測不受影響**：回測沿用的 `drawdown_pcts()` 是重構出來的。main 與分支的 `execute_request` 在合成預設和真實資料（period 20）上，payload 除 `engine_sha256` 外完全相同，報表長度也相同（14,209／267,114）。

## 2. 真實資料正確性：PASS

自寫 `replay_windows.py`：在分支 clone（`data/okx` 副本）上跑兩組設定。每一窗都用核心 `research.backtest` 重跑同一切片：`bars[test_start − warmup : test_end]`，加上窗內的資金費事件。另外用獨立寫法（每根重算、不用 deque）重算環境標籤，並用完整權益曲線重做分環境歸屬。

```text
== dev_measured: preflight work 54960 | bars replayed 54960 in 30 runs | equal True
label_counts == separate implementation: True
window 0: period 32 | return_pct -0.7939531 net_pnl -79.395318 fees 46.520304 funding 0.57701460 trades 118 fund_n 32 curve 145/1001 deepest@982 residual 0E-19 | ALL OK (18 checks)
window 1: period 32 | return_pct -0.7293630 ... trades 83  curve 145/1001 | ALL OK (18 checks)
window 2: period 32 | return_pct 0.04207582 ... trades 101 curve 145/1001 | ALL OK (18 checks)
window 3: period 32 | return_pct -0.5687712 ... trades 86  curve 144/1001 deepest@1000 | ALL OK (18 checks)
window 4: period 32 | return_pct -1.0420385 ... trades 119 curve 145/1001 | ALL OK (18 checks)
window 5: period 32 | return_pct -0.2930598 ... trades 75  curve 145/1001 | ALL OK (18 checks)
== p2_max_trades: preflight work 8720 | bars replayed 8720 in 24 runs | equal True
window 0..7: period 2 | 544～567 trades each | curve 121～122/1080 | ALL OK (18 checks)
```

每窗 18 項檢查：

- **與重跑一致**：視窗起訖時間，以及 `performance`、`trades`、`funding`、`pending_intent`、`config` 都等於重跑結果。
- **資金費對原始 CSV**：
  - rate 等於 `funding.csv` 的 `realized_rate`，mark 等於結算當下 K 線的開盤價。
  - 金額 = 部位 × 0.01 × mark × rate。
  - 合計等於 `funding_paid`。
- **取樣曲線**：
  - 是完整曲線的子序列，含起點、終點與最深回撤點。
  - `curve_sampling` 的 total／returned 正確，點數 ≤ 1,000 ÷ 視窗數。
  - 保留點上的最大回撤等於 `performance.max_drawdown_pct`。
- **分環境**：
  - 各環境的 K 線數、淨損益、手續費、資金費、成交數，都等於獨立重算的結果。
  - 各環境加總等於 total，total 等於 performance。
  - `reconciled` 為 true，且沒有 `intervals`。

量測設定的 OOS 報酬依序為 -0.79%、-0.73%、+0.04%、-0.57%、-1.04%、-0.29%，與方案文件一致。

## 3. 計算量預檢、逾時與輸出上限：PASS（附觀察 O1、O2）

- **公式與實際重播根數一致**：把 `research_validation.backtest` 包一層計數後實跑，54,960 = 54,960，8,720 = 8,720。
- **超過上限在送出時就拒絕，且在載入策略之前**：
  - `execute_validation` 先呼叫 `validate_validation_request`（計算量檢查在載入資料之前），再呼叫 `load_registered_strategy`。開發者測試 `test_bar_evaluation_budget_is_checked_before_strategy_load` 也涵蓋這一點。
  - HTTP 實測 253,552 → 422 `walk-forward exceeds max_bar_evaluations before execution`，run 清單維持 8 筆，沒有建立任務。
- **研究服務實測**（自寫 `service_cases.py`）：在 18870 起 `tests.integration_http_fixture`，用全新輸出根，經 HTTP 送出並輪詢；收尾後埠已釋放。

| 案例 | 計算量 | 任務耗時（started → finished） | result.json | report.html | 結果 |
| --- | --- | --- | --- | --- | --- |
| 合成預設 | 312 | 1.03 秒 | 185,132 | 6,523 | complete |
| 量測設定（開發者） | 54,960 | 2.61 秒 | 595,149 | 9,972 | 6/6 COMPLETE |
| 計算量邊緣（開發者） | 242,272 | 6.32 秒 | 552,601 | 12,371 | 8/8 |
| 成交最多（開發者） | 17,248 | 1.94 秒 | 984,335 | 13,024 | 2,591 筆 OOS 成交 |
| **最慢**：SMA 2~12（11 候選）、train 2800、test 200、8 窗、lookback 4320 | 249,152 | **15.24 秒** | 576,679 | 9,462 | 8/8 |
| 同上，輸入改用最長合法小數 | 249,152 | 14.69 秒 | 632,430 | 10,517 | 8/8 |
| **最大輸出**：SMA 2~14（13 候選）、train 1、test 1232、7 窗、最長合法小數、1000 張 | 10,087 | 2.03 秒 | **1,420,576** | 13,218 | 4,413 筆 OOS 成交 |
| 每窗都選 period 2：SMA 2~3、train 1、test 1079、8 窗、最長合法小數 | 8,720 | 1.78 秒 | 1,387,348 | 14,366 | 4,416 筆 OOS 成交 |
| 超過上限：SMA 2~12、train 2850、test 200、8 窗 | 253,552 | — | — | — | 422，沒有建立任務 |

「最長合法小數」指 fee_rate `0.000512345678901234`、slippage `2.345678901234567891`、本金 `999999999.123456789012345678`。這已到輸入精度上限：28 位有效數字、18 位小數。

- 在我的量測下，最慢的合法請求是 15.24 秒，約為 30 秒逾時的一半。
- 最大的 Worker 輸出（payload＋報表，程序內量）是 1,430,178 bytes，約為 2,000,000 上限的 71.5%。
- 兩者都在限內，但都比文件寫的最壞情況重，見 O1、O2。
- 程序內補充量測：
  - 分類器單獨耗時：lookback 16／1000／2160／4320 分別為 0.16／3.47／6.30／8.34 秒。
  - 長訓練窗（2 候選、train 8,000、8 窗）約每秒 3.4～3.6 萬根。

## 4. 來源快照與報表頁尾：PASS

**真實資料的 `referenced_files`**（研究服務結果）：

- 共 4 個檔案的 path＋sha256：`manifest.json`、`candles.csv`、`funding.csv`、`instrument.json`。
- 三個資料檔的雜湊等於 manifest 的 `files`；`manifest.json` 的雜湊等於實際檔案。整體等於 `provenance.dataset.files`。
- `files` 裡沒有任何 `data/` 路徑，內嵌的 14 個都是程式與 manifest 檔。
- notice 加註「只記路徑與 sha256、不內嵌內容；重現時以同一份 manifest 核對，或依 README 以 --end-ms 重抓同一區間」。

**合成資料**：`referenced_files` 是 `[]`，CSV 仍內嵌，notice 與 v1 相同。

**竄改測試**（自寫 `tamper_check.py`）：在暫存 clone 的資料副本上做，main 與分支的結果逐行相同。

```text
pristine _reproduction: accepted (embedded 14, referenced 4)        [main: embedded 18, referenced 0]
candles changed, manifest NOT updated: ValueError: unknown_dataset
candles changed + manifest rehashed: ValueError: source_changed_during_archive
funding changed after resolve (race): ValueError: source_changed_during_archive
candles changed after resolve (race): ValueError: source_changed_during_archive
funding changed + manifest rehashed: _reproduction accepted；provenance 與送出時不同
  → execute_validation 整體拒絕：ValueError source_changed_restart_required
restored: True
```

- `source_changed_during_archive` 對資料檔的涵蓋範圍與 v1 相同：
  - 資料檔現在列在 `referenced_files`，但仍計入同一組雜湊比對。
  - 只有 candles 的雜湊和送出時的 provenance 比對；其他資料檔比對的是當下的 manifest。
  - 同時改寫 funding 與 manifest 的情況，兩版都由後續的 provenance 比對攔下。這是既有行為，不是本範圍的退化。

**報表頁尾**：

- OKX 報表的標題是「固定研究來源 · OKX 公開歷史資料」，全文沒有「合成」二字。
- 合成資料的報表是「固定研究來源 · 合成資料」。
- 報表本體是 3 個摘要表，不再內嵌 JSON；`<pre>` 只出現在頁尾的綁定區。

## 5. 前端：PASS（附觀察 O4）

### 程式核對

- **Decimal 紀律**：
  - `toPlotNumber` 只用在權益曲線座標與本金虛線；Y 軸刻度用 `toFixed(0)`；tooltip 以原始字串經 `formatDecimal` 顯示。
  - 最佳／最差用 `compareDecimal`，正負用 `signOf`。表格 `title` 保留完整的 Decimal 字串。
  - 新增檔案裡沒有任何金額經過 `parseFloat` 或 `Number`；`parseInt` 只用在整數表單欄位。
- **呈現邊界**：
  - 圖只畫選定的一窗，各窗權益曲線不串接。
  - 沒有通過門檻或部署判定的文字。
- **hook 重構**：
  - 舊的 `use-optimization-research.ts` 與新的 `use-research-runs.ts` 逐行 diff，差異只有 kind／label／send 參數化與變數改名。
  - `researchApi` 是物件字面量，方法裡沒有用到 `this`，所以傳入未綁定的 `submitOptimization` 是安全的。
- **測試範例**：`tests/validation_plan_test.mjs` 手寫的 catalog 範例，與後端 `DEFAULT_VALIDATION` 程序內比對結果相等。

### 瀏覽器實測

環境是隔離的 18870 fixture，加上 18890 的 Vite 代理。內建瀏覽器視窗沒有繪製，所以改用頁面內 JavaScript 觸發 click 與 input 事件，見「未涵蓋」。

| 步驟 | 結果 |
| --- | --- |
| 側欄 | 「滾動驗證 WALK-FORWARD」連到 `#/validation` |
| 開啟對話框（合成，預設選取） | 2~4／1、24／16／3 窗、lookback 4／0.5／250；使用 76／96 根、需 12 次回測、計算量 312／250,000；送出可按 |
| 選 OKX | 8~32／8、2152／1076／6 窗；使用 8,640／8,640 根、需 30 次回測、計算量 59,064；顯示資料集 notice |
| 超限提示 | 見下方清單 |
| 送出 OKX 預設 | 約 3.9 秒出結果：6/6 COMPLETE、32×6、0/6 窗為正、最佳 -4.76%、最差 -16.53%、30/30 次回測、未使用 0 根。各窗表的 OOS 報酬、淨損益、回撤、手續費、資金費、成交數，都等於 API 值四捨五入到兩位；`title` 與 API 字串完全相同 |
| 點選 #3 | 該列反白；明細標題為 10/01 13:00 → 10/12 18:00 UTC，標示「圖表取樣 156 / 1,077 點」。訓練格點 4 列（32 選定，鄰域最差 -22.97%）；分環境 7 類＋合計（1,076 根、98 筆、-107.12），與 API total 相同，顯示「與樣本外帳務核對一致」 |
| 注入 OOS_FAILED／NO_SELECTION（攔截 result JSON） | HUD 顯示「4 / 6 COMPLETE」「部分視窗無樣本外結果」「0 / 4 窗為正」，最佳／最差只取有結果的 4 窗。這兩列的數字欄全是「不適用」；明細顯示「此視窗沒有樣本外結果（OOS_FAILED）：RuntimeError: injected。不以 0 計入。」與「（NO_SELECTION）：訓練格點沒有可選的穩定區。不以 0 計入。」 |
| 優化頁 | 任務清單不含驗證任務。OKX、8~32、7 試驗、seed 42 → Trial #1、週期 31、-81.97%，與上一份驗收（`fe0912c`）相同 |
| 共用忙碌槽 | 經 API 送出一筆約 14 秒的驗證，在優化頁按刷新後顯示「後端忙碌中」，按鈕停用並顯示「後端計算中...」；任務完成後自動解除，按鈕恢復 |
| 回到驗證頁 | 兩筆驗證任務依時間排序，預設選最新一筆：8/8 COMPLETE、1/8 窗為正、未使用 4,228 根、取樣 101 / 201 點 |
| 全頁 | 沒有 NaN 或 undefined |

超限提示的實測（每種都列出原因，有問題時送出鍵停用）：

- 計算量 251,072：列出「計算量 251,072 超過上限 250,000（避免超過 30 秒逾時）」並停用送出；改成 242,272 後提示消失，可以送出。
- test 2000：「需要 14,184 根 K 線，資料集只有 8,640 根」。
- SMA 2~32、步進 1：候選 31 超過 20、需要 192 次回測超過 100、計算量 412,872 超限，三條同時列出。
- 步進 5：候選週期沒有對齊。
- 9 窗：視窗數需在 1~8。
- 訓練根數清空：訓練與測試根數需為正整數。
- 按「依資料長度重設」會恢復預設值。

## 6. 後端完整套件：PASS

- 在沒有 `data/okx` 的乾淨 clone（`280dff4`）執行：`Ran 1393 tests in 241.863s`、`OK (skipped=11)`，exit 0。
- 這台機器可以建立 symlink，所以只 skip 11 個，符合 README 的「11 或 12」。

## 7. 文件與實測一致：PASS（附觀察 O3）

- **README**：
  - 「回測、優化與滾動驗證都可選資料集」「v2 在 8,640 根上約 0.6 MB」都與實測相符：595,149～599,573 bytes。
  - 計算量公式與 250,000 上限和程式一致。
  - 後端 1393 tests、整合測試含驗證頁，都與本輪結果相符。
- **`docs/research-real-data-plan.md`**：下列數字與本輪實測一致：
  - 量測設定與前端預設的 OOS 報酬，以及「6 窗都選 32」。
  - 3 份報表的 bytes（9,972／12,371／13,024）。
  - v2 結果 449,460 bytes、v1 報表 8,168,455 bytes。
  - 成交 2,591 筆。
  - 「未涵蓋」已誠實列出更長資料集的輸出風險。
- **`docs/research-validation-api.md`「v2 輸出」**：表內各項做法都與程式及實測相同：
  - 取樣規則：每窗超過 1,000 ÷ 視窗數才取樣，保留起點與終點。
  - 只引用、不內嵌的檔案範圍。
  - 報表改為摘要表。
- **`docs/backend-frontend-integration-map.md`**：`lookback_bars` 改寫為 1～19,999，等於程式的 `MAX_BARS - 1`；React 串接狀態也與實際相符。
- **`docs/next-steps.md`（`280dff4` 收尾表格）**：

| 項目 | 文件狀態 | 核對結果 |
| --- | --- | --- |
| 7 個已合併的本機分支 | 已刪除 | `git show-ref` 全部不存在 |
| `feature/catos-react-vite` 本機與遠端 | 已刪除 | 本機分支與 `origin/feature/catos-react-vite` 追蹤分支都不存在 |
| 遠端 `feature/catos-v1-sim` | 已刪除 | 追蹤分支不存在 |
| 遠端 `feature/frontend-redesign-v2`、`archive/catos-v1` | 保留 | 兩個追蹤分支都在 |
| `docs/review-20261102/` | 已刪除 | 不存在 |
| `.git/worktrees/main-wt`、`main-wt2` | 已刪除 | `.git/worktrees` 為空，`git worktree list` 只剩主工作目錄 |
| `.claude/launch.json` | 改用 `.git/info/exclude` | `git check-ignore -v` → `.git/info/exclude:9:/.claude/launch.json`；`.gitignore` 沒有相關列 |
| 筆電的 CRLF 檔 | 未處理 | 工作樹仍有 453 個 `w/crlf` |

遠端狀態以本機追蹤分支（最後 fetch 為 14:01）為準，沒有連 GitHub 核對。

## 實際執行的命令與結果

代號：
- `<branch>`、`<main>`、`<suite>`、`<tamper-*>` 指 scratchpad 下的乾淨 clone。
- `<fe>` 指 `<branch>/frontend/cat-os-vite`。
- `<py>` 指 `C:/Users/kai/Desktop/CatOS/.venv/Scripts/python.exe`。

| 命令 | 位置 | 結果 |
| --- | --- | --- |
| `git clone -q -c core.autocrlf=false --no-hardlinks C:/Users/kai/Desktop/CatOS <dir>`，再 `git checkout --detach 280dff4`／`3f5ee9b` | scratchpad | 5 份 clone；563 個 LF |
| `<py> -B -m unittest discover -s tests -p "test_*.py"` | `<suite>` | `Ran 1393 tests in 241.863s`、`OK (skipped=11)`，exit 0 |
| `npm ci --no-audit --no-fund` | `<fe>` | exit 0（npm 11 提示 esbuild 的 postinstall 不在 allowScripts 內，不影響 build） |
| `npm run typecheck` | `<fe>` | exit 0 |
| `npm test` | `<fe>` | `check:tokens OK`；tests 15、pass 15、fail 0 |
| `npm run build` | `<fe>` | exit 0，`✓ built in 11.33s`（既有的 chunk > 500 kB 警告） |
| `node tests/simulation_integration_test.mjs <py>` | `<fe>` | exit 0，10 PASS（含 `validation page shows a real walk-forward run submitted through the proxy`）；證據在 `%TEMP%\catos-sim-integration-RUDGd9`；結束後 18870／18890 沒有監聽 |
| `run_default_validation.py`、`compare_v1_v2.py` | `<main>`、`<branch>` | 見第 1 項 |
| `real_v1_dump.py dev_measured` 與真實資料逐欄比對 | `<main>`、`<branch>` | v1 輸出 14,081,440 bytes（報表 8,168,455），v2 輸出 601,561 bytes；result 差異為 0 |
| `backtest_dump.py` | `<main>`、`<branch>` | 回測 payload 相同 |
| `replay_windows.py dev_measured p2_max_trades` | `<branch>` | 14 窗 × 18 項全部 OK |
| `measure_cases.py`（13 個案例） | `<branch>` | 程序內最慢 13.34 秒，最大輸出 1,430,178 bytes；253,552 被拒絕 |
| `classify_regimes` 計時 | `<branch>` | lookback 16／1000／2160／4320：0.16／3.47／6.30／8.34 秒 |
| `service_cases.py`（9 個案例） | `<branch>`，18870 | 見第 3 項的表；fixture 結束、埠已釋放 |
| `tamper_check.py` | `<tamper-branch>`、`<tamper-main>` | 見第 4 項 |
| `accept-serve.mjs`（fixture 18870＋Vite 18890），配合內建瀏覽器 | `<fe>` | 見第 5 項；結束後兩埠都可綁定 |

## 非阻斷觀察

- **O1（分類器成本不在計算量公式內）**：
  - `research_regimes._labels` 每根都對回看窗做三次加總，成本約為 (N − L) × L，L ≈ N/2 時最大。
  - 在 8,640 根上，lookback 4320 光是分類就要 8.34 秒（程序內），而 250,000 的公式只算回測根數。`lookback_bars` 允許到 19,999。
  - 所以本機最慢的合法請求是 15.24 秒。仍在 30 秒內，但 README 與方案文件說的「250,000 約 13 秒、保留約兩倍餘裕」沒有算到這一段。
  - 若換成 20,000 根的資料集（`MAX_BARS`），推估 lookback 10,000 時分類器單獨就約 45 秒，任務會以 `research_timeout` 失敗。這是 fail-closed，不會寫出錯誤結果；目前的授權範圍（90 天 15m）也碰不到。
  - 建議：把類似 `len(bars) × min(lookback, len(bars))` 的項目納入預檢，或替 lookback 設上限，並在文件補一句。
- **O2（「成交最多」不是最壞情況）**：
  - 文件的「成交最多」案例是 2,591 筆、988,759 bytes。
  - 讓每窗都選 period 2 可以到 4,416 筆。做法例如 SMA 2~3，或 train 1 讓所有分數平手，因而選到第一個候選。
  - 再加上最長合法小數與 13 個候選，result.json 是 1,420,576 bytes、Worker 輸出 1,430,178 bytes。
  - 仍在 2,000,000 內，「最壞情況量過仍在上限內」的結論成立；但實際餘裕只有約 0.57 MB，比文件呈現的小。建議更新方案文件的這一列。
- **O3（文件數字的小落差）**：
  - **byte 數**：文件的數字是在有 CRLF 檔的筆電工作樹上量的。來源快照會內嵌檔案內容，每個 `\r` 在 JSON 裡多 2 bytes。乾淨 clone 的 v2 結果一律少 4,424 bytes（例如 599,573 → 595,149），v1 少 3,906 bytes；報表大小完全相同。
  - **耗時**：本輪比文件快（2.61／6.32／1.94 秒，文件是 4.35／7.72／2.91 秒）。方案文件寫「每秒約 1.9～2.7 萬根」，本輪程序內是每秒 3.4～4.5 萬根，同一台筆電，可能是量測時的負載不同。
  - **v1 大小**：驗證 API 文件寫 v1「13.7 MB、各窗權益曲線 1.8 MB」；同一設定實測是 14,081,440 bytes、曲線 1,577,262 bytes。標籤 1,807,107 bytes、逐根歸屬 1,746,102 bytes 都與文件相符。這可能是前一個工作包的舊量測，數字都遠超上限，不影響結論。
- **O4（前端有少數欄位只靠後端檢查）**：
  - 對話框不預檢 `trend_efficiency`、`high_volatility_bps` 的格式，也不檢查 lookback 的上限；這些由後端以 422 拒絕，前端用既有的錯誤列顯示。本輪沒有在瀏覽器觸發這條路徑。
  - 步進沒對齊時，摘要行會顯示「需 不適用 次回測」，用語略生硬。

## 未涵蓋

- **瀏覽器互動方式**：內建瀏覽器視窗沒有繪製（Claude 視窗被隱藏），滑鼠點擊無法送出，改用頁面內 JavaScript 觸發 click 與 input 事件並讀 DOM 核對。沒有檢查版面、圖形與動畫，視覺由使用者自行在網頁驗收。
- **其他機器**：沒有在另一台機器量計算量與耗時，與文件「未涵蓋」相同。
- **超限失敗路徑**：沒有實際觸發 30 秒逾時與 2 MB 輸出超限，因為找不到會超限的合法請求；這兩段處理程式不在本範圍的改動內。
- **外部連結**：沒有核對方案文件引用的外部工具文件內容。
- **遠端分支**：`280dff4` 的遠端分支狀態以本機追蹤分支為準，沒有連 GitHub。
- **後端套件的資料條件**：只在沒有 `data/okx` 的乾淨 clone 跑過（開發者是在有 `data/okx` 的工作目錄跑的）。真實資料路徑另由第 2～4 項的程序內與服務實測涵蓋。
