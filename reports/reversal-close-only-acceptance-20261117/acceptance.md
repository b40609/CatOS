# 獨立驗收：反手被風控擋下時只平倉（reversal_close_only）

- 對象：commit `27845a20`（branch `feat/agent-strategy`），worktree `C:\Users\user\.t3\worktrees\CatOS\feat-wp-b-kill-switch-7bd55fc4c3125468`
- 驗收者：沒有參與這次改動的另一個會話（Claude Opus 5.5），2026-11-17
- 範圍：`catos/risk.py`（`evaluate`、`_increase_refusal`）、`catos/journal.py`（`_risk_verdict`）、`catos/execution.py`（`prepare`）、`catos/demo_bot.py`（一行 log），以及它們的呼叫端（`supervisor.dispatch`、`execution.flatten`、`local_sim_replay._fill_intent`）
- 隔離：沒有碰 `C:\dev\CatOS`、沒有連網、沒有執行 `catos.cli demo`、沒有讀憑證。`CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH` 指到暫存路徑；整套測試時 `HOME`／`USERPROFILE` 也導到暫存資料夾；demo_bot 測試本身已 patch `ACCOUNTS_DIRECTORY`／`LOCK_DIRECTORY`。沒有改 `catos/`，沒有 commit。
- 隔離失誤（已處理）：`replay_over_budget.py` 和 `close_only_paths.py` 跑的時候我沒有導開 `HOME`，local-sim 的帳戶鎖寫了 15 個 `.lock` 到 `~/.catos/local-simulation-locks/`。每一個的內容都指向這次 scratchpad 裡的 `state.sqlite3`。這 15 個檔已經移到 `scratchpad\acceptance-reversal\moved-home-locks\`；其他鎖檔（包括一個正被占用的 `fb0cc894….lock`）沒有碰。`~/.catos/okx-demo-accounts/` 沒有被寫入。
- 腳本位置：`C:\Users\user\AppData\Local\Temp\claude\06a2d6733c105b8e\e959d5a4-c8a1-4a67-830d-e90e8ab84b74\scratchpad\acceptance-reversal\`

## 結論：FAIL

風控核心正確：沒有找到任何會在閘門關閉時增加曝險或穿越零點的路徑，非反手的加倉與未核准部署的反手也和舊版一樣整筆拒絕。不通過的原因是一個中度缺陷：local-sim 歷史重播（`local_sim_replay._fill_intent`）不認得新的 `reversal_close_only` 判定，會把它當成兩腿反手送出。結果是重播以 `failed` 結束，帳本留下一筆卡在 `SUBMITTING` 的委託和沒釋放的保留額度，之後 resume 也接不回來。改之前同一情境是乾淨的 `stopped`。預設 profile 碰不到這個情境（見第 5 節），但非預設 profile 重現得出來。修正後只需要重驗重播這一段。

## 缺陷

### D1（中）：local-sim 重播把 reversal_close_only 當成兩腿反手處理，以 failed 結束並卡住一筆委託

- 位置：`catos/local_sim_replay.py:141`、`:146`、`:154`（`_fill_intent`）。觸發點是 `catos/risk.py:658` 新增的判定。
- 情境：核准部署在重播中反手，但反向開倉超過曝險額度（例如價格比進場時高、或張數接近額度）。`risk.evaluate` 現在回 `RESERVED_SIMULATION / reversal_close_only`。`_fill_intent` 只看 `view.position * receipt.target_position < 0`，所以判定為「平倉腿」，用 `reversal_close_key(intent_key)` 算 clOrdId 並排好 FakeExchange 的回報。可是 `Supervisor.dispatch` 的 `reversal_pending` 只認 `reversal_reserved`，於是走 `prepare`，以 `intent_key` 當 order_key 和 clOrdId 送單。FakeExchange 回的報告 clOrdId 對不上，`execution.apply` 拋出 `JournalError: report client id mismatch`。
- 預期：重播要嘛把它當成單腿、只減倉的平倉送出，要嘛在送出前以明確原因停下（例如 `unexpected_verdict:RESERVED_SIMULATION:reversal_close_only`）。不論哪種，帳本都應該乾淨（沒有未決委託、沒有保留額度），跟改之前一樣。
- 實際（`replay_over_budget.py`，序列 `100×4, 90×4, 130×5`，`Limits(0.002, 0.5, 0.05, 0.10)`，1 張）：
  - 新版：`state=failed`，`stop_reason="JournalError: report client id mismatch"`。第二筆委託 `SUBMITTING`、`settled=0`（reduceOnly=True、sz=1，所以沒有增加曝險），`reservations`／`outbox`／`risk_orders` 各留 1 列，帳本部位 -1。resume 會以 `resume_with_unresolved_orders` 拒絕。
  - 舊版（`git archive 27845a20^` 解到暫存目錄跑同一支腳本）：`state=stopped`，`stop_reason="unexpected_verdict:REJECTED:symbol_exposure_limit"`，三張表都是空的。
- 影響：只在 local-sim（FakeExchange），沒有資金風險，送出去的那筆也是只減倉。但重播紀錄壞掉、停止原因誤導，而且 `outputs/local-sim-replay` 下的正式 run 會留下無法 resume 的帳本。
- 建議修法：`_fill_intent` 在 `receipt.reason == "reversal_close_only"` 時，`leg_target = 0`、`order_key = receipt.intent_key`、單腿、預期 `reduceOnly=True`，成交後照常續跑；或依「第 2 步碰到拒絕就停」的精神在 dispatch 前停下。兩種都要補一個重播測試（本報告的情境可以直接改成 test）。

## 逐項檢查

### 1. 閘門關閉時有沒有路徑會增加曝險或穿越零點

追了一個 `reversal_close_only` 意圖的完整路徑（`close_only_paths.py`，真的 Supervisor／Journal／FakeExchange，在反手那根 K 線的風控觀測之後 latch，所以 commit 時閘門已關）：

- commit（`journal.py:1035-1039`）：`intents.target` 留策略原本的 -1，`reason=reversal_close_only`，`reservations.amount=0`，`risk_orders` 是 `quantity=-1, reduce_only=1, eligible=1`。
- `Supervisor.dispatch`：`reversal_pending` 只認 `reversal_reserved`（`execution.py:141`），回 False，走 `prepare`，不會產生開倉腿。
- `ExecutionJournal.prepare`（`execution.py:110`）：以 target 0 重新評估，得到 `legal_reduction`、quantity = -目前部位、reduce_only。只有在 `verdict.quantity == risk_orders.quantity` 且 `reduce_only` 一致時才送。
- 實際送出：剛好一筆 `sell 1`、`reduceOnly=True`、tag `41cb53c54d6dABDE`；成交後部位 0，三張表都清空；再 dispatch 一次不送任何東西（NEVER resend）。
- 決策和送出之間部位變了：
  - 部位改成 0（模擬保底停損先平倉）：`target_equals_position`，委託寫 ABORTED，沒送單，額度釋放。
  - 部位改成 2：`legal_reduction` 的量是 -2，跟保留的 -1 不符，ABORTED，沒送單，額度釋放。
  - 部位翻到另一側的情況同理：數量或方向對不上，就 ABORTED。
- 交易所端另有保險：FakeExchange 的 `apply` 會拒絕「reduceOnly 成交卻增加部位或穿越零點」（`execution.py` 的 `reduceOnly fill would increase or cross zero`）。OKX 端則是 reduceOnly 旗標本身。

結論：沒有路徑會增加曝險或穿越零點。

### 2. Hard／Kill（FLAT）

- 在 FLAT 下 commit，同樣得到 close-only（等同策略 target 0 的合法減倉，跟改之前 FLAT 下 target 0 的行為一樣）。
- 還沒送就進 `flatten_step`：`execution.flatten` 把還在 outbox 的 close-only 寫成 ABORTED 並釋放，接著送一筆 flatten 子單 `sell 1 reduceOnly`，成交後部位 0，三張表清空。沒有重複減倉。
- 先 dispatch 再 flatten：close-only 在 FLAT 下照樣送出成交（合法減倉），之後 `flatten_step` 什麼都不送，phase 變 `VERIFY`，沒有卡住。
- `control_step` 只撈 `reduce_only=0` 的保留，不會碰 close-only。
- 模擬盤 Bot 在 `_bar` 開頭遇到 FLAT 就直接清倉、不做決策，所以模擬盤上 FLAT 與 close-only 不會同時出現。`_flatten_rounds` 不受影響。

### 3. 減倉衝突的檢查

- 允許反手時，`reduction_conflict`（快照的 conflict、`held_reduction`、同方向的掛單）現在排在閘門之前，有衝突就整筆拒絕（`risk.py:651-653`）。網格與既有測試都確認了。
- Journal 層：反手不算 reduction，所以只要有任何 `risk_orders` 或未決委託，`_risk_verdict` 會先回 `order_pending`（`journal.py:695-697`），根本到不了 evaluate。

### 4. 理由與優先序的改變（新舊 evaluate 網格比對）

`grid_compare.py`：把 `27845a20^` 的 `risk.py` 載成另一個模組，在 journal 層模擬新舊兩種順序（舊：保底停損 → order_pending → evaluate；新：order_pending → evaluate(refuse_increase)）。網格包含 mode（RUN／NO_INCREASE／FLAT）、health、basis（今天／沒有／昨天）、部位 ±10/0、13 種目標（含超額度）、掛單、other_notional、conflict、held（含 held_reduction）、`allow_reversal`、保底停損閘、order_pending、快照過期、position_verified、reconciled。

- 共 2,156,544 組。1,223,936 組完全相同。
- 5,104 組變成 `reversal_close_only`。每一組都滿足：`allow_reversal=True`、確實反手、舊版是被閘門拒絕（increase_gate_closed／day_basis_missing／exposure limit／protection_gate_closed）、沒有任何衝突、快照新鮮且部位已驗證、quantity = -部位、reduce_only、保留 0。違規 0 組。
- 其餘 927,504 組都是「拒絕變拒絕，只換了理由」，沒有任何一組的接受與否改變。主要的理由變動：
  - 保底停損閘關閉時，`protection_gate_closed` 變成 `order_pending`／`risk_snapshot_stale`／`position_not_verified`／`reduction_conflict`。原因是保底停損的判斷從 journal 最前面移到 evaluate 裡面。
  - 允許反手且閘門關閉、又有衝突時，`increase_gate_closed`／`day_basis_missing` 變成 `reduction_conflict`。
- 唯一的處置變動是觀察 O1：保底停損閘關閉且目標等於部位時，`REJECTED/protection_gate_closed` 變成 `NO_CHANGE/target_equals_position`，共 5,184 組。新的結果比較準確。模擬盤 Bot 與重播對這兩種都不停機，但 bar log 的處置欄會不同。
- 非反手的加倉、`allow_reversal=False` 的反手：接受與否和舊版完全一致。`cross_zero_forbidden` 照舊（網格包含）。

### 5. local-sim 重播一致性

- 研究回測沒有曝險額度與 Soft／Hard。重播中 Soft／Hard 會在決策前的 `observe` 就停止（`local_sim_r4.observe` 拋 `synthetic_risk_halt`），當日基準每天午夜由 `observe` 建立。所以重播裡唯一走得到 close-only 的是曝險額度。
- 兩條路都讓這次 run 不通過一致性檢查：舊版是 REJECTED 停止，新版是 D1 的 failed（`replay_completed=False`）。所以不會出現「一致性通過但成交悄悄不同」的情況。`replay_consistency` 的 `replay_completed` 檢查擋得住。
- 預設情境碰不到：
  - 預設的測試序列（`CLOSES`）新舊版都跑完 9 筆成交、一致性通過。在額度卡在進場邊緣的 `Limits(0.0023…)` 下也一樣，因為那個序列的反手價格都不高於進場價。
  - 正式 profile（`donchian-breakout` 192/48、1 張、本金 10,000、BTC-USDT-SWAP 每張 0.01 BTC）：單幣額度 1.0×10,000×0.5 = 5,000 USDT（legacy-v1 是 15,000）。1 張的名目約 600 到 1,200 USDT，要 BTC 超過 50 萬 USDT，或權益掉到 2,000 以下（Hard 10% 會先觸發），才會超額。所以預設 profile 碰不到，只有使用者核准較大張數、又在反手時價格高於進場時才會碰到（也就是 D1）。

### 6. INVARIANTS 的看法

- 合法減倉始終允許：符合。close-only 從 prepare 到送出都和既有的 `legal_reduction` 走同一條路，連保底停損未確認時也放行（`execution.py:115` 的 `verdict.reduce_only or not blocked`）。
- Soft 停止增倉：符合。反向開倉被拒絕，只送減倉；之後每根 K 線的 -1 目標從 0 起算是加倉，照舊 `increase_gate_closed`。
- Hard 清倉：不受影響（見第 2 節）。
- UNKNOWN 不盲重送：符合。`prepare` 遇到同 key 已存在的委託一律回 None；部位不符就 ABORTED，不重試。
- P3b 不做自動去槓桿：我認為這不算自動去槓桿。去槓桿是風控因為「現有部位超限」而主動減倉，沒有策略訊號。這裡的減倉來自策略自己的決策：目標穿越零點，代表策略已經不要原本的多單。風控只是拒絕其中增加曝險的那一半（反向開倉），沒有超過策略要求的範圍去減倉，觸發條件是策略訊號而不是曝險水位。改之前把策略的出場一起擋掉，反而讓被擋下的那一刻持有策略已經不要的部位。新行為和「合法減倉始終允許」一致。被動超限本身（例如價格漲到部位超額）仍然不會觸發任何減倉，網格裡沒有反手目標的情況都沒有變。

## 觀察（不是缺陷）

- O1：保底停損閘關閉時，拒絕理由與處置的優先序改變（見第 4 節），包括 `REJECTED/protection_gate_closed` 變成 `NO_CHANGE`。比較準確，不影響安全。建議在 next-steps 註記，免得有人照舊 log 的理由統計。
- O2：模擬盤 Bot 把 close-only 的成交記成「開倉／調整」（`demo_bot.py:535`，因為 order_key 等於 intent_key，`closing_leg=False`）。前一行已經印「只平掉原部位」，但成交那行的標籤會誤導，建議 close-only 時記成「反手平倉（開新倉被擋）」。
- O3：close-only 之後，策略在後續每根 K 線仍給出反向目標，Bot 維持空倉並記 REJECTED。使用者 `demo rearm` 之後，下一根 K 線會以當時的價格開反向倉，而不是在原本的訊號價開。這是使用者決定的自然結果，跟研究回測不同，上實盤前值得讓使用者知道。
- O4：`intents.target` 存的是策略原本的反向目標，實際動作卻是平到 0。`prepare` 依 `reason` 判斷，所以正確；但其他以後要讀 `intents.target` 推論實際下單方向的程式（報表、UI）要記得看 `reason`。

## 執行過的指令與結果

在 worktree 根目錄執行，`HOME`／`USERPROFILE`／`CATOS_STRATEGY_APPROVALS`／`CATOS_KILL_SWITCH` 都導到 `scratchpad\acceptance-reversal\home`：

| 指令 | 結果 |
|---|---|
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_step2_deployment.py"` | Ran 23 tests，OK |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_demo_bot.py"` | Ran 42 tests，OK |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"` | Ran 866 tests，OK（跟作者回報的一致） |
| `.venv/Scripts/python.exe scratchpad/acceptance-reversal/grid_compare.py` | 2,156,544 組，違規 0（見第 4 節） |
| `.venv/Scripts/python.exe scratchpad/acceptance-reversal/close_only_paths.py <worktree> <tmp>` | 5 個情境（soft、部位改 0、部位改 2、Kill 後 flatten、Kill 先 dispatch），全部 OK |
| `.venv/Scripts/python.exe scratchpad/acceptance-reversal/replay_over_budget.py <worktree> <tmp>`（預設序列） | completed，9 筆成交，一致性通過 |
| 同上，序列 `100×4,90×4,130×5`、leverage 0.002，新版 | failed：`JournalError: report client id mismatch`（D1） |
| 同上，以 `git archive 27845a20^` 解出的舊版 | stopped：`unexpected_verdict:REJECTED:symbol_exposure_limit`，帳本乾淨 |

前端檢查沒有跑：這次改動沒有碰前端。
