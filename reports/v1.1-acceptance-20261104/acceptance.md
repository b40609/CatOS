# CatOS v1.1「全站真資料」獨立驗收報告

- 日期：2026-11-04（Asia/Taipei）
- 驗收者：Claude Opus 5.5，獨立驗收會話（筆電）。未撰寫本工作包的任何 commit，具 AGENTS.md「DEVELOPMENT WORKFLOW」所定的獨驗資格。開發者是另一個 Claude 會話。
- 範圍：`feat/v1.1-real-data-pages` 的 `845ab14..12fdb09`，1 個 commit，20 個檔案（+736／−1711）。
- 結論：**FAIL（6 項中 5 項 PASS，第 1 項 FAIL）**。缺陷 D2：全站命令面板有兩個假動作，其中一個謊稱「Kill-Switch 已鎖存」。四個改寫頁面本身全部通過。依指示只 commit 本報告，不合併、不 push，修正交回開發者。

## 自我揭露

D2 所在的 `command-palette.tsx` 在 v1 範圍內被 `428e182` 修改過；本驗收者的 v1 正式驗收（`reports/v1-acceptance-20261104/acceptance.md` 第 5 項）沒有發現它。這是 v1 驗收的漏網缺陷，不是本工作包引入的，但本工作包的目標是「全站真資料」，第 1 項的驗收條件明確涵蓋「整站」，所以在此判 FAIL。

## 隔離方式

- 所有重跑都在暫存區的乾淨 clone（`git clone -b feat/v1.1-real-data-pages`，HEAD `12fdb09`）進行。前端以 `npm ci` 全新安裝，不借用工作樹的 `node_modules`，因此能驗證 lockfile。Python 使用 repo 的 `.venv`（3.12.10），Node 使用 24.19.0。
- 瀏覽器實測：以 `tests.integration_http_fixture` 搭配**全新空資料根**，在 18870 起後端、在 18890 起 Vite proxy，用內建瀏覽器操作，用完即關閉，並確認兩個埠都已釋放。
- 沒有碰 8770／8771／8890、既有資料根、憑證或 OKX。後端 Python 在本範圍內沒有變更，所以未重跑後端全套。

## 總表

| # | 項目 | 結果 |
| --- | --- | --- |
| 1 | 四頁與整站沒有殘留展示假值或假即時數字；`lib/mock`、`use-live` 已無引用 | **FAIL**（D2） |
| 2 | Decimal 紀律與 `compareDecimal` 正確性 | PASS（附觀察 O1） |
| 3 | 風控頁語義 | PASS（附觀察 O2、O3） |
| 4 | 日誌與策略頁 | PASS（附觀察 O4） |
| 5 | 刪除的元件與依賴沒有遺漏引用，package.json 與 lockfile 一致 | PASS |
| 6 | README 與文件的敘述和程式一致 | PASS（附註：第 10 節標題「全站真資料」要等 D2 修正後才成立） |

## 缺陷

### D2（阻斷）：命令面板的兩個假動作

- 位置：`frontend/cat-os-vite/src/components/catos/command-palette.tsx`，「風控與應急處置 (Risk & Safety)」群組（第 152–175 行，原始碼註解寫著 `風控處置 (Mock 模擬)`）。
- 掛載方式：`shell.tsx:347` `<CommandPalette />` 全站掛載，任何頁面按 Ctrl／⌘+K 都能開啟（`command-palette.tsx:43`）。
- 兩個項目的 `onSelect` 都只做 `setOpen(false)` 加一則 toast，沒有任何 HTTP 請求，也沒有改動任何狀態：
  1. 「執行帳戶與委託強制對帳 (Recon Audit)」→ `toast.info("已執行帳戶快速對帳檢查，本地與 OKX 完全一致 (Recon Pass)")`（第 158 行）。這是捏造的對帳結果。v1 不連 OKX，也沒有對帳 HTTP。
  2. 「觸發 Emergency Kill-Switch (模擬鎖存)」→ `toast.error("已觸發模擬緊急停止 (Kill-Switch Latch 已鎖存)")`（第 168 行）。實際上什麼都沒有鎖存；README 也寫明 v1「沒有 Kill-Switch／re-arm HTTP，前端對應按鈕標示『未接線』」。
- 情境：使用者在緊急時按 Ctrl+K 觸發 Kill-Switch，會看到「已鎖存」的確認，誤以為已經熔斷，但 Supervisor 什麼都沒收到。對帳項目則會讓人誤信本地與 OKX 已核對一致。
- 嚴重度：高於 v1 的 D1。D1 是靜態假值；D2 是在應急路徑上回報不存在的動作結果，正好違反「未接線的動作沒有任何假行為」。
- 全站掃描結果：`toast.`、`alert(`、`window.confirm`、「完全一致／已鎖存／已下單／已平倉」等字樣，只在這兩處命中；另一個 `toast.info("已聚焦機器人…")`（第 66 行）是真實的前端導覽回饋，不算缺陷。
- 建議最小修法：比照風控頁的 re-arm 按鈕，把兩個項目改為停用並標示「未接線」，或直接移除；不要保留任何成功類 toast。修正後在整合測試的 FORBIDDEN 清單加入 `Recon Pass`、`已鎖存`，或補一個命令面板單元測試。

## 逐項核對

### 1. 四頁與整站沒有假值：FAIL（D2）

四個改寫頁面本身都通過：
- `pages/risk.tsx`：資料全部來自 `useCatStore` 的 `risk`、`bots`、`events`、`connection`，沒有常數數值。re-arm 按鈕為 `disabled`、沒有 `onClick`，標示「人工 re-arm · 未接線」。舊的 re-arm 對話框與規則滑桿已移除。
- `pages/logs.tsx`：資料來自 `events`、`eventsOmitted`、`bots`、`connection`。
- `pages/strategies.tsx`：資料來自 `strategies`、`bots`、`events` 與 `StateAdapter.equityCurve`。績效卡片與啟停開關已移除。
- `pages/review.tsx`：只有說明文字與三個連結（`#/backtest`、`#/bots`、`#/risk`），沒有任何數字。舊版 `845ab14` 確實有 `Math.sin` 曲線與「實盤淨值：12,483,920.00 USDT」（舊檔第 116、162 行）。
- 搜尋 `src tests package.json vite*.ts tsconfig*.json` 中的 `lib/mock|use-live|useLive|ui/slider|ui/switch|react-slider|react-switch|mock/data|mock/terminal`，以及已刪 hook 的匯出名稱 `useClock|nowStamp|fmtMoney|fmtSigned|useLiveFeed`：0 筆引用。使用者工作樹的 `src/lib/mock` 只剩一個 git 不追蹤的空目錄。
- `Math.random` 只剩 `lib/layout-tree/tree-ops.ts:296`，用來產生版面節點 id，與資料無關。

整站：命令面板有 D2，判 FAIL。其他仍含示範數字的地方都已標示，不判缺陷：
- `pages/market-intel.tsx`：頁面標示「v1 未啟用」及「本頁為展示資料；市場情報線在 v1 凍結…」，與 README 一致（觀察 O5）。
- `personal-os-modal.tsx` 主題預覽卡的 `BTC-PERP $64,280.50 +1,280.00 USDT +4.85%`：位於標示「即時渲染預覽 (Live Interactive Preview)」的樣式預覽區，屬色票樣本（觀察 O5）。

### 2. Decimal 紀律：PASS（附觀察 O1）

- 四頁的金額與比例文字只來自後端字串，經 `formatDecimal`、`formatRatioPct`、`qty()`（`formatDecimal(..., {digits: 0})`）輸出。`toPlotNumber` 只出現在以下兩處，都只算幾何：
  - `risk.tsx` `fillPct()`：儀表弧度，夾在 0 到 100。
  - `strategies.tsx`：`AreaChart` 的 `v`；提示框顯示原始 `equity` 字串。
- 本範圍沒有新增由浮點算出的金額或百分比文字。
- 部位以 `digits: 0` 顯示不會失真：v1 合約規格為 `lot_size=1`、`min_size=1`（實測 `validate_request(DEFAULT_REQUEST)[1].contract`）。
- `compareDecimal`（`lib/format.ts`）：兩邊都經 `parse()` 後，補齊小數位數再轉 `BigInt` 比較；任一邊缺值或格式錯誤時回傳 `null`。本驗收者自寫 `cmp-check.mjs`，以 TypeScript 轉譯原始檔後獨立測試 17 個案例，全部符合預期：

```text
PASS compareDecimal("-0", "0") = 0
PASS compareDecimal("+1", "1") = 0
PASS compareDecimal("-0.000", "0E-8") = 0
PASS compareDecimal("0E-7", "-0E-7") = 0
PASS compareDecimal("3000.00000000", "2999.87") = 1
PASS compareDecimal("2999.87", "2999.870000001") = -1
PASS compareDecimal("-2", "-10") = 1
PASS compareDecimal("-10.5", "-10.49") = -1
PASS compareDecimal("0.30000000000000000001", "0.3") = 1
PASS compareDecimal("123456789012345678901234567890.1", "123456789012345678901234567890.09") = 1
PASS compareDecimal("5E-7", "0") = null
PASS compareDecimal("1E+3", "1000") = null
PASS compareDecimal("", "1") = null
PASS compareDecimal(" 1 ", "1") = 0
PASS compareDecimal("1.", "1") = 0
PASS compareDecimal(".5", "0.5") = null
PASS compareDecimal(undefined, "1") = null
formatRatioPct("5.0E-7") = 不適用 | formatDecimal("1E+3") = 不適用
```

- 開發者測試 `state_adapter_test.mjs` 的 `compareDecimal` 案例也通過（見命令表）。

### 3. 風控頁語義：PASS（附觀察 O2、O3）

- 狀態與可否增倉：標頭膠囊與「鎖存狀態」卡直接讀 `risk.derived.status`（經 `RISK_STATUS_META` 轉成中文標籤）與 `risk.derived.can_increase`；鎖存原因直接讀 `risk.reasons.join(", ")`。前端沒有自行推導。
- fail-closed 旗標：`FACTS` 依序顯示 `valuation_known`、`flows_known`、`margin_ok`、`position_verified` 四個旗標，並註明「未宣告即視為未知（fail-closed）」；另一列顯示 `reduction_conflict`。沒有觀測時顯示「不適用」，`false` 以紅字顯示「否」。
- 合成時間：顯示「起算時間 (合成)」與「觀測 seq N · 合成 HH:MM:SS」。
- 未接線動作：「人工 re-arm · 未接線」按鈕為 `disabled`、沒有 handler（瀏覽器實測 `rearmDisabled: true`）；參數面板標示「門檻修改 HTTP 未接線」。
- 超限著色：`hot` 用 `compareDecimal(...) === 1` 判斷；比例儀表的 `hot` 等於 `latched`。
- 空狀態（瀏覽器實測，全新資料根）：四個儀表的數值與上限都顯示「不適用」，風控事件為「尚無風控事件」，沒有 `$0.00`、`NaN` 或 `undefined`。
- run 後（整合測試證據 `dom-risk.txt`）顯示：「正常 · 可增倉」、「起算時間 (合成) 11/05 00:00」、「Soft 10.00% / Hard 20.00%」、「觀測 seq 8 · 合成 00:30:00」、四個旗標皆為「是」，風控事件 3 筆（`final_account`、兩次 `day_basis`）。

### 4. 日誌與策略頁：PASS（附觀察 O4）

日誌頁（`pages/logs.tsx`）：
- 篩選邏輯 `matchesFilter`：ALL 全部；TRADE 等於 `category === "ORDER"`；其餘依 `level`。搜尋比對 `title`、`kind`、`category`、`run_id`、`bot_id`，不分大小寫。
- 瀏覽器實測，在全新資料根上跑一次合成 run：

| 操作 | 結果 |
| --- | --- |
| run 期間每秒取樣行數 | 1 → 4 → 7 → 9 → 10 → 11 → 13 → 15 → 16 → 20，即時增加 |
| ALL | 20 / 20，徽章 INFO、TRADE |
| INFO | 20 / 20。成交事件後端等級為 INFO，所以也在內；徽章以 TRADE 疊加顯示 |
| WARN、ERROR | 0 / 20 |
| TRADE | 4 / 20，等於 4 筆成交 |
| 搜尋 `fill`、`BTC-USDT` | 各 4 筆 |
| 搜尋 `RISK` | 3 筆 |
| 搜尋 `sim-control` | 20 筆 |
| 搜尋 `zzz-no-match` | 0 筆，顯示「沒有符合條件的事件」 |

- 後端事件分類（`catos/simulation_catalog.py` `event_level_category`）中，`fill` 一律是 INFO／ORDER，所以 TRADE 徽章不會蓋掉 WARN 或 ERROR。
- `omitted`：只在 `eventsOmitted > 0` 時顯示「後端緩衝已略過 N 筆」（`catStore.ts` 註解 `reported not hidden`）；本輪資料沒有觸發大於 0 的情況。行數標籤的 tooltip 註明前端最多保留 400 筆（`MAX_STORED_EVENTS`）。

策略頁（`pages/strategies.tsx`）：
- 綁定實例依 `strategy_id` 與 `version` 篩選 `bots`。run 權益曲線取 `bound.find(b => b.current_run_id)` 的 run，再用 `StateAdapter.equityCurve(events, runId)` 取該 run 的 `signal.account.equity`。
- 瀏覽器實測顯示「run 權益 · sim-control-sma 8 點 · run 216c424b」，有 1 條面積曲線；綁定實例顯示 `已完成 · run 1 次 · 成交 4 · 權益 $999.91`。
- 空狀態顯示「尚無 run 權益」與「權益 未啟動」。
- 後端 `simulation_catalog.strategy_entry()` 確實提供 DTO 使用的 `name`、`description`、`entry` 欄位。

### 5. 刪除的元件與依賴：PASS

- 刪除 `components/ui/{slider,switch}.tsx`、`hooks/use-live.ts`、`lib/mock/{data,terminal,terminal.test}.ts`，`src` 中無殘留引用（第 1 項的搜尋）。
- `package.json` 移除 `@radix-ui/react-slider` 與 `@radix-ui/react-switch`。lockfile 移除 4 個 `node_modules/` 條目：`@radix-ui/number`、`@radix-ui/react-slider`、`@radix-ui/react-switch`、`@radix-ui/react-use-previous`，後兩個是前兩者專用的傳遞依賴。lockfile 中 `react-slider|react-switch` 剩 0 筆。
- 乾淨 clone 的 `npm ci` 結束碼為 0，`npm ls --depth=0` 結束碼為 0，沒有 missing、extraneous 或 invalid；之後 typecheck、test、build 都通過。

### 6. README 與文件：PASS（附註）

- README「v1 範圍・前端」列與程式一致：戰情台、實例、風控、策略、日誌與側欄讀控制面資料；回測與優化接研究 HTTP；設定頁讀 `/api/workspace/version`（`settings.tsx:42`）；覆盤頁與市場情報頁標示「v1 未啟用」。
- 「v1 不包含」新增覆盤一條，與 `review.tsx` 一致。
- `docs/simulation-api-contract-draft.md` 第 10 節的四頁描述、400 筆上限、刪檔清單與自測項目，都與程式一致。
- `docs/backend-frontend-integration-map.md` 開頭註記把該文件降級為後端契約索引，合理。
- `docs/next-steps.md` 引用的位置都核對過：`catStore.ts:41-48`、`local_sim_control_api.py:118,130,138`、`supervisor.py:108,952,970`、`research_catalog.py:21-22,222`、96 根合成資料（CSV 97 行含表頭）、`tools/fetch_okx_candles.py`、`docs/demo-collection-handoff.md`，全部存在且相符。
  - 小瑕疵：`supervisor.py` 的列舉順序寫成「latch、rearm、set_loss_limits」，對應行號卻是 108、952（`set_loss_limits`）、970（`rearm`），順序對調，不影響理解。
- 附註：第 10 節標題與分支名都叫「全站真資料」，要等 D2 修正後才名實相符。

## 實際執行的命令與結果

`<clone11>` 指 `12fdb09` 的乾淨 clone，`<fe>` 指 `<clone11>/frontend/cat-os-vite`。

| 命令 | 位置 | 結果 |
| --- | --- | --- |
| `git clone -b feat/v1.1-real-data-pages …` | 暫存區 | HEAD `12fdb09` |
| `npm ci --no-audit --no-fund` | `<fe>` | exit 0（只有 allow-scripts 提示） |
| `npm ls --depth=0` | `<fe>` | exit 0，無 missing／extraneous／invalid |
| `npm run typecheck` | `<fe>` | exit 0 |
| `npm test` | `<fe>` | `check:tokens OK`；tests 11、pass 11、fail 0（含 `compareDecimal compares Decimal strings exactly…`） |
| `npm run build` | `<fe>` | exit 0，`✓ built in 10.96s` |
| `node tests/simulation_integration_test.mjs <.venv python>` | `<fe>` | exit 0，9 PASS，含新增的 risk、logs、strategies、review 四項；證據 `%TEMP%\catos-sim-integration-vNod6V`，六個 `dom-*.txt` 中 `NaN|undefined` 皆為 0 筆 |
| `node cmp-check.mjs`（自寫） | `<fe>` | 17 個案例全部符合預期 |
| `ratio_sci.py`（自寫，以整合測試的 `control.json` 重放每筆觀測的期間損益與比例字串） | repo 根目錄 | 9 筆皆為一般小數格式，沒有科學記號 |
| 瀏覽器實測（`serve-check.mjs`，全新資料根，18870／18890） | `<fe>` | 空狀態：風控、日誌、策略、覆盤四頁皆無 NaN／undefined／$0.00；啟動 1 次 run 後行數即時增加、篩選與搜尋結果如第 4 項；覆盤頁連結指向 `#/backtest`、`#/bots`、`#/risk`；主控台 0 個錯誤；結束後兩埠均已釋放 |

## 非阻斷觀察

- **O1（潛在邊界，既有程式）**：後端以 `str(Decimal)` 輸出，絕對值小於 1e-6 的非零值會變成科學記號，例如 `str(pnl / basis_equity)` 可能是 `5.0E-7`。前端 `parse()` 只接受零的科學記號，所以這類值會顯示「不適用」，`compareDecimal` 也回傳 `null`，該儀表不會標紅。本輪固定模板重放 9 筆，最小非零比例為 `-0.0000016203`，沒有觸發。建議後端改用 `format(x, 'f')`，或在前端 `parse()` 支援非零科學記號。
- **O2（風控頁快照時點）**：「風控參數與觀測事實」顯示的是最後一次風控觀測（seq 8，發生在最後一筆平倉成交之前）。run 完成後，風控頁顯示「部位 2 張 / $103.00、帳戶權益 $999.96」，同時實例頁是「FLAT 0」，最終帳戶事件則是 $999.91、部位 0。R1 面板頁尾有標「觀測 seq 8 · 合成 00:30:00」，但事實面板本身沒有。建議面板標題加上「最後風控觀測（seq／合成時間）」。
- **O3（後端投影語義，非本範圍）**：`simulation_catalog.risk_projection` 的 `can_increase` 只看 `mode == RUN`、`health == HEALTHY` 與 `basis` 是否存在，沒有納入 `position_verified` 與 `reduction_conflict`。依 v1 驗收的實測，只有 `position_verified=False` 時 health 仍是 HEALTHY，但 `risk.evaluate` 會拒絕增倉。local-sim 的四個旗標恆為 True，所以實際上不會誤顯示；Demo／Live 前應修正。另外，run 已完成時標頭仍顯示「可增倉」，這反映的是最後的風控狀態，不代表有 run 在跑。
- **O4（策略頁標籤）**：頁首「綁定 Bot {bots.length}」計算的是全部 Bot，不是綁定到登錄策略的 Bot。v1 只有一個 Bot，所以數字相同。
- **O5（已標示的示範內容）**：市場情報頁的展示資料，以及個人化浮窗主題預覽卡的 BTC-PERP 數字，都已標示「v1 未啟用」或「預覽」。開發者預先告知的範圍外項目：`pages/backtest.tsx` 用 `parseFloat` 判斷正負色，`5a101d4` 前就存在。
- **O6（設定頁靜態文字）**：`settings.tsx` 的「有效槓桿上限 3.0x · 單幣預算上限 50%」是寫死的政策說明，不是讀取 `risk.limits`。v1 沒有修改門檻的 HTTP，所以目前一致。

## 未涵蓋

- 沒有在超過一屏的日誌量下實測自動捲動：20 行沒有溢出；只做了程式碼核對，並確認自動捲動開啟時位於底部。
- 沒有觸發 `eventsOmitted > 0`，也沒有觸發 Soft／Hard 鎖存或 WARN／ERROR 事件；這些情況的顯示只做了程式碼核對。
- 沒有重跑後端完整套件：`git diff 845ab14..12fdb09 -- catos tests` 為空，沿用 v1 正式驗收的結果。
- 沒有做整體視覺驗收，由使用者自行在網頁上驗收；也沒有跑 `integration_baseline_test.mjs`。
