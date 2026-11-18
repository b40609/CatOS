# 第二意見：commit 5ca49b93（Gemini 4 Hydrogen xhigh，唯讀）

- 日期：2026-11-18；管道：agy 無頭（Antigravity），conversation_id `31505f40-b733-408d-af53-84bb6a6e31bf`。
- 原文照錄如下（只刪掉開頭的進度旁白）。主控處理：缺陷 1（= Claude 驗收 D1）、缺陷 2（= O1）、缺陷 3（對帳時第一次出現的告警沒寫事件）都已在下一個 commit 修正並加測試。

---

【完成待收尾】已完成對 commit `5ca49b93` 的唯讀第二意見審查（未改動 repo 任何檔案、未執行任何核准／解除／網路連線／真實金鑰讀取；僅在系統暫存資料夾建立隔離測試與 `HOME`/`USERPROFILE`）。

## 結論：FAIL（針對目標 commit `5ca49b93`）

> [!NOTE]
> 在本輪審查期間，工作區已出現尚未 commit 的修補 diff（`M catos/demo_bot.py`、`M catos/okx_demo_exchange.py`、`M tests/test_demo_bot.py`），修復了下方缺陷 1 與缺陷 2；但**目標 commit `5ca49b93` 本身**仍存在可重現缺陷，且缺陷 3 於 `5ca49b93` 與目前工作區皆仍存在。

---

## 缺陷清單

### 1. [中] `algo_cancel` 在第 0 次查詢即查歷史且遇 `NOT_FOUND` 立即結束，撤單延遲同步時會誤卡死後續開倉
- **檔案與行號**：`catos/okx_demo_exchange.py`（`5ca49b93` 版第 144–160 行；目前工作區 [okx_demo_exchange.py](file:///C:/dev/CatOS/catos/okx_demo_exchange.py#L146-L163) 已改為 `with_history(attempt)` 修補）
- **情境**：送出 `cancel-algos` 後，若 OKX 剛進入狀態轉換空窗——`order-algo` 已查不到（51603）且 `orders-algo-history` 尚未寫入（延遲 1 個輪詢間隔才出現），`5ca49b93` 在 `attempt = 0` 未等待 `POLL_SECONDS` 即傳入 `history=True`，且 `settled` 對 `NOT_FOUND` 直接回傳 `history`（`True`），導致立刻退出輪詢並回傳 `NOT_FOUND`。
- **證據**：以 `git show 5ca49b93:catos/okx_demo_exchange.py` 搭配暫存驗證腳本模擬 `lag_after_cancel = 1` 實測重現：反手平倉賣單成交後，撤舊停損回傳 `NOT_FOUND` 觸發 `protection_unconfirmed`，造成反手的反向空單被擋（`posts = [('buy', False), ('sell', True)]`），無機會開倉。工作區未提交修改已改為 `attempt >= 1` 才查歷史並延後退出，實測重現該情境已可開出反向空單。
- **建議修法**：保持目前工作區未提交版本作法——`algo_cancel` 於 `attempt == 0` 先只重查 `order-algo`，睡過 `POLL_SECONDS` 後於 `attempt >= 1` 才補查 `orders-algo-history`（並於完成驗證後 commit）。

### 2. [低] `_flatten_rounds` 遺漏清倉單部分成交後被撤的 `fills.json`／事件紀錄
- **檔案與行號**：`catos/demo_bot.py`（`5ca49b93` 版第 590 行；目前工作區 [demo_bot.py](file:///C:/dev/CatOS/catos/demo_bot.py#L596-L597) 已改為 `D(row["filled"]) != 0` 修補）
- **情境**：觸發 Kill-Switch 或 Hard 日損執行 `_flatten_rounds` 時，若第 1 張清倉市價單部分成交（例如 0.4 張）後剩餘被撤（`state = "CANCELED"`, `filled = "0.4"`），下一輪雖會繼續送出第 2 張清倉單平掉剩餘 0.6 張並正確更新 SQLite `execution_fills` 與 `ownership.position`，但 `5ca49b93` 第 590 行仍判斷 `if row["state"] == "FILLED":`，未呼叫 `_record_fill`。
- **證據**：以 `git show 5ca49b93:catos/demo_bot.py` 在暫存驗證腳本模擬清倉單 `partial_fill = "0.4"` 實測：SQLite `execution_fills` 有 `['1', '0.4', '0.6']` 共 3 筆，但 `fills.json` 只記 `[('開倉／調整', 'FILLED', '1'), ('清倉', 'FILLED', '0.6')]`，`status['fills']` 與 `events.jsonl` 的 `fill` 事件皆僅 2 筆，遺漏 0.4 張真實清倉成交。工作區未提交修改改為 `D(row["filled"]) != 0` 後已補齊為 3 筆。
- **建議修法**：採用工作區修改之 `if D(row["filled"]) != 0:` 記錄清倉部分成交（註：反手平倉腿若部分成交，同 `5ca49b93` 第 549–553 行與工作區皆會止於 `order_partially_filled:canceled` 並於接續時依 `expires_at_ms` 作廢剩餘開倉意圖，實測安全）。

### 3. [低] `_reconcile` 觸發 `protection_verify` 首次寫入 `protection_unconfirmed` 或 `protection_mismatch` 時，`events.jsonl` 漏記告警事件（`5ca49b93` 與目前工作區皆存在）
- **檔案與行號**：[catos/demo_bot.py](file:///C:/dev/CatOS/catos/demo_bot.py#L355-L360) 與 [catos/demo_bot.py](file:///C:/dev/CatOS/catos/demo_bot.py#L428-L429)（`5ca49b93` 版第 355–360 與 428–429 行相同）
- **情境**：平倉後若 OKX 自動撤銷條件單且同時在 `order-algo` 與 `orders-algo-history` 皆查不到（`NOT_FOUND`），`_reconcile` 先呼叫 `supervisor.protection_verify`，將保護狀態的 `alert` 設為 `"protection_unconfirmed"`，但 `_reconcile` 未寫入 `protection_alert` 事件；隨後 `_execute` 呼叫 `_protect` 時，`before["alert"]` 已是 `"protection_unconfirmed"`，使 `state["alert"] != before["alert"]` 為 `False` 而跳過寫入事件。
- **證據**：在暫存驗證腳本 `test_s3_not_found_in_history_remains_uncertain_and_blocks_open` 實測，OKX 部位歸零後反向開倉確實安全被擋（`posts == [('buy', False), ('sell', True)]`），且 SQLite `protection` 表內 `uncertain == True`、`alert == "protection_unconfirmed"`，但 `events.jsonl` 中 `protection_alert` 清單為 `[]`（與 [next-steps.md](file:///C:/dev/CatOS/docs/next-steps.md#L69) 記下之 `protection_mismatch` 同源，且同步影響 `protection_unconfirmed`）。
- **建議修法**：將 `protection_alert` 的比對寫入邏輯抽出共用於 `_reconcile` 的 `protection_verify` 之後，或於 `_reconcile` 呼叫 `protection_verify` 前後比對並補寫 `protection_alert` 事件。

---

## OKX 實際行為（未實測，全數標「待驗證」）

- `order-algo` 查詢已結束之條件單是否實際回 `51603`：**待驗證**。
- 部位市價平倉歸零時，OKX 是否自動撤銷 `closeFraction="1"` 條件單，以及自動撤銷後是否即時寫入 `orders-algo-history`：**待驗證**。
- `GET /api/v5/trade/orders-algo-history` 在模擬盤實際回傳欄位（如 `ordType`、`tag`、`slTriggerPx`、`algoClOrdId`、`uTime`）、無 `limit` 時單頁上限是否為 100 筆，以及 `partially_effective`／`partially_failed` 是否歸屬在 `effective`／`order_failed` 過濾條件下：**待驗證**。
- `amend-algos`／`cancel-algos` 實際回傳之 `51xxx` 錯誤碼與該筆條件單當時在 OKX 的真實終態：**待驗證**。

---

## 看過且實測無問題的項目

1. **不變量與授權邊界**
   - 白名單僅於 [okx_demo.py](file:///C:/dev/CatOS/catos/okx_demo.py#L55) `_GET_PATHS` 新增 `"/api/v5/trade/orders-algo-history"`，`_POST_PATHS` 未變動；`protection_history` 僅在 [okx_demo_exchange.py](file:///C:/dev/CatOS/catos/okx_demo_exchange.py#L173-L175) 當 `protection_order` 回 `None` 且 `history=True` 時呼叫，其餘模組未呼叫；`algo_create` 與正常輪詢階段之 `algo_amend` 不補查歷史（情境 S1、S14 實測通過）。
   - 所有市價單與條件單維持 Supervisor 唯一交易出口、固定 `TAG`、`cross`、`net_mode`、`reduceOnly`、`Decimal` 計算與 `UNKNOWN` 不盲目重送。
2. **歷史補查隔離性與邊界**
   - `protection_history` 帶 `instType="SWAP"` 與 `instId`，以 `algoClOrdId` 嚴格比對，遇重複筆數（`len(found) != 1`）或合約不符皆拋 `DemoError` 並於 `_protection_report` 轉 `OSError` 維持不確定；`_protection_report` 另核對 `tag` 與 `ord_type == "conditional"`（情境 S5 實測通過）。
   - 歷史查得 `effective`／`order_failed` 時，Bot 依 `disaster_stop_triggered` 或 `disaster_stop_incomplete` 流程停止，不續開新單（情境 S4 實測通過）；查無結果（`NOT_FOUND`）時維持 `uncertain=True` 與 `pending`，不視為已撤（情境 S3 實測通過）。
   - 請求數與 Supervisor 5 秒逾時：在最壞補查情境下（`algo_cancel` 進 `attempt=1` 最多 7 次請求、`algo_query` 最多 4 次請求），即使模擬 `orders-algo-history` 延遲超過 5 秒觸發 `wait_for` TimeoutError，帳本仍維持 `uncertain=True`、阻塞該輪加倉並待後續恢復查詢解鎖（情境 S13 實測通過）。
3. **`algo_amend` 遇 51xxx 拒單與 `algo_cancel` 遇 51xxx 轉查**
   - `algo_amend` 遇 `51xxx` 後先補查，若停損仍為 `LIVE`（含 `pause`）則回傳 `REJECTED`（`algo_id=None`），帳本保持舊停損價、`failed=True`、`protection_request_failed` 告警僅記一次、每次檢查重試一次不緊迴圈；同時加倉被擋，反手轉為 `reversal_close_only` 平倉，Kill／Hard 清倉不受影響（情境 S6 實測通過）。
   - 若 `algo_amend` 遇 `51xxx` 時原單在歷史中已 `canceled` 或 `order_failed`，如實回報並觸發重建或停機（情境 S4、S7 實測通過）。
   - `algo_cancel` 遇 `51xxx` 時進查詢；若單子實際未撤成仍為 `LIVE`，`ProtectionJournal.apply` 因 `pending['operation'] == 'algo_cancel'` 不會將 `LIVE` 誤當成成功，維持 `uncertain=True` 並擋住後續反向開倉（情境 S2 實測通過）。
4. **部分成交處理與接續一致性（`DemoBot._execute`／`_recover`）**
   - `DemoBot._execute` 部分成交先記 `_record_fill`、重讀帳戶與 `_reconcile`、再執行 `_observe`；若觸及 `FLAT`（Hard）則直接進入 `_flatten` 清倉並以 `risk_flat:...` 停下而不先多掛停損（情境 S10 實測通過）；否則先依新部位執行 `_protect` 再以 `order_partially_filled:canceled` 停下。
   - 反手平倉腿部分成交（保留舊停損、`fills.json` 與帳本一致，且於 60 秒過期前快速接續時 `_recover` 會等過期並作廢未送出的反手開倉意圖，情境 S9 實測通過）、反手只平倉部分成交（保留 Soft 鎖存與部位，情境 S12 實測通過），以及 `UNKNOWN` 委託於接續 `_recover` 第 877 行補查到部分成交並補記 `fills.json` 與補掛保底停損（情境 S8 實測通過；註：`ReviewFixTests` 原未覆蓋 S2、S3、S4、S5、S6、S8、S9、S10、S12 這些分支）。

---

## 測試與驗證實測摘要（均於隔離 `HOME`／`USERPROFILE` 執行）

- **指定核心測試（目前工作區）**：
  - [test_demo_bot.py](file:///C:/dev/CatOS/tests/test_demo_bot.py)（含 `ReviewFixTests`）：`47` tests OK（註：首次以模組路徑執行時因 `tests/` 未入 `sys.path` 發生 2 筆 import 錯誤，改以 `discover` 分別執行後全數通過）。
  - [test_protection.py](file:///C:/dev/CatOS/tests/test_protection.py)：`19` tests OK（2.394s）。
  - [test_step2_deployment.py](file:///C:/dev/CatOS/tests/test_step2_deployment.py)：`25` tests OK（26.824s）。
- **整套後端測試（目前工作區，含工作區未提交修改）**：
  - `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`：`Ran 875 tests in 232.203s — OK`。
- **暫存資料夾自寫獨立情境（針對工作區）**：
  - 14 項獨立情境測試（`s1`–`s14`）：`Ran 14 tests in 53.593s — OK`。
- **暫存資料夾抽出純 `5ca49b93` 兩項缺陷重現腳本**：
  - 2 項重現測試（`5ca49b93` 版 `lag_after_cancel = 1` 卡住反手開倉、`5ca49b93` 版清倉部分成交 0.4 張漏記於 `fills.json`／`status['fills']`／`events.jsonl`）：`Ran 2 tests in 2.488s — OK`。
