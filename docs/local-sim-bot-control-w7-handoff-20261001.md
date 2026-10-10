# W7：正式 stop 原命令重送執行交接

2026-10-01（台灣時間）。[assessment 與確認範圍](local-sim-bot-control-w7-assessment-20261001.md)先前維持不執行；使用者後續「同意 請繼續」授權依已確認範圍執行單一案例。本輪已完成執行與 38/38 離線證據核對，指定 `chatgpt-web/gpt-5.6-sol` 獨立驗收待進行，不能將開發核對改稱正式獨驗 PASS。未取得 Git 授權，未核對或操作 Git。

## 執行結果

沿用 `sma-synthetic-smoke-v1`，2 warmup＋8 bars、1 秒間隔。UI start 一次；實際 GET 確認 running、warmup_bars=2、worker_pid=39156、bars=1／fills=1 後，UI stop 一次；stopped 收尾確認後，以保存的原 path、原本文及所有已捕獲 headers 重送同 stop 一次，沒有補開 run。

| 項目 | 保存結果 |
|---|---|
| run_id | `4874ffc8cb444bbc898032005a1a848e` |
| start request_id | `ac3fb2aa6c1d486c8037d98510f5c129` |
| stop request_id（兩次相同） | `53417f2ceb64478d8e6199d2f3aba098` |
| 首次 stop | 202／stopping，stop_requested=true，stop_requested_at 非空 |
| 終態／原命令重送 | stopped；重送 202，完整 snapshot 與清單不變 |
| 收尾 | cleanup_confirmed=true、worker_closed=true、error=null、finished_at 非空 |
| 命令總數 | start=1、stop=2、唯一新增 run=1；三次 POST 皆 202 |
| 停止後能力 | slot=idle、active=null、start=true／stop=false、unavailable_reason=null |
| metadata | stop_commands 嚴格等於僅含原 stop ID 的一筆清單；重送前後整份 control.json bytes／SHA256 不變 |

原始 UTC：created_at=`2026-10-01T10:58:10.528413+00:00`、stop_requested_at=`2026-10-01T10:58:12.254567+00:00`、finished_at=`2026-10-01T10:58:12.289435+00:00`。終態 bars=1／fills=1、position=`2`、fees=`0.00102030`、equity=`1000.01837970`、fill price=`102.03`，保留 Decimal 原字串；本片只比較重送前後不變，不重算完整帳務。停止保留部位，不宣稱清倉或 ownership 釋放，也不要求提前停止產生 final_account。

control.json SHA256：`c1e809f53694df9410c33850e5db9ec2d2ef2452a2a64d89615bbbf0c3d569b6`。來源為同 owner 正式控制根 `outputs/local-sim-control/control.json` 的唯讀原檔複本。

## 基線與未漂移證據

- 既有 127.0.0.1:8770 PID5108／8771 PID49164 與 launcher 維持；未恢復或重啟服務。workspace／research／simulation／preview 前後 loaded=current、restart_required=false，build／instance 不變。
- simulation build=`33fb635a68420472f276b65eb62aff4db2c1c4043072e1a877144b14f5f8e184`，instance=`d76e5fa4c1fb4d24b859537afba9ecb3`；research instance=`f3fa2652523c43f0aab3b4d3a478058e`。
- 研究完整 26 筆清單一致、無 active；simulation 舊 3 筆完整 metadata 不變，收尾僅增加本次一筆。R4 完整 manifest／status／events／來源一致，只排除 GET 即時產生的頂層 observed_at（`catos/workspace_snapshot.py:154`）。
- runtime SHA256=`ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`；相關程式、設定、輸入資料 hashes 不變。preview simulation GET=404，本輪 preview 無 POST。

## 證據索引與實際核對

[本輪證據目錄](../outputs/workspace-w7-20261001-stop-replay/)保留原始資料及限定採證腳本，不覆寫 W6 輸出：

- `before.json`／`before-control.json`：前置 owner、版本、來源、完整清單、metadata 與日誌起點；`pre-replay.*`、`gate-raw.*`：重送門檻與原檔。`gate-raw.json`／`after.json` 額外保存 GET 的 raw_json。
- `start-command.json`、`activity-get.json`、`ui-stop-intent.json`、`ui-network.json`：原 UI 命令、實際 running GET、送出時點、202 回覆與 headers。活動命令窗口 truncated=false，能核對先觀測正式 bar 再送 stop。
- `terminal-get.json`、`replay-before.json`、`replay-intent.json`、`replay-response.json`、`replay-after.json`／`replay-after-control.json`、`replay-check.json`：完整終態、原命令重送及嚴格前後比較。
- `after.json`／`after-control.json`、`interval-a-recovery-*.log`：唯讀收尾與本輪服務日誌位元組區間；正式日誌恰好 start 一次、同 stop 兩次，無其他 POST；兩服務區間 stderr 均空。
- `ui-selected-final-dom.txt`／[停止畫面](../outputs/workspace-w7-20261001-stop-replay/ui-w7-stopped.png)：已選中本次 run，UI 顯示可啟動／已停止／1 根／1 成交。較早 `ui-stopped.png` 的詳情仍選中 W6 舊 run，不能拿該詳情當本次終態。
- `verification.json`：38 項本輪離線證據核對皆通過。核對涵蓋活動停止、Worker 收尾回報、命令數、完整 snapshot／清單／metadata／events、唯一 stop 綁定、來源／owner／版本、研究與 R4 不變；不是指定角色獨驗。
- `evidence-sha256.json`：本輪證據檔案大小與 SHA256 清單，清單本身不自我列入。

## 採證修正與限制

三次支援腳本前置檢查在 API POST／replay-intent 建立前中止，依序為 R4 查詢時間差異、PowerShell ISO 時間轉時區、新增 raw_json 使 wrapper 不同；詳見 [執行補記](../outputs/workspace-w7-20261001-stop-replay/execution-notes.md)。修正均只影響採證比較，沒有額外控制命令或案例補跑。before／pre-replay 的 API body 是 PowerShell 解析後值，未保存原始 API 時間字串；舊 run 原 UTC 字串取自 before-control.json，後續 gate／CDP／replay 保存原 JSON。simulation 時間、金融欄位、events 與 metadata 未放寬比較。

離線核對腳本初次讀 UTF-8 DOM 時以 Windows 預設 cp950 失敗，尚未寫出核對結果或日誌區間；補明 encoding 後離線核對 38/38 通過，未重送命令。後段閒置採證 `ui-final-network.json` truncated=true，不能宣稱整輪 CDP 網路事件完整；原活動命令窗口無截斷，總 POST 數由保存的服務日誌區間獨立佐證。

未改正式程式／profile，未跑單元測試、研究／R4 或歷史回測；未開 DB 做離線帳務驗收。授權 local-sim runner 正常產生本次本機 SQLite 寫入，不宣稱零 DB 變動。未接觸憑證、採集／Demo／Live、schema／latch／recovery、清理或其他工作目錄。

## 下一步與分工

建議換對話，由指定 5.6 Sol（Web）對上述保存證據唯讀獨立驗收，直接由原始檔重算關鍵斷言及 hashes；不得執行 `replay-stop.py`、start／stop 或另開 run。所有本片控制命令額度已使用完畢。獨驗完成後再提出下一片；Git 仍須另行明確授權，既有未提交內容維持。

短接續指令：「先讀 current-handoff 與 W7 handoff；以指定 5.6 Sol（Web）唯讀獨驗保存證據，不執行案例或控制腳本、不新增 run、不解除 recovery、不操作 Git；完成後同步入口。」
