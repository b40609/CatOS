# 重驗：反手只平倉的重播修正（D1）

- 對象：commit `a1b220c8`（branch `feat/agent-strategy`），worktree `C:\Users\user\.t3\worktrees\CatOS\feat-wp-b-kill-switch-7bd55fc4c3125468`
- 重驗者：沒有寫這次修正、也不是第一次驗收的會話（Claude Opus 5.5），2026-11-17
- 範圍：只重驗 D1 影響的部分，也就是 `catos/local_sim_replay.py` 的 `_fill_intent`、下游讀成交與腿名稱的程式（`replay_consistency`、`replay_api`、前端 replay 介面、`workspace_snapshot`），以及 `demo_bot.py` 的成交標籤（O2）。
- 隔離：沒有碰 `C:\dev\CatOS`，沒有連網，沒有讀憑證，沒有改 `catos/`，沒有 commit。所有腳本和整套測試都把 `HOME`／`USERPROFILE` 導到 `scratchpad\recheck-reversal\home`，`CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH` 指到暫存路徑；重播腳本另外把 `account_lock.LOCK_DIRECTORY` 設到各自的輸出資料夾。跑完後確認真正的 `~/.catos/` 還是 854 個檔，21:00 之後沒有任何檔案被修改。
- 腳本：`C:\Users\user\AppData\Local\Temp\claude\06a2d6733c105b8e\e959d5a4-c8a1-4a67-830d-e90e8ab84b74\scratchpad\recheck-reversal\`（`replay_scenarios.py`、`resume_after_close_only.py`、`test_recheck_demo_label.py`；輸出在 `run1.log`、`run2.log`、`full-suite.log`）

## 結論：PASS with observations

D1 修好了。`reversal_close_only` 在重播裡現在以意圖自己的 key 送出一筆只減倉單，數量剛好是 -部位。run 會跑完，帳本三張表都清空，一致性比對也照實報告和回測不同。一般的兩腿反手沒有退化。

另外找到一個低嚴重度的新缺陷 N1：決策落在最後一根 K 線時，一致性比對會誤報 PASS。這個問題在 `27845a20` 就引入了，這次修正沒有處理，第一次驗收也沒抓到。預設與正式 profile 都碰不到，所以不擋這次交付，但建議修掉，修完只要重驗 N1。

## 1. 重播處理 reversal_close_only

`replay_scenarios.py`：donchian 4/2、預熱 4、1 張、本金 1000，`Limits(L, 0.5, 0.05, 0.10)`。

| 情境 | 結果 |
|---|---|
| D1 原情境：空翻多超額，`100×4,90×4,130×5`，L=0.002 | `completed`，13 根，2 筆成交。intents：seq 5 `exposure_reserved`，seq 9 `RESERVED_SIMULATION/reversal_close_only`（target 存 `1`）。第 2 筆委託的 order_key／intent_key 就是 seq 9 意圖本身，`buy 1`、`reduceOnly=True`、tag `41cb53c54d6dABDE`、`FILLED`、settled=1。部位 0，`reservations`／`outbox`／`risk_orders` 都是空的。events 的腿名是 `close_only`。一致性 `passed=False`：`fills_equal`、`equity_curve_equal`、`final_account_equal`、`realized_and_fees_equal` 都是 False，`replay_completed`、`orders_terminal`、`risk_verdicts_ok` 是 True。研究端是 `+2 @130.03`，重播是 `+1 @130.03` |
| 多翻空超額：`100×4,110,150×4,140×4`，L=0.0025 | `completed`。seq 10 是 `reversal_close_only`，送出 `sell 1 reduceOnly=True`，key 是意圖本身，部位 0，三張表清空，一致性 `passed=False`（研究端 `-2 @139.97`） |
| close-only 之後再進場：`100×4,90×4,130×3,80×4`，L=0.002 | `completed`，3 筆成交（開空、只平倉、重新開空）。三張表清空，部位 -1，一致性 `passed=False` |
| close-only 成交後停下，再接續跑（`resume_after_close_only.py`，同上序列，第 10 根 `operator_stop`） | 停下時部位 0、三張表 0/0/0；`resume=True` 之後 `completed`，15 根、3 筆，一致性 `passed=False`。不再出現 D1 的 `resume_with_unresolved_orders` |
| close-only 落在最後一根：`100×4,90×4,130`，L=0.002 | `completed`。seq 9 是 `reversal_close_only`，照設計留成 pending（沒送單；`risk_orders` 是 `quantity=1, reduce_only=1`，`outbox` 是 `HELD_SIMULATION`，`reservations` 的 amount 是 0）。但一致性報告是 **PASS**，見 N1 |
| Soft：`100×4,90×4,6000×3`，L=1 | `stopped`，`risk_halt:soft_loss`，停在第 8 根，三張表清空。Soft 在決策前的 `observe`（`local_sim_r4.py:155-156`）就停止整個 run，所以重播裡走不到「Soft 鎖存下的 close-only」。和第一次驗收第 5 節的結論一致 |

先前 D1 的症狀（`report client id mismatch`、`SUBMITTING` 卡單、保留額度沒釋放）都沒有再出現。

## 2. 兩腿反手沒有退化

- 預設序列，L=1.0（`default_two_leg`）與 `risk.Limits()` 預設值（`default_legacy`）：都 `completed`，9 筆腿成交、5 筆合併成交、4 次反手。平倉腿的 key 是 `{"kind":"reversal_close",...}`，`reduceOnly=True`；開倉腿是意圖 key，`reduceOnly=False`；events 腿名依序是 `single`、`close`／`open`。一致性 10 項全部 PASS，研究端成交逐筆相同。
- `test_step2_deployment.py` 的 `test_reversals_go_out_as_two_legs_and_match_research_exactly` 和其他重播測試都通過（見第 4 節）。

## 3. 新腿名 `close_only` 和下游

- `replay_consistency.ledger_facts`（`replay_consistency.py:56-69`）不讀 events 的腿名，是從帳本 order_key 推出腿（`intent`／`reversal_close`）。close-only 成交記成 `intent`，`fill_rows`、`fills_sha256` 和 `reversal_decisions` 都不受影響（close-only 只有一腿，不算反手）。
- `replay_api._run` 只讀 manifest、status、summary、consistency，不讀 events 或腿名。前端 `contracts/replay.ts`、`replay-api-adapter.ts`、`replay-panel.tsx` 沒有任何腿名欄位。
- `workspace_snapshot` 讀 events.jsonl，但只接受 `mode == "local-sim-synthetic"`，不會讀重播的 run（`local-sim-historical-replay`）。
- 模擬盤 Bot（O2）：`test_recheck_demo_label.py` 重跑 `test_soft_loss_blocks_increase_but_keeps_running`，再確認 `fills.json` 的 leg 是 `["開倉／調整", "反手只平倉"]`，通過。`demo_bot` 接續時讀 `fills.json` 只檢查它是不是 list，不依標籤做判斷。正式測試裡沒有斷言這個標籤（見觀察 R2）。

## 缺陷

### N1（低）：決策落在最後一根 K 線的 close-only，一致性比對會誤報 PASS

- 位置：
  - `catos/local_sim_replay.py:342-343`：pending 記的是 `target=str(receipt.target_position)`，也就是策略原本的反向目標，不是實際會做的「平到 0」。
  - `catos/replay_consistency.py:228-232`（`pending_intent_equal` 只比 target）
  - `catos/replay_consistency.py:239-242`（`risk_verdicts_ok` 把 `RESERVED_SIMULATION/reversal_close_only` 當成正常）
- 重現：`replay_scenarios.py <worktree> <out> last_bar_close_only`，序列 `100,100,100,100,90,90,90,90,130`，`Limits(0.002, 0.5, 0.05, 0.10)`。
  - 新版（`a1b220c8`，`27845a20` 也一樣，因為最後一根不經過 `_fill_intent`）：`completed`，`consistency_passed=True`，10 項全部 PASS。summary 的 `pending_intent.target="1"`，研究端 pending 也是 `+1`。實際上帳本保留的是一筆 `quantity=1, reduce_only=1` 的只平倉單，也就是平到 0 而不是翻成 +1。
  - 改動前（`27845a20^`，`acceptance-reversal\oldtree`）：`stopped`，`unexpected_verdict:REJECTED:symbol_exposure_limit`，一致性 `passed=False`。
- 影響：只發生在重播最後一根，沒有成交差異，沒有資金風險。但一致性報告說「部署路徑執行了和研究相同的決策」，最後一個決策其實不同。這是 `27845a20` 之後才出現的假 PASS。正式 profile（1 張、本金 10,000）碰不到，見第一次驗收第 5 節。
- 建議修法（擇一）：
  - `replay_consistency` 把 `reason == "reversal_close_only"` 列進 `rejected_verdicts`，讓 `risk_verdicts_ok` 失敗。
  - 或者 pending 記實際動作（target `0`，並附 reason），讓 `pending_intent_equal` 失敗。

  兩種都要補一個「最後一根 close-only」的重播測試。

## 觀察（不是缺陷）

- R1：`local_sim_replay.py:230` 的 manifest `model` 文字、模組 docstring（`:16-17`）和 `_fill_intent` 的 docstring（`:135`）還是寫「反手是平倉腿加開倉腿」，沒有提到 close-only。程式旁邊的註解（`:137-138`）有寫。
- R2：`demo_bot.py:535-536` 新的「反手只平倉」標籤沒有正式測試斷言，只有我的暫存測試驗過。
- R3：整套測試照舊在 worktree 的 `outputs/workspace-w6-fixture-test-*`、`workspace-w8-fixture-test-*` 留下 fixture 證據，被 git 忽略，`git status` 是乾淨的。這是既有測試的行為，跟這次修正無關。

## 執行過的指令與結果

在 worktree 根目錄執行，`HOME`／`USERPROFILE` 導到 `scratchpad\recheck-reversal\home`，`CATOS_STRATEGY_APPROVALS`／`CATOS_KILL_SWITCH` 指到暫存檔：

| 指令 | 結果 |
|---|---|
| `git show a1b220c8` | 改了 `local_sim_replay.py`（+5/-2）、`demo_bot.py`（+2/-1）、測試 +20 行，另加第一次驗收報告 |
| `.venv/Scripts/python.exe scratchpad/recheck-reversal/replay_scenarios.py <worktree> <run1>` | 7 個情境，結果見第 1、2 節（`run1.log`） |
| `.venv/Scripts/python.exe scratchpad/recheck-reversal/replay_scenarios.py <oldtree 27845a20^> <run-old> last_bar_close_only` | `stopped`，`REJECTED:symbol_exposure_limit`，一致性 False |
| `.venv/Scripts/python.exe scratchpad/recheck-reversal/resume_after_close_only.py <worktree> <run2>` | 停下 → 接續 → `completed`，一致性 False（`run2.log`） |
| `PYTHONPATH=<worktree> .venv/Scripts/python.exe -m unittest discover -s scratchpad/recheck-reversal -p "test_recheck_demo_label.py"` | Ran 1 test，OK |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_step2_deployment.py"` | Ran 24 tests，OK |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_demo_bot.py"` | Ran 42 tests，OK |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"` | Ran 867 tests，OK（和作者回報一致；`full-suite.log`） |

前端檢查沒有跑：這次修正沒有碰前端，前端也沒有讀腿名的程式。
