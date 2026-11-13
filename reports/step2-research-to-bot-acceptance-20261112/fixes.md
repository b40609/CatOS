# 驗收觀察的處理（開發者，2026-11-13）

獨立驗收 `acceptance.md`：PASS，無阻斷，6 項非阻斷觀察。處理如下（自測；受影響範圍另交獨立重驗，見 `reverify.md`）。

| # | 觀察 | 處理 |
| --- | --- | --- |
| 1 | 文件說「刪、截斷一律失敗」，但整行刪掉結尾幾行或還原舊檔偵測不到（刪掉最後一筆撤銷，核准恢復有效） | 改文件（`docs/step2-research-to-bot.md`「核准紀錄」列）寫明偵測不到的情況；測試加一條記錄此已知限制。不加外部錨點（屬 P1「程序上的防呆、不是安全邊界」）。 |
| 2 | 核准檔非 UTF-8 時丟 `UnicodeDecodeError`，唯讀端點 500 | `strategy_approvals._text` 改丟 `ApprovalError("approval_invalid_utf8")`；`replay_api` 另外接住 `OSError`／`ValueError` 顯示不可用。加測試。 |
| 3 | 已保留額度、還沒送單時中斷，續跑多處理 3 根才停 | 續跑一開始檢查 `risk_orders`／`outbox`，有就停在 `resume_with_reserved_unsent_intent`，不送任何單。加測試。 |
| 4 | 唯讀介面看不出重播用的是哪個核准檔 | 端點每筆重播加 `approvals_path` 與 `formal_approval`；介面在非正式核准檔的重播旁標「測試核准」。加測試。 |
| 5 | build_id 沒涵蓋比對工具 | 一致性報告新增 `tool_sha256`（`catos/replay_consistency.py`＋`catos/research.py`）；三輪既有帳本重產報告。 |
| 6 | 反手只有合成測試覆蓋 | 不改；4H 資料上 0 次反手，已寫在文件與交接。 |

另外：觀察 3 的修正動到 `catos/local_sim_replay.py`，為了讓證據對應最終程式，用最終程式再跑一次 4H 全量。那次在第 2,377 根因 Worker 單根回應超過 5 秒逾時而 fail-closed（當時同機在跑前端 build／tsc）；接著用 `resume` 以新 Supervisor＋新 Worker（由帳本已提交的 192 根重餵，未提交的那根重新處理）跑完，決策與成交摘要和 current-a 位元組相同（`selftest-evidence/evidence.json` 的 `repeat_current_a_vs_final_resumed`，build_id 不同是預期）。這同時是 4H 實際資料上的檢查點 v2 重啟證據。
