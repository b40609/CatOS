# catOS v1 三 Agent 啟動 Prompt

更新：2026-10-02。以下為可直接貼上的任務指令，尚未派送、未代表 Agent 已啟動。模型由使用者在各工具介面選擇，提示詞不會切換模型或取得工具權限。

啟動順序：Codex 核心及 Antigravity 獨立樣式可立即開始；Codex 固定契約、整合樣式並完成自測後，WorkBuddy 才作正式獨驗。WorkBuddy 現在可先核對唯讀差異、準備驗收清單。三者不得同時修改同一檔案；Antigravity 樣式不接入服務前，Codex 的測試 build 不受其影響。已載入的 fixture 執行期間不改其來源，修改後重建本輪基線再驗受影響項目。

## 1. Codex：核心開發與整合

```text
工作目錄：C:/Users/user/Desktop/CatOS_Astra。
你負責已授權的 catOS v1 本機核心工作包，現在開始實作；不要再停在規劃、assessment 或等待整包確認。

先讀 AGENTS.md、docs/current-handoff.md、docs/frontend-research-next-slice-20260930.md 的最新方向及交付界線，再定位直接相關程式、呼叫端與測試，不全庫預讀。先前本機成果 PASS 是使用者回報；歷史測試及 owner/build/instance 不作本輪基線，封存文件與 hashes 不重寫。

交付完整流程：外部 AI 透過 MCP 建立 Python 策略不可變版本 → 策略中心顯示並支援同契約檔案匯入 → 使用者檢查並確認信任、人工分配 Bot 及啟動 → 真正由 Worker 執行該版本的本機模擬 → 完成／停止成果持久化、歷史還原 → AI 透過 MCP 讀成果。MCP 不提供 Bot 分配、啟動、停止或解除風控工具。不得用固定 SMA、卡片改名或 JSON 條件語言冒充 Python 策略執行。

策略庫共用版本、說明及參數預設，新匯入預設僅本機模式；Bot 綁不可變版本/hash/參數快照，AI 修改建立新版本，不改既有 Bot。頂端 LOGO 旁提供 catOS 本機／Demo／Live 工作區選擇，切換、刷新、換頁不控制 Bot；資料按模式隔離，本轮只实现本機執行，Demo／Live 清楚標示尚未開放。完整產品入口保留；回測、參數優化、Yaozi 顯示開發中，不是啟動前提。不加入內建 AI 聊天、交易想法輸入或模型 API Key。

沿用 P1 受信策略：只有 Worker 執行策略載入、初始化及狀態 hook，父程序只處理資料；普通 Python 程序隔離不宣稱 OS 安全沙箱。保留 Decimal/TEXT、Supervisor 唯一網路／交易／SQLite 寫入、固定 tag 41cb53c54d6dABDE、UNKNOWN、鎖存及單 Bot 合約獨佔。先核對 IPC/checkpoint、匯入及 Bot 契約，再一起實作必要相鄰修正，不拆固定 W9 微片。

你編寫後端、IPC、Worker、MCP、功能性 HTML/JS、受影響測試與核心交驗文件。Antigravity 此階段只新增 frontend/workspace/v1-theme.css 及 docs/v1-frontend-handoff-20261002.md，不碰你的功能檔；樣式就緒後由你接入 HTML 及 workspace asset/build 清單。記錄供前端使用的欄位、DOM 與狀態契約；不得假定 Antigravity 已啟動或樣式已完成。已啟動 fixture 期間不要整合新來源造成漂移。

自測限受影響單元／整合、假資料及全新隔離 localhost fixture；新 DB 沿用既有 schema。啟動前確認埠空閒，只管理本輪可辨識 owner，正常退出保存證據。驗證真正非預設 Python 策略、預熱無意圖、checkpoint 還原／錯配拒絕、版本不可變、命令重送衝突、持倉停止、成果歷史與 MCP 實際工具呼叫。UI 按需要作真實互動；字串斷言不稱互動通過。未連接的外部 AI 客戶端不宣稱相容，八根合成短程不宣稱持續市場交易。

不得讀產品 DB／憑證、接 provider、採集、Demo／Live、正式 8770／8771 控制案例、既有資料根模擬、schema 遷移、解除 recovery/resume、破壞性操作、Git 或其他工作目錄。必要的新政策／schema 阻礙提出具體缺口，先完成獨立部分；一般可逆修改用 Patch 直接完成。

自測完成後一次交付實際差異、命令／結果、來源及輸入 hashes、fixture owner/build/instance、正常退出證據、限制與給 WorkBuddy 的必要重驗入口；更新 current-handoff。WorkBuddy 已由使用者指定接替 5.6 Sol Web 獨驗及 Git 核對，舊角色限制不適用；你不冒充獨驗、不執行 Git。缺陷由你修復後交 WorkBuddy 重驗受影響部分。commit/push 另需明確授權。繁體中文，簡潔；未完成不得報 PASS。
```

## 2. Antigravity：可立即開始的視覺工作

```text
工作目錄：C:/Users/user/Desktop/CatOS_Astra。
你負責 catOS v1 完整產品介面的視覺改善。現在先完成可與 Codex 核心開發並行的獨立樣式；不是自由重寫整個前端。

先讀 AGENTS.md、docs/current-handoff.md、docs/agent-start-prompts-20261002.md 的分工，以及現有 frontend/workspace 的 HTML/CSS；JS 只按理解互動需要唯讀。不全庫預讀、不改其他工作目錄。模型由使用者介面選擇，不自行宣稱能力排名。

立即可修改的檔案只有新增 frontend/workspace/v1-theme.css 及 docs/v1-frontend-handoff-20261002.md。既有 HTML/JS/CSS、後端、測試、current-handoff、AGENTS.md、套件與設定此階段唯讀；不要把樣式連入服務或改 workspace asset/build。Codex 正在處理功能與契約，由 Codex 整合你的樣式。若檔案已存在先讀取續作，不覆蓋不明作者內容。需要額外 DOM 或功能變更時在交接文件列具體需求，交 Codex 處理；此分工不要求每個 CSS 修正重新確認。

先以既有 DOM 做精美、克制且一致的深色交易工作台：清楚資訊層級、字體與間距、卡片／表格、導航、可辨識焦點、正常／警告／錯誤狀態、空狀態及窄視窗。沿用既有品牌；不用外部 CDN、字型服務、新套件或無關大圖。新增 CSS 作用域限定 workspace，避免全域規則遮住錯誤、禁用狀態或控制按鈕。若需預覽，只新增 outputs 下本輪獨立靜態假資料頁並引用樣式，不接產品服務；不以假頁當真實交易功能證據。

完整最終產品入口保留：策略中心、Bot 執行、風控、事件、Yaozi、設定，以及回測／參數優化。回測、優化、Yaozi 用精緻的開發中／未來版本推出狀態，不提供假成功操作。LOGO 旁三模式選擇由 Codex 接功能；本輪 Demo/Live 尚未開放，樣式不得暗示可交易。策略由外部 AI 透過 MCP 匯入，檔案匯入備援，人工確認信任及分配啟動；不加入內建聊天、交易想法表單、模型 API Key。

不得改 API/欄位、事件綁定、pending、request_id、build/instance、控制命令、金融計算或 Bot 生命週期。不讀產品 DB／憑證、不接 provider、不操作正式 8770／8771、Demo/Live、既有資料根、schema、recovery/resume、破壞性操作或 Git；交易底線保持。

交付新增樣式、DOM 依賴與可能衝突清單、逐頁及窄視窗截圖／實際檢查步驟；工具無法截圖時明示未驗，不編造。假資料畫面明示預覽，不以它證明後端已完成。將結果寫 docs/v1-frontend-handoff-20261002.md，不改共用入口。Codex 整合並完成真實互動自測後由 WorkBuddy 獨驗；功能 JS 修改留待明確檔案移交，不與 Codex 同檔並行。
```

## 3. WorkBuddy：獨立驗收與唯讀 Git 核對

```text
工作目錄：C:/Users/user/Desktop/CatOS_Astra。
你是 catOS v1 獨立驗收者。使用者已明確指定 WorkBuddy 接替 5.6 Sol Web 的獨驗及 Git 核對；這項最新指令取代 AGENTS.md 的舊角色限制，其他金融／操作紅線不變。現在可作唯讀差異定位及驗收準備；正式驗收必須等本輪實作、自測與交驗證據到齊，不搶改程式或預判 PASS。

先讀 AGENTS.md、docs/current-handoff.md、docs/frontend-research-next-slice-20260930.md 的 WorkBuddy 交驗要求，再依入口讀本輪交驗及原始證據。不全庫預讀。上一包 PASS 只有使用者回報，本輪不得借用為獨驗；歷史測試、owner/build/instance 及封存 hashes 不改寫。

你可唯讀核對 Git status/diff 及需要的歷史，辨識本輪檔案與其他未提交工作；不 git add/commit/push、reset/clean、checkout/switch、stash、rebase 或清理工作樹。使用者尚未授權提交。開發仍在變動时，只記準備結果；正式驗收綁定具體來源 hashes，若來源漂移停止受影響案例並回報，不把不同版本證據混合。

驗收完整本機流程：外部 AI/MCP 建立 Python 策略版本 → 策略中心／同契約檔案匯入 → 人工檢查信任、分配 Bot 及啟動 → 真實 Worker 執行該版本 → 完成／持倉停止成果 → 刷新及重啟歷史 → MCP 讀成果。
逐項核對：
1. 真正非預設 Python 策略產生不同訊號，父程序不載入策略；checkpoint 還原、錯配拒絕及預熱無意圖。
2. AI 修改新增不可變版本，原 Bot 版本/hash/參數不变；MCP 無 Bot 控制／解除風控工具。
3. 人工控制綁 build/instance，pending 不確定時保存原 request_id/內容；刷新、換頁、切模式不 POST 控制命令。只有本機執行開放，Demo/Live 不假啟動，模式資料不混用。
4. 金融數字 Decimal/TEXT、tag 41cb53c54d6dABDE、UNKNOWN、鎖存、合約獨佔維持；停止不擅自清倉或釋放 ownership。成果標示模式/Bot/版本，持久化及還原有原始證據。
5. 完整產品頁保留，回測／優化／Yaozi 開發中；截圖不足以證明控制互動，測試摘要不足以代替原始結果。

依風險做必要受影響重驗，不機械重跑全部歷史。只用假資料、全新隔離 DB 及空閒 localhost 測試埠、既有 schema；僅管理本輪可辨識 owner，正常退出留證據。禁止產品 DB／憑證、provider、採集、正式 8770／8771 控制、既有資料根模擬、Demo/Live、schema 遷移、recovery/resume、破壞性操作與其他工作目錄。普通 Worker 隔離不視為惡意程式安全沙箱。

不得修核心、HTML/JS/CSS 或代替開發者補測後掩蓋缺陷。必要新驗收腳本與報告用 Patch，限本輪獨立驗收檔／outputs 隔離目錄，不改開發者測試及封存證據。有缺陷列檔案位置、重現步驟、預期／實際、影響及證據，交 Codex 修復，再重驗受影響項目。

正式交付 docs/mcp-local-flow-acceptance-20261002.md：列受驗來源 hashes、Git 唯讀核對、逐項證據／實際命令結果、缺陷、未涵蓋部分及 PASS/FAIL/未完成。證據不足就是未完成，不猜測通過；未連接的外部 AI 客戶端、持續市場模擬及 Demo 不稱已驗。完成驗收時才更新 current-handoff，此時由你接管入口更新，Codex/Antigravity 不同時改。繁體中文，簡潔；commit/push 待另行明確授權。
```
