# W6 A／B 唯讀獨立驗收

2026-10-01（台灣時間）。指定 5.6 Sol (Web) 依既有 W6 提案、交接與保存原始證據進行唯讀獨立驗收。結果：**PASS**。本輪未建立任何新 simulation run，未重跑 A／B、未 POST 控制命令、未解除 recovery／latch、未開歷史 DB、未重跑 R4／研究、未執行 Git。

## 驗收方法

- 直接讀取 `outputs/workspace-w6-20261001/` 的 before／after、browser observations、19 次獨立 GET、retry 前後終態、fixture command/storage/UI 與服務 log；未採信開發者 36/36、18/18 結果作為結論。
- 以純 stdin Python 重新計算 40 項核心斷言，全數 PASS；過程只讀既有檔案，不呼叫服務、不產生新 run 或新輸出。
- 直接檢視 `a-completed-details.png`、`b-pending.png`、`b-stopped.png`：A 顯示 8/8 根、4 成交；B pending 顯示保留原命令／手動重送，stop 後回到可啟動狀態。

## A 正式服務

- before／after 的 owner、workspace／research／simulation／preview version、26 筆 research runs、R4、來源摘要及 preview simulation GET，排除動態 `observed_at` 後保持一致；前後 simulation 均 idle、active=null、start=true／stop=false、unavailable=null，研究 26/26 complete、無 active。
- 唯一新增正式 run=`5975e67dffa34594ab78c1fe4bf475b0`，request_id=`fe83d2cb42b44e48b0e0b025de5e15e3`。終態 completed、cleanup_confirmed=true、worker_closed=true、error=null、stop_requested=false；2 warmup＋8 bars／4 fills，fees=`0.00404010`、equity=`999.91375990`。
- 保存命令早於實際 POST；同 tab 切至設定再返回時仍為同 run running。tab 關閉完成時間早於 run finished_at；關閉後的獨立 GET 仍觀察到 running 並持續進度，最後自然 completed。新 tab 讀回同一 completed run。
- 終態明示 retry 使用與原始 UI start 完全相同的 URL、body、build、instance，202 回同 run。`a-terminal-before-retry.json` 與 `a-terminal-after-retry.json` 內容完全相同；服務 log 僅兩次 simulation start POST、零 stop POST，符合一次原 start＋一次同命令 retry 的額度。

## B 隔離 stub

- 唯一 stub run=`12575ca8d48c4650bcc618c90c74c798`，request_id=`ae82b2673be046779af8bd30eb7e8bbe`。第一次 start 後端已 202 接受並建立該 run，但 fixture 對 UI 回 503；第二次明示 retry 後端／UI 均 202，path、body、build、instance 完全相同，仍只有該一個 run。
- 返回及 reload 前 `b-before-retry.json` 仍只有第一次 POST；pending 在 first／returned／reloaded 三份 storage 證據完全一致，且內容等於第一次送出的命令。retry 確認後 pending 才清除。
- pending／returned UI 均顯示 start、stop 禁用且「重送原命令」可用。最後只對原 run 發一次 stop；終態 stopped、cleanup_confirmed=true、worker_closed=true、error=null、slot=idle、active=null。fixture launcher exit=0，隨機埠 54825 已無 listener。

## 證據錨點與限制

核心檔案 SHA256：

- `a-browser-observations.json`：`C0AACC4FC2BB9AE6B25F25CB3509794650DAD41C2A0ECA883ED2108A063CCE7D`
- `a-independent-observations.json`：`AC44DCA2DAC1BB64CDFB536395947373A87DA81C01161C7AB63948F366678CD7`
- `a-terminal-before-retry.json`／`a-terminal-after-retry.json`：均為 `A86933378D7076AAD21B54D6C65913064562B090C4001D8900DC62F9D6F1D708`
- `b-final.json`：`CCB5751270A95F23F4D4BEE150F9A4C4C79E5839AD63C09EC8B344C130693C48`
- `b-storage-first.json`：`39815060A955A04D5FC27C4D17523C90ECD01F20D2C3CE1CA4290DB25852DADB`
- `b-pending.png`：`45D686E8DD787D0A4A99DB8D87999D5BBB49A4047089444AD094E6213DD7C44B`
- `a-completed-details.png`：`EC8333F138E325E856CD2F9832AC2C6883A1EA436E8ACF510F477DF28C49DC34`

A 的 CDP 保存為 `truncated=true`，較早的閒置 GET 不在紀錄中；原 start、切頁／返回與關頁活動窗口仍在，且服務 log 獨立支持總命令數，因此不影響本片所需判定，但不宣稱完整前置網路歷史。B 是專用 stub，只驗證「後端接受、UI 回覆不可確認、pending 保留與同命令 retry」；其 worker_closed 不是實際 Worker 關閉證據，也不構成帳務、交易或正式網路斷線驗證。

W6 A／B 的限定驗收需求已滿足。Git 仍未執行；若後續要保存提交，應另做 scoped Git 收尾，不重跑 W6 案例。
