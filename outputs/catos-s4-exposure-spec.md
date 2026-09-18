# S4：純資料 Gross／淨曝險觀測與差異報告

最新狀態（2026-09-18）：使用者回報本正式規格已通過靜態QA，並明確授權刪除舊草稿及進入實作。程式與36個測試方法已編寫，待Sol執行驗證；詳見 [S4 開發交接](../docs/lot-exposure-handoff.md)。下文設計階段的「本輪只有文件」保留為歷史，不變更正式契約。

2026-09-17。使用者同意執行下一個交付「輸入／輸出契約與驗收規格」；本輪只有設計文件，沒有程式、Schema、風控裁決或交易路徑變更。基線依使用者提供：S3 commit `604e983fdaef3bfaeade8648e67679a678149c17`，S3 53項與必要回歸190項、合計243項通過；不是全量套件驗收。本輪未執行測試或 Git。

## 1. 具體目的與界線

多 Lot 可能多空抵銷：long 3張、short 2張，Lot Gross 是5張、Net是+1張。只看實體淨倉1張會隱藏虛擬策略總部位；反過來，5張也不能直接當作交易所實際持倉或保證金。

S4 提供確定性的純資料計算與差異報告，僅使用合成 local-sim、USDT-M、cross＋net_mode。每次處理一個帳戶的一個合約、完整合約規格與一個共同截點。不做帳戶多合約加總、資金費、槓桿／保證金估算、限額裁決、latch變更或交易授權。

| 失敗情境 | 最小處理 | 驗證方式 |
|---|---|---|
| 多空相抵掩蓋虛擬總部位 | 分開顯示多、空、Gross、Net | 手算例及多空對稱 |
| 只讀一頁 Lot 就與全帳戶部位比對 | 明示完整性、所有 Bot 覆蓋與共同截點 | 缺頁／缺Bot時不可比較 |
| 同訂單同時出現在 held 與 exchange | 共同 obligation_id、來源互斥 | 重複去重及衝突拒絕 |
| UNKNOWN 或缺 mark 被當成零 | 可空結果與明確原因 | 未知量／過期邊界 |
| 未成交 CLOSE 提早降低曝險 | 當前曝險不預扣；在途分開計算 | 待平倉不改已持有Gross |
| 部位與 Lot 取樣不同步 | 比較要求相同可信 cut_id | 同時間戳不同截點仍不可比 |

不把報告命名為 risk-approved 或 reconciled；淨量一致只能表示該截點的数量相等，不能證明成交、費用、歸屬或帳戶對帳已完成。

## 2. 現有介面與本片輸入責任

- `LotJournal.list_current` 是按 Bot 分頁的目前快照，沒有跨多次呼叫的一致讀取承諾。禁止直接把幾頁結果貼同一 cut_id 當完整資料。
- `LotFillJournal.get_order/list_fills` 返回本機合成收據，沒有交易所 UNKNOWN 或完整未成交數量證據。S3 flags 只表示責任未決，不能推導在途張數。
- 既有 `risk.Snapshot.pending_buy/pending_sell` 與 local held intents 已分離；S4沿用這個區分，不修改 `risk.evaluate`。
- 本片由測試中的受信父側建立完整 frozen 輸入。未實作 Journal 匯出器或交易所適配器；將來匯出器必須在同一讀取交易取得 Lot、Bot覆蓋及在途集合，並與外部截點另行建立有效關聯。

cut_id 是受信輸入對共同狀態截點的明示承諾，不是時間戳碰巧相等，也不是 S4 自行查證的外部事實。

## 3. 輸入契約

所有資料使用 frozen dataclass／tuple。金額、價格、張數用 Decimal；整數拒絕 bool；禁止 float／NaN／Infinity，來源 token 沿用既有驗證。金融數值採 S1 派生範圍，合約仍採 S1 輸入範圍。非法輸入拋 ExposureInputError，資料有效但不完整則輸出降級報告。

### 3.1 ExposureRequest

| 欄位 | 定義 |
|---|---|
| scope | LotScope，environment限定local-sim |
| contract | 單一 ContractSpec，乘數、lot_size、tick等均驗證 |
| now_ms | 呼叫端明示時間；純函式不讀系統時鐘 |
| lots_view | LotInventory |
| physical_view | PhysicalPosition |
| mark_view | MarkObservation或None |
| pending_view | PendingInventory或None |

三種狀態來源各自帶 `cut_id`、`observed_at_ms`、`valid_until_ms`；mark 有獨立 quote_id及時間，不要求與部位同一cut，但必須同scope／合約且新鮮。時間整數範圍沿用ipc，valid_until必須大於observed_at；新鮮條件為 observed_at <= now < valid_until。未來取樣、已過期皆降級，不默認容忍秒數。

### 3.2 LotInventory

- scope、inst_id、截點／時間、`complete: bool`。
- `expected_bot_ids: tuple[str,...]`、`included_bot_ids: tuple[str,...]`；均不得重複，included只能為expected子集。complete=True必須集合相等，否則輸入矛盾，拒絕。
- `lots: tuple[StoredLot,...]`；每筆scope／inst一致，Bot在included內；Lot完整重建驗證，revision和commit_seq合法。lot_id不可重複，即使快照數值相同也拒絕，防止拼頁錯誤。
- 只有所有頁面及所有合成歸屬Bot已覆蓋才可標complete；complete=False時，所見合計只標記observed，不稱完整總額或可信下界。
- 已關閉Lot可保留，其remaining=0不產生部位曝險；opening／closing_unresolved仍須保留為診斷，不由部位為0推定責任解除。

### 3.3 PhysicalPosition

- scope、inst_id、截點／時間、`quantity: Decimal | None`、`verified: bool`。
- quantity是net_mode有號張數，正多負空；None表示未知，0才表示明確空倉。
- 非空數量须符合lot_size；verified=True且quantity=None屬矛盾輸入，拒絕。數量存在但verified=False可列作觀測值，不能參與可信差額判定。
- 不載入 long_short_mode 雙邊部位、不自動轉換交易所帳戶模式。

### 3.4 MarkObservation

- scope、inst_id、quote_id、mark: Decimal >0、時間與有效期限。
- mark用於估值，不是委託價格，**不要求tick對齊、不做tick取整**。
- 缺價、過期或未來價格使所有標記估值為None；有效部位張數仍可報告。

### 3.5 PendingInventory

- scope、inst_id、cut／時間、complete、`orders: tuple[PendingObligation,...]`。
- obligation包含共同 `obligation_id`、origin=HELD/EXCHANGE、state=HELD/WORKING/UNKNOWN、side=BUY/SELL、`remaining_quantity: Decimal | None`、effect=OPEN/CLOSE/UNCLASSIFIED、`lot_id: str | None`。
- HELD origin只能對HELD state；EXCHANGE只能對WORKING/UNKNOWN。均是未決責任，終態不應出現在集合。
- obligation_id由受信父側跨來源一致映射，不使用交易所order_id與本地intent_id兩個不同名字各算一次；沒有已知共同身份時不得聲稱集合完整。
- 同obligation_id完全相同的重複觀測可去重；數量、來源、狀態、方向或關聯不同則輸入衝突，拒絕。尤其held→exchange雙份不能自動挑一份；父側應先產出同截點的一致狀態。
- remaining_quantity非負、符合lot_size；0仍可帶UNKNOWN責任。None不當0，即使state已標WORKING。
- OPEN/CLOSE要有lot_id。CLOSE須指向所提供Lot且side為其減倉方向；OPEN若已有Lot則方向須一致；尚無Lot的OPEN可指向預定Lot ID。UNCLASSIFIED不作虛擬Gross推算，但有已知side／數量仍能進物理在途情境。
- 同一個Lot同截點最多一個不同obligation，對齊S3串行限制。Lot未決flag必須有責任對應；已分類責任須與相應flag一致。UNCLASSIFIED若關聯到既有Lot，僅能證明有未決責任，不能證明OPEN/CLOSE分類；可保留物理情境，但虛擬Gross情境為None。缺對應或flags雙向未決時，標`pending_lot_link_incomplete`，不輸出完整在途情境；不得推測數量。
- PendingInventory=None代表未提供，不代表空集合；只有complete=True的空集合才聲明沒有在途（仍需flag關聯檢查）。

有界輸入：最多64個Bot、4096個Lot、4096個在途觀測；超限明確拒絕，不截斷。這是本片計算／記憶體邊界，不是交易策略配額。數字供實作驗收固定使用，不新增配置框架。

## 4. 計算規則

以下所有量都限定同一合約，張數不可跨不同合約直接相加。

| 結果 | 算法／含義 |
|---|---|
| observed_long_qty | 所見long Lot的remaining_qty加總 |
| observed_short_qty | 所見short Lot的remaining_qty加總，保持非負 |
| observed_gross_qty | long＋short |
| observed_net_qty | long−short，有號 |
| physical_qty | 提供的有號實體張數或None |
| delta_qty | Lot Net−physical；只在可信比較成立時產生 |
| observed_gross_notional | observed_gross_qty × base_per_contract × fresh mark |
| observed_net_notional | observed_net_qty ×乘數×mark，有號，命名明示signed |
| physical_notional | abs(physical_qty)×乘數×mark；保留其verified/fresh標記 |

`comparison_status`只取MATCH、MISMATCH、UNAVAILABLE。成立條件：Lot完整／新鮮、physical已知／verified／新鮮、兩者cut相同。以精確張數比較，**沒有epsilon或容忍比例**。價格缺失不妨礙張數比較。

在途集合完整、新鮮、quantity全部已知、關聯可用且cut與Lot及physical一致時：

- pending_buy_qty／pending_sell_qty分別加總所有唯一責任，保留held／exchange分項；相反方向不相抵。
- `physical_scenario_upper_qty = max(abs(physical_qty − pending_sell_qty), abs(physical_qty + pending_buy_qty))`。包含CLOSE，只作保守數量情境，不假設reduceOnly執行機制或掛單必成交；當前physical_notional不改。
- `virtual_gross_scenario_upper_qty = observed_gross_qty + sum(OPEN remaining_quantity)`。不扣CLOSE。需Lot完整、新鮮且所有責任effect已分類；有UNCLASSIFIED則此欄None。
- UNKNOWN但剩餘量已知仍納入情境，同時保留has_unknown=True；若量未知，完整在途合計與兩種upper欄都為None，不輸出忽略未知部分的「上界」。
- quantity為0的UNKNOWN不影響數字，但仍是未解除責任；報告不解除任何gate。
- 在途推算需physical verified；Lot Net與physical若不相等仍可分別算各自的情境，但comparison保持MISMATCH，不合併成單一帳戶風險結論。

這些upper欄只是在明示完整數量與方向下的合成情境，不保證未來成交價格、不包含未知新委託，也不是交易授權或Gross風控門檻。

Decimal數量加總／減法要求精確可表示，使用有界高精度暫存，輸出通過S1派生限制；不可因50位捨入吞掉小部位。估值同樣用足夠精度算乘積再验证派生範圍，超出範圍拋`decimal_range`，不靜默捨入／改float。對4096筆、各最多50位／指數範圍的加總及三項乘積，建議固定512位本地Context，明確捕捉溢位／不足與輸出範圍；不依賴呼叫端context。

手算例：long3、short2、physical+1、乘數0.01、mark100，Gross估值5 USDT、signed Net估值1 USDT、實體估值1 USDT，comparison=MATCH。這不代表Gross只有1 USDT。另有OPEN BUY2及CLOSE SELL1時，當前Gross仍5張，虛擬Gross情境上界7張；物理情境上界max(abs(1−1),abs(1+2))=3張。fixture須提供符合方向與未決flags的Lot關聯。

## 5. 輸出契約與原因

`ExposureReport`為frozen dataclass，包含scope／contract／各來源cut、observed quantities、上述可空估值與情境欄、comparison_status、delta_qty、lot_complete、各來源fresh／verified、has_unknown、unresolved_lot_count、去重筆數以及排序固定的`reasons: tuple[str,...]`。

數量與估值欄保留來源品質標記；不把observed欄名稱改為total，也不提供一個容易被當交易許可的ready／accepted布林。

資料不足原因：lot_inventory_incomplete、lot_stale、physical_unknown、physical_unverified、physical_stale、position_cut_mismatch、mark_missing、mark_stale、pending_missing、pending_incomplete、pending_stale、pending_cut_mismatch、pending_quantity_unknown、pending_effect_unknown、pending_lot_link_incomplete、future_observation。原因排序固定，可並存，不只返回第一個。

非法資料錯誤：invalid_scope、invalid_contract、invalid_decimal、invalid_integer、invalid_time_range、duplicate_lot、invalid_bot_coverage、identity_mismatch、pending_conflict、invalid_pending_direction、input_limit、decimal_range。不把無效來源資料默認為空集合。

## 6. 預計程式與測試

預計新增 `catos/lot_exposure.py`，單一入口`observe_exposure(request) -> ExposureReport`；只依賴標準庫及S1資料驗證，不讀寫SQLite、不讀時鐘、不連網。不修改risk.py、S2/S3的交易路徑，不新增schema8。另新增`tests/test_lot_exposure.py`，手造合成不可變輸入。

| 情境群 | 驗收內容 |
|---|---|
| E01–E04 | 空集合完整時為零；單多／單空；多空對沖Gross保留；closed Lot與未決責任 |
| E05–E08 | MATCH／MISMATCH精確差額；缺Bot／缺頁不可比；不同cut不可比；實體未知與未verified |
| E09–E12 | mark缺失；期限前／等於期限；未來時間；mark非tick價可估值 |
| E13–E16 | held與exchange分項；相反在途不抵銷；相同責任完全重複去重；跨來源／數量衝突拒絕 |
| E17–E20 | UNKNOWN已知量納入；UNKNOWN未知量不當0；CLOSE不預扣Gross；未分類責任只允許物理情境 |
| E21–E24 | missing／incomplete pending；在途截點不符；flag與責任缺配對；零量UNKNOWN仍保留 |
| E25–E28 | 跨scope／合約拒絕；重複Lot／Bot；無效方向／關聯；同Lot多責任拒絕 |
| E29–E32 | float／NaN／bool拒絕；派生精度與極小差額；溢位／範圍拒絕；外部低精度context不影響 |
| E33–E36 | 輸入順序不影響結果；輸入不變與重複計算一致；有界容量；既有risk.worst_notional相容數值對照 |

以上是情境群，不預先承諾方法數。標準手算預期值不得從待測函式反算。未接持久化，故不新增Windows程序死亡測試；Sol只需專屬模組及S1與直接受影響的risk算術測試，若實作範圍改變再調整驗證。

## 7. 交付順序與後續決策

本輪已交付契約與驗收規格；後續實作按此觀測範圍編寫純模組與測試，由Sol獨立執行验证與Git工作。一般內部實作選擇不重複要求授權；若加入Gross限額、帳戶層加總、真實在途適配或變更風控裁決，另提出具體政策與影響。

S4觀測通過後，主動評估最小一致快照匯出器是否是下一依賴；Gross限額不自動套3x／50%，也不因報告MATCH而接多Bot交易。是否使用risk_equity作任何新比率分母尚不在本片；本片刻意只產生張數與USDT名目估值。
