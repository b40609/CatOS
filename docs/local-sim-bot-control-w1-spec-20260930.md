# W1：本機模擬 Bot 啟停契約評估

更新：2026-10-01（台灣時間；檔名沿用 09-30 開片日期）。階段：assessment／spec 完成，使用者已回報驗證；文件尚無獨立審查明細，不推定驗證者或測試結果。使用者已同意執行「本機模擬 Bot 啟停契約評估」；本片只交付規格，不代表以下 API、控制器或按鈕已實作，也不授權 Demo／Live。

## 目標與現況

正式 8770 工作台已完成獨立驗收，機器人管理仍只讀 R4。下一個最小成果是從該頁明確啟動、觀察及停止一次短程合成模擬；不將這個成果稱為常駐策略管理或實盤 Bot。

核對的程式依據：

- `catos/workspace_api.py`：正式 app 沿用研究 lifespan；`runtime_controls=[]`，只有 R4 快照 GET，preview 沒有自己的 writer。
- `catos/research_api.py`／`research_service.py`：研究任務有自己的單服務與輸出鎖；它不是交易 Supervisor，不將模擬交易塞進研究 job。
- `catos/supervisor.py:235`：`start()` 為 single-use，取得帳戶鎖與 DB 綁定；`process_bar()` 要求先合成對帳。`close()`（990 行）等待 writer 收尾並關 Worker／Journal，不清倉，也不呼叫 `release_contract()`。
- `catos/journal.py:817`：釋放合約要求空倉、委託終結及新鮮對帳；Worker 死亡與 runner 結束不能代替該證據。
- `catos/local_sim_r4.py`：已有固定 SMA、合成 Closed Bar、FakeExchange、Decimal 成交及單 Supervisor writer。R4 runner 寫固定證據根目錄，不能直接當新 Bot 控制 API；原 manifest 列出的程式與八小時證據保持凍結。

行號為本片讀取時定位，後續以實際函式為準；未核對 Git HEAD／status，不提供新提交基線。正式入口驗收引用 [交接](workspace-formal-entry-handoff-20260930.md)，本片未重驗其測試或瀏覽器。

## 具體失敗情境與最小方案

| 失敗情境 | 建議做法 | 最小驗證成本 |
|---|---|---|
| 雙擊、HTTP 回覆遺失或兩個頁面同時啟動 | 一個控制槽，啟動 request_id 持久化，重送回同 run；不同 request 在占用時拒絕 | 控制器併發與 API 重送測試 |
| 頁面切換／關閉誤停策略 | 排程 task 由 app 管理；HTTP request 只提交命令，瀏覽器不持有 task | GET／導航及 client teardown 期間 task 繼續的整合測試 |
| 停止時截斷 COMMIT／ACK／合成成交 | 設停止旗標，當前事件完整收尾後不接下一根；不 cancel 金融操作 | 可控制事件邊界的測試，核對 receipt／fill 無重複 |
| Worker 或 writer 尚未關閉便顯示已停止 | close 成功且 Worker 結束才回終態；不確定則 recovery_required | 故障替身與少量真實 Worker 清理測試 |
| 服務重啟後猜測舊 run 已完成 | 非終態紀錄一律 recovery_required，阻擋新啟動，不自動續跑或接管 PID | 新服務讀入殘留 starting／running／stopping 測試 |
| 新功能改寫已驗收 R4 | 新輸出根、新合成 account_id／DB，不改 frozen runtime | 暫存根測試及 R4 範圍不變核對 |

建議同一 8770 app 內新增小型 `LocalSimControlService`，只負責命令、單槽、證據與排程；不是另一個交易出口。由新 runner 組合既有 `LocalSupervisor`／FakeExchange，所有交易、風控及 SQLite 寫入仍只經該 run 的 Supervisor。可調用 R4 中既有純投影／合成證據 helper，不能修改其檔案、執行八小時 profile 或寫入 R4 目錄。

控制器採 asyncio task 與現有 app lifespan 組合，不新增常駐服務、外部 broker 或 runner 父程序。Worker 維持既有獨立 Python 程序、環境白名單及 JSON IPC；不匯入策略到 Web／Supervisor，不複製父程序完整環境。

## 建議首個實作邊界

- 一個固定 Bot 模板、核可 SMA／既有合成資料，2 根預熱＋8 根正式，每根等待 1 秒的短程 profile。沿用 R4 smoke 的設定與 next-open 成交假設；明示 wall-clock 加速與合成 15m K 線不同。不是八小時驗收。
- 不提供任意策略、檔案路徑、帳戶、合約、時距、參數或風控設定；研究草稿不能直接變成可執行 Bot。
- 每次啟動建立新的 `sim-control-<run_id>` 合成帳戶與 `outputs/local-sim-control/<run_id>/state.sqlite3`，`require_new_database=True`；同帳戶固定 DB 綁定不變。新 run 是獨立測試案例，不是舊帳戶重啟、權益重設或 latch 解除。
- app 級固定輸出鎖保證該控制根只有一個命令／metadata owner；沿用標準函式庫 file lock 方式，不偷接管、不刪鎖檔。每個 DB 僅其 Supervisor 的單 thread writer；控制器只寫 JSON／JSONL metadata，不建第二帳本或新增既有 DB schema。
- 控制器鎖失敗、metadata 缺損或讀取錯誤時，控制能力顯示 unavailable／recovery_required，研究及既有 R4 閱讀仍可用。不得忽略錯誤後啟新 run。
- 啟動前保存 request_id、固定設定、run_id、來源 digest 與 starting 狀態；金融字串使用 Decimal／TEXT，tag、cross／net、原子額度、UNKNOWN、鎖存與單合約單 Bot 全部沿用。
- 記錄上限建議 100 個 run；滿額拒絕新啟動。本片與首個實作均不自動刪除或清理資料。

這是限制功能的建議契約，尚未實作；不新增安全保證。仍為受信策略與程序故障隔離，不宣稱 OS 安全沙箱。

## 狀態與停止語義

| 狀態 | 可接受操作／意義 |
|---|---|
| idle | 尚無占用；可啟動新的獨立案例 |
| starting | 新 run 已持久化，建立 Supervisor、合成對帳及預熱；可提出停止 |
| running | 固定 Closed Bar 排程；可提出停止 |
| stopping | 停止要求已接受；拒絕新 run，等待事件及資源收尾 |
| completed | 全部 8 根結束、證據保存且資源關閉；不是 R4 PASS |
| stopped | 人工停止已收尾；不是平倉、委託撤銷或合約釋放 |
| failed | 執行異常已保存，且資源關閉可確認；保留原 DB／部位／reservation／latch |
| recovery_required | 關閉／落盤不確定，或重啟發現非終態；禁新啟動，不自動清除 |

只有 completed／stopped／failed 且 cleanup_confirmed=true，單槽才可接受另一個**新帳戶案例**。不對原帳戶執行 release、re-arm、resume、cancel 或 flatten；既有 ownership 與 UNKNOWN 保留。控制槽空閒不等於原合約所有權已釋放。

停止只禁止開始下一個事件。若要求抵達時該事件已開始，該事件仍可能完成決策、提交、ACK、FakeExchange 派送與成交；應在 API／按鈕說明中明示「完成目前事件後停止」。預熱也在事件邊界停止。等待下一根期間以停止旗標喚醒，不等待完整排程間隔。

202 回覆僅表示停止命令已接受。前端持續顯示 stopping，超過 5 秒顯示「仍在收尾」，不偽報 stopped、不因 UI 逾時 kill Worker 或搶走 writer 鎖。原 writer 永久卡住無法保證限時終止；保留禁啟動狀態與錯誤。普通服務 shutdown 用同一停止／收尾路徑；強制終止、主機故障不保證收尾，下一次啟動進 recovery_required。

recovery_required 的人工判讀、舊 run 恢復與解除流程留後片，不提供讓使用者按一下繞過未知帳務的按鈕。沒有 OS orphan 自動辨識／接管，也不依 PID 不存在便宣稱帳務已恢復。

## 建議 API 與頁面契約

新命名空間 `/api/workspace/simulation`，與 `/api/workspace/local-sim` 的 R4 唯讀證據分離。

| 介面 | 契約 |
|---|---|
| GET `/version` | loaded／current build、instance、mode=local-sim-synthetic、capabilities、slot 狀態；版本不合禁新啟動 |
| GET `/runs` | 有界 run 清單，明確包含 control_state 與 cleanup_confirmed |
| GET `/runs/{run_id}` | 持久化狀態、停止要求、bounded events／來源／最後訊號與合成成交；GET 無 mutation |
| POST `/start` | 僅 JSON `{request_id, template_id}`；template_id 固定 `sma-synthetic-smoke-v1`，request_id 為 32 位小寫 hex；首次 202，同 ID 同本文回原 run，不同本文 409 |
| POST `/runs/{run_id}/stop` | 僅 JSON `{request_id}`；首次接受 202，重送及已終態回原 run 的當前狀態，不重新啟動或改寫終態 |

start 成功回覆前先保存命令綁定；失敗不得留下未追蹤的 task。若寫入結果不確定，回錯誤並阻擋新啟動；重送查既有 request_id，不偷偷生成第二帳戶。100 個紀錄內保留命令綁定，重啟後對終態啟動命令的重送仍回原 run；對殘留非終態回 recovery_required，不重新啟動。

slot 占用／不同命令啟動衝突回 409；未知 run 404、契約錯誤 422、metadata／控制器不可用 503。拒絕未知鍵、超過 8 KiB body、任意路徑、Demo／Live。沿用 localhost hostname／Origin／JSON 檢查與明確版本 header；start 要求 loaded build／instance 相符，stop 即使 source 版本漂移仍可對同 instance 的已知 run 接受。舊 instance 命令不可作用於新服務。所有金融數值原字串傳遞，前端不計算帳務。

機器人管理頁新增「啟動短程模擬」「停止模擬」及當前控制槽。按鈕以後端能力／狀態啟閉；HTTP 回覆遺失時保留同 request_id 重試，不換 ID。R4 固定摘要與歷史選取保持原行為，新控制 run 不覆蓋 R4 驗收狀態。首頁只讀；切換、刷新、關頁與 layout 操作都不提交命令。8771 preview 不代理新增 mutation，明示只能到正式 8770 操作。

## 實作與驗收切片

1. **W2 建議範圍**：新 controller／runner、正式 app lifespan 與窄 API、專屬 tests；使用暫存輸出根與合成資料。先交 API 閉環，不改六頁 UI。不修改 frozen R4 runtime、不重啟現行服務以測試。
2. **W3 建議範圍**：W2 驗收後才接機器人管理按鈕及狀態，最小人工導航；不加 Bot 配置中心或長跑調度。

W2 必要測試：重複與併發 start、異本文衝突、落盤失敗不留 task；停止在 starting／等待／事件在途三個邊界；stop 重送／終態重送；Worker 真實退出及 close 不確定；source 漂移禁 start 仍可 stop；新服務讀入殘留非終態阻擋；持久化 request_id 跨服務重送；兩控制器競爭輸出鎖；GET／client teardown 不改 task；完整短程合成 run 的 Decimal／tag／單 writer／對帳與預熱。測試僅新建暫存 DB，控制器所有權與 Supervisor 帳戶鎖分別核對。

只執行新模組專屬測試及受影響 workspace／lifespan 測試；不得順帶重跑 R4 或全市場回測。本 spec 完成不構成上述測試已通過。實作自驗及指定 5.6 Sol (Web) 獨立驗收／Git 分工維持；提交、push、服務切換與資料清理不由本規格額外授權。

## 本片交付與後續確認

2026-10-01 接續更新：W2 實作與開發自驗完成，指定 5.6 Sol (Web) 已獨立驗收 50/50 PASS，詳見 [W2 交接](local-sim-bot-control-w2-handoff-20261001.md)。W3 依本規格完成 UI 實作與開發自驗，指定 5.6 Sol (Web) 再獨立重跑 UI 11/11＋workspace 22/22，共 33/33 PASS；preview mutation 隔離亦核對通過，未發現阻斷缺陷，詳見 [W3 交接](local-sim-bot-control-w3-handoff-20261001.md)。取代下方歷史「待使用者指示 W2」狀態；未授權切換現行服務，未重跑 R4。

本片完成：讀取既有契約與程式、列出具體失敗情境、最小方案、停止／重啟限制、API 與等比驗收成本；僅新增本文件並更新接續入口。未修改程式、未啟動模擬、未讀寫既有 DB、未核對 Git 或執行測試。

2026-10-01 使用者回報「已驗證」，取代前述待審查的接續狀態；尚無獨立審查明細或提交編號。本片不自行新增驗收證據；下一步由使用者指示 W2 實作。新起點限定短程模擬、停止不清倉、非終態重啟阻擋；這些為本片提出的產品契約，不改既有交易金融政策。若要長時間運行、同帳戶 resume、清倉式停止或 recovery 解除，另訂具體切片與必要決策，不能由本片推導為已授權。
