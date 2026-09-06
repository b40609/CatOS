# AGENTS.md

Welcome to catOS V1. This document defines the engineering guidelines, domain boundaries, and agent skills configuration for this repository.

## 專案負責人與角色 (User & Role)

- **User**: Kai（交易者，OKX KOL，台灣，具備軟體與 Vibe coding 基礎，非全職軟體工程師）。
- **溝通語言**: 繁體中文。嚴格對齊 OKX App 標準專業用語與業界 GitHub 開源量化專案標準用詞（如 CCXT、TradingView、Jesse）。**嚴禁自創工程黑話**。
- **唯一最高規格憲法**: 根目錄的 [catOS_V1.md](catOS_V1.md)。所有架構設計與實施必須 100% 符合其規範。

---

## 核心架構共識（方案 A 定案）

1. **後端架構**：單一 Python 3.12 (FastAPI) 進程，拒絕多進程碎片。
   - **策略與回測大腦**：對齊 Jesse 策略物件語法（should_long、go_long），後端內嵌 jesse.research 高精度回測規格（杜絕前視偏差、8h 資金費率結算、精確滑點）。
   - **執行與風控**：純 Python 原生 OKX 模擬盤/期貨執行器（吸納 OKX 官方 Agent Trade Kit 精神：合約張數自動換算、標記價條件停損、實質槓桿硬上限拒單）。
2. **前端狀態**：**目前尚未定案，保留開放**。後端以 REST API + SSE 事件流提供通用接口，預留 src/web/ 供未來靜態託管。
3. **出廠雙試紙**：Signal Test 通道驗證試紙、SMA 5/20 雙均線試紙。

---

## 產品核心紅線（不得違背）

1. **唯一通道**：第一版只准連接 **OKX 模擬盤**（Demo API Key，強制帶 x-simulated-trading: 1 標頭），絕對不碰實盤真錢，不跑純紙上虛擬撮合。
2. **AI / MCP 不能下單**：AI 負責生成、調參、安裝策略插件與回測，但**絕不下單、不動金鑰、不觸發全平**。下單與平倉權限 100% 掌握在交易者與本機狀態機手中。
3. **交易所標記價條件停損**：停損單必須掛在交易所端（標記價觸發市價平倉），不在本機記憶體軟止損；留白代表不掛停損。
4. **同一交易對排他性**：同一合約（如 BTC-USDT-SWAP）同一時間只允許一台機器人處於運行中。
5. **OKX App 狀態同步**：交易者在手機 OKX App 手動平倉後，機器人自動同步轉為 停機 · App 已平倉，絕不二次反向開倉。
6. **語言與術語標準**：
   - 全專案（UI、日誌、代碼與對話）嚴格對齊 OKX App 標準專業交易術語與業界開源量化標準用詞（如 CCXT、TradingView、Jesse），**嚴禁自創工程黑話**。
   - 機器人生命週期標準狀態術語：待機、載入中、運行中、異常 · 連線中斷、停機 · 策略運算錯誤、停機 · App 已平倉。

---

## 工程工作流規範 (Matt Pocock's Skills)

本專案全面採用安裝於 .agents/skills/ 的 Matt Pocock 正統工程工作流：

1. **需求訪談與對齊**：使用 /grill-with-docs 或 /grilling 深入確認需求。
2. **規格擬定**：使用 /to-spec 撰寫規格書至 .scratch/。
3. **任務分解**：使用 /to-tickets 將規格拆解為 Tracer-bullet 任務票。
4. **嚴謹實施**：使用 /implement（內含 /tdd 測試驅動與 /code-review 代碼審查）。
5. **疑難排錯**：使用 /diagnosing-bugs（最小化重現 ➔ 假設 ➔ 驗證 ➔ 修復）。
6. **流程指引**：不確定下一步時使用 /ask-matt。

---

## 終端交付標準

終端用戶在 Windows 本機雙擊 啟動catOS.bat，即可一鍵拉起後端服務並在預設瀏覽器打開控制台，**終端電腦無需安裝 Node.js**。
