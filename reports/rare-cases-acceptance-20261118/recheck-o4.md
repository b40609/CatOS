# 窄範圍重驗：Gemini 第二意見 O4（commit 31e57015）

- 驗收者：Claude Opus（同一位獨立驗收者，沒有參與修改），2026-11-18
- 範圍：只重驗 `git show 31e57015` 的程式改動：
  - `catos/demo_bot.py`：新增 `_reconcile_if_marked`（`:446-452`），在 `_protect` 的三個地方使用：第一步之後（`:423`）、例外路徑（`:428`）、結尾（`:444`）。
  - `catos/okx_demo.py:262`：判斷「有張數」時也涵蓋 `pause` 狀態。
  - 回歸測試 `ResumeProtectionMarkTests`。
- 限制：沒有改 `catos/`、`tests/`，沒有 commit，沒有連 OKX，沒有動 Gemini 的檔案（`gemini-second-opinion.md`、`scratch/verify_*.py` 只讀不改）。全部用 FakeOkx 與隔離路徑，每次執行都用暫存家目錄，執行後都是空的。

## 結論：PASS

- X1、X2 都修好了。
- 21 個一般、清倉、接續情境中，修好前後的行為逐項相同，包括每一次 `_reconcile` 呼叫。
- 沒有多出來的對帳，也沒有新的停止原因。
- 沒有新缺陷，也沒有新觀察。

## 對照方式

- 把 3064346c（修之前）解到 `scratch/prev`（`git archive 3064346c catos`）。HEAD 就是 31e57015。
- 情境腳本會先 import 指定版本的 `catos` 套件，並斷言 `catos.demo_bot.__file__` 確實來自那個版本，再跑同一組情境。

## 1. X1、X2

我沒有改 Gemini 的探測腳本，用 `scratch/o4_runner.py` 包一層，先固定 `catos` 的來源，再執行 `verify_uncommitted_recheck.py` 的 `test_probe_x1…`、`test_probe_x2…`：

```
catos from: ...\scratch\prev\catos
  [PROBE X1: pending algo_create + 0% + >=2 missed bars] state=failed, stop_reason=SupervisorUnavailable: synthetic reconciliation required before processing
  [PROBE X2: pending algo_cancel + 5% + >=2 missed bars] state=failed, stop_reason=SupervisorUnavailable: synthetic reconciliation required before processing
catos from: C:\dev\CatOS\catos
  [PROBE X1: pending algo_create + 0% + >=2 missed bars] state=stopped, stop_reason=manual_kill:kill-switch-…
  [PROBE X2: pending algo_cancel + 5% + >=2 missed bars] state=stopped, stop_reason=manual_kill:kill-switch-…
```

回歸測試的檢查：
- 拿 HEAD 的 `ResumeProtectionMarkTests` 配舊的 `catos`（prev）跑：`Ran 2`、`FAILED (failures=2)`，兩個都是 `state: failed … synthetic reconciliation required before processing`。
- 在 HEAD 跑 `discover -p test_demo_bot.py`：`Ran 61 tests`、`OK`。

所以這兩個回歸測試確實走到了要測的路徑：修好前失敗，修好後通過。它們斷言停止原因是 `manual_kill`、OKX 部位最後是 0、條件單的狀態，不只是「沒有出錯」。

## 2. 一般檢查與清倉時，沒有多餘的對帳或新的停下原因

程式判讀：
- `_reconcile_if_marked` 只看 `supervisor.health == "RECONCILING"`。
- 這個值在 `protection_step` 結尾由 `_execution_sync` → `_load` 讀自帳本（`catos/supervisor.py:641-643`、`:185`）。
- 保護處理只有在 active 從無到有、或從有到無時，才會呼叫 `_dirty` 把帳本標成待對帳（`catos/protection.py` 的 `apply`）。只改價格不會標記。
- 呼叫 `_protect` 之前，每個呼叫點都先完成 `_reconcile`，帳本已是 `LOCAL_READY`：
  - `_bar`
  - 成交後的 `_execute`
  - 每分鐘的 `_intrabar_check`（`catos/demo_bot.py` 約 `:648-660`）
  - `_resume` 前的 `_recover`
  - 清倉完成後的 `_flatten_rounds`
- 所以一般路徑上，觸發對帳的條件跟原本「處理前後一有一無」相同。多出來的只有「兩步各翻一次、結果看起來沒變」的 O4 情況。
- 例外路徑（`:428`）：
  - 原本只記 `protection_wait`，現在帳本被標記時也會對帳。
  - Supervisor 故障時 `health` 會被設成 `DEGRADED`（`catos/supervisor.py:166`、`:185`），不會在故障中觸發對帳。
  - 清倉時唯一的 `_protect(flattening=True)` 呼叫點是 `_remove_stop_after_flat`，它會把 `BotStopped` 接住、改記 `protection_left`（約 `:610-621`）。所以即使對帳在這裡發現陌生條件單或部位不符，也不會打斷已完成的清倉。

實測：`scratch/scen_o4.py` 用監看包住 `DemoBot._reconcile`，記下每一次呼叫（標籤、是否在清倉中），並比對停止原因、下單、條件單寫入。修好前、修好後各跑一次，`Ran 18 tests`、`OK`，共 21 筆情境結果，**全部相同**（`same=True`），包括完整的 `_reconcile` 呼叫序列：

```
a_basic                      manual_kill   對帳(protection) prev=4 head=4
b_auto_cancel                manual_kill   prev=2 head=2
c_hard                       risk_flat:hard_loss,soft_loss   prev=0 head=0
d_soft                       manual_kill   prev=2 head=2
e_kill_foreign_algo          manual_kill   prev=2 head=2   （Kill 當下出現陌生條件單，清倉中）
f_foreign_algo_minute        foreign_algo_orders_on_contract:999   prev=1 head=1
g_position_mismatch_minute   position_mismatch:okx=2:ledger=1      prev=1 head=1
h_position_mismatch_flatten  manual_kill   prev=2 head=2
i_cancel_race / i_finished_vanish / i_lag_after_cancel / i_lose_algo_create / i_reject_amend   都相同
j_partial                    order_partially_filled:canceled   prev=1 head=1
k_trigger                    disaster_stop_triggered          prev=1 head=1
l_resume_10_to_5 / l_resume_same / l_resume_off（各含第一段）  都相同
```

明細在 `scratch/o4_prev.json`、`scratch/o4_head.json`。

說明：h（清倉後才出現的外部空單）在兩個版本都是 Kill 清倉完成後就結束，所以沒有走到「清倉中部位不符」。陌生條件單在清倉中和每分鐘檢查的情況，分別由 e 和 f 涵蓋，兩個版本的結果一致。

## `pause` 狀態

`altered_stop` 現在把 `pause` 加上 `sz` 有值也當成被改過。live、effective、canceled 的實測形狀都不受影響（上一輪 R6 驗過，這次的改動沒有碰到那幾條）。OKX 的 `pause` 狀態會不會帶 `sz`，沒有實測紀錄，待驗證；就算會，結果也只是帳本維持不確定、禁止加倉，不會送出任何東西。

## 整套

- `T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"`：`Ran 896 tests in 288.664s`、`OK`（`scratch/fullsuite-o4.log`）。
- 前端沒跑，因為這次沒有改前端。
