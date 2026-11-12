# CatOS 回測保證金模型 D1／D2 修正：獨立重驗報告

- 日期：2026-11-12
- 重驗對象：`6cdb9115`（fix(research): 開盤跳空先強平再成交，初始保證金以開盤價估值），比對基準 `c160dbfe`、`main`（`e9eec74a`）
- 重驗者：未參與開發與先前驗收的另一個會話
- 範圍：只重驗 D1、D2 影響的範圍（`catos/research.py` 的開盤強平檢查與 `margin_rejection`），沒有重做整套驗收
- 做法：三個 commit 各自 `git worktree add --detach` 到本目錄的 `wt_c160`、`wt_6cdb`、`wt_main`，用 `C:\dev\CatOS\.venv\Scripts\python.exe -B` 直接呼叫函式。沒有連 OKX、沒有讀憑證、沒有啟動服務、沒有改 repo。

## 整體判定：PASS

兩個缺陷都已修正，沒有發現新的缺陷。下面的「觀察」都不阻斷交付。

## 1. D1：開盤跳空越過強平價

腳本 `scripts/d1.py`，輸出 `d1_output.txt`。K 線：40000、40000、第 2 根開盤跳空到 30000（空單案例跳到 50000）、之後持平。本金 2091、手續費率 0.0005、滑價 0，多單 50 張、均價 40000，強平價 36000。

| 案例 | c160dbfe | 6cdb9115 |
| --- | --- | --- |
| 多 50 -> 0（原案） | `liquidation: None`，權益 -2926.5，策略在第 0～4 根都被呼叫 | `trigger=open` 第 2 根，成交 30000，deficit 2919，權益 0，策略只在第 0、1 根被呼叫 |
| 多 50 -> 10（減倉） | 先減倉成 10 張，再強平 10 張，強平價 59517.8（不合理） | `trigger=open`，以開盤 30000 平 50 張，權益 0 |
| 多 50 -> -50（同張數反手） | 先反手成空 50，再強平空單，強平價 24023.9 | `trigger=open`，同上 |
| 多 50 -> -100（加大反手） | 拒單後強平 | `trigger=open`，意圖作廢、沒有拒單紀錄 |
| 多 50 -> 80（加倉） | 拒單後強平 | `trigger=open`，同上 |
| 空單鏡像（-> 0、-> -10、-> 50） | -> 0 時 `liquidation: None`、權益 -2931.5；其他兩種先成交再強平 | 全部 `trigger=open`，以開盤 50000 成交，強平價 43964.2，deficit 2919，權益 0 |

6cdb 的 10 個案例全部：有強平紀錄、`fill_price` 是開盤價、`gapped=True`、成交只有開倉和強平兩筆、`pending_intent=None`、權益曲線最低 0、強平後策略不再被呼叫；結果和「持有不平倉」的對照案例一樣。每個案例的恆等式、`trade_stats`、`cost_breakdown` 都通過。

## 2. 開盤檢查不會在不該觸發時觸發

腳本 `scripts/gen.py`（種子 20261112）產生 1500 個開啟保證金模型的隨機案例：20～70 根 K 線、0%／5%／15% 機率出現 4～30% 開盤跳空、本金對應 2～120 倍槓桿、15% 案例進到第 2、3 檔、隨機資金費、手續費率 0／0.0002／0.0005、滑價 0／5／20／37.5 bps、檔位 imr 或 10x／20x 槓桿、預熱 0 或 2 根。`scripts/run_cases.py` 在兩個 worktree 各跑一次，把完整結果序列化；`scripts/compare.py` 比對（輸出 `compare_output.txt`）。

```
margin cases: 1500
new open-trigger liquidations: 213
  A_open_gap(label_only): 165
  A_open_gap:old_filled_intent_first: 26
  A_open_gap:old_rejected_intent: 18
  B_D2_new_rejects_old_accepted: 38
  B_D2_rejection_values_only: 255
  identical: 998
UNEXPECTED: 0 []
slippage=0 cases: 621; without new open-liquidation: 542; of those differing from c160: 0
```

- 滑價 0 時 D2 不起作用，這時沒有開盤強平的 542 個案例和 c160 完全相同，逐欄位比對 0 差異。
- 有差異的案例按「第一根出現分歧的 K 線」分類，只有兩類：
  - A（開盤越過強平價，209 個）：分歧發生在新版 `trigger=open` 的那根。其中 142 個只差 `liquidation.trigger`／`trigger_price`，舊版是同一根以 `adverse_extreme` 用同一個開盤價成交（沒有掛著的意圖時，兩版本成交結果相同，只有標籤不同，符合規格）；其餘是舊版先成交或拒絕掛著的意圖，新版作廢它。
  - B（D2，291 個，都在滑價大於 0 的案例）：新版拒單、舊版接受，或兩邊都拒單、只有 `equity_after`／`required_initial_margin` 數值不同。沒有任何「舊版拒、新版收」的案例。
- 沒有無法分類的差異。

獨立核對（`scripts/check_new.py`，輸出 `check_new_output.txt`），不用引擎的內部數值，從權益曲線重建每根開盤前的狀態，自己算「開盤權益 <= |q| × b × 開盤價 × (mmr + f)」：

```
  open_trigger_expected: 213
  liq_open: 213
  open_liq_spec_ok: 213
  open_liq_voided_intent: 44
```

所有有部位的 K 線開盤，觸發條件的判斷和引擎完全一致（沒有 `open_trigger_mismatch`）。213 筆開盤強平都符合規格：以開盤價成交、`gapped=True`、同根只有強平一筆成交、意圖作廢（其中 44 筆前一根確實有會改變部位的意圖）、之後不再呼叫策略、權益固定在 `balance_after` 而且不為負。

## 3. D2：初始保證金以開盤價估值

OKX [Futures margin calculation rules](https://www.okx.com/en-us/help/ii-what-is-margin-in-perpetual-swaps)（WebFetch 抽取正文，2026-11-12）：

- 第 7 節：買單 order loss = Abs(面值 × |張數| × 乘數 × Min[0, 標記價格 − 委託價])，賣單 = Abs(面值 × |張數| × 乘數 × Min[0, 委託價 − 標記價格])；市價單以預估成交價當委託價；「OKX includes order loss as a part of the cost required to open a position」。
- 第 2 節：全倉 U 本位初始保證金 = 面值 × |張數| × 乘數 × 標記價格 ÷ 槓桿。

等價推導：以開盤價當標記價格時，成交後權益 = B + 已實現 − 手續費 + 目標張數 × b ×（開盤價 − 新均價）。從空倉開倉時，最後一項等於 −|q| × b × |成交價 − 開盤價|，也就是 OKX 的 order loss；加倉時多出的是舊部位在開盤價的未實現損益；反手時平倉部分在成交價實現，新部位均價是成交價，最後一項同樣是新部位的 order loss。所需保證金也照第 2 節以開盤價（標記價格的替代）計。所以「用開盤價估值」等於把滑價算成 order loss。新公式在 long／short 都比舊公式嚴格（權益變低，long 時所需保證金也變低但乘上 imr < 1）；隨機案例沒有出現新版較寬鬆的成交（`new_looser_than_old` 0 筆）。

邊界（`scripts/d2.py`，輸出 `d2_output.txt`，門檻本金由腳本以獨立公式計算）：

| 情境 | 獨立算出的門檻本金 | 6cdb：門檻 | 6cdb：少 0.01 | c160：少 0.01 |
| --- | --- | --- | --- | --- |
| 多 50 開倉，開盤 40000，滑價 20 bps | 250.02（費 10.02 + order loss 40 + IM 200） | 成交 | 拒單，equity_after 199.99，required 200 | 成交 |
| 空 50 開倉，同上 | 249.98（費 9.98 + 40 + 200） | 成交 | 拒單，199.99 對 200 | 成交 |
| 多 10 加到 80，開盤 41000，滑價 37.5 bps | 精確 367.07133，取到分 367.08 | 成交 | 拒單，327.99867 對 328 | 成交 |
| 多 50 反手到空 60，開盤 39000，滑價 20 bps | 精確 891.2271，取到分 891.23 | 成交 | 拒單，233.9929 對 234 | 成交 |
| 10x 槓桿，多 50，滑價 20 bps | 2050.02 | 成交 | 拒單，1999.99 對 2000 | 成交 |

先前驗收寫「OKX 約需 250.42」，那是把 IM 用成交價 40080 計（0.5 × 40080 × 1% = 200.4）。依第 2 節，IM 用標記價格計；本模型以開盤價代替標記價格，所以是 250.02。兩者差 0.40，來源是 IM 的估值價格，不是 order loss。

減倉與同張數反手不檢查（`scripts/d2_reduce.py`，輸出 `d2_reduce_output.txt`）：多 50 @ 40000、本金 215，第 2 根開盤 39900，開盤權益 155（IM 199.5、MM + LF 89.775）。

```
[50 -> 10 減倉]          rejections=0 trades=[('50','40000','50'), ('-40','39900','10')]
[50 -> -50 同張數反手]   rejections=0 trades=[('50','40000','50'), ('-100','39900','-50')]
[50 -> 0 平倉]           rejections=0 trades=[('50','40000','50'), ('-50','39900','0')]
[50 -> -51 加大反手]     rejections=1 equity_after=134.850500 required=203.4900
```

隨機案例另外重算了 4879 筆讓 |部位| 變大的成交（全部符合開盤價估值 >= 所需 IM）和 2776 筆拒單紀錄（`fill_price`、`equity_after`、`required_initial_margin` 和獨立計算逐位相同，而且確實 equity < required）。3596 筆減倉或同張數反手沒有被檢查。

## 4. 對帳恆等式

`scripts/check_new.py` 在 6cdb 跑 1500 個隨機案例（含 213 筆開盤強平、310 筆最不利價強平、1 筆資金費後強平、202 筆由保險基金補負數）：

```
  trade_stats_ok: 1500
  regime_ok: 1500
PROBLEMS by type: {'identity': 47, 'regime_result_differs': 4}
```

- `cost_breakdown`：1500 個案例的 price_pnl = 淨損益 + 手續費 + 滑價 + 資金費 + liquidation_cost 全部精確相等。
- `trade_stats` 與 `regime_backtest`：1500 個案例都沒有拋對帳錯誤；regime 的 `reconciled` 全部為 True，結果和直接回測相同。
- 列出的 51 筆都是 50 位有效數字的捨入殘差，不是這次修正造成的（`scripts/identity_probe.py`，輸出 `identity_probe_output.txt`）：
  - 恆等式的差值最大 1E-44（例如案例 223 是 -1E-45，均價 17938.9，沒有強平）。c160 在同一批案例有 46 筆、最大差值也是 1E-44，而且包含 34 個沒有強平的案例。6cdb 多出的 1 筆是案例分歧後算術路徑不同所致（6cdb 有 3 筆 open，c160 那邊同類案例是 adverse_extreme）。
  - 4 筆 regime 只是 `core_net_rounding_residual` 是 ±1E-46 這個量級的非 0 值（`reconciled=True`），c160 也有其中 3 筆。

## 5. 保證金模型關閉時與 main 一致

600 個 `margin=None` 的隨機案例（其中 184 個期末權益為負，代表有高槓桿穿倉），`main` 與 `6cdb` 比對 `trades`、`funding`、`equity_curve`、`pending_intent`、`assumptions`、策略呼叫序列與 `performance` 全部欄位：

```
margin=None cases: 600; mismatches main vs 6cdb: 0 []; new-field non-default: 0
```

6cdb 新增的欄位都是預設值（`liquidation=None`、拒單 0、`liquidation_cost=0`）。

## 6. 單元測試

指令（在 `C:\dev\CatOS`）：

```
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -B -m unittest discover -s tests -p "test_research_margin.py" -v
```

輸出（尾段）：

```
test_slippage_counts_as_order_loss_against_the_open ... ok
...
test_open_gap_liquidates_before_a_pending_exit_fills ... ok
...
----------------------------------------------------------------------
Ran 20 tests in 0.808s

OK
```

## 新發現的缺陷

無。

## 觀察（不阻斷）

1. 恆等式有 1E-44 量級的捨入殘差，c160 本來就有，跟 D1／D2 無關。`tests/test_research_margin.py:60` 的 `reconcile` 用精確相等，是因為手算案例的數字剛好可以整除；換成任意均價就可能有這種殘差。要不要改成容差比較，可以另外決定。
2. `catos/research.py:287-293` 的 `_MARGIN_ASSUMPTIONS` 沒有寫到「開盤先檢查強平、作廢意圖」，也沒寫「初始保證金以開盤價估值（含 order loss）」。規格文件 `docs/research-margin-model.md:86`、`:91` 已經寫了。這是附在結果上的說明文字，建議補上，不影響數值。
3. 前端只用 `gapped` 決定文案（`frontend/cat-os-vite/src/pages/backtest.tsx:612`），沒有依 `trigger` 分支。開盤強平的 `gapped` 一定是 True（開盤價是 tick 的整數倍，越過精確解就一定越過取整後的強平價），所以文案「跳空越過強平價，以開盤價成交」是正確的。

## 待驗證

- OKX 開倉成本是否就是「order loss + 手續費 + IM」相加：說明中心第 7 節只說 order loss 是開倉成本的一部分，沒有給合併公式（WebFetch 抽取，不是原始 HTML）。本模型把手續費也從權益扣掉，是否與 OKX 實際扣法一致，標為**待驗證**。
- 先前驗收引用的「約 250.42」與本模型的 250.02 差在 IM 用成交價還是標記價格；依第 2 節是標記價格，但 OKX 下市價單時實際用哪個價格估 IM，沒有一手 payload，標為**待驗證**。

## 檔案

- 腳本：`scripts/`（d1.py、d2.py、d2_reduce.py、gen.py、run_cases.py、compare.py、check_new.py、identity_probe.py）
- 案例與原始結果：`out/`（cases_margin.json、cases_nomargin.json、res_*.json）
- 各腳本輸出：`d1_output.txt`、`d2_output.txt`、`d2_reduce_output.txt`、`compare_output.txt`、`check_new_output.txt`、`identity_probe_output.txt`、`labelonly_output.txt`
- 三個 worktree 已在結束時 `git worktree remove`。
