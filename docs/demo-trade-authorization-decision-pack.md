# Demo Trade Authorization 決策包

2026-09-23 B1 follow-up：見 [額度決策與實作](demo-trade-budget-decision.md)及[審查紀錄](demo-trade-authorization-review.md)。原 `max_entry_reservation_usdt` 已改為 `max_entry_mark_notional_usdt`，採每 grant 一次新增曝險 transport 嘗試；已 consumed ID 可由既有 execution order metadata 跨 restart 恢復，active grant 仍不恢復。本輪專屬 17/17、直接受影響七模組 120/120 OK。原 11/11 與 reservation 額度敘述只保留為 B1 前歷史，不得當目前契約。

日期：2026-09-22；2026-09-23 定案並完成 local synthetic 實作。範圍：第一個 OKX Demo 自動策略閉環的寫入授權契約。本文件與本次實作不授權 OKX network、credential、Demo POST、下單、撤單、帳戶修改、既有 trading DB、commit 或 push。

## 0. 2026-09-23 定案／實作狀態

使用者已同意採 **T1-A + T2-A + T3-A**。

- T1-A：Demo 新增曝險必須有每次明示、有限、綁 account／Bot／instrument／reconciliation evidence／revision／時間／額度的 grant。
- T2-A：entry cutoff 後禁止增加曝險；既有 responsibility 的 reduce-only flatten、cancel/query 與既有 P6 cleanup 不被 entry grant 擋住。
- T3-A：grant 僅存在 Supervisor 記憶體，不持久化；restart 後不自動恢復 entry permission，必須重新 reconciliation 並再次明示 authorization。

本機實作：

- 新增 `catos/trade_authorization.py`：immutable `DemoTradeGrant` 與 fail-closed `entry_blocker()`。
- `LocalSupervisor(..., require_demo_trade_grant=True)` 明示啟用此安全 fence；預設 `False` 保留既有 local-simulation 行為。
- 新增 `authorize_demo_trading()`／`revoke_demo_trading()`；grant 綁 durable ownership 的 `evidence_id`／`reconciled_revision`，不把一般 bot revision 或 `reconciled=True` 直接當寫權限。
- 普通 `dispatch()` 在 `ExecutionJournal.prepare()` 前驗 grant；若 prepare 與 transport handoff 間跨過 cutoff／grant 改變，會 `abort_unsent`，不進 FakeExchange。
- reduce-only flatten、query/cancel 與 P6 路徑沿用既有 safety contract，不受 entry grant 過期阻塞。
- 時間由 Supervisor trusted wall clock 決定；synthetic tests 以 `day_clock` 注入，production fallback 使用系統 wall clock，不接受 caller 自報 grant 時間。

驗證：`test_demo_trade_authorization` 6/6 OK；14 個直接／formal 關聯模組合計 263/263 OK；`py_compile` 通過。包含 grant 在 pre-check 後、transport handoff 前跨過 cutoff 的 race；該 request 會 durable `ABORTED`，FakeExchange 0 calls。

## 1. 為什麼需要獨立契約

Formal reconciliation 已明確分離兩個概念：

- `reconciled=True`：這批 evidence 可接受為本地 ownership／fills／risk 基線。
- `trade_authorized=False`：目前仍不得把 reconciliation PASS 當成寫入授權。

現行 `LocalSupervisor.process_bar()` 以 `health == "LOCAL_READY"` 作本地策略處理前置；這對 FakeExchange／local simulation 足夠，但未來接 Demo transport 時不能把 `LOCAL_READY` 或 `reconciled=True` 單獨視為對外 POST 權限。

因此下一個最小切片應新增獨立的 Demo write grant。它只決定「本次明示授權允許哪些 Demo 寫操作」，不修改既有 risk verdict、ownership、UNKNOWN、P6、固定 tag、Decimal 或 sole-writer 規則。

## 2. 建議最小資料契約

候選 `DemoTradeGrant` 至少綁定：

- `authorization_id`：不可重複的稽核 token。
- `environment = demo`。
- `account_id`／account alias。
- `bot_id`。
- `inst_id`，v1 只允許單一 USDT-M SWAP。
- `reconciliation_evidence_id` 與 `bot_revision`：grant 只對指定 reconciliation fence 生效。
- `starts_at_ms`、`entry_cutoff_ms`：新增曝險的明確時間窗。
- `max_entry_notional_usdt` 或等價明示 Decimal 額度：不得由程式自行猜預設。
- 允許操作集合：v1 建議只包含現行普通策略單、cancel、P6 必要維護與風險減倉；不包含轉帳、帳戶模式修改或 Live。
- `end_mode`：授權到期後如何處理既有 position／orders，必須由使用者定案。

grant 不是 Worker 輸入，也不能交給 Worker；只由 Supervisor 持有、驗證與消費。所有真正 exchange request 仍必須走 Supervisor 唯一出口並強制 tag `41cb53c54d6dABDE`。

## 3. 建議 gate 關係

新增曝險只有在以下條件同時成立時才可能送出：

1. grant 本身有效且時間／帳戶／Bot／合約／環境完全匹配。
2. grant 綁定的 `reconciliation_evidence_id`、`bot_revision` 與目前 durable ownership fence 一致。
3. Supervisor 為 `LOCAL_READY`，沒有新的 reconciliation blocker 或 responsibility change。
4. risk state 為 `RUN`＋`HEALTHY`，沒有 Soft／Hard／manual latch。
5. 現有 exposure、reservation、UNKNOWN、P6、margin 與合法減倉規則仍全部通過。
6. 本次新增曝險不超過 grant 的明示額度；金額與數量維持 Decimal。

任何一項失效時，新增曝險 fail closed。grant 不得覆蓋 risk、ownership 或 reconciliation 的拒絕結果。

## 4. 已定案的三個政策點

### T1. 授權是否採每次明示、有限 grant

**已定案：T1-A**。每次 Demo 寫入演練都由使用者明示 account、instrument、額度、entry cutoff 與 end handling；程式沒有永久或隱含 Demo trade permission。

不建議 T1-B「帳戶一旦 reconciled 就持續可交易」，因為這會把 evidence acceptance 與外部寫入權限混為一體。

### T2. 到期後的 end handling

**已定案：T2-A**。`entry_cutoff_ms` 到期後立即禁止任何增加曝險；已存在 responsibility 只允許 risk-reducing cleanup，例如 reduce-only 平倉、取消未成交增倉單、維持／取消 P6 所需操作，直到 position 與 orders 終結。cleanup 不得反向穿零或建立新曝險。

不建議 T2-B「到時一刀切停止所有 POST」，因為可能把既有 Demo position／order 留在交易所無法由系統收尾。

### T3. restart 後是否自動恢復新增曝險權限

**已定案：T3-A**。restart 後不自動恢復 entry permission。必須先完成現有 restart reconciliation；即使原 grant 尚未超時，也要再次明示 re-arm entry。既有 responsibility cleanup 依 T2-A 繼續走既有 risk-reducing path，不以舊 grant 復活 entry。

不建議 T3-B「未過期 grant 自動恢復新增曝險」，因為 restart 本身會重新建立責任與 freshness fence。

## 5. 已完成的最小實作切片

已完成本機 contract，未接 OKX：

1. 新增 immutable `DemoTradeGrant` 與純驗證器。
2. Supervisor 增加獨立 authorization state；`reconciled=True` 不直接改 grant。
3. 在真正 execution dispatch 前加入 grant fence；FakeExchange synthetic 測試驗證 request 不會在 fence 前送出。
4. responsibility revision、reconciliation evidence、expiry、latch、UNKNOWN、額度任一變動都能阻斷 increase。
5. 依 T2 驗證 increase blocked 時合法 reduction／cancel 的行為。
6. restart 依 T3 fail closed，不以舊 `LOCAL_READY` 或舊 evidence 自動復活 entry permission。

本切片沒有新增真實 Demo transport、沒有讀 credential、沒有執行下單，也沒有把 `trade_authorized` 改成 production default true。

## 6. 最小 synthetic 驗收矩陣

| 情境 | 預期 |
| --- | --- |
| reconciliation PASS、無 grant | 不可增加曝險 |
| grant account／bot／inst 任一不符 | 拒絕，無 exchange request |
| grant evidence/revision stale | 拒絕，要求重新 reconciliation／re-arm |
| grant 剛好在有效時間與額度內 | 只允許既有風控已接受的 request |
| 超額或超時 1 ms | 增加曝險拒絕 |
| Soft／Hard／manual latch | grant 不得覆蓋 latch |
| UNKNOWN／foreign responsibility | grant 不得覆蓋 ownership blocker |
| entry cutoff 後合法減倉 | 依 T2；建議允許 cleanup 且禁止穿零 |
| restart | 依 T3；建議 entry permission 不自動復活 |
| Live environment／transfer／mode change | 永遠不在此 grant 範圍 |

## 7. 與目前 production blockers 的關係

此 grant 契約不解除目前三類 evidence/environment blocker：

- production classification 仍為 156/185、29 unknown、`complete=false`。
- D1-A 仍要求精確午夜 verified E₀；目前沒有核准的 production baseline 建立來源。
- dedicated Demo subaccount、foreign position/order/algo responsibility 必須由實際環境證據滿足。

只有上述 blocker 先通過，且另有有效 DemoTradeGrant 時，後續階段才有資格討論真正 Demo POST。
