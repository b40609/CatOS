# W7 唯讀獨立驗收

2026-10-01（台灣時間）。指定 5.6 Sol (Web) 依 [W7 assessment](local-sim-bot-control-w7-assessment-20261001.md)、[執行交接](local-sim-bot-control-w7-handoff-20261001.md)及 `outputs/workspace-w7-20261001-stop-replay/` 保存原始證據進行唯讀獨立驗收。結果：**PASS**。

本輪未執行 `replay-stop.py`、`verify-evidence.py`、`collect.ps1` 或其他案例／控制腳本；未呼叫 8770／8771 API、未 POST、未新增 run、未啟停服務、未解除 recovery／latch、未開 DB 重算帳務、未重跑 R4／研究、未操作 Git。驗收只讀既有 JSON、log、DOM／截圖及檔案 bytes。

## 獨立核對結果

- `evidence-sha256.json` 列出的 38 個既有證據檔，逐檔以目前 bytes 重算 size／SHA256，38/38 與封存清單一致。
- 唯一 W7 run=`4874ffc8cb444bbc898032005a1a848e`。`activity-get.json` 最後活動觀測為 running、warmup_bars=2、bars=1、fills=1、worker_pid=39156、stop_requested=false；活動視窗 `ui-network.json` 的兩段 flags 均 `truncated=false`。
- 活動視窗只有兩個 UI POST：`/simulation/start` 一次、同 run `/stop` 一次，兩者皆 202。首次 stop 回覆為 stopping、stop_requested=true、stop_requested_at 非空，當時 cleanup=false、worker_closed=false，證明 stop 是在實際 Worker 活動中接受。
- `terminal-get.json` 為 stopped、cleanup_confirmed=true、worker_closed=true、error=null、finished_at 非空，仍為 warmup=2、bars=1、fills=1。最後成交保留 position=`2`、fees=`0.00102030`、equity=`1000.01837970`、fill price=`102.03`；沒有 `final_account`，符合提前停止不要求自然完成摘要的界線。
- 原 stop request_id=`53417f2ceb64478d8e6199d2f3aba098`。`replay-intent.json` 與首次 UI stop 的 method、URL、原始 body 相同，且保存的 Content-Type、Referer、User-Agent、X-CatOS-Build、X-CatOS-Instance 與 sec-ch headers 逐項一致；`maximum_attempts=1`。
- 重送前／後 `control.json` 複本 SHA256 均為 `c1e809f53694df9410c33850e5db9ec2d2ef2452a2a64d89615bbbf0c3d569b6`，本 run 的 `stop_commands` 前後都嚴格只有上述 stop request_id 一筆，stop_requested_at／finished_at 未改寫。
- 原命令重送回 202；`replay-response.json` body 與 `replay-before.json` 的完整 run snapshot 相同。另直接比較 `replay-before.json`／`replay-after.json`：version、完整 run、完整 runs 清單及 control SHA 全部不變。
- 正式服務保存 log 區間恰有三個 simulation 控制 POST：start 1、同 run stop 2，皆 202；preview log 無 simulation 控制 POST。這與一次 UI start、一次 UI stop、一次終態原命令 stop 重送一致。
- before／after owner 清單一致：8770 PID 5108、8771 PID 49164。workspace／preview／R4 排除各自頂層即時 `observed_at` 後一致；research body、26 筆 research runs、source hashes、simulation version 均一致。simulation runs 由 3 筆增至 4 筆，舊 3 筆逐筆不變，唯一新增即本 W7 run；preview simulation GET 前後皆 404。
- runtime SHA256=`ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`。`ui-w7-stopped.png` 直接檢視顯示選中本次 run、已停止、1/8 根、1 成交，停止後按鈕回到可啟動狀態。

## 證據錨點與限制

主要 SHA256：

- `activity-get.json`: `55c92c00100cbb98dd0634cb12f213ae29aa28b2f35d0e1199910205ccd00671`
- `ui-network.json`: `25c3d91095540f9fd1d5147c9825786488ef958221d26a534489a60d8f48c27b`
- `terminal-get.json`: `c0bf0cb8fe477e032ce2dda1e24bfc4c654fb666a96d1195dd1ed7f153c55b5c`
- `replay-before.json`: `e4a95199b39a486fdd174711aa2739f5c8139546925ea86e21474bb6237899f7`
- `replay-intent.json`: `e4ac9ce87faec97ba46c1ba1d519df11db0b9fcf60f42a958f947e5955f11002`
- `replay-response.json`: `63c77156deda57ad8d155bf9caddfe3c3243788eae8dfaa8d5c44263712bc273`
- `replay-after.json`: `aa4ab9553f82a4d06a43cb3b525c54f755862888a066f1d8a1b19e988782372f`
- `ui-w7-stopped.png`: `2a5316ba2fe1bf91baf6244d5bfa3b028038c067b421b6de8d15210cf7e2bf4f`
- 正式 log 區間：`61c862fa2d1aa5d7fefe785f98c5a6d7dd307492c8fc24cc9ce871e0cd74e231`

本片只證明「活動中正式 stop → Worker 正常收尾 → 同 instance 終態原 stop 命令重送冪等」。停止保留模擬部位，不代表清倉或 ownership 釋放；未逐列重算帳務。後段 `ui-final-network.json` 仍為 `truncated=true`，因此不宣稱整輪 CDP 完整；控制命令總數由未截斷的活動窗口與正式服務 log 共同佐證。

W7 限定驗收需求已滿足。下一片候選可先做 **W8 最小 assessment：stop 首次回覆不確定時的 pending 保存／還原與同命令重送**；只做靜態缺口與證據設計，是否執行新案例仍須依新切片另行確認。Git 保存維持另行明確授權。
