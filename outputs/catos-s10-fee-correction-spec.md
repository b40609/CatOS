# S10：已知成交費用更正正式資料與重放契約

狀態：2026-09-21，**Sol 規格審查通過、使用者授權實作、Astra 完成程式與測試後，Sol 已完成獨立驗收，S10 通過**。P1A／P2A不變；本輪實測 S10 專屬 34/34、必要 Lot／Journal 回歸 344/344、目標檔 `py_compile`、scoped `git diff --check` 與 F05 1280／390 px 視覺 QA 均通過。實作與完整驗證證據見 [S10 驗收交接](../docs/lot-fee-correction-handoff.md)。既有 DB migration與交易接線仍未授權。以下審查及第12節保留規格／開發階段歷史，不代表目前仍待驗收。

依據：[S10 assessment 最新政策](catos-s10-accounting-gap-assessment.md)、[S9 規格](catos-s9-fee-completion-spec.md)、[S9 驗收交接](../docs/lot-fee-completion-handoff.md)。本輪唯讀核對現行 lot_accounting、lot_fills、lot_journal、lot_schema8、lots、research、Journal 與 capture／scenario 型別；沒有執行 Git、Python、Decimal 探針、DB 或測試。S9 344/344 為歷史證據，不是本輪重驗。

## Sol 獨立規格審查（2026-09-21）

未發現阻斷缺陷。P1A 的 identity／重送／no-change 優先序、P2A 的「先扣舊再加新」兩步 Decimal 契約、精確前驅防分叉、current head／active flags、不改 unknown count 與非費用欄位等，均與現行 S9 實碼邊界相容。schema9、event／S2 request／capture v3 是本規格的新版本選擇，不倒寫成 assessment 當時已核准政策；schema7／8 仍固定且不遷移。

審查補強兩個實作時不得模糊的版本邊界：第一，schema9 雖沿用 LotV2／snapshot_version=2，但 S2 request 必須為 format_version=3；因此 LotV2 codec／validator 的選擇不得再由現行 `schema_version == 8` 這個條件隱含決定。第二，S2 僅 revision 變動的 correction 特例只能先做結構性延後判定，Journal 建構完成、任何 schema9 公開 S2／S3 查寫及 capture 對外返回前，都必須完成 S3 deterministic replay 並反向證明該版本唯一對應合法 correction。不能把「結構掃描通過」當成完整 recovery 成功。

另鎖定 V3 capture header 的 `format` 精確為 `catos-local-lot-capture-v3`，與 hash domain 一致，避免只換外層 domain 卻沿用 v2 header 造成兩種實作。以上屬規格澄清，未擴張功能範圍或新增帳務政策。本輪未執行 Python、Decimal 探針、DB、migration、單元測試或視覺驗證。

## 1. 範圍、失敗情境與交付邊界

原成交費用已記 0.02 USDT，後續合成證據改成 0.015；S9 completion 只接受 unknown→known，不能覆寫已知費用。S10 以不可變 correction 事件替換該成交的目前有效費用，原 fill／completion 及所有既有收據原樣保留。

僅 local-sim、受管成交、單訂單單 Lot、USDT。原 KNOWN fill 與 UNKNOWN 經 completion 後都可更正；尚 UNKNOWN 必須先走 S9 completion，UNVERIFIED 不接管。允許正費、返佣及已知零之間更正，不改成交 qty／price／歸屬。無 funding、成交撤銷或數量更正、幣別換算、多 Lot 分配、帳戶 net PnL、交易／風控／P6／真實 adapter／Worker 接線。

本片完整交付包含 reducer、同 writer 持久化與 recovery、capture／S6／S7。最小做法是沿用 LotV2 與現有曝險算術，加一種事件、一張表、精確前驅查詢與新版 capture 入口；不增加第二個帳本、常駐服務、可變費用 head 表或完整歷史 UI。驗證成本主要為更正鏈、有限精度、原子收據、版本隔離與跨層品質；不以新增通用框架解決。

## 2. 已定案政策與本規格版本選擇

### 使用者已定案

- **P1=A：** 新 identity 的 fee 與目前有效 fee 數值等價時，拒絕 `no_change`，不保存事件、不消耗 seq、不推進 revision。已接受 identity 同 canonical payload 重送先回原收據；不重做 no-change 或前驅判定。
- **P2=A：** 既有 Decimal context 下，先算 `intermediate = current_subtotal - old_effective_fee`，驗證 intermediate，再算 `next_subtotal = intermediate + new_fee`，驗證 next_subtotal。不得重寫成 subtotal + (new-old)，也不得改成全部有效費用重加。接受有限精度往返痕跡；相同歷史必須精確重放。

### 正式規格選定，Sol 審查通過

| 契約 | S10 選擇 | 相容邊界 |
|---|---|---|
| Journal schema | 9，僅明示新建／重開9 | schema7／8 固定 DDL、hash、收據及 recovery 不變 |
| Lot snapshot | 沿用 snapshot_version=2、LotV2／StoredLotV2 | 不增加欄位，不偽造 fees_paid |
| S2 request | format_version=3，schema9 全部 S2 寫入適用 | 7 維持1、8 維持2 |
| S3 event | event_version=3，含五種事件 | 9 不混入 event_version=2 |
| 內部 write_id | `s10_`＋hash 前60字元，共64字元 | schema7／8 的 s3_／s9_ 原值不變 |
| S5 capture | LocalLotCaptureV3，capture_version=3、schema_version=9 | v1／v2 不接受 schema9 |
| S6 observation | SyntheticScenarioObservationV3，observation_version=3 | 精確新版入口，舊版不放寬 |
| S4／Worker IPC | 沿用 LotInventoryV2／ExposureRequestV2；IPC 不升版 | 不接 Worker、不增加第三套數量算術 |

assessment 當時未指定版本；本節是本輪制定的具體契約，不能倒寫為當時已核准 schema9。PRAGMA user_version 仍是整個 DB 唯一持久化 schema 版本，沒有另一個 lot_schema_version 儲存欄位。

## 3. 型別、身份與查詢

新增型別皆 frozen／slots dataclass。Decimal 不接受 float、int 或 bool 代替；整數欄位拒絕 bool。

```python
class FeeCorrection:
    scope: LotScope
    source_id: str
    inst_id: str
    order_id: str
    trade_id: str
    correction_id: str
    predecessor_event_seq: int
    fee_paid: Decimal
    fee_currency: Literal["USDT"] = "USDT"

class EffectiveFee:
    scope: LotScope
    source_id: str
    inst_id: str
    order_id: str
    trade_id: str
    fee_state: Literal["KNOWN", "UNKNOWN"]
    fee_paid: Decimal | None
    fee_currency: Literal["USDT"]
    effective_event_seq: int | None
    effective_event_kind: Literal["fill", "fee_completion", "fee_correction"] | None
```

scope 沿 LotScope 驗證且必須對應當前 Journal 的 local-sim 帳戶。source／inst／order／trade／correction_id 採現有 token 規則 `[A-Za-z0-9_-]{1,64}`；predecessor_event_seq 為 1..9223372036854775807。輸入重建驗證，不信任 frozen 物件未被繞過建構。

correction identity 精確為 **(order_key, trade_id, correction_id)**；order_key 沿 `_key(scope, source_id, inst_id, order_id)`，不改既有業務身份。相同 correction_id 可用於不同成交；同成交同 ID 不可改內容。沒有自動生成 ID 或以換 ID 重試衝突的 API。

UNKNOWN 的 EffectiveFee 為 fee_paid／effective_event_seq／effective_event_kind 同時 None；原 UNKNOWN fill 的 seq 不能冒充已知費用前驅。KNOWN 的三者必須完整，seq 指向原 KNOWN fill、completion 或最近 correction。每次合法 correction 後，即使小計因捨入未變，effective fee 與前驅仍更新。

```python
Journal(..., lot_schema_version=9)
journal.lot_fills.correct_fee(correction: FeeCorrection) -> EventReceipt
journal.lot_fills.get_fee_correction(
    *, scope, source_id, inst_id, order_id, trade_id, correction_id
) -> EventReceipt | None
journal.lot_fills.get_effective_fee(
    *, scope, source_id, inst_id, order_id, trade_id
) -> EffectiveFee | None
```

get_effective_fee 在同一 `_access` 交易內 recovery 後回傳當時有效值；不存在成交回 None，尚 UNKNOWN 回明示 UNKNOWN，不能把兩者合併。查詢只是取得前驅，不保留寫入權；查後若已被更正，寫入須拒絕失效前驅。get_fee_correction 找不到已接受 identity 回 None；no-change 被拒絕的 ID 沒有收據，不是已占用 identity。

correct_fee、get_fee_correction、get_effective_fee 均限定 schema9；schema7／8 呼叫一律 unsupported_fee_version。兩個查詢入口依第6節驗版本、scope 與所需身份 tokens，然後完整 recovery；查詢不存在不是繞過完整性檢查的捷徑。

EventReceipt 沿用 event_seq、request_hash、lot_id、revision、commit_seq、replayed。首次成功 replayed=False；查詢為 False；同內容重送為 True，其餘原收據欄位不變。查詢沒有新增 list-all API。

schema9 沿用 bind_order、apply_fill_v2、complete_fee、get_fee_completion、finish_order、get_order、list_fills 的呼叫形狀，由 DB 版本生成 v3 事件。list_fills 不混入 correction。RecoveryReportV3 精確包含 storage_ready、order_count、fill_count、terminal_count、fee_completion_count、fee_correction_count，各 count 各自計數。

## 4. DB 開啟、DDL 與版本隔離

預設 lot_schema_version=7 不改。明示9僅接受 risk_limits=None、execution_enabled=False。先唯讀檢查 user_version，再決定分流；既有非9、未知版或非空 user_version=0 檔案以9開啟皆在 WAL pragma、DDL、recovery 寫入之前拒絕 `schema_version_mismatch`，不升降版。9 可新建空 DB 或重開9；既有9以7／8開啟同樣先拒絕。既有7、8開啟契約不放寬，不對使用者 DB 執行 migration。

schema9 的既有 Journal 非 Lot 表與 schema8 相同；Lot 的 lot_bindings、lot_heads、lot_revisions，以及四張既有 S3 表，**逐字沿用 catos/lot_schema8.py 的 LOT_SCHEMA／FILL_SCHEMA 與其引用之既有固定常數**，不修改來源常數。未列出的欄位、順序、PK／FK／UNIQUE／CHECK／STRICT 都不變。完整 schema9 manifest 由以上固定基表加下列完整新表組成，recovery 檢查全部結構；後續不得藉修改共用常數改動 schema7／8。

```sql
CREATE TABLE lot_fee_corrections (
    order_key TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    correction_id TEXT NOT NULL CHECK(length(correction_id) BETWEEN 1 AND 64),
    predecessor_event_seq INTEGER NOT NULL
        CHECK(predecessor_event_seq BETWEEN 1 AND 9223372036854775807),
    fee_paid TEXT NOT NULL CHECK(typeof(fee_paid)='text'),
    fee_currency TEXT NOT NULL CHECK(fee_currency='USDT'),
    seq INTEGER NOT NULL UNIQUE CHECK(seq BETWEEN 1 AND 9223372036854775807),
    request_json TEXT NOT NULL
        CHECK(length(CAST(request_json AS BLOB)) BETWEEN 1 AND 65536),
    request_hash TEXT NOT NULL
        CHECK(length(request_hash)=64 AND request_hash NOT GLOB '*[^0-9a-f]*'),
    lot_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision BETWEEN 1 AND 9223372036854775807),
    commit_seq INTEGER NOT NULL CHECK(commit_seq BETWEEN 1 AND 9223372036854775807),
    PRIMARY KEY(order_key,trade_id,correction_id),
    FOREIGN KEY(order_key,trade_id) REFERENCES lot_fill_events(order_key,trade_id),
    FOREIGN KEY(lot_id,revision) REFERENCES lot_revisions(lot_id,revision),
    UNIQUE(lot_id,revision),
    UNIQUE(predecessor_event_seq),
    CHECK(predecessor_event_seq<seq)
) STRICT
```

predecessor 是五張表的全域 seq，不能用只指向 corrections 的 FK；由 replay 驗證其存在、種類、同成交歸屬與當時有效性。UNIQUE(predecessor_event_seq) 防止兩個後繼；它不能取代跨表全域 seq 唯一與鏈語義驗證。SQL 不解析／加總／CAST 金融 TEXT；所有金額由 Decimal 校驗。

無 UPDATE／DELETE 業務 API、trigger、第二個 connection 或第二個 writer。有效費用 map 僅由不可變事件重建，不新增持久化 fee head cache。

## 5. Payload、canonical 與 S2 收據

schema9 五種 S3 payload 均必填 event_version=3，精確 int，不接受 bool。bind／fill／terminal／fee_completion 欄位沿 S9，只有版本改3；fee_correction 精確欄位如下，未知鍵、漏鍵拒絕：

```text
event_version, kind, scope, source_id, inst_id, order_id, trade_id,
correction_id, predecessor_event_seq, fee_paid, fee_currency
```

kind 固定 `fee_correction`。scope 精確為 account_ref／environment；fee_paid 為 bounded Decimal 字串，經現有 `_number` canonical 化；0.02／0.020、0／負零數值身份相同。API 先按原始輸入界限驗證再 canonical 化，不能利用先去零繞過輸入限制。payload 不接受 old_fee、delta、bot_id、lot_id、qty、price 或 caller 指定 revision；舊有效值與歸屬只能從 replay 取得。

JSON 沿現有 `_json`／SHA256、UTF-8 上限65536 bytes、純資料與嚴格鍵集合契約；hash 包含版本、target、identity、精確前驅及完整費用。資料庫 request_json 必須已 canonical，不能只接受 hash 相同卻無法重建的欄位。冗餘欄位需與 payload 一致。

schema9 S2 request 與 S9 的精確欄位相同，format_version 改3；after 仍使用 snapshot_version=2 的 LotV2 wire。一般金融欄位與 fee subtotal 仍採 `_numeric_identity`，None 保持 null。schema9 所有 S3 事件的內部 write_id 為 `s10_`＋SHA256(canonical `{seq, fingerprint}`) 前60字元；fingerprint 是事件 request_hash。不改 schema7／8 的算法或重算舊資料。

schema9 的 Lot 持久化仍必須使用 LotV2 codec、`lots.validate_lot_v2` 與 V2 financial 欄位集合；這個資料型別選擇與 Journal schema 版本號分開判定。不得因現行 `LotJournal` 以 `schema_version == 8` 選擇 V2 codec，就讓 schema9 回退到 v1 Lot codec／validator；也不得因此把 S2 request 留在 format_version=2。

公開 S2 schema9 create_v2／replace_v2 仍只能寫 UNVERIFIED，並拒絕 s3_／s9_／s10_ 保留前綴。schema7／8 的保留前綴與既有輸入／收據契約不變；schema9 的新內部命名不能反向套用到舊版。

## 6. 精確前驅、更正鏈與錯誤優先序

predecessor_event_seq 指 **Journal S3 全域 event seq**，不是 bind payload 的 Worker event_seq、fill_seq、Lot revision 或 S2 commit_seq。

第一個前驅只能是同成交的原 KNOWN fill 或由 UNKNOWN 轉 KNOWN 的 completion；之後只能是該成交最近 correction。不得引用其他成交、bind／terminal、未來事件、UNKNOWN fill 或舊更正。0.02→0.015→0.02 之後，最初0.02的 seq 已失效。

correct_fee 順序固定如下：

1. 驗 API／DB 版本、型別／scope／local-sim，再依序驗 target tokens、correction_id、前驅整數、幣別、原始 fee Decimal，生成 canonical payload。非法輸入不因 ID 已存在而跳過驗證。
2. 在既有同 writer `_access` 交易中完成 S2＋S3 recovery；損毀優先回 integrity_error，不回成功收據。
3. 查 correction identity。已存在且 canonical request 完全相同，先回原收據；已存在且合法內容不同，`write_conflict`，不再檢查目前 head／前驅／no-change。
4. 新 identity：找不到目標 fill→`fee_target_not_found`；其受管狀態不符→`unmanaged_lot`。正常公開 API 對不存在逐筆證據的 UNVERIFIED Lot 只能找不到 fill；損毀的 MANAGED／UNVERIFIED 關聯應已在 recovery 被拒絕。
5. 目標有效費用尚 UNKNOWN→`fee_not_known`；無自動 completion。其後要求 predecessor 精確等於目前有效 seq，不符→`fee_predecessor_conflict`，即使新金額等於目前值也先拒絕前驅。
6. 前驅有效後，比對新 fee 與舊有效 fee 的 Decimal 數值；相同→`no_change`。不得以 Lot subtotal 是否變化代替此比較。
7. 驗證當前 head／active flags、count 與重放狀態；檢查 seq／revision／Bot commit_seq 不溢位，否則 `sequence_exhausted`。依第7節計算，再同交易追加事件、版本、水位與收據。

新 API 的錯版沿 `unsupported_fee_version`；scope 沿 `scope_mismatch`；型別／token／前驅整數／fee 輸入錯誤統一 `invalid_fee_correction`，非 USDT 為 `unsupported_fee`。算術／中間值非法為 `invalid_decimal`。既有 API 在7／8的錯誤契約不改。schema9 的其他事件沿 S9 優先序。

所有 caller 拒絕不新增事件或占用 identity，不使健康 handle 失效。no-change 未接受的 ID 日後再提交，按當時完整條件判定，不提供被拒請求的歷史收據。已接受 correction 後再送原 fill／completion 仍回各自原收據，不能被新 fee 覆寫。

## 7. Decimal 與當前 Lot reducer

原始 fee 界限沿 research._decimal：有限 Decimal，tuple digits<=28、tuple exponent>=-18、adjusted exponent<=18；正負與零皆允許。小計及每一步結果沿 lots._decimal(derived=True)：有限、digits<=50、tuple exponent>=-148、adjusted exponent<=99。不得用 quantize 或截斷輸入偷偷放寬。

算術使用與現行 research._CONTEXT 相同的 context：prec=50、ROUND_HALF_EVEN、Emin=-99、Emax=99、capitals=1、clamp=0；陷阱 InvalidOperation／DivisionByZero／Overflow／FloatOperation 啟用，另明示啟用 Underflow。Rounded／Inexact／Subnormal 不自行改為陷阱。不得受呼叫端全域 context、flags 或 traps 污染。

對驗證後目前小計、有效舊 fee 與新 fee 執行兩次獨立 Decimal 運算：

```text
intermediate = current_subtotal - old_effective_fee
validate_derived(intermediate)
next_subtotal = intermediate + new_fee
validate_derived(next_subtotal)
```

每步都在上述 context；第一步失敗即拒絕，不能因第二步理論上回到界限內而接受。捕捉 DecimalException 並映射 invalid_decimal；派生驗證失敗同碼。Underflow 拒絕整筆；符合界限的精確 subnormal 不因 Subnormal flag 單獨拒絕。不使用 float、SQLite SUM／數值 CAST、無限精度補算或先算差額。

current head 取事件當下最新 StoredLotV2，不能取原 fill 的歷史 Lot。active map 無 active→false／false、OPEN→true／false、CLOSE→false／true；與 head flags 不符為 integrity_error。未補費原成交集合計數必須等於 fee_unknown_fill_count；更正不改 completion 集合或 count。

成功後只替換 fee_quality.known_fee_subtotal，coverage 維持 MANAGED、unknown count 原值，revision+1。身份、side、opened／remaining qty、average_entry、realized_pnl、funding_paid、protection 與兩個旗標原樣。order total／fill_seq／done／active 不變。允許 terminal／部分取消後、全平 Lot、active OPEN／CLOSE 期間更正。已接受 CLOSE binding 繼續有效；未接受且引用舊 revision 的新意圖依既有 revision_conflict 拒絕。

**不同有效 fee，但捨入後 subtotal 相同，仍必須建立 correction 與新 revision。** P1 拒絕的是新舊單筆 fee 相同，不是聚合結果相同。現行 S2 `_transition` 會拒絕只有 revision 變動的版本；schema9 必須提供受限的內部事件證據通道，允許此一已驗證 correction：

- 寫入端僅 S3 在同一交易中完成 target／前驅／P1／P2 校驗後能使用；無公開 allow_no_change 參數，不能僅憑 write_id 前綴放行。
- recovery 的 S2 結構檢查遇此候選版本只可延後最終判定；完成 S3 deterministic replay 並逐版核對唯一 correction 證據後才可對外回 storage_ready、查詢或 capture。所有 schema9 S2 公開讀寫也必須經此完整驗證，不得繞過 S3 證明。
- 外部 S2 UNVERIFIED 無變化仍 no_change；無 correction 證據的僅 revision 版本、其他非法狀態轉換及 schema7／8 原 no-change 契約均不放寬。此例外只處理無狀態差異判定，身份與其他 transition 校驗照常。

schema9 recovery 因此分為「S2 結構掃描」與「S3 完整證明」兩個內部階段，但對外仍只有一個成功狀態。Journal 初始化只有在第二階段完成後才可成功返回 handle；`lots.get／get_revision／list_current／recover／create_v2／replace_v2`、所有 S3 API 與 capture 皆不得只執行第一階段後對外返回。

本輪未執行 Decimal 探針。不能宣稱在現行輸入界限下已重現任何極端差異；reducer 邊界測試與實際可達的 Journal 事件軌跡應分開標示，不能把人工構造的大 subtotal 冒充合法歷史。

## 8. 重放、原子性與完整性

同一 SQLite transaction 內保存 canonical 事件／hash／seq、S2 revision／request、head、Bot 水位與 EventReceipt；成功 COMMIT 後才 ACK。任何例外整筆 rollback，事件、前驅占用、revision／commit_seq 都不能半筆留下。儲存或 COMMIT 結果不確定沿 storage_unavailable／失效 handle／重開驗證契約，不換 ID 自動重送。

五表合併，按 seq=1..N 重放；跨表同 seq、缺號、錯版本拒絕，不插回原成交時間。既有 orders／states／active／flags／原 fill／completion 集合之外，維護由事件生成的 effective fee map：

| 事件 | map 更新 |
|---|---|
| 原 KNOWN fill | fee、kind=fill、該事件全域 seq |
| 原 UNKNOWN fill | UNKNOWN、fee／有效來源皆 None |
| fee_completion | 原 UNKNOWN 轉 KNOWN，kind=fee_completion、該 seq |
| fee_correction | 精確前驅及不同 fee 驗證後替換 fee／kind／seq |
| bind／terminal | 不修改 map |

每個事件生成的 Lot 與原子收據，必須逐欄等於 S2 保存版本，包括 flags、fee quality、revision、write_id、commit_seq。跨表每個 Lot revision 只能引用一次。所有 MANAGED 版本與 s10_ 內部版本都反向對應唯一事件；schema9 拒絕混入 s3_／s9_ 內部版本，不假裝為已完成遷移。

全域 seq、Bot context event_seq、fill_seq、Bot commit_seq 是不同序列，不要求數值相同。純外部 UNVERIFIED S2 寫入可占 Bot commit_seq，但不能占 S3 seq；前驅查詢不依賴兩者相等。

recovery 必須拒絕：跨成交／跨 scope 前驅、前驅種類錯誤、引用未來或不存在 seq、同前驅分叉、金額往返後引用舊前驅、新 identity 同值事件、孤立 correction／revision、尾端刪除後殘留版本（含捨入後 subtotal 不變）、hash／SQL 冗餘欄位／flags／fee map 不一致。損毀統一 integrity_error 並使 handle 失效，不自動修補。

不宣稱能辨識整個 DB 及全部證據一致回退的舊副本；沒有新增外部錨點。COMMIT 後 ACK 遺失以原完整 identity 查詢／重送取得原收據，不能再次扣舊加新。

## 9. Capture、S6 與 S7

```python
journal.capture_lot_snapshot_v3(
    *, scope, inst_id, observed_at_ms, valid_until_ms
) -> LocalLotCaptureV3
observe_synthetic_scenario_v3(*, capture, scenario, now_ms)
render_synthetic_scenario_report_v3(*, capture, scenario, now_ms)
```

LocalLotCaptureV3 精確欄位同 LocalLotCaptureV2：source、scope、contract、capture_id、observed_at_ms、valid_until_ms、bot_watermarks、lots、pending、unmanaged_unresolved_lot_ids、capture_version、schema_version；版本固定3／9，lots 仍 tuple[StoredLotV2,...]。其餘型別沿 S9，不增加 correction history 或虛構 last_correction 欄位。

沿同一 pinned read transaction：metadata 首讀→完整 S2／S3 recovery→物化→hash→ROLLBACK。仍限制64 Bot／4096 Lot／4096 pending；包含 closed Lot。correction 與 capture 競爭時只得見完整更正前或後版本，不能混用費用與水位。

hash domain 固定 `catos-local-lot-capture-v3`；header 的 `format` 亦精確固定為 `catos-local-lot-capture-v3`，並含 capture_version=3／schema_version=9。fragment 順序、canonical 數值身份、8-byte big-endian 長度前綴沿 v2。Lot fragment 包含完整 fee_quality／revision／flags；Bot 水位仍納入。時間與 DB path 不進 hash。即使 subtotal 捨入不變，合法 correction 推進 revision／水位，capture_id 仍必須改變；no-change 拒絕及已接受重送不改 capture_id。

schema9 的舊 capture_lot_snapshot／v2 明確拒絕 unsupported_fee_version；schema7／8 的 v3 同樣拒絕。純 S6／S7 舊入口只接受其原型別／版本，新入口只接受 V3／3／9；不能把 V3 轉成 V2 冒用舊 hash domain。

SyntheticScenarioObservationV3 精確欄位同 ObservationV2，observation_version=3；fee_quality 沿 tuple[LotFeeObservation,...]，按 lot_id 排序並精確涵蓋 capture 全部 Lot。source_capture_id 必須綁定這次 V3 capture。S4 沿 observe_exposure_v2 與 LotInventoryV2／ExposureRequestV2，共用現有數量及曝險算術；不複製第三套計算。

S7 新版保留 S9 費用品質及 funding 未知文案，另明示「資料版本：capture v3／schema9；費用為此截點的有效小計」，呈現既有 capture_id 與逐 Lot revision，使使用者可辨別所用版本。不聲稱每個 Lot 都曾更正，不新增歷史 UI、帳戶 net PnL 或交易許可。

MANAGED count>0 仍「費用不完整／已知費用小計，非全部費用」，count=0 仍只代表受管成交費用完整；UNVERIFIED／空集合按 S9 不填零、不宣稱完整。更正不影響 pending_complete、fresh、MATCH、has_unknown、ExposureReport.reasons、qty／notional。S8 CLI 保持 schema7，S9 v2 範例／報告不改為 schema9。

## 10. 具體驗收軌跡

新建合成 schema9；單 long Lot、price=100、base_per_contract=0.01，OPEN3張、CLOSE3張。Worker bind event_seq 自行使用有效序列，下表 seq 指 S3 全域序列。每列後的 revision 如表；bind OPEN 未建立 Lot。

| seq | 事件 | subtotal | unknown count | remaining | revision | OPEN／CLOSE flags |
|---|---|---|---|---|---|---|
| 1 | OPEN bind | — | — | — | — | — |
| 2 | fill T1，1張，KNOWN 0.02 | 0.02 | 0 | 1 | 1 | true／false |
| 3 | fill T2，2張，UNKNOWN | 0.02 | 1 | 3 | 2 | true／false |
| 4 | OPEN FILLED terminal | 0.02 | 1 | 3 | 3 | false／false |
| 5 | CLOSE bind，expected_revision=3 | 0.02 | 1 | 3 | 4 | false／true |
| 6 | T1 correction C1，前驅2，改0.015 | 0.015 | 1 | 3 | 5 | false／true |
| 7 | T2 completion，補0.01 | 0.025 | 0 | 3 | 6 | false／true |
| 8 | T2 correction C2，前驅7，改0 | 0.015 | 0 | 3 | 7 | false／true |
| 9 | T1 correction C3，前驅6，改0.02 | 0.02 | 0 | 3 | 8 | false／true |
| 10 | CLOSE fill T3，3張，KNOWN 0.01 | 0.03 | 0 | 0 | 9 | false／true |
| 11 | CLOSE FILLED terminal | 0.03 | 0 | 0 | 10 | false／false |
| 12 | T3 correction C4，前驅10，改-0.005 | 0.015 | 0 | 0 | 11 | false／false |

在 seq9 後插入以下請求都不能占 seq10：重送 T1/C1 原 payload 回 seq6 原收據；T1/C1 改內容為 write_conflict；新 T1/C5 引用2，即使送0.02亦 fee_predecessor_conflict；新 T1/C6 引用9且送0.020為 no_change。在 seq12 後重送原 T2 UNKNOWN fill／completion 仍回原收據。

全軌跡 average_entry=100、realized_pnl=0、funding=None；correction 不改 protection。CLOSE 在 revision4接受後，後續 fee 版本不使該 binding 失效。重開後有效來源為 T1→seq9、T2→seq8、T3→seq12；報告計數 order=2、fill=3、terminal=2、completion=1、correction=4。此為預期值，尚未執行。

## 11. Sol 驗收矩陣

以下為後續實作驗收要求，不是本輪已通過測試；情境群不等於測試方法數。

| ID | 案例與必要證據 |
|---|---|
| A01 | 型別／token／scope／USDT／整數上下界；float、NaN、Infinity、bool seq、偽造 frozen 拒絕 |
| A02 | canonical 0.02／0.020、正負零等價；超限原始表示先拒絕；未知鍵／漏鍵／錯版拒絕 |
| A03 | 原 KNOWN、completion 後 KNOWN 都可；UNKNOWN→fee_not_known；不存在 target／UNVERIFIED 無接管 |
| B01 | 同 identity 同內容回原收據，後續更正／terminal 後仍可；不同合法內容 write_conflict 優先於失效前驅 |
| B02 | 新 identity 正確前驅同值→no_change，無事件／水位變化、查詢None；拒絕ID不占用 |
| B03 | 同 ID 不同成交可各自接受；同成交不同 ID 引同前驅最多一個成功；不得形成分叉 |
| B04 | 0.02→0.015→0.02 後舊前驅拒絕；跨成交／bind／terminal／未來／UNKNOWN fill 前驅拒絕 |
| B05 | 查詢有效來源四狀態（不存在／UNKNOWN／原KNOWN／completion或correction），查寫競爭仍CAS拒絕 |
| C01 | P2先減再加，與獨立手算／明示兩步 oracle一致，不用被測函式產生期望值；外部 context 無影響 |
| C02 | 正費／零／返佣、抵銷、大小數混合、往返；若探針找到順序差異，固定輸入／每步預期值，標示可達性 |
| C03 | 原始及派生界限、中間步先失敗而最終理論可回界限、Underflow／Overflow／InvalidOperation；全部 rollback |
| C04 | 不同 fee 但 subtotal 捨入相同仍有事件／revision／新有效前驅；S2讀寫／重開均驗唯一correction證據，偽造僅revision拒絕 |
| C05 | 第10節完整軌跡、short／非零價差、partial cancel、active OPEN／CLOSE／全平後，非費用欄位及flags不變 |
| C06 | 其他 UNKNOWN 不因一筆更正變完整；舊expected_revision新意圖拒絕、已接受CLOSE後續fill成功；seq上限無半筆 |
| D01 | 五表seq缺號／重號、錯event版、hash／SQL欄位竄改、scope／來源歸屬錯誤拒絕 |
| D02 | 雙向event↔revision；尾端刪除、殘留版、孤立事件、同subtotal correction證據刪除、分叉及錯前驅拒絕 |
| D03 | 每個原子寫入點故障 rollback，無孤立head／水位／前驅占用；健康caller衝突不使handle失效 |
| D04 | 真實Windows程序COMMIT前終止與COMMIT後ACK前終止，重開原identity重送／查詢不二次計費 |
| D05 | storage／COMMIT不確定與損毀失效handle；不得自動修補、換ID或盲目重送 |
| E01 | 新建／重開9明示；7／8↔9及未知版在DDL／WAL變更前拒絕；非空user_version0拒絕 |
| E02 | schema7／8固定DDL／payload／hash／receipt／replay／capture golden值維持，S9重送補零仍合法 |
| E03 | API／codec／capture錯版互拒；schema9外部S2僅UNVERIFIED、保留ID與no-change門檻；Worker IPC不接線 |
| E04 | 混合外部UNVERIFIED S2版本與S3事件時Bot commit_seq與全域seq分離仍正確，反向版本證據無漏查 |
| F01 | 真實WAL第二connection提交與capture競爭，只見完整前／後；更正改hash、no-change／重送不改 |
| F02 | v3 hash domain／header固定，捨入同subtotal仍改hash；舊hash／偽造fee品質或revision拒絕 |
| F03 | V3 scenario精確綁capture，完整／缺費／UNVERIFIED／空集合／closed Lot呈現；funding仍未知 |
| F04 | 曝險與pending品質不因fee改判；不輸出帳戶net PnL或交易許可，無偽造Lot v1轉接 |
| F05 | 1280／390 px實際viewport讀圖，版本／capture_id／revision／長Decimal／HTML逸出可讀；S8與S9必要視覺回歸 |

持久化與程序中斷使用測試新建臨時 DB／程序，不使用既有 DB。SQL損毀注入僅針對新建 fixture；受控故障stub須明示。數值邊界若現行原始輸入無法到達，分為 reducer／例外防線驗證，不捏造合法Journal軌跡，也不為測試放寬生產界限。

Sol 已獨立審查本文件的 identity 範圍、錯誤順序、P2 中間值、S2 同 subtotal 特例、schema9 與 capture 版本，結論為規格通過。後續只有另獲實作授權，才編寫程式與專屬測試；實作後驗收限更正專屬、受影響 Lot／Journal 及 S8／S9 必要回歸，不執行全量或市場回測。

## 12. 交接與授權

Astra 本輪只新增本規格並同步 assessment、README、WORK_PLAN、current-handoff 入口；其他未提交工作保留。不修改 AGENTS、程式、測試、DDL常數或資料庫，不執行 Git／Python／測試／真實採集，不讀憑證、不連交易所、不提交或push。

文件檢查：五份文件的 Markdown fence 成對且未見行尾空白；本規格四個相對連結目標存在。已人工核對第10節事件數、revision 與小計；這是文件靜態檢查，不代表算術探針、DDL執行或單元測試通過。

Sol 正式規格獨立審查已完成；下一步需另獲使用者實作授權，再由 Astra 實作、Sol 驗收。交接見 [目前接續入口](../docs/current-handoff.md)。本輪 Sol 已唯讀核對 HEAD／工作樹／index 狀態，但未 stage、commit 或 push；S9 歷史測試未重跑。market、yaoI／yaozi、S5–S7 補記與 S9 QA 證據不得清理或混入後續限定提交。
