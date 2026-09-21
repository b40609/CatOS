# catOS × Yaozi Functional Parity — P1 Handoff

日期：2026-09-18

## 1. 目前狀態

P0 核心已具備，可直接進入 P1，不需要重做 P0-A～P0-E。

已完成的主要模組：

```text
catos/market_collectors.py     public OKX/Binance market adapters
catos/market_stream.py         bounded Binance aggTrade WS ingestion
catos/market_features.py       Decimal feature engine / complete-window CVD
catos/market_signals.py        known-threshold L2 + patterns
catos/market_lifecycle.py      SMF interface + Flow/Opportunity/Risk lifecycle
catos/market_proof.py          cycle + immutable push + 24h proof
catos/market_orchestrator.py   deterministic scan orchestration
catos/market_intel.py          market_intel.sqlite single-writer persistence
catos/market_api.py            localhost-only read API
```

`market_intel.sqlite` 目前 schema version = 3：

- WAL + `synchronous=FULL`。
- Supervisor 唯一 writer。
- 精確市場/金融數值使用 `Decimal`，SQLite 以 `TEXT` 保存。
- missing 保持 `NULL` / `None`，不得補 0。
- `signal_state` 每 scan 保存完整 14 個 L2 狀態；`signal_hit` 只保存 confirmed HIT。
- `push_snapshot` immutable，通知必須在 snapshot COMMIT 後才發生。
- 不修改金融交易 `Journal` schema 7，不宣稱跨 DB 原子一致。

最近 P0 專屬回歸：

```text
53/53 PASS
py_compile PASS
git diff --check PASS
catos/journal.py 無變更
```

## 2. P0 已確認語義，不要重做

- 約 60 秒 scan；caller 提供 timestamp，不讀 wall clock。
- Five Views：Flow / Momentum / Opportunity / Risk / History。
- SMF：`-100..+100`；底層真實 feature weights 未知，禁止猜。
- Flow 公開係數：35/15/15/10/10/10/10，合計 105，不 normalize。
- Flow：`>=70 ignition`、`50..69 accumulation`、`<35 x3 -> flow_faded`。
- Opportunity：`quality >=55` 入池、`<45 x3` 結束、`risk >=60` 阻擋新入池。
- Risk：`>=60 high_risk`、`>=45 watch`、`<30 x2 -> risk_resolved`。
- Momentum 沒有獨立 score；目前 API 只組合 materialized SMF + 14 L2 states。
- Funnel 私有 contract 未公開，維持 `not_materialized`，不可自創。
- `/intel/today` 是 `catos-p0-today-v1` latest-materialized aggregate，明示 `yaozi_contract=unverified`。
- REST latest-N trades 永遠 incomplete；只有不中斷完整 WS coverage 才可產生 CVD/taker complete window。
- P0 cycle 自動 start 私有 gate 未知，因此現行 cycle 使用 explicit deterministic directive，不推測。

## 3. P1 正式範圍與順序

依 `outputs/yaozi-functional-parity-spec-v0.1.md`：

```text
P1-A  Hyperliquid whales
P1-B  DEX flow
P1-C  Capital Flow events / cycle
P1-D  Dealer position + flow axes
P1-E  On-chain address expansion + Plateau
```

先做 P1-A；不要一次把整個 P1 展開成大型 framework。

## 4. P1-A：Hyperliquid whales

目標：建立可重播、public-only 的 Hyperliquid whale observation source，之後提供 Capital Flow / Dealer flow 使用。

資料契約至少包含：

```text
symbol
observed_at_ms
source_ms
wallet_or_trader
direction            LONG / SHORT 或 BUY / SELL，必須依來源語義明示
notional_text        Decimal TEXT
position_or_flow_type
source               hyperliquid
source_id / dedupe identity
provenance_json
```

實作邊界：

- 只用 Hyperliquid public API / public market data。
- 不接收 private key、API secret、wallet signing、user session。
- 網路只能由 Supervisor-owned collector 執行；Worker 維持純計算。
- raw JSON decimal string 直接解析成 `Decimal`；禁止 float 進核心資料。
- 缺資料 / stale / endpoint failure 保持 missing + issue code。
- 所有 observation 必須可 deterministic replay / dedupe。
- 不因為「大額」就自行制定 Yaozi `WHALE_ENTRY` threshold；該 L2 私有門檻仍 disabled/unknown。

建議先新增：

```text
catos/market_hyperliquid.py
tests/test_market_hyperliquid.py
```

先做 parser / normalized contract / mock transport / persistence；除非使用者另行明確授權，本切片不要執行真實外部採集。

## 5. P1-B：DEX flow

在 P1-A 穩定後再做。

規格要求 CEX taker 與 DEX swap 必須分開，不可混成單一未標來源的 flow：

```text
chain
venue / router
token / catOS symbol
wallet
side
base quantity
quote/notional
tx hash / log identity
block/time
source freshness
```

優先做 provider-neutral normalized event contract；不要先做通用多鏈 framework。

## 6. P1-C：Capital Flow

Capital Flow 是獨立 observation engine，**不進 SMF**。

已知事件類型至少包含：

```text
inflow
large inflow
sustained inflow
inflow acceleration
whale buy cluster
whale sell cluster
smart money accumulation
smart money distribution
CEX accumulation
CEX outflow
quiet accumulation
alpha confirm
FOMO
```

Yaozi 公開資料提到約 31 類事件，但未取得的事件/門檻不得自行補齊。

Capital Flow 必須保存：

```text
event_type
symbol
observed_at_ms
score NULL/Decimal TEXT
cycle_state
evidence_json
source_snapshot_ids_json
```

若 score 的完整公式未公開，先保存 observation/evidence，不生成偽造 score。

## 7. P1-D：Dealer Profile

Dealer `op_v1` 是三軸：

```text
position_axis
flow_axis
chip_axis
```

P1 先完成 position + flow；chip/holder/forensics 依賴較後資料，可保持 missing。

必須保存：

```text
coverage_mask
axis_count
```

缺 axis 是 NULL，不是 0。Dealer 最終 direction score 精確權重未知，禁止自行合成 parity score。

## 8. P1-E：On-chain Address Expansion + Plateau

目前已知公開 gate：

```text
FLAGGED:
  full_day_ratio >= 3x
  AND outgoing_distinct_addresses >= 5
  AND baseline_days >= 7

ELEVATED:
  any_ratio >= 2x
  AND not FLAGGED
```

其他已知語義：

- 每條 chain 的 baseline 分開，不跨鏈相加。
- rolling baseline = 前 14 個完整日 median。
- Plateau 第一次 FLAG 時鎖存 `baseline_anchor`。
- `anchored_ratio >=3x` 進入 Plateau；`>=1.5x` 留存。
- Plateau 不進 scoring、不進 flag gate、不推播。
- resonance board = COIL / address expansion / strong SMF；>=2/3 顯示，3/3 full resonance；只是 materialized view，不新增交易 score。

## 9. P1 仍未知，禁止猜測

1. `WHALE_ENTRY` 等私有絕對 threshold。
2. Capital Flow 約 31 類事件的完整清單與全部 scoring thresholds。
3. Dealer final direction score 精確公式。
4. 完整 forensics JSON schema（屬 P2）。
5. SMF 私有 weights。
6. Admin Reflection 動態 weighting policy。

未知欄位使用 `NULL` / `unknown` / feature flag；不要用 0 或近似值冒充。

## 10. API 現況

目前以下 P1 API endpoint 已存在，但故意回 `not_materialized`：

```text
GET /intel/capital-flow/{symbol}
GET /intel/dealer/{symbol}
GET /intel/onchain
GET /intel/onchain/{symbol}
```

P1 實作時，只有在對應資料已正式 materialize 後才把 endpoint 切成 real data。API 層不可重新計算核心 score / lifecycle。

## 11. 工作區與安全邊界

專案：`C:\Users\user\Desktop\CatOS_Astra`

目前 Market Intelligence 與其他 lot/scenario 工作仍有未 commit 修改。禁止：

- `git clean`
- `git reset --hard`
- revert / overwrite 其他工作流檔案
- 為了 P1 重寫 P0 schema/history
- 修改金融 `Journal` schema 7
- 讀真實交易憑證
- 發 Demo/Live 訂單

只做最小 diff。

## 12. 新對話第一個指令

```text
請讀取 `outputs/yaozi-p1-handoff-2026-09-18.md`、`outputs/yaozi-functional-parity-spec-v0.1.md`、`docs/market-intel.md` 與 `AGENTS.md`。

延續 catOS × Yaozi Functional Parity，不要重做 P0。直接執行 P1-A：Hyperliquid whales。先建立 public-only、Supervisor-owned 的資料 adapter / parser / normalized observation contract / mock tests / market_intel persistence；Decimal 精確值不得經 float，missing 不得補 0，未知 Yaozi whale threshold 不得猜。不要讀任何 private key/API secret，不接實盤，不修改金融 Journal schema 7，不碰工作區其他任務的修改。完成 P1-A 專屬測試後停止並回報，再進 P1-B DEX flow。
```
