# CatOS 後端能力與前端串接交接（Antigravity）

更新：2026-10-20。用途：讓前端開發者知道可用功能、接法與未解問題；不要求前端立即定稿、全面串接或完成驗收。

本輪僅靜態讀取現行路由、資料契約、React 呼叫端、相關測試與非敏感歷史報告，更新本文件與[接續入口](current-handoff.md)。沒有修改程式、啟停服務、呼叫 HTTP、讀產品 DB／憑證、執行測試或建置。以下「已有 HTTP」指現行程式已掛載路由，**不代表本輪已確認執行中的 8770／8771 載入相同版本**。前端約 80% 為使用者提供的版面／操作進度，不能換算成後端整合完成率。

## 1. 先看功能與可用程度

| 前端功能 | 後端能力 | 接法 | 現況／限制 |
| --- | --- | --- | --- |
| 回測、權益／回撤、成交明細 | 已有 HTTP；Decimal 研究核心 | POST `/api/research/backtests`，共用 runs 查詢 | **React 已串接** version、catalog、提交、歷史、輪詢與結果；仍有第 7 節問題，未完成本輪互動驗收。只有登錄的 SMA／96 根合成 15m 資料 |
| 參數搜尋 | 已有 HTTP；Optuna 樣本內搜尋 | POST `/api/research/optimizations` | **React 尚為展示資料**：固定 TRIALS、EMA／ATR、Sharpe、4 Workers；後端只搜 SMA period，以 return_pct 排序 |
| 參數穩定區 | 已有 HTTP；候選網格與鄰域選參 | POST `/api/research/validations`，讀訓練結果 | React 尚無對應呼叫；不是另一個 stability 端點。Python 核心另有可重用能力，不表示 HTTP 接受任意策略 |
| Walk-Forward／樣本外 | 已有 HTTP；滾動訓練、固定參數後測試 | 同一 validations 任務，讀各窗 out_of_sample | React 尚無對應呼叫；各窗空倉獨立起跑，不能拼成連續帳戶績效 |
| 分市場環境評估 | 已有 HTTP；七類環境損益／成本歸屬 | 同一 validations 結果的分環境區段 | React 尚無對應呼叫；示範門檻，非自動部署通過規則 |
| 研究封存、歷史與報告 | 已有 HTTP；三類任務共用封存 | GET runs、單次狀態、result、report | 回測頁已接 backtest 歷史與 JSON；optimization／validation 歷史與 HTML 報告入口尚未接 React |
| 策略版本、Bot 建立／部署 | 已有部分 Python 製品／策略庫／狀態能力，**目前管理 HTTP 未掛載** | 先確認缺口，不能使用 mock 中的網址當 API | 主要狀態仍走 mockAdapter；舊文件／MCP 呼叫不等於路由可用 |
| 固定模板本機模擬 | 已有 HTTP；單槽 SMA 合成 smoke 模板 start／stop | `/api/workspace/simulation/*` | 尚未透過主 React 狀態 adapter 串接；只限固定 8 根／2 根預熱模板，非任意 Bot 或常駐交易 |
| 舊 local-sim 證據瀏覽 | 已有唯讀 HTTP | `/api/workspace/local-sim/runs*` | 可讀 manifest／status／events；不是即時帳戶、Worker 存活或風控就緒證明 |
| 帳戶風控、R1 風控期間基準 | 已有 Python／local-sim；**R1 未接 HTTP／UI** | 目前不能從 React 讀取／操作完整帳戶風控 | R1 local-sim 有歷史獨驗 PASS；風控／Kill Switch 展示不能宣稱已控制後端 |
| Virtual Lots／逐筆成交帳務 | 已有分階段 Python／local-sim 工作與證據 | 無對應前端 HTTP 契約 | 不等於目前單合約單 Bot 執行已改制，也不含完整多 Lot 分配、funding 與交易整合 |
| 真實行情研究、任意策略上傳、AI 自主研究、Demo／Live | 本次研究 HTTP 沒有完整可用流程 | 尚未實作此整合，或需另核對／另行授權 | 不能以展示按鈕、模組存在或研究完成推導為交易能力 |
| Yaozi 情報 | 有唯讀路由，依指定本機資料可用性 | 第 9 節保留路由索引 | 情報頁仍有固定告警／費率；本輪未核實各卡 DTO、實際資料與新鮮度 |

策略／Bot、風控／遙測、帳戶權益與主工作區事件主要仍取自 [stateAdapter.ts](../frontend/cat-os-vite/src/state/stateAdapter.ts) → [mock-adapter.ts](../frontend/cat-os-vite/src/adapters/mock-adapter.ts)。回測頁另外直接使用研究 adapter，**不能因此把整站改稱真實帳戶資料**。

## 2. 連線、版本與同源

來源：[workspace_api.py](../catos/workspace_api.py)、[research_api.py](../catos/research_api.py)、[local_sim_control_api.py](../catos/local_sim_control_api.py)。

- 一般整合入口是 `catos.workspace_api.create_app(preview=False)`，掛載研究、情報、舊模擬證據與固定模板模擬控制。舊 `/research/`、`/workspace/` 與 React 是不同前端，測過舊頁不代表 React 已通過。
- 使用 `127.0.0.1`。研究路徑有 host 檢查；POST 的 Origin 若存在，必須等於後端所見的請求入口（含埠），不是允許任意 localhost 來源。
- 研究 POST：`Content-Type: application/json`、`X-CatOS-Build: <GET /api/research/version 的 build_id>`。不要求 simulation 的 instance header。
- simulation POST：同時要求其 **自身** version 的 `X-CatOS-Build` 與 `X-CatOS-Instance`；不能拿 research 或 workspace 的版本代替。
- 兩類 POST 都限制 body 8192 bytes、拒絕重複 JSON 欄位與非有限常數；請求採精確欄位集合，不自行附加 UI 欄位。
- `restart_required=true` 停用提交並顯示原因；頁面不得自行重啟服務或假設 reload 就能解決來源漂移。研究回應有 no-store 與 build／instance headers。
- 研究 version 的 `mode=local_research_synthetic`；simulation 的 `contract=catos.simulation.v1`；workspace 的 `contract=catos.workspace.v1`。結果也有各自 schema，不能共用一份結果 DTO。

| 入口／設定 | 現行靜態核對 | 串接意義 |
| --- | --- | --- |
| [vite.config.ts](../frontend/cat-os-vite/vite.config.ts) | `127.0.0.1:8890`；`/api/research` 代理到 **127.0.0.1:8770**；changeOrigin 且固定轉送 origin 為 8770 | 正式研究通路已有代理，舊文件「沒有 proxy」已過時；不是隔離後端設定 |
| 同一 Vite 設定的其他路徑 | 未配置 simulation、workspace、intel 代理 | 不可照抄研究 adapter 的相對路徑就宣稱其他 API 已可經 Vite 使用 |
| [vite.dashboard-preview.config.ts](../frontend/cat-os-vite/vite.dashboard-preview.config.ts) | 8887、strictPort、獨立 Dashboard 預覽，沒有後端 proxy | 不能當研究串接隔離環境 |
| 8771 preview 的後端程式 | 只轉送白名單研究 GET／POST至固定 8770；另有 workspace 證據讀取；不轉送 intel／simulation | preview 仍可能到正式研究 writer，不是獨立研究資料根 |
| 全新隔離研究環境 | 本輪未找到獨立 React／Vite 研究 proxy 設定 | 未來要做隔離互動時，須先確認專用埠、資料根與固定目標代理；不能沿用 8890→8770 後稱隔離 |

本文件描述接法，不授權操作正式服務、建立測試環境或執行控制案例。維持原同源防護，不以關閉檢查或任意 URL 代理解決串接。

## 3. 研究任務共用流程

來源：[research_service.py](../catos/research_service.py)、[research-api-adapter.ts](../frontend/cat-os-vite/src/adapters/research-api-adapter.ts)。

| 方法 | 路徑 | 用途／回傳 |
| --- | --- | --- |
| GET | `/api/research/version` | build_id、instance_id、restart_required、active_run_id、mode 等 |
| GET | `/api/research/catalog` | 登錄策略／資料與限制；defaults、optimization.defaults、validation.example_request |
| GET | `/api/research/runs` | `{"items":[]}` 或任務清單，依建立時間新到舊；混合三種 kind，無分頁／kind 查詢參數 |
| POST | `/api/research/backtests` | 202，回傳任務物件，kind=backtest |
| POST | `/api/research/optimizations` | 202，回傳任務物件，kind=optimization |
| POST | `/api/research/validations` | 202，回傳任務物件，kind=validation |
| GET | `/api/research/runs/{run_id}` | queued／running／complete／failed，含 error |
| GET | `/api/research/runs/{run_id}/result` | complete 才可讀封存 JSON |
| GET | `/api/research/runs/{run_id}/report` | complete 才可讀 HTML；不要用 JSON parser |

1. 載入 version＋catalog＋runs；按 kind 分類，保留 active_run_id 的後端觀測。
2. 以 catalog 內對應預設請求建立表單，再覆蓋使用者輸入；不要把所有 UI 控制欄位直接送出。
3. POST 收到 202，保存實際 run_id，輪詢該任務；回應可能已進入 running，不能只接受 queued。
4. complete 後讀 result；failed 顯示 error，不讀取上次成功結果冒充本次結果。同步重讀 runs／version，直到後端確認忙碌槽已釋放，不由前端清空 active_run_id。
5. 離頁停止前端輪詢，不取消後端任務；回頁／重新整理以 runs＋version 恢復觀察，不能再次 POST。任務切換要保留「正在追蹤的任務」與「正在查看的歷史結果」各自身分。
6. 三類研究共用一個 writer／忙碌槽；沒有取消、WebSocket、逐 Trial 進度、提交 request_id 或自動去重契約。POST 網路結果不明時先查 runs，不能盲目重送。重啟時未完成研究會標為 failed，error 為 interrupted_by_service_restart。

錯誤 JSON 使用 `detail`。常見 HTTP：400 無效 run_id、404 查無任務、403 host／Origin、413 body 過大、415 Content-Type、422 請求驗證、409 research_busy／版本不符／result_not_complete／封存額度等；服務未就緒也可能 503。保留 HTTP status 與 detail，不全部顯示成空資料。run_id 為 32 位小寫十六進位。

以下 JSON 是**契約示例／欄位節錄，不是本輪執行輸出**；字串占位值不可直接當有效 ID 或版本提交。

202 任務回應節錄（完整物件另含 request、provenance、build_id 與時間欄位）：

```json
{
  "run_id": "0123456789abcdef0123456789abcdef",
  "kind": "backtest",
  "status": "queued",
  "error": null,
  "started_at": null,
  "finished_at": null
}
```

GET 狀態完成與失敗的最小辨識欄位：

```json
{"run_id":"0123456789abcdef0123456789abcdef","kind":"backtest","status":"complete","error":null}
```

```json
{"run_id":"0123456789abcdef0123456789abcdef","kind":"backtest","status":"failed","error":"interrupted_by_service_restart"}
```

版本與結果 DTO 節錄不表示可忽略其他欄位。React adapter 現有 getVersion／getCatalog／getRuns／getRunStatus／getRunResult／submitBacktest；**尚無 optimization／validation 提交與 report 方法**。其 getRunResult 目前固定型別為 BacktestResult，run 的 request 也固定為 BacktestRequest；接其他 kind 前要分流 DTO，不能只新增按鈕沿用斷言。

## 4. 研究請求與結果怎麼接

### 4.1 回測：看單次策略在指定合成資料的結果

來源：[research_catalog.py](../catos/research_catalog.py) 的 DEFAULT_REQUEST／validate_request／execute_request、[research.py](../catos/research.py)。

POST `/api/research/backtests`，下列為目前 catalog 預設的完整最小請求：

```json
{
  "strategy_id": "sma-trend",
  "dataset_id": "synthetic-btc-15m-v1",
  "parameters": {"period": 2, "quantity": "2"},
  "initial_balance": "1000",
  "fee_rate": "0.0005",
  "slippage_bps": "2",
  "warmup_bars": 2
}
```

- 目前只登錄此 SMA 與 BTC-USDT-SWAP 合成 15m／96 根已收盤 K 線；不是即時或真實行情回測。沒有任意 CSV、日期範圍、策略程式或路徑參數。
- period 為整數 2～32；quantity 為 Decimal 字串、整張合約數 1～1000。warmup_bars 為整數、>= period 且 <64。
- initial_balance 為正 Decimal 字串且 <=1000000000；fee_rate 為字串、0～0.01；slippage_bps 為字串、0～100。Decimal 輸入不可有前後空白／非有限值，長度 1～64。
- 本根收盤決策、下一根開盤加明示滑價；單一費率，資金費明示為空。預熱不做交易決策、不計績效；末根意圖可能留 pending_intent。
- 期末以未平倉部位估值，**不是自動強制平倉**。不包含完整帳戶保證金、強平、Guardian 或 Demo／Live 底座。

結果最小取用範例（JavaScript，只讀欄位；不假造績效數字）：

```javascript
const payload = await researchApi.getRunResult(runId, signal);
const performance = payload.result.performance;
const equityCurve = payload.result.equity_curve;
const drawdownCurve = payload.drawdown_curve;
const fills = payload.result.trades;
```

| 畫面用途 | /result 根物件內路徑 | 語義／限制 |
| --- | --- | --- |
| 權益／損益／成本 | result.performance | initial_equity、final_equity、net_pnl、return_pct、realized_pnl、unrealized_pnl、fees、funding_paid、max_drawdown_pct 為 Decimal 字串；trade_count 為整數 |
| 權益圖 | result.equity_curve | 使用 time_ms 與 equity；以原時間對應，不用固定點補值 |
| 水下圖 | drawdown_curve | time_ms、drawdown_pct；後端為非負回撤幅度，顯示時可取負 |
| 成交表 | result.trades | time_ms、decision_time_ms、quantity、price、fee、realized_pnl、position_after；交易金融值維持字串 |
| 計算區間 | result.warmup_bars、evaluation_start_ms、evaluation_end_ms | 後兩欄也在 result 內；不要把預熱算成評估樣本 |
| 未成交／假設 | result.pending_intent、result.assumptions | null 與有意圖要區分；保留期末未成交與估值假設 |
| 證據／標示 | request、provenance、data_notice、trade_count_unit、run_id、created_at、build_id | trade_count 是 simulated fills，**不是已平倉往返數**；不能推算勝率 |

回應形狀節錄（`<Decimal 字串>` 是型別占位，非可用績效）：

```json
{"result":{"performance":{"initial_equity":"1000","net_pnl":"<Decimal 字串>","return_pct":"<Decimal 字串>"}},"trade_count_unit":"simulated fills, not closed round trips"}
```

金融值從請求、封存到 KPI／明細保留原 Decimal 字串。圖表可另作 Number 轉換供座標／tooltip，不能用該值回算損益、費用、額度或風控。整數時間／計數維持整數；顯示 return_pct 時不再當小數乘 100。無效／缺失值應呈現缺資料，不能用零掩蓋。權益／損益以 USDT，quantity 是合約張數，不能直接當 BTC 數量。

### 4.2 參數搜尋：找樣本內報酬較好的 SMA period

來源：[research_optimization.py](../catos/research_optimization.py)、[optimization.py](../catos/optimization.py)。

POST `/api/research/optimizations`；完整預設請求：

```json
{
  "backtest": {
    "strategy_id": "sma-trend",
    "dataset_id": "synthetic-btc-15m-v1",
    "parameters": {"period": 2, "quantity": "2"},
    "initial_balance": "1000",
    "fee_rate": "0.0005",
    "slippage_bps": "2",
    "warmup_bars": 8
  },
  "search_space": {"period": {"low": 2, "high": 8, "step": 1}},
  "n_trials": 8,
  "seed": 42
}
```

搜尋僅 period 整數範圍；low／high 介於 2～32，step 為正整數且範圍對齊；預熱 >= high。n_trials 為 1～20，seed 為 0～4294967295 整數。quantity 固定。以 catalog 最新限制為準。

202 與狀態查詢沿用第 3 節。結果節錄的取用方式（adapter 尚未有此專用 DTO；不是現有可直接編譯的呼叫範例）：

```javascript
// payload = GET /api/research/runs/{run_id}/result 的 optimization JSON
const trials = payload.trials;
const bestTrialNumber = payload.best_trial_number;
const objective = payload.objective;
```

回應形狀節錄（省略其他 trial／欄位，不代表完整 DTO）：

```json
{"kind":"optimization","trials":[{"number":0,"params":{"period":2},"score_decimal":"<Decimal 字串>"}],"objective":{"name":"return_pct","direction":"maximize"}}
```

trials 每列為 number、state、params（物件，如 period）、score_decimal、performance、error。失敗列 performance／score 可為 null；最佳編號也不能先假設一定存在。performance 欄位沿用回測績效，未封存每個 trial 的完整成交／權益曲線。保留 objective、seed、optuna_version、request、provenance、data_notice。

目標是 return_pct 最大化；只有交給 Optuna 的搜尋評分可轉 Float，帳務與封存 score_decimal 保持 Decimal。沒有 Sharpe、多 Worker、多目標 Pareto、EMA／ATR 多參數或策略檔匯出。搜尋完成不是樣本外驗證或部署建議。

### 4.3 穩定區 → Walk-Forward → 分市場環境

來源：[research_validation_job.py](../catos/research_validation_job.py)、[research_validation.py](../catos/research_validation.py)、[research_regimes.py](../catos/research_regimes.py)；詳細語義見[驗證 API 契約](research-validation-api.md)。

POST `/api/research/validations`；同一任務產生三項能力，不猜另一條穩定度／OOS 路由。完整預設請求：

```json
{
  "backtest": {
    "strategy_id": "sma-trend",
    "dataset_id": "synthetic-btc-15m-v1",
    "parameters": {"period": 2, "quantity": "2"},
    "initial_balance": "1000",
    "fee_rate": "0.0005",
    "slippage_bps": "2",
    "warmup_bars": 4
  },
  "search_space": {"period": {"low": 2, "high": 4, "step": 1}},
  "plan": {"train_bars": 24, "test_bars": 16, "windows": 3},
  "regime_rule": {
    "lookback_bars": 4,
    "trend_efficiency": "0.5",
    "high_volatility_bps": "250"
  },
  "max_candidates": 3,
  "max_runs": 12
}
```

限制：HTTP 驗證至少 2 個候選、最多 20，預熱 >= high；windows 1～8。max_runs 是此驗證計算預算，最多 100；windows ×（候選數＋1）不得超過預算。warmup＋train_bars＋windows × test_bars 不得超過資料長度。train_bars／test_bars 為正整數；lookback_bars 為 1～511 整數，trend_efficiency 為 >0 且 <=1 的 Decimal 字串，high_volatility_bps 為正 Decimal 字串。此 API 是確定性網格驗證，不使用 Optuna 隨機搜尋。

回應根層 schema 為 `catos.research.validation-result.v1`、kind=validation；最小結果取用路徑：

```javascript
// payload = GET /api/research/runs/{run_id}/result 的 validation JSON
const allWindowsComplete = payload.evaluation_complete;
const training = payload.result.validation.windows[0].training;
const oos = payload.result.validation.windows[0].out_of_sample;
const environment = payload.result.windows[0].evaluation;
```

回應形狀節錄（只展示成功窗的辨識欄位，不表示每次皆成功）：

```json
{"schema":"catos.research.validation-result.v1","kind":"validation","evaluation_complete":true,"result":{"validation":{"windows":[{"status":"COMPLETE","training":{"selection_rule":"maximin_axis_neighbors_v1"}}]}}}
```

| 呈現內容 | 欄位 | 必須保留的語義 |
| --- | --- | --- |
| 穩定區候選 | result.validation.windows[n].training.trials | number、indices、params、score、performance、terminal_position、pending_intent、error；**params 序列化為名稱／值配對陣列**，不同於 optimization 的物件 |
| 鄰域／選參 | training.neighborhoods、selected_trial_number、selection_rule | 鄰域含中心及軸向相鄰；maximin_axis_neighbors_v1 先比較鄰域最差分數，再均分、自身分數與固定順序；失敗鄰域不能選 |
| 訓練／測試區間 | result.validation.windows[n] | train_start_ms／train_end_ms、test_start_ms／test_end_ms；status 為 COMPLETE／NO_SELECTION／OOS_FAILED，error 要可讀 |
| OOS 績效／曲線 | 同窗 out_of_sample | BacktestResult 或 null；各窗獨立，不把 null 當損益 0。早期 OOS 日後可進入下一窗訓練，不能宣稱全程未使用的最終 holdout |
| 計算完整性 | evaluation_complete、result.complete、result.validation.complete | 外層任務 complete 只代表計算／封存完成；不等於每窗成功、可部署或有獲利 |
| 計算預算 | result.validation.required_runs、attempted_runs、max_runs、unused_bars | 次數／剩餘資料統計，不是瀏覽器即時進度 |
| 分環境 | result.windows[n].evaluation.summaries | regime、bar_count、positive_bars、negative_bars、zero_bars、fill_count、funding_payment_count、net_pnl、gross_pnl、fees、funding_paid |
| 分環境核對 | evaluation.total、core_net_rounding_residual、reconciled | 保留成本、誤差與核對狀態；net_pnl 已扣費用／資金費，不能再扣一次；gross_pnl 也不等於已還原滑價 |
| 規則／來源 | result.rule、rule_version、labels；根層 request／provenance／reproduction／data_notice | 規則使用先前已收盤資料；門檻僅示範，不新增前端自訂驗收／部署門檻 |

七類為 UNKNOWN、UP_LOW、UP_HIGH、DOWN_LOW、DOWN_HIGH、RANGE_LOW、RANGE_HIGH，零樣本組也保留。分環境結果不是七個獨立策略回測；目前未提供各環境報酬率、最大回撤、統計顯著性或自動通過門檻。

### 4.4 封存、報告與可重現性

三種任務共用 runs，依 kind 分流。根層 request／provenance／run_id／created_at／build_id 對應該次封存，不用目前表單值覆蓋歷史請求。report 是 HTML，可作報告連結；現有 React adapter 尚未提供該方法／入口。

validation 的 reproduction 含 Python／套件版本、演算法及 files（path、sha256、content_utf8）；供查看與核對，不是環境鎖檔、自動載入套件、部署製品或防竄改簽章。不得直接執行快照內容。

catalog.limits.max_runs=200 是研究封存數上限；catalog.validation.max_runs=100 是單次驗證回測預算，兩者不可混淆。共用執行逾時 30 秒，Worker 輸出上限 2,000,000 bytes。沒有刪除封存、任意匯入歷史或清空資料 API 可供前端自行推定。

## 5. 本機模擬與唯讀證據

### 固定模板控制：有 HTTP，但不是 Bot 管理

來源：[local_sim_control_api.py](../catos/local_sim_control_api.py)、[local_sim_control.py](../catos/local_sim_control.py)。

| 方法 | 路徑 | 用途 |
| --- | --- | --- |
| GET | `/api/workspace/simulation/version` | contract、build_id、instance_id、restart_required、slot、active_run_id、capabilities、unavailable_reason、config |
| GET | `/api/workspace/simulation/runs` | items、state、issues |
| GET | `/api/workspace/simulation/runs/{run_id}` | 單次控制快照，不使用研究的 /result 路徑 |
| POST | `/api/workspace/simulation/start` | 202，固定模板；body 如下 |
| POST | `/api/workspace/simulation/runs/{run_id}/stop` | 202，要求停止；不代表已完成清理 |

兩個 POST 都帶本節 simulation/version 的 build／instance 與 JSON／同源要求。每個新命令使用自己的 32 位小寫十六進位 request_id；重試同一命令保留原 request_id、路徑與 body。與研究提交不同，這裡有命令重放／衝突檢查；版本或 instance 變更仍需遵守檢查，不自動換新 ID 重送。

start 完整請求：

```json
{"request_id":"11111111111111111111111111111111","template_id":"sma-synthetic-smoke-v1"}
```

stop 完整請求：

```json
{"request_id":"22222222222222222222222222222222"}
```

start 回應的最小辨識欄位節錄（實際排程可能已前進）：

```json
{"run_id":"0123456789abcdef0123456789abcdef","control_state":"starting","cleanup_confirmed":false,"stop_requested":false}
```

輪詢同一 run 快照，區分 starting／running／stopping 與終態 completed／stopped／failed；同時讀 cleanup_confirmed、worker_closed、error、events／events_omitted、bars／warmup_bars／fills。stop 為完成當前事件後停止，stopping 不等於已停止；still_finishing 提示也不是錯誤清理授權。遇 recovery_required、version 不可用或清理未確認，顯示原因並停用不合格控制，沒有 resume／解除端點可猜。

模板只有 8 根合成資料、2 根預熱；不是任意策略、長期即時行情或實盤。現有 Vite 沒有此路徑代理。

### 舊證據讀取：另一個資料根

來源：[workspace_api.py](../catos/workspace_api.py)、[workspace_snapshot.py](../catos/workspace_snapshot.py)。

- GET `/api/workspace/version`：workspace 版本，不是模擬提交版本。
- GET `/api/workspace/local-sim/runs`：最小空回應 `{"state":"empty","items":[],"issues":[]}`。
- GET `/api/workspace/local-sim/runs/{run_id}?limit=200`：limit 1～200，回傳 manifest、status、events、issues、last_signal、last_fill 等；不是研究結果 DTO。

詳情辨識欄位節錄：

```json
{
  "contract": "catos.workspace.local-sim.v1",
  "read_only": true,
  "source": "manifest/status/events",
  "risk": {"state":"unavailable","can_increase":null,"latch":null,"unresolved":null},
  "worker_alive": null,
  "acceptance": "not_evaluated"
}
```

reader 的 available／empty／partial／stale／unavailable／error 要如實呈現；null 不代表安全／正常，acceptance 不是 PASS。預設證據根 outputs/local-sim-r4，控制服務根 outputs/local-sim-control，不可混成同一 run 清單。這組 reader 不讀 SQLite，不能推導帳戶風控即時狀態。

## 6. 只有 Python／local-sim、尚不能接成 HTTP 的項目

- **策略／Bot**：[python_strategy.py](../catos/python_strategy.py)、[strategy_library.py](../catos/strategy_library.py) 有製品／策略庫／Bot 資料操作；[strategy_mcp.py](../catos/strategy_mcp.py) 有 HTTP 呼叫包裝。但現行 workspace／simulation 路由沒有掛載下列舊文件路徑：
  - GET `/api/workspace/simulation/strategy-contract`
  - GET／POST `/api/workspace/simulation/strategies`
  - GET／POST `/api/workspace/simulation/bots`
  - POST `/api/workspace/simulation/bots/start`
  這是具體整合缺口，不提供假想欄位／請求範例。舊 [v1 交接](v1-local-core-handoff-20261002.md) 與 mock 路徑不能當現行 API 文件。
- **風控／R1**：[risk.py](../catos/risk.py)、[risk_period.py](../catos/risk_period.py)、[supervisor.py](../catos/supervisor.py) 等有 local-sim 能力。R1 按台北日首次合格觀測建立固定基準，顯示語義應為「風控期間損益」與實際起算時間，不涵蓋起算前整日日損；重啟／反彈／跨日不自動解除 latch。沒有前端可呼叫的完整 R1 觀測／基準／re-arm／Kill Switch HTTP 契約。
- **Lot 帳務**：見 [lot-fill-handoff.md](lot-fill-handoff.md)。Python／local-sim 階段與歷史驗證按各切片認定，不提升為現行多 Bot 共用合約、交易、額度預留、內部對沖或完整分攤能力。
- 模組存在、單元測試通過、MCP 有方法或 mock 有命令，都不等於網站已取得控制能力。要補 HTTP 屬另一個後端工作包，本次只記錄。

## 7. 回測串接的最新問題與待驗證項目

本節取代舊版「回測仍全為固定資料／沒有 Vite proxy」及入口中已過時的部分缺陷。來源：[backtest.tsx](../frontend/cat-os-vite/src/pages/backtest.tsx)、[research-api-adapter.ts](../frontend/cat-os-vite/src/adapters/research-api-adapter.ts)、[backtest-underwater-chart.tsx](../frontend/cat-os-vite/src/components/catos/backtest-underwater-chart.tsx)。均為本輪靜態結論，未執行瀏覽器案例。

### 已確認會影響正確串接的問題

| 項目 | 現行程式證據／影響 | 接線時需要處理的範圍 |
| --- | --- | --- |
| 前端自行清空 active_run_id | startPolling 終態後重讀 version，仍把等於該 run 的 active_run_id 改成 null。後端先封存 complete／failed，再於 finally 釋放 active，中間確有合法短窗 | 不覆寫後端權威狀態；直到後端確認釋放再解除忙碌。後端仍可 409 拒絕，不能說已繞過交易／風控 |
| 隔離宣稱與代理目標不符 | 8890 的研究代理固定到正式 8770；8887 沒有研究代理 | 未來隔離 UI 證據須來自真正專用 backend／資料根／proxy；現行正式代理本身不是「沒有設定」 |
| 非回測 DTO 與路由缺口 | adapter 把所有結果型別斷言成 BacktestResult；未提供優化／驗證提交。策略／Bot HTTP 未掛載 | 對應頁要真接時先補正型別／adapter 或取得後端契約，不猜欄位／路徑 |
| 圖表錯值轉零 | 水下圖使用 parseFloat(value) || 0，缺 drawdown 點也給 0，並按陣列索引配對 | 正常後端有等長證據，但缺欄／非數值／時間錯位可能被畫成正常 0；不能拿此圖判定資料完整或風險正常 |

### 已有改善，不再照列為尚未修復

- adapter 已使用相對研究 HTTP，無連線失敗自動 fixture、假 run_id 或自動重送 POST；回測頁移除固定 HISTORY_RUNS／SAMPLE_FILLS。
- 回測歷史只列 backtest；只對 complete 取 result。圖表已移除固定收益與月度矩陣，空結果不補示意曲線。
- 載入時會找既有 queued／running backtest 並啟動輪詢；忙碌監測會重讀 version／runs。不能再說「重新整理不輪詢」。
- 切到未完成任務會重設 resultLoading；結果請求有 AbortController 與 generation 防止舊結果覆蓋。
- 舊輪詢完成後，僅在未選任務或仍選該 run 時自動載入結果，不再無條件搶回歷史選擇。
- 離頁有 mounted 檢查、清除兩個 timer、abort 結果請求。**只有 result 請求傳入 AbortSignal**，不能擴大宣稱所有請求皆取消。
- 終態已重讀 version／runs；原本「完全沒有刷新版本」已改善，但自行清空 active_run_id 的新問題仍存在。

### 待互動驗證與可延後的流程細節

| 線索 | 靜態可確認部分 | 尚缺證據／影響 |
| --- | --- | --- |
| 快速切換、重新整理與輪詢重疊 | result 有 generation；initial/status/submit 請求沒有同等取消／輪詢世代隔離 | in-flight status 遇刷新可能建立重疊輪詢或過期更新；尚未證明實際發生，不列已重現缺陷 |
| 新提交的選取行為 | submit 成功只 startPolling，未立即設 selectedRun／刷新歷史；終態會尊重原有歷史選取 | 可能仍顯示舊結果，新 run 完成才進歷史；屬已知流程，需決定如何清楚標示正在跑哪一筆，不應誤判結果遺失 |
| 背景失敗提示 | failed 分支的 setErrorMsg 不受目前選取 run 條件限制 | 可能在查看其他歷史時顯示背景錯誤；提示應帶 run 身分，待 UI 核對 |
| 斷線／重連 | adapter 保留 HTTP detail；非 HTTP／JSON parse 例外歸類 status=0 network_error；頁面 ONLINE 依 version 是否存在 | 後續請求失敗仍保留舊 version，ONLINE 不等於目前可達；待斷線互動核對，不補假結果 |
| 離頁／回頁 | 有前端清理；後端任務繼續，初載可恢復 | 尚無本輪瀏覽器證據證明快速離頁／提交中離頁／回頁皆無重複請求或過期更新 |
| 假資料與真結果 | 回測 adapter／圖表正常路徑未發現 fixture 回退；整站主狀態與優化／情報仍有展示來源 | 不能宣稱「整站已無 mock」；新卡片接線須核對來源，不把展示帳戶 KPI 當該 run 績效 |
| 顯示語義 | 回測仍有「期末估值平倉」文案；後端實際估值未強平 | 文案後續收斂；Sharpe／勝率不以成交筆數自算，無完整月資料不補月收益 |

這些問題只對要接入的頁面形成對應限制，不阻擋 Antigravity 繼續完成版面與一般操作。沒有已確認來源／完整性時保留錯誤或缺資料標示。

## 8. 證據能支持到哪裡

本輪讀取下列原始測試／報告，**沒有重跑，也沒有重新核對所有來源 hash**；歷史 PASS 不自動涵蓋目前 React 或執行中服務。

| 日期／證據 | 實際支持的範圍 | 不支持的宣稱 |
| --- | --- | --- |
| 2026-10-19 [研究三包獨驗](../reports/research-independent-acceptance-20261019-gpt6sol/acceptance.md) | 穩定度／WF、分環境、封存查詢；專屬 22／22、26／26、10／10，另 8 模組 126／126；隔離合成資料、真 Worker、TestClient；preview relay 有 mock | 不是目前 React、Vite proxy、真 8770／8771、真行情或整站驗收 |
| 2026-10-20 [R1 獨驗](../reports/risk-period-r1-independent-acceptance-20261020-gpt6sol/acceptance.md) | 合成 local-sim／暫存 SQLite／固定 clock／FakeExchange；197／197＋3 邊界，17 hash 核對 | 不是 HTTP／UI／Demo／Live；[R1 開發交付](risk-period-r1-local-sim.md) 若仍寫待獨驗，以較新獨驗報告及入口狀態為準 |
| [test_research_web.py](../tests/test_research_web.py) 的 success_result_and_reload_read_contract | TestClient 提交、等待 service、重讀 result 相等、runs 與 HTML；曲線／回撤一致性有後端斷言 | 名稱中的 reload 不是瀏覽器重整／React 輪詢，沒有 Vite |
| [test_research_optimization_web.py](../tests/test_research_optimization_web.py)、[test_research_validation_web.py](../tests/test_research_validation_web.py) 忙碌案例 | 人工設定 service._active，斷言 research_busy；有明確後端拒絕斷言 | 不是 UI 同時提交競態，也不證明目前前端忙碌標示 |
| 同一 validation 測試的 HTTP／preview 案例 | TestClient 門檻、202、封存／schema／報告；mock relay 核對 POST 白名單及 body，preview 無自己的 research writer | 不是實際 8771→8770 通路或隔離瀏覽器 |
| [test_workspace_f1.py](../tests/test_workspace_f1.py) | 舊 workspace HTML／JS 字串、路由與 mock relay、隔離後端案例 | 字串沒有 mock-data.js 不等於整個 React 無假資料；不是 React 互動 |
| 入口先前記載 Antigravity build／隔離 HTTP 9／9 | **二手歷史回報**；入口記載是 Python 直打隔離後端、非 Vite／adapter／瀏覽器；並記載 busy 允許 202 或 409 | 本輪未找到該 scratch 原稿／原始 log，不能當成本輪重新核對斷言；即使依原記錄，也不能穩定證明 busy 拒絕或 UI 整合通過 |

測試對 NO_SELECTION／OOS_FAILED／Decimal 歸屬與後端封存的支持，與頁面是否正確呈現是兩件事。未來若要補證據，按實際接入頁面的成功、失敗、斷線、忙碌、刷新／切換／離頁選取必要案例；不必為盤點重跑全部歷史測試。

本輪另做文件連結、JSON 範例與請求預設值檢查。接續入口有三個既有歷史附件缺檔：artifacts/dcm-20261011-casebook-final/index.html、artifacts/dcm-20261011-study-final/report.html、artifacts/dcm-20261011-selftest/replay-verification.json；未重建或改動其他並行工作。這些附件不能作為目前可直接開啟的證據，不影響本文件新交接連結。

## 9. 情報頁：保留唯讀路由索引，逐卡另核對

此節保留既有索引，不擴大成每張情報卡已完成契約核對。路由與 MarketIntelReader 均在 [market_api.py](../catos/market_api.py)，資料模型在 [market_intel.py](../catos/market_intel.py)；[market-intel.tsx](../frontend/cat-os-vite/src/pages/market-intel.tsx) 仍有固定 YAOZI_ALERTS／FUNDING_RATES。下列皆 GET：

| 功能 | 路徑 |
| --- | --- |
| 總覽、決策與雷達 | `/intel/today`、`/intel/decision-surface`、`/intel/decision-surface/{symbol}`、`/intel/decision-compare`、`/intel/radar` |
| 標的與 K 線 | `/intel/picks`、`/intel/picks/{symbol}`、`/intel/picks/{symbol}/candles` |
| 訊號、警報與歷程 | `/intel/signals`、`/intel/alerts`、`/intel/picks/{symbol}/timeline`、`/intel/picks/{symbol}/journey` |
| 跨軸、狀態與證據 | `/intel/cross-axis`、`/intel/status-labels`、`/intel/signal-dex/{symbol}`、`/intel/proof` |
| 資金與事件 | `/intel/raw-flow`、`/intel/raw-flow/{symbol}`、`/intel/capital-flow/{symbol}`、`/intel/event-candidates`、`/intel/event-candidates/{symbol}`、`/intel/dealer/{symbol}` |
| 鏈上與來源涵蓋 | `/intel/onchain`、`/intel/onchain/{symbol}`、`/intel/source-coverage` |
| 社群與流動性 | `/intel/social`、`/intel/picks/{symbol}/social`、`/intel/liquidity`、`/intel/picks/{symbol}/liquidity`、`/intel/picks/{symbol}/money-flow` |
| 敘事、板塊與新聞 | `/intel/narrative`、`/intel/narrative-attention`、`/intel/sectors`、`/intel/news` |
| 選擇權 | `/intel/options`、`/intel/options/{underlying}` |

資料不存在／不合格可能 503，也可能 empty／stale／coverage 不足；不回退假行情。查詢參數與 DTO 需逐路由／reader 核對，例如 candles 的 timeframe／limit 不能直接套到其他路由。本輪不提供未核對的最小結果範例，不宣稱實際 DB、新鮮度、跨交易所費率或來源已可用；此清單不授權重啟採集。

## 10. 阻擋事項與可延後項目

**對應頁面要正確串接時先處理：**

- 回測 busy 以後端 active_run_id 為準；來源／版本／任務與結果身分一致，不補假結果或無效零值。
- 隔離驗證先確認真正隔離的固定 proxy／資料根，避免把正式 writer 當 fixture；目前只研究路徑已有 Vite 代理。
- 優化／驗證使用各自 DTO；策略／Bot／R1 缺 HTTP 的部分明示不可用，不猜契約。
- 保留 Decimal 字串、null／failed／unavailable，依 catalog 和逐窗狀態顯示，不宣稱未提供指標／交易能力。

**可隨頁面成熟逐步完成，不必當前端定稿前置：**

- 參數搜尋、穩定區、逐窗 OOS、分環境的版面與逐步接線；研究 HTML 報告入口、來源快照檢視。
- 新 run 選取、背景錯誤歸屬、斷線標示與快速切換的操作細節，配合受影響頁面補必要互動證據。
- 策略／Bot 與 R1 HTTP 後端整合、真行情研究、進階指標、Demo／Live，另定範圍與授權；不能以趕前端進度補成假成功。
- 完整跨頁驗收與所有歷史測試重跑，本輪不要求；前端約 80% 的版面／操作開發照原分工進行。

## 11. 可直接貼給 Antigravity

> 請繼續依我們目前方向完成 CatOS 前端版面與操作細節，保留已定案設計；這份盤點不是要求立即改版、一次接完全部後端或完成驗收。請先讀 docs/current-handoff.md 與 docs/backend-frontend-integration-map.md，等相關頁面流程穩定後再逐步接入。
>
> 回測頁目前已接真實研究 API；參數搜尋、參數穩定區、Walk-Forward／OOS、分市場環境及研究封存／報告也已有後端 HTTP，可依文件範例與欄位對照承接。穩定區／OOS／分環境共用 validations 任務，資料目前僅登錄 SMA 與合成 K 線。金融值維持 Decimal 字串，未提供的指標不顯示成真實結果。
>
> 接線時先留意：回測頁仍自行清空 active_run_id；8890 研究代理固定到正式 8770，不能當隔離驗證；優化／驗證尚缺 React adapter／分流 DTO。策略／Bot 管理路由與 R1 風控 HTTP 尚未接通，先保留清楚的展示／不可用狀態，列出需要後端補齊的契約，不自行猜 API。新任務選取、刷新／切換／離頁與斷線提示可隨頁面成熟逐項核對，不需重做整套版面或重跑全部歷史驗收。
