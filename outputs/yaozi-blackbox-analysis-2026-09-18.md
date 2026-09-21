# Yaozi × catOS 黑箱對照：第一批同步樣本

採樣窗：2026-09-18 18:09 Asia/Taipei。妖子 Today 顯示更新 18:09:03；catOS public-only scan 物化時間 18:09:50.810。所有精確十進位值在 JSON 樣本中以字串保存，missing 維持 null。

原始結構化樣本：`outputs/yaozi-blackbox-sample-2026-09-18-1809.json`。

## 已確認差異

1. 市場 universe 不同。
   - 妖子 Today：POOL 159、15 picks。
   - catOS：523 個 OKX active USDT-SWAP。
   - 妖子本輪 15 個標的中，catOS 可直接對到 11 個；`META`、`MINIMAX`、`INTW`、`SKHY` 不在目前 catOS OKX universe。
   - 妖子單幣頁明確使用 Binance 合約掛單簿與「USDT 永續」語義，因此若目標是功能 parity，catOS 不能只以 OKX instrument universe 當候選池。這是目前比私有公式更前面的結構性缺口。

2. 妖子的 `SINCE` 不是 24h 漲跌。
   - Today 卡片文字明示「入池以來（首推價 → 現價）」；catOS 現有 Market 欄位是 24h change。
   - 兩者不能直接比較或互相代替。要 parity，必須保留 cycle first-push price / first-push time。

3. SMF 與 Dealer 的缺口是真實資料／公式缺口，不是前端缺欄位。
   - 妖子本輪 Today 幾乎都有 SMF A/B；catOS 同批 11 個可對照標的目前 `smf_grade=null`。
   - 妖子 Dealer 可產生方向讀數；catOS 依既有限制維持 `dealer_direction=null`，未猜私有公式。

4. 妖子 Whale / Capital Flow 的事件層比目前 catOS 豐富。
   - EIGEN 直接出現 `WHALE_BUY_CLUSTER 4 筆 / $87K / 1 wallet`、`WHALE_SELL_CLUSTER`、`MAJOR_OUTFLOW`。
   - ADA 出現 `SMART_WALLET_DISTRIBUTION 4 HL top traders short $3.7M`。
   - ARX 出現 OI breakout、CEX accumulation、single-venue dominance、24h 內幕異動等事件。
   - 因此「whale」不是單一 notional threshold；至少還有 trade cluster、wallet count、top-trader position、venue concentration 等不同事件型別。

## Dealer 初步約束

目前拿到三個可用方程樣本，但還不足以唯一解出權重：

| Symbol | 可見 component | 最終方向 |
| --- | --- | --- |
| ARX | 鏈上籌碼 -80；資金週期 +50；價格-OI -30 | -22 |
| ADA | 資金週期 -60；價格-OI -30 | -28 |
| EIGEN | 資金週期 -60；其他軸有 coverage 但未顯示 component 分數 | -21 |

可排除「把可見 component 直接相加」；也不能只用簡單平均宣稱公式。下一批需要刻意採集正向、負向、缺軸、三軸全滿四種案例，至少 20–30 個 Dealer snapshot，才有資格做權重擬合與殘差檢驗。

## 目前最值得先補的功能

優先順序應調整為：

1. `Universe parity`：Supervisor public-only 同時 materialize OKX + Binance USDT perpetual instrument universe，身份映射到 catOS canonical symbol；仍不接帳戶／交易。
2. `Cycle/SINCE contract`：把首次推送價、首次推送時間、latest push、push count 變成 Today 可直接使用的 materialized contract，不再拿 24h change 冒充。
3. `Whale event taxonomy`：先實作已從妖子畫面確認的 event facts，例如 WHALE_BUY_CLUSTER / WHALE_SELL_CLUSTER / SMART_WALLET_DISTRIBUTION / MAJOR_OUTFLOW；未知門檻仍標 unknown。
4. `Dealer reverse-engineering dataset`：先擴樣，不立刻硬編權重。等樣本能約束公式，再決定是否實作 parity score。

## 第一批結果的實際意義

這次採樣已證明目前最大落差不只有「私有公式」。候選市場來源、cycle 語義與事件 taxonomy 也不同；先補這三個公開可驗證層，會比直接猜 SMF/Dealer 權重更快接近妖子的實際效果。

## 第二批修正：Universe 根因已定位

第二批 observation：`outputs/yaozi-blackbox-sample-2026-09-18-1822.json`。

第一批把 `META / MINIMAX / INTW / SKHY` 記為「不在目前 catOS OKX universe」是現象描述，後續已查到真正原因：這四檔都存在於 OKX public `SWAP` instruments，且均為 `state=live`、`settleCcy=USDT`；OKX 對這類 SWAP 回傳的 `quoteCcy` 是空字串。

catOS 原 collector 同時要求 `quoteCcy == USDT` 與 `settleCcy == USDT`，因此錯誤排除了 OKX SWAP。修正為以 `settleCcy == USDT` 判定 USDT-margined SWAP，仍保留 canonical `*-USDT-SWAP` instId 驗證。

修正後 public-only scan：

- instrument refs：1120
- active symbols：730（原 523）
- materialized symbols：730
- missing market symbols：0
- collection issues：0
- `META / MINIMAX / INTW / SKHY` 四檔全部已 materialize

所以 Universe parity 的下一步不再是「先新增交易所」；先前主要缺口是 catOS 自身 OKX instrument 過濾錯誤。Binance 仍可作第二 venue observation，但不是補這四檔的必要條件。

## 第二批 Dealer / Whale 樣本

新增兩個正向 Dealer sample：

| Symbol | Dealer | Coverage | 可見持倉 / 籌碼 | Whale / flow events |
| --- | --- | --- | --- | --- |
| NEAR | +4 中性、拉升 | 2/3 | L/S 2.71、多 73%、top10 37.5% | WHALE_BUY_CLUSTER 11 筆 / $150K / 9 錢包；SMART_WALLET_ACCUMULATION 3 HL top traders long $41.4M |
| SKHY | +10 中性、蓄勢 | 2/3 | L/S 0.68、多 40%、top10 84.0% | WHALE_BUY_CLUSTER 3 筆 / $32K / 2 錢包；SINGLE_VENUE_DOMINANCE 79.1%；FLOW_FLIP_TO_OUTFLOW $50K → -$25K |

目前 Dealer 已有正向與負向結果，但仍沒有足夠「明示 component 數值」樣本唯一解出私有權重；維持 `unknown`。Whale 事件則再次證明至少包含 cluster、top-trader、venue concentration、flow flip 等不同 gate，不能硬塞成單一 notional threshold。

## 第三批：18:50–18:53 跨時間 / 跨頁面約束

原始結構化樣本：`outputs/yaozi-blackbox-sample-2026-09-18-1853.json`。

Today 在 `UPD 18:50:26` 顯示：POOL 162、CYCLES 160、16 picks；今日焦點 10、撤退警示 3、持有追蹤 3。這一批最重要的新發現，是「同一標的不同頁面的 Dealer snapshot 可能不是同一版本」。

| Symbol | Today card | Detail page | 結論 |
| --- | --- | --- | --- |
| ARX | -14 中性、1/3 軸 | -22 偏空、2/3 軸 | 不可直接當同時刻同版本方程 |
| ADA | -21 偏空、1/3 軸 | -28 偏空、2/3 軸 | 不可直接當同時刻同版本方程 |

所以後續擬合 Dealer 前，資料集必須保留 `surface`、source update time / observed time 或等價 snapshot version；否則把 Today card 與 detail page 混在一起，會把非同步刷新誤判成公式殘差。

同一輪也拿到幾個跨時間穩定性約束：

- ADA：方向觀察層由先前約 +66.7 降到 +58.7，但主力週期仍是「主力撤退」，Dealer 仍 -28。
- ARX：距主力成本由先前約 +29.6% 降到 +27.5%，Dealer 仍 -22；可見 component 仍是鏈上籌碼 -80、資金週期 +50、價格-OI -30。
- INJ：24h 事件 48 → 53、本輪總計 219 → 232、流入分 32 → 63，Dealer 仍固定 +4，且可見 component 仍只有 `fomo +10`。這進一步排除「Dealer 直接由事件數或流入分線性映射」的簡單模型。
- NEAR：Dealer 仍 +4，方向觀察層仍偏空約 -12.8；Today 精確 DEX 顯示 +84,755 USD。

INJ 在 18:53 還出現新的已觀察事件型別 `CONTRACT_IGNITION`，同批事件鏈同時有 `CEX_ACCUMULATION`、`OI_BREAKOUT`、`TOP_TRADER_LONG_BUILD`、`TOP_VS_RETAIL_DIV`。Whale / capital event taxonomy 因此繼續擴張，未知 gate 仍保持 `unknown`。

另有一個 UI 內部刷新節奏證據：INJ 詳情同一張渲染頁一方面顯示「缺 volume 與 OI — 只能 WATCH」，另一方面最新事件鏈已經顯示 `OI1h+8.0%` 與 `CONTRACT_IGNITION`。目前只記為 asynchronous snapshot timing，不解讀成規則或 bug。

### 目前可安全使用的 Dealer 約束

只使用同一 detail surface 的明示 component：

| Symbol | 可見 component | Detail Dealer |
| --- | --- | --- |
| ARX | -80、+50、-30 | -22 |
| ADA | -60、-30 | -28 |
| NEAR | fomo +10 | +4 |
| INJ | fomo +10 | +4 |

`ARX / ADA` 的 Today card 值暫時只用來研究 materialization / refresh semantics，不再拿去解 Dealer 權重。Dealer formula 與 whale thresholds 維持 `unknown`。

## 第四批：19:01–19:04 滾動窗 / materialization 約束

原始結構化樣本：`outputs/yaozi-blackbox-sample-2026-09-18-1904.json`。

Today 在 `UPD 19:01:14` 顯示 POOL 161、CYCLES 159、16 picks；焦點 10、撤退 3、持有 3。相較 18:50，總 picks 不變，但 POOL 162 → 161、CYCLES 160 → 159。AKE 仍在 focus，但 action 由「減倉」切回「觀察」。

這一輪最重要的新約束是：`24h 事件` 明確是滾動窗，不是單調累積計數。

- ARX：24h 事件 25 → 24，但本輪總計 38 → 39；方向 -58.7 → -62.8，Dealer 仍 -22。最新事件窗加入 18:53 的 `SINGLE_VENUE_DOMINANCE`（Binance OI 67.2%）。
- INJ：24h 事件 53 → 52，但本輪總計 232 → 246；流入分仍 63、Dealer 仍 +4、方向仍 +68.9。事件窗仍含 `CONTRACT_IGNITION` 等 18:53 事件。
- NEAR：本輪總計 2585 → 2589，事件窗新增 18:53 的 `SMART_WALLET_ACCUMULATION`；方向 -12.8 → -7.4，但 Dealer 仍 +4。L/S 2.71 → 2.62，多頭占比 73% → 72%。
- ADA：週期、14 個 24h 事件、round total 1、方向 +58.7、Dealer -28 全部穩定；目前渲染摘要把 L/S 顯示為 `—`，因此本輪不沿用上一輪 1.64，保持 missing。

因此後續公式擬合不能把 `24h event count` 或 `round total` 當成直接線性輸入。至少在 ARX / INJ 這兩個跨時間樣本中，這些計數明顯變動時 Dealer 完全不動。

跨頁面差異仍存在：ARX Today card -14 / 1/3，但 detail -22 / 2/3；ADA Today card -21 / 1/3，但 detail -28 / 2/3。這再次確認必須保留 surface + snapshot/materialization version，再談 Dealer 權重。

INJ 的非同步證據也持續存在：同頁仍顯示「缺 volume 與 OI — 只能 WATCH」，但事件鏈已有 `OI1h+8.0%`、`OI_BREAKOUT` 與 `CONTRACT_IGNITION`。目前仍只視為 materialization timing，不把它解讀成規則或 bug。

Dealer formula 與 whale thresholds 維持 `unknown`。

## 第五批：19:11–19:20 同頁 Dealer component 映射

原始結構化樣本：`outputs/yaozi-blackbox-sample-2026-09-18-1920.json`。

Today 在 `UPD 19:11:03` 顯示 POOL 160、CYCLES 158、16 picks；焦點 10、撤退 3、持有 3。這一批刻意改採 detail surface 的明示 Dealer component，避免再把 Today card 與 detail 非同步版本混成同一條方程。

| Symbol | Detail 明示 component | Detail Dealer | Coverage |
| --- | --- | --- | --- |
| INJ | `fomo +10` | `+4` | 2/3 |
| AKE | `fomo +10` | `+4` | 2/3 |
| SKHY | `accumulation +30` | `+10` | 2/3 |
| EIGEN | `markup +50` | `+18` | 2/3 |
| OPEN | `retreat -60` | `-21` | 2/3 |
| VIRTUAL | `retreat -60` | `-21` | 2/3 |

目前得到一組穩定、單調的「可見資金週期 component → 最終 Dealer」對照，但仍不能宣稱公式已解出。理由是 coverage 固定只有 2/3，另一個已覆蓋軸可能有隱藏輸入；ARX、ADA 先前也已證明其他明示 component 能改變結果。因此這組資料只當約束，不硬編權重。

這批還新增三個重要語義約束：

- EIGEN：方向觀察層 `-27` 偏空，但 Dealer `+18`，明示 `markup +50`。所以「方向綜合判讀」與 Dealer 是不同觀測量，不能互相代替。
- VIRTUAL：當下 `撤退分 0`，但資金週期仍是「主力撤退」，Dealer 明示 component 仍是 `retreat -60`，最終 `-21`。因此「當前撤退分」不是 Dealer 資金週期 component 的同義欄位。
- OPEN、VIRTUAL 的 Today card 都是 `-21 / 1/3`，detail 則是 `-21 / 2/3`。分數可以在 coverage 改變時維持不變；coverage 仍需獨立保存，不能由 score 反推。

Whale taxonomy 也得到更強反例。AKE 在同一分鐘同時出現：

- `WHALE_BUY_CLUSTER`：5 筆大單買入 / $101K / 1 wallet。
- `WHALE_SELL_CLUSTER`：5 筆大單賣出 / $101K。
- `MAJOR_OUTFLOW`：netflow -$41K、large sells $101K、5 sells。

所以 whale 事件不能縮成「notional >= X 就是 whale」；至少還有方向聚合、交易筆數、wallet count 與 netflow/event-type gate。未知 threshold 繼續維持 `unknown`。

EIGEN 另觀察到新事件型別 `INFLOW_ACCELERATION`。目前已知 event taxonomy 繼續擴充，但只保存畫面可證實的名稱與 payload，不猜未顯示的 gate。

Dealer formula 與 whale thresholds 維持 `unknown`；下一輪若繼續採樣，優先找 `3/3 coverage`、多 component 同時明示、或 component 相同但 Dealer 不同的反例，資訊增益會比重複抓 2/3 單 component 更高。

## 第六批：21:07–21:09 第三軸缺口定位 + CAP 多 component

原始結構化樣本：`outputs/yaozi-blackbox-sample-2026-09-18-2109.json`。

Today 在 `UPD 21:07:26` 顯示 POOL 155、CYCLES 154、15 picks；焦點 8、撤退 5、持有 2。市場階段已轉為「多空分化」，2H 方向分 `-9`、風險 `4`。

本輪最重要的新樣本是 CAP：

| Symbol | 明示 component | Detail Dealer | Coverage |
| --- | --- | --- | --- |
| CAP | 鏈上籌碼 `-95`；accumulation `+30`；價格-OI 看跌背離 `-30` | `-35` | 2/3 |
| ARX | 鏈上籌碼 `-80`；markup `+50`；價格-OI 看跌背離 `-30` | `-22` | 2/3 |

CAP 與 ARX 現在構成兩組同 surface、同 coverage、同樣具有三個明示 component 的衝突案例。可直接確認「可見 component 不是直接相加成 Dealer」。CAP Today card 與 detail 在本輪都顯示 `-35 / 2/3`，說明跨 surface 並非必然不同步；先前 ARX／ADA 的 mismatch 應視為 materialization timing 問題，而不是固定的頁面公式差異。

資金週期 component 的重複性也變強：

- `accumulation +30 -> Dealer +10`：目前 SKHY、META、KMNO 三個獨立 detail sample 都成立，且皆為 2/3 coverage。
- `markup +50 -> Dealer +18`：目前 EIGEN、COTI 兩個獨立 detail sample 都成立，且皆為 2/3 coverage。
- `fomo +10 -> +4`、`retreat -60 -> -21` 仍維持前批重複結果。

這些值與「可見 component 總和約壓縮成三分之一」在數值上相容，但殘差不固定，且目前所有 detail Dealer 仍只有 2/3 coverage；因此這只能列為候選 transform，不得硬編成公式。

### 第三軸缺口已定位到 1h DEX flow

本輪刻意挑有鏈上 DEX 資料的 META、KMNO、COTI：

- META：24h DEX 淨流顯示 `+$0`，Dealer 仍顯示 `DEX 淨流 1h —`，coverage `2/3`。
- KMNO：24h DEX 淨流 `+$1.08萬`，Dealer 仍顯示 `DEX 淨流 1h —`，coverage `2/3`。
- COTI：24h DEX 淨流 `+$1.02萬`，Dealer 仍顯示 `DEX 淨流 1h —`，coverage `2/3`。

所以「缺第三軸」不是因為整體 DEX 資料不存在，而是 Dealer 要的 `1h` flow input / materialization 缺失。這對 catOS parity 很重要：不能拿 24h DEX netflow 直接補成 Dealer 的 1h 資金流軸，missing 必須維持 missing。

### 新事件與 identity 風險

CAP、COTI 新觀察到 `FIRST_INFLOW`。同時兩者都再次出現 buy cluster、sell cluster 與 outflow 類事件並存，whale / flow taxonomy 仍是多 gate，不可壓成單一 notional threshold。

META 另出現一個需要保留的 identity 警訊：渲染現價約 `690`，主力成本卻是 `0.005470`，頁面直接算出距成本 `+12621850.3%`。目前只保存為畫面事實；在 catOS 使用這類鏈上成本前，必須先做 canonical asset identity / contract identity 驗證，不能只靠 ticker `META` 對應。

目前仍未抓到 `3/3 coverage`。Dealer formula 與 whale thresholds 維持 `unknown`；下一輪應優先找能產生 `DEX 淨流 1h` 的標的或 operator snapshot，因為這比繼續堆 2/3 單 component 樣本更能約束真正聚合公式。

## 第七批：22:44–22:49 Signal DEX 與 Dealer/op_v1 materialization 分離

原始結構化樣本：`outputs/yaozi-blackbox-sample-2026-09-18-2249.json`。

這一輪改從 `/signals` 反向挑已經明確出現「鏈上大單爆發」且帶 1h 鏈上淨買值的標的，再回到各自 `/picks/{symbol}` 的「莊家摘要」比對 `DEX 淨流 1h`。

已直接看到的 signal 1h DEX 例子包括：

| Symbol | Signal 時間 | 1h 大額成交 | Signal 鏈上淨買 |
| --- | --- | ---: | ---: |
| CRV | 22:31 | 5 | -13,961 USD |
| ETH | 17:30 | 21 | +476,100 USD |
| ARK | 16:30 | 37 | -16,632 USD |
| KMNO | 12:30 | 7 | -5,714 USD |
| GENIUS | 10:42 | 34 | +14,997 USD |
| AAPL | 10:42 | 300 | +305 USD |
| GOOGL | 07:42 | 300 | +51 USD |
| AERO | 06:57 | 19 | -60,535 USD |
| CAKE | 06:57 | 20 | -61,299 USD |
| NEAR | 09/17 23:47 | 18 | -1,295 USD |

Dealer/op_v1 同輪掃描結果：

| Symbol | Dealer coverage | `DEX 淨流 1h` |
| --- | --- | --- |
| CRV | 2/3 | — |
| ETH | 2/3 | — |
| ARK | 1/3 | — |
| KMNO | 2/3 | — |
| GENIUS | 2/3 | — |
| AERO | 2/3 | — |
| CAKE | 2/3 | — |
| AAPL | 1/3 | — |
| GOOGL | 1/3 | — |
| NEAR | 2/3 | — |
| JUP | 2/3 | — |

其中 CRV 同頁仍是 `markup +50 -> Dealer +18`，ETH 是 `accumulation +30 -> Dealer +10`；JUP 當下 Dealer `+4`。這些既有 2/3 映射保持一致，但第三軸仍完全沒有可觀察輸入。

因此目前最強、但仍需維持為「證據支持的工程假設」的結論是：`/signals` 的 1h DEX observation 與 Dealer/op_v1 的 `operator_profile.dex_flow.net_flow_h1_usd` 並非同一份即時 materialization。至少在本輪 11 個候選中，signal 層可有非空 1h DEX 值，Dealer 層仍全部 missing。

對 catOS parity 的直接約束：

- signal DEX 與 Dealer DEX 必須分開建模，不能因為 signal 有值就把 Dealer coverage 強制補成 3/3。
- Dealer DEX missing 必須保持 `null` / `—`，不得補 0。
- 不得拿 24h DEX 淨流代替 Dealer 1h 軸。
- 在沒有第一筆 `3/3` Dealer 同頁樣本前，不推導第三軸權重，也不硬編「三分之一壓縮」。
- whale threshold 仍維持 `unknown`；本輪觀察到的 1h 大額成交筆數與淨額只保存為事件事實，不反推 gate。

本輪沒有找到 `3/3`。後續實作應把這個差異當成 contract boundary：signal observation 可以獨立呈現，Dealer/op_v1 只有在自身 DEX snapshot 真正存在時才提高 coverage。
