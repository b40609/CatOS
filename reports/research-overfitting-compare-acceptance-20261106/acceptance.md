# 工作包 D（過擬合防護）與 E（預先登錄三策略比較）獨立驗收報告

- 日期：2026-11-06（Asia/Taipei）
- 驗收者：Claude Opus 5.5，獨立驗收會話。沒有參與 D、E 的開發，也沒有撰寫任何 commit，具 AGENTS.md「DEVELOPMENT WORKFLOW」所定的獨驗資格。
- 範圍：分支 `feat/research-overfitting` 的兩筆 commit，分開下結論。
  - **D**：`fb11e321`，對照 `18370fab`（19 個檔案，+1052／−18，其中 357 行是收入 repo 的 B＋A 驗收報告）。
  - **E**：`98316e41`，對照 `fb11e321`（24 個檔案，+1096／−49）。
  - 驗收在 worktree `C:\Users\user\Desktop\CatOS\.claude\worktrees\acceptance-overfit-compare-b5cce7`（分支 `claude/acceptance-overfit-compare-b5cce7`，HEAD 即 `98316e41`）進行。D 用 `git archive fb11e321` 匯出到暫存目錄 `d_tree\` 另外驗。
- 結論：
  - **D：PASS（4／4）**
  - **E：PASS（7／7）**
  - 兩包都沒有阻斷缺陷。另有 7 項非阻斷觀察（O1～O7），其中 **O1（PBO 判讀不穩健）建議優先處理**。
  - 依指示不 commit、不 push、不 merge。
- 自寫腳本與完整輸出在本會話暫存目錄 `C:\Users\user\AppData\Local\Temp\claude\27f11abdf19a5896\7cff6b8e-d55e-4336-b6fe-4d18904a1066\scratchpad\`，不在 repo，會話結束後可能被清掉；關鍵輸出已抄進本報告。
  - Python 腳本：`check_overfit.py`、`check_pbo_ties.py`、`ref_stats.py`、`measure_d.py`、`measure_d_onresult.py`、`check_o1.py`、`check_e_rules.py`、`measure_e.py`、`check_e_api.py`。
  - 前端腳本：`fe_check.mjs`。
  - 輸出：同名 `.log`、`measure_e.json`、`catalog.json`、`fe_requests.json`、`opt_tsmom.json`。

## 驗收限制與隔離

- **沒有連網採集**：沒有對 OKX 發請求，也沒有重新抓取資料。上網只做兩件事：查 PBO 原始論文與 R 套件 `pbo` 的定義，以及用 pip 下載 scipy、pypdf。
- **資料集**：4H 資料集從主 checkout `C:\Users\user\Desktop\CatOS\data\okx\BTC-USDT-SWAP\4H\okx-btc-usdt-swap-4h-20211106-20261106\` **複製**到 worktree 與 `d_tree\` 的同一路徑（git 忽略，`.gitignore:29:/data/`）。複製後 sha256 與 manifest 相符：candles `5a702ece…`、funding `76d6e4e1…`、instrument `248697dd…`。
- **參考實作**：scipy 1.18.1 以 `pip install --no-deps --target <暫存>\pkgs` 安裝，沿用 venv 的 numpy 2.5.4，沒有裝進專案 venv。pypdf 裝在 `<暫存>\pdfpkgs`，只用來擷取論文文字。
- **沒有修改**程式、測試或文件，只新增本報告。沒有 commit、push、merge、切換分支或 stash。
- **沒有啟動任何 HTTP 服務**，也沒有碰 8770／8771。
  - 前端驗證用 `tsc`、`node --test`，以及 Vite middleware 模式的 SSR 渲染（`ws: false`、不開埠）。
  - 結束時 18870／18872／18890／18892／24678／8770／8771 都沒有監聽。
- **環境**：`catos` 匯入路徑都有印出確認，HEAD 指向 worktree，D 指向 `d_tree\catos`。venv 的 Python 3.14.6、optuna 4.9.0；Node v26.4.0。
- **自己啟動的程序**：`npm ci` 後第一次 `node --test` 卡住（HEAD、D 樹各一次，見 O7）。我核對父程序鏈與 esbuild 路徑都屬本 worktree 後，結束了這幾組自己啟動的程序。
- **暫存 junction**：D 樹前端共用 worktree 的 `node_modules`，用的是 junction。驗完已用 `rmdir` 移除，只移除連結，worktree 的 `node_modules` 仍在。
- **執行後 worktree 只多了 git 忽略的產物**，依指示沒有刪除：
  - `data/`
  - `frontend/cat-os-vite/node_modules/`，含一個被中斷的 `.vite/deps_temp_c5820366`
  - 測試自己寫的 `outputs/workspace-w6-fixture-test-bd99e3d0…`、`outputs/workspace-w8-fixture-test-bae8df91…`
  - 本報告（`.gitignore:47:/reports/*`，要收進 repo 需 `git add -f`）
  - `git status --short` 乾淨，HEAD 仍是 `98316e41`。

## 總表

### D（`fb11e321`）：PASS（4／4）

| # | 項目 | 結果 |
| --- | --- | --- |
| D1 | DSR／PSR／PBO 公式（獨立實作與原論文核對） | PASS（判讀穩健性見 O1） |
| D2 | `on_result` 語意、`distinct_trials`、`selection_edges` | PASS |
| D3 | O1 窗尾資金費修正（真實資料），O2～O6 文件與前端修正 | PASS（文件狀態見 O6） |
| D4 | 「工作包 D」實測表重現 | PASS（只在 D commit 可重現，見 O2） |

### E（`98316e41`）：PASS（7／7）

| # | 項目 | 結果 |
| --- | --- | --- |
| E1 | 事前登錄的規則與 `research_daily.py` 一致 | PASS（依文件自寫重實作，6 變體逐筆成交相同） |
| E2 | 沒有未來資料（決策時點、DCM 點位、首日捨棄、前綴不變） | PASS |
| E3 | 登錄與邊界（只供研究、manifest、預熱、合約規格、1 倍名目、TPE／窮舉） | PASS |
| E4 | `research_robustness.py`（逐年、延遲一根、bootstrap） | PASS |
| E5 | 量測可重現（6 變體、逐年、相關係數、多重試驗） | PASS（N=29 算法未寫明，見 O3） |
| E6 | 前端（typecheck、測試、三頁選策略、預熱 2,202、張數上限與 1 倍名目） | PASS（0／1 開關的邊界警示見 O4，環境見 O7） |
| E7 | 文件與程式一致、「展示候選」照事前門檻判定 | PASS（過時敘述見 O5、O6） |

### 共同

- 後端全套測試：
  - HEAD：`Ran 1447 tests in 173.256s`、`OK (skipped=11)`
  - D 樹：`Ran 1430 tests in 183.283s`、`OK (skipped=11)`
  - 兩者都與開發者自測數字相同。
- 前端：
  - HEAD：typecheck exit 0，`npm test` 21／21。
  - D 樹：typecheck exit 0，`node --test` 19／19，`check:tokens OK`。
- 資料沒有進 git：`git ls-tree -r 98316e41 --name-only | grep -c '^data/'` → 0；兩筆 commit 的 `--stat` 都沒有 `data/okx` 或 `.csv`。

---

## D1. DSR／PSR／PBO 公式：PASS（附 O1）

程式：`catos/research_overfit.py`（D、E 之間沒有改動）。

**對照原文。** 以 pypdf 擷取 eScholarship 上的論文修訂版（2015-02-27，LBNL）CSCV 段落，原文定義如下：

- 相對排名 `ω̄c := r̄cn*/(N + 1) ∈ (0, 1)`。
- `λc = ln(ω̄c/(1−ω̄c))`。
- `φ = ∫ 從 −∞ 到 0 的 f(λ)dλ`，且「λc > 0 即樣本內冠軍在樣本外勝過多數」。

程式逐項對照：

- 相對排名用平均名次除以 (N+1)（:130）。
- logit 在 :131。
- PBO 計 λ ≤ 0 的比例（:136）。
- 樣本內冠軍並列時取最小索引（:129）。
- 區塊不能整除時捨棄開頭 `len % 8` 根（:122）。
- PSR／DSR 分母是 `1 − γ3·SR + (γ4−1)/4·SR²`，γ4 為非超額峰態（:86、:67），乘 √(T−1)（:89）。
- 純運氣最大 Sharpe 的期望值是 `√V·((1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(Ne)))`（:80-81）。

以上都與 Bailey & López de Prado 2014（DSR）、Bailey 等 2017（CSCV）一致。

> 註：R 套件 `pbo` 的分母用 N（`omega_bar_c <- os_rank / length(r_bar)`），與原文的 N+1 不同。開發者依原文用 N+1，λ ≤ 0 的計數慣例則與 R `pbo`、fynance 相同。

**獨立核對。** 我在 `ref_stats.py`、`check_overfit.py` 用 scipy／numpy 自寫參考實作，不呼叫開發者函式：

- 動差用 `scipy.stats.skew(bias=True)`、`kurtosis(fisher=False)`。
- PBO 由 T×N 矩陣切 8 塊、70 種組合，排名用 `scipy.stats.rankdata('average')`。

`check_overfit.py` 的輸出：

```text
   published example: SR0 dev=0.113172 ref=0.113172 (paper 0.1132)
PASS example SR0 dev == ref
PASS example SR0 rounds to paper 0.1132 :: 0.113172
   published example: DSR dev=0.900397 ref=0.900397 (paper 0.9004)
PASS example DSR dev == ref
PASS example DSR within 0.001 of paper 0.9004 :: 0.900397
PASS N=100 var=1 expected max == 2.5306 :: 2.530603
PASS kurtosis is non-excess (~3 for normal) :: 3.0045
PASS negative skew lowers PSR (sign of g3 term)
PASS fat tails lower PSR (g4-1)/4 term
PASS moments/sharpe == scipy (12 random series, 4 shapes) :: max rel diff 9.89e-16
PASS search_report DSR/PSR/SR0/variance == reference within output rounding (10 random sets) :: 10/10, max |dDSR| 4.0e-05
FAIL pbo_cscv == reference CSCV (14 random sets: noise, edge, ties, coarse) :: 10/14
PASS pbo_cscv returns None below 50 bars per block
PASS pbo_cscv offset drops the first len%8 bars
PASS dominant candidate -> PBO 0
```

- **論文算例**：2014 年論文的數值例子是 N=100、T=1250、年化 SR 2.5、試驗間變異數 0.5、偏態 −3、峰態 10。開發者函式與我的實作都得到 SR0 0.113172、DSR 0.900397，論文是 0.1132／0.9004。
- **PBO 的 4 個不符**：都出現在我**刻意**把報酬四捨五入到 0.01／0.001 格點、製造大量並列的案例。`check_pbo_ties.py` 改用 `fractions.Fraction` 精確算術重算：

```text
case  3 N=29 T=1750: exact pbo=0.4714 ... | dev pbo=0.4857 ... | numpy pbo=0.4857 ...
case 11 N=15 T=896: exact pbo=0.6000 ... | dev pbo=0.6429 ... | numpy pbo=0.6286 ...
continuous data: dev == exact-arithmetic CSCV in 20/20 cases
```

  - 在格點化資料上，開發者的浮點加總與我的 numpy 加總**都**和精確算術不同。這是浮點加總順序影響並列判定，不是公式差異。
  - 連續資料 20／20 與精確算術完全相同。
  - 真實研究資料只有在兩組參數報酬序列完全相同時才會並列；這時兩邊的運算順序相同，並列判定一致。
  - 所以不列為缺陷。
- **真實資料**：D 的兩次優化與合併 N=16，以 scipy 參考實作獨立重算，結果完全相同，見 D4。

**慣例差異。** 每根 Sharpe 用樣本標準差（ddof=1），偏態、峰態用母體動差，試驗間變異數用 ddof=1。原文沒有規定，這是常見做法，影響在小數第 4 位以下。

## D2. `on_result`、`distinct_trials`、`selection_edges`：PASS

**讀碼：**

- `optimize()` 在 COMPLETE 分支記錄後才呼叫 `on_result`（`fb11e321:catos/optimization.py:182-183`；HEAD :203）。FAIL 分支在 `except` 內 `continue`，不會呼叫。
- `execute_optimization` 以 `candidates.setdefault(params, run)` 只保留每組參數第一次的結果（`fb11e321:catos/research_optimization.py:36-38`），再交給 `search_report`（:59）。
- 滾動驗證以 `trials[selected_trial_number]` 取選定參數（`fb11e321:catos/research_validation_job.py:314-318`）。`research_validation.py` 的 trial 編號就是串列索引（:239），這個取法成立。

`measure_d_onresult.py` 在 D 樹與 HEAD 各跑一次（真實資料前 3,000 根，`entry_bars == 192` 時故意拋錯）：

```text
   states: 15 COMPLETE, 5 FAIL; callbacks 15
PASS optimize: injected failures recorded as FAIL
PASS on_result called once per COMPLETE trial, in order, never for FAIL
PASS on_result receives that trial's BacktestResult
PASS no callback -> identical trials and best
PASS callback exception propagates and aborts the search
```

`distinct_trials` 與 `selection_edges` 在真實資料上的檢查，摘自 `measure_d.py`：

```text
PASS opt orig overfitting.distinct_trials == distinct COMPLETE params :: 9 vs 9
PASS opt wide overfitting.distinct_trials == distinct COMPLETE params :: 10 vs 10
PASS wf orig selection_edges params == independent recount :: {'entry_bars': {'at_low': 0, 'at_high': 5}, 'exit_bars': {'at_low': 3, 'at_high': 1}}
PASS wf orig windows_at_edge == independent :: 5
PASS wf wide selection_edges params == independent recount :: {'entry_bars': {'at_low': 0, 'at_high': 2}, 'exit_bars': {'at_low': 3, 'at_high': 0}}
PASS wf wide windows_at_edge == independent :: 4
PASS opt orig/wide report has overfitting table；wf orig/wide report has edges table
```

## D3. O1 窗尾資金費修正，以及 O2～O6：PASS（附 O6）

**O1 程式。** `_scenario` 在 `last < uncovered_end_ms`、`last` 落在 8 小時格點、且資料有該時刻開盤價時，把窗尾時刻 T 加進結算時點（`fb11e321:catos/research_costs.py:77-86`；HEAD :80-86）。

**O1 在真實 4H 資料上的核對（`check_o1.py`，D 樹）。** 逐窗以 `research_validation._window_inputs` 的切片規則（`bars[start−warmup : end]`，事件取 `first ≤ t ≤ T`）重跑選定參數。另外自建「評估起點到 T、早於真實資金費起點」的每 8 小時 0.01% 事件，連同真實事件一起交給引擎，比較多出的資金費：

```text
== ba_plan (train 2000, ends off-grid): total assumed 29.7782004 events 3500
PASS    w0..w6 scenario == engine :: events 500 vs 500 (每窗)
== train 2001 (all ends on grid): total assumed 29.7514351 events 3507
PASS    w1 T=1699315200000 on_grid=True pos@end=1: scenario == engine :: events 501 vs 501; paid 2.5630190 vs 2.5630190
PASS    w6 T=1771315200000 on_grid=True pos@end=-1: scenario == engine :: events 501 vs 501; paid -10.5950528 vs -10.5950528
（其餘 5 窗同樣 501 對 501、金額相同）
== train 2001, test 1224 (last window crosses real funding start): total assumed 31.6940273 events 4008
PASS    w6 T=1793894400000 on_grid=True pos@end=0: scenario == engine :: events 330 vs 330; paid 2.7687346 vs 2.7687346000000000000
（w0～w5 同樣 613 對 613、金額相同）
FAILURES: none
```

- 窗尾落在格點、窗尾有部位（w1 多 1 張、w6 空 1 張）時，假設情境現在與引擎完全相等。B＋A 驗收時是 500 對 501。
- 窗尾不在格點時（B＋A 原計畫）合計仍是 **29.7782004**，與 B＋A 文件相同，修正沒有改變既有數字。
- 最後一窗跨進真實資金費期間時，假設情境只算到真實起點，T 時刻的真實事件兩邊都算，沒有重複。
- 每窗的 plain 重跑淨損益都等於 payload 的 OOS 淨損益。

**O2～O6：**

| 觀察 | 位置 | 結果 |
| --- | --- | --- |
| O2 | `docs/research-real-data-plan.md:301` | 已寫明「Optuna TPE，n_trials 20」「TPE 不是窮舉：SMA 7／7、Donchian 9／12，缺 96/48、288/24、384/72」。D4 也重現了同樣的缺點（`untried: [(96, 48), (288, 24), (384, 72)]`）。 |
| O3 | `docs/research-real-data-plan.md:307` | 已改為「第一根開盤 61,112.7、收盤 60,777.5」，與 CSV 第一列相同。 |
| O4 | `docs/research-real-data-plan.md:327` | 已改為 41.29。 |
| O5 | `docs/next-steps.md:24`、`:29`；`docs/research-real-data-plan.md:254`；`AGENTS.md:28` | B＋A 狀態已改為 commit `18370fab`、驗收 PASS；「選定的 entry 都在格點上限」已修正；方案標題已改為「使用者選定 B＋A」，`AGENTS.md:28` 的引用同步更新。但 D 新增的第 6 項又寫「未 commit」，見 O6。 |
| O6 | `cost-breakdown-panel.tsx`；`pages/optimization.tsx`、`pages/validation.tsx` | 新增 `emptyText`，預設仍是舊紀錄文字。優化頁在 `best_costs === null` 時、滾動驗證頁在 `costs.total === null` 時改用新文案；欄位不存在（舊紀錄）時仍顯示舊文案。SSR 渲染核對見 E6（`PASS O6: legacy text by default, specific text when given`）。 |

## D4. 「工作包 D」實測表重現：PASS（附 O2）

依 `docs/research-real-data-plan.md:374-383` 的量測計畫自寫 `measure_d.py`，在 **D 樹**直接呼叫 `execute_optimization`／`execute_validation`。被搜尋參數的佔位值用格點下限；滾動驗證 `max_candidates` 20、`max_runs` 100。另以暴力法跑完整格點，並用 scipy 參考實作重算。

| | 原範圍（本次／文件） | 放寬範圍（本次／文件） |
| --- | --- | --- |
| N（TPE，20 trials） | 9／9 | 10／10 |
| 最佳參數／全期報酬 | 384/48，+6.6697%／+6.67% | 384/48，+6.6697%／+6.67% |
| 最佳 Sharpe（年化） | 0.751／0.751 | 0.751／0.751 |
| 純運氣最大 Sharpe（年化） | 0.515／0.515 | 0.393／0.393 |
| PSR／DSR | 0.9458／0.6932（相同） | 0.9458／0.7781（相同） |
| PBO | 0.2714／0.2714 | 0.1000／0.1000 |
| 優化／驗證耗時 | 3.16／2.57 秒（文件 3.01／2.48） | 3.34／3.06 秒（文件 2.88／2.85） |
| 各窗選定 entry | 384 ×5（exit 24、24、24、48、72） | 576、384、576、960、960 |
| 邊界視窗 | 5／5 | 4／5（entry 上限 2、exit 下限 3） |
| OOS 合計：價格／淨損益 | +225.0860000／+208.5582785 | +211.2860000／+197.2734355 |
| 成交／每邊兩平 | 36／95.43 bps | 29／105.66 bps |
| 同期買進持有 | +671.776 | +671.776 |

- OOS 起訖是 1678795200000 → 1765195200000，也就是 2023-03-14 12:00 到 2025-12-08 12:00 UTC，與文件相同。
- 兩邊最佳 384/48 都是暴力法的格點最大值。
- scipy 參考實作的 DSR、PSR、PBO、年化 Sharpe、偏態 0.203、非超額峰態 35.119，兩次優化都完全相同。
- 合併 N=16：`merged: N 16 DSR 0.7083 PBO 0.2000 | mine N 16 DSR 0.7083 PBO 0.2000`，與文件相同。16 組是兩次 TPE 實際評估過的參數聯集。
- 耗時略慢於文件，量級一致；耗時不是驗收門檻。
- 這張表只能在 `fb11e321` 重現：E 起研究優化改成窮舉，同一請求在 HEAD 的結果不同，見 O2。

---

## E1. 事前登錄規則與程式一致：PASS

**做法。** 我只依 `docs/research-real-data-plan.md:449-490` 的文字，自寫三個策略 `MyEnsemble`、`MyTSMOM`、`MyDCM`，以及自己的 UTC 日聚合 `MyDays`（`check_e_rules.py`，不 import `research_daily`）。在真實 4H 資料上用同一引擎、預熱 2,202、手續費 0.0005、滑價 2 bps、本金 10,000，與 `research_daily.py` 逐筆比較成交的時間、決策時間、張數、價格、成交後部位，以及完整 `Performance`：

```text
PASS A_vol: written-rule re-implementation == research_daily, fill by fill :: 267 fills, net 5845.77
PASS A_raw: written-rule re-implementation == research_daily, fill by fill :: 275 fills, net 11493.43
PASS B_vol: written-rule re-implementation == research_daily, fill by fill :: 191 fills, net 8071.93
PASS B_raw: written-rule re-implementation == research_daily, fill by fill :: 193 fills, net 13291.80
PASS C_arrow: written-rule re-implementation == research_daily, fill by fill :: 166 fills, net -1771.90
PASS C_score: written-rule re-implementation == research_daily, fill by fill :: 187 fills, net -1937.55
```

**逐條讀碼對照**（文件 → `catos/research_daily.py`）：

| 規則 | 程式 | 一致 |
| --- | --- | --- |
| UTC 日聚合，高低取極值、收盤取最後一根，第一個不完整日捨棄 | `_Days.push` :38-56 | 是。日開盤沒有儲存，三個策略都沒用到。 |
| 只在當日最後一根 4H 收盤決策，下一根開盤成交 | :50（收在 00:00 才回 True），引擎 `research.py` 的 pending 機制 | 是 |
| A 子模型 N = 5、10、20、30、60、90、150、250、360 | :84 | 是 |
| A 空手時：收盤 > 前 N 日（不含當日）最高收盤就進場；停損 = 含當日 N 日高低收盤中點 | :109-117 | 是 |
| A 持倉時：收盤 < 前一日停損就出場；否則停損取前一日停損與當日中點的較高者 | :111-115 | 是 |
| 權重 = 持倉子模型數 ÷ 9 | :132 | 是 |
| σ = 最近 90 個日報酬樣本標準差 × √365；槓桿 min(2, 25% ÷ σ) | :119-127 | 是 |
| 再平衡：目標 0 就出場、空手就進場、其餘差距 > 20% 才調整 | `_rebalance` :70-76 | 是。嚴格大於；反手時差距必大於 20%，與文件等價。 |
| B 的 k = 30、91、365，取正負號（0 記 0）後平均 | :180 | 是 |
| B 的 EWMA：λ = 60/61，以前 60 個日報酬樣本變異數起始，年化 × 365 | :146、:161-168、:173 | 是 |
| C 的點位：前一完整日 H、L、C；DC = (H+L+C)/3、TC = (9H+9L+10C)/28、DH／DL = TC ± 0.8065(H−L)，不夾值 | `dcm_levels` :185-190、:240 | 是。也與既有 `catos/dcm.py:90-99` 的不夾值版相同。 |
| C 箭頭：收盤 ≥ DH 做多、< DL 做空、其餘維持 | :242-245、:252 | 是 |
| C 評分 = 50 + 月線斜率分 + 位置分 + 趨勢分，門檻 ≥60／≤40，反向觸發被擋就空手 | `ma_slope_score` :193-202、`score` :222-233、:246-251 | 是 |
| 張數向零取整到 lotSz 0.01，小於 minSz 0.01 為 0，上限 ±quantity | `_contracts` :62-67 | 是。成交部位全在 0.01 格點上，A 只做多，C 只有 −10／0／10。 |

**文件沒寫明、但程式採自然解讀的細節**（我的重實作也採相同解讀，結果一致）：

- 名目換算張數用的價格是決策日收盤（:133、:181）。
- 各子模型在預熱期間一有足夠天數就開始累積狀態。

**無法核實：**

- 「規則在任何真實資料執行前寫好」：規則、程式與量測結果都在同一筆 commit `98316e41`，git 歷史無法證明時間先後。
- 原 Pine DCM 指標的評分原文不在 repo，只能核對「文件 ↔ 程式」。
- 文獻參數（Zarattini 等 2025、Hurst／Ooi／Pedersen 2017 等）是否忠實轉錄，不在本次範圍，沒有查證。

## E2. 沒有未來資料：PASS

`check_e_rules.py`：

```text
PASS daily H/L/C from raw CSV == dev _Days for every complete day :: 1825 days
PASS first partial day (2021-11-06, starts 04:00) is dropped; first day 2021-11-07
PASS every day-closing bar closes at 00:00 UTC
PASS data starting 08:00: that partial day dropped, next full day kept
PASS <每個變體>: every decision at a 00:00 UTC close and filled at the next open
   prefix cut at bar 5000 (2024-02-17 08:00) checked for 6 variants
   prefix cut at bar 7500 (2025-04-09 00:00) checked for 6 variants
   prefix cut at bar 9000 (2025-12-15 00:00) checked for 6 variants
   prefix cut at bar 10389 (2026-08-03 12:00) checked for 6 variants
   prefix cut at bar 10700 (2026-09-24 08:00) checked for 6 variants
PASS prefix invariance: truncated runs reproduce the full run's earlier fills and equity (5 cuts x 6 variants)
```

- **日聚合**：以 `csv` 直接讀原始 `candles.csv` 自建 1,825 個完整日，與開發者 `_Days` 逐日完全相同。資料從 04:00 開始，第一天被捨棄；人工把起點改成 08:00 也會捨棄當天。
- **決策時點**：6 個變體每筆成交的 `decision_time_ms` 都是 00:00 UTC 整點，成交時間等於決策時間，即下一根開盤。
- **DCM 點位只用前一完整日**：`on_bar` 用 `days[-2]` 算當日點位、`days[-3]` 算昨日點位（:240-241）；E1 的獨立實作同樣這樣寫，逐筆成交相同。
- **前綴不變性**：截斷點有 5 個，涵蓋：
  - 非日界（08:00）
  - 日界（00:00）
  - 真實資金費起點前一根（2026-08-03 12:00）
  - 資金費期間內（2026-09-24）

  截斷資料的資金費事件只保留到最後收盤。6 個變體截斷後的成交序列都等於全量結果中同期間的成交，權益曲線前綴也逐點相同；vol_target 版的張數取決於權益，同樣成立。

## E3. 登錄與邊界：PASS

`check_e_api.py` 第一階段：

```text
PASS worker strategy_registry.resolve(donchian-ensemble|tsmom-multi|dcm-daily) fails :: RegistryError: unknown_strategy
PASS <三者> manifest lives in research_only_artifacts
   worker manifests: [('sma-trend', 'sma-parameters-v1')]
PASS research_daily.py source hash == DAILY_SHA256 == each manifest sha256 :: 8f59036ce64615f3b2ebab0ecedf56e4808fa073f07f2153cc90ed970805dc85
PASS <三者> manifest validates (approved, entry catos.research_daily:...)
PASS RUNTIME_FILES has research_daily.py and the 3 manifests
PASS research_robustness.py is not wired into the API (doc: measurement script only)
PASS <三者>: warmup 2201 rejected :: ValueError: warmup_bars: at least 2202 bars (367 days) required
PASS <三者>: warmup 2202 accepted
PASS <三者>: synthetic 15m fixture rejected (needs 35232 bars)
PASS donchian-ensemble / tsmom-multi: factory without contract refused :: ValueError: contract_required_for_vol_target
PASS donchian-ensemble / tsmom-multi: strategy receives the dataset contract spec and quantity as cap :: ContractSpec(inst_id='BTC-USDT-SWAP', base_per_contract=Decimal('0.01'), tick_size=Decimal('0.1'), lot_size=Decimal('0.01'), min_size=Decimal('0.01'))
PASS dcm-daily: fixed quantity 10, no contract needed
PASS research optimize, 12-point grid with 20 trials: sampler exhaustive_grid, 12 distinct, numbered 0..11 :: 1.78s
PASS exhaustive best = brute-force max 384/48 (+6.67%) :: {'entry_bars': 384, 'exit_bars': 48} 6.669732 DSR 0.7126 PBO 0.4571
PASS research optimize, 15-point grid with 10 trials: falls back to TPE
PASS tsmom-multi optimize: exhaustive 2 points, N=2 :: 0.58s best {'vol_scaling': 0}
PASS tsmom-multi best_costs: buy-hold is 1x initial notional (1000 USDT -> 4.96 contracts) and scenario says approximate :: 4.96
PASS buy_hold_quantity(vol_target) = floor(10000 / (first open x 0.01)) on 0.01 lot = 49.62 :: first open 20151.9, raw 49.62311246085977004649685638
```

- **manifest 雜湊**：我依 `files_hash` 的格式自行計算 `sha256(json [["catos/research_daily.py", sha256(檔案)]])`，與 `DAILY_SHA256`（`catos/research_catalog.py:55`）及三份 manifest 的 `sha256` 相同。
- **預熱檢查**：`min_warmup_days` 由 `catos/research_catalog.py:356-358` 檢查。
- **合約規格**：vol_target 策略由 `registered_factory` 交入合約規格（:517-531）；回測、優化、滾動驗證三條路徑都傳 `config.contract`。
- **買進持有**：`buy_hold_quantity` 對 vol_target 策略用期初 1 倍名目（:542-550）。
- **TPE／窮舉**：
  - 通用 `optimize()` 的 `exhaustive_small_grid` 預設 False（`catos/optimization.py:129`），只有研究路徑傳 True（`catos/research_optimization.py:39`）。
  - `measure_d_onresult.py` 在 HEAD 另外確認：預設 sampler 是 `tpe`；開啟後 12 點逐一評估、編號 0..11；格點大於 n_trials 時退回 TPE；FAIL 點保留紀錄，回呼只給 COMPLETE。
  - 滾動驗證的訓練一向窮舉全格點，不受影響。

## E4. `research_robustness.py`：PASS

- **逐年加總等於總淨損益**：6 個變體在引擎精度（`research._CONTEXT`，prec 50）下逐年 `net_pnl` 加總都**完全等於** `performance.net_pnl`。
  - 我的第一版檢查用 Python 預設 28 位精度加總，A_vol、A_raw、B_raw 差 1E-45 而報 FAIL；改用 50 位精度重核後三者都是 True。這是我腳本的精度問題，不是程式缺陷。
  - 年份歸屬用 `time_ms − 1`，所以 00:00 的點算前一年（:45-46）。
- **延遲一根**（`Delayed` :60-77）：

```text
PASS Delayed A_vol: every fill at 04:00 UTC, one bar after the 00:00 decision :: 265 vs 267 fills
PASS Delayed A_raw: ... :: 274 vs 275 fills
PASS Delayed B_vol: ... :: 191 vs 191 fills
PASS Delayed B_raw: ... :: 193 vs 193 fills
PASS Delayed C_arrow: identical targets, each fill exactly +1 bar (04:00 instead of 00:00) :: 166 vs 166 fills
PASS Delayed C_score: identical targets, each fill exactly +1 bar (04:00 instead of 00:00) :: 187 vs 187 fills
```

  - 所有成交都從 00:00 移到 04:00，剛好晚一根。
  - 固定張數的 DCM 目標序列完全相同，每筆剛好平移一根。
  - vol_target 版的張數取決於成交價改變後的權益，筆數略有差異，屬預期。
- **bootstrap**：
  - 每個變體以相同輸入呼叫兩次結果相同；跨程序重跑也與文件數字完全相同（見 E5）。
  - 用法是移動區塊法：起點在 `[0, n−20]` 均勻抽，接到滿 n 再截斷。
  - 信賴區間取排序後第 50 與第 1,949 個平均值，兩端各排除 50 個，對稱。
- **日報酬**：取 00:00 的權益點。評估起點 04:00 不是日界，所以日報酬從 2022-11-09 起算，共 1,458 個，與文件相同。我另以 numpy 自算的年化 Sharpe 與 `sharpe_annualized` 差 < 1e-15。

## E5. 量測可重現：PASS（附 O3）

依文件 :491-499 的量測計畫自寫 `measure_e.py`：

- 回測經 `execute_request`，量 `json_text(payload)` 的 UTF-8 位元組。
- 成本加倍、延遲一根、bootstrap、逐年統計直接呼叫引擎與 `research_robustness`。

| 變體 | 淨損益（報酬） | 最大回撤 | 年化 Sharpe | 成交 | 價格損益／成本 | 每邊兩平 | 成本加倍 | 延遲一根 | bootstrap 不為正 | DSR（N=6） | 與文件 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A 波動目標 | +5,845.77（+58.46%） | 16.45% | 0.848 | 267 | +6,194.11／282.80 | 151.90 | +5,553.30 | +5,854.86 | 0.0565 | 0.7166 | 相同 |
| A 不縮放 | +11,493.43（+114.93%） | 24.28% | 0.861 | 275 | +12,286.90／657.29 | 129.57 | +10,747.64 | +11,204.04 | 0.0455 | 0.7131 | 相同 |
| B 波動目標 | +8,071.93（+80.72%） | 17.11% | 0.913 | 191 | +8,779.26／714.66 | 86.18 | +7,207.55 | +7,468.31 | 0.0455 | 0.7662 | 相同 |
| B 不縮放 | +13,291.80（+132.92%） | 33.04% | 0.795 | 193 | +14,943.71／1,656.25 | 63.26 | +11,285.42 | +12,925.90 | 0.0650 | 0.6741 | 相同 |
| C 箭頭原義 | −1,771.90（−17.72%） | 60.95% | 0.049 | 166 | −197.98／1,588.61 | −0.81 | −3,359.00 | +1,701.97 | 0.4240 | 0.1375 | 相同 |
| C 加評分 | −1,937.55（−19.38%） | 52.58% | −0.039 | 187 | −808.54／1,098.83 | −5.35 | −3,035.27 | −1,125.98 | 0.5405 | 0.1012 | 相同 |

**其他數字逐項核對：**

- **評估期間**：2022-11-08 04:00 到 2026-11-06 04:00 UTC，1,458 個日報酬。
- **買進持有（含手續費與滑價）**：用一個「首根評估 K 線收盤下單、持有到底」的策略經引擎重跑，與文件**完全相同**：
  - A、B 用 49.62 張：+27,202.50（+272.03%），最大回撤 53.29%，Sharpe 0.977。
  - C 用 10 張：+5,482.16（+54.82%），最大回撤 32.59%，Sharpe 0.663。
  - 這個算法的成交在第二根評估 K 線開盤（2022-11-08 08:00，19,797.3）。49.62 張則是用第一根開盤 20,151.9 算的，文件沒寫這個細節，見 O3。
  - 如果改成在評估起點開盤成交，結果是 +27,024.43／Sharpe 0.933，與文件不同。
- **逐年**：A、B 波動目標五年的淨損益與標的漲跌和文件表格逐格相同：

| 年 | A 波動目標 | B 波動目標 | 標的 |
| --- | --- | --- | --- |
| 2022 | −93.07 | +275.02 | −17.90% |
| 2023 | +2,812.57 | +2,068.11 | +155.64% |
| 2024 | +4,376.70 | +4,041.68 | +121.24% |
| 2025 | −1,084.53 | +1,802.88 | −6.40% |
| 2026 | −165.90 | −115.77 | −13.38% |

  - DCM 2025 年是 −3,070.66（箭頭版）、−4,238.22（評分版），也相同。
- **假設資金費**：
  - A 波動目標 4,093 次，多付 1,553.00，扣掉後淨損益 +4,292.77。
  - B 波動目標多付 595.89，扣掉後 +7,476.04。
  - 兩者都相同，說明文字都含「只是近似值」。
- **相關係數**：A~B（波動目標）0.653、A~C 0.171、B~C 0.238，相同。這裡的 C 是箭頭原義版，見 O3。
- **多重試驗**：
  - N=6 時 DSR 與表格相同，PBO 0.2286。scipy 參考實作也是 DSR(B 不縮放) 0.6741、PBO 0.2286。
  - N=29 的 **0.4037** 可重現，但算法是「沿用 6 個變體的 Sharpe 變異數、只把 N 換成 29」。把 SMA 7 組、Donchian 16 組都在同一評估期間重跑後一起算，DSR 是 0.3720。見 O3。
- **payload**：最大 1,032,669 bytes（A 不縮放），與文件相同。每次 0.30～0.51 秒，文件寫 0.30～0.50。

## E6. 前端：PASS（附 O4、O7）

**typecheck 與測試：**

- `npm ci`：exit 0。npm 警告 esbuild 的 postinstall 被 allow-scripts 擋下，但 `@esbuild/win32-x64` 二進位已在，之後的測試正常。
- `npm run typecheck`：`typecheck exit 0`。
- `npm test`：
  - 第一次卡住，見 O7。
  - 結束自己的程序後，`node --test` 連跑兩次都是 `ℹ tests 21`、`ℹ pass 21`、`ℹ fail 0`。
  - 原命令 `npm test` 是 `npm test exit 0`、`check:tokens OK`、`ℹ tests 21`、`ℹ pass 21`、`ℹ fail 0`。
- D 樹：`tsc --noEmit` exit 0，`node --test` 兩次都是 19／19，`check:tokens OK`。

**`fe_check.mjs`**（以專案自己的 Vite 設定做 SSR 載入，輸入是從後端匯出的真實 `catalog()`）：

```text
PASS donchian-ensemble|tsmom-multi|dcm-daily: in catalog strategy list (StrategyPicker renders every catalog entry)
PASS <三者>: minWarmupBars on 4H = 2202 :: 2202
PASS <三者>: minWarmupProblems 2201 rejected, 2202 accepted :: 預熱根數需至少 2202 根（367 天）
PASS <三者>: synthetic 15m needs 35232 bars and is blocked (>= 96)
PASS <三者>: validation default form warm-up 2202, quantity 1000|1000|10 :: {"train_bars":2188,"test_bars":1094,"windows":6}
PASS donchian-ensemble / tsmom-multi: sizing vol_target；dcm-daily: sizing fixed
PASS backtest page: vol_target label "張數上限"
PASS cost panel equitySized: "買進持有（期初 1 倍名目、成本前）"
PASS cost panel fixed: "買進持有（同張數、成本前）"
PASS cost panel shows the equity-sized scenario notice
PASS O6: legacy text by default, specific text when given
PASS overfitting panel renders DSR / PBO / N / earlier-search note
PASS overfitting panel old record fallback
PASS selection edges note
PASS selection edges note hidden when no edge
FAILURES: none
```

前端產生的請求交給後端驗證（`check_e_api.py` 第二階段）：

```text
PASS frontend backtest|optimization|validation request for donchian-ensemble|tsmom-multi|dcm-daily accepted by backend（9 項）
```

- 回測請求依頁面 `applyDefaults` 的 preset 規則組出；優化請求依頁面規則：預熱等於 `minWarmupBars`、參數用 preset、搜尋範圍用 `presetAxes`；滾動驗證請求由 `buildValidationRequest` 產生。三類請求都被後端 `validate_*` 接受。
- 用前端預設的 tsmom-multi 滾動驗證請求實際執行一次：6 窗都是 `COMPLETE`，`evaluation_complete True`，假設情境標示近似值。
  - 我第一版腳本把狀態寫成小寫 `complete` 而誤報 FAIL，改正後確認。
  - 這次也觀察到 `selection_edges` 為 6／6，見 O4。
- **三頁的程式位置**：
  - 回測頁：`applyDefaults` 帶入 preset 參數、張數與 `minWarmupBars`；張數標籤在 `pages/backtest.tsx:858`，預熱標籤在 :882-883。
  - 優化頁：預熱用 `minWarmupBars`（`pages/optimization.tsx:79`），搜尋範圍用 `presetAxes`。
  - 滾動驗證頁：`defaultValidationForm` 使用 `presetAxes` 與 `minWarmup`（`lib/validation-plan.ts:93-95`）。
- **沒有做瀏覽器實測**（選做）。要在隔離埠起 `catos.workspace_api` 與 Vite 整合代理，並另建資料根；本次沒有做，見「未涵蓋」。

## E7. 文件與「展示候選」判定：PASS（附 O5、O6）

**展示候選判定。** 事前門檻在 `docs/research-real-data-plan.md:501-509`，四項是：成本加倍仍正、延遲一根仍正、bootstrap 不為正 ≤ 0.10、DSR ≥ 0.95。用 E5 重算的數字逐項判定：

| 變體 | 1 成本加倍 > 0 | 2 延遲 > 0 | 3 boot ≤ 0.10 | 4 DSR ≥ 0.95 | 應判 | 文件 |
| --- | --- | --- | --- | --- | --- | --- |
| A 波動目標 | 是 | 是 | 是（0.0565） | 否（0.7166） | 有跡象 | 有跡象 |
| A 不縮放 | 是 | 是 | 是（0.0455） | 否 | 有跡象 | 有跡象 |
| B 波動目標 | 是 | 是 | 是（0.0455） | 否 | 有跡象 | 有跡象 |
| B 不縮放 | 是 | 是 | 是（0.0650） | 否 | 有跡象 | 有跡象 |
| C 箭頭 | 否 | 是 | 否 | 否 | 不通過 | 不通過 |
| C 評分 | 否 | 否 | 否 | 否 | 不通過 | 不通過 |

沒有變體達到「展示候選」，判定與事前門檻一致。

**文件與程式核對：**

- `docs/research-real-data-plan.md`「實作」:511-523 的描述與程式一致，包括：
  - `min_warmup_days`、`sizing`、`preset`
  - 假設情境的近似說明
  - 研究端窮舉而 `optimize()` 預設 TPE
  - 前端預熱 2,202 與「張數上限」
- 「判讀」:556-575 的數字都在 E5 重現。
- `docs/next-steps.md` 第 7 項的內容與程式及量測一致，狀態字樣見 O6。

---

## 實際執行的命令與結果

cwd 為 worktree 根目錄，`PY=C:/Users/user/Desktop/CatOS/.venv/Scripts/python.exe`，`S` 為上述暫存目錄，`DT=$S/d_tree`（`git archive fb11e321` 匯出）。

| 命令 | 結果 |
| --- | --- |
| `cp -r <主 checkout 4H 資料夾> data/okx/BTC-USDT-SWAP/4H/` 後 `sha256sum` | 三檔與 manifest 相同 |
| `$PY -B -m unittest discover -s tests`（HEAD） | `Ran 1447 tests in 173.256s`、`OK (skipped=11)` |
| 同上，cwd `$DT` | `Ran 1430 tests in 183.283s`、`OK (skipped=11)` |
| `PYTHONPATH=$S/pkgs;. $PY -B $S/check_overfit.py` | 15 項 PASS；1 項 FAIL 是我刻意製造並列的案例，由下一列說明 |
| `$PY -B $S/check_pbo_ties.py` | 連續資料 20／20 與精確算術相同；格點化資料的差異來自浮點並列 |
| `$PY -B $S/measure_d.py`（cwd `$DT`） | 優化、合併 N、滾動驗證全部 PASS；腳本最後一段因我的短切片帶到範圍外資金費而拋錯，另寫下一列 |
| `$PY -B $S/measure_d_onresult.py`（`$DT` 與 HEAD 各一次） | 全部 PASS，`FAILURES: none` |
| `$PY -B $S/check_o1.py`（cwd `$DT`） | 三組計畫 21 窗全部 PASS，`FAILURES: none` |
| `$PY -B $S/check_e_rules.py` | 全部 PASS；逐年加總 3 項是我用 28 位精度誤報，改 50 位重核相等 |
| `$PY -B $S/measure_e.py $S/measure_e.json` | 第一次因我的 N=29 key 格式錯誤中斷，修正後全部輸出，數字見 E5 |
| `$PY -B $S/check_e_api.py 1 $S`、`… 2 $S` | 第一階段全部 PASS；第二階段 9 項 PASS，1 項是我狀態大小寫寫錯，重核確認 |
| `npm ci`（`frontend/cat-os-vite`） | exit 0（esbuild postinstall 被 allow-scripts 擋，二進位已在） |
| `npm run typecheck` | exit 0 |
| `npm test` | 第一次卡住（O7）；`node --test` 兩次 21／21；原命令 exit 0、21／21 |
| `$DT` 前端：`npx tsc --noEmit`、`node --test …`、`node scripts/check-tokens.mjs` | exit 0；第一次卡住，之後兩次 19／19；`check:tokens OK` |
| `node $S/fe_check.mjs <frontend> $S/catalog.json $S/opt_tsmom.json $S/fe_requests.json` | 第一次因 SSR 載入 CJS 的 react 失敗（我的腳本），改用 `createRequire` 後全部 PASS |

## 非阻斷觀察

**O1（D，建議優先處理）　PBO 的判讀對「試了哪些參數」和 λ=0 的計數很敏感，`docs/research-real-data-plan.md:434`「PBO 在 0.10～0.27，選參過程本身沒有明顯偏差」站不住。**

- **λ=0 的影響**：原範圍 TPE N=9 的 70 種切法中，有 **11 種 λ 剛好為 0**（樣本外名次剛好是中位數）。
  - λ ≤ 0 計數得到 0.2714（開發者與 fynance、R `pbo` 相同慣例）。
  - 只計 λ < 0 是 0.1143。
  - 原文的定義是「∫ 從 −∞ 到 0」，沒有明確區分 λ=0；原文另外要求 N 遠大於 10，否則 φ 粒度太粗。
- **全格點的數字**：在 HEAD 用窮舉跑完整格點（同一請求）：

| 搜尋 | N | DSR | PBO |
| --- | --- | --- | --- |
| 原範圍 | 12 | 0.7126 | 0.4571 |
| 放寬範圍 | 15 | 0.7688 | 0.2000 |
| 兩格點聯集 | 21 | 0.7111 | 0.4286 |

- DSR「未達 0.95」的結論不受影響，D 的最終決定（不放寬、不當展示策略）也不受影響。但「選參過程沒有明顯偏差」只在 TPE 剛好抽到的 9 組上成立，全格點時 PBO 落在 0.2～0.5，依程式自己的判讀文字是「有一定機率選到樣本外不佳的組合」。
- 建議：
  - 在 :434 補註全格點的數字。
  - 或在 N 小時讓判讀文字（`research_overfit.verdict`）提示粒度粗、λ=0 的佔比。

**O2（D 文件）　D 實測表只能在 `fb11e321` 重現。**

- E 讓研究優化在格點 ≤ n_trials 時改窮舉。量測計畫裡同一個 n_trials 20 的請求，在 HEAD 會得到 N=12／15 與 O1 表中的數字。
- 表頭有寫「TPE，20 trials」，但沒有提醒 E 之後重跑會不同。
- 建議在表下註明對應的 commit。

**O3（E 文件）　有幾個量測算法文件沒寫明，第三方照文件重做會得到不同數字。**

- **N=29 的 DSR 0.4037**：實際是「沿用 6 個變體的 Sharpe 變異數，只把 N 換成 29」。把 SMA 7、Donchian 16 組在同一評估期間（預熱 2,202、1 張）重跑後一起算，N=29 的 DSR 是 **0.3720**（PBO 0.1429）。兩者都遠低於 0.95，結論不變。
- **「買進持有（含手續費與滑價）」**：在第二根評估 K 線開盤成交；1 倍名目的 49.62 張則用第一根開盤算。
- **相關係數的「C」**：是箭頭原義版。評分版與 A、B 的相關是 0.278、0.417。
- **張數換算價格**：用決策日收盤，見 E1。

**O4（E，前端／後端）　0／1 開關參數的滾動驗證，選參必然落在「邊界」。**

- `vol_scaling`、`score_filter` 的範圍是 0～1，任何選擇都是上限或下限。所以 `selection_edges` 永遠是 100%，前端 `SelectionEdgesNote` 會顯示「最佳值可能在範圍外；放寬範圍等於再搜尋一次」。這對開關參數沒有意義。
- 實測前端預設的 tsmom-multi 請求：6／6 窗都在邊界（下限 5、上限 1）。
- 建議：對只有兩個值的參數不計邊界，或改用不同文案。

**O5（E，程式說明）　`catos/research_costs.py:15-16` 的模組說明過時。**

- 說明仍寫假設情境「只對不依權益的策略有效，登錄的研究策略都是固定張數」。
- E 之後已有兩個依權益定部位的策略。程式改以 `EQUITY_SIZED_NOTICE` 在結果中說明（:34、:141），但 docstring 沒有同步。

**O6（D、E 文件）　入口與 README 有過時敘述。**

- `docs/next-steps.md:36`（D）與 :47（E）在 commit 內容裡寫「**尚未獨立驗收、未 commit**」，與 B＋A 驗收的 O5 同型。本次驗收後也要更新驗收狀態。
- `README.md:12`、:15 的研究策略仍只列 SMA／Donchian（「可選策略（SMA、Donchian）」）。E 的三個研究專用策略，以及 D 的 DSR／PBO、邊界統計，都沒有寫進 README；AGENTS.md 規定「現況以 README.md 為準」。

**O7（環境）　`npm ci` 後第一次 `node --test` 卡住。**

- HEAD 與 D 樹各發生一次，與 B＋A 驗收的 O7 相同。
- 現象：
  - `state_adapter_test` 的測試在等待後顯示 ✖。
  - 程序持有 HMR 埠 24678 與 esbuild 服務。
  - 留下被中斷的 `node_modules/.vite/deps_temp_c5820366`。
- 我核對程序屬於本 worktree 後結束了它們；之後每次都在 1～2 秒內通過。
- 另外 `npm ci` 警告 esbuild 的 postinstall 被 allow-scripts 擋下，二進位仍已安裝。
- 測試基礎設施不在本次差異內，列為環境觀察。

## 未涵蓋

- **瀏覽器實測**（選做）：沒有起研究服務與 Vite 代理，沒有在瀏覽器操作三個研究頁。改用 typecheck、既有前端測試、SSR 渲染面板與標籤，以及「前端產生的請求交給後端驗證」。版面、互動與 HTTP 端到端路徑沒有重驗，視覺由使用者自行在網頁驗收。
- **研究服務 HTTP 路徑**：量測直接呼叫研究計算函式，沒有經研究服務子程序與 `result.json` 落檔。開發者所說的隔離 18872／18892 瀏覽器實測沒有重驗。
- **事前登錄的時間先後**：規則與量測在同一筆 commit，無法從 git 歷史證明「先寫規則、後跑結果」。只能確認規則文字與程式一致，參數也都是文獻常見的固定值（9 個 Donchian 週期、1／3／12 月、質心 60 日、25% 波動目標）。
- **文獻與原指標的忠實度**：沒有查證 Zarattini 等 2025、Hurst／Ooi／Pedersen 2017 的原始參數，也沒有原 Pine DCM 指標的評分原文；只核對「文件 ↔ 程式」。
- **開發者的 repo 外核對**（fynance 2.13.1 的 12 案、8 案）：沒有重做同一套，改用我自己的 scipy 參考實作與精確算術。
- **其他合約、週期**：不在本包範圍，沒有觸發。30 秒逾時與 2 MB 輸出上限也沒有觸發，最大 payload 1,032,669 bytes。

## 參考來源（查證 PBO 定義用）

- Bailey, Borwein, López de Prado, Zhu, *The Probability of Backtest Overfitting*，eScholarship 修訂版：https://escholarship.org/content/qt4w1110bb/qt4w1110bb.pdf （J. Computational Finance 20(4), 2017：https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting ）
- R 套件 `pbo` 原始碼：https://rdrr.io/cran/pbo/src/R/pbo.R
- fynance `research.pbo` 文件：https://fynance.readthedocs.io/en/latest/generated/fynance.research.pbo.html
