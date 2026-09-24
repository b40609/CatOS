# catOS 第一個安全策略閉環 local-synthetic handoff

日期：2026-09-23。狀態：**PASS（local synthetic integration acceptance）**。

## 本片目標

在不取得新 Demo private evidence、不連 OKX、不修改既有 project DB／schema 的前提下，把既有 formal reconciliation、`DemoTradeGrant`、Worker、Supervisor、Execution 與 restart responsibility reconciliation 串成同一條可重現驗收路徑，確認第一個安全策略閉環的本機契約已可組合運作。

本片不嘗試用 synthetic evidence 解除 production blocker，也不新增第二條交易、帳務、風控或 Supervisor lifecycle 路徑。

## 實際交付

- 新增 `tests/test_safe_strategy_loop.py`。
- 測試只使用 `FakeExchange`、`FakeClock`、temporary SQLite 與 synthetic formal evidence。
- 起始狀態沿用既有 formal happy-path 的合法本地 ownership baseline；全新、沒有 owner/reconciliation baseline 的 DB 仍維持 fail closed。
- synthetic complete classification + verified synthetic E₀ + F1-compliant evidence 先讓 formal reconciliation PASS；`gate.trade_authorized` 仍固定 `False`。
- Closed Bar 經 Worker 產生 entry intent；尚未安裝 `DemoTradeGrant` 時 dispatch 以 `demo_trade_grant_required` 阻斷，`FakeExchange` 0 calls。
- 安裝綁 account／Bot／instrument／reconciliation evidence／revision／time／mark-notional limit 的一次性 grant 後，entry 由既有 Supervisor/Execution 路徑送往 `FakeExchange`，payload 保留固定 tag `41cb53c54d6dABDE`、`cross`、`net`、非 reduce-only。
- synthetic fill durable 落入既有 Journal；Supervisor close/restart 後 active grant 不復活，但 consumed authorization ID 由既有 execution metadata 恢復。
- restart 後以 synthetic remote position/order/fill responsibility evidence 再跑 formal reconciliation，成功綁定 `remote_pos_id` 並回到 `LOCAL_READY`；同一 consumed authorization ID 仍不可重用。

本片未修改 production runtime 程式；既有程式契約已足以通過上述 integration acceptance，因此只新增專屬驗收程式與交接／證據。

## 保持不變的邊界

- Decimal、固定 tag、Supervisor 唯一交易出口、Worker 無交易憑證／client、UNKNOWN 不盲重送、risk latch 與原子額度規則不變。
- formal reconciliation PASS 不等於 Demo write permission；`trade_authorized=False` 不變，entry 仍需獨立有效 `DemoTradeGrant`。
- restart 不恢復 active grant；已進 transport 的 authorization ID 不可因 restart 重用。
- production classification 仍為 166/185、19 unknown、`complete=false`；未知 subtype 繼續 `unknown_external_flow` fail closed。
- D1-A 精確 Asia/Taipei 午夜 E₀ 尚無合格 production producer/source，不以 synthetic baseline、近午夜 observation、UTC statement 或 bills 倒推替代。
- dedicated Demo subaccount／foreign responsibility 仍未取得新的 real Demo private read-only evidence；synthetic `uid != mainUid` 不構成指定專用子帳戶 identity 證據。
- 未接 Demo／Live transport、未讀 credential、未寫 project DB、未改 schema、未修改 `CatOS_Yaozi`、未 commit／push。

## 驗證

- 專屬：`PYTHONPATH=.;tests python -m unittest tests.test_safe_strategy_loop -v`：1/1 OK。
- 直接相關回歸：`tests.test_safe_strategy_loop + tests.test_demo_reconciliation + tests.test_demo_trade_authorization + tests.test_supervisor_reconciliation`：63/63 OK。
- 專屬測試只建立 temporary SQLite；沒有使用 project DB。

機器可讀證據：`outputs/catos-safe-strategy-loop-verification-20260923.json`。

## 後續 blocker

目前沒有新的 local reconciliation／grant／restart integration correctness blocker 可在既有政策下直接解除。production 前仍缺：

1. 19 個 flow subtype 的足夠外部證據或明確會計政策。
2. D1-A 精確午夜 E₀ 的可信 production producer/source。
3. 指定 dedicated Demo subaccount identity 與 foreign position/order/algo responsibility 的新一輪 real Demo private read-only evidence；需要使用者另行明確授權該次唯讀採集。
4. 真正 Demo POST／cancel 等 write transport 仍需獨立明確授權；本片不構成該授權。
