# YAOZI Functional Parity Matrix（2026-09-20）

此矩陣用來回答「功能複製到什麼程度」，避免把程式碼裡有 class/function 誤算為完成。

## 1. 計分規則

每個功能域只計以下四項，每項 0 / 0.5 / 1：

- I — Implementation：本地邏輯是否存在。
- S — Source：所需來源是否實際可用／已物化；只有 mock 或 adapter 但沒有 live coverage 只能 partial。
- V — Verification：是否有專屬測試或 deterministic evidence 驗證行為。
- U — Surface：是否已接到 localhost read API / dashboard，可被使用者讀取。

每個功能域滿分 4。此分數衡量本地功能複製，不把「已經研究清楚」本身算成產品完成度。

## 2. Parity matrix

| 功能域 | I | S | V | U | 得分 / 4 | 目前判定 |
|---|---:|---:|---:|---:|---:|---|
| Universe / public market scan | 1 | 1 | 1 | 1 | 4.0 | 已有 OKX/Binance public collection、universe scan、API |
| Feature layer / closed-market data | 1 | 1 | 1 | 1 | 4.0 | features 與 closed-candle read surface 已接；不把 catOS feature 冒充 YAOZI private overlay |
| 14 L2 lights | 0.5 | 0.5 | 1 | 1 | 3.0 | taxonomy 全，已知規則可算；多個 unpublished threshold 保持 disabled |
| Pattern axis | 1 | 0.5 | 1 | 1 | 3.5 | 7 個公開型態已實作；trend reversal 的未公開子條件採 caller-confirmed facts；Alpha+/Alpha 與三個公開 status-label local derivation 已補，缺 facts 保持 MISSING_DATA |
| SMF score / grade | 0.5 | 0.5 | 1 | 1 | 3.0 | grade bands 已做；exact private SMF score 不可還原，score 由 caller supplied |
| FLOW view | 1 | 0.5 | 1 | 1 | 3.5 | 公開 35/15/15/10/10/10/10 與 lifecycle 已做；component live completeness 未滿 |
| MOMENTUM view | 0.5 | 0.5 | 1 | 1 | 3.0 | SMF/L2 materialized；private funnel/ranking 明確未物化 |
| OPPORTUNITY view | 0.5 | 0.5 | 1 | 1 | 3.0 | 55/45×3/risk block reducer 已做；quality formula/source 仍外部提供 |
| RISK view | 1 | 0.5 | 1 | 1 | 3.5 | 60/45/<30×2 + active-pool cooling/hysteresis 已做；未公開的額外時間參數不猜 |
| Cycle / history lifecycle | 1 | 1 | 1 | 1 | 4.0 | cycle、push、journey、timeline、history 已物化 |
| Proof / calibration | 0.75 | 0.5 | 1 | 1 | 3.25 | frozen push、24h、MFE/MAE、baseline fields 已有；完整公開 calibration workflow 仍 partial |
| Capital Flow | 1 | 0.5 | 1 | 1 | 3.5 | Guide 31-kind semantic contract 已 31/31 並接 read API；source-explicit fact 可保存且不推測 private gate。ETH 兩個 GeckoTerminal pools 已 `verified_multi_pool_window`，但上游 source/trigger coverage 仍 partial |
| Dealer profile | 0.5 | 0.5 | 1 | 1 | 3.0 | 三證據軸與 materialization 已有；Blockscout Ethereum address-level top10 holder CHIP 已完成 WETH live verification，另有 fail-closed direct-EOA stablecoin-counterflow cost subset；但 WETH top10 目前 9 contract + 1 paginated EOA，beneficial-owner consolidation / YAOZI holder cost 仍不可得，direction formula/source intentionally unknown/null，因此整體 Source 仍 partial |
| On-chain anomaly hub | 1 | 0.5 | 1 | 1 | 3.5 | `catos.market_onchain` 已接 Blockscout Ethereum token-transfer provider、caller-supplied 24h boundary、14-day baseline completeness gate、bounded cursor/page budget 與 fail-closed persistence；WBTC public endpoint 已有 keyless HTTP 200 + live cursor/payload evidence，但完整 15-day live window 尚未穿透／materialize，因此 Source 只計 partial |
| Single-coin K-line workbench | 1 | 0.75 | 1 | 1 | 3.75 | 15m / 30m / 1h / 4h / 1d closed OHLCV reader、HTTP 與 detail Dashboard 已接；另有明示非等價的 7d/30d closed-candle cost proxy。真正 holder cost / private overlays/markers 仍不猜 |
| Liquidity / ±2% spot depth | 1 | 1 | 1 | 1 | 4.0 | OKX + Binance + Bybit + Gate + Coinbase + Bitget spot orderbook adapter、Decimal ±2% depth、lower-bound coverage、v13 persistence、API/dashboard 已完成；六個 configured venues 均有 bounded direct live evidence |
| Narrative / sector rotation | 0.75 | 0.75 | 1 | 1 | 3.5 | CoinGecko categories + trending-category membership 已接；CoinPaprika raw social counts 已有 schema v14 persistence/read API。Universe-wide mapping coverage 已實測 734 active symbols：只有 BTC/ETH 具既有 explicit identity 可 resolved，242 ambiguous / 324 unique-but-unverified / 166 missing；不以 ticker 唯一性猜 mapping。social heat 與 YAOZI 私有 heat/ranking/rotation formula 仍未知，因此不加分 |
| News | 1 | 0.5 | 1 | 1 | 3.5 | CoinDesk RSS revision-preserving ingestion、SQLite、API/dashboard 已接；單一 public feed 不宣稱等於原站完整 news universe |
| Options / Gamma | 1 | 1 | 1 | 1 | 4.0 | OKX public option summary + OI 已接 SQLite/API/dashboard；Deribit BTC inverse book-summary 第二 provider 已完成 direct live 918 items / 0 issues 與 source-run proof，但因 snapshot 無 source 欄，Deribit facts 不混寫既有 OKX read model；signed GEX / dealer sign / YAOZI aggregation 維持 unknown |
| Signals event timeline | 1 | 0.75 | 1 | 1 | 3.75 | unified source-semantic event stream、family/view/time filters、read-only alert routing 與 Dashboard 已完成；YAOZI private family mapping/gate/unread state 仍 unknown |
| Today decision surface | 0.5 | 0.75 | 1 | 1 | 3.25 | materialized aggregate/dashboard 已有；YAOZI private ranking/market phase formula 未還原 |
| Member shell: account/watchlist/push/chat/whistle/auth | 0 | 0 | 0 | 0 | 0 | 已研究清楚 surface，尚未實作 |

總分：73.5 / 88 = **83.5% functional parity**。

這個 83.5% 的含義是：以目前已發現的 YAOZI 功能域，依 implementation/source/verification/surface 四層計分的本地功能完成度。它不是程式碼行數、UI 相似度，也不是 YAOZI 方向預測命中率。

## 3. 已完成度最高的核心

- Public market adapters / universe scan。
- Decimal feature layer。
- 已公開的 known L2 rules 與 5 個主要 bullish patterns。
- FLOW 公開 coefficients 與 FLOW / Opportunity / Risk deterministic lifecycle reducer。
- SMF grade mapping；不冒充 private score formula。
- Cycle、push snapshot、history、journey、timeline。
- Proof core 的 immutable push / 24h MFE/MAE contract。
- Hyperliquid public observation、DEX adapter/coverage contract、ETH 兩個 configured pools 的 live multi-pool verification、public event candidate evidence。
- Capital Flow / Dealer 與 On-chain reducer/source-run materialization；On-chain 已有 Blockscout fixed-host provider adapter 與 completeness gate，但完整 15-day live source window 仍未驗證。
- MoneyFlow Guide public subset：5m / 1h / 4h / 24h coverage-safe DEX→CEX fallback、same-source delta、flow/market-cap ratio、DEX >= USD 1,000 tx reference 與 single-coin Dashboard 已完成；90d daily peak timezone contract 保持 unknown。
- Holder public subset：Blockscout Ethereum token holder adapter、balance-desc/top10 completeness validation、Decimal direct-address concentration 與既有 Dealer CHIP persistence/read surface 已完成；WETH current-v2 bounded live reconstruction 已驗證。custody / vault / pool / bridge 不做 beneficial-owner 合併，holder cost 與 Dealer direction source 仍缺，因此 Dealer 整體 Source 維持 partial。
- OKX/Binance/Bybit/Gate/Coinbase/Bitget public spot orderbook 的 ±2% liquidity observation、coverage/lower-bound contract、SQLite/API/dashboard；六個 configured venues 均已有 direct live source evidence。
- CoinPaprika public social raw-count adapter、schema v14 persistence、read API/source diagnostics、BTC/ETH bounded live evidence，以及 universe-wide `/v1/coins` candidate coverage contract；current 734 active symbols只有 2 個 explicit mapping 可 resolved，其餘 fail closed，不推導 social/YAOZI heat。
- localhost-only read API 與本地 dashboard。

## 4. 主要缺口，依 functional parity 影響分組

### A. 核心 scoring 未知／未做

1. Exact SMF base weights / private formula。
2. L1/L2 private funnel gate、ranking、去重全規則。
3. 多個 L2 light 的 absolute threshold。
4. Opportunity quality 的完整生成公式。
5. Risk Live 若另有未公開的分鐘級 cooling 時間參數，仍維持 unknown；已公開的 active-pool hysteresis 與 <30×2 resolve 已實作。
6. Dealer direction exact formula。

這些若沒有第一方公開證據，應長期維持 `unknown_unpublished`，不可用猜測追求假 parity。

### B. 已公開但本地還能直接補齊

1. Guide-vs-Live 已確認但未公開數值的 Trend reversal 子條件來源 adapter。
2. History 逐筆 flat 分類所需的 source-date timezone contract；目前只版本化 3%→1% 規則，不猜時區。
3. Exit engine 的公開 deterministic subset 已補（ATR adaptive floor、healthy-pullback exemption、-20% peak hard floor、720h stale）；market risk-off exact tightening formula 仍 `unknown_unpublished`，不可自行補值。

這一組不需要破解 private formula，可以直接依公開 Guide 開發。

### Guide 已顯示但規則仍未公開

- `EARLY` 已在 2026-09-21 Guide 生命線 UI 顯示，但同頁沒有獨立 scoring / lifecycle formula；維持 `unknown_unpublished`，不計成可直接實作缺口。

### C. 上游 source coverage

1. On-chain Blockscout provider 已完成 implementation 與單頁 live endpoint evidence；下一步是取得一個完整「目標日 + 前 14 日」live window 並 materialize source-run/activity，才能把 Source 從 partial 升為 full。
2. DEX 更廣資產／pool coverage；`ETH-USDT-SWAP` 的兩個 Ethereum WETH pools 已完成真實 upstream + multi-pool identity verification，但尚不能外推成全市場 DEX coverage。
3. Beneficial-owner holder / holder-cost reconstruction：direct-EOA 同交易 stablecoin counterflow 的窄子集已完成，但不代表 beneficial-owner 或 YAOZI main-cost reconstruction。
4. Liquidity configured coverage 已擴至 OKX/Binance/Bybit/Gate/Coinbase/Bitget 並具 direct live evidence；若再擴 venue，屬 breadth enhancement。主 DB v12→v13 尚未執行，因此不宣稱 live liquidity 已 materialize 到主 DB。
5. Social universe-wide ID candidate coverage 已完成，但公開資料只足以驗證 BTC/ETH 既有 explicit mapping；其餘 732 symbols 缺可安全 cross-provider identity。後續缺口是新增 explicit identity evidence 與 YAOZI private narrative heat/rotation formula。
6. News ingestion。
7. Options 第二公開 provider 已補 Deribit BTC inverse book-summary；後續缺口改為其他 family coverage，以及若要將 Deribit facts materialize 到 `/intel/options`，需先定義 snapshot source 維度。本輪不升 schema、不把不同 venue facts 合併。

### D. User-facing functional surfaces

1. Social raw metric API 已可讀；universe-wide candidate coverage 已有，但只有 2/734 可安全 resolved。若要視為完整 product coverage，仍需補足可驗證的 explicit CoinPaprika asset identity。YAOZI private social heat / rotation rank 仍不可由 raw counts 推導。
2. YAOZI private event-family/view mapping、Whistle unread/history state；catOS source-semantic filters 與 read-only alert routing 已完成，不猜私有映射。
3. Watchlist / push / whistle history。
4. Account / membership / auth / chat，如最終產品仍需要這層。

## 5. Evidence boundaries

- `candidate_miss` 只代表 captured surface/window 內沒有同 symbol rendered event，不是 false positive。
- Offline alignment 只證明時間先後，不證明 private gate 或 causality。
- Hyperliquid public trades 不等於 smart-wallet classification。
- DEX observed net flow 不等於 whale event，除非 exact gate 已公開且 source coverage 被證明完整。
- Dealer direction score 目前保持 missing，符合公開證據邊界。
- Narrative / sectors / public attention / News / Options 均已有 materialized read surface；attention 只代表 CoinGecko trending-category membership。另有獨立 CoinPaprika social raw-count read surface，但不保存／推導 source rank、social heat 或 YAOZI heat；Options 只呈現 OKX raw Greeks + OI，`signed_gex`、dealer sign 與 YAOZI Gamma aggregation 仍是 `unknown_unpublished`。
- Liquidity 的 `complete_2pct` 只代表該 venue 回傳 book 已跨過 mid ±2% boundary；未跨 boundary 時只回 lower bound。每 venue asymmetry 只有兩側都完整時才 materialize，且只描述厚度，不是方向訊號。
- MoneyFlow 每個 horizon 都獨立做 coverage proof；1h DEX proof 不可外推到 4h / 24h。CEX fallback 必須由 complete trade windows 無縫覆蓋；90d daily peak 因 source calendar/timezone 未公開維持 missing。此 slice 沒有新增 scored functional-domain row 或 live provider，因此總分維持 72.25 / 88 = 82.1%。
- Holder top10 現在只表示 EVM direct-address balance share，不表示 beneficial owner。Blockscout adapter 的 deterministic tests 與 WETH current-v2 live reconstruction 都已完成；`catos-direct-address-stablecoin-cost-v1` 只在完整 EOA history、無 target outflow、同交易單一 USDT/USDC direct net spend 且 current balance 可完全解釋時輸出 cost reference。WETH top10 live probe 為 9 contract + 1 history-paginated EOA，因此沒有可宣稱的 top10 holder cost。Dealer profile 仍缺 beneficial-owner aggregation、YAOZI main-cost 與 private direction source/formula，整體 Source 維持 partial；本切片不改總分，仍為 72.75 / 88 = 82.7%。
- Liquidity configured source coverage 已從 OKX/Binance 擴為 OKX/Binance/Bybit/Gate，四個來源分別完成 fixed public GET + parser live verification。Liquidity Source 因此由 0.5 升為 1.0；總分增加 0.5 至 72.75 / 88 = 82.7%。當次 orderbooks 均未跨滿 ±2% boundary，所以仍只保存 lower-bound observation，不冒充完整 depth。
- Coinbase/Bitget venue expansion 再把 configured source breadth 擴為六個；兩者 fixed public GET + parser 均完成 bounded live verification。Liquidity Source 原已為 1.0，因此這一片不再加分，總分維持 72.75 / 88 = 82.7%。Coinbase live probe 只有 bid 側跨 -2%，Bitget 兩側都未跨，整體均維持 partial coverage。
- `/intel/source-coverage` 只診斷已持久化 source runs / venue snapshots / coverage proof；不依 wall clock 判定 freshness，也不從歷史成功 run 推論目前 provider live，因此不因新增 diagnostics 提高 Source 分數。
- Blockscout on-chain provider slice：新增 `catos-blockscout-token-outgoing-address-v1`，固定 Ethereum token-transfer endpoint、token contract scope、caller-supplied 24h day boundary、前 14 個完整日 baseline、cursor/page budget、mint/self-transfer 排除與 partial fail-closed。deterministic focused 72/72、全部 `test_market*.py` 192/192、`py_compile` / scoped `diff --check` 通過。WBTC live raw GET 已驗證 HTTP 200、50 items、`block_number/index` cursor 與 timestamp/token payload；但單頁只覆蓋數分鐘且 adapter 的完整 live collection 尚未通過 runtime safety review，因此沒有 15-day completeness 或主 DB materialization claim。On-chain I 0.75→1、Source 0→0.5，總分 +0.75 至 73.5 / 88 = 83.5%。

## 6. 下一個可執行切片

先做已公開但本地缺少的規則，不碰 private unknown：

1. Alpha+ / Alpha、status labels 與 Options/Gamma raw public facts 已完成 materialization/read surface。
2. Multi-venue liquidity 的 OKX/Binance/Bybit/Gate/Coinbase/Bitget implementation + direct live verification 已完成；後續不再以 venue breadth 作高優先工作，且仍不把 book asymmetry 升格為 private signal。
3. MoneyFlow 5m / 1h / 4h / 24h deterministic fallback 已完成；90d daily peak 等待 source calendar/timezone contract，不自行定義日界線。
4. Holder / cost reconstruction 已有 verified direct-address holder source與 fail-closed direct-EOA quote-cost subset；beneficial-owner aggregation 與 YAOZI main-cost 仍缺，7d/30d closed-candle cost reference 只能維持明示 proxy。
5. Sector public facts + trending-category attention 已完成；CoinPaprika raw social metric provider / persistence / read API、BTC/ETH live proof與 universe-wide fail-closed mapping coverage 已完成。current 734 active symbols只有 BTC/ETH resolved，其餘需新的 explicit identity evidence；private heat formula 仍 unknown。Options 不推導 private signed GEX。
6. On-chain provider implementation 已完成；下一個 source 驗收只做完整 15-day live coverage/materialization，不改 caller-supplied 日界，也不把 direct transfer-from address 擴張解讀成 beneficial owner/whale identity。
7. unknown_unpublished 的私有 funnel、SMF base weights、Dealer direction、Gamma aggregation、未公開 threshold 繼續保持 null/disabled，不為提高百分比硬猜。
