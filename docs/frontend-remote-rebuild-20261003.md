# catOS 跨電腦前端重開發交接

日期：2026-10-03。使用者已將 CatOS_Astra 複製到另一台電腦桌面；本輪未連接／核對遠端電腦。

## 決定與分工

使用者要求前端轉到另一台 Antigravity 從頭開發。重做視覺與前端結構，保留既有核心及功能契約；不重寫交易底座。先前「Antigravity 只能寫 theme 與文件」改為：可在新目錄 `frontend/redesign-v1/` 完成獨立 HTML/CSS/JS、圖表、展示互動與測試；既有 `frontend/workspace/`、Python、核心測試及歷史證據唯讀。

- 遠端 Antigravity：新前端、共用元件、示意資料、靜態預覽、畫面與交接。
- 本機 Codex：契約審閱、正式 API/HTML/JS 接入、asset/build 清單及受影響隔離自測。
- WorkBuddy：使用者指定的獨驗與 Git 核對。提交／push 仍須另行授權。
- 不假定遠端任務已開始、複本一致、服務存在或設計已通過。
- 本機已授權的 UI 補證仍未執行；此次轉移不代表已完成 .py／啟停／模式／歷史互動驗證。

## 傳送與啟動

複本已存在，不需再傳整個專案。請補複製這三個新檔到遠端同相對路徑：
1. 本文件。
2. `docs/antigravity-remote-start-20261003.md`。
3. `docs/frontend-transfer-baseline-20261003.json`。

在 Antigravity 開啟遠端桌面的 CatOS_Astra，貼啟動文件全文。使用遠端實際專案根路徑，不硬編碼本機 Windows 使用者名稱。將使用者偏好的第三張舊版 Dashboard 截圖一併提供；若尚未提供，以本文件的布局說明開始，不假裝看過截圖。

遠端先重算 baseline 的檔案 SHA-256，記錄缺檔／差異，不覆蓋來源以「修好」hash。JSON 是本機目前 55 個相關檔案的轉移快照，不是全庫清單、歷史驗收 hash、workspace runtime build 或遠端驗收。差異可能來自複製時間或既有工作，先列明；可獨立完成的視覺工作繼續，涉及不一致契約的接線留給 Codex。

禁止掃描產品 DB、憑證、.env、金鑰與敏感環境變數；複製存在不代表可以讀取或使用。不要執行專案正式 launcher 或預設資料根服務。

## 產品與頁面

本機專用單人交易工作區，完整導覽：戰情總覽、策略中心、機器人管理、風險控管、系統日誌、市場情報/Yaozi、系統設定。回測、參數優化、Yaozi 保留入口與完整視覺布局，標示開發中；不是本機啟動前提。

LOGO 旁本機/Demo/Live 工作區選擇；目前只有本機可執行。切模式／刷新／換頁不控制 Bot。策略庫共用，執行／帳戶／成果按模式隔離。新版本預設僅本機。MCP 在外部 AI 使用，不加入內建聊天、交易想法輸入或模型 API Key。

## 視覺與交付次序

先 Dashboard：舊版多面板交易工作區的內容完整度為參考，不沿用最近空洞的診斷清單。A 為 KPI + 趨勢/配置/事件 + 風險/Bot/研究/情報；B 為大趨勢 + 需處理事項 + Bot/成果摘要。兩版同資料、同功能、同 token，差異在閱讀順序。Dashboard 完成供使用者選擇；選定後同一工作包延伸其餘頁面，不全面開做兩套產品。

深色中性灰、低圓角、清楚邊框、少陰影、可讀字級。數值 tabular numerals；程式/hash monospace。accent 預設金/橘但可換，並非品牌固定色；語意色獨立。CSS variables 涵蓋 surfaces、文字、邊框、accent、語意色、字體、字級、間距、圓角。沿用 HTML/CSS/JS；不新增框架、套件或遠端 CDN 依賴。參考 Tabler 元件語言，不等於已安裝該框架。

圖表有時間、單位、範圍與圖例；示意資料可充足，不用因缺後端而刪除圖表。正式模式缺來源時同布局呈現空狀態，不補零。build/instance/hash/JSON/exit code 放診斷詳情，不主導首頁。沒有接線的圖表只是設計，不承諾新增 schema 或帳務來源。

## 核心功能契約

- 外部 AI → MCP 建 Python 不可變版本 → 策略中心／同契約 JSON 或 .py 匯入 → 人工檢查並勾信任建立 Bot → 機器人管理人工啟動 → 真 Worker → 保存成果／歷史 → MCP 讀成果。
- Bot 固定版本/hash/參數快照；AI 新版本不改既有 Bot。現行不支援改綁、刪除或撤銷信任；信任隨人工建立 Bot，不是全版本認證，不預勾。
- 製品精確欄位：contract,strategy_id,version,name,description,source,defaults,warmup_bars；contract=catos.python-strategy.v1。source 是 Python 原始碼，不是「來源為 MCP」。沒有 origin/author/審查活動資料，不捏造。
- entry 含 artifact,artifact_hash,allowed_modes,created_at；Bot 含 bot_id,mode,binding,trusted,created_at。binding 固定 artifact/hash/parameters。具體 run 與 API 原始形狀讀核心交接及實際 serializer，不以舊 mock 的 data.risk/data.bots 欄位推定已存在。
- defaults 為通用有界 JSON，不是型別化參數 schema；Decimal 字串，禁止 float 參數。不可把 quantity/period/hold 固定成所有策略欄位。.py 需要 ID/版本/名稱/說明/defaults/warmup metadata。
- HTTP prefix /api/workspace/simulation；GET version,strategy-contract,strategies,bots,runs,runs/{run_id}；POST strategies,bots,bots/start,runs/{run_id}/stop。遠端本輪只 mock，不呼叫這些真實控制入口。
- MCP 僅 strategy_contract,list_strategy_versions,create_strategy_version,list_simulation_results,get_simulation_result；無 Bot 分配/啟停/解除風控/模式切換。
- states：starting,running,stopping,completed,stopped,failed,recovery_required。stopped/completed 不自動等於空倉或 ownership 釋放。服務可讀不等於風控正常；歷史快照不等於即時監控。
- pending 保存原 request_id/body/build/instance；不確定結果只允許人工重送同一命令。輪詢保留未提交表單。正式接線不得因刷新/換頁/模式切換送控制命令。
- 只有 Worker 執行策略載入、初始化與 hook；P1 普通 Python 程序隔離不是 OS 安全沙箱。只標準庫/專案模組，第三方策略套件尚未接入。
- Decimal/TEXT、Supervisor 唯一網路/交易/SQLite writer、固定 tag 41cb53c54d6dABDE、UNKNOWN、不盲重送、鎖存、單 Bot 合約獨佔保留。
- 當前本機僅八根合成 15m 短程，不是持續市場、全市場回測或 Demo/Live。不同隔離案例不可串成一條帳戶權益。
- 曝險與保證金不可混稱；曝險預算=槓桿上限×風控權益，單幣上限=曝險預算×占比。不要復活 equity buffer、把未知值當零或由前端重算風控。

## 技術結構與檢查

新目錄至少有 index.html、styles/、js/、assets/、mock/、README.md、HANDOFF.md。以同一共用 shell/token/components 支援各頁與狀態；mock 與未來 API adapter 分開。HTML/CSS/JS 原生實作，SVG/canvas 圖表可用；不要新增另一套帳本或策略執行器。mock Decimal 保留字串，圖表轉數值僅呈現，不回流提交/帳務。

靜態伺服器只以 frontend/redesign-v1 為 root，只綁 127.0.0.1，先核對空閒埠；不使用 8770/8771，不服務整個專案根。只管理本輪 PID，正常退出留證。Python 可用時可採 python -m http.server <空閒埠> --bind 127.0.0.1 --directory frontend/redesign-v1；實際命令/PID/埠記入交接。不預設另一台已安裝 Python 或瀏覽器工具。

1440、1280、768 寬度實際渲染；記錄鍵盤、導覽、圖表、詳情、mock 匯入/信任/建立/啟停、模式切換/reload、mock 歷史狀態互動。原型 mock 通過不等於真 Worker/API/MCP/UI 全流程通過。確認控制不隨 navigation/reload 自動觸發（mock command log）。需處理 pending/recovery/unavailable/空資料/錯誤/持倉停止，hidden/disabled 不可被 CSS 繞過。

現行 DOM 與控制 ID 見核心交接第「前端欄位、DOM 與狀態」。新結構可重新設計，但交付明確對照與 Codex adapter 接入位置；不要假裝改了布局即可直接替換 v1.js。

## 回傳與整合

只回傳 frontend/redesign-v1/、docs/frontend-remote-return-20261003.md、以及新目錄內 evidence/；不回傳整個專案、.git、DB、.env、venv、快取或既有 outputs。每個回傳檔列相對路徑/SHA-256；記錄遠端基線差異、瀏覽器/版本/命令/畫面/操作/退出與未涵蓋事項。引用用相對路徑，截圖存新目錄，不能依賴某台 Antigravity 私有 brain 絕對路徑。

本機先另存回傳目錄、核對清單與契約，再整合；不直接覆蓋 frontend/workspace。整合前核對本機最新來源，舊遠端複本不能覆蓋本機核心修改；已有 fixture 採證期間不得整合來源。Codex 新隔離 fixture 真實驗證 .py、人工信任/分配、啟停、模式/reload/歷史、owner/build/instance 與正常退出；再交 WorkBuddy 受影響獨驗。無真實工具證據不稱 PASS。

## 本輪實際驗證

本輪只讀相關文件與來源、建立轉移文件/55 檔 SHA-256 快照、核對文件與 hashes。未啟動遠端、服務、策略、DB 或 Git；未複製至遠端。既有前端視覺交接現在存在，但其聲稱的瀏覽器證據與欄位 mapping 未經本輪核驗，不能繼承為新設計的通過證據。
