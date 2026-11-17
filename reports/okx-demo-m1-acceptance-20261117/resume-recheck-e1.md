# 接續 run 獨立重驗：E1（Soft 鎖住被接續自動解除）

- 日期：2026-11-17
- 重驗者：沒有參與 E1 修正的另一個會話（Claude Opus 5.5）
- 前一輪報告：`reports/okx-demo-m1-acceptance-20261117/resume-acceptance.md`（E1）

## 重驗對象

`git diff 94f5ffd9..0f3732ec`（commit `0f3732ec fix: 接續 run 只認停下之後的 demo rearm 才解除 Soft（接續驗收 E1）`）：

- `catos/demo_bot.py`：新增 `_iso_ms`（`:106-114`），`_resume` 改寫（`:771-797`）。
- `tests/test_demo_bot.py`：新增 `test_resume_without_a_rearm_keeps_the_ledger_soft_latch`（`:635-669`）。
- 文件（README、`docs/next-steps.md`、模組 docstring）只核對是否和程式一致。

## 方式與限制

- 讀程式：`demo_bot.py` 的 `_observe`、`run`、`_recover`、`_resume`、`rearm_main`、`AccountGuard`；`supervisor.py` 的 `_load`、`latch`、`observe_risk`、`rearm`；`risk.py` 的 `State`、`observe`、`halt`、`rearm`、`expire`；`journal.py` 的 `rearm`、`_audit_risk`。
- 實跑：`tests.test_demo_bot` 全部 30 項；把 `94f5ffd9` 的 `catos/`、`tests/` 用 `git archive` 解到暫存目錄，放進新測試跑舊程式；另寫 9 項補測（暫存目錄 `probe_e1.py`、`probe_flat2.py`），全部用假 OKX、隔離的帳戶資料夾、核准紀錄與 Kill-Switch 檔。
- 補測 B、E 把 `demo_bot._now_text` 改成讀假時鐘，讓 `demo rearm` 的 `at` 和 Bot 的 `wall_ms` 出自同一個時鐘，模擬正式環境（正式環境兩者都讀系統時間）。
- 限制：沒有連 OKX、沒有在模擬盤實測；沒有跑後端整套（另一個程序在跑）；沒有動工作樹（舊程式只在暫存目錄跑），`git status` 乾淨，只新增這份報告。

## 結論

**PASS。** E1 已關閉：沒有停機後的 `demo rearm` 時，接續一律維持帳本的 Soft、不送加倉單，並把帳戶紀錄補回鎖住；真的 rearm 過仍會解除。沒有新的阻斷缺陷。

## 逐項判定

| # | 項目 | 判定 | 依據 | 實跑 |
|---|---|---|---|---|
| 1 | E1 原情境不再自動解除 | 通過 | `demo_bot.py:774` 在 `_recover` 之前記下帳本的 `risk_state.time_ms`；`:783` 只有 `rearms[-1].at` 晚於它才 rearm；否則 `:794-797` 把帳戶紀錄補成 `soft_latched=True` 並記 `soft_latched` 事件 | 補測 A（原報告 R 項的情境，`rearms=[]`）：寫 Soft 失敗、run `failed`、部位 1，權益回升、沒有 rearm 就重開。沒有 `soft_rearmed`；帳本 `risk_actions` 只有 `manual_kill`，沒有 `rearm`；送出的單只有 `buy`、`sell(reduceOnly)`，反手的開倉腿沒送；帳戶紀錄 `soft_latched=True`，`soft_reason` 是「接續時從帳本補回」 |
| 2 | 合法路徑仍會解除 | 通過 | `rearm_main`（`:990`）只處理 `soft_latched=True` 的帳戶，`:1003` 用 `_now_text()` 記 `at`；接續時 `:783` 比對成立後呼叫 `supervisor.rearm` | 既有 `test_resume_follows_a_soft_rearm_made_while_stopped` 通過。補測 B（同一個時鐘）：E1 之後第一次接續把帳戶紀錄補回鎖住並停下（部位 1），再以隔離路徑執行 `rearm_main`，第三次接續出現 `soft_rearmed`，帳本記 `('rearm','cli','demo-rearm-0')`，反手兩腿都送出 |
| 3a | 單位、時區 | 通過 | `_wall_ms`（`:117-118`）是 `time.time_ns()//1e6`，UTC epoch 毫秒；`_now_text`（`:102-103`）是 `datetime.now(timezone.utc).isoformat()`；`_iso_ms` 用 `fromisoformat(...).timestamp()*1000`，帶時區才算，兩邊單位與時區一致 | 補測 D2：`at = time_ms + 1ms` 與 `Z` 結尾都判為「之後」，會 rearm |
| 3b | 解析失敗、相等都偏向鎖住 | 通過 | `_iso_ms` 對 `TypeError`／`ValueError` 與不帶時區都回 -1（`:108-113`）；`:783` 用嚴格的 `>`，`time_ms ≥ 0`，所以 -1 永遠不會成立 | 補測 D：不帶時區的 2099 年、`"yesterday"`、沒有 `at`、數字 `at`、和 `time_ms` 同一毫秒，五種都不 rearm，開倉腿沒送 |
| 3c | 停下之前的 rearm 會不會被當成之後 | 通過（正式環境同一時鐘、時鐘不倒退時） | 帳戶的 rearm 只能由 `rearm_main` 寫入，它要拿到 `.lock`（`:980`），Bot 從 `guard.acquire()` 到 `_close` 都持有同一把鎖，所以 rearm 只會發生在 run 與 run 之間。帳本的 `time_ms` 只會往前：`risk.observe` 拒絕倒退的時間（`risk.py:511`），`expire` 也是（`:558`），`halt`／`latch` 不改時間（`risk.py:480-489`）；帶 `soft_loss` 的狀態寫進帳本時，`time_ms` 就是穿越那次觀測的時間或更晚。所以停下的 run 最後寫入的 `time_ms` 晚於它啟動前的任何 rearm。同一 run 內「解除後又鎖住」：接續時的解除只寫帳本，不新增帳戶 rearm，之後的觀測時間都晚於那筆 rearm。前一個 run 的 rearm：早於這個 run 的任何觀測。`_recover` 期間補餵 K 線或 `dispatch` 可能推進 `time_ms`，但 `:774` 在 `_recover` 之前就讀好，不受影響；`supervisor.start()` 的 `_load` 只做 `risk.halt`，不改 `time_ms` | 補測 E（同一時鐘）：run1 正常鎖 Soft，停下後 rearm；run2 接續時解除，之後再虧 6% 且寫帳戶失敗，run2 `failed`、部位 1。此時帳本 `time_ms=1794802037000`（04:07:17Z），最後一筆 rearm 是 04:06:16Z。權益回升後 run3 接續：沒有第二次 `soft_rearmed`，帳本的 `rearm` 仍只有 run2 那一筆，只送出平倉腿，帳戶紀錄補回鎖住。新測試也覆蓋「停下前的 rearm（2026-11-16T01:00Z）不算」 |
| 4 | 補回帳戶紀錄時 `guard.save` 又失敗 | 通過（fail-closed） | `:796` 的 `OSError` 往上丟出 `_resume`，`run()` 的 `except Exception`（`:579-580`）記成 `failed`。這時已過 `_recover`，不會送任何單；帳本的 Soft 沒動。下次啟動仍走同一分支 | 補測 C：所有 `save` 都失敗時，run2 `failed`（`OSError: still full`），沒有新的單（只有 run1 的 `buy`），帳本 reasons 仍是 `['soft_loss']`、沒有 `rearm`。磁碟恢復後 run3 接續，補回鎖住，只送平倉腿 |
| 5 | 新測試修正前失敗、修正後通過 | 通過 | — | 舊程式（`94f5ffd9`，暫存目錄）：`FAIL`，`'soft_rearmed' unexpectedly found`。修正後：`tests.test_demo_bot` 30 項 `OK` |
| 6 | 文件和程式一致 | 通過 | 模組 docstring（`:38-41`）、README `:156` 最後一句、`docs/next-steps.md:56` 都寫「只認停下之後的 rearm，沒有就維持鎖住」；docstring 也改正了前一輪 F7 的「Resuming itself sends nothing」 | — |

## 新缺陷

無。

## 觀察（不阻斷）

- **O1　帶 0 部位時寫 Soft 失敗，重開是新 run，Soft 一樣會不見。** 這次的修正只涵蓋接續。Soft 在空倉時穿越（例如反手兩腿之間）而寫帳戶紀錄失敗時，run `failed`、部位 0，重開走的是新 run 與新帳本，帳戶紀錄沒有鎖住，Soft 就沒了。補測 `probe_flat2`：`lose_after_fill=2` 讓平倉腿之後虧 6%，寫入失敗，run1 `failed`、部位 0、帳戶 `soft_latched=False`；權益回升後 run2 沒有任何 `soft_latched` 事件（這段 K 線剛好沒有新訊號，所以沒有加倉單）。這條路徑在 `94f5ffd9` 之前就存在，程式碼也沒被這次修改碰到，前一輪報告已提到「修改前碰到同樣的寫入失敗也會失去 Soft」。觸發要同時「空倉時穿越」與「寫檔失敗」，發生率比 E1 更低。真要補，可以在 `_observe`（`:370-374`）寫帳戶失敗時先寫入共用的總開關，或讓新 run 啟動時讀上一個 run 帳本的 reasons。
- **O2　系統時鐘大幅倒退時可能誤判。** 比對假設 rearm 的 `at` 和帳本的 `time_ms` 出自同一個不倒退的時鐘。如果使用者 rearm 之後系統時鐘被往回調，而且調回的幅度超過「rearm 到下一次 Soft 穿越」的間隔，下一次 E1 情境下舊的 rearm 會被當成停下之後的。要同時碰到時鐘倒退與寫檔失敗，實際上不太可能，只記錄。另外，`risk.observe` 遇到時間倒退會直接讓 run 停下（補測 B 第一版不小心倒退時鐘，得到 `ProtocolError: risk observation must follow sequence and time`），所以 run 進行中的倒退不會被默默吃掉。
- **O3　帳戶紀錄的 `rearms` 有非 dict 項目時，接續會當掉。** `:783` 的 `rearms[-1].get("at")` 在項目是字串時拋 `AttributeError`，run `failed`，沒有送單（補測 D3）。方向是 fail-closed，只有手動改檔才會發生；`AccountGuard.load`（`:208-228`）沒有驗證 `rearms` 的結構。
- **O4　接續時 rearm 被拒絕，使用者那次 rearm 就用掉了。** 例如 `mgnRatio` 沒回造成 `DEGRADED`，接續時 `supervisor.rearm` 被拒（前一輪 F8）。那個 run 之後的觀測時間都會晚於這筆 rearm，下次接續就判為「停下前的 rearm」，維持鎖住並補回帳戶紀錄，使用者要再做一次 `demo rearm`。方向正確，只是終端機訊息沒說要再 rearm 一次。
- **O5　既有測試會隨機失敗（不在這次修改範圍）。** `test_same_day_restart_keeps_the_basis_and_the_soft_latch`（`tests/test_demo_bot.py:344`）斷言帳戶紀錄裡沒有 `"u1"`。但 `94f5ffd9` 起帳戶紀錄多了 `run.dir`，裡面含隨機的暫存目錄名稱。本次跑補測時剛好遇到 `tmpmiv0cu1b`，這項就失敗了，每次約 0.5% 機率。建議改成只檢查 uid 欄位，或比對 `"u1"` 以外不會撞到的 uid。

## 實際跑過的指令與輸出摘要

```
# 修正後
.venv/Scripts/python.exe -m unittest tests.test_demo_bot
Ran 30 tests in 33.331s
OK

# 舊程式（git archive 94f5ffd9 catos tests 到暫存目錄，放入新測試）
python -m unittest tests.test_demo_bot.DemoBotTests.test_resume_without_a_rearm_keeps_the_ledger_soft_latch \
                   tests.test_demo_bot.DemoBotTests.test_resume_follows_a_soft_rearm_made_while_stopped
FAIL: test_resume_without_a_rearm_keeps_the_ledger_soft_latch
AssertionError: 'soft_rearmed' unexpectedly found in [... 'risk', 'soft_rearmed', 'bar', 'started', ...]
Ran 2 tests  FAILED (failures=1)       # 合法路徑那項在舊程式也通過

# 補測（PYTHONPATH=工作樹，暫存目錄 probe_e1.py）
python -m unittest probe_e1.Probe.test_A_... test_B_... test_C_... test_D_... test_D2_... test_D3_... test_E_...
Ran 7 tests  OK
A posts [('buy', False), ('sell', True)]  risk_actions [('manual_kill', ...)]  account soft_latched=True, rearms=[]
B run2 stopped operator_stop_file 1 → rearm_main → run3 posts [buy, sell(RO), sell, buy(RO)]  risk_actions [('rearm','cli','demo-rearm-0'), ('manual_kill', ...)]
C status failed OSError: still full, posts [('buy', False)], ledger reasons ['soft_loss'], no rearm；run3 補回鎖住，只送平倉腿
D naive_future / garbage / missing_at / number_at / equal_ms：rearmed=False，沒送開倉腿
D2 plus1 / z_suffix：rearmed=True
D3 string entry：failed AttributeError，posts 1
E 帳本 time_ms 1794802037000（04:07:17Z）> 最後 rearm 04:06:16Z；run3 posts [('buy', False), ('sell', True)]，rearm 只有一筆

# 空倉變體（probe_flat2.py）
run1 failed OSError: disk full pos 0 posts [buy, sell(RO)] acct soft False
run2 stopped manual_kill  soft events 0  new posts []

git status --short   # 只有這份報告是新增的
```
