# F1 專屬工作台：實作與本機驗證交接

## Git 收尾狀態（2026-09-30 18:07）

使用者已授權「F1 Git 收尾 → 等 R4 PASS 並收尾」。本次以 F1 獨立實作提交保存 workspace API／snapshot、frontend/workspace、專屬 tests、四份 F1 文件與 current-handoff；不混 R4、不 stage outputs／DB／log、不 push、不切正式8770。Gemini 布局引擎保留 8 處原有行尾空白，不為排版重寫程式／改變服務 build。

既有驗收對話「依 F1 清單驗收並保留 R4」（`01a0f18e-ff90-7751-8624-15b9fde8f4dd`）仍 active，正在補 #6 窄版成交表水平自捲；尚無正式完成結果。下方「獨立驗收尚未執行」取代為「已進行、待最後結果」，其餘自驗數字維持歷史來源。本次提交不是獨立驗收 PASS，不重跑網頁／專屬 tests；收到原驗收結果後再據實封存。

首頁比較截圖與 `/workspace/design` 樣稿保留於本機 outputs，不納入提交；乾淨 checkout 缺少這些參考檔會回 404，六頁程式資產包含於提交。R4 18:07 心跳29/32、11 fills、0 anomalies、running；只讀 status／manifest 與 Get-Process，未開DB、改 frozen source 或重啟任何服務。

## 最新交付：首頁接受後展開六頁（2026-09-30）

使用者已確認「首頁方向 OK，展開其他頁」。本輪完成六頁，保留 Gemini 整體畫面、密度、導航與工作台操作；首頁比較與舊版保留。使用者最新要求停止大量點擊網頁測試，完成後提供驗收方法；已停止額外瀏覽器測試。下方 15:46／12:55 是歷史，不再表示其他頁未獲授權。

### 開啟與功能

直接開 [策略中心](http://127.0.0.1:8771/workspace/research)，使用左側導航；不需要 file URL 或安裝工具。

| 頁面 | 已接入功能 | 缺口 |
| --- | --- | --- |
| 策略中心 research | 核可策略、固定合成資料、回測／Optuna、歷史／結果／成交／報告、候選帶入草稿 | 無任意策略或外部資料匯入 |
| 機器人管理 execution | R4 與 smoke 記錄、決策前目標／部位／裁決、成交後部位、近期事件 | Bot 啟停未接入 |
| 風險控管 risk | R4 已記錄異常；既定曝險／日損／災難停損政策詳情 | 有效帳戶、日損、latch、可增倉未提供，顯示 — |
| 系統日誌 events | 最新有界事件、類型／文字篩選、完整事件詳情、訊號／成交分開 | 不冒充全帳戶稽核 |
| 市場情報 yaozi | 既有情報服務接入狀態與生命週期說明 | 目前 market_intel_not_found；不造資料 |
| 系統設定 settings | 服務狀態、版本詳情、瀏覽器密度／布局、七工具契約說明 | Agent client 連線未提供；Demo／Live 未接入 |

新增 desk.html／desk.css／desk.js，共用本地布局引擎；每頁、預設、desktop／compact 分別保存，不影響首頁或策略生命週期。首頁導航改接六頁。API 僅新增六個固定 GET 頁面／兩個資產，未知頁 404、非研究 POST 拒絕；不建第二 writer。研究 POST 仍走原 8770，沿用 build／origin／大小與有界提交契約。畫面不重算帳務，完整 Decimal 保留文字。

### 已實際驗證與修正

- `python -B -m unittest tests.test_workspace_f1`：**22/22，1.068 秒**；新增六頁路由、CSP、localhost、未知頁、非法 POST、資產與沒有啟動第二 writer 的檢查。
- `node --check` desk.js／home.js／home-layout.js 通過。未跑全套、全市場回測或 Git 檢查。
- UI 新建合成回測 `6a7956b291bf4205b2d8293ef9963b02`：period=4／warmup=8，net_pnl=`-0.99090140`、final_equity=`999.00909860`、33 筆成交，complete。
- UI 新建搜尋 `9076af29fda2417f92015bb946486bc1`：period 2–8、step=1、3 trials、seed=42、warmup=8，complete；候選 4／8／7。帶入 7 只改新草稿，原搜尋與保存結果維持固定。
- 已檢查草稿預熱不足提示、R4／smoke 切換、訊號 seq=10／26 完整詳情、異常篩選為 0、legal_reduction 搜尋、事件更新維持選定 line_number、缺風控／情報與版本詳情。
- 設定密度 reload 保存、預設切換、隱藏後 reload／元件庫加回、放大／Escape 已操作。1440 桌面研究／風控截圖保存；390 窄視窗僅有限檢查，沒有完成全部頁載入後／所有布局的響應式驗收，也未做最後全頁 console 重驗。
- 修正 backtest 結果判型（kind 屬 run）、事件完整行選取、刷新後事件選取及最重要的 **固定 R4 狀態與選定歷史記錄分離**；歷史 smoke 完成不會使頂部 R4 顯示完成。
- 證據：[研究頁](../outputs/frontend-design-review-20260930/desk-research.png)／[風控頁](../outputs/frontend-design-review-20260930/desk-risk.png)。這是本輪自驗，指定 5.6 Sol (Web) 獨立驗收尚未執行。

### 人工驗收清單（建議 10 分鐘）

先在一般桌面寬度開啟上述策略中心；等資料載入。只需以下少量操作，無須每個按鈕反覆點擊。

1. **研究草稿與結果**：開「研究設定」，均線週期=4、委託張數=2、預熱=8，其他維持初始權益1000／費率0.0005／滑價2；儲存後，舊結果不改。按「執行回測」等待完成，應顯示上述 -0.99090140／999.00909860，並新增一筆歷史。開一次「完整報告」，確認內容屬該 run；此連結尚未在本輪瀏覽器重驗。
2. **參數搜尋**：搜尋下限2、上限8、步長1、試驗次數3、seed42、預熱8；按「參數搜尋」。候選「帶入草稿」只改草稿，保存搜尋及舊回測不變；不必再執行候選回測。
3. **R4 與事件**：機器人管理切換 smoke 與八小時 R4，面板隨記錄切換；頂部仍追蹤八小時 run。日誌用「訊號」或 legal_reduction 篩選，開一筆詳情；序號、目標、決策前部位與成交後部位應能區分。0 anomalies 只限該 run。
4. **缺資料**：風控帳戶權益／日損／latch 應為 —／未提供，不能出現假正常；情報應未接入。設定詳情顯示原研究服務與預覽版本，Demo／Live、Bot 啟停應未接入。
5. **工作台**：選一個預設，調一條分隔／拖換一個面板／隱藏一個面板，重新整理確認保存；元件庫加回、放大後 Escape、重設。切另一頁確認布局獨立；頂部 R4 狀態不被隱藏或放大遮住。剩餘拖排／分隔／復原由這一步人工確認。
6. **窄視窗**：縮窄一次，確認導航可捲動、面板單欄、表格自身捲動，沒有整頁橫向溢位；不要求重複遍歷所有預設。

若不符，回報「頁面＋操作＋預期／實際」即可；例如「研究→帶入候選7→原SMA4結果也變7」。畫面回饋直接指出區塊／密度／位置。不要清研究紀錄、DB 或 R4 證據來重試。

### 運行與權限

預覽 8771 PID `5512`，最後重開載入修正後 loaded=current／restart_required=false；只重啟預覽，原 8770 未重啟，原 build／instance 保留，正式 launcher 未切換。log 為 desk-preview.stdout.log／desk-preview.stderr.log。兩筆合成任務由原服務保存；沒有交易、憑證、R4 writer 或 DB 操作。

R4 唯一 run `347282b9d0d9433db6a0276209936f60`，最新只讀 UI 至 16:46 心跳、24/32 正式訊號、10 fills、0 anomalies、running。沒有重核 PID／frozen digest 或跑 8h verifier，不能宣稱長跑 PASS。仍預計18:40:11結束，依原 heartbeat／收尾分工處理。

未做獨立驗收、提交或 push；F1/R4 scope 分開，outputs／DB／研究 runs 不 stage，Gemini／CatOS_Yaozi 不碰。建議由指定 **5.6 Sol (Web)** 依上方清單驗收，再另議正式啟動器切換；本輪不因頁面完成自動切換服務。

## 15:46 Gemini 基準首頁比較（歷史）

使用者明確要求保留 Gemini 整體畫面、密度、導航與工作台操作，接入真實功能，來源／版本／驗收進詳情、缺資料簡短標示；**只先交付一頁首頁，方向確認後再展開其他頁。** 此要求取代原「只參考風格／不載布局引擎」限制，僅改新版首頁。使用者視覺確認與指定 **5.6 Sol (Web)** 獨立驗收仍未執行，本輪未提交／push。

[首頁比較](http://127.0.0.1:8771/workspace/home) 已開啟並保留頁籤；頂部切新版、Gemini 原版、上一版。參考頁是 14:31 保存截圖，附 8791／舊 F1 互動入口，不冒充同時更新的畫面。原 `/workspace/`、`/workspace/design` 保留，其餘導航沿用舊 F1；使用者不需要知道 file 路徑或另啟服務。

### 實作範圍

- 新增 `home.html`／`home.css`／`home.js`／`home-layout.js`／`home-layout.css`。沿用 Gemini 黑金配色、238px 側欄、52px 標頭、緊湊面板及布局引擎；引擎複製到本目錄，布局 localStorage 使用 `_home_preview_v1` 獨立命名，desktop／compact 分別保存，沒有跨 worktree import 或 CATOS_DATA mock。
- 三預設、拖曳換位、分隔條、放大、隱藏／元件庫加回、自動補滿、復原、重設只影響畫面。固定 R4／異常／風控未接入狀態在布局外。修正百分比加 splitter 造成寬度溢位、隱藏元件留下空 splitter；補滿依當前可見 DOM 計算，不依舊固定 ID。
- 首頁只有 GET：既有研究保存結果／報告、version、R4 status／manifest／events 只讀快照。研究圖可選已完成回測，摘要與標籤保留完整 Decimal；Float 只作 SVG 座標／進度。每 15 秒更新，有界逾時；不開 R4 DB，不提供交易或策略生命週期控制。
- 帳戶／日損／有效風控／情報缺資料顯示「未接入」與 `—`；研究曲線明示「研究回測 · 合成資料」。完整來源、原始事件、版本及驗收進原生詳情 dialog，元件庫有焦點限制與 Escape。
- `workspace_api.py` 新增首頁資產／hash 與 `/workspace/home`；GET `/workspace/reference/{name}` 只容許 gemini／previous 固定圖片，不接受任意路徑。CSP 同源，無 inline handler 或外部 runtime。新增兩項相關 route／CSP／localhost／路徑測試。

### 本輪實際驗證

- `python -B -m unittest tests.test_workspace_f1`：**21/21 通過，0.975 秒**。包含舊 19 項與新增首頁／固定比較圖片兩項，TestClient 只跑有界合成研究，不使用 R4 writer／DB；未跑全套或全市場回測。
- `node --check frontend/workspace/home.js`、`node --check frontend/workspace/home-layout.js` 通過。
- 真實瀏覽器：三預設、編輯顯示隱藏按鈕、隱藏／元件庫加回、單面板補滿、全版補滿、拖曳換位與復原、splitter 調整／reload 保存、雙擊均分、放大／Escape、固定狀態可見、資料／事件詳情、兩份比較圖完整載入、導航到舊研究頁再返回。
- 實際選 SMA4 run `178656caa4e644e5a2b72ae0e43a2e5c`：淨損益 `-0.99090140`、末值 `999.00909860`；回到最新 SMA7 run `d8a4acdde8424be68795900e2bbc8d98`：淨損益 `-1.43122140`、末值 `998.56877860`、33 筆成交、8 根預熱／89 根評估。均讀既有結果，沒有新增研究任務。
- 1440×900／390×844 無整頁水平溢位；窄視窗單欄、導航可橫捲，元件庫及資料 dialog 不超出視窗。compact 舊測試布局曾顯示不同排序，UI 重設後回到曲線／事件／執行／研究／情報出廠順序，並未改 Gemini 保存布局。console warn/error 為空，暫時 viewport override 已解除。
- 新版證據：[桌面首頁](../outputs/frontend-design-review-20260930/new-home.png)／[窄視窗首頁](../outputs/frontend-design-review-20260930/mobile-home.png)。[Gemini](../outputs/frontend-design-review-20260930/gemini-home.png)／[上一版](../outputs/frontend-design-review-20260930/current-home.png) 為前段比較截圖；截圖不是即時資料。

### 程序、R4 與接續限制

8771 preview 從已核對 command line 的 PID `26132` 重開為 `37740` 以載入新路由；沒有 writer，只轉交固定研究 API 給原 8770。原 8770 未重啟；`40828` 是前輪 PID，本輪 GET 讀到原 build `72734a4e3b7d06215a68ea9c5c52af3e898b8fafbee921bc2c87e68deeeff5e5`，未重核 idle／PID。後續靜態修改可能讓 workspace version 顯示 restart_required，完整 loaded/current 在詳情；其他頁的提交流程本輪未重新驗證，不把前輪功能自驗當成本輪結果。Gemini 8791／PID `15076` 保留，原目錄未修改。預覽 log：`outputs/frontend-design-review-20260930/home-preview.stdout.log`／`home-preview.stderr.log`。

R4 唯一 run `347282b9d0d9433db6a0276209936f60`，最新首頁心跳 **15:46:15**、running、20/32 正式訊號、8 fills、0 anomalies，預計 18:40:11 結束。僅 GET 證據，沒有讀 R4 DB、重核 PID／digest、停止／重啟或執行八小時 verifier。frozen SHA 與程序證據以下歷史為準，不能宣稱本輪八小時 PASS。

首頁與 R4 未提交 scope 分開；本輪修改首頁資產、workspace API、專屬 tests、規格／設計紀錄／交接／入口。outputs／DB／研究 runs 不 stage，未碰 CatOS_Yaozi。下一步留在原對話收首頁視覺回饋；方向確認後才展開其他頁。獨立驗收與 Git 維持使用者既有分工，未自動建立其他對話或發送驗收指令。

## 12:55 舊 F1 實作紀錄（歷史）

2026-09-30 12:55（台灣時間）。使用者本輪指示「讀入口與 F1 規格，保留 R4，實作專屬工作台」。本輪已完成程式、專屬測試與 HTTP 瀏覽器驗證；尚未做 5.6 Sol (Web) 獨立驗收、提交或 push。

## 可以直接開啟

- **實作工作台**：[http://127.0.0.1:8771/workspace/](http://127.0.0.1:8771/workspace/)。首頁先呈現來源／時間、異常與資料限制，再呈現當前執行；側欄切換研究、執行與事件。
- **原設計樣稿**：[http://127.0.0.1:8771/workspace/design](http://127.0.0.1:8771/workspace/design)。仍是 11:47 的固定合成快照，不隨 R4 更新。
- 原研究服務 8770／PID 40828／instance `f2a3c7d3b3544eeaa2aa42eb8a45d71b` 保留運行，build `72734a4e3b7d06215a68ea9c5c52af3e898b8fafbee921bc2c87e68deeeff5e5`、loaded=current、active_run_id=null；沒有重啟或修改其 source。

瀏覽器頁籤「catOS · 運行與異常」及原樣稿已保留。使用者只需點上述連結，不須操作 file URL 或啟動 Python。127.0.0.1 只指向使用者目前這台電腦。

## 最小實作與啟動邊界

- `frontend/workspace/`：原創 F1 shell／CSS／JS，不載入 Gemini runtime、CATOS_DATA 或舊 layout 引擎。研究使用既有 catalog、submit、runs、task、result、report；草稿、保存結果與 R4 參數分離。完整金額保留 Decimal 文字；Float 只用於研究曲線的衍生繪圖座標。
- `catos/workspace_snapshot.py`：固定 server-side `outputs/local-sim-r4/` 根目錄、32 位 hex run ID；拒絕 symlink／Windows reparse point 與非普通檔案，metadata 64 KiB、events 2 MiB、每列 32 KiB、至多 4096 列，每次最多回 200 列。回傳完整列序號、實讀計數、最後訊號及成交；未完整末行不納入，計數不一致為 partial，running 心跳超過 120 秒為 stale。只讀 manifest/status/events，**不開 SQLite、不探測 Worker 存活、不判 8h PASS**；風控、latch、未決與可增倉保留 unavailable/null。
- `catos/workspace_api.py`：正式 factory 以同一 `research_api.create_app()`／同一 ResearchService 掛入 F1 root、`/quant`、`/workspace/` 與 GET adapter；研究 API 與既有 intelligence API 保留。F1 build 自行追蹤，不修改 R3 build 契約。
- 為遵守原服務不重啟及立即檢視需求，本輪啟動 **暫時 8771 預覽**（PID 39844）。預覽沒有 ResearchService／writer／DB，僅將固定 allowlist 研究 API 轉交 `127.0.0.1:8770`；只容許既有 backtest／optimization POST，保留 origin、JSON、8 KiB 與 build 檢查，不接受任意 URL／路徑／query／交易控制。
- 此預覽是手動啟動的本機程序，沒有新增 Windows service、自啟動、重啟監控或第二帳本。唯一綁定 `127.0.0.1`，沒有 CORS 放寬。關閉瀏覽器不停止 R4。

若預覽已結束，於本工作目錄執行：

```powershell
python -B -m catos.workspace_api --preview
```

正式整合啟動命令為 `python -B -m catos.workspace_api`，固定 8770。**本輪沒有取代原 8770 程序**；後續需確認研究空閒、明確安排原服務收尾後才切換啟動器。port 被占用即退出，不自動停 owner 或換 port。不能把本輪 TestClient 的整合驗證寫成原 8770 已切換。

## 實際驗證

- `python -B -m unittest discover -s tests -p test_workspace_f1.py -v`：**19/19 通過**。包含決策前／成交後分離、完整 Decimal、禁止開 DB、部分末行／計數 race、stale、歷史完成、身分／路徑／reparse、資料缺漏與損壞／上限、tail 計數、localhost／origin／proxy 限制，以及 integrated factory 的真正合成回測與同一 service 結果。
- `node --check frontend/workspace/workspace.js` 通過；HTML 58 個 ID 無重複；`git diff --check` 無 whitespace error。沒有執行全市場回測、修改 source 的 R4/R3 漂移測試或全套測試。
- 真實瀏覽器：三個主工作區及風控／事件／情報／系統導航；研究草稿 period=4 時舊結果仍固定 period=2；候選只帶入草稿；分割 70%／收合重新整理後保留、每工作區獨立、還原為 62%／展開；完整事件詳情可查 tag／cross／net／reduceOnly。切 smoke 再切 R4 的來源身分正確。
- 實作頁於 1440×900（client width=1425）與 390×844（client width=375）無整頁水平溢位。窄視窗單欄；放大保留頂層合成環境、來源心跳及固定異常／可見性限制。console error／warn 記錄為空。
- 原樣稿已由 **HTTP** 正常開啟，補驗切換、草稿／結果分離、分割／收合／reload 保存、放大／還原與窄視窗；沒有整頁水平溢位或 console error。發現原樣稿放大時會覆蓋固定異常區，且手機導覽需要橫向捲動；保留原樣稿作設計歷史，**實作頁已修正**。原 file URL 阻擋只保留為歷史，不再是 HTTP 檢視障礙。
- 首頁截圖：[home-1440.jpg](../outputs/workspace-f1-preview/home-1440.jpg)，12:54 的 8 根／4 fills 快照；不拿截圖當即時資料。

實際透過工作台提交、由原 8770 保存的三筆有界合成任務均為 complete：

| 任務 | run_id | 設定／證據 |
| --- | --- | --- |
| 回測 | `80d322cc74d4429a8fecf49ce927a420` | period=2、warmup=2；net_pnl=`-0.79532090`，35 筆模擬成交 |
| Optuna | `30e9b37f46bc49878f7dc0afb16814fc` | period 2–8、step=1、3 trials、seed=42、warmup=8；候選 4／8／7 |
| 候選新回測 | `178656caa4e644e5a2b72ae0e43a2e5c` | period=4、warmup=8；與原結果各自保存 |

這三筆寫入既有 `outputs/research-web/`，沒有接交易所、實盤、Demo 或 R4 writer。

## R4 保留與交付範圍

12:55 唯讀核對：原 run `347282b9d0d9433db6a0276209936f60` 為 running，9 根訊號、4 fills、0 anomalies，runner PID 26720／Worker PID 28460 仍在，預計 18:40:11 結束；不表示 8h PASS。manifest 全清單重新計算 SHA 仍為 `ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`。

本輪新增兩個 workspace 模組、三個 frontend/workspace 資產、F1 tests、本交接，更新 F1 spec 與 current-handoff。原 R4 未提交內容及 CatOS_Yaozi 不碰；不提交、不 push、不把 F1 混入 R4 scope。預覽 log／截圖、R4 output／DB、研究 runs 不 stage。樣稿目錄原即未提交，保留。

下一步建議由 **5.6 Sol (Web)** 獨立驗收 F1（不能把本輪自驗寫成獨立驗收），再安排 8770 啟動器切換。R4 仍依原 heartbeat／8h verifier 流程收尾；F1 通過不自動使 R4 通過。
