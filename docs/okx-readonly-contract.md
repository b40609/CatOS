# Slice I-a：OKX 唯讀資料契約與保護單研究

查證／交付日期：2026-09-12。基線為 `v0.2-simulation-base`。本片完成官方文件查證、最小離線標準化與差異檢查；**沒有 HTTP client、憑證、私有請求、交易 builder 或 SQLite 寫入**。停在 I-a，不進 I-b／J，不 commit／push。

## 已確認政策與實作差距

P2：陌生部位／委託禁止增倉，不自動接管或處置。P3a：`E_risk = E_verified`，取消 equity buffer。P3b：被動超限只禁止增加曝險，合法減倉始終允許，不自動去槓桿。合法減倉仍須已歸因、核實、新鮮、不穿零且無衝突責任。

P4：固定 E_0、台北午夜日界與外部資金流白名單；日損率為 `(E_verified - E_0 - C_t) / E_0`。不以入金或啟動權益重設分母，未知帳單類別不猜測。費用／funding 已含在權益時，不再扣一次。

P5：Soft／Hard 可配置，v1 預設損失 10%／20%。觸發鎖存、不自動解除；原風險原因消失且恢復條件合格後可隨時人工 re-arm，包含同日。修改門檻不直接解除 latch。

I-a 交付時 F/G 尚未遷移新 P5；後續本輪已完成，見 [風控契約](risk.md)。P5 本機遷移已完成：可配置 10%／20%、原子保存門檻、合格人工 re-arm、schema 4 控制稽核；舊意圖不復活。實際帳戶資料與交易所適配仍未接入。[P6 政策](disaster-stop-policy.md) 也已依最新決策定稿。

## 官方來源與適用性

使用 agent-reach 網頁讀取路由；Jina 暫時拒絕該網域，改用瀏覽工具讀取官方公開文件。環境沒有可執行的 agent-reach CLI，更新檢查未能執行。未安裝工具或讀取帳戶資料。

- [OKX API（my 區域）](https://my.okx.com/docs-v5/en/)：本次可讀取完整 SWAP algo 參數表。
- [OKX API（app 區域）](https://app.okx.com/docs-v5/en/)：本次 Place Algo 表偏向 SPOT／cash，不能據此推定與 my 區域相同。
- [OKX API 全域入口](https://www.okx.com/docs-v5/en/)：大頁直接讀取受大小限制；搜尋索引可查部分欄位，不當成帳戶可用性證據。
- [OKX 交易與對帳最佳實務](https://app.okx.com/docs-v5/trick_en/)：識別碼、回報與部位對帳限制。
- [OKX 策略委託說明](https://www.okx.com/en-ar/help/xi-strategy-order-types)：附加停損、整倉／部分倉位保護的使用說明。

以上是文件能力，不是指定子帳戶／Demo 支援證明。I-b 才能在另獲授權後核對實際區域、帳戶模式與可交易商品；不切換帳戶模式來遷就範例。KOL／帶單角色的端點限制也須依實際 role 核對。

## 唯讀欄位映射與最小失敗處理

以下是 I-a 資料契約；只有下一節列出的部分已有離線程式。金融值保留 Decimal 字串，空字串／缺欄位不等於零。公開商品資料不代表指定帳戶可交易。欄位與端點參照 [OKX Account／Trade／Market 文件](https://app.okx.com/docs-v5/en/)。

| 資料與候選 GET 端點 | 欄位／單位 | 本地核對要求 |
|---|---|---|
| `/api/v5/account/config` | uid、mainUid、acctLv、posMode、roleType、perm | 子帳戶身分、net_mode、環境、角色；讀取成功不等於有交易資格 |
| `/api/v5/public/instruments`；帳戶可用性另查 `/api/v5/account/instruments` | instType、instId、ctType、settleCcy、ctVal、ctMult、ctValCcy、tickSz、lotSz、minSz、state | 只接受已核實 USDT 線性 SWAP；張數乘契約面值，先核對面值幣別，不能套研究合成規格 |
| `/api/v5/account/balance` | totalEq／adjEq 是 USD；details 的 ccy／eq／liab／availEq／ordFrozen、uTime | 不把 USD 當 USDT。I-a 僅支援單一 USDT、無負債 fixture；其他資產拒絕由此 decoder 估值。可用額度與權益分開 |
| `/api/v5/account/positions` | instId、posId、mgnMode、posSide、pos、uTime | SWAP pos 為張數；與自身成交推進核對，差異不自動接管。posId 不是 Bot 所有權證據 |
| `/api/v5/trade/orders-pending`、`order`、`orders-history` | ordId、clOrdId、sz、accFillSz、state、uTime | 去重並區分剩餘量／累計成交；時間不是嚴格版本；終態不代表費用／成交資料已齊 |
| `/api/v5/trade/fills`、`fills-history` | instId、tradeId、ordId、fillSz、fillPx、fee、feeCcy | 成交張數；費用按原符號與幣別保存，不直接塞進 G 的費用成本欄位 |
| `/api/v5/account/bills`、`bills-archive` | billId、type、subType、ccy、balChg、ts | 每個類別明示 external／internal，未分類保留；完整日區間／分頁證據另存，不自行補造 E_0 |
| `/api/v5/trade/orders-algo-pending`、`orders-algo-history`、`order-algo` | algoId、algoClOrdId、state、ordIdList、closeFraction、觸發參數 | 條件責任與觸發後普通委託分開追蹤；查 pending 為空不足以結案 |
| `/api/v5/public/mark-price`；`/api/v5/market/candles` | markPx／ts；K 線 ts、OHLC、confirm | 核對價格單位／年齡；只接受 confirm=1 與指定週期的連續 Closed Bar，不做 1m 盤中重播 |

ordId／billId 可用於各自資料去重；tradeId 必須連同 instId。所有 ID 外再套帳戶／環境命名空間。clOrdId 的 pending 唯一性不等於遠端 exactly-once；posId 可在平倉重開後沿用。強平／ADL 也可能沒有普通委託更新，不能只靠成交序號推斷部位完整性。[OKX 對帳與識別碼](https://app.okx.com/docs-v5/trick_en/)

## 新鮮度、覆蓋與離線實作

具體失敗情境是：不同時點快照、重複回報或缺頁，被誤判為終態而釋放 UNKNOWN。最小做法為純函式回報差異，保留證據，沒有新服務或第二套帳本。驗證成本為 16 個合成單元測試。

`catos/okx_readonly.py` 已提供：

- 嚴格十進位字串與 response envelope 檢查；窄範圍 USDT fixture 權益等值轉換。
- 普通單模式／狀態／張數標準化；ordId 去重、亂序、同時間衝突及累計成交回退標記。
- 成交依 instId＋tradeId 去重；衝突不吞掉；按委託累加張數、按幣別保存有符號費用。
- 外來委託、缺成交、孤立成交、無效終態、未解本地 UNKNOWN 的差異檢查。歸因來自呼叫端持久化資料，不能由 tag 猜測。
- 帳單去重與明示白名單分類；沒有預載生產分類表，測試類別明示為 fixture。
- Evidence 的帳戶／環境／來源／證據 ID／來源時間／接收時間／完整性與年齡檢查。

| 參數／證據 | I-a 實際界線 | 後續要求 |
|---|---|---|
| max_age_ms | 必填、無預設；以來源與接收時間檢查 | mark／帳戶／規格分別配置與量測，不能沿用測試毫秒數 |
| max_skew_ms | 必填；檢查組合快照時間差及來源超前 | I-b 記錄 RTT／服務端時鐘偏差，再提出候選值 |
| received_ms／source_ms | 明示整數；接收時間不能在 now 之後 | uTime 若代表「最後變動」不能冒充全量查詢取樣時間，須保留語義 |
| complete | 合成呼叫端斷言，不是 API 保證 | 每來源保存查詢區間、頁游標鏈、結束證據、重疊重查與缺頁狀態；先建立這些證據才可標完整 |
| 查詢逾時／重查窗口 | 無網路實作、不提供預設 | 與端點限流／歷史保留期核對；429、逾時、WS 重連均不釋放 UNKNOWN |

`reconcile()` 回傳空差異也**不表示可交易、空倉、DONE 或可釋放所有權**；部分成交資料也可以內部一致。不得轉成 G 的 `complete=True`。本模組要求同一帳戶／環境、明示稽核窗口且帶入匹配歷史訂單；呼叫端尚未實作，不能把外層 scope 檢查省略。

尚未實作：完整 config／商品／部位／algo／K 線 decoder、全帳戶現金與部位守恆、分頁採集、WS 補查、可用保證金計算、受管 pending 與本地 reservation 合併、真實帳戶資料與 Supervisor 交易整合。欄位契約先固定，本片只交付最小離線核心，不宣稱 I-b／J 出口已達成。

## P6 能力與生命週期

my 區域 API 表列出整倉 TP/SL：`closeFraction="1"`，與 sz 二選一；SWAP 的 net 模式須 reduceOnly，僅 conditional／oco、市價執行，排除 Portfolio Margin。同一部位只支援一筆待觸發整倉 TP/SL。可選 last／index／mark；`slOrdPx="-1"` 表示市價。`cxlOnClosePos=true` 要求 reduceOnly，適用帳戶模式有限。conditional 同傳 TP／SL 時只有 SL 生效。[OKX Place Algo 參數](https://my.okx.com/docs-v5/en/#order-book-trading-algo-trading-post-place-algo-order)

API 附加單欄位描述包含「主單完全成交後」的關聯；使用說明則說一般附加停損可於部分或全部成交後建立、拆分 TP 才要求全部成交。不能用這兩段文字證明選定 API 路徑具有首次部分成交原子保護，也不能斷言所有附加單都等待全成交。[API 附加單欄位](https://my.okx.com/docs-v5/en/)、[官方附加停損說明](https://www.okx.com/en-ar/help/xi-strategy-order-types)

撤銷／修改的受理回覆不是已撤／已改終態；修改失敗且 cxlOnFail=true 可能取消原單。algo 的 effective 不等於部位已平，須追踪觸發產生的普通委託與成交。[OKX Algo 修改、取消與查詢](https://my.okx.com/docs-v5/en/#order-book-trading-algo-trading)

下表是未來驗證義務與缺口，不授權任何 P6 動作：

| 時點／失敗情境 | 必須留下的證據／未定處理 |
|---|---|
| 首次部分成交 | 已歸因部位、剩餘進場責任、保護查詢結果；不能只看主單 ACK 宣稱已受保護 |
| 增減倉 | 整倉型與固定張數型的覆蓋差異須實測；不能讓新的部位超過已核實覆蓋 |
| 建立 ACK 遺失 | 用持久化 algo client ID 查詢 pending／history／detail；未知不盲重送，查無也不是失敗終態 |
| 修改失敗 | 原保護是否仍在、使用哪個觸發價須核實；cancel-replace 可能有無保護窗口 |
| 觸發 | 沿 algoId／ordIdList 追蹤普通單、部分成交、拒單與餘倉；市價不保證精確止損或完全成交 |
| 平倉與再進場 | 查明 auto-cancel 與剩餘進場單；舊保護不能被誤認為新部位保護，亦不能擅動陌生責任 |
| 重啟／離線 | 對帳普通單、algo、成交與部位後才評估；只知道磁碟上的 live 不等於交易所仍有效 |

固定 tag `41cb53c54d6dABDE`、cross／net、唯一 Supervisor 出口、耐久意圖及 UNKNOWN 規則全部延續。P6 不新增磁碟失效繞行下單通道，也不能取代帳戶級日損風控。

## P6 政策更新

P6 已確認：每個 Bot 可獨立設定災難停損比例，不同幣種可不同，預設 0% 表示不啟用。使用 OKX 交易所端整倉停損作斷線／主機故障時最後保險；正常仍由策略自身停損處理，不取代帳戶級 Soft／Hard。部位平均成本改變時更新；保護建立／更新失敗時禁止繼續增加曝險並告警，不做自動減持。執行參數採 mark 觸發、tick 向提早觸發方向取整；非零改為 0% 時必須確認取消終態，UNKNOWN 期間仍禁增倉並告警。

本節取代先前候選表，撤回「保護缺口超時後自動減持」建議。mark 觸發已批准；自動撤銷殘留進場單仍未定案。首次部分成交、ACK 遺失、觸發後餘倉、平倉取消與重啟仍屬適配驗證義務。見 [P6 定稿](disaster-stop-policy.md)。

## 驗證結果

`python -m unittest discover -s tests -p test_okx_readonly.py -v`：**16 tests 通過**。測試資料全部程式內合成；覆蓋精度、拒絕缺值／float／非有限值、模式限制、去重／亂序／衝突、費用符號、UNKNOWN／外來委託、終態差異、新鮮度與白名單分類。未重跑 177 個全域測試，未做市場回測。

政策衝突文件已同步：AGENTS、架構、H、F／G 契約、模擬規劃、README 與 WORK_PLAN。保留歷史實作界線，沒有把後續完整帳戶對帳或成功 re-arm 記成已完成。
