# W7：正式 stop 原命令重送最小 assessment

2026-10-01（台灣時間）。使用者本輪指示：「先提出正式 stop 原命令重送的最小 assessment，不執行案例」。本片僅靜態評估與文件交付；下述操作是待核准提案，不代表新案例已獲授權。

後續使用者指示「依 W7 assessment 審閱，維持不執行案例」。靜態審閱已完成並修正採證位置與證據界線；可作後續核准依據，未執行案例，亦非指定 5.6 Sol (Web) 的獨立驗收。

## 缺口與現行契約

具體失敗情境：正式 stop 已接受並完成收尾後，使用者因原回覆不確定而重送同一命令；應讀回原 run 的當前終態，不增加停止命令綁定、不改寫停止時間或終態、不再啟動 Worker／建立 run。

上述為重送需求的來源。本片首發回覆須成功保存，僅驗證其後再次收到同 stop 命令的正式終態行為；不注入回覆遺失、不驗證 UI 如何從不確定回覆恢復。

W6 A 正式服務只有兩次 start、零 stop；B stub 只有一次 stop，沒有 stop 重送。[W6 獨驗](local-sim-bot-control-w6-acceptance-20261001.md)已 PASS，但未涵蓋此缺口。W2 的 controller 停止／終態重送及真實事件邊界測試、W3 的 UI 控制測試為歷史證據，本輪未重跑，也未核對其完整歷史輸入與來源 digest，不宣稱可代替正式服務驗證。

本輪靜態核對：

- [W1](local-sim-bot-control-w1-spec-20260930.md:77)：stop 僅 `{request_id}`，首次及重送回同 run 當前狀態；202 表示接受，停止完成目前事件後收尾，保留部位，不釋放原合約 ownership。
- `catos/local_sim_control.py:284–306`：先查 request_id 綁定；同 stop／run 直接回 snapshot，不再次 `_save`、新增 stop_commands 或設定停止旗標。不同操作／run 的綁定衝突仍拒絕。
- `catos/local_sim_control.py:176–187,217–229,316–326`：命令綁定與 events 均存於控制根 `control.json`；API snapshot／清單移除 `stop_commands`，不能只用 GET 驗證該綁定。controller 沒有獨立 events JSONL 輸出。
- `catos/local_sim_control_api.py:42–64,85–88`：正式 stop 202；本文與 loaded build／instance 驗證仍適用，不能以新 instance 重送舊命令。
- `frontend/workspace/simulation.js:41–61`：POST 前保存 path／body／build／instance；成功確認後清除 pending。故本片終態重送採保存原命令的 API，不回填 storage 或宣稱 UI 重送。
- `catos/local_sim_control_runner.py:82–155`：正式事件內不插入 stop 中斷，收尾確認後才 stopped；提前停止不一定產生 `final_account`，不能要求完整自然 completed 的期末摘要。
- `tests/test_local_sim_control.py:69–96`：已有同 stop ID 終態重送與跨操作／run 衝突測試。

行號為本輪靜態定位。未發現必須先改正式程式的缺口；建議只補正式服務證據，不新增機制或金融政策。

## 建議最小案例：一個 run、一次 start、兩次同命令 stop

待使用者核准案例與執行者後，沿用固定 `sma-synthetic-smoke-v1`、2 根預熱＋8 根正式、每根間隔 1 秒；不延長 profile、不注入故障、不改 runner／UI／服務設定。

| 步驟 | 操作與必要證據 |
|---|---|
| 唯讀前置 | 核對 8770 正式／8771 preview owner、workspace／research／simulation loaded=current、restart_required=false、instance、simulation slot=idle、active=null、start=true／stop=false、容量及無在途研究。保存完整研究清單、simulation 舊紀錄、R4 摘要／來源及 frozen runtime SHA。先確認原命令採證與活動 GET 觀測已準備好，能保存實際 POST 的原本文與 headers；確認正式控制根的 metadata 可唯讀取得，不能只靠點擊推定接受。 |
| 正式啟動 | UI 明示 start 一次，取得唯一新 run；保存原 start 與回覆。GET 確認同 run 已 running、warmup_bars=2、有效 worker_pid 且至少完成 1 根正式 bar；這與正式 runner 的 Worker 建立路徑相符，不只在 starting 就 stop。 |
| 首次停止 | 在同 run 仍 running、bars<8 時，UI 明示 stop 一次。保存 POST path、原始本文、request_id、Content-Type、X-CatOS-Build／Instance、送出時點與 202 回覆；確認回同 run、stop_requested=true、stop_requested_at 非空。回覆可能已 stopped，不強求目視捕捉短暫 stopping。 |
| 等待收尾 | 僅 GET 觀察至 stopped、cleanup_confirmed=true、worker_closed=true、error=null、finished_at 非空；slot=idle／active=null、start=true／stop=false。不以 202 或 5 秒視覺提示當完成、不 kill／cancel。保存完整終態清單與控制根 `control.json` 原檔內容及 SHA256，確認其中本次 run 與 API snapshot 相符。 |
| 原命令重送 | 再唯讀確認 owner／loaded build／instance 未變、原 run 合格終態，才以保存的同 path、同原始本文及同 build／instance 明示 API stop 重送一次。202 回同 run／stopped；與重送前完整終態紀錄、清單、metadata 及 events 比較。 |
| 唯讀收尾 | 核對正式 start=1、stop=2，兩次 stop 完全同命令；清單相對前置僅增加一個 run，所有舊 run／研究清單／R4 摘要與來源未變，owner／instance／build 未漂移。停止後 UI 顯示已停止且單槽可啟動，不再點 start。 |

PASS 必須包含首次 stop 確實在活動中接受、實際 Worker 收尾及終態原命令重送三項證據。命令總額度：start 最多 1 次、stop 最多 2 次、唯一新增 run。僅補同 instance 的終態 stop 冪等；不驗證 stopping 中重送、正式回覆遺失、UI pending stop 還原、多 tab、跨 instance 或重啟恢復。

若窗口耗盡、首次 stop 回 completed，或始終未觀測到 running／正式 bar，記錄未涵蓋，不補開第二個 run。不為滿足 bars<8 而截斷已開始事件；有效 stop 仍可能完成當前事件甚至第 8 根。本片不要求固定停止根數／成交筆數，不將完整自然完成的 4 fills、fees=`0.00404010`、equity=`999.91375990` 當提前停止的預期值。金融數值保留原 Decimal 字串，只比較終態重送前後不變；不開 DB、重算完整帳務或宣稱 stop 清倉／ownership 釋放。

重送前後要求同 run 的完整 API snapshot、events、bars、fills、stop_requested_at、finished_at 不變，完整 simulation 清單不變。必須從同 owner 正式控制根的 `control.json` 核對 `runs[run_id].stop_commands` 嚴格等於 `[首次 stop request_id]`；保存重送前後原檔內容及 SHA256，要求整份 metadata 不變，不只比較新增 run。正式預設位置為 `outputs/local-sim-control/control.json`（`catos/workspace_api.py:155–161`）；執行時須確認實際控制根與既有 launcher／資料根一致，不猜路徑或讀其他目錄。API 欄位與 metadata 比對時，只排除 API 新增的 `still_finishing` 與刻意隱藏的 `stop_commands`，其餘原始欄位須一致。無法取得 metadata，不能宣稱命令綁定已驗證，也不送後續重送。

GET 的 version 前後保留正常能力變化，只在前置／收尾／重送階段要求 idle、active=null、start=true／stop=false；重送前後 loaded=current、restart_required=false、unavailable=null、owner／instance 仍合格。以命令觀測及服務日誌的本輪區間共同核對總 POST 數；不把含舊命令的累計日誌當本輪計數。controller events 就在 metadata／API snapshot 中，不要求不存在的 JSONL，也不新增輸出機制或逐列 DB 驗收。

## 前置失敗與成本

缺失服務可依 AGENTS.md 固定授權使用既有 launcher／資料根恢復，先確認埠空缺，不停止不明 owner；恢復後建立新 owner／instance 基線，不沿用 W6 PID／instance。這只免除同範圍服務恢復的重複詢問，不授權本片新案例。服務占用者不明、版本漂移、非 idle、容量不足、unavailable／recovery_required 或研究活動中，保存原因並停止案例，不解除、不 resume、不重啟既有 owner。

首次命令回覆不確定、原 stop 本文／headers 未完整保存、收尾不合格或 instance 變更時，保留 pending／證據並回報，停止後續重送；不猜 ID、不增加命令、不自動換案例。停留 stopping／收尾不確定不等於允許強制終止，交付觀察狀態與缺口。

驗證成本為一個約十秒內可提出 stop 的固定真實短程、三次 mutation 上限、前後唯讀採證與離線比較；收尾本身無限時完成保證。無正式程式修改時，不重跑 W2／W3 全套或增加鏡像單元測試。可沿用 W6 採證思路，若需支援腳本，只在新具名 `outputs/workspace-w7-<識別>/` 準備限定 stop 原命令保存／比較，保留舊輸出；此支援未於本輪實作或執行。

## 分工、交付與下一步

assessment 建立輪僅新增提案並同步 [接續入口](current-handoff.md)；後續審閱輪僅修正這兩份文件。均未操作服務／瀏覽器、未 POST、未新增 run／Worker／DB、未執行測試、未核對 Git。W6 已 PASS／本機保存為入口及既有文件的歷史狀態，未重驗。

下一步建議核准上述單一正式案例及執行者，證據完成後由指定 5.6 Sol (Web) 唯讀獨立驗收，不能由 6.1 Sol／6 Sol 取代；獨驗不另開 run。Git 保存另行授權。本片不涉及憑證、採集／Demo／Live、schema／latch／recovery、R4 重跑、清理、push 或 Yaozi／其他工作目錄。

可留在目前對話確認 assessment 範圍；切換執行／獨驗角色時建議新對話。短接續指令：「先讀 current-handoff 與 W7 assessment；靜態審閱完成，新案例未授權。核准後依限定一個 run／一次 start／兩次同 stop 命令執行，從 control.json 核對綁定，不補跑、不解除 recovery，保留分工與既有未提交內容。」

## 靜態審閱紀錄

2026-10-01 後續審閱核對 controller 的持久化／snapshot／綁定／事件、runner Worker 建立與 close、窄 API 的 build／instance 檢查及既有採證方法；未呼叫服務或執行程式測試。發現並修正文檔兩項缺口：

1. 原「新 run metadata／可取得的 events JSONL」改為正式控制根的 `control.json`，明定重送前後原檔內容／SHA256 與唯一 stop ID；取代原採證位置說法。API 隱藏綁定，events 無獨立 JSONL，均為現行程式行為。
2. 明定首發回覆須確認成功，活動證據包含 2 warmup／worker_pid／正式 bar，idle 能力與重送基線須合格；僅證明活動中停止、runner 回報資源收尾及終態同命令冪等，不推論回覆遺失、PID 追蹤、COMMIT／ACK 的逐列獨驗或安全沙箱保證。

修正後未發現靜態阻斷問題，仍須案例核准、實際採證及指定角色獨立驗收才能形成正式案例 PASS。本輪僅修正本文件與入口，文件內容／連結／格式核對結果於交付回覆記錄；未變更正式程式、未執行案例／服務操作／測試／Git。

## 範圍確認紀錄

2026-10-01 使用者指示「依修正版 W7 確認範圍，維持不執行案例」。核對上述提案，範圍確認完成，未新增操作或放寬條件；本次確認不構成案例執行授權。

- 額度：唯一新增 run；一次 UI start、一次活動中 UI stop、合格終態後一次 API 原 stop 重送。沿用固定 profile，不補跑。
- 首次 stop 前須觀測 running、2 warmup、有效 worker_pid、至少 1 根正式 bar 且 bars<8；首次回覆須完整保存並確認接受。
- 重送前須 stopped、cleanup_confirmed／worker_closed=true、error=null、單槽 idle，owner／build／instance 合格且未漂移。同 path／原本文／headers 重送；同 run 終態、完整清單、events 及整份 `control.json` 內容／SHA256 不變，stop 綁定僅原 ID 一筆。
- 缺採證、窗口耗盡、不合格基線或收尾未確認即停止後續命令；不增加 run、不解除 recovery、不強制終止。回覆遺失／UI pending 恢復及其他擴充案例不在本片。
- 本輪僅文件確認與入口同步，未呼叫服務、準備採證腳本、執行案例／測試或 Git。未來實際採證後，獨立驗收維持指定 5.6 Sol (Web)，Git 另行授權。

## 後續執行授權與結果

2026-10-01 使用者後續「同意 請繼續」，授權依上述已確認 W7 範圍執行。先前「維持不執行案例」為 assessment／審閱／範圍確認階段紀錄，保留其歷史事實；最新授權取代當前不執行狀態，不擴大案例或政策。

本輪已完成唯一 run `4874ffc8cb444bbc898032005a1a848e`：UI start 一次、活動中 UI stop 一次、合格 stopped 後 API 原 stop 重送一次。完整終態／清單及整份 control.json bytes／SHA256 不變，stop_commands 僅原 ID 一筆；本輪離線證據核對 38/38 通過。詳細原始證據、採證修正與限制見 [W7 執行交接](local-sim-bot-control-w7-handoff-20261001.md)。指定 5.6 Sol（Web）獨立驗收待進行，未取得 Git 授權；不再執行案例或重送腳本。
