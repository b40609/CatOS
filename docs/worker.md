# D：本機獨立 Worker

本模組讓已檢查的 SMA 策略在普通獨立 Python 程序執行，透過有界 JSON 訊框回傳純資料目標。父程序不載入 SMA，不提供交易 client、憑證或 SQLite 介面。僅使用 Python 標準函式庫；研究核心與既有 SMA 交易邏輯未修改。

這是本機模擬底座的 D 切片，單獨使用時尚非完整 Supervisor。沒有撮合、交易所連線、風控裁決、合約所有權、outbox 或自動故障續跑。E 已新增由 [LocalSupervisor](supervisor.md) 管理的 SQLite／COMMIT ACK 模式；直接使用 D 的預設行為仍為純記憶體。普通子程序提供故障隔離，不能阻止惡意策略自行讀檔、連網或越權；只執行使用者選定並經檢查的策略及依賴。

## 使用方式

從專案根目錄的 Python 程式呼叫；需使用支援 subprocess 的 asyncio event loop（Windows 標準 `asyncio.run` 所用的 Proactor loop）。`WorkerHost` 必須用 async context manager 或在 `finally` 中 `await close()`：

```python
import asyncio
from decimal import Decimal as D

from catos.ipc import WorkerConfig
from catos.research import AccountView, Candle, ContractSpec
from catos.worker_host import WorkerHost


async def main():
    step = 900_000
    config = WorkerConfig(
        ContractSpec("SYNTHETIC-USDT-SWAP", D("0.01"), D("0.01"), D("1"), D("1")),
        timeframe_ms=step,
        warmup_bars=2,
    )
    async with WorkerHost("example-bot", config, timeout=5) as host:
        for index, text in enumerate(("100", "101", "103", "102")):
            price = D(text)
            candle = Candle(index * step, price, price, price, price)
            # 明示假帳戶，每次仍為空倉；本例不執行意圖或模擬成交。
            view = None if index < 2 else AccountView(
                (index + 1) * step, D("0"), D("0"), D("1000"),
                D("0"), D("0"), D("1000"), D("0"), D("0"),
            )
            result = await host.process_bar(candle, view)
            print(result.event_seq, result.target_position)


asyncio.run(main())
```

預期依序取得 `None`、`None`、`Decimal("2")`、`Decimal("0")`。回覆是目標張數；`None` 表示維持原部位，零表示平倉目標，兩者不等價。有效目標仍不是核准委託，也不表示已成交。

## 程式責任

| 檔案 | 責任 |
|---|---|
| `catos/ipc.py` | 訊框、嚴格 schema、Decimal 還原、設定／checkpoint／事件／結果驗證；不載入 SMA |
| `catos/worker_host.py` | 一個 Bot 對應的一組 pipe、啟動及停止、非同步輸出排空、逾時與回覆驗證 |
| `catos/worker.py` | 子程序入口；唯一載入策略的執行端，依研究時序更新指標及決策 |
| `examples/sma_state.py` | 對既有 `SMATrend` 提供兩根收盤價的明確狀態轉接，不重寫策略邏輯 |

目前策略識別固定 `sma-trend`／版本 `1`，不接受任意模組路徑、class hook 或 Worker 自報 Bot 身分。版本 1 是目前已檢查製品的契約標記，尚非來源雜湊驗證或 Live 製品啟用機制；修改策略或其狀態契約時必須重新檢查版本與相容性。

## 訊框與資料契約

- 每框為 4-byte unsigned big-endian 長度＋UTF-8 JSON object；長度不含前綴。支援分段讀寫及連續訊框。
- JSON 根訊息欄位恰為 `version`、`kind`、`generation`、`seq`、`payload`。版本固定 `1`；generation 由父程序產生，Bot 身分由 pipe 綁定。世代只阻擋舊程序訊息，未來不得放入持久化意圖主鍵。
- `init` 傳入設定及 checkpoint；`initialized` 確認相同 checkpoint。`bar` 傳入當前 K 線與帳戶視圖；`result` 恰含 `target`、`checkpoint`、`ready`。每 Bot 最多一筆往返在途，並行呼叫直接拒絕，不累積工作佇列。
- `seq` 是從 1 開始、包含預熱事件的連續序號；初始 checkpoint 為 0。D 不提供同一 session 事件重送；錯序號、缺口、重複 K 線、未知欄位、冒名及舊世代均拒絕。
- JSON 拒絕重複鍵、Float token、NaN／Infinity、非法 UTF-8、過深巢狀與過長數字。金融值使用字串，直接還原 Decimal；禁止 pickle、dill、cloudpickle 或自動反序列化 Python 物件。
- 合約規格、OHLC、目標張數沿用研究核心的外部 Decimal 範圍（最多 28 係數位、最細 18 位小數、adjusted exponent 至多 18）。帳戶視圖可能含核心計算後的 50 位數值，允許最多 50 係數位、exponent 不小於 −148、adjusted exponent 不大於 99，保留其精度；不將它轉為研究外部輸入再截斷。
- K 線須已收盤、OHLC／tick 合法、指定週期連續；帳戶視圖的時間必須等於本根收盤時間。帳戶數值由父程序提供，此模組不驗證會計完整性、行情新鮮度或實際保證金。
- 目標與差額須符合 lot／最小張數，但這僅為數量驗證，不替代 Supervisor 的曝險、日損或交易權限檢查。

### 預熱與狀態還原

父子程序均由設定與序號判定預熱，不接受策略自報 phase。預熱事件的 `account` 必須為 null，只更新指標、回覆 null 目標；父程序拒絕預熱意圖。SMA 需要兩根收盤價，正數預熱結束時必須就緒；零預熱時第一根正式事件不就緒便失敗，與既有研究介面一致，不默默補足預熱。

`Checkpoint` 包含設定（含策略識別／版本）、最後事件序號、最後 K 線開盤時間、最多兩根 Decimal 收盤價。欄位明確，不序列化 `__dict__`；設定不符、窗口長度／價格錯誤或不可能的時間／序號均拒絕。父程序另比對回覆的窗口是否正是前窗口加當前收盤價。

預設 D 模式的 `result.checkpoint` 與 `host.checkpoint` 是通過驗證後的記憶體狀態。可由呼叫端明確傳入新的 `WorkerHost(..., checkpoint=saved)`，驗證相同輸入產生相同後續決策；本模組不自動保存、重啟或重送。E 的 [LocalSupervisor](supervisor.md) 已另外建立輸入留存、消費位置、模擬裁決與 COMMIT／ACK 邊界；其 ACK 模式如下。

## 故障與資源上限

E 新增可選 `WorkerHost(..., require_commit_ack=True)`。初始化帶 `commit_ack: true`，Worker 回覆 result 後只等 `ack`；父端須在 SQLite COMMIT 成功後呼叫 `await host.acknowledge(seq)`，並驗證 `acknowledged` 回覆。ACK 完成前 host checkpoint 不前進，下一根事件會被拒絕。錯 ACK、連線失敗或程序停止須由 Supervisor 從已持久化紀錄恢復；Worker 本身不驗證 DB，亦不持有 DB。省略此選項時維持 D 原行為。

| 項目 | 上限／處置 |
|---|---|
| 每框 payload | 65,536 bytes，讀取本文前先驗證長度 |
| JSON 巢狀 | 最多 8 層容器；在 JSON decoder 前檢查 |
| JSON 整數 | 非金融用的 signed 63-bit magnitude；序號／時間非負且至多 `2**63-1`，拒絕 bool |
| 金融字串 | 至多 192 字元，另依欄位驗證精度與範圍 |
| 訊息／事件在途 | 1 個 pending future，無無界事件佇列；每方向一個 writer |
| pipe 讀取緩衝 | asyncio StreamReader limit 65,536 bytes；並非整個程序 RAM 上限 |
| stderr | 每次讀取最多 4,096 bytes，持續排空，只保留最後 8,192 bytes |
| 往返期限 | 預設 5 秒，可設 `(0, 60]` 秒，涵蓋寫入 drain 與回覆等待；不承諾 OS 程序建立耗時上限 |
| 終止等待 | 停用時 kill 子程序，最多等待 2 秒；未完成則回報錯誤，不宣稱已清理 |

Worker 崩潰、EOF／截斷、stdout 污染、無回覆或協議違約會停用該 host，`failure` 保存原因，`stderr_tail` 保留限量診斷。未通過驗證的事件不推進父程序 checkpoint。重複輸出停用 host；若首個合法回覆已交付，它可能已推進記憶體 checkpoint，第二框仍不得成為第二筆結果。

取消正在等待的 `process_bar` 也停止子程序，並向呼叫端傳出 `CancelledError`；外部控制流程可主動 `await close()` 中止等待。host 為一次性物件，故障後不能用 `start()` 重新啟用。使用 async context manager 確保收尾。

子程序用固定 bootstrap、`-I -S -B -u` 與明確 Python executable 啟動，僅傳遞 `SystemRoot`／`WINDIR`（若存在），不複製整份環境、不搜尋任何真實金鑰。Windows 啟動不另開 console 視窗。這些是受信策略的應用職責限制，不構成 OS 安全沙箱。

## 驗收

2026-09-11：IPC 11 個、Worker 13 個專屬測試全部通過；Worker 最後一輪包含控制端主動關閉與 Windows 隱藏子程序啟動設定。測試結束已檢查受測 Worker 終止與讀取 task 收尾。

E 整合新增 COMMIT ACK 與錯序號 ACK 測試，本輪受影響 Worker 共 15 個測試通過；IPC 原始模組未修改，未重跑其測試。

只執行本切片的專屬測試：

```powershell
py -3 -B -m unittest discover -s tests -p test_ipc.py -v
py -3 -B -m unittest discover -s tests -p test_worker.py -v
```

測試採合成 Closed Bar、假帳戶、假環境哨兵，以及 `tests/fixtures/worker_peer.py` 的受控故障子程序。涵蓋分段 I/O、嚴格 JSON、Decimal、設定／狀態綁定、SMA 等價、預熱中及正式期還原、父程序不載入策略、錯世代／序號／冒名、逾時／取消／崩潰／重複輸出／stderr 排空及子程序收尾。fixture 不提供產品可選策略或任意程式執行入口。

未執行全市場歷史回測、全域測試、真實斷電或惡意程式 OS 隔離測試；不宣稱本模組已提供交易授權、金融持久化或遠端 exactly-once。
