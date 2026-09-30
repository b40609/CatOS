# R4 等待期間的前端盤點與操作檢查

2026-09-30：R4 正在跑 8 小時固定合成策略，本文件為唯讀靜態盤點及操作建議，不授權實作下一片。沒有修改 frontend 或 manifest 所列 runtime；不重啟 R4。入口：`http://127.0.0.1:8770/research/`。

使用者後續澄清 Gemini 前端僅作風格／主題／功能參考，要求重審 catOS 專屬前端。本文件保留為技術現況，不能當正式產品導航或版面規格；後續方向見 [產品重新審視討論稿](catos-frontend-product-reassessment-20260930.md)，尚未核准實作。

## 已接線程度

| 頁面／功能 | 現況 | 程式證據 |
| --- | --- | --- |
| 策略中心／回測 | 真實 Decimal 核心、固定 approved artifact／合成資料、API task 與 persisted result | `js/views/strategy.js`、`js/research.js`、`catos/research_api.py` |
| 參數優化／套用候選 | 真實 Optuna 任務；候選套入表單後另建回測 | `js/research.js`、R2/R3 驗收 |
| Dashboard | 原型資料，非 R4 帳戶與成交遙測 | `js/views/dashboard.js` 讀 `CATOS_DATA`；research.js 將其他主頁標為原型 |
| Bot 管理 | 原型；建立 Bot 尚未接線，執行控制 disabled | `js/views/bots.js` |
| Risk | 修改頁面 mock settings；尚未寫入真實 Supervisor | `js/views/risk.js` 的 apply 僅修改 `CATOS_DATA.risk` |
| Logs | 原型日誌；R4 真實證據另存在 events.jsonl | `js/views/logs.js`、R4 runner |
| Yaozi | 此研究前端頁面仍使用 `CATOS_DATA.yaozi`；既有 intelligence API 是另一條只讀能力，尚未接到這個 view | `js/views/yaozi.js`、`catos/market_api.py` |
| Settings／遙測 | 原型情境與外觀；research.js 已標示 MOCK、無交易所連線 | `js/views/settings.js`、`js/research.js` |

本表不把既有情報 API、研究 API 或 R4 CLI 的能力自動算成 Bot／Risk／Logs UI 已接線。其他頁面雖可展示版面，不是 R4 真實監看介面。

## 使用者可立即檢查的流程

1. 在策略中心建立一次合成回測：period=2、quantity=2、warmup=2、initial_balance=1000、fee_rate=0.0005、slippage_bps=2。查看結果／權益／成交／HTML 報告，記錄欄位是否清楚、操作是否順手。
2. 在參數優化選小 budget（例如 3 trials、seed=42），確認可讀候選、套入候選後建立另一筆回測；這只驗操作流程，不評估策略投資價值。
3. 修改回測設定但先不重跑，檢查舊結果是否仍清楚標示原快照；換頁／重新整理後檢查歷史 run 是否仍可找到。把問題以「頁面、操作、預期、實際」四項回報。

上述研究任務只寫隔離 research-web 輸出，與 R4 的合成帳戶／DB／生命週期分開；操作時不改策略 source、manifest 或 R4 listed runtime。長跑期間不要執行會修改 source bytes 的測試或修改固定執行程式。

## 等待期間已完成的工程工作

新增獨立只讀驗收器 `catos/local_sim_r4_verify.py`：以固定 run_id 讀 manifest/status/events 與 read-only WAL snapshot；核對真實時間／900 秒訊號節拍、兩根預熱、完整 journal hashes/checkpoint、逐筆訊號與已提交 receipt、fill/tag/Decimal TEXT／費用、account projection、verified baseline、reservation 與程序收尾。running 回 PENDING，smoke 只回 SMOKE_PASS，只有完整 eight-hour 才可 PASS；不啟停程序、不改 DB。

完成後使用：`python -B -m catos.local_sim_r4_verify 347282b9d0d9433db6a0276209936f60`。驗收工具及專屬 tests 不在運行中 manifest source list，因此本輪修改不影響固定 run。R4 已保存的最終 smoke 可由本工具獨立核對；不能拿 smoke 結果替代 8 小時。

本輪驗收器專屬測試 **9/9 通過**；正式 CLI 重驗已保存最終 smoke 回 `SMOKE_PASS`，費用 `0.00404010`、最終權益 `999.91375990`。2026-09-30 11:13 核對長跑為 `PENDING`，2 根訊號／2 筆成交／0 異常，仍須等待實際 8 小時。

## 後續可討論的最小產品切片

R4 驗收後，真實 local-sim 的只讀狀態與事件仍是產品需求之一，包含 run、心跳、strategy version、signals/fills 和異常；其後才討論受 Supervisor 管理的啟停操作。這是待核准建議，不是已排定功能，也不表示沿用原型 Bot／Logs 版面。導航與呈現應先依專屬產品討論稿重設；Yaozi 依固定來源整合，仍維持情報與交易責任分離。
