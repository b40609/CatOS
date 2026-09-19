# S8：固定合成範例入口正式規格

狀態：2026-09-19，依使用者指示制定並通過文件驗收；尚未實作或執行。範圍依 [S8 評估](catos-s8-scenario-example-assessment.md)，評估已由使用者驗收並提交 `8c0000a`（`docs(lots): assess S8 fixed scenario example`）。S7 基線為 `e00c2b5`；文件驗收不代表 S8 程式已通過。

## 1. 目的與限制

提供一個固定本機範例，使用全新 Journal 建立合成部分成交，取得 S5 capture，再呼叫 S7 產生完整／降級 HTML。使用者不必引用測試 fixture 或自行建立 capture hash。

程式範圍限 `examples/lot_scenario_demo.py`、`tests/test_lot_scenario_demo.py`、開發交接及 README／WORK_PLAN。沿用標準函式庫與現有公開 API，不修改 Journal、S3／S5／S6／S7、Schema7、Risk、P6、execution／protection、交易或研究回測路徑。不修改既有 report_demo、research_cli、catos.cli 或 .gitignore。

僅 local-sim、固定單帳戶／合約／Bot／Lot，不接行情、憑證、Worker、Supervisor 或交易派送；不提供輸入 DB、JSON／CSV 匯入、策略選擇、情境編輯、force、服務或自動開啟瀏覽器。保留 Decimal 與既有帳務語義，不新增交易政策。

## 2. 入口與參數

```text
<python> -B -m examples.lot_scenario_demo --output-dir reports/lot-scenario-run-001
```

此命令為待實作契約。使用者先確保父目錄存在，目標目錄必須尚不存在。

模組提供 `main(argv: list[str] | None = None) -> int`；直接執行以 `raise SystemExit(main())` 結束。import 不建立目錄、Journal 或輸出。內部 helper 可按需拆分，不新增可接外部任意情境的公開 API。

| 項目 | 契約 |
|---|---|
| `--output-dir PATH` | 必填，一個路徑字串；空字串拒絕，不展開 ~ 或環境變數 |
| `-h`／`--help` | 顯示固定合成資料、保留 DB、禁止覆寫及失敗可能留產物的說明；退出 0，無檔案／DB 副作用 |
| 缺少參數／未知參數 | argparse usage error，退出 2；不建立輸出目錄或 Journal |
| 參數縮寫 | `allow_abbrev=False`，不接受 `--output` 代替完整選項 |
| 相對路徑 | 相對於呼叫端工作目錄；成功訊息列絕對路徑 |

只解析命令列及既有 Python 啟動環境；程式不得主動讀取任何憑證或環境變數，也不將目前時鐘作為情境資料。help 的格式沿用 argparse，不固定其換行或 Python 版本差異。

## 3. 正式固定資料

所有金融值由十進位字串建立 Decimal；整數時間、序號使用 int。下列值是範例常數，不接受命令列覆寫，不代表交易建議。

| 資料 | 固定值 |
|---|---|
| account_id／scope.account_ref | `s8-example-account` |
| scope.environment | `local-sim` |
| bot_id | `s8-example-bot` |
| fixture_budget | Decimal("1000") |
| Journal 設定 | risk_limits=None、execution_enabled=False |
| inst_id | `SYNTHETIC-USDT-SWAP` |
| base_per_contract | Decimal("0.01")，標的資產／張 |
| tick_size | Decimal("0.5")，USDT／標的資產 |
| lot_size／min_size | Decimal("0.5")／Decimal("1")，張 |
| source_id／order_id／trade_id | `s8-synthetic`／`s8-open-1`／`s8-trade-1` |
| IntentContext | 上述 scope／bot／contract，event_seq=1、warmup=False |
| OpenLot | side="long"、quantity=Decimal("3") |
| LotProtection | trigger_price_type="mark"、take_profit=None、stop_loss=None；不接 P6 |
| SyntheticFill | fill_seq=1、quantity=Decimal("1")、price=Decimal("100")、fee_paid=Decimal("0.01")、fee_currency="USDT" |
| capture 取樣／截止 | observed_at_ms=1000、valid_until_ms=2000 |
| 評估時間 | now_ms=1500 |

時間單位為 Unix epoch 毫秒，刻意使用固定合成時間；不代表執行當天的市場。`fee_paid` 原值交由 S3 處理，不改號或推導費率。只綁定一個 OPEN、寫入一筆 fill，不 finish_order、不取消、不 CLOSE、不建立 unmanaged Lot；未成交 2 張維持未終結責任。

Journal 的呼叫順序：

1. 使用新目錄內 `scenario.sqlite3` 建立 Journal。
2. `journal.lots.register_binding(scope=..., bot_id=..., contract=...)`。
3. `journal.lot_fills.bind_order(source_id=..., order_id=..., context=IntentContext(...), intent=OpenLot(...))`。
4. `journal.lot_fills.apply_fill(SyntheticFill(...))`。
5. `journal.capture_lot_snapshot(scope=..., inst_id=..., observed_at_ms=1000, valid_until_ms=2000)`，恰取一次 capture。

禁止引用 `tests`、fixture helper、私有 hash／reducer 或直接 SQL 寫入；Lot／intent／order key 與水位皆由現有流程產生，不硬編碼雜湊值或 commit_seq。新 DB 依既有初始化建立 schema，不讀取或升級任何既有 DB。

## 4. 兩份情境證據

兩份 `SyntheticScenarioEvidence` 使用同一 capture 物件、完整相同 scope／contract，source="synthetic_scenario"、source_capture_id=capture.capture_id。共同 physical 取樣 1100、截止 2100，quantity=Decimal("1") 為明示常數，禁止從 Lot 加總推導。

| 欄位 | complete | degraded |
|---|---|---|
| scenario_cut_id | `s8-complete-cut` | `s8-degraded-cut` |
| physical_complete | True | False |
| mark_quote_id | `s8-mark-1` | None |
| mark_observed_at_ms | 1200 | None |
| mark_valid_until_ms | 2200 | None |
| mark | Decimal("100.123456789012345678901234") | None |

依 complete→degraded 順序各呼叫一次 `render_synthetic_scenario_report(capture=..., scenario=..., now_ms=1500)`。S8 不另呼叫 S6／S4、不自行計算報告值、不修改返回 HTML；S7 內部各呼叫一次 S6。兩份字串都產生成功且 Journal 關閉成功後才開始寫 HTML。

### 必要語義驗收值

| 結果 | complete | degraded |
|---|---|---|
| comparison_status／delta_qty | MATCH／0 | UNAVAILABLE／None |
| long／short／Gross／Net／physical 數量 | 1／0／1／1／1 張 | 相同，保留原值 |
| pending buy／sell | 2／0 張 | None／None |
| synthetic buy／sell | 2／0 張 | None／None |
| held buy／sell、exchange buy／sell | 全部 0 | 全部 None |
| physical／virtual Gross 上界 | 3／3 張 | None／None |
| 三種 notional | 均為 1.00123456789012345678901234 USDT | 全部 None |
| lot_complete／pending_complete | True／True | True／True |
| lot／physical／pending fresh | 全部 True | 全部 True |
| physical_verified／mark_fresh | True／True | False／False |
| has_unknown | False | False |
| unresolved_lot_count／pending_unique_count／pending_duplicate_count | 1／1／0 | 1／1／0 |
| reasons | 空 tuple | `mark_missing`、`physical_unverified`，依既有排序 |

degraded 的 pending_complete 仍為 True；分項與上界不可用是因 physical 完整性聲明不成立，不可誤稱缺少 pending。mark None 與所有 metadata 同時缺席；預期 None 交由 S7 呈現為「不可用」或「未提供」，不自行改零。mark 不必對齊 tick，沿用現有 S6 語義。

## 5. 目錄與資源生命週期

1. 在 Journal 建立之前，對使用者指定路徑執行 `mkdir(parents=False, exist_ok=False)`。不得以 exists 預檢取代建立時拒絕，也不得先 resolve 最後一層連結再對連結目標建立目錄。
2. 父目錄必須存在；不得自動補建父目錄。目標已存在時，即使為空目錄、一般檔案、有效或懸空連結，均拒絕。拒絕時不開 Journal、不讀目標內資料、不更動 sentinel。
3. 只有目錄建立成功後，才取得其絕對位置供固定子路徑與訊息使用。父目錄既有連結可沿檔案系統正常解析；本片不提供防止惡意競態的沙箱保證。
4. Journal 正常建構返回後，須在 finally 或等效結構呼叫 close；資料建立、capture 或 renderer 任一步失敗也必須嘗試關閉。建構失敗沒有可用 Journal 物件，沿用既有建構器對已建立 connection 的清理，不自行重開 DB。
5. close 失敗即失敗，不寫 HTML、不回成功，也不重試 DB。若業務錯誤與 close 錯誤同時發生，保留兩者 exception chain 或 exception group，不能靜默抹掉原錯誤；CLI 可只輸出有限的失敗類別資訊。
6. close 成功後依 complete.html→degraded.html 順序寫入；每份使用 `open("x", encoding="utf-8", newline="\n")` 或等效 exclusive create，內容為 renderer 原字串，無 BOM、不額外加尾端換行。禁止 append、可覆寫 write、replace／rename。
7. 各檔 write 及 context exit／close 都成功才算該檔完成；兩檔均完成後才輸出成功清單。保持 DB 與任何 SQLite 自行管理的副檔；程式不直接刪除、移動或清理任何產物。

新目錄預期內容為 scenario.sqlite3、complete.html、degraded.html，WAL／SHM 是否保留依 SQLite 關閉行為，不要求固定數量。不得為此強制 checkpoint 或更動 Journal 的 PRAGMA。

不提供跨檔原子提交、斷電完整性或自動續跑。生成錯誤留下 DB／目錄；第一份保存成功而第二份失敗時，已產生與可能未寫完整的檔案皆保留。後續重跑須指定另一個新目錄，不提供覆寫、修補或清空既有 run 的選項。

## 6. 成功、失敗與結束碼

成功後 stdout 依序三行，鍵名固定，路徑為本次絕對路徑：

```text
database=<absolute path>/scenario.sqlite3
complete=<absolute path>/complete.html
degraded=<absolute path>/degraded.html
```

Windows 使用原生路徑表示即可，不要求正斜線；路徑可含空白，不自行 shell-escape。成功 stderr 為空，main 返回 0。不列印 capture／fill 物件、HTML 全文或任何憑證資料。

| 類別 | 結束碼及行為 |
|---|---|
| help | argparse SystemExit(0)，stdout help，無資料副作用 |
| usage 錯誤 | argparse SystemExit(2)，stderr usage／error，無資料副作用 |
| 目錄、Journal、資料、render、close、保存的一般例外 | main 返回 1，stderr 顯示失敗階段與 exception 類別；stdout 無成功清單 |
| KeyboardInterrupt／SystemExit | 不以一般 except Exception 吞掉，沿 Python 行為離開；已取得 Journal 仍走 finally |

階段名稱固定為 `output_dir`、`journal_init`、`scenario`、`journal_close`、`write_complete`、`write_degraded`。一般例外訊息格式：`S8 example failed: stage=<stage>; error=<ExceptionClass>`；若新目錄已建立，另列 `artifacts=<absolute directory>; retained; retry with a new output directory`，未建立則不得聲稱擁有或保留既有目錄產物。

錯誤階段以當時失敗動作為準；close 與先前錯誤同時發生時列 journal_close 並保留例外關聯。業務 helper 原樣拋出 S3／S5／S6／S7 錯誤，不新增錯誤碼對照層；CLI 最外層可 catch Exception 以返回 1，但不能改成正常空報告。預設不需要完整 traceback 或公開輸入內容。

成功清單的 console I/O 失敗須造成非零退出，不宣稱可回收已送出的 stdout；此前生成的三份產物仍保留。這個 console 例外不要求重試或追加新的檔案狀態格式。

## 7. 可重現性與驗證成本

同版本、同一執行環境，於兩個不同新目錄執行，complete.html 彼此及 degraded.html 彼此須逐 byte 相同；capture_id 也相同。stdout 路徑、SQLite 二進位及 WAL／SHM 不在 byte 一致性要求內。path、系統時間、隨機值或產生時戳不進報告資料；不建立 manifest、checksum 檔或第二種匯出格式。

只使用單筆固定成交，無全市場回測、額外並行或效能測試。新增測試在各自受控臨時目錄驗證檔案操作；測試 fixture 的清理責任與正式範例「保留產物」分開，不把 test cleanup 加入範例。

## 8. 驗收矩陣

下列為情境群，非預先宣稱的方法數；Sol 記錄實際 run／failure／error／skip。

| ID | 必要驗收證據 |
|---|---|
| A01 | 真實全新 Journal→binding→OPEN→單筆 fill→S5 capture→兩份 S7 HTML，資料與固定常數一致；無 terminal |
| A02 | complete 的第 4 節全部結果與來源標示，用 HTML 解析及既有回傳契約核對，不由範例重算 |
| A03 | degraded 所有空值／旗標／精確兩項原因；pending_complete=True 與不可用數量能同時成立 |
| A04 | 同一 capture 物件供兩次 renderer、一次 capture、兩次 renderer，參數與順序正確；沒有 S8 額外 S4／S6 呼叫 |
| B01 | 不同新目錄執行，兩份 HTML 分別 bytes 相同；明示 UTF-8、無 BOM、長 Decimal 完整 |
| B02 | 現有空目錄、非空目錄、檔案拒絕；sentinel 不變且 Journal 未建立 |
| B03 | 可建立的有效／懸空 symlink 或 Windows 連結拒絕，不修改連結及目標；權限不允許時如實記錄未驗項目，不偽稱通過 |
| B04 | 父目錄不存在、父層非目錄、目錄權限失敗；不建立父層或 Journal，非零且無成功清單 |
| B05 | 在新 run 中預先注入 complete／degraded 檔案衝突，exclusive create 拒絕且 sentinel 不變；不只依目錄預檢保護 |
| C01 | Journal 建構失敗、S3／capture／任一 renderer 失敗，非零且無 HTML 保存；已返回的 Journal 關閉，既有產物保留 |
| C02 | Journal close 失敗，不開始 HTML；與先前錯誤同時發生時保留兩者 exception 關聯 |
| C03 | complete／degraded open、write 或 close 失敗，各自非零、不回成功、不刪除產物；第二檔失敗仍保留第一檔 |
| C04 | 實際成功返回後可另以唯讀連線檢視新 DB 的 S3 部分成交／未 terminal；不以刪除 DB 作唯一關閉證據 |
| D01 | help、缺參數、未知參數、空路徑及縮寫拒絕契約；無目錄／Journal 副作用 |
| D02 | 從專案根目錄以 Python -m 啟動，使用有空白的新輸出路徑，三行成功清單與實際檔案一致 |
| D03 | import 無寫入；無 tests／私有 hash 依賴，不連網、不讀憑證；生產程式未加環境讀取、force 或 DB 參數 |
| D04 | 一般錯誤階段／stderr／返回值契約，KeyboardInterrupt 仍關閉 Journal 並傳遞；console 失敗不轉成功 |
| E01 | 新入口產生的完整／降級 HTML 實際開啟可讀；S7 未修改時不重跑四組 F01 矩陣 |
| E02 | 專屬測試、S7 必要回歸、編譯、diff／staged 範圍；無無關檔案或生成產物混入 |

正常資料鏈與檔案成功／防覆寫案例用真實臨時 SQLite 及檔案。難以穩定重現的權限、write／close、console 及雙重例外可用明示 stub／fault injection；不可用 stub 取代 A01 或可重現性實測。B03 如需 skip 必須列出原因，由使用者判定驗收限制。

## 9. 分工與完成條件

後續由 Astra 編寫程式、專屬測試及 `docs/lot-scenario-demo-handoff.md`，Sol 執行以下預定命令：

```text
<python> -B -m unittest discover -s tests -p "test_lot_scenario_demo.py" -v
<python> -B -m unittest discover -s tests -p "test_lot_scenario_report.py" -v
```

實際啟動新入口並開啟兩份報告，記錄 Python／SQLite 版本與檔案範圍；發現相關失敗或改動既有模組時才擴充對應測試。不執行全量測試或歷史回測，不以規格／測試編寫數宣稱驗收通過。

本輪僅交付正式文件，未執行 Python、DB、報告生成、測試、編譯或 Git。S8 開發完成後交由使用者驗收與提交；market、yaoI／yaozi、S5／S6／S7 未提交紀錄保持獨立，不能一起納入 S8。README／WORK_PLAN 若同時含既有補記，Git 分組由驗收端另行核對。
