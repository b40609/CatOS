# Verified E₀ lifecycle 獨立驗收

## 2026-09-22 第三輪獨立實作與驗收

Verdict：**PASS（限 local synthetic Verified E₀ lifecycle 切片）**。本輪由 Astra 直接修正並獨立重驗 R3 / R4 / D2；未授權 Git commit/push。

- `test_verified_e0_lifecycle -v`：22/22 tests / OK。
- 11 個關聯模組：229/229 tests / OK。
- `git diff --check`：exit 0；僅既有 LF→CRLF warnings。
- R3 原始 adversarial probe：當前 day=D 時直接要求 `block_day_basis(D+100)`，Supervisor 以內部 trusted day clock 拒絕，`basis_blocked_day` 維持 `None`；clock 合法推進至 D+1 後，D+1 verified baseline 可正常提交。
- R4 原始 adversarial probe：authorized canonical source + 任意 equity/evidence_id + public self-computed digest、但缺正式 evidence payload 時，`is_verified_baseline=False`；durable provider 回傳 `None` 並持久封鎖當日。
- D2 原始 formal probe：durable baseline=`baseline_A`，午夜 bill `timing_evidence_id=baseline_B`，結果 `reconciled=False`、`trade_authorized=False`、blocker=`day_baseline_unverified`。

### R3：PASS

第二輪的 `DayContext` 雖有型別檢查，但 caller 仍可自行建立匹配 D+100 的 context，因此第一次第三輪 probe 仍成功污染 future durable state。本輪進一步移除 Supervisor `commit_day_basis` / `block_day_basis` 的 caller-supplied `DayContext` 參數，改由 `LocalSupervisor` 的內部 day clock 建立 trusted current Taipei day context；非當日 basis/day 在進 Journal 前直接拒絕。synthetic 測試只在 Supervisor 建構時注入 `FakeClock`，並以實際 clock advance 驗證合法跨日。

Journal 仍保留 `DayContext` 參數作 writer 內部 defense-in-depth；現行 production call graph 僅由 Supervisor 傳入，符合 Supervisor sole-writer invariant。

### R4：PASS

canonical source 已改為 token-safe `synthetic_midnight_snapshot_v1`。verified baseline 必須攜帶 `BaselineEvidence` payload，明確綁定 contract version、account、environment、Taipei midnight timestamp、equity、`pre_event_midnight_equity` semantics、source 與 evidence_id；digest 同時涵蓋 payload。缺 payload 的 authorized-source self-hash 不再能升格為 verified evidence。

### D2：PASS

午夜 bill 的 timing evidence 會與本次 `DayLedgerEvidence.baseline_evidence_id` 綁定；ID 不一致由 gate 加入 `day_baseline_unverified`。正式 `account_report` 對只有 `timing_verified` 而無 evidence ID 的午夜事件仍維持 `external_flow_unavailable` fail-closed。既有 inclusive-window fixture 已補上匹配 synthetic baseline ID，未放寬 D2 檢查。

### 範圍限制

此 PASS 僅代表本地 synthetic Verified E₀ lifecycle correctness slice。Classification 156/185 incomplete、正式 midnight baseline 建立來源、dedicated Demo subaccount、remote foreign responsibilities 等 production blockers 仍維持原狀；本輪未使用 OKX network、credentials、real Demo collection、既有 trading DB，亦未 commit/push/reset/clean。

## 2026-09-22 第二輪獨立驗收

Verdict：**NEEDS FIX**。Gemini 第二輪修正已讓 R1 與 R2 的原始重現案例通過，但 R3 與 R4 仍有可重現缺口；本片仍不授權 Git commit/push。

- 親自重跑 `test_verified_e0_lifecycle -v`：20/20 tests / OK。
- 親自重跑 11 個關聯模組：227/227 tests / OK。
- `git diff --check` exit 0；仍有既有 LF→CRLF warnings。
- R1 獨立 race probe：在 `commit_day_basis()` 的 SQLite I/O 等待期間插入 `manual_kill`，完成後記憶體與 DB 均保留 `manual_kill` 且 mode=FLAT。原 R1 blocker 可視為修正。
- R2 新實作將 `day_flow_cutoff_ms` 錨定 `scope.window_end_ms`，既有 1300 ms false coverage 重現已被對應 regression 覆蓋；本輪未再重現原 R2 false PASS。

### R3 仍未完成：future day 可污染 E1 狀態

前輪要求是「依受信任 DayContext 維持單調日序，拒絕過期／未來 context 擾動有效日狀態；不能只靠 caller day 數字切日」。目前 `Journal.block_day_basis(day)` 只拒絕日期倒退，仍接受任意未來整數。

獨立重現：當前 target day=D，呼叫 `block_day_basis(D+100)` 成功，`basis_blocked_day` 被寫成 D+100；之後嘗試提交正常下一日 D+1 baseline，被 `missing day basis cannot be rebuilt before next Taipei day` 拒絕。這會讓 caller 提前封鎖未來日，並使當前／下一日無法合法建立基準。

修正要求：`commit_day_basis` / `block_day_basis` 必須由受信任 DayContext（例如正式 provider 的 target day）約束，而不是裸 `day` 整數公開改寫 durable state。至少加入「未來日拒絕」及合法跨日轉移 regression；不得讓 caller 先跳到未來日再鎖死目前日。

### R4 仍未完成：authorized source + self-computed digest 仍可冒充 verified evidence

目前 `is_verified_baseline()` 只檢查 source 是否在白名單、metadata 與自行重算 digest 是否一致。它仍未驗證來源 evidence payload、午夜取樣事實或事件前語意。

獨立重現：使用已授權來源字串 `synthetic_midnight_snapshot`、任意 equity=12345.67、任意 evidence_id=`self_asserted`，再以公開 `compute_baseline_digest()` 自行計算 digest；`is_verified_baseline()` 回傳 True，`commit_day_basis()` 後 durable provider 直接回傳該 12345.67 / self_asserted 作為 verified baseline。

另有契約自相矛盾：`SYNTHETIC_BASELINE_SOURCE = "synthetic_midnight_snapshot.v1"` 含 `.`，但 `ipc.token()` 不接受 `.`；直接建立使用此 canonical constant 的 `DayBasis` 會 `ProtocolError invalid basis source`。現行測試實際使用未版本化的 `synthetic_midnight_snapshot`。

修正要求：建立真正的 synthetic baseline evidence payload 契約，至少把帳戶／環境、交易日午夜 timestamp、equity、事件前 baseline semantics、來源版本與 evidence_id 一起驗證並綁 digest；provider 只能消費經此驗證器產生／載入的 evidence。不要僅用 source 常數代表「已驗證」。同時統一 canonical source 的 token 格式。

### D2 仍可 false PASS：timing_evidence_id 未與 baseline_evidence_id 綁定

`account_report.decode_row()` 目前只要求午夜 bill 的 `timing_evidence_id` 非空；report/provider/gate 都沒有驗證它等於正在使用的 `DayLedgerEvidence.baseline_evidence_id`。

獨立 formal probe：durable baseline 使用 evidence_id=`baseline-A`，午夜 bill 宣告 `timing_verified="after_baseline"` 但 `timing_evidence_id="different-baseline-B"`；formal reconciliation 仍得到 `reconciled=True, blockers=()`。

修正要求：午夜事件時序證據必須明確綁定本次 baseline evidence，且 gate/provider 能驗證關聯；不一致時 fail closed。新增「wrong timing evidence id」formal regression。

第二輪結論：R1/R2 可保留修正；Gemini 下一輪只需聚焦 R3 future-day DayContext、R4 baseline evidence payload，以及 D2 timing evidence/baseline linkage，完成後再由 Astra 重驗。

日期：2026-09-22。Gemini 實作，Astra 本輪獨立 review。Verdict：**NEEDS FIX**。本片不授權 Git commit/push。

## 實際驗證

- 讀取 Gemini 完整交付，inspect 現行程式與相關 tracked Git diff。工作樹含既有其他修改；Git HEAD diff 不是 Gemini 本輪獨立差異，不能據此把既有 schema／Lot 修改歸因本片。
- 親自重跑 11 模組：test_account_report、test_reconciliation_gate、test_supervisor_reconciliation、test_okx_collection、test_demo_collection、test_okx_http、test_okx_readonly、test_demo_reconciliation、test_risk、test_journal、test_verified_e0_lifecycle，共 221 tests / OK。
- 另外重跑 lifecycle suite：14 tests / OK。30 個 Demo tests 已包含在 221 中，不另加算。
- git diff --check exit 0，既有 LF→CRLF warnings。此指令不涵蓋 untracked 檔案。
- 獨立 probes 利用 tests/test_verified_e0_lifecycle.py 的臨時 DB setup、FakeClock 與 synthetic transport；四次 probe 執行均成功重現以下問題。probe 測試的 OK 表示重現缺陷成功，並非驗收 PASS。

## R1／P1：baseline 提交覆寫尚未持久化的 latch

位置：catos/supervisor.py:442 的 commit_day_basis 與 :448 的 block_day_basis。方法從 Journal 取得舊 state，直接 _accept_risk(state)，既未先同步 pending risk，也未保護等待 I/O 期間的控制更新。

重現：setup → supervisor.latch('manual_kill') → await supervisor.commit_day_basis(make_verified_basis(now)) → 讀取記憶體與 Journal risk_state。

- 提交前 reasons={'manual_kill'}、mode=FLAT。
- 提交後記憶體與 DB reasons 均為空，DB mode=RUN。
- supervisor.halt_reasons 集合可能仍保留原因，但正式 risk state 的 latch 已遺失，不能宣稱所有 latches 保留。

修正要求：沿用既有 writer／control generation 邊界，不能以舊 DB 全量 state 覆蓋較新 risk。除提交前 pending latch，還要測試 commit/block I/O 等待期間收到 latch 或 observe_risk 的情境，以及重啟後原因仍存在。單純在呼叫前 flush 無法涵蓋 await 期間 race。

## R2／P1：當日 C_t 聲稱的 coverage 超出實際採集窗口

位置：catos/account_report.py:409 將 day_cutoff 設為 manifest.completed_ms；gate 的 _day_blockers 未驗證 day_flow_start_ms/day_flow_cutoff_ms 的 coverage；provider 也未核對 context 時間範圍。

獨立重現（正常 synthetic_midnight_snapshot source）：plan end=1700000000000，collection 完成=1700000001300；report 宣稱 day_flow_cutoff_ms=1700000001300，但 bills 只查到 plan end。實際 gate.reconciled=True、blockers=()。

修正要求：以真正有完整 evidence 的 cutoff 計算 C_t，驗證 day start 到 cutoff 均被 request/page evidence 涵蓋，並使 provider/gate/risk 使用同一區間。禁止把採集耗時期間的未查詢流量視為零；不放寬 24h formal plan。補充不同 query cutoff、採集／evaluate 跨日、缺失及不一致 context 的 tests。

## R3／P1：E1 封鎖可被另一日期覆蓋

位置：catos/journal.py:496。block_day_basis 只檢查等日，允許用任意另一日覆蓋 basis_blocked_day；commit_day_basis 也沒有日別單調性限制。

重現：block_day_basis(D) → block_day_basis(D-1) → commit_day_basis(D 的 basis)。今日 basis 成功提交，違反今日已封鎖不得補建。

修正要求：依受信任 DayContext 維持單調日序，拒絕過期／未來 context 擾動有效日狀態；不能只靠 caller day 數字切日。測試亂序請求、同日重放、重啟與跨日合法轉移。另需處理 legacy／invalid basis 已存在時 block_day_basis 拋錯、provider 吞錯而未持久封鎖的路徑，不能宣稱已 durable blocked。

## R4／P1：來源名稱與自算 digest 仍被當成 verified provenance

位置：catos/risk.py:95 的 is_verified_baseline。只要求 source 非空並重算 scalar metadata hash，沒有來源證據內容、午夜取樣語意或合格來源檢驗。

重現：make_verified_basis(now, source='unverified_intraday_guess') 可通過 commit/provider，formal synthetic gate 得到 reconciled=True、blockers=()。此 probe 同時觀察到 R2；R2 已另以正常 source 獨立重現。程式明確不區分任意 source 字串。

修正要求：為本片明示且隔離 synthetic baseline evidence 契約，驗證來源 payload、帳戶／環境、午夜時點與事件前語意並綁定 digest；舊 token-only／任意 source+自算 hash 不得升格。這是資料契約，不要求對抗可任意修改 Python 的惡意 caller或導入簽章系統。生產建立仍阻斷。

相關 D2 缺口：account_report.py:152 直接接受 bill payload 的 timing_verified 字串，未綁定 baseline evidence。不能把任意原始 bill 的 after_baseline／prior_to_baseline 自述當成時序證明；應僅接受有明確 baseline 關聯的 synthetic 證據，並遵守已核准事件前基準語意。本項屬靜態審查，未另執行 adversarial probe。

## 下一步與邊界

Gemini 修 R1–R4，新增可重現上述缺陷的 regression tests，再重跑受影響 modules。Astra 後續獨立驗收。既有 221/221 不足以覆蓋這些情境。

本輪只新增本 review 並修正 handoff，未修改 production code。未讀 credentials、未使用 OKX network、未採集 Demo、未開既有 trading DB、未 commit/push/reset/clean，未修改 Lot／market／Yaozi 工作。
