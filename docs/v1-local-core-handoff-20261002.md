# catOS v1 本機核心交驗

更新：2026-10-02。負責者：Codex（開發及自測）。狀態：已實作、開發自測完成；待 WorkBuddy 獨立驗收與 Git 核對，未宣稱最終 PASS。

## 已交付流程與差異

外部 AI 使用 stdio MCP 建立不可變 Python 版本；策略中心顯示原始碼、說明、預設參數與使用中 Bot，支援相同製品契約的 JSON 檔及附版本資料的 Python 檔匯入。使用者檢查程式／依賴並勾選信任，人工分配 Bot、啟動／停止。真正由獨立 Worker 執行選定版本，完成／停止成果持久化，重開服務後 UI 與 MCP 可讀相同成果。

本輪核心新增：`catos/python_strategy.py`、`strategy_library.py`、`strategy_mcp.py`；修改 IPC、Worker／host、local_sim_control service／API／runner、journal。Bot 保存版本、完整製品 hash、參數快照；修改建立新版本，既有 Bot 不變。journal 的 Python 委託身分使用真實 strategy_id／artifact_hash，保留既有 SMA 路徑相容性。父程序只驗證 AST／資料，不執行策略載入、初始化或狀態 hook。

前端新增 `v1.js`／`v1-core.css`，接入 home／desk HTML、workspace asset/build 清單；調整舊 JS 掛載及 simulation 成果摘要匯出。LOGO 旁模式選擇、策略檢查／匯入／信任／分配、啟停、歷史成果皆可操作。模式切換／刷新／換頁只改顯示，不控制 Bot。Demo／Live 明示未開放；回測／參數優化／Yaozi 保留入口並明示開發中。沒有內建 AI 聊天、想法輸入或模型 Key。

Antigravity 的 `frontend/workspace/v1-theme.css` 與 [視覺交接](v1-frontend-handoff-20261002.md)已存在，於最終 fixture 啟動前接入；未由本輪改寫。第一份 fixture 期間 theme 發生外部漂移，該基線保留，不當成最終來源驗證。後續改動均在第一份 fixture 關閉後，最終兩份 fixture 期間來源與輸入 47 項 hash 未變。

策略版本／Bot／命令帳使用 Supervisor 寫入的原子 JSON metadata；已有 pending／損壞時拒絕寫入，不自動解除。SQLite 沿用既有 schema，未做 migration／產品 DB 修改。版本庫上限 100、Bot 100、命令 500、metadata 4 MB；需擴充另評估，不靜默丟棄重送紀錄。版本建立、Bot 分配與控制命令同 request_id 同內容重送還原原結果，跨操作／不同內容衝突拒絕。

## Python、IPC 與 MCP 契約

製品精確欄位：`contract,strategy_id,version,name,description,source,defaults,warmup_bars`；contract=`catos.python-strategy.v1`。策略 ID／版本為 1–64 字元 ASCII token；名稱 120、說明 2000、原始碼 12000 UTF-8 bytes。預設／Bot 參數與 checkpoint 狀態使用有界 JSON，禁止 float；Decimal 參數用字串，數量／金額由策略轉 Decimal。參數／狀態上限 4096 bytes、深度 2、每個容器 64 項；warmup_bars 為 1–16。

Worker 契約：`Strategy(parameters)`；`update_indicators(bar) -> None`；`ready -> bool`；`on_bar(bar, account) -> Decimal | None`；`snapshot_state() -> dict`；`restore_state(state)`。目標是絕對合約張數，並非下單增量；None 不產生意圖。只有 Worker 執行這些 hook。預熱只更新指標／保存狀態，不呼叫交易決策，不保存交易意圖。checkpoint 綁完整 config／製品／參數／序號／預熱與策略狀態；新 Worker 還原後重放一致，版本、hash 或參數錯配拒絕。有界回覆、逾時與既有 JSON IPC／ACK 保留。

`strategy_contract` 提供實際 bar／account 型別及完整限制。新 Worker 只帶標準函式庫與專案模組，沒有憑證／交易 client／寫庫介面；第三方策略依賴未接入。沿用 P1 受信策略，普通 Python 程序隔離不提供防惡意讀檔／連網的 OS 沙箱保證。

MCP 僅 5 工具：

- `strategy_contract`、`list_strategy_versions`、`create_strategy_version(request_id, manifest)`。
- `list_simulation_results`、`get_simulation_result(run_id)`。

啟動：`python -m catos.strategy_mcp --base-url http://127.0.0.1:<已核對本機服務埠>`。只橋接 127.0.0.1，禁止 proxy／外部 URL；使用現有 research requirements 的 MCP 依賴。沒有 Bot 分配、啟動、停止或解除工具。未連接任何外部 AI 客戶端；本輪證明安裝的 MCP SDK 實際 stdio initialize／list_tools／call_tool，不宣稱客戶端相容性。

HTTP prefix：`/api/workspace/simulation`。GET：`version,strategy-contract,strategies,bots,runs,runs/{run_id}`。POST：`strategies` 製品建立、`bots` 人工信任分配、`bots/start`、`runs/{run_id}/stop`。嚴格 JSON／origin／build／instance 驗證；策略 body 32768 bytes，其餘命令 8192 bytes。原模板 start 路徑保留，同樣受持倉／風險保留阻擋。

## 前端欄位、DOM 與狀態交接

資料契約：策略 entry 含 `artifact,artifact_hash,allowed_modes`；Bot 含 `bot_id,mode,binding`（artifact/hash/parameters）；run 含 `run_id,control_state,config`、頂層 Worker／輸入 hash／終態欄位及持久化事件與帳戶成果。API 原始形狀以 [MCP 原始回覆](../outputs/v1-local-core-20261002-dev/mcp-results-final.json)為準，金額字串不可轉 float 做帳務。

DOM：`workspace-mode`、`v1-workflow`、`v1-heading`、`v1-mode-note`、`v1-status`、`v1-content`、`v1-refresh`、`v1-retry`；策略 `strategy-version,strategy-inspection,v1-all-strategies,v1-import,strategy-file,import-strategy`；Python 檔 metadata `import-id,import-version,import-name,import-description,import-defaults,import-warmup`；人工分配 `allocate-bot-id,allocate-parameters,trust-strategy,allocate-bot`；控制 `start-bot,start-bot-command,stop-bot-command`；成果 `result-run,result-summary`。home 六 widget 保留既有 ID，統一使用 `.widget-box-body`。

執行狀態：starting／running／stopping／completed／stopped／failed／recovery_required。非本機、未信任、preview、來源漂移、unavailable、pending、儲存失效及能力不合格時禁止相應操作。sessionStorage 於發送前保存完整原命令／build／instance；不確定結果只允許人工重送原命令。輪詢避免覆蓋未送出的表單。樣式可修改外觀，不改上述 ID、事件與資料契約；新來源接入須先關閉 fixture，再建新基線。

## 本輪自測與原始證據

[證據索引與命令](../outputs/v1-local-core-20261002-dev/index.md)。執行環境 Python 3.14.6。所有 SQLite 僅為本輪全新隔離 fixture／測試暫存 DB。

- 新 Python Worker／版本庫測試 7 項、API／MCP 契約 4 項通過。
- 既有受影響 94 項初跑 1 項失敗：舊控制命令 8193-byte body 回 422，應為 413。恢復 8192-byte 限制後，控制／新 API 33 項通過。
- journal 真實策略身分與 home DOM 相鄰修正後，Worker／journal／workspace 45 項通過。合計涵蓋 105 個 Python 測試，依受影響範圍重驗；不是最後一次單跑 105 項。
- JS 成果摘要工具 15 項通過；`node --check frontend/workspace/v1.js` 成功。這些不是 v1 UI 互動證據。
- 新 fixture 的真實 UI：檢查版本／勾信任／分配兩 Bot、JSON 檔匯入、啟動、running 期間 Demo→刷新→Live→home→本機、讀完成成果、持倉後停止、歷史重開與模式隔離。未用字串斷言宣稱互動通過。commands.jsonl 僅 start=2／stop=1／bots=2／strategies=4，換頁／模式沒有增加控制命令。
- MCP SDK 實際 16 次工具呼叫（建立批次 6、成果 5、歷史 5），五工具均使用；同 request_id 建立重送結果一致，list/get 結果一致，重開前後完整成果相同。
- 四份 final／history DB 唯讀核對 integrity、TEXT、固定 tag、預熱零意圖、checkpoint 決策根數、真實策略 intent identity 與 ownership；DB hashes 及 raw/effective input hashes 已保存。新 owner／instance 重開只讀歷史，無控制命令、無新 Worker。

最終來源 runtime build：`f791e202bb000bf2cce06433849fd3c86c8d49e0837cb77545ec73cc5b6d39ee`；workspace：`3f261bd0623e56eb23543e22a904616d13f73d372d59bd3cbb79a6b849e78b5e`。以 source-baseline-final.json 的逐檔 hashes 為準。

| Fixture | 埠／owner PID | instance | 狀態 |
| --- | --- | --- | --- |
| final | 60863／49772 | 868721f213644b64a81cb88b1a447d3b | 正常退出 0 |
| history | 53028／32204 | 4f3f59672376471eac8b9c4c6c62778f | 正常退出 0 |

啟動先原子綁定空閒 localhost port 0，僅管理本輪 owner。兩個 Worker PID 23348／34212 均 graceful shutdown／returncode=0；server exit.json、server log、owner-exit-evidence.json 與埠關閉證據已保存。所有 fixture 已關閉，不拿舊 owner 當接手者基線。

| Bot／run | 結果 |
| --- | --- |
| counter-final／0c7f81a812284eddbca2b7b088a93e57 | Counter Python 交替空／平倉，非 SMA；2 根預熱＋8 根正式，8 成交，部位 0；權益 1000.00385505 USDT，費用 0.00404495 USDT |
| hold-final／c60612f504954eeb92da5288d5744f38 | 2 根預熱＋1 根正式後人工停止；1 成交，保留 -1 張；權益 999.98919015 USDT，費用 0.00050985 USDT；阻擋新／舊 start，不清倉／解除 |

第一份 fixture 的來源漂移及初版 home body 掛載問題已保存，不冒充最終來源通過。MCP probe 初版需解析 SDK JSON text fallback；另一次 probe 缺少 tests import path 的失敗保留 log，修正呼叫後成功。這些沒有回寫封存證據。

## 限制與 WorkBuddy 必要重驗

這是每次 8 根合成 15m 已收盤 K 線的本機短程執行，固定 1000 USDT、fee 0.0005、slippage 2 bps、資金費 0；不是持續市場交易或全市場回測。持倉停止保留曝險與獨佔，不自動清倉、不 resume。模式切換已隔離顯示，本輪沒有 Demo／Live 執行或可用模式擴充。終態風控是最後已觀測狀態，不宣稱停機後持續監控。

未做 v1 pending 首次回覆遺失／刷新／重送的真實 UI 故障注入；命令重送與衝突有本輪單元／API及 MCP 同 ID 重送證據，歷史 W8 的互動證據不可冒充此版。Python 檔 UI 匯入已實作，本輪真實檔案互動覆蓋 JSON 製品，未互動驗證 .py 路徑。未保證全部視窗尺寸、第三方策略套件或外部 AI 客戶端。

WorkBuddy 先核對此文、逐檔 hashes、raw commands／MCP／exit／SQLite 證據，再按風險重驗 Worker checkpoint 身分、不可變綁定、重送衝突、預熱、持倉 stop、歷史與 UI 人工控制；.py 匯入及 pending 故障互動是可優先補證的未涵蓋部分。重驗建立全新資料根與 owner/build/instance，不使用已關閉 fixture 控制埠，不讀產品 DB／憑證、不碰正式服務或 recovery。fixture 工具輸出根須在本工作包 outputs 下，使用新的不存在名稱。獨驗不是機械重跑所有歷史測試。

Git 核對由 WorkBuddy 處理；本輪未執行 Git，不宣稱工作樹乾淨，也無法列完整其他未提交內容。上列核心檔、四份新測試／probe/evidence 工具與本輪文件為交驗範圍；既有 simulation_result_fixture.py 未改。其他工作及歷史檔保留。發現缺陷交 Codex 修復後重驗受影響部分；commit／push 另需明確授權。下一個成果是獨验結論；Demo 接線／帳戶來源／對帳／授權另案，不自行啟動。
