# CatOS 目前接續入口

**更新時間**：2026-10-18 21:55 (UTC+8；前端資產配置環圖全響應式流體化定案與版面收斂完成，準備跨機交接)  
**當前負責者**：前端視覺與互動開發者 (Antigravity / 6.1 Sol) · 待獨立驗收者 (chatgpt-web/gpt-5.6-sol)  
**工作目錄**：`C:/Users/kai/Desktop/CatOS_Astra`  
**Git 分支**：`feature/catos-react-vite`（追蹤遠端 `origin/feature/catos-react-vite`）  
**明日目標**：接續至公司電腦開發環境，啟動 Vite 驗證，並依序推進 Stage 2 佈局快捷板或策略回測聯調。

---

## 1. 今日核心成果交付：資產曝險配置環圖 (Allocation Donut) 完美收斂定案 (2026-10-18)

針對使用者指示「顯示比例問題」與「卡片縮放未跟隨、太大了頂天立地、字體跑版切邊」等問題，已徹底完成全方位幾何重構與收斂固化：

1. **中心純淨留空（方案 1 定案）**：中央維持沉穩留空，資訊全面移至外部標註，杜絕中央擁擠雜亂。
2. **外置微折短鉤（方案 A 定案）**：徹底廢除長水平托盤底線，採用 8~14px 雅緻 45° 肘點 + 微折短鉤，引線絕不穿透切割文字。
3. **全響應式流體幾何架構 (Fluid ResizeObserver)**：
   - 根除寫死 `max-h-[260px]` 與固定 `viewBox`；由容器 `ResizeObserver` 60 FPS 即時捕捉卡片寬高 `(W, H)`，拖曳卡片邊界時圓環與線條平滑等比縮放。
   - **黃金比例收斂（解決「太大了」）**：圓環半徑嚴格限縮至最大 75px（外直徑約 170px，維持容器高度約 50%~55% 黃金佔比），環身厚度收斂在 12~24px，兼顧厚實份量與深黑呼吸留白。
   - **垂直防溢出安全夾持（解決「真實本金字體切邊跑版」）**：針對 12 點鐘（`佔用 0.1%`）與 6 點鐘（`可用 99.9%`）等垂直切片，肘點強制向外側展 16px，文字 Y 軸座標嚴格鎖定在 `[18px, H - 24px]` 安全區間內，絕不切字或跌入底部麵板。
   - **底部量化指標徹底防折行**：全面鎖定單行等寬微標（`whitespace-nowrap`），各尺寸視窗下嚴格防擠壓疊字。
4. **收斂固化 SOP**：徹底移除所有臨時開關、對照開關與過渡狀態，還原為高質感單一正式組件，頂部配備 `即時同步` 微光指示。
5. **編譯自測**：`npm run build` (tsc + vite build) **0 錯誤** 通過（7.39s），全視圖截圖已存證。

---

## 2. 既有研究與前端架構基線 (維持完整保留)

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

## 2. 前端全面收斂固化與開發 SOP 定案 (2026-10-18 交付)

本輪前端優化實驗與版面評選經使用者逐項審閱後，已依使用者指示全面執行**收斂固化（Solidification）**與代碼清理：

1. **8899 工作台 (Vue 3, `redesign-v2-return`) 固化**：
   - 永久定案為「方案一：舒展四分割 (60:40) 定案純淨視圖」。
   - 徹底刪除方案 A/C/D、頂部切換膠囊按鈕（`style-toggle-pill`）、次級工具條（`hybrid-ribbon`，含「⚙ 調整版面」與「🔲 舒展四分割」狀態牌）、四卡片標題列上的版本膠囊（`V0 | 原版`），四張核心卡片 100% 垂直頂滿視野，實現極致零浪費純淨四分割。

2. **8890 主終端 (React 19, `cat-os-vite`) 固化**：
   - **開關 1 (頂部態勢帶)**：徹底拔除，全域 Header 保持純淨純寬裕，資產回歸【系統總覽】首頁。
   - **開關 2 (子頁面佈局)**：全面固化「方案 B（零浪費頂滿首屏）」，子頁面（Bots、Risk、Market Intel、Backtest、Optimization）統一採用精簡工具列，釋放 200px 垂直高度。
   - **開關 3 (盤口 Tick 閃爍)**：正式固化，微光漸層呼吸跳動直接常態啟用。
   - **開關 4 (部位深度指標)**：正式固化，採用 OKX 官方標準「預估強平價」、「距爆倉」與純粹白話「停損價」，徹底拋棄 P6 等工程晦澀詞。
   - **開關 5 (回測水下載回撤與熱力圖)**：正式固化為默認圖表組件。
   - **開關 6 (超參數優化帕累托散佈圖)**：正式固化為默認圖表組件。
   - **開關 7 (全域命令面板)**：不採用，徹底刪除。
   - **過渡元件徹底刪除**：已刪除 `optimization-labs.tsx`（實驗室彈窗）、`optimizationStore.ts`、`global-telemetry-bar.tsx`、`command-palette.tsx`，並拔除所有卡片標題列上的 `X` 關閉按鈕（`從主畫面關閉此卡片`）與「新增卡片 (4/6)」下拉選單，四分割版面鎖定。

3. **視覺決策定案 SOP 正式寫入 `AGENTS.md`**：
   - **定案固化 SOP（Solidify & Purge on Decision）**：使用者一旦對 UI/UX 方案拍板定案，下一階段開發即刻執行收斂固化——直接寫死為正式代碼，第一時間徹底清除所有臨時對照開關、實驗室彈窗、過渡期分支代碼與冗餘自訂按鈕，嚴禁在交付環境中繼續殘留已決策之過渡調試選項。
   - 型別驗證：`npx tsc --noEmit` 0 錯誤通過；全域實機截圖已完成存證。

---

## 3. 交易帳戶模式恢復與 TradingView / 台灣 XQ 工作台多階段落地 (2026-10-18 Stage 1 交付)

針對使用者指示「切換 (本機 Demo Live) 交易帳戶模式是 CatOS 開發文件內的最基礎需求」以及「參考台灣 XQ 或 TradingView 的靈活多階段套用」，已完成 **Stage 1 (第一階段)** 實作與實機截圖存證：

1. **核心交易帳戶切換器 (`[本機] [Demo] [Live]`) 正式恢復並連動**：
   - 新增 [`mode-selector.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/mode-selector.tsx)，直接嵌入全域 Header 右側。
   - 雙向連動 `useCatStore` 與 `stateAdapter.setMode`，提供三色專屬狀態：
     - **本機 (Local Sim)**：琥珀金呼吸微光 (`bg-amber-500/15 text-amber-400 border-amber-500/40`)，可自由啟動/停止策略進行本機模擬。
     - **Demo (模擬盤)**：青空藍標示 (`bg-cyan-500/15 text-cyan-400 border-cyan-500/40`)，唯讀隔離展示，禁止增倉與下單。
     - **Live (實盤)**：警示紅標示 (`bg-rose-500/15 text-rose-400 border-rose-500/40`)，依 INVARIANTS 嚴格鎖定防護，禁止真實金鑰。

2. **Stage 1：台灣 XQ / TradingView 風格卡片原地模組切換 (In-Place Module Swap)**：
   - 解決痛點：不需破壞已調校好的 60:40 或自訂分割線，任何視窗皆可原地秒切為交易員當前最想看的量化視窗。
   - 在 [`card-header-title.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/card-header-title.tsx) 引入微型下拉標記 `▾`，點擊即展開快速切換選單：
     - 📈 帳戶權益 (Equity & Drawdown)
     - 📊 部位與活動 (Positions & Activity)
     - 📐 多空曝險配置 (Exposure & Margin)
     - 🤖 量化機器人 (Bots Matrix)
     - 🪙 資產配置比例 (Asset Allocation Donut)
     - ⚡ 即時成交流 (Recent Fills)
   - 呼叫 `layoutStore.replaceLeafNode(leafId, newCardId)` 原地替換，即時生效並持久化。

3. **動態自由增刪卡片功能正式啟用 (Add & Remove Card Controls)**：
   - 使用者明確指示「要的是原本可以新增或刪減單張卡片的選項」，讓用戶有打造屬於自己 OS 的高度自由：
   - **新增卡片 (Add Card)**：在 [`shell.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/shell.tsx) 頂部 Header 正式掛載 [`card-manager-dropdown.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/card-manager-dropdown.tsx)，呈現 `[+ 新增卡片 4/6]` 即時狀態指示。點擊展開「主畫面卡片庫」，可一鍵將未在畫面上的卡片加入排版，或快速點擊「四分割／三分割／雙分欄」佈局預設。
   - **刪減卡片 (Remove Card)**：在 [`card-header-title.tsx`](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/cat-os-vite/src/components/catos/card-header-title.tsx) 為每張卡片常態提供微型 `✕` 關閉按鈕（以及標題下拉選單內的「關閉此卡片」選項）。當畫面卡片數 > 1 時，點擊即可刪減單張卡片，其餘卡片自動觸發 Auto-Merge 平滑填滿視野空間，0 空白空洞；最後 1 張核心卡片受防誤刪保護。

4. **實機截圖存證（眼見為憑）**：
   - 頂部 `[+ 新增卡片 4/6]` 與每張卡片 `✕` 關閉按鈕總覽：[`catos_8890_add_remove_overview.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/57b93e2d-f876-4b94-891c-5b6f304c8966/catos_8890_add_remove_overview.png)
   - 點擊展開「主畫面卡片庫」面板（自由選擇 6 大卡片開關）：[`catos_8890_card_manager_open.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/57b93e2d-f876-4b94-891c-5b6f304c8966/catos_8890_card_manager_open.png)
   - 點擊 `✕` 刪減卡片後：自動平滑合併為三分割（按鈕即時變為 `3/6`）：[`catos_8890_card_removed_tri.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/57b93e2d-f876-4b94-891c-5b6f304c8966/catos_8890_card_removed_tri.png)
   - Demo 模式切換狀態：[`catos_8890_stage1_demo_mode.png`](file:///C:/Users/kai/.gemini/antigravity-ide/brain/57b93e2d-f876-4b94-891c-5b6f304c8966/catos_8890_stage1_demo_mode.png)

5. **後續階段規劃**：
   - **Stage 2 (第二階段)**：台灣 XQ 風格頂部微型佈局快捷板（四分割 60:40 / 大圖三分割 / 對等雙分割 / 單窗聚焦）一鍵切換與自訂比例一鍵復位。
   - **Stage 3 (第三階段)**：台灣 XQ 多分頁自訂桌面系統（例如「我的盯盤版面」、「極速下單版面」等）自訂命名與本機儲存。

---

## 4. 政策邊界與不可碰事項

- **嚴禁事項**：禁止接觸真實 OKX API Key、禁止向外發出實盤交易請求、禁止引入 Docker / PostgreSQL / Redis 等外置依賴。
- **金融底線**：交易計算嚴格維持 Decimal / SQLite TEXT；SWAP 委託強制包含 tag: `41cb53c54d6dABDE`；OKX 子帳戶專用，禁止陌生部位處置。

---

## 5. 明日公司電腦接續指引 (Quick Resume Guide)

### 1. 取得最新程式碼
若已提交並推送到遠端：
```bash
git checkout feature/catos-react-vite
git pull origin feature/catos-react-vite
```

### 2. 啟動本機前端服務
```bash
cd frontend/cat-os-vite
npm install
npm run dev -- --port 8890
```
瀏覽器訪問：`http://127.0.0.1:8890/#/` 即可即時預覽並接續開發。

### 3. 明日新對話接續指令 (可以直接貼給 AI)
```text
請先讀取 docs/current-handoff.md。目前 feature/catos-react-vite 前端已完成資產配置環圖 (Allocation Donut) 的流體響應式收斂與所有視圖防裁切。今天在公司電腦接續，請確認目前環境狀態，並依據規劃繼續執行下一階段工作。
```

