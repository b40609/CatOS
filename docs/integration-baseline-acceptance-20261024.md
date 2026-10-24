# CatOS 整合基線獨立驗收與提交範圍

日期：2026-10-24（Asia/Taipei）。使用者授權「整合基線獨立驗收＋提交範圍整理」，不含 stage／commit／push。主目錄維持 `CatOS_Astra`，產品名稱為 CatOS。

## 驗收狀態

限定範圍獨立驗收通過（Scoped PASS）：指定 GPT-6 Sol 首輪發現 REV-01／P1，首輪結論為 BLOCKED；主代理修復後交原獨驗者聚焦複核，8 項 store／adapter、10 項隔離互動、typecheck／build 全數通過。原阻擋已解除，未發現新的範圍內阻擋缺陷。

獨驗角色為實際指定模型 `chatgpt-web/gpt-6-sol`，子代理 `01a16d2b-7670-7af0-960b-8178af7fe35d`；主代理負責缺陷修復與文件收尾，沒有將自己的開發自測代稱獨驗。

基準為分支 `feature/catos-react-vite`、HEAD `149f9fcbf2a2c5d741aa696750ab1ed62ae14460`。驗收對象是整合基線變更，並非全案、完整 Bot 控制、R1 HTTP 或 Demo／Live 就緒認證。

## 本輪發現與修正

| 編號／級別 | 發現、處理與證據 |
| --- | --- |
| REV-01／P1，已關閉 | 首輪獨驗確認 Local 收到 Bot／KPI v10 後切換 Demo／Live，v1 初始化會被舊模式版本擋住，留下 Local 資料。已修正不同模式同步清空投影、版本與命令，模式切換自動重載，透過世代隔離舊模式的延遲回應；Demo／Live 不載入 Local 命令。保留同模式單調版本保護。回歸測試修復前 4 pass／4 fail，修復後 8／8，原獨驗者重驗通過。缺陷限展示投影，沒有實際下單證據 |
| ACC-01／P2，已修復 | 舊入口快照含終端截斷提示，未完整保存原文。已由既有 `pre-change-sources.zip/current-handoff.md` 透過 Patch 恢復完整正文，只增加前兩行歷史／恢復註解。獨驗核對：正規化換行後正文完全一致，均為 41,581 字元、無截斷標記；原備份正文 SHA-256 為 `96eef09081ef88da4aedb15d6211d89fdc70b9d2a83ca82ee07587a93e5d9ac0`。原始備份未改，證據 `archive-compare.json` |
| ACC-02／文件範圍 | 未採用的更名工具保留本機、排除提交；整合交付內改用歷史檔名記述，避免提交文件連結到未交付工具。取消更名不再列為待辦或阻斷 |
| ACC-03／P3 | README 的 `catos/db`、`catos/core` 與 LICENSE 共 4 處本機連結失效。前兩者改指實際來源；根目錄與 Git 皆未提供 LICENSE，移除未有檔案支持的 MIT 徽章／宣稱，記錄現況，不代替使用者新增或選擇授權條款 |

## 證據核對與實際驗證

本輪原始日誌與 JSON 位於本機 `outputs/integration-acceptance-20261024/`，不列入提交白名單；前輪證據位於 `outputs/integration-baseline-20261024/`。這些本機原始證據不會因提交文件而自動搬到另一台 PC，需要另行保存／傳遞，或以本次納入的測試重現。

| 範圍 | 本輪結果與適用界線 |
| --- | --- |
| Git／既有材料保存 | HEAD、兩份既有 stash 未變；暫存區空白。原有 721 份未追蹤路徑均存在，僅核對存在性，不讀產品 DB／憑證內容 |
| 前輪原始證據 | `verification.json` 所列 14 份日誌／JSON SHA-256 全部一致；沿用歷史證據，未冒稱本輪重跑 |
| 後端來源 | 202 份既有 catos／tests Python 來源與原盤點 SHA-256 全部一致；後端與既有測試無工作樹差異。前輪 56／56 保留為歷史結果，不計入本輪新增通過數 |
| 工具路徑修正 | 3 份 Python 來源 AST 解析通過；差異僅為從 `__file__` 推導 checkout 內的輸出路徑及產品名稱。未執行會寫入外部素材目錄的產生器 |
| 目前 8890 | 唯讀身分端點的 contract／root 符合本 checkout；launcher `-CheckOnly -NoBrowser` exit 0，HTML 就緒；未啟停既有服務 |
| 目前後端服務 | 核對時 8770／8771 無 listener；launcher 明示後端 unavailable／身分來源未合格。前端 ready 不代表研究 API ready；未恢復服務或執行正式控制案例 |
| GPT-6 Sol：store／adapter | 修復後 `npm.cmd test`：8／8、fail 0、exit 0，940.3485 ms；`frontend-test-rev01.log`。載入正式 store／adapter，涵蓋舊事件、延遲 hydrate、無效版本、Decimal 字串、Local 高版本切至 Demo／Live、回 Local、同模式保護及跨模式舊回應隔離。首輪 4／4 另保留 `frontend-test.log`，不取代修復後證據 |
| GPT-6 Sol：隔離互動 | 修復後 `node tests/integration_baseline_test.mjs <bundled-node_modules> <isolated-python>`：10／10、exit 0；`integration-recheck.log`、新建 `outputs/integration-baseline-20261024/fixture-BfQ8Bd/result.json`。包含真 Vite 代理、Host／Origin 正反案例、build／instance、冪等 POST、恢復輪詢、跨 kind 共用槽、過期結果隔離、單次提交、展示標示及實際點選 Demo／Live／本機的投影隔離與重載；使用合成來源與可控 React fixture，未執行正式控制案例。首輪 9 項證據另存 `fixture-BHsZmz` |
| GPT-6 Sol：型別／建置 | 修復後 `npm.cmd run typecheck` exit 0；`npm.cmd run build -- --outDir ../../outputs/integration-acceptance-20261024/build-rev01 --emptyOutDir false` exit 0，2,374 modules、3.68s。日誌 `typecheck-rev01.log`、`build-rev01.log`；主 JS chunk 1,442.14 kB／gzip 394.84 kB，保留超過 500 kB 的警告。首輪日誌另存，沒有冒稱零警告 |
| GPT-6 Sol：程式審查 | 修復後聚焦複核通過，REV-01 關閉；確認不同模式同步清空、世代隔離、切換自動重載、同模式版本保護與 Promise 錯誤處理，未發現新的範圍內阻擋 |
| REV-01 開發回歸 | `npm.cmd test`：新增案例在修復前失敗，修復後 8／8、fail 0；`mode-regression-before.log`、`mode-regression-after.log`。涵蓋 Local 高版本切至 Demo／Live、切回 Local、同模式版本保護與 Local→Demo→Local 延遲回應；此列為開發自測，獨驗結果另列 |
| GPT-6 Sol：文件／Git | `archive-compare.json`、`readme-check-final.json`、`scope-check-final.json` 全數合格；32 份清單無缺件／重複，涵蓋 21 份已追蹤變更與 11 份必要未追蹤檔。17:41（台北）核對 HEAD／分支／兩份 stash 與空白 index；其後僅主代理收尾文件與證據 |
| 最終服務／交付封存 | 主代理唯讀確認 8890 owner 33688、身分 root 符合本 checkout、HTML 200；8770／8771 未啟動，18870／18890 測試後均無 listener。`services-final.json`；最終來源／日誌 SHA、提交清單與保存核對記錄於 `verification-final.json`，屬文件收尾，非另一輪獨驗 |

## 提交範圍

精確白名單見 [integration-baseline-submission-20261024.json](integration-baseline-submission-20261024.json)，共 32 份，建議分成兩次提交，兩組均尚未 stage／commit。

| 建議提交 | 檔案數 | 範圍 |
| --- | --- | --- |
| `fix(integration): establish local frontend and research baseline` | 29 | 前端展示權威、優化 hook、store、防護代理、launcher、HTTP 依賴、測試，以及現況／驗收／歷史快照文件 |
| `chore(tools): resolve generated asset paths from checkout root` | 3 | tools 產生器／素材同步的本機路徑修正，與執行期整合分開審閱 |

新 hook、共享 store、Vite plugin、Python fixture 必須與引用端一起提交；不能只依 `git diff --stat` 的已追蹤檔案清單提交，否則會漏掉必要新模組。`scripts/compat/deepseek-r3-mcp.cordis.yml` 已恢復為 HEAD 內容，無差異可提交。

排除所有 `outputs/`、歷史 `frontend/workspace/`、原型、可再生 build／venv／node_modules、產品資料／DB／憑證、兩份未採用更名工具及其他不在白名單的未追蹤內容。排除代表不納入這兩次提交，沒有刪除或放棄這些材料。

## 保留限制與下一步

完整 Bot／策略管理 HTTP、R1／主頁帳戶風控 HTTP、validation／report React、回測全面互動與情報逐卡資料新鮮度均不在此次驗收範圍。歷史 DCM 缺件、研究封存來源 hash 漂移及全專案證據保存政策仍依[盤點](project-inventory-audit-20261024.md)追蹤；本輪合成 fixture 通過不能關閉上述事項。

已完成指定角色複核並更新[接續入口](current-handoff.md)。提交／推送仍需使用者另行授權；下一個功能建議為最小 Bot 狀態唯讀 HTTP 契約與主頁接線，尚未開工。
