# catOS：最小 Closed Bar 研究核心

目前完成單合約、單週期的純記憶體研究核心、最小 Optuna 搜尋、CSV 已收盤 K 線匯入與離線 HTML 報告。核心採 Jesse research 的介面風格與自有 Decimal Core，只用標準函式庫；搜尋另使用 Optuna，不依賴 Jesse。需要 Python 3.11+；目前在 Python 3.14.6、Optuna 4.9.0 執行驗證。

CSV 格式見 [資料匯入](docs/data-io.md)，報告介面與視覺驗收見 [研究報告](docs/reporting.md)。執行 `py -3 -B -m examples.report_demo` 可重新產出 `reports/visual-qa/synthetic-report.html`；產生的 CSV、HTML、截圖與本機資料庫不納入 Git，驗收腳本保留。此版本為已驗收的研究模組，尚非 Demo／Live 執行器。

## 執行

命令列入口（固定 SMA 示範策略，詳見 [CLI 設定契約](docs/research-cli.md)）：

```powershell
py -3 -B -m examples.report_demo
py -3 -B -m catos.research_cli --csv reports/visual-qa/synthetic.csv --config examples/research-config.json --strategy sma-trend --output reports/research.html
```

輸出已存在時拒絕覆蓋，請指定新路徑。範例 JSON 的空資金費陣列代表無資金費假設，與 `report_demo` 的非空資金費設定不同，兩份報告不可直接視為相同設定的績效。

在專案根目錄執行合成資料示範：

```powershell
py -3 -B -m examples.closed_bar_demo
```

只執行本模組的專屬測試：

```powershell
py -3 -B -m unittest discover -s tests -p test_research.py -v
```

示範以固定的合成 15 分鐘 K 線執行 SMA 多倉／空倉策略，預熱 2 根。輸出金額以十進位字串呈現；沒有下載行情、寫入資料庫或發送交易。

## 介面

```python
from catos.research import backtest

result = backtest(
    strategy=MyStrategy,  # 無參數 class／factory；每次提供全新 Strategy
    candles=closed_bars,
    config=config,
    warmup_bars=20,
)
```

`Strategy.update_indicators(bar)` 只更新指標並回傳 `None`；`ready` 表示指標是否就緒；`on_bar(bar, account)` 回傳有號目標張數 `Decimal`、`Decimal("0")` 平倉，或 `None` 維持原部位。相同目標不會反覆買入。每次 callback 只收到當前已收盤 K 線及不可變的帳戶視圖；策略自行累積所需歷史，不取得完整未來 K 線陣列。

`warmup_bars` 為輸入前段的預熱根數，必須為非負整數。前 N 根只呼叫指標更新，不呼叫交易決策、不撮合或計績效。正數預熱結束時必須已就緒；`warmup_bars=0` 時，第一根正式 K 線先更新指標再檢查就緒。正式交易決策從第 N+1 根收盤開始，不能把預熱訊號留到正式區間執行。資料須至少有一根正式 K 線；不默默縮短預熱。

## 資料與數值契約

- `Candle.open_time_ms` 為整數開盤時間，收盤時間是開盤時間加上 `timeframe_ms`。同一串資料只能有一種週期，且必須已收盤、排序、無重複、連續；缺口直接報錯，不補值。直接使用指定週期，不載入 1m 細部資料。
- 價格、目標張數、初始餘額、費率、滑價、合約規格均須由字串建立 `Decimal`；拒絕 Float、NaN、Infinity。外部 Decimal 最多 28 個係數位、最細 18 位小數、最高 adjusted exponent 18；計算使用獨立 50 位精度及 `ROUND_HALF_EVEN`，不依賴呼叫端的全域 Decimal context。
- `ContractSpec.base_per_contract` 是每張合約對應的標的幣數。名目金額為 `abs(張數) × 每張標的幣數 × 價格`。呼叫端提供正確的 USDT 線性 SWAP 規格；此處沒有查核交易所 metadata，名稱檢查也不代表已驗證實盤合約。
- OHLC 必須符合價格 tick；目標及委託差額須符合 lot／最小張數，無效數量報錯，不擅自改成另一個目標。

## 撮合與帳務假設

| 項目 | 本切片的規則 |
|---|---|
| 成交 | 本根收盤產生意圖，下一根開盤全量成交；不使用訊號根的收盤價成交 |
| 滑價 | 買入 `open × (1 + bps / 10000)`，賣出 `open × (1 - bps / 10000)`；買價向上、賣價向下取 tick 整數倍 |
| 價差 | 滑價參數表示合計執行成本，不另疊加 bid/ask spread；未建模流動性、排隊或部分成交 |
| 手續費 | `abs(成交張數) × 每張標的幣數 × 成交價 × fee_rate`，採給定的非負市價費率 |
| 淨倉 | 同向加倉更新加權成本，減倉只實現已平部分損益，反向後剩餘部位以此次成交價作成本 |
| 資金費 | 呼叫端明確提供 `FundingEvent(time_ms, rate, mark_price)`；支付額為 `有號張數 × 每張標的幣數 × mark_price × rate`，正值扣款、負值入帳 |
| 同時事件 | 資金費和開盤成交同時時，先按原有部位結算資金費，再撮合；這是固定模擬順序，非交易所逐筆時序保證 |
| 預熱資金費 | 正式起點之前的資金費事件排除；正式期事件各處理一次，不由 K 線猜費率、時間或 mark price |
| 估值 | 用指定週期收盤價估計未實現損益及權益；最大回撤只看起始權益與各根收盤，不代表盤中或 mark-price 回撤 |
| 期末 | 不強制平倉；末根的新意圖保留為 `pending_intent`，未平部位保留未實現損益 |

`funding_events` 必須明確傳入 tuple；空 tuple 表示呼叫端假設沒有資金費事件，不表示歷史資料已完整。每個事件需有唯一且遞增的時間戳，落在輸入 K 線覆蓋期間。結算 mark price 是獨立給定的事件價格，不是載入細部 K 線。

帳務關係：

```text
balance = initial_balance + realized_pnl - fees - funding_paid
equity = balance + unrealized_pnl
net_pnl = final_equity - initial_balance
```

`result.trades` 是逐筆模擬成交，並非往返交易統計。結果另含資金費分錄、權益曲線、績效、正式起訖時間、完整設定及模型假設；所有交易數值維持 Decimal。

## Optuna 最小整合

目前環境已安裝 Optuna 4.9.0；其他環境需要搜尋功能時，才執行 `py -3 -m pip install -r requirements-research.txt`。只用 backtest 不需要安裝它。

```powershell
py -3 -B -m examples.optuna_demo
py -3 -B -m unittest discover -s tests -p test_optimization.py -v
```

`catos.optimization.optimize` 使用獨立 InMemoryStorage、固定 seed 的 TPESampler 及順序 ask/tell。每個 trial 重建策略，所有 trial 共用同一組 candles、config 與 warmup_bars；搜尋不同指標週期時，預熱根數應涵蓋最大的候選需求，保持正式評估期間相同。示範只用 12 根合成 K 線、12 個 trial，不是歷史市場或樣本外驗證。

- `IntRange(low, high, step=1)`：signed 32-bit 整數邊界、正 step，high 必須落在格點上；不默默縮短上界。
- `DecimalChoices(("1", "2", ...))`：Optuna 接收原始字串候選，策略收到 Decimal。拒絕 Float、非有限值與數值重複的候選，不經由浮點價格／張數還原。
- `strategy_factory(params)`：每次建立全新策略，params 是唯讀的 int／Decimal mapping；不接收原始 Optuna Trial，也不能藉參數改寫帳戶 config。
- `score(performance)`：由 Decimal 原始績效算出無量綱 Decimal 評分。`score_name` 明示目標／公式；只有這個評分轉成 Float 交給搜尋器。拒絕非有限值、轉換溢位或非零數下溢為零；一般 Float 捨入仍可能造成分數並列，最佳 trial 依 Optuna 的 Float 排名，不能宣稱保留無限精度排名。
- 結果保存每次 trial 的順序、int／原始字串參數、Decimal 評分、搜尋 Float 評分、原始 Performance、失敗原因、seed、Optuna 版本、搜尋空間及固定回測設定。`best_trial.strategy_params()` 可還原參數，重新 backtest 得到完整交易／權益曲線。呼叫端仍需保存相同輸入資料及策略／評分原始碼，不能只靠 seed 跨版本重現。
- 一般策略／評分錯誤記為 `FAIL`，不給假分數、不列入最佳候選、不重試補足成功數；`n_trials` 是嘗試次數。全部失敗時 `best_trial` 為 None。KeyboardInterrupt 等中斷立即傳出。

目前不暴露 storage 參數、不用 SQLite、pickle／joblib、不做並行、pruning、續跑或訓練／驗證資料自動切分。原始交易核心未更動，搜尋結果不提供 Live 下單權限。

介面依據：[Optuna ask/tell](https://optuna.readthedocs.io/en/v4.9.0/reference/generated/optuna.study.Study.html)、[InMemoryStorage](https://optuna.readthedocs.io/en/v4.9.0/reference/generated/optuna.storages.InMemoryStorage.html)。分工與可直接貼入另一 IDE 的任務見 WORK_PLAN.md、ANTIGRAVITY_HANDOFF.md。

## 本切片界線

研究核心未包含限價／停利／停損撮合、保證金／強平模型、帳戶風控與額度保留、Guardian、UNKNOWN／對帳、完整 Supervisor、SQLite、UI 或 OKX 連線。核心可用來驗證策略與帳務算術，尚不能作為 Demo／Live 執行器或判定交易所是否會接受委託；也不宣稱已實現跨環境同一核心的完整產品。

研究版驗收後，新增獨立的 [D：Worker／JSON IPC](docs/worker.md) 切片，提供受信 SMA 策略的普通子程序執行、有界通訊與明確 JSON 狀態還原；既有研究入口與交易邏輯維持原樣。預設 D 模式是純記憶體的程序故障隔離，沒有交易或 OS 安全沙箱保證。後續順序見[本機模擬規劃](docs/local-simulation-plan.md)。

[E：本機 Supervisor／SQLite](docs/supervisor.md) 另提供單一 Windows 模擬帳戶的路徑綁定與帳戶鎖、合約所有權、原子 journal、重播去重，以及 COMMIT 後才 ACK 的 Worker 模式。保留的 E fixture 介面預設拒絕交易意圖，outbox 固定不可派送。

[F：合成帳戶風控](docs/risk.md) 已接入 Decimal 曝險、含在途／UNKNOWN 的數量保留、固定日初權益的台北日損、Soft／Hard／Kill 鎖存與合法 reduceOnly 減倉裁決。以 `risk_limits` 明示啟用，獨立合成快照不等待 Worker。

[G：假交易所與恢復閉環](docs/execution.md) 已接入固定 tag 的唯一模擬建單、SUBMITTING／UNKNOWN、查單、撤單、成交去重、原操作 reduceOnly 清倉及重啟對帳。以 `FakeExchange` 明示啟用，只使用本機腳本回報；D–G 本機模擬底座已完成，真實估值、保證金與 Demo／Live 尚未接入，待決金融政策維持原狀。

專屬測試採合成資料驗證預熱、可見時間、tick／lot 與合約單位、雙向淨倉、費用／資金費、帳務守恆、期末狀態及 Decimal context 隔離。沒有執行全市場歷史回測或存取真實憑證。
