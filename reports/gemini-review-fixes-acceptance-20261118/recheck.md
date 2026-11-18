# 重驗：commit 7a3d142c（驗收 D1、O1、O2，Gemini 第二意見 #3）

- 日期：2026-11-18
- 重驗者：Claude Opus 5.5，與 `acceptance.md` 是同一個驗收會話，沒有參與開發
- 範圍：只驗 7a3d142c 動到的地方：
  - `catos/okx_demo_exchange.py` 的 `with_history`
  - `catos/demo_bot.py` 的 `_flatten_rounds`、部分成交停下的訊息、`START_HINTS`、`_reconcile` 的告警事件
  - `tests/test_demo_bot.py` 新增的 3 項 `ReviewFixTests`
- 限制：沒改 `catos/`、`tests/`，沒連網，沒讀金鑰或 `~/.catos/`。HOME／USERPROFILE 都導到暫存資料夾，跑完檢查是空的。

## 結論

**PASS**。D1、O1、O2 和 Gemini #3 都修好了，沒有新的缺陷。

## 逐項

### 1. D1：撤單後第一次查不到時先只重查（`okx_demo_exchange.py:146-147`）

- 程式：撤單時，第 0 輪 `with_history` 回 False，只查 `order-algo`，這時 NOT_FOUND 不算結算；第 1 輪起才補查歷史，NOT_FOUND 才算結算。`algo_query` 照舊一次就查歷史。`algo_create`、`algo_amend` 沒變。
- 用 `test_accept_lag.py` 重跑：
  - 7a3d142c：`posts: [('buy', False), ('sell', True), ('sell', False), ('buy', True)]`，反手照常完成。
  - 5ca49b93：`posts: [('buy', False), ('sell', True)]`，開倉腿被擋下。
- 請求數與 5 秒逾時（O3）：用 `count_requests.py` 直接數 adapter 的請求，floor 是只算節流 0.25 秒／請求與輪詢 0.3 秒，不含網路延遲。

  | 撤單情境 | 7a3d142c | 5ca49b93 |
  |---|---|---|
  | LIVE 三次後查不到、歷史也沒有（最壞） | 9 個請求、3 次 sleep、floor 3.15 秒 | 9、3、3.15 秒 |
  | 一直 LIVE | 6、4、2.70 秒 | 6、4、2.70 秒 |
  | 撤單後立刻查不到、歷史有 canceled | 7、1、2.05 秒 | 6、0、1.50 秒 |
  | 撤單後立刻查不到、歷史也沒有 | 7、1、2.05 秒 | 6、0、1.50 秒 |
  | 撤單前就查不到、歷史有 canceled | 6、1、1.80 秒 | 5、0、1.25 秒 |

  最壞情況沒變。常見路徑多 1 個請求、多 0.3 秒，仍在 5 秒內。逾時情境（`test_history_lookup_timeout`，每次查條件單延遲 1.4 秒）重跑：沒有多送任何寫入（`writes: ['order-algo', 'order-algo']`），最後部位 0，結果仍然安全。
- 預期中的差異：我原本寫的 `test_adapter_not_found_anywhere_stays_not_found_for_cancel` 斷言 5 個請求，現在是 6 個，多出的就是第 0 輪的重查。這是修法本身的效果，不是缺陷。

### 2. O1：清倉單部分成交寫進 `fills.json`（`demo_bot.py:599-600`）

用 `test_partial_in_kill_flatten` 重跑：

- 7a3d142c：`fills.json` = `[開倉／調整 FILLED 1, 清倉（部分成交） CANCELED 0.5, 清倉 FILLED 0.5]`，`status.fills=3`，帳本 `['1','0.5','0.5']`，OKX 部位 0，三邊一致。
- 5ca49b93：`fills.json` 少了部分成交那筆，`status.fills=2`。

### 3. O2：部分成交停下的訊息與 CLI 提示（`demo_bot.py:553-561`、`:1066`）

用 `test_recheck_msg.py` 實測三種狀態，訊息依保底停損的實際狀態寫：

- 沒設停損（`--disaster-stop 0`）：「目前部位 0.5，沒有設保底停損；Bot 停下，用同一個指令重開會接續」
- 停損已確認：「目前部位 0.5，保底停損在 94.5；…」
- 停損建立時連線失敗、還沒確認：「保底停損還沒確認，請到 OKX 網頁看條件單；…」

`_hint("order_partially_filled:canceled")` 會回新的提示。`START_HINTS` 沒有其他鍵是它的前綴，不會被別的提示搶先比對到。

### 4. Gemini #3：對帳重查保護單後，第一次出現的告警會寫事件（`demo_bot.py:355-362`）

- 程式：呼叫 `protection_verify` 之前先記下原本的告警，之後告警不是空的而且和原本不同時，才寫一筆 `protection_alert`。
- 不會重複寫：
  - `_protect` 開頭讀到的 `before` 已經是對帳後的告警，只有告警再變一次才會寫。
  - 告警還停在「不確定」時，`_reconcile` 不會再進這個分支，因為進入條件要求 `pending`、`uncertain`、`triggered` 都不成立。
  - `_protect` 結尾呼叫的 `_reconcile`，比對基準是 `_protect` 剛寫過的那個告警。
- 實測：逾時情境的事件序列只出現一次 `protection_alert(protection_unconfirmed)`，5ca49b93 一次都沒有。新增的測試 `test_a_stop_gone_everywhere_is_reported_once_by_the_minute_check` 斷言告警剛好一次、而且沒有重送。

### 5. ReviewFixTests 新增的 3 項

把 7a3d142c 的 `tests/` 放到 5ca49b93 的 `catos/` 上跑，結果 `Ran 8, FAILED (failures=4)`。失敗的是新增的 3 項（D1 延遲、清倉部分成交、告警只寫一次），加上改寫過斷言的部分成交測試（訊息含「保底停損在 94.5」、提示含「接續」）。原有的 4 項照樣通過。所以新測試在修正前真的會失敗，測到的就是這次的修正。

## 實際跑過的指令

全部以 HOME／USERPROFILE 導到 `…\scratchpad\accept-work\r-home*` 執行。

| 指令 | 結果 |
|---|---|
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_demo_bot.py"` | Ran 50, OK |
| `… -p "test_*.py"`（整套後端） | Ran 876 in 265s, OK |
| 7a3d142c 的 `ReviewFixTests` 放到 5ca49b93 的 `catos/` 上跑 | Ran 8, FAILED (failures=4)，見第 5 項 |
| `test_accept_lag`、`test_partial_in_kill_flatten`、`test_history_lookup_timeout`、`HistoryMatchingTests`，對 HEAD 跑 | Ran 9，1 項失敗；失敗的是預期中的請求數斷言 5 改成 6（見第 1 項），其餘符合預期 |
| 同上，對 5ca49b93 跑 | Ran 9, OK（用來比對修正前後的差異） |
| `count_requests.py`（兩個版本） | 見第 1 項的表 |
| `test_recheck_msg.py`（3 項） | Ran 3, OK |

腳本放在 `C:\Users\user\AppData\Local\Temp\claude\09abadd8a3a6a13d\32a2fad0-10db-4ae6-83ab-7019170dec6b\scratchpad\accept-work\`。
