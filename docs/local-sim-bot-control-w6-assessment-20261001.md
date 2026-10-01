# W6 提案：切頁／關頁／重送最小驗證

2026-10-01（台灣時間）。提案初版依「先不執行案例」完成；其後使用者明確授權「同意由 6.1 Sol 執行 W6，先 B 後 A，依提案限定範圍」，取代執行／fixture 尚待授權狀態。A／B 已執行完成：B 為前輪證據；本輪經使用者固定授權恢復既有 localhost 服務、唯讀建立新有效基線後完成原 A，開發證據核對 36/36 PASS。詳見 [W6 執行交接](local-sim-bot-control-w6-handoff-20261001.md)。服務恢復固定授權已寫入 AGENTS.md，同範圍不再詢問；以下契約中的缺失服務「不重啟」限制由此後續授權取代，recovery／不合格基線仍不得解除或啟動案例。尚待指定角色獨驗，Git 未授權；不延伸 W5 或三片 Git 的例外授權。

## 缺口與現行契約

W5 已取得正式 UI 啟動與 reload 後自然完成的歷史證據，未測切頁、關頁或重送。W3 的導航與回覆遺失測試分別屬 stub 瀏覽器及單元證據，不等於正式服務的新驗證。

本輪讀取 W1、W3、W5 與現行 `frontend/workspace/simulation.js`、`catos/local_sim_control.py`、UI 測試及 fixture：

- UI 先將 path、body、build、instance 存入 `catos_simulation_pending_v1`，確認 POST 回覆後才移除；GET、refresh 與 pending 還原不送命令。
- sessionStorage 僅承諾同一 tab session。關閉該 tab 後，新 tab 以後端清單找回 run，不承諾找回待確認命令；不要求新 tab 顯示「重送原命令」。
- 後端相同 start request_id／template 回傳既有 run，包含終態；不建立第二個 task／帳戶案例。重送仍須相同 build／instance。
- 固定真實短程約十秒，不為瀏覽器操作延長 profile。現有 fixture 可保持 running 等待 stop，但未提供「後端接受、僅第一次回覆不可用」的故障模式。

實際失敗情境為導航或關頁誤觸 stop、回覆不確定時產生第二個 run、還原 pending 自動 POST。建議一個正式案例加一個隔離 stub 案例；不新增正式服務機制或帳務政策。

## A：正式服務，單一新案例合併三項驗證

前置限定唯讀核對 8770／8771 owner、workspace／research／simulation version、instance、slot=idle、容量及無在途研究；保存完整研究 run ID／狀態、R4 摘要與凍結 SHA。若漂移、非 idle、unavailable 或 recovery_required，不啟動、不重啟或解除。

| 步驟 | 最小操作與通過條件 |
|---|---|
| 啟動 | 正式 `/workspace/execution` UI 點一次 start；保存送出前 storage 與實際 POST 的 path／body／build／instance，取得新 run_id。確認已 starting／running，不能只靠畫面點擊推定接受。 |
| 切頁 | 同 tab 經側欄到設定頁、再回機器人管理；記錄時間與同 run 的活動狀態。導航期間沒有額外 start／stop POST。 |
| 關頁 | 確認同 run 尚在 starting／running 後，只關本次驗證 tab；由與該 tab 無關的唯讀 GET 觀察同 run 繼續更新或自然終態，再新開正式頁讀回同 run。保留關頁時點與前後事件／bars，證明關頁發生在執行期間。 |
| 重送 | 待該 run 自然 completed，以已保存的原始命令明示重送一次 start POST，帶相同本文與 build／instance；應回同 run_id／既有終態，清單新增總數仍為一，事件／bars／fills／finished_at 不變。這是正式 API 冪等證據，不宣稱點擊 UI 重送。 |

總額度：正式 start POST 最多兩次（首次＋同命令重送），唯一新 run；stop POST 為零。原始命令已確認時 UI 會移除 pending，因此不回填 storage 來偽造正式 UI 重送。

關頁後即使很快 completed，若關頁前已證明活動中、後端完成時間晚於關頁且資料連續，可判定本案例關頁未中止。若導航耗盡窗口、關頁前已 completed，對應項目記「未觀測」，保留案例且不補開第二個 run。若工具無法可靠保留命令、關頁時點或跨 tab 請求證據，先回報證據缺口，不執行無法證明的步驟。

終態要求 completed、2 warmup＋8 bars、cleanup_confirmed=true、worker_closed=true、error=null，slot=idle／active_run_id=null。固定輸入與來源未變時，比對歷史參考 4 fills、fees=`0.00404010`、equity=`999.91375990`，保留 Decimal 原字串。前後 owner／instance、完整研究清單及 R4 摘要／凍結 SHA 保持；不開舊 DB、不重跑 verifier，不宣稱 ownership 釋放或逐列帳務重驗。

## B：隔離 stub，UI 回覆不確定與明示重送

待授權後才為專用 fixture 加最小故障模式：第一次 start 先交給 controller 正常接受並保存唯一 run，再只在該 fixture 將回覆轉為不可用；重送回正常回覆。僅綁定 `127.0.0.1` 隨機埠、新隔離 metadata、stub runner，無 Worker、交易 DB 或正式服務攔截。這驗證「後端已接受但 UI 無法確認」，不宣稱實際網路斷線。

本片 fixture 使用新具名輸出目錄保留 metadata／觀測，不直接沿用現有 `TemporaryDirectory` 的退出自動刪除；此支援同樣待授權後實作。

1. UI 點 start 一次，觀察 pending 保留，start／stop 禁用，「重送原命令」可用；後端只有一個 running run。
2. 同 tab 切頁／返回及 reload，pending 完整還原；GET／還原均不自動 POST。
3. 明示點「重送原命令」一次；兩次 start 的 path、body、request_id、build、instance 完全相同，回同 run_id，pending 才清除，後端仍只有一個 run。
4. 明示 stop 一次供 stub 收尾，確認終態及 cleanup，再正常關閉本輪 fixture。只操作本輪可辨識的 launcher，不刪任何檔案；若無法正常停止，保留狀態並回報。

stub 命令額度：兩次同命令 start、一次 stop。保存請求觀測與 storage 前後值；fixture 限定修改應增加一個「接受後回覆不可用、同 ID 回同 run」專屬檢查，不重跑無關套件。以上不是正式 Worker／金融驗證；正式 stop 重送、跨 instance、重啟恢復與多 tab 競爭不列入本片。

## 證據、成本與分工

證據使用新的具名 `outputs/workspace-w6-<識別>/`，正式新 DB 僅由既有 runner 建於自己的新 run 目錄。記錄命令序列、storage、導覽／關頁時點、GET 快照及前後基線；不覆寫 W4／W5／R4，不預設提交 outputs。

成本為一個固定真實短程、一個 stub UI 案例、少量 fixture 支援與限定檢查；不需服務更新、profile 延長、schema、帳務政策或長跑。正式窗口若未涵蓋全部動作，交付部分觀測，不以重跑補齊。本片 PASS 須 A、B 必要觀測均取得，缺項不得用 W3／W5 歷史證據代填。

建議執行次序先 B、後 A，先確認工具能保存命令及觀測，減少耗用正式短程窗口。開發執行者與實際服務／瀏覽器操作由使用者後續授權指定；獨立驗收及 Git 維持指定 5.6 Sol (Web)，舊 6.1 Sol 例外不延伸。驗收只審本輪證據，不另開案例；Git 收尾另授權。

保留可辨識的既有 owner、所有歷史輸出與 DB；缺失服務依後續固定授權恢復，採新有效 owner／instance 基線；不清理、不讀憑證、不採集、不交易、不解除 latch／recovery、不 resume、不碰 Yaozi／其他工作目錄、不 commit／push。若 UI 自動審查拒絕操作，記錄原因，不以 API 替代後宣稱 UI 案例通過。

## 本輪交付狀態

初版僅提案與入口；前輪 B 的 fixture 單元 1/1、證據核對 18/18 PASS。A 原先因缺失服務停止，後續使用者固定授權恢復並建立有效基線，本輪原 A 完成切頁／執行中關頁／獨立 GET／新 tab 讀回／終態同命令重送；唯一新 run、兩次 start、零 stop，證據 36/36 PASS。B 未重跑、不解除 recovery、不 Git；W6 尚待指定角色唯讀獨立驗收。\n
