# catOS：純函式研究報告

`catos.reporting` 模組提供純標準函式庫的自包含 HTML 報告產生器，將 `catos.research.BacktestResult` 輸出為繁體中文離線靜態報告。

## 介面規格

```python
from catos.reporting import render_report
from catos.research import BacktestResult

html_content: str = render_report(result)
```

- `result`：`BacktestResult` 回測結果物件。
- 回傳：自包含的繁體中文 HTML 字串（含內嵌 CSS 與 SVG 權益曲線）。
- 特性：純函式設計，不修改輸入物件、不寫入檔案、不啟動 Web 服務、無外部 CDN、JavaScript 或外部圖片依賴。

## 呈現內容

1. **基本設定與合約資訊**：合約標的代號、K 線週期、預熱根數、正式評估起訖時間戳（ms）、每張合約標的幣數、tick size、lot size、min size、費率與滑價設定。
2. **核心績效指標**：初始權益、期末權益、淨損益、總報酬率（%）、已實現損益、未實現損益、手續費總支出、資金費總支出、收盤最大回撤（%）、模擬成交筆數。
3. **期末部位與委託狀態**：期末持倉張數、持倉均價、末根未成交意圖（若有標明目標張數與決策時間戳）。
4. **收盤權益曲線**：以內嵌 SVG 呈現折線圖，處理空曲線、單點、水平等權益曲線以及負權益／穿越零軸之情形。
5. **逐筆成交明細**：模擬成交時間、決策時間、成交張數、成交價格、手續費、實現損益及成交後持倉張數。
6. **資金費分錄**：結算時間、結算持倉張數、資金費率、標記價格及支付金額。
7. **模型假設與邊界聲明**：呈現 `result.assumptions` 逐條假設，並顯著標示「研究結果，非 Demo／Live 執行器」與「交易筆數指模擬成交筆數，不宣稱往返交易數」。

## 數值與安全契約

- **純十進位與整數運算**：SVG 折線與座標運算採 Decimal 與整數，禁止 Float 操作；金額與比率以完整精度字串呈現，無浮點截斷或科學記號變形。
- **HTML 跳脫**：所有動態插入 HTML 之字串皆經由 `html.escape(..., quote=True)` 跳脫，防範 XSS 注入。
- **無外部資源**：完全離線可用，無 `<script src="...">`、`<link rel="stylesheet">` 或 `<img src="http...">`。
- **會計忠實性**：直接呈現既有績效，不重新計算會計帳務，不擅自加入勝率、盈虧比等未定義指標。
- **曲線邊界**：權益刻度使用定點十進位文字，僅 SVG 座標取至一位小數；空曲線的期末持倉與均價標示「無資料」，不推定為零。圖表運算隔離呼叫端 Decimal context。

## 使用範例

```python
from pathlib import Path
from catos.reporting import render_report
from catos.research import backtest

result = backtest(
    strategy=MyStrategy,
    candles=candles,
    config=config,
    warmup_bars=10,
)

# 取得自包含 HTML 字串，由呼叫端自行決定保存方式
html_report = render_report(result)
Path("reports/backtest_btc.html").write_text(html_report, encoding="utf-8")
```

## 本切片界線

僅提供將純記憶體回測結果轉換為 HTML 報告字串之純函式。不包含 Web 儀表板、互動下單按鈕、多策略彙整或 Optuna 搜尋結果儀表板。

## 離線示範與視覺驗收

執行 `py -3 -B -m examples.report_demo`，產出 `reports/visual-qa/synthetic-report.html`。示範以合成 CSV 經既有回測核心生成，非歷史績效。另產生的 `fixture-*.html` 僅供曲線版面邊界檢查，人工替換的曲線不可與績效卡片作會計比對。

2026-09-11 使用本機 Edge 無頭瀏覽器，以 1280×900 與 390×900 視窗檢查正常、空曲線、單點、水平、極小小數及跨零負權益，共 12 組。已修正長刻度裁切及窄視窗持倉卡片擠壓；窄視窗圖表保留可讀尺寸，圖表與表格可水平捲動。12 組均無 SVG 文字越界、頁面橫向溢出或外部 HTTP 請求，並檢視正常報告、持倉、極小數曲線及表格捲動截圖。報告專屬 12 個單元測試通過；未執行全域套件。

驗收腳本、幾何檢查結果與截圖存於 `reports/visual-qa/`。`check.cjs` 使用本機已備妥的 Playwright 與 Edge 路徑，仅為開發驗收工具，不是報告執行依賴。
