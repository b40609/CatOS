# YAOZI Live On-chain Provider — Schema v12 Proposal / Approved Implementation

## 觸發原因

目前 `onchain_activity` 只保存 reducer 結果：`symbol / chain / observed_at_ms / outgoing_distinct / baseline / ratio / state`。它沒有 provider、監控 address scope、fetch issues 或 coverage/provenance。

因此即使現在接上真實 address provider，寫入後也無法從 SQLite 證明：

- 資料來自哪個 provider。
- 本次實際監控哪些 address。
- 7 日 baseline 使用哪些完整日來源事實。
- provider 是否只回部分頁面、是否截斷或有 fetch issue。
- activity row 是 live provider-derived 還是既有 fixture/offline materialization。

`/intel/source-coverage` 目前因此固定回 `provider_identity_status=not_recorded_in_schema`，`/intel/onchain` 固定回 `provider_status=no_live_provider_configured`。

## 最小 v12 方案

保留既有 `onchain_activity` 不動，新增一張 source-run evidence table。這樣 reducer contract 與既有資料不需要重寫，而且 provider 失敗時仍可保存 run evidence。

```sql
CREATE TABLE onchain_source_run (
    source TEXT NOT NULL,
    symbol TEXT NOT NULL,
    chain TEXT NOT NULL,
    observed_at_ms INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ok','issues')),
    source_scope_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    issues_json TEXT NOT NULL,
    PRIMARY KEY(source, symbol, chain, observed_at_ms)
) STRICT;
```

欄位語義：

- `source`：明示 provider identity，例如未來選定的 keyless public provider 名稱。
- `source_scope_json`：normalized chain/network、排序後的 public monitored addresses、address count、identity rule。不得保存私鑰、API key 或簽名資料。
- `evidence_json`：provider-derived 完整日 `outgoing_distinct` 計數與其 source date/window、pagination/coverage proof。現行 reducer 使用目標日 + 前 14 個完整日；Decimal 衍生 ratio 仍只由現有 reducer 計算。
- `issues_json`：bounded fetch/parser/coverage issues；失敗 run 也要保存，因此不能只把 metadata 塞進 `onchain_activity`。

成功 collection 的同一 `observed_at_ms` 會：

1. 寫一筆 `onchain_source_run`。
2. 用 evidence 中的 current day + previous complete days 呼叫既有 `reduce_onchain_activity()`。
3. 寫既有 `onchain_activity`。

失敗 collection 只寫 `onchain_source_run(status='issues')`，不製造假的 `onchain_activity`。

## Read surface 調整

- `/intel/source-coverage`：on-chain source 改讀最新 `onchain_source_run`，輸出 explicit `source`、coverage status、provider identity status 與 issues。
- `/intel/onchain`：只有 latest successful source-run 能和同 anchor activity 對上時，`provider_status=materialized_live_source_run`；否則保持 unknown/unavailable。
- YAOZI 日界、address universe、whale taxonomy 若沒有第一方公開證據，仍標 `unknown_unpublished`，不由 provider 的 day boundary 或 address list反推。

## 預計修改範圍

- `catos/market_intel.py`：`SCHEMA_VERSION 11 -> 12`、新增 table/migration、source-run writer。
- 新增 `catos/market_onchain.py`：固定 public host、bounded pagination、address-scope validation、provider parser。
- `catos/market_api.py`：source coverage / on-chain provider status。
- 最小 tests：schema migration、source-run exact replay/conflict、provider failure persistence、successful reducer linkage、API diagnostics。
- `docs/market-intel.md`、parity matrix、handoff。

## 不在這次 v12 內

- 不新增 holder/cost reconstruction。
- 不新增 social metric persistence。
- 不推導 YAOZI 私有 whale threshold、address universe、ranking 或 taxonomy。
- 不接任何需要讀取本機 API key、私鑰或 wallet credential 的 provider。
- 不修改交易、風控、Supervisor/Worker 邊界。

## 驗收條件

- live provider 使用固定 public host、無憑證 GET、timeout/body/page 上限。
- source-run 可以 deterministic replay；同 identity 不同內容必須 conflict。
- provider failure 不生成 activity。
- successful run 的 provider/address scope/完整日 evidence 可從 SQLite 重建。
- `/intel/source-coverage` 不再把 live on-chain provider identity 顯示成 `not_recorded_in_schema`。
- focused tests、market affected regression、`py_compile`、`git diff --check` 全部通過。

2026-09-21 使用者已明確核准此 schema change。v12 table、writer、read diagnostics、11→12 migration 已實作，主 `outputs/catos-market-intel.sqlite` 已升至 v12；focused tests 58/58 通過。

2026-09-21 後續 provider slice 已新增 `catos.market_onchain`：固定 `eth.blockscout.com/api/v2/tokens/{token}/transfers`、caller-supplied 24h day boundary、目標日 + 前 14 日完整 coverage gate、cursor/page budget 與 fail-closed persistence。Blockscout WBTC token-transfer endpoint 已以 keyless raw GET 得到 HTTP 200、50 筆 items 與 `block_number/index` cursor，證明公開 provider endpoint 與目前 payload contract 可用；同 adapter 的 live collector 呼叫仍被 runtime safety review 攔截，且高活動 WBTC 單頁只覆蓋約數分鐘，因此沒有宣稱 15 日完整 live window 或寫入主 DB。partial/truncated run 一律只保存 source-run evidence，不產生 `onchain_activity`。
