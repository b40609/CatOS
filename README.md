# catOS：最小 Closed Bar 研究核心

新對話先讀[目前接續入口](docs/current-handoff.md)，確認階段、待決政策、分工與授權；詳細歷史留在各切片文件。

2026-10-19 後端研究新增[參數鄰域穩定度與滾動樣本外驗證](docs/research-validation.md)：有界完整格點、固定訓練選參後測 OOS、獨立視窗及 Decimal JSON，初輪開發自測含必要回歸 48/48 通過，待指定角色獨驗。合成範例 `py -3 -B -m examples.research_validation_demo`；OOS 視窗不是連續投資組合績效。

同日接續完成[分市場環境評估](docs/research-regimes.md)：明示趨勢／震盪與波動規則，用前一根收盤標籤歸屬當根估值損益，保留未知、樣本數及成本。26 項專屬＋40 項必要回歸，66/66 開發自測通過，待指定角色獨驗；合成範例 `py -3 -B -m examples.research_regimes_demo`。未改前端或原選參／回測行為。

同日第三個工作包完成[研究驗證封存與後端查詢](docs/research-validation-api.md)：POST `/api/research/validations` 沿用單一 writer，保存各窗穩定區／OOS／分環境結果及來源快照，透過既有 runs／result／report API 查詢。126/126 開發自測通過，待指定角色獨驗；未改前端、MCP 送出工具、DB schema 或正式服務，實際服務尚未載入新版本。

2026-10-01 W2／W3 已由指定 5.6 Sol (Web) 獨立驗收，分別 50/50、33/33 PASS；W4 已將 W2／W3 載入正式 8770，限定啟停驗收 PASS。W5 已完成正式 UI 單次 start、reload 後持續至自然 completed，並依使用者本次例外授權由 6.1 Sol 限定唯讀獨立驗收 PASS（原始證據 41 項斷言）。8771 preview 保留原 owner，不掛 simulation mutation。以上為既有驗收紀錄；本次收尾另獲 6.1 Sol 三片本機提交授權，未重跑案例、測試或 R4，未重啟服務或 push。詳見 [W2](docs/local-sim-bot-control-w2-handoff-20261001.md)／[W3](docs/local-sim-bot-control-w3-handoff-20261001.md)／[W4](docs/local-sim-bot-control-w4-handoff-20261001.md)／[W5 獨立驗收](docs/local-sim-bot-control-w5-acceptance-20261001.md)。

正式工作台入口：在本目錄執行 `powershell -ExecutionPolicy Bypass -File scripts/start-research.ps1`（或 `python -B -m catos.workspace_api`），開啟 `http://127.0.0.1:8770/`。Gemini 首頁、六頁工作台與研究 API 共用同一 ResearchService／writer，無須 8771 預覽。舊研究頁保留於 `/research/`，舊 F1 工作台保留於 `/workspace/legacy`。更新程式前先等研究任務完成，於啟動終端按 Ctrl+C 再重啟；8770 被占用時直接退出，不自動停其他程序。下列 R1／R2 啟動方式為歷史紀錄，日常使用以上正式入口。

2026-09-30 R1 正式研究入口已實作並通過 Sol 驗收：[R1 交接](docs/frontend-research-r1-handoff-20260930.md)／[驗收證據](docs/frontend-research-r1-sol-verification-20260930.md)。在本目錄執行 `python -B -m catos.research_api --port 8770`，開啟 `http://127.0.0.1:8770/research/`，使用註冊 SMA 與合成資料執行真實 Decimal 回測，結果保存於隔離 JSON／HTML。原型 8088／8089 不是研究驗收入口；畫面底部顯示程式版本，更新後等任務完成再手動重啟。原有 root／Yaozi 保留，其他主頁仍為示意。

2026-09-30 R2 Optuna 已接同一研究入口：註冊 SMA 週期搜尋、明示 trial 預算與 seed、查看保存候選並套用為新回測。僅合成資料樣本內搜尋，未執行樣本外檢驗。5.6 Sol (Web) 專屬與必要回歸 30/30 通過；後續固定 8770 人工重啟、實際瀏覽器畫面及 1-trial 正式 HTTP Optuna 任務均已驗證。詳見 [R2 交接](docs/frontend-research-r2-handoff-20260930.md)。

2026-09-23 產品方向已確認：`CatOS_Astra` 與 `CatOS_Yaozi` 保留分工開發，最終整合成同一 catOS 網站內的「量化交易／Yaozi 情報」分頁，不需另開網站。切換頁面不應中斷後端策略；此為交付要求，尚未完成整合驗收。分工、現況與整合順序見[單一介面整合契約](docs/catos-yaozi-integration.md)。

2026-09-21 最新優先序：**catOS 自動跑策略為主線，Yaozi 收斂成可選唯讀情報模組 v0.1**。主線阻斷與最小驗收見[自動策略盤點](docs/catos-auto-strategy-readiness.md)，情報封版見[v0.1 契約](docs/yaozi-v0.1-closeout.md)。S10 已依[專屬交接](docs/lot-fee-correction-handoff.md)通過 Sol 驗收（34/34 專屬、344/344 必要回歸）；下方「待驗收」及各「最新」段落均為切片歷史，不代表目前狀態。本輪未重驗，不啟動新採集或 Demo／Live 交易。

S10 已獲使用者實作授權，Astra 依 [通過審查的正式規格](outputs/catos-s10-fee-correction-spec.md)完成程式及34個專屬測試方法編寫，**待 Sol 執行驗收，尚未宣稱通過**。包含 P1A／P2A、精確前驅及重送、schema9、S2 request／event／capture v3、同 subtotal correction 版本的完整重放證明及 V3 報告。Lot snapshot沿用v2，schema7／8不遷移。詳見 [S10 開發交接](docs/lot-fee-correction-handoff.md)；本輪未執行 Python、測試、DB 或 Git，其他未提交工作保留。

S9 已依[正式規格](outputs/catos-s9-fee-completion-spec.md)完成 Sol 功能／資料完整性驗收：S9 專屬 32/32、必要回歸 312/312，共 344/344 通過，`py_compile` 通過；驗收中修正 schema7 `apply_fill()` raw payload 的既有錯誤語義相容。`Journal(..., lot_schema_version=8)` 只用於新建合成 DB，既有 DB 不遷移、不修改。詳見 [S9 開發交接](docs/lot-fee-completion-handoff.md)。

S9 文件基線：[assessment](outputs/catos-s9-fee-completion-assessment.md) `bb29389`、正式規格 `120dc58`；使用者確認 S8 `b069082` 為穩定基線。本輪以新建 schema8 合成 DB 產生完整／缺費報告，1280／390 px 實際 viewport 均完成像素驗收與 scrollWidth 量測，長 Decimal、費用品質、缺費筆數與 funding 文案可讀，無整頁水平溢位或裁切。

S7 已提交：`e00c2b5`（`feat(lots): add S7 synthetic scenario report`），依使用者回報補記；未執行全量測試，Astra 本輪未重跑驗證或執行 Git。

最新開發：**S8 已實作並通過修正後 Sol 驗收**。入口 `python -B -m examples.lot_scenario_demo --output-dir <new-dir>` 以全新 Journal 走真實 S3→S5→S7，保存合成 DB 與 complete／degraded HTML，拒絕覆寫且失敗保留產物。Astra 獨立審查後將 S8 專屬測試由 16 增至 22 個方法；Sol 重驗 S8 22/22＋S7 21/21，共 43/43，0 failure／error／skip，`py_compile` 通過，生產程式未改。詳見 [S8 開發交接](docs/lot-scenario-demo-handoff.md)。

最新驗收：**S7 本機合成情境報告已通過 Sol 驗收**。純函式 `render_synthetic_scenario_report()` 呼叫 S6 後回傳離線繁體中文 HTML，保留 Decimal 精度、空值／零、品質與降級原因。S7 21/21、S6 回歸 34/34，共 55/55 通過；Python 3.14.6、SQLite 3.50.4，新增 Python 檔編譯通過。F01 以完整／降級樣本在 1280 px 與 390 px 實際渲染，無整頁水平溢位或裁切，長 Decimal、品質旗標與降級原因可讀。詳見 [S7 開發交接](docs/lot-scenario-report-handoff.md)。

最新驗收：**S6 合成情境轉接已驗收並提交**，commit `ecc897e3afc19ab03527a4e1529f060b83f21df7`。以明示scenario cut及精確capture binding將S5資料轉接至S4；pending標示`SYNTHETIC_LEDGER / UNTERMINATED`，report保留`SYNTHETIC_SCENARIO`，不作交易所對帳或交易授權。詳見 [S6交接與驗證範圍](docs/lot-scenario-handoff.md)。

依使用者回報，S6／S4／S5 為 34＋42＋39，共 115/115 通過，0 failure／error／skip；Python 3.14.6、SQLite 3.50.4，編譯及 diff／staged 檢查通過，未執行全量測試。既有 schema7 維持不變，要求 SQLite 3.37+；S6 不存取資料庫。[S7 正式規格](outputs/catos-s7-scenario-report-spec.md)已驗收並提交 `299884f`。

2026-09-15 最新狀態：[I-b-4 單次 Demo 唯讀採集](docs/demo-collection-handoff.md) 已由執行模型依各輪明確指令執行；最後一輪 config gate 通過，13 個來源分頁完成，driver／wire 各 41 次。這是歷史交接結果，不是本輪重驗。餘額解碼、模式、歸因、P6 關聯、新鮮度／窗口／日初基準差異仍在，`reconciled=false`、`trade_authorized=false`，J／Live 未啟動。完整記憶體報告未保留，舊授權不允許自動重跑。

[I-b-3 受限 HTTP transport](docs/http-transport-handoff.md) 與 [I-b-2 decoder](docs/account-decoder-handoff.md) 已有另一模型獨立驗收紀錄，詳見 WORK_PLAN；歷史測試數字不代表目前修補版本已通過測試。

本輪已修補已知研究入口、輸出保護、來源歸併／證據鏈、欄位診斷、合法減倉與 P6 恢復交叉問題，並補合成回歸測試；僅靜態核對，未執行測試、編譯、Git、憑證讀取或帳戶請求。開發與執行驗證分工不變。以下各切片描述保留其交付時點邊界。

最新本機切片：[P6 災難保護模擬](docs/protection-simulation.md) 已支援持久化設定、成交平均成本更新、FakeExchange 保護建立／更新／取消／UNKNOWN 與失敗禁增倉告警。預設 0% 停用；已確認 mark 觸發、tick 向提早觸發方向取整、0% 停用等待取消終態。P6 交易所保護生命週期尚未接入，I-b 唯讀資料亦未完成 P6 責任對帳；J 未啟動。

目前完成單合約、單週期的純記憶體研究核心、最小 Optuna 搜尋、CSV 已收盤 K 線匯入與離線 HTML 報告。核心採 Jesse research 的介面風格與自有 Decimal Core，只用標準函式庫；搜尋另使用 Optuna，不依賴 Jesse。需要 Python 3.11+；研究模組歷史驗收環境為 Python 3.14.6、Optuna 4.9.0，不代表本輪已重驗。

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

## 額外研究入口（本輪修補，待驗證）

`catos.cli`／`catos.optuna_study` 不再對任意 symbol 套用固定合約規格。兩者必須明示 `--symbol --base-per-contract --tick-size --lot-size --min-size`；程式呼叫必須傳入與 symbol 一致的 `contract=ContractSpec(...)`。這些只是本地研究輸入，未查核交易所 metadata，不代表可交易。標準 `catos.research_cli --config` 不受影響。

只使用合成資料的額外 CLI 範例（不會自動下載資料）：

```powershell
py -3 -B -m catos.cli --csv reports/visual-qa/synthetic.csv --symbol SYNTHETIC-USDT-SWAP --base-per-contract 0.01 --tick-size 0.01 --lot-size 1 --min-size 1 --fast 1 --slow 2 --report reports/dual-sma-synthetic.html
```

額外 Optuna study 使用同樣四個規格參數，另有 `--timeframe-ms`（預設 3600000，即 1H）；固定預熱 80 根，輸入必須另含正式評估資料。權益差分、收益率、樣本標準差及夏普年化全程 Decimal；365 天年、零無風險利率，按指定週期換算。少於兩個收益率或零方差顯示 N/A；非正／非有限權益不補零。此評分不是帳戶風控依據。旧调用的隐含规格已移除，须更新参数；没有新增真实行情验证。

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

[G：假交易所與恢復閉環](docs/execution.md) 已接入固定 tag 的唯一模擬建單、SUBMITTING／UNKNOWN、查單、撤單、成交去重、原操作 reduceOnly 清倉及重啟對帳。以 `FakeExchange` 明示啟用，只使用本機腳本回報；D–G 本機模擬底座已完成，真實估值、保證金與 Demo／Live 尚未接入，政策更新與實作差距見下方 I-a 契約。

專屬測試採合成資料驗證預熱、可見時間、tick／lot 與合約單位、雙向淨倉、費用／資金費、帳務守恆、期末狀態及 Decimal context 隔離。沒有執行全市場歷史回測或存取真實憑證。

D–G 已封版為 `v0.2-simulation-base`。下一階段見 [H：Demo 進入條件與驗收矩陣](docs/demo-entry-contract.md)；P2–P5 已依 2026-09-12 決策更新。[I-a：官方映射、離線對帳與 P6 選項](docs/okx-readonly-contract.md) 已交付，尚未啟動 I-b 唯讀帳戶連線或 J Demo 交易。新日損政策為可配置 10%／20%、無 equity buffer、合格可隨時人工 re-arm；P5 本機遷移已完成：可配置 10%／20%、原子保存門檻、合格人工 re-arm、schema 4 控制稽核；舊意圖不復活。實際帳戶資料與交易所適配仍未接入。[P6 災難停損政策](docs/disaster-stop-policy.md) 已定稿：每 Bot 預設 0% 停用，mark 觸發、tick 向提早觸發方向取整，0% 停用須確認取消終態；平均成本變動時更新，失敗禁增倉並告警、不自動減持。
