# YAOZI Guide Evidence Baseline — 2026-09-21

用途：把本次 authenticated `/guide` 完整掃描固化成可交接的第一方規格基線，避免換新對話後依賴聊天記憶或重新爬站。

來源：`https://yaozi.yalgo.io/guide`。本次讀取的是登入後 rendered Guide；只保存功能語義、規則、門檻、頁面 anchor 與公開驗證邊界，不保存帳號、密碼、cookie、token 或其他會員識別資料。

狀態標記：

- `official_guide`：目前 Guide 直接公開。
- `official_live_surface`：第一方登入後頁面公開，但不是本次 `/guide` 文字直接證明。
- `implemented`：CatOS 已有 deterministic local rule / materialization。
- `partial`：taxonomy 或部分規則已做，但 source、公式或 derivation 尚未完整。
- `missing`：Guide 已公開、CatOS 尚未實作。
- `unknown_unpublished`：第一方仍未公開足夠規則，不猜。

## 1. 完整章節 coverage

本次 `/guide` DOM 共有 33 個正式內容 anchor，全部讀取：

`m-what`, `m-views`, `m-today`, `m-hold`, `m-exit`, `m-evidence`, `m-pages`, `m-narrative`, `m-account`, `m-disclaimer`, `m-score`, `s-axis`, `s-grade`, `s-views`, `s-signals`, `s-tags`, `s-events`, `s-exits`, `s-where`, `m-glossary`, `m-kline`, `k-toolbar`, `k-overlay`, `k-panels`, `k-sidebar`, `k-direction`, `i-badge`, `i-mnemonic`, `i-timeframe`, `i-oiprice`, `i-cvdprice`, `i-truth`, `i-redline`。

目前 Guide 的生命線 UI 顯示 `FLOW / EARLY / MOMENTUM / OPPORTUNITY / RISK / HISTORY`。但評分章節只公開 FLOW、MOMENTUM、OPPORTUNITY、RISK 的 deterministic 定義；`EARLY` 沒有獨立公式或 gate，因此 `EARLY exact rule = unknown_unpublished`，不可自行把 FLOW 或其他 view 規則複製過去。

## 2. 產品定位與驗證紅線

| 規則 | 第一方狀態 | CatOS 狀態 |
|---|---|---|
| YAOZI 是市場 screener / research layer，不是自動交易策略 | official_guide | implemented boundary |
| 三層架構：篩選層、資料層、復盤層 | official_guide | partial |
| 系統價值主要是收斂候選與未來大幅波動篩選，不宣稱控制波動與大盤後仍有 24h 方向預測力 | official_guide | implemented boundary |
| observation/reference layer 不應冒充 validated scoring edge | official_guide | implemented boundary |

Guide 公開體檢說明使用 62,578 筆樣本做過方向能力檢定；這是站方公開研究敘述，不應被 CatOS 轉寫成自己的驗證結果。

## 3. 視角與 lifecycle 規則

| 視角 / 規則 | 公開規格 | CatOS |
|---|---|---|
| FLOW score | OI speed×35 + taker×15 + top-trader LSR slope×15 + OI quadrant×10 + accumulation/compression×10 + capital-flow cycle×10 + momentum tilt×10 | implemented |
| FLOW watch | score >= 50 | implemented |
| FLOW ignition | score >= 70 | implemented |
| FLOW fade | score < 35 連續 3 次 | implemented |
| MOMENTUM | 沒有獨立 score，直接使用 SMF + L2 lights + funnel/cycle evidence | partial；private funnel 未公開 |
| OPPORTUNITY entry | quality >= 55 | implemented |
| OPPORTUNITY exit | quality < 45 連續 3 次 | implemented |
| OPPORTUNITY risk block | bearish risk >= 60 不入機會板 | implemented |
| RISK push | bearish risk >= 60 | implemented |
| RISK watch | bearish risk >= 45 | implemented |
| RISK resolve | bearish risk < 30 連續 2 次 | implemented |
| EARLY | Guide 有名稱，但沒有獨立 deterministic formula | unknown_unpublished |
| HISTORY | 同幣多 cycle，MFE 捕獲與 hold-until-exit realized 要分開看 | implemented / partial calibration |

## 4. 退場與持有規格

- 持有建議 taxonomy：續抱、觀察、減倉、退場。
- 核心模型：signal-led + volatility-adaptive，不是固定百分比停損。
- adaptive drawdown floor：`clamp(8×ATR%, 8%, 22%)`。
- healthy pullback exemption：主力仍流入、SMF 偏多、OI 上升時可豁免一般價格底。
- peak hard exit：自高點 -20%。
- stale：720h 未再被掃到則 stale exit。
- market risk-off：可收緊退場門檻；精確調整式未公開。

目前 CatOS cycle/history 與 exit reason persistence 已存在；2026-09-21 已補公開且 deterministic 的 exit subset：adaptive drawdown floor、healthy-pullback exemption、-20% peak hard exit、720h stale 與 leading-signal exit。market risk-off 的 exact tightening adjustment 仍未公開，因此依賴該未知調整幅度的 case 保持 `MISSING_DATA`；不可把這個 subset 宣稱為完整私有 exit engine。

## 5. SMF 與兩軸模型

SMF 聚合範圍：-100 到 +100。

| Grade | Guide 範圍 | CatOS |
|---|---:|---|
| S | >= +50 | implemented |
| A | +20 到 +49 | implemented |
| B | -20 到 +19 | implemented |
| C | -49 到 -20 | implemented |
| D | <= -50 | implemented |

Guide 明確區分 S 與 A：S 是較高 beta 的多方資金狀態，A 偏穩健；不可把 S 解讀為單純「更高級的 A」。SMF exact base weights / complete score formula 仍為 `unknown_unpublished`，CatOS 目前只接受外部 score 並做 grade mapping。

## 6. 神級、Alpha+ / Alpha 與型態

### 神級

四條件同時成立：resonance >= 3、quality >= 80、24h hits >= 4、push 後 max gain >= 5%。

### Cross-axis 精選

- Alpha+：pattern strength >= 75、resonance >= 3、bullish、SMF 不可為 C/D。
- Alpha：pattern strength >= 60、resonance >= 2、bullish、SMF 不可為 D。

以上 CatOS 已 implemented。

### Legacy 資金軸別名

- Alpha+ display alias：SMF >= +50，或 accumulation score >= 50 + behavior=accumulation/build-up + 24h gain >= 10% + funnel score >= 80。
- Alpha display alias：SMF +20 到 +49，或 behavior=accumulation/build-up + accumulation score >= 30 + 24h gain < 15%。

這組是舊資金軸顯示語義，與 cross-axis Alpha+/Alpha 不可混用。完整 legacy second-branch source completeness 仍 partial。

### 七個型態

| Pattern | Guide 公開規則 | CatOS |
|---|---|---|
| Short squeeze candidate | 24h >= +5%、OI 4h >= +10%、OI 1h >= +3%、無 whale exit，且 trend / funding flip / extreme-long 任一成立 | implemented |
| Coil breakout | 15m volatility percentile < 50、OI 5m >= +1.5%、OI 1h >= +2.5%、1h price -1% 到 +2%，且 trend 或 funding flip | implemented |
| Preheat | OI 1h >= +2%、OI 5m >= +1%、1h price +1.5% 到 +6%、24h -5% 到 +10%、無 whale exit、5m OI speed > 1h average speed | implemented |
| Ambush | 15m volatility percentile < 35、OI 1h >= +2%、abs(1h price) < 1.5%、24h -3% 到 +3% | implemented |
| FOMO | 24h move >= 15% + 24h volume >= USD 1m，或 capital-flow FOMO event；舊單一標籤路徑 >=25% + resonance >=30 | implemented main pattern branch |
| Trend reversal | 1h volatility 歷史前 15%、trend strength >=25 且連續下降、bullish directional force > bearish、24h 仍正、無前置 bullish support | partial；部分 source facts caller-confirmed |
| Distribution | whale exit，或 behavior ∈ 派發/減倉/分發/出貨/distribution/decay | implemented |

## 7. 狀態標籤

Guide 本次已把 derivation rule 直接公開：

- `OBSERVE`：SMF B 且無其他細分 pattern。
- `DUMP_WARNING`：SMF D，或鏈上 distribution/whale exit，或 24h <= -10%，或 behavior=distribution + SMF <= C + 24h <= -5%。
- `NEW_CANDIDATE`：首次入池 < 6h 且無其他 label。

CatOS `status_label_snapshot` 已 materialize；`market_signals.evaluate_status_labels()` 也已用上述公開 facts 做 local deterministic derivation，並保留 caller/source-explicit override。若 derivation 所需 facts 不完整則回 `MISSING_DATA`，不把 missing 當 false。

## 8. 14 個 `signals_matched` lights

Guide taxonomy：命中、埋伏、吸籌、熱度、動能、強動能、資費轉負、OI 暴衝、極端做多、鯨魚進場、鯨魚撤離、團隊出貨、蓄力突破、純動能。

已公開 deterministic 門檻：

- 動能：24h absolute move >= 10%。
- 強動能：24h absolute move >= 25%。
- 資費轉負：funding 正轉負 + OI 持續上升。
- 團隊出貨：24h 內 non-exchange address → exchange 單筆 >= USD 500k，同 symbol 24h 至多計一次；v7 起不再一票否決，但 signal 保留。
- 純動能：24h gain >= 10% + market cap < USD 300m + daily volume >= USD 5m。
- 熱度來源語義：OKX Square + CoinGecko trending + internal anomaly pool；完整 aggregation threshold 未公開。
- 鯨魚進場：DEX 1h net buy 達門檻且平均單筆夠大；數值未公開。
- 鯨魚撤離：DEX 1h net sell 達門檻；數值未公開。
- OI 暴衝：短期 OI delta 達 strong threshold；數值未公開。

CatOS 已 materialize 14-key taxonomy；公開數值規則可算，其餘維持 `DISABLED_UNKNOWN_THRESHOLD`。

## 9. Capital Flow 31 kinds

Guide 明確說明 CapitalFlowBar / MoneyFlowTable 共 31 種 event kind，且全部 display-only，不進 SMF。

流入類：首次流入、大額流入、持續流入、流入加速、鯨魚買入群、聰明錢吸籌、CEX吸籌、安靜吸籌、Alpha確認、量價FOMO。

流出類：大額流出、鯨魚賣出群、聰明錢派發、持幣減少、資金轉流出、CEX流出。

lifecycle：止盈觸發、移動止盈預警、流入轉弱、退場確認、看跌追蹤開始、看漲追蹤結束、追蹤開始、追蹤結束、循環重置。

structural / quality：數據低信度、單所主導、OI突破、負費率佈局、跨所背離、OI靜默下滑。

CatOS 已把這 31 種 Guide 公開語義固化成 `yaozi-capital-flow-guide-taxonomy-v1`，並接到 `/intel/capital-flow/{symbol}`；31/31 都可作 source-explicit fact 保存。這只代表 semantic coverage 完整，不代表 31 個 trigger gate 已被本地還原；未公開門檻仍不推測，既有 DEX `inflow/outflow` 仍標為 catOS-native observation。

## 10. Exit reason dictionary

Leading：`cvd_divergence`, `oi_silent_decline`, `funding_rate_flipped`, `lsr_long_reduction`, `oi_price_bearish_div`, `smf_short`, `risk_resolved`。

Reactive：`behavior_派發`, `behavior_減倉`, `structure_broken`, `structure_dump_topping`, `sustained_dump`, `tag_transition`, `mfe_drawdown`, `day_high_drawdown`, `entry_drawdown`, `peak_drawdown`, `stale_dropped`, `momentum_faded`, `flow_faded`, `flow_data_gone`, `funnel_collapsed`, `superseded_by_risk`, `quality_dropped`。

這些是第一方公開 taxonomy；CatOS event/lifecycle surface 已能保存部分對應事件，但不是每一個 reason 都已有完整 upstream trigger。

## 11. 市場、Narrative、sector rotation

- Narrative map：資金 + momentum + social heat 的注意力位置；Risk map 分開。
- X 軸：market correlation；Y 軸：signal score。
- p80 breakout / p60 observe 是同儕 percentile ranking，不是方向門檻。
- Sector rotation 軸：relative strength / momentum 都以 100 為標準化中心。
- 典型循環：leading → weakening → lagging → improving，但允許跳格或反轉。
- Bubble size 預設：market-volume-share change；可切 turnover increase / volume / move amplitude。
- Market phase 五態：順勢漲、漲勢衰竭、分化、跌勢衰竭、順勢跌。
- Market phase 是 reference layer，不直接進單幣 score。
- Guide 仍只寫四個 market tabs；Live 已有 Options/Gamma，屬 Guide-vs-Live 差異。

CatOS Narrative/Sectors public facts 已 materialize；YAOZI private heat/ranking/rotation formula 仍 `unknown_unpublished`。

## 12. K-line / indicator contract

- Timeframes：15m / 30m / 1h / 4h / 1d。
- Price structure：7d window + 4h bars 對機會/風險；48h 短期對 Momentum/FLOW。
- Main overlays：EMA21、EMA55、VWAP、7d cost、30d cost、historical large trades、volume-standoff Doji、divergence markers。
- Panels：taker direction、CVD、whale OI、concentration。
- Binance `/futures/data` 的 taker / concentration 官方歷史約 30d；concentration 另含三交易所 OI snapshot + 約 30d backfill。
- Concentration > 66% 顯示警戒。
- Direction badge：OI×price、CVD、taker、concentration、divergence 合成 -100 到 +100；observation-only，不進 scoring，也不宣稱方向預測 edge。
- OI×price 與 CVD×price 的四象限 / truth-table semantics 均已公開，可作 read-model/reference 說明；完整 badge weights 未公開。

CatOS 已有五週期 closed K-line reader，並新增明示非等價的 `catos-closed-candle-cost-reference-v1`：用同 venue、連續 4h closed candles 做 7d/30d volume-weighted close proxy。另新增 `catos-blockscout-address-holder-v1` 的 Ethereum address-level top10 concentration adapter：只在 balance-desc 順序、前 10 完整性與 total supply 都可驗證時，以 Decimal 輸出 direct-address share，並可 materialize 至 Dealer CHIP。它不合併 custody / vault / bridge / pool 或同 beneficial owner 多地址，因此不宣稱等同 YAOZI 私有 holder reconstruction。2026-09-21 已以 WETH `0xc02a...6cc2` 完成 Blockscout current-v2 bounded live reconstruction：3,348,933 holders、前 10 direct-address share 58.669906871554692593137817787784214245784532916141%，top10 completeness 通過。Holder-cost 另新增 `catos-direct-address-stablecoin-cost-v1` 的窄 public subset：只對完整 bounded EOA history、無 target outflow、且每筆 inbound 同交易存在單一 direct USDT/USDC 淨支出的情況計算 address-level quote cost；其他情況固定 `MISSING_DATA`。WETH top10 live probe 為 9 contract + 1 EOA，唯一 EOA 的 history 超出 bounded page，因此本輪仍沒有可安全宣稱的 WETH top10 cost。真實 beneficial-owner concentration、YAOZI 主力成本與 direction badge weights 仍尚未完整。

CatOS 另新增 `catos-spot-depth-2pct-v1` public liquidity observation：目前支援 OKX、Binance、Bybit、Gate、Coinbase、Bitget spot orderbook，以 Decimal 計算每 venue 的 mid ±2% quote depth。回傳 book 未跨過對應 boundary 時只保留 lower bound，不宣稱完整 depth；asymmetry 僅在 bid/ask 兩側 coverage 都完整時輸出，且固定為 descriptive-only，不轉成 YAOZI direction/SMF。2026-09-21 六個 configured venues 均已有 bounded direct live source evidence；新增 Coinbase 100 levels 與 Bitget 150 levels 皆通過 fixed allowlist transport + parser。Coinbase 當次只有 bid 側跨過 -2%，Bitget 兩側都未跨，因此兩者整體仍是 `partial_boundary_coverage`。主 market-intel DB 仍維持已確認 v12，未宣稱 live liquidity 已 materialize 至主 DB。

## 13. Dealer / on-chain / MoneyFlow observation contract

- Dealer `op_v1`：概念上四類摘要；UI coverage 顯示 `n/3` 三個 evidence systems，分別為 position=CEX derivatives、flow=DEX on-chain、chip=on-chain holdings。Dealer direction 是 observation-only，不進 SMF。
- Guide 的 on-chain badge 語義：distinct outgoing address count 對 baseline，顯示 `addr_ratio ×`。Guide 公開研究敘述為未來 volatility IC +0.145，但方向測試 NO-GO。
- MoneyFlowTable：5m/1h/4h/24h… net flow、對前一同長 window 的 delta、flow/market-cap ratio；有 DEX 時顯示 real swaps >= USD 1,000 並附 tx reference，否則 fallback CEX taker；另顯示 90d window 內單日淨流入峰值。

CatOS 已實作 `yaozi-guide-money-flow-public-v1` read model：5m / 1h / 4h / 24h 各自先檢查 persisted DEX coverage proof 是否完整包住該 horizon，否則只在 complete CEX taker trade windows 能無縫覆蓋整段時 fallback；不把既有 1h DEX proof 延伸成 4h / 24h。current / previous delta 僅在同類 source 與同 quote currency 時輸出，flow/market-cap ratio 維持 Decimal。DEX >= USD 1,000 swap 會附 tx reference；90d 單日峰值因 calendar-day timezone contract 未公開仍保持 missing。`/intel/picks/{symbol}/money-flow` 與 single-coin Dashboard 已接，固定 observation-only / `smf_eligible=false`。

注意：目前 `/guide` 文字沒有直接出現 `FLAGGED/ELEVATED` 的 3×/2×/1.5× gate。既有 `yaozi-official-guide-spec-2026-09-20.md` 中這些 on-chain reducer 門檻來自先前第一方登入後 live surface 研究，應標 `official_live_surface`，不可誤標成這次 current Guide 文字直接證明。

## 14. Guide 與目前 CatOS 的直接缺口

以下不需猜 private formula，且可在後續以 deterministic slice 處理：

1. `EARLY`：Guide 只公開 view label，沒有 formula；維持 `unknown_unpublished`，不可實作猜測版。
2. 31-kind Capital Flow：semantic contract 已補 31/31 並接 read API；上游來源與各 kind 的本地 trigger coverage 仍 partial，未公開 gate 保持 `not_inferred`。
3. Exit engine：adaptive ATR floor、healthy-pullback exemption、-20% peak hard floor、720h stale 已補 deterministic subset；risk-off exact adjustment 仍 unpublished，完整私有 exit engine 仍不可宣稱完成。
4. K-line overlays / holder-cost / concentration：Guide 已公開 surface contract。address-level top10 holder adapter 已完成 deterministic reconstruction 與 WETH live source verification；direct-EOA stablecoin-counterflow cost subset 也已做成 fail-closed contract，但 WETH top10 live evidence 仍 10/10 不具完整 cost coverage。beneficial-owner consolidation 與 YAOZI 主力成本公式未公開，因此 holder cost 仍不可宣稱完成。MoneyFlow DEX-to-CEX fallback 的公開 deterministic subset 已完成；90d daily peak 仍等待官方 calendar/timezone contract，且更廣 DEX/CEX source coverage 仍 partial。

仍不可自行補值：SMF exact score formula、L1/L2 full funnel/ranking/dedup、HEAT exact aggregation threshold、OI_SURGE absolute threshold、whale entry/exit numeric threshold、Dealer final direction formula、direction-badge exact weights、EARLY exact gate。

## 15. Future-session rule

新 session 先讀本檔，再讀：

1. `outputs/yaozi-official-guide-spec-2026-09-20.md`
2. `outputs/yaozi-parity-matrix-2026-09-20.md`
3. `outputs/yaozi-handoff-2026-09-20.md`
4. `outputs/yaozi-site-surface-inventory-2026-09-20.md`

除非目的是確認 YAOZI 是否改版，否則不要再次完整爬 `/guide`。若重爬，應建立新日期 baseline 並做差異比較，禁止覆寫本檔造成規則來源歷史消失。
