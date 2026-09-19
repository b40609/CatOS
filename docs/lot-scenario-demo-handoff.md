# S8 開發交接：固定合成情境範例入口

## Astra 獨立靜態審查與補強（2026-09-19）

原始 S8 程式及 16 個測試由 Sol 編寫，下方 37/37 是 Sol 實作者自測紀錄，不是 Astra 獨立執行驗收。本輪依使用者授權完成獨立程式／規格審查，未發現主要業務流程的阻斷缺陷，保留 `examples/lot_scenario_demo.py` 原實作。

審查發現並修正驗證缺口：

- A02 原用子字串斷言，MATCH 可誤匹配 MISMATCH、數值 1 可誤匹配 10；改為精確比較。
- A03 原只檢查部分原因存在／缺席；改為解析 reasons 區塊並斷言精確兩項原因及完整旗標／metadata。
- A04 原確認兩次 render 共用 capture，但未計算 capture 呼叫次數；新增真實 capture spy。
- C01／C02 原以整個情境失敗及 exception 類別名稱代替細部契約；新增 bind／fill／capture／兩次 renderer 故障、原始雙重例外物件斷言。
- C03 原保存失敗案例實際只涵蓋檔名衝突；補入兩份檔案的 stream write／close 故障，檢查部分產物保留。
- B04／C04／D01／D04 補上權限失敗、第一份 HTML 前真實 SQLite connection 已關閉、help／usage 阻斷副作用、console 失敗非零。

專屬測試由 16 增至 22 個方法，含子案例；Astra 補強階段只編寫及靜態閱讀，未執行 Python、測試、編譯、DB、視覺驗收或 Git。原 37/37 僅為補強前歷史自測，不代表修正後版本。

Sol 於 2026-09-19 完成修正後重驗：S8 專屬 22/22、S7 必要回歸 21/21，共 43/43，0 failure／error／skip；`py_compile` 通過。Python 3.14.6、SQLite 3.50.4。生產程式與 HTML 未改，因此本輪不重做既有視覺矩陣；限定範圍 staged review 僅納入 S8 五檔。

下方保留 Sol 原始實作與自測歷史，最新驗收狀態以上述 43/43 為準。

狀態：2026-09-19，依 [S8 正式規格](../outputs/catos-s8-scenario-example-spec.md)完成固定本機範例、專屬測試與本交接。範例只使用既有 S3／S5／S7 公開入口，不修改 Journal、S3／S5／S6／S7、Schema7、Risk、P6、execution／protection 或交易路徑。

## 實作內容

- 新增 `examples/lot_scenario_demo.py`，入口為 `python -B -m examples.lot_scenario_demo --output-dir <new-dir>`。
- 固定建立 `s8-example-account`／`local-sim`、單一 `SYNTHETIC-USDT-SWAP`、OPEN 3 張及 1 張合成成交；不 terminal，保留 2 張未決責任。
- 真實建立新 Journal，經 S3 `register_binding`／`bind_order`／`apply_fill`，再恰取一次 S5 capture。
- 同一 capture 依 complete→degraded 順序各呼叫一次 S7 renderer；不由 S8 另算曝險、不另呼叫 S4／S6。
- 成功前先關閉 Journal，再以 exclusive create 依序保存 `complete.html`、`degraded.html`。目標目錄必須不存在，父層必須已存在；不提供 force、覆寫、清理或續跑。
- 失敗時保留本次已建立的 DB／HTML 供檢查；一般錯誤回傳 1 並輸出固定 stage。KeyboardInterrupt／SystemExit 不被一般錯誤處理吞掉；已取得 Journal 仍嘗試關閉。若情境與 close 同時失敗，以 exception group 保留兩者。
- 成功 stdout 僅列 database／complete／degraded 三個絕對路徑，不讀環境變數、憑證、行情或目前時鐘作為情境資料。

## 初版專屬測試覆蓋（歷史）

補強前 `tests/test_lot_scenario_demo.py` 共 16 個方法，包含：

- 真實新 SQLite 的部分成交、未 terminal、完整與降級報告語義、同一 capture／兩次 renderer。
- 兩個不同新目錄的 HTML byte-for-byte 可重現、UTF-8 無 BOM、長 Decimal 保留。
- 既有空／非空目錄、一般檔案、有效及懸空 symlink、缺父層／父層非目錄拒絕。
- help／usage／空路徑／未知參數／縮寫拒絕、含空白路徑的實際 `python -m` 啟動。
- Journal 初始化、情境、close、complete／degraded 保存失敗；第二檔失敗時保留第一檔與 sentinel。
- KeyboardInterrupt 仍關閉 Journal 後傳遞；生產模組不引用 tests、私有 capture hash、環境讀取或網路套件。

## 初版實作自測（歷史）

- `test_lot_scenario_demo.py`：16/16 通過。
- S7 必要回歸 `test_lot_scenario_report.py`：21/21 通過。
- 合計 37/37，0 failure／error／skip；未執行全量測試。
- `examples/lot_scenario_demo.py` 與 `tests/test_lot_scenario_demo.py` 通過 `py_compile`。
- Python 3.14.6、SQLite 3.50.4。
- 實際執行新入口成功建立 `scenario.sqlite3`、`complete.html`、`degraded.html`；complete／degraded 均以本機 Chrome 1280 px viewport 開啟確認可讀。QA 產物位於忽略的 `reports/s8-qa-20260919-impl/`，不應納入 Git。

## Git 邊界

S8 預定提交範圍限：`examples/lot_scenario_demo.py`、`tests/test_lot_scenario_demo.py`、本交接、README、WORK_PLAN。工作樹既有 S5／S6／S7 補記、market、yaozi 及其測試／輸出均屬其他切片，不得混入。

提交前已執行限定範圍 `git diff --check`、staged check，並確認生成的 DB／HTML／PNG 未被暫存。
