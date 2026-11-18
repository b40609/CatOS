# 窄範圍重驗：D1、O1、O6（commit 3064346c）

- 驗收者：Claude Opus（同一位獨立驗收者，沒有參與修改），2026-11-18
- 範圍：只重驗 `git show 3064346c` 影響到的部分：
  - `catos/demo_bot.py` 的 `_configure_protection`、`_protect` 兩個呼叫點，以及 `_unsettled_flat_run`
  - `catos/okx_demo.py` 的 `altered_stop`
  - 測試的改動
- 限制：沒有改 `catos/`、`tests/`，沒有 commit，沒有連 OKX。全部用 FakeOkx 與隔離路徑，每次執行都用暫存家目錄，執行後都是空的。

## 結論：PASS（有觀察）

- D1 已修好。
- 新比例裝得上的一般接續（換比例、同比例、關掉比例、繼承的停損一時查不到）都沒有被誤停。
- O1 不會把實測的 live 形狀誤判成被改過。
- O6 有寫事件。

新增一條觀察（O7），不擋驗收。

## 改動摘要（自己讀過程式）

- `catos/demo_bot.py:386-395`：`_configure_protection` 失敗一律 `BotStopped("protection_config_failed:…")`。
- `catos/demo_bot.py:414-416`、`:419-422`：接續時兩個呼叫點都改呼叫這個會停下的版本，不再 return 繼續跑。兩個呼叫點都只在繼承的停損不是 pending／uncertain／triggered 時才嘗試，這點沒有變。
- 清倉時呼叫 `_protect` 的路徑也檢查過：只出現在 `_remove_stop_after_flat`，而且那裡會接住 `BotStopped`、改記 `protection_left`（`catos/demo_bot.py:610-621`）。所以設定失敗不會打斷 Kill／Hard 的清倉。
- `catos/okx_demo.py:261-262`：多判一條「`state == "live"` 而且 `sz` 不是空的、也不是 "0"」。
- `catos/demo_bot.py:765-770`：讀不到上一個 run 時，在新 run 記 `previous_run_unsettled` 事件，`reason=previous_run_unreadable`。

## 1. D1：重跑 S6b

指令（在 `scratch/` 裡）：

```
T=$(mktemp -d)
HOME=$T USERPROFILE=$T PYTHONPATH='C:\dev\CatOS;C:\dev\CatOS\tests' /c/dev/CatOS/.venv/Scripts/python.exe -m unittest scen_bot.S6ResumeRatioNotInstalled scen_bot.S3AlteredStop -v
```

結果：

```
OUTCOME[new] S6a stop_reason= protection_config_failed:synthetic algo_writes_after_resume= [] posts= [('buy', False)] before_each_order(pos, live stops)= []
OUTCOME[new] S6b stop_reason= protection_config_failed:synthetic posts= [('buy', False)] before_each_order(pos, live stops)= []
OUTCOME[new] S6c stop_reason= protection_config_failed:synthetic posts= [('buy', False), ('sell', True)] before_each_order(pos, live stops)= [] run2_exists= False
Ran 6 tests in 9.957s
OK
```

`scen_recheck.py` 的 R1 是同一個情境，另外檢查了 OKX 上的狀態：

```
OUTCOME[new] R1 stop_reason= protection_config_failed:synthetic posts= [('buy', False)] before_each_order= [] algo_writes_after_resume= [] okx_position= 1 stops= [('94.5', 'live')]
```

接續後沒有送出任何委託，也沒有任何條件單寫入。多 1 的部位與已確認的停損 94.5 都留在 OKX 上，沒有開出沒有停損的部位。

上一輪新版的輸出是 `('-1', [])`，也就是空單沒有停損，現在已經消失。S6c（空倉接續加上比例裝不上）也一樣在下單前停下。

## 2. 一般接續沒有被誤停（新比例裝得上）

`scratch/scen_recheck.py`，沒有 mock `configure_protection`：

| 情境 | 結果 |
|---|---|
| R2：用 10% 停在多 1，用 5% 接續；FakeOkx 平倉後自動撤停損，條件單是實測的形狀（live 時 `sz ""`，觸發後 `sz` 有值） | `manual_kill`（正常跑到 Kill）。先把停損改到 `99.8`（105 × 0.95 向上取整到 0.1），反手後替空單掛 `94.5`。每筆單送出前的狀態是 `[('1', ['99.8']), ('0', []), ('-1', ['94.5'])]`，`altered= False` |
| R3：用同樣的 10% 接續 | `manual_kill`，委託序列 `buy／sell(只減倉)／sell／buy(只減倉)` 完整 |
| R4：用 0%（關掉）接續 | `manual_kill`，接續後撤掉舊停損，沒有留下停損 |
| R5：停下前讓條件單查詢延遲，接續後第一次仍查不到 | `manual_kill`，正常交易。我沒有確認這次帳本確實停在「不確定」，只能證明「繼承的停損查詢延遲」時接續不會誤停 |

既有的接續測試都通過，包括 `test_resume_keeps_the_stop_and_applies_the_new_ratio` 與 `test_resume_*` 系列：

```
discover -p test_demo_bot.py    Ran 59 tests   OK
discover -p test_okx_demo.py    Ran 24 tests   OK
discover -p test_execution.py   Ran 25 tests   OK
discover -p test_protection.py  Ran 19 tests   OK
整套 discover -p "test_*.py"     Ran 894 tests in 257.093s  OK
```

整套的輸出在 `scratch/fullsuite-recheck.log`。

## 3. O1：正常的 live 停損不會被誤判

R6，直接呼叫 `altered_stop`，前三個形狀取自 `reports/okx-demo-protection-check/` 的兩份實測紀錄：

```
[('live/sz=', False), ('effective/sz=0.01', False), ('canceled/sz=', False), ('live/sz=', False), ('live/sz=0', False), ('pause/sz=0.5', False)]
```

另外，`state=live, closeFraction "", sz "0.5"` 回傳 True。

- R7：全程用實測形狀，停損由 OKX 觸發（effective，`sz` 有值）。結果是 `disaster_stop_triggered`、`altered= False`，觸發後的 `sz` 沒有被誤判。
- S3c：全程用 live 形狀，`altered= False`，委託與條件單序列跟上一輪相同。
- S3b：上一輪漏掉的固定張數形狀，現在偵測到了（`altered_detected= True`），空單沒開。

兩份實測紀錄裡，`order-algo` 的 live 列（建立後、改單後）`sz` 都是空的（`1794979993705.json` 的 create／amend、`1794980390196.json` 的 create）。

## O6

R8：第一個 run 在空倉時停下，把它的 manifest.json 弄壞後重開。結果是 `notes= ['previous_run_unreadable']`，開新 run 並記錄。

## 新觀察

### O7：`orders-algo-pending` 在 live 時的 `sz` 形狀沒有實測紀錄（待驗證）

`altered_stop` 也用在 `_reconcile` 讀到的條件單列表上（`catos/demo_bot.py:353`）。這份列表來自 `orders-algo-pending`（`catos/okx_demo.py` 的 `pending_algos`），但兩份實測紀錄只有 `order-algo`／history 的形狀，沒有 pending 列表的。

如果 pending 列表對整倉停損也回傳有值的 `sz`：
- 每次對帳都會記一筆 `protection_altered`，並查詢一次。
- 接著 `order-algo` 的查詢（實測 `sz ""`）會把停損確認回來，所以不會長期禁止加倉。
- 影響是事件紀錄很吵，每根 K 線多一次查詢。

建議下次跑 protection-check 時，把 `orders-algo-pending` 的原始列也記下來。

## 腳本與紀錄

- `scratch/scen_recheck.py`（R1–R8）、`scratch/run_recheck.log`：`Ran 8 tests`、`OK`。
- `scratch/scen_bot.py`：S3／S6 類別以 HEAD 重跑，`Ran 6`、`OK`。
- 沒跑前端，因為這次沒有改前端。
