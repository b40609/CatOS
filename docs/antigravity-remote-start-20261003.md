# Antigravity 遠端重開發啟動提示詞

以下全文可貼給另一台 Antigravity。

---

你負責另一台電腦上的 catOS v1 前端重開發。使用者已把 CatOS_Astra 複製到這台電腦桌面，請以目前開啟的專案為根，核對實際路徑。使用繁體中文；直接產出可檢視前端，不只規劃。

先讀 AGENTS.md、docs/current-handoff.md、docs/frontend-remote-rebuild-20261003.md、docs/v1-local-core-handoff-20261002.md，依需要讀 docs/frontend-research-next-slice-20260930.md 與現行 home/desk/v1.js。這些入口若缺失，明示缺檔，先完成不依賴缺失契約的靜態設計；不全庫預讀。

本任務的最新分工取代舊「只能寫 theme/交接」限制：你可以在全新 frontend/redesign-v1/ 內編寫完整 HTML/CSS/JS、共用元件、SVG/canvas 圖表、mock、畫面證據與README/HANDOFF。先檢查此路徑；若已有他人工作，不刪除或覆蓋，改用新的 frontend/redesign-v1-<唯一後綴>/ 並記錄。只新增本輪路徑與 docs/frontend-remote-return-20261003.md；其餘檔案唯讀。Patch 修改。

從頭重做視覺與前端結構，保留既有交易核心。不要修改 frontend/workspace、Python、API、IPC、MCP、DB schema、AGENTS 或核心測試；不跑Git、不讀DB/憑證/.env/金鑰，不接provider、不啟動正式launcher、不操作8770/8771、Demo/Live或recovery。遠端複本不代表可以恢復其既有資料服務。

先核對 docs/frontend-transfer-baseline-20261003.json 的相對路徑/SHA-256，記錄差異，不用覆蓋檔案修復hash。它是來源轉移快照，不是runtime build或驗收。既有視覺交接及mock資料不是API事實，具體契約要查現行serializer；私有brain的截圖路徑不是可攜證據。

先做 Dashboard A/B，而非策略中心。使用者偏好舊版完整的多面板量化工作區，不接受空洞卡片或工程驗證清單。若附有舊版截圖，以其資訊層級參考；沒附則依轉移文件文字開始，不聲稱看過。
A：上方KPI，中間趨勢/配置/事件，下方風險/Bot/研究/情報。
B：大趨勢主導，右側需處理事項，下方Bot/成果。
兩版同資料/功能/token，只比較布局。作真實可點擊靜態原型並取得畫面，Dashboard完成供使用者選定，再沿同一Design System完成策略中心、機器人管理、風險、日誌、Yaozi與設定；未選定前不全面實作兩套頁面。等待選版期間可完成共用元件、資料契約與狀態展示。

深色中性灰、低圓角、清楚邊框、適中密度、可讀字級；不要滿版巨大卡片、霓虹、玻璃、過量副標。accent預設金/橘但可換，語意色獨立；CSS variables涵蓋surface/文字/邊框/accent/語意色/字體/字級/間距/圓角。不加框架、套件或遠端CDN。Tabler只作元件語言參考。技術JSON/hash/build/exit code放詳情，不主導首頁。

產品原型集中標示「示意資料」，允許完整圖表與內容；有來源才當真資料，無來源同布局空狀態，不補零。顯示時間/單位/範圍，區分保證金和曝險；不串接獨立run成帳戶權益曲線，不新增equity buffer/帳務政策。缺API的項目列提案，不能假稱已有data.risk/data.bots等舊mock欄位。

完整導覽保留，LOGO旁本機/Demo/Live模式；只有本機可執行，Demo/Live未開放。回測/優化/Yaozi開發中，不是啟動前提。不加內建AI聊天/交易想法/模型APIKey。模式切換/reload/換頁不控制Bot，資料按模式隔離，策略庫共用。

策略不可變，AI修改新版本；Bot凍結版本/hash/參數。不能改綁、刪除或撤銷信任。人工信任與建立新Bot同流程，非全版本認證，不預勾；啟停在Bot管理。通用defaults JSON，不固定quantity/period等欄位；Decimal字串。.py需製品metadata。stopped/completed不代表空倉，持倉/風險/ownership保留清楚呈現。pending保留原命令/id/build/instance，人工重送同一命令，輪詢不蓋草稿；不新增解鎖/清倉操作。P1普通Worker不是OS沙箱。MCP只有版本建立/契約/版本與成果讀取，沒有Bot控制。

只用mock adapter，不接真實控制API。新增api-adapter接入說明及DOM對照給Codex，不重做交易算術。mock操作日誌可證明展示事件；不能稱真Worker/MCP/UI核心通過。

靜態預覽僅服務新前端目錄，綁定127.0.0.1，核對空閒埠後啟動，只管理本輪PID，正常退出留證；不服務整個專案根。若缺runtime/瀏覽器工具如實報告，仍交完整原始碼，不假造渲染結果。
1440/1280/768實測渲染、鍵盤、長ID、圖表、導覽、mock匯入/信任/啟停、模式/reload/歷史；覆蓋空資料、失敗、pending、recovery、服務不可用、持倉停止。hidden/disabled不可被CSS繞過。

完成回傳僅新前端目錄、該目錄evidence及 docs/frontend-remote-return-20261003.md；不要整包專案。回傳清單含相對路徑/SHA-256、來源差異、資料/DOM/狀態/API接入對照、截圖/步驟/結果/命令/PID/退出、未涵蓋與需決策項。證據相對路徑，不依賴Antigravity私有brain。
本機Codex負責正式整合/asset-build/真實隔離自測，WorkBuddy獨驗；不自行宣稱核心PASS或commit/push。

開始執行，先交Dashboard A/B可比較成果。
