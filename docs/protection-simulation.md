# P6：本機災難保護生命週期

本輪已完成參數化的離線核心、同一 SQLite writer 整合及 FakeExchange 操作；沒有帳戶連線、私有請求或 I-b／J。沿用 [P6 已確認政策](disaster-stop-policy.md)；2026-09-12 已確認執行政策為 mark 觸發、tick 向提早觸發方向取整，以及 0% 停用採取消終態確認。

## 範圍與資料

具體失敗情境：保護建立／修改結果不明卻繼續增倉，成本已變但沿用舊保護，或平倉後把仍存在的保護當作已取消。最小做法是同一 writer 保存 Bot 設定、成本、有效保護及未決操作；不建第二套交易程序或帳本。

`catos/protection.py` 提供純 Decimal 計價、Config、合成 Report 與 ProtectionJournal。schema 4 → 5 新增 `protection` 表，按 bot_id 保存有界 JSON，金融值為 TEXT 中的十進位字串。比例預設 0，不同 Bot 的設定分開保存；既有執行器仍限制單一帳戶同時一個 Bot／合約，本輪未擴充多 Bot 調度。

平均成本由 G 去重成交在**同一成交交易**內更新：同向增加依數量加權，部分減倉維持成本，空倉歸零；重複成交不再計算。Worker 的 average_entry 不用來建立保護。舊版非空倉 DB 若缺成本基準，拒絕啟用正比例，不以零、mark 或 Worker 值猜測；舊版平倉後再有自身成交即可建立新成本。

## Supervisor 介面

```python
from catos.protection import Config

# 有效的預設：不啟用；若已有保護，依原設定的停用流程處理。
await supervisor.configure_protection(Config())
state = await supervisor.protection_step(now_ms=simulation_time_ms)
state = await supervisor.protection_state()
```

正比例必須明示 `ratio`（Decimal）；`trigger`、`rounding`、`disable` 未另傳時分別自動採 `mark`、`earlier`、`cancel_confirm`。替代值仍保留供離線分支測試。ratio 支援 `0 <= ratio < 1`；避免多倉生成零／負停損價格，取整後無有效距離也拒絕。

每次 protection_step 只做一個明示模擬步驟，沒有背景輪詢。先核對新鮮且已歸因部位，再 COMMIT 未決操作，之後才呼叫 FakeExchange。其 `algo_create`／`algo_amend`／`algo_cancel`／`algo_query` 腳本獨立於普通交易腳本，沒有 OKX HTTP 實作。payload 固定 tag、cross／net、reduceOnly、closeFraction=1；requestId 是本機合成關聯，不宣稱此 payload 可直接送至 OKX。

## 狀態與失敗處理

| 情境 | 已實作行為 |
|---|---|
| 預設 0%、沒有既有保護 | 不建立保護，不因缺保護阻擋增倉；帳戶 Soft／Hard 照常生效 |
| 正比例、首次部位或平均成本變動 | 對照期望與已確認價格／方向／觸發來源，不符即禁止增加曝險，等待建立／更新 |
| 建立／更新成功 | 必須合成完整確認並符合期望覆蓋；ACK 或不同價格不放行 |
| 建立／更新遭明確拒絕 | 保存失敗及告警、禁增倉；舊有效保護仍可見；不自動減持 |
| 逾時、查無、不完整回覆 | 保留 pending／UNKNOWN，下一步只查詢，不盲重送或釋放責任 |
| 取消 ACK 或不完整 CANCELED | 保留原保護；完整取消終態才清除。條件單清單改變須重新對帳 |
| 正常策略平倉 | 仍可執行合法 reduceOnly；尚有保護時不釋放 Bot 所有權。核實取消後才可完成結案 |
| 重啟 | 有效／未決保護先標記未知，告警並查詢；舊回覆版本不能解除重啟的未知狀態 |
| 磁碟提交失敗 | 不呼叫假交易所；保留原交易與責任，不另開持久化繞行通道 |
| TRIGGERED | 保持待成交對帳，不能解讀成已成交、空倉或 DONE |

保護閘門獨立於 P5 latch：P5 re-arm 不會繞過它。G 的意圖保留及出站前都檢查保護閘門；合法減倉走既有裁決，不因 P6 失敗一概封鎖。變更失效的舊增倉意圖不會因之後保護恢復而重新獲准。

告警保存於 `state['alert']`，Supervisor 在狀態改變與重啟時發出 `catos.protection` WARNING；可由主程式收集。這是本機告警，沒有新增外部訊息推送或通知服務。

## 已確認執行政策

2026-09-12 已確認以下三項為 P6 正式執行政策：

| 項目 | 已確認值 | 行為 |
|---|---|---|
| 觸發來源 | `mark` | 與目前風控估值來源對齊；實際帳戶支援仍須在後續適配驗證 |
| tick 取整 | `earlier` | 多倉向上、空倉向下，不因取整擴大設定停損距離；若無法表示有效距離則拒絕 |
| 非零改為 0% | `cancel_confirm` | 送取消；完整取消終態前禁增倉並保留責任，UNKNOWN 持續告警與查詢 |

`Config` 現在會自動帶入上述三項值；這不會替任何 Bot 自動把 ratio 從 0% 改成正比例。ratio 仍須由使用者／Supervisor 明示設定。

## 驗證與未涵蓋能力

P6 專屬 **18 tests 通過**，含價格取整／Decimal context、0% 停用、完整確認、查無不重送、更新失敗、合法減倉、取消確認、重啟查回、提交失敗、部分成交去重成本、正常平倉殘留保護、舊 DB 缺成本拒絕啟用。受影響 F 27、P5 12、G 28、共用 Journal／Supervisor 28，共 **113 tests 通過**；未重跑全域套件。

本輪不包含行情驅動的保護觸發撮合、algo 觸發後普通子委託與成交的自動連結、TRIGGERED 的完整結案流程、實際帳戶能力驗證及交易所參數映射。TRIGGERED 目前保留責任並關閉增倉，後續必須補齊證據橋接才能結案；不宣稱本機已有真實斷線保險。I-b／J 未啟動，未 commit／push。
