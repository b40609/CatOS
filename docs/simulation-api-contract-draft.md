# v1 模擬工作區 HTTP 契約草案（Simulation Workspace API）

狀態：**草案，未核准、未實作**。日期：2026-11-02。分支 `feat/v1-simulation-api`。

目的：讓前端主工作區（戰情台 KPI、Bot 表、風控卡、持倉表、事件流水、bots 頁）從 `mock-adapter` 換成真資料。v1 只接本機模擬（local-sim），不接 Demo／Live，不碰憑證，不新增交易出口。本文件只定契約；端點與 adapter 程式分別屬第 3、4 步。

依據（唯讀核對，行號為目前工作樹）：

| 類別 | 檔案 |
| --- | --- |
| 後端控制面 | `catos/local_sim_control.py`、`catos/local_sim_control_api.py`、`catos/local_sim_control_runner.py`、`catos/workspace_api.py`、`catos/research_api.py` |
| 帳務／風控結構 | `catos/supervisor.py`、`catos/journal.py`、`catos/execution.py`、`catos/risk.py`、`catos/research.py`（`AccountView`）、`catos/local_sim_r4.py`（`project_account`／`durable_view`） |
| 策略製品 | `catos/research_catalog.py`、`catos/research_artifacts/sma-trend-sma-parameters-v1.json`、`catos/python_strategy.py`、`catos/strategy_library.py`、`catos/strategy_mcp.py`、`tests/test_python_strategy_api.py`、`tests/test_python_strategy_v1.py` |
| 前端 | `src/adapters/types.ts`、`src/adapters/mock-adapter.ts`、`src/adapters/research-api-adapter.ts`、`src/contracts/*.ts`、`src/state/catStore.ts`、`src/state/stateAdapter.ts`、`src/state/liveMarketStore.ts`、`src/state/dashboard-demo-store.ts`、六個戰情台元件與 `src/pages/bots.tsx` |
| 文件 | `docs/backend-frontend-integration-map.md`、`docs/demo-entry-contract.md`、`AGENTS.md` |

## 0. 盤點結論（寫契約前必須知道的現況）

1. **現有可用的模擬 HTTP 只有五條**（`local_sim_control_api.py:68-88`，前綴 `/api/workspace/simulation`）：`GET /version`、`GET /runs`、`GET /runs/{run_id}`、`POST /start`（body `{request_id, template_id}`）、`POST /runs/{run_id}/stop`（body `{request_id}`）。單槽、固定模板 `sma-synthetic-smoke-v1`（8 根＋2 根預熱，`local_sim_control.py:16-21`）。
2. **策略／Bot 管理 HTTP 從未掛載過。** `GET/POST /strategies`、`GET/POST /bots`、`POST /bots/start` 只出現在 `tests/test_python_strategy_api.py`、`catos/strategy_mcp.py` 與舊文件；`LocalSimControlService` 沒有 `library` 屬性，`start()` 只收 `template_id`。`git log --all -S'self.library'` 查無任何提交。對應的 8 個測試在目前基線全部 ERROR（`AttributeError: 'LocalSimControlService' object has no attribute 'library'`、`WorkerConfig.__init__() got an unexpected keyword argument 'python_strategy'`）。`python_strategy.py`／`strategy_library.py` 是半套：製品驗證與 JSON 策略庫存在，控制面與 Worker 端整合不存在。
3. **Supervisor 沒有任何狀態摘要方法**（`supervisor.py` 無 `to_dict`／`snapshot`）。可讀的是 `risk_state: risk.State`（`:66`）、`halt_reasons`、`health`、`revision`、`epoch`、`total_reserved` 等屬性；`journal.Journal.snapshot(bot_id)` 回 `{checkpoint, revision, isolated, health, epoch, halt_reasons, owner, total_reserved, pending, risk_state}`（`journal.py:687-695`）。
4. **journal 沒有任何帶掛鐘時間戳的稽核表。** `risk_actions`（`journal.py:251-254`）只有 rowid 序；`execution_orders` 有 `deadline`／`epoch` 無建立時間；`execution_fills` 無時間無序號。可當事件流水的現成來源，只有控制面 run 記錄裡的 `events`（`local_sim_control.py:316-326`，每 run 環形上限 `MAX_EVENTS=40`，有 `wall_time` ISO 字串）。
5. **runner 每根 bar 已經拿到完整帳戶視圖與風控狀態**：`signal` 事件帶 `account=ipc.account_to_wire(view)`（`AccountView`：`time_ms, position, average_entry, balance, realized_pnl, unrealized_pnl, equity, fees, funding_paid`，全 Decimal 字串，`research.py:92-101`），`final_account` 帶 `risk_state=supervisor.risk_state.to_wire()`（`runner:130-131`）。風控／持倉 DTO 可從這裡投影，不必另開 SQLite reader。
6. **前端現況比「換 adapter」更深。** `catStore` 的 `kpis/bots/risk/telemetry/equitySeries/auditLogs` slice 由 `stateAdapter.init()` 用 mock 餵入，但**戰情台六個元件與 `pages/bots.tsx` 沒有任何一個讀 `catStore`**。它們的資料來自 `liveMarketStore`（1 秒 tick 重播 `MARKET_TAPE_10M` 常數，全是 JS number）、`dashboard-demo-store` 的 `usePreviewStore`（寫死的 `INITIAL_EVENTS_DATA`）、`inspectorStore` 的 `INSPECTOR_BOTS`、`lib/v0-engine` 與元件內常數（例如 `allocation-donut-card.tsx` 的 pnl 視圖全為寫死數字，`activity-panel.tsx` 的資金費率字串寫死）。`catStore` 唯二消費者是 `mode-selector.tsx:66`（`mode`）與 `lib/i18n.ts`（`language`）。`stateAdapter.handleEvent()` 沒有呼叫者。因此第 4 步除了寫 real-adapter，還必須把元件改讀 store（見第 7 節）。
7. **同源／版本門檻已有兩套可沿用**：research（`research_api.py:90-127`：host 127.0.0.1、Origin 必須等於 base_url、`Content-Type: application/json`、`X-CatOS-Build` 等於 loaded build、body ≤ 8192、拒絕重複鍵與非有限常數）與 simulation（`local_sim_control_api.py:42-66`：同上再加 `X-CatOS-Instance` 必須等於 `service.instance_id`、精確欄位集合、`request_id` 為 32 hex）。錯誤格式皆為 HTTP status ＋ `{"detail": "<snake_case_code>"}`。
8. `research-api-adapter.ts` 的四條不變量（檔頭 12-16 行）：Decimal 字串、真 API 模式絕不回退 fixture、POST 失敗絕不產生假 run_id／假成功／自動重送、保留 403/409/413/415/422/503 的 detail。它目前**不送 Origin、不送 `X-CatOS-Instance`、body 無 `request_id`**；simulation 的 adapter 必須補齊後兩者。

## 1. 端點清單

全部掛在既有前綴 `PREFIX = /api/workspace/simulation`，由同一個 `LocalSimControlService` 提供，沿用同一組 middleware（`X-CatOS-Build`、`X-CatOS-Instance`、`Cache-Control: no-store`）。GET 一律唯讀、冪等、不建立任何狀態；POST 一律以 `request_id` 綁定。

| 方法 | 路徑 | 用途 | 冪等性 | 對應後端 | 狀態 |
| --- | --- | --- | --- | --- | --- |
| GET | `/version` | build／instance／slot／capabilities／config | 是 | `LocalSimControlService.version()`（`:204-215`） | **既有** |
| GET | `/state` | 聚合快照：version＋strategies＋bots＋risk＋positions＋summary＋最近事件，供 `stateAdapter.init()` 一次拉齊與輪詢 | 是 | 新增 `service.state(since_version=None)`，內部組合下列各節的投影函式 | 新增 |
| GET | `/strategies` | 可用策略清單；v1 只有登錄的 SMA | 是 | 新增 `service.strategies()`，來源 `research_catalog.STRATEGY_MANIFEST`＋`DEFAULT_REQUEST` | 新增 |
| GET | `/bots` | Bot 清單（v1 固定一個） | 是 | 新增 `service.bots()` | 新增 |
| GET | `/bots/{bot_id}` | 單筆 Bot＋最近一次 run 投影 | 是 | 新增 `service.bot(bot_id)`；404 `bot_not_found` | 新增 |
| POST | `/bots/start` | 啟動 Bot（v1 等於用固定模板開一個 run） | 以 `request_id` 冪等：同 id 同 body 回同一 run；同 id 不同 body 409 `request_id_conflict` | 新增薄包裝 → 既有 `service.start(request_id, template_id=TEMPLATE)`（`:241-282`），回 202 | 新增（包裝既有） |
| POST | `/start` | 既有固定模板啟動 | 同上 | `service.start` | **既有**，v1 保留給舊頁與測試 |
| POST | `/runs/{run_id}/stop` | 停止 run（本事件完成後停） | 以 `request_id` 冪等 | `service.stop(run_id, request_id)`（`:284-306`），202 | **既有** |
| GET | `/runs` | run 清單（新到舊） | 是 | `service.list_runs()`（`:228-231`） | **既有** |
| GET | `/runs/{run_id}` | 單 run 快照 | 是 | `service.snapshot(run_id)`（`:217-226`） | **既有** |
| GET | `/risk` | 帳戶風控快照（active／最近一次 run） | 是 | 新增 `service.risk()`，投影自最新 `signal`／`final_account` 事件的 `account`＋`risk_state` 與 `risk.Limits` | 新增 |
| GET | `/positions` | 部位清單（v1 單合約，0 或 1 筆） | 是 | 新增 `service.positions()`，投影自同一來源 | 新增 |
| GET | `/events?since=<seq>&limit=<n>` | 審計流水，游標分頁 | 是 | 新增 `service.events(since, limit)`，來源為控制面事件（run 生命週期＋`warmup`／`signal`／`fill`／`final_account`）加全域序號 | 新增 |

不提供（v1）：`POST /strategies`、`POST /bots`（建立製品／配置 Bot，見第 6 節 Q1）、任何 `demo`／`live` 路徑、任何 WebSocket。

**推送 vs 輪詢：v1 用輪詢。** 理由：(a) 控制服務是單事件迴圈、單槽，run 長度固定 8 根×1 秒，事件量極小；(b) 現有研究頁已是輪詢模式（`backtest.tsx`／`use-optimization-research.ts`），前端沒有 WS 基礎設施，加 WS 要處理重連、同源驗證與 instance 變更，驗證成本高於收益；(c) `GET /state?since_version=N` 在無變化時回 `{"unchanged": true, "version": N}`（或 304），輪詢成本接近零。建議節奏：有 active run 時 1 秒，idle 時 5 秒；tab 不可見時暫停（與 `shell.tsx` 現有 1 秒 tick 合併，避免兩套計時器）。

## 2. DTO 定義

通則：

- 金額、價格、數量、比例一律 **Decimal 字串**（沿用 `account_to_wire`／`State.to_wire` 的字串化）；百分比用「比例字串」（`"0.0184"`），不帶 `%`、不帶千分位，格式化在前端。
- 時間：新增欄位一律 **epoch ms 整數**，欄位名以 `_ms` 結尾。既有 run 記錄的 `created_at`／`finished_at`／`stop_requested_at`／`wall_time` 是 ISO 字串且被現有測試與 `control.json` 契約鎖住（`local_sim_control.py:163-168`），v1 **保留原欄位不改**，另加對應 `*_ms`（見 Q6）。
- 版本：每個 DTO 帶 `version`（整數），來源是服務內單調遞增的 `state_version`，每次 `_save`／`_emit`／`_update` 成功後 +1；重啟歸零但 `instance_id` 改變。前端規則：`instance_id` 與上次不同 → 清空 `versionMap` 再套用（等同現有 `store.setMode` 的清空行為）。
- 缺值用 `null`，不用 `"--"`、不用 `0`、不用 `"unknown"`（mock 目前三者都有）。
- 列舉值沿用後端原字串，不在後端做大小寫或語意轉換。

### 2.1 `VersionDTO`（既有，不改）

`service.version()` 原樣：`contract:"catos.simulation.v1"`, `mode:"local-sim-synthetic"`, `build_id`, `current_build_id`, `restart_required`, `instance_id`, `slot: "idle"|"starting"|"running"|"stopping"|"recovery_required"|"unavailable"`, `active_run_id`, `capabilities:{start,stop}`, `unavailable_reason`, `config`。前端 `contracts/workspace.ts:16-31` 已對齊。

### 2.2 `WorkspaceStateDTO`（`GET /state`，新增）

```jsonc
{
  "contract": "catos.simulation.v1",
  "version": 1287,                 // state_version，給 versionMap.global
  "observed_at_ms": 1762090000000,
  "instance_id": "…32hex…",
  "service": { ...VersionDTO },    // 同 /version
  "strategies": [ StrategyEntryDTO ],
  "bots": [ BotViewDTO ],
  "risk": RiskSnapshotDTO | null,  // 無任何 run 時 null
  "positions": [ PositionDTO ],
  "summary": SummaryDTO | null,
  "events": { "items": [ EventDTO ], "next_since": 412, "omitted": 0 },  // 最近 ≤40 筆
  "domains": { "bots": 1287, "risk": 1280, "positions": 1280, "events": 1287 } // 各 domain 最後變更版本
}
```

`domains` 讓前端對各 slice 分別套用 `applyAuthoritativeUpdate`（`catStore.ts:121-136` 接受相等版本、拒絕較舊），與 `hydrateAll` 的逐 domain 門檻（`:138-152`）一致。`since_version` 等於目前 `version` 時回 `{"contract":…, "unchanged": true, "version": N, "instance_id": …}`。

### 2.3 `StrategyEntryDTO`（`GET /strategies`）

v1 只有一筆，來源固定：

| 欄位 | 型別 | 來源 |
| --- | --- | --- |
| `strategy_id` | string | `research_catalog.STRATEGY_ID = "sma-trend"` |
| `version` | string | `STRATEGY_VERSION = "sma-parameters-v1"` |
| `name` | string | 製品 `artifact_id`＋`version`（manifest 無 name 欄；v1 由後端組字串，Q2） |
| `artifact_hash` | string | manifest `sha256`（`APPROVED_STRATEGY_SHA256`） |
| `approval_state` | `"approved"` | manifest `approval_state` |
| `allowed_modes` | `["local"]` | 固定 |
| `defaults` | object | `DEFAULT_REQUEST.parameters` = `{"period": 2, "quantity": "2"}` 與 `warmup_bars: 2` |
| `source_files` | string[] | manifest `source_files` |
| `kind` | `"registered_python_module"` | 區分於 `catos.python-strategy.v1` 上傳製品 |

與前端 `contracts/strategy.ts` 的 `StrategyEntry{artifact: StrategyArtifact, artifact_hash, allowed_modes, created_at}` **不同構**：那個型別是為 `python_strategy.py` 的上傳製品（含 `source` 原始碼）設計的，v1 沒有上傳製品。建議新增 `RegisteredStrategyDTO` 型別而不是硬塞 `StrategyArtifact`（`source` 欄位會被迫填空字串，違反 `validateArtifact` 的 `source` 長度 > 0 規則）。

### 2.4 `BotDTO`／`BotViewDTO`（`GET /bots`、`GET /bots/{id}`）

v1 固定一個 Bot，`bot_id = "sim-control-sma"`（runner 已用此 id 建 Supervisor，`runner:63`）。

**靜態欄位（BotDTO）**

| 欄位 | 型別 | 來源 |
| --- | --- | --- |
| `bot_id` | string | 固定常數 |
| `mode` | `"local"` | 固定 |
| `strategy_id`／`strategy_version`／`artifact_hash` | string | 同 2.3 |
| `parameters` | object | `DEFAULT_REQUEST.parameters` |
| `contract_id` | string | `config.contract`（`ipc.ContractSpec`，由 `validate_request(DEFAULT_REQUEST)` 產生，runner `:52,58`） |
| `symbol` | string | `ContractSpec.inst_id`（需於第 3 步核對欄位名，`ipc.py` ContractSpec） |
| `timeframe_ms` | int | `CONFIG.candle_timeframe_ms = 900000` |
| `trusted` | `true` | 固定（登錄製品） |
| `created_at_ms` | int | 服務啟動時間（v1 無持久建立時間） |

**執行投影（BotViewDTO = BotDTO ＋ 以下）**，來源為最近一次 run（`service.runs` 依 `run_id` 建立序倒排第一筆）：

| 欄位 | 型別 | 來源 |
| --- | --- | --- |
| `state` | `BotControlState` | `run.control_state`；無 run 時 `"stopped"` |
| `current_run_id` | string\|null | `service.active` 或最近 run |
| `worker_pid` | int\|null | `run.worker_pid`（runner `update(worker_pid=…)`，`:80`） |
| `bars`／`warmup_bars`／`fills` | int | run 記錄 |
| `last_synthetic_time_ms` | int\|null | `run.last_synthetic_time_ms`（`:125`） |
| `position` | Decimal str\|null | 最新 `account.position` |
| `average_entry` | Decimal str\|null | `account.average_entry` |
| `equity` | Decimal str\|null | `account.equity` |
| `realized_pnl`／`unrealized_pnl`／`fees`／`funding_paid` | Decimal str\|null | `account.*` |
| `last_disposition`／`last_reason` | string\|null | 最新 `signal` 事件 `disposition`／`reason`（`NO_INTENT`／`NO_CHANGE`／`RESERVED_SIMULATION`…） |
| `ownership_retained` | bool | 終態且 `position != "0"`（來源 `final_account.account.position`；見 Q4） |
| `error` | string\|null | `run.error` |

**對照 `contracts/bot.ts` 的 `Bot`：mock 有、後端沒有的欄位**

| mock／`Bot` 欄位 | 後端有無 | 建議 |
| --- | --- | --- |
| `name` | 無 | 刪；UI 顯示 `bot_id` 或策略名 |
| `symbol` | 有（`ContractSpec`） | 保留，改為 `contract_id`＋`symbol` |
| `pnl_usdt`（mock 填 `realized_pnl`） | 有 | 拆為 `realized_pnl`＋`unrealized_pnl`，不合併 |
| `position_contracts`／`equity_usdt`／`fee_usdt` | 有 | 改名 `position`／`equity`／`fees`，與 `AccountView` 同名 |
| `side` | 可推導 | 前端由 `position` 正負推導，不傳 |
| `entry_price` | 有（`average_entry`） | 改名 |
| `mark_price` | `AccountView` 無；`risk.Snapshot.mark` 有 | 放在 `RiskSnapshotDTO.mark`（Q5：是否同步加進 `signal` 事件） |
| `roe_pct` | 無保證金模型 | **v1 不提供**（null）；local-sim fixture 無 margin，算 ROE 會是假數 |
| `timeframe` | 有（`timeframe_ms`） | 前端格式化成 `15m` |
| `next_bar_countdown` | 無 | **v1 不提供**；合成時間不是掛鐘倒數 |
| `sl_price`／`sl_distance_pct` | `protection` 表只在 `configure_protection` 後存在；runner 未配置 | **v1 不提供**（null），UI 顯示「未啟用」而非 `--` |
| `nominal_value_usdt` | 可算（`risk.worst_notional`／`Snapshot.position*mark*base_per_contract`） | 放 `RiskSnapshotDTO.notional` |
| `margin_usdt`／`leverage` | 無保證金；`effective_leverage` 有 | `margin` 不提供；`effective_leverage` 放風控 DTO |
| `worker_cpu`／`worker_rss`／`ipc_heartbeat_ago` | 無採集 | **v1 不提供**（null） |
| `strategy_step` | 可用 `last_disposition`／`last_reason` | 改名 |
| `recent_signals[]`（`bar_time, signal, close_price, pnl_delta, note`） | `signal` 事件有 `seq, synthetic_time_ms, target, disposition, reason, account` | 由 `/events` 取 `kind=signal`，不內嵌於 Bot |
| `risk_retained` | 無此概念 | 刪；風控鎖存看 `RiskSnapshotDTO.reasons` |

### 2.5 `RunDTO`（既有＋擴充）

既有 `service.snapshot(run_id)` 欄位全部保留（`run_id, request_id, config, build_id, instance_id, created_at, control_state, cleanup_confirmed, stop_requested, stop_requested_at, bars, warmup_bars, fills, events, events_omitted, error, finished_at, worker_closed, still_finishing, last_signal?, last_fill?, worker_pid?, last_synthetic_time_ms?`）。前端 `contracts/run.ts:18-52` 的 `RunDTO` 大致對齊，但下列欄位 mock 有、後端沒有：`bot_id`（v1 後端新增，常數）、`template_id`（在 `config.template_id`）、`account`（改由 `last_signal.account`／`final_account` 投影成 `BotViewDTO`，或後端在 `snapshot()` 補 `last_account`，Q5）、`artifact_hash`／`binding`／`symbol`／`period`／`slippage_bps`（在 `config.research_request`，前端自行讀）。

`SimulationRun`（`run.ts:63-86`）是 mock 的 view model，含 `total_bars`／`current_bar`（mock 都填 `bars`）、`trade_count`（=`fills`）、`updated_at`；真 adapter 不需要這層，建議第 4 步刪除 `SimulationRun`，頁面直接用 `RunDTO`。

### 2.6 `RiskSnapshotDTO`（`GET /risk`）

來源：`risk.State.to_wire()`（`risk.py:422-428`）＋ `risk.Limits.to_wire()`（`:40-41`）＋ 後端 Decimal 計算。v1 取自 active run 的最新觀測；無 run 時 `null`。

```jsonc
{
  "version": 1280,
  "run_id": "…",
  "seq": 7, "time_ms": 1762092900000,           // State.seq / State.time_ms（合成時間）
  "mode": "RUN" | "NO_INCREASE" | "FLAT",        // State.mode（risk.py:457）
  "health": "RECONCILING" | "HEALTHY" | "DEGRADED",
  "phase": "IDLE" | "WORKING" | "VERIFY" | "WAIT" | "DONE",
  "reasons": ["soft_loss"],                      // State.reasons ⊆ {soft_loss, hard_loss, manual_kill}
  "epoch": 3,
  "limits": { "leverage": "3.0", "symbol_share": "0.50", "soft_loss": "0.10", "hard_loss": "0.20" },
  "basis": {                                     // DayBasis.to_wire()（risk.py:220）；null = 尚無基準
    "day": 20760, "equity": "1000", "evidence_id": "r4-midnight-20760",
    "source": "…", "account_alias": "sim-control-…", "environment": "local-sim",
    "period_start_ms": null                      // R1 實際起算時間；local-sim 合成午夜基準時與 day 起點相同（Q7）
  },
  "snapshot": {                                  // risk.Snapshot.to_wire()（risk.py:383）
    "equity": "1003.21", "risk_equity": "1003.21", "position": "2", "mark": "101.5",
    "pending_buy": "0", "pending_sell": "0", "other_notional": "0", "external_net": "0",
    "valuation_known": true, "flows_known": true, "margin_ok": true,
    "position_verified": true, "reduction_conflict": false, "valid_until_ms": 1762093800000
  },
  "derived": {                                   // 後端 Decimal 算，不給前端算
    "period_pnl": "3.21",                        // equity - basis.equity - external_net（risk.py:469-471 同式）
    "period_pnl_ratio": "0.00321",
    "notional": "203",                           // worst_notional 或 |position|*base_per_contract*mark
    "effective_leverage": "0.2024",              // risk.effective_leverage((notional,), equity)；equity<=0 → null
    "exposure_budget": "3009.63",                // limits.leverage * risk_equity（risk.py:613）
    "symbol_budget": "1504.815",                 // budget * symbol_share
    "can_increase": true,                        // mode == RUN && health == HEALTHY && basis != null
    "status": "normal" | "soft_latch" | "hard_latch" | "missing"
  }
}
```

`derived.status` 對映：`reasons` 含 `hard_loss`／`manual_kill` → `hard_latch`；含 `soft_loss` → `soft_latch`；`basis == null` 或 `health != HEALTHY` → `missing`；否則 `normal`。與 `contracts/risk.ts:7` 的 `RiskStatus` 四值一致，`DashboardKPIs.risk_status` 的 `UNAVAILABLE`／`UNKNOWN` 由前端在 HTTP 失敗時自行標記，不由後端回。

對照 `contracts/risk.ts` 的 `RiskState`：`day_start_equity_usdt`→`basis.equity`；`current_equity_usdt`→`snapshot.equity`；`daily_pnl_*`→`derived.period_pnl*`（**語義改為「風控期間損益」**，依 R1）；`soft/hard_loss_limit_pct`→`limits`；`current_drawdown_pct`→與 `period_pnl_ratio` 同值，刪；`exposure_nominal_usdt`→`derived.notional`；`exposure_budget_usdt`→`derived.exposure_budget`；`margin_used_usdt`／`margin_available_usdt`→**v1 不提供**（無保證金模型，`margin_ok` 是布林）；`fixed_tag_active`→不是風控狀態，改放 `summary.invariants`；`latched_reasons`→`reasons`。`ExposureAllocationItem{label, nominal_usdt, pct_share, color}`：v1 單合約只有一筆，`color` 不該由後端給，刪。

### 2.7 `PositionDTO`（`GET /positions`）

v1 單合約：`position == "0"` 時空陣列，否則一筆。

| 欄位 | 型別 | 來源 |
| --- | --- | --- |
| `bot_id`／`run_id` | string | 常數／active run |
| `contract_id`／`symbol` | string | `ContractSpec` |
| `position` | Decimal str | `account.position`（帶正負） |
| `average_entry` | Decimal str | `account.average_entry` |
| `mark` | Decimal str\|null | `risk.Snapshot.mark`（Q5） |
| `unrealized_pnl` | Decimal str | `account.unrealized_pnl` |
| `notional` | Decimal str\|null | 同 `derived.notional` |
| `verified` | bool | `Snapshot.position_verified` |
| `ownership_revision` | int\|null | `ownership.reconciled_revision`（需讀 journal；v1 可省略，Q3） |
| `protection` | null | P6 未配置（`protection` 表不存在此 run）；**v1 固定 null** |
| `funding_interval_ms`／`funding_rate` | null | 合成資料 `funding: "explicit_zero"`；**v1 不提供** |
| `liquidation_price`／`margin` | null | 無保證金／強平模型；**v1 不提供** |

`activity-panel.tsx` 目前渲染的 `liqPrice`、`distLiqPct`、`mmr`、`fundingIntervalHours`、`p6StopPrice`、`p6Status`、`p6DistPct` 在 v1 都沒有真值，第 4 步要改成「不適用」狀態而不是沿用寫死數字。掛單表（`INITIAL_ORDERS`）在 local-sim 中沒有對應來源（每筆意圖立即以合成 FILLED 終結，`runner:111-115`），v1 固定空陣列。

### 2.8 `EventDTO`（`GET /events`）

來源：控制面事件（`service._emit`）與 run 狀態轉換（`service._update` 的 `control_state` 變化、`stop` 命令）。v1 由服務在記錄時附上全域 `seq`（整數，單調遞增、重啟歸零並由 `instance_id` 區分）。

```jsonc
{ "seq": 412, "run_id": "…", "bot_id": "sim-control-sma",
  "kind": "run_state" | "warmup" | "signal" | "fill" | "final_account" | "stop_requested",
  "wall_time_ms": 1762090001234, "synthetic_time_ms": 1762092900000,   // 後者僅 signal/fill
  "level": "INFO" | "WARN" | "ERROR",            // 後端固定映射：failed/recovery_required → ERROR；stopping/stop_requested/NO_INCREASE/FLAT → WARN；其餘 INFO
  "category": "SUPERVISOR" | "WORKER" | "RISK" | "ORDER" | "SYSTEM",   // run_state→SYSTEM, warmup/signal→WORKER, fill→ORDER, final_account→RISK
  "payload": { /* 原事件欄位原樣：signal 的 target/disposition/reason/account/intent_key；fill 的 request/fill/position/fees/equity/state */ } }
```

分頁：`?since=<seq>&limit=<1..200>`，回 `{items, next_since, omitted}`；`omitted` 來自各 run 的 `events_omitted`（環形上限 40）。前端 `AuditLogItem{id, timestamp, level, category, message, details}`（`command.ts:40-47`）：`id`=`run_id:seq`、`timestamp`=`wall_time_ms`、`message` 由前端依 `kind` 與 `payload` 組字串（後端不產生中文文案）。`unified-incident-activity-card.tsx` 現在依 `title` 子字串推斷 `domain`（`:26-34`），改讀 `kind`／`category` 後可刪推斷。

### 2.9 `SummaryDTO`（戰情台 KPI）

後端以 Decimal 計算，前端只格式化：

| 欄位 | 來源 |
| --- | --- |
| `equity` | `account.equity` |
| `period_pnl`／`period_pnl_ratio` | 同 `RiskSnapshotDTO.derived` |
| `realized_pnl`／`unrealized_pnl`／`fees` | `account` |
| `period_start_ms`／`basis_equity` | `basis` |
| `running_bots`／`total_bots` | `active != null ? 1 : 0`／`1` |
| `risk_status`／`effective_leverage`／`leverage_limit` | `derived.status`／`derived.effective_leverage`／`limits.leverage` |
| `invariants` | `{"fixed_tag": "41cb53c54d6dABDE", "settlement": "cross_net_mode", "arithmetic": "decimal_text"}`（常數，取代 mock `TelemetryState` 的 `fixed_tag_active`／`settlement_mode`／`core_arithmetic`） |

`DashboardKPIs` 的 `equity_change_pct`（7 日變化）、`bots_summary_note`、`risk_sub_note` 是 mock 文案，刪。權益曲線（`fetchEquityCurve`）v1 由 `/events` 的 `signal.account.equity` 序列組成（最多 40 點），不另開端點；`account-equity-band.tsx` 現用 `lib/v0-engine` 合成序列，第 4 步改接。

## 3. 錯誤契約

沿用現行格式：HTTP 狀態碼 ＋ JSON body `{"detail": "<snake_case_code>"}`（`ControlError` handler `local_sim_control_api.py:29-31`；research 同 `research_api.py:103-105`）。code 是穩定識別字，不是人類文案；前端 `handleResponse` 讀 `detail`（`research-api-adapter.ts:236-250`）可直接沿用。新增 GET 端點用同一格式，不回 `{status, reason}` 巢狀物（那只在 `UnavailableMarketReader` 出現，不採）。

| HTTP | code | 何時 |
| --- | --- | --- |
| 403 | `simulation_requires_127_0_0_1` | 任何非 127.0.0.1 host（含 GET，擴大現行只檢查 POST 的範圍） |
| 403 | `simulation_origin_mismatch` | POST 的 Origin 存在且 ≠ base_url |
| 403 | `mode_not_available` | 路徑或 query 帶 `demo`／`live`，或 body 的 `mode` 不是 `"local"`（新增） |
| 404 | `run_not_found`／`bot_not_found` | 既有／新增 |
| 409 | `service_instance_mismatch`／`page_version_mismatch_reload_required` | POST header 不等於 `instance_id`／`loaded_build` |
| 409 | `source_changed_restart_required` | `current_build != loaded_build` |
| 409 | `request_id_conflict` | 同 `request_id` 不同操作或不同 body |
| 409 | `simulation_slot_occupied`／`simulation_run_limit`／`simulation_stop_command_limit` | 既有 |
| 409 | `ownership_retained` | 最近 run 終態但 `position != 0`，再次 start（v1 若採 Q4 的保留規則） |
| 413 | `simulation_request_limit` | body > 8192 |
| 415 | `application_json_required` | POST content-type |
| 422 | `invalid_json`／`invalid_command_contract`／`invalid_template_id`／`unsupported_template`／`invalid_run_id` | 既有 |
| 422 | `invalid_bot_id`／`invalid_since`／`invalid_limit` | 新增 GET／POST 參數 |
| 503 | `not_started`／`simulation_output_in_use`／`simulation_metadata_unavailable`／`simulation_metadata_write_uncertain`／`simulation_run_directory_uncertain`／`simulation_service_closing`／`simulation_source_unavailable` | `ControlError` 預設 503（`local_sim_control.py:45-48`），服務 `unavailable` 時所有 POST 與 `/state`、`/risk`、`/positions` 皆 503；`/version`、`/runs` 仍可回（含 `unavailable_reason`） |

輪詢無變化：`GET /state?since_version=N` 回 200 `{"unchanged": true, …}`（不用 304，避免 fetch 快取語義與 `no-store` 衝突）。

## 4. 安全與邊界

- 只回 local-sim：所有 DTO 的 `mode` 固定 `"local"`／`"local-sim-synthetic"`；服務內沒有任何讀取憑證、環境變數或對外連線的路徑（`local_sim_control_runner.py` 使用 `FakeExchange`）。任何含 `demo`／`live` 的請求回 403 `mode_not_available`，不回 404（讓前端能區分「不存在」與「被禁止」）。
- 同源與版本：POST 維持 `local_sim_control_api.py:42-66` 全套檢查；GET 加 host 檢查。回應維持 `X-CatOS-Build`／`X-CatOS-Instance`／`Cache-Control: no-store`。前端 POST 必帶 `X-CatOS-Build`、`X-CatOS-Instance`（取自 `/version`）、`Content-Type: application/json`、body 僅精確欄位集合、`request_id` 由前端 `crypto.randomUUID()` 去連字號產生並在送出前存入 `sessionStorage`（`PendingCommand` 契約 `command.ts:19-25` 已定義）。
- 不新增寫入面：`/state`、`/risk`、`/positions`、`/events` 不碰 SQLite 寫、不建立基準、不解除 latch、不釋放 ownership。v1 不提供 kill-switch／re-arm／set_loss_limits HTTP（`supervisor.latch`／`rearm`／`set_loss_limits` 存在但未授權接入，見 Q8）。
- 不讀產品 DB：v1 投影只用控制面記憶體與 `control.json`；若 Q3 選讀 `state.sqlite3`，必須 `mode=ro` 且只在 run 終態後讀。
- 上限：`/events` `limit ≤ 200`；`/state` 的 `events` 固定最近 40；回應不含 `source` 原始碼。

## 5. 模式切換（前端 `setMode`）

現況：`stateAdapter.setMode()`（`stateAdapter.ts:107-113`）→ `mockAdapter.setMode` → `store.setMode`（清空所有 slice 與 `versionMap`，`catStore.ts:97-112`）→ `init()`。mock 在 demo／live 回固定「locked」KPI、空陣列、`status:'missing'` 與 `latched_reasons:['MODE_NOT_OPEN']`，mutation 丟 `DEMO_MODE_LOCKED`。

v1 規則：

1. `mode === 'local'`：real adapter 走本文件端點。
2. `mode === 'demo' | 'live'`：adapter **不發任何請求**，所有 fetch 立即 resolve 成明確的「不可用」結果：`{available: false, reason: "mode_not_open"}` 型別化回傳（不是丟例外、不是回 mock 資料、不是回 `'--'`）；所有 mutation reject `ResearchApiError(403, "mode_not_available")` 同格式。與 research adapter「絕不回退 fixture」一致。
3. 切換時 `store.setMode` 既有的清空行為保留；另外 real adapter 切回 local 時必須重新 `GET /version`，若 `instance_id` 改變，視同全新基線。
4. `ScenarioType`（`normal`／`soft_loss`／`hold_stopped_409`／`empty`／`service_unavailable`／`demo_live_locked`）是 mock 專用，real adapter 忽略；第 4 步從 `WorkspaceAdapter` 介面移除 `scenario`／`setScenario`／`resetStorage`，或保留在 mock 實作但不列入介面（Q9）。

## 6. 未決問題（需作者決定）

| # | 問題 | 建議 | 理由 |
| --- | --- | --- | --- |
| Q1 | 策略／Bot 資料模型：(a) v1 固定一個登錄 SMA 策略＋一個固定 Bot（唯讀清單，start 走既有模板）；(b) 接通 `strategy_library.py` 的上傳製品／`allocate` 流程（補 `service.library`、`WorkerConfig.python_strategy`、`worker_host` 執行 Python 製品） | **(a)** | 作者 v1 路線「只放行 SMA」；(b) 等於把一個從未提交、8 個測試全 ERROR 的工作包納入 v1，且涉及受信策略邊界與 Worker 執行任意 Python，不是前端串接的範圍。(b) 保留為 v2 候選，端點路徑已預留（`POST /strategies`、`POST /bots`） |
| Q2 | 登錄策略的顯示名稱與說明從哪來（manifest 無 `name`／`description`） | 後端在 `research_catalog.catalog()` 旁加固定中文名／說明常數 | 不在前端寫死字串，也不改 manifest schema |
| Q3 | 風控／持倉的資料來源：(a) 控制面事件投影（記憶體）；(b) 唯讀開 `<run>/state.sqlite3` 讀 `ownership`／`risk_control`／`execution_fills` | **(a)**，runner 另在每根 bar 的 `signal` 事件加 `risk_state`（目前只有 `final_account` 有） | 不新增第二個 SQLite reader、不碰單 writer 邊界；run 只有 8 根，投影完整。(b) 在 Q1(b) 或多 Bot 時再評估 |
| Q4 | Bot 與 run 的對應、以及「停止時帶倉」如何呈現：mock 以 `ownership_retained` 阻擋再次 start（409）；後端現行 `start()` 只看槽位與 `cleanup_confirmed`，沒有保留倉位的概念（那在未提交的 `retained_run` 設計裡） | v1 `BotViewDTO.ownership_retained` 只做**顯示**（終態且 `position != 0`），**不**在 `start` 加 409 `ownership_retained` | 每個 run 都是全新 `account_id`（`"sim-control-" + run_id`）與新 DB，上一 run 的倉位不會延續，阻擋沒有帳務意義；真正的單合約獨佔要等多 Bot／持久帳戶才有對象 |
| Q5 | `mark` 與 `risk_state` 要不要加進每根 bar 的 `signal` 事件（目前 `account` 無 mark，`risk_state` 只在 `final_account`） | 加：`signal.payload` 增 `mark`（= `bar.close`）與 `risk_state`（`State.to_wire()`） | 讓 `/risk`、`/positions` 在 run 進行中就有值；這是 runner 的小改動，不改帳務 |
| Q6 | 時間格式：新 DTO 用 epoch ms，但既有 run 記錄是 ISO 字串且被 `control.json` 契約鎖住 | 新欄位 `*_ms`；既有 ISO 欄位原樣保留，`RunDTO` 兩者並存 | 改既有欄位要改 `_validate` 與多個測試，收益小 |
| Q7 | R1「風控期間基準」在 local-sim 的呈現：合成 run 以午夜基準起算（`local_sim_r4.observe`），沒有「首次合格觀測時間」 | `basis.period_start_ms` 在 local-sim 回 `day` 起點；UI 標示「合成基準」而不是「風控期間起算」 | 不把合成資料的語義寫成已接 R1 HTTP；R1 HTTP 另案 |
| Q8 | 是否在 v1 暴露 kill-switch／re-arm／門檻修改 HTTP | **不暴露**；UI 的 Kill Switch 按鈕在 local 模式顯示為「未接線」 | 政策面動作（鎖存、人工恢復）牽涉金融底線與 AGENTS 授權，不應混入前端串接工作包 |
| Q9 | `WorkspaceAdapter` 介面瘦身：移除 `scenario`／`setScenario`／`resetStorage`／`fetchResearchTasks`／`fetchYaoziAlerts`／`fetchEquityCurve`／`fetchExposureAllocation`，改為 `fetchState`／`fetchEvents`／`startBot`／`stopBot`／`setMode` | 瘦身 | mock 專用方法進入正式介面會讓 real adapter 被迫實作假方法；`researchTasks`／`yaoziAlerts` slice 本來就從未被 hydrate |
| Q10 | 元件改接策略：(a) 六個元件改讀 `catStore` slice；(b) real adapter 把資料灌進 `liveMarketStore`／`usePreviewStore` 現有形狀 | **(a)** | (b) 要把 Decimal 字串轉成那兩個 store 的 JS number 欄位，違反 Decimal 不變量；且 `liveMarketStore` 內建 tick 重播與隨機漫步，無法關掉又不改檔 |
| Q11 | 事件流水來源：控制面事件（本草案）vs journal `risk_actions`／`execution_orders` | 控制面事件 | journal 無掛鐘時間與統一序號，拼接需要跨表推斷；控制面事件已涵蓋 signal／fill／風控終態 |

## 7. 實作順序

### 第 3 步：後端端點（不動帳務核心）

| 檔案 | 改動 |
| --- | --- |
| `catos/local_sim_control.py` | 加 `state_version` 計數與 `domains` 版本；`_emit` 加全域 `seq`、`wall_time_ms`；`_update` 在 `control_state` 變化時產生 `run_state` 事件；新增唯讀投影方法 `strategies()`、`bots()`、`bot()`、`risk()`、`positions()`、`summary()`、`events(since, limit)`、`state(since_version)`；`BUILD_FILES` 不需改（已含本檔） |
| `catos/local_sim_control_runner.py` | 依 Q5 在 `signal` 事件加 `mark` 與 `risk_state`；其餘不動 |
| `catos/local_sim_control_api.py` | 掛 8 條 GET 與 `POST /bots/start`；GET 加 host 檢查；`mode_not_available` 守門 |
| `catos/research_catalog.py` 或新 `catos/simulation_catalog.py` | 登錄策略的顯示常數（Q2） |
| `tests/test_local_sim_control.py`（擴充）或新 `tests/test_simulation_workspace_api.py` | TestClient 隔離資料根：`/state` 聚合與 `unchanged`、各 GET 的 Decimal 字串型別、`events` 游標、403 demo／live、`request_id` 冪等、既有五條路由行為不變 |
| `docs/backend-frontend-integration-map.md` | 第 6 節「尚不能接成 HTTP」改列實際掛載的路由 |

不動：`supervisor.py`、`journal.py`、`execution.py`、`risk.py`、`python_strategy.py`、`strategy_library.py`、任何 schema。

### 第 4 步：前端 real adapter 與元件接線

| 檔案 | 改動 |
| --- | --- |
| `src/contracts/{bot,run,risk,command,workspace,strategy}.ts` | 依第 2 節改型別：新增 `RegisteredStrategyDTO`、`BotViewDTO`、`RiskSnapshotDTO`、`PositionDTO`、`EventDTO`、`SummaryDTO`、`WorkspaceStateDTO`；刪 `SimulationRun`、`ExposureAllocationItem.color`、`Bot` 的 mock 專用欄位 |
| `src/adapters/types.ts` | 介面瘦身（Q9） |
| `src/adapters/simulation-api-adapter.ts`（新） | 沿用 `research-api-adapter.ts` 的 `handleResponse`／`ResearchApiError`／網路錯誤處理；補 `X-CatOS-Instance`、`request_id`、`PendingCommand` 存取；demo／live 回型別化不可用 |
| `src/state/catStore.ts`／`stateAdapter.ts` | slice 改為 `state`、`bots`、`risk`、`positions`、`summary`、`events`；`init()` 改拉 `/state`；新增輪詢器（1s／5s，tab 隱藏暫停），用 `domains` 版本逐 slice 套用 |
| `src/components/catos/account-equity-band.tsx` | KPI 改讀 `summary`；曲線改讀 `events` 的 `signal.account.equity`；移除 `v0-engine` 合成序列與 `selectedBotMeta` 寫死值 |
| `src/components/catos/v0-bot-table.tsx` | 列改讀 `bots`；移除 `INITIAL_BOTS`、`getFleetMeta` 寫死預算／7 日報酬；暫停／恢復按鈕改呼叫 `startBot`／`stopBot` 或在 v1 停用 |
| `src/components/catos/allocation-donut-card.tsx` | 改讀 `risk.derived`；`margin`／`pnl`／`delta` 視圖在 v1 標示不適用 |
| `src/components/catos/activity-panel.tsx` | 持倉改讀 `positions`；掛單固定空；強平／資金費率／P6 欄位改「不適用」 |
| `src/components/catos/unified-incident-activity-card.tsx` | 改讀 `events`；刪 `getEventDomain` 子字串推斷 |
| `src/pages/bots.tsx`、`src/state/inspectorStore.ts` | 陣列表改讀 `bots`；`INSPECTOR_BOTS` 寫死詳情改讀 `bot`＋`events`；部署對話框在 v1 停用（Q1） |
| `src/state/liveMarketStore.ts`、`src/lib/mock/market-tape-10m.ts`、`src/lib/v0-engine.ts`、`src/state/dashboard-demo-store.ts` | 元件改接後成為死碼，依「定案即固化」原則刪除；頂部行情帶（`top-market-ticker.tsx`）若仍需要報價，v1 沒有行情來源，顯示「無行情」或移除（另列決策） |
| `tests/state_adapter_test.mjs` | 改為對 `simulation-api-adapter` 的版本守門與 demo／live 不可用測試；加 fixture HTTP（沿用 `integration_baseline_test.mjs` 的隔離埠做法） |

驗證界線：第 3 步只跑隔離 TestClient 與既有 `test_local_sim_control.py`；第 4 步在隔離埠起後端 fixture 資料根，不碰正式 8770／`outputs/local-sim-control`。
