# W6 執行交接：A／B 執行完成，待指定角色獨驗

2026-10-01（台灣時間）。使用者明確授權：「同意由 6.1 Sol 執行 W6，先 B 後 A，依提案限定範圍」。本輪為開發執行與證據核對，尚未指定角色獨立驗收；Git 未授權。[限定提案](local-sim-bot-control-w6-assessment-20261001.md)。

## B 隔離案例

新增 `tests/simulation_ui_w6_fixture.py` 及專屬 `tests/test_simulation_ui_w6_fixture.py`；未改正式程式。fixture 僅 127.0.0.1 隨機埠 54825、新 metadata、沿用 held stub runner，無 Worker／交易 DB。首次 start 正常接受後只將回覆改 503；此為回覆不可確認，非實際斷網。

唯一 stub run=`12575ca8d48c4650bcc618c90c74c798`，start request_id=`ae82b2673be046779af8bd30eb7e8bbe`，instance=`d8693bdb0eef4af69d43af51a1201e6c`。首次後端 202／UI 503；pending 完整保留，start／stop 禁用、重送可用。同 tab 經設定頁返回、reload，pending 相同，重送前仍僅一次 POST。明示 UI retry 一次後 202、仍同 run、pending 清除。

兩次 start 的 path、本文、request_id、build、instance 完全相同。一次 UI stop request_id=`a443e3e4ef1940d5a3e8bb6779b6b9a1`；最終 stopped、cleanup_confirmed=true、worker_closed=true、error=null、slot=idle／active_run_id=null。stub 的 worker_closed 欄位不是實際 Worker 關閉證據。

模擬命令共兩次 start＋一次 stop。另一次 fixture 專用 `/__test/shutdown` 僅供確認 cleanup 後正常退出，非 simulation 命令；launcher exit=0，54825 不再監聽。輸出與 metadata 全數保留，未刪檔。

使用 computer-use 技能及可用 browser 工具。為觀測 save-before-POST，在該測試 tab 暫加 Storage.setItem 觀測鉤子，先呼叫原 setter 再讀指定合成 pending，未改應用檔案／命令／後端；導航後已消失。console 保存成功時間 `09:21:50.310Z`，早於 fixture 接收 `17:21:50.311856+08:00`。DOMStorage 事件不支援，未重試；B 命令序列採 fixture 原始觀測。首次未 enable Network，因此不宣稱其空事件代表無 POST；收尾時 enable 後唯讀 refresh 成功捕捉 16 事件，供後續 A 工具能力準備。

## 實際檢查與證據

- `python -B -m unittest tests.test_simulation_ui_w6_fixture -v`：1/1 PASS，6.212 秒。保留 `outputs/workspace-w6-fixture-test-8f58e784d5bd4660807b4bd3120d672a/`；此為隔離單元案例，非正式服務或 UI run。
- `python -B outputs/workspace-w6-20261001/check-b-evidence.py`：18/18 PASS，僅本輪執行證據核對。首版檢查誤把 AX「無變化」diff 當完整樹、slot 誤寫 control_state；修正證據讀法與欄位後通過，未改應用／重跑 UI。
- [B 原始證據目錄](../outputs/workspace-w6-20261001/)：storage first／returned／reloaded／cleared、UI 快照、console、backend first／before-retry／retry／final、fixture commands.jsonl、pending／stopped PNG、正常退出紀錄。

## 歷史：A 前置阻擋（已由後續授權恢復取代）

B 結束後執行唯讀 `collect.ps1 before`，owner 檢查未通過。逐一核對 8770／8771 均無監聽，GET version 拒絕連線；入口歷史 PID 39200／5512 均不存在，退出原因不明。沒有有效正式前置快照，不能以歷史 build／instance／idle／R4 摘要作本輪基線。

依提案第 20 行「若漂移、非 idle、unavailable 或 recovery_required，不啟動、不重啟或解除」停止 A。正式 start=0／stop=0，沒有新正式 run／Worker／DB；切頁、關頁、終態原命令重送均未執行。`collect.ps1`／`watch.py` 僅為已準備的 A 證據支援，watch 未執行、before.json 未產生。[前置缺口](../outputs/workspace-w6-20261001/a-preflight-unavailable.md)。

W6 整體未 PASS；不可用 B 或 W5 歷史證據補 A。未重啟正式／preview、未讀憑證、未開歷史 DB、未修改 schema／金融政策、未重跑 R4／研究、未碰 Yaozi、未 Git。

## A 接續執行：2026-10-01

使用者回覆「同意 請改規則，以後不需要我授權」。已在 AGENTS.md AUTONOMY 寫入固定授權：既有 localhost launcher／資料根恢復及唯讀新基線不再逐次詢問；先核對空埠、不停止不明 owner。不延伸 recovery 解除、交易、Git、新增案例或其他工作目錄。此決策取代上述 unavailable 時服務恢復須另行授權的狀態，其他案例契約保留。

8770／8771 缺失後使用既有 `python -B -m catos.workspace_api`（preview 加 `--preview`）及既有資料根，以隱藏程序恢復；未停止任何 owner。正式新 listener PID5108，preview PID49164；建立時間分別為 17:45:31.982700／17:45:32.015481。WindowsApps launcher 的實際 Python 子程序命令可執行檔後有兩個空格，collector 初次嚴格空白匹配拒絕；唯讀核對 exe／完整後綴後，僅將空白改為 `[ \t]+`，未改正式程式或允許不明 owner。

### 恢復後唯讀有效基線

`before.json`／`after.json` 的 owner、版本／instance、設定、固定輸入與來源 SHA 保持；動態 observed_at 排除比較。兩埠僅 127.0.0.1 監聽。

| 項目 | 新有效值 |
|---|---|
| workspace build（正式／preview） | `5e59ae5320b83271e5e18c148545b39b9fe89e730387f8b2003a23a89dc14417` |
| research build | `72734a4e3b7d06215a68ea9c5c52af3e898b8fafbee921bc2c87e68deeeff5e5` |
| research instance | `f3fa2652523c43f0aab3b4d3a478058e` |
| simulation build | `33fb635a68420472f276b65eb62aff4db2c1c4043072e1a877144b14f5f8e184` |
| simulation instance | `d76e5fa4c1fb4d24b859537afba9ecb3` |
| 前後 slot／capacity | idle，active=null，start=true／stop=false，unavailable=null |
| 研究 | 26 complete，無 active，完整清單相同 |
| R4 | 原 run `347282b9d0d9433db6a0276209936f60` 摘要相同；32＋2 根／13 fills／0 anomalies |
| 凍結 runtime SHA | `ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65` |

所有 loaded=current／restart_required=false；恢復後 preview 已載入現行來源，舊 restart_required=true 僅為歷史。preview simulation GET 仍 404。R4 risk=unavailable 為既有唯讀摘要欄位且前後相同，不據此宣稱帳戶恢復或解除；A capacity 依 simulation 獨立端點確認。未開 R4／研究歷史 DB，未重跑 verifier／研究。

### 原 A 唯一短程

run=`5975e67dffa34594ab78c1fe4bf475b0`，request_id=`fe83d2cb42b44e48b0e0b025de5e15e3`。

- 原 UI 本文：`{"request_id":"fe83d2cb42b44e48b0e0b025de5e15e3","template_id":"sma-synthetic-smoke-v1"}`。path=`/api/workspace/simulation/start`，headers 為上述 simulation build／instance。storage 保存時間 17:48:10.426，console sequence1032／實際 POST sequence1035，第一次回覆 202。
- 同 tab 設定頁 17:48:10.784，返回 17:48:11.080，同 run 仍 running（0/8）。只關本次測試 tab，關閉完成 17:48:11.124。
- 與 tab 無關的 GET watcher 保存 19 次觀測，關頁後仍 running 並繼續增加 bars；17:48:19.532144 自然 completed。新 tab 選中 `5975e67d · 已完成`，8/8 根／4 fills。
- 終態以保存的原 request 本文／build／instance 明示 API 重送一次，202 回同 completed run；重送前後完整清單相同，包括 events／bars／fills／finished_at。沒有回填 storage 或宣稱 UI 重送。
- 2 warmup＋8 bars／4 fills；Decimal 原字串 fees=`0.00404010`、equity=`999.91375990`。cleanup_confirmed／worker_closed=true、error=null、stop_requested=false。前後舊 simulation run 原紀錄相同，唯一新增 run 為本案；正式 start 共2、stop=0。

A instrumentation 與 B 相同，Storage setter 先正常保存再觀測指定合成 pending，導航後消失。CDP `truncated=true`：初始等候時大量 GET 使較早閒置紀錄被截斷；保存 seq306～1300 包含原 start、切頁／返回活動窗口。不宣稱完整前置網路紀錄；正式服務自恢复日起日誌只有兩次 simulation start POST，皆202，零 stop／其他 POST，另支持總命令數。未為補證重跑案例。

### 本輪實際驗證

`python -B outputs/workspace-w6-20261001/check-a-evidence.py`：36/36 PASS，唯讀核對保存證據。兩次探索性列印因 Windows cp950 編碼失敗，改用 UTF-8 後讀取成功，未觸發命令或影響案例。未改正式程式，不重跑無關單元或 B。

[證據目錄](../outputs/workspace-w6-20261001/) 包含 `before.json`、`after.json`、`a-browser-observations.json`、`a-independent-observations.json`、`a-new-tab.txt`、`a-completed.png`、`a-original-command-retry.json`、`a-retry-response.json`、`a-terminal-before-retry.json`、`a-terminal-after-retry.json`、`a-evidence-checks.json` 及恢復服務日誌。支援工具 collect／watch／retry／check 均留存；retry 已執行一次，不得重跑。B 證據為前輪結果，未重驗。

## 接續與角色

A／B 必要觀測已取得、開發證據核對通過；W6 尚待指定 5.6 Sol (Web) 唯讀獨立驗收，不由本輪開發核對替代。驗收只審保存證據，不另開 run、不重跑 A／B；Git 另需使用者授權，未核對 Git／commit／push。

已同步 current-handoff；建議換對話交獨驗。恢復服務固定授權持續有效，無須再次詢問同範圍。未解除 recovery／latch、未 resume、未讀憑證、未交易／採集／改 schema、未改凍結來源、未清理或碰 Yaozi／其他工作目錄。正式／preview 保留運行，新結果 tab 保留。另保存 `a-completed-details.png`；截圖呈現完成 8/8 根／4 成交，完整 run／cleanup 核對使用保存的 DOM 與 API 證據。
