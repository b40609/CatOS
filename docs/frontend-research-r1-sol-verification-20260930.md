# R1 Sol 獨立驗收紀錄

日期：2026-09-30。工作目錄：`C:/Users/user/Desktop/CatOS_Astra`。僅合成資料；未讀憑證、未碰 DB/schema、未執行 Demo／Live、未提交或 push。此文件記錄實際驗證，不取代 Astra 的接續入口。

## 已核對

- Git：`main...origin/main [ahead 23]`；原有修改與未追蹤檔案保留，未清理。
- `python -B -m unittest tests.test_research_web tests.test_app_shell tests.test_market_api`：缺 DB 修正後 57/57 通過，包含 API、HTML 報告來源、worker timeout／輸出上限與 allowlisted 環境 mock 契約；未跑整套測試。
- 後加 `python -B -m unittest tests.test_research_web.ResearchServiceTests.test_shutdown_keeps_writer_until_active_result_finishes`：1/1 通過；受控合成 task 確認 close 等待 active 結果完成且 writer 鎖未提前釋放。這是基線 57 加獨立補測 1，並非重跑 58 個測試。
- 最後 `research_catalog` 策略載入職責修正後，只重跑 `python -B -m unittest tests.test_research_web.ResearchCatalogTests tests.test_research_web.ResearchApiTests`：8/8 通過。全新 Python 行程單獨匯入 `catos.research_catalog` 後，`catos.research_strategy` 不在已載入模組中；`RegisteredSMA` 僅由 `execute_request` 計算路徑匯入。未重跑 57 基線或已通過的 shutdown 測試。
- `python -B -m py_compile catos/research_catalog.py catos/research_strategy.py catos/research_worker.py catos/research_service.py catos/research_api.py catos/market_api.py`：exit 0。
- `node --check` 遞迴檢查 `frontend/research/js`：13/13 檔通過。
- `frontend/research/source-manifest.json`：16 筆來源與匯入檔 SHA256 均相符。
- `git diff --check`：exit 0；僅 Git 換行符警告。
- 固定服務 `python -B -m catos.research_api --port 8770` 最終保留：PID `42620`，`127.0.0.1:8770`，build `d938ee544cafd4246d9a6170fbeedb078262d425cc771dd9489de5db3fe90b9b`；`current_build_id` 相同，`restart_required=false`，無 active run。8088／8089 原有程序 PID `19132`／`10752` 未停止。
- 無市場 DB 時 `/intel/today` 實際 HTTP 503，`reason=market_intel_not_found`；研究服務正常啟動。市場 factory 原預設與路由由 `tests.test_market_api`／`tests.test_app_shell` 回歸驗證。
- 真實 Codex in-app browser：選 SMA → 回測 → 完成結果、35 筆模擬成交與 Decimal 字串績效 → 表單張數 2 改 3，原 run 與淨損益 `-0.79532090` 不變 → reload 後相同 run／結果仍在。測試 run_id：`b4384253862942f9bc7ec37f5c13af4c`。
- 真實瀏覽器輸入張數 `abc`，頁面顯示 `quantity: invalid Decimal string`，未新增 run，舊結果仍在。
- 真實瀏覽器暫時攔截 `/api/research/version` 回應：模擬 `restart_required=true` 時顯示手動重啟並停用新回測；模擬服務 build 與頁面不一致時顯示重新整理並停用新回測。已清除攔截並 reload；真實版本一致，按鈕恢復可用。此測試未修改 runtime。瀏覽器 console error／warning 為空。
- 真實 source 變動及手動重啟：Astra 僅在 `frontend/research/css/research.css` 首行加入固定說明 comment，來源 manifest 不變。舊 PID `39340` 的 GET version 由 loaded build `d24bdf...` 對 current build `524fcc...` 回報 `restart_required=true`，`active_run_id=null`；未重整的真實瀏覽器頁面經輪詢顯示「發現程式更新；請手動重啟服務再重新整理」，新回測按鈕停用。合法 `DEFAULT_REQUEST` 搭舊 build POST 回 `409 source_changed_restart_required`，run 數 1 → 1。
- 停止前核對 PID `39340` 的命令為 `python -B -m catos.research_api --port 8770`，且 `127.0.0.1:8770` owner 相同、無 active run。只對原服務 session 送 Ctrl+C；服務完成 shutdown，舊 PID 消失、8770 釋放。以原指令重啟後新 PID `43144`、新 build 與 current 一致。舊分頁未重整即顯示「服務已換版，請重新整理頁面」並停用新回測；重整後舊 run `b4384253862942f9bc7ec37f5c13af4c` 結果仍可讀且按鈕恢復可用。新版本建立合法 run `6e79515ba9e241f4b3b33bfe0f26b6d8`，瀏覽器顯示 complete；API 列表兩筆 complete，各綁各自 build。
- 最後 `research_catalog` runtime 修正使 PID `43144` 回報 loaded build `524fcc...`、current build `d938ee...`、`restart_required=true`。再次核對 8770 owner／命令及 `active_run_id=null`，只停止該服務 session，確認 PID 消失、8770 釋放後以原指令重啟。最終 PID `42620` 的 loaded/current 均為 `d938ee...`。真實舊分頁先顯示「服務已換版」並停用新回測；reload 後兩筆既有 complete 結果仍可讀，按鈕恢復可用；再建合法 run `b0b9e474246644beaab93cedec835b8f` 並在瀏覽器看到 complete。API 列表三筆 complete，各保留其 build；最後瀏覽器 console error／warning 為空。

## 已解除阻斷與未測

初輪 `python -B -m unittest tests.test_research_web tests.test_app_shell` 15 個中 11 通過、4 個 API 測試在 `setUp` 因 `market_intel_not_found` 報錯，8770 啟動亦失敗。Astra 後續加入 optional `market_reader` 及研究入口 unavailable reader，未建立 DB；完整受影響測試與實際啟動均通過，舊阻斷已解除。

未測：自然執行中的任務遇 source 變動，等其結束再人工重啟的完整 UI 時序；本輪實際重啟是在 `active_run_id=null` 後，關閉期間 writer 鎖另以受控合成 task 單測驗證。未做整晚 local-sim、Optuna、MCP、Demo／Live、全市場回測或整套測試；均不屬 R1。
