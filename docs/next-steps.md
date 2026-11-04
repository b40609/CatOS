# v1 之後的下一步

更新：2026-11-04（第二個策略 Donchian）。v1 local-sim 已正式獨驗 PASS（`reports/v1-acceptance-20261104/acceptance.md`），合併進 `main`（`845ab14`）並推送。本文件整合舊分支上的 `docs/v2-candidates.md`（`d8c2133`，未合併）。

## 候選工作包

| # | 工作包 | 內容 | 成本／風險 | 需要的授權或決策 |
| --- | --- | --- | --- | --- |
| A | v1.1 全站真資料（已完成並合併） | 風控中心、系統日誌、策略中心改讀控制面資料；刪掉 `lib/mock/data.ts`、假即時數值 hook（`useLiveNumber`／`useLiveSeries`）與只剩測試在用的 `lib/mock/terminal.ts` | 小。只動前端三頁；資料 `catStore` 已在輪詢（`state/catStore.ts:41-48`），後端端點已在（`catos/local_sim_control_api.py:118,130,138`） | 不需新授權 |
| B | Kill-Switch／re-arm／門檻修改 HTTP | 把 `supervisor.latch`、`set_loss_limits`、`rearm`（`catos/supervisor.py:108,952,970`）接上 HTTP 和風控中心按鈕 | 中。牽涉鎖存與人工恢復政策；Demo 前必備 | 恢復介面細節（確認步驟、誰能 re-arm）。動工前先查業界／開源做法再提方案 |
| C | 真實歷史 K 線研究 | 研究目前寫死一份 96 根合成資料（`catos/research_catalog.py:21-22,222`）。改成可登錄多份資料集，用 `tools/fetch_okx_candles.py` 抓 OKX 公開歷史 K 線跑回測／優化 | 中。公開行情 GET，不用金鑰 | 採集授權（AGENTS.md：採集不因工作包自動授權） |
| D | OKX Demo 接線 | Supervisor 持金鑰連 OKX 模擬盤、下單、對帳 | 大，多個工作包；I-b-4 Demo 對帳未通過仍是已知阻斷（`docs/demo-collection-handoff.md`） | Demo 授權、金鑰保管方式；建議 B 先完成 |
| E | v2：策略上傳／多 Bot／Yaozi 重啟 | python_strategy 上傳製品（測試已 skip）、多 Bot 多策略、市場情報線解凍 | 大 | 受信策略邊界、資料模型、採集邊界 |

## 建議順序

1. **A 已完成**（2026-11-04），已通過獨立驗收（`reports/v1.1-acceptance-20261104/acceptance.md`）並合併進 main（`0dc1fae`）。過程中發現策略覆盤頁也是假資料（sin 波曲線與寫死的「實盤淨值」），已改標「v1 未啟用」；實作紀錄見 `docs/simulation-api-contract-draft.md` 第 10 節。
2. **方向已定：研究線**（2026-11-04 使用者選定）。工作包 C 已完成並通過獨立驗收（`reports/research-real-data-acceptance-20261104/acceptance.md`，6/6 PASS）；驗收後依觀察 O1、O7、O8 補了請求上限硬鎖與文件，這部分只有開發者自測：已抓取 BTC-USDT-SWAP 15m 90 天的公開資料，回測與優化可選資料集。方案、授權範圍與實作紀錄見 `docs/research-real-data-plan.md`。原本的選項：
   - 研究線（C）：先找到值得跑的策略。現在唯一的策略是 SMA，只在合成資料上跑過，接 Demo 只能驗證管線。
   - 實盤線（B → D）：先讓下單、對帳、緊急停止在真交易所跑通。
   - 我傾向研究線先行：風險最低、不碰金鑰，而且能早點知道策略值不值得上線。這是產品方向，由你決定。
3. **滾動驗證接上真實資料**（2026-11-04，分支 `feat/research-validation-real-data`，獨立驗收 7／7 PASS，`reports/research-validation-real-data-acceptance-20261104/acceptance.md`；驗收後依觀察 O1–O4 補了回看根數上限、前端預檢與文件數字，只有開發者自測；已合併進 `main`（`aa4def4`）並推送）：驗證結果升為 v2（不保存逐根明細），真實資料上以研究服務實測 4.35 秒、result.json 0.6 MB（原本 14 MB，超過 2 MB 上限）；前端新增「滾動驗證」頁。樣本外結果：SMA 在 6 個視窗中 5 窗虧損（1 張、本金 10,000），和樣本內優化的結論一致。方案比較與量測見 `docs/research-real-data-plan.md`。研究線接下來的候選：月度收益矩陣、保證金與強平模型、換一個策略再驗證（已做，見第 4 項）。
4. **第二個策略：Donchian 通道突破**（2026-11-04 使用者從四個候選中選定，分支 `feat/research-second-strategy`；只有開發者自測，尚未獨立驗收，未合併）：研究端改成固定白名單兩個策略，回測、優化、滾動驗證都可選；Donchian 的 manifest 放在 Worker 不讀的 `catos/research_only_artifacts/`，local-sim Bot 仍只用 SMA。真實資料上和 SMA 同計畫比較：成交 582 → 55 筆，淨損 338.51 → 58.52 USDT，但扣成本前的價格損益仍為負，6 窗 2 窗為正，各窗選出的參數不穩定。研究服務實測最慢 5.25 秒、result.json 最大 0.69 MB。候選比較、規則與量測見 `docs/research-real-data-plan.md` 的「第二個策略」。研究線接下來的候選：放寬 SMA 週期上限做對照、加停損或依波動調整部位、取得更長的資料（需另行授權採集）。

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
| `feature/catos-react-vite`（本機多一個 `d8c2133`，內容已併入本文件；遠端停在 `5a101d4`，已包含在 `main`） | 已刪除本機與遠端 |
| 遠端 `feature/catos-v1-sim`（已合併進 `main`） | 已刪除；之後重新推送 `ab5043d`，以 PR #1 合併進 `main`（`6ffd18f`），遠端分支目前還在 |
| 遠端 `feature/frontend-redesign-v2`、`archive/catos-v1` | 保留（歷史） |
| `docs/review-20261102/`（11/02 讀碼筆記，行號以舊版 `fffed2e` 為準） | 已刪除 |
| `.git/worktrees/main-wt`、`main-wt2` | 已刪除 |
| `.claude/launch.json`（本機 Vite 預覽設定） | 改用本機 `.git/info/exclude` 忽略，沒有改 `.gitignore` |
| 筆電工作樹仍有舊的 CRLF 檔 | 已處理：滾動驗證合併後，452 個檔案就地改為 LF，逐檔核對與 index 位元組一致，沒有跑 `git reset --hard`；策略登錄與資料集測試通過 |

## 兩台機器怎麼分工

- 之後以 `main` 為基底，每個工作包開一條短分支，獨驗通過再合併 `main`（合併和 push 要你下指令）。
- 同一時間只在一台機器改前端；開工前先拉 `main` 最新版。
- 獨立驗收由沒參與該工作包開發的另一個 Claude 會話執行。
