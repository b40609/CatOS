# 獨立驗收：11-18 的 6 個少見情況修正（commit b9e406a4）

- 驗收者：Claude Opus（沒有參與這次改動），2026-11-18，獨立驗收（verify）
- 範圍：`git show b9e406a4` 的 `catos/execution.py`、`catos/okx_demo_exchange.py`、`catos/okx_demo.py`、`catos/demo_bot.py`，以及 `tests/test_demo_bot.py` 的 `RareCaseTests`、`tests/test_execution.py` 的 `test_a_reduction_held_across_a_restart_still_goes_out`
- 沒有改 `catos/`、`tests/`，沒有 commit／push，沒有連 OKX、沒有讀金鑰，沒有執行 approve／revoke／rearm／kill clear，沒有碰 `outputs/` 的正式資料。所有 Bot 情境都用 `tests/test_demo_bot.py` 的 `FakeOkx`，Kill-Switch、核准紀錄、帳戶鎖都用隔離路徑（借用 `DemoBotTests.setUp`），每次執行都用暫存家目錄，執行後暫存家目錄都是空的。

## 結論：FAIL

6 個情況與延伸項目，在我自己寫的情境裡都能重現「修好前會出事、修好後不會」。但情況 6 的修法有一個缺陷（D1）：新比例裝不上時，接續的 run 仍能反手開出新部位，而且這個部位一直沒有保底停損。這違反了 `docs/next-steps.md:83` 寫的「維持禁止加倉」。修好之前，這個部位用的是舊比例的停損，所以在這個情境下，這次改動反而讓保護變少了。

D1 的觸發前提是 `configure_protection` 在接續時一直失敗。我找不到自然會讓它一直失敗的原因，只能跟開發者自己的測試一樣用 mock 造出來，所以實際發生的機率低。不過，「新比例裝不上時禁止加倉」正是這次修正宣稱的保證，修法也很便宜，因此列為必修。其他項目都通過，另有 6 條觀察。

## 測試與整套檢查

| 指令 | 結果 |
|---|---|
| `T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"` | `Ran 894 tests in 225.957s` / `OK`；暫存家目錄執行後為空（`scratch/fullsuite.log`） |
| 同上，分別用 `-p test_execution.py`、`-p test_protection.py`、`-p test_demo_bot.py` | 25、19、59 個測試，都是 `OK` |
| 前端四項 | 沒跑：這個 commit 沒有改前端 |

自寫的情境放在 `scratch/`：
- `scen_bot.py`：Bot 層，16 個測試。
- `scen_exec.py`：`ExecutionJournal.prepare` 層，8 個測試。

修好前與修好後的對照做法如下：
- `git archive b9e406a4^ catos tests` 解到 `scratch/old`，`git archive b9e406a4 catos tests` 解到 `scratch/new`（HEAD 就是 b9e406a4）。
- 同一份情境腳本只換 `PYTHONPATH` 裡的 `catos/`。
- 測試輔具（`FakeOkx`）兩邊都用 b9e406a4 的版本。

重跑方式（在 `scratch/` 裡執行；v 換成 `new` 或 `old`）：

```
B='C:\dev\CatOS\reports\rare-cases-acceptance-20261118\scratch'
P="$B"'\'"$v;$B"'\new\tests'
T=$(mktemp -d)
HOME=$T USERPROFILE=$T PYTHONPATH="$P" /c/dev/CatOS/.venv/Scripts/python.exe -m unittest scen_bot -v
```

彙總如下：
- `scen_bot`：新版 `Ran 16`、`FAILED (failures=2)`，失敗的是 D1（S6b）和 O1（S3b）。舊版 `Ran 16`、`FAILED (failures=9, skipped=3)`，失敗的都是預期中「修好前會出事」的情境。
- `scen_exec`：新版 `Ran 8`、`OK`。舊版 `FAILED (failures=1)`，失敗的是 E1，也就是修好前的行為。

完整輸出在 `scratch/run_bot_{new,old}.log`、`scratch/run_exec_{new,old}.log`。

## 逐項

### 情況 1：平倉單結果不明時停下，重開時 OKX 已空倉

程式：
- `catos/demo_bot.py:706-712`：空倉且沒有 `--new-run` 時，呼叫 `_unsettled_flat_run`。
- `catos/demo_bot.py:754-793`：帳本有 `settled=0` 的委託時，用 `_resumable_run` 檢查能不能接續，再檢查停多久；不能接續就在新 run 寫 `previous_run_unsettled`。
- `_resumable_run`（`catos/demo_bot.py:795`）在有未結清委託時不比部位。接著由 `_recover` 查詢（不重送），查不清楚就停下（`resume_unresolved_orders`）。

| 情境 | 修好前（old） | 修好後（new） |
|---|---|---|
| S1a：反手平倉回應遺失，停下；過 2 根 K 線再重開 | `new_run_dir_created= True old_ledger_unsettled= 1` | `new_run_dir_created= False old_ledger_unsettled= 0 posts_after_restart= []` |
| S1c：Soft（虧 6%）已鎖住，反手只平倉的回應遺失，空倉重開 | `run2_exists= True old_unsettled= 1` | `run2_exists= False old_unsettled= 0 posts_after= []`：接續後只查不送，Soft 照樣擋加倉 |
| S1b：同 S1c，改用 `--new-run` | （沒有這個參數） | `run2_soft_latched_event= True old_unsettled_kept= 1 posts_after= []`：開新 run，舊帳本保留；帳戶層的 Soft 鎖住仍然生效，沒有任何加倉 |
| S1d：停下 400 根 K 線後才重開 | （沒有這個行為） | `notes= [('resume_gap_too_long', 1)] old_unsettled= 1`：開新 run 並記錄原因 |

S1d 新 run 的停止原因是 `bar_not_published`。這是我的情境沒有後續 K 線造成的，跟這次修正無關。

風險檢查：
- 只有 OKX 空倉時才會走 `--new-run` 或 `_unsettled_flat_run`。有部位時仍走原本的 `_resumable_run`，而且一定要帳本擁有那個部位（`catos/demo_bot.py:703-705`）。
- Hard 鎖存在共用的 Kill-Switch 紀錄，Soft 鎖存在帳戶紀錄，`--new-run` 都跳不過，S1b 已實測。例外見 O5。

### 情況 2：決策到送單之間風控改變（epoch 改變）

程式：
- `catos/execution.py:117-119`：只減倉的意圖，在目前狀態仍核准、而且不是 FLAT 時才放行。
- `catos/execution.py:190-194`：反手的平倉腿在非 FLAT 時，忽略 eligible 與 epoch，但仍要重新評估成只減倉到 0（`verdict.reduce_only`、`quantity == -position`），而且不能有未結清委託。
- 加倉列仍然要 `row["epoch"] == state.epoch`。

`scen_exec.py`，直接操作帳本（建立在 `tests/test_execution.py` 的 setUp 上）：

| 情境 | old | new |
|---|---|---|
| E1：多 2，決策平倉後 Soft 鎖住 | `request= None` | `request= ('sell', '2', True)` |
| E2：同 E1，改成 Hard | `None`、ABORTED、保留額度 0 | 同左（交給清倉流程） |
| E3：同 E1，改成 manual_kill | `None` | `None` |
| E4：加倉決策後 Soft 鎖住 | `None`、保留額度 0 | 同左 |
| E5：加倉決策後健康度降級又恢復（mode 回到 RUN、epoch +2） | `None` | `None`：放寬沒有讓加倉通過 |
| E6：決策時是多 2、要賣 2；送單前已驗證部位變成 1 | `None` | `None`：數量不符，不會超賣、不會穿越零點 |
| E7：Soft 之後，但已經過期限 | `None` | `None` |
| E8：已送過一次、結果 UNKNOWN 後 Soft 鎖住，再 prepare | `again= None state= UNKNOWN` | 同左：不重送，也不釋放 |

延伸項目（反手的平倉腿），Bot 層，在第 2 次 `_execute` 前改掉 `risk_state`（手法同開發者的測試）：

| 情境 | old | new |
|---|---|---|
| S2a：反手決策後健康度變 DEGRADED | `dispatch_returned_nothing posts= [('buy', False)] okx_position= 1`：帶著部位停下 | `posts= [('buy', False), ('sell', True)] okx_position= 0`：平倉腿送出，開倉腿被擋，繼續跑到 Kill |
| S2b：反手決策後變成 manual_kill（FLAT） | `dispatch_returned_nothing`，部位 1 | 同左：FLAT 時不會由 dispatch 送平倉腿，見 O4 |

### 情況 3：條件單在 OKX 上被改成限價或部分張數

程式：
- `catos/okx_demo.py:253-260`（`altered_stop`）。
- `catos/okx_demo_exchange.py:193-198`：LIVE 但被改過時 `complete=False`，帳本維持不確定、禁止加倉。
- `catos/demo_bot.py:353-358`：在列表上看出被改，就記 `protection_altered` 並查詢一次。

| 情境 | old | new |
|---|---|---|
| S3a：K 線 4 之後把停損改成限價 `slOrdPx=94`；使用者在 K 線 5 後 30 秒撤掉 | `altered_events= 0`，K 線 5 反手開空照送：`('sell', False)` | `altered_events= 1`，只送 `('buy', False), ('sell', True)`，空單沒開 |
| S3c：每張條件單都帶真實 OKX 的 live 形狀（`slOrdPx -1`、`closeFraction 1`、`sz ""`，來源是 `reports/okx-demo-protection-check/1794980390196.json:107-110`） | 沒有誤判 | `altered= False`，下單與條件單序列跟 old 完全相同：不會誤判 |
| S3b：部分張數以 `closeFraction ""`、`sz "0.5"`、`slOrdPx -1` 的形狀出現 | 沒偵測到 | **也沒偵測到**（`altered_detected= False`），空單照開，見 O1 |

### 情況 4：只改觸發來源（價格不變）的改單

程式：`catos/okx_demo_exchange.py:157-159`，改單要等查到價格與觸發來源都一致才算完成。

| 情境 | old | new |
|---|---|---|
| S4a：OKX 上的來源被改成 `index`，改回 mark 後要再查 2 次才看得到 | 改單送了 3 次 | 改單只送 1 次，最後來源是 `['mark']` |
| S4b：延遲 6 次，超過輪詢上限 4 次 | 改單 5 次 | 改單 2 次，最後來源 mark，正常跑到 Kill（延遲超過輪詢時會多送一次，可以接受） |

### 情況 5：OKX 回空的觸發來源

程式：`catos/okx_demo_exchange.py:193`，以及 `catos/demo_bot.py:358` 的 `or "last"`。

| 情境 | old | new |
|---|---|---|
| S5a：欄位整個拿掉 | `state= failed stop_reason= ProtocolError: invalid confirmed protection` | 改單改回 mark，正常跑到 Kill |
| S5b：欄位是 `""` | 同上，run 失敗 | 同上，正常 |

### 情況 6：接續時新比例裝不上

程式：`catos/demo_bot.py:414-421`。

| 情境 | old | new |
|---|---|---|
| S6a：用 10% 停下時是多 1，用 5% 接續，`configure_protection` 一直被拒（FakeOkx 預設：平倉後不自動撤條件單） | 接續後用舊比例撤單、再掛 `order-algo 99.0` | 沒有任何條件單寫入；反手只平倉，開倉被擋：通過 |
| S6b：同 S6a，但 FakeOkx 照 11-18 實測「平倉後 OKX 自動結束條件單」（`auto_cancel_on_flat=True`） | 開空前沒有停損，開空後掛上舊比例 99.0（下一筆單送出前看到 `('-1', ['99.0'])`） | **開出空單 -1，直到 Kill 都沒有任何停損**（`('-1', [])`），見 D1 |
| S6c：空倉接續（情況 1）加上比例裝不上 | — | 這段 K 線沒有新進場，沒重現問題 |

## 缺陷

### D1：新比例裝不上時，接續的 run 仍能開新部位，而且這個部位沒有保底停損

- 位置：
  - `catos/demo_bot.py:414-421`：不能 configure 就直接 return，註解寫「the journal keeps increases blocked」。
  - `catos/protection.py:121-133`（`blocked()`）。
  - 文件宣稱「維持禁止加倉」：`docs/next-steps.md:83`。
- 原因：
  - 帳本沒有「這次的比例還沒裝上」這個狀態，`blocked()` 只看「舊比例算出的應有停損」是否等於「現有停損」。
  - 反手的平倉腿成交後，OKX 會自動結束整倉停損（11-18 實測）。帳本對帳後 active 變成 None，空倉時應有停損也是 None，兩者相等，所以 `blocked()` 回 False。
  - 結果開倉腿通過 `prepare`（`catos/execution.py:120` 的保護檢查）送出。之後每次 `_protect` 都在第 421 行直接 return，新部位一直沒有停損。
- 重現：
  1. 執行 `scratch/scen_bot.py` 的 `S6ResumeRatioNotInstalled.test_s6b_okx_auto_cancels_on_flat_then_reversal_opening_leg`。情境是：用 10% 跑到多 1 後以 stop.request 停下；`fake.auto_cancel_on_flat = True`；mock `LocalSupervisor.configure_protection` 讓它一直拋 `SupervisorUnavailable`；用 5% 接續。
  2. new 的輸出：`posts= [('buy', False), ('sell', True), ('sell', False), ('buy', True)] before_each_order(pos, live stops)= [('1', ['94.5']), ('0', []), ('-1', [])]`，也就是開空送出，到 Kill 清倉前都沒有停損。
  3. old 的輸出：`[('1', ['94.5']), ('0', []), ('-1', ['99.0'])]`，空單有舊比例的停損。
- 測試漏洞：`RareCaseTests.test_resume_never_uses_the_old_ratio_while_the_new_one_is_not_installed`（`tests/test_demo_bot.py:1266`）用的是 FakeOkx 預設的 `auto_cancel_on_flat=False`（`tests/test_demo_bot.py:74`）。這跟模擬盤實測相反，舊停損一直被列出，開倉腿才被擋下，所以測不到這條路。這個測試也只斷言最後部位是 0，不看中間有沒有開過倉。
- 發生機率：要 `configure_protection` 在接續時一直失敗。它會失敗的情況只有帳本 owner 部位不等於保護帳的 quantity、保護不確定，或 Supervisor 不可用；我找不到自然的長期觸發。如果只是短暫失敗，開倉後下一次 `_protect` 會重試 configure，然後掛上停損。
- 建議修法（擇一，由開發者決定）：
  - 在 `self.protection_configured` 為 False、而且這次要求的比例不是 0 時，讓非只減倉的委託在 `prepare` 被擋。例如由 Supervisor 帶一個 `refuse_increase` 原因，或在保護帳記一個「設定待裝」旗標，讓 `blocked()` 回 True。
  - 補測試：`auto_cancel_on_flat=True` 加上斷言「全程沒有在無停損時持有非零部位」。

## 觀察（建議，不擋驗收）

### O1：「部分張數」的偵測大概碰不到真實的改法

`altered_stop` 只在 `closeFraction` 有值而且不是 1 時才判定被改（`catos/okx_demo.py:260`）。

真實 OKX 上，改成固定張數比較可能長成 `closeFraction ""` 加上 `sz` 有值；這是推測，**待驗證**，我沒找到可引用的官方原文。這種形狀不會被判定成被改，S3b 新版的輸出是 `altered_detected= False`，而且空單照開。

模擬盤實測顯示 live 狀態的 `sz` 是空的，觸發後（effective）才會填（`reports/okx-demo-protection-check/1794980390196.json:110`、`:206`）。而 `altered_stop` 只會用在 LIVE 的列上：
- `catos/okx_demo_exchange.py:197` 只在 status 是 LIVE 時呼叫。
- `catos/demo_bot.py:353` 用的是 `orders-algo-pending` 的列。

所以「LIVE 但 `sz` 不是空的」可以當成被改的證據，不會跟觸發後填入的 `sz` 衝突。

重現：執行 `scen_bot.py` 的 `S3AlteredStop.test_s3b_partial_size_as_okx_would_show_it`。單元測試 `test_the_fill_size_okx_adds_after_firing_is_not_an_alteration`（`tests/test_demo_bot.py:1224`）只測了 `close_fraction "0.5"` 這種不太可能出現的形狀。

### O2：情況 2 的 Bot 層測試靠直接改寫 `supervisor.risk_state` 走到路徑

`test_a_soft_latch_before_the_reversal_still_closes_the_long`（`tests/test_demo_bot.py:1184`）直接改寫 `supervisor.risk_state`，繞過 `_accept_risk` 與 `halt_reasons`。

正常的 `_bar` 流程裡，決策到送平倉腿之間沒有新的觀測，實際上很難遇到。放寬本身是安全的：我在帳本層的 E1 到 E8 驗過，只放行減倉，FLAT、Hard、Kill、過期、數量不符、UNKNOWN 都不放行。只是這個測試證明的是機制，不是 Bot 真的會遇到的時序。

另外，`tests/test_execution.py` 新測試的註解寫「Before, the resumed Demo Bot stopped on it」。但 `_recover` 會等到期限過了才 dispatch 留下的意圖（`catos/demo_bot.py` 的 `_recover`），所以接續時，這筆意圖本來就會因為過期被擋，跟 epoch 無關。註解容易誤導。

### O3：被改過的條件單一直不撤，帳本會長期停在「不確定」

使用者不去 OKX 撤掉的話，每次檢查都只做查詢，帳本一直不確定、禁止加倉。這是設計，有提示，也沒有盲目重送。

如果 OKX 平倉後沒有自動結束這張單（例如限價版），下次空倉啟動會被 `contract_not_flat_at_start:algo_orders=1` 擋下。S6c 在 FakeOkx 預設不自動撤單時就是這樣停的：`contract_not_flat_at_start:position=0:orders=0:algo_orders=1`。需要使用者手動處理，和提示一致。

### O4：既有行為，這次沒有改變

反手決策後如果變成 FLAT（Kill／Hard），`dispatch` 不會送平倉腿，Bot 以 `dispatch_returned_nothing` 停下並保留部位，不會走清倉（S2b 新舊相同）。這是既有行為，這次沒有改變，而且正常時序走不到（Kill 在每根 K 線開頭檢查，Hard 在成交後的觀測會走 `_flatten`）。

如果之後有任何路徑會在這兩步之間鎖成 FLAT，`_execute` 收到 None 時應該改走 `_flatten`，而不是直接停下。

### O5：`--new-run`（和舊版空倉重開一樣）不會讀舊帳本內的 Soft 鎖存

如果當初存帳戶紀錄失敗，Soft 只留在舊帳本裡，開新 run 就看不到這個鎖存。接續的路徑有補回（`_resume` 的「帳本的 Soft 鎖住沒有對應的 demo rearm」），新 run 沒有。

這跟 b9e406a4 之前空倉重開的行為一樣，不是新風險。`--new-run` 是使用者主動選的，建議在說明裡註明。

### O6：`_unsettled_flat_run` 讀不到上一個 run 的帳本時，靜默開新 run，不寫 `previous_run_unsettled`

位置在 `catos/demo_bot.py:771-772`。程式註解有說明，只是使用者事後看不出曾經有一個讀不到的舊 run，可以考慮也記一筆。

## 沒做的事

- 沒有連 OKX 驗證以下行為（都只用 FakeOkx 模擬）：O1 的固定張數形狀、`slTriggerPxType` 回空字串的實際情況、只改來源的改單在 OKX 上的顯示延遲。
- 沒有跑前端檢查，因為這個 commit 沒有改前端。
- `catos/okx_demo_protection_check.py` 的改動只是顯示條件，我讀過，沒有另外寫情境。
