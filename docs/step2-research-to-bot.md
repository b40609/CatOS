# 第 2 步：研究策略上 local-sim Bot 跑歷史重播（實作紀錄）

2026-11-12 使用者對 `docs/step2-research-to-bot-proposal.md` 8 題回覆「完全同意建議」（授權原文見 `AGENTS.md` 授權紀錄）。本文件寫實作了什麼、怎麼用、限制與驗證。設計理由與業界比較見提案。

> 一致性通過只證明部署路徑執行了和研究相同的決策；不證明成交模型接近真實交易所，不含資金費、保證金與強平，也不證明策略會獲利。

## 使用者要做的事：正式核准

代理不得執行核准或撤銷（`AGENTS.md` 紅線）。在 `C:\dev\CatOS` 的終端機（要互動式終端機，管線輸入會被拒絕）：

```
.venv\Scripts\python.exe -m catos.cli strategy identity
.venv\Scripts\python.exe -m catos.cli strategy approve --strategy donchian-breakout --version donchian-parameters-v1 --sha256 1596e3ace639379086f6fd5ff2ba73948697c2b34884366c3b32b15ba9ba6817 --profile catos\deployment_profiles\donchian-breakout-4h-192-48.json
```

- `identity` 列出可上 Bot 的研究策略與目前來源 sha256，先核對它和上面的 64 碼相同。
- `approve` 會重算來源 sha256、印出 manifest、參數、合約、週期、本金與成本，要你輸入 `approve` 才寫入；印出的 `approval_id` 之後撤銷要用。
- 紀錄寫在 `outputs/strategy-approvals/approvals.jsonl`（git 忽略、只在這台機器）。
- 撤銷：`.venv\Scripts\python.exe -m catos.cli strategy revoke --approval-id <id>`；列出：`... strategy list`。

核准後跑重播與比對（不用金鑰、不連網）：

```
.venv\Scripts\python.exe -m catos.cli replay --profile catos\deployment_profiles\donchian-breakout-4h-192-48.json --dataset okx-btc-usdt-swap-4h-20211106-20261106
.venv\Scripts\python.exe -m catos.cli replay-compare outputs\local-sim-replay\<run_id>
```

- 2026-11-14 起預設 `--limits current` 就是新風控值（1.0 倍有效槓桿 × 50% = 單幣 0.5 倍、Soft 5%、Hard 10%）；`--limits legacy-v1` 是之前的 3.0 倍／50%、10%／20%，用來對照或續跑用舊值錄的 run。原本的 `new-defaults` 選項已移除（工作包 B）。
- Kill-Switch 觸發中時重播啟動不了；重播中觸發，會在下一根 K 線前鎖存 `manual_kill` 並停止，不平倉（`docs/wp-b-kill-switch-proposal.md`）。
- `--pace per-bar-1s` 是每根 1 秒的展示步調（4H 五年約 3 小時，Ctrl+C 結束）；預設 `full` 全速。
- 進度與結果在策略中心頁下方的「研究策略上 Bot」面板（唯讀，每 2 秒更新）。

## 做了什麼

| 部分 | 檔案 | 內容 |
| --- | --- | --- |
| 核准紀錄 | `catos/strategy_approvals.py` | 只增 JSON Lines，每行存前一行 sha256；改一行、刪中間的行、換順序、截斷半行、非正規 JSON 或非 UTF-8 一律讀取失敗（fail-closed）。**偵測不到**：整行刪掉結尾的幾行，或把檔案還原成較早的版本（例如刪掉最後一筆撤銷，核准會恢復有效）；這需要檔案以外的錨點，和「程序上的防呆、不是安全邊界」一致（驗收觀察 1）。核准單位是部署設定（`catos/deployment_profiles/*.json`）。CLI 要完整 64 碼 sha256 且必須是互動式終端機。只有 `BOT_STRATEGIES` 列的策略可核准（目前只有 Donchian；工作包 E／F 的策略狀態取決於全部歷史，不可上 Bot）。lookback 上限 512 根。 |
| 兩層登錄 | `catos/strategy_registry.py` `resolve_deployment` | 內建層不變。研究製品只透過有效核准解析：策略、版本、來源 sha256（也核對研究白名單與磁碟上的檔案）、manifest 檔 sha256、entry、參數、張數、合約、週期、預熱、lookback 全部相符才通過。 |
| IPC | `catos/ipc.py` | `WorkerConfig.deployment`；檢查點 v2 只存 `event_seq` 與最後一根時間，不存策略狀態；`ready` 必須恰好在餵滿 lookback 根時為真；重啟歷史（最近 lookback 根已提交 K 線）在 init 訊框傳給 Worker。SMA 的 v1 檢查點與 wire 格式不變。 |
| Worker | `catos/worker.py`、`catos/worker_host.py` | 部署設定以核准解析；重啟時以歷史 K 線預熱重餵；每根前後都重新核對核准與來源，撤銷或改檔就停。子程序只多繼承 `CATOS_STRATEGY_APPROVALS`（路徑，不是憑證）。 |
| 帳本 | `catos/journal.py` | 部署設定的意圖 key 改為 `[環境, 帳戶, bot, strategy_id, version, approval_id, seq, 0]`（SMA 不變）；`history()` 讀已提交輸入給 Worker 重餵。schema 不變（仍是 7）。 |
| 反手 | `catos/risk.py`、`catos/execution.py`、`catos/supervisor.py` | `evaluate(allow_reversal=True)`（只有部署設定的 commit 用）：平倉腿要過減倉衝突檢查、整體要過增倉閘門與曝險預算，保留額度＝開倉腿。`dispatch` 先送 reduce-only 平倉單（order key `{"kind":"reversal_close","intent_key":…}`，不帶 intent），呼叫端對帳、重新觀察風險後再 `dispatch` 一次送開倉腿，開倉腿由已驗證的空倉重新評估。平倉腿送不出時，平倉腿與整個意圖在同一個交易內 ABORTED 並釋放額度，開倉腿不會單獨送出。 |
| 重播 | `catos/local_sim_replay.py` | 研究資料集（載入時核對 sha256）的真實時間戳 K 線走 Supervisor → Worker → 風控 → 執行 → FakeExchange；成交價與手續費由研究引擎同一段程式（`research._Ledger`）以下一根開盤＋滑價算出；資金費明示 0、無保證金模型；每根檢查核准；Soft／Hard 觸發、非預期判定、撤銷、故障都停止並記錄原因，不平倉、不釋放合約。可續跑（`replay_bars(..., resume=True)`，目前只能從 Python 呼叫，CLI 沒有續跑選項；新 Supervisor＋新 Worker，由帳本重餵；沿用第一段的 manifest，不另記續跑時的 build_id）。輸出 `manifest.json`、`status.json`、`events.jsonl`、`state.sqlite3`、`summary.json`。 |
| 一致性 | `catos/replay_consistency.py` | 唯讀開帳本，和關掉資金費與保證金的研究回測逐筆比對：每根 Worker 目標、成交（反手兩腿合併，兩腿價格須相同）、每根收盤帳戶檢視、期末帳戶、已實現損益與手續費、期末未成交意圖、風控判定（出現 REJECTED 就失敗）。另列和已發表研究結果（含資金費與保證金模型）的差。`--repeat-of` 比對兩次重播的決策與成交摘要是否位元組相同。 |
| 唯讀介面 | `catos/replay_api.py`、`frontend/cat-os-vite/src/components/catos/replay-panel.tsx` | `GET /api/workspace/replay`：核准清單（有效／撤銷／來源已變更）與最近 30 筆重播（進度、成交、期末權益、一致性）。沒有寫入端點。 |

## 限制

- 核准紀錄只在本機，換機器要重新核准；擋得住意外接線，擋不住刻意繞過的本機程式（P1 本來就不提供這種保證）。
- `CATOS_STRATEGY_APPROVALS` 可指定別的核准檔，只供隔離測試；每次重播的 manifest 與一致性報告都記錄實際用的核准檔路徑。
- 撤銷或改檔後，該帳本的 Supervisor 無法再解析設定，連釋放合約也做不到；要先重新核准。每次重播是獨立帳本與帳戶，不影響其他重播。
- 續跑只處理在 K 線之間停下的情況；中斷在成交途中（有未終結委託，或已保留額度、還沒送出的意圖）時，續跑一開始就停止（`resume_with_unresolved_orders`／`resume_with_reserved_unsent_intent`），不自動修復。
- 沒做（列為待辦）：local-sim 控制面（`control.json`）的重播模板與介面啟動按鈕；目前只能用 CLI 啟動重播，介面只看。提案曾列「依模板驗證 control.json」，因為只做唯讀介面就不需要動它，正式資料根的 `control.json` 不受影響。
- 資金費仍明示為 0；接進 Supervisor 屬於帳務改動，接 Demo 前另議。
- Worker 單根回應超過 5 秒（`WorkerHost` 既有逾時）就 fail-closed。2026-11-13 同機跑前端建置時實際發生一次；以 `replay_bars(..., resume=True)` 續跑即可，決策與成交摘要和不中斷的重播位元組相同（帳本本身不是位元組相同：重啟會多幾次 epoch 與一次風控觀測）。

## 驗證

見 `docs/next-steps.md` 本節與 `reports/step2-research-to-bot-acceptance-20261112/`。
