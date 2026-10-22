# R1 風控期間基準：本機模擬交付

日期：2026-10-20。狀態：**實作與開發自測完成；197／197 通過，待指定 GPT-6 Sol 獨立驗收。** 使用者已授權完成 R1 local-sim 工作包；政策依[精簡評估第 5 節](retail-v1-simplification-assessment-20261020.md#5-已定案金融變更r1-操作性風控基準)。

## 已完成行為

- 當日首次合格觀測建立固定基準，綁定帳戶、local-sim、台北日、實際觀測時間、正的 Decimal 初始權益、來源及報告 digest。基準在既有單 writer 交易內重新驗證 gate，COMMIT 後才可供風控使用。
- 首次／新日資料暫缺可重試，不自動寫入整天封鎖的 E1。尚未建立基準時禁止增倉；既有合法減倉仍依部位新鮮度、歸屬、數量與衝突條件判斷。
- 同日重啟、入金或虧損沿用原分母。`basis_established_day` 保存在既有 `risk_control.state_json`；既存標記或本日執行責任卻缺基準、基準損壞或同日替換，一律拒絕重新起算。
- 新日須建立新期間，不能混用舊基準；Soft／Hard／manual Kill latch 保留。提交期間到達的新 latch 不被舊狀態覆蓋。寫入回滾或 COMMIT 後 ACK 遺失均不回報成功；後者讀回耐久狀態，避免關閉時覆寫已提交基準，失敗實例仍停止使用。
- 外部資金流由完整 bill facts 重新計算，不沿用午夜小計。起算前已含於初始權益；起算後只排除白名單外部淨流。邊界同毫秒須有 `timing_verified` 與精確 `timing_evidence_id`，否則 unavailable。相同 bill 去重，衝突版本拒絕；實際 unknown／forbidden 活動在起算前也不豁免。
- 報告輸出「風控期間損益」、`start_ms`、固定基準、期間損益／比例與 `full_day=false`。摘要先加入報告再計算 digest，回傳報告與 gate 引用一致；等待 writer 時呼叫端修改原始報告不會改變已驗證權益。
- UNKNOWN、陌生責任、完整性、成交終態、freshness、窗口及 P6 檢查保留。獨立 Lot 報表缺費不新增 gate；`trade_authorized` 始終為 false。

```text
風控期間損益 = 當前權益 - 固定期間基準權益 - 起算後已確認外部淨流入
風控期間損益率 = 風控期間損益 / 固定期間基準權益
```

初始權益必須為正；之後當前權益可為零或負數，仍觸發既有 Hard／FLAT，不能因驗值拒絕而漏掉風險。

## 接口與保存

- `risk_period.candidate()` 產生候選證據，不代表已合格或可交易；`project()` 對既存基準投影期間流水與摘要。其輸入為受信的合成／已正規化報告，並非原始帳戶 response 驗證器。
- `LocalSupervisor.prepare_risk_period(report, classifications=..., freshness_policy=..., freshness_evidence=...)`：資格檢查、建立／讀取耐久基準、期間投影、既有 ownership/fills 對帳，回傳 `(report, ledger, gate)`。候選不能藉直接呼叫 `observe_risk()` 注入未保存的 R1 基準。
- `observe_risk_period(report, snapshot, **qualification)`：在同一金融操作鎖內執行上述流程，將已驗證報告副本的權益、外部流與基準綁入合成快照，觀測並保存控制狀態，回傳 `(report, gate)`。gate 不通過不更新為健康風控；摘要本身不代表 gate 通過。
- `risk_period.durable_ledger()` 缺首次基準回傳 None；已有基準才投影，不自動建立或封鎖。R1 `Snapshot` 另綁 `flow_basis_id`／`flow_start_ms`，不能把其他期間小計餵給日損計算。
- 沿用原 `DayBasis`／baseline evidence、SQLite writer 與風控 JSON；無 schema 變更、既有 DB 遷移、第二帳本或新背景服務。交易內 ownership 讀取重用一致快照 helper，避免巢狀 BEGIN。

## 本輪實際驗證

Python 3.14.6；全部使用 TemporaryDirectory、全新既有 schema DB、固定 clock、合成 report／FakeExchange，無外部 transport。

| 測試模組 | 通過數 | 主要證據 |
| --- | ---: | --- |
| `test_risk_period_r1` | 21 | 首啟、同日重啟、首次失敗重試、帳戶／環境／日界／逾時、提交資格、遺失／損壞、回滾／ACK 遺失、並發 latch、跨日持倉、入出金／邊界／去重、既有 blocker、零／負權益、篡改與呼叫端修改 |
| `test_risk`／`test_risk_journal`／`test_risk_supervisor` | 27 | Decimal、固定分母、原子風控保存、鎖存及合法減倉 |
| `test_reconciliation_gate`／`test_supervisor_reconciliation` | 32 | scope、identity、完整性、UNKNOWN、revision／responsibility fence |
| `test_verified_e0_lifecycle` | 22 | 舊基準 producer／provider、綁定、耐久保存及鎖存相容 |
| `test_execution`／`test_execution_supervisor` | 33 | UNKNOWN 晚成交／不盲重送、額度、執行與減倉衝突 |
| `test_protection` | 19 | 既有 P6 責任與保護生命週期 |
| `test_demo_quiescent_e0`／`test_demo_reconciliation` | 43 | 舊 Demo／Q1 合成流程相容，未做真實採集 |
| **合計** | **197** | **0 failure／error／skip** |

跨午夜持倉案例在隔離 fixture 中建立已歸屬部位，驗證新基準前禁增倉但允許合法減倉，合格新期間後恢復一般裁決；不代表可以接管遠端陌生部位。UNKNOWN 真正晚成交生命週期由既有 execution 回歸覆蓋，並非只靠報告字串案例。

實際命令：`py -3 -B -`，由 `unittest.TestLoader.discover('tests', pattern=module + '.py')` 載入下列 summary 的 12 個模組，合併後 `unittest.TextTestRunner(verbosity=2).run(suite)`。專屬測試亦以 `py -3 -B -m unittest discover -s tests -p test_risk_period_r1.py` 執行通過。重現合併測試：

```python
import json, unittest
from pathlib import Path
evidence = json.loads(Path('reports/risk-period-r1-local-sim-20261020/summary.json').read_text(encoding='utf-8'))
loader = unittest.TestLoader()
suite = unittest.TestSuite(loader.discover('tests', pattern=name + '.py') for name in evidence['module_counts'])
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
```

[逐項原始日誌](../reports/risk-period-r1-local-sim-20261020/unittest.log)、[模組計數／環境／來源 SHA-256](../reports/risk-period-r1-local-sim-20261020/summary.json)。開發期間發現並修復：交易內巢狀讀取、提交回覆遺失後關閉覆寫、非正當前權益漏掉 Hard，以及等待寫入後讀取呼叫端可變報告。最終 197 項是在上述修復後一次合併執行的結果。

## 交付限制與下一步

僅本機合成 USDT 單一無負債 equity scope；R1 使用受信 clock 與明示 freshness，本輪快照時間須等於注入的當前時間，未建立真實連續行情／多來源估值適配。不把 source receive time 說成交易所原子快照，不輸出完整台北日日損，也不保證離線期間越線後反彈能被捕捉。

尚未串入 HTTP API、正式服務啟動流程、前端或 Demo／Live；報告欄位已提供新語意，產品畫面尚未改動。舊 exact-midnight／Q1 producer 與 Demo 既有路徑保留，未擴大其適用範圍；舊明示 `basis_blocked_day` 不會被自動清除。未讀產品 DB／憑證、未採集、未交易、未操作 Git、未修改 Yaozi／並行前端，未執行前端 tsc／build 或全市場研究。

下一成果為指定 GPT-6 Sol 對上述來源、原始證據與必要風險案例做獨立驗收及唯讀 Git 核對；本文件僅為開發自測交付。commit／push、真實採集與 Demo／Live 仍需另有授權。[接續入口](current-handoff.md)。
