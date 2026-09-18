# S4 開發交接：純資料曝險觀測

最新驗收（依使用者2026-09-18回報）：commit `8b16c0b244af611294ec0a98b8add835bb14008b`；S4 36/36、S1 26/26、Risk14/14，合計76/76、0 failure/error/skip，未跑全量。以下待驗證敘述保留為開發歷史，本輪未獨立重跑驗證。

2026-09-18：依使用者「同意刪除並執行」完成程式與專屬測試編寫，待 Sol 獨立質檢。正式依據為 [S4 規格](../outputs/catos-s4-exposure-spec.md)。使用者已確認的舊草稿已刪除；不以舊稿 UNKNOWN／新鮮度規則實作。

## 本輪變更

- `catos/lot_exposure.py`：frozen/slots 證據與報告型別，單一 `observe_exposure()` 純入口；在入口完整驗證資料，沒有 DB／網路／系統時鐘存取。
- `tests/test_lot_exposure.py`：36 個 E01–E36 方法，包含子案例；無 SQLite fixture、無程序啟動。數量只是編寫數，不是通過數。
- 刪除 `outputs/catos-s4-exposure-observation-spec.md`，依使用者明確授權。
- 更新正式規格狀態、工作計畫、README 與本交接文件。

未修改 Schema、risk.py、S1/S2/S3 業務程式、3x／50%、日損、P6、Worker、Supervisor 或交易路徑。未執行測試、編譯、Git、資料庫操作或外部請求。

## 關鍵行為

1. 張數精確加總，Gross不抵銷；Net與實體差額固定為Lot Net−physical。只有Lot完整、新鮮、physical已知／verified／新鮮且同cut才有差額。MATCH不是對帳完成或交易許可。
2. mark可不對tick；缺價／過期／未來取樣時估值為None，獨立保留數量比較。未來取樣同時記future_observation與相應stale原因。
3. 按obligation_id去重；同ID完全等價的Decimal數值只計一次，任何來源／方向／數量／狀態／歸屬衝突拒絕。沒有跨來源自動挑選。
4. UNKNOWN有明示數量時仍算情境且has_unknown=True；未知數量、缺完整集合、截點或flags配對不足時，在途合計／分項與情境上界為None。未成交CLOSE不扣目前Gross。
5. UNCLASSIFIED責任可進物理情境，但不輸出虛擬Gross情境；若引用無法找到的Lot，關聯不足，兩者均降級。Lot雙向未決flags也降級，不猜分配。
6. Lot與實體MISMATCH不禁止列出兩者各自的合成情境；不輸出accepted／ready／allowed等裁決欄位。
7. `lot_complete`／`pending_complete`是原始來源完整性聲明；須連同fresh、verified、原因及可空結果解讀。has_unknown僅描述所見UNKNOWN；輸入缺失不代表沒有UNKNOWN。
8. 固定512位local Decimal context，捕捉Inexact／Underflow；每個計算結果正規化後通過S1派生範圍。估值超出範圍整筆拒絕，不產生捨入的近似值或假零；不改呼叫端context／flags。
9. Bot64、Lot4096、在途觀測4096硬上限，重複觀測也先占輸入容量；不截斷。輸入順序不影響報告，原因排序去重。

模組引用既有StoredLot作型別驗證，沒有建立Journal實例或讀取其資料。輸入均由合成測試或受信父側提供；本片沒有一致快照匯出器，cut_id是來源承諾而非函式自行取得的證據。

## Sol 驗證

```text
<python> -B -m unittest discover -s tests -p "test_lot_exposure.py" -v
<python> -B -m unittest discover -s tests -p "test_lots.py" -v
<python> -B -m unittest discover -s tests -p "test_risk.py" -v
```

以上是建議命令，本輪未執行。先執行36個S4案例，再依正式規格做S1及risk算術最小必要回歸。不因之前S3的243項通過而宣稱本片通過；無新增持久化，所以不新增Windows中斷案例或migration測試。

特別核對：E18未知量不變0、E20未分類／關聯、E23多空責任配對、E30極小差額、E31精確乘積／上下邊界、E35容量、E36既有實體情境數值。驗證報告記錄實際Python／SQLite環境、執行方法數與failure/error/skip；本片功能不需要SQLite runtime行為測試。

## 下一片

S4驗收回報後主動評估「同一讀取交易的一致Lot／在途快照匯出」是否具備足夠契約；不得直接將S3收據當作真實交易所在途證據。Gross限額、風控接線、Demo／Live仍另案，不在本次開發範圍。
