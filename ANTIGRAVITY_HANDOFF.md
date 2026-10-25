# Antigravity 交接：研究版周邊模組

2026-09-11：使用者已同意 Codex 負責精度、Optuna 與關鍵整合審查，Antigravity 負責界線清楚的資料匯入及報告。任務 A、B 均已交付並經 Codex 補強審查；CSV 16 個、報告 12 個專屬測試各於其交付輪次通過，報告測試包含 CSV → 回測 → 報告串接。下方規格保留為交付紀錄，不再派送重做。

## 原始開始指令（已完成，不再執行）

請在 `C:/Users/user/Desktop/CatOS` 開啟本專案，讀取 `AGENTS.md`、`README.md` 及本檔。任務 A 已完成，現在只執行下方任務 B，不修改已驗收的 CSV 模組及其測試；通過任務 B 專屬測試就停止並交付，不跑全域測試。所有修改用結構化 Patch。使用假資料與本地暫存測試檔，不讀取憑證或真實金鑰環境變數、不連接交易所。若遇到規格衝突，說明具體檔案與行號，不自行改寫金融政策或核心測試。

`catos/research.py` 是已驗收的 Decimal 核心。不要修改核心、`catos/optimization.py`、`AGENTS.md`、架構文件、既有測試或依賴檔；不要重構整個專案。需要的介面變更列為建議，交回 Codex 評估。兩個 IDE 不同時修改同一檔案。

## 任務 A：CSV 已收盤 K 線匯入

可新增檔案僅限：

- `catos/data_io.py`
- `tests/test_data_io.py`
- `docs/data-io.md`

實作 `load_candles_csv(path, *, config: BacktestConfig) -> tuple[Candle, ...]`，使用 Python 標準函式庫。

輸入 UTF-8（允許 BOM）CSV 表頭固定為 `open_time_ms,open,high,low,close,closed`，拒絕缺欄、重複欄、多餘欄、資料列欄數不符。時間以整數文字解析；價格直接由文字建立 Decimal，禁止先轉 Float；`closed` 只接受文字 `1`。不得自動排序、補 K 線、插值、載入 1m、猜合約規格或自行下載行情。

匯入後可透過 `research._call(research._validate, config, bars, 0)` 重用目前內部驗證器（不改核心），檢查有限價格、OHLC、tick、時間序列與缺口。錯誤需可理解：CSV 解析錯誤標示列號／欄位，核心驗證錯誤保留其訊息。不要將空字串當零。資金費仍由 config 明確提供；此任務不新增資金費下載或默認填補機制。

專屬測試：正常檔及 BOM、小數精度不流失、未收盤、空檔／只有表頭、缺欄／重複欄／多欄、無效時間、NaN／Infinity、錯序／重複／缺口、非法 tick；至少一個 CSV 載入後接既有 backtest 的合成資料案例。測試寫入 `tempfile.TemporaryDirectory`，不依賴真實資料檔。

驗收命令：`py -3 -B -m unittest discover -s tests -p test_data_io.py -v`。

## 任務 B：純函式研究報告

可新增檔案僅限：

- `catos/reporting.py`
- `tests/test_reporting.py`
- `docs/reporting.md`

實作 `render_report(result: BacktestResult) -> str`，回傳自包含的繁體中文 HTML。只使用標準函式庫，不啟動服務、不寫檔、不用 CDN、不載入外部 JavaScript 或圖片。由呼叫端另行決定保存方式。

呈現合約、週期、預熱根數、正式起訖、初始／期末權益、實現／未實現損益、費用、資金費、收盤最大回撤、逐筆成交、資金費分錄、期末持倉與未成交意圖。顯示 result.assumptions 及「研究結果，非 Demo／Live 執行器」邊界。直接呈現既有績效值，不重算會計、不加入勝率等未定義指標。

使用內嵌 SVG 呈現簡單收盤權益折線；座標運算採 Decimal／整數後輸出字串，不新增 Float 例外。處理空曲線、單點、水平曲線及負權益；所有插入 HTML 的資料文字必須 escape。交易筆數指模擬成交筆數，不宣稱往返交易數。不要加入 Web UI、互動交易按鈕或優化器儀表板。

專屬測試：正常結果、沒有成交／資金費、未平倉及未成交意圖、單點／水平曲線、HTML 文字跳脫、Decimal 原值呈現、沒有外部資源引用及輸入結果不被修改。

驗收命令：`py -3 -B -m unittest discover -s tests -p test_reporting.py -v`。

## 每次交付格式

回報修改檔案、實作功能、實際驗收命令與測試結果、未完成項目。若失敗，保留失敗證據，不降低斷言或刪除測試來取得通過。不要自行擴充下一階段；交回 Codex 進行受影響介面的審查。本文的驗收要求是交付條件，不是目前已完成或已通過的聲明。
