# R3 MCP 完整交接

日期：2026-09-30。R3 第一片與第二片均已由 5.6 Sol (Web) 獨立驗收通過；本批 R1-R3 由本次 Sol Git 提交收斂。未修改 CatOS_Yaozi、交易、OKX、真實憑證或既有 DB/schema；R4 未開始。Sol 最終證據見 [R3 Sol 獨立驗收](frontend-research-r3-sol-verification-20260930.md)，Astra 第二片證據見 [R3 Astra 實作／驗證](frontend-research-r3-astra-implementation-verification-20260930.md)。

## 第二片最終契約

`sma-trend / sma-parameters-v1` 已遷入固定 inspected/approved artifact manifest：`catos/research_artifacts/sma-trend-sma-parameters-v1.json`。schema 固定為 `catos.research.strategy-artifact` v1，欄位只允許 `schema`、`schema_version`、`artifact_id`、`version`、`sha256`、`entry`、`source_files`、`approval_state`、`provenance`；duplicate／extra／missing field、unknown artifact、version/entry/provenance mismatch、unapproved、path traversal、symlink、source hash mismatch 均 fail closed。固定來源只有 `examples/closed_bar_demo.py` 與 `catos/research_strategy.py`，entry 為 `catos.research_strategy:RegisteredSMA`，reviewed SHA256 為 `3b411bb170572445bc8d4a28c5647387ed08cc3846b03c0c0b36949052f92cf2`。

immutable version 另以程式內 reviewed digest 固定，不能靠「改 source 並同步改 manifest SHA」重新定義同一版本。執行前會取得 allowlisted source bytes 快照、驗證固定 digest，再從已驗證 bytes 建立策略；因此來源在 validation 與一般 import 間被替換時，不會先執行未驗內容。執行完成仍再次核對 provenance，source/engine change 會 fail closed。

MCP 保持七個工具：`research_catalog`、`research_list_runs`、`research_submit_backtest`、`research_submit_optimization`、`research_get_run`、`research_get_result`、`research_get_report`。mutation 綁定 exact `{id, version, sha256}`；每次 mutation 重新查 8770 version/catalog，後端 service/worker 再做共同 manifest/request/provenance gate。MCP process 不建立 `ResearchService`、writer 或 persistence，不碰 DB；production bridge 只允許固定 `127.0.0.1:8770` 並停用 proxy。schema 不接受任意 path、URL、Python source、command、credential、DB handle，也沒有 pickle/marshal 等 executable deserialization。

## 第二片驗收證據

- Sol 獨立重跑 `python -B -m unittest tests.test_research_mcp`：6/6 `OK`。
- Sol 獨立重跑 `python -B -m unittest tests.test_research_mcp tests.test_research_optimization_web tests.test_research_web`：28/28 `OK`；埠占用訊息為既有預期案例。
- Sol 獨立重跑 `python -B -m unittest tests.test_optimization`：8/8 `OK`。
- `python -B -m py_compile catos/research_catalog.py catos/research_optimization.py catos/research_mcp.py`：exit 0。
- 測試覆蓋 approved manifest、hash/version mismatch、unapproved/unknown、extra/missing fields、任意 path/URL/Python 欄位、source-changed、immutable digest、驗證後執行 TOCTOU、exact binding、Decimal JSON string、Web/MCP 共用 busy slot、七工具 surface、MCP 不建立第二 ResearchService/writer，以及 R1/R2 研究 API/Optuna regression。

Sol 獨立審查 snapshot loader：allowlisted source 先讀成 bytes 並驗固定 digest，再從已驗 bytes compile/exec；執行前後均核對 provenance。reviewed SHA256 獨立重算仍為 `3b411bb170572445bc8d4a28c5647387ed08cc3846b03c0c0b36949052f92cf2`。

重啟前已確認唯一 8770 listener 為 PID `27172`、`active_run_id=null`；安全重啟後唯一實際 listener/worker PID `26872`，loaded/current build 均為 `1ecdac33b20bee7ea614337b2e4567fdd1bde23068448f464e7925e54ba878f3`，`restart_required=false`、`active_run_id=null`。Windows launcher PID `3756` 只負責啟動 child，不是第二 writer。

官方 Python MCP `ClientSession + stdio_client` 真實啟動 `python -B -m catos.research_mcp`：protocol `2025-11-25`、server `catOS Research R3 v1.29.1`、七工具全數列出、catalog 回 `approval_state=approved` 與 `source=approved_fixed_artifact_manifest`。最終 patch 後 E2E：backtest `1d50884666cd4ede8fa7e08db8ee239e` complete，`net_pnl=-0.79532090` 且 JSON type=string；optimization `37743f66815d4a2f88d8349b3ba67db9` complete，1 trial、seed=42、objective=`return_pct`、唯一 trial period=4、`score_decimal=-0.0990901400`。MCP `research_list_runs` 與 Web `/api/research/runs` 均能讀回這兩筆 persisted runs，run/build/strategy provenance 一致。最後 `/api/research/version` 仍為 PID `26872`、`restart_required=false`、`active_run_id=null`。

舊的 final patch 前 runs `1c65147b4a324f069352e23e79145b28`／`26ee362f1dcc4d17a5497520900c0889` 只保留歷史，不再作最終驗收依據。

## Client 相容性

Antigravity：本機 `agy.exe` 1.2.4；`agy mcp list` 真實執行時讀既有 `C:/Users/user/.gemini/config/mcp_config.json`，因 UTF-8 BOM 回報 `invalid character '\ufeff' looking for beginning of value`。未修改使用者既有設定，因此沒有宣稱 initialize/tool invocation 成功；CLI 與 stdio registration contract 已確認。

DeepSeek Harness：本機 `dsh` 0.1.1-rc.2；新增 `scripts/compat/deepseek-r3-mcp.cordis.yml`，使用內建 `@deepseek-ai/dsh-mcp-client`、`transport: stdio`、`python -B -m catos.research_mcp`、固定 Astra cwd、30 秒 tool timeout、startup fail-closed。`dsh --profile headless --patch ... --dump-config` 已成功確認 CatOS MCP row 被 compose。Headless 真正 agent task 需要 `DEEPSEEK_API_KEY`；依本專案金鑰邊界未讀取／使用真實 credential，因此未宣稱 DSH initialize/tool invocation 成功。

## 接續

R3 技術驗收與本批 Git 收斂完成；停在 R3 邊界，不得進 R4。
