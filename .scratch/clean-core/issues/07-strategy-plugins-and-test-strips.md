# 07: 策略插件介面、熱加載沙盒與出廠雙試紙 (Strategy Plugins & Test Strips)

**What to build:**
實作策略插件體系：
1. `src/plugins/base.py`：定義 `StrategyBase` 抽象類別，對齊 Jesse 策略風格（`should_long`、`should_short`、`go_long`、`go_short`），並包含 `params_schema` 宣告式表單定義，支援前端動態渲染參數。
2. `src/plugins/loader.py`：實作 `StrategyLoader`，支援動態熱加載、熱重載與語法/執行期例外隔離沙盒（單一插件崩潰不影響主進程）。
3. 出廠雙試紙 (`src/plugins/strategies/`)：
   - 試紙一：下單通道驗證試紙 (`signal_test.py`)：無部位時市價開多 + 掛標記價條件停損；持倉 N 根 K 線（預設 1 根）收盤無條件市價平倉。
   - 試紙二：經典雙均線試紙 (`sma_cross.py`)：快線 SMA 5 上穿慢線 SMA 20 金叉開多，死叉開空。

**Blocked by:** 06: 實質槓桿硬上限風控引擎

**Status:** completed

- [x] 實作 `src/plugins/base.py`，定義 `StrategyBase`、`ParameterSchema` 與信號/委託介面
- [x] 實作 `src/plugins/loader.py`，支援動態掃描、熱加載與錯誤隔離沙盒
- [x] 實作試紙一：`SignalTestStrategy` (通道驗證試紙)
- [x] 實作試紙二：`SMACrossStrategy` (SMA 5/20 雙均線試紙)
- [x] 撰寫單元測試 `tests/test_plugins.py`：驗證插件熱加載、參數 Schema 結構、雙試紙信號運算與例外隔離
