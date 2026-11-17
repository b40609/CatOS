# 獨立驗收：九月模組清理（077cdd0a）與模擬盤 P6 保底停損（ed72bbe8）

- 日期：2026-11-17
- 驗收者：獨立會話（沒有參與這兩個改動）
- 範圍：worktree `C:\Users\user\.t3\worktrees\CatOS\feat-wp-b-kill-switch-7bd55fc4c3125468`。交辦寫的是 `feat/okx-demo-m1`，實際 checkout 的是 `feat/agent-strategy`，但兩個 commit（077cdd0a、ed72bbe8）一致，HEAD = ed72bbe8，工作樹乾淨。
- 沒有連網，沒有碰 `C:\dev\CatOS`，沒有開憑證檔。所有情境都用 tests/test_demo_bot.py 的 FakeOkx（加上我自己的故障注入）和隔離路徑。
- 情境腳本：`C:\Users\user\AppData\Local\Temp\claude\06a2d6733c105b8e\e959d5a4-c8a1-4a67-830d-e90e8ab84b74\scratchpad\acceptance-p6\scenarios_p6.py`（下文簡稱 `scenarios_p6.py`），另有 `trace_check.py`、`import_all.py`，都在同一個資料夾。

## 結論

**FAIL**（A 通過；B 有一項要修的缺陷）

- A（清理）：PASS。刪掉的程式不在任何執行中的路徑上，Supervisor／execution 對沒用授權碼和帳本綁定的呼叫端行為不變，資料庫結構沒變。
- B（P6）：FAIL。停損狀態沒確認或已觸發時，Kill／Hard 的清倉會被擋下，不送只減倉單，部位留在 OKX 上（D1）。開倉的閘門本身沒問題：停損缺少、過期、沒確認或失敗時，找不到任何加倉送得出去的路徑。

## 缺陷

### D1（高，緊急路徑；觸發機率低）：停損狀態沒確認或已觸發時，Kill／Hard 不清倉

- 位置：`catos/demo_bot.py:341`（`_reconcile` 一開頭就呼叫 `_protection_settled`，`flattening=True` 也一樣）、`catos/demo_bot.py:360-374`（`_protection_settled` 會丟 `protection_unconfirmed`／`disaster_stop_triggered`）、`catos/demo_bot.py:540-549`（`_flatten_rounds` 送 `flatten_step` 前先跑 `_reconcile`）、`catos/demo_bot.py:589-597`（`_intrabar_check` 在 `_observe` 之前先跑 `_reconcile`）。
- 情境：
  1. `scenarios_p6.py` `test_01b_kill_after_lost_create`：進場成交後，建立停損的那個請求沒送到 OKX（連線錯誤，只發生一次）。使用者在下一次分鐘檢查前按 Kill。
  2. `test_01_kill_flatten_while_stop_unconfirmed`：停損其實已經掛上，但回應遺失，而且 OKX 的條件單查詢端點一直回 50001。這時按 Kill。
  3. `test_01c_hard_after_lost_create`：情境 1 一樣的建立遺失，接著虧損超過 Hard（12%），然後才到分鐘檢查。
- 預期：只減倉的市價清倉一律允許（INVARIANTS：合法減倉始終允許；Hard 啟動市價清倉及 Kill-Switch；Kill 觸發後清倉到 OKX 部位為 0）。保底停損的狀態不應該擋住緊急出口。
- 實際：
  - 1：`flatten_failed:protection_unconfirmed`，OKX 部位 1，OKX 上沒有停損，只送過一張開倉單。
  - 2：`flatten_failed:protection_unconfirmed`，OKX 部位 1。
  - 3：停在 `protection_unconfirmed`，OKX 部位 1，沒有清倉，**Kill-Switch 也沒寫入**（因為 `_reconcile` 先丟例外，Hard 根本沒被評估）。重開會在 `_recover` 的 `_reconcile` 又停在同一處，Hard 永遠不會執行（見 D2）。
  - 同一個原因造成的較輕情形，見 `test_10_stop_fires_during_kill_flatten`：Kill 和 OKX 停損同時觸發時，結果是 `flatten_failed:disaster_stop_triggered`。OKX 已經平倉，但訊息寫「部位可能還在 OKX 上」。
- 備註：帳本端的 `ExecutionJournal.flatten` 只要求 `conditional_open == int(active is not None)`。Bot 的對帳證據本來就照帳本產生，所以只要 `_reconcile` 在清倉模式下不因為 pending／triggered 停下，清倉單就送得出去。停損預設是 0%（關），所以這個缺陷只有開了 `--disaster-stop` 才會出現。

### D2（低）：沒送到 OKX 的建立請求會永久卡住接續，提示卻說重開會接續

- 位置：`catos/demo_bot.py:1017`（`protection_unconfirmed` 的提示文字）、`catos/protection.py:202-203`（pending 只會被查詢，NOT_FOUND 不算證據）。
- 情境：`test_02_create_lost_before_okx_is_permanent`，`trace_check.py`。
- 預期：符合「不盲目重送」，但要讓使用者知道出路。
- 實際：建立請求只送過一次，沒有重送（trace：全程 1 次 POST order-algo，6 次查詢），這是對的。但第一次 run 在 65 秒後停在 `protection_unconfirmed`，OKX 部位 1、沒有停損；重開後是接續，又停在 `protection_unconfirmed`；只要部位還在，就永遠接不下去。提示卻寫「用同一個指令重開會接續」。實際出路只有一條：使用者到 OKX 手動平倉，下次啟動就是新 run。在這段期間，部位沒有策略管理、沒有 Soft／Hard 監看，也沒有交易所停損。

### D3（低）：別人在 OKX 改了我們停損的觸發價，Bot 不會發現

- 位置：`catos/demo_bot.py:342-353`（只核對 `algoClOrdId` 有沒有列出）。
- 情境：`test_04_stop_amended_on_okx_is_not_noticed`：停損掛上後，在 OKX 把觸發價改成 1.0。
- 預期：觸發價、方向或觸發來源跟帳本不同，應視為不符（陌生委託：禁止增倉並停下或告警）。`pending_algos()` 已經讀回 `sl_trigger_px`、`side`、`sl_trigger_px_type`。
- 實際：Bot 照常跑到 `operator_stop_file`，帳本仍以為停損在 94.5，`blocked()` 為 False，增倉閘門是開的。

### D4（低）：重啟時電腦時鐘若比上次的 revision 早，程序失敗而不是正常停下

- 位置：`catos/okx_demo_exchange.py:148-150`（revision 是牆鐘微秒）、`catos/protection.py:250-253`（revision 不大於已存的值就丟 `conflicting protection evidence`）。
- 情境：`test_07_revision_after_clock_step_back`：停損掛上後停下，重開時把 `time.time_ns` 往回撥 1 小時。
- 預期：同一個 request 跨重啟的 revision 嚴格遞增，或者至少以 `BotStopped` 乾淨地停下。
- 實際：`state=failed`，原因 `ProtocolError: conflicting protection evidence`，部位 1。fail-closed，不會多送東西。在時鐘追過舊值之前，每次重開都會一樣失敗。實務上要時鐘倒退才會遇到，機率很低。

### D5（低）：兩則訊息與實際狀態不符

- `catos/demo_bot.py:536`（`test_10`）：OKX 停損已經把部位平掉，訊息卻是「清倉沒有完成…部位可能還在 OKX 上」。
- `catos/demo_bot.py:567`（`test_16_cancel_after_flat_with_foreign_position`）：清倉時帳戶裡有別的合約部位，停損其實已經撤掉了（OKX 上沒有 live 條件單），訊息卻寫「保底停損單沒有確認撤掉（foreign_positions_or_orders_in_account…）」。原因是 `_protect` 裡的 `_reconcile(facts, "protection")` 沒帶 `flattening=True`。

## 觀察（不擋交付，供參考或由使用者定案）

1. **拿掉 `ProtectionJournal.save` 的作廢，沒有削弱「停損不對就不能加倉」**：
   - 決策時 `Journal._risk_verdict`（journal.py:692）和送出前 `ExecutionJournal.prepare`（execution.py:112）都會查 `blocked()`。`prepare` 和 handoff 在同一個 `_operation()` 名額內，中間沒有別的工作能改停損狀態。
   - 反手的開倉腿會從空倉重新評估（張數必須相符，期限最多 60 秒），接續時的舊意圖都過期才處理。
   - 少掉的只有一點：短暫被擋之後，未送出的加倉意圖不再永久作廢；擋住解除後，如果仍在期限內、風控重評也通過，還是可以送出。`_write_risk`（非 RUN／HEALTHY）和 rearm 的作廢都還在。
   - 全部送單點都經過 `prepare`、`prepare_reversal_close`（只減倉）或 `flatten`（只減倉）：execution.py:116／182／351，supervisor.py:719-725／767。
2. **停損閘門關著時，整筆反手都會被拒，連出場腿也一起**（`test_14_reversal_while_stop_refused` 對照 `test_14b`）：
   - 停損一直被 OKX 拒絕時，第 6 根的反手訊號被判 `REJECTED protection_gate_closed`，部位留在多 1 張，也沒有停損；沒開停損的對照組會正常反手到 -1。
   - 這是既有設計（Soft 下的反手也一樣整筆拒絕），B 只是讓 Demo 走得到這條路。是否改成「閘門關時反手只做平倉腿」，建議由使用者定案。
3. **order_failed／partially_failed 對應成 TRIGGERED，是安全的**（`test_05`）：
   - 觸發後不再送任何單，重開在 `_recover` 會再停一次（`disaster_stop_triggered`），不會接手。
   - 部位會留在 OKX 上、沒有停損。提示有寫「確認部位是 0」，但沒明講這種情況下部位可能還在。
4. **停損被別人在 OKX 撤掉**（`test_03`）：下一次分鐘檢查查到 canceled，自動用新的 `algoClOrdId` 重掛，查詢結果出來之前增倉都是擋住的。畫面只顯示「保底停損已掛上」，沒有說原本那張被撤了。
5. **Bot 停著時停損觸發**（`test_11`）：下次啟動 OKX 是空倉，就直接開新 run，不會提示停損曾經觸發。
6. **改單被 OKX 拒絕時當成不確定，而不是失敗**（`test_08`，接續時從 10% 改成 5%）：
   - 每分鐘查一次確認舊價還在，然後再送一次改單。5 分鐘內送了 6 次改單，OKX 上仍是 94.5。
   - 每次重送前都先以查詢結清，不算盲目重送。增倉一直擋著。告警只寫進 events.jsonl 和 stderr 的 logging（`Bot demo-bot: protection_mismatch`），終端機的 echo 沒有訊息。
7. **告警的呈現**：`_protect` 的 `protection_alert`／`protection_wait` 事件沒有 message，只寫 events.jsonl；終端機看得到的只有 Supervisor 用 logging lastResort 印到 stderr 的英文代碼。P6 要求的「告警」算是勉強有。
8. **陌生條件單只查四種類型**（conditional／oco／trigger／move_order_stop），沒查 `chase`、`twap`、`iceberg`。後三種實際會下一般委託，大多會被 orders-pending 抓到。
9. **建立請求的 51xxx 一律當 REJECTED**，比一般下單用的明確白名單寬。如果 OKX 對已受理的請求回 51xxx：下一步會用新的 `algoClOrdId` 再建一張（OKX 每個部位只收一張整倉 TP/SL，應會拒絕），原本那張會被當成陌生單而停下，結果仍是 fail-closed，但停下原因的標籤會誤導。
10. `protection_order` 把 51000（參數錯誤）也當成「查不到」。如果查詢格式本身被 OKX 拒絕，結果會一直是 NOT_FOUND，然後停在 `protection_unconfirmed`。fail-closed，但不容易診斷。
11. **OKX 平倉後自動撤銷整倉 TP/SL**（`test_06`，我假設 OKX 是這樣運作）：`protection_verify` 這條路正確處理，反手和 Kill 都正常，不用另外撤單。
12. Kill 清倉時撤停損的請求遺失（`test_15`）：部位已經是 0，記一筆 `protection_left` 提醒使用者手動撤，下次啟動會擋在 `contract_not_flat_at_start`。這樣處理合理。
13. `_remove_stop_after_flat` 和 `_protect` 只接 `BotStopped`／`SupervisorUnavailable`。交易所回來的 tag 不符、帳本的 identity mismatch 這類 `ProtocolError` 會讓 run 變成 `failed`。仍是 fail-closed。
14. **測試衛生（與 A／B 無關）**：完整測試會把鎖檔寫進真正的 `~/.catos/local-simulation-locks`。例如 test_step2_deployment／test_strategy_folder 的重播沒有 patch `account_lock.LOCK_DIRECTORY`；在我轉向的假家目錄裡，一次完整測試留下 17 個鎖檔。真正的目錄裡今天 17:45 之前已經有 317 個新鎖檔，不是我造成的（見下面「執行紀錄」）。
15. `docs/risk-period-r1-local-sim.md:42` 還列著已刪除的 `test_demo_quiescent_e0`／`test_demo_reconciliation`。這是歷史文件，可以不改。

## A（077cdd0a）核對

- base 468f72eb 裡，被刪模組除了彼此互相引用，只有 `catos/supervisor.py`、`catos/execution.py` 引用到（`git grep`）。workspace API、CLI、local-sim、重播、研究、demo bot、MCP 都沒有用到。
- HEAD 下 `.py`、`.ts`、`.tsx`、`.mjs`、`.bat`、`.json` 都找不到殘留引用，只剩 `__pycache__` 的舊 .pyc：Python 不會從 `__pycache__` 載入沒有原始碼的模組，`import_all.py` 也確認八個被刪模組都是 `ModuleNotFoundError`。`catos/` 的 63 個模組和 `tools` 全部 import 成功；`python -m catos.cli --help` 正常。
- 沒用授權碼的呼叫端，行為逐段比對過：
  - 移除的分支都受 `require_demo_trade_grant`（預設 False）控制。
  - `dispatch` 少了一次讀 `reduce_only` 和一次會立刻回 None 的呼叫。
  - `_submit_prepared` 沒進 handoff 時，`_execution_sync` 從兩次變一次；它是冪等的，載入同一份快照。
  - `prepare`／`_insert` 只少一個可選參數，`stored_payload` 內容不變。
- 一個語意差異：`expected_demo_uid_sha256` 以前必須和帳本綁定證明成對，現在可以單獨傳。目前沒有任何呼叫端傳這個參數，不影響執行中的路徑。
- 資料庫結構：兩個 commit 都沒有改到 SCHEMA、CREATE／ALTER TABLE 或 user_version。唯一的 schema 版本字樣在被刪的 demo_ledger_preflight 唯讀檢查器裡。

## B（ed72bbe8）各焦點結果

| 焦點 | 結果 |
|---|---|
| 1 加倉閘門 | 停損缺少、過期、沒確認或失敗時，加倉在決策與送出兩處都會被擋。拿掉作廢沒有削弱保證（觀察 1）。反手整筆被拒見觀察 2。 |
| 2 停損觸發 | 分鐘檢查、K 線、接續都走 `_reconcile` 的「沒列出就 verify」路徑，偵測得到。觸發後以 `disaster_stop_triggered` 停下，之後不送單；重開時 OKX 空倉就開新 run，仍有部位就再停一次。order_failed 的對應見觀察 3。清倉中觸發見 D1、D5。 |
| 3 不確定的建立、改單、撤單 | 都不重送，只查詢（trace 證據）。`_protection_settled` 查 3 次仍不明就停下，不猜。沒找到會丟 OwnershipError 的路徑：對帳證據的 `conditional_open` 照帳本產生，位置在查完停損之後。會丟出的是 `ProtocolError`（觀察 13、D4）。問題在 D1、D2。 |
| 4 對帳證據與陌生條件單 | 有核對 `conditional_open` 和 OKX 是否列出我們的 `algoClOrdId`；陌生條件單在非清倉時會停下。被別人撤掉時會重掛（觀察 4）；被別人改價時不會發現（D3）。 |
| 5 Kill／Hard 清倉時停損還掛著 | 平倉後會撤停損，撤單失敗只提醒（觀察 12）。但停損狀態不明時清倉本身會被擋（D1）。 |
| 6 接續 | 停損還掛著時，先查詢確認再接續；比例改了會改單（作者測試）；改成 0 時撤單並等確認才算完成（`test_12`）；改單被拒見觀察 6。 |
| 7 OKX API 對應 | 見下節，都沒有實測。 |
| 8 revision | 同一個程序內嚴格遞增；跨重啟依賴牆鐘（D4）。 |
| INVARIANTS | 每筆條件單都帶 tag `41cb53c54d6dABDE`、`closeFraction=1`、`reduceOnly=true`、cross／net、不帶 `sz`（`test_13`）；預設 0% 時完全不送條件單（作者測試）；tick 取整多倉向上、空倉向下（94.5、99.0、99.75→99.8）；全程用 Decimal（`_percent`、`_dec`、revision 是 int，沒有 float）；比例只來自 `--disaster-stop`，manifest 有記錄，不在部署設定裡。 |

## OKX API 對應（都沒有實測，只依文件與經驗判斷）

- 下條件單 `POST /api/v5/trade/order-algo`：送 instId、tdMode=cross、side、posSide=net、ordType=conditional、closeFraction="1"、reduceOnly=true、slTriggerPx、slTriggerPxType=mark、slOrdPx="-1"、algoClOrdId（32 位 hex）、tag。照文件應該可行：closeFraction 只收 1，net 模式要 reduceOnly=true，不能帶 sz。**沒實測**：每個部位只收一張整倉 TP/SL 的限制、模擬盤是否接受 tag。
- 改單 `POST /api/v5/trade/amend-algos`：用 algoClOrdId＋reqId＋newSlTriggerPx／newSlOrdPx／newSlTriggerPxType。**沒實測**：整倉 TP/SL 是否可改、`newSlTriggerPxType` 是否被接受、改完多久查得到新價（程式只輪詢 4 次）。
- 撤單 `POST /api/v5/trade/cancel-algos`：送陣列 `[{instId, algoId}]`，格式符合文件。
- 查詢 `GET /api/v5/trade/order-algo?algoClOrdId=`。**沒實測**：查不到時的代碼（程式假設 51603／51000）、canceled／effective 的歷史是否查得到，以及保留多久。
- 狀態值：live／pause／effective／partially_effective／order_failed／partially_failed／canceled，和文件一致。
- 列表 `GET orders-algo-pending`：ordType 必填。**沒實測**：整倉 TP/SL 是否以 conditional 列出，以及是否帶回 algoClOrdId。
- **沒實測**：OKX 平倉時是否自動撤整倉 TP/SL。兩種行為程式都處理得了（`test_06` 和作者測試）。
- 時間預算：一次建立加 4 次查詢、3 次 0.3 秒等待，再加每個請求 0.25 秒的間隔，延遲高時可能超過 Supervisor 的 5 秒上限；超時會留在 pending，之後以查詢處理，安全。

## 執行紀錄

| 指令（worktree 根目錄） | 結果 |
|---|---|
| `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_demo_bot.py"` | Ran 37，OK（40.4 s） |
| `... -p "test_protection*.py"` | Ran 19，OK（2.4 s） |
| `... -p "test_*.py"`（USERPROFILE／HOME 轉到 scratchpad 的假家目錄，`CATOS_STRATEGY_APPROVALS`／`CATOS_KILL_SWITCH` 指到 scratchpad） | Ran 861，OK（191.8 s），log：`...\acceptance-p6\full_suite.log` |
| `python -m unittest -v scenarios_p6`（cwd＝scratchpad，PYTHONPATH＝worktree;worktree\tests） | Ran 40（含匯入的 27 個 DemoBotTests），1 FAIL＝`test_01`（D1 證據），其餘通過，`scenarios_run1.log` |
| `... scenarios_p6.P6Acceptance2` | Ran 4，OK（01b／01c／14／14b，結果記在輸出的 JSON），`scenarios_run2.log` |
| `... scenarios_p6.P6Acceptance3` | Ran 2，OK（15／16），`scenarios_run3.log` |
| `... trace_check.Trace.test_lost_create_posts` | Ran 1，OK（建立只送一次） |
| `import_all.py`、`python -m catos.cli --help` | 63 個模組 import 成功，8 個被刪模組都 import 不到；CLI 正常 |

情境的斷言主要用來記錄實際行為。缺陷以每個情境印出的 `[編號] {...}` JSON 為準，不看斷言是否通過。

**一次中止的執行**：第一次跑完整測試時，我沒有轉向家目錄。開始後約一分鐘，我發現測試會寫 `~/.catos/local-simulation-locks`，就立刻停掉。之後只看了那個目錄的檔名與時間戳（只讀中繼資料）：最新的鎖檔建立於 17:44:49–17:45:19，我的那次執行約在 17:58 開始，沒有新增檔案。`~/.catos/okx-demo-accounts/` 完全沒有碰。

## 沒有驗證的

- 所有 OKX 實際回應（見上節），包括模擬盤的延遲對 5 秒上限的影響。
- 前端四項檢查：A／B 都沒有改前端（`git diff --stat` 空白），所以沒跑。
- 真實的程序被殺（例如在 prepare 寫入後、HTTP 送出前被殺）。只用「請求沒送到 OKX」模擬，結果相同（D2）。
- local-sim（FakeExchange）的 P6 路徑：只以 test_protection 的 19 項和完整測試作為證據，沒有另外做情境。
- 沒有檢視使用者在 `C:\dev\CatOS` 執行中的 Bot，也沒有在那裡做任何操作。
