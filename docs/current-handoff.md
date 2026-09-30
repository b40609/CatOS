# CatOS 目前接續入口

更新：2026-09-30。工作目錄 `C:/Users/user/Desktop/CatOS_Astra`。R1、R2 已完成既有驗收；R3 原 5.6 Sol (Web) 驗收後的 frontend whitespace/EOF patch 導致 build drift，已由使用者本輪指定 6.1 Sol 接手補驗與 Git 收尾，取代本任務原模型分工限制。**R1-R3 runtime 基線已提交為 `87d60be`；6.1 Sol 已完成該 build 的 focused tests 與官方 MCP E2E，R4 未開始、未 push。**

## R3 現況

固定製品只有 `sma-trend / sma-parameters-v1`。manifest：`catos/research_artifacts/sma-trend-sma-parameters-v1.json`；reviewed SHA256=`3b411bb170572445bc8d4a28c5647387ed08cc3846b03c0c0b36949052f92cf2`；entry=`catos.research_strategy:RegisteredSMA`；來源只允許 `examples/closed_bar_demo.py`、`catos/research_strategy.py`；catalog provenance source=`approved_fixed_artifact_manifest`。exact fields、immutable version、approval/provenance、path/symlink、source hash 均 fail closed。策略執行改用「已驗證 source bytes snapshot」，避免 hash check 與一般 import 之間的 TOCTOU。

`catos/research_mcp.py` 仍只暴露七工具，mutation 綁定 exact `{id, version, sha256}`，並固定經 `127.0.0.1:8770` 既有 API。MCP 不建立 `ResearchService`／writer、不碰 DB、不接受任意 path／URL／Python source／command／credential／DB handle。8770 仍是唯一 authoritative ResearchService；single active task、build/restart gate、Decimal string、timeout/request/output bounds 均沿用既有 service/worker。

## R3 已提交 build 最終證據

6.1 Sol 本輪重新審查 snapshot loader、重算 reviewed digest，並執行 `tests.test_research_mcp + tests.test_research_optimization_web + tests.test_research_web + tests.test_optimization`：36/36 `OK`。原 5.6 Sol 各組 focused tests／py_compile 仍保留為歷史證據，不宣稱本輪重跑 py_compile。

本輪接手時 8770 無 listener／research_api 程序，故未終止任何程序；完成測試並再核對後啟動唯一服務。launcher PID `28968`、唯一 `127.0.0.1:8770` listener PID `40828`，instance=`f2a3c7d3b3544eeaa2aa42eb8a45d71b`；loaded/current build=`72734a4e3b7d06215a68ea9c5c52af3e898b8fafbee921bc2c87e68deeeff5e5`、`restart_required=false`、`active_run_id=null`。官方 MCP ClientSession initialize protocol=`2025-11-25`，精確七工具與 approved catalog 成功。

目前 build 的 backtest `81c81c8c76cc44e8b5d8baddc4bd0218` complete，`net_pnl=-0.79532090` JSON string；1-trial optimization `4536469217f84b3f915d285fba425d47` complete，seed=42、objective=`return_pct` maximize、唯一 trial period=4、`score_decimal=-0.0990901400` JSON string。MCP／Web 的 task、result、report、完整 runs list 逐一相等，build／strategy provenance 一致；舊兩筆 runs 亦讀回成功。E2E 後 PID／instance 不變、loaded=current、`restart_required=false`、`active_run_id=null`。原 build `1ecdac33...878f3` 的 runs 只作歷史，不能替代已提交版本驗收。

Antigravity 1.2.4：`agy mcp list` 被既有 `C:/Users/user/.gemini/config/mcp_config.json` UTF-8 BOM parse error 阻擋，未修改設定，未宣稱 initialize/tool flow 成功。DeepSeek Harness 0.1.1-rc.2：`scripts/compat/deepseek-r3-mcp.cordis.yml` 已由 `--dump-config` 驗證 composition；真正 headless task 需要 `DEEPSEEK_API_KEY`，依金鑰邊界未讀取／使用，因此只宣稱 configuration/launch contract。

最終證據及驗收腳本欄位誤用／唯讀修正紀錄見 [R3 6.1 Sol 補驗](frontend-research-r3-sol61-verification-20260930.md)。歷史證據見 [Astra 實作](frontend-research-r3-astra-implementation-verification-20260930.md)、[5.6 Sol 驗收](frontend-research-r3-sol-verification-20260930.md)，完整契約見 [R3 handoff](frontend-research-r3-handoff-20260930.md)。本輪僅更新這四份驗收／交接文件，runtime/frontend 無修改；未碰其他工作、真實憑證、交易、採集或既有 DB/schema。

接續：**R3 已提交 build 驗收完成；停在 R3，不進 R4。** 文件收尾依本輪驗收後 Git 授權提交；push 需另有指示。切換新任務時先讀本入口，核對 service 與 Git 現況；不得將歷史 PID／build 當作即時狀態。
