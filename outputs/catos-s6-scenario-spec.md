# S6：S5 → S4 合成情境轉接契約與驗收規格

狀態：2026-09-18 正式設計規格。基線為已驗收 S5 commit `274891981027cf554c590224f68f4ea7c46bb716`；依既有紀錄，S5 專屬與必要回歸合計 180/180 通過，未執行全量測試。本文件不重驗 S5，也不修改該驗收紀錄。

## 1. 目的與邊界

S5 已能在單一 SQLite read snapshot 內輸出完整 `LocalLotCapture`：Lot、Bot 水位、S3 synthetic pending 與未受 S3 管理的 unresolved Lot。S4 則需要 `LotInventory`、`PhysicalPosition`、`MarkObservation`、`PendingInventory`，並要求 pending 有明確 origin/state 與可驗證共同 cut。

S6 只建立 **local-sim 合成情境轉接**：把 S5 的本機帳本證據與呼叫端明示的 synthetic physical／mark 情境組成 S4 可觀測輸入，並保留「這是合成情境，不是交易所證據」的 provenance。

本片不做下列事情：

- 不讀 DB、不新增 connection、table、schema、migration、checkpoint 或 cache。
- 不修改 S5 capture 內容，不重新命名或猜測交易所訂單狀態。
- 不把 `SYNTHETIC_LEDGER` 映射成 `HELD`、`EXCHANGE`、`WORKING` 或 `UNKNOWN`。
- 不從 Lot Net 反推 physical，不從 mark／physical 數值相等推導共同截點。
- 不把 S5 `capture_id` 當成外部或情境共同 cut。
- 不接 `risk.evaluate()`、Gross 限額、3.0x／50%、P6、Demo／Live 或交易出口。
- 不提供 accepted／ready／authorized 等交易裁決。

環境固定為 `local-sim`、USDT-M SWAP；其他 environment 或 instrument 類型直接拒絕。

## 2. 已定案的語義選擇

### 2.1 Pending 不偽裝成交易所狀態

S3/S5 能證明的是：「這筆 synthetic order 已 bind，且截至該 capture 尚未記錄 terminal」。它不能證明訂單目前在 Supervisor HELD、交易所 WORKING 或交易所 UNKNOWN。

因此 S6 採加法式分類：

```text
origin = "SYNTHETIC_LEDGER"
state  = "UNTERMINATED"
```

每一筆 S5 `SyntheticPendingObligation` 一對一轉成 S4 pending；`order_key` 成為 `obligation_id`，side／effect／lot_id／remaining_quantity 原樣保留。S6 不接受逐筆狀態 override，避免同一帳本事實被情境輸入改寫成另一種來源。

### 2.2 共同 cut 必須明示 attestation

`capture_id` 只識別 S5 本機內容，不表示 physical／mark 與它原子同時取得。S6 的共同截點由呼叫端提供獨立 `scenario_cut_id`，並在 `SyntheticScenarioEvidence` 中明示綁定精確的 `source_capture_id`。

成立共同 cut 的必要條件是：

1. `scenario.source_capture_id == capture.capture_id`。
2. scenario 與 capture 的 scope／完整 ContractSpec 完全一致。
3. `scenario_cut_id` 為合法 token，且不得等於 `capture_id`。
4. adapter 自己不產生、刷新、重寫或猜測 `scenario_cut_id`。

時間戳相同、數量相同或呼叫順序相鄰都不能替代上述 attestation。

### 2.3 S4 明示 evidence kind

為避免 synthetic report 被誤認為一般 S4 evidence，S4 的 request/report 增加：

```text
evidence_kind = "OBSERVED" | "SYNTHETIC_SCENARIO"
```

既有呼叫預設 `OBSERVED`；只有 `SYNTHETIC_SCENARIO` 才允許 `SYNTHETIC_LEDGER / UNTERMINATED` pending。既有 `HELD / EXCHANGE` 驗證與語義不放寬。

## 3. 正式公開 API

預計新增 `catos/lot_scenario.py`：

```text
observe_synthetic_scenario(
    *,
    capture: LocalLotCapture,
    scenario: SyntheticScenarioEvidence,
    now_ms: int,
) -> SyntheticScenarioObservation
```

行為固定為純函式：

1. 驗證 `capture` 結構與其 `capture_id` 可由既有 S5 canonical hash 重算得到。
2. 驗證 `scenario` 的 scope／contract／capture binding／cut／時間／Decimal。
3. 純資料建立 S4 `ExposureRequest(evidence_kind="SYNTHETIC_SCENARIO")`。
4. 呼叫既有 `observe_exposure()`；不複製 S4 曝險算術。
5. 回傳帶 S5/S6 provenance 的 frozen wrapper。

不得在 API 內讀系統時鐘、資料庫、網路或環境變數。

## 4. S6 輸入／輸出資料型別

全部新型別使用 `@dataclass(frozen=True, slots=True)`。Decimal 禁止轉 float；整數拒絕 bool；token 與數值限制沿用既有 IPC／Lot 契約。

### 4.1 SyntheticScenarioEvidence

```text
SyntheticScenarioEvidence
  source: Literal["synthetic_scenario"]
  scope: LotScope
  contract: ContractSpec
  scenario_cut_id: str
  source_capture_id: str
  physical_observed_at_ms: int
  physical_valid_until_ms: int
  physical_quantity: Decimal | None
  physical_complete: bool
  mark_quote_id: str | None
  mark_observed_at_ms: int | None
  mark_valid_until_ms: int | None
  mark: Decimal | None
```

規則：

- `source` 固定為 `synthetic_scenario`。
- scope／contract 必須與 capture 完全一致。
- `source_capture_id` 必須精確等於 capture 的 64 位 lowercase SHA256 identity。
- `scenario_cut_id` 是情境共同截點的獨立身份，不由 adapter 生成，且不得等於 `source_capture_id`。
- physical 必須由 scenario 明示；禁止從 Lot Net 產生。
- `physical_complete=True` 表示該 **synthetic scenario** 對此 cut 的 physical quantity 已完整給定；若 quantity 為 `None`，complete 必須為 false。
- physical quantity 若存在，必須為合法 Decimal 並對齊 contract lot_size。
- mark 可以完全缺席。`mark is None` 時，三個 mark metadata 欄位必須全為 `None`。
- mark 存在時，quote_id 與兩個時間欄位必須全部存在；mark 必須 > 0。mark 不要求與 physical 同一時間戳，但同屬此 synthetic scenario provenance。
- 所有來源時間原樣傳入 S4；S6 不把舊 capture 或舊 scenario 的 observed/valid 時間刷新成 `now_ms`。

### 4.2 SyntheticScenarioObservation

```text
SyntheticScenarioObservation
  evidence_kind: Literal["SYNTHETIC_SCENARIO"]
  scenario_cut_id: str
  source_capture_id: str
  report: ExposureReport
```

此 wrapper 是 S6 對外結果。`report.evidence_kind` 也必須為 `SYNTHETIC_SCENARIO`。

它只表示合成情境觀測；不得把 wrapper 或 nested `ExposureReport` 當成交易所對帳、risk ready、交易許可或真實帳戶證據。

## 5. S5 → S4 精確轉接規則

### 5.1 LotInventory

由 capture 建立：

```text
scope              = capture.scope
inst_id            = capture.contract.inst_id
cut_id             = scenario.scenario_cut_id
observed_at_ms      = capture.observed_at_ms
valid_until_ms      = capture.valid_until_ms
complete            = True
expected_bot_ids    = tuple(w.bot_id for w in capture.bot_watermarks)
included_bot_ids    = expected_bot_ids
lots                = capture.lots
```

`capture_id` 不塞進 `cut_id`；它保留在 S6 wrapper 的 `source_capture_id`。

### 5.2 PendingInventory

每筆 S5 pending：

```text
obligation_id      = order_key
origin             = "SYNTHETIC_LEDGER"
state              = "UNTERMINATED"
side               = side
remaining_quantity = remaining_quantity
effect             = effect
lot_id             = lot_id
```

Inventory metadata：

```text
scope              = capture.scope
inst_id            = capture.contract.inst_id
cut_id             = scenario.scenario_cut_id
observed_at_ms      = capture.observed_at_ms
valid_until_ms      = capture.valid_until_ms
complete            = (capture.unmanaged_unresolved_lot_ids == ())
orders              = one-to-one mapped capture.pending
```

重要規則：

- 首次成交前 OPEN 仍輸出，即使對應 Lot 尚不存在。
- `remaining_quantity=0` 但未 terminal 仍輸出。
- CLOSE 不因 pending 而預先減少 current Lot Gross。
- S6 不用 `resolved_quantity - filled_quantity` 重算剩餘量；直接使用已由 S5 驗證的 `remaining_quantity`。
- `unmanaged_unresolved_lot_ids` 非空時，不製造假 pending，也不填 `UNCLASSIFIED` 猜測；`complete=False`，由 S4 既有 lot-link 規則降級。
- unmanaged id 必須對應 capture 中實際 unresolved current Lot，且不得同時被 mapped pending 佔用；矛盾 capture 直接拒絕。

### 5.3 PhysicalPosition

```text
scope           = scenario.scope
inst_id         = scenario.contract.inst_id
cut_id          = scenario.scenario_cut_id
observed_at_ms   = scenario.physical_observed_at_ms
valid_until_ms   = scenario.physical_valid_until_ms
quantity         = scenario.physical_quantity
verified         = scenario.physical_complete
```

此處 `verified=True` 只在 `report.evidence_kind == "SYNTHETIC_SCENARIO"` 下表示「scenario attestation 宣告 physical 完整」，不是交易所 verification。

### 5.4 MarkObservation

mark 缺席時傳 `None`。存在時：

```text
scope           = scenario.scope
inst_id         = scenario.contract.inst_id
quote_id        = scenario.mark_quote_id
observed_at_ms   = scenario.mark_observed_at_ms
valid_until_ms   = scenario.mark_valid_until_ms
mark             = scenario.mark
```

mark 仍遵守 S4 的獨立 quote／freshness 規則。缺 mark 不妨礙純張數比較，但 notional 維持不可得。

## 6. S4 的最小加法式變更

S6 實作時允許對 `catos/lot_exposure.py` 做下列最小變更；其他 S4 算術維持原狀。

### 6.1 Pending taxonomy

合法配對改為：

```text
HELD             -> HELD
EXCHANGE         -> WORKING | UNKNOWN
SYNTHETIC_LEDGER -> UNTERMINATED   # 僅 SYNTHETIC_SCENARIO request
```

在 `OBSERVED` request 中出現 `SYNTHETIC_LEDGER` 必須拒絕，避免一般 S4 呼叫繞過 S6 provenance。

### 6.2 ExposureReport source buckets

既有欄位保持：

- `held_buy_qty` / `held_sell_qty`
- `exchange_buy_qty` / `exchange_sell_qty`

新增：

- `synthetic_buy_qty` / `synthetic_sell_qty`
- `evidence_kind`

`pending_buy_qty`／`pending_sell_qty` 為所有合法 origin 的合計。`physical_scenario_upper_qty` 使用此總合計；`virtual_gross_scenario_upper_qty` 仍為 current Gross 加所有 `effect=OPEN` 的未決數量，CLOSE 不預扣。

既有 observed-mode 結果不變：沒有 synthetic order 時 synthetic buckets 為精確 0；HELD／EXCHANGE bucket 與原先數值相同。

`has_unknown` 只表示真正 `state=UNKNOWN`，`UNTERMINATED` 不冒充 UNKNOWN。

## 7. Capture 完整性與 forged input 防護

S6 接受的是 Python object，不假設 caller 一定從正式 Journal API 取得。adapter 必須在純資料層重新確認最低限度 S5 invariants：

- `source == "synthetic_ledger"`，scope 為 local-sim，contract 合法。
- `capture_id` 格式正確，且以既有 S5 canonical streaming hash 對目前內容重算完全一致。
- Bot watermark、Lot id、order_key 不重複；固定排序規則未被破壞。
- Lot scope／inst_id／bot coverage 與 capture 一致。
- pending scope identity、side/effect、Decimal、Lot direction 關聯符合 S5/S4 契約。
- 每個 unresolved current Lot 恰好由一筆 matching pending 或 unmanaged 清單解釋；兩者不得重疊。
- unmanaged 清單不得包含不存在、已 resolved 或重複的 Lot。

任何矛盾都拒絕；不得「修正」傳入 capture、截斷集合或跳過壞項目。

## 8. 錯誤契約

新增 `ScenarioInputError(code)`；建議 machine-readable code：

| code | 條件 |
|---|---|
| `invalid_capture` | 型別、source、hash、排序、Lot/pending/unmanaged 內部一致性失敗 |
| `scenario_identity_mismatch` | scope、contract、source_capture_id 或 scenario cut 綁定不符 |
| `invalid_scenario_cut` | cut 非 token、等於 capture_id 或其他格式矛盾 |
| `invalid_scenario_time` | physical/mark 時間型別、範圍或先後關係非法 |
| `invalid_scenario_physical` | physical quantity／complete／lot-size 規則不符 |
| `invalid_scenario_mark` | mark metadata 缺半套、數值非法或 <= 0 |
| `input_limit` | 輸入超過沿用 S4/S5 的 64 Bot／4096 Lot／4096 pending 上限 |

S4 `ExposureInputError` 若由已建好的合法 S6 request 觸發，視為 adapter bug；S6 不把它靜默降級成另一個 scenario 結果。

## 9. 完整性與降級語義

S6 分清「輸入矛盾」與「證據不完整」：

- scope／contract／capture hash／cut binding 矛盾：**拒絕**。
- physical 未知或 `physical_complete=False`：合法輸入，S4 `comparison_status=UNAVAILABLE`。
- mark 缺失／stale：合法輸入，數量觀測仍可存在，notional 降級。
- unmanaged unresolved Lot：合法 S5 狀態，但 S6 pending `complete=False`，不得輸出完整 pending scenario upper。
- S5 pending 本身完整且 unmanaged 為空：pending `complete=True`，包括 0-remainder unterminated obligation。
- 任一來源 stale／future：沿用 S4 reasons，不用 S6 自行延長有效期限。

## 10. 驗收矩陣

預計新增 `tests/test_lot_scenario.py`，並擴充受影響的 `test_lot_exposure.py`。下列為驗收情境群，不預先承諾測試方法數。

| ID | 驗收情境 |
|---|---|
| A01 | 空 Lot／空 pending 的合法 S5 capture + 完整 synthetic physical，產生 SYNTHETIC_SCENARIO report |
| A02 | source_capture_id 與 capture_id 不同：拒絕，不建立 S4 request |
| A03 | scenario_cut_id 等於 capture_id：拒絕，避免把內容身份冒充共同 cut |
| A04 | scope 任一欄或 ContractSpec 任一欄不同：拒絕 |
| A05 | adapter 不自行生成 cut；相同時間戳不能替代缺失／非法 attestation |
| A06 | capture observed/valid 時間原樣進 Lot/Pending，不刷新為 now 或 physical 時間 |
| B01 | 未成交 OPEN 一對一映射為 SYNTHETIC_LEDGER/UNTERMINATED，Lot 可不存在 |
| B02 | 部分 OPEN 保留 S5 remaining quantity，方向與 effect 不被 override |
| B03 | 部分 CLOSE 保留責任，但 current Gross 不提前減少 |
| B04 | OPEN 全成交但未 terminal：remaining=0 pending 仍存在 |
| B05 | CLOSE 全成交但未 terminal：closed Lot 與 remaining=0 pending 同時存在 |
| B06 | terminal 後 S5 不再有 pending，S6 不自行保留歷史責任 |
| B07 | 多 Bot、多 long/short pending，order_key 一對一成 obligation_id 且固定排序 |
| B08 | OBSERVED S4 request 直接塞 SYNTHETIC_LEDGER 必須拒絕 |
| B09 | SYNTHETIC_SCENARIO 不接受 HELD/EXCHANGE override 來改寫 S5 pending provenance |
| C01 | unmanaged unresolved Lot 非空時 pending.complete=False |
| C02 | unmanaged unresolved Lot 不生成假 UNKNOWN／UNCLASSIFIED order |
| C03 | unresolved Lot 同時出現在 pending 與 unmanaged：invalid_capture |
| C04 | unmanaged 指向不存在／已resolved Lot：invalid_capture |
| C05 | managed unresolved Lot 與 matching pending 完整時不被錯誤降級 |
| C06 | forged capture 內容但沿用舊 capture_id：invalid_capture |
| C07 | duplicate Lot／order_key／bot watermark 或順序不符合 canonical 規則：invalid_capture |
| D01 | physical quantity 只能來自 scenario；Lot Net 不會自動填入 |
| D02 | physical_complete=False 即使 quantity 與 Lot Net 相等仍 UNAVAILABLE |
| D03 | physical_complete=True 且 quantity=None：拒絕矛盾輸入 |
| D04 | 相同 scenario cut、完整新鮮 physical 與完整新鮮 Lot 可得到 MATCH／MISMATCH |
| D05 | 不同數值但相同 cut 精確得到 MISMATCH；沒有 epsilon |
| D06 | mark 缺失不阻止張數比較，但三個 notional 欄位依 S4 規則保持 None |
| D07 | mark 存在時使用原 quote/time；過期／future 沿用 S4 reasons |
| E01 | synthetic buy/sell 進 pending aggregate 與 synthetic 專屬 bucket，不進 HELD/EXCHANGE bucket |
| E02 | physical scenario upper 使用所有 synthetic pending 買賣責任 |
| E03 | virtual gross scenario upper 只加 OPEN pending；CLOSE 不抵銷 current Gross |
| E04 | UNTERMINATED 不使 has_unknown=True；真正 EXCHANGE/UNKNOWN 舊案例維持原語義 |
| E05 | unmanaged unresolved 導致 pending_incomplete／link incomplete，upper 欄位不偽裝完整 |
| E06 | stale capture、stale physical、future observation 各自保留來源 reasons |
| F01 | Decimal 數值等價與 ambient low-precision context 不改結果，不產生 float |
| F02 | lot_size 對齊、極小合法 quantity、邊界 exponent 沿用既有 Decimal 契約 |
| F03 | 所有新 dataclass frozen；adapter 不修改 capture 或 scenario object |
| F04 | S6 純函式：不得出現 SQLite、網路、系統時鐘或檔案 I/O |
| F05 | S5 `test_lot_snapshot.py` 保持；S4 既有 36 個 observed-mode 案例語義不退化 |
| F06 | `git diff --check` 通過；Schema7、risk.py、execution、protection、交易路徑無變更 |

## 11. 實作順序與完成條件

建議後續實作順序：

1. 新增 `catos/lot_scenario.py` 的 frozen evidence/result 型別與純驗證／轉接函式。
2. 對 `lot_exposure.py` 做最小 additive change：`evidence_kind`、synthetic pending taxonomy、synthetic buy/sell buckets，以及總 pending 聚合涵蓋 synthetic origin。
3. 新增 S6 專屬測試，先驗證 provenance／cut／completeness，再驗證 S4 整合算術。
4. Sol 執行 S6 專屬、S4、S5 與直接受影響回歸，再做 diff/staged 檢查。

S6 完成條件：本機 S5 帳本責任能以不冒充交易所狀態的方式進入 S4 合成情境；共同 cut 必須有明示 attestation；unmanaged／stale／unknown 不被轉成零或完整；結果始終標示 `SYNTHETIC_SCENARIO`，且不新增任何交易或風控授權語義。

S6 驗收後才評估下一片。真實 Demo／Live physical／mark 的可信截點、交易所 order 狀態與帳戶 reconciliation 仍屬另一條證據鏈，不由本 synthetic adapter 延伸。
