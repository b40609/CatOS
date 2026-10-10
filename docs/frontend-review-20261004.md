# 新前端第一版審查（2026-10-04）

結論：Vue 3／TypeScript／Vite 的基本拆分可沿用；型別檢查與建置通過，功能交驗未通過，尚不可正式接入。本輪為 Codex 開發審查，不是 WorkBuddy 獨驗。未修改回傳功能來源、未接核心、未執行 Git。

## 來源與證據

- 輸入：`C:/Users/user/我的雲端硬碟/catos-frontend-redesign-v1.zip`。
- ZIP SHA-256：`4EE07BB80ECA1F172C04A28BC17FAB0321ED9A0E0D82B0887A0C4155043CC897`。
- 獨立副本：`outputs/frontend-review-20261004-4ee07bb8/source/`；原 ZIP 與既有前端未覆蓋。
- [49 檔來源及本輪 build hashes](../outputs/frontend-review-20261004-4ee07bb8/hashes.json)、[owner](../outputs/frontend-review-20261004-4ee07bb8/fixture-owner.json)、[退出證據](../outputs/frontend-review-20261004-4ee07bb8/shutdown.txt)。
- [互動紀錄](../outputs/frontend-review-20261004-4ee07bb8/interaction-log.md)、[刷新前日誌](../outputs/frontend-review-20261004-4ee07bb8/commands-before-refresh.txt)、[刷新後](../outputs/frontend-review-20261004-4ee07bb8/commands-after-refresh.txt)、[停止未更新](../outputs/frontend-review-20261004-4ee07bb8/stop-unchanged.txt)、[匯入無反應](../outputs/frontend-review-20261004-4ee07bb8/import-no-action.txt)、[503 狀態](../outputs/frontend-review-20261004-4ee07bb8/unavailable.txt)。
- 畫面：同目錄 `commands.png`、`bots-stop-unchanged.png`、`dashboard-unavailable-1440.png`、`dashboard-b-1280.png`、`dashboard-768.png`。僅抽查布局，未宣稱所有尺寸與頁面通過。

## 必修缺陷與重验入口

1. **P1：Mock 命令回成功卻不改狀態。** `src/adapters/mock-adapter.ts` 的 createStrategy／allocateBot／startBot／stopBot 未更新版本、Bot、run 儲存；fetch 仍回固定 fixture。真實 UI：啟動 SOL 後仍已停止；建立 `review-new-bot` 顯示成功但仍原 3 Bot；停止 BTC 後仍運行中。修正為具狀態的隔離 Mock，讓頁面可讀到命令效果、持倉停止與歷史；不要假稱 Python Worker 已執行。重驗：匯入→分配→啟動→停止→換頁→刷新→歷史。
2. **P1：離線仍顯示正常。** `useWorkspace.ts` 遙測硬編碼 connected=true／PID 4821／16ms，未使用 fetchTelemetry；`useDashboard.ts` 失敗保留舊資料，布局 A/B 不呈現 error。真實 UI 選 503 後仍連線正常、NORMAL、舊 KPI；改布局 B 後反而顯示 0 Bot、正常說明與 SOFT LATCHED 混合。修正失敗／未知／最後快照標示，禁止未知轉零或正常，禁止未完成讀取卻宣告安全。重驗 A/B 的 normal→503→恢復與首次離線載入。
3. **P1：分配快照不對。** `mock-adapter.ts:221` 固定 `mockStrategies[0].artifact`，即使 payload 選其他 hash；`BotsPage.vue:47` 固定 `{period:'15m'}`，忽略所選預設參數。參數型別僅 flat string/number/bool，未完整表達既有有界 JSON；小數應為 Decimal 字串。修正 hash→對應製品、完整預設／可審閱參數與冻结快照；選版後不影響舊 Bot。重驗第二策略的 hash/source/defaults/parameters 一致。
4. **P1：命令契約及重送不完整。** 每次點擊新 request ID；沒有原 body、build、instance 綁定與 pending／uncertain 還原／人工重試。`BotsPage.vue:78` 缺 run ID 使用虛構 `run-default`。移除虛構 ID、停止前確認真實 run；重試原命令保留 ID/body/build/instance，遇不確定先查詢，不能另發新命令。重驗回覆遺失、重複提交、同 ID 不同 body、刷新與版本／instance 錯配。
5. **P1：交接把 view model 當原 API。** HANDOFF 聲稱契約嚴格對齊、只換 activeAdapter 即完成接線，但 GET `/api/workspace/simulation` 不存在；正式讀取為 `/version`、`/runs`、`/runs/{id}`、`/strategies`、`/bots`。runs 是含 items/state/issues 的 wrapper；Bot metadata 無 runtime state，需與 run 合併；成果不能假定 flattened equity_usdt 等即原回覆。正式命令須 X-CatOS-Build／X-CatOS-Instance，allocate body 需 mode，策略建立 body 是 request_id＋manifest。分開 raw DTO 與展示 view model，由 adapter 映射；頁面不得直接綁 concrete Mock。以目前 `catos/local_sim_control_api.py`、`local_sim_control.py`、`strategy_library.py` 與既有功能前端為接線依据，不新增後端或 schema 遷就 mock。
6. **P2：匯入與歷史缺入口。** StrategiesPage 匯入按鈕無 handler，真實點擊沒有檔案選擇；AST 通過 badge 無驗證依據且固定顯示。Bot 流程未提供成果歷史讀取／還原。補可互動匯入／錯誤狀態／版本不可變呈現與歷史入口；原型只標示示意驗證，未接後端不得稱 AST 通過。
7. **P2：信任綁定容易沿用。** 對話框初始未預勾已實測；但取消／重開或切換策略不清除 isTrusted，也沒有在分配表單檢查所選 source／defaults。每次開啟及選版需清除信任，顯示所選版本與參數後人工確認。重驗勾選→取消→重開、勾選→切換策略。
8. **P2：產品狀態與資產不符方向。** Demo/Live disabled，無法完成工作區切換與隔離展示，且選擇器未放 LOGO 旁。研究／優化示意卻呈現已完成，曝險有已取消的風控緩衝預留；應明確開發中，保留入口。base.css 載入 Google Fonts，跨機／離線可能不同；改本機資產或系統字體。Mock 虛構 PID、行情、回測數值只作示意，不能稱本機實際服務資料。

## 實際檢查

在 source 副本執行（本輪未重跑核心歷史測試）：

```text
npm.cmd ci --ignore-scripts --no-audit --no-fund
node.exe node_modules/vue-tsc/bin/vue-tsc.js --noEmit
node.exe node_modules/vite/bin/vite.js build --outDir ../rebuilt-dist --emptyOutDir false
node.exe node_modules/vite/bin/vite.js preview --outDir ../rebuilt-dist --host 127.0.0.1 --port 61943 --strictPort
```

安裝 exit 0（79 套件）；typecheck exit 0；build exit 0（Vite 6.4.3，89 modules）。[型別日誌](../outputs/frontend-review-20261004-4ee07bb8/typecheck.log)、[建置日誌](../outputs/frontend-review-20261004-4ee07bb8/build.log)。建置另存 rebuilt-dist，未覆寫交付 dist。

啟動前確認 61943 無 listener；本輪 Vite owner 44212／parent 51924，creation time 與 command line 已保存。審查 fixture 標識 `review-20261004-4ee07bb8-61943`，僅為審查識別，**不是後端 instance**；build 以 hashes.json 的產物 SHA-256 為準。沒有 Python 服務、Worker 或 DB。CUA 實際互動覆蓋信任提交、分配、啟動、停止、換頁、刷新、匯入點擊、503、布局 B；Demo/Live disabled 未完成模式切換、缺歷史入口未完成歷史還原。Ctrl+C 控制本輪 owner 收尾，程序 exit 1、埠關閉；不冒稱正常 exit 0。

ZIP 原 scripts/verify-ui.js 多為導航／截图，只開分配表單未提交，部分 selector 缺失會跳過；未覆蓋匯入、啟停、歷史、重送。其 SUCCESS 與零 console error 不能當功能驗收。交付既有 screenshots 是外部材料，本輪不背書其來源。

## Antigravity 與 WorkBuddy 下一步

Antigravity 可繼續視覺微調，先修上述狀態／契約，再回傳第二版完整新前端來源、lockfile、變更清單與原始互動紀錄；不要改核心或既有工作前端。无需重做 Vue 架構；不要用成功 toast 取代狀態轉換。修正交接中過度保證。

Codex 收第二版後依新 hashes 重驗受影響部分，之後才正式接線到全新隔離 Python fixture，核對真正 Worker 執行、持倉停止、歷史、MCP。WorkBuddy 按本報告原始證據與修復差異獨驗；未整合前無正式前端 PASS。無 commit/push 授權。
