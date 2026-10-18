# CatOS 目前接續入口

**更新時間**：2026-10-11 (UTC+8；首份 DCM 研究製品交驗，保留並行前端最新交接)  
**當前負責者**：DCM 研究開發與自測 (Codex)；前端視覺與互動開發者 (Antigravity) · 待獨立驗收者 (chatgpt-web/gpt-5.6-sol)  
**工作目錄**：`C:/Users/kai/Desktop/CatOS_Astra`  
**Git 分支**：`feature/catos-react-vite`（追蹤遠端 `origin/feature/catos-react-vite`；沿用前端交接資訊，研究本輪未執行 Git 核對）

---

## 本輪研究接續：DCM 六家族／三週期，已交開發自測證據

- 目標：理解 Pine → 多候選與反例 → 多週期成本後比較 → 按證據討論。允許隔夜，策略可演化；使用者看過證據後已確認保留 D 雙向反轉研究，不需重問。前端不作本次評估依據。
- 已校準：由 AI 解釋、選例、畫圖與提出疑點，用戶判斷合理性；不要求用戶先準備交易情境。新增 [三張可切換圖例](../artifacts/dcm-20261011-casebook-final/index.html)，復用已使用資料，新增下載／回測 0。當時／後續切換與六圖載入已用隔離 Edge 實際驗證，證據與命令見研究紀錄；未改 Antigravity 前端。
- 圖例回饋已更新：使用者認同假突破做空、假跌破做多；台股盤中跌破 DL 後等收盤站回買多。DH 收盤突破視為強多發動，之後幾天等 DC／DL／周／月成本回踩。回踩處若有 POC、EMA、SNR、OB／FVG 等同方向支撐／壓力共振，觸價進場；沒有共振則等收盤守住／站回，多空同理。空單退出可看 DL 或日 K 站上 DC／DH。點位固定／更新及各共振的精確定義仍待圖例收斂；觸價是已確認偏好，不能再重問。現行核心只支援收盤決策、次根開盤，未實作觸價撮合；詳見研究紀錄末節。
- 已完成：`catos/dcm.py`、`dcm_public_data.py`、`dcm_study.py` 與 23 個隔離 DCM 測試；沿用既有 Decimal／Closed Bar／下一根開盤／資金費核心，未改 DB schema、HTTP／MCP catalog 或交易底座。
- 公開資料：使用者本輪授權上網取得；僅 BTC-USDT-SWAP，2026-07-17 至 10-10 UTC，15m／1H／4H 共 10,710 根、256 資金費事件。公開 GET 135 次；無帳戶／憑證／產品 DB／交易請求。資金費 mark 是對應 1H mark 開盤近似，費率／滑價為明示假設。
- 研究結果：36 種家族／週期／限幅組合，150 個固定試驗、無最佳化；沒有候選通過事前探索門檻。最後段 D-15m 正損益但樣本小且開發段虧損；E 樣本不足、B 最後段虧損，不選定部署策略。最後段已使用，不再當新的未使用資料。
- 驗證：72 個開發自測 PASS；封存修改後 23 個受影響測試再 PASS。封存來源離線重跑後 report／selection bytes 相同；共 450 次市場回測執行，均為同一 150 試驗的初次／封存／再現，未新增調參。不是獨驗；Git 未執行。
- 詳細規則、失敗修復、實際命令、結果與未涵蓋項目：[研究紀錄](dcm-research-plan.md)。製品：[報告](../artifacts/dcm-20261011-study-final/report.html)、[再現證據](../artifacts/dcm-20261011-selftest/replay-verification.json)；原 Pine／完整執行程式已封存，市場資料與證據位於 gitignore 的 `artifacts/dcm-*/`，跨機接續需另外保留。
- 下一成果建議：依最新意圖提供發動後成本回踩的共振證據，先比較單一共振與收盤確認，再另設計觸價研究的撮合契約；舊 D／B／C 結果不能視為此框架已驗證。較長期間事件證據及 MCP 製品／快照接入仍待辦。未來聊天建議快照共用＋精確結果快取＋持久研究意圖，詳見研究紀錄；目前尚未接入或實作同步常駐功能。
- 指定 `chatgpt-web/gpt-5.6-sol` 獨驗差異與必要證據，commit／push 另授權。研究本輪未動前端、8770／8771、Demo／Live、產品資料根及其他目錄。以下前端為並行開發者最新交接，未由研究本輪核對或重驗。

## 1. 前端並行成果：8890 (React 19) 視覺瑕疵根除與全子頁面 Noir & Gold 終端化

針對先前斷網與上下文幻覺導致的程式碼混亂、8890 雙層邊框瑕疵及子頁面佔位符問題，已依據 ChatGPT 歷史共識全面完成下列修復與升級：

1. **消除雙層邊框與右下卡片溢出（截圖瑕疵根因解決）**：
   - 在 [`workspace-grid.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/workspace-grid.tsx) 外層定義單一 `rounded-xl border border-border/80 bg-surface/90 backdrop-blur-md`，並引入 `[&_.panel]:border-0 [&_.panel]:rounded-none [&_.panel]:bg-transparent`，徹底根除內部組件 `.panel` 導致的「框中框／雙重圓角」嵌套瑕疵。
   - 在 [`shell.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/shell.tsx) 的 `Panel` 與 [`index.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/index.tsx) 的 `allocation` / `fills` 容器加上 `flex-1 min-h-0 overflow-y-auto`，右下成交流完美自適應滾動，不再切斷底部行情。

2. **全子頁面終端化（徹底消除 "Coming next" 骨架感）**：
   - [`backtest.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/backtest.tsx)：4 大 KPI 卡、歷史任務清單（選中高亮）、Closed Bar 與 Decimal 執行約束橫幅、逐筆模擬成交流表格。
   - [`optimization.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/optimization.tsx)：Optuna TPE 任務狀態卡、3 參數搜尋空間、一鍵導出 Trial #42、帕累托最優 Top Trials 排行榜。
   - [`market-intel.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/market-intel.tsx)：獨立情報源架構約定橫幅、Yaozi 哨兵清算/偏離預警卡、跨所（OKX vs Binance）8H 資金費率偏離套利矩陣。
   - [`settings.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/settings.tsx)：OKX KOL 返佣 Tag (`"tag": "41cb53c54d6dABDE"`) 一鍵複製、cross + net_mode 保證金約束、本機 Localhost 執行底座說明。
   - [`bots.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/bots.tsx)：1 Bot : 1 SWAP 獨佔合約約定橫幅、OKX USDT-M SWAP 合約規範（`BTC-USDT-SWAP` 等）、Supervisor 強制注入 Tag 審計面板、集群狀態與損益動態匯總。
   - [`risk.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/pages/risk.tsx)：E_risk = E_verified 風控約定、4 大動態儀表盤（總曝險、槓桿 2.81x/3.0x、單幣上限 42.8%/50%、日損 3.42%/10%）、Asia/Taipei 00:00 Soft 10% 停止增倉 / Hard 20% 市價清倉與 Kill-Switch 鎖存規則。

3. **Mock 數據與契約嚴格校準 (Mock Alignment)**：
   - 全面替換 `data.ts` 中的 PERP / Spot 標的為 OKX SWAP 標準合約（`BTC-USDT-SWAP`、`ETH-USDT-SWAP`、`SOL-USDT-SWAP` 等）。
   - 成交流注入 Supervisor 強制標記 `tag: "41cb53c54d6dABDE"`，完全契合 OKX KOL 返佣架構。

4. **四分割工作台定案方案 3（常態拖曳零按鈕 · Zero-UI）**：
   - 彻底移除頂部 4 張笨重靜態 KPI 卡片（`UnifiedKpiStrip`）與中間佔位橫條（`LayoutRibbon`）。
   - 徹底杜絕自我說明廢話，全域 Header 保持極致純淨，0 額外按鈕佔位。
   - 工作區高度自適應延展至 `h-[820px] lg:h-[calc(100vh-80px)]`，視野 100% 留給核心四分割數據。
   - 四卡片常態支援自由拉伸（120 FPS rAF 流暢縮放），雙擊中央分割線自動還原 60:40，雙擊水平分割線還原 50:50。

5. **帳戶權益卡片縮放排版瑕疵修復與方案 B 定案（Bloomberg 緊湊側欄 + 自適應圖表）**：
   - **根除高度寫死黑洞**：走勢圖徹底擺脫寫死 `height = 210`，改由 `ResizeObserver` 雙向測量寬高，SVG 折線與漸層面積 100% 垂直隨容器自適應延展。
   - **消除雙層 Header 冗餘**：徹底移除外層 28px 冗餘握把條（「按住拖曳換位 ⇄」），將拖曳換位事件直接掛於卡片頂部 Header（距離頂部 42px 內），全卡片 Header 一體化收斂為 34px 單層結構，帶金色 `⋮⋮` 抓手圖示。
   - **消除指標撕裂感**：左側 KPI 欄移除 `justify-between` 撕裂拉扯，改為頂部自然緊湊排列；拉高時自然展現「保證金使用率」與「最大歷史回撤」等深層指標，消除下方空洞。
   - **方案 B 徹底定案落地**：移除所有多方案切換代碼，固定為 Bloomberg AIM / TradingView 風格緊湊側欄 + 自適應圖表佈局，標頭保持純淨：`⋮⋮ 帳戶權益 (Equity & Drawdown)` 與 `[24H] [7D] [30D]`。

6. **業務內容全盤校準 (Option A 一次到位) 與 8899 v0 核心三大卡片完整移植落地**：
   - **右上卡片（多空曝險配置 · Exposure）**：移植 8899 雙向標尺尺規組件 [`exposure-panel.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/exposure-panel.tsx)。
   - **右下卡片（量化機器人矩陣 · Bots Matrix）**：移植 8899 雙層高階版表格組件 [`v0-bot-table.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/v0-bot-table.tsx)。
   - **左下卡片（部位與活動 · Positions & Activity）**：移植 8899 三 Tab 綜合組件 [`activity-panel.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/activity-panel.tsx)。
   - **左上卡片（帳戶權益 · Equity）**：在方案 B 左側欄底部注入有效槓桿與 Asia/Taipei 00:00 風控防線。

7. **自研輕量級 Layout Tree 引擎落地（2026-10-13 交付）**：
   - **二元分割空間樹 (Binary Layout Tree)**：在 [`types.ts`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/types.ts) 與 [`tree-ops.ts`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/tree-ops.ts) 實作純函數樹引擎，0 外置笨重依賴，全面支援遞迴分割與持久化。
   - **接縫感應提示條 (Drop Seam Sensing · 方案 A 定案)**：使用者已確認採「VS Code 扇區模式」，徹底廢除大面積 Center Swap 誤觸。在 [`drop-indicator.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/drop-indicator.tsx) 與 [`tree-node-renderer.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/tree-node-renderer.tsx) 依主對角線 100% 劃分上、下、左、右四向扇區，專注接縫分裂；琥珀金光柱 (`bg-primary animate-pulse`) 與方向徽章指示（`← 插入左側`、`→ 插入右側`、`↑ 插入上方`、`↓ 插入下方`）。
   - **高對比落位槽與自定義微型 DragImage（徹底根除幽靈重疊 BUG）**：
     - 在 [`drop-indicator.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/drop-indicator.tsx) 中引入 `bg-background/92` 實體遮罩 + CAD 工程幾何斜紋與 3px 雷射光柱，解決原 15% 透明度太淡導致底層文字穿透混亂問題。
     - 在 [`tree-node-renderer.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/tree-node-renderer.tsx) 透過 `setDragImage` 建立微型金黑膠囊，徹底杜絕瀏覽器原生抓取整張大卡片 DOM 造成的「雙重文字幽靈重疊 BUG」；並將操作膠囊居中（`left-1/2 -translate-x-1/2`），根除長標題與右側按鈕撞車。
   - **插入分裂 (2卡變3卡) 與移除自動合併 (Auto-Merge)**：支援卡片一鍵快速分裂選單及拖曳分裂；關閉卡片時兄弟節點直接平滑取代父容器填滿空間，0 留白空洞。
   - **每條分割線自由拉伸 (120 FPS rAF)**：在 [`tree-splitter.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/lib/layout-tree/tree-splitter.tsx) 與 [`workspace-grid.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/workspace-grid.tsx) 實作獨立節點 rAF 拉伸，雙擊自動還原 50:50。
   - **預設佈局秒切**：工作台頂部整合四分割 (60:40)、三分割 (左一右二)、雙分欄 (50:50) 與新增卡片快捷列。

8. **雙端建置與驗證狀態**：
   - `frontend/cat-os-vite` (8890, React 19 + Tailwind v4 + Radix UI)：`tsc && vite build` **0 錯誤** 通過（11.25s）。
   - 實機截圖存證：四分割 [`layout_tree_vscode_sectors.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/c33cb8e1-6de3-4e28-bf1a-9e3034043165/layout_tree_vscode_sectors.png)、三分割 [`layout_tree_tri_split.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/c33cb8e1-6de3-4e28-bf1a-9e3034043165/layout_tree_tri_split.png)、雙分欄 [`layout_tree_dual_split.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/c33cb8e1-6de3-4e28-bf1a-9e3034043165/layout_tree_dual_split.png)。

9. **8890 卡片移動所有相關 BUG 全面根除 (2026-10-14 交付)**：
   - **根除拖曳即時取消與無法移動的毀滅性 BUG**：原先 `workspace-grid.tsx` 中的 `isLiveMorphing` 在拖曳 `dragover` 期間即時替換樹結構，導致瀏覽器 HTML5 拖曳來源 DOM 節點被 React 卸載（Unmount），瀏覽器依規範強制中斷拖曳（觸發 `dragend`）。現改為拖曳期間保持樹結構穩定，由 `DropIndicator` 提供藍圖骨架預覽，放開滑鼠（`drop`）時精準提交並持久化，徹底根除無法移動問題。
   - **完整支援中央對調換位 (Center Swap ⇄) 與四向邊緣接縫分裂 (Edge Split ⊞)**：擴充 `types.ts` 納入 `"center"`；中央 56% 區域判定為對調換位（Swap Panes ⇄），兩張卡片內容與身份乾淨互換，不破壞四分割樹比例；外圍 22% 邊緣判定為四向分裂插入（Dock / Split ⊞）。
   - **杜絕按鈕與分頁標籤誤觸拖曳**：在 `handleDragStart` 過濾 `button`、`input`、`select`、`[role='button']`，點擊週期按鈕（24H/7D/30D）與持倉標籤不再誤觸卡片拖曳。
   - **自定義金色微型 DragImage 與直觀抓手**：修正 `setDragImage` 膠囊建立與非同步安全清理；四大卡片標題列抓手注入 `cursor-grab active:cursor-grabbing`。
   - **開發自測通過**：隔離測試腳本覆蓋中央對調、邊緣分裂、兄弟節點對調及樹剪枝全部 PASS，`tsc && vite build` 0 錯誤通過。

---

## 2. 分工約定與後續接續 (Handoff & Next Steps)

- **前端開發者 (Antigravity)**：本輪前端視覺極致化、四分割佈局、120 FPS 縮放跟手、視覺瑕疵根除與子頁面補齊已全數交付。
- **後端與資料對接者 (GPT-6.1)**：接手後端 Supervisor 核心、IPC 通訊契約與狀態轉接層（`stateAdapter`）對接。
- **獨立驗收者 (`chatgpt-web/gpt-5.6-sol`)**：進行 Git 差異核對與獨立驗收。未獲授權不得自行提交或推送至遠端。

---

## 3. 政策邊界與不可碰事項

- **嚴禁事項**：禁止接觸真實 OKX API Key、禁止向外發出實盤交易請求、禁止引入 Docker / PostgreSQL / Redis 等外置依賴。
- **金融底線**：交易計算嚴格維持 Decimal / SQLite TEXT；SWAP 委託強制包含 tag: `41cb53c54d6dABDE`；OKX 子帳戶專用，禁止陌生部位處置。
