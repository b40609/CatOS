# I-b-1：採集整合器開發交接

日期：2026-09-14。狀態：開發與測試案例已補齊，**已由驗證模型完成 review 與專屬驗證，I-b-1 DoD 驗收通過**。驗證過程沒有讀憑證、連 OKX、執行資料持久化或 commit／push。

目標設定已由使用者提供：`okx-demo`／OKX Demo／台灣、`BTC-USDT-SWAP`，API 有交易權限、無提幣權限。這些不是交易授權；唯讀權限、區域主機與實際帳戶仍未查證。

## 已完成的開發範圍

- 沿用工作目錄已有的修正：剩餘時間限制 timeout、預期傳輸錯誤統一、JSON 深度／節點／大小限制，以及 GET allowlist／不可變 endpoint tuple。
- 補強序列化：分塊計算實際 UTF-8 JSON 大小及 digest，捕捉遞迴／Unicode／JSON 轉換錯誤，保留之前已接受的頁面。cursor 亦受大小限制。
- PageRequest 拒絕超出 RunScope 的頁碼與 timeout；CollectionPlan 拒絕非字串 alias。
- 完成 `okx_collection.collect_plan(plan, transport, clock=...)`，串接既有 `bounded_pagination.collect()`，沒有第二套分頁實作。
- 跨端點共用請求與 monotonic 時間預算，scope 全程傳入 PageRequest。response 帳戶代稱／環境不符時不保存該頁、停止剩餘端點。
- 完成整批 manifest：版本、帳戶代稱、環境、合約、時間窗、批次時間、請求計數及逐端點頁鏈／digest／失敗原因；未開始的端點亦列出。

## 邊界與停止語義

`complete` 僅代表所選來源的分頁流程正常結束，**不表示帳戶已對帳、資料新鮮、時間窗已由交易所證明完整或可以交易**。回應必須有 `code="0"` 及 list 型別 data，金融欄位與來源時間語義仍由 I-b-2 解碼。

帳戶／環境綁定是可信測試 transport 的回應契約，不是身分認證。GET 路徑由固定 allowlist 決定；實際主機、簽名、查詢參數、API 分頁終點判定與資料篩選不在本片。特別是單筆 order／order_algo 所需的受限 ID，不能由本片無參數 plan 直接形成真實 API 查詢。

scope_mismatch、rate_limited、interrupted 停止全批，後續端點記為 not_started；請求或時間預算用盡也不得再呼叫 transport。其他端點局部錯誤保留 partial evidence，可在剩餘預算內採集其他來源，但整批 complete=false。沒有自動 retry。

timeout 是合作式：driver 傳入較小的剩餘時間，也拒收遲到頁面，但不能強制終止無視 timeout 的同步 fetch。未增加執行緒、程序或無法取消的背景呼叫。請求計數是 driver 嘗試次數的預算上界，包含失敗或適配檢查拒絕的嘗試。

每頁預設上限：深度 32、節點 100,000、JSON 2,000,000 bytes。Limits 可明示調整；這些是開發資源限制，不是金融政策。transport 已建立物件的記憶體不受本函式事後限制，未來 HTTP transport 必須在讀取 body 時另外限流／限大小。

結果目前只保存在記憶體，成功頁面是未脫敏 JSON，**不能直接寫檔、輸出至日誌或分享**。I-b-2 必須補欄位 allowlist／假名化後才提供正式輸出。原始傳輸異常 body 不由本片保存；自訂 FetchError 的 issue 必須是固定非敏感錯誤代碼，不得塞入憑證或回應內容。

## 交由驗證模型執行

```powershell
python -m unittest discover -s tests -p test_bounded_pagination.py -v
python -m unittest discover -s tests -p test_okx_collection.py -v
git diff --check
```

新增案例涵蓋：剩餘時間縮短、ConnectionError 保存先前證據、JSON 深度／節點／實際 bytes／循環資料／Unicode、不可變 plan、偽造端點／方法、請求超額，以及整批 manifest、跨端點預算、scope mismatch、429／中斷、API 失敗、局部分頁上限、傳輸錯誤保留部分結果。

請重點 review：不接受錯帳戶頁面、不以 API 錯誤回應當空帳戶、未執行端點仍有 manifest、所有來源完成才可 complete=true，以及上述合作式 timeout／未脫敏記憶體結果的限制有無被誤用。通過後由驗證模型記錄實際測試數與結果，再決定是否開 I-b-2；本輪不自動續開。

## 2026-09-14 驗證結果

- `test_bounded_pagination.py`：14 tests passed。
- `test_okx_collection.py`：13 tests passed。
- I-b-1 專屬合計：27 tests passed。
- `git diff --check`：通過；僅出現既有工作樹的 LF → CRLF 提示，沒有 whitespace error。
- Review 未發現 I-b-1 阻斷性問題；錯域、缺頁、重複游標、全域請求／時間預算、timeout、429、中斷、亂序來源時間、partial evidence、未開始端點 manifest 與 `complete` 聚合語義均符合本片契約。
- 核心模組未加入 HTTP／socket、憑證環境變數讀取、SQLite／檔案持久化或 subprocess 副作用。

本驗收只涵蓋 I-b-1 離線採集契約與 driver，不代表 I-b 整體、I-b-2、實際 OKX 帳戶或 Demo／Live 交易能力已驗收；依分工停在本片。
