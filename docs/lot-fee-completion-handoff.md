# S9 成交費用補齊開發交接

2026-09-21：**Sol 已完成 S9 功能、資料完整性與必要回歸驗收；待限定提交**。Astra 原交付的程式與測試已實際執行，並修正一項 schema7 舊 API 錯誤語義相容問題。既有 DB 未遷移、未修改；所有 schema8 驗證均使用新建合成 DB。

瀏覽器介面因本機安全政策拒絕直接開啟 `file://` 測試報告，因此 1280／390 px 的實際像素截圖矩陣**未能執行，不能宣稱已通過**。已完成 F04／F05 報告語義測試與生成 HTML 的 viewport、responsive media rule、table `overflow-x`、品質／funding 文案靜態核對；此限制保留到可使用允許本機報告渲染的驗收環境再補證據。

## 基線與授權

- 使用者回報 S8 `b069082`、assessment `bb29389`、正式規格 `120dc58` 已限定提交。
- 契約：[S9 正式規格](../outputs/catos-s9-fee-completion-spec.md)。只允許 local-sim、新建 schema8 合成 DB 與 unknown→known 補費。
- 既有 DB 不遷移、不修改；不讀憑證、不連交易所、不接風控、交易授權、P6、funding 或多 Lot 分配。
- Astra 編寫；Sol 驗證及 Git。market、yaoI／yaozi 與既有補記不納入。

## 實作入口

- `lots.FeeQuality`／`LotV2`、`lot_journal.StoredLotV2`；沒有把 subtotal 冒充完整 `fees_paid` 的 property。
- `lot_accounting.SyntheticFillV2`／`FeeCompletion`；共用既有 OPEN／CLOSE 部位算術，費用累加使用 research Decimal context。
- [snapshot v2 codec](../catos/lot_snapshot_codec.py) 與 Worker IPC 分離；[固定 schema8 DDL](../catos/lot_schema8.py) 保留原表名、writer 與交易邊界。
- `Journal(..., lot_schema_version=8)`：在修改 journal_mode、DDL 或 recovery 前拒絕既有其他版本；`PRAGMA user_version` 是唯一持久化 schema 版本。
- S2 `create_v2`／`replace_v2` 僅接受 UNVERIFIED；MANAGED 由同交易 S3 寫入。
- `lot_fills.apply_fill_v2`、`complete_fee`、`get_fee_completion`；四表合併 seq、事件與 Lot 版本雙向關聯。重送先找原鍵，completion 不增加 fill_count。
- completion 從目前 head 更新品質與 revision，檢查並保留當下 active flags；原訂單 terminal 與 Lot 全平均不阻止補費。
- `capture_lot_snapshot_v2`、`observe_exposure_v2`、`observe_synthetic_scenario_v2`、`render_synthetic_scenario_report_v2`；品質納入 capture 身份，費用原因獨立於 ExposureReport.reasons。
- S8 CLI 未新增選項，仍使用 schema7。

## Sol 執行順序

先讀取工作樹差異與正式規格，確認限定範圍，再執行以下專屬測試。所有測試 DB 使用 TemporaryDirectory；損毀、版本偽造及程序終止只針對測試新建檔案。

```powershell
py -3 -B -m unittest discover -s tests -p test_lot_fee_completion.py -v
```

專屬測試包含 A01–A05 型別／算術、B01–B04 去重／身份、C01–C05 狀態、D01–D06 重放／故障／重啟、E02–E04 版本／API、F01–F05 capture／報告案例。D05 使用 multiprocessing spawn＋Pipe 通知抵達 COMMIT 邊界，父程序 terminate；D04 為受控 connection proxy，F01 為第二個真實 WAL connection 在 metadata 首讀後提交補費。E01 舊版固定契約與 F06 S8／S7 回歸仍需配合下列既有測試及原始碼差異核對，不宣稱單一測試檔已證明整份矩陣。

必要回歸限受影響的 Lot 模組；逐檔執行，保留各自結果，不執行全量：

```powershell
py -3 -B -m unittest discover -s tests -p test_lots.py -v
py -3 -B -m unittest discover -s tests -p test_ipc_lots.py -v
py -3 -B -m unittest discover -s tests -p test_lot_accounting.py -v
py -3 -B -m unittest discover -s tests -p test_lot_journal.py -v
py -3 -B -m unittest discover -s tests -p test_lot_journal_process.py -v
py -3 -B -m unittest discover -s tests -p test_lot_fills.py -v
py -3 -B -m unittest discover -s tests -p test_lot_fills_process.py -v
py -3 -B -m unittest discover -s tests -p test_lot_exposure.py -v
py -3 -B -m unittest discover -s tests -p test_lot_snapshot.py -v
py -3 -B -m unittest discover -s tests -p test_lot_scenario.py -v
py -3 -B -m unittest discover -s tests -p test_lot_scenario_report.py -v
py -3 -B -m unittest discover -s tests -p test_lot_scenario_demo.py -v
```

另因修改 Journal 初始化，請核对預設 schema7 初始化、既有錯版拒絕與必要 Journal 測試；只有測試新建 fixture 可使用原有歷史版本測試工具。編譯所有本片修改／新增 Python 檔，記錄實際 Python／SQLite 版本。不得把零測試匹配當通過；若檔名與工作樹不同，先確認實際測試名稱。

## Sol 實際驗收結果（2026-09-21）

- S9 專屬：32/32 通過，0 failure／error／skip；涵蓋真實 Windows process kill、WAL capture 競爭、補零版本、terminal／closed Lot 後補費、active CLOSE 旗標、損毀拒絕與報告品質。
- 必要回歸：`lots` 26、`ipc_lots` 23、`lot_accounting` 11、`lot_journal` 34、`lot_journal_process` 4、`lot_fills` 38、`lot_fills_process` 4、`lot_exposure` 42、`lot_snapshot` 39、`lot_scenario` 34、`lot_scenario_report` 21、`lot_scenario_demo` 22、`journal` 14，共 312/312 通過。加上 S9 專屬，最終驗收集合共 344/344 通過。
- 發現並修正一項 schema7 相容缺陷：舊 `apply_fill()` 對 raw cumulative dict 原應維持既有 `TypeError`，S9 初稿的版本 gate 提前改成 `unsupported_fee_version`。修正後 `test_lot_fills.py` 38/38 與 S9 32/32 重新通過；schema7 傳入真正 `SyntheticFillV2` 仍明確拒絕 `unsupported_fee_version`。
- 修改／新增 Python 檔及 S9 測試 helper `py_compile` 通過。實際環境 Python 3.14.6、SQLite 3.50.4。
- 視覺樣本成功以全新 schema8 合成 DB 產生 `complete.html`／`incomplete.html`；F04／F05 測試通過，HTML 具 viewport、600 px media rule、table `overflow-x:auto`、費用品質與 funding 未知文案。因瀏覽器安全政策封鎖 `file://`，未執行 1280／390 px 實際截圖，不把靜態核對寫成像素驗收。

## 視覺驗收

可選樣本產生器只在明示呼叫時新建目錄，拒絕覆寫；DB 與 HTML 皆在該目錄。範例路徑必須尚不存在：

```powershell
py -3 -B -c "import sys; sys.path.insert(0, 'tests'); from lot_fee_completion_visual import build; build('reports/s9-qa-20260920')"
```

以 1280 px／390 px 渲染 incomplete.html 與 complete.html；確認品質區、長 Decimal、缺費筆數可讀，無整頁水平溢位／裁切，費用降級不改 pending／MATCH；funding 未知文字必須保留。UNVERIFIED／空集合／逸出另有專屬測試。實際視覺證據與結果由 Sol 補記。

## 限定提交範圍

程式：`catos/lots.py`、`lot_accounting.py`、`lot_journal.py`、`lot_fills.py`、`journal.py`、`lot_snapshot.py`、`lot_exposure.py`、`lot_scenario.py`、`lot_scenario_report.py`，新增 `catos/lot_schema8.py`、`catos/lot_snapshot_codec.py`。

測試：新增 `tests/test_lot_fee_completion.py`、`tests/lot_fee_completion_visual.py`。

文件：本交接、README 的 S9 段落、WORK_PLAN 的本輪 S9 新段落。README／WORK_PLAN 既有 S7 補記須逐 hunk 分離。正式規格未改。所有 DB、HTML、快取與其他功能不得納入提交。

功能與資料完整性驗收後執行 `git diff --check`、限定 staged review 與 staged check、Git commit。交付前保留實際案例數與失敗／錯誤／跳過數；視覺像素矩陣的環境限制不得被改寫為已通過。S9 不因此擴張到下一個帳務政策切片。
