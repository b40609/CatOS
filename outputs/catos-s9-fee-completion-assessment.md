# S9 Fee Completion Assessment：成交費用延遲補齊

後續：assessment 已限定提交 `bb29389`；[S9 正式規格](catos-s9-fee-completion-spec.md)已通過 Sol 文件驗收，明列型別、版本、API、重放及驗收矩陣。以下保留 assessment 與契約審查歷史，程式尚未實作。

狀態：2026-09-20，**Sol 契約審查通過，可進正式規格**。使用者確認 S8 已重驗並限定提交，`b069082` 為 S9 前穩定基線；Astra 本輪未查 Git 或重跑驗證。本文件仍僅為評估契約，**不是正式實作規格，也不授權 Schema 變更或修改 S3**。正式資料型別、schema／payload 版本、API 與驗收矩陣仍須下一片定案。

## Sol 契約審查（2026-09-20）

依現行 `lot_accounting`、S2 `lot_journal`、S3 `lot_fills` 與 S5 `lot_snapshot` 實碼交叉核對，未發現阻斷缺陷。本文提出的 unknown→known completion、terminal 後獨立分流、補 0 仍建立版本證據、舊 schema7 不靜默 nullable 化，以及 fee quality 與 pending／曝險品質分離，均與目前狀態機限制一致。

正式規格必須鎖定兩個實作細節：第一，completion 產生新 S2 revision 時，`opening_unresolved`／`closing_unresolved` 必須取該事件當下的目前 Lot head／active order 狀態，不能由被補費的歷史訂單 terminal 狀態回推；第二，新版 `known_fee_subtotal`、unknown count／coverage 狀態必須進明示版本化的 Lot payload、replay/hash 與 S5 capture identity，不能只存在 reducer 記憶體或報告層。這兩點屬正式規格要求，不阻擋本 assessment 通過。

## 1. 目標與排除範圍

目前 `SyntheticFill` 要求完整 USDT 費用。成交 qty／price 已知但 fee 尚未提供時，整筆拒絕，因此無法先反映已知部位、平均成本與價差損益。S9 的目標是將「成交事實」與「費用是否完整」分開，仍保持同一 writer、同一重放來源及同一 Lot 歸屬。

使用者已確認方向：缺費成交可更新 qty／price／average entry／realized PnL，費用必須明示 unknown；後續費用綁定原成交，terminal 後可補齊，但不重開訂單。unknown→known 屬本片，known→different known 費用更正留後續。

僅 local-sim、單訂單明確歸屬單 Lot、USDT 費用、Decimal／SQLite TEXT。不接風控、交易授權、真實 OKX adapter、funding、非 USDT 換算、多 Lot 分配、成交 qty／price 更正、累計回報轉逐筆或自動訂單操作。帳務狀態可以表達不完整，不因此產生任何可交易裁決。

## 2. 現行程式耦合與失敗情境

| 現行位置 | 已核對行為 | S9 必須處理的影響 |
|---|---|---|
| `lot_accounting.SyntheticFill`／`apply_fill` | fee 必填 Decimal；成交同時更新 fees_paid，funding 保持 None | 不能將未知費用當 0 塞入舊 reducer，也不能僅放寬 nullable |
| `lots.Lot`、`ipc_lots`、S2 lot_revisions | fees_paid 為 Decimal／TEXT NOT NULL，型別與 wire 欄位嚴格 | 費用完整性屬版本化資料契約，不能只存在記憶體或 HTML |
| S2 `_transition` | 全平後仍禁止數量／平均成本改變；內容不變而只加 revision 會拒絕 no_change | 補費 0 也要持久化 unknown 筆數變化；保留全平不復活規則 |
| S3 `_evaluate` | bind 以外先檢查 order done；fill／terminal 共用 replay | fee completion 須在 terminal 禁止新成交的檢查之外分流，不能放寬 fill 的終態禁令 |
| S3 `_append`／recovery | 數值正規化、事件 seq、request hash、S2 receipt 雙向核對 | 新補費事件須進同一序列與原子交易；不能以外部 update 修補 fees_paid |
| S5 `_fragments`／`_materialize` | 固定 schema／hash domain，capture 包含 closed Lot，terminal 訂單不進 pending | 費用責任要獨立於交易 pending；完整性欄位需進 capture identity |
| S6／S7／S8 | 驗證 capture，再做曝險觀測與報告；目前未輸出完整 net PnL | 加上費用品質資訊，不將 pending_complete 當成 fee_complete |

另有重要時序：OPEN 已 terminal、同 Lot 的 CLOSE 正在進行時，遲到的 OPEN 補費不得清掉 CLOSE 的 unresolved 旗標；不能只根據被補費訂單的 done 狀態決定目前 Lot 旗標。

## 3. 待審資料契約：金額與完整性分開

建議在版本化的帳務狀態中提供下列語義；正式欄位命名、DTO／wire 版本及 DDL 於審查後定案。

| 層次 | 必要資料 | 不變條件 |
|---|---|---|
| 每筆原始成交 | 完整 identity、qty、price、費用來源狀態 KNOWN／UNKNOWN；KNOWN 才有 USDT 金額 | 原始事件不可覆寫；UNKNOWN 是明示狀態，不是金額零 |
| 每筆有效費用 | 原始 KNOWN，或 UNKNOWN 加上唯一有效 completion | 一個成交至多一個有效費用來源；不得同時計原始費用與補費 |
| 每個受 S3 管理的 Lot | `known_fee_subtotal`、`fee_unknown_fill_count` | 小計只含已知有效費用；count 為尚未補齊的不同成交數，不是張數或訂單數 |
| 完整性 | `fee_complete = (fee_unknown_fill_count == 0)` | 僅在完整受管成交集合已驗證時可作此推導，不對缺來源資料預設 count=0 |

`known_fee_subtotal` 以 Decimal 表示，沒有任何已知費用時可為 0，但必須與 unknown count 一起解讀。正值為支出、負值為返佣、已知零為有效結果，沿用 S3 現行符號；金額不得重複扣入 realized_pnl。

**建議保留舊版 fees_paid 的原義，不在無版本標示下將其改稱不完整小計。** 新版投影明示已知小計與 count；若保留相容的 fees_paid 存取方式，只能在有完整性契約的版本中使用，禁止把 incomplete 投影偽裝成舊版 Lot／wire。舊完整費用事件與快照仍走既有語義，不對舊資料補一個任意的 nullable fee。

不受 S3 管理的 S2 Lot 沒有逐筆成交證據可重建 count；其費用品質應為「未驗證」，count 不得假設 0，亦不接受 completion。這個狀態與「已知有 N 筆未補齊」不同，正式規格需明列投影方式。

### 首次缺費成交的轉移

正常執行 S3 的身份、序號、數量、價格與 OPEN／CLOSE 校驗。合法成交依現有算術更新 opened／remaining qty、average_entry、realized_pnl；小計不變，unknown count 加 1。費用品質與該成交的 Lot 版本必須同一交易提交，不得先以 fee=0 入帳後再補註未知。

建議在既有純帳務模組內把「部位／價差更新」與「費用狀態更新」明確分開，共用相同計算，不複製第二套平均成本或 CLOSE reducer。此為後續實作方向，本輪不重構。

## 4. Completion 身份、去重與更正邊界

原成交身份沿用 `(scope, source_id, inst_id, order_id, trade_id)`；其中 order_key 已包含前四部分。建議補費的唯一業務鍵直接採 `(order_key, trade_id)`，金額與 currency 屬內容，不以新補費 ID 逃避去重。若未來需要來源訊息 ID，只能作稽核欄位，不得改變一筆成交只結算一次費用的約束。

補費 API 語義只接原成交身份、USDT fee amount；Bot／Lot 由原綁定取得，呼叫者不得指定另一個 Bot／Lot。必須存在原成交且原始 fee 狀態為 UNKNOWN，不接受只有 order binding 而尚無成交的補費，也不為孤立補費自動建立成交。

| 請求狀態 | 建議結果 |
|---|---|
| UNKNOWN，首次合法補費 | 追加 completion，小計加本筆 fee，count 減 1，產生新帳務版本 |
| 已有 completion，同 identity、同 canonical 內容 | 回原收據並標 replayed；不增 seq／revision，不重算 fee |
| 已有 completion，同 identity、不同金額或幣別 | 衝突拒絕，不能覆寫先前結果 |
| 原成交一開始就 KNOWN，呼叫 completion，即使相同金額 | 拒絕「非待補費成交」；不是重送既有 completion，不另造事件 |
| UNKNOWN 成交以相同原始內容重新送入 fill API | 回原成交收據，即使 fee 後來已補齊；不逆轉有效狀態 |
| 原 UNKNOWN fill 被重送為 KNOWN fill | fill 內容衝突；只能透過 completion 補齊 |
| 目標不存在／scope 不符／非 USDT／非法 Decimal | 拒絕且不新增事件、Lot 版本或收據 |

相同內容採既有 Decimal 數值身份：0.10 與 0.1 等價，0 與負零等價；不同 finite 金額才屬衝突。不比較原始文字表達，不接受 float、NaN 或 Infinity。receipt identity 與錯誤碼名稱留正式規格，不重用訊息 ID 猜測內容。

已補為 known 的不同金額屬於費用更正，S9 一律拒絕；不提供撤銷、反向 fee event 或覆寫原事件。批次補多筆亦不在首片 API 範圍。

## 5. Terminal 後與 Closed Lot 補費

建議對所有合法既有 terminal 狀態，允許其已存在且尚缺費用的成交補費。零成交 REJECTED 訂單沒有可補費目標，不因此製造一筆 fee。

補費僅變更已知費用小計、unknown count 及會計版本／水位；以下必須保持原值：

- 原訂單 done／terminal 收據、成交總量、fill_seq 計數及未成交餘量。
- Lot opened_qty、remaining_qty、average_entry、realized_pnl、funding_paid、side、protection 及所有身份。
- 目前 active order 身份、opening_unresolved／closing_unresolved，不受被補費的歷史訂單狀態覆寫。

全平 Lot 可補費但 remaining_qty 永遠維持 0；不重新開啟 OPEN／CLOSE 或釋放／重取 ownership。補費必須作用在目前 Lot head 的費用狀態，而非把歷史成交當時的 Lot 快照覆寫回來。

**版本影響需明示接受：** completion 即使金額為 0，也因 count 減少產生新的 Lot revision／commit_seq。已生成但尚未接受、攜帶舊 expected_revision 的 CLOSE 意圖可能遇到 revision_conflict，應重新取得快照；不為此放寬 revision 驗證。已接受的 active CLOSE binding 不重建，其後成交仍沿既有 replay 邏輯驗證。首片不另拆帳務 revision 與部位 revision，以免擴大狀態機。

## 6. 原子寫入與確定性重放

建議 completion 成為既有 S3 event stream 的新事件種類，使用同一 Journal connection／writer 與交易。新事件、費用狀態、S2 版本、head 與收據必須一起提交；不增加旁路寫庫、可變 fee cache 或第二套帳本。

replay 必須依持久化全域 seq 重建：原始 fill 的 fee 狀態、每筆唯一 completion、每 Lot 小計與 unknown count、Lot 版本、水位及訂單旗標。不能把補費依目標成交位置回填到舊 seq，不能在重啟時按另一種金額排序重算小計。Decimal 累加沿現行有界 context／正規化契約；正式規格須固定事件順序與精度，使增量與重放逐版本一致。

每筆 completion 都需有明確事件→Lot revision 收據，且受管版本反查得到唯一事件。包含補費 0 的版本，均不能因數值小計未變而省略；持久化 unknown count 變化使 S2 no_change 校驗保持有效，不應為補費全面放寬 no_change。

| 損毀／衝突情境 | 必須拒絕的依據 |
|---|---|
| 刪除 completion，留下對應 Lot 版本 | seq 缺口、孤立版本或重算狀態不一致；尾端刪除亦須由雙向版本關聯識別 |
| 重複 completion，另換訊息 ID／seq | 目標成交唯一性及 reducer unknown→known 一次性約束 |
| 補費指向不存在的成交 | 完整身份／外鍵或 replay 引用檢查，不只檢查訂單存在 |
| 改 Bot／Lot 歸屬 | 原訂單綁定與版本收據雙向核對 |
| 改小計／count／事件內容／冗餘欄位 | request hash、canonical 內容、重算結果及 S2 版本一致性 |
| 同一版本被兩個事件引用 | 事件／版本唯一性 |

繼承現有完整性保證邊界：若整個 DB 被替換成一致舊副本，或事件及全部版本證據一起回退成一致歷史，本機無外部錨點不能保證偵測。不能把「刪除補費事件必須拒絕」誇大為能偵測任意協同竄改；本片不新增外部服務。

COMMIT 後 ACK 遺失，以同一成交補費鍵查詢／重送取得原收據；COMMIT 不確定沿既有 handle 失效與重開重放處理。不盲目再新增事件，不自行認定費用未入帳。

## 7. Schema 與舊版相容：先決策，後實作

現有 schema7 的 fee_paid／fees_paid 為非空 Decimal TEXT，S3 嚴格比對表結構，S2／IPC 的 canonical request 與 S5 capture domain 均有既有身份語義。**S9 無法靠新增 nullable 欄位或一張旁表就宣稱相容。**

建議採明示版本化的 schema／帳務 payload 與投影格式，新增受管費用完整性及 completion 事件；實際 schema 版號、DDL、wire 版本與 hash domain 由正式規格定案。原始 UNKNOWN 事件可以沒有金額值，但必須有狀態與結構約束，不能僅靠 SQL NULL 推導所有意義。

| 路徑 | 評估 |
|---|---|
| 直接放寬舊 fee_paid 並把 fees_paid 當小計 | 拒絕：舊 consumer 會誤讀完整性，舊 hash／replay 有退化風險 |
| 費用旁表，Lot／capture 不版本化 | 不足：補零無版本證據，刪除事件及 capture 完整性難以雙向驗證 |
| 明示新版事件與 Lot 投影，原 writer／replay 整合 | 建議：改動較廣但費用狀態可追溯，不另建第二帳本 |

建議首個實作限全新測試／合成 DB，不自動升級使用者既有 DB。舊 schema7 的完整費用歷史保留既有讀取／重放路徑及原 hash／收據，對它提出 S9 寫入應明確拒絕，不在開啟時靜默遷移。舊 payload 不接受 UNKNOWN 或 completion，舊 capture consumer 不可默默忽略新版完整性欄位。

舊 S3 受管且原始 fee 全部完整的歷史，才可在明示相容投影下認定 unknown count=0；不能把缺欄位的任意 S2 Lot 當完整。若保留舊 replay 與新版投影的成本超出切片，需要先調整版本邊界，不能以破壞既有 schema7 作捷徑。

這是給 Sol 的相容方案建議，**尚未定案、不允許目前執行 migration**。任何後續正式 schema 變更仍需依專案規則取得明確授權；本評估不包含使用者 DB 升級工具。

## 8. S5–S8 的品質傳遞

| 模組 | 必要影響與限制 |
|---|---|
| S5 | 同一 read transaction 擷取每 Lot 費用小計／unknown count／涵蓋狀態；完整性進新版 capture hash。closed Lot 仍納入；未補費不能被 terminal 的 pending 過濾掉 |
| S6 | 校驗費用品質與 capture 的身份、一致性，原樣傳遞。費用不完整不自動變成 pending 不完整或 UNKNOWN 訂單 |
| S4 | 數量／曝險算術原則不變；缺 fee 不代表 qty、mark 或 physical 不可用。帳務品質獨立呈現，不假造數量降級 |
| S7 | 明示「費用不完整」及未補齊成交數，標示小計不是全部費用；未驗證涵蓋範圍另標示，不假造 0。保留 valid 的曝險與 MATCH，但不得解讀為帳務完整 |
| S8 | 原完整費用範例作回歸基準，數量／估值／費用品質保持正確；不為 S9 大幅擴充範例選單，缺費／補費情境先由專屬測試覆蓋 |

補齊全部 fee 不代表完整 net PnL：funding 仍未知，S9 不新增 net PnL、帳戶權益或風控輸入。如果未來提供價差 PnL 扣已知 fee 的局部值，必須另定名稱與完整性，不能在本片自行加入。

費用品質的 reason／欄位應在正式規格明列，與現有 exposure reasons 分清責任。新 capture domain 的輸入輸出相容要一併驗證，不能僅修改 HTML 顯示。

## 9. 最小驗收矩陣建議

| 群組 | 必要證據 |
|---|---|
| 首次缺費 | 多空 OPEN／CLOSE、部分成交：qty／成本／realized PnL 沿用原算術，小計不變、unknown count 加一 |
| 混合費用 | 已知／未知成交交錯，正／負／零補費，已知小計與未補筆數可重建；不是 unknown 張數 |
| 去重／衝突 | 同補費內容與 Decimal 等價重送無第二次累計；不同內容、原 KNOWN 成交補費及 fill 改內容拒絕 |
| 歷史原事件重送 | UNKNOWN fill 補齊後重送原 fill 仍回原收據，不撤銷完成狀態 |
| 終態／Lot 狀態 | terminal 後、Lot 全平後、另一 CLOSE 已 active 時補歷史 OPEN fee；所有量／成本／flags／done 不變 |
| 零費用版本 | unknown→known 0 仍產生可重放版本，count 下降，刪除該事件可被版本關聯檢出 |
| revision | 未接受的舊 expected_revision 意圖按既有規則拒絕；已接受 binding 後續成交不因費用版本錯誤失效 |
| 完整性 | 刪除 completion、重複歸屬、孤立補費、重複版本引用、小計／count 篡改均拒絕 |
| 原子與恢復 | COMMIT 前中斷、COMMIT 後 ACK 遺失、重啟與重放：同事件／receipt／版本，fee 不重計 |
| 相容 | 舊 schema7／舊 S3 完整費用歷史不被 nullable 改壞；舊 hash 與收據不變，新格式不能降版偽裝完整 |
| 品質傳遞 | S5 hash 含費用狀態、S6 不丟失、S7 明確降級；pending 完整而 fee incomplete 可同時成立，S8 完整費用基準維持 |

測試範圍預計跨純 reducer、S2／S3 儲存與恢復、S5／S6／S7 呈現及必要 S8 回歸；持久化能力實作時需有 Windows 真實中斷案例。方法數、DDL 及具體錯誤碼待正式規格，不先宣稱測試通過或要求全量回測。

## 10. Sol 契約審查出口

優先審查並回覆下列設計是否可接受，未通過前不實作：

1. **去重主鍵與已知費用界線：** completion 以原成交業務鍵唯一，原始 KNOWN 不接受 completion；UNKNOWN 原事件不可修改。
2. **狀態與版本：** 小計＋未補筆數持久化；補 0 仍有版本，terminal／closed／active CLOSE 旗標保留；接受既有 revision-conflict 行為而不拆第二套 revision。
3. **相容策略：** 新版契約與新建合成 DB 為首片，舊 schema7 不自動升級，保留舊 replay／hash／收據；不以 nullable 改壞舊格式。
4. **品質傳遞：** S2 非受管資料為未驗證，S5–S8 明確區分 fee incomplete 與交易 pending／曝險品質；funding 未知仍不宣稱完整 net PnL。
5. **完整性保證：** 單獨刪除補費事件可拒絕，完整一致舊副本回退仍無外部證明；不為此增加外部服務。

通過後，Astra 才制定正式資料型別、schema／payload 版本、reducer／重放順序、API／錯誤碼及測試矩陣；實作與 migration 授權另依正式規格確認。Sol 負責契約審查、後續驗證與 Git。

本輪沒有程式、Schema、AGENTS 或 DB 變更；沒有 Python／測試／Git 操作。market、yaoI／yaozi 及 S5–S8 既有未提交紀錄維持獨立。本文件與 README／WORK_PLAN 新索引屬 S9 文件交付，驗收端提交時需排除兩檔既有補記。
