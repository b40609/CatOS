# 第 2 步提案：研究策略上 local-sim Bot 跑歷史重播

2026-11-12 提案，等使用者定案。這份只是設計，沒有改任何程式。目的是第一次接通「研究 → 部署」，不是宣稱 Donchian 會賺錢：研究結論仍是「有跡象、不顯著」（`docs/research-real-data-plan.md` 工作包 D、E）。

## 需要你決定的事

每題附建議。全部照建議，回「照建議」即可。

| # | 題目 | 建議 | 其他選項 |
| --- | --- | --- | --- |
| 1 | 核准怎麼做、存在哪 | 本機核准紀錄（git 忽略、只增不改），只能用 CLI 核准，要輸入完整 sha256；代理不得執行核准或撤銷（方案 A） | 把 manifest 搬進 `catos/research_artifacts/`，以 commit 當核准（方案 B）；介面按鈕核准（方案 C） |
| 2 | 核准要不要綁參數 | 要綁。核准的單位是「部署設定」：策略、版本、來源 sha256、manifest sha256、參數、張數、合約、週期 | 只綁策略與 sha256，參數在啟動 Bot 時另選 |
| 3 | 用哪個 Donchian、什麼參數 | `donchian-breakout`／`donchian-parameters-v1`，entry 192／exit 48、預熱 192、1 張、本金 10,000 | 384／48（優化與滾動驗證選到的值）；工作包 E 的集成或波動目標版（不建議，理由見第 2 節） |
| 4 | 重播速度 | 全速重播；本機估計 5 年 4H 約 9～10 分鐘跑完。另留「每根 1 秒」的展示步調 | 只做展示步調（10,956 根約 3 小時） |
| 5 | 一致性的門檻 | 成交逐筆完全相等，誤差 0。比對基準是「關掉資金費與保證金模型」的同一份研究回測；和已發表研究結果的差只允許資金費 | 允許小額容差（例如每筆 0.01 USDT） |
| 6 | 和新風控預設的先後 | 第 2 步先做，不等。重播把風控上限當參數，另外用新值（0.5 倍、Soft 5%、Hard 10%）跑一次對照，不改預設；第 3 步新預設上線後再重跑一次 | 先做第 3 步再做第 2 步；或兩包一起做 |
| 7 | 重播中碰到 Soft／Hard | 停止該次重播並記錄原因，不模擬清倉；1 張時實際碰不到（見第 4 節）。完整的鎖存與清倉行為留給第 3 步 | 在重播裡完整模擬 Soft 停增倉、Hard 市價清倉 |
| 8 | 反手（多翻空） | Supervisor 拆成兩腿：先平倉、再開反向，同一根開盤成交。4H 資料上兩組參數的反手次數都是 0，但 Demo 前一定要支援 | 先不支援，遇到反手就判一致性失敗、停止重播 |

第 1、2 題會改 INVARIANTS 的 P1 條文（建議的新文字見第 6 節），依規則要你定案。

## 0. 現況：Bot 路徑上寫死 SMA 的地方

讀程式後，下列地方都假設 Bot 只會跑 SMA period 2，換策略前都要改：

- 登錄表只讀 `catos/research_artifacts/`（`catos/strategy_registry.py:25`）。`instantiate()` 固定用研究預設參數 `period`、`quantity`（`catos/strategy_registry.py:140-143`），`restore()`／`snapshot()` 直接讀寫 `strategy.closes`（`:145-152`）。
- IPC 檢查點只存最後 2 個收盤價：長度固定 `min(seq, 2)`（`catos/ipc.py:284`），Supervisor 用 `(*previous.closes, bar.close)[-2:]` 獨立重算後比對（`catos/ipc.py:352-353`）。
- Worker 檢查來源有沒有被改時，呼叫的是 SMA 預設的 `provenance()`（`catos/worker.py:26-29`）。
- 委託意圖的 key 寫死 `ipc.STRATEGY_ID`（`sma-trend`）與 `ipc.STRATEGY_VERSION`（`catos/journal.py:953-954`）。
- 風控把跨零的目標部位直接拒絕（`cross_zero_forbidden`，`catos/risk.py`，`evaluate` 內），而研究引擎一筆成交就反手（`catos/research.py`，`_Ledger.execution`）。
- local-sim 控制面只有一個模板 `sma-synthetic-smoke-v1`，8 根合成 K 線、每根 1 秒（`catos/local_sim_control.py:20-25`）；`control.json` 驗證時要求 `run["config"] == CONFIG`、`bars <= 8`、`fills <= 8`（`:177`、`:185-188`）。
- runner 把 K 線時間改成「今天台北 22:00」起算（`catos/local_sim_control_runner.py:54-57`），首日基準權益寫死 1000（`catos/local_sim_r4.py:134`），`fixture_budget` 也是 1000（`catos/local_sim_control_runner.py:63`）。任何風控停機都直接丟例外（`catos/local_sim_r4.py:154-155`），任何非 `NO_INTENT`／`NO_CHANGE`／`RESERVED_SIMULATION` 的判定也會中止（`catos/local_sim_control_runner.py:104-105`）。
- 介面的策略與 Bot 清單只回 SMA（`catos/simulation_catalog.py:30-42`）。
- 研究端的 Donchian 已有獨立 manifest、白名單 sha256 與 build_id 綁定（`catos/research_catalog.py:37-50`、`:95-99`），這部分不用改。

已經對齊、可以直接沿用的：local-sim 的成交價與手續費是用研究引擎同一段程式算的（`catos/local_sim_control_runner.py:107-111` 呼叫 `research._Ledger.fill`，下一根開盤加滑價、依方向取整到 tick），帳戶檢視也用研究核心重放成交（`catos/local_sim_r4.py:83-94`）。所以「同一份資料、同樣成本參數」下，成交可以要求完全相等。

## 1. 業界與開源做法（查閱日期 2026-11-12）

| 框架 | 回測和部署是同一份策略程式嗎 | 歷史重播進部署路徑 | 成交模型 | 核准或版本綁定 |
| --- | --- | --- | --- | --- |
| Freqtrade | 同一個策略類別；文件把 dry-run 描述為看「what is the performance of your strategy」，沒有逐字寫「同一份」（[configuration](https://www.freqtrade.io/en/stable/configuration/)） | 沒找到「把歷史 K 線餵進 dry-run」的功能，**待驗證**。重啟時用 `startup_candle_count` 拉歷史 K 線暖指標（[strategy-customization](https://www.freqtrade.io/en/stable/strategy-customization/)） | 回測：「Entries happen at open-price」，訊號出場在下一根開盤；dry-run 市價單「fill based on orderbook volume」，最多 5% 滑價（[backtesting](https://www.freqtrade.io/en/stable/backtesting/)、[configuration](https://www.freqtrade.io/en/stable/configuration/)） | 沒有核准機制。回測匯出的 zip 含「A copy of the strategy file」，但不含依賴檔；快取在策略與設定相同時重用，並警告會「silently skip changes to modules strategies import」 |
| NautilusTrader | 是：「The same strategy and execution-algorithm code can run across backtest and live systems」（[overview](https://nautilustrader.io/docs/latest/concepts/overview/)） | 回測就是把歷史資料當串流餵進同一套元件，BacktestNode 提供「catalog-backed, configurable runs」（[backtesting](https://nautilustrader.io/docs/latest/concepts/backtesting/)） | K 線拆成開、高、低、收四個價位點；`on_bar` 送出的單在四個點處理完才到，沒有延遲模型時以該根收盤的盤口成交，不是下一根開盤（[bar-execution](https://nautilustrader.io/docs/latest/concepts/backtesting/bar-execution/)） | 沒查到核准機制，**待驗證** |
| Jesse | 文件說 paper／live「supported by Jesse via an official plugin」，需要授權金鑰；沒有逐字寫同一份策略，**待驗證**（[livetrade](https://docs.jesse.trade/docs/livetrade)） | 研究模式可從資料庫取 K 線、結構和策略 `self.candles` 相同（[research/candles](https://docs.jesse.trade/docs/research/candles)，經搜尋摘要，未逐字核對，**待驗證**） | 沒查，**待驗證** | 沒查到 |
| QuantConnect LEAN | 官方說法是同一份演算法從回測到實盤不用改程式（[algorithm-engine](https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/algorithm-engine)，經搜尋摘要，未逐字核對，**待驗證**） | 有「reconciliation」：把實盤權益曲線和同期的樣本外回測疊在一起看（[reconciliation](https://www.quantconnect.com/docs/v2/writing-algorithms/live-trading/reconciliation)） | 實盤成交價由券商決定；差異來源列了資料、成交、手續費、起始狀態，例如「If you don't start your backtest and live deployment on the same date with the same holdings, deviations can occur」 | 沒有容差門檻：「exact overlap」才叫完全對上，沒給量化指標 |

可借鏡的：

- 同一份策略程式跑回測與部署（四個都這樣做）。CatOS 已有：Worker 執行的就是研究用的同一份 manifest 與 sha256。
- 重啟時用歷史 K 線重新暖指標，而不是序列化策略內部狀態（Freqtrade 的 `startup_candle_count`）。第 3 節的檢查點設計照這個做。
- 回測結果留一份策略來源（Freqtrade 的 zip）。CatOS 的做法更嚴：核准紀錄綁 sha256，Worker 載入前重算。
- 對帳先控制起始狀態（LEAN 列的第一個差異來源）。CatOS 的重播從空倉、同一根預熱、同一筆本金開始，起始狀態由程式保證相同。

不照抄的：

- NautilusTrader 預設在本根收盤成交；CatOS 的 INVARIANTS 定的是下一根開盤加滑價，維持不變。
- 四個框架都沒有「使用者逐一核准」這層。這是 CatOS 自己的需求（受信策略邊界：只執行使用者選定並檢查過的策略），沒有現成做法可抄，所以做法保持最小。

## 2. 用哪個 Donchian、參數怎麼定

建議 `donchian-breakout`／`donchian-parameters-v1`，entry 192、exit 48、預熱 192、1 張、本金 10,000、手續費 0.0005、滑價 2 bps。

為什麼是這個策略，不是工作包 E 的變體：

- 狀態只由最近 entry_bars 根決定（`catos/research_donchian.py` 的單調佇列），重啟時重餵最近 192 根就能完全恢復。集成版的停損會逐日上移（`catos/research_daily.py:112-117`），動能版有指數加權變異數（`:161-168`），狀態取決於全部歷史，要另做狀態序列化或從頭重放。
- 固定張數。波動目標版依權益定部位、上限 2 倍名目，會撞到新的單幣 0.5 倍上限，重播和回測必然不同，第一次接通時分不清是接線錯還是風控擋下。
- 原始碼是單檔。集成、動能、DCM 日線三個策略共用 `catos/research_daily.py` 與同一個 sha256（`catos/research_catalog.py:54-55`），核准其中一個等於核准整個檔案。

為什麼是 192／48，不是 384／48：

- 192／48 是工作包 B＋A 在看任何 4H 結果之前就固定的回測參數；384／48 是全期優化選出來的，PBO 的判讀是要保守（工作包 D）。第 2 步要驗證的是接線，不該讓人以為這組參數是「推薦的」。
- 192／48 有 103 筆成交，384／48 只有 56 筆。成交越多，一致性比對涵蓋的情況越多。

本機實測（開發者自測，腳本在本次會話的 scratchpad，不在 repo；資料集 `okx-btc-usdt-swap-4h-20211106-20261106`，10,956 根）：

| 參數 | 成交 | 反手 | 期末權益（含資金費與保證金模型） | 關掉資金費與保證金模型 | 差 | 成交是否相同 |
| --- | --- | --- | --- | --- | --- | --- |
| 192／48、預熱 192 | 103 | 0 | 10,370.68 | 10,373.89 | -3.21（資金費） | 相同 |
| 384／48、預熱 384 | 56 | 0 | 10,628.96 | 10,633.65 | -4.69（資金費） | 相同 |

兩組都沒有強平、沒有保證金拒單。單筆最大成交價 124,728.1，1 張名目約 1,247 USDT，約 0.125 倍權益。

## 3. 歷史重播怎麼做

### 資料

- 從研究資料集讀 K 線：沿用 `research_catalog.load_dataset_bars`，載入時核對 sha256；重播紀錄寫入資料集 id、檔案 sha256 與 `provenance()`。
- 保留真實時間戳，不改成「今天 22:00」。4H K 線收在 UTC 00、04、08、12、16、20 點，其中 16:00 UTC 正好是台北 00:00，所以每天的風控基準照現有規則（`catos/local_sim_r4.py:129-133` 要求新的一天落在台北午夜）就能建立。15m、1H、5m 也成立。
- 資金費：local-sim 現在是 `explicit_zero`（`catos/local_sim_control.py:24`），第 2 步維持不變，差額在一致性報告明列（見第 4 節）。把資金費接進 Supervisor 屬於帳務改動，留到接 Demo 前另議。

### 檢查點與重啟

SMA 的檢查點把策略狀態（最後 2 個收盤）放進 IPC，由 Supervisor 獨立重算核對。Donchian 照這個做，每根要帶 192 根高低價，每筆約 10 KB，10,956 根會讓帳本多出約 100 MB，384 根以上會逼近 64 KB 的訊框上限（`catos/ipc.py:14`）。

建議改成「檢查點 v2：視窗重放」：

- 檢查點只存 `event_seq` 與最後一根的時間，不存策略狀態。
- Worker 重啟時，Supervisor 從帳本已提交的輸入（`inputs` 表）取最近 `lookback` 根，以預熱方式重餵（只呼叫 `update_indicators`，不產生意圖），再接著處理新的一根。
- 適用條件：策略狀態只由最近 `lookback` 根決定。`donchian-breakout` 與 SMA 都符合；不符合的策略（工作包 E 的變體）登錄時就拒絕上 Bot。
- SMA 維持 v1 檢查點不動，舊的 R4 證據與 `local_sim_r4_verify` 不受格式變更影響（但 build_id 會因檔案雜湊改變而改變，和第二個策略合併時一樣，是預期結果）。

### 速度

- 現況實測：用現有 Supervisor、Worker、FakeExchange 路徑把合成 96 根 15m 全速跑完（不等待，SMA period 2，35 筆成交），93 根 4.66 秒，每根約 50 ms，帳本約 5 KB／根（開發者自測，腳本在 scratchpad）。
- 推估 4H 五年 10,956 根約 9～10 分鐘、帳本約 55 MB。這是推估，實作後要實測；控制面的 `control.json` 每個事件都會 fsync，進度更新要節流（例如每 100 根或每秒一次）。
- 建議兩種步調：全速（驗收與一致性比對用）、每根 1 秒（在介面上看 Bot 動作用，跑完 10,956 根約 3 小時，可隨時停）。不做「照實際時間」：4H 照實際時間要跑 5 年，沒有意義。

### 能不能重現

- 決策路徑不讀牆鐘：K 線時間、風控時鐘（`FixtureClock`）、委託到期時間都由資料推導。
- FakeExchange 的成交由研究引擎依下一根開盤決定，沒有隨機數。
- 所以同一份資料、同一筆核准、同一個 build_id，兩次重播的成交清單應位元組相同。驗收時跑兩次比對成交摘要（sha256）。
- 重播紀錄寫入：核准紀錄 id、策略 sha256、manifest sha256、資料集 sha256、build_id、風控上限、成本參數、步調。

### 控制面

- 新增模板 `donchian-4h-replay-v1`（名稱可改），和既有 `sma-synthetic-smoke-v1` 並存。`control.json` 的驗證改成「依模板各自驗證」：舊模板的紀錄照舊規則驗，不改寫、不遷移既有 `control.json`。
- 自測一律用新的隔離資料根與測試埠，不對 `outputs/local-sim-control` 等正式資料根送任務。

## 4. 一致性驗收

### 比什麼

同一份資料、同一組參數與成本參數，比較兩邊：

1. 研究回測，關掉資金費與保證金模型（`funding_events=()`、`margin=None`）。上面實測過，關掉後成交和正式結果完全相同，只差資金費。
2. Bot 重播：從帳本 `execution_fills` 與 `inputs` 讀出。

比對項目與門檻：

| 項目 | 比法 | 門檻 |
| --- | --- | --- |
| 每根的目標部位（Worker 輸出） | 逐根比對研究策略 `on_bar` 的回傳 | 完全相同 |
| 成交清單 | 逐筆比 K 線時間、帶正負號的張數、價格、手續費、成交後部位 | Decimal 完全相等，誤差 0 |
| 已實現損益、累計手續費 | 期末值 | 完全相等 |
| 權益曲線 | 每根收盤估值 | 完全相等 |
| 風控判定 | 每筆意圖的判定 | 全部 `RESERVED_SIMULATION` 或 `NO_CHANGE`；出現任何 `REJECTED` 就判失敗並列出原因 |

為什麼門檻是 0：兩邊的成交價、手續費、已實現損益都由 `research._Ledger.execution` 同一段 Decimal 程式算出，沒有浮點、沒有隨機數。對不上就是接線錯（例如漏一根、早一根、檢查點錯），不是模型誤差。

要說清楚的限制：一致性通過只證明「部署路徑執行了和研究相同的決策」，不證明成交模型接近真實交易所。真實滑價、部分成交、資金費都要到 Demo 才看得到。

### 預期會不同的地方

| 來源 | 研究回測 | Bot 重播 | 預期差異 | 處理 |
| --- | --- | --- | --- | --- |
| 資金費 | 資料集內真實資金費（2026-08-03 起） | 明示為 0 | 192／48：-3.21 USDT；384／48：-4.69 USDT（實測） | 以「關掉資金費」的回測為比對基準；和正式結果的差額寫進報告 |
| 保證金與強平模型 | 單合約全倉、逐根最不利價檢查 | 無（`margin_ok=True`） | 1 張、0.125 倍以下不會強平或拒單，實測 0 筆 | 報告列出「回測強平 0 次、拒單 0 次」；若不是 0 就判不可比 |
| 曝險上限 | 無 | 現行 1.5 倍權益（3.0 倍 × 50%） | 1 張最大約 0.125 倍，不會碰到 | 出現 `symbol_exposure_limit` 就判失敗 |
| Soft／Hard | 無 | 現行 10%／20%；新值 5%／10% | 1 張時單日最大虧損約為名目 × 單根最大跌幅 20.38%，約 254 USDT、2.5%，碰不到 Soft | 第 7 題：觸發就停止重播並記錄 |
| 反手 | 一筆成交 | 被 `cross_zero_forbidden` 擋下 | 4H 上兩組參數 0 次 | 第 8 題：拆兩腿。兩腿同價、手續費按張數相加，和一筆成交的金額相同；比對時同一根的兩腿合併後再比 |
| 本金與基準權益 | 10,000 | 現在寫死 1000 | 不改就不可比 | 改成由部署設定帶入 |

另外跑一次對照（不列入通過條件）：用新風控值 `Limits(leverage=1.0, symbol_share=0.5, soft_loss=0.05, hard_loss=0.10)` 重播同一組設定。`risk.Limits` 已可參數化（`catos/risk.py:26-38`），這只是把值傳進重播，不改預設、不改 INVARIANTS。預期結果和現行值相同。

## 5. 和新風控預設的關係

建議第 2 步先做，不等第 3 步：

- 1 張的部署設定在新舊兩組上限下都碰不到（最大約 0.125 倍、單日最多約 2.5%），一致性結果和預設值無關。
- 等第 3 步會讓「研究 → 部署」再晚一包，而第 3 步（Kill-Switch／re-arm HTTP）和第 2 步改的檔案大多不同。
- 第 3 步上線新預設後，用同一筆核准重跑一次重播，確認結果不變。這也符合授權紀錄「回測要用同一上限重跑」的要求。

如果你希望第 2 步就測到「上限真的會擋」，那要另外設計一組會碰到上限的部署設定，預期結果和回測不同，比對方式改為「每個差異都要對到一筆風控判定」。建議放在第 3 步做。

## 6. INVARIANTS 修改、改動檔案、驗收範圍、工作量與風險

### INVARIANTS 要改的條文

P1 條文的後半段（從「2026-11-03 起登錄策略由…」到結尾）建議改成：

> 2026-11-03 起登錄策略由 `catos/strategy_registry.py` 依 manifest 驅動：只接受 `approved`，以 (strategy_id, version) 解析 entry，載入前核對 source_files 的 sha256，不符即 fail-closed，Worker 不寫死策略模組。Worker 登錄表分兩層：`catos/research_artifacts/` 的內建製品（目前只有 `sma-trend`／`sma-parameters-v1`），以及使用者逐一核准的研究製品。研究製品的 manifest 留在 `catos/research_only_artifacts/` 不動；只有本機核准紀錄裡有一筆有效核准，且 strategy_id、version、來源 sha256、manifest sha256、參數、張數、合約與週期全部相符時，local-sim Bot 與 IPC 才解析得到，其餘研究製品仍解析不到。核准只能由使用者以 CLI 輸入完整 sha256 完成，代理不得執行核准或撤銷；撤銷寫入新紀錄，執行中的 Bot 在下一根 K 線前停止，不自動平倉、不釋放合約。核准紀錄是程序上的防呆，不是安全邊界。核准只涵蓋 local-sim；Demo／Live 另依授權。上 Bot 的策略狀態必須只由最近 `lookback` 根已收盤 K 線決定，重啟時由 Supervisor 以帳本已提交的輸入重餵恢復。2026-11-04 選定的 Donchian（`donchian-breakout`／`donchian-parameters-v1`）與工作包 E、F 的策略，在核准前仍只供研究，由 `catos/research_catalog.py` 以固定白名單核對 sha256。

其他條文不改。「回測、Demo、Live 使用同一策略製品」維持原文，這次的設計就是照它做。

另外建議在 `AGENTS.md`「紅線」加一條：「代理不得執行策略核准或撤銷指令，也不得編輯核准紀錄。」

### 核准機制細節（方案 A）

- 紀錄：`outputs/strategy-approvals/approvals.jsonl`（`outputs/` 已被 git 忽略），只增不改。每筆有：紀錄 id、動作（approve／revoke）、strategy_id、version、來源 sha256、manifest 檔案 sha256、entry、部署設定（參數、張數、合約、週期、預熱）、研究依據（選填，例如研究任務 id）、時間。每行再存前一行的 sha256，讀取時核對鏈，斷鏈就 fail-closed。
- 核准：`python -m catos.cli strategy approve --strategy donchian-breakout --version donchian-parameters-v1 --sha256 <完整 64 碼> --profile <部署設定檔>`。CLI 先重算來源 sha256 並印出 manifest 與參數，要求在終端機輸入 `approve` 確認；stdin 不是終端機就拒絕。完整 sha256 要從研究頁或 `catalog` 輸出複製，確保核准的就是看過的那份。
- 撤銷：`strategy revoke --approval-id <id>`，同樣要終端機確認。
- 解析：`strategy_registry.resolve` 先找內建層；找不到時，到 `research_only_artifacts` 找 manifest，再到核准紀錄找「最後一筆是 approve、而且每個欄位都相符」的紀錄。來源檔案被改、manifest 被改、紀錄被撤銷，都解析不到。
- 誠實的限制：這擋得住「代理順手把研究策略接上 Bot」這類意外，擋不住刻意繞過的本機程式（P1 本來就不提供這種保證）。紀錄只在本機，另一台機器要再核准一次。

### 會動到的檔案

| 檔案 | 改什麼 | 獨立驗收 |
| --- | --- | --- |
| `catos/strategy_approvals.py`（新） | 核准紀錄的讀寫、驗證、雜湊鏈 | 要 |
| `catos/strategy_registry.py` | 兩層解析；依部署設定建立策略，不再寫死 SMA 參數 | 要 |
| `catos/ipc.py` | `WorkerConfig` 帶部署設定 id；檢查點 v2 | 要 |
| `catos/worker.py`、`catos/worker_host.py` | 依策略核對來源；v2 檢查點的重餵恢復 | 要 |
| `catos/journal.py` | 意圖 key 改用設定裡的策略身分；v2 檢查點的存放。**要等 Virtual Lots 刪除合併後再做** | 要 |
| `catos/supervisor.py`、`catos/risk.py` 或 `catos/execution.py` | 反手拆兩腿（第 8 題）；重播時的風控停止處理 | 要 |
| `catos/local_sim_replay.py`（新）、`catos/local_sim_control.py`、`catos/local_sim_control_runner.py`、`catos/local_sim_r4.py` | 重播 runner、新模板、依模板驗證 `control.json`、本金與基準權益參數化、build 檔案清單 | 要（成交與帳戶路徑） |
| 一致性比對工具（新，`tools/` 或 CLI 子指令） | 讀帳本與研究回測逐筆比對、輸出報告 | 要（損益計算） |
| `catos/cli.py` | `strategy approve／revoke／list`、`replay` 子指令 | 不用（工具） |
| `catos/simulation_catalog.py`、`frontend/cat-os-vite/src/`（策略中心、Bot 頁） | 顯示已核准策略與重播進度，唯讀 | 不用，寫明「未經獨立驗收」 |
| `tests/` | 每項對應測試，含「未核准解析不到」「改一個位元組就解析不到」「撤銷後下一根停止」「兩次重播位元組相同」 | 隨所屬模組 |
| `AGENTS.md`、`README.md`、`docs/` | P1 改寫、紅線一條、使用說明 | 不用 |

### 工作量（估計，未實測）

分三包，依序做：

1. 2a 核准與登錄（新模組、登錄表、CLI、測試）：約 1～2 個開發會話。
2. 2b 部署路徑（檢查點 v2、意圖 key、反手兩腿、重播 runner、控制面模板）：約 2～3 個開發會話。`journal.py` 的部分要等 Virtual Lots 刪除合併。
3. 2c 一致性工具、全量重播實測、唯讀介面：約 1～2 個開發會話。

獨立驗收一次涵蓋 2a 到 2c 的金流與 Worker 路徑，預留一輪修正後重驗。

### 主要風險

- `journal.py` 和 Virtual Lots 刪除那條對話會撞檔。2a 不碰它，2b 開工前先確認那邊已合併。
- `control.json` 驗證很嚴（`catos/local_sim_control.py:168-207`）。新模板處理錯會讓 8770 啟動時把正式資料根判成 `simulation_metadata_unavailable`。要用一份正式資料根的唯讀複本測「舊紀錄仍能讀」。
- 全速重播的實際耗時與帳本大小是推估（9～10 分鐘、約 55 MB），每次重播一個新帳本，`MAX_RUNS` 100 次最多約 5.5 GB，需要清理政策。
- 兩腿反手會在同一根 K 線產生兩筆委託，碰到 UNKNOWN 不盲重送、額度保留原子化等既有不變量，這是 2b 裡風險最高的一段。如果你選第 8 題的「先不支援」，可以拿掉這段。
- 一致性通過容易被讀成「策略在部署環境也會賺」。報告開頭要固定寫明：只證明接線，不證明成交模型或獲利。
- 另一台機器沒有 4H 資料集與檔位快照時不能重播，要先依既有授權重抓。

## 7. 方案比較

| | 方案 A（建議） | 方案 B | 方案 C |
| --- | --- | --- | --- |
| 核准 | 本機只增紀錄＋CLI，要輸入完整 sha256 與終端機確認 | 把 manifest 搬進 `research_artifacts/`，commit 即核准 | 介面按鈕＋HTTP API，畫面顯示 sha256 與研究證據 |
| 綁定 | sha256、manifest、參數、合約、週期 | sha256（參數要另開新 manifest 版本才能綁） | 同 A |
| 撤銷 | CLI 寫撤銷紀錄，下一根停止 | 改 `approval_state` 再 commit | 介面按鈕 |
| 和代理的關係 | 代理可以 commit，但碰不到 git 忽略的本機紀錄；規則禁止代理執行 CLI | 代理依規則可自由 commit，核准和一般修改分不開 | HTTP 端點代理一樣能呼叫，要另做確認流程 |
| 研究製品要不要動 | 不動 | 要搬檔或複製，研究端白名單與已發表結果的 provenance 要跟著處理 | 不動 |
| 重播 | 全速＋每根 1 秒 | 同 A | 同 A，另加介面步調控制 |
| 工作量 | 中（約 4～7 個開發會話） | 小（少掉核准模組，約 3～5 個） | 大（再加前端頁面與 API，要先給你看畫面，約 6～9 個） |
| 主要缺點 | 紀錄只在本機，換機器要重新核准 | 「使用者明確核准」沒有可驗證的紀錄 | 工作量大；介面要先做候選畫面給你選 |

建議方案 A：它是能滿足「逐一明確核准、綁版本與 sha256、可撤銷」的最小做法，而且不動已驗收的研究製品。方案 C 的介面可以之後加在 A 的紀錄之上，不用重做。

## 驗證證據（本次只做唯讀量測）

- `research.backtest` 在本機 4H 資料集上跑 Donchian 192／48 與 384／48，結果和 `docs/research-real-data-plan.md` 工作包 B＋A 的數字一致（+370.68、+628.96）。關掉資金費與保證金模型後成交逐筆相同，差額只有資金費。
- 現有 local-sim 路徑全速 93 根 4.66 秒。量測用全新暫存目錄與新帳戶 id，沒有碰正式資料根，跑完已刪除暫存目錄。
- 兩支量測腳本在本次會話的 scratchpad，不在 repo；沒有改 `catos/`、`tests/`、`frontend/`。
