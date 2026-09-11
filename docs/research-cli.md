# catOS：研究命令列入口

`catos.research_cli` 模組提供純標準函式庫的命令列入口，串接 CSV 匯入（`load_candles_csv`）、回測執行（`backtest`）與自包含報告產出（`render_report`），讓使用者能以單一命令完成本機 Closed Bar 策略研究。

## 執行方式

### 1. 前置資料準備（可選）

若需要示範用的合成 15 分鐘 K 線資料，可在專案根目錄執行既有示範腳本生成 `reports/visual-qa/synthetic.csv`：

```powershell
py -3 -B -m examples.report_demo
```

### 2. 執行研究回測命令

```powershell
py -3 -B -m catos.research_cli --csv reports/visual-qa/synthetic.csv --config examples/research-config.json --strategy sma-trend --output reports/research.html
```

- `--csv`（必填）：已收盤 K 線 CSV 檔案路徑。
- `--config`（必填）：回測 JSON 設定檔路徑。
- `--strategy`（必填）：策略代號，目前固定支援 `sma-trend`（映射至 `examples.closed_bar_demo.SMATrend`，固定兩根 SMA、目標兩張或空倉）。
- `--output`（必填）：輸出 HTML 報告路徑，副檔名必須為 `.html`。

所有命令列相對路徑均以當前工作目錄為基準解讀。

## JSON 設定檔契約

設定檔為 UTF-8（允許 UTF-8 BOM）JSON 物件，所有欄位皆為必填。

範例內容（見 `examples/research-config.json`）：

```json
{
  "contract": {
    "inst_id": "SYNTHETIC-USDT-SWAP",
    "base_per_contract": "0.01",
    "tick_size": "0.01",
    "lot_size": "1",
    "min_size": "1"
  },
  "timeframe_ms": 900000,
  "initial_balance": "1000",
  "fee_rate": "0.0005",
  "slippage_bps": "2",
  "funding_events": [],
  "warmup_bars": 2
}
```

### 驗證規則

1. **鍵值完整性**：根物件、`contract` 及 `funding_events` 元素拒絕缺漏鍵、未知多餘鍵，且任何層級均嚴格拒絕重複鍵。
2. **數值型態**：
   - 金融價格、數量與比率（`initial_balance`、`fee_rate`、`slippage_bps`、`base_per_contract`、`tick_size`、`lot_size`、`min_size` 以及資金費率 `rate`、標記價格 `mark_price`）必須使用 JSON 字串，以直接建立高精度 `Decimal`，禁止透過 float。
   - 時間與根數（`timeframe_ms`、`warmup_bars`、資金費事件 `time_ms`）必須為 JSON 整數，拒絕布林值（`true`/`false`）、浮點數與字串。
   - `warmup_bars` 必須為非負整數（`>= 0`）。
   - 拒絕 JSON 常數 `NaN`、`Infinity`、`-Infinity`。
3. **資金費事件**：`funding_events` 必須為明確陣列；空陣列代表使用者假設無資金費事件。若有元素，各元素必須包含 `time_ms`（整數）、`rate`（字串 Decimal）、`mark_price`（字串 Decimal）。

## 輸出與覆蓋保護機制

1. **副檔名限制**：輸出路徑副檔名必須為 `.html`（不分大小寫）。
2. **避免覆蓋輸入**：解析後的輸出路徑若與輸入 CSV 或設定檔路徑相同，立即報錯拒絕。
3. **拒絕覆蓋既有報告**：若輸出檔案已存在，拒絕執行並退出，不提供 overwrite 或 force 選項。
4. **目錄建立**：若輸出檔案的父目錄不存在，自動遞迴建立。
5. **獨佔建立模式（`x` mode）與失敗清理**：完成讀取、驗證、回測與報告渲染後才建立檔案。寫入、flush、close 失敗或 KeyboardInterrupt 時，關閉檔案並比對檔案識別後嘗試清理本次半成品，原例外繼續傳出。建立競爭導致檔案已存在時不刪除該檔案。若作業系統拒絕清理，仍可能留下半成品；不承諾斷電或強制終止後的原子持久化。

## 退出狀態碼

- `0`：成功。stdout 顯示輸出路徑，並附帶合成／歷史來源由使用者負責的研究邊界聲明。
- `2`：預期錯誤（檔案不存在、格式不符、JSON 結構無效、回測驗證失敗、檔案已存在等），錯誤訊息輸出至 stderr。
- argparse 標準行為：`--help` 正常退出（代碼 `0`）；缺少必要選項或無效策略參數退出（代碼 `2`）。

## 本切片界線

2026-09-11 Codex 審查後，15 個 CLI 專屬測試通過，包含實際成交／資金費與核心結果比對、預熱決策時序、巢狀重複鍵、Decimal context 隔離、建立競爭、中斷與 close 失敗清理。使用者後續授權執行 `py -3 -B -m unittest discover -s tests -v`，全域 69 個測試亦全數通過。

僅作為本地研究回測命令列工具。無外部網路連線、無憑證或金鑰讀取、無交易所 API、無 SQLite 資料庫，亦不宣稱已實現 Supervisor／Worker 程序隔離架構。
