# 獨立驗收報告：回測保證金與強平模型（c160dbfe）

- 驗收日期：2026-11-12
- 驗收者：獨立會話（未參與開發）
- 範圍：`git diff main...c160dbfe`（19 個檔案，+1186／-43），基準 `main` = `e9eec74a`
- 方式：唯讀。repo 沒有改動、沒有 commit／push、沒有切換分支；比對 `main` 用暫存 worktree，結束後已用 `git worktree remove` 移除（`git status` 乾淨，HEAD 仍為 `c160dbfe`，分支 `feat/backtest-margin-model`）。沒有呼叫任何 OKX API，只用 curl 下載文件頁。沒有讀憑證，也沒有啟動 8770 服務。
- 驗收腳本與輸出都在 `C:\Users\user\AppData\Local\Temp\claude\09abadd8a3a6a13d\d193eb95-ab02-4f70-8fd5-b5ba50577647\scratchpad\work\`

## 整體判定：FAIL（1 項阻斷缺陷，修正範圍小）

公式、檔位、標示、端點白名單、Decimal，以及關閉時與 `main` 一致等項目都通過。阻斷的是 D1：啟用保證金模型後，策略在「開盤跳空越過強平價」的那根 K 線平倉或減倉時，引擎先成交、後檢查強平，所以權益會跌到 0 以下，而且沒有強平紀錄，策略也繼續被呼叫。這和文件承諾的「強平後權益為 0、由保險基金補足、停止交易」矛盾。在真實 OKX 資料上，開盤相對前一根收盤的最大跳空是 0.057%（4H），實際觸發機率很低，偏差方向也是偏保守（虧損比 OKX 規則多）。但它會讓同一個情境下「主動平倉」的結果比「抱著被強平」更差，帳務語意錯了，所以列為阻斷。修正後只需要重驗 D1 影響的範圍。

## 核對結果

### 1. 公式與 OKX 文件（PASS，取捨偏保守且已寫明）

我用 curl 下載 5 篇說明中心文章、API 文件與更新紀錄，自己抽出正文核對，沒有沿用開發者文件的摘要。

| 項目 | OKX 原文（本次抽出） | 實作 | 判定 |
| --- | --- | --- | --- |
| 觸發條件 | 分級文章 1.1：「account equity is equal to or less than the required maintenance margin plus any applicable liquidation fees」；FAQ：「maintenance margin ratio ≤ 100%」 | `equity > N×(m+f)` 才不觸發，相等就觸發（research.py `liquidation_price`） | 一致 |
| 維持保證金 | 全倉文章：「USDT-margined: face value × \|number of contracts\| × multiplier × position tier maintenance margin ratio × mark price」 | `N(P) × m`，P 用成交價 K 線的最不利價代替標記價格 | 一致；以成交價代替標記價格已寫明為保守假設 |
| 強平手續費 | 強平條件文章：「Expiry futures and perpetual swaps fee = Position value × taker fee rate」 | `N × fee_rate` | 一致；用回測的 fee_rate 當 taker 費率，已寫明 |
| 清算費 | 分級文章 1.3：「U-margined: Face value × Contract multiplier × Number of liquidated positions × Mark price × Position tier maintenance margin requirement」，並說「may be levied」 | `N × m`（整倉） | 一致 |
| 強平後權益 | FAQ：「the entire margin portion corresponding to that position is lost」；全倉文章：「When the liquidation results in negative assets, the system will use the security fund to offset」 | 強平價成交時剩 0；跳空時保險基金補足到 0 | 一致 |
| 文件不一致 | 全倉文章：分段減倉時收一部分維持保證金，「which will not get additional liquidation fee」；分級文章：收強平手續費，另外「may」收清算費 | 兩項都收 | 開發者採保守讀法，標為待驗證，差額最多 `N × f`。我同意 |
| 初始保證金 | 保證金文章：「Initial margin = Contract size × \|Number of contracts\| × Multiplier × Mark price / Leverage」；單向持倉的多單是 `Max((Position notional + Buy order value), (Sell order value – Position notional)) / Leverage` | 只有 \|目標\| > \|部位\| 時檢查 `成交後權益 >= |目標|×b×成交價×max(1/槓桿, imr)` | 一致：反手同張數時 `max(10, 20-10) = 10`，不需要額外保證金；張數變大才需要。另見 D2 |
| 檔位查找 | API：`minSz`／`maxSz` 單位是張；分級文章：「Under cross-margin mode, the positions in all directions of each contract are calculated together」 | `|q| <= maxSz` 的第一檔 | 一致 |
| 第 3 檔以上分段減倉 | FAQ：「positions at tier 3 and above are partially reduced」 | 一次全部強平 | 偏保守，已寫明 |

API 文件 Get position tiers 的參數表有 `instType`、`tdMode`、`instFamily`（SWAP 必填）、`instId`（SWAP 忽略）、`ccy`、`tier`；範例 Python 用 `uly=`、參數表沒有 `uly`。開發者的描述正確。

快照核對：
```
$ sha256sum data/okx/BTC-USDT-SWAP/position-tiers/okx-btc-usdt-swap-position-tiers-cross-20261112T023422Z.json
638d1e4a5bb2b500b2c1a5aaed853cbd4c4ab6c24422eb47a8322c053c3479bf
records: 99；tier 1: minSz 0, maxSz 1000, mmr 0.004, imr 0.01；tier 2: minSz 1000.01, maxSz 5000, mmr 0.005, imr 0.015；tier 99: maxSz 1940000, mmr 0.4875
instId 全為 ""，instFamily 全為 BTC-USDT；git check-ignore: .gitignore:29:/data/
```

### 2. 2026-11-11 更新紀錄（PASS，不影響 net_mode）

原文：「In long/short position mode, the position tier gradient factors used to calculate the maximum openable quantity now differ between the long and short directions for SWAP and FUTURES.」異動的只有 `estMaxAmt`、`maxBuy/maxSell`、`availBuy/availSell` 的說明，以及 `posSide` 的建議。條目沒有提到 net mode、position-tiers、mmr 或強平。API 文件的 Get leverage estimated info 寫的是：「posSide ... net: The default value ... In long/short position mode, it is recommended to specify long or short」。結論和開發者相同。

### 3. 邊界情況（自寫最小案例，`edge.py`，除 D1 外全部 PASS）

我自己構造數字，不沿用開發者測試的 60000／5277.5 案例。合約每張 0.01、tick 0.1、lot 1，檔位用測試的三檔。

```
PASS long equality low=36000 -> liquidated=True | (36000, 36000, 9.000000, 72.00000, 0.000000)
PASS   fee=9, clearance=72, after=0, deficit=0
PASS long equality low=36000.1 -> liquidated=False
PASS short equality high=44000 -> liquidated=True
PASS short equality high=43999.9 -> liquidated=False
PASS long wide bar uses low | (20000, 36000)
PASS short wide bar uses high | (60000, 44000)
PASS long: huge high, safe low -> none / short: huge drop, safe high -> none
PASS reverse 50 -> -50 with equity < IM: accepted
PASS after reverse, short checked on high=36163.2 (low 30000 irrelevant) -> True ；liquidation price == independent ceil-tick
PASS after reverse, short checked on high=36163.1 -> False
PASS reverse 50 -> -60 with low equity: rejected, stays long 50 | (insufficient_initial_margin, 111.145000, 216.6000)
PASS reverse 50 -> -60 with enough equity: accepted
PASS IM boundary from flat init=210 -> 0 rejections / 209.99 -> 1
PASS reduce 50 -> 10 with equity < IM: accepted
PASS on_bar not called after liquidation | [0, 1]
PASS no trades after liquidation / equity 0 each bar after / funding payments zero after / pending_intent None
PASS lot1 q=1000: IM tier 1 imr 0.01 / q=1001: tier 2 imr 0.015 / q=5000: tier 2 / q=5001: tier 3
PASS above max tier rejected
PASS lot1 q=1000: liquidation tier 1 mmr 0.004 / q=1001: tier 2 mmr 0.005, floor-tick price
PASS real tiers q=1000 -> tier 1 / q=1000.01 -> tier 2；real IM boundary（實際快照、lot 0.01）
PASS gap: fill at open 35000, deficit 419 ；perf.liquidation_cost = -419
PASS open above P*, low below: fill at P* 36000, not gapped
PASS short gap up: fill at open 45000
PASS close funding triggers liquidation (last bar=False / True) | ('after_funding', 2700000, 37000, 9.25, 16.75, 0, 0)
PASS close funding below threshold: no liquidation
random oracle: 4000 runs, 2859 liquidations, 0 mismatches
```

隨機 oracle 的做法：我自己算觸發條件、強平價（多單向下取 tick、空單向上取 tick）、成交價（跳空時用開盤價）、檔位與初始保證金拒單，再和引擎逐筆比對。另外確認成交價都落在 [low, open]（多單）或 [open, high]（空單）之間，強平後權益為 0，四項對帳恆等式都成立。

強平價取 tick 的方向：OKX 沒有寫強平價怎麼取整，所以本項只能確認實作和文件一致，「待驗證」的標示是恰當的。

### 4. 對帳恆等式（PASS）

`recon.py`：1500 組隨機案例，一半用測試檔位（lot 1），一半用真實快照（lot 0.01）。包含隨機加減倉、反手、平倉、資金費、滑價與四種費率。結果有 449 次強平、54 次跳空、47 次穿倉補足、466 組有拒單。

```
{'runs': 1500, 'liq': 449, 'liq_after_funding': 0, 'gapped': 54, 'deficit': 47, 'rejections': 466, 'neg_equity_no_liq': 4, 'fail': 0}
max |ledger residual| 1.1E-44
```

- 期末權益 = 初始 + 已實現 − 手續費 − 資金費 − liquidation_cost + 未實現：全部成立，殘差 <= 1.1E-44。殘差來自 50 位精度的均價捨入，和 `research_trades` 原有的 1e-30 容差同一性質。
- price_pnl = 淨損益 + 手續費 + 滑價 + 資金費 + liquidation_cost：全部成立。另外我用現金流獨立重算一次：一般成交以成交 K 線開盤價計、強平成交以自身價格計，再加期末部位乘以收盤價，結果與引擎一致。
- `research_trades.trade_stats`、`round_trips`：沒有拋出殘差錯誤；全部平倉時，各往返淨損益的合計等於淨損益。
- `research_regimes._attribute`：沒有拋錯；合計的淨損益、手續費與成交筆數一致，包含收盤資金費觸發的強平。這類強平計入發生的那一根 K 線。
- 收盤資金費觸發強平的對帳（含發生在最後一根）另外在 `edge.py` 驗過，四項都是 True。隨機案例沒有產生這種強平，因為資金費率範圍太小。
- 那 4 筆 `neg_equity_no_liq` 全部屬於 D1 的型態，見下方缺陷清單。

### 5. Decimal（PASS）

- `research.py` 的 `_CONTEXT` 開啟 `traps[FloatOperation] = True`，強平與初始保證金的計算都在這個 context 裡執行。上述 5500 組以上的啟用案例都沒有觸發 FloatOperation。
- 檔位從 JSON 字串轉成 Decimal（`_record_decimal`），`_strict_json` 用 `parse_float=reject`。
- diff 新增的 Python 裡，`float` 相關用法只有兩處 `fetched_at_ms / 1000`，都是用來產生 datetime 檔名與顯示時間，不涉及金額。

### 6. margin=None 與 main 一致（PASS）

- 核心：`equiv.py` 在 `main` worktree 與 `c160dbfe` worktree 各跑同一組 300 個隨機案例（3805 筆成交、1739 筆資金費，其中 142 個案例期末權益為負）。輸出包含 BacktestResult、cost_breakdown、trade_stats 與 regime 歸因，比對時排除新欄位。
  ```
  3badf0e3311449b211c682f61b5e7d4391003195f3268fec99d4ff1f10aff8df *eq_main.json
  3badf0e3311449b211c682f61b5e7d4391003195f3268fec99d4ff1f10aff8df *eq_c160.json
  IDENTICAL
  ```
- 研究服務：`equiv_catalog.py` 用合成資料集跑 execute_request（sma-trend、donchian-breakout）、execute_optimization 與 execute_validation，再比對兩邊輸出。數值欄位全部一致；不同的只有兩類，都是預期中的差異：
  - `reproduction/files[]` 引擎原始碼的內容與 sha256。
  - 5 個 `input_sha256`。原因是 config 序列化後多了 `"margin": null`，所以即使沒有啟用，輸入雜湊也和 main 不同。這不是錯誤，但舊結果的 input_sha256 無法用新程式重算出來（見觀察 O3）。
- HTML 報告的聲明文字在 margin=None 時和 main 相同（「未建立保證金、強平或交易所端狀態機模型。」）。

### 7. 結果標示（PASS，有一項觀察）

用真實 4H 資料集實跑（`labels.py`；execute_* 是純計算，沒有寫檔）：

```
[backtest-real-highlev] margin_model: {'enabled': True, 'reason': None, 'tiers_path': 'data/okx/BTC-USDT-SWAP/position-tiers/okx-btc-usdt-swap-position-tiers-cross-20261112T023422Z.json', 'tiers_sha256': '638d1e4a…79bf', 'tiers': 99, 'tiers_fetched_at_ms': 1794450862734, 'leverage': 'tier_max'}
[backtest-real-highlev] provenance files: [... manifest.json, candles.csv, funding.csv, instrument.json, data/okx/BTC-USDT-SWAP/position-tiers/okx-...-20261112T023422Z.json]
[backtest-real-highlev] liquidation: {'time_ms': 1636545600000, 'trigger': 'adverse_extreme', 'fill_price': '66167.9', 'fee_charged': '33.0839500', 'clearance_charged': '264.5976500', 'deficit_covered': '0', 'balance_after': '0E-7'}
[backtest-real-highlev] equity_wiped_out: {'liquidated': True, ...}
  report has margin section: True | banner: True
[optimization-real] margin_model enabled True；provenance 含檔位檔
[validation-real] margin_model enabled True；result 內 config.margin 的 tiers 已縮成 99，含 liquidation 欄位
[backtest-synthetic] margin_model: {'enabled': False, 'reason': 'synthetic_fixture', ...}；notice 寫「未套用保證金與強平模型」
[synthetic opt/val] margin_model: False synthetic_fixture False synthetic_fixture
```

- 沒有檔位快照的情況：把 4H 資料集複製到我自己的暫存資料根（不含 position-tiers）→ `enabled False, reason 'no_position_tiers'`。
- 快照內容不合法（mmr > imr）→ 該合約的資料集全部被拒絕（`position_tiers_rates_invalid`），符合 fail-closed。
- 舊結果：前端 `backtest.tsx` 在沒有 `margin_model` 時顯示「舊結果：未啟用保證金模型」。`npm --prefix frontend/cat-os-vite run typecheck` 0 錯誤，`npm --prefix frontend/cat-os-vite test` 結果是 pass 21／fail 0。我沒有跑 build 與整合測試，也沒有實際開頁面操作。
- 觀察 O1：優化與滾動驗證頁面沒有額外顯示保證金狀態，只有 payload 的 `margin_model` 與 data_notice 的文字。舊的優化／驗證結果在介面上沒有「未啟用」的標示。

### 8. 抓取工具白名單（PASS）

`fetchcheck.py` 用不連網的替身 client 與真的 `Client` 驗證，沒有發出任何網路請求：

```
ENDPOINTS: ('/api/v5/market/history-candles', '/api/v5/public/funding-rate-history', '/api/v5/public/instruments')
ALLOWED_PATHS: (上述三個, '/api/v5/public/position-tiers')
TIERS_INST_IDS: ('BTC-USDT-SWAP',)
ETH-USDT-SWAP exit: 1 calls: [] stderr: stopped after 0 requests: position_tiers_not_authorized: ETH-USDT-SWAP
BTC-USDT-SWAP calls: [('/api/v5/public/position-tiers', {'instType': 'SWAP', 'tdMode': 'cross', 'instFamily': 'BTC-USDT'})]
blocked: /api/v5/account/balance、/api/v5/trade/order、/api/v5/public/mark-price-candles -> endpoint_not_allowed（requests counted: 0）
write_position_tiers ETH: position_tiers_not_authorized: ETH-USDT-SWAP
--position-tiers 搭配 --days／--resume -> SystemExit 2
```

合約白名單有兩道：工具的 `fetch_position_tiers`，以及資料層的 `write_position_tiers`／`load_position_tiers`。端點只多了 position-tiers。

### 測試執行

```
$ PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_research_margin.py"
Ran 18 tests in 0.808s  OK
$ ... -p "test_fetch_okx_dataset.py" -k PositionTiersFetchTest
Ran 2 tests in 0.025s  OK
$ .venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_*.py"
Ran 1245 tests in 164.248s  OK (skipped=11)
```

說明：完整套件執行時，測試本身在 `outputs/workspace-w6-fixture-test-*`、`outputs/workspace-w8-fixture-test-*` 留下 fixture 證據。這些路徑不是正式資料根，而且被 git 忽略，`git status` 仍然乾淨。

## 缺陷清單

### D1（阻斷）：跳空開盤越過強平價時先成交平倉，權益變負且沒有強平

- 位置：`catos/research.py:585`。pending 意圖在開盤成交，之後才在 `catos/research.py:597` 用最不利價檢查強平；檢查時部位已經是 0，所以不會觸發。文件 `docs/research-margin-model.md:91-92` 的順序就是這樣寫的，沒有考慮這種情況。
- 重現（`work/gapclose.py`）：多單 50 張、均價 40000、初始 2091，強平價 36000。bar 1 收盤時策略決定平倉，bar 2 開盤跳空到 30000。
  ```
  liquidation: None
  trades: [(900000, '50', '40000', '0', '10.000000'), (1800000, '-50', '30000', '-5000.00', '7.500000')]
  equity curve: ['2091.00', '2091.00', '2081.000000', '-2926.500000', '-2926.500000', '-2926.500000']
  on_bar calls after gap: [0, 1, 2, 3, 4]
  control (hold) -> liquidation: ('30000', True, '2919.000000') final 0.000000
  _wiped_out: liquidated False，notice 用的是通用文字
  ```
  同一個價格路徑下，抱單的結果是被強平、權益 0；主動平倉反而是權益 −2926.5，而且策略繼續被呼叫（之後的加倉都因保證金不足被拒）。隨機對帳的 4 個 `neg_equity_no_liq` 案例全部是這個型態（例如 case 387：前一根部位 −348、開盤平倉後權益 −5993.89）。
- 影響：啟用模型後，「權益不會低於 0、穿倉由保險基金補足、強平後停止」的保證失效，報表也不會標示強平。真實 OKX 資料的開盤跳空最大是 0.0574%（4H）／0.018%（1H）／0.0088%（15m）／0.0054%（5m），觸發機率很低。偏差方向是虧損比 OKX 多。
- 建議：成交 pending 之前，先用開盤價對「成交前的部位」檢查一次，例如呼叫 `liquidation_price(bar.open, bar.open)`；觸發就以開盤價強平並作廢 pending。或者把文件改成明示這個例外並要求 UI 標示，但不建議這樣做。修正後重驗本項，以及 `research_trades`、`research_regimes` 對這個情境的對帳。

### D2（非阻斷）：初始保證金檢查沒有計入 OKX 的 order loss

- 位置：`catos/research.py:451-452`。新部位以成交價（含滑價）估值，所以滑價造成的虧損沒有計入開倉成本。
- OKX 原文（保證金文章第 7 節）：「OKX includes order loss as a part of the cost required to open a position」，買單的 order loss = `size × max(0, 委託價 − 標記價格)`。
- 重現（`work/im_extra.py`）：開盤 40000、滑價 20 bps，成交 40080；初始 210.42 被接受。以標記價格約等於開盤價計算，OKX 需要約 250.42。
  ```
  D2 accepted with slippage 20bps, init 210.42: True fill 40080.0 equity at open close 160.4000000 IM at mark 40000 = 200
  ```
- 影響：比 OKX 寬鬆，屬於不保守的方向，但幅度只等於滑價成本（預設 2 bps 時約為初始保證金的 2%）。建議把權益改用開盤價（代替標記價格）估值，或在文件「不模擬」一節寫明。

## 觀察（不列缺陷）

- O1：優化與滾動驗證頁面沒有獨立顯示保證金狀態，舊結果在這兩頁也沒有「未啟用」的標示（詳見第 7 項）。
- O2：`fee_rate` 允許到 0.01。當 `mmr + fee_rate > imr` 時（例如 0.004 + 0.01 > 0.01），剛通過初始保證金檢查的部位會在同一根 K 線開盤就被強平（`im_extra.py` D3：`liquidation (900000, '40000', True)`）。這在模型內部是一致的，OKX 在這種費率下也會這樣；只是 `_validate_margin` 沒有提示。
- O3：config 序列化多了 `margin: null`，所以 margin 關閉時 walk-forward／regime 的 `input_sha256` 也和 main 不同，舊結果的輸入雜湊無法用新程式重算出來。
- O4：檔位快照沒有獨立的雜湊錨點（不像資料集有 manifest）。內容被改成另一份仍然合法的檔位時會被接受；不過 sha256 會變，provenance 也會不同（實測改 mmr 後 sha 變成 `e36bca826e44…`）。

## 無法核實的項目

- OKX 實際強平時是否同時收強平手續費與清算費、強平價怎麼取 tick、歷史期間的檔位是否和 2026-11-12 的快照相同：官方文件沒有寫明，維持「待驗證」。
- Demo 帳戶是否為 `acctLv=2`（合約模式）：需要讀帳戶設定，本次不碰帳戶與憑證，沒有核實。
- 真實的 position-tiers 回應內容：本次不呼叫 API，只核對了本機快照的雜湊與結構，以及它和文件欄位是否一致。
- 前端 build、`simulation_integration_test.mjs` 與實際頁面操作：本次沒有執行。
