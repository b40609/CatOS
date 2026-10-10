# CatOS 目前接續入口

**更新時間**：2026-10-10 23:10 (UTC+8)  
**當前負責者**：開發者 (Antigravity) · 待驗收者 (chatgpt-web/gpt-5.6-sol)  
**工作目錄**：`C:/Users/kai/Desktop/CatOS_Astra`  
**Git 分支**：`feature/catos-react-vite`（追蹤遠端 `origin/feature/catos-react-vite`）

---

## 1. 當前階段與最新成果：React 前端定案 60:40 舒展四分割與 120 FPS 縮放引擎落地

已完整完成將 `http://127.0.0.1:8899/#/`（Vue 3）的卡片縮放與換位引擎複製至 `http://127.0.0.1:8890/#/`（React + Vite），並直接定案 **60:40 舒展四分割**：

1. **直接定案 60:40 舒展四分割（無多餘選項）**：
   - **比例定案**：左欄 60% 主視野（上軌走勢圖 50% / 下軌持倉明細 50%）；右欄 40% 輔助視野（上軌資產配置 50% / 下軌成交流 50%）。
   - **收斂清理**：在 [`layoutStore.ts`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/state/layoutStore.ts) 清除 64:36、50:50、70:30 等冗餘方案，儲存鍵升級為 `catos_layout_profiles_v3_6040`，預設強制生效 60:40；工具列標註「🔲 舒展四分割版面 (已定案) 60:40」。

2. **1:1 復刻卡片縮放與換位引擎**：
   - **左右分割拉伸**：按住中央垂直分割線平滑拉伸寬度（35%~80%），雙擊分割線自動還原 60:40。
   - **上下分割拉伸**：左欄與右欄各配備水平分割線，雙擊自動還原 50:50。
   - **16px 安全間隔**：分割線位於 16px 緩衝區中央，具備微光髮絲線反饋，徹底杜絕卡片邊框貼合為 0 的問題。
   - **直覺拖曳對調**：解鎖狀態每張卡片頂部顯示 `⋮⋮ 拖曳換位 ⇄` 抓手；拖曳源呈現半透明虛線態（`is-drag-source`），目標槽位高亮顯示 `DROP TO SWAP` 標籤，放開即刻對調。

3. **根本性修復卡頓（120 FPS 順暢跟手，比照側邊欄）**：
   - **拖曳中關閉 CSS 過渡**：設定 `!isResizing && "transition-all duration-200"`，拖曳時 1:1 即時跟隨滑鼠，解除 150ms 補間動畫衝突。
   - **I/O 延遲固化 (Lazy Persistence)**：拖曳中傳入 `persist = false`，不呼叫 `localStorage.setItem`，僅在 `onPointerUp` 放開時儲存一次，零 I/O 阻塞。
   - **`requestAnimationFrame` (rAF)**：所有分割線移動接入 rAF 影格節流，確保每幀（16.6ms / 8.3ms）精確更新一次。
   - **遮罩子元件事件**：拖曳期間卡片主體加上 `pointer-events-none`，阻斷 Recharts 與表格內部的重繪開銷。

4. **建置與驗證狀態**：
   - `frontend/cat-os-vite`：`tsc && vite build` **0 錯誤**，建置耗時 7.25s 通過。
   - 服務狀態：`http://127.0.0.1:8890/#/` 與 `http://127.0.0.1:8899/#/` 正常運行。

---

## 2. 筆電出國接續開發指引 (Laptop GitHub Continuation)

### A. 筆電環境要求
- Windows 10/11
- Git、Node.js 18+ 或 20+（含 npm）、Python 3.11+
- 本機專用（Localhost-only），禁止 Docker、PostgreSQL、Redis

### B. 筆電端 Git 同步指令 (免 USB，直接經由 GitHub)
若筆電已 clone 過專案：
```bash
git fetch origin
git checkout feature/catos-react-vite
git pull origin feature/catos-react-vite
```
若筆電為首次 clone：
```bash
git clone -b feature/catos-react-vite <YOUR_REPO_URL> CatOS_Astra
cd CatOS_Astra
```

### C. 筆電一鍵啟動並自動開啟網址
在專案根目錄直接執行腳本（或雙擊 `start-laptop-dev.bat`）：
```cmd
.\start-laptop-dev.bat
```
或 PowerShell：
```powershell
.\scripts\start-laptop-dev.ps1
```
> **腳本自動行為**：
> 1. 自動檢查並安裝 React (8890) 與 Vue (8899) 的 `node_modules`（若缺失）。
> 2. 自動在背景啟動 8890 與 8899 服務。
> 3. 服務就緒後，**自動在瀏覽器彈出開啟下列兩頁**：
>    - `http://127.0.0.1:8899/#/`（Vue 原版）
>    - `http://127.0.0.1:8890/#/review`（React 審查/對照版）

### D. 給筆電 Antigravity 的銜接指令 (Prompt)
```markdown
請拉取遠端最新 feature/catos-react-vite 分支，閱讀 docs/current-handoff.md，並執行 .\start-laptop-dev.bat 自動啟動前後端並開啟 http://127.0.0.1:8899/#/ 與 http://127.0.0.1:8890/#/review 雙頁，確認 60:40 佈局與 120 FPS 縮放無誤後接續開發。
```

---

## 3. 政策邊界與未涵蓋事項

* **禁止事項**：嚴格禁止碰觸真實 OKX API Key、禁止向外發出實盤交易請求、禁止使用外部非授權資料庫。
* **Git 邊界**：本輪工作已自測通過，程式碼推送到 `feature/catos-react-vite` 分支；獨立驗收仍由 `chatgpt-web/gpt-5.6-sol` 進行。
