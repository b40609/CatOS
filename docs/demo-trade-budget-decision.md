# Demo TradeGrant 額度語意決策稿

日期：2026-09-23。狀態：**使用者已定案採 B1；local synthetic 程式與測試已完成**。範圍限第一個本機 synthetic Demo 策略閉環。本文不授權 OKX network、credential、真實 Demo 採集或 POST、既有 trading DB、commit／push。

## 實作前程式證據

- `risk.evaluate()` 對新增曝險的 reservation 計算為 `abs(delta) × base_per_contract × snapshot.mark`；另用 `worst_notional()` 管理持倉與在途委託的帳戶／單幣曝險。reservation 不是保證金，也不是已成交金額。
- `DemoTradeGrant.max_entry_reservation_usdt` 現在只比對 `Journal.total_reserved()`。完整終態成交證據到齊時，`ExecutionJournal._release()` 刪除 reservation；已成交持倉不留在這個計數中。
- `ExecutionJournal.prepare()` 會依最新風控快照重算 verdict，但目前授權額度仍取較早寫入的 reservation。因此 mark 變動時，舊值不能證明送單當下的委託名目額仍在 grant 上限內。
- `prepare()` 使 ownership reconciliation revision 失效。現行 grant 與該 revision 綁定，下一次新增曝險必須重新對帳及授權；此行為不等同明文定義的一次性額度契約。

## 建議定案：B1，首輪一次性送單額度

每份 grant 只允許**一次新增曝險送單嘗試**。使用者明示 `max_entry_mark_notional_usdt`，其意義是送單前用 Supervisor 核實的新鮮 mark 計算的「本張新增曝險委託名目額」上限：`abs(送單數量) × 每張合約基礎幣數量 × mark`。使用 `Decimal`，不得以 Worker 自報金額或較早的 reservation 取代。

- 先通過現有 reconciliation、ownership、風控、UNKNOWN、P6 及時間窗 gate；額度不能放寬任何既有 gate。
- 在同一筆受控 dispatch 中，以準備送出的數量及當下有效風控 mark 重算名目額。若超額、mark 過期或無法核實，拒絕且不呼叫 transport。若 prepare 後到 transport 前 mark／風控快照改變，重新驗證或保守地中止未送訂單。
- 進入 transport 前，於無 await 的入口處把 grant 標成已使用。只要 transport 曾被呼叫，無論 FILLED、CANCELED、REJECTED、逾時或 UNKNOWN，都不恢復此 grant 的 entry 權限。可證明未進入 transport 的 ABORTED 不消耗額度，但原 reconciliation fence 仍須重新建立。
- 撤銷、到期、重啟均禁止該 grant 再新增曝險。若要第二次 entry，須先處理既有責任、重新 reconciliation，再由使用者以新 authorization ID 明示新 grant；不能在同一份 grant 下回收或循環使用額度。
- 到期後的 reduce-only cleanup、cancel/query 與 P6 必要維護，沿用已定案 T2-A 及既有風控；一次性 entry 額度不阻斷合法收尾。

這是**送單前 mark 計價的上限**，不是實際成交 USDT、手續費、保證金或虧損的硬上限。市價成交價可能偏離 mark；若要對實際成交總額設定不可超越的硬上限，仍需另定價格邊界／滑價與委託型態政策，不能靠現有市價委託保證。

現有 `max_entry_reservation_usdt` 已依定案改為 `max_entry_mark_notional_usdt`；既有風控的在途額度與總曝險檢查維持不變。本片未修改既有 trading DB schema。若未來要一份 grant 連續執行多次 entry，需另定累計扣額、部分成交、取消／拒絕返還、UNKNOWN 與重啟稽核規則；不得把 B1 擴充解讀成連續自動交易授權。

## B1 local synthetic 實作

- `DemoTradeGrant` 使用 `max_entry_mark_notional_usdt`；額度不再由 `Journal.total_reserved()` 或 Worker／caller 自報金額決定。
- transport handoff 前以準備送出的 Supervisor-owned 數量、合約 `base_per_contract` 與當下有效 risk snapshot mark，以 `Decimal` 重算 `abs(quantity) × base_per_contract × mark`。
- handoff 內再次檢查 grant generation、時間、risk snapshot revision／time／epoch 與額度；最終檢查、把 authorization ID 標記 consumed、進入 `FakeExchange.submit()` 之間沒有 await。
- transport 一旦被呼叫，REJECTED、逾時／UNKNOWN、取消或其他結果都不恢復該 ID。撤銷後或 reconciliation 後重新安裝同一已 consumed ID 會拒絕。
- 可證明未進 transport 的 request 由既有 `abort_unsent()` durable 記為 `ABORTED`，不消耗一次權限；其後仍需重新 reconciliation，才可再次明示安裝尚未 consumed 的 grant。
- restart 不自動恢復 active grant；已進 transport 的 authorization ID 會由既有 `execution_orders.payload_json` 內部 metadata 恢復 consumed tombstone，因此同 ID 無法靠 restart 重用。此 metadata 不會送進 transport，且本片未修改 DB schema。

## 驗收條件與成本

本機 synthetic 驗收已覆蓋：上限恰好相等可進 transport、超額 1 個 Decimal 最小測試單位被拒、mark 在 intent 建立後上升導致超額被拒、prepare 到 handoff 間快照變動／到期／撤銷不會送出失效 request、已進 transport 後回報拒絕／逾時仍不可用同 grant 再送、可證明未送出時不計一次、restart 不恢復 active grant 且不能重用已 consumed ID、reduce-only cleanup 不受一次性限制。專屬 `test_demo_trade_authorization` 本輪 17/17 OK；直接受影響七模組合計 120/120 OK；使用 FakeExchange、FakeClock 與 temporary synthetic DB，未連網或接觸真實 credential／trading DB。

實作成本為 grant 狀態與 dispatch 入口的最小改動、更新現有專屬測試；無需第二套累計帳本或既有 DB schema 變更。真正 Demo 接線前仍要解決 production classification、verified E₀、專用子帳戶與外部責任證據等既有 blocker。

## 定案結論

使用者於 2026-09-23 已明確同意定案 **B1：每份 grant 最多一次新增曝險送單嘗試，以送單前核實 mark 計算的委託名目額設上限；transport 一旦進入就不返還額度**。本片已完成 local synthetic 實作與本輪驗證；仍不構成真實 Demo write 授權。
