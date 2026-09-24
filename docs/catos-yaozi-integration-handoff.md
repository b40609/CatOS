# Yaozi 最小功能整合：Astra 交驗

2026-09-23。狀態：Yaozi 程式與來源測試已整合，Sol 最小驗收 **PASS**；同日後續已完成統一量化／情報頂層 shell 的 local-sim 驗收，詳見 [統一 shell handoff](catos-unified-shell-handoff-20260923.md)。

## 2026-09-23 Social V9 follow-up

使用者已明確授權在 Astra 額度冷卻期間直接完成後續整合。本輪依 `CatOS_Yaozi/docs/yaozi-astra-v9-integration-manifest-20260923.json` 對 Astra 套用 contextual patch，沒有整檔覆蓋共同工作、沒有修改 Yaozi 工作樹，也沒有建立 runtime cross-worktree import。

- `catos/market_social.py`：由 V5 續接 V6–V9；current alias 固定 V9，新增 `current_social_identity_registry()` 與 `collect_current_coinpaprika_mapping()`。explicit identities 共 34 筆。
- `catos/market_api.py`：`/intel/social` 增加唯讀 `identity_registry`；raw counts、`social_heat=null`、`yaozi_heat=null`、ranking 未物化語意保持不變。
- `catos/market_dashboard.py`：Social 頁顯示 `registry=v9`、34 identities 與 baseline-derived coverage；identity readiness 與 materialized raw metrics 分開呈現。
- `tests/test_market_social.py`：帶回 V6–V9 registry fail-closed cases；新增 `tests/test_yaozi_social_runtime_sync.py` 驗證 current runtime entrypoint 與 Web observable state。
- `outputs/yaozi-social-explicit-identity-registry-v5-20260923.json` 至 V9 一併帶回，讓 V9 runtime `evidence_path` 在 Astra 本地可解析；這些是靜態 evidence，不是新 live 採集。

V9 coverage 為 `34 resolved / 242 ambiguous_mapping / 291 unverified_identity / 167 missing_asset = 734`，明確沿用 Yaozi 的 baseline-derived 語意，不宣稱為 2026-09-23 完整 live distribution。AAVE `ambiguous_metric`、缺 numeric stats 不補 0、ticker-only mapping 禁止等 fail-closed 規則維持。

本輪驗證：5 個程式／測試檔正規化換行後與 Yaozi V9 source 完全相同；`tests.test_yaozi_social_runtime_sync + tests.test_market_social` 25/25 OK；既有 Social Dashboard/API regression 1/1 OK；`py_compile` OK。Astra synthetic schema-14 temp DB 的 `/intel/social` 回 `registry=v9`、34 identities、上述 coverage，且 `items=0`、`source_runs=0`、heat 均為 null；Crawl4AI 實際渲染成功，只有 favicon 404。詳見 [V9 manifest](yaozi-v9-integration-manifest-20260923.json) 與 `outputs/yaozi-v9-astra-integration-verification-20260923.json`。

本 follow-up 未寫 project DB、未改 schema、system watchlist、Decision Compare 排序、scoring、交易核心、風控、Supervisor 或策略生命週期；未 commit／push。Astra `main @ 3925759` 與既有 dirty work 保留。

## 來源與範圍

依使用者轉交的 Sol 核對結果，採 `C:/Users/user/Desktop/CatOS_Yaozi` 現行工作樹，包含未提交成果；branch `yaozi/dev-v0.7`／HEAD `a4fb910` 僅為 Sol 提供的基線資訊，本輪未重新執行 Git。來源內容以 [逐檔 manifest](yaozi-integration-manifest-20260923.json) 的 SHA-256 固定。

本片新增 1 個 runtime 檔，對 7 個既有檔案套用有上下文的區段補丁；保留共同區段，不以整檔複製取代 Dashboard。這 8 個檔案正規化 CRLF/LF 後與來源相同；合併後重新讀取來源雜湊，8 個來源檔皆未變動。這只是檔案比對證據，不是程式測試。

| 檔案 | 帶回內容 |
|---|---|
| `catos/market_decision.py` | 已保存市場事實的唯讀 decision surface、symbol decision、compare 聚合；不授予交易權限 |
| `catos/market_api.py` | Reader 的三個聚合方法與三個 `/intel/decision-*` GET 路由 |
| `catos/market_dashboard.py` | Decision 摘要、Today server 排序、trace、Compare filter、單幣 drill-down、Personal watchlist、Push、Whistle、Social、Account / Local |
| `catos/market_social.py` | explicit identity registry V1–V5，仍需呼叫端明示提供，不新增 ticker 自動對應或採集 |
| `catos/market_lifecycle.py` | 僅補 SMF -20 歸 B 是本地相容慣例、非原站等價證明的註解 |
| `tests/test_market_api.py` | decision 方向、缺資料、衝突、排序、時間差、路由與既有 Dashboard surface 契約測試 |
| `tests/test_market_social.py` | registry V1–V5、未提供 explicit identity 仍拒絕，以及 ambiguous metric 測試 |
| `tests/test_market_signals.py` | MOMENTUM ±10% 邊界、24h 來源與 PURE_MOMENTUM 區分測試 |

SMF 註解引用的 [v1.11 歷史說明](yaozi-v1.11-handoff.md) 一併帶回；文件內「本輪」及觀察結果皆屬 Yaozi 歷史紀錄，本輪未連網重驗。Social identity 證據仍保留在來源目錄的 `outputs/yaozi-social-explicit-identity-registry*-20260922.json` 及 `outputs/yaozi-social-explicit-identity-registry-v5-20260923.json`；這些不是執行期依賴，本片不重新認證供應商資料。

## Dashboard 區段處理

1. 擴充樣式、導覽、狀態與 browser-local watchlist；保留既有資訊頁樣式與控制項。
2. Today 改讀 server decision 排序與方向，原 lifecycle 只作上下文；保留持有週期、資金流、訊號等既有呈現。
3. 單幣既有 Dealer／資金流／流動性／K 線保留，補 decision 與觀察清單操作；帶回 Push／Whistle／Social／Account 頁面。
4. 接入 view 載入與 Compare／單幣 URL 狀態；不新增量化頂層 shell、不改根路由、不啟停 Supervisor。

現有分頁字串斷言不是瀏覽器互動驗收。未把來源既有測試通過數字當成本輪結果，也未因有 Account 頁而宣稱會員、登入、通知送達或已讀功能完成。

## Sol 最小驗收

從 Astra 目錄執行既有三個受影響測試模組（只用測試建立的臨時 synthetic DB）：

```powershell
$env:PYTHONPATH=".;tests"
python -m unittest test_market_api test_market_social test_market_signals -v
```

另外以隔離的 schema-14 synthetic 情報 DB 做最小瀏覽器驗收：Today 決策與 Compare 排序／filter、單幣資訊、觀察清單加入／移除及重載、四個 member-shell 導覽與缺資料呈現。啟動只綁 `127.0.0.1`；不得直接使用 CLI 預設 outputs DB 代替 fixture。不得把這次情報頁 QA 當作量化策略不中斷的驗證。

### 2026-09-23 驗收結果

- Git／來源核對：`CatOS_Yaozi` 仍為 branch `yaozi/dev-v0.7`、HEAD `a4fb910d2b8e6de6aaf0a40a9c0d3a716873cab6`、merge-base `3925759d16771b9cbe8fac709c0b5dc355772865`。8 個整合檔以 CRLF/LF 正規化後，Astra 目標、Yaozi 來源及 manifest SHA-256 全數一致，0 mismatch。
- 專屬測試：`python -m unittest test_market_api test_market_social test_market_signals -v` 實跑 79 tests，全部通過，耗時約 6.1 秒。
- Browser QA：以隔離 schema-14 synthetic DB 啟動 `127.0.0.1` localhost 服務；另加入既有 multi-symbol synthetic fixture 驗證 Compare。實際順序為 ETH → SOL → BTC → XRP → ADA，rank #1 → #5；偏空 filter 僅保留 ETH，URL 保存 `dcfilter=bearish`。
- 單幣頁：BTC drill-down 正常顯示 Decision 與已物化 closed K 線；ETH 正常顯示 bearish Decision，K 線／liquidity 缺資料維持 explicit missing／not materialized，不虛構資料。
- Personal watchlist：ETH 加入後 localStorage 保存 canonical symbol，reload 後仍存在；移除後 reload 仍為空，Personal 頁同步更新。
- Member shell：Account 頁四個本機 action `personal`／`pushes`／`whistle`／`social` 均可導覽；其餘 6 個 `not_materialized` capability 保持 disabled。Push／Whistle／Social 只讀頁皆可載入，缺資料狀態照契約呈現。
- 驗收期間未讀憑證、未連外採集、未使用產品預設 DB、未修改既有 DB 或 schema、未碰交易／Lot、未 commit／push。

本片驗收已完成；不得把這次情報頁 Browser QA 宣稱為量化策略不中斷、交易生命週期或統一網站驗收。

## 保留與後續

- 37 個僅換行差異檔與 2 個相同檔保持原樣。
- 其餘 12 個 Yaozi-only capture／ground-truth／audit／report tools/tests 本片未帶回；它們不在本片 decision runtime 的 import 路徑，另片需要時再連同資料證據整合，不把本片描述成全部 Yaozi 成果合併完成。
- 不改 Yaozi 工作目錄及其接續入口；不動 Astra Demo 額度決策、授權審查、Lot 與其他未提交工作。
- 本段屬原 Yaozi 最小整合片的歷史狀態；後續統一 shell 已完成。量化頁目前仍是唯讀 backend status projection，不新增未核准的交易操作。
- 下一步以 `docs/current-handoff.md` 的最新主線為準；需要切換角色時先讀本文件與入口，不重跑 live 採集、不直接升級主庫。

## 2026-09-23 統一 localhost shell follow-up

- `catos/app_shell.py`：新增單一產品 shell 與唯讀 quant surface；頂層分頁固定為「量化交易／Yaozi 情報」。
- `catos/market_api.py`：root `/` 改為 shell；`/dashboard` 保留既有 Yaozi Dashboard；新增 GET `/quant` 與 GET `/system/strategy-status`。`create_app()` 僅新增可選 `strategy_status_provider` dependency injection，沒有 global Supervisor singleton。
- `supervisor_status_provider()` 只讀現有 LocalSupervisor 的 health、bot、revision、event seq、worker 狀態、halts、failure；不持有交易權限，不呼叫 lifecycle mutation。
- `tests/test_app_shell.py` 使用 temporary market DB + temporary Supervisor DB。Supervisor 先 reconcile 並處理 event 1；Web root／quant／dashboard／status 與重複 root request 後 revision／checkpoint 不變，Web client teardown 後同一 Supervisor 成功處理 event 2。
- 受影響測試 `tests.test_app_shell + tests.test_yaozi_social_runtime_sync + tests.test_market_api` 44/44 OK；`py_compile` OK。
- Browser QA：Crawl4AI 對 `/quant`、`/dashboard` 實際 render 成功；root shell 亦抓到兩個頂層分頁。`browser-use` 因本機 Chrome/CDP launch failure 無法完成互動 runner，未視為應用失敗；功能互動與 lifecycle independence 由專屬測試覆蓋。
- 沒有 project DB/schema write、沒有真實憑證、沒有 Demo／Live network、沒有交易／risk／Lot mutation、沒有修改 `CatOS_Yaozi`，沒有 commit／push。

證據：`outputs/catos-unified-shell-verification-20260923.json`。
