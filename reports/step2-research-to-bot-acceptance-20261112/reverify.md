總結論：PASS（沒有阻斷缺陷；觀察 1 到 5 的處理都確實做到，沒有引入新問題；有 4 項新的非阻斷觀察，都是文件措辭或續跑紀錄的完整度）

# 第 2 步獨立驗收：觀察處理的重驗

- 驗收者：獨立會話（Claude Opus 5.5），沒有參與開發，也不是首次驗收的會話。2026-11-13。
- 範圍：`git diff 220de36b..c52838d8`（HEAD `c52838d8`），只重驗受影響範圍：觀察 1 到 5 的處理，以及新證據 `final-resumed`。
- 唯讀：除了本檔，沒有修改 repo 任何檔案，沒有 commit 或 push。帳本一律用 `mode=ro&immutable=1` 開啟，或先複製到 scratchpad 再處理。測試核准紀錄只放在暫存目錄並用 `CATOS_STRATEGY_APPROVALS` 指向。沒有執行 `strategy approve／revoke`（`outputs/strategy-approvals/` 驗收前後都不存在），沒有動 `outputs/research-web`、`outputs/local-sim-control`、`outputs/local-sim-r4`，沒有連網、沒有讀憑證，沒有重跑 4H 全量重播。
- 附帶影響：後端整套測試照既有行為在 `outputs/` 多留 2 個 fixture 目錄（`workspace-w6-fixture-test-02d35c57…`、`workspace-w8-fixture-test-fd8f4607…`，git 忽略），我沒有刪除。

## 實際執行的檢查

| # | 指令／做法 | 輸出摘要 |
| --- | --- | --- |
| A | `PYTHONPATH="<工作樹>;<工作樹>/tests" C:/dev/CatOS/.venv/Scripts/python.exe -m unittest tests.test_step2_deployment -v` | `Ran 23 tests in 23.508s`、`OK`，exit 0。含新測試 `test_resume_refuses_a_reserved_unsent_intent ... ok`、`test_edited_removed_or_truncated_lines_fail_closed ... ok` |
| B | `C:/dev/CatOS/.venv/Scripts/python.exe -m unittest discover -s tests -p "test_*.py"`（同上 PYTHONPATH） | `Ran 925 tests in 133.302s`、`OK (skipped=11)`，exit 0（首次驗收 924，多 1 個是新測試）。過程中有既有訊息 `Port 63804 already in use. No process stopped and no alternate port selected.`，不影響結果 |
| C | `npm --prefix frontend/cat-os-vite run typecheck`；`npm --prefix frontend/cat-os-vite test` | typecheck exit 0；`tests 21`、`pass 21`、`fail 0` |
| D | `local_sim_replay.build_id()`（HEAD）；`research_catalog.files_hash(("catos/replay_consistency.py","catos/research.py"))` | `1ad27d585c443fff…66d70f5`；`e2c3716ad3862387…5c5ef82c5` |
| E | 自寫 `ledger_check.py`、`ledger_check2.py`（scratchpad）：唯讀比對 `final/afde52fb…` 與 `current-a/fdae007a…`、`current-b/6c4e2156…` 帳本與 events | 見第 2 節 |
| F | 自寫 `recompare.py`（scratchpad）：把 final 與 current-a 的整個目錄複製到 scratchpad，用 HEAD 的 `replay_consistency.compare`／`compare_repeat` 重算 | `passed True`，10 項 check 全 True；重算報告和存檔的 `consistency.json` 完全相同 `True`；repeat 只有 `build_id: False`，其他全 True |
| G | 自寫 `adversarial_reverify.py`（scratchpad，合成資料、隔離核准檔與資料根，3 個測試） | `Ran 3 tests in 5.558s`、`OK`；輸出見第 1 節 |
| H | `cmp` 報告目錄的 `*-consistency.json`、`final-resumed-summary.json` 和 `outputs/selftest-step2-replay-20261113/` 原檔；`evidence.json` 兩處副本 | 全部位元組相同 |

沒做的：
- 沒跑前端 `build` 和 `node frontend/cat-os-vite/tests/simulation_integration_test.mjs`（前者寫入 `dist/`，後者要起服務與埠，超出唯讀範圍），也沒有在瀏覽器實際看「測試核准」標記。只用 typecheck、前端測試與後端 `replay_overview` 的輸出驗證。介面屬「未經獨立驗收」範圍。
- 沒有重跑 4H 全量重播（依指示）。

## 1. 觀察 1 到 5 的處理

| # | 處理 | 重驗結果 |
| --- | --- | --- |
| 1 | 文件改寫＋測試記錄已知限制 | 通過。`docs/step2-research-to-bot.md:36` 現在寫明「整行刪掉結尾的幾行，或把檔案還原成較早的版本」偵測不到，和程式行為一致（`catos/strategy_approvals.py` 只從頭驗鏈）。`tests/test_step2_deployment.py:147-150` 把「只剩第一行仍可讀」寫成斷言，符合文件。 |
| 2 | 非 UTF-8 改丟 `ApprovalError`；端點另接 `OSError`／`ValueError` | 通過。`catos/strategy_approvals.py:112-116` 的 `_text`，`read_records`（`:258`）與 `load_profile`（`:189`）都改用它。實測（檢查 G）：核准檔尾端加 `b"\xff\xfe\n"`，`read_records` 與 `find_active` 都丟 `ApprovalError approval_invalid_utf8`；`replay_overview` 回 `approvals_state: unavailable`、issues `['approvals_approval_invalid_utf8']`，不再 500。`ApprovalError` 本來就是 `ValueError` 子類（`:61`），`catos/replay_api.py:31` 多接的例外沒有放寬到吞掉別的東西。 |
| 3 | 續跑先檢查 `risk_orders`／`outbox` | 通過。`catos/local_sim_replay.py:266-270`。`reservations` 與 `outbox` 在同一交易插入（`catos/journal.py:1021-1022`），所以查 `outbox` 就涵蓋 `reservations`。實測（檢查 G）：在反手平倉腿成交後、開倉腿送出前中斷，帳本留 `risk_orders 1`、`outbox 1`；續跑立即 `stopped`／`resume_with_reserved_unsent_intent`，委託數前後都是 2，沒有多送。開發者的新測試（送單前中斷）也通過（檢查 A）。正常在 K 線之間停下時兩表必為空（每根的意圖在同一輪就成交並釋放，`:171-172` 的 `reservation_not_released` 檢查），不會誤擋。 |
| 4 | 端點每筆重播加 `approvals_path`、`formal_approval`；介面標「測試核准」 | 通過。`catos/replay_api.py:67-68`；`frontend/cat-os-vite/src/contracts/replay.ts:35-36`；`frontend/cat-os-vite/src/components/catos/replay-panel.tsx:124-126`。實測：manifest 指向 `DEFAULT_PATH` 的重播 `formal_approval: True`；缺 `approvals_path` 的舊 manifest 進 `run_unreadable:y`，不會被當成正式核准。前端沒有執行期驗證，欄位缺漏時 `!undefined` 會顯示「測試核准」，方向是保守的。 |
| 5 | 一致性報告加 `tool_sha256` | 通過。`catos/replay_consistency.py:260` 雜湊 `replay_consistency.py`＋`research.py`，markdown 也列出（`:339`）。四輪報告都是 `e2c3716a…`，等於 HEAD 現算值（檢查 D）。 |

## 2. 新證據：final-resumed

結論：通過。續跑後的帳本完整連續，決策與成交和 current-a 相同，中斷那一根沒有重複決策或漏處理。

- 中斷點：第一段 `status` 是 `failed`、`bars 2377`、`WorkerError: worker event failed: TimeoutError:`；events 的 `{"kind": "resumed", "after_seq": 2377, "position": "0"}`。也就是 seq 1 到 2377 已提交，逾時發生在 **seq 2378**（0 起算的 index 2377）。我用合成資料重現同一情況（檢查 G，`test_worker_timeout_then_resume_matches_uninterrupted`）：Worker 在某根丟 `WorkerError` 後，該根的 `inputs` 留在 `PENDING`；續跑時 `Journal.prepare` 找到同 hash 的 PENDING 列就沿用（`catos/journal.py:948-952`，內容不同會隔離 Bot），由新 Worker 重新算並提交。結果 `completed`，和不中斷的重播 decision／fills digest 相同。
- 帳本完整連續（檢查 E）：`inputs` 10,956 列，seq 1 到 10956 連續，0 列非 COMMITTED；`bots.checkpoint_json` 的 `event_seq 10956`、`consumed_seq 10956`，和 current-a 相同。
- 逐列和 current-a 比對（帳戶 id 正規化後）：
  - `inputs.input_json`、`input_hash`、`before_json`、`result_json`、`result_hash`：10,956 列全部相同。所以每根 K 線、每根收盤給 Worker 的帳戶檢視、每根 Worker 回應都相同。
  - `inputs.receipt_json`：剛好 8,579 列不同（seq 2378 到 10956），去掉 `epoch` 後 0 列不同。
  - `intents` 286 列：seq、目標、處置、原因全部相同；`epoch` 在 seq <= 2377 的 55 列相同，之後 231 列都是 +3（重啟遞增的 fence epoch）。沒有同一 seq 出現兩筆意圖。中斷點附近的意圖是 seq 2334 與 2415，seq 2376 到 2379 都沒有意圖。
  - `execution_orders` 103 筆：除了 `clOrdId`（每輪不同，current-a 對 current-b 也不同）與 `epoch`（79 筆 +3）之外全部欄位相同，`report_json` 去掉 id 後相同；全部 `FILLED`、`settled`，`clOrdId` 103 個各不相同，沒有一個意圖對應兩筆委託。
  - `execution_fills` 103 筆：數量、價格、手續費逐筆相同。
  - `reservations`／`outbox`／`risk_orders` 期末都是 0；`ownership` 相同。
  - events：`fill` 103 筆（去掉 request 後）相同；`day_basis` 1,795 筆去掉 digest 後和 current-a 相同（digest 含帳戶別名，current-a 對 current-b 也不同），沒有重複建立當日基準。
- 風控狀態唯一的實質差異：`risk_control.state_json.seq` 是 10765，current-a 是 10764。原因是 seq 2378 的風控觀測（`local_sim_r4.observe`）在第一段已持久化，Worker 才逾時，續跑時同一根又觀測一次。快照時間與權益相同，沒有觸發任何原因、沒有新基準，決策與成交不受影響。見觀察 R3。
- build_id：first session 的 manifest `build_id` 是 `1ad27d585c443fff…66d70f5`，等於 HEAD 的 `local_sim_replay.build_id()`（檢查 D）。HEAD commit 時間 15:04（+08:00），第一段 14:46 開始、續跑在 14:50 到 15:03，都在 commit 前；RUNTIME_FILES 雜湊相同代表第一段跑的就是已 commit 的執行端程式。續跑那段用的程式沒有被另外記錄，見觀察 R2。
- `repeat_current_a_vs_final_resumed`：decision_digest、fills_digest、summary_fills_sha256、approval_id、bars 都相同；`build_id` 不同（`d34d09dd…` 對 `1ad27d58…`），所以這筆比對的 `passed` 是 `false`。這和開發者說明一致（current-a 是修正前的程式），不是一致性失敗。我用 HEAD 程式在 scratchpad 複本上重算（檢查 F），結果相同。
- final-resumed 對研究回測的一致性：重算 `passed True`，`targets_equal`、`fills_equal`、`equity_curve_equal`、`final_account_equal` 等 10 項全 True；期末持倉 -1、權益 10373.8899095，和 current-a 相同。

## 缺陷

### 阻斷

無。

### 非阻斷觀察

- **R1. 文件說「用 `resume` 續跑即可」，但 CLI 沒有續跑選項。** `catos/local_sim_replay.py:387-392` 的 `replay` 只有 `--profile／--dataset／--limits／--pace／--output-root／--max-bars`；續跑只能用 Python 呼叫 `replay_bars(..., resume=True)`（開發者的證據也是用 `selftest-evidence/resume_4h_final.py`）。`docs/step2-research-to-bot.md:42`、`:54` 沒寫怎麼續跑。建議補 `--resume <run_dir>`，或在文件寫明目前只能用 Python 呼叫。
- **R2. 續跑不記錄、也不核對續跑當下的程式版本。** 續跑直接沿用第一段的 manifest（`catos/local_sim_replay.py:223-224`），`resumed` 事件只有 `after_seq` 與 `position`（`:274`）。如果兩段之間改了程式，manifest 的 build_id 仍是第一段的，帳本看不出來。這次因為兩段都在 commit 前、且第一段 build_id 等於 HEAD、結果和 current-a 相同，不影響結論。建議在 `resumed` 事件寫入 `build_id()`，或和 manifest 不同時停止。
- **R3. 「位元組相同」與「第 2,377 根」措辭不精確。** `docs/step2-research-to-bot.md:54` 說續跑「結果和不中斷的重播位元組相同」，實際上相同的是決策與成交摘要；帳本本身不是位元組相同（續跑後 epoch +3、風控觀測 seq 多 1）。`fixes.md:14` 說在「第 2,377 根」逾時，實際是第 2,378 根（seq 2378，index 2377）。建議改成「決策與成交摘要相同」與「seq 2378」。
- **R4. `docs/next-steps.md:84` 還是佔位文字**「驗證與獨立驗收：見本節最後（合併前補上）」。合併前要補上本檔與 `acceptance.md` 的結論與測試數字。

首次驗收的觀察 6（反手沒有真實資料覆蓋）維持原狀，開發者已在文件與交接寫明，不再列。

## 結論

觀察 1 到 5 的處理都確實做到：文件和實際行為一致、非 UTF-8 變成 fail-closed 的 `ApprovalError` 且端點不再 500、續跑遇到已保留未送出的意圖（含反手兩腿之間）立即停止、介面能分辨測試核准、一致性報告記錄比對工具雜湊。final-resumed 帳本 10,956 根連續且全部提交，和 current-a 的每根輸入、Worker 回應、意圖、委託與成交逐列相同（只差重啟遞增的 epoch 與一次重複的風控觀測），中斷那一根沒有重複決策也沒有漏處理；第一段的 build_id 等於 HEAD。後端整套 925 個測試、第 2 步 23 個測試、前端 typecheck 與 21 個測試都通過。

驗收用的腳本在 scratchpad（不在 repo）：`ledger_check.py`、`ledger_check2.py`、`recompare.py`、`adversarial_reverify.py`。
