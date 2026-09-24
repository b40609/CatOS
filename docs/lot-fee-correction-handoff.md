# S10 已知成交費用更正驗收交接

2026-09-21：使用者在 Sol 正式規格通過後明確授權「授權 請開始」，Astra 完成程式與測試編寫後交由 Sol。**Sol 已完成獨立驗收，S10 通過。** 驗收只使用新建 local-sim 臨時／QA DB；未遷移或修改使用者既有 DB，未連網、未讀憑證、未交易、未 stage／commit／push，其他未提交工作保留。

## Sol 獨立驗收結果

- 執行環境：Python 3.14.6、SQLite 3.50.4。
- 本片 8 個程式檔與 2 個新測試／fixture 檔 `py_compile`：OK。
- S10 專屬測試：首輪 33/34，唯一失敗是 C03 測試 stub 把 `correct_fee()` 防禦性 `replace(before)` 觸發的 `average_entry=100.25` 驗證誤認為 P2A 第一個中間值。Sol 僅修正測試注入條件，讓故障精確發生在 `0.01` 中間值，並確認第二步 `0.025` 未執行；生產 reducer 未修改。重跑 **34/34 OK**。
- 必要 Lot／Journal 回歸集合 14 檔：**344/344 OK**。包含 S9 fee completion、Lot domain／IPC／accounting／journal／process、fills／process、exposure、snapshot、scenario／report／demo 及 Journal。
- scoped `git diff --check`：OK；只有既有 Windows LF→CRLF 提示，無 whitespace error。
- F05 視覺 QA：`outputs/s10-qa-20260921-sol/` 已產生 before／corrected-incomplete／corrected-complete 三份 HTML、schema9 QA DB、六張 1280／390 px 實際 Chrome 渲染截圖與 `viewport-metrics.json`。`innerWidth` 精確為 1280／390；因垂直 scrollbar，`clientWidth`／`scrollWidth` 分別同為 1265／375，沒有頁面級水平溢位。V3 版本文字、capture_id、revision 3→4→5、長 Decimal、缺費／完整狀態與 funding 未知文案均可讀。
- 共用 S7 renderer 的 S9 視覺回歸：本輪重新產生的 schema8 `complete.html`／`incomplete.html` 與先前已做 1280／390 實圖驗收的 S9 HTML SHA256 逐 byte 相同；既有實圖亦重新讀圖確認，沒有 V3 文案污染。
- Sol 驗收沒有修改生產程式；唯一程式碼差異是 `tests/test_lot_fee_correction.py` 的 C03 測試 harness 修正。QA 產物保留作本輪證據。

## 基線、政策與授權

- 依 [S10 正式規格](../outputs/catos-s10-fee-correction-spec.md)及 Sol 補強：P1A 拒絕新 identity 同有效 fee；P2A 在50位context先減舊、驗證，再加新、驗證。重送先回原收據，精確前驅防分叉。
- 僅 local-sim、新建 schema9 合成 DB、單訂單單 Lot、USDT。schema7／8 不遷移；不接網路、憑證、交易、風控、P6、funding 或多 Lot 分配。
- 角色維持 Astra 編寫、Sol 驗收與 Git。歷史 HEAD `cc216f7910fc786afe39776daacf1d10737cc66d`、main ahead18、index空為上輪 Sol 回報；本輪 Astra 未執行 Git，未核對現況。S9 344/344 為既有歷史證據。

## 程式入口

| 檔案 | 實作內容 |
|---|---|
| [lot_accounting.py](../catos/lot_accounting.py) | FeeCorrection／EffectiveFee，嚴格身份／費用驗證、兩步 correct_fee reducer、派生中間值及 DecimalException |
| [lot_fills.py](../catos/lot_fills.py) | correction API／收據及有效費用查詢、v3事件、五表seq重放、當下head／flags／unknown count、原子追加與RecoveryReportV3 |
| [lot_schema9.py](../catos/lot_schema9.py) | 新表固定DDL；LotJournalV3／LotFillJournalV3，schema8基表固定引用；s10_內部write_id |
| [lot_journal.py](../catos/lot_journal.py) | schema9正確選LotV2 codec／validator，S2 request format3，僅9增加s10_保留前綴 |
| [journal.py](../catos/journal.py) | 明示9與錯版先拒絕、建構完成前完整recovery、V3 capture入口 |
| [lot_snapshot.py](../catos/lot_snapshot.py) | LocalLotCaptureV3，同讀取交易、header format與domain皆catos-local-lot-capture-v3 |
| [lot_scenario.py](../catos/lot_scenario.py)、[report](../catos/lot_scenario_report.py) | V3入口與型別，沿用S4 V2算術；版本／fee品質呈現，funding仍未知 |

schema7／8 的 DDL、既有 hash 與 write_id 演算法未改；schema9 的 Lot snapshot 仍version2，但S2 request及S3 event為3。這是實作意圖與靜態核對，不是回歸測試通過證明。

## 同 subtotal 更正與兩階段 recovery

不同單筆 fee、但subtotal捨入不變仍推進revision。LotJournalV3只在兩個內部情境延後S2 no-change判定：結構掃描中的MANAGED版本，或S3已完成deterministic evaluation且綁定精確after／flags的當次correction寫入。沒有公開allow_no_change參數；外部UNVERIFIED仍拒絕無變化。

完整入口為S2結構掃描→S3完整重放／event↔revision雙向證明。schema9 `_access` 在所有公開S2／S3操作前執行完整證明；Journal建構與capture也執行完整證明。S3回呼只用私有結構掃描，避免遞迴。結構掃描的內部報告不得被當作外部storage_ready。請 Sol 特別審查不存在查詢、get_revision、create_v2／replace_v2、收據重送及capture是否皆無旁路。

## 專屬驗收命令（已執行）

新增 [test_lot_fee_correction.py](../tests/test_lot_fee_correction.py)，共 34 個測試方法。首輪 33/34 後依上節修正 C03 測試 harness，重跑 34/34 通過。

```powershell
py -3 -B -m unittest discover -s tests -p test_lot_fee_correction.py -v
```

案例包含：型別及canonical、KNOWN／completion／UNKNOWN查詢、重送及ABA前驅、同ID不同trade、no-change不占ID、規格12事件完整軌跡、多空／部分取消／全平／active CLOSE、失效新意圖、損毀及尾端事件刪除、所有公開S2入口完整證明、寫入故障rollback、真實spawn程序COMMIT前後終止、COMMIT成功後ACK例外、錯版無寫入、外部S2與全域seq分離、真實第二WAL connection capture競爭、V3 hash及品質呈現。

驗證證據必須區分：

- 第10節正常軌跡、重放、程序中斷與WAL競爭使用測試建立的真實臨時SQLite檔案。
- P2A差異案例為手算的 **reducer-only邊界**：subtotal=1e33、old=6e-18、new=6e-17；預期先減再加回1e33，先算差額會多1e-16。這是待Sol執行的預期，尚未重現，也沒有宣稱此巨大subtotal可由小型合法成交歷史建立。
- 同subtotal持久化路徑測試明示使用 **合成fill reducer stub** 提供1e50 subtotal，P2A correction本身走真實reducer；只驗revision／proof gate／reopen／刪尾拒絕機制，不是實際可達Journal數值軌跡。
- Underflow／Overflow／InvalidOperation採受控例外注入；第一步驗證失敗採guard stub。這些證明例外映射／流程，不能取代自然數值可達性證明。真實數值上下界由型別案例及既有S9派生界限案例補充。
- F02獨立檢查header/domain和長度前綴組合，但沒有新造schema7／8 golden hash；E02仍須搭配既有回歸與diff核對。

## 必要回歸與編譯

沿 [S9 驗收交接](lot-fee-completion-handoff.md)的Lot必要回歸集合，加S9本身與Journal；逐檔記錄，不跑全量：

```powershell
$s10Patterns = @('test_lot_fee_completion.py','test_lots.py','test_ipc_lots.py','test_lot_accounting.py','test_lot_journal.py','test_lot_journal_process.py','test_lot_fills.py','test_lot_fills_process.py','test_lot_exposure.py','test_lot_snapshot.py','test_lot_scenario.py','test_lot_scenario_report.py','test_lot_scenario_demo.py','test_journal.py')
foreach ($s10Pattern in $s10Patterns) {
    py -3 -B -m unittest discover -s tests -p $s10Pattern -v
    if ($LASTEXITCODE -ne 0) { throw "S10 regression failed: $s10Pattern" }
}
```

Sol另執行本片8個程式檔與2個新測試／fixture檔的py_compile並記錄Python／SQLite版本。零測試匹配不算通過。無法證明的矩陣項明示缺口，不以S9歷史344/344替代本輪回歸。

## 視覺驗收

[lot_fee_correction_visual.py](../tests/lot_fee_correction_visual.py)只在明示呼叫時建立新目錄，拒絕覆寫；產生新schema9 DB與before、corrected-incomplete、corrected-complete三份HTML。Sol 本輪已以 `outputs/s10-qa-20260921-sol/` 執行並完成實際 viewport／截圖驗收。

```powershell
py -3 -B -c "import sys; sys.path.insert(0, 'tests'); from lot_fee_correction_visual import build; build('outputs/s10-qa-NEW')"
```

將NEW換成尚不存在的本輪目錄。以真正1280／390 CSS px各讀取三份HTML，保存6張截圖及viewport／scrollWidth量測；檢查版本、capture_id、Lot revision、長Decimal、完整／缺費與funding未知文案。S8／S9必要視覺回歸依實際受影響共用renderer決定，不能只靠HTML字串assert宣稱視覺通過。

## 限定範圍與下一步

程式8檔：lot_accounting、lot_fills、lot_journal、journal、lot_snapshot、lot_scenario、lot_scenario_report，新增lot_schema9。新增測試／視覺fixture2檔。文件為本handoff、current-handoff、README／WORK_PLAN的S10段落、assessment／spec現況。

Sol接手先核對實際HEAD／index／工作樹，依既有分工完成獨立驗收與必要修正，記錄結果；如處理Git，逐hunk分離S10，不使用git add .，不push。其他market、yaoI／yaozi、S5–S7補記、S9 QA及AGENTS交接流程既有修改保留。上輪Git metadata權限警告未診斷，不自行清理或修復。

入口見 [current-handoff](current-handoff.md)。建議換Sol新對話接手驗收；不擴充S11或funding。
