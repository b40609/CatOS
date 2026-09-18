# catOS 階段與分工規劃

## 2026-09-18：S4 已編寫，待 Sol 質檢

依使用者「同意刪除並執行」，刪除已確認舊草稿，保留正式 [S4 規格](outputs/catos-s4-exposure-spec.md)。新增 `catos/lot_exposure.py` 及36個 E01–E36測試方法；純Decimal觀測、資料品質降級與在途身份核對，不修改Schema／risk.evaluate／3x與50%／P6／交易路徑。Astra只做補丁與靜態核對，未執行測試、編譯或Git。Sol驗證範圍見 [S4交接](docs/lot-exposure-handoff.md)。

## 2026-09-17：S4 觀測契約與驗收規格已交付

依使用者「同意 執行」完成 [S4 曝險觀測規格](outputs/catos-s4-exposure-spec.md)：單帳戶／單合約、純Decimal Gross/Net與實體淨量差異、來源完整性／共同截點／新鮮度、held與exchange共同責任身份、UNKNOWN可空數量，以及36個驗收情境群。此輪只交付已提出的下一項設計文件，不編寫業務程式、不改Schema／風控門檻、不執行測試或Git。後續實作限觀測範圍；Gross限額與交易接線仍不在授權範圍。

## 2026-09-17：S3 已驗收，後續評估 S4 曝險觀測

依使用者提供的 Sol 報告：commit `604e983fdaef3bfaeade8648e67679a678149c17`，S3 53/53、必要回歸190/190，本輪實際243/243 OK；Windows中斷4/4、0 skip。Python3.14.6／SQLite3.50.4；diff/staged檢查通過，提交後 working tree clean、main ahead3、未 push。未執行全量測試，不推算全量通過數。本段文件更新發生於該提交之後，未重新查 Git 或執行測試。

主動評估結果：下一片建議 S4「純資料 Gross／淨曝險觀測與差異報告」。既有 risk.Snapshot 已區分交易所在途與本地 held intents，risk.evaluate 不抵銷相反在途委託；但未有完整 Lot 視圖／同截點實體部位的對照契約。先設計帳戶／合約／截點與完整性、mark新鮮度、Lot Gross與Net、實體Net差異及在途來源去重；未知數量不得當0，CLOSE不得預扣已持有曝險。S4先不修改風控裁決、3x／50%門檻、Schema或交易路徑。虛擬Gross是否成為新限額屬另需定案的政策，不能直接套用既有實體曝險預算。尚未開始S4程式實作。

## 2026-09-17：S3 序列化阻斷修正，待 Sol 重驗

首次驗收由使用者回報：純帳務 11/11 OK，儲存 35 errors、程序 4 errors，停止 Commit。依確認方案將 `_key()`／`_write_id()` 的雜湊輸入由 list 改成具名 object；不放寬 S2／IPC 契約、不改 Schema。新增三個回歸方法，目前 S3 共 53 個方法待重新驗證。Astra 僅補丁與靜態核對，未執行測試、編譯或 Git。詳見 [S3 交接](docs/lot-fill-handoff.md)。

## 最新：S3 已編寫，待 Sol 質檢

使用者在 S3 規格交付後明確要求「執行」，已完成純帳務 reducer、schema7 三張事件表、同交易 S2 版本更新、受管 Lot 寫入閘門、重啟帳務重算及專屬測試編寫。詳見 [S3 開發交接](docs/lot-fill-handoff.md)。本輪未執行測試、編譯、Git 或既有 DB 遷移；下方「S3 待審查」為先前歷史。

## 最新：S2 已驗收；S3 規格待審查

使用者回報 Sol 已完成 S2 質檢與提交：`690d8549dd4d078d5e62a12acf536ba0f768bdcb`，447/447 OK、0 failure/error/skip，含 Windows 程序中斷 4/4；Python 3.14.6、SQLite 3.50.4。當時 working tree clean、main ahead 2，未 push；以下舊交接狀態保留為歷史，本輪未重新核對 Git。

已交付 [S3 合成成交歸屬與帳務規格](outputs/catos-s3-fill-accounting-spec.md)，待審查帳務政策後實作。本輪僅文件，未執行測試、編譯、Git 或資料庫遷移。

依使用者新指示：每次驗收回報後主動評估並提出下一片，不等待「下一步」提示；新帳務／交易政策仍明列審查，不自行擴大實作範圍，不建立背景排程。

## S2：設計已核准，開發交接待 Sol 驗證

使用者確認 [S2 規格](outputs/catos-s2-lot-journal-spec.md) 後，已編寫 `catos/lot_journal.py` 與 Journal schema 6 接點；新增三張 STRICT Lot 表、同 writer 原子快照／收據、版本與寫入去重、重啟重放及完整性拒絕。新增 34 個儲存測試方法與 4 個 Windows 程序中斷方法，並調整 schema 1／2／3／4 的既有測試夾具。詳見 [交接文件](docs/lot-journal-handoff.md)。

本輪僅靜態閱讀核對，未執行測試、編譯、Git、既有資料庫遷移、憑證讀取或 OKX 請求。S1 的 `720c632`／409 項通過為使用者回報基線，不能轉作 S2 驗收。後續由 Sol 檢查與執行測試；不自動進入成交分配或交易接線。

## 2026-09-15：已知問題修補開發交接（尚未執行驗證）

本輪依「修正所有已知問題」修改額外 CLI 輸出保護與明示合約規格、Optuna study Decimal 夏普及週期口徑、模式查詢測試契約、同身份多內容版本來源歸併、頁號／游標／完成證據校驗、餘額固定欄位診斷與安全摘要、普通合法減倉及 P6 未決責任的人工恢復門控。同步 README、AGENTS 與交接文件，舊 I-b-4 單次授權標為歷史已結束。

新增及擴充合成回歸測試，只做靜態閱讀核對；未執行測試、編譯、Git、市場回測、憑證讀取、帳戶採集或交易。歷史通過數字不能轉用為本輪驗收。驗證模型應依本輪交付清單執行受影響模組，不自動跑全市場或重新採集。真實餘額／模式差異因原始報告未保留仍無法確診；歸因、P6、日初基準等對帳工作不是靠放寬 gate 消除，J／Live 仍未啟動。

## I-b-4：net_mode 調整後單次採集完成，對帳仍有缺口

使用者自行將 Demo 主帳戶改為 net_mode 後，依明確指令執行一次既有正式入口，未修改 gate。status=collected、config_gate_passed=true；13 個來源分頁完成，driver／wire 各 41 次，exit 0。餘額解碼無效、其他資料 mode_mismatch、未載入歸因、P6 子單／保護／觸發對帳與新鮮度／窗口／日初基準等差異仍在，reconciled=false、trade_authorized=false；詳見 [實際採集紀錄](docs/demo-collection-handoff.md)。僅保存非敏感執行摘要；程序退出後未保留完整記憶體報告。未重跑、未交易、未改帳戶設定／交易 DB、未執行測試或 Git 檢查、未 commit／push；到此停止。

## 2026-09-15：I-b-4 改採使用者指定 Demo 主帳戶 API

使用者將本次指定憑證來源更新為 `C:\Users\user\Desktop\OKX_API.txt`，並於首次 config 結果後明確澄清該 API 即為 Demo 主帳戶，要求直接使用。I-b-4 因此把身份 gate 從「必須是子帳戶」改成「必須是主帳戶（uid=mainUid）」；Demo header、Global host、net_mode、acctLv 2／3、唯讀權限、24h／120 次／40 頁／180 秒等限制不變。account_report 的一般子帳戶政策訊號不改，只在這個明確授權的 one-shot runner 摘要中排除 `not_subaccount`。修改後 `test_demo_collection.py` 9／9、`test_okx_collection.py` 13／13、相關 `py_compile` 均通過；再次執行一次有界唯讀採集後，主帳戶身份 gate 已通過，但仍為 `config_mode_mismatch`，故 account_config 一頁後停止（driver 2、wire 1），其餘帳務端點未執行。未修改帳戶設定、未下單／撤單、未碰 Live、交易 DB、commit 或 push。詳見 [I-b-4 交接](docs/demo-collection-handoff.md)。

## 2026-09-15：I-b-3 已完成獨立驗收

使用者已授權 I-b-3。新增 `catos/okx_http.py` 的固定 Global Demo GET transport、記憶體簽名、分支 query／有界讀取；既有採集 driver 補統一計數的 opt-in rate-limit retry，decoder 補 algo reduceOnly 官方字串型別。另一模型依 [I-b-3 開發交接與驗證矩陣](docs/http-transport-handoff.md) 完成獨立 review：先由新增回歸測試抓到跨頁舊 ID 可重現的 `nonprogressing_page` 漏洞，已以 endpoint／partition 內已接受 ID 集合做最小修補並重驗。`test_okx_http.py` 24／24、`test_bounded_pagination.py` 16／16、`test_okx_collection.py` 13／13、`test_account_report.py` 19／19，共 72／72 通過；本機合成 TLS sender 覆蓋憑證驗證、GET/header、redirect、不使用代理環境、body/deadline 邊界。`py_compile` 通過，`git diff --check` exit 0；未追蹤 I-b 檔另以 no-index check 檢查，只有既有 LF→CRLF 提示。驗收未讀真實憑證、未連 OKX 或其他外部站點、未修改交易 DB、未 commit／push；僅使用 localhost 合成 TLS。I-b-3 到此停止，不自動續開 I-b-4／J／Live。

## 2026-09-14：I-b-2 已完成獨立驗收

使用者已授權 I-b-2。新增帳戶 decoder、差異報告、同批假名化與 18 個專屬合成測試；詳見 [I-b-2 交接](docs/account-decoder-handoff.md)。2026-09-14 由另一模型完成獨立 review 與驗證：`test_account_report.py` 18／18 通過，`git diff --check` exit 0（僅既有 LF→CRLF 警告），聚焦副作用掃描未發現連網、環境憑證讀取、SQLite、subprocess 或檔案寫入路徑；未發現 I-b-2 阻斷性問題。未讀憑證、連網、修改交易 DB 或 commit／push；本片驗收不自動續開 I-b-3／J／Live。

## 2026-09-14：I-b-1 已完成外部模型驗收

使用者已指定 `okx-demo`／Demo／台灣、`BTC-USDT-SWAP`，API 有交易權限、無提幣權限。已完成四項 review 問題的修補與 `collect_plan`／整批 manifest，詳見 [開發交接](docs/collection-driver-handoff.md)。2026-09-14 由另一模型完成 review 與驗證：`test_bounded_pagination.py` 14、`test_okx_collection.py` 13，共 27 tests passed，`git diff --check` 通過；未發現 I-b-1 阻斷性問題。驗證未讀憑證、未連 OKX、未 commit／push；本片驗收不自動續開 I-b-2／J／Live。

## 歷史紀錄：I-b 規劃交付，帳戶存取尚未啟動

使用者補充目標環境為 OKX Demo、地區為台灣；子帳戶代稱與首個 USDT-SWAP 合約尚待指定。此資訊補充不授權憑證讀取或帳戶連線。

2026-09-13 使用者確認 P6 正式預設為 mark／earlier／cancel_confirm，ratio=0% 不啟用；回報 I-a 16、P6 18、受影響合計 113 tests 與 diff 格式檢查通過。此為使用者交接基線，本輪不重驗。新分工：本模型負責規劃／開發，另一模型負責核對、review 與執行驗證。

已交付 [I-b 唯讀適配規劃](docs/readonly-account-plan.md)：帳戶／環境待指定、候選 GET 清單、有界採集與脫敏保存、四個開發切片及驗收出口。建議下一片為 I-b-1 離線採集契約與 driver；本輪僅完成規劃，不讀憑證、不呼叫私有端點、不進 J／Live、不 commit／push。以下 P6「參數待選」與測試執行描述保留為歷史紀錄，已由本段最新決策取代。

P6 交付用量快照：週配額剩餘 88%、5 小時剩餘 24%（帳戶共用，差額不等於本片精確用量）。

使用者授權 P6 本機切片後，完成 [保護生命週期](docs/protection-simulation.md)：同 writer／schema 5、每 Bot 設定、去重成交平均成本、整倉保護建立／更新／取消／UNKNOWN、本機告警及獨立增倉閘門。P6 專屬 18、受影響 F／P5／G／Journal／Supervisor 95，共 113 tests 通過。三項明示選擇（觸發來源、tick 取整、停用取消）尚待回覆，不默認套用測試值；未進 I-b／J，未 commit／push。

本輪驗證：P5 12、F 風控相關 27、G 執行相關 28、共用 Journal／Supervisor 28，共 95 個受影響模組測試通過；未重跑全域套件。完成即停，不進 I-b／J，不 commit／push。交付用量快照：週配額剩餘 96%、5 小時剩餘 76%（帳戶共用；與先前快照重設時間不同，不據差額估算本片成本）。

I-a 專屬 16 tests 通過，未重跑全域套件。2026-09-12 交付用量快照：Codex 週配額剩餘 2%，5 小時剩餘 13%；為帳戶共用數值，不能當成本片精確成本。依使用者要求完成 I-a 即停。

2026-09-12 使用者確認 D–G 全域驗收封版：177 tests 通過、0 failures／errors，已推送 `d3f3158be8c8327a14a386a68c4ef4e1fb6fe330` 與標籤 `v0.2-simulation-base`。H 已核對本機 HEAD／標籤一致，未重新驗證遠端或重跑測試。

2026-09-12 使用者確認 P2–P5，授權 I-a 並要求完成即停。[I-a 交付契約](docs/okx-readonly-contract.md) 包含官方欄位映射、新鮮度／完整性契約、離線標準化與差異檢查、P6 保護單能力／生命週期與最小決策選項。未接入憑證、私有端點或交易；I-b／J 未啟動，未 commit／push。

取消 equity buffer，E_risk = E_verified；被動超限只禁增倉，合法減倉始終允許，不自動去槓桿；陌生責任不接管或處置。固定 E_0、台北日界與資金流白名單不變。Soft／Hard 可配置，v1 預設 10%／20%；合格可隨時人工 re-arm，修改門檻不直接解除 latch。P5 本機遷移已完成：可配置 10%／20%、原子保存門檻、合格人工 re-arm、schema 4 控制稽核；舊意圖不復活。實際帳戶資料與交易所適配仍未接入。P6 已按最新決策定稿，見 [災難停損契約](docs/disaster-stop-policy.md)。

2026-09-12 H 文件交付查得：Codex 週配額剩餘 8%，5 小時配額剩餘 50%（帳戶共用快照）。與 G 紀錄相比週配額差額為 3 個百分點，不代表 H 的精確成本。

2026-09-11 使用者確認研究版驗收完成，隨後同意依規劃開始實作「本機模擬交易底座」；切片順序為 D：Worker／JSON 契約 → E：SQLite／單 Supervisor／所有權 → F：已確認風控 → G：假交易所／UNKNOWN／重啟對帳。

詳見 [階段規劃](docs/local-simulation-plan.md)、[D 使用契約](docs/worker.md)、[E 使用契約](docs/supervisor.md)、[F 風控契約](docs/risk.md)與 [G 執行契約](docs/execution.md)。D／E／F／G 已完成，未接入 Demo／Live；下方研究版分工與配額數字保留為歷史紀錄。

| 工作 | 狀態／出口 |
|---|---|
| D：獨立 Worker／JSON IPC | 已完成；IPC 11 個、Worker 13 個專屬測試通過。包含真實子程序故障、非同步控制、假憑證不繼承、SMA 狀態還原與父程序不載入策略 |
| E：SQLite／單 Supervisor／所有權 | 已完成；Journal 14、Supervisor 14、受影響 Worker 15，共 43 個模組測試通過；固定 Windows 單使用者 local-sim 範圍 |
| F：已確認風控 | 已完成；risk 14、risk journal 8、risk Supervisor 5，另跑受影響 Journal／Supervisor 28，共 55 個測試通過；未定案政策維持原狀 |
| G：假交易所／UNKNOWN／對帳 | 已完成；execution 18、Supervisor 8、程序中斷 1，另跑受影響 E／F 模組 41，共 68 個測試通過；只用本機假資料 |

2026-09-12 G 基線為 `3e41c97`，已核對 HEAD 與乾淨工作目錄。使用者回報 150 個全域測試全過並同步遠端；本輪未重跑全域測試或遠端驗證。完成固定 tag 的唯一模擬建單、永久訂單 ID、SUBMITTING／UNKNOWN、查單與撤單、成交去重、額度終結、原操作 reduceOnly 清倉、schema 2→3 及重啟對帳。專屬與受影響測試共 68 個通過，包含三個真實程序死亡時點。

G 沒有修改研究核心或策略邏輯、沒有網路／憑證／市場回測／Git commit 或 push。D–G 本機模擬底座完成後即交付；Demo／Live 與 P2–P6 待決金融政策仍需後續定案，不在本輪自動推進。

2026-09-12 G 交付查得：Codex 週配額剩餘 11%，5 小時配額剩餘 65%（帳戶共用快照）。與 F 紀錄相比週配額差額為 6 個百分點，不能歸為 G 的精確成本。本輪依使用者啟動 G 的授權完成，不另開新階段。

F 基線為使用者指定的 `c928195`，已核對 HEAD 與乾淨工作目錄；使用者回報基線測試全過。本輪只跑 F 及受影響模組，共 55 個測試通過，未重跑全域套件。完成 Decimal 最壞曝險、原子數量保留、固定日初分母、台北切日、獨立風險事件、鎖存／epoch、合法減倉與 schema 1→2 升級。未修改研究／Worker 策略邏輯、CLI／Optuna／下載工具，未執行行情下載或 Git 提交／推送。

2026-09-11 F 交付查得：Codex 週配額剩餘 17%，5 小時配額剩餘 12%（帳戶共用快照）。相較 E 紀錄，週配額差額為 6 個百分點，不能歸為 F 的精確成本。本輪依使用者啟動 F 的授權完成並交付，不續開 G；後續分工依下方既有配額流程評估。

E 基線為使用者指定的 `3879c55`，當時已核對 HEAD 與乾淨工作目錄。使用者回報基線全域 93／93 測試通過，E 未重跑全域套件。E 沒有修改研究核心、SMA 交易邏輯、既有 CLI／Optuna／下載工具，也未執行行情下載、Git 提交或推送。

E 已驗證 COMMIT 前後程序中斷、ACK 遺失重播、取消／關閉仍等待 writer、在途 80／100 額度阻擋第二筆、Kill 持續鎖存、跨 DB 路徑鎖競爭及 Worker 死亡保留所有權。F 單獨啟用時延續不可派送的 `HELD_SIMULATION`，另以合成風控取代 fixture 裁決；G 已新增明示啟用的假交易所生命週期與對帳閉環，舊 outbox 字面狀態不作為是否已送出的依據。

2026-09-11 E 交付查得：Codex 週配額剩餘 23%，5 小時配額剩餘 56%（帳戶共用快照）。與 D 紀錄相比週配額差額為 8 個百分點，不能歸為 E 的精確成本。依單片完成即交付原則，本輪不續開 F。

2026-09-11 D 交付查得：Codex 週配額剩餘 31%，5 小時配額剩餘 12%（帳戶共用，為查詢當下快照）。與任務 C 記錄相比週配額差額為 6 個百分點，包含其他工作，不能當成本模組精確用量。依單片完成即交付原則，本輪不續開 E。

## 研究版分工與配額紀錄

使用者已於 2026-09-11 同意此分工。研究版是中間里程碑，不等同可實盤完整 v1；v2 維持延後。

| 工作 | 負責者 | 狀態／出口 |
|---|---|---|
| Closed Bar Decimal 核心 | Codex | 使用者已驗收；18 個專屬測試通過 |
| Optuna 最小整合 | Codex | 已完成；8 個專屬測試通過、12-trial 合成示範成功；順序 ask/tell、整數／十進位候選、僅評分 Float |
| CSV 匯入 | Antigravity／Codex 審查 | 已完成；Codex 補強引號解析、Decimal 錯誤隔離與實體行號，16 個專屬測試通過（含回測整合） |
| 自包含研究報告 | Antigravity／Codex 審查 | 已完成；修正權益刻度精度與空曲線持倉呈現，12 個專屬測試通過 |
| 受影響介面審查與整合 | Codex | A、B 已審查；CSV → 回測 → 報告合成資料串接測試通過 |
| 離線報告視覺驗收 | Codex | 已完成；桌面／窄視窗共 12 組版面檢查，修正刻度裁切及持倉卡片排版；12 個報告專屬測試通過 |
| 研究版首次 Git 提交 | Codex | 已推送 b40609/CatOS_Astra，main 基線 99f59ee |
| 研究命令列入口 | Antigravity／Codex 審查 | 已完成；修正中斷與 close 失敗清理，15 個專屬測試通過；使用者後續授權的全域 69 個測試亦通過，納入本輪提交 |

以目前使用者提供的 Antigravity／Gemini 配置作為備援，不假設其配額、品質或自動調用通道。交接入口為 ANTIGRAVITY_HANDOFF.md，不建立跨 IDE 自動化系統。一次一個模組，不讓兩個 IDE 同時改同一檔案。

每個模組交付時查一次 Codex 用量，記錄實際變化後再估下一個切片；用量為帳戶共用，不能把差額全歸因本專案。以週配額剩餘 20% 為預留整合／修復／審查的工作分界；接近時不再啟動大型新增功能，轉交界線清楚的實作。此為每次交付時執行的流程，沒有背景監控或自動通知。

2026-09-11 Optuna 交付時查得：週配額剩餘 46%，5 小時配額剩餘 19%；預計重設時間分別為 2026-09-17 11:49、2026-09-11 14:26（Asia/Taipei）。規劃時週配額為 50%，觀察差額為 4 個百分點；因帳戶共用，不視為本模組的精確成本。

2026-09-11 CSV 審查時查得：週配額剩餘 45%，5 小時配額剩餘 98%。本輪僅重跑 CSV 專屬測試；Antigravity 回報的 39 個全域測試通過未於本輪重驗。

2026-09-11 報告審查交付時查得：週配額剩餘 44%，5 小時配額剩餘 91%。本輪僅執行報告專屬測試（12 個，含 CSV 串接與 Decimal context 隔離），未重跑全域套件，未進行瀏覽器視覺驗收。本輪 A／B 分工及受影響介面審查完成；尚不等同完整實盤 v1。

2026-09-11 視覺驗收完成時查得：週配額剩餘 42%，5 小時配額剩餘 79%。已生成可離線開啟的 `reports/visual-qa/synthetic-report.html`；驗收範圍與證據見 `docs/reporting.md`。本輪未新增行情下載、UI 服務或交易功能。

2026-09-11 任務 C 審查完成時查得：Codex 週配額剩餘 37%，5 小時配額剩餘 53%（帳戶共用）。本輪僅執行 CLI 專屬測試；任務 C 與交接文件仍為本地未提交修改。

2026-09-11 使用者另行授權全域測試與推送：執行 `py -3 -B -m unittest discover -s tests -v`，69 個測試全數通過（核心 18、Optuna 8、CSV 16、報告 12、CLI 15）。任務 C 程式、測試、設定範例與文件納入本輪 Git 提交。

研究版交付範圍不包含 SQLite、Web UI、OKX 連線、Guardian、保證金／強平、UNKNOWN／對帳或多策略分倉。後續本機模擬範圍依上方新規劃；實盤前仍須完成相應政策、交易底座與故障驗證，不能以節省配額省略金融底線。
