# S10：S9 後帳務缺口與下一片評估

2026-09-21 後續：Sol 已通過 [S10 正式規格](catos-s10-fee-correction-spec.md)，使用者其後明確授權實作；Astra 已完成程式與測試編寫，待 Sol 執行驗收。規格採 schema9／event v3／S2 request v3／capture v3，Lot snapshot 沿用 v2；這是正式規格的版本設計，非本 assessment 當時已定案的版本。實作交接見 [S10 handoff](../docs/lot-fee-correction-handoff.md)；本節以下保留政策決策與更早審查沿革，不代表目前仍待實作授權。

## 最新政策決策（2026-09-21）

使用者明確同意 **S10-P1=A、S10-P2=A**，取代下文 assessment／Sol 審查當時「P1／P2 尚待定案」的狀態；下文選項比較保留為歷史依據。

- **P1=A：** 新 correction identity 的新費用若與目前有效費用數值等價，拒絕 no-change，不新增事件或推進 revision。已接受 identity＋相同 canonical payload 的重送仍優先回原收據；不能改判 no-change。
- **P2=A：** 在既有 `research._CONTEXT`（prec=50、ROUND_HALF_EVEN）中，依序計算目前 subtotal 扣舊有效 fee，再加新 fee。不得改寫為先算 new-old 再加 subtotal，也不重建全部有效費用加總。接受有限精度捨入可能使往返更正無法還原先前 subtotal 最後有效位；相同事件歷史必須依同一契約精確重放。
- 正式規格仍須鎖定每一步中間值界限、Underflow／DecimalException、整筆 rollback、API／wire／DDL／版本及驗收矩陣。政策定案不等於這些細節已完成或已驗證。
- 下一步為 Astra 起草正式規格，再交 Sol 獨立審查。本輪只記錄政策，未起草正式規格、未實作、未執行 Decimal 探針或測試；不授權既有 DB migration、交易接線或 Git 操作。

## 評估及審查時狀態（歷史）

狀態：2026-09-21，Astra 完成評估；Sol 獨立契約審查結論為**「附待決政策可進正式規格」**。現行實碼支持先評估「受管成交已知費用更正」的方向，未發現阻斷性的事實錯誤；但新 identity 同金額請求、Decimal 更新順序與後續版本編號仍未定案。使用者定案必要帳務政策後，再由 Astra 制定正式規格。本輪未授權實作、Schema 變更、既有 DB migration 或交易接線。

## Sol 契約審查（2026-09-21）

未發現阻斷缺陷。下一片維持 local-sim、單訂單單 Lot、USDT，只更正已有逐筆證據且目前已知費用的受管成交；原 KNOWN fill 與由 S9 completion 轉為 KNOWN 的成交都可作起點。UNKNOWN 仍走 S9 completion，UNVERIFIED 不接受更正；funding、非 USDT 換算、多 Lot 分配、帳戶 net PnL、風控與真實 adapter 均留後續。

正式規格須把每次更正定義為**新的不可變事件**，並至少同時帶穩定 `correction_id` 與目前有效費用來源的精確前驅引用。Sol 建議直接引用前驅事件的全域 `event_seq`：第一個前驅只能是原 KNOWN fill 或其 S9 completion，之後只能是同成交上一筆 correction。僅比對舊金額、只用 `trade_id` 或只用 Lot revision 都不足以防止 0.02→0.015→0.02 的往返分叉。

重送優先序可作為正式規格的必要契約：先以 correction identity 查已存在事件；同 identity＋同 canonical payload 永遠回原收據，即使後續已有新更正；同 identity＋不同內容為 `write_conflict`。只有 identity 不存在時，才驗證 target、目前前驅與可更正狀態。**新的 identity 若新費用與目前有效費用數值等價時如何處理仍待使用者定案**；不能因 S9 補零會建立 revision，就推導更正同值也必須建立 revision。錯誤碼名稱與 wire 精確欄位由正式規格鎖定。

Decimal 順序不能在 assessment 階段假定等價。現行 `research._CONTEXT` 為 prec=50、ROUND_HALF_EVEN，S9 亦在該 context 逐事件更新 subtotal；因此「先算差額再加」、「subtotal 先減舊再加新」與「重新加總有效費用」都必須視為不同候選契約。正式規格前需由使用者定案採用哪一種，再鎖定 context、每一步中間值界限、Underflow／DecimalException 與整筆 rollback。無論採哪一種，都不得宣稱扣回舊值可恢復無限精度真值，往返更正也不保證還原先前 subtotal 的最後有效位。本輪只做靜態核對，未執行 Decimal 探針。

schema8 DDL 已固定，若更正持久化需要新增事件表或固定 DDL，必須走**新的 Journal schema 版本**，不能原地改寫 schema8；但新版本號目前未定案，assessment 不預設一定是 schema9。現行 `LocalLotCaptureV2` 明確綁定 `capture_version=2`、`schema_version=8`，因此後續若把更正狀態送入 capture／S6／S7，必須另定 capture/hash domain 與入口版本，或把首片交付明確縮到不含下游呈現；同樣不預設版本號。

Sol 本輪只做唯讀實碼與文件交叉核對；未執行 Python、Decimal 探針、DB、migration、單元測試或全量測試。S9 的 344/344 仍是既有驗收紀錄，不因本輪文件審查而重新宣稱重驗。

## 1. 建議與依據

建議下一個實作候選為「受管成交已知費用更正」，先完成契約審查與正式規格，再另行實作。理由是 S9 已有不可變成交身份、補費收據、Lot 版本及同 writer 重放，可用較小範圍處理 known→different known；funding 還需要獨立結算身份、期間完整性與歸屬政策，直接累加 funding_paid 不能解決這些缺口。

此排序依目前 local-sim 開發邊界與驗證成本，不代表已觀察到真實費用更正事故，也不代表 funding 必須依賴費用更正。若下一個產品目標改為含資金費的期間損益，應重新評估 funding 的優先性，不把本建議當成永久順序。

S9 基線依使用者回報：實作 `b783460`、獨立驗收紀錄 `132654df560f2e5f60a490100a8d8be2c8c5349d`，344/344 通過，未 push。已閱讀 [S9 handoff](../docs/lot-fee-completion-handoff.md) 的驗收紀錄；Astra 評估階段未執行 Git 或重跑測試，Sol 本輪也未重跑 S9 測試，不宣稱重新驗證 344/344。

## 2. 現行能力與缺口

| 證據來源 | 現行行為 | 尚缺能力 |
|---|---|---|
| [S9 正式契約](catos-s9-fee-completion-spec.md) | 僅 unknown→known；known→different known 明確排除 | 費用更正的事件身份、先後關係與失效前提 |
| [lot_accounting](../catos/lot_accounting.py) | completion 小計加費用、unknown count 減一、revision 前進；保留其他 Lot 欄位 | 替換某一成交的有效費用，而非再次加上整筆新費用 |
| [lot_fills](../catos/lot_fills.py) | 原 KNOWN 成交補費拒絕；completion 同鍵不同內容衝突；按全域 seq 重放 | 允許後續更正但仍保留原 fill／completion 的不可變性 |
| [schema8](../catos/lot_schema8.py) | completion 主鍵為 order_key＋trade_id，一筆原成交最多一筆 completion | 同成交多次合法更正的順序與唯一前驅證據 |
| [S7 renderer](../catos/lot_scenario_report.py) | 費用完整性獨立呈現，保留 funding 未知文案 | funding 的涵蓋範圍、結算證據與完整性投影 |
| [research](../catos/research.py) | 研究模型接受明示 funding_events；同時間先結算舊部位再撮合 | Virtual Lot 持久化結算、遲到事件及歸屬；研究假設不能直接當作該政策 |
| [架構文件](../catOS-architecture-review.md) | 日損與權益需要帳務及估值；分類和基準重建仍有待決項 | 從 Lot 局部帳務到完整帳戶損益、權益及日損的證據閉環 |

S9 的 fee_complete 只表示受管成交集合沒有尚缺費用的成交，不是費用永不更動的保證，更不是 funding／帳戶完整性。未受管 S2 快照仍為 UNVERIFIED；不能藉更正 API 接管或補造逐筆證據。

## 3. 兩個候選的比較

| 面向 | 已知費用更正 | funding 帳務 |
|---|---|---|
| 具體失敗情境 | 成交已記 0.02，後續證據改為 0.015；S9 拒絕不同金額，現行無合法更正入口 | 持有期間有結算費用，或無法證明是否遺漏；只看成交 fee 無法形成期間損益 |
| 已有身份依據 | 原 scope／source／inst／order／trade 與不可變收據 | 尚須定義結算事件 identity，不能借用某筆成交 identity |
| 最小可行範圍 | 單筆受管成交、USDT、追加更正、保留原事件與目前 Lot head | 明示合成結算事件、明確期間與唯一可證明歸屬；無法歸屬時不強塞 Lot |
| 新政策 | 更正順序、前驅版本、無變化請求、Decimal 調整順序 | 結算時點持倉、同時事件順序、遲到／缺漏、涵蓋期間、歸屬與零費用證據 |
| 主要驗證成本 | 更正鏈、去重、失效前驅、Decimal、原子收據、跨層相容 | 上述事件完整性再加時間窗口、歷史部位、歸屬、完整性與守恆 |
| 相對成本判斷 | 中；可重用 S9，但不是改掉衝突判斷即可 | 高；不能用「已經有 funding_paid 欄位」視為完成基礎 |
| 對 net PnL 的貢獻 | 修正 fee，funding 仍未知 | 補上另一類成本；仍須定義損益期間、其他帳務及估值範圍 |

成本為設計比較，未量測工時或預估測試方法數。兩者皆維持 Decimal／SQLite TEXT、同 writer、local-sim，不接真實 adapter 或風控。

## 4. 費用更正候選：方向可接受，含待決政策

以下不涉及新政策選擇的邊界已通過 Sol 靜態契約核對；待決項仍須由使用者定案後，才交 Astra 正式規格鎖定資料型別、wire、DDL、API、錯誤碼與驗收矩陣。本文件本身不是實作規格或 Schema 變更授權。

### 4.1 原成交與更正鏈

- 目標限定既有受管成交；首次 KNOWN fill 與由 S9 completion 補為 KNOWN 的成交均可作起點。UNKNOWN 仍走 completion；UNVERIFIED 不接受更正。
- 保留原 fill、completion 及所有更正。新事件提供「更正後的絕對費用」，不讓 caller 自填要累加的差額，也不修改 qty／price／Bot／Lot 歸屬。
- 每次更正需要穩定 `correction_id`，以及對該成交目前有效費用來源的明確前驅引用；正式規格優先採前驅事件全域 `event_seq`。不能僅以 trade_id 去重，也不能只檢查舊金額或 Lot revision。
- 只檢查舊金額會漏掉 0.02→0.015→0.02 的往返：最初的 0.02 與目前的 0.02 金額相同，但版本不同。失效前驅的新更正應拒絕，不能以換 ID 繞過。
- 同 identity 同 canonical 內容先回原收據，即使該成交後續又更正也應可重送；同 identity 不同合法內容衝突。不存在該 identity 才檢查目前前驅及可更正狀態。
- **待決政策 P1：新 identity、同有效金額。** 選項 A：拒絕為 no-change，不增加事件／revision，狀態最小且避免無經濟效果的版本噪音。選項 B：接受為新的不可變更正事件並前進 revision，可保留新的外部證據到達紀錄，但會增加事件、capture 與 recovery 的版本負擔。S9 補 0 不能作為此題先例，因為 S9 補 0 會把 unknown count 減一，狀態確實改變。錯誤名稱、identity 範圍與前驅 wire 精確格式留正式規格定案。

### 4.2 更新目前 Lot，而非歷史版本

新更正只更新當下 Lot head 的費用小計與 revision／收據水位；coverage 維持 MANAGED，unknown count 不變。該 Lot 仍可能有其他 UNKNOWN 成交，所以更正一筆 KNOWN 不得把整個 Lot 標成完整。

沿 S9 檢查並保留當下 active OPEN／CLOSE 旗標，允許 terminal 後及全平 Lot 更正。qty、average entry、realized_pnl、funding、protection、order total、fill_seq、done 與 active order 都不改。已接受 CLOSE binding 繼續有效；尚未接受且引用舊 Lot revision 的意圖仍須遵守 revision_conflict。

### 4.3 Decimal 是必要契約，不能憑直覺推定

概念上需要扣除該成交舊有效費用並加入新有效費用；不能把新絕對費用完整再加一次。例如小計 0.03 含目標費用 0.02，改為 0.015 後應為 0.025，unknown count 不變。

但是 50 位 context 下，「先算新舊差額再加小計」、「小計先減舊再加新」及「重新加總全部有效費用」不保證等價。S9 小計已按事件順序捨入，也不能宣稱減回舊值就恢復無限精度真值。

**待決政策 P2：Decimal 更新順序。** 選項 A：在現行 `research._CONTEXT` 下依序做「目前 subtotal 扣舊有效 fee，再加新 fee」，只依賴 current subtotal 與目標成交目前有效 fee，實作與 recovery 較小，但往返更正可能保留有限精度捨入痕跡。選項 B：從不可變事件重建全部目前有效 fee，再依正式規格指定的固定順序加總，可減少對 current subtotal 反向調整的依賴，但 recovery 與事件狀態會更複雜，且仍須明定加總順序與中間界限。若改採「先算 new-old 再加 subtotal」也必須作為獨立契約明示，不能視為與 A 等價。所有選項都禁止 float，並須鎖定 context、Underflow／DecimalException、每步中間值驗證與失敗原子性；重放必須依同一契約得到完全相同結果。

### 4.4 儲存、重放與呈現

更正事件、canonical payload/hash、前驅、Lot revision、head 與水位須同交易提交，並與既有事件一起按全域順序重放。驗證事件→版本與版本→事件雙向唯一，拒絕缺前驅、分叉、跨成交引用、刪尾端事件及殘留版本；COMMIT 後 ACK 遺失仍以原 identity 查詢／重送。

新增事件不能悄悄改寫 schema8 的固定 DDL 或舊版 replay。若正式規格納入更正持久化，應使用明示的**新 Journal schema 版本（版本號待定）**；`PRAGMA user_version` 仍是唯一持久化 schema 版本，且不因此取得既有 schema7／8 migration 授權。既有 schema7／8 必須保持原 DDL、hash、receipt 與錯版拒絕。現行 V2 capture 精確綁定 schema8，因此新 schema 的 capture／hash domain 與 S6／S7 入口須明示升版，或明確不納入首片；不能把新 schema 偽裝成 V2，capture／payload 版本號同樣待正式規格決定。

報告須能識別使用的是更正後版本；capture identity 必須隨相關內容與版本變更。費用完整性仍與 pending／曝險品質分離，不新增帳戶 net PnL。是否需在 observation 額外呈現最後更正來源，須以最小稽核需求定案，不先加完整歷史 UI。

## 5. funding 後續的獨立前置決策

1. **事件來源與金額：** 合成情境輸入已結算金額，或按費率／mark／部位推算，是兩種不同證據；不能把推算值包裝成已結算帳務。正式規格需先選最小範圍。
2. **時間與順序：** 明示結算時間、接收／追加順序、相同時間先後與遲到規則。不能用收到事件時的剩餘部位替代結算時部位。
3. **歸屬：** 一訂單一 Lot 不代表一筆 funding 一定一 Lot。若結算時有多 Lot，或不能證明唯一歸屬，首片應拒絕 Lot 歸屬或保留未歸屬狀態；具體方式待定，不任意按當前 qty 分攤。
4. **完整性：** 定義期間及涵蓋證據；沒有事件不等於已知零，收到一筆不等於期間完整。沒有預期集合或窗口證據就不能計算有意義的「缺幾筆」。不能直接套用 fee_unknown_fill_count。
5. **符號與守恆：** 支出／收入、零、重送、衝突、後續更正與來源總額核對需定義。研究模型的 funding 算術僅供比較，不能取代持久化來源與歸屬契約。

funding 不必等待費用更正才可評估，但在以上決策完成前，不建置新的帳本、通用分配框架或把 funding_paid 的 None 改成 0。即使未來 fee 與 funding 完整，完整帳戶損益仍需額外定義外部資金流、估值與期間邊界。

## 6. 建議驗收情境與審查出口

| 類別 | 正式規格應鎖定的證據 |
|---|---|
| 身份 | 原 KNOWN／completion 起點均可；跨 scope／trade／來源與 UNVERIFIED 拒絕 |
| 去重 | 同鍵同內容、Decimal 等價重送回原收據；不同內容衝突；後續更正後仍可重送舊收據 |
| 順序 | 連續更正、兩個請求同前驅、往返同金額、遲到失效前驅；禁止鏈分叉 |
| 數值 | 正費、返佣、零、無變化、大／小數混合、界限與外部 Decimal context；明示捨入結果 |
| 狀態 | active OPEN／CLOSE、terminal、全平、其他成交缺費；費用更正不改交易狀態或 unknown count |
| 完整性 | 前驅／事件／版本雙向關聯、跨表 seq、尾端刪除、孤立與重複歸屬 |
| 原子性 | 各寫入點 rollback、真實程序 COMMIT 前／後 ACK 前終止、重開收據一致 |
| 下游 | capture 競爭與 hash、品質呈現、數量／曝險不變、仍明示 funding 未知 |
| 相容 | 舊 schema7／8、S9 completion／收據、S8 範例維持；錯版開啟在變更前拒絕 |

Sol 已完成排序理由、最小範圍、前驅／重送要求與現行版本邊界的靜態核對，未發現阻斷問題；**文件結論為「附待決政策可進正式規格」**。在 Astra 起草正式規格前，使用者仍須定案 P1「新 identity 同金額」與 P2「Decimal 更新順序」。正式規格再鎖定新 schema 的實際版本號、完整 DDL、correction wire/API、前驅查詢方式、錯誤優先序、capture／payload 版本與故障驗收。

後續順序：使用者定案 P1／P2→Astra 制定正式資料型別／新 schema 版本／API／驗收矩陣→Sol 再做正式規格獨立審查。只有後續另獲實作授權，才進程式與新建合成 DB 驗證。此文件完成不代表更正或 funding 已實作。

## 7. 本輪範圍與交接

本輪只修改本評估及 README／WORK_PLAN 的 S10 入口與審查結論；不更動程式、測試、正式 S9 規格、AGENTS、Schema 或 DB。Sol 僅對這三份 S10 文件做格式／連結、diff 與限定 staged review；不藉本輪清理其他工作樹內容。

既有 README／WORK_PLAN 的 S7 補記、S5–S7 handoff、market、yaoI／yaozi 與 S9 QA 證據維持原樣；不得因 S10 文件工作而清理或混入提交。
