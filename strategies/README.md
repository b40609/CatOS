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
   - 資料集 id 也在 `research_catalog` 裡。
   - 4H 五年是 `okx-btc-usdt-swap-4h-*`，本機要先抓過。
6. 結果裡的 `trial_log` 是這個策略（所有版本）累計送出的次數與參數組數。優化結果另外用這個數字算一次 DSR（`dsr_with_history`），回報時要一起講。

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
- `lookback` 指向決定策略狀態的最長視窗。回測的 `warmup_bars` 至少要等於它的值。
- `constraints` 可以是空陣列；運算子只有 `<`、`<=`。
- 不接受小數點數字、重複欄位或多餘欄位。

## `strategy.py`

- 只能有這一個檔案。雜湊只涵蓋它，所以不能 import 同資料夾的其他檔案。
- 可以 import 的只有 `__future__`、`collections`、`dataclasses`、`decimal`、`enum`、`functools`、`itertools`、`typing`、`catos.research`。
- 不能用 float：不能寫小數點數字，也不能呼叫 `float(...)`。價格、部位一律用 `Decimal`，例如 `Decimal("0.5")`。
- 類別繼承 `catos.research.Strategy`，建構子用關鍵字參數：每個參數名稱，加上 `quantity`（`Decimal`，張數）。
- `update_indicators(bar)`：每根已收盤 K 線都會呼叫，預熱期間也會。只能更新狀態，回傳 `None`。
- `ready`（property）：資料夠了才回 `True`。
- `on_bar(bar, account)`：只在評估期呼叫。回傳目標部位（`Decimal`，正數做多、負數做空、`0` 平倉），或回 `None` 表示不變。成交在下一根開盤加滑價。
- 不能連網、讀檔、用亂數或時間。這是約定，不是沙箱，CatOS 不會阻止。

## 上 Bot 的條件

Bot 重啟時，只用最近 `lookback` 根 K 線重建策略。所以策略狀態必須只由這些 K 線決定。

- 不能記住進場價、移動停損、計數器或累計值，除非它們也能從最近 `lookback` 根算回來。
- `research_check_strategy` 的 `bot_eligible` 為 `false` 時，策略仍可研究，但使用者核准會被拒絕。
- 使用者用 `python -m catos.cli strategy approve` 核准時，會用部署設定的參數再跑一次這個檢查。

## 其他

- 研究資料夾最多保存 200 次研究結果，滿了要由使用者清理。
- 這份說明和 `docs/agent-strategy-submission-proposal.md` 有出入時，以程式行為為準（`catos/strategy_folder.py`）。
