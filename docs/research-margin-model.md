# 回測保證金與強平模型（第一步：單合約全倉）

2026-11-12 開工前寫成；實作、驗收與實測附在第 6 節。範圍是使用者 2026-11-11 同意的第一步：單合約全倉；每根 K 線用最不利價（多單用最低價、空單用最高價）檢查權益是否跌到維持保證金；跌到就強平、扣強平成本、標記並停止交易；下單時檢查初始保證金，不夠就拒單。

第 2 步（改用標記價格）與第 3 步（多合約共用保證金）不在範圍內。

## 1. 對 OKX 官方文件的核實

查閱日期都是 2026-11-12。說明中心文章與 API 文件是用 curl 抓下原始 HTML 後抽出正文核對，不是摘要。

### 1.1 `GET /api/v5/public/position-tiers` 的參數與回傳欄位

來源：[OKX API 文件 Get position tiers](https://www.okx.com/docs-v5/en/#public-data-rest-api-get-position-tiers)

- 限速 10 次／2 秒，依 IP 計。公開端點，不需金鑰。
- 請求參數：`instType`（必填，`SWAP`）、`tdMode`（必填，`cross` 或 `isolated`）、`instFamily`（SWAP／FUTURES／OPTION 必填，最多 5 個，逗號分隔）、`instId`（SWAP 會被忽略）、`ccy`（只用於全倉 MARGIN）、`tier`（選填）。
- 回傳欄位：`uly`、`instFamily`、`instId`、`tier`、`minSz`、`maxSz`、`mmr`、`imr`、`maxLever`、`optMgnFactor`、`quoteMaxLoan`、`baseMaxLoan`。
- 文件範例的 Python 呼叫用 `uly=`，但參數表裡沒有 `uly`；我們照參數表用 `instFamily`。

2026-11-12 實抓 BTC-USDT-SWAP（`instType=SWAP&tdMode=cross&instFamily=BTC-USDT`，1 次請求）：共 99 檔，`instId` 為空字串、`instFamily` 為 `BTC-USDT`。`minSz`／`maxSz` 的單位是張（第 1 檔 0～1000、第 2 檔 1000.01～5000，和合約的 `lotSz` 0.01 一致）。前三檔：

| 檔位 | 張數 | mmr | imr | maxLever |
| --- | --- | --- | --- | --- |
| 1 | 0～1000 | 0.004 | 0.01 | 100 |
| 2 | 1000.01～5000 | 0.005 | 0.015 | 66.66 |
| 3 | 5000.01～20000 | 0.0075 | 0.02 | 50 |

最後一檔是第 99 檔，上限 1,940,000 張，mmr 0.4875。BTC-USDT-SWAP 一張是 0.01 BTC，所以研究請求的上限 1000 張（10 BTC）一律落在第 1 檔；依權益調整張數的策略在本金很大時才會進到更高檔位。

### 1.2 全倉、單向持倉下的維持保證金與強平

來源：
- [Futures mode: cross margin trading](https://www.okx.com/en-us/help/iii-single-currency-margin-cross-margin-trading)（CatOS 的 Demo 帳戶是 `acctLv=2`，即這篇講的合約模式）
- [How do I calculate the liquidation price for futures? What are the conditions for liquidation?](https://www.okx.com/en-us/help/how-to-calculate-the-price-what-are-the-conditions-for-strong-flat)（2026-08-11 更新）
- [How does liquidation work in futures trading?](https://www.okx.com/en-us/help/frequently-issues-of-contracts-for-compulsory-liquidation)（2026-08-05 更新）
- [Tiered maintenance margin ratio rules](https://www.okx.com/en-us/help/v-tiered-maintenance-margin-ratio-rules)（2026-08-11 更新）
- [Futures margin calculation rules](https://www.okx.com/en-us/help/ii-what-is-margin-in-perpetual-swaps)（2026-10-08 更新）

原文重點：

- 全倉（合約模式）維持保證金率 = （該幣全倉餘額 + 未實現損益 − 掛單占用 − … − 掛單手續費）÷（維持保證金 + 強平手續費）。
- 強平手續費 = 部位價值 × taker 費率（永續與交割合約）。
- U 本位合約的維持保證金 = 面值 × 張數 × 乘數 × 標記價格 × 該檔位維持保證金率。
- 全倉時，同一合約的所有方向合起來算張數與檔位。
- 觸發條件：維持保證金率 ≤ 100%，也就是「權益小於或等於維持保證金加強平手續費」。
- 強平價格以標記價格為準。
- 第 3 檔以上的部位先分段減倉，每減一次降一檔；第 1、2 檔不分段。
- 初始保證金（全倉、U 本位）= 面值 × 張數 × 乘數 × 標記價格 ÷ 槓桿。單向持倉下，多單掛賣單的保證金需求是 max（部位名目 + 買單價值，賣單價值 − 部位名目）÷ 槓桿，所以減倉或反手到較小部位不需要額外保證金，只有新部位比舊部位大時才要。

### 1.3 強平時的費用與剩餘權益

同上來源，加上 [Tiered maintenance margin ratio rules](https://www.okx.com/en-us/help/v-tiered-maintenance-margin-ratio-rules) 第 1.3 節：

- 強平手續費：按使用者目前費率等級的 taker 費率收。
- 強平清算費（liquidation clearance fee）：U 本位合約 = 面值 × 乘數 × 被強平張數 × 標記價格 × 該張數對應檔位的維持保證金率。用來補強平過程的滑價與損失，淨額轉入風險準備金。
- 「強平觸發後，這個部位對應的整份保證金都會損失，不只是手動平倉會虧的那部分。」
- 實際扣款 = 以強平當下標記價格計的已實現虧損 + 強平手續費 + 強平前未結算的資金費。
- 強平後資產為負時，由風險準備金（security fund）補足負數，並產生穿倉損失帳單。

文件之間有一處不一致：全倉文章說分段減倉時收取一部分維持保證金，「不另收強平手續費」；分級文章則說強平時收強平手續費，另外可能收清算費。本模型兩項都收（較保守）。兩種讀法的差別最多是「部位名目 × taker 費率」，例如 1000 張、價格 60,000 時 taker 0.05% 是 300 USDT。這點標為**待驗證**。

### 1.4 2026-11-11 更新紀錄提到的多空模式檔位計算

來源：[OKX API 更新紀錄 2026-11-11](https://www.okx.com/docs-v5/log_en/#2026-11-11-max-open-size-direction-specific-calculation-in-long-short-position-mode)

原文：「In long/short position mode, the position tier gradient factors used to calculate the maximum openable quantity now differ between the long and short directions for SWAP and FUTURES.」異動的是 `Get leverage estimated info` 的 `estMaxAmt`、`Get maximum order quantity` 的 `maxBuy`／`maxSell`、`Get maximum available balance/equity` 的 `availBuy`／`availSell` 的說明，以及建議在多空模式指定 `posSide`。

結論：只影響多空模式（`long_short_mode`）下「最大可開數量」的計算；條目沒有提到單向模式（`net_mode`）、`position-tiers` 端點、維持保證金率或強平。CatOS 只用 `net_mode`，本模型也不計算最大可開數量，所以不受影響。API 文件裡 `posSide` 的說明寫 `net` 是預設值，與此一致。

## 2. 採用的公式

符號：`q` 是帶正負號的張數，`b` 是每張的基礎幣數量（BTC-USDT-SWAP 為 0.01），`E` 是均價，`B` 是帳戶餘額（初始本金 + 已實現損益 − 手續費 − 資金費），`f` 是本次回測的手續費率（研究一律市價成交，視為 taker 費率），`m`／`i` 是 `|q|` 所在檔位的 mmr／imr。

- 名目 `N(P) = |q| × b × P`
- 權益 `Eq(P) = B + q × b × (P − E)`
- 維持保證金 `MM(P) = N(P) × m`，強平手續費 `LF(P) = N(P) × f`
- 檔位：`|q| ≤ maxSz` 的第一檔（邊界值 1000 張屬第 1 檔，1000.01 張屬第 2 檔）。
- **觸發**：`Eq(P) ≤ MM(P) + LF(P)`，`P` 用該根 K 線的最不利價（多單最低價、空單最高價）。
- **強平價**（`Eq = MM + LF` 的解）：
  - 多單：`P_liq = (q × b × E − B) ÷ (q × b × (1 − m − f))`，向下取到 tick（成交價對交易者不利）。
  - 空單：`P_liq = (B + |q| × b × E) ÷ (|q| × b × (1 + m + f))`，向上取到 tick。
  - 觸發判斷本身不取整；觸發代表最不利價已越過精確解，所以取整後的價格仍在該根 K 線的最不利價與開盤價之間。
- **成交價**：開盤價已經越過強平價（跳空）時用開盤價，否則用強平價。
- **強平成本**：以成交價計 `LF` 與清算費 `N × m`。先算 `e = B + 已實現損益`；`e ≤ 0` 時兩項都收不到，保險基金補足 `−e`；`e > 0` 時依序收強平手續費、清算費，每項以剩下的權益為上限。強平後餘額 = max(0, e − LF − N × m)。在強平價成交時 `e` 剛好等於 `LF + N × m`（取 tick 後略小，清算費只收到剩下的部分），所以強平後權益是 0，和 OKX「整份保證金損失」一致。
- **強平後**：部位歸零、掛著的意圖作廢、不再呼叫策略，之後每根 K 線的權益維持 0。
- **初始保證金**（只在新部位張數大於舊部位時檢查，減倉與反手到較小部位不檢查）：模擬成交後，以開盤價代替標記價格估值，`成交後權益 < |目標| × b × 開盤價 × max(1 ÷ 槓桿, 目標檔位 imr)` 就拒單。用開盤價估值等於把成交價比開盤價差的滑價算成 OKX 開倉時計入的 order loss（[Futures margin calculation rules](https://www.okx.com/en-us/help/ii-what-is-margin-in-perpetual-swaps) 第 7 節；獨立驗收 D2，2026-11-12），部位不變並記錄。目標張數超過最後一檔上限也拒單。槓桿預設不設，等於直接用檔位的 imr（交易所允許的最大槓桿），也就是只擋交易所一定會拒的單。

### 一根 K 線內的順序

1. 結算開盤時刻的資金費。
2. 有部位時，先用開盤價檢查一次強平（上一根收盤到這根開盤之間跳空越過強平價）；觸發就以開盤價強平，前一根收盤決定的意圖作廢。實際的價格路徑在跳空中已經先越過強平價，所以強平排在成交之前（獨立驗收 D1，2026-11-12）。
3. 前一根收盤決定的意圖在開盤價（加滑價）成交，先做初始保證金檢查。
4. 用最不利價檢查強平（用步驟 1～3 之後的餘額）。
5. 結算收盤時刻的資金費；有部位時，再用收盤價檢查一次（資金費可能把權益壓到門檻以下），觸發就以收盤價強平。
6. 記錄收盤權益；沒有強平才呼叫策略。

### 和使用者同意的做法有哪些不同，以及為什麼不需要另外決定

| 項目 | 同意的做法 | 採用 | 差別 |
| --- | --- | --- | --- |
| 觸發門檻 | 權益低於維持保證金 | 權益 ≤ 維持保證金 + 強平手續費 | 照 OKX 原文。門檻多出 `N × f`（taker 0.05% 時約為維持保證金的八分之一），方向較保守 |
| 強平成本 | 扣強平成本 | 強平手續費 + 清算費，不夠由保險基金補到 0 | 照 OKX 原文；兩項都收是兩篇文章較保守的讀法（見 1.3） |
| 第 3 檔以上 | 未提 | 一次全部強平 | OKX 會分段減倉；全部強平虧得較多，方向保守。研究固定張數上限 1000 張到不了第 3 檔 |

差別都小，而且都偏保守，所以照開工單的指示自行採用並記錄，不停下來問。

## 3. 保守假設與待驗證

- **價格來源**：用成交價 K 線的高低點代替標記價格。成交價的影線通常比標記價格長，會高估強平次數。第 2 步再評估是否改抓標記價格 K 線。
- **同一根 K 線先碰高還是先碰低**：已收盤 K 線看不出來，一律假設先碰不利的那端。這和開盤成交、收盤決策的現有模型一致，會高估強平次數。
- **檔位是現在的快照**：OKX 沒有歷史檔位的公開端點，5 年資料一律套 2026-11-12 抓的檔位。過去的檔位是否不同，**待驗證**。
- **強平手續費與清算費是否都收**：見 1.3，**待驗證**，採較保守的都收。
- **強平價取 tick**：OKX 沒寫強平價怎麼取整；本模型讓成交價往對交易者不利的方向取 tick（多單向下、空單向上），**待驗證**。
- **費率**：強平手續費用本次回測的 `fee_rate`。OKX 用帳戶當下的 taker 費率，研究請求的 `fee_rate` 本來就代表 taker。
- **不模擬**：自動減倉（ADL）、掛單占用的保證金（研究在收盤決策、下一根開盤成交，K 線內沒有掛單）、多合約共用保證金、逐倉、標記價格與成交價的差。

## 4. 預設開關與結果標示

選擇：

- **研究核心 `research.backtest`**：`BacktestConfig.margin` 預設 `None`（不啟用）。CLI（`catos/research_cli.py`、`catos/cli.py`）、範例、DCM 研究與 local-sim 的既有呼叫行為不變。
- **研究服務（網頁、MCP、Worker；回測、優化、滾動驗證）**：OKX 歷史資料集只要本機有該合約的檔位快照，就**預設啟用**；內建合成資料集不啟用（它的合約規格是測試用的，不是真實合約）；OKX 資料集在本機找不到檔位快照時不啟用，並寫明原因。
- 理由：研究線的目的是接近實盤可得的結果。不加保證金模型時，槓桿越高結果越樂觀，而且權益跌破 0 之後的數字只是算術延伸。真實資料預設啟用是保守的一邊。不啟用的情況一律在結果裡寫明，不會默默改變。
- 不在研究請求裡加開關：請求欄位是固定的（`DEFAULT_REQUEST`），加欄位要改前端、MCP 與既有測試，且使用者沒有要求關掉。

標示：

- 每份研究結果多一個 `margin_model` 欄位：`enabled`、`reason`（不啟用時的原因）、`tiers_path`、`tiers_sha256`、`tiers`（檔位數）、`leverage`。回測結果另有 `liquidation`（沒被強平時為 `null`）與 `margin_rejections`（拒單次數與前 20 筆）。
- 資料集的 provenance 把檔位檔案列進 `files`（路徑與雜湊），所以檔位一換，provenance 就不同。
- 舊結果（2026-11-12 之前存的）沒有 `margin_model` 欄位，介面顯示「舊結果：未啟用保證金模型」。舊結果不改寫。

## 5. 檔位資料的存放

- 位置：`data/okx/<instId>/position-tiers/okx-<instid>-position-tiers-cross-<UTC 時間>.json`（git 忽略），由 `tools/fetch_okx_candles.py --position-tiers` 抓取、`catos.research_datasets.write_position_tiers` 寫入，內容是 OKX 原始回應加上端點、參數與抓取時間。
- 雜湊：整個檔案的 sha256。研究端每次載入都重新計算並核對欄位，有疑問就不用（fail-closed）。本機有多份快照時用抓取時間最新的一份。
- 沒有放進既有資料集的 manifest：既有 manifest 的欄位與端點清單是固定的，改了會讓四份已抓的資料集全部驗證失敗；而且檔位是「現在」的快照，和 K 線區間無關，同一份快照適用該合約的所有資料集。
- 授權：只限 BTC-USDT-SWAP（工具與資料層都寫死），沿用同一套節流、請求上限與存放規則（`AGENTS.md` 授權紀錄 2026-11-11）。

## 6. 實作、驗收與實測（2026-11-12）

程式：`catos/research.py`（`MarginTier`、`MarginModel`、`Liquidation`、`MarginRejection`；`BacktestConfig.margin`、`Performance.liquidation_cost`），`catos/research_datasets.py`（檔位快照讀寫、掛到資料集），`catos/research_catalog.py`／`research_optimization.py`／`research_validation_job.py`（輸出 `margin_model`），`catos/research_costs.py`、`research_trades.py`、`research_regimes.py`（強平清算費的對帳），`tools/fetch_okx_candles.py --position-tiers`，回測頁的「保證金與強平」列與強平提示。測試在 `tests/test_research_margin.py`（20 個）與 `tests/test_fetch_okx_dataset.py` 的 `PositionTiersFetchTest`。

檔位快照：`data/okx/BTC-USDT-SWAP/position-tiers/okx-btc-usdt-swap-position-tiers-cross-20261112T023422Z.json`，99 檔，sha256 `638d1e4a5bb2b500b2c1a5aaed853cbd4c4ab6c24422eb47a8322c053c3479bf`。當天對這個端點共 3 次請求（1 次存檔路徑寫錯而丟棄、1 次檢視欄位、1 次正式存檔），都是 BTC-USDT-SWAP、公開端點、沒有金鑰。

獨立驗收（全新 Claude 子代理，只拿規格、差異與證據路徑）：

- 第一次（`c160dbfe`）：FAIL，阻斷缺陷 D1、非阻斷缺陷 D2，其餘 8 個核對項目通過。全文 `reports/margin-model-acceptance-20261112/acceptance.md`。
  - D1：開盤跳空越過強平價時，前一根收盤決定的平倉或減倉先成交，權益變負且沒有強平紀錄。修法：成交前先用開盤價檢查原部位（見第 2 節順序第 2 步）。
  - D2：初始保證金檢查沒算 order loss。修法：以開盤價代替標記價格估值。
- 重驗（`6cdb9115`，另一個全新子代理，只驗 D1、D2 影響範圍）：PASS，沒有新缺陷。1500 組隨機案例比對修正前後，差異只出現在「開盤越過強平價」與「滑價大於 0 的初始保證金」兩類，都符合規格；`margin=None` 與 `main` 600 組 0 差異。全文 `reports/margin-model-acceptance-20261112/reverify-d1-d2.md`。

真實資料實測（`execute_request` 純計算，不提交任務）：重跑 `docs/research-real-data-plan.md` 記錄爆倉的 F3 Donchian 1H（24／6、10 張、本金 10,000、taker 0.0005、滑價 2 bps）。2026-07-08 以 63416.9 被強平（第 1 檔、未跳空），強平手續費 3.17、清算費 25.36，權益歸 0 並停止交易；舊引擎是同日稍晚權益跌破 0 後繼續算到 -525.75。往返統計對帳殘差 0。

沒做的事：介面只在整合測試的合成資料集上實際渲染過「未啟用」狀態；「啟用」與「已強平」狀態只有型別檢查與後端輸出測試，沒有在瀏覽器實際操作。優化與滾動驗證頁沒有顯示舊結果的「未啟用」標示（資料仍有 `margin_model` 欄位可判斷）。
