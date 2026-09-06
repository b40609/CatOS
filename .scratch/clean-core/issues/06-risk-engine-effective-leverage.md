# 06: 實質槓桿硬上限風控引擎 (Risk Engine & Effective Leverage)

**What to build:**
實作 `src/core/risk_engine.py`，封裝 `RiskEngine`。包含：
1. 即時計算實質槓桿：`實質槓桿 = 全帳戶持倉名義價值總和 / 帳戶總權益`。
2. 預估開倉後實質槓桿：`(當前持倉名義價值總和 + 擬開倉名義價值) / 帳戶總權益`。
3. 若預估實質槓桿超過自訂硬上限（如 2.0x、3.0x），強制拋出 `RiskLimitExceededError` 拒絕開倉。
4. 白名單豁免機制：平倉委託與條件停損委託 100% 豁免風控檢查，保證部位隨時可平倉避險。

**Blocked by:** 05: 永續合約市價下單與交易所標記價條件停損單

**Status:** completed

- [x] 實作 `RiskEngine` 類別與 `RiskLimitExceededError` 風控異常
- [x] 實作 `calculate_effective_leverage(positions, total_equity)`
- [x] 實作 `validate_order(order_action, notional_usdt, current_positions, total_equity)`
- [x] 實作平倉與停損委託白名單豁免邏輯
- [x] 撰寫單元測試 `tests/test_risk_engine.py`，覆蓋正常開倉、超出硬上限拒單、平倉豁免放行與極端邊界測試
