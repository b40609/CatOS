# W8：stop pending 保存／還原與原命令重送交驗

2026-10-02（台灣時間）。使用者最新交辦：「採用新流程接續catOS開發」。依 [AGENTS.md](../AGENTS.md) 新工作包流程，接續已確認的 [W8 最小範圍](local-sim-bot-control-w8-assessment-20261001.md)，連續完成 fixture、限定測試、唯一隔離瀏覽器案例及採證。此交辦取代先前暫停／僅 assessment 不執行的接續狀態；未擴及正式服務、採集／交易、金融政策或 Git。

## 結果與差異

**開發自測通過，待指定 `chatgpt-web/gpt-5.6-sol` 獨立驗收。** 原 UI／controller 已支援所需行為，正式程式沒有修改。

| 檔案 | 本輪變更 |
|---|---|
| [simulation_ui_w6_fixture.py](../tests/simulation_ui_w6_fixture.py) | 新增明確 `hide_reply="stop"`／CLI `--hide-reply stop`；預設 start 故障保留。首次 stop 202 接受後改回 503，記錄 Content-Type、接受後 snapshot／run／stop 綁定。listener 記 owner PID、根與故障模式。 |
| [test_simulation_ui.cjs](../tests/test_simulation_ui.cjs) | 新增 stop 專屬測試：POST 前已保存完整 command、不確定回覆後保留、終態 GET／重建 Control 不提交、pending 禁止新 start／stop、明示 retry 本文與 headers 不變、確認後才清除。 |
| [test_simulation_ui_w8_fixture.py](../tests/test_simulation_ui_w8_fixture.py) | 新增接受後 stop 遮蔽與終態同命令重送測試，核對唯一 run／stop ID、完整 snapshot／version／runs／control bytes 不變。使用獨立保留根。 |

上述三檔為本工作包的程式差異；本文件、assessment 接續紀錄及 current-handoff 為交接差異。前一工作包修改的兩邊 AGENTS 規則與其他既有內容維持原樣；本輪同步本專案入口，未操作 Yaozi 業務、核對 Git 或提交。Git 差異及是否已有其他未提交內容留指定角色核對。

## 已執行限定測試

| 命令 | 實際結果 |
|---|---|
| `node --test tests/test_simulation_ui.cjs` | 12/12 通過，exit0，86.4408 ms。 |
| `python -B -m unittest tests.test_simulation_ui_w6_fixture tests.test_simulation_ui_w8_fixture -v` | 2/2 通過，exit0，12.345 秒；包含原 W6 預設 start 故障回歸。 |

Python 為本機 3.14，符合 3.11+。測試摘要在 [test-results.json](../outputs/workspace-w8-20261002-stop-pending/test-results.json)，是已觀測終端結果的摘要，未保存完整逐字終端輸出。unit 與 browser 分開計數；unit 保留根為：

- [W6 fixture unit root](../outputs/workspace-w6-fixture-test-c20100cd6aec41a285a8b94973cb2d44/)。
- [W8 fixture unit root](../outputs/workspace-w8-fixture-test-6b9be6b0966f49819892bb9adfe081bf/)。

本輪測試後未修改這三份來源；瀏覽器採證前後另核對 19 份 fixture／stub／測試／UI／controller／API／workspace 相關來源 size／SHA256，全部不變。未重跑無關套件、全市場回測或歷史正式案例。

## 唯一隔離瀏覽器案例

[完整證據根](../outputs/workspace-w8-20261002-stop-pending/)／[採證索引](../outputs/workspace-w8-20261002-stop-pending/README.md)。啟動命令：

```text
python -B -m tests.simulation_ui_w6_fixture --output-root outputs/workspace-w8-20261002-stop-pending --hide-reply stop
```

fixture 綁定新隨機埠 127.0.0.1:58238，owner PID44320，同 tab／origin。build=`33fb635a68420472f276b65eb62aff4db2c1c4043072e1a877144b14f5f8e184`，instance=`5bed03f8cb9e4b9aa5b40f35f9201b8a`。baseline loaded=current、restart_required=false、slot=idle／active=null、可 start、無 unavailable、pending=null、runs=0／POST=0。

- 唯一 run=`f434ce8ffdc4460f81fbc47541672685`，stop ID=`86c6bad336e240d9a570416f79b1e76d`。
- UI start 一次，202、pending 清除且唯一 run running；UI stop 一次，controller 202 接受，fixture 對 UI 回 503。接受後觀測保存 stop_requested=true、時間與唯一 stop 綁定；UI 顯示未確認，原 command 保留且新 start／stop 禁用、retry 可用。
- 20.0 秒內唯讀觀測到同 run stopped／cleanup_confirmed=true／worker_closed=true／error=null，slot=idle／active=null。終態 GET 未清 pending。worker_closed 是 stub 欄位，沒有實際 Worker 程序退出保證。
- 同 tab 設定頁 → 返回機器人管理 → reload，各份 storage 原字串與解析 command 完全相同；設定頁只查 storage，返回／reload 已載入同 build／instance 且 start／stop 禁用、retry 可用。完整 fixture observations 仍僅 start=1／stop=1，沒有自動 POST。
- retry 前封存完整 snapshot／runs／version／control.json。唯一一次 UI「重送原命令」使用完全相同 path、body 原字串、Content-Type、request_id、build／instance；202 的原 HTTP 本文為同 run／stopped，且完整等於 retry 前 snapshot。確認後 pending=null、retry 隱藏、start 可用／stop 禁用，沒有再點 start。
- shutdown 前比對完整 simulation version／runs／snapshot／events／時間及 control.json 原 bytes，完全不變；workspace 保留 raw、僅排除頂層 observed_at 後相同。control SHA256=`fae9e2dea256b59596d59996d3f286f93d96f430dddb11021b673bf78944f1d9`，僅一個 run、stop_commands 僅原 ID 一筆。
- 最終完整 `commands.jsonl`／observations 為 start=1、stop=2；backend 狀態 202／202／202、client 狀態 202／503／202。合格後另一次 `/__test/shutdown`，200，launcher exit0，owner 與 listener 消失；沒有 kill、清理或刪除。

[離線斷言](../outputs/workspace-w8-20261002-stop-pending/check-after.json)及 [HTTP／來源補核](../outputs/workspace-w8-20261002-stop-pending/final-checks.json)均通過。本輪採證工具在證據根，capture／check 只讀，shutdown 限本 fixture 且 exclusive request 檔避免重送；不要把封存工具當成下輪執行授權。正常退出後保存 [inventory](../outputs/workspace-w8-20261002-stop-pending/inventory.json)與兩個 [unit inventories](../outputs/workspace-w8-20261002-stop-pending/unit-inventories.json)。

## 限制與採證失敗記錄

CDP 前段控制事件與後段 retry 已保存，後段 GET 因緩衝淘汰有 truncated=true，不能宣稱整輪 CDP 完整。嘗試讀導航前的舊 response body 時資源已不可取得；沒有補 POST 或增加 run，改保存當前 retry 原始本文，首次接受以 fixture 的接受後 snapshot／綁定佐證。該 snapshot 不是被遮蔽的原始 HTTP response body。命令總數由完整 fixture 觀測及 commands.jsonl 重建，非僅靠 CDP 截斷窗口。

沒有缺少上述 W8 必要斷言。未涵蓋真實網路遺失、正式 stop 故障、實際 Worker／帳務／交易、跨 tab／browser 重啟、跨 instance、服務重啟、stopping 中 retry 或異 run 回覆注入。正式 8770／8771 API／控制請求為 0，未讀產品 DB／憑證、不採集、交易、改 schema／latch 或解除 recovery。W6／W7 PASS 為歷史，不代填本輪證據。

## 下一個成果與交接

建議切至指定 5.6 Sol (Web) 一次完成 W8 獨驗，核對這三檔差異、來源 hashes、inventory、原始命令／storage／metadata 與退出證據；必要重驗依風險及新流程，不能擅自補 browser run、正式案例或 Git。Git 仍另需明確授權。通過後將控制介面視為已覆蓋此缺口，下一工作包回到既有自動策略主線；不固定新增 W9 微片或重開相同 assessment。

接續指令：「讀 current-handoff、AGENTS 與 W8 handoff，獨立核對 W8 原始證據及差異；保留其他工作，不新增控制案例，不提交／push。」
