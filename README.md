# CatOS (Crypto Agent Trading OS)

> **CatOS（Crypto Agent Trading OS）是一個開發中的本機加密貨幣量化交易工作台，結合 AI Agent 輔助策略開發、回測驗證與受控執行。**  
> 以 OKX 永續合約（USDT-M SWAP）為首個交易場景，目標是讓個人交易員在同一工作環境中，把交易想法逐步轉化為可追溯、可驗證的自動化策略，並集中管理風控與執行狀態。目前以策略研究與本機模擬為主要交付階段。

[![Python Version](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Frontend](https://img.shields.io/badge/Frontend-React%2019%20%7C%20TypeScript%20%7C%20Vite%20%7C%20Tailwind-61dafb.svg)](frontend/cat-os-vite)
[![Database](https://img.shields.io/badge/Database-SQLite%20(WAL%20Mode)-success.svg)](catos/journal.py)
[![Precision](https://img.shields.io/badge/Financial%20Core-Strict%20Decimal%20(Zero--Float)-orange.svg)](catos/research.py)

---

## 核心產品訴求：把交易想法變成可驗證、可控執行的策略

在傳統量化研發中，交易員常常需要在多個互不連貫的工具之間痛苦切換：在 TradingView 看指標、在 Python 寫回測、在 Excel 算手續費、在交易所網頁手動下單。

**CatOS 的核心價值，是把「研究、策略機器人、帳戶風控與市場情報」放進同一個連貫的本機工作台**，串起這條完整的策略生命週期：

```mermaid
flowchart LR
    A["交易想法 / 策略素材\n(Pine / 截圖 / 邏輯假說)"] --> B["明確策略規格\n(受信策略契約)"]
    B --> C["無狀態策略程式\n(Python Worker)"]
    C --> D["回測與參數驗證\n(Decimal / Optuna / OOS)"]
    D --> E["本機模擬與對帳\n(Local-Sim / S3-S10)"]
    E --> F["受控 OKX 執行\n(Supervisor 唯一出口)"]
    F --> G["全天候風控與追蹤\n(R1 台北切日 / P6 災難防線)"]
```

---

## 真正值得對外展現的五大核心賣點

| 核心賣點 | 對交易員的實質價值 |
|---|---|
| **AI 協助把想法變成可驗證的策略** | 從自然語言、TradingView / Pine Script 或市場邏輯開始，逐步形成明確規格、程式與研究結果，大幅降低反覆轉換工具的摩擦成本。 |
| **研究到執行的連貫工作流程** | 設計上讓同一無狀態策略製品走過回測、模擬與實盤階段，保留版本指紋、參數與研究來源快照，杜絕回測與實盤行為脫節。 |
| **策略與資金權限嚴格分離** | 策略子進程僅負責提出純數據訊號（Target Intent），由統一的 Supervisor 判定風控並獨佔交易出口，AI 產出絕不直接取得交易所下單權。 |
| **重視結果可信度（Zero-Float）** | 全鏈路 Decimal 金融計算、明示手續費與滑價模型、樣本外（OOS）滾動驗證與參數鄰域穩定度分析，幫助交易員客觀辨識漂亮回測背後的過擬合限制。 |
| **本機整合工作台（Zero-Waste）** | 在自己的電腦集中管理策略、持倉、曝險及事件；融合 Yaozi 作為同站可選情報模組，免除微服務運維負擔，頁面切換或關閉瀏覽器絕不中斷策略。 |

---

## 現行交付階段與工程邊界

目前整合基線與限制以[接續入口](docs/current-handoff.md)及[整合交付](docs/integration-baseline-20261024.md)為準。主頁／Bot／風控仍是明示展示資料；回測與優化已接合成研究 HTTP。以下能力包含 Python／local-sim 層，不能解讀為整站已完成對接或 Demo／Live 已就緒。

- **現階段已交付（Phase 1: 研究核心與本機模擬）**：
  - 高精度 Closed Bar 策略回測引擎（支援 `warmup_bars` 預熱期隔離）。
  - Optuna 多維超參數搜尋、參數鄰域穩定區檢驗與離線 HTML 互動報告。
  - 分市場環境評估（Regimes：趨勢／震盪／高波動損益歸屬）與樣本外（OOS）滾動驗證。
  - Supervisor-Worker 雙進程 JSON IPC 隔離與 SQLite（WAL）原子帳本。
  - S3–S10 逐筆帳務流水、Virtual Lots 虛擬批次與成交更正重放證明。
  - Zero-Waste 純資料密度 React 19 戰情工作台（Dock as Tab 容器、TradingView 風格同心圓 HUD 甜甜圈資產曝險圖）。
- **後續階段推進（Phase 2: OKX Demo / Live）**：
  - OKX 實盤對帳閘門、P6 交易所端整倉災難停損託管與環境平滑切換，持續依安全矩陣演練與驗收。

---

## 雙引擎智慧體生態

CatOS 採用雙主軸協同設計，所有功能集中於同一本機站點，切換分頁或關閉瀏覽器絕不影響後端交易生命週期：

```mermaid
flowchart LR
    subgraph CatOS["CatOS (Crypto Agent Trading OS)"]
        direction TB
        subgraph Quant["量化交易核心 (Quant Engine)"]
            Research["策略研究與回測"]
            Supervisor["Supervisor 資金守護者"]
            Risk["R1/P6 機構級風控"]
            Exec["OKX SWAP 唯一交易出口"]
        end
        subgraph Yaozi["Yaozi 市場情報雷達 (Yaozi Intel)"]
            Social["社群情緒與 KOL 輿情 (X/Twitter)"]
            Flow["Smart Money 大戶資金流"]
            Arb["跨所資金費率套利哨兵"]
            Surface["多市場決策曲面 (Decision Surface)"]
        end
        Terminal["React 19 + Vite 專業戰情工作台 (Port 8890 / 8770)"]
    end
    Terminal <--> Quant
    Terminal <--> Yaozi
    Quant <==>|Signed REST / WS| OKX["OKX 永續合約 (USDT-M SWAP)"]
```

- **量化交易核心**：負責分鐘至小時級已收盤 K 線策略回測、參數優化、多市場環境評估、Supervisor-Worker 雙進程隔離執行，以及單合約獨佔的訂單生命週期管理。
- **Yaozi 市場情報雷達**：負責整合多源外部情報——包含 X (Twitter) 社群輿情指數、OKX/Binance 資金費率偏離套利監控、巨鯨大額轉移警報與決策曲面（Decision Surface），為策略決策提供情報加權。

---

## 終端產品功能矩陣（十大戰情工作台）

CatOS 前端採用現代化 React 19 + TypeScript + Vite + Tailwind CSS 構建，為交易員提供十個專屬的專業工作台：

| 工作台 | 功能名稱 | 核心產品能力與交易員價值 |
|---|---|---|
| **01** | **戰情總覽 (Dashboard)** | **Zero-Waste 核心戰情室**。搭載 Dock as Tab 自由拖曳分割容器、TradingView 風格同心圓 HUD 甜甜圈資產曝險圖、即時帳戶權益帶、即時持倉盈虧與高頻成交流動態。 |
| **02** | **策略中心 (Strategy Hub)** | **智慧體策略倉庫**。支援 TradingView / Pine Script 指標轉接、策略模板管理與無狀態 Python 策略製品版本控制。 |
| **03** | **歷史回測 (Backtesting Lab)** | **高精度 Closed Bar 回測**。嚴格遵循 `warmup_bars` 預熱期指標隔離、撮合滑價與市價手續費模型、完整歷史資金費結算、交互式權益與水下拉回（Drawdown）圖表。 |
| **04** | **參數優化 (Optimization Studio)** | **Optuna 驅動超參數調優**。支援多目標搜尋、TPE 採樣、參數鄰域穩定區（Neighborhood Stability）檢驗，有效杜絕歷史過擬合陷阱。 |
| **05** | **策略覆盤 (Strategy Review)** | **分市場環境評估（Regimes）**。將歷史行情切片為趨勢、震盪、高波動等不同市場環境，驗證策略在不同環境下的損益歸屬與樣本外（OOS）滾動表現。 |
| **06** | **機器人管理 (Bot Manager)** | **執行個體生命週期控制**。實踐「One Bot, One Contract」單合約獨佔原則，提供在途訂單狀態機追蹤、一鍵啟停與緊急市價平倉（Emergency Flatten）。 |
| **07** | **風控中心 (Risk Control)** | **機構級資本守護樞紐**。即時監控 R1 台北切日損益曲線、有效槓桿倍數（Effective Leverage）、Soft/Hard 熔斷狀態機、手動 Kill-Switch 與 P6 交易所災難停損託管。 |
| **08** | **市場情報 (Market Intel - Yaozi)** | **全天候情報監控雷達**。整合 OKX 永續大額多空清算告警、跨所（OKX vs Binance）資金費率偏離套利機會、鏈上巨鯨動向與多空情緒矩陣。 |
| **09** | **系統日誌 (System Logs)** | **全鏈路審計與日誌追蹤**。即時監控 Supervisor 與 Worker 之間的 JSON IPC 封包、訂單狀態機跳轉流水與金融帳本交易重播日誌。 |
| **10** | **系統設定 (Settings)** | **環境與偏好配置**。管理 OKX 專用子帳戶 API 金鑰、配置帳戶有效槓桿上限與單幣預算占比、切換模擬與實盤環境。 |

---

## 核心技術與金融安全防線

### 1. 全鏈路零浮點保證（Zero-Float Financial Core）
- 所有金額、價格、部位、保證金、手續費與資金費，全流程強制使用 Python `Decimal` 與 SQLite `TEXT` 存儲與計算。
- **全面禁止 `float`** 計算，避免 IEEE 754 精度漂移導致的對帳不平或錯誤平倉。

### 2. Supervisor / Worker 進程安全隔離
- **Supervisor（主行程）**：獨佔 API 憑證、外部連網、OKX 唯一交易出口、風控狀態機與 SQLite WAL 唯一寫入權限。
- **Worker（策略子進程）**：無網路連線權限、無 API 金鑰、無資料庫寫入權，僅透過標準 JSON IPC 接收已收盤行情並回傳目標意圖（Target Intent），從架構上杜絕策略越權。

### 3. 機構級風控三重保障
- **R1 固定風控期間基準（Risk Period Benchmark）**：依 Asia/Taipei 每日 00:00 切日建立固定 E0 權益基準，精確計算日損；Soft 止增倉 (-10%) 與 Hard 清倉 (-20%) 一旦觸發立即鎖存（Latch），反彈或入金絕不自動解除，僅限人工核驗後 re-arm。
- **P6 交易所端整倉災難停損防線**：OKX 伺服器原生條件單託管，向上/向下取整（Ceil/Floor）以確保提早觸發，作為主機離線或斷網時的最後一道物理保險。
- **專用子帳戶與專用合作通道**：所有 OKX SWAP 委託由 Supervisor 強制靜默注入專屬通道標籤，專用子帳戶嚴禁與手動交易混用。

### 4. 虛擬批次與逐筆帳務（Virtual Lots & Ledger）
- S3–S10 逐筆帳務流水支援單筆訂單精確歸屬至 Virtual Lot，具備完整 USDT 手續費核算與成交更正重放證明（Correction Replay Proof）。

---

## 專案結構導覽

```text
CatOS/
├── catos/                     # 後端 Python 核心架構
│   ├── core/                  # Decimal 算術、合約規格、事件定義
│   ├── research/              # Closed Bar 回測引擎、指標庫、撮合模型
│   ├── optimization/          # Optuna 參數搜尋、鄰域穩定度、樣本外驗證
│   ├── supervisor/            # Supervisor 行程、帳本持久化、IPC 管理
│   ├── risk/                  # R1 台北日損風控、P6 災難停損、曝險預算
│   ├── execution/             # OKX SWAP 簽名器、交易出口、FakeExchange
│   └── market_*.py            # Yaozi 市場情報系統 (社交情緒、資金流、決策曲面)
├── frontend/cat-os-vite/      # React 19 + TypeScript + Vite 戰情終端
│   ├── src/
│   │   ├── pages/             # 十大核心戰情工作台頁面 (Dashboard, Bots, Risk...)
│   │   ├── components/catos/  # 終端核心組件 (Shell, WorkspaceGrid, HUD Donut)
│   │   ├── state/             # Zustand 全域狀態 (Layout, Market, Sidebar)
│   │   └── services/          # WebSocket & REST API 客戶端
│   └── package.json
├── docs/                      # 深度架構白皮書、風控政策與驗收規範
│   ├── catOS-architecture-review.md     # 核心架構白皮書
│   ├── catos-yaozi-integration.md       # 量化交易 / Yaozi 整合契約
│   ├── retail-v1-simplification-*.md    # R1 風控政策定義
│   └── disaster-stop-policy.md          # P6 災難停損規範
├── examples/                  # 回測示範、合成資料與 Optuna 範例
└── tests/                     # 300+ 項高覆蓋率自動化單元與整合測試
```

---

## 快速啟動指南

### 環境需求
- **Python**：3.11 或以上（支援 `sqlite3` WAL 模式）
- **Node.js**：18.0 或以上（前端工作台構建）

產品名稱為 `CatOS`；主目錄已於 2026-10-25 由 `CatOS_Astra` 更名為 `CatOS`。`_Astra` 後綴僅反映開發期使用的 ASTRA 模型，並非產品命名的一部分。`CatOS_Yaozi` 仍獨立開發。Windows 可執行根目錄 `start-laptop-dev.bat`；腳本會核對 8890 身分與就緒狀態，遇其他 owner 不接管。手動啟動如下。

### 1. 啟動前端專業戰情工作台

```bash
# 進入前端目錄
cd frontend/cat-os-vite

# 安裝依賴
npm ci

# 啟動 Vite 開發伺服器（監聽 http://127.0.0.1:8890）
npm run dev
```

在瀏覽器造訪 `http://127.0.0.1:8890`，即可體驗 Zero-Waste 純資料密度戰情操作台。

### 2. 啟動後端量化與情報工作台 API

```bash
# 在專案根目錄安裝 HTTP／研究依賴，再啟動 API（127.0.0.1:8770）
python -m pip install -r requirements-http.txt
python -B -m catos.workspace_api
```

### 3. 執行策略回測與報告生成

```bash
# 執行合成 15 分鐘 K 線 SMA 策略回測
python -B -m examples.closed_bar_demo

# 生成離線 HTML 互動回測報告
python -B -m examples.report_demo
```

### 4. 執行 Optuna 參數調優

```bash
# 執行多目標超參數搜尋與穩定區分析
python -B -m examples.optuna_demo
```

### 5. 執行自動化測試套件

CatOS 擁有超過 300+ 項高覆蓋率的自動化單元與整合測試，覆蓋 Decimal 算術、訂單狀態機、風控熔斷、對帳大閘與 IPC 序列化：

```bash
# 執行全量測試
python -B -m unittest discover -s tests -v
```

---

## 安全邊界與合規保證

1. **無真實金鑰洩漏**：開源代碼庫中僅包含假資料（Synthetic Fixture）與 Mock 實作，不包含任何真實 OKX API 金鑰或環境變數。
2. **受信策略邊界**：Worker 進程預設僅授予計算純訊號之權限，不提供 OS 任意命令或外部 URL 連線代理。
3. **單向資料流**：所有對外交易請求皆必須經過 Supervisor 風控檢查閘門，杜絕任何繞過風控的事後交易。

---

## 授權條款

目前專案根目錄未提供 LICENSE 檔；本次未新增或變更授權條款。

