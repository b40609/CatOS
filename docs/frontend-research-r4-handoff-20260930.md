# R4 local-sim 啟動交接

更新：2026-09-30 20:23 台灣時間。使用者已授權啟動 R4，並選擇短程驗證後立即連續跑 8 小時；原由 6.1 Sol 完成實作與短程驗證。**狀態：8 小時正式 verifier PASS，進入限定範圍 Git 收尾。** 唯一 run `347282b9d0d9433db6a0276209936f60` 實際 28800.073 秒、32 根正式＋2 根預熱、13 fills、0 anomalies、worker_closed=true。5.6 Sol (Web) 已依正式 CLI 驗收；基線 `7c346f2`，契約見 [R4 spec](frontend-research-r4-spec-20260930.md)。以下啟動與早期驗證紀錄保留為歷史。

## 完成內容與證據

- 新增 `catos/local_sim_r4.py`：固定合成 fixture、既有 LocalSupervisor／FakeExchange／單 writer Journal、32 根 × 900 秒、有界心跳與手動停止、source/worker/continuity fail closed。
- `WorkerConfig.strategy_artifact` 僅允許固定 `sma-parameters-v1`；舊 wire 預設不變。state adapter 從 approved snapshot 建立 period=2／quantity=2 的 RegisteredSMA，checkpoint 仍兩根；策略只在 child 載入。`strategy_version=1` 是舊 IPC/state adapter 契約，製品身分另由 config／manifest 的 artifact version + reviewed SHA 綁定，不把它當成 R3 製品版本。
- 帳戶視圖以既有研究 Decimal 核心對 SQLite execution_fills 作唯讀投影；SQLite 是唯一成交持久來源，沒有第二帳本／schema 變更／交易所 transport。
- 專屬 `test_local_sim_r4.py` 9/9、既有 IPC 11/11、Worker 15/15 通過。9 個專屬測試含全 32 根快速機制驗證，不能算成真實 8 小時。
- 最終實際 smoke：`d8fdd571ef554c8681e2316edd22bbe9`，2026-09-30 10:39:22.704357 到 10:39:30.828284（台灣時間），8.12394 秒、兩根無意圖預熱、8 根訊號、4 筆完整成交、0 異常；父程序策略 modules absent；Worker 已收尾。

首輪 smoke `51e0f2cbe309473e8c0e2b32563a4087` 在 2 筆成交後失敗：runner 以 intent_key 是否存在判定派送，但 NO_CHANGE 也保存 intent key，造成 `only committed risk-approved intents can be submitted`。已修正為只派送 `RESERVED_SIMULATION`，加專屬 regression；失敗證據保留，未清理／覆寫。中間修正後 smoke `049a422bab384a068839d22e8ec55ac8` 亦 complete；最終依據採上述 d8fdd571 run。

## 8 小時 run 證據

- run_id：`347282b9d0d9433db6a0276209936f60`
- 目錄：`outputs/local-sim-r4/347282b9d0d9433db6a0276209936f60/`
- 實際開始：2026-09-30 **10:40:11.810391 UTC+08:00**；預計結束 **18:40:11.810397 UTC+08:00**，32 根每 900 秒。
- launcher PID `28860`、runner PID `26720`、Worker PID `28460`，CIM parent/command 核對成功；啟動後 running、warmup_bars=2、bars=0、fills=0、anomalies=0。
- runtime SHA256：`ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`；source list／reviewed artifact／dataset／engine digest 詳見 manifest.json。改 listed runtime bytes 會停止本輪，運行中不得修程式。
- stdout／stderr：`outputs/local-sim-r4/01c6b94d1b684eb992de640b2211c3ac.stdout.log`／`.stderr.log`；status.json 每 30 秒心跳，events.jsonl 保存預熱、日基準、訊號、成交與異常。

合成時間從當日台北 22:00 重定位固定 15m fixture，與實際牆鐘分開；本次是白天連續 8 小時，不稱已跑過自然整晚行情。資料完全合成，funding 明示零，不接交易所。若需人工停用，只在本 run 目錄建立 `stop.request`，runner 自行收尾，保存責任與證據；停止不代表 PASS，也不平掉最後部位。

## 驗收

等待期間新增 `catos/local_sim_r4_verify.py`，其專屬 `test_local_sim_r4_verify.py` 9/9 通過（9.114 秒）。涵蓋只讀完成驗收、running 不開 DB、時長不足、存活 Worker、runtime digest 漂移、費用證據不一致、未決委託不釋放、journal content hash 及固定 artifact config。測試僅使用新建暫存 smoke／自己的副本，不改長跑 source 或 DB。

2026-09-30 11:13 台灣時間，以正式 CLI 對已保存最終 smoke 獨立核對：`SMOKE_PASS`、8 根／4 fills／0 anomalies、費用 `0.00404010`、權益 `999.91375990`、read-only DB、runtime digest 未變。對 8 小時 run 回 `PENDING`，2 根訊號／2 fills／0 anomalies，status 心跳 11:13:13；這是進度，尚非 8 小時驗收。驗收器不在凍結 source list，未影響 running。前端策略中心可並行操作；Bot／Risk／Logs 等頁面仍為原型，詳見 [等待期間前端盤點](frontend-readiness-parallel-20260930.md)。

等實際 8 小時完成再讀 status/events/manifest，並對本 run 的 DB 使用 read-only SQLite（含 WAL），核對實際時長 >= 28800 秒、32 根正式 + 2 根無意圖預熱、所有 fill/tag/Decimal 費用與 execution_fills 相符、0 anomalies、無 unresolved／reservations、Worker 已終止、source digest 未漂移、journal integrity 與保存訊號完整。running／stopped／failed 不可改寫 PASS；不自動清理 DB／釋放 UNKNOWN／重送／re-arm／啟第二 runner。

正式入口：`python -B -m catos.local_sim_r4_verify 347282b9d0d9433db6a0276209936f60`。完整 eight-hour 才回 `PASS`；smoke 為 `SMOKE_PASS`，running 為 `PENDING`。工具輸出不能取代錯誤證據及人工追查；不因 PENDING 啟第二 runner。

2026-09-30 20:23 台灣時間，指定 5.6 Sol (Web) 對唯一 run 執行上述正式 CLI，實際回 `PASS`：profile=`eight-hour`、elapsed_seconds=`28800.073241599952`、bars=`32`、fills=`13`、anomalies=`0`、final_equity=`999.67939950`、fees=`0.01320050`、database_mode=`read-only`、runtime_digest_unchanged=`true`。此結果是本輪正式 verifier 證據，取代先前 complete／待驗收狀態；未啟第二 runner、未改 DB、未切 8770。

已建立本對話 heartbeat automation `r4-8-local-sim`，每小時唯讀追蹤、最多 9 次；完成時按上述條件驗收與文件／Git 收尾，完成或需人工介入時停用。它只接續驗收工作，不建立 runner、不取代執行程序，也不自動故障重跑。首次工具呼叫因缺 destination 被拒絕，未建立 automation；補上 destination=thread 後工具確認建立，沒有重複項目。

正式 verifier 已通過；Git 收尾僅提交本片 scope：`.gitignore`、`catos/ipc.py`、`catos/worker.py`、`examples/sma_state.py`、`catos/local_sim_r4.py`、`catos/local_sim_r4_verify.py`、兩組 R4 專屬 tests、本片 spec/handoff、前端盤點與相關使用說明，以及 current-handoff 的 R4 狀態更新。生成資料／DB／log 不 stage；`AGENTS.md`、`.codex/` 與其他切片改動不混入。不 push、不切 8770、不啟新 runner；Demo／Live 仍另需授權。
