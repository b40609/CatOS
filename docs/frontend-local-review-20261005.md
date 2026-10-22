# 原電腦 Antigravity 交付來源審查

## 當前：Codex 已修復（2026-10-05）

使用者授權直接修復。本輪型別／另存建置 exit 0，受影響開發自測 7/7；模式隔離、Run 快照／未知持倉、風控未接線宣稱及空集合刷新已修。證據與範圍見 [修復交驗](frontend-local-repair-20261005.md)，下一步 [Antigravity 視覺細節](antigravity-frontend-details-20261005.md)。仍為 Mock，非核心接線或 WorkBuddy 獨驗。下方 R2／R1 為修復前歷史判定，不作本輪現況。

## R2 核對（2026-10-05，取代下方 R1 的當前狀態）

Codex 本輪只核對來源、ZIP 與既存證據，未重跑型別／build／UI、未啟動服務、未執行 Git／DB。下方 R1 留作歷史；R2 的 8/8 是 Antigravity 自測紀錄，不是本輪 PASS 或 WorkBuddy 獨驗。

R2 ZIP `frontend/outputs/catos-frontend-local-resume-20261005-r2.zip` SHA-256 實算 `63DD715B25CAC6A173367B5CA07A5C09EA56BFFB6906A86619FFDC752566DC6A`；246 entries／246 unique，清單 246 項與 ZIP 內容、目前前端檔案逐一 SHA-256 全數吻合。兩份 dist 的 index／JS／CSS 亦納入核對，與報告 hashes 相符。這可證明交付內容一致，不能證明執行期間來源未漂移。dist 使用 module script，預覽仍需 localhost HTTP，不能保證雙擊 HTML 即可使用。

確實改善：503 同 payload 恢復重送與四路由 dispatch、Dashboard 模式 watcher 與請求 token、風控模式 watcher／按鈕鎖定、分配字典／4096 bytes／整數／信任驗證、新 Run 快照欄位，以及最新 dist 打包。仍須修正以下三組缺口，保留現有視覺，不從頭重做：

1. **模式資料隔離仍不完整。** `src/adapters/mock-adapter.ts:422` 的 `fetchAuditEvents` 未檢查模式，Demo／Live 仍回傳本機事件；`:435` 的非本機風控以 spread 沿用 `mockNormalRiskState`，留下日損 +18.42／+1.84% 等本機值。`src/pages/RiskPage.vue:107` 仍顯示固定曝險，`:164` 宣稱 OKX 保護「已部署 ACTIVE」，不隨未開放模式消失或明示未接線。改為未開放／未知狀態；固定示意內容可保留版面，但须清楚標示示意、不可稱部署成功。風控非同步載入亦需清空舊值與請求 token，避免接真 API 後舊模式回應覆蓋新模式。
2. **歷史缺快照仍以目前 Bot 補資料。** `mock-adapter.ts:551-555` 與 `:1109-1113` 仍由 `bot?.binding` 補 hash／策略／合約／週期／滑價，與「統一自 Run 快照取得、缺值 unknown」的交付說法不符。只取 Run 自身欄位或 Run binding 的參數；缺少可信快照即 unknown／--，不由目前 Bot 反推。TEST 4 只放入不存在 Bot 的 run，未覆蓋存在同 ID Bot 而歷史快照缺漏的情況。
3. **正常退出與全覆蓋證據不成立。** `scripts/run-test-suite-r2.js` 的 cleanup 使用 `taskkill /T /F`，屬強制終止；lifecycle 實記 exitCode 1，不能稱正常退出。lifecycle 只保存外層 cmd PID 19236，未保存／核對監聽 PID 46896 的父子歸屬；沒有本輪 instance。查埠函式捕捉任何錯誤即回 null，無法區分埠空閒與查詢失敗。改用可正常收尾且可辨識 owner 的 fixture、唯一證據目錄、保存監聽 owner 與實際查埠輸出、動態實算並凍結 build hashes；純前端 instance 標明 frontend fixture，不冒充後端。既有 R2 證據不要重寫。

受影響重驗即可，不要求機械重跑歷史：TEST 1 只檢查 Demo Dashboard 的未開放文字，Live 未核對 Dashboard／Bots；必須檢查舊數值、事件與曝險消失。TEST 5 僅實測 allocate 的 503，四路由聲明尚缺 create／start／stop。TEST 8 先在未勾選時關閉，再重開，沒有測「勾選後關閉／重開」的信任重設。整份腳本只有開頭清 storage 後 reload，沒有動作後刷新歷史；需補实际刷新與 Run 快照比較。fixtureBuild 是腳本手填值，非執行時 hash 量測。

目前判定：**R2 有實際修復，ZIP／來源一致；尚有模式與歷史功能缺陷，不接受完整交驗通過或正常退出宣稱。** Antigravity 修上述受影響部分，Codex 再核對並負責核心接線；WorkBuddy 維持獨驗／Git 分工。未檢視所有工作樹差異，不宣稱其他檔案未變。

## R1 歷史核對

2026-10-05，Codex 開發者來源／證據核對，非 WorkBuddy 獨驗。材料為使用者貼上的 Antigravity 回覆、本機交驗文件及實際程式。未啟動服務、未重跑 build／UI、未操作 Git／DB。保留原報告、清單及畫面。

## 已核對

- 交付 ZIP SHA-256 為 `7CD7FF0863035873F376FB0036F9C701B7B3E302D6D3159C56DEB90966ABE9FA`，與報告相符；233 entries／233 unique，來源清單 233 檔與目前來源 hash 全數一致。
- 原始自測 JSON 存在，記錄 7 passed／0 failed；這是 Antigravity 自測結果，不是本輪重驗或獨驗。
- 新增 validator、完整製品 digest、同版本衝突、完整分配 payload 比對、持倉停止阻擋與 .py 上傳流程確實有實作；不能據此稱「100% 對齊」。

## 修復前不能接核心

1. **503 保留命令卻無法重送**：`src/adapters/mock-adapter.ts` 的 allocate/start/stop 在 503 寫入 `status='failed'`；`checkIdempotency` 對任何 failed 都直接丟回舊錯誤。服務恢復後原 request_id 仍無法執行。`retryPendingCommand` 也只有 start/stop，未處理 allocate/create。修正暫態狀態／重送路由，保留同 ID、body、build、instance，補恢復後成功與改 body 拒絕案例。
2. **模式切換未更新 Dashboard／風控頁**：`src/state/useDashboard.ts` 只監聽 scenario／chartRange，沒有 currentMode；`src/pages/RiskPage.vue` 只在 mounted 讀取。Bot 頁修好不能代表全站隔離。補切換時清除舊資料並重讀，避免非同步舊模式回應覆蓋新模式；在原頁切換 Local→Demo→Live→Local 真實互動核對。
3. **歷史快照仍有假替補**：`fetchRuns`／`stopBot` 從現在 Bot 取 hash，找不到就填固定 `c70ea915…`；歷史 symbol／period 固定 BTC／15m，帳務缺值填 0／1000。RunDTO 本身缺完整 binding 快照。保存並還原當次 run 的不可變來源／參數／合約週期；缺資料明示 unknown，不用現行 Bot／固定值補造歷史。
4. **分配參數未完整驗證**：allocateBot 只呼叫 validateData，未要求 parameters 為物件、未檢查 canonical 4096 bytes；陣列及 64 個長字串可通過。已有 validateBinding 沒被使用；該 helper 也沒有完整 exact-key／digest 驗證。補與核心一致的分配入口驗證，明示 JS safe integer 的前端限制；Python AST/hooks 仍須核心確認，includes('class Strategy') 不能稱 AST 驗證。
5. **交付 ZIP 的 dist 是舊版**：ZIP 含 `dist/assets/index-B7jkDTJG.js`／`index-GjKXvyC2.css`，沒有報告本輪的 `index-Dphj84DA.js`／`index-C6mV5_wq.css`；新 build 在副本外。下次新包明確區分歷史 dist，附實際新 build 與 hash，避免使用者預覽舊成品；不覆寫原包。
6. **測試與管理證據不足**：TEST 7 取得 STOPPED／HEALTHY 後只斷言 rows 非空，未逐列比 Bot 狀態；模式測試主要涵蓋 Demo Bot 頁，沒有完整 Live／Dashboard／風控、人工信任表單、動作後刷新歷史及 503 恢復重送。固定 evidence 目錄重跑會覆寫，改唯一目錄。報告 task-364 不是可核對 OS owner PID，未列 fixture build hash／instance，也沒有正常退出原始證據；不能將查埠命令 exit 1 當服務正常退出。

## 邊界及下一步

貼上紀錄含 `git status -s`，違反本次明示禁止 Git，雖然它是唯讀且沒有 commit/push。報告也使用 `--emptyOutDir true` 並在啟動 fixture 後修改來源／重建；後續改以全新唯一 build 目錄，先收尾可辨識 owner，再凍結来源及啟動新 fixture，避免基線漂移。Codex 本輪未執行 Git，無法由貼上紀錄證明其他範圍全部未變。

Antigravity 先在既定前端範圍修上述問題，另存受影響自測／owner／來源與 build hashes／退出證據，保留既有視覺；完成後 Codex 核對並接核心，WorkBuddy 做獨驗及 Git 核對。目前判定：**有實際進展，尚不可宣稱完整交驗通過或接線就緒**。
