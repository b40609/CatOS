# catOS 階段與分工規劃

## 2026-09-20：S9 正式規格通過 Sol 文件驗收

使用者回報 assessment 已通過並提交 `bb29389`。依指示完成 [S9 正式規格](outputs/catos-s9-fee-completion-spec.md)，明定新建 schema8、版本化 Lot／event／capture、費用 API、原子重放及驗收矩陣；completion 保留事件當下 head／active flags，fee subtotal／count／coverage 全部進 payload、replay/hash 與 capture identity。保留 schema7，禁止靜默 migration 或 nullable 化舊費用契約。

Sol 依現行 Journal、S2–S7 實碼交叉核對，未發現阻斷缺陷；確認 `PRAGMA user_version` 維持單一 Journal schema 標記，`lot_schema_version` 僅選擇 schema7／8 路徑，不能形成第二個持久化版本來源。正式規格可進實作授權階段；本輪仍僅文件，未執行 Python、DB、測試或編譯，尚未修改程式或取得既有 DB migration 授權。其他未提交補記與功能保持獨立。

## 2026-09-20：S9 fee completion assessment 通過 Sol 契約審查

使用者確認 S8 已完成重驗及限定提交，`b069082` 為 S9 前穩定基線。依指示完成 [S9 費用補齊評估與待審契約](outputs/catos-s9-fee-completion-assessment.md)：缺費成交先更新部位與價差帳務，費用以已知小計＋未補齊成交數表達；補費綁定原成交、只允許 unknown→known，terminal 後不重開訂單。列明補零版本證據、active CLOSE 旗標、舊 schema7／replay 相容及 S5–S8 品質傳遞風險。

Sol 依現行 S2／S3／S5 實碼交叉核對，未發現阻斷缺陷；unknown→known、terminal 後補費、補 0 版本證據、舊 schema7 相容與品質分離可進正式規格。正式規格須明定 completion revision 使用事件當下的 Lot head／active order 旗標，並使 fee subtotal／unknown count／coverage 成為明示版本化 payload、replay/hash 與 capture identity。評估不構成 Schema／DB 變更授權；其他未提交工作保持獨立。

## 2026-09-19：S8 修正後通過 Sol 重驗與限定範圍驗收

依使用者授權審查 Sol 已完成的實作與正式規格，未發現主要流程阻斷缺陷，生產程式維持原狀。補強精確狀態／數值與原因集合、capture 次數、細部資料及輸出故障、雙重例外物件、關閉順序與 console 失敗等測試，專屬方法由 16 增至 22。詳見 [S8 交接審查紀錄](docs/lot-scenario-demo-handoff.md)。

原 37/37 為 Sol 實作者自測歷史。修正後由 Sol 實際執行 S8 22/22、S7 報告回歸 21/21，共 43/43，0 failure／error／skip；新增 Python 檔 `py_compile` 通過，Python 3.14.6、SQLite 3.50.4。生產程式與 HTML 未改，本輪不重做既有視覺矩陣；限定範圍 staged review 僅納入 S8 五檔。其他未提交功能與紀錄不在本輪範圍。

## 2026-09-19：S8 固定合成範例入口初版實作自測（歷史）

依 [S8 正式規格](outputs/catos-s8-scenario-example-spec.md)新增 `examples/lot_scenario_demo.py` 與 `tests/test_lot_scenario_demo.py`。固定新 Journal 經 S3 部分成交→S5 capture→S7 complete／degraded HTML；目標目錄原子拒絕既有項目，Journal 關閉成功後才 exclusive create HTML，失敗保留本次產物、不自動清理。未修改 Journal、S3／S5／S6／S7、Schema7、Risk、P6 或交易路徑。詳見 [S8 開發交接](docs/lot-scenario-demo-handoff.md)。

該次自測實際執行 S8 專屬 16/16、S7 報告回歸 21/21，共 37/37，0 failure／error／skip；新增 Python 檔編譯通過。Python 3.14.6、SQLite 3.50.4。另實際執行入口並以本機 Chrome 1280 px 開啟 complete／degraded HTML；QA 產物位於忽略的 `reports/s8-qa-20260919-impl/`。該次未執行全量測試且尚未建立 S8 commit；既有 S5／S6／S7 補記、market、yaozi 等未提交內容保持獨立。

## 2026-09-19：S8 正式規格已通過文件驗收

使用者回報 S8 評估已驗收並提交 `8c0000a`，技術敘述、本地連結、格式及 diff 檢查通過，純文件未執行 Python／DB。依指示完成 [S8 正式規格](outputs/catos-s8-scenario-example-spec.md)：固定 3 張 OPEN／1 張成交、同 capture 的完整與降級情境、必填新輸出目錄、關閉 Journal 後 exclusive create 兩份 HTML，以及失敗保留產物與非零結束碼。

Astra 開發階段僅制定文件並靜態核對，未編寫或執行 S8 程式、測試、DB、編譯或 Git。Sol 文件驗收確認固定常數與現行 S3／S5／S7 契約一致，本地連結、格式與 diff 檢查通過；純文件未執行 Python、測試或 DB。下一片依驗收規格實作範例與專屬測試；其他功能及既有補記維持獨立。

## 2026-09-19：S8 固定合成範例入口評估完成

依使用者同意完成 [S8 範圍評估](outputs/catos-s8-scenario-example-assessment.md)。建議採全新輸出目錄中的合成 Journal，經 S3 部分成交→S5 capture→S7 renderer 產生完整／降級 HTML；固定資料與時間，HTML 可重現，拒絕既有目錄及覆寫，保留合成 DB 與失敗產物、不自動清理。範例不引用 tests，不接受使用者 DB 或交易參數。此為評估建議，正式常數、入口及錯誤契約為下一交付，未開始 S8 程式。

本輪僅閱讀與文件補丁，未執行 Python、測試、DB、報告生成或 Git；S7 及其他未提交功能維持獨立。

## 2026-09-19：S7 renderer 已通過 Sol 驗收

使用者回報 S7 正式規格已驗收並提交 `299884f`，40/40 欄位與 16/16 原因碼、本地連結及 diff／staged 檢查通過；純文件未執行 Python 測試。依此完成 `lot_scenario_report.py` 與 21 個專屬測試方法，純函式先呼叫一次 S6，再產生離線 HTML。含真實 Journal 成交生命週期、空值／過期資料、精度、HTML 逸出與錯誤傳遞案例，詳見 [S7 開發交接](docs/lot-scenario-report-handoff.md)。

Sol 驗收結果：S7 21/21、S6 34/34，共 55/55，0 failure／error／skip；Python 3.14.6、SQLite 3.50.4，新增 Python 檔編譯通過。F01 以完整／降級樣本分別在 1280 px／390 px 渲染並檢視全頁；四組皆無整頁水平溢位、無裁切儲存格，長 Decimal、`不可用`／`未提供`、品質旗標及原因可讀。未執行全量測試；未修改既有 S4／S5／S6、Schema、Risk、P6 或交易路徑，其他未提交工作保持獨立。

## 2026-09-19：S7 正式報告規格已交付

依使用者同意，完成 [S7 正式 API／欄位映射／驗收規格](outputs/catos-s7-scenario-report-spec.md)。單一純函式接收 capture／scenario／now_ms，先呼叫一次 S6，再產生離線繁體中文 HTML；完整保留 Decimal、None／零、來源、品質旗標與降級原因，不重算 S4 或增加交易裁決。明定過期但有值時仍保留數值與旗標、synthetic 分項零不代表交易所無委託，以及錯誤原樣傳遞。

本輪僅制定文件並靜態核對既有契約，未編寫 S7 程式，未執行測試、編譯、Git 或資料庫操作。後續實作依正式規格，Astra 編寫、Sol 驗證與 Git；yaoI／yaozi、market 及 S5 未提交驗收紀錄不在本片範圍。

## 2026-09-19：S6 已驗收；S7 報告入口範圍評估

依使用者回報，S6 commit `ecc897e3afc19ab03527a4e1529f060b83f21df7`（`feat(lots): add S6 synthetic scenario adapter`）；S6 34/34、S4 42/42、S5 39/39，合計 115/115，0 failure／error／skip。Python 3.14.6、SQLite 3.50.4；`py_compile`、`git diff --check`、staged check 通過，未執行全量測試。Schema、Risk、P6、execution／protection／交易路徑未變。回報時 `main` ahead 6；S5 驗收紀錄與 market／yaozi 工作未納入 S6 commit，工作區並非全乾淨。

本輪依使用者同意補齊驗收紀錄，完成 [S7 本機合成情境報告入口評估](outputs/catos-s7-scenario-report-assessment.md)。建議以純函式輸出離線 HTML，沿用 S6 校驗與 S4 計算，呈現來源、曝險、完整性與降級原因；本輪僅評估，未開始 S7 程式或新增帳務／交易政策。yaoI／yaozi 為獨立功能，market 相關工作也不納入本片。Astra 未執行測試、編譯、Git 或資料庫操作；以下保留各階段歷史。

## 2026-09-18：S6 已編寫，待 Sol 質檢

依 [S6 正式規格](outputs/catos-s6-scenario-spec.md)新增純資料`lot_scenario.py`，驗證S5內容身份及內部一致性，以明示scenario cut／capture binding轉接到S4。S4加上synthetic來源分類、evidence kind與專屬buckets；保留既有OBSERVED預設。新增S6測試及S4回歸，包含真實S3→S5→S6生命週期、容量、派生精度與不完整降級。詳見 [S6開發交接](docs/lot-scenario-handoff.md)。Astra未執行測試、編譯或Git；未修改Schema7、S5、Risk、execution、protection或交易路徑，未處理其他工作區草稿與market-intel檔案。

## 2026-09-18：S6 合成情境轉接正式規格已交付

依既有 [S6 範圍評估](outputs/catos-s6-scenario-assessment.md)完成 [S6 正式規格](outputs/catos-s6-scenario-spec.md)。定案採 `SYNTHETIC_LEDGER / UNTERMINATED`，不把 S5 本機責任偽裝成 HELD／EXCHANGE／WORKING／UNKNOWN；S4 以 additive `evidence_kind=SYNTHETIC_SCENARIO` 與 synthetic buy/sell buckets 保留 provenance。Lot／Pending／synthetic physical 的共同截點只能由明示 `scenario_cut_id` + 精確 `source_capture_id` attestation 成立，`capture_id` 本身不當共同 cut；unmanaged unresolved 使 pending 降級為 incomplete，不補造未知委託。本輪只交付設計文件，不重做 S5 驗收、不執行測試、不做 git add／commit／push；僅以 diff/status 做文件與工作區檢查，也不處理其他無關工作區檔案。

## 2026-09-18：S5 已驗收；S6 轉接範圍評估

依使用者回報，S5 commit `274891981027cf554c590224f68f4ea7c46bb716`（`feat(lots): add S5 consistent snapshot capture`）；S5 39/39、S2/S3/S4/Journal 必要回歸141/141，合計180/180、0 failure/error/skip。真實雙connection WAL隔離及4096/4097容量邊界通過；Python3.14.6／SQLite3.50.4，diff/staged檢查通過，未執行全量測試。Schema7、Risk、execution、protection與交易路徑未變。回報時main ahead5；另有未提交的`outputs/yaozi-functional-parity-spec-v0.1.md`，未納入S5，本輪不處理該檔案。

下一片評估見 [S6 合成情境轉接評估](outputs/catos-s6-scenario-assessment.md)。先釐清S5本機責任與S4來源／狀態／共同截點語義，尚未核准新政策或開始S6程式。Astra本輪僅更新文件，未執行測試或Git；本段及評估文件不包含在上述已完成的S5提交。

## S5 已編寫，待 Sol 質檢

依正式S5規格新增`catos/lot_snapshot.py`，Journal增加`capture_lot_snapshot()`及BEGIN DEFERRED／metadata首讀／ROLLBACK的唯讀範圍。新增39個測試方法，含真實雙connection WAL一致性、完整內容身份、無寫入與4096輸出邊界。未改Schema7、S2/S3/S4業務邏輯、Risk、P6或交易路徑；本輪未執行測試、編譯或Git。詳見 [S5開發交接](docs/lot-snapshot-handoff.md)。

## 2026-09-18：S5 正式 API／快照身份／驗收規格已交付

依 S5 範圍評估完成 [S5 一致快照正式規格](outputs/catos-s5-snapshot-spec.md)：公開入口為 `Journal.capture_lot_snapshot()`，只用既有 Journal connection 的 `BEGIN DEFERRED` 一致讀取；輸出完整 matching Bot 水位、current Lot、S3 synthetic pending 與未受 S3 管理的 unresolved Lot。`capture_id` 採逐筆具名 object＋8-byte 長度前綴的 streaming SHA256，排除時間與 DB path；未成交 OPEN、零剩餘但未 terminal 責任均保留。規格明確禁止猜 HELD／WORKING／UNKNOWN、反推 physical 或接風控／交易。此輪僅文件，不改 Schema 或程式，不執行測試或 Git。

## 2026-09-18：S4 已驗收；S5 一致快照範圍評估

依使用者回報，S4 commit `8b16c0b244af611294ec0a98b8add835bb14008b`，36＋26＋14合計76/76、0 failure/error/skip；Python3.14.6／SQLite3.50.4，diff/staged檢查通過，未跑全量；提交後working tree clean、main ahead4。本輪僅記錄驗收及新增 [S5評估](outputs/catos-s5-snapshot-assessment.md)，未執行測試或Git；文件修改發生於該提交之後。

建議先做同一讀取交易的Lot＋S3合成未決責任匯出；S3缺乏HELD／WORKING／UNKNOWN來源證據，不直接映射成S4交易所在途。保留首次成交前OPEN與零剩餘但未terminal責任；不從Lot反推physical。正式API與驗收規格為下一交付，尚未開始S5程式實作，不改Schema／Gross限制／Demo／Live。

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
