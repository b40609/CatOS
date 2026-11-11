# 研究線工作包 C（真實歷史 K 線研究）獨立驗收報告

- 日期：2026-11-04（Asia/Taipei）
- 驗收者：Claude Opus 5.5，獨立驗收會話（筆電）。沒有撰寫本工作包任何 commit，具 AGENTS.md「DEVELOPMENT WORKFLOW」所定的獨驗資格。開發者是另一個 Claude 會話。
- 範圍：`feat/research-real-data` 的 `fc63f2f..7c90133`，1 個 commit，19 個檔案（+1259／−278）。
- 結論：**PASS（6／6）**，附 8 項非阻斷觀察。依指示只 commit 本報告，不合併 main、不 push。

## 驗收限制與隔離

- **沒有對 OKX 發出任何請求。**
  - 抓取工具以自寫的離線腳本測試：先把 `urllib.request.urlopen` 換成觸發即報錯的絆線，再注入假 opener。
  - 真實資料集只做唯讀核對。
- **沒有修改 `data/okx`。**
  - 竄改測試都在暫存副本上進行。
  - 瀏覽器實測時，把資料集複製到乾淨 clone 的 `data/okx` 下使用。
  - 驗收結束時，四個原始檔的 sha256 與修改時間（12:11:38）都沒有變。
- **重跑都在乾淨 clone 上做**：`git clone -b feat/research-real-data`，HEAD `7c90133`。
  - 前端以 `npm ci` 全新安裝。
  - Python 使用 repo 的 `.venv`（3.12.10），Node 使用 24.19.0。
- **瀏覽器實測**：在隔離的 18870／18890 上，以全新的 fixture 資料根進行；用完關閉，並確認兩個埠都已釋放。
- **沒有碰** 8770／8771／8890、既有資料根或憑證。

## 總表

| # | 項目 | 結果 |
| --- | --- | --- |
| 1 | 採集安全與授權範圍 | PASS（附觀察 O1） |
| 2 | 資料完整與 fail-closed | PASS（附觀察 O2、O3） |
| 3 | 研究正確性 | PASS（附觀察 O4） |
| 4 | Decimal 紀律 | PASS（附觀察 O5） |
| 5 | 前端 | PASS（附觀察 O6） |
| 6 | 文件與 AGENTS.md 授權條 | PASS（附觀察 O7、O8） |

## 1. 採集安全與授權範圍：PASS

### 程式核對（`tools/fetch_okx_candles.py`）

- **端點白名單**：`Client.get` 只接受 `datasets.ENDPOINTS` 這三個路徑（`/api/v5/market/history-candles`、`/api/v5/public/funding-rate-history`、`/api/v5/public/instruments`），其他路徑丟 `endpoint_not_allowed`，而且不計入請求數。`BASE_URL` 固定為 `https://www.okx.com`。
- **沒有認證**：`urlopen_json` 只設 `User-Agent: catOS-research/1.0`；全檔沒有任何金鑰、簽名、`OK-ACCESS-*` 標頭，也沒有帳戶或交易端點。
- **限速與上限**：
  - 兩次請求之間至少 `MIN_INTERVAL_S = 0.25` 秒。
  - 每次嘗試（包括重試）都計入 `requests`，達到 `max_requests` 就停止。
  - 預設上限 150，見觀察 O1。
- **重試與停止**：
  - 重試：HTTP 429、HTTP 5xx、OKX `50011`、`URLError`／`OSError`，以 1、2、4 秒退避，最多重試 3 次。
  - 立即停止：其他 4xx，以及 OKX 其他錯誤碼。
  - 分頁 `_check_page` 要求每頁最多 100 筆、時間嚴格早於游標、遞減且不重複；範圍內出現 `confirm != "1"`、OHLC 越界、合約不符或資料形狀不符時，一律停止。
  - 所有檢查都通過後，才由 `write_dataset` 寫檔：先寫入暫存目錄，再用 `os.replace` 一次換上，並拒絕覆寫既有資料集。

### 離線實測（自寫 `fetch_offline.py`，假 OKX，`urlopen` 換成絆線）

| 案例 | 結果 |
| --- | --- |
| 2 天完整抓取 | exit 0，4 次請求，寫出 1 個資料集，最小請求間隔 0.25 秒 |
| 實際用到的端點 | 只有上述三個；URL 中沒有 apikey、sign、passphrase |
| 送出的請求標頭 | `{'User-agent': 'catOS-research/1.0'}` |
| HTTP 429 一次後成功 | exit 0，退避 [1] 秒 |
| HTTP 503 兩次後成功 | exit 0，退避 [1, 2] 秒 |
| OKX 50011 一次後成功 | exit 0，退避 [1] 秒 |
| HTTP 403 | 第 1 次請求後停止，`http_403`，沒有寫檔 |
| OKX 錯誤碼 51000 | 停止，`okx_error 51000`，沒有寫檔 |
| 連續 4 次 503 | 退避 [1, 2, 4] 秒後停止，`retries_exhausted`，沒有寫檔 |
| 上限 3 次（需要 4 次） | 停止，`request_budget_exhausted: 3`，沒有寫檔 |
| 範圍內有未收盤 K 線 | 停止，`unclosed_candle_in_range` |
| OHLC 越界 | 停止，`invalid_ohlc_bounds` |
| 分頁沒有早於游標 | 停止，`pagination_unexpected` |
| `/api/v5/account/balance`、`/api/v5/trade/order` | `endpoint_not_allowed`，請求數 0 |
| 網路錯誤（`OSError`）一次後成功 | 重試成功，共 2 次請求 |

整個測試過程中絆線沒有被觸發，代表沒有任何真實網路呼叫。

### 授權範圍與 manifest 紀錄（真實資料集，唯讀）

| 項目 | 授權 | manifest 與實測 |
| --- | --- | --- |
| 合約與週期 | BTC-USDT-SWAP、15m | `inst_id` BTC-USDT-SWAP、`bar` 15m、`timeframe_ms` 900000 |
| 區間 | 90 天 | [2026-08-06 04:00, 2026-11-04 04:00) UTC，剛好 90.0 天 |
| 請求數 | 單次最多 150 | `requests` 91，等於 K 線 87 頁（8,640 根，每頁 100 筆，最後一頁跨過起點）＋資金費 3 頁（270 筆）＋合約 1 次 |
| 端點 | 三個公開端點 | `endpoints` 與白名單完全一致 |
| 存放 | 只在本機 `data/okx/`，git 忽略 | `.gitignore:29 /data/` 命中 |
| 抓取時間 | — | `fetched_at_ms − end_ms = 676 秒`，符合「終點為最後一根已收盤 K 線的 15 分鐘對齊點」 |

`instrument.json` 是 OKX 公開合約資料，內容沒有任何帳戶資訊。

## 2. 資料完整與 fail-closed：PASS

### 真實資料集（自寫 `dataset_raw_check.py`，`python -I` 唯讀）

```text
range: 2026-08-06 04:00 -> 2026-11-04 04:00 | days: 90.0 | fetched - end (s): 676.085
hash candles.csv OK / funding.csv OK / instrument.json OK
bars: 8640 == manifest 8640 | exact grid: True | closed all 1: True | bad OHLC: 0 | off-tick: 0
funding events: 270 == manifest 270 | intervals: {28800000} | first-start (h): 4.0 | end-last (h): 4.0
  | all on bar grid: True | realized==funding: True
rate min/max: -0.0000471724574553 0.0001 | negative events: 21
```

- K 線落在完整的 15 分鐘格點上，沒有缺口。
- 資金費每 8 小時一筆，頭尾都在一個間隔內，覆蓋完整。

### `load_manifest` 的檢查（`catos/research_datasets.py`）

- 欄位集合必須完全相同；拒絕重複鍵與非整數數值。
- schema、source、`dataset_id` 格式、目錄名稱、區間與根數一致性、端點清單、`gaps == []`、`funding.complete == True` 都會核對。
- 重算三個檔案的 sha256；`contract` 必須等於由 `instrument.json` 推導出的結果。
- 拒絕 symlink 與資料根以外的路徑。
- `write_dataset` 只接受 linear、USDT 結算的 SWAP（`contract_from_instrument`），並拒絕缺口、資金費不規則或不完整，以及覆寫既有資料集。

### 暫存副本竄改測試（自寫 `dataset_tamper.py`）

| 竄改 | 結果 |
| --- | --- |
| 未改動的副本 | 接受，並能載入 K 線與資金費 |
| candles 改一個價格數字 | `dataset_hash_mismatch` |
| candles 改成 CRLF | `dataset_hash_mismatch` |
| candles 刪一列並重算雜湊 | 載入時被拒：`candles must be ordered and contiguous; gaps are not filled` |
| funding 改一個費率 | `dataset_hash_mismatch` |
| 刪除 funding.csv | `dataset_file_missing` |
| instrument.json 的 tickSz 0.1 改成 0.01 | `dataset_hash_mismatch` |
| 同上並重算 instrument 雜湊 | `contract_instrument_mismatch` |
| manifest 的 contract.lot_size 改成 1 | `contract_instrument_mismatch` |
| manifest 的 bars 8640 改成 8639 | `dataset_range_invalid` |
| manifest 多一個欄位 | `manifest_fields_mismatch` |
| manifest 的 gaps 非空 | `dataset_has_gaps` |
| manifest 的 funding.complete 改成 false | `funding_incomplete_or_unsupported` |
| manifest 的 endpoints 加上帳戶端點 | `dataset_endpoints_mismatch` |
| manifest 數值寫成浮點（8640.0） | `manifest_non_string_number` |
| manifest 重複鍵 | `manifest_duplicate_key` |
| manifest 的 dataset_id 改名 | `dataset_directory_mismatch` |
| 把 `DATA_ROOT` 指到竄改後的根目錄 | `list_datasets` 回報 valid 為空、rejected 為 `dataset_hash_mismatch`；`resolve_dataset` 回 `unknown_dataset` |
| 只改 manifest 的 `requests` 或 `fetched_at_ms` | 接受（見觀察 O2） |

### 執行期再驗證

- 一次回測至少四次經由 `list_datasets → load_manifest` 重算雜湊：`validate_request`、`load_registered_strategy`、`load_dataset_bars`，以及執行後的 `provenance(dataset_id)`。
- 執行中若有檔案被改動，結束時會因 `source_changed_during_run` 被拒絕。

## 3. 研究正確性：PASS

### 程序內實跑（自寫 `research_real_check.py`）

在真實資料集上直接呼叫 `research_catalog.execute_request`（period 20、1 張、本金 10000、warmup 20），再獨立重算：

```text
run 0.60s | output bytes 856,473 | sampling {'total_points': 8621, 'returned_points': 1725, 'method': 'bucket_deepest_drawdown'}
perf: return_pct -5.669437…, max_drawdown_pct 6.119392…, fees 415.0442385, funding_paid 5.9245164791516333804, trade_count 1062
contract used: ContractSpec(inst_id='BTC-USDT-SWAP', base_per_contract=0.01, tick_size=0.1, lot_size=0.01, min_size=0.01)
trades: 1062 | prices off 0.1 tick: 0 | qty multiples of lot: True
funding payments: 269 == events after warmup 269 | marks == bar open: True | sum paid == recomputed == perf funding_paid (5.9245164791516333804)
payments with open position: 141 | sign check (long & rate>0 => paid>0): True
sampled points dd/eq: 1725 1725 | aligned times: True
max dd sampled == perf max_drawdown: 6.1193921968976933659132380222603097238305104438884
last equity point == final equity: 9433.0562450208483666196
synthetic provenance == legacy shape: True
validation on real dataset: validation_supports_synthetic_dataset_only
```

- **合約規格**：
  - `validate_request` 以 `dataset.contract` 與 `dataset.timeframe_ms` 建立 `BacktestConfig`，回測確實使用 tick 0.1、lot 0.01、ctVal 0.01。
  - 1,062 筆成交價都落在 0.1 tick 上，數量都是 lot 的倍數。
  - `research.py` 的 K 線驗證也要求價格是 tick 的倍數，真實資料全部通過。
- **資金費**：
  - `research._Ledger.fund` 的公式是 `position × base_per_contract × mark × rate`，多倉在正費率時付費；mark 取結算當下那根 K 線的開盤價（`Dataset.load`），並在該根開盤成交之前結算。
  - 預熱期（第 1 根到第 20 根）的第一筆資金費（開始後第 4 小時）沒有計入，所以 269 筆等於 270 筆扣掉 1 筆，邏輯正確。
  - 獨立重算的總額與 `funding_paid` 完全相同。
- **取樣**：
  - `sample_curve_indices` 每段保留回撤最深的一點，最後一點也保留。
  - 取樣後的最大回撤等於績效裡的最大回撤；期末權益點也保留下來。
  - 績效數字在取樣前，就已經以全部 8,621 點計算完成。
- **provenance**：
  - 合成資料的 `provenance()["dataset"]` 仍是 `{id, source: "synthetic_closed_bars", sha256}`，與舊版形狀完全相同。
  - 本機模擬路徑（`worker.py` 呼叫沒有參數的 `provenance()`）不受影響；整合測試 9/9 證實本機模擬照常運作。
  - `engine_sha256` 因為 `ENGINE_FILES` 加入 `research_datasets.py` 而改變，這是預期的。
- **研究服務**：
  - `ResearchService` 以請求中的 `dataset_id` 計算 provenance：回測取頂層，優化與驗證取 `backtest` 裡的值。
  - `_run` 結束後用同一個資料集重新核對來源。
  - 實際送出後，run 清單記錄的 `dataset_id` 就是所選的資料集（見第 5 項）。
- **驗證在送出時拒絕**：`validate_validation_request` 在 `submit_validation` 階段就丟出錯誤。HTTP 實測回 422 `{"detail":"validation_supports_synthetic_dataset_only"}`，之後 run 清單只有回測與優化兩筆，沒有建立驗證工作。

### 程序內優化（自寫 `opt_real_check.py`）

在真實資料集上跑 period 8~32、7 個試驗、seed 42：1.9 秒、輸出 6 KB，provenance 指向所選資料集，`data_notice` 也串上了資料集說明。

## 4. Decimal 紀律：PASS（附觀察 O5）

- 後端新增的程式全部用 Decimal：價格與費率以 `_price`、`_rate`、`_positive_decimal` 驗證，manifest 拒絕浮點數；取樣用 Decimal 回撤值比較；資金費在 `Dataset.load` 以 `Decimal(row[1])` 建立。
- 前端：
  - 回測頁的總回報、淨損益、最大回撤、本金、期末權益，以及優化表的分數、淨損益、手續費、回撤，都改用 `formatDecimal`／`formatDrawdownPct`。
  - 正負色改用 `signOf`，取代原本的 `parseFloat`。
  - 權益 tooltip 用原始字串 `equityText` 經 `formatDecimal` 顯示，實測為「$9,796.89 USDT」。
- 剩下的浮點只用在三處，都可以接受：
  - `backtest-underwater-chart.tsx` 的圖形座標（`parseFloat` 轉成繪圖用數值）。
  - Y 軸刻度：`toFixed(0)`、`toFixed(1)%`。這只是刻度標籤，不是任何績效數字。
  - 回撤 tooltip（見觀察 O5）。
- `formatDrawdownPct`：會加上負號；捨入到兩位後若是 0，則顯示「0.00%」；格式不合時回傳 fallback。

## 5. 前端：PASS（附觀察 O6）

- `DatasetPicker`（`components/catos/dataset-picker.tsx`）是單選清單（`role="radiogroup"`），下方顯示所選資料集的 `notice`。`pickDataset` 遇到未知 id 時，退回第一個資料集。
- 瀏覽器實測回測頁：

| 步驟 | 結果 |
| --- | --- |
| 開啟對話框 | 兩個選項：「合成 BTC 15m · 96 根已收盤 K 線」（預設選取）與「OKX BTC-USDT-SWAP 15m · 2026-08-06 ~ 2026-11-04 · 8,640 根已收盤 K 線（含資金費）」 |
| 選 OKX | `aria-checked` 切換；說明改成 OKX 資料集的 notice（mark price 近似、沒有保證金與強平模型） |
| 送出（period 20、1 張、本金 10000、預熱 20） | 總回報 -5.67%、淨損益 -566.94 USDT、最大回撤 -6.12%、1062 筆、本金 10,000.00 USDT、期末 9,433.06 USDT，與第 3 項程序內重算一致 |
| 圖表 | 標示「圖表取樣 1,725 / 8,621 點」，並顯示資料集 notice；多日資料的 X 軸改用 `MM/DD` |
| 資金費列 | 「資料集實際費率（本次 5.9245 USDT） · 期末估值平倉」 |
| 月度頁籤 | 「月度收益矩陣尚未實作」 |
| 全頁 | 沒有 NaN 或 undefined |

- 瀏覽器實測優化頁：選 OKX 資料集、period 8~32、7 個試驗、seed 42。
  - 狀態為 COMPLETE；最佳是 #1，period 31，-81.97%。
  - 表格以兩位小數顯示分數、淨損益、手續費與回撤，`title` 保留完整的 Decimal 字串。
  - 沒有 NaN 或 undefined。

## 6. 文件與 AGENTS.md：PASS（附觀察 O7、O8）

- AGENTS.md AUTONOMY 新增的授權條，與使用者授權範圍、程式和 manifest 一致：三個公開 GET 端點、BTC-USDT-SWAP、15m、90 天、`--end-ms` 重抓、0.25 秒、150 次、`data/okx/`、只做單一合約的回測與優化。
- README：
  - 「研究資料」列和「研究資料」段的敘述，與第 1、2 項實測相符：只接受雜湊相符、沒有缺口、資金費完整的資料集；滾動驗證只接受合成資料；遇到缺口、未收盤、分頁不符或資金費不完整就停止、不寫檔。
  - README 的 `--end-ms 1793764800000` 等於 manifest 的 `end_ms`。
- `docs/research-real-data-plan.md` 的實作紀錄中，區間、8,640 根、270 筆資金費、合約規格、`realizedRate` 與 `fundingRate` 相同、回測績效數字，都與本輪實測相符。不符的只有優化數字（觀察 O7）。
- 後端模組文件字串與 MCP instructions，都已改成「登錄資料集（合成或經雜湊核對的 OKX 公開歷史）」。

## 實際執行的命令與結果

`<clone13>` 指 `7c90133` 的乾淨 clone，`<fe>` 指 `<clone13>/frontend/cat-os-vite`。

| 命令 | 位置 | 結果 |
| --- | --- | --- |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"` | `<clone13>`（沒有 `data/okx`） | `Ran 1388 tests in 239.103s`、`OK (skipped=11)`。這台機器這次能建立 symlink，所以 `test_lot_scenario_demo` 的 symlink 測試實際跑過並通過，skip 少 1 個，符合 README 的「11 或 12」 |
| `npm ci --no-audit --no-fund` | `<fe>` | exit 0 |
| `npm run typecheck` | `<fe>` | exit 0 |
| `npm test` | `<fe>` | `check:tokens OK`；tests 11、pass 11、fail 0 |
| `npm run build` | `<fe>` | exit 0，`✓ built in 12.04s` |
| `node tests/simulation_integration_test.mjs <.venv python>` | `<fe>` | exit 0，9 PASS；證據 `%TEMP%\catos-sim-integration-cLTDRi` |
| `fetch_offline.py`（自寫，離線） | repo 根目錄 | 14 個案例全部 PASS；絆線沒有觸發 |
| `dataset_raw_check.py`（自寫，唯讀） | repo 根目錄 | 輸出見第 2 項 |
| `dataset_tamper.py`（自寫，暫存副本） | repo 根目錄 | 輸出見第 2 項 |
| `research_real_check.py`、`opt_real_check.py`（自寫） | repo 根目錄 | 輸出見第 3 項 |
| 瀏覽器實測回測與優化頁（`serve-check.mjs`；資料集複製到 `<clone13>/data/okx`） | 18870／18890 | 見第 5 項 |
| `curl -X POST /api/research/validations`（真實資料集） | 18870 | HTTP 422 `validation_supports_synthetic_dataset_only`，沒有建立工作 |

## 非阻斷觀察

- **O1（抓取範圍靠授權約束）**：工具接受任何 `<BASE>-USDT-SWAP`、`1m`～`4H`、1～365 天，而 `--max-requests` 雖然預設 150，卻沒有硬上限。授權範圍要靠使用規則遵守，程式不強制。README 寫「單次最多 150 次請求」，嚴格來說只是預設值。建議把 `--max-requests` 夾在 150 以內，或把文件改成「預設 150」。
- **O2（manifest 是信任根）**：
  - 只改 manifest 的中繼欄位（`requests`、`fetched_at_ms`）不會被拒絕，不過 provenance 裡 manifest 的雜湊會跟著改變。
  - 同時改 `instrument.json`、manifest 的 `contract` 與雜湊也能通過。這與策略登錄的模式相同，防的是意外損毀，不防刻意偽造，符合 P1 受信邊界。
- **O3（被拒的資料集不會顯示）**：`list_datasets` 回傳的 rejected 清單沒有被 catalog 或 UI 使用。資料集被拒時只會從清單消失，使用者看不到原因。
- **O4（取樣偏向低點）**：
  - 每段（約 5 點）只保留回撤最深的一點，所以權益曲線會系統性略去區段內的高點，第一個點也可能被略過。
  - 績效數字不受影響，最大回撤點與期末點都有保留；只是圖形會略偏向低點。
- **O5（回撤 tooltip 仍是浮點文字）**：`backtest-underwater-chart.tsx:193` 的回撤 tooltip 是 `${v.toFixed(2)}%`，`v` 來自 `parseFloat`，屬於既有程式，不是本範圍新增。開發者描述的「圖表 tooltip 顯示原始 Decimal 字串」只適用於權益 tooltip。兩位小數的顯示值是正確的。
- **O6（靜態標籤）**：
  - 回測頁頂部固定顯示「127.0.0.1:8770 ONLINE」，在隔離埠下也一樣（既有）。
  - `research_api.py` 的 `/api/research/version` 仍回傳 `mode: "local_research_synthetic"`，現在已經有真實資料集，這個名稱不準確（不在本範圍內）。
- **O7（優化實測數字無法重現）**：
  - 方案文件寫「最佳是 period 32，報酬 -80.16%」。
  - 本驗收者以 UI 的相同設定（period 8~32、7 試驗、seed 42、本金 1000、2 張），在瀏覽器與程序內各跑一次，結果都是 period 31、-81.97%。
  - 建議開發者補上當時的完整請求，或更新數字。回測數字完全一致。
- **O8（文件小落差）**：
  - `docs/next-steps.md` 第 1 點仍寫 A「待獨立驗收」，實際上 A 已經驗收並合併。
  - 方案文件寫回測「輸出 1.1 MB」，本輪 payload JSON 量到 856 KB。差異可能來自量測對象不同（例如包含報表），沒有超過上限。

## 未涵蓋

- 沒有對 OKX 實際重抓，所以「另一台機器以 `--end-ms` 重抓會得到相同雜湊」沒有驗證。真實分頁語義只能依開發者的抓取結果與 manifest 推斷。
- 沒有在不允許 symlink 的條件下重跑後端套件（本輪 skipped=11）。
- 沒有做整體視覺驗收，由使用者自行在網頁上驗收；回撤圖只用 tooltip 和刻度做抽查。
- 優化頁只跑了一組設定；滾動驗證只確認送出時會拒絕真實資料集，沒有對合成資料重跑驗證流程（這部分不在本範圍的改動內）。
