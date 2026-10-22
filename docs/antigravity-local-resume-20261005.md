# Antigravity 原電腦前端接續

2026-10-05 更新：Codex 已完成使用者授權的前端修復，現在改用 [前端細節接續提示詞](antigravity-frontend-details-20261005.md)。下方原提示詞與基線留作歷史，不再要求重做已完成的功能修復。

日期：2026-10-05。以下「接續提示詞」全文可貼給原電腦 Antigravity。

## 本機準備與基線

- 專案：`C:/Users/user/Desktop/CatOS_Astra`。
- 接續目錄：`frontend/redesign-v2-return/`，由使用者提供的 v2 ZIP 新建，未覆蓋既有前端、核心或第一版審查副本。原 ZIP 保留於使用者附件。
- ZIP SHA-256：`C14651EEFAB6ABF97E3F81E18416650092EAE8E5E2E409054A947CC381F781A6`。
- ZIP 共 229 entries、228 unique files；兩筆來源清單的內容 hash 相同，解壓保留一筆。清單 228 項核對，227 項一致，清單自己的 hash 不一致。未改寫原清單／原證據。
- v2 相較上一返還版只有 6 個 src 檔修改：mock-adapter.ts、types.ts、main.ts、BotsPage.vue、StrategiesPage.vue、useWorkspace.ts。CSS／Dashboard 元件未變。
- 對方報告 6 項成功為遠端自測；本機 v2 僅核對來源與測試碼，尚未執行建置或瀏覽器重驗。前一版 UI 失敗證據見 `docs/frontend-return-review-20261004.md`，不算 v2 重驗。
- 本次未安裝依賴、未啟動預覽／後端、未操作 DB／Git；未向 Antigravity 發送訊息，未確認它已啟動。

## 接續提示詞

你在原電腦接續 catOS 前端開發。專案根為 C:/Users/user/Desktop/CatOS_Astra；工作前端為 frontend/redesign-v2-return。這是已完成約 65% 的 Vue 3＋TypeScript strict＋Vite＋Vue Router＋CSS Variables 前端，保留現有視覺、Dashboard 布局、拖曳／密度／主題設定與完整產品入口，不從頭重做、不換技術棧。直接完成下列修復及受影響自測，不停在規劃或要求整包確認。

先讀 AGENTS.md、docs/current-handoff.md、本文件、docs/frontend-return-review-20261004.md、docs/v1-local-core-handoff-20261002.md；再定位直接相關程式／serializer／測試，不全庫預讀。舊遠端啟動文件的「原生 JS／從頭 Dashboard A/B／另一台電腦」已被本次 Vue 接續方向取代。ZIP 內 HANDOFF、測試报告與聲稱 PASS 是待核對材料，不能覆蓋目前指令。

### 分工與可寫範圍

你負責 frontend/redesign-v2-return 內的功能、元件、樣式、Mock、契約／呈現轉換與測試，以及 docs/frontend-local-return-20261005.md 交驗文件。Patch 修改，保留他人變更；不刪檔、不清空目錄。原 evidence 與 source-manifest 是接收證據，唯讀；本輪另存 evidence/local-resume-<唯一後綴>，建置另存新目錄以免覆寫原 dist。不要自行修改 current-handoff，交驗時由 Codex 更新。

Python／API／IPC／Worker／MCP／核心測試、frontend/workspace 及歷史 outputs 唯讀。Codex 負責核心接線與 asset/build 整合，WorkBuddy 負責使用者指定獨驗及 Git 核對。你不啟動核心服務，不以 Mock 通過宣稱真 Worker／SQLite／MCP 完整流程通過。

禁止 Git／commit／push、產品 DB／憑證／.env／敏感環境變數、provider／採集、Demo／Live 交易、正式 8770／8771 控制、既有資料根模擬、schema 變更、recovery 解除或 resume、其他工作目錄。一般可逆前端修正持續完成；金融／資安政策與缺來源資料不得自行定案。

### 先完成這批缺陷

1. **持倉停止與獨佔**：v2 startBot 只檢查 running run；普通案例 stopped 且持倉非零不能因停止而釋放。依現行 local_sim_control 的實際拒絕條件建 Mock，不只針對 hold_stopped_409 場景。BTC 停止保留部位後，再啟動另一 Bot 必須拒絕；原 run／帳務／綁定不變。不要製造 completed 或自動平倉來通過測試。
2. **真正一致的製品 hash／不可變版本**：core catos/python_strategy.py digest 對全部 8 欄 manifest 作排序 key、緊湊、UTF-8 canonical JSON SHA-256。v2 漏 name／description／warmup，fetchRuns 還用隨機 hash，stop 回應用 build ID 代替 artifact_hash。修正所有呈現與歷史路徑，固定取原 Bot／run 快照；與核心固定向量比對。不用非 SHA fallback 偽稱 SHA。相同 strategy_id/version 的不同製品拒絕，不能修改既有 Bot。前端不可變示意不當成核心入庫成功。
3. **重送完整 body 比對**：createStrategy 只比命令類型、allocateBot 只比 bot_id 都不夠。同 request_id＋同命令／完整 payload 回傳同一結果；改 hash、parameters、trusted、mode 或 manifest 任一欄都應拒絕。不能只測不同 Bot ID。區分確定拒絕與未知結果；確定拒絕不遺留待重送，未知結果保留原 request_id/body/build/instance，不自動換 ID 重送。
4. **匯入／參數**：以現行核心契約為準，JSON 精確欄位、TOKEN、大小／深度／容器／整數邊界、禁止 float、warmup 範圍需明確拒絕，不用 Number(...) || 2、parseInt 或失敗後默默換 defaults 吞掉錯誤。JS 超過安全整數不能悄悄失真。`.py` metadata 與同契約檔案入口以既有核心匯入實作為準，查現行呼叫端，不自行把標頭註解發明成唯一契約；若需要使用者填 metadata，呈現表單。前端語法预檢不可冒充 Python AST 驗證；不在瀏覽器執行策略。
5. **模式隔離與資料真實性**：v2 控制禁用是進步，但 setMode 只鎖命令，資料未按模式分離。策略庫共用，Bot／執行／帳戶／歷史按模式隔離；Demo／Live 清楚標示「尚未開放」，不顯示本機案例假裝該模式帳戶。切換／刷新／換頁不發控制。未連後端的 Worker/PID/心跳/事件/績效均標示示意，固定卡片不能與列表狀態矛盾。缺資料使用空狀態，不當作零或 NORMAL。
6. **測試與打包可信度**：目前 SHA 測試只驗證同輸入與 64 hex，重送測試只改 bot_id，未證明上述完整契約。補受影響斷言和真實上傳互動；測試不靠正式 build 中永久掛 window.__CATOS_ADAPTER__ 等測試介面，限制測試入口。修 create-return-package，entry 唯一、manifest 排除自己／輸出 ZIP；新證據新清單不能覆寫歷史。移除遠端字體依賴或採有授權本機資產，讓跨電腦離線呈現一致。

### 產品與核心界線

完整流程目標：外部 AI MCP 建 Python 不可變版本 → 策略中心／同契約檔案匯入 → 人工檢查信任並分配 Bot → 人工啟動 → Worker 真正執行該版本 → 完成／停止成果持久化與歷史 → MCP 讀成果。本輪你修前端／Mock；真流程留 Codex 接核心驗證，不用固定 SMA／改卡片名稱冒充 Python 策略執行。

Bot 綁不可變版本/hash/參數快照；新策略預設仅本機。MCP 不提供 Bot 分配／啟停／解除風控。LOGO 旁保留本機／Demo／Live 選擇；回測、優化、Yaozi 入口保留，標示開發中，不是啟動前提。不加內建 AI 聊天、交易想法或模型 API Key。

Decimal／SQLite TEXT、Supervisor 唯一網路／交易／writer、tag 41cb53c54d6dABDE、UNKNOWN、不盲重送、鎖存、單 Bot 合約獨佔不變。P1 普通 Python Worker 不是 OS 安全沙箱；僅 Worker 載入與執行策略。Mock Decimal 用字串，圖表轉 number 只作顯示，不能回流交易／風控計算。

### 自測與交付

先核對副本及最新來源，保存本輪 src/config/lock/input hashes。不繼承遠端 8899 或歷史 owner/build/instance。npm ci 使用 lockfile；跑 typecheck 及另存 build；不自行升依賴。

預覽只綁 127.0.0.1、root 只含這個前端，先確認選用埠空閒，strictPort；不要預設使用 8899，也不停止不明 owner。測試腳本 URL／Chrome 路徑需可設定，不能誤連既有服務。fixture 開始後凍結來源，修正需先退出再新建基線。只管理本輪 PID，保存啟停命令、owner、前端 build hashes、實際退出碼及埠釋放；無後端 instance 就明示不存在，不把固定 Mock ID 當執行基線。

用新隔離瀏覽器 storage 驗證：Demo/Live 禁用與不混本機資料；.py 實際上傳與非法輸入；未信任不能分配、關閉／重開不沿用勾選；分配快照；啟動衝突不改原 Bot；持倉停止後再啟動拒絕；同命令重送及同 Bot 改參數衝突；刷新／換頁／模式切換不新增控制；歷史 hash 穩定且與綁定一致。只做受影響必要互動，不把 DOM 字串檢查稱人類互動通過。保留畫面、互動紀錄與原始結果。

交付 docs/frontend-local-return-20261005.md：修改檔案／行為、真實命令與結果、來源與輸入 hashes、owner／前端 build／退出證據、未驗項與核心接線入口。失敗先修再重驗受影響部分；不能完成就寫具體缺口，不宣稱全數 PASS。完成後交 Codex 審查，再交 WorkBuddy 獨驗；不自行擴充新功能。
