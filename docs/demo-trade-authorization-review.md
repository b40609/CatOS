# DemoTradeGrant 本機審查 — 2026-09-23

2026-09-23 B1 follow-up 已完成：額度欄位改為 `max_entry_mark_notional_usdt`，每份 grant 最多一次新增曝險 transport 嘗試，送單前依當下有效 mark 重新計價；已進 transport 的 REJECTED／逾時／UNKNOWN 都消耗該 ID，可證明未送出的 ABORTED 不消耗。consumed ID 會由既有 execution order 的內部 metadata 在 restart 後恢復，但 active grant 不恢復。本輪專屬 17/17、直接受影響七模組 120/120 OK。以下 11/11 與 reservation 額度敘述保留為 B1 前歷史證據，不是目前契約。

結論：PASS WITH FOLLOW-UP，限 FakeExchange entry grant。前端依使用者指示延後。本輪直接檢查現行程式，新增 adversarial cases，先證實失敗再修正；不是以先前 263 tests 宣稱安全。

## 實測缺陷與修正

- P1：grant pre-check 後，asyncio.wait_for 排程 handoff 前時間跨過 cutoff，舊程式仍呼叫 submit。已在 handoff coroutine 內、transport 入口前無 await 地重新驗時間與 grant；拒絕後 durable ABORTED，0 submit。
- P1：prepare I/O 等待時呼叫 revoke 會遭 SupervisorBusy。撤銷現在是 event-loop 上的立即控制輸入；generation 防止正在等待的 authorize 把撤銷的 grant 裝回。
- P2：close 後同一 Supervisor 仍保留 grant。close 現立即清除並推進 generation；原有新 instance restart 測試亦保留。
- 額度檢查原讀 memory total_reserved，現改讀同次 Journal snapshot 的 durable total_reserved；合成快取偏低案例證明不再放行。pure validator 亦拒絕負值與非有限 reservation。

## 驗證與限制

專屬測試 11/11 OK，包含原 6 案與新增 5 案。受影響回歸命令：PYTHONPATH=.;tests python -m unittest test_demo_trade_authorization test_execution_supervisor test_supervisor test_protection test_supervisor_reconciliation test_verified_e0_lifecycle。

最終版本上述六模組 90/90 OK（含專屬 11 案，不重複加算）。git diff --check exit 0，僅既有 LF/CRLF warnings；另對本片未追蹤檔執行 trailing-whitespace 檢查，0 問題。

B1 前的 `max_entry_reservation_usdt` 曾只限制未釋放 reservation；此限制已由 B1 取代。現在 `max_entry_mark_notional_usdt` 是送單前 mark 計價的單次委託名目額上限，不是市價實際成交額、費用、保證金或虧損的硬上限。

現有執行器只接受 FakeExchange；require_demo_trade_grant=False 是本地模擬相容路徑，不是未來 Demo adapter 可沿用的預設。cleanup 仍受既有 ownership/risk/P6 檢查，entry grant 到期本身不強制平倉，也不構成真實 cleanup POST 授權。未測試真實交易所行為。

僅使用 temporary synthetic DB；未連網、未讀憑證、未開既有 trading DB、未 commit/push，未改 Lot/market/Yaozi。
