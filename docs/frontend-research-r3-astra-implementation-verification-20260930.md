# R3 Astra 第二片實作與驗證證據

日期：2026-09-30。範圍只含 R3 inspected/approved fixed strategy artifact、MCP 綁定、client compatibility 與 focused verification。這不是 5.6 Sol (Web) 獨立驗收。未 commit、未 push；未碰交易、OKX、真實憑證、Demo/Live 或既有 DB/schema；R4 未開始。

## 實作

新增固定 manifest `catos/research_artifacts/sma-trend-sma-parameters-v1.json`。registry 只接受 exact schema/version/fields、固定 artifact id/version/entry/source files、`approval_state=approved`、固定 provenance，以及 reviewed SHA256 `3b411bb170572445bc8d4a28c5647387ed08cc3846b03c0c0b36949052f92cf2`。manifest/source symlink、path escape、duplicate JSON field、extra/missing field、unknown/unapproved、hash/version/entry/provenance mismatch 全部拒絕。

靜態審查先後修正兩個實質缺陷。第一個是 immutable version 原先只核對「目前 source hash 等於 manifest SHA」，source 與 manifest 同步改寫可能重定義同一 version；修正為程式內 reviewed digest pin。第二個是原先「驗 hash → 一般 import → 再驗 hash」仍有 TOCTOU 窗口；修正為先讀 allowlisted source bytes snapshot、驗 digest，再由該已驗證 snapshot 建立策略，執行後再次核對 provenance。未新增通用 plugin framework、PKI、第二 registry、第二 writer 或可執行反序列化。

MCP mutation 仍只經 `http://127.0.0.1:8770` 既有 API；exact `{id, version, sha256}` 綁定每次 mutation 重新核對 version/catalog。API/service/worker 再共用 manifest/request/provenance gate。MCP 不 import/instantiate `ResearchService`，不碰 DB，不提供任意 path、URL、Python source、command、credential 或 DB handle。Decimal 研究結果維持 JSON string，Float 只留在既有 Optuna ranking 邊界。

## 實測

- `python -B -m unittest tests.test_research_mcp` → `Ran 6 tests`、`OK`。
- `python -B -m unittest tests.test_research_mcp tests.test_research_optimization_web tests.test_research_web` → `Ran 28 tests`、`OK`。
- `python -B -m unittest tests.test_optimization` → `Ran 8 tests`、`OK`。
- `python -B -m py_compile catos/research_catalog.py catos/research_optimization.py catos/research_mcp.py` → exit 0。
- manifest 實際重算結果與 reviewed SHA 一致；catalog provenance source=`approved_fixed_artifact_manifest`。

官方 MCP Python ClientSession 本輪 post-final-patch protocol baseline：真正 stdio 啟動 `python -B -m catos.research_mcp`，initialize protocol=`2025-11-25`，列出精確七工具，catalog=`sma-trend / sma-parameters-v1 / approved / approved_fixed_artifact_manifest`。mutation 嘗試回傳 `source_changed_restart_required`，原因是 runtime 修改後 8770 尚未重啟。

最後一次可成功 mutation 的官方 MCP E2E 發生在本輪 manifest 已完成、最終 source-snapshot TOCTOU patch 前：backtest `1c65147b4a324f069352e23e79145b28` complete，`net_pnl=-0.79532090` 且型別為 JSON string；optimization `26ee362f1dcc4d17a5497520900c0889` complete，1 trial、objective=`return_pct`；同一 8770 Web/API 可見兩筆 persisted runs。這兩筆不得當成最終 patch 後的重新驗收。

## Client compatibility

Antigravity 1.2.4：CLI 存在，但 `agy mcp list` 因使用者既有 `C:/Users/user/.gemini/config/mcp_config.json` 帶 UTF-8 BOM 而 parse failure。未改該設定，因此未完成 Antigravity initialize/tool flow，也不宣稱成功相容。

DeepSeek Harness 0.1.1-rc.2：新增 `scripts/compat/deepseek-r3-mcp.cordis.yml`；`--dump-config` composition 已確認 `mcp-catos-research` 使用內建 `@deepseek-ai/dsh-mcp-client`、stdio、`python -B -m catos.research_mcp`、固定 cwd、30 秒 timeout、`failOnStartupError=true`。真正 headless agent task 需要 `DEEPSEEK_API_KEY`；未讀取或使用真實 credential，因此只驗到 configuration/launch contract。

## 8770 最終限制

重啟前已再次核對：API PID=`27172`，listener PID=`27172`，command=`python -B -m catos.research_api --port 8770`，local address=`127.0.0.1`，`active_run_id=null`。loaded build=`892fec435cdddb218a4d259432724b702adc20b724b7b01e644526e632686b13`；最新 current build=`1ecdac33b20bee7ea614337b2e4567fdd1bde23068448f464e7925e54ba878f3`；`restart_required=true`。停止／重啟該已知 PID 的執行命令被執行層拒絕，原始結果為 `rejected: blocked by policy`，因此程序未被終止、沒有改 port、沒有啟第二個 writer。

明早 Sol 必須先人工完成該唯一 research process 重啟，再用最終 runtime 重跑官方 MCP mutation E2E；完成前 R3 第二片只能標為「Astra 實作與 focused self-test 完成，待 Sol 獨立驗收」。
