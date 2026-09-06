# 08: 機器人生命週期狀態機與 App 平倉同步 (Bot State Machine & OKX App Sync)

**What to build:**
實作 `src/core/state_machine.py`，封裝 `BotStateMachine` 與 `BotManager`。包含：
1. 嚴格對齊標準 6 大狀態：`待機` (STANDBY)、`載入中` (LOADING)、`運行中` (RUNNING)、`異常 · 連線中斷` (ERROR_DISCONNECTED)、`停機 · 策略運算錯誤` (STOPPED_STRATEGY_ERROR)、`停機 · App 已平倉` (STOPPED_APP_MANUAL_CLOSED)。
2. 同一交易對排他性防呆（Single-instance Mutex per Contract）：同一合約（如 BTC-USDT-SWAP）同一時間只允許一個機器人實例處於運行狀態。
3. OKX App 手動平倉同步：當偵測到部位在 OKX App 端被交易者手動平倉（持倉歸零）時，狀態機自動轉入 `停機 · App 已平倉`，並徹底阻斷二次反向開倉。

**Blocked by:** 06: 實質槓桿硬上限風控引擎, 07: 策略插件介面、熱加載沙盒與出廠雙試紙

**Status:** ready-for-agent

- [ ] 實作 `BotState` 列舉與 `BotStateMachine` 類別，限制合法狀態跳轉路徑
- [ ] 實作交易對排他鎖（Contract Exclusivity Lock），杜絕多機器人重複下單同一合約
- [ ] 實作持倉對帳與 OKX App 手動平倉自動同步轉移至 `停機 · App 已平倉`，並鎖死開倉
- [ ] 撰寫單元測試 `tests/test_state_machine.py`：驗證標準狀態轉換、排他性衝突報錯、OKX App 平倉同步防二次開倉
