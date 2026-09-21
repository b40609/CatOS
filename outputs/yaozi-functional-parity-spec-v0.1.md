# catOS：Yaozi Functional Parity Spec v0.1

狀態：2026-09-18 研究／設計規格。目標是先重建妖子的資料與功能語義，再依實際使用體驗簡化；不複製 UI，不假造未公開公式。本文件不修改交易 Journal schema、不接實盤、不讀憑證、不實作交易。P0-A 已開始落地：`catos.market_collectors` 與獨立 `market_intel.sqlite` schema 1 已實作，範圍與驗證見 `docs/market-intel.md`；其餘 feature/signal/lifecycle/proof 尚未因此視為完成。

## 1. 目標與架構定位

妖子不是單一「方向預測器」，而是一條市場情報生命週期：

```text
Market Data
  -> Feature Engine
  -> Signal Engine
  -> Lifecycle Engine
  -> Evidence Layer
  -> Reflection / Proof
```

catOS parity 版本應保持相同職責分離：

```text
Supervisor（唯一網路、唯一 SQLite writer）
  ├─ Market Collectors
  ├─ Feature Engine
  ├─ Signal Engine
  ├─ Lifecycle Engine
  ├─ Evidence Engine
  └─ market_intel.sqlite

Worker
  └─ 只接收已標準化唯讀快照，做策略純計算；不直接抓市場情報來源
```

金融交易 Journal 維持現有 schema 7。市場情報另存 `market_intel.sqlite`；兩者不宣稱跨檔原子一致。只有交易、風控、帳務資料屬金融 Journal。

## 2. Functional Parity Matrix

| Page / Engine | 功能 | Raw / Derived fields | 已確認規則 | Cadence | 妖子 endpoint / surface | catOS 來源 | Scoring | 優先級 | 信心 |
|---|---|---|---|---|---|---|---|---|---|
| Universe / Radar | 全市場掃描 | price、volume、OI、funding、候選狀態 | Binance 永續全市場；約 60s；L1 <=200、L2 <=50 | ~60s | `/radar/scores` | OKX USDT-SWAP 主場；Binance 補充 | 是 | P0 | 高 |
| Radar | 資費背離 | funding history、OI | funding 正轉負＋OI 上升為已知訊號之一 | ~60s | `/radar/funding-divergence` | OKX＋Binance | 是 | P1 | 高 |
| Radar | 新上市 | listing time、venue | 新上市觀測 | 分鐘級 | `/radar/new-listings` | OKX/Binance announcement＋instrument list | 否/觀測 | P2 | 中 |
| L2 Lights | 14 種訊號燈 | hit type、evidence、threshold status | 見第 4 節 | ~60s | picks/radar | 自算 | 是 | P0 | 中高 |
| Flow | 點火前候選 | OI speed、taker、LSR slope、OI quadrant、compression、cycle、tilt | 35/15/15/10/10/10/10；>=70 ignition；50-69 accumulation；<35 三次退出 | ~60s | picks views | 自算 | 是 | P0 | 高 |
| Momentum | 已異動追蹤 | SMF、14 lights、funnel | 非獨立 score | ~60s | picks views | 自算 | 是 | P0 | 高 |
| Opportunity | 品質候選 | structure、behavior、SMF、risk | quality >=55 入池；<45 三次結束；risk >=60 阻擋 | ~60s | picks views | 自算 | 是 | P0 | 高 |
| Risk | 風險候選 | bearish evidence | >=60 高風險；>=45 watch；<30 兩次 risk_resolved | ~60s | picks views | 自算 | 是 | P0 | 高 |
| Lifecycle | cycle 狀態機 | cycle_id、first/latest push、entry/exit、MFE/MAE | 必須保存重入池、結束原因、視角進出 | ~60s | `/picks/{symbol}/journey` `/timeline` | 自算 | 是 | P0 | 高 |
| Single Coin | 單幣研究頁 | Kline、OI、CVD、taker、direction、news、depth | 15m/30m/1h/4h/1d；方向 -100..+100 | 秒～分鐘 | `/picks/{symbol}` `/series` | OKX/Binance/News | 混合 | P0 | 高 |
| Money Flow | CEX/DEX 資金流 | CEX taker net、DEX swap、cost estimate | 鏈上 DEX 與 CEX taker 分開 | 秒～分鐘 | `/picks/{symbol}/money-flow` | OKX/Binance trades＋DEX indexer | 否 | P1 | 高 |
| Capital Flow | 資金週期事件 | event_type、score、cycle_state、MFE/MAE | 約 31 類事件；display/observation-only | 分鐘級 | `/capital-flow/*` | CEX＋DEX＋Hyperliquid | 否 | P1 | 高 |
| Dealer Profile | 三軸莊家檔案 | position、flow、chip coverage | 持倉面 / 資金流 / 籌碼面；missing != 0 | 分鐘～小時 | `/operator/{symbol}` | Binance＋DEX＋forensics | 否 | P1 | 高 |
| On-chain | 地址轉出放量 | outgoing addresses、baseline、ratio、chain | FLAG 三閘；Plateau 錨定基線 | 小時級 | `/operator/onchain` | RPC/indexer | 否 | P1 | 高 |
| Forensics | 鏈上鑑識 | cashout、wallet coverage、sentinel、net buy、CEX flow | 歷史研究快照，不作 live scoring | 小時～日 | `/onchain/forensics/{symbol}/full` | 自建＋第三方鑑識 | 否 | P2 | 中 |
| Liquidity | ±2% 現貨深度 | bid/ask depth by venue、asymmetry | 多交易所；比值只描述厚度 | 分鐘級 | single coin panel | Binance/Gate/OKX/Coinbase/Bitget/Bybit 等 | 否 | P2 | 高 |
| Narrative | 敘事地圖 | movement、flow、derivative、social、onchain | p80 breakthrough、p60 watch；peer percentile | 小時級 | `/narrative/*` | 自建＋外部熱度 | 否 | P2 | 中高 |
| Sector | 板塊輪動 | member returns、turnover share | 板塊報酬取成員中位數；資金佔比是 turnover share | 小時級 | `/narrative/sectors` | 自建 taxonomy＋CoinGecko | 否 | P2 | 高 |
| News | 多來源快訊 | source、category、symbols、sector、importance | ingest -> normalize -> dedupe -> classify -> tag | 分鐘級 | narrative/news | RSS/API/X/公告 | 否 | P2 | 高 |
| Options / Gamma | 選擇權情報 | spot、zero-gamma、net gamma、IV、RV、RR、PCR、DVOL | Deribit public OI proxy；missing 不轉 0 | ~1m / 8h report | Gamma/Options views | Deribit＋OKX options | 否 | P2 | 高 |
| Proof | 推送後驗證 | frozen snapshot、future return、MFE、MAE、baseline | 24h 評估；全市場同時點 baseline＋vol-matched baseline | 事件＋批次 | `/proof` `/reflection/*` | 自建 | 驗證層 | P0 | 高 |

## 3. 資料來源矩陣

### 3.1 P0/P1 必要來源

| Data | Primary | Secondary / parity source | 取得方式 | catOS 正規化欄位 |
|---|---|---|---|---|
| Universe | OKX | Binance Futures | instruments REST | venue、inst_id、base、quote、contract_type、status |
| Price / Kline | OKX | Binance | REST/WS | ts、O/H/L/C、volume、closed |
| Trades | OKX | Binance | WS | ts、price、qty、side/aggressor、notional |
| CVD | 自算 | Binance parity | trades aggregate | interval、buy_volume、sell_volume、cvd |
| Taker ratio | 自算 | Binance `/futures/data` 類指標 | trades / public metrics | buy_ratio、sell_ratio、zscore |
| OI | OKX | Binance＋Bybit | REST/WS | oi_contracts、oi_notional、delta_5m/1h/4h/24h |
| Funding | OKX | Binance | REST | current、previous、next、flip_state |
| Top Trader L/S | Binance | - | public futures metrics | account_lsr、position_lsr、slope |
| OI concentration | Binance＋OKX＋Bybit | - | venue snapshots | venue_oi_share、dominant_venue |
| Liquidation | OKX | Binance＋Bybit | WS | side、notional、cluster window |
| Hyperliquid whales | Hyperliquid | - | public API | wallet/trader、direction、notional |
| DEX flow | chain indexer | RPC fallback | swap events | buy/sell notional、wallet、venue、chain |
| On-chain address activity | chain indexer | provider API | token transfer graph | distinct_outgoing、baseline、ratio |
| Holder / cost | 自建 reconstruction | provider snapshot | transfer＋swap history | holder_share、estimated_cost、confidence |
| Market cap / categories | CoinGecko | internal | API/cache | mcap、category、rank |
| News | multi-source | - | RSS/API/web ingestion | canonical id、source、title、time、entities |
| Options chain | Deribit | OKX | public API | expiry、strike、type、OI、IV、delta、gamma |

### 3.2 開源元件使用範圍

| Project | 用途 | 是否作 production source |
|---|---|---|
| `Co-Messi/HyperData-Terminal` | 多交易所 adapter、OI/funding/CVD/orderbook/liquidation/Deribit/HL 參考 | 參考／可抽 adapter；需自行審核 |
| `duolaAmengweb3/crypto-monitor` | 多交易所監控、新上市、大單、HL whale pattern | 參考／可抽模組 |
| `Crypto-Liquidation-Feed` | liquidation clustering / anomaly / replay | 可抽演算法 |
| TradingView `lightweight-charts` | K 線與 overlays | 是，UI library |
| `open-coinglass` | schema / flow 設計 | 否；DOM scraping 不作正式資料源 |

## 4. Signal Engine

### 4.1 14 個 L2 lights

1. 命中：多 scanner 共振，hit/composite 達 gate。
2. 埋伏：價格盤整＋OI 上升＋L/S 不平衡；絕對 threshold 未公開。
3. 吸籌：低位價格＋OI 緩升＋大額流入；絕對 threshold 未公開。
4. 熱度：OKX Square＋CoinGecko trend＋內部異常池。
5. 動能：abs 24h change >=10%。
6. 強動能：abs 24h change >=25%。
7. 資費轉負：funding 正轉負＋OI 上升。
8. OI 暴衝：短期 OI delta 達內部強門檻；絕對 threshold 未公開。
9. 極端做多：深負 funding 回升 / V-reversal / squeeze 類 capital event。
10. 鯨魚進場：DEX 1h net buy＋平均交易額門檻；絕對 threshold 未公開。
11. 鯨魚撤離：DEX 1h net sell threshold。
12. 團隊出貨：non-exchange -> exchange，單筆 >= US$500k；同幣 24h 一次。
13. 蓄力突破：range compression＋volume decline，等待 breakout。
14. 純動能：24h gain >=10%＋mcap < US$300M＋daily volume >= US$5M；可不靠共振入池。

未公開門檻必須配置為 `unknown`，禁止為了 parity 自行猜數字。

### 4.2 Pattern flags

```text
SHORT_SQUEEZE_CANDIDATE
  24h gain >= 5%
  AND 4h OI >= 10%
  AND 1h OI >= 3%
  AND no whale exit
  AND (trend OR funding-negative-flip OR extreme-long event)

COIL_BREAKOUT
  15m volatility < p50
  AND 5m OI >= 1.5%
  AND 1h OI >= 2.5%
  AND 1h price in [-1%, +2%]
  AND (trend OR funding-negative-flip)

PREHEAT
  1h OI >= 2%
  AND 5m OI >= 1%
  AND 1h price in [+1.5%, +6%]
  AND 24h price in [-5%, +10%]
  AND no whale exit
  AND 5m OI acceleration > 1h average speed

AMBUSH
  15m volatility < p35
  AND 1h OI >= 2%
  AND abs(1h price move) < 1.5%
  AND 24h price in [-3%, +3%]

FOMO
  (24h gain >=15% AND volume >= US$1M)
  OR capital_flow_event == FOMO
```

### 4.3 SMF

SMF 範圍 `-100..+100`：

```text
S >= +50       高 beta bullish
A +20..+49     bullish
B -20..+19     neutral
C -49..-20     weak bearish
D <= -50       strong outflow / bearish
```

`S` 不是單純「比 A 更好」，而是較高 beta。底層 feature weights 尚未取得，v0.1 僅定義 interface：

```text
SmfSnapshot
  symbol
  observed_at
  score
  grade
  component_json
  model_version
  confidence
```

神級 promotion 已確認：resonance >=3、quality >=80、24h hits >=4、post-push max gain >=5%。

## 5. Lifecycle Engine

### 5.1 Five Views

Flow：

```text
flow_score =
  oi_speed * 35
  + taker * 15
  + top_trader_lsr_slope * 15
  + oi_quadrant * 10
  + compression_accumulation * 10
  + capital_flow_cycle * 10
  + momentum_tilt * 10
```

網站公開係數合計 105；v0.1 不自行 normalize。

```text
>=70          ignition
50..69        accumulation
<35 x3 scans  flow_faded
```

Opportunity：`quality >=55` 入池；`quality <45 x3` 結束；`risk >=60` 阻擋。

Risk：`bearish >=60` 高風險＋push；`>=45` watch；`<30 x2` risk_resolved。

Momentum：SMF＋14 L2 lights＋Funnel 的狀態，不另建獨立 score。

### 5.2 Exit reason dictionary

Leading：

```text
cvd_divergence
oi_silent_decline
funding_rate_flipped
lsr_long_reduction
oi_price_bearish_div
smf_short
risk_resolved
```

Reactive：

```text
behavior_派發
behavior_減倉
structure_broken
structure_dump_topping
sustained_dump
tag_transition
mfe_drawdown
day_high_drawdown
entry_drawdown
peak_drawdown
stale_dropped
momentum_faded
flow_faded
flow_data_gone
funnel_collapsed
superseded_by_risk
quality_dropped
```

價格防線：`adaptive floor = clamp(8 * ATR%, 8%, 22%)`；另有約 -20% peak hard floor；stale timeout 720h。健康回調 exemption 只有在 primary inflow＋bullish SMF＋rising OI 等條件保持時才可能成立。

## 6. Evidence Layer

### 6.1 Capital Flow

獨立 observation engine，不進 SMF。事件至少分：

- inflow / large inflow / sustained inflow / inflow acceleration
- whale buy cluster / whale sell cluster
- smart money accumulation / distribution
- CEX accumulation / outflow
- quiet accumulation / alpha confirm / FOMO
- holder reduction / large outflow
- take-profit trigger / trailing TP warning / inflow weakening / exit confirm
- tracking start/end / cycle reset
- low data confidence / single venue dominance / OI breakout / negative funding setup / cross-exchange divergence / OI silent decline

### 6.2 Dealer Profile `op_v1`

三軸：

```text
position_axis
  top_trader_lsr
  top_trader_long_pct
  retail_lsr
  taker_buy_pct
  funding_rate

flow_axis
  dex_net_flow_1h
  large_buy_sell_1h
  independent_buyers_1h
  capital_flow_cycle

chip_axis
  holder_structure
  estimated_cost
  distribution_flags
  forensic_snapshot
```

必須保存 `coverage_mask` / `axis_count`。缺資料是 NULL，不是 0。最終 Dealer direction 的精確權重仍未知。

### 6.3 On-chain Address Expansion

```text
FLAGGED:
  full_day_ratio >= 3x
  AND outgoing_distinct_addresses >= 5
  AND baseline_days >= 7

ELEVATED:
  any_ratio >= 2x
  AND not FLAGGED
```

各 chain baseline 獨立，不跨鏈相加。

Rolling baseline = 前 14 個完整日 median。

Plateau：第一次 FLAG 時鎖存 `baseline_anchor`；`anchored_ratio >=3x` 進入；`>=1.5x` 留存。Plateau 不進 scoring、不進 flag gate、不推播。

### 6.4 On-chain resonance board

三腳：`COIL`、`address expansion`、`strong SMF`。>=2/3 顯示；3/3 完整共振。這只是 materialized view，不建立新的交易分數。

## 7. SQLite 資料模型

### 7.1 DB 邊界

新增獨立市場情報資料庫：

```text
market_intel.sqlite
  journal_mode=WAL
  單一 Supervisor writer
  UI / research 只讀
```

不修改現有交易 `Journal` schema 7。`market_intel.sqlite` 可以丟棄後重建的 market cache 與不可丟棄的 proof snapshot 混在同檔，但 retention policy 要區分；若未來資料量實測成為瓶頸，再拆 historical cache，不先增加第三套服務。

### 7.2 核心 tables

```text
instrument
  symbol PK
  primary_inst_id
  venues_json
  sector_json
  active
  first_seen_ms
  updated_at_ms

market_snapshot
  snapshot_id PK
  symbol
  observed_at_ms
  price_text
  volume_24h_text
  change_1h_text
  change_24h_text
  market_cap_text NULL
  source_health_json

derivative_snapshot
  symbol
  observed_at_ms
  oi_text
  oi_delta_5m_text
  oi_delta_1h_text
  oi_delta_4h_text
  funding_text
  top_lsr_text NULL
  taker_buy_ratio_text NULL
  concentration_json NULL

flow_snapshot
  symbol
  observed_at_ms
  cvd_text NULL
  cex_taker_net_text NULL
  dex_net_1h_text NULL
  dex_buyers_1h INTEGER NULL
  hl_long_notional_text NULL
  hl_short_notional_text NULL

feature_snapshot
  symbol
  observed_at_ms
  feature_version
  payload_json

signal_hit
  hit_id PK
  symbol
  observed_at_ms
  signal_type
  signal_version
  evidence_json
  threshold_json
  source_snapshot_ids_json

pattern_hit
  hit_id PK
  symbol
  observed_at_ms
  pattern_type
  active
  evidence_json

smf_snapshot
  symbol
  observed_at_ms
  score_text
  grade
  model_version
  component_json NULL
  confidence_text NULL

view_state
  symbol
  view_name
  observed_at_ms
  state
  score_text NULL
  consecutive_count
  evidence_json

cycle
  cycle_id PK
  symbol
  started_at_ms
  ended_at_ms NULL
  first_push_price_text
  latest_push_at_ms
  push_count
  peak_price_text NULL
  trough_price_text NULL
  mfe_text NULL
  mae_text NULL
  end_reason NULL

cycle_event
  event_id PK
  cycle_id
  symbol
  observed_at_ms
  event_type
  view_name NULL
  payload_json

capital_flow_event
  event_id PK
  symbol
  observed_at_ms
  event_type
  cycle_state NULL
  inflow_score_text NULL
  exit_score_text NULL
  payload_json

dealer_snapshot
  symbol
  observed_at_ms
  phase NULL
  direction_score_text NULL
  direction_label NULL
  coverage_mask
  position_json NULL
  flow_json NULL
  chip_json NULL

onchain_activity
  symbol
  chain
  observed_at_ms
  outgoing_distinct INTEGER
  baseline_days INTEGER
  baseline_live_text NULL
  baseline_anchor_text NULL
  live_ratio_text NULL
  anchored_ratio_text NULL
  state
  first_flag_at_ms NULL
  plateau_started_at_ms NULL
  consecutive_days INTEGER

forensic_snapshot
  symbol
  chain
  observed_at_ms
  source
  chain_state NULL
  realized_cashout_pct_text NULL
  monitored_wallets INTEGER NULL
  total_wallets INTEGER NULL
  sentinel_7d INTEGER NULL
  net_buy_24h_text NULL
  cex_net_8h_text NULL
  payload_json

liquidity_snapshot
  symbol
  observed_at_ms
  venue
  pair
  up_2pct_cost_text
  down_2pct_cost_text

news_event
  news_id PK
  published_at_ms
  source
  source_url NULL
  category
  title
  content_hash
  symbols_json
  sectors_json
  importance_text NULL

options_snapshot
  underlying
  observed_at_ms
  spot_text
  zero_gamma_text NULL
  net_gamma_text NULL
  atm_iv_1w_text NULL
  rv_7d_text NULL
  rr_25d_text NULL
  put_call_oi_text NULL
  dvol_text NULL
  payload_json

push_snapshot
  push_id PK
  symbol
  pushed_at_ms
  push_type
  cycle_id NULL
  frozen_payload_json
  feature_version
  signal_version

forward_return
  push_id
  horizon
  measured_at_ms
  return_text
  mfe_text
  mae_text
  market_baseline_text NULL
  vol_matched_baseline_text NULL

reflection_result
  push_id
  evaluated_at_ms
  cohort
  metric_json
```

所有價格、金額、比例、分數等需精確保存的數值使用 Decimal string / SQLite TEXT，不使用 REAL。純排序 percentile/統計若日後允許 Float，必須留在衍生分析層，不回流金融帳務。

## 8. 60 秒 Scan DAG

### 8.1 主流程

```text
T+00  Universe refresh / health check
        |
        +-> OKX ticker / Kline / OI / funding
        +-> Binance derivatives / top trader LSR
        +-> Bybit OI concentration (optional cadence cache)
        +-> Hyperliquid whale cache
        +-> DEX/on-chain cache
        |
T+10  Normalize + validate freshness
        |
T+15  Feature Engine
        |- returns / volatility / BBWP
        |- OI speed / quadrant / concentration
        |- CVD / taker / funding transitions
        |- structure / compression
        |- DEX / whale / capital-flow features
        |
T+25  Signal Engine
        |- 14 L2 lights
        |- Pattern flags
        |- SMF snapshot
        |
T+35  Lifecycle Engine
        |- Flow
        |- Momentum
        |- Opportunity
        |- Risk
        |- cycle enter / transition / exit
        |
T+45  Evidence materialization
        |- Dealer summary
        |- Capital Flow panel
        |- resonance board
        |- single-coin snapshot
        |
T+50  Push gate
        |- freeze immutable push_snapshot BEFORE notification
        |- dedupe / cooldown
        |- notification is downstream side effect
        |
T+55  Commit market_intel.sqlite
        |
T+60  next scan
```

### 8.2 非 60 秒來源

不要強迫所有來源每分鐘重抓：

```text
1-5s     ticker / orderbook UI cache
10-60s   trades / CVD / OI / funding / core scan
5-15m    sector / narrative / social heat
15-60m   on-chain address aggregation
1-8h     holder reconstruction / forensic refresh
~1m      options realtime snapshot
8h       options evidence report
```

主 scan 使用「最近一筆已驗證且未過 freshness TTL」的慢速資料；超時就是 missing/stale，不填 0。

## 9. Push / Proof 正確性

任何通知、入池或視角推送，順序固定：

```text
compute candidate
  -> freeze push_snapshot
  -> COMMIT
  -> notification / UI event
  -> future evaluation jobs
```

不能先推播再補 snapshot，否則失敗案例或服務中斷會產生 survivor bias。

每個 push 至少保存：

```text
symbol
timestamp
push_type
price
cycle_id
all active L2 lights
patterns
SMF
five-view states/scores
feature version
source freshness
market regime snapshot
pre-entry volatility
```

24h 後評估：future return、MFE、MAE、same-hour market baseline、volatility-matched baseline。失敗推送不可刪除。

## 10. API surface for catOS UI

先做 read-only localhost API：

```text
GET /intel/today
GET /intel/radar
GET /intel/picks?view=flow|momentum|opportunity|risk|history
GET /intel/picks/{symbol}
GET /intel/picks/{symbol}/timeline
GET /intel/picks/{symbol}/journey
GET /intel/signals
GET /intel/capital-flow/{symbol}
GET /intel/dealer/{symbol}
GET /intel/onchain
GET /intel/onchain/{symbol}
GET /intel/narrative
GET /intel/sectors
GET /intel/news
GET /intel/options/{underlying}
GET /intel/proof
```

API 只輸出已物化資料；前端不要自行重算核心 score，避免同一訊號在 UI 與後端出現兩套語義。

## 11. 實作切片

### P0：最小可用 parity

1. OKX/Binance Market Data adapters。`P0-A 已完成 public REST 基礎；完整 trade stream 待 WS。`
2. `market_intel.sqlite` schema。`P0-A/P0-B 已到 schema 2。`
3. Feature snapshot：price/OI/funding/taker/CVD/volatility/structure。`P0-B 已完成 closed-bar、OI delta 與完整 trade-window 純計算；production CVD ingestion 待 WS。`
4. 已知可完整定義的 L2 lights＋patterns。`P0-C 已完成：5 個完整門檻 L2 可執行，9 個私有門檻固定 disabled/unknown；5 個公開 Pattern 採 HIT/MISS/MISSING_DATA 三值規則。`
5. Flow / Opportunity / Risk / Lifecycle state machine。
6. Single coin read API。
7. immutable `push_snapshot`＋24h proof evaluation。

實作進度（2026-09-18）：P0-A / P0-B / P0-C 已落地並使用固定 fixture 驗證。尚未完成 SMF、Five Views lifecycle、60 秒 scan orchestrator、push/proof，因此不得宣稱 P0 parity completed。

P0 暫不需要 DEX、完整鏈上、新聞、Options 才能開始實際使用；未知 signal threshold 以 disabled/unknown 處理，不用自造數字。

### P1：資金與主力證據

1. Hyperliquid whales。
2. DEX flow。
3. Capital Flow events/cycle。
4. Dealer position＋flow axes。
5. On-chain address expansion＋Plateau。

### P2：研究增強層

1. Holder/cost reconstruction。
2. Forensics。
3. Multi-venue ±2% liquidity。
4. Narrative / sector / social。
5. News aggregation。
6. Deribit options / Gamma。

## 12. 未知項目清單

以下不得標為 parity completed：

1. SMF `-100..+100` 底層 feature weights。
2. 埋伏 / 吸籌 / OI 暴衝 / 鯨魚進場的部分絕對 threshold。
3. Narrative 外部 heat leaderboard vendor 身份。
4. Dealer 最終 direction score 精確合成公式。
5. `/onchain/forensics/{symbol}/full` 完整 JSON schema。
6. Admin `/reflection` 權重調整 UI / backend policy。

未知值一律在 schema 中保留 `NULL`、`unknown` 或 feature flag；不得把缺失資料轉成 0，也不得以主觀近似門檻冒充妖子原規則。

## 13. Definition of Done for parity research

研究規格完成不等於產品 parity。要宣稱某模組 parity completed，至少必須同時滿足：

1. 原始資料來源已確定。
2. derived fields 的公式／門檻已確認或明確標示自有替代版本。
3. cadence / freshness / missing semantics 已定義。
4. lifecycle transition 可重播且 deterministic。
5. push snapshot 在事件發出前已持久化。
6. UI 只讀同一後端 materialized state。
7. 至少有固定 fixtures 驗證 entry / transition / exit / stale / missing-data。

本規格下一步可直接轉成 `market_intel` 模組骨架與 schema migration 0->1；在使用者明確要求實作前，本輪只停在設計與資料契約。
