# 工作包 B 提案：Kill-Switch、HTTP 控制、新風控預設

日期：2026-11-14。基準：`main` d719103f。

**定案**：使用者 2026-11-14 對第 10 節 5 題回覆「照建議」（授權原文見 `AGENTS.md` 授權紀錄）。以下是當時的提案原文，只改了這段開頭；實作與用法見文末「實作紀錄」。

## 0. 結論

- Kill-Switch 的核心（鎖存、FLAT、人工恢復、門檻修改）在 Supervisor 裡已經做好並有測試，缺的是「人能按到它」：HTTP、介面按鈕、CLI。
- 「重新啟用被停用的 HTTP」其實是「第一次接上」：2026-11-03 定案 Q8 決定 v1 先不開放，介面按鈕一直標「未接線」。
- 8770 服務裡沒有長駐的 Bot：控制面每次只跑約 10 秒的 8 根合成 K 線，Donchian 重播在另一個 CLI 程序裡跑。所以 Kill 不能只靠 HTTP 直接呼叫 Supervisor，要一份兩邊都讀得到的「總開關紀錄」。
- 新預設照 11/12 定案：單幣曝險 0.5 倍權益、Soft 5%、Hard 10%。已 PASS 的重播報告與你的核准都不受影響，不用重新核准。

## 1. 範圍確認與不一致

依據：上層對話 2026-11-13 的回覆（工作包 B＝Kill-Switch＋HTTP＋新預設，做完才接 Demo；你回「同意 執行下一步」），`docs/next-steps.md:31`、`:110`，`AGENTS.md` 授權紀錄 2026-11-12。

| 項目 | 任務說明的寫法 | repo 與原文 | 處理 |
| --- | --- | --- | --- |
| HTTP | 重新啟用先前被停用的那組 | 從未啟用。`docs/simulation-api-contract-draft.md:320` Q8：「不暴露 kill-switch／re-arm／門檻修改 HTTP」，理由是牽涉金融底線與授權，不混進前端串接包。按鈕標「未接線」：`frontend/cat-os-vite/src/pages/risk.tsx:195`、`bots.tsx:295`、`command-palette.tsx:161`。後端只有 `runtime_controls: []`（`catos/workspace_api.py:96`） | 本包第一次接上，同時更新 Q8 的紀錄 |
| 槓桿 | 槓桿 0.5 倍 | 11/12 定的是「單幣曝險上限 0.5 倍權益」。現行是帳戶有效槓桿上限 3.0 倍 × 單幣占比 50%，單幣實際上限 1.5 倍（`catos/risk.py:27-30`）。上層對話說的「3 倍槓桿」是帳戶總上限 | 照 11/12 原文做；拆法見決策題 3 |
| 工作包 B 原始定義 | Kill-Switch、HTTP、新預設 | `next-steps.md:110`：把 `latch`、`set_loss_limits`、`rearm`（`catos/supervisor.py:108,962,980`）接上 HTTP 與風控中心按鈕；待決「確認步驟、誰能 re-arm」，動工前查業界做法 | 一致；`set_loss_limits` 與單一帳本 `rearm` 目前沒有長駐 Bot 可以作用，建議延到工作包 D（決策題 4） |
| 測試 | 後端 pytest | `.venv` 的 pytest 壞了，repo 規定用 `python -m unittest discover`（`AGENTS.md` 驗證節、`next-steps.md` 已知缺口） | 用 unittest |

## 2. 業界做法比較

| 系統 | 觸發 | 觸發後 | 恢復 |
| --- | --- | --- | --- |
| CME Globex Kill Switch | 風控管理員人工 | 撤掉掛單、擋住新單。官方頁沒寫到平倉（待驗證：是否完全不碰部位） | 人工 |
| NautilusTrader `TradingState` | 程式或人工設定 | HALTED：除撤單外全擋；REDUCING：只准減倉 | 再設回 ACTIVE |
| Freqtrade REST（預設 127.0.0.1:8080，要帳密） | 人工 `/stop`、`/stopbuy` | `/stopbuy` 只擋新進場；`/forceexit` 另外平倉 | `/start` 即恢復，不鎖存 |
| Hummingbot `kill_switch_rate` | 報酬率碰到門檻自動觸發 | 停掉 Bot | 人工重啟 |
| CatOS 現行規則（INVARIANTS） | Hard 日損自動；手動 Kill | FLAT：撤非減倉單、市價清倉 | 鎖存，只限人工，原因消失且對帳合格才可恢復 |

CatOS 的規則比上面都嚴（自動清倉＋鎖存），本包不放寬。來源列在文末。

## 3. Kill-Switch 設計

### 兩層

1. **總開關紀錄**（新增）：`outputs/controls/kill-switch.jsonl`，只增不改、每筆串前一筆的 sha256，做法和核准紀錄相同。測試用 `CATOS_KILL_SWITCH` 指到隔離路徑。
2. **每個 Bot 帳本裡的鎖存**（已有）：`manual_kill` 寫進帳本，Bot 的事實來源仍是帳本。

為什麼要第 1 層：你在介面按 Kill 時，Donchian 重播可能正在另一個程序跑，HTTP 碰不到它。只做 HTTP 直接呼叫的話，Kill 只對 10 秒的合成 run 有效。

| 方案 | 內容 | 涵蓋 | 成本 |
| --- | --- | --- | --- |
| A | HTTP 只控 8770 程序內的 run | 只有合成 run | 最小，但重播與之後 Demo 的獨立程序都蓋不到 |
| B（建議） | 共用紀錄檔，每個持有 Supervisor 的程序在每根 K 線前讀 | 控制面、重播、之後的 Demo | 一個小模組、一個檔；不是第二本帳 |
| C | 程序間連線通知 | 全部 | 要新增傳輸通道與常駐監聽，成本高 |

### 誰能觸發

- 人工：介面按鈕（有確認框），或 CLI `python -m catos.cli kill engage --reason "..."`。代理也可以觸發，因為這是往安全的方向。
- 自動：不新增。Hard 日損本來就自動進 FLAT（`catos/risk.py:461-470`），Soft 禁增倉；Worker 掛掉或對帳不符走既有 DEGRADED（禁增倉）。

### 觸發後

- 總開關生效期間，新 run 一律啟動不了：控制面 `start`、`bots/start`、重播 CLI 都拒絕。紀錄檔讀不到或損壞時也當成已觸發。
- 正在跑的 run 在下一根 K 線前讀到（全速重播約 0.1 秒內，每根 1 秒模式與控制面 run 1 秒內）：
  1. `supervisor.latch("manual_kill")`，帳本轉 FLAT 並寫入；
  2. 帳本 `risk_actions` 加一筆 `manual_kill` 稽核（操作者、總開關紀錄 id）；
  3. run 停止，停止原因記為 `manual_kill`。
- 撤單：local-sim 是市價單當根成交，平常沒有掛單；有未終結的單時，沿用既有 `flatten_step` 先撤非減倉單（`catos/supervisor.py:873-896`）。
- 平倉：local-sim 不模擬清倉，部位留在帳本，和第 2 步決定 7 一樣（決策題 1）。Demo／Live 照 INVARIANTS 市價清倉，在工作包 D 接上交易所。

### 鎖定與重啟

- 總開關只能人工解除；每個帳本的 `manual_kill` 永遠不會自動解除。
- 8770 重啟、重播程序重啟、Worker 重啟都不影響：總開關在檔案裡，帳本鎖存由既有的 `_load` 重新載入（`catos/supervisor.py:161-175`）。Worker 只算訊號，不知道 Kill。

### 解除（re-arm）

- 介面「解除」要填原因，並打字輸入「解除」確認；或用 CLI `kill clear --reason "..."`。
- 條件：目前沒有在跑的 run。
- 解除只讓新 run 可以啟動，不會救回被 Kill 的 run，那些 run 是終態。
- 紅線新增一條：代理不得解除總開關（同核准的做法，是程序上的防呆，不是安全邊界）。

### 帳本與稽核

- 帳本 schema 不變：`risk_actions` 的 `kind` 沒有限制值（`catos/journal.py:347-350`），加 `manual_kill` 這種新值不用遷移。
- 稽核留在三處：總開關紀錄（動作、操作者 http／cli、原因、時間、前一筆 sha256）、帳本 `risk_actions`、重播 summary 與控制面事件流（風控中心看得到）。

## 4. HTTP 介面

- 綁定不變：只聽 127.0.0.1:8770。
- 寫入沿用控制面 POST 的整套檢查（`catos/local_sim_control_api.py:53-76`）：主機、Origin 同源、JSON、`X-CatOS-Instance`、`X-CatOS-Build`、8 KB 上限、`request_id`；帶 demo／live 一律 403。
- 不加帳密：只聽本機、單人使用。Freqtrade 有帳密是因為常放 Docker 或遠端主機。
- 新端點：
  - `GET /api/workspace/simulation/kill-switch`：目前狀態與最近幾筆紀錄。
  - `POST .../kill-switch/engage`：`{request_id, reason}`。
  - `POST .../kill-switch/clear`：`{request_id, reason, confirm: "解除"}`；有 run 在跑回 409。
- `GET /risk` 已帶 `limits`；設定頁改讀它，不再寫死「3.0x · 50%」。
- 仍只限 CLI 與人工：策略核准與撤銷（不變）、總開關解除也可用 CLI。
- 本包不開：門檻修改 HTTP、單一帳本 `rearm` HTTP（決策題 4）。
- 前端接線：風控中心 Kill 與解除按鈕、Bot 頁、命令面板；移除「未接線」標示。

## 5. 新風控預設

- 數值：有效槓桿上限 1.0、單幣占比 50%、Soft 5%、Hard 10%。單幣上限 0.5 倍權益，帳戶總上限 1.0 倍。第 2 步對照用的 `NEW_DEFAULT_LIMITS` 就是這組（`catos/local_sim_replay.py:50-51`）。
- 要改：
  - `catos/risk.py:26-30` 的 `Limits` 預設。
  - `catos/local_sim_replay.py`：`current` 改指新預設，舊值改名 `legacy-v1`，保留給舊 run 對照與續跑。
  - `catos/research_loss_limits.py:131`：回測日損診斷的「現行」改成新值，原本的「新預設」欄改為「舊預設 10%／20%」對照。
  - 前端 `settings.tsx:201`、`card-registry.ts:54` 改讀後端。
  - `AGENTS.md` INVARIANTS 的曝險（3.0x／50%）與 R1（10%／20%）兩條；11/12 授權已寫「實作時一併改寫」。
- 不改：
  - `catos/demo_production_inputs.py:54` 舊 Demo 唯讀路徑釘死的舊值。改了會讓既有 Demo 帳本的預檢報 `risk_limits_mismatch`；工作包 D 再定。
  - 帳本舊 schema 升級時補 10%／20% 的邏輯，那是舊帳本的歷史語意。
- 既有帳本：每本帳存自己的上限，重開沿用原值，新預設不會偷換。
- 已 PASS 的重播 `8a74592b…`：manifest 與比對報告都寫明當時用的上限，檔案不動也不重算，結論仍有效。`build_id` 會因為 `risk.py` 改動而變，只影響「續跑同一個舊 run」，而那個 run 已經完成。
- 你的核准 `8ca25f97…`：綁的是策略、版本、來源 sha256、manifest sha256、參數、張數、合約、週期，不含風控上限。**不用重新核准，也不用新的 profile。**
- 建議另跑一次新預設的正式重播，留新的 run_id 當證據，不覆寫舊報告（決策題 5）。Donchian 1 張約 0.1 倍權益，第 2 步自測已顯示新舊上限結果相同。
- 研究回測本身目前不套曝險上限，只做日損診斷；本包讓診斷改讀新預設。回測要不要加曝險上限會改到研究損益計算，另案提。

## 6. 預計改動檔案

後端：
- 新增 `catos/kill_switch.py`（紀錄檔讀寫、雜湊鏈、fail-closed）
- `catos/risk.py`、`catos/journal.py`（`manual_kill` 稽核列）、`catos/supervisor.py`（latch 帶操作者與證據 id）
- `catos/local_sim_control.py`、`catos/local_sim_control_runner.py`、`catos/local_sim_control_api.py`、`catos/simulation_catalog.py`
- `catos/local_sim_replay.py`、`catos/cli.py`（`kill` 子指令）、`catos/research_loss_limits.py`

測試：新增 `tests/test_kill_switch.py`；調整控制面、第 2 步重播、P5、risk、回測日損診斷相關測試。

前端：`src/adapters/simulation-api-adapter.ts`、`src/adapters/types.ts`、`src/contracts/risk.ts`、`src/pages/risk.tsx`、`src/pages/bots.tsx`、`src/pages/settings.tsx`、`src/components/catos/command-palette.tsx`、`src/components/catos/card-registry.ts`、`tests/simulation_integration_test.mjs`。adapters 與 contracts 依規則由高階模型改。

文件：`AGENTS.md`（INVARIANTS 兩條、紅線一條）、`README.md:62,186`、`docs/risk.md`、`docs/simulation-api-contract-draft.md`（Q8 更新）、`docs/next-steps.md`、新增 `docs/kill-switch.md`。

## 7. 測試計畫

- 單元：紀錄檔的新增、雜湊鏈、損壞時 fail-closed、兩個程序同時寫；總開關生效時控制面 start 回 409、重播拒絕啟動；跑到一半 Kill，下一根前停止、帳本有 `manual_kill` 與稽核、重開帳本仍鎖存；解除條件；HTTP 的主機、Origin、實例、build、JSON、確認字檢查；demo／live 403；`Limits()` 新值；舊帳本重開保留舊上限；`legacy-v1` 續跑。
- 整合（隔離資料根、測試埠、測試核准紀錄）：短重播中途 Kill；4H 全量新預設重播放背景跑，對照研究回測逐筆相同。
- 整套：後端 `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"`；前端 typecheck、`npm test`、build、`simulation_integration_test.mjs`；在隔離服務實際點 Kill 與解除。

## 8. 驗收條件

1. 介面按 Kill 後，正在跑的控制面 run 與 CLI 重播都在下一根 K 線前停止，原因 `manual_kill`，帳本鎖存並有稽核列。
2. 總開關生效時任何新 run 都啟動不了；重啟 8770 或重播程序後仍生效。
3. 解除要原因與打字確認；有 run 在跑時拒絕；解除後新 run 可啟動，被 Kill 的 run 維持終態。
4. 新 run 預設上限為 1.0／50%／5%／10%；既有帳本與 `8a74592b…` 報告不變。
5. 上述整套測試全綠，附實際輸出。
6. 動到風控與執行路徑，要獨立驗收：由沒參與的 Claude 會話主驗收。

## 9. 不做的事

- 不接 OKX Demo／Live，不讀金鑰，不對外送任何請求。
- local-sim 不模擬清倉。
- 不加新的自動觸發條件。
- 不開門檻修改 HTTP 與單一帳本 re-arm HTTP（決策題 4）。
- 不改舊 Demo 唯讀路徑的釘死值，不遷移帳本 schema。
- 不改寫或重算已 PASS 的重播報告；不碰正式核准紀錄；代理不執行核准、撤銷或解除總開關。
- 研究回測不加曝險上限（另案）。

## 10. 需要你決定

1. **local-sim 被 Kill 時要不要模擬清倉？** 建議不要：停止並記錄，部位留在帳本，和重播碰到 Hard 的做法一致。真的清倉在 Demo 接上交易所時做。
2. **誰能解除總開關？** 建議介面加打字確認，加 CLI，並在紅線寫明代理不得解除。另一個選項是只限 CLI，最保守，但你要開終端機。
3. **0.5 倍怎麼拆？** 建議有效槓桿 1.0 倍 × 單幣占比 50%：單幣 0.5 倍，之後多幣時帳戶總上限 1.0 倍。另一個選項是 0.5 倍 × 100%，總上限也是 0.5 倍，多幣時會更緊。
4. **門檻修改與單一帳本 re-arm 的 HTTP 這包要不要做？** 建議延到工作包 D：現在沒有長駐的 Bot，跑完的 run 是終態，接了也沒有對象。若要先做，可以只開「只能調嚴」。
5. **新預設的正式重播誰跑？** 建議你授權代理在你現有的核准下代跑一次（約 12 分鐘，新的 run_id，不碰舊報告）。另一個選項是你自己執行我給的指令。

## 來源（查閱日期 2026-11-14）

- CME Kill Switch：https://www.cmegroup.com/tools-information/webhelp/globex-credit-controls/Content/Kill-Switch.html
- NautilusTrader 風控引擎：https://nautilustrader.io/docs/latest/api_reference/risk
- Freqtrade REST API：https://www.freqtrade.io/en/stable/rest-api/
- Hummingbot Kill Switch：https://hummingbot.org/client/global-configs/kill-switch/

## 實作紀錄（2026-11-14）

### 用法

- 介面：風控中心「Kill-Switch 總開關」面板。Kill 要填原因；解除要填原因並打字「解除」。實例監控頁與命令面板會導到這裡。
- 終端機：
  - `.venv\Scripts\python.exe -m catos.cli kill engage --reason "原因"`
  - `.venv\Scripts\python.exe -m catos.cli kill status`
  - `.venv\Scripts\python.exe -m catos.cli kill clear --reason "原因"`（只限互動式終端機，代理不得執行）
- 紀錄檔：`outputs/controls/kill-switch.jsonl`（git 忽略）；`CATOS_KILL_SWITCH` 可指到別的路徑，測試一律用隔離路徑。

### 紀錄檔的保守規則

- 紀錄檔內容被改、截斷、順序被換、不是 JSON、讀不到，都當成已觸發。
- 第一次觸發後會多一個 `kill-switch.jsonl.lock` 旁檔（只有觸發會建立，解除不會）。之後紀錄檔被刪或被清成 0 位元組，也當成已觸發（獨立驗收 D1、重驗 R1 修正）。
- 觸發永遠做得到：紀錄檔不見或變空時，觸發會從頭寫一條新的紀錄鏈，狀態變成已觸發。
- 執行中的 run 也看 `.lock` 旁檔：紀錄檔在觸發後被刪掉，run 仍會停下。
- 只有「紀錄檔和 `.lock` 旁檔都不存在」才算全新安裝。要重置總開關，必須由使用者刻意刪除這兩個檔；代理不得刪除或編輯（紅線）。

### 解除時「有 run 在跑」的檢查範圍

- 介面解除只檢查 8770 自己的控制面 run；終端機的歷史重播與 R4 看不到。CLI `kill clear` 不做這項檢查。
- 安全結果不受影響：每個執行中的 run 會記住「開始之後出現過的任何一次觸發」，即使隨後被解除，它仍會在下一根 K 線前停止（`Watch`）。

### 和提案的差異

- 除了控制面與歷史重播，R4 浸泡測試（`catos/local_sim_r4.py`）也會在啟動前拒絕、在等待下一根 K 線時每秒檢查。它也持有 Supervisor，提案時漏列。
- 紀錄檔另有一個 `.lock` 旁檔，讓介面與終端機不會同時寫入。
- `request_id` 寫進紀錄，同一個 `request_id` 重送不會多寫一筆。
- 鎖存寫入失敗時，run 記為失敗（控制面 `failed`、重播 `failed`），不是一般的停止（驗收 O3）。
- 帳本稽核列的操作者記 `kill-switch-http` 或 `kill-switch-cli`，對應觸發的來源（驗收 O4）。
- 會啟動 run 的 10 個測試模組都用 `tests/kill_isolation.py` 把總開關檔指到暫存路徑，使用者觸發 Kill 不會讓測試失敗（驗收 O2、重驗 N1）。
- 沒有另外建立 `docs/kill-switch.md`，用法與規則都寫在本文件。
- 既有測試裡依舊預設數字校準的情境（3.0 倍、10%／20%），改成明確使用 `risk.LEGACY_LIMITS`，測的是機制；新預設的數值與邊界由 `tests/test_kill_switch.py` 測。

### 改動的檔案

- 後端：新增 `catos/kill_switch.py`；`catos/risk.py`（預設值、`LEGACY_LIMITS`）、`catos/journal.py`（`audit_manual_kill`）、`catos/supervisor.py`（`manual_kill`）、`catos/local_sim_control.py`、`catos/local_sim_control_runner.py`、`catos/local_sim_control_api.py`、`catos/simulation_catalog.py`、`catos/local_sim_replay.py`、`catos/local_sim_r4.py`、`catos/cli.py`、`catos/research_loss_limits.py`。
- 前端：新增 `src/components/catos/kill-switch-panel.tsx`；契約 `risk.ts`、`command.ts`、`workspace.ts`；`adapters/simulation-api-adapter.ts`、`adapters/types.ts`、`adapters/research-api-adapter.ts`（日損診斷鍵）；`state/catStore.ts`、`state/stateAdapter.ts`；頁面 `risk.tsx`、`bots.tsx`、`settings.tsx`；`command-palette.tsx`、`card-registry.ts`。
- 測試：新增 `tests/test_kill_switch.py`、`tests/kill_isolation.py`（匯入它的模組：`test_local_sim_r4`、`test_local_sim_r4_verify`、`test_workspace_f1`、`test_step2_deployment`、`test_local_sim_control`、`test_simulation_workspace_api`、`test_simulation_ui_w6_fixture`、`test_simulation_ui_w8_fixture`、`test_browser_backtest_e2e`、`test_research_web`）；調整 `test_risk`、`test_risk_journal`、`test_p5`、`test_protection`、`test_execution`、`test_execution_supervisor`、`test_risk_period_r1`、`test_simulation_workspace_api`、`test_research_loss_limits`、`tests/integration_http_fixture.py`、前端 `tests/simulation_integration_test.mjs`。
