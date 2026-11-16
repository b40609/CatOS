# M1（OKX 模擬盤）修正後重驗

- 對象：`888e9f36` 之上尚未 commit 的工作區修正（`git diff`：`catos/demo_bot.py`、`catos/kill_switch.py`、`catos/okx_demo.py`、`catos/okx_demo_exchange.py`、前端兩個檔、`tests/test_demo_bot.py`、README、AGENTS.md）
- 上一輪：`reports/okx-demo-m1-acceptance-20261117/acceptance.md`（FAIL：D1、D2；另有 D3、D4 與 O1–O14）
- 驗收者：沒有參與修正的另一個會話（Claude Opus 5.5），2026-11-17。只驗受影響的範圍。
- 方式：讀 diff 與修正後的原始碼，自己寫假 OKX 情境重現（`probe_recheck.py` 22 項，沒有用開發者的測試當證據），再跑既有測試。全程沒有連網，沒有呼叫 OKX，沒有讀金鑰檔，沒有碰 `scratchpad\smoke2\` 與 `outputs/okx-demo-bot`。也沒有執行 approve、revoke、`kill clear`、`demo rearm`（正式路徑）。`CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH` 都指向臨時檔，`CATOS_OKX_DEMO_CREDENTIALS` 指向不存在的路徑，輸出資料夾也用臨時資料夾。

## 結論：PASS（有觀察）

D1–D4 都修好了，用自己的情境重現後，結果都是預期行為。上一輪 PASS 的各項（UNKNOWN 不重送、分批成交、51016、5 秒逾時、補處理 K 線不下單）重跑後仍通過。

另有兩個低嚴重度的殘留缺口（N1、N2）：都要使用者自己動手（刪掉帳戶檔，或指定別的 `--output-root`）才會發生。R1「曾建立……卻遺失時不得當作首次建立」在這兩種情況下不成立。這兩項不擋模擬盤，但接 Live 前要補，或者由使用者明確接受。

## D1–D4 判定

### D1 清倉途中讀取失敗：已修好

- 修法：`catos/demo_bot.py:243-256` 的 `_call` 只包讀取，遇到 `DemoError` 就退避重試，間隔 2、4、8 秒，之後都是 15 秒。一般讀取試 4 次，清倉時試 12 次（`:69-70`，用在 `:400`、`:413`）。`_flatten`（`:388-396`）接到 `BotStopped` 時，會記一筆 `flatten_failed` 事件，並在終端機提示「到 OKX 網頁手動平倉」。
- `_call` 包的是 `_account`、`closed_candles`（`:378`、`:400`、`:413`、`:437`、`:462`、`:522`、`:564`），全部都是讀取。下單、查詢委託和結清仍照舊走 Supervisor，沒有被包進重試，所以不會重複送單或重複結清。

| 情境（自寫的假 OKX） | 結果 |
| --- | --- |
| 持有 1 張時觸發 Kill；清倉第一次讀 `/account/balance` 回 HTML 503 一次 | `stopped`／`manual_kill`；OKX 部位 0；POST 2 筆（買、只減倉的賣）；`read_retry` 1 次 |
| Kill；`/account/positions` 連續回 11 次 503 | 部位 0；POST 2 筆；`read_retry` 11 次 |
| Kill 加上 Hard；清倉時 balance 連續回 3 次 503 | `risk_flat:hard_loss,soft_loss`；部位 0 |
| Kill；之後 balance 一直回 503 | 重試了 134 秒（模擬時間）後停下：`flatten_failed:okx_read_failed:DemoError`；有一筆 `flatten_failed` 事件；OKX 部位 1；POST 只有原本的買單 1 筆 |
| Kill；清倉單 POST 已成交但回應遺失 | 先記成 UNKNOWN，查詢後結清，部位 0；POST 共 2 次（沒有重送） |
| Kill；清倉單 POST 回 503，OKX 沒收到 | `flatten_failed:order_not_settled:UNKNOWN:…`；部位 1；POST 共 2 次。依「UNKNOWN 不盲重送」停下並提示手動平倉，屬設計上的行為（見觀察 R3） |

### D2 重啟繞過 Soft／Hard：已修好（殘留 N1、N2）

- 修法：`AccountGuard`（`catos/demo_bot.py:118-196`）把當日基準和 Soft 鎖存寫進 `<output_root>/accounts/<uid digest>.json`。`_observe`（`:280-303`）在同一個台北日沿用存檔的基準，換日時才建新的，而且先寫檔再用。Soft 觸發時寫入 `soft_latched`（`:313-317`），新的 run 啟動時重新 latch（`:517-520`）。Hard 時以 actor `demo-bot` 寫入共用的 Kill-Switch（`:318-327`）。`kill_switch.clear` 只接受 `http`／`cli`（`catos/kill_switch.py:48-50`、`:302-303`）。

| 情境 | 結果 | 判定 |
| --- | --- | --- |
| 同日重啟（Soft 已鎖）：run1 買進後虧 6%，觸發 Soft，用 stop.request 停止；部位手動平掉，同一天再啟動 | 基準 `["5000"]`，沿用 run1 的值，不是虧損後的權益；第一根 `REJECTED/increase_gate_closed`；POST 0 筆 | R1「同日既存基準不得因重啟替換」成立；Soft 跨重啟 |
| 跨日重啟（Soft 已鎖）：隔天台北日 | 新基準 4699.999475（隔天的第一次觀測）；帳戶檔 `day=20774`、`soft_latched=true`；第一根仍是 `increase_gate_closed`；POST 0 筆 | 「跨日不自動解除」成立 |
| 跨日後用 `rearm_main` 解除（以 lambda 模擬互動確認，路徑是臨時資料夾） | rc=0，下一個 run 照常買進 | 人工恢復可用 |
| Hard 後重啟：run1 虧 12%，清倉到 0，Kill 由 `demo-bot` 觸發；同日與隔日各重啟一次 | 兩次都是 `KillSwitchError:kill_switch_engaged`，沒有建立 run 資料夾 | Hard 鎖存跨重啟、跨日 |
| Hard 後由使用者解除（臨時檔，actor `cli`），同一天再啟動 | 基準沿用 5000；第一根就判 `risk_flat:hard_loss`；POST 0 筆；Kill 再次由 `demo-bot` 觸發 | 正確；`demo-bot` 自己去解除會被拒（`kill_switch_actor_invalid`） |
| 寫入 Kill-Switch 失敗（`engage` 拋出 OSError） | 有 `hard_kill_switch_failed` 事件，清倉照常，部位 0。同日重啟會再判 Hard，POST 0 筆，並補寫 Kill。只在隔天重啟時：Kill 沒有紀錄，但 Soft 鎖存還在，所以 POST 0 筆 | 安全：Hard 必定帶著 Soft，Soft 鎖存就是退路 |
| 帳戶檔損壞，8 種：`{`、空檔、缺 `day`、`soft_latched` 是字串、權益 0、權益 NaN、uid digest 不符、`[]` | 全部 `account_state_unreadable`；沒有建立 run 資料夾；POST 0 筆；拒絕後鎖已釋放 | R1「損壞時不得當作首次建立」成立 |
| 帳戶檔被刪除（Soft 已鎖、虧損 6%）後同日重啟 | 基準變成 4699.999475（虧損後的值）；Soft 消失；照常買進 | **R1「遺失時不得當作首次建立」不成立**，見 N1 |
| 同一天換一個 `--output-root` 重啟 | 情況同上：基準重設、Soft 消失、照常買進 | 見 N2 |

我的判斷：帳戶檔被刪除時當成首次建立，不符合 R1 的字面。程式在 `AccountGuard.load` 遇到「檔案不存在」就直接回 None（`catos/demo_bot.py:161-162`），分不出從來沒建立過和建立後被刪掉。不過這要使用者自己刪檔，紅線也已經禁止代理編輯這個資料夾，而且一般的重啟、崩潰、Ctrl+C 都不會走到這條路徑。所以它不屬於上一輪 D2 那種「正常重啟就繞過」的缺陷，我把它列成低嚴重度的殘留缺陷 N1。另外要注意：帳戶檔損壞後，目前唯一的復原方式就是刪檔，`demo rearm` 遇到損壞的檔案也會報錯，而刪檔又等於同時重設當日基準並解除 Soft。

### D3 其他合約：已修好（範圍限 SWAP 一般委託）

- 修法：`_account`（`catos/demo_bot.py:228-241`）改成不帶 instId 讀整個帳戶的 SWAP 部位和掛單，其他合約都列進 `others`。啟動時有就拒絕（`:490-491`）；執行中在 `_reconcile` 停下（`:264-265`），K 線之間的檢查也一樣（`:438-439`）；清倉時不擋（`flattening=True`）。

| 情境 | 結果 |
| --- | --- |
| 啟動時 ETH-USDT-SWAP 有一筆掛單（沒有部位） | `foreign_positions_or_orders_in_account:ETH-USDT-SWAP`；沒有建立 run 資料夾；POST 0 筆 |
| 持有 BTC 1 張時，出現 SOL-USDT-SWAP 掛單 | 59 秒後，K 線之間的檢查發現並停下；BTC 部位留著（照 README，「停下不平倉」） |
| Kill 時帳戶另有 ETH 部位 2 張 | 清倉沒有被擋；BTC 部位 0；ETH 沒有被碰 |

範圍限制見觀察 R4（只看 SWAP、只看一般委託）。

### D4 同帳戶兩個 Bot：已修好（殘留 N2）

- 修法：`AccountGuard.acquire`（`catos/demo_bot.py:135-153`）以 OKX uid 的 digest 取得 `msvcrt.locking` 非阻塞檔案鎖，整個 run 都持有，`_close` 時釋放（`:603-604`）。

| 情境 | 結果 |
| --- | --- |
| 另一個**子程序**持有同一個 uid 的鎖，本程序啟動 Bot | `account_busy:another_demo_bot_runs_on_this_okx_account`；沒有建立 run 資料夾；POST 0 筆。不同 uid 的鎖可以取得 |
| 子程序結束後再啟動 | 正常執行 |
| 鎖在各種例外路徑上的釋放：啟動時拒絕（有陌生部位）、啟動時 `_account` 拋出 DemoError、主迴圈拋出 RuntimeError（`failed`） | 三種都已釋放 |
| 鎖交給 `self.guard` 之後、進入 `try` 之前發生例外（模擬 `LocalSupervisor` 建構失敗） | 例外從 `run()` 拋出，**鎖沒有釋放**（同一程序內再取是 `account_busy`）。CLI 每次執行都是一個程序，程序結束鎖就放掉，見觀察 R6 |
| Bot 持有鎖時執行 `demo rearm` | rc=1，`account_busy`，檔案仍是 `soft_latched=true`。沒有 tty（管線或代理）時執行，也是 rc=1（`interactive_terminal_required`） |
| 兩個不同 `--output-root`、同一個 uid | 兩邊都能取得鎖，見 N2 |

## 有沒有引入新問題

- `_intrabar_check` 和 K 線處理之間的競態：沒有。整個 run 只有一個 coroutine。`_intrabar_check` 只在 `_wait_for_bar` 的第一段迴圈裡呼叫（`catos/demo_bot.py:455-457`），和 `_bar`／`_execute` 是先後執行，不會交錯。HTTP 都是 `await asyncio.to_thread`。
- `_call` 會不會重複送單或結清：不會，理由見 D1。實測 D1e、D1f 的 POST 次數都等於應送的筆數。
- Hard 寫 Kill-Switch 失敗：清倉照常，事件裡有紀錄。Soft 鎖存是退路，實測見 D2 表。
- AccountGuard 在例外路徑上的釋放：只有一個窗口會漏，就是 `:496-514`。見 R6。
- `demo rearm` 能不能在 Bot 執行中解除：不能，因為取不到鎖，而且必須在互動式終端機確認（實測見上）。
- 新 actor 對既有讀取端的影響：
  - `kill_switch._check` 的驗證改用新的 `ACTORS`（`catos/kill_switch.py:115`）。
  - local-sim 的 `Watch` 看到 `demo-bot` 觸發會照常 fire，ledger actor 是 `kill-switch-demo-bot`，能通過 `ipc.token`（`[A-Za-z0-9_-]{1,64}`）。`status()` 與 `public()` 會原樣回傳 actor，HTTP 端的 `engage_kill`／`clear_kill` 固定用 `http`。
  - 前端的 `actorLabel` 和型別已經更新：`typecheck` 0 錯誤，`npm test` 21 項全部通過。
  - 實測：一份已有 `demo-bot` 觸發紀錄的檔案，新的 `Watch` 會拒絕啟動。
  - 版本混用的風險見 R7。
- DemoClient 的執行緒鎖：6 個執行緒同時送出，沒有重疊，最小間隔 0.301 秒；在鎖內等待之後才重新簽時間戳（`catos/okx_demo.py:273-291`）。請求裡沒有巢狀呼叫 `_request`，所以不會死鎖。
- Decimal 解析：數字形式的 `markPx` 會解析成 `Decimal('64000.123456789012345678')`，精度沒有損失（`catos/okx_demo.py:293`）。
- 手續費幣別：`feeCcy=BTC` 時拋出 OSError（`catos/okx_demo_exchange.py:108-109`），Supervisor 記成 UNKNOWN、不結清，Bot 停在 `order_not_settled:UNKNOWN`。這是安全方向。
- O1：觸發 Kill 時，如果剛好在等 K 線發布（K 線收盤後 60 秒內查不到），Kill 在同一秒就被處理，清倉到 0。

## 新缺陷

### N1（低，R1 殘留）：帳戶檔被刪除時當成首次建立

- 位置：`catos/demo_bot.py:161-162`、`:284-298`。
- 重現：用假 OKX，run1 買進後虧 6%，觸發 Soft，用 stop.request 停止，部位手動平掉。刪除 `<root>/accounts/*.json`，同一個台北日再啟動。結果：新基準是 4699.999475，不是 5000；Soft 消失，Bot 照常買進。
- 影響：使用者刪檔（包括帳戶檔損壞後，目前唯一的復原方式就是刪檔），就等於同時重設當日基準並解除 Soft，不必經過 `demo rearm` 的確認。代理已經被紅線禁止這樣做。
- 建議：把 uid digest 寫進每個 run 的 `manifest.json`。帳戶檔不存在時，掃描 output root 底下今天有沒有這個 uid 的 `day_basis` 事件，有就拒絕啟動。或者由使用者明確接受「刪檔等於人工重設」，並寫進 README 與 R1 的適用說明。

### N2（低，D2／D4 殘留）：帳戶檔和鎖都跟著 `--output-root` 走

- 位置：`catos/demo_bot.py:483`（`self.output_dir.parent / "accounts"`）。對照既有的 `catos/account_lock.py:29`，它把鎖放在固定的 `~/.catos/…`。
- 重現：同上的 run1 之後，用另一個 `--output-root` 在同一天重啟。基準重設、Soft 消失、照常買進。用兩個不同的 accounts 目錄、同一個 uid 各建一個 `AccountGuard`，兩邊都能取得鎖。
- 影響：使用者為了分開實驗紀錄而改 `--output-root`，就會不知不覺繞過 Soft 與當日基準，同一個 OKX 帳戶也能同時跑兩個 Bot（D4 的情境）。Hard 不受影響，因為 Kill-Switch 是共用的檔案。
- 建議：帳戶檔和鎖改放在與 output root 無關的固定位置（例如 `~/.catos/okx-demo-accounts/`，和 `account_lock` 一樣），測試時用模組常數替換。

## 觀察（不影響本次判定）

- R1：`flatten_failed` 時狀態是 `stopped`，`cli_main` 的結束碼是 0（`catos/demo_bot.py:652`）。終端機有印出提示，但腳本只看結束碼的話，會把「部位還留在 OKX 上」當成正常結束。建議 `flatten_failed` 回 1。
- R2：啟動階段的 `account_config`、`_contract`、第一次 `_account`（`catos/demo_bot.py:476`、`:480`、`:487`）沒有經過 `_call`。這些地方拋出的 `DemoError` 不是 `BotStopped`，`cli_main`（`:641-650`）也沒有接，終端機會印出 Python traceback。訊息已經去掉敏感內容，不會洩漏金鑰。這時還沒有下單，所以是安全的。
- R3：D1 的修法只涵蓋讀取。清倉單的 POST 一旦短暫失敗、OKX 沒收到，會記成 UNKNOWN，查詢一直回 NOT_FOUND，Bot 就以 `flatten_failed` 停下並提示手動平倉（實測見 D1f）。這符合「UNKNOWN 不盲重送」。README 寫「清倉途中讀 OKX 失敗會重試約 2 分鐘」，沒有說寫入失敗的情況，建議補一句。
- R4：D3 只看 `instType=SWAP` 的部位，以及 `orders-pending` 的一般委託（`catos/okx_demo.py:345-365`）。FUTURES、MARGIN、OPTION 的部位，條件單、止盈止損這類 algo 委託，以及其他幣別的資產都看不到。模擬盤階段可以接受，接 Live 前要補。
- R5：`demo rearm` 先 `load` 再 `acquire`（`catos/demo_bot.py:669`、`:673`）。理論上，有一個 Bot 剛好在這兩步之間結束並寫檔時，rearm 會用讀到的舊內容覆蓋過去。這個窗口只有微秒，改成先取鎖再讀就能消除。另外，任何一個帳戶檔損壞，rearm 就直接回 1，其他帳戶也無法解除。
- R6：鎖交給 `self.guard`（`catos/demo_bot.py:496`）之後，到 `try`（`:515`）之前，如果發生例外（`_Log`、`atomic_json`、`OkxDemoExchange`、`LocalSupervisor` 建構失敗），不會執行 `_close`，鎖和 log handle 都要等程序結束才會放掉。CLI 不受影響；如果在同一個程序裡連續跑多個 Bot（例如之後接到 HTTP），就會卡住。
- R7：Kill-Switch 紀錄檔是共用的，而 `demo-bot` 是新的 actor。合併之後，如果有舊版程式的程序還在跑（例如還沒重啟的 8770 服務），它讀到 `demo-bot` 紀錄會判成 `kill_switch_action_invalid`，等於檔案無法讀取。結果是 fail-closed：所有 run 被擋下，介面顯示錯誤。部署時重啟服務即可。另外，模擬盤 Bot 觸發 Hard 時，同一台機器上所有 local-sim run 也會一起停止，這符合「總開關」的語意，但 README 沒有寫。
- R8：AGENTS.md 這次又改了 INVARIANTS 的鎖存條文（2026-11-17），也新增了紅線。依「先問再做」，INVARIANTS 的任何一條都要由使用者定案，上一輪的 O11 也還沒有使用者確認。另外，檔頭第 3 行列出 INVARIANTS 改寫紀錄的那段，沒有補上 2026-11-17 這次。
- R9：上一輪觀察的處理情況：
  - O12 只修了一部分：Bot 限定 BTC-USDT-SWAP，但 `first-order --inst` 仍然接受任何 USDT 永續合約（`catos/okx_demo.py:56`）。
  - O13 只修了一部分：空 tag 仍然接受（`catos/okx_demo_exchange.py:101`），`feeCcy` 是空的也接受。
  - O14 已修好（`catos/demo_bot.py:366-369`），開發者的測試 `test_soft_between_reversal_legs_keeps_running_flat` 有涵蓋這個情境，我沒有另寫重現。
  - O3、O4、O5、O7、O8、O9 這次沒有改動，也不在重驗範圍內。
- R10：uid 取自 `account/config` 回應裡的 `uid` 欄位（`catos/okx_demo.py:334`）。如果這個欄位是空的，會以 `account_uid_missing` 拒絕啟動，屬於安全方向。真實 Demo 回應裡有沒有這個欄位，我沒有連網，無法驗證。

## 實際跑的測試

環境：`CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH` 都指向 scratchpad 的臨時檔，`CATOS_OKX_DEMO_CREDENTIALS` 指向不存在的路徑。

| 指令 | 結果 |
| --- | --- |
| `.venv/Scripts/python.exe -m unittest tests.test_demo_bot tests.test_okx_demo -v` | `Ran 43 tests in 10.564s` / `OK` |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_kill_switch*.py"` | `Ran 26 tests in 9.172s` / `OK` |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"` | `Ran 994 tests in 152.638s` / `OK (skipped=11)` |
| 自寫 `probe_recheck.py`（D1 6 項、D2 6 項、D3 3 項、D4 3 組、新問題 5 項） | `Ran 21 tests in 23.275s` / `OK` |
| 自寫 `probe_d2g.py`（寫入 Kill 失敗後只在隔天重啟；會連帶重跑上面 21 項） | `Ran 22 tests in 24.803s` / `OK` |
| 上一輪的 `acc/test_acceptance_extra.py` | `Ran 7 tests in 28.446s` / `FAILED (errors=1)`。其他 6 項通過。失敗的那項是 `test_restart_same_day_after_hard_resets_basis_and_trades_again`，它原本用來證明 D2，現在第二個 run 會被 `kill_switch_engaged` 擋下，正好說明 D2 已修好 |
| `npm --prefix frontend/cat-os-vite run typecheck` | `tsc --noEmit` 0 錯誤 |
| `npm --prefix frontend/cat-os-vite test` | pass 21 / fail 0 |

沒跑的：
- 前端 `build` 與 `node frontend/cat-os-vite/tests/simulation_integration_test.mjs`：前端只改了顯示文字和型別，而且 build 會寫入工作區。
- 連 OKX 模擬盤實測：紅線不允許，開發者的 smoke2 也沒有讀。

補測腳本都在 `C:\Users\user\AppData\Local\Temp\claude\06a2d6733c105b8e\e959d5a4-c8a1-4a67-830d-e90e8ab84b74\scratchpad\recheck\`（`probe_recheck.py`、`probe_d2g.py`，輸出在 `probe.log`，整套測試的輸出在 `full.log`）。scratchpad 可能會被清掉，所以重現步驟也寫在上面各節裡了。
