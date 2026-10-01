# W5 正式 UI 完整短程模擬交接

2026-10-01（台灣時間）。使用者指令「執行 W5，依提案完成限定驗證」已執行。**開發輪限定驗證 PASS；指定 5.6 Sol (Web) 獨立驗收待辦。** 本輪沒有修改應用程式或執行 Git。

## 唯一新案例與結果

正式 `http://127.0.0.1:8770/workspace/execution` 明示點擊一次「啟動短程模擬」，固定 `sma-synthetic-smoke-v1`；沒有 API 替代啟動、第二次啟動或 stop。

- run_id：`c02f745093ae4aaba423cb5a51855219`
- request_id：`947445dc87224c8681ae793235a0fd5d`
- created_at：`2026-10-01T14:38:10.498223+08:00`
- finished_at：`2026-10-01T14:38:19.704013+08:00`，耗時 `9.20579` 秒。
- completed、2 warmup＋8 bars、4 fills、cleanup_confirmed=true、worker_closed=true、error=null、still_finishing=false。
- 原定 interval_seconds=1 未改；最後一根預熱至首個正式訊號、相鄰正式訊號間隔為 `1.047522` 至 `1.092086` 秒。2 根預熱皆 target=null／NO_INTENT。
- final_account 原始字串：equity=`999.91375990`、fees=`0.00404010`、position=`0`；與提案 W2 參考值一致。4 筆 FakeExchange 費用用 Decimal 加總一致，tag 均為 `41cb53c54d6dABDE`。
- stop_requested=false、stop_requested_at=null；本輪新案例 metadata 的 stop_commands=[]。
- 控制槽 idle、active_run_id=null、start=true／stop=false；UI 顯示「可啟動 · 已完成 · 8/8 根 · 4 成交」。

真實 Worker PID `43840`，關閉證據來自 controller API／metadata，未另查程序或強制終止。runner 現行程式建立 `sim-control-<run_id>` 合成帳戶並指定 require_new_database=true；新案例目錄與 state.sqlite3 僅核對檔案資訊，未開 DB。final position=0 是策略自然成交結果；cleanup 不代表自動清倉、ownership 釋放或逐列帳務重驗。

## UI 命令、刷新與觀測限制

瀏覽器 Network 證據記錄唯一 start POST（hasUserGesture=true），本文為 `{ "request_id": "947445dc87224c8681ae793235a0fd5d", "template_id": "sma-synthetic-smoke-v1" }`，回覆 202；X-CatOS-Build 與 X-CatOS-Instance 完全符合本案例與正式服務。

點擊後保存「啟動中 · 0/8 根」畫面，立即 reload，刷新後仍為同一啟動中狀態，之後觀測 6/8 根，再自然完成 8/8 根。觀測游標後的兩段 Network 事件沒有遺漏／截斷（hasMore=false、truncated=false），總共僅 1 次 POST；沒有 stop 或刷新產生的額外命令。前後 simulation 清單只增加上述唯一 run，W4 舊案例完整 API snapshot 相同。運行中使用 reload，未額外測試切頁、關頁或重送。

命令保存先於 POST：`frontend/workspace/simulation.js` 的 Control.send 先同步 sessionStorage.setItem，保存失敗即 return，成功才發 POST；成功回覆才 removeItem。本輪確認此現行程式與 build／來源前後未變，並取得成功 UI POST，據此支持該路徑先保存的判斷。**未取得 sessionStorage 的直接即時觀測**：raw CDP enable 呼叫不支援，DOMStorage 事件為 0；Network.readEvents 可用。這是觀測方法限制，不是 UI 自動安全審查拒絕，也沒有注入觀測程式、修改頁面或另開案例補證據。

## 服務、歷史與基線保持

| 項目 | 本輪前後比對 |
| --- | --- |
| 8770 owner | PID `39200`、127.0.0.1 唯一 listener、`python -B -m catos.workspace_api`，命令／建立時間相同 |
| workspace build | `5e59ae5320b83271e5e18c148545b39b9fe89e730387f8b2003a23a89dc14417` |
| research build | `72734a4e3b7d06215a68ea9c5c52af3e898b8fafbee921bc2c87e68deeeff5e5` |
| simulation build | `33fb635a68420472f276b65eb62aff4db2c1c4043072e1a877144b14f5f8e184` |
| 正式版本 | 三個 loaded=current、restart_required=false；版本前後相同，忽略 workspace observed_at |
| research instance | `9a6c6367ff024b2d9ea4df5be8ecce29`，active_run_id=null |
| simulation instance | `db7231f9f987439d9375ccc1778528ad`，不可與 research instance 混用 |
| 研究 runs | 完整 JSON 相同，26/26 complete |
| 8771 preview | 原 PID `5512`、命令／建立時間相同；loaded build `5e82055844056572452a1225a0916104a8a977a262cf1ed6662373e903f08c4d` 不變，restart_required=true 保留 |
| preview 控制 | 僅 GET simulation/version，前後均 404；未 POST |
| R4 摘要 | 前後完整 API snapshot 相同，僅忽略 observed_at；complete、32＋2 根、13 fills、0 anomalies、issues=[] |
| R4 frozen SHA | `ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`，前後與基線相同 |
| 來源／輸入 | 收集的 runtime、controller、runner、API、workspace、simulation.js、相關測試與合成 CSV SHA，以及固定設定前後相同 |

## 證據與驗證

`outputs/workspace-w5/` 保存：

- `before.json`／`after.json`：owner、唯讀 API、來源／輸入 SHA；`collect.ps1` 是本輪收集腳本，拒絕覆寫。
- `browser-events.json`／`browser-events-tail.json`：游標後的 Network／DOMStorage 事件與唯一 POST。
- `ui-before.txt`／`ui-running.txt`／`ui-reloaded.txt`／`ui-completed.txt`，以及 `ui-before.png`／`ui-completed.png`。
- `metadata-after.json`：僅合成控制 metadata 副本；`new-run-file-inventory.json`：僅新案例檔案資訊。
- `compare.py`／`comparison.json`：本輪前後證據比對，41 項斷言 PASS（含兩輪 loaded/current 檢查）；不開 DB、不發命令。已完成結果不為交接而重跑，腳本拒絕覆寫輸出。

新增模擬資料留在 `outputs/local-sim-control/c02f745093ae4aaba423cb5a51855219/`；所有 outputs 保留，不預設提交。沒有重跑 W2／W3 單元測試、R4 verifier、全市場回測或 DB 驗證。W2／W3／W4 獨立 PASS 均為既有證據，不算本輪重驗。

## 下一片與分工

交由指定 **5.6 Sol (Web)** 做 W5 限定唯讀獨立驗收：核對本文件、comparison 與原始證據，再以 GET／程序唯讀確認現行 owner／三版本／控制槽、唯一新 completed 案例、26 筆研究、8771 loaded build 與 R4 摘要／frozen SHA。判斷命令保存證據時保留上述直接觀測限制；不得為補證據重跑新案例。

本輪僅新增提案狀態、W5 交接、入口與驗證產物；未核對 Git 狀態、commit 或 push。既有其他未提交內容見 W2／W3／正式入口交接，不清理、不混入。沒有新政策待決；保留兩服務、R4、研究與所有合成案例，不讀憑證、不採集、不接交易、不改既有 DB／schema、不長跑、不 resume、不解除 latch／recovery、不動 Yaozi 或 Gemini 目錄。
