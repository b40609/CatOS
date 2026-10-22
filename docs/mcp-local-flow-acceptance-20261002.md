# catOS v1 完整本機 MCP 流程獨立驗收

驗收：WorkBuddy（2026-10-02）。範圍：`docs/v1-local-core-handoff-20261002.md` 所載本機核心，含 MCP 不可變 Python 版本、檔案匯入、人工信任／分配／啟動、真 Worker 執行、成果持久化與歷史讀取。

結論：**PASS（附未涵蓋事項）**。程式面與金融不變量逐項通過，並以全新隔離 fixture 獨立重驗；兩項未涵蓋（UI 互動原始證據、外部 AI 客戶端相容）不影響本輪核心判定，但不得對外宣稱已驗。

## 受驗來源與基線

- 來源基線 `outputs/v1-local-core-20261002-dev/source-baseline-final.json`。
- **獨立重算 47/47 逐檔 SHA-256 完全一致，無來源漂移**；`pre-exit-source-check.json`、`delivery-source-check.json` 亦為 `baseline_unchanged: true`。
- runtime build `f791e202bb000bf2cce06433849fd3c86c8d49e0837cb77545ec73cc5b6d39ee`；workspace build `3f261bd0623e56eb23543e22a904616d13f73d372d59bd3cbb79a6b849e78b5e`。與交驗一致。
- Python 3.14.6（與交驗環境相同）。所有 SQLite 為本輪全新隔離 fixture，未觸產品 DB／憑證／provider／正式 8770／8771。

## Git 唯讀核對

- HEAD 未變：`94515687a3d1c87352712402ba1cb63819696a90`。分支 `main`。
- 本輪核心新增檔皆未追蹤（`??`）：`catos/python_strategy.py`、`strategy_library.py`、`strategy_mcp.py`、`frontend/workspace/v1.js`、`v1-core.css`、`tests/test_python_strategy_v1.py`、`test_python_strategy_api.py`、`strategy_v1_mcp_probe.py`、`strategy_v1_evidence.py`。與交驗「未執行 Git」一致。
- 本輪未執行任何 `git add/commit/push/reset/checkout/stash`。

## 逐項核對

### 1. 非預設 Python 策略、父程序不載入、checkpoint、預熱

- 非 SMA 策略：`counter-python` source 為 `self.n % 2` 交替 `-1`／`0`，與 SMA 無關（`fixture-final-evidence.json`）。
- **父程序不載入策略**：`catos/` 無任何對策略原始碼的 `exec`／`eval`；唯一 `exec(compile(...))` 在 `catos/worker.py:29`（Worker 子程序）。`worker_host.py:51-53` 以 `-I -S -B` 子程序 bootstrap `catos.worker.main`。`python_strategy.artifact` 僅 `ast.parse` 驗證結構（`python_strategy.py:59-63`），不執行。
- **預熱無意圖**：Worker `target = None if warmup`（`worker.py:58`）；runner 對預熱 receipt 檢查 `target_position is not None or intent_key is not None` 即 raise（`local_sim_control_runner.py:96-97`）。獨立重驗：warmup targets `[None, None]`、disposition `NO_INTENT`。
- **checkpoint 還原／錯配拒絕**：`worker.py:31-35` 還原後比對 `snapshot_state` 與 `ready`，不一致即 `Python checkpoint restore mismatch`；`Checkpoint.from_wire` 比對 config 即 `checkpoint artifact/config mismatch`。測試 `test_checkpoint_rejects_version_source_parameters_and_bad_restore` 覆蓋版本／參數／原始碼／壞還原四種錯配，重驗通過。

### 2. 不可變版本、MCP 邊界

- **AI 修改產生新版本**：獨立重驗以 `n % 3` 建立 `strategy_id=counter-python, version=wb-evolved`（hash `f75afad7…`）→ 201；原 `wb-counter` Bot 綁定仍為 `8bb79f5f0bca`／`mcp-v1`，**版本／hash／參數不變**。
- 同 `strategy_id` 不同內容 → `immutable_version_conflict`（`strategy_library.py:127-128`）；Bot 綁定寫入即不可變（`immutable_bot_conflict`）。
- **MCP 僅 5 工具**：`strategy_contract`、`list_strategy_versions`、`create_strategy_version`、`list_simulation_results`、`get_simulation_result`。**無 Bot 分配／啟動／停止／解除風控工具**（原始碼與 SDK `list_tools` 實測一致）。MCP bridge 限 `http`＋`127.0.0.1`、禁 proxy（`research_mcp.py:35-39`）。

### 3. 人工控制綁定、模式隔離

- **build／instance 綁定**：`local_sim_control_api.py:49-52` 驗 `x-catos-instance`（否 409 `service_instance_mismatch`）、`x-catos-build`（否 409 `page_version_mismatch_reload_required`）。獨立重驗兩者皆 409。
- **pending 保存原命令**：`v1.js` 於發送前寫 `sessionStorage`，不確定結果僅允許人工重送原命令。同 request_id 同內容重送回原結果（獨立重驗 `same_result=True`）；跨操作／不同內容 → 409 `request_id_conflict`（皆重驗）。
- **刷新／換頁／切模式不 POST 控制命令**：`v1.js:130` 模式切換僅 `render()`；`commands.jsonl` 計數 start=2／stop=1／bots=2／strategies=4，頁面與模式切換未增加控制命令。
- **模式隔離**：`workspace-mode` 選項 local／demo／live；`v1.js:70` 非 local 顯示「尚未開放」並註明「切換只改變顯示，本機 Bot 依原模式執行」；`/strategy-contract` 明示 `modes: local available, demo not_open, live not_open`。獨立重驗 mode=`local` 始可啟動，未假啟動 Demo／Live。

### 4. 金融不變量

- **Decimal／TEXT**：`execution_fills` 的 quantity／price／fee 皆 SQLite `text`（獨立 sqlite3 `mode=ro` 核對，`integrity_check=ok`）。`python_strategy.data` 拒 float（`strategy_data_no_float`，獨立重驗 422）。
- **固定 tag**：所有委託 payload 含 `"tag":"41cb53c54d6dABDE"`（events 與 DB `execution_orders.payload_json` 皆確認）。
- **合約獨佔／停止不清倉**：`retained_run()`（`local_sim_control.py:241-262`）對非零部位或風險原因阻擋新案例。獨立重驗：持倉停止後 final position `-1`、boundary `stopped`，新 start → 409 `simulation_ownership_or_risk_retained`。
- **UNKNOWN／鎖存**：沿用既有路徑，本輪未放寬。真實策略身分：DB `intent_key` 含 `counter-python`＋真實 `artifact_hash`。
- **成果標示模式／Bot／版本**：run config 含 `mode`、`bot_id`、`binding`（artifact／hash／parameters）。

### 5. 完整產品頁與證據充分性

- 產品頁保留：desk.html 側欄 7 入口（首頁／策略／機器人／風險／日誌／Yaozi／設定）＋模式選擇框；回測／優化／Yaozi 標示開發中（`v1.js` feature-notice）。
- **UI 互動證據不足**：交驗文件聲稱以 CUA 完成真實 UI 互動，但 `outputs/v1-local-core-20261002-dev/` **無任何截圖、DOM 快照或 CUA log**。`commands.jsonl` 僅能證明存在控制命令，不足以證明係人類 UI 互動，亦不足以證明模式切換發生。此為**未涵蓋項**，不影響程式面判定。

## 獨立重驗（全新隔離 fixture）

| 項目 | 結果 |
| --- | --- |
| fixture-main 埠／PID | 63109／13612，instance `4081924f…`，正常退出 owner_closed=True |
| fixture-history 埠／PID | 59440／40648，instance `57fbbba7…`，正常退出 |
| 來源 SHA-256 | 47/47 一致 |
| counter（completed） | run `83db5e30…`，8 根／8 成交／部位 0／equity 1000.00385505 |
| hold（stopped） | run `bcd5fa8c…`，3 根／1 成交／部位 -1 保留 |
| MCP 真實 SDK | create 6 次、history 讀取 5 次，工具名一致 |
| 歷史重開 | 與關閉前完全一致，無新控制命令 |
| .py 匯入補證 | 合法 201；缺 hook 422；float 422 |

指令（節錄）：

```
python -c "import sys,unittest; sys.path.insert(0,'tests'); unittest.main(module=None,argv=['check','test_python_strategy_v1','test_python_strategy_api'],verbosity=2)"
python -c "import sys,unittest; sys.path.insert(0,'tests'); unittest.main(module=None,argv=['check','test_ipc','test_worker','test_journal','test_local_sim_control','test_workspace_f1'],verbosity=1)"
python -c "import runpy; runpy.run_path('tests/simulation_result_fixture.py',run_name='__main__')" --output-root outputs/wb-accept-v1-20261002/fixture-main
python -c "import sys,runpy; sys.path.insert(0,'tests'); runpy.run_path('tests/strategy_v1_mcp_probe.py',run_name='__main__')" --base-url http://127.0.0.1:<ready埠> --output <...> --create
```

重驗結果：Python 新增 11/11 通過；受影響回歸 93/93 通過；JS 15/15 通過；`node --check v1.js` 成功。證據存 `outputs/wb-accept-v1-20261002/`（`wb-acceptance-summary.json`、`mcp-create.json`、`mcp-history.json`、`fixture-main/`、`fixture-history/`）。

## 缺陷

無功能性缺陷。

## 未涵蓋事項

1. **UI 互動原始證據缺失**：交驗無截圖／DOM 快照／CUA log；`commands.jsonl` 不足以證明人類 UI 互動與模式切換。建議補一組可複核的互動證據（或明示為未驗）。
2. **外部 AI 客戶端相容未驗**：僅以 MCP SDK 實測 stdio initialize／list_tools／call_tool，未連接真實外部客戶端。
3. **`.py` 匯入互動**：本輪以 API 補證檔案契約路徑，未經真實瀏覽器 `FileReader` 互動。
4. 持續市場模擬、全市場回測、Demo／Live 未驗，且非本輪範圍。

## 判定

**PASS（附未涵蓋事項）**。逐項核心與金融不變量通過並經獨立重驗；未涵蓋項已明示，不得對外宣稱 UI 互動或外部 AI 客戶端已驗。commit／push 待另行明確授權。
