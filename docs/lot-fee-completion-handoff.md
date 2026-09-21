# S9 成交費用補齊開發交接

2026-09-21：**Sol 本輪已完成 S9 獨立功能、資料完整性、必要回歸與視覺驗收**。開始驗收時 `HEAD` 已是 `b783460`（`feat(lots): add S9 fee completion`），因此本輪不改寫既有 commit，只補上重新執行後的驗收證據。既有 DB 未遷移、未修改；所有 schema8 驗證均使用本輪新建合成 DB。

1280／390 px 已以 Chrome DevTools Protocol 強制實際 CSS viewport 後完成完整／缺費四張像素截圖。量測結果在 1280 px 時 `innerWidth`、`clientWidth`、`scrollWidth`、`body.scrollWidth` 全為 1280；390 px 時四者全為 390。長 Decimal、費用品質、缺費筆數與 funding 未知文案均可讀，未見整頁水平溢位或右側裁切。直接使用 Chrome `--window-size=390` 會被瀏覽器下限提升為 500 px，因此該次探針未列入 390 px 驗收證據。

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
- 既有 `b783460` 已包含一項 schema7 相容修正：舊 `apply_fill()` 對 raw cumulative dict 維持既有 `TypeError`，schema7 傳入真正 `SyntheticFillV2` 仍明確拒絕 `unsupported_fee_version`。本輪獨立審查未發現新的程式或測試缺陷，`test_lot_fills.py` 38/38 與 S9 32/32 均重新通過。
- 修改／新增 Python 檔及 S9 測試 helper `py_compile` 通過。實際環境 Python 3.14.6、SQLite 3.50.4。
- 視覺樣本以本輪新建 schema8 合成 DB 產生 `complete.html`／`incomplete.html`；F04／F05 測試通過。1280／390 px 均以實際 CSS viewport 渲染並讀圖驗收，四組 `scrollWidth` 與 viewport 相等；長 Decimal、完整／缺費狀態、缺費筆數與 funding 未知文案可讀，無整頁水平溢位或裁切。

## 視覺驗收

可選樣本產生器只在明示呼叫時新建目錄，拒絕覆寫；DB 與 HTML 皆在該目錄。範例路徑必須尚不存在：

```powershell
py -3 -B -c "import sys; sys.path.insert(0, 'tests'); from lot_fee_completion_visual import build; build('reports/s9-qa-20260920')"
```

以 1280 px／390 px 渲染 incomplete.html 與 complete.html；確認品質區、長 Decimal、缺費筆數可讀，無整頁水平溢位／裁切，費用降級不改 pending／MATCH；funding 未知文字必須保留。UNVERIFIED／空集合／逸出另有專屬測試。本輪已完成四張實際像素截圖與 viewport／scrollWidth 量測，結果見上節。

## 限定提交範圍

程式：`catos/lots.py`、`lot_accounting.py`、`lot_journal.py`、`lot_fills.py`、`journal.py`、`lot_snapshot.py`、`lot_exposure.py`、`lot_scenario.py`、`lot_scenario_report.py`，新增 `catos/lot_schema8.py`、`catos/lot_snapshot_codec.py`。

測試：新增 `tests/test_lot_fee_completion.py`、`tests/lot_fee_completion_visual.py`。

文件：本交接、README 的 S9 段落、WORK_PLAN 的本輪 S9 新段落。README／WORK_PLAN 既有 S7 補記須逐 hunk 分離。正式規格未改。所有 DB、HTML、快取與其他功能不得納入提交。

功能、資料完整性與視覺驗收後執行 `git diff --check`、限定 staged review 與 staged check、Git commit。交付前保留實際案例數與失敗／錯誤／跳過數。S9 不因此擴張到下一個帳務政策切片。
