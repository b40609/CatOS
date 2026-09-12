# Slice G：本機假交易所與恢復閉環

2026-09-12，以 `3e41c97` 為基線完成。本片接通 Worker 意圖、Supervisor 裁決、SQLite 持久化、本機腳本回報、重啟查單及對帳；研究核心與策略製品未改動。沒有網路、真實憑證、Demo／Live 或行情撮合模型。

## 啟用與最小操作

```python
from decimal import Decimal
from catos import risk
from catos.fake_exchange import FakeExchange
from catos.supervisor import LocalSupervisor

exchange = FakeExchange("synthetic-account")
supervisor = LocalSupervisor(
    "simulation.sqlite3",
    account_id="synthetic-account", bot_id="bot", config=worker_config,
    fixture_budget=Decimal("100"), risk_limits=risk.Limits(), exchange=exchange,
)
```

`worker_config` 沿用 [D](worker.md) 的已檢查製品設定；其餘風險觀測與對帳資料依 [F](risk.md)。只接受帳戶相符的 `FakeExchange` 本類別，不接受任意交易 client；不建立 Live 適配器。未傳入 exchange 的 E／F 介面維持原行為，不能派送。

依序 `start()`、`reconcile(Reconciliation(...))`、`observe_risk(Snapshot(...))`，再提供 Closed Bar。預熱不產生意圖。`process_bar()` 的 `RESERVED_SIMULATION` receipt 仍只代表原子提交；`dispatch(receipt.intent_key, now_ms=...)` 才嘗試本機送出。

假交易所不自行撮合。用 `exchange.enqueue("submit" | "query" | "cancel", Report(...) | Exception(...))` 排入腳本；未提供回報等同 timeout，不憑空產生成交。`Fill` 的數量、價格及費用用 Decimal；單次 `Report` 最多 128 筆成交且受 JSON 訊框上限約束。測試中的腳本與 call log 是短程合成資料，不是常駐行情或生產重播服務。

| Supervisor 介面 | 行為 |
|---|---|
| `dispatch(intent_key, now_ms=...)` | 重查當前風控、數量、期限與 epoch；持久化後送出一次 |
| `query_order(order_key)` | 按永久 client ID 查詢；只使用腳本證據更新狀態 |
| `cancel_order(order_key)` | 先保存撤單在途，再呼叫假交易所；撤單 ACK 不直接結案 |
| `control_step(now_ms=..., expires_at_ms=...)` | Soft／健康關門處理增倉待辦；FLAT 轉交清倉步驟 |
| `flatten_step(now_ms=..., expires_at_ms=...)` | 原清倉操作中的單一步驟：撤單、查詢或核實後減倉 |
| `flatten_progress("DONE", now_ms=...)` | 僅 VERIFY 後、完整新鮮證據成立才能結案；不解除鎖存 |

控制步驟由呼叫端明示驅動，不啟動背景循環。每次 transport await 上限 5 秒；與 Worker、SQLite 金融操作共用既有單一操作序列。同步 `observe_risk()`／`latch()` 仍能在等待時立即關門；後續控制步驟使用同一 writer，不另開救援交易路徑。

## 唯一建單與持久化界線

`build_payload()` 只從 Supervisor 的合約、固定 client ID、裁決後數量與 reduceOnly 重建白名單欄位。一般開倉、策略平倉、Hard／Kill 減倉都使用同一 builder，固定：

```text
tag = 41cb53c54d6dABDE
tdMode = cross
posSide = net
ordType = market
instId = …-USDT-SWAP
```

不合併 Worker 字典，也不接收任意 API 參數。這是本機模擬 payload 契約，未重新查核地區／帳戶適用的 OKX API schema，也不表示 tag 歸屬或返佣資格已驗證。

完整 order key 與其 32 位英數 `clOrdId` 映射永久保存，碰撞拒絕，不因重啟或換 Worker 世代重用。一般訂單連回既有 intent；清倉子單的完整鍵包含帳戶、Bot、原 `flatten_id` 及子序號，沒有偽造 Worker 事件。

先在同一 SQLite writer 提交 payload、deadline、epoch、SUBMITTING，再呼叫假交易所。送出前還會檢查記憶體中的最新 epoch、風險序號與時間；COMMIT 等待時到達的 Kill、風險或 timer 事件能阻止尚未交付的請求。已進入 transport 的請求則保留可能受理的責任，不能宣稱已撤回。

同一 order key 只送一次，包括已拒絕或終結的訂單。後續策略事件若要建立新意圖，仍須通過當前風控；有未釐清／未終結委託時拒絕重複目標，不逐根 K 線再買一次相同數量。

## UNKNOWN、成交與額度

timeout／不確定 I/O、重啟殘留 SUBMITTING 或撤單在途轉 UNKNOWN；不換 ID、不重送、不自動釋放。一次 NOT_FOUND 不能證明未受理；帳戶位置恰好相同亦不能清除 UNKNOWN。只接受明確拒絕或完整訂單／成交終態證據。

回報用 client ID、exchange ID、單調 revision 及 `(exchange_id, trade_id)` 驗證。相同回報及 REST／WS 重複成交只記一次；同 ID 不同內容、回退累計量、超額成交或不完整卻宣稱 complete 的資料拒絕。部分成交在同筆交易更新去重紀錄、歸因部位與剩餘待成交量；Decimal 價格及費用原值以 TEXT 保存。F 的名目保留金額保守維持到終結，不能把剩餘數量與已成交部位重複相加。

FILLED／CANCELED／REJECTED 必須另有 `complete=True` 的完整成交證據才釋放對應 reservation／outbox；LIVE 撤單 ACK、單純查無、終態但成交缺漏都不夠。釋放後帳戶仍回到 RECONCILING，需完整新鮮對帳才開放後續裁決。`complete` 是合成腳本的證據契約，真實交易所資料的完整性判定仍需未來適配器實作。

G 的 `Snapshot.pending_buy/pending_sell` 必須排除**全部已由本地 execution 管理的委託**，包含已送出者；Journal 從剩餘數量自行計入，避免外部快照再次重算。其餘未知風險仍須完整提供；沒有把 UNKNOWN 清成零的捷徑。

`execution_fills` 保存自身歸因所需的成交、價格與費用，部位沿用 ownership 欄位；沒有虛擬分帳或第二套績效帳本。權益、margin 與資金流仍由明示的合成觀測供應，沒有由成交推導完整保證金、現金或日損帳單模型。

## 清倉、晚到成交與所有權

Hard／Kill 沿用 F 的 FLAT 鎖存與唯一操作 ID。尚未交付的舊待辦可在本地終結；已送出的增倉先撤單或查詢。最新已核實部位允許 reduceOnly 市價減倉，不以所有撤單終結作為全域屏障；仍有 UNKNOWN 減倉時，不建立第二張衝突減倉單。

每一張減倉均重算數量，不穿零；部分成交／拒絕後需補齊回報、重新對帳及提供最新部位。每次重試是原清倉操作中的新子序號，不能重送同一張結果未知的子單。零部位、普通及條件單終結、無 UNKNOWN、成交已對帳且本地待辦全結束，才能 VERIFY → DONE。晚到的新增成交使原操作回到 WORKING，鎖存與操作 ID 不變。

新 G 帳戶只從已核實空倉初始化；已有 F 歸因部位保留在原 DB。對帳位置必須等於本地已歸因部位加去重成交的結果，差異拒絕自動歸因並關閉 gate。未知普通委託、條件單或陌生部位不會被默認為本 Bot 所有。G 不建 algo／保護單、不替陌生部位清倉；條件單未終結時不宣稱完成。

## 升級與驗證

schema 2 → 3 在交易內新增 `execution_mode`、`execution_orders`、`execution_fills`；沿用 F 表與唯一 writer，保留舊 checkpoint、意圖、reservation、所有權及日損鎖存。啟用 G 的 DB 不能原地改回沒有 execution 的模式。F 尚未送出的舊 epoch 待辦於 G 重查時可明確 ABORTED；不把它冒充 UNKNOWN 或直接派送。

為保留 E／F 相容性，舊 outbox 的字面狀態仍叫 `HELD_SIMULATION`；啟用 G 後，真正的送出生命週期以 `execution_orders` 為準，不能以舊 outbox 字串或歷史 receipt 推斷未送出。程式外部不應直接操作 Journal 內部方法。

本輪 G 專屬 27 個測試（execution 18、Supervisor 8、程序中斷 1，含三個死亡時點），另跑受影響 E／F Journal／Supervisor 41 個，共 68 個通過。程序測試實際使用 `os._exit`，涵蓋 SUBMITTING COMMIT 前／後及假交易所 handoff 後；亦驗證固定 tag、部分成交、重複與衝突回報、撤單競態、Kill 在提交／handoff 期間到達、晚到成交、schema 升級與清倉完成條件。

```powershell
py -3 -B -m unittest discover -s tests -p "test_execution*.py" -v
```

使用者回報基線全域 150 個測試通過；本輪未重跑全域套件，未執行市場回測、網路請求、Git commit 或 push。上述是本機模擬與程序故障證據，不是遠端 exactly-once、真實斷電、交易所可成交性或完整 v1 生產驗收。P2–P6 的未定案金融政策維持原狀，D–G 完成不自動授權 Demo／Live。
