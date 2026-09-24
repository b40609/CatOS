# Demo D1-Q1：quiescent interval exact-equivalence E₀ 決策稿

日期：2026-09-24。狀態：**使用者已核准 Q1-B；D1-Q1 已完成 local implementation／synthetic verification，尚未產生新的 production Q1 evidence**。

## 問題

現行 D1-A 要求 Asia/Taipei 00:00 的 exact-midnight Trading Account equity。OKX 現行公開／private API 沒有可指定歷史 timestamp 的完整 Trading Account equity snapshot；`account/balance` 與 `account-position-risk` 只提供當下狀態／update time，因此「午夜啟動 GET」或「午夜後第一筆 balance」本身都不能滿足 D1-A。

目前 Demo 帳戶已清成 acctLv=2、`net_mode`、單一 USDT、無 positions／ordinary orders／algo orders。這使一個更窄、可驗證的等價方案成立條件可以具體化。

## D1-Q1 提案

只允許 **bootstrap day 的 dedicated Demo account** 使用 quiescent interval exact-equivalence：

1. 目標日界固定 Asia/Taipei 00:00，沒有取樣時間容差政策。
2. 採樣時 account config 必須是已綁定 expected UID、dedicated subaccount、acctLv=2、`net_mode`。
3. balance 必須只有單一 USDT detail、無 liability、無 frozen／order-frozen，且 `details[].eq` 為有效 Decimal。
4. 從該日 00:00 到採樣 cutoff 必須有完整 endpoint/window evidence，且 positions、ordinary pending、algo pending、orders history、fills 全部沒有任何責任或成交。
5. 同一 `[00:00, cutoff]` 的 bills 必須完整，且 **零筆 balance-changing bill**。只要有任何 bill、未知／forbidden flow、coverage gap 或時間邊界歧義即拒絕；不做 `balChg` 加減回推。
6. OKX bills 契約定義 bills 為所有會改變 account balance 的 transaction records；在單一 USDT、零 position/order/fill 且完整 bills=0 的前提下，可證明 account equity 在整個 `[00:00, cutoff]` 不變。因此 cutoff 採樣的 USDT `eq` 與 00:00 E₀ 數值相同。
7. 新 evidence source 建議命名 `demo_quiescent_midnight_equivalence_v1`，event semantics 為 `quiescent_interval_equivalent_midnight_equity`；evidence digest 綁 expected UID digest、day start/cutoff、balance content digest、完整 endpoint/window evidence 與零事件證明。
8. 此 evidence 只建立 E₀；不直接令 `reconciled=true` 或 `trade_authorized=true`。formal reconciliation、F1/S1/W1、ownership、classification 與 DemoTradeGrant 仍各自通過才可增加曝險。

## 保證變化

- D1-A 原保證：來源在 00:00 直接取得 exact snapshot。
- D1-Q1 新保證：來源不直接在 00:00 snapshot；改以完整「狀態不變區間」證明 cutoff equity 與 00:00 equity **數值等價**。
- 不再涵蓋：存在任何午夜後 balance-changing event 時的 E₀ 重建；此情況仍 fail closed，不使用容差、不倒推。

## 最小實作與驗證成本

若核准，只需擴充既有 `BaselineEvidence`／verified baseline source 與 `demo_reconciliation` producer；不新增 DB schema、不新增第二 writer、不改交易出口。測試至少涵蓋：零事件 PASS、任一 USDT/non-USDT bill FAIL、fill/order/position FAIL、window/freshness gap FAIL、wrong UID/mode FAIL、非單一 USDT FAIL、digest tamper FAIL、重啟 durable consumption PASS。

## 決策

- **Q1-B 已核准並採用**。允許上述 quiescent interval exact-equivalence 作為 dedicated Demo bootstrap E₀ source；其餘情況仍 fail closed。
- Q1-A 保留為直接 exact-midnight source 的較強證據路徑，但不再是 dedicated Demo bootstrap 唯一可接受的 E₀ source。

## 實作結果

- `catos/risk.py` 新增 `demo_quiescent_midnight_equivalence_v1` authorized baseline source；既有 `synthetic_midnight_snapshot_v1` wire／驗證語意維持不變。Q1 durable evidence 額外綁 expected UID SHA-256、Taipei day start/cutoff、report digest、balance digest、完整 collection digest 與 zero-event digest。
- `catos/okx_collection.py`／`catos/okx_http.py` 補齊 `orders_history` window provenance：官方時間 filter 語意固定為 `cTime`，pagination 固定 `after=ordId`；fills／bills 仍維持 `ts`＋`after=billId`。
- `catos/demo_reconciliation.py` 新增純 verifier/builder；只接受完整 formal Demo collection、正確 UID／dedicated subaccount／acctLv=2／`net_mode`、單一完全可用 USDT、零 position／ordinary pending／algo pending／orders history／fills／bills、完整 window/page chain 與 F1/S1 freshness。任何 malformed evidence、coverage gap、非零事件或 digest mismatch 都回傳無 baseline，不做 `balChg` 回推。
- `catos/supervisor.py` 只在 formal collection 完成後、D3 day-ledger provider 執行前嘗試 Q1 builder；成功仍由既有 Supervisor→Journal 單 writer `commit_day_basis` 持久化。失敗不產生副作用，後續 D3 維持 fail closed。
- Q1 專屬 10/10 OK；連同 Verified E₀、Demo reconciliation、gate、bootstrap、Supervisor reconciliation、collection、HTTP、account report 直接受影響回歸共 188/188 OK。沒有 production network、credential 讀取、production DB/binding 建立、Demo/Live trading write、commit/push。

目前既有 production 40 GET 不能倒補成 Q1 evidence：清理後 24h 仍有 7 筆 balance-changing bills，其中 6 筆非 USDT transfer；而該批採集發生於 `orders_history` window provenance 擴充之前。即使 raw responsibility 為空，也不符合 Q1 的「整段零 bill + 完整新 provenance」條件。production `day_baseline_verified`、`reconciled`、`trade_authorized` 仍為 false。

使用者後續已另行授權一批新的 production read-only Q1 collection。該批 40 GET 完整結束，expected UID／dedicated subaccount／acctLv=2／`net_mode` 通過，`orders_history` 已帶 `cTime + after_order_id` window provenance，且 positions／ordinary pending／algo pending／orders history／fills／algo history 均為空；但 bills 仍有 7 筆，因此 Q1 builder fail closed，沒有產生 baseline。sanitized evidence 保存於 `outputs/catosv1-demo-production-q1-collection-evidence-20260924.json`；未建立 DB/binding、未 reconciliation、未授權交易。
