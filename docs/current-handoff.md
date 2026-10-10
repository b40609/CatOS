# CatOS 目前接續入口

**更新時間**：2026-10-10 23:00 (UTC+8)  
**當前負責者**：開發者 (Antigravity) · 待驗收者 (chatgpt-web/gpt-5.6-sol)  
**工作目錄**：`C:/Users/kai/Desktop/CatOS_Astra`

---

## 1. 當前階段與最新成果：React 前端定案 60:40 舒展四分割與 120 FPS 縮放引擎落地

已完整完成將 `http://127.0.0.1:8899/#/`（Vue 3）的卡片縮放與換位引擎複製至 `http://127.0.0.1:8890/#/`（React + Vite），並直接定案 **60:40 舒展四分割**：

1. **直接定案 60:40 舒展四分割（無多餘選項）**：
   - **比例定案**：左欄 60% 主視野（上軌走勢圖 50% / 下軌持倉明細 50%）；右欄 40% 輔助視野（上軌資產配置 50% / 下軌成交流 50%）。
   - **收斂清理**：在 [`layoutStore.ts`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/state/layoutStore.ts) 清除 64:36、50:50、70:30 等冗餘方案，儲存鍵升級為 `v3_6040`，預設強制生效 60:40；工具列標註「🔲 舒展四分割版面 (已定案) 60:40」。

2. **1:1 復刻卡片縮放與換位引擎**：
   - **左右分割拉伸**：按住中央垂直分割線平滑拉伸寬度（35%~80%），雙擊分割線自動還原 60:40。
   - **上下分割拉伸**：左欄與右欄各配備水平分割線，雙擊自動還原 50:50。
   - **16px 安全間隔**：分割線位於 16px 緩衝區中央，具備高階微光髮絲線反饋，徹底杜絕卡片邊框貼合為 0 的問題。
   - **直覺拖曳對調**：解鎖狀態每張卡片頂部顯示 `⋮⋮ 拖曳換位 ⇄` 抓手；拖曳源呈現半透明虛線態（`is-drag-source`），目標槽位高亮顯示 `DROP TO SWAP` 標籤，放開即刻對調。

3. **根本性修復卡頓（120 FPS 順暢跟手，比照側邊欄）**：
   - **拖曳中關閉 CSS 過渡**：設定 `!isResizing && "transition-all duration-200"`，拖曳時 1:1 即時跟隨滑鼠，解除 150ms 補間動畫衝突。
   - **I/O 延遲固化 (Lazy Persistence)**：拖曳中傳入 `persist = false`，不呼叫 `localStorage.setItem`，僅在 `onPointerUp` 放開時儲存一次，零 I/O 阻塞。
   - **`requestAnimationFrame` (rAF)**：所有分割線移動接入 rAF 影格節流，確保每幀（16.6ms / 8.3ms）精確更新一次。
   - **遮罩子元件事件**：拖曳期間卡片主體加上 `pointer-events-none`，阻斷 Recharts 與表格內部的重繪開銷。

4. **建置與驗證狀態**：
   - `frontend/cat-os-vite`：`tsc && vite build` **0 錯誤**，建置耗時 7.25s。
   - 服務狀態：`http://127.0.0.1:8890/#/` 正常監聽運行。

---

## 2. 筆電出國接續開發指引 (Laptop Continuation Checklist)

### A. 檔案同步建議（若要在筆電上繼續開發）
* **免拷貝項目（減少傳輸體積）**：
  - 忽略所有 `node_modules/` 與 Python `.venv/`。
  - 建議使用隨身碟拷貝整包 `CatOS_Astra` 或推送到私有 Git 分支（排除快取與打包 zip）。
* **筆電必備環境**：
  - Node.js 18+ 或 20+（含 npm）。
  - Python 3.11+。
  - 本地 SQLite（無需 Docker、無需 PostgreSQL、無需 Redis）。

### B. 筆電本機一鍵啟動指令
```bash
# 1. 進入 React 前端目錄 (8890 主線)
cd frontend/cat-os-vite
npm install
npm run dev -- --port 8890 --host 127.0.0.1

# 2. (可選) 若需對照 Vue 原版 (8899 參考線)
cd frontend/redesign-v2-return
npm install
npm run dev -- --port 8899 --host 127.0.0.1
```

### C. 筆電開啟新 AI 對話之一鍵提示詞 (One-Line Handoff Prompt)
> 「請先閱讀 `docs/current-handoff.md`。目前已完成 React 版前端 8890 的 60:40 舒展四分割定案與 120 FPS 流暢縮放拖曳換位。請根據接續入口指示繼續下一階段工作。」

---

## 3. 政策邊界與未涵蓋事項

* **禁止事項**：嚴格禁止碰觸真實 OKX API Key、禁止向外發出實盤交易請求、禁止使用外部非授權資料庫。
* **Git 邊界**：本輪程式碼已在本地自測通過；commit / push 依規範維持由指定角色（`chatgpt-web/gpt-5.6-sol`）獨立驗收後另行授權。
* **下一步建議**：
  1. 完成其他子頁面（策略中心、機器人管理、風控中心）至 React 版的統一搬移與元件復用。
  2. 配合獨立驗收角色進行 Git 工作樹核對。
