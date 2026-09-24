# catOS 統一 localhost shell handoff

日期：2026-09-23。狀態：**PASS（local-sim）**。

## 交付內容

- root `/` 現為單一 catOS shell，頂層只提供「量化交易」與「Yaozi 情報」。
- `/dashboard` 保留已驗收的 Yaozi V9 情報頁與同源 `/intel/...` API。
- `/quant` 為唯讀量化狀態面；沒有 Web start/stop、下單或 lifecycle mutation 控制。
- GET `/system/strategy-status` 使用 `catos-strategy-status-v1`，可由 `create_app(..., strategy_status_provider=...)` 注入 backend Supervisor 的唯讀 snapshot。沒有 provider 時明示 `not_materialized`。
- `catos.app_shell.supervisor_status_provider(supervisor)` 只讀既有 `LocalSupervisor`；backend Supervisor 仍是唯一 lifecycle owner。

## Lifecycle independence 證據

`tests/test_app_shell.py` 使用 temporary synthetic DB 與 real local-sim `LocalSupervisor`：

1. `start()` + `reconcile()` 後處理 synthetic event 1，worker 已建立，checkpoint event_seq = 1。
2. 同一 Supervisor 掛入唯讀 status provider，依序請求 `/`、`/quant`、`/dashboard`、再次 `/` 與 `/system/strategy-status`。
3. Web requests 前後 Supervisor revision、checkpoint event_seq 與 worker ownership 均不變。
4. TestClient context 結束後 Supervisor 仍存在；再處理 synthetic event 2 成功，checkpoint event_seq = 2。

因此 browser navigation／reload request／Web client teardown 沒有被實作成 Supervisor `start()`、`close()` 或第二條策略 lifecycle path。

## 驗證

- `python -m unittest tests.test_app_shell tests.test_yaozi_social_runtime_sync tests.test_market_api`：44/44 OK。
- `python -m py_compile ...`：OK。
- Crawl4AI `http://127.0.0.1:8877/quant`：render success，顯示 `lifecycle_owner=backend_supervisor`、`browser_controls_lifecycle=false`、`mutation_routes=[]`。
- Crawl4AI `http://127.0.0.1:8877/dashboard`：render success，既有 Yaozi Dashboard 正常。
- root `/`：Crawl4AI 已取得「量化交易／Yaozi 情報」兩個頂層項目；因頁面本身很小，runner 的 structural heuristic 將 `success` 標為 false，但 HTML 與 visible text 均已取得。
- `browser-use`：本機 Chrome 在 CDP ready 前退出，故該 runner 未完成；不是應用 route 或 lifecycle 測試失敗。

## 邊界

- 未寫 project DB、未改 schema；所有 runtime 驗證只用 temporary synthetic DB。
- 未讀真實憑證，未發送 Demo／Live request。
- 未修改交易核心、risk、Journal／Lot、Demo grant semantics。
- 未修改 `CatOS_Yaozi` 工作樹；Yaozi V9 source/runtime/Web 狀態維持既有驗收結果。
- 未 commit／push；Astra 既有 dirty work 保留。

機器可讀證據：`outputs/catos-unified-shell-verification-20260923.json`。
