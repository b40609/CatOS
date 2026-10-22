# Antigravity 前端細節接續提示詞

下方全文可貼給原電腦 Antigravity；取代舊接續文件的「先修六大缺陷」工作指令，歷史證據保留。

---

你在原電腦接續 catOS 前端細節調整。專案 `C:/Users/user/Desktop/CatOS_Astra`，前端 `frontend/redesign-v2-return`。Codex 已直接完成本輪功能修復，現在使用者要調整按鈕位置、內容呈現、資訊密度及版面細節。保留目前約 65% 的 Vue 3＋TypeScript strict＋Vite＋Vue Router＋CSS Variables 設計，不從頭重做、不換技術棧。

先讀 AGENTS.md、docs/current-handoff.md、docs/frontend-local-repair-20261005.md，再定位當次要改的頁面／元件／樣式；不全庫預讀。接下來依使用者逐項視覺意見直接調整，一般可逆改動不等待整包確認；不自行大幅重新設計。未指定位置時先保留既有布局。

你可修改此前端的 Vue 頁面／元件／CSS 與必要呈現邏輯，使用 Patch。保留產品導覽、策略原碼／hash、人工信任、Bot 分配／啟停、歷史及模式選擇入口；允許重新排版、調整文案、整理次要技術資訊到詳情，不能以刪功能讓畫面簡潔。未知資料用 unknown／-- 或空狀態，不能填零或假裝 NORMAL。

本輪不改 adapters、contracts、持久化、命令冪等與核心。若定位到具體功能缺陷，記錄重現步驟及檔案交 Codex 修；不要為了展示自行改金融／安全邊界。模式切換、刷新與換頁不控制 Bot；Demo／Live 尚未開放。信任勾選關閉重開要重設；停止後非零／未知部位仍鎖定；歷史只能用 Run 快照，不用目前 Bot 補值；空集合刷新不能播種。

目前是 Mock 前端，固定 SAFE、16ms、帳戶／事件／Worker 等展示應清楚標示示意；可精簡或搬到適當位置，不能包裝成真核心遙測。Kill-Switch／P6 未接線，維持禁用／未接線標示，不顯示清倉成功。回測、優化、Yaozi 保留開發中入口。不加內建 AI 聊天、交易想法輸入或模型 API Key；普通 Python Worker 不稱 OS 沙箱。金額字串不轉成浮點帳務計算。

從 src 啟動 localhost 預覽，勿雙擊 HTML 或使用歷史 dist 當最新版本。Codex 修復成品為 dist-codex-repair-20261005-final；後續修改另存新 build，勿覆寫舊 build／ZIP／evidence／source-manifest。不要執行 scripts/run-test-suite-r2.js 或使用其強制終止程序方式。

預覽僅綁 127.0.0.1，先確認埠空閒、strictPort，只管理自己本輪 owner，不停止未知程序；不操作 8770／8771、核心服務、產品 DB／憑證／provider／採集、Demo／Live 交易、schema、recovery/resume、Git、其他工作目錄。不刪檔或清空目錄。

修改後跑 npm run typecheck，另存新 build；對受影響按鈕／頁面做實際 localhost 互動與截圖。需要回歸本輪功能時，執行 node scripts/verify-local-repair.js <新build目錄名>，它會建立唯一證據、量測 source/build/owner/instance 並正常退出；fixture 活躍期間不改來源。只稱實際測過的結果，不把 Mock 通過稱真 Worker／SQLite／MCP 通過。

交付精簡說明修改頁面、按鈕／內容前後差異、實際檢查與畫面、新 build／證據入口及未完成事項；另存本輪 docs 交驗，不覆寫原報告。current-handoff 由 Codex 更新。WorkBuddy 負責獨驗與 Git 核對，commit／push 另需授權。
