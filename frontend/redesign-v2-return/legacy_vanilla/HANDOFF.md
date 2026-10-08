# catOS v1 前端視覺設計與 Dashboard A/B 原型交接手冊

- **更新日期**：2026-10-03
- **交付目錄**：`frontend/redesign-v1/`
- **對接角色**：本機 Codex（API/DOM 正式接入）、WorkBuddy（獨立驗收）
- **核心定位**：回歸舊版經典量化交易工作區完整度，提供布局 A（多面板工作區）與布局 B（趨勢主導）供使用者選擇。

---

## 一、Dashboard A/B 布局設計評估

| 評估維度 | 布局 A：多面板工作區 (Multi-Pane Workstation) | 布局 B：趨勢主導 (Trend-First & Attention Hub) |
| :--- | :--- | :--- |
| **視覺焦點** | 平鋪 3 層結構，資訊密度高，全盤均衡掌握。 | 大尺寸 60D 趨勢圖 (68%) 主導第一視野，強烈波段感。 |
| **頂部第一眼** | 4 格大字級 KPI 卡片（權益、損益、Bot 數、槓桿）。 | 整合型精簡 KPI 帶，為大圖表讓出最大垂直空間。 |
| **核心優勢** | 適合**日內多合約監控、高頻盤口盯盤**。同時看清資金、走勢、事件與持倉。 | 適合**中長線趨勢策略審查、異常焦點快速處置**。右側 Attention Hub 聚焦需人工介入之項目。 |
| **待辦與異常** | 分散於頂部狀態、事件流與隊列標籤中。 | 集中於右側 Attention Hub 卡片群（高亮呈現 409 衝突、日損距離、待信任審查）。 |
| **單幣曝險呈現** | 中間 SVG 甜甜圈圓環圖（環形比例）。 | 下方橫向進度條（直觀呈現 50% 單幣上限紅線）。 |

---

## 二、四大關鍵系統狀態視覺呈現規範

原型內建即時場景切換開關（Scenario Switcher），可一鍵切換驗證：

1. **正常運行 (Normal Running)**：
   - 頂部底座指示燈為綠色「底座連線正常 · 14ms」。
   - KPI 顯示完整金額（125,480.50 USDT、+1,240.80 USDT (+1.00%)、有效槓桿 1.85x）。
   - 日損安全儀表指針位於盈利安全區（+1.00%），標記距 Soft 緩衝 13,664.77 USDT。
   - 圖表繪出平滑金色漸層面積折線，Bot 隊列正常盈利。

2. **空資料待命 (Empty Standby)**：
   - 誠實呈現空狀態，**嚴禁偽造假數據或強制補零**。
   - 權益顯示 `— USDT`，損益顯示 `—`，有效槓桿顯示 `—`。
   - 圖表繪製基線與「尚無歷史權益點陣資料 (Standby)」提示。
   - Bot 隊列表格提示「尚無運行中的 Bot，請前往策略中心指派」。

3. **持倉停止 409 鎖定 (Stopped Position Retained - 409 Conflict)**：
   - 頂部彈出高亮紅底脈衝橫幅：`409 simulation_ownership_or_risk_retained`。
   - 頂部遙測燈亮紅燈，標示「底座 409 獨佔鎖定中」。
   - Bot 列表中 hold-01 狀態標記為 `STOPPED`，但部位方向清晰標記 `空 1.00 CONT`（紅底高亮）。
   - 嚴格承諾交易員：系統不隨 Worker 死亡釋放獨佔，不自動市價清倉，保障部位不失控。

4. **風控 Soft 鎖存 (Risk Recovery Required)**：
   - 當日損益達到 -10.50%（超越 -10.00% Soft 門檻）。
   - 日損安全儀表指針進入警戒區，標註「已觸發 Soft 鎖存 (禁增倉)」。
   - 風控狀態徽章顯示 `RECOVERY_REQUIRED`（紅底）。
   - 所有加倉或新增 Bot 操作進入 disabled 防護狀態，防止 CSS 繞過。

---

## 三、Codex 正式接入指南

請參閱 [js/api-adapter-spec.js](file:///c:/Users/kai/Desktop/CatOS_Astra/frontend/redesign-v1/js/api-adapter-spec.js) 進行 DOM 綁定與 API 串接：
- KPI 欄位綁定 `#kpi-a-equity`, `#kpi-a-pnl`, `#kpi-a-bots`, `#kpi-a-leverage`。
- 圖表 Canvas 綁定 `#chart-equity-canvas-a` (30D) 與 `#chart-equity-canvas-b` (60D)。
- 409 橫幅綁定 `#banner-409-alert`。
- 切換模式、刷新或換頁時，保證不送出任何真實交易控制命令（可由 `mockAdapter.getAuditLogs()` 驗證）。
