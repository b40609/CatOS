# 工作包 B＋A（4H 五年資料與成本歸因）獨立驗收報告

- 日期：2026-11-06（Asia/Taipei）
- 驗收者：Claude Opus 5.5，獨立驗收會話。沒有參與本工作包的開發，也沒有撰寫任何 commit，具 AGENTS.md「DEVELOPMENT WORKFLOW」所定的獨驗資格。
- 範圍：分支 `feat/research-strategy-cost` 的 `eb558c85`，對照父 commit `240637fb`（`git diff 240637fb eb558c85`：20 個檔案，+899／−40）。驗收在 worktree `C:\Users\user\Desktop\CatOS\.claude\worktrees\acceptance-strategy-cost-8221eb`（分支 `claude/acceptance-strategy-cost-8221eb`，HEAD 即 `eb558c85`）進行。
- 結論：**PASS（7／7）**，沒有阻斷缺陷，附 7 項非阻斷觀察（O1～O7）。依指示不 commit、不 push、不 merge。
- 自寫腳本與完整輸出在本會話暫存目錄 `C:\Users\user\AppData\Local\Temp\claude\837e5163a61f2809\891bd209-adcb-43ef-96fc-6ace69cbd047\scratchpad\`（不在 repo，會話結束後可能被清掉；關鍵輸出已抄進本報告）：`check_costs.py`、`check_datasets.py`、`old_behavior.py`、`check_fetch.py`、`boundary.py`、`render_panel.mjs`，以及同名 `.log` 與 `measure_acceptance.json`。

## 驗收限制與隔離

- 沒有對 OKX 或任何外部服務發請求，沒有重新抓取資料。抓取工具只做讀碼與離線模擬：注入假的 opener，並把 `socket.connect`、`create_connection`、`getaddrinfo` 與工具的 `urlopen_json` 全部換成會拋錯的函式。
- 4H 資料集從主 checkout `C:\Users\user\Desktop\CatOS\data\okx\BTC-USDT-SWAP\4H\okx-btc-usdt-swap-4h-20211106-20261106\` **複製**到 worktree 的同一路徑（git 忽略，`.gitignore:29:/data/`）。複製後 sha256 與 manifest 相符，也與來源相同：candles `5a702ece…`、funding `76d6e4e1…`、instrument `248697dd…`、manifest `45cbf5be…`。主 checkout 沒有 15m 資料集，所以「舊的資金費完整資料集行為不變」改用 `git archive` 匯出的基底與新版，對同一份合成完整資金費輸入做比對（見第 1 項）。
- 沒有修改程式、測試或文件，只新增本報告。沒有 commit、push、merge、切換分支或 stash。竄改測試只改暫存目錄內的資料集副本，用完即刪。
- 沒有啟動任何 HTTP 服務，沒有使用 18870／18890，沒有碰 8770／8771。前端驗證用 `tsc`、`node --test` 與 Vite SSR 渲染（middleware mode、`ws: false`，不開埠）。
- `catos` 匯入路徑指向 worktree（`...\acceptance-strategy-cost-8221eb\catos\__init__.py`），venv 的 Python 3.14.6；Node v26.4.0。
- 執行後 worktree 只多了 git 忽略的產物，依指示沒有刪除：`data/`（複製的資料集）、`frontend/cat-os-vite/node_modules/`（`npm ci`，含一個被中斷的 `.vite/deps_temp_e523e733`，見 O7），以及後端套件自己寫的 `outputs/workspace-w6-fixture-test-52f569c2…`、`outputs/workspace-w8-fixture-test-58971aae…`。`git status --short` 乾淨，HEAD 仍是 `eb558c85`。本報告本身也在忽略範圍內（`.gitignore:47:/reports/*`；既有驗收報告是強制加入追蹤的），要收進 repo 需 `git add -f`。

## 總表

| # | 項目 | 結果 |
| --- | --- | --- |
| 1 | 資料集規則（`catos/research_datasets.py`） | PASS |
| 2 | 抓取工具（`tools/fetch_okx_candles.py`） | PASS |
| 3 | 成本歸因（`catos/research_costs.py`），真實 4H 資料獨立重驗 | PASS（窗尾邊界見 O1） |
| 4 | 輸出整合（回測、優化 `best_costs`、滾動驗證 `costs.total`、版本檔案清單） | PASS |
| 5 | 量測可重現（六個案例） | PASS（文件用語與數字見 O2～O4） |
| 6 | 前端（typecheck、測試、舊紀錄 fallback） | PASS（用語見 O6，環境見 O7） |
| 7 | 授權與文件、資料沒有進 git | PASS（過時敘述見 O5） |

## 1. 資料集規則：PASS

程式：`catos/research_datasets.py`。

- 規則：`funding_coverage` 在 `end_ms - times[-1] > interval` 時拋 `funding_stops_before_end`（:138-139），否則回傳 `(interval, times[0] - start_ms < interval)`（:140）。所以「晚開始」只會讓 `complete` 為 False，「提早結束」一律拒絕。`write_dataset` 不再有 `funding_incomplete` 分支，直接把 `complete` 寫進 manifest（:188-189、:208-209）。
- `load_manifest` 先要求 `complete` 是 bool、`events`／`interval_ms` 是 int（:340-343），雜湊核對後再從 `funding.csv` 重算（:353-358）；筆數、遞增唯一、`(interval_ms, complete)` 任一不符就回 `funding_manifest_mismatch`。`Dataset.funding_complete` 也是從第一筆資金費時間重算，不讀旗標（:240-243）。

自寫 `check_datasets.py` 的輸出（節錄）：

```text
PASS coverage: full funding -> complete True
PASS coverage: late start -> complete False
PASS coverage: stops before end -> funding_stops_before_end :: ValueError: funding_stops_before_end: last 374400000
PASS coverage: late and stops early -> funding_stops_before_end :: ValueError: funding_stops_before_end: last 345600000
PASS coverage: hole in the middle -> funding_interval_irregular :: ValueError: funding_interval_irregular
PASS coverage: end - last == interval accepted
PASS coverage: end - last == interval + 1 bar rejected
PASS real 4H copy is accepted unchanged :: []
PASS real 4H: funding_complete False, from 2026-08-03 16:00
PASS tamper: complete flag flipped to true -> funding_manifest_mismatch :: funding_manifest_mismatch
PASS tamper: events count 283 -> funding_manifest_mismatch :: funding_manifest_mismatch
PASS tamper: interval_ms 14400000 -> funding_manifest_mismatch :: funding_manifest_mismatch
PASS tamper: complete as string 'false' -> funding_unsupported :: funding_unsupported
PASS tamper: complete as 0 -> funding_unsupported :: funding_unsupported
PASS tamper: funding.csv tail removed, hash not updated -> dataset_hash_mismatch :: dataset_hash_mismatch
PASS tamper: funding.csv last 3 rows removed, hash+events updated -> funding_stops_before_end :: funding_stops_before_end: last 1793836800000
PASS tamper: funding.csv middle row removed, hash+events updated -> funding_interval_irregular :: funding_interval_irregular
PASS tamper: funding.csv row duplicated, hash+events updated -> funding_manifest_mismatch :: funding_manifest_mismatch
PASS first 10 funding rows dropped (hash+events updated) -> still accepted, partial :: []
FAILURES: none
```

- 竄改測試用的是真實 4H 資料集的暫存副本：把 `complete` 改成 true 會被拒；連同雜湊與筆數一起改掉尾端 3 筆，`load_manifest` 重算後以 `funding_stops_before_end` 拒絕，不會因 manifest 宣稱而放行。
- **舊的「資金費完整」資料集行為不變**：`old_behavior.py` 分別在 `git archive 240637fb` 與 `git archive eb558c85` 的匯出目錄內，以同一份輸入（15m、480 根、資金費從第一根到最後一根）呼叫 `write_dataset`，再 `load_manifest`、`execute_request`：

```text
PASS same dataset files byte for byte (manifest, candles, funding, instrument)
PASS Dataset name/notice/files/contract/bars/range unchanged
PASS head adds only funding_from_ms/interval_ms
   name: OKX BTC-USDT-SWAP 15m · 2026-09-30 ~ 2026-10-04 · 480 根已收盤 K 線（含資金費）
PASS describe(): head adds only funding_coverage (complete True)
PASS payload: head adds only costs and funding_coverage :: ['costs', 'funding_coverage']
PASS payload.request identical
PASS payload.provenance identical except engine_sha256
PASS engine_sha256 changed (research_costs.py added to ENGINE_FILES)
PASS payload.result identical
PASS payload.drawdown_curve identical
PASS payload.data_notice identical
PASS payload.trade_count_unit identical
PASS complete dataset: no funding scenario; costs.net == result net
PASS complete dataset: real funding paid nonzero and equal :: 0.77728086
PASS report: head == base plus one cost table before </body>
   base late write: ValueError: funding_incomplete: first 1791561600000, last 1791849600000
   head late write: {'complete': False, 'events': 11, 'interval_ms': 28800000, ...}
   base stops early: ValueError: funding_incomplete: ... | head: ValueError: funding_stops_before_end: last 1792483200000
PASS stops-early write rejected in head, no dataset or staging dir left
```

  四個檔案逐位元組相同，名稱與聲明不變（仍是「含資金費」與原 `NOTICE`），回測結果、回撤曲線、聲明完全相同；新版只多了 `costs`、`funding_coverage` 兩個欄位與報表尾端一張成本表，`engine_sha256` 因 `ENGINE_FILES` 增加檔案而改變（預期）。完整資金費時不產生假設情境。

## 2. 抓取工具：PASS

讀碼（`tools/fetch_okx_candles.py`）：

- `MAX_REQUESTS_CAP = 150`（:37）未變；新增 `MAX_DAYS = 1_830`（:40），`--days` 範圍檢查改用它（:199-200），`--max-requests` 上限檢查不變（:201-202）。本次差異只動了 docstring、`MAX_DAYS` 與這兩行。
- `Client.get` 只放行 `datasets.ENDPOINTS` 三個公開路徑，其他路徑在送出前就拋 `endpoint_not_allowed`（:75-76）。請求標頭只有 `User-Agent`（:42、:51）。`grep -n "environ|getenv|secret|passphrase|OK-ACCESS|api_key|apikey|sign"` 對整個工具沒有任何命中（exit 1）。

自寫 `check_fetch.py`（離線、網路已封）：

```text
PASS MAX_DAYS == 1830
PASS MAX_REQUESTS_CAP == 150 (unchanged)
PASS MIN_INTERVAL_S == 0.25 (unchanged)
PASS ENDPOINTS are the three public GET paths
PASS parser rejects days 1831 :: check_fetch.py: error: inst-id must be <BASE>-USDT-SWAP and days in [1, 1830]
PASS parser rejects days 0 :: ...
PASS parser rejects max-requests 151 :: check_fetch.py: error: max-requests must be in [1, 150] (authorized cap)
PASS parser rejects coin-margined inst :: ...
PASS Client(max_requests=151) rejected :: max_requests must be an integer in [1, 150]
PASS private endpoint refused before any request :: endpoint_not_allowed: /api/v5/account/balance
   simulated run: 0  {'/api/v5/market/history-candles': 110, '/api/v5/public/funding-rate-history': 4, '/api/v5/public/instruments': 1}
PASS simulated 1826-day 4H run uses 115 requests (110 candles, 4 funding, 1 instrument) :: 115
PASS simulated dataset id and bars match the collected one :: {'dataset_id': 'okx-btc-usdt-swap-4h-20211106-20261106', 'bars': 10956, 'funding_events': 284}
PASS every request after the first waited >= 0.25 s :: 114
PASS simulated manifest: complete false, 284 events, requests 115
FAILURES: none
```

以文件記載的參數（`--bar 4H --days 1826 --end-ms 1793937600000`）模擬，請求數正好是 115（K 線 110、資金費 4、規格 1），與實際 manifest 的 `"requests": 115` 一致；114 次後續請求都等滿 0.25 秒。受影響的 `tests/test_fetch_okx_dataset.py` 9 個測試 OK（見「實際執行的命令」）。

## 3. 成本歸因（真實 4H 資料獨立重驗）：PASS（附 O1）

程式：`catos/research_costs.py`。價格損益在 :115 以恆等式倒推，滑價逐筆是成交價與成交 K 線開盤價之差（:112），兩平成本是 `(price_pnl − funding_paid) / notional`（:119），買進持有取評估期間第一根開盤與最後一根收盤（:120-121），假設情境只在 `funding_from_ms > evaluation_start_ms` 時計算（:125），結算時點的部位取「時間嚴格早於該時點」的最後一筆成交（:80），對齊引擎「同時間戳先結算資金費、再成交」的順序（`catos/research.py:361-366`）。

自寫 `check_costs.py` 在真實 4H 資料集上以量測計畫的兩個回測（SMA 20／預熱 20、Donchian 192／48／預熱 192；1 張、本金 10,000、手續費 0.0005、滑價 2 bps）做了四種**不依賴 `research_costs` 的**獨立重算：

1. **現金流法**：自寫函式，價格損益 = Σ(−成交張數 × 0.01 × 成交 K 線開盤價) + 期末部位 × 0.01 × 最後一根收盤；開盤／收盤直接從 `candles.csv` 用 `csv` 讀，不經 catos 載入器。
2. **零成本重跑**：同策略、`fee_rate=0`、`slippage_bps=0` 重跑，要求部位序列相同、每筆都剛好成交在開盤價，再比 `price_pnl == 零成本 net + funding`。
3. **自建假設資金費事件**：在 `[評估起點, 第一筆真實資金費)` 每 8 小時建一筆 0.01% 事件（mark 取該根開盤），**加上**資料集的真實事件一起交給引擎重跑，比較多出的資金費與假設情境。
4. **買進持有**：起訖價從原始 CSV 讀。

```text
== bt_sma: 0.40s, payload 867,080 B
PASS bt_sma payload costs == cost_breakdown on direct run
PASS bt_sma every fill slippage is adverse (>= 0)
PASS bt_sma price_pnl == independent cash-flow :: -42.6300000000000000000 vs -42.630
PASS bt_sma slippage == independent cash-flow :: 150.868 vs 150.868
PASS bt_sma traded_notional == independent cash-flow :: 751164.120 vs 751164.120
PASS bt_sma fees == independent cash-flow :: 375.5820600 vs 375.5820600
PASS bt_sma fill_count == independent cash-flow :: 1288 vs 1288
PASS bt_sma identity price = net + fees + slippage + funding
PASS bt_sma zero-cost rerun has the same positions
PASS bt_sma zero-cost rerun fills exactly at opens
PASS bt_sma price_pnl == zero-cost net + funding (exact) :: -42.6300000000000000000 vs -42.6300000000000000000
PASS bt_sma real funding equal in both runs :: 6.2366791128699345682
PASS bt_sma scenario events == engine extra payments :: 5184
PASS bt_sma scenario assumed_paid == engine extra funding (exact) :: 155.3806296 vs 155.3806296000000000000
PASS bt_sma net_pnl_with_assumption == engine net (exact) :: -730.6973687128699345682
PASS bt_sma scenario window [eval start, funding start)
PASS bt_sma buy-hold entry open / exit close from raw CSV :: 67644.8 -> 75875.1
PASS bt_sma buy-hold pnl and return :: 82.303, 12.166936704669095037608212309002317990444202658590
PASS bt_sma money fields are Decimal
PASS bt_sma payload costs leaves are str/int/None (no float)
== bt_don: 0.42s, payload 659,395 B
PASS bt_don price_pnl == zero-cost net + funding (exact) :: 415.1780000000000000000 vs 415.1780000000000000000
PASS bt_don real funding equal in both runs :: 3.2111080192866714387
PASS bt_don scenario events == engine extra payments :: 5098
PASS bt_don scenario assumed_paid == engine extra funding (exact) :: 23.7866294 vs 23.7866294000000000000
PASS bt_don net_pnl_with_assumption == engine net (exact) :: 346.8921720807133285613
PASS bt_don buy-hold entry open / exit close from raw CSV :: 50126.4 -> 75875.1
PASS bt_don buy-hold pnl and return :: 257.487, 51.367542851670975773245236043282581633630182897630
（其餘各行同 bt_sma，全部 PASS）
```

- 價格損益：兩個策略都**完全相等**於零成本重跑的淨損益＋資金費，也等於自寫現金流法。零成本重跑每筆都剛好成交在開盤價，部位序列相同。
- 假設情境：把同費率事件交給引擎實際跑一次，多出的資金費（SMA 155.3806296、5,184 次；Donchian 23.7866294、5,098 次）與「含假設的淨損益」都**完全相等**。這個比對同時帶著真實資金費，比開發者測試（只有假設事件）更嚴格。
- 買進持有：起點是評估期間第一根（`bars[warmup]`）的開盤，終點是最後一根的收盤，與原始 CSV 一致。
- Decimal：`research_costs.py` 的 AST 沒有 float 常數或 `float` 名稱；`research._CONTEXT` 開著 `FloatOperation` trap，`cost_breakdown`、`total` 都在這個 context 內計算（:104、:143）；所有金額欄位型別都是 `Decimal`，payload 葉節點只有 str／int／None。
- 滾動驗證的 OOS 視窗也逐窗做了同樣的獨立重跑（見第 4 項）。另外刻意構造窗尾落在資金費時刻的計畫，發現假設情境與「依滾動驗證切片規則交給引擎」差一筆窗尾事件，見 O1。量測計畫與文件數字不受影響。

## 4. 輸出整合：PASS

- **回測**：`execute_request` 的 payload `costs` 等於對直接回測結果呼叫 `cost_breakdown`（`catos/research_catalog.py:576-581`），HTML 報表在 `</body>` 前插一張成本表（:590）。`funding_coverage` 正確：`{'source': 'dataset', 'complete': False, 'from_ms': 1785772800000, 'interval_ms': 28800000}`。
- **優化 `best_costs`**：程式用最佳參數重跑一次，performance 不同就拋 `best_trial_rerun_mismatch`（`catos/research_optimization.py:32-41`）。自寫檢查：

```text
== opt_sma: 3.25s, payload 13,824 B
   trials 20 distinct 7 of grid 7
PASS opt_sma best_trial_number is the max Decimal score among trials
PASS opt_sma reported best params are the grid maximum
PASS opt_sma best_costs == cost_breakdown of an independent rerun
PASS opt_sma best_costs.net_pnl == best trial net_pnl :: -554.9032486128699345682
PASS opt_sma best trial performance == independent rerun performance
PASS opt_sma best_costs price_pnl == independent cash-flow
== opt_don: 3.21s, payload 14,307 B
   trials 20 distinct 9 of grid 12
（同樣 7 項全部 PASS）
```

  另外以暴力法跑完整格點（SMA 7 點、Donchian 12 點），報告的最佳參數就是格點最大值（SMA period 20、Donchian 384／48），`best_costs` 等於獨立重跑的歸因，淨損益等於最佳 trial 的淨損益。Donchian 的 TPE 20 次只試到 9／12 點，見 O2。

- **滾動驗證 `costs.total`**：`_window_costs` 對每個完成的 OOS 視窗算歸因，再經 `json.loads(json_text(...))` 轉成 JSON 字串（`catos/research_validation_job.py:268-278`），在 payload 組裝前算好（:293、:302）。

```text
== val_sma: 1.56s, payload 551,027 B
PASS val_sma 7 OOS windows with costs
PASS val_sma total.price_pnl == sum of windows and is str :: 50.1970000
PASS val_sma total.fees == sum of windows and is str :: 236.8983565
PASS val_sma total.slippage == sum of windows and is str :: 95.109
PASS val_sma total.funding_paid == sum of windows and is str :: 0
PASS val_sma total.net_pnl == sum of windows and is str :: -281.8103565
PASS val_sma total.traded_notional == sum of windows and is str :: 473796.713
PASS val_sma total.buy_hold_pnl == sum of windows :: 515.971
PASS val_sma total.assumed_funding_paid == sum of window scenarios :: 121.2505063
PASS val_sma total.fill_count / events are int sums
PASS val_sma total ratios recomputed on sums
PASS val_sma costs JSON has no Decimal/float objects
PASS val_sma report has window cost table
PASS val_sma window 0 costs == independent rerun; scenario == engine :: params {'period': 32}
（window 1～6 同樣 PASS；val_don 7 窗與 13 項合計檢查同樣全部 PASS）
```

  合計每個金額欄位都是 `str`，等於各窗字串轉 Decimal 後相加；兩個比率用合計重算。逐窗以自寫切片（`bars[start − warmup : end]`、資金費 `first <= t <= last`）重跑選定參數，歸因與 payload 完全相同，假設情境也等於引擎實際收取的同費率資金費。

- **版本檔案清單**：`catos/research_costs.py` 在 `ENGINE_FILES`（`catos/research_catalog.py:95`）與研究服務 `RUNTIME_FILES`（`catos/research_api.py:27`）。第 1 項的基底／新版比對也證實 `engine_sha256` 因此改變。

## 5. 量測可重現：PASS（附 O2～O4）

依 `docs/research-real-data-plan.md:296-303`「量測計畫」自寫腳本（`check_costs.py`），直接呼叫 `execute_request`／`execute_optimization`／`execute_validation`，量 `json_text(payload)` 的 UTF-8 位元組。優化 `n_trials` 計畫沒寫，用 20（上限）；請求裡被搜尋參數的佔位值用格點下限。這樣六個 payload 的位元組數與文件**完全相同**，可佐證開發者用的是同一組請求。

| 案例 | 耗時（本次／文件） | payload（本次／文件） | 報酬 | 價格損益 | 手續費＋滑價（精確） | 淨損益 | 成交 | 每邊兩平 | 買進持有 | 與文件 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 回測 SMA 20 | 0.40／0.37 秒 | 867,080／867,080 | -5.75% | -42.63 | 526.4500600 | -575.32 | 1,288 | -0.65 bps | +82.30 | 相同 |
| 回測 Donchian 192/48 | 0.42／0.36 秒 | 659,395／659,395 | +3.71% | +415.18 | 41.2880905 | +370.68 | 103 | 69.93 bps | +257.49 | 相同（「41.28」見 O4） |
| 優化 SMA 8~32/4 | 3.25／2.81 秒 | 13,824／13,824 | 最佳 20：-5.55% | -23.14 | 525.5275695 | -554.90 | 1,286 | -0.39 bps | | 相同 |
| 優化 Donchian 12 點 | 3.21／2.60 秒 | 14,307／14,307 | 最佳 384/48：+6.29% | +656.80 | 23.1509585 | +628.96 | 56 | 197.41 bps | | 相同 |
| 滾動驗證 SMA 7 窗 | 1.56／1.36 秒 | 551,027／551,027 | 4 窗為正 | +50.20 | 332.0073565 | -281.81 | 723 | 1.06 bps | +515.97 | 相同 |
| 滾動驗證 Donchian 7 窗 | 2.94／2.58 秒 | 467,108／467,108 | 5 窗為正 | +369.58 | 17.4045645 | +352.18 | 40 | 148.80 bps | +515.97 | 相同 |

文件「說明」與「各窗」段落的數字也逐一核對：

- 每邊實際成本 7.01 bps（六案都是）。OOS 視窗資金費合計 0。
- 假設情境：Donchian 多付 29.7782004，含假設淨損益 322.3992351（文件「約 322.40」）；SMA 多付 121.2505063。
- 兩個滾動驗證的 OOS 起訖都是 1670500800000 → 1771300800000，即 2022-12-08 12:00 到 2026-02-17 04:00 UTC，`unused_bars` 1572（262 天）。
- Donchian 各窗選定參數：entry 7 窗都是 384，exit 依序 24、24、24、24、48、72、72。
- Donchian 各窗淨損益：+38.03、+21.39、+166.65、-38.18、+266.57、-143.59、+41.31。
- 最後一窗（2025-09-03 起）標的 -38.55%，買進持有 -429.43，Donchian +41.31。

耗時本次略慢（Python 3.14.6，同機另有其他程序），量級一致；耗時不是驗收門檻。

## 6. 前端：PASS（附 O6、O7）

- `npm ci`：exit 0。`npm run typecheck`（`tsc --noEmit`）：exit 0，無輸出錯誤。
- `npm test`：第一次在 `npm ci` 後卡住超過 6 分鐘（見 O7），手動結束後重跑。逐檔 `validation_plan_test` 8／8、`state_adapter_test` 11／11。原命令連跑三次都通過，3～4 秒：`ℹ tests 19`、`ℹ pass 19`、`ℹ fail 0`。`check:tokens OK`。
- 現有前端測試沒有涵蓋成本面板，所以另寫 `render_panel.mjs`，用專案自己的 Vite 設定以 SSR 載入 `src/components/catos/cost-breakdown-panel.tsx`，再用 `react-dom/server` 渲染：

```text
PASS view=null renders without throwing
PASS view=null shows the fallback text and no data block
PASS view=undefined renders without throwing
PASS view=undefined shows the fallback text and no data block
PASS page expressions on old payloads yield null views and no throw
PASS Donchian backtest payload renders price/net data attributes
PASS Donchian backtest shows +415.18 / +370.68 / 69.93 bps / +257.49 / assumed funding block :: 3557
   verdict(backtest Donchian): 扣成本前後都賺錢；每邊兩平成本和目前每邊成本的差距，就是對成本上升的緩衝。
   verdict(backtest SMA): 扣成本前的價格損益已經不是正的：問題在訊號，降低成本也救不回來。
PASS validation total renders +352.18 / 148.80 bps / +515.97 / assumed -29.78 with the notice
PASS validation total omits the underlying-return row (no single window)
   verdict(validation SMA total): 扣成本前賺錢、扣成本後虧損：成本吃掉了優勢，需要降低交易頻率或成本。
PASS no fills (null bps) renders without throwing
FAILURES: none
```

- 舊紀錄 fallback：`view` 為 `null`／`undefined` 時，面板顯示「這筆結果沒有成本拆解（成本歸因上線前的舊紀錄）。」（`cost-breakdown-panel.tsx:71-72`），不拋錯。三頁的呼叫端對缺欄位都有防護：
  - 回測：`result.costs ? … : null`（`pages/backtest.tsx:586`）。
  - 優化：`realResult.best_costs ? … : null`（`pages/optimization.tsx:305`）。
  - 滾動驗證：合計 `realResult.costs?.total ? … : null`（`pages/validation.tsx:612`）；逐窗 `realResult.costs?.windows.find(...)?.costs`（:569），視窗表的 `costs?.price_pnl`、`costs?.buy_hold.pnl` 在 `costs` 為 undefined 時短路。
  腳本以舊 payload 形狀實際求值，三個 view 都是 null，逐窗欄位是 undefined，沒有拋錯。
- 回測頁資金費說明在 `funding_coverage.complete` 為 false 時加「僅涵蓋 … 之後」（`pages/backtest.tsx:688`）。
- 沒做瀏覽器實測（選做項目），見「未涵蓋」。

## 7. 授權與文件：PASS（附 O5）

- **授權**：`AGENTS.md:28` 的 2026-11-06 條文，與實際採集逐項一致：
  - 範圍：BTC-USDT-SWAP、4H、最近 5 年。實際區間 [2021-11-06 04:00, 2026-11-06 04:00) UTC，正好 1,826 天，10,956 根。
  - 端點：同一工具、三個公開 GET 端點，與 manifest `endpoints` 相同。
  - 請求數：單次上限 150，實際 `requests: 115`。
  - 時間：`fetched_at_ms` 1793946864666，即 2026-11-06 06:34 UTC（台北 14:34），在授權當日。
  - 存放：只存 `data/okx/`。
  - 資金費缺口：採「不計真實資金費並明示＋固定費率假設情境」，假設情境在 payload、報表、前端都標「假設情境，不是實際帳務」。
- **README.md**：研究資料列（:15）描述「manifest 雜湊相符、無缺口；資金費必須連續到最後一根、可晚於第一根開始；明示之前未計資金費並另列固定費率假設情境；三種研究都有成本拆解與買進持有基準」，與程式一致。抓取工具段（:66）「資金費在結束前中斷就停止，不寫入任何檔案；`--days` 上限 1,830」與第 1、2 項實測一致：中斷時沒有留下資料夾或 staging 目錄。
- **docs/next-steps.md** 第 5 項、**docs/research-real-data-plan.md**「工作包 B＋A」：實作與數字描述與程式及第 5 項重跑相符。不精確處列在 O2～O5。
- **資料沒有進 git**：`git ls-tree -r eb558c85 --name-only | grep -c '^data/'` → 0；`git show --stat eb558c85` 沒有 `data/okx` 或 `.csv`；`git check-ignore -v` → `.gitignore:29:/data/`；複製資料後 `git status --short` 乾淨（`data/` 只出現在 `--ignored` 清單）。

## 實際執行的命令與結果

（cwd 為 worktree 根目錄，`PY=C:/Users/user/Desktop/CatOS/.venv/Scripts/python.exe`，`S` 為上述暫存目錄）

| 命令 | 結果 |
| --- | --- |
| `cp -r <主 checkout 4H 資料夾> data/okx/BTC-USDT-SWAP/4H/` 後 `sha256sum` | 四檔與 manifest、來源相同 |
| `$PY -B -m unittest discover -s tests` | `Ran 1419 tests in 202.016s`、`OK (skipped=11)` |
| `$PY -B -m unittest discover -s tests -p <module>.py`（4 個受影響模組） | `test_fetch_okx_dataset` 9 OK；`test_research_datasets` 11 OK；`test_research_costs` 8 OK；`test_research_validation_web` 12 OK |
| `$PY -B $S/check_costs.py` | 112 項 PASS，`FAILURES: none`（第一次跑因我自己讀錯欄位名 `score`／`selected_trial` 出現假 FAIL 與 KeyError，修正腳本後重跑，程式沒有問題） |
| `$PY -B -I $S/old_behavior.py $S/base …`、`… $S/head …`，再 `$PY -B $S/check_datasets.py` | 全部 PASS，`FAILURES: none`（第一次我寫錯一個邊界案例的預期值，修正腳本後重跑） |
| `$PY -B $S/check_fetch.py` | 全部 PASS，`FAILURES: none` |
| `$PY -B $S/boundary.py` | 見 O1 |
| `npm ci`（`frontend/cat-os-vite`） | exit 0 |
| `npm run typecheck` | exit 0 |
| `npm test` | 第一次卡住（O7）；之後 3 次都 `ℹ tests 19`、`ℹ pass 19`、`ℹ fail 0` |
| `node $S/render_panel.mjs <frontend> $S/measure_acceptance.json` | 全部 PASS，`FAILURES: none` |

## 非阻斷觀察

**O1　OOS 窗尾剛好是資金費時刻時，假設情境少算窗尾那一筆。**

- 兩邊的區間不同：
  - `_scenario` 用半開區間 `range(first, end, interval_ms)`（`catos/research_costs.py:79`）。
  - 滾動驗證切片收進 `first <= t <= last` 的事件（`catos/research_validation.py:269`），引擎在最後一根收盤時刻也會結算（`catos/research.py:366`）。
  - 所以 OOS 窗尾 T 若剛好是 8 小時格點、且在真實資金費起點之前，引擎依同一規則會以 T 時的部位收一次，假設情境不收。每個新視窗從 0 部位開始，起點那筆金額為 0，不會重複計。
- `boundary.py` 把 Donchian 滾動驗證的 train 改成 2001，讓 7 個窗尾都落在格點上：
  - 7 窗都是 500 次對 501 次。
  - 窗尾有部位的兩窗差 +0.0350514 與 -0.0683459（等於窗尾部位 × 0.01 × T 開盤 × 0.0001），合計 -0.0332945 USDT。
  - 其餘窗尾部位為 0，金額相同。
- 量測計畫的窗尾在 04:00／12:00／20:00，不在格點上，所以第 3～5 項的數字不受影響。完整資料集回測的終點是真實資金費期間，也不受影響。
- 金額小，而且是標明的假設，所以列為非阻斷。但這和 docstring「mirroring `research._Ledger.fund`」以及文件「部位與 mark 價對齊引擎的結算順序」（`docs/research-real-data-plan.md:318`）在這個邊界不一致。建議二選一：
  - 窗尾 T < 真實資金費起點時也收 T；
  - 或在文件明示「不含窗尾時刻」。
  另外補一個窗尾對齊的測試。

**O2　量測計畫寫「窮舉格點」，但沒寫 `n_trials`，實際也不是窮舉。**

- `docs/research-real-data-plan.md:301`。優化器是 TPE（`catos/optimization.py:142`）。
- 用 `n_trials` 20 重現時 payload 位元組與文件完全相同，可推定開發者也用 20。
- SMA 7 點全試到；Donchian 只試到 9／12 點，缺 (96, 48)、(288, 24)、(384, 72)。
- 暴力法確認未試的點都不是最大值，報告的最佳 384／48 就是格點最大值，結論不受影響。
- 建議文件寫明 `n_trials 20`，並把「窮舉」改成「TPE 20 次；Donchian 試到 9／12 點」，或真的改成窮舉。

**O3　`docs/research-real-data-plan.md:307`「期間收盤從 61,112.7」不對。** 61,112.7 是第一根 K 線（2021-11-06 04:00 UTC）的開盤；第一根收盤是 60,777.5。結尾 75,875.1 正確。

**O4　`docs/research-real-data-plan.md:327` Donchian 回測「手續費＋滑價 41.28」。** 精確值 29.4540905＋11.834＝41.2880905，四捨五入應為 41.29；表中其他格都是四捨五入，例如 SMA 526.4500600 → 526.45、滾動驗證 332.0073565 → 332.01。

**O5　入口文件有過時或不精確的敘述。**

- `docs/next-steps.md:24` 仍寫「只有開發者自測，**尚未獨立驗收、未 commit**」，實際已 commit 為 `eb558c85`；本次驗收後也要更新驗收狀態。
- 同檔 :29「選定參數都在格點上限」：只有 entry 384 在上限，exit 是 24／48／72。方案文件 `docs/research-real-data-plan.md:352` 的說法是對的。
- `docs/research-real-data-plan.md:254` 標題仍是「下一個工作包候選：策略與成本（2026-11-06 提案，待你選）」，但已經選定。`AGENTS.md:28` 以這個標題引用，若改名要一起改。

**O6　前端 fallback 文字在非舊紀錄時也會出現，措辭不準。** 「這筆結果沒有成本拆解（成本歸因上線前的舊紀錄）」（`cost-breakdown-panel.tsx:72`）在下列新紀錄上也會顯示：

- 新優化所有 trial 都失敗、沒有最佳 trial（`best_costs` 為 null，`catos/research_optimization.py:32`、:54）；
- 新滾動驗證沒有完成任何 OOS 視窗（`costs.total` 為 null，`catos/research_costs.py:140-142`）。

建議依情況改用「沒有可拆解的最佳試驗／完成的視窗」。

**O7　環境：`npm ci` 後第一次 `npm test` 卡住。**

- 卡住超過 6 分鐘。測試子程序只用 0.48 秒 CPU，持有 HMR 埠 24678 與一個 esbuild 服務，並留下被中斷的 `node_modules/.vite/deps_temp_e523e733`，推測卡在首次依賴預打包。
- 我結束了這組自己啟動的程序（`npm test`、`node --test`、子程序、esbuild），24678 已釋放；之後逐檔與原命令共 5 次都在 1～4 秒內通過。
- 測試基礎設施不在本包差異內，列為環境觀察；若常見，可考慮在 `node --test` 加 `--test-timeout`。

## 未涵蓋

- **實際採集**：依限制沒有重新抓取或連網。「115 次請求、29 秒」中，115 有 manifest 與離線模擬佐證；29 秒沒有可核對的紀錄。OKX 只保留約 3 個月資金費，是依文件與實際資料（284 筆從 2026-08-03 16:00 起）判讀，沒有對外查證。
- **瀏覽器實測**（選做）：沒有啟動 18870／18890，也沒有在瀏覽器操作三個研究頁。改用 typecheck、既有前端測試與成本面板的 SSR 渲染，涵蓋 fallback 與數字顯示；版面、互動與研究服務經 HTTP 的端到端路徑沒有重驗。視覺由使用者自行在網頁驗收。
- **研究服務 HTTP 路徑**：量測直接呼叫研究計算函式，與文件量測方式相同。沒有經研究服務子程序與 `result.json` 落檔，所以服務端耗時（文件的 0.72／3.17／3.17 秒）沒有重驗。
- **15m 舊資料集**：主 checkout 沒有 15m 資料集，舊行為以 `git archive` 基底與新版在相同合成輸入上比對，沒有用真實 15m 資料重跑。
- **其他合約、週期與 30 秒逾時、2 MB 輸出上限**：不在本包改動內，沒有觸發。
