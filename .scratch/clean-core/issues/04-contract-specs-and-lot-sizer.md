# 04: 合約規格查詢與張數雙向精確換算 (Instrument Specs & Contract Lot Sizer)

**What to build:**
在 `src/exchange/okx_client.py` 實作公共合約規格查詢（`GET /api/v5/public/instruments?instType=SWAP`）與本地快取機制，提取合約面值（`ctVal`）、最小下單張數（`minSz`）、張數步進（`lotSz`），以及標記價行情查詢（`GET /api/v5/market/mark-price`）。

【交易核心原則】：
1. **下單金額定義**：交易者輸入的金額一律為「倉位名義價值 (Notional Value in USDT)」，絕非保證金！
   - 例如：輸入 1000 USDT、逐倉槓桿 10x ➔ 實際開出 1000 USDT 倉位（扣 100 USDT 保證金）。
   - 下單張數計算公式：`下單張數 = 倉位名義價值 / (當前標記價 × 合約面值)`。
2. **依賴邊界確認**：本專案為純 Python 3.12 原生架構，第一階段無須安裝外部 Jesse 或 Node.js OKX Tool Kit，由 `okx_client.py` 原生直連 OKX V5。

實作「倉位名義價值（USDT）」與「合約張數（cont）」的雙向精確無損換算器（向下取整保護），並在換算張數小於 `minSz` 時拋出結構化防呆警告。

**Blocked by:** 03: OKX 模擬盤非同步連線與 V5 簽名核心

**Status:** completed

- [x] 實作合約產品規格查詢與本地快取（取得 `ctVal`, `minSz`, `lotSz`, `ctValCcy`）
- [x] 實作標記價即時查詢方法 `get_mark_price(inst_id)`
- [x] 實作名義價值轉合約張數算法 `notional_to_contracts(inst_id, notional_usdt, mark_price)`，嚴格以「倉位名義價值」換算，包含小於最小張數之拒單防呆
- [x] 實作合約張數轉名義價值算法 `contracts_to_notional(inst_id, sz, mark_price)`
- [x] 撰寫測試 `tests/test_okx_sizer.py`：測試 BTC-USDT-SWAP 等多幣種在各種價格與金額下的換算精度、邊界值防呆與取整邏輯（以倉位名義價值為基準）
