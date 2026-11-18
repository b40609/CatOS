# 獨立驗收：保證金率改讀 details[].mgnRatio（commit cecbe729）

日期：2026-11-18（Asia/Taipei）
驗收者：Claude Opus 5.5（未參與這個改動的會話）
範圍：`catos/okx_demo.py` `account_snapshot`（cecbe729）、`catos/demo_bot.py:479` 的 `margin_ok`、`catos/risk.py:525-528` 的健康判定、`tests/test_demo_bot.py` 的 `MarginRatioTests` 與 FakeOkx `margin_ratio_at`。

## 結論：PASS（有觀察）

改動本身是嚴格的 fail-closed：只有帳戶層級 `mgnRatio` 為空或沒有欄位時，才退回同一筆 USDT `details` 的 `mgnRatio`；兩處都沒有仍是 `None`，持倉時 `margin_ok=False`。0、負值、低於 3 都不放行，非數字與 NaN／Infinity 直接丟 `DemoError`。找不到會放寬安全檢查的路徑。沒有缺陷（D）。

沒辦法在這次驗收裡證實的有兩件，都標「待驗證」：OKX 模擬盤在 Futures 模式持倉時 `details[].mgnRatio` 是否真的有值，以及它的單位是不是和帳戶層級一樣是倍數（1.0 = 強平）。就算答案是否定的，最壞結果也只是維持修正前的 fail-closed（持倉時健康降級、反手只平倉），不會變得更寬鬆。唯一例外是單位：如果 OKX 回的是百分比數字（例如 300 代表 300%），門檻 3 等於 3%，會低於強平線，這時檢查形同虛設，見 O1。

## 1. 語意是否等價

做了什麼：下載 OKX 官方文件 https://www.okx.com/docs-v5/en/ （2026-11-18），抽出 Trading Account > Get balance 的回應參數。原文摘錄存在 `reports/margin-ratio-20261118/scratch/docs/get-balance-mgnRatio-excerpt.txt`。另外讀了 OKX 說明中心「Futures mode: cross margin trading」（https://www.okx.com/help/iii-single-currency-margin-cross-margin-trading）。

看到什麼：
- 帳戶層級 `mgnRatio`：「Account-level margin ratio = adjEq / mmr. Values at or below 1.0 indicate the account is at or past the liquidation boundary. … Applicable to Spot mode / Multi-currency margin / Portfolio margin」。`mmr` 的說明也寫了「mgnRatio ≤ 1.0」時開始強平。所以 API 回的是倍數。
- `details[].mgnRatio`：「Cross maintenance margin ratio of currency. The index for measuring the risk of a certain asset in the account. Applicable to Futures mode and when there is cross position」。和委託人給的描述一致。文件沒有寫公式或單位，範例回應裡的值是空字串。
- 說明中心的 Futures 模式全倉：維持保證金率 =（該幣種全倉帳戶餘額 + 全倉部位損益 − 掛單占用 − 手續費）/（維持保證金 + 強平手續費），≤ 100% 時先撤單、仍 ≤ 100% 就強平，300% 是預警線。說明中心用百分比表示。

判斷：
- 兩個欄位都是「可用權益 / (維持保證金 + 強平費)」，強平線都在 100%。差別是範圍：帳戶層級是整個帳戶換成 USD，details 是 USDT 這個幣種自己的全倉池。CatOS 只做 USDT 本位的 BTC-USDT-SWAP，帳戶裡有其他合約、委託或逐倉部位時 Bot 直接停（`catos/demo_bot.py:305-306`、`catos/demo_bot.py:338-339`），所以 USDT 池就是這個部位的保證金池，語意對得上，範圍反而更準。
- 門檻 3 對應 300%，正好是說明中心寫的預警線，在單位是倍數的前提下合理。
- 單位：帳戶層級的 API 值確定是倍數（文件寫 ≤ 1.0）。details 的 API 值文件沒寫，這次也沒有任何 OKX 實際回應可以看：修正前的程式不讀這個欄位，`outputs/okx-demo-bot/` 的 run 紀錄也沒存保證金率。**待驗證**，見 O1。

## 2. 會不會放寬不該放寬的

做了什麼：`reports/margin-ratio-20261118/scratch/scenarios.py` 把 `DemoClient._request` 換成回固定資料（不連 OKX），直接呼叫 `account_snapshot()`，再套 `demo_bot.py:479` 的同一條判斷（持倉 1 張）。

指令與輸出（`reports/margin-ratio-20261118/scratch/scenarios.log`）：

```
T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe -X utf8 reports/margin-ratio-20261118/scratch/scenarios.py
S1 Futures：頂層空、USDT details 50               mgn_ratio=50     margin_ok(持倉)=True
S2 兩處都空                                      mgn_ratio=None   margin_ok(持倉)=False
S3 兩處都沒有欄位                                   mgn_ratio=None   margin_ok(持倉)=False
S4 頂層空、details 0                             mgn_ratio=0      margin_ok(持倉)=False
S5 頂層空、details 負值 -1                         mgn_ratio=-1     margin_ok(持倉)=False
S6 頂層空、details 2.99（低於門檻）                    mgn_ratio=2.99   margin_ok(持倉)=False
S7 頂層空、details 3（剛好門檻）                       mgn_ratio=3      margin_ok(持倉)=True
S8 頂層空、details 非數字 abc                       DemoError: OKX 回應的 mgnRatio 不是數字
S9 頂層空、details NaN                           DemoError: OKX 回應的 mgnRatio 不是有限數字
S10 頂層空、details Infinity                     DemoError: OKX 回應的 mgnRatio 不是有限數字
S11 只有 BTC details 有值、USDT 空                 mgn_ratio=None   margin_ok(持倉)=False
S12 BTC 在前且有值、USDT 2                         mgn_ratio=2      margin_ok(持倉)=False
S13 多幣種：頂層 2、details 50（並存）                  mgn_ratio=2      margin_ok(持倉)=False
S14 頂層 0、details 50                          mgn_ratio=0      margin_ok(持倉)=False
S15 頂層 abc、details 50                        DemoError: OKX 回應的 mgnRatio 不是數字
S16 頂層 50、details abc（不會讀到）                  mgn_ratio=50     margin_ok(持倉)=True
S17 頂層空白字串 ' '、details 50                    DemoError: OKX 回應的 mgnRatio 不是數字
S18 頂層 null（JSON null）、details 50            mgn_ratio=50     margin_ok(持倉)=True
S19 details 數字型別 50（非字串）                     mgn_ratio=50     margin_ok(持倉)=True
```

逐項：
- 兩處都沒有（S2、S3）：`None`，持倉時不安全。和 commit 說明一致。
- 0、負值、低於 3（S4–S6）：不放行。只有 `>= 3` 放行（S7），和修正前同一條門檻（`catos/demo_bot.py:479`）。
- 非數字、NaN、Infinity（S8–S10）：`_dec`（`catos/okx_demo.py:226-236`）丟 `DemoError`，`_call` 重試後以 `okx_read_failed` 停 Bot（`catos/demo_bot.py:317-330`）。比降級更嚴，見 O3。
- 別的幣種（S11、S12）：只讀 `ccy == "USDT"` 那一筆，和 `usdt_eq` 用的是同一筆（`catos/okx_demo.py:607`），BTC 的值不會被拿來用。
- 並存（S13、S14、S16）：帳戶層級優先，只要它有值（包括 0）就不看 details。多幣種／組合保證金模式下帳戶層級才是整體強平指標，優先它是對的；0 不會被 details 蓋掉，不會放寬。
- 健康判定：`margin_ok` 只在 `risk.observe` 的 HEALTHY 條件裡當 AND 用（`catos/risk.py:525-528`），`Snapshot.margin_ok` 預設 False（`catos/risk.py:384`），符合 AGENTS.md INVARIANTS「risk.Snapshot … 預設為 False（fail-closed）」。

## 3. 其他用到的地方

做了什麼：在 repo 中排除 `outputs/`、`node_modules/`、`reports/` 後 grep `mgn_ratio|mgnRatio|account_snapshot`。

看到什麼：只有三個檔案。
- `catos/okx_demo.py:601-616`（被改的函式本身）
- `catos/demo_bot.py:302`（`_account` 呼叫）、`catos/demo_bot.py:313`（傳進 facts）、`catos/demo_bot.py:479`（唯一的判斷）
- `tests/test_demo_bot.py`

`usdt_balance`（`catos/okx_demo.py:366-372`）、`account_report.py`、前端都沒有讀保證金率，不受影響。

## 4. 測試是否守住

做了什麼：
1. 跑 `MarginRatioTests` 與相關模組。
2. 變異檢查：`reports/margin-ratio-20261118/scratch/mutants.py` 在記憶體內換掉 `DemoClient.account_snapshot`，或把 `catos/demo_bot.py` 原始碼改一處後 exec 回模組，再跑 `MarginRatioTests`。不改 `catos/`、`tests/` 的檔案。
3. 整套 Python 測試（discover）。

指令與輸出：

```
T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe -m unittest tests.test_demo_bot.MarginRatioTests -v
Ran 3 tests in 4.580s
OK
```

```
T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe -m unittest tests.test_demo_bot tests.test_okx_demo tests.test_risk
Ran 97 tests in 87.731s
FAILED (errors=1)
```
唯一的錯誤是 `test_risk` 匯入失敗（`from test_ipc import config`，要從 `tests/` 目錄 discover 才找得到），與這個改動無關；整套 discover 的結果在下面。

變異檢查（`reports/margin-ratio-20261118/scratch/mutants.log`）：

```
baseline: run=3 failed=0 SURVIVED []
top_only: run=3 failed=1 KILLED ['test_futures_mode_ratio_lets_the_reversal_open']
details_only: run=3 failed=1 KILLED ['test_account_level_ratio_still_works']
details_first: run=3 failed=0 SURVIVED []
missing_is_safe: run=3 failed=1 KILLED ['test_no_ratio_with_a_position_keeps_increases_closed']
any_ccy: run=3 failed=0 SURVIVED []
threshold_gt0: run=3 failed=0 SURVIVED []
threshold_100: run=3 failed=2 KILLED ['test_account_level_ratio_still_works', 'test_futures_mode_ratio_lets_the_reversal_open']
drop_none_check: run=3 failed=0 SURVIVED []
always_ok: run=3 failed=1 KILLED ['test_no_ratio_with_a_position_keeps_increases_closed']
```

判讀：
- 這次修正的三個行為都守住了：退回修正前（top_only）、拿掉帳戶層級（details_only）、兩處都沒有卻當安全（missing_is_safe、always_ok）都被抓到。
- `drop_none_check`（`(ratio or 0) >= 3`）是等價變異，行為不變，不算漏洞。
- 沒守住的三個：優先序顛倒（details_first）、不分幣種取第一筆（any_ccy）、門檻放寬成 `> 0`（threshold_gt0）。前兩個由這次修正引入但實際風險低，第三個是修正前就有的缺口。見 O2。
- FakeOkx 的預設改成 `margin_ratio_at = "futures"`（`tests/test_demo_bot.py:91`），所以整個 `DemoBotTests` 現在都走 details 這條路；`test_no_ratio_...` 也確認了反手只平倉時 `why.health == "DEGRADED"`。

整套測試：

```
T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"
exit=0
Ran 907 tests in 240.273s
OK
```
完整輸出在 `reports/margin-ratio-20261118/scratch/full-suite.log`。附帶發現：這套測試本身會在 `outputs/` 留下兩個 fixture 證據目錄（`outputs/workspace-w6-fixture-test-28749b58805e438797873075a1a37141`、`outputs/workspace-w8-fixture-test-0eb24e5ed8524900a8381e555e0ffbd2`），這是既有測試的行為（輸出寫「Retained fixture unit evidence」），沒碰到任何 Bot run。我沒有刪掉這兩個目錄，見 O5。

## 觀察

### O1　details[].mgnRatio 的單位與模擬盤是否真的有值：待驗證
- 文件只說是「Cross maintenance margin ratio of currency」，沒有公式、單位或非空範例；帳戶層級才明寫 ≤ 1.0 為強平。
- 如果是倍數（和帳戶層級一致，OKX 其他 mgnRatio 欄位也是這樣），門檻 3 = 300%，等於說明中心的預警線，正確。
- 如果是百分比數字，門檻 3 = 3%，低於強平線，檢查形同虛設。以目前規模（1 張 BTC-USDT-SWAP，面值約 640 USDT、權益約 5,000 USDT）比率是千倍等級，兩種單位都不會跨門檻，所以眼下不會造成錯誤放行；張數加大或上實盤前要確認。
- 修正的根因也還沒直接證據：`7a08ab81…/events.jsonl` seq 28 的 `order` 事件沒有 `why`（`3520f4b4` 才加），所以「健康因保證金率降級」是由文件推論，不是 log 證明。之後（23:40 起）的兩個 run 還沒遇到持倉中的加倉或反手。
- 重現／確認方式：下一次模擬盤持倉時，用唯讀的 `GET /api/v5/account/balance?ccy=USDT` 看 `details[0].mgnRatio` 的值，再用 `details[0].eq / details[0].mmr` 對照（倍數的話兩者約略相等）；或等 Bot 下一次持倉中反手，看 `order` 事件的 `why.health` 是不是 HEALTHY。這次驗收照限制沒有連 OKX。
- 建議（不是缺陷）：在 `bar` 或 `risk` 事件裡記下 `mgn_ratio`，之後就不用再推論。

### O2　測試沒守住優先序、幣種與門檻邊界
- 重現：`T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe reports/margin-ratio-20261118/scratch/mutants.py details_first`（`any_ccy`、`threshold_gt0` 同樣），三個都 SURVIVED。
- `details_first`：多幣種／組合保證金模式下若兩處並存，會拿幣種層級蓋掉帳戶層級。依文件 details 只在 Futures 模式有值，實際並存機率低。
- `any_ccy`：程式用的是和 `usdt_eq` 同一筆 USDT row，又帶 `ccy=USDT` 查，要寫錯才會出事；目前的測試抓不到這種寫錯。
- `threshold_gt0`：FakeOkx 只會回 `"50"` 或空值，所以門檻 3 從來沒被測過（修正前就是如此）。
- 建議補：一個並存情境（頂層 2、details 50，應不安全）、一個 BTC 在前的 details、一個低於門檻的值（例如 `"2.9"`，應不安全）。

### O3　details 是非數字時，Bot 會停而不是降級
- 修正前 details 的 `mgnRatio` 完全不讀；現在帳戶層級為空時會讀，值不合法就經 `_dec` 丟 `DemoError`，重試用完以 `okx_read_failed` 停 Bot（S8–S10；`catos/okx_demo.py:226-236`、`catos/demo_bot.py:317-330`）。
- 這是 fail-closed，和帳戶層級 `mgnRatio` 本來的處理方式相同；OKX 文件說這個欄位是數字字串，發生機率低。只是持倉中停下時不會自動平倉（保底停損仍在 OKX 上），提出來讓開發者知道多了一條停機路徑。

### O4　多幣種／組合保證金模式的退回路徑
- `account_issues` 允許 acctLv 2、3、4（`catos/okx_demo.py:631`）。在 3、4 模式下，若帳戶層級暫時為空、而 USDT details 剛好有值，會拿幣種層級的值代替帳戶整體。依文件 details 的 `mgnRatio` 只適用 Futures 模式，這條路實際上應該走不到；記錄下來，不視為缺陷。

### O5　整套測試會寫入 outputs/（和這次改動無關）
- 重現：在 repo 根目錄跑 `T=$(mktemp -d) && HOME=$T USERPROFILE=$T .venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"`，輸出會有兩行「Retained fixture unit evidence: C:\dev\CatOS\outputs\workspace-w6-fixture-test-…／workspace-w8-fixture-test-…」。
- 不影響正式資料根或 Bot run，但和「outputs/ 只讀」的驗收限制有衝突。這兩個目錄是否刪除，由使用者決定。

## 沒做的事
- 沒有連 OKX（含模擬盤）、沒讀金鑰檔，所以 O1 的單位和實際值沒有一手 payload。
- 沒跑前端檢查（`npm` typecheck／test／build、`simulation_integration_test.mjs`）：這次改動沒有碰前端，也沒有前端讀這個欄位。
- 沒有動 `outputs/` 的任何 run，只讀了 `7a08ab81…`、`dd5de9dd…`、`5ff76d05…` 的 `events.jsonl`。
- 沒改 `catos/`、`tests/`，沒有 commit、push。

## 附件（`reports/margin-ratio-20261118/scratch/`）
- `scenarios.py`、`scenarios.log`：第 2 節情境
- `mutants.py`、`mutants.log`：變異檢查
- `full-suite.log`：整套 Python 測試輸出
- `docs/get-balance-mgnRatio-excerpt.txt`：OKX 文件原文摘錄；`docs/okx-docs-v5.html`、`docs/okx-docs-v5.txt` 是 2026-11-18 下載的整頁原檔與轉出的文字
