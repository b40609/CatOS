# S9：成交費用補齊正式資料與重放契約

狀態：2026-09-20，**Sol 文件驗收通過，可進實作授權階段，尚未實作**。依已通過契約審查的 [S9 assessment](catos-s9-fee-completion-assessment.md)，提交 `bb29389`；開發基線為使用者確認的 S8 `b069082`。本文件明定後續設計，**不是執行 Schema 變更或既有 DB migration 的授權**。

## Sol 文件驗收（2026-09-20）

依現行 `journal`、S2 `lot_journal`、S3 `lot_fills`、S4 `lot_exposure`、S5 `lot_snapshot` 與 S6／S7 實碼交叉核對，未發現阻斷缺陷。schema8 的型別、事件分流、completion 去重、terminal 後補費、補 0 版本證據、S2 版本關聯、S5 capture identity 與 S6／S7 品質傳遞均可由現行架構有限延伸；schema7 保留與 S8 舊範例回歸邊界明確。

實作時需維持單一資料庫版本來源：`PRAGMA user_version` 仍是整個 Journal 檔案的 schema 標記，8 表示本規格定義的 Journal schema8；`lot_schema_version` 僅作為呼叫端明示選擇 schema7／8 路徑的參數，不新增第二個持久化版本欄位。明示 8 必須在任何既有 schema1–7 自動升級、WAL pragma 修改或 recovery 寫入前拒絕；預設 7 的既有 schema1–6→7 行為與 schema7 hash／receipt 保持原狀。

## 1. 範圍與版本決策

只處理 local-sim、單訂單單 Lot、USDT 原始缺費成交與 unknown→known completion。qty／price 已知即可更新部位及未扣費的 realized_pnl；費用小計與缺費筆數另行保存。不包含 known→different known、成交更正、funding、非 USDT 換算、多 Lot 分配、風控、交易授權、真實 adapter 或帳戶 net PnL。

| 邊界 | 舊版 | S9 新版 |
|---|---|---|
| SQLite user_version | 7 | 8，僅明示建立新 DB |
| Lot snapshot payload | 現有嚴格欄位與 fees_paid | snapshot_version=2，LotV2 與 fee_quality |
| S3 event payload | 現有無版本 payload，bind／fill／terminal | event_version=2，bind／fill／terminal／fee_completion |
| S2 request／內部 write_id | format_version=1／s3_ 前綴 | format_version=2／s9_ 前綴 |
| S5 capture | 現有 v1 與 schema7 domain | LocalLotCaptureV2，capture_version=2、schema_version=8，domain `catos-local-lot-capture-v2` |
| Worker IPC | 現有 LOT_PROTOCOL_VERSION=2 | 不升級、不接線；舊 wire 明確拒絕 LotV2 |

這些是同一 writer／核心內的有限版本分流，不建立第二個帳本或通用版本框架。新版 snapshot codec 是本機持久化 codec，與 Worker IPC 版本不同，不得因皆稱 v2 而混用。

## 2. 資料型別

以下新增型別均為 frozen／slots dataclass，集合用 tuple；既有 Lot、StoredLot、SyntheticFill 與舊 codec 不放寬。

### FeeQuality

```python
class FeeQuality:
    coverage: Literal["MANAGED", "UNVERIFIED"]
    known_fee_subtotal: Decimal | None
    fee_unknown_fill_count: int | None
```

- MANAGED：subtotal 必須為有限 Decimal，count 為 0..MAX_INTEGER 的 int，bool 不算 int；對完整 S3 成交集合重放可重建。count=0 表示費用完整，count>0 表示缺費。
- UNVERIFIED：subtotal 與 count 必須同時 None；不聲稱已知任何完整的小計或筆數。用於無 S3 逐筆證據的 S2 外部快照；本片不接管此 Lot，不接受補費。
- 正數 fee 為支出、負數為返佣、0 為已知零。MANAGED 小計 0 不能單獨表示完整。
- `fee_complete` 為衍生三態：MANAGED 時 count==0，UNVERIFIED 時 None，不另外保存可能矛盾的布林欄位。

### LotV2／StoredLotV2

LotV2 保留現行 Lot 的 scope、bot_id、inst_id、lot_id、open_intent_key、side、opened_qty、remaining_qty、average_entry、realized_pnl、funding_paid、protection、revision，**以 fee_quality 取代 fees_paid**。禁止提供把 subtotal 當完整 fees_paid 的相容 property。身份、數量、價格及全平後不得復活的規則沿用現行 Lot 校驗。

StoredLotV2 欄位為 lot: LotV2、opening_unresolved: bool、closing_unresolved: bool、commit_seq: int。兩個 unresolved 旗標屬交易生命週期，不因缺費而改變。MANAGED fee_quality 只允許 S3 同交易內寫入；公開 S2 新版快照寫入只接受 UNVERIFIED，不能由外部輸入宣稱 MANAGED。

### SyntheticFillV2／FeeCompletion

SyntheticFillV2 保留舊 SyntheticFill 的 scope、source_id、inst_id、order_id、trade_id、fill_seq、quantity、price；費用欄為 fee_state: Literal["KNOWN", "UNKNOWN"]、fee_paid: Decimal | None、fee_currency: Literal["USDT"]。

KNOWN 必須有合法 Decimal；UNKNOWN 必須 fee_paid=None，但 currency 仍明示 USDT。這是帶狀態的互斥契約，不是舊 SyntheticFill 改成 nullable。qty／price 的精度、對齊與範圍沿用 S3；fee 輸入沿用原始數值限制，subtotal 沿用派生限制。

FeeCompletion 必填 scope、source_id、inst_id、order_id、trade_id、fee_paid: Decimal、fee_currency="USDT"。不接受 bot_id、lot_id、completion_id、qty、price 或 fill_seq；歸屬只能從原成交及綁定取得。

## 3. 公開 API 與 DB 開啟

```python
Journal(path, account_id, fixture_budget, risk_limits=None,
        execution_enabled=False, *, lot_schema_version=7)
journal.lot_fills.apply_fill_v2(fill: SyntheticFillV2) -> EventReceipt
journal.lot_fills.complete_fee(completion: FeeCompletion) -> EventReceipt
journal.lot_fills.get_fee_completion(
    *, scope, source_id, inst_id, order_id, trade_id
) -> EventReceipt | None
journal.capture_lot_snapshot_v2(
    *, scope, inst_id, observed_at_ms, valid_until_ms
) -> LocalLotCaptureV2
```

- 預設 7 保持既有新建與舊版行為；8 必須明示且只接受 risk_limits=None、execution_enabled=False。
- 既有 schema7 以 8 開啟、既有 schema8 以 7 開啟皆拒絕 `schema_version_mismatch`；先讀 user_version 並檢查選擇，再進任何 schema／journal_mode／恢復寫入。拒絕不升降版、不改內容。未知版本拒絕。
- 明示 8 可新建無資料的 DB，或重開既有 schema8；不在 schema1–7 上執行升級。預設 7 的歷史 schema1–6 支援不在本片新增授權內，既有測試行為保留，不對使用者 DB 執行。
- bind_order、finish_order 的呼叫形狀不改，依已選 DB 版本生成對應事件；schema8 的新 fill 僅經 apply_fill_v2，schema7 僅經舊 apply_fill。錯版本 API 拒絕 `unsupported_fee_version`。
- get_order、list_fills 的既有 EventReceipt 結構保留，completion 有獨立查詢。補費不混入 list_fills，不增加 fill_seq 或 recovery 的 fill_count。
- S2 get/list 查詢依 DB 版本返回 StoredLot／StoredLotV2；新版外部寫入用明示 create_v2／replace_v2，參數形狀沿用舊 create／replace，僅接受 LotV2 且 UNVERIFIED。舊寫入 API 不接受新版物件，反之亦然。

上述方法名鎖定；無交易 client、網路或 Worker 暴露。recovery 在 schema8 使用 RecoveryReportV2：原 storage_ready／order_count／fill_count／terminal_count 加 fee_completion_count，保留原欄位語義，不把 completion 算成交。

## 4. Schema8 的結構契約

僅建立全新 schema8；以下相對 schema7 的欄位差異構成 DDL 契約，未列出的欄位、STRICT、PK、FK、CHECK、長度與收據限制全部保留。正式實作需將完整 DDL 固定為版本專屬常數，recovery 比對本版本完整結構；不得在 schema7 上 ALTER 或放寬舊常數。

### S2 lot_revisions

移除 schema8 表的 fees_paid，新增：

```sql
fee_coverage TEXT NOT NULL CHECK(fee_coverage IN ('MANAGED','UNVERIFIED')),
known_fee_subtotal TEXT CHECK(known_fee_subtotal IS NULL OR typeof(known_fee_subtotal)='text'),
fee_unknown_fill_count INTEGER CHECK(fee_unknown_fill_count IS NULL OR
    fee_unknown_fill_count BETWEEN 0 AND 9223372036854775807),
CHECK((fee_coverage='MANAGED' AND known_fee_subtotal IS NOT NULL
       AND fee_unknown_fill_count IS NOT NULL)
   OR (fee_coverage='UNVERIFIED' AND known_fee_subtotal IS NULL
       AND fee_unknown_fill_count IS NULL))
```

SQLite 不做金融加總或數值 CAST；TEXT 解析、精度與 canonical 身份由 Decimal 校驗。fee_quality 必須同時存在 S2 request_json 中，recovery 逐欄比較，不能只新增三個 SQL 欄位。

### S3 lot_fill_events

schema8 新增 fee_state TEXT NOT NULL，限定 KNOWN／UNKNOWN；fee_paid 為 TEXT 或 NULL，CHECK 強制 KNOWN→非 NULL TEXT、UNKNOWN→NULL。fee_currency 保留 NOT NULL／USDT。原 PK(order_key, trade_id)、UNIQUE(order_key, fill_seq)、order FK、seq 及 Lot receipt 保留。schema7 原 fee_paid TEXT NOT NULL 不變。

### 新表 lot_fee_completions

欄位：order_key TEXT NOT NULL、trade_id TEXT NOT NULL、fee_paid TEXT NOT NULL、fee_currency TEXT NOT NULL CHECK='USDT'，以及既有 S3 共用 seq／request_json／request_hash／lot_id／revision／commit_seq。

- PRIMARY KEY(order_key, trade_id)。
- FOREIGN KEY(order_key, trade_id) REFERENCES lot_fill_events(order_key, trade_id)。
- seq 為正整數、單表 UNIQUE，跨四表全域連續性由 replay 驗證。
- lot_id／revision／commit_seq 對此表必須全非 NULL；引用 S2 lot_revisions，UNIQUE(lot_id, revision)。其餘共用長度、正值限制沿用 S3。
- 每列不可變，無 UPDATE／DELETE 業務 API、trigger 或獨立 connection。

四個 S3 表依 seq 合併；跨表同 seq 或同 Lot revision 都拒絕。schema8 保留 lot_bindings／lot_heads 及既有 v1 表結構，僅透過既有 Journal 的同一交易寫入，不新增 writer。

## 5. Payload、canonical 與身份

新版 Lot wire 的頂層為 snapshot_version=2 及 LotV2 全部欄位；fee_quality 精確包含 coverage、known_fee_subtotal、fee_unknown_fill_count。Decimal wire 使用受驗證字串，None 用 JSON null，未知鍵、漏鍵、錯版皆拒絕。不允許把缺 fee_quality 的新版物件預設成完整。

S2 新版 request 保留既有欄位，將 format_version 明示設為 2，其中 after 使用新版 Lot wire。request hash 前，after 的一般金融欄位及 fee_quality.known_fee_subtotal 採既有 `_numeric_identity`；None 保留 null，coverage 與 count 原樣保留。request_hash 使用既有 canonical JSON／SHA256 邊界，但包含版本及完整 fee_quality；不重算舊版 request_hash。

S3 新版事件精確欄位為：

| kind | 欄位 |
|---|---|
| bind | 現行 bind 全欄位＋event_version=2 |
| fill | 現行 fill 全欄位＋event_version=2＋fee_state；fee_paid 依狀態為 canonical 數值或 null |
| terminal | 現行 terminal 全欄位＋event_version=2 |
| fee_completion | event_version、kind、scope、source_id、inst_id、order_id、trade_id、fee_paid、fee_currency |

event_version 精確為整數 2，bool 拒絕；原始事件不可變。event canonical 金額沿用 S3 `_number` 數值身份；0.10／0.1、0／負零等價，非有限值與 float 拒絕。Bot／Lot 不在 completion payload，從原綁定取得。

order_key 與 intent／Lot identity 沿既有算法，版本不得改變既有業務身份。schema8 內部 S2 write_id 為 `s9_`＋SHA256(canonical object `{seq, fingerprint}`) 前 61 字元；公開 S2 寫入拒絕 s3_／s9_ 保留前綴。舊 schema7 hash／write_id 不變。

## 6. 重送與錯誤優先序

一次寫入先驗版本／型別／scope，再於既有 `_access` 交易內完整 recovery，接著依不可變業務鍵找已存在事件：

1. 已存在且 canonical request 相同，返回原 EventReceipt，replayed=True；不增加 seq／revision／fee。
2. 已存在但合法 canonical 內容不同，`write_conflict`；不得改為新 ID 重送。
3. 不存在才做目標與事件生命週期驗證並追加。

completion PK 是原成交鍵，不另設訊息 ID。找不到該 fill→`fee_target_not_found`；原 fill 為 KNOWN→`fee_not_pending`；不受管 Lot→`unmanaged_lot`。非法幣別先回 `unsupported_fee`，非法金額沿 `invalid_fill`；因此不同非 USDT 幣別被輸入驗證拒絕，不要求一定回 write_conflict。UNKNOWN／KNOWN 配對錯誤回 `invalid_fee_state`。

schema8 中 UNKNOWN fill 補齊後重送原 UNKNOWN payload 仍回原 fill 收據；改成 KNOWN payload 會 write_conflict。terminal 後同內容 fill／completion 重送亦走原收據；不得以 done 擋掉合法重放。新 fill 仍受 order_unavailable 終態禁令。

caller 衝突不使健康 handle 失效；recovery 偵測損毀→integrity_error 並失效；儲存／COMMIT 不確定沿既有 S2 storage_unavailable 與重開規則，不吞掉、換鍵或自動重送。查詢 absent completion 返回 None 不表示其原成交 fee 一定未知。

## 7. Reducer 與事件順序

增量寫入與啟動 recovery 使用同一 deterministic evaluator。四表依 seq=1..N 重放，拒絕缺號／重號，不將 completion 插回原 fill 位置，也不依 trade_id／金額重排。

replay 狀態至少包含 orders、每 Lot 最新 StoredLotV2、active order、原始 fill map 與已完成 fee map。它們均由事件重建，不另持久化可變旁路 cache。

### fill

保留既有 binding、fill_seq、qty／price、terminal、overfill 校驗。部位與 realized_pnl 使用原有 50 位 ROUND_HALF_EVEN Decimal 算術；共用純部位計算，不把未知 fee=0 送進舊完整費用模型冒充已知。

- 首個受管 fill 建立 MANAGED 品質：KNOWN 初始化小計 fee、count=0；UNKNOWN 初始化小計 0、count=1。
- 後續 KNOWN fill 小計加 fee，count 不變；UNKNOWN 小計不變，count+1。
- 每個合法 fill 都是獨立成交，count 不按張數計；更新費用品質與部位在同一版本中。
- 小計加法使用現行 research Decimal context（prec=50、ROUND_HALF_EVEN），對外部 context 隔離，結果依現有派生界限驗證；不是另用 sorted sum 或無限精度總和。重放依同一事件順序得到完全相同結果，算術錯誤拒絕整筆交易。

### terminal

只依成交 seq／total／status 驗證，unknown count 不阻止 terminal。保留最新 fee_quality，沿原生命週期清除該 active order；費用仍 unknown 時不得創造交易 pending。

### fee_completion：兩項強制規則

**規則一：使用事件當下的 head／active 狀態。** 找到目標原 UNKNOWN fill 後，取目前 Lot head 的完整 StoredLotV2，不取原 fill 的舊版本。先用 replay active map 驗證目前旗標：無 active→兩者 false；active OPEN→true／false；active CLOSE→false／true。不一致即 integrity_error，不自行修補。completion 後原樣保留這兩個已驗證旗標。

補費分支在目標 order.done 拒絕新 fill 的路徑之外；不更新 active、done、total、fill count 或 terminal 收據。可補歷史 OPEN、目前 CLOSE、terminal 後或全平 Lot，只要該原 fill 仍 UNKNOWN。

**規則二：品質與版本一起改。** subtotal 加本筆 fee、unknown count 減一、revision+1；coverage 維持 MANAGED。count 原為 0 或 map 與 count 不一致視為損毀。金額 0 仍因 count 改變建立版本；不能繞過 no_change，也不能省略收據。

除此之外，scope／Bot／Lot 身份、opened／remaining qty、average_entry、realized_pnl、funding_paid、side、protection 全部原樣。更新 current head，不回寫歷史版本。已接受的 CLOSE binding 保留；尚未接受且引用舊 revision 的意圖仍 revision_conflict。

## 8. 原子收據與完整性

同一 SQLite 交易包含：事件 payload／seq／hash、新 S2 revision 及 fee_quality、head／Bot 水位、事件 receipt。任一失敗 rollback，不得只記 completion 或只改 subtotal。completion 的事件 seq 與 S2 commit_seq 分屬原有序列，不混為同一值。

recovery 先按 schema8 S2 結構驗證，再 S3 四表完整重算。逐事件核對 canonical hash、冗餘欄位、目標 fill、唯一 fee 來源、S2 after payload／品質／旗標／revision／write_id／commit_seq。每個受管版本或 s9_ 版本必須反向對應唯一事件；同版被跨表重複引用拒絕。

必須拒絕：孤立 completion、重複歸屬、刪除 completion 後殘留版本（包含尾端及補零）、刪除版本後殘留事件、修改 coverage／count／subtotal、跨 Bot 歸屬、seq 缺口及跨表重號。不能只憑 count>=0 或 FK 通過認定完整。

不保證偵測整個 DB 與全部證據一致回退到舊副本；不新增外部錨點。COMMIT 後 ACK 遺失使用原鍵取得相同 receipt；重啟不再次累計費用。

## 9. S5 capture、S6 與 S7 品質傳遞

LocalLotCaptureV2 精確欄位：capture_version=2、schema_version=8，加現有 LocalLotCapture 全部欄位；lots 改為 tuple[StoredLotV2,...]，source 仍 synthetic_ledger。pending 與 unmanaged unresolved 的交易語義不變，不把缺費列入這兩者。

capture_lot_snapshot_v2 保留同一 read transaction、metadata 首讀、recovery→物化→hash→ROLLBACK 的時序，64 Bot／4096 Lot／4096 pending 上限不變，closed Lot 仍納入。

新版 hash 用 domain `catos-local-lot-capture-v2`，沿用逐 fragment canonical object＋8-byte big-endian 長度前綴；header 含兩個版本與既有 scope／contract，Lot fragment 包含完整 fee_quality。subtotal 使用既有數值身份，UNVERIFIED None 保留 null；count、coverage、revision、旗標均進 hash，時間與 DB path 仍不進 hash。任何品質改變都改 capture_id；不同 Decimal 等價表示不改數值身份。

S6 新增明示 `observe_synthetic_scenario_v2` 與 SyntheticScenarioObservationV2；同既有參數名 capture／scenario／now_ms，scenario 可沿用既有 SyntheticScenarioEvidence 型別，須精確綁定新版 capture。舊入口只接受 v1，新入口只接受 v2。新版校驗全部品質欄位、hash 及交易關聯，不把不完整 Lot 轉成舊 Lot 再驗證。

S4 共用既有數量／估值算術，但新版輸入使用明示 LotInventoryV2／ExposureRequestV2 與 `observe_exposure_v2`；只替換庫存型別驗證，report 仍是既有 ExposureReport。禁止偽造 fees_paid=0 的舊 Lot 適配；不得複製第二套 Gross／Net 算術。

ObservationV2 欄位為 observation_version=2、evidence_kind、scenario_cut_id、source_capture_id、report、fee_quality；此處 fee_quality 是按 lot_id 排序的 tuple[LotFeeObservation,...]。LotFeeObservation 精確包含 lot_id、bot_id、revision、coverage、known_fee_subtotal、fee_unknown_fill_count、fee_complete。涵蓋 capture 的全部 Lot，無缺漏／重複／多餘 Lot；fee_complete 由來源品質推導，不接受 caller 覆寫。

S7 新增 `render_synthetic_scenario_report_v2`，呼叫一次新版 S6，保留既有報告區塊，新增「費用品質」表，逐 Lot 列出上述欄位，長表允許自然延展／捲動，不截斷。欄位全為 Decimal／int／字串格式化，不計 net PnL。

- MANAGED count>0 顯示「費用不完整」、`fee_incomplete`、缺費筆數；subtotal 標「已知費用小計，非全部費用」。
- UNVERIFIED 顯示「費用涵蓋範圍未驗證」、`fee_coverage_unverified`；小計／筆數顯示不可用，不填 0。
- MANAGED count=0 顯示「費用已完整」，仍明示 funding 未知，不代表完整淨損益。
- 空 Lot 集合顯示「無 Lot 費用資料」，不宣稱整個帳戶帳務完整。
- 費用原因留在品質區，不加入 ExposureReport.reasons，不將 pending_complete、fresh、MATCH、has_unknown 改判；舊版 S7 不接受新版 capture。

S8 固定範例仍用 schema7 與舊 API，保持原完整費用基準及既有輸出；S9 品質範例由專屬測試建立，不新增 S8 CLI 選項。禁止把 S8 已知費用顯示改成未知以掩蓋相容問題。

## 10. 具體事件驗收軌跡

單一 long Lot，base_per_contract=0.01，所有成交 price=100；費用支出為正。以下小計與 count 為每個事件之後的值。

| 事件 | remaining | subtotal | count | opening／closing |
|---|---|---|---|---|
| OPEN 3 張，第一 fill 1 張 UNKNOWN | 1 | 0 | 1 | true／false |
| 第二 fill 2 張 KNOWN fee=0.02 | 3 | 0.02 | 1 | true／false |
| OPEN terminal FILLED | 3 | 0.02 | 1 | false／false |
| 綁定 CLOSE 全部 3 張 | 3 | 0.02 | 1 | false／true |
| 補第一筆 OPEN fee=0 | 3 | 0.02 | 0 | false／true |
| CLOSE fill 3 張 UNKNOWN | 0 | 0.02 | 1 | false／true |
| CLOSE terminal FILLED | 0 | 0.02 | 1 | false／false |
| 補 CLOSE fee=-0.01 | 0 | 0.01 | 0 | false／false |

每個有 Lot 更新的事件 revision 前進一次；補零重送不前進。平均成本保持 100、此軌跡 realized_pnl=0、funding=None；已建立 CLOSE 的後續 fill 仍合法。反向 short、部分取消及非零價差另測，不只測此一例。

## 11. 完整驗收矩陣

| ID | 案例與必須證明的結果 |
|---|---|
| A01 | KNOWN／UNKNOWN 欄位配對、USDT、非法 float／NaN／Infinity／bool count，型別與 wire 邊界拒絕 |
| A02 | MANAGED／UNVERIFIED 三態約束，缺欄位／未知鍵／版本錯誤不默認完整 |
| A03 | 多空 OPEN／CLOSE 部分成交缺費，成本／價差與完整費用路徑一致，count 按成交數 |
| A04 | 正費／返佣／已知零與 unknown 小計 0 明確不同；低精度外部 context 不影響結果 |
| A05 | 費用累加大／小數及派生上下界，逐事件增量與重放完全一致 |
| B01 | 同 completion 重送／Decimal 等價返回原 receipt、seq／revision 不變，費用只計一次 |
| B02 | 不同金額衝突、原 KNOWN 即使同金額也非待補；非 USDT 輸入拒絕 |
| B03 | 補齊後重送原 UNKNOWN fill 合法；把原 fill 改為 KNOWN 衝突 |
| B04 | 不存在 fill、跨 scope／order／trade 歸屬、無成交 REJECTED 無法補費 |
| C01 | OPEN 仍 active／terminal 後／部分 CANCELED 後補費，done、total、fill_seq 不變 |
| C02 | 第 10 節完整軌跡，歷史 OPEN 補費保留 active CLOSE 旗標，後續 CLOSE 成交合法 |
| C03 | 全平 Lot 補費不復活、平均成本／損益／protection 不變，closed Lot 品質仍在 capture |
| C04 | 零 completion 新 revision／count 下降，no_change 不被放寬；重送無第二版 |
| C05 | 舊 expected_revision 新意圖拒絕，已接受 binding 不重建；同時存在 fee incomplete 與無交易 pending |
| D01 | 四表 seq 連續、重號／缺號／非法事件版本拒絕；replay 不把 completion 插回 fill 時點 |
| D02 | completion→revision→completion 雙向唯一；刪尾端補零／非零事件、孤立版、孤立 fee 均拒絕 |
| D03 | 竄改 coverage／subtotal／count／flags／hash／冗餘欄位，重複成交歸屬或跨 Lot 版本拒絕 |
| D04 | 故障注入任一原子寫入點 rollback，沒有只更新小計或只存 completion |
| D05 | Windows 真實程序 COMMIT 前終止：重開無半筆；COMMIT 後 ACK 前終止：同鍵查詢／重送不重計 |
| D06 | 全平後與 active CLOSE 中補費，重啟後每個 S2 版本／收據／水位／flags 完全一致 |
| E01 | schema7 DDL／SyntheticFill／canonical／replay／capture hash／收據保持原值，無 nullable 放寬 |
| E02 | 新建與重開8明示、錯版開啟在變更前拒絕；舊 DB 不升級、不改 pragma，未知版本拒絕 |
| E03 | 舊／新版 API、codec 與 capture 互相拒絕錯版，不把 incomplete 投影到 fees_paid |
| E04 | schema8 外部 S2 只准 UNVERIFIED，不能 forge MANAGED；受管寫入沿內部交易門檻 |
| F01 | S5 同讀取交易含 fee state，補費競爭下只見前或後完整組合；零補費亦改 capture identity |
| F02 | 修改 quality 而沿用舊 hash 拒絕；數值等價 hash 一致；closed Lot 納入、非受管不假設 count=0 |
| F03 | S6 原樣傳遞完整品質，Lot 對照無遺漏／重複，費用原因不污染 exposure reasons |
| F04 | S7 MANAGED incomplete／complete／UNVERIFIED／空集合、長 Decimal、HTML 逸出與不可用顯示 |
| F05 | qty、notional、MATCH／pending_complete 原值不因 fee 改判；不輸出 net PnL 或交易許可 |
| F06 | 原 S8 schema7 範例與必要 S7 回歸維持；新版費用品質完整／缺費樣本於桌面及窄視窗可讀 |

上述是情境群，非預估測試方法數。持久化與 Windows 中斷用真實臨時 DB／程序；不可全部用 mock 取代。故障注入及非法 payload 可用受控 stub，需註明。schema7 相容測試使用歷史格式 fixture／既有 tests，不接使用者資料庫。

## 12. 分工、授權與交付

Astra 制定階段只建立正式文件，沒有修改程式、DDL、DB 或 AGENTS，也沒有執行 Python、測試或編譯。Sol 已完成新型別／schema 差異／版本邊界／錯誤優先序與上述兩條 completion 強制規則的文件驗收；下一步仍須由使用者明確授權程式與新建 schema8 合成 DB 的實作驗證。既有 DB migration 不在本規格內。

開發可分純型別／reducer、同 writer 持久化／replay、capture／呈現三個內部步驟，但未完成跨層驗收前不得宣稱 S9 整體完成。Astra 編寫，Sol 驗證與 Git；只跑受影響專屬及必要回歸，不自行跑全量或市場回測。

market、yaoI／yaozi 與既有 S7 等未提交補記均獨立；README／WORK_PLAN 的 S9 新段落提交時須與舊補記分開。本文不是交易或真實採集授權。
