# CatOS 獨立驗收（第二意見）：2026-11-18 的 6 個少見情況修正（commit b9e406a4）

- 驗收標的：`b9e406a4`（`fix: 修 11-18 審查留下的 6 個少見情況，並記下保底停損觸發實測`）
- 對照版本：`b9e406a4~1`（修補前）、`b9e406a4`（受驗目標）與目前 `HEAD` `3064346c`（驗收過程中主線剛合入的 D1／O1／O6 修補）
- 驗收時間：2026-11-18
- 驗收角色：唯讀獨立驗收（未修改 `catos/`、`tests/` 或 `outputs/`）

---

## 一、結論

- **對目標 commit `b9e406a4` 的驗收結論：`FAIL`**
  - 阻斷缺陷 **D1**：第 6 項修改讓 Bot 在接續（resume）遇到新 `--disaster-stop` 比例暫時無法安裝時繼續運行，並預設由 `ProtectionJournal.blocked()` 擋住加倉。然而當上一次 run 沒有停損（0%）、或平倉／反手後 OKX 於空倉自動撤除舊停損（已於模擬盤實測確認 `auto_cancel_on_flat: true`），帳本 `desired()` 與 `active` 皆為 `None`，`blocked()` 會回傳 `False`，導致策略在「完全沒有保底停損」的情況下重新開出反向部位；另外從 `10%` 改為 `5%` 時也能以舊停損（仍覆蓋原倉位）通過同向加倉檢查。此缺陷已以「無 Mock、legacy schema 4 帳本缺成本基準」及「0% -> 10%／10% -> 5%」兩種情境實際重現。同時 `b9e406a4` 新增的第 6 項測試在修正前程式碼（`b9e406a4~1`）上竟然直接通過（**O2**）。
- **對目前主線 `HEAD` `3064346c` 的窄範圍順道重驗結果：**
  - 主線於 `3064346c`（14:34 提交）已將接續時安裝新比例失敗改為比照全新啟動停機（`protection_config_failed`），並補上 `altered_stop` 在 `state == "live"` 時檢查固定張數 `sz`（O1 主要缺口）及無法讀取舊帳本時紀錄 `previous_run_unreadable`（原漏報行為）。
  - 重跑本輪獨立腳本驗證：**D1 在 `3064346c` 已確實修好**（無 Mock schema 4 情境與 Mock 0%->10%、10%->5% 皆立即停機且零加倉）。
  - 但在針對 `_protect()` 與 `_catch_up_bar()` 的邊界探測中，發現一項**跨 `b9e406a4~1`、`b9e406a4` 與 `3064346c` 皆存在的既有潛在故障路徑（O4／PROBE X1・X2）**：若上一輪停下時留有 `pending` 保底停損請求且停機期間缺漏至少 2 根 K 線，`_protect()` 可能在 `execution._dirty()` 把 `supervisor.health` 設為 `"RECONCILING"` 後跳過 `_reconcile()`，使緊接著執行的 `_catch_up_bar()` 直接觸發 `SupervisorUnavailable: synthetic reconciliation required before processing` 而以 `state="failed"` 異常終止；此外 `altered_stop` 對 `state="pause"` 仍回傳 `False`（**O1**）。若 `3064346c` 要進入後續驗收收尾，建議評估並一併處理 **O1／O4**。

---

## 二、驗收方法與環境隔離

- 依照規則不連線 OKX、不讀取真實金鑰檔、不執行 `strategy approve/revoke`、`demo rearm`、`kill clear`，不動用 `outputs/` 或 `~/.catos`。
- 所有測試與重現腳本皆透過暫存 `HOME`／`USERPROFILE` 及隔離的 `CATOS_STRATEGY_APPROVALS`、`CATOS_KILL_SWITCH`、`CATOS_STRATEGY_HOME`、帳本與帳號鎖目錄執行，結束後均檢查暫存家目錄項目數為 `0`（`HOME_CONTENTS: 0`）。
- 唯讀快照提取：`b9e406a4~1` 置於 `%TEMP%\catos_prev_b9e406a4`，`b9e406a4` 置於 `%TEMP%\catos_commit_b9e406a4`，與目前工作區 `3064346c` 並排對照執行。
- Scratch 驗證程式置於 `reports/rare-cases-acceptance-20261118/scratch/`：
  1. `verify_rare_cases.py`（17 個情境與安全探針，涵蓋第 1–6 項、第 2 項延伸、安全不變量與 D1/O1 探針）
  2. `compare_prev_vs_head.py`（以同一套 7 組情境同時跑在 `b9e406a4~1`、`b9e406a4` 與 `3064346c`）
  3. `probe_unmocked_d1.py`（不用任何 `configure_protection` mock，以降級至 `PRAGMA user_version=4` 的舊版帳本重現 D1）
  4. `verify_uncommitted_recheck.py`（針對 `3064346c` 修正與 `PROBE X1`／`PROBE X2` 邊界路徑的 6 項獨立複驗）

---

## 三、逐項情況驗證（6 個少見情況＋第 2 項延伸）

### 情況 1：平倉單結果不明時停下、重開時 OKX 已空倉（`_unsettled_flat_run`、`--new-run`、`previous_run_unsettled`）

- **程式判讀**：
  - `DemoBot.run`（`catos/demo_bot.py:700-706` at `3064346c`）在 OKX 空倉（`facts["position"] == 0`）且未帶 `--new-run` 時，會呼叫 `_unsettled_flat_run(facts)`（`748-791`；`b9e406a4` 為 `754-794`）。
  - `_unsettled_flat_run` 以 `?mode=ro` 唯讀開啟舊帳本（支援讀取未 checkpoint 的 WAL 變更），檢查 `execution_orders WHERE settled=0`；若有未結清委託，再依序檢驗 `_resumable_run(facts)`（授權、設定、風控門檻）、`status.json["last_bar_open_ms"]` 及停機時間差 `>= RESUME_CANDLES - 1`（`788`，`RESUME_CANDLES = 299`，即 `>= 298`）。不能接續時不改動舊帳本，將原因記入 `self.start_notes` 並於新 run 開頭寫入 `previous_run_unsettled` 事件（`726-727`）。
  - 啟動參數 `--new-run`（`catos/demo_bot.py:1162-1163, 1181-1182`）與 `START_HINTS["resume_unresolved_orders"]`（`1122-1123`）可強制開新 run，保留舊帳本不動。
- **前後對照與實測**：
  - `compare_prev_vs_head.py`（`1_flat_unsettled_resume`）：
    - `b9e406a4~1`（修補前）：`run2_created: true`、`old_ledger_settled: [1, 0]`、`old_ledger_pos: "1"`（平倉單永遠卡在 `settled=0`）。
    - `b9e406a4`（修補後）：`run2_created: false`、`old_ledger_settled: [1, 1, 1]`、`old_ledger_pos: "0"`、`stop2: "manual_kill:..."`。
  - `verify_rare_cases.py`（對 `b9e406a4` 快照執行）：
    - `test_1a_unsettled_close_with_disaster_stop_resumes_and_settles`（含 `--disaster-stop 10%` 與 `auto_cancel_on_flat=True`）：舊委託全數結清（`settled=1`、`ownership.position='0'`、`reservations=0`）、等待超時的開倉腿結束為 `ABORTED`、`fills.json` 記錄「接續時補查」、未重送任何下單。
    - `test_1b_unsettled_kill_flatten_order_resumes_and_respects_flat_latch`：Kill 清倉單結果不明停機後空倉重開，接續查明成交並因舊帳本 `mode == "FLAT"` 正確停於 `risk_flat:...`。
    - `test_1c`／`test_1c2`：真實經過 `cli_main(["--profile", ..., "--new-run"])` 解析並傳入 `DemoBot(..., new_run=True)`；確認 `--new-run` 於 `facts["position"] != 0` 時完全不會跳過 `_resumable_run`，且帳戶級 Soft 鎖存仍在新 run 開頭載入。
    - `test_1d`／`test_1e`／`test_1f`：授權異動與停機過久（298 根邊界）皆於新 run 記下 `previous_run_unsettled`；OKX 空倉卻查到舊平倉單為 `CANCELED` 時正確停於 `resume_position_mismatch` 不錯記空倉；未 checkpoint 的 SQLite WAL 仍可被 `ro` URI 讀出未結清數。
- **評估**：情況 1 實作成立且邊界堅固；惟仍有兩個次要觀察見 **O5**（讀不到帳本靜默回傳已於 `3064346c` 修掉、`>= 298` 邊界與 `risk_flat` 缺提示）。

---

### 情況 2 與延伸項：決策到送單之間風控變更（epoch 改變），以及反手平倉腿在 Soft／epoch 變動下照送

- **程式判讀**：
  - `ExecutionJournal.prepare`（`catos/execution.py:117-123`）新增：當 `bool(row["reduce_only"]) and verdict.reduce_only and state.mode != "FLAT"` 時，允許沿用不同 epoch 的舊減倉意圖送出（`epoch_ok` 放寬），但加倉（`reduce_only=False`）、`FLAT` 模式、數量不一致、未過風控 `verdict.accepted` 或 `self.unresolved()` 有在途／不明單時仍一律擋下。
  - `ExecutionJournal.prepare_reversal_close`（`catos/execution.py:190-194`）延伸修改：`((row["eligible"] and row["epoch"] == state.epoch) or state.mode != "FLAT")`，只要目前帳本非 `FLAT`、目標與持倉反向（`position * D(row["target"]) < 0`）、未超時、通過風控檢核 `verdict.accepted` 且 `verdict.reduce_only and verdict.quantity == -position`、無 `unresolved()` 委託，即使在決策後因 epoch 變動或 Soft 鎖住使反手整筆失去 `eligible`，仍抽出平倉腿以 `reduceOnly=True`、剛好 `-position` 送出；第二腿開倉則於 `DemoBot._execute`（`catos/demo_bot.py:532-536`）呼叫 `dispatch` 回傳 `None`（當 `closed_first=True`）時記錄「反手的開倉腿被風控擋下，維持空倉繼續跑」並平倉續跑。
- **前後對照與實測**：
  - `compare_prev_vs_head.py`（`2a_reduction_epoch_change`）：
    - `b9e406a4~1`：`epoch_bumped: true, prepared: false, order_state: "ABORTED"`。
    - `b9e406a4`：`epoch_bumped: true, prepared: true, order_state: "SUBMITTING"`。
  - `compare_prev_vs_head.py`（`2b_reversal_close_under_soft`）：
    - `b9e406a4~1`：`stop_reason: "dispatch_returned_nothing", posts: [["buy", false]], final_pos: "1"`（平倉腿被作廢，帶著多單停機）。
    - `b9e406a4`：`stop_reason: "manual_kill:...", posts: [["buy", false], ["sell", true]], final_pos: "0"`（平倉腿照送，開倉腿被擋）。
  - `verify_rare_cases.py`：`test_2a_ordinary_reduction_survives_epoch_change_in_bot`（真正透過 `DemoBot` 觸發普通減倉時 epoch 變更）、`test_2b_reversal_close_leg_survives_latch_soft_and_degraded`（同時驗證 `supervisor.latch("soft_loss")` 與 `degraded` 風控降級）。
- **評估**：情況 2 與第 2 項延伸均成立，完全符合 P3b「合法減倉始終允許」。

---

### 情況 3：條件單在 OKX 被改成限價或部分張數（`altered_stop`）

- **程式判讀**：
  - `catos/okx_demo.py:512-521`（`_algo_row`）擷取 `sl_ord_px`、`close_fraction`、`sz`。
  - `b9e406a4` 版的 `altered_stop`（`catos/okx_demo.py:253-260` at `b9e406a4`）：僅檢查 `row.get("sl_ord_px", "") not in ("", "-1") or row.get("close_fraction", "") not in ("", "1")`，刻意忽略 `sz`（理由為實測停損觸發成 `effective` 後 OKX 會回填 `sz`）。
  - `catos/okx_demo_exchange.py:197-198` 回報 `complete = order["state"] == "live" and not altered_stop(order)`；`catos/demo_bot.py:353-365` 在 `_reconcile` 偵測 `altered_stop(row)` 時寫入 `protection_altered` 事件並呼叫 `protection_verify` 將條件單設為未確認、禁止加倉。
- **前後對照與獨立探針**：
  - `compare_prev_vs_head.py`（`3_altered_stop`，限價 `slOrdPx="94"`）：
    - `b9e406a4~1`：`has_protection_altered: false, posts: [["buy", false], ["sell", true], ["sell", false], ["buy", true]]`（未偵測改價，第 5 根仍反手開空）。
    - `b9e406a4`：`has_protection_altered: true, posts: [["buy", false], ["sell", true]]`（記下 `protection_altered`，平倉後擋下空單開倉）。
  - **在 `b9e406a4` 上發現的漏判探針（`verify_rare_cases.py` `test_3b`）**：
    - `[PROBE 3b-bot] fixed sz='0.5' closeFraction='' -> altered_events=[], posts=[('buy', False), ('sell', True), ('sell', False), ('buy', True)]`：若 `live` 條件單維持 `slOrdPx="-1"` 但將全倉比例改為固定部分張數 `sz="0.5"`、`closeFraction=""`，`b9e406a4` 的 `altered_stop` 回傳 `False`，導致無警報且反手照常開空！
  - **在 `3064346c` 的修補與重驗**：
    - `3064346c` 在 `catos/okx_demo.py:261-262` 新增 `or (row.get("state") == "live" and row.get("sz", "") not in ("", "0"))`。對 `state=="live"` 已修正，但 `state=="pause"` 仍回傳 `False`（見 **O1**）。

---

### 情況 4：只改觸發來源（價格不變）須等到來源一致才算完成

- **程式判讀**：
  - `catos/okx_demo_exchange.py:158-159` 將原本只比對 `report.price == wanted` 擴充為 `and report.trigger == payload["slTriggerPxType"]`。
- **前後對照與實測**：
  - `compare_prev_vs_head.py`（`4_amend_source_alone`）：
    - `b9e406a4~1`：`amend_count: 2`（第一次查詢時價格已一致但 `slTriggerPxType` 仍顯示舊值 `"last"`，舊碼誤判已確認、下一輪又發現不符再重送第 2 次 `amend-algos`）。
    - `b9e406a4`：`amend_count: 1, alerts: ["protection_mismatch"], final_trigger: "mark"`（第一次查詢維持 `unconfirmed`，等下輪 OKX 反映 `"mark"` 後確認完成）。
  - `verify_rare_cases.py`（`test_4a_source_only_amend_waits_and_excess_lag_stays_blocked`）：當延遲超過 `amend_source_lag` 尚未一致時，`protection` 保持未確認並成功阻擋第 5 根開倉腿（只平倉、不開反手空單）。
- **評估**：情況 4 修正完全成立。

---

### 情況 5：OKX 回空的觸發來源時以預設 `"last"` 解讀並改回 `"mark"`

- **程式判讀**：
  - `catos/okx_demo_exchange.py:193`：`trigger = order["sl_trigger_px_type"] or "last"`。
  - `catos/demo_bot.py:358`：`row["sl_trigger_px_type"] or "last"`。
- **前後對照與實測**：
  - `compare_prev_vs_head.py`（`5_empty_trigger_source`）：
    - `b9e406a4~1`：`state: "failed", stop_reason: "ProtocolError: invalid confirmed protection", amend_count: 0, final_trigger: ""`（`ProtectionReport.wire` 驗證失敗使 Bot 當機）。
    - `b9e406a4`：`state: "stopped", stop_reason: "manual_kill:...", amend_count: 1, final_trigger: "mark"`。
  - `verify_rare_cases.py`（`test_5a_empty_and_missing_trigger_source`）：額外驗證 `slTriggerPxType=""` 與欄位完全缺漏（`None`）兩種情況，兩者皆自動重掛為 `"mark"`，沒有發生例外。
- **評估**：情況 5 修正成立（惟 OKX 是否真回空字串仍標「待驗證」）。

---

### 情況 6（D1 所在）：接續時新 `--disaster-stop` 比例裝不上

- **程式判讀與實作缺陷（`b9e406a4` FAIL）**：
  - 在 `b9e406a4` 的 `catos/demo_bot.py:386-430`，`_configure_protection(strict=False)` 若碰到 `SupervisorUnavailable` 只寫一筆 `protection_wait` 後直接 `return`（假定註解「a changed position is not covered, so the journal keeps increases blocked」）。
  - 但 `ProtectionJournal.blocked()`（`catos/protection.py:121-133`）檢查的是 DB 中**舊 run 留下的** `s['config']['ratio']` 與 `s['active']`：
    1. 若舊 run 為 `0%`（無停損）而新啟動要求 `10%` 但安裝失敗，`s['config']['ratio']` 仍為 `0`、`desired()` 為 `None`、`blocked()` 永遠回傳 `False` -> 策略可無停損開倉／加倉。
    2. 若舊 run 為 `10%` 停損（`active` 覆蓋 `position=1`）、新啟動要求 `5%` 但安裝失敗：
       - 若策略平倉／反手且 OKX 於空倉自動撤除舊單（`auto_cancel_on_flat=True`），`active` 變成 `None`，同時 `desired()` 為 `None`，`blocked()` 在空倉時成為 `False`，反手開倉腿竟可通過並開出**毫無保底停損**的反向部位；
       - 若策略同向加倉（`position 1 -> 2`）時在多單進場前當根 K 線：舊停損仍「存在」，直到成交前雖覆蓋 `position=1`，`blocked()` 也是 `False`，導致加倉後新張數以舊 10%（且等待下一根／下一分鐘才檢查或依舊比例移動）執行。
- **在 `b9e406a4` 的重現輸出**：
  1. `compare_prev_vs_head.py`（`6_resume_uninstalled_ratio`）：證明 `b9e406a4` 確實在 `94.5` 掛著時不會用舊比例送 `amend-algos`/`cancel-algos`（`b9e406a4~1` 會送 `[["amend-algos", "94.5"], ["cancel-algos", null]]`；`b9e406a4` 為 `[]`），但這只是**沒有平倉且未開倉前**的片段表象。
  2. `verify_rare_cases.py` 探針（對 `b9e406a4` 快照執行，`task-237`）：
     - `[PROBE 6b-1: 0%->10% uninstalled] posts=[('buy', '1', False), ('sell', '1', True), ('sell', '1', False), ('buy', '1', True)], algos=0`（0% 接續 10% 安裝失敗，全無停損卻照樣反手開空）。
     - `[PROBE 6b-2: 10%->5% uninstalled scale-in] posts=[('buy', '1', False), ('buy', '1', False), ('sell', '2', True)], algos=['94.5']`（10% 接續 5% 安裝失敗，照樣同向加倉到 2 張）。
  3. **無 Mock 實戰重現**（`probe_unmocked_d1.py` 對 `b9e406a4` 快照執行）：
     將 0% 運行過並開多 1 張的 run1 SQLite DB 降級為 `PRAGMA user_version=4`（缺乏成本基準，完全符合實際升級過渡情景，不使用任何 `mock`），以 `--disaster-stop 10%` 接續 run2：
     ```text
     NO-MOCK D1 RESULT:
       posts: [('buy', '1', False), ('buy', '1', False), ('sell', '2', True)]
       algos: {}
       protection_wait events: 12 [{'kind': 'protection_wait', 'reason': 'configure:verified cost baseline required before enabling protection', ...}, ...]
       stop_reason: manual_kill:kill-switch-3ae4fad83e883e8c4b1c8649997933b4
     ```
     Bot 連續紀錄 12 次 `protection_wait`（安裝 10% 失敗），OKX 上 `algos: {}`，第 5 根仍然多加倉 1 張（總部位 2 張，完全沒有保底停損）。
- **在 `3064346c` 的修正與重驗**：
  - `catos/demo_bot.py:386-399, 413-423` 已取消 `strict=False` 容錯，只要接續時沒有在途／不確定／已觸發的遺留條件單（或該遺留單剛被查詢結束），安裝新比例失敗一律拋出 `BotStopped("protection_config_failed:...")` 立即停機，保留原部位與 OKX 已確認的條件單。
  - 重跑 `probe_unmocked_d1.py` 於 `3064346c`：
    ```text
    NO-MOCK D1 RESULT:
      posts: [('buy', '1', False)]
      algos: {}
      protection_wait events: 0 []
      stop_reason: protection_config_failed:verified cost baseline required before enabling protection
    ```
  - 重跑 `verify_uncommitted_recheck.py` 的 `test_d1_fix_0pct_to_10pct_and_10pct_to_5pct_stop_cleanly` 與 `test_d1_fix_10pct_to_5pct_scale_in_stops_before_scale_in`（皆已覆蓋 `3064346c`）：兩者皆立即停於 `protection_config_failed:synthetic`，`posts` 僅保留原先開多 1 張，零新增開倉／加倉，原 `94.5` 停損完整保留。

---

## 四、新風險重點稽核

1. **會不會讓加倉在不該送的時候送出／epoch 放寬限制／FLAT・Hard・Kill 清倉／不穿越零點**
   - 核對 `catos/execution.py:117-123, 190-194`：
     - `prepare`：`epoch_ok` 放寬明確以 `bool(row["reduce_only"]) and verdict.reduce_only and state.mode != "FLAT"` 為必要條件。普通加倉（`reduce_only=False`）仍要求 `row["epoch"] == state.epoch` 且 `not self.j.protection.blocked(bot_id)`。
     - `prepare_reversal_close`：明確要求 `position * D(row["target"]) < 0`、`state.mode != "FLAT"`、`verdict.accepted and verdict.reduce_only and verdict.quantity == -position`，只送剛好平到 0 的張數，絕不會穿越零點。
     - `FLAT`／Hard／Kill：兩個函式皆嚴格檢查 `state.mode != "FLAT"`，進入 `FLAT` 後僅走 `flatten()`（`catos/supervisor.py:750-767`、`catos/demo_bot.py:591-608`）清倉路徑。
   - 實測驗證：`verify_rare_cases.py::RareCase2Tests.test_2c_safety_invariants_increase_flat_cross_zero_unknown` 驗證 (a) epoch 改變後普通加倉仍遭作廢；(b) `FLAT` 狀態下舊減倉意圖被拒絕於 `prepare`/`prepare_reversal_close` 之外並改走 `flatten()`；(c) 策略翻轉企圖穿越零點時，`prepare_reversal_close` 僅核發 `-position` 且要求 `reduceOnly=True`。
2. **`UNKNOWN` 不能盲目重送，也不能盲目釋放額度**
   - 核對 `catos/execution.py:123, 194` 皆保留 `not self.unresolved()`（於 `prepare` 針對減倉也仍要檢查「在 `test_1b`／`test_2c` 無衝突減倉時才放行」，於 `prepare_reversal_close` 一律要求 `not self.unresolved()`；普通減倉若另有 `UNKNOWN` 減倉單，受 `Journal` 與 `reduction_conflict` 限制）。
   - `DemoBot._recover`（`catos/demo_bot.py:933-953`）只執行 `supervisor.query_order(...)` 查詢，若超過 `RESUME_QUERY_ROUNDS` 仍未結清則停於 `resume_unresolved_orders:...`，完全不盲目重送或釋放額度。
   - 實測：`test_1a` 中 `UNKNOWN` 平倉單僅被補查結清，隨後超時開倉腿終止於 `ABORTED`；`test_2c` 驗證存在未結清訂單時 `prepare_reversal_close` 與加倉皆不放行新單。
3. **接續舊 run 的條件（`_unsettled_flat_run`）及 `--new-run` 是否會跳過舊部位或鎖存**
   - 舊部位：`catos/demo_bot.py:697-706` 只有在 `facts["position"] != 0` 時直接進 `_resumable_run(facts)`，完全無視 `--new-run` 旗標（`test_1c` 已實測非空倉帶 `new_run=True` 仍受 `_resumable_run` 與授權變更拒絕保護）。
   - Hard／Kill-Switch：存在獨立總開關檔案（`kill_switch`），`run()` 啟動即檢查，不受 `--new-run` 跳過。
   - Soft 鎖存：帳號級紀錄檔（`~/.catos/okx-demo-accounts/<uid>.json`）於 `DemoBot.run()` line 732（所有新開與接續 run）皆會讀取並在 `soft_latched=True` 時立即 `supervisor.latch("soft_loss")`（`test_1c` 已證實）。惟獨當上一輪觸發 Soft 時**恰好寫帳戶檔失敗**（帳戶檔仍是 `soft_latched: false`，Soft 只留在舊 run 的 SQLite 裡），一般接續路徑會有 `demo_bot.py:1000-1005` 從舊帳本補回帳戶檔；若使用者主動帶 `--new-run` 強制重開，新 run 不讀舊 SQLite，即不繼承該未寫入帳戶檔的 Soft 鎖存（屬帳戶檔寫入失敗時的既有架構取捨，非本次新增，在 `test_resume_without_a_rearm_keeps_the_ledger_soft_latch` 已有考量一般接續情形）。
   - 另觀察：若舊 run 在 `FLAT` 鎖住下仍有未結清平倉單，空倉重開接續 `_recover` 查明空倉後，`_resume` line 986 會因 `state.mode == "FLAT"` 執行 `_flatten` 並停於 `risk_flat:...`（`test_1b` 實測如此）；`START_HINTS` 目前沒有 `risk_flat` 對應說明（見 **O5**）。
4. **`altered_stop` 誤判與漏判**
   - 詳見下方 **O1**。
5. **新比例裝不上時是否無停損仍能加倉**
   - `b9e406a4` **會**（**D1**）；`3064346c` 已改為直接停機（`protection_config_failed`）而解決。

---

## 五、測試本身漏洞檢查

對 `b9e406a4` 新增的 `tests/test_demo_bot.py::RareCaseTests`（9 項）與 `tests/test_execution.py::test_a_reduction_held_across_a_restart_still_goes_out`（1 項）檢視如下（總計見 **O2**）：

1. **第 6 項測試在修正前版本（`b9e406a4~1`）竟然通過**（實測佐證）：
   將 `b9e406a4:tests/test_demo_bot.py` 中的 `RareCaseTests` 完整執行於 `b9e406a4~1` 快照（僅對 `DemoBot.__init__` shim 接受 `new_run=False`，`task-269`）：
   ```text
   Ran 9 tests in 36.634s
   FAILED (failures=7, errors=1)
   test_resume_never_uses_the_old_ratio_while_the_new_one_is_not_installed ... ok
   ```
   其餘 8 個測試皆如預期 fail/error，唯獨第 6 項在修補前的舊碼上通過！原因是該測試中舊停損價 `94.5` 本來就與舊 10% 算出的 `desired` 一致、又沒有加倉成交或改價，舊碼本來就不會送出 `order-algo` 或 `amend-algos`；到第 5 根 K 線反手時該測試未打開 `FakeOkx.auto_cancel_on_flat`，且只檢查 `names not in ("order-algo", "amend-algos")`，未斷言 `fake.posts` 不該開出新單，也完全沒測 `0% -> 10%` 或同向加倉，因而漏過 **D1**。（註：`3064346c` 已將此測試改為 `test_resume_stops_when_the_new_ratio_cannot_be_installed`，開啟 `fake.auto_cancel_on_flat = True` 並斷言 `stop_reason` 與 `len(fake.posts) == 1`。）
2. **其餘測試斷言偏窄處**：
   - 第 1 項：`test_a_flat_restart_settles_the_stopped_runs_unknown_order` 未檢查舊帳本 SQLite 的 `execution_orders.settled=1`、`ownership.position='0'`、`reservations=0`，亦未將 `--disaster-stop > 0` 與平倉後自動撤單同場驗證；`test_new_run_leaves_the_unsettled_run_as_it_is` 未直接透過 `cli_main(["--new-run", ...])` 測試 CLI 旗標解析，亦未斷言舊 SQLite 仍維持 `settled=0`。
   - 第 2 項：`test_a_soft_latch_before_the_reversal_still_closes_the_long` 以 `bot.supervisor.risk_state = risk.halt(...)` 直接寫內部屬性（跳過 `supervisor.latch("soft_loss")` 與持久化通道），且未在 `DemoBot` 端對端測試「普通減倉（非反手）跨 epoch」與「`FLAT` 攔截」。
   - 第 3 項：`test_a_stop_changed_to_a_limit_price_blocks_increases` 只測 `slOrdPx="94"`，未在 Bot 迴圈測 `closeFraction="0.5"`、固定 `sz`、事件只記一次與使用者在 OKX 撤單後的自癒重掛。
   - 第 5 項：`test_an_empty_trigger_source_is_amended_not_a_crash` 只測 `slTriggerPxType=""`，未測整欄缺漏（`None`）。
   - `test_execution.py:372`（`test_a_reduction_held_across_a_restart_still_goes_out`）：在單元層有效驗證重啟後 `epoch` 遞增且合法減倉可透過 `ExecutionJournal.prepare` 送出，行為無誤。

---

## 六、缺陷與觀察清單

### 缺陷（必須修才能過）

- **D1〔阻斷，`b9e406a4` FAIL；已於 `3064346c` 修復〕：接續時新保底停損比例裝不上仍放行無保護開倉或以舊保護加倉**
  - **位置**：`b9e406a4` 的 `catos/demo_bot.py:386-430`（`3064346c` 已修改為 `catos/demo_bot.py:386-399, 413-423`）與 `catos/protection.py:121-133`。
  - **原因**：接續時 `strict=False` 吞掉 `SupervisorUnavailable`，`ProtectionJournal.blocked()` 仍只依賴帳本儲存的舊設定（`0%` 或平倉後 `active=None` 時 `blocked() == False`）。
  - **重現步驟**：
    1. （無 Mock）執行 `.venv\Scripts\python.exe reports\rare-cases-acceptance-20261118\scratch\probe_unmocked_d1.py`（針對 `b9e406a4` 快照或將 schema 4 舊帳本多單以 `--disaster-stop 10%` 接續）。
    2. 觀察 `b9e406a4` 下輸出 `posts: [('buy', '1', False), ('buy', '1', False), ('sell', '2', True)]`、`algos: {}`、`protection_wait events: 12`。
    3. 或對 `b9e406a4` 執行 `verify_rare_cases.py`（`CATOS_SNAPSHOT_DIR=%TEMP%\catos_commit_b9e406a4`），觀察 `[PROBE 6b-1]` 與 `[PROBE 6b-2]` 在無停損／未升級停損下照常反手開空與同向加倉。
  - **重驗狀態**：在 `3064346c` 重跑 `probe_unmocked_d1.py` 與 `verify_uncommitted_recheck.py`，均正確於接續檢查階段以 `protection_config_failed` 停機且零加倉。

### 觀察（建議與注意事項）

- **O1（`altered_stop` 對 `state="pause"` 與小數格式，以及 `b9e406a4` 漏判固定張數）**
  - **位置**：`catos/okx_demo.py:253-262`（`3064346c`）；`catos/okx_demo.py:253-260`（`b9e406a4`）。
  - **說明**：`b9e406a4` 漏判固定 `sz`（已見 `PROBE 3b-bot`）；`3064346c` 加入 `row.get("state") == "live" and row.get("sz", "") not in ("", "0")` 修補了 `live` 狀態，但未涵蓋 `state == "pause"`（`[RECHECK O1 pause+sz] altered=False`；雖在 `okx_demo_exchange.py:198` 會因 `state != "live"` 判為未確認，但 `_reconcile` 不會寫 `protection_altered`），且對 `close_fraction` 與 `sl_ord_px` 採嚴格字串比對（`"1.0"` 會被視為被改、`FakeOkx` 等測試省略欄位回傳空字串不計）。
  - **重現**：執行 `verify_uncommitted_recheck.py::test_o1_altered_stop_cases_including_pause` 可見 `altered_stop({"state": "pause", "sl_ord_px": "-1", "close_fraction": "", "sz": "0.5"}) -> False`。

- **O2（`b9e406a4` 測試覆蓋不足與第 6 項測試在舊碼通過）**
  - **位置**：`tests/test_demo_bot.py:1144-1292`。
  - **說明**：詳見「五、測試本身漏洞檢查」；在 `b9e406a4~1` 上直接跑 `b9e406a4` 的 9 項 `RareCaseTests` 只有第 6 項意外通過。`3064346c` 已修復第 6 項測試本身，但第 1、2、3、5 項的前述斷言窄度（CLI `--new-run` 解析、SQLite 欄位、Bot 普通減倉與 `FLAT`、使用者撤單後重掛等）仍建議補強（本輪獨立測試 `verify_rare_cases.py` 的 `test_1a`–`test_5a` 已示範可驗證作法）。

- **O3（被改過的條件單於平倉後不會自動撤銷與告警文案略失真）**
  - **位置**：`catos/demo_bot.py:353-370, 402`、`catos/protection.py:191-193, 202-203`。
  - **說明**：使用者改限價後，`protection_verify` 將該條件單留在 `uncertain=True`／`pending=algo_query`；平倉成空倉後因 `prepare()` 優先查 `s['pending']`，不再送 `cancel-algos`，必須照 `protection_altered` 事件提示「請到 OKX 網頁撤掉這張條件單」。若使用者沒撤且停止後空倉重開，`run()` 第 694 行會停在 `contract_not_flat_at_start`（符合安全不領養原則）；惟同時寫出的 `protection_alert` 沿用 `ALERTS["protection_unconfirmed"]`（「OKX 沒回應或還查不到」），於單子明明存在且已記 `protection_altered` 時文字略不精準。

- **O4（跨版本既有潛在故障：`pending` 保護接續＋缺漏 >= 2 根 K 線時 `_protect()` 跳過對帳導致 `_catch_up_bar()` 以 `SupervisorUnavailable` 當機 — PROBE X1 / PROBE X2）**
  - **位置**：`catos/demo_bot.py:413-443, 1017-1022`（`3064346c`）、`catos/protection.py:274-275`、`catos/execution.py:48-51`、`catos/supervisor.py:927-928`。
  - **原因**：
    1. 路徑 X1：上一輪停在 `pending` `algo_create`（`before["active"] is None`），停機期間缺漏 `>= 2` 根 K 線後改以 `--disaster-stop 0` 接續。`_protect` 第 419 行確認建立（`execution._dirty` 將 `supervisor.health` 設為 `"RECONCILING"`），接著第 422–423 行切換 `0%` 並確認 `algo_cancel`（`active` 回到 `None`）。第 439 行只比對端點 `(active is None) != (old is None)`，兩者皆 `True`，故跳過第 442 行 `_reconcile()`，使 `supervisor.health` 維持 `"RECONCILING"`。
    2. 路徑 X2：上一輪停在 `pending` `algo_cancel`（`before["active"]` 非空），缺漏 `>= 2` 根 K 線後以 `--disaster-stop 5%` 接續。第 419 行確認撤單使 `active` 變 `None`（`_dirty` 設為 `"RECONCILING"`），第 422 行安裝 `5%`，第 423 行嘗試新建停損即在 `protection.prepare()`（`protection.py:213`）因尚未對帳而拋出 `SupervisorUnavailable("fresh attributed position required for protection mutation")`；第 424 行攔截例外並直接 `return facts`，同樣留下 `supervisor.health == "RECONCILING"`。
    3. 隨後 `_resume()` 第 1019 行進入 `missed[:-1]` 呼叫 `_catch_up_bar()` -> `supervisor.process_bar()`，直接觸發 `supervisor.py:927-928` 的 `SupervisorUnavailable: synthetic reconciliation required before processing`，使 Bot 在未處理 K 線下以 `state="failed"` 終止（經 `task-300` 對比，`b9e406a4~1`、`b9e406a4`、`3064346c` 皆會重現）。
  - **重現步驟**：在隔離暫存家目錄執行 `.venv\Scripts\python.exe reports\rare-cases-acceptance-20261118\scratch\verify_uncommitted_recheck.py`，觀察 `[PROBE X1]` 與 `[PROBE X2]` 兩者皆印出 `state=failed, stop_reason=SupervisorUnavailable: synthetic reconciliation required before processing`。
  - **建議修法**：在 `_protect()` 離場前（包含 `except SupervisorUnavailable` 之後，只要狀態非 `triggered`）檢查 `self.supervisor.health == "RECONCILING"`（或由 `protection_step` 後確認是否曾經歷 `dirty`）即強制先做 `_reconcile(facts, "protection", flattening=flattening)` 再返回，或於 `_catch_up_bar()` 之前確保已經對帳就緒。

- **O5（`_unsettled_flat_run` 邊界與啟動檢查細節）**
  - **位置**：`catos/demo_bot.py:94, 694, 748-791, 986, 1120-1131`。
  - **說明**：
    1. 第 788 行 `>= RESUME_CANDLES - 1`（`298`）以 `status.json["last_bar_open_ms"]` 估算差距，較 `_resume`（`:1011-1016`）提早 1–2 根拒絕（偏保守）；且 `status.json` 在 `_bar` 後才更新，若於補 K 線過程停機可能只寫出 `resume_last_bar_unreadable` 開新 run。
    2. 若上一輪平倉但 OKX 尚餘 Bot 原先所掛未撤的條件單（`facts["position"] == 0 and facts["algos"]`），`run()` 第 694 行直接於 `contract_not_flat_at_start` 停機，不會走入 `_unsettled_flat_run`。
    3. 上一輪在 `FLAT` 鎖住下留有未結清委託，接續平倉查核後 `_resume` 第 986 行會因 `state.mode == "FLAT"` 停於 `risk_flat:...`，`START_HINTS` 尚未收錄 `risk_flat` 提示。
    4. 舊帳本無法讀取時在 `b9e406a4` 原為靜默回傳 `None`，`3064346c` 已補上 `previous_run_unsettled` 事件（`reason="previous_run_unreadable"`，本輪以 `verify_uncommitted_recheck.py::test_o6_unreadable_ledger_logs_event` 驗證通過）。

- **O6（第三方平台待驗證清單）**
  - 下列 OKX Demo API 實際回應行為於本輪無網實測中未接觸真實交易所，皆標「**待驗證**」：
    1. OKX `GET /api/v5/trade/order-algo` 或 `orders-algo-pending` 是否實際會回傳 `slTriggerPxType == ""` 或省略該欄。
    2. 在 OKX 網頁介面將全倉條件單改為固定張數或小數格式（例如 `"1.0"`）時，回傳的 `slOrdPx`、`closeFraction`、`sz`、`state` 確實欄位組合。

---

## 七、實測指令與結果摘要（皆於隔離暫存 HOME 執行，`HOME_CONTENTS: 0`）

| 測試項目 | 目標版本 | 指令摘要／腳本 | 結果（親眼觀測） |
| --- | --- | --- | --- |
| 自建 17 項少見情況與探針 | `b9e406a4`（快照） | `CATOS_SNAPSHOT_DIR=%TEMP%\catos_commit_b9e406a4 python verify_rare_cases.py` | `Ran 17 tests in 43.261s -> OK`；但探針印出 `[PROBE 3b-bot] altered_events=[]`、`[PROBE 6b-1]` 無停損開空、`[PROBE 6b-2]` 未升級停損加倉 |
| 自建無 Mock D1 實戰重現 | `b9e406a4`（預載快照） | `probe_unmocked_d1.main()` | 重現 D1：`posts: [('buy', '1', False), ('buy', '1', False), ('sell', '2', True)]`、`algos: {}`、`protection_wait: 12` |
| 三版本並排對照（7 情境） | `b9e406a4~1` vs `b9e406a4` vs `3064346c` | `compare_prev_vs_head.py --worker` | 7 項在 `b9e406a4~1` 均失敗／重送／崩潰；`b9e406a4` 通過（含第 6 項僅不送舊比例改單片段）；`3064346c` 第 6 項改為 `stop_reason: protection_config_failed:synthetic` |
| `b9e406a4` 原 9 項測試跑在舊碼 | `b9e406a4~1`（快照） | 動態編譯 `b9e406a4:tests/test_demo_bot.py` `RareCaseTests` | `Ran 9 tests in 36.634s -> FAILED (failures=7, errors=1)`，證實第 6 項測試在舊碼竟回報 `ok` |
| 自建 17 項跑在新主線 | `3064346c` | `python verify_rare_cases.py` | `Ran 17 tests in 57.657s -> FAILED (failures=1)`：`test_6a` 失敗原因為 `3064346c` 已按 D1 修法停機於 `protection_config_failed:synthetic`（符合期待）；`PROBE 6b-1`/`6b-2` 皆不再加倉或開倉 |
| 無 Mock D1 重驗 | `3064346c` | `python probe_unmocked_d1.py` | `posts: [('buy', '1', False)]`、`algos: {}`、`stop_reason: protection_config_failed:verified cost baseline required before enabling protection` |
| `3064346c` 窄範圍複驗＋X1/X2 | `3064346c` | `python verify_uncommitted_recheck.py` | `Ran 6 tests in 9.108s -> OK`；證實 D1／`live+sz`／O6 已修，並印出 `[RECHECK O1 pause+sz] altered=False` 及 `[PROBE X1]`/`[PROBE X2]` `state=failed` |
| X1/X2 跨三版本比較 | `b9e406a4~1` vs `b9e406a4` vs `3064346c` | `verify_uncommitted_recheck` `test_probe_x1`＋`test_probe_x2` | 三版本皆回傳 `Ran 2 tests -> OK`，皆重現 `SupervisorUnavailable: synthetic reconciliation required before processing` |
| 現有受影響單元與整合測試（6 組） | `3064346c` | `python -m unittest discover -s tests -p ...` | `test_demo_bot.py`: 59 tests OK；`test_risk*.py`: 48 tests OK；`test_kill_switch.py`: 26 tests OK；`test_execution*.py`: 35 tests OK；`test_protection.py`: 19 tests OK；`test_okx_demo.py`: 24 tests OK |

### 本輪未執行的檢查項目（明確揭露）

1. 未執行完整非受影響後端測試全集（如研究核心、本地模擬重播、workspace API 等其餘模組；`3064346c` commit 訊息註記其曾執行 `894 tests` 屬原開發方歷史紀錄，本獨立驗收僅實測上述直接受影響之 6 組後端測試套件共 211 項既有測試與自寫腳本）。
2. 未執行前端任何檢查（`npm --prefix frontend/cat-os-vite run typecheck`、`test`、`build`、`node frontend/cat-os-vite/tests/simulation_integration_test.mjs`）。
3. 未連線真實 OKX 模擬盤／實盤、未讀取任何憑證檔。
