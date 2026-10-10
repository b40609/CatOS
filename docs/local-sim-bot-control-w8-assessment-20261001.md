# W8：stop 回覆不確定／pending 還原最小 assessment

2026-10-01（台灣時間）。使用者指示：「進行 W8 最小 assessment，不執行案例」。本輪僅靜態核對與文件交付；以下 fixture 修改、測試及瀏覽器操作均為待核准提案，尚未實作或執行。不是指定 5.6 Sol (Web) 的獨立驗收。

最新狀態（2026-10-02）：使用者其後交辦「採用新流程接續catOS開發」，已按本文確認範圍完成 W8 工作包及開發自測，待指定角色獨驗；見 [執行交接](local-sim-bot-control-w8-handoff-20261002.md)。此新交辦取代先前暫停／不執行的接續狀態；以下保留各輪當時的範圍與授權紀錄，不改稱當時已測。

## 具體缺口與現行路徑

失敗情境：stop 已被後端接受，但 UI 首次回覆無法確認。後端可能已 stopped／單槽 idle，UI 仍應保存原 stop 的 run 路徑、request_id、本文及 build／instance；同 tab 返回／reload 只還原 pending，不自動提交或因 GET 終態而清除。使用者明示重送後，才確認原命令並清除 pending。

[W7 acceptance](local-sim-bot-control-w7-acceptance-20261001.md)為歷史 PASS，僅涵蓋正式活動中 stop、實際 Worker 收尾、終態 API 原命令重送；首次回覆已確認，不涵蓋 UI pending stop。[W6 acceptance](local-sim-bot-control-w6-acceptance-20261001.md)隔離 B 涵蓋 start 回覆不確定及 pending 還原，stop 只有一次。不能將兩片拼接成 W8 已驗證。

本輪靜態定位，行號依目前檔案：

| 來源 | 現行行為及限制 |
|---|---|
| `frontend/workspace/simulation.js:4–16,74–75` | key=`catos_simulation_pending_v1`；constructor 驗證並還原 sessionStorage。stop 必須是指定 run 路徑、本文僅 request_id。保存限同 origin／同 tab 的 session，不宣稱關 tab 後、新 tab 或瀏覽器重啟還原。 |
| `simulation.js:18–38,78–82,91–93` | pending 阻擋新 start／stop；同 build／instance 可明示 retry。refresh 只 GET，不清除 pending；終態能力 start=true 仍不越過 pending。服務更換、不可用或 storageError 阻擋重送。 |
| `simulation.js:40–61` | 新 stop 取 active_run_id，先保存完整 command 再 POST；retry 直接用原 command，無須當前仍有 active run。錯誤保留 pending；有效命令回覆且 storage 移除成功後才清除。 |
| `catos/local_sim_control.py:284–306` | 同 request_id 綁定 stop／同 run 直接回當前 snapshot，不再保存／設定停止事件；新 ID 即使終態仍會新增 stop_commands，故必須核對原 ID 與唯一綁定。 |
| `catos/local_sim_control_api.py:42–64,85–88` | localhost、Origin、JSON、build／instance 與本文契約仍適用；stop 回 202。GET snapshot 不提供 stop_commands，需另讀隔離根 control.json。 |
| `tests/test_simulation_ui.cjs:23–32,38–43,51–67` | 已有 start 的回覆遺失／還原／retry 與正常 stop；沒有「stop 首次不確定、已終態後還原並明示 retry」的組合測試。本輪只讀，不宣稱測試通過。 |
| `tests/simulation_ui_w6_fixture.py:create_fixture` | 現有 middleware 只遮蔽第一次已接受 start，保留 controller 與觀測／正常 shutdown。不能直接原樣使用來驗證 stop。 |
| `tests/simulation_ui_fixture.py:15–20` | stub 等待 stop，再延後 6 秒收尾；無 Worker／交易 DB。可沿用，不延長或改動正式合成 profile。 |

未發現本片必須先修改正式 UI／controller 的缺口。最小做法是只補隔離 stop 故障模式及證據，不新增持久化機制、交易路徑或金融政策。

## 建議實作邊界與成本

待核准後，將 W6 專用 fixture 的故障操作做成明確選項：既有預設仍為 start，W8 明示選 stop。W8 start 正常 202；只將第一次 controller 已接受的 stop 回覆改成 fixture 503，之後同 stop 正常 202。限定只遮蔽一次、只在已接受後遮蔽，保留原 W6 行為；不改正式 API／UI，不攔截正式 8770／8771。

觀測檔須分列 backend_status／client_status、原 path／body／Content-Type／build／instance、已接受的 run_id 與 stop 綁定；在 controller 回 202 後、遮蔽前保存接受後 snapshot 與綁定，不能只以 503 推定後端接受。這是 middleware 的接受後觀測，不是被遮蔽的原始 HTTP response body；若未保存原始本文，須明示限制，不能改稱完整原回覆。原 stop 路徑／ID、綁定與 snapshot 須一致；不強求首次觀測必為 stopping。

沿用同一 stub runner、127.0.0.1 隨機埠、新建且保留的隔離證據／metadata 根。不得使用會結束時刪除資料的 W3 TemporaryDirectory launcher。服務 build 不涵蓋所有 fixture／UI 來源，另保存本輪實際 fixture、stub runner、UI、controller／API／workspace 的來源 hashes，不能只靠 loaded=current 推定故障模式及 UI 未變。

成本：fixture 的小幅選項與觀測擴充、一個 stop 專屬 UI 單元測試、一個 fixture 接受後遮蔽測試、一個隔離瀏覽器案例。UI 專屬測試須在首次 POST 回呼檢查 storage 已含該 stop，再模擬不確定回覆、終態 GET、重建 Control、唯讀 refresh 及明示 retry；核對未產生新 ID、未自動 POST、原本文／headers 不變、確認後才清除。因修改共用 W6 fixture，另執行既有 W6 預設 start 故障專屬測試作最小回歸，不重跑無關套件。單元／fixture 測試使用各自隔離資料，其控制請求與瀏覽器案例分開計數，不冒充同一 run 的證據。現階段不需要再新增正式短程 run、真實 Worker 或帳務驗證。

## 待核准最小瀏覽器案例

一個 stub run；UI start 一次、活動中 UI stop 一次、同 tab pending 還原、合格終態後 UI retry 一次。sessionStorage 必須由實際首次 stop 自行寫入，不回填、不修改保存內容、不手工呼叫 API 冒充 UI retry。

| 步驟 | 操作與必要證據 |
|---|---|
| 前置 | 核對本輪可辨識 fixture owner、隨機 localhost 埠、新隔離根、明示 stop 故障模式與必要來源 hashes；GET workspace／simulation，loaded=current、restart_required=false、slot=idle、active=null、可 start、無 unavailable；同 origin／tab pending 為空。若已有 pending，保留並停止，不清除 storage 或改用舊 run。觀測檔與 storage／DOM 採證須先準備好。 |
| start | UI 明示 start 一次，正常 202 且 pending 清除；唯一 run 已 running。runner 為 stub，不要求實際 worker_pid、正式 bar 或金融成交。 |
| 首次 stop | running 時 UI 明示 stop 一次。controller 202 接受，保存同 run、stop_requested=true、stop_requested_at 及唯一 stop ID；fixture 對 UI 改回 503。保存 UI 錯誤與原始 storage command，start／stop 禁用、retry 可用，POST 此時只有 start=1／stop=1。 |
| 終態唯讀觀測 | 僅 GET 等到同 run stopped、cleanup_confirmed=true、worker_closed=true、error=null、slot=idle／active=null；自首次 stop 起最多觀測 30 秒，逾時保存未涵蓋而不強制終止。UI 即使讀到終態仍保存原 pending、禁用新 start／stop。worker_closed 僅 stub 欄位，不能視為實際程序退出證據。 |
| 還原 | 同 tab 前往設定頁、返回機器人管理，再同 tab reload。first／returned／reloaded 三份 storage 原字串與解析 command 均相同且等於首次 stop；設定頁只核對 storage／POST 計數，不要求不存在的模擬按鈕。機器人管理的各次觀測須等同 build／instance 唯讀載入完成，才判定 start／stop 禁用、retry 可用。觀測檔依然 start=1／stop=1，證明 GET／導航／還原不自動 POST。 |
| retry 前封存 | build／instance／owner 未變，原 run 合格終態且 pending 未變；保存完整 snapshot／runs／version 與整份 control.json 原檔 bytes／SHA256、events、stop_requested_at／finished_at、stop_commands 僅原 ID 一筆。 |
| 明示 retry | UI 點「重送原命令」一次。原 path／body 原字串／Content-Type／request_id／build／instance 一致；後端及 UI 202，回同 run／stopped。storage key 移除、pending 清除，retry 隱藏，start 可用、stop 禁用。禁止再點 start。 |
| 收尾 | shutdown 前完成 retry 前後完整 simulation version／snapshot／清單／events／時間及整份 control.json bytes／SHA256 比較，全部不變、唯一 run／唯一 stop 綁定。workspace version 保留 raw，只排除頂層即時 observed_at 後比較，不能排除 run 時間或其他差異。保存最終 POST 觀測與 UI／storage；合格終態後僅用本輪 fixture 的 test-only shutdown 正常結束，核對 owner exit 與 listener 消失，保留檔案，不強制 kill／刪除。 |

成功案例的瀏覽器控制額度：start=1、stop=2，stop 兩次完全同命令；另提案最多一次本輪 fixture 的 `/__test/shutdown` 作正常收尾，單列而不混入 simulation 控制計數，不代表本輪已獲執行授權。不得補開第二 run、增加 stop 或重試失敗的 retry。正式 8770／8771 控制 POST=0，不呼叫其 API 或恢復服務。

採證須保存各階段原始 API JSON、storage／DOM 或截圖、原 POST 與 fixture 觀測、retry 前後 control.json bytes 及來源 hashes；每階段以完整 observations／commands.jsonl 核對命令累計，最終保留整份命令檔。`/__test/shutdown` 不在現有 simulation 觀測 middleware 範圍，另存其請求／回覆及 launcher exit／listener 證據。正常結束後封存檔案 size／SHA256 inventory，供指定角色從原始證據重建斷言；CDP 若截斷須明示，不能只靠截斷窗口推定總命令數。

## PASS、停止條件與證據界線

PASS 須同時滿足：後端先接受而 UI 首次無法確認；原 stop pending 在終態 GET／同 tab 返回／reload 後完整保留；無自動 POST；明示 retry 完全同命令；確認後才清除 pending；終態與唯一綁定不變。缺項標記未涵蓋，不用 W6／W7 的歷史 PASS 代填。

遇不合格基線、首次 stop 未接受／故障未生效、缺命令／storage 採證、build／instance 漂移、unavailable／recovery、未確認收尾或命令額度耗盡，停止後續案例命令並保存原因。不解除、不 resume、不改 storage、不補跑；只有合格終態才走 test-only shutdown，無法正常結束則保留並回報。

此案例驗證「後端已接受，但 fixture 使 UI 無法確認」，不宣稱真實網路回覆遺失、正式 stop 故障、實際 Worker／帳務／交易、跨 tab、關 tab 後保存、跨 instance、服務重啟或 stopping 中 retry。UI 一般回覆檢查目前只驗 run_id 格式與已知 state，不核對回覆 run_id 等於 stop 路徑；本片使用正常 controller 回覆並由證據核對同 run，不將異 run 回覆注入擴為本片要求。

## 本輪交付與下一步

本輪只讀適用指令、必要 UI／controller／API／fixture／測試與歷史入口，新增本 assessment 並同步 current-handoff；文件連結、靜態定位與授權邊界已檢查。未修改程式、未準備執行腳本、未執行單元測試／案例、未呼叫服務、未讀 DB／憑證、未操作 Git 或其他工作目錄。歷史 hashes／PASS 未重算；現行服務 owner／build／instance 未重新核對。

初版下一步為審閱範圍；2026-10-02 審閱、範圍確認結果及最新接續建議見文末紀錄。fixture 實作與限定測試／瀏覽器案例仍待新授權。實際交驗後的獨立驗收及 Git 維持指定 5.6 Sol (Web) 分工，Git 另行授權。本片不新增金融政策待決。

## 2026-10-02 靜態審閱結果

使用者指示：「依 W8 assessment 審閱範圍，維持不執行案例」。審閱完成，修正上述採證位置與判定條件；結論為範圍可供後續確認，並非案例 PASS、使用者核准或指定角色獨立驗收。

- 保留一個隔離 stub run、UI start=1／stop=2、首次 stop 已接受後遮蔽、合格終態後同命令 UI retry；不新增正式服務案例、金融政策或正式程式修改。
- 補明 middleware 接受後 snapshot 的證據界線、fixture／UI 來源 hashes、POST 前保存的專屬測試斷言，以及共用 W6 fixture 預設 start 行為的限定回歸。
- 修正設定頁無模擬按鈕、返回／reload 須待唯讀載入才判按鈕；明定 30 秒 stub 終態觀測上限、不 kill／補跑。
- 明定不變比較在 shutdown 前完成、workspace 僅排除頂層 observed_at；shutdown 單獨採證、命令全檔與 inventory 保存。

本輪僅文件修正與入口同步，文件連結／內容及必要靜態來源已核對；未修改程式、準備執行腳本、執行測試／案例、呼叫服務、讀 DB／憑證、重算歷史 hashes 或操作 Git。下一步建議依修正版確認 W8 範圍，維持不執行案例；不將本次審閱視為實作或案例授權。

## 2026-10-02 最小範圍確認

使用者指示：「依修正版 W8 assessment 確認最小範圍，維持不執行案例」。已依修正版確認下列範圍，取代上一節「待確認範圍」的接續狀態；此次確認限文件範圍，不授權實作、測試、瀏覽器案例或 Git，也不構成 W8 PASS。

- 實作邊界：僅 W6 fixture 新增 stop 故障選項，保留預設 start 行為；新增 stop 專屬 UI／fixture 測試及既有預設故障的限定回歸。無正式程式或金融政策變更。
- 瀏覽器案例邊界：僅一個新隔離 stub run，UI start=1／stop=2。首次 stop 後端接受但 UI 收到 503；原 pending 經終態 GET、同 tab 返回及 reload 保留，不自動 POST；合格終態後僅一次明示 UI retry，完全同命令，確認後才清除。
- 採證與停止邊界：沿用上述來源 hashes、命令全檔、storage／DOM、完整 metadata 與 control.json 不變比較；shutdown 前完成比較，workspace 僅排除頂層 observed_at。30 秒終態觀測上限、失敗保存並停止、不補跑；合格終態後最多一次 test-only shutdown，獨立採證及 inventory 封存。
- 執行與分工邊界：正式 8770／8771 API／控制與恢復不列入；單元／fixture 測試各用獨立根並分開計數。指定 5.6 Sol (Web) 獨立驗收及另行授權的 Git 分工維持原規則。

本輪僅核對修正版文件、記錄範圍確認並同步 current-handoff，檢查文件內容與連結；未修改程式、執行測試／案例、呼叫服務、讀 DB／憑證、核對 Git 或重算歷史證據。下一步建議另行授權上述 fixture 實作與限定驗證；無須重做同一範圍確認。

## 2026-10-02 新流程接續與工作包交驗

使用者在流程修訂後指示「採用新流程接續catOS開發」。依已確認 W8 最小範圍完成 fixture 修改、UI 專屬測試、W6 限定回歸與 W8 fixture 測試，並執行唯一隔離 stub 瀏覽器案例：start=1／stop=2，首次接受後 503、同 tab pending 保存／還原、合格終態後原命令明示 retry、確認後清除、完整 metadata 不變。開發自測通過，正常 shutdown 與原始證據已封存；不是指定角色獨立驗收。詳細差異、命令、基線、採證限制與接續見 [W8 handoff](local-sim-bot-control-w8-handoff-20261002.md)。未操作正式服務、產品 DB／憑證、採集／交易、金融政策、Git 或 Yaozi 業務。
