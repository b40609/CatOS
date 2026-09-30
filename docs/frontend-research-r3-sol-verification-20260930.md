# R3 Sol 獨立驗收紀錄

日期：2026-09-30。工作目錄：`C:/Users/user/Desktop/CatOS_Astra`。R3 MCP 第一片與第二片均已由 5.6 Sol (Web) 獨立驗收通過；本輪未讀真實憑證、未碰交易、未修改既有 DB/schema，R4 未開始。

## 第二片驗收結論

固定 `sma-trend / sma-parameters-v1` strategy artifact 的 snapshot loader、immutable reviewed digest、MCP exact binding、最終 runtime restart 與 persisted-runs E2E 均通過。`catos/research_mcp.py` 維持固定 localhost stdio bridge，production 只連 `http://127.0.0.1:8770`；MCP process 不建立第二個 `ResearchService`、writer 或 persistence。

## 獨立程式審查

`catos/research_catalog.py` 的 `_verified_strategy_source_snapshot()` 先讀 allowlist source bytes 並驗 digest；`_strategy_from_verified_snapshot()` 只從已驗證 bytes compile/exec。`load_registered_strategy()` 在執行前後都核對 provenance，digest 同時比 manifest 與程式內 `APPROVED_STRATEGY_SHA256`。`examples.closed_bar_demo` 的 import 由 snapshot module 提供，未發現一般 import 可偷渡未驗策略碼。

reviewed SHA256 獨立重算為 `3b411bb170572445bc8d4a28c5647387ed08cc3846b03c0c0b36949052f92cf2`，與 manifest／程式固定值一致。

## Focused tests

- `python -B -m unittest tests.test_research_mcp`：6/6 `OK`。
- `python -B -m unittest tests.test_research_mcp tests.test_research_optimization_web tests.test_research_web`：28/28 `OK`；`Port 60061 already in use` 為預期測試訊息。
- `python -B -m unittest tests.test_optimization`：8/8 `OK`。
- `python -B -m py_compile catos/research_catalog.py catos/research_optimization.py catos/research_mcp.py`：exit 0。

## 8770 restart 與最終官方 MCP E2E

重啟前唯一 `127.0.0.1:8770` listener 為 PID `27172`，command=`python -B -m catos.research_api --port 8770`，`active_run_id=null`。停止該 process 後重新啟動唯一 research service；Windows launcher PID `3756`，實際 listener/worker PID `26872`。重啟後 `/api/research/version`：instance=`bbcef7dec91349e788aa9f6cab43d112`、loaded/current build=`1ecdac33b20bee7ea614337b2e4567fdd1bde23068448f464e7925e54ba878f3`、`restart_required=false`、`active_run_id=null`、mode=`local_research_synthetic`；netstat 仍只有 PID `26872` 監聽 8770。

官方 MCP `ClientSession + stdio_client` 真實啟動 `python -B -m catos.research_mcp`，protocol=`2025-11-25`、server=`catOS Research R3 v1.29.1`，精確七工具：`research_catalog`、`research_list_runs`、`research_submit_backtest`、`research_submit_optimization`、`research_get_run`、`research_get_result`、`research_get_report`。catalog 回 `approval_state=approved`、`source=approved_fixed_artifact_manifest`。

- 最終 backtest：`1d50884666cd4ede8fa7e08db8ee239e`，`complete`，build=`1ecdac33b20bee7ea614337b2e4567fdd1bde23068448f464e7925e54ba878f3`，engine SHA256=`43d172d8ac82806db289faa2ac481c4335e935b127b2e6fe2a36979e9c80a35c`，`performance.net_pnl="-0.79532090"` 且 JSON 型別為 string。
- 最終 1-trial optimization：`37743f66815d4a2f88d8349b3ba67db9`，`complete`，`n_trials=1`、`seed=42`、objective=`return_pct`、direction=`maximize`；唯一 trial 為 `COMPLETE`、period=`4`、`score_decimal="-0.0990901400"`。第一次送出因 JSON 尾端多一字元被 server 以 `Invalid JSON: trailing characters` 拒絕，未執行；修正 request 後上述 run 成功。
- `research_list_runs` 與 Web `/api/research/runs` 都能讀回上述兩筆最新 persisted runs，run id、kind、status、build id、strategy SHA256 與 `strategy_source=approved_fixed_artifact_manifest` 一致。
- E2E 後 `/api/research/version` 仍為 PID `26872`、build=current=`1ecdac33b20bee7ea614337b2e4567fdd1bde23068448f464e7925e54ba878f3`、`restart_required=false`、`active_run_id=null`。

驗收用 MCP stdio process 最後以 Ctrl-C 人工結束，因此 Python/anyio 印出 `CancelledError`／`KeyboardInterrupt` 並 exit 1；這是驗收 client teardown，不影響已完成 runs 或持續運作的 8770 research service。

第一片舊 runs 與第二片 final patch 前的 `1c65147b4a324f069352e23e79145b28`／`26ee362f1dcc4d17a5497520900c0889` 僅保留歷史，不能替代本次最終驗收證據。

## Client compatibility 邊界

Antigravity／DeepSeek Harness 維持 Astra 已記錄的 compatibility contract 證據；本次 Sol 最終通過依據為官方 MCP server/client E2E。未讀取或使用任何 client credential，也未改寫使用者既有外部 client 設定。
