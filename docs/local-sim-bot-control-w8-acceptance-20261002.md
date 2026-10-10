# W8 唯讀獨立驗收

2026-10-02（台灣時間）。指定 `chatgpt-web/gpt-5.6-sol` 依 [W8 assessment](local-sim-bot-control-w8-assessment-20261001.md)、[執行交接](local-sim-bot-control-w8-handoff-20261002.md)及 `outputs/workspace-w8-20261002-stop-pending/` 封存證據進行獨立驗收。結果：**PASS**。

本輪沒有新增控制案例：未啟動 fixture／browser run、未呼叫 8770／8771、未 POST simulation API、未新增 run、未啟停正式服務、未讀產品 DB／憑證、未採集／交易，也未提交或 push Git。只讀既有證據與來源；另重跑既有純 JS 單元測試，Python W8 相關測試檔僅做 AST 靜態解析。

## 獨立核對結果

- `inventory.json` 所列 93 份封存證據逐檔重算 size／SHA256，93/93 與現有 bytes 完全一致。`source-hashes-final.json` 的 19 份來源目前 size／SHA256 全部一致；baseline、started、first-stop、settings、returned、retry-before、retry-after 保存的 source-hashes 也一致。
- W8 程式範圍符合 assessment：`tests/simulation_ui_w6_fixture.py` 增加 `hide_reply="stop"` 並保留預設 start；`tests/test_simulation_ui.cjs` 增加 stop pending 專屬測試；`tests/test_simulation_ui_w8_fixture.py` 增加接受後遮蔽與終態原命令重送測試。正式 `frontend/workspace/simulation.js`、controller／API 沒有本片差異。
- 隔離基線為 127.0.0.1:58238、PID 44320、`hide_reply=stop`；baseline 為 loaded=current、restart_required=false、unavailable=null、slot=idle、active=null、runs=0、POST=0、pending=null。
- `commands.jsonl` 嚴格只有三筆 simulation 控制 POST：start 1、stop 2。狀態依序為 backend/client `202/202`、`202/503`、`202/202`。唯一 run=`f434ce8ffdc4460f81fbc47541672685`，唯一 stop request_id=`86c6bad336e240d9a570416f79b1e76d`。
- 首次 stop 的 controller 已先接受：保存的 accepted snapshot 為同 run、`stop_requested=true`、`stop_requested_at` 非空，且 `accepted_stop_commands` 只有上述 stop ID；之後 fixture 才向 UI 回 503。這能區分「後端已接受」與「UI 無法確認」。
- `first-stop`、`terminal`、`settings`、`returned`、`reloaded` 五份 browser 證據中的 pending 原字串完全相同，path／body／build／instance 都等於首次 stop。settings／返回／reload 前的 observations 仍只有 start=1、stop=1，沒有自動 POST；execution 畫面持續禁用 start／stop、保留可用 retry。
- `terminal-poll.json` 的同 run 已為 stopped、cleanup_confirmed=true、worker_closed=true、error=null。此處 `worker_closed` 是 stub 欄位，只作本 fixture 終態證據，不延伸為實際 Worker 退出保證。
- 明示 retry 的 path、body、Content-Type、build、instance 與首次 stop 完全相同；CDP 保存的兩次 stop request URL／postData 亦相同。retry 回 202 後 pending 清除、retry 隱藏、start 恢復可用。
- retry 前後 `version.json`、`runs.json`、完整 run JSON、`control.json` 逐檔 bytes 完全相同；workspace 只排除頂層 `observed_at` 後相同。`control.json` SHA256 前後皆 `fae9e2dea256b59596d59996d3f286f93d96f430dddb11021b673bf78944f1d9`，僅一個 run，`stop_commands` 嚴格只有原 stop ID 一筆。retry HTTP body 與終態 snapshot 完全一致。
- 保留的 W6／W8 fixture unit roots 與 `unit-inventories.json` 所列檔案 size／SHA256 全部一致。本輪另重跑 `node --test tests/test_simulation_ui.cjs`，12/12 PASS、exit0；兩個 Python W8 相關檔案 AST parse 通過，沒有重跑會新增 fixture run 的 Python 測試。
- 正常收尾證據為 `/__test/shutdown` 200、launcher exit0、PID 44320 已不存在、58238 listener 不可達、`forced_kill=false`。封存 CDP 中未出現 127.0.0.1:8770／8771。

## 證據界線

後段 CDP GET 有截斷，不能宣稱整輪 CDP 完整；simulation 控制總數由完整 `commands.jsonl`、各階段 observations 與保存的三筆控制 POST 交叉核對。首次接受後 snapshot 是 middleware 在 controller 202 後保存的觀測，不是被遮蔽的原始 HTTP response body；retry 的完整 202 body 有另存並與終態 snapshot 比對。

本片只證明隔離 stub 下「stop 已接受但 UI 首次無法確認 → pending 經終態 GET／同 tab 返回／reload 保留且不自動送出 → 明示同命令 retry → 確認後清除」的既定 W8 範圍。未涵蓋真實網路遺失、正式 stop 故障、實際 Worker／帳務／交易、跨 tab／browser 重啟、跨 instance、服務重啟、stopping 中 retry 或異 run 回覆注入。

W8 限定驗收需求已滿足。Git 狀態仍含既有未提交內容，本輪只新增此驗收文件並同步入口；沒有 commit／push。
