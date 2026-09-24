# CatOS 目前接續入口

## 2026-09-23 Sol 核對補充：Yaozi 整合來源已固定

已依 `docs/catos-yaozi-integration.md` 核對兩個工作樹。Yaozi 來源固定為 `C:/Users/user/Desktop/CatOS_Yaozi` 現行工作樹：branch `yaozi/dev-v0.7`、HEAD `a4fb910`，但 v1.5–v1.26 含未提交成果，**不得只用 HEAD commit 取代工作樹內容**。與 Astra `main` 的 merge-base 為 `3925759`。正規化換行後，Yaozi 整合來源範圍有 7 個同名實質差異檔、13 個 Yaozi-only 檔；另有 37 個僅 CRLF/LF 差異，不列功能整合。完整檔案清單與功能差異已寫入[整合契約](catos-yaozi-integration.md)。本輪只讀核對後更新文件；未改 Yaozi 程式、未開 DB、未重跑測試、未 commit／push，兩邊既有未提交工作全部保留。

下一片由 Astra 依該差異清單做最小整合：先處理 `market_decision.py`、`market_api.py` 與 Dashboard 的逐段合併，再納入 social registry 與專屬測試；不可整包覆蓋 Yaozi/Astra 目錄。Astra 目前仍只有情報 FastAPI 入口，根路由已被 Dashboard 使用，因此統一「量化交易／Yaozi 情報」介面仍需另行實作與驗收。

## 2026-09-23 接續補充：Yaozi 單一介面整合方向已確認

使用者已同意保留兩個開發目錄，最終將 Yaozi 整合為同一 catOS 網站分頁。Astra 已完成靜態盤點與[整合契約](catos-yaozi-integration.md)，同步 `AGENTS.md`／`README.md`；本輪僅文件修改，未合併程式、未核對 Git 狀態、未執行測試、未開 DB。兩邊情報 API／Dashboard／social 檔案已分歧，Astra 尚無另一個量化管理 Web 入口；不可宣稱統一介面已完成。下一片由 Sol 核對基線及未提交內容、固定 Yaozi 交付來源與差異清單，再由 Astra 進行最小介面整合。保留兩邊交易／Lot／Yaozi 進行中工作；不跨目錄載入、不覆蓋、不改 schema、不新增交易或 commit／push 授權。下方為原交易主線狀態與歷史驗證，本輪未重驗。

## 2026-09-23 Demo 額度語意：待使用者定案

已核對現行 `risk.evaluate()`、Journal reservation 釋放與 Supervisor grant gate；`max_entry_reservation_usdt` 僅比對當下未釋放 reservation，且 `prepare()` 可用更新的 mark 重評風控、舊 reservation 仍被用作 grant 額度證據。已完成[額度決策稿](demo-trade-budget-decision.md)，建議首輪 B1：每份 grant 最多一次新增曝險送單嘗試，以送單前核實 mark 計算的委託名目額設上限，transport 一旦進入就不返還額度。**B1 尚未核准或實作**；市價實際成交額可能高於 mark 計價額。下一步請使用者定案 B1 後，才改 local synthetic grant 契約及專屬測試。這次只改文件、未跑程式測試；`git diff --check` exit 0。保留原有 local-only 與不碰 Lot／market／Yaozi dirty work、既有 DB、網路、憑證、commit／push 的邊界。前端依使用者指示延後。

## 當前片：Demo Trade Authorization adversarial review 完成

2026-09-23 最新審查：**PASS WITH FOLLOW-UP（限 FakeExchange）**。已重現並修正 handoff 排程後過期仍送單、prepare 期間不能撤銷、close 保留 grant；另補 authorization/revoke generation 與 durable reservation 檢查。專屬 11/11 OK。詳見 [審查紀錄](demo-trade-authorization-review.md)。此前 263/263 是歷史回歸，不能取代本次審查。前端依使用者指示延後。

後續：真正 Demo 額度語意請以上方 2026-09-23 決策稿與使用者定案為準。目前 max_entry_reservation_usdt 只限未釋放 reservation，不能宣稱限制持倉曝險或 grant 累計交易量；仍維持 local-only，不授權網路、憑證、既有 DB 或 commit/push。

更新日期：2026-09-23。主線：**OKX Demo formal reconciliation → 首個安全自動策略閉環**。
使用者已定案 T1-A／T2-A／T3-A；Astra 已完成純本機 **Demo Trade Authorization Contract** 實作與 synthetic 驗證。`reconciled=True` 仍只代表 evidence 可接受；只有明示 `require_demo_trade_grant=True` 且存在有效、有限、綁 reconciliation evidence/revision 的 in-memory `DemoTradeGrant` 時，普通增加曝險 dispatch 才能進 FakeExchange。真正 OKX Demo POST 仍未授權／未接線。詳見 `docs/demo-trade-authorization-decision-pack.md`。

---

## 1. 切片／角色與授權邊界

- **負責角色**：Astra 已完成 Verified E₀ 第三輪、formal readiness 收斂與 Trade Authorization local contract。本片未授權 commit/push。
- **授權邊界**：
  - 僅使用本地臨時 synthetic DB 與 `FakeClock` 模擬測試。
  - 嚴格未改 SQLite Schema、未碰既有交易資料庫。
  - 嚴格未連線 OKX 網路、未讀取真實憑證、未執行 private GET/POST、未發出實盤請求。
  - 未修改無關之 Lot / market / Yaozi 模組。
  - `trade_authorized = False` 無條件維持。
  - 未執行 `git commit` 或 `git push`。

---

## 2. 第三輪驗收結論

- **R1：PASS（沿用第二輪 local synthetic 證據）**。I/O 期間 latch race 已封閉。
- **R2：PASS（沿用第二輪並納入 229/229 regression）**。`day_flow_cutoff_ms` 嚴格錨定實際 query window。
- **R3：PASS**。Supervisor 不再接受 caller-supplied `DayContext`；由內部 day clock 建立 trusted current Taipei day。原始 D+100 probe 現直接拒絕且 durable state 不變，clock 合法跨日至 D+1 後可正常提交 D+1 baseline。
- **R4：PASS**。verified baseline 現要求完整 `BaselineEvidence` payload；authorized source + self-hash 但缺 payload 時 `is_verified_baseline=False`，provider 不接受並封鎖當日。canonical source 已改成 token-safe `synthetic_midnight_snapshot_v1`。
- **D2：PASS**。午夜 bill `timing_evidence_id` 必須與實際 `baseline_evidence_id` 一致；baseline-A / timing-B formal probe 現為 `reconciled=False`、`day_baseline_unverified`。

下方 Gemini 第二輪內容僅供追溯；以本節與 review 頁首第三輪 verdict 為準。

## 3. Gemini 第二輪修正重點

1. **R1 / P1（保護 pending / I/O 期間 latch）**：
   - `catos/journal.py`：`commit_day_basis` 與 `block_day_basis` 接收並原子持久化合併 `in_flight_reasons`，若存在理由則維持 `FLAT` 模式，防止以舊 DB state 覆蓋新 latch。
   - `catos/supervisor.py`：`_accept_risk` 確保 `self.halt_reasons` 永不丟失；`commit_day_basis` / `block_day_basis` 在 I/O 前後均呼叫 `await self._flush_halts()`，並在接收 Journal state 時精確合併 basis / basis_blocked_day 至記憶體 risk_state。
2. **R2 / P1（當日 C_t coverage 嚴格錨定與一致）**：
   - `catos/account_report.py`：`day_cutoff_ms` 嚴格錨定為 `scope.window_end_ms`（bills 實際 query window end），絕不使用採集耗時後的 `manifest.completed_ms`；當 `scope.window_start_ms > day_start_ms` 時回報 `window_coverage_unverified`。
   - `catos/reconciliation_gate.py`：`_day_blockers` 在 `evidence.day_flow_cutoff_ms` 存在時，強制比對 `rep_cutoff == evidence.day_flow_cutoff_ms`，且檢驗 `rep_cutoff <= win_end` 與 `rep_cutoff >= expected_day_start_ms`，確保 provider / gate / risk 區間嚴格一致，禁止採集耗時期間未查流量視為零。
   - `catos/demo_reconciliation.py`：provider 核對 `day_flow_start_ms == expected_start_ms` 且 `ctx_cutoff` 在區間內，並將 `day_flow_cutoff_ms` 傳入 `DayLedgerEvidence`。
3. **R3 / P1（維持 E1 單調日序與持久封鎖）**：
   - `catos/journal.py`：`commit_day_basis` 拒絕倒退日序（`< state.basis.day`）與已被封鎖日（`<= state.basis_blocked_day`）；`block_day_basis` 拒絕倒退日序（`< state.basis_blocked_day`）。
   - 當已存在 legacy / unverified basis 時，`block_day_basis` 主動清除舊 basis 並建立持久封鎖；`catos/demo_reconciliation.py` 移除吞錯 pass，確保封鎖異常能直接向上拋出。
4. **R4 / P1（明示 synthetic 來源契約與午夜時序證據）**：
   - `catos/risk.py`：定義 `SYNTHETIC_BASELINE_SOURCE = "synthetic_midnight_snapshot.v1"` 與 `AUTHORIZED_BASELINE_SOURCES` 白名單。`is_verified_baseline` 嚴格要求 `source in AUTHORIZED_BASELINE_SOURCES`，拒絕任意字串與自算 hash，並核對 `trading_day_start_ms` 對齊台北午夜。
   - `catos/account_report.py`：`decode_row("bill", row)` 要求 `timing_verified` 必須為 `prior_to_baseline` 或 `after_baseline`，且必須綁定非空 `timing_evidence_id`。

---

## 4. 最新驗證證據

- **專屬生命週期與 R1–R4 / D2 Regression 測試（共 22 個測試）**：
  `$env:PYTHONPATH=".;tests"; python -m unittest test_verified_e0_lifecycle -v`
  - **22/22 tests OK**。
- **受影響關聯模組全量測試（共 11 個測試模組）**：
  `$env:PYTHONPATH=".;tests"; python -m unittest test_account_report test_reconciliation_gate test_supervisor_reconciliation test_okx_collection test_demo_collection test_okx_http test_okx_readonly test_demo_reconciliation test_risk test_journal test_verified_e0_lifecycle -v`
  - **229/229 tests OK**，0 失敗，0 錯誤。
- **Git Check**：
  `git diff --check` 返回 code 0；無 whitespace error，僅既有 LF→CRLF warnings。

---

## 5. 當前生產阻礙（Remaining Production Blockers）

1. **Classification Incomplete**：官方目錄覆蓋度為 156/185，29 unknown、`complete=false`；生產正式判定維持 `unknown_external_flow`。剩餘項需要新官方證據或新的明確會計／產品政策，不能本地猜分類。
2. **Production Verified E₀ Source**：local synthetic lifecycle 已 PASS；生產仍依 D1-A 精確午夜政策，沒有核准的 production baseline 建立來源。不得用午夜後第一筆 balance、啟動 equity 或任意容差替代。
3. **Dedicated Demo Subaccount Requirement**：正式環境下 `uid == mainUid` 仍固定以 `scope_mismatch` 阻斷。
4. **Remote Foreign Responsibilities**：若遠端存在非本機 Journal 部位或掛單，維持 `foreign_position/order/algo` 阻斷。
5. **Real Demo write 尚未授權／接線**：T1-A／T2-A／T3-A local contract 已完成，但 formal reconciliation 的 `trade_authorized` 仍固定 false；現有 Supervisor 也仍只接受 `FakeExchange`。真實 Demo transport、credential、POST、指定 account/instrument/額度/時間與收尾方式都需要新的明確授權。

### Readiness 核對

- S1 `s1-bounded-sequential.v1` 已完成並由 gate 直接驗 source/page timeline，不是未解 blocker。
- F1 已定案為 `1000 / 31000 / 3000 / 500 ms`，formal runner 於 check-time 動態取時。
- E1／durable posId／algoId、W1、R1–R4、D2 均已有 local synthetic regression。
- 2026-09-22 本輪焦點重跑 5/5 OK：synthetic formal happy path、production classification blocker、missing E₀ blocker、S1 overlap blocker、durable E₀ formal pass。
- 2026-09-23 Trade Authorization：新增 6 個 T1/T2/T3 acceptance tests，6/6 OK；包含 prepare→handoff cutoff race 的 unsent-abort probe。連同 formal／execution／protection 等 14 個關聯模組合計 **263/263 OK**，`py_compile` 通過。

---

## 6. 接續指引

> T1-A／T2-A／T3-A local authorization contract 已完成。下一步不要直接把 `trade_authorized` 翻成 true；production classification 29 unknown 與 exact-midnight E₀ 仍需新證據／新政策，dedicated Demo subaccount／foreign responsibilities 仍需新的真實唯讀驗證。任何 OKX network、credential、real Demo collection、Demo POST 或既有 trading DB 操作都需要新的明確授權；目前仍不授權 commit/push。
