# I-b-2：帳戶 decoder 與差異報告交接

2026-09-14：使用者授權啟動；本地開發與 18 個專屬合成測試完成。同日由另一模型完成獨立 review／驗收，未發現 I-b-2 阻斷性問題。本片未接觸憑證、網路或交易 DB，未 commit／push；停在 I-b-2。

## 輸入與輸出

`catos/account_report.py` 提供 `decode_row(alias, row)` 與 `build_report(result, scope=..., ...)`。前者依 I-a 本地欄位契約回傳 Decimal facts；後者接受 I-b-1 記憶體 CollectionResult，核對帳戶／環境／合約／時間窗及每頁 digest、游標證據，回傳可 JSON 序列化的私人報告。沒有寫檔函式。

呼叫端提供持久化歸因證據：owned_order_ids、owned_algo_ids、owned_positions（`(instId, posId)` 對應有符號 Decimal 張數）、unresolved_local_ids。不由 tag、client ID 或 posId 自動判定所有權。classifications 是明示的 `(type, subType)` external／internal 白名單，無生產預設分類。

涵蓋 config、帳戶／公開商品、balance、positions、普通委託、成交、帳單、algo、公開時間及 mark。缺值、float、非有限金融值列為無效記錄，不補零；空倉的空 avgPx 明示 null。totalEq／adjEq 保留 USD，details 保留原幣別，沒有估算風控權益或可用保證金。

差異包含模式不符、陌生責任、部位數量不符、未解 UNKNOWN、同 ID 衝突、成交窗口缺口、未知資金流及 P6 子單缺口。成交以 instId＋tradeId 去重，帳單以 billId 去重；相同觀測保留各來源索引。不同版本保留衝突觀測，不擅自選最新。費用保留原符號、按幣別彙總；無效／衝突／窗口外事件不提供合計。部分採集可提供有效資料的「已觀測」小計，不能解讀成全帳戶合計。

## 2026-09-15 修補（僅開發，待獨立驗證）

- 同身份保存所有不同內容版本，各自持有 observations；A／B／A 只保留兩版本，後續 A 來源歸回 A，衝突告警不消失。不以最後一筆覆蓋衝突，Decimal 等值格式仍歸為同一內容。
- 驗證來源 evidence 按順序為真正整數 1..N、首請求游標為 null、後頁銜接前頁 next、不得循環或在終頁後續頁；完成來源須非零頁、末 next=null、無 issue，批次／來源完成標誌須一致。`page_chain_invalid`／`manifest_completion_mismatch` 使 collection_complete=false，費用／資金流小計不可用；重複 evidence 不重複解碼。
- 不強加 HTTP 各來源的單頁或空頁終止契約至通用 CollectionResult。合法不完整前綴可零頁，末 next 可有可無；保留有效資料已觀測小計，不宣稱完整。重試使 requests 大於頁數不視為錯誤。
- balance 解碼新增 `record_diagnostics`（alias/page/row/field/reason）；field 與 reason 僅固定白名單，不含值、幣別、ID 或例外訊息。缺值不補零，保留 `invalid_record:balance`。此診斷只能處理未來提供的證據，不能還原已丟失的歷史回應。
- 本次只編寫合成測試，未執行。以下原始驗收數字保留為歷史，不能當目前修補版本驗收。

## 證據與隱私

- 保留起訖／接收時間、頁序、同批游標關聯與來源索引；transport source_ms 不當成已核實快照時間。uTime 是更新時間，不能證明查詢新鮮度。
- fills／bills 採本地閉區間 `[window_start_ms, window_end_ms]`；交易所 begin／end 參數尚未核對。跨台北午夜事件照原時間保留，不重建 E_0。
- uid／mainUid、委託／成交／部位／algo／帳單 ID 與游標使用同批流水假名，保留子帳戶關係與 ordIdList 關聯。每批重建對照，不提供跨批追蹤保證。
- 僅輸出 decoder 欄位 allowlist，未知原始欄位與例外文字不輸出。來源錯誤統一為 collection_failed；原始 digest 改為證據假名，另計算脫敏報告 content_digest。原始 hash 僅在記憶體比對。
- 帳戶代稱由使用者提供；金融值、時間、商品與模式仍屬私人資料。假名化不等於可公開，正式保存目錄與保存動作仍未實作或授權。

## 驗收邊界

collection_complete 只表示 driver 分頁完成且頁面 digest、順序、游標鏈與完成標誌一致。reconciled、trade_authorized 永遠 false；明示 freshness、window coverage、day baseline 未核實。尚無全帳戶守恆、來源重疊收斂、實際帳戶身分認證、P6 成本／tick 價格一致性或觸發後完整結案。effective 永遠保留未對帳差異，即使找到普通子單也不宣稱已平倉。

本片沿用專案 I-a 映射；後續 I-b-3 已補 algo reduceOnly 的官方字串布林解碼並留下獨立驗收紀錄，HTTP／簽名／query／大小限制由該層負責。這不表示所有實際帳戶欄位皆已核實：I-b-4 最新採集仍有餘額及模式差異，本次無原始資料可重新確診，亦未重新查證遠端 API。

## 專屬驗證

開發端交接：`python -m unittest discover -s tests -p test_account_report.py -v`：18 tests passed。包含 Decimal／缺值、USD 分離、陌生部位、模式、子帳戶假名、費用正負／去重／衝突、窗口邊界、白名單、P6 關聯、UNKNOWN、錯域、缺頁／篡改與錯誤脫敏。未跑全域測試或市場回測。

獨立驗證（2026-09-14）：重跑同一專屬命令，18／18 通過；`git diff --check` exit 0，僅出現既有 LF→CRLF 工作樹警告。另以聚焦掃描確認 `catos/account_report.py` 未引入 HTTP／socket、環境憑證讀取、SQLite、subprocess 或檔案寫入路徑。review 核對未取得資料不當零、缺頁不當空帳戶、所有權不猜測、金融字串及事件去重、假名關聯、來源時間語義與 P6 未結案限制，未發現阻斷性問題。I-b-2 本地範圍驗收通過；不自動續開 I-b-3／J／Live，且不擴張上節列出的未驗證邊界。
