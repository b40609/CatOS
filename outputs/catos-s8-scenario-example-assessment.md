# S8 範圍評估：固定合成情境範例入口

後續進度：本評估已由使用者驗收並提交 `8c0000a`（`docs(lots): assess S8 fixed scenario example`）。依後續指示制定 [S8 正式規格](catos-s8-scenario-example-spec.md)，固定常數、入口、目錄生命週期及驗收契約以該文件為準；程式尚未實作。以下保留評估歷史。

狀態：2026-09-19，依使用者同意完成下一片評估；尚非正式實作規格，未編寫或執行 S8 程式。基線為 S7 commit `e00c2b5`，55/55 測試及四組 F01 渲染通過，來源為 [S7 驗收交接](../docs/lot-scenario-report-handoff.md)，本輪未重驗。

## 1. 需求與目前缺口

S7 已能將合法 capture／scenario 轉成離線 HTML，但一般使用者尚無可直接執行的固定範例。目前需自行組裝物件或引用測試 fixture；這容易混用截點、遺漏 mark metadata，或把降級資料當成完整報告。

本片目的為提供一個可重現的本機範例入口，沿用真實 S3 合成成交、S5 capture 與 S7 renderer，產生完整及降級兩份報告。不增加金融計算或來源推定；合成 physical 仍明示為固定情境值，不由 Lot Net 反推。

## 2. 既有程式核對

- `examples/report_demo.py` 為研究績效範例，採模組啟動並寫入報告，但使用可覆寫的 `write_text()`；S8 借用模組啟動形式，不沿用其保存方式，也不修改該既有範例。
- `Journal.__init__()` 會將路徑轉成實體 Path，要求 SQLite WAL／FULL；直接傳 `:memory:` 不是現有可用的記憶體 DB 模式，不為範例改造 Journal。
- S3 已有 register_binding／bind_order／apply_fill 公開流程；S5 已提供 capture_lot_snapshot；S7 的 renderer 回傳字串且自行呼叫 S6。範例應使用這些既有入口，不引用 `tests` 或私有 capture hash 函式。
- `.gitignore` 已排除 reports 產物及 SQLite／WAL／SHM；不因本片擴大忽略規則。產物仍由驗收端核對，不將合成 DB／HTML 加入程式提交。

## 3. 建議方案與替代方案

| 方案 | 成本及取捨 |
|---|---|
| 純手工 LocalLotCapture | 無 DB，但需建立內容身份、Lot／pending 一致性，容易依賴私有 hash 或重複測試 fixture；不建議 |
| 系統臨時目錄中的 Journal | 可走完整資料鏈，但多一套目錄清理與 Windows 關閉時序；本片不增加自動刪除 |
| 每次全新輸出目錄中的合成 Journal | 重用現有單一 writer，保留可追溯合成資料與報告；無需清理或開啟使用者 DB，建議採用 |

建議新增 `examples/lot_scenario_demo.py`，僅有固定情境及輸出目錄參數。預定呼叫形式如下，尚未可執行：

```text
<python> -B -m examples.lot_scenario_demo --output-dir reports/lot-scenario-run-001
```

`--output-dir` 必填，指向尚不存在的目錄；父目錄需已存在。相對路徑以呼叫端目前工作目錄解讀，成功後列出實際輸出位置。不提供 DB 輸入路徑、帳戶／市場參數、配置檔、情境編輯、force／覆寫、網頁服務或自動開啟瀏覽器。這是固定範例的命令列入口，不擴充 `catos.cli`／research_cli 為通用工具。

每次新目錄預計包含：

- `scenario.sqlite3`：本次固定合成 Journal；關閉後保留，不自動清除。
- `complete.html`：來源完整且新鮮的合成情境報告。
- `degraded.html`：相同帳本 capture 搭配明示缺價與不完整 physical 聲明的報告。

可能由 SQLite 留下的 WAL／SHM 同樣不自行刪除。新增 DB 使用既有 schema，非 schema 變更，不讀取或升級使用者既有 DB；也不形成第二條生產交易或持久化路徑。固定範例自行擔任受信本機資料建立端，不啟動 Worker 或交易派送。

## 4. 固定合成資料與報告語義

最小範例建議單帳戶代稱、local-sim、單一 SYNTHETIC-USDT-SWAP、單 Bot／單 Lot：

1. 使用固定 ContractSpec、Decimal fixture budget、合成 source／order／trade 身份及整數時間。
2. 綁定一筆 OPEN long 3 張，建立 1 張、價格 100 USDT／標的資產、完整 USDT 費用的合成成交；保留 2 張未決責任，不寫 terminal。合約及費用確切常數由正式規格列明。
3. 由 Journal.capture_lot_snapshot 取得真實 S5 capture；不複製或手改其 hash、pending 或 Lot。
4. 完整情境：明示 synthetic physical 1 張、完整性為 true；明示有效長小數 mark 與獨立 scenario_cut_id，精確綁定 capture_id。應呈現 MATCH、目前 Gross 1 張、synthetic buy 2 張與虛擬 Gross 上界 3 張。
5. 降級情境：沿用相同 capture，使用另一個明示 scenario_cut_id；physical_quantity 仍為 1 張但 physical_complete=false；mark 及全部 mark metadata 為 None。應保留目前數量、比較為 UNAVAILABLE、估值及情境上界不可用，至少顯示 physical_unverified 與 mark_missing，has_unknown=false 不表示無未決責任。

兩份報告皆使用 S7 renderer；每份由 S7 呼叫一次 S6，不額外插入 S4 計算。評估時間與所有來源有效期固定、互相相容，不讀目前時鐘作為資料時間；日後執行仍是固定歷史合成情境，不宣稱目前行情。

範例常數不代表交易政策，physical 數值不是計算結果或對帳證據。降級樣本先用既有 public evidence 支援的缺價與完整性聲明即可，不為展示新增 unmanaged Lot 寫入、帳務分類或故障注入。

## 5. 保存、失敗與可重現邊界

建議依序：解析參數→以 `mkdir(exist_ok=False)` 建立新目錄→建立固定名稱 Journal→合成資料與 capture→產生兩份 HTML 字串→關閉 Journal→以 exclusive create 保存兩檔。不得只以 exists 預檢取代原子拒絕既有目錄，也不得用可覆寫模式。

輸出目錄若為既有檔案／目錄／連結即拒絕，拒絕時不讀其中 DB 或修改任何內容。父目錄不存在、權限不足、合成資料錯誤或輸出失敗皆回非零結果，不宣稱完成。Journal 的正常與錯誤出口都要關閉；已建立的本次檔案留存供檢查，不自動刪除、覆寫或改名，重試改用新的輸出目錄。

兩份 HTML 不提供跨檔原子提交；例如第一份寫入後第二份失敗，第一份與可能未完整的第二份保留，程序明示失敗。成功訊息只在兩份均完成關閉後列出。此邊界避免新增 staging／rename／rollback 機制，符合個人本機固定範例需求。

相同版本、同一執行環境與固定資料在不同新目錄執行，兩份對應 HTML 應逐 byte 相同；輸出位置可不同，stdout 不屬於內容一致性比較。DB 二進位與副檔不要求 byte 相同；capture 身份與報告語義須相同，輸出路徑不能進入報告資料。HTML 明定 UTF-8 與一致換行，細節留正式規格。

本片不新增對惡意檔案系統競態或任意不受信任路徑的安全隔離保證；沿用個人本機受信操作範圍。以上是保存契約建議，本輪未建立或刪除任何 DB／報告目錄。

## 6. 最小驗收成本

| 情境 | 必要證據 |
|---|---|
| 固定資料鏈 | 真實新 Journal、S3 部分成交、S5 capture、S7 輸出；沒有 tests／私有 hash 依賴 |
| 完整報告 | MATCH、Gross 1、Net 1、synthetic buy 2、上界 3、來源標示及完整旗標 |
| 降級報告 | 原始數量保留、UNAVAILABLE、缺價與完整性原因、估值／上界不可用 |
| 可重現 | 不同新目錄的 complete／degraded HTML 分別逐 byte 相同 |
| 防覆寫 | 既有目錄（含空目錄）、檔案及可測的連結拒絕；既有 sentinel 內容不變，未開 Journal |
| 錯誤出口 | 建立／生成／寫出失敗時非零；Journal 關閉；保留本次已產物且不回成功 |
| 啟動隔離 | help 不建立資料、參數缺漏拒絕、不接受 DB／交易參數、不連網或讀憑證 |

Sol 執行新增範例專屬測試與 S7 必要回歸。S7 renderer 未修改時不重跑 S6／S4／S5 全套，也不重做完整四組 F01 矩陣；實際開啟新生成兩份 HTML 確認入口產物即可。有相關失敗或 renderer 改動再擴充驗證，不先宣稱任何測試通過。

預定程式範圍限一個 examples 模組、一個專屬測試檔、開發交接與 README／WORK_PLAN。無新套件、部署或常駐服務。Astra 負責規劃與編寫，使用者／Sol 執行 Python、DB／輸出驗證與 Git。

## 7. 下一交付

建議下一片依本評估制定正式常數、入口參數、成功／失敗輸出、目錄生命週期及驗收規格，再進程式實作。此評估完成不代表範例已可執行，也不授予外部採集或交易權限。

yaoI／yaozi、market、既有 S5／S6 紀錄及 S7 提交後補記各自保持獨立；本輪只新增評估及更新 README／WORK_PLAN 的入口索引，不處理其他未提交內容。
