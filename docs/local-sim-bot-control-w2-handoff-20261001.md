# W2 本機模擬啟停實作交接

日期：2026-10-01。依 [W1 規格](local-sim-bot-control-w1-spec-20260930.md)及使用者「執行 W2，依 W1 規格實作與最小自驗」授權完成。實作、開發自驗及指定 **5.6 Sol (Web)** 獨立驗收均完成；Git 收尾仍待後續處理，本輪未提交或 push。

## 交付範圍

- `catos/local_sim_control.py`：app event loop 單控制槽、持久化命令綁定、輸出根鎖、重啟檢查及狀態快照。
- `catos/local_sim_control_runner.py`：固定 SMA 合成案例，2 根預熱＋8 根正式 15 分鐘 K 線，正常事件間隔 1 秒。每次建立新合成帳戶與新 `state.sqlite3`，沿用 LocalSupervisor／FakeExchange 與真實獨立 Worker。
- `catos/local_sim_control_api.py`：窄 API、版本與 instance 綁定、正式 app lifespan 整合。
- `catos/workspace_api.py`：新增 `simulation_root` 注入，預設隔離於 `outputs/local-sim-control`。8771 preview 不掛載或代理控制 API。
- `tests/test_local_sim_control.py`：28 項專屬測試；既有 workspace 測試僅加入暫存 simulation root，避免操作真實 outputs。

未接 UI 按鈕；workspace version 的 `runtime_controls` 仍為空，控制能力由新的 simulation version 提供。研究服務及 R4 唯讀摘要維持原路徑。本輪未重啟、停止或切換 8770／8771；現行程序不因此自動載入 W2。

## API 契約

前綴 `/api/workspace/simulation`：

| 方法 | 路徑 | 用途 |
| --- | --- | --- |
| GET | `/version` | loaded/current build、instance、配置及控制槽 |
| GET | `/runs` | 已保存案例 |
| GET | `/runs/{run_id}` | 指定案例、最近事件及停止進度 |
| POST | `/start` | 固定模板啟動，回覆 202 |
| POST | `/runs/{run_id}/stop` | 事件邊界停止，回覆 202 |

mutation 必須使用 `127.0.0.1`、同來源或無 Origin、`application/json`，並帶入從 version 取得的 `X-CatOS-Build` 與 `X-CatOS-Instance`。body 上限 8 KiB；拒絕未知鍵、重複 JSON 欄位、NaN、任意模板及不合法 ID。

start body 範例（ID 為合成示例）：

```json
{"request_id":"11111111111111111111111111111111","template_id":"sma-synthetic-smoke-v1"}
```

stop body 僅含新的 32 位小寫十六進位 request_id。HTTP 回覆遺失時重送原命令與原 ID；同 ID 異本文、異 run 或異操作回 409。start 綁定先落盤才排程 task；同命令重送回原 run，不重建帳戶。source 漂移禁止新 start，同 instance 既有 run 仍可 stop；舊 instance 命令不能操作新服務。

## 停止與持久化邊界

停止喚醒等待中的 runner；事件在途時完成 decision、COMMIT、ACK、dispatch、成交及對帳，再停止下一事件。服務關閉等待相同收尾，不 cancel task。stopping 超過 5 秒提供 still_finishing 狀態。GET、導航及 HTTP client 關閉不停止案例。

cleanup 關閉 Worker、Journal、executor 及帳戶鎖；不清倉、撤單、釋放 ownership 或解除 latch。只有終態且 cleanup 確認完成才能開始新案例。重啟遇非終態或 cleanup 不確定標記 recovery_required，阻擋新 start；沒有自動續跑、解鎖或 recovery 解除端點。落盤失敗不宣稱成功；未確認的 pending 保留供人工檢查。

`control.json` 僅保存控制 metadata／命令綁定，採 fsync 與原子替換，不是第二帳本。控制根鎖與 Supervisor 帳戶鎖分別處理所有權。上限為 100 runs、每 run 40 筆事件尾端、100 個 stop 命令及 4 MB metadata；不自動清除歷史。損毀、孤立目錄及不一致 metadata 使控制 API 不可用，研究與 R4 唯讀功能仍可使用。異常文字僅保留 exception 類別。

Supervisor 維持唯一 SQLite writer；固定 tag `41cb53c54d6dABDE`、cross／net_mode、Decimal／SQLite TEXT。模型為下一根開盤加明示滑價成交、完整合成 USDT 費用、資金費明示零；不代表 Demo／Live 能力或新增帳務政策。

## 本輪自驗證據

```text
python -B -m unittest discover -s tests -p test_local_sim_control.py
28 tests / 5.166s / OK
python -B -m unittest discover -s tests -p test_workspace_f1.py
22 tests / 0.980s / OK
```

共 **50/50 PASS**。涵蓋併發／重送／持久化失敗、重啟阻擋、鎖競爭、版本漂移、starting／warmup／等待／成交在途停止、HTTP client 關閉及 lifespan 收尾，以及真實 Worker 退出與 cleanup 不確定。全部使用新建暫存資料與模擬交易；Worker 強制退出僅對測試自行建立的子程序注入故障。

完整 runner 測試以間隔 0 秒加速，驗證真實 Worker 的 2 根預熱、8 根正式 K 線及 4 筆合成成交，不宣稱已驗證實際 1 秒節奏或長跑。費用 `0.00404010`、期末權益 `999.91375990`；核對單 writer thread、SQLite integrity、TEXT 金額、COMMITTED inputs、無未終結委託／reservation，以及 ownership 保留。事件在途停止另驗證保留部位 `2`、完成成交而不重送。

本輪讀取 frozen R4 runtime 源碼計算 SHA256：`ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`，與原驗收基線相同。未修改 frozen runtime、未讀寫 R4 DB、未重跑 R4 verifier／soak、未執行全市場回測，未接觸憑證或交易服務。歷史正式服務驗收不是本輪服務存活核對。

## 獨立驗收

2026-10-01 指定 **5.6 Sol (Web)** 依入口執行限定範圍驗收，未切換 8770／8771、未讀寫 R4 DB／soak 證據、未重跑 R4 verifier。靜態核對 controller／runner／API 與 workspace 掛載後，未發現阻斷缺陷；停止事件邊界、cleanup 不確定轉 `recovery_required`、build／instance 綁定及 preview 不掛 mutation 均符合 W1 契約。

```text
python -B -m unittest discover -s tests -p test_local_sim_control.py
28 tests / 4.743s / OK
python -B -m unittest discover -s tests -p test_workspace_f1.py
22 tests / 0.832s / OK
```

本輪獨立驗收 **50/50 PASS，W2 PASS**。測試只使用暫存 simulation／research／evidence 目錄與合成資料；未啟動正式服務、未提交或 push。

## 接續

W2 已完成指定 5.6 Sol (Web) 獨立驗收；Git 沿既有分工，不混入其他工作或 outputs，不 push。下一片可進 W3：僅機器人管理按鈕、命令重送及狀態呈現，維持導航不控制生命週期。服務切換、資料清理、長跑、resume 與交易不在本輪授權內。

建議驗收換對話，先讀 [目前接續入口](current-handoff.md)。
