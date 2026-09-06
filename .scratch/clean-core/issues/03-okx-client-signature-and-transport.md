# 03: OKX 模擬盤非同步連線與 V5 簽名核心 (OKX Demo Async Client & V5 Signature)

**What to build:**
實作 `src/exchange/okx_client.py` 基礎通訊層，封裝 `OKXDemoClient`。包含：
1. 強制注入 `x-simulated-trading: 1` 請求標頭硬防呆，若缺少則阻斷送出。
2. OKX V5 原廠 HMAC-SHA256 簽名產生器，與 ISO 8601 UTC 時間戳校準。
3. 指數退避重試（針對網路超時與 HTTP 429 速率限制），含隨機抖動（Jitter）。
4. 測試 Seam 設計（可注入 Mock HTTP Transport 以利端對端無外部依賴測試）。

**Blocked by:** 01: 環境與核心依賴配置, 02: 本地 AES-256-GCM 金鑰安全模組

**Status:** ready-for-agent

- [ ] 實作 `OKXDemoClient`，封裝非同步 `httpx.AsyncClient` 與連線生命週期
- [ ] 實作請求攔截器強制注入 `x-simulated-trading: 1` 標頭
- [ ] 實作 OKX V5 簽名計算器（`timestamp + method + path + body` 之 HMAC-SHA256 Base64 編碼）
- [ ] 實作指數退避重試機制（處理 429 與暫態連線錯誤）
- [ ] 撰寫測試 `tests/test_okx_client_auth.py`，驗證官方簽名向量數據契約、標頭強制注入防呆與重試行為
