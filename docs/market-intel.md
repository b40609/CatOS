# catOS：Market Intelligence P0 / P1

狀態：2026-09-19 依現存程式重建：P0 核心、P1 公開觀測／候選證據及本機讀取介面已有實作；私有公式仍為 unknown，不宣稱完整 Yaozi parity。最新續作與待驗收項目見 [Yaozi 恢復交接](../outputs/yaozi-recovery-handoff-2026-09-19.md)。下列既有驗證敘述為歷史紀錄，不代表本輪重跑。

## 已實作

- `catos.market_collectors`
  - 固定 GET allowlist，僅 `www.okx.com` 與 `fapi.binance.com`。
  - 不接收 API key、不讀環境憑證、不在 import 時連網。
  - OKX：USDT-SWAP universe、ticker、OI、funding。
  - Binance：USDT perpetual universe、24h ticker、OI、funding、Top Trader position L/S、taker buy/sell ratio。
  - 同一 CatOS symbol 正規化，例如 `BTC-USDT-SWAP` 對應 Binance `BTCUSDT`。
  - API decimal 字串直接進 `Decimal`，禁止 JSON float 偷渡到計算層。
  - 補充來源失敗時保留 `None` 與 issue code，不以 `0` 代替 missing。

- `catos.market_intel`
  - 獨立 `market_intel.sqlite`，目前程式的 schema version 為 13；v10 新增 Alpha+/Alpha cross-axis 與 explicit status-label materialization，v11 新增 OKX public option summary / open-interest tables，v12 新增 `onchain_source_run` provider/source evidence table，v13 新增 `liquidity_source_run` / `liquidity_snapshot`。v12→v13 原地 migration 已有專屬測試；本 Session 嘗試遷移主 `outputs/catos-market-intel.sqlite` 時被 runtime safety review 攔截，因此主 DB 仍以已確認的 v12 狀態看待，不宣稱已升級。
  - WAL + `synchronous=FULL`。
  - 不修改金融交易 `Journal` schema 7，也不宣稱兩個 DB 跨檔原子一致。
  - 保存 venue-level normalized snapshot，再物化目前 P0 的 consolidated market / derivative snapshot。
  - 價格、成交量、OI、funding、ratio 均以 SQLite `TEXT` 保存 Decimal。
  - `market_candle` 只保存 `closed=1` 的已收盤 OHLCV。Read model 固定公開 YAOZI 已確認的五週期 `15m / 30m / 1h / 4h / 1d`；缺少某週期時回 `missing/no_closed_candles_materialized`，不在 API 端 resample 或補值。
  - 同一 `symbol + observed_at_ms` 的完全相同資料可重播；不同內容拒絕為 `snapshot_conflict`，避免覆寫歷史快照。
  - `signal_state` 每 scan 保存全部 14 個 L2 評估狀態；`signal_hit` 仍只保存 confirmed HIT，避免把 MISS、missing、disabled 混成同一語義。
  - 已預建 P0 後續需要的 feature、signal、pattern、SMF、view、cycle、push、proof tables。

- `catos.market_features`
  - 純 Decimal、無 I/O Feature Engine。
  - Closed Candle：1h / 24h return、ATR%、20-bar realized volatility、Bollinger Band Width、BBWP、rolling range position、breakout state。
  - OI：由 `market_intel` 已保存的同 venue snapshot 推導 5m / 1h / 4h percentage delta；目標時間前最近樣本超過 120 秒即視為 missing，且禁止跨 venue 串接 delta。
  - Trade Flow：完整視窗才計算 quote-notional CVD 與 taker buy ratio；REST `latest N trades` 一律標為 incomplete，不得冒充 CVD。
  - feature / flow snapshot 皆 immutable；重播相同資料可接受，同 key 不同內容拒絕。

- `catos.market_signals`
  - 純 Decimal、無 I/O、deterministic 規則引擎。
  - 14 個 L2 lights 中，目前只執行已取得完整公開門檻的 5 個：`MOMENTUM`、`STRONG_MOMENTUM`、`FUNDING_NEGATIVE_FLIP`、`TEAM_DISTRIBUTION`、`PURE_MOMENTUM`。
  - `HIT / AMBUSH / ACCUMULATION / HEAT / OI_SURGE / EXTREME_LONG / WHALE_ENTRY / WHALE_EXIT / COIL_BREAKOUT_LIGHT` 因妖子私有 gate 或絕對 threshold 未公開，固定為 `DISABLED_UNKNOWN_THRESHOLD`，不自行補數字。
  - 7 個 Pattern：`SHORT_SQUEEZE_CANDIDATE / COIL_BREAKOUT / PREHEAT / AMBUSH / FOMO / TREND_REVERSAL / DISTRIBUTION`。Trend reversal 只執行公開的 `trend strength >= 25` 與組合條件；「1h 高波動區、方向力成立、前置多頭加持」因完整算法未公開，必須由 caller 以已確認布林事實傳入，不在本模組猜數值門檻。Distribution 只接受 whale-exit 或 caller 已確認的派發／減倉／出貨同義 behavior。
  - Alpha+ / Alpha 已拆成獨立 cross-axis eligibility：Alpha+ = pattern strength >=75、resonance >=3、bullish、SMF 非 C/D；Alpha = >=60、resonance >=2、bullish、SMF 非 D。Guide 的歷史 `Alpha+=SMF S / Alpha=SMF A` 資金軸別名不會拿來冒充 cross-axis selection。
  - Alpha+ / Alpha 已物化到 `cross_axis_evaluation`；`OBSERVE / DUMP_WARNING / NEW_CANDIDATE` 已物化到 `status_label_snapshot`。兩者皆 versioned、exact replay idempotent，同 identity 不同內容拒絕 `snapshot_conflict`。2026-09-21 current Guide 已公開三個 status-label derivation rule；`market_signals.evaluate_status_labels()` 現已能由本地 facts 做 deterministic derivation，同時保留 caller/source-explicit state override。缺必要 facts 時維持 `MISSING_DATA`，不把缺資料當 false。
  - Momentum exit 已新增 Guide-published deterministic subset：`adaptive floor = clamp(8×ATR%, 8%, 22%)`、720h stale、peak -20% hard exit、leading-signal exit，以及 healthy-pullback 對一般 adaptive price floor 的豁免。market risk-off 雖公開為「收緊退場」，但 exact adjustment 未公開；因此只有不依賴該未知調整值的情況才下 `EXIT/HOLD`，其餘維持 `MISSING_DATA`，不猜 tightening 公式。
  - Pattern 採 `HIT / MISS / MISSING_DATA` 三值判定；缺資料不會被當成 false 或 0。
  - `signal_hit` 只保存確定 HIT；`pattern_hit` 保存 7 個 Pattern 的判定狀態，`active=1` 只代表 HIT，完整狀態留在 evidence JSON。
  - Signal DEX 讀模型使用已持久化 `dex_swap_observation` 做近 1h 精確 Decimal 加總。GeckoTerminal public adapter 僅允許固定 host、明示 pool 與無憑證 GET；provider 最新交易最舊一筆若已跨過 1h 起點，該 run 標示 `coverage_status=verified_pool_window`。若已碰到 300 筆上限但仍未跨過起點則標示 `provider_limit_truncated`；其餘無法證明 coverage 的回應維持 `unverified_window_coverage`。同一掃描時間若存在多個已驗證 pool，只有在 chain 相同且 `base_token_address` 完全一致時才合併為 `verified_multi_pool_window`；identity 缺失、跨鏈或 token address 不一致時淨流保持 missing。multi-pool 仍只代表已配置 pools，不代表該幣全市場 DEX。
  - 2026-09-21 已完成真實 GeckoTerminal upstream verification：`ETH-USDT-SWAP` 使用 Ethereum WETH/USDC 的 Uniswap V3 `0x88e6...5640` 與 Uniswap V2 `0xb4e16...c9dc`，同一 bounded collection anchor 取得 2 runs / 600 observations / 0 issues；主 DB 的 Signal DEX read model 輸出 `verified_multi_pool_window`，兩個 pool 的 `base_token_address` 均為 WETH `0xc02a...6cc2`。設定見 `outputs/yaozi-dex-pools-20260921.json`，實測摘要見 `outputs/yaozi-dex-live-verification-20260921.json`。此證據只證明這兩個明示 pools 的 coverage，不外推成 ETH 全市場或 YAOZI 私有 DEX universe。
  - Signal DEX 與 Dealer/op_v1 FLOW 是分離 contract；public DEX observation 不會自動提高 Dealer coverage，也不觸發未知 whale threshold。
  - Capital Flow 可由 `verified_pool_window` 且 quote 資料完整的 DEX window 物化 catOS-native `inflow` / `outflow` 事件；`score`、`cycle_state`、whale threshold 與 Dealer FLOW 均保持 missing/unknown，不借用 Yaozi 私有公式。
  - 已新增 `yaozi_observed_event_fact_v1` 黑箱觀測契約，只保存畫面已證實的事件名稱與結構化 payload，不反推事件 gate。現階段已登錄：`WHALE_BUY_CLUSTER`、`WHALE_SELL_CLUSTER`、`SMART_WALLET_ACCUMULATION`、`SMART_WALLET_DISTRIBUTION`、`MAJOR_OUTFLOW`、`FIRST_INFLOW`、`CONTINUED_INFLOW`、`INFLOW_ACCELERATION`、`FLOW_FLIP_TO_OUTFLOW`、`CEX_ACCUMULATION`、`OI_BREAKOUT`、`CONTRACT_IGNITION`、`SINGLE_VENUE_DOMINANCE`、`TOP_TRADER_LONG_BUILD`、`TOP_VS_RETAIL_DIV`。這類事件一律 `score=NULL`、`cycle_state=NULL`、`threshold_status=unknown_unpublished`；原始精確數值以 Decimal string 保存在 payload，拒絕 JSON float。
  - 已新增 `catos_public_event_candidate_v1` evidence-only candidate contract。`verified` DEX directional flow 只列出可能相關的 inflow/outflow taxonomy、正向 OI change 只列 `OI_BREAKOUT` 為可能相關事件；兩者均固定 `yaozi_event_triggered=false` 且 private threshold 維持 unknown。Hyperliquid public trade 因每筆成交同時存在 buyer/seller counterparties，只保存成交筆數、去重後 notional 與 wallet observations，`net_flow_status=not_defined_counterparty_symmetric`，且沒有 smart-wallet 分類時不映射成 `SMART_WALLET_*` 或 whale event。
  - Dashboard 已新增「候選證據 / EVIDENCE」頁，只讀 `/intel/event-candidates`，顯示 candidate type、原始方向／強度、來源、可能相關的 Yaozi taxonomy 與時間；possible taxonomy 不代表事件已觸發。
  - `catos.market_candidate_alignment` 提供離線黑箱時間對齊。它只讀目前 schema 的 market-intel DB 與指定 `catos-yaozi-blackbox-sample-v1` JSON，列出 Yaozi 已觀測事件前 5m / 15m / 1h 出現的 public candidates，並標示 taxonomy compatibility。輸出 contract 為 `catos_yaozi_candidate_alignment_v1`，另含 `alignment_summary`，直接統計各時間窗 candidate links、至少有一筆 link 的事件數、taxonomy-compatible links，以及最大時間窗內的 candidate type link coverage；這些都只代表 observational timing，不推論 trigger、threshold 或因果。
  - 2026-09-20 alignment 新增 `catos-yaozi-signal-surface-sample-v1`：可保存 `/signals` 畫面明示的時間、symbol、view、category 與 event title。這類 surface event 固定 `taxonomy_comparable=false`，candidate link 的 `taxonomy_compatible=NULL`；不得把中文 UI 文案自行映射成 `OI_BREAKOUT`、whale threshold 或其他私有 taxonomy。
  - `catos.market_candidate_evidence` 提供離線 negative-control scoring。它從 signal-surface sample 的 public candidate population 與 `capture_anchor` 判斷每個 5／15／30／60 分鐘窗口是否已具備完整 follow-up，再計算 candidate hit／miss；未走完整窗口的 candidate 固定列為 `non_evaluable`，不得當成 miss。若提供 market-intel DB，會用 candidate snapshot timestamp 精確讀取當輪 `derivative_snapshot` symbol universe，另外輸出 public-coverage event link rate。此值仍不是 recall，因 `/signals` surface filter 與完整私有 event taxonomy 並未保存／公開。
  - evidence scorer 輸出 contract 為 `catos_yaozi_candidate_evidence_score_v1`。`candidate_miss` 的語義僅是「在已捕捉的 signal surface 與指定 follow-up window 內未看到同 symbol event」；不等於 Yaozi gate 未觸發，也不證明 candidate 為 false positive。所有 rate 使用 Decimal text，沒有 float 回流交易或風控。零候選輪仍保留 `comparison_observed_at_ms` 作為採樣時間，檢查當輪公開資料覆蓋並計算已捕捉事件分母；candidate hit rate 保持 null，不把沒有正向 OI 候選誤報為沒有採樣。
  - 2026-09-19 歷史查詢修正（9／20 alignment＋API 最小驗收 23／23 通過）：候選改按各事件的幣種與前 60 分鐘閉區間查詢，所有區間共用單一 SQLite read snapshot。`--limit` 為每個區間的上限（1～1000），多讀一筆判斷截斷；截斷寫入 `candidate_query` 與 issue，統計明示 lower bound。重疊區間的候選按 ID 去重，原始 observation 及其 links 仍逐筆計數。`complete_stored_rows` 只代表已儲存候選查詢完整，不證明 OI／DEX／Hyperliquid 採樣完整；沒有事件時不讀全庫候選。既有 HTTP 候選端點保持原行為。
  - `catos.market_evidence_collect` 提供 watchlist-based、同步有界的 5m public evidence cadence。OI 成功路徑只呼叫 OKX public ticker + open-interest 兩個 endpoint；對應事實缺失時才個別 fallback Binance。持久化仍走既有 `record_public_batch()`，由同 venue snapshot 推導 5m / 1h / 4h OI delta，不另建第二套公式。Hyperliquid 使用 bounded frames + recv timeout，batch observation anchor 取本輪已接收交易的最新 source time，single-frame parser 仍拒絕 future source。Hyperliquid／DEX 同一 `source_id` 若跨 collection run 被來源重播，持久化保留首次 collection anchor；除 `observed_at_ms` 外的來源事實仍必須完全一致，否則拒絕為 `snapshot_conflict`。DEX 僅接受 caller 明示且通過 identity 驗證的 GeckoTerminal pool；沒有已驗證 pool config 時不自行猜 pool。
  - cadence runner 是同步 bounded rounds，不建立背景服務。CLI 可用 `python -m catos.market_evidence_collect --symbol BTC-USDT-SWAP --hyperliquid-symbol BTC-USDT-SWAP --rounds 1` 執行一次；`--dex-config` 需要 JSON list，每項明示 `symbol`、`chain`、`network_id`、`pool_address`、`venue`、`base_token_address`。加上 `--public-context` 後會把 Narrative + Trending-category attention + News 併入同一 bounded runner，預設每 3 輪採一次（5m cadence 下為 15m），第 1 輪一定採集；可用 `--public-context-every-rounds` 調整。所有 candidates 仍固定 evidence-only，不自動升格 Yaozi event hit。
  - rolling watchlist 可用 `--watchlist-config` 傳入 JSON object，僅允許 `symbols` 與 `hyperliquid_symbols` 兩個 string list；CLI 直接指定的 symbols 會與 config 合併，重複項去除。DEX pool identity 不接受從 rolling watchlist 帶入，仍必須走獨立 `--dex-config` 明示 verified pool identity。

- `catos.market_narrative_news`
  - Narrative 固定讀取 CoinGecko public categories endpoint；價格/市值/24h 變化等數值由 JSON 直接以 Decimal 解析，不經 binary float。
  - Public attention 另外讀取 CoinGecko public `/search/trending` 的 `categories`。目前只保存「本次出現在 trending categories」的 membership，以及 source-reported market cap / USD 24h change / total volume；現行 schema 無 source-rank 欄位，因此 `/intel/narrative-attention` 固定明示 `ranking_persisted=false`、`source_rank=null`、`social_heat=null`、`yaozi_heat=null`。2026-09-21 direct live smoke 回 6 categories、0 parser issues。
  - `/intel/sectors` 重用最新 CoinGecko categories snapshot 作公開 category/sector facts；`relative_strength`、`momentum`、`rotation_position` 固定為 null，因 YAOZI 公開 Guide 說明 rotation 使用 standardized position，不能拿 CoinGecko 24h market-cap change 代替。
  - News 固定讀取 CoinDesk public RSS；只保存 title、URL、published time、summary、source categories。RSS 修訂採 content-addressed revision 保存，read API 只回同 URL 最新 revision。
  - 不建立 Yaozi narrative score、importance、symbol tag、sector tag 或 ranking；`/intel/narrative`、`/intel/narrative-attention`、`/intel/sectors` 與 `/intel/news` 均保留 public-source / unknown-unpublished 邊界。
  - Social raw metric 已新增 `catos.market_social` 與 schema v14 persistence。固定讀 CoinPaprika public `GET /v1/coins/{coinpaprika_id}`，由 caller 明示 CoinPaprika ID，response 必須同時回傳相同 ID 與 CatOS base symbol 才接受 `links_extended.stats` 中的 Twitter followers / Reddit subscribers / Telegram members。link metadata、缺值與 provider failure 不轉成 metric；失敗 run 會遮蔽先前 count，不把舊值冒充 current。`/intel/social`、`/intel/picks/{symbol}/social` 與 `/intel/source-coverage` 已接。另新增 `catos-coinpaprika-identity-list-v1`：公開 `GET /v1/coins` 只建立 current active identity 候選集合，**不以 ticker 唯一性自動 mapping**；只有 caller 明示 ID 且 list 驗證 active + same-symbol 才 resolved，多候選 / 無候選 / unique-but-unverified 分別保持 `ambiguous_mapping` / `missing_asset` / `unverified_identity`。detail endpoint 再做 exact ID + base symbol 二次驗證。2026-09-21 current live universe 734 active symbols，只有既有 BTC/ETH explicit mapping 可安全 resolved；其餘 242 ambiguous / 324 unverified / 166 missing。暫存 v14 DB 仍只 materialize BTC/ETH 2 source runs / 4 metric rows；`social_heat`、`yaozi_heat`、ranking 固定 null / `unknown_unpublished`。證據見 `outputs/yaozi-social-verification-20260921.json` 與 `outputs/yaozi-social-mapping-verification-20260921.json`。主 `outputs/catos-market-intel.sqlite` 未執行 v12→v14 migration，也未寫入 social live facts。
  - 可用 `python -m catos.market_narrative_news --db <market_intel.sqlite> --observed-at-ms <ms>` 執行一次 bounded public collection；不讀憑證、不在 import 時連網。

- `catos.market_options`
  - 固定讀 OKX public `GET /api/v5/public/opt-summary` 與 `GET /api/v5/public/open-interest?instType=OPTION`，只允許 `https://www.okx.com`，不讀 API key。
  - Greeks、IV、forward price、OI 全部以 Decimal 解析並以 SQLite TEXT 保存；summary 與 open-interest 各自記錄 collection status，一邊失敗不會抹掉另一邊。
  - 第二公開 provider 新增 Deribit `GET /api/v2/public/get_book_summary_by_currency?currency={base}&kind=option`，固定 `https://www.deribit.com`。目前只接受 inverse `*-USD` family，provider batch 保留 expiry code、strike、C/P、underlying-base OI、mark IV、mark/underlying price 與 premium currency；不把 `quote_currency=BTC/ETH` 的 inverse facts 冒充 OKX `BTC-USD` / `ETH-USD` snapshot semantics。
  - 現行 option snapshot tables 沒有 source 欄，因此 Deribit 只寫 `option_context_run` source evidence，不混寫 `option_summary_snapshot` / `option_open_interest_snapshot`，也不要求 schema migration。2026-09-21 bounded live verification：`BTC-USD` 對應 Deribit BTC inverse options 取得 918 筆、0 issues、source-run `ok`；暫存 DB 的兩張 OKX-shaped snapshot tables 都維持 0。證據見 `outputs/yaozi-deribit-options-verification-20260921.json`。
  - `/intel/options` 與 `/intel/options/{instFamily}` 只做 latest source-fact join，Dashboard「期權 / GAMMA」頁只顯示 raw Greeks + OI。
  - `signed_gex`、dealer sign、Gamma aggregation 與 ranking 固定為 `NULL` / `unknown_unpublished`；即使 gamma 與 OI 同時存在，也不自行相乘冒充 YAOZI Gamma 指標。
  - OKX 官方文件已確認 public option market-data/open-interest contract。2026-09-21 已使用既有固定 public host、無憑證、10 秒 timeout、4 MiB body 上限的 `market_options._http_get` 路徑完成 bounded live verification：`BTC-USD` option summary 734 筆、open interest 1,726 筆，兩邊 0 issues，並以同一路徑 materialize 到主 market-intel DB。實測摘要見 `outputs/yaozi-options-live-verification-20260921.json`。這只證明 OKX public raw option facts live 可取得，不推導 signed GEX、dealer sign 或 YAOZI Gamma aggregation。

### P0-B 指標定義

本版 BB width 使用 `4 × population_std(close, 20) / SMA(close, 20) × 100`，對應 ±2σ Bollinger bands 的總寬度。BBWP 是目前 band width 相對前最多 100 個已可計算 width 的 percentile rank；不含目前值本身。

`structure_state` 只做資料特徵，不冒充妖子未公開 Structure score：目前 close 高於前 20 根 high 為 `BREAKOUT_UP`，低於前 20 根 low 為 `BREAKOUT_DOWN`，其餘為 `RANGE`。後續 L2 / Opportunity 若需要不同結構定義，必須版本化，不可偷偷改寫歷史 feature。

上述 BBWP / structure 是 catOS P0 自有可重播定義；目前沒有證據證明妖子內部使用完全相同公式，因此不標示為妖子公式 parity。

### P0-C Pattern 邊界

`COIL_BREAKOUT` / `AMBUSH` 需要 `volatility_percentile_15m`。目前不拿 BBWP 冒充 15m volatility percentile，也不猜 percentile baseline/lookback；上游沒有已驗證 percentile 時，結果保持 `MISSING_DATA`。

`PREHEAT` 的「5m OI acceleration > 1h average speed」採同百分比尺度比較：`OI delta 5m > OI delta 1h / 12`。

`TEAM_DISTRIBUTION` 只有在呼叫端同時提供 non-exchange -> exchange、單筆 >= US$500k，以及同幣 24h cooldown 已清除時才會 HIT；規則引擎本身不偷偷維護 wall-clock cooldown。

## 目前資料融合規則

`market_snapshot` 優先採 OKX，OKX 缺失才使用可用補充來源。`derivative_snapshot` 的 OI / funding 優先 OKX；Top Trader L/S 與 taker ratio 目前由 Binance 補充。來源選擇寫入 provenance / source-health JSON，不隱藏來源差異。

這只是來源優先序，不代表跨交易所 OI 已完成單位換算或 concentration 計算。不同 venue 的 raw normalized snapshot 保留原本單位標記，後續 Feature Engine 必須先完成 contract/base/notional 語義對齊後才能做跨所加總。

## 未執行的事情

- 本切片測試沒有對 OKX / Binance 發出真實網路請求。
- 沒有帳戶 API、Demo/Live 下單、撤單或任何寫入交易所行為。
- 已有 Kline parser、Binance REST trade-tail parser，以及 `catos.market_stream` 的 Binance USD-M
  public `aggTrade` WebSocket parser / fixed-host adapter / bounded continuity buffer。REST tail 仍一律 incomplete；
  WebSocket 只有在單一不中斷 coverage segment 完整跨過要求區間、且沒有 parser/order error 或 buffer truncation
  影響該區間時，才產生 `complete=True` 的 `TradeWindow` 給 CVD/taker 計算。實作未讀憑證、未連 user-data stream；
  本輪只以 mock transport 驗證，未對外執行真實採集。
- 已完成已知門檻的 L2 / Patterns；其餘 9 個 L2 私有門檻仍 disabled/unknown。
- P0-D 已實作 SMF interface 與 Flow / Opportunity / Risk deterministic lifecycle。
- Risk lifecycle v2 明示 cooling/hysteresis：已在 risk pool 的項目低於 45 先進 `cooling`；低於 30 連續 2 次才 `risk_resolved`。從未進過 >=45 risk pool 的低分項目不會憑空產生 resolved cycle；未公開的額外分鐘級 cooling 時間不自行補造。
- P0-E 已實作明示 directive 的 cycle reducer、immutable push freeze、24h proof evaluator，
  以及 caller-driven 60 秒 scan orchestrator。cycle 的 Yaozi 私有自動進場 gate 未公開，
  因此不推測；cycle / proof 的 MFE、MAE 定義為相對 push 價格的原始最大上行／下行 excursion，
  不宣稱為 Yaozi 私有方向分數。orchestrator 不讀 wall clock、不自行連網，通知只在 push snapshot
  commit 後觸發，24h proof 只接受已存在的 frozen push。
- History flat-threshold 已版本化保存公開日期語意：2026-05-08 前為 3%，自 2026-05-08 起為 1%。公開資料未明示把 epoch 轉成該日期時應採哪個時區，因此純規則函式要求 caller 傳入已正規化 source date；History API 只公布兩版 contract，不偷偷以 UTC／本機時區替歷史 cycle 分類。
- P0 read-only API 已實作於 `catos.market_api`。SQLite 使用 `mode=ro` + `query_only=ON`，HTTP 只輸出
  已物化資料，不在 API 層重算 score。`/intel/picks/{symbol}`、timeline、journey、signals、proof、
  unranked radar 與 Flow/Opportunity/Risk picks 已可讀。Momentum 依公開契約只組合已物化 SMF＋14 L2
  states，不建立獨立 score；Funnel 私有契約未公開，因此欄位明示 `not_materialized`。`/intel/today`
  採 `catos-p0-today-v2` latest-materialized 聚合，不讀 wall clock，並明示 `yaozi_contract=unverified`，
  不冒充 Yaozi 私有 Today 排序／公式。P1 已有對應持久化資料的 endpoint 讀取實際資料；尚未支援的能力保持 unavailable／missing；`serve()` 只允許 `127.0.0.1`。
- `/intel/signals` 已新增統一 materialized event stream，family 固定為 `signal / pattern / flow / onchain / lifecycle / status / candidate`。可用 `family`、`symbol`、inclusive `since_ms / until_ms` 與 `view` 篩選；`view` 只匹配資料表中明示的 `cycle_event.view_name`，不把其他事件硬映射到 YAOZI 私有 view taxonomy。全 stream 以 `observed_at_ms DESC + family/source_id` 穩定排序，先合併後套 global limit。
- `/intel/alerts` 是同一 event stream 的 read-only route projection，僅依 catOS source semantics 分到 `signals / flow / onchain / lifecycle / risk / status / public_evidence`；`mutation_supported=false`、`unread_state=null/not_materialized`。public candidate 仍固定 `yaozi_event_triggered=false`，不因 alert route 而升格成 YAOZI hit。Dashboard Signals 頁已接 family/view/time filters 與 read-only route counts；回應明示 `taxonomy_contract=catos_source_semantic_only`、`yaozi_taxonomy_mapping_status=unknown_unpublished`。
- Capital Flow 已補 Guide 公開的完整 31-kind semantic contract：10 個流入、6 個流出、9 個 lifecycle、6 個 structural/quality。`/intel/capital-flow/{symbol}` 會回 `yaozi-capital-flow-guide-taxonomy-v1`，固定標示 `display_only=true`、`smf_eligible=false`、`semantic_coverage=complete_31_of_31`。31 個 kind 都可作 source-explicit fact 保存，但本地 trigger 一律不由名稱自行反推，維持 `local_trigger_status=not_inferred`；既有 DEX `inflow/outflow` 仍是 catOS-native observation，不冒充 YAOZI 的 31 個私有 gate。
- `/intel/source-coverage` 已新增 `materialized_source_run_diagnostics_v1` read model，統一列出最新 `collector_run`、venue-level market/derivative snapshot、public context、Options、Hyperliquid、DEX、on-chain、liquidity 與 social source-run 狀態。DEX 只回已保存的 coverage proof；v12 起 on-chain 改讀最新 `onchain_source_run`；v13 liquidity 會回 source-explicit venue、`complete_2pct / partial_boundary_coverage / unavailable` 與 issues；v14 social 只在成功 run 有 provider-reported numeric count 時標 `materialized_public_count_source`。此 endpoint 固定 `freshness_status=not_evaluated_no_wall_clock`、`live_equivalence_status=not_inferred_from_persisted_run`，不把「曾 materialize」冒充「目前 live/fresh」。`/intel/onchain` 只有同 anchor 的 successful source run 且 `source_scope.collection_mode=live_public` 時才標 `provider_status=materialized_live_source_run`，否則為 `no_verified_live_source_run`。2026-09-21 修正高基數 derivative rows 對全域 `limit` 的 starvation：先按 `observed_at_ms` 選出最新 persisted diagnostics，再恢復 `(domain, source, scope)` 對外穩定排序。Dashboard「來源 / SOURCE」頁顯示 run status、coverage、identity、issues 與已知 gaps。
- Live on-chain public subset 新增 `catos.market_onchain` / `catos-blockscout-token-outgoing-address-v1`：固定 Ethereum `eth.blockscout.com/api/v2/tokens/{contract}/transfers` keyless GET，只接受 validated `block_number/index` cursor；caller 必須明示一個完整 24h `[day_start_ms, day_end_ms)`，collector 只有在目標日與前 14 個 24h window 都證明 complete 時才把 distinct non-zero/non-self `from` address counts 送進既有 `reduce_onchain_activity()`。page budget、transport/parser/scope/cursor 問題或未跨到 required history start 一律 `status=issues`，只保存 source-run evidence，不生成 `onchain_activity`。此來源只代表 ERC-20 transfer-from direct address activity，不做 beneficial-owner / whale identity，calendar boundary 也不由 provider 推測。2026-09-21 WBTC endpoint raw keyless GET 已回 HTTP 200、50 items 與 `block_number/index` next cursor，證明 live endpoint/payload contract 可用；高活動 WBTC 單頁只覆蓋數分鐘，完整 15-day live window 尚未驗證或 materialize，因此 Source 仍為 partial。
- Single-coin closed-candle workbench 已接 `/intel/picks/{symbol}/candles`。不帶 `timeframe` 時固定回五個 documented timeframe；帶參數時只接受 `15m / 30m / 1h / 4h / 1d`。每列保留原始 `venue/open_time_ms/timeframe_ms/OHLCV/volume_unit/closed`，Decimal 欄位保持 TEXT；回應明示 `derived_indicators=null`、`ranking=null`、`yaozi_overlay_status=unknown_unpublished`。Dashboard detail 只做 raw table 切換，不在瀏覽器端重算指標、overlay、marker 或 ranking。
- 同一 K-line read surface 新增 `catos-closed-candle-cost-reference-v1`：從單一 venue 最長尾端連續 4h closed candles，以 Decimal 計算 volume-weighted close，固定 42 bars = 7d、180 bars = 30d；若連續資料不足、volume 缺值／單位不一致或總 volume 非正值就保持 missing。回應與 Dashboard 都明示這是 CatOS public cost proxy，`yaozi_equivalence_status=not_claimed_private_formula_unpublished`；beneficial-owner holder share 與鏈上 holder cost 仍未重建，不拿 K 線 proxy 冒充 holder reconstruction。
- Holder public subset 新增 `catos.market_holders` / `catos-blockscout-address-holder-v1`：固定 Ethereum `eth.blockscout.com` 的 token detail + holders 路徑，依 Blockscout 公開的 balance-desc holder contract 驗證前 10 名順序、地址唯一性、page completeness 與 total supply 後，以 Decimal 計算 top10 direct-address share。parser 同時支援目前 Blockscout v2 的 `address_hash` / `holders_count` 與既有 fixture aliases。結果可透過既有 `dealer_snapshot.chip_json` materialize，不新增 schema；`MarketIntelStore.materialize_dealer_snapshot(..., chip=...)` 會保留 POSITION + CHIP coverage，既有 Dealer read surface 可直接讀取。此值只代表 ERC-20 直接持幣地址，不合併 exchange custody、vault、bridge、pool 或同一實體的多地址；`beneficial_owner_aggregation=not_available`、`yaozi_equivalence_status=not_claimed_source_semantics_only`。2026-09-21 keyless bounded live verification 已以 WETH `0xc02a...6cc2` 成功走完整 transport + parser：Blockscout 回報 3,348,933 holders，本地證明前 10 完整並得到 58.669906871554692593137817787784214245784532916141% direct-address share。這只驗證 Blockscout direct-address source contract，不把結果升格成 beneficial-owner concentration、holder cost 或 YAOZI 私有 Dealer identity。
- Holder-cost 公開可行子集新增 `catos-direct-address-stablecoin-cost-v1`。它只對單一 direct EOA 做 fail-closed reconstruction：地址的目標 token transfer history 必須在 bounded page 內完整、不得存在任何目標 token outflow、每個 inbound transaction 都必須能在同一 transaction token-transfer 集合中找到該地址直接淨支出的單一 USDT 或 USDC counterflow，且這些 acquisition 必須精確解釋目前 address balance；全部計算使用 Decimal。合約地址、分頁不完整、outflow、無／多重 quote counterflow、mixed quote、current balance 無法完全解釋都輸出 `MISSING_DATA`，不套用 FIFO/LIFO、不把 transfer-in 當買入，也不做 beneficial-owner 歸屬。2026-09-21 WETH top10 live probe 顯示 9/10 為 contract，唯一 EOA 的 WETH transfer history 超過 bounded page；因此 WETH top10 本輪沒有任何可安全輸出的 direct-address cost，正確維持 missing。此 contract 只是公開資料可驗證的窄子集，`yaozi_equivalence_status=not_claimed_private_formula_unpublished`，不能當成 YAOZI 主力成本。
- Multi-venue liquidity 新增 `catos.market_liquidity` 與 schema v13 persistence：目前固定使用 OKX、Binance、Bybit、Gate、Coinbase、Bitget 六個 spot public orderbook contract，以 Decimal 從 mid 向下／向上計算 ±2% quote notional。只有回傳 book 的最外層價格已跨過對應 ±2% boundary 時才填 `down_2pct_cost_text / up_2pct_cost_text`；否則只保存 `*_lower_bound_text`，coverage 標 `partial_boundary_coverage`，asymmetry 保持 null。crossed book、float/malformed row fail closed；單一 venue failure 隔離。`/intel/liquidity`、`/intel/picks/{symbol}/liquidity`、single-coin Dashboard detail 與 `/intel/source-coverage` 已接；asymmetry 僅作厚度描述，不轉成方向、SMF 或 YAOZI private signal。2026-09-21 direct live evidence 已覆蓋六個 configured venues：既有 OKX 400、Binance 500、Bybit 200、Gate 100 levels，新增 Coinbase 100 levels、Bitget 150 levels。Coinbase 當次 bid 側跨過 -2% boundary、ask 側未跨 +2%；Bitget 兩側都未跨，因此兩者整體仍是 `partial_boundary_coverage`，沒有把單側完整或 lower bound 冒充完整 ±2% depth。主 `outputs/catos-market-intel.sqlite` 仍維持已確認 v12，未在本切片執行 v12→v13 migration 或 live materialization。
- MoneyFlow public read model 新增 `yaozi-guide-money-flow-public-v1` 與 `/intel/picks/{symbol}/money-flow`：固定輸出 5m / 1h / 4h / 24h。每個 horizon 只有 persisted DEX coverage proof 實際覆蓋整段 window 才選 DEX；例如既有 1h pool proof 不會被延伸成 4h / 24h。DEX 不足時只接受 `flow_snapshot` 中 `trade_window_complete=1` 且能無縫覆蓋完整 horizon 的 CEX taker/CVD window；gap、重疊歧義或來源衝突均保持 missing。delta 僅在 current / previous 同類 source 與同 quote currency 時輸出，flow/market-cap ratio 使用 Decimal。DEX swap >= USD 1,000 只作 display subset 並附 tx reference；90d 單日淨流入峰值因 Guide 未公開 calendar-day timezone contract，固定 `calendar_day_timezone_contract_unpublished`。single-coin Dashboard 已顯示各 horizon selected source、net flow、delta、ratio、DEX/CEX coverage 與大額 swap；整體仍是 observation-only、`smf_eligible=false`。
- Today 的 `SINCE` 僅由 active cycle 的 `first_push_price_text` 與最新已物化市場價格用 Decimal 推導；
  沒有 active cycle 時維持 missing，不再拿 24h change 代替「入池以來」。

## 專屬驗證

```text
py -3 -B -m unittest tests.test_market_intel -v
py -3 -B -m unittest tests.test_market_candidate_evidence tests.test_market_candidate_alignment tests.test_market_api -v
```

驗證涵蓋 schema 0→2 / 1→2、WAL/FULL、固定 endpoint allowlist、USDT perpetual universe mapping、Decimal parsing、missing semantics、OKX/Binance materialization、closed candle filtering、REST trade-tail incomplete 語義、OI delta、Decimal feature 計算、L2/Pattern 邊界、三值 missing semantics、immutable feature/flow/signal materialization、exact replay 與 snapshot conflict。

2026-09-21 Capital Flow semantic slice：`tests.test_market_p1 + tests.test_market_api` 37/37；全部 `test_market*.py` 166/166。無 schema change、無 network I/O、無新增 provider。

2026-09-21 MoneyFlow deterministic slice：`tests.test_market_api` 21/21；全部 `test_market*.py` 176/176；`py_compile` 通過。無 schema change、無 network I/O、無新增 provider；既有 DEX 1h proof 不外推到較長 horizon。

2026-09-21 Holder address-level slice：`tests.test_market_holders + tests.test_market_p1` 26/26；全部 `test_market*.py` 182/182。無 schema change；WETH Blockscout current-v2 live reconstruction 已成功，驗證 direct-address holder source 可用；beneficial-owner aggregation、holder cost 與 Dealer direction 仍保持 unavailable / unknown。
2026-09-21 Liquidity live/venue expansion slice：新增 Bybit + Gate fixed public GET allowlist 與 parser，configured venues 擴為 OKX/Binance/Bybit/Gate。四個 venue 均完成 bounded live source verification；focused liquidity/intel/API 51/51、全部 `test_market*.py` 183/183、`py_compile` 通過。當次 books 均為 `partial_boundary_coverage`，因此只保存 lower bound。主 DB v12→v13 未執行。
2026-09-21 Liquidity Coinbase/Bitget expansion slice：新增 Coinbase market product book + Bitget v2 spot orderbook fixed public GET allowlist 與 parser，configured venues 擴為六個。Coinbase 100×100、Bitget 150×150 bounded live verification 均成功；focused liquidity/intel/API 52/52、全部 `test_market*.py` 187/187。Coinbase 僅 bid 側達 -2%，Bitget 兩側皆未達，因此兩者仍是 partial coverage。無 schema change，主 DB v12→v13 未執行。
2026-09-21 Holder-cost public subset：`tests.test_market_holders + tests.test_market_p1` 29/29；全部 `test_market*.py` 186/186。新增 `catos-direct-address-stablecoin-cost-v1` direct-EOA acquisition reference，對 contract holder、paginated history、target outflow 與無法證明同交易 quote counterflow 一律 fail closed。WETH top10 bounded live probe 為 9 contract + 1 EOA；該 EOA history 不完整，因此 10/10 都沒有可宣稱的 holder cost。無 schema change，不提高 parity 分數。
2026-09-21 Blockscout on-chain provider slice：`catos.market_onchain` + `tests.test_market_onchain` 已完成 fixed-host transport、caller-supplied day boundary、15 個 24h buckets、distinct outgoing address reducer linkage、mint/self exclusion、scope/token/cursor/ordering/duplicate fail-closed，以及 source-run-first persistence。focused onchain/P1/intel/API 72/72、全部 `test_market*.py` 192/192、`py_compile` / scoped `diff --check` 通過。live evidence 目前只證明 WBTC public token-transfer endpoint、payload、timestamp 與 cursor 形狀；完整 15-day pagination 未驗證，因此不宣稱 main DB live on-chain materialization。

## 下一切片

2026-09-20 唯讀重跑七份 9／18 blackbox sample：85 筆觀測、43 個區間，0 links，無截斷與解析 issue。現存 48 筆候選全部位於 9／19 10:56:32～13:10:52（台北時間），與樣本不重疊；DEX observation 為 0。下一步需補同時段觀測，不能將不同日期資料視為同步證據。詳細驗收見最新恢復交接。

2026-09-20 已從 authenticated rendered `/signals` 補兩份 surface sample：一份保存 9／20 08:31～09:03 最近事件及 09:05 public OI baseline；另一份保存 9／19 11:04～13:46 的歷史 signal events，用來與既有 9／19 candidates 做真正同日期對齊。後者 11 筆 signal observation 在事件前 60 分鐘仍為 0 candidates；JUP／BR 的已存 OI candidates 出現在可見 12:42～12:43 signal events 之後，因此不得反向算成 leading evidence。

2026-09-20 10:00 surface sample 已出現第一批真正 preceding evidence。11 個 `OI_POSITIVE_CHANGE` candidates 中，5m 完整 follow-up 為 0／11 hit；15m 與 30m 均為 3／11 hit（HOME、SKYAI、USELESS）與 8／11 negative controls。當輪 exact derivative public coverage 為 19 symbols；candidate snapshot 後捕捉到的 34 筆 surface events 中有 10 筆位於這 19 symbols，15m／30m 各有 4／10 observed events 存在 preceding positive-OI candidate。60m 在 10:00 capture 時 11 個 candidates 都尚未走完整窗口，因此不計 candidate hit/miss rate；已看到的 5 個 60m links 只能作 observational lower-horizon evidence。完整輸出見 `outputs/yaozi-candidate-evidence-score-2026-09-20-1000.json`。

P0 的資料／訊號／lifecycle／proof／read API、Momentum component view、catOS Today aggregate 與 bounded
public trade stream 基礎已具備；Funnel 私有 contract 仍維持 unknown。P1 已具備 Hyperliquid observation、DEX pool flow、single/multi-pool coverage proof、identity gate、catOS-native Capital Flow materialization、Yaozi observed-event fact、public evidence candidate persistence/read surface、candidate dashboard、離線 Yaozi candidate timing alignment，以及 watchlist-based 5m public evidence cadence。實際 v8 DB 已確認舊資料沒有足夠 OI cadence／Hyperliquid／DEX evidence；後續要累積同步樣本後再重跑 5m / 15m / 1h alignment，依 coverage 決定是否補 CEX flow、top-trader divergence 或 funding/contract ignition 公開 evidence。不得由時間共現直接反推私有 threshold 或因果。
