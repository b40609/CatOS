# S6 範圍評估：S5 → S4 合成情境轉接

狀態：S5驗收後的下一片建議，非正式實作規格；尚未編寫S6程式。

## 當前缺口

S5可提供同一SQLite讀取交易內的Lot、水位與synthetic pending。S4需要來源origin、責任state、完整性與共同截點；S3 bind/fill/terminal並不能證明HELD、WORKING或UNKNOWN。直接預設狀態會把模擬假設當成帳本事實；將capture_id貼到外部physical資料也不能建立原子一致性。

## 最小候選方案

建立僅供local-sim使用的純資料轉接，消費既有LocalLotCapture，不另讀DB、不新增帳本或交易出口。Lot、數量與Bot水位取自S5；缺少的狀態若需表達，必須來自明示的合成情境輸入，且輸出可追溯其假設來源。不得將該結果當作交易所證據或增倉許可。

正式規格先定義以下契約，再進入實作：

- S5 pending與情境輸入以order_key逐筆對應；不得覆寫Lot歸屬、方向或數量。缺項、多項、重複與衝突須明定拒絕或降級行為。
- 不預設把synthetic pending映射成EXCHANGE／WORKING或HELD；選擇不擴充S4的明示模擬映射，或另立synthetic來源型別，須先比較語義與變更成本。
- physical與mark由獨立且明示為合成的情境資料提供，不由Lot Net反推。情境共同截點如何成立、何時必須維持不可比較，需有可驗證規則；capture_id仍只識別S5內容。
- 未受S3管理的unresolved Lot、首次成交前OPEN、零剩餘但未terminal責任均保留；缺證據不可當成零曝險或完整。
- 來源時間、有效期限、帳戶／環境／合約及Decimal限制沿用既有契約；不得因轉接刷新舊資料時間或放寬精度。

## 預計驗證範圍

專屬測試涵蓋多Bot多空、未成交OPEN、部分成交、零剩餘未terminal、未受管責任、映射缺漏／重複／衝突、來源與合約不符、過期／截點不符、Decimal邊界、輸入不可變，以及結果不能被誤認為交易所對帳或交易授權。另安排S5 capture至S4觀測的合成整合案例，確認CLOSE不提前扣除Gross、未知不轉為零；必要回歸限受影響模組，由Sol執行。

## 交接與範圍

S5接受基線為`274891981027cf554c590224f68f4ea7c46bb716`，使用者回報180/180通過，非全量測試。正式規格見`catos-s5-snapshot-spec.md`，開發與驗收紀錄見`../docs/lot-snapshot-handoff.md`。

Astra負責設計及程式／測試編寫；Sol負責執行驗證與Git。S6不改Schema、Gross限額、risk.evaluate、P6或Demo／Live交易路徑。無實测瓶頸，不增加快取、checkpoint或新服務。

工作區另有使用者指出的未提交`yaozi-functional-parity-spec-v0.1.md`，與本片無關，不讀取或納入修改。正式 API、pending taxonomy、共同 cut attestation、完整性與驗收清單已整理於 [S6 正式規格](catos-s6-scenario-spec.md)；本評估保留為範圍決策紀錄。
