# R3 6.1 Sol 提交後驗收

日期：2026-09-30。使用者本輪明確指定由 6.1 Sol 接手原 5.6 Sol (Web) 的驗收與 Git 工作；此授權取代本任務原模型分工限制，不擴張交易或 R4 範圍。基線為 `87d60be feat(research): complete R1-R3 localhost workflow`，接手時工作樹乾淨。

## 補驗原因與現況

原 5.6 Sol E2E 使用 build `1ecdac33b20bee7ea614337b2e4567fdd1bde23068448f464e7925e54ba878f3`。其後 frontend whitespace/EOF patch 改變 runtime bytes，提交後 current build 成為 `72734a4e3b7d06215a68ea9c5c52af3e898b8fafbee921bc2c87e68deeeff5e5`；舊證據只代表舊 build，不能稱為已提交版本的最終 E2E。前次停止／重啟被執行層拒絕的紀錄保留，不以其他終止方式重試。

本輪接手時 8770 無 listener，GET version 連線遭拒；CIM 核對沒有 `python.exe -m catos.research_api` 程序。因此無可核對的舊 owner 或 active run，未終止任何程序。完成 focused tests 後，再核對無 listener／research process，使用原指令 `python -B -m catos.research_api --port 8770` 以隱藏視窗啟動唯一服務。launcher PID `28968`，實際唯一 `127.0.0.1:8770` listener PID `40828`，CIM 命令與 API PID 相符。

instance=`f2a3c7d3b3544eeaa2aa42eb8a45d71b`；loaded/current build 均為 `72734a4e3b7d06215a68ea9c5c52af3e898b8fafbee921bc2c87e68deeeff5e5`；`restart_required=false`、`active_run_id=null`、mode=`local_research_synthetic`。`market_status=market_intel_not_found` 為既有情報 DB 缺席，未為此建立或修改 DB。

## 本輪獨立審查與 focused tests

重新審查 snapshot loader：allowlist bytes 快照驗證固定 reviewed digest 後才 compile/exec；`examples.closed_bar_demo` 使用已驗證 module；執行前後核對 provenance，manifest 與程式 digest pin 同時有效。此為受信任固定策略邊界，不宣稱 OS 安全沙箱。

`files_hash(STRATEGY_FILES)` 本輪重算為 `3b411bb170572445bc8d4a28c5647387ed08cc3846b03c0c0b36949052f92cf2`，與 `APPROVED_STRATEGY_SHA256` 一致。

本輪實際執行 `python -B -m unittest tests.test_research_mcp tests.test_research_optimization_web tests.test_research_web tests.test_optimization`：36/36 `OK`。`Port 64668 already in use` 為預期測試案例。前輪各組測試與 py_compile 紀錄保留為歷史，不冒充本輪執行。

## 官方 MCP E2E

透過官方 Python `ClientSession + stdio_client` 啟動 `python -B -m catos.research_mcp`；initialize protocol=`2025-11-25`，server=`catOS Research R3` v`1.29.1`。tools/list 精確為既有七工具；catalog approval=`approved`，source=`approved_fixed_artifact_manifest`。mutation 使用 catalog 的 exact `{id, version, sha256}`，僅執行既有合成資料預設 backtest 與 seed=42、n_trials=1 的 optimization。

| 任務 | run_id | 結果 |
| --- | --- | --- |
| backtest | `81c81c8c76cc44e8b5d8baddc4bd0218` | complete；net_pnl=`-0.79532090`，JSON string |
| optimization | `4536469217f84b3f915d285fba425d47` | complete；1 trial、seed=42、return_pct maximize、COMPLETE、period=4、score_decimal=`-0.0990901400`，JSON string |

兩筆均綁上述 `72734a4e...ff5e5` build、strategy SHA256=`3b411bb...92cf2`、engine SHA256=`43d172d8ac82806db289faa2ac481c4335e935b127b2e6fe2a36979e9c80a35c`。MCP `get_run`／`get_result`／`get_report` 與 Web API 對應回應逐一相等，完整 MCP runs list 與 Web runs list 相等；兩筆 persisted statuses、kind、build、provenance 均核對成功。啟動前已保存的 `1d50884666cd4ede8fa7e08db8ee239e`／`37743f66815d4a2f88d8349b3ba67db9` 亦由新服務與 MCP 讀回 complete。

驗收腳本第一次在兩筆任務均完成後，誤用 trial 欄位 `parameters`，實際 schema 為 `params`，因此該腳本 exit 1；不是產品錯誤。核對實際結果後修正驗收腳本，另開官方 MCP session 只讀回同兩筆任務並完成上述所有 assertions，exit 0；未重送 mutation。官方 client context 正常結束，未手動 Ctrl-C。

E2E 後 version 仍為相同 PID／instance，loaded/current build 一致、`restart_required=false`、`active_run_id=null`。

## 收尾邊界

本輪只補驗與修正文檔，不改 runtime/frontend。R3 已提交 runtime 的最終驗收通過；舊 build 的「最終完成」敘述由本紀錄取代。Antigravity BOM／DeepSeek credential 所限的 compatibility 證據仍維持原明示範圍，不宣稱外部 client 實際 tool flow 通過。未讀真實憑證、未連交易所、未採集、未下單、未改既有 DB/schema；R4 未開始，未 push。
