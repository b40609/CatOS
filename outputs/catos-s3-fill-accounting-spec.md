# S3：合成成交歸屬與 Lot 帳務更新

狀態：2026-09-16 設計已交付；使用者後續明確要求「執行」，現已編寫程式與測試，待 Sol 質檢。下文保留設計階段政策及驗收矩陣，最新實作細節與限制見 [S3 交接](../docs/lot-fill-handoff.md)。後續驗收完成即主動評估下一片。

基線依使用者提供的 Sol 報告：S2 commit `690d8549dd4d078d5e62a12acf536ba0f768bdcb`；447/447 通過，Windows 中斷測試 4/4、0 skip；Python 3.14.6、SQLite 3.50.4。本輪未重跑驗證或核對 Git。

## 1. 目的與範圍

S2 只能證明快照被原子保存，不能證明其數量與損益由成交正確導出。S3 接受受信父側提供的合成逐筆成交，由純 Decimal reducer 算出快照，再於同一 Journal 交易保存成交與 Lot 版本。

| 具體失敗 | 最小機制 | 驗證成本 |
|---|---|---|
| 相同成交以不同 write_id 重送而重複入帳 | 獨立成交唯一鍵、內容指紋 | 重送與衝突測試 |
| 成交保存後程序死亡，Lot 未更新 | 共用既有交易與內部 Lot 寫入操作 | SQL 注入、程序中斷 |
| 平倉報告先於開倉／漏一筆成交 | 每個合成訂單連續 fill_seq、單 Lot 串行責任 | 缺號、亂序、終態測試 |
| 部分平倉後錯用歷史 opened_qty 作成本權重 | 明確數學規則與逐筆重算 | 多空手算例、Decimal 邊界 |
| 直接覆寫快照掩蓋漏帳 | S3 管理的 Lot 禁止外部 S2 修改；重啟雙向比對 | 繞過寫入與損毀測試 |

僅 local-sim、合成資料、一訂單對一 Lot；不做 FIFO／比例分配、內部對沖、成交拆分、多 Lot 合併訂單。沒有交易所來源適配、累計回報轉逐筆、Worker 接線、下單、Gross、P6 改造或資金費分攤。既有 v1 表與交易限制不變。

## 2. 本片提出的政策

以下政策已按使用者執行指示納入合成切片，不宣稱是交易所契約：

1. 只接受不可變逐筆成交；數量為本筆張數，禁止把累計數量當成交。`fill_seq` 是合成來源明示的訂單內序號，不從 trade_id、時間戳或收到順序猜測。
2. 費用必須已完整提供，且以 USDT 計價。`fee_paid > 0` 表示支出、負值表示返佣；來源若符號相反須由未來適配器轉換。缺費用、其他幣別或更正成交明確拒絕，保留未決責任；不得填零、覆寫舊成交或發明費率。
3. 每個 Lot 同時只允許一個未決合成訂單；開倉訂單結束後才允許平倉。不支援已關閉 Lot 再開。OPEN 的多筆成交屬同一開倉意圖；不新增 S1 未定義的加倉意圖。
4. 不接管已有 S2 快照。S3 只管理自己從首次成交建立的 Lot；既有 S2 Lot 照舊可用，兩類不得混寫。
5. 終態由明示的合成完整性證據關閉，不能因 remaining_qty=0 或 filled_qty 達上限自動解除未決旗標。
6. 平均成本與損益使用既有 50 位 ROUND_HALF_EVEN Decimal 規則；這是本機模型精度，非交易所結算精度。數量加減必須精確可表示，不能因捨入吞掉小量。

費用晚到／成交修正留後續獨立事件規格；本片拒絕後可用完整且尚未入帳的原成交重試，已提交成交不可換內容。

## 3. 資料契約與身份

全部 frozen 純資料；整數拒絕 bool，Decimal 拒絕 float／非有限值。沿用 S1 token、scope、合約與 ID 驗證；快照沿用派生精度，定點 canonical intent 與快照 wire 保持分離。

`SyntheticOrderBinding`：scope、bot_id、inst_id、source_id、order_id、IntentContext、原始 OPEN/CLOSE 意圖、intent_key、lot_id、resolved_quantity。建立時以交易內最新 Lot／旗標重新執行 S1 驗證，不能僅相信呼叫端的 ValidatedLotIntent。

- OPEN 必須尚無此 Lot，保存初始 side／protection；Lot ID 由原 OPEN key 派生。
- CLOSE 指向既有 S3 Lot，expected_revision 在綁定時檢查；全平量固定為當時 remaining_qty，不在每筆成交重新解析。
- 訂單綁定是測試歸屬證據，並非 outbox、額度預留或風控授權。
- `(bot_id,event_seq)` 不可跨 OPEN/CLOSE 重用；intent_key 與訂單關聯一對一。

`SyntheticFill`：scope、source_id、inst_id、order_id、trade_id、fill_seq、quantity、price、fee_paid、fee_currency='USDT'。Bot／Lot／方向從 binding 取，不接受成交覆寫。

成交唯一鍵：`(account_ref, environment, source_id, inst_id, order_id, trade_id)`；不含 bot_id／write_id，避免改歸屬逃過去重。這只是合成來源命名空間，不預設 OKX tradeId 的全球唯一性。

數量 >0、價格 >0；價格符合 tick，數量符合 lot_size；單筆部分成交可低於 min_size，但訂單意圖仍遵守 S1 min_size 規則。數量可接受 S1 派生精度以支援派生全平，價格／費用採輸入精度。累計成交不得超過 resolved_quantity，平倉不得超過當前 remaining_qty。

重送先查成交唯一鍵：數值等價且其餘內容相同回原收據，即使訂單已終態或 Lot 已推進；同鍵異內容拒絕。新成交的 fill_seq 必須是前一筆 +1，缺號不入庫、不緩存、不自行排序。

## 4. 純帳務 reducer

記 q 為本筆成交張數、p 為價格、m 為 base_per_contract、R 為成交前 remaining_qty、A 為平均入場價，方向 s：long=+1、short=-1。

| 操作 | 更新 |
|---|---|
| 首筆 OPEN | opened=q、remaining=q、average=p、realized_pnl=0、fees_paid=fee_paid、funding_paid=NULL、revision=1 |
| 後續 OPEN 成交 | opened'=opened+q；remaining'=R+q；average'=(R×A+q×p)/(R+q) |
| CLOSE 成交 | remaining'=R−q；opened、average 保留；realized_pnl'=realized_pnl+s×(p−A)×q×m |
| 任意成交 | fees_paid'=fees_paid+本筆費用；funding_paid 不變；既有 Lot revision+1 |

realized_pnl 為未扣費用的價差損益，費用不得重複扣入。funding 未知時不輸出宣稱完整的淨損益。CLOSE 不改平均成本，即使全平也保留原值供 S1／S2 歷史驗證。

使用固定 localcontext，禁止改全域 context。成本除法允許明示的 50 位捨入；所有輸出重新通過 S1 派生範圍檢查。數量加減以足夠精度的有界暫存計算後驗證可精確儲存；若超出 50 位有效數字拒絕整筆，不得靜默截斷。溢位、過小結果／意外歸零或合約對齊失敗亦拒絕。

手算基準：m=0.01，多倉 q=2@100、q=1@130，remaining=3、average=110；平1@120 得 realized_pnl=0.10，餘2；再平2@90 得累計 -0.30。四筆費用另加，空倉方向反轉應有對稱例。

## 5. 儲存與接口

預計 schema 7，新增三張 STRICT 表；沿用同 DB、同 writer、WAL/FULL、FK ON。金融數字都是 TEXT；數值檢查由 Python Decimal 執行，禁止 SQLite CAST REAL／SUM。正式 DDL 隨核准實作，必須具有下列鍵與約束：

| 表 | 核心欄位與約束 |
|---|---|
| lot_fill_orders | scope/source/order 複合 PK；bot FK lot_bindings；inst_id、intent_key UNIQUE、event_seq、lot_id、operation、binding_json/hash；resolved_quantity TEXT；UNIQUE(bot_id,event_seq)。OPEN 綁定時尚無 lot_heads，所以 lot_id 不設立即 FK；恢復檢查關聯 |
| lot_fill_events | 成交複合 PK；FK order；fill_seq INTEGER>0、UNIQUE(order key,fill_seq)；quantity/price/fee_paid TEXT、currency CHECK USDT；event_json/hash；lot_id/revision FK lot_revisions，且該版本 UNIQUE；保存原 S2 收據欄位 |
| lot_fill_terminals | order key PK/FK；terminal_id、status CHECK FILLED/CANCELED/REJECTED；final_fill_seq INTEGER>=0、final_filled_qty TEXT；terminal_json/hash；可空 lot_id/revision FK（零成交 OPEN 無 Lot），兩欄必須同為空或非空 |

所有 JSON 有界、嚴格解析；hash 與指紋用 S2 數值身份規則，版本固定。DB scope 必須匹配 Journal；跨 Bot／scope／合約拒絕。沒有到 v1 execution／ownership 的外鍵。

公開 API：

- `bind_order(binding)`：不可變、同內容冪等；拒絕衝突和同 Lot 第二未決訂單。CLOSE 綁定同交易增加 Lot 版本並設 closing_unresolved=True；OPEN 尚無成交不建立零量 Lot。
- `apply_fill(fill)`：回固定 FillReceipt（唯一鍵、Lot revision、commit_seq、指紋、replayed）。首筆 OPEN 建立 Lot 並設 opening_unresolved=True；後續成交保留未決旗標。
- `finish_order(evidence)`：final_fill_seq／final_filled_qty 必須與已保存成交完全一致。FILLED 要等於委託量；REJECTED 要零成交；CANCELED 允許部分成交。已有 Lot 則同交易新增旗標清除版本；零成交 OPEN 僅保存 terminal。終態同內容重送回原結果，衝突拒絕。
- `get_order`、`list_fills`：有界查詢、固定排序。
- `recover`：只讀重算與驗證，無自動修復。

finish 的證據只適用合成測試來源；不是「收到交易所終態便能證明全部成交已齊」。終態後新成交拒絕；已保存成交的原樣重送仍回收據。

### 5.1 原子化與禁止繞過

S2 公開 API 現在各自開交易，不能先呼叫 create/replace 再另外寫成交。抽出內部「已有交易」操作，S2 公開接口仍保留原行為並拒絕巢狀交易；S3 外層只開一次 BEGIN IMMEDIATE。

順序：驗證 binding／去重 → 讀最新狀態 → reducer → 內部 Lot 版本寫入 → 成交／終態紀錄 → COMMIT → 回收據。內部操作只供 Journal 模組使用，不提供 Worker 或任意回呼能力。

S3 管理 Lot 的任何公開 S2 create/replace（含修改 protection／flags）均拒絕；防止成交算出的歷史被手工快照繞過。S2 原有未管理 Lot 保留原接口。每個 S3 Lot 版本必須能對應首筆成交、後續成交、CLOSE 綁定或終態事件之一；恢復不得容忍未知額外版本。binding／terminal 存其產生的版本及收據，實作 DDL 需補齊這些關聯欄位。

不重算或寫入 v1 ownership、execution_fills、reservation、日損或 P6。儲存錯誤／COMMIT 不確定沿用 S2 停用 handle 後重啟核實，不能用新成交 ID 重試。

## 6. 重啟與升級

schema 6→7 在既有初始化交易增加三表，舊 S2 Lot 不自動轉成 S3；既有 schema1–5 先按原規則升級。舊版本殘留 S3 表、未知 schema、錯誤 DDL 拒絕。只以臨時 DB 驗證；不操作使用者既有 DB。

先執行 S2 完整性檢查，再驗證 S3 表／外鍵、binding 原意圖、成交唯一性及連續序列、終態完整性。按保存的 Lot revision 次序重放 OPEN／CLOSE binding／fill／terminal，從第一筆 OPEN 重算每個版本，逐欄對照 S2 快照、旗標、hash、收據及 head。

檢查雙向完整性：每筆成交引用一個正確版本；每個受管 Lot 版本必須有且只有一個原因；終態不能早於最後成交，未決狀態與 flags 一致。零成交 OPEN 只有 binding／terminal 是合法狀態。刪除事件、孤立版本、篡改成本、費用或錯誤歸屬皆拒絕整個 Journal 啟動，不補帳不重送。

重啟恢復不授予交易權、不清除 latch、UNKNOWN 或 v1 對帳責任。

## 7. 預計測試清單

每列為驗收情境群，實作時可拆多個方法；不預先宣稱方法數或通過數。

| ID | 驗收情境 |
|---|---|
| A01–A04 | 多／空首筆、分批開倉平均成本、部分／全平、費用與返佣獨立累加 |
| A05–A08 | 合約乘數、步長／tick／min_size 邊界、超平／超委託量、閉合 Lot 不重開 |
| A09–A12 | 外部低精度 context 不影響；50位／指數邊界；數量不可無聲捨入；拒絕 NaN／float／bool |
| B01–B04 | 原意圖重新驗證、scope／Bot／合約隔離、事件序號不重用、一 Lot 一未決訂單 |
| B05–B08 | 首筆原子建 Lot、CLOSE 綁定旗標版本、零成交 OPEN 終態、部分成交取消 |
| B09–B12 | 同成交跨 write_id 去重、數值等價重送、同鍵異內容拒絕、終態後歷史收據重放 |
| B13–B16 | 缺號／亂序可補齊後重送；累計資料拒絕；缺費用／幣別／修正拒絕；不偽造零費用 |
| B17–B20 | 終態證據缺成交／錯數量／衝突；full fill 仍未決直到終態；終態後新成交拒絕；多 Lot 互不污染 |
| B21–B24 | 每步 SQL 故障回滾、busy／COMMIT 不確定、S2 受管寫入拒絕、舊 S2 接口保持 |
| R01–R04 | 正常重算所有版本、遺失成交／孤立版本、成本／費用／關聯篡改、未決與終態不一致 |
| R05–R08 | schema6及舊版升級、DDL／殘留表拒絕、失敗升級回滾、v1 表與風控語義不變 |
| C01–C04 | 首筆 OPEN 中斷、部分 CLOSE COMMIT 前、COMMIT 後 ACK 前、終態與旗標原子中斷 |

程序案例在 Windows 真實子程序退出後重開臨時 DB，核對成交數、版本、flags 與原收據；0 skip 才算平台案例已驗證。

## 8. 實作順序與交接

1. 核准第2節政策及本片邊界；把本提案狀態改為已核准，P8 同步允許隔離合成逐筆帳務。
2. `catos/lot_accounting.py`：純資料契約／reducer，先寫手算及精度測試。
3. `catos/lot_journal.py`：最小抽出交易內操作與受管 Lot 寫入閘門，保持 S2 公開契約。
4. `catos/lot_fills.py`：STRICT DDL、綁定、原子成交、終態、查詢與重放；Journal 接入 schema7。
5. 新增 accounting／fill journal／process 測試，更新舊版遷移夾具與交接文件。
6. Astra 靜態核對後交付；Sol 執行新模組、S1/S2 及受影響 v1 回歸、Windows 中斷與 Git 工作。本提案不授權 push 或真實採集。

完成界線：專屬測試與受影響回歸經 Sol 驗證，成交與快照不漏不重，v1 基線保持。屆時主動評估下一片；初步候選為「純資料 Gross／實體淨曝險對照」，先確認所需價格與在途資料契約是否齊全，不直接接交易。

## 9. 持續協作

驗收回報到達後，自動整理基線、檢查剩餘缺口並提出下一片具體範圍，不再等待使用者詢問下一步。這是後續互動的工作方式，沒有建立背景排程，也不表示未核准政策、實際交易或無限擴充已獲授權。
