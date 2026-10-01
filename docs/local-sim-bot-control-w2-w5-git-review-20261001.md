# W2～W5 Git 分片核對

2026-10-01。最初使用者授權「5.6 Web 暫時用不了，你直接執行」本次 Git 分片核對；該輪未授權暫存／提交／push。後續明確例外授權 6.1 Sol 依三片計畫暫存並本機提交 W2～W5（含 W1 規格）；仍不授權 push、不重跑案例，排除 AGENTS、.codex、F1 補記與所有 outputs，保留原始證據與服務。不變更後續一般角色分工。

## 基線與結論

核對起點：分支 `main`，HEAD=`46bdba2469e49c4f05328e858263eed8197bfe3a`（正式 localhost 入口），前序 R4=`33a4518`、F1=`7957447`。正式入口已提交，不能再次算成待提交切片。當時暫存區空、W2～W5 尚未提交；後續依下列順序提交，實際紀錄見末節。README 過期敘述已依後續授權修正。

## 建議分片

後續文件修正（2026-10-01）：依使用者「修正 README 現況，不提交／push」授權，已同步 README 的 W4 正式載入與 W5 限定驗收敘述。下列 README 待辦為核對當時紀錄，現已完成；本次只修文件，未重跑案例或操作 index／提交／push。

| 順序 | 候選內容 | 邊界與相依 |
| --- | --- | --- |
| 1：W1／W2 | W1 spec、W2 handoff；新增 `catos/local_sim_control.py`、`local_sim_control_runner.py`、`local_sim_control_api.py`、`tests/test_local_sim_control.py`；修改 `tests/test_workspace_f1.py` 的 tempfile simulation_root；`catos/workspace_api.py` 的 create_app 簽章與正式 mount_simulation 區塊 | 依 HEAD 正式入口；workspace_api 資產 allowlist 的 simulation.js 不在此片。W1 未追蹤且為 W2 規格依據，應一併保留；W1 末段已有 W3 驗收補記，不是純歷史 W1 快照。 |
| 2：W3 | 新增 `frontend/workspace/simulation.js`、`tests/test_simulation_ui.cjs`、`tests/simulation_ui_fixture.py`、W3 handoff；修改 desk.html／desk.css／desk.js；workspace_api 僅 simulation.js allowlist hunk | 依 W2。前端其餘 diff 均為模擬區、R4 標籤及設定說明；無正式入口殘留 diff。 |
| 3：W4／W5 與收尾文件 | W4 handoff、W5 assessment／handoff／acceptance、本核對文件、current-handoff；README 已更新至 W4／W5 現況 | W4／W5 沒有獨立應用程式 diff。最終入口含全部切片，放最後避免先引用尚未提交文件；outputs 僅保留本地，不能因文件引用而納入。 |

共享 `catos/workspace_api.py` 已於提交輪按上述兩個 hunk 分配，工作檔未改。不宣稱各中間 commit 已實際建置或測試。W1／W2 文件引用 W3，以及 W3 文件引用最終入口，有跨片文件連結；完整三片落地後連結才齊全，不將每片宣稱為獨立完整文件集。

## 排除清單與待辦

- `AGENTS.md`、`.codex/`：使用者規則與模型設定工作，不屬 W2～W5。
- `docs/catos-workspace-f1-handoff-20260930.md`：既有 F1 6/6 驗收補記，獨立文件收尾，不混入模擬功能。
- 所有 outputs：設計樣稿、F1／W3 畫面、W4／W5 原始證據、local-sim-control metadata／DB／案例，全數保留本地、不預設提交。不清理或改 ignore 規則。
- README 第 5 行已修正正式服務載入與 W4／W5 驗收現況；既有 W3 歷史驗收證據保持，不新增本輪測試宣稱。
- 不修改 CatOS_Yaozi、Gemini 原目錄、R4 manifest／runtime／DB、研究輸出、憑證或交易設定。

## 核對輪驗證與限制（歷史紀錄）

已核對 status、tracked diff、HEAD 提交內容、import 相依及未追蹤檔案清單。tracked 候選檔案 `git diff --check` 通過；七個未追蹤程式／測試檔以 `git diff --no-index --check` 通過空白檢查。W5 保存的 25 個來源 SHA 與現行檔案一致；此只支持該範圍未變，不涵蓋所有 UI／測試檔案，也不把 W2 50/50、W3 33/33 歷史驗收冒充本輪重驗。

未重跑案例、單元測試、服務或 R4 verifier，未開 DB、連線交易或讀憑證。未讀 `.codex` 內容；未 stage、commit、push、切分支或清理。原核對輪只新增本核對文件並更新入口；後續文件輪已修 README。若授權提交，確認工作樹未漂移並精確分配共享 hunk；本文件本身不授權該操作。

## 提交前收尾與授權範圍

2026-10-01 依使用者最新指令完成唯讀核對：HEAD 仍為 `46bdba2`、分支 main、暫存區空；候選檔案清單與已記錄分片一致，workspace_api 仍為 allowlist 與 create_app／mount_simulation 兩個 hunk。此輪未重驗應用行為或服務狀態，原始證據與服務未操作。

其後使用者已直接明示：「本次例外授權 6.1 Sol 依三片計畫暫存並本機提交 W2～W5（含 W1 規格）；不 push、不重跑案例，排除 AGENTS、.codex、F1 補記與所有 outputs，保留原始證據與服務。」這已同時授權角色例外與本機 Git 操作，取代本文件先前「尚未獲授權」說法；無須另開對話，push 仍未授權。

## 本機提交紀錄

- 第一片：`580516003441054227f66ee5af15e03c1fffeea2`，`feat(local-sim): add W1 W2 bot control backend`，8 個檔案；workspace_api 僅 create_app／mount_simulation hunk。
- 第二片：`52c981f4012fff43f2e296fdd075a8d6cea67aa6`，`feat(workspace): add W3 local simulation controls`，8 個檔案；workspace_api 僅 simulation.js allowlist hunk。
- 第三片：`docs(local-sim): record W4 W5 acceptance and closeout`，包含本文件與入口，連同 README、W4 handoff、W5 assessment／handoff／acceptance，共 7 個檔案；提交號由最終 git log 核對，避免在文件中自引自身 commit SHA。

每片暫存時核對精確檔案集合與 `git diff --cached --check`。應用程式工作檔沒有修改；W2／W3／W4／W5 驗收均沿用歷史證據，本輪不重跑測試／案例，不操作服務、DB 或交易，不 push。

提交輪第一個手寫後端 hunk 套用失敗，Git 未套入該 hunk；改以 Git 原始 diff 的後端 hunk 成功暫存，核對 UI hunk 仍未暫存，無工作檔變更。第一片提交 exit 0，另有 Git 自動維護警訊 `unable to update .git/info/refs: No such file or directory`；提交物件與 main 指標已核對。後兩片以單次 `maintenance.auto=false`／`gc.auto=0` 停用自動維護，不改專案設定或清理檔案；此警訊不宣稱已修復。
