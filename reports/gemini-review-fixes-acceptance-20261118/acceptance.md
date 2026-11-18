# 獨立驗收：commit 5ca49b93（保底停損補查歷史、部分成交、改單被拒）

- 日期：2026-11-18
- 驗收者：Claude Opus 5.5（沒有參與這次開發的另一個會話），effort high
- 範圍：`catos/okx_demo.py`、`catos/okx_demo_exchange.py`、`catos/demo_bot.py` 在 5ca49b93 的改動，以及 `tests/test_demo_bot.py` 的 `ReviewFixTests`
- 沒做的事：沒連 OKX（任何網路），沒讀金鑰檔或 `~/.catos/`，沒碰 `outputs/` 的正式資料夾，沒改 `catos/`、`tests/`，沒 commit。所有測試與自寫情境的 HOME／USERPROFILE 都導到暫存資料夾，跑完檢查都是空的。

## 結論

**PASS**，附 1 個低嚴重度缺陷（D1）和 5 個觀察（O1～O5）。

三項修正都照開發者的說法運作，INVARIANTS 沒有被破壞：固定 tag、Decimal、UNKNOWN 不盲目重送、合法減倉始終允許、保護未確認時擋加倉、唯一交易出口都成立。D1 是保守方向的失敗（多擋了一次開倉，沒有多送東西），不影響安全，所以不判 FAIL；但這是相對於改動前的行為退步，建議修。

OKX 的實際行為都**待驗證**，沒有一手證據：`order-algo` 對已結束的條件單會不會回 51603、`orders-algo-history` 的參數與欄位、平倉時會不會自動撤掉 `closeFraction=1` 的條件單、改單和撤單被拒時實際回哪些 51xxx、從台灣連過去的實際延遲。

## 缺陷

### D1（低）撤條件單後，只要查一次查不到就停止輪詢，OKX 稍有延遲就會漏掉反手的開倉腿

- 位置：`catos/okx_demo_exchange.py:146-150`（`settled()` 對 `algo_cancel` 的 NOT_FOUND 回 `history`，也就是 True）
- 情境：反手時先撤舊的停損。撤單送出後，第一次查 `order-algo` 回 51603（OKX 還沒更新），`orders-algo-history` 也還沒列出這張單。新程式第一輪就把 NOT_FOUND 當成「已結算」回傳，帳本維持「不確定」，同一根 K 線的開倉腿被 `ExecutionJournal.prepare` 擋下（`blocked()`），Bot 留在空倉，要等下一個策略訊號才會再進場。改動前遇到 NOT_FOUND 會繼續查（最多 4 次），第二次查到 canceled 就能照常開倉。
- 重現：暫存資料夾的 `test_accept_lag.py`。用假 OKX 模擬撤單後 `order-algo` 回一次 51603、歷史第一輪也是空的，接著才查得到 canceled。同一份測試分別對 HEAD 和 `5ca49b93~1` 的 `catos/` 跑：
  - HEAD：`posts: [('buy', False), ('sell', True)]`，反手的開倉腿沒送出
  - 改動前：`posts: [('buy', False), ('sell', True), ('sell', False), ('buy', True)]`，照常反手
- 安全性：保守方向的失敗，沒有重送、沒有誤判成已撤；下一次檢查用 `algo_query` 補查就會結清。
- 建議修法：`algo_cancel` 遇到 NOT_FOUND 時繼續輪詢，只查 `order-algo`；只在最後一輪（或 `order-algo` 連續查不到兩次以上）才補查一次歷史。這樣也不會讓請求數變多（見 O3）。

## 觀察（不影響結論）

- **O1 清倉單部分成交沒寫進 `fills.json`**：`catos/demo_bot.py:590` 只在 `FILLED` 時呼叫 `_record_fill`。Kill 清倉的第一張單只成交 0.5 就被撤時，帳本 `execution_fills` 有 `['1','0.5','0.5']`，`fills.json` 只有 `[開倉 1, 清倉 0.5]`，`status.fills=2`（自寫情境 `test_partial_in_kill_flatten`）。帳本與 OKX 部位一致，下一輪會清掉剩下的部位，只有顯示用的紀錄少一筆。這不是這次改動造成的，但和這次修的 `_execute` 屬於同一類問題，建議同樣改成 `D(row["filled"]) != 0`。
- **O2 部分成交停下的提示**：`START_HINTS` 沒有 `order_partially_filled`，CLI 結束時沒有對應說明，只有 events 裡的訊息。訊息（`demo_bot.py:550-552`）寫「保底停損照新部位處理」；沒開保底停損（`--disaster-stop 0`），或那一步因為 `protection_wait` 沒跑成時，這句話不準確。建議依實際狀態措辭。
- **O3 請求數與 Supervisor 的 5 秒等待**：補查歷史一次要 1 個 `order-algo` 加 3 個歷史請求。撤單最壞的路徑是查一次、撤單、3 次 LIVE，再加一次「查不到並補查歷史」，總共 9 個請求，另外有 3 次 0.3 秒的等待。光節流的下限就約 3.15 秒，延遲稍高就會超過 5 秒（改動前最壞是 6 個請求）。逾時的結果是安全的：`protection_step` 吞掉 TimeoutError，pending 留著，下一次檢查用 `algo_query` 補查，不重送（自寫情境 `test_history_lookup_timeout`：每個條件單查詢延遲 1.4 秒，觸發逾時之後才結清，沒有多送任何寫入，最後部位 0）。實際延遲待驗證。
- **O4 撤單被 51xxx 拒絕、單子其實還在**（例如 51000）：查詢回 LIVE，帳本停在「不確定」，之後只查、不再撤。部位已經是 0 時，條件單會一直留在 OKX 上，Bot 也不能再開倉，直到 Kill 或停止時提示 `protection_left`（自寫情境 `test_cancel_refused_stop_still_live`：撤單請求只送一次，最後 `algos: ['live']`）。改動前這種情況是 OSError，結果相同，不算退步；屬於已知缺口「撤單請求沒送到時帳本一直不確定」的同類情況。
- **O5 整套測試會在 `outputs/` 留下 fixture 證據**：這次跑整套測試新增了 `outputs/workspace-w6-fixture-test-c4e73bf…` 和 `outputs/workspace-w8-fixture-test-07b312c…`（同類資料夾共 59 個）。不是正式資料夾，我沒有刪；這是既有行為，和本次改動無關。

## 實際跑過的指令與結果

HOME／USERPROFILE 都指向 `C:\Users\user\AppData\Local\Temp\claude\…\scratchpad\accept-work\home*`，每次跑完都檢查過，目錄是空的。

| 指令 | 結果 |
|---|---|
| `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_demo_bot.py"` | Ran 47, OK |
| `… -p "test_protection.py"` | Ran 19, OK |
| `… -p "test_step2_deployment.py"` | Ran 25, OK |
| `… -p "test_*.py"`（整套後端） | Ran 873 in 201s, OK |
| 新測試 `ReviewFixTests` 對改動前的 `catos/`（`git archive 5ca49b93~1 catos` 解到暫存資料夾）跑 | Ran 5, FAILED (failures=5)，確認 5 項在修改前都會失敗 |
| 自寫情境 `test_accept_scenarios.py`（14 項） | Ran 14, OK（輸出摘要見下） |
| 自寫情境 `test_accept_more.py`（改單持續被拒時遇到反手） | Ran 1, OK |
| 自寫情境 `test_accept_lag.py`（D1），分別對 HEAD 和改動前跑 | 兩邊都是 OK，但送出的委託不同（見 D1） |

工作目錄的 `M tests/test_demo_bot.py` 只是 stat 過期：`git hash-object` 和 `HEAD:tests/test_demo_bot.py` 都是 `54d7a66a…`，內容一樣。`catos/` 四個相關檔案也和 HEAD 相同。

自寫情境的輸出摘要（腳本在 `C:\Users\user\AppData\Local\Temp\claude\09abadd8a3a6a13d\32a2fad0-10db-4ae6-83ab-7019170dec6b\scratchpad\accept-work\`）：

- 歷史比對（直接測 `DemoClient.protection_history`）
  - 同合約別人的條件單、別的 algoClOrdId：會略過，只取自己的那張。三個請求都帶 `ordType=conditional`、`instId`。
  - 別的合約卻有同一個 algoClOrdId：拋 `DemoError`，轉成 OSError，視為不確定，不會被當成自己的單。
  - 同一個 algoClOrdId 出現在兩種狀態：拋 `DemoError`，同樣視為不確定。
  - 三種狀態都查不到：回 `None`。
  - algoClOrdId 相同但 tag 是別人的：adapter 拋 `ProtocolError`。
  - 撤單時哪裡都查不到：回 NOT_FOUND，不送 cancel-algos。
- 反手平倉腿部分成交（1 張只成交 0.5）
  - 停下原因 `order_partially_filled:canceled`，OKX 部位 0.5。停損仍在 94.5 LIVE（均價沒變，`closeFraction=1` 會涵蓋剩下的 0.5）。
  - `fills.json` 和帳本都有 1 與 0.5。
  - 接續時，上一次 run 留下的反手意圖已過期限、不送出（`resume_intent`）；Kill 時清倉 0.5，OKX 部位 0。
- 部分成交後立刻觸發 Hard：記下部分成交，`_observe` 判定 FLAT，先清倉，停下原因 `risk_flat:hard_loss,soft_loss`，OKX 部位 0，沒有掛停損（先清倉）。
- 改單被拒，但 OKX 其實已經改了（假設情況）：帳本先記被拒；下一次分鐘檢查時，`_reconcile` 發現價格對不上，再查一次並採用 OKX 的價格，就自己修正了。只送 1 次 amend，提示也只出現一次 `protection_request_failed`。
- 改單被拒，同時停損已觸發（`order-algo` 查不到）：補查歷史得到 effective，回報 TRIGGERED，停下原因 `disaster_stop_triggered`。
- 改單持續被拒時遇到反手：在約 20 分鐘的模擬時間裡送了 11 次 amend，大約每次檢查一次。反手只送平倉單（只減倉），開倉腿被擋下；撤舊停損成功，OKX 部位 0。
- 停損在 `order-algo` 和歷史都查不到：維持「不確定」，反手的開倉腿被擋下，沒有重送任何寫入；Kill 時提示 `protection_left`。

## 看過但沒問題的項目

- **白名單**（`catos/okx_demo.py:42-58`）：只多了一個 GET `/api/v5/trade/orders-algo-history`，POST 白名單沒變。這個端點在 `catos/` 裡只被 `protection_history` 呼叫（`okx_demo.py:540`）；`okx_collection.py:59` 是之前就有的採集別名，不是 Demo Bot 的路徑。AGENTS.md 授權紀錄有寫 2026-11-18 的授權，範圍與實作一致。
- **補查歷史的時機**（`okx_demo_exchange.py:144`、`:171`）：只有 `algo_cancel`、`algo_query`，以及改單被 51xxx 拒絕之後的那一次查詢，會在 `order-algo` 回 None 時補查。`algo_create`、`algo_amend` 送出之後的輪詢不查歷史。一張建立結果不確定的單，之後經由 `algo_query` 補查歷史也是安全的：algoClOrdId 由 `account_id:bot_id:protection:serial` 雜湊而成（`protection.py:226`），`account_id` 每個新 run 都不同，接續 run 沿用原本的 serial，所以不會撞到舊單。
- **補查到 effective／order_failed**：回報 TRIGGERED。帳本把 triggered 設為 True，`_protect`／`_reconcile` 依 `_fired` 停下；清倉途中則照原本的清倉流程。
- **補查不到**：回報 NOT_FOUND，帳本當作沒有證據，維持不確定並繼續擋加倉，不會被當成已撤（`protection.py:272`）。
- **改單被拒（REJECTED）**：只在查到停損仍是 LIVE 時才回報 REJECTED。帳本的 active 留在舊價，`failed=True`，所以 `blocked()` 為真，加倉被擋（`execution.py` 的 `prepare` 要求 `verdict.reduce_only or not blocked`）。清倉與反手只平倉不受影響（`ReviewFixTests` 和自寫的反手情境都驗過）。重送頻率是每次檢查一次，因為 serial 每次加一，`requestId` 每次都是新的。查到停損已不是 LIVE 時，照實回報 CANCELED／TRIGGERED／NOT_FOUND。
- **撤單遇到 51xxx 直接進查詢**：結果完全由查詢決定。查到 LIVE 時不會當成已撤，只會停在不確定，所以不會誤判。沒有哪個 51xxx 會讓查詢流程判錯，最壞情況是 O4 的卡住。
- **部分成交**（`demo_bot.py:534-553`）：
  - 順序是記成交、對帳、`_observe`（FLAT 就先清倉）、`_protect`，然後停下。
  - 部分成交的單是 CANCELED 且完整，`execution.apply` 會在同一個交易裡釋放保留額度與 outbox，不會留下半張意圖。
  - 反手平倉腿的意圖沒有寫進 execution order，接續時等到期限，`prepare` 會因為過期而 ABORTED，不會送出。
- **接續補記**（`demo_bot.py:877`）：`_recover` 只處理還沒結算的委託，上一次 run 已記過的部分成交不會重複記。
- **Decimal**：新程式碼的金額與數量都用 `Decimal`／`_dec`，沒有 float。
- **固定 tag**：歷史查詢不送 tag。查到的單如果 tag 不是自己的，會被拒絕（`_protection_report` 的 tag 檢查）。
- **唯一交易出口**：沒有新增任何寫入路徑，所有寫入仍經由 Supervisor 到 adapter。
- **ReviewFixTests**：5 項都對應到開發者說的行為，而且在修改前都會失敗（實測）。沒涵蓋的部分由上面的自寫情境補上：歷史比對、改單被拒且停損已觸發、逾時、反手平倉腿或清倉單部分成交、Hard。
