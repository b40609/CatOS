# Reconciliation 政策／Identity 決策包

更新：2026-09-22。E1、P6 `algoId` JSON 與 `posId` P1 已完成。subtypes／分類證據見 [唯讀證據](reconciliation-readonly-evidence-20260922.md)；後續 [F1 freshness 補證](reconciliation-f1-freshness-evidence-20260922.md) 已完成並固定四個門檻。分類仍未完整，snapshot semantics 仍獨立 fail closed。

## 2026-09-22 evidence 結論（取代「尚未取得 subtypes」的舊現況）

- Demo subtypes GET 成功：32 類、185 組，完整非敏感目錄／SHA-256 已保存。後續逐組審查已把 52 組官方語意明確的交易／交割／強平／conversion activity 補為 `internal`；目前 63 組已分類、122 組 unknown、complete=false。上一輪 174 組 unknown 可再分成 52 組已解、19 組官方語意不足、103 組需新帳務／equity 邊界政策。詳見 [分類與 freshness 審查](reconciliation-classification-freshness-review-20260922.md)。
- F1 後續補證新增 4 次正常 production plan：20159–20216 ms；gate-adjacent report age 132–170 ms、clock sample age 66–85 ms、midpoint offset +2837～+2848 ms。另有真實 360 GET／179993 ms pagination stress，由 runtime deadline fail closed。
- F1 固定為 policy ID `f1-demo-2026-09-22`：`max_report_age_ms=1000`、`max_batch_span_ms=31000`、`max_clock_skew_ms=3000`、`max_clock_sample_age_ms=500`。gate 仍不藏 default，Supervisor 必須明示注入。
- 本輪 139/139 PASS；read-only 授權已執行完畢，沒有 Demo 交易／Live／帳戶修改／DB schema 變更／commit／push。分類剩餘清單與實際帳戶 gate 差異見 evidence，不把 collection_complete 當 reconciled。

## 1. Freshness

2026-09-22 後續使用者已核准 C1-B、C2-A、C3-B、C4-B；classification residual closure 後現行分類 153/185（10 external、89 internal、54 forbidden），32 unknown、complete=false。新增 21 組 public-evidence closure 加上 12 組 residual catalog closure，詳見 `reconciliation-classification-closure-20260922.md`。C1–C4 已完成 Sol 本機合成驗收。F1 四值亦於後續授權補證完成後定案；snapshot semantics 仍獨立未解。

### 現況

- `FreshnessPolicy` 已要求 `max_report_age_ms`、`max_batch_span_ms`、`max_clock_skew_ms`、`max_clock_sample_age_ms` 與 `checked_at_ms`，gate 沒有生產預設值。
- `CollectionResult.manifest.started_ms/completed_ms` 可驗證本機批次耗時；public server time 可驗證 clock skew。
- account `uTime` 是 record update time，不是整批 snapshot timestamp；transport receive time 也不能單獨證明帳戶狀態同時點。
- S1 已移除 caller 可直接指定的 `snapshot_semantics_verified` 布林值。formal gate 依 `s1-bounded-sequential.v1` 直接驗 account report 的 source/page timeline；`uTime`、transport source time、receive time 均不得作 snapshot fence。

### 候選方案

| 方案 | 規則 | 成本／限制 |
| --- | --- | --- |
| F1：固定保守門檻 | 對 report age、batch span、clock skew、clock sample age 設固定上限 | 最簡單；數值仍需用實測 bounded collection latency 校準 |
| F2：依 CollectionPlan 動態門檻 | 由 request/runtime budget 推導 batch/report 上限 | 參數較多，容易把「允許慢」誤當「資料新鮮」 |
| F3：僅用 record `uTime` | 直接以 balance/position/order update time 判 freshness | 不成立；靜止帳戶可長時間沒有更新，不能採用 |

### 已定案方向：F1

採 F1；不在 gate 寫死 fallback。2026-09-22 補證後固定 policy ID `f1-demo-2026-09-22`：`max_report_age_ms=1000`、`max_batch_span_ms=31000`、`max_clock_skew_ms=3000`、`max_clock_sample_age_ms=500`。正常 4/4 真實樣本只證明 F1 timing 可過，179993 ms stress 會被 freshness 阻斷；歷史摘要不因此取得 S1 snapshot pass。剛好等於各自門檻可通過；超過 1 ms、`checked_at_ms < completed_ms`、sample 位於 checked time 之後、雙向 clock skew 超限或 S1 source/page 契約不成立均 fail closed。四值由 Supervisor 明示注入。

驗收至少包含：剛好等於門檻通過、超過 1 ms 阻斷、`checked_at_ms < completed_ms` 阻斷、clock skew 雙向超限阻斷、clock sample age 超限／sample 在未來阻斷，以及 S1 缺必要 source、source interval 重疊／倒序、偽造 record/transport snapshot fence 時永遠阻斷。

## 2. 缺失 E_0

### 現況

- 已確認日損分母固定為 Asia/Taipei 00:00 的 E_0；當日入金、出金等外部資金流只進 C_t，不重設分母。
- risk state 已能持久化 `DayBasis`；正常重啟應沿用同一日既有 basis。
- 真正未解問題只剩「當日本來就沒有 durable E_0」的 bootstrap／遺失案例。

### 候選方案

| 方案 | 規則 | 風險 |
| --- | --- | --- |
| E1：禁止當日自動重建 | 缺 E_0 時保持 `day_baseline_unverified`，等下一個台北午夜取得 verified equity 後建立新日基準 | 最保守；首次啟動可能要等到下一日 |
| E2：人工 evidence bootstrap | 操作者提供經核對的當日 00:00 equity evidence，再建立 basis | 可縮短等待；需要額外人工證據契約與稽核 |
| E3：由目前 equity／bills 倒推 | 用現值與帳單推回午夜 equity | 不採用；缺完整價格、PnL、funding、fee、ADL／強平等路徑時不可證明精確 |

### 建議

v1 採 E1。`risk.State.basis_blocked_day` 會持久化「本日已缺失 E_0」狀態；同一台北日後續即使再提供 basis 也拒絕重建，只能在下一個台北日接受新的 verified basis。若之後確實需要同日 bootstrap，再獨立核准 E2；E3 維持禁止。

午夜建立新 basis 時仍須：verified equity、完整 external-flow 分類狀態、台北日界一致、evidence_id 可追溯。跨日、重啟或入金不得解除既有 Soft／Hard／manual latch。

## 3. External-flow `(type, subType)` 白名單

### 現況

- `okx_readonly.external_flows()` 已只接受明示 `(type, subType) -> external|internal` 映射；未知類別保留並阻斷。
- `account_report` 已保留 bill `type`、`subType`、`ccy`、`balChg`，只對 USDT 計入目前 v1 external-flow 總額。
- 已新增 `FlowClassification`／`FlowClassificationEntry`：`flow_classification_id` 由版本名加 mapping／evidence／completeness canonical digest 組成，同名但內容、證據或 completeness 不同會得到不同 ID；account report 保存實際使用的 ID 與 completeness，formal gate 要求 ID 與 DayLedger 完全一致，且 completeness 必須明示為 true。
- 公開 OKX API v5 `Get bill types` 靜態範例目前只明示 `type=1` Transfer 的 `subType=11` Transfer in、`subType=12` Transfer out；本機只把這兩項收進 `okx-v5-static-transfer-2026-09-21` 並分類為 `external`。任何其他 code 仍 unknown。

### 分類原則

- `external`：不是策略損益來源、但改變受管帳戶權益的資本移入／移出；例如經官方 code 表確認的存入、提領、跨帳戶資金轉入／轉出。
- `internal`：策略／交易活動本身已反映於 equity 的項目；例如經官方 code 表確認的交易費、funding、已實現損益、結算等。這些不能再從日損分子重扣一次。
- 任何未列入版本化白名單的 `(type, subType)`、非 USDT、語意不明或官方定義改版，維持 `unknown_external_flow`。

### 建議

版本化資料契約已建立：`flow_classification_id` 綁定不可變 mapping、evidence 與 completeness，每個 entry 附 evidence 描述；raw dict 仍可供既有離線測試使用，但沒有 classification ID／completeness，不能滿足 formal day-ledger gate。partial mapping 一律 `complete=false`；不能因第一次 Demo read-only bills 只出現已知 code，就把尚未取得官方完整 type/subType 對照的分類表視為完整。

官方文件指出完整 type/subType 對照由 `GET /api/v5/account/subtypes` 提供。本輪只讀公開文件，未讀 credential、未呼叫帳戶 endpoint；因此完整生產白名單仍未定案。若官方資料不足，實際未知 code 仍維持 blocker，不以名稱猜測。

## 4. Durable remote identity

### 4.1 `algoId`

現行 `protection` 已以 `state_json` 持久化 active/pending/report 狀態，因此 remote `algoId` 可新增在既有 protection JSON 契約，不需要 SQLite table/column migration。必要修改面：

1. protection `Report` 增加 remote `algo_id`，只接受交易所回應中的明示 ID。
2. create/query/amend/cancel 成功或查詢證據將同一 `algoId` 持久化至 active/pending/report。
3. restart snapshot 將 durable `algoId` 提供給 `owned_exchange_algo_ids`。
4. 舊 state 有 active/pending obligation 但沒有 `algoId` 時繼續 fail closed；不得用 `algoClOrdId`、tag 或 symbol 補猜。

已定案並實作。Protection `Report` 的 LIVE／CANCELED／TRIGGERED 證據必須帶明示 remote `algoId`；LIVE active state 持久化 `algo_id`，restart reconciliation snapshot 會輸出 durable `owned_exchange_algo_ids`。舊 active/pending responsibility 缺 `algoId` 時仍 fail closed，不用 `algoClOrdId` 補猜。

### 4.2 `posId`

現行 `ownership` 只有 `position` Decimal、open/unknown counters 與 reconciliation evidence，沒有可正確承載 remote `posId` 的欄位。`evidence_id`、`config_json`、protection JSON 都不是合適替代欄位，不能挪用。

候選方案：

| 方案 | 做法 | 評估 |
| --- | --- | --- |
| P1：`ownership` 新增 `remote_pos_id TEXT` | 單 Bot／單 contract 最小欄位 | 最簡單，但需正式 schema migration；後續若擴多 position identity 彈性低 |
| P2：新增 remote ownership table | `(bot_id, inst_id, kind, remote_id, state/evidence)` | 模型較完整，但對 v1 單 Bot 明顯較重 |
| P3：沿用既有 JSON／evidence 欄位 | 不升 schema | 語意錯置且容易被 reconciliation 覆寫，不採用 |

已定案並實作 P1。因 `PRAGMA user_version` 同時承載 Lot 7/8/9，core migration 改由 `metadata.core_schema_version` 管理；目前 core v2 新增 `ownership.remote_pos_id TEXT`，不改 Lot `user_version`。舊 DB 缺 core marker／欄位時在同一交易原子 migration；partial、future 或不一致 core schema 一律拒絕開啟。

`posId` 綁定規則固定不變：只能由 Supervisor 在「本地已持久化自有成交造成的非零 position」之後，以完整 account reconciliation 證據首次綁定；既有非零遠端 position若本地沒有可完整解釋當前 position 的 durable fill lineage，不能自動 claim。readonly fills 契約本身沒有 `posId`，所以目前 bootstrap 採兩段證據：本機 durable `(exchange order id, trade id, signed fill quantity, fill price)` lineage 必須淨額完全等於 local position；遠端 collection 必須只有唯一相符非零 position，且全部 `(tradeId, ordId, fillSz, fillPx)` 與本機 lineage 一對一完全一致。任何缺漏、額外 fill、重複 trade 衝突、ordId/size/price 不符、position 歧義或 collection race 都不綁定。成功綁定會遞增 revision 並重新跑 formal gate。flat reconciliation 會清除 `remote_pos_id`。

## 5. 定案狀態

1. E_0：E1，已定案並實作。
2. `algoId`：沿 protection JSON 保存 remote ID，已定案並實作，不升 SQLite table schema。
3. `posId`：P1，已定案並完成 core schema v2 migration／durable storage／首次可信 bootstrap。
4. external-flow：versioned mapping／classification ID 綁定已完成；公開靜態文件只足以固定 Transfer 11/12 的部分 mapping，完整生產白名單仍需當期 OKX `/api/v5/account/subtypes` 證據。
5. freshness：F1 已完成真實 Demo read-only 補證並定案為 `1000 / 31000 / 3000 / 500 ms`；gate 仍要求 Supervisor 明示注入，snapshot semantics 不隨數值定案自動成立。

external-flow 剩餘 32 unknown 與 snapshot semantics 仍需外部／契約證據。未注入 F1 時 `freshness_policy_unset` 維持；`snapshot_freshness_unverified`、`unknown_external_flow` 及缺 durable position/algo identity 的 blocker 行為不變。`trade_authorized=false` 不變。

## 6. 2026-09-21 實作驗收

本片已修改 `risk.py`、`protection.py`、`journal.py`、`reconciliation_gate.py`、Supervisor 接線與專屬測試；沒有執行 Demo HTTPS、讀 credential、採集帳戶或下單／撤單。

- E1：同日缺失 basis 後拒絕同日重建，blocked day 可序列化／重啟，下一台北日才可建立新 verified basis。
- P6：LIVE／CANCELED／TRIGGERED remote identity 必須明示；active `algoId` 可跨重啟並進 ownership snapshot。
- P1：core schema v2 原子加入 `metadata.core_schema_version` 與 `ownership.remote_pos_id`；Lot `PRAGMA user_version` 7/8/9 不變，partial migration fail closed。
- Freshness／flow evidence：新增門檻等號與超 1 ms、雙向 clock skew、snapshot semantics 的 fail-closed 測試；新增 immutable `FlowClassification`、report classification ID 與 DayLedger ID 一致性檢查。公開靜態 OKX 文件只收 Transfer 11/12，未擴張成完整白名單。
- E1／durable identity 切片原驗收 271/271 通過。後續 `posId` bootstrap 切片將 Supervisor reconciliation 擴充至 15 個案例，補上 exact bind、fill mismatch、missing/extra fill、duplicate conflicting trade、ordId mismatch、local signed-net mismatch、ambiguous position 與 collection race；最新直接受影響 123/123＋既有核心回歸 196/196，共 319/319。
