# 下一步

更新：2026-11-18。2026-11-17 前的完整沿革（研究線、工作包 A～F、v1 驗收、repo 重建、兩台機器分工）在 `docs/archive/next-steps-20261117.md`，本頁只寫現況。

## 現況

- v1 local-sim、研究線、工作包 B（Kill-Switch 與新風控預設）都已完成並合併進 `main`。
- **M1 接 OKX 模擬盤**：程式完成、在模擬盤實測、獨立驗收通過（有觀察）。使用者 11-17 已核准正式設定並啟動正式 Bot，見下方「正式 Bot」。

| 步驟 | 內容 | 狀態與證據 |
| --- | --- | --- |
| 1 | 模擬盤用戶端、`demo status` | 完成。桌面金鑰檔第 2 組可用（子帳戶、讀取＋交易、net_mode）。讀到 5,000 USDT |
| 2 | `demo first-order` 開倉再平倉 | 完成。ordId 4105011010260422656／4105011044586606592，權益變化等於成交損益加手續費 |
| 3 | 策略 Bot `demo bot`，逐根 K 線經 Supervisor 下單 | 完成。11-16 用隔離核准跑 5m：買 1 張，ordId 4105099728749056000，12 筆成交全部入帳。11-17 修正後又跑一次：買 1 張，ordId 4105945336137371648 |
| 4 | Kill／Hard 在模擬盤平倉 | 完成。11-16 Kill 後 4 秒平倉（ordId 4105108293048061952）；11-17 修正後同樣 4 秒平倉（ordId 4105971616673157120，14 筆成交），部位 0 |

## 正式 Bot（2026-11-17 起）

- 使用者本人核准：`approval_id=10d7846fe1adfef05a5e25825c7d884d`（15m、Donchian 192／48、1 張、本金 5000）。
- 現在的 run：`outputs/okx-demo-bot/fa778156c1444ef8a278757a61d95db9`，11-18 17:00 台北時間由代理照使用者「重開正式 Bot 要做」以 `--disaster-stop 10%` 在新視窗重開（程式 a7f89789，含 6 個少見情況修正），空倉、預熱完成。之前的 run：`e96edaec…`（11-18 13:36 到 13:39，為了 P6 觸發實測以 stop.request 停下）、`1e5a3848…`（11-18 13:24 到 13:33，為了 P6 實測以 stop.request 停下）、`63e5c1a1…`（11-17 11:21，舊版 e09da051）、`d3ad9901…`（11-17 17:04 到 23:27，217 根、0 成交）、`9630e8f5…`（11-17 23:27 到 11-18 13:24，a5ee0b0c，約 244 根、0 成交，Ctrl+C 停下）。
- 第一筆成交是 P6 條件單在模擬盤的第一次實測：看 `events.jsonl` 的 `protection`／`protection_alert` 事件，並在 OKX 網頁核對條件單（觸發價、方向、整倉）。
- P6 模擬盤實測（2026-11-18 13:33，`python -m catos.cli demo protection-check`，紀錄 `reports/okx-demo-protection-check/1794979993705.json`）：等 Donchian 成交太慢，改成一次性實測。Bot 以 stop.request 停下（空倉），用 Bot 同一個轉接層開最小張數 0.01 張，均價 64820。結果：
  - 掛單：`order-algo` 回的欄位和程式照 SDK 寫的一致（`state`、`side`、`slTriggerPx`、`slTriggerPxType=mark`、`slOrdPx=-1`、`closeFraction=1`、`reduceOnly="true"`、`sz` 空字串、`tag` 保留），轉接層判定 LIVE、價格 58338 相符。
  - 改價：`amend-algos` 成功，algoId 與 algoClOrdId 不變，價格改到 57041.6。
  - 平倉後 OKX 自動撤掉整倉停損（第一次查就是 canceled）；`order-algo` 仍回這張單（code 0，不是 51603），`orders-algo-history` 的 canceled 也有；轉接層判定 CANCELED。結束時空倉、沒有條件單。
  - 觸發（2026-11-18，`demo protection-check --trigger`，紀錄 `reports/okx-demo-protection-check/1794980390196.json`）：把觸發價設在現價附近讓 OKX 觸發。`order-algo` 回 `effective`，`orders-algo-history` 的 effective 也有，轉接層判定 TRIGGERED，觸發後部位 0。觸發後 OKX 會把 `sz` 填上成交張數，所以「被改成部分張數」只看 `slOrdPx` 與 `closeFraction`。
  - 沒測到：觸發失敗、幾小時後的查詢結果、改單被拒。
- 唯讀核對工具：`.venv/Scripts/python.exe tools/demo_bot_watch.py`（只讀 run 資料夾，依成交重算均價與停損價，對照 Bot 寫的 `protection` 事件）。2026-11-18 起 T3 排程「模擬盤 Bot 保底停損核對」每小時跑一次，狀態檔在 `outputs/demo-bot-watch/state.json`；11-18 改用主動實測後已暫停這個排程。
- 帳戶紀錄 `~/.catos/okx-demo-accounts/dfa73b44….json` 在 11-17 11:21 新建，之後的 run 沿用。
- 看狀態：讀 run 資料夾的 `status.json`、`events.jsonl`。停止：Ctrl+C（部位保留）、run 資料夾建 `stop.request`，或 `kill engage`（會平倉，之後要使用者解除）。
- 重新啟動：`.venv\Scripts\python.exe -m catos.cli demo bot --profile catos\deployment_profiles\donchian-breakout-15m-192-48.json --disaster-stop 10%`。有部位時會接續同一個 run（限制見「已知缺口」）；核准仍有效就不用重做。

## M1 獨立驗收（2026-11-17）

- 第一輪 FAIL：`reports/okx-demo-m1-acceptance-20261117/acceptance.md`。下單出口、UNKNOWN 不重送、成交入帳、憑證、Decimal 都通過。不通過的是四個缺陷：
  - D1：清倉途中讀取失敗一次就放棄，部位留著。
  - D2：Soft／Hard 鎖存與當日基準只存在單次 run，同日重啟就重設。
  - D3：沒看其他合約的部位。
  - D4：同一個帳戶可以同時跑兩個 Bot。
- 修正：
  - D1：讀 OKX 會退避重試，清倉中重試約 2 分鐘。
  - D2：帳戶紀錄放在 `~/.catos/okx-demo-accounts/`，存當日基準與 Soft 鎖存，重啟和換 output root 都沿用。紀錄遺失或損壞就拒絕啟動。Soft 只能由使用者用 `demo rearm` 解除。Hard 會寫入共用的 Kill-Switch 紀錄，來源是 `demo-bot`。
  - D3：讀整個帳戶，其他合約有部位或掛單就視為陌生部位。
  - D4：用 OKX uid 的檔案鎖，一個帳戶只能跑一個 Bot。
  - 另外依觀察補了幾項：有部位時每分鐘看一次帳戶；等 K 線期間也檢查 Kill；反手的第二腿被 Soft 擋下時以空倉繼續跑；只允許 BTC-USDT-SWAP；手續費不是 USDT 就不結清；清倉失敗時 CLI 回 2。
- 第二輪重驗 PASS（有觀察）：`reports/okx-demo-m1-acceptance-20261117/recheck.md`，D1～D4 都用驗收者自寫的情境重現過。這輪找到 N1（帳戶檔被刪除會當成首次建立）與 N2（帳戶檔跟著 output root 走），已依上面的方式修正。
- 第三輪重驗 PASS（有觀察）：`reports/okx-demo-m1-acceptance-20261117/recheck3.md`。N1、N2 修好，D1～D4 沒有回歸，沒有新缺陷。之後依觀察 O1～O4、O6 補了以下幾項，只有開發者自測：
  - 第一次寫帳戶紀錄失敗時不留下鎖檔。
  - 建 run 失敗會關掉 log。
  - 關閉 Supervisor 失敗時仍會釋放鎖。
  - Ctrl+C 後 `status.json` 寫成 stopped／interrupted。
  - 啟動被拒時附上處理提示。
- 還沒處理的觀察：
  - O5：任一帳戶檔損壞時，`demo rearm` 整個停下。
  - O7：少數啟動例外仍會印 traceback。這時鎖已釋放，也還沒下單。
- 驗證：後端整套與前端四項檢查見 commit 訊息。

## 代理決定（可推翻）

- 帳本沿用 local-sim 的資料庫結構與標籤，不改 schema；實際交易所記在 run 的 manifest。
- P1 核准涵蓋模擬盤 Bot，只認 2026-11-16 之後的核准。
- 錯過後補處理的 K 線只更新策略狀態，不下單。接續 run 也一樣：停下期間的 K 線只補進策略，只有最新收盤的那根可以下單（可能在收盤後最多 15 分鐘才執行）。
- 接續 run 最多補 299 根 K 線（OKX `market/candles` 一頁），更長就不接續，不新增 `history-candles` 端點。
- 接續時，使用者停機期間做的 `demo rearm` 也套用到接續的帳本（虧損仍超過 Soft 時不解除）；只認 run 停下之後的 rearm，沒有就維持鎖住並把帳戶紀錄補回（獨立驗收 E1）。
- Hard 寫入 Kill-Switch 紀錄、Soft 跨日也保持鎖住：原屬代理決定，2026-11-17 使用者確認保留。上實盤或加大張數前再談是否改成「隔天自動解除＋累計虧損上限」。
- 入金會掩蓋虧損：外部資金流在模擬盤階段不分類（使用者 11-16 第 3 題），模擬盤上不要入出金。

## 已知缺口

- 接續 run 的限制：帳戶紀錄只記最後一個 run，11-17 之前開的 run 沒有這筆紀錄，帶部位停下時仍要先平倉；接續的前置步驟（查舊委託、等舊委託期限）最壞約 2 分鐘不檢查 Kill-Switch，期間不送新單；Bot 停著時按 Kill 不會平倉；接續只比對張數，停機時手動平倉再開同樣張數分辨不出來；補進策略的 K 線上的反手或出場訊號不補做，部位要等下一個訊號才回到和策略一致；程序被直接殺掉後再接續，`fills.json` 會少算（帳本完整）；部位為 0 時若寫 Soft 到帳戶紀錄失敗，重開是新的 run，Soft 鎖住會遺失（同一天虧損仍超過 5% 時下一根會再鎖；重驗觀察 O1）；查不到結果的舊委託（OKX 回「不存在」）會讓接續停下，要手動處理；OKX 已空倉時可加 `--new-run` 開新 run（舊帳本保留、不結清）。
- 跨家第二意見（2026-11-18，Gemini 4 Hydrogen xhigh，P6 與反手只平倉各一份唯讀審查）：主控逐條核對後，有 3 條成立並已修（`tests/test_demo_bot.py` 的 `ReviewFixTests`）。獨立驗收（Claude Opus，`reports/gemini-review-fixes-acceptance-20261118/acceptance.md`）PASS，找到 D1（撤單後查一次查不到就停止輪詢）與觀察 O1、O2；Gemini 同時做的第二意見也找到 D1、O1，另外還有「對帳時第一次出現的告警沒寫事件」。這四項都已修，窄範圍重驗 PASS、沒有新發現（`recheck.md`）。正式 Bot 已於 11-18 13:24 重開、用上這些修正：
  - 已結束的保底停損用 `order-algo` 查不到（51603）時，帳本會一直「待確認」、之後不能開倉。現在撤單與查詢時改查 `orders-algo-history`（使用者 11-18 授權）。只查每種狀態最近 100 筆。11-18 模擬盤實測（見下方「P6 模擬盤實測」）：平倉後 OKX 會自動撤掉條件單，已結束的條件單幾秒內 `order-algo` 仍查得到（code 0、state canceled），history 也查得到；幾小時後 `order-algo` 是否改回 51603 仍待驗證。
  - 部分成交後被撤：以前會直接停下、不記成交、不掛停損。現在記帳、對帳、掛停損之後才停下（`order_partially_filled:canceled`），重開會接續。
  - 改條件單被 OKX 拒絕（51xxx）時，以前會被當成「沒回應」，提示來回跳；現在單子還在就記成「被拒」、下次檢查重試。撤條件單遇到 51xxx（例如剛好已撤）改成接著查結果。
  - 核對後不成立：`closeFraction` 和 `reduceOnly` 並存會被拒（OKX 文件寫 net 模式必須帶 `reduceOnly=true`）；對帳拿帳本比帳本（`demo_bot.py` 先比對 OKX 列出的條件單）；接續時同一次呼叫撤舊單又掛新單、跳過對帳（第二步會因為還沒對帳被拒，下一次檢查會補上）；停損觸發的瞬間加倉（這份部署的目標只有 -1、0、+1）。
  - 當時成立但沒修的 6 個少見情況，11-18 使用者要求修（「做第 2 項、修那 6 個少見情況」），已修，測試在 `tests/test_demo_bot.py` 的 `RareCaseTests` 與 `tests/test_execution.py`。獨立驗收（Claude Opus，`reports/rare-cases-acceptance-20261118/acceptance.md`）FAIL 在 D1（見第 6 項），修好後窄範圍重驗 PASS（有觀察，`recheck.md`）。Gemini 第二意見（`gemini-second-opinion.md`）也找到 D1，另外找到 O4（見下），已修，窄範圍重驗 PASS（`recheck-o4.md`，21 個情境修前修後逐項相同）：
    1. 平倉單結果不明時停下、重開時 OKX 已空倉：以前開新 run，舊委託永遠沒結清。現在帳本有沒結清的委託就接續那個 run 先查清楚；不能接續（核准或設定改過、停太久、讀不到）就開新 run，並在新 run 寫 `previous_run_unsettled` 事件；啟動指令加 `--new-run` 可強制開新 run。
    2. 決策到送單之間風控改變（epoch 變了）：以前只減倉意圖一律作廢、Bot 停下。現在只要目前狀態仍核准這筆減倉、且不是 FLAT（FLAT 走清倉流程）就送出；加倉照舊作廢。測試時另外發現：Soft 剛好在反手決策後鎖住時，反手的平倉腿也被作廢、Bot 帶著部位停下；改成平倉腿照送、開倉腿照舊被擋（同 11-17「反手被擋時至少平倉」）。
    3. 條件單在 OKX 上被改成限價或部分張數：以前看不出來。現在看 `slOrdPx`／`closeFraction`，以及 live 狀態卻有 `sz`（驗收 O1；真實改單長什麼樣待驗證），被改過就記 `protection_altered`、視為未確認、禁止加倉，請使用者到 OKX 撤掉，Bot 下次檢查重掛。
    4. 只改觸發來源（價格不變）的改單：以前第一次查詢就當完成，現在要查到觸發來源也一致。
    5. OKX 回空的觸發來源：以前是程式錯誤，現在當成 OKX 預設的 last（請求端文件如此，回應端待驗證），會被改回 mark。
    6. 接續時新比例裝不上：以前該次檢查仍用舊比例掛或改單。第一版改成「不掛不改、之後再裝」，驗收 D1 指出空倉時 OKX 會自動撤掉停損，帳本就不擋加倉，反手會開出沒有停損的部位；改成和全新啟動一樣直接停下（`protection_config_failed`），部位與 OKX 上已確認的條件單都留著。
    - 驗收其他觀察：被改過的條件單使用者不撤，帳本一直「不確定」，空倉重開會被 `contract_not_flat_at_start` 擋（O3，維持；a7f89789 起只寫 `protection_altered`，不再另外顯示「OKX 沒回應」的告警）；反手決策後立刻變 FLAT 時 Bot 以 `dispatch_returned_nothing` 停下、不清倉，既有行為（O4）；`--new-run` 不讀舊帳本的 Soft 鎖住，只在當初寫帳戶紀錄失敗時有差（O5，維持，已寫進 `--new-run` 說明；另補上 `risk_flat` 的停下提示）；讀不到上一個 run 時改成寫 `previous_run_unreadable` 事件（O6，已改）。
    - Gemini O4（修之前就有）：接續時上一次 run 留著沒確認的停損請求，而且停機期間漏了 2 根以上 K 線時，兩步保護處理（先確認舊的、再撤掉或改掛）會讓帳本停在「待對帳」，補 K 線時 Bot 以 `failed` 結束（沒有下單）。改成看帳本有沒有被標記待對帳，而不是只比對前後有沒有停損（`ResumeProtectionMarkTests`）。Gemini O1 的 `pause` 狀態也算進「有張數＝被改」。
    - 重驗觀察 O7：已實測（11-18 17:00，`reports/okx-demo-protection-check/1794992422997.json`）。`orders-algo-pending` 列表裡整倉停損是 `sz` 空、`slOrdPx -1`、`closeFraction 1`，`altered_stop` 判定沒被改，不會誤報。protection-check 之後每次都記這份列表。
- 保底停損（P6）的限制：掛、改價、平倉後自動撤單、觸發（effective）已在模擬盤實測（上方「正式 Bot」的 P6 模擬盤實測）；觸發失敗沒有實測；OKX 觸發後 Bot 只停下，不把那筆平倉補記進帳本（使用者 11-17 選「停下並提示」）；陌生委託只查 SWAP 的四種條件類委託（conditional／oco／trigger／move_order_stop），冰山與時間加權委託沒查。
- 保底停損的其他限制：建立或撤單請求沒送到 OKX 時，帳本一直「不確定」，這個 run 之後都不加倉（出場與清倉不受影響），要等空倉重開，提示裡的「會繼續查」不會有結果；停損觸發但沒完全成交時 Bot 只停下說明、要使用者手動平倉（帳本已對不上，不判斷 Hard）；查詢故障期間觸發，停下原因會是 `position_mismatch`；條件單方向在 OKX 上被改時每次檢查都送改單（OKX 介面不能改方向，實際難遇到）；revision 用牆鐘，重啟時系統時鐘若倒退，run 會以錯誤結束（不多送東西）。
- 測試衛生：2026-11-18 起整套後端測試不再寫進真的 `~/.catos`（最後兩個漏網的是 `test_strategy_folder` 的重播、`test_kill_switch` 的控制面與重播；以暫存家目錄跑整套後檢查為空）。`~/.catos/local-simulation-locks` 的舊鎖檔已整理（11-18，使用者同意）：綁定的資料庫已不存在的 799 個移到 `~/.catos/local-simulation-locks-archive-20261118/`（沒刪，可搬回），資料庫還在的 59 個（含正式 Bot 各 run）留著。正式 Bot 的鎖在同一個資料夾，不要整個刪。
- 介面沒有 Bot 畫面，等前端定案再接。
- 正式對帳的核心（`okx_readonly`、`okx_collection`、`account_report`、`reconciliation_gate`、`risk_period`）保留給實盤前的手續費與資金費分類，目前沒有接到執行中的路徑。
- 驗收觀察，沒有處理：
  - 送單請求最壞的耗時會超過 Supervisor 的 5 秒等待。超過時記成不確定，再查詢結清，結果仍正確。
  - 清倉單送出時遇到 503：2026-11-18 起 Kill／Hard 清倉的只減倉單帶 OKX `expTime`（送出前現讀 OKX 伺服器時間加 5 秒）。之後查不到時再讀一次 OKX 時間，超過期限 10 秒以上、再查一次仍查不到，才判定 OKX 沒收到，下一輪清倉送新單（`okx_demo_exchange.py`，`FlattenResendTests`）。策略平倉、反手、開倉加倉都不帶期限，狀態不明照舊停下。模擬盤實測過期請求回 `50036`、不處理，正常單第一次查詢就查得到（`reports/flatten-resend-20261118/`）。前提是 OKX 收下的單立刻查得到；不成立時會多送一張只減倉單，Bot 在下一輪清倉讀到部位對不上而停下（OKX 對超量只減倉單怎麼處理，待驗證）。獨立驗收第一輪 FAIL（D1 本機時鐘倒退會讓清倉單全被拒、D2 證明用本機時鐘、D3 證明也套用到策略平倉），已修，待窄範圍重驗。觀察：讀 OKX 時間很慢時會吃掉 Supervisor 的 5 秒等待，這張單就變成無法證明、照舊停下（O1）。
  - OKX 回報空的 tag：2026-11-18 起不接受（實測我們的單都會回 tag）。
  - 8770 服務：11-18 確認沒在跑，下次啟動就是看得懂 `demo-bot` 來源的新版。
- 策略資料夾（Agent 提交策略）：
  - 研究資料夾最多 200 次研究結果（`MAX_RUNS`），Agent 反覆試驗會用完，要由使用者清理，沒有清理指令。
  - 滾動驗證沒有「含累計試驗次數的 DSR」，只有優化有。
  - 重啟一致性檢查用合成資料：沒有成交的路徑檢查不到，結果會提示。它逐根比對「只看最近 lookback 根重建」與「看過全部歷史」的決策，但不模擬重建後繼續跑幾根，所以是上 Bot 前的必要條件，不是充分條件。
  - 已核准的資料夾策略被改或被刪，只有用那筆核准的 Bot 會停（不平倉）；要繼續就重新核准新版本。其他核准不受影響。
  - 重啟一致性最多花 15 秒逐根比對。update 很慢的策略比不完時，結果寫明比到第幾個，核准會被拒。實測每根重算 512 根均線的寫法 8.6 秒比完。
  - 試用者驗收（`reports/agent-strategy-acceptance-20261117/trial-user.md`）提出、還沒做的改善：
    - 買進持有基準加最大回撤與 Sharpe。
    - 送出後可以等待結果，不用輪詢。
    - 優化格點支援列出值，不只等差。
    - 部署設定的唯讀預檢指令。
    - `regime_rule` 依週期給預設值。
- 其他小缺口沿用舊清單：`docs/archive/next-steps-20261117.md`「已知小缺口」。

## 等使用者決定

- 前端方向（另一個對話在出 X／Y／Z 草稿）。
- 第 6 步（同幣種多策略）的做法草案，見封存檔。

## 工作順序（2026-11-17 使用者「按照你建議執行」）

1. 接續 run：Bot 停下時有部位，重開能接著跑。完成（2026-11-17）：獨立驗收 FAIL（E1：帳戶紀錄寫入失敗時接續會自動解除 Soft），修正後窄範圍重驗 PASS；報告 `reports/okx-demo-m1-acceptance-20261117/resume-acceptance.md`、`resume-recheck-e1.md`。只用假 OKX 測過，沒有在模擬盤實測接續（正式 Bot 在跑）。驗證：後端 `Ran 1005 tests`、`OK (skipped=11)`；前端 typecheck 0 錯誤、21 項通過、build 成功；整合測試 13 項 PASS。
2. 讓 Agent 提交策略：使用者 2026-11-17 回覆「完全同意你的所有建議」。完成（2026-11-17）。實作見 `docs/agent-strategy-submission-proposal.md` 末節「實作紀錄」，Agent 用法見 `strategies/README.md`。
   - 獨立驗收：第一次 FAIL，缺陷有三個：
     - D1：改已核准的資料夾，整份核准紀錄跟著失效。
     - D2：檢查沒有重現 Bot 的 `ready` 規則。
     - D3：重播比對讀的是資料夾的新版本。
   - 修正後窄範圍重驗 PASS；重驗提出的觀察 O-A～O-C 也已處理。
   - 另開一個 Agent 扮演試用者，只靠 README 和 MCP 走完「寫策略 → 檢查 → 4H 回測 → 優化 → 滾動驗證」。前 5 項摩擦裡，4 項已改成文件、錯誤訊息或 MCP `fields` 參數；部署設定預檢與其他建議列在上面「已知缺口」。
   - 報告都在 `reports/agent-strategy-acceptance-20261117/`。
   - 使用者還沒核准任何資料夾策略：核准、重播或上模擬盤由使用者本人做，步驟在 `strategies/README.md`。
   - 驗證（commit 6c2d2b8c）：後端 `Ran 1016 tests`、`OK`；前端 typecheck 0 錯誤、22 項通過、build 成功；整合測試 13 項 PASS。
   - 正式 Bot 已由使用者在 11-17 23:27 用 a5ee0b0c 重開，接續 run、新的核准檢查與 P6 都在用。
3. P6 交易所端保底停損：2026-11-17 使用者要求現在做，三題選建議（10%、觸發後停下並提示、啟動指令加 `--disaster-stop`）。程式與假 OKX 測試完成（`DisasterStopTests` 11 項）。獨立驗收第一次 FAIL（D1：停損沒確認時 Kill／Hard 不清倉），修正後窄範圍重驗 PASS（有觀察），重驗提出的兩則訊息問題（N1、N2）由開發者修好、只有自測；報告 `reports/p6-cleanup-acceptance-20261117/acceptance.md`、`recheck.md`。同一份驗收也驗了第 5 項的清理：通過。沒有在模擬盤實測。帳本的保護狀態機原本在保護「暫時不一致」的瞬間把待送的加倉意圖永久作廢，會讓反手的開倉腿消失；改成只在決策與送單時檢查（兩處原本就有），屬帳本改動，列入驗收。
   - 2026-11-17 使用者對驗收觀察回覆「改」：反手被加倉閘門擋下時照樣平掉原部位，只拒絕反向開倉（`reversal_close_only`，改在 `risk.py`、`journal.py`、`execution.py`）。獨立驗收：風控核心正確（新舊版約 216 萬組輸入比對，沒有任何組合會加倉或穿越零點），但 FAIL 在 local-sim 重播不認得新判定（D1）；修好後窄範圍重驗 PASS（有觀察），重驗提出的「最後一根只平倉時一致性誤報通過」（N1）由開發者修好、只有自測。報告在 `reports/reversal-close-only-acceptance-20261117/`。使用者 rearm 之後下一根才開反向倉，開倉價和研究回測不同（驗收觀察 O3）。
4. Bot 的介面：等前端定案。
5. 拆掉九月模組：2026-11-17 使用者要求做。刪掉 Demo 連線（`okx_http`、`demo_collection`）、帳本綁定（`demo_ledger_*`）、E0 對帳流程（`demo_reconciliation`、`demo_production_inputs`）、一次性交易授權（`trade_authorization` 與 Supervisor／execution 裡的授權碼）、兩個 tools 與對應測試，約 6,600 行；正式對帳核心保留（見已知缺口）。資料庫結構不變。
