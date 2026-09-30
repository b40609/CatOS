# R4 固定策略 8 小時 local-sim

2026-09-30：使用者核准啟動 R4，並選擇「短程驗證通過後立即連續跑 8 小時」。6.1 Sol 執行實作、驗證與交接；基線 `7c346f2`／runtime `87d60be`。R3 完成不代表本片已通過。

## 範圍與最小做法

具體缺口：研究 Worker 能執行 approved snapshot，但既有 COMMIT/ACK Worker 只載入舊 SMA；沒有以真實時間持續執行與保存訊號／模擬成交／異常的 R4 runner。

選用唯一已核可 `sma-trend / sma-parameters-v1`、reviewed digest `3b411bb170572445bc8d4a28c5647387ed08cc3846b03c0c0b36949052f92cf2`。固定研究預設 period=2、quantity=2、warmup=2、BTC-USDT-SWAP 15m、1000 USDT 合成初始資金、fee_rate=0.0005、slippage_bps=2、明示零 funding；不將 Optuna period=4 候選自動當作新設定。

WorkerConfig 僅新增可選固定 `strategy_artifact=sma-parameters-v1`；未指定時保持舊 wire 契約。Worker 透過 R3 snapshot loader 建立固定參數策略，沿用兩根 checkpoint、JSON IPC、COMMIT/ACK 與既有 WorkerHost；不接受任意模組／參數。不在 Supervisor 載入策略。

runner 只使用既有 LocalSupervisor、risk.Limits、FakeExchange 與單 writer SQLite。每次建立全新隔離目錄／合成 account／DB，以 require_new_database=True 拒絕沿用舊 DB，不修改 schema，不碰既有資料庫。SQLite execution_fills 為成交唯一持久來源；帳戶視圖由這些 rows 重播既有研究 Decimal 記帳核心作唯讀投影，不建立第二帳本。

## 時序與證據

固定已收盤合成 fixture 的 15m OHLC；synthetic clock 與實際牆鐘分開保存。兩根預熱立即載入，此後 32 根每 900 秒處理一次，連續真實 28,800 秒；不將快速重播稱為整晚。短程 smoke 為 8 根每 1 秒，涵蓋 synthetic 午夜。合成時間從當日台北 22:00 起算，與實際啟動時間無市場對應。

本根收盤決策、下一根開盤加明示 tick/slippage 成交，下一根 open 位於同一收盤邊界；Worker 只收到當根 Closed Bar。FakeExchange 僅排入明確完整成交證據，由 Supervisor 注入固定 tag／cross／net。逐筆核對 FILLED、完整費用、對帳、reservation 釋放；UNKNOWN、缺成交、risk halt 或程序故障立即記異常並停止，保留 DB 責任，不自動重送／re-arm／清倉／清理。

初始 synthetic 日初權益採帳戶自午夜起無活動的 1000 USDT fixture；跨日時在 synthetic 午夜、當根決策與成交前記錄 Decimal 權益，經既有 verified baseline 契約與同 writer 保存。沒有 Demo／Live 帳務／重建政策變更。

輸出 manifest.json、events.jsonl、status.json、state.sqlite3，含 source/runtime digest、設定、PID、實際／合成起訖、訊號、裁決、mock request／fill、風控與心跳。每秒檢查手動 stop.request；至多每 30 秒核對 worker／source 與更新心跳。心跳間隔超過 120 秒記 continuity failure，停止新增工作，不宣稱連續成功。程序結束保留所有證據，不新增 Windows service 或常駐自動重啟機制。

## 驗收

專屬測試涵蓋固定 artifact 拒絕／checkpoint 綁定、真正 Worker／Supervisor／FakeExchange smoke、Decimal 投影與已保存成交一致、synthetic 切日、手動停止、source drift／缺 script／continuity 異常；重跑受影響 IPC／Worker 必要測試。short smoke 通過後啟動一次 8 小時背景程序。

8 小時驗收必須等程序完成後核對實際起訖、32 根正式訊號、兩根無意圖預熱、成交／tag／費用與 journal 一致、0 anomalies、Worker 已收尾。running／failed／stopped 不能標 PASS；驗收後才提交本片。不得自動擴展 Demo／Live、交易所資料採集、全市場回測、R5 或 push。
