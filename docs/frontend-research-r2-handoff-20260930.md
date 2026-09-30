# R2 Optuna 正式研究接線

日期：2026-09-30。Astra 編寫；5.6 Sol (Web) 獨立驗收與 Git。本片只接合成資料樣本內參數搜尋，不接交易或樣本外檢驗。

## 操作與契約

固定研究入口仍為 `http://127.0.0.1:8770/research/`。策略中心的「參數優化」設定 SMA 週期搜尋範圍、步長、1–20 次 trial 預算、uint32 seed、固定目標張數、權益、手續費、滑價與預熱；預熱必須覆蓋搜尋上限。後端只接受註冊 SMA／合成 96 根 15m 已收盤 K 線，不接受任意策略、路徑、URL 或其他搜尋維度。目標為最大化 `performance.return_pct`；核心先以 Decimal 算績效，僅 Optuna 排序評分轉 Float。這是同一份合成資料的樣本內搜尋，未執行樣本外檢驗。

`POST /api/research/optimizations` 使用既有同源、版本、內容型別、JSON 重複欄位與 8192 bytes 閘門。與回測共用 `ResearchService` 單 writer、單 active 任務、30 秒及有界 worker 輸出；受信計算程序在 worker 端才載入策略與 Optuna。`GET /api/research/runs` 以 `kind` 區分兩種任務；原 R1 歷史紀錄缺 `kind` 時視為回測。`GET /api/research/runs/{id}/result` 保存候選、完整搜尋設定、來源 hash、Optuna 版本、目標定義、seed 與原始 Decimal 績效；完成結果重啟後可讀。候選「套用並新建回測」以固定優化結果的設定及該候選週期，另送 R1 回測請求，保留兩筆任務各自快照。

首次獨立驗收發現本機 Optuna 所需 `packaging` 只裝於 Python user site，原 worker 的 `-s` 使其不可見；第一次修補亦因 worker 白名單環境缺少 Windows 使用者路徑而無效。現由服務端解析 `packaging` 實際 `__init__.py`，僅在優化分支把該檔路徑傳給 worker 並明確載入該套件，保留 `-s`、不把整個 user site 加入模組搜尋路徑；若本機缺此依賴則任務明確失敗。另一修正將候選 payload 在回傳前正規化，直接呼叫與 HTTP 路徑皆保證 Decimal 字串。

輸出仍為 `outputs/research-web/<run_id>/`，不碰 DB/schema。`RUNTIME_FILES` 及來源 hash 納入優化模組；R2 更新觸發 R1 既有版本警示與新任務阻擋。既有任務完成後由使用者手動停止原服務、同指令重啟並重整；8770 占用時報錯，不切換埠、不終止未知程序。原 root、Yaozi 與 8088／8089 不改。

## 驗證狀態與後續

專屬測試 `tests/test_research_optimization_web.py` 涵蓋 Decimal 候選對直接回測一致、輸入拒絕、來源變更、保存／重啟、共用任務槽與 API 閘門。5.6 Sol (Web) 首輪 27/30，修正 Decimal 字串後 28/30，再修正 Windows worker 套件路徑後執行 `python -B -m unittest tests.test_research_optimization_web tests.test_research_web tests.test_optimization`，**30/30 通過**；`node --check frontend/research/js/research.js` 與 `git diff --check` exit 0。這些是實際本輪證據，不等於整套測試。

後續已完成固定 8770 的人工重啟與實際瀏覽器驗證：舊 PID 42620 已退出；目前 PID 16560 使用原命令，loaded／current build 均為 `f704b0c23cc9aea1ed434498b2f5165c1b30176e73050a0668816e0250fe85f9`，`restart_required=false`、`active_run_id=null`。`/research/` 回 200／`no-store`，瀏覽器顯示 R2 參數優化設定、完成紀錄、候選表及「套用並新建回測」。另以正式 HTTP 路徑執行 1-trial Optuna 任務 `7f10f5db3b674a61aa849e3f1622b165`，`complete`、`kind=optimization`、`return_pct=-0.0990901400`，保存結果已由 UI 讀回。仍未執行全市場、整晚 local-sim 或 Demo／Live；未 commit／push。下一片依序 R3 MCP，再 R4 整晚 local-sim；各自需獨立驗收。
