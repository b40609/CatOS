# 工作包 F 第三輪觀察 P1～P5 處理（b1e637fd）獨立驗收

- 驗收對象：commit `b1e637fd`（父 commit `c2f0cba9`），分支 `claude/acceptance-pfix-411cf8`，worktree `acceptance-shortterm-a51238`。
- 驗收者：未參與 P1～P5 開發的 Claude 會話（2026-11-09）。
- 範圍：上一輪報告 `reports/research-shortterm-nfix-acceptance-20261108/acceptance.md` 的 P1～P5；宣稱的處理見 `docs/research-real-data-plan.md:780-787`。
- 限制：沒有連網、沒有呼叫 OKX；`C:/Users/user/Desktop/CatOS/data/okx/` 只讀（前後 sha256 相同）；沒有碰金鑰；沒有啟動或停止 8770／8771；沒有改產品 DB；沒有 commit、push、merge。

## 總判定：PASS（5／5），無阻斷缺陷

| 項目 | 判定 |
| --- | --- |
| P2 變異數無法估計時回 None，HTML 與前端顯示「不適用」 | PASS |
| P3 滾動驗證抽樣直接用 `limit` | PASS（附觀察 Q2） |
| P4 limit < 3 丟 ValueError、方法名稱與說明文字 | PASS（附觀察 Q1） |
| P1 不改的理由 | PASS（理由成立） |
| P5 next-steps 狀態 | PASS |
| 收錄的第三輪報告逐位元組相同 | PASS |
| 測試（後端全套、前端 typecheck／npm test） | PASS |

本輪新觀察 Q1、Q2 都不阻斷，不影響任何數字或研究結論。

## P2 `catos/research_overfit.py` 的 `search_report`：PASS

程式證據：
- `catos/research_overfit.py:231`：`variance_known = len(alive) >= 2 or trials < 2`。
- `catos/research_overfit.py:250-252`：`trial_sharpe_variance`、`expected_max_sharpe_per_bar`、`expected_max_sharpe_annualized` 在 `variance_known` 為 False 時都是 None。
- `catos/research_optimization.py:22-23`：`overfit_rows` 在 None 時顯示「不適用」。HTML 報告的過擬合表格只列年化的那一欄，沒有列變異數和每根 K 線的值（`catos/research_optimization.py:15-28`）。
- `frontend/cat-os-vite/src/adapters/research-api-adapter.ts:265-268`：三個欄位的型別是 `string | null`。
- `frontend/cat-os-vite/src/components/catos/overfitting-panel.tsx:54`：`?? "不適用"`。前端只渲染年化的那一欄，另外兩欄沒有地方使用。

### 後端新舊比對

方法：`$S/p2_check.py` 用測試裡的 `Flip`、`candles`、`config` 合成 4 組試驗，必要時把權益扣到 0 以下模擬爆倉。同一組輸入分別交給 HEAD 的 `search_report`，以及 `git show c2f0cba9:catos/research_overfit.py` 存下的舊版，比對整個 dict。

| 情境 | N／爆倉 | 新舊差異鍵 | 新版三欄 | 舊版三欄 | `overfit_rows` 顯示 |
| --- | --- | --- | --- | --- | --- |
| A 4 組都沒爆倉 | 4／0 | 無 | 0.01852113／0.143186／26.803 | 相同 | 26.803 |
| B 3 組沒爆倉、1 組爆倉 | 4／1 | 無 | 0.00259835／0.053631／10.039 | 相同 | 10.039 |
| C 最佳組爆倉、3 組沒爆倉 | 4／1 | 無 | 0.02132782／0.153653／28.762 | 相同 | 28.762 |
| D 只剩 1 組沒爆倉 | 4／3 | 只有這三欄 | None／None／None | 0.00000000／0.000000／0.000 | 不適用 |
| E 2 組裡 1 組爆倉 | 2／1 | 只有這三欄 | None／None／None | 0.00000000／0.000000／0.000 | 不適用 |
| F 4 組全爆倉 | 4／4 | 只有這三欄 | None／None／None | 0.00000000／0.000000／0.000 | 不適用 |
| G 只跑一組 | 1／0 | 無 | 0.00000000／0.000000／0.000 | 相同 | 0.000 |
| H 只跑一組且爆倉 | 1／1 | 無 | 0.00000000／0.000000／0.000 | 相同 | 0.000 |

- D、E、F 的 HTML 表格含 `<th>N 組純運氣可期待的最大 Sharpe（年化）</th><td>不適用</td>`，DSR 新舊都是 None。
- 只跑一組（G、H）、沒爆倉（A）、爆倉但仍有 2 組以上存活（B、C）時，新舊輸出整個 dict 相同。
- 輸出：`FAILURES: none`。

### 前端實際渲染（SSR）

方法：`$S/ssr/run.mjs` 用 worktree 內 `node_modules` 的 esbuild，把 `overfitting-panel.tsx` 和 `react-dom/server` 打包成 CJS。路徑別名 `@` 指向 `src`，tsconfig 用 worktree 的設定。接著把上表 8 種情境的後端 JSON（`$S/reports.json`，由新版 `search_report` 產生）餵給 `renderToStaticMarkup`，從 HTML 抓「純運氣可期待的最大 Sharpe（年化）」那一列的值。

為了對照，渲染時把 `c2f0cba9` 版的元件暫存為 `src/components/catos/__old_overfitting_panel_acc.tsx`，跑完立即刪除；之後 `git status --short` 是乾淨的。

這是靜態伺服器端渲染，不是瀏覽器互動；面板本身沒有互動元件。

```
PASS A: json="26.803" new_row="26.803" old_row="26.803"
PASS B: json="10.039" new_row="10.039" old_row="10.039"
PASS C: json="28.762" new_row="28.762" old_row="28.762"
PASS D: json=null new_row="不適用" old_row=""
PASS E: json=null new_row="不適用" old_row=""
PASS F: json=null new_row="不適用" old_row=""
PASS G: json="0.000" new_row="0.000" old_row="0.000"
PASS H: json="0.000" new_row="0.000" old_row="0.000"
FAILURES: 0
```

- 新版在 null 時顯示「不適用」。舊元件遇到同一份 JSON 會渲染成空白，證明這個檢查能抓到原本的問題。
- 去掉 `data-*` 屬性後，整段 HTML 不含 `null`、`undefined` 字樣。
- D 情境的實際片段：`純運氣可期待的最大 Sharpe（年化）</span><span class="font-mono text-foreground">不適用`。

## P3 `catos/research_validation_job.py` 的 `_sampled_curve`：PASS

程式證據：`catos/research_validation_job.py:142-147` 直接呼叫 `sample_curve_indices(drawdown_pcts(...), limit)`，不再先傳 `limit - 1` 再補 0；`method` 改為 `bucket_deepest_drawdown_keep_first_last`（`:164`）。

方法：`$S/p34_check.py` 用 `test_research_datasets.write_fixture` 在暫存目錄建立合成的抓取資料集。同一個請求分別交給 HEAD 的 `execute_validation`，以及 `c2f0cba9` 版的 `research_validation_job.py`（整個舊模組，含舊 `_sampled_curve` 和舊方法名稱，搭配同一個 catalog），比對兩邊的 payload 和 HTML 報告。兩版的 `sample_curve_indices` 只差在 limit 檢查，抽樣邏輯相同。

| 設定 | 每窗 limit | 拿掉 OOS 權益曲線與 `curve_sampling` 後 payload 相同 | 報告相同 | 每窗點數（新／舊） |
| --- | --- | --- | --- | --- |
| 4,000 根、test 900、3 窗 | 333 | True | True | 301／301、302／302、302／302 |
| 6,000 根、test 400、8 窗 | 125 | True | True | 101～102，新舊相同 |
| 3,000 根、test 245、8 窗 | 125 | True | True | 新 123～124、舊 82～84 |

- 每一窗的 `performance`、`trades`、`funding` 新舊都相同。
- 第一點與最後一點新舊相同。
- 新版點數不超過 limit，`total_points` 等於 test_bars + 1。
- 差異只有抽樣點數和 `method` 名稱（舊版為 `bucket_deepest_drawdown_keep_first`）。HTML 報告逐字相同，因為驗證報告不寫取樣說明。
- 19 個窗全部 PASS，`FAILURES: none`。

另外，repo 內的測試 `tests/test_research_datasets.py:256-262` 也斷言新方法名稱、每窗不超過 `MAX_VALIDATION_CURVE_POINTS // windows`，以及頭尾點等於完整曲線的頭尾點。

## P4 `catos/research_catalog.py` 的 `sample_curve_indices`：PASS

limit 檢查：
- `catos/research_catalog.py:632-633`：limit < 3 時丟 `ValueError("curve sampling limit must be at least 3 (first, last and one bucket)")`。
- 實測 limit 為 -1、0、1、2 時都丟這個錯誤。
- limit 為 3 時：10 點回 `[0, 3, 9]`，3 點回 `[0, 1, 2]`。

所有呼叫端的 limit：
- `catos/research_catalog.py:672`：payload 用預設值 `MAX_CURVE_POINTS = 2_000`（`:153`）。
- `catos/research_validation_job.py:156`：`MAX_VALIDATION_CURVE_POINTS // len(windows)`。
  - 窗數由 `validate_validation_request` 限制在 1～`MAX_VALIDATION_WINDOWS = 8`（`catos/research_validation_job.py:76`、`catos/research_catalog.py:168`）。
  - 實測 windows=9 時丟 `windows: integer in [1, 8] required`。
  - 各窗數對應的 limit：`{1: 1000, 2: 500, 3: 333, 4: 250, 5: 200, 6: 166, 7: 142, 8: 125}`，最小 125，都 ≥ 3。
- 全 repo 只有這兩個呼叫端：`grep sample_curve_indices` 除了這兩處，只出現在定義與測試。

性質測試：3,000 組隨機曲線，limit 從 {1000, 500, 333, 250, 200, 166, 142, 125, 3, 4, 5, 2000} 中抽。檢查點數不超過 limit、遞增且不重複、保留頭尾點、保留回撤最深點，以及總點數不超過 limit 時原樣回傳。結果 0 違反。

舊方法名稱的依賴：
- `grep -rn "curve_sampling|keep_first|bucket_deepest"` 在前端 `src` 只找到型別 `method: string`（`research-api-adapter.ts:353`、`:449`）。
- 畫面只顯示 `returned_points`／`total_points`（`backtest-underwater-chart.tsx:140`、`pages/validation.tsx:178`），沒有讀 `method`。
- Python 端除了寫入點，只有測試用到這個名稱，而且已經改成新名稱。
- 沒有程式依賴舊名稱。唯一的舊名稱殘留在文件，見觀察 Q1。

說明文字：
- `catos/reporting.py:242` 的「保留第一點、最後一點，以及每個區間回撤最深的一點」和 `sample_curve_indices` 的行為一致（`:637-645`：每桶取最深點，必要時補上 0 和最後一點）。
- 在真實 5m 資料上，HTML 報告確實出現這段新文字（見 P1 實測）。

## P1 不改的理由：PASS（理由成立）

- `docs/research-real-data-plan.md:728` 寫明位元組數是「`51500b88` 獨驗重現的數字」，措辭本身正確。
- 本 commit 又改了 payload 的 `method` 名稱和報告說明文字，輸出再次變動，正好印證「之後的抽樣與欄位名稱變動都會讓輸出差幾百 bytes」。
- HEAD 實測（`$S/p1_bytes.py`，真實 5m 資料唯讀，provenance 路徑比照一般 checkout）：

```
12/3: fills 5801 stdout 1,798,492 B cap 2,000,000 -> ok; sampling {'total_points': 51841, 'returned_points': 1996, 'method': 'bucket_deepest_drawdown_keep_first_last'}; fills/day(180) 32.23; report note new wording True
8/2: fills 7757 stdout 2,193,704 B cap 2,000,000 -> over; sampling {...同上...}; fills/day(180) 43.09; report note new wording True
data unchanged: True
```

- 和 `c2f0cba9` 的 1,798,443／2,193,655 相比，各多 49 bytes。12／3 仍在 2,000,000 上限內，8／2 仍超過。
- 成交筆數 5,801／7,757 不變，每天約 32.23～43.09 筆，符合「上限落點每天約 32～43 筆不變」。

## P5 `docs/next-steps.md:93`：PASS

- 新增的文字是：「N1～N6 在 `c2f0cba9` 修正，第三輪獨立驗收 PASS 6／6，報告在 `reports/research-shortterm-nfix-acceptance-20261108/acceptance.md`；第三輪的 5 項觀察 P1～P5 的處理見 … 只有開發者自測」。
- 這些內容在 commit 當下都是事實：報告已收錄在同一個 commit，P1～P5 當時確實只有自測。沒有預寫本輪的驗收結果。
- 本輪 PASS 之後，「只有開發者自測」會再次過時。這是逐輪更新的固有落差，不算缺陷。

## 收錄的第三輪報告：PASS

```
6a82b80be6e348a0eff86ed20465a1c3e018c8f7b42d73a1dc98a1807f44b619  git show b1e637fd:reports/.../acceptance.md
6a82b80be6e348a0eff86ed20465a1c3e018c8f7b42d73a1dc98a1807f44b619  .claude/worktrees/acceptance-nfix-912eb4/reports/.../acceptance.md
cmp → IDENTICAL；兩邊都是 18,862 bytes；原檔 CR 數 0
git ls-files -s → 100644 3b72f0fd…，attr text=auto eol=lf
```

sha256 開頭與開發端宣稱的 `6a82b80be6e348a0` 相同。

## 其他核對

- `git diff --check c2f0cba9 b1e637fd -- . ':!reports'`：exit 0，沒有空白錯誤。
- 本 commit 改動的 12 個檔，`git ls-files --eol` 全部是 `i/lf w/lf`。

## 測試

| 命令 | 結果 |
| --- | --- |
| `$PY -B -m unittest discover -s tests`（乾淨 worktree） | `Ran 1478 tests in 221.872s`、`OK (skipped=11)`、exit 0 |
| `npm run typecheck`（`frontend/cat-os-vite`） | exit 0 |
| `npm test` | `check:tokens OK`；`tests 21`、`pass 21`、`fail 0`；exit 0 |

後端全套跑完後的輸出含一行 `Port 52947 already in use. No process stopped and no alternate port selected.`，來自既有的埠衝突測試路徑，不影響結果。測試留下的 `outputs/workspace-w*-fixture-test-*` 都被 git 忽略。

## 本輪觀察（非阻斷）

**Q1（文件殘留舊名稱）　`docs/research-validation-api.md:77` 仍寫 method 是 `bucket_deepest_drawdown_keep_first`。**
- 程式實際輸出的是 `bucket_deepest_drawdown_keep_first_last`（`catos/research_validation_job.py:164`）。
- 沒有程式依賴這個字串。建議下次動文件時一併改成新名稱。
- `docs/research-real-data-plan.md:121` 的「另保留起點」沒有提到終點，但沒有寫錯。

**Q2（更正上一輪報告的估計）　P3 修正前，每窗少畫的不只 1 點。**
- 上一輪 P3 寫「每窗最多少畫 1 點」。實際上舊版用 `limit - 1` 時，桶大小是用 limit − 3 算的，遇到邊界會整個跳一級。
- 例如每窗 246 點、limit 125：新版桶大小 2，得到 123～124 點；舊版桶大小 3，只有 82～84 點（`$S/p34_out.txt` 第三組）。
- 修正後只會多畫點、不超過 limit，對 P3 的判定沒有影響，只是更正影響幅度的描述。

## 未核對與限制

- **瀏覽器互動**：前端用 SSR 靜態渲染核對，沒有在瀏覽器開啟優化頁。面板沒有互動元件，渲染結果足以判定顯示文字；不能代表整頁版面。
- **真實資料上的 P2 情境**：真實資料沒有「只剩 1 組沒爆倉」的搜尋。上一輪曾用真實 1H F2＋F3 組合重現，本輪只用合成試驗比對新舊版。改動只是遮蔽輸出欄位，不影響 DSR、PSR、PBO 的算式。
- **真實資料上的滾動驗證**：P3 只用合成的抓取資料集跑 `execute_validation`。真實 5m／15m 的滾動驗證沒有重跑，因為成本高；抽樣函式只依賴權益曲線，風險低。
- **worker 子程序與 HTTP 路徑**：P1 的位元組數用程序內 `json_text` 量，沒有另起 worker 子程序，也沒有經過研究服務 HTTP。本 commit 沒有改 `research_worker.py`。
- **開發者自測腳本**：看不到開發會話的 scratchpad，本輪全部用自己的腳本重驗。
- 驗收腳本與輸出放在本會話 scratchpad，不在 repo 內：`C:\Users\user\AppData\Local\Temp\claude\4677ee93a5daf182\fae062a9-e314-469d-9a22-a305120b0772\scratchpad\`。
  - 腳本：`p2_check.py`、`ssr/run.mjs`、`ssr/entry.tsx`、`p34_check.py`、`p1_bytes.py`。
  - 輸出：`p2_out.txt`、`ssr_out.txt`、`p34_out.txt`、`p1_out.txt`、`full_tests.txt`。
  - 舊版對照：`old/old_*.py`。

## 實際命令

| 命令 | 結果 |
| --- | --- |
| `git diff --stat c2f0cba9 b1e637fd`；`git diff c2f0cba9 b1e637fd -- . ':!reports'` | 12 個檔，+283／-17 |
| `git show c2f0cba9:catos/<模組>.py > $S/old/old_<模組>.py`（overfit、optimization、validation_job、catalog、reporting） | 舊版對照 |
| `PYTHONIOENCODING=utf-8 $PY -B $S/p2_check.py <worktree> $S/reports.json` | 8 種情境 PASS，`FAILURES: none` |
| `node $S/ssr/run.mjs <worktree> $S` | 8 種情境 PASS，`FAILURES: 0`；暫存的舊元件已刪除，`git status` 乾淨 |
| `PYTHONIOENCODING=utf-8 $PY -B $S/p34_check.py <worktree>` | limit 檢查、3,000 組性質測試 0 違反、19 窗新舊比對 PASS，`FAILURES: none` |
| `PYTHONIOENCODING=utf-8 $PY -B $S/p1_bytes.py <worktree>` | 1,798,492／2,193,704 bytes；資料檔未變 |
| `sha256sum`、`cmp`、`git ls-files -s`、`git check-attr -a` | 收錄報告相同，LF |
| `git diff --check`、`git ls-files --eol` | 無空白錯誤，全部 LF |
| `$PY -B -m unittest discover -s tests` | Ran 1478 tests，OK (skipped=11)，exit 0 |
| `npm run typecheck`、`npm test` | exit 0；21／21；check:tokens OK |

（`$PY` = `C:/Users/user/Desktop/CatOS/.venv/Scripts/python.exe`；`$S` = 本會話 scratchpad。）
