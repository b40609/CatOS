# 策略資料夾

這裡的每個子資料夾是一個策略。研究服務每次讀檔都會重算 sha256，結果綁定這個雜湊；檔案改了就是新版本。研究（回測、優化、滾動驗證）不需要核准。上 Bot 要使用者本人在終端機核准，Agent 不得代為核准。

這個資料夾在 git 裡只追蹤這份說明和 `example-sma-cross/`；你自己的策略不會被推上公開 repo。

## 給 Agent 的流程

1. 複製 `example-sma-cross/`，資料夾改名成策略 id：2～48 字元，小寫英文、數字或 `-`，以字母開頭，不能和內建策略同名。
2. 改 `strategy.json` 與 `strategy.py`。
3. 呼叫 MCP `research_catalog`。
   - 寫對了，`strategies` 裡會有這個策略和它的 `sha256`。
   - 寫錯了，`strategy_folder.errors` 會寫出哪裡錯。
4. 呼叫 `research_check_strategy`，它會檢查三件事：
   - 能載入。
   - 在合成資料上跑兩次，結果相同。
   - 重啟一致性（見下面「上 Bot 的條件」）。
5. 用 `research_catalog` 給的 `{id, version, sha256}` 送 `research_submit_backtest`、`research_submit_optimization`、`research_submit_validation`。
   - 請求欄位照 `research_catalog` 的 `defaults`（回測）、`optimization.defaults`、`validation.example_request` 複製再改；欄位不對時，錯誤會列出缺了哪些、多了哪些。
   - 資料集 id 也在 `research_catalog` 裡。4H 五年是 `okx-btc-usdt-swap-4h-*`，本機要先抓過。
   - 滾動驗證的 `regime_rule` 是分環境統計用的：`lookback_bars` 是判斷趨勢的視窗、`trend_efficiency` 是趨勢效率門檻、`high_volatility_bps` 是高波動門檻。範例值是 15m 用的，用在 4H 幾乎全被歸成低波動盤整，要依週期調大。
6. 送出後用 `research_get_run` 等到 `complete`。`research_get_result` 的完整結果可能近 1 MB（每筆成交、權益曲線、滾動驗證還附來源快照），請傳 `fields` 只取需要的欄位，例如 `["trial_log", "costs", "trade_stats", "overfitting"]`。
7. `trial_log` 是這個策略（所有版本）累計送出的次數與評估過的參數組次數（同一組再送一次也再算一次），也在 `research_get_run` 裡。優化結果另外用這個數字算一次 DSR（`dsr_with_history`），回報時要一起講。

研究服務讀的是哪個資料夾，看 `research_catalog` 的 `strategy_folder.path`。測試或隔離環境可以用環境變數 `CATOS_STRATEGY_HOME` 指定另一個根目錄（策略放在它底下的 `strategies/`），研究服務、MCP 與 Bot 要用同一個值。

## `strategy.json`

```json
{
  "schema": "catos.user-strategy",
  "schema_version": 1,
  "strategy_id": "資料夾名稱",
  "version": "v1",
  "name": "顯示名稱（80 字內）",
  "description": "一句話說明規則（2000 字內）",
  "entry": "strategy.py 裡的類別名稱",
  "parameters": [{"name": "fast", "min": 2, "max": 200, "default": 20}],
  "lookback": "最長視窗的參數名稱",
  "constraints": [["fast", "<", "slow"]]
}
```

- 參數只能是整數，1 到 8 個，值在 0 到 1,000,000 之間，名稱用 snake_case，不能叫 `quantity`。需要小數時改用整數單位，例如 bps。
- `lookback` 指向策略持有的 K 線根數（最長的視窗）。回測的 `warmup_bars` 至少要等於它的值。要比較「N 根之前」的收盤，策略需要持有 N+1 根，這時參數就定義成 N+1（例如 `window`，比較的是 `window - 1` 根之前）。
- `constraints` 可以是空陣列；運算子只有 `<`、`<=`。
- 不接受小數點數字、重複欄位或多餘欄位。

## `strategy.py`

- 只能有這一個檔案。雜湊只涵蓋它，所以不能 import 同資料夾的其他檔案。
- 可以 import 的只有 `__future__`、`collections`、`collections.abc`、`dataclasses`、`decimal`、`enum`、`functools`、`itertools`、`typing`、`catos.research`（也可寫 `from catos import research`）。
- 不能用 float：不能寫小數點數字，也不能用 `float`。價格、部位一律用 `Decimal`，例如 `Decimal("0.5")`。
- 不能用 `print`、`input`：研究 worker 和 Bot Worker 的標準輸出是回傳結果的通道。
- 類別繼承 `catos.research.Strategy`，建構子用關鍵字參數：每個參數名稱，加上 `quantity`（`Decimal`，張數）。
- `update_indicators(bar)`：每根已收盤 K 線都會呼叫，預熱期間也會。只能更新狀態，回傳 `None`。同一根 K 線先呼叫 `update_indicators`，再呼叫 `on_bar`。
- `ready`（property）：餵滿 `lookback` 根之前回 `False`，剛好餵滿時變成 `True`。Bot 會逐根檢查這條規則；基底類別預設永遠回 `True`，要上 Bot 就得自己寫。
- `on_bar(bar, account)`：只在評估期呼叫。回傳目標部位（`Decimal`，正數做多、負數做空、`0` 平倉），或回 `None` 表示不變。成交在下一根開盤加滑價。
- 不能連網、讀檔、用亂數或時間。這是約定，不是沙箱，CatOS 不會阻止。

## 上 Bot 的條件

Bot 重啟時，只用最近 `lookback` 根 K 線重建策略。所以策略狀態必須只由這些 K 線決定。Bot 的 `lookback` 上限是 512 根。

- 不能記住進場價、移動停損、計數器或累計值，除非它們也能從最近 `lookback` 根算回來。
- `research_check_strategy` 的 `bot_eligible` 為 `false` 時，策略仍可研究，但使用者核准會被拒絕。
- 使用者用 `python -m catos.cli strategy approve` 核准時，會用部署設定的參數再跑一次這個檢查，而且逐根比對。
- 核准後改了或刪了這個資料夾，用這筆核准的 Bot 會在下一根 K 線前停下（不平倉），要重新核准新版本；其他核准不受影響。正在跑 Bot 的策略不要改，改版請另開一個資料夾或先停 Bot。
- 檢查與核准都在 30 秒內跑完。重啟一致性最多花 15 秒逐根比對；`update_indicators` 太慢（例如每根都重算整個視窗）會比不完，結果會寫比到第幾個，核准會被拒，改成增量計算即可。

### 使用者核准的步驟（Agent 只能把這些寫給使用者）

1. 在主資料夾確認策略身分：`.venv/Scripts/python.exe -m catos.cli strategy identity`。核准時 `--sha256` 填這裡印出的 `sha256`（來源），不是 `manifest_sha256`。
2. 存一份部署設定 JSON，放哪裡都可以（建議放在策略資料夾外，例如 `strategies/<id>-4h.json`）。週期可用 5m、15m、1H、4H（`timeframe_ms` 為 300000、900000、3600000、14400000），`warmup_bars` 至少等於 lookback 參數的值，lookback 不超過 512：

   ```json
   {
     "schema": "catos.strategy-deployment",
     "schema_version": 1,
     "strategy_id": "<id>",
     "version": "v1",
     "parameters": {"fast": 20, "slow": 50},
     "quantity": "1",
     "inst_id": "BTC-USDT-SWAP",
     "timeframe_ms": 14400000,
     "warmup_bars": 50,
     "initial_balance": "10000",
     "fee_rate": "0.0005",
     "slippage_bps": "2"
   }
   ```

3. 使用者本人執行：`.venv/Scripts/python.exe -m catos.cli strategy approve --strategy <id> --version v1 --sha256 <sha256> --profile <部署設定檔>`。它會先跑重啟一致性檢查，再在終端機要求輸入 `approve`。
4. 核准後可以用 `replay` 在 local-sim 跑歷史重播、用 `replay-compare` 和研究回測逐筆比對；同一份核准也涵蓋 OKX 模擬盤 Bot（`demo bot --profile <部署設定檔>`）。

## 其他

- 研究資料夾最多保存 200 次研究結果，滿了要由使用者清理。
- 這份說明和 `docs/agent-strategy-submission-proposal.md` 有出入時，以程式行為為準（`catos/strategy_folder.py`）。
