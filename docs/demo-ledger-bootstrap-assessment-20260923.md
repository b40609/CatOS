# catOSv1 ledger 初始化與 binding 建立流程

更新日期：2026-09-24（承接 2026-09-23 切片）。階段：流程 assessment、唯讀 preflight、production bootstrap planning contract 與受 planning gate 約束的 bootstrap operation 均已由 Sol 獨立驗收；其後已完成指定 Demo 的真實唯讀 identity/current-responsibility 10 GET 與 bounded 24h accounting 40 GET。實際 production 帳本仍未建立。Git 提交／push 本輪未授權；Demo write 仍未授權。

## 結論與具體失敗情境

現有 binding 可證明設定的 UID digest、scope、DB path 與 metadata 一致，不能證明帳本歷史完整、帳戶沒有舊責任或 E₀ 合格。建立空 DB 後直接解除 ownership／UNKNOWN blocker，會把「沒有記錄」誤認為「沒有責任」。因此初始化只產生待對帳的本地儲存，不能直接授予 production ledger 資格或交易權限。

另一個具體風險是以 `LocalSupervisor.start()` 檢查既有 DB：此入口會寫入及可能遷移 schema。最小做法是先唯讀預檢，首次建立只允許全新明示路徑；既有 QA DB 不得轉正。不要新增第二套帳本、writer 或交易出口。

## 現行程式依據

| 現行入口 | 已有行為 | 對初始化的限制 |
| --- | --- | --- |
| `catos/account_lock.py::AccountLock` | 僅 local-sim；帳戶鎖獨立於 DB path；持久記錄指定 DB | 不同 DB 或已綁定 DB 遺失時拒絕，不能清鎖或重建繞過 |
| `catos/journal.py::Journal.__init__` | 新 DB 建立既有 schema；WAL/FULL；初始 RECONCILING；舊版可能遷移 | 不是唯讀檢查入口；fixture_budget 必須為正 Decimal，不能當成真實權益或 E₀ |
| `catos/supervisor.py::LocalSupervisor.start` | 取得帳戶鎖，單 writer 開 Journal，註冊 Bot，再綁定 DB；`require_new_database=True` 時在鎖內 exclusive create DB 路徑 | bootstrap operation 沿用此唯一 writer；一般既有啟動預設行為不變 |
| `catos/supervisor.py::LocalSupervisor.__init__` | exchange 僅接受帳戶相符的 FakeExchange | 不能把本地初始化稱為 Demo execution runtime 已完成 |
| `catos/demo_ledger_binding.py` | make/load/verify；外部 JSON contract；metadata 唯讀驗證 | make_binding 不建立 DB，也不保存檔案；驗證 metadata 不等於驗證完整 Journal schema |
| `catos/demo_reconciliation.py::run_formal_reconciliation` | collection 前驗 binding，後續檢查 UID、帳務、E₀ 與責任；當前 trade_authorized 永遠 false | binding 成功只允許進入後續檢查，不等於對帳或交易通過 |

`binding_id` 是 payload 的 SHA-256 一致性檢查，不是數位簽章或來源認證。expected UID digest 必須來自明示且已核對的帳戶識別設定，不能從待驗證 binding 本身抄回來當獨立預期值。

## 最小流程

1. 明示輸入：全新 DB 路徑、外部 binding 路徑、獨立 expected UID digest、Bot/config、Decimal fixture_budget 與既有 risk limits。alias 固定 catOSv1，remote environment 固定 demo，storage environment 沿用 local-sim。不讀取憑證；不自行填假 UID、假風控權益或任意正式路徑。
2. 唯讀預檢：已由 `catos/demo_ledger_preflight.py` 實作 `create`／`resume`。首次建立遇 DB、binding 或殘留 WAL/SHM 任一已存在即拒絕，不覆寫、不清理；五個既有 QA DB 依 canonical path 明確排除。`resume` 在無 sidecar 的靜止 DB 使用 `mode=ro&immutable=1`，已有完整 WAL/SHM pair 時使用 `mode=ro` 以觀察 live WAL；WAL 模式由 SQLite header 驗證，sidecar pair 不完整 fail closed。其後驗 binding、v7 schema、metadata、Bot/config、ownership/protection、fixture budget 與 risk limits，不呼叫 Journal／Supervisor 嘗試修復或遷移。AccountLock 持久 binding 也只讀檢查；不同 DB、破損或僅殘留起始 byte 的 incomplete binding 均 fail closed。
3. 首次建立：沿用 Supervisor 帳戶鎖與唯一 writer；在鎖內重檢路徑，採排他建立以避免檢查後被其他檔案取代。沿用既有 schema，不另加表、不遷移既有 DB；不得以 FakeExchange 的餘額、position 或 fill 作正式帳務證據。
4. 產生 binding：新 DB 初始化成功後，建立 immutable contract，執行 runtime binding 驗證，再以不覆寫方式保存 JSON；輸出僅含 digest／binding ID／狀態，不保存 raw UID。持久化失敗即維持未完成狀態，不清除殘留檔或解除風控。
5. 完成初始化：只回報 ledger_initialized 與 binding_verified 等局部結果；reconciled=false、trade_authorized=false。新空帳本不清除本地歷史／ownership 證據缺口，也不補出 balance、fills、bills 或 D1-A E₀。
6. 後續正式對帳：由獨立授權的採集流程取得同一 expected UID 的完整證據，沿用既有 classification、freshness、ownership、E₀ gate。未使用的 catalog unknown 不阻擋；實際完整流水的 unknown／forbidden 仍阻擋增倉。Demo write 仍需獨立授權，不能由初始化隱含開啟。

### Production bootstrap planning contract

`catos/demo_ledger_bootstrap.py` 已把上述首次建立前置條件收斂成純唯讀 contract。production 目的地固定為工作目錄下 `data/catosv1-demo/state.sqlite3` 與 `data/catosv1-demo/ledger-binding.json`；expected UID digest 必須由獨立 `operator_verified_demo_uid.v1` 來源明示傳入，Bot/config、Decimal fixture_budget 與 risk limits 也必須由 caller 明示，不從 QA DB、binding 或遠端空集合反推。

歷史責任銜接只接受 `production_readonly.v1` provenance，且同一 UID/scope 證據必須同時滿足：identity 與 account mode 已驗證；account config、balance、positions、ordinary pending、algo pending、orders history、fills、bills、algo history 均完整；當下 position/order/algo responsibility 皆為空；實際完整流水 unknown=0、forbidden=0；E₀ 必須通過 `risk.is_verified_baseline()` 的 authorized source contract（目前可為 D1-A direct midnight 或已核准 D1-Q1 quiescent exact-equivalence）；collection 與 E₀ evidence ID 均存在。缺任一條件即 `bootstrap_ready=false`。

`bootstrap_ready=true` 只表示已授權的唯一 writer 具備進入 create 操作的前置條件，不表示 DB 已建立、binding 已驗證、formal reconciliation 已通過或交易已授權。planning result 固定回報 `ledger_initialized=false`、`binding_verified=false`、`reconciled=false`、`trade_authorized=false`。

### Production bootstrap operation contract

`bootstrap_production_ledger()` 每次 mutation 前重新執行上述 planning contract；`bootstrap_ready=false` 時不建立任何目標路徑。通過後建立 `LocalSupervisor(..., require_new_database=True)`，由 Supervisor 先取得既有 account lock，再在鎖內以 exclusive create 保留全新 DB 路徑，之後仍由既有 `Journal` 建立 schema、risk state、Bot/ownership/protection 並完成 account→DB persistent binding。沒有第二個 SQLite writer，也沒有 exchange、Worker 或 reconciliation 呼叫。

DB 初始化成功後，operation 依同一 expected UID digest 建立既有 immutable binding payload，先以 in-memory proof 執行 `verify_runtime_binding()`；通過後才以 exclusive create 保存 JSON、flush/fsync，再 reload 實際檔案並重新執行 runtime verification。DB race 或 binding race 都拒絕覆寫；任何中途失敗保留已建立的 DB、account binding 或衝突檔供人工檢查，不自動刪除、重試、搬移或重綁。成功結果只回報 `ledger_initialized=true`、`binding_verified=true`，固定 `reconciled=false`、`trade_authorized=false`。

## 失敗與重啟

- DB 已建立而 binding 尚未保存：保留現場，回報初始化未完成；不得自動刪除 DB、換路徑、重新建立或採信空帳本。
- binding 已保存但 DB 遺失／path 或 metadata 不符：沿用 fail closed，不從 binding 自動重建。
- 已存在帳戶鎖的持久路徑與新路徑不同：沿用 AccountLock 拒絕；不搬動、不重綁、不刪鎖。
- 既有帳本恢復：先以 mode=ro 觀察 WAL 並核對 binding 與 schema，再交由已授權的 writer 開啟；不得在本輪對既有 DB 執行 start。恢復不重設 latch、不恢復 active grant、不略過 UNKNOWN 或 reconciliation。
- 排他建立、DB 初始化、帳戶鎖綁定與 JSON 保存不是一個跨檔案交易；任一中斷必須可辨識為未完成。最小方案採明確失敗與保留現場，不新增自動修復框架。

## 真正 bootstrap 前仍需具體化

2026-09-24 使用者已核准依 Sol 建議鎖定 production bootstrap inputs；單一機器可讀來源為 `catos/demo_production_inputs.py`，決策與 public instrument snapshot 見 [production bootstrap inputs](demo-production-bootstrap-inputs-20260924.md)。固定 Bot 為 `sma-trend-btc-usdt-swap-v1`，既有 SMA v1 使用 15m／warmup 2；BTC-USDT-SWAP contract 依當日 OKX public metadata 固定 `base_per_contract=0.01`、`tick_size=0.1`、`lot_size=min_size=0.01`；`fixture_budget=100` 僅為 risk mode 下的 legacy metadata identity；risk limits 沿用 3.0x／50%／10%／20%。bootstrap 前仍須重新核對最新 public instrument metadata，漂移即 fail closed。

指定 Demo 的 expected UID digest／dedicated subaccount／`net_mode` 已由 production read-only 證據核對；清理後 24h accounting 當下 responsibility 為空、fills=0、bills=7，其中 6 筆非 USDT transfer 仍使現行 accounting contract `unknown=6`、forbidden=0。D1-Q1 已完成程式與 synthetic verification，但既有 production collection 有 bill，不能建立 Q1 E₀；因此實際 `bootstrap_ready` 仍不能成立。production ledger/binding 仍未建立。

bootstrap operation 程式路徑已完成，且沿用現有 Supervisor writer；實際 production 呼叫仍被 historical responsibility/Q1 planning contract 阻擋。preflight／planning／synthetic operation／Q1 local PASS 均不能當作 production E₀、formal reconciliation 或交易授權證據。

2026-09-24 真實唯讀 evidence 已把「完整 accounting 尚未採集」更新為完整 40 GET manifest。`details[].liab` N/A sentinel 修補已由後續 production 40 GET 實證 record diagnostic=0。接著依使用者明確 Demo write 授權，以新建 fixed-host/fixed-endpoint operator maintenance tool 呼叫 Demo-only `POST /api/v5/account/demo-adjust-balance` 的 `reduce`，在重驗 expected UID／dedicated subaccount／net_mode／空 positions/orders/algo 與各資產完全可用、無 liability/frozen 後，只清除 BTC／ETH／OKB，USDT 不調整；post-verify 成功。再跑 40 GET 後 `unsupported_collateral` 消失，balance 已符合 acctLv=2 單一 USDT contract。

清理後 24h bills 共 7 筆，官方 code 全是已分類 `type=1` Transfer：`subType=11 Transfer in` 4 筆、`subType=12 Transfer out` 3 筆；沒有 forbidden subtype。現行 accounting contract 對非 USDT bill 即使 subtype 已知仍不做匯率換算，因此 6 筆非 USDT transfer 仍計為 unknown，這是幣別算術邊界而非 classification catalog 缺口。最後一筆非 USDT bill 為 2026-09-24 07:07:33+08:00，若不再產生非 USDT balance change，trailing 24h 最早於 2026-09-25 07:07:33+08:00 後自然清空；不需放寬 Decimal／USDT 帳務政策。D1-Q1 已核准並實作，但只接受從 Taipei 00:00 到 cutoff 完整零 bill／零責任／零成交的新 collection proof，不能使用目前這 7 筆 bill 的歷史 evidence。

## 本片交驗

本輪 bootstrap operation 最小驗證：`test_demo_ledger_bootstrap.py` 11/11 OK、`test_demo_ledger_preflight.py` 9/9 OK、`test_demo_ledger_binding.py` 4/4 OK、`test_supervisor.py` 14/14 OK，共 38/38；`py_compile` 與 scoped `git diff --check` 通過。新增案例包含：gate 未就緒時 0 建立、成功 temporary bootstrap 後 resume preflight 可驗 schema/binding、planning 後 DB race 不覆寫 sentinel、DB 已初始化後 binding race 保留 ledger 與衝突 binding 並使後續 create fail closed。所有 SQLite mutation 只發生於 temporary test directory；實際 `data/catosv1-demo`、`state.sqlite3`、`ledger-binding.json` 均仍不存在。本輪未連網、未採集、未讀 credential、未發 Demo／Live write、未修改既有 production DB/schema、未碰 Yaozi/Lot/market、未 commit/push。

Sol 於 2026-09-24 對 bootstrap operation 做獨立 acceptance：重新逐模組執行上述 11+9+4+14 = 38/38 OK，`py_compile` 與 scoped `git diff --check` 通過；另執行不落 production 路徑的 temporary adversarial acceptance。額外確認：`bootstrap_ready=false` 時在 `LocalSupervisor` 建構前即拒絕且 0 target path；成功 bootstrap 不呼叫 `reconcile()` 或 `authorize_demo_trading()`；落盤後 metadata 為 `catOSv1/local-sim/100`、control 為 `RECONCILING`、ownership 的 position/evidence/reconciled revision 初始皆為 NULL、`execution_mode` 空集合；binding 不含 raw UID；一般 `LocalSupervisor` resume 可正常開啟同一已綁 DB，而 `require_new_database=True` 對該 DB 明確拒絕。resume preflight 再次驗證 schema/binding PASS，仍固定 `reconciled=false`、`trade_authorized=false`。獨立驗收結論 PASS，未發現需修改 production code 的缺陷。

Sol 於 2026-09-24 對 production bootstrap planning contract 獨立驗收：實跑 `tests/test_demo_ledger_bootstrap.py` 7/7 OK 與 `tests/test_demo_ledger_preflight.py` 9/9 OK，共 16/16；`py_compile` 與 scoped `git diff --check` 通過。程式審查確認 planning function 只組合固定 production path、既有 create preflight 與明示 historical evidence，不建立 DB／binding、不呼叫 Supervisor、不升格 reconciled 或 trade authorization。驗收後 `data/catosv1-demo`、`state.sqlite3`、`ledger-binding.json` 仍不存在。未連網、未採集、未讀 credential、未發 Demo／Live write、未修改既有 trading DB/schema、未碰 Yaozi/Lot/market、未 commit/push。

Sol 於 2026-09-24 獨立驗收時實跑 `tests/test_demo_ledger_preflight.py` 9/9 OK、`tests/test_demo_ledger_binding.py` 4/4 OK、直接下游 `tests/test_demo_reconciliation.py` 33/33 OK，共 46/46 OK；`py_compile` 通過。驗收先重現原實作會在 quiescent WAL DB 上新增 `-wal`／`-shm` sidecar，修正後新增回歸斷言確認 resume 不新增 sidecar，並新增非 WAL DB fail-closed 測試。涵蓋新路徑唯讀預檢、QA 拒絕、既有 DB／binding／WAL／SHM 衝突、明示設定缺漏、UID／budget／risk／Bot 不符、incomplete schema 不遷移、AccountLock DB 衝突／半成品、合格 synthetic resume 與 formal reconciliation binding 下游。

所有 SQLite 寫入僅發生於 temporary test fixture；本輪另外以 `mode=ro&immutable=1` 重新讀取五個排除 QA DB 的 metadata，仍全為 `local-sim` 且 account_id 為 `fake-account` 或 `s8-example-account`，沒有建立 sidecar。未修改工作樹既有 trading DB/schema，未連網、未採集、未讀 credential、未發 Demo／Live write、未 commit/push。151/151 仍是前片既有紀錄，未重跑。
