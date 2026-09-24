# Reconciliation W1 window coverage 契約

日期：2026-09-22。範圍：OKX Demo read-only transport／collection manifest／account report／formal gate／Supervisor 的本機契約與合成測試；本片未讀 credential、未連私有 endpoint、未重跑 Demo、未開既有 DB、未交易、未 commit/push。

## 結論

W1 contract ID：`w1-exact-window-pagination.v1`。

舊版 `WindowEvidence(fill_covered, bill_covered)` 是 caller 可直接提供的布林通行證，不能證明實際 HTTP request 帶了目標 `begin/end`，也不能證明 pagination cursor 已走到 terminal page。W1 移除這個外部布林值；formal gate 改為直接驗 account report 中由 transport／collector 保存的 request 與 page-chain evidence。

## Transport evidence

對 `fills`、`fills_history`、`bills`、`bills_archive`，`DemoReadTransport` 形成 request 後必須確認：

```text
begin == RunScope.window_start_ms
end   == RunScope.window_end_ms
event_time_field = ts
cursor_semantics = after_bill_id
```

不相符時 transport fail closed 為 `window_filter_mismatch`。接受的 `PageResponse` 攜帶 immutable `WindowRequestEvidence`；collection 只有在該 endpoint 每個接受頁都保存完全相同的 evidence 時，才將它寫入 `EndpointManifest.window_evidence`。

## Report evidence

account report 對 windowed event source 輸出：

```text
contract_id = w1-exact-window-pagination.v1
begin_ms / end_ms = report window_start_ms / window_end_ms
event_time_field = ts
cursor_semantics = after_bill_id
filter_semantics = exact_inclusive_begin_end
```

cursor 本身仍以 private alias 輸出；W1 不新增原始 ID、credential 或 raw query 洩漏。

## Gate acceptance

fills 與 bills 分別獨立驗證。每一組要通過必須同時成立：

1. 至少存在一個對應來源：fills/fills_history 或 bills/bills_archive。
2. 每個被選來源 `complete=true`、`issue=""`、`requests>0`。
3. `window_request_evidence` 必須完全等於 report 的 inclusive `[window_start_ms, window_end_ms]` 與 W1 固定 semantics。
4. pages 必須從 page 1 連續編號；第一頁 request cursor 為 `None`，後頁 request cursor 必須等於上一頁 next cursor。
5. cursor 不得重複；最後一頁 `next_cursor` 必須為 `None`，才能證明 pagination terminal。
6. report 內所有對應 fill/bill fact 的 `ts` 都必須滿足 inclusive `window_start_ms <= ts <= window_end_ms`。

fill 任一條件失敗：`fill_window_coverage_unverified`；bill 任一條件失敗：`bill_window_coverage_unverified`。任一子 blocker 存在時同時保留 `window_coverage_unverified`。

W1 不使用「目前拿到的資料剛好都在窗口內」推論完整覆蓋；request filter evidence 與 terminal pagination chain 都是必要條件。

## 歷史資料限制

2026-09-22 先前 Demo/F1 摘要沒有保存 W1 新增的 per-endpoint `window_evidence` 欄位，因此不能把歷史 timing／manifest 摘要倒推成 W1 pass。本片沒有為補這個缺口重跑任何真實帳戶採集。

## 本機驗證

```text
PYTHONPATH=.;tests python -m unittest test_okx_collection test_okx_http test_account_report test_reconciliation_gate test_supervisor_reconciliation
```

W1 修改後 109/109 通過。新增/覆蓋：transport begin/end evidence、report evidence 輸出、移除 caller `WindowEvidence`、缺 fill evidence、bill begin mismatch、非 terminal cursor、事件超窗與 inclusive boundary acceptance。
