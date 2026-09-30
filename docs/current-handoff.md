# CatOS 目前接續入口

更新：2026-09-30。工作目錄 `C:/Users/user/Desktop/CatOS_Astra`。R1、R2 已完成既有驗收；R3 第一片與第二片均已由 5.6 Sol (Web) 獨立驗收通過。snapshot strategy loader、focused tests、8770 唯一 service restart、最終官方 MCP backtest + 1-trial optimization + persisted-runs E2E 均已完成。**本批 R1-R3 由本次 Sol Git 提交收斂；R4 未開始。**

## R3 現況

固定製品只有 `sma-trend / sma-parameters-v1`。manifest：`catos/research_artifacts/sma-trend-sma-parameters-v1.json`；reviewed SHA256=`3b411bb170572445bc8d4a28c5647387ed08cc3846b03c0c0b36949052f92cf2`；entry=`catos.research_strategy:RegisteredSMA`；來源只允許 `examples/closed_bar_demo.py`、`catos/research_strategy.py`；catalog provenance source=`approved_fixed_artifact_manifest`。exact fields、immutable version、approval/provenance、path/symlink、source hash 均 fail closed。策略執行改用「已驗證 source bytes snapshot」，避免 hash check 與一般 import 之間的 TOCTOU。

`catos/research_mcp.py` 仍只暴露七工具，mutation 綁定 exact `{id, version, sha256}`，並固定經 `127.0.0.1:8770` 既有 API。MCP 不建立 `ResearchService`／writer、不碰 DB、不接受任意 path／URL／Python source／command／credential／DB handle。8770 仍是唯一 authoritative ResearchService；single active task、build/restart gate、Decimal string、timeout/request/output bounds 均沿用既有 service/worker。

## R3 第二片最終證據

Sol 獨立重跑：`tests.test_research_mcp` 6/6；`tests.test_research_mcp + tests.test_research_optimization_web + tests.test_research_web` 28/28；`tests.test_optimization` 8/8；三個 R3 Python 模組 `py_compile` exit 0。snapshot loader 經獨立審查確認只從已驗證 source bytes 建立策略，reviewed SHA256 獨立重算為 `3b411bb170572445bc8d4a28c5647387ed08cc3846b03c0c0b36949052f92cf2`。

重啟前唯一 8770 listener PID `27172` 且 `active_run_id=null`；安全重啟後實際 listener/worker PID `26872`，loaded/current build=`1ecdac33b20bee7ea614337b2e4567fdd1bde23068448f464e7925e54ba878f3`、`restart_required=false`、`active_run_id=null`、mode=`local_research_synthetic`。官方 MCP ClientSession 真實 initialize，protocol=`2025-11-25`、精確七工具與 approved catalog 成功。

最終 patch 後 backtest `1d50884666cd4ede8fa7e08db8ee239e` complete，`net_pnl=-0.79532090` JSON string；1-trial optimization `37743f66815d4a2f88d8349b3ba67db9` complete，seed=42、objective=`return_pct`、唯一 trial period=4、`score_decimal=-0.0990901400`。MCP `research_list_runs` 與 Web `/api/research/runs` 均讀回相同兩筆 persisted runs 及相同 build／strategy provenance。E2E 後 8770 仍為 PID `26872`、`restart_required=false`、`active_run_id=null`。

Antigravity 1.2.4：`agy mcp list` 被既有 `C:/Users/user/.gemini/config/mcp_config.json` UTF-8 BOM parse error 阻擋，未修改設定，未宣稱 initialize/tool flow 成功。DeepSeek Harness 0.1.1-rc.2：`scripts/compat/deepseek-r3-mcp.cordis.yml` 已由 `--dump-config` 驗證 composition；真正 headless task 需要 `DEEPSEEK_API_KEY`，依金鑰邊界未讀取／使用，因此只宣稱 configuration/launch contract。

完整第二片實作與自測證據見 [R3 Astra 證據](frontend-research-r3-astra-implementation-verification-20260930.md)，R3 全部交接見 [R3 handoff](frontend-research-r3-handoff-20260930.md)，最終 Sol 獨立驗收見 [R3 Sol 驗收](frontend-research-r3-sol-verification-20260930.md)。既有交易授權與決策文件不變；本輪未讀真實憑證、未連交易所、未採集、未下單、未修改既有 DB/schema。

接續：**R3 已完成驗收與本批 Git 收斂；停在 R3 邊界，不進 R4。**
