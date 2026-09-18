# S3 開發交接：合成逐筆成交與 Lot 帳務

最新驗收（2026-09-17，依使用者提供的 Sol 報告）：S3 53/53、必要回歸190/190，合計243/243 OK；Windows4/4、0 skip，未額外跑全量套件。Commit `604e983fdaef3bfaeade8648e67679a678149c17`，未 push。下方待驗證及首次阻斷敘述保留為歷史；本次僅更新文件，未獨立重跑驗證。

狀態：程式與測試已編寫，待 Sol 靜態審查、實際測試與 Git 工作。Astra 本輪未執行測試、編譯、Git、資料庫 migration、憑證讀取或外部請求。

2026-09-17 修正交接：使用者回報首次驗收純帳務 11/11 OK、儲存 35 errors、程序 4 errors，未 commit。根因為 `_key()` 向限定頂層 object 的 S2 `_json()` 傳入 list；靜態檢查另發現 `_write_id()` 同類問題。本次只將兩處輸入改成具名 object，不修改 S2／IPC helper 或 Schema。新增兩個不依賴 DB setup 的身份回歸及一個綁定→首次成交→重送→重啟回歸。修正後尚未執行驗證，請 Sol 從三個 S3 模組重新驗收，再執行必要回歸；前次錯誤阻斷的流程不能視為已驗證。

S2 `690d8549dd4d078d5e62a12acf536ba0f768bdcb`／447 項通過來自使用者驗收回報，不能沿用為 S3 結果。規格見 [S3 設計](../outputs/catos-s3-fill-accounting-spec.md)。

## 交付內容

- `catos/lot_accounting.py`：SyntheticFill、精確數量加減、多空逐筆平均成本與價差損益；費用獨立累計，funding 保持未知。
- `catos/lot_fills.py`：三張 STRICT 表，訂單綁定／成交／終態、數值等價重送、事件收據、序號查詢、完整歷史重算。
- `catos/lot_journal.py`：保留公開接口的交易邊界；內部寫入可加入 S3 既有交易；拒絕受管 Lot 的外部快照寫入。
- `catos/journal.py`：schema7，保留 schema1–6 升級；先 S2 校驗，再 S3 重算，之後才執行既有 v1 恢復。
- 新增 `test_lot_accounting.py`、`test_lot_fills.py`、`test_lot_fills_process.py`、共用 fixtures；調整 S2／Risk schema 版本斷言及空表降版夾具。
- 靜態清點 S3 測試方法為 11 個純帳務、38 個身份／儲存／恢復、4 個 Windows 程序案例，共 53 個；此為編寫數，不是通過數。
- AGENTS／README／WORK_PLAN／規格同步執行範圍與待驗證狀態。

## 實作決策與限制

1. 金融欄以 TEXT 保存，JSON 同樣使用 Decimal 字串；比較／加總只在 Python Decimal。數量以有界 300 位暫存作精確加減，再驗證 S1 50 位派生限制；成本除法與損益採既有 50 位 ROUND_HALF_EVEN。無 float。
2. `order_key` 是 scope/source/inst/order 完整身份的 SHA256；原身份保留於有界 request_json，恢復重算驗證。成交 PK 為 `(order_key,trade_id)`，不含 bot/write_id。同鍵不同原始內容拒絕。
3. 三表共用不可變 seq／request hash／S2 receipt 欄位；跨表事件序號恢復時檢查連續性。CLOSE binding 與 terminal 都保存其旗標版本關聯；零成交 OPEN 沒有 Lot 版本。
4. 內部 S2 write_id 使用 `s3_` 前綴，公開 S2 禁止新寫入該前綴；重放可據此前綴找出刪除歸屬事件後留下的版本。若舊 schema6 自訂資料曾使用此保留前綴，升級會明確拒絕，不自動改名；本專案測試資料之外的 DB 不在本片遷移授權內。
5. 每次 S3 操作完整校驗與重放歷史，再計算新事件，優先可審查與一致性；成本隨事件歷史線性增加，連續寫入總成本可能平方成長。目前只用合成小資料，不宣稱生產吞吐量。未加快取或第二 writer。
6. `get_order` 與 `list_fills` 回不可變事件收據；最新 Lot 內容沿用 Journal.lots 查詢。無 Worker／API 對外接線。
7. 完整性檢查不是防惡意竄改或備份版本回退的外部證明。整個 DB 被替換為一致舊副本，或無 Lot 的尾端事件連同所有證據被刪除，沒有外部錨點可證明遺失；本片不增加額外服務或遠端稽核。
8. 同一 Lot 只一個未決訂單；OPEN 分批成交完成或取消後才能 CLOSE。缺費用／其他幣別／已提交成交更正拒絕；累計回報不作差分。資金費不分攤，沒有完整淨損益或帳戶風控主張。
9. 儲存失敗／COMMIT 不確定沿用 S2 handle 失效規則；重開後以原成交身份查明，不換 ID 重送。現行 ownership／UNKNOWN／risk latch／P6 規則不改。

正式 DDL 位於 `lot_fills.SCHEMA`；表欄位與原提案相比以雜湊 order_key 表示複合身份，並明確加入全域合成事件序號與版本收據，不增加交易授權能力。

## Sol 驗證清單

先審查純帳務公式、S2 內部交易入口、跨表事件／Lot 版本雙向關聯與遷移；再使用已授權 interpreter 對臨時資料執行：

```text
<python> -B -m unittest discover -s tests -p "test_lot_accounting.py" -v
<python> -B -m unittest discover -s tests -p "test_lot_fills.py" -v
<python> -B -m unittest discover -s tests -p "test_lot_fills_process.py" -v
```

必要回歸：`test_lots.py`、`test_ipc_lots.py`、`test_ipc.py`、`test_lot_journal.py`、`test_lot_journal_process.py`、`test_journal.py`、`test_supervisor.py`、`test_risk_journal.py`、`test_execution.py`、`test_p5.py`、`test_protection.py`。若 Sol 依既有授權全量驗證，記錄實際結果，不用新增方法數推定通過總數。

重點：

- 平均成本手算例／多空 PnL、費用正負號、50位與指數邊界、外部 Decimal context。
- 同一成交數值等價重送、COMMIT 後收據遺失、終態後舊收據、缺號補齊。
- 三表 DDL 在實際 SQLite 可建立、FK 與 CHECK 生效；schema6／舊版夾具升級和失敗 rollback。
- 刪除成交／終態、篡改冗餘欄位、額外內部快照都應拒絕恢復。
- Windows 4 個程序測試方法實際執行，其中 C04 分別測終態 COMMIT 前與後；skip 不算平台行為已驗證。
- 既有 S2 公開操作與所有 v1 基線不退化。不要為測試通過而放寬金融或完整性檢查。

## 下一片評估

S3 驗收回報到達後主動確認缺陷與契約缺口，再規劃 S4「純資料 Gross／淨曝險對照」。目前不開始該實作；其在途／UNKNOWN、價格快照、風控權益輸入必須先定義，不能把 S3 合成終態當作交易所對帳證據。
