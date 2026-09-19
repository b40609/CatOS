# S7 範圍評估：本機合成情境報告入口

狀態：2026-09-19，依使用者同意完成範圍評估。本文為下一片建議，尚非正式實作規格，未編寫 S7 程式。基線為已驗收 S6 commit `ecc897e3afc19ab03527a4e1529f060b83f21df7`；115/115 的驗收範圍及來源見 [S6 交接](../docs/lot-scenario-handoff.md)。

後續進度：使用者同意後已制定 [S7 正式規格](catos-s7-scenario-report-spec.md)，API、欄位映射、錯誤及驗收契約以該文件為準。本文保留為範圍評估紀錄；程式尚未實作。

## 1. 目前需求與具體失敗情境

S5 已輸出一致的本機 Lot 快照，S6 以明示合成 physical／mark 情境轉接至 S4，返回 `SyntheticScenarioObservation` 與 `ExposureReport`。目前缺少供人閱讀這條資料鏈的專用報告；直接讀物件容易忽略來源與降級旗標。

- 未提供 mark 時，估值為 None；若呈現為 0，會誤認無曝險。
- Lot 數量與合成 physical 的 MATCH，容易被解讀為交易所對帳完成。
- pending 不完整或來源過期時，單獨顯示目前數量會掩蓋上界不可用的原因。
- `has_unknown=False` 只描述既有 EXCHANGE／UNKNOWN 語義，不能解讀為所有責任已終結。

最小做法為一個純呈現模組，產生可離線開啟的 HTML 字串。驗證成本集中在欄位映射、精度、降級標示及 HTML 逸出；不需常駐服務、前端框架或新增資料庫。

## 2. 建議入口與資料責任

建議新增 `catos/lot_scenario_report.py`，公開入口暫定 `render_synthetic_scenario_report(*, capture, scenario, now_ms) -> str`。

入口接受既有 `LocalLotCapture`、`SyntheticScenarioEvidence` 與明示整數時間；呼叫一次 `observe_synthetic_scenario()`，再依返回結果呈現。這可沿用 S6 身份與內容驗證，避免另開接受任意 report 並自行驗證的第二套契約。HTML 生成器不讀 DB、系統時鐘、環境變數或網路；呼叫端負責取得 S5 capture，並另行處理輸出檔案。

保留 `ScenarioInputError`／`ExposureInputError`，輸入失敗直接向呼叫端傳遞，不改成正常報告或空白數值。只呈現 S4 已算出的結果，不重算 Gross／Net、餘量、差額、估值或情境上界。

既有 `catos/reporting.py` 是研究績效報告，`catos/account_report.py` 是 I-b 採集解碼；此片不修改兩者。沿用標準函式庫與離線 HTML 的做法即可，不抽取通用報告框架。

## 3. 最小呈現契約

| 區塊 | 內容與語義 |
|---|---|
| 來源 | 固定醒目顯示「本機合成情境／SYNTHETIC_SCENARIO」，註明不是交易所證據或交易許可 |
| 身份 | local-sim、account_ref、合約、source_capture_id、scenario_cut_id、quote_id；capture hash 只代表內容身份 |
| 時間 | 明示 now_ms 及 capture／physical／mark 的 observed／valid 時間；整數標示 Unix epoch 毫秒，不讀目前時鐘 |
| 已觀測數量 | long、short、Gross、signed Net、合成 physical 與差額，單位均為張；差額固定為 Lot Net−physical |
| 估值 | Gross、signed Net、physical notional，單位 USDT；physical notional 沿用 S4 絕對值語義 |
| 未決責任 | pending buy／sell、synthetic buy／sell、held／exchange 分項與 unresolved／unique／duplicate 計數；保留來源語義 |
| 情境上界 | physical 與 virtual Gross 的既有上界，單位張；標示為合成情境量，不是限額或可用額度，CLOSE 不預扣目前 Gross |
| 品質與原因 | lot／pending complete、各 fresh、physical_verified、has_unknown，以及所有 reasons 原始代碼和簡短中文說明 |

Decimal 採完整固定小數格式，不轉 float、不四捨五入、不以科學記號隱藏細節；保留負號。None 顯示「不可用」，精確零顯示數值 0；缺席身份／mark metadata 顯示「未提供」。結果不可用時同頁列出完整原因，不自行推定單一欄位與單一原因的一對一關係。

MATCH 顯示「合成情境數量相符」，MISMATCH 顯示「合成情境數量不符」，UNAVAILABLE 顯示「無法比較」，並保留原始代碼。`physical_verified` 說明為 S6 對明示合成資料的既有映射，不代表向交易所查證。未知 reason 仍顯示原始代碼，不丟棄。沒有 reasons 時只顯示「無降級原因」，不產生通過／可交易裁決。

HTML 使用繁體中文、內嵌 CSS、無外部資源與 JavaScript；所有動態文字使用 HTML 逸出。長 ID／長 Decimal 應可換行或橫向捲動，不截斷數值。固定摘要表即可，不增加每 Lot 明細、圖表、互動篩選或第二種匯出格式。

## 4. 邊界與成本

本片只呈現 S5→S6→S4 的既有結果，不增加 schema、帳本、快取、寫庫入口、Gross 限額、風控裁決、額度預留或 P6 政策。不接 Worker／Supervisor、真實行情、Demo／Live 或歷史回測，不變更 v1 單合約單 Bot 規範。

首片只交付字串 API；CLI、檔案匯入契約、常駐 UI 與報告保存流程留後續需求。這能避免為展示另加快照序列化或 DB 路徑管理。既有 S6 呼叫仍具有原來的驗證成本，本片不宣稱改善歷史重放效能。

yaoI／yaozi 是獨立功能，market 相關檔案同樣不在此片的讀取、修改、驗收或提交範圍；現存 S5 未提交驗收紀錄保持原狀。

## 5. 最小驗收方案與交付

正式規格建議涵蓋下列情境群，案例數於測試編寫後如實記錄：

1. 完整有效情境：來源、身份、單位、MATCH／MISMATCH／UNAVAILABLE 與 S6 返回值一致。
2. 缺價、缺 physical、unmanaged pending、過期與未來取樣：不可用與精確零清楚區分，完整呈現旗標及原因。
3. 多空與 OPEN／CLOSE：使用現有 S6 情境確認呈現無抵銷 Gross、無預扣 CLOSE 或改寫上界。
4. 極小值、長 Decimal、負 Net、低精度呼叫端 context：完整保留數值，輸入與 context 不被修改。
5. 錯 capture 綁定或非法情境：既有錯誤向外傳遞；未知 reason 原始代碼保留，動態文字逸出。
6. 同輸入同輸出、無 I/O／時鐘／網路與外部 HTML 資源；以真實 S6 返回值覆蓋至少一條整合路徑。

Sol 執行新增報告專屬測試及 S6 必要回歸；S4／S5 若有被修改或出現相關失敗，再擴充對應驗證。HTML 另以完整與降級樣本做桌面及窄視窗人工視覺檢查，確認長數字／身份可讀、零與不可用不同且來源標示醒目。這是呈現驗收，不重跑全量測試或全市場回測。

下一交付建議為正式 API／欄位映射／錯誤契約與驗收規格，之後按既有分工由 Astra 編寫程式及測試、Sol 執行驗證與 Git。本文完成只代表範圍評估交付，不代表 S7 功能已完成或新政策已核准。
