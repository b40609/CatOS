# CatOS 整合基線收斂交付

日期：2026-10-24。使用者核准「整合基線收斂」，並要求主資料夾統一為 CatOS。本文件記錄該輪開發／限定自測；後續指定 GPT-6 Sol 獨驗與修復重驗已完成，限定範圍 PASS，見[獨立驗收報告](integration-baseline-acceptance-20261024.md)。下列開發日誌與歷史結果保留，不回寫為獨驗或修復後重跑。

同日後續決策：使用者已取消資料夾更名，保留 `C:/Users/user/Desktop/CatOS_Astra`，產品名稱仍為 CatOS。此決策取代下文的待改名步驟；不再執行改名腳本。現行文件與 compat cwd 已同步，歷史測試／備份／verification 雜湊保留原樣，不冒稱本次重驗。

## 基線與範圍

- HEAD `149f9fcbf2a2c5d741aa696750ab1ed62ae14460`，分支 `feature/catos-react-vite`；修改留在工作樹，未 commit／push。
- 原目錄 `C:/Users/user/Desktop/CatOS_Astra`，目標 `C:/Users/user/Desktop/CatOS`；CatOS_Yaozi 不變。實體改名狀態見下節。
- 舊入口完整內容保留於[歷史快照](archive/current-handoff-before-integration-20261024.md)；現況改用[一頁入口](current-handoff.md)。歷史路徑、雜湊與驗收結論不回寫。
- 不是全面刪檔、全案重驗或新功能開發；保留原型、舊 preview、既有 stash 與未追蹤內容。不讀憑證／產品 DB，不改 schema、交易或金融政策。

## 具體變更

| 範圍 | 行為與目的 |
| --- | --- |
| 展示權威 | 全域模式標示展示；Bot 暫停／重啟、委託移除文字明示僅作用展示。P6 以示例 ACTIVE／UPDATING／異常呈現，去除固定 100% 錨定 |
| 優化任務 | production hook 管理版本、清單、共用 active slot、刷新／回頁輪詢；其他 kind 仍占槽時禁提交，終態不等於槽釋放。結果請求取消及世代檢查，舊回應不覆蓋新選取 |
| Store | hydrate 按 domain version 保護新版資料，拒絕負值／非安全整數版本；測試載入實際 catStore／stateAdapter／mockAdapter |
| Vite | 8890 strictPort；研究、workspace、intel 固定 loopback 上游。前置 Host／Origin 防護，保留後端 build／instance 檢查 |
| 啟動 | 新增前端身分端點；launcher 比對 root＋contract，等 HTML ready；未知 8890 owner 拒絕接管，失敗只收尾本輪啟動程序 |
| 依賴 | `requirements-http.txt` 明列研究＋FastAPI／Uvicorn／HTTPX；乾淨 venv 安裝與相容性驗證 |
| Preview 相依 | 共用展示 store 移至 state/dashboard-demo-store.ts；preview-store.ts 只保留相容轉匯出，不刪舊入口 |
| 名稱與路徑 | README 不再把 Astra 當產品模組名稱；現行工具由檔案位置推導專案根。使用者取消更名後，compat cwd 已恢復 CatOS_Astra。外部素材與歷史產生器路徑不盲改 |

未新增完整 Bot API；主工作區與情報仍有展示資料。研究真實 HTTP 使用登錄 SMA／96 根合成 K 線，優化概念視圖另外標示，不代表任意策略、多參數或實盤支援。

## 實際開發自測

證據根：`outputs/integration-baseline-20261024/`，相對本專案。測試只使用假資料與全新隔離根；正式服務只唯讀核對及改名所需維護。

| 命令／驗證 | 實際結果 | 證據 |
| --- | --- | --- |
| 前端 `npm.cmd test` | 4／4；production store／adapter、分域版本、無效版本、mock 模式與 Decimal 字串 | `state-tests.log` |
| `python -B -m unittest tests.test_local_sim_control tests.test_workspace_f1 tests.test_research_optimization_web` | 56／56，8.983s | `backend-tests.log` |
| 前端 `node tests/integration_baseline_test.mjs <bundled-node_modules> [python]` | 9／9；真 Vite／隔離後端 HTTP＋React 攔截 fixture 互動，無 pageerror | `integration-tests.log`、`fixture-OQSFd4/result.json` |
| `npm.cmd run typecheck` | exit 0 | `typecheck.log` |
| `npm.cmd run build -- --outDir ../../outputs/integration-baseline-20261024/build --emptyOutDir false` | exit 0，2374 modules，5.26s | `build.log`、`build/` |
| 乾淨 venv：`python -m pip --isolated install --index-url https://pypi.org/simple -r requirements-http.txt`；pip check／import | 安裝、依賴一致性與 import 通過：FastAPI 0.141.1／Uvicorn 0.52.4／HTTPX 0.28.1／Optuna 4.9.0 | `http-install.log`、`http-check.log` |
| launcher 未啟動 CheckOnly | 預期 exit 1，不把未啟動宣稱 ready | `launcher-absent.log` |
| launcher 遇其他 owner | 預期 exit 1；測試 owner 仍存活，未誤停 | `launcher-foreign-owner.log` |
| launcher 實際啟動及 CheckOnly | 身分＋HTML 就緒；後續 CheckOnly exit 0，可重用同一服務 | `launcher-start.log`、`launcher-ready.log` |
| 改名腳本 PowerShell 語法／`-CheckOnly` | 語法通過，唯讀檢查 exit 0；不代表實體改名已通過 | `rename-check.log` |
| 正式服務恢復後唯讀核對 | 來源一致、restart_required=false；8770 simulation 閒置，8771 preview=true | `services-restored.json` |

隔離 9 項涵蓋：身分／GET 代理；外站 Host／Origin 403；後端 build／instance 409；相同來源 POST 202、request_id 重放與 stop（僅 fixture）；重載恢復輪詢與共用槽釋放短窗；延遲結果隔離；其他 kind 忙碌；單次提交；展示／P6 待確認。研究瀏覽器競態使用明示攔截 fixture，不能當成真 Optuna 執行完成的瀏覽器驗收。

建置有既有 chunk >500 kB 提示；型別檢查與編譯通過。沒有擴大為全歷史回歸、全市場回測、真行情、交易或獨立驗收。

測試開發中修正了新 store 的 TypeScript 索引型別、Vite 測試關閉時掃描，以及測試端 Host 發送方法／提交按鈕定位；最後上述通過版本為本輪證據，不刪除先前失敗 fixture。

## 改名與服務

**以下為取消前的嘗試與服務快照，非目前待辦或即時服務狀態。** 更名不再構成整合交付的阻斷；改名腳本保留但不執行，歷史 PID 不可直接沿用。

狀態：**實體改名未完成**。Windows 拒絕目錄改名；在釋放已確認的服務／工具 cwd 後，仍定位到 Codex 本身 `ChatGPT.exe`（當時 PID 59192）持有舊根的 3 個目錄控制代碼。未強制結束 Codex 或關閉其內部控制代碼；來源仍為 `C:/Users/user/Desktop/CatOS_Astra`，目標尚不存在，沒有搬移或刪除專案內容。

原已確認閒置的 workspace 服務曾為改名停止，現已恢復：8770 owner PID 60532、8771 owner PID 45048；前端 8890 owner PID 54724。唯讀核對身分／來源／HTML 合格，研究與 workspace restart_required=false，8770 simulation slot=idle、無 unavailable。8771 的研究端點沿用正式研究 owner，不以回應內 pid 當作該埠程序；preview 不掛 simulation API，初次探測 404 已記錄，不當作服務失效。可於 `http://127.0.0.1:8890/` 檢視本輪修改。

當時備妥本機 `rename-project-to-catos.bat` 與 `scripts/rename-project-to-catos.ps1`；兩者為未採用材料，保留本機並排除本次提交。下列步驟已由後續取消決策取代，不再執行：

1. 關閉 Codex，以及仍使用舊目錄的 IDE／終端。
2. 執行 `C:/Users/user/Desktop/CatOS_Astra/rename-project-to-catos.bat`；可先加 `-CheckOnly` 唯讀核對。
3. 成功後從 `C:/Users/user/Desktop/CatOS` 重新開啟 Codex；核對 `outputs/integration-baseline-20261024/rename-result.json` 與新路徑服務身分。

腳本限制來源／目標為同一父目錄、不覆寫既存 CatOS、不接管未知埠 owner；只有已辨識且閒置的服務可停止／恢復。改名失敗時嘗試恢復舊根服務並保存原因。當時已做語法與 CheckOnly，**未驗證完整實體改名流程**；後續使用者取消，不再依先前授權執行。

- 改名前原始來源備份：`pre-change-sources.zip`，SHA-256 `3DA53542B718970CD96C9C3508DE7E5263C899301F023888C357CFAF947A7445`。
- 改名前 30 份變更來源備份：`before-rename-sources.zip`，SHA-256 `71cfba35886d36b8889c6bd2785d83af5edd06846ae6a016e1f394ea31bf115d`；`before-rename.json` 記錄來源雜湊、HEAD、stash、工作樹路徑與根目錄名稱。
- `services-before-rename.json`：原 8770／8771 已來源漂移；研究 active_run_id=null，simulation slot=idle。沒有恢復風控或執行正式 start／stop。
- 改名只改本機主目錄；遠端 URL／repo／分支名稱不隨之修改。Codex 專案入口可能仍指向舊根，須從新資料夾重新開啟。
- 測試 venv 是本機可再生產物，已排除 Git，不作為跨機交付；需要時按 requirements 重建。既有歷史絕對路徑僅供沿革；新證據索引以 repo 相對路徑為準。
- 最終來源雜湊、證據索引及既有工作樹保留核對見 `outputs/integration-baseline-20261024/verification.json`；實體改名狀態保持 blocked，不列為 PASS。

## 未關閉項目與下一成果

完整 Bot／策略管理、R1／主頁帳戶風控 HTTP、validation／report React 串接仍未完成。回測圖表錯值語義與部分互動線索保留於[串接表](backend-frontend-integration-map.md)，不因本次優化頁自測而關閉。情報未逐卡核對。DCM 缺失附件、研究歷史 hash 漂移、舊預覽／原型保留，詳見[盤點追蹤](project-inventory-audit-20261024.md)。

先交 GPT-6 Sol 獨驗整合基線、核對 Git 差異並整理具體提交清單；commit／push 另需授權。之後建議最小 Bot 狀態唯讀 HTTP 契約及主頁真實狀態接線，再評估控制操作，不自動實作。
