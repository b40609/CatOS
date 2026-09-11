# 任務 C：研究命令列入口

狀態：已交付並經 Codex 審查修正，15 個專屬測試通過；使用者後續授權的全域 69 個測試亦通過，納入本輪提交。以下保留為規格紀錄，不再派送重做。

使用者已同意由 Antigravity 實作，Codex 負責交付審查。先讀 AGENTS.md、README.md、本檔；A、B 已驗收，不重做。使用同一本地專案，不自行 pull、reset、commit 或 push。

## 目的與最小範圍

目前更換 CSV、回測設定及報告路徑需要編輯 Python 示範。新增標準函式庫 argparse 入口，串接既有 CSV loader、backtest、render_report，讓使用者一條命令完成本機研究。只提供既有 SMATrend 示範策略，固定以明示名稱選取，不新增動態模組載入、策略框架或 Optuna 命令。

僅可新增：`catos/research_cli.py`、`tests/test_research_cli.py`、`docs/research-cli.md`、`examples/research-config.json`。所有修改用 Patch。不修改既有核心、CSV、報告、策略、測試、依賴、架構或 AGENTS.md。若需要修改既有介面，回報具體原因交回 Codex，不擅自擴充。

## 命令契約

```powershell
py -3 -B -m catos.research_cli --csv reports/visual-qa/synthetic.csv --config examples/research-config.json --strategy sma-trend --output reports/research.html
```

提供 `main(argv: list[str] | None = None) -> int`，模組入口 `raise SystemExit(main())`。四個選項均必填，策略 choices 僅 `sma-trend`，直接映射 `examples.closed_bar_demo.SMATrend`（既有固定兩根 SMA、目標兩張／空倉；文件明示此限制，不改其交易邏輯）。所有命令列路徑相對目前工作目錄解讀，不自動下載或猜測輸入檔。

成功回傳 0，stdout 顯示輸出路徑與合成／歷史來源由使用者負責的研究邊界；預期輸入、設定、I/O 或回測驗證錯誤回傳 2 並寫入 stderr，不輸出成功訊息。argparse 的 help／參數錯誤可保留其標準 SystemExit 行為。不吞掉 KeyboardInterrupt 或未預期程式錯誤，不新增重試。

## JSON 設定

設定為 UTF-8（允許 BOM）物件，欄位全部必填；各層拒絕未知、缺漏及重複鍵。JSON 金融數值必須使用字串，直接建立 Decimal，不透過 float；整數欄位只接受真正 JSON 整數，拒絕 bool、小數及字串。拒絕 JSON NaN／Infinity；文字 Decimal 的有限性與範圍沿用核心驗證，解析錯誤應指出設定欄位。不受呼叫端 Decimal trap 設定影響。

`examples/research-config.json` 使用以下內容（明示範例，非交易所 metadata）：

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

`funding_events` 必须明示陣列，每個事件欄位恰為 `time_ms`（整數）、`rate`、`mark_price`（Decimal 字串）。空陣列代表使用者假設無資金費，不代表完整歷史。依原樣轉為 FundingEvent tuple，不排序、不填補。除 warmup_bars 外建立 BacktestConfig；warmup_bars 另傳 backtest，必須為非負整數。合約／價格／費用／事件及 K 線合法性重用現有 loader／backtest，不另建帳務驗證器。

## 輸出與失敗情境

具體風險是誤覆蓋原始 CSV、設定或既有報告。最小做法：輸出副檔名限制 `.html`（大小寫皆可），先檢查輸出不可與輸入解析後路徑相同，拒絕已存在的輸出，不提供 overwrite／force。完成讀取、驗證、回測及 render 後才寫檔；以 UTF-8 的獨佔建立模式 `x` 寫入，避免檢查後出現檔案而被覆蓋。可建立不存在的父目錄。

若寫入失敗，僅清理本次成功獨佔建立但尚未完成的報告，不刪其他檔案或目錄；驗證失敗不應產生報告。這是研究報告的基本覆蓋保護，不承諾斷電原子持久化，不引入另一套持久化框架。

無連網、無憑證、無交易所、無 SQLite、無背景服務；CLI 只是研究呼叫端，不宣稱已實作 Supervisor／Worker。所有交易、費用、績效維持原核心規則。

## 等比驗收

新增專屬測試並使用 TemporaryDirectory 合成資料：

- 正常命令串接 CSV → 回測 → HTML，確認實際績效與明細來自核心；至少一次 subprocess 驗證模組命令入口、退出碼及輸出檔。
- 設定 BOM、Decimal 精度、非空資金費事件；warmup_bars 生效且不保留預熱交易意圖。
- 缺漏／未知／重複鍵（含巢狀）、金融 JSON 數字、NaN／Infinity、bool 整數、負預熱、無效 Decimal／合約設定、未知策略均拒絕。
- 不存在的 CSV／設定、未收盤或缺口 CSV，不產生成功報告；錯誤包含可理解的欄位或原因。
- 既有報告及輸入路徑不被覆蓋；父目錄建立；mock 寫入失敗與獨佔建立競爭，確認清理只影響本次新建的半成品。
- `--help` 與預期錯誤的退出行為。不要複製整套核心測試。

只執行 `py -3 -B -m unittest discover -s tests -p test_research_cli.py -v`，不跑全域套件或真實市場回測。文件提供上述命令、先用 `py -3 -B -m examples.report_demo` 產生合成 CSV 的步驟、JSON 契約、固定策略限制及退出碼。

完成後回報修改檔案、功能、實際命令與測試結果、未完成項目；停止並交回 Codex。不得降低斷言或擴充下一階段。
