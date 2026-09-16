# S2：SQLite Lot 狀態帳本與重啟重放設計

狀態：**使用者已審查通過；程式與測試已編寫，待 Sol 驗證**。設計階段只新增本文件；後續依核准範圍完成開發，未執行測試、編譯、Git 或既有資料庫升級。最新狀態見 [S2 開發交接](../docs/lot-journal-handoff.md)。

基線由使用者回報：S1 已由 Sol 驗收並提交 `720c632`，409 項測試通過。本輪閱讀目前工作區，未重新核對 Git commit 或重跑驗證。S1 的全平派生精度與指數快照序列化修補已見於原始碼。

## 1. 切片定位與交付邊界

S2 完成的是 **Lot 狀態的持久化、條件更新、重送去重與重啟完整性校驗**。以受信父側提供的合成 Lot 快照為輸入，不在本片計算成交分配、平均成本、已實現損益、資金費或保證金。

具體要處理的失敗情境：

| 失敗情境 | 最小處理 | 驗證成本 |
|---|---|---|
| 更新快照中途程序死亡 | 版本紀錄、最新指標、提交序號在同一 SQLite 交易 | SQL 故障注入及 COMMIT 前後子程序退出 |
| COMMIT 成功但收據未收到，父側重送 | 固定 write_id、規範內容比對、回傳原版本收據 | 重啟及最新版本已推進後重送 |
| 兩次更新都根據同一舊版本 | 交易內重讀、expected_revision 比較與條件 UPDATE | 同版本競爭及回滾測試 |
| 重啟讀到缺頁、遺失版本或錯誤身份 | SQLite 檢查、順序重放、版本鏈與最新指標比對 | 合成損毀案例，拒絕啟動 |
| 虛擬多 Lot 誤改 v1 淨倉與 ownership | 新表不連結舊 Bot／委託外鍵，沒有執行呼叫 | v1 資料不變與既有遷移回歸 |

**本片不做：** Worker IPC v2 接線、策略重算、接受待成交 OPEN 意圖的 outbox、成交事件處理器、交易所 fill 去重、Gross 風控、額度預留、多 Bot 執行、TP／SL 觸發、P6 改造、Demo／Live、備份還原工具或 UI。

狀態儲存收據不代表意圖已獲風控批准、交易已送出、成交已核實或帳戶對帳成功。保留 `ValidatedLotIntent` 與執行授權的區別；它不能直接作為落盤批准憑據。

### 1.1 與現行規則的關係

設計起草時 `AGENTS.md:41` 只允許 S1，仍禁止把 Lot 接入持久化。使用者先要求 S2 設計，之後明確回覆「審查通過」，現已據此實作並同步 P8 的隔離儲存範圍；沒有執行既有資料庫遷移。

實作交付已同步 P8 與架構文件第 13／15 節：允許同一 Journal 內隔離的 Lot 狀態儲存與重放；v1 執行仍為單合約單 Bot、cross＋net_mode，Lot 不接交易、風控預留、分配器或內部對沖。日損 10%／20%、風險鎖存與 P6 均維持。

## 2. 單一資料庫、單一 writer

沿用現有 `Journal.connection`、writer thread、帳戶鎖、資料庫路徑綁定與 `_transaction()`。後者使用 `BEGIN IMMEDIATE`，提交由 `_commit()` 完成。

- 新增內部 `LotJournal(journal)`，由 `Journal.lots` 持有；不接受 DB 路徑，不自行 connect／commit／close，不新增 writer 或服務。
- 所有公開 S2 寫入函式各自使用一次 `Journal._transaction()`；不可在已有交易內呼叫。內部 migration／recovery helper 不另開巢狀交易。
- SQLite 維持 `journal_mode=WAL`、`synchronous=FULL`、`foreign_keys=ON`；初始化確認設定生效。
- 本片僅接受現行 Journal 的 `local-sim` 範圍。`LotScope.account_ref` 必須等於 `Journal.account_id`，environment 必須等於 DB metadata 與 `local-sim`；S1 能表示 demo／live，不等於 S2 可寫那些環境。
- `lot_bindings` 的 Bot 是獨立儲存身份，不呼叫 v1 `Journal.register()`、不取得或釋放 v1 合約所有權。多個 Lot Bot 可綁定同合約，不代表能同時執行交易。
- 不以第二份 SQLite、外部 JSON 日誌或記憶體字典作耐久性依據。

## 3. Schema 6：三張新增表

建議將 `SCHEMA_VERSION` 從 5 升為 6。所有新增表使用 `STRICT`；實作時先檢查 SQLite runtime 支援 STRICT（SQLite 3.37.0 以上），不支援即明確失敗，不安裝替代儲存引擎或靜默放寬表型別。

以下 DDL 是實作目標，**本輪不執行**。Bot／帳戶／合約等 token、Decimal 值與 JSON 內容仍須由 Python 嚴格驗證；STRICT 表無法阻止 SQLite 將可轉換的數字綁定值轉成 TEXT，因此不能代替應用層「拒絕 float」規則。

### 3.1 Bot 與合約綁定

```sql
CREATE TABLE lot_bindings (
    bot_id          TEXT PRIMARY KEY NOT NULL,
    account_ref     TEXT NOT NULL,
    environment     TEXT NOT NULL CHECK(environment = 'local-sim'),
    inst_id         TEXT NOT NULL,
    contract_json   TEXT NOT NULL
                    CHECK(length(CAST(contract_json AS BLOB)) BETWEEN 1 AND 65536),
    last_commit_seq INTEGER NOT NULL DEFAULT 0
                    CHECK(last_commit_seq BETWEEN 0 AND 9223372036854775807)
) STRICT;
```

`contract_json` 精確保存 ContractSpec 五欄，四個規格數值為 Decimal 字串。註冊時驗證型別、USDT-SWAP 標識、正數、min_size／lot_size 關係。相同 Bot 的重複註冊僅允許語義相同的 scope／contract，不原地換帳戶、合約或規格。無刪除或重新使用 Bot ID 的 API。

`last_commit_seq` 是 **S2 儲存提交序號**，每 Bot 從 1 連續遞增；不是 Worker event_seq，不參與 S1 intent_key 的生成。

### 3.2 Lot 身份與最新版本指標

```sql
CREATE TABLE lot_heads (
    lot_id           TEXT PRIMARY KEY NOT NULL
                     CHECK(length(lot_id)=64 AND lot_id NOT GLOB '*[^0-9a-f]*'),
    bot_id           TEXT NOT NULL REFERENCES lot_bindings(bot_id),
    open_event_seq   INTEGER NOT NULL
                     CHECK(open_event_seq BETWEEN 1 AND 9223372036854775807),
    open_intent_key  TEXT NOT NULL UNIQUE
                     CHECK(length(open_intent_key)=64
                           AND open_intent_key NOT GLOB '*[^0-9a-f]*'),
    side             TEXT NOT NULL CHECK(side IN ('long','short')),
    current_revision INTEGER NOT NULL
                     CHECK(current_revision BETWEEN 1 AND 9223372036854775807),
    UNIQUE(bot_id, open_event_seq),
    UNIQUE(lot_id, bot_id),
    FOREIGN KEY(lot_id, current_revision)
        REFERENCES lot_revisions(lot_id, revision)
        DEFERRABLE INITIALLY DEFERRED
) STRICT;
```

除了 `current_revision`，其他欄位建立後不可變。CREATE 時先插入 head，再插入 revision=1；延遲外鍵於同次 COMMIT 檢查，不存在可提交的「有 head、無快照」狀態。

scope／inst_id 從 binding 得到；建立及每次讀寫都核對 S1 快照身份。利用保存的 `open_event_seq`、scope、bot_id、contract 重建 S1 `IntentContext(..., warmup=False)`，驗證 `open_intent_key` 與 `lot_id`，不只確認雜湊字串長度。

這是已存在 Lot 的來源關聯，**不保存未成交意圖，也不是完整 Worker 事件序號配置器**。未產生 Lot 的事件仍需後續 Worker／outbox 切片保存；不得拿 `max(open_event_seq)+1` 推算 Worker 下一事件。首次成交到達順序可能不同於決策順序，所以不要求新的 open_event_seq 大於其他 Lot 的開倉序號，只要求同 Bot 不重用。

### 3.3 追加式完整版本快照

```sql
CREATE TABLE lot_revisions (
    lot_id             TEXT NOT NULL,
    bot_id             TEXT NOT NULL,
    revision           INTEGER NOT NULL
                       CHECK(revision BETWEEN 1 AND 9223372036854775807),
    expected_revision  INTEGER NOT NULL
                       CHECK(expected_revision BETWEEN 0 AND 9223372036854775806),
    write_id           TEXT NOT NULL CHECK(length(write_id) BETWEEN 1 AND 64),
    commit_seq         INTEGER NOT NULL
                       CHECK(commit_seq BETWEEN 1 AND 9223372036854775807),
    operation          TEXT NOT NULL CHECK(operation IN ('CREATE','REPLACE')),
    opened_qty         TEXT NOT NULL CHECK(typeof(opened_qty)='text'),
    remaining_qty      TEXT NOT NULL CHECK(typeof(remaining_qty)='text'),
    average_entry      TEXT NOT NULL CHECK(typeof(average_entry)='text'),
    realized_pnl       TEXT NOT NULL CHECK(typeof(realized_pnl)='text'),
    fees_paid          TEXT NOT NULL CHECK(typeof(fees_paid)='text'),
    funding_paid       TEXT CHECK(funding_paid IS NULL OR typeof(funding_paid)='text'),
    trigger_price_type TEXT NOT NULL CHECK(trigger_price_type='mark'),
    take_profit        TEXT CHECK(take_profit IS NULL OR typeof(take_profit)='text'),
    stop_loss          TEXT CHECK(stop_loss IS NULL OR typeof(stop_loss)='text'),
    opening_unresolved INTEGER NOT NULL CHECK(opening_unresolved IN (0,1)),
    closing_unresolved INTEGER NOT NULL CHECK(closing_unresolved IN (0,1)),
    request_json       TEXT NOT NULL
                       CHECK(length(CAST(request_json AS BLOB)) BETWEEN 1 AND 65536),
    request_hash       TEXT NOT NULL
                       CHECK(length(request_hash)=64
                             AND request_hash NOT GLOB '*[^0-9a-f]*'),
    PRIMARY KEY(lot_id, revision),
    UNIQUE(bot_id, write_id),
    UNIQUE(bot_id, commit_seq),
    FOREIGN KEY(lot_id, bot_id) REFERENCES lot_heads(lot_id, bot_id),
    CHECK(revision = expected_revision + 1),
    CHECK((operation='CREATE' AND expected_revision=0)
       OR (operation='REPLACE' AND expected_revision>=1))
) STRICT;
```

`lot_heads` 與 `lot_revisions` 的循環外鍵只用於原子建立及 head 指向存在的版本；兩張表與索引須在同次 schema 交易完成後才寫資料。沒有 CASCADE DELETE。

應用 API 只 INSERT 新版本，不提供 UPDATE／DELETE 歷史、INSERT OR REPLACE、清理關閉 Lot 或裁剪歷史的入口。原始 SQL 不屬於支援 API；本片不建防惡意本機使用者的資料庫存取控制。

最新快照直接由 head JOIN 對應版本得到，不另外複製一份金額投影。歷史版本服務稽核、重送與完整性重放，並非第二套帳戶／資金帳本。

### 3.4 Decimal 與內容規範

- 所有金融值都先驗證為有限 Decimal，再以字串綁定。禁止 SQLite REAL／NUMERIC 金融欄、CAST 成 REAL、SQL SUM／AVG 金額及 float 中介。
- 快照的數量、均價、損益、費用與 funding 沿用 S1 派生範圍；TP／SL 與合約規格沿用 S1 輸入範圍。呼叫 `lots.validate_lot` 驗證數量步長、保護與合約。
- 使用 S1 快照 wire 的指數表示保存派生值；`1e50`／`1e99` 不展開為超過 50 位的定點係數。不得先 normalize 或去尾零再驗證輸入範圍。
- funding 的 SQL NULL 代表未知，與文字 `"0"` 不同；負費用／返佣及負資金費保留原符號。
- SQLite 金額 CHECK 只保證儲存型別；正負、剩餘量上下界與 tick／lot 對齊由 Python 檢查。SQL 不按字串比較金融大小。
- `type(x) is int` 驗證 seq／revision，拒絕 bool；布林旗標只接受真正 bool，再轉成 0／1 儲存。達到 MAX_INTEGER 後拒絕推進，不溢位或重設。

**寫入指紋另行定義，不更改 S1 canonical_intent：**

1. 先完整驗證請求及所有 Decimal。
2. 對請求中的 Decimal 做純字串／整數的數值身份表示 `[sign, coefficient, exponent]`：由 `as_tuple()` 得到係數，移除係數尾零並等量增加 exponent；零統一 `[0,"0",0]`。不呼叫會受 context 捨入的 `normalize()`。
3. request_json 的精確欄位為 `format_version=1, scope, bot_id, inst_id, contract, write_id, operation, open_event_seq, expected_revision, after, opening_unresolved, closing_unresolved`。CREATE 的 open_event_seq 為請求整數、expected_revision 為 0；REPLACE 的 open_event_seq 固定為 null，來源序號沿用不可變 head，不要求呼叫端再次提供。after 為完整 S1 Lot wire 的結構，但 Decimal 字串位置改為上述身份陣列；contract 四個數值同樣處理。null 仍為 null。
4. JSON 使用 `ensure_ascii=True, sort_keys=True, separators=(",", ":")`，UTF-8，無 BOM／換行；沿用既有純 JSON 有界檢查。request_hash 為其 SHA256 小寫十六進位。
5. `1`／`1.0`／`1e0` 是同一內容；null／0 不同。重送同時比較 request_json 與 request_hash，不只信任雜湊。
6. `commit_seq` 由資料庫分配，不放進請求身份；重送回傳原 commit_seq。重放時從版本欄位與不可變 binding／head 重新建構 request_json 校驗。

## 4. Journal 介面與原子操作

以下是待實作 API。資料回傳型別為 frozen dataclass，不回傳可變 sqlite Row 或裸 connection。

```python
@dataclass(frozen=True, slots=True)
class StoredLot:
    lot: Lot
    opening_unresolved: bool
    closing_unresolved: bool
    commit_seq: int

@dataclass(frozen=True, slots=True)
class LotWriteReceipt:
    bot_id: str
    lot_id: str
    write_id: str
    revision: int
    commit_seq: int
    request_hash: str
    replayed: bool = False

class LotJournal:
    def register_binding(self, *, scope: LotScope, bot_id: str,
                         contract: ContractSpec) -> None: ...

    def create(self, *, scope: LotScope, bot_id: str, write_id: str,
               open_event_seq: int, after: Lot,
               opening_unresolved: bool,
               closing_unresolved: bool) -> LotWriteReceipt: ...

    def replace(self, *, scope: LotScope, bot_id: str, write_id: str,
                expected_revision: int, after: Lot,
                opening_unresolved: bool,
                closing_unresolved: bool) -> LotWriteReceipt: ...

    def get(self, *, scope: LotScope, bot_id: str,
            lot_id: str) -> StoredLot | None: ...

    def get_revision(self, *, scope: LotScope, bot_id: str,
                     lot_id: str, revision: int) -> StoredLot | None: ...

    def list_current(self, *, scope: LotScope, bot_id: str,
                     after_lot_id: str | None = None,
                     limit: int = 100) -> tuple[StoredLot, ...]: ...

    def recover(self) -> LotRecoveryReport: ...
```

### 4.1 註冊、查詢與呼叫責任

`register_binding` 在交易內查重與新增；同內容重試成功，不消耗 commit_seq。不同內容報 `binding_conflict`。S2 不創建任何 v1 bots／ownership 紀錄。

除整庫 recover 外，資料接口須帶父側 scope／bot_id，驗證與 DB binding 一致。查詢其他 Bot 的 Lot 回傳 None，不洩漏其快照；其他 scope 不符報通用 `scope_mismatch`。create／replace 的 after 不可自行改寫這些身份。查詢、收據重送與恢復共用嚴格的儲存列解碼及內容指紋檢查，不把已通過一次啟動檢查當成之後可以忽略壞資料。

`list_current` 按 lot_id 排序，以不透明但必須合法的 lot_id 作 keyset cursor；limit 為 1–1000 的真正 int。預設包含已關閉 Lot，不因 remaining_qty=0 隱藏責任。單次查詢使用同一 SQLite 讀取快照；跨頁不承諾快照一致，後續展示若需要才另設讀交易介面。

`write_id` 是父側提供、同 Bot 範圍唯一的 `[A-Za-z0-9_-]{1,64}`，代表一次**狀態儲存請求**。首次發送前呼叫端須能保留完整請求與該 ID，重試不得換新 ID。它不是 lot_id、S1 intent_key、fill_id 或 Worker generation。S2 不新增未提交請求佇列；COMMIT 前死亡且呼叫端也遺失請求時，不能由 S2 猜回未持久化工作。

### 4.2 CREATE／REPLACE 的共同交易順序

1. 在交易外只做不可變的形狀／數值驗證。所有依賴當前 DB 的判斷必須在交易內確認。
2. `BEGIN IMMEDIATE`；讀取並核對 binding，取得其 contract 建構有界規範請求。在 `(bot_id, write_id)` 查已提交版本。
3. 若已存在且規範內容相同，回傳原收據並標記 replayed；即使 head 已推進或原 expected_revision 現在過期，仍重放舊收據，不覆寫 head。不同內容報 `write_conflict`，保留原資料，不把它當新寫入。
4. 新請求才讀當前 head／snapshot，執行第 4.3 節限制。取得 binding.last_commit_seq+1，檢查整數上界。
5. CREATE 插入 head 與 revision=1；REPLACE INSERT 新 revision，再以 `WHERE lot_id=? AND bot_id=? AND current_revision=?` 更新 head，rowcount 必須為 1。
6. 同次更新 binding.last_commit_seq；版本行、head、序號有任一失敗，整筆 rollback。
7. `_commit()` 成功返回後才向呼叫端交付收據。收據由已提交版本欄位構成，不另存一份可分歧的 receipt JSON。

重送查重不會重新校驗「目前 revision 是否等於舊請求 expected_revision」，但仍檢查儲存收據本身及身份完整性。禁止先因舊 revision 拒絕，再要求呼叫端改 ID 重送。

### 4.3 狀態更新限制

- CREATE：head 不存在；after.revision=1；expected_revision 隱含為 0。after 必須是已有成交數量的有效 S1 Lot，opened_qty>0；未成交的空殼 Lot 不可存。資料是合成父側提供，不因儲存成功就宣稱有真實 fill。
- REPLACE：head 存在且屬於指定 scope／Bot；expected_revision 必須等於 current_revision；after.revision 必須恰為 expected_revision+1。
- side、scope、Bot、inst_id、open_intent_key、lot_id、open_event_seq 均不可變。after 不能換到另一個 Lot。
- opened_qty 不可倒退；已關閉 Lot 的 remaining_qty 仍須為 0，opened_qty 與 average_entry 不再改動，不能復活舊 Lot。關閉後可追加費用／funding 等狀態版本；不刪除歷史。
- 每版都執行 S1 快照與合約驗證；未新增開倉數量時，remaining_qty 不可增加，average_entry 不改。S2 不重算新增數量的均價、平倉損益或費用歸屬，不聲稱這些值與外部成交相符。
- 旗標是該版快照的一部分；只有 unresolved 旗標改變，也消耗一個 revision，使舊 view 明確失效。重啟不自動把 true 改成 false，也不把 false 當成交易所已對帳。
- 除 revision 外完全無語義變化的新 write_id 報 `no_change`，不追加空版本。相同 write_id 的重送則回原收據，不報 no_change。
- closed snapshot 仍可保留 closing_unresolved=true；空倉不等於責任已終結。S2 不根據旗標釋放 v1 ownership 或預留額度。
- 旗標與開／平倉量並不提供遠端 UNKNOWN 處理器；它們由受信父側合成輸入。不同 write_id 包含同一 fill 時，S2 無法識別交易所重複成交，必須留待成交歸屬切片處理。

### 4.4 拒絕與 I/O 不確定性

新增 `LotStorageError(JournalError)`，帶非敏感 code：`scope_mismatch`、`binding_conflict`、`lot_not_found`、`lot_exists`、`identity_conflict`、`revision_conflict`、`invalid_transition`、`no_change`、`write_conflict`、`sequence_exhausted`、`integrity_error`、`storage_unavailable`。S1 LotError／ProtocolError 在公開儲存入口轉成可辨認的錯誤，不吞掉例外後回成功。

領域／版本／重放衝突完整 rollback，原快照與序號不變。SQLite 寫入／COMMIT 例外不得回收據或假稱「一定沒寫入」；該 LotJournal 標為不可再使用，呼叫端須關閉並以同 DB 重啟。重啟成功後，持同一 write_id／內容查重，才能判斷是否已提交。

不因 SQLite busy 自動產生新 ID，也不自動重送交易。沿用既有 bounded SQLite timeout；S2 不新增無限重試。現行 Supervisor 沒有 S2 派送入口，之後接入時仍須沿用其 JournalError 失效處理；本片不新增另一套全域風控鎖存。

## 5. 重啟與重放

### 5.1 啟動順序

在既有帳戶鎖與 DB 路徑綁定成立後，由 Journal 初始化完成版本／帳戶檢查及 WAL／FULL 設定。在既有初始化交易內，先完成新增表 migration，再執行 S2 的內部唯讀校驗；成功後才進行既有 v1 的重啟 RECONCILING／UNKNOWN／P6 行為並 commit，最後公開 Journal。

`LotJournal.recover()` 用於明示重新檢查，使用相同 writer 的一致交易；不與寫入並行。初始化內部 helper 不呼叫它的開交易包裝，避免巢狀 BEGIN。

恢復流程：

1. 檢查 schema 6 的必要欄位、型別、索引、外鍵與 STRICT 屬性；版本不支持、缺表或缺約束皆拒絕，不用 IF NOT EXISTS 補洞。
2. 執行 SQLite `quick_check` 及新表的 `foreign_key_check`，拒絕底層結構與引用錯誤。這些檢查不能代替後面的 Decimal／業務完整性檢查。
3. 校驗所有 binding 的 scope、合約 JSON 與非負提交序號；嚴格 JSON 解碼，拒絕重複鍵、Float、過大內容或未知欄位。
4. 按 `(bot_id, commit_seq)` 串流讀版本，每個 Bot 從 1 到 last_commit_seq 連續，不能缺號或超出標記；無版本的 binding 必須 last_commit_seq=0。
5. 按 Lot 檢查第一次為 CREATE／revision=1／expected=0，之後必須 REPLACE 且版本逐一增加。重新驗證 scope、來源 ID、Decimal、合約規格、旗標及第 4.3 節可檢查的轉移條件。
6. 每版重建規範請求，與 request_json／request_hash 比較；同 write_id 不得出現多筆。從完整版本快照產生當時狀態，不呼叫策略、交易、fill handler 或帳務計算。
7. 比對最後重放結果與所有 head：每個 head 必有完整歷史，current_revision 必須指向最大版本；無孤兒歷史、缺失 head 或多出版本。關閉 Lot 一樣檢查。
8. 全部成功才回 `LotRecoveryReport(storage_ready=True, binding_count, lot_count, revision_count, unresolved_lot_count)`。計數以 INTEGER 計算，不包含金額彙總。空的新表可成功恢復，但不初始化任何虛構部位。

恢復只重建／核對記憶體狀態，不重寫最新金額、不追加新 revision、不重發訂單、不遞增 commit_seq。正常 SQLite 原子交易應只有完整提交或無提交；head 與歷史不一致視為損毀，**不自動挑一邊覆蓋另一邊**。修復／匯入工具另行規劃。

### 5.2 程序死亡矩陣

| 死亡時點 | 重啟結果 |
|---|---|
| BEGIN 前 | 無變更；必須由呼叫端提供原請求才可再次寫入 |
| 插入 revision 後、head／序號更新前 | 未提交交易由 SQLite 恢復，三表仍是舊狀態 |
| 三表 SQL 已完成、COMMIT 前 | 舊狀態完整保留，不返回已提交收據 |
| COMMIT 後、回收據前 | 新狀態完整存在；同 write_id 重送回原收據 |
| 已有更多版本後重送較舊請求 | 回較舊版本收據，head 保留最新版本 |
| COMMIT 回傳錯誤，結果不明 | 當前實例不繼續使用；同 DB 重啟校驗及查重，不能直接判作未提交 |

`storage_ready` 僅表示本機紀錄一致，不可設定 v1 `LOCAL_READY`、解除 latch、改 reconciled／trade_authorized，或聲稱已完成交易所對帳。

### 5.3 完整性保證的限制

版本序號與內容雜湊可偵測缺失、錯配及未同步修改；不是防竄改簽章。若有人同步修改所有相關列與雜湊，或回復一份內部一致的舊 DB，沒有外部錨點就無法證明歷史未倒退。S2 不新增外部帳本、簽章或備份服務。

同樣，不能用程序退出測試宣稱真實斷電／磁碟韌體的耐久性已驗證。

## 6. 遷移與 v1 平行隔離

### 6.1 遷移規則

- 保留 schema 1–5 的既有升級順序；版本 whitelist 明確接受 1、2、3、4、5、6，不因常數改成 6 而意外漏掉 5。
- schema<6 時，確認三個 `lot_*` 表名尚不存在，再在既有初始化交易內建立三表及索引；最後設定 user_version=6。同時存在舊 version 與 S2 表視為不一致，拒絕而非猜測。
- 新空 DB 仍先建立既有 v1 表，再建立 S2 空表。既有 v1 Bot、ownership、部位、委託或 fill **完全不轉成 Lot**。
- schema=6 缺表或 schema不符即拒絕，不當成首次安裝；未知較高版本也拒絕。
- 建表或既有初始化任一步失敗，DDL／user_version 與同次資料寫入一併 rollback。
- 本片不自動備份／改名／覆蓋 DB。程式實作測試只使用臨時資料庫；使用者既有 DB 的實際升級不由本規劃授權。
- schema 6 是格式升級：舊版 schema-5 程式不能再開啟它。不能把「增量加表」宣稱為二進位可降版；正式升級前的備份／回退操作另由使用者及驗證模型安排。

### 6.2 隔離保證與真實影響

- S2 API 的 SQL 寫入集合只限三張 lot_* 表；migration 另更新 user_version。
- 不建立指向 v1 bots、ownership、inputs、intents、execution_orders、execution_fills、risk_orders、reservations、outbox 或 protection 的外鍵／trigger。
- 不呼叫 v1 register／release／commit_result，不把 Lot 表拿來推算帳戶淨倉、可用預算、風控權益或日損。
- v1 新增合約 Bot、持倉、固定 tag、風控與 P6 行為保留；S2 多 Bot 資料不放寬 v1 唯一 ownership。
- Journal 原本重啟就會變更 health／對帳資格／部分 UNKNOWN 與 P6 狀態；測試須與相同 v1 基線重啟行為比較，不能要求重啟前後所有 v1 列位元組相同。
- 新增的成本是 schema 升級、啟動完整性掃描與版本歷史儲存。第一次採全歷史串流檢查，不建 checkpoint／壓縮框架；成本隨版本數線性增加，實测有瓶頸後才另提縮減。
- **S2 資料損毀會讓同一 Journal 啟動失敗**，不繞過損毀繼續使用同 DB。這是本設計明示的失敗邊界；正常 S2 空表或有效資料不影響 v1 決策。若需要損毀時 v1 仍可獨立啟動，須另定降級方案，本片不隱式加入。

## 7. 預計新增測試清單

以下是驗收情境，不是已建立或已通過的測試數。全部使用合成 Lot、臨時 SQLite／帳戶鎖目錄；無 OKX、真實憑證、既有交易 DB 或市場回測。

### 7.1 `tests/test_lot_journal.py`：儲存、遷移與重放

| 編號 | 預期驗證 |
|---|---|
| S01 | 空庫初始化 schema6；WAL／FULL／FK、三表 STRICT、必要索引外鍵生效 |
| S02 | 真正 schema5 升級成功，新增表為空；v1 非重啟控制資料與既有 latch 保留 |
| S03 | migration 中途例外不留下部分表或 version6；後續可用原庫重新升級 |
| S04 | 高版本、schema6 缺表、舊版帶 S2 表、錯誤帳戶／環境拒絕且不重建 |
| S05 | 綁定重送冪等；同 Bot 換 scope／合約／規格拒絕；多 Bot 同合約可儲存 |
| S06 | CREATE 同交易保存身份、revision1、write_id 與 commit_seq1；無 v1 Bot／ownership 副作用 |
| S07 | 首次快照零開倉量、錯開倉 seq／派生 ID、非有限值及浮點值拒絕 |
| S08 | 金融欄 typeof 為 text；負費用、funding NULL／0／負值精確往返 |
| S09 | 均價／金額 1e50、1e99、1e-148 與 50 位係數往返；超界編解碼拒絕，不經 float |
| S10 | 合法派生剩餘量、非 tick 均價、合法碎量保留；無效數量步長／保護價格拒絕 |
| S11 | REPLACE 正好增加一版；head、history、commit_seq 同步且舊版可讀 |
| S12 | 舊 expected_revision、跳版、bool／越界序號拒絕，三表不變 |
| S13 | 同期兩個請求共用舊 revision，只能一個成功；失敗請求不消耗序號 |
| S14 | 變更 Bot、合約、方向或來源 ID 拒絕；跨 Bot 查詢不洩漏快照 |
| S15 | 同 write_id 同內容回原收據；數字 1／1.0／1e0 不製造假衝突 |
| S16 | 同 write_id 不同內容、目標 Lot、expected_revision 或旗標報衝突，原紀錄不覆蓋 |
| S17 | head 已進到後續版時重送舊請求，回舊收據且不倒退 head |
| S18 | 新 write_id 的無變化快照拒絕；只改旗標需增加一版；同 ID 重送不再加版 |
| S19 | 關閉快照保留歷史；不允許重開或減少 opened_qty；關閉後費用／funding 更新可保存 |
| S20 | 數量未增加時不得提高 remaining_qty 或改均價；有效部分開／平快照按契約保存 |
| S21 | unresolved=true 經重啟保留；空倉加未決責任不釋放舊 ownership／reservation |
| S22 | get／get_revision／keyset 列表排序、邊界、已關閉 Lot 與 scope 過濾正確 |
| S23 | 每個 INSERT、head UPDATE、序號 UPDATE 注入例外，完整 rollback；不回成功收據 |
| S24 | SQLite busy／COMMIT 例外無自動換 ID 或繼續 S2 寫入；重啟用原 ID 確認 |
| S25 | MAX_INTEGER 邊界不溢位／歸零，無部分紀錄 |
| S26 | 外層 Decimal precision=2／不同 rounding 不改變儲存、指紋及返回值，不污染 context |
| S27 | 多 Lot 交錯版本重放結果與最新查詢一致；開倉事件 seq 到達順序可不同 |
| S28 | 刪掉中間版本、尾版或改 commit watermark 都會拒絕恢復 |
| S29 | head 缺失／指向舊版／多出版本、孤兒引用、身份重綁會拒絕恢復 |
| S30 | 修改有效 Decimal 數值但不更新指紋，或破壞 request_json／hash，拒絕恢復 |
| S31 | 無效 Decimal、flags、revision、contract JSON 與重複 JSON 鍵，不以預設值代替 |
| S32 | 有效空庫／多 Bot／已關閉 Lot 可恢復；恢復不增加版本／序號、不觸發任何交易 |
| S33 | S2 create／replace 前後比較 v1 表，無額外寫入；v1 仍拒絕第二個 owner |
| S34 | 在包含 latch、UNKNOWN、reservation、P6 責任的合成 DB 上重啟，v1 既有恢復語義不變 |

測試損毀案例可使用測試專用 raw SQLite 操作，必要時在該測試 connection 關閉 FK 來製造故障；正常 Journal 仍須開啟 FK。測試不得把正式防線改成略過錯誤以取得通過。

### 7.2 `tests/test_lot_journal_process.py`：真實子程序退出

測試 fixture 位於 `tests/fixtures/lot_journal_process.py`，沿用現有 AccountLock 與臨時鎖目錄；故障 hook 僅存在測試程式，不暴露正式 crash API。

| 編號 | 預期驗證 |
|---|---|
| C01 | CREATE 寫入部分 SQL 後 os._exit：重啟三表沒有半成品 |
| C02 | REPLACE 三表更新後、COMMIT 前退出：完整回到舊版本 |
| C03 | COMMIT 後、回收據前退出：重啟取得新版本，原 ID 重送只回收據 |
| C04 | 多 Lot／未決責任的版本重啟重放；程序死亡釋放 OS lock，不刪除 Lot 或 v1 ownership |

### 7.3 既有回歸範圍

直接相依：`test_lots.py`、`test_ipc_lots.py`、`test_ipc.py`、`test_journal.py`、`test_supervisor.py`。

Journal 初始化／schema migration 受影響的額外範圍：`test_risk_journal.py`、`test_execution.py`、`test_p5.py`、`test_protection.py`。開發時另外確認到 schema 1 的 Risk Journal 夾具；四者均以當前 DB 刪部分表再降低 user_version 模擬舊版，新增 S2 後須同時移除空的 S2 表，不放寬正式 migration 檢查。循環 FK 表的測試清理在專用 fixture connection 依明確步驟處理，不提供正式降版入口。

不把 409 項歷史全綠當成本輪驗收；Sol 依實際修改與上列情境執行定向回歸。若另獲全量質檢授權，再執行全套；不預先宣稱通過數。

## 8. 實作檔案與順序

| 檔案 | 預計變更 |
|---|---|
| `catos/lot_journal.py`（新增） | Schema 常數、儲存資料型別、指紋、binding、原子快照 API、重放驗證 |
| `catos/journal.py` | schema6 白名單／migration、同 connection 的 LotJournal、初始化完整性檢查；不改交易決策 |
| `tests/test_lot_journal.py`（新增） | S01–S34 |
| `tests/test_lot_journal_process.py`（新增） | C01–C04 |
| `tests/fixtures/lot_journal_process.py`（新增） | 純合成故障子程序 |
| `tests/lot_journal_helpers.py`（新增） | 共用合成快照及測試專用空表移除器 |
| 既有 Risk Journal／P5／P6／Execution 遷移測試 | 僅調整舊 schema fixture 及新版本號，保持原行為斷言 |
| `AGENTS.md`、架構文件、README、WORK_PLAN | 確認後同步 S2 範圍與開發／驗收狀態，不把提案寫成已完成 |

實作順序：型別／DDL與嚴格 codec → migration／binding → create／replace／查詢及冪等收據 → 重放完整性檢查 → 故障與隔離測試 → Sol 獨立驗證。S1 domain／IPC 原則上只復用，不順手改它們的 wire 版本或數值範圍。

### 完成定義

三表與同 writer API 完成；Decimal／身份／版本／重送規則有專屬測試；COMMIT 前後退出能得到原子結果；重放對損毀明確拒絕；v1 回歸保留；文件如實區分本機儲存一致與交易所對帳。完成後交付，不自動展開成交分配或交易接線。

## 9. 已確認的設計選擇

使用者已核准以下邊界：**同 DB schema6、三張隔離表、完整版本快照＋最新指標、父側固定 write_id、啟動全歷史校驗、損毀時拒絕同 Journal 啟動、只接合成 local-sim 快照。**

核准範圍是程式與測試開發，不授權真實帳戶存取、既有 DB 實際升級或交易。net_mode／long_short_mode、P6 聚合保護、日損門檻遷移等仍在執行切片前另行決策。
