# CatOS 目前接續入口

Git 收斂（2026-09-24）：Sol 已重跑受影響測試模組與 changed/new Python compile，全部通過；將既有 Astra 未提交的 Q1／reconciliation／Demo bootstrap／trade authorization、S10、統一 shell／Yaozi 整合與 sanitized evidence 收斂為 checkpoint `8df0cbe`（`feat(v1): checkpoint validated Astra integration work`）。提交後工作樹乾淨；本機 visual QA/runtime/stage patch 產物保留在磁碟並以 `.git/info/exclude` 排除，不刪除、不納入 repository。尚未 push。

Production bootstrap inputs（2026-09-24）：使用者已核准依 Sol 建議執行，新增 `catos/demo_production_inputs.py` 鎖定 `sma-trend-btc-usdt-swap-v1`、15m／warmup 2、BTC-USDT-SWAP 真實 public contract 規格、legacy `fixture_budget=100` 與既有 3.0x／50%／10%／20% risk limits。10:37:53+08:00 無 credential public instruments 查詢確認 `state=live`、linear、`ctVal=0.01`、`ctMult=1`、`tickSz=0.1`、`lotSz=minSz=0.01`；新增 fail-closed metadata verifier，bootstrap 前須重驗。專屬 3/3、bootstrap 11/11、preflight 9/9，共 23/23 OK；`py_compile`、`git diff --check` 通過。實際 production DB/binding 路徑仍不存在，未執行 private collection 或交易 write。

最新接續（2026-09-24）：使用者已核准 D1-Q1，`quiescent interval exact-equivalence E₀` 已完成 local implementation／synthetic verification。`risk.BaselineEvidence` 現同時接受既有 synthetic midnight 與 `demo_quiescent_midnight_equivalence_v1`；Q1 evidence 綁 expected UID、Taipei day start/cutoff、report/balance/collection/zero-event digests。`orders_history` window provenance 已補為 `cTime + after_order_id`，fills/bills 維持 `ts + after_bill_id`。Q1 builder 只在完整 formal collection、single-USDT、零 position/order/algo/fill/bill、完整 window/page chain 與 F1/S1 成立時產生 basis，並在 D3 provider 前由既有 Supervisor→Journal 單 writer 提交；任何缺口均不寫入。production DB/binding 仍未建立，`bootstrap_ready=false`、`reconciled=false`、`trade_authorized=false`。

所屬工作目錄：`C:/Users/user/Desktop/CatOS_Astra`；負責交易核心、風控、帳務與最終單一 localhost 網站整合。本入口只代表 Astra 工作樹；`CatOS_Yaozi` 的情報來源進度以該目錄的 `docs/current-handoff.md` 為準。接續 Astra 時不修改 Yaozi 來源目錄。

更新日期：2026-09-24。當前片：**D1-Q1 已核准並實作；production bootstrap planning/operation 仍 fail closed，因現有 production 24h evidence 含 7 筆 bill（6 筆非 USDT）且採集早於新的 orders-history window provenance，不能倒補為 Q1 E₀。實際 production ledger／binding instance 仍未建立**。operation 不新增第二個 Journal writer，只編排 planning gate、Supervisor exclusive create、binding exclusive save/verify。既有 binding/preflight 行為不變：binding 不保存 raw UID，resume 靜止 DB 使用 `mode=ro&immutable=1`，live WAL 完整 sidecar pair 使用 `mode=ro`。formal reconciliation 與 trade authorization 仍未成立。

既有 inventory 仍只有 5 個 QA／scenario DB，全部為 `environment=local-sim`，account_id 為 `fake-account` 或 `s8-example-account`；它們明確排除為 catOSv1 Demo 證據，不得為了滿足新 contract 而替它們建立 production binding。新 contract 解決的是「如何證明指定 expected UID／Demo scope 對應指定 DB」與「缺證明時如何 fail closed」，沒有憑空建立 production ledger，因此 `local_unknown`／ownership blocker 仍保留。

本輪 Q1 直接受影響驗證合計 **188/188 OK**：Q1 10、Verified E₀ lifecycle 22、formal Demo reconciliation 33、reconciliation gate 17、Demo ledger bootstrap 11、Supervisor reconciliation 15、OKX collection 13、HTTP transport 25、account report 42。另 `py_compile` 通過；全部使用 temporary DB／synthetic evidence，未接 OKX private network、未修改既有 trading DB/schema、未輸出 raw UID/credential、未 commit/push。先前 151/151 等數字保留為歷史驗證，不冒充本輪重驗。

使用者其後明確同意執行新的 production Q1 read-only collection。本輪已完成一批固定 `catOSv1`／Demo／`BTC-USDT-SWAP` 的 40 GET：expected UID、dedicated subaccount、acctLv=2／`net_mode` 驗證通過，collection complete；positions／ordinary pending／algo pending／orders history／fills／algo history 均為 0，`orders_history` 已實際保存 `cTime + after_order_id` window provenance。bills 仍為 7 筆，因此 `build_demo_quiescent_midnight_basis()` 正確回傳無 basis，blocker 為 `balance_changing_bill_present` 與 `unknown_external_flow`。sanitized evidence：`outputs/catosv1-demo-production-q1-collection-evidence-20260924.json`。本次只做 GET；未建立 production DB/binding，`reconciled=false`、`trade_authorized=false`。

本輪沿用 `tools/demo_subaccount_evidence.py` 的明示 Demo credential loader，未切換其他 credential source。清理後再次 bounded 24h accounting 40 GET：positions／ordinary pending／algo pending／orders history／fills／algo history 皆 0，balance=1，bills=7；record diagnostic=0，`unsupported_collateral` 已消失。7 筆 bills 的 subtype 全已知：`1/11 Transfer in` 4、`1/12 Transfer out` 3，forbidden=0；但其中 6 筆是非 USDT，現行 `observed_external_flow_usdt` contract 不做跨幣換算，因此 `unknown=6`。最後一筆非 USDT bill 為 2026-09-24 07:07:33+08:00；若後續不再有非 USDT balance change，最早 2026-09-25 07:07:33+08:00 後 trailing 24h 可自然變為 unknown=0。sanitized evidence 已更新，不保存 raw payload、raw ID、credential 或 monetary value。

真實 balance 的 `acctLv=2 details[].liab` N/A sentinel 已完成閉環：decoder 將缺欄／`null`／空字串保留為 `None`，僅 verified acctLv=2 視為 N/A；production 40 GET 已實證 diagnostic=0。多幣資產不是 decoder placeholder：BTC／ETH／OKB 當時均為真實非零，因此沒有放寬 collateral policy，而是使用 Demo-only cleanup 把它們從 Trading Demo balance 清除。新 tool 專屬 6/6、相關 `test_demo_subaccount_evidence + test_account_report + test_okx_http` 71/71 OK；原受影響回歸 116/116、`py_compile`、scoped `diff --check` 亦保留通過證據。

分類縮減已由使用者核准並實作：全目錄 coverage 僅提示；完整採集的實際流水遇 unknown／forbidden 仍阻擋。gate 不再因 catalog complete=false 一律拒絕；classification ID、完整採集、E₀、ownership 與交易授權檢查保留。17 gate + 30 orchestration + 42 report = **89/89 OK**。詳見 [政策與驗證](classification-observed-flow-policy-20260923.md)。此決策取代下方所有「19 unknown 本身為 blocker」與「縮減待定」歷史敘述。

歷史：舊 key 曾有 UID 不符的 config-only 結果，使用者澄清該 key 是 Live；其後新 Demo key 首次檢查曾回 `acctLv=1`。使用者已自行調整模式，以上方最新 10 次 GET 證據為準。

前輪新增獨立 `tools/demo_subaccount_evidence.py`、`tests/test_demo_subaccount_evidence.py` 與 evidence 文件；其專屬及既有採集回歸 **20/20 OK**。分類縮減仍依已核准政策：未出現的 19 unknown subtype 不是獨立 blocker；只有完整採集實際遇到 unknown／forbidden 才阻擋增倉。本輪沒有修改交易程式、既有 DB/schema、Yaozi/Lot/market，也沒有 reset／clean／commit／push。以下保留前片完成紀錄，均非本輪重驗。

前片：**第一個安全策略閉環 local-synthetic integration acceptance 已完成**。既有 formal reconciliation、`DemoTradeGrant`、Worker／Supervisor／Execution 與 restart responsibility reconciliation 已在同一條 temporary-DB/FakeExchange 路徑通過；沒有新增 production runtime 路徑，也沒有用 synthetic evidence 解除 production blocker。

## 本片現況與角色

- 新增 `tests/test_safe_strategy_loop.py`：synthetic formal reconciliation PASS 後，Closed Bar 經 Worker 產生 entry intent；無 `DemoTradeGrant` 時 0 transport；安裝有界一次性 grant 後由既有 Supervisor/Execution 路徑以固定 tag 送入 `FakeExchange` 並取得 synthetic fill；restart 後 active grant 不恢復、consumed authorization tombstone 仍在，再以 remote position/order/fill responsibility evidence 完成 formal reconciliation。
- 本片沒有 production runtime 程式差異；既有交易底座已能完成上述 integration acceptance。專屬 1/1 OK；`test_safe_strategy_loop + test_demo_reconciliation + test_demo_trade_authorization + test_supervisor_reconciliation` 直接相關回歸 63/63 OK。
- 本片只使用 temporary SQLite、FakeExchange、FakeClock 與 synthetic evidence；未開 project DB、未改 schema、未連 OKX、未讀 credential、未修改 `CatOS_Yaozi`、未 commit／push。詳細見 [安全策略閉環 handoff](catos-safe-strategy-loop-handoff-20260923.md) 與 `outputs/catos-safe-strategy-loop-verification-20260923.json`。
- production blocker 更新：classification subtype 已非目前問題；清理後 7 筆 bill 均為已知 `1/11` 或 `1/12`。因 6 筆非 USDT transfer 無安全 USDT 換算，現行 contract 仍標 unknown=6；若帳戶保持單一 USDT，2026-09-25 07:07:33+08:00 後 trailing 24h 可自然清空。D1-Q1 已核准並完成程式實作，但 production Q1 尚未成立：既有採集有 bill，且缺新 `orders_history` window provenance，不能倒補。dedicated Demo identity/current responsibility 已通過；Demo balance cleanup write 已獲本輪明確授權並完成，但交易下單授權與 `trade_authorized` 仍未因此成立。
- 新增 `catos/app_shell.py`，提供同一 localhost 頂層「量化交易／Yaozi 情報」導覽；`market_api.create_app()` 支援可選 `strategy_status_provider`，只新增 GET `/quant` 與 GET `/system/strategy-status`，沒有 start/stop mutation route。
- `supervisor_status_provider()` 只讀既有 `LocalSupervisor` 狀態，不新增第二個 lifecycle owner、不呼叫 `start()`／`close()`／交易路徑。未注入 provider 時量化頁明示 `not_materialized`。
- 新增 `tests/test_app_shell.py`：真實 local-sim `LocalSupervisor` 在第一根 synthetic bar 後，經 root／quant／Yaozi／status requests、重複 root request 與 Web client teardown，revision／checkpoint 不變；同一 Supervisor 隨後成功處理第二根 bar。
- 本片專屬與受影響回歸 `tests.test_app_shell + tests.test_yaozi_social_runtime_sync + tests.test_market_api` 共 44/44 OK；`py_compile` OK。Crawl4AI 實際渲染 `/quant` 與 `/dashboard` 成功；root shell 可抓到兩個頂層分頁。`browser-use` 本機 Chrome/CDP 啟動失敗，故未把其失敗冒充應用錯誤；互動語意由專屬 lifecycle test 覆蓋。
- Astra 已按區段補丁整合 `market_decision.py`、`market_api.py`、`market_dashboard.py`、`market_social.py`、`market_lifecycle.py` 及 market 測試；未整檔覆蓋 Dashboard。
- 已帶回 decision API／Compare／單幣、Personal watchlist、Push／Whistle／Social／Account 本機能力；Social explicit identity registry 現已由原 V1–V5 續接到 **V9**。
- V9 follow-up 來源固定為 `CatOS_Yaozi` 現行工作樹：`market_social.py` 帶回 V6–V9、current V9 alias／runtime mapping entrypoint；`market_api.py` 的 `/intel/social` 回傳 `identity_registry`；Dashboard Social 頁分開顯示 identity readiness 與 materialized raw metrics；新增 V9 runtime sync 專屬測試。Astra 不需執行期依賴 Yaozi worktree。
- 來源為 `CatOS_Yaozi` 現行工作樹，包含未提交成果。Sol 本輪已重新核對 branch `yaozi/dev-v0.7`、HEAD `a4fb910` 及 merge-base `3925759`。
- V9 follow-up 的 5 個程式／測試檔在 CRLF/LF 正規化後與 Yaozi source 完全一致；另把 registry V5→V9 evidence chain 帶回 Astra `outputs/`，使 runtime 回傳的 V9 `evidence_path` 在本工作樹可解析。37 個既有僅換行差異檔與其他 capture／audit／report tools/tests 仍保持原樣。
- Sol 已核對 `CatOS_Yaozi` branch `yaozi/dev-v0.7`、HEAD `a4fb910d2b8e6de6aaf0a40a9c0d3a716873cab6`、merge-base `3925759d16771b9cbe8fac709c0b5dc355772865`；8 個整合檔正規化後與來源及 manifest SHA-256 全數一致，0 mismatch。
- 本輪 V9 follow-up 實跑 `tests.test_yaozi_social_runtime_sync + tests.test_market_social`：25/25 OK；既有 Social Dashboard/API regression 1/1 OK；`py_compile` OK。歷史 79/79 仍只代表原 V5 整合驗收，不冒充本輪重驗。
- 本輪以隔離 schema-14 synthetic DB 啟 Astra localhost；`/intel/social` 回 `registry=v9`、34 explicit identities、coverage `34 resolved / 242 ambiguous / 291 unverified / 167 missing`，同時 `items=0`、`source_runs=0`、`social_heat=null`、`yaozi_heat=null`。Crawl4AI 實際渲染 Social 頁成功；只有 favicon 404 console 訊息。
- 本片驗收 **PASS**。這代表 **Astra 已接受 Yaozi Social V9 runtime/Web sync**；仍不代表 2026-09-23 完整 live social distribution，也不代表統一量化／情報頂層網站、量化策略不中斷或策略生命週期已驗收。

細節見[本片交驗與驗收指令](catos-yaozi-integration-handoff.md)、[整合契約](catos-yaozi-integration.md)、[原始整合 manifest](yaozi-integration-manifest-20260923.json)、[V9 follow-up manifest](yaozi-v9-integration-manifest-20260923.json) 與 `outputs/yaozi-v9-astra-integration-verification-20260923.json`。

## 授權與不可碰的工作

- 保留兩邊全部其他未提交內容；不修改 Yaozi 來源工作目錄，不整包覆蓋、不跨 worktree import、不清理工作樹。
- Astra 編寫，Sol 驗收與 Git。沒有 commit／push 授權。本片已依使用者明確授權使用指定 Demo loader 完成上述唯讀 GET；授權不包含 Demo／Live write、替代 credential source、既有 DB/schema mutation 或後續未明示的新採集。
- 本片不修改交易、Lot、Demo grant／額度、風控；情報仍無交易權限。統一 shell 與 browser/backend lifecycle independence 已完成 local-sim 驗收；真正 Demo／Live 交易接線與 Web start/stop contract 仍未物化。
- 本片相關未提交內容為上述 8 個程式／測試檔與整合交驗、manifest、SMF 歷史說明、入口及入口歷史保存；Sol 已核對工作樹，未清理或覆蓋其他既存未提交內容。

## 交易主線保留狀態

- 主線仍為 formal reconciliation → 第一個安全策略閉環。Demo Trade Authorization 的 B1 follow-up 已完成 local synthetic 實作並由 Sol 於 2026-09-23 獨立驗收 PASS；詳見[額度決策與實作](demo-trade-budget-decision.md)與[審查](demo-trade-authorization-review.md)。本輪重新執行 `test_demo_trade_authorization` 17/17 OK；直接受影響七模組 `test_demo_trade_authorization`、`test_execution`、`test_execution_supervisor`、`test_supervisor`、`test_protection`、`test_supervisor_reconciliation`、`test_verified_e0_lifecycle` 合計 120/120 OK。`git diff --check` exit 0，僅既有 LF/CRLF warning。未沿用歷史 11/11、90/90 或 263/263 作本輪證據。
- 2026-09-23 B1 現況：`DemoTradeGrant` 使用 `max_entry_mark_notional_usdt`，以送單前 Supervisor-owned quantity × contract base quantity × 當下有效 mark 做 Decimal 計價。prepare 到 handoff 間若 mark／risk snapshot 改變、到期或撤銷，request 會在 transport 前 durable `ABORTED`；最終檢查到 consumed 標記之間無 await。transport 一旦進入，REJECTED、逾時／UNKNOWN 等結果都不返還同 ID；撤銷／重新 reconciliation 後仍不能用已 consumed ID 重裝。未進 transport 的 ABORTED 不消耗，但仍需重新 reconciliation。restart 不恢復 active grant；已進 transport 的 ID 會由既有 execution order 內部 metadata 恢復 consumed tombstone，同 ID 無法靠 restart 重用，且未修改 DB schema。reduce-only cleanup、cancel/query 與 P6 維護維持 T2-A。此上限不是實際成交額、費用或虧損硬上限。保留 local-only、FakeExchange／FakeClock／temporary DB 邊界，未碰 OKX network、credential、既有 trading DB、Lot／market／Yaozi／前端、commit／push。
- B1 diff、17 案專屬測試與直接受影響回歸已由 Sol 獨立驗收通過；下一片回到 production classification、verified E₀、dedicated Demo subaccount／foreign responsibility 等既有 blocker。不得由本片直接延伸到真實 Demo POST、連續多次 entry 累計預算或跨 restart grant ledger。
- production classification 已依 2026 年 OKX Stock Perpetual corporate-action 官方文件，將 `37/422-427` 六個 value-neutral 持倉重整 subtype 收斂為 `internal`；依現行 API guide 對 `274/275` 的明確 Spread trading close long/short 定義，將 `24/274,275` 收斂為 `internal`；本輪再依 API guide／changelog 與 Forced Repayment／Auto Crypto Conversion 官方文件，將 `4/376,377` Collateralized borrowing auto conversion buy/sell 收斂為 `internal`。最新 coverage 166/185（10 external、102 internal、54 forbidden、19 unknown），`complete=false`。其餘 `1/290,292`、`4/393,394`、`12/276,277`、`22/259,260`、`26/441-446`、`37/421,432-435` 保持 unknown，不猜 account scope／空白 subtype。exact-midnight E₀ 來源、dedicated Demo subaccount／foreign responsibilities 及真正 Demo write 授權／接線等阻礙仍保留。
- D1-A exact-midnight E₀ 公開證據調查已完成：OKX `account/balance`、`account-position-risk`、`asset-valuation` 均只有當下狀態／update timestamp，沒有指定歷史 timestamp 的完整 account-equity query；private WS snapshot 是當前推送，不是歷史來源；Account Statement 的官方 record time 以 UTC 為基準且預設 cutoff 00:00 UTC，不等於 Asia/Taipei 00:00；Position snapshot 缺完整 account `totalEq`；PoR snapshot 為月度。故未找到符合 D1-A 的公開 production source，不能用 S1 observation、`uTime`、午夜附近 balance、UTC statement 或 bills 倒推替代。formal reconciliation 繼續 fail closed。完整證據見 [Verified E₀ lifecycle assessment](verified-e0-lifecycle-assessment.md#7-2026-09-23-d1-a-production-source-公開證據調查)。
- `4/376,377` 收斂後實跑 classification 直接受影響驗證：`test_okx_readonly + test_account_report` 63/63 OK；`test_reconciliation_gate.py` 16/16 OK。`git diff --check` exit 0，僅既有 LF/CRLF warning；本輪碰到的三個 untracked 文件無 trailing whitespace。
- dedicated Demo subaccount／foreign responsibility 已完成 local contract 強化：formal account alias 現為 `catOSv1`；除了 `uid == mainUid` 會以 `scope_mismatch` 阻斷，`uid != mainUid` 但 UID digest 不等於綁定 expected UID 也同樣阻斷。遠端未歸屬 position/order/algo、本地 unresolved／UNKNOWN、responsibility digest race 的既有 fail-closed 規則不變。synthetic happy path 只驗程式接線，不能替代 production ledger/binding instance 或真實 identity evidence。
- 本片最小驗證：`python -B -m unittest discover -s tests -p test_demo_reconciliation.py -v` 30/30 OK；`python -B -m unittest discover -s tests -p test_reconciliation_gate.py -v` 16/16 OK；`tests.test_account_report` 42/42 OK。首次把三者用 dotted module 合併執行時，兩個測試檔因 repo 既有 `test_ipc` import-root 方式載入失敗，改用既有 `discover -s tests` 後全數通過；不是產品測試失敗。
- 完整前一版入口與歷史 229／263 等驗證證據已保存於[整合前入口](catos-handoff-before-yaozi-integration-20260923.md)，不得當成本輪重驗結果。

## 下一步

身份／模式、current responsibility、balance decoder 與單一 USDT collateral 現已有真實 Demo evidence。2026-09-24 使用者已核准依 Sol 建議鎖定 production bootstrap inputs：`sma-trend-btc-usdt-swap-v1`、既有 SMA v1、15m／warmup 2；OKX public metadata 核對後 contract 固定 `base_per_contract=0.01`、`tick_size=0.1`、`lot_size=min_size=0.01`；`fixture_budget=100` 僅作 risk mode legacy metadata identity；risk limits 固定 3.0x／50%／10%／20%。實作入口 `catos/demo_production_inputs.py`，bootstrap 前須再次驗 public instrument metadata。剩餘 bootstrap blocker 收斂為：**現有 trailing 24h 仍有 6 筆非 USDT transfer（最早 2026-09-25 07:07:33+08:00 自然清空）與尚未取得符合 Q1 的全新 production zero-event/window proof**。production ledger/binding instance 仍不建立，formal reconciliation 與 trade authorization 仍 false。

下一個 production Q1 機會仍需帳戶持續 quiescent。由於本輪新採集仍觀測到 7 筆既有 bills，Q1 未成立；依目前 trailing-24h formal collection 與既有最後非 USDT bill 時間，最早在 2026-09-25 07:07:33+08:00 後再以新的明確 read-only 授權重採，才有機會同時清除既有 accounting unknown 與 Q1 bill blocker。新的 collection 仍須保存 `orders_history cTime/after_order_id` provenance，且 current position/order/algo、fills/history/bills 均符合 Q1 fail-closed 條件。

接續指令：

> 先讀 AGENTS.md、docs/current-handoff.md、docs/demo-production-bootstrap-inputs-20260924.md、docs/demo-e0-quiescent-equivalence-decision-20260924.md、catos/demo_production_inputs.py、catos/risk.py、catos/demo_reconciliation.py、catos/demo_ledger_bootstrap.py、tests/test_demo_quiescent_e0.py 與 outputs/catosv1-demo-q1-e0-verification-20260924.json。production bootstrap inputs 已核准並鎖定；D1-Q1 已核准並完成 local implementation：Q1 10/10，直接受影響回歸共 188/188 OK；production DB/binding 仍不存在，現有 production collection 因有 7 筆 bill 不能建立 Q1。下一步僅在取得新的明確 production read-only 採集授權後採集全新 Q1 evidence，並於 bootstrap 前重驗 OKX public instrument metadata；不得自行讀 credential／建立 production instance／發交易 write／修改既有 DB/schema／碰 Yaozi/Lot/market／push。
