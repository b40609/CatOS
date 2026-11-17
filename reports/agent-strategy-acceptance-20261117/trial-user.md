# 試用者驗收：BTC 4H 價格動能（2026-11-17）

角色：第一位試用者，用 AI Agent 輔助寫 Python 的量化開發者。只靠研究 MCP 工具走完「寫策略 → 檢查 → 4H 回測 → 參數優化 → 滾動驗證」。
環境：隔離資料根 `%TEMP%\catos-trial-098523f1`（`home/strategies/`、`research/`），研究服務在 `127.0.0.1:18872`（PID 29732，結束時已停），MCP 用 `mcp.client.stdio` 啟動 `python -B -m catos.research_mcp --port 18872`，env 帶 `CATOS_STRATEGY_HOME`。沒有連外網、沒有寫 repo 的 `strategies/`、`outputs/`，repo `git status` 乾淨。
文件：只讀了 `README.md`、`strategies/README.md`、`strategies/example-sma-cross/`。沒有讀 `catos/` 的 Python 原始碼；為了寫部署設定，讀了 `catos/deployment_profiles/` 裡兩個範例 JSON（見摩擦 #4）。

---

## 1. 給使用者的結論

**現在這個樣子不值得上 Bot。** 長回看期（約 30 天）的動能在 BTC 4H 上有一點訊號，但樣本外只賺到買進持有的一半左右。它還有一個樣本外視窗虧 26.5%，參數只要差一格，結果就從大賺變成大賠，過擬合檢查也沒過。

規則：本根收盤高於 N 根之前的收盤做多，低於做空，相等不變。實作時參數是 `window = N + 1`，原因見摩擦 #2。所有測試都用 10 張（0.1 BTC）、本金 10,000 USDT、手續費 0.05%、滑價 2 bps，並套用保證金模型。

| 項目 | 數字 |
| --- | --- |
| 初次回測（N=42，約 7 天；2021-11-13～2026-11-06） | 報酬 **−17.35%**，最大回撤 49.0%，768 筆成交。扣成本前價格損益 +4,679，手續費 4,586、滑價 1,842 把它吃光。勝率 29.2%，獲利因子 0.96 |
| 同期買進持有（同 10 張） | +1,183 USDT（**+11.83%** 本金；BTC 漲 18.47%） |
| 優化（`window` 7～367、步長 20，19 格窮舉；2022-01-06～2026-11-06） | 最佳 `window=187`（N=186，約 31 天）：**+81.85%**，最大回撤 28.5%，299 筆。但鄰近參數差很多：167 是 −6.88%，147 是 −59.88%，7 和 27 爆倉（−100%） |
| 優化同期買進持有 | +3,265 USDT（**+32.65%** 本金；BTC 漲 75.5%） |
| 過擬合檢查 | Sharpe（年化）0.691，純雜訊下的期望最大值 0.447；PSR 0.9359；**DSR 0.7042**；**`dsr_with_history` 0.7001**（history_trials=20）；**PBO 0.6143**。工具判讀：「有跡象但不顯著……樣本內選出的冠軍，樣本外多半排在中位數以下」 |
| 滾動驗證（5 窗；訓練 2000 根約 333 天，測試 1700 根約 283 天；樣本外 2022-12-05～2026-10-22） | 4 窗選 `window=207`，1 窗選 367（剛好在範圍上限）。樣本外各窗：**+2.56%、+29.99%、−26.52%（回撤 43.7%）、+8.95%、+16.17%** |
| 樣本外合計 vs 買進持有 | 策略淨損益 **+3,114.48 USDT**，同窗買進持有 **+6,511.73 USDT**。手續費 1,457.54、滑價 585.48 |
| 日損（N=42 那次回測的診斷） | Soft 5% 有 38 天（每年 7.62 次），Hard 10% 有 4 天。上模擬盤 Bot 會被鎖住好幾次 |
| `trial_log`（最終） | runs 3、**configurations 39**、versions 1（since 2026-11-17T08:40:35Z） |

判讀：
- 樣本外 5 窗中 4 窗賺錢，只在空頭窗（第 4 窗，BTC −9.6%）贏過買進持有。多頭窗大幅落後：第 1 窗 BTC +135%，策略只有 +30%。
- 參數地形很破碎，相鄰回看期的報酬正負交替。DSR 0.70 低於 0.95，PBO 0.61 高於 0.5，優化最佳值 +81.85% 不能當真。
- 想繼續的話，可以試「只做多」或波動調整部位。但每次換規則或參數都會累加 `trial_log`，DSR 會再往下修。

## 2. 流程紀錄

| 步驟 | 做了什麼 | 嘗試次數 | 錯誤原文與處理 |
| --- | --- | --- | --- |
| 讀文件 | `README.md`、`strategies/README.md`、範例 | 1 | — |
| 列工具 | `list_tools`。`research_submit_*` 的 `request` 只寫 `additionalProperties: true` | 1 | 欄位從 `research_catalog` 的 `defaults`、`optimization.defaults`、`validation.example_request` 反推 |
| 寫策略 | 複製範例改成 `btc-momentum`。第一版參數 `n`，`lookback: "n"`，`deque(maxlen=n+1)` | 2 | 見下一列 |
| 檢查 | `research_check_strategy {"strategy_id":"btc-momentum"}` | 2（＋1 次用部署參數） | 第一版 `stages[2]`：`"backtest" ok:false detail:"ValueError: strategy indicators are not ready after warm-up"`，`bot_eligible:false`、`bot_reason:null`。原因：比較「N 根之前」需要 N+1 根，但 `lookback` 只能指向單一參數，`ready` 必須剛好在 `lookback` 根時變 True。處理：改成參數 `window`（= N+1），`lookback: "window"`。第二版五個階段全過 |
| 4H 回測 | `research_submit_backtest`，`window=43`、10 張、本金 10000、`warmup_bars=43`；輪詢 `research_get_run`，再用 `research_get_result` 取結果 | 1 | 沒有錯誤，但結果有 992,700 bytes，只能存檔後用 Python 解析（摩擦 #1） |
| 優化 | `research_submit_optimization`，`search_space.window {low:7, high:367, step:20}`，`n_trials 19`，`warmup_bars 367` | 1 | 沒有錯誤；4 秒完成，結果 21,865 bytes |
| 滾動驗證 | `research_submit_validation` | 2 | 第一次沒帶 `regime_rule`：`research_http_422: validation: exact registered fields required`，沒說缺哪個欄位。比對 `validation.example_request` 才發現少 `regime_rule`；補上後 4 秒完成，結果 862,155 bytes |
| 報告 | `research_get_report` ×3 | 1 | 回測報告 HTML 122,994 bytes，優化 35,263，驗證 12,298 |
| 核准指令 | `python -m catos.cli --help`、`strategy --help`、`strategy identity`（唯讀，env 指向隔離路徑） | — | 頂層 `--help` 顯示舊的「Dual SMA Strategy Backtest CLI」（摩擦 #9）。部署設定格式文件裡沒有，讀了範例 JSON（摩擦 #4）。**沒有執行 `strategy approve`／`revoke`**，連 `--help` 也沒跑 |

MCP 呼叫總數約 22 次，包含 3 次輪詢。每個研究任務都在 1～4 秒內完成，一次只跑一個。

## 3. 摩擦清單（依嚴重度）

### 高

1. **`research_get_result` 的輸出太大，Agent 吃不下**
   - 預期：拿到摘要，包含績效、成本、買進持有、過擬合與 `trial_log`。
   - 實際：回測 992,700 bytes（768 筆成交、1,821 點權益曲線），滾動驗證 862,155 bytes（`reproduction.files` 內嵌 17 個引擎原始檔的全文）。`trial_log` 和 `selection_edges` 都在 JSON 尾端，一般 MCP 客戶端的輸出上限一截斷就不見了，而 README 要求回報時一起講 `trial_log`。我只能存檔再用 Python 解析，這已經不是「只靠 MCP 工具」。
   - 建議：預設回傳摘要，加 `detail`／`fields` 參數才給明細；滾動驗證的原始碼快照只回路徑和 sha256；`trial_log` 移到開頭。

2. **`lookback` 只能等於某個參數值，「N 根之前」會差一根**
   - 預期：照直覺寫 `n` 與 `deque(maxlen=n+1)` 就能過；萬一不過，錯誤訊息會講清楚規則。
   - 實際：`ValueError: strategy indicators are not ready after warm-up`，`bot_reason: null`。這個訊息容易讓人以為加大 `warmup_bars` 就好，其實是 `ready` 必須「剛好在 `lookback` 根時變 True」。最後只好把參數改成 `window = N + 1`，使用者要自己記得 N = window − 1。
   - 建議：在 `strategies/README.md` 加一段「比較 N 根之前要 N+1 根」的寫法，或讓 `lookback` 支援位移（例如 `{"param": "n", "plus": 1}`）；錯誤訊息改成「ready 在餵滿 lookback=42 根時仍為 False；ready 必須剛好在 lookback 根時變 True」；`bot_eligible=false` 時 `bot_reason` 要填原因。

3. **`request` 沒有 schema，422 也不說是哪個欄位**
   - 預期：工具的 inputSchema 列出欄位；欄位錯了，訊息寫出缺什麼、多什麼。
   - 實際：`request` 是 `additionalProperties: true`，欄位只能從 catalog 的範例反推。漏了 `regime_rule` 時只回 `exact registered fields required`。
   - 建議：在 inputSchema 寫出完整欄位，或在工具描述註明「欄位見 `research_catalog.validation.example_request`」；422 列出 missing／unexpected 欄位。

### 中

4. **部署設定（profile）的格式沒寫在文件裡**
   - 預期：README 或 `strategies/README.md` 有部署設定的範本與欄位說明，並說明檔案放哪裡、用哪一個 sha256。
   - 實際：README 只給 Donchian 的 approve 指令，`--profile` 指向 `catos/deployment_profiles/…`；`strategies/README.md` 只寫「用部署設定的參數」。我讀了 `catos/deployment_profiles/donchian-breakout-{15m,4h}-192-48.json` 才知道格式。另外有幾件事文件也沒寫：
     - `strategy identity` 同時印 `sha256` 和 `manifest_sha256`，`--sha256` 要哪個沒寫，我推定是前者。
     - 自訂 profile 能不能放在 `catos/` 外面。
     - 模擬盤 Bot 支不支援 4H。
     - 有沒有不核准、只檢查 profile 的 dry-run。
   - 建議：在 `strategies/README.md`「上 Bot 的條件」補 profile 範本、欄位說明、`--sha256` 對應哪個值、檔案建議放哪裡；加 `strategy check-profile` 之類的唯讀檢查。

5. **`regime_rule` 是必填，但沒有說明；範例門檻是 15m 的**
   - 預期：選填，或依週期給預設值，並說明各欄位意義。
   - 實際：照範例填 `lookback 42 / trend_efficiency 0.5 / high_volatility_bps 250` 用在 4H，結果 10,956 根裡有 9,937 根被歸為 `RANGE_LOW`，分環境統計等於沒用。文件和工具描述都沒寫這三個值怎麼選。
   - 建議：改成選填並依 timeframe 給預設值，或在工具描述寫出各欄位定義與建議範圍。

6. **`trial_log.configurations` 會重複計數，說明文字也互相矛盾**
   - 預期：README 說是「累計試過幾組參數」，同一組參數再跑不應增加。
   - 實際：優化後是 20（19 格加上回測的 43），滾動驗證用同樣 19 格後變成 39。優化結果 `overfitting.notice` 仍寫「同一份資料過去的搜尋沒有計入，所以 DSR 是上限」，但同一份結果已經有 `dsr_with_history`。
   - 建議：講清楚 configurations 是「評估次數」還是「不同參數組」，要嘛改名，要嘛去重；更新 notice。

7. **買進持有基準只有損益，沒有回撤或 Sharpe**
   - 預期：可以比較風險調整後的表現，判斷「賺得比較少但回撤小」值不值得。
   - 實際：`buy_hold` 只有 `pnl` 和 `underlying_return_pct`。這次策略報酬落後持有，但無法判斷風險上有沒有換到什麼。
   - 建議：基準也給最大回撤與年化 Sharpe。

### 低

8. **`CATOS_STRATEGY_HOME` 沒寫進文件，catalog 只顯示相對路徑**
   - 實際：`strategy_folder.path` 永遠是 `"strategies/"`，`source_files` 是 `strategies/btc-momentum/strategy.py`，看不出服務實際讀的是哪個資料夾。Agent 和研究服務設定不同時會寫錯地方。
   - 建議：catalog 回傳解析後的絕對路徑，README 補這個環境變數。

9. **`python -m catos.cli --help` 顯示舊的「Dual SMA Strategy Backtest CLI」**
   - 實際：要求 `--csv` 等參數，沒有列出 `strategy`／`demo`／`kill` 子指令，從頂層 help 找不到 `strategy identity`。另外 `strategy --help` 寫「研究策略上 local-sim Bot 的本機核准」，沒提模擬盤。
   - 建議：頂層 help 列出子指令，並更新說明文字。

10. **`update_indicators` 與 `on_bar` 的呼叫順序沒有寫明**
    - 實際：只能從範例推斷同一根 K 線先呼叫 `update_indicators` 再呼叫 `on_bar`。
    - 建議：在 `strategies/README.md` 寫一句。

11. **catalog 的 `model` 字串與資料集設定矛盾**
    - 實際：寫「no order book, margin or liquidation model」，但 4H 資料集的 `margin_model.enabled` 是 `true`。
    - 建議：改寫成「依資料集而定」。

12. **送出後只能輪詢**
    - 實際：沒有 wait 選項，要自己輪詢 `research_get_run`。這次 1～4 秒就完成，影響小。

13. **優化格點只能等差，上限 20 點**
    - 實際：動能回看期通常想試等比格點（1、3、7、30、60 天），`low/high/step` 無法表達。上限 20 點時，7～367 只能用步長 20。
    - 建議：`search_space` 支援明列的值清單。

## 4. 檢查結果（`research_check_strategy`）

| 版本 | 參數 | 結果 |
| --- | --- | --- |
| 第一版（參數 `n`，sha 未送研究） | `n=42`，quantity 1 | `load` ok、`construct` ok、`backtest` **失敗**：`ValueError: strategy indicators are not ready after warm-up`；`ok:false`，**`bot_eligible:false`**，`bot_reason:null` |
| 定版 `v1` sha256 `8c2334ca…f8085` | 預設 `window=43`，quantity 1 | load／construct／backtest／deterministic／restart_consistency 全過；trades 5、decisions_checked 557、restart_points 557、exhaustive true；`ok:true`，**`bot_eligible:true`** |
| 同上，部署參數 | `window=207`，quantity "1" | 全過；trades 7、decisions_checked 714、restart_points 714、exhaustive true；**`bot_eligible:true`** |

身分：`btc-momentum` / `v1`
- `sha256 = 8c2334ca0952a304ce7431b8ec4bb871366bd673f8cc4343164790f684cf8085`
- `manifest_sha256 = de1b13aa9418d7fe15b98f0071583544d8fdd41fb59985d17ae8c9f7991ca938`

## 5. 核准指令（使用者本人執行；代理沒有執行）

依結論，不建議核准。如果仍要上模擬盤 Bot，步驟如下：

1. 把策略資料夾放進正式主資料夾 `C:\dev\CatOS\strategies\btc-momentum\`，兩個檔案內容在本節最後，要逐位元組相同、用 LF 換行，否則 sha256 會變。
2. 在 `C:\dev\CatOS` 確認 sha256：

```bash
.venv/Scripts/python.exe -m catos.cli strategy identity
```

應看到 `btc-momentum v1 sha256=8c2334ca0952a304ce7431b8ec4bb871366bd673f8cc4343164790f684cf8085`。

3. 存一份部署設定，例如 `C:\dev\CatOS\strategies\btc-momentum-4h-207.json`。內容照 `catos/deployment_profiles/donchian-breakout-4h-192-48.json` 的格式推得；建議放在策略資料夾外，以免影響策略資料夾的檢查，這點文件沒寫：

```json
{
  "schema": "catos.strategy-deployment",
  "schema_version": 1,
  "strategy_id": "btc-momentum",
  "version": "v1",
  "parameters": {"window": 207},
  "quantity": "1",
  "inst_id": "BTC-USDT-SWAP",
  "timeframe_ms": 14400000,
  "warmup_bars": 207,
  "initial_balance": "10000",
  "fee_rate": "0.0005",
  "slippage_bps": "2"
}
```

4. 核准（會先用 `window=207` 跑重啟一致性檢查，並在終端機要求確認）：

```bash
.venv/Scripts/python.exe -m catos.cli strategy approve --strategy btc-momentum --version v1 --sha256 8c2334ca0952a304ce7431b8ec4bb871366bd673f8cc4343164790f684cf8085 --profile strategies/btc-momentum-4h-207.json
```

5. 啟動模擬盤 Bot：

```bash
.venv/Scripts/python.exe -m catos.cli demo bot --profile strategies/btc-momentum-4h-207.json
```

推不出來或沒驗證的部分：
- `--sha256` 用 `sha256`（來源）而不是 `manifest_sha256`，是從 README 的「用 strategy identity 查到的 64 碼」推定的。
- profile 放在 `catos/deployment_profiles/` 以外能不能被接受，沒有驗證。
- 模擬盤 Bot 支不支援 4H，README 沒寫；有 4H 的 Donchian 範例 profile，但 README 的 Bot 範例只有 15m。
- `initial_balance`、`fee_rate`、`slippage_bps` 對模擬盤 Bot 有沒有作用，沒寫。
- 1 張等於 0.01 BTC，名目約 750 USDT，必須在帳戶單幣 0.5 倍權益的上限內。

`strategy.json`：

```json
{
  "schema": "catos.user-strategy",
  "schema_version": 1,
  "strategy_id": "btc-momentum",
  "version": "v1",
  "name": "價格動能（多／空）",
  "description": "看最近 window 根收盤：本根收盤高於最舊一根（window-1 根之前）做多，低於做空，相等不變。N = window - 1。",
  "entry": "PriceMomentum",
  "parameters": [
    {"name": "window", "min": 2, "max": 500, "default": 43}
  ],
  "lookback": "window",
  "constraints": []
}
```

`strategy.py`：

```python
"""Price momentum: long when close > close (window - 1) bars ago, short when below."""

from collections import deque
from decimal import Decimal

from catos.research import AccountView, Candle, Strategy


class PriceMomentum(Strategy):
    def __init__(self, window: int, quantity: Decimal):
        # the last `window` closes: closes[-1] is this bar, closes[0] is N = window - 1 bars ago
        self.closes = deque(maxlen=window)
        self.quantity = quantity

    def update_indicators(self, bar: Candle) -> None:
        self.closes.append(bar.close)

    @property
    def ready(self) -> bool:
        return len(self.closes) == self.closes.maxlen

    def on_bar(self, bar: Candle, account: AccountView) -> Decimal | None:
        now = self.closes[-1]
        then = self.closes[0]
        if now > then:
            return self.quantity
        if now < then:
            return -self.quantity
        return None
```

研究 run_id（隔離資料根 `%TEMP%\catos-trial-098523f1\research`）：
- 回測 `d46043ab9c1c43a69724507d80cef893`
- 優化 `bce00632f44945b29d0c949436bec968`
- 滾動驗證 `55c4379acfd94306835b60a497e62161`
