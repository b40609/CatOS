# YAOZI 官方 Guide 規格摘要（2026-09-20）

本文件只整理 YAOZI 第一方 Guide 與登入後可見頁面中已公開的功能語義。目的為功能／資料語義重建，不複製原站文案或畫面。動態價格、即時名單、事件數、命中率與時間戳只視為當下快照，不列為固定規格。

2026-09-21 已重新完整讀取 authenticated rendered `/guide` 的 33 個正式內容 anchor，並建立可交接證據基線：`outputs/yaozi-guide-evidence-baseline-2026-09-21.md`。未來 session 應先讀該 baseline，不需為了恢復上下文再次完整爬站；只有檢查網站改版時才重爬並建立新日期版本。

## 1. 產品定位與總流程

- YAOZI 的角色是全市場候選篩選與風險提示層，不是自動交易策略，也不是方向預測器。
- 主要宇宙是 Binance 永續合約全市場，約每 60 秒掃描一次。
- 首頁公開的收斂流程為：來源層全市場 → L1 候選池（上限約 200）→ L2 多訊號交叉（上限約 50）→ 五視角決策層（焦點約 20）。
- L1 公開語義包含多來源合併、市值／動能／活躍度，以及排除穩定幣、極端延伸與部分孤證標的；精確完整 gate 未全部公開。
- L2 強調跨來源、跨訊號家族交叉，同一現象不可重複灌分。
- Guide 將系統拆為篩選層、資料層、復盤層。評分與觀測資料必須區隔，不應把 observation-only 資料回灌成已驗證 edge。

## 2. 五視角與 History

### 2.1 FLOW／先行

FLOW 是點火前資金蓄勢視角，採 5 分鐘級資金速度概念。公開公式：

- OI velocity：35
- taker：15
- top-trader LSR slope：15
- OI quadrant：10
- consolidation：10
- capital cycle：10
- momentum tilt：10

公開狀態門檻：

- score >= 70：ignition
- 50 到 69：accumulation
- score < 35 連續 3 次：flow faded／退出

Guide 明確說明 FLOW 描述點火前狀態，不等於看漲預測。

### 2.2 EARLY／早期

- 2026-09-21 的 Guide 生命線 UI 明確顯示 `EARLY`。
- 但同一份 Guide 的「五視角評分定義」沒有提供 EARLY 的獨立公式、threshold 或 lifecycle gate。
- 因此目前只把 `EARLY` 視為 `official_guide_label`；exact derivation 維持 `unknown_unpublished`，不可把 FLOW 或其他視角規則直接複製過去。

### 2.3 MOMENTUM／異動

- 沒有獨立 Momentum score。
- 直接依 SMF、14 個 L2 lights、funnel 與 cycle 狀態組成異動視角。
- 已知 private funnel gate 尚未完整公開，因此不能自行補一個 Momentum 綜合分。

### 2.4 OPPORTUNITY／機會

- 核心是延續品質 quality，不是方向本身。
- quality >= 55：可進機會池。
- quality < 45 連續 3 次：結束。
- risk >= 60：風險優先，阻擋機會入池。
- Live 頁另有排序／呈現偏好，例如平進場優先；這類排序不等同 SMF 本身。

### 2.5 RISK／風險

- bearish risk >= 60：高風險並可觸發推送。
- bearish risk >= 45：watch／入池。
- bearish risk < 30 連續 2 次：risk resolved。
- Live 另觀察到 cooling／hysteresis：低於 45 先進降溫狀態，真正移除需要更低風險並維持一段時間；因此不可把風險池實作成單一 threshold 的瞬間移除。

### 2.6 HISTORY／歷史

- 保存同幣多輪 cycle，而不是只保留目前一輪。
- Guide 與 Live 會區分推送後曾到達的 MFE 捕獲能力與一路持有到 exit 的 realized 結果。
- 2026-05-08 起 flat 判定門檻由 3% 改為 1%，跨日期比較需保留版本語意。

## 3. SMF 與兩軸模型

SMF 是主力資金聚合分，範圍 -100 到 +100：

| Grade | 公開範圍 | 語意 |
|---|---:|---|
| S | >= +50 | 高 beta 看多／強流入 |
| A | +20 到 +49 | 穩健看多／流入 |
| B | -20 到 +19 | 中性 |
| C | -49 到 -20 | 弱看空／弱流出 |
| D | <= -50 | 看空／強流出 |

兩軸模型：

- 資金軸：SMF。
- 型態軸：盤面結構與行為型態。
- 跨軸精選：型態與資金同時達標的稀有標籤。
- Direction badge 的 -100 到 +100 是另一個 observation-only composite，不能與 SMF 混用。

仍未公開：SMF 底層所有 feature 的精確 base weights、完整合成式、部分 dynamic adjustment 細節。Live 單幣頁公開過 SMF v4 layer、regime multiplier、每日權重調整與 blacklist 機制，但不足以還原精確 base formula。

## 4. 跨軸精選與型態

### 4.1 神級

同時滿足 resonance >= 3、quality >= 80、24h hits >= 4、push 後最大漲幅 >= 5%。

### 4.2 Alpha+ / Alpha 跨軸精選

- Alpha+：pattern strength >= 75、resonance >= 3、bullish、SMF 不可為 C/D。
- Alpha：pattern strength >= 60、resonance >= 2、bullish、SMF 不可為 D。

Guide 也保留歷史語意的 Alpha+ = SMF S、Alpha = SMF A 資金軸別名，顯示層已合併以避免重複。實作時需把跨軸精選與舊資金軸別名分開建模。

### 4.3 已公開型態條件

| 型態 | 公開條件摘要 |
|---|---|
| Short squeeze candidate | 24h >= +5%、OI 4h >= +10%、OI 1h >= +3%、沒有 whale exit，且 trend active／funding flip／extreme-long 任一成立 |
| Coil breakout | 15m volatility percentile < 50、OI 5m >= +1.5%、OI 1h >= +2.5%、1h price 位於 -1% 到 +2%，且 trend active 或 funding flip |
| Preheat | OI 1h >= +2%、OI 5m >= +1%、1h price +1.5% 到 +6%、24h -5% 到 +10%、沒有 whale exit，且 5m OI 速度大於 1h 平均速度 |
| Ambush | 15m volatility percentile < 35、OI 1h >= +2%、1h price 絕對變化 < 1.5%、24h -3% 到 +3% |
| FOMO | 24h >= +15% 且 24h volume >= USD 1,000,000，或 Capital Flow FOMO event |
| Trend reversal | 1h volatility 進入歷史高波動區、trend strength >= 25 且下降、方向力條件成立、24h 尚為漲、沒有前置多頭加持 |
| Distribution | whale exit，或 behavior 屬派發／減倉／出貨等同義行為 |

Guide 另公開狀態標籤，包括中性觀望、砸盤注意、新候選等。這些不是新的型態預測器，而是候選當下狀態描述。

2026-09-21 current Guide 已直接公開三個 status label derivation：

- `OBSERVE`：SMF B 且沒有其他細分 pattern。
- `DUMP_WARNING`：SMF D，或鏈上 distribution/whale exit，或 24h <= -10%，或 behavior=distribution + SMF <= C + 24h <= -5%。
- `NEW_CANDIDATE`：首次入池 < 6h 且沒有其他 label。

這三條已不是 `unknown_unpublished`。目前 CatOS status-label persistence 已有，但 derivation 還只接受 caller/source-explicit state，尚未從本地 facts 重建。

## 5. 14 個 L2 lights

公開 taxonomy：共振命中、埋伏、吸籌、熱度、動能、強動能、資費轉負、OI 暴衝、極端做多、鯨魚進場、鯨魚撤離、團隊出貨、蓄力突破、純動能。

已公開的明確門檻包含：

- 動能：24h 絕對漲跌幅 >= 10%。
- 強動能：24h 絕對漲跌幅 >= 25%。
- 資費轉負：funding 由正翻負且 OI 上升。
- 團隊出貨：非交易所地址到交易所、單筆 >= USD 500,000，同幣 24h 去重。
- 純動能：24h 漲幅 >= 10%、market cap < USD 300,000,000、24h volume >= USD 5,000,000。

其餘若 Guide 只描述語意而未給完整 absolute threshold，仍標為 `unknown_unpublished`，不得用主觀值補齊。

## 6. Cycle、退場與持有建議

異動視角退出採訊號優先 + 波動率自適應：

- adaptive floor = clamp(8 × ATR%, 8%, 22%)。
- peak hard floor = 自高點 -20%。
- stale = 720h 未再被掃到。
- 健康回調可能豁免一般價格底。
- 市場 risk-off 可收緊退出判斷，但精確完整調節式未公開。

leading exit reasons 包含 CVD divergence、OI silent decline、funding flipped、top-trader LSR long reduction、price-OI bearish divergence、SMF turns short、risk resolved。

reactive exit reasons 包含 behavior distribution/reduction、structure broken/dump topping、sustained dump、tag transition、MFE/day-high/entry/peak drawdown、stale dropped、momentum faded、flow faded/data gone、funnel collapsed、superseded by risk、quality dropped。

持有建議的續抱／觀察／減倉／退場是對上述 evidence 的摘要，不應另造一套與 lifecycle 分離的帳本。

## 7. Capital Flow

- Guide 列出 31 種 Capital Flow event kind，分為流入、流出、cycle lifecycle、結構／資料品質等語意群。
- 這些事件是 display-only / observation-only，不直接進 SMF。
- 單幣右側 MoneyFlowTable 顯示多時間窗淨流、對前一同長窗口變化、資金市值比等。
- 有 DEX 資料時，可顯示大額 swap 與鏈上 transaction reference；無 DEX 時可退回 CEX taker 口徑。
- Live Guide 說明 DEX 逐筆顯示門檻為單筆至少 USD 1,000；這是顯示規格，不等於 whale signal gate。

## 8. 單幣 K 線工作台

時間框架：15m、30m、1h、4h、1d。

主圖 overlays：EMA21、EMA55、VWAP、7d cost、30d cost、historical large trades、volume-doji、divergence markers。

下方 panels：taker directional momentum、CVD overlay、whale OI、venue concentration。Guide 對 concentration 的可見警戒值為 > 66%。

Direction badge 由 OI × price、CVD、taker、concentration、divergence 組成啟發式 composite，範圍 -100 到 +100。它是 observation-only，不進 SMF，也不是 forward-validated directional edge。

右側信任分層中，cycle tracking 與 latest L2 lights 是評分主軸；Capital Flow、Dealer summary、event timeline、onchain volume badge、MoneyFlowTable 為觀測／紀錄層。

## 9. Dealer／莊家檔案

- Live 使用 `op_v1`。
- 核心證據系統可拆為持倉、資金流、籌碼三組 coverage；Guide 同時提及 dealer events 作為第四類摘要內容。
- UI 會顯示類似 n/3 軸有據的三證據系統 coverage。
- Dealer direction reading 是 observation-only，不進 SMF。
- 精確 Dealer direction 合成公式仍未公開，必須保留 null/unknown，而不是自造方向分。

## 10. On-chain Hub

來源註記：本節的 `FLAGGED/ELEVATED/Plateau` 3×/2×/1.5× reducer 門檻來自先前第一方登入後 live on-chain surface 研究，屬 `official_live_surface`；2026-09-21 current `/guide` 文字直接公開的是 `distinct outgoing address count vs baseline -> addr_ratio ×`、volatility-leading / direction-NO-GO 語義，沒有直接列出 `FLAGGED/ELEVATED` 名稱與上述 numeric gates。

核心訊號是 token 地址活動放量，用於提醒後續波動可能擴大，不代表方向。

- FLAGGED：live ratio >= 3×，distinct outgoing addresses >= 5，baseline >= 7 完整日。
- ELEVATED：ratio >= 2×、未通過 FLAGGED 三閘。
- Plateau：事件進入後改採事件前錨定 baseline，進入時 >= 3×，續留約 >= 1.5×。
- Research sample：只作研究觀察，不進正式上下榜與評分。

同一 token 多鏈 ratio 各自獨立，不相加。Live 24h 與完整日口徑分開呈現。

## 11. 市場／Narrative

Guide 公開四個傳統分頁：rotation、narrative map、sectors、news；Live 目前另有 Options/Gamma，第五 tab 屬 Guide-vs-Live 差異。

- Narrative map 是被市場注意的程度／位置，不是方向預測。
- Risk map 與 narrative heat 分離，同幣可同時很熱又很危險。
- p80 / p60 是當下 peer percentile reference，不是固定漲跌門檻。
- sector rotation 的 relative strength / momentum 採標準化位置，不可把 110 解讀為強 10%。
- Guide 明確說明 rotation bubble 的歷史移動沒有被證明能預測後續 24h 方向。
- Live 研究證據顯示 Risk map 排名以 local bearish risk 為主，外部 evidence 是展示／佐證，不直接加分。

## 12. 市場階段

短期五態：順勢漲、漲勢衰竭、分化、跌勢衰竭、順勢跌。

市場階段是 reference layer，用於調整使用者對單幣訊號的信任程度；Guide 明確說明目前不直接改單幣評分。

## 13. Signals 主頁

- Live 約 30 秒更新。
- 是策略／系統事件的事件流，不是下單指令。
- 可按視角、時間窗與 event family 篩選。
- Live 已見 event family 包含 SMF grade transition、risk、onchain、market direction、lifecycle、flow 等。
- 事件密度本身不代表 edge 變強。

## 14. Proof／公開體檢

公開方法論要求：push 前先凍結 snapshot、固定 24h outcome、同時保存 MFE/MAE、對照全市場 baseline、再做 volatility-matched baseline，並保留失敗與漏抓以避免 survivor bias。

站方公開結論是：系統擅長把全市場收斂為後續可能大幅波動的候選，但沒有證明能在控制波動與大盤後穩定預測 24h 漲跌方向。

## 15. Account、通知、Chat 與警哨

帳號頁公開功能包含會員權限差異、watchlist 與 watchlist push、browser notification、提示音、站內通知與歷史提醒、nickname/password/support/Guide/legal/share 等入口。

Chat 可見能力包含線上人數／成員、500 字輸入上限、`$TOKEN` token-link 語法。

警哨 drawer 包含即時／我的觀察／歷史，可依 Today、Narrative、Picks、Risk、On-chain、News 等分類篩選，並有 unread state。

研究期間未執行發訊息、已讀、watchlist、通知或帳號設定變更。

## 16. 已知 Guide-vs-Live 差異

1. Narrative Live 有 Options/Gamma，第五 tab 尚未完整寫進 Guide 的四分頁段落。
2. Risk Live 有 cooling／hysteresis，不能只按 Guide 的單次 threshold 做立即移除。
3. Bullish views 有平進場優先與爆發潛力等排序層，與 SMF 本體不同。
4. History 明確拆分 MFE hit-rate 與 hold-until-exit realized result。
5. Single-coin Live 公開比 Guide 更多的 SMF v4 layer／regime／weight adjustment／blacklist 說明。
6. Dealer Guide 同時使用四類摘要與 n/3 evidence axes 描述，實作時需保留兩個不同概念。

## 17. `unknown_unpublished` 清單

以下仍不可宣稱已完全複製：

1. SMF exact base weights 與完整 private score formula。
2. L1/L2 funnel 的完整 private candidate gate、去重與 ranking formula。
3. 埋伏 light、吸籌 light、OI 暴衝、極端做多、鯨魚進出等部分 absolute threshold。
4. Narrative 外部 heat leaderboard 的完整 vendor／修正公式。
5. Dealer final direction score 精確公式。
6. `/onchain/forensics/{symbol}/full` 的完整 private schema 與 provider mapping。
7. Admin `/reflection` 的完整後台 policy／調權介面。
8. `EARLY` 視角的獨立 scoring / lifecycle gate；Guide 目前只有 label，沒有 deterministic formula。

未知欄位一律維持 missing／unknown，不轉為 0，也不以自訂值冒充 YAOZI 原規則。
