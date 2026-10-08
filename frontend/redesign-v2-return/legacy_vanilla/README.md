# catOS v1 Frontend Redesign (redesign-v1)

本目錄為 catOS v1 獨立重開發之前端原型與設計系統。
以「多面板量化交易工作區」為核心定位，拒絕空洞診斷清單，提供極致密度與專業交易終端質感。

## 目錄結構

```
frontend/redesign-v1/
├── index.html              # 主頁面：整合 Dashboard A/B 視角無縫切換
├── styles/
│   ├── theme.css           # Design Tokens、中性灰底色、低圓角、高可讀字體變數
│   ├── components.css      # 表格、按鈕、徽章、日損刻度儀表、Popover 等元件樣式
│   ├── layout-a.css        # 布局 A：多面板經典工作區 (Multi-Pane Workstation)
│   └── layout-b.css        # 布局 B：趨勢主導與待辦焦點 (Trend-First & Attention Hub)
├── js/
│   ├── app.js              # 主控制器：A/B 布局切換、場景監聽、響應式重繪
│   ├── charts.js           # 原生 Canvas/SVG 圖表 (平滑走勢圖、甜甜圈環形配置、曝險條)
│   ├── components.js       # 微互動：底座遙測 Popover、事件時間軸展開、長 ID 複製
│   ├── mock-adapter.js     # Mock 資料層與操作日誌 (保證導航/換頁不送出交易命令)
│   └── api-adapter-spec.js # 專為 Codex 撰寫之正式 API 與 DOM 映射對照規格
├── mock/
│   ├── models.js           # 金融不變量常量、Decimal 字串格式化、短 Hash 輔助
│   └── scenarios.js        # 四大場景資料 (正常運行、空資料待命、409 衝突、風控鎖存)
├── evidence/               # 瀏覽器實測畫面截圖與驗證證據
├── README.md               # 本說明檔
└── HANDOFF.md              # 視覺設計與切版交接指南
```

## 核心設計理念與不變量

1. **視覺風格**：
   - 深色中性灰底色（`#080a0f`, `#0c1017`, `#121824`）
   - 低圓角（2px - 4px）、精緻邊框（`1px solid var(--border-subtle)`）
   - 琥珀金/橙（`#f59e0b`）Accent 色，獨立語意色（買多綠、賣空紅、警示黃、通知藍）
   - 核心財務數值皆採用等寬數字字型棧（Tabular Numerals），排版整齊
   - 零外部 CDN、零第三方框架依賴，純原生 Web 技術

2. **金融與架構不變量**：
   - 所有資料契約數值均使用 Decimal 字串，嚴格禁止 float 計算
   - 所有 OKX 委託固定注入 `"tag": "41cb53c54d6dABDE"`
   - 1 合約 1 Bot 獨佔，部位未平倉且對帳未完成前不釋放
   - stopped / completed 不代表部位為 0，未平倉部位與合約獨佔明確保留（409 阻擋新案例）
   - 帳戶有效槓桿上限 3.0x，單幣曝險預算上限 50%
   - 日損以 Asia/Taipei 00:00 每日切日，Soft -10% 禁增倉，Hard -20% 清倉與 Kill-Switch

3. **Dashboard A/B 兩版對照**：
   - **布局 A（多面板工作區 Multi-Pane Workstation）**：
     - 上方 4 格 KPI：風控權益、當日損益、運行 Bot 數、有效槓桿與曝險預算
     - 中間 3 欄：30D 權益時序走勢、保證金配置甜甜圈圖、執行事件時間軸
     - 下方 4 欄：日損鎖存安全儀表軌道、機器人持倉隊列、近期研究成果、Yaozi 市場情報
   - **布局 B（趨勢主導 Trend-First & Attention Hub）**：
     - 上方主體：左側 68% 包含整合 Mini-KPI 帶與 60D 雙軸走勢大圖表；右側 32% 聚焦 Attention Hub（急迫待辦與人工處置中心）
     - 下方 3 欄：Bot 矩陣表格、單幣曝險橫向進度條（對比 50% 紅線上限）、策略成果與情報雷達
