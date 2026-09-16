# S2 開發交接：Lot 狀態帳本與重啟重放

狀態：使用者已核准設計；程式及測試已編寫，**待 Sol 獨立審查與執行驗證**。本輪未執行測試、編譯、Git、帳戶存取或任何資料庫 migration。

S1 的 commit `720c632`、409 項測試全綠來自使用者回報，不是本輪查核或 S2 通過數。設計依據：[S2 規格](../outputs/catos-s2-lot-journal-spec.md)。

## 已交付程式

- `catos/lot_journal.py`：三張 STRICT 表、同 connection 的 LotJournal、frozen 回傳物件、Decimal 儲存與數值指紋、binding／create／replace／get／get_revision／list_current／recover。
- `catos/journal.py`：schema 6；保留 1–5 升級；在同次初始化交易建立或核對 S2，再進入既有 v1 重啟流程。
- `tests/test_lot_journal.py`：34 個 S01–S34 方法，包含子案例。
- `tests/test_lot_journal_process.py`、`tests/fixtures/lot_journal_process.py`：4 個 C01–C04 程序死亡方法；使用既有 Windows AccountLock，其他平台會明示 skip，不算已驗證 Windows 故障行為。
- `tests/lot_journal_helpers.py`：合成快照及測試專用空表移除器，用於建構真正舊 schema 夾具。
- `test_risk_journal.py`、`test_execution.py`、`test_p5.py`、`test_protection.py`：調整 schema 1／2／3／4 升級夾具，保留原風控／執行斷言。
- AGENTS、架構文件、README、WORK_PLAN：同步已核准 S2 範圍及待驗證狀態。

S1 domain／IPC 原始碼、Worker、Supervisor、Execution、風控及 P6 業務邏輯未修改。Journal 接入僅涉及 schema 與啟動完整性檢查，不接 Lot 交易派送。

## 關鍵行為與限制

1. `Journal.lots` 沿用 `Journal.connection`／`_transaction()`；不另開 connection 或 writer。公開 S2 操作拒絕巢狀交易。查詢也在單一交易內完成一致讀取。
2. 完整版本紀錄、head 與 Bot 提交序號同次 COMMIT；收據在 COMMIT 成功返回後才交付。
3. 同 write_id 及相同數值內容回原收據；舊收據可以在 head 已推進後重放。不同內容拒絕；不透過新 ID 自動重試。
4. 金融欄都是 TEXT，funding NULL 保留未知；快照指數表示不展開超出派生精度。指紋用 Decimal 係數／指數的數值身份，不改 S1 canonical_intent。
5. 新版本須通過 expected_revision、身份、合約及狀態轉移檢查；不自行計算或證實成交／損益／費用。
6. 恢復檢查固定 DDL、外鍵、SQLite quick_check、連續 commit_seq／Lot revision、內容指紋與最新 head。任何不一致明確拒絕，沒有自動重建或覆寫歷史。
7. SQLite I/O／COMMIT 結果不明時，不再使用該 LotJournal；需關閉並以同 DB 重啟，再用同一 write_id 確認。測試含「先真的 commit 再拋錯」，不能一律推定 rollback。
8. storage_ready 只是本機狀態紀錄一致，不解除 v1 latch／RECONCILING，也不代表帳戶對帳、風控批准或交易授權。

依核准設計，schema 6 要求 SQLite 3.37+；格式不可直接交給舊版程式開啟。S2 損毀會拒絕同 Journal 啟動。現行 Journal 初始化本來就會調整 v1 對帳／UNKNOWN／P6 狀態，S2 不取消這些行為。

## Sol 建議驗證順序

先以已授權的 Python 絕對路徑檢查 runtime／SQLite 版本，再使用臨時資料庫執行以下明確模組。這些命令是交接建議，**本輪沒有執行**：

```text
<python> -B -m unittest discover -s tests -p "test_lot_journal.py" -v
<python> -B -m unittest discover -s tests -p "test_lot_journal_process.py" -v
```

接著驗證 S1／IPC 與 Journal 直接依賴：

```text
test_lots.py
test_ipc_lots.py
test_ipc.py
test_journal.py
test_supervisor.py
test_risk_journal.py
test_execution.py
test_p5.py
test_protection.py
```

每個模組使用相同 discover pattern 方式。上述範圍以這次變更為依據；全量質檢／Commit 由 Sol 依使用者授權執行。不要把 0 tests、非 Windows skip 或未執行模組記作通過。

特別檢查：

- 三表循環外鍵在 CREATE 同交易能提交，半成品 COMMIT 必須拒絕。
- SQLite 保存的 DDL 與固定 schema 比對可正常通過；真實 schema 5／1／2／3／4 夾具能正確升級。
- C01–C04 真正由子程序在 SQL／COMMIT 邊界退出，父程序用同 DB 恢復；不是只 mock 回傳結果。
- S24 的 COMMIT 已成功後例外，重開後能取得原收據；S17 舊版本重送不倒退 head。
- Decimal 邊界、低精度外部 context、NULL／0 與返佣符號保持正確。
- S33／S34 的 v1 隔離及既有遷移測試，不得為了通過而放寬金融或完整性斷言。

驗證報告請記錄實際 interpreter／SQLite 版本、模組、run／failure／error／skip 與修補內容。38 是新增測試方法數，不是已驗收通過數。

## 完成界線

本輪開發交付到此，不自動啟動成交分配、Gross、Worker IPC v2 接線、P6 改造或 Demo／Live。不得用使用者既有交易資料庫測 migration；本片不提供降版、清庫、帳戶接管或重新採集授權。
