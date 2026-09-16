# 2026-09-16 專案檢查與下一步建議

本輪為靜態檢查與規劃，不是實作或重新驗收。檢查範圍為專案約定、架構與交接文件、已存驗證紀錄，以及研究入口、IPC、ownership、執行、風控與 P6 的相關程式接縫；未逐行審查全部模組。未執行測試、讀取憑證、連接 OKX 或變更帳戶／交易資料庫。

## 1. 目前狀態

| 範圍 | 核對結果 |
|---|---|
| 研究 | 已有 Closed Bar Decimal 核心、CSV、HTML 報告與 Optuna；仍有獨立修補事項 |
| 本機模擬 | 已有 Worker、IPC v1、SQLite Journal、風控、FakeExchange、UNKNOWN／重啟對帳及 P6 模擬 |
| 執行限制 | `ipc.VERSION=1`；ownership 以合約為主鍵、Bot 唯一；執行按 owner 淨倉更新；日損預設仍為 10%／20% |
| Demo 唯讀 | 已有採集與解碼，但最新帳戶交接仍為 `reconciled=false`、`trade_authorized=false`；舊採集授權已結束 |
| S1 | `outputs/catos-s1-lots-ipc-spec.md` 已存；四個目標實作／測試檔尚不存在 |
| 驗證證據 | 2026-09-15 兩輪定向驗證紀錄合計 16 模組、232 項通過；不是本輪重跑或全專案驗收 |

證據：`outputs/catos-regression-2026-09-15.txt`、`outputs/catos-research-tests-2026-09-15.txt`。README 與 WORK_PLAN 頂部仍標示修補尚未驗證，應補上後續驗證索引及剩餘限制，保留原歷史紀錄。

## 2. 推薦的下一片：S1 純資料模型與 IPC v2

S1 已有足夠具體的介面與驗收矩陣，適合作為下一個新增功能切片。它先解決多 Lot 的身份、數量、歸屬與意圖表達，交付物可獨立驗證，且不依賴 Demo 對帳完成。

現有淨倉執行器不能直接套用：例如多空 Lot 互抵時，關閉某個本地多 Lot 可能需要增加交易所空頭。直接解除 ownership 或把 CLOSE_LOT 轉成舊 target，會破壞執行與風控語義。

### 2.1 開工時同步文件邊界

現有規則尚有衝突：

- `AGENTS.md:41` 與架構文件第 13、15 節維持 P8 延後；S1 規格第 1.1 節卻記載已改變研發方向。
- S1 規格第 12 節記載來源工作區為 `CatOS_Astra - 複製`，不可直接把其行號與基線當成目前工作區的驗收證據。

建議在使用者選定 S1 開發時，將規則同步為：「允許隔離的 Lot 領域與 IPC v2 資料契約研發；現行 v1 執行仍維持單合約單 Bot、cross＋net_mode，不建立或接入虛擬帳本／分配器。」這是待採用的具體文字，本規劃不自行覆寫既有政策，也不把規格文件當成交易或遷移授權。

日損 3%／5%、long_short_mode、P6 多 Bot 相容與保證金分配都不需要在 S1 定案；現行值及執行模式保留。

### 2.2 實作順序與交付物

| 順序 | 目標檔案 | 交付內容 |
|---|---|---|
| 1 | `catos/lots.py` | frozen／slots 類型；LotScope、LotProtection、Lot 快照；OPEN／CLOSE／UPDATE 意圖；父側上下文與 view 校驗；穩定 SHA256 身份及錯誤碼 |
| 2 | `tests/test_lots.py` | 規格 L01–L24：多 Bot／多方向表示、不可變、Decimal、數量步長、碎量全平、歸屬、revision、未決責任、Lot ID 綁定、warmup |
| 3 | `catos/ipc_lots.py` | 獨立 v2 lot_intents 訊息；嚴格欄位、Decimal 字串、快照往返、canonical_intent；沿用既有 framing 與嚴格 JSON |
| 4 | `tests/test_ipc_lots.py` | 規格 P01–P20：雙向編解碼、身份注入、版本隔離、warmup、重複鍵、截斷／超限、canonical 數值一致性及 null 語義 |

以上 44 項是規格覆蓋點，不是預先承諾的測試函式數量或通過數。只使用標準函式庫及既有 research／ipc 基礎。

### 2.3 實作時必須處理的細節

- `ContractSpec` 本身沒有建構時驗證，不能僅做 isinstance；應驗證 USDT-SWAP 標識、正數規格及 min_size／lot_size 關係。
- `ipc.decimal_text(..., derived=True)` 不執行 positive 檢查；快照均價等欄位須另外明確驗證正負。
- 派生值的允許範圍比意圖輸入寬；步長整倍數校驗須覆蓋邊界與低精度外部 context，不能把可解碼等同所有後續 Decimal 運算必然可行。運算超出能力時需有明確錯誤，不得捨入後誤收。
- CLOSE／UPDATE 必須比較請求 lot_id 與傳入快照 lot_id；相同 Bot、合約和 revision 不能代替此檢查。
- 全平 null、明確數量和未知 funding 必須保留各自語義；canonical 先驗證範圍再去尾零。
- 穩定 ID 不依賴 generation 或時鐘；它不等同持久化去重。ValidatedLotIntent 也不代表風控或交易批准。

### 2.4 隔離與驗收出口

S1 不接 Worker 主迴圈、Supervisor、SQLite、成交結算、風控預留、TP／SL 監控或交易。`ipc.VERSION`、舊策略 target 介面、ownership、日損預設、latch、P6 及 tag 出口均維持原行為。

依既有分工，由開發模型交付程式／測試，再由驗證模型使用已授權的 Python 絕對路徑執行：

```text
<python> -B -m unittest discover -s tests -p "test_lots.py" -v
<python> -B -m unittest discover -s tests -p "test_ipc_lots.py" -v
<python> -B -m unittest discover -s tests -p "test_ipc.py" -v
```

確認兩個新模組確實被發現，0 tests 不算通過；回報實際執行／失敗／錯誤／跳過數。靜態確認既有執行入口沒有 import 或呼叫新模組。若共享程式未改動，驗證止於上述範圍，不擴成全域測試或歷史市場回測。

完成條件：四個檔案完成、規格覆蓋點可追溯、三個測試模組通過、未接入執行流程。完成即交付，不接著實作帳本或 Demo。

## 3. 已有問題另列修補

已存驗證紀錄揭露的問題仍有對應程式路徑，本輪未動態重現，也未修復：

| 問題 | 目前程式接縫 | 建議最小處理 |
|---|---|---|
| 異常輸出清理的 stat／unlink 競態 | `catos/cli.py:151`、`catos/research_cli.py:261` | 專門決定失敗檔保留／清理契約，補檔案替換競態測試；不要宣稱現有身份比較能原子保護刪除 |
| 任意 symbol 搭配預設 BTC CSV | `catos/optuna_study.py:93`、`:205` | 明示 CSV 來源，移除容易誤用的預設；資料來源與 symbol 的綁定驗證另須明確契約 |
| 搜尋策略固定數量 2 | `catos/optuna_study.py:39` | 明示數量並在搜尋前驗證 lot_size／min_size，相依測試同步更新 |
| trial 全失敗仍可能 exit 0 | `catos/optuna_study.py:229` | 定義無成功 trial 的命令列失敗狀態，補最小回歸 |

這些問題不在 S1 的直接依賴路徑；可單獨安排小修補，且應在再次把上述研究入口用於實際研究前處理。P5／P6 全增倉入口的專項驗證、P6 TRIGGERED 結案與真實帳戶對帳仍保留各自邊界，不因 S1 完成而宣稱解決。

## 4. S1 之後

獨立驗收完成後，先定案交易所模式、Lot 減倉與交易所曝險關係、P6 聚合保護及日損是否遷移；之後才規劃同 writer 的 Lot 持久化／收據重放、成交歸屬、Gross 與實體曝險檢查，以及本地保護與展示。這些是後續順序，不是本輪新增工作。
