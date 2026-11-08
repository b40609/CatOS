# D／E 驗收後修正與工作包 F（短週期研究）獨立驗收報告

- 日期：2026-11-07（Asia/Taipei）
- 驗收者：Claude Opus 5.5，獨立驗收會話。沒有參與 D／E 驗收後修正，也沒有參與工作包 F 的開發，沒有撰寫任何 commit，具 AGENTS.md「DEVELOPMENT WORKFLOW」所定的獨驗資格。
- 範圍：分支 `feat/research-overfitting` 的兩筆 commit，分開下結論。
  - **修正**：`3c78d6fd`，對照 `bd63e66e`（8 個檔案，+674／−16，其中 584 行是收錄的 D／E 驗收報告）。
  - **F**：`2f839a36`，對照 `3c78d6fd`（19 個檔案，+1058／−16）。
  - 驗收在 worktree `C:\Users\user\Desktop\CatOS\.claude\worktrees\acceptance-shortterm-a51238` 進行（分支 `claude/acceptance-shortterm-a51238`，HEAD 即 `2f839a36`，與 `feat/research-overfitting` 相同）。修正 commit 用 `git archive 3c78d6fd` 匯出到暫存目錄 `fix_tree\` 另外驗。
- 結論：
  - **修正：PASS（2／2）**
  - **F：PASS（9／9）**
  - 兩包都沒有阻斷缺陷。另有 12 項非阻斷觀察（O1～O12）。建議優先處理：
    - **O3**：真正的 2 MB 上限是 worker 的 stdout，含 HTML 報告；6 個月 5m 上，約 2,000 筆以上成交的策略會失敗。
    - **O2**：F2「持倉中遇到發動日」的處理沒寫進事前登錄，照字面另寫會得到不同數字。
    - **O4、O5**：計畫文件的組內 DSR 範圍不對；F3 1H 權益跌破 0，Sharpe、bootstrap、DSR 都失真。
  - 依指示沒有修改程式或文件，只新增本報告；沒有 commit、push、merge。
- 自寫腳本與完整輸出在本會話暫存目錄 `C:\Users\user\AppData\Local\Temp\claude\4677ee93a5daf182\6e45f232-c3a7-4988-bb65-b2926c991bba\scratchpad\`，不在 repo，會話結束後可能被清掉；關鍵輸出已抄進本報告。
  - Python：`check_fetch.py`、`check_fix.py`、`fref.py`（我的獨立實作）、`check_f.py`、`measure_f.py`、`dsr_alt.py`、`cap_probe.py`、`opt_probe.py`、`coverage_f.py`，以及沿用上一輪獨驗會話自寫的 scipy 參考實作 `ref_stats.py`。
  - 前端：`fe_check_f.mjs`。
  - 輸出：同名 `.log`、`measure_f.json`、`catalog.json`、`payload_f2_1h.json`、`payload_tsmom_4h.json`。

## 驗收限制與隔離

- **沒有連網採集**：沒有對 OKX 發任何請求，也沒有重新抓取資料。`--resume` 是用離線假 OKX 驗的：假 OKX 把真實資料集的內容，依 OKX 的分頁格式回應給工具，client 的 `base_url` 是 `https://fake.invalid`。
- **資料集**：依指示從主 checkout `C:\Users\user\Desktop\CatOS\data\okx\BTC-USDT-SWAP\` **複製** 4 個資料夾到 worktree 與 `fix_tree\` 的同一路徑（git 忽略，`.gitignore:29:/data/`）。複製後的 sha256 與各自 manifest 全部相符：

| 資料集 | candles | funding | instrument |
| --- | --- | --- | --- |
| `4H/okx-btc-usdt-swap-4h-20211106-20261106` | `5a702ece…` | `76d6e4e1…` | `248697dd…` |
| `1H/okx-btc-usdt-swap-1h-20231107-20261107` | `a8bce986…` | `c10c9cc7…` | `248697dd…` |
| `15m/okx-btc-usdt-swap-15m-20251107-20261107` | `82ff87d3…` | `c10c9cc7…` | `248697dd…` |
| `5m/okx-btc-usdt-swap-5m-20260508-20261107` | `8822be2c…` | `c10c9cc7…` | `248697dd…` |

- **參考實作**：DSR／PBO 用上一輪獨驗會話自寫的 `ref_stats.py`（scipy 1.18.1，裝在那個會話的暫存 `pkgs\`，用 `PYTHONPATH` 載入，沒有裝進專案 venv）。往返統計與 F1／F2 規則是我依文件另寫的 `fref.py`，往返用 `fractions.Fraction` 精確算術，不呼叫開發者的函式。
- **沒有修改**程式、測試或文件，只新增本報告。沒有 commit、push、merge、切換分支或 stash。
- **沒有啟動任何 HTTP 服務**，也沒有碰 8770／8771。
  - 輸出上限與逾時的量測，直接呼叫 `ResearchService._compute`。它會起真正的 worker 子程序（`python -B -s -m catos.research_worker`），套用同一個 2,000,000 bytes stdout 上限與 30 秒逾時，但不開埠。
  - 前端用 `tsc`、`node --test`，以及 Vite middleware 模式的 SSR 渲染（`ws: false`、`hmr: false`，不開埠）。
  - 結束時 24678／8770／8771 都沒有監聽，也沒有本 worktree 或 `fix_tree` 的 node／esbuild 程序殘留。主 checkout 有一個不是我啟動的 Vite（PID 36776），沒有碰。
- **環境**：venv 的 Python 3.14.6、Node v26.4.0。`catos` 匯入路徑都有印出確認：HEAD 指向 worktree，修正樹指向 `fix_tree\catos`。
- **自己啟動的程序**：`npm test` 第一次卡住，HEAD 與修正樹各發生一次，見 O12。我用 `timeout 180`／`timeout 120` 包住，逾時後程序已經結束，核對過沒有殘留。
- **暫存 junction**：修正樹前端共用 worktree 的 `node_modules`，用的是 junction。驗完已用 `cmd /c rmdir` 移除，只移除連結，worktree 的 `node_modules` 仍在。
- **執行後 worktree 只多了 git 忽略的產物**，依指示沒有刪除：
  - `data/`
  - `frontend/cat-os-vite/node_modules/`，含被中斷的 `.vite/deps_temp_f2e0a28e`
  - 測試自己產生的 `outputs/workspace-w6-fixture-test-856555f3…`、`outputs/workspace-w8-fixture-test-01aad23e…`
  - 本報告（`.gitignore:47:/reports/*`，要收進 repo 需 `git add -f`）
  - `git status --short` 乾淨，HEAD 仍是 `2f839a36`。

## 總表

### 修正（`3c78d6fd`）：PASS（2／2）

| # | 項目 | 結果 |
| --- | --- | --- |
| X1 | O1～O6 照上一份報告的建議修正，文件數字正確（完整格點 N=12／15／21、N=29、N=34 重算） | PASS |
| X2 | `logit_zero_share` 與判讀提醒、`edge_selections` 排除開關參數 | PASS（提醒措辭見 O1） |

### F（`2f839a36`）：PASS（9／9）

| # | 項目 | 結果 |
| --- | --- | --- |
| F1 | 採集與授權：AGENTS.md 條文與 manifest 一致；`--resume` 分次結果與單次逐位元組相同、每次 ≤ 150、範圍不同拒絕、staging 不算資料集 | PASS（邊界情況見 O10） |
| F2 | 往返統計：獨立還原、反手手續費拆分、資金費歸屬、對帳殘差與容許值 | PASS（JSON 字串見 O9） |
| F3 | 事前登錄規則與 `research_intraday.py` 一致（依文件自寫，逐筆成交比對） | PASS（F2 有一條未寫明，見 O2） |
| F4 | 沒有未來資料：真實 1H、15m 前綴不變性 | PASS |
| F5 | `Delayed` 修正：邏輯不變、只晚一根；E 的延遲數字前後相同 | PASS |
| F6 | 量測可重現：15 個變體全部欄位、買進持有、DSR、PBO | PASS（文件摘要句的數字見 O4、O5、O6） |
| F7 | 回測上限與輸出：60,000 根下的耗時與輸出大小 | PASS，附明示風險（O3、O11） |
| F8 | 前端：typecheck、`npm test`、勝率面板對舊紀錄與 payload | PASS（O8、O12） |
| F9 | 文件與程式一致 | PASS（O4～O7） |

### 共同

- 後端全套測試（`python -B -m unittest discover -s tests`）：
  - HEAD：`Ran 1466 tests in 188.840s`、`OK (skipped=11)`
  - 修正樹：`Ran 1449 tests in 198.569s`、`OK (skipped=11)`
  - 兩者都與開發者自測數字相同。
- 前端：
  - HEAD：typecheck exit 0；`npm test` 第 2、3 次都是 21／21（`check:tokens OK`）。
  - 修正樹：`tsc --noEmit` exit 0、`check:tokens OK`；`node --test` 第 2、3 次都是 21／21。
- 資料沒有進 git：`git ls-tree -r 2f839a36 --name-only | grep -c '^data/'` → 0，`3c78d6fd` 也是 0；兩筆 commit 的 `--stat` 都沒有 `data/okx` 或 `.csv`。

---

## X1. O1～O6 修正與文件數字：PASS

逐項對照上一份報告（`reports/research-overfitting-compare-acceptance-20261106/acceptance.md`「非阻斷觀察」）的建議：

| 觀察 | 上一份報告的建議 | 修正內容 | 判定 |
| --- | --- | --- | --- |
| O1 | 補註全格點數字，或在 N 小時讓判讀提示粒度粗、λ=0 佔比 | `docs/research-real-data-plan.md:431-437` 加完整格點表；`:443` 改寫判讀並引用 11／70；`catos/research_overfit.py:136-140` 回報 `logit_zero_share`；`:151`、`:171-173` 在 N < 10 或佔比 ≥ 10% 時加提醒 | 照做 |
| O2 | 表下註明對應 commit | `research-real-data-plan.md:431` 註明 `8ab4dbe9`、TPE 9／12 與 10／15 組 | 照做 |
| O3 | 寫明 N=29 算法、買進持有成交時點、相關係數的 C 是哪一版、張數換算價格 | `:562-565`（N=29 近似、0.3720、N=34 0.3960／0.1429）、`:546`（第二根評估 K 線開盤成交）、`:567`（箭頭版與評分版都列）、`:568`（決策日收盤） | 照做 |
| O4 | 兩個值的參數不計邊界，或改文案 | `research_overfit.py:229-231` 排除最多兩個值的參數，`:246` 列在 `excluded_switch_params` | 照做 |
| O5 | 更新 `research_costs.py:15-16` 模組說明 | `catos/research_costs.py:15-19` 改寫，並指向 `EQUITY_SIZED_NOTICE`（`:37`、`:144`） | 照做 |
| O6 | next-steps 狀態、README 列出 E 的三策略與 D 的 DSR／PBO | `docs/next-steps.md:36`、`:47` 改為已 commit、獨驗 PASS；`README.md:12`、`:15` 列出五個研究策略與 DSR／PSR／PBO | 照做 |

**重算核對**：`check_fix.py` 在 `fix_tree` 執行，同時跑開發者的 `execute_optimization`（n_trials 20，seed 42）和我的 scipy 參考實作，輸出：

```text
== orig: sampler exhaustive_grid trials 12 best {'entry_bars': 384, 'exit_bars': 48} (1.9s)
   mine: N 12 DSR 0.7126 PBO 0.4571 zero-share 0.0000
PASS orig: DSR dev == mine :: 0.7126 / 0.712629
PASS orig: PBO dev == mine :: 0.4571 / 0.4571
PASS orig: logit_zero_share dev == my count :: 0.0000 / 0.0000
PASS orig: verdict coarse-PBO warning iff N<10 or zero share>=0.1 :: warn False, N 12, share 0.0000
== wide: sampler exhaustive_grid trials 15 best {'entry_bars': 384, 'exit_bars': 48} (2.4s)
   mine: N 15 DSR 0.7688 PBO 0.2000 zero-share 0.0000
== union: dev N 21 DSR 0.7111 PBO 0.4286 zero 0.0000 | mine DSR 0.7111 PBO 0.4286
PASS doc table orig: N 12 DSR 0.7126 PBO 0.4571
PASS doc table wide: N 15 DSR 0.7688 PBO 0.2000
PASS doc table union: N 21 DSR 0.7111 PBO 0.4286
== TPE N=9 subset: PBO 0.2714 zero share 0.1571 -> 11/70; verdict has warning: True
PASS doc: N=9 has 11 of 70 splits at lambda=0
== N=29: dev N 29 DSR 0.3720 PBO 0.1429 | mine DSR 0.3720 PBO 0.1429
== N=34: dev N 34 DSR 0.3960 PBO 0.1429 | mine DSR 0.3960 PBO 0.1429
FAILURES: none
```

- 完整格點表（`:435-437`）、N=29、N=34 的數字，開發者函式與我的實作都完全相同。
- 「N=9 時 70 種切法有 11 種 λ=0」：TPE 試過的 9 組，取自上一輪 D 量測紀錄（全格點扣掉未試過的 (96,48)、(288,24)、(384,72)）。重算得到 0.1571 = 11／70。
- `docs/next-steps.md:40` 的「完整格點聯集 N = 21 時，DSR 0.7111、PBO 0.4286」與重算相同。

## X2. `logit_zero_share`、判讀提醒、`edge_selections` 排除：PASS（附 O1）

- **`logit_zero_share`**（`research_overfit.py:140`）：計算 λ 剛好等於 0 的切法比例。我用 `scipy.stats.rankdata` 另算，原範圍、放寬兩組都相同（0.0000），TPE 9 組是 0.1571，也相同。PBO 仍以 λ ≤ 0 計數（`:136-139` 的註解與 R `pbo`、fynance 慣例一致）。
- **判讀提醒**（`:171-173`）：條件「`trials < 10` 或佔比 ≥ 0.1」與文件 `:443` 一致。實測 N=12、15 不提醒，N=9 提醒，都正確。單元測試 `tests/test_research_overfit.py:154-163` 也涵蓋。措辭問題見 O1。
- **`edge_selections` 排除**（`:229-231`）：用 `(high − low) // step + 1 <= 2` 判定格點只有 1～2 個值的參數。這類參數任何選擇都落在邊界，排除邏輯正確。我的 5 個案例全部通過：

```text
PASS edge_selections ['vol_scaling']: at_edge 0, excluded ['vol_scaling'] :: (0, ['vol_scaling'], 2)
PASS edge_selections ['w']: at_edge 0, excluded ['w'] :: (0, ['w'], 1)        # 1..5 step 4，兩個值
PASS edge_selections ['w']: at_edge 1, excluded [] :: (1, [], 2)              # 1..5 step 2，三個值照算
PASS edge_selections ['w']: at_edge 0, excluded ['w'] :: (0, ['w'], 1)        # 單一值
PASS edge_selections ['e', 's']: at_edge 1, excluded ['s'] :: (1, ['s'], 2)   # 混合，None 窗不計
== tsmom-multi frontend default walk-forward (1.4s): {"windows_with_selection": 6, "windows_at_edge": 0, "params": {}, "excluded_switch_params": ["vol_scaling"]}
PASS tsmom-multi walk-forward: vol_scaling excluded, 0 windows at edge (was 6/6)
```

- 前端 `SelectionEdgesNote` 在 `windows_at_edge === 0` 時不顯示（`frontend/cat-os-vite/src/components/catos/overfitting-panel.tsx:72`）。所以上一輪 tsmom-multi 6／6 窗的無意義警示已消失。
- adapter 只新增兩個選填型別（`research-api-adapter.ts:273`、`:285`），舊紀錄缺欄位也能讀；修正樹 typecheck 0 錯誤。

---

## F1. 採集與授權：PASS（附 O10）

**授權條文與 manifest。** `AGENTS.md:29`（2026-11-07）授權的是：同一工具、三個公開 GET 端點；BTC-USDT-SWAP 的 1H 最近 3 年、15m 最近 1 年、5m 最近 6 個月；可分次接續；單次最多 150 次、間隔至少 0.25 秒；只存 `data/okx/`。三份 manifest 的實際內容：

| 資料集 | 區間（UTC） | 天數 | 根數 | 缺口 | requests | 抓取時間 |
| --- | --- | --- | --- | --- | --- | --- |
| 1H | 2023-11-07 12:00 → 2026-11-07 12:00 | 1,096 | 26,304 | 無 | 269 | 2026-11-07 20:34 +08 |
| 15m | 2025-11-07 12:30 → 2026-11-07 12:30 | 365 | 35,040 | 無 | 356 | 2026-11-07 20:35 +08 |
| 5m | 2026-05-08 12:35 → 2026-11-07 12:35 | 183 | 52,704 | 無 | 533 | 2026-11-07 20:38 +08 |

- 合約、週期與區間都在授權內，3 年、1 年、6 個月對應 1,096、365、183 天。
- `endpoints` 都只有 history-candles、funding-rate-history、instruments 三個。
- 資金費都是 279 筆、`complete: false`。
- 主 checkout 的 `data/okx/` 只有 BTC-USDT-SWAP 的這 3 份加既有 4H，`.staging/` 是空的。4H 的抓取時間仍是 11-06，沒有重抓。
- manifest 只記總請求數，**每次執行的請求數**只能靠下面的離線重放推得，見「未涵蓋」。

**`--resume` 離線重放**（`check_fetch.py`，假 OKX 依真實 CSV 回應，另外在資料開頭前補 300 根合成舊 K 線，模擬真實分頁會跨過起點）：

```text
PASS 1H: every run <= 150 requests :: per run [144, 125]
PASS 1H: total requests == manifest 269 :: sum 269
PASS 1H: resumed candles.csv sha256 == real manifest :: a8bce986e61494a4
PASS 1H: resumed manifest.json bytes == real manifest.json
PASS 1H: pacing >= 0.25 s between requests within each run (fake clock) :: min gap within runs 0.250; ...
PASS 1H: only the 3 public endpoints, instrument once, funding only in the last run :: instrument 1 funding 4
PASS 1H: resumed candles.csv == single-run candles.csv (bytes)    （funding、instrument、manifest 同樣 PASS）
PASS 15m: every run <= 150 requests :: per run [144, 144, 68]
PASS 15m: total requests == manifest 356 :: sum 356
PASS 5m: every run <= 150 requests :: per run [144, 144, 144, 101]
PASS 5m: total requests == manifest 533 :: sum 533
PASS 15m／5m: resumed 三個檔案 sha256 == real manifest；manifest.json 逐位元組相同；與單次結果逐位元組相同
PASS refuse: different --days -> exit 1 resume_range_mismatch, 0 requests
PASS refuse: different --end-ms -> exit 1 resume_range_mismatch, 0 requests
PASS refuse: staging unchanged after refusals
PASS resume without --end-ms continues the stored range (end from staging) :: 0  used 125
PASS --max-requests 151 refused by the parser :: SystemExit 2
FAILURES: none
```

- **分次與單次逐位元組相同**：「單次」是在離線環境把上限暫時拉到 10,000 才能一次跑完。三個資料集分次重放得到的 4 個檔案（含 `manifest.json`），都與真實資料集及單次結果逐位元組相同。
- **每次在上限內**：每次都停在 144 次（`stop_at = max_requests − FUNDING_RESERVE`，`tools/fetch_okx_candles.py:247`、`:279`），保留 6 次給最後一次的資金費（實際用 4 次：3 頁加 1 個空頁）。
  - 次數分配 144＋125、144＋144＋68、144×3＋101，與計畫文件 `docs/research-real-data-plan.md:677-681` 相同。
  - 總數等於不重試時的最少頁數。重試也會算進 `requests`（`:86`），所以實際採集沒有發生重試。
- **範圍不同時拒絕**：`--days` 或 `--end-ms` 不同時，回 exit 1 `resume_range_mismatch`（`:270`），請求 0 次，staging 不變。
- **staging 不會被當成資料集**：staging 檔在 `data/okx/.staging/<inst>-<bar>.json`（`:251-253`）。`list_datasets` 只掃 `*/*/*/manifest.json`（`catos/research_datasets.py:396`），所以進行中 `list_datasets(root) == ([], [])`；完成後 staging 刪除（`:301`），只看得到正式資料集。
- **節流**：同一次執行內的間隔至少 0.250 秒。跨次執行是新的程序，不共用節流狀態，見 O10。

## F2. 往返統計：PASS（附 O9）

**獨立還原。** `fref.my_trips` 依文件定義從逐筆成交還原往返，全部用 `Fraction` 精確算術：

- 部位離開 0 開新的一筆，回到 0 結束；反手時同一筆成交結束舊的一筆、開新的一筆。
- 手續費依數量拆分：結束部分 |old|／|qty|，開倉部分 |new|／|qty|。
- 資金費依**時間區間**歸屬：開倉時間 < t ≤ 平倉時間。開發者是依事件排序，兩者寫法不同。我也斷言每筆資金費紀錄的 `position`，等於由成交推得的 t 之前部位。

在 15 個 F 變體（4 個週期 × F1 兩種出場、F2）以及 6 個依權益定部位的執行上，逐筆比對開發者的 `round_trips` 與 `trade_stats`（`check_f.py`），節錄：

```text
PASS 1H F1_dc: trips == my exact reconstruction (shape, per-trip realized/fee/funding) :: 413 closed, open False, max per-trip |diff| 0.0e+00, trips with funding 33
PASS 1H F1_dc: win rate, payoff, PF, expectancy, streak, hold, long/short == mine :: win 0.3099 payoff 1.454 pf 0.653 exp -18.800 streak 14 zero-trips 0
PASS 4H tsmom-multi vol_scaling=1: trips == my exact reconstruction ... :: 66 closed, open True, max per-trip |diff| 0.0e+00, trips with funding 2
   4H tsmom-multi vs=1: fills 191, distinct sizes 181, scale-ins 60, reversals 66; dev residual 1.5501…E-45, exact residual 1.550e-45
FAILURES: none
```

- 所有執行的每筆往返，已實現損益、手續費、資金費與我的精確值差 0。
- 勝率、平均賺賠、賺賠比、獲利因子、期望值、最大連虧、平均持倉、多空分開統計，與我的計算相同（比率容許 1e-40，因為開發者在 50 位精度下除）。
- 沒有出現損益剛好為 0 的往返，所以「0 不算勝負」與「0 會中斷連虧」兩條規則在真實資料上沒有被觸發。

**反手拆分。** F1／F2 只在空手時進場，不會反手。所以反手拆分是在 tsmom-multi 上驗的：4H 有 66 次反手，1H 有 19 次，逐筆相同（`catos/research_trades.py:67-77`）。

**資金費順序。** 引擎在同一時刻先結算資金費、後成交（`catos/research.py:361-363`，假設文字 `:188`）。`research_trades.py:53-54` 把資金費排在同時刻的成交之前，與引擎一致。`funding_ties.log` 確認真實資料確實有同時刻的情況：

```text
F3 1H: ... at a fill time with a position 9 (closing fills 8, reversals 1); per-trip funding equal to mine: True
F1 dc 4H: ... at a fill time with a position 33 (closing fills 33, reversals 0); per-trip funding equal to mine: True
tsmom vol 4H: ... at a fill time with a position 7 (closing fills 0, reversals 2); per-trip funding equal to mine: True
```

**對帳殘差與 1e-30 容許值。**

| 執行 | 成交 | 不同張數 | 加碼 | 反手 | 開發者回報的殘差 | 精確殘差 |
| --- | --- | --- | --- | --- | --- | --- |
| 15 個 F 變體（固定 10 張） | 28～1,072 | 1 | 0 | 0 | 0E-19 | 0 |
| 4H tsmom-multi 波動目標 | 191 | 181 | 60 | 66 | 1.5501E-45 | 1.550e-45 |
| 4H donchian-ensemble 波動目標 | 267 | 187 | 113 | 0 | -7.920E-46 | -7.920e-46 |
| 4H tsmom-multi 不縮放 | 193 | 182 | 65 | 66 | 7.735E-46 | 7.735e-46 |
| 1H tsmom-multi 波動目標（預熱 8,808） | 85 | 72 | 32 | 19 | 4.732E-46 | 4.732e-46 |
| 1H donchian-ensemble 波動目標 | 146 | 95 | 54 | 0 | 2.6353E-45 | 2.635e-45 |
| 1H tsmom-multi 不縮放 | 90 | 85 | 37 | 19 | -2.296E-45 | -2.296e-45 |

- 開發者回報的殘差等於我用 `Fraction` 算的精確殘差。殘差來自引擎 50 位精度的累計捨入，例如平均成本除不盡。
- 實際殘差最大 2.6e-45，容許值 1e-30 大了約 15 個數量級。
- 用上限推算，容許值仍然合理：
  - 本金上限 1e9 USDT（`catos/research_catalog.py:383-384`），50 位精度下每次運算的捨入約 1e-41。
  - 就算 60,000 根、數萬次成交全部累計，也遠小於 1e-30。
  - 另一方面，任何真的少算或多算一筆費用、資金費，金額都遠大於 1e-30，會被擋下。
- 補充：總額對帳只能抓到「漏算」，抓不到「費用歸錯往返」，因為總和不變。這部分已由上面的逐筆獨立還原補足。

## F3. 事前登錄規則與 `research_intraday.py` 一致：PASS（附 O2）

我依 `docs/research-real-data-plan.md` 的「工作包 F」量測計畫（`:629-671`）自寫 `fref.MyFade`、`fref.MyPullback`。寫法與開發者不同：

- 先建每個 UTC 日的 H／L／C 與「是否完整」表，D 日的點位只用 D−1 日。
- 點位公式取自文件 `:487-489` 與 `docs/dcm-research-plan.md:44`。

兩邊交給同一個引擎，比對逐筆成交的所有欄位：

```text
PASS 5m F1_opp: dev fills == my document reimplementation (every field) :: 170 fills vs 170; net -1702.07
PASS 5m F1_dc ... 186 vs 186; PASS 5m F2 ... 28 vs 28
PASS 15m F1_opp ... 272 vs 272; PASS 15m F1_dc ... 328 vs 328; PASS 15m F2 ... 50 vs 50
PASS 1H F1_opp ... 630 vs 630; PASS 1H F1_dc ... 826 vs 826; PASS 1H F2 ... 170 vs 170
PASS 4H F1_opp ... 714 vs 714; PASS 4H F1_dc ... 1072 vs 1072; PASS 4H F2 ... 248 vs 248
```

逐條對照文件與程式，並列出真實資料上各分支的實際發生次數（`coverage_f.py`），確認比對有涵蓋這些分支：

| 規則（文件） | 程式 | 真實資料上發生次數（例） |
| --- | --- | --- |
| 點位來源：前一個完整 UTC 日的 H、L、C，不夾值；第一個不完整日與之後一整天不交易 | `research_intraday.py:20-25`、`:46-58`（`complete and self._ended`） | 三份新資料都從 12:00 開始，第一天不完整，路徑有被走到 |
| 同一根跌破並站回（含同一根） | `:90-93` 記錄跌破，`:113-114` 收盤 > DL 或 < DH | 1H F1 對側：多 160、空 143 次 |
| 每天每方向最多一次，只在空手時進場 | `:85-86`、`:113-118`、`:109` | 5m「當天已進過多單」被擋 1,991 次 |
| 多空同時成立不進場 | `:115-116` | 4H F1：4 次、9 次 |
| 失效停損用事件極值（跌破起到進場那根的最低 low），收盤破就出場 | `:91`、`:119` 凍結、`:99` | 5m 有 13 次停損低於進場那根的 low（停損取自更早的跌破） |
| 出場 0：收盤 ≥ 進場日 DH（空單 ≤ DL），點位凍結 | `:101`、`:119` | 4H 119 次 |
| 出場 1：日線收盤破（站上）當天 DC | `:102-104` | 4H 354 次 |
| 停損與出場同一根只出一次 | `:105-107` | 1H 15 次、4H 45 次 |
| F2 發動：日收盤 ≥ 當日 DH；用發動日 H、L、C 凍結點位 | `:162-165` | 4H 227 個發動日 |
| F2 視窗：之後 `window_days`（3）天內，low ≤ 凍結 DC 後收盤 > 凍結 DC | `:142-145`、`:157-160`，視窗終點 `:164-165` | 4H 24 次視窗過期沒進場 |
| F2 每次發動最多進場一次；出場：收盤 < 凍結 DL，或日收盤 < 當天 DC | `:159`、`:150-153` | 4H 凍結 DL 7 次、日線 DC 117 次 |

**文件沒寫明、但程式有固定做法的兩點（O2）**：

1. **持倉中遇到發動日**：程式不登記發動，進場那一根也不登記（`:162-163`，`position == ZERO and decision is None`）。
2. **新發動覆蓋還沒用完的視窗**：程式以最新的發動為準（`:165`）。

我第一版的實作在第 1 點選了和程式相同的做法，所以逐筆相同。照字面另寫「持倉中也登記發動」，結果不同：5m −1,143.91（對 −1,077.70）、15m −433.23（對 −217.26）、1H −2,221.51（對 −892.51）、4H −2,421.04（對 −1,262.60）。都是虧損，結論不變。

## F4. 沒有未來資料：PASS

- 在真實 1H、15m 資料上，F1 兩種出場與 F2 各取 14 個截點：
  - 開頭附近 1 個、結尾 1 個、隨機 6 個。
  - UTC 日界 3 個，以及日界後一根 3 個。
- 每個截點只用前綴 K 線跑一次（資金費也截到前綴範圍），要求三件事都相同：
  - 截點前的成交逐筆相同。
  - 前綴的待成交意圖，等於完整執行在截點那根的成交。
  - 權益曲線前綴相同。

```text
PASS 15m F1_opp: prefix invariance at 14 cut points (incl. day boundaries) :: bad cuts []
PASS 15m F1_dc ... bad cuts []；PASS 15m F2 ... bad cuts []
PASS 1H F1_opp ... bad cuts []；PASS 1H F1_dc ... bad cuts []；PASS 1H F2 ... bad cuts []
```

- 程式結構上，決策只用剛收盤的 K 線（`on_bar` 在 `update_indicators` 之後，`research.py:369-373`），點位只用前一個完整日，引擎在下一根開盤成交。我自寫的實作雖然預先建了日表，但 D 日只讀 D−1 日，與開發者逐筆相同，也是旁證。

## F5. `Delayed` 修正：PASS

- 修正後（`catos/research_robustness.py:61-91`），被包的策略看到的是自己已決定的部位（`believed`，`:85-89`），只有實際成交晚一根。
- 用會讀自身部位的 F1，在 4 個週期驗證「決策時間與成交時間各晚一根、目標部位序列相同」：

```text
PASS 5m F1_opp: Delayed = same targets, decision and fill one bar later :: 170 vs 170 fills; delayed net -1582.98
PASS 15m F1_opp ... 272 vs 272 fills; delayed net -489.37
PASS 1H F1_dc ... 826 vs 826 fills; delayed net -7490.11
PASS 4H F1_dc ... 1071 vs 1072 fills; delayed net -6489.98   （最後一個決策晚一根後落在資料外，未成交）
（F1 兩種出場、F2 在 4 個週期共 12 組全部 PASS）
```

- 舊版（`fix_tree` 的 `research_robustness.py`）重現了文件描述的症狀。F1 在 5m 只成交 1 筆就卡住：策略看到舊部位 0，把自己的交易狀態清掉，之後持倉中也不會出場。4 個週期的兩種出場，延遲結果都完全相同：

```text
   5m: old Delayed F1 exit 0 vs exit 1 identical fills: True
   15m／1H／4H: 同樣 True
```

- 工作包 E 的 6 個變體（4H，預熱 2,202），舊版與新版延遲結果逐筆相同，也與 E 表的「延遲一根」欄相同：

```text
PASS E A_vol: delayed old == fixed (all fills) and == doc +5,854.86
PASS E A_raw ... +11,204.04；PASS E B_vol ... +7,468.31；PASS E B_raw ... +12,925.90
PASS E C_arrow ... +1,701.97；PASS E C_score ... -1,125.98
```

## F6. 量測可重現：PASS（附 O4、O5、O6）

我依「工作包 F」的量測計畫自寫 `measure_f.py`（固定 10 張、taker 0.0005、滑價 2 bps、本金 10,000、預熱 3 天：5m 864、15m 288、1H 72、4H 18；F3 Donchian 5m 288／72、15m 96／24、1H 24／6），重跑 15 個變體：

- 往返統計用我的 `fref`。
- 成本、兩平、買進持有用 payload。
- 成本加倍（fee 0.001、滑價 4）、延遲用引擎重跑。
- DSR／PBO 用開發者函式與 `ref_stats` 各算一次。

| 變體 | 淨損益 | 最大回撤 | 往返 | 勝率 | 賺賠比 | 獲利因子 | 期望值 | 價格損益／成本 | 每邊兩平 | 延遲一根 | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 對側 5m | -1,702.07 | 21.34% | 85 | 11.8% | 4.12 | 0.55 | -20.02 | -865.21／853.86 | -6.96 | -1,582.98 | 不通過 |
| F1 日線 DC 5m | -2,035.26 | 21.73% | 93 | 18.3% | 1.46 | 0.33 | -21.88 | -1,095.28／939.81 | -8.17 | -1,854.44 | 不通過 |
| F2 5m | -1,077.70 | 13.15% | 14 | 21.4% | 0.90 | 0.25 | -76.98 | -922.54／141.07 | -46.53 | -930.53 | 不通過 |
| F3 5m | -1,311.78 | 20.11% | 182 | 28.0% | 2.13 | 0.83 | -7.21 | 538.65／1,852.88 | 2.05 | -1,024.84 | 不通過（限價單） |
| F1 對側 15m | -1,499.99 | 34.74% | 136 | 16.9% | 4.06 | 0.83 | -11.03 | -67.46／1,433.41 | -0.33 | -489.37 | 不通過 |
| F1 日線 DC 15m | -3,444.39 | 36.49% | 164 | 25.0% | 1.50 | 0.50 | -21.00 | -1,693.58／1,743.85 | -6.83 | -2,700.79 | 不通過 |
| F2 15m | -217.26 | 11.49% | 25 | 36.0% | 1.56 | 0.88 | -8.69 | 57.48／261.21 | 1.18 | -91.13 | 不通過 |
| F3 15m | -2,264.59 | 33.75% | 319 | 31.0% | 1.92 | 0.86 | -7.10 | 1,131.98／3,397.57 | 2.34 | -2,161.02 | 不通過（限價單） |
| F1 對側 1H | -4,232.64 | 69.08% | 315 | 22.5% | 2.92 | 0.85 | -13.44 | -828.84／3,408.57 | -1.69 | -2,569.45 | 不通過 |
| F1 日線 DC 1H | -7,764.41 | 80.86% | 413 | 31.0% | 1.45 | 0.65 | -18.80 | -3,189.35／4,594.75 | -4.83 | -7,490.11 | 不通過 |
| F2 1H | -892.51 | 19.55% | 85 | 36.5% | 1.51 | 0.87 | -10.50 | 67.68／945.93 | 0.40 | -1,030.04 | 不通過 |
| F3 1H | -10,293.31 | 104.80% | 771 | 31.6% | 1.69 | 0.78 | -13.35 | -1,629.13／8,665.60 | -1.32 | -11,663.98 | 不通過 |
| F1 對側 4H | -3,940.97 | 51.72% | 357 | 32.2% | 1.87 | 0.89 | -11.04 | -810.44／3,125.16 | -1.83 | -3,008.72 | 不通過 |
| F1 日線 DC 4H | -7,253.47 | 75.36% | 536 | 36.8% | 1.23 | 0.71 | -13.53 | -2,734.18／4,534.50 | -4.20 | -6,489.98 | 不通過 |
| F2 4H | -1,262.60 | 23.79% | 124 | 35.5% | 1.56 | 0.86 | -10.18 | -147.38／1,100.64 | -1.03 | -705.64 | 不通過 |

- **實測表**：上表 15 列、12 欄，與 `docs/research-real-data-plan.md:698-712` **逐格相同**。開發者 payload 的 `trade_stats` 與我的獨立計算也相同。
- **判定**：依事前門檻自己重算，15 個成本加倍後全部虧損、延遲後全部虧損，所以沒有「通過」也沒有「有跡象」。「限價單才可能救」的條件是 taker 下虧損且每邊兩平 > 2 bps，只有 F3 5m（2.05）、F3 15m（2.34）符合，與文件相同。
- **買進持有 10 張（含成本）**：-653.75（-6.54%）、-3,122.85（-31.23%）、+3,750.19（+37.50%）、+672.66（+6.73%），與 `:716` 相同。這是在第二根評估 K 線開盤成交，與工作包 E 同一慣例；如果改在第一根成交，會是 -654.04、-3,120.77、+3,760.96、+607.60。
- **bootstrap**：不為正的比例 0.0260～1.0000，與 `:717` 相同。0.0260 是 F3 1H，見 O5。
- **DSR（N=15）**：用同週期組內的 Sharpe 變異數、N 取 15，最大值 0.0532（F3 1H），與 `:717`「都 ≤ 0.0532」相同。
- **PBO**：組內含 F3，5m 0.7714、15m 0.5000、1H 0.4571、4H 0.6286，開發者函式與 scipy 參考一致，與 `:718` 相同。
- **組內 DSR**：我算出的範圍是 0.0000～0.4976，與 `:718` 的「0.0069～0.1346」不符，見 O4。
- **判讀段落**：
  - 「F1 扣成本前在每個週期都是負的」：8 個 F1 的價格損益都 < 0，成立。
  - 「F2 15m、1H 扣成本前接近打平」「F3 5m、15m 兩平 2.05、2.34 bps」：成立。
  - 「F1 對側目標 1H、4H 多單 +508.94、+803.89，空單 -4,741.59、-4,744.86」：與我的多空分開統計相同。
  - 「對側點位出場的賺賠比 2.9～4.1」不含 4H 的 1.87，見 O6。

## F7. 回測上限與輸出：PASS，附明示風險（O3、O11）

- **上限**：`MAX_BARS` 從 20,000 改為 60,000（`catos/research_catalog.py:149`），5m 6 個月的 52,704 根可以跑。另外，日線預熱上限 `DAILY_WARMUP_LIMIT` 也改成 60,000（`:60`），所以 1H 上日線策略的 8,808 根預熱可以用。
- **15 個變體**：
  - 程序內 `execute_request` 每次 0.41～1.76 秒，文件寫 0.5～1.8 秒。
  - payload（等同 result.json 主體）最大 929,451 bytes（F3 1H），與文件 `:719` 相同。
- **真正受上限約束的是 worker stdout**，內容是 `{"payload", "report"}`（`catos/research_worker.py:54`、`catos/research_service.py:212`）。15 個變體的 stdout 是 893,921～1,514,277 bytes。最重的 3 個用真 worker 子程序跑：

```text
worker subprocess F3 5m: 1.94s, ok, stdout 1,514,277 B (cap 2,000,000 B, 30s)
worker subprocess F3 1H: 1.25s, ok, stdout 1,462,872 B (cap 2,000,000 B, 30s)
worker subprocess F1 opp 5m: 1.78s, ok, stdout 1,458,048 B (cap 2,000,000 B, 30s)
```

  交付範圍內全部在 2 MB 與 30 秒內。

- **風險**（O3）：HTML 報告的 SVG 把每一個權益點都畫出來（`catos/reporting.py:96-100`），5m 6 個月約 640 KB。成交越多，stdout 越大。用高周轉的 Donchian 在 5m 上實測：

```text
Donchian 96/24 on 5m: fills 975, payload 919,655 B, worker stdout 1,690,212 B -> worker ok in 1.96s
Donchian 48/12 on 5m: fills 1786, payload 1,058,516 B, worker stdout 1,930,421 B -> worker ok in 1.95s
Donchian 24/6 on 5m: fills 3302, payload 1,317,151 B, worker stdout 2,372,833 B -> worker ResearchError: research_output_limit in 2.00s
Donchian 12/3 on 5m: fills 5801, payload 1,681,786 B, worker stdout 3,048,737 B -> worker ResearchError: research_output_limit in 1.99s
```

  在 6 個月 5m 上，大約 2,000 筆以上成交（每天 11 筆左右）的策略會回 `research_output_limit`，而且這時 payload 本身仍小於 2 MB。程式註解（`research_catalog.py:147-148`）只提到成交會變多，沒有提到報告 SVG。

- **優化**（O11）：上限放寬也影響優化。5m 上 20 次優化用真 worker 跑 14.1～14.5 秒，15m 9.8 秒，都在 30 秒內，但只剩約一半餘裕；優化沒有計算量預檢，滾動驗證有。

## F8. 前端：PASS（附 O8、O12）

- `npm run typecheck` exit 0。`npm test`：第一次卡住（O12），第 2、3 次都是 `tests 21`、`pass 21`、`fail 0`，`check:tokens OK`。F 沒有新增前端測試，面板改用 SSR 渲染另外核對。
- **SSR 渲染 `TradeStatsPanel`**（`fe_check_f.mjs`，資料是真實 payload）：

```text
   F2 1H panel text: 往返交易統計（扣成本） 85 筆已平倉 勝率 36.47%（31 勝 54 敗） 平均賺／平均賠 +188.60 USDT ／ -124.80 USDT 賺賠比（平均） 1.51 獲利因子 0.87 每筆期望值 -10.50 USDT 最大連虧 5 筆 平均持倉 51.9 小時 最大單筆賺／賠 +769.93 USDT ／ -555.64 USDT 多單 85 筆 · 勝率 36.47% · -892.51 USDT ｜ 空單 0 筆 · 勝率 不適用 · 0.00 USDT ...
PASS F2 1H: win rate 36.47% (31 勝 54 敗), payoff 1.51, PF 0.87, expectancy -10.50 USDT, streak 5, hold 51.9 h
PASS F2 1H: win rate never alone (payoff, PF and expectancy cells in the same panel)
PASS F2 1H: data-win-rate attribute is the payload string
PASS tsmom 4H: open short trip notice with formatted unrealized PnL :: +398.19 USDT
PASS no closed trips: renders "不適用" without throwing
PASS backtest page: panel only when result.trade_stats exists
PASS backtest page: header falls back to "舊紀錄沒有往返統計" when trade_stats is absent
PASS dcm-fade: in catalog; min warm-up 5m 864, 15m 288, 1H 72, 4H 18
PASS dcm-pullback: in catalog; min warm-up 5m 864, 15m 288, 1H 72, 4H 18
FAILURES: none
```

  - 面板上的數字與 payload（以及 F6 表）一致：36.47% = 31／85，1.51、0.87、-10.50。
  - 沒有已平倉往返時（比率全為 null）不會崩潰。
- **舊紀錄（沒有 `trade_stats`）**：`trade_stats` 在型別上是選填（`research-api-adapter.ts:313`）。
  - 面板只在有 `trade_stats` 時渲染（`frontend/cat-os-vite/src/pages/backtest.tsx:607`）。
  - 頂部勝率用 `result?.trade_stats?.win_rate != null` 判斷，舊紀錄顯示「舊紀錄沒有往返統計」（`:571-581`）。
  - 這兩條是程式碼核對加 SSR 子元件，沒有在瀏覽器實際開一筆舊紀錄，見「未涵蓋」。

## F9. 文件與程式一致：PASS（附 O4～O7）

- `README.md:12`、`:15`、`:66`：列出兩個短週期策略、七個研究策略、往返統計、單次 60,000 根、`--resume` 與 `.staging`，與程式相同。
- `docs/research-real-data-plan.md`「工作包 F」：
  - 基礎建設、量測計畫、採集表、實作描述，與程式及重放結果相同。
  - 兩個修正的描述，與 F5 及 F2 的實測相同。
  - 量測數字的摘要句有三處不準：O4（組內 DSR 範圍）、O5（F3 1H 失真沒有標示）、O6（賺賠比範圍）。另有一處沒寫明的規則：O2。
- `docs/next-steps.md:93-105`：內容與程式一致，但狀態仍寫「尚未獨立驗收、未 commit」，見 O7。
- 程式說明：
  - `catos/research_trades.py:1-19` 的對帳說明、`research_intraday.py:1-10` 的模組說明，與實作一致。
  - `research_robustness.py:62-70` 寫明修正日期，並說明「之前讀自身部位的策略的延遲數字受影響」。實測 E 不受影響（F5）。

---

## 實際執行的命令與結果

cwd 為 worktree 根目錄。`PY=C:/Users/user/Desktop/CatOS/.venv/Scripts/python.exe`；`S` 為上述暫存目錄；`P` 為上一輪獨驗會話的暫存目錄 `C:/Users/user/AppData/Local/Temp/claude/27f11abdf19a5896/7cff6b8e-d55e-4336-b6fe-4d18904a1066/scratchpad`（只取 scipy 的 `pkgs` 與 `ref_stats.py`）；`FT=$S/fix_tree`（`git archive 3c78d6fd` 匯出）。

| 命令 | 結果 |
| --- | --- |
| `cp -r <主 checkout 4 個資料夾> data/okx/BTC-USDT-SWAP/<週期>/` 後 `sha256sum` | 12 個檔案都與 manifest 相同 |
| `$PY -B -m unittest discover -s tests`（HEAD） | `Ran 1466 tests in 188.840s`、`OK (skipped=11)` |
| 同上，cwd `$FT` | `Ran 1449 tests in 198.569s`、`OK (skipped=11)` |
| `$PY -B $S/check_fetch.py` | 第一次：同一次執行內的節流檢查被我寫成跨執行比較而 FAIL（跨執行是新程序）；改成分開計算後全部 PASS，`FAILURES: none` |
| `PYTHONPATH=$P/pkgs;$S;. $PY -B $S/check_fix.py $S/prev_fe_requests.json`（cwd `$FT`） | 第一次因 cp950 主控台無法印「≤」中斷；加 `PYTHONIOENCODING=utf-8` 後全部 PASS，`FAILURES: none` |
| `PYTHONPATH=$S;. $PY -B $S/check_f.py $FT` | 第一次因我的前綴切片沒有一併截掉資金費，引擎拒絕（`funding event outside candle coverage`）；修正後全部 PASS，`FAILURES: none`，39.98 秒 |
| `PYTHONPATH=$P/pkgs;$S;. $PY -B $S/measure_f.py $S/measure_f.json $S/svc_scratch` | 15 個變體與 3 次 worker 子程序全部完成，52.0 秒，數字見 F6、F7 |
| `$PY -B $S/dsr_alt.py` | 組內 DSR 範圍、F3 1H 負權益，見 O4、O5 |
| `$PY -B $S/cap_probe.py $S/svc_scratch` | 975／1,786 筆成交 OK；3,302／5,801 筆 `research_output_limit` |
| `$PY -B $S/opt_probe.py $S/svc_scratch` | 第一次因我的 15m 格點違反 exit < entry 被拒；修正後 4 組 OK，另加 Donchian 480～960 一組 14.1 秒 OK |
| `$PY -B $S/coverage_f.py`、資金費同時刻統計 | 見 F3、F2 |
| `npm ci`（`frontend/cat-os-vite`） | exit 0（esbuild postinstall 被 allow-scripts 擋，二進位已在） |
| `npm run typecheck` | exit 0 |
| `timeout 180 npm test` ×3 | 第一次逾時 exit 124（11 個 ✖，O12）；第 2、3 次 exit 0、21／21 |
| `$FT` 前端（junction 共用 node_modules）：`npx tsc --noEmit`、`node scripts/check-tokens.mjs`、`node --test …` ×3 | tsc exit 0、`check:tokens OK`；第一次逾時（O12），第 2、3 次 21／21 |
| `node $S/fe_check_f.mjs <frontend> $S` | 全部 PASS |
| `git ls-tree -r 2f839a36 --name-only \| grep -c '^data/'`、`3c78d6fd` 同 | 0、0 |

## 非阻斷觀察

**O1（修正，措辭）　PBO 粒度提醒在「試驗數夠、但 λ=0 佔比高」時，仍印出「只有 N 組參數」。**

- `catos/research_overfit.py:171-173` 的條件是「N < 10 **或** λ=0 佔比 ≥ 10%」，但文字固定寫「注意：只有 {trials} 組參數、或有 {佔比} 的切法剛好落在中位數」。
- 實測 `verdict(0.7, {"pbo": 0.3, "logit_zero_share": 0.2}, trials=40)` 印出「注意：只有 40 組參數、或有 20% 的切法…」；`trials=4`、佔比 0 時則印「或有 0% 的切法…」。
- 邏輯正確，只是讀者可能誤解。建議依觸發的條件分開寫。

**O2（F，事前登錄缺兩條，建議處理）　F2 在「持倉中遇到發動日」與「新發動覆蓋舊視窗」時的做法，文件沒寫。**

- 程式在持倉中（以及進場那一根）不登記發動（`catos/research_intraday.py:162-163`）；新發動直接取代還沒用完的視窗（`:165`）。
- `docs/research-real-data-plan.md:644-650` 只寫「每次發動最多進場一次」（`:647`）。
- 真實資料上，持倉中遇到發動日的次數：5m 1、15m 7、1H 30、4H 48；覆蓋舊視窗：4、5、21、30 次。
- 照字面「持倉中也登記發動」重寫，淨損益變成 5m −1,143.91、15m −433.23、1H −2,221.51、4H −2,421.04（程式是 −1,077.70、−217.26、−892.51、−1,262.60）。差距不小，但全部虧損，結論不變。
- 建議把這兩點補進文件。如果要改規則，就是新的事前登錄，N 要累計。

**O3（F，輸出上限，建議優先）　真正的 2 MB 上限是 worker stdout（payload 加 HTML 報告），短週期高周轉策略會撞到。**

- 文件 `:719` 量的是 result.json（最大 929,451 bytes）。但 worker 回傳 `{"payload", "report"}`，stdout 上限是 2,000,000 bytes（`research_service.py:212`）。
- HTML 報告的 SVG 把每一個權益點都畫出來（`catos/reporting.py:96-100`），5m 6 個月約 640 KB，payload 則已取樣到 2,000 點。
- 15 個變體的 stdout 最大 1,514,277 bytes（F3 5m），在上限內。高周轉 Donchian 在 5m 上：
  - 1,786 筆成交：1,930,421 bytes，OK。
  - 3,302 筆成交：2,372,833 bytes，`research_output_limit`。
- 使用者要的正是短週期策略，每天 10 筆以上成交的 5m 策略會跑不了。`research_catalog.py:147-148` 的註解只提到成交。
- 建議：報告 SVG 也取樣，或不讓報告計入 stdout 上限。

**O4（F，文件數字）　`docs/research-real-data-plan.md:718`「各週期組內：DSR 0.0069～0.1346」與實算不符。**

- 每個變體在同週期組內（含 F3）的 DSR：

| 週期 | F1 對側 | F1 日線 DC | F2 | F3 |
| --- | --- | --- | --- | --- |
| 5m | 0.0170 | 0.0007 | 0.0069 | 0.0646 |
| 15m | 0.0467 | 0.0003 | 0.1198 | 0.0354 |
| 1H | 0.0163 | 0.0000 | 0.0255 | 0.4976 |
| 4H | 0.1148 | 0.0033 | 0.1346 | — |

- 實際範圍是 0.0000～0.4976。「0.0069～0.1346」剛好是 F2 四個值的範圍。不含 F3 的分組是 0.0003～0.1346，也不是 0.0069。
- PBO 四個數字正確。全部遠低於 0.95，結論不變。

**O5（F，統計失效）　F3 1H 權益跌破 0，它的 Sharpe、bootstrap、DSR 都沒有意義，文件沒有標示。**

- F3 1H 從 2026-07-08 11:00 UTC 起權益 ≤ 0，共 1,314 個權益點；最低 −525.75，期末 −293.31，最大回撤 104.80%。引擎沒有強平模型，這是研究假設。
- 日報酬用權益比值計算，跌破 0 之後會出現 < −1 的日報酬（9 天）與 +25.19 這種值。所以得到：
  - Sharpe +0.760，一個淨虧 10,293 的策略。
  - bootstrap 不為正比例 0.0260，形式上過了門檻 3。
  - 組內 DSR 0.4976。
- 文件 `:717` 引用的「bootstrap 0.026～1.000」下限、「DSR（N=15）都 ≤ 0.0532」的最大值，都來自這個失真。它在門檻 1、2 已經不通過，結論不變。
- 建議：權益 ≤ 0 的執行標成爆倉，不計算比率型統計；文件補註。

**O6（F，文件數字）　`:727`「對側點位出場的賺賠比 2.9～4.1」不含 4H 的 1.87。** 應寫 1.87～4.12，或註明只指 5m～1H。

**O7（F，文件狀態）　`docs/next-steps.md:93` 在 commit 內容裡寫「只有開發者自測，尚未獨立驗收、未 commit」。** 與上一輪 O6 同型；本次驗收後也要更新驗收狀態。

**O8（F，前端）　回測頁頂部列單獨顯示勝率，沒有選取結果時也顯示「舊紀錄沒有往返統計」。**

- 文件 `:689` 說勝率「不單獨顯示」。往返統計面板確實如此，但頂部指標列（`backtest.tsx:571-584`）只有勝率與「勝場／往返筆數」，賺賠比等只在 tooltip 的 notice 文字與下方面板。
- 還沒有任何結果（`result` 為 null）時，條件會落到「舊紀錄沒有往返統計」（`:581`），其他欄位則顯示「--」。
- 小細節：`average_hold_hours` 為 null 時顯示「不適用 小時」（`trade-stats-panel.tsx:34`）。

**O9（F，輸出格式）　部分 `trade_stats` 欄位帶著 120 位精度的長字串。**

- 例如 `rounding_residual` 的 `"1.55010000000000000000000000000000000000000000000000000000000000000000000E-45"`，以及 `open_trip.net_pnl_with_unrealized` 的 `"398.190101712376074774431000…"`，後面有上百個 0。
- 前端格式化後顯示正常（+398.19 USDT），只是 JSON 變大、人工閱讀不便。

**O10（F，抓取工具邊界情況）　不影響已授權的採集。**

- `--max-requests` ≤ 6 時，`stop_at` ≤ 0，每次執行都回 exit 3 但沒有任何進度。實測三次是 `[(3, 0, 1), (3, 0, 0), (3, 0, 0)]`。
- 最後一次如果在資金費階段失敗（例如資金費超過 5 頁），這次抓到的 K 線不會存回 staging。下次從舊的游標重來，會重複同樣的失敗。
- staging 檔直接覆寫（`tools/fetch_okx_candles.py:285`），不是原子寫入。中斷時可能留下壞檔，下次會回 exit 1，要手動刪除。
- 跨次執行不共用 0.25 秒節流：每次是新程序，第一個請求不等上一次。程序啟動本身就有延遲，實務上影響很小。

**O11（F，效能餘裕）　上限放寬到 60,000 根後，5m 的 20 次優化只剩約一半逾時餘裕。**

- 用真 worker 實測，5m Donchian 20 次 14.1～14.5 秒，15m 9.8 秒，逾時是 30 秒（本機 i7-14700）。
- 滾動驗證有計算量預檢（`MAX_VALIDATION_BAR_EVALUATIONS`），優化沒有。在較慢的筆電上可能逾時。

**O12（環境）　`npm ci` 後第一次 `node --test` 卡住。**

- HEAD 與修正樹各發生一次，與前兩輪驗收的 O7 相同。11 個 state_adapter 測試顯示 ✖ 後等到逾時。
- 我用 `timeout` 包住，結束後沒有程序或埠殘留，留下被中斷的 `node_modules/.vite/deps_temp_f2e0a28e`。之後每次都在 1～2 秒內 21／21。
- 測試基礎設施不在本次差異內。

## 未涵蓋

- **每次實際採集的請求數**：manifest 只記總數（269／356／533）。我用離線重放證明，現行程式在這三個範圍必然是 144＋125、144＋144＋68、144×3＋101，總數與 manifest 相同、沒有重試。但沒有實際採集時的執行紀錄可以逐次核對。
- **授權與採集的先後**：AGENTS.md:29 的條文與資料都在 2026-11-07（資料 20:34～20:38 +08 抓取），條文是隨 `2f839a36` 一起 commit 的。使用者同意的對話我看不到，無法從 git 證明「先授權、後抓取」。
- **事前登錄的時間先後**：量測計畫、規則與量測結果在同一筆 commit，無法從 git 歷史證明「先寫規則、後跑結果」。只能確認文件文字與程式逐筆一致（F3），以及 O2 的兩點未寫明。
- **規則與使用者校準原意的忠實度**：我只核對「計畫文件 ↔ 程式」。F1 的失效停損，文件自己註明不是使用者原話（`:638`）。觸價進場、週成本／月成本沒有實作（`:736-737`）。
- **瀏覽器實測**（選做）：沒有起研究服務與 Vite 代理，沒有在瀏覽器開回測頁。改用 typecheck、既有前端測試、真實 payload 的 SSR 渲染，以及頁面條件的程式碼核對。舊紀錄在整頁上的實際顯示、版面與互動沒有重驗，視覺由使用者自行在網頁驗收。
- **研究服務 HTTP 路徑**：輸出上限與逾時用 `ResearchService._compute` 起真 worker 子程序驗證，沒有經 HTTP 端點、`result.json` 落檔與 `status.json` 流程。
- **短週期策略的優化與滾動驗證**：只做了 F7 的優化逾時探測。兩個短週期策略在優化頁、滾動驗證頁的前端預設請求沒有逐一跑過，catalog 與最小預熱已核對。
- **其他合約、週期**：不在本包範圍，沒有觸發。
