# 重播一致性報告 afde52fb110e472db065c945256794a0

> 一致性通過只證明部署路徑執行了和研究相同的決策；不證明成交模型接近真實交易所，不含資金費、保證金與強平，也不證明策略會獲利。

- 結果：PASS（門檻：Decimal 完全相等，誤差 0）
- 比對基準：research.backtest，同一份 K 線、參數與成本；funding_events=()、margin=None
- 核准 id：`12d224a4ee62b405f39ce9cb449ca1f9`（核准檔 `C:\Users\user\.t3\worktrees\CatOS\feat-step2-research-to--0735ac9fe296102b\outputs\selftest-step2-replay-20261113\test-approvals.jsonl`）
- 策略來源 sha256：`1596e3ace639379086f6fd5ff2ba73948697c2b34884366c3b32b15ba9ba6817`；build_id `1ad27d585c443fff15d4390fe7e383410d8be173d77e0b3a30e7f3bd666d70f5`；比對工具與研究引擎 sha256 `e2c3716ad3862387d03eb49c07fa13ad7c0372b726a09389e9a278d5c5ef82c5`
- 資料集：`okx-btc-usdt-swap-4h-20211106-20261106`，10956 根（預熱 192、評估 10764）
- 風控上限：`{"leverage": "3.0", "symbol_share": "0.50", "soft_loss": "0.10", "hard_loss": "0.20"}`

| 檢查 | 結果 |
| --- | --- |
| replay_completed | PASS |
| targets_equal | PASS |
| fills_equal | PASS |
| reversal_leg_prices_equal | PASS |
| equity_curve_equal | PASS |
| final_account_equal | PASS |
| realized_and_fees_equal | PASS |
| pending_intent_equal | PASS |
| risk_verdicts_ok | PASS |
| orders_terminal | PASS |

- Bot 成交 103 筆（合併後 103，反手 0 次）；研究成交 103 筆
- 風控判定：`{"RESERVED_SIMULATION": 103, "NO_CHANGE": 183}`；原因 `{"exposure_reserved": 52, "target_equals_position": 183, "legal_reduction": 51}`
- Bot 期末權益 10373.8899095；研究（關掉資金費與保證金）10373.8899095
- 重播耗時 756.415 秒；帳本 45764608 bytes
- 成交摘要 sha256 `f37793ab7266ae6deab880ee03ddc263c310d0e13022cc65699ab1c8e70bb937`；決策摘要 sha256 `3aa65a31157d192169c647019298da0d994b8b2e62dc18affccef4e9d9861c5d`

## 和已發表研究結果（含資金費與保證金模型）的差

- 期末權益 10370.6788014807133285613，與基準差 -3.2111080192866714387（資金費支付 3.2111080192866714387）
- 成交與基準相同：True；強平：False；保證金拒單 0 筆；保證金模型啟用：True
