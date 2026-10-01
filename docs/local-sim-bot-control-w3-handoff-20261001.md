# W3：短程合成模擬 UI 交接

2026-10-01；使用者授權「同意 執行 W3，依 W1 規格接 UI 與最小自驗」。依 [W1](local-sim-bot-control-w1-spec-20260930.md)，以 [W2 獨立驗收 50/50 PASS](local-sim-bot-control-w2-handoff-20261001.md) 為前置證據；W3 實作、自驗及指定 5.6 Sol (Web) 獨立驗收均完成，結論 PASS。

## 實作

- 機器人管理頁新增獨立短程合成模擬區：啟動、停止、控制槽、案例選取及 bounded events。R4 摘要／歷史仍走原唯讀資料路徑；首頁與其他頁不掛載控制器。
- 按鈕依 simulation version／capabilities 啟閉。preview 不查控制 API、不代理 POST，提示至正式 8770；source 漂移阻擋新 start，保留同 instance stop。
- 命令先保存於 sessionStorage，才 POST；回覆遺失或不符保留原 request_id、本文及 build／instance。只由明示「重送原命令」重送，GET、刷新、切頁與恢復 pending 不自動 POST；跨 instance 禁重送。雙擊不產生第二命令。
- 停止明示完成目前事件後停止、保留部位；stopping 不冒充 stopped，後端 still_finishing 顯示「仍在收尾」。金融值以原字串呈現，不作帳務計算。
- 設定頁 Bot 啟停說明改指向機器人管理頁。控制 API／runner／金融政策未修改。

## 本輪檔案

新增 `frontend/workspace/simulation.js`、`tests/test_simulation_ui.cjs`、`tests/simulation_ui_fixture.py` 及本文件；修改 `frontend/workspace/desk.html`、`desk.js`、`desk.css`、`catos/workspace_api.py`（僅靜態資產 allowlist）、README、W1 接續狀態與 [current-handoff](current-handoff.md)。

`outputs/workspace-w3-preview/stopped.png` 為開發實作輪新建的隔離畫面證據，與既有 outputs 分離，不預設納入提交。W2／正式入口既有未提交內容與其他工作交由指定角色核對 Git；開發實作輪未核對 Git 或提交。

## 最小自驗與證據

| 本輪檢查 | 結果 |
|---|---|
| `node --check frontend/workspace/simulation.js` | PASS |
| `node --test tests/test_simulation_ui.cjs` | 11/11 PASS，91.5234 ms |
| `python -B -m unittest discover -s tests -p test_workspace_f1.py` | 22/22 PASS，1.257 s |
| R4 frozen runtime SHA | `ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`，本輪核對與基線一致 |

UI 單元檢查涵蓋唯讀 refresh／pending 還原、回覆遺失同命令重送、併發點擊、202 stopping、版本漂移、preview、跨 instance、recovery／不可用／離線、storage 失效、503／不符回覆及 Decimal 字串與歷史保留。合計 33/33 PASS；未重跑 W2 runner 或 R4 verifier。

實際 IAB 瀏覽器使用 `python -B -m tests.simulation_ui_fixture`，隔離 `127.0.0.1:51345` 與新 tempfile metadata，runner 為 stub，不建立 Worker／交易 DB。run=`7dca51dfedcd4b95b06d98f932b717ec`：

1. 啟動後顯示運行中，start 停用、stop 可用。
2. 由側欄進設定、返回機器人管理並 reload，仍為同一運行案例；觀測僅一次 start POST。
3. stop 後先顯示停止中；stub 延後 6 秒收尾，完成才顯示已停止、cleanup_confirmed=true，start 恢復可用。
4. 展開最新案例，`equity="1000.000000000000000001"` 完整呈現。最終觀測只有一次 start 及該 run 一次 stop POST。

畫面：[停止終態](../outputs/workspace-w3-preview/stopped.png)。R4 fixture 為空，瀏覽器畫面只核對缺資料呈現，不將它當成 R4 真實證據重驗；既有 R4 行為由受影響 workspace 測試及原資料路徑核對。未目視捕捉 5 秒後的 still_finishing 窄時間窗；該顯示有單元證據。Ctrl+C 結束 launcher 後 listener 仍在，已核對命令列僅停止本輪 fixture Python PID 34636，確認 51345 listener 關閉；測試 tab 已關閉。強制停止不保證 TemporaryDirectory 自動清理，本輪不另刪暫存目錄。

## 限制與下一步

本輪未切換／重啟正式 8770 或 preview 8771，正式服務尚未載入 W3；未讀寫既有 DB、憑證、R4 證據或 Yaozi，未新增 schema、長跑、resume、recovery 解除、清倉、交易或 Git 操作。W2 的真實 Worker／Decimal／tag／writer 驗證屬歷史獨立驗收證據，不能稱為本輪重驗。

不確定命令採保守保留；即使 HTTP 錯誤也不自動換 ID／丟棄。跨 instance pending 阻擋控制，沒有新增人工丟棄或重綁流程；sessionStorage 僅保證同 tab session 內保存，關閉 tab 後由後端持久化 run 提供狀態，不宣稱命令跨 tab 恢復。

## 獨立驗收

2026-10-01 指定 **5.6 Sol (Web)** 依入口與 W1 做限定範圍驗收，未切換 8770／8771、未執行 R4 verifier、未接交易。

```text
node --check frontend/workspace/simulation.js
PASS
node --test tests/test_simulation_ui.cjs
11 tests / 89.0526 ms / PASS
python -B -m unittest discover -s tests -p test_workspace_f1.py
22 tests / 1.060 s / OK
```

本輪獨立測試 **33/33 PASS**。程式審查確認 UI 使用的 `version`／`runs` 欄位與 W2 實際 API projection 一致；實際空槽回覆 `slot=idle`、`capabilities.start=true`、`capabilities.stop=false`。preview 額外探針確認 `simulation.js` 與 execution 頁均 200、`preview=true`，`/api/workspace/simulation/version` 與 `/start` 在 preview 均 404，因此 preview 不代理控制 mutation。

隔離瀏覽器 fixture 成功載入 `/workspace/execution`，畫面顯示短程合成模擬控制區、「可啟動」、start 可用、stop 停用。嘗試執行 start 點擊時遭 OpenAI 自動 UI 安全審查封鎖，本輪未繞道重試；因此開發輪既有 start→導航／reload→stop 的瀏覽器結果仍屬歷史證據，不記成本輪重驗。fixture listener 已關閉。

未發現阻斷缺陷，**W3 PASS**。Git 已核對但工作樹同時含 W2、正式入口與其他歷史未提交內容，本輪未 commit、未 push、未清理。正式 8770 尚未載入 W3；服務更新另依使用者明確授權處理。
