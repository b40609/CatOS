# I-b-4：已授權單次 Demo 唯讀採集交接

2026-09-15 歷史授權：使用者確認 Global 註冊站點，後續澄清 `okx-demo` 為 Demo 主帳戶，並將該輪指定來源更新為 `C:\Users\user\Desktop\OKX_API.txt`。這是 I-b-4 有界唯讀例外，不改一般專用子帳戶交易政策，亦不擴張至其他憑證／帳戶／交易。

**目前狀態：歷史最後一輪 config gate 與 13 個來源分頁完成，但帳戶對帳未通過；reconciled=false、trade_authorized=false。**各輪是在使用者追加明確指令後執行，先前失敗及最新結果皆保留於下文，不能合稱只有一輪。所有已記錄單次授權均已執行並停止；任何新的真實採集須另有明確授權。本次修補只用合成測試程式與靜態核對，尚未執行驗證、憑證讀取或重跑。

## 固定執行設定

| 項目 | 本次設定 |
|---|---|
| 帳戶／環境 | okx-demo，Global Demo 主帳戶（依使用者澄清）；非 Live |
| 主機 | openapi.okx.com:443，驗證 TLS，固定 GET，Demo header=1 |
| 商品 | BTC-USDT-SWAP |
| 時間窗 | 啟動前捕捉 end_ms，start_ms=end_ms−86,400,000；採集期間不移動 |
| 預算 | 全批最多 120 次 driver 嘗試；每端點最多 40 頁，每頁 100 筆 |
| 時間 | 每次 10 秒，全批 180 秒；保留 I-b-3 的 DNS 無硬時限限制 |
| 節流／重試 | 間隔至少 500ms；僅 429／50011，每頁最多重試 2 次；全數計入同批預算 |
| 保存 | 首輪不寫帳戶資料檔，不寫 DB；完整假名化報告與 audit 只留記憶體，終端只輸出摘要 |

順序固定為 account_config → public_time → account_instruments → public_instruments → balance → positions → orders_pending → algo_pending → mark_price → orders_history → fills → bills → algo_history。

使用 fills／bills 的近期端點即涵蓋本次 24h 候選窗口，不額外查 archive 或 fills_history，不自動切換來源。普通歷史委託以 cTime 篩選；algo_history 沒有 begin/end，保留來源可返回的受預算限制歷史，不宣称其僅限 24h。algo 7／21 分支及空頁終止規則沿用 I-b-3。單筆 order／order_algo 補查不列入首輪；P6 子單缺口留作差異，不自行擴張請求。

## 新入口與 config 前置檢查

`catos/demo_collection.py`：

- parse_credentials：純解析函式，接受單組 JSON、有標籤的 key=value／key:value，或 `default_profile` 精確指向 `[profiles.<name>]` 的 profile 格式；指定 profile 必須 `demo=true`。標籤支援 api_key／API KEY／apikey、secret／secret_key／SecretKey／api_secret、passphrase／api_passphrase 及部分 okx 前綴。未知標籤、同義重複、缺欄位、未知／重複 profile 或歧義選擇均拒絕，不猜哪一組才是 Demo。
- load_authorized_credentials：只讀使用者指定檔案，最多 16KiB，UTF-8（可含 BOM）或 BOM UTF-16；拒絕解析到其他路徑的 symlink／junction。讀取／格式失敗只回固定錯誤代碼，不列出內容、行號內容或 parser 例外。它不讀 env、搜尋其他檔案或自動改寫來源。
- run_once：接受記憶體 credentials 與必填 sender；假資料驗證不得使用真實 loader 或 HTTPS sender。共用 clock／sleep 供另一模型測試。
- `_ConfigGate`：先取得唯一 config，確認 uid=mainUid（依使用者最新指示直接使用 Demo 主帳戶 API）、net_mode、acctLv 2／3、明示 read_only、權限限 read_only／trade（不接受 withdraw 或未知值）、已知角色 0／1／2。保留 config 原頁供 decoder，檢查失敗後禁止其餘 HTTP 呼叫，不修改帳戶模式。
- `okx_collection.collect_plan` 新增 opt-in `stop_on_incomplete`；本入口指定 account_config。避免 config 曾在 transport 成功、卻被 driver 因逾時／序列化等原因拒絕後，仍繼續採集其他來源。預設空 tuple，保留既有呼叫行为。
- config 內容未通過但頁證據已接受時，下一次 driver 嘗試只在本地丟出 interrupted；會占一次 driver 嘗試，但不呼叫 sender。後續來源列 not_started。config HTTP／頁證據失敗則立即停止其餘來源。

本次身分依據為「使用者指定的憑證來源＋簽名請求成功＋主帳戶關係」。沒有預先提供期待 uid，因此不能宣稱已獨立比對指定 uid；摘要明示 expected_uid_independently_matched=false。Global／Demo 對應若被 API 拒絕，只回差異，不嘗試其他主機或移除 Demo header。

沒有載入本地交易帳本／歸因資料／UNKNOWN 清單或資金流白名單；摘要明示 local_attribution_not_loaded。回應中責任不能由空的本地集合推定已歸因，不能解除 UNKNOWN、latch 或所有權。config 的 acctLv／posMode 不證明所有現存部位都為 cross；逐部位模式仍由 decoder 列差異。

## 2026-09-15 診斷修補（待驗證）

餘額 decoder 現在回傳固定欄位路徑／原因碼；runner 的 `record_diagnostics` 只彙總 alias／field／reason／count，不輸出值、幣別、ID 或原始例外。保留 `invalid_record:balance` 及全部 gate；完整報告仍不寫檔。新增合成回歸測試但未執行。此變更避免未來獲授權採集結束後只剩籠統錯誤碼，不能還原本文件歷史採集已丟失的回應，也不構成新的採集授權。

## 輸出與錯誤處理

CollectionOutcome 隱藏 repr，內含 report、audit、summary。report 與 audit 只留記憶體，沒有預設檔案輸出；report 的原 content_digest 不因額外 runner 註記而被修改。

CLI 只 print summary：固定帳戶代稱／主機／商品、時間窗、完成狀態、config gate、嘗試／頁數／facts 數量、差異代碼與報告 digest。不輸出 raw payload、uid、任何委託／部位 ID、金融值或憑證。CLI 捕捉例外且不列 traceback／locals。人工中斷只回 interrupted；不得自動重啟補跑。

status=collected 只表示分頁及 config gate 完成；reconciled／trade_authorized 永遠 false。資料不足、未知分類、陌生責任、P6 關聯缺口、新鮮度／日初權益未核實仍需如實交付，空帳戶亦不能證明已驗證費用或保護触發生命週期。

## 另一模型的執行順序

1. **先只用假資料建立並執行專屬測試**：新建 test_demo_collection.py，檢查指定設定、credential 格式／去重／固定錯誤、缺欄位時 sender 零次呼叫、指定路徑／大小／encoding 限制（必須以 mock／合成 tempfile 取代真實來源）、config gate 各拒絕路徑、config 逾時後零後續 HTTP、重試與共享預算、摘要不含秘密／ID／金融值、所有權未核實及完整性語義。沿用 fake sender／clock／sleep，勿以真實 API 充當測試。
2. 受影響回歸範圍為 test_okx_collection.py 與新 test_demo_collection.py；必要時依失敗原因補跑其他直接受影響模組，不自動跑全域。編譯／靜態掃描／Git whitespace 由驗證模型執行；也納入未追蹤檔。
3. 前述驗證通過後，使用已獲授權的固定入口執行**一次**：

   ```powershell
   python -m catos.demo_collection --execute-authorized
   ```

   不帶旗標只顯示說明，不读憑證或連網。不把憑證值放進命令列、不用 Get-Content／cat 顯示檔案、不設 shell tracing，不把輸出 redirect 為帳戶資料檔。若格式不支援，僅回報缺少的格式資訊，不能貼內容；修正解析器以合成資料驗證後處理，不改原檔或改找其他來源。
4. 採集出現 partial／timeout／認證或能力錯誤就交付該結果，不自動擴增預算、換主機、重跑或新增端點。CLI exit 2 不是重跑指令。保留摘要中的實際時間窗、driver/wire 嘗試數、完成來源、差異與尚缺能力；如果實際請求尚未開始，也要明示。
5. 將**不含私人帳務的驗收摘要**寫回本文件與 WORK_PLAN，區分合成測試與實際採集。使用者未授權 commit／push、交易 DB 修改、Demo 下單／撤單、J 或 Live；到此停止。

## 驗證／實際採集結果

### 使用者改為 net_mode 後的本次單次採集

使用者確認 acctLv=2，並已自行在 OKX App 將 long_short_mode 改為 net_mode，明確要求直接執行原授權的單次採集。本輪未修改 gate、帳戶設定或程式，僅執行一次既有 `python -m catos.demo_collection --execute-authorized`；exit 0，status=collected、config_gate_passed=true、collection_complete=true。

- 實際窗口（Unix ms）：1789356296025 至 1789442696025；開始 1789442696025，完成 1789442716253。
- 13 個來源分頁全部完成；driver 41 次、wire 41 次。完成指分頁及 config gate，不代表帳戶對帳或可交易。
- 摘要差異：day_baseline_unverified、foreign_algo、freshness_unverified、invalid_record:balance、local_attribution_not_loaded、missing_or_ambiguous:balance、mode_mismatch、p6_child_order_gap、p6_protection_unverified、p6_triggered_not_reconciled、window_coverage_unverified。
- balance HTTP／分頁成功但 decoder 無法產生有效 balance fact；config gate 已通過，仍有其他資料的 mode_mismatch，摘要不足以定位具體欄位。不得由此猜測原因或放寬檢查。
- reconciled=false、trade_authorized=false。沒有載入本地歸因證據，foreign_algo 不構成接管或處置依據。
- 終端只輸出既有安全摘要；未輸出憑證或原始回應、未另存私人帳務。程序結束後本批完整記憶體報告未保留，後續診斷不得宣稱仍持有該原始資料。
- 未重跑、未調整 gate、未下單／撤單、未修改交易 DB／帳戶設定、未碰 Live、未 commit／push。本輪無程式變更，未重跑合成測試或 Git 檢查。停止於結果交付；I-b-4 實際採集已執行，完整帳戶對帳驗收仍未通過。

### 先前執行紀錄

2026-09-15 由執行模型完成合成驗證與該輪一次正式採集（歷史紀錄）：

- 新增 `tests/test_demo_collection.py`，9／9 通過；`test_okx_collection.py` 13／13 通過。另以 `py_compile` 檢查 `demo_collection.py`、`okx_collection.py`、`okx_http.py` 與新測試，均通過。
- `git diff --check` 未發現 whitespace error；工作樹仍有既有與本階段未追蹤檔案，Git 只回報 LF→CRLF 提示。新測試另以 no-index `--check` 檢查，亦只有 LF→CRLF 提示。
- 新指定來源為 UTF-8-sig 的明示 profile 格式；parser 只依 `default_profile` 精確選取對應 profile，並要求該 profile `demo=true`。沒有輸出或保存任何憑證值。
- 已依授權執行唯一一次 `python -m catos.demo_collection --execute-authorized`。結果 status=`incomplete`、config_gate_passed=false；安全摘要顯示 `config_not_subaccount` 與 `config_mode_mismatch`。account_config 取得一頁後，後續 HTTP 依 gate 規則停止；driver 共 2 次嘗試、實際 wire request 1 次，未進入其餘帳務採集。
- 未修改原始憑證檔、未搜尋其他憑證來源、未重跑正式入口、未修改交易 DB、未下單／撤單、未啟動 J／Live、未 commit／push。

其後使用者明確澄清提供的是 Demo 主帳戶 API，要求直接使用。因此 I-b-4 身分 gate 改為要求 uid=mainUid；其餘 Demo、模式、唯讀權限與有界採集條件維持不變。修改後 `test_demo_collection.py` 9／9、`test_okx_collection.py` 13／13 與相關 `py_compile` 均通過，`git diff --check` 無 whitespace error（僅 LF→CRLF 提示）。接著執行一次新的有界唯讀採集：主帳戶身份 gate 已通過，但仍有 `config_mode_mismatch`，因此 config_gate_passed=false；account_config 取得一頁後停止，driver 2 次、wire 1 次，其餘帳務端點未執行。未重跑、未修改帳戶設定、未下單／撤單。
