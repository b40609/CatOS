# Reconciliation S1 snapshot semantics 契約

日期：2026-09-22。範圍：collection／account report／formal gate／Supervisor 的本機契約與合成測試；未讀 credential、未連私有 endpoint、未重跑 Demo、未開既有 DB、未交易、未 commit/push。

## 審查結論

現行 OKX REST collection 沒有可供 catOS 驗證的跨 endpoint 原子 snapshot token。`balance`、`positions`、普通委託、algo 的 `uTime` 是 record update/reference time；`PageResponse.source_ms` 與 manifest page `received_ms` 是 transport／collector 的本機觀測時間。這些時間都不能單獨證明整批帳戶狀態來自同一個交易所原子 snapshot。

現有 `collect_plan()` 本身是單執行緒、依 `CollectionPlan.endpoint_aliases` 順序逐 endpoint 完成，manifest 已保存每個 endpoint 的 `started_ms`、`completed_ms`、完整性、request count 與 page evidence。因此目前能嚴格驗證的是「同一 collection run 的 bounded sequential observation」，不是 exchange-atomic snapshot。

## S1 契約

contract ID：`s1-bounded-sequential.v1`。

account report 必須明示：

```text
mode = bounded_sequential_observation
atomic_snapshot = false
record_update_time_is_snapshot_fence = false
transport_time_is_snapshot_fence = false
```

formal gate 僅在以下條件全部成立時接受 snapshot semantics：

1. report 宣告的 contract 完全符合上述 S1 契約。
2. 同批至少包含 `balance`、`positions`、`orders_pending`、`algo_pending`。
3. 同批至少包含 `fills`／`fills_history` 其中一種，以及 `bills`／`bills_archive` 其中一種。
4. source alias 不重複；每個 source 都 `complete=true`、`issue=""`、`requests>0` 且至少有一頁 evidence。
5. source interval 依 report 順序單調且不重疊：下一 source 的 `started_ms` 不得早於上一 source 的 `completed_ms`；全部 interval 必須落在 report 的 `started_ms..completed_ms`。
6. 每頁 `received_ms` 必須落在所屬 source interval；`source_ms` 只要求為有效 timestamp，不把它當 snapshot fence。
7. state/source 的 `record_time_semantics` 必須是 `last_update_or_reference_ms_not_snapshot`；fills／bills 必須是 `event_ms`。任何把 record `uTime`、transport `source_ms` 或 receive time 改宣稱成 snapshot 的 report 都 fail closed。
8. fills／bills 的歷史窗口完整性由獨立 [W1 window coverage 契約](reconciliation-w1-window-coverage-20260922.md) 驗證；S1 不把事件窗口誤寫成單一時點 snapshot，也不接受 caller 布林值代替 request/page evidence。
9. F1 的 `max_batch_span_ms`、report age、clock skew、clock sample age 仍獨立生效；S1 不放寬任何 F1 門檻。

這個契約允許狀態在批次內依時間演進，因此名稱刻意使用 observation；它只證明一個有界、可重建順序的讀取批次。若未來 OKX 提供可驗證的跨 endpoint snapshot/version token，應另立 atomic snapshot contract，不把 S1 改名冒充原子一致性。

## Fail-closed 行為

原本 `FreshnessEvidence.snapshot_semantics_verified: bool` 已移除。gate 不再接受 caller 直接聲稱 `True`；snapshot semantics 改由 report metadata 自行驗證。

下列任一情況回傳 `snapshot_freshness_unverified`：缺必要 state/event source、來源不完整、來源倒序或 interval 重疊、page receive time 超出 source interval、契約宣告被改寫、record time 或 transport time 被宣稱成 snapshot fence。

歷史 2026-09-22 Demo/F1 摘要沒有保存可重建完整 account report 的全部 source/page evidence，因此本片不把歷史 timing 摘要倒推成新的 snapshot pass，也沒有取得新帳戶資料。

## 本機驗證

2026-09-22 執行：

```text
PYTHONPATH=.;tests python -m unittest test_okx_collection test_account_report test_reconciliation_gate test_supervisor_reconciliation
```

修改後 83/83 通過。涵蓋 report 契約宣告、完整 sequential source chain、缺 fills/bills、source interval 重疊、偽造 record/transport snapshot semantics，以及 Supervisor formal reconciliation 合成路徑。
