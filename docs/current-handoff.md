# CatOS 目前接續入口

更新：2026-09-30（F1 實作 Git 收尾）。工作目錄 `C:/Users/user/Desktop/CatOS_Astra`。**使用者已授權「F1 Git 收尾 → 等 R4 PASS 並收尾」；F1 以獨立實作提交保存，5.6 Sol (Web) 驗收對話仍在補 #6，尚無正式 PASS。** 本輪不增加瀏覽器測試；R4 八小時長跑仍運行中。Git 基線已核對為 `7c346f2`，F1 與 R4 分開、不 push、不切正式 8770。

## F1 六頁工作台

[首頁](http://127.0.0.1:8771/workspace/home)／[策略中心](http://127.0.0.1:8771/workspace/research)。機器人管理、風控、日誌、情報與設定共用 Gemini 黑金、密度、導航與布局操作；來源／版本／驗收進詳情，缺資料短標示。新增 `desk.html/css/js`，更新首頁導航、workspace API 固定路由／資產 hash、tests 與文件；Gemini 原目錄及 CatOS_Yaozi 未修改。舊 F1／design 保留。

策略中心經原 8770 單一 ResearchService 提交合成回測／搜尋，草稿與結果分離，候選僅帶入新草稿。其餘頁讀既有 R4 證據／缺口／本機偏好；沒有 Bot 啟停、交易、風控 mutation 或第二 writer。固定 R4 狀態與選定歷史記錄分離，避免切 smoke 誤顯示長跑完成。金額維持 Decimal 字串。

實際自驗：`test_workspace_f1` **22/22**、desk／home／home-layout 三支 JS 語法通過；真實 UI 合成回測 `6a7956b291bf4205b2d8293ef9963b02`、3 次搜尋 `9076af29fda2417f92015bb946486bc1` 均 complete。已操作候選草稿、R4／smoke 切換、事件篩選／詳情、偏好 reload、隱藏／加回／放大／Escape；不是全站 E2E 或獨立驗收。完整報告連結及剩餘版面互動交由人工驗收；窄視窗只做有限檢查，不宣稱六頁完整響應式驗收。詳見 [交接與人工清單](catos-workspace-f1-handoff-20260930.md)／[規格](catos-workspace-f1-spec-20260930.md)／[設計決策](catos-frontend-design-feedback-20260930.md)。

8771 preview 前輪 PID `5512`，只有預覽轉交、無 writer；前輪最後載入版本無需重啟。原 8770 未重啟，前輪 GET build=`72734a4e3b7d06215a68ea9c5c52af3e898b8fafbee921bc2c87e68deeeff5e5`，instance=`f2a3c7d3b3544eeaa2aa42eb8a45d71b`；正式啟動器尚未切換。預覽命令 `python -B -m catos.workspace_api --preview`；log／截圖在 `outputs/frontend-design-review-20260930/`。F1 提交僅 workspace API／snapshot、frontend/workspace、專屬 tests、四份 F1 文件與本入口；outputs／研究 runs／DB 不 stage，R4 保留未提交。Gemini 布局引擎的 8 處原有行尾空白保留；本輪未重跑 tests 或修改程式 bytes。

獨立驗收對話：[依 F1 清單驗收並保留 R4](codex://threads/01a0f18e-ff90-7751-8624-15b9fde8f4dd)。18:07 核對仍 active，最後處理窄版成交表水平自捲；來源是該對話工具／進度，不能改寫為完整驗收通過。本次提交是實作保存，不是獨立驗收封存。比較圖片／design 樣稿仍屬本機 outputs，乾淨 checkout 缺檔時回 404，不納入 Git。

## R4 保留與收尾

唯一 run=`347282b9d0d9433db6a0276209936f60` 已正式 **PASS**。2026-09-30 20:23 台灣時間執行 `python -B -m catos.local_sim_r4_verify 347282b9d0d9433db6a0276209936f60`，回 profile=`eight-hour`、elapsed=`28800.073241599952` 秒、32 根正式＋2 根預熱、13 fills、0 anomalies、final_equity=`999.67939950`、fees=`0.01320050`、database_mode=`read-only`、runtime_digest_unchanged=`true`。未改 DB、未啟第二 runner。

SMA period=2／quantity=2；固定 runtime SHA=`ec21bab7a7f26436bc75f6f48ea843f82dfcf62e1dbf65b5c507a44616db9e65`，manifest 程式維持凍結。前輪 R4／verifier 9/9、IPC 11/11、Worker 15/15 與 smoke `d8fdd571ef554c8681e2316edd22bbe9` 的 SMOKE_PASS 是歷史證據。詳見 [R4 spec](frontend-research-r4-spec-20260930.md)／[handoff](frontend-research-r4-handoff-20260930.md)。

既有 heartbeat `r4-8-local-sim` 原為每小時唯讀追蹤、最多 9 次；R4 已正式 PASS。本輪嘗試以原完整設定改為 `PAUSED`，automation 後端回報該項目已不存在，故目前沒有可再停用的 active heartbeat。驗收器已核對 >=28800 秒、32+2 根、成交／費用／tag／Decimal／journal、0 異常、無未決與 Worker 收尾。不刪證據、不改 DB、不解除 latch。R4 提交範圍及輸出規則見原交接，F1 不混入。

## R3 基線與下一步

R3 已驗收：固定核可 SMA／合成資料、七 MCP 工具 exact binding、原 8770 唯一服務；36/36 與 MCP E2E 是歷史驗證。詳見 [R3 handoff](frontend-research-r3-handoff-20260930.md)／[6.1 Sol 補驗](frontend-research-r3-sol61-verification-20260930.md)。Antigravity BOM／DSH credential 限制仍保留。

R4 收尾完成後，下一片為正式 8770 工作台入口切換；需先確認研究 idle 與單一 writer，再依既有授權進行。R4 不需重跑；F1 亦不需重複驗收。`AGENTS.md`／`.codex` 設定與本片無關，保持未混入；本輪不 push、不切 8770、不啟新 runner。
