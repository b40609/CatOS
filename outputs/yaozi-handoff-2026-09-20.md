# YAOZI Development Handoff — 2026-09-20

## 目前目標

先完整重建 YAOZI 的功能與資料語義，再依使用者需求刪減；不追求畫面像素級複製，也不猜未公開 private formula。

YAOZI 是獨立資料分析系統分支。研究階段只讀：不改 YAOZI 設定、不發聊天室訊息、不改已讀、不下單、不撤單。

## 目前完成度

客觀 functional parity：**73.5 / 88 = 83.5%**。

計分不是看程式碼行數，而是每個功能域分四層：

1. Implementation：本地邏輯／資料結構存在。
2. Source：上游資料來源實際可取得。
3. Verification：有 deterministic test／固定 evidence 驗證。
4. Surface：有可使用的 API／dashboard／互動 surface。

完整計分見：`outputs/yaozi-parity-matrix-2026-09-20.md`。

## 已完成的官方研究

已完整讀官方 Guide，並從首頁開始逐頁核對目前可發現的第一方 Live surface：

2026-09-21 已再次從 authenticated rendered `/guide` 完整讀取全部 33 個正式內容 anchor，並固化為 `outputs/yaozi-guide-evidence-baseline-2026-09-21.md`。這份檔案是未來新 session 的 Guide source-of-truth baseline；除非要檢查網站是否改版，否則不要再次完整爬 `/guide`。

- `/`
- `/today`
- `/narrative`：rotation / narrative map / sectors / news / Options-Gamma
- `/picks`：flow / momentum / opportunity / risk / history
- `/picks/{symbol}` 單幣頁與 K 線工作台
- `/operator/{symbol}` Dealer
- `/operator/onchain`
- `/signals`
- `/proof`
- `/account`
- Chat panel
- Whistle / 警哨 drawer
- `/guide`、`/guide/signals`
- `/legal/terms`、`/legal/privacy`
- `/login`、`/register`、`/forgot`
- aliases：`/sectors`、`/focus/{symbol}`

`/reflection` 為 admin-only，已記錄 inaccessible state，沒有繞過。

`sitemap.xml` 回 404，因此不能宣稱 private backend／隱藏 route 已完整枚舉。

官方研究成果：

- `outputs/yaozi-official-guide-spec-2026-09-20.md`
- `outputs/yaozi-guide-evidence-baseline-2026-09-21.md`
- `outputs/yaozi-site-surface-inventory-2026-09-20.md`
- `outputs/yaozi-parity-matrix-2026-09-20.md`
- 舊研究底稿：`outputs/yaozi-functional-parity-spec-v0.1.md`

## 已確認的公開核心規則

- SMF：-100..+100；S >= +50、A +20..+49、B -20..+19、C -49..-20、D <= -50。
- Momentum 沒有獨立 score，直接使用 SMF。
- God-tier：resonance >=3 + quality >=80 + 24h hits >=4 + push 後最大漲幅 >=5%。
- FLOW：OI velocity×35 + taker×15 + top-trader LSR slope×15 + OI quadrant×10 + consolidation×10 + capital cycle×10 + momentum tilt×10；>=70 ignition，50–69 accumulation，<35 連 3 次 exit。
- Opportunity：quality >=55 enter；<45 連 3 次 exit；risk >=60 block。
- Risk：>=60 high risk；>=45 watch；<30 連 2 次 resolve；Live 另有 cooling/hysteresis 呈現。
- Adaptive exit floor：clamp(8×ATR%, 8%, 22%)；peak hard floor -20%；stale 720h。
- 14 light signals、patterns、31 Capital Flow event kinds 已讀；Capital Flow event 為 display-only，不直接進 SMF。
- K 線週期：15m / 30m / 1h / 4h / 1d。
- Direction badge -100..+100 是 observation-only composite，和 SMF 不同，不進 scoring。
- On-chain flag：完整日 >=3× AND distinct outgoing >=5 AND baseline >=7d；Elevated >=2×；Plateau 用事件前 anchor baseline，進榜 >=3×、留榜 >=1.5×。
- Narrative Live 比 Guide 多 Options/Gamma。

## 仍必須保持 unknown_unpublished

以下沒有足夠第一方公開證據，不可猜：

1. Exact SMF base weights / full private formula。
2. L1/L2 private funnel gate、ranking、去重全規則。
3. 多個 L2 light 的 absolute threshold。
4. Opportunity quality 的完整生成公式。
5. Dealer direction exact formula。
6. `/reflection` 後台調權 policy。
7. `EARLY` 視角 exact scoring / lifecycle gate；2026-09-21 Guide 有顯示 label，但沒有獨立 deterministic formula。

缺失值維持 `None` / `NULL` / `unknown`，不可轉成 0。

## 目前 repo 已存在的 YAOZI 分支能力

主要模組：

- `catos/market_collectors.py`
- `catos/market_features.py`
- `catos/market_signals.py`
- `catos/market_lifecycle.py`
- `catos/market_proof.py`
- `catos/market_intel.py`
- `catos/market_orchestrator.py`
- `catos/market_api.py`
- `catos/market_dashboard.py`
- `catos/market_hyperliquid.py`
- `catos/market_dex.py`
- `catos/market_p1.py`
- `catos/market_p1_materialize.py`
- `catos/market_candidate_evidence.py`
- `catos/market_candidate_alignment.py`
- `catos/yaozi_surface_lifecycle.py`

已存在：public market adapters、Decimal features、已公開 L2/patterns、Flow/Opportunity/Risk lifecycle、proof、orchestrator、SQLite materialization、localhost read API、dashboard、Hyperliquid observation、DEX evidence、Capital Flow、Dealer、On-chain 計算與 offline evidence alignment。

注意：有 class/function 不等於 parity completed；Narrative / News 已於 2026-09-21 接上 public ingestion + SQLite + API/dashboard，Sectors 以 CoinGecko category source facts materialize，另接 CoinGecko `/search/trending` category membership 作 public attention；2026-09-21 live smoke 回 6 categories、0 parser issues。Attention 不保存來源 rank，不冒充 social/YAOZI heat。Alpha+/Alpha 與 explicit status labels 已物化。Options/Gamma 已接 OKX public option summary + open-interest、SQLite、read API 與 dashboard；2026-09-21 已完成 `BTC-USD` bounded live verification：summary 734 筆、OI 1,726 筆、0 issues。單幣頁已接 15m / 30m / 1h / 4h / 1d closed-candle raw workbench；不存在的 timeframe 明示 missing，不在 read API 補算。Narrative ranking/heat、News importance、signed GEX、dealer sign 與 YAOZI Gamma aggregation 均不可冒充私有公式。

## 2026-09-21 已完成切片

已補「已公開、無需猜 private formula」的規則：

1. 擴充 `catos/market_signals.py`：
   - trend reversal pattern
   - distribution pattern
   - Alpha+ / Alpha cross-axis selection rules
   - observe / dump-warning / new-candidate 等 status labels
2. 加最小必要單元測試。
3. Risk cooling state semantics：已進 risk pool 後 <45 進 cooling，<30 連 2 次 resolved；不猜額外分鐘參數。
4. History 2026-05-08 前後 flat-threshold versioning：3% → 1%；source timezone 未公開，所以不從 epoch 偷猜逐筆日期。
5. Narrative + News：CoinGecko Categories + CoinDesk RSS 已接 bounded collector、read API、dashboard，並併入 5m evidence runner 的可選 15m public-context cadence。
6. Schema 10：Alpha+/Alpha cross-axis 與 `OBSERVE / DUMP_WARNING / NEW_CANDIDATE` explicit status labels 已接 immutable SQLite + read API；exact replay idempotent，同 identity 不同內容 conflict。
7. Schema 11：OKX public `opt-summary` + option `open-interest` 已接 bounded collector、Decimal TEXT SQLite、read API、Options/Gamma dashboard 與 deterministic tests。只呈現 raw Greeks + OI；signed GEX / YAOZI Gamma aggregation 維持 null/unknown。
8. parity matrix 已按實際 implementation/source/verification/surface 更新，不把 unknown private formula 算完成。
9. Single-coin K-line workbench：`market_candle` 的 closed OHLCV 已接 15m / 30m / 1h / 4h / 1d reader、`/intel/picks/{symbol}/candles` 與 detail Dashboard；每個 timeframe 有 materialized/missing 狀態，價格與成交量維持 SQLite Decimal TEXT，不生成 private indicator/overlay/marker/ranking。專屬 API 14/14、受影響回歸 116/116 通過。
10. Sector / public attention：`/intel/sectors` 已從 `coingecko-categories` materialized source facts 輸出，YAOZI standardized relative strength / momentum / rotation position 維持 null；`coingecko-trending-categories` 透過既有 `narrative_snapshot` 保存 trending membership 與 public market facts，`/intel/narrative-attention` 與 Dashboard 已接。Current CoinGecko `community_data` 實測為 null，且 `twitter_followers` 已於 2025-05-15 被官方移除，因此 social heat 仍未 materialize。受影響回歸 123/123 通過。
11. Signals stream / alert read routing：`/intel/signals` 已統一讀取既有 `signal_hit / pattern_hit / capital_flow_event / onchain_activity / cycle_event / status_label_snapshot / public_event_candidate`，提供 `family / symbol / view / since_ms / until_ms / limit` deterministic filters；`view` 僅匹配 explicit `cycle_event.view_name`。`/intel/alerts` 只做同 stream 的 read-only route projection，不建立 unread/write state。Dashboard Signals 頁已接 filters + route counts。`taxonomy_contract=catos_source_semantic_only`、YAOZI taxonomy mapping 保持 `unknown_unpublished`；public candidate 不自動升格。Market affected regression 153/153 通過。
12. Source coverage diagnostics：`/intel/source-coverage` 已接 existing SQLite 的 core collector/venue market/venue derivative、public context、Options、Hyperliquid、DEX、on-chain materialization。輸出只描述 persisted latest runs，固定不做 wall-clock freshness/live inference；DEX 只呈現已保存 coverage proof，on-chain provider identity 若 schema 未記錄則保持 unknown。Dashboard 新增「來源 / SOURCE」頁。Market affected regression 154/154 通過；此 slice 沒有新增 upstream provider，因此 parity 維持 68 / 84 = 81.0%。
13. DEX 真實 upstream / multi-pool coverage：新增 `outputs/yaozi-dex-pools-20260921.json`，以既有 `market_evidence_collect` bounded 路徑對 `ETH-USDT-SWAP` 採集 Ethereum WETH/USDC Uniswap V3 `0x88e6...5640` + Uniswap V2 `0xb4e16...c9dc`。主 `outputs/catos-market-intel.sqlite` 實測 2 runs / 600 observations / 0 issues，`/intel/signal-dex/ETH-USDT-SWAP` 為 `verified_multi_pool_window`，兩個 pool base-token identity 一致。另修正 `/intel/source-coverage` 高基數 derivative rows 先吃掉 `limit=500` 的 starvation：先選最新 persisted diagnostics，再恢復既有 deterministic `(domain, source, scope)` 排序。`tests.test_market_api` 17/17、market affected regression 155/155 通過。實測摘要：`outputs/yaozi-dex-live-verification-20260921.json`。此 slice 只驗證單一資產兩個 configured pools，仍不宣稱全市場 DEX/YAOZI source equivalence，因此 parity 維持 68 / 84 = 81.0%。
14. OKX public Options live coverage：沿用 `catos.market_options` 的固定 `www.okx.com` public host、兩個 allowlisted GET path、無憑證、10 秒 timeout、4 MiB body limit；`BTC-USD` bounded live smoke 與主 DB materialization 均成功，summary 734 筆、open-interest 1,726 筆、0 issues。專屬 Options + API tests 22/22 通過。實測摘要：`outputs/yaozi-options-live-verification-20260921.json`。Options Source 由 0.5 升為 1.0；signed GEX、dealer sign、YAOZI Gamma aggregation 仍保持 unknown，因此 parity 只增加 0.5，更新為 68.5 / 84 = 81.5%。
15. Live on-chain provider schema boundary 已處理：使用者已明確核准 Schema v12；`SCHEMA_VERSION=12`，新增單一 `onchain_source_run` evidence table，保留既有 reducer/activity table 不動。writer 採 exact replay/conflict contract；`/intel/source-coverage` 改讀 explicit on-chain source runs，`/intel/onchain` 只有 successful 同 anchor source run 且 `collection_mode=live_public` 才標 `materialized_live_source_run`。v11→v12 migration、source-run replay/conflict 與 API linkage focused tests 58/58 通過；主 `outputs/catos-market-intel.sqlite` 已升至 v12，目前 `onchain_source_run` 為 0 筆。Blockchair keyless public REST 候選的 raw network smoke 被 runtime safety review 攔截，未重送，因此尚未宣稱 live provider verified，On-chain Source 分數維持 0。驗收摘要：`outputs/yaozi-onchain-schema-v12-verification-20260921.json`。
16. Guide baseline persistence：2026-09-21 authenticated `/guide` 的 33 個正式 anchor 已完整讀取並落成 `outputs/yaozi-guide-evidence-baseline-2026-09-21.md`。新確認：`EARLY` 有 label 但無獨立 formula；current Guide 已直接公開 `OBSERVE / DUMP_WARNING / NEW_CANDIDATE` derivation；31-kind Capital Flow taxonomy、exit reason dictionary、MoneyFlow DEX >= USD 1,000 fallback contract、concentration >66%、Dealer n/3 evidence semantics 都已建立 source-status 與 CatOS implementation-status 索引。這是文件／證據切片，沒有新增 upstream provider，因此 parity 維持 68.5 / 84 = 81.5%。
17. Guide deterministic gap：`OBSERVE / DUMP_WARNING / NEW_CANDIDATE` 已由 source-explicit-only 擴充成 local facts derivation，仍保留 explicit override 與三值 `MISSING_DATA`；status-label version 升為 `yaozi-status-label-guide-v2`。同時在 `market_lifecycle` 補 momentum exit deterministic subset：`clamp(8×ATR%,8%,22%)`、720h stale、peak -20% hard exit、leading-signal exit、healthy-pullback exemption。risk-off exact tightening 未公開，因此依賴該未知幅度的 case 固定維持 `MISSING_DATA`，不猜私有公式。focused market lifecycle/signals/intel 51/51 通過；此 slice 不新增 upstream source 或 user-facing surface，因此 parity 總分不變。
18. Capital Flow 31-kind semantic coverage：`catos.market_p1` 新增 Guide 31-kind canonical semantic contract，分組固定為 inflow 10 / outflow 6 / lifecycle 9 / structural-quality 6；`CapitalFlowEvent` 與 source-explicit observed fact 路徑可表示全部 31 kind，`/intel/capital-flow/{symbol}` 回傳 `yaozi-capital-flow-guide-taxonomy-v1`。所有 kind 明示 `display_only=true`、`smf_eligible=false`、`local_trigger_status=not_inferred`，沒有由名稱猜 private gate；既有 DEX `inflow/outflow` 保留 catOS-native observation。無 schema change、無 network I/O。focused P1+API 37/37、全部 `test_market*.py` 166/166 通過。Capital Flow Implementation 由 0.75 補到 1，Source 仍 0.5，因此 parity 更新為 68.75 / 84 = 81.8%。驗收摘要：`outputs/yaozi-capital-flow-semantics-verification-20260921.json`。
19. 7d/30d public cost reference：`/intel/picks/{symbol}/candles` 新增 `catos-closed-candle-cost-reference-v1`，只讀 SQLite 已 materialize 的同 venue 4h closed candles，選尾端最長連續序列，以 Decimal volume-weighted close 計算 42 bars / 180 bars 的 7d / 30d cost reference 與距最新 close 百分比。資料不足、gap、volume 缺值／單位混用均 fail closed；Dashboard K-line workbench 已顯示兩個 cost reference。此值明示 `yaozi_equivalence_status=not_claimed_private_formula_unpublished`，holder share 仍 `not_materialized_no_verified_holder_source`，不冒充 YAOZI holder cost。無 schema change、無 network I/O；API focused 19/19、全部 `test_market*.py` 168/168、`py_compile` 通過。此 slice 沒有新增 verified holder source，因此 parity 維持 68.75 / 84 = 81.8%。驗收摘要：`outputs/yaozi-cost-reference-verification-20260921.json`。
20. Multi-venue ±2% liquidity：新增 `catos.market_liquidity`，固定 OKX + Binance spot public orderbook adapter，以 Decimal 從 mid 計算每 venue -2% bid depth / +2% ask depth；只有 provider 回傳 book 已跨過 boundary 才 materialize full depth，否則保存 `*_lower_bound_text` 並標 `partial_boundary_coverage`。crossed/malformed/float-containing book fail closed，單一 venue failure 隔離。Schema 升為 v13，新增 `liquidity_source_run / liquidity_snapshot`，writer 採 exact replay/conflict；v12→v13 migration 已測。`MarketIntelReader.liquidity()`、`/intel/liquidity`、`/intel/picks/{symbol}/liquidity`、`/intel/source-coverage` 與 single-coin Dashboard 已接；asymmetry 僅兩側完整時輸出且 descriptive-only。focused liquidity/intel/API 49/49、全部 `test_market*.py` 175/175、`py_compile` 通過。Direct OKX/Binance live smoke 與主 `outputs/catos-market-intel.sqlite` v12→v13 migration 都被本 Session runtime safety review 攔截，因此不宣稱 live verified、主 DB 仍視為 v12；Source 只計 0.5。新增 Liquidity 功能域 I/S/V/U = 1/0.5/1/1，parity 更新為 72.25 / 88 = 82.1%。驗收摘要：`outputs/yaozi-liquidity-verification-20260921.json`。
21. MoneyFlow Guide public subset：`MarketIntelReader.money_flow()` 與 `/intel/picks/{symbol}/money-flow` 已完成 5m / 1h / 4h / 24h。每個 horizon 只在 DEX coverage proof 完整包住該 window 時選 DEX；既有 1h proof 不可外推到 4h / 24h。DEX 不足時，只有 `flow_snapshot` complete windows 能無 gap／無歧義覆蓋整段才 fallback CEX taker/CVD。current / previous delta 僅同類 source + 同 quote currency，flow/market-cap ratio 全 Decimal；DEX >= USD 1,000 swaps 附 tx reference。90d daily inflow peak 因 Guide 未公開 calendar/timezone rule 固定 missing。single-coin Dashboard 已接 selected source/net flow/delta/ratio/coverage/large swaps。無 schema change、無 network I/O、無新增 provider；`tests.test_market_api` 21/21、全部 `test_market*.py` 176/176、`py_compile` 通過。現行 parity matrix 沒有獨立 MoneyFlow scored row，且本 slice 未新增 live source，因此總分維持 72.25 / 88 = 82.1%。驗收摘要：`outputs/yaozi-money-flow-verification-20260921.json`。
22. Holder address-level reconstruction：新增 `catos.market_holders` / `catos-blockscout-address-holder-v1`，固定 Ethereum Blockscout instance 的 token detail + holders contract。parser 強制 ERC-20 contract identity、total supply、balance-desc、前 10 完整性、地址唯一性與 supply consistency；top10 share 全 Decimal，並兼容目前 Blockscout v2 `address_hash` / `holders_count` 欄位。結果透過既有 `dealer_snapshot.chip_json` materialize，無 schema change，Dealer direction 仍 null/unknown。語義明示為 `direct_token_balance_address`；custody / exchange / vault / bridge / pool 與同 beneficial owner 多地址不合併，不能冒充 YAOZI 私有 holder identity。2026-09-21 WETH `0xc02a...6cc2` bounded live reconstruction 已成功：Blockscout 回報 3,348,933 holders，前 10 direct-address share 58.669906871554692593137817787784214245784532916141%，top10 completeness 通過。focused holder+P1 26/26、全部 `test_market*.py` 182/182 通過。Dealer profile 因 beneficial-owner aggregation、holder cost 與 direction source/formula 仍 partial，parity 維持 72.25 / 88 = 82.1%。驗收摘要：`outputs/yaozi-holder-verification-20260921.json`。
23. Liquidity direct live + venue expansion：`catos.market_collectors` / `catos.market_liquidity` 新增 Bybit `api.bybit.com/v5/market/orderbook` 與 Gate `api.gateio.ws/api/v4/spot/order_book` fixed public GET allowlist，configured venues 擴為 OKX/Binance/Bybit/Gate。Bybit parser 驗證 echoed symbol；Gate 使用 request-scoped pair；兩者與既有來源都沿用 Decimal ±2% / lower-bound contract。2026-09-21 bounded live verification：OKX 400、Binance 500、Bybit 200、Gate 100 levels 都成功經各自 parser；當次四個 books 都未跨滿 ±2% boundary，正確維持 `partial_boundary_coverage`。四 venue 合併 collector 單命令後續被 runtime safety review 攔截，但四個 source 已分別有 live evidence。focused liquidity/intel/API 51/51、全部 `test_market*.py` 183/183、`py_compile` / scoped `diff --check` 通過。主 DB v12→v13 未執行。Liquidity Source 0.5→1.0，parity 更新為 72.75 / 88 = 82.7%。驗收摘要：`outputs/yaozi-liquidity-verification-20260921.json`。
24. Holder-cost public feasible subset：`catos.market_holders` 新增 `catos-direct-address-stablecoin-cost-v1` 與 Blockscout address / address token-transfers / transaction token-transfers fixed-host read path。只在 direct EOA 的目標 token history 能於 bounded first page 完整取得、完全沒有 target outflow、每筆 inbound transaction 都有同地址直接單一 USDT 或 USDC net spend，且這些 acquisitions 精確解釋 current balance 時，才用 Decimal 輸出 address-level quote cost。contract holder、paginated history、outflow、unpriced/multi-quote inbound、mixed quote、balance mismatch 全部 `MISSING_DATA`；不套 FIFO/LIFO、不推 beneficial owner，也不宣稱等於 YAOZI 主力成本。WETH top10 bounded live probe：9 contract + 1 EOA；唯一 EOA transfer history 超出 bounded page，因此 10/10 均沒有可安全輸出的 holder cost。focused holder+P1 29/29、全部 `test_market*.py` 186/186 通過；無 schema change。此切片只建立可證明的 fail-closed subset，Dealer / K-line scored rows不升分，parity 維持 72.75 / 88 = 82.7%。驗收摘要：`outputs/yaozi-holder-cost-verification-20260921.json`。
25. Coinbase / Bitget liquidity venue expansion：`catos.market_collectors` / `catos.market_liquidity` 新增 Coinbase `api.coinbase.com/api/v3/brokerage/market/product_book` 與 Bitget `api.bitget.com/api/v2/spot/market/orderbook` fixed public GET allowlist。Coinbase parser 驗證 echoed `product_id` 並解析 dict price/size levels；Bitget parser 驗證 `code=00000` 並保留 source ms。兩者沿用 `catos-spot-depth-2pct-v1` Decimal / boundary / lower-bound contract及單來源失敗隔離。2026-09-21 bounded live：Coinbase 100×100 成功，bid 側跨 -2% 但 ask 側未跨 +2%；Bitget 150×150 成功，兩側均未跨，因此兩者都維持 `partial_boundary_coverage`。focused liquidity/intel/API 52/52、全部 `test_market*.py` 187/187 通過；無 schema change，主 DB v12→v13 未執行。Liquidity Source 原已 1.0，parity 維持 72.75 / 88 = 82.7%。驗收摘要沿用 `outputs/yaozi-liquidity-verification-20260921.json`。
26. Blockscout live on-chain provider implementation：新增 `catos.market_onchain` / `catos-blockscout-token-outgoing-address-v1`，固定 `eth.blockscout.com` Ethereum token-transfer path、token contract scope、validated `block_number/index` cursor、caller-supplied 24h day boundary、目標日 + 前 14 個完整日 coverage gate，以及 bounded page limit。只有 15 個 window 都完整時才把 distinct ERC-20 `from` address counts餵入既有 3×/2×/1.5× reducer；mint sender與 self-transfer 排除，token scope mismatch、non-monotonic source order、duplicate transfer、repeated cursor、transport/parser issue、page truncation全部 fail closed。partial run 可保存 `onchain_source_run` evidence，但不產生 activity。WBTC raw keyless live GET 已取得 HTTP 200、50 items、timestamp/token fields 與 `block_number/index` cursor；同 adapter 的完整 live collection 仍被 runtime safety review 攔截，且單頁只覆蓋數分鐘，因此沒有宣稱 15-day complete 或主 DB live materialization。focused onchain/P1/intel/API 72/72、全部 `test_market*.py` 192/192、`py_compile` / scoped `diff --check` 通過。On-chain I/S/V/U 更新為 1/0.5/1/1，parity 由 72.75/88 提升至 73.5/88 = 83.5%。驗收摘要：`outputs/yaozi-onchain-provider-verification-20260921.json`。
27. Deribit second public Options provider：完整 15-day Blockscout live probe 再次被 runtime safety review 阻擋後，依既定 fallback 轉做 Options 第二來源。`catos.market_options` 新增固定 `www.deribit.com/api/v2/public/get_book_summary_by_currency?currency={base}&kind=option` 的 inverse option book provider，parser 保留 expiry/strike/C-P、underlying-base OI、mark IV、mark/underlying price 與 premium currency。因現行 option snapshots 沒有 source 欄，Deribit 只 persist `option_context_run` source evidence，不把 venue facts 混入 OKX snapshots，也不升 schema。2026-09-21 `BTC-USD` bounded direct live：918 items、0 issues、source-run `ok`，暫存 DB `option_summary_snapshot=0`、`option_open_interest_snapshot=0`；focused `tests.test_market_options` 8/8、`py_compile`、scoped `diff --check` 通過。Options 原已 4/4，本片只補 provider breadth，parity 維持 73.5/88 = 83.5%。驗收摘要：`outputs/yaozi-deribit-options-verification-20260921.json`。
28. CoinPaprika social raw metrics：新增 `catos.market_social` 與 schema v14 `social_source_run` / `social_metric_snapshot`，caller 明示 CoinPaprika ID 並驗證 response ID + base symbol 後，只保存 provider-reported Twitter followers / Reddit subscribers / Telegram members。link metadata、缺值、transport/parser failure 不轉 metric；失敗 latest run 不沿用舊 count。`/intel/social`、`/intel/picks/{symbol}/social` 與 source-coverage 已接，`social_heat` / `yaozi_heat` / ranking 固定 null。官方 endpoint 文件標示 Free plan 可用、update interval every 1 minute，但 counter 無 source timestamp，因此只宣稱 bounded current endpoint evidence，不宣稱單筆 counter freshness。2026-09-21 BTC/ETH direct live 0 issues，暫存 v14 DB 2 runs / 4 metrics；focused social+intel+API 54/54、`py_compile`、scoped `diff --check` 通過。主 DB 未 migration、未 social materialize。Narrative / sector rotation 仍缺 universe-wide mapping 與 private heat formula，故 parity 維持 73.5/88 = 83.5%。證據：`outputs/yaozi-social-verification-20260921.json`。

下一個直接執行切片：完整 15-day Blockscout live pagination 本輪再次被 runtime safety review 阻擋，On-chain Source 維持 partial，不重試相同 blocked 路徑。Social raw metric provider / persistence / read API 與 BTC/ETH bounded live proof 已完成；後續若要提高這一域，先補 universe-wide CoinPaprika ID mapping coverage，不以 raw counts 猜 social heat。holder beneficial-owner identity 與 YAOZI main-cost formula 繼續 unavailable / unknown；主 DB 仍不自行 migration。MoneyFlow 90d daily peak 在官方 calendar/timezone contract 未公開前保持 missing；liquidity book asymmetry 不升格為 direction signal。`EARLY`、risk-off exact tightening、SMF exact formula 與 Capital Flow 未公開 trigger gate 持續維持 `unknown_unpublished / not_inferred`。

## 後續主要缺口

上游來源：

- Blockscout on-chain provider 已實作且有單頁 live endpoint evidence；仍缺完整 15-day live window + persisted source-run/activity proof
- DEX 更廣資產／pool coverage（ETH 兩個 configured pools 已 live verified）
- beneficial-owner holder / YAOZI main-cost reconstruction（direct-address holder 與 fail-closed EOA quote-cost subset 已完成；公開資料仍不足以做 beneficial-owner / private formula）
- liquidity 目前 OKX/Binance/Bybit/Gate/Coinbase/Bitget 六個 configured venues 均有 live evidence；主 DB v12→v13 尚未執行
- social raw metric provider / persistence 已完成；剩 universe-wide CoinPaprika ID mapping 與 private heat formula
- news ingestion
- Options 第二公開 provider 已補 Deribit BTC inverse book-summary source-run；若要把 Deribit facts materialize 到 `/intel/options`，需要先處理 snapshot source 維度，現階段不升 schema

User-facing surfaces：

- YAOZI private narrative heat / rotation ranking；raw social metric API 已完成，不等同 private heat
- YAOZI private Signals taxonomy mapping、Whistle unread/history
- Watchlist / push / whistle history
- Account / membership / auth / chat（若最後產品需要）

## 既有 evidence snapshot，不要覆寫

- `outputs/yaozi-cohort-2026-09-20-1237.json`
- `outputs/yaozi-signal-surface-sample-2026-09-20-1344.json`
- `outputs/yaozi-candidate-evidence-score-2026-09-20-1344.json`
- `outputs/yaozi-candidate-alignment-2026-09-20-1344.json`
- `outputs/yaozi-recovery-handoff-2026-09-19.md`

語義邊界：

- `candidate_miss` 只表示 captured surface/window 內沒有同 symbol rendered event，不是 false positive。
- alignment 只證明時間先後，不證明 private gate 或 causality。
- Hyperliquid public trade 不等於 smart-wallet classification。
- DEX observed net flow 不等於 whale event。

## 新對話起始指令

可直接貼：

> 接續 YAOZI 開發。先讀 `outputs/yaozi-handoff-2026-09-20.md`、`outputs/yaozi-guide-evidence-baseline-2026-09-21.md`、`outputs/yaozi-official-guide-spec-2026-09-20.md`、`outputs/yaozi-site-surface-inventory-2026-09-20.md`、`outputs/yaozi-parity-matrix-2026-09-20.md`、`outputs/yaozi-social-verification-20260921.json`。不要重掃已完成網站，也不要再次完整爬 Guide，除非目的是檢查改版。CoinPaprika social raw metric schema v14 / writer / read API / source diagnostics 已完成，BTC+ETH bounded live 為 2 runs / 4 metrics / 0 issues；counter 沒有 source timestamp，因此 `social_heat`、`yaozi_heat`、ranking 仍 unknown/null，不以 raw counts 猜 private heat。On-chain provider 仍只有 WBTC raw endpoint/cursor evidence，完整目標日 + 前14日 pagination 尚未驗證或 materialize，Source partial，且不要重試被 runtime safety review 阻擋的相同路徑。主 market-intel DB 未自行升到目前 schema v14，也未寫入 social live facts。holder beneficial-owner / YAOZI main-cost、`EARLY` formula、risk-off exact tightening、Capital Flow private gates 仍 unknown。維持 `unknown_unpublished` 邊界，不猜 YAOZI private formula/taxonomy，不碰 Lot S10 未提交工作。
