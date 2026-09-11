# Slice F：本機合成帳戶風控

基線 `c928195`。F 實作已確認的曝險與日損規則，沿用 E 的單 Supervisor、單 SQLite writer、原子意圖提交及 COMMIT 後 ACK。只處理合成資料；沒有交易所連線或派送器。

## 啟用與資料來源

建立 `LocalSupervisor` 時傳入 `risk_limits=risk.Limits()`，預設槓桿上限 `Decimal("3.0")`、單幣預算占比 `Decimal("0.50")`。參數只由 Supervisor 設定，不進入 Worker IPC。同一 DB 啟用後不得改回 fixture 模式或更換 limits；本片不提供在線風控設定變更。

未傳入 `risk_limits` 保留 E 的離線 fixture 測試介面，預設仍拒絕有差額的目標。啟用 F 後拒絕任何非預設 `FixtureDecision`，裁決不採用 `fixture_budget`；該欄位只保留舊 DB 身分相容性。

對帳完成後，Supervisor 呼叫同步的 `observe_risk(Snapshot(...))`。每筆序號必須接續，時間不得倒退；即刻更新記憶體風控，不等待 Closed Bar、Worker 或 SQLite。`await persist_controls()` 才確認耐久保存；bar 提交前後與 close 也會序列化保存。等待 writer 期間即使先跌破門檻再反彈，中間的鎖存仍保留。沒有新增背景服務或自動時鐘；測試／呼叫端需獨立注入觀測及 `risk_timer(now_ms)`。

`Snapshot` 的金額、部位、mark、買賣待成交量及外部資金流一律 Decimal；有效期限與證據序號為整數。`valid_until_ms` 必須明示，沒有自行設定實際行情的逾時政策。`valuation_known`、`flows_known`、`margin_ok`、`position_verified` 與 `reduction_conflict` 是 Supervisor 的合成事實，不能由 Worker 宣告。

`pending_buy`／`pending_sell` 必須包含本合約所有外部在途與 UNKNOWN 的未成交量，**排除 F 已保存且從未派送的本地 held 意圖**；它們由 Journal 另外相加。`other_notional` 是其餘帳戶的完整最壞曝險合計，亦須含在途及 UNKNOWN。F 仍只擁有單一 Bot／合約，該合計不授予外部部位的歸因或清倉權限。真實委託回報如何去重、歸併與終結屬 G，不能直接把這些合成欄位當成完整交易所帳本。

## 曝險與減倉

對部位 `q`、全部待買 `B`、全部待賣 `S`：

```text
worst_q = max(abs(q - S), abs(q + B))
本幣最壞名目 = worst_q × base_per_contract × mark
總預算 = leverage × risk_equity
本幣上限 = 總預算 × symbol_share
```

反向委託不互抵，未成交減倉不釋放額度。本地 held 數量在每次裁決以當前 mark 重估，不能拿舊 reservation 金額代替。`effective_leverage()` 另計算實際名目合計／權益；非正權益回傳 `None`，不執行無效除法。所有運算隔離於研究核心的 50 位 Decimal context。

意圖、風控裁決、reservation、signed quantity、reduceOnly、outbox、checkpoint 與消費位置在同筆交易保存。單一金融提交等待時，Supervisor 保存保守的 pending 金額上界並拒絕第二筆金融操作。重播只回傳原 receipt，不再保留一次額度。

增倉需要有效估值、正權益、合成保證金條件成立、當日基準與資金流完整、已對帳部位及開放的 R／H。曝險被動超限至少拒絕增倉；不自行計算自動去槓桿目標。

減倉獨立裁決：新鮮且核實、與 Worker 帳戶視圖一致的已歸因部位；目標不穿零，符合合約數量限制；沒有衝突減倉或其 UNKNOWN。通過者保存 `reduce_only=1`、新增曝險保留為零。日損、保證金不足等增倉原因不一律阻止合法減倉；部位陳舊或不明仍拒絕。零金額 reservation 仍是未終結責任，不等於可釋放所有權。

## 日損與 R／H／P

`DayBasis` 必須給出 Taipei 日識別、正的日初權益及證據識別。同日基準不可替換；新一天必須供應新日初證據，缺漏不以啟動權益補建。`external_net` 是當日累計、已分類的非策略外部淨流入：

```text
日損率 = (當前權益 - 固定日初權益 - 外部淨流入) / 固定日初權益
```

費用、資金費及損益已含在當前權益，不重複扣除。台北 UTC+08:00 午夜切日；快照跨午夜仍須重新確認當日基準。`<= -3%` 鎖存 soft，`<= -5%` 鎖存 hard；入金、反彈、跨日、重啟均不解除。

| 狀態 | F 行為 |
|---|---|
| R：RUN／NO_INCREASE／FLAT | soft 至 NO_INCREASE，hard／manual Kill 至 FLAT；不提供成功 re-arm |
| H：RECONCILING／HEALTHY／DEGRADED | 啟動先對帳並要求新快照；不完整／逾時觀測與執行錯誤關閉增倉 |
| P：IDLE／WORKING／VERIFY／WAIT／DONE | FLAT 建立唯一 `flatten_id`；反覆 Kill 沿用；F 的進度由合成呼叫驅動 |

`flatten_progress("DONE", now_ms=...)` 只接受 VERIFY 後的新鮮空倉、普通及條件委託全終結、無 UNKNOWN、成交對帳完成，且沒有本地 pending／reservation／outbox 的證據。DONE 不解除 FLAT；後續非零部位或待成交曝險重新轉 WORKING，沿用操作 ID。F 不執行市價清倉，G 才接模擬撤單、reduceOnly 建單及回報。

日損／Kill／健康關門會持久化遞增的 epoch，將舊增倉 `risk_orders.eligible` 設為零，不自動回復。原 outbox 始終是不可派送的 `HELD_SIMULATION`，原 reservation 保留到 G 的終結契約；receipt 是歷史提交結果，不代表目前允許執行。若 Kill 在 COMMIT 途中到達，該筆可能已保留，但本機立即關門，writer 隨後保存失效狀態。G 出站前仍須重新核對最新 epoch、健康、曝險與部位，不能只看歷史 receipt 或 eligible。

## 儲存與驗證邊界

schema 1 → 2 在交易內增加 `risk_control` 與依附原意圖的 `risk_orders`，保留原 checkpoint、所有權及鎖存。舊 fixture 尚有 reservation／outbox 時拒絕啟用 F，不能把未知單位的 fixture 額度轉成真實曝險。重啟保留日基準、R／P、原因及操作 ID，清除快照並回到 RECONCILING。沒有新帳本、第二條 writer 或儲存故障繞行下單。

專屬驗證：risk 14、risk journal 8、risk Supervisor 5；另跑受影響的原 Journal 14、Supervisor 14，共 55 個測試。包含真實 Worker、SQLite 提交回滾、Kill 在 COMMIT 中到達、等待 Worker 期間日損越線又反彈、重啟鎖存、舊 schema 升級、期限及 Decimal 邊界。未重跑全域套件或市場回測。

權益／費用／滑價緩衝、帳單分類與停機跨日重建、人工恢復資格、被動超限自動減倉及交易所保護單仍待決。合成 `risk_equity` 與 `margin_ok` 不構成真實保證金模型或 Demo／Live 風控驗證。
