# catOS：CSV 已收盤 K 線匯入

`catos.data_io` 模組提供純標準函式庫的 CSV 已收盤 K 線解析器，將歷史資料載入為十進位 `Candle` 序列供 `catos.research.backtest` 使用。

## 介面規格

```python
from catos.data_io import load_candles_csv
from catos.research import BacktestConfig, Candle

bars: tuple[Candle, ...] = load_candles_csv(path, config=config)
```

- `path`：CSV 檔案路徑（`str` 或 `PathLike`）。
- `config`：`BacktestConfig`，提供合約規格、週期與精度依據。
- 回傳：不可變的 `tuple[Candle, ...]`。

## CSV 格式契約

- **編碼**：UTF-8（允許 UTF-8 BOM）。
- **表頭**：固定為 `open_time_ms,open,high,low,close,closed`。拒絕缺欄、重複欄、多餘欄或順序不符。
- **欄位規格**：
  - `open_time_ms`：整數文字，以 `int` 解析。
  - `open`, `high`, `low`, `close`：價格文字直接建立 `Decimal`，禁止轉為 Float，保留完整十進位精度；空字串直接報錯，不當作零。
  - `closed`：只接受字串 `"1"`。未收盤（如 `"0"`）或其他非 `"1"` 字串一律報錯拒絕。
- **資料列**：每列欄數必須為 6，欄數不符立即報錯。
- **解析邊界**：啟用 CSV 嚴格引號檢查；錯誤列號採原始檔案的實體起始行號。無效 Decimal 文字一律提供欄位錯誤，不受呼叫端的 InvalidOperation trap 設定影響，也不污染其旗標。

## 驗證機制

解析完成後，重用核心驗證器 `research._call(research._validate, config, bars, 0)` 進行資料檢查：

1. **數值邊界**：拒絕 `NaN`、`Infinity`、非正數或超過支援精度（28 位係數、18 位小數）之數值。
2. **Tick 合法性**：OHLC 各價格必須符合 `config.contract.tick_size` 之整數倍。
3. **OHLC 幾何關係**：`low <= min(open, close)` 且 `max(open, close) <= high`。
4. **時間連續性**：K 線必須嚴格依 `config.timeframe_ms` 遞增連續，禁止重複時間戳、倒序或缺口；不自動補值或插值。
5. **資料長度**：至少包含一根正式評估 K 線；空檔或僅有表頭將拒絕。

## 錯誤劃分

- **CSV 結構與文字解析錯誤**：標示具體行號與欄位（如 `row 2, column 'open': invalid decimal 'abc'`、`row 3: expected 6 columns, got 5`）。
- **核心市場資料驗證錯誤**：直接保留核心驗證訊息（如 `open must be a multiple of 0.25`、`candles must be ordered and contiguous; gaps are not filled`）。

## 使用範例

```python
from decimal import Decimal
from catos.data_io import load_candles_csv
from catos.research import BacktestConfig, ContractSpec, backtest

config = BacktestConfig(
    contract=ContractSpec("BTC-USDT-SWAP", Decimal("0.01"), Decimal("0.25"), Decimal("1"), Decimal("1")),
    timeframe_ms=900_000,
    initial_balance=Decimal("10000"),
    fee_rate=Decimal("0.0005"),
    slippage_bps=Decimal("1"),
    funding_events=(),
)

candles = load_candles_csv("data/btc_15m.csv", config=config)
result = backtest(strategy=MyStrategy, candles=candles, config=config, warmup_bars=10)
```

## 本切片界線

僅使用 Python 標準函式庫。不包含行情下載、自動網路請求、未收盤 K 線撮合、1m 歷史重播或猜測合約規格。
