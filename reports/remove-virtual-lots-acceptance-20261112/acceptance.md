# Virtual Lots 刪除：獨立驗收報告

- 受驗範圍：`git diff e95d37dc..223e02e4`（分支 chore/remove-virtual-lots，HEAD 223e02e4da8163f6e1da634abce5f4452e76e8d9）
- 驗收者：獨立會話（Claude 子代理，未參與開發），唯讀
- 工作樹：C:\Users\user\.t3\worktrees\CatOS\chore-remove-virtual-lo-776e0bd075c74035
- Python：C:\dev\CatOS\.venv\Scripts\python.exe；`catos.__file__` = 工作樹的 `catos\__init__.py`
- 改動前的程式樹用 `git archive e95d37dc | tar -x` 解到暫存目錄。所有驗收腳本都是驗收者自己寫的，沒有使用開發者的 dump／open 腳本，只拿開發者的 JSON 來交叉比對。
- 日期：2026-11-12

## 總結

| # | 檢查 | 結論 |
|---|------|------|
| 1 | 沒有殘留的 lot import 或呼叫 | PASS |
| 2 | 新帳本的 schema 與 user_version 和改動前相同 | PASS |
| 3 | 既有帳本複本開得起來；1 到 6 版的遷移路徑可用 | PASS |
| 4 | 8／9 版帳本被拒絕，且檔案不被改動 | PASS |
| 5 | 後端整套測試通過，數字一致 | PASS |
| 6 | journal.py 沒有改變 lot 以外的行為 | PASS（有非阻斷觀察 O1 到 O3） |
| 7 | AGENTS.md 只改了 P8 與獨立驗收清單 | PASS（有非阻斷觀察 O4、O5） |

**總結：PASS，沒有阻斷缺陷。**

## 1. 殘留 lot 引用

做法：

- 用 `ls` 確認規格列出的刪除項目都不存在：catos/lot_*.py、lots.py、ipc_lots.py、tests/test_lot*.py、test_ipc_lots.py、test_lots.py、tests/lot_*.py、tests/fixtures/lot_*.py、examples/lot_scenario_demo.py、docs/lot-fill-handoff.md。
- `git grep -nIE "lot_journal|lot_fills|lot_accounting|lot_exposure|lot_scenario|lot_schema[89]|lot_snapshot|ipc_lots|catos\.lots|LotStorageError|LotJournal|LotFillJournal|lot_schema_version|capture_lot_snapshot|\.lot_fills\b|\.lots\b|lot_journal_helpers|lot_fill_helpers|lot-fill-handoff" -- . ':!docs/archive' ':!reports'`，再用 `git grep -wiE "lots?|lot_[a-z_]+"` 做更廣的字詞搜尋。

結果：

- 程式碼裡沒有殘留的 import 或呼叫。命中的只有說明文字、刪除紀錄、`--lot-size` 參數（合約下單單位）、保留的 6 張表 DDL、表名清單與 fixture。
- 在 e95d37dc 上反查：非 lot 的正式程式只有 `catos/journal.py` 引用 lot 模組，lot 以外的正式流程不依賴 lot 行為。
- 4 個測試檔（test_execution、test_p5、test_protection、test_risk_journal）只把 helper 的 import 換成 `journal_legacy_helpers`。

## 2. 新帳本 schema 與 user_version

做法：分別用 e95d37dc 和 223e02e4 的程式建立 plain、risk、risk＋execution 三種新帳本，傾印 `sqlite_master`（type、name、tbl_name、rootpage、sql，依 rowid 排序）、`PRAGMA user_version`、journal_mode，以及每張表的所有資料列。

```
plain     user_version 7 7 | sqlite_master(type,name,tbl_name,rootpage,sql) identical: True | rows identical: True | journal_mode wal wal
risk      user_version 7 7 | ... identical: True | rows identical: True
execution user_version 7 7 | ... identical: True | rows identical: True
fixture == my e95d37dc baseline (type,name,tbl_name,sql sorted): True
lot entries in baseline: 26 [lot_bindings, lot_fill_events, lot_fill_orders, lot_fill_terminals, lot_heads, lot_revisions]
```

- 每份帳本 56 筆 sqlite_master 項目，連 rootpage 都相同，比開發者的比對（不含 rootpage）更嚴格。
- 開發者的 `schema-before-e95d37dc.json`、`schema-after.json` 與 `tests/fixtures/journal_schema_v7.json` 都和驗收者自己產生的基準一致。

## 3. 既有帳本與 1 到 6 版的遷移

### 3a. 正式帳本複本

做法：用 shutil 位元組複製 8 個正式帳本（local-sim-control 4 個、local-sim-r4 4 個，含 -wal 和 -shm），每個複製兩份到暫存目錄，複製時沒有對原檔開任何 SQLite 連線。兩份分別用改動前、改動後的程式開 Journal（從 limits_json 還原 risk.Limits，開啟 execution，讀每個 bot 的 snapshot revision 與 risk_state），開檔後比對兩邊的 sqlite_master 與所有表的資料列。驗收前後各算一次原檔 24 個檔案的 sha256。

```
local-sim-control__4874ffc8... uv 7 -> 7 {'opened': True, 'bots': {'sim-control-sma': 8},  'risk_mode': 'RUN', 'execution': True, 'has_lots_attr': False} lot_rows 0 ok
local-sim-r4__347282b9...      uv 7 -> 7 {'opened': True, 'bots': {'r4-sma': 94}, 'risk_mode': 'RUN', 'execution': True, 'has_lots_attr': False} lot_rows 0 ok
（其餘 6 個同樣是 opened True、lot_rows 0、integrity ok）

改動前後對照（8 個都一樣）：pre-open master same: True | post-open master same: True | post-open master == pre-open: True | post-open rows differing tables: [] | open info same (excl lots attr): True
originals sha256 unchanged (24 files)
```

結論：8 個帳本都能開，lot 表全部 0 筆；改動前後的程式開檔後 schema 與資料逐列相同；不需要遷移。

### 3b. 1 到 6 版的遷移

做法：用 e95d37dc 的程式建帳本（register、reconcile、prepare_and_commit 一筆），用驗收者自己的降版邏輯退到 1 到 6 版（各版新增的表從 `_RISK_SCHEMA`、`execution.SCHEMA` 與舊 `lot_journal.TABLES`／`lot_fills.TABLES` 程式化解析，不用開發者的 helper），另做 execution＋risk 版本的 v5、v6。每份複製兩份，分別用改動前、改動後的程式開檔。

```
plain-v1..v6, exec-v5, exec-v6：opened True、checkpoint_seq 1、uv N -> 7（新舊程式皆同）
每份：post schema old==new: True | post rows old==new: True | new post schema == v7 baseline: True
```

結論：1 到 6 版都能升到 7 版，結果和改動前逐列相同，也和 v7 基準一致。

## 4. 拒絕 8／9 版帳本

做法：(a) 用舊程式真正建出的原型帳本（`Journal(..., lot_schema_version=8)`、`=9`）；(b) 正式帳本 local-sim-r4/347282b9 的複本改 user_version=8。用新程式開檔，比對主檔 sha256 並列出開檔後的檔案。

```
proto-v8 (新): JournalError: schema 8 came from the removed Virtual Lots prototype; not supported, no automatic rebuild | uv 8 -> 8 | main file unchanged: True
proto-v9 (新): JournalError: schema 9 came from ... | uv 9 -> 9 | main file unchanged: True
proto-v9 單獨實測：開檔前後 sha256 都是 b9b25eb6...401b，目錄裡只有 proto-v9.sqlite3，沒有留下 -wal/-shm
prod copy uv=8 (新): JournalError: schema 8 came from the removed Virtual Lots prototype ... | main file unchanged: True | files: ['state.sqlite3']
對照 e95d37dc: LotStorageError: schema_version_mismatch（JournalError 的子類別）
```

- 新程式明確拒絕 8／9 版，檔案位元組不變，錯誤訊息說明原因。
- 拒絕發生在 `PRAGMA journal_mode=WAL` 之前，檢查順序與改動前相同（catos/journal.py:313-315）。
- 10 版與 99 版仍由「unsupported journal schema」擋下（tests/test_journal_schema.py 有測）。

## 5. 後端整套測試

```
C:\dev\CatOS\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

Ran 890 tests in 116.278s
OK (skipped=11)
EXIT=0
```

與開發者回報（890、OK、skipped=11）一致。用 unittest loader 計數核對：e95d37dc 總數 1247，14 個 lot 測試模組合計 364 項；223e02e4 總數 890，lot 模組 0 項，新增 test_journal_schema 7 項。1247 − 364 + 7 = 890；非 lot 測試前後都是 883 項。跳過的 11 項來自 3 個類別層級 `@unittest.skip`（tests/test_python_strategy_api.py:13、tests/test_python_strategy_v1.py:61、:127），與改動前相同。

## 6. journal.py 審查（lot 以外的行為）

核對舊的 `lot_journal._scan`／`_recover_in_transaction`、`lot_fills._recover_in_transaction`（e95d37dc）與新程式 catos/journal.py:290-400：

- 整庫完整性檢查：舊程式在 lot 復原裡做的 `PRAGMA foreign_keys == 1` 與 `PRAGMA quick_check == ok` 保留，位置不變（設定 user_version 之後、ProtectionJournal 之前，journal.py:357-361）。用 writable_schema 弄壞索引的帳本，新程式回 `JournalError: journal integrity check failed`，舊程式回 `LotStorageError: integrity_error`，都會擋下。
- 舊 lot 復原另外檢查的 journal_mode=WAL 與 synchronous=2，Journal 本身在 journal.py:328-331 已經檢查。舊的 `foreign_key_check` 只針對 lot 表。
- 錯誤類型：8／9 版與 quick_check 失敗原本是 LotStorageError（JournalError 子類別），現在是 JournalError。repo 裡沒有程式捕捉 LotStorageError 或比對 `integrity_error`／`schema_version_mismatch` 字串；supervisor 捕捉 JournalError（catos/supervisor.py:225、:530），處理方式相同。
- 檢查順序不變：user_version → version 0 非空拒絕 → 不支援版本拒絕 → metadata 比對 → WAL/FULL → 交易內建表與遷移 → 完整性檢查 → protection、execution、risk。
- `_install_retained_tables`（journal.py:244-250）保留舊 install_schema「表已存在就拒絕」的行為，訊息改為 JournalError("unexpected retained table before schema install")，有測試覆蓋。
- 刪掉的 `_lot_read_snapshot`、`capture_lot_snapshot*`、`self.lots`、`self.lot_fills` 在 repo 裡已沒有使用者。
- `catos/demo_ledger_preflight.py:36-42` 的表名清單原樣保留，只加一行註解。

## 7. AGENTS.md 審查

`git diff e95d37dc..223e02e4 -- AGENTS.md` 只有兩處：獨立驗收清單拿掉 `lot_*`（AGENTS.md:69）與 P8 條文（AGENTS.md:118）。INVARIANTS 其他條文、授權紀錄與其他章節沒有改動。

## 阻斷缺陷

無。

## 非阻斷觀察

- **O1：v7 帳本開檔不再檢查 6 張 lot 表。** 改動前 lot 復原會檢查 lot 表存在、DDL 逐字相符、沒有 trigger、foreign_key_check 與資料列一致性；改動後都不做。實測：

  ```
  v7 + DROP TABLE lot_fill_terminals        新：OPENED   舊：LotStorageError: integrity_error
  v7 + ALTER TABLE lot_heads ADD COLUMN     新：OPENED   舊：integrity_error
  v7 + TRIGGER on lot_bindings              新：OPENED   舊：integrity_error
  v7 + 孤兒列 lot_fill_orders（FK off 寫入） 新：OPENED   舊：integrity_error
  ```

  只涵蓋 lot 表，正式帳本沒有這種狀況，不影響 lot 以外的行為。缺表的帳本仍會被 Demo 前檢查擋下（`catos/demo_ledger_preflight.py:205-206` 的 `ledger_schema_incomplete`）。若要維持「schema 7 結構一致才放行」，可在開檔時比對這 6 張表的存在、DDL 與資料列；由使用者決定。
- **O2：註解說得太滿。** catos/journal.py:358 寫「開檔行為不變」，依 O1 已不精確。
- **O3：測試斷言比實際行為寬。** tests/test_journal_schema.py:140 也接受 `sqlite3.DatabaseError`；8／9 版「檔案不變」的測試（同檔 :108-118）只比對 sqlite_master，沒比對位元組（驗收者另外驗過 sha256）。
- **O4：P8 是改寫，不只是刪字。** AGENTS.md:118 除了拿掉 Virtual Lots 文字，也拿掉了「不接交易、額度預留、內部對沖或 P6 改造」與「S3 交接見 docs/lot-fill-handoff.md」，並加上刪除紀錄。被拿掉的句子原本限制 lot 原型的範圍，拿掉合理，但不是單純刪除，請使用者確認。
- **O5：AGENTS.md:3 的說明已不精確。** 該行寫 INVARIANTS「是原文，一字未改」，現在 P8 已改。
- **O6：有些文件還是舊說法。** docs/next-steps.md:71 仍把刪除列在「已同意、排程中」；docs/reconciliation-gate-contract.md:297、docs/reconciliation-policy-decision-pack.md:105、:125 仍寫 user_version 承載 Lot 7/8/9；docs/retail-v1-simplification-assessment-20261020.md:15 仍說 S9／S10 是現有能力。
- **O7：測試副作用。** 整套後端測試會在工作樹 `outputs/`（git 忽略）留下 `workspace-w6/w8-fixture-test-*` 目錄；這是既有測試行為，與本次改動無關，驗收者沒有清理。

## 唯讀聲明

沒有修改、commit、push、checkout 或 stash；`git status --short` 為空。正式帳本只做位元組複製，24 個檔案 sha256 驗收前後相同。暫存檔都在 scratchpad。沒有讀取憑證，沒有連網。

---

## 開發者處理（驗收後，未重新送獨立驗收）

依 AGENTS.md「驗收發現的缺陷由開發者修復，只重驗受影響的範圍」。以下都是非阻斷觀察，改動限於註解、測試與文件，受影響範圍是 `tests/test_journal_schema.py`（`Ran 7 tests`、`OK`）與合併後的後端整套。

| 觀察 | 處理 |
|------|------|
| O1 | 不加檢查。程式已不讀寫這 6 張表，結構不一致不影響任何流程；缺表仍會被 Demo 前檢查擋下。列為交付回報中的待決事項，由使用者決定要不要補。 |
| O2 | 已改：catos/journal.py 註解改為「整庫檢查保留；Lot 表本身的結構與資料不再驗證」。 |
| O3 | 已改：損壞帳本測試只接受 `JournalError("integrity check failed")`（突變測試確認拿掉 quick_check 後該帳本會被開啟）；8／9 版測試改為比對檔案位元組。 |
| O4 | 交付時寫出 P8 原文與新文，由使用者確認。 |
| O5 | 已改：AGENTS.md:3 補上「之後只有 2026-11-12 依使用者決定刪除 Virtual Lots 原型時改寫了 P8」。 |
| O6 | docs/next-steps.md 已改為已完成。另外三份是有日期的決策紀錄，保留當時原文，不改。 |
| O7 | 不處理（既有測試行為，目錄被 git 忽略，隨工作樹一起刪除）。 |
