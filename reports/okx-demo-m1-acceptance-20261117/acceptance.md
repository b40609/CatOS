# M1（OKX 模擬盤）獨立驗收

- 驗收對象：`git diff f30c4800..888e9f36`（分支 `feat/okx-demo-m1`，HEAD `888e9f36`）
- 驗收者：沒有參與這次改動的另一個會話（Claude Opus 5.5），2026-11-17
- 方式：讀原始碼與 INVARIANTS、核對實跑證據（只讀）、重跑測試，另外用假 OKX sender 補測 8 個情境。全程沒有連網，沒有讀金鑰檔，也沒有執行 approve、revoke 或 kill clear。

## 結論：FAIL

唯一交易出口、固定 tag／cross／net、UNKNOWN 不重送、成交入帳、核准範圍、憑證與 Decimal 都通過，實跑證據也和帳本逐筆相符。

不通過的原因在風控與清倉，共兩項，屬於「未清倉」和「繞過風控」：

- D1：Kill 或 Hard 清倉途中，只要遇到一次暫時性的讀取錯誤（例如 HTTP 503），Bot 就以 `failed` 結束，部位留在 OKX 上。
- D2：Soft／Hard 鎖存和當日基準只存在單次 run 的帳本裡。同一天重新啟動時，會用已經虧損後的權益重建基準，Bot 也能再開倉。

另有兩項中低風險缺陷（D3、D4）與 14 項觀察，列在後面。

## 逐條不變條件

| # | 不變條件 | 判定 | 依據 |
| --- | --- | --- | --- |
| 1 | 唯一交易出口；tag、cross、net 不可繞過 | PASS | Bot 只透過 `supervisor.dispatch`／`flatten_step` 下單（`catos/demo_bot.py:213`、`:241`），沒有直接呼叫 `DemoClient` 的寫入。payload 由 `fake_exchange.build_payload` 建立（`catos/fake_exchange.py:172-182`，經 `catos/execution.py:67`）。轉接器先檢查 tag、cross、net 與 instId（`catos/okx_demo_exchange.py:50-53`），`submit_supervisor_payload` 再要求欄位集合完全相同，並逐一檢查各欄位的值（`catos/okx_demo.py:394-406`）。Supervisor 只接受 FakeExchange 或 OkxDemoExchange 兩種型別，而且帳戶要相符（`catos/supervisor.py:46-49`）。測試 `test_payload_without_tag_never_leaves`、`test_trades_reverses_and_kill_flattens_through_supervisor` 都通過。實跑兩張單的 `payload_json` 都帶 tag `41cb53c54d6dABDE`、`tdMode=cross`、`posSide=net`。`first-order`（`catos/okx_demo.py:514`）是授權過的 CLI 煙霧測試，不經 Supervisor，但同樣強制帶 tag 與 cross（`:374-375`）。 |
| 2 | UNKNOWN 不盲重送、不釋放額度 | PASS | 傳輸錯誤、逾時，以及不在 `_REQUEST_REJECTED` 內的 OKX 錯誤，一律轉成 `OSError`（`catos/okx_demo_exchange.py:56-63`）。Supervisor 接到後記成 UNKNOWN（`catos/supervisor.py:828-830`、`catos/execution.py:215-220`）。UNKNOWN 不會 settle，也不釋放額度。`prepare` 遇到同一個 key 一律不重送（`catos/execution.py:98-100`）。`_REQUEST_REJECTED`（`:30-31`）列的 51000、51001、51004、51006、51007、51008、51010、51020、51121、51124、51169、51202、51203，都是下單前的參數、額度或餘額驗證失敗，OKX 沒有收下委託，歸成確定拒絕是正確的。51016（clOrdId 重複）不在清單內，會被當成不確定，這也正確。補測結果：POST 已成交但回應遺失時，記成 UNKNOWN，查詢後轉成 FILLED，POST 只送一次；遇到 51016 時記成 UNKNOWN，Bot 停在 `order_not_settled:UNKNOWN`，POST 也只送一次；交易所變慢、觸發 Supervisor 的 5 秒逾時時，同樣記成 UNKNOWN、查詢後結清，沒有重送。用 spy 確認這三種情況都實際走到 `uncertain()`（4 次）。 |
| 3 | 成交入帳（部分、多筆、手續費正負、complete／revision） | PASS | 只有終態（FILLED／CANCELED），而且列出的成交數量加總等於 `accFillSz` 時，才標成 `complete`（`catos/okx_demo_exchange.py:109-112`）。帳本的成交以 `(exchange_id, trade_id)` 為主鍵去重，同一 id 內容不同會直接報錯（`catos/execution.py:264-270`）。OKX 的 fee 收費為負，轉接器反號後存成正的成本（`:106`），對應 `local_sim_r4.project_account` 的 `balance -= fee`（`catos/local_sim_r4.py:92`）。revision 取 `uTime*1000+成交筆數`（`:114`），且必須嚴格遞增（`catos/execution.py:245-248`）。實跑證據：買單 ordId 4105099728749056000 在帳本有 12 筆成交，trade_id 沒有重複，數量合計 1.00，fee 合計 0.3218278565（約等於 1×0.01×64366×0.05%，正負號正確）；`report_revision` 是 1794843905549012（uTime×1000＋12）。補測：成交分 3 筆、跨 3 次查詢陸續出現時，入帳 3 筆、合計 1，沒有重複；部分成交後被 OKX 取消時，帳本 0.4 等於 OKX 0.4，Bot 停在 `order_canceled`，沒有接管，也沒有重送。 |
| 4 | 對帳：每根核對、啟動空倉、不接管 | PASS（範圍有缺口，見 D3） | 每根 K 線前、每次成交後、清倉的每一輪，都會核對 OKX 部位等於帳本，而且合約上沒有掛單（`catos/demo_bot.py:141-154`、`:222-223`、`:233-240`）。啟動時要求空倉、無掛單，否則不建立帳本（`:291-294`）；有逐倉部位就停（`:128-129`）。測試 `test_refuses_foreign_position_or_orders_before_creating_a_ledger`、`test_position_changed_outside_stops_without_adopting` 通過。缺口：只查本合約，同一帳戶其他合約上的部位與掛單看不到（D3）。 |
| 5 | 風控：日基準、Soft、Hard／Kill 清倉、reduce-only、歸零才停、margin_ok、fail-closed | 不通過（D1、D2） | 每個台北日第一次觀測時建立基準（`catos/demo_bot.py:159-167`、`catos/risk.py:664-679`），經 `commit_day_basis` 持久化。四個 fail-closed 旗標都有明示宣告（`catos/demo_bot.py:170-173`）。margin_ok 的判斷是：無部位時為真；有部位時，OKX 要回 mgnRatio 且至少 3（`:169`）。清倉單由 `execution.flatten` 建立，只減倉（`catos/execution.py:363`）；帳本套用回報時拒絕會跨零的成交（`:292-295`）。部位要等 OKX 回報為 0 才算清倉完成（`catos/demo_bot.py:233-237`）。實跑的清倉單 ordId 4105108293048061952 是 `reduceOnly:true`、賣 1 張，成交 1 筆，帳本 ownership.position 為 0；`risk_actions` 有一筆 manual_kill 稽核，`control.halt_reasons=["manual_kill"]`。測試 `test_hard_loss_latches_and_flattens`、`test_soft_loss_blocks_increase_but_keeps_running` 通過。不通過的部分：清倉遇到暫時性錯誤就中止（D1）；鎖存與基準不跨 run（D2）；`flows_known=True` 是直接宣告的，沒有證據（O7）。 |
| 6 | Kill-Switch 每根前與等待期間檢查；Bot 不解除 | PASS（有觀察 O1） | Kill-Switch 在每根 K 線開頭檢查（`catos/demo_bot.py:351`），等待收盤期間每秒檢查一次（`:261-267`）。啟動時已觸發或讀不到檔案，就拒絕啟動（`:283`、`catos/kill_switch.py:338-347`）。`demo_bot.py` 裡沒有任何 clear 呼叫。實跑時，23:49:18 在等待中觸發 Kill，同秒開始清倉，23:49:21 成交，23:49:22 部位歸零後停止。等待 K 線發布（最多 90 秒）和等待委託結清（最多 30 秒）的期間不檢查 Kill（O1）。 |
| 7 | 核准：舊核准不涵蓋模擬盤；參數不符就解析不到 | PASS（有觀察 O9） | `find_demo_approval` 會拒絕 2026-11-16T00:00Z 之前的核准（`catos/demo_bot.py:403-407`）。每根 K 線都重新 `resolve_deployment`，比對核准綁定的所有欄位（`catos/strategy_registry.py:235-265`）；不符或已撤銷就停，不平倉（`catos/demo_bot.py:352-355`）。正式核准紀錄只有一筆 `8ca25f97…`，時間是 2026-11-13，不涵蓋模擬盤（只讀過時間欄位）。測試 `test_old_approval_does_not_cover_demo` 通過。 |
| 8 | 憑證不洩漏；白名單；每個請求帶 `x-simulated-trading: 1` | PASS | `Credentials` 與 `DemoClient` 的 repr 都已遮蔽（`catos/okx_demo.py:70-82`、`:253-254`）。送出層的例外一律包成固定訊息，並用 `from None` 切斷例外鏈（`:203-207`、`:276-280`）。讀金鑰檔的錯誤訊息只含路徑與原因。端點是固定白名單，寫入只有下單與撤單（`:40-53`、`:257-259`）。模擬盤 header 寫死，沒有參數能關掉（`:262-263`）。直接 TLS 連到固定主機，不走代理（`:190-209`）。測試 `test_errors_never_contain_credentials`、`test_every_request_is_demo_and_signed_correctly`、`test_non_whitelisted_endpoints_are_refused_before_sending` 通過。證據資料夾掃描結果：events、fills、manifest、status、approvals、kill、run_smoke.py、smoke.log 與 state.sqlite3 裡，api_key、secret、passphrase、OK-ACCESS 都出現 0 次，UUID 形式出現 0 次；32 碼十六進位的命中都是 `prev_sha256` 的零值。smoke.log 只印出第幾組金鑰和 OKX 上的名稱 `catOSv1_Demo`。沒有發現疑似金鑰的內容。 |
| 9 | Decimal | PASS | 金額、價格、部位都經 `_dec` 或 `Decimal(str)` 處理（`catos/okx_demo.py:221-231`、`:446-447`）。用到 float 的只有睡眠秒數與時間間隔。mgnRatio 的比較是 Decimal 對 int。 |
| 10 | 補處理的 K 線不下單 | PASS | 非最新的 K 線，`expires_at_ms` 設成 now（`catos/demo_bot.py:369`）；`commit_result` 遇到 `now_ms >= expires` 就判 EXPIRED（`catos/journal.py:1013-1014`），`prepare` 也要求 `now_ms < deadline`（`catos/execution.py:125`）。補測：兩根同時到達，第一根原本會突破進場，結果判 `EXPIRED/deadline_elapsed`，POST 數為 0。漏掉超過 5 根時停在 `bar_gap`（`:271-273`）。 |

## 缺陷

### D1（中高，未清倉）：Kill／Hard 清倉遇一次暫時性讀取錯誤就中止，部位留在 OKX

- 位置：`catos/demo_bot.py:233`（`_flatten` 內的 `_account`）、`:246`、`:344-345`（`run` 把非 `BotStopped` 的例外一律當成 failed）。
- 重現（補測 `probe_flatten_transient.py`）：持有 1 張時觸發 Kill；清倉第一輪讀 `/account/balance`，OKX 回一次 HTTP 503。結果是 `state=failed`，原因 `DemoError: OKX 回應不是 JSON（HTTP 503）`，OKX 部位仍是 1。Kill 已經鎖存，但沒有其他程序會接手清倉。
- 影響：README 承諾「平倉到 0 再停止」，在 50011 限流、50001 系統忙或網路短暫中斷時都不成立。Hard 走同一條路徑。
- 建議：`_flatten` 內讀取帳戶時遇到 `DemoError`，退避後重試（例如 5 到 10 次，間隔遞增），委託相關的 UNKNOWN 仍照舊停下。重試用完還沒清完，就把狀態寫成 `flatten_incomplete`，並在終端機與 `status.json` 明確告警，要使用者手動平倉。另外補一個測試：Kill 加上一次 503。

### D2（中，繞過風控）：Soft／Hard 鎖存與當日基準不跨 run，同日重啟會重設預算

- 位置：每次 run 都用新資料夾、`require_new_database=True`，帳戶別名也是隨機產生（`catos/demo_bot.py:294-296`、`:310-312`）；基準只在這次 run 的帳本裡（`:159-167`）。
- 重現（補測 `test_restart_same_day_after_hard_resets_basis_and_trades_again`）：第一次 run 虧 12%，觸發 Hard，清倉後停止，權益 4399.998955。同一個台北日、同一個 OKX 帳戶再啟動一次：新 run 的基準就是 4399.998955，Bot 照常買進（`buy, reduceOnly=False`）。
- 抵觸的條文：INVARIANTS R1 寫「同日既存基準不得因重啟、虧損或入金替換」；鎖存條文寫「當日不重設預算……重啟……不自動解除」「人工恢復仍不得覆蓋有效風險原因」。README 只寫「重新啟動要先把部位平掉」，沒有說明預算會被重設。Hard 清倉後部位已經是 0，所以這個條件不會擋下重啟。
- 建議（擇一）：(a) 觸發 Hard 時，同時寫入共用的 Kill-Switch 紀錄（`kill_switch.engage`）。重啟時 `Watch` 會拒絕啟動，要使用者手動解除，符合「僅限人工恢復」。實作最小。(b) 把當日基準與鎖存存成 OKX 帳戶層級的檔案，以 OKX 帳戶身分加台北日為鍵，新 run 啟動時沿用，有鎖存就拒絕啟動。Soft 也要能跨 run（例如 Ctrl+C 後重啟，Soft 不能消失），(b) 才涵蓋得到。

### D3（中，曝險與陌生部位）：只看本合約，同帳戶其他合約的部位與掛單不計入、不阻擋

- 位置：`catos/demo_bot.py:127`、`:131`（`positions`／`pending_orders` 都帶 instId）；`:170-173` 的 Snapshot 沒有傳 `other_notional`，預設為 0（`catos/risk.py:377`）。
- 情境：模擬盤帳戶另外持有 ETH-USDT-SWAP（手動或其他程式開的），Bot 完全看不到，仍以 1.0 倍、50% 的預算加倉。帳戶的實際有效槓桿可能超過上限，也違反「陌生部位／委託禁止增倉」。這一條是讀程式碼推得的，沒有寫補測。
- 建議：啟動時與每根 K 線前，各查一次不帶 instId 的全部 SWAP 部位與掛單（端點已在白名單內）。只要有其他合約的部位或掛單，就拒絕啟動或停止（最簡單）；或者把它的名目金額填進 `other_notional`。

### D4（中低，單一 Bot 獨佔）：同一 OKX 帳戶可同時跑兩個 Bot

- 位置：`AccountLock` 以帳戶別名為鍵（`catos/supervisor.py:36`），而 Bot 的帳戶別名每次隨機產生（`catos/demo_bot.py:296`）。
- 情境：在兩個終端機各啟動一次 `demo bot`。如果兩邊在同一根 K 線都讀到空倉，並且都送出買單，OKX 部位會變成 2。兩個 Bot 在成交後對帳時都會發現不符而停下（`:223`），部位 2 留著不平，曝險是上限的兩倍。只要有一邊先成交，另一邊會在下單前停下，所以需要剛好碰上競態。這一條也是讀程式碼推得的。
- 建議：以 OKX 帳戶身分（`account/config` 的 uid 或金鑰名稱）加 instId 取得一個固定的本機鎖，啟動時就拿，拿不到就拒絕。

## 觀察（不影響正確性）

- O1：Kill 只在 `_wait_for_bar` 的第一段迴圈裡檢查（`catos/demo_bot.py:261-267`）。等待 K 線發布（`:268-278`，最多 90 秒）、`_settle`（`:185-194`，最多 30 秒）和反手兩腿之間都不檢查。README 第 156 行寫「1 秒內鎖住」，並不是每種時刻都成立。建議在這幾個迴圈裡也呼叫 `self.watch.check()`，至少要先 latch。
- O2：Hard／Soft 只在每根 K 線與每次成交後觀測，K 線之間權益沒有人看。15m 週期下最多要 15 分鐘才會發現虧損越線。INVARIANTS 也寫明盤中由 Guardian 負責；建議在 README 說明這個延遲。
- O3：最壞情況下，轉接器的 `submit`（HTTP 逾時 10 秒，`catos/okx_demo.py:37`，加上 8 次輪詢）會超過 Supervisor 的 5 秒逾時（`catos/supervisor.py:828`）。成交稍慢時就會先記成 UNKNOWN，再查詢結清。結果是安全的，只是 UNKNOWN 的雜訊比較多。另外，被取消的 `to_thread` 執行緒會繼續跑完它的請求，`DemoClient._last` 的節流不是執行緒安全，可能短暫低於 0.25 秒的間隔。建議把 `POLL_TRIES` 和 HTTP 逾時降到 5 秒內，或者把輪詢移到 Supervisor 之外。
- O4：`order_fills` 的 `limit=100`，而且不分頁（`catos/okx_demo.py:423-427`）。超過 100 筆撮合的委託永遠不會 complete，Bot 會停在 `order_not_settled`。這是安全方向，但大張數時會卡住。
- O5：POST 成功後拿到的 ordId 沒有用上（`catos/okx_demo_exchange.py:57`）。OKX 若短暫查不到委託（51603），會一直回報 NOT_FOUND，列狀態維持 SUBMITTING，直到查得到為止。
- O6：除了清倉以外，任何一次暫時性讀取錯誤（`_account`、`closed_candles`）也都會讓 Bot 以 failed 結束，部位不平（`catos/demo_bot.py:344-345`）。這和 README 寫的「停下不平倉」一致，但很容易在無人看管時留下部位。建議讀取類請求做有限次數的重試。
- O7：`flows_known=True` 是直接宣告的，沒有證據（`catos/demo_bot.py:173`）。使用者 2026-11-16 第 3 題說的是「手續費與資金費的逐筆分類不核對」，沒有提到入金、轉帳或重設模擬資金。如果期間有入金，會被當成獲利，遮掉虧損，這和 R1「邊界不明不得視為零」的精神相反。建議請使用者確認這個解讀，或者偵測 OKX 帳單中的轉帳類型，有轉帳就降級。
- O8：OKX 模擬盤的帳本、基準與 order_key 都標成 `local-sim`（`catos/demo_bot.py:164`，實跑的 order_key 開頭是 `"local-sim"`）。新的基準來源 `okx_demo_first_observation_v1` 在 `is_verified_baseline` 裡不限制環境（`catos/risk.py:344-346`），不像 `RISK_PERIOD_SOURCE` 只限 local-sim。manifest 有註明，但接 Live 前應該拆開。
- O9：核准涵蓋模擬盤的起點用字串比較（`catos/demo_bot.py:405`）。目前所有紀錄都用 UTC 的 `isoformat` 寫入，所以沒有出錯；改成先 `fromisoformat` 再比較會比較穩。另外，起點 2026-11-16T00:00Z 比核准摘要文字改成「涵蓋模擬盤」的 commit（2026-11-16 23:50 +08:00，即 15:50Z）早了約 16 小時，這段時間內的核准看到的是「不涵蓋 Demo」，卻會被算進來。正式紀錄裡沒有這種核准，所以沒有實際影響。還有一點：起點只在 `cli_main` 的 `find_demo_approval` 檢查，`DemoBot` 本身不檢查。
- O10：README 第 13 行（「還不能做的：接 OKX 模擬盤……下單」）和第 59 行（「下單尚未接到 CLI 或 Bot」）已經過時。
- O11：AGENTS.md 這次改寫了 INVARIANTS 的 P1 核准範圍與鎖存條文，標成「代理決定、可推翻」。依「先問再做」，INVARIANTS 的任何一條都要由使用者定案。內容方向保守（舊核准不算數；清倉早有「接上交易所後執行」的伏筆），但應該請使用者明確確認。
- O12：授權紀錄的代理決定寫「只做 BTC-USDT-SWAP」，但 `_INST` 接受任何 USDT 永續合約（`catos/okx_demo.py:55`），`first-order --inst` 與 README 也說可以換。Bot 的合約綁在核准上，所以目前影響不大。
- O13：`json.loads` 沒有用 `parse_float=Decimal`（`catos/okx_demo.py:284`）。OKX 實際回的都是字串，但如果回了數字會經過 float。fills 的 `feeCcy` 沒有檢查是不是 USDT。`_report` 接受空 tag（`catos/okx_demo_exchange.py:101`）。
- O14：反手時，如果平倉腿成交後才觸發 Soft，開倉腿會被 ABORTED，`dispatch` 回 None，Bot 停在 `dispatch_returned_nothing`（`catos/demo_bot.py:214-215`）。部位已經是空的，結果是安全的，但比較合理的做法是繼續以空倉跑下去。

## 實際跑過的測試

全部在本機隔離環境下執行：`CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH` 指向 scratchpad 裡的臨時檔，`CATOS_OKX_DEMO_CREDENTIALS` 指向一個不存在的路徑；測試內的 Bot 一律使用假 sender，沒有連網。

| 測試 | 結果 |
| --- | --- |
| `.venv/Scripts/python.exe -m unittest tests.test_okx_demo tests.test_demo_bot -v` | `Ran 35 tests in 4.623s` / `OK` |
| `tests.test_risk tests.test_risk_journal tests.test_risk_period_r1 tests.test_risk_supervisor tests.test_supervisor tests.test_supervisor_reconciliation tests.test_execution_supervisor tests.test_kill_switch tests.test_step2_deployment tests.test_strategy_registry`（`PYTHONPATH=tests`；repo 沒有 `test_strategy_approvals*`，核准相關測試在 `test_step2_deployment`、`test_kill_switch`、`test_demo_bot`） | `Ran 141 tests in 50.374s` / `OK` |
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"` | `Ran 986 tests in 155.150s` / `OK (skipped=11)` |
| 補測 `test_acceptance_extra.py`（7 個情境：回應遺失、51016、分批成交、部分成交後取消、5 秒逾時、K 線補處理、Hard 後重啟） | `Ran 7 tests in 28.333s` / `OK`（最後一項用來證明 D2：測試通過代表行為如預期地重設了基準） |
| 補測 `probe_slow.py`（用 spy 確認走到 `uncertain()`） | `Ran 2 tests` / `OK`，`uncertain()` 被呼叫 4 次 |
| 補測 `probe_flatten_transient.py`（Kill 加一次 503） | `Ran 1 test` / `OK`，輸出 `state: failed`、OKX 部位 1（證明 D1） |

補測腳本都在 `C:\Users\user\AppData\Local\Temp\claude\06a2d6733c105b8e\e959d5a4-c8a1-4a67-830d-e90e8ab84b74\scratchpad\acc\`（`test_acceptance_extra.py`、`probe_slow.py`、`probe_flatten_transient.py`）。它們重用 `tests/test_demo_bot.py` 的 `FakeOkx`，不連網。scratchpad 可能被清掉，所以重現情境也寫在上面各條缺陷裡。

沒跑的：前端的 typecheck、test、build 和 `simulation_integration_test.mjs`。這次 diff 沒有改前端，next-steps 記的是第 1 步時的歷史結果，本次沒有重驗。也沒有連 OKX 模擬盤重跑；實跑證據只讀檔核對。

## 實跑證據核對（只讀）

來源：`…\scratchpad\smoke\out\run\`。

- 事件順序：started → day_basis（台北日 20773，基準 4999.9948357355）→ 3 根預熱後的 5 根 K 線，第 5 根判 `RESERVED_SIMULATION/exposure_reserved` → 買單成交（23:45:06）→ kill_switch（23:49:18）→ flatten → risk FLAT `manual_kill` → 清倉成交（23:49:21）→ flatten_done → stopped。順序合理。
- 帳本 `execution_orders` 有兩列，都是 `FILLED`、`settled=1`。買單 ordId 4105099728749056000，`reduceOnly=false`，成交 12 筆、合計 1.00。清倉單 ordId 4105108293048061952，`reduceOnly=true`、賣 1 張，成交 1 筆。`ownership.position=0`，`unknown_count=0`。
- `status.json`：`stopped`，原因 `manual_kill:kill-switch-50837ff5…`，position 0。
- 隔離的 `test-kill.jsonl` 只有一筆 engage，沒有 clear。
