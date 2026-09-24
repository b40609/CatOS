# catOS 自動策略主線：首輪阻斷盤點

2026-09-21。使用者已同意自動跑策略優先、Yaozi 限定收尾。此片為 Astra 靜態 assessment，非 Demo 驗收或新帳戶存取授權。

## 目標與已知基線

第一個成果為單 Bot、單合約、既有 SMA 策略的 Demo 全閉環：Closed Bar → Worker 意圖 → Supervisor 風控／持久化 → 委託 → 成交 → 重啟對帳。Yaozi 與進一步 Virtual Lots 不列必要前置。現有 Decimal、固定 tag、唯一交易出口、UNKNOWN 保留及風控鎖存不縮減。

D–G 已有模擬驗收；I-b-4 歷史採集完成但未對帳。9/15 修補文件記錄多項程式／合成測試已寫入，不能以更早通過數字替代目前版本验收。本輪未核對 Git，也未執行測試。

## 阻斷分類與最小交付

| 項目 | 靜態證據／原因 | 下一個最小交付 | 驗證成本與界線 |
|---|---|---|---|
| balance 解碼 | account_report 已有固定 field/reason 診斷，demo_collection 已聚合安全摘要；歷史原始回應未保留，不能確診當時壞欄位 | 先驗收既有診斷與拒絕路徑；不猜空字串可轉零 | account_report、demo_collection 合成測試，不讀真實憑證 |
| 來源衝突／分頁證據 | 已有 A/B/A 分版本 observations、cursor chain 與 completion gates 修補 | 驗證各版本來源不混合、不完整證據不能給完整總額 | account_report 專屬測試，必要時 collection 回歸 |
| mode_mismatch | 檢查 posSide、mgnMode/tdMode、account_config；config gate 通過不代表每筆責任均為 cross/net | 保留拒絕；後續若需定位，增加固定欄位診斷，不輸出 ID／值 | 合成 config 合格但其他事實不合格的案例；不可自動改帳戶 |
| 責任歸屬 | runner 呼叫 decoder 未提供持久化 local ownership，且固定加入 local_attribution_not_loaded | 下一份對帳契約定義從 Journal 提供 owned orders/positions/algos 與 unresolved IDs 的一致快照 | 需獨立契約及合成對照；不可憑 tag、空集合或同 symbol 接管陌生責任 |
| freshness／window | account_report 固定加 freshness_unverified/window_coverage_unverified；okx_readonly.evidence_issues 僅接受明示測試參數 | 提出各來源時間語義、同批快照／完整窗口證明及明示門檻方案 | 門檻待定，不以 uTime 直接當快照新鮮度；不刪告警求通過 |
| 日初基準／資金流 | 固定 day_baseline_unverified；external_flows 依明示白名單，未知保留 | 提出 E_0 來源、台北日界、重啟／缺失基準及外部流量分類方案 | 固定分母／鎖存已定；基準重建與未知分類不可自行定案 |
| P6 保護責任 | 保護參數與 effective 子單缺口可被診斷，但非完整交易所生命週期對帳 | 保留 P6 未驗證，設計保護單與子委託／成交證據連結 | 不自動處置 foreign_algo；真實建立／更新／取消驗收後續另授權 |
| 真正 reconciliation gate | account_report report 及 runner summary 均固定 reconciled=false、trade_authorized=false | 保留觀測報告；另規格化正式對帳判定及 Supervisor 消費方式 | 避免把純 decoder 當交易許可；不可直接將兩個布林改 true |
| 合法減倉／恢復交叉 | 9/15 已修 journal、execution、protection 邊界，驗收狀態需確認 | 最小受影響回歸，不重寫既有機制 | execution／protection；journal 已有 S10 歷史回歸但非整體目前基線證明 |

## 交給 Sol 的第一批驗收

先核對當前未提交來源及固定受測版本，避免驗收中同檔再被修改。只使用合成資料與臨時路徑，禁止執行 demo_collection 的 CLI 採集旗標。建議第一批：

```text
python -B -m unittest tests.test_account_report tests.test_demo_collection tests.test_okx_readonly tests.test_okx_collection -v
```

執行前先靜態核對測試不觸及實際 loader／HTTPS：loader 案例須以臨時檔或 mock 取代指定真實來源。失敗交付精確案例，Astra 修補後只重驗受影響部分。HTTP transport 若無變更／失敗依賴不額外擴測；交易出站交叉另依 execution／protection 受影響測試驗收。不得把第一批通過宣稱整個 Demo gate 完成。

驗收交付需記錄檔案版本或 hashes、命令、通過／失敗數、是否有 skip、環境，以及未驗證項目。Git 工作只由 Sol 執行；不自動提交／push。

### 2026-09-21 Sol 第一批離線驗收

- 固定基線：branch `main`，HEAD `cc216f7910fc786afe39776daacf1d10737cc66d`；Python 3.14.6，Windows 本機工作目錄 `C:\Users\user\Desktop\CatOS_Astra`。
- 受測來源 SHA-256：
  - `catos/account_report.py`：`e1eaba8e4427da709d84cd40a836604897a2cd16f1babc3181ab1ebaa6bc3eb7`
  - `catos/demo_collection.py`：`3c6d122ea9306db27cd89b6b15c583b9ae5b74ccecd366d49e579360eeaf0fae`
  - `catos/okx_readonly.py`：`5b89be5cd51de456fc7a5f32460189d80eb7ddcb9c2c73e68700fed386bc3288`
  - `catos/okx_collection.py`：`4bd0e0afe77d2d8904351a6d919359202844966dee5d5b35a8a7e0da94a83a3a`
  - `catos/okx_http.py`：`1345bf2128bd35c2d065d7b246eb8e72e669ff990ff55435e5080f3b06330f10`
- 測試 SHA-256：
  - `tests/test_account_report.py`：`67b3fec0636b7903d90a058d2da414eaf52cbde6b3260c12b799e188517edf4f`
  - `tests/test_demo_collection.py`：`bc6862515b84725d360d1dc2ec546868015c20665b8ec4736a3825e28f5f380b`
  - `tests/test_okx_readonly.py`：`3b6d32d564e308baefa740c7e73edb9ae1fafeade049b272320174953c9c50f2`
  - `tests/test_okx_collection.py`：`aa31526ef599a8689595ac19adf8f116acec496dcec054be9da6ce7086d5b3cb`
  - `tests/test_bounded_pagination.py`：`6cd4564ddc48c25f3680a936235e68077b7c8a985804c68cd27b1d6b044e119c`
- 靜態核對：四組測試均使用合成 transport／fixture；credential loader 測試只把 `AUTHORIZED_CREDENTIAL_FILE` patch 到 `TemporaryDirectory`。runner 案例均明示注入 synthetic sender，未落到預設 HTTPS sender。
- 原建議單行命令實際執行後，前 67 個案例通過，但 `tests.test_okx_collection` 載入時因 `from test_bounded_pagination import FakeClock` 找不到頂層模組而產生 1 個 import error。這是測試啟動方式問題，未出現產品邏輯案例失敗。
- 依 repo 既有慣例改用 `python -B -m unittest discover -s tests -p <test_file> -v`，逐一執行四組：`test_account_report.py` 39/39、`test_demo_collection.py` 12/12、`test_okx_readonly.py` 16/16、`test_okx_collection.py` 13/13，共 80/80 通過，0 failure、0 error、0 skip。
- 驗收全程未執行 `demo_collection` CLI 採集、未讀真實 credential、未連 OKX、未讀／寫交易 DB、未下單／撤單、未變更帳戶設定。測試前後既有工作樹變更集合一致；未由測試新增檔案變更。
- 本批仍未驗證：正式 reconciliation gate、ownership snapshot、freshness/window 門檻、E_0／external flow 政策、P6 真實生命週期、execution／protection 交易出站交叉、Demo 下單閉環。

## 正式唯讀對帳契約

2026-09-21 已完成 [正式唯讀 Reconciliation Gate 契約](reconciliation-gate-contract.md)。契約固定 revision fence、Journal ownership snapshot、freshness/window evidence、E_0／external flow、P6 responsibility、blocker enum 與 Supervisor 消費方式；`trade_authorized` 固定 false。

靜態核對確認兩個不能猜測的 durable identity 缺口：現行 Journal 未保存 OKX position `posId`，protection state 也未保存遠端 `algoId`。因此非零 position／現存 protection responsibility 在缺 identity 時必須 fail closed；本片不以 symbol、tag、client ID 補猜，也不升 DB schema。

仍待使用者定案的政策只有 freshness 數值門檻、缺失 E_0 重建規則及未知資金流分類。這些待決項目不得阻止先實作純本機 ownership snapshot／gate，但未定案前對應案例必須維持 blocker。

### 2026-09-21 ownership snapshot＋gate 第一版

- 新增 `catos/reconciliation_gate.py`：純函式 gate 與明示 `FreshnessPolicy`、freshness/window/day-ledger evidence；無 HTTP、credential、DB write 或交易方法。未知 report discrepancy 一律 fail closed。
- `Journal.reconciliation_snapshot()` 使用 `BEGIN DEFERRED` 在單一 WAL read snapshot 取得 bot revision、local position、durable exchange order IDs、unresolved local IDs、execution counts 與 P6 obligation；finally rollback，不修改 DB。
- 現行 schema 仍沒有 remote position `posId`／protection `algoId`；非零 position 或現存 P6 responsibility 缺 durable identity 時，分別回傳 `position_identity_unavailable`、`algo_identity_unavailable`／`p6_protection_unverified`，不猜 ownership。
- `trade_authorized` 永遠 false；合成完整 evidence 可使 `reconciled=true`，只證明 gate 判定邏輯可達，不代表目前生產 freshness/window/E_0 政策已核准。
- 專屬 `test_reconciliation_gate.py` 9/9；必要回歸 `test_journal.py` 14/14、`test_execution.py` 24/24、`test_protection.py` 19/19、`test_account_report.py` 39/39，合計 105/105、0 failure。另以真實 `account_report.build_report()` 合成輸出驗證 content digest 相容；`git diff --check` 通過。
- 固定檔案 SHA-256：`catos/reconciliation_gate.py` = `c9f28946cc99e06f374feff96bf1a7f13b6c98b50ed900fc5bf7678ab7805ed3`；`tests/test_reconciliation_gate.py` = `9ddc9c5323b38eee4257289550f6cde5b0caab19682cc5c0b419099e42f8d300`。`catos/journal.py` 位於共用髒工作樹，另含既有 Lot S10/S11 變更，不把整檔 hash 當成本片獨占基線。

### 2026-09-21 Supervisor 離線消費接線

- 新增 `LocalSupervisor.reconcile_report()`：僅在 `RECONCILING` 消費已在記憶體中的 `CollectionResult`；由 Supervisor 取得 revision／ownership snapshot、以 `report_attribution()` 建 account report、執行 formal gate，通過後才轉 `journal.Reconciliation`。
- gate pass 後、Journal write 前再次讀 durable revision；race 回傳 `local_revision_changed` 並拒絕寫入。`Journal.reconcile()` 仍保留最終 stale revision 防線。
- 專屬 `test_supervisor_reconciliation.py` 3/3；必要回歸 gate 9/9、Supervisor 14/14、execution-supervisor 9/9、Journal 14/14，合計 49/49、0 failure。
- 此方法沒有 transport；目前 `revision_before` 是離線消費入口 fence，不是 HTTPS 採集開始前 fence。沒有讀 credential、沒有連 OKX、沒有交易、沒有 schema 變更。

### 2026-09-21 採集前 fence orchestration

- 新增 `LocalSupervisor.collect_and_reconcile()`：只接受 caller-injected `CollectionPlan`／transport；先在 sole-writer 邊界取得 ownership snapshot 與 revision，再於 operation 外執行 bounded collection，最後把原 fence 傳入既有 `reconcile_report()`。
- `reconcile_report()` 現可接受明示 pre-collection ownership/revision fence；collection 後、report 後與 Journal write 前都重取 durable snapshot/revision。revision 改變，或 execution/protection responsibility 在 revision 不變時造成 snapshot digest 改變，都回傳 `local_revision_changed` 並拒絕寫 reconciliation。
- 專屬 `test_supervisor_reconciliation.py` 由 3/3 增至 6/6；連同 gate 9/9、Supervisor 14/14、execution-supervisor 9/9、Journal 14/14，共 52/52、0 failure。`py_compile` 與 scoped `git diff --check` 通過。
- 測試 transport 完全合成；沒有真實 HTTPS、credential、帳戶採集、交易或 schema 變更。此片只封閉 orchestration/race 邊界，不把待決 freshness／E_0／flow 政策視為已核准。

下一個阻斷已整理成 [政策／Identity 決策包](reconciliation-policy-decision-pack.md)：E_0 建議缺失即封鎖至下一個台北午夜 verified baseline；`algoId` 建議沿 protection JSON 持久化；`posId` 建議 ownership 專用欄位並另開 schema migration。external-flow 生產 code 與 freshness 數值仍需外部／實測證據後定案；未定案前不升 schema、不接真實 Demo HTTPS、不交易。

本片完成：首輪阻斷盤點、Sol 第一批 80/80 離線驗收、正式 gate 契約、ownership snapshot＋純函式 gate、Supervisor 離線消費接線與採集前 fence orchestration。尚未完成：待決 freshness／E_0／flow 政策、durable posId/algoId、Demo 閉環。詳見 [目前入口](current-handoff.md)。

### 2026-09-21 E1／durable identity 實作

- 使用者已定案 E1：缺失日初 basis 後以 `basis_blocked_day` 鎖住該台北日，拒絕同日重建；狀態跨重啟保存，下一台北日才可接受新 verified basis。
- P6 `algoId` 已接入既有 protection JSON 與 ownership snapshot；LIVE／CANCELED／TRIGGERED 缺 remote identity 直接拒絕，舊 obligation 無 ID 仍 fail closed。
- Position P1 已新增 core schema v2：`metadata.core_schema_version`＋`ownership.remote_pos_id`。migration 不改 Lot `PRAGMA user_version` 7/8/9；legacy 原子升級，partial/future core schema fail closed。
- 非零 position 的 Journal reconciliation 現要求 durable remote identity；flat reconciliation 清除 ID。readonly fills 本身不含 `posId`，但首次可信 bootstrap 已改由 durable local execution-fill lineage＋完整 account reconciliation 交叉證明，不從 symbol／quantity／tag 猜 ownership。
- `posId` bootstrap 只在 local signed fill net 完整等於本機 position、遠端唯一非零 position quantity 相符、且遠端 `(tradeId, ordId, fillSz, fillPx)` 與本機 durable lineage 一對一完全一致時綁定；成功後遞增 revision 並重建 snapshot/report/gate。缺漏、多餘、衝突或 race 全部 fail closed。
- 最新直接受影響 123/123＋既有核心回歸 196/196，共 319/319；無 Demo HTTPS、credential、帳戶採集或交易。
- freshness 生產數值與 external-flow `(type, subType)` 白名單仍未定案，對應 blocker 不變。

### 2026-09-22 formal readiness 收斂

後續工作已大幅超過 2026-09-21 首輪盤點：S1/W1/F1、Supervisor pre-collection fence、durable posId/algoId、E1、Verified E₀ local synthetic lifecycle 與 R1–R4/D2 均已有實作／回歸。最新 production classification 為 166/185：10 external、102 internal、54 forbidden、19 unknown，`complete=false`。

本輪在既有 local-only 邊界重跑 5 個代表性 formal cases，5/5 OK：

- synthetic complete classification＋verified E₀＋F1/S1/W1 evidence 可 `reconciled=True`，且 `trade_authorized=False`。
- production 166/185 classification 仍會對未分類 bill 以 `unknown_external_flow` fail closed。
- 缺 day-ledger／verified E₀ 會以 `day_baseline_unverified` fail closed。
- S1 source interval overlap 會以 `snapshot_freshness_unverified` fail closed。
- durable Verified E₀ provider 的正常 formal path 可通過。

目前沒有額外 local reconciliation correctness blocker 可在既有政策下直接解除。剩餘 production blockers 分成四類：

1. **需要新外部證據／政策**：19 個 flow subtype unknown，不能用名稱或相鄰編號猜分類。
2. **已核准保持阻斷**：D1-A 精確午夜 E₀ 尚無 production 建立來源，不能用近午夜觀測替代。
3. **實際環境條件**：dedicated Demo subaccount 與 foreign responsibility 必須由新一輪明確授權的真實唯讀 evidence 驗證。
4. **寫入安全邊界已定案、真實寫入尚未授權**：2026-09-23 使用者已採 T1-A／T2-A／T3-A，local `DemoTradeGrant` fence 已實作；formal gate 的 `trade_authorized` 仍固定 false，reconciliation PASS 不等於 Demo POST permission。

2026-09-23 dedicated Demo subaccount／foreign responsibility 重核：formal report 對主帳戶 `uid == mainUid` 固定映射為 `scope_mismatch`；遠端未歸屬 position/order/algo 與本地 unresolved／UNKNOWN 均維持 fail closed。另確認 `uid != mainUid` 只證明「某個子帳戶」，`account_alias` 亦只是邏輯 scope，現行 local path 沒有獨立 expected uid，因此 synthetic pass 不構成指定專用子帳戶的 production identity evidence。本輪不修改交易程式、不新增帳戶政策，也不沿用歷史 Demo 主帳戶採集作專用子帳戶證據。最小回歸：`test_demo_reconciliation.py` 30/30、`test_reconciliation_gate.py` 16/16、`test_account_report.py` 42/42 OK；未執行任何 OKX private network／real Demo collection。

2026-09-23 後續已完成 [Demo Trade Authorization 決策包](demo-trade-authorization-decision-pack.md) 的 T1-A／T2-A／T3-A 定案與本機實作。`DemoTradeGrant` 為 in-memory、綁 account/Bot/instrument/reconciliation evidence/revision/時間/額度；restart 不復活 entry permission，entry cutoff 後仍允許既有 reduce-only/cancel/P6 cleanup。新增 6 個 acceptance tests 全數通過，並驗證 pre-check 後若在 prepare→transport handoff 間跨過 cutoff，request 會 durable `ABORTED` 且不呼叫 FakeExchange；連同 formal／execution／protection 等 14 個關聯模組合計 263/263 OK，`py_compile` 通過。仍未接 OKX Demo transport，亦未取得任何真實寫入授權。
