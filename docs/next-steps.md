# v1 之後的下一步

更新：2026-11-12。研究線工作包 B＋A、D、E、F（合併 commit `368092a0`）已於 2026-11-11 推送到 GitHub；下文各項寫的「尚未推送」是 2026-11-09 當時的狀態。v1 local-sim 已正式獨驗 PASS（`reports/v1-acceptance-20261104/acceptance.md`），合併進 `main`（`f1997bd`）並推送。本文件整合舊分支上的 `docs/v2-candidates.md`（`d8c2133`，未合併）。

## 2026-11-11：目標確認與接下來的順序

使用者確認的目標（全文見 `AGENTS.md` 的 GOAL）：試用者是用 AI Agent 輔助寫策略的量化開發者；開源試用的最低門檻是在 OKX 模擬盤跑通「想法 → 研究 → 回測 → 部署」；長期要能同時跑多策略。

同日完成（開發者自測，未經獨立驗收；不碰帳務、風控與執行路徑）：

- 主資料夾搬到 `C:/dev/CatOS`，離開被 Google Drive 同步的桌面。
- Yaozi 市場情報拆成獨立專案，本 repo 移除 `catos/market_*.py`、對應測試與文件；`catos/research_api.py` 不再建立在 market app 上。
- 後端單埠：8770 直接提供建置後的 React 介面，移除 `frontend/workspace`、`frontend/research`、`/app/*` 舊頁面與 8771 preview；新增一鍵啟動 `start.bat`。
- 實測：後端 1225 tests OK（11 skipped）、前端 typecheck 0 錯誤、21 tests 通過、build 成功、`tests/simulation_integration_test.mjs` 12 項通過。

- 同日以 `git filter-repo` 改寫歷史並強制推送：所有分支的歷史移除檔名含 yaozi 的檔案與 `docs/market-*`。2026-09-18 之後的 commit 編號全部改變，文件裡的引用已換成新編號。GitHub 的 PR #1 參照當時仍指向舊 commit，2026-11-12 重建 repo 後已不存在（見下）。
- 同日重寫 `AGENTS.md`：流程規則精簡，改成測試通過就推送、獨立驗收只用在金流路徑、允許較便宜的模型做介面與文件；金融不變量與授權原文不變。舊版在 `docs/archive/AGENTS-20261111.md`。

2026-11-12：

- GitHub repo 重建：舊 repo 改名 `CatOS-old-20261112` 並轉私有（同日已由使用者刪除），用原名建全新的公開 repo，推上 `main`、其餘四個分支與一個標籤，commit 編號不變。新 repo 沒有任何 PR 參照，PR #1 的紀錄不在公開 repo 上。
- 2026-11-11 的改動（拆出 Yaozi、單埠、歷史改寫、規則重寫）由 Gemini 3.8 Flash 做了唯讀驗收，結果與預期相符：後端 1225 tests OK（11 skipped）、前端 typecheck 0 錯誤、21 tests 通過、build 成功、整合測試 12 項通過；從 GitHub 重抓的鏡像有 6 個 ref、歷史裡沒有檔名含 yaozi 的路徑。這是機械檢查，不是金流路徑的獨立驗收。
- 使用者確認：交易所端每個策略各自的停損單不是必要條件；Yaozi 原件的 `outputs` 保留在本機。
- 使用者定案（授權原文見 `AGENTS.md` 授權紀錄）：放寬「研究策略 Bot 選不到」；日損與曝險新預設是單幣曝險 0.5 倍、Soft 5%、Hard 10%，接 Demo 前實作；回測報表加「套用 Soft／Hard 會觸發幾次」；刪除 Virtual Lots 原型。
- 更正：使用者先前對多策略說的「同意」，是指先做好單策略閉環（Donchian 上 local-sim Bot 跑歷史重播，即第 2 步）。組合策略還沒同意，使用者提出保證金交叉污染與成本歸屬兩個疑問，修訂後的草案見「第 6 步的做法草案」。

接下來的順序（第 1 項已完成；第 2 項的規則放寬已同意，下一個就做；其餘待確認）：

1. **回測加保證金與強平模型**（2026-11-12 完成並合併，獨立驗收 PASS，見下節）。
2. 研究驗過的策略能在 local-sim Bot 上跑，行情用已抓取的歷史 K 線重播。不需要金鑰，是「研究 → 部署」第一次接通。2026-11-12 使用者同意放寬「研究策略 Bot 選不到」；放寬方式動工前先提方案定案（建議逐一明確核准，綁定版本與 sha256）。改到 Worker 與策略登錄，要獨立驗收。
3. 工作包 B：Kill-Switch／re-arm HTTP。接 Demo 前必備。日損與曝險的新預設可以併在這包一起做（同屬風控，同一次獨立驗收）。
4. 工作包 D：OKX Demo 接線。這是最低試用門檻的最後一段，需要 Demo 授權與金鑰保管方式的決策。動工前日損與曝險的新預設要已上線。
5. Agent 提交策略的入口（`python_strategy` 上傳製品，測試目前 skip），讓「想法 → 研究」可以由 Agent 走完。
6. 同一幣種多策略：先做訊號合成（各策略輸出目標部位，合成一個淨目標後由單一 Bot 執行，各策略績效用紙上帳歸因）；需要硬隔離時用 OKX 子帳戶；不做本地虛擬分倉。OKX 原生分倉到 2026-11-11 的 API 更新紀錄仍沒有公開介面。做法草案見下面（2026-11-12 修訂，未同意），排在單策略閉環之後。
7. 跨平台（`AccountLock` 目前只支援 Windows）。

### 回測保證金與強平模型（第一步，2026-11-12 完成）

規格、OKX 核實（附連結與查閱日期）、公式、取捨與驗收紀錄都在 `docs/research-margin-model.md`。

- 現況：研究服務（回測、優化、滾動驗證）對 OKX 資料集預設啟用單合約全倉模型。每根 K 線先以開盤價、再以最不利價檢查權益是否 ≤ 維持保證金 + 強平手續費，觸發就強平、扣強平手續費與清算費、權益歸 0 並停止交易；擴大部位時以開盤價估值檢查初始保證金，不足拒單。合成資料集與本機沒有檔位快照時不啟用，結果寫明原因。每份結果有 `margin_model`（是否啟用、檔位 sha256），provenance 列入檔位檔案。
- 檔位快照：`tools/fetch_okx_candles.py --position-tiers`（只限 BTC-USDT-SWAP），存 `data/okx/BTC-USDT-SWAP/position-tiers/`，2026-11-12 抓的 99 檔 sha256 `638d1e4a…79bf`。另一台機器要先抓一次才會啟用。
- 影響：有槓桿或曾爆倉的既有研究結果會改變；`docs/research-real-data-plan.md` 的數字是之前沒有這個模型時跑的。
- 驗收：第一次獨立驗收 FAIL（D1 阻斷、D2 非阻斷），修正後重驗 PASS。報告在 `reports/margin-model-acceptance-20261112/`。
- 驗證證據（合併前在分支上實跑）：後端 `Ran 1247 tests`、`OK (skipped=11)`；前端 typecheck 0 錯誤、21 個測試通過、build 成功；整合測試 12 項 PASS。合併後的結果見本次收尾回報。
- 待驗證（OKX 文件沒寫明，採保守做法）：強平手續費與清算費是否都收；強平價怎麼取 tick；過去幾年的檔位是否和現在的快照相同；市價單估初始保證金用哪個價格。
- 未做：第 2 步（標記價格 K 線取代成交價高低點）、第 3 步（多合約共用保證金）；介面的「啟用／已強平」狀態沒有在瀏覽器實際操作；優化與滾動驗證頁沒有舊結果的「未啟用」標示。

### 第 6 步的做法草案（2026-11-12 修訂，等使用者確認）

使用者問：同一個全倉帳戶裡，一個策略出事會不會拖垮其他策略；手續費與滑價怎麼客觀歸屬。修訂如下：

- 單 Bot、單合約、`cross`＋`net_mode` 不變。交易所只有一個淨部位，保證金與強平都按淨部位算。
- 改成各子策略各自下單，委託標記所屬策略，不在本機合成淨單。每個策略的部位、手續費與滑價都來自自己的真實成交，不用分攤，也不需要差額帳。NautilusTrader 在淨額制交易所上就是這樣追蹤多個虛擬部位。代價是兩個策略在同一根 K 線反向交易時兩邊都付手續費；6a 回測要量出合成能省多少，省得明顯才考慮改回合成。
- 每根 K 線核對各策略部位加總等於交易所實際部位，對不上就停止增倉。
- 各策略部位上限加總不超過帳戶單幣曝險上限（0.5 倍）。單一策略上限建議不超過 0.25 倍：BTC 4H 五年最差的一根跌 20.38%，0.25 倍時帳戶虧 5.1%，會碰到 Soft，碰不到 Hard。
- 各策略有自己的虧損預算，加總不超過帳戶 Soft（5%）；超過就把該策略目標歸零並鎖存，人工恢復。
- 資金比例可以是 0（影子策略）：只記紙上帳、不下單，對帳戶沒有風險。
- 做不到的事：資金硬隔離（同一根 K 線內的跳空，策略虧損可能超過自己的預算，超出的部分由共用權益吸收）、交易所端各策略自己的停損單、靠掛單的策略。要硬隔離就用子帳戶，排在 OKX Demo 接通之後。
- 拆兩段：6a 組合回測、6b 上 Bot（含影子策略），都排在單策略閉環（第 2 步）之後。

### 日損與曝險新預設（2026-11-12 定案，未實作）

- 數值：單幣曝險上限 0.5 倍權益、Soft 5%、Hard 10%（現行 1.5 倍、10%／20%）。用本機 4H 五年資料估算每年最多觸發 Soft 4.4 天、Hard 0.2 天（假設整天滿倉在不利的方向）。
- 實作時要定的細節：0.5 倍由哪個參數得到。現行單幣上限是有效槓桿上限 3.0 倍乘單幣占比 50%；建議把有效槓桿上限改成 1.0 倍、占比維持 50%。
- 上線後，有槓桿的回測要用同一上限重跑。

### 回測的 Soft／Hard 日損觸發次數（2026-11-12 完成）

- 回測結果 JSON（`daily_loss_limits`）、HTML 報表與回測頁面板顯示：照 R1 台北日切日、以當日第一根開盤權益為分母、用最不利價估當日最低權益時，現行（讀 `risk.Limits()`，10%／20%）與新預設（5%／10%，尚未套用到風控）各觸發幾天、每年幾天、第一次日期、最大單日虧損與觸發日清單。純診斷，不改成交與損益、不模擬鎖存、不套用單幣上限。規格、選擇與驗證在 `docs/research-loss-limits.md`。
- 4H 五年實跑：Donchian 384／48（10 張、本金 10,000）新 Soft 4 天（每年 0.83）、其餘 0；時間序列動能（波動目標）現行 Soft 1 天、新 Soft 5 天（每年 1.25）、新 Hard 1 天（2025-10-11，單日虧 11.53%，部位超過 0.5 倍）。都在上面「每年最多 Soft 4.4 天」的估計之內；Hard 略高於 0.2，原因是回測沒套用 0.5 倍上限。
- 驗證：後端 `Ran 1259 tests`、`OK (skipped=11)`；前端 typecheck 0 錯誤、21 個測試通過、build 成功；整合測試 12 項 PASS；介面在隔離服務實際送出 4H 回測並操作面板。開發者自測，未經獨立驗收（報表診斷，不屬損益計算）。commit 見本次收尾回報。
- 待辦：優化與滾動驗證還沒有這個指標；新預設上線時改讀 `risk.Limits()` 並用 0.5 倍上限重跑。

### 已同意、排程中

- 刪除 Virtual Lots 原型（2026-11-12 同意）。`catos/journal.py` 每次開帳本都會建 6 張 lot 表並把 `PRAGMA user_version` 設為 7；正式資料根的 8 個帳本都有這 6 張表，全部 0 筆。做法：刪掉 lot 程式與測試，保留這 6 張表的建表語句，不改 schema、不遷移。

### 等使用者決定

- 第 6 步的做法草案（上面），排在單策略閉環之後。

## 候選工作包

| # | 工作包 | 內容 | 成本／風險 | 需要的授權或決策 |
| --- | --- | --- | --- | --- |
| A | v1.1 全站真資料（已完成並合併） | 風控中心、系統日誌、策略中心改讀控制面資料；刪掉 `lib/mock/data.ts`、假即時數值 hook（`useLiveNumber`／`useLiveSeries`）與只剩測試在用的 `lib/mock/terminal.ts` | 小。只動前端三頁；資料 `catStore` 已在輪詢（`state/catStore.ts:41-48`），後端端點已在（`catos/local_sim_control_api.py:118,130,138`） | 不需新授權 |
| B | Kill-Switch／re-arm／門檻修改 HTTP | 把 `supervisor.latch`、`set_loss_limits`、`rearm`（`catos/supervisor.py:108,952,970`）接上 HTTP 和風控中心按鈕 | 中。牽涉鎖存與人工恢復政策；Demo 前必備 | 恢復介面細節（確認步驟、誰能 re-arm）。動工前先查業界／開源做法再提方案 |
| C | 真實歷史 K 線研究 | 研究目前寫死一份 96 根合成資料（`catos/research_catalog.py:21-22,222`）。改成可登錄多份資料集，用 `tools/fetch_okx_candles.py` 抓 OKX 公開歷史 K 線跑回測／優化 | 中。公開行情 GET，不用金鑰 | 採集授權（AGENTS.md：採集不因工作包自動授權） |
| D | OKX Demo 接線 | Supervisor 持金鑰連 OKX 模擬盤、下單、對帳 | 大，多個工作包；I-b-4 Demo 對帳未通過仍是已知阻斷（`docs/demo-collection-handoff.md`） | Demo 授權、金鑰保管方式；建議 B 先完成 |
| E | v2：策略上傳／多 Bot | python_strategy 上傳製品（測試已 skip）、多 Bot 多策略。市場情報（Yaozi）已於 2026-11-11 拆成獨立專案，完工後以獨立服務接回 | 大 | 受信策略邊界、資料模型 |

## 建議順序

1. **A 已完成**（2026-11-04），已通過獨立驗收（`reports/v1.1-acceptance-20261104/acceptance.md`）並合併進 main（`fc63f2f`）。過程中發現策略覆盤頁也是假資料（sin 波曲線與寫死的「實盤淨值」），已改標「v1 未啟用」；實作紀錄見 `docs/simulation-api-contract-draft.md` 第 10 節。
2. **方向已定：研究線**（2026-11-04 使用者選定）。工作包 C 已完成並通過獨立驗收（`reports/research-real-data-acceptance-20261104/acceptance.md`，6/6 PASS）；驗收後依觀察 O1、O7、O8 補了請求上限硬鎖與文件，這部分只有開發者自測：已抓取 BTC-USDT-SWAP 15m 90 天的公開資料，回測與優化可選資料集。方案、授權範圍與實作紀錄見 `docs/research-real-data-plan.md`。原本的選項：
   - 研究線（C）：先找到值得跑的策略。現在唯一的策略是 SMA，只在合成資料上跑過，接 Demo 只能驗證管線。
   - 實盤線（B → D）：先讓下單、對帳、緊急停止在真交易所跑通。
   - 我傾向研究線先行：風險最低、不碰金鑰，而且能早點知道策略值不值得上線。這是產品方向，由你決定。
3. **滾動驗證接上真實資料**（2026-11-04，分支 `feat/research-validation-real-data`，獨立驗收 7／7 PASS，`reports/research-validation-real-data-acceptance-20261104/acceptance.md`；驗收後依觀察 O1–O4 補了回看根數上限、前端預檢與文件數字，只有開發者自測；已合併進 `main`（`0e36985`）並推送）：驗證結果升為 v2（不保存逐根明細），真實資料上以研究服務實測 4.35 秒、result.json 0.6 MB（原本 14 MB，超過 2 MB 上限）；前端新增「滾動驗證」頁。樣本外結果：SMA 在 6 個視窗中 5 窗虧損（1 張、本金 10,000），和樣本內優化的結論一致。方案比較與量測見 `docs/research-real-data-plan.md`。研究線接下來的候選：月度收益矩陣、保證金與強平模型、換一個策略再驗證（已做，見第 4 項）。
4. **第二個策略：Donchian 通道突破**（2026-11-04 使用者從四個候選中選定，分支 `feat/research-second-strategy`；獨立驗收 7／7 PASS，`reports/research-second-strategy-acceptance-20261104/acceptance.md`；驗收後依觀察 O1–O3、O6、O7 補了預熱預檢、build_id 綁定、前端用語與文件，只有開發者自測；已合併進 `main` 並推送（功能 `59f840f`、修正 `83c4970`），8770 要重啟才會載入）：研究端改成固定白名單兩個策略，回測、優化、滾動驗證都可選；Donchian 的 manifest 放在 Worker 不讀的 `catos/research_only_artifacts/`，local-sim Bot 仍只用 SMA。真實資料上和 SMA 同計畫比較：成交 582 → 55 筆，淨損 338.51 → 58.52 USDT，但扣成本前的價格損益仍為負，6 窗 2 窗為正，各窗選出的參數不穩定。研究服務實測最慢 5.25 秒、result.json 最大 0.69 MB。候選比較、規則與量測見 `docs/research-real-data-plan.md` 的「第二個策略」。研究線接下來的候選：放寬 SMA 週期上限做對照、加停損或依波動調整部位、取得更長的資料（需另行授權採集）。
5. **工作包 B＋A：4H 五年資料與成本歸因**（2026-11-06 使用者同意，分支 `feat/research-strategy-cost`，commit `18370fab`；獨立驗收 PASS 7／7，`reports/research-strategy-cost-acceptance-20261106/acceptance.md`；驗收後依觀察 O1～O6 的修正放在 `feat/research-overfitting`，只有開發者自測；2026-11-09 合併進 `main`（`368092a0`），尚未推送）：
   - 採集 BTC-USDT-SWAP 4H 五年（10,956 根、115 次請求）；資料集可接受只涵蓋尾段的資金費並明示。
   - 回測、優化、滾動驗證都加了精算的成本拆解、每邊兩平成本、買進持有基準，以及資金費固定費率假設情境；三個研究頁都有成本面板。
   - 預先固定的量測結果：
     - SMA 在 4H 仍被成本吃掉，每邊兩平約 1 bps，實際成本 7 bps。
     - Donchian 在 7 個 OOS 視窗中 5 窗為正，合計淨損益 +352.18 USDT，每邊兩平 148.80 bps；但只有 40 筆成交，選定的 entry 都在格點上限，絕對損益低於同期間買進持有（+515.97）。
   - 細節見 `docs/research-real-data-plan.md` 的「工作包 B＋A」。
   - 接下來的候選：
     - 過擬合防護（D）：Deflated Sharpe 與試驗數揭露，放寬 Donchian 範圍前先做。
     - 風險調整指標：Sharpe、與買進持有對照的最大回撤。
     - 波動目標部位加停損（C）。
     - 第三個預先登錄的策略（例如時間序列動能）。
6. **工作包 D：過擬合防護，與放寬 Donchian 範圍**（2026-11-06 使用者同意，分支 `feat/research-overfitting`，commit `fb11e321`；獨立驗收 PASS 4／4，報告 `reports/research-overfitting-compare-acceptance-20261106/acceptance.md`；驗收後依觀察 O1～O6 修正，只有開發者自測；2026-11-09 合併進 `main`（`368092a0`），尚未推送）：
   - 優化結果加 DSR、PSR、PBO（CSCV），滾動驗證加邊界選參統計，前端有對應面板；公式已在 repo 外與 fynance 2.13.1、scipy 交叉核對一致。
   - 預先登錄的放寬量測：
     - entry 放寬到 960 後，OOS 淨損益 +197.27，原範圍是 +208.56（同一組視窗），選定參數在 384 到 960 之間跳動。
     - 兩次搜尋合併 N = 16 時，DSR 0.7083、PBO 0.2000；完整格點聯集 N = 21 時，DSR 0.7111、PBO 0.4286（驗收觀察 O1，PBO 判讀改為保守）。
     - 結論：Donchian 不放寬範圍；證據有跡象但不顯著，還不能當展示策略。
   - 細節見 `docs/research-real-data-plan.md` 的「工作包 D」。
   - 接下來的候選：
     - 優化在格點小於 trials 時改用窮舉。（已在工作包 E 完成）
     - 風險調整指標，例如和買進持有對照的最大回撤。（已在工作包 E 的量測完成）
     - 第三個預先登錄的策略。（見第 7 項）
7. **工作包 E：預先登錄三策略比較與驗證強化**（2026-11-06 使用者同意，分支 `feat/research-overfitting`，commit `98316e41`；獨立驗收 PASS 7／7，同一份報告；驗收後修正同上；2026-11-09 合併進 `main`（`368092a0`），尚未推送）：
   - 三個策略只供研究，規則在跑之前就寫進文件：Donchian 多週期集成、時間序列動能、DCM 日線版。
   - 另外加了逐年、延遲、bootstrap 等驗證工具，優化在格點小時改窮舉，前端三頁可選這三個策略。
   - 結果：
     - 沒有變體達到「展示候選」，DSR 都低於 0.95。
     - 順勢四個變體都是「有跡象」：4 年 +58%～+133%，波動目標版最大回撤 16～17%；同期買進持有 +272%、回撤 53%。
     - DCM 日線版不通過。
   - 細節見 `docs/research-real-data-plan.md` 的「工作包 E」。
   - 接下來的候選（需要決策）：
     - 要不要把順勢波動目標版標成「示範策略（有跡象、未達顯著）」放在研究頁。
     - 測試使用者校準的 DCM「假突破反轉」「突破後回踩」規則。
     - 把驗證強化接到研究頁。
     - 資金費擁擠過濾：需要另一個 OKX 端點的授權。

## 已知小缺口（來自 v2 候選清單與 v1.1 驗收觀察）

- 後端沒有 `exposure_ratio`，前端甜甜圈「佔預算 x%」用浮點換算，只用於顯示。
- bots 艦隊表窄視窗時右側欄位被截斷；權益曲線 y 軸百分比標籤待調整。
- `.venv` 的 pytest 損壞（缺 `_pytest.scope`），後端測試用 `python -m unittest discover`。
- `AccountLock` 只支援 Windows（`catos/account_lock.py`）。
- 後端以 `str(Decimal)` 輸出，絕對值小於 1e-6 的非零值會變成科學記號（如 `5.0E-7`）；前端 `lib/format.ts` 的 `parse()` 只接受零的科學記號，這類值會顯示「不適用」。修法二選一：後端改 `format(x, 'f')`，或前端支援非零科學記號（v1.1 驗收 O1）。
- `simulation_catalog.risk_projection` 的 `can_increase` 沒有納入 `position_verified` 與 `reduction_conflict`；local-sim 四個旗標恆為 True 不會誤顯示，Demo／Live 前要修（v1.1 驗收 O3）。
- 設定頁的「有效槓桿上限 3.0x · 單幣預算上限 50%」是寫死的政策說明，不是讀 `risk.limits`（v1.1 驗收 O6）。
- `pages/backtest.tsx` 用 `parseFloat` 判斷報酬正負色（既有）。
- 命令面板等需要鍵盤操作的元件沒有自動化互動測試；要補需要引入 playwright 或 jsdom。
- 滾動驗證：HTML 報表沒有前端入口；分類規則的預設值沿用合成示範門檻（高波動 250 bps，BTC 15m 幾乎都會分到低波動）；計算量上限 250,000 只在本機量過。
- ~~優化的 HTML 報表內文仍寫「合成資料樣本內搜尋」~~：第 4 項已改為顯示資料集的聲明（分支 `feat/research-second-strategy`）。

## 收尾雜項（2026-11-04 你同意後已處理）

| 項目 | 狀態 |
| --- | --- |
| 已合併的本機分支：`fix/v1-safety`、`docs/v1-release`、`chore/v1-cleanup`、`chore/v1-type-scale`、`feat/v1-simulation-api`、`feat/v1-simulation-endpoints`、`feat/v1-simulation-frontend` | 已刪除 |
| `feature/catos-react-vite`（本機多一個 `d8c2133`，內容已併入本文件；遠端停在 `2633a59`，已包含在 `main`） | 已刪除本機與遠端 |
| 遠端 `feature/catos-v1-sim`（已合併進 `main`） | 已刪除；之後重新推送 `13eb605`，以 PR #1 合併進 `main`（`107c5f6`），遠端分支目前還在；2026-11-12 重建 repo 後 PR 紀錄不在公開 repo 上 |
| 遠端 `feature/frontend-redesign-v2`、`archive/catos-v1` | 保留（歷史） |
| `docs/review-20261102/`（11/02 讀碼筆記，行號以舊版 `02445fe` 為準） | 已刪除 |
| `.git/worktrees/main-wt`、`main-wt2` | 已刪除 |
| `.claude/launch.json`（本機 Vite 預覽設定） | 改用本機 `.git/info/exclude` 忽略，沒有改 `.gitignore` |
| 筆電工作樹仍有舊的 CRLF 檔 | 已處理：滾動驗證合併後，452 個檔案就地改為 LF，逐檔核對與 index 位元組一致，沒有跑 `git reset --hard`；策略登錄與資料集測試通過 |

## 兩台機器怎麼分工

- 之後以 `main` 為基底，每個工作包開一條短分支；測試通過就合併 `main` 並推送，不用等指令。2026-11-11 改：原本寫「合併和 push 要你下指令」，那條讓已合併的工作一週沒推上 GitHub。
- 同一時間只讓一台機器、一個代理改同一批檔案；開工前先拉 `main` 最新版。
- 獨立驗收只用在帳務、風控、執行與研究損益計算的改動，範圍與做法見 `AGENTS.md` 的「獨立驗收」。
- 2026-11-11 改寫過歷史，2026-11-12 重建了 GitHub repo（網址不變）。另一台機器上的舊 clone 不要 pull 或 push（會把舊歷史合回來），刪掉後重新 clone。
8. **工作包 F：短週期研究基礎與預先登錄短週期策略**（2026-11-07 使用者同意，含 1H 3 年、15m 1 年、5m 6 個月的採集授權；分支 `feat/research-overfitting` 上接續；已 commit `fc2ff409`，2026-11-08 獨立驗收 PASS 9／9，報告在 `reports/research-shortterm-acceptance-20261107/acceptance.md`。驗收的 12 項觀察 O1～O11 已在 `51500b88` 修正，2026-11-08 第二輪獨立驗收 PASS 11／11，報告在 `reports/research-shortterm-fix-acceptance-20261108/acceptance.md`；第二輪的 6 項非阻斷觀察 N1～N6 在 `c2f0cba9` 修正，第三輪獨立驗收 PASS 6／6，報告在 `reports/research-shortterm-nfix-acceptance-20261108/acceptance.md`；第三輪的 5 項觀察 P1～P5 在 `b1e637fd` 處理，第四輪獨立驗收 PASS 5／5，報告在 `reports/research-shortterm-pfix-acceptance-20261109/acceptance.md`；第四輪的 2 項觀察 Q1、Q2 只涉及文件，處理見 `docs/research-real-data-plan.md` 工作包 F 末尾表格；2026-11-09 合併進 `main`（`368092a0`），尚未推送）：
   - 完成的基礎：分次接續抓取、回測上限 60,000 根、往返交易統計（勝率、賺賠比、獲利因子、期望值），回測頁顯示勝率與統計面板。
   - 修正兩個問題：延遲測試包裝（工作包 E 重跑後數字不變）、往返統計對帳的捨入殘差。
   - 結果：
     - 15 個預先登錄的短週期變體（DCM 假突破反轉、DCM 突破後回踩、短週期 Donchian；5m／15m／1H／4H）全部不通過，勝率 11.8%～36.8%；短週期 Donchian 在 1H 爆倉（權益跌破 0）。
     - DCM 假突破反轉扣成本前就虧，問題在訊號。
     - 短週期 Donchian 扣成本前小賺，但每邊兩平只有 2.05～2.34 bps，接近 maker 費率。
   - 細節見 `docs/research-real-data-plan.md` 的「工作包 F」。
   - 接下來的候選（需要決策）：
     - 限價單（maker）模擬。只有在找到扣成本前有明顯正期望的訊號後才值得做。
     - 補成交量欄位，測 DCM 的週成本與月成本、量價類訊號。
     - 換其他合約或資料源。
     - 接受「BTC 短週期在零售成本下沒有已知優勢」，改把 Bot 用在日線順勢策略的紀律執行與風控。
