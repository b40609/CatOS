# Reconciliation 唯讀證據切片 — 2026-09-22

本輪依使用者新授權執行，不沿用 9/15 歷史授權。已完成 subtypes 與一次 bounded Demo 採集、部分分類、最小驗證；兩個政策 blocker 尚未解除。trade_authorized=false。

## 採集與來源

沿用 catos.demo_collection.load_authorized_credentials()、DemoReadTransport、HTTPSGetSender；只讀既有指定 Demo 憑證供簽名，不讀其他憑證來源／環境變數，不保存或輸出憑證。主機固定 openapi.okx.com、TLS、GET、x-simulated-trading=1。新增 account_subtypes 固定 allowlist，無 query，不另造 HTTP／credential 路徑。

官方公開文件由 agent-reach Jina Reader 路徑讀取：[Get bill types](https://www.okx.com/docs-v5/en/#trading-account-rest-api-get-bill-types)。文件說明不帶 type 時回傳所有類型，空白描述表示未啟用；文件不是交易授權。一般網頁搜尋未取得有用結果，未作分類依據。

### Subtypes

- 實際執行一次 python -m catos.demo_collection --read-subtypes-authorized；exit 0，1 次 wire GET、accepted，HTTP body 11,698 bytes。
- 本機 request started_ms=1790039748468；completed/received_ms=1790039748822；耗時 354 ms。
- 取得 32 個 type、185 個唯一 (type, subType)。
- [完整非敏感目錄](evidence/okx-demo-subtypes-20260922.json) 僅保存官方 type/typeDesc/subType/subTypeDesc，沒有 raw account response、UID、帳務或認證 header。
- catalog SHA-256：84373423204fe2ccf65955ba096e11687e96879caf436d00efcf5af030506e4c。計算方式：JSON sort_keys=True、separators=(',', ':')、ensure_ascii=True、UTF-8；保存後重算吻合。
- 17 個 subType 描述空白；type 22、24、26 的 typeDesc 空白。未啟用不等於可忽略其未來帳單，仍 unknown。

### Classification

新增 OKX_DEMO_CATALOG_FLOW_CLASSIFICATION，版本名 okx-demo-subtypes-2026-09-22。11 組 entry 均附上述目錄 digest、接收時間、官方 label 與分類理由：

| 類別 | (type, subType) | 理由 |
| --- | --- | --- |
| external | 1/11、1/12 | 資本移入／移出交易帳戶 |
| internal | 2/3、2/4、2/5、2/6 | 開／平多空交易活動已反映於 equity |
| internal | 8/173、8/174 | funding 費用／收入已反映於 equity |
| internal | 9/125、9/126 | ADL 平倉已反映於 equity |
| internal | 34/355 | Settlement PnL 已反映於 equity |

complete=false，既有靜態 Transfer mapping 也維持 false；未將本輪 bills 為空視為分類完整。此常數是 caller 可明示選用的部分版本，不是自動注入的生產預設。分類 ID 仍綁 mapping/evidence/completeness。formal gate 的 completeness 要求未放寬。

其餘 174 組未納入映射，完整集合如下。這包含語意／受管 equity 邊界待釐清，以及本輪尚未納入 v1 白名單的其他產品交易類型；不是宣稱 174 組都沒有官方名稱。每組原始 label 可查上方目錄：

| type | 官方類型 | 仍 unknown 的 subType |
| --- | --- | --- |
| 1 | Transfer | 257, 283, 284, 285, 286, 287, 288, 290, 292, 381, 392, 420, 429 |
| 2 | Trade | 1, 2, 407, 408, 410, 411, 412, 413 |
| 3 | Delivery | 112, 113, 117, 170, 171, 172, 414, 415 |
| 4 | Auto token conversion | 114, 115, 312, 376, 377, 393, 394 |
| 5 | Forced liquidation | 16, 17, 100, 101, 102, 103, 104, 105, 106, 107, 110, 111, 116, 313, 314, 315, 316, 317 |
| 6 | Margin transfer | 160, 161, 162, 332, 333, 334 |
| 7 | Interest | 9, 14, 293, 294, 295 |
| 9 | ADL | 127, 128 |
| 10 | Overloss recovery | 108 |
| 11 | System crypto conversion | 118, 119 |
| 12 | Strategy transfer | 200, 201, 202, 203, 267, 268, 269, 276, 277, 372, 373, 374, 375 |
| 13 | DDH | 131, 132 |
| 14 | Block trade | 204, 205, 206, 207, 208, 209 |
| 15 | Quick margin | 210, 211, 212, 213, 216 |
| 16 | Borrowing | 306, 307, 308, 309 |
| 20 | Token conversion | 220, 221 |
| 22 | 空白（未啟用） | 259, 260 |
| 24 | 空白（未啟用） | 270, 271, 272, 273, 274, 275 |
| 26 | 空白（未啟用） | 296, 297, 298, 299, 340, 341, 342, 343, 344, 345, 441, 442, 443, 444, 445, 446 |
| 27 | Convert | 318, 319, 379, 380 |
| 28 | Easy convert | 236, 237 |
| 29 | One-click repay | 224, 225 |
| 30 | Simple trade | 320, 321 |
| 32 | Move position | 324, 325, 326, 327, 328, 329 |
| 33 | Loans | 348, 349, 350, 351, 352, 353, 354, 356, 357, 358, 359 |
| 35 | Options market | 382, 383 |
| 37 | Corporate action | 421, 422, 423, 424, 425, 426, 427, 432, 433, 434, 435 |
| 38 | USDG Rewards | 416, 417, 418, 419 |
| 250 | Profit share payment | 250, 280 |
| 251 | Profit share refund | 251, 281 |

主要待釐清：voucher/bonus 是否進入可驗證風控權益及回收處理；Auto Earn 利息／獎勵屬策略外收入或受管活動；內部保證金／Bot／借貸／產品子帳間移轉是否跨越本帳戶 equity 邊界；corporate action、退款／分潤與調整的帳务歸屬。不能僅以 Transfer、in/out 字樣自動分類；例如 type 1 同時包含 lending interest，type 11 是 crypto conversion。

External-flow blocker 未解除。下一片應逐項以官方產品／帳務定義釐清上述範圍；無官方語意或使用者尚未定案的帳務政策繼續 unknown。不得將未啟用 code 靜默忽略後宣稱 production complete=true。

## 唯一一次 bounded latency collection

實際執行 python -m catos.demo_collection --execute-authorized；exit 0。config gate、13 sources 分頁完整，driver=41、wire=41；加上 subtypes，本輪 Demo wire 總計 42。未重跑、未改節流／budget／帳戶模式。既有範圍 BTC-USDT-SWAP、trailing 24h，max_runtime_ms=180000、request_timeout_ms=10000、最多 120 driver attempts、每 endpoint 40 pages、至少 500 ms 節流。

| 非敏感時間證據 | 實際值（ms） |
| --- | --- |
| window_start_ms | 1789953380886 |
| window_end_ms / collection started_ms | 1790039780886 |
| collection completed_ms | 1790039801068 |
| report_built_ms | 1790039801069 |
| batch_span_ms | 20182 |
| report age at build | 1 |
| public-time request started_ms | 1790039781386 |
| public-time response completed_ms | 1790039781654 |
| public server timestamp | 1790039784256 |
| public-time RTT | 268 |
| server − local receive | +2602 |
| server − local send | +2870 |
| midpoint offset／half RTT | +2736 ±134 |
| report built − public-time receive | 19415 |

偏移區間以 server timestamp 產生於 request/response 間且期間本機 wall clock 未跳動為假設；單樣本不能證明持續時鐘穩定。未校正 OS 時鐘。report_built_ms 是建報告時間，不是假冒實際 formal gate checked_at_ms。

批次只使用 runtime budget 約 11.2%，沒有接近 180 秒的真實 latency evidence。本輪未故意 sleep／增加請求、擴大預算或重跑來製造樣本。合成 SlowSender 每次推進 4900 ms，既有 runtime deadline 會拒收超時回應；這僅驗證 fail closed，不能當真實網路延遲。

### F1 最終狀態

max_report_age_ms、max_batch_span_ms、max_clock_skew_ms 均維持未定案（不注入生產值），freshness_policy_unset 持續有效。不能由單次 1 ms 建報告成本直接推導排程／消費 age 上限，亦不能從 20.182 秒正常批次推導近 180 秒行為與安全 margin；任意乘倍數不是實測證據。

目前 gate 同時將 checked_at_ms 與校時樣本 local_time_ms 的距離套用 max_clock_skew_ms。本次樣本距建報告已 19.415 秒，和約 2.736 秒的時計偏移是不同量。未以放寬 clock-skew 解鎖；後續應在獨立契約中區分校時樣本年齡與時計誤差，或在獲授權批次中調整既有 public_time 採樣位置。snapshot_semantics_verified 仍無新證明，不能自動 true。

### 帳戶對帳結果

collection_complete=true 只代表分頁與 config gate。reconciled=false、trade_authorized=false。

本輪安全摘要仍有 day_baseline_unverified、foreign_algo、freshness_unverified、invalid_record:balance、local_attribution_not_loaded、missing_or_ambiguous:balance、mode_mismatch、p6_child_order_gap、p6_protection_unverified、p6_triggered_not_reconciled、window_coverage_unverified。balance 診斷明確為 adjEq missing。未根據這些差異猜測資金、所有權或自動修正帳戶；沒有載入交易 DB／正式 Supervisor gate。完整帳戶報告只存在採集程序記憶體，程序已結束，未保存帳務 raw data。

## 實際修改與驗證

- catos/okx_collection.py：新增固定 account_subtypes GET。
- catos/okx_http.py：該端點不注入 instType；其餘簽名、Demo、TLS、redirect、預算機制不變。
- catos/demo_collection.py：subtypes 單次入口與安全目錄解析；既有 run_once 新增 allowlisted latency 摘要。public time 只從已通過 decoder 的 facts 擷取，無效 ts 不產生 clock evidence，仍保留失敗報告。
- catos/okx_readonly.py：11 組部分版本化映射，complete=false。
- tests/test_demo_collection.py、tests/test_okx_readonly.py：入口／欄位／目錄 digest、部分分類、合成 runtime 與無效 timestamp 驗證。
- 本文件、目錄 evidence、current-handoff、gate contract、policy pack 同步。沒有修改既有 DB schema。

本輪實際執行 python -m unittest discover -s tests -p <下列檔名>：

| 模組 | PASS |
| --- | --- |
| test_demo_collection.py | 16/16 |
| test_okx_readonly.py | 20/20 |
| test_okx_http.py | 24/24 |
| test_okx_collection.py | 13/13 |
| test_account_report.py | 39/39 |
| test_reconciliation_gate.py | 12/12 |
| test_supervisor_reconciliation.py | 15/15 |
| 合計 | 139/139 |

四個修改模組及兩個修改測試 py_compile PASS。scoped whitespace 檢查結果見接續入口。合成測試使用 fake credentials／clock，HTTP 測試另包含 localhost TLS；沒有用真實帳戶取代測試。本輪 139/139 和前輪 85/85 是不同驗證，不能相加宣稱全域回歸。

Git HEAD 實際核對為 3925759d16771b9cbe8fac709c0b5dc355772865；cc216f7 為歷史。原有 Lot、market、reconciliation 未提交內容保留；未清理、reset、commit、push。

本輪碰過公開網路、指定 credential 簽名與 Demo GET。沒有交易、下單、撤單、POST、Live、資金轉移、帳戶修改、DB migration；Demo 交易仍未授權。此次 read-only 採集已執行完畢，不構成後續重跑授權。
