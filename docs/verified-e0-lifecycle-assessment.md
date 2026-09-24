# Verified E₀ lifecycle 盤點與最小規格草案

日期：2026-09-22。負責：Astra 規格盤點；後續 Gemini 實作、Astra 獨立驗收。狀態：使用者於文件交付後回覆「同意」，核准下述最小 local synthetic 切片；尚未實作。

## 使用者定案與 Gemini 執行範圍

- 採 D1-A：維持精確午夜 E₀ 政策，先完成 synthetic lifecycle 與既存 durable baseline 消費；生產新基準建立繼續阻斷，未核准取樣容差或午夜後第一筆 balance 替代。
- 採 D2 的保守邊界：當日 C_t 使用 [00:00, cutoff]，午夜事件歸新日；基準證據必須可證明相對於午夜事件的前後關係，避免重扣。無法證明時阻斷，不猜測。synthetic fixture 必須明示一致的事件前基準語意；未核准用不明時序的真實資料。
- 採 D3 建議：首次正式新日判定無合格 durable basis 即封鎖該日，不增設等待寬限，同日不得補建；重啟不解除。此規則不改 E1。
- Gemini 可依第 3、5 節完成最小本地程式與受影響 synthetic tests；只用臨時 DB，沿用單 writer，不新增第二帳本，不修改 DB schema 或升級既有 DB。既有 state JSON 的必要相容擴充需明確記錄，舊缺證據 state 不自動視為 verified。
- 不接生產午夜排程、網路、憑證、Demo collection、真實交易或 Git 提交。未解證據仍 fail closed，trade_authorized=False。
- 第 3–5 節保留盤點原文；其中「提案／待定／定案後」以本節最新定案為準。尚無 Gemini 實作或 Astra 本片驗收結果。

## 1. 已定案基線

- 固定 Asia/Taipei 00:00 日初權益為日損分母；金額全用 Decimal、序列化為十進位字串。
- E1 已定案：當日缺少 verified E₀ 就保持阻斷，同日不得重建；不得以啟動或目前 equity 倒推。不重問 E1/E2/E3。依據：reconciliation-gate-contract.md 第 4 節；policy-decision-pack.md 的 E1 建議文字須以後續正式契約為準。
- 同日分母不可更換；入出金僅影響外部資金流。跨日、重啟、入金均不解除 Soft／Hard／manual latch。
- 分類 complete=false、未知流、foreign responsibility、帳戶範圍不符繼續阻斷；本草案不授權降低任何條件。
- Formal runner 的 F1 override／plan bounds 已於前片通過驗收，不代表 E₀ lifecycle 已完成。

## 2. 現有能力與具體缺口（靜態檢視）

| 位置 | 已有能力 | 缺口與失敗情境 |
| --- | --- | --- |
| catos/risk.py：DayBasis、State、observe | basis 含 day/equity/evidence_id；同日不可替换；basis_blocked_day 可序列化；固定分母與 latch | 屬 synthetic reducer，未驗證 evidence_id 對應的 durable 來源；首次帶任意當日 basis 可被接受，不等於已驗證午夜證據 |
| catos/journal.py：risk_state、save_risk | risk_control.state_json 持久化；交易內更新 controls；保護既有 halt reasons | 沒有正式 E₀ 證據載入／驗證 provider；save_risk 不是 E₀ 完整證據驗證器；既有 basis 僅有 token 不能直接升格 verified |
| catos/supervisor.py：observe_risk | 記憶體 reducer、後續 persist_controls 持久化 | 記憶體更新不等於 durable commit；不能在寫入確認前向正式 gate 提供新 baseline |
| catos/demo_reconciliation.py：day_ledger_provider | 以 plan.scope.window_end_ms 呼叫 provider | 尚無生產 provider；caller 可直接提供 DayLedgerEvidence，這仍是受信任 evidence seam |
| catos/reconciliation_gate.py：_day_blockers | 檢查台北午夜格式、分類 ID／complete、unknown count、flow 金額相等 | 未比對 baseline 是否屬目標日，未查 durable provenance；任意其他日期的午夜可通過日期這一項檢查。此為程式靜態判讀，本片未新增執行 probe |
| catos/account_report.py：bill_valid／classify_bill_flows | 對已去重／檢查的窗口 bills 分類加總 | observed_external_flow_usdt 是整個採集窗口合計；24h trailing window 通常跨兩個台北日，不能直接當當日 C_t。例如昨晚入金會錯誤扣入今日損益 |
| tests/test_risk.py | 已有跨日、同日缺失、序列化後拒絕重建、latch 測試 | 尚無 formal provider durable lifecycle／跨日 report 整合驗收；本片只讀測試，未重跑 |

現有 DayBasis.day 為日序號，DayLedgerEvidence.trading_day_start_ms 為毫秒時間戳。轉換必須用整數：day = (time_ms + 28800000) // 86400000；day_start_ms = day × 86400000 - 28800000。不可混用兩者。

## 3. 最小實作方向（提案，未授權實作）

先交付 local synthetic 的「既存 durable baseline 消費與 E1 狀態機」，不啟動午夜排程或真實採集。具體失敗情境是錯日基準、重啟後重建、尚未落盤就 PASS、24h 流量冒充當日流量；以單一 provider、現有 writer 與小型純函式處理即可。

1. 明確 DayContext：目標交易日、cutoff、當日資金流窗口；目標日必須與實際 gate check-time 所屬日一致。採集／處理跨午夜時拒絕混日組合，要求新日重新取得證據，不倒用前日 ledger。
2. provider 只讀同一 account/environment 的已提交 baseline，核對日別、正數 Decimal、evidence digest 與來源。空值、錯日、毀損或無來源一律不能轉成 verified。
3. 分離「E₀ 證據合格」與「完整 reconciliation PASS」的判定，避免必須先有 E₀ 才能產生 E₀ 的循環依賴。候選證據至少包含帳戶範圍、valuation 來源與版本、來源時間區間、日別、equity、分類版本、內容 digest；完整門檻仍受第 4 節決策約束。
4. 沿用 risk_control 的單 writer 路徑，原子提交 baseline／basis_blocked_day／必要來源引用，再允許 provider 輸出。先確認現有 JSON 契約可承載與舊 state fail-closed 讀取；不另建帳本。本片不核准 JSON 格式修改、DB schema migration 或使用既有 DB。
5. 同日相同證據重放為冪等；同日不同 equity／證據不得替換。重啟沿用同日 durable basis；缺失、損壞、前日 basis 不可用當前 equity 修補。
6. 24h plan 維持已核准 bounds；在已驗證窗口內依 bill event timestamp 篩出當日流量，保留全窗口小計供對帳。增加明確的當日 coverage 與金額欄位，gate/provider/risk.external_net 必須比較同一時間區間；不能只改欄位名稱。邊界以第 4 節定案為準。
7. 任何寫入結果不確定時不回報 durable success，不解除 latch；恢復時讀 durable 狀態再判斷，不盲目寫入第二份 baseline。

## 4. 需要使用者定案的部分

### D1：午夜基準的可證明程度

現行 S1 僅保證有界循序觀測，balance 的 uTime 不是 snapshot 時間；在 00:00 啟動請求或於其後收到 balance，均不能單獨證明精確 00:00 equity。F1 的 500ms sample age 也不能當成午夜取樣容差。

- 建議本片採 D1-A：保持精確日初政策，先完成 synthetic lifecycle；生產新基準建立保持阻斷，直到有符合政策的可驗證來源。這不保證下一午夜必能建立 E₀。
- D1-B：若希望用午夜附近第一個合格觀測作操作性日初值，必須另核准時間容差、時間基準、區間內持倉估值與資金流處理，並明示這會縮減「精確午夜權益」保證；本草案不選數字。

### D2：日界資金流歸屬

建議以當日 [00:00, cutoff] 為 C_t，午夜事件歸新日、同交易去重；但需確定 baseline 是午夜事件前或後的權益。若來源無法判定入金已否包含於 baseline，不能靠 <= 或 >= 猜測，該組證據阻斷。完整目錄仍須 complete=true，不能因當日無未知 bill 而放寬。

### D3：新日首次缺失的判定時機

E1 同日不得重建已定案，待定的是跨午夜的短暫採集中何時算「已缺失」。建議 local slice 不新增寬限：首次正式新日判定無合格 durable basis 即封鎖該日；未來午夜採集若需候選等待期，須與 D1 一起另定截止及 crash/restart 規則。不能用下一次重啟清掉封鎖。

## 5. Gemini 驗收清單（定案後才實作）

| 情境 | 必要結果 |
| --- | --- |
| 同日、同帳戶合格 durable baseline | provider 回傳一致 Decimal 與來源；仍不自動授權交易 |
| 昨日／未來日午夜、錯帳戶／環境、偽造 token | fail closed，不能僅憑午夜格式通過 |
| 初次缺基準→同日補傳→重啟再傳 | 同日均拒絕重建，封鎖可恢復 |
| 同日重放／不同基準替換 | 相同冪等；不同拒絕 |
| 次日新合格證據 | 僅新日符合政策時接受；原 Soft／Hard／manual latch 保留 |
| 持久化前中斷／寫入失敗／提交結果不明 | 不輸出 verified success；恢復後以 durable 結果判斷 |
| 昨日外部流、今日入出金、重複 bill | 今日 C_t 不混入昨日、不重複；分母不變 |
| 恰在午夜／cutoff 的 bill | 依 D2 唯一歸屬；證據含義不明時阻斷 |
| collection 或 evaluate 跨日 | 不沿用舊日 baseline／flow context |
| partial classification、unknown、coverage gap | 持續阻斷，不以零補值 |

最小驗證：受影響 risk、Journal、gate、provider／runner 模組；所有 DB 僅臨時 synthetic。無實測瓶頸不新增服務或並行架構。只做文件盤點的本片不需要跑單元測試。

## 6. 交付界線

盤點及本次定案記錄只修改本文件與 current-handoff.md，未改程式、未執行測試／採集、未讀憑證或既有 DB、未做 Git 寫入。前片 177/177、30/30 為前片證據，不是本片重驗。使用者已核准頁首 local synthetic 範圍，不構成生產啟用授權。

## 7. 2026-09-23 D1-A production source 公開證據調查

結論：**截至 2026-09-23 的 OKX 官方公開 API Guide／Help Center，未找到可直接回溯取得「指定 Asia/Taipei 00:00 的完整 Trading Account equity」且能滿足 D1-A provenance 的 production source。D1-A blocker 維持，不能以午夜附近觀測、record `uTime`、transport time、UTC 00:00 statement 或 position-only snapshot 替代。**本結論是對已檢索官方公開契約的結果，不宣稱不存在任何未公開／機構專用資料來源。

已排查候選：

- `GET /api/v5/account/balance`：官方只提供 `ccy` request parameter；`totalEq` 是帳戶總資產、`uTime` 是 account information update time。沒有 `before`／`after`／`ts` 等歷史時間點參數，因此只能取得請求當下狀態，`uTime` 仍不是指定午夜 snapshot fence。來源：<https://www.okx.com/docs-v5/en/>。
- `GET /api/v5/account/account-position-risk`：request 僅有 `instType`；response `ts` 定義為 account information update time。沒有歷史時間點查詢參數，不能回溯重建指定午夜 equity。來源：<https://www.okx.com/docs-v5/en/>。
- `GET /api/v5/asset/asset-valuation`：request 僅有估值幣別 `ccy`；response 回傳單一 `ts` 與當下 `totalBal`／各 account valuation。沒有歷史時間點參數，且其 scope 是跨 Funding／Trading／Earn 的 asset valuation，不是 D1-A 所需的指定午夜 Trading Account equity source。來源：<https://www.okx.com/docs-v5/en/>。
- Private WebSocket `account`／`balance_and_position`：官方契約是事件觸發與定期 push；`balance_and_position` 的 `eventType=snapshot` 是訂閱後的當前 snapshot 語意，不提供歷史 timestamp query。其 balance payload 以 `cashBal` 為主，也不是可回溯的完整 `totalEq` 歷史序列。來源：<https://www.okx.com/docs-v5/en/>。
- Account Statement：官方 Help Center 可按日期產生 statement，但明示 record time **基於 UTC，預設 cutoff 為 00:00 UTC**；這與固定 Asia/Taipei 00:00（前一日 16:00 UTC）不同。公開 `POST/GET /api/v5/asset/monthly-statement` 只接受月份，回傳產生／下載狀態，沒有任意時區或任意 timestamp 的 equity snapshot API 契約。來源：<https://www.okx.com/help/how-can-i-download-my-statements>、<https://www.okx.com/docs-v5/en/>。
- Position snapshot：官方 Help Center 允許選 date／time zone，且包含 Snapshot time，但輸出是 position-level 欄位（position size、margin、assets/liability、mark price 等），未提供完整 account `totalEq`，不能單獨作 E₀。來源：<https://www.okx.com/help/how-to-check-download-order-history-position-history-and-trading-history>。
- Proof of Reserves user snapshot：官方說明為 specific-point-in-time 的 net asset snapshot，但 reserve data 為月度更新；不是每日台北午夜 production feed，也沒有本專案可依賴的指定日／指定時點 API。來源：<https://www.okx.com/help/proof-of-reserves-por-user-snapshot-data-explanation>。

因此 production 契約不變：只有已由可信 production producer 在正確台北午夜取得、以既有 `BaselineEvidence` provenance 契約 durable commit 的 E₀ 才可供 provider 消費；目前專案尚無此 producer。不得由 S1 sequential balance observation、午夜後第一筆 balance、Account Statement 的 UTC midnight、position snapshot 或 bills 倒推自動產生 verified E₀。若未來 OKX 新增可指定歷史 timestamp 的完整 account-equity endpoint，或使用者另提供可驗證的專用資料來源，再另片評估；在此之前 formal reconciliation 依 D1-A／E1 fail closed。

## 8. 2026-09-24 Q1-B 已核准：D1-Q1 quiescent exact-equivalence

本節取代第 4／7 節中「production 只能使用 direct exact-midnight source」的政策結論；第 7 節對 OKX 公開 API 能力的調查事實仍保留。使用者已核准 dedicated Demo bootstrap 使用更窄的 D1-Q1：若從 Asia/Taipei 00:00 到 cutoff 的完整 evidence 能證明 single-USDT、正確 UID／subaccount／acctLv=2／`net_mode`、零 current responsibility、零 ordinary order history／fills／balance-changing bills，且 window/page-chain/F1/S1 均完整，則 cutoff USDT equity 可作為與午夜 E₀ 數值完全相等的 durable baseline。任何事件、coverage gap、malformed evidence 或時間歧義都 fail closed；不做 `balChg` 倒推，也不採時間容差。

程式已新增 `demo_quiescent_midnight_equivalence_v1` authorized baseline source，並保留既有 synthetic midnight source 相容性。Q1 durable evidence 綁 expected UID SHA-256、day start/cutoff、report/balance/collection/zero-event digests；producer 在 D3 provider 前執行，成功仍只透過 Supervisor→Journal 單 writer commit basis。Q1 自身不設定 `reconciled=true` 或 `trade_authorized=true`。專屬及直接受影響回歸共 188/188 OK；詳見 `docs/demo-e0-quiescent-equivalence-decision-20260924.md` 與 `outputs/catosv1-demo-q1-e0-verification-20260924.json`。

現有 production 40 GET 不能倒補：該批 evidence 有 7 筆 bill（其中 6 筆非 USDT transfer），且發生於 `orders_history` window provenance 擴充之前，因此不滿足 Q1 的零 bill 與完整新 provenance 條件。production E₀ 仍未建立。
