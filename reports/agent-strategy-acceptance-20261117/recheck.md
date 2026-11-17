# 窄範圍重驗：D1–D3 與 O1 的修正（2026-11-17）

## 重驗對象

- `git diff 4cafbbcd..HEAD`，HEAD = `d14505cee8ce8db547314fb390841e9bb348b53c`（`fix: 依獨立驗收修正資料夾策略的核准紀錄、ready 規則與重播比對（D1–D3）`），分支 `feat/agent-strategy`，工作樹乾淨。
- 只看前一輪報告 `acceptance.md` 的 D1、D2、D3、O1 是否關閉，以及這次修正有沒有帶來新問題。其他觀察（O2–O12）的修正只順帶看，不逐項判定。
- 重驗者：沒有參與這次修正的另一個會話（Claude Opus 5.5），強度：高。

## 方式與遵守的限制

- 讀修正 diff（`catos/strategy_approvals.py`、`strategy_folder.py`、`replay_consistency.py`、`strategy_registry.py` 等），以及相關呼叫端：`strategy_registry.resolve_deployment`、`ipc.WorkerConfig.from_wire`、`demo_bot._bar`／`find_demo_approval`、`local_sim_replay`、`replay_api._approvals`。
- 開發者的說法逐條用實跑核對，沒有直接採信。
- 新舊比對：用 `git archive 4cafbbcd` 把修正前的 `catos/`、`tests/`、`strategies/`、`examples/` 解到暫存目錄，同一支腳本分別對新舊程式各跑一次。
- 前一輪的補測腳本 `exp5_chain.py`、`exp1_ready.py`、`exp10_compare.py`、`exp2_minhold.py` 原封不動對新程式重跑；另寫 10 支補測腳本，放在 `C:\Users\user\AppData\Local\Temp\claude\06a2d6733c105b8e\590345b6-9f76-493a-a5ca-7d9d9e237d28\scratchpad\recheck\`。
- 限制：
  - 除本報告外沒有改 repo 內任何檔案，沒有 commit 或 push。結束時 `git status` 乾淨（本報告在 git 忽略的 `reports/` 下）。
  - 每支腳本在匯入 catos 之前，把 `CATOS_STRATEGY_HOME`、`CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH` 指到全新的暫存目錄。沒有寫入 repo 的 `strategies/`。
  - 核准只用 `strategy_approvals.approve(..., confirm=lambda...)` 寫進暫存核准檔（等同測試的做法）。偽造紀錄的測試直接在暫存檔寫入算好 record_id 與鏈的行。
  - Donchian 的既有重播 `outputs/local-sim-replay/dd9521ae…` 先整個複製到暫存目錄，再對複本做比對，沒有在原處開啟。該 run 的 manifest 裡記的正式核准檔路徑（`C:\dev\CatOS\…`）沒有讀。
  - 沒有連網、連 OKX 或讀金鑰檔，沒有讀寫 `~/.catos/`，也沒有碰 `C:\dev\CatOS`。
  - 沒有執行 `catos.cli strategy approve/revoke`、`kill clear` 或 `demo rearm`。
  - 沒有跑後端整套，只跑 7 個受影響的模組（見最後一節）。

## 結論

**PASS。** D1、D2、D3 都已關閉，O1 的原反例（最短持有期策略 3／10）在核准時被擋下；沒有發現阻斷的新缺陷，但有 7 項觀察，其中 O-A（逐根檢查讓部分正當策略核准逾時）是相對修正前的退步，建議在方案驗收前處理或寫進 README。

## 逐項判定

| # | 項目 | 判定 | 證據（檔案:行號） | 實跑 |
| --- | --- | --- | --- | --- |
| 1a | D1：改已核准的資料夾，不再讓整份核准紀錄、Donchian 與撤銷失效 | **關閉** | `catos/strategy_approvals.py:282` 讀紀錄改呼叫 `_recorded_profile`；`:191-193` 只有 `BOT_STRATEGIES` 的 key 走完整 `validate_profile`；`:194-206` 資料夾紀錄只做不讀檔的結構檢查 | R1（`r1_chain.py`）：改 version、寫小數點數字、JSON 不合法、收窄參數範圍、刪資料夾，另加 4 種（同版本改參數名、加參數、改 lookback 參數名、A-B-A），每種都是 `read_records` OK；Donchian 的 `active_approval`、`resolve_deployment`、`find_active`、`find_demo_approval`、`WorkerConfig.from_wire` 全 OK；`replay_api._approvals` 回 `available`，資料夾那筆標 `changed`；`strategy list` exit 0；撤銷資料夾核准 OK，撤銷後 Donchian 仍可解析。「先撤銷再改 version」與「先撤銷再刪資料夾」也正常。原腳本 `exp5_chain.py` 重跑：每一列都是 `read_records OK | Donchian approval OK | resolve_deployment OK | revoke OK` |
| 1b | D1：該筆資料夾核准本身仍 fail-closed | **成立**（3 種情況錯誤型別不對，見 O-B） | `catos/strategy_registry.py:266-294` | R1：改 version 回 `strategy_not_bot_eligible`；小數點數字與 JSON 不合法回 `strategy_folder_invalid: …`；收窄範圍回 `deployment_manifest_changed`；刪資料夾回 `unknown_strategy`；加註解回 `deployment_manifest_mismatch`；IPC 都是 `ProtocolError: unregistered strategy: …`。同版本改參數名、加參數、改 lookback 參數名時，`resolve_deployment` 與 `WorkerConfig.from_wire` 丟出 `KeyError`，仍然解析不到。只有 A-B-A（改了又改回原位元組）會恢復解析，這是雜湊綁定的預期行為。R1b（`r1b_midrun.py`）：local-sim 重播跑到第 100 根時改資料夾，三種改法都在第 100 根停下：加註解是 `stopped approval_or_source_invalid:deployment_manifest_mismatch`，改 version 是 `stopped …strategy_not_bot_eligible`，同版本改參數名是 `failed KeyError: 'quick'` |
| 1c | D1：結構檢查有沒有放寬到接受損壞或偽造的紀錄 | **損壞的紀錄照擋；內建策略繞不過；偽造的資料夾紀錄放寬**（見 O-C） | `catos/strategy_approvals.py:191-206`；`:259-262`（鏈與 record_id）；`:312-313`（canonical） | R1c（`r1c_forge.py`，新舊各跑一次）。**損壞（沒有重算 id）**：T1 改一個位元組、T2 只重算前一行、T3 非 canonical 空白、T4 換順序、T5 刪中間行、T6 缺結尾換行、T7 小數、T8 重複鍵，新舊結果逐項相同，全部拒絕。**內建策略**：Donchian 身分（F1 超範圍、F2 exit≥entry、F3 warmup<lookback）新舊都拒絕，因為仍走完整驗證；改成其他 version（F4）或 `sma-trend`（F5）時，新程式讀得進來，但解析一律回 `strategy_not_bot_eligible`。R1d：把 Donchian 紀錄改標成資料夾 id（F19–F21），新程式也讀得進來，解析時回 `KeyError: 'fast'`、`deployment_manifest_mismatch` 或 `unknown_strategy`。原因有三：`strategy_spec` 先查內建表（`research_catalog.py:130-141`）；`bot_strategy` 對內建 id 不查資料夾（`strategy_approvals.py:102`）；來源雜湊含路徑，所以 Donchian 的 source_sha256 對不上任何資料夾。**偽造的資料夾紀錄（重算 id 與鏈）**：F6 參數超出資料夾範圍、F8 warmup<lookback、F9 違反 fast<slow、F11 多一個參數，新程式讀得進來也解析得到；4cafbbcd 讀取時就拒絕。F7（lookback 600）被 IPC 的 512 上限擋下 |
| 1d | D1：雜湊鏈與 canonical 檢查有沒有退步 | **沒有退步** | `catos/strategy_approvals.py:247-262,309-324` 與修正前相同 | 同上 T1–T8，新舊輸出逐字相同 |
| 2 | D2：`ready` 用預設值的策略要 `bot_eligible=False` 且核准被拒；範例照常通過 | **關閉** | `catos/strategy_folder.py:421-427` 預熱時逐根檢查 `ready == (已餵根數 >= lookback)`；`:445-446` 違規時不做重啟比對；`:464` | R2（`r2_ready.py`）：刪掉 `ready` 回 `ok=True bot_eligible=False`，理由是「餵到第 1 根時 ready 是 True…」，核准回 `restart_consistency_failed`。早一根變 True 的版本也被擋（第 19 根）。範例策略回 `bot_eligible=True exhaustive=True checked=580/580`，核准 OK，重播 600 根 `completed`、25 筆成交。原腳本 `exp1_ready.py` 重跑：check 回 `True False`，核准丟出 `restart_consistency_failed`（Bot 已經不可能拿到這筆核准，`exp1b_worker` 的情境不再可達）。另外兩種：`ready` 在 lookback 前丟例外會讓檢查失敗、核准被拒（O-F）；`ready` 之後又變回 False 會被回測階段擋下（`strategy indicators are not ready for evaluation`） |
| 3 | D3：資料夾改過後，重播比對要拒絕；Donchian 的比對不受影響 | **關閉** | `catos/replay_consistency.py:160-167` | R3（`r3_compare.py`）：重播後比對 PASS，source 是 `78d5fd2441dc`。之後只加註解、改成只做多、只改 manifest 描述、改 version，四種都回 `strategy_source_changed_since_replay`；改回原內容後又 PASS，摘要相同；刪資料夾回 `unknown_strategy`。原腳本 `exp10_compare.py` 重跑：兩種修改都被拒。Donchian：對 `dd9521ae…` 的複本跑 `replay_consistency.compare`，PASS，耗時 0.8 秒；`passed`、`checks`、`source_sha256`、`fill_digest`、`decision_digest`、`counts`、`research`、`published_research` 和該 run 存的 `consistency.json` 逐項相同 |
| 4a | O1：最短持有期策略在核准參數下被擋 | **關閉**（只限原反例 3／10，見 O-D） | `catos/strategy_folder.py:436-446` 預算內逐根比對；`catos/strategy_approvals.py:412-413` 核准要求 `exhaustive` | R4（`r4_o1.py`）：3／10 回 `bot_eligible=False`、`exhaustive`、590／590，第 12 根不同，核准回 `restart_consistency_failed`。原腳本 `exp2_minhold.py` 重跑結果相同。5／20 與 20／50 仍通過，也核准得了；R4b 證實在檢查用的合成資料上，這兩組翻向的最短間隔是 6 根和 83 根，3 根的持有規則從沒生效，所以重啟後往前跑 6 根也沒有分歧（0／580、0／550） |
| 4b | O1：lookback 512 時的耗時（研究 worker，逾時 30 秒） | 範例策略遠低於 30 秒；**每根 update 成本 O(L) 的策略會逾時**（見 O-A） | `catos/strategy_folder.py:336`；`catos/research_catalog.py:175`；`catos/research_service.py:315-319` | 經 `run_worker` 實測：範例策略（update 為 O(1)）L=50 0.3 秒、L=200 0.6 秒、**L=512 1.2 秒**（1324／1324 逐根）、L=1900 4.6 秒（抽樣 1386／4100）。在 `update_indicators` 重算 SMA 總和（O(L)）：L=512 10.2 秒，L=1900 逾時。R4c 走 `folder_check`，在 `update_indicators` 重算平均與變異數（布林通道寫法）：L=200 7.5 秒、L=300 22.2 秒，L=400 與 L=512 都是 `restart_check_failed: research_timeout`（30.0 秒）。同一支腳本用 4cafbbcd 跑：L=512 只要 5.1 秒，核准通過 |
| 5 | 新問題：`replay_api` 核准清單、`find_active`、Demo Bot 找核准 | 沒有阻斷問題 | `catos/replay_api.py:28-44`；`catos/strategy_approvals.py:349-355`；`catos/demo_bot.py:891-895` | R1 的每種改法：`replay_api._approvals` 都是 `available`，Donchian 標 `current`、資料夾標 `changed`；`find_active(Donchian)` 與 `find_demo_approval(Donchian)` 都 OK。`find_active(資料夾 profile)` 在加註解後仍回那筆紀錄（只比 profile，不比雜湊），解析時被擋，修正前也是這樣。暫時放進 `sys.modules` 的 `build_class` 只在子程序與單執行緒的 CLI 呼叫，沒有同程序並行的路徑。試驗紀錄新加的格式檢查和寫入端的欄位一致（`research_service.py:193-195`），舊紀錄不會被誤判 |

## 新缺陷（阻斷）

無。

## 觀察（不阻斷）

- **O-A（相對修正前的退步，建議優先處理）逐根檢查讓「每根 update 成本與視窗長度成正比」的正當策略在 lookback 約 350 以上核准不了。**
  - 工作量是 評估根數 ×（lookback＋1）× 每次 update 的成本。`CHECK_UPDATE_BUDGET` 的註解（`catos/strategy_folder.py:333-336`）只算了呼叫次數，沒有算每次的成本。
  - 實測：布林通道寫法（每根重算平均與變異數）L=400、L=512 都逾時，核准回 `restart_check_failed: research_timeout`。修正前同一策略 L=512 只要 5.1 秒，可以核准。
  - 結果是 fail-closed，不影響資金，但錯誤訊息看不出原因。`docs/next-steps.md:77` 有寫「在 lookback 512 時可能逾時」，實測從約 400 就會發生。Agent 讀的 `strategies/README.md` 沒有提醒，而方法名稱 `update_indicators` 本身就引導人在這裡重算指標。
  - 可選做法：核准路徑放寬逾時；或在 README 寫明指標要增量更新、核准檢查有 30 秒上限；或在逾時時回一個看得懂的訊息。
- **O-B 同一個 version 下改參數名、加參數或改 lookback 參數名，資料夾核准仍然解析不到，但錯誤型別是 `KeyError`，不是 `RegistryError`／`ProtocolError`。**
  - 位置：`catos/strategy_registry.py:272-279` 用資料夾**目前的**參數名稱去取紀錄的參數，取不到就丟 KeyError，而且發生在雜湊比對之前。`ipc.WorkerConfig.from_wire` 和 `local_sim_replay.worker_config` 同樣如此。
  - 後果：`demo_bot._bar` 只接 `RegistryError`（`catos/demo_bot.py:833-836`），所以模擬盤 Bot 會走到 `:579`，記成 `failed: KeyError…`，而不是 `stopped: approval_or_source_invalid`。local-sim 重播也一樣（`catos/local_sim_replay.py:300,356`，R1b 實測）。兩者都在下一根停下、不下單、不平倉，其他核准不受影響。
  - 修正前，這種改法會讓 `read_records` 失敗（也就是 D1），所以這是 D1 修正後才露出來的錯誤分類問題，不是新的資金風險。
- **O-C 偽造的資料夾核准紀錄比修正前容易被接受。**
  - 有人刻意重算 record_id 與雜湊鏈時，參數超出資料夾範圍、違反 `constraints`、warmup 小於 lookback、或多出參數的資料夾紀錄（F6、F8、F9、F11），現在讀得進來，也解析得到。4cafbbcd 在讀取時就會拒絕。
  - 原因：`resolve_deployment` 的資料夾分支只核對雜湊，沒有用資料夾目前的內容驗證該筆 profile。開發者說「依檔案的驗證留在該筆核准的 resolve_deployment」，實際上只有雜湊比對。
  - 真實的核准不會進入這個狀態：manifest 雜湊綁住參數範圍，而 `approve` 當下已經驗過。偽造紀錄本來就在 P1「程序上的防呆，不是安全邊界」之外，偽造者也可以直接偽造一筆範圍內的核准。另外，非字串的 `strategy_id`（F14）會讓 `read_records` 丟 `TypeError`，而不是 `ApprovalError`（`catos/strategy_approvals.py:191`）；`replay_api._approvals` 只接 `ApprovalError`／`OSError`／`ValueError`。只有手工偽造才會碰到。
  - 一個做法可以同時解決 O-B 與 O-C：在 `resolve_deployment` 的資料夾分支，雜湊比對通過後對該筆 profile 呼叫 `validate_profile`，並把 `ApprovalError` 轉成 `RegistryError`，參數名稱的取用也移到這之後。這只讀這一個資料夾，不會讓 D1 復發。
- **O-D 重啟一致性檢查仍取決於合成資料。** 最短持有期策略 5／20、20／50 可以核准，因為合成資料上翻向的間隔從沒短於 3 根，規則沒生效。真實行情若出現 3 根內的反轉，Bot 重啟後就可能做出不同決策。`docs/next-steps.md:75` 寫了「必要條件，不是充分條件」，`strategies/README.md` 沒寫。
- **O-E D3 的比對讀了兩次資料夾。** `compare_run` 先在 `catos/replay_consistency.py:161-167` 核對雜湊，`research_run`（`:114-116`）再重讀一次，回傳的 `source_hash` 沒有再和核准比對。兩次讀取之間改檔，仍可能出現前一輪 D3 的情況。窗口只有毫秒級，影響極低；可以在 `research_run` 之後補一句 `source_hash == record["source_sha256"]`。
- **O-F `ready` 在餵滿 lookback 前丟例外時，例如 `self.closes[-maxlen]`，檢查回的是不帶階段與行號的 `ResearchError: IndexError: deque index out of range`。** 原因是預熱逐根檢查（`catos/strategy_folder.py:421-423`）不在 `stage()` 裡。核准仍正確被拒，只是 Agent 不容易看懂。
- **O-G `docs/next-steps.md:88` 的「狀態：STATUS_PENDING」仍是佔位字**，前一輪的 `WIP_STATUS` 只是換了名字。

## 實際執行的指令與輸出摘要

所有 Python 都用 `.venv/Scripts/python.exe`，工作目錄是本 worktree，並設 `PYTHONIOENCODING=utf-8`。腳本在 `…\scratchpad\recheck\`，原腳本在 `…\scratchpad\scripts\`。

- 受影響模組（三個環境變數指到暫存目錄）：`python -m unittest discover -s tests -p "<模組>.py"`。
  - `test_strategy_folder` 20、`test_step2_deployment` 23、`test_strategy_registry` 6、`test_ipc` 11、`test_worker` 15、`test_demo_bot` 30、`test_research_mcp` 6。
  - 全部 OK，共 111 項。
- `git archive 4cafbbcd catos tests strategies examples | tar -x -C …\recheck\old-4cafbbcd`：修正前的程式樹，供新舊比對。
- R1 `r1_chain.py`：D1 的 12 種改法加 2 種「先撤銷再改」，結果見 1a、1b。
- R1b `r1b_midrun.py`：重播途中改資料夾，見 1b。
- R1c `r1c_forge.py`：新舊各跑一次，輸出在 `r1c_forge.new.out`、`r1c_forge.old.out`。差異只在 F4–F11、F14、F18，其中 F6、F8、F9、F11 在新程式解析得到。T1–T8 新舊相同。
- R1d `r1d_relabel.py`：把 Donchian 紀錄改標成資料夾 id，全部解析不到。
- R2 `r2_ready.py`、R2b `r2b_raise.py`：D2，見第 2 列與 O-F。
- R3 `r3_compare.py`：D3，加上 Donchian 複本比對。
- R4 `r4_o1.py`：最短持有期策略，以及經 `run_worker` 的耗時。R4b `r4b_forward.py`：重啟後往前跑的分歧數。R4c `r4c_timing.py`：布林通道寫法走 `folder_check`，新舊各跑一次。
- 原腳本重跑（`ACC_TMP` 指到暫存目錄）：`exp5_chain.py`、`exp1_ready.py`、`exp10_compare.py`、`exp2_minhold.py`，結果見各列。
- `git status`：乾淨。
