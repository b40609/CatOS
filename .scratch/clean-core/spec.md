# 規格書：第一階段 Clean Core 後端核心 (Clean Core Backend Foundation)

**狀態**：`ready-for-agent`  
**領域**：後端核心架構、安全性與 OKX 模擬盤通訊  
**對齊規範**：[catOS_V1.md](file:///c:/Users/kai/Desktop/catOS_v1/catOS_V1.md)、[CONTEXT.md](file:///c:/Users/kai/Desktop/catOS_v1/CONTEXT.md)、[AGENTS.md](file:///c:/Users/kai/Desktop/catOS_v1/AGENTS.md)

---

## 一、問題陳述 (Problem Statement)

專業交易者（OKX KOL）在實施量化策略時，面臨以下關鍵痛點：
1. **環境與通道風險**：現有開源量化系統多數預設連線實盤或仰賴本機虛擬紙上撮合，缺乏針對 OKX 模擬盤（Demo Trading）的強制隔離保護，容易因手誤配置洩漏真實 API Key 或送出實盤委託。
2. **金鑰明文暴露**：一般腳本通常將 API Key、Secret、Passphrase 直接以明文存於 `.env` 或設定檔中，缺乏端點加密保護。
3. **合約規則與下單斷層**：OKX 永續合約以「張數（cont）」為撮合計量單位，而交易者通常以「名義價值（USDT）」思考部位規模；手動計算容易產生精度誤差、不符合最小下單單位（`minSz` / `lotSz`）或保證金計算錯誤。
4. **停損缺乏交易所保障**：多數開源系統將停損邏輯寫於本機記憶體（軟止損），一旦電腦休眠、斷網或程式異常崩潰，部位將完全失去停損保護，暴露於爆倉風險；且若以最新成交價停損，易遭插針惡意觸發。
5. **依賴臃腫與多進程破碎**：許多量化架構要求同時啟動多個獨立進程或安裝 Node.js 前端依賴，安裝繁瑣且難以在個人電腦上一鍵穩定過夜運行。

---

## 二、解決方案 (Solution)

為 catOS V1 構建純淨、健壯的 **Clean Core 後端核心**：
1. **乾淨 Python 3.12 核心環境 (`requirements.txt`)**：以單一 Python 進程為核心，精準引入 FastAPI、HTTPX、Cryptography、Pydantic 等純 Python 必要依賴，絕不混雜 Node.js。
2. **本機 AES-256-GCM 金鑰安全模組 (`security.py`)**：
   - 採用 AES-256-GCM 提供認證加密（AEAD），結合 PBKDF2/HKDF 密鑰衍生機制與隨機 Nonce。
   - 提供安全金鑰管理器（`SecurityManager`），負責 OKX Demo 金鑰（API Key, Secret, Passphrase）的本機加密持久化與解密。
   - 實作防外洩保護：絕不輸出明文金鑰至日誌或例外訊息中。
3. **原生 OKX V5 模擬盤非同步客戶端 (`okx_client.py`)**：
   - **唯一通道硬防呆**：所有 HTTP 請求強制硬編碼注入 `x-simulated-trading: 1` 標頭，杜絕切換實盤之可能性。
   - **OKX V5 嚴格簽名機制**：實作 HMAC-SHA256 簽名與 ISO 8601 UTC 時間戳校準。
   - **指數退避重試 (Exponential Backoff with Jitter)**：針對網路抖動與 OKX API 429 速率限制自動重試。
   - **合約規格查詢與張數雙向換算器**：非同步快取永續合約產品規格（`ctVal` 面值、`minSz` 最小張數、`lotSz` 步進單位），精確無損換算名義價值（USDT）與合約張數（cont）。
   - **標記價條件停損單**：下單開倉成交後，原子化向 OKX 交易所送出標記價觸發市價平倉的條件單（`order-algo`，`slTriggerPxType: "mark"`），徹底託管於交易所端。
   - **持倉與帳戶即時查詢**：提供標記價、逐倉持倉、保證金率與未實現盈虧查詢，精準對齊 OKX App 欄位。

---

## 三、用戶故事 (User Stories)

1. 作為交易者，我希望 catOS 的 Python 核心依賴清晰且精簡，以便在 Windows 本機無縫安裝運行，無需安裝 Node.js 或複雜編譯環境。
2. 作為交易者，我希望輸入我的 OKX 模擬盤 Demo API Key、Secret 與 Passphrase 後，系統能以 AES-256-GCM 加密保存於本機，以防止金鑰在硬碟中以明文洩漏。
3. 作為交易者，我希望系統在解密金鑰或執行簽名時，任何錯誤或日誌中都將敏感憑證完全遮罩，以防在除錯時無意洩漏憑證。
4. 作為交易者，我希望當本機金鑰檔案被惡意竄改或損壞時，系統能透過 GCM 驗證標籤（Auth Tag）即時拒絕解密並拋出警報，以確保資料完整性。
5. 作為交易者，我希望向 OKX 送出的每一筆 API 請求，都強制帶有 `x-simulated-trading: 1` 標頭，以保證 100% 只在模擬盤中執行，絕對不會打到實盤。
6. 作為交易者，我希望系統送出的 OKX V5 簽名完全符合原廠 HMAC-SHA256 規範，以確保所有私有 API（查持倉、下單、查帳戶）順暢通過身分驗證。
7. 作為交易者，我希望在遇到 OKX 伺服器限流（HTTP 429）或臨時網路中斷時，客戶端能自動以指數退避演算法進行安全重試，以維持過夜無人值守的連線韌性。
8. 作為交易者，我希望只需指定下單名義價值（例如 500 USDT），系統就能自動根據合約當前標記價與合約面值（如 BTC 0.01），精確換算成整數合約張數，以符合 OKX 撮合引擎規則。
9. 作為交易者，我希望如果換算出的下單張數小於合約規定的最小下單張數（`minSz`）時，系統能明確阻擋並回報「低於最小下單張數」，以防送出無效委託。
10. 作為交易者，我希望在開多或開空成交後，系統能自動向 OKX 掛出標記價觸發的條件停損單，以確保斷網或插針時部位仍受交易所保護。
11. 作為交易者，我希望當我將停損設定留白時，系統明確跳過掛出條件單的步驟，以尊重交易者不設停損的自主決策。
12. 作為交易者，我希望隨時能精確獲取特定合約（如 BTC-USDT-SWAP）的最新標記價，以便策略運算與停損點位計算。
13. 作為交易者，我希望隨時能查詢當前持倉狀態（含持倉方向、張數、持倉均價、標記價、未實現盈虧與保證金率），且用語完全對齊 OKX App。
14. 作為交易者，我希望執行「市價全平」時，客戶端能先撤銷該交易對的所有未觸發條件單，再送出市價平倉委託，以確保部位乾淨結清無殘留掛單。

---

## 四、架構與實作決策 (Implementation Decisions)

### 1. 模組邊界與職責劃分
- **環境與設定層**：定義 Python 3.12 核心依賴，鎖定安全性與網路庫版本。
- **安全模組 (`security.py`)**：
  - 封裝 `SecurityManager` 類別。
  - 使用 Python `cryptography.hazmat.primitives.ciphers.aead.AESGCM`。
  - 金鑰衍生採用 PBKDF2-HMAC-SHA256（100,000 次疊代）搭配本機硬體指紋或隨機 Salt 生成 Master Key。
  - 密文封裝格式為：`Salt (16 bytes) + Nonce (12 bytes) + Ciphertext + Tag (16 bytes)`，以 Base64 編碼保存。
- **OKX 模擬盤客戶端 (`okx_client.py`)**：
  - 封裝 `OKXDemoClient` 類別，採用非同步 `httpx.AsyncClient`。
  - Base URL 固定為 `https://www.okx.com`。
  - 自定義請求攔截器（HTTP Request Hook）：無條件強制注入 `x-simulated-trading: 1` 標頭；若檢測到標頭遺失或被竄改，直接熔斷拒絕送出。
  - 簽名模組：嚴格遵循 OKX V5 規格：
    `sign = base64(hmac_sha256(secret, timestamp + method + requestPath + body))`
  - 退避重試：封裝 Retry 裝飾器或傳輸適配器，設定初始 0.5s、最大 8s、上限 3 次，附加隨機抖動（Jitter）。
  - 合約張數換算：
    - 正向換算（USDT ➔ 張數）：`sz = round_down(notional_usdt / (mark_price * ctVal), lotSz)`
    - 反向換算（張數 ➔ USDT）：`notional_usdt = sz * ctVal * mark_price`
  - 條件停損委託：封裝 `/api/v5/trade/order-algo`，參數嚴格指定：
    - `instId`: 合約代碼（如 `BTC-USDT-SWAP`）
    - `tdMode`: `"isolated"`（逐倉）
    - `side`: `"sell"`（平多）或 `"buy"`（平空）
    - `posSide`: `"net"`
    - `ordType`: `"conditional"`
    - `slTriggerPx`: 停損觸發價（依開倉均價與停損百分比計算）
    - `slTriggerPxType`: `"mark"`（標記價）
    - `slOrdPx`: `"-1"`（市價委託）

### 2. 測試 Seam (架構接縫) 宣告
本模組設計**單一高層測試 Seam**：
- **HTTP 傳輸層接縫 (`HTTP Transport Seam`)**：
  - `OKXDemoClient` 接受注入自定義的 `httpx.AsyncBaseTransport`（或 Mock 傳輸層）。
  - 測試時無須發送真實對外網路請求，透過 Mock Transport 完整檢驗「強制標頭注入」、「簽名計算正確性」、「指數退避行為」以及「OKX V5 API 錯誤碼處理（如 51000 餘額不足、50004 速率限制）」。
  - 保留對 OKX 官方模擬盤 API 的端對端真實連線驗收能力。

---

## 五、測試決策 (Testing Decisions)

### 1. 測試哲學
- **黑箱行為驗證**：只測試公開對外介面（如加密/解密、OKX 請求/回應封裝、張數換算精度），不測試內部私有輔助函數。
- **邊界與安全性優先**：極端測試 Nonce 隨機性、防竄改檢查、浮點數換算精度（不允許產生浮點小數張數）、網路逾時與重試次數上限。

### 2. 模組測試清單
- **安全模組測試 (`test_security.py`)**：
  - 測試 Roundtrip：明文金鑰經加密後解密，還原出完全一致的明文字串。
  - 測試防竄改：修改密文中任意 1 個 byte，解密時必須拋出認證失敗異常，禁止回傳破損資料。
  - 測試敏感資料脫敏：確保 `repr()`、日誌記錄與異常堆疊中不含原始金鑰明文。
- **OKX 客戶端通訊與簽名測試 (`test_okx_client.py`)**：
  - 測試請求標頭：驗證每個向外送出的請求均強制包含 `x-simulated-trading: 1`。
  - 測試 V5 簽名生成：使用 OKX 官方文檔提供的簽名向量數據進行契約測試。
  - 測試指數退避重試：模擬 429 狀態碼與網路連線超時，驗證重試間隔及達到最大次數後的異常拋出。
  - 測試張數與名義價值換算：
    - BTC-USDT-SWAP（面值 0.01 BTC）各價格與名義金額之張數換算。
    - 低於最小張數（`minSz`）時的拒絕與警告。
    - 步進單位（`lotSz`）之無條件向下取整（避免超額下單）。
  - 測試條件停損單 Payload 結構：驗證 `slTriggerPxType: "mark"` 與 `ordType: "conditional"` 正確注入。

---

## 六、範圍外項目 (Out of Scope)

- **前端 Web 介面與組件**（保留至第三階段）。
- **FastAPI REST 路由與 SSE 事件流**（屬於第二階段）。
- **Jesse 策略抽象層、動態參數表單與出廠雙試紙**（屬於第一階段後續任務）。
- **實盤真實資金交易**（本專案第一版唯一紅線：永久禁止）。

---

## 七、補充說明 (Further Notes)

- 專案所有程式碼、變數、註解及測試用例均遵照 [CONTEXT.md](file:///c:/Users/kai/Desktop/catOS_v1/CONTEXT.md) 中的標準術語。
- 所有 Python 代碼遵循 PEP 8，型別提示全面採用 Python 3.12 原生語法（如 `str | None`、`list[dict]`）。
