# R1 正式研究回測接線

日期：2026-09-30。Astra 編寫；Sol 獨立驗收與 Git。本片接研究回測，不接交易。

## 交付範圍

同源入口 `http://127.0.0.1:8770/research/`。沿用外部原型主側欄、配色、布局引擎及其他主頁；策略中心改為受信 SMA 版本，操作為：選策略 → 選合成資料與完整設定 → 真實回測 → 查看績效／權益／回撤／模擬成交 → 重整讀回保存結果。正式研究入口尚未取代 `/`、`/app/...`、`/dashboard` 與其他 Yaozi API。

靜態審查補正：既有 `market_api.create_app()` 立即驗證情報 DB，會讓純研究因缺 DB 而無法啟動。factory 僅加可選 `market_reader` 注入，原預設行為維持；研究 adapter 提供正常唯讀 reader，或缺失／不可用時明示 503 的 reader。保留全部原路由，不自動建立／遷移 DB。Sol 必要回歸包含 market API；這項補正取代先前「市場 API 檔案未改」說法，交易核心未改。

`frontend/research/source-manifest.json` 逐檔列出 16 份外部原型資源的來源 SHA256 與帶入 SHA256。來源目錄未修改，不執行期跨桌面目錄 import。`state.js` 僅改為隔離 localStorage namespace；其他帶入檔案僅正規化換行。策略 view、boot、index 與 research CSS 為本片新檔案；排除不用的 GridStack JS 與 mock 策略 view，不刪來源檔案。保留 Workspace 程式及 CSS，沒有重做外部原型布局收尾。

## 實作契約

- `catos/research_catalog.py`：固定策略／資料 ID、請求驗證、來源 hash、共用核心執行與 Decimal serializer。註冊 `sma-trend / sma-parameters-v1`，以 `research_strategy.RegisteredSMA` 沿用既有 `SMATrend` 的 Long / Flat 規則，明示可設定 period 與目標張數；預設 period 2、quantity 2 保持原示例規則。
- 資料 `examples/research-web-synthetic.csv`：固定 96 根 15m 合成已收盤 K 線，價格 98–105 USDT 僅為算術 fixture；不能視為真實 BTC 市場。合約 fixture 為 BTC-USDT-SWAP，每張 0.01 BTC、tick 0.01、lot／min 1 張，資金費事件明示為空。
- 重用 `data_io.load_candles_csv`、`research.backtest` 與 `reporting.render_report`。核心／既有策略示例未改。金額、費率、滑價與目標張數均要求 JSON 字串，期間／預熱為 JSON integer；拒絕 float、bool、非有限值、額外欄位、任意 Python、路徑與 URL。
- `ResearchService` 獨占隔離研究輸出 writer；普通獨立受信 Python 程序使用 JSON stdin/stdout 計算，不提供 DB writer、交易 client、簽名器或憑證，環境只允許 SystemRoot／WINDIR。這是受信程序隔離，不宣稱 OS 安全沙箱。service 寫結果，計算程序不寫檔、不連網。
- queued／running／complete／failed 由後端保存。一個 active 任務，無擴充任務佇列；執行中另送請求回 409。關閉頁面不終止任務；正常停止服務等待有界任務結束；意外停止後，下次啟動將未完成任務標 failed／interrupted，不自動重跑。
- `outputs/research-web/<run_id>/` 保存 request.json、status.json、result.json、report.html。run_id 為後端 UUID hex，只有固定 ID 可讀；每筆新建目錄與 exclusive 新結果，禁止覆寫既有結果。status 由同 writer 原子 replace。完整結果／設定／策略版本／策略及資料 hash／核心 hash 固定綁定，重啟可讀。
- 前端只在 SVG 座標轉成 Number；原始績效、成交與回撤仍顯示後端 Decimal 字串。績效保留未實現損益、手續費、資金費、末筆未成交意圖、核心模型假設。成交筆數明示為 fills，不稱勝率／完整交易。
- 其他主頁均標示原型示意，側欄移除假連線與遙測數值的真實感；策略的參數優化子頁明示 R2 未接線。原型頁本身不構成帳戶狀態、風控變更或 Bot 啟動授權。

## 最小 API

| 方法／路徑 | 用途 |
| --- | --- |
| GET `/api/research/catalog` | 受信策略、固定資料、預設與上限 |
| POST `/api/research/backtests` | 建立固定請求；回 202 與 run_id |
| GET `/api/research/runs` | 保存任務紀錄 |
| GET `/api/research/runs/{run_id}` | 狀態與錯誤原因 |
| GET `/api/research/runs/{run_id}/result` | complete 固定 JSON |
| GET `/api/research/runs/{run_id}/report` | complete HTML 報告 |
| GET `/api/research/version` | build／實例／PID／路徑／是否需重啟 |

提交須 application/json、同源 Origin（CLI 無 Origin 仍須版本 header）、`X-CatOS-Build` 與啟動版本一致。研究路徑要求 Host 為 127.0.0.1，並停用 HTTP 快取；服務只 bind 127.0.0.1。不把這些限制宣稱為防禦使用者本機惡意程序。

資源上限：單請求 8192 bytes；最多 512 bars（目前固定 96）；period 2–32；warmup >= period 且 <64；quantity 1–1000 整數張；初始權益 >0 且 <=1000000000 USDT；fee_rate 0–0.01 比例；slippage_bps 0–100；計算 30 秒；stdout 2000000 bytes／stderr 65536 bytes；最多 200 runs。達筆數上限報錯，不自動刪除使用者結果。這些是本機研究資源限額，不是帳戶風控政策。

## 避免舊版誤驗（使用者已選定）

本次查到 8088 被既有 Python 占用、8089 為外部靜態原型；不能據此斷言所有舊版問題均由快取造成。正式研究入口固定 8770，舊 8088／8089 不再作研究驗收入口；未終止其既有程序。

1. 固定啟動 `scripts/start-research.ps1`，或在 Astra 根目錄 `python -B -m catos.research_api --port 8770`。launcher 明示 workspace 與入口，socket 已占用即報錯，不自動換埠、不猜測／終止占用者。不要同時開靜態伺服器驗收研究功能。
2. index 的資源版本參數自動使用來源內容 SHA256；研究 HTML／assets／API 回應 `Cache-Control: no-store`，不依賴 HTML meta 或手動更新 v13。
3. 畫面底部每 5 秒顯示服務 build、PID、實例；hover 可查啟動時間與根目錄。新資料不等於新程式，版本欄才是判斷服務來源的依據。
4. 原始碼／前端檔案更新時顯示「等待任務結束後手動重啟」。後端阻擋新回測；既有任務與完成結果仍可查看。使用者已選手動重啟，不採 auto reload／自動重啟。完成修改後：等待 active 任務結束 → 原啟動終端 Ctrl+C → 同一指令重開 → 瀏覽器重整 → 確認版本欄一致。
5. 若服務已換版但舊分頁還在，顯示重新整理提示，舊 build 的送出仍會被後端拒絕。`/` 與外部原型是舊展示入口，本片保持不變，不能當成 R1 驗收位置。

不添加另一個常駐管理服務，不自動停止 Python／Node 所有程序，不關閉交易生命週期。未納入瀏覽器 Service Worker 管理；目前帶入資源沒有註冊 Service Worker。

## 驗收與下一片

`tests/test_research_web.py` 包含直接核心一致性、原示例規則一致性、Decimal 及非法輸入、來源變動拒絕、持久化重啟與不覆寫、單 writer／busy／failed、中斷不恢復、ID 路徑拒絕、timeout／輸出上限／不繼承憑證環境、關閉時等待結果完成才釋放 writer、HTML 來源綁定、API／原 root／Yaozi 保留、缺情報 DB 明示不可用且不建 DB、版本／Origin／Host／重複 JSON／大小上限／埠占用。Astra 編寫時未執行驗證；實際驗證以 [Sol 證據](frontend-research-r1-sol-verification-20260930.md) 為準。

本片已通過 Sol：基線 57/57、新增關閉契約 1/1、最後策略延後載入修正後 Catalog／API 8/8。策略模組僅於 execute_request 計算路徑載入，web／writer 列 registry 或驗證請求不載入策略。6 個 Python 模組編譯、13 個 JS 語法、16 筆 manifest hash 及 diff check 通過；不代表整套測試。

真實瀏覽器已確認成功回測、固定結果、非法設定與 reload 保存；真實 CSS 更新造成 restart_required、停用新回測與舊 build POST 409，沒有新增 run。確認 active 空及 ownership 後 Sol 人工重啟兩次，最終 PID 42620，8770 loaded/current build 一致。舊分頁提示 reload；重整後舊結果可讀、新回測完成、三筆 run 皆 complete，console error／warning 空。自然 running 遇更新再等結束手動重啟的完整 UI 時序仍未實測，關閉等待與 writer 鎖由受控單測驗證。最終交付後只改入口／README／本交接文字，未重跑 Git 檢查。

Sol 另驗真實瀏覽器成功流程、非法設定錯誤、reload 保存、表單變更不動完成結果、瀏覽器 console；模擬 DOM 不是瀏覽器證據。Git 工作僅核對／檢查，沒有 commit／push 授權。既有其他未提交內容不混入。

下一片依順序 R2 Optuna → R3 MCP 同 service 及固定受信製品 → R4 整晚 local-sim。新策略製品、客戶端相容性及整晚證據各自有驗收，不由 R1 成功自動成立；Demo／Live 與 DB/schema 授權不變。
