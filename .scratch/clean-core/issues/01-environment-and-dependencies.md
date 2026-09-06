# 01: 環境與核心依賴配置 (Environment & Dependencies)

**What to build:**
建立 catOS 後端核心依賴清單（`requirements.txt`）與專案模組目錄骨架（`src/core/`, `src/exchange/`, `tests/`）。精確鎖定 Python 3.12 核心庫（FastAPI, Uvicorn, HTTPX, Cryptography, Pydantic, Pytest, Pytest-Asyncio），確保不引入任何 Node.js 前端工具鏈。建立最小健全度測試，確保開發者安裝依賴後能直接透過 `pytest` 跑通基礎測試套件。

**Blocked by:** None (can start immediately)

**Status:** completed

- [x] 建立 `requirements.txt`，嚴格包含純 Python 必要依賴，拒絕雜質
- [x] 建立標準專案目錄架構 `src/core/`, `src/exchange/`, `tests/`
- [x] 建立 `tests/test_sanity.py`，驗證測試環境與非同步測試（pytest-asyncio）正常運行
- [x] 執行 `pytest` 確保環境為全綠燈
