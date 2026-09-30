# 正式 8770 工作台入口

2026-09-30。使用者授權正式入口切換，僅做最小必要驗證。基線 `33a4518`；F1 6/6 與 R4 八小時 PASS 引用既有驗收，本輪不重跑。

## 完成與限制

- `scripts/start-research.ps1` 改啟動 `catos.workspace_api`，固定 127.0.0.1:8770。
- `/`、`/quant`、`/workspace`、`/workspace/` 改呈現已確認的 Gemini 首頁；舊 F1 保留 `/workspace/legacy`，舊研究頁 `/research/` 與研究 API 保留。
- 沿用既有 integrated factory 與 ResearchService lifespan／writer.lock，沒有新增 writer、DB schema、交易或任意 proxy。
- `test_workspace_f1.py` 22/22 通過，含正式根入口與同一研究服務的暫存合成回測／Decimal 結果；不是本機正式服務已切換或獨立驗收。
- 切換前 GET 確認舊 instance `f2a3c7d3b3544eeaa2aa42eb8a45d71b`、PID 40828、active_run_id=null，保存任務清單無 queued／running。程序命令與工作目錄核對為本專案 `catos.research_api --port 8770`。
- 自動安全政策拒絕停止舊程序並啟動新服務的命令，未提供具體拒絕理由；沒有停止或啟動任何服務。因此實際 8770 仍為舊研究入口，8771 preview 保留。新啟動命令對占用中的 8770 非零退出，訊息確認埠被占用，未停 owner 或換 port。
- 未提交或 push；AGENTS.md／.codex 設定與既有其他修改不混入。

## 人工切換與驗收

### 2026-09-30 23:20 接續結果（台灣時間）

對話遺失後唯讀核對 8770 已無 listener，直接啟動 `python -B -m catos.workspace_api`，未停止任何程序。新 PID `41344`、instance `e126513443884f26810bf437290c66b1`；正式服務已切換，取代上節「實際 8770 仍為舊研究入口」的現況描述。8771 PID `5512` 保留。

HTTP 最小核對：workspace version 為 preview=false、research_owner=same_app；workspace／research 均 restart_required=false，active_run_id=null。根首頁 HTTP 200 且含戰情總覽，`/workspace/research`、`/workspace/settings` HTTP 200。研究紀錄可讀取 26 筆、queued／running=0。R4 專用 `/api/workspace/local-sim/runs/347282b9d0d9433db6a0276209936f60` 回 `status.state=complete`、32 根／13 fills／0 anomalies、issues=[]；R4 不屬於 `/api/research/runs`，查該端點得到 404 不能判定 R4 資料遺失。

本輪未修改程式、未重跑單元測試／回測／R4 verifier，未做瀏覽器視覺與導航互動；歷史 PASS 不作本輪重驗。Git 狀態與提交仍待指定 5.6 Sol (Web) 核對；以下步驟保留為日後人工啟動與驗收清單，目前無須再執行停止／啟動。

1. 原 8770 啟動終端按 Ctrl+C，等程序結束；若研究已開始新任務，先等完成。
2. 在 `C:\Users\user\Desktop\CatOS_Astra` 執行 `python -B -m catos.workspace_api`；日常也可使用 `scripts/start-research.ps1`。
3. 開啟 `http://127.0.0.1:8770/`，應為 Gemini 戰情總覽，切策略中心與系統設定確認導航即可。
4. GET `/api/workspace/version`：preview=false、research_owner=same_app、restart_required=false；GET `/api/research/version`：PID／instance 應與舊程序不同、active_run_id=null、restart_required=false。兩個端點由同一 8770 程序服務。
5. 策略中心應讀得到既有保存結果；R4 應顯示 complete、32 根／13 fills／0 異常。無須新增回測來確認資料保存，且頁面的 complete 狀態不取代獨立 verifier PASS。

此時工作台無須 8771；原 preview 可在其啟動終端按 Ctrl+C 關閉。只綁 localhost，沒有 Demo／Live。

### 指定 5.6 Sol (Web) 獨立驗收

2026-09-30 已完成限定範圍驗收。`127.0.0.1:8770` 唯一 listener PID 與 research API PID 均為 `41344`，CIM 命令列確認為本專案 `python -B -m catos.workspace_api`；instance 仍為 `e126513443884f26810bf437290c66b1`。workspace／research 兩個 version 端點均 `restart_required=false`，workspace `preview=false`、`research_owner=same_app`，research `active_run_id=null`。`/api/research/runs` 實際為 `items` 陣列，共 26 筆，queued／running=0。

真實瀏覽器只做最小導航：正式 `/` 顯示「戰情總覽」、R4「已完成」、32/32 根訊號與 13 成交；實際點入「策略中心」及「系統設定」均成功，頁面顯示研究服務與工作台已連線、R4 已完成。未點執行回測、參數搜尋、設定變更或任何交易控制。R4 快照再確認 `status.state=complete`、bars=32、warmup_bars=2、fills=13、anomalies=0、issues=[]。

本輪未重跑單元測試、回測或 R4 verifier；22/22 與 R4 PASS 僅引用既有證據。scoped Git 只納入 workspace_api、start-research、README、workspace tests、本交接與 current-handoff；`AGENTS.md`、`.codex/`、outputs 與其他未提交文件留在工作樹，不 push。
