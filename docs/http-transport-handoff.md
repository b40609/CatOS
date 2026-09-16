# I-b-3：受限 HTTP transport 開發交接

日期：2026-09-15。使用者授權本片，並指定開發模型與驗證模型分工。程式交接後已由另一模型完成獨立 review／驗證；結果見本文末「獨立驗收結果」。驗收未讀真實憑證、未向 OKX 或其他外部站點發請求、未修改交易 DB、未 commit／push；只使用合成資料與 localhost TLS 假伺服器。

## 官方查證與帳戶適用性

使用 agent-reach 的 Jina Reader 讀取 Global 官方 API 文件，另以網頁工具查閱官方入口／異動紀錄。首次整頁輸出過大，後改為只讀相關段落；一次終端編碼失敗後以 UTF-8 重讀。查證為公開文件資料，不代表指定帳戶可用性。技能要求的 check-update 未能執行，環境找不到 agent-reach CLI；未安裝或更新工具。

- [Global API 文件](https://www.okx.com/docs-v5/en/)：Demo REST 使用 `https://openapi.okx.com`，須帶 `x-simulated-trading: 1`。同一主機亦服務其他環境，不能只靠主機判定 Demo。
- [官方主機異動紀錄，2026-05-20](https://www.okx.com/docs-v5/log_en/)：Global 建議改用 openapi.okx.com，舊 www 主機仍支援；區域主機未因此更換。
- [區域入口說明](https://www.okx.com/docs-v5)：註冊站點決定區域；app 站美國／澳洲對應 us.okx.com，my 站歐洲對應 eea.okx.com。**目前只有使用者回報台灣，未核實帳戶註冊站點；不能据此斷言應用 Global。**程式僅提供需明示選擇的 Global Demo profile，不預設、不探測、不切換區域；其他主機拒絕。
- [REST 簽名](https://www.okx.com/docs-v5/en/#overview-rest-authentication-signature)：UTC 毫秒 ISO 時間＋大寫 GET＋實際 path/query＋空 body，HMAC-SHA256 後 Base64。送出的 query 與簽名使用同一字串，重試重新簽名。不自動校時，也不在失敗時追加公開時間請求。

### 本片 query 與分頁映射

| 來源 | 固定參數／覆蓋 | 分頁／時間語義 |
|---|---|---|
| account_config、balance | 不加幣別篩選，不隱藏非 USDT 資產 | 單次回應，要求一筆 |
| account_instruments、public_instruments、mark_price | instType=SWAP、指定 instId | 單次回應，要求一筆；公開規格不替代帳戶資格 |
| public_time | 無額外參數、不附私有認證 | 單次回應，要求一筆；ts 留給 decoder |
| positions | instType=SWAP，不加 instId | 帳戶級快照，空清單可保留，不代表已對帳 |
| orders_pending | instType=SWAP，不加 instId／state | after=ordId、limit；涵蓋帳戶級普通在途責任 |
| orders_history | SWAP、指定 instId、begin／end | after=ordId；官方時間篩選依 cTime，不能當 uTime 或成交時間 |
| fills、fills_history | SWAP、指定 instId、begin／end | **after=billId**；時間篩選依 ts。去重仍為 instId＋tradeId |
| bills、bills_archive | begin／end，不加商品／幣別／類型篩選 | after=billId；時間篩選依 ts，保留未知分類 |
| order | 指定 instId＋已知 ordId，不帶 instType | 單筆；必須匹配所查 ID 與商品 |
| order_algo | 已知 algoId | 單筆；回應必須匹配所查 ID 與指定商品 |
| algo_pending | SWAP、不加 instId；逐類型分支 | after=algoId；conditional,oco 合併，另查 trigger、move_order_stop、iceberg、twap、chase、smart_iceberg |
| algo_history | 上述類型 × effective／canceled／order_failed | 官方未列 begin／end，本片不杜撰時間參數；以整批頁數／請求／時間上限限制 |

對照來源：[帳務](https://www.okx.com/docs-v5/en/#trading-account-rest-api-get-bills-details-last-7-days)、[普通單](https://www.okx.com/docs-v5/en/#order-book-trading-trade-get-order-history-last-7-days)、[成交](https://www.okx.com/docs-v5/en/#order-book-trading-trade-get-transaction-details-last-3-days)、[algo 清單](https://www.okx.com/docs-v5/en/#order-book-trading-algo-trading-get-algo-order-list)、[algo 歷史](https://www.okx.com/docs-v5/en/#order-book-trading-algo-trading-get-algo-order-history)。

所有可分頁來源均採保守空頁終止：非空頁即使不足 limit 也繼續；空頁才結束該分支。跨分支游標含 partition／after，仍由既有 bounded_pagination 保存頁證據及偵測循環。不同分支不藏在單次 fetch 裡，每次 HTTP 嘗試均可計數。algo pending 空帳戶至少需要 7 次請求，history 至少 21 次；預算不足列 incomplete，不縮減類型集合來湊 complete。未知類型、回應狀態與查詢分支不符均停止該來源，不能據此忽略責任。

官方保留期：orders-history 最近 7 日、fills 最近 3 日、fills-history／bills-archive 最近 3 個月、bills 最近 7 日。這些不是「任意時間窗一定完整」保證；程式沒有用固定天數近似月份或自行改查別的端點。超出可證範圍、空窗口或跨午夜資料仍需 I-b-4 核對，I-b-2 的 window_coverage_unverified 不解除。

查得限流：positions 10／2 秒、account instruments 20／2 秒、bills 5／秒、bills-archive 5／2 秒、orders-pending 60／2 秒、orders-history 40／2 秒、fills 60／2 秒、fills-history 10／2 秒、三個 algo 查詢 20／2 秒。本片以全部端點共用、至少 500ms 的連續間隔保守發送；這不是跨程序／跨工具的帳戶級配額保證。

## 程式交付與介面

新增 `catos/okx_http.py`：

- MemoryCredentials：只接受呼叫端傳入的記憶體值；repr 遮蔽。沒有 env、檔案、SDK credential discovery 或 credential CLI。
- HTTPOptions：主機必填且只允許固定 Global profile；page_size 1–100、body 上限不超過 2MB、min_interval 至少 500ms。這些是操作限制，不是風控門檻。
- HTTPSGetSender：只向固定主機 443 直連、驗證 TLS 憑證；無代理、cookie、redirect 或自動 retry。私有與公開呼叫均注入 Demo header；公開來源不附私有認證。非 200 body 不讀取／保存。
- DemoReadTransport：綁定完整 RunScope、單次循序使用；自行保留 wire 嘗試數與同一 runtime deadline，防止绕過 driver 超額。傳輸層只作一個 HTTP 嘗試；429／API 50011 交給 driver 重試，其他錯誤不重試。
- WireRequest／WireResponse：repr 不洩露 headers、query ID 或 body。可注入 Sender、時鐘與 sleep，供另一模型用全合成資料測試。注入介面屬受信測試程式，不是策略插件能力。
- audit()：回傳 ID-free 的副本，含 endpoint、page、partition、類型／狀態、起訖、wait、結果與成功 body 大小。它補充分支／wire 嘗試資訊，不能單獨當帳戶證據。搭配 I-b-2 脫敏報告保存的流程仍未實作。

known_order_ids／known_algo_ids 必須是呼叫端已核對、屬於傳入 scope 的持久化 ID 集合；程式不自行開 DB 驗證歸因。接受頁中的目標商品普通單／成交／algo 子單可增補記憶體已知 ID，仍不推斷 Bot 所有權。order_id／algo_id 可在建構時指定，或在取得前序資料後透過 select_detail 選定已知 ID；每個 detail 來源本次只查一筆，不擴充為自動補查佇列。select_detail 不加入新 ID、不發請求。

修改 `bounded_pagination.py`、`okx_collection.py`：

- RetryPolicy 預設 0 次 retry，保留舊呼叫語義。需由呼叫端明示開啟，最多每頁 5 次。
- 僅 RetryableRateLimit 觸發指數退避；Retry-After 支援整數秒與 HTTP date。延遲超過 cap 時直接終止，不縮短服務端等待要求。
- 每次嘗試都占全域 max_requests；退避、間隔及請求耗時全部占 max_runtime。retry 不增加頁序、不換游標，不重跑已成功頁。Sleep 未走完整延遲即列 interrupted。
- `RunManifest.requests` 是 driver 嘗試數，可能包含送出前被拒絕的檢查；audit.wire_attempts 是呼叫 sender 的次數，包含 sender 的本地失敗，不等於交易所收件數。

修改 `account_report.py`：algo reduceOnly 官方回應型別為字串，嚴格接受 `"true"`／`"false"` 並轉布林；保留原本布林合成 fixtures。其他字串、數字、缺值仍無效。不改变 P6、UNKNOWN 或任何金融政策。partially_effective／partially_failed 等非既有解碼狀態仍明示未知，不擅自認定終態。

## 明示限制與未執行事項

1. 標準函式庫的 OS DNS lookup 不可強制取消。連線／TLS 使用 socket timeout；DNS 返回後在送 HTTP 前檢查 deadline，HTTP headers／body 使用剩餘 deadline 讀取，逾時頁不接受。**沒有聲稱 DNS 期間具 OS 層硬時限或零殘留背景 DNS；本實作未新增背景執行緒／服務。**若後續要求 DNS 硬時限，須另評估平台／resolver 成本。
2. 邏輯 scope 是呼叫端標籤，HTTP 成功不是指定子帳戶身份認證。I-b-4 前仍需確認帳戶註冊站点、憑證來源授權、uid/mainUid 關係與實際 Demo 能力。
3. 帳戶資料未組成原子快照；query 範圍、歷史保留期、類型支援及實際帳戶責任仍須獨立核對。資料日期超出窗口由 decoder 明示，transport 不悄悄裁掉原始列。
4. 原始 body／PageResponse／CollectionResult 只留記憶體且可能敏感；不能直接 print、日誌、寫入 Git 或分享。只有 I-b-2 allowlist／假名化報告才是後續私人輸出候選。標準 traceback 不能附 locals dump；Python 記憶體不提供憑證抹除保證。
5. 沒有 supervisor 整合、寫庫、下單、撤單、帳戶模式修改、背景排程、Live 支援，沒有新的金融／安全政策。

## 獨立驗收結果

2026-09-15 由另一模型依下列矩陣建立並執行驗證。初次 `test_okx_http.py` 17 個案例中，跨頁重複 ID 案例失敗，確認 `DemoReadTransport` 原實作只檢查同頁重複與目前 `after`，未拒絕同 endpoint／partition 更早已接受頁面出現過的 ID。已在 `catos/okx_http.py` 以記憶體 `seen` 集合做最小修補；狀態只在頁面完整驗證並接受後更新，不改 retry、page sequence 或 partition 語義。

修補與補強後，受影響驗證全部通過：`test_okx_http.py` 24／24、`test_bounded_pagination.py` 16／16、`test_okx_collection.py` 13／13、`test_account_report.py` 19／19，共 72／72。transport 專屬測試另以動態合成憑證與 localhost TLS 假伺服器走實際 `HTTPSGetSender` 路徑，驗證受信／不受信憑證、GET 與 Demo header、代理環境不生效、301／302／307／308 不跟隨、錯誤 body 不保留、Content-Length／chunked／truncated／gzip／慢 headers／慢 body 邊界。429、API 50011、Retry-After、重新簽名、全批 request/runtime budget、algo 7／21 分支、detail ID gate、audit/repr 脫敏與 reduceOnly 亦有合成案例。

`python -m py_compile catos/okx_http.py tests/test_okx_http.py` 通過。`git diff --check` exit 0；I-b 相關未追蹤檔另以 `git diff --no-index --check` 檢查，只有工作樹既有 LF→CRLF 提示，沒有 whitespace error。聚焦副作用掃描沒有發現 env／檔案憑證讀取、SQLite、subprocess 或額外外部網路路徑；正式 sender 的外連仍只有固定 Global Demo host，驗收沒有實際呼叫它。

I-b-3 於此範圍驗收通過。這不代表 I-b-4 帳戶註冊站點／真實 Demo 能力／實際帳戶責任已核對，也不授權讀憑證、私有採集、交易或 Live。

## 驗證矩陣

開發交接要求建立專屬 `test_okx_http.py`，補既有 retry 與 decoder 案例；所有憑證、ID、帳戶與回應均使用合成資料。驗收已依此執行，沒有向 OKX 發送請求。

| 義務 | 最小必要案例 |
|---|---|
| 簽名與環境 | 獨立固定 HMAC golden vector；UTC 毫秒；query byte-for-byte；空 GET body；Demo header 不可省；公開端點無私有認證；retry 更新 timestamp |
| 出口限制 | 任意 host／path／method／header 注入拒絕；HTTPS 憑證檢查；HTTP 301／302／307／308 不跟隨、不對 Location 發第二請求；不使用代理 env／cookie |
| 真實 sender 的本機驗證 | 使用合成 TLS 憑證與本機假伺服器，測試時替換連線建立 seam，不改正式 host allowlist、不開 insecure production 選項；覆蓋 headers、body、TLS、狀態碼、關閉資源 |
| 有界讀取 | Content-Length 超限／重複／無效、chunked 超限、截斷、gzip 拒絕、深層 JSON、重複 key、數值 float／NaN、UTF-8 失敗、慢 headers／body deadline；DNS 限制符合文件 |
| 限流與預算 | 429、50011、Retry-After 秒／date／無效／過長、重試上限、timeout 不重試、全域剩餘請求／runtime、500ms 間隔、延遲後重簽；假時鐘與假 sleep 必須共用時間來源 |
| 分頁 | fills 使用 billId 非 tradeId；短頁仍續查空頁；重複游標與重複 ID；重試頁碼不跳號；部分成功後失敗保留既有 evidence |
| 治理覆蓋 | positions／pending 不加 instId；bills 不加 instType／ccy；algo 7／21 分支逐次請求、空分支轉換、預算不足 incomplete、分支回應不符不當成功 |
| 明細限制 | 未知 ID 在送出前拒絕；持久化已知 ID；前序觀測後 select_detail；錯商品／錯 ID 拒絕；查無不解除 UNKNOWN；一批不得重置預算 |
| 脫敏與契約 | credential/request/response repr；自訂 sender exception 不含 body 或秘密；audit 不含 ID；source_ms 為接收時間而非遠端快照；reduceOnly 字串 true/false、非法值 |

受影響驗證範圍：`test_okx_http.py`、`test_bounded_pagination.py`、`test_okx_collection.py`、`test_account_report.py`。本次沒有跑全市場回測或全域測試。

Git 已由驗證模型檢查 diff、未追蹤檔與 whitespace；此文件與新模組均納入。使用者沒有授權 commit／push，故未執行。本片完成即停；本交接不授權實際憑證讀取或私有採集，更不包含 I-b-4／J／Live。
