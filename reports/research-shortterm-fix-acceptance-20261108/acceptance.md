# 工作包 F 驗收後修正（b8eb1280）獨立驗收

- 對象：commit `b8eb1280`（父 `2f839a36`），分支 `claude/acceptance-ffix-5810b1` 的 HEAD 就是 `b8eb1280`，工作樹乾淨。
- 驗收者：獨立的 Claude 會話，沒有參與這批修正的開發。開發者自測（`Ran 1475 tests`、`OK (skipped=11)`）只當參考，下面的結果都是本會話實際執行的。
- 日期：2026-11-08。

## 結論

- **總判定：PASS。** 上一輪報告的 O1～O11 全部確實修正（11／11），沒有阻斷缺陷。O12 依約不處理，本輪也重現一次。
- 另有 6 項非阻斷觀察（N1～N6），都不影響研究結論：
  - N1：文件寫的 worker 輸出位元組數，在 HEAD 上重現時多了約 360 bytes。結論（5,801 筆可跑、7,757 筆超過上限）成立。
  - N2：`docs/next-steps.md:93` 在 commit 內寫「修正……尚未 commit、尚未獨立驗收」。這是第三次出現同型的狀態文字落後。
  - N3：「各週期組內選出的最佳變體（四個週期都是 F2）」沒有寫選法。依淨損益（搜尋目標）選才是 F2；依 Sharpe 選的話，5m 是 F3。
  - N4：`--resume` 的第一次執行如果在 K 線分頁時失敗（還沒有存過進度），已花的請求不會記進總數。計畫表寫「失敗的請求也計入總數」，沒有寫這個例外。
  - N5：爆倉的組計入 N，但只剩 1 組沒爆倉時，Sharpe 變異數是 0，「純運氣最大 Sharpe」變成 0，DSR 就等於 PSR，N 不起作用。真實資料沒有遇到。
  - N6：報告的權益圖抽樣後不一定包含第一個點，圖從第一個區間回撤最深的點開始。這是 payload 抽樣原本就有的行為。
- 依指示：只新增本報告，沒有改程式或文件，沒有 commit、push、merge。

## 驗收限制與隔離

- 沒有連網：O10 的檢查用 repo 測試裡的 `FakeOKX`（base_url `https://fake.invalid`），並把 `socket.socket` 換成一呼叫就丟錯的函式。沒有呼叫 OKX，也沒有碰金鑰或憑證。
- 真實資料：把主 checkout 的 `C:/Users/user/Desktop/CatOS/data/okx/`（5.7 MB）唯讀複製到本 worktree 的 `data/okx/`（被 `.gitignore:29` 的 `/data/` 忽略），然後用 `diff -r` 比對，完全相同。原始資料沒有改動。
- 沒有啟動或停止 127.0.0.1:8770／8771，也沒有碰產品 DB。worker 子程序用 `ResearchService._compute` 在本機起 `catos.research_worker`。這個 worker 不聽埠，暫存目錄在本會話的 scratchpad。
- 後端全套測試在 worktree 留下 `outputs/workspace-w6-fixture-test-*`、`outputs/workspace-w8-fixture-test-*`（git 忽略，是既有 fixture 測試的證據）。前端執行 `npm ci` 產生 `frontend/cat-os-vite/node_modules`（git 忽略）。
- 自寫腳本與完整輸出放在本會話的暫存目錄，不在 repo，會話結束後可能被清掉；關鍵輸出已抄進本報告：
  `C:\Users\user\AppData\Local\Temp\claude\690ae60c87e239ad\e4155f9b-057e-4043-a22a-e28648d9b90c\scratchpad\`
  - `o5_check.py`／`.log`、`o3_check.py`／`.log`、`o10_check.py`／`.log`、`misc_check.py`／`.log`、`fe_check.mjs`／`.log`、`fe_reports.json`
  - `tests_full.log`、`npm_ci.log`、`fe_typecheck.log`、`fe_tokens.log`、`fe_test_1.log`、`fe_test_2.log`

## 判定一覽

| # | 項目 | 判定 |
| --- | --- | --- |
| Y1 | O5 爆倉：不計比率統計、計入 N 但不計入變異數與 PBO、Decimal、文件數字重算 | PASS |
| Y2 | O3 輸出上限：圖表抽樣、成交明細上限、實測位元組 | PASS（附 N1、N6） |
| Y3 | O10 抓取工具：預算下限、原子寫入、資金費失敗保留 K 線、跨次節流 | PASS（附 N4） |
| Y4 | O1、O8、O9 的程式與前端 | PASS |
| Y5 | O2、O4、O6、O7、O11 的文件與註解 | PASS（附 N2、N3） |
| Y6 | 收錄的報告和原檔相同 | PASS |
| Y7 | 迴歸：後端全套、前端 typecheck／test／tokens | PASS（第一次 `npm test` 重現 O12） |

## Y1. O5 爆倉處理：PASS

**程式核對**

- `catos/research_overfit.py:43` `first_non_positive` 用 Decimal 比較 `point.equity <= 0`。
- `bar_returns` 遇到權益 ≤ 0 就丟 `equity_not_positive`（`:54`）。
- `search_report`：
  - `:214-215` 把試驗分成爆倉與沒爆倉兩組。
  - `:216` 只對沒爆倉的組算報酬。
  - Sharpe 平均與變異數只用沒爆倉的組，但 `:223` 的 `expected_max_sharpe(variance, trials)` 用的是全部的 N。
  - `:226` 最佳參數爆倉時，`dsr`、`psr` 是 None。
  - `:228` PBO 只用沒爆倉的組。
  - `:237` 回報 `wiped_out_trials`。
- `catos/research_robustness.py:64` `wiped_out()`。`daily_returns` 遇到爆倉就丟錯（`:115`），所以 bootstrap 也算不出來。
- `catos/research_catalog.py:641` `_wiped_out` 回傳 `time_ms`、`min_equity`（Decimal）與說明。`:673` 寫進 payload 的 `equity_wiped_out`。
- `catos/research_optimization.py:20`、`:24`：HTML 報告的最佳 Sharpe 顯示「爆倉，不計算」，並列出爆倉的組數；DSR 是 None 時，`costs_html` 顯示「—」（`research_catalog.py:593`）。
- 金額全程是 Decimal：`git diff 2f839a36 b8eb1280 -- catos/` 新增的行沒有任何 `float(`。`min_equity` 的型別實測是 `Decimal`。float 只出現在既有的報酬率統計（P7 允許）。

**真實資料重算**（`o5_check.py`）

我自己寫了一份參考實作：報酬用 `Fraction` 算，動差、DSR、CSCV PBO 都是自己寫的，然後拿來和 repo 的函式與文件數字比對。15 個變體依文件設定執行：10 張、taker 0.0005、滑價 2 bps、本金 10,000，預熱 5m 864、15m 288、1H 72、4H 18 根。

```
PASS only F3 1H wiped out | {('1H', 'F3')}
PASS F3 1H first <=0 at 2026-07-08 11:00 UTC | 2026-07-08T11:00:00+00:00
PASS F3 1H min equity -525.75 | -525.7534129392851326600
PASS F3 1H 1,314 points <= 0 | 1314
PASS daily_returns refuses wiped run | equity_not_positive
PASS bar_returns refuses wiped run | equity_not_positive
bootstrap range 0.5660 .. 1.0000
PASS bootstrap 0.566..1.000
DSR N=15 (group variance, alive only): {... '15m F2': 0.0304 ...}
  max 0.0304 at ('15m', 'F2'); pooled-variance max 0.0882 at ('4H', 'F2')
PASS ('1H', 'F3') wiped report: dsr/psr None, sharpe None, N=4 | dsr=None verdict=最佳參數權益跌破 0（爆倉），無法計算 DSR。…
PASS 1H PBO repo 0.7714 == mine 0.7714 (zero share 0.7286)
  5m: best-Sharpe F3 DSR 0.0646; per-variant 0.0007..0.0646; PBO 0.7714
  15m: best-Sharpe F2 DSR 0.1198; per-variant 0.0003..0.1198; PBO 0.5000
  1H: best-Sharpe F2 DSR 0.0758; per-variant 0.0002..0.0758; PBO 0.7714; N=4 alive=3
  4H: best-Sharpe F2 DSR 0.1346; per-variant 0.0033..0.1346; PBO 0.6286
PASS per-variant DSR range 0.0002..0.1346
F3 1H payload bytes 929,807; report bytes 113,311
FAILURES: none
```

- 14 個沒爆倉的變體：
  - 每日報酬與 repo 的 `daily_returns` 逐值相同。
  - 每根報酬與 `bar_returns` 的差都小於 1e-15。
  - 組內 DSR 13 個都和 repo 的 `search_report` 相同到 4 位。
  - 四組 PBO 與 λ=0 佔比和 repo 相同。
- 「DSR（N=15）≤ 0.0304」的算法是用同週期組內、沒爆倉的組的 Sharpe 變異數，N 取 15。這個算法和上一輪報告一致，最大值確實是 F2 15m。如果改用 14 個變體合併的變異數，最大值是 0.0882（4H F2）。跨週期的每根 Sharpe 不能直接比較，所以合併變異數不是合理的讀法，不算不一致。
- 1H 組 73% 的切法落在中位數：實測 0.7286。
- 「1H 組最佳 DSR 0.0255 → 0.0758」：F3 移出變異數之後，1H F1 對側的 DSR 也從 0.0163 變成 0.0527。文件只列最佳變體，沒有矛盾。
- payload 的 `equity_wiped_out`：`time_ms` 1783508400000，`min_equity` "-525.7534129392851326600"，附說明。沒爆倉的 F2 1H 是 None。
- 文件 `docs/research-real-data-plan.md:725` 寫「result.json 最大 929,807 bytes（F3 1H）」：payload 實測 929,807 bytes，相同。

**單元測試**

`tests/test_research_overfit.py` 的 `WipedOutTest` 涵蓋拒算、計入 N、不計入變異數與 PBO、最佳參數爆倉時 DSR 是 None，以及 `overfit_rows`。這些都在 Y7 的全套測試裡通過。

## Y2. O3 輸出上限：PASS（附 N1、N6）

**程式核對**

- `catos/reporting.py`：
  - `:80`、`:87`、`:104` 只畫 `indices` 指定的點，x 仍是 `pad_left + i × plot_w ÷ (n − 1)`，也就是原本的索引位置。
  - `:43` 的軸標籤與 `:76-77` 的 y 軸範圍都用整條曲線。
  - `:154` 頭尾各取一半。`:160` 寫出省略的列：「中間省略 N 筆；完整成交明細在 result.json 的 result.trades」。
  - `:219`、`:221` 檢查輸入。
  - `:239-241` 加上抽樣說明。
- `catos/research_catalog.py:154` `REPORT_MAX_FILL_ROWS = 400`。`:682` 報告使用和 payload 相同的 `keep` 索引。
- 2 MB 上限的位置：`catos/research_service.py:212`，限制 worker 的 stdout；`research_worker.py:57` 輸出的是 `{"payload", "report"}`。

**真實資料**（`o3_check.py`，F3 1H，26,233 點）

```
PASS report draws returned_points | 1875 of 26233
PASS every drawn point (x,y) equals a full-render point (original x kept)
FAIL drawn x ascending, first/last at plot ends | 188.2,49.5 .. 868.0,255.3
PASS axis labels = full-curve max/mid/min | ['10950.2924250', '5212.2695060303574336700', '-525.7534129392851326600']
PASS zero line drawn (curve crosses 0)
PASS fill table capped with omission note | fills 1488, omitted 1088
PASS table header keeps full count
PASS sampling note
F3 1H report 113,311 B (full render 529,657 B)
```

- 抽樣後畫出的每一個點（x, y），都和完整渲染的同一點逐字相同，所以 x 保留了原始索引。
- 軸標籤是整條曲線的最大值、中間值、最小值。最小值 -525.75 這個點不一定會被抽到，但標籤照樣有。
- 唯一的 FAIL 是我自己多加的檢查：我原本假設第一個點一定會被畫出來。實際上抽樣是「每個區間保留回撤最深的點，再加上最後一點」（`research_catalog.py:624-638`，原本就是這樣），不保證包含第一個點。所以圖從 x=188.2 開始，繪圖區起點是 188.0。這不在修正的宣稱範圍內，記為 N6，不算 O3 的缺陷。

**真實 worker 子程序**（6 個月 5m，Donchian）

```
Donchian 12/3 5m: fills 5,801, payload 1,682,145 B, report 114,720 B, worker stdout 1,798,187 B (cap 2,000,000) -> ok 2.05s
Donchian 8/2 5m: fills 7,757, payload 2,077,363 B, report 114,714 B, worker stdout 2,193,399 B (cap 2,000,000) -> ResearchError: research_output_limit 1.82s
```

- 我另外直接起 worker，量原始 stdout：12／3 是 1,798,187 B，8／2 是 2,193,399 B，和程序內 `json_text` 的結果逐位元組相同，報告內容也和程序內渲染的相同。
- 結論「5,801 筆可以跑、7,757 筆超過上限」成立。報告約 113～115 KB，和文件 `:727`「約 115 KB」相符。
- 文件 `:728` 寫的 1,797,828／2,193,038 bytes 比 HEAD 少 359／361 bytes，見 N1。

## Y3. O10 `tools/fetch_okx_candles.py`：PASS（附 N4）

**程式核對**

- `:253` `MIN_RESUME_REQUESTS = FUNDING_RESERVE + 2 = 8`。`:226-227` 在任何請求之前就用 `parser.error` 結束（exit 2）。
- `:263-272` `_write_staging`：先寫 `.tmp`，再 `os.replace`；失敗時刪掉 `.tmp`。
- `:318` 每次執行抓完 K 線就存進度，包括最後一次。`:334-338` 失敗時重存一次，更新請求數。
- `:295` 存檔時記下 `saved_at_s`。`:309-311` 下一次執行如果距離上次存檔不到 0.25 秒，就等到滿 0.25 秒。

**fake client 實測**（`o10_check.py`；離線，`socket.socket` 被封鎖）

```
PASS budget 1..7 --resume refused (exit 2, 0 requests, no staging)   ← 7 個預算逐一測
PASS CLI --resume --max-requests 7 refused | error: --resume needs max-requests >= 8 …
PASS multi-run completes | [3, 0]
PASS every request gap >= 0.25 s incl. across runs (real clock) | min gap 0.2501s; cross-run gaps [0.2509]
PASS manifest requests == sum over runs | 5 vs [2, 3]
PASS staging removed, no .tmp left
PASS single-run dataset files byte-identical to multi-run | ['candles.csv', 'funding.csv', 'instrument.json']
PASS funding failure -> exit 1, staged cursor reached start (candles kept) | code 1, stopped after 3 requests: http_400
PASS staged request count includes failed run | 5 = 2 + 3
PASS next run fetches only funding and finishes | ['/api/v5/public/funding-rate-history']
PASS manifest total counts all runs incl. failed
PASS torn write: exit 1, previous staging intact, no .tmp left | stopped after 2 requests: simulated crash mid-write
PASS run after torn write continues normally | 0
INFO first-run paging failure: code 1, requests 2, staging exists False
FAILURES: none
```

- 跨次節流用的是真實時鐘：`Client` 用預設的 `time.monotonic`／`time.sleep`，`wall_clock` 用 `time.time`。兩次執行背對背啟動，跨次的間隔是 0.2509 秒。
- 寫到一半中斷：我讓 `.tmp` 只寫一半就丟 `OSError`。結果原本的 staging 檔逐位元組不變，沒有留下 `.tmp`，下一次執行也正常完成。
- 最後一列 INFO 是 N4 的情況。

## Y4. O1、O8、O9 程式與前端：PASS

**O1**

- `catos/research_overfit.py:189-195` 只寫實際觸發的條件。`misc_check.py` 實測：
  - `trials=40`、佔比 0.2：只寫「有 20% 的切法剛好落在中位數」，沒有「只有 40 組」。
  - `trials=4`、佔比 0：只寫「只有 4 組參數」，沒有「0% 的切法」。
  - 兩個條件同時成立時寫「只有 4 組參數、有 50% 的切法…」；兩個都不成立時不提醒。
- 真實 1H 組在前端渲染出「只有 4 組參數、有 73% 的切法剛好落在中位數」。

**O8**

- `frontend/cat-os-vite/src/pages/backtest.tsx:573-590`：勝率旁邊同時顯示賺賠比與每筆期望值。`result` 為 null 時顯示「--」（`:585-586`）；有結果但沒有 `trade_stats` 時才顯示「舊紀錄沒有往返統計」。
- `trade-stats-panel.tsx:34-35`：`average_hold_hours` 為 null 時只顯示「不適用」。
- `backtest.tsx:603-612`：爆倉時顯示紅色提示，時間用 `formatDateTimeWithYear`（`src/lib/format.ts:186`）。舊紀錄沒有這個欄位時不顯示。

**O9**

- `catos/research_trades.py:86` `_compact`，在 `:128` 套用。
- 用上一輪報告舉的同一筆 tsmom-multi 4H 舊 payload（上一輪驗收的 `payload_tsmom_4h.json`）在 HEAD 重跑：

```
numeric diffs []
residual 1.5501000000000000000000000000 ... -> 1.5501E-45
open 398.19010171237607477443100000 ... len 121 -> 398.190101712376074774431
json bytes 1742 -> 1308
```

- 1H 的 F2、F3：13 個和 14 個 Decimal 欄位，壓縮前後的數值都相等，也沒有尾端補 0。

**前端 SSR 實測**（`fe_check.mjs`，用 vite `ssrLoadModule` 載入真實元件，再用 `renderToStaticMarkup` 渲染。輸入是 `search_report` 對真實 1H 四個變體的輸出）

```
PASS best wiped: Sharpe row shows 爆倉，不計算 (no "null")
PASS best wiped: DSR/PSR show 不適用
PASS best wiped: wiped count row 1 組
PASS best alive: Sharpe number shown, wiped row 1 組, verdict mentions 爆倉
PASS best alive: O1 verdict names both fired conditions
PASS legacy report (no wiped fields): no wiped row
PASS wiped_out_trials 0: no wiped row
PASS trade stats: 平均持倉 不適用 without 小時
PASS trade stats: 平均持倉 51.9 小時
PASS formatDateTimeWithYear(2026-07-08 11:00 UTC) = 2026/07/08 19:00 (Taipei)
PASS formatDateTimeWithYear year boundary (2025-12-31 16:00 UTC -> 2026/01/01 00:00)
PASS formatDateTimeWithYear null -> 不適用
PASS banner min equity format
FAILURES: none
```

- 第一次執行有 3 項 FAIL，原因在我的腳本：`text()` 沒有還原 `&gt;`；另外「沒有爆倉列」的檢查誤比到判讀文字裡的「權益跌破 0（爆倉）」。改成比對「權益跌破 0（爆倉） 1 組」之後全部 PASS。元件的輸出本身沒有變。
- 回測頁頂部與爆倉提示是整頁元件，沒有單獨渲染，只核對了程式碼與用到的格式函式（見「未涵蓋」）。

## Y5. 文件與註解（O2、O4、O6、O7、O11）：PASS（附 N2、N3）

- **O2**：`docs/research-real-data-plan.md:649` 補上兩條規則，並註明是補記。程式 `catos/research_intraday.py:162-167`（`decision is None and position == ZERO` 才登記發動；新的發動直接覆蓋 `self.launch`）和文字一致。策略原始碼在這個 commit 沒有變（`--stat` 不含 `research_intraday.py` 與 manifest）。照字面另寫的四個數字引自上一輪報告，本輪沒有重算。
- **O4**：`:721-723` 的各組最佳 DSR、PBO、逐變體範圍 0.0002～0.1346，全部和 Y1 的重算相同。選法沒有寫明，見 N3。
- **O6**：`:736` 寫「1.87～4.12（5m～1H 是 2.92～4.12，4H 是 1.87）」。表內 F1 對側四個週期的值是 4.12、4.06、2.92、1.87，相符。
- **O7**：`docs/next-steps.md:93` 已把 F 改成「已 commit `2f839a36`、獨立驗收 PASS 9／9」，O7 本身照做了。但同一行又寫了這批修正「尚未 commit、尚未獨立驗收」，見 N2。
- **O11**：
  - `catos/research_catalog.py:158-164` 的註解：(20 + 1) × 60,000 = 1,260,000，實測 14.1～14.5 秒，最壞約 17 秒，不加預檢。
  - 重測：20 次 TPE、5m 6 個月、Donchian 96～480／12～72，透過真 worker 兩次，分別 14.6 秒、14.3 秒（逾時 30 秒；本次 N 為 13，評估 51,840 根）。和註解相符，比上一輪報告的 14.5 秒多 0.1 秒以內。
  - 「最壞約 17 秒」是外推：14.5 × 60,000 ÷ 52,704 ≈ 16.5 秒，加上程序開銷。本輪沒有實際跑 60,000 根的資料集，因為沒有這麼長的已授權資料。
- **README.md:15、:66**：寫的抽樣、400 筆上限、爆倉標示與 `--max-requests` 至少 8，都和程式一致。

## Y6. 收錄的報告和原檔相同：PASS

```
$ git show b8eb1280:reports/research-shortterm-acceptance-20261107/acceptance.md | tr -d '\r' | sha256sum
39e8ec450f3fe02e322f8c6a7db3d8b7cc4bad9b74bb9814edb38d772164a688
$ tr -d '\r' < .claude/worktrees/acceptance-shortterm-a51238/reports/research-shortterm-acceptance-20261107/acceptance.md | sha256sum
39e8ec450f3fe02e322f8c6a7db3d8b7cc4bad9b74bb9814edb38d772164a688
```

兩邊都沒有 CR（`grep -c $'\r'` 都是 0），逐位元組相同。原檔大小 48,676 bytes。

## Y7. 迴歸：PASS

| 命令（cwd 是 worktree；`PY=C:/Users/user/Desktop/CatOS/.venv/Scripts/python.exe`） | 結果 |
| --- | --- |
| `$PY -B -m unittest discover -s tests` | `Ran 1475 tests in 184.569s`、`OK (skipped=11)`，3 分 8 秒；log 中有 `Port 53029 already in use. No process stopped and no alternate port selected.`，是既有 fixture 遇到埠被佔用時的處理，不是失敗。本 worktree 有 `data/okx` 副本，總數和 skip 數仍和開發者自測相同 |
| `git diff --check 2f839a36 b8eb1280` | exit 0 |
| 差異檔案逐一 `git show b8eb1280:<path> \| grep -c $'\r'` | 全部是 0（LF） |
| `git ls-tree -r b8eb1280 --name-only \| grep -c '^data/'` | 0 |
| `frontend/cat-os-vite`：`npm ci` | EXIT 0（`allow-scripts` 警告沒有執行 esbuild postinstall，不影響後面的檢查） |
| `npm run typecheck` | exit 0 |
| `npm run check:tokens` | `check:tokens OK - no arbitrary font sizes in src/ or index.html` |
| `timeout 180 npm test`（第 1 次） | exit 124：`EPERM: operation not permitted, rename '…node_modules\.vite\deps_temp_017dbc3b' -> '…\.vite\deps'`，21 個 ✖ 後逾時。就是 O12 的 `npm ci` 後第一次的情況 |
| `timeout 180 npm test`（第 2 次） | exit 0，`tests 21`、`pass 21`、`fail 0` |

## 指令與腳本

| 命令 | 結果 |
| --- | --- |
| `git show b8eb1280 --stat`、`git diff 2f839a36 b8eb1280 -- catos/ tools/ tests/ frontend/ README.md docs/` | 21 個檔案，+1079／−73 |
| `cp -r C:/Users/user/Desktop/CatOS/data/okx data/okx && diff -r …` | `SAME` |
| `PYTHONIOENCODING=utf-8 PYTHONPATH=. $PY -B $S/o5_check.py` | `FAILURES: none` |
| `… $PY -B $S/o3_check.py $S/svc_scratch` | 只有 N6 那一項自加檢查 FAIL，其餘 PASS |
| 直接起 `catos.research_worker` 量 stdout（行內腳本） | 1,798,187／2,193,399 B，和程序內的結果相同 |
| `… $PY -B $S/o10_check.py` | `FAILURES: none` |
| `… $PY -B $S/misc_check.py $S/svc_scratch` | `FAILURES: none`；O11 14.6 秒、14.3 秒 |
| tsmom 4H 舊 payload 重跑（行內腳本） | `numeric diffs []` |
| `node $S/fe_check.mjs <frontend> $S` | 修正我自己的比對後 `FAILURES: none` |

## 非阻斷觀察

**N1（文件數字，位元組級）　`docs/research-real-data-plan.md:728` 的 worker 輸出大小，在 HEAD 上不能逐位元組重現。**

- 文件寫 1,797,828／2,193,038 bytes，HEAD 實測 1,798,187／2,193,399 bytes，固定多約 360 bytes。我直接量 worker 的原始 stdout，和程序內結果相同，所以差異不是量法造成的；比較可能是開發者在定稿前的版本量的。
- 「每天約 32～42 筆」是用資料集約 183 個日曆天算的。用評估期間 180 天（51,840 根）算，是 32.2～43.1 筆。
- 結論（5,801 筆可跑、7,757 筆超過）不變。可改成本輪的數字，或註明是約略值。

**N2（文件狀態，第三次）　`docs/next-steps.md:93` 在 commit `b8eb1280` 內寫「修正只有開發者自測，尚未 commit、尚未獨立驗收」。**

- 和上一輪的 O7、再上一輪的 O6 同型：狀態文字在 commit 前寫好，一 commit 就過時。
- 本次驗收後要更新成「已 commit `b8eb1280`、獨驗 PASS」。可考慮把狀態改寫在 commit 之後的下一筆變更，或不寫「尚未 commit」這種一定會過時的字眼。

**N3（文件措辭）　`:721`「各週期組內選出的最佳變體（四個週期都是 F2）」沒有寫依什麼選。**

- 依淨損益（和優化的搜尋目標 `return_pct` 相同）選，四個週期都是 F2，和文件的數字一致。
- 依 Sharpe 選的話，5m 是 F3（DSR 0.0646），不是 F2（0.0069）。
- 建議補上「依淨損益選」。

**N4（抓取工具邊界）　`--resume` 第一次執行在 K 線分頁時失敗，已花的請求不會記進總數。**

- 實測：腳本讓第 2 個請求回 400，exit 1，花了 2 個請求，沒有 staging 檔。下一次從頭開始，manifest 的 `requests` 不含這 2 個。
- `tools/fetch_okx_candles.py:283-286` 的 docstring 寫得準確（只有存過進度或載入暫存之後才重存）。但計畫表的 O10 列寫「失敗的請求也計入總數」，沒有寫這個例外。
- 單次 150 次上限照樣由 `Client` 強制，所以不影響授權的遵守，只影響 manifest 總數的完整性。
- commit 訊息寫「每頁 K 線抓完即存 staging」，實際是每次執行抓完所有 K 線頁才存一次；計畫表的寫法是對的。

**N5（統計邊界）　沒爆倉的組只剩 1 組時，N 不起作用。**

- `search_report` 只用沒爆倉的組估 Sharpe 變異數（`research_overfit.py:220-222`）。只剩 1 組時，變異數是 0，`expected_max_sharpe` 回 0（`:92-93`），DSR 就等於「Sharpe > 0」的 PSR，不管 N 是多少。
- 例如 20 組裡 19 組爆倉，剩下那 1 組的 DSR 會被高估。這個情況下，判讀文字仍會寫「有 19 組參數權益跌破 0」。
- 判讀的「只有 N 組參數」用的是含爆倉的 N（1H 組寫 4 組，PBO 實際用 3 組）。
- 真實資料沒有遇到。可考慮在沒爆倉的組少於 2 時把 DSR 設為 None，或在判讀中註明。

**N6（報告圖表，外觀）　抽樣後的權益圖不一定從第一個點開始。**

- `sample_curve_indices`（`research_catalog.py:624-638`）每個區間取回撤最深的點，再補上最後一點，不保證包含索引 0。
- F3 1H 的圖從 x=188.2 開始（繪圖區起點 188.0），初始權益那一點沒有畫出來。payload 的回撤曲線原本就是這樣，只影響外觀。

**O12（環境，依約不處理）　本輪重現一次。** `npm ci` 後第一次 `npm test` 出現 vite `deps_temp` 改名的 EPERM，然後逾時。第二次 21／21。

## 未涵蓋

- **瀏覽器實測**：沒有起研究服務與 Vite 開發伺服器。回測頁頂部的勝率列與爆倉紅色提示是整頁元件，只核對了程式碼（`backtest.tsx:573-612`）與用到的格式函式；版面、顏色與互動由使用者自行在網頁驗收。過擬合面板與往返統計面板用 SSR 實際渲染過。
- **研究服務 HTTP 路徑**：worker 輸出上限與優化時間用 `ResearchService._compute` 起真 worker 驗證，沒有經過 HTTP 端點，也沒有寫出 `result.json`／`status.json`。
- **O2 照字面另寫的四個數字**（-1,143.91、-433.23、-2,221.51、-2,421.04）引自上一輪報告，本輪沒有重寫那份另寫的實作。
- **O11 的 60,000 根最壞情況**：只重測了 51,840 根的 5m 資料，17 秒是外推。
- **文件其他沒改的數字**（例如 `:725`「每次回測 0.4～1.6 秒」、15 變體實測表的其他欄位）：本輪只重算了修正涉及的爆倉、bootstrap、DSR、PBO 與輸出大小，其餘沿用上一輪的獨驗結果。
- **開發者的 `measure_f2.py`**：在開發會話的 scratchpad，我看不到，所以用自己的腳本重算，沒有比對開發者的腳本。
