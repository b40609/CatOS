# catOS (Crypto Agent Trading OS)

> **專為 OKX 交易者量身打造的本地部署 AI 量化交易工作站**  
> **A Local, Agentic Quantitative Trading OS Engineered for OKX**

[![OKX Agent Trade Kit Builder](https://img.shields.io/badge/OKX-Agent%20Trade%20Kit%20Builder-black?logo=okx)](https://www.okx.com/zh-hans/agent-tradekit/builder)
[![Python 3.12](https://img.shields.io/badge/Python-3.12%2B-blue.svg?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: 100% Passed](https://img.shields.io/badge/Tests-39%2F39%20Passed-brightgreen.svg)]()

---

## 🌟 專案願景與定位 (Project Vision)

**catOS** 是一款開源、隱私安全、本地運行的量化交易操作系統，專為 OKX 專業衍生品交易者與社群用戶設計。透過開放式 **Model Context Protocol (MCP)** 協議，catOS 將交易者的交易直覺、自然語言構想無縫轉化為具備機構級風控、原生對齊 OKX 合約規則且能穩定過夜運行的量化機器人。

- **官方 Builder 計畫**：[OKX Agent Trade Kit Builder Program](https://www.okx.com/zh-hans/agent-tradekit/builder)
- **接入方式**：API Broker（用戶 100% 自主持有 OKX Demo / API Key，金鑰本地 AES-256-GCM 加密，絕不上傳任何伺服器）
- **專案使命**：大幅降低量化交易門檻，為 OKX 生態帶來高黏性活躍交易者與健康的手續費增量。

---

## 🚀 核心亮點 (Key Highlights)

### 1. 自然語言生成策略 (Natural Language to Strategy)
- 交易者無需具備深厚編程背景，只需以繁體中文或自然語言描述交易邏輯與指標條件（例如：「快線 5 均線金叉 20 均線開多，死叉開空，回撤 2% 標記價條件停損」）。
- 本地 AI Agent 自動編譯為符合開源規範的 Python 策略插件，具備宣告式參數表單（`params_schema`），即時動態渲染調節面板。

### 2. 開放式 MCP 協議 (Open MCP Architecture)
- 遵循 Model Context Protocol (MCP) 標準，無縫對接 Claude Desktop、Cursor、Gemini 等主流 AI 工具鏈。
- 拒絕特定廠商綁定（No Vendor Lock-in），交易者可自由更換最適合的大語言模型。

### 3. OKX 深度原廠整合 (Deep OKX V5 Integration)
- **原生純 Python 非同步連線**：全面吸納 OKX 原廠 `okx/agent-trade-kit` 風控精神，原生非同步直連 OKX V5 REST / WebSocket。
- **OKX 2026 最新 Multi-Trade 獨立子倉位相容**：底層架構全面預留獨立子倉位接口，杜絕策略間持倉互相干擾。
- **交易所端標記價條件停損 (`slTriggerPxType: "mark"`)**：開倉成交後原子化將條件停損單掛載於 OKX 撮合撮合引擎伺服器端，徹底杜絕本機斷電、斷網或程式崩潰時的爆倉黑天鵝。
- **帳戶實質槓桿硬上限風控 (`RiskEngine`)**：即時計算全帳戶持倉名義價值總和 / 帳戶總權益；開倉前瞻預估，一旦超出硬上限（如 2.0x、3.0x）強制拒絕新委託，平倉與停損委託 100% 白名單放行。
- **模擬盤安全護欄**：第一版強制鎖定 OKX 模擬盤（硬編碼帶入 `x-simulated-trading: 1` 標頭），絕對不碰實盤真錢，提供過夜無人值守驗證。

---

## 🛡️ 產品核心紅線 (Core Architectural Safeguards)

1. **AI 絕不下單**：AI 僅負責策略編寫、參數調優、代碼審查與回測分析。所有開倉、下單與平倉權限 100% 掌握在交易者與本機狀態機手中，AI / MCP 無權調用下單金鑰。
2. **單一交易對排他性**：同一永續合約（如 `BTC-USDT-SWAP`）同一時間只允許一台機器人處於運行狀態，避免邏輯衝突。
3. **OKX 手機 App 平倉同步**：交易者在手機 OKX App 手動平倉後，本機狀態機偵測持倉歸零自動同步轉為 `停機 · App 已平倉`，鎖死開倉權限，絕不二次反向開倉。
4. **標準專業交易術語**：全介面、日誌與代碼嚴格對齊 OKX App 專業術語與業界開源標準（CCXT / Jesse），嚴禁自創工程黑話。
5. **倉位名義價值 (Notional Value)**：下單金額一律以「倉位名義價值 (USDT)」定義（下單張數 = 倉位名義價值 / [標記價 × 合約面值]），非保證金概念。

---

## 📂 專案架構 (Project Structure)

```text
catOS_v1/
├── src/
│   ├── core/                  # 安全核心 (AES-256-GCM)、風控引擎 (實質槓桿)、機器人狀態機
│   │   ├── security.py        # 本地金鑰安全模組 (PBKDF2 + AES-GCM + 脫敏)
│   │   ├── risk_engine.py     # 實質槓桿硬上限風控引擎
│   │   └── state_machine.py   # 6 大生命週期狀態機與 OKX App 平倉同步
│   ├── exchange/              # OKX V5 原生非同步連線層
│   │   └── okx_client.py      # 模擬盤客戶端、V5 簽名、張數換算、標記價條件停損、市價全平
│   ├── plugins/               # 策略插件體系與熱加載沙盒
│   │   ├── base.py            # 策略基類 (對齊 Jesse 風格) 與 params_schema
│   │   ├── loader.py          # 動態加載器與例外隔離沙盒
│   │   └── strategies/        # 出廠雙試紙 (Signal Test 通道試紙、SMA 5/20 雙均線)
│   └── api/                   # (階段二) FastAPI 路由與 SSE 即時事件推播
├── tests/                     # 完整測試驅動套件 (39 項單元測試 100% 通過)
├── requirements.txt           # 純 Python 3.12 核心依賴 (無 Node.js 雜質)
└── 啟動catOS.bat               # 終端用戶雙擊一鍵拉起服務 (預留)
```

---

## 🧪 測試套件 (Test Suite)

catOS 採用嚴格的測試驅動開發 (TDD) 與架構接縫 (Seams) 設計，所有核心功能均具備自動化單元測試：

```bash
# 運行完整測試套件
pytest -v
```

```text
============================= 39 passed in 1.13s ==============================
✔ tests/test_okx_client_auth.py    - OKX V5 HMAC-SHA256 簽名向量與模擬盤強制標頭契約
✔ tests/test_okx_sizer.py          - 倉位名義價值與合約張數雙向精確無損換算
✔ tests/test_okx_orders.py         - 逐倉市價委託、標記價條件停損掛單與市價全平
✔ tests/test_security.py           - 本地 AES-256-GCM 加密防竄改與敏感資料脫敏
✔ tests/test_risk_engine.py        - 全帳戶實質槓桿計算與平倉白名單豁免
✔ tests/test_plugins.py            - 策略插件動態熱加載、例外隔離與出廠雙試紙
✔ tests/test_state_machine.py      - 標準 6 大狀態流轉、交易對排他防呆與 OKX App 平倉同步
```

---

## 🚀 快速上手 (Quick Start)

### 1. 安裝環境
無需安裝 Node.js，僅需 Python 3.12+：
```bash
git clone https://github.com/b40609/catOS_v1.git
cd catOS_v1
pip install -r requirements.txt
```

### 2. 執行驗證測試
```bash
pytest
```

---

## 📄 開源授權 (License)

本專案採用 [MIT License](LICENSE) 授權。  
Dedicated to the **OKX Agent Trade Kit Builder Program**.
