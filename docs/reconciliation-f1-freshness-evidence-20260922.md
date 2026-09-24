# F1 Demo read-only freshness 補證 — 2026-09-22

本切片依使用者明確授權執行。只讀既有指定 Demo credential 檔、固定 `openapi.okx.com` allowlist GET 與 public time；未交易、撤單、修改帳戶、開既有 DB、保存／輸出 credential、commit 或 push。`trade_authorized=false`。

## 正常 production plan 樣本

同一既有 24h／13 endpoint plan 連續執行 4 次；每次皆 41 driver/wire GET、`collection_complete=true`。每次 collection 完成後再做一個 gate-adjacent `public_time` GET，以 local send/receive midpoint 作 `FreshnessEvidence.local_time_ms`，`checked_at_ms` 在回應解析後立即取得。

| 指標 | 4 次實測範圍 |
| --- | --- |
| batch span | 20159–20216 ms |
| completed -> checked_at report age | 132–170 ms |
| public-time RTT | 131–169 ms |
| midpoint clock offset | +2837～+2848 ms |
| clock sample age | 66–85 ms |

完整非敏感 timing：`evidence/f1-freshness-normal-20260922.json`，SHA-256 `D21EF487A55A3EC279D2A19751522D6DD3C6D87F14F725F5F4E8AFFD93F795BB`。

## 180 秒真實 pagination 壓力樣本

為驗證既有 180000 ms runtime deadline，以相同 Demo 帳戶與既有 GET allowlist 建立一次 evidence-only stress plan：30 天窗口、`page_size=1`、`max_requests=360`、`max_pages_per_endpoint=360`、`request_timeout_ms=10000`、`max_runtime_ms=180000`。只選既有 `account_config`、`public_time`、`fills_history`、`bills_archive`、`algo_history`；transport 保留原 500 ms 最小間隔，沒有額外 synthetic sleep。

- `account_config` 與起始 `public_time` 完整。
- `fills_history` 實際完成 357 頁，第 358 次 request 在 deadline 以 `timeout` fail closed。
- 總計 360 次真實 GET，batch span `179993 ms`。
- `bills_archive`、`algo_history` 因 request budget 已耗盡而未啟動；整體 `complete=false`，符合壓力樣本預期。
- 批次後 gate-adjacent public-time：RTT 161 ms、midpoint offset +2865 ms、clock sample age 81 ms、completed -> checked_at 161 ms。

完整非敏感 timing：`evidence/f1-freshness-stress-20260922.json`，SHA-256 `052AA63AFB5F0CB869CDBF60778B50F794BE384B8364024A18679BB73473B64C`。此 stress plan 只證明真實 HTTPS/pagination 下 runtime fail-close 行為，不作 production snapshot evidence。

第一次 24h `page_size=1` stress probe 在採集完成後，因摘要程式誤用 `EndpointManifest.issues` 而於本機整理階段退出；未保存結果、不納入 F1 定量，也未重送相同配置。錯誤發生在 GET 完成後，不是 API、credential 或帳戶錯誤。

## F1 定案

policy ID：`f1-demo-2026-09-22`。

| 欄位 | 定案值 | 依據 |
| --- | ---: | --- |
| `max_report_age_ms` | 1000 | 正常實測最大 170 ms；formal gate 為同程序立即消費，1 秒保留一次既有 transport cadence／網路與本機排程餘裕，超過即視為非 gate-adjacent。 |
| `max_batch_span_ms` | 31000 | 正常實測最大 20216 ms，加一個既有 `request_timeout_ms=10000` 的明示延遲預算後向上取整；180 秒 stress 必須被 freshness 阻斷。 |
| `max_clock_skew_ms` | 3000 | 新樣本 midpoint offset 最大 +2865 ms；連同 RTT 半寬及前片 +2736 ±134 ms，觀察到的 offset uncertainty 上緣低於 3000 ms。 |
| `max_clock_sample_age_ms` | 500 | gate-adjacent 實測最大 85 ms；限制 clock sample 必須在一個既有 500 ms transport cadence 內被消費。 |

用現行 `_freshness_blockers()` 驗證：4/4 正常樣本皆無 freshness blocker；179993 ms stress 樣本被 `snapshot_freshness_unverified` 阻斷。既有單元測試已覆蓋門檻等號可通過、超 1 ms、future sample、雙向 skew 與 snapshot semantics fail closed。

F1 四值定案不代表 `snapshot_semantics_verified=True`。snapshot semantics 仍需獨立證據；現行 65 個 unknown flow 也仍使 classification `complete=false`。formal gate 與 `trade_authorized=false` 不因此解鎖。
