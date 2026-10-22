# catOS 正式唯讀 Reconciliation Gate 契約

更新：2026-10-20（R1 local-sim 已實作並完成開發自測，待獨驗）。此文件記錄唯讀對帳 gate 契約；不產生交易授權。9/21、9/22 evidence 為歷史紀錄，不代表當前帳戶狀態。2026-09-23 起全分類目錄 coverage 僅供資訊，實際 unknown／forbidden bills 仍阻擋；Journal／protection 已支援 durable `posId`／`algo_id`。R1 取代第 4 節相應舊基準政策，完整政策見[精簡評估第 5 節](retail-v1-simplification-assessment-20261020.md#5-已定案金融變更r1-操作性風控基準)，實作與 197 項本機自測見[R1 交付](risk-period-r1-local-sim.md)。Demo／Q1 既有路徑仍保留舊來源契約，未接入 R1。

## 2026-09-22 當期 evidence 與未解除條件

- [當期唯讀證據](reconciliation-readonly-evidence-20260922.md)：當時 subtypes 32 類／185 組已取得，11 組明確分類、174 組仍 unknown，新版本與既有靜態 Transfer 版本均為 complete=false。此為 9/22 歷史狀態；當時的全目錄 completeness 阻斷要求已由 9/23 分類縮減政策取代。
- 後續 [F1 freshness 補證](reconciliation-f1-freshness-evidence-20260922.md) 已完成：4 次正常 13-source／41-GET collection 為 20159–20216 ms；gate-adjacent report age 132–170 ms、clock sample age 66–85 ms、midpoint offset +2837～+2848 ms。另有 360 GET／179993 ms 真實 pagination stress 由 deadline fail closed。F1 四值已定案；snapshot semantics 仍未獲新證明。
- 2026-09-22 後續審查已把 clock sample age 從 clock offset 拆開：`max_clock_skew_ms` 只約束 server/local offset，新增 `max_clock_sample_age_ms` 約束 sample 到 `checked_at_ms` 的年齡；不藉放寬 skew 吸收批次耗時。詳見 [分類與 freshness 審查](reconciliation-classification-freshness-review-20260922.md)。
- 本輪 collection_complete=true，但 reconciled=false、trade_authorized=false；balance adjEq missing 與既有 attribution／E_0／P6／foreign／window 等實際差異仍保留。詳見 evidence；未使用真實帳戶資料作單元測試。

## 1. 目的與邊界

2026-09-22 C1-B/C2-A/C3-B/C4-B 已核准。當期 classification residual closure 後 coverage 為 153/185，32 unknown、complete=false；此數字為歷史盤點，coverage 不再單獨阻斷。`FlowClassificationEntry.category` 支援 external/internal/forbidden；forbidden 計入已知分類，但 report 觀察到禁止 bill（包含零金額與非 USDT）必須產生 `unsupported_account_activity`，external-flow 小計 unavailable，formal gate 固定阻斷。分類完整性、DayLedger、freshness 或其他證據不得覆蓋此 blocker。禁止表項本身不代表本批出現禁止活動。external 同時包含核准 C3-B 的非策略 equity adjustment，也包含 C2-A 明確跨 verified trading-account equity scope 的 Funding/OTC system-account transfer；C2 邊界與 verified account equity scope 一致（不再綁定單一欄位名稱；acctLv=2 依單一無負債 USDT details[].eq，adjEq="" 視為合法 not applicable；acctLv=3 依有效 adjEq）。當期分類與剩餘 32 組見 `reconciliation-classification-closure-20260922.md`。

正式 gate 只回答一件事：指定 Bot 在指定本地 revision 下，現有本地責任與一批完整、可驗證的 OKX 唯讀證據是否一致。

`reconciled=true` 只代表「這批證據可接受為本地 ownership／fills／risk 基線的對帳證據」。它不是下單權限。`trade_authorized` 在此契約固定為 `false`；Demo 寫入仍需後續獨立授權與交易入口條件。

gate 不自動接管陌生部位／委託／algo，不因 tag、`clOrdId`、`algoClOrdId`、相同 symbol 或空集合推定 ownership，也不自動修改 OKX 帳戶模式。

## 2. 輸入契約

### 2.1 Collection report

Demo 輸入既有 `account_report.build_report()` 產生的私有報告；R1 本機模擬由受信合成報告經 `risk_period.project()` 投影。至少保留：

- account/environment/instrument/window scope。
- `collection_complete`、來源分頁完整性、digest／cursor chain 結果。
- 正規化 facts、record diagnostics、現有 discrepancies。
- fills 費用小計與 external flow 小計；證據不足時維持 unavailable。

`collection_complete=true` 只是必要條件，不等於 reconciled。

### 2.2 Local ownership snapshot

必須由 Supervisor 單 writer 對 Journal 做一致快照，至少包含：

```text
bot_id
bot_revision
inst_id
local_position
owned_exchange_order_ids
owned_exchange_algo_ids
owned_remote_position_ids
unresolved_local_ids
ordinary_open_count
conditional_open_count
unknown_count
fills_reconciled_local
protection_state
snapshot_digest
```

來源限定為 Journal 已持久化資料；Worker 不得提供或覆寫 ownership。

目前可直接取得的資料：`ownership`、`execution_orders`、protection state。Journal 已支援 `ownership.remote_pos_id`，protection state 已保存遠端 `algo_id`；早期「沒有持久化 identity」的缺口敘述已被後續實作取代。這不代表每個帳戶都已有合格 identity：非零遠端 position 或需歸屬的遠端 algo 缺少 durable remote identity 時仍阻斷，不能以 symbol、tag 或 client ID 補猜。首次 position identity 綁定須通過既有本地／遠端成交 lineage 與 revision 驗證；詳見 [identity 政策與實作紀錄](reconciliation-policy-decision-pack.md)。

### 2.3 Revision fence

唯讀採集前後都必須取得本地 revision fence：

1. `revision_before`：開始採集前的 Bot revision。
2. 採集期間不得把舊快照視為持續有效。
3. `revision_after`：報告送入 gate 前再次讀取。
4. 僅 `revision_before == ownership_snapshot.bot_revision == revision_after` 才可進一步判定。

若 revision 改變、execution/protection responsibility 改變或出現新的 UNKNOWN，回傳 `local_revision_changed`，重新取得唯讀證據；不沿用舊報告。

### 2.4 Freshness policy 與 evidence

freshness 的數值政策必須由 Supervisor 設定後明示傳入，不在 decoder 或 gate 內藏預設值。至少包含：

```text
policy_id
max_report_age_ms
max_batch_span_ms
max_clock_skew_ms
max_clock_sample_age_ms
checked_at_ms
```

Demo F1 已定案為 policy ID `f1-demo-2026-09-22`：`max_report_age_ms=1000`、`max_batch_span_ms=31000`、`max_clock_skew_ms=3000`、`max_clock_sample_age_ms=500`。這些值必須由 Supervisor 明示注入；gate 本身仍不提供 fallback。

現有 collection `source_ms` 是本機 transport receive time，不是 OKX 帳戶狀態的遠端 snapshot timestamp；balance/order/position 的 `uTime` 也只是 record update time。兩者都不能單獨證明整批 snapshot freshness。

S1 已定義 `s1-bounded-sequential.v1`：現有 collection 不宣稱 exchange-atomic snapshot，而是驗證同一 `collect_plan()` 內有界、依 manifest 順序完成的 sequential observation。account report 必須明示 `atomic_snapshot=false`、`record_update_time_is_snapshot_fence=false`、`transport_time_is_snapshot_fence=false`。詳細條件見 [S1 snapshot semantics 契約](reconciliation-s1-snapshot-semantics-20260922.md)。

正式 freshness evidence 必須同時證明：

- collection completion time 相對 `checked_at_ms` 未超出明示門檻。
- 整批來源完成時間跨度未超出明示門檻。
- public server time 與本機 clock skew 在明示門檻內。
- public-time clock sample 相對 `checked_at_ms` 的年齡在獨立明示門檻內，sample 不得位於 `checked_at_ms` 之後。
- 對需要 snapshot 語義的來源，有可驗證的同批 bounded sequential 讀取語義；至少包含 balance、positions、orders_pending、algo_pending，並各有 fills／fills_history 與 bills／bills_archive 來源。不能把單筆 `uTime`、transport source time 或 receive time 當整批 snapshot fence。

未注入 F1 policy 時，回傳 `freshness_policy_unset`／`snapshot_freshness_unverified`，不得為了通過而刪除告警。S1 後不再接受 caller 提供 `snapshot_semantics_verified=True`；gate 直接驗 report 的 S1 契約與 source/page timeline，缺證據即回傳 `snapshot_freshness_unverified`。

### 2.5 Window coverage

fills／bills 的目標窗口仍採 collection scope 的 inclusive `[window_start_ms, window_end_ms]`。gate 必須要求：

- 對應 endpoint 完整 pagination chain。
- 每個接受的事件 timestamp 位於窗口內。
- request filter／cursor 證據足以證明窗口起點到終點已覆蓋，而非「目前拿到的資料剛好都在窗口內」。
- fills、bills 任一來源 coverage 無法證明時，分別回傳 `fill_window_coverage_unverified` 或 `bill_window_coverage_unverified`。

W1 已定義 `w1-exact-window-pagination.v1`：`DemoReadTransport` 對 fills/fills_history/bills/bills_archive 保存與 scope 完全相等的 `begin/end`、`ts` event-time 與 `after=billId` cursor semantics；collector 僅在每個接受頁 evidence 一致時保存 endpoint window evidence。gate 直接驗 request evidence、完整 terminal page chain 與 report event `ts`，不再接受 caller 提供 `WindowEvidence(True, True)`。詳細條件見 [W1 window coverage 契約](reconciliation-w1-window-coverage-20260922.md)。

歷史 2026-09-22 Demo/F1 摘要沒有保存 W1 新欄位，因此不能以既有 timing 摘要補成 window pass；本片未因此重跑真實採集。

### 2.4 Dedicated Demo subaccount 證據邊界（2026-09-23 重核）

- `account_config` 的 `uid != mainUid` 只證明目前回應屬於某個子帳戶；`account_alias="okx-demo"` 是呼叫端邏輯標籤，兩者都不能單獨證明「這就是 CatOS 指定的專用 Demo 子帳戶」。
- formal report 對 `uid == mainUid` 維持 `not_subaccount -> scope_mismatch` fail closed；不因歷史 I-b-4 曾使用 Demo 主帳戶而放寬正式契約。
- 現行 local synthetic path 沒有獨立配置的 expected uid，也沒有本輪新取得的真實 private account identity evidence。因此 synthetic happy path 只能驗證 gate wiring，不能作為 dedicated-account production evidence。
- foreign responsibility 判定仍以 durable local ownership snapshot 對遠端非零 position、live/partial order、active algo responsibility 逐項比對；未歸屬者分別產生 `foreign_position`、`foreign_order`、`foreign_algo`，本地 unresolved／UNKNOWN 產生 `local_unknown`。
- 本輪重核未發現可在既有政策內再解除的 local correctness blocker。production readiness 仍需新一輪明確授權的真實唯讀 evidence，同時證明指定專用子帳戶身分與當下無 foreign／UNKNOWN responsibility；未取得新授權前不得自行採集或接 write。

## 3. Ownership 判定

### 3.1 Position

- 非零 OKX position 必須有 durable `(instId, posId)` ownership identity，且 quantity 與本地 snapshot 完全一致。
- 本地非零 position 但遠端找不到對應責任：`local_position_unverified`。
- 遠端非零 position 沒有本地 durable identity：`foreign_position` 或 `position_identity_unavailable`。
- flat 仍需證明沒有未結責任；不能以空 response 取代 collection completeness。

### 3.2 Ordinary orders

- 已有遠端 `ordId` 的本地 execution order 才能列入 `owned_exchange_order_ids`。
- `SUBMITTING`／`UNKNOWN` 且尚無遠端 `ordId` 時保留 `unresolved_local_ids`；不得盲重送、不得用 `clOrdId` 宣告已歸屬。
- 遠端 live/partial responsibility 不在 owned set：`foreign_order`。
- 本地未決責任在遠端證據無法解析：`local_unknown`。

### 3.3 P6 protection

- P6 啟用時，active/pending/uncertain/triggered responsibility 必須與 durable remote `algoId` 及其 child orders／fills 建立證據鏈。
- 現行 protection state 已保存 durable remote `algoId`；既存責任缺少該 identity 或保護條件不符，仍回傳 `algo_identity_unavailable`／`p6_protection_unverified`，不能以 request/client identity 代替。
- `TRIGGERED` 不是 flat 或 fills complete 的證明；維持 `p6_triggered_not_reconciled` 直到 child order/fill 對帳完成。
- P6 ratio=0 且沒有 active/pending/uncertain/triggered obligation 時，不要求建立不存在的遠端 algo ownership。

## 4. 風控基準與 external flow

### 4.1 R1 本機模擬路徑

保留 Asia/Taipei 00:00 日界，以當日首個合格觀測的實際時間與固定權益建立風控期間。候選須綁定 account／local-sim／day／Decimal equity／report digest，經 Journal 單 writer 交易內的完整 gate 驗證與 COMMIT 才可供風控使用；無需精確午夜證據。

`DayLedgerEvidence` 在下列共用欄位外帶入已驗證 `period_basis`；report 的 `risk_period_basis_id`、`risk_period_start_ms`、`day_flow_start_ms` 必須匹配基準證據，cutoff 與 report window 完全相等，完整窗口必須覆蓋起算點。`Snapshot.flow_basis_id`／`flow_start_ms` 再將風控小計綁定同一期間。

external flow 從完整 bill facts 依實際起算點重算；起算前不重複排除，恰在邊界須有綁定精確基準的前／後歸屬證據，否則 unavailable。實際 unknown／forbidden 活動、缺頁、freshness、ownership、UNKNOWN、成交與 P6 blocker 均保留。

首次／新日暫缺可等待及重試，不自動整天封鎖；合格前禁增倉。同日既存基準不得替換，持久化標記或本日執行責任存在卻缺少／損壞基準須停止恢復，不能假裝首次建立。新期間不解除 latch。報告明示「風控期間損益」與起算時間、`full_day=false`，不宣稱完整台北日日損。

### 4.2 共用欄位與舊 Demo／精確午夜來源

正式 gate 的 day ledger evidence 至少包含：

```text
trading_day_start_ms
baseline_equity_usdt
baseline_evidence_id
external_flow_usdt
flow_classification_id
unknown_flow_count
```

舊 Demo／精確午夜來源的必要條件如下；R1 的 `trading_day_start_ms` 仍是台北 00:00，但其固定 equity 與實際觀測時間由 4.1 的期間基準驗證，並不要求 equity 來自午夜：

- `trading_day_start_ms` 必須是目標交易日台北時間 00:00。
- E_0 必須是既有持久化且可追溯的日初基準；不能由目前 balance 倒推。
- external flow 僅使用明示 `(type, subType)` 白名單；未知分類不得當 0。
- account report 必須保存實際用來計算 external flow 的 `flow_classification_id` 與目錄 completeness 資訊；ID 必須與 `DayLedgerEvidence.flow_classification_id` 完全一致，不一致時以 `external_flow_mismatch` fail closed。依 2026-09-23 政策，完整目錄 coverage 僅供資訊；未使用的 type/subType 尚未分類不阻斷，實際流水出現 unknown／forbidden 仍阻斷。目錄 completeness 與採集／窗口 completeness 不可混為一談。
- `unknown_flow_count > 0`、bills coverage 不完整或 external flow unavailable 時阻斷。

歷史 E1 的「首次缺失即封鎖整天」已由 R1 取代；現有明示 `basis_blocked_day` 與舊 Demo provider 的封鎖行為仍保留，不由本輪自動清除或擴大採集授權。舊精確午夜來源仍須提供可追溯證據，不能拿目前 balance 冒充午夜。尚未定義的資金流 `(type, subType)` 生產分類仍回傳 `unknown_external_flow`，R1 不取消此條件。

歷史沿革：2026-09-22 曾要求 `FlowClassification.complete=true`，該阻斷政策已於 2026-09-23 取消；completeness 資訊與 classification ID 仍保留。不能從靜態範例自行推廣未知分類，也不必為未出現的 subtype 補齊整份目錄才可對帳。現行行為見 `reconciliation_gate._day_blockers`／`_period_blockers` 與 `test_partial_catalog_allows_known_flows_but_keeps_actual_blockers`；本輪已包含合成本機回歸，未重新採集。

## 5. Gate 輸出

輸出只包含固定 enum 與非敏感摘要，不輸出真實帳戶 ID、order/algo/position ID 或 raw response：

```text
version
bot_id
bot_revision
report_content_digest
ownership_snapshot_digest
reconciled
trade_authorized=false
blockers[]
warnings[]
evidence_id
```

`reconciled=true` 必須同時滿足：

1. scope 與 revision fence 完全一致。
2. collection／page evidence 完整且無 malformed/conflicting observation。
3. 所有現存 position/order/algo responsibility 已 durable attribution，且沒有 foreign／UNKNOWN。
4. fills evidence 完整且與 owned orders 累計一致。
5. freshness 與 window coverage 依明示 policy 驗證通過。
6. 適用來源的固定基準可追溯（R1 為已保存風控期間），external flow coverage 完整且沒有未知分類。
7. P6 若啟用，現存 protection lifecycle evidence 完整。

任一條件不成立即 `reconciled=false`。`warnings` 不得承載會影響帳務、ownership、風控或交易安全的問題；這類問題一律放 `blockers`。

## 6. Supervisor 消費規則

- gate 是 Supervisor 內部唯讀輸入驗證，不由 Worker 呼叫。
- gate blocked 時維持 Journal `RECONCILING`，不得呼叫既有 `Journal.reconcile()` 寫入「已對帳」狀態。
- gate pass 後才可把同一 revision 的結果轉成既有 `journal.Reconciliation`，寫入 ownership/fills reconciliation evidence。
- 寫入前再次比對 Bot revision；若已變動，整份 gate result 作廢。
- `Journal.reconcile()` 成功也不代表可交易；後續交易入口仍需 risk snapshot、latch、protection、pending/UNKNOWN 與明確 Demo 寫入授權全部成立。
- 合法減倉規則維持既有設計：風控被動超限時仍允許合法減倉；本契約不新增自動去槓桿。

## 7. 固定 blocker enum

第一版至少保留以下固定原因，後續可以新增但不得用自由文字取代：

```text
scope_mismatch
local_revision_changed
collection_incomplete
evidence_integrity_failed
record_invalid
mode_mismatch
ownership_snapshot_missing
local_bot_isolated
position_identity_unavailable
foreign_position
foreign_order
foreign_algo
local_position_unverified
local_unknown
fill_reconciliation_failed
freshness_policy_unset
snapshot_freshness_unverified
window_coverage_unverified
fill_window_coverage_unverified
bill_window_coverage_unverified
day_baseline_unverified
external_flow_unavailable
external_flow_mismatch
unknown_external_flow
unsupported_account_activity
algo_identity_unavailable
p6_protection_unverified
p6_triggered_not_reconciled
```

## 8. 第一版實作狀態

2026-09-21 已完成不改 schema 的第一版：

1. `Journal.reconciliation_snapshot()` 以單一 `BEGIN DEFERRED` WAL read snapshot 取得 bot revision、owner、execution order remote IDs、protection obligations 與 unresolved local IDs，finally rollback。
2. `catos.reconciliation_gate.evaluate()` 只吃 account report、ownership snapshot 與明示 policy/evidence，輸出固定 blocker enum；無 DB write、HTTP 或交易方法。
3. 合成測試已覆蓋 flat/no obligation 政策阻斷、revision race、foreign responsibility、UNKNOWN、缺 E_0／flow、P6 identity 缺口、report digest tamper；專屬 9/9。
4. freshness 生產數值未定時維持 fail closed，不提供生產預設值；E_0 缺失已採 E1；`trade_authorized=false` 固定不變。

新增 `local_bot_isolated` 與 `external_flow_mismatch` blocker，分別表示本地 replay conflict isolation 尚未解除，以及 day-ledger external flow 與 account report 觀測值不一致。兩者都屬 fail closed，不放 warnings。

## 9. Supervisor 離線消費接線

2026-09-21 已完成：

1. `LocalSupervisor.reconcile_report()` 只在 `RECONCILING` 狀態接受已在記憶體中的 `CollectionResult`；方法本身沒有 transport。
2. Supervisor 取得 durable revision 與 `Journal.reconciliation_snapshot()`，以 snapshot 的 `report_attribution()` 呼叫 `account_report.build_report()`，再交純函式 gate。
3. gate blocked 時不呼叫 `Journal.reconcile()`；gate pass 才轉成同 revision 的既有 `journal.Reconciliation`，`evidence_id` 使用 gate 結果，`trade_authorized` 仍固定 false。
4. gate pass 後、Journal write 前再次讀 `current_revision()`；若變動，重新產生 `local_revision_changed` verdict 並拒絕寫入。`Journal.reconcile()` 本身仍保留最終 stale revision 防線。
5. 專屬 3/3，既有 gate／Supervisor／execution-supervisor／Journal 46/46，這片合計 49/49 通過；全部使用 TemporaryDirectory、合成 collection 與 mock race。

`LocalSupervisor.reconcile_report()` 本身仍是無 transport 的離線 consumer；若直接呼叫，caller 必須明示提供 pre-collection ownership/revision fence 才能代表採集前 fence。`LocalSupervisor.collect_and_reconcile()` 已把這個 fence 放到 caller-injected bounded collection 之前，並在 collection 後沿用同一 snapshot 做 attribution/gate/prewrite 驗證。

## 10. 採集前 fence orchestration

2026-09-21 已完成：

1. `LocalSupervisor.collect_and_reconcile()` 在 bounded collection 前先取得 `Journal.reconciliation_snapshot()`；該 snapshot 同時固定 `bot_revision` 與 durable execution/protection responsibility digest。
2. collection 使用 caller-injected transport；本片驗證只提供 synthetic transport，沒有內建 HTTP、credential 或交易能力。
3. collection 後 `reconcile_report()` 使用原 snapshot 的 `report_attribution()` 建 report；若目前 snapshot digest 已不同，即使 bot revision 沒變，也 fail closed 為 `local_revision_changed`。
4. gate pass 後、Journal write 前再次核對 revision 與 snapshot digest；任一漂移都拒絕 `Journal.reconcile()`。
5. 新增三個測試：正常 pre-collection orchestration、collection 中 revision race、revision 不變但 local responsibility 改變。專屬 reconciliation 6/6，連同必要回歸共 52/52 通過；`trade_authorized=false` 不變。

## 11. 政策／Identity 決策後續

以下為 2026-09-21 歷史狀態：當時已定案並實作 E1、P6 `algoId` JSON 與 position P1 core schema v2。後續 F1 數值與分類縮減依上文更新；2026-10-20 R1 已取代首次暫缺的 E1 政策，並完成 local-sim 自測。真實 Demo HTTPS、帳戶採集與交易仍需另行授權。

## 12. E1 與 durable identity 實作

2026-09-21 使用者已定案並完成本機實作，以下保留歷史行為及原驗證；第 1 點首次暫缺的政策由 4.1 的 R1 取代，durable identity 保證維持：

1. E_0 採 E1：`risk.State` 持久化 `basis_blocked_day`。某台北日第一次需要 basis 卻缺失後，該日後續 basis 注入一律拒絕；只有下一台北日可接受新 verified basis。跨日仍不自動解除既有 latch。
2. P6 remote `algoId` 保存在既有 protection JSON；LIVE／CANCELED／TRIGGERED 證據缺 remote identity 直接拒絕。ownership snapshot 從 active／triggered report 取得 durable `algoId`；舊 obligation 缺 ID 保持 fail closed。
3. Position P1 使用 `ownership.remote_pos_id TEXT`。為避免與 Lot schema 7/8/9 的 `PRAGMA user_version` 衝突，新增獨立 `metadata.core_schema_version=2`；legacy core schema 在單一 Journal transaction migration，partial/future schema 拒絕開啟。
4. 非零 `Reconciliation` 必須同時帶 attributed bot 與 remote position identity；flat reconciliation 清除 remote identity。snapshot 只在 nonzero local position 時輸出 `(instId, posId)` attribution。
5. readonly fills 本身沒有 `posId`，因此不得從 fill 直接推導 identity；首次綁定只能使用下一節定義的 durable local lineage＋完整 account reconciliation 證據。缺足夠 evidence 時非零 position 仍由 `position_identity_unavailable` 阻斷。

E1／durable identity 切片原驗收 271/271 通過；未連 OKX、未讀 credential、未執行真實帳戶採集或交易。freshness 數值及 external-flow 生產白名單仍未定案。

## 13. Position `posId` 首次可信 bootstrap

2026-09-21 已完成本機實作：

1. `Journal.position_bootstrap_lineage()` 只從 durable `execution_orders`＋`execution_fills` 建立 lineage；order 必須已有 remote `exchange_id`，fill quantity 依本機 order direction 轉成 signed quantity，signed net 必須完整等於當前本機非零 position。
2. `build_position_identity_evidence()` 只接受完整 collection/report，要求唯一非零遠端 position 與本機 instrument／quantity 完全一致，且遠端全部 `(tradeId, ordId, fillSz, fillPx)` 與 durable local lineage 一對一相同。缺 fill、多 fill、重複 trade 衝突、ordId/size/price 不符、position 歧義皆拒絕。
3. `Journal.bind_remote_position_identity()` 在同一 transaction 重新核對 bot revision、ownership snapshot digest 與 fill lineage digest 後才寫 `ownership.remote_pos_id`；成功後遞增 revision、清除舊 reconciliation 狀態並回到 `RECONCILING`。
4. Supervisor 綁定成功後必須重新取得 ownership snapshot 並重新建立 account report／formal gate；collection 期間 revision 或 responsibility 發生變化時不得綁定。
5. `posId` 本身、symbol、quantity、tag、`clOrdId`、`algoClOrdId` 均不構成 ownership proof；歷史未解釋非零 position、外部 fills 或不完整 evidence 維持 fail closed。

最新驗證：直接受影響 123/123（Supervisor reconciliation 15、gate 10、Journal 16、execution 24、protection 19、account_report 39）＋既有核心回歸 196/196，共 319/319。全程只使用 synthetic transport、FakeExchange 與 TemporaryDirectory；未連 OKX、未讀 credential、未採集真實帳戶、未下單／撤單。`trade_authorized=false`、freshness 生產數值與 external-flow 生產白名單均未變更。
