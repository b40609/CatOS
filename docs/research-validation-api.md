# 研究驗證封存與後端查詢

2026-10-19 開發完成、126/126 自測通過；後續已由使用者指定 GPT-6 Sol 完成三個研究包獨驗與唯讀 Git 核對，均 PASS，見[獨驗報告](../reports/research-independent-acceptance-20261019-gpt6sol/acceptance.md)。範圍限合成資料與隔離後端，不包含正式服務更新或前端串接。下方「本輪」驗證數字仍指原開發自測，不冒充獨驗或 2026-10-20 重驗。

2026-11-04 第二次更新（分支 `feat/research-second-strategy`；獨立驗收 7／7 PASS，見 `reports/research-second-strategy-acceptance-20261104/acceptance.md`，驗收後的觀察修正只有開發者自測）：策略可選 `sma-trend` 或 `donchian-breakout`，`search_space` 依策略的參數名稱各給一條 range（見下方表格）。

2026-11-04 更新（分支 `feat/research-validation-real-data`，已合併進 `main`；獨立驗收 7／7 PASS，見 `reports/research-validation-real-data-acceptance-20261104/acceptance.md`，驗收後依觀察 O1–O4 的修正只有開發者自測）：結果升為 `catos.research.validation-result.v2`，可在已登錄的 OKX 公開歷史資料集上執行，並接上 React 滾動驗證頁（`frontend/cat-os-vite/src/pages/validation.tsx`）。v1 → v2 的差異見文末「v2 輸出」；方案比較與實測見 [研究線方案](research-real-data-plan.md)。

## 已可交付的行為

新增 `kind=validation` 任務。每個訓練視窗先跑完整參數格點與鄰域穩定區排序，再固定參數跑 OOS，最後依事前明示的市場環境規則歸屬逐根損益。分類不反饋選參，未新增策略、資料來源、評分公式或金融部署門檻。

沿用原有 `ResearchService` 單一寫入者、單一忙碌槽、200 筆封存上限與檔案鎖。回測、Optuna 與驗證互斥；Worker 只回傳有界 JSON／HTML，Service 寫入同一個研究目錄。沒有第二個 writer、SQLite schema 或 DB 遷移。

每筆仍是 `request.json`、`status.json`、`result.json`、`report.html`。新增結果保存來源碼／合成 CSV／策略 manifest 的固定白名單快照與各檔 SHA-256，並記錄 Python、Optuna、packaging 版本；不讀請求指定的路徑、憑證或產品資料。查詢只讀封存，重啟不重算，舊 queued／running 任務沿既有規則標為 failed，不自動續跑。

同時修正送出回覆的巢狀資料共用：呼叫者修改回傳的 request／provenance，不會再改到執行中任務。原本的回測與最佳化請求契約保持相容。

## 前端串接

先 GET `/api/research/version` 取得 `build_id`，再 GET `/api/research/catalog` 取得 `validation.example_request` 與上限。`example_request` 是合成示範，分類門檻不作通用市場預設；提交時仍須傳齊全部欄位。

POST `/api/research/validations`，Content-Type 為 application/json，標頭 `X-CatOS-Build` 必須等於當前 build_id。Origin 如有提供，須與 localhost 入口相同。服務只接受 127.0.0.1；本文不授權啟動、停止或重啟正式服務。

```json
{
  "backtest": {
    "strategy_id": "sma-trend",
    "dataset_id": "synthetic-btc-15m-v1",
    "parameters": {"period": 2, "quantity": "2"},
    "initial_balance": "1000",
    "fee_rate": "0.0005",
    "slippage_bps": "2",
    "warmup_bars": 4
  },
  "search_space": {"period": {"low": 2, "high": 4, "step": 1}},
  "plan": {"train_bars": 24, "test_bars": 16, "windows": 3},
  "regime_rule": {
    "lookback_bars": 4,
    "trend_efficiency": "0.5",
    "high_volatility_bps": "250"
  },
  "max_candidates": 3,
  "max_runs": 12
}
```

`backtest.parameters` 保留原請求格式；驗證任務的候選參數由 `search_space` 決定，quantity 固定。策略只允許 catalog 白名單上的兩個已核准策略（2026-11-04 起），每個整數參數一條 range，參數名稱必須與策略完全相同：

| `strategy_id` | 參數（`backtest.parameters` 與 `search_space` 的鍵） | 範圍 | 預熱 |
| --- | --- | --- | --- |
| `sma-trend` | `period` | 2～32；單軸至少兩個候選 | `warmup_bars` ≥ 最高候選 `period` 且 < 64 |
| `donchian-breakout` | `entry_bars`、`exit_bars` | 2～960、1～959；每格點都要 `exit_bars` < `entry_bars`，所以 `exit_bars` 最大值須小於 `entry_bars` 最小值；全部格點至少兩個 | `warmup_bars` ≥ 最高候選 `entry_bars` 且 ≤ 960 |

資料可選任一已登錄資料集（96 根合成 15m K 線，或經 manifest 雜湊核對的 OKX 公開歷史資料）。整數 range 須對齊（差距為步進的整數倍）。單參數策略的錯誤訊息沿用原本的 `low`／`high`／`step` 欄名，多參數策略為 `entry_bars.low` 這類帶參數名的欄名。HTML 報表的「選定參數」欄以 `name=value` 列出各窗選定的參數組。

任務最多 20 個格點、8 個視窗、100 次回測；提交時預檢 `windows × (格點數 + 1) <= max_runs`、`warmup_bars + train_bars + windows × test_bars <= 資料根數`，以及 `windows × (格點數 × (warmup_bars + train_bars) + warmup_bars + test_bars) <= max_bar_evaluations`（250,000；本機實測每秒約 1.9～5.4 萬根，超過就在送出時以 422 拒絕，不等 30 秒逾時）。環境分類器每根都加總整個回看窗，所以 `regime_rule.lookback_bars` 上限是 `max_lookback_bars`（512）。不自動縮短計畫、補預算或增加成功次數。已有的 30 秒逾時、2,000,000 bytes 子程序輸出上限仍適用。目前沿用參數型別的既有 Optuna 依賴；本任務採完整格點，不啟動 Optuna 搜尋，也不轉 Float 排名。

| 操作 | API | 用途 |
| --- | --- | --- |
| 送出 | POST `/api/research/validations` | 202 回傳 run_id 與 queued 任務 |
| 清單 | GET `/api/research/runs` | `items` 內以 kind=validation 辨識 |
| 狀態 | GET `/api/research/runs/{run_id}` | queued／running／complete／failed 與錯誤 |
| 結果 | GET `/api/research/runs/{run_id}/result` | 完整封存 JSON，不執行運算 |
| 報告 | GET `/api/research/runs/{run_id}/report` | 既有下載報告路徑，含任務與來源綁定 |

8771 preview 只將此 POST 轉送既有 8770 writer，GET 沿用原轉送契約，不另建服務或封存目錄。本輪僅以 mock relay 和 in-process TestClient 自測，未連實際 8770／8771。MCP 未新增驗證送出工具；既有清單／結果讀取不變。

## 結果欄位

頂層 `schema=catos.research.validation-result.v2`、kind、run_id、created_at、build_id、request、provenance 與原任務綁定。`reproduction.files` 為相對路徑、sha256、content_utf8；已抓取資料集的檔案改列在 `reproduction.referenced_files`（路徑與 sha256，不內嵌內容）；只供檢查／人工重現，API 不執行封存程式碼。雜湊和來源快照不是防竄改簽章、可安裝環境或跨版本重現保證；未保存套件本體與完整環境鎖檔。

| JSON 路徑 | 內容 |
| --- | --- |
| `result.validation.windows[n].training` | 格點、各候選原績效／錯誤、鄰域、固定選擇與排序規則 |
| `result.validation.windows[n].out_of_sample` | 當窗完整 OOS 回測：績效、成交、資金費、權益與末筆意圖；權益曲線超過每窗上限時取樣 |
| `result.validation.windows[n].curve_sampling` | 只在取樣時出現：total_points、returned_points、method（`bucket_deepest_drawdown_keep_first_last`；2026-11-09 前產出的結果是 `bucket_deepest_drawdown_keep_first`） |
| `result.windows[n].evaluation.summaries` | UNKNOWN／上漲／下跌／震盪 × 波動組別，含零樣本組 |
| `result.windows[n].evaluation.total` | 當窗損益、成本、K 線數與成交數 |
| `result.windows[n].evaluation.reconciled` | 分環境歸屬與原 OOS 帳務核對 |
| `result.rule`、`result.rule_version`、`result.label_counts` | 門檻、分類版本及全資料各環境的 K 線數（v2 不再輸出逐根標籤） |
| `result.omitted_detail` | v2 省略的逐根明細：`labels`、`windows.evaluation.intervals` |
| `evaluation_complete` | 是否每個 OOS 視窗均 COMPLETE，非策略有效或可部署判定 |
| `reproduction`、`provenance` | 研究來源快照、版本與既有核准策略身分 |

Service 的 `status=complete` 表示計算與封存完成。研究視窗若有 NO_SELECTION／OOS_FAILED，任務仍可 complete，但 `evaluation_complete=false`；原錯誤保留，該窗 `out_of_sample`／`evaluation` 為 null，不補零，不重試。Worker 失敗、逾時、輸出超限或來源漂移則整個任務 failed，結果查詢 409。請求不合格為 422，過大為 413，版本不符／忙碌為 409，Origin 不符為 403。

所有金額與比例採 Decimal 字串；時間、根數、候選索引採整數。不要把正損益 K 線比例當往返交易勝率，也不要串接獨立 OOS 權益曲線當連續投資組合。期末部位估值而非強平，沒有新增末筆成交或假設平倉費。合成資料的資金費事件明示為空，不能當歷史資金費完整的證明；OKX 資料集帶實際資金費率，以結算當下 K 線開盤價近似 mark price。

## 實際驗證與界線

本輪命令：

```powershell
py -3 -B reports/research-validation-archive-20261019/verify.py
```

一次性腳本拒絕覆寫既有證據。Python 3.14.6；10 項新增＋原研究 Web／Optuna Web／MCP／workspace 契約與 Decimal／穩定區／分環境必要回歸，**126/126 通過，0 failure／error／skip**。23 個 Python 檔 AST 通過，25 個來源／fixture／測試檔在驗證前後雜湊一致。

包含真實受信子程序、原核心逐窗重播、與不含分類的 walk_forward 選參一致、低精度 context、來源與資料快照逐檔核對、呼叫者修改回覆不污染任務、封存重啟唯讀不重算、失敗 OOS／無候選／零樣本／UNKNOWN、預算預檢、既有 writer 互斥及 HTTP 版本／Origin／大小／重複欄位拒絕。

預設合成請求實際執行 3 視窗／12 次回測，各窗 16 個區間，淨損益均為 -0.14949010 USDT，逐窗核對一致；重複情境與負值原樣保留，並非市場研究結論。結果含 14 份固定來源材料，序列化 189,053 bytes。

- [實際命令、來源雜湊、結果](../reports/research-validation-archive-20261019/verification.json)
- [原始測試日誌](../reports/research-validation-archive-20261019/unittest.log)
- [合成封存結果（含來源快照）](../reports/research-validation-archive-20261019/synthetic-validation.json)
- [本輪一次性驗證腳本](../reports/research-validation-archive-20261019/verify.py)

reports 沿既有忽略規則保留本機；本節保存原開發自測，後續獨驗另見文首連結。開發交付時既有運行服務尚未載入此變更；不能將 TestClient 通過當正式服務已更新，2026-10-20 文件盤點亦未查證服務現況。本開發工作包沒有真實行情、AI 自主提出策略、外部 provider、產品 DB／憑證、採集、Demo／Live、Git 或前端操作。

接續價值最高的成果是讓前端依本契約顯示「候選穩定區 → 各窗 OOS → 分環境樣本與成本」，由 Antigravity 參照[前後端串接清單](backend-frontend-integration-map.md) 承接；三個後端研究包已獨驗 PASS。任何真實資料研究或 AI 代理寫入策略仍需另訂範圍。

## v2 輸出（2026-11-04）

v1 在 8,640 根的 OKX 資料上量到 14.1 MB（14,085,346 bytes；逐根標籤 1.81 MB、各窗權益曲線約 1.58 MB、逐根歸屬約 1.75 MB，加上把整份 JSON 轉成 HTML 的 8.17 MB 報表），超過 2,000,000 bytes 的 Worker 輸出上限。v2 只拿掉隨資料長度成長的逐根明細，回報的數字不變：

| 項目 | v1 | v2 |
| --- | --- | --- |
| 環境標籤 | `result.labels` 逐根（含每根 efficiency、volatility_bps） | `result.label_counts`：七類環境的 K 線數；逐根標籤可由綁定的資料集與規則以 `classify_regimes` 重算 |
| 分環境歸屬 | `evaluation.intervals` 逐根＋`summaries`／`total` | 只保留 `summaries`／`total`／`reconciled`／`core_net_rounding_residual` |
| 各窗 OOS 權益曲線 | 全部點 | 每窗超過 `max_curve_points`（1,000）÷ 視窗數時取樣：每段保留回撤最深的一點，並保留起點與終點；績效、成交、資金費不受影響 |
| 來源快照 | 所有檔案內嵌內容 | 程式與合成 CSV 照舊內嵌；`data/okx` 下的檔案只記路徑與 sha256 |
| HTML 報表 | 整份 JSON 放進 `<pre>` | 設定、各窗與分環境摘要表；完整紀錄以 `result.json` 為準 |

合成資料在這個規模不會觸發取樣，所以 v2 結果等於 v1 結果去掉 `labels` 與 `intervals`、加上 `label_counts` 與 `omitted_detail`，其餘欄位與數值完全相同（`tests/test_research_validation_web.py` 的 `test_v2_keeps_every_v1_figure_and_only_drops_per_bar_detail` 逐欄核對）。v1 封存結果不會被改寫；讀取端以 `schema` 分辨版本。
