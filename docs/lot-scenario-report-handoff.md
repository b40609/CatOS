# S7 開發交接：本機合成情境報告

狀態：2026-09-19，依 [S7 正式規格](../outputs/catos-s7-scenario-report-spec.md)完成 renderer 與專屬測試，並由 Sol 完成獨立驗收。規格文件已提交 `299884f`（`docs(lots): define S7 scenario report contract`）。

Astra 開發階段只做結構化補丁與靜態閱讀，未執行 Python、單元測試、編譯、視覺驗收、Git、DB 或外部請求；下方保留其開發交接內容。驗收結果以本節記錄為準。

## 正式驗收結果（2026-09-19）

- `test_lot_scenario_report.py`：21/21 通過。
- `test_lot_scenario.py`：34/34 通過。
- 合計 55/55，0 failure／error／skip；未執行全量測試。
- Python 3.14.6、SQLite 3.50.4；`lot_scenario_report.py` 與 `test_lot_scenario_report.py` 均通過 `py_compile`。
- F01 由驗收端建立完整與降級兩份合法合成樣本，分別以 1280 px 與 390 px 本機 Chrome headless 渲染。四組均無整頁水平溢位、無裁切儲存格；桌面與窄視窗來源說明可見，狀態不只靠顏色表達。完整樣本的長 Decimal `100.123456789012345678901234` 保留且在窄視窗完整換行；降級樣本的 `不可用`、`未提供`、品質旗標及五項原因同頁可讀。
- 視覺樣本與截圖僅存於本機 `reports/visual-qa/` 供驗收，不納入程式提交。
- S4／S5／S6、Schema7、Risk、P6、execution／protection 與交易路徑未修改；market、yaoI／yaozi、S5／S6 既有未提交文件更新均排除於 S7 Git 範圍。

## 變更

- `catos/lot_scenario_report.py`：公開 keyword-only `render_synthetic_scenario_report(capture, scenario, now_ms) -> str`，沿用既有型別；恰一次 S6 呼叫成功後才呈現，不接受任意 report 或 Journal。
- `tests/test_lot_scenario_report.py`：21 個測試方法，包含子案例；以 HTMLParser 核對欄位值、單位、旗標與文字，不做全頁 golden snapshot。
- README／WORK_PLAN 更新開發狀態，本文件提供驗收交接。

未修改 S4／S5／S6、Schema7、Risk、P6、execution／protection、交易路徑或正式規格。既有 S5 驗收紀錄、S6 handoff 修改、market 與 yaoI／yaozi 工作均不在本輪修改範圍，也不得一併加入 S7 提交。

## 呈現契約

完整顯示來源、身份、合約、時間、數量、估值、分類桶、情境上界、品質與 16 種原因碼。report 的 scope／contract 展開，reasons 獨立區塊，其餘欄位各自有固定 data-field 表格列；身份與數值不截斷。

Decimal 只格式化，非零固定小數保留尾零，零／負零統一為 0；結果 None 為「不可用」，缺席 mark／metadata 為「未提供」。過期但仍有數值時原樣呈現，保留所有旗標與原因。MATCH、physical_verified、HELD／EXCHANGE 零值及 has_unknown 均附合成語義說明，沒有交易裁決。

所有動態文字在 HTML 邊界逸出；未知原因／狀態保留原碼，原因順序沿用 S4。內嵌 CSS、繁體中文、無 JavaScript 或外部資源。S6／S4 及非預期錯誤原樣向外傳遞；renderer 無檔案／DB／網路／時鐘／環境讀取或日誌輸出。

## 覆蓋與限制

| 規格群 | 編寫覆蓋 |
|---|---|
| A01–A04 | dataclass 欄位解析對照、身份／時間／單位、三種比較狀態、真實 S6／S4 各一次、同輸入輸出及 Decimal context 不變 |
| B01–B06 | mark／physical 缺席、不完整 physical、unmanaged、各來源過期／未來、時間端點、有效空集合 |
| C01、C04 | 多空 Gross／負 Net／負差額／實體絕對估值、分類桶與限制文字 |
| C02–C03、E04 | 同一真實臨時 Journal：首次成交前→部分成交→全成交未 terminal→terminal→CLOSE 未成交；逐步核對 S6 與 HTML |
| D01 | 私有 formatter：極小值、長小數、負值、尾零及負零，低精度 context |
| D02–D03 | 明示受控 S6 stub：16 原因碼中文、反向原因順序、未知碼／狀態及 HTML 注入字串；不修改 S6 輸入契約 |
| D04 | 文件語言／charset／viewport、無外部資源、換行與捲動 CSS；不能取代視覺驗收 |
| E01–E03 | 真實 S6 拒絕、stub 錯誤物件原樣傳遞、fixture 建立後阻斷 I/O 及日誌 |
| 額外 | 必填與 keyword-only 呼叫契約 |
| F01–F02 | Sol 已執行；F01 完整／降級樣本於 1280 px／390 px 視覺驗收通過，F02 專屬與 S6 回歸共 55/55 通過 |

測試重用 `test_lot_scenario` 的 capture／evidence／pending fixture 函式與既有 lot helpers；沒有匯入該模組的 TestCase 至本模組，不複製完整 S6 校驗。臨時 Journal 在 finally 中 close，之後才清理臨時目錄，以符合 Windows 檔案生命週期。

## Sol 驗證（已執行）

```text
<python> -B -m unittest discover -s tests -p "test_lot_scenario_report.py" -v
<python> -B -m unittest discover -s tests -p "test_lot_scenario.py" -v
```

實際執行 S7 21 個、S6 34 個，共 55 個測試方法，全部通過。S4／S5 未修改且未出現相關失敗，因此未擴充其測試。新增 Python 檔案編譯通過；diff／staged 檢查由本輪 Git 驗收完成。未執行全量測試。

F01 實際以 1280 px／390 px 檢查完整與降級樣本：

1. 完整樣本使用多空 Lot、合成 physical、有效 mark 與完整 pending，確認欄位／長 capture ID 可讀、負數與零正確。
2. 降級樣本使用 unmanaged unresolved Lot、缺 mark 或過期 capture，確認「不可用／未提供」與零區分、仍有值時品質旗標及原因可見。
3. 加入合法長小數 mark（例如 `Decimal("100.123456789012345678901234")`）檢視換行；勿以不合法 capture 或截斷數值簡化驗收。
4. 測試／驗證端以 renderer 回傳字串寫到新的本機檔案，使用 exclusive create 避免覆寫；renderer 本身不負責保存。HTML 與截圖不須加入程式提交。

桌面與窄視窗均已確認來源說明醒目、不靠顏色判斷、沒有內容遮擋；四組渲染均無整頁水平溢位或裁切儲存格。驗收產生的 HTML 與截圖保留於本機 `reports/visual-qa/`，不納入程式提交。

本輪以限定範圍 commit 交付；下一片再依實際報告使用需求評估，不自動增加 CLI、行情或交易接線。
