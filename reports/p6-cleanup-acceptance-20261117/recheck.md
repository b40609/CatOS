# 重驗：P6 保底停損修正（04a84107）

- 日期：2026-11-17
- 驗收者：獨立會話（沒有參與 ed72bbe8 和 04a84107）
- 範圍：只重驗 acceptance.md 的 D1、D2、D3、D5，以及新的 `_reconcile` 可能造成的回歸。看的是 `git diff ed72bbe8..04a84107`，程式只改了 `catos/demo_bot.py`；`protection.py`、`journal.py`、`execution.py`、`supervisor.py` 都沒動。
- worktree `C:\Users\user\.t3\worktrees\CatOS\feat-wp-b-kill-switch-7bd55fc4c3125468`，分支 feat/agent-strategy，HEAD = 04a84107。
- 隔離方式：
  - 沒有連網，沒有碰 `C:\dev\CatOS`，沒有開憑證檔，沒有執行 `catos.cli demo`。
  - 情境測試都用 `tests/test_demo_bot.py` 的 setUp：鎖目錄、帳戶目錄、`CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH` 都轉到暫存目錄。
  - 跑完整測試時，HOME／USERPROFILE 轉到 scratchpad 的假家目錄。
  - `~/.catos/` 沒有讀也沒有寫。`catos/` 沒有改。
- 腳本都在 `C:\Users\user\AppData\Local\Temp\claude\06a2d6733c105b8e\e959d5a4-c8a1-4a67-830d-e90e8ab84b74\scratchpad\recheck-p6\`，下文簡稱 `recheck-p6\`：
  - `recheck_p6.py`
  - `recheck_p6_partial.py`
  - `debug_r05c.py`
  - 也重跑了第一位驗收者在 `acceptance-p6\` 的 `scenarios_p6.py`、`trace_check.py`。

## 結論

**PASS with observations**

- D1：修好了。停損沒確認時，Kill 和 Hard 都會送只減倉單，清到 OKX 部位 0；Hard 也會寫入 Kill-Switch。停損觸發但部位還在、帳本也對得上（order_failed）時，按 Kill 一樣會清倉。
- D2：修好了。
  - 停損沒確認不再讓 run 停下。
  - 加倉、反手、重新進場都會被擋，平倉照樣允許。
  - 不會重送，告警只出現一次。
  - `protection_unconfirmed` 的停下提示已經刪掉。
- D3：修好了。觸發價或觸發來源被改時，只送一次改單就改回來，不會重送建立。方向被改的情形會一直改單，見觀察 O3。
- D5：acceptance.md 列的兩則訊息都改對了。但新的那則「OKX 已經平倉」，在停損只平掉一部分時是錯的（N1）。
- 回歸：沒有找到會多送單或放寬加倉閘門的路徑，INVARIANT 沒有被削弱。
- 有兩個低嚴重度缺陷，不擋交付：
  - N1 是這次新加的訊息不準，改一個判斷條件就能修。
  - N2 是原本就有的：停損觸發了但部位還在時，Hard 不會執行。commit 訊息說「已觸發時 Kill／Hard 照樣清倉」，Hard 那一半不成立。

## 新缺陷

### N1（低）：停損只平掉一部分時，清倉訊息說「OKX 已經平倉」，部位其實還在

- 位置：
  - `catos/demo_bot.py:555-557`：D5 新加的訊息。
  - `catos/demo_bot.py:361`：清倉中只要停損已觸發，而且 OKX 部位跟帳本不同，就丟 `disaster_stop_triggered`。
- 情境：`recheck-p6\recheck_p6_partial.py` `test_p1_partial_fire_during_kill`。多 1 張、停損已掛上，OKX 把停損標成 `partially_effective`，部位剩 0.5，同時使用者按 Kill。
- 預期：
  - 訊息依 OKX 的實際部位寫：部位是 0 才說已經平倉，不是 0 就說部位還在、要手動平倉。
  - 帳本沒有補記 OKX 的平倉（使用者 11-17 選「停下並提示」），所以停下本身是合理的。
- 實際：
  - `flatten_failed:disaster_stop_triggered`，OKX 部位 0.5，只送過開倉那一張。
  - 終端機顯示「清倉途中 OKX 的保底停損先觸發了，OKX 已經平倉：請到 OKX 網頁確認部位是 0；Kill-Switch 維持觸發」。
  - CLI 結尾另外印「清倉沒有完成：請到 OKX 網頁確認模擬盤部位，必要時手動平倉。」，前後矛盾。
- 修法建議：第 555 行的判斷再加上 OKX 部位是 0（例如把部位帶進例外，或在 `_flatten` 再讀一次部位）。
- 機率：要整倉市價停損只成交一部分才會發生，很低。

### N2（低，原本就有）：停損觸發了但部位還在時，Hard 不執行，Kill-Switch 也不寫

- 位置：
  - `catos/demo_bot.py:620-621`：`_intrabar_check` 先 `_reconcile` 再 `_observe`。
  - `catos/demo_bot.py:361`：不是清倉中、停損已觸發，就直接丟例外，Hard 根本不會被評估。
  - `_execute`、`_bar` 的順序一樣。
- 情境：
  - `recheck_p6.py` `test_r01t_hard_and_order_failed_in_the_same_minute`：同一次分鐘檢查，OKX 把停損標成 `order_failed`（部位 1 還在），虧損也超過 Hard（12%）。
  - `recheck_p6_partial.py` `test_p2_partial_fire_and_hard`：`partially_effective`，部位剩 0.5，加上 Hard。
- 預期：INVARIANTS 寫「Hard 啟動市價清倉及 Kill-Switch」，而且合法減倉一律允許。order_failed 時帳本和 OKX 部位一致，清倉送得出去（同樣狀態下按 Kill 就能清，見 `test_r01k`）。
- 實際：
  - 兩個情境都停在 `disaster_stop_triggered`，OKX 部位 1／0.5，沒有停損，沒有清倉，Kill-Switch 沒寫入。
  - 重開會在 `_protect` 再停一次（`disaster_stop_triggered`），只能由使用者到 OKX 手動平倉。
  - README.md:175 和 demo_bot 的 docstring 都寫「OKX 那時已經空倉」，這兩種狀態下不成立。
- 對照：`test_p3_fired_flat_and_hard_then_restart`（停損 effective，OKX 已空倉）的第一次 run 也沒寫 Kill-Switch，重開的新 run 第一次觀察就以 `risk_flat:hard_loss` 寫入。所以空倉的情形最後會補上，部位還在的情形不會。
- 判斷：
  - 不是這次修正造成的，舊程式也是 `_protection_settled` 先丟例外。第一份驗收在觀察 3 認為 order_failed 停下是安全的，但沒考慮同時碰到 Hard。
  - 單幣上限 0.5 倍權益時，10% 的停損大約只虧 5%，要同時碰到 Hard 需要更大的跳空。機率低。
  - 牽涉「觸發後停下並提示」和 Hard 規則的先後順序。建議由使用者定案，例如：觸發但帳本和 OKX 部位一致時，先跑 `_observe`，碰到 FLAT 就清倉，其餘才停下。

## 1. D1：Kill／Hard 清倉

| 情境 | 結果 |
|---|---|
| `scenarios_p6 test_01`：停損其實掛上了、回應遺失、條件單查詢一直 50001，然後 Kill | `manual_kill`，送單是 buy 開倉、sell 只減倉，OKX 部位 0。原本的斷言現在通過。 |
| `scenarios_p6 test_01b`：建立請求沒送到 OKX，然後 Kill | `manual_kill`，OKX 部位 0 |
| `scenarios_p6 test_01c`：建立請求沒送到 OKX，接著 Hard（12%） | `risk_flat:hard_loss,soft_loss`，OKX 部位 0，Kill-Switch 已寫入 |
| `recheck_p6 test_r01h`：test_01 的故障再加上 Hard | `risk_flat:hard_loss,soft_loss`，部位 0，Kill-Switch 紀錄是 `engage`／`demo-bot`，條件單只送過一次建立 |
| `recheck_p6 test_r01k`：OKX 標成 order_failed（部位還在），同時 Kill | `manual_kill`，送出只減倉單，部位 0 |
| `scenarios_p6 test_10`：停損觸發和 Kill 同時發生 | `flatten_failed:disaster_stop_triggered`，OKX 部位 0，沒有多送單，訊息正確 |
| 作者的兩個新測試（Kill／Hard，建立請求遺失） | 通過 |
| 停損部分觸發，或觸發後碰到 Hard | 見 N1、N2 |

帳本端的閘門：`ExecutionJournal.flatten` 的 `_known` 要求 `conditional_open == int(active is not None)`。Bot 的對帳證據就是用同一個值產生的，所以停損是 pending 或不確定時，清倉單照樣送得出去。

## 2. D2：停損沒確認時 run 不再停下

| 檢查 | 證據 | 結果 |
|---|---|---|
| 反手被擋 | `test_r02a`（建立請求沒送到 OKX，跑完全部 K 線） | 第 6 根 `REJECTED protection_gate_closed`，target -1，只送過開倉單 |
| 重新進場被擋、出場照樣送 | `test_r02b`（自訂 K 線：進場、出場、再進場） | 出場 `legal_reduction` 有送出；第 7 根再進場 `REJECTED protection_gate_closed`。對照組 `test_r02c` 沒有故障，會正常再進場。 |
| 反手的開倉腿被擋 | `test_r02d`（反手時撤舊停損的請求沒送到 OKX） | 平倉腿送出，開倉腿沒送，訊息是「反手的開倉腿被風控擋下，維持空倉繼續跑」 |
| 不重送 | `test_r02a`（trace）、`trace_check` | 建立：整個 run 和重開加起來只有 1 次 POST，之後都是查詢（29 次）。撤單：只有 1 次 POST。 |
| 告警只出現一次 | `test_r02a`、`test_r02b` | `protection_alert`（protection_unconfirmed）事件 1 筆，終端機「保底停損單還沒確認…」1 行 |
| 停下提示已刪 | `demo_bot._hint("protection_unconfirmed")` 回 None；`git grep` 找不到任何 `BotStopped("protection_unconfirmed")` | 是 |
| run 不再停下 | `scenarios_p6 test_02` | 第一次 run 和重開都跑到 K 線用完（`bar_not_published`），不再停在 `protection_unconfirmed`。這個測試會失敗，是因為它的斷言寫的是修正前的行為，屬預期。 |

## 3. D3：OKX 上的停損被改

| 情境（`recheck_p6`） | 條件單寫入 | OKX 最後狀態 |
|---|---|---|
| `r03a` 觸發價改成 80 | 建立 → 改單（1 次） | 94.5、sell、mark |
| `r03b` 觸發來源改成 last | 建立 → 改單（1 次） | 94.5、sell、mark |
| `r03d` 同價不同寫法（"94.50"） | 只有建立，沒有誤判 | — |
| `r03f` 改價和 Kill 同時發生 | 建立 → 撤單 | 部位 0，清倉沒被擋 |
| `r03e` 改價，而且 OKX 拒絕改單 | 建立 → 改單 ×3（每次檢查 1 次） | 一直是 80，加倉一直擋著 |
| `r03c` 方向改成 buy | 建立 → 改單 ×5（約 10 分鐘） | 方向改不回來，見 O3 |

- 所有情境都沒有第二次建立。改單前都先以查詢確認，不算盲目重送。
- 不會無限迴圈：價格和觸發來源改一次就回來。改單被拒或方向不符時，每次檢查送一次改單，有頻率上限，加倉一直擋著。方向不符見 O3。

## 4. D5：訊息

- `test_10`：訊息改成「清倉途中 OKX 的保底停損先觸發了，OKX 已經平倉…」，符合 OKX 部位 0。部分觸發時不對，見 N1。
- `test_16`：清倉時帳戶裡有別的合約部位，停損確實撤掉了。現在沒有 `protection_left` 訊息（`protection_left: []`），正確。
- `test_15`：撤單請求遺失，停損還掛在 OKX 上。「保底停損單還沒確認撤掉：部位已是 0…」，正確。
- 新的三則 ALERTS 文字和實際行為一致，但「Bot 會繼續查」有時永遠查不出結果（O2）。

## 5. 回歸

- **觸發後要停下 run**：
  - 作者的 `test_a_fired_stop_ends_the_run…`、`scenarios_p6 test_05`（order_failed）、`test_10`（清倉中觸發，OKX 部位和帳本不同）都以 `disaster_stop_triggered` 結束。觸發後不再送單，重開也一樣停下。
  - 查詢故障期間觸發，停下原因變成 `position_mismatch`（O4），仍然停下，不會送單。
- **把 pending 請求的 algoClOrdId 當成自己的，是對的**：
  - 這個 id 是帳本用 `digest(account:bot:protection:serial)` 產生的。建立時是新 id，改單和撤單沿用 active 的 id，同一時間最多一筆。
  - 如果不算進來，建立回應遺失之後，下一次分鐘檢查會把自己的停損當成陌生單而停下。`test_r05b` 證實現在會繼續跑，下一次 `_protect` 查到後就確認了，流程正常。
  - 用舊 serial、已經判為 REJECTED 的單，仍然算陌生（和第一份驗收的觀察 9 相同）。
- **`conditional_open` 仍等於帳本的 active**：
  - `demo_bot.py:371-372` 用的是 verify 之後的 guard（`int(guard["active"] is not None)`），之後到 `supervisor.reconcile` 之間沒有任何保護操作。
  - `execution.check_reconciliation`（execution.py:314）沒改。所有情境的對帳都沒有出現 OwnershipError。
- **接續時，繼承的停損確認後才套用新比例**：
  - `test_r05c`：10% 改成 5%，前 4 次查詢失敗。查詢時間在 306、366、426、486 秒都失敗，546 秒成功，同一秒才送改單（99.8）。
  - `debug_r05c.py`：Kill 比查詢成功還早時，一直沒送改單，等清倉後才設定並撤單。
  - `scenarios_p6 test_12`：10% 改成 0，撤單。
  - `test_r05d`：0 改成 10%，接續時建立。
  - 作者的 `test_resume_keeps_the_stop_and_applies_the_new_ratio`：通過。
  - 新開 run 仍在 `_warm_up` 嚴格設定（demo_bot.py:828），失敗就以 `protection_config_failed` 停下。

## 6. INVARIANT

- 不確定或失敗時禁止加倉：`ProtectionJournal.blocked()`、`Journal._risk_verdict`（journal.py:692）、`ExecutionJournal.prepare`（execution.py:112）都不在 diff 裡。D2 的三個情境都有擋住。
- 不自動減倉：diff 沒有新增任何送單路徑。送單仍只經過 Supervisor 的 dispatch／flatten_step／protection_step。
- 合法減倉一律允許：出場（`r02b`）和 Kill／Hard 清倉（D1 表）在停損不確定時都送得出去。例外是 N2，原本就有。
- UNKNOWN 不重送：建立、撤單都只送一次（trace）。verify 只把狀態標成不確定，接著只查詢。
- 固定 tag、整倉、只減倉、cross／net：`scenarios_p6 test_13` 通過。

## 觀察（不擋交付）

- **O1：清倉後不會提醒 OKX 上可能留著條件單。**
  - 情形：帳本裡是 pending 的建立請求、沒有 active 時，`_remove_stop_after_flat`（demo_bot.py:584）直接 return。
  - 證據：`test_01`、`test_r01h` 結束時 OKX 上還有 1 張 live 條件單，沒有 `protection_left` 訊息。
  - 影響：下次啟動會擋在 `contract_not_flat_at_start`，仍是 fail-closed。實際 OKX 平倉時可能會自動撤掉整倉停損，但沒實測過。
- **O2：會卡住的情形比 next-steps 寫的多，提示也誤導。**
  - 撤單請求沒送到 OKX（`test_r02d`）也會卡住：OKX 回 LIVE，但 pending 的撤單永遠不結清（protection.py:272，原本就是這樣）。run 空倉繼續跑，不再交易。
  - 提示寫「Bot 會繼續查」，但建立沒送到和撤單沒送到這兩種情形，永遠查不出結果，而且只提示一次。
  - 建議 next-steps 補上撤單的情形，或者提示改成「可能要空倉重開」。
- **O3：方向不符時，每次檢查都改單，而且永遠改不回來。**
  - amend 不能改方向。`test_r03c` 10 分鐘內送了 5 次改單，終端機沒有任何訊息（`protection_alert` 事件 0 筆），加倉一直擋著。
  - OKX 介面不能改條件單的方向，所以只有 OKX 回報的方向和送出的不同才會遇到。
  - 建議：方向不符就停下 run；至少要印出告警。
- **O4：查詢故障期間停損觸發，停下原因是 `position_mismatch:okx=0:ledger=1`。**
  - 不是 `disaster_stop_triggered`，也沒有提示（`test_r05a`）。
  - 不會送單，重開時 OKX 空倉，是新的 run。
  - 在清倉中遇到時，訊息會是「部位可能還在 OKX 上」，但其實已經空倉。
- **O5：CLI 結尾和事件訊息矛盾。** `flatten_failed:disaster_stop_triggered` 時，CLI 一律印「清倉沒有完成…必要時手動平倉」，exit code 2（demo_bot.py:1107-1109）。
- **O6：order_failed 時按 Kill 的訊息不清楚。**
  - `test_r01k` 清倉成功，最後一行卻是「保底停損單還沒確認撤掉…」（實際上停損已經觸發失敗，不是還掛著）。
  - 整段沒有告訴使用者 OKX 的停損觸發失敗。
- **O7：清倉模式的 `_reconcile` 只接 `SupervisorUnavailable`。**
  - `protection_verify` 丟出的 `ProtocolError`（D4 時鐘倒退、tag 或 algo_id 不符）仍會中斷清倉，run 變成 failed。
  - 舊程式的 `_protection_settled` 也是這樣，不是回歸。要完全做到「停損不擋清倉」，清倉模式可以把這類例外也接住，記錄後繼續。
- **O8：接續時設定失敗只記一筆 `protection_wait`，終端機沒有訊息。**
  - 如果舊比例是 0、新比例不是 0，設定失敗期間加倉會照舊比例走，也就是不掛停損。
  - 要發生，必須在 `_recover` 對帳後，帳本部位和保護狀態的張數還不同。實際上走不到。
  - 另外，只在 Kill 清倉時才查到繼承的停損時，「保底停損：…5.00%…」那行會出現在「清倉完成」之後，只是外觀問題。
- **O9：文件與作者測試。**
  - README.md:175「OKX 那時已經空倉」不完全成立（N2）。
  - next-steps.md:107 還寫「`DisasterStopTests` 7 項」，現在是 10 項。
  - 作者的 `test_a_stop_changed_on_okx_is_put_back` 對結束狀態的斷言很寬（`or state == "stopped"`）。
  - 作者的 `lose_algo_create` 模擬的是請求沒送到 OKX，沒有涵蓋「已經掛上但回應遺失，而且查詢一直故障」。這個情形由 `test_01`、`test_r01h` 補上。
- **O10：測試衛生（和第一份驗收相同）。** 完整測試在假家目錄留下 17 個 `.catos/local-simulation-locks/*.lock`。完整測試也在 worktree 的 `outputs/` 留下 `workspace-w6/w8-fixture-test-*`，這是 git 忽略的路徑，不是正式資料根。

## 執行紀錄

所有指令都在 worktree 根目錄，或在 `recheck-p6\` 執行（PYTHONPATH 設為 `acceptance-p6;worktree;worktree\tests`）。

| 指令 | 結果 |
|---|---|
| `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_demo_bot.py"` | Ran 40，OK（47.8 s），`recheck-p6\demo_bot.log` |
| `... -p "test_protection*.py"` | Ran 19，OK（2.6 s），`recheck-p6\protection.log` |
| `... -p "test_*.py"`（HOME／USERPROFILE＝`recheck-p6\fakehome`，`CATOS_STRATEGY_APPROVALS`／`CATOS_KILL_SWITCH` 指到 `recheck-p6\envtmp`） | Ran 864，OK（235.4 s），`recheck-p6\full_suite.log`。和作者報的 864 一致。 |
| `python -m unittest -v scenarios_p6.P6Acceptance scenarios_p6.P6Acceptance2 scenarios_p6.P6Acceptance3 trace_check.Trace` | Ran 33，2 FAIL，`recheck-p6\old_scenarios.log`。兩個都是 `test_02`：一個在 scenarios_p6，一個是 trace_check 繼承來的重複；斷言寫的是修正前的 `protection_unconfirmed`，屬預期。`test_01`（D1 證據）現在通過，其餘也都通過。`[編號]` JSON 列出實際行為。 |
| `python -m unittest -v recheck_p6` | Ran 17，OK（24.5 s），`recheck-p6\recheck_run2.log`。第一次執行 `recheck_run1.log` 有 4 個失敗，都是我腳本自己的問題：沒送到 OKX 的請求不在 `algo_posts` 裡，改成從 trace 計數；R05c 的 Kill 時間太早。修正腳本後全部通過，產品程式沒有變。 |
| `python -m unittest -v recheck_p6_partial` | Ran 3，OK（只記錄行為），`recheck-p6\recheck_partial.log`。N1、N2 的證據。 |
| `python -m unittest debug_r05c` | Ran 4，OK（印出接續時查詢與改單的時間線） |

## 沒有驗證的

- OKX 的實際回應，同第一份驗收：
  - partially_effective／order_failed 時部位怎麼呈現。
  - 平倉時是否自動撤掉整倉停損。
  - orders-algo-pending 是否帶回 `slTriggerPx`／`side`／`slTriggerPxType`。這三個欄位缺了，D3 的比對每次檢查都會多查一次，不影響正確性。
- D4（時鐘倒退）不在這次範圍；作者記在 next-steps。`scenarios_p6 test_07` 的結果和之前相同：`ProtocolError: conflicting protection evidence`。
- 前端：這次 diff 沒有改到前端，所以沒跑前端檢查。
- 這份報告沒有 commit。
