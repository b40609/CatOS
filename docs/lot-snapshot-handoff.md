# S5 開發交接：一致 Lot／合成未決責任快照

## 正式驗收結果（使用者回報）

S5已由Sol驗收並提交：`274891981027cf554c590224f68f4ea7c46bb716`，`feat(lots): add S5 consistent snapshot capture`。專屬39/39、必要回歸141/141，合計180/180、0 failure/error/skip；真實雙connection WAL隔離與4096/4097邊界通過。Python3.14.6／SQLite3.50.4，diff/staged檢查通過；未執行全量測試。Schema7及既有Risk／execution／protection／交易路徑未變。

回報時main ahead5；另有未提交且與S5無關的`outputs/yaozi-functional-parity-spec-v0.1.md`，不可稱工作區全乾淨。本次驗收紀錄更新在S5提交之後；Astra未重跑測試或查Git。下方保留原開發交付與驗證設計供追溯，驗證結果以上述回報為準。

依 [正式S5規格](../outputs/catos-s5-snapshot-spec.md)完成程式與測試編寫。開發階段Astra未執行測試、編譯、Git、資料庫操作或外部請求。

## 變更

- 新增`catos/lot_snapshot.py`：三個frozen/slots輸出型別、輸入檢查、快照物化與streaming SHA256。
- `catos/journal.py`僅增加`capture_lot_snapshot()`及私有`_lot_read_snapshot()`；既有初始化、寫入交易與業務流程不變。
- 新增`tests/test_lot_snapshot.py`：39個測試方法，包含子案例；D01–D04由一個實際双connection測試共同驗證，容量邊界分成Bot／Lot／pending三個方法。規格的E07／E08另由回歸及Git檢查驗收，不偽裝成新單元測試。
- 更新規格狀態、README、WORK_PLAN及本交接文件。未修改Schema7、S1/S2/S3/S4業務程式、risk、P6或交易路徑。

## 重要語義

1. 先驗證scope／inst／明示時間與handle；同一connection執行BEGIN DEFERRED，第一個SELECT讀metadata並檢查帳戶／環境／budget。所有S2/S3完整性校驗及匯出讀取均留在該快照內；全部物化與hash完成，再ROLLBACK，之後返回。
2. 純讀路徑不呼叫`_commit()`、不開新connection、不重新初始化Journal、不修改任何table／PRAGMA設定。既有SQLITE一致性／外鍵檢查只讀。沒有借用外層交易；巢狀呼叫拒絕，保留呼叫端交易。
3. 同合約所有Bot納入，完整ContractSpec不一致即拒絕；current head包括closed Lot。其他合約不進輸出／hash，但全庫S2/S3完整性檢查仍會拒絕損毀，不跳過坏資料。
4. S3使用既有重放結果，不複製帳務reducer。未成交OPEN與零剩餘但未terminal責任均保留；未受管未決Lot列獨立清單。無HELD／WORKING／UNKNOWN、physical／mark或交易許可欄位。
5. hash固定domain tag `catos-local-lot-capture-v1`，逐fragment具名object／有界canonical JSON、8-byte big-endian byte length，按header→Bot→Lot→pending→unmanaged順序。全部Decimal用S2數值身份；時間與DB path不進hash。
6. 輸出上限64Bot／4096Lot／4096pending。完整歷史重放的成本仍隨歷史增長；只限制輸出，不聲稱限制全庫歷史讀取量，不另加checkpoint／快取。
7. caller錯誤（時間、scope、binding_not_found、contract_conflict、capture_limit）不使handle失效；損毀會失效。讀取I/O及rollback失敗回storage_unavailable並停用handle。S5會辨識既有replay例外cause中的SQLite錯誤，避免把被包裝的I/O誤當資料損毀。rollback失敗不交付capture。

## 測試設計

- 內容／身份：空binding、未知binding、多Bot／其他合約隔離、合同衝突、current head、所有未決生命週期、多空方向、完整內容hash、數值等價、時間／path排除。
- 並行：兩個測試Journal先開妥；reader消費第一個metadata SELECT後，同執行緒的測試攔截器讓第二connection真實提交多Bot／多Lot成交。reader仍取得舊的完整組合；下次capture才見全部新組合。無sleep、不依賴競速成功。
- 無寫入：SQL trace檢查BEGIN DEFERRED、首SELECT與ROLLBACK；禁止呼叫_commit；對含v1 owner、risk latch與P6未決資料的所有table做前後一致比對。
- 故障：讀取／解碼／hash失敗、被replay包裝的I/O、rollback回應失敗、巢狀與失效handle、S2/S3篡改拒絕。
- 容量：臨時DB實際建立64／65Bot、4096／4097Lot與pending，不mock capture的校驗。大pending fixture以測試專用批次寫入避免逐次public replay的平方成本，capture仍執行未修改的全量完整性重放。
- 串流：200個Lot形成總長超過64KB的capture，每個fragment仍受原IPC上限保護；不放寬object頂層限制。

## Sol 驗證順序

```text
<python> -B -m unittest discover -s tests -p "test_lot_snapshot.py" -v
```

必要回歸：`test_lot_journal.py`、`test_lot_journal_process.py`、`test_lot_accounting.py`、`test_lot_fills.py`、`test_lot_fills_process.py`、`test_lot_exposure.py`，以及公開入口所在Journal的`test_journal.py`。這些命令／範圍尚未由Astra執行；依實際失敗再擴充，不預先宣稱全量通過。

另檢查Git diff/staged、schema版本不變、risk.py／execution／protection未變。確認並行案例在Windows／WAL真實執行，非mock commit；記錄interpreter、SQLite版本與run/failure/error/skip。容量案例允許比一般小fixture較慢，不以縮小上限取代正式邊界驗證。

## 下一片

S5驗收後主動評估明示的synthetic adapter，處理S5未決責任與S4 origin/state契約差異。未核准前不填造交易所狀態，不把外部physical／mark貼上capture_id當作原子一致，不接Gross限制或Demo／Live。
