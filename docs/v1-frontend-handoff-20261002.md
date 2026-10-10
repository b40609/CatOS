# catOS v1 前端視覺設計與 Dashboard A/B 原型交接手冊

- **更新日期**：2026-10-03
- **負責角色**：Antigravity（視覺架構、Design System 與 Prototype 實作）
- **對接角色**：Codex（正式 HTML/JS/DOM 接入與功能狀態管理）、WorkBuddy（獨立驗收）
- **交付目標**：擺脫「開發交驗/診斷清單視角」，全面回歸舊版經典量化交易產品完整度（以第三張舊版截圖為標準），交付多面板工作區（A）與趨勢主導總覽（B）兩大高擬真獨立 Prototype。

---

## 一、交付概要與職責邊界

### 1. 核心定位與產品設計邊界
- **產品原型與接線能力之區分**：
  - 設計原型使用清楚標示的「產品原型 · 示意資料」，完整呈現目標產品 Dashboard 的資訊組織、圖表與交易視覺密度。
  - 「目前後端還沒有資料」不代表必須刪除圖表，或把整個模組縮成一行文字。
  - 正式介面依據資料來源情況展現：有來源顯示真實數據，無來源使用相同佈局之標準空狀態或開發中狀態。
  - 嚴格遵守金融與後端邊界：不據此擴充後端、不改金融政策、不接觸真實金鑰環境變數或對外實盤發單。
- **技術資訊退居次席**：
  - 首屏預設**不顯示**：原始 JSON、完整 SHA-256 Hash、build/instance、Worker exit code、IPC 與 Supervisor 架構細節。
  - 這些資訊統一收納至頂部「底座遙測狀態 Popover」與詳情抽屜中，點擊展開，不主導第一屏。
  - 取消密集英文技術副標，放大主要核心數字與內文，強化文字對比。

### 2. Antigravity 本輪具體交付成果
1. **共用 Design System 擴展**：[frontend/workspace/v1-theme.css](file:///c:/Users/user/Desktop/CatOS_Astra/frontend/workspace/v1-theme.css)（補充 Workstation 與 Trend-First 佈局之 Token 與元件樣式）。
2. **Dashboard 原型 A（多面板工作區 Multi-Pane Workstation）**：
   - 伺服路徑：`http://127.0.0.1:8899/prototypes/dashboard-prototype-a.html`
   - 本地檔案：[outputs/dashboard-prototype-a.html](file:///c:/Users/user/Desktop/CatOS_Astra/outputs/dashboard-prototype-a.html)
3. **Dashboard 原型 B（趨勢主導總覽 Trend-First Overview）**：
   - 伺服路徑：`http://127.0.0.1:8899/prototypes/dashboard-prototype-b.html`
   - 本地檔案：[outputs/dashboard-prototype-b.html](file:///c:/Users/user/Desktop/CatOS_Astra/outputs/dashboard-prototype-b.html)
4. **真實瀏覽器畫面驗收採證**：包含桌面版（1440px）、窄視窗（768px）、狀態切換與技術 Popover 展開截圖。

---

## 二、Dashboard A/B 佈局架構與實質差異對比

| 評估維度 | 原型 A：多面板工作區 (Multi-Pane Workstation) | 原型 B：趨勢主導總覽 (Trend-First Overview) |
| :--- | :--- | :--- |
| **視覺佈局核心** | 沿用舊版經典 3 層平鋪式佈局，緊湊均勻，全屏掌控。 | 兩欄主次視野，大趨勢走勢圖（68%）主導第一眼。 |
| **第一層（首要）** | 4 格核心 KPI 網格（總權益、損益、Bot 數、風控狀態）。 | 大視野權益曲線走勢圖 + 整合型 KPI 統計列。 |
| **第二層（次要）** | 三欄並排：走勢圖 (48%) + 保證金配置 (28%) + 事件時間軸 (24%)。 | 右側焦點監控與待辦事項 (Attention Hub 32%)。 |
| **第三層（摘要）** | 四欄並排：日損安全儀表 (34%) + Bot 隊列 (22%) + 研究 (22%) + Yaozi (22%)。 | 下方三欄：Bot 隊列表格 (38%) + 保證金條形配置 (32%) + 研究/Yaozi (30%)。 |
| **適用交易場景** | **高頻盯盤、多合約實盤監控**（一眼看清資金、走勢、事件與持倉）。 | **中長線波段策略審視、異常焦點處理**（先看大趨勢與急迫待辦）。 |

---

## 三、真實瀏覽器截圖驗收採證

本輪已透過本機 HTTP 伺服器（`127.0.0.1:8899`）使用無頭瀏覽器進行實際渲染驗收，產出實體截圖：

### 1. 原型 A（多面板工作區）畫面採證
- **桌面寬螢幕畫面 (1440x900)**：
  ![Prototype A Desktop](file:///C:/Users/user/.gemini/antigravity-ide/brain/0ce81a5f-30b3-45ce-974f-de8350dfe41e/prototype_a_desktop_1791027540562.png)
- **技術遙測 Popover 展開與狀態切換**：
  ![Prototype A Popover](file:///C:/Users/user/.gemini/antigravity-ide/brain/0ce81a5f-30b3-45ce-974f-de8350dfe41e/prototype_a_popover_1791027663957.png)
- **窄視窗自適應畫面 (768px)**：
  ![Prototype A Narrow](file:///C:/Users/user/.gemini/antigravity-ide/brain/0ce81a5f-30b3-45ce-974f-de8350dfe41e/prototype_a_narrow_1791027733218.png)

### 2. 原型 B（趨勢主導總覽）畫面採證
- **桌面寬螢幕畫面 (1440x900)**：
  ![Prototype B Desktop](file:///C:/Users/user/.gemini/antigravity-ide/brain/0ce81a5f-30b3-45ce-974f-de8350dfe41e/prototype_b_desktop_1791027782597.png)
- **持倉停止 409 鎖定狀態響應**：
  ![Prototype B 409 State](file:///C:/Users/user/.gemini/antigravity-ide/brain/0ce81a5f-30b3-45ce-974f-de8350dfe41e/prototype_b_state_change_1791027818716.png)
- **窄視窗自適應畫面 (768px)**：
  ![Prototype B Narrow](file:///C:/Users/user/.gemini/antigravity-ide/brain/0ce81a5f-30b3-45ce-974f-de8350dfe41e/prototype_b_narrow_1791027843770.png)

---

## 四、各模組使用目的與視覺職責清單

| 模組名稱 | 使用目的 (Why it exists) | 關鍵回答 (First-screen Question) | 視覺呈現與互動方式 |
| :--- | :--- | :--- | :--- |
| **1. 帳戶核心概況 (KPI)** | 即時提供帳戶全局資金、損益與整體風控水位。 | 我帳戶總共有多少錢？今日賺或賠多少？目前槓桿倍數安全嗎？ | 4 張卡片，大字級金額（19px JetBrains Mono），清楚標明時間範圍與幣種（USDT）。 |
| **2. 帳戶淨值走勢 (Equity Curve)** | 追蹤策略組合的資產成長曲線與回撤軌跡。 | 近期 7D/30D/90D 的資產淨值曲線是穩健向上還是處於回撤？ | SVG 平滑折線與金色漸層面積光澤，時間軸刻度與座標，附帶撮合基準備註。 |
| **3. 保證金與曝險配置 (Allocation)** | 監控帳戶保證金佔用結構與未佔用可用水位。 | 多少保證金被 BTC/ETH 佔用？在途委託凍結了多少？風控緩衝是否足夠？ | SVG 甜甜圈圓環圖（A 版）或橫向進度條（B 版），滑鼠懸浮高亮，圖例清楚列出數值與佔比。 |
| **4. 重要事件時間軸 (Incident Stream)** | 即時通報撮合滑價、風控告警與策略生命週期變更。 | 剛剛發生了什麼關鍵事件？是否有滑價異常或外部訊號更新？ | 時間軸清單，WARN/INFO/DANGER 彩色膠囊，點擊就地展開詳細原因。 |
| **5. 日損鎖存安全儀表 (Risk Latch Gauge)** | 監控盤中浮動損益與 Soft/Hard 日損鎖存門檻之安全距離。 | 距 Soft 禁增倉 (-10%) 還差多少？目前是在安全盈利區還是回撤警戒區？ | 4 態橫向刻度軌道（Hard/Soft/基準/盈利），即時指針與氣泡提示，明確標示安全緩衝金額。 |
| **6. 運行中機器人 (Active Bots Fleet)** | 掌握個別 Bot 的即時持倉方向、損益與是否需要人工處置。 | 哪支 Bot 正在賺錢？哪支 Bot 接近風控邊界需要補保證金？ | 清單/表格，標明合約、多空方向、浮動損益、狀態徽章與前往 Bot 管理快捷鍵。 |
| **7. 近期研究任務 (Research Queue)** | 呈現離線回測、參數網格優化或外部 Agent 生成之研究成果。 | 昨晚的回測跑完了嗎？夏普值與淨利表現如何？ | 進度條、夏普值、淨利百分比、完成徽章，點擊前往回測庫。 |
| **8. Yaozi 市場情報 (Yaozi Intel)** | 接收資金費率偏離與鏈上巨鯨異動等宏觀情報參考。 | 市場是否有異常的資金費率飆升或鏈上突發轉帳？ | 標明「研究參考 · 開發中」，提供時間與情報標題，不干涉交易生命週期。 |

---

## 五、示意欄位與現行欄位對照表（Field Mapping）

| 模組 | 原型展示欄位 | 示意數值範例 | 現行後端 / 資料契約對照 | 目前狀態 | 備註說明 |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **KPI** | 總權益淨值 | `125,480.50 USDT` | `data.risk.totalAccountEquity` / `E_verified` | **已有** | 現行本地模擬為短程合成，待接真實帳戶資產估值 API。 |
| **KPI** | 今日損益 | `+1,240.80 USDT (+1.00%)` | `data.risk.dailyLoss` / 日初基準差額 | **已有** | 依據 Asia/Taipei 00:00 切日計算已實現與未實現損益。 |
| **KPI** | 運行 Bot 數 | `1 運行中 · 1 需處理 · 1 已停止` | `data.bots[].status` 統計 | **已有** | 區分 RUNNING、WARNING 與 STOPPED。 |
| **KPI** | 風控槓桿 | `1.85x / 上限 3.00x` | `data.risk.effectiveLeverage` / `maxAllowedLeverage` | **已有** | 嚴格符合 3.0x 槓桿契約，數值以 Decimal 存取。 |
| **走勢圖** | 權益時序數據 | 30 天每日淨值點陣 | 尚無時序儲存 API（目前僅短程 8 根 Bar 終態） | **尚缺** | **設計提案**：需由 Supervisor 或 SQLite 記錄日結淨值時序。 |
| **配置** | 保證金與曝險 | 總曝險 1,420.50 / 上限 3,000 | 總名義曝險 = 有效槓桿 × 風控權益；單幣上限 50% | **部分** | **設計提案**：需在 Supervisor 新增多幣保證金快照 API。 |
| **時間軸** | 事件日誌清單 | `11:10:02 WARN ETH 滑價 2.8 bps` | `data.meta.incidents[]` / SQLite 審計軌跡 | **已有** | 現行已有 Incident 結構，原型增強了就地展開功能。 |
| **日損儀表**| 日初基準 / 浮虧 | 基準 1000 / 當前 +18.42 | 日初權益分母、Soft (-10%)、Hard (-20%) | **已有** | 風控鎖存規則完備，Soft/Hard 閾值與 Latch 狀態明確。 |
| **Bot 隊列** | 部位方向與張數 | `BTC-USDT-SWAP 多 0.20 BTC` | `data.bots[].position.direction`, `amount` | **已有** | 嚴格遵守「stopped 不等於空倉」規則，409 鎖定狀態明確。 |
| **研究任務** | 夏普值與撮合數 | `Sharpe 2.14, 淨利 +36.84%` | 現行研究核心 Decimal 計算結果 | **已有** | 支援 warmup_bars，計算維持 Decimal。 |
| **Yaozi** | 市場情報快訊 | `[待確認: 費率偏離] BTC 資金費率` | 獨立情報模組交付 | **開發中** | 同一 localhost 交付，分頁隔離，不控制交易生命週期。 |

---

## 六、正式接入所缺的資料清單（Codex 接入需求）

Codex 在將本設計接入正式前後端時，需補充或對接以下 4 項後端 API / 資料契約：

1. **即時帳戶權益時序 API (`/api/v1/telemetry/equity_curve`)**：
   - **所缺內容**：提供 7D、30D、90D 的帳戶整體權益歷史時間序列。
   - **約束條件**：**絕對禁止將不同隔離測試案例串接為一條帳戶權益曲線**。必須是真實帳戶或指定持續模擬環境的淨值時序點。
2. **保證金與曝險快照 API (`/api/v1/risk/margin_allocation`)**：
   - **所缺內容**：返回當前帳戶持倉保證金（分幣種）、在途委託凍結保證金、未佔用可用保證金、以及依據 3.0x 槓桿與 50% 單幣占比計算的總名義曝險預算。
3. **Bot 實時持倉與異常原因 API (`/api/v1/bots/fleet_status`)**：
   - **所缺內容**：除現有的 RUNNING / STOPPED 狀態外，需傳回 `attention_reason`（例如：價格逼近網格上限、滑價偏高、保證金率偏低）以及精確的持倉合約與張數（防止停止後隱蔽持倉）。
4. **日損鎖存即時軌道 API (`/api/v1/risk/latch_status`)**：
   - **所缺內容**：傳回日初權益分母、當日最低回撤值（用於標記 Latch 鎖存原因）、當前浮動損益、Soft 門檻值與 Hard 熔斷值。

---

## 七、四大關鍵系統狀態視覺呈現規範

原型中已內建互動切換器，展示 4 大核心狀態之具體表現：

### 1. 正常連線狀態 (Normal Connected)
- **頂部遙測**：綠色指示燈，顯示「底座連線正常 · 16ms」。
- **KPI**：總權益顯示即時金額（例：125,480.50 USDT），損益顯示綠色正值，風控顯示 `NORMAL` 綠色徽章。
- **日損儀表**：指針位於綠色盈利安全區（+1.84%），標註「安全運行中」。
- **Bot 隊列**：RUNNING 綠色徽章，顯示即時盈利。

### 2. 空資料待命狀態 (Empty Standby)
- **頂部遙測**：灰色指示燈，顯示「底座就緒 · 待命中」。
- **KPI**：總權益顯示 `— USDT`，今日損益 `0.00 USDT`，Bot 數 `0 運行中`，風控 `STANDBY`。
- **日損儀表**：指針置中於基準 0.0%，標明「尚未指派 Bot」。
- **圖表與隊列**：走勢圖顯示基線，Bot 隊列提示「目前尚無部署的 Bot，請前往策略中心指派」，**不顯示假數值或偽造圖表**。

### 3. 持倉停止與 409 衝突狀態 (Stopped with Position Retained - 409 Locked)
- **頂部遙測**：黃色警示，提示「409 獨佔鎖定中」。
- **Attention Hub (B 版) / KPI (A 版)**：高亮紅色告警橫幅，明確標註：「Bot 手動停止但仍保留部位 (-1 張)，合約獨佔未釋放，409 阻擋新案例啟動」。
- **隊列呈現**：Bot 狀態顯示 `STOPPED`，但部位方向清晰標記 `空 1.00 張`（紅底高亮），右側操作提供「人工處置 / 平倉」按鈕。
- **安全承諾**：明確向交易員展示「系統不自動市價清倉、不隨 Worker 死亡釋放獨佔」。

### 4. 服務異常 / 需人工檢查狀態 (Service Recovery / Unknown)
- **頂部遙測**：紅色指示燈，顯示「需人工檢查 · 409」。
- **KPI**：損益顯示 `UNKNOWN`（紅色），風控顯示 `RECOVERY_REQUIRED`（紅色徽章）。
- **日損儀表**：指針退縮至左側警戒端，標記「來源代碼漂移 / 需核對基線並重啟本機服務」。
- **操作防護**：所有新增下單與指派按鈕處於 Disabled 狀態，防止在不確定環境中加劇風險。

---

## 八、原型完整原始碼歸檔

兩個自含可渲染原型檔案已同步部署至以下位置，供 Codex 開發人員與 WorkBuddy 驗收人員隨時查閱與提取：

- **原型 A (多面板工作區)**：
  - 倉庫位置：[outputs/dashboard-prototype-a.html](file:///c:/Users/user/Desktop/CatOS_Astra/outputs/dashboard-prototype-a.html)
  - 靜態託管位置：[C:\Users\user\Desktop\catOS-Frontend-Final\prototypes\dashboard-prototype-a.html](file:///C:/Users/user/Desktop/catOS-Frontend-Final/prototypes/dashboard-prototype-a.html)
- **原型 B (趨勢主導總覽)**：
  - 倉庫位置：[outputs/dashboard-prototype-b.html](file:///c:/Users/user/Desktop/CatOS_Astra/outputs/dashboard-prototype-b.html)
  - 靜態託管位置：[C:\Users\user\Desktop\catOS-Frontend-Final\prototypes\dashboard-prototype-b.html](file:///C:/Users/user/Desktop/catOS-Frontend-Final/prototypes/dashboard-prototype-b.html)
