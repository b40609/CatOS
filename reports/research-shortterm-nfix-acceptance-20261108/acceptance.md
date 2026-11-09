# 工作包 F 第二輪觀察 N1～N6 修正（7b7f743c）獨立驗收

- 驗收對象：commit `7b7f743c`（父 `b8eb1280`），分支 worktree `claude/acceptance-nfix-912eb4`，工作樹乾淨。
- 範圍：`reports/research-shortterm-fix-acceptance-20261108/acceptance.md` 的 N1～N6，以及 `docs/research-real-data-plan.md:770-777` 宣稱的處理。
- 驗收者：沒有參與 `7b7f743c` 的開發；開發者自測（1478 tests OK）只作參考，下面的結果都是本輪實際執行的。
- 日期：2026-11-08。
- 限制遵守：沒有連網、沒有呼叫 OKX；`C:/Users/user/Desktop/CatOS/data/okx/` 只唯讀使用（執行前後所有檔案 sha256 相同）；沒有碰金鑰、沒有啟動 8770／8771、沒有改產品 DB、沒有 commit／push。

## 總判定：PASS（6／6），無阻斷缺陷

| 項目 | 判定 |
| --- | --- |
| N5 DSR／PBO 爆倉邊界 | PASS（附觀察 P2） |
| N6 抽樣保留第一點 | PASS（附觀察 P3、P4） |
| N4 `--resume` 第一次執行計入請求 | PASS |
| N1 worker 輸出位元組數 | PASS（附觀察 P1） |
| N2 next-steps 狀態措辭 | PASS（附觀察 P5） |
| N3 組內最佳變體選法 | PASS |
| 收錄的第二輪報告逐位元組相同 | PASS |
| 全套後端測試 | PASS：Ran 1478 tests，OK (skipped=11) |

本輪新觀察 P1～P5 都是非阻斷，不影響研究結論。

## N5 `catos/research_overfit.py`：PASS

**程式核對**

- `:231` `variance_known = len(alive) >= 2 or trials < 2`；`:232` 變異數無法估計時 DSR 是 None。`:233` PSR 照算（只在最佳參數爆倉時是 None）。
- `:174-175` 判讀：DSR 是 None、有爆倉、進入 PBO 的組數 < 2 時寫「沒爆倉的參數組不到 2 組，無法估計 Sharpe 變異數，DSR 不計算。」再接爆倉說明。
- `:172-173` 最佳參數爆倉的分支在前面，所以「最佳爆倉、只剩 1 組沒爆倉」仍寫「最佳參數權益跌破 0」，正確。
- `:260` 傳給 `verdict` 的組數改成 `len(alive)`，`:193-194` 的「只有 N 組參數」因此是實際進入 PBO 的組數。沒有爆倉時 `len(alive) == len(names)`，所以沒爆倉情境的文字不變。
- `verdict` 只有 `search_report` 一個呼叫端（`grep -rn "verdict(" catos tools`）。
- 只有一組參數時 `trials < 2`，DSR 仍照算，等於對 0 的 PSR。

**真實資料重算**（`n5n6_real.py`：用 repo 的 `validate_request`、`registered_factory`、`research.backtest` 跑 15 個變體；10 張、taker 0.0005、滑價 2 bps、本金 10,000，預熱 5m 864、15m 288、1H 72、4H 18；每組同時用 `7b7f743c` 與 `b8eb1280` 版的 `search_report` 算）

```
 5m F1-0 net -1702.0702204319200547180 ... 15 個變體淨損益與文件表格相同（-1,702.07 … -1,262.60）
PASS 5m: best=F2 N=4 wiped=0 dsr=0.0069 psr=0.0412 pbo=0.7714 doc=('0.0069', '0.7714') | old==new: True diff_keys=[]
     best-by-Sharpe=F3
PASS 15m: best=F2 N=4 wiped=0 dsr=0.1198 psr=0.4391 pbo=0.5000 doc=('0.1198', '0.5000') | old==new: True diff_keys=[]
PASS 1H: best=F2 N=4 wiped=1 dsr=0.0758 psr=0.4159 pbo=0.7714 doc=('0.0758', '0.7714') | old==new: False diff_keys=['verdict']
   new verdict ... 注意：只有 3 組參數、有 73% 的切法剛好落在中位數 ...
   old verdict ... 注意：只有 4 組參數、有 73% 的切法剛好落在中位數 ...
PASS 4H: best=F2 N=3 wiped=0 dsr=0.1346 psr=0.3595 pbo=0.6286 doc=('0.1346', '0.6286') | old==new: True diff_keys=[]
1H F2+F3(wiped) new: dsr None psr 0.4159 pbo None | 沒爆倉的參數組不到 2 組，無法估計 Sharpe 變異數，DSR 不計算。有 1 組參數權益跌破 0（爆倉）…
1H F2+F3(wiped) old: dsr 0.4159 psr 0.4159 | dsr==psr True
1H F2 alone: dsr 0.4159 psr 0.4159 equal True
data unchanged: True
FAILURES: none
```

- 四組依淨損益選出的最佳變體都是 F2，DSR／PBO 和文件 `docs/research-real-data-plan.md:721` 逐值相同。
- 5m、15m、4H 三組沒爆倉，新舊版 `search_report` 的整份輸出（JSON 排序後）完全相同。
- 1H 組只有判讀文字從「只有 4 組參數」改成「只有 3 組參數」，所有數字相同。
- 用真實的 1H F2（沒爆倉）加 F3（爆倉）組成兩組的搜尋：舊版 DSR = PSR = 0.4159（N 不起作用，N5 原缺陷重現）；新版 DSR 是 None、PSR 仍是 0.4159、判讀寫明原因。
- 單獨跑 1H F2：DSR = PSR = 0.4159，維持原行為。

**邊界補測**（用 `tests/test_research_overfit.py` 的 `WipedOutTest` fixture）

```
不同參數組數 N（只計本次） = 4
N 組純運氣可期待的最大 Sharpe（年化） = 0.000
PSR（真實 Sharpe > 0 的機率） = 0.0000
DSR = None
PBO（CSCV） = 樣本不足
判讀 = 沒爆倉的參數組不到 2 組，無法估計 Sharpe 變異數，DSR 不計算。有 3 組參數權益跌破 0（爆倉）…
variance 0.00000000
best wiped, alive 1: None None 最佳參數權益跌破 0（爆倉），無法計算 DSR。有 3 組參數權益跌破 0（爆倉
all wiped: None None 最佳參數權益跌破 0（爆倉），無法計算 DSR。有 4 組參數權益跌破 0（爆倉
```

- HTML 報告的 DSR 是 None 時顯示「—」（`catos/research_catalog.py:592-593`）；前端過擬合面板顯示「不適用」（`frontend/cat-os-vite/src/components/catos/overfitting-panel.tsx:59`）。
- 觀察 P2：變異數無法估計時，「純運氣可期待的最大 Sharpe」仍顯示 0.000、變異數 0.00000000，見下文。

## N6 `catos/research_catalog.py` 的 `sample_curve_indices`：PASS

**程式核對**

- `:635` 區間大小改用 `limit - 2`，`ceil(total / (limit - 2))` 個區間最多 `limit - 2` 個；`:638-641` 補第一點與最後一點，所以總數 ≤ `limit`。
- `:636-637` 每個區間仍取回撤最深的點（同深取最早），全域最大回撤點一定在某個區間裡，不會遺失。
- 呼叫端：`execute_request` 的 payload 與報告用同一個 `keep`（`:670`、`:682-686`）；`catos/research_validation_job.py:146-149` 也呼叫同一個函式。

**真實資料**（F3 1H，經 `execute_request` 產生 payload 與報告）

```
curve_sampling {'total_points': 26233, 'returned_points': 1876, 'method': 'bucket_deepest_drawdown'} len eq 1876 len dd 1876 full pts 26233
first payload point == first full point: True last: True
keep len 1876 <=2000 True ascending unique True first/last 0 26232 max-dd index 24302 kept True maxdd 104.80127281111659566169074247348239195539109084569
payload times == keep times True
report polyline points 1876 first 188.0,49.0 last 868.0,255.3
plot start x1 188 | sampling note: 圖表取樣 1876／26233 點（每個區間保留回撤最深的一點）；績效數字以全部 K 線計算。
old sampler first 6 len 1875 | new len 1876
```

- 報告的權益折線第一點 x = 188.0，等於繪圖區起點（上一輪是 188.2）。
- `curve_sampling` 的 `total_points`、`returned_points` 和 payload 的權益點數、回撤點數一致；payload 每一點的時間都等於 `keep` 指到的原始點。
- 15 個變體全部：第一點是 0、最後一點是最後一根、點數 ≤ 2,000（5m 1,995、15m 1,932、1H 1,875～1,876、4H 1,824）、最大回撤點都有保留。

**性質測試**（`n6_prop.py`，seed 20261108）

```
random cases 4000 violations 0
validation limit 125: new returned 124 (<= 124), old returned 125
...
validation limit 1000: new returned 974 (<= 999), old returned 974
limit=2 -> ZeroDivisionError (old: [0, 9] )
```

- 4,000 組隨機（長度 1～6,000、limit 3～2,500）：第一點、最後一點、≤ limit、遞增不重複、最大回撤點保留、短於 limit 時原樣回傳，全部成立。
- 觀察 P3、P4 見下文（驗證任務少用一點、limit = 2 會除以 0，現行呼叫端都碰不到）。

## N4 `tools/fetch_okx_candles.py`：PASS

**程式核對**

- `:301-304` 抽出 `progress(cursor)`，內容和原本 `:324` 之後存的欄位相同。
- `:320-323` 第一次執行：`fetch_instrument` 與 `contract_from_instrument` 通過後，先 `save(progress(end_ms))`，之後才分頁。
- `:340-345` 任何失敗：`staged` 不是 None 就重存，`requests = previous + client.requests`，所以分頁失敗的請求會計入。
- 合約資料就失敗時 `staged` 仍是 None，不留紀錄；docstring `:283-290` 寫明。
- 續抓、`_write_staging` 原子寫入（`:263-272`）、跨次節流（`:316-318`）、資金費失敗保留 K 線（`:326`、`:333`）的程式沒有改。

**fake client 實測**（`n4_check.py`；用 repo 測試的 `FakeOKX`，`socket.socket` 與 `socket.create_connection` 都被換成會丟例外的函式）

```
PASS first run instrument 400 -> exit 1, no staging | code=1 requests=1 err=stopped after 1 requests: http_400
PASS first run instrument retries exhausted -> no staging | code=1 requests=4 err=stopped after 4 requests: retries_exhausted: http_503
PASS first run contract check fails -> no staging, no paging | code=1 requests=1 err=stopped after 1 requests: instrument_not_linear_usdt_swap
PASS first run 2nd page fails -> staged requests 3 | code=1 requests=3 staged=(3, True, 0)
PASS resumed to completion; manifest requests == all requests spent == fake server calls | manifest=7 spent=7 server_calls=7
PASS manifest.json on disk carries the same total | requests field present=True
PASS old b8eb1280 left no staging after first-run paging failure (defect reproduced) | requests=2
PASS old manifest undercounts | old manifest=5 actually spent=7
PASS rerun 0.05 s after first-run save waits the remaining 0.20 s | sleep=0.2000
PASS clean resume completes, total == server calls, staging removed | requests=5 calls=5
PASS new vs old clean resume: same data files and same request total | new=5 old=5
ALL PASS
```

- 第一次執行第 2 頁失敗時，已抓到的第 1 頁 K 線不保留（存的是分頁前的進度），但 3 次請求都計入；續抓到完成，manifest 的 7 次等於 fake 伺服器實際收到的 7 次。舊版同情境 manifest 寫 5、實際 7，N4 原缺陷重現並確認已修。
- 合約資料就失敗（HTTP 400、重試耗盡 4 次、合約檢查不過）都不留 staging，和 docstring 一致。
- 第一次執行的新存檔也帶 `saved_at_s`，下一次執行的跨次節流照常（等 0.20 秒）。
- 沒有失敗的續抓：新舊版的資料檔逐位元組相同、請求總數相同，沒有退步。
- 既有的 `ResumableFetchTest`（含原子寫入與跨次節流、資金費失敗保留 K 線、預算 6／7 拒絕）在全套測試中一起跑。

## N1 文件位元組數：PASS（附觀察 P1）

**實測**（`n1_bytes.py`，程序內 `json_text({"payload", "report"})`，等同 worker stdout；provenance 路徑設成 repo 相對路徑，和正常 checkout 相同）

```
warm 864 12/3 old-sampler: fills 5801 stdout 1,798,187 B cap 2,000,000 -> ok; sampling {... 'returned_points': 1995 ...}; fills/day(180) 32.23
warm 864 12/3 7b7f743c: fills 5801 stdout 1,798,443 B cap 2,000,000 -> ok; sampling {... 'returned_points': 1996 ...}; fills/day(180) 32.23
warm 864 8/2 old-sampler: fills 7757 stdout 2,193,399 B cap 2,000,000 -> over; sampling {... 'returned_points': 1995 ...}; fills/day(180) 43.09
warm 864 8/2 7b7f743c: fills 7757 stdout 2,193,655 B cap 2,000,000 -> over; sampling {... 'returned_points': 1996 ...}; fills/day(180) 43.09
```

- 用 `b8eb1280` 的抽樣函式，逐位元組重現文件 `:728` 的 1,798,187／2,193,399 bytes。
- 評估期間：權益點 51,841 = 51,840 根 × 5 分鐘 = 180 天。5,801 ÷ 180 = 32.23、7,757 ÷ 180 = 43.09，「每天約 32～43 筆」正確。
- 第一次量時把資料根直接指到主 checkout，provenance 變成絕對路徑，多出 112 bytes（4 個檔 × 28 字元）；改成 repo 相對路徑後才相同。這是量法差異，不是程式差異。
- 觀察 P1：`7b7f743c` 的 N6 多保留一點，HEAD 上的輸出是 1,798,443／2,193,655 bytes，比文件多 256 bytes。文件已寫明「`b8eb1280` 獨驗重現的數字」，所以措辭正確；結論不變。

## N2 `docs/next-steps.md:93`：PASS（附觀察 P5）

- 原本「尚未 commit、尚未獨立驗收」已改成已 commit 的 hash（`2f839a36`、`b8eb1280`）與已完成的獨驗（PASS 9／9、PASS 11／11）及報告路徑；N1～N6 寫「只有開發者自測」。
- 報告路徑 `reports/research-shortterm-acceptance-20261107/acceptance.md`、`reports/research-shortterm-fix-acceptance-20261108/acceptance.md` 都存在。

## N3 選法措辭：PASS

- `docs/research-real-data-plan.md:721` 補上「依淨損益（和優化的搜尋目標 `return_pct` 相同）」與「依 Sharpe 選的話，5m 是 F3」。
- 實測：依 `return_pct` 四組都選 F2；依年化 Sharpe，5m 選 F3，15m、1H、4H 選 F2（上面 N5 輸出的 `best-by-Sharpe`）。
- 優化的搜尋目標確實是 `return_pct`（`catos/research_optimization.py:45` `score=lambda performance: performance.return_pct`）。

## 收錄的第二輪報告：PASS

```
b60d804f16604688b441cdab8e8050ae626ed93290b4d7e569fa9e9530a4d33f *reports/research-shortterm-fix-acceptance-20261108/acceptance.md
b60d804f16604688b441cdab8e8050ae626ed93290b4d7e569fa9e9530a4d33f *../acceptance-ffix-5810b1/reports/research-shortterm-fix-acceptance-20261108/acceptance.md
b60d804f16604688b441cdab8e8050ae626ed93290b4d7e569fa9e9530a4d33f *-     ← git show 7b7f743c:<同路徑>
identical                                                              ← cmp
i/lf    w/lf    attr/text=auto eol=lf    reports/research-shortterm-fix-acceptance-20261108/acceptance.md
0                                                                      ← CR 數
```

## 測試

在本 worktree（`7b7f743c`，執行前 `git status --short` 為空）跑全套後端：

```
$PY -B -m unittest discover -s tests
Ran 1478 tests in 252.743s
OK (skipped=11)
real	4m15.535s
exit 0
```

- 包含本 commit 新增的 `test_a_single_surviving_trial_gets_no_dsr`、`test_coarse_note_counts_only_trials_that_entered_pbo`、`test_a_first_run_paging_failure_still_counts_its_requests` 與 `sample_curve_indices` 的 limit 3／4／5／7 迴圈，以及既有的 `ResumableFetchTest`、`WipedOutTest`、驗證任務抽樣測試（`tests/test_research_datasets.py:253`）。
- 沒有 ERROR／FAIL 行。skip 數 11 和開發者自測、上一輪獨驗（1475 tests、skipped=11）相同；本輪沒有逐一核對 skip 的原因。

## 本輪觀察（非阻斷）

**P1（文件數字，位元組級）　`docs/research-real-data-plan.md:728` 的位元組數是 `b8eb1280` 的，HEAD 上多 256 bytes。**
- N6 讓 5m 的抽樣從 1,995 點變 1,996 點，worker 輸出 12／3 是 1,798,443 bytes、8／2 是 2,193,655 bytes。
- 文件已註明是 `b8eb1280` 的數字，措辭沒錯；之後若要寫「目前的大小」，要用 HEAD 重量。

**P2（統計顯示）　沒爆倉的組不到 2 組時，「純運氣可期待的最大 Sharpe」與變異數仍顯示 0。**
- `search_report` 在變異數無法估計時把 DSR 設為 None，但 `trial_sharpe_variance` 仍是 "0.00000000"、`expected_max_sharpe_annualized` 仍是 "0.000"（`catos/research_overfit.py:226-228`、`:249-251`）。
- HTML 報告（`catos/research_optimization.py:22`）和前端面板（`overfitting-panel.tsx:54`）會把 0.000 當成算出來的值顯示，和判讀「無法估計 Sharpe 變異數」並列。可考慮在 `variance_known` 為 False 時一併回 None／「不適用」。真實資料沒有遇到。

**P3（驗證任務，外觀）　`research_validation_job._sampled_curve` 的補點與 `limit - 1` 已多餘，每窗最多少畫 1 點。**
- `catos/research_validation_job.py:146-149` 仍傳 `limit - 1`，再補 0。現在函式本身就保留 0，所以每窗最多 `limit - 1` 點（例如 limit 125 時 124 點，舊版 125 點）。
- 不超過上限、不影響任何數字，只是少用 1 點；方法名稱 `bucket_deepest_drawdown_keep_first` 仍正確。

**P4（防禦性邊界）　`sample_curve_indices` 在 `limit = 2` 時除以 0。**
- 新算式 `-(-total // (limit - 2))`（`catos/research_catalog.py:635`）在 limit = 2 時 ZeroDivisionError；舊版可回 [0, 最後一點]。
- 現行呼叫端：payload 用 2,000，驗證任務最小是 1,000 ÷ 8 窗 − 1 = 124，都碰不到。之後新增呼叫端時要注意，或加上 limit ≥ 3 的檢查。
- payload 的 `curve_sampling.method` 仍寫 `bucket_deepest_drawdown`，報告說明「每個區間保留回撤最深的一點」沒提到頭尾點；驗證任務用的是 `..._keep_first`。只是命名，不影響數字。

**P5（文件狀態，輕微）　`docs/next-steps.md:93` 的「N1～N6 … 只有開發者自測」在本輪驗收後就過時。**
- 比原本「尚未 commit」好：commit 當下是事實。本輪 PASS 後要更新成已獨驗與本報告路徑。

## 未核對與限制

- **真 worker 子程序與 HTTP 路徑**：N1 的位元組數用程序內 `json_text` 量，沒有另起 worker 子程序；上一輪已確認兩者逐位元組相同（收錄報告 Y2），本輪沒有改 `research_worker.py`。也沒有經過研究服務 HTTP 端點。
- **前端**：本 commit 沒改前端，沒有跑 `npm test`／typecheck；DSR 是 None 時的顯示只核對程式碼（`overfitting-panel.tsx:59`）。
- **N4 的真實 OKX 行為**：依限制只用 fake client，沒有連網。
- **開發者的自測腳本**：看不到開發會話的 scratchpad，DSR／PBO 用 repo 函式加新舊版比對重算，沒有另寫 Fraction 參考實作（上一輪已用參考實作核對過同一批數字，本輪核對的是「新舊版輸出相同」）。
- 驗收腳本與輸出在本會話 scratchpad：`C:\Users\user\AppData\Local\Temp\claude\65ab48767f490e72\0a4a8f75-7421-4d27-9f06-e6856e61e6a4\scratchpad\`（`n5n6_real.py`、`n4_check.py`、`n6_prop.py`、`n1_bytes.py` 與對應 `*_out.txt`），不在 repo 內。

## 實際命令

| 命令 | 結果 |
| --- | --- |
| `git diff --stat b8eb1280 7b7f743c`；`git diff b8eb1280 7b7f743c -- catos tools tests docs` | 9 個檔，+415／-14 |
| `git show b8eb1280:catos/research_overfit.py`（及 `research_catalog.py`、`tools/fetch_okx_candles.py`）存到 scratchpad `old/` | 舊版對照 |
| `$PY -B $S/n5n6_real.py <worktree>` | 四組 DSR／PBO 與文件相同；沒爆倉的三組新舊輸出相同；`FAILURES: none`；資料檔未變 |
| `$PY -B $S/n4_check.py <worktree>` | 11／11 PASS |
| `$PY -B $S/n6_prop.py <worktree> $S/old/old_catalog.py` | 4,000 組 0 違反；P3、P4 |
| `$PY -B $S/n1_bytes.py <worktree> $S/old/old_catalog.py` | 舊抽樣重現 1,798,187／2,193,399；HEAD 1,798,443／2,193,655 |
| `sha256sum`、`cmp`、`git ls-files --eol` 比對收錄報告 | 相同，LF |
| `$PY -B -m unittest discover -s tests` | Ran 1478 tests，OK (skipped=11)，exit 0 |

（`$PY` = `C:/Users/user/Desktop/CatOS/.venv/Scripts/python.exe`；`$S` = 本會話 scratchpad。）
