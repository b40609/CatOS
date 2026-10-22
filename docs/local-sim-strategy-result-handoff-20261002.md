# 本機自動策略成果工作包交驗

更新：2026-10-02。狀態：實作及開發自測完成，待指定 `chatgpt-web/gpt-5.6-sol` 獨立驗收；沒有本工作包 acceptance 或 Git 操作。

## 範圍與結果

依使用者「同意 執行下一工作包」接續自動策略本機端到端交付。既有真實 Python Worker → Supervisor → FakeExchange → SQLite 成交路徑已接通，本包補齊停止後的 durable 結束帳戶快照，以及執行頁可讀成果與歷史還原；沒有新增金融政策。

- 完成或停止，在最後一根完整處理的 K 線邊界，透過原 Supervisor writer 讀取 durable 成交投影，保存 `final_account` 事件。停止保留部位；不清倉、不釋放 ownership。未開始處理即停止，不建立帳戶快照或 DB。快照失敗記為 failed，不冒充正常停止。
- 成果顯示案例、進度、收尾、部位、平均成本、餘額、權益、損益、手續費、資金費、評價價格及最後觀測風控。金額逐字顯示 Decimal 字串，沒有 Float 換算；舊案例缺快照或欄位則明示缺失，不補零。
- 評價沿用最後完整處理 K 線的收盤價；風控是既有最後觀測，沒有宣稱成交後重算風控。原始事件仍可展開。
- 明示命令確認後選取其案例；一般 GET 保留使用者選取的歷史案例，切頁／刷新不發送控制 POST。既有 pending／原 ID 重送規則保留。
- 成果面板支援三欄／兩欄／手機單欄。固定 SMA 合成模板仍為 2 根預熱＋8 根正式 K 線；不宣稱任意策略排程、持續無人值守或 Demo／Live 能力。

## 本包來源

正式來源：[runner](../catos/local_sim_control_runner.py)、[前端](../frontend/workspace/simulation.js)、[現行執行頁樣式](../frontend/workspace/desk.css)。驗證來源：[Python 測試](../tests/test_local_sim_control.py)、[JS 測試](../tests/test_simulation_ui.cjs)、[隔離真實 Worker fixture](../tests/simulation_result_fixture.py)。fixture 使用新隔離資料根及自動分配 localhost 埠；研究 GET 為空資料 stub，simulation 是真實服務及 Worker。

沒有修改 controller／API、產品 schema、R4 runtime 或其他工作目錄。曾放在未使用 `workspace.css` 的新增樣式已撤回，最終樣式位於 `desk.css`。

## 實際驗證與證據

[證據索引](../outputs/workspace-auto-strategy-result-20261002/index.md)、[來源 hashes](../outputs/workspace-auto-strategy-result-20261002/source-hashes.json)、[案例與命令摘要](../outputs/workspace-auto-strategy-result-20261002/summary.json)、[唯讀 storage 核對](../outputs/workspace-auto-strategy-result-20261002/storage-checks.json)、[退出核對](../outputs/workspace-auto-strategy-result-20261002/cleanup-checks.json)、[inventory](../outputs/workspace-auto-strategy-result-20261002/inventory.json)。這些是開發自測，不能改稱指定角色獨驗 PASS。

- `python -B -m unittest tests.test_local_sim_control tests.test_workspace_f1`：51/51 PASS，見 `python-tests-fixed.txt`。涵蓋完成／停止、預熱／未啟動、整個事件收尾、durable 還原、快照失敗與 Worker 失敗。
- `node --test tests/test_simulation_ui.cjs`：最終 15/15 PASS，見 `ui-tests-final.txt`。涵蓋精度、歷史缺失、異常收尾、確認後選取及既有 pending 行為。
- 真實瀏覽器新增 **4 個案例、start=4／stop=1，全部控制 POST 202**。第二 fixture 的 3 筆歷史副本不算新增案例。完成 3 筆，停止 1 筆；保存 DOM、完整終態、命令與截圖。
- 四個原始案例 DB 以 SQLite `mode=ro` 核對：integrity=ok，成交與委託筆數一致、全部 FILLED、固定 tag 正確；數量／價格／費用及委託金額欄位為 TEXT。費用以 Decimal 加總與快照一致，ownership 部位與快照一致。沒有宣稱全量帳戶對帳獨驗。

| 案例 | 終態 | 正式 K 線／成交 | 部位 | 權益 USDT | 手續費 USDT |
| --- | --- | --- | --- | --- | --- |
| `77db4721fed64992b4a5282e56ad5e25` | completed | 8／4 | 0 | 999.91375990 | 0.00404010 |
| `6c979b8ae2d645eaa59253e8d58cec2d` | completed | 8／4 | 0 | 999.91375990 | 0.00404010 |
| `04d1337b368d4f7f8d1214446515c375` | stopped | 1／1 | 2 | 1000.01837970 | 0.00102030 |
| `fbe0990e65004bb5b250856798833ccf` | completed | 8／4 | 0 | 999.91375990 | 0.00404010 |

第一 fixture：127.0.0.1:58434、PID12440、instance=`2dc1cf3fbd2c4d5c93dade7286af6e92`；第二：127.0.0.1:53326、PID13772、instance=`5dd4cdab73264dd3b1230f532418548c`。控制 build 均為 `fbb93bc671611eb50d8527e1d18c42fc53570be6650437671051d80cac96979d`。兩次專用 shutdown 均 HTTP200、launcher exit0；owner_closed=true、active=null、全部 cleanup／worker_closed=true，兩個 listener、owner 與實際 Worker PID46228／47212／41596／23640 均消失，沒有 forced kill。

第二 fixture 重新開啟第一 fixture 已正常收尾的歷史副本，停止快照可讀；其命令日誌只有使用者明示的一次新 start。新命令自動選取新案例的修正經瀏覽器確認，完成後仍可選回停止歷史。

## 修正經過與限制

- 首輪 Python 1 個失敗：未開始即停止時，快照呼叫參數提前引用未初始化 config。加上完整事件存在檢查後 51/51 通過；失敗日誌 `python-tests.txt` 保留。
- 第二個瀏覽器案例原想在活動中停止，採證等待條件誤用「執行中」，實際 UI 是「運行中」，錯過短程窗口；沒有送出 stop POST，該筆正常完成。第三筆才在 1 根／1 成交停止。總數按原始命令記錄，沒有隱藏額外案例。
- 初版成果樣式誤放未載入的 CSS，導致摘要裁切；改至 `desk.css` 後，桌面三欄完整可見，手機單欄沒有水平溢出。舊截圖保留，最終畫面見 `final-browser/stopped-final.png`／`mobile.png`。
- 最後 CSS 修改時 fixture 已無活動案例。重新載入後 workspace 正確顯示 restart_required=true（loaded=`4e1ea52a66f5d6d3d343eb5e26a838e8d067c3c8bd3c53c4520d5c446237df8b`，current=`9abec4e05d337304fc3e5b86196869d3eb109a6d939bd6db22ef67fddd7dbead`）；僅唯讀確認最終樣式／歷史，未重啟或新增控制案例。控制 build 不包含前端 CSS，不能以其一致宣稱 workspace loaded=current。
- 重算 frozen R4 runtime SHA=`ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`，與歷史一致；未重跑 R4 或核對正式 8770／8771 owner／build／instance。
- 沒有操作正式服務、既有產品 DB、憑證、採集、Demo／Live、recovery／resume、schema／latch 或其他工作目錄。沒有執行任何 Git 命令；既有未提交內容依先前交接保留，本輪未核對 Git 狀態。

## 接續

建議換對話交指定 `chatgpt-web/gpt-5.6-sol`：依 [current-handoff](current-handoff.md) 唯讀核對本包來源、inventory、原始命令、DB 與終態／退出證據；核准範圍內做最小必要驗證，不因交接新增控制案例。保存獨驗結論並同步入口。Git 另須使用者明確授權；不固定衍生 W9 小片。
