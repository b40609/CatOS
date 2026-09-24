# Reconciliation 分類與 Freshness 契約審查 — 2026-09-22

2026-09-22 S1 後續：本文件中 `snapshot_semantics_verified` 布林值的描述保留為 S1 前歷史狀態；現行契約已由 [S1 snapshot semantics](reconciliation-s1-snapshot-semantics-20260922.md) 取代，gate 直接驗 `s1-bounded-sequential.v1` source/page evidence，不接受 caller 布林聲明。後續 classification closure 已把 coverage 更新為 156/185、29 unknown；最新分類狀態見 [classification closure](reconciliation-classification-closure-20260922.md)，本文件內 120/185／65 unknown 段落保留為前一片歷史。

本文件接續 `reconciliation-readonly-evidence-20260922.md`。本輪沒有讀 credential、沒有呼叫私有帳戶 endpoint、沒有重跑 Demo 採集、沒有交易或帳戶修改。公開官方資料只作證據；實際分類仍受既有 catOS 帳務原則約束。

## 1. 官方證據基線

### 後續政策定案與實作（2026-09-22，待 Sol 驗收）

使用者已核准 C1-B、C2-A、C3-B、C4-B。下文 63/185 與「待定案」是前片歷史；現行版本新增 57 組，為 120/185 已分類（7 external、71 internal、42 forbidden），65 unknown、complete=false。本片沒有取得新的公開或私有 API 證據。

- C1-B：已知禁止活動可計入 classification coverage；實際觀察到時以 `unsupported_account_activity` 阻斷。禁止項目不作 external-flow 算術調整，report 小計 unavailable；分類完整也不能覆蓋此 blocker。未觀察到 forbidden bill 時不因表內存在 forbidden entry 而阻斷。
- C2-A：external 邊界與 verified account equity scope 一致。acctLv=2 依單一無負債 USDT collateral 之 details[].eq 為 E_verified；acctLv=3 要求有效非空 adjEq。code 名稱不足以證明 scope 時不落表。
- C3-B：明確非策略正向 credit 排除於策略日損，external 語意擴充為非策略 equity adjustment。新列 1/257、288、381、392、429；沿用 signed balChg，不取絕對值。bonus 回收 1/292 尚缺回收與原始 credit／日界關係，仍 unknown。
- C4-B：本金依 C2；利息、費用、penalty、成本退款 internal。本片不把借入本金自動當資本注入，也不推導 357/358/359 scope。

| 分類 | type | 本片新增 subType |
| --- | --- | --- |
| forbidden | 1 | 283, 284, 285, 286, 287 |
| forbidden | 12 | 200, 201, 202, 203, 267, 268, 269, 372, 373, 374, 375 |
| forbidden | 26 | 296, 297, 298, 299, 340, 341, 342, 343, 344, 345 |
| forbidden | 32 | 324, 325, 326, 327, 328, 329 |
| forbidden | 35 | 382, 383 |
| forbidden | 38 | 416, 417, 418, 419 |
| forbidden | 250 / 251 | 250, 280 / 251, 281 |
| external | 1 | 257, 288, 381, 392, 429 |
| internal | 7 | 9, 14, 293, 294, 295 |
| internal | 33 | 350, 351, 352, 353, 354 |

剩餘為原 19 組語意不足及原 103 組中的 46 組：type 1: 292,420；4: 114,115,312；5: 16,17,313,314,315,316,317；6: 160,161,162,332,333,334；15: 210,211,212,213,216；16: 306,307,308,309；29: 224,225；33: 348,349,356,357,358,359；37: 421,422,423,424,425,426,427,432,433,434,435。政策原則已核准，逐項 scope／調整語意證據仍不足，保持 unknown。

原 63 組帳務分類維持；其中 internal 只表示不調整 external flow，不能解讀成允許該交易產品。此次 C1 只對上表明確活動新增禁止標記，並非所有非 SWAP 產品偵測已完備。

程式新增 `classify_bill_flows()` 三值契約；既有 `external_flows()` 二值呼叫保留相容，將 forbidden IDs 合併至未解集合，避免舊 caller 靜默接受。account report 使用三值契約。新增測試涵蓋正負／零金額、非 USDT、去重、衝突、unknown 並存、空 bills 與完整 day evidence 下阻斷；本片未執行測試，交由 Sol 驗收。F1 四值、snapshot semantics 與 trade_authorized=false 均不變。

- 當期 Demo catalog：32 個 type、185 個唯一 `(type, subType)`，SHA-256 `84373423204fe2ccf65955ba096e11687e96879caf436d00efcf5af030506e4c`。
- OKX API 文件 `Get bills details` 定義 bill 為會造成 account balance 改變的交易紀錄，`balChg` 是該事件對指定 `ccy` 的 signed balance change；文件也把 Buy/Sell、Open/Close、Forced liquidation、Delivery/Exercise、Funding 等 subtype 明確綁到交易／PnL 欄位。
- OKX API 文件 `Get bill types` 定義 `/api/v5/account/subtypes` 為 type/subType mapping 來源；空白 `typeDesc`／`subTypeDesc` 表示該 type 未啟用。未啟用不代表可忽略，也不構成分類證據。
- 既有帳務原則：`external` 只用於非策略損益來源且跨越受管帳戶 equity 邊界的資本移入／移出；交易、費用、funding、PnL、結算等已反映於 equity 的經濟活動屬 `internal`，避免二次扣除。

公開來源：

- https://www.okx.com/docs-v5/en/#trading-account-rest-api-get-bills-details-last-7-days
- https://www.okx.com/docs-v5/en/#trading-account-rest-api-get-bill-types

## 2. 上一輪 174 組 unknown 的審查結果

上一輪 11/185 已分類。本輪對剩餘 174 組逐組審查後分為：52 組可直接依官方語意＋既有帳務原則判定，19 組官方語意不足，103 組需要新的帳務／受管 equity 邊界政策。52 + 19 + 103 = 174。

### 2.1 可直接判定：52 組，已補為 `internal`

這些項目都是明確交易／交割／強平／ADL／結算型經濟活動，或明確在同一 account equity 內做資產 conversion；把其 `balChg` 再當 external flow 會重複調整 equity。

| type | 官方類型 | 本輪新增 internal subType |
| --- | --- | --- |
| 2 | Trade | 1, 2, 407, 408, 410, 411, 412, 413 |
| 3 | Delivery | 112, 113, 117, 170, 171, 172, 414, 415 |
| 5 | Forced liquidation | 100, 101, 102, 103, 104, 105, 106, 107, 110, 111, 116 |
| 9 | ADL | 127, 128 |
| 10 | Overloss recovery | 108 |
| 11 | System crypto conversion | 118, 119 |
| 14 | Block trade | 204, 205, 206, 207, 208, 209 |
| 20 | Token conversion | 220, 221 |
| 24 | typeDesc 空白；subType 明示 Spread trade | 270, 271, 272, 273 |
| 27 | Convert | 318, 319, 379, 380 |
| 28 | Easy convert | 236, 237 |
| 30 | Simple trade | 320, 321 |

目前版本化 classification 因此為 63/185 已分類，122 組仍 unknown，`complete=false`。沒有因 bills 為空、未啟用或名稱含 Transfer 而宣告完整。

### 2.2 官方語意不足：19 組

這些 code 無法只靠目前官方 catalog／公開文件判定受管 equity 邊界。維持 unknown，不猜分類。

| type | subType | 原因 |
| --- | --- | --- |
| 1 | 290 | subTypeDesc 空白 |
| 4 | 376, 377, 393, 394 | subTypeDesc 空白 |
| 12 | 276, 277 | subTypeDesc 空白 |
| 13 | 131, 132 | 只有 `DDH buy/sell`，目前公開文件未提供 DDH 的帳務／equity 邊界語意 |
| 22 | 259, 260 | typeDesc、subTypeDesc 都空白 |
| 24 | 274, 275 | typeDesc、subTypeDesc 都空白 |
| 26 | 441, 442, 443, 444, 445, 446 | typeDesc、subTypeDesc 都空白 |

若未來官方文件補足描述，可直接重新審查，不需要先改帳務政策。

### 2.3 需要新帳務／equity 邊界政策：103 組

這些官方名稱大致可理解，但無法由目前「資本移入／移出 vs 已反映於 equity 的交易活動」二分法安全決定。主要問題是產品 allocation、借貸負債、獎勵／非策略 credit、copy/bot/profit-share，以及 account/product 間移轉是否屬同一受管 equity 邊界。

| type | 官方類型 | 待政策 subType |
| --- | --- | --- |
| 1 | Transfer | 257, 283, 284, 285, 286, 287, 288, 292, 381, 392, 420, 429 |
| 4 | Auto token conversion | 114, 115, 312 |
| 5 | Forced liquidation | 16, 17, 313, 314, 315, 316, 317 |
| 6 | Margin transfer | 160, 161, 162, 332, 333, 334 |
| 7 | Interest | 9, 14, 293, 294, 295 |
| 12 | Strategy transfer | 200, 201, 202, 203, 267, 268, 269, 372, 373, 374, 375 |
| 15 | Quick margin | 210, 211, 212, 213, 216 |
| 16 | Borrowing | 306, 307, 308, 309 |
| 26 | typeDesc 空白；subType 有產品名稱 | 296, 297, 298, 299, 340, 341, 342, 343, 344, 345 |
| 29 | One-click repay | 224, 225 |
| 32 | Move position | 324, 325, 326, 327, 328, 329 |
| 33 | Loans | 348, 349, 350, 351, 352, 353, 354, 356, 357, 358, 359 |
| 35 | Options market | 382, 383 |
| 37 | Corporate action | 421, 422, 423, 424, 425, 426, 427, 432, 433, 434, 435 |
| 38 | USDG Rewards | 416, 417, 418, 419 |
| 250 | Profit share payment | 250, 280 |
| 251 | Profit share refund | 251, 281 |

## 3. 需要使用者定案的最小政策

### C1. Classification 是否增加第三類 `forbidden`

目前只有 `external|internal`。但 catOS v1 是專用 USDT-M SWAP 子帳戶，copy trading、trading bot、Move position、部分產品 subscription 等即使官方語意已知，也可能是「已知但不允許出現在此帳戶」的活動。

- C1-A：維持二分法。所有 185 組最後都必須硬分成 external 或 internal。
  - 影響：改動最小，但已知不支援活動若被分成 internal/external，可能失去「出現即阻斷」語意。
- C1-B：新增 `forbidden` 類別。classification completeness 可包含已知 forbidden code；report 觀察到 forbidden bill 時固定 fail closed。
  - 建議：C1-B。
  - 影響：需擴 `FlowClassificationEntry.category`、`external_flows()` 回傳／report contract 與 gate blocker。建議新增 `unsupported_account_activity` blocker，避免把已知 forbidden 混成 `unknown_external_flow`。

### C2. 受管 equity 邊界

- C2-A：邊界與 verified account equity scope 完全一致。這是一致的經濟／帳務邊界，不再把 policy 綁死在單一 OKX API 欄位名稱。欄位來源依 account mode 明確區分：
  - `acctLv=2`：OKX balance 的 `adjEq=""` 視為合法 not applicable schema；只有在 balance profile 同時符合單一幣別、ccy=="USDT"、details[].eq 為有效 Decimal、details[].liab==0、無其他 collateral 時，以 `details[].eq` 作為 `E_verified`（`E_risk = E_verified`）。
  - `acctLv=3`：仍嚴格要求非空有效 Decimal 之 `adjEq`，`adjEq=""` fail closed (`unsupported_collateral`)。
  - `totalEq` 保留 USD evidence，不得作為 USDT equity fallback；`adjEq=""` 不得轉為 Decimal(0)；missing/null/float/bool/malformed 均維持 fail closed (`invalid_record:balance`)。
  只要資產／position 仍在同一 verified account equity scope 內，產品 allocation／conversion／margin 搬移都視為 internal；只有真正跨出該 account equity scope 的資本流才 external。
- C2-B：邊界只含 catOS SWAP 可用資金；轉入 bot、copy、options、structured product、USDG 等即使仍在同一 OKX account-level equity，也視為 external。
- 建議：C2-A。日損分母與即時 equity 都以 verified account equity 為基礎，external-flow 邊界與 equity measurement scope 一致，較不會產生雙重調整。
- 影響：若採 C2-A，仍需官方證據判斷各 transfer code 是否真的跨出 account-level equity；若採 C2-B，需重新定義目前 `external` 的語意與 E_0 scope，變更較大。

### C3. 非策略正向 credit／reward

包含 voucher、trading bonus、Auto Earn+ reward/bonus、bot airdrop、corporate dividend、USDG reward 等。

- C3-A：視為 internal economic result，直接留在日內 equity PnL。
- C3-B：視為 external/non-strategy adjustment，從日內 PnL 排除。
- 建議：若仍使用二分法，正向 reward 採 C3-B 較保守，避免 bonus/reward 抵銷真實交易虧損、延後 Soft/Hard latch；但需明確把 `external` 定義擴充為「排除於策略日損的非策略 equity adjustment」，不再只等於 capital transfer。
- 影響：若 C1-B 同時採用，可把帳戶本來不應出現的 reward/product code 設為 forbidden，而不是硬塞進 external。

### C4. 借貸／利息／強制償還

- C4-A：所有 borrow/repay principal、interest、penalty、refund 都視為 internal；由 verified `adjEq` 的資產與負債淨額承擔結果。
- C4-B：principal movement 依受管 equity 邊界判定，interest/fee/penalty/refund 維持 internal；真正轉到 funding/OTC system account 的 code 再依 C2 判 external/forbidden。
- 建議：C4-B。借入／償還本金本身不應被當成策略資本注入／抽離；利息與 penalty 是真實經濟成本，若視為 external 會低估日損。
- 影響：需對 357/358/359 等跨帳戶字樣取得更明確官方來源後再落表。

在 C1–C4 定案前，103 組維持 unknown，`complete=false`。

## 4. Freshness gate 最小契約修正

原 gate 把兩個不同物理量都套用 `max_clock_skew_ms`：

1. `abs(server_time_ms - local_time_ms)`：clock offset。
2. `abs(checked_at_ms - local_time_ms)`：clock sample age。

這會逼迫 `max_clock_skew_ms` 同時吸收時鐘偏移與批次內 sample age。上一輪 clock offset 約 +2736 ±134 ms，但 sample 到 report build 已 19415 ms；放大 skew 門檻來包住 19 秒 sample age 會失去原本的 clock offset 安全意義。

本輪已做最小修正：

```text
FreshnessPolicy:
  max_report_age_ms
  max_batch_span_ms
  max_clock_skew_ms
  max_clock_sample_age_ms
  checked_at_ms
```

規則：

- `max_clock_skew_ms` 只限制 `abs(server_time_ms - local_time_ms)`。
- `max_clock_sample_age_ms` 只限制 `checked_at_ms - local_time_ms`。
- clock sample 在 `checked_at_ms` 之後直接 fail closed。
- 等於門檻可通過；超 1 ms 阻斷。
- `snapshot_semantics_verified=False` 仍永遠阻斷。
- 沒有新增生產預設值，沒有靠放大 skew 解鎖。

## 5. F1 已完成補證並定案

2026-09-22 後續獲使用者明確授權完成 [F1 freshness 補證](reconciliation-f1-freshness-evidence-20260922.md)：同一 production plan 4 次正常 Demo read-only run 均為 41 GET、20159–20216 ms；批次後 gate-adjacent public-time 的 report age 132–170 ms、clock sample age 66–85 ms、midpoint offset +2837～+2848 ms。另以既有 allowlist 真實 HTTPS/pagination 建立 180000 ms stress，360 GET、357 頁 fills_history，`179993 ms` 時由 deadline `timeout` fail closed；沒有 synthetic sleep。

F1 policy ID 固定為 `f1-demo-2026-09-22`：

- `max_report_age_ms = 1000`
- `max_batch_span_ms = 31000`
- `max_clock_skew_ms = 3000`
- `max_clock_sample_age_ms = 500`

四值仍由 Supervisor 明示注入，gate 不新增 fallback。4/4 正常樣本依現行 `_freshness_blockers()` 均通過 freshness；179993 ms stress 被 freshness 阻斷。`snapshot_semantics_verified` 仍是獨立必要證據，不因 F1 定案自動改為 true。
