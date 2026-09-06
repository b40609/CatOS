# 02: 本地 AES-256-GCM 金鑰安全模組 (Local AES-256-GCM Security Module)

**What to build:**
實作 `src/core/security.py`，提供 `SecurityManager` 封裝 AES-256-GCM 認證加密、PBKDF2-HMAC-SHA256 密鑰衍生與隨機 Nonce 生成機制。提供交易者本機 OKX 模擬盤憑證（API Key, Secret, Passphrase）的加密存儲、讀取與驗證功能。具備強大的防竄改驗證（Tag 檢驗失敗拋出明確異常）與敏感資訊遮罩機制（嚴禁於日誌或字串輸出中暴露明文金鑰）。

**Blocked by:** 01: 環境與核心依賴配置

**Status:** completed

- [x] 實作 `SecurityManager` 類別，支援 AES-256-GCM 加解密與 PBKDF2 密鑰衍生
- [x] 實作憑證模型 `OKXCredentials`，具備敏感欄位遮罩（repr 脫敏）
- [x] 實作本機加密憑證持久化（以安全 JSON 格式或 SQLite 儲存密文）
- [x] 撰寫單元測試 `tests/test_security.py`：驗證加解密往返一致性、防竄改拋錯、空密碼與格式異常保護
- [x] 測試通過且無任何敏感資訊洩漏至日誌
