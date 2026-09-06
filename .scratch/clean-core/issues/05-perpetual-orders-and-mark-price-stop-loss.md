# 05: 永續合約市價下單與交易所標記價條件停損單 (Perpetual Orders & Mark Price Stop Loss)

**What to build:**
在 `src/exchange/okx_client.py` 中實作永續合約下單與部位生命週期管理：

【交易核心原則】：
1. **下單金額定義**：交易者輸入的金額一律為「倉位名義價值 (Notional Value in USDT)」，絕非保證金！開倉計算張數時嚴格以倉位名義價值為分子。
2. **依賴邊界確認**：本專案為純 Python 3.12 原生架構，第一階段無須安裝外部 Jesse 或 Node.js OKX Tool Kit，由 `okx_client.py` 原生直連 OKX V5。

功能實作清單：
1. 逐倉永續合約市價委託（`/api/v5/trade/order`），支援開多、開空、平多、平空，傳入張數由倉位名義價值精確換算。
2. 委託成交後原子化掛出 OKX 交易所端標記價條件停損單（`/api/v5/trade/order-algo`，`slTriggerPxType: "mark"`, `ordType: "conditional"`）；支援停損留白防呆（留白即不掛停損）。
3. 查詢逐倉持倉部位（`/api/v5/account/positions`），對齊持倉張數、持倉均價、標記價、未實現盈虧與保證金率。
4. 實作特定交易對之「市價全平」（撤銷所有未觸發條件單 + 市價全平部位）。

**Blocked by:** 04: 合約規格查詢與張數雙向精確換算

**Status:** completed

- [x] 實作永續合約市價委託下單方法 `place_market_order`
- [x] 實作交易所標記價條件停損單方法 `place_mark_stop_loss`，並支援停損參數留白不掛單防呆
- [x] 實作持倉查詢方法 `get_positions` 與標記價對齊
- [x] 實作交易對撤銷所有條件單與市價全平方法 `close_position_market`
- [x] 撰寫測試 `tests/test_okx_orders.py`：使用 Mock HTTP Transport 驗證完整開倉 ➔ 掛標記價停損 ➔ 查持倉 ➔ 市價全平之 Payload 結構與呼叫順序
