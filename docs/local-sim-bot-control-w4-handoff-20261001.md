# W4：正式 8770 載入 W2／W3

2026-10-01（台灣時間）；使用者明確授權核對 owner、版本及在途任務，載入已驗收 W2／W3並完成最小驗證。**服務更新、開發最小驗證及指定 5.6 Sol (Web) 限定獨立驗收均 PASS。** 本輪沒有程式修改、提交或 push。

## 更新前核對與服務更新

- 8770 唯一 listener 為 PID `41344`，命令為 `python -B -m catos.workspace_api`；API workspace 指向本工作目錄，research instance=`e126513443884f26810bf437290c66b1`、research_owner=`same_app`。workspace restart_required=true，simulation version 404，尚未載入 W2／W3。
- 研究紀錄 26 筆全部 complete、queued／running=0、active_run_id=null；正式 simulation metadata 尚不存在。未遇在途任務，因此沒有停止研究任務或強制終止 Worker。
- 8771 preview owner 為 PID `5512`，命令含 `--preview`；本輪不停止或更新它。
- 更新前後以 `files_hash(RUNTIME_FILES)` 核對 R4 凍結來源：`ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`，一致。沒有修改 manifest／runtime，沒有重跑 R4 verifier。
- 對已核對的 8770 console 發送正常 Ctrl+C；觀測舊 PID 與 8770 listener 消失後，才用同一 Python executable 隱藏啟動 `-B -m catos.workspace_api`。未使用 Stop-Process、taskkill 或其他強制終止。

正式服務於 **2026-10-01 13:34:42（台灣時間）** 啟動，PID `39200`；啟動日誌確認 application startup complete。research 與 simulation 各自有 instance，不能混用 mutation header。

| 身分 | instance／build |
|---|---|
| research instance | `9a6c6367ff024b2d9ea4df5be8ecce29` |
| simulation instance | `db7231f9f987439d9375ccc1778528ad` |
| workspace build | `5e59ae5320b83271e5e18c148545b39b9fe89e730387f8b2003a23a89dc14417` |
| research build | `72734a4e3b7d06215a68ea9c5c52af3e898b8fafbee921bc2c87e68deeeff5e5` |
| simulation build | `33fb635a68420472f276b65eb62aff4db2c1c4043072e1a877144b14f5f8e184` |

三個正式 version 的 loaded/current build 相同、restart_required=false；workspace preview=false、research_owner=same_app。workspace runtime_controls=[] 為既有契約；控制能力由 simulation version 提供。8771 保留舊 loaded build，其 restart_required=true 亦保留，不冒充已更新。

## 本輪最小驗證

使用已驗收 API 在正式 8770 建立唯一新案例 `89470c8bb7084de89ed701d54b9274fd`，固定 `sma-synthetic-smoke-v1`、1 秒間隔、真實獨立 Worker／FakeExchange／新合成帳戶及新 DB；未使用既有研究或 R4 DB。start／stop 本文、request_id 與 simulation build／instance 在命令前保存至本輪證據，沒有回覆遺失或重送。

- start 202；讀取到 2 根正式 K 線後明示 stop，stop 202。最終 stopped、warmup_bars=2、bars=2、fills=2、cleanup_confirmed=true、worker_closed=true、error=null。這是提前停止驗證，不是完整 8 根或八小時驗收。
- 最終控制槽 idle、active_run_id=null、start=true、stop=false；沒有清倉、釋放 ownership、resume 或解除 recovery／latch。
- 正式 `/workspace/execution` 與 `/workspace/assets/simulation.js` HTTP 200。實際 IAB 頁面更新前顯示可啟動，案例停止後 reload 顯示「可啟動 · 已停止 · 2/8 根 · 2 成交」、停止按鈕停用；R4 仍顯示 32/32 根、13 成交、0 anomalies。啟停由 API 執行，本輪沒有點擊 UI 啟停，沒有重演 W3 導航中啟停證據。
- 8771 simulation version GET 404、simulation start POST 404，沒有代理控制 mutation。8771 PID 與 loaded workspace build 前後相同；沒有更新 preview。
- 研究 runs 完整 JSON 前後相同，共 26 筆；沒有建立新研究任務。research active_run_id=null。
- R4 唯讀摘要仍為 complete、32 根正式＋2 根預熱、13 fills、0 anomalies、issues=[]，run=`347282b9d0d9433db6a0276209936f60`。只讀既有摘要，不開 R4 DB，不重跑 verifier；原正式 PASS 仍引用歷史證據。

沒有程式修改，故不重跑 W2／W3 單元測試；[W2 50/50](local-sim-bot-control-w2-handoff-20261001.md)與 [W3 33/33](local-sim-bot-control-w3-handoff-20261001.md)為指定角色既有獨立驗收，不計入本輪重驗。

## 證據與接續

本輪證據在 `outputs/workspace-w4/`：`before.json`（更新前版本及完整研究清單）、`commands.json`（合成命令與版本綁定，無憑證）、`smoke.json`（啟停及收尾）、`after.json`（更新後版本、完整研究清單、R4 摘要、preview probes）及 `service.stdout.log`／`service.stderr.log`。新增模擬資料只在 `outputs/local-sim-control/89470c8bb7084de89ed701d54b9274fd/` 與控制 metadata；保留所有資料，不預設提交 outputs。

限制：未做本輪 DB integrity／逐列帳務重驗、完整 8 根、長跑、服務重啟後持久化重驗；這些不能冒充通過。沒有修改既有 DB schema、碰 Yaozi／Gemini 原目錄、讀憑證、採集或接交易。

## 指定 5.6 Sol (Web) 限定獨立驗收

2026-10-01 14:22 起執行唯讀驗收，沒有重啟服務或建立新 run：

- 8770 唯一 listener 為 PID `39200`，CIM 命令為 `python -B -m catos.workspace_api`，建立時間仍為 13:34:41；8771 仍為 PID `5512`、`--preview`。
- 8770 workspace build=`5e59ae5320b83271e5e18c148545b39b9fe89e730387f8b2003a23a89dc14417`、research build=`72734a4e3b7d06215a68ea9c5c52af3e898b8fafbee921bc2c87e68deeeff5e5`、simulation build=`33fb635a68420472f276b65eb62aff4db2c1c4043072e1a877144b14f5f8e184`；三者 loaded=current、restart_required=false。research instance=`9a6c6367ff024b2d9ea4df5be8ecce29`、active_run_id=null；simulation instance=`db7231f9f987439d9375ccc1778528ad`、slot=idle、active_run_id=null、start=true、stop=false。
- 研究紀錄仍為 26/26 complete、queued=0、running=0；run ID 順序與 `outputs/workspace-w4/after.json` 完全一致，無在途任務，因此沒有等待、停止或終止程序。
- W4 stopped 案例 `89470c8bb7084de89ed701d54b9274fd` 仍為 stopped、2 warmup＋2 bars、2 fills、cleanup_confirmed=true、worker_closed=true、error=null、still_finishing=false。
- 正式 `/workspace/execution` 及 `/workspace/assets/simulation.js` 均 HTTP 200；8771 `/api/workspace/simulation/version` GET 404，`/api/workspace/simulation/start` POST 404，preview 未掛載控制 mutation。
- R4 唯讀摘要仍為 complete、32 根正式＋2 根預熱、13 fills、0 anomalies、issues=[]。重新以 `files_hash(RUNTIME_FILES)` 計算 frozen runtime SHA=`ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`，與正式基線一致；未開 R4 DB、未重跑 verifier。

驗收範圍內未發現阻斷缺陷，**W4 PASS**。W2 50/50 與 W3 33/33 保持既有獨立驗收證據，本輪不重跑；完整 8 根、長跑、resume／recovery、DB integrity／逐列帳務及交易均不在本輪範圍。

Git 收尾仍由指定角色依既有分片範圍處理，提交及 push 不由此文授權。更廣完整 profile／resume／recovery／交易另定切片，不自動執行。

建議換驗收對話，入口：[current-handoff.md](current-handoff.md)。
