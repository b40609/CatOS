# CatOS — Crypto Agent Trading OS

**把交易想法變成可驗證、可控執行的策略。**

CatOS 是結合 AI Agent 的本機加密貨幣量化交易工作台，面向希望自行開發、驗證與管理策略的交易者。以 OKX USDT 本位永續合約為首個交易場景，將策略製作、回測、參數探索與本機模擬整合為可追溯的工作流程。

AI 協助撰寫與研究策略；交易與資金管理則由明確的執行契約和風控規則承接。從策略版本、參數到研究結果，使用者都能逐步檢查，再決定是否進入下一個階段。

[核心特色](#核心特色) · [工程亮點](#工程亮點) · [功能與進度](#功能與進度) · [快速開始](#快速開始) · [文件](#文件)

> **專案階段**：持續開發中，目前以策略研究與本機模擬為主要交付範圍。Web 工作台持續串接後端；Demo／Live 分階段推進。

## 核心特色

| 特色 | 帶來的價值 |
| --- | --- |
| **AI Agent 輔助策略開發** | 透過 MCP 讀取策略契約、建立不可變版本與查詢模擬結果，讓人與 Agent 以共同介面協作。 |
| **可追溯的研究流程** | 保存策略識別、參數、輸入資訊與結果，方便重現試驗、比較版本及定位問題。 |
| **超越單次最佳回測** | 結合 Optuna、參數鄰域穩定度、滾動樣本外驗證與分市場環境評估，檢查策略的適用條件。 |
| **策略與交易職責分離** | Worker 計算訊號，Supervisor 統一管理交易路由、風控與寫庫，集中處理執行決策。 |
| **本機整合工作台** | 以 Python、SQLite 與瀏覽器介面整合研究及執行狀態，並朝同站整合可選的 Yaozi 市場情報模組。 |

產品流程涵蓋以下階段；實際支援範圍見下方進度表：

```text
交易想法 → 策略規格與版本 → 回測與參數驗證 → 本機模擬與對帳
                                                  ↓
                                    經授權的 Demo／Live（後續階段）
```

## 工程亮點

CatOS 將研究可重現性、金融計算與執行邊界落實到具體模組：

| 設計 | 實作重點 | 程式與文件 |
| --- | --- | --- |
| **Decimal 金融核心** | 金額、價格、部位與費用採 Decimal；SQLite 金融數值採 TEXT。Optuna 的衍生搜尋評分可轉 float，帳務依據維持 Decimal。 | [回測核心](catos/research.py) |
| **明示回測假設** | 已收盤 K 線決策、下一根開盤加滑價成交；預熱期只更新指標，成本與資金費事件由設定明示。 | [合成範例](examples/closed_bar_demo.py) |
| **策略程序分離** | 受信任的 Python Worker 透過 JSON IPC 傳遞意圖；執行、風控與持久化集中管理。 | [Supervisor](catos/supervisor.py) |
| **樣本外研究驗證** | 先在訓練窗選參，再固定參數評估後段資料，保留規則、失敗原因與完整結果。 | [驗證方法](docs/research-validation.md) |
| **Agent 工具介面** | 將策略版本建立與結果查詢封裝為 MCP 工具，沿用本機服務契約。 | [策略 MCP](catos/strategy_mcp.py) |

技術組成：**Python 3.11+ · React · TypeScript · Vite · SQLite WAL · Optuna · MCP**。核心部署不要求 Docker、PostgreSQL 或 Redis。

## 功能與進度

各項能力依研究、本機模擬與交易接入階段分別交付：

| 領域 | 目前提供的能力 | 交付範圍 |
| --- | --- | --- |
| 回測研究 | Closed Bar、預熱、Decimal 計算、成本模型、CSV 匯入與 HTML 報告 | 可由合成範例與 CLI 使用 |
| 參數探索 | Optuna 搜尋、明示搜尋空間與試驗紀錄 | 研究用途 |
| 策略驗證 | 參數鄰域穩定度、滾動樣本外、分環境評估與結果封存 | 已有後端實作與驗證紀錄；前端串接另計 |
| Agent 介面 | 研究 MCP、策略版本 MCP、本機模擬結果查詢 | 本機服務與既定工具契約 |
| 本機模擬 | 策略 Worker、執行狀態、帳務與風控模組 | local-sim；不等同交易所實盤驗證 |
| Web 工作台 | React／TypeScript 介面、研究與交易管理畫面 | 持續整合中；部分畫面仍使用模擬資料 |
| Yaozi 情報 | 可選市場情報模組與整合契約 | 依各模組資料來源及整合進度提供 |
| Demo／Live | OKX 執行、對帳與授權相關底座 | 分階段開發，尚未完整交付 |

## 架構

```text
使用者 / AI Agent
        │
        ├── Web 工作台
        └── MCP 工具
                │
         本機應用與研究服務
                │
         Supervisor ───── SQLite WAL
                │
             JSON IPC
                │
         Python 策略 Worker
```

- **Supervisor**：在應用職責上集中管理憑證、對外連線、交易、帳戶風控與 SQLite 寫入。
- **Worker**：載入使用者選定、經檢查的策略及依賴，傳回純資料訊號或目標意圖；不取得交易 client、憑證或寫庫介面。
- **研究核心**：借鑒 Jesse 的策略 API 風格，使用自有 Decimal 核心，不依賴完整 Jesse 套件。
- **前端**：React、TypeScript、Vite；以資訊密度與研究／執行狀態的可辨識性為設計方向。
- **情報整合**：Yaozi 與量化交易朝同一個 localhost 工作台整合；切換頁面不應控制策略生命週期。

Worker 採普通 Python 子程序與 JSON IPC，提供程序故障隔離，**不具備 OS 層惡意程式沙箱保證**。只應載入受信任的策略與依賴。

## 快速開始

### 1. 執行最小研究範例

需要 Git 與 Python 3.11 以上版本。在終端執行：

```powershell
git clone https://github.com/b40609/CatOS.git
cd CatOS
python -B -m examples.closed_bar_demo
```

此範例只使用合成 K 線及標準函式庫，輸出交易、資金費與績效的 JSON，不需要交易所 API Key，也不連線下單。

回測採「本根收盤決策、下一根開盤加明示滑價成交」；預熱期只更新指標，不執行交易決策。它是研究成交模型，不能代表盤中撮合、真實流動性或完整帳戶風控。

### 2. 探索參數搜尋

建議先建立專用虛擬環境，再安裝研究用依賴：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-research.txt
.\.venv\Scripts\python.exe -B -m examples.optuna_demo
```

此範例以合成資料執行 12 次試驗，示範搜尋流程；最佳樣本內分數不代表未來績效。

### 3. 延伸使用

- **CSV 與報告**：依[研究 CLI 文件](docs/research-cli.md)匯入資料、設定成本並產出報告。
- **研究驗證**：閱讀[穩定度與樣本外驗證](docs/research-validation.md)及[分環境評估](docs/research-regimes.md)。
- **Agent 整合**：研究橋接位於 [research_mcp.py](catos/research_mcp.py)，策略版本與結果工具位於 [strategy_mcp.py](catos/strategy_mcp.py)。需先準備相應本機服務；MCP 不是獨立交易引擎。
- **Web 開發**：前端位於 [frontend/cat-os-vite](frontend/cat-os-vite)。畫面、服務與資料基線的當前狀態請先查看[接續入口](docs/current-handoff.md)。

## 範圍與限制

- v1 交易設計聚焦 OKX USDT-M SWAP、cross 保證金與 net_mode；單一合約由單一 Bot 獨佔。
- 研究聚焦分鐘至小時級的已收盤 K 線，不以 1m 細部資料重播模擬所有盤中成交。
- 風控包含曝險限制、停止增倉與鎖存機制；具體政策及已接入階段以文件為準。
- 回測、研究完成或本機模擬通過，不構成 Demo／Live 的上線核准，也不保證策略獲利。

## 文件

| 文件 | 內容 |
| --- | --- |
| [架構設計](catOS-architecture-review.md) | 系統職責、策略介面與設計依據 |
| [目前接續入口](docs/current-handoff.md) | 最新開發狀態、已知限制與交付證據 |
| [研究 CLI](docs/research-cli.md) | CSV、回測設定與報告輸出 |
| [研究驗證](docs/research-validation.md) | 鄰域穩定度與滾動樣本外方法及限制 |
| [分環境評估](docs/research-regimes.md) | 市場環境分類與研究結果解讀 |
| [研究驗證 API](docs/research-validation-api.md) | 任務、結果與封存介面 |
| [風控期間基準](docs/risk-period-r1-local-sim.md) | R1 本機模擬的行為與邊界 |
| [Yaozi 整合](docs/catos-yaozi-integration.md) | 情報與交易工作台的整合契約 |

## 回饋與參與

歡迎透過 [Issues](https://github.com/b40609/CatOS/issues) 提出可重現的問題或具體功能建議。回報時請附上版本、執行步驟、預期行為與去除敏感資訊的輸出。

涉及帳務、交易授權或風控政策的提案，請先描述使用情境與行為影響，再討論實作。

## 授權

授權條款尚未指定；儲存庫目前沒有 LICENSE 檔案。
