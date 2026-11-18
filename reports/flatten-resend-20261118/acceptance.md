# 獨立驗收：清倉單可證明沒送到後再送（commit 6d600094）

- 驗收日期：2026-11-18
- 驗收者：沒有參與這次改動的另一個會話（Claude Opus 5.5，唯讀審查加 FakeOkx 情境）
- 範圍：`git show 6d600094` 的全部差異。`catos/okx_demo.py`、`catos/okx_demo_exchange.py`、`tests/test_demo_bot.py`（FakeOkx 新欄位、`FlattenResendTests`、`RareCaseTests` 的一行改動）、README 與 `docs/next-steps.md` 的說明
- 限制：沒有連 OKX，也沒有開金鑰檔；沒有改 `catos/`、`tests/`；沒有碰 `outputs/`；沒有 commit。測試一律在暫存 HOME 下跑，Kill-Switch、核准紀錄、帳戶鎖都用 `DemoBotTests.setUp` 的隔離路徑
- 情境腳本：`reports/flatten-resend-20261118/scratch/test_acceptance_scratch.py`（20 個情境），輸出在 `scratch/run-output.txt`；拿上一版程式對照的腳本是 `scratch/run_old_2e.py`

## 結論：FAIL

這次改動的方向是對的。「只減倉單帶 expTime、過期一段時間後查不到才算沒收到」在正常時鐘下成立：開倉單完全沒變，重啟後也不會誤證明。問題出在證明和期限都用本機牆鐘（`time.time_ns`）加上快取 5 分鐘的偏移量來算，本機時鐘一跳就會出錯：

- **D1**：本機時鐘往回跳約 5 秒以上，而且之前 5 分鐘內送過只減倉單時，Kill／Hard 清倉的每一張單都會被 OKX 以 50036 拒絕，清倉失敗、部位留著。上一版在同一個情境能清倉成功，所以這是安全功能的退步（已實跑對照）。
- **D2**：本機時鐘往前跳約 10 到 15 秒以上時，證明會在 OKX 的 expTime 還沒到之前就成立，「沒收到」不是真的被證明。
- **D3**：證明套用在所有只減倉單，不只清倉。策略的平倉腿和反手的平倉腿也算在內，但這些路徑拿到 REJECTED 一樣會停下，得不到好處。反過來，萬一判斷錯（OKX 其實已成交），重啟時不會再補查那張單，會直接開新的 run，那筆成交就永遠沒記進帳本。改動前同一個情境會在接續時補查記帳。

D1、D2 是同一個根因，修法很小（見 D1 的建議）。D3 只要把證明限定在清倉路徑，或在非清倉路徑維持 NOT_FOUND 就能解決。

## 整套測試（在 6d600094 上，暫存 HOME）

- `tests.test_demo_bot`：`Ran 65 tests in 97.441s` / `OK`
- `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"`：`Ran 900 tests in 263.109s` / `OK`
- 前端四個指令：沒跑。這次沒有動前端
- 情境腳本：`Ran 20 tests in 24.753s` / `OK`。這些情境的斷言寫的是「目前的行為」，所以 OK 代表缺陷可以重現，不代表行為正確

---

## 重點 1：證明是否成立

### 讀程式

- 期限：`okx_demo_exchange.py:105-108`。只有 `reduceOnly is True` 的單才讀偏移量，期限 = 本機現在時間 + 偏移量 + 5000 ms，而且送出前就記進 `self._deadlines`。
- 偏移量：`okx_demo_exchange.py:71-85`。量 `public/time` 前後的本機時間，來回超過 2000 ms 就不採用（這張單不帶期限），否則取中點；有效期 5 分鐘，用 `_now()`（牆鐘）判斷是否過期。中點估計的誤差不超過來回時間的一半，也就是 1 秒以內，10 秒的餘裕夠用。
- 證明：`okx_demo_exchange.py:87-91`、`246-253`。查詢「送出前」的本機時間加上**目前快取的**偏移量，大於期限加 10000 ms，查不到就回 REJECTED。這裡取送出前的時間是保守的做法（情境 1h）。
- 期限只存在記憶體（`okx_demo_exchange.py:66`），重啟後無法證明，會照舊回 NOT_FOUND（情境 1g）。
- `DemoClient` 用 `_gate` 一次只送一個請求（`okx_demo.py:278`、`302`），所以查詢一定排在那次 POST 的 HTTP 往返結束之後。POST 在 gate 裡排得太久時，送到 OKX 已經過了 expTime，OKX 回 50036，這仍然是「沒處理」，安全。

### 證明成立的前提（程式只寫了其中一個）

1. OKX 確實照 expTime 拒絕：有實測（`exptime-probe.json`：50036、查不到、部位不變）。我沒有另外查官方文件原文，這點沿用實測紀錄。
2. OKX 收下的單在期限後約 9 秒內就查得到：只有一次實測（0.35 秒），屬於假設。程式註解有寫這一點（`okx_demo_exchange.py:15-16`）。
3. **本機牆鐘在「讀偏移量 → 送單 → 查詢」這段時間內沒有跳動**：程式沒寫，也沒有檢查。這就是 D1、D2。

### 情境與輸出（`scratch/run-output.txt`）

| 情境 | 做法 | 結果 |
|---|---|---|
| 1a | OKX 收下但一直查不到（hide_orders），時鐘正常 | 到 t0+15000 還是 NOT_FOUND，t0+15001 變成 REJECTED（`[1a] listing lag 15 s: status=REJECTED ... okx_position=0`）。前提 2 不成立時就會誤判 |
| 1b | 送出後實際只過 1 秒，本機時鐘 +20 秒 | `[1b] okx_server_now - deadline = -4000 ms, status=REJECTED`：OKX 的期限還沒到就判定沒收到（D2） |
| 1c | 偏移量已快取，本機時鐘 +20 秒後才送單 | `[1c] expTime sent = OKX now + 25000 ms (intended 5000)`；`at query: okx_now - deadline = -9999 ms, status=REJECTED`（D2） |
| 1d | `public/time` 來回 2.5 秒 | `expTime header=[None], deadlines={}, status=NOT_FOUND`：不帶期限，照舊 |
| 1e | 快取 5 分鐘 | 3 張只減倉單、跨 300001 ms，`public/time` 只讀了 2 次 |
| 1f | 本機時鐘 -1 小時 | 快取被當成「還不到 5 分鐘」繼續沿用，期限已經在 OKX 的過去，`posts=1`：第二張單被 50036 擋下（D1） |
| 1g | 新的 adapter（等同重啟），1 小時後查 | `status=NOT_FOUND`：無法證明，照舊停下 |
| 1h | 查詢在 t0+14 秒送出、t0+19 秒才回 | `NOT_FOUND`：取的是送出前的時間，保守 |

## 重點 2：誤判時最壞會怎樣

### 會不會加倉或穿越零點

- 每張單都由 Supervisor 建成 `reduceOnly=true`，`execution.flatten` 的張數是 `-position`。OKX 的只減倉單本來就不會增加部位，所以不會穿越零點。程式註解說的「OKX caps it at the position」（`okx_demo_exchange.py:103-104`），也就是張數大於部位時 OKX 會怎麼處理，沒有一手證據，**待驗證**（見 O4）。
- 帳本這一層：`execution.apply` 對只減倉單另有一道檢查，「增加部位或穿越零點」的成交會直接拒收（`execution.py:297`）。
- 誤判後的順序：被誤判的單 A 在期限前已經被 OKX 處理，所以下一輪清倉讀帳戶時，OKX 部位已經是 0、帳本還是 1，會在 `_reconcile` 停在 `position_mismatch`（`demo_bot.py:374`），不會送第二張（情境 2b：`posts=[('buy', False), ('sell', True)]`）。只有在 OKX 的部位顯示也延遲時才會送出 B；但那時部位已經是 0，B 只會被拒，不會加倉。

### 帳本收到 REJECTED 後（情境 2a，正常重送）

```
{'cl_ord_id': 'a08e…', 'quantity': '-1', 'filled': '0', 'state': 'REJECTED', 'settled': 1, 'exchange_id': 'rejecteda08e…'}
{'cl_ord_id': 'fda0…', 'quantity': '-1', 'filled': '1', 'state': 'FILLED',   'settled': 1, 'exchange_id': '4001'}
reservations=0 risk_orders=0, ledger_owned=0, okx_position=0
lost sent at OKX t=1794801911000, expTime=1794801916000; resend at OKX t=1794801927000 (= expTime + 11000 ms)
```

狀態 REJECTED、成交 0、已結清，`_release` 也清掉了保留（`execution.py:309`）。重送用的是新的 clOrdId，而且在 OKX 時間的期限加 11 秒才送，符合設計。

### 之後 OKX 其實有成交，Bot 會不會察覺

- 同一個 run 會察覺：下一次對帳就停在 `position_mismatch`（2b）。
- **重啟後不會察覺**（情境 2c，D3）：上一個 run 的帳本沒有未結清的單，OKX 又是空倉，`demo_bot.py:780` 直接回 None 開新 run。那筆成交（價格、手續費）永遠不會進帳本，新 run 也沒有任何提示：

```
[2c] first run stop=order_rejected okx_position=0 ledger_owned=1 states=['FILLED', 'REJECTED']
     restart stop=manual_kill:… new_run_dir=True
     old ledger after restart: owned=1 states=['FILLED', 'REJECTED']
```

拿上一版程式跑同一類情境（`run_old_2e.py`，2b 情境）：`stop_reason=flatten_failed:order_not_settled:UNKNOWN`、`states=['FILLED','UNKNOWN']`。帳本留著一張未結清的單，重啟時會補查記帳（既有的 `test_a_flat_restart_settles_the_stopped_runs_unknown_order`）。也就是說，誤判把「可以補救的 UNKNOWN」變成了「帳本少一筆、沒有提示」。清倉路徑因為 Kill-Switch 還鎖著，要等使用者解除後才會走到這一步，而且能換到「不必手動平倉」的好處；非清倉路徑則沒有任何好處（D3）。`docs/next-steps.md:93` 寫的「最壞是多送一張只減倉單，Bot 以部位對不上停下」漏了這個後果。

## 重點 3：開倉、加倉維持舊行為

- `okx_demo_exchange.py:105`：只有 `payload.get("reduceOnly") is True` 才讀偏移量。開倉單的 `deadline=None`，不帶 header（`okx_demo.py:292`），也不寫進 `_deadlines`，所以 `_never_taken` 永遠是 False。
- 情境 3a：快取已有偏移量的情況下送開倉單並遺失：`expTime=[None], extra time reads=0, deadlines={}, status 1 h later=NOT_FOUND`。
- 情境 3b：`reduceOnly="true"`（是 truthy，但不是 True）不會拿到期限。
- 50036 被加進全域的 `_REQUEST_REJECTED`，但開倉單不帶 expTime，OKX 不會回這個碼，沒有影響。
- 結論：開倉、加倉的行為沒變（不帶 expTime，UNKNOWN 就停）。成立。

## 重點 4：tag 收緊

- 改動：`okx_demo_exchange.py:228`（條件單）與 `258`（一般委託）都改成必須等於固定 tag，空字串或缺欄位都拋 `ProtocolError`（情境 4a、4b 證實）。
- 一手證據（`scratch/inspect_tags.py` 讀 `reports/okx-demo-protection-check/*.json`）：OKX 模擬盤在 `order-algo` 的 live、effective、canceled，`orders-algo-pending` 的 live，以及 `orders-algo-history` 的 effective 與 canceled，全部回 `tag='41cb53c54d6dABDE'`。一般委託的 filled 單也回 tag（`exptime-probe.json`）。條件單觸發（effective）、protection-check、撤單後補查歷史，這幾條正常流程都有實測支持，不會誤停。
- 接續 run：查的是同一個 Supervisor 用固定 tag 送出的單，路徑相同。`tests.test_demo_bot` 的接續、保底停損與罕見情境測試共 65 個，全部通過。
- 沒有證據的狀態：`order_failed`、`partially_effective` 的條件單，以及一般委託的 canceled／mmp_canceled（例如只成交一部分就被撤）有沒有回 tag（O3）。缺 tag 時 Bot 會以例外停下，不會下單，屬於保守方向。

## 重點 5：測試漏洞

變異測試（情境 5a 到 5c，在 commit 自己的 `FlattenResendTests` 上跑）：

```
[5a] PROOF_MARGIN_MS=-1e12 (proof right away): FlattenResendTests ran=4 failed=0
[5b] _never_taken = 'any deadline' : FlattenResendTests ran=4 failed=0
[5c] deadline in local time (offset 0): FlattenResendTests ran=4 failed=3
```

- 證明完全不等待（一查不到就判 REJECTED），或證明不看時間，commit 的測試都照樣通過。也就是說，「過了期限再 10 秒」這個核心條件**沒有任何測試在守**。只有「期限要用伺服器時間」有測到（5c）。
- `RareCaseTests.lose_the_reversal_close`（`tests/test_demo_bot.py:1151`）加了 `fake.time_failures = 10**9`，好讓舊的斷言繼續通過。但這個情境正是「OKX 收下了、查不到」，拿掉這行就是情境 2c 的誤判。這等於用測試設定把新路徑的風險遮住，而不是另外寫測試記錄它的後果。
- 沒測到的：OKX 列出委託延遲、本機時鐘跳動、重啟後無法證明、非清倉的只減倉單、偏移量快取到期。
- `test_a_flatten_order_that_never_arrived_is_sent_again` 沒有斷言第一張單在帳本裡是 REJECTED、已結清，也沒有斷言重送在期限加 10 秒之後（2a 已補驗，結果正確）。

---

## 缺陷

### D1 本機時鐘往回跳時，Kill／Hard 清倉會整批被 50036 擋下（比上一版退步）

- 位置：`okx_demo_exchange.py:74`（快取的有效期用牆鐘判斷）、`106`（期限 = 牆鐘 + 快取的偏移量）。
- 原因：偏移量是「OKX 時間減本機牆鐘」。本機時鐘往回跳 S 秒之後，快取的偏移量還沒過期（用跳過的時鐘算，還要再撐 5 分鐘加 S），送出的 expTime 比 OKX 現在的時間早 S - 5 秒。只要 S 大於約 5 秒，每張只減倉單都會被 OKX 以 50036 拒絕。
- 重現：`scratch/test_acceptance_scratch.py` 的 `test_2e_backward_clock_step_within_the_offset_cache_fails_the_kill_flatten`。bar 5 反手時的平倉腿把偏移量存進快取；5 分鐘內本機時鐘相對 OKX 往回 10 秒（用 `fake.server_skew = 10_000` 模擬，對 adapter 來說兩者等價）；接著按 Kill。
  - 這一版：`stop=flatten_failed:flatten_incomplete:okx_position=-1`，`states=[…, 'REJECTED' ×5]`，部位留在 OKX 上。
  - 上一版（`git archive 6d600094^ catos` 解到 `scratch/old` 後跑 `run_old_2e.py`）：`stop_reason='manual_kill:…', 'position': '0'`，清倉成功。
- Windows 校時多常往回跳 5 秒以上，**待驗證**（看 w32time 的設定與休眠喚醒的情況）。後果是 Kill-Switch 清倉失敗、要手動平倉。
- 建議：期限與證明都不要用牆鐘。做法一：偏移量改記「讀到的 OKX 時間 + 當時的 `client._monotonic()`」，之後的 OKX 時間用單調時鐘推算，期限和查詢時間點都用這個推算值。做法二：每張只減倉單都重讀 `public/time`（多一次請求，代價大約 0.25 秒）。另外收到 50036 時清掉快取，讓下一輪重讀。

### D2 本機時鐘往前跳時，「證明」在 OKX 的期限之前就成立

- 位置：`okx_demo_exchange.py:87-91`（證明時間 = 牆鐘 + 快取的偏移量，查詢時不會重讀，也不看快取年齡）、`106`。
- 重現：情境 1b（送出後本機 +20 秒，查詢時 OKX 距離期限還有 4 秒，已判 REJECTED）；情境 1c（偏移量快取後本機 +20 秒才送單，expTime 實際比 OKX 現在晚 25 秒，查詢時距離期限還有 10 秒，已判 REJECTED）。
- 後果：這時「OKX 沒收到」並沒有被證明，可能出現重點 2 說的誤判。重送的單一樣是只減倉，不會加倉；但可能出現 2c 那種帳本少一筆的情況。
- 建議：和 D1 一起修。最穩的做法是證明時直接用 OKX 時間：查詢前先讀一次 `public/time`，讀到的值大於期限加餘裕，而且接著的查詢回「不存在」，才算證明。這樣完全不依賴本機時鐘。

### D3 證明套用在非清倉的只減倉單：沒有好處，誤判時會讓重啟跳過補查

- 位置：`okx_demo_exchange.py:105`（條件只有 reduceOnly）；`demo_bot.py:553-555`（非清倉路徑拿到 REJECTED 就停在 `order_rejected`）；`demo_bot.py:780`（沒有未結清的單就開新 run）。
- 重現：情境 2c（就是 `RareCaseTests.lose_the_reversal_close` 拿掉 `time_failures`）。第一個 run 停在 `order_rejected`，OKX 部位 0、帳本 1；重啟後開了新的 `run2`，舊帳本仍然是 `owned=1`，那筆成交沒有記帳，也沒有提示。
- 改動前：同一個情境停在 `order_not_settled:UNKNOWN`，重啟時補查記帳。
- 建議：只在清倉路徑（`flatten_step` 送出的單）允許證明。例如由 Supervisor 或 Bot 告訴 adapter 這是清倉單，或在非清倉路徑把證明出來的 REJECTED 照舊當成 UNKNOWN 處理。另外更正 `docs/next-steps.md:93` 與 README 的「最壞是多送一張」。

## 觀察（不擋交付，建議處理）

- **O1** `public/time` 很慢時，會吃掉 Supervisor 的 5 秒等待時間。讀偏移量包在 `submit` 裡面，而 `submit` 在 `asyncio.wait_for(..., timeout=5)` 之內（`supervisor.py:693`）。情境 2d 讓 `public/time` 實際卡 5.5 秒：`stop=flatten_failed:order_not_settled:UNKNOWN`、`posts=[('buy', False)]`。清倉單根本沒送出，卻被記成 UNKNOWN 而停下；上一版會直接送出。建議在 `flatten_step` 之前先讀好偏移量，或給這次讀取一個比 5 秒短得多的上限。
- **O2** 測試漏洞見重點 5，修 D1 到 D3 時建議把 1a、1b、2b、2c、2e、5a 這類情境寫進正式測試。`RareCaseTests` 那一行 `time_failures` 也要改成明確測試新行為。
- **O3** 條件單在 `order_failed`、`partially_effective` 狀態，以及一般委託在 canceled、mmp_canceled 狀態時有沒有回 tag，模擬盤沒有實測，**待驗證**。缺 tag 會讓 Bot 以例外停下，屬於保守方向。
- **O4** 只減倉單的張數大於部位時，OKX 會縮成部位大小還是整筆拒絕（51169 或其他代碼），沒有一手證據，**待驗證**。程式註解與 next-steps 寫成既定事實。這不影響「不穿越零點」的結論，那是只減倉單本身的語意。
- **O5** POST 成功拿到 ordId，是「OKX 有收到」的直接證據，但 `_deadlines` 沒有因此移除。目前 Supervisor 等 5 秒就放棄，而證明至少要 15 秒，所以在 `submit` 裡面碰不到這條路；之後若調整逾時，就可能出現「明明送成功卻判 REJECTED」。建議送成功時 `self._deadlines.pop(cl_ord_id, None)`。

## 沒跑的項目

- 沒有連 OKX 模擬盤（限制），所以 OKX 列出委託的延遲、expTime 檢查發生在哪一層、O3、O4 都只能根據既有實測紀錄判斷，或標「待驗證」。
- 沒有自己查 OKX 官方文件的原文，expTime 的語意沿用 `exptime-probe.json` 的實測。
- 前端四個指令沒跑（這次沒有動前端）。
- 上一版程式只拿 2b、2e 兩個情境做對照，2c 的舊行為以既有測試 `test_a_flat_restart_settles_the_stopped_runs_unknown_order` 為準。對照時解出來的 `scratch/old/` 跑完後已刪除，重建指令寫在 `run_old_2e.py` 開頭。

## 整套測試結果

`T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"`：`Ran 900 tests in 263.109s` / `OK`。這套測試本身會在 `outputs/workspace-w6-fixture-test-*`、`workspace-w8-fixture-test-*` 留下 fixture 證據（測試原有行為，不是正式資料根）。過程中印出的 `Port 65514 already in use` 也是測試本身在驗證埠被占用的情況。
