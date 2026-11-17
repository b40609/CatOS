# M1 模擬盤 Bot「帶部位停下後接續同一個 run」獨立驗收

- 對象：`git diff e09da051..94f5ffd9`（commit `94f5ffd9`「feat: 模擬盤 Bot 帶部位停下後可接續同一個 run」，分支 `feat/okx-demo-m1`）。程式只改了 `catos/demo_bot.py`（+256／−30），測試改了 `tests/test_demo_bot.py`（+183，新增 8 項），文件改了 `AGENTS.md`、`README.md`、`docs/next-steps.md`。`supervisor`、`journal`、`execution`、`risk` 這次都沒改，只當作被呼叫端來讀。
- 背景：已讀 `acceptance.md`（D1–D4）、`recheck.md`、`recheck3.md`，以及 AGENTS.md 的 INVARIANTS 與紅線。
- 驗收者：沒有參與這次改動的另一個會話（Claude Opus 5.5），2026-11-17。
- 方式：先讀 diff 與現行原始碼，追 `Supervisor.process_bar／dispatch／query_order／rearm`、`Journal.prepare／commit_result／rearm` 與 `ExecutionJournal.prepare／prepare_reversal_close／apply`，再用假 OKX 自己寫情境去重現：`probe_resume.py` 17 項、`probe_extra.py` 2 項、`probe_r2.py` 1 項，另有一個子程序腳本 `probe_child.py`，模擬程序被直接殺掉。腳本都放在會話暫存目錄，沒有 commit。我沒有把開發者的測試結果當成證據，只拿來對照覆蓋範圍。
- 遵守的限制：
  - 全程沒有連網、沒有連 OKX，也沒有打開任何金鑰檔。
  - 沒有讀寫 `~/.catos/`，也沒有碰 `C:\dev\CatOS`。
  - 帳戶紀錄、帳本的帳戶鎖、Kill-Switch、核准這幾條路徑，都改指到每個測試自己的暫存資料夾：`demo_bot.ACCOUNTS_DIRECTORY`、`account_lock.LOCK_DIRECTORY`、`CATOS_KILL_SWITCH`、`CATOS_STRATEGY_APPROVALS`。每個情境的 `setUp` 都會斷言 `accounts_directory()` 與 Kill-Switch 路徑確實落在暫存資料夾裡。
  - 沒有執行 CLI 的 `strategy approve／revoke`、`kill clear`、`demo rearm`。
  - 需要模擬「使用者解除 Kill」時，我把 `CATOS_KILL_SWITCH` 換成一個新的暫存檔，沒有呼叫 clear。
  - 需要「使用者 rearm」時，在行程內呼叫 `rearm_main`，帳戶路徑是暫存的，確認動作由假的 confirm 回呼代答。這是開發者測試的同一種隔離寫法，紅線允許測試這樣做。
  - repo 內只新增了這份報告。

## 結論：FAIL（1 項阻斷缺陷）

主流程都照描述運作：
- 不接管陌生部位。
- UNKNOWN 委託不盲目重送。
- 同一根 K 線重送不會重複決策。
- 錯過的 K 線只補進策略，不下單。
- 停機期間碰到 Hard 或 Kill 會鎖存並清倉。
- 停機期間的 `demo rearm`，在虧損仍超過 Soft 時不生效。

阻斷的是 E1：帳戶紀錄寫入失敗之後，接續會在沒有任何使用者 rearm 的情況下自動解除帳本的 Soft 鎖住，並以 `actor=cli` 記成一次人工 rearm。這違反 INVARIANTS「Soft 鎖存……僅限人工恢復；反彈、重啟不自動解除」。觸發需要寫檔失敗，發生率低，但方向是 fail-open，修法也很小。另外有 9 項不阻斷的觀察（F1–F9）。

## 逐條判定

| # | 項目 | 判定 | 證據（檔案:行號） | 實跑 |
| --- | --- | --- | --- | --- |
| 1 | 不接管陌生部位 | 通過（見 F1、F2） | `catos/demo_bot.py:532-540`：有掛單就拒絕，有部位才找可接續的 run。`:580-582`：帳戶紀錄沒有 run 指標時拒絕。`:584-593`：manifest、模式、bot_id、account_id、DB 任一不符就拒絕。`:594`：核准不同就拒絕。`:596-598`：策略設定或風控門檻不同就拒絕。`:599-610`：以唯讀方式開帳本，Bot 被隔離或沒有 ownership 就拒絕。`:613-614`：部位數量不符就拒絕。`:539-540`：只有不是接續時才建新資料夾 | 開發者測試：部位 2 對帳本 1，拒絕且 POST 1 筆、manifest 不變；資料夾刪掉時拒絕；換了核准時拒絕。我自己的 N 項：門檻改成 Soft 6%，得到 `resume_config_changed`，舊 run 所有檔案逐 byte 相同。A 項：OKX 上同數量但換成手動部位，**被接續**（F1）。M 項：在 UNKNOWN 委託後面還藏著部位不符時，拒絕前已經動了舊 run（F2） |
| 2 | UNKNOWN 不盲重送 | 通過 | `:720-731`：只呼叫 `query_order`，最多 10 輪，仍有未決委託就以 `resume_unresolved_orders` 停下。`okx_demo_exchange.py:95-96`：查不到時回 `NOT_FOUND`。`execution.py:238-240`：`NOT_FOUND` 不算證據、不結算。`:746-753`：沒送出的意圖等過期限才 `dispatch`。`execution.py:98-100、125`：同一個 key 永不重送，超過期限一律 ABORTED。`:751-752`：萬一送出了就停下 | B 項：OKX 一直回「不存在」時，10 秒（假時鐘）後停下，原因是 `resume_unresolved_orders:<clOrdId>`。帳本那筆維持 `('UNKNOWN', 0)`，沒有被當成未送出；POST 維持 1 筆；也沒有建立 run2／run3。第二次啟動同樣拒絕。開發者測試：查得到時補記成交「接續時補查」，之後由 Kill 清倉 |
| 3 | 沒處理完的 K 線重送 | 通過 | `:734-742`：取出 PENDING 那一筆，用 `parse_event` 還原後交給 `process_bar`。`journal.py:960-965`：內容雜湊不同就隔離 Bot，相同就繼續同一個 seq。`journal.py:993-996`：已經 COMMITTED 的只回原收據。重送仍沿用原本的 `expires_at_ms`，過了期限就是 EXPIRED，沒過期限的進入下面的等待後也會 ABORTED | L 項：2000 組隨機 Decimal 文字經 `decimal_text` 來回轉換，結果完全相同（`str(Decimal(s))` 本來就冪等）。開發者測試：在 bar 4 中斷後接續，出現 `resume_input`，下單序列和不中斷時一樣。J 項：程序被直接殺掉、留下 `-wal`／`-shm` 的情況，接續也正常 |
| 4 | 錯過的 K 線 | 通過（見 F4） | `:777-779`：整頁 K 線必須逐根相差剛好一個週期，重複或缺根都會停下。`:780-782`：最舊一根必須正好接在 checkpoint 之後，否則以 `resume_gap_too_long` 停下。`:783-785`、`:797-806`：補進的 K 線 `expires_at_ms=now`，所以只會是 EXPIRED，不會成為可下單的意圖。`:786-789`：只有最新一根走 `_bar`，`_bar` 第一步就是 Kill 檢查（`:809`）。`okx_demo.py:443-458`：K 線依時間排序，只取已收盤的 | E 項：頁內有重複或少一根時，都得到 `resume_candles_not_contiguous`，POST 1 筆。O 項：`RESUME_CANDLES=2` 而剛好錯過 2 根時可以補上（邊界正確）。K 項：連續接續兩次後 inputs 的 seq 是 1..8 連續，fills 4 筆沒有重複，`resumes` 有 2 筆。P 項：最新一根在收盤約 5 分鐘後（一個週期）才下單（F4） |
| 5 | 風控鎖存跨接續 | **不通過（E1）** | `:558`：帳本已是 Hard 時沿用 `hard_engaged`。`:559-562`：帳戶紀錄是 Soft 就重新鎖住。`:763-765`：FLAT 先清倉。`:766-774`：帳本有 Soft、帳戶紀錄沒有時，就呼叫 `supervisor.rearm(actor="cli")`。`:357`：帳戶紀錄改成只在實際穿越 Soft 時才鎖。基準沿用 `:326-340` 原有的邏輯 | G 項：沒有 rearm、虧損已回升時，仍鎖著，反手的開倉腿沒有送出。H 項：做了 rearm 但虧損仍超過 Soft 時，帳戶紀錄被重新鎖住，不解除。I 項：跨到隔天，以當下權益 4699.999475 建立新基準，Soft 仍鎖住。F 項：停機期間虧到 12%，接續時清倉，並以 actor `demo-bot` 觸發 Kill-Switch。Q 項：前一次 Kill 之後清倉失敗、使用者換掉總開關檔再重開時，帳本的 `manual_kill` 讓 Bot 只清倉、不開新倉。**R 項：帳戶紀錄寫 Soft 失敗、虧損回升後，接續自動 rearm（E1）** |
| 6 | 接續流程中的 Kill-Switch | 通過（見 F3、F5） | 不檢查 Kill 的窗口有：`:720-731` 查詢最多 10 輪（每輪最多 5 秒逾時加 1 秒）、`:746-749` 等舊意圖期限（最多約 60 秒）、`:783-785` 補 K 線，以及期間幾次 `_call` 的退避重試（約 14 秒）。這些窗口裡都不會送出任何新委託。第一個可能送單的地方是 `_bar`，它先做 Kill 檢查（`:809`），或是只減倉的 `_flatten`（`:763-765`） | C 項：接續一開始就觸發 Kill，在等舊意圖的期間沒有發現；`resume_intent` 之後才出現 `kill_switch`，偵測延遲約 59 秒（假時鐘：1794802504000 到 1794802563050）。非只減倉的單只有第一個 run 的那一張 buy。D 項：停機期間觸發 Kill，啟動時被 `KillSwitchError` 擋下，部位 1 留在 OKX 上，不會清倉（F5） |
| 7 | 新測試的覆蓋 | 部分 | `tests/test_demo_bot.py:481-634` 的 8 項 | 有覆蓋：正常接續、數量不符、資料夾不見、核准換掉、缺口過長、UNKNOWN 查得到、PENDING 重送、未送出的意圖、rearm 後接續。沒覆蓋，由我補測：OKX 一直回「不存在」（B）、改門檻（N）、K 線重複或缺根（E）、缺口邊界（O）、停機期間的 Hard（F）、沒有 rearm（G）、rearm 但仍超過 Soft（H）、跨日（I）、Kill 鎖存在帳本（Q）、程序被直接殺掉（J）、接續中觸發 Kill（C）、寫入失敗（R，發現 E1） |
| 8 | 文件與程式是否一致 | 大致一致（見 F6、F7） | `README.md:155-165`、`docs/next-steps.md:54-56、62、81`、模組 docstring `catos/demo_bot.py:32-41` | 「新增 8 項」數字正確，299 根與「約 3 天」也正確。不一致或寫得不完整的地方見 F6、F7 |

## 缺陷（阻斷）

### E1　帳戶紀錄沒記到 Soft 時，接續會自動解除帳本的 Soft，並記成人工 rearm

- 位置：`catos/demo_bot.py:766-774`，搭配 `:352`、`:357-360`。
- 原因：`_observe` 先把帳本的 Soft 寫入持久化（`persist_controls`，`:352`），之後才寫帳戶紀錄（`guard.save`，`:360`）。`_resume` 只要看到「帳本 reasons 只有 `soft_loss`」而且「帳戶紀錄 `soft_latched=False`」，就推定使用者在停機期間做過 `demo rearm`，於是以 `actor="cli"`、`evidence_id="demo-rearm-<rearms 筆數>"` 解除帳本的 Soft。它沒有核對 `rearms` 裡是否真的有一筆晚於這次鎖住的 rearm。
- 重現（`probe_extra.py` 的 `test_probe_R_soft_write_lost_then_bounce`，加上 `probe_r2.py`）：
  1. 正常啟動，bar 3 買進 1 張，之後權益降 300（6%，超過 Soft）。
  2. 寫帳戶紀錄時遇到 OSError（以 mock 模擬：寫入內容含 `soft_latched=True` 時拋出）。run 結束成 `failed`，部位 1 留著；帳本已經是 Soft。
  3. 權益回升 300，使用者沒有做 `demo rearm`，只是用同一個指令重開。
  4. 結果：
     - 接續時出現 `soft_rearmed` 事件。
     - 帳本 `risk_actions` 多了 `('rearm', 'cli', 'demo-rearm-0')`，但帳戶紀錄的 `rearms` 是空的 `[]`。
     - bar 5 的反手開倉腿（`sell 1`、非只減倉，是一筆加倉）被送出。
     - 同樣情況下沒有寫入失敗的 G 項，則一直維持鎖住。
- 後果：Soft 被「重啟＋反彈」自動解除，而且稽核紀錄把它記成一次人工 rearm，這兩點都違反 INVARIANTS 的鎖存條文。觸發條件是寫帳戶檔失敗，例如磁碟滿、權限錯誤，或 Windows 上防毒軟體鎖住檔案造成 `replace` 失敗，所以發生率低。Hard 不受影響，因為 Hard 會寫入共用的總開關並且清倉。修改前的程式碰到同樣的寫入失敗也會失去 Soft，但那時要人工先平倉才能重開；現在只要重開就會自動解除，而且被標成人工動作。
- 修正方向（僅供參考）：只有在 `rearms` 的最後一筆時間晚於帳本 Soft 鎖住的時間（或另外記下帳本已見過的 rearm 筆數）時才 rearm。若帳本有 Soft 而帳戶紀錄沒有，又找不到 rearm 證據，就把帳戶紀錄補成鎖住、維持 fail-closed。修完再補一項測試：寫入失敗加上反彈後接續，必須仍然鎖住。

## 觀察（不阻斷）

- **F1　「剛好擁有」只比對數量。** `_resumable_run`（`:613`）與 `_reconcile`（`:314`）只比較數量，`facts["avg_px"]` 有讀到卻沒有用來比對。停機期間如果有人在 OKX 手動平倉，再開一張同數量的倉，接續會把它當成自己的部位（A 項）。主流程每分鐘的核對也有同樣的盲點，模擬盤授權第 3 題也只要求「部位與餘額對得上」，所以不判阻斷。不過停機可能長達數天，風險比主流程每分鐘一次大得多。README 第 156 行寫「帳本必須剛好擁有這個部位」，建議寫明「只比對數量」，或改成核對 OKX 的 avgPx／posId（`cTime`）。
- **F2　`_resumable_run` 的 docstring 說「Read-only：所有檢查通過前不改舊 run」，有例外。** 帳本還有未決委託時，數量比對會延後到 `_recover`（`:612-613`）。在那之前已經做了三件事：把 `stop.request` 改名（`:657-659`）、在 manifest 追加一筆 `resumes`（`:661-664`）、查詢並記下自己委託的成交。如果最後發現部位不符，停止原因是 `position_mismatch:...`，沒有 `resume_` 前綴，CLI 因此不會顯示任何提示（M 項的 hint 是 None）。下次啟動才會得到 `resume_position_mismatch`。帳務本身是對的（記的是自己的委託），只是 docstring 與提示不一致。
- **F3　不檢查 Kill 的窗口比文件寫的長。** `docs/next-steps.md:62` 只寫「等待舊委託期限的那一分鐘」。實際上前面還有查詢未決委託最多 10 輪（每輪最多約 6 秒）以及讀取時的退避重試，最壞情況大約 2 分鐘以上。README 第 161 行「Bot 在 1 秒內鎖住」在接續期間並不成立。這些窗口內不會送出新委託，所以不阻斷，建議文件照實寫。也可以在等待迴圈與查詢迴圈裡呼叫 `_kill_check`（`self.watch` 在 `run()` 一開始就建好了）。
- **F4　最新一根 K 線最晚可能在收盤後一整個週期才下單。** P 項：5 分鐘線在收盤 4 分 58 秒後才接續，bar 5 仍然得到 `RESERVED_SIMULATION` 並送出反手。next-steps 第 54 行有寫明（15 分鐘線最多約 15 分鐘），但這和研究回測「下一根開盤成交」的假設不同，屬於代理自己的設計決定，沒有使用者定案。另外，Donchian 是訊號式策略（`research_donchian.py:60-72`），補進來的那幾根 K 線上若有反手或出場訊號，接續後部位會和策略、回測不一致，要等到下一個訊號才修正（K 項：bar 5 的反手被略過，部位一直維持多單）。
- **F5　停機期間觸發 Kill 不會清倉。** D 項：啟動時 `kill_switch.Watch` 直接拒絕，部位留在 OKX 上。使用者解除 Kill 之後重開，帳本沒有見過這次 Kill，會照常接續交易。這是修改前就有的語意，但有了接續功能後，使用者可能預期「按 Kill 就會平倉」。建議在 README 寫明：Bot 停著時按 Kill 不會平倉，要自己到 OKX 網頁平倉。
- **F6　程序被直接殺掉後，`fills.json` 與 `status.fills` 會少算。** S 項：OKX 上有 4 筆 POST，帳本有 4 筆成交，但 `fills.json` 只有 3 筆，`status.fills` 也是 3。原因是被殺掉的那次 run 沒有寫出 `fills.json`，接續時從 `[]` 開始算（`:617-618`，程式註解有說明）。帳本與 `events.jsonl` 都是完整的，只影響報表。可以改成接續時從帳本的 `execution_fills` 重建。
- **F7　文件細節。**
  - 模組 docstring（`:39`）說「Resuming itself sends nothing」。但帳本是 FLAT 時，`_resume` 會清倉（`:763-765`）；最新一根 K 線也可能下單。真正完全不送單的只有 `_recover`。
  - README 第 155 行把舊的「（其他合約的也算）」改寫後，沒有提到其他合約的掛單也會被拒絕（程式 `:280`、`:537-538` 有擋）。
- **F8　自動 rearm 被拒絕時，帳戶紀錄與帳本不一致。** 例如 `mgnRatio` 沒回或低於 300%，導致 `health=DEGRADED`，`rearm` 被拒（`:773-774`）。這時帳戶紀錄已經解除，帳本仍是 Soft，這個 run 剩下的時間都不能加倉；終端機會顯示「Soft 仍鎖住」。方向是 fail-closed，可以接受，只是這個 run 裡不會再重試 rearm。
- **F9　沒有在模擬盤實測。** 開發者已在 next-steps 第 81 行說明：「正式 Bot 在跑，沒有在模擬盤實測接續」。本次驗收也只用了假 OKX。真實 OKX 的時序（例如 `order_by_client_id` 對很舊的委託回什麼、`market/candles` 一頁的實際根數）還沒驗證過。

## 實際跑過的指令與輸出摘要

```
git show 94f5ffd9 --stat；git diff e09da051..94f5ffd9（全部讀過）
git status --short → 乾淨（報告寫入前）

.venv/Scripts/python.exe -m unittest tests.test_demo_bot
  Ran 29 tests in 23.861s  OK

各模組以 discover 執行（直接用 tests.xxx 會因為 tests 不是 package 而 import 失敗，所以改用 discover）：
  test_demo_bot.py            Ran 29  OK
  test_execution.py           Ran 24  OK
  test_execution_supervisor.py Ran 9  OK
  test_kill_switch.py         Ran 26  OK
  test_p5.py                  Ran 13  OK
  test_protection.py          Ran 19  OK
  test_risk.py                Ran 14  OK
  test_risk_journal.py        Ran 8   OK
  test_risk_period_r1.py      Ran 21  OK
  test_okx_demo.py            Ran 24  OK
（後端整套沒有重跑。這次只改了 demo_bot.py，開發者的 1004 OK／skipped 11 屬於歷史證據）

probe_resume.py（17 項，Ran 17 in 20.6s，OK）重點輸出：
  [A] 同數量換手動部位 → 被接續，manual_kill 結束，posts buy/sell(r)/sell/buy(r)
  [B] resume_unresolved_orders:b6288a11…，耗時 10000 ms，帳本 [('UNKNOWN', 0)]，POST 1；第二次同樣拒絕
  [C] Kill 在 1794802504000 觸發，在 1794802563050 才發現（約 59 s），事件順序 resume_intent → started → kill_switch → flatten
  [D] 停機時觸發 Kill → KillSwitchError，部位 1 沒變
  [E-dup]/[E-hole] resume_candles_not_contiguous，POST 1
  [F] risk_flat:hard_loss,soft_loss，posts buy、sell(r)，kill 紀錄 [('engage','demo-bot')]
  [G] 沒有 soft_rearmed，沒有非只減倉的 sell
  [H] 帳戶紀錄重新鎖住 True，沒有 rearmed，沒有非只減倉的 sell
  [I] 基準 (20773,'5000') → (20774,'4699.999475')，soft_latched True
  [J] 子程序 rc 9，留下 state.sqlite3-wal/-shm；接續正常，最後 manual_kill
  [K] seqs [1..8]，fills 2 筆對 posts 2 筆，resumes 2 筆
  [L] 2000 組 Decimal 來回轉換完全相同
  [M] position_mismatch:okx=3:ledger=1，hint None，manifest 已改，stop.request 已改名；下次啟動 resume_position_mismatch
  [N] resume_config_changed，舊 run 檔案逐 byte 相同
  [O] RESUME_CANDLES=2、錯過 2 根 → 接續成功
  [P] 收盤後約 5 分鐘接續，bar 5 RESERVED_SIMULATION 並送出反手
  [Q] 第一次 flatten_failed；換掉總開關檔後接續 → risk_flat:manual_kill，部位 0，沒有非只減倉的單

probe_extra.py / probe_r2.py：
  [R] 第一次 failed OSError；接續 soft_rearmed True，posts 多了 sell 1（非只減倉）；帳戶紀錄 rearms []
  [R2] 帳本 risk_actions [('rearm','cli','demo-rearm-0'), ('manual_kill','kill-switch-cli',…)]
  [S] posts 4、fills.json 3、status.fills 3、帳本 fills 4
```

暫存腳本位置（沒有 commit）：`C:\Users\user\AppData\Local\Temp\claude\06a2d6733c105b8e\590345b6-9f76-493a-a5ca-7d9d9e237d28\scratchpad\probe_resume.py`、`probe_extra.py`、`probe_r2.py`、`probe_child.py`。
