# Yaozi 開發恢復交接

日期：2026-09-19；驗收更新：2026-09-20。狀態：歷史窗口查詢修正已通過最小必要測試，並完成既有資料唯讀對齊；尚未 Git 提交。

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
