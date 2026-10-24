# CatOS 總盤點與問題分級

日期：2026-10-24（Asia/Taipei）。授權：使用者「同意，執行總盤點與問題分級」。工作目錄：`C:/Users/user/Desktop/CatOS_Astra`。

**結論：已達中型、多子系統專案的管理複雜度。主要問題是現況、入口、驗收證據與歷史版本未充分收斂，不能把檔案多直接解讀成大量垃圾。** 本輪列出 P1 3 項、P2 7 項、P3 2 項；未證實 P0。這不是前後端對接完成或交易安全驗收。

**基線更新**：下列原始盤點保留為同步前歷史；本機現已依使用者指示從 `2290593` fast-forward 至 `149f9fc`。受影響結論以本文末「同步後差異複核」為準。原始檔案數、靜態檢查與未執行事項不冒充同步後重新全盤點；本次另完成前端型別檢查與 build。

## 2026-10-24 整合基線追蹤

使用者另已核准「整合基線收斂」及主資料夾更名 CatOS；原始分級／數量／來源 hash 保留，不回寫為全案已驗收。詳見[本輪交付](integration-baseline-20261024.md)。

| 項目 | 本輪狀態 |
| --- | --- |
| INV-01 展示權威 | 部分改善：展示標示、P6 待確認狀態；完整 Bot／風控 HTTP 仍缺 |
| INV-02 代理同源 | 已修正並隔離自測；先驗證前端 Host／Origin，再改寫固定上游 |
| INV-03 HTTP 依賴 | requirements-http.txt，乾淨環境安裝／pip check 通過 |
| INV-04／05 優化競態 | 共用槽／恢復輪詢／結果切換已修正並瀏覽器自測 |
| INV-06 假 store 測試 | 改為實際 production store／adapter，4 項自測通過 |
| INV-07 文件漂移 | 現況入口、串接表與 README 收斂；歷史文件保留 |
| INV-08／09 歷史證據 | 未關閉：缺檔與來源漂移仍待指定角色確認，不補造 hash／PASS |
| INV-10 launcher | 加入身分／就緒／埠占用檢查；實際結果見本輪交付 |
| INV-11 舊預覽 | 部分改善：主頁移除對 preview store 的實作依賴；舊入口保留，未刪檔 |
| INV-12 可攜性 | 新證據採相對索引、現行工具移除專案絕對路徑；既有缺失證據未補造 |

本輪是開發自測，尚待 GPT-6 Sol 獨驗；未 commit／push。

## 範圍與判讀方式

- 基線時間：2026-10-23 23:58:28（UTC+08:00）；540 份來源於 2026-10-24 00:08:07 再核對，寫入本輪文件前 **零漂移**。
- 盤點 1,939 個 rg 可見檔案，約 94.21 MiB；540 份選定來源計算 SHA-256。逐檔清單、用途分類、時間與適用雜湊見 [outputs/project-inventory-20261024/manifest.json](C:/Users/user/Desktop/CatOS_Astra/outputs/project-inventory-20261024/manifest.json)；靜態檢查與補充目錄盤點見 [outputs/project-inventory-20261024/checks.json](C:/Users/user/Desktop/CatOS_Astra/outputs/project-inventory-20261024/checks.json)。
- 讀取現行入口、主要設定、API、adapter、呼叫頁面、核心邊界與指定歷史證據。**未逐行審閱所有來源，也未逐份語意判定 123 份 docs。** 中繼資料分類與來源雜湊不等於完整程式碼稽核。
- 不含其他 PC、另一個 CatOS_Yaozi 工作目錄、被忽略的完整磁碟內容或 Git 追蹤狀態。必要時定點查閱被忽略的非敏感驗收 JSON／Markdown；沒有讀產品 DB、憑證或環境變數。
- 未執行 Git、套件安裝、應用程式 import、服務啟停、HTTP、建置、測試、採集或交易。只新增本報告與盤點證據，並更新接續入口。
- P0＝已證實的立即金融／憑證／資料破壞風險；P1＝指定對接或跨機重建前須解決的缺口；P2＝具體缺陷、文件或驗證不足；P3＝需確認用途的整理候選。P1 亦包含尚未實作的必要契約，不一律是既有程式故障。
- 本報告位置行號以本輪基線為準；接續入口插入本輪摘要後，舊行號會位移。

## 規模與目錄用途

| 目錄 | 可見檔案 | MiB |
| --- | ---: | ---: |
| [root] | 9 | 0.16 |
| .vscode | 2 | 0.00 |
| catos | 98 | 1.69 |
| docs | 123 | 1.14 |
| examples | 9 | 0.02 |
| frontend | 770 | 41.87 |
| outputs | 782 | 47.56 |
| reports | 1 | 0.00 |
| scripts | 9 | 0.04 |
| tests | 119 | 1.44 |
| tools | 17 | 0.29 |
| 合計 | 1,939 | 94.21 |

來源實體行數包含空白、註解與測試，不是有效程式碼行數：

| 範圍 | 來源檔 | 實體行 |
| --- | ---: | ---: |
| catos Python | 97 | 34,631 |
| tests Python | 105 | 28,950 |
| tools Python | 17 | 7,962 |
| scripts Python | 2 | 285 |
| 主 React 的 src TS／TSX | 146 | 38,130 |

全體已盤來源有 228 份 Python；其中還包含其他目錄的 Python。靜態辨識 1,351 個 test 函式宣告，**不是本輪跑過的測試數**。540 份雜湊來源沒有 byte 完全相同的重複群組；不代表沒有近似重複、複製後修改或 ignored 舊版。

| 身分 | 目錄／檔案 | 處置原則 |
| --- | --- | --- |
| 現行後端 | [catos](C:/Users/user/Desktop/CatOS_Astra/catos) | 保留；研究、執行、帳務、風控、情報並存，不能整目錄視為單一功能 |
| 現行主前端 | [frontend/cat-os-vite](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite) | Antigravity 仍在修改；以當前來源及版本為準 |
| 仍掛載的舊介面 | [frontend/workspace](C:/Users/user/Desktop/CatOS_Astra/frontend/workspace)、[frontend/research](C:/Users/user/Desktop/CatOS_Astra/frontend/research) | 後端／研究入口仍使用，不能因「舊」就移除 |
| 啟動器仍引用的對照版 | [frontend/redesign-v2-return](C:/Users/user/Desktop/CatOS_Astra/frontend/redesign-v2-return) | 先解除現行入口依賴，再評估歸檔 |
| 參考／原型候選 | [frontend/cat-os-upstream](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-upstream)、[frontend/redesign-v1](C:/Users/user/Desktop/CatOS_Astra/frontend/redesign-v1)、[frontend/prototypes](C:/Users/user/Desktop/CatOS_Astra/frontend/prototypes)、[frontend/rebuilt-dist-local-resume-20261005](C:/Users/user/Desktop/CatOS_Astra/frontend/rebuilt-dist-local-resume-20261005) | 確認來源價值、備份與引用；本輪不判定可刪 |
| 執行／產生工具 | [scripts](C:/Users/user/Desktop/CatOS_Astra/scripts)、[tools](C:/Users/user/Desktop/CatOS_Astra/tools) | 分辨正式 launcher、可重用工具、一次性 UI 產生器及舊 Demo 工具 |
| 規格與歷史 | [docs](C:/Users/user/Desktop/CatOS_Astra/docs)、[README.md](C:/Users/user/Desktop/CatOS_Astra/README.md)、[WORK_PLAN.md](C:/Users/user/Desktop/CatOS_Astra/WORK_PLAN.md)、Antigravity 交接文件 | 保留決策沿革；現況入口需收斂 |
| 證據與產物 | [outputs](C:/Users/user/Desktop/CatOS_Astra/outputs)、[reports](C:/Users/user/Desktop/CatOS_Astra/reports) | 先判別可再生性與驗收用途，不能按體積清理 |
| 產品資料／機密 | data、credentials、secrets、.env 等排除區 | 未讀取；移轉／備份需另有明確範圍 |

實體 frontend 補充掃描排除了 node_modules、dist、快取，但包含部分 ignored 內容，因此不能與 1,939 直接加總。可見多組完整來源或快照：upstream 503 檔、redesign-v1 225 檔、redesign-v2-return 525 檔、主 React 161 檔、workspace 49 檔、research 21 檔。詳細數據記於 checks.json；這些數字不代表可刪數量。

## 現行能力與入口

| 功能 | 現行來源判讀 | 尚未確認／限制 |
| --- | --- | --- |
| React 回測 | 已直接呼叫 research version／catalog／runs／backtests／result；歷史報告有隔離 E2E | 本輪未重跑；歷史 PASS 只適用原範圍 |
| React 優化 | 已新增真實 SMA Optuna 提交與結果；另有明示展示模式 | 舊能力表已過期；本輪定位兩個非同步流程缺陷，見 INV-04／05 |
| Walk-Forward／穩定區／環境評估 | 後端 validations API／封存存在 | 主 React adapter 未見 validation 提交與 HTML report 方法 |
| 主工作區 Bot／風控／遙測 | 主要 state adapter 與多個頁面仍用 mock | 不等於後端即時帳戶；風控頁有明示示範標記 |
| 固定模板 local-sim | 有獨立 version／start／stop 路由 | 固定合成 smoke 模板，不是任意 Bot 管理服務 |
| R1 | Python／local-sim 已有歷史獨驗 PASS；17 份證據來源現況仍一致 | 未接完整 HTTP／主 React 風控；不可由 UI 本地狀態解除真實 latch |
| Yaozi 情報 | 主 React 有 /intel/today 呼叫，workspace 後端有情報路由 | 未核對另一工作目錄、產品資料、新鮮度或每張卡 DTO |
| Demo／Live | 本輪未接觸 | 任何既有模組或按鈕均不構成本輪交易授權 |

| 入口 | 靜態設定 | 注意事項 |
| --- | --- | --- |
| 8890 | React 主 Vite；research、intel、workspace 代理至 8770 | 主設定無 strictPort；只有 research 明示改寫 Origin |
| 8887 | Dashboard 獨立預覽；strictPort | 沒有同一套後端 proxy，不能當完整研究整合環境 |
| 8770 | workspace 後端，組合研究／情報／模擬控制與既有前端 | 本輪未確認實際 owner、build、instance 或服務是否運行 |
| 8771 | 後端 preview；白名單研究請求轉送固定 8770 | **不是獨立研究 writer／隔離資料根** |
| 8899 | 舊 Vue 對照版，仍由 laptop launcher 啟動 | 與接續入口列出的 8890／8887 不一致 |

來源：[frontend/cat-os-vite/vite.config.ts](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/vite.config.ts)、[frontend/cat-os-vite/vite.dashboard-preview.config.ts](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/vite.dashboard-preview.config.ts)、[catos/workspace_api.py](C:/Users/user/Desktop/CatOS_Astra/catos/workspace_api.py)、[scripts/start-laptop-dev.ps1](C:/Users/user/Desktop/CatOS_Astra/scripts/start-laptop-dev.ps1)。

## 問題清單

| 編號 | 等級 | 性質 | 問題 |
| --- | --- | --- | --- |
| INV-01 | P1 | 整合前必要缺口 | 主工作區的 Bot／風控仍由 mock 驅動，尚無完整管理 HTTP 契約 |
| INV-02 | P1 | 條件成立即阻斷的契約不一致 | workspace 代理未對齊 simulation POST 的 Origin 檢查 |
| INV-03 | P1 | 跨電腦重建缺口 | 缺少可重建 HTTP 後端的完整 Python 依賴宣告 |
| INV-04 | P2 | 已定位程式缺陷；待互動重現 | 優化頁重新整理後未恢復既有進行中任務的輪詢 |
| INV-05 | P2 | 已定位程式缺陷；待互動重現 | 優化結果缺少選取請求識別，較舊回應可覆蓋目前選取 |
| INV-06 | P2 | 驗證品質缺口 | StateAdapter 測試未載入實際 adapter，無法證明正式行為 |
| INV-07 | P2 | 文件漂移 | 能力表與接續入口混用過期狀態，入口已累積 519 行 |
| INV-08 | P2 | 證據可攜性缺口 | DCM 歷史證據有 18 處本機失效引用，另有跨機絕對連結 |
| INV-09 | P2 | 驗收證據需重新界定 | 研究封存驗收的 25 個來源有 4 個與現況不同 |
| INV-10 | P2 | 啟動與環境辨識缺陷 | 開發啟動器仍啟舊 Vue，且未以 owner／版本／就緒結果確認服務 |
| INV-11 | P3 | 歸檔候選，非可刪清單 | 多版前端／原型與一次性產生器缺少明確保留身分 |
| INV-12 | P3 | 產物與證據治理 | outputs 與被忽略的 reports 缺少統一可搬移證據索引 |

### INV-01／P1：主工作區尚無完整真實控制閉環

[frontend/cat-os-vite/src/state/stateAdapter.ts:29](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/state/stateAdapter.ts:29) 初始化由 mock 取 dashboard、Bot、策略、風控與遙測；[frontend/cat-os-vite/src/pages/risk.tsx:104](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/risk.tsx:104) 的 latch 與 re-arm 是本地 state，頁面另有「展示資料／HTTP 控制路由未掛載」標記。後端 [catos/local_sim_control_api.py:68](C:/Users/user/Desktop/CatOS_Astra/catos/local_sim_control_api.py:68) 提供的則是固定模板 local-sim。

這是**必要整合缺口，不是已證實的後端風控繞過**。不能將 mock 網址直接當後端契約，也不能把固定模板包成任意 Bot。下一步應指定一個本機模擬垂直流程及其 DTO／版本／命令回執／允許動作；前端只呈現後端權威狀態。驗收應包含重啟、失敗、UNKNOWN 與 latch 不被頁面重設的受影響案例；Demo／Live 另行處理。

### INV-02／P1：simulation 的代理與 Origin 契約不一致

[frontend/cat-os-vite/vite.config.ts:29](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/vite.config.ts:29) 已代理 /api/workspace，但沒有如 research 的固定 Origin header。[catos/local_sim_control_api.py:45](C:/Users/user/Desktop/CatOS_Astra/catos/local_sim_control_api.py:45) 要求帶入的 Origin 等於後端 request.base_url。

**靜態推導的觸發條件**：瀏覽器從 8890 以相對 URL POST simulation，保留 Origin=8890，而代理後後端入口為 8770，將落入 simulation_origin_mismatch。現行主 adapter 尚未接此操作，因此未宣稱已在使用者操作中發生。

修復須對齊指定本機代理或部署入口，保留錯誤 Origin 的拒絕與獨立 build／instance 檢查；不應取消後端防護。以全新隔離 fixture 驗證正反案例。

### INV-03／P1：Python 後端跨機重建缺少完整依賴宣告

[requirements-research.txt:1](C:/Users/user/Desktop/CatOS_Astra/requirements-research.txt:1) 僅宣告可選研究依賴 optuna／mcp；[catos/workspace_api.py:11](C:/Users/user/Desktop/CatOS_Astra/catos/workspace_api.py:11) 直接依賴 FastAPI，服務入口 [catos/workspace_api.py:209](C:/Users/user/Desktop/CatOS_Astra/catos/workspace_api.py:209) 使用 uvicorn。可見範圍未找到完整 Python 服務依賴清單或 pyproject。

這不表示目前電腦缺套件；表示乾淨環境無法只靠現行宣告可靠重建。應建立一份明確的服務／研究依賴與支援版本文件，測試獨立環境的安裝及指定入口載入。主 React 已有 package-lock，不能據此推導 Python 同樣可重現。

### INV-04／P2：優化頁重載未恢復進行中任務

[frontend/cat-os-vite/src/pages/optimization.tsx:119](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/optimization.tsx:119) 初次只取得 version／catalog／runs；選到非 complete 的 run 時，[frontend/cat-os-vite/src/pages/optimization.tsx:161](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/optimization.tsx:161) 直接返回。startPolling 只在本頁提交新任務後呼叫（基線第 265 行），而提交按鈕以快取的 active_run_id 判忙。

因此在後端仍忙時重載或進頁，沒有自動恢復該任務輪詢；需要重新載入資料才能刷新，單次完成查詢也未保證追到後端 busy slot 釋放。本輪以控制流程定位，未操作頁面。修復後用可控慢任務驗證 reload／返回／跨研究 kind 忙碌及終態後解鎖。

### INV-05／P2：優化結果存在回應覆寫競態

[frontend/cat-os-vite/src/pages/optimization.tsx:156](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/optimization.tsx:156) 切換歷史立即設定 selectedRun，再 await 結果；[frontend/cat-os-vite/src/pages/optimization.tsx:168](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/optimization.tsx:168) 回來只檢查是否仍 mounted，沒有核對目前選取的 run 或請求序號。

選 A 後選 B，若 A 較晚回覆，就可能留下「選 B、結果 A」。應加入選取／請求一致性判斷，並用兩個可控延遲結果驗證。回測頁歷史 E2E 已測過類似場景，不代表優化頁也受相同保護。

### INV-06／P2：StateAdapter 測試未驗證正式實作

[frontend/cat-os-vite/tests/state_adapter_test.mjs:5](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/tests/state_adapter_test.mjs:5) 重新定義 applyUpdate，再測自己；其餘案例檢查硬編碼字串與模式陣列。檔案未載入正式 StateAdapter／store，即使正式邏輯壞掉，也可能通過。

應將測試接到實際可觀察行為，保留必要的版本、模式與 Decimal 傳輸契約斷言。[frontend/cat-os-vite/src/lib/mock/terminal.test.ts](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/mock/terminal.test.ts) 則有 import 被測函式；本項**不代表所有前端測試都無效**。package scripts 未提供統一 test 入口，也是交接可重現性的缺口。

### INV-07／P2：現況文件已落後來源

[docs/backend-frontend-integration-map.md:12](C:/Users/user/Desktop/CatOS_Astra/docs/backend-frontend-integration-map.md:12) 仍稱優化只有展示，基線第 99 行仍稱 adapter 無 optimization 提交且結果型別固定；現行來源已加入 submitOptimization 與泛型結果。第 42 行仍說 workspace／intel 無 proxy，也已過時。

[docs/current-handoff.md](C:/Users/user/Desktop/CatOS_Astra/docs/current-handoff.md) 基線為 519 行，混合多輪「目前／下一步」、不同負責者與舊方案；其中仍有「優化待串接」。[docs/risk-period-r1-local-sim.md:3](C:/Users/user/Desktop/CatOS_Astra/docs/risk-period-r1-local-sim.md:3) 仍保留待獨驗說法，但入口已有 10 月 20 日的獨驗 PASS。

應保留歷史內容與日期，將一頁左右的現況入口連到詳細歷史，指定一份現況能力表。本輪新增盤點摘要以防誤讀，沒有重寫 Antigravity 的整份交接或把歷史結果改寫成當前驗收。

### INV-08／P2：歷史證據缺失與跨機連結失效

本機確認 DCM 證據 **18 處引用、15 個不同目標不存在**，分布於 current-handoff 與 dcm-research-plan；包括 casebook、研究報告、來源 manifest 與重播證據。[docs/current-handoff.md](C:/Users/user/Desktop/CatOS_Astra/docs/current-handoff.md) 原有文字已說明 artifacts/dcm-* 由 ignore 排除，跨機需另保留。另有指向其他使用者目錄的 file:/// 絕對連結，無法當可攜交接。

這不證明證據被刪除或不存在於其他 PC。應先尋回保存位置或標記「本機缺件」，補上安全搬移清單與校驗。Markdown 初掃另有 1 個「檔名:77」被當路徑的假陽性；實際檔案存在，已排除於 18 處計數。

### INV-09／P2：研究歷史 PASS 不能直接套用現況

本輪重算 [reports/research-validation-archive-20261019/verification.json](C:/Users/user/Desktop/CatOS_Astra/reports/research-validation-archive-20261019/verification.json) 的 25 份來源：21 份一致，4 份不同，為 research_catalog.py、research_service.py、research_worker.py、research_api.py。歷史／現況 SHA-256 完整列於 manifest。

這只證明來源變動，**不是程式故障，也不撤銷 2026-10-19 當時 PASS**。本輪定點查閱未取得能完整對應這四份現況來源的較新驗收基線；應由指定獨驗者先比對變更與其他證據，必要才重驗受影響 API／Worker／封存契約。

相對地，R1 summary 17／17 來源仍一致，可作歷史證據沿用的來源條件；本輪未重跑 197 項或額外案例，不稱重新驗收。

### INV-10／P2：啟動入口與服務身分不一致

[scripts/start-laptop-dev.ps1:16](C:/Users/user/Desktop/CatOS_Astra/scripts/start-laptop-dev.ps1:16) 啟動 React 8890＋舊 Vue 8899；未啟動目前交接所說的 8887，也未啟動必需的 8770 後端。腳本以 TCP 能連線即認定服務已存在，未核 owner／版本；npm install 後未檢查成功與否，等待後仍無條件顯示就緒與開頁。

主 Vite 無 strictPort，可能改埠，與腳本固定開 8890 亦不一致。應在指定入口中明確列出主站、預覽、後端與資料根，驗證埠占用／錯 owner／依賴失敗／服務未就緒的行為。不能停止不明 owner，也不能將指向 8770 的 8771 當測試隔離環境。

### INV-11／P3：舊版與一次性工具需先確認用途

多組前端版本、重建 dist、原型與 tools 的 UI 產生器並存；部分工具硬編碼另一個 CatOS-Frontend-Final 目錄，部分仍會寫既有 workspace。這是歸檔候選，不是安全可刪清單。

優先為每組補「現行／對照／參考／歷史／可再生」身分，追蹤 launcher／import／文件引用及保留價值。特別保留仍掛載的 workspace／research 與 launcher 還引用的 Vue。舊 Demo 採證工具保持既有停止與授權限制，檔案存在不等於可重跑。

### INV-12／P3：產物與證據缺少統一搬移索引

基線 outputs 782 檔約 47.56 MiB，占可見檔案體積約一半；reports 大部分由 ignore 排除，仍保存重要驗收材料。兩者都不能以「非來源」或「未追蹤」直接判定垃圾；本輪也沒有查 Git tracked 狀態。

建議索引最少記錄工作包、來源雜湊、命令、環境、結果、限制與保存位置，區分必要證據、可再生產物及可丟暫存，再提出保留政策。報告與附件搬機應一併校驗。

## 核心邊界抽查

靜態抽查 Worker／host／IPC、risk／risk-period、execution／journal 與研究評分路徑，未在已查範圍證實新的 P0：

- Worker 路徑保持純資料與 JSON IPC，host 有環境縮減及界線控制；沒有把普通程序隔離宣稱為惡意策略安全沙箱。
- IPC 拒絕 float／不合格資料，金融核心使用 Decimal，SQLite 金融欄位可見 TEXT／型別檢查。Optuna 只有衍生評分轉 float，屬已核准例外。
- 固定 tag、latch、UNKNOWN／額度與 R1 實作有既有來源與測試材料；本輪未將片段閱讀提升為全路徑或重啟／故障情境驗證。
- UI 中 mock 數值／隨機展示不能當成真實帳務證據；未證實它們已回流控制交易。

未執行全庫資料流證明、依賴弱點掃描、祕密歷史掃描、資料一致性或執行期安全驗證，不能宣稱「零資安／金融問題」。

## 建議處理順序與驗收門檻

1. **先完成整合基線收斂**：唯一主站與啟動方式、完整依賴宣告、當前能力表、資料來源標記、代理／版本契約，以及 INV-04／05 的優化頁一致性修正。不要在 Antigravity 並行改頁時混入大量搬檔。
2. **再交付一個本機模擬垂直流程**：選定策略版本 → 人工啟動 → 後端回執／真實狀態 → 風控與停止 → 歷史還原。只涵蓋明定範圍；R1 HTTP、金融政策及 Demo／Live 不由本盤點新增授權。
3. **補齊指定範圍驗收與可攜證據**：指定 GPT-6 Sol 對當前來源與較新證據核對，僅做必要重驗；恢復缺件或明確標示未取得。
4. **最後提出歸檔清單**：先列現行引用、備份與可再生方式，再由使用者確認刪除。不得清空資料夾、重設工作樹或整包覆蓋另一工作目錄。

本輪成果已完成靜態盤點與分級，**上述修復、搬移、清理及獨驗尚未執行**。最有價值的下一工作包是「整合基線收斂」，其具體差異與驗證由後續交辦處理。

## 本輪實際檢查與限制

| 檢查 | 結果 | 能證明什麼 |
| --- | --- | --- |
| rg 可見檔案中繼資料／用途分類 | 1,939 檔 | 固定排除範圍內的本機清單，不是全磁碟或 tracked 清單 |
| 選定來源 SHA-256 與回核 | 540 檔，文件寫入前零漂移 | 本輪靜態來源一致；本輪修改的 handoff 另列 |
| Python ast.parse | 228 檔，0 語法錯誤 | 語法解析，不是 import／執行／測試 |
| TypeScript createSourceFile | 主 src 146 檔，0 parse diagnostics | 語法解析，不是 tsc 型別檢查或 build |
| 主 src 靜態本地 import 目標 | 0 缺件 | 相對路徑與 @/ 引用的檔案存在；不涵蓋所有動態 import 或外部套件 |
| Markdown 本機連結候選查核 | 18 處真實缺件／15 目標，另排除 1 假陽性 | 路徑存在性，不證明其他 PC 或原始保存位置 |
| 歷史來源核對 | R1 17／17；研究封存 21／25 | 歷史證據的適用邊界，不是本輪測試通過 |
| 540 份雜湊來源完全重複 | 0 群組 | 不涵蓋近似重複、ignored 版本或所有產物 |

操作使用唯讀 Python／Node 標準檔案與 AST API，以及既有 TypeScript parser；沒有載入應用程式。Windows 曾拒絕一個過長的命令列，改以已新增 manifest 作為輸入後完成相同靜態檢查。一次 rg 定位使用不存在的推測檔名而失敗，相關結論改依實際存在的入口 import；不以失敗搜尋宣稱檢查通過。

交接：[docs/current-handoff.md](C:/Users/user/Desktop/CatOS_Astra/docs/current-handoff.md)。修復優先序是建議，不構成新功能、正式控制案例、獨驗、commit／push 或刪檔授權。

## 2026-10-24：同步後差異複核

### 同步與保存

- 分支 `feature/catos-react-vite` 已從 `2290593fafa93ff8858c8b3ae2aea7536b938364` fast-forward 至 `149f9fcbf2a2c5d741aa696750ab1ed62ae14460`。本機共接收 8 次提交、21 個檔案差異；使用者提供的 19 檔是最後一次提交的統計，兩者範圍不同。
- 同步前只有 `docs/current-handoff.md` 有已追蹤修改；先將交接、盤點報告與原始兩份 JSON 證據保存至 [pre-sync-backup.zip](C:/Users/user/Desktop/CatOS_Astra/outputs/frontend-sync-20261024/pre-sync-backup.zip)，逐項校驗成功，再僅 stash 交接檔並使用 `pull --ff-only`。未追蹤盤點材料留在原處，未用一般 `git stash` 假設它們已保存。
- 新建 stash `0206ef0110df18d7b77e6880202a95d35215285e` 與既有 stash 均保留。本輪以 Patch 將盤點與同步現況重新整合到入口，保留遠端歷史本文，未執行 stash pop、刪除或整包覆蓋。
- 文件更新前，比對原始 540 份來源：520 一致、20 改變、0 缺失；另有 `.vscode/tasks.json` 屬 Git 差異但不在原始 540 份選定來源內。721 份既存未追蹤檔案位元組雜湊一致、0 缺失；使用中的 `outputs/local-sim-control/control.lock` 僅保留中繼資料，未讀取鎖檔內容或操作服務。
- 這是差異複核，沒有重算整個工作目錄檔案數。後端、契約、主要 API adapter、優化頁、測試、依賴宣告與主 Vite 設定來源未因同步變動，沿用原有靜態判斷，不將歷史測試稱為本輪重驗。完整差異見 [source-comparison.json](C:/Users/user/Desktop/CatOS_Astra/outputs/frontend-sync-20261024/source-comparison.json)。

### 問題分級更新

仍維持 12 項：P1 3 項、P2 7 項、P3 2 項；其中 INV-10 部分改善，沒有任何一項可完整結案。這不表示收斂提交沒有價值，而是編譯、視覺收斂與前後端契約分屬不同驗收範圍。

| 項目 | 本次判定 |
| --- | --- |
| INV-01／P1 | 保留，補充 P6 顯示與 mock 操作風險，詳下 |
| INV-02、03／P1 | 保留；代理／Origin 與完整依賴缺口未修改，未執行 HTTP 重現 |
| INV-04、05、06／P2 | 保留；優化頁與測試來源未改，仍屬原靜態證據 |
| INV-07、08、09／P2 | 保留；入口補上本次狀態，但全體能力表、歷史缺件與指定獨驗仍未完成 |
| INV-10／P2 | 部分改善：launcher 與 VS Code task 已取消 Vue 8899；TCP 連線即視為正確服務、安裝結果未核對、逾時仍顯示就緒、主 Vite 未設定 strictPort 等問題仍在。腳本僅啟動前端，後端啟動責任仍須明定 |
| INV-11／P3 | 保留；Vue 不再由此 launcher 引用，仍須確認其他用途；preview 與主站存在共用依賴，不可直接整包移除 |
| INV-12／P3 | 保留；本輪建立同步備份與索引，尚未完成全專案保存政策 |

**INV-01 補充：主畫面尚不能代表後端保護或控制已生效。** [pages/index.tsx:63](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/index.tsx:63) 掛載 ActivityPanel 時未傳入 monitoring；[activity-panel.tsx:385](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/activity-panel.tsx:385) 無條件顯示綠色「P6 交易所端 100% 錨定」，但同檔 fixture 仍有 `p6Status: "UPDATING"`，列顯示亦固定使用綠色取整標記。Bot 表的「暫停／重啟」仍只修改本機 React state，沒有因此取得後端回執。以上是來源可證實的顯示／能力落差，不是已證實真實委託缺少保護。對接前須讓模式、保護終態與控制回執反映後端權威狀態；本輪沒有自行修改已定案視覺。

**INV-11 補充：8887 尚未從來源完整退出。** [vite.dashboard-preview.config.ts:17](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/vite.dashboard-preview.config.ts:17) 仍設定 8887，[preview/main.tsx:135](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/preview/main.tsx:135) 仍掛載 SharedInspectorSheet；主站日誌卡 [unified-incident-activity-card.tsx:2](C:/Users/user/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/unified-incident-activity-card.tsx:2) 仍 import `@/preview/preview-store`。其他 PC 已停止 8887 的回報不等於本機埠狀態，也不代表這些檔案可直接刪除；應先分離主站需要的事件資料，再確認退役範圍。

### 本機實際驗證

| 命令／範圍 | 結果 |
| --- | --- |
| `npm.cmd run typecheck`，主 React 目錄 | exit 0，實際執行 `tsc --noEmit` |
| `npm.cmd run build -- --outDir ../../outputs/frontend-sync-20261024/build --emptyOutDir false` | exit 0，2,373 模組，Vite build 5.88s；隔離輸出，未覆蓋既有 dist |
| build 警告 | JS 主 chunk 1,440.28 kB，gzip 393.81 kB，超過 Vite 500 kB 建議值；通過不代表零警告 |

使用既有 node_modules，Node v26.4.0、npm 11.17.0、Vite 6.4.4；未安裝依賴。命令、日誌、備份校驗與限制見 [verification.json](C:/Users/user/Desktop/CatOS_Astra/outputs/frontend-sync-20261024/verification.json)。本輪未修改產品程式、未啟停或核對服務 owner、未做 HTTP／UI 互動、未讀產品 DB／憑證、未執行採集或交易，亦未 commit／push；前端自測不稱獨立驗收。

建議下一成果仍是「整合基線收斂」：依目前 `149f9fc` 處理權威狀態、代理契約、依賴與啟動入口，再做限定本機模擬流程。清理與功能修正尚未啟動。

## 2026-10-24：整合基線修正後追蹤

本節更新上述同步快照的「尚未修正／未開工」狀態；原始盤點、分級與當時證據保留。整合基線已實作，指定 GPT-6 Sol 的本輪複核結果、限制及精確提交範圍統一見[獨立驗收報告](integration-baseline-acceptance-20261024.md)，不將局部修正提升為全案結案。

| 項目 | 修正後狀態 |
| --- | --- |
| INV-01／P1 | 展示來源、Bot 本地操作與 P6 待確認狀態已明示；完整 Bot／風控 HTTP 權威閉環仍未完成，保留 |
| INV-02／P1 | 固定 loopback proxy，在 Origin 改寫前驗證前端 Host／Origin；隔離實際代理驗證正反案例及 build／instance 防護，原代理不一致已修正 |
| INV-03／P1 | 新增明確 HTTP 依賴，乾淨 venv 安裝／pip check／import 為已核對的前輪證據；不等於所有跨機部署環境均已驗收 |
| INV-04、05／P2 | 優化 hook 接管恢復輪詢、跨 kind 槽位與過期回應隔離；本輪隔離 React 互動重驗通過對應案例 |
| INV-06／P2 | 測試改載入正式 store／adapter；本輪獨驗發現 REV-01 模式投影污染，修復後 8 項 store 與 10 項隔離互動重驗通過，含實際切換按鈕。REV-01 已關閉，完整驗收界線依報告，不以測試數代表全面覆蓋 |
| INV-07／P2 | 現況能力表與約一頁接續入口已更新；舊入口由原始備份完整恢復到歷史快照，避免截斷或覆寫政策歷史 |
| INV-08、09／P2 | DCM 本機缺件與研究歷史來源 hash 漂移仍保留；本輪整合測試不涵蓋歷史封存重新認證 |
| INV-10／P2 | strictPort、checkout 身分／HTML readiness、未知 owner 拒絕與安裝結果檢查已實作。8890 本輪唯讀核對合格；8770／8771 未啟動，前端 ready 不代表後端 ready |
| INV-11／P3 | 主站所需展示 store 已移至 state，舊 preview 入口保留相容轉匯出；舊版／原型未刪除，全體保留身分尚未定案 |
| INV-12／P3 | 本工作包有來源與證據索引、精確提交白名單；原始日誌與備份留本機、排除提交，全專案搬移／保存政策仍未完成 |

使用者已取消主目錄更名，維持 `CatOS_Astra`；未採用更名工具保留並排除提交。沒有刪檔、清理工作樹、讀取產品 DB／憑證、操作 Demo／Live 或新採集。stage／commit／push 不在本次授權內。

## 2026-10-24：瘦身刪除清單（核准前快照，執行結果見下節）

本輪完成引用、檔案大小與回復來源核對，尚未刪檔或建立備份。下一步優先清理，不啟動 Bot HTTP 等新功能。逐檔清單與引用命中見 [deletion-proposal.json](../outputs/cleanup-review-20261024/deletion-proposal.json)，原始掃描見 [scan.json](../outputs/cleanup-review-20261024/scan.json)。

| 組別 | 範圍 | 檔案數 | 邏輯大小 | 處理方式 |
| --- | --- | ---: | ---: | --- |
| A | 舊前端依賴與建置產物，4 個目錄 | 36,120 | 659.42 MiB | 核准後刪除，可依備份保留的來源及 lockfile 重建，不保證重現歷史產物的相同位元組 |
| B | 舊來源、原型、預覽與工具，30 個路徑 | 1,027 | 107.78 MiB | 先備份到專案外並逐檔校驗，再刪除 |
| 合計 | A 與 B 不重複計數 | 37,147 | 767.20 MiB | 實際釋放空間依檔案系統而異 |

### A：可重建目錄

- `frontend/cat-os-upstream/node_modules`
- `frontend/cat-os-upstream/.next`
- `frontend/cat-os-upstream/out`
- `frontend/redesign-v2-return/node_modules`

### B：備份後退役

- 舊前端：`frontend/cat-os-upstream`、`frontend/redesign-v1`、`frontend/redesign-v2-return`。本組計數已排除 A，包含舊來源及部分歷史驗證材料，不可假設全部已進 Git。
- 原型與舊打包：`frontend/prototypes`、`frontend/rebuilt-dist-local-resume-20261005`。
- 8887 預覽：`frontend/cat-os-vite/src/preview`、`frontend/cat-os-vite/vite.dashboard-preview.config.ts`、`frontend/cat-os-vite/tsconfig.dashboard-preview.json`、`frontend/outputs/dashboard-native-preview`。
- 視覺候選：`frontend/outputs/dashboard-concepts-20261020`。
- 舊 UI 產生／修補工具：`tools/append_css.py`、`tools/create_dashboard_prototypes.py`、`tools/create_prototype_a.py`、`tools/create_prototype_b.py`、`tools/fine_tune.py`、`tools/fix_autopack.py`、`tools/fix_visual_flaws.py`、`tools/serve_frontend_final.py`、`tools/sync_assets.py`、`tools/update_dashboard_view.py`、`tools/update_frontend.py`、`tools/update_router.py`、`tools/update_spec_test.py`、`tools/update_workspace.py`。
- 舊 Vue 打包工具：`scripts/check-zip.ps1`、`scripts/generate-hashes.js`、`scripts/generate-return-doc.js`、`scripts/package-zip.js`。這些工具仍引用舊目錄，應隨舊來源一起退役。
- 已取消的更名工具：`scripts/rename-project-to-catos.ps1`、`rename-project-to-catos.bat`。

靜態搜尋未發現正式主站對舊 preview 的外部 import；主站已改用 `state/dashboard-demo-store`。舊 UI 工具未發現正式入口呼叫；這是靜態引用判定，未執行工具。刪除前須再次核對來源未漂移，不能依本清單清理其他同名路徑。

### 明確保留

- 正式 React `frontend/cat-os-vite`，除上述退役 preview 外，保留來源、依賴與正式 dist，維持 8890 開發環境。
- `frontend/workspace`：`catos/workspace_api.py:18` 仍指定此目錄，相關頁面／資產與測試仍使用。
- `frontend/research`：`catos/research_api.py:20` 仍指定此目錄。
- `frontend/lovable-reference` 是 Git gitlink，不視為一般重複目錄。
- 後端、測試、產品資料、憑證、`CatOS_Yaozi`、未列入候選的輸出與 ZIP 證據。`outputs` 尚有後端引用的頁面，不整包清空。

本次擴大到實體舊前端來源後，找到 31 組 SHA-256 完全相同的來源，冗餘共 192,525 bytes。原盤點「540 份選定來源、0 組重複」的範圍未涵蓋全部忽略的舊前端，兩者不可直接比較。採退役舊版本整體處理，保留正式版本，不為約 188 KiB 另做跨目錄共用重構。

### 備份、提交影響與驗證

建議備份位置為 `C:/Users/user/Desktop/CatOS-cleanup-backup-20261024.zip`，目前尚未建立。B 包含未追蹤檔及已修改的 preview／3 份工具，不以 Git 或既有 ZIP 代替本輪備份。核准後先核對每個絕對路徑位於專案內，檢查 reparse point／敏感檔名，備份 B 並逐檔比對雜湊；成功才刪除 A+B，遇來源漂移或備份失敗即停止相關刪除。

若核准退役，既有 32 份提交白名單須同步修訂：3 份工具路徑修正組將由退役取代，preview 的原提交項亦需更新，不能直接照舊清單提交。本輪未修改白名單，未 stage／commit／push。

刪除後執行正式 React typecheck、隔離輸出的 build 與既有 store／adapter 測試，確認保留的後端靜態入口及資產存在。保留結果與實際刪除清單即可，不重跑全部歷史案例。本輪僅整理清單及文件，沒有重新執行程式測試；先前測試仍屬歷史證據，文件修改後不宣稱舊文件雜湊仍一致。

## 2026-10-24：核准後清理結果

使用者明確同意「先將 B 備份至專案外並校驗，再刪除 A＋B，最後驗證正式前端」。本節取代上一節待核准、未備份、未刪除及未執行測試的狀態敘述，候選範圍未擴大。

- B 共 1,027 檔已備份到 `C:/Users/user/Desktop/CatOS-cleanup-backup-20261024.zip`，壓縮檔 90,692,265 bytes；ZIP 完整性、逐檔 SHA-256、來源在備份期間及刪除前的一致性均通過。ZIP 內含 `CATOS-CLEANUP-MANIFEST.json`。
- ZIP SHA-256：`ec2b45f1c3cd3c6b1d7b79dcadb0e95e39f4c9e886811ec84ea8f6494828f0f2`。這是本輪完整 B 備份，不依賴既存 ZIP 或未追蹤檔的 Git 回復能力。
- 所有頂層絕對路徑均核對位於專案內；836 個依賴連結的目的地皆在待刪依賴目錄內，先以非遞迴方式移除連結本身，再刪除目錄，未跨連結清理其他位置。
- A＋B 的 30 個不重疊頂層路徑已移除，涵蓋 37,147 檔、804,467,737 bytes（767.20 MiB 邏輯大小）；其中 564 份為追蹤檔，其他為未追蹤或忽略內容。備份保留於專案外，因此此數字是專案內容減量，非整顆磁碟淨釋放量。
- 比對 306 份保留的後端／前端來源雜湊，0 變更、0 缺失；workspace 必要頁面與 9 個資產、research 入口仍存在。未讀產品 DB 或憑證，未操作其他工作目錄。

| 本輪驗證 | 結果 |
| --- | --- |
| `npm.cmd run typecheck` | exit 0 |
| `npm.cmd run build -- --outDir ../../outputs/cleanup-review-20261024/build --emptyOutDir false` | exit 0，2,374 modules，Vite build 4.14s；既有大型 chunk 警告仍在 |
| `npm.cmd test` | 8 passed、0 failed；Node 有 localStorage 實驗功能警告 |
| 8890 身分端點、首頁、`/src/main.tsx` | HTTP 200，checkout root 正確；未啟停服務 |
| 正式啟動入口／主站來源退役路徑搜尋 | 未找到殘留引用；未執行舊工具 |
| HEAD、兩份 stash、Git index tree | 與本輪前一致，未 stage／commit／push |

這是本輪開發自測，不宣稱已完成指定角色獨立驗收、全部 UI 互動或前後端完整串接。提交白名單已改為整合基線 28 份＋退役刪除 564 份；原 29＋3 規劃被取代。已刪的未追蹤檔不列為 Git 刪除。

逐檔備份雜湊及刪除路徑見 [execution.json](../outputs/cleanup-review-20261024/execution.json)、[deletion-result.json](../outputs/cleanup-review-20261024/deletion-result.json)；實際驗證摘要與日誌索引見 [post-cleanup-verification.json](../outputs/cleanup-review-20261024/post-cleanup-verification.json)。本輪沒有啟動新功能，後續可由指定角色核對清理差異，再依授權保存提交。

## 2026-10-24：清理差異獨立驗收與提交範圍

使用者已授權「清理差異獨立驗收，通過後提交並推送」。指定 `chatgpt-web/gpt-6-sol` 獨驗者 `01a16d63-77fc-7290-95eb-3d510de02fe9` 結論為 **PASS（限定清理範圍）**，取代上一節尚待獨驗的狀態，沒有新增清理或功能範圍。

- 重新計算 ZIP SHA-256，並逐檔核對 B 的 1,027 份 payload 大小／雜湊及內嵌 manifest，全部一致。
- A 的 4 個路徑與 B 的 30 個路徑均不存在；合併後為 30 個不重疊頂層刪除目標。37,147 檔與 767.20 MiB 為清理前清單及執行紀錄核對結果，非刪除後重新計數；836 個舊連結目的地只沿用執行紀錄，不能重驗已刪連結。
- 564 份追蹤刪除均符合備份清單與原始逐組追蹤數。306 份保留來源雜湊一致，workspace 的 12 項必要頁面／資產與 research 入口存在。掃描 248 份程式及啟動設定，退役引用 0 命中。
- 前輪 18 份相關整合程式及設定無漂移。核對清理後 typecheck、build、8 項測試原始日誌後沿用其成功證據，未重跑歷史整合測試、UI 或 HTTP；既有大型 chunk 與 Node localStorage 警告保留，不構成本輪阻擋。
- 主代理另行 fetch 核對：本機與遠端均在 `149f9fc`，無需合併。白名單為 592 個唯一路徑，完整涵蓋 581 份追蹤差異及 11 份必要新增檔；未發現清單外追蹤變更，兩份 stash 保留。採單筆提交保存整合基線及退役刪除，提交前再核對暫存區範圍與差異格式。

提交格式核對：完整 `git diff --cached --check` 僅回報完整舊入口快照第 639 行的檔尾空行。為保留前輪已核對的原文，此處不改寫快照；其餘路徑採預設檢查通過，該快照僅豁免 `blank-at-eof` 後通過，未忽略其他空白錯誤。

本機原始獨驗證據見 [acceptance.json](../outputs/cleanup-acceptance-20261024/acceptance.json)。本節與接續入口隨本次授權提交交付；備份 ZIP、原始日誌、建置輸出與其他未追蹤材料不納入 Git。實際提交識別及推送狀態以 Git 與本輪交付訊息為準。本輪 PASS 不代表完整 Bot／帳戶／交易已就緒。
