# 方案：讓 Agent 提交策略（2026-11-17，已定案）

依使用者 2026-11-17「按照你建議執行」的工作順序第 2 項：動工前先提方案。使用者同日對下面 3 題回覆「完全同意你的所有建議」（授權紀錄見 `AGENTS.md`）。實作與方案的差異見文末「實作紀錄」。

## 你會得到什麼

你對 Agent 說一句想法（例如「BTC 4H，突破 20 日高點做多，跌破 10 日低點出場」），Agent 自己寫好策略、檢查、回測、優化、滾動驗證，把結果給你看。你覺得可以，就用現有的核准指令核准，策略就能上 local-sim 重播或模擬盤 Bot。整個過程不用改 CatOS 的程式碼。

## 現在為什麼做不到

- 研究能跑的策略寫死在 `catos/research_catalog.py` 的固定白名單（`STRATEGIES`，`catos/research_catalog.py:91`），每加一個策略都要改 CatOS 程式碼、更新雜湊、commit。
- MCP 只能對白名單裡的策略送回測與優化（`catos/research_mcp.py:221-231`），沒有滾動驗證，也沒有「檢查我寫的策略」的工具。
- 九月做的上傳合約 `catos/python_strategy.py`（把原始碼字串塞進 JSON）從沒接上，3 個測試是 skip。

## 業界做法

| 專案 | 策略放哪 | 怎麼指定 |
| --- | --- | --- |
| Freqtrade | `user_data/strategies/` 下的 Python 檔，另可用 `--strategy-path` 加路徑 | `--strategy 類別名稱` |
| Jesse | 專案的 `strategies/<名稱>/` 資料夾 | 路由設定寫策略名稱 |
| NautilusTrader | 任意可匯入的模組 | 設定檔寫類別的完整路徑 |
| QuantConnect LEAN CLI | 每個策略一個專案資料夾 | `lean backtest "專案"` |

共同點是「策略是使用者資料夾裡的普通 Python 檔，平台用名稱或路徑載入」，沒有人走「上傳原始碼字串」的 API。這也最適合 Claude Code、Codex 這類本來就能寫檔的 Agent。

## 建議做法

1. **策略資料夾 `strategies/<strategy_id>/`**：放兩個檔案。
   - `strategy.py`：一個繼承 `catos.research.Strategy` 的類別，每根已收盤 K 線回傳目標部位，和現有 Donchian 的寫法相同（`catos/research_donchian.py:60`）。
   - `strategy.json`：名稱、版本、參數與範圍、預熱根數、下單量的算法。
   - repo 附一個範例策略。
2. **以內容雜湊認版本**：研究服務每次讀檔都算 sha256，結果綁定這個雜湊。檔案改過就是新版本，舊結果仍標著舊雜湊，不會混在一起。
3. **MCP 新增兩個工具**：
   - `research_check_strategy`：檢查格式，並在合成資料上試跑。確認載得起來、不丟例外、目標部位合法、策略狀態只由最近 `lookback` 根 K 線決定（上 Bot 的必要條件）。錯誤用 Agent 看得懂的訊息回報。
   - `research_submit_validation`：滾動驗證，目前只有 HTTP 有。
   - 既有的回測與優化工具改成也接受資料夾策略。
4. **試驗次數紀錄**：每個策略累計跑過幾次回測與優化，寫進每份結果，並交給既有的 DSR 計算。Agent 很容易一直調參直到數字好看，這個數字讓你看得出它試了多少次。
5. **上 Bot 不變**：沿用你本人用 CLI 核准（綁策略、版本、sha256、參數、張數、合約、週期）。Worker 改成也能從策略資料夾載入；核准後檔案再被改，雜湊不符就拒絕執行。
6. **執行位置不變**：研究在既有的研究子程序跑（有逾時，`catos/research_service.py:187`），Bot 在既有的 Worker 子程序跑。兩者都不拿金鑰、不連網。

## 不做的事

- 上傳原始碼的 API、介面上的策略編輯器、Agent 代為核准（紅線不變）。
- 多策略同時跑、自動上 Bot、新的資料採集（只用已授權的 BTC-USDT-SWAP 資料）。
- 安全沙箱：策略仍是受信程式碼（P1 原本就這樣寫）。網路上下載的策略要你自己看過再放進資料夾。

## 要你決定（3 題）

1. **研究階段不用核准。** 策略資料夾裡的策略，Agent 可以直接回測、優化、滾動驗證，只有上 Bot 才需要你核准。這要改 P1 的一句話：原本是「研究策略由 `research_catalog.py` 以固定白名單核對」，改成「研究可執行策略資料夾裡的策略，結果綁定 sha256」。**建議：同意。** 研究只在本機算數字，不碰錢；每個策略都要你核准才能回測，等於回到現在改程式碼的慢流程。
2. **策略資料夾加進 git 忽略。** 你和試用者自己的策略不會被推上公開 repo，只追蹤範例策略。**建議：忽略。**
3. **刪掉從沒接上的上傳合約**：`catos/python_strategy.py` 和 3 個 skip 的測試。git 有歷史。**建議：刪**，順手做「拆九月模組」的一部分。

## 驗收方式

- 開一個全新的 Agent，扮演試用者，只給它 README 和一句策略想法。它只能用 MCP 走完「寫策略 → 檢查 → 4H 回測 → 優化 → 滾動驗證」。卡住的地方就是要修的文件或錯誤訊息。
- 你用核准指令核准它的策略，在 local-sim 重播。一致性門檻沿用第 2 步：Bot 成交和研究回測逐筆相同。
- 改到 Worker 載入與 `strategy_registry`（執行路徑），所以要獨立驗收；其餘自測。

## 預估

一個工作包，約 2 天，含獨立驗收。

## 實作紀錄（2026-11-17）

### 格式

- 策略放在 `strategies/<id>/`，`strategy.json` 加 `strategy.py`。
- 格式寫在 `strategies/README.md`，範例在 `strategies/example-sma-cross/`。
- 讀檔、檢查與雜湊在 `catos/strategy_folder.py`。

### 和方案不同、由代理決定的細節（可推翻）

- **參數只接受整數**，最多 8 個。`lookback` 指向一個參數。參數間的大小限制寫在 `constraints`，例如 `fast < slow`，研究請求、優化格點與部署設定都會檢查。
- **單一檔案**：只能 import 白名單模組（`collections`、`collections.abc`、`decimal` 等與 `catos.research`），不能寫小數點數字、用 `float`，也不能用 `print`、`input`（worker 的 stdout 是回傳通道）。
  - 原因：雜湊只涵蓋 `strategy.py`。另外，價格與部位要維持 Decimal。
  - 這是約定，不是沙箱。
- **建構子用關鍵字參數**（各參數名稱加 `quantity`），只支援固定張數，不支援依權益調整張數。
- **重啟一致性檢查**：在合成 15m 資料上做，資料是固定種子的趨勢隨機漫步，長度為 3 倍 lookback 加 300 根，介於 600 到 6,000 根。
  - 檢查時點：每一根評估 K 線都是一個重啟點，逐根比對。工作量（根數 ×（lookback＋1））超過 200 萬次 update 才改抽樣，抽樣時交易決策點優先；核准一律要求逐根，Bot 的 lookback 上限 512 時一定是逐根。
  - 比法：只餵最近 lookback 根重建的實例，要和看過全部歷史的實例回同一個目標部位。
  - `ready` 規則：餵滿 lookback 根之前必須是 False，剛好餵滿時變 True，和 Bot 的 IPC 規則相同。
  - 同時檢查：載入、建立實例、回測兩次結果相同。
  - lookback 上限 1,900 根；Bot 本身的上限是 512 根。
- **核准**：資料夾策略在核准時，用部署設定的參數在研究 worker 子程序重跑這個檢查，不通過就拒絕。核准紀錄綁定來源 sha256、`strategy.json` 的 sha256 與 entry。之後任何一個檔案改了，Bot 和 Worker 都解析不到。
- **試驗次數**：研究資料夾的 `trials.jsonl` 每送出一次回測、優化或滾動驗證，就記一行：策略、版本 sha256、參數組數。
  - 參數組數：回測算 1；優化算 min(n_trials, 格點數)；滾動驗證算格點數。
  - 每份結果的 `trial_log` 是這個策略（所有版本）到這次為止的累計。
  - 優化結果另外用累計參數組數當 N 算一次 DSR（`dsr_with_history`，Sharpe 變異數沿用本次搜尋）。
  - 紀錄讀不懂時拒絕送出，寧可擋下也不少算。
- **check 不留紀錄**：它在研究 worker 裡同步執行，和回測共用「同一時間一個任務」的限制。結果不存檔，也不算試驗。
- **介面**：回測、優化、滾動驗證頁會列出資料夾策略，參數限制改讀目錄的 `constraints`，不再寫死 Donchian。資料夾策略的優化預設格點是預設值，lookback 參數再加一個兩倍值。
- **一併刪掉的檔案**：上傳合約 `catos/python_strategy.py` 依賴的 `strategy_library.py`、`strategy_mcp.py`，以及兩個證據腳本 `tests/strategy_v1_evidence.py`、`tests/strategy_v1_mcp_probe.py`。原本 skip 的 11 個測試也一起刪了，後端整套不再有 skipped。

### 獨立驗收（2026-11-17）

第一次驗收 FAIL，報告在 `reports/agent-strategy-acceptance-20261117/acceptance.md`。

- **D1**：讀核准紀錄時，用資料夾目前的內容重驗每一筆舊紀錄。改一次已核准的資料夾，整份紀錄就讀不了，Donchian 模擬盤 Bot 也會停。
  - 修正：讀紀錄時，資料夾策略的紀錄只做不依賴檔案的結構檢查。依檔案的檢查只在核准當下，以及該筆核准被解析時做。
- **D2**：檢查沒有重現 Bot 的 `ready` 規則，沿用預設 `ready` 的策略會通過檢查，上 Bot 卻第一根就停。
  - 修正：檢查加上這條規則，`strategies/README.md` 寫明。
- **D3**：重播一致性比對讀的是資料夾目前的版本。
  - 修正：改成先核對核准綁定的來源與 manifest 雜湊，不符就拒絕比對（`strategy_source_changed_since_replay`）。
- **觀察 O1**：重啟檢查從抽樣改成逐根，核准一律要求逐根。
- **其他觀察**：
  - O2：check 端點改在執行緒池跑，不再卡住整個 8770 服務。
  - O3：只剩 1 組有效試驗時，不算累計版 DSR。
  - O4：試驗紀錄每一行都檢查格式。
  - O5：禁止 `print`、`input`。
  - O6：`@dataclass` 搭配 `__future__` 可以載入。
  - O7：允許 `collections.abc` 與 `from catos import research`。
  - O8：資料夾改過之後，錯誤碼改成 `strategy_changed_since_submission`。
  - O9：核准前再比對一次 manifest。
  - O10、O11：文件更正。
  - O12：部署解析直接比對 spec 的 manifest 雜湊。
- 修正後的窄範圍重驗結果見同一資料夾的 `recheck.md`。
