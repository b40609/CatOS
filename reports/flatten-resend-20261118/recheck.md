# 窄範圍重驗：D1 到 D3、O2、O5 的修正（commit bdb645bc）

- 日期：2026-11-18
- 驗收者：與第一輪是同一個獨立會話，沒有參與修正
- 範圍：`git show bdb645bc` 中的 `catos/okx_demo_exchange.py`、`catos/demo_bot.py`、`tests/test_demo_bot.py`、`docs/next-steps.md`
- 限制與第一輪相同：沒有改 `catos/`、`tests/`，沒有 commit，沒有連 OKX，沒有讀金鑰，暫存 HOME，沒有碰 `outputs/`
- 情境腳本：`scratch/test_recheck_scratch.py`（14 個測試，其中一個包含 6 組變異），輸出在 `scratch/recheck-output.txt`

## 結論：PASS（有觀察）

D1、D2、D3、O5 都已修好，O2 大致補上。這次沒有新的缺陷。剩下三條觀察：OR1 是一個測試缺口，OR2 很輕微，O1 依指示只寫進文件、沒有修。

## 修法讀程式

- 期限：`okx_demo_exchange.py:97-98`。只有在 `self.flattening` 為真、而且是只減倉單時，才現讀 OKX `public/time`，期限 = 讀到的值 + 5000。不快取，也不用本機時鐘（整個檔案已經沒有 `_clock_ms` 或 `_now`）。讀到的時間如果是舊的，期限只會更早，最壞是 OKX 回 50036（拒收、不處理），所以是安全的方向。
- 證明：`okx_demo_exchange.py:74-83`。第一次查詢回「不存在」之後，現讀 OKX 時間，必須大於期限 + 10000；然後**在讀到時間之後**再查一次，仍然不存在才成立。第二次查詢是在 OKX 時間已經超過門檻之後才送出，所以整個證明只依賴 OKX 自己的時鐘。讀時間失敗就不證明（`_server_ms` 回 None）。
- O5：`okx_demo_exchange.py:103`。POST 拿到 ordId 後就移除這張單的期限。
- D3：`OkxDemoExchange.flattening` 預設是 False（`:64`），只有 `DemoBot._flatten` 會設成 True（`demo_bot.py:586`）。我逐一檢查了 `_flatten` 的五個呼叫點（`demo_bot.py:562`、`640`、`661`、`997`、`1065`），每一個之後都緊接 `raise BotStopped`。旗標設下去之後，這個 run 不會再有非清倉的下單，所以不重設也沒問題。重啟後是新的 adapter：旗標是 False、期限紀錄是空的，照舊無法證明。

## 每一項重跑的結果（`scratch/recheck-output.txt`）

| 項目 | 情境 | 第一輪 | 這次 |
|---|---|---|---|
| D1 | bar 5 反手後的 5 分鐘內，本機時鐘相對 OKX 倒退 10 秒，然後按 Kill | `flatten_failed:flatten_incomplete:okx_position=-1`，5 張 REJECTED | `[d1] stop=manual_kill:… okx_position=0 states=['FILLED'×4]`，清倉成功 |
| D2（1b） | 送出後實際只過 1 秒，本機時鐘 +20 秒 | REJECTED（OKX 的期限還沒到） | `[r1b] okx_now-deadline=-4000 status=NOT_FOUND` |
| D2（1c） | 本機時鐘 +20 秒之後才送單 | expTime 比預期晚 20 秒，提早證明 | `[r1c] expTime-sent=5000`，OKX 時間過了 15.001 秒才 REJECTED（drop_posts，確實沒收到） |
| D2（變化） | 清倉期間本機時鐘一直比 OKX 快 40 秒，第一張清倉單遺失 | 沒有這個情境 | `[r2a]` expTime = OKX 時間 + 5000；重送在 expTime + 11000 ms（OKX 時間），帳本 `REJECTED/settled/0`，保留 0，部位 0 |
| D3（2c） | 反手的平倉腿被 OKX 收下但回應遺失，而且查不到 | `order_rejected`；重啟開新 run，成交沒記帳 | `[r2c] first stop=order_not_settled:UNKNOWN expTimes=[None, None]`；重啟後接續原 run（沒有建立 run2），fills 有「接續時補查」，`owned=0` |
| D3（各種組合） | flattening 與 reduceOnly 的四種組合，遺失後 1 小時再查 | 沒有這個情境 | `[r3]` 只有 (True, True) 帶 expTime 並證明 REJECTED，其他三種都不帶 expTime、維持 NOT_FOUND |
| O1（2d） | `public/time` 實際卡 5.5 秒 | 清倉單沒送出就記成 UNKNOWN 而停下 | 不變：`[r2d] stop=flatten_failed:order_not_settled:UNKNOWN posts=1`（依指示不修，`docs/next-steps.md` 已寫明） |
| O5 | POST 正常回應 | 期限留著 | `[o5] status=FILLED deadlines={}` |
| 前提 2 | OKX 收下但一直列不出來（1a、2b） | 期限 + 10001 ms 判 REJECTED；清倉停在 position_mismatch | 一樣：`[r1a]`、`[r2b] stop=flatten_failed:position_mismatch:okx=0:ledger=1 posts=2`。這是文件寫明的前提，影響只在清倉路徑，而且 Kill-Switch 仍鎖著 |
| 其他 | 讀時間一直失敗（`[r1e]`）、重啟後的新 adapter（`[r1f]`） | 沒有這個情境 | 都是 NOT_FOUND，不證明 |
| 其他 | 第一次查不到，但第二次查詢前訂單已列出（`[r1d]`） | 沒有這個情境 | 不會判 REJECTED；這一輪回 NOT_FOUND，下一輪查到 FILLED |

## 變異測試：commit 的 `FlattenResendTests`（7 個）會不會被騙

```
[mut] PROOF_MARGIN_MS=-1e12 (no waiting): ran=7 failed=2 [test_a_late_listing_inside_the_margin…, test_the_proof_waits_for_okx_time…]
[mut] _never_taken = any deadline:        ran=7 failed=2 [同上]
[mut] proof by local clock (round-1 D2):  ran=7 failed=2 [test_the_deadline_follows_okx_server_time, test_the_proof_waits_for_okx_time…]
[mut] no second query after the time read: ran=7 failed=0 []
[mut] every reduce-only gets a deadline (round-1 D3): ran=7 failed=1 [test_a_strategy_close_gets_no_deadline]
[mut] deadline kept after an ordId (O5 reverted): ran=7 failed=0 []
```

第一輪那類變異（不等待、不看時間、用本機時鐘、套用到所有只減倉單）現在都會被抓到。沒被抓到的兩項見 OR1。

## 整套測試（bdb645bc，暫存 HOME）

- `.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"`：`Ran 903 tests in 285.261s` / `OK`
- 重驗情境：`Ran 14 tests in 68.621s` / `OK`。斷言寫的是預期的正確行為；只有 r1a、r2b 斷言的是文件寫明的前提限制。
- 前端：沒跑，這次沒有動前端。

## 觀察

- **OR1 測試缺口：第二次查詢與 O5 都沒有測試在守。** 拿掉「讀時間後再查一次」，或把 O5 改回去，7 個測試都照樣通過。第二次查詢是證明成立的必要條件：沒有它，第一次查詢可能在 OKX 時間到門檻之前就送出，有效餘裕會少掉一次請求的間隔（至少 0.25 秒，最多到 Supervisor 的 5 秒）。O5 目前碰不到（證明至少要 15 秒，送單最多等 5 秒）。建議補一個測試：第一次查詢回「不存在」，讀時間時才讓訂單列出（做法同 `[r1d]`），斷言不可以 REJECTED。
- **OR2 第二次查詢查到訂單時，這一輪的證據被丟掉。** `_never_taken` 只回傳 True 或 False，所以第二次查到了，`_report` 還是回 NOT_FOUND（`[r1d]`）。下一輪會再查到，結果正確，只是多一輪。屬於保守方向，不必修。
- **O1（沿用，不修）**：讀 OKX 時間很慢時，會吃掉 Supervisor 的 5 秒等待，清倉單沒送出就變成 UNKNOWN 而停下。已寫在 `docs/next-steps.md:93`。
- **其他**：bdb645bc 一起 commit 了 `reports/flatten-resend-20261118/scratch/__pycache__/test_acceptance_scratch.cpython-314.pyc`（二進位快取檔），建議移出版本控制。另外，這次的重驗報告與 `test_recheck_scratch.py` 都在被 `.gitignore` 的 `reports/` 底下，沒有 commit。
