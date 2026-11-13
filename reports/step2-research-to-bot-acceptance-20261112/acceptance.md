總結論：PASS（沒有阻斷缺陷；有 6 項非阻斷觀察，其中觀察 1 是文件說法和實測不符，建議合併前更正文件）

# 第 2 步「研究策略上 local-sim Bot 跑歷史重播」獨立驗收

- 驗收者：獨立會話（Claude Opus 5.5），沒有參與開發。2026-11-13。
- 範圍：`git diff 4eb16071..220de36b`（26 檔，+2533／-52），以及未 commit 的自測證據 `reports/step2-research-to-bot-acceptance-20261112/selftest-evidence/` 與原始重播目錄 `outputs/selftest-step2-replay-20261113/`。
- 依據：`AGENTS.md` 授權紀錄 2026-11-12「完全同意建議」、INVARIANTS、紅線；`docs/step2-research-to-bot-proposal.md`；`docs/step2-research-to-bot.md`。
- 唯讀：除了本檔，沒有修改 repo 內任何檔案，沒有 commit 或 push。所有自建資料都放在 scratchpad 或系統暫存目錄，核准檔一律用隔離路徑（`CATOS_STRATEGY_APPROVALS`）。沒有執行指向正式路徑的 `strategy approve／revoke`（`outputs/strategy-approvals/` 不存在，驗收前後都一樣），沒有動 `outputs/research-web`、`outputs/local-sim-control`、`outputs/local-sim-r4`，沒有連網，也沒有讀任何憑證。
- 附帶影響：跑後端整套測試時，既有測試在 `outputs/` 留下 2 個 fixture 目錄（`workspace-w6-fixture-test-9da1ac8e…`、`workspace-w8-fixture-test-eed5c876…`，git 忽略）。這是既有測試的行為，我沒有刪除。驗收期間工作樹的 `docs/next-steps.md` 有一份別人未 commit 的修改（開發者的交接文字），我沒有碰。

## 我實際執行的檢查

| # | 指令／做法 | 輸出摘要 |
| --- | --- | --- |
| A | `C:/dev/CatOS/.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"`（工作樹，未設 `CATOS_STRATEGY_APPROVALS`） | `Ran 924 tests in 117.720s`、`OK (skipped=11)`。和開發者自述相同。過程中有一行 `Port 63379 already in use. No process stopped and no alternate port selected.`，是既有測試的訊息，不影響結果 |
| B | `npm --prefix frontend/cat-os-vite run typecheck`；`npm --prefix frontend/cat-os-vite test` | typecheck exit 0；`tests 21`、`pass 21`、`fail 0` |
| C | 自寫的獨立核對腳本 `independent_check.py`（scratchpad），對三輪重播帳本各跑一次 | 三輪都是 `problem_count: 0`，細節見第 4 項 |
| D | `local_sim_replay.build_id()`（HEAD 220de36b） | `d34d09ddc3af…74da4de`，和三輪重播 manifest 的 build_id 相同，所以證據是用已 commit 的執行端程式產生的 |
| E | 自寫的對抗測試 `adversarial_tests.py`（scratchpad，7 個測試，隔離核准檔與暫存資料根） | `Ran 7 tests`、`OK`；印出的觀察見第 1、3 項 |
| F | 自寫的 `resume_held.py`（scratchpad）：送單前中斷再續跑 | 見觀察 3 |
| G | CLI 實測（`CATOS_STRATEGY_APPROVALS` 指向 scratchpad 的 `cli-approvals.jsonl`） | 見第 1 項 |
| H | 比對提案第 6 節的 P1 建議文字是否逐字進了 `AGENTS.md` | `True` |

沒做的：
- 沒有重跑 4H 全量重播（約 11 分鐘一次）。改成用和研究引擎完全無關的獨立重寫模型，核對開發者三輪重播的原始帳本（檢查 C），再用 build_id 確認帳本是 HEAD 程式產生的（檢查 D）。
- 沒有跑前端 `build` 和 `node frontend/cat-os-vite/tests/simulation_integration_test.mjs`：前者會寫入工作樹的 `dist/`，後者要起服務與埠，都超出唯讀範圍。這兩項只有開發者自述（build 成功、整合測試 12 項 PASS），我沒有重驗。前端屬「未經獨立驗收」範圍。

## 1. 核准（fail-closed、雜湊鏈、CLI、只有 Donchian）

結論：通過。觀察 1、2 是非阻斷。

- 未核准時解析不到：`resolve("donchian-breakout", …)` 回 `unknown_strategy`（既有測試）；`WorkerConfig.from_wire` 在沒有有效核准時回 `unregistered strategy: approval_not_found`（`catos/ipc.py` from_wire、`catos/strategy_registry.py:235-275` `resolve_deployment`）。CLI 實測（檢查 G）：`replay` 在沒有核准時印 `no_active_approval_for_profile`、exit 1，沒有建立輸出目錄。
- 撤銷：`active_approval` 遇到撤銷紀錄回 `approval_revoked`；Worker 每根前後呼叫 `resolve_deployment`（`catos/worker.py` `source_check`），重播主迴圈每根也呼叫一次（`catos/local_sim_replay.py:275-278`）。既有測試 `test_revocation_stops_*` 兩支通過（全套 A）。
- 來源或 manifest 改一個位元組：`resolve_deployment` 核對研究白名單、manifest 欄位、manifest 檔 sha256 與磁碟上的來源（`catos/strategy_registry.py:266-274`）。測試 `test_edited_source_or_manifest_is_rejected_after_approval` 用暫存複本與 patch 驗證，沒有改 repo 檔案。
- 部署設定任一欄位不符：策略、版本、來源 sha256、manifest sha256、參數（含順序）、張數、lookback、合約、週期、預熱都比對（`catos/strategy_registry.py:255-265`）。本金、手續費率、滑價不在 `WorkerConfig` 裡，由 `find_active` 用整份 profile 相等比對綁定（`catos/strategy_approvals.py:290-296`）；我的對抗測試 `test_profile_cost_fields_bound_by_find_active` 改 `initial_balance`、`fee_rate`、`slippage_bps` 任一項都找不到核准。重播用的是核准紀錄裡的 profile（`catos/local_sim_replay.py:189`）。
- 雜湊鏈：改內容、刪中間行、換順序、尾端少一個位元組、非正規 JSON 都讀取失敗（既有測試 `test_edited_removed_or_truncated_lines_fail_closed`）。**但整行刪掉最後一行不會被發現**，見觀察 1。
- CLI 只能在互動式終端機核准（檢查 G，管線輸入 `echo approve |`）：`strategy approve` 印 `interactive_terminal_required`、exit 1，核准檔沒有建立；`strategy revoke` exit 1；`strategy list` 顯示 0 筆；`strategy identity` 印 `donchian-breakout donchian-parameters-v1 sha256=1596e3ace639…6817 manifest_sha256=3149232f…62d3`，和文件寫的 64 碼相同。判斷在 `catos/strategy_approvals.py:377-383`（stdin 與 stdout 都要是 tty）。
- 只有 Donchian：`BOT_STRATEGIES` 只有一筆（`catos/strategy_approvals.py:86-89`）；SMA、`dcm-fade`、`tsmom-multi` 都回 `strategy_not_bot_eligible`（對抗測試）。
- `CATOS_STRATEGY_APPROVALS` 覆寫：和文件說的一樣，可以指到任意檔案，再用 Python 直接呼叫 `approve(confirm=lambda…: True)` 或 `_append` 產生有效核准（對抗測試 `test_forged_append_without_cli_is_accepted` 通過）。這和 P1「核准紀錄是程序上的防呆，不是安全邊界」一致；每次重播的 manifest 與一致性報告都記錄實際用的核准檔路徑（`catos/local_sim_replay.py:212-213`、`catos/replay_consistency.py:247`）。Worker 子程序只多繼承這個路徑變數（`catos/worker_host.py:23-28`），不是憑證。唯讀介面沒有顯示每次重播用的核准檔，見觀察 4。

## 2. 檢查點 v2 與重啟重餵

結論：通過。

- Supervisor 給的歷史：`Journal.history`（`catos/journal.py:714-731`）取 `state='COMMITTED' AND seq<=checkpoint.event_seq` 的最近 `count` 筆，要求 seq 連續且結尾等於檢查點、筆數等於 `min(count, event_seq)`，否則 `committed input history is incomplete`。Worker 端 `ipc.parse_history`（`catos/ipc.py:415-440`）再驗：筆數恰為 `min(event_seq, lookback)`、K 線連續（相差一個 timeframe）、最後一根等於檢查點時間。兩端各驗一次，沒有放寬。
- 只在檢查點已提交的範圍取歷史：處理中（尚未 COMMITTED）的那一根不會被當成歷史重餵。
- ready 判定：v2 是 `event_seq >= lookback`（`catos/ipc.py:489-492`）。Donchian 的 `ready` 是四個極值視窗都滿（`catos/research_donchian.py:55-58`），entry 必大於 exit（`catos/strategy_approvals.py:159-160`），所以恰好在第 lookback 根轉為 ready；預熱必須 >= lookback（`:169-171`），評估邊界一定 ready。
- 策略狀態只由最近 lookback 根決定：Donchian 的持倉從 Supervisor 給的帳戶檢視讀（`account.position`），不存在策略內部，所以重餵最近 192 根就能完全恢復。測試 `test_restart_from_committed_history_matches_uninterrupted_worker`（切點 2、4、7、12）和 `test_resume_restores_the_worker_from_committed_bars`（新 Supervisor＋新 Worker，續跑後和一次跑完位元組相同）通過。
- SMA v1 不變：`WorkerConfig.to_wire` 在 `deployment is None` 時輸出和原本相同；v1 檢查點仍要 `closes` 且長度 `min(seq, 2)`；v1 意圖 key 仍是 `[環境, 帳戶, bot, "sma-trend", 1, seq, 0]`（`catos/journal.py:705-712`）。這次 diff 只新增 `tests/test_step2_deployment.py`，沒有改任何既有測試，既有 SMA／R4／IPC 測試在整套 A 中全數通過。R4 的 `RUNTIME_FILES` 多了 `catos/strategy_approvals.py`，R4 build_id 因此改變，提案已預告。
- 帳本實證（檢查 C）：三輪帳本的 `bots.checkpoint_json` 都只有 `config`、`event_seq`、`last_open_time_ms` 三個鍵，`event_seq = 10956`；286 筆意圖 key 都是 8 段、第 4 到 6 段為 `donchian-breakout`、`donchian-parameters-v1`、核准 id。

## 3. 反手兩腿

結論：通過。4H 資料上反手 0 次，反手只由合成資料測試覆蓋；我另外補了兩個故障情境，結果符合不變量。

- `allow_reversal` 只在部署設定時開：全 repo 唯一呼叫點是 `catos/journal.py:703`（`allow_reversal=config.deployment is not None`）。送單前的重新評估 `ExecutionJournal.prepare` 沒有傳這個參數，所以開倉腿只能從已驗證的空倉成立，持倉沒歸零就是 `cross_zero_forbidden`。
- 平倉腿：`prepare_reversal_close`（`catos/execution.py:159-203`）以目標 0 重新評估，要求 `legal_reduction`、`reduce_only`、數量等於 `-position`、對帳完成、沒有未結委託、同一 epoch、未過期；payload 由 `build_payload` 產生，`reduceOnly=True` 且注入固定 tag（`catos/fake_exchange.py:57-67`）。送不出時，平倉腿與整個意圖在同一個交易內記成 ABORTED 並釋放 reservations／outbox／risk_orders。
- 額度：commit 時以整段變化（例如 +1 到 -1 的 delta -2）檢查曝險預算，保留額度＝開倉腿（`catos/risk.py:618-633`）。
- 平倉腿送不出時開倉腿不會送出：既有測試 `test_blocked_close_leg_ends_the_whole_reversal_atomically` 通過。
- 我補的故障測試（檢查 E，合成資料、隔離目錄）：
  - 平倉腿 UNKNOWN（FakeExchange 沒有腳本、逾時）：平倉單留在 `UNKNOWN`、`settled=0`，沒有重送；第二次 `dispatch` 回 `None`，意圖記成 ABORTED、額度釋放（reservations／outbox／risk_orders 都是 0）；整段只有 1 筆送單，就是那張 reduce-only 平倉單。
  - 平倉腿部分成交（2 張只成交 1 張後 CANCELED）：持倉剩 +1；第二次 `dispatch` 回 `None`，意圖 ABORTED；整段只有 1 筆送單（reduce-only、sell 2）。
- tag 注入：三輪 103 筆委託的 payload 都是 `tag=41cb53c54d6dABDE`、`tdMode=cross`、`posSide=net`、`ordType=market`、`instId=BTC-USDT-SWAP`；每筆的 `reduceOnly` 都和持倉變化相符（檢查 C）。重播 runner 自己也每筆檢查一次（`catos/local_sim_replay.py:153-155`）。

## 4. 重播 runner 與一致性工具

結論：通過。觀察 5 是非阻斷。

一致性工具的獨立性：
- Bot 端從帳本讀：每根 Worker 目標（`inputs.result_json`）、每根收盤時 Supervisor 給 Worker 的帳戶檢視（`inputs.input_json`）、判定（`intents`）、成交（`execution_fills`）。研究端跑 `research.backtest`（`funding_events=()`、`margin=None`）。兩邊的決策是兩個程序各自算出來的（Worker 子程序對研究回測），帳戶檢視是用帳本成交重放的，不是循環論證。
- 已知的部分重疊：Bot 端的成交價與手續費是 runner 用 `research._Ledger` 依下一根開盤算好、寫進 FakeExchange 腳本的（`catos/local_sim_replay.py:142-147`），和研究端是同一段程式，所以「同一根成交時價格與手續費相等」是構造上成立的。真正有檢出力的是：哪一根下決策、目標與數量、成交在哪一根、持倉路徑與權益曲線。提案第 4 節已寫明這個設計。
- 為了排除工具本身的漏洞，我寫了和 `research.backtest`、`_Ledger`、`replay_consistency`、`local_sim_replay` 都無關的重寫模型（檢查 C）：自己算 Donchian 通道（不含當根）、自己做下一根開盤加 2 bps 滑價、依方向取整到 tick、手續費、已實現損益與平均成本，直接讀三輪帳本比對。結果（三輪相同）：
  - 10,956 根輸入 seq 1 到 10956 連續、全部 COMMITTED，每根 K 線和雜湊核對過的資料集逐欄相同；預熱 192 根沒有任何目標。
  - 10,764 根評估的 Worker 目標和重寫模型完全相同。
  - 成交 103 筆，時間、帶正負號張數、價格、手續費逐筆相同；每筆成交量等於委託量。
  - 期末持倉 -1、餘額 10353.1289095、已實現 382.583、手續費 29.4540905、權益 10373.8899095，和 `summary.json` 完全相同。期末未成交意圖一致。
  - reservations／outbox／risk_orders 期末都是 0。
- 門檻誤差 0：所有欄位用 Decimal 相等比較，沒有容差（`catos/replay_consistency.py:193-221`）；出現 REJECTED、未完成或非 FILLED 委託就失敗。反手兩腿先合併、要求兩腿同價。合併後的手續費等於研究單筆手續費（手續費是 張數 × 面值 × 價格 × 費率，沒有逐筆取整，兩腿相加等於一筆）。
- 資金費與保證金差額：報告列出已發表結果（含資金費與保證金模型）期末權益 10370.6788014807133285613，和基準差 -3.2111080192866714387，等於資金費支付 3.2111080192866714387；強平 False、保證金拒單 0、成交和基準相同 True。和提案第 2 節的實測（-3.21）一致。
- 兩次重播位元組相同：current-a 與 current-b 的 decision_digest、fills_digest、build_id、approval_id 全部相同；new-defaults（1.0 倍有效槓桿 × 50% = 單幣 0.5 倍、Soft 5%、Hard 10%）的成交摘要也相同，風控預設 `risk.Limits()` 沒有改。
- 停止行為：Soft／Hard 觸發只停止並記錄 `risk_halt:`，沒有清倉單（`test_soft_loss_stops_the_replay_without_liquidation`）；非預期判定停止（`test_rejected_verdict_stops_the_replay`）；撤銷後在下一根前停止、持倉留著、沒有 reduce-only 單（`test_revocation_stops_before_the_next_bar_without_flatten_or_release`）。全部在整套 A 中通過。
- 規則面：`AGENTS.md` 的 P1 改寫和提案第 6 節建議文字逐字相同（檢查 H）；紅線新增一條；授權紀錄新增一條；開頭沿革說明有寫。其他 INVARIANTS 沒有改。新增程式在金額路徑沒有 float（只有步調秒數與耗時統計用 float），沒有網路程式碼。

## 缺陷

### 阻斷

無。

### 非阻斷觀察

1. **雜湊鏈擋不住「整行刪掉最後幾行」，文件說法過頭。**
   - 證據：`catos/strategy_approvals.py:242-266` 只從頭驗鏈，沒有任何外部錨點；檔案尾端少掉完整的行時，剩下的仍是合法的鏈。`docs/step2-research-to-bot.md:36` 寫「改、刪、換順序、截斷…一律讀取失敗」，模組說明 `catos/strategy_approvals.py:7-8` 也寫 removed line 會斷鏈；測試的 truncated 只砍最後一個位元組（`tests/test_step2_deployment.py:132`）。
   - 重現：核准一筆、撤銷，再把檔案改成只剩第一行。`active_approval` 回傳那筆核准，`WorkerConfig.from_wire` 也解析得到（對抗測試 `test_deleting_the_last_revoke_line_reactivates_the_approval`，輸出 `TAIL-DELETE: approval reactivated, WorkerConfig resolves`）。
   - 影響：撤銷可以被「刪最後一行」或「還原成舊版檔案」（例如同步軟體或備份還原）無聲抵銷。因為任何本機程式本來就能自行追加有效紀錄（觀察 2），這不比既有限制更弱，也符合 P1「程序上的防呆，不是安全邊界」，所以不列阻斷。
   - 建議：至少把文件改成「中間的行被改、刪、換順序，或尾端不完整都會失敗；整行刪掉最後幾行或還原舊版檔案無法偵測」。如果要擋還原舊版，可以讓重播 manifest 記錄核准檔的行數與最後一行 sha256，續跑或比對時發現變短就停。
2. **核准檔有非 UTF-8 內容時丟出 `UnicodeDecodeError`，不是 `ApprovalError`。**
   - 證據：`catos/strategy_approvals.py:251` 的 `line.decode("utf-8")` 在 `_strict_json` 的 try 外面。
   - 重現：在核准檔尾端加 `b"\xff\xfe\n"`。`read_records` 和 `resolve_deployment` 丟 `UnicodeDecodeError`（仍然 fail-closed，解析不到策略，重播記成 failed）；但 `replay_api._approvals`（`catos/replay_api.py:29-32`）只接 `ApprovalError`，`GET /api/workspace/replay` 會變成 500，而不是 `approvals_state: unavailable`（對抗測試 `test_invalid_utf8_line`，輸出 `INVALID-UTF8 overview raised: UnicodeDecodeError`）。
   - 建議：把 decode 移進 `_strict_json` 的 try，或在 `read_records` 轉成 `ApprovalError("approval_invalid_json")`。
3. **在「已保留額度、還沒送單」時中斷再續跑，不是立即 fail-closed。**
   - 證據：續跑只檢查未結委託（`catos/local_sim_replay.py:263-265`），沒有檢查已保留但沒有委託的意圖。
   - 重現（`resume_held.py`）：第 5 根保留額度後、送單前中斷（`bars 4`、`reservations 1`）。續跑繼續處理第 6 到 8 根，到第 9 根新的意圖才以 `unexpected_verdict:REJECTED:order_pending` 停止，期間 0 筆委託。
   - 影響：沒有重複曝險、沒有送單，最後仍停下，一致性也會判失敗；只是比 `docs/step2-research-to-bot.md` 寫的「續跑會 fail-closed」晚幾根才停。
   - 建議：續跑時如果 `reservations`／`risk_orders` 不是空的，就以 `resume_with_held_intent` 立即停止。
4. **唯讀介面的重播清單沒有顯示該次重播用的核准檔路徑。**
   - 證據：`catos/replay_api.py:58-80` 的每筆 run 沒有回傳 manifest 的 `approvals_path`；頂層 `approvals_path` 是服務程序當下的路徑（`:96`）。
   - 影響：如果有人用測試核准檔、把重播輸出到預設資料根 `outputs/local-sim-replay/`，介面上看起來會像正式核准的重播（核准 id 不在清單裡，但沒有明示）。目前的自測證據放在 `outputs/selftest-step2-replay-20261113/`，不受影響。
   - 建議：run 物件加上 `approvals_path`，和目前核准檔不同時標示「測試核准」。
5. **一致性報告的 build_id 不涵蓋比對工具本身。**
   - 證據：`catos/local_sim_replay.py:53-56` 的 `RUNTIME_FILES` 沒有 `catos/replay_consistency.py`（也沒有 `catos/cli.py`）。
   - 影響：報告無法證明是哪一版比對程式產生的。這次我用獨立重寫模型重驗過，結論不受影響。
   - 建議：一致性報告另記 `replay_consistency.py` 的 sha256。
6. **反手兩腿沒有真實資料覆蓋。** 4H 五年資料反手 0 次（`counts.reversal_decisions = 0`），兩腿行為只由合成資料測試（3 次以上反手）與我補的 UNKNOWN、部分成交兩個故障測試覆蓋。接 Demo 前建議用 15m 或 5m 資料找一段有反手的區間再跑一次一致性比對（不需新的採集授權的話）。

## 結論

核准綁定、fail-closed 解析、檢查點 v2 重餵、反手兩腿的原子性與不盲重送、tag 注入、一致性門檻誤差 0，都經獨立重驗，符合使用者 2026-11-12 的 8 題決策與 INVARIANTS。三輪 4H 重播帳本用和研究引擎無關的重寫模型逐根、逐筆核對，結果完全相同。觀察 1 到 6 都不影響金流正確性；觀察 1 的文件說法建議合併前更正。

正式核准仍要使用者自己在互動式終端機執行（`docs/step2-research-to-bot.md` 開頭），核准後的正式重播與 `replay-compare` 本次沒有執行，也不在授權範圍。

驗收用的腳本在 scratchpad（不在 repo）：`independent_check.py`、`adversarial_tests.py`、`resume_held.py`。
