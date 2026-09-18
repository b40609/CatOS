# S5：一致 Lot／合成未決責任快照 API 與驗收規格

實作狀態：依使用者正式規格交付後的執行指示，已編寫API、快照物化／streaming hash及39個測試方法，待Sol質檢；詳見 [S5交接](../docs/lot-snapshot-handoff.md)。本輪未執行測試、編譯或Git，Schema7維持不變。

狀態：2026-09-18 正式設計規格。基線依使用者提供的 S4 驗收紀錄為 commit `8b16c0b244af611294ec0a98b8add835bb14008b`，S4 36 項＋S1 26 項＋Risk 14 項，合計 76/76 通過；未執行全量測試。本文件不重新驗證該結果。

## 1. 目的與邊界

S4 已能對完整 LotInventory 做 Gross／Net 觀測，但目前 `LotJournal.list_current()` 每次呼叫各自開交易；跨 Bot 或跨頁拼接不能證明資料來自同一 SQLite 快照。S3 也只有合成 order／fill／terminal 帳本，沒有交易所 HELD／WORKING／UNKNOWN 生命週期。

S5 只補一個本機一致讀取能力：在同一 SQLite `BEGIN DEFERRED` 讀取交易內，物化指定合約的完整目前 Lot、所有匹配 Bot 水位與 S3 尚未終態的合成責任，並產生可重算的內容身份 `capture_id`。

本片不做下列事情：

- 不修改 Schema 7、不新增資料表、trigger、migration 或第二 writer。
- 不修改 `risk.evaluate()`、3.0x／50%、日損、P6、ownership、execution 或交易路徑。
- 不讀實體 position、mark、交易所訂單、憑證或網路。
- 不把 S3 責任命名或映射成 HELD／WORKING／UNKNOWN。
- 不從 Lot Net 推導實體 position，也不產生 S4 MATCH／MISMATCH。
- 不把 `capture_id` 當作外部帳戶截點、交易授權、對帳完成或時間新鮮度證明。

環境固定為 `local-sim`、USDT-M SWAP、單一 account scope／單一 inst_id；其他 environment 直接拒絕。

## 2. 正式公開 API

S5 的公開入口掛在現有 `Journal`，因為一次 capture 同時需要 S2 Lot 與 S3 fill journal，且必須使用該 Journal 已擁有的同一 connection：

```text
Journal.capture_lot_snapshot(
    *,
    scope: LotScope,
    inst_id: str,
    observed_at_ms: int,
    valid_until_ms: int,
) -> LocalLotCapture
```

行為：

1. 呼叫端必須在擁有該 `Journal` 的既有執行緒呼叫；S5 不建立新 Journal、connection、thread 或 background task。
2. API 不讀系統時鐘。`observed_at_ms`／`valid_until_ms` 由受信父側明示；兩者是報告包裝時間，不決定 SQLite snapshot identity。
3. 若 connection 已在任何 transaction 中，拒絕巢狀 capture，不借用呼叫端 transaction。
4. API 開啟 `BEGIN DEFERRED`，以第一個 metadata SELECT 明確固定 SQLite read snapshot；之後所有 S2／S3 校驗與 SELECT 均在該 transaction 內完成。
5. 全部資料先物化、驗證及計算 `capture_id`，成功後才返回一個 frozen 結果；任何錯誤都沒有部分結果。
6. transaction 結束只做 rollback／關閉 read snapshot；capture 路徑不得執行 INSERT／UPDATE／DELETE／DDL，也不得推進 revision、commit_seq 或 S3 event seq。

預計資料型別放在 `catos/lot_snapshot.py`；`Journal.capture_lot_snapshot()` 僅作公開委派與 transaction ownership，不把 snapshot 計算散入 risk／execution。

## 3. 輸出資料契約

全部為 `@dataclass(frozen=True, slots=True)`。Decimal 不轉 float；整數拒絕 bool；token、Lot、ContractSpec 沿用既有 S1/S2 驗證。

### 3.1 BotWatermark

```text
BotWatermark
  bot_id: str
  last_commit_seq: int
```

只包含本次 `inst_id` 的全部 `lot_bindings`。按 `bot_id` 升冪排序。`last_commit_seq` 是該 binding 的 S2 Lot commit 水位，不是 Worker event seq、S3 全域 event seq 或交易所版本。

### 3.2 SyntheticPendingObligation

```text
SyntheticPendingObligation
  order_key: str
  intent_key: str
  bot_id: str
  lot_id: str
  effect: "OPEN" | "CLOSE"
  side: "BUY" | "SELL"
  resolved_quantity: Decimal
  filled_quantity: Decimal
  remaining_quantity: Decimal
  last_fill_seq: int
```

來源固定是 S3 synthetic ledger；型別故意沒有 `origin`、`state`、`verified`、`exchange_order_id` 或 `unknown` 欄位。

重建規則：

- 未決責任 = S3 order 已 bind 且沒有通過 S3 完整性重放的 terminal event。
- `effect` 只由原始已驗證 S3 intent 決定；OPEN/CLOSE 不從 Lot flags 猜測。
- OPEN：long side -> BUY；short side -> SELL。
- CLOSE：long Lot -> SELL；short Lot -> BUY。
- `resolved_quantity` 使用 S3 binding 時固定的已驗證數量。
- `filled_quantity` 是同 order 已驗證、去重且 fill_seq 連續的成交量精確總和。
- `remaining_quantity = resolved_quantity - filled_quantity`，使用 Decimal 精確有界加減；不得 float、負值、捨入或 clamp。
- `last_fill_seq=0` 代表尚無 fill；否則為最後一筆已驗證連續 fill_seq。
- OPEN 在首次成交前也必須輸出；此時 Lot 可能尚不存在，但 `lot_id` 已由原 OPEN identity 確定。
- 已全部成交但尚無 terminal 時仍必須輸出，且 `remaining_quantity=0`。
- CLOSE 全部成交使 Lot `remaining_qty=0` 但尚無 terminal 時，Lot 與零剩餘 pending obligation 都必須保留。
- 有 terminal 的 order 不列入 pending；S5 不根據 `remaining_quantity=0` 自動視為 terminal。

pending 按 `order_key` 升冪排序。`order_key` 與 `intent_key` 都必須是既有 S3 重放後的穩定身份，不重新發明 ID。

### 3.3 LocalLotCapture

```text
LocalLotCapture
  source: Literal["synthetic_ledger"]
  scope: LotScope
  contract: ContractSpec
  capture_id: str
  observed_at_ms: int
  valid_until_ms: int
  bot_watermarks: tuple[BotWatermark, ...]
  lots: tuple[StoredLot, ...]
  pending: tuple[SyntheticPendingObligation, ...]
  unmanaged_unresolved_lot_ids: tuple[str, ...]
```

規則：

- `contract` 必須是所有匹配 `lot_bindings` 的完整共同 ContractSpec；同 inst_id 若出現不同乘數、tick、lot_size 或 min_size，整個 capture 拒絕。
- `lots` 包含全部匹配 Bot 的 current head，不分頁，包含 `remaining_qty=0` 的 closed Lot；按 `lot_id` 升冪排序。
- `unmanaged_unresolved_lot_ids` 是 current Lot 中「不屬於任何 S3 managed order，且 opening_unresolved 或 closing_unresolved 為 true」的 lot_id，固定排序。
- S3 managed Lot 的 unresolved flags 仍原樣存在於 `lots`；不重複放入 unmanaged 清單。
- 已有 matching binding 但 lots／pending 都空時，是合法完整空 capture。
- 完全沒有 matching binding 時不是空 capture，而是 `binding_not_found`。

輸出硬上限：64 個 Bot、4096 個 current Lot、4096 個 pending obligation。超限拒絕，不截斷、不分頁、不把部分結果標成完整。

## 4. 同一讀取交易的精確語義

### 4.1 Snapshot pinning

公開 API 的最小順序固定為：

```text
驗證呼叫參數與 handle
BEGIN DEFERRED
SELECT metadata ...       # 第一個 DB read，固定 WAL read snapshot
S2 完整性校驗
S3 完整性校驗／重放
讀取 matching bindings
讀取全部 current Lot
由已重放 S3 state 物化 pending
找 unmanaged unresolved Lot
計算 capture_id
ROLLBACK                  # 結束純讀 transaction
return frozen capture
```

不能先在 transaction 外查 binding／count，再進 transaction 讀內容；也不能對每個 Bot 呼叫一次 `list_current()`。所有構成 capture 的資料必須來自同一 read snapshot。

### 4.2 BEGIN DEFERRED

S5 明確使用 `BEGIN DEFERRED`，不重用現有 `Journal._transaction()` 的 `BEGIN IMMEDIATE`。原因是 capture 為唯讀，且在 WAL 下應允許第二個 connection 在 reader 已固定 snapshot 後提交更新；reader 繼續看到舊的一致版本，下次 capture 才看到新版本。

這只是讀取鎖行為，不建立第二條 writer。產品程式仍只有既有 Journal writer。

### 4.3 完整性校驗

在同一 read snapshot 內先執行既有 S2/S3 完整性邏輯：

- Schema 必須仍為 7，WAL／FK 條件與正式 DDL 符合既有 S2/S3 規則。
- Lot head/revision、binding、request hash、commit_seq、flags 與 S1 domain 必須一致。
- S3 bind/fill/terminal seq、hash、欄位、Lot version 雙向關聯與重放結果必須一致。
- 損毀時拒絕 capture；不得跳過壞資料只匯出其餘 rows。

S5 不修復資料，也不因 capture 清除任何 unresolved flag。

## 5. `capture_id` 正式身份格式

`capture_id` 是 64 位小寫十六進制 SHA256，表示「S5 目前輸出的本機內容」。相同內容重複 capture 必須得到相同 ID；`observed_at_ms`、`valid_until_ms`、DB path、呼叫次數及系統時鐘不進身份。

### 5.1 Canonical numeric identity

所有 Decimal 在 hash 輸入中使用 S2 的數值身份語義：符號、去除無意義尾零後的 coefficient、調整後 exponent。數值等價的 `1`、`1.0`、`1.00` 產生相同身份；不得以 float 或呼叫端 Decimal context 正規化。

ContractSpec、Lot financial fields 與 pending quantity 都依此規則編碼。`None` 保留為 null，bool／int／str 保留原型別。

### 5.2 Streaming hash

禁止把 4096 Lot＋4096 pending 整包塞進 IPC 64KB frame。使用逐 fragment 的 canonical JSON 串流：

1. SHA256 先加入固定 ASCII domain tag `catos-local-lot-capture-v1`。
2. 每個 fragment 都是具名 top-level object，先經既有有界 canonical JSON 規則驗證；單 fragment 不得超過既有 IPC frame 上限。
3. 將 fragment UTF-8 bytes 長度編成固定 8-byte unsigned big-endian，再依序餵入 `length || bytes`。
4. 最後取 lowercase hex digest。

fragment 順序固定：

```text
header
bot_watermark       # bot_id 排序
lot                 # lot_id 排序
pending             # order_key 排序
unmanaged_unresolved # lot_id 排序，一筆一 fragment
```

`header` 至少包含：format=`catos-local-lot-capture-v1`、schema_version=7、source=`synthetic_ledger`、scope、完整 canonical ContractSpec。時間欄位明確排除。

每個 `lot` fragment 必須涵蓋 `StoredLot` 的完整可觀測內容：Lot identity、side、opened/remaining、average_entry、realized_pnl、fees_paid、funding_paid、protection、revision、opening_unresolved、closing_unresolved、commit_seq。每個 `pending` fragment涵蓋第 3.2 節全部欄位。

內容回到相同狀態時允許 capture_id 回到相同值；它是內容身份，不是不可逆的歷史序號。例如零成交 OPEN bind 後又合法 terminal，若最終 Lot／pending／watermark 內容與 bind 前完全相同，ID 可以相同。

### 5.3 `capture_id` 不代表的事實

`capture_id` 不證明：

- 交易所帳戶同時刻狀態。
- 外部 position／mark 與此 capture 原子一致。
- 沒有手動交易或其他資料庫外責任。
- capture 仍在有效期限內。
- risk／execution 已允許交易。

因此後續若接 S4，只能把它作為本機 Lot/pending 來源身份，不能把外部資料「貼同 capture_id」後宣稱同截點。

## 6. API 錯誤契約

公開 API 沿用 `LotStorageError`，新增或固定下列 machine-readable code：

| code | 條件 |
|---|---|
| `scope_mismatch` | 非本 Journal account、非 local-sim scope |
| `invalid_contract` | inst_id 非法或非允許的 USDT-M SWAP identity |
| `invalid_capture_time` | 時間不是真正 int、超界或 valid_until_ms <= observed_at_ms |
| `binding_not_found` | 此 scope／inst_id 完全沒有 lot binding |
| `contract_conflict` | 同 inst_id matching bindings 的完整 ContractSpec 不一致 |
| `capture_limit` | matching Bot、current Lot 或 pending 超出固定上限 |
| `integrity_error` | S2/S3 schema、hash、replay、版本、關聯或內容完整性失敗 |
| `storage_unavailable` | handle 已失效、巢狀 transaction、SQLite read/transaction 無法可靠完成 |

規則：

- caller input 錯誤不把 handle 標為失效。
- `integrity_error` 沿用現行 S2/S3 做法，使 Lot handle 不再可用，需關閉並重新開啟 Journal 後再核實。
- SQLite I/O／transaction 例外若無法確定 read handle 狀態，回 `storage_unavailable` 並停止使用該 handle。
- 不把 `binding_not_found` 轉成合法空集合。
- 不回傳半份 capture 或部分 hash。

## 7. S4 後續適配邊界

S5 成功輸出後，未來可以用：

- `bot_watermarks` -> S4 `expected_bot_ids`／`included_bot_ids` 的本機 binding 覆蓋證據。
- `lots` -> S4 `LotInventory.lots`。
- `capture_id` -> 本機 LotInventory 的 `cut_id` 候選。

但 `pending` 不能直接轉為 S4 `PendingInventory`，因為 S4 要求 origin/state 語義，而 S3 只知道本機 synthetic ledger 的 bind/fill/terminal。S5 不填造 `HELD`、`EXCHANGE`、`WORKING` 或 `UNKNOWN`。

若未來需要 S4 synthetic scenario adapter，必須另定義其 origin/state 限制與完整性語義；若要與實體 position 比較，physical 仍須由獨立可信來源提供。

## 8. 驗收矩陣

預計新增 `tests/test_lot_snapshot.py`。每列是驗收情境群，不預先承諾測試方法數或通過數。

| ID | 驗收情境 |
|---|---|
| A01 | 單一 binding、無 Lot、無 S3 order：回合法完整空 capture，而非 binding_not_found |
| A02 | 完全無 matching binding：明確 `binding_not_found` |
| A03 | 同合約多 Bot 全部納入，bot_watermarks 按 bot_id 穩定排序 |
| A04 | 其他 inst_id binding／Lot／S3 order 完全隔離，不進輸出或 hash |
| A05 | 同 inst_id 但 ContractSpec 任一欄不同：`contract_conflict`，不挑任一份 |
| A06 | closed Lot `remaining_qty=0` 仍保留於 lots |
| A07 | current Lot 只取 head 對應 revision，不輸出歷史 revision |
| A08 | 非 local-sim、錯 account、非法 inst_id、非法時間與 bool 時間拒絕 |
| B01 | OPEN bind 尚無 fill：pending 存在、lot 可不存在、filled=0、last_fill_seq=0 |
| B02 | 部分 OPEN：Lot 與 pending 同時存在，filled／remaining 精確 |
| B03 | 部分 CLOSE：current Lot 已反映成交，pending 仍保留未成交責任 |
| B04 | OPEN 全成交但無 terminal：remaining=0 的 pending 仍存在 |
| B05 | CLOSE 全成交但無 terminal：closed Lot 與 remaining=0 pending 同時存在 |
| B06 | terminal 提交後對應 order 從 pending 移除；Lot 依 S3 終態版本保留 |
| B07 | 零成交 OPEN terminal 後不製造零量 Lot，也不保留 pending |
| B08 | 多 order／多 Lot pending 按 order_key 固定排序，順序不依 DB row 回傳順序 |
| B09 | S2 未受 S3 管理且有 unresolved flag 的 Lot 進 unmanaged_unresolved_lot_ids |
| B10 | S3 managed unresolved Lot 不重複進 unmanaged 清單；flag 仍保留在 StoredLot |
| C01 | 完全相同 DB 內容、不同 observed_at／valid_until，capture_id 相同 |
| C02 | Lot revision／數量／費用／flags／commit_seq 任一可觀測內容改變，capture_id 改變 |
| C03 | 零成交 OPEN bind 新增 pending，即使 bot watermark 不變，capture_id 仍改變 |
| C04 | fill quantity／filled total／last_fill_seq 改變，capture_id 改變 |
| C05 | terminal 移除 pending 或產生終態 Lot version，capture_id 改變 |
| C06 | 其他 inst_id 的寫入不改指定合約 capture_id |
| C07 | 數值等價 Decimal 表示與外部低精度 Decimal context 不改 capture_id；格式固定 64 位小寫 hex |
| D01 | 第一 connection `BEGIN DEFERRED` 並完成首個 metadata SELECT 後，第二 connection 可在 WAL 提交更新 |
| D02 | D01 中第一 capture 只看到更新前的完整 Lot＋pending 組合，不混入 writer 新資料 |
| D03 | D01 結束後下一次 capture 才看到 writer 的新完整組合，capture_id 對應改變 |
| D04 | 多 Bot／Lot／pending 在並行寫入下仍全數來自單一 read snapshot，不出現跨版本拼接 |
| D05 | capture 前後資料表內容、revision、commit_seq、S3 seq、v1 control／risk／P6 完全不變 |
| D06 | 讀取／解碼／hash 任一階段注入失敗：無部分回傳、transaction 關閉、資料不寫入 |
| D07 | 已存在 transaction 或失效 handle 直接 `storage_unavailable`，不偷用外層 transaction |
| E01 | S2 head/revision/hash/FK 任一損毀時 `integrity_error`，不得跳過壞 Lot |
| E02 | S3 bind/fill/terminal/hash/版本雙向關聯任一損毀時 `integrity_error`，不得輸出推測 pending |
| E03 | 64 Bot、4096 Lot、4096 pending 邊界可完整輸出；任一超出即 `capture_limit`，不截斷 |
| E04 | 每個 hash fragment 維持既有單-frame 上限；大 capture 使用 streaming hash，不放寬 IPC 64KB 規則 |
| E05 | Decimal 精確 subtraction、極小合法 remainder、50 位／指數邊界不受 ambient context 影響 |
| E06 | `capture_id` 不含時間、DB path 或呼叫次數，也不提供 accepted／ready／verified／reconciled 欄位 |
| E07 | S2/S3 直接受影響回歸保持；S4 `test_lot_exposure.py` 保持，不修改 risk 算術 |
| E08 | `git diff --check` 通過，且實作 diff 無 Schema 版本、risk.py、execution、protection 或交易路徑變更 |

並行測試只使用臨時 DB 與第二個測試 connection。第二 connection 是測試用 writer，用來證明 SQLite snapshot isolation；產品實作不新增第二 writer。

## 9. 實作順序與完成條件

建議後續實作順序：

1. 新增 `catos/lot_snapshot.py` 的 frozen 輸出型別、canonical fragment 與 streaming hash helper。
2. 在 `Journal` 增加單一 `capture_lot_snapshot()` 公開入口與私有 `BEGIN DEFERRED` read-snapshot context。
3. 在既有 S2/S3 private replay 結果上物化 matching bindings、current Lot、pending 與 unmanaged unresolved；不複製第二套帳務 reducer。
4. 新增 `tests/test_lot_snapshot.py`，先驗證內容與 identity，再做雙 connection WAL snapshot isolation。
5. Sol 執行 S5 專屬、S2/S3 直接受影響回歸與 S4 回歸，再做 Git 格式／staged 檢查。

S5 完成條件：同一 read transaction 的本機 Lot＋synthetic pending capture 可重現、身份穩定、並行 writer 不造成混讀、整條 capture 路徑沒有資料寫入，且既有 S2/S3/S4 邊界未退化。

S5 驗收完成後才評估「S5 -> S4 的明示 synthetic adapter」。Gross 風控限制、真實帳戶 position／mark 對齊、Demo／Live 與交易接線仍另案。
