# 研究線：真實歷史 K 線研究（工作包 C 方案）

更新：2026-11-04。使用者選定「研究線」並授權下方的採集範圍。本文件是方案與採集授權範圍，實作與實測結果見文末「實作紀錄」。

## 要解決的問題

研究 HTTP 目前只能用一份 96 根的合成資料，跑出來的績效沒有任何市場意義：
- 資料集寫死：`catos/research_catalog.py:21-22`（`DATASET_ID`、`DATA_PATH`），`validate_request` 遇到其他 id 一律 `unknown_dataset`（`:222`）。
- 合約規格寫死為 tick 0.01、lot 1（`research_catalog.py:245-248`），和真實 BTC-USDT-SWAP 不一定相同。
- 資金費固定為空（`research_catalog.py:248` 的 `()`），回測說明也寫「Synthetic only」。
- 單次回測上限 512 根（`MAX_BARS`，`:52`）。本機實測 Decimal 核心約每秒 4.5 萬根（5 萬根約 1.1 秒），所以這不是效能限制；真正的瓶頸是結果每根都輸出權益點，而輸出上限是 2 MB（`MAX_OUTPUT_BYTES`）。
- 現有抓取工具 `tools/fetch_okx_candles.py` 沒有資料來源紀錄、雜湊、缺口檢查與合約規格，而且每頁間隔 0.05 秒等於每秒 20 次，超過 OKX 公開的每 2 秒 20 次。

## 業界與開源做法

| 工具 | 歷史資料怎麼取得與存放 | 可借鏡 | 不適合 CatOS 的地方 |
| --- | --- | --- | --- |
| [Freqtrade](https://www.freqtrade.io/en/stable/data-download) | `download-data` 依交易所／交易對／週期存本機檔案，預設 feather，也支援 json、parquet；保留既有資料只補抓缺的區間 | 本機檔案、增量補抓、依區間下載 | feather／parquet 需要 pyarrow，而且以浮點存價格 |
| [Jesse](https://docs.jesse.trade/docs/research/candles) | 只匯入 1m K 線到資料庫，回測時再合成較大週期；缺 K 線會讓回測直接失敗 | 缺口必須擋下來，不能默默補 | 需要 PostgreSQL；CatOS 規定不載入 1m 資料 |
| [NautilusTrader](https://nautilustrader.io/docs/latest/concepts/data/catalog/) | `ParquetDataCatalog` 把 K 線與合約定義一起存成 Parquet，回測從資料目錄讀 | 合約規格和資料一起保存 | Parquet 與 Rust 引擎太重 |
| [ccxt](https://github.com/ccxt/ccxt/wiki/binance-fetch-ohlcv-pagination) | 統一抓取介面，用 since／limit 迴圈分頁 | 分頁與空頁處理 | 新增大型依賴，CatOS 只需要 OKX 三個公開端點 |
| [Tardis.dev](https://docs.tardis.dev/historical-data-details/okex) | 付費的逐筆歷史資料，每月第一天的 CSV 免費 | — | 付費、逐筆，超出已收盤 K 線研究的需求 |

OKX 端點（第三方資料，實作時以實際回應核對）：
- `GET /api/v5/market/history-candles`：公開，每 IP 每 2 秒 20 次（[Hummingbot 連接器](https://github.com/hummingbot/hummingbot/pull/7022/files/d94ee1fde23adb3de1ed4b148e1d0e4eb9c3080d)）；回應含 `confirm`，只取已收盤（`confirm == "1"`）。
- `GET /api/v5/public/funding-rate-history`：公開，第三方指南列每 2 秒 10 次；[實測](https://athenum.mataroa.blog/blog/how-much-crypto-funding-rate-history-can-you-actually-get-four-venues-four-silent-limits/) BTC-USDT-SWAP 只能回溯約 93 天。
- `GET /api/v5/public/instruments`：公開，取 `ctVal`、`tickSz`、`lotSz`、`minSz`。

## 建議做法

**存法：CSV＋JSON manifest**，放在已被 git 忽略的 `data/okx/<instId>/<bar>/`。

| 選項 | 優點 | 缺點 |
| --- | --- | --- |
| **A. CSV＋manifest（建議）** | 沿用現有 `data_io.load_candles_csv` 與策略 manifest 的雜湊模式；只用標準函式庫；價格保持 Decimal 字串；不需新 DB schema | 檔案比 Parquet 大；3.5 萬列讀取不到 1 秒，不構成問題 |
| B. SQLite 表 | 符合 SQLite 底座，增量去重方便 | 要新 schema，依 AGENTS.md 需另行確認 |
| C. Parquet／feather | 讀寫快、檔案小 | 需要 pyarrow；預設浮點，違反 Decimal／TEXT 不變量 |

manifest 記錄：來源端點、`instId`、`bar`、起訖時間、列數、CSV 的 sha256、抓取時間、缺口檢查結果，以及當時的合約規格快照與資金費檔案的 sha256。研究端比照策略登錄：只接受 manifest 登錄、雜湊相符的資料集，不符即拒絕（fail-closed）。

**第一個切片範圍：BTC-USDT-SWAP、15m、最近 90 天**（約 8,640 根）。90 天落在資金費歷史的可回溯範圍內，所以回測可以帶真實資金費，不必標「未計資金費」。

## 採集授權範圍（需要你同意）

- 只呼叫上面三個公開 GET 端點，不用金鑰、不碰帳戶端點、不下單。
- 合約與週期：BTC-USDT-SWAP、15m，最近 90 天。
- 請求量約 90 次 K 線＋數次資金費＋1 次合約規格；每次間隔至少 0.25 秒（低於兩個限速），總時間約 30 秒。
- 資料存在本機 `data/okx/`（git 忽略），不上傳；另一台機器需要時用同一個指令自己抓，manifest 雜湊可互相核對。
- 只在這份資料上跑單一合約的回測與優化，不做全市場歷史回測。

## 實作內容（授權後一個工作包完成）

1. 抓取：改寫 `tools/fetch_okx_candles.py`，修正限速、加入重試、去重、缺口檢查、合約規格與資金費抓取，並產生 manifest。
2. 資料集登錄：`research_catalog` 改從 manifest 讀資料集清單，載入前核對雜湊；合約規格與資金費改由 manifest 提供；保留現有合成資料集。
3. 上限：`MAX_BARS` 依實測放寬（例如 2 萬根）；權益曲線在輸出時降採樣，避免超過 2 MB，績效數字仍用全部 K 線計算。
4. 前端：回測與優化頁加資料集選擇，並顯示資料說明（來源、區間、是否含資金費）。
5. 測試：抓取用離線假回應做單元測試（分頁、未收盤過濾、缺口、限速、重試）；manifest 雜湊不符要拒絕；整合測試涵蓋選擇資料集。
6. 驗收：完成後交另一個 Claude 會話獨立驗收。

## 不涵蓋與模型假設

- 仍是本根收盤決策、下一根開盤加滑價成交；沒有訂單簿、沒有保證金與強平模型，回測結果不代表實盤可得績效。
- 不做 1m 資料、多合約、多策略、策略上傳。
- OKX 的 `limit`、`after` 分頁語義與資金費回溯深度，要在第一次抓取時以實際回應核對，和文件不符就停止並回報。

## 實作紀錄（2026-11-04，分支 `feat/research-real-data`）

採集（依授權實際執行一次）：`tools/fetch_okx_candles.py --inst-id BTC-USDT-SWAP --bar 15m --days 90`，共 91 次請求。結果是資料集 `okx-btc-usdt-swap-15m-20260806-20261104`：區間 [2026-08-06 04:00, 2026-11-04 04:00) UTC，8,640 根、無缺口，資金費 270 筆、每 8 小時一次、涵蓋完整。分頁行為與預期一致（`after` 回傳更舊的資料、由新到舊、每頁最多 100 筆）。合約規格為 ctVal 0.01 BTC、tickSz 0.1、lotSz 0.01、minSz 0.01，和合成資料（tick 0.01、lot 1）不同。這 270 筆的 `realizedRate` 與 `fundingRate` 完全相同。

程式：
- `catos/research_datasets.py`：manifest 的唯一寫入者（`write_dataset`，拒絕缺口、資金費不完整或間隔不規則，以及覆寫）與驗證者（`load_manifest`，重算每個檔案的雜湊，並核對合約規格與 `instrument.json` 一致）。
- `catos/research_catalog.py`：`datasets()`、`resolve_dataset()`；`provenance(dataset_id)` 預設仍是合成資料，所以本機模擬路徑不變；合約、週期與資金費都由資料集提供；`MAX_BARS` 512 → 20,000。權益與回撤曲線超過 2,000 點時，每段保留回撤最深的一點，並在 payload 標明 `curve_sampling`；績效數字仍以全部 K 線計算。
- 研究服務、優化與驗證工作改用請求裡的資料集計算與核對來源。
- 前端：回測與優化頁加上資料集選擇（`components/catos/dataset-picker.tsx`）；績效數字改用 Decimal 格式化（原本直接顯示 50 位小數）；資金費說明改依資料集顯示；圖表座標軸取整、多日資料改用日期標籤。

和方案不同的地方：
- **滾動驗證只接受合成資料。** 在 8,640 根上量到的輸出是 13.7 MB（逐根環境標籤 1.8 MB、各視窗權益曲線 1.8 MB、區間評估 1.8 MB，加上 8.2 MB 的 HTML 報表），超過 2 MB 上限，而且和方案大小無關。所以改在送出時就拒絕（`validation_supports_synthetic_dataset_only`），不讓它跑完才失敗。（已由下方「滾動驗證接上真實資料」取代：v2 輸出瘦身後不再拒絕。）

實測（本機，真實資料集）：
- 回測（period 20、1 張、本金 10,000）：0.57 秒，輸出含 HTML 報表約 1.1 MB，其中 payload JSON 約 856 KB（曲線從 8,621 點取樣為 1,725 點）。報酬 -5.67%，最大回撤 6.12%，1,062 筆成交，手續費 415.04，資金費 5.92 USDT。
- 優化（period 8~32、步進 4、7 個試驗、seed 42、本金 1,000、2 張，約 1.3 倍槓桿）：5.4 秒，輸出 34 KB。最佳是 period 32，報酬仍是 -80.16%，各參數都被手續費拖累。獨立驗收以步進 1 重跑，得到 period 31、-81.97%。研究模型沒有保證金與強平，所以回撤可能超過 100%。

自測：後端 `test_research_datasets`（9 個）、`test_fetch_okx_dataset`（6 個，假 OKX，不連網）與既有研究測試全過；前端 typecheck、單元測試通過。另在隔離的 18870／18890 用瀏覽器實際選資料集，各送出一次回測與優化。

獨立驗收：6/6 PASS，附 8 項非阻斷觀察（`reports/research-real-data-acceptance-20261104/acceptance.md`）。驗收後修了其中 3 項，只有開發者自測：
- O1：`tools/fetch_okx_candles.py` 把請求上限硬鎖在 150（`MAX_REQUESTS_CAP`，`Client` 與 CLI 都會拒絕更大的值），補 1 個測試（現為 7 個）。
- O7：優化數字補上步進 4 與完整參數。
- O8：next-steps 的過時敘述，以及回測輸出大小的量測對象。

其餘觀察（被拒資料集不顯示原因、曲線取樣偏向低點、回撤 tooltip 與版本 `mode` 等既有文字、manifest 防意外不防偽造）留在報告，未處理。

後續（未做）：
- ~~滾動驗證輸出瘦身~~（2026-11-04 完成，見下節）。
- 月度收益矩陣（頁籤目前標示尚未實作）。
- 保證金與強平模型（目前回撤可能超過 100%）。

## 滾動驗證接上真實資料（2026-11-04，分支 `feat/research-validation-real-data`）

獨立驗收 7／7 PASS，附 4 項非阻斷觀察（`reports/research-validation-real-data-acceptance-20261104/acceptance.md`）。驗收後依觀察 O1–O4 補了回看根數上限、前端預檢與文件數字，這部分只有開發者自測。已合併進 `main`（`aa4def4`）並推送。

### 業界與開源 walk-forward 報告怎麼呈現

| 工具 | 每個視窗保留什麼 | 跨視窗怎麼呈現 | 逐根資料 |
| --- | --- | --- | --- |
| [AmiBroker](https://amibroker.com/guide/h_walkforward.html) | 每段 IS／OOS 各一份回測報告，依最佳化目標排序選參 | 「PS」彙總報告涵蓋所有 OOS 段；OOS 權益串成 `~~~OSEQUITY`，每段以上一段期末權益起算（假設複利） | 權益只在合成曲線裡 |
| [TradeStation WFO](https://help.tradestation.com/09_01/tswfo/topics/walk-forward_summary_out-of-sample.htm) | 每次 run 的 IS 與 OOS 摘要列 | Walk-Forward Efficiency（OOS 對 IS 年化報酬）、獲利 run 比例、單一 run 占總淨利比例、單 run 最大回撤，並內建[通過／不通過準則](https://help.tradestation.com/09_01/tswfo/topics/walkforward_test_results.htm) | 不列 |
| [NinjaTrader 8](https://ninjatrader.com/de/support/helpGuides/nt8/walk_forward_optimize_a_strate.htm) | 每段一列：起訖日與最佳參數，保留前 N 名結果可點開 | 未見合併的 OOS 摘要 | 不列 |
| [vectorbt 範例](https://github.com/polakowo/vectorbt/blob/master/examples/WalkForwardOptimization.ipynb) | 每段只存純量（IS／OOS Sharpe、最佳參數） | 逐段的純量表與折線 | 不保留，組合物件算完即丟 |
| Freqtrade（[回測輸出](https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/optimize/optimize_reports/optimize_reports.py)、[FreqAI 滑動視窗](https://www.freqtrade.io/en/stable/freqai-running/)） | 全部成交、`daily_profit` 日彙總、週期分組 | FreqAI 依 `train_period_days`／`backtest_period_days` 滑動重訓 | 不存逐根權益，只有日彙總 |
| [QuantConnect LEAN](https://quantconnect.com/docs/v1/algorithm-reference/charting) | — | 圖表每張上限 4,000 點，超過要降低取樣頻率 | 圖表一律取樣 |
| NautilusTrader | 報表是訂單、成交、部位、帳戶表 | 沒找到官方 walk-forward 報表（只有社群專案） | — |

共通點：每個視窗一列摘要（區間、選定參數、IS 分數、OOS 績效），細節按需展開；沒有工具在報告裡保存逐根標籤或逐根歸屬；曲線一律取樣。CatOS 不照搬兩件事：AmiBroker 的 OOS 權益串接（CatOS 明訂各窗獨立、不是連續投資組合），以及 TradeStation 的自動通過門檻（CatOS 明訂驗證不是部署門檻）。

### 採用的瘦身方案（結果 schema 升為 v2）

| 部分 | 做法 | 理由 |
| --- | --- | --- |
| 逐根環境標籤 | 改為七類環境的 K 線數（`label_counts`） | 實測改成區間（run-length）也有 3,540 段（lookback 4），不夠小；逐根標籤可由綁定的資料與規則重算 |
| 逐根分環境歸屬 | 只留各環境彙總與核對結果 | 彙總就是報告要呈現的內容；核對仍以全部 K 線計算 |
| 各窗 OOS 權益曲線 | 超過 1,000 ÷ 視窗數點才取樣，沿用 `sample_curve_indices`，另保留起點 | 與回測曲線取樣同一方法；合成資料不會觸發 |
| 來源快照 | `data/okx` 下的檔案只記路徑與 sha256 | 原本每份結果都內嵌 400 KB 的 K 線；資料已由 manifest 雜湊固定 |
| HTML 報表 | 改成摘要表 | 原本把整份 JSON 轉義後塞進報表，比結果本身還大 |
| 成交、資金費、訓練格點 | 不動 | 是 OOS 結果的證據；最壞情況量過仍在上限內 |

合成資料的結果除了去掉 `labels`、`intervals` 並加上 `label_counts`、`omitted_detail` 外，欄位與數值和 v1 完全相同（有測試逐欄核對）。欄位說明見 [驗證 API 契約](research-validation-api.md) 的「v2 輸出」。

另外加了送出前的計算量檢查：`windows × (候選數 × (warmup + train) + warmup + test)` 不得超過 250,000。實測有合法請求會超過 30 秒逾時（8 窗 × 11 候選 × 8,000 根訓練，程序內 36.7 秒）；同一台筆電每秒約 1.9～5.4 萬根（隨當下負載變動），以最慢的速度算，250,000 約 13 秒。

環境分類器的成本不在這個公式裡：每根 K 線都要加總整個回看窗，共約 (K 線數 − 回看根數) × 回看根數 步，本機每秒約 240 萬步。獨立驗收發現回看根數設到資料長度的一半（4,320）時，光分類就要 8 秒多（驗收觀察 O1）。所以回看根數上限改為 512（工作包 C 放寬 `MAX_BARS` 之前的實際上限是 511），8,640 根上分類最多約 1.8 秒，換成 20,000 根的資料集也只有約 1,000 萬步。最慢的合法請求（計算量邊緣加回看 512）以研究服務實測 8.29 秒。

### 實測（本機，真實資料集）

量測設定（任務指定）：period 8~32 步進 8、train 2000、test 1000、6 窗、max_candidates 4、max_runs 30、warmup 32、1 張、本金 10,000。

| 量測 | v1 | v2 |
| --- | --- | --- |
| Worker 輸出（payload＋報表） | 14,085,346 bytes | 605,985 bytes |
| 其中 payload | 5,916,864 | 599,397（來源快照 147,261，結果 449,460） |
| 其中 HTML 報表 | 8,168,455 | 6,561 |
| 程序內耗時 | 2.39 秒 | 2.06 秒 |

研究服務實測（`tests.integration_http_fixture` 起在隔離的 18870、獨立輸出目錄，以 HTTP 送出，與前端相同路徑；結束後確認埠已釋放）：

| 請求 | 任務耗時（started → finished） | result.json | report.html |
| --- | --- | --- | --- |
| 量測設定 | 4.35 秒（送出到完成 5.0 秒） | 599,573 bytes | 9,972 bytes |
| 計算量邊緣：SMA 2~32 步進 3（11 候選）、train 2700、test 200、8 窗（242,272） | 7.72 秒 | 557,025 bytes | 12,371 bytes |
| 最慢：同上，再把回看根數設為上限 512 | 8.29 秒（送出到完成 9.06 秒） | 555,953 bytes | 9,784 bytes |
| 輸出最大：SMA 2~26 步進 2（13 候選）、train 1（各候選分數平手，每窗都選 period 2）、test 1230、7 窗、本金／手續費率／滑價用最長合法小數（4,398 筆 OOS 成交） | 1.88 秒 | 1,386,134 bytes | 13,042 bytes |

輸出最大的情況離 2,000,000 bytes 上限約 0.6 MB；獨立驗收用類似設定量到 1,420,576 bytes（驗收觀察 O2）。原本列的「成交最多」案例（2,591 筆、988,759 bytes）不是最壞情況。

表中 byte 數是在這台筆電的工作樹上量的，那裡還有舊的 CRLF 檔；來源快照內嵌檔案內容，每個 `\r` 在 JSON 多 2 bytes，所以乾淨 clone 的 result.json 約少 4.4 KB（驗收觀察 O3）。耗時隨負載變動：獨立驗收在同一台筆電量到 2.61／6.32／1.94 秒（前三列）。

量測設定的結果：6 窗都完成，每窗都選 period 32；OOS 報酬 -0.79%、-0.73%、+0.04%、-0.57%、-1.04%、-0.29%，6 窗只有 1 窗為正。前端預設設定（2 張、本金 1,000、train 2152、test 1076、6 窗）在瀏覽器實際送出：6 窗都選 32，OOS 報酬 -4.76% ~ -16.53%，全部為負。樣本外檢驗與樣本內優化的結論一致：SMA 在這 90 天被手續費拖累。

### 前端

新增「滾動驗證」頁（`#/validation`，側欄「策略與研究」）：沿用優化頁的版型（左側任務清單與邊界說明、右側結果），送出對話框帶資料集選擇、候選週期、滾動計畫與分類規則，並即時顯示使用根數、回測次數與計算量；超出上限、回看根數超過 512，或兩個小數門檻格式不對時，列出原因並停用送出（小數用字串比較，不轉浮點）。結果有四格摘要、各窗表、點選後的該窗 OOS 權益曲線、訓練格點（含鄰域分數）與分環境表。版面沿用既有頁面，沒有新的版面選擇需要定案。

優化頁與驗證頁的任務清單、共用忙碌槽輪詢與送出邏輯抽成 `hooks/use-research-runs.ts`，優化頁行為不變（隔離環境實際送出一次優化確認）。

### 未涵蓋

- 輸出上限仍是 2 MB 的硬上限：成交筆數隨 OOS 根數成長，換成更長的資料集（`MAX_BARS` 20,000）且選到短週期時仍可能超過，屆時任務以 `research_output_limit` 失敗。
- 計算量上限依本機速度訂定，沒有在另一台機器上量過。
- 前端分類規則的預設值沿用合成示範門檻（高波動 250 bps），在 BTC 15m 上幾乎都會被分到低波動；門檻要使用者自行明示。
- HTML 報表沒有前端入口（既有缺口）。

## 第二個策略：Donchian 通道突破（2026-11-04，分支 `feat/research-second-strategy`）

尚未獨立驗收。只有開發者自測，未 push、未 merge。

### 為什麼換、怎麼選

滾動驗證的 SMA 量測（上一節的量測設定）拆開來看，6 窗選出的週期都是允許上限 32；582 筆成交的手續費 236.39 USDT，加上估計滑價約 94.56（由手續費反推名目再乘 2 bps），交易成本約 331，佔淨損 338.51 的 98%，扣掉成本的價格損益約 -3.86。問題主要是交易太頻繁，不是方向判斷。

候選比較（外部資料由研究子代理查找，其中 4 個關鍵來源另行開啟核對；選定前沒有在這 90 天資料上試跑任何候選，避免看過結果再挑）：

| 候選 | 類型 | 外部證據 | 交易頻率 | 實作成本 |
| --- | --- | --- | --- | --- |
| A. Donchian 通道突破 | 順勢（突破） | 最強：多組回看期的 Donchian 集成扣費後 Sharpe > 1.5（[Zarattini、Pagani、Barbon 2025](https://ideas.repec.org/p/chf/rpseri/rp2580.html)）、區間突破在 7 種規則中最好（[Gerritsen 等 2020](https://research-portal.uu.nl/en/publications/the-profitability-of-technical-trading-rules-in-the-bitcoin-marke/)）；反例是上萬條規則在 BTC 樣本外沒有預測力（[Hudson & Urquhart 2021](https://ideas.repec.org/a/spr/annopr/v297y2021i1d10.1007_s10479-019-03357-1.html)）。證據都在日線 | 低 | 只比大小，Decimal 精確；不改研究核心 |
| B. 布林通道均值回歸 | 逆勢 | 弱：BTC 下一根 15m 的反轉毛利最多約 1.3 bp／筆，低於來回成本（[Kitron & Wengrowicz，預印本](https://arxiv.org/html/2608.21888v1)） | 中高 | 平方比較，不必開根號 |
| C. 時間序列動能 | 順勢（報酬門檻） | 中：日～週動能有證據，盤中結論不一致 | 低～中 | 精確；和 SMA 同家族 |
| D. 資金費率逆勢 | 逆勢 | 弱：對下一個 8 小時報酬的 R² 約 0.001～0.017 | 很低 | 要把資金費交給策略，改研究核心介面 |

開源框架的範例也有這類策略：Jesse 的 [Donchian、TurtleRules](https://github.com/jesse-ai/example-strategies)，NautilusTrader v1.231.0 的 [bb_mean_reversion](https://raw.githubusercontent.com/nautechsystems/nautilus_trader/v1.231.0/nautilus_trader/examples/strategies/bb_mean_reversion.py)（檔頭寫明沒有優勢、只供測試）。2026-11-04 使用者選定 A。

### 規則

每根收盤決策、下一根開盤加滑價成交，固定張數，淨部位多空（`catos/research_donchian.py`）：

- 進場通道是前 `entry_bars` 根（不含正在決策的這一根）的最高價與最低價；收盤高於最高價做多、低於最低價做空，反向部位直接反手。
- 出場通道是前 `exit_bars` 根的最低價（多單）或最高價（空單）；收盤跌破就平多、突破就平空。
- 其餘情況維持部位。`exit_bars` 必須小於 `entry_bars`，所以出場一定比反手先觸發；預熱至少 `entry_bars` 根。
- 通道用單調佇列維護，每根 O(1)，只做 Decimal 比大小，沒有任何算術捨入。

### 實作

- 研究端改成固定白名單兩個策略（`catos/research_catalog.py` 的 `STRATEGIES`）：各自釘住 id、version、entry、sha256、來源檔、manifest 與參數範圍。回測、優化、滾動驗證都依 `strategy_id` 驗證參數並載入對應策略；不是通用插件框架。
- Donchian 參數：`entry_bars` 2～960（10 個 15m 天）、`exit_bars` 1～959；搜尋範圍要讓每個格點都合法，所以 `exit_bars` 的最大值須小於 `entry_bars` 的最小值。預熱 ≥ 最高的 `entry_bars`，計算量仍受 250,000 根次預算限制。SMA 的範圍與錯誤訊息不變。
- manifest 放在 `catos/research_only_artifacts/`。Worker 登錄表 `catos/strategy_registry.py` 只讀 `catos/research_artifacts/*.json`，所以 local-sim Bot 與 IPC（`WorkerConfig.from_wire`）解析不到 Donchian，測試有涵蓋。
- 研究服務送出時依請求的策略計算來源綁定，完成時再核對一次；請求與綁定的策略不同時以 `strategy_source_mismatch` 拒絕。
- 優化與滾動驗證的 HTML 報表改為通用的「參數」「選定參數」欄；優化報表不再寫死「合成資料樣本內搜尋」，改用資料集的聲明（原本的已知缺口）。

### 實測（本機，研究服務，真實資料集）

`tests.integration_http_fixture` 起在隔離的 18870、獨立輸出目錄，以 HTTP 送出（與前端相同路徑），結束後確認埠已釋放。帳戶 1 張、本金 10,000、手續費率 0.0005、滑價 2 bps；最後一列是前端預設值，從瀏覽器送出。

| 請求 | 任務耗時（started → finished） | result.json | report.html |
| --- | --- | --- | --- |
| 回測 entry 192／exit 48、預熱 192 | 0.75 秒 | 686,169 bytes | 151,629 bytes |
| 優化 entry 96~384/96 × exit 24~72/24（12 格點）、20 trials | 4.26 秒 | 13,254 bytes | 25,782 bytes |
| 滾動驗證，同上 12 格點、預熱 384、train 2000／test 1000／6 窗（與 SMA 量測同計畫） | 4.85 秒 | 556,397 bytes | 10,377 bytes |
| 計算量邊緣：entry 96~960/96 × exit 24~48/24（20 格點）、預熱 960、train 4000／test 1800／2 窗（203,920） | 5.25 秒 | 471,763 bytes | 7,159 bytes |
| 前端預設：12 格點、2 張、本金 1,000、train 2064／test 1032／6 窗（184,752） | 5.17 秒 | 562,531 bytes | 10,365 bytes |

和 SMA 同計畫的比較（Donchian 預熱 384 根、SMA 32 根，所以 OOS 視窗起點晚 352 根，約 3.7 天，期間不完全相同）：

| | SMA period 8~32/8 | Donchian 12 格點 |
| --- | --- | --- |
| 各窗選出參數 | 6 窗都是 32（範圍上限） | 288/24 ×3、96/24、96/72、384/24 |
| 成交筆數 | 582 | 55 |
| 手續費 | 236.39 | 24.28 |
| 估計滑價 | 94.56 | 9.71 |
| 資金費（正為支出） | 3.70 | -0.33 |
| 扣成本前的價格損益（估計） | -3.86 | -24.86 |
| 淨損益（6 窗合計，各窗獨立） | -338.51 | -58.52 |
| 正報酬視窗 | 1／6 | 2／6 |

Donchian 各窗 OOS 報酬：-0.015%、+0.140%、-0.075%、-0.281%、-0.393%、+0.038%。前端預設（2 張、本金 1,000）在瀏覽器送出：-0.72%、+10.07%、-8.42%、-6.64%、-2.30%、-1.07%，6 窗 1 窗為正。

結論：Donchian 把交易成本降到 SMA 的約十分之一（331 → 34 USDT），淨損從 338.51 降到 58.52；但扣掉成本前的價格損益仍是負的，各窗選出的參數也不穩定（4 種組合）。在這 90 天、15m、單一合約的設定下，Donchian 沒有顯示出值得上線的優勢。

### 前端

回測、優化、滾動驗證三個送出對話框都加了策略選擇（`components/catos/strategy-picker.tsx`），參數欄位依 catalog 的參數表產生，切換策略或資料集時套用預設值。Donchian 在合成資料上用短通道（回測 6／3；搜尋 4~8/2 × 2~3/1），在 OKX 資料上用 1～4 天的進場通道、6～18 小時的出場通道（回測 192／48；搜尋 96~384/96 × 24~72/24）。三個對話框都會在送出前列出問題並停用送出（例如出場通道沒有小於進場通道）。任務清單、結果摘要與表格改顯示 `name=value` 的參數組。共用邏輯在 `lib/research-strategies.ts`；`lib/validation-plan.ts` 改為多軸格點。

### 未涵蓋

- 只有 90 天、單一合約、單一週期；每個 OOS 視窗只有 6～16 筆成交，雜訊大。
- 這 90 天已經被 SMA 用過，不是全新的保留資料。
- 固定張數，沒有依波動調整部位，也沒有停損、保證金與強平模型。
- SMA 的週期上限 32 根沒有放寬；若要確認 SMA 是否只輸在週期太短，需要另外放寬再量。
- 外部證據多在日線以上，這裡是在 15m K 線上做 1～4 天的通道。
