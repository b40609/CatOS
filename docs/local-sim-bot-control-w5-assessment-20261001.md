# W5 候選：正式頁面完整短程模擬驗證

2026-10-01（台灣時間）。最初為靜態範圍提案；使用者後續已授權「執行 W5，依提案完成限定驗證」。**W5 開發輪限定驗證 PASS，指定 5.6 Sol (Web) 獨立驗收待辦**，詳見 [W5 交接與實際證據](local-sim-bot-control-w5-handoff-20261001.md)。以下保留原提案及評估當時的歷史範圍；「尚未執行」不再代表目前狀態。W4 指定角色 PASS 保持既有證據。

## 具體缺口與最小做法

W2 完整 runner 測試驗證真實 Worker、2 根預熱＋8 根正式、4 fills，但將事件間隔改為 0 秒。W3 實際瀏覽器啟停／導航使用 stub。W4 正式服務使用真實 Worker／FakeExchange，API 提前停止於 2 根正式／2 fills，瀏覽器只核對頁面呈現。因此尚無「正式 UI 明示啟動、原定 1 秒節奏自然完成全部 8 根」的共同證據；這是證據缺口，不判定為程式缺陷。

建議不改程式，沿用正式 8770 的固定 `sma-synthetic-smoke-v1`，只建立一個新合成帳戶／新 DB 案例。透過機器人管理頁明示啟動，在運行期間切頁／返回或刷新，等待自然 completed；不發 stop、不 resume，也不重啟服務。若無法在約十秒的短程窗口內完成導航，明示未觀測，不為補畫面另建 run。

## 執行前與成功條件

1. 執行前限定唯讀核對 8770 owner、三個 version 的 loaded/current build、simulation instance／slot、研究無在途任務及控制容量；若版本漂移、非 idle、命令不確定或 recovery_required，保留現況並停止啟動步驟。
2. 保存前後研究 run ID／狀態、8771 owner／loaded build、R4 既有摘要與 frozen runtime SHA；不開 R4 DB、不重跑 verifier。8771 僅 GET，不發控制命令。
3. 命令由 UI 先保存 request_id／本文／build／instance，再明示 POST。核對唯一 start 命令與唯一新 run；刷新／導航不提交額外命令。回覆不確定只按既有契約處理，不換 ID 啟動另一案例。
4. 新案例應為 completed、warmup_bars=2、bars=8、cleanup_confirmed=true、worker_closed=true、error=null；控制槽回 idle、active_run_id=null，start 可用、stop 停用。
5. 現行 W2 測試的參考結果為 4 fills、fees="0.00404010"、equity="999.91375990"。它們僅為歷史比對值；執行前核對固定輸入／設定未變，再比對新案例原始字串，不能當成已取得的新證據。
6. 前後研究清單與 R4 摘要保持相同，8770／8771 owner 保留，R4 frozen SHA 與基線一致。不以 cleanup 成功宣稱 ownership 已釋放、已清倉或帳務逐列重驗。

證據建議保存於新的 `outputs/workspace-w5/`；若已存在則使用新的具名目錄，不覆寫。模擬資料沿用既有 `outputs/local-sim-control/<新 run_id>/`，保留所有產物，不預設提交 outputs。

## 成本、分工與邊界

成本是一個固定短程 run、少量唯讀 API／程序核對與瀏覽器觀測；無新常駐服務、schema 或帳務政策。不因純驗證重跑 W2／W3 單元測試，若發現具體缺陷再另行最小修正與受影響測試。

開發角色收集上述最小證據；限定獨立驗收及 Git 仍由指定 5.6 Sol (Web) 負責。新 run、實際 UI 控制與任何 Git 收尾須依使用者後續指令執行。若 UI 自動審查拒絕啟動，保留拒絕原因並回報，不能以 API 替代後宣稱 UI 點擊已驗證。

保留 8770／8771、R4 frozen baseline 與研究歷史；不清理、不接交易、不讀憑證、不採集、不修改既有 DB、不長跑、不解除 latch／recovery、不動 CatOS_Yaozi 或 Gemini 原目錄。

提案評估輪僅讀取相關文件、controller／runner／API 與測試定位，並新增本提案及同步入口；當時未執行 Python、單元測試、DB、API／瀏覽器操作或 Git。後續 W5 執行輪的唯讀核對、唯一 UI 新案例與結果另見交接，不把兩輪混為相同驗證範圍。

原執行候選已授權並完成；下一步為指定 5.6 Sol (Web) 的 W5 限定唯讀獨立驗收，不另開 run。
