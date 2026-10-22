# Slice F：本機合成帳戶風控

基線 `c928195`。F 實作已確認的曝險與日損規則，沿用 E 的單 Supervisor、單 SQLite writer、原子意圖提交及 COMMIT 後 ACK。只處理合成資料；沒有交易所連線或派送器。

2026-09-12 補註：[G](execution.md) 已完成本機假交易所閉環。下文保留 F 單獨啟用的契約；傳入 `FakeExchange` 時，委託生命週期、保留釋放及 pending 去重以 G 契約為準，未連線至真實交易所。

## 啟用與資料來源

建立 `LocalSupervisor` 時傳入 `risk_limits=risk.Limits()`，預設槓桿上限 `Decimal("3.0")`、單幣預算占比 `Decimal("0.50")`。參數只由 Supervisor 設定，不進入 Worker IPC。同一 DB 啟用後不得改回 fixture 模式；曝險 limits 仍固定。P5 新增 Soft／Hard 設定，預設 Decimal("0.10")／Decimal("0.20")，可透過下方 Supervisor 介面原子更新。

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

2026-10-20 R1 local-sim 已實作並完成開發自測，詳見[交付與證據](risk-period-r1-local-sim.md)。`DayBasis` 綁定 Taipei 日、帳戶／環境、當日首次合格觀測的實際起算時間、正的固定權益與來源證據，經單 writer COMMIT 後才可使用。同日不可替換；首次／新日資料暫缺可重試，未合格前禁增倉。同日曾建立或已有本日執行責任但基準遺失／損壞，不能假裝首次建立。

R1 的 `external_net` 僅包含實際起算後、已分類且已證明歸屬的非策略外部淨流入；快照以 `flow_basis_id`／`flow_start_ms` 綁定，不能沿用午夜小計或以未知為零：

```text
風控期間損益率 = (當前權益 - 固定期間基準權益 - 起算後外部淨流入) / 固定期間基準權益
```

費用、資金費及損益已含在當前權益，不重複扣除。台北 UTC+08:00 午夜切日；快照跨午夜仍須重新確認當日基準。報告顯示「風控期間損益」與起算時間，不涵蓋起算前的當日損失。舊 exact-midnight／Q1 能力與 Demo 路徑保留，不代表 Demo 已接入 R1；舊明示 E1 封鎖不自動解除。

最新 P5：Soft／Hard 可配置，v1 預設損失 10%／20%；入金、反彈、跨日、重啟均不自動解除。原原因消失且條件合格後可隨時人工 re-arm，修改門檻不直接解除 latch。P5 本機遷移已完成：可配置 10%／20%、原子保存門檻、合格人工 re-arm、schema 4 控制稽核；舊意圖不復活。實際帳戶資料與交易所適配仍未接入。

| 狀態 | F 行為 |
|---|---|
| R：RUN／NO_INCREASE／FLAT | soft 至 NO_INCREASE，hard／manual Kill 至 FLAT；只有明示人工 re-arm 可降低嚴重度 |
| H：RECONCILING／HEALTHY／DEGRADED | 啟動先對帳並要求新快照；不完整／逾時觀測與執行錯誤關閉增倉 |
| P：IDLE／WORKING／VERIFY／WAIT／DONE | FLAT 建立唯一 `flatten_id`；反覆 Kill 沿用；F 的進度由合成呼叫驅動 |

`flatten_progress("DONE", now_ms=...)` 只接受 VERIFY 後的新鮮空倉、普通及條件委託全終結、無 UNKNOWN、成交對帳完成，且沒有本地 pending／reservation／outbox 的證據。DONE 不解除 FLAT；後續非零部位或待成交曝險重新轉 WORKING，沿用操作 ID。F 不執行市價清倉，G 才接模擬撤單、reduceOnly 建單及回報。

日損／Kill／健康關門會持久化遞增的 epoch，將舊增倉 `risk_orders.eligible` 設為零，不自動回復。原 outbox 始終是不可派送的 `HELD_SIMULATION`，原 reservation 保留到 G 的終結契約；receipt 是歷史提交結果，不代表目前允許執行。若 Kill 在 COMMIT 途中到達，該筆可能已保留，但本機立即關門，writer 隨後保存失效狀態。G 出站前仍須重新核對最新 epoch、健康、曝險與部位，不能只看歷史 receipt 或 eligible。

## 儲存與驗證邊界

schema 1 → 2 在交易內增加 `risk_control` 與依附原意圖的 `risk_orders`，保留原 checkpoint、所有權及鎖存。舊 fixture 尚有 reservation／outbox 時拒絕啟用 F，不能把未知單位的 fixture 額度轉成真實曝險。重啟保留日基準、R／P、原因及操作 ID，清除快照並回到 RECONCILING。沒有新帳本、第二條 writer 或儲存故障繞行下單。

專屬驗證：risk 14、risk journal 8、risk Supervisor 5；另跑受影響的原 Journal 14、Supervisor 14，共 55 個測試。包含真實 Worker、SQLite 提交回滾、Kill 在 COMMIT 中到達、等待 Worker 期間日損越線又反彈、重啟鎖存、舊 schema 升級、期限及 Decimal 邊界。未重跑全域套件或市場回測。

2026-09-12 已確認：E_risk = E_verified，不設 equity buffer；被動超限只禁增倉、合法減倉始終允許、不自動去槓桿；陌生部位／委託不接管、不處置；資金流白名單分類。P5 政策如上，缺失基準依上述 R1 與既存責任規則處理，未定義的生產帳單分類不自行補猜；[P6 政策](disaster-stop-policy.md) 已確認，實際交易所適配未實作。合成 `risk_equity` 與 `margin_ok` 不構成真實保證金模型或 Demo／Live 風控驗證。

## P5 人工設定與恢復介面（本機已實作）

本輪驗證：P5 專屬 12、既有 F 27、受影響 G 28、共用 Journal／Supervisor 28，共 95 tests 通過。涵蓋重複 Kill 在恢復提交期间的否決、失敗回滾、舊版 DB 遷移及 G 舊意圖不復活；未執行全域測試或帳戶請求。

具體失敗情境：設定變更誤清除 latch，或恢復與新 Kill 競爭，導致舊委託出站。最小做法沿用單 writer，新增控制稽核表，先 COMMIT 才在記憶體解除；不增加新交易出口或常駐服務。

```python
await supervisor.set_loss_limits(
    soft_loss=Decimal("0.10"), hard_loss=Decimal("0.20"),
    actor="operator", evidence_id="settings-review")
await supervisor.rearm(
    now_ms=now_ms, actor="operator", evidence_id="reconciliation-review")
```

門檻為正的損失比例，必須 `0 < soft_loss < hard_loss <= 1`，拒絕 float／非有限值。提高門檻保留 latch；降低門檻立即以現有可信快照評估並鎖存。人工恢復按目前已保存的門檻判定日損原因；設定變更本身不恢復，不改寫固定 E_0／C_t。

re-arm 需要新鮮健康快照、當日有效 E_0、完整已歸因部位對帳、無未知單、普通／條件委託已終結、無本地 reservation／outbox／PENDING 輸入，以及原風險原因消失。Soft 可持有核實部位恢復；Hard／Kill 須完成既有清倉至 DONE 且帳戶空倉。manual Kill 另需 `manual_cause_cleared=True` 明示已排除手動停機原因，不能覆蓋有效日損／健康原因。RUN 仍受曝險與合法減倉裁決約束。

2026-09-15 修補（待驗證）：上述恢復檢查明確納入 P6 active／pending／uncertain／triggered 責任，即使首次保護建立尚無 active ID 也不得略過。拒絕恢復時 latch、epoch 與成功稽核紀錄不變。已明確結束且只剩 failed 訊號時，仍按原條件判斷能否恢復；P6 自身禁增倉閘門保持關閉，恢復不等於允許增倉。

恢復增加 epoch、重置清倉操作 ID／phase，不復活舊意圖、不釋放未終結責任。同日可恢復；反彈、入金、跨日或重啟不自動解除。恢復提交期間任何新風控輸入（含重複 Kill）均否決本地解除並重新保存最新鎖存；一般輸入仍須 persist_controls 才有耐久保證。

schema 3 → 4 增加 `risk_actions`，保存動作、操作者、證據 ID、前後狀態／E_0、門檻及 epoch。設定、狀態與稽核同交易提交；失敗回滾，普通 save_risk 仍禁止清除原因。舊版只有曝險欄位的 limits JSON 補入 10%／20%，保留既有 latch／E_0／所有權／委託；啟動清除快照並先對帳。新版 DB 重啟須提供已保存的 limits，不可用建構子悄悄換設定。
