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
- **滾動驗證只接受合成資料。** 在 8,640 根上量到的輸出是 13.7 MB（逐根環境標籤 1.8 MB、各視窗權益曲線 1.8 MB、區間評估 1.8 MB，加上 8.2 MB 的 HTML 報表），超過 2 MB 上限，而且和方案大小無關。所以改在送出時就拒絕（`validation_supports_synthetic_dataset_only`），不讓它跑完才失敗。

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
- 滾動驗證輸出瘦身（標籤與曲線取樣、精簡報表），之後才能用在真實資料上。
- 月度收益矩陣（頁籤目前標示尚未實作）。
- 保證金與強平模型（目前回撤可能超過 100%）。
