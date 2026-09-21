# Yaozi 開發恢復交接

## 2026-09-20 12:37 新組恢復

- 使用者已澄清：YAOZI 是獨立的數據分析系統分支開發；CatOS 的開發／驗證／採集模型分工不適用本分支。本任務直接執行 YAOZI 公開資料採集與最小驗證，後文舊分工僅為歷史紀錄。
- 入口為 `https://yaozi.yalgo.io/signals`，已恢復 authenticated rendered UI。新組沿用 10:38 的固定 22-symbol watchlist，在新候選結果產生前確定名單。
- 12:37:56.370 baseline 已保存 22／22 derivative snapshots：OKX 14、Binance 8；8 個 OKX ticker／OI API error 已使用當輪 Binance 資料，來源經唯讀核對。5m delta 為 0 個可用，不與數小時前舊快照硬接。
- 新組狀態保存於 `outputs/yaozi-cohort-2026-09-20-1237.json`。12:42:56.370 comparison 已完成，與 baseline 間隔 300,000 ms；22／22 個同 venue 5m delta，12 個 positive candidates：AVA、DASH、ENA、HEI、JTO、PROM、SKL、SKYAI、T、ZEC、ZEN、ZIL。manifest 已與 DB 的 12 個 candidate ID 逐一核對；兩輪 22-symbol OI 來源一致。
- 新組 5／15／30／60 分鐘 follow-up cutoff 分別為 12:47:56.370／12:57:56.370／13:12:56.370／13:42:56.370。時間尚未走完的窗口不得當成 miss。
- 本次展開並保存 default filter：13／17 類啟用；排除「主力轉弱 · 弱看空」「大戶轉空」「SMF 中性轉換」「持續異動中」。此為可見 UI 篩選契約，不是私有 gate 定義。
- 12:50 完成新組 5m checkpoint。authenticated `/signals` 在 12:42:56.370 candidate snapshot 後、12:47:56.370 cutoff 內明示兩筆事件，皆為 JTO：12:43「首次入池 · 異動視角」、12:47「結構撤離確認 · 降級至先行」。固化 `outputs/yaozi-signal-surface-sample-2026-09-20-1250.json`；UI 時間僅分鐘精度，不捏造秒數。
- `outputs/yaozi-candidate-evidence-score-2026-09-20-1250.json`：12 個 candidates 全部與 SQLite 唯一匹配，exact public coverage 22 symbols，issues 空。5m 已完整可評估：JTO 1 hit／其餘 11 miss，candidate hit rate 0.083333；兩筆 captured post-snapshot events 都由同一 JTO candidate 先行，因此 captured-surface event link rate 2／2。此分母只代表本次 captured surface；miss 仍只表示該視窗內未看到同 symbol 事件，不是 false positive 或 Yaozi gate 失敗。
- `outputs/yaozi-candidate-alignment-2026-09-20-1250.json`：2 observations、2 個 5m links，皆為 `SIGNAL_SURFACE_EVENT`、`taxonomy_comparable=false`、`taxonomy_compatible=null`；JTO candidate → 12:43 lead 3,630 ms，→ 12:47 lead 243,630 ms。15m／30m／60m evidence 尚未成熟，不計 hit/miss；下一個 cutoff 為 12:57:56.370。
- 12:58 完成新組 15m checkpoint，固化 `outputs/yaozi-signal-surface-sample-2026-09-20-1258.json`。新增畫面事件為 ZEC 12:57「降 D 級 · 主力出逃」、AWE 12:57「首次入池 · 風險視角」、PONS 12:58「首次入池 · 風險視角」；依既有分鐘精度 parser，12:57 事件落在 12:57:56.370 cutoff 內，12:58 PONS 已超過該窗口。
- `outputs/yaozi-candidate-evidence-score-2026-09-20-1258.json`：15m 已完整可評估，12 candidates 為 2 hit／10 miss，candidate hit rate 0.166667；hit 為 JTO、ZEC。5m 維持 JTO 1 hit／11 miss。capture anchor 前共 5 筆 post-snapshot events，其中 public 22-symbol coverage 內 4 筆；15m linked events 3 筆，coverage linked 3／4。AWE 沒有本輪 public candidate，PONS 12:58 不構成 15m hit。
- `outputs/yaozi-candidate-alignment-2026-09-20-1258.json`：5 observations；5m 2 links，15m 3 links。新增有效 15m 配對為本輪 ZEC candidate → 12:57 event，lead 843,630 ms（約 14 分）；`taxonomy_compatible` 仍為 `null`。alignment 的 60m 視窗另會看見更早一輪 ZEC candidate，因此不可直接當成本 cohort 的 candidate hit 數；本 cohort hit/miss 以 evidence scorer 的固定 12-candidate population 為準。30m／60m 尚未成熟；下一個 cutoff 為 13:12:56.370。
- 13:16 完成新組 30m checkpoint，固化 `outputs/yaozi-signal-surface-sample-2026-09-20-1316.json`。12:42:56.370 candidate snapshot 後至 13:12:56.370 cutoff 共保存 12 筆明示單幣 rendered events；另保留 13:01「★ 市場下跌 · 方向確立」為無 symbol 的 global event，明示排除單幣 alignment。capture anchor 為 13:16:53.743+08，未提前把 60m 窗口算成 miss。
- `outputs/yaozi-candidate-evidence-score-2026-09-20-1316.json`：30m 的固定 12 candidates 全部可評估，2 hit／10 miss，candidate hit rate 0.166667；hit 仍為 JTO、ZEC。5m 維持 JTO 1 hit／11 miss，15m 維持 JTO／ZEC 2 hit／10 miss；60m 12 個全部 `non_evaluable`。candidate persistence `complete`、exact derivative public coverage 22 symbols、issues 為空。
- `outputs/yaozi-candidate-alignment-2026-09-20-1316.json`：12 observations、issues 為空。5m／15m／60m 的 stored link counts 為 2／3／4；其中 60m 多出的第 4 link 是 ZEC 更早一輪 public candidate，不能當成本 cohort 的 30m hit。固定 cohort 的 30m scorer linked observations 為 3，候選 hit 仍只有 JTO、ZEC；所有 surface events 仍 `taxonomy_comparable=false`、links 的 `taxonomy_compatible=null`。
- 新增獨立 `catos/yaozi_surface_lifecycle.py` 與 `tests/test_yaozi_surface_lifecycle.py`，只分析 `catos-yaozi-signal-surface-sample-v1` 的 rendered surface 時序，與既有 `catos/market_lifecycle.py` 分離。已觀察到 JTO 12:43「首次入池」→12:47「結構撤離確認」為 4 分鐘，BCH 13:03「首次入池」→13:05「結構撤離確認」為 2 分鐘；同分鐘多事件固定標為 order-ambiguous，不推定先後或私有 gate。
- 9／18 `catos-yaozi-blackbox-sample-v1` 的 `transition_constraints` 保留為另一類黑箱約束證據，不直接併入 rendered surface lifecycle transition counts；若後續需要合併，先建立明示 normalization／provenance adapter，避免把 Dealer／Today 狀態變化誤當 `/signals` 事件生命週期。
- 13:44 完成新組 60m checkpoint，capture anchor `2026-09-20T13:44:27.955+08:00`。`outputs/yaozi-signal-surface-sample-2026-09-20-1344.json` 固化 12:42:56.370 candidate snapshot 後至 13:42:56.370 cutoff 的 26 筆明示單幣 rendered events，另保留 13:16／13:01 兩筆無 symbol global events；13:43 ONG「首次入池 · 機會視角」明確晚於 cutoff，排除於本 60m sample。
- `outputs/yaozi-candidate-evidence-score-2026-09-20-1344.json`：固定 12 candidates 全部可評估，60m 為 2 hit／10 miss，candidate hit rate 0.166667；hit 仍為 JTO、ZEC。public 22-symbol coverage 內有 9 筆 observed events，其中 5 筆在 60m 內有本固定 cohort 的 preceding candidate。candidate_miss 只表示 captured surface/window 內未見同 symbol event，不是 false positive，也不證明 Yaozi 私有 gate 失敗。
- `outputs/yaozi-candidate-alignment-2026-09-20-1344.json`：26 observations、issues 為空；5m／15m／60m stored link counts 為 2／3／6，linked event counts 為 2／3／5。60m 的 6 links 含 ZEC 更早一輪 DB candidate，因此 alignment link 數不可當成本固定 cohort hit 數；固定 cohort 仍以 evidence scorer 的 JTO／ZEC 2 hit／10 miss 為準。所有 surface events 維持 `taxonomy_comparable=false`、links 的 `taxonomy_compatible=null`。
- cohort 已更新為 `comparison_complete_60m_followup_complete`，`followup_checkpoints.60m` 已落檔。60m 收尾後重跑最小受影響回歸：`py -3 -B -m unittest tests.test_market_candidate_evidence tests.test_market_candidate_alignment tests.test_yaozi_surface_lifecycle tests.test_market_api -q`，34／34 通過。
- 採集器＋evidence scorer＋alignment＋API 最小回歸 35／35 通過，未執行全量測試或 Git。
- 新修正 `market_candidate_evidence` 的零候選輪：採樣 anchor 改由已驗證的 public comparison timestamp 取得，保留 exact public coverage 與事件分母；candidate rate 仍為 null。兩個新測試先重現失敗，修正後 evidence＋alignment＋API 31／31 通過；五份舊非零候選評分報告重算逐欄位一致。加上本輪已通過且未修改的 6 個採集器測試，共 37 個相關測試通過。

日期：2026-09-19；驗收更新：2026-09-20。狀態：10:00 signal sample 與本交接已於 `f2e1873` 提交；本輪新增 evidence scorer／report 尚未提交。

## 2026-09-20 驗收結果

依使用者「同意，繼續執行」接續上輪提出的驗收步驟，本輪實際執行：

- `py -3 -B -m unittest tests.test_market_candidate_alignment tests.test_market_api -v`：23／23 通過（alignment 13、API 10），0 failure／error／skip。Python 3.14.6、SQLite 3.50.4。
- 對既有 `outputs/catos-market-intel.sqlite` 與七份 2026-09-18 blackbox sample 執行唯讀 alignment：85 筆 observation、43 個唯一查詢區間、0 candidates、5／15／60 分鐘均 0 links；`complete_stored_rows`，issues 為空，沒有截斷。
- 唯讀庫存檢查：public candidates 48 筆、derivative snapshots 1674 筆、Hyperliquid observations 1342 筆、DEX observations 0 筆。
- 候選時間為台北時間 2026-09-19 10:56:32～13:10:52，晚於 9／18 黑箱事件；本次 0 links 源於沒有同時段候選，不能解讀為事件 gate 不成立或缺乏關聯。

後續同日補樣結果：

- Yaozi authenticated `/signals` 頁面可直接讀到 24h 事件時間線，因此新增 `catos-yaozi-signal-surface-sample-v1`，只保存畫面明示時間／symbol／view／category／event title。
- alignment 已支援此 schema。surface event 固定 `event_type=SIGNAL_SURFACE_EVENT`、`taxonomy_comparable=false`；public candidate link 的 `taxonomy_compatible` 為 `null`，避免把 UI 文案硬映射成私有事件 gate。
- 新增 `outputs/yaozi-signal-surface-sample-2026-09-19-overlap.json`：11 筆 9／19 11:04～13:46 signal observation，與既有 candidate DB 同日期、時間範圍重疊；實際對齊仍為 0 links。已存 JUP／BR OI candidates 晚於畫面 12:42～12:43 事件，因此不算 preceding evidence。
- 新增 `outputs/yaozi-signal-surface-sample-2026-09-20-0905.json`：保存 Today 14 個目前標的、15 筆 08:31～09:03 recent signals，以及 09:05:23 public OI baseline。第一輪尚無 5m delta，待第二輪採樣後再判斷。
- 新增兩個 signal-surface parser／alignment 測試後，alignment＋API 最小回歸為 25／25 通過。
- 原 09:05:23 baseline 因遠端 context handoff 中斷，恢復時已超過 5 分鐘容忍窗；09:14:43 採樣因此只作新 baseline，不把約 9 分 20 秒差距硬算成 5m delta。
- 09:19:44 完成有效第二輪：19 個 symbol、19 份 derivative snapshot，其中 16 個具有效 5m delta，產生 11 個 `OI_POSITIVE_CHANGE` public candidates。8 個 OI 來源為 OKX，UAI／SKYAI／VTHO 來源為 Binance；這三者雖同輪有 OKX `api_error`，snapshot provenance 已確認使用同時段 Binance OI，並非舊快照回填。
- 新增 `outputs/yaozi-signal-surface-sample-2026-09-20-0921.json` 固化 09:14:43→09:19:44 有效窗口與 11 個 candidate。candidate 的 Yaozi threshold 仍為 `unknown_unpublished`，`yaozi_event_triggered=false`；只能表達公開 OI 在 5 分鐘內正成長，不能當成已重建 Yaozi OI gate。
- Yaozi `/signals` 在 09:19 candidate 形成後，截至 09:21 最新僅新增 09:16 的全市場「★ 市場下跌 · 方向確立」，該事件沒有 symbol，故明示排除單幣 alignment。畫面最新單幣事件仍為 09:14 HOME／DASH，時間早於 09:19 candidates，因此目前仍沒有真正的 preceding candidate→後續單幣事件配對；此結果不能解讀為事件 gate 不成立。
- 新 09:21 sample 實際通過 JSON 解析與 alignment CLI：6 個可比對單幣 observation、0 個事件前 stored candidates、5／15／60 分鐘均 0 links，`complete_stored_rows`、issues 為空。這是時間順序預期結果；09:19 的 11 個 candidates 留給後續新事件做真正的 preceding 檢查。
- 10:00 再次讀取 authenticated `/signals` rendered UI；畫面最新仍為 09:55，24h 顯示 244／244，最近 1 小時 42 筆。新增 `outputs/yaozi-signal-surface-sample-2026-09-20-1000.json`，固化 09:23～09:55 共 34 筆單幣事件；只保存 UI 明示的分鐘時間、symbol、view、category 與 event title，另保留 09:16 無 symbol 的全市場事件為 excluded global event。
- 新 10:00 sample 首次出現真正的 `preceding public candidate → 後續 Yaozi 單幣 UI event` 時間配對。alignment 實際結果：`candidate_count=3`、5 分鐘 0 links／0 events、15 分鐘 4 links／4 events、60 分鐘 5 links／5 events；最大窗口的 candidate type 為 `OI_POSITIVE_CHANGE: 5`，`complete_stored_rows`、issues 為空。
- 具體配對：USELESS `public-candidate-46f76cb91aba4ba66f2fe1b16789489c` → 09:29 兩筆事件，各 lead 555,433 ms；SKYAI `public-candidate-69e35afa636d91b006b90ed30e32e168` → 09:33，lead 795,433 ms；HOME `public-candidate-48d3f69ca9160b0848240383519917fb` → 09:34，lead 855,433 ms，另同 candidate → 09:50，lead 1,815,433 ms。前三組落 15 分鐘，09:50 HOME 僅落 60 分鐘。
- `SIGNAL_SURFACE_EVENT` 仍固定 `taxonomy_comparable=false`，各 link 的 `taxonomy_compatible=null`。上述結果只證明公開 OI 正成長候選在時間上先於後續 UI 事件；Yaozi threshold 仍為 `unknown_unpublished`，不能推論已重建私有 OI gate、taxonomy parity 或任何因果關係。
- 新 sample 通過 `json.tool`；alignment CLI 在 Windows CP950 直接輸出含「我踏马来了」時會遇到編碼限制，改用 UTF-8 執行後正常完成。最小回歸 `py -3 -B -m unittest tests.test_market_candidate_alignment tests.test_market_api -v` 再次為 25／25 通過。
- 新增 `catos.market_candidate_evidence` 與 `tests/test_market_candidate_evidence.py`，把 candidate→event 個案改成可重複的 negative-control scoring。它依 `capture_anchor` 檢查 follow-up 是否完整，未走完整窗口的 candidate 固定為 `non_evaluable`，不會被誤算成 miss；另由 exact `derivative_snapshot` timestamp 讀取當輪 public symbol coverage。
- 產生 `outputs/yaozi-candidate-evidence-score-2026-09-20-1000.json`。11 個 candidates 全部與 DB persisted candidate 唯一匹配，exact public coverage 為 19 symbols，issues 為空。5m：0 hit／11 miss；15m：3 hit／8 miss，hit rate 0.272727；30m：3 hit／8 miss，hit rate 0.272727；60m：0 個可評估、11 個 `non_evaluable`，因此不輸出 candidate hit rate。
- 15m／30m hit symbols 均為 HOME、SKYAI、USELESS。candidate snapshot 後共 34 筆 captured surface events，其中 10 筆位於當輪 19-symbol public coverage；15m／30m 各有 4／10 coverage events 存在 preceding positive-OI candidate，coverage event link rate 0.400000。全 surface 則為 4／34，0.117647。這些是 descriptive link rates，不是 recall；`/signals` 當時的完整 filter type contract 與 Yaozi 私有 taxonomy 仍不完整。
- 受影響最小回歸更新為 `py -3 -B -m unittest tests.test_market_candidate_evidence tests.test_market_candidate_alignment tests.test_market_api -v`：29／29 通過。該 scorer 驗收只讀既有 SQLite 與 sample，沒有新增外部採集、交易或憑證存取。
- 後續依使用者明示「同意，請繼續執行」接續公開資料同步採集：`outputs/yaozi-active-watchlist-2026-09-20-1038.json` 共 22 個 CEX 可映射 symbols；10:39:09.944 baseline 與 10:44:09.944 comparison 各保存 22 份 derivative snapshot，comparison 22／22 具有效 5m delta，產生 6 個 `OI_POSITIVE_CHANGE` candidates：AGLD、AVA、BANK、ENA、T、ZEC。候選仍固定 `threshold=null`、`threshold_status=unknown_unpublished`、`yaozi_event_triggered=false`。
- 新增 `outputs/yaozi-signal-surface-sample-2026-09-20-1049.json`，固化 authenticated rendered `/signals` 在 10:44～10:49 的 12 筆單幣事件與 10:46 無 symbol 的全市場事件。UI 時間僅到分鐘；10:44 畫面事件解析為 10:44:00，早於 public comparison 10:44:09.944，因此不把同分鐘事件當成 candidate 後續證據。
- 10:49 AGLD `首次入池 · 異動視角` 是本輪第一個有效 5m preceding link：AGLD candidate `public-candidate-62fc22d683239bbec4bbdb3e95d2db47` → 10:49 surface event，lead 290,056 ms。alignment 實測 `candidate_count=1`，5m／15m／60m 均 1 link／1 event，`taxonomy_compatible=null`、issues 為空；這只表示時間先後，不代表已重建 Yaozi OI gate 或因果關係。
- 新增 `outputs/yaozi-candidate-evidence-score-2026-09-20-1049.json`。6 個 candidates 均與 persisted DB 唯一匹配，exact public coverage 為 22 symbols，issues 為空。5m 已完整走完：1 hit／5 miss，candidate hit rate 0.166667；hit 為 AGLD，miss 為 AVA／BANK／ENA／T／ZEC。comparison 後共 7 筆 captured surface events，其中 2 筆在本輪 22-symbol public coverage，1 筆存在 preceding positive-OI candidate，因此 coverage event link rate 1／2 = 0.500000；全 surface link rate 1／7 = 0.142857。15m／30m／60m 尚未走完整，6 個 candidates 全部 `non_evaluable`，不輸出 hit／miss rate。
- 11:01 監控 follow-up 新增 `outputs/yaozi-signal-surface-sample-2026-09-20-1101.json`，capture anchor 為 11:01:11.274+08，已跨過 10:44:09.944 candidate snapshot 的 15 分鐘完整窗口。樣本固化 10:44～10:59 共 30 筆單幣 rendered events 與 10:46 無 symbol 的全市場事件；10:59 最新為 ICP `結構撤離確認 · 漏斗崩塌(主表連動)`。candidate snapshot 後共 25 筆單幣事件，其中本輪 exact 22-symbol public coverage 內有 6 筆。
- 本輪 alignment 實測 `candidate_count=3`、5m 1 link／1 event、15m 4 links／4 events、60m 4 links／4 events，issues 為空。有效時間配對為：AGLD → 10:49 `首次入池 · 異動視角`（lead 290,056 ms）、AGLD → 10:50 `結構撤離確認 · 晉級至異動`（350,056 ms）、AVA → 10:53 `結構撤離確認 · 被風險覆蓋`（530,056 ms）、ZEC → 10:57 `降 D 級 · 主力出逃`（770,056 ms）。`taxonomy_compatible` 仍全部為 `null`。
- 新增 `outputs/yaozi-candidate-evidence-score-2026-09-20-1101.json`。15m 現已完整可評估：3 hit／3 miss，candidate hit rate 0.500000；hit 為 AGLD／AVA／ZEC，miss 為 BANK／ENA／T。15m public-coverage event link rate 為 4／6 = 0.666667，全 surface 為 4／25 = 0.160000。5m 維持 1 hit／5 miss；因 follow-up surface 已擴充，5m coverage event link rate 的分母同步擴為 6，故為 1／6 = 0.166667。30m／60m 尚未走完整，仍為 `non_evaluable`。
- 上述 15m 結果仍只屬 descriptive negative control：它證明公開 5m OI 正成長候選與後續已捕獲 UI 事件的時間重疊，不代表候選是 Yaozi 私有 gate、觸發原因或可推導私有 threshold／SMF 權重；`recall_status` 仍為 `not_true_recall_signal_surface_filter_and_event_taxonomy_incomplete`。
- 11:23 完成 30m follow-up，新增 `outputs/yaozi-signal-surface-sample-2026-09-20-1123.json` 與 `outputs/yaozi-candidate-evidence-score-2026-09-20-1123.json`。該 checkpoint 明示只保留六個 public candidates 的 post-snapshot rendered events，capture anchor 已跨過 30m cutoff 11:14:09.944；BANK／T 在 cutoff 前沒有 post-snapshot rendered event。
- 30m scorer 實測 6／6 candidates 可評估：4 hit／2 miss，candidate hit rate 0.666667；hit 為 AGLD／AVA／ENA／ZEC，miss 為 BANK／T。5m 維持 1／6，15m 維持 3／6；60m 尚未成熟，6 個 candidates 仍為 `non_evaluable`。candidate persistence `complete`、exact derivative public coverage 22 symbols、issues 為空。
- 同一 30m checkpoint 的 alignment 實測 7 筆 candidate-symbol rendered observations、4 個唯一 preceding candidates；5m 1 link、15m 4 links、60m 7 links，issues 為空，所有 `SIGNAL_SURFACE_EVENT` 仍 `taxonomy_comparable=false`、`taxonomy_compatible=null`。此 sample 是 candidate-symbol follow-up，不是全 surface census，因此其 `observed_event_link_rate`／`public_coverage_event_link_rate` 分母只包含這 7 筆 targeted observations，不與 11:01 的全 surface link rate 直接比較。
- 30m 結果仍只有時間先後與 captured-surface negative-control 意義：`OI_POSITIVE_CHANGE` 只代表公開 5m OI delta > 0；Yaozi 私有 threshold、SMF／Dealer 權重、taxonomy、gate 與因果均未知，不由 4／6 命中率反推。
- 11:47 完成 60m follow-up，新增 `outputs/yaozi-signal-surface-sample-2026-09-20-1147.json` 與 `outputs/yaozi-candidate-evidence-score-2026-09-20-1147.json`。capture anchor 11:47:53.174+08 已跨過 60m cutoff 11:44:09.944；刷新後 `/signals` 為 257／257、最近 1 小時 110 筆，最新事件 11:43。六個候選後續事件共固化 10 筆；30m 之後新增 ZEC 11:27、AVA 11:33、ZEC 11:43。
- 對 T／BANK 另外做 exact-symbol rendered UI 核對：T 24h 只有 10:03 `首次入池 · 機會視角`；BANK 只有 10:05 `資金流蓄勢 · 先行視角` 與 05:26 `降 D 級 · 主力出逃`。三筆都早於 10:44:09.944 candidate snapshot，因此 60m 仍沒有 post-snapshot BANK／T captured event。
- 60m scorer 實測 6／6 candidates 可評估：4 hit／2 miss，candidate hit rate 0.666667；hit 為 AGLD／AVA／ENA／ZEC，miss 為 BANK／T。5m／15m／30m candidate hit rate 分別維持 0.166667／0.500000／0.666667；60m targeted sample 的 10 筆 post-snapshot captured events 全部存在 60m preceding candidate link。candidate persistence `complete`、exact derivative public coverage 22 symbols、issues 為空。
- 60m alignment 實測 10 筆 candidate-symbol observations、4 個唯一 preceding candidates；5m 1 link、15m 4 links、60m 10 links，issues 為空。所有 `SIGNAL_SURFACE_EVENT` 仍 `taxonomy_comparable=false`、`taxonomy_compatible=null`；10／10 只表示此 targeted sample 內事件在 60m 窗口有 preceding public positive-OI candidate，不是全 surface recall 或私有 gate 命中率。
- 本輪公開採集只做市場 GET、Yaozi 只讀既有 authenticated rendered UI；沒有讀取或輸出憑證、沒有 OKX 帳戶 API、下單、撤單或帳戶修改。上述 hit／miss 均為 captured signal surface 的 descriptive negative control；`recall_status` 仍為 `not_true_recall_signal_surface_filter_and_event_taxonomy_incomplete`。
- 新增 60m sample／score 後重跑受影響最小回歸：`py -3 -B -m unittest tests.test_market_candidate_evidence tests.test_market_candidate_alignment tests.test_market_api -v`，29／29 通過，0 failure／error／skip；score 檔亦與 scorer 即時計算結果逐欄位相等。

本片通過專屬測試及受影響 API 回歸，達成本地修正驗收；未執行全量測試、外部採集或 Git，未修改既有資料庫。以下保留 9／19 開發紀錄，其「未驗收」描述以本節更新為準。

## 目標與已恢復脈絡

使用者要求在歷史對話遺失後接續 Yaozi 功能開發。本輪依工作區程式、既有交接與樣本重建進度，沒有恢復原始對話全文。

- 目標仍為 Yaozi 功能／資料語義的研究實作；未知私有門檻、SMF／Dealer 權重不得猜測。
- P0：public adapters、Decimal features、已知 L2／patterns、lifecycle、proof、orchestrator 與 localhost read API 已存在，不從 P0-A 重做。
- P1：Hyperliquid observation、DEX pool flow／identity／coverage、Capital Flow、Dealer／onchain 純計算與物化、public evidence candidates、dashboard 及離線 alignment 已有程式。存在程式不等於所有來源已上線或 parity 已完成。
- 最新資料工作為 `market_evidence_collect.py` 的 watchlist-based 5m bounded cadence。`outputs/yaozi-active-watchlist-2026-09-19.json` 現列 12 個 symbols，`hyperliquid_symbols` 為空。這是歷史配置，不代表本輪已確認可採集或更新。
- `catos/market_intel.py` 的 schema 常數目前是 8；舊 P0／P1 handoff 中的 schema 3 及「下一步開始 P1-A」已落後，不據此重做。
- 七份 2026-09-18 blackbox sample 與分析文件保留。既有 alignment JSON 記錄 85 筆 observation、0 candidates；本輪沒有重查實際 DB，不把該結果當作目前 coverage。

## 本輪修正：歷史事件候選查詢

具體失敗情境：原 alignment 先讀全庫最新 1000 筆候選，再於記憶體匹配歷史事件。新資料或其他幣種累積後，即使資料庫保有歷史候選，也可能被排除，產生誤導性的零 links。

最小修正：

1. `MarketIntelReader.event_candidates_for_windows()` 接受 `(symbol, start_ms, end_ms)` 閉區間，以唯讀 connection、同一讀取 transaction 查詢。
2. alignment 先解析事件，再查各事件前 60 分鐘候選。相同區間只查一次；重疊區間候選按 `candidate_id` 去重。
3. `--limit` 保留 1～1000，語義改為每個幣種／事件區間上限。多讀一筆判斷截斷；不靜默視為完整。
4. 新增 `candidate_query`：區間、上限、截斷、snapshot 語義與未知來源 coverage。`count_semantics` 區分完整 stored links 與截斷下界。
5. 原 `contract`、events、summary 欄位保留，HTTP 候選清單行為不變。`candidate_count` 現為事件區間內已載入的唯一候選數，不是全庫最新候選數。

邊界：`complete_stored_rows` 僅表示查完該區間已持久化候選，不能推論上游採樣完整、事件未觸發或因果。原始跨樣本 observation 不去重，因此 links 是逐 observation 計數，不能稱唯一市場事件數。既有時間解析仍按 sample 的年份與時區解析畫面分鐘時間；跨年與分鐘內精度不在本片修改範圍。

## 修改範圍

- `catos/market_api.py`：新增歷史窗口唯讀查詢。
- `catos/market_candidate_alignment.py`：切換查詢及補診斷欄位、CLI help。
- `tests/test_market_candidate_alignment.py`：新增 8 個回歸案例。
- `docs/market-intel.md`：更正過時進度、schema 說明與本片行為。
- 本交接文件。

未修改金融 Journal／schema、交易、風控、憑證、其他 lots 任務；未開啟既有 DB、執行網路採集、測試、編譯或 Git。市場 schema 也未變更。

## 驗收交接

依 `AGENTS.md:22` AUTONOMY 的既有分工，開發模型編寫程式與測試案例，驗證／採集／Git 由另一模型執行。本輪只閱讀修改後內容，未宣稱測試通過。

最小必要測試：

```powershell
py -3 -B -m unittest tests.test_market_candidate_alignment tests.test_market_api -v
```

新增案例涵蓋：超過 1000 筆新資料時仍能查到歷史候選、幣種隔離、5／15／60 分鐘邊界與 future 排除、剛好上限不誤報截斷、超限下界、重疊區間去重、缺資料／無事件、參數驗證，以及 WAL 同時插入時多窗口仍維持同一讀取 snapshot。全數使用暫存合成 DB，不需連網或憑證。

驗收完成前不要把本片標為已完成 DoD。Git 分組需限定本片修改；market 檔案可能已有其他未提交工作，本輪未檢查 Git 狀態，不能整個工作區一起提交。

## 下一片

本片驗收已完成。下一片沿既有方向累積同時段 Yaozi 畫面事件與公開候選資料，再使用修正後 alignment 檢查 coverage。優先補與新黑箱觀測同時段的 OI candidates；Hyperliquid 須明示追蹤 symbols，DEX 須有已驗證 pool identity 配置。現存 9／18 樣本不能與 9／19 候選硬湊成同步樣本，亦不得補造歷史事件。實際採集依有效授權與既有分工執行；確認 coverage 前，不擴充猜測性的 CEX／top-trader／funding 私有事件 gate。
