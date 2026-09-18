# S5 評估：一致 Lot／合成未決責任快照

2026-09-18。本輪為S4驗收後的範圍評估，沒有程式或Schema變更。基線依使用者回報：S4 commit `8b16c0b244af611294ec0a98b8add835bb14008b`，36項S4＋26項S1＋14項Risk，合計76項通過、0 failure/error/skip；未執行全量測試。未獨立重跑驗證或查Git。

## 評估結論

建議下一片S5只提供同一SQLite讀取交易取得的Lot與S3合成未決責任快照。它補上目前跨Bot／跨頁查詢可能混入不同版本的缺口，不接Gross限制、Demo／Live或任何交易路徑。

現有程式已具備S2／S3交易內完整性檢查與S3重放結果，無須新表。但S3沒有HELD／WORKING／UNKNOWN外部生命週期，不能僅因訂單存在就建構S4的EXCHANGE/WORKING，更不能把剩餘量為0當終態。

## 建議最小輸出

`LocalLotCapture`為不可變資料，包含：

- scope、完整ContractSpec、`capture_id`，呼叫端明示的取得時間與有效期限。
- 同交易讀取的全部匹配`lot_bindings` Bot清單、每Bot的commit_seq，以及按lot_id排序的StoredLot集合。
- S3未決責任集合：order_key、bot_id、lot_id、OPEN/CLOSE、BUY/SELL、resolved_quantity、已入帳fill quantity、remaining_quantity、最後已保存fill_seq。
- 來源明示為`synthetic_ledger`；沒有exchange origin/state、實體position、mark、verified或交易許可欄位。
- S2未受S3管理但帶未決flag的Lot ID清單：數量不可推算，顯示責任證據不足，不能以S3集合空白宣稱沒有在途。

未決定義為「已綁定且沒有已驗證terminal事件」，不是filled quantity小於委託量。首次成交前OPEN必須匯出，即使尚未有Lot；全成交未terminal也匯出，remaining=0但責任仍存在。終態訂單不列未決，已關閉Lot仍保留於Lot集合。

remaining_quantity以Decimal精確計算resolved_quantity−已去重成交總量；來源是S3帳本，不宣稱是交易所真實剩餘量。不建立、更新或清除任何flag。

## 一致讀取設計方向

1. 由現有Journal所屬執行緒、同connection呼叫；拒絕巢狀交易與已失效handle，不新增writer、常駐服務或另一條DB路徑。
2. 在同一顯式讀取交易內完成S2／S3完整性檢查、binding篩選、完整Lot讀取、未決責任重建及身份計算；所有資料物化後才返回。不逐頁呼叫公開API。
3. 現有`LotJournal._access()`使用BEGIN IMMEDIATE，不應把它描述成不占writer的純讀取交易。S5建議新增僅供匯出的BEGIN DEFERRED內部範圍；不改既有寫入transaction行為。第一次讀取確立快照後，後續查詢維持同一視圖。
4. 交易只執行SELECT與唯讀完整性檢查；不觸發初始化遷移、restart latch／UNKNOWN更新，也不另開Journal來匯出。
5. `capture_id`表示本機內容截點，可由scope、合約、匹配Bot水位及完整匯出內容形成確定性SHA256。不把全庫user_version或max(open_event_seq)當狀態版本；不重用Worker事件序號。
6. 大集合不能整包套入IPC的64KB限制。採固定順序、具名object逐筆有界序列化，再用長度前綴更新hash；不放寬IPC頂層object契約。時間戳與期限作包裝資料，不影響相同帳本內容的身份。
7. 沿用S4的64Bot／4096Lot／4096責任輸出上限，超限拒絕，不截斷或假稱完整。S3完整歷史校驗仍有隨歷史成長的成本，本片不加快取或checkpoint最佳化。

匹配同一inst_id的Bot若合約乘數／步長規格不一致，明確拒絕，不挑任一份。不存在該合約binding時回報未知合約，不自行建立空帳本。已存在binding但沒有Lot與責任才是可匯出的本機空集合。

## 與S4的界線

Lot部分可轉成S4 LotInventory，但「完整」只限該Journal中所有匹配binding；不能代表交易所帳戶的所有策略或手動部位。匯出不接受Bot子集冒充全合約視圖。

S3未決責任先以自身資料契約輸出，不直接產生S4 PendingInventory。將來串接S4需要明確的合成情境適配，或能證明實際origin/state的父側來源；兩者均不能猜測。

實體部位要有獨立來源，不能用Lot Net製造必然MATCH；外部資料也不能僅貼上capture_id就宣稱同截點。S5不替不同來源建立不存在的原子一致性。

## 驗證成本與預計情境

- 同合約多Bot／多Lot／已關閉Lot／空集合，完整穩定排序；其他合約隔離。
- 未成交OPEN、部分成交OPEN/CLOSE、全部成交但未terminal、terminal後移除未決。
- S2未受管未決Lot不被漏報；合約規格衝突／數量超限明確拒絕。
- 相同內容重複capture身份一致，內容或責任改變身份改變；外部Decimal context不影響。
- 使用第二個測試connection，在第一個connection確立讀快照後提交更新；第一次capture只見舊的完整組合，下次才見新的完整組合，不能混讀。只用臨時DB，測试connection不成為產品新writer。
- 在讀取／校驗各階段注入失敗，沒有部分結果或任何資料寫入；損毀拒絕匯出。
- 匯出前後全部表內容及v1控制／對帳／P6資料不變；純讀取不產生新Lot revision／commit_seq。
- S2/S3直接受影響回歸與S4觀測回歸；沒有新的提交狀態機，暫不新增程序死亡測試。

## 後續交付

本評估先確立S5的最小範圍。正式 API、錯誤契約、hash 輸入格式及可控並行測試步驟已整理於 [S5 正式規格](catos-s5-snapshot-spec.md)；不先動Schema或業務程式。Astra開發、Sol獨立驗證／Git分工維持。

S5驗收後主動評估S4與本機合成快照的適配；Gross風控限制、真實帳戶適配與Demo／Live仍不在本片。
