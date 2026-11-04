# catOS／Yaozi 單一介面整合契約

2026-09-23。使用者已同意保留兩個開發目錄，最終將 Yaozi 功能整合為 catOS 內的分頁；不要求使用者另開網站。此文件固定交付方向與分工，不宣稱已完成程式合併或 Web 整合。

## 已確認的產品方向

- 最終使用同一個 localhost 網站與頂層導覽，提供「量化交易」與「Yaozi 情報」分頁。
- 切換分頁、重新整理或關閉瀏覽器不得成為策略啟停指令；策略生命週期由後端管理，明確操作才改變執行狀態。2026-09-23 統一 shell follow-up 已用 real local-sim `LocalSupervisor` 驗證 Web requests／reload 模擬／client teardown 不改變 lifecycle；Web start/stop contract 仍未物化。
- Yaozi 是可選情報模組；缺資料或模組不可用時要明示狀態，不妨礙量化核心自身運作。第一個安全策略閉環仍為主線。
- 本契約取代「兩個開發目錄表示兩個獨立交付網站」的理解。既有 v0.1 文件仍提供歷史範圍與待驗事項，不能用它否認 Yaozi 工作目錄後續成果，也不能將後續成果視為已合入 Astra。

## 開發目錄與所有權

| 目錄 | 責任 |
|---|---|
| `CatOS` | 交易核心、風控、Supervisor、最終應用整合與主交接入口 |
| `CatOS_Yaozi` | Yaozi 情報功能、畫面、專屬測試與該線交接 |

保留現有 worktree，不搬移、不刪除、不建立第二份儲存庫。兩邊檔案不自動同步；同一功能只指定一條開發線修改，整合時按固定交付版本逐項帶回。不得以目錄整包覆蓋或執行期跨目錄 import 代替整合。最終啟動不應依賴兄弟目錄 `CatOS_Yaozi` 存在。

Astra 負責方案與程式，Sol 負責 Git 核對、驗收及 Git 操作；本次同意不新增 commit／push 授權。其他進行中的交易、Lot 與 Yaozi 未提交工作都保留，不混入本文件切片。

## 本輪靜態盤點

- Yaozi 的 `.git` 指向 Astra 的 `.git/worktrees/CatOS_Yaozi`；建立紀錄為 2026-09-21 23:23:11（UTC+08:00）。
- Astra 仍有 `catos/market_dashboard.py`、`market_api.py`、情報模組、測試及 outputs；不是已清空 Yaozi 的目錄。
- `market_dashboard.py`、`market_api.py`、`market_social.py` 的兩邊檔案雜湊不同，不能直接互相覆蓋。
- 現有 `market_api.create_app(db_path)` 建立情報 FastAPI，`/` 與 `/dashboard` 顯示情報畫面，前端呼叫同源 `/intel/...`；`serve` 限制 `127.0.0.1`，預設埠 8765。
- 在 Astra 的 `catos` 程式掃描中，沒有找到另一個量化管理 FastAPI／Web 入口；不能只新增空白量化分頁就宣稱完成整合。
- 兩邊情報儲存程式宣告 schema 14；既有文件記載曾有 v12 主庫。本輪未開啟資料庫，實際版本與可讀性尚未核對。
- Yaozi 入口記載後續功能與未提交內容；屬來源文件敘述，本輪未做 Git 狀態核對或重跑其測試。

## 2026-09-23 Sol 核對：固定整合來源與差異清單

Sol 已依兩邊實際工作樹完成只讀核對。`CatOS_Yaozi` 目前為 branch `yaozi/dev-v0.7`、HEAD `a4fb910d2b8e6de6aaf0a40a9c0d3a716873cab6`；與 Astra `main` HEAD `3925759d16771b9cbe8fac709c0b5dc355772865` 的 merge-base 即 `3925759d16771b9cbe8fac709c0b5dc355772865`。Yaozi 的 v1.5–v1.26 成果包含大量未提交內容，因此後續整合來源固定為 **`C:/Users/user/Desktop/CatOS_Yaozi` 現行工作樹**，不能只取 `a4fb910`，也不能把 Astra 既有同名檔視為新版來源。沒有 commit／push 授權，整合前仍須再次核對 Yaozi Git status，保留全部未提交內容。

以 `catos/market_*.py`、`catos/yaozi_surface_lifecycle.py`、`tests/test_market_*.py`、`tests/test_yaozi_*.py`、`tools/yaozi_*.py` 為整合來源範圍，並正規化 CRLF/LF 後比對：7 個同名檔存在實質內容差異、13 個檔案僅 Yaozi 存在、37 個檔案只有換行格式差異、2 個檔案內容完全相同。換行差異不列為功能整合項，不應為此批次覆寫檔案。

同名且有實質差異的 7 個檔案：

- `catos/market_api.py`：Yaozi 增加 decision surface／symbol decision／decision compare 聚合與 `/intel/decision-surface`、`/intel/decision-surface/{symbol}`、`/intel/decision-compare` 路由。
- `catos/market_dashboard.py`：Yaozi 累積 decision surface、Personal watchlist、Push History、Whistle History、Social raw metrics、Account / Local 與 member-shell 導覽；此檔同時含已提交與 v1.5–v1.26 未提交成果，必須逐段整合，不可整檔覆蓋。
- `catos/market_lifecycle.py`：僅補強 SMF `-20` 邊界的既有本機相容語義註解，不改演算法。
- `catos/market_social.py`：新增 evidence-backed `EXPLICIT_SOCIAL_ASSETS_V1` 至 `V5`，目前累積 AAVE、LDO、ENA、MORPHO、ONDO、ETHFI、LINK、PAXG、PENDLE、QNT、AERO、CAKE、CRV、GRT、VIRTUAL 等 explicit identity mapping。
- `tests/test_market_api.py`：覆蓋 decision surface 與 v1.15–v1.21 Dashboard/member-shell surfaces。
- `tests/test_market_signals.py`：新增 MOMENTUM 的 ±10% 邊界、24h 欄位來源與 PURE_MOMENTUM 區分驗證。
- `tests/test_market_social.py`：覆蓋 explicit identity registry V1–V5 與 ambiguous metric fail-closed 行為。

僅 Yaozi 存在的 13 個整合候選：

- runtime：`catos/market_decision.py`。
- tests：`tests/test_yaozi_capture_preflight.py`、`tests/test_yaozi_capture_workflow.py`、`tests/test_yaozi_ground_truth.py`、`tests/test_yaozi_ground_truth_series.py`、`tests/test_yaozi_parity_audit.py`、`tests/test_yaozi_series_report.py`。
- tools：`tools/yaozi_capture_preflight.py`、`tools/yaozi_capture_workflow.py`、`tools/yaozi_ground_truth.py`、`tools/yaozi_ground_truth_series.py`、`tools/yaozi_parity_audit.py`、`tools/yaozi_series_report.py`。

Yaozi 上述來源範圍目前另有 18 個 tracked-modified／untracked 檔案；包含 `market_dashboard.py`、`market_lifecycle.py`、`market_social.py`、三個既有 market tests、三個既有 Yaozi tests、三個既有 Yaozi tools，以及六個新 capture/report tests/tools。這些未提交內容均保留。本輪未重跑 Yaozi 測試、未開 DB、未修改 Yaozi 工作樹。

此段為整合前靜態盤點：當時 Astra 只找到 `catos/market_api.py:create_app()`，根路由 `/` 與 `/dashboard` 都由情報 Dashboard 使用。2026-09-23 follow-up 已解決 root ownership：`/` 現為統一產品 shell，`/dashboard` 保留 Yaozi，`/quant` 為唯讀量化狀態面；仍沿用同一 FastAPI 入口，沒有第二個網站或跨 worktree runtime dependency。

## 最小整合順序

2026-09-23 Astra 實作進度：原 decision／API／Dashboard 與 Social V1–V5 最小整合已驗收；後續 Social V9 follow-up 亦已完成。Astra 現行 `market_social.py` 已含 V1–V9 並以 V9 作 current runtime mapping registry，`/intel/social` 與 Dashboard 可唯讀呈現 V9 identity readiness／baseline-derived coverage，且與 materialized raw metrics 分離。本 follow-up 的 5 個程式／測試檔正規化換行後與 Yaozi V9 source 一致，25/25 runtime+Social tests、1/1 Social Dashboard/API regression、py_compile 與 synthetic localhost Crawl4AI render 均通過。詳見[本片交驗](catos-yaozi-integration-handoff.md)、[原始 manifest](yaozi-integration-manifest-20260923.json)及[V9 follow-up manifest](yaozi-v9-integration-manifest-20260923.json)。其餘 capture／audit／report tools/tests 未因本片自動帶回。下列為整體交付順序，不能解讀為全部待做或全部完成；量化前端延後的既有指示不因情報 Dashboard 合併而解除。

1. Sol 核對兩邊基線、未提交內容與 Yaozi 交付檔案清單，保留工作後固定整合來源；在取得既有流程所需 Git 授權前不提交或合併。
2. Astra 依差異整合情報模組及必要依賴、專屬測試；共享 `market_api`／`market_intel` 按內容處理，避免蓋掉交易主線變更。
3. **已完成第一階段**：建立 catOS 統一導覽與唯讀量化狀態面，接入既有情報頁；root ownership 已解決，Yaozi 繼續使用 `/dashboard` 與同源 `/intel/...`。未新增第二個使用者網站、反向代理服務或通用插件框架；交易 mutation UI 仍待明確 product contract。
4. Web 介面只負責操作與呈現；交易生命週期、風控與唯一交易出口仍由 Supervisor 管理。情報頁不取得交易憑證、不直接交易；情報失敗不得解除 latch 或改變部位。
5. 先使用隔離的 synthetic 資料驗收。主庫如需 schema 變更，另交備份、遷移及驗證方案並取得確認；不直接讓 writer 升級既有 DB。

根路由衝突與頁面 lifecycle 綁定風險已由本次統一 shell follow-up 收斂；版本覆蓋與舊 DB 可讀性仍依各自切片處理。整合繼續採明確檔案歸屬、同源路由與後端 lifecycle owner，不增加常駐整合服務或新的帳本。

## 最小驗收條件

- 單一瀏覽器頁面可切換量化／情報；不開新視窗、不要求第二個網站。
- 本地模擬策略運行時切換、重新整理及關閉頁面，策略仍依後端狀態推進；只有明確停止操作才停止。由 Sol 記錄可重現證據。
- 情報缺資料、讀取錯誤及不相容版本皆明示；策略不依賴情報頁請求才能推進。
- 受影響情報 API／畫面與策略生命週期最小測試通過；DB fixture 與實際主庫證據分開記錄。
- 不讀真實憑證、不發送 Demo／Live 交易、不改既有 DB schema；不因整合新增交易授權。

最初文件片僅交付契約；現行進度以上方 Astra 交驗與 [統一 shell handoff](catos-unified-shell-handoff-20260923.md) 為準。統一量化／情報頂層介面已完成第一階段 local-sim 驗收；Web start/stop、真正 Demo／Live 交易與未完成交易主線 blocker 不因 shell 完成而自動成立。
