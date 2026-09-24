# catOSv1 dedicated Demo evidence slice

## 2026-09-23 帳戶模式調整後的最新結果

使用者表示已自行改為合約模式；沿用已授權的 Demo private read-only bounded GET，執行一次完整窄範圍 evidence slice。`account/config` 的 expected UID、`uid != mainUid`、`net_mode`、acctLv 2／3 契約、權限與角色全數 **PASS**。帳戶範圍 `positions` 0 筆、`orders-pending` 0 筆、七組 `orders-algo-pending` 合計 0 筆；全部 10 次 GET 接受，沒有 POST 或帳戶設定修改。此為查詢當下的序列觀測，不能證明跨端點原子快照、歷史責任或本地 UNKNOWN 已清除。既有 trading DB／本地責任帳本未讀；`reconciled=false`、`trade_authorized=false`。見[去識別化證據](../outputs/demo-subaccount-remote-responsibility-evidence-20260923.json)。本輪未更動採集程式或重跑測試；先前 21/21 只代表前輪程式驗證。

此結果取代下方 `acctLv=1`、舊 key 身分不符與來源缺失作為「目前」blocker 的敘述。下一步若需正式 reconciliation，須核對該子帳戶的本地 UNKNOWN／歸因、完整帳務與 D1-A verified E₀；本次空遠端責任不能直接解除交易 gate。

## 2026-09-23 更新後 Demo key 的最新結果

使用者指明更新後來源為 `C:/Users/user/Desktop/OKX_API.txt`。檔案同時含 Live 與 Demo 區塊；獨立採集器依明示 Demo 標題選出唯一一組 Demo credential，不從 Live 區塊取 key、不輸出金鑰。新 Demo key 經 `account/config` GET 驗證：指定 UID **PASS**、`uid != mainUid` **PASS**、`net_mode` **PASS**、權限／角色 **PASS**；`acctLv=1`，CatOS 要求 2 或 3，故帳戶模式 **FAIL**。另一次 config-only GET 只確認模式代碼。本輪共 **2 次 private GET**，皆為 account/config；mode gate 後停止，foreign position／ordinary order／algo 及本地 UNKNOWN 仍未驗證。見 [最新去識別化證據](../outputs/demo-subaccount-config-evidence-20260923-updated-key.json)。先前舊 key 的主帳戶結果及舊路徑缺失紀錄均為歷史，不代表更新後 key。

使用者需自行將 Demo 子帳戶調整至 CatOS 契約相容的帳戶模式；本輪沒有帳戶設定修改授權。若自行調整後再接續既有有界 GET，身分與模式 gate 通過才會查遠端責任。獨立工具新增雙區塊明示 Demo 選擇，合成測試與既有採集測試 **21/21 OK**。

## 2026-09-23 新 Demo key 路徑再試

使用者表示已將新 Demo key 更新至 `C:/Users/user/Desktop/OKX/_API.txt`，並澄清先前提供的 key 是 catOSv1 Live key。已將獨立採集器指定路徑切回該路徑並執行一次；本機檢查該檔案及父目錄均不存在，credential loader 固定回傳 `credential_setup_failed`，**0 次 GET**。未讀新 key、未對新 key 驗證 UID／模式／責任。舊路徑 `C:/Users/user/Desktop/OKX_API.txt` 仍存在，但本機修改時間為 2026-09-09；本輪未讀該舊檔，也沒有從其結果推論新 key 身分。等待檔案實際出現在指定路徑後續跑；同一 credential／GET 授權有效。

2026-09-23，本輪使用者明確授權指定 credential file 與 Demo private read-only bounded GET；本輪直接執行優先於舊 Astra／Sol 採集分工及歷史禁止採集敘述。授權不含任何 POST、交易、撤單、帳戶修改、既有 DB/schema 寫入或 Git mutation。

## 本次結果

### 使用者更正來源後的後續執行（取代來源缺失 blocker）

使用者提供 `C:/Users/user/Desktop/OKX_API.txt`，與先前不存在的 `C:/Users/user/Desktop/OKX/_API.txt` 不同。本輪僅更正獨立 evidence 工具的指定路徑，沿用已授權 credential／GET，不輸出檔案內容或 UID。實際執行一次，完成 **1 次 account/config GET**：expected UID **FAIL**、dedicated subaccount **FAIL**；net_mode、acctLv 2／3 契約、權限與角色檢查 **PASS**。身分 gate 停止後續所有查詢；positions／ordinary orders／algos 未執行，local UNKNOWN 未核對。新證據見 [config evidence](../outputs/demo-subaccount-config-evidence-20260923.json)。先前 0 GET 記錄只代表上一輪失敗嘗試。

目前 blocker 改為：指定來源所選 credential 未通過預期專用子帳戶 identity，需改用 catOSv1 對應 credential；不再稱檔案不存在或 GET 未授權。本轮只有指定路徑變更，未重跑上輪 20 案測試；上輪測試仍只代表上輪結果。

使用者質疑 19 unknown 屬過度工程。已核對 `catos/reconciliation_gate.py` 的 `flow_classification_complete` 全目錄阻擋確實存在，與 `unknown_flow_count` 實際流水阻擋分開。提出縮減方案（**尚未定案、未改 gate**）：保留既有分類；全目錄 166/185 僅為資訊，不再要求先補完 19 類；只有實際採集到 unknown／forbidden 流水才阻擋增倉並告警，合法減倉維持既有路徑。原保證是全目錄分類完整才放行；建議改成完整採集範圍內的實際流水全部可分類才放行，不再保證預先支援每一種 OKX 業務。這不代表把未知金額當零，也不取消成交損益、手續費與資金費的既有帳務處理；入出金及反佣仍須按既有已證實類型處理。最小驗證為：未出現 unknown 可過此分類條件、實際 unknown／forbidden 仍阻擋、採集不完整仍阻擋；其他 identity／E₀／責任 gate 保留。待使用者定案後實作，不再以研究完全部 subtype 作唯一下一步。

### 前次來源缺失紀錄

- 指定來源 `C:/Users/user/Desktop/OKX/_API.txt` 的 `is_file()` 為 false；未讀到 credential 內容，未搜尋其他來源或環境變數。
- 已實際執行 `python -B -m tools.demo_subaccount_evidence --execute-authorized`，回傳固定 `credential_setup_failed`；private GET **0 次**。後續只檢查同一路徑存在性，確認來源缺失，不是 credential／GET 未授權。
- expected UID、uid != mainUid、net_mode、acctLv 契約、遠端 position／ordinary order／algo 均 **未驗證**，不能寫成 pass 或帳戶設定錯誤。UID 只在執行程式比對；一般輸出與本證據不含 UID。
- local UNKNOWN 未核對：本輪未讀既有 trading DB／責任帳本，遠端空集合也不能解除本地 UNKNOWN、ownership 或 latch。`reconciled=false`、`trade_authorized=false`。
- 去識別化結果：[evidence JSON](../outputs/demo-subaccount-evidence-20260923.json)。

## 最小採集邊界與驗證

新增 `tools/demo_subaccount_evidence.py`，沿用既有安全 credential loader、簽名與僅 GET 的 HTTPS sender，不改舊主帳戶入口或 production gate。僅在 explicit execute flag 下讀指定來源；設定驗證先行，失敗即停止。帳戶契約沿用 `net_mode`、acctLv 2／3、既有權限與角色檢查。

最多 10 次 GET、無 retry、每次 10 秒、總預算 120 秒、每回應最多 2 MB。查 account/config、account-wide positions、orders-pending，以及既有七組 algo ordType（conditional/oco、trigger、move_order_stop、iceberg、twap、chase、smart_iceberg），不加 instId/instType 過濾。單頁非空即否決空帳戶檢查，無須列舉全部責任；空頁才提供該查詢當下的空集合證據。任何 API／partition 錯誤保持 incomplete；零部位紀錄亦保守視為非空，不宣稱已證明 foreign ownership。跨端點序列快照不是原子快照；本工具不涵蓋額外 trading-bot 家族或歷史 responsibility 重建，也不替代正式 reconciliation。空倉帳戶的 cross 執行模式無法由 acctLv 單獨證明。

本輪 `python -B -m unittest tests.test_demo_subaccount_evidence tests.test_demo_collection -v` **20/20 OK**，其中新測試 4 案：錯誤 UID／主帳戶停止、非 SWAP 責任不被過濾、algo 分支錯誤不誤判空、空遠端仍保留 local UNKNOWN。皆為 synthetic，沒有把測試當實際帳戶驗證。

本輪直接重算既有 local catalog 與 current mapping：classification **166/185**，external 10、internal 102、forbidden 54、unknown 19，`complete=false`；未重新採集 catalog，未修改分類。

## 剩餘 blocker／接續

1. 指定 credential file 不存在；待使用者將檔案放回原位置或指定更正路徑。既有 credential／GET 授權不需重問。
2. 即使 remote checks 通過，本地 UNKNOWN／ownership 仍須正式、與該子帳戶綁定的責任證據，不得以空本地集合假設解除。
3. production classification 19 unknown、D1-A exact-midnight E₀ source/producer 缺口及真正 Demo write 未授權仍保留。

未修改既有交易 DB/schema、Yaozi／Lot／market；未 reset／clean／commit／push，未核對 Git 狀態。先前安全策略閉環與其他驗收不重跑。
