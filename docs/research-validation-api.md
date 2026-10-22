# 研究驗證封存與後端查詢

2026-10-19 開發完成、126/126 自測通過；後續已由使用者指定 GPT-6 Sol 完成三個研究包獨驗與唯讀 Git 核對，均 PASS，見[獨驗報告](../reports/research-independent-acceptance-20261019-gpt6sol/acceptance.md)。範圍限合成資料與隔離後端，不包含正式服務更新或前端串接。下方「本輪」驗證數字仍指原開發自測，不冒充獨驗或 2026-10-20 重驗。

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

`backtest.parameters.period` 保留原請求格式；驗證任務的候選週期由 `search_space.period` 決定，quantity 固定。策略只允許已核准的 RegisteredSMA，資料只允許既有 96 根合成 15m K 線。整數 range 須對齊、至少兩個候選、週期在 2 到 32，預熱涵蓋最高候選週期。

任務最多 20 個格點、8 個視窗、100 次回測；提交時預檢 `windows × (格點數 + 1) <= max_runs`，且 `warmup_bars + train_bars + windows × test_bars <= 資料根數`。不自動縮短計畫、補預算或增加成功次數。已有的 30 秒逾時、2,000,000 bytes 子程序輸出上限仍適用。目前沿用參數型別的既有 Optuna 依賴；本任務採完整格點，不啟動 Optuna 搜尋，也不轉 Float 排名。

| 操作 | API | 用途 |
| --- | --- | --- |
| 送出 | POST `/api/research/validations` | 202 回傳 run_id 與 queued 任務 |
| 清單 | GET `/api/research/runs` | `items` 內以 kind=validation 辨識 |
| 狀態 | GET `/api/research/runs/{run_id}` | queued／running／complete／failed 與錯誤 |
| 結果 | GET `/api/research/runs/{run_id}/result` | 完整封存 JSON，不執行運算 |
| 報告 | GET `/api/research/runs/{run_id}/report` | 既有下載報告路徑，含任務與來源綁定 |

8771 preview 只將此 POST 轉送既有 8770 writer，GET 沿用原轉送契約，不另建服務或封存目錄。本輪僅以 mock relay 和 in-process TestClient 自測，未連實際 8770／8771。MCP 未新增驗證送出工具；既有清單／結果讀取不變。

## 結果欄位

頂層 `schema=catos.research.validation-result.v1`、kind、run_id、created_at、build_id、request、provenance 與原任務綁定。`reproduction.files` 為相對路徑、sha256、content_utf8；只供檢查／人工重現，API 不執行封存程式碼。雜湊和來源快照不是防竄改簽章、可安裝環境或跨版本重現保證；未保存套件本體與完整環境鎖檔。

| JSON 路徑 | 內容 |
| --- | --- |
| `result.validation.windows[n].training` | 格點、各候選原績效／錯誤、鄰域、固定選擇與排序規則 |
| `result.validation.windows[n].out_of_sample` | 當窗完整 OOS 回測：績效、成交、資金費、權益與末筆意圖 |
| `result.windows[n].evaluation.summaries` | UNKNOWN／上漲／下跌／震盪 × 波動組別，含零樣本組 |
| `result.windows[n].evaluation.total` | 當窗損益、成本、K 線數與成交數 |
| `result.windows[n].evaluation.reconciled` | 分環境歸屬與原 OOS 帳務核對 |
| `result.rule`、`result.rule_version`、`result.labels` | 門檻、分類版本及逐根標籤 |
| `evaluation_complete` | 是否每個 OOS 視窗均 COMPLETE，非策略有效或可部署判定 |
| `reproduction`、`provenance` | 研究來源快照、版本與既有核准策略身分 |

Service 的 `status=complete` 表示計算與封存完成。研究視窗若有 NO_SELECTION／OOS_FAILED，任務仍可 complete，但 `evaluation_complete=false`；原錯誤保留，該窗 `out_of_sample`／`evaluation` 為 null，不補零，不重試。Worker 失敗、逾時、輸出超限或來源漂移則整個任務 failed，結果查詢 409。請求不合格為 422，過大為 413，版本不符／忙碌為 409，Origin 不符為 403。

所有金額與比例採 Decimal 字串；時間、根數、候選索引採整數。不要把正損益 K 線比例當往返交易勝率，也不要串接獨立 OOS 權益曲線當連續投資組合。期末部位估值而非強平，沒有新增末筆成交或假設平倉費。資金費事件仍明示為空，不能當歷史資金費完整的證明。

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
