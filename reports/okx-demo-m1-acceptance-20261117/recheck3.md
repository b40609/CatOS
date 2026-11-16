# M1（OKX 模擬盤）第三輪修正後重驗

- 對象：`d6e48764`（分支 `feat/okx-demo-m1`），只驗第二輪之後改動的範圍：`catos/demo_bot.py`、`catos/okx_demo.py`、`tests/test_demo_bot.py`、README「OKX 模擬盤」、AGENTS.md 紅線、`docs/next-steps.md`。
- 前兩輪：`acceptance.md`（FAIL，D1–D4）、`recheck.md`（PASS 有觀察，N1、N2、R1–R10）。
- 驗收者：沒有參與修正的另一個會話（Claude Opus 5.5），2026-11-17。
- 方式：讀 `git show d6e48764` 與現行原始碼，用自寫的假 OKX 情境重現（`probe_regress.py` 21 項、`probe_d2g.py` 1 項、`probe_r3.py` 24 項），再跑既有測試。沒有拿開發者的測試當證據。
- 隔離：全程沒有連網，沒有呼叫 OKX，沒有打開任何金鑰檔，也沒有執行 `demo status`、`first-order`、`bot`。`demo_bot.ACCOUNTS_DIRECTORY` 與 `account_lock.LOCK_DIRECTORY` 都替換成臨時資料夾，每個情境開始前都斷言 `accounts_directory()` 落在臨時資料夾裡。`CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH`、`CATOS_OKX_DEMO_CREDENTIALS` 都指向臨時檔或不存在的路徑。CLI 情境另外替換了 `connect` 與 `credentials_path`。真實的 `~/.catos/okx-demo-accounts` 在驗收前後都不存在（`probe_r3` 的 Z 項與每次測試後的 `ls` 都確認過）。
- 夾具：測試用的核准與 Kill-Switch 紀錄，只用函式寫在臨時檔裡。迴歸項 D2b 沿用第二輪的寫法，在臨時檔上以 actor `cli` 呼叫 `kill_switch.clear`；新寫的 `probe_r3` 改成換一個新的臨時檔，完全不呼叫 clear。沒有執行 CLI 的 approve、revoke、`kill clear`，也沒有對正式路徑執行 `demo rearm`。

## 結論：PASS（有觀察）

N1、N2 都修好了，第 3～6 項也都照描述運作。D1–D4 沒有回歸。`run()` 重構後，我試了 12 種啟動失敗、取消與 Ctrl+C，帳戶鎖全部都有釋放。

沒有新的缺陷。有 7 項觀察（O1–O7），都屬低嚴重度：只在同一程序內連續跑多個 Bot 時才有影響，或者是失敗時傾向拒絕的 fail-closed 行為。CLI 每次執行都是獨立程序，所以不受影響。

## N1：帳戶檔被刪除時不再當成首次建立，已修好

實作位置：
- `catos/demo_bot.py:146`：取鎖前先記下鎖檔原本存不存在（`fresh`）。
- `:166-167`：鎖檔原本就存在、狀態檔卻不見時，以 `account_state_missing` 拒絕，並先釋放鎖。
- `:168`：全新帳戶在取得鎖後，先寫一份 `day=None`、`basis=None` 的初始狀態。
- `:181-182`：`load` 只在 `day` 是 None 時，才接受 `basis` 也是 None。

| 情境 | 結果 |
| --- | --- |
| 全新帳戶（兩個檔都不存在） | 取鎖後出現 `.json` 與 `.lock`，初始狀態是 `day=None`、`basis=None`、`soft_latched=False`。Bot 照常執行，之後狀態檔變成 `day=20773`、基準 5000，POST 1 筆 |
| 只刪狀態檔（run1 已觸發 Soft 並停下，同一天） | `account_state_missing`，沒有建立 run 資料夾，POST 0 筆。隔天再啟動仍然拒絕。拒絕後鎖已釋放（再取一次得到的也是 `account_state_missing`，不是 `account_busy`） |
| 只刪鎖檔 | 照常啟動，基準沿用 5000，Soft 仍鎖住，POST 0 筆 |
| 兩個都刪 | 當成新帳戶：基準 4699.999475（虧損後的值），Soft 消失，照常買進。README 第 157 行寫明這是使用者本人才能做的決定，AGENTS.md 第 55 行也禁止代理刪除 |
| 第一次 run 在寫入基準前失敗：預熱 K 線少一根（`warmup_history_incomplete`），或 K 線端點一直回 503（`okx_read_failed`） | 狀態檔維持 `(None, None)`。同一天重啟正常，以當下第一次觀測建立基準 5000，並下單 |
| 子程序在 `acquire` 建好鎖檔之後、寫入初始狀態之前被殺掉（以 `os._exit(9)` 模擬） | 只剩 `.lock`。重啟時得到 `account_state_missing`；使用者刪掉 `.lock` 之後正常執行 |
| 同一程序內寫入初始狀態失敗（`save` 拋出 OSError） | OSError 從 `run()` 拋出。GC 回收前鎖沒有放（`account_busy`），回收後變成 `account_state_missing`。見 O1 |
| `load` 的形狀檢查 | 以下三種都判 `account_state_unreadable`：`day=None` 但有 `basis`、有 `day` 但 `basis=None`、`day` 是字串。`day=None` 且 `soft_latched=True` 會被接受，不過程式本身不會產生這種狀態 |

**判斷：首次 run 在寫入初始狀態前崩潰時，帳戶會不會永久卡在 `account_state_missing`？可以接受嗎？**

- 會卡住，但不是永久。使用者刪掉 `.lock` 就能恢復。這時本來就沒有狀態檔，所以「連同 `.lock` 一起刪」也就是只刪 `.lock`，正好符合 README 第 157 行的說明。
- 會進入這個窗口的情況只有兩種：程序在第一次 `acquire` 開鎖檔到寫完初始狀態之間被殺掉，或寫入時磁碟出錯。一般的重啟、Ctrl+C、啟動失敗都不會走到這裡（見下面的例外路徑表）。
- 方向是 fail-closed：不會建出不該有的基準，也不會解除鎖存。代價只是多一次人工處理，而且這時帳戶還沒有任何基準，刪檔不會失去什麼。我判定可以接受。
- 小缺點：CLI 只會印出「沒有啟動：account_state_missing:<檔名>」，沒有提示怎麼處理（O6）。

## N2：帳戶檔與鎖改放固定位置，已修好

- 實作位置：`catos/demo_bot.py:74-79` 的 `accounts_directory()`；`:221` 的 `DemoBot(accounts_dir=None)` 預設也用它；`cli_main` 不再傳入跟 output root 有關的路徑（`:672`）。
- 用 grep 查過 `catos/`、`tools/`、`tests/`、前端與文件（`docs/archive` 除外）：已經沒有任何地方使用 `output_dir.parent / "accounts"`。本工作樹裡也沒有舊的 `outputs/okx-demo-bot/accounts`。

| 情境 | 結果 |
| --- | --- |
| 預設路徑 | 常數是 None 時，`accounts_directory()` 等於 `~/.catos/okx-demo-accounts`（只計算路徑，沒有建立或讀取）。`accounts_dir` 參數有效 |
| run1 在 root 底下觸發 Soft；同一天分別在 rootB、rootC 重啟 | 兩次都沿用基準 5000、Soft 仍鎖住、POST 0 筆。帳戶檔只有 1 份，任何 output root 底下都沒有多出 `accounts` 資料夾 |
| 兩個 Bot 同時執行：Bot A（rootA）持有 1 張時，在另一個執行緒啟動 Bot B（rootB，同一個 uid） | B 得到 `account_busy`，沒有建立 run 資料夾，POST 0 筆；A 照常跑完 |
| 迴歸 D2e：用兩個 output root 各建一個 `AccountGuard` | 第二個得到 `account_busy`（第二輪時兩邊都能取得） |

## 第 3 項：`run()` 重構（`_open_run`、`_main_loop`），已修好（有觀察）

程式結構：
- `catos/demo_bot.py:501-514`：取鎖之後的讀檔、`_account`、檢查與 `mkdir`，都包在 `except BaseException: release`。
- `:515-520`：`_open_run` 失敗時，釋放鎖並把 `self.guard` 設回 None。
- `:521-534`：主體在 `try/finally: _close()` 裡。

| 失敗點 | 拋出／回傳 | 鎖 | 其他 |
| --- | --- | --- | --- |
| `account/config` 回 503（取鎖前） | DemoError | 已釋放 | 沒有 run 資料夾 |
| `account_issues` 不合格 | BotStopped | 已釋放 | 沒有 run 資料夾 |
| `instruments` 回 503 | DemoError | 已釋放 | 沒有 run 資料夾 |
| uid 是空的 | BotStopped `account_uid_missing` | 已釋放 | 沒有 run 資料夾 |
| 取鎖後 `positions` 回 503 | DemoError | 已釋放 | 沒有 run 資料夾 |
| run 資料夾已經存在 | FileExistsError | 已釋放 | — |
| `_Log` 建構失敗 | OSError | 已釋放 | — |
| 寫 manifest 失敗 | OSError | 已釋放 | **log 把手沒關**（O2） |
| `OkxDemoExchange` 建構失敗 | RuntimeError | 已釋放 | log 把手沒關；留下 `events.jsonl` 與 `manifest.json`，沒有 `status.json`（O2） |
| `LocalSupervisor` 建構失敗 | RuntimeError | 已釋放 | 同上（O2）。第二輪的 R6 已修好 |
| `supervisor.start()` 失敗 | 回傳 `failed` | 已釋放 | log 已關，status、fills 都有寫 |
| `_close` 裡的 `supervisor.close()` 拋出 | RuntimeError | **沒有釋放** | log 沒關，也沒寫 `status.json`（O3） |
| 取鎖後、`_account` 執行中被取消（CancelledError） | CancelledError | 已釋放 | 沒有 run 資料夾 |
| 同一位置收到真實的 SIGINT（`signal.raise_signal`，由 asyncio.run 轉成取消） | KeyboardInterrupt | 已釋放 | 沒有 run 資料夾 |
| 主迴圈中被取消（持有 1 張） | CancelledError | 已釋放 | log 已關；最後一筆事件是 `stopped`；OKX 部位 1（照設計不平倉）；`status.json` 的 state 仍是 `running`（O4） |
| 主迴圈中收到真實的 SIGINT | KeyboardInterrupt | 已釋放 | 同上（O4） |
| 主迴圈中直接 raise KeyboardInterrupt | KeyboardInterrupt | 已釋放 | log 已關 |

## 第 4 項：`demo rearm`，已修好

- 修正後的順序：`catos/demo_bot.py:708-709` 的 `for_file` 只讀 uid，然後取鎖；`:715` 在持有鎖的情況下才 `load`。第二輪 R5 指出的覆寫窗口已經消除。參數改成隱藏的 `--accounts-dir`（`:699`）。

| 情境 | 結果 |
| --- | --- |
| Bot 執行中（在 Bot 的 sleep 回呼裡同步呼叫 rearm） | rc=1，`account_busy`，檔案仍是 `soft_latched=true` |
| 沒有互動式終端機（真的 `terminal_confirm`，stdin 不是 tty） | rc=1，`interactive_terminal_required`；檔案沒變；鎖已釋放 |
| 狀態檔截斷成 `{` | rc=1，`account_state_unreadable`（在 `for_file` 就被擋下）；鎖未被占用 |
| uid 正確但 `day` 是字串 | rc=1，`account_state_unreadable`（持有鎖時的 `load` 擋下）；鎖已釋放 |
| 另一個子程序持有鎖 | rc=1，`account_busy`；檔案沒變 |
| 另一個帳戶的檔案損壞，而且排在前面 | rc=1，鎖住的那個帳戶沒有解除（第二輪 R5 後半，維持原樣，見 O5） |
| 輸入錯誤的確認字 | rc=1，「沒有解除。」 |
| 鎖檔不見、狀態檔還在 | rc=0，「已解除 Soft 鎖住。」 |
| 全新帳戶（`day=None`）；也從 `okx_demo.cli_main(["rearm", ...])` 分派進來 | rc=0，「沒有被 Soft 鎖住的模擬盤帳戶。」 |

## 第 5 項：CLI 結束碼與 DemoError，已修好

以 `demo_bot.cli_main` 實跑，`connect` 換成假 OKX 用戶端，Bot 換成假時鐘。

| 情境 | 結束碼與輸出 |
| --- | --- |
| Kill 後 balance 一直回 503（`flatten_failed`） | **2**；有印出「手動平倉」提示；OKX 部位 1 |
| 用 stop.request 停止 | 0 |
| 主迴圈例外（`failed`） | 1 |
| 取鎖前 `account/config` 回 DemoError | 1；stderr「沒有啟動：OKX 回應不是 JSON（HTTP 503）」，沒有 traceback |
| 取鎖後 `positions` 回 DemoError | 1；同樣的訊息；鎖已釋放 |
| `account_state_missing` | 1；「沒有啟動：account_state_missing:<檔名>」 |
| 主迴圈中收到真實的 SIGINT | 1；「已收到 Ctrl+C；部位留在模擬盤上」；鎖已釋放 |
| 啟動時發生其他型別的例外（例如 `LocalSupervisor` 拋出 RuntimeError） | 沒有被接住，會印出 traceback；鎖已釋放（O7） |

## 第 6 項：`first-order --inst`，已修好

- `catos/okx_demo.py:655` 改成 `choices=[DEFAULT_INST]`。執行 `okx_demo.cli_main(["first-order", "--inst", "ETH-USDT-SWAP"])` 時，結束碼 2，訊息是 `invalid choice: 'ETH-USDT-SWAP'`。`connect` 被換成「呼叫就失敗」，結果沒有被呼叫到。`demo status --inst` 仍然接受其他合約，但它只讀不寫，不在這次範圍內。

## 第 7 項：文件，已核對

- README 第 157–160 行：帳戶紀錄的位置、紀錄不見或損壞時拒絕啟動、要重來就連同 `.lock` 一起刪、`demo rearm`、結束碼 2，都和程式一致。
- AGENTS.md 第 55 行新增一條紅線：代理不得執行 `demo rearm`，也不得編輯或刪除 `~/.catos/okx-demo-accounts/`。檔頭第 3 行補上了 2026-11-17 的 INVARIANTS 改寫紀錄，第二輪 R8 的後半已處理。不過 INVARIANTS 的改寫仍然寫著「代理決定、可推翻」，還沒有使用者定案，這點維持 R8 前半。
- `docs/next-steps.md`：65 行，大約一頁；D2 的描述和現行程式一致。

## D1–D4 迴歸

`probe_regress.py`：第二輪的 21 項，改成替換 `ACCOUNTS_DIRECTORY`，`rearm` 改用 `--accounts-dir`。另外加跑 `probe_d2g.py`。

| 項目 | 結果 |
| --- | --- |
| D1a–D1f（清倉途中讀取失敗、POST 回應遺失、POST 回 503） | 和第二輪相同：a、b、d、e 部位都清到 0；c 重試 134 秒後 `flatten_failed:okx_read_failed`，POST 只有 1 筆；f 是 `flatten_failed:order_not_settled:UNKNOWN`，POST 2 次，沒有重送 |
| D2a 同日／跨日重啟、rearm | 同日沿用基準 5000，POST 0 筆；跨日新基準 4699.999475，Soft 仍鎖住，POST 0 筆；rearm rc=0 之後照常買進 |
| D2b Hard 後重啟 | 同日與隔日都是 `kill_switch_engaged`；`demo-bot` 自己解除會被拒（`kill_switch_actor_invalid`）；使用者解除後（臨時檔），同日重啟仍判 Hard，POST 0 筆 |
| D2c 帳戶檔損壞 8 種 | 全部 `account_state_unreadable`，沒有 run 資料夾，POST 0 筆，鎖已釋放 |
| D2d 刪除帳戶檔 | 改成 `account_state_missing`（第二輪會重建基準）。這就是 N1 的修正 |
| D2e 換 output root | 改成沿用基準 5000、POST 0 筆，鎖互斥（第二輪會重設）。這就是 N2 的修正 |
| D2f／D2g 寫入 Kill 失敗 | 和第二輪相同，Soft 鎖存是退路：隔天重啟時沒有 Kill 紀錄，基準 4399.998950，POST 0 筆 |
| D3a–D3c 其他合約 | 和第二輪相同 |
| D4a–D4c 跨程序鎖、例外路徑釋放、rearm 被擋 | 跨程序互斥；四種例外路徑鎖都已釋放，其中 `LocalSupervisor` 建構失敗那條在第二輪會漏，現在已修好；rearm rc=1 |
| 其他（Kill 時正在等 K 線、`feeCcy` 是 BTC、`demo-bot` actor、請求鎖、數值精度） | 和第二輪相同 |

## 新缺陷

無。

## 觀察（低嚴重度，不影響判定）

- **O1** 位置：`catos/demo_bot.py:163-168`、`:502`。`acquire` 在設好 `self._handle` 之後才寫初始狀態；寫入時如果拋出例外，把手不會關閉，而 `run()` 第 502 行的 `guard.acquire()` 又在 try 外面。所以同一程序內，鎖要等 GC 回收才會放掉。之後帳戶會停在 `account_state_missing`，要刪掉 `.lock` 才能恢復（見 N1 的判斷）。CLI 會印出 OSError 的 traceback。建議：寫入失敗時先 `release()` 再拋出。
- **O2** 位置：`catos/demo_bot.py:515-520`、`:539`。`_open_run` 失敗時只釋放鎖，沒有關閉已經開啟的 `events.jsonl` 把手。run 資料夾會留下空的 `events.jsonl`（有時還有 `manifest.json`），但沒有 `status.json`。在 Windows 上，把手沒關之前，這個資料夾刪不掉。CLI 的程序結束後就會釋放。建議：在 except 裡關閉 `self.log`。
- **O3** 位置：`catos/demo_bot.py:625-641`。`_close` 裡的 `supervisor.close()` 如果拋出例外，後面的 `finished_at`、status 與 fills 的寫入、`guard.release()`、log 的關閉都不會執行。我是用 mock 讓 `close` 拋出例外來重現的；實際上 `close` 本身有 try/finally，會拋出的情況不多。建議：在 `_close` 裡用 try/finally 包住 `guard.release()` 與 log 的關閉。
- **O4**：Ctrl+C 或取消時，`status.json` 的 `state` 仍是 `running`（有 `finished_at`，`stop_reason` 是 None），events 的最後一筆是「Bot 停止：running（None）」。原因是 `run()` 的 except 只接 `BotStopped` 與 `Exception`。這是 `888e9f36` 就有的行為，不是這次重構造成的。之後如果介面要讀 `status.json`，會看成還在執行。
- **O5**（沿用第二輪 R5 後半）：`demo rearm` 遇到任何一個帳戶檔損壞，就直接回 1，排在後面、被 Soft 鎖住的帳戶也無法解除。只有一個帳戶時沒有影響。
- **O6**：`account_state_missing` 和 `account_state_unreadable` 在 CLI 只顯示原因代碼，沒有提示處理方式（例如「見 README：由你本人刪除 .json 與 .lock」）。
- **O7**（沿用第二輪 R2 的範圍）：`cli_main` 只接住 `BotStopped`、`KillSwitchError`、`DemoError` 與 KeyboardInterrupt。啟動階段的其他例外（FileExistsError、O1 的 OSError、`_open_run` 的例外）仍會印出 traceback。這些情況下鎖都已釋放，也還沒有下單。

## 實際跑的測試

環境：`CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH` 都指向 scratchpad 的臨時檔，`CATOS_OKX_DEMO_CREDENTIALS` 指向不存在的路徑。

| 指令 | 結果 |
| --- | --- |
| `.venv/Scripts/python.exe -m unittest tests.test_demo_bot tests.test_okx_demo -v` | `Ran 43 tests in 11.724s` / `OK` |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_kill_switch*.py"` | `Ran 26 tests in 9.164s` / `OK` |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"` | `Ran 994 tests in 156.372s` / `OK (skipped=11)` |
| 自寫 `probe_regress.py`（第二輪的 21 項迴歸） | `Ran 21 tests in 21.628s` / `OK` |
| 自寫 `probe_d2g.py`（會連帶重跑上面 21 項） | `Ran 22 tests in 23.766s` / `OK` |
| 自寫 `probe_r3.py`（N1 8 項、N2 3 項、例外路徑 6 組、rearm 4 組、CLI 2 組、真實目錄檢查 1 項） | `Ran 24 tests in 19.919s` / `OK` |

沒跑的：
- 前端的 typecheck、test、build 與整合測試：這次的改動沒有碰前端。
- 連 OKX 模擬盤實測：紅線不允許。

測試前後，`git status` 都是乾淨的。補測腳本與輸出都在 `C:\Users\user\AppData\Local\Temp\claude\06a2d6733c105b8e\e959d5a4-c8a1-4a67-830d-e90e8ab84b74\scratchpad\recheck3\`（`probe_regress.py`、`probe_d2g.py`、`probe_r3.py`、`regress.log`、`r3.log`、`t1.log`、`t2.log`、`full.log`）。scratchpad 可能會被清掉，所以重現步驟也寫在上面各節裡了。
