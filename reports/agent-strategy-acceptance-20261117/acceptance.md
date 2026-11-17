# 獨立驗收：讓 Agent 把策略寫進 `strategies/<id>/` 直接研究（2026-11-17）

## 驗收對象、驗收者與方式

- 對象：`git diff 3743062d..4cafbbcd`，分支 `feat/agent-strategy`，兩個 commit（`4b712f24` 功能、`4cafbbcd` 修正）。驗收時 HEAD = `4cafbbcd99398916476078727794a314a829fc62`，工作樹乾淨。
- 驗收者：沒有參與這次改動的另一個會話（Claude Opus 5.5），強度：高。
- 方式：
  - 讀方案、`AGENTS.md`（P1、授權紀錄、紅線）、`strategies/README.md` 與全部改動程式。
  - 跑受影響的後端測試模組，以及前端的 typecheck 和單元測試。
  - 依風險自寫 13 組補測腳本，全部在隔離目錄執行。
  - 新舊行為比對：用 `git archive 3743062d` 解出改動前的程式樹，與現行程式在同一組輸入上各跑一次，再比對輸出。
- 遵守的限制：
  - 除本報告外沒有改 repo 內任何檔案，沒有 commit 或 push。結束時 `git status` 乾淨。
  - 沒有寫入 repo 的 `strategies/` 與 `outputs/research-web`。
  - 沒有連網、連 OKX 或讀任何金鑰檔，沒有讀寫 `~/.catos/`，也沒有碰 `C:\dev\CatOS`。
  - 沒有執行 `catos.cli strategy approve/revoke`、`kill clear` 或 `demo rearm`。
  - 正式核准紀錄 `outputs/strategy-approvals/approvals.jsonl` 不在本工作樹，所以沒有讀。`8ca25f97` 的核准紀錄全文取自本工作樹的唯讀證據 `outputs/local-sim-replay/dd9521ae…/manifest.json`，再複製到暫存檔驗證。
  - 每支補測腳本都在匯入 catos 之前，把 `CATOS_STRATEGY_HOME`、`CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH` 指到全新的暫存目錄。核准只用 `strategy_approvals.approve(..., confirm=lambda...)` 寫入暫存檔，等同測試的做法。
  - 補測腳本放在 `C:\Users\user\AppData\Local\Temp\claude\06a2d6733c105b8e\590345b6-9f76-493a-a5ca-7d9d9e237d28\scratchpad\scripts\`。

## 結論

**FAIL。** 只要有一個資料夾策略被核准過，之後對該資料夾的一般修改（改 version、暫時寫壞、收窄參數範圍、刪資料夾）就會讓整份核准紀錄讀取失敗。結果是所有 Bot 的核准都解析不到，包括正式 Donchian 模擬盤 Bot 所依賴的核准，而且連撤銷都做不了（D1）。另有兩個較輕的阻斷缺陷（D2、D3）。

## 逐項判定

| # | 項目 | 判定 | 證據（檔案:行號） | 實跑 |
| --- | --- | --- | --- | --- |
| 1a | 核准前一定跑重啟一致性檢查，檢查的正是被核准的來源與 manifest | 通過 | `catos/strategy_approvals.py:413-416` 只要是資料夾策略就呼叫 `folder_check`。`:356-378` 比對報告裡的 `(sha256, manifest_sha256)` 與要寫入的 artifact 雜湊；子程序在 `catos/research_catalog.py:784-800` 前後兩次核對 provenance | E6：檢查子程序啟動前改 `strategy.py`，結果 REFUSED `source_changed_restart_required`；改 `strategy.json` 同樣被擋；A-B-A（改了又改回）也被擋；檢查後、寫紀錄前改 `strategy.py`，結果 REFUSED `sha256_does_not_match_current_source` |
| 1b | 核准後改 `strategy.py` 或 `strategy.json` 任一位元組，Bot、Worker、IPC 都解析不到 | 通過，但見 D1 | `catos/strategy_registry.py:284-294`；`:165-179`（`FolderDeployment`）；`catos/ipc.py:315-328`；`catos/worker.py:33-50`（每根 K 線前後各檢查一次） | E6：兩個檔案各加 1 byte。`resolve_deployment` 分別回 `deployment_manifest_mismatch`／`deployment_manifest_changed`，`WorkerConfig.from_wire` 回 `ProtocolError`。已解析的 deployment 在改檔後再 instantiate，回 `strategy_source_changed` |
| 1c | Worker 只從驗過雜湊的 bytes 建立類別，沒有 TOCTOU | 通過 | `catos/research_catalog.py:574-583`：讀一次 bytes，雜湊必須等於 artifact 與 spec。`catos/strategy_folder.py:301-312` 只 exec 這份 snapshot，不放進 `sys.modules`。`catos/strategy_registry.py:170-179` 再核對 spec 雜湊等於核准的雜湊 | 程式推理加上 E6。manifest 的比對分三次讀檔（spec 載入、`artifact()` 重讀、`file_hash`），理論上有 A-B-A 窗口，見 O12 |
| 2a | Donchian 改走 `constraints` 後，請求、格點、部署設定、滾動驗證的判定與錯誤訊息都不變 | 通過 | `catos/research_catalog.py:105,405,447-450`；`catos/strategy_approvals.py:184-186` | E3：新舊兩棵樹各跑 418 項（13×13 組 entry／exit、8 組格點、各內建策略邊界值、兩份正式 profile），輸出逐字相同（`diff` 為空）|
| 2b | SMA、日線、短週期策略的 provenance 與 spec 沒有變 | 通過 | 只多 `constraints`、`origin`、`base` 三個有預設值的欄位 | E3：7 個內建策略的 `provenance["strategy"]`、資料集 provenance、manifest sha、spec 新舊相同。`engine_sha256` 與各 build／runtime 雜湊本來就會因為檔案變動而改變，屬預期 |
| 2c | 正式核准 `8ca25f97…`、`10d7846f…` 綁的 Donchian 部署設定仍解析得到 | 通過 | `catos/strategy_registry.py:295-304` 的內建分支沒變 | E4：把 `8ca25f97` 全文寫進暫存檔，雜湊鏈驗證成功。`validate_profile` 結果與原 profile 相同，`worker_config` 與該次 run 的 manifest 逐欄相同，`resolve_deployment` 得到 `RegisteredDonchian`，IPC 來回一致。`10d7846f` 只有 profile 資訊（15m、192／48、1 張、本金 5000），用舊程式寫入同樣的 profile，再用新程式解析，結果成功。注意：一旦正式檔裡出現資料夾核准，這兩筆會受 D1 影響 |
| 3 | 重啟一致性檢查和 Bot 重啟實際行為一致，也抓得到狀態超出 lookback 的策略 | **未通過** | 重建方式與 Bot 一致：`catos/strategy_folder.py:415-425` 先餵 lookback 根，再餵當根並呼叫 `on_bar`，等同 `ipc.parse_history` 加上 `worker.py:35-36,60-65`。但沒有檢查 `ipc.py:487-492` 要求的 ready 時點（D2）；也只抽查前 200 個決策點加 60 個等距時點（O1） | E1：`ready` 用基底預設值的策略，檢查與核准都通過，重播在第 1 根就停。E2：最短持有期策略（3／10）的 `bot_eligible=True`，但重啟後 588 個時點中有 14 個決策不同 |
| 4 | 研究結果綁定雜湊，送出後改檔會被偵測；子程序只多帶 `CATOS_STRATEGY_HOME` | 研究任務通過；**重播比對未通過**（D3） | `catos/research_service.py:186-201,272-273`；`catos/worker_host.py:28-31`；`catos/replay_consistency.py:111-116` 用的是資料夾目前的內容 | E7：送出回測後馬上改檔，任務 failed `source_changed_restart_required`，沒有產生結果。E10：重播後只加一行註解，`compare_run` 仍 PASS，但報告的 `source_sha256` 已不是重播用的版本；改成只做多後，`compare_run` FAIL 5 項，看起來像 Bot 錯了 |
| 5a | `trials.jsonl` 計數合理 | 通過 | `catos/research_service.py:133,137-138,144,260-266`。滾動驗證是全格點窮舉（`research_validation_job.py:65-68`），優化在格點不超過 n_trials 時窮舉 | E7：回測、優化（4／格點 6）、滾動驗證（格點 4）依序記 1、4、4，累計 runs 3、組數 9 |
| 5b | 紀錄讀不懂時拒絕送出 | 大致通過，見 O4 | `catos/research_service.py:163-174` | E7：`not json` 回 `trial_log_unreadable`。缺 `sha256` 的行丟出 `KeyError`（仍然擋下，但不是 ResearchError）。`configurations=-1000` 被接受，累計變成 -989 |
| 5c | `dsr_with_history` 只是把 N 換成累計數 | 通過，單一試驗時見 O3 | `catos/research_overfit.py:242-244` | E8：同一組 12 格搜尋，N=12 時 DSR 0.0729，N=60 時 0.0227 |
| 5d | 原本的 DSR、PSR、PBO 數值沒變 | 通過 | 只新增兩個鍵 | E8：舊樹與新樹的 `search_report` 在相同輸入下，所有舊鍵完全相同；傳入 `history_trials` 也不影響其他欄位 |
| 6 | AST 白名單與 float 禁令沒有誤擋或漏擋到影響正確性的程度 | 通過（約定，不是沙箱） | `catos/strategy_folder.py:54-57,216-234` | E9：目標部位仍經 `research._decimal` 檢查，float 進不了帳務。有些誤擋與漏擋，而且允許的 `__future__` 加 `dataclasses` 組合不能用，見 O5–O7 |
| 7 | 文件和程式對得上 | **部分不符** | 見 O10 | `docs/next-steps.md:87` 留有 `WIP_STATUS` 佔位，`:74` 和前端程式不符，等等 |
| 8 | 刪除的上傳合約沒有殘留引用 | 程式通過；文件有殘留 | `catos/`、`tests/`、`tools/`、前端都沒有 import 或引用 | 全 repo grep：只剩文件引用，見 O11 |

## 缺陷（阻斷）

### D1（高）資料夾策略一旦核准過，改這個資料夾就會讓整份核准紀錄失效，所有 Bot 跟著停

- **根因**：
  - `read_records` 會對每一行呼叫 `_check_record`（`catos/strategy_approvals.py:278`），`_check_record` 再呼叫 `validate_profile(record["profile"])`（`:249`）。
  - `validate_profile` 經 `bot_strategy` 讀**資料夾目前的內容**（`:104-108`），並用目前的參數範圍、限制與 lookback 驗證舊紀錄（`:172-196`）。
  - 改動前，`bot_strategy` 只查固定的 `BOT_STRATEGIES`，所以驗證是靜態的。這次改動把「隨時會被改的檔案」接進了雜湊鏈的讀取路徑。被撤銷的核准紀錄同樣會被驗證。
- **重現**：E5，`scratchpad\scripts\exp5_chain.py`。
  1. 隔離核准檔先核准 Donchian（15m／192／48／5000，同 `10d7846f`），再核准資料夾策略 `my-cross` v1。
  2. 接著做下列任一件事：
     - 把 `strategy.json` 的 version 改成 v2。
     - 在 `strategy.py` 寫一個小數點數字，例如 Agent 改到一半。
     - 讓 `strategy.json` 暫時是不合法的 JSON。
     - 把 `fast` 的 max 收窄到低於已核准的值。
     - 刪掉資料夾。
  3. 每一種情況的結果都一樣：
     - `read_records()` 失敗。
     - Donchian 的 `active_approval` 失敗。
     - Donchian 的 `resolve_deployment` 丟出 `RegistryError`，例如 `strategy_not_bot_eligible`、`strategy_folder_invalid: …`、`profile_fast_out_of_range`、`unknown_strategy`。
     - 連 `revoke` 資料夾核准也失敗。
  4. 先撤銷資料夾核准再改 version，結果一樣。
  5. 只有合法、不改 version 和範圍的修改（例如加一行註解）不受影響。
- **後果**：
  - 正在跑的模擬盤 Bot 會在下一根 K 線停下（`catos/demo_bot.py:833-836`，`BotStopped approval_or_source_invalid`），local-sim 重播也一樣（`catos/local_sim_replay.py:297-300`）。停下時不平倉，部位留在 OKX 模擬盤上，P6 交易所端停損還沒做。
  - 核准、撤銷、`strategy list`、`find_active`、`replay_api` 都失敗，直到資料夾回復到相容的狀態。
  - 如果資料夾已經刪掉，紀錄就一直讀不了。紀錄只能追加、代理又不得編輯，所以只能由使用者手動處理。
  - README 鼓勵「檔案改了就是新版本」、讓 Agent 隨時改檔，這個情況很容易發生。而方案的驗收步驟正是「你核准它的策略」：使用者第一次核准資料夾策略後，就會進入這個狀態。
- **修正方向（供參考）**：讀取雜湊鏈時只做不依賴檔案的結構檢查，例如資料夾策略不呼叫 `strategy_spec`；依檔案內容的驗證只放在 `approve` 與該筆核准的 `resolve_deployment`。

### D2（中，fail-closed）`ready` 沿用基底預設值的策略會通過檢查與核准，Bot 卻一根都跑不了

- **根因**：
  - Bot 要求 `ready == (event_seq >= lookback)` 每根都完全成立（`catos/ipc.py:487-492`）。
  - 檢查只確認「重建後 lookback+1 根時 ready 為 True」（`catos/strategy_folder.py:421`），研究回測也只要求預熱結束時 ready（`catos/research.py:572`）。
  - `research.Strategy.ready` 的預設值是 True（`catos/research.py:161-162`）。README 只寫「資料夠了才回 True」。
- **重現**：E1、E1b（`exp1_ready.py`、`exp1b_worker.py`）。
  1. 把範例策略的 `ready` property 刪掉。
  2. `execute_check` 回 `ok=True`、`bot_eligible=True`（140 筆成交）。
  3. 隔離核准成功。
  4. `local_sim_replay.replay_bars` 回 `failed`，原因是 `WorkerError: worker pipe EOF or truncated frame`，處理 0 根。直接驅動 `worker.run` 可以看到 `ProtocolError invalid readiness result`，發生在第 1 根預熱。
  5. 對照組保留 `ready` 時，重播 `completed`。
- **後果**：
  - 不影響資金，但 `bot_eligible` 和「重啟一致性檢查通過」的核准摘要是錯的。
  - 方案驗收（「開一個新 Agent、只給 README」→ 核准 → 重播）走到最後一步會失敗，錯誤訊息也看不出原因。使用者還浪費了一筆核准。
- **修正方向**：在檢查裡重現 Bot 的 ready 規則，也就是餵 lookback−1 根時必須是 False、lookback 根時必須是 True；README 寫明這條規則。

### D3（低～中）重播一致性比對沒有綁定核准的來源雜湊，資料夾改過後會張冠李戴

- **根因**：`replay_consistency.research_run` 讀資料夾**目前**的來源建立研究基準（`catos/replay_consistency.py:111-116`），沒有比對該 run 的 manifest 裡 `approval_record.source_sha256`／`manifest_sha256`。資料集有比對（`:277-279`），來源沒有。內建策略的雜湊固定，以前不會出問題；資料夾策略可以隨時改，才出現這個缺口。
- **重現**：E10（`exp10_compare.py`）。
  1. 核准並重播資料夾策略，`compare_run` PASS，雜湊相同。
  2. 只在 `strategy.py` 加一行註解，`compare_run` 仍然 PASS，但報告的 `source_sha256` 變成新版本 `b62855d7…`，和重播實際用的 `78d5fd24…` 不同。
  3. 把策略改成只做多，`compare_run` FAIL 5 項（targets、fills、equity…），看起來像 Bot 與研究不一致，實際上是基準換了版本。
- **後果**：方案驗收依據的「Bot 成交和研究回測逐筆相同」報告可能標錯版本，或者誤報 FAIL。不影響交易。
- **修正方向**：`compare_run`／`compare` 先要求目前的 spec 雜湊等於 run manifest 綁定的雜湊，不符就像資料集一樣拒絕（例如 `source_changed_since_replay`）。

## 觀察（不阻斷）

- **O1** 重啟一致性檢查是抽樣，抓不到只在 `on_bar` 保存的狀態。
  - 反例是 E2、E2b 的最短持有期策略：`on_bar` 計數，翻向後 3 根內不再翻；計數的初始值設成「允許」。
  - 參數 3／10 時 `bot_eligible=True`。實際上 590 根中有 11 根重新建立的實例決策不同（第 2、56、57、312…根），全部不在檢查的取樣（44 個決策點，加上每 9 根一點）裡。模擬「重啟後繼續跑」時，588 個重啟點中有 14 個在 6 根內出現不同決策。
  - `docs/next-steps.md:76` 已寫明這是「必要條件，不是充分條件」。
  - 核准路徑的 lookback 不超過 512，E12 實測 L=512 單次檢查 0.5 秒，可以考慮核准時逐根檢查。
- **O2** `POST /api/research/strategy-checks` 是 `async def`，裡面同步等候子程序（`catos/research_api.py:151-158`），會卡住 8770 整個 app 的事件迴圈，最長 30 秒（`TIMEOUT_SECONDS`）。
  - E13：檢查期間在 0.20 秒送出的 `GET /api/research/version`，到 1.90 秒才回應，也就是檢查結束時。
  - 依程式推理（未實測），同一個 app 上的 Kill-Switch engage HTTP 也會跟著延遲。CLI 與 Bot 讀檔的觸發不受影響。
  - 可以改用 `run_in_threadpool` 或一般的 `def` 端點。
- **O3** 單一試驗的優化：變異數當成 0，所以 `dsr_with_history` 永遠等於 PSR，與累計 N 無關。E8：N=60 時仍是 0.4528，等於 PSR。介面會顯示「DSR（N = 累計 60 組）」，容易誤讀。建議試驗數少於 2 時回 None。
- **O4** `trials.jsonl` 的行驗證只檢查 `configurations` 是不是 int。
  - 缺 `sha256` 或 `created_at` 時丟出 `KeyError`，HTTP 會是 500，不是 `trial_log_unreadable`。
  - 負數會被接受，累計次數因此被少算（E7）。只有手動編輯才會發生。
- **O5** `print()` 沒有被禁止，也沒有處理。
  - 它會寫進研究 worker 的 stdout：檢查回 `JSONDecodeError Expecting value`，回測 failed `JSONDecodeError: Extra data`（E7）。Agent 看不懂這個錯誤。
  - Bot Worker 的 stdout 是 IPC 通道，也會被破壞。不過檢查會先失敗，所以 print 進不了核准。
- **O6** 允許清單裡的 `from __future__ import annotations` 加 `@dataclass`，載入時失敗：`AttributeError: 'NoneType' object has no attribute '__dict__' (strategy.py line 9: @dataclass)`（E11）。原因是模組不在 `sys.modules`，`strategy_folder.py:306-308` 刻意不放。沒有 `__future__` 的 `@dataclass` 正常。
- **O7** AST 規則的小誤差（E9）：
  - 誤擋：`from catos import research`、`from collections.abc import …`、名為 `open` 的變數、`isinstance(x, float)`。都有清楚的訊息。
  - 漏擋：整數相除 `int / int` 會產生 float。目標部位仍會被 Decimal 檢查擋下，不影響帳務。
- **O8**
  - 資料夾策略在送出後被改，錯誤碼是 `source_changed_restart_required`，但其實不需要重啟，重新送出就好（E7）。
  - MCP 綁定 `{id, version, sha256}` 只在用戶端比對一次 catalog（`catos/research_mcp.py:125-144`），伺服器不知道 Agent 綁的是哪個雜湊。結果仍標示實際的雜湊，送出後改檔也會被偵測，所以沒有錯置。
- **O9** 檢查結束後、寫入紀錄前若只改 `strategy.json`，核准仍會寫入（綁的是檢查過的 manifest），之後一律解析不到（E6）。這是 fail-closed，但 `approve` 在 `:415` 只比對來源雜湊，可以順手補上 manifest 的比對。
- **O10** 文件和程式不符：
  - `docs/next-steps.md:87` 留有「狀態：WIP_STATUS」佔位。
  - `docs/next-steps.md:74` 說「參數之間的限制只由後端檢查，前端不先提示」。實際上前端已依 catalog 的 `constraints` 預先檢查（`frontend/cat-os-vite/src/pages/backtest.tsx:355,413`、`optimization.tsx:82`，前端測試也有斷言）。
  - `docs/step2-research-to-bot.md:37` 仍寫「只有 `BOT_STRATEGIES` 列的策略可核准（目前只有 Donchian）」。
  - `README.md:195` 仍寫「11 skipped：v2 候選的 python_strategy 兩個模組」，現在應為 0 skipped。
  - 方案「實作紀錄」寫「每個交易決策點」，程式只取前 200 個（`catos/strategy_folder.py:320,414`）。
  - `strategies/README.md` 缺三件事：ready 必須剛好在 lookback 根時變成 True（D2）、Bot 的 lookback 上限 512、核准後不要改或刪資料夾（D1）。
- **O11** 刪除的上傳合約：程式裡沒有殘留。`docs/backend-frontend-integration-map.md:351` 仍連到已刪除的 `catos/python_strategy.py`、`strategy_library.py`，並說對應測試是 ERROR。`docs/simulation-api-contract-draft.md`、`docs/v1-local-core-handoff-20261002.md` 屬於歷史文件。
- **O12** `resolve_deployment` 對資料夾 manifest 的比對分三次讀檔：spec 載入、`artifact()` 重讀、`file_hash`（`catos/strategy_registry.py:284-294`）。理論上有 A-B-A 窗口，可能用到與核准不同的 manifest 解析結果。直接比對 `spec.manifest_sha256 == record["manifest_sha256"]` 就能消除。依 P1，這不是安全邊界，影響極低。

## 實際執行的指令與輸出摘要

- 受影響的後端模組：
  - 指令：`.venv/Scripts/python.exe -m unittest discover -s tests -p "<模組>"`。
  - 環境：`CATOS_STRATEGY_HOME`、`CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH` 指到暫存目錄。
  - 結果：16 個模組全部 OK，共 231 項：
    - `test_strategy_folder` 12、`test_step2_deployment` 23、`test_research_donchian` 16、`test_research_mcp` 6
    - `test_research_overfit` 17、`test_strategy_registry` 6、`test_worker` 15、`test_ipc` 11
    - `test_research_web` 18、`test_research_optimization_web` 6、`test_research_validation_web` 11、`test_research_daily` 15
    - `test_research_intraday` 10、`test_local_sim_r4` 9、`test_demo_bot` 30、`test_kill_switch` 26
  - `test_research_web` 印出「Port 55057 already in use…」，是該測試本身預期的輸出，結果仍為 OK。
- 後端整套沒有重跑。開發者在 4b712f24 時點跑過 1006 項 OK，屬歷史證據；之後的變更已由上列模組覆蓋。
- 前端：
  - `npm --prefix frontend/cat-os-vite run typecheck`：0 錯誤。
  - `npm --prefix frontend/cat-os-vite test`：22 項通過、0 失敗。
  - 沒有跑 build 與整合測試，以免寫入 `dist/`。
- 補測腳本（`…\scratchpad\scripts\`，皆用隔離目錄）：
  - E1／E1b `exp1_ready.py`／`exp1b_worker.py`：見 D2。
  - E2／E2b `exp2_minhold.py`／`exp2b.py`：見 O1。
  - E3 `exp3_donchian.py`：新舊兩棵樹各 418 項，`diff` 為空。
  - E4 `exp4_formal.py`：`8ca25f97` 的複本可以解析；舊程式寫入、新程式讀取的 15m／5000 紀錄也可以解析。
  - E5 `exp5_chain.py`：見 D1。
  - E6 `exp6_toctou.py`：核准期間改檔都被擋；核准後改 1 byte，三條路徑都拒絕。
  - E7 `exp7_service.py`：送出後改檔偵測得到；計數 1／4／4；O3–O5、O8 的現象。
  - E8 `exp8_overfit.py`：DSR、PSR、PBO 新舊相同；`dsr_with_history` 的公式正確；單一試驗等於 PSR。
  - E9 `exp9_ast.py`：O7。
  - E10 `exp10_compare.py`：見 D3。
  - E11 `exp11*.py`：O6。
  - E12 `exp12_timing.py`：檢查耗時 L=50 為 0.4 秒、L=512 為 0.5 秒、L=1900 為 1.8 秒。
  - E13 `exp13_loop.py`：見 O2。
- `git status`：乾淨（本報告位於 git 忽略的 `reports/` 下）。
