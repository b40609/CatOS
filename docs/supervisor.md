# Slice E：本機 Supervisor 與 SQLite

E 接在 `3879c55` 的 Worker 基線之上。使用者回報該基線全域 93／93 測試通過；本輪只執行 E 與受影響 Worker 的測試。

此切片提供單一 Windows 使用者、單一模擬帳戶、單 Bot／合約的持久化流程。Python 標準函式庫即可執行；SQLite 使用 WAL、`synchronous=FULL`、foreign keys。策略仍只在普通獨立 Worker 載入，Supervisor 不載入策略。

## 使用方式

從專案根目錄的 Python 程式呼叫。以下全為合成帳戶與 K 線，不撮合、不產生可派送委託：

```python
import asyncio
from decimal import Decimal as D
from pathlib import Path

from catos.ipc import WorkerConfig
from catos.journal import Reconciliation
from catos.research import AccountView, Candle, ContractSpec
from catos.supervisor import LocalSupervisor


async def main():
    step = 900_000
    config = WorkerConfig(
        ContractSpec("SYNTHETIC-USDT-SWAP", D("0.01"), D("0.01"), D("1"), D("1")),
        timeframe_ms=step, warmup_bars=2,
    )
    async with LocalSupervisor(
        Path("data/local-simulation/state.sqlite3"),
        account_id="slice-e-example", bot_id="sma-example", config=config,
        fixture_budget=D("100"),
    ) as supervisor:
        # 這是明示的合成證據；不能以此取代實際交易所對帳。
        await supervisor.reconcile(Reconciliation(
            revision=supervisor.revision, evidence_id="synthetic-empty-account",
            position=D("0"), ordinary_open=0, conditional_open=0,
            unknown_count=0, fills_reconciled=True,
        ))
        for index, text in enumerate(("100", "101", "103")):
            price = D(text)
            candle = Candle(index * step, price, price, price, price)
            account = None if index < 2 else AccountView(
                (index + 1) * step, D("0"), D("0"), D("1000"),
                D("0"), D("0"), D("1000"), D("0"), D("0"),
            )
            receipt = await supervisor.process_bar(
                index + 1, candle, account,
                expires_at_ms=(index + 2) * step,
                now_ms=(index + 1) * step,
            )
            print(receipt.event_seq, receipt.disposition, receipt.replayed)


asyncio.run(main())
```

新帳戶預期為 `NO_INTENT`、`NO_INTENT`、`REJECTED`。F 尚未接入，預設以 `risk_engine_not_installed` 拒絕有交易差額的目標。`CommitReceipt` 只表示資料已提交，不是交易所 ACK 或成交證明。重跑相同事件可回傳既有紀錄，`replayed=True`。

`account_id` 是明示且穩定的本機假帳戶識別；目前只接受 `environment="local-sim"`，拒絕 Demo／Live。再次啟動須使用同一帳戶、DB、Bot 設定與 fixture budget，並先提供合成對帳證據。沒有憑證讀取器、連網 client、背景服務或交易出口。

## 提交與 ACK 時序

1. 取得帳戶 OS file lock，核對固定 DB 路徑綁定與 SQLite 中的帳戶／設定。恢復已提交 checkpoint，健康狀態一律先為 `RECONCILING`。
2. Supervisor 提供合成證據後，才可開始處理 Closed Bar。事件序號包含預熱，從 1 遞增；K 線、帳戶視圖及期限一起寫入 `inputs`，COMMIT 後才交給 Worker。
3. Worker 以 `require_commit_ack=True` 啟動。回覆暫定 EventResult 後等待 ACK；父程序的 Worker checkpoint 尚不前進，也不能送下一根。
4. 同一 SQLite 交易寫入事件消費位置、checkpoint、意圖、裁決、reservation 與 outbox。無意圖不建立意圖列；拒絕／過期結果也提交，避免反覆重算。
5. COMMIT 成功後轉換記憶體暫定額度，保存等待期間收到的鎖存，才傳 `ack`。Worker 回覆 `acknowledged` 後，Supervisor 才向呼叫端交付 receipt。

一筆輸入保存與其結果提交是兩個明確交易：前者供未完成事件重播，後者才是金融接受點。沒有跨 DB 金融交易，也沒有只因 Worker 回覆便視為已接受。

`inputs` 以 `(bot_id, seq)` 唯一；資料庫本身固定 account／environment。意圖 key 保存 `[environment, account_id, bot_id, strategy_id, strategy_version, seq, output_index]`，本切片 output index 為 0；Worker generation 不在 key 裡。

canonical JSON 對 object key 排序，並保存 SHA-256 與完整本文。同 key、同內容回傳原紀錄；同 key、異內容將 Bot 持久化標記 `isolated`，拒絕後續處理，並停用該 Worker。金融數值是 JSON 字串，所以改變十進位文字表示也屬於內容變更，不自動猜測其等價性。

重啟時未 COMMIT 的結果由已保存輸入與 checkpoint 重播；已 COMMIT 但 ACK 遺失者直接回傳紀錄，不再執行策略或占用額度。重播仍須明確傳入相同輸入與期限；沒有自動掃描／排程待處理事件。

## 單一寫入與控制事件

`LocalSupervisor` 內只有一個專用 SQLite thread，connection 使用預設的同執行緒檢查。外部不使用該 connection；Worker 只收到策略資料，沒有 Journal／DB 路徑／寫庫介面。

同時最多一個狀態／金融操作在途，其他操作回報 `SupervisorBusy`，不累積無界工作佇列。SQLite 等待不阻塞 asyncio loop。`latch("manual_kill")`、`latch("soft_loss")`、`latch("hard_loss")` 可立即提高記憶體要求並增加 epoch，不等待 Worker 或 DB。

`latch()` 返回不表示已落盤：閒置時呼叫端應接著 `await persist_controls()`；交易等待中則由當前操作在提交／ACK 邊界保存，正常 `close()` 也會嘗試保存。已保存的原因只合併、不清除，重啟、對帳或空倉不解除；E 沒有人工解鎖介面。Soft／Hard 觸發門檻與完整 R／H／P 狀態機留給 F。

若 Kill 在金融 COMMIT 已送入 SQLite 後抵達，該筆模擬 reservation 仍可能提交；隨後寫入的新 epoch／鎖存持續有效。其 outbox 始終不可派送，舊 epoch 不提供下單權限。G 仍須實作出站前重查，不得把本切片的 receipt 當成派送許可。

取消 asyncio 等待不能取消正在執行的 SQLite COMMIT。Supervisor 保留帳戶鎖，等待該 thread 返回後進入 `DEGRADED`；不 ACK、不清空不確定的暫定額度。`close()` 同樣等候寫入收尾，才關 connection 及釋放鎖。沒有宣稱磁碟永久卡住時仍可限時關閉；不能以逾時搶走仍在工作的 writer。

## 純模擬額度與不可派送待辦

測試可由 Supervisor 呼叫端明示 `FixtureDecision(reserve=True, amount=Decimal("80"), reason="test_fixture")`，驗證原子 reservation。Worker 沒有此參數。`fixture_budget` 與 `amount` 是測試指定的 USDT 數值，採研究核心外部 Decimal 範圍，並非 3.0x／50% 曝險政策，也不由目標或假帳戶權益自動推算。

| 裁決 | 持久化結果 |
|---|---|
| 預熱／null 目標 | `NO_INTENT`，只保存輸入消費位置與狀態 |
| 目標等於目前部位 | `NO_CHANGE`，無 reservation／outbox |
| 預設、鎖存、未就緒或預算不足 | `REJECTED`，記錄原因，無 reservation／outbox |
| 模擬時鐘達到明示期限 | `EXPIRED`，不保留額度 |
| 明示 fixture 通過且預算足夠 | `RESERVED_SIMULATION`，同筆新增 reservation 及 `HELD_SIMULATION` outbox |

所有金額、部位與目標以 SQLite TEXT 保存，運算以 Decimal 在獨立 context 完成，不使用 SQLite `SUM` 或 REAL 算金融數值。可用 fixture budget 扣除已提交與本次暫定保留；提交未確認時不能批准第二筆。80／100 的在途請求會先占用 80，後續 80 不能又以 100 為可用預算。

outbox 只有意圖關聯、epoch 與 `HELD_SIMULATION`，沒有 OKX payload、網路派送器或解鎖待辦的 API。固定 tag 的 OKX 建單出口仍屬 G，E 沒有另一條可跳過 tag／風控的交易路徑。既有 reservation 在本片沒有自動到期釋放／清空方法；需留待 G 的取消與對帳契約處理。

`now_ms` 與 `expires_at_ms` 是顯式合成時鐘，期限不可早於決策收盤時間。重播舊 receipt 不重評其期限；未來派送器必須另查當前真實時間，E 不宣稱已驗證行情新鮮度。

## 帳戶鎖、資料庫綁定與合約所有權

Windows 使用標準函式庫 `msvcrt.locking` 非阻塞鎖住檔案第 0 byte；鎖檔位於使用者家目錄的 `.catos/local-simulation-locks/`，檔名由 environment／account_id 雜湊決定，與 DB 路徑、工作目錄及 Worker generation 無關。同一 Windows 使用者下的相同模擬帳戶競爭同一把鎖，無 heartbeat 偷接管。

初次 SQLite 初始化成功後、接受金融工作前，在同一鎖檔附加固定 DB 絕對路徑並 flush／fsync。它只存路徑，不存金額、鎖存或另一套帳本。鎖檔不刪除、不重寫綁定；改指另一 DB、已綁定 DB 遺失或綁定不完整時拒絕啟動，不自動新建帳戶狀態。跨路徑遷移／備份還原工具尚未實作；不要刪鎖檔來繞過錯誤。

程序退出／被終止後 OS 釋放 file lock，但 SQLite `ownership` 紀錄仍在。這兩種所有權不同。E 只允許同帳戶一個受管 Bot／合約；不原地改策略設定，也不將未知或別人的部位歸給目前 Bot。這是受信程序的單人本機流程，不是跨 Windows 使用者的鎖或惡意程序隔離保證。

`reconcile(Reconciliation(...))` 只接收 Supervisor 提供的合成證據。非零部位必須明示歸屬同 Bot；陌生歸屬拒絕。證據要包含 position、普通／條件委託數、UNKNOWN 數與成交是否完成對帳，並匹配目前 revision。新輸入與結果提交會增加 revision，重啟使舊的對帳資格失效。

`release_contract()` 須有最新證據，部位為零、普通及條件委託均為零、UNKNOWN 為零、成交已對帳，且 DB 裡無未完成輸入、reservation 或 outbox。即使合成快照聲稱空倉，既有待辦也不能因此消失。Worker 死亡或停止不呼叫釋放。

## 資料表與失敗邊界

資料只保存在一個 SQLite：`metadata` 固定帳戶／環境／fixture budget；`control` 保存鎖存與 epoch；`bots` 保存設定、checkpoint 與消費位置；`ownership` 保存歸屬及合成證據；`inputs` 保存可見輸入與結果；`intents`、`reservations`、`outbox` 保存接受責任。無成交帳本、虛擬分帳或通用事件溯源框架。

未知 schema、帳戶／預算不符、損毀或消費位置不一致時報錯，不刪庫重建。SQLite 錯誤／取消等不確定狀態會停用 Worker、禁止繼續本次 Supervisor；已落盤資料留待同 DB 重啟並先對帳。失效期間無旁路下單，也不宣稱新鎖存已寫入故障磁碟。

## 驗收

2026-09-11：Journal 14 個、Supervisor 14 個、受影響 Worker 15 個，共 43 個模組測試通過。本輪未重跑全域套件；先前的 93／93 為使用者回報的基線結果。

```powershell
py -3 -B -m unittest discover -s tests -p test_journal.py -v
py -3 -B -m unittest discover -s tests -p test_supervisor.py -v
py -3 -B -m unittest discover -s tests -p test_worker.py -v
```

合成場景包含 WAL／FULL／TEXT、重播去重與異內容隔離、原子額度、預熱／拒絕／過期、所有權釋放條件、錯 DB 與缺檔拒絕、雙程序競爭、程序死亡解鎖、COMMIT 前後 `os._exit`、COMMIT 錯誤、ACK 遺失、取消／關閉等待及 Kill 不被舊提交解除。故障子程序僅存在於 `tests/fixtures/journal_process.py`。

這些是程序中斷及受控 I/O 故障驗證，不代表真實斷電、硬體 fsync 耐久性、遠端 exactly-once、完整帳戶風控或 OKX 對帳已驗證。F／G、UI、Demo／Live 與真實憑證均未接入。
