# 分市場環境評估：後端契約與自測證據

2026-10-19，使用者同意接續上一工作包的下一規劃。本工作包已實作、開發自測通過，待使用者最新指定的 GPT-6 Sol 獨立驗收與 Git 核對（取代 5.6 Sol Web）。前端仍由 Antigravity IDE 負責。

## 能回答的問題

策略的損益集中在上漲、下跌還是震盪？高／低波動時有多少觀察區間、多少成交、付出多少成本？本模組用同一份回測的逐根權益變化回答，避免在不同環境重複計入同一筆跨環境持倉的整段損益。

新增 `catos/research_regimes.py`、專屬測試與 `examples/research_regimes_demo.py`。沿用原有 Decimal 回測及滾動 OOS 控制器，不改變策略決策、選參、成交模型或上線門檻；這是研究診斷，不是自動調整策略的環境過濾器。

## 明示分類規則

版本 `lagged_efficiency_true_range_v1`。呼叫者必須提供 `RegimeRule(lookback_bars, trend_efficiency, high_volatility_bps)`，沒有通用預設門檻。範例門檻只驗證合成算術，不是 BTC 或其他市場的建議參數。規則應在研究前固定；若看完 OOS 再調門檻，同一批資料不再是全新保留集。

- 視窗 L：最近 L 次收盤價變化，需要 L+1 根已收盤 K 線。效率值 = 收盤淨變化的絕對值 ÷ 逐次變化絕對值合計；全程平盤為 0。效率值 >= 趨勢門檻時，依淨變化正負標為 UP／DOWN，其餘為 RANGE。
- 每根 True Range = `max(最高－最低, abs(最高－前收), abs(最低－前收))`；除以前收並乘 10000 轉為 bps。最近 L 根的算術平均 >= 波動門檻為 HIGH，否則 LOW。這不是年化波動率或標準差。
- 六種互斥環境為 UP／DOWN／RANGE × LOW／HIGH。歷史不足保留 UNKNOWN 與 `insufficient_history`，不補值、不刪除。剛好等於門檻歸趨勢／高波動。
- 分類數值使用既有 50 位 Decimal context；不使用 float、全樣本分位數或未來 K 線。L 必須為正整數；趨勢門檻必須為有限 Decimal 且 > 0、<= 1；波動門檻必須為有限正 Decimal，沿用核心輸入精度限制。

每個 `RegimeLabel` 記錄收盤時間、環境、效率、波動值及未分類原因。改動未來資料或增加後段資料，不能改變較早的標籤。

## 因果時間與損益歸屬

標籤在該根收盤後才已知，因此某根的權益區間使用「前一根收盤」的標籤。當前根突然大漲，不會把自己的獲利事後歸為上漲環境。沒有前根時記為 UNKNOWN／`no_prior_closed_bar`。沒有前置歷史的 L 根視窗，最初 L+1 個權益區間會是 UNKNOWN。

預熱仍只更新策略指標、不產生交易；分類器可以使用已提供的前置歷史。OOS 分類可用先前訓練資料，即使策略預熱較短；分類器不把這些額外資料或標籤傳給策略／評分器，也不改變訓練選擇。

每個權益區間只歸一種環境：

- 淨損益 = 本根收盤權益－前一個權益點。包含跨環境持倉的估值變化，不把整段已實現損益再於平倉時重算。
- 手續費與帶正負號的資金費採核心累計值差額。它們已包含在淨損益，不再重複扣除。負資金費表示收入。
- `gross_pnl` = 淨損益＋手續費＋資金費；只加回這兩項，**不加回成交滑價**，不虛構期末退出成本。
- 成交筆數按該根開盤成交歸屬，不是完整來回交易次數。資金費在等時點沿用核心的「先前部位先結算，再做開盤成交」；落在收盤邊界的事件歸前一區間，首段另包含評估起點事件。零部位的零金額資金費事件仍計筆數。

`RegimeEvaluation` 同時保存逐根明細、七種環境（包含零樣本者）的彙總、全部區間總額及核對結果。彙總含 K 線區間數、正／負／零損益根數、成交／資金費筆數、淨／毛損益及成本。這些根數不是獨立統計樣本；正損益根數占比不是交易勝率。

歸屬加減及分組加總使用足以精確保存核心既有數值的 Decimal 精度，沒有更動帳務核心。總淨損益在核心 50 位 context 下須與原績效一致，成本與筆數也須一致；失配直接報錯。極端量級可能有核心最終減法的捨入差，另存 `core_net_rounding_residual`，滿足「歸屬總淨損益＋差額 = 原核心淨損益」，不藏入任何環境。一般合成範例差額為 0，專屬測試另涵蓋非零邊界。

各 OOS 視窗維持獨立初始資金／空倉，期末僅估值、保留 pending intent；不把不同環境或不同視窗的數值串成可交易資金曲線。不提供分環境複利報酬、回撤、顯著性或自動通過標準。

## 後端入口

```python
from decimal import Decimal
from catos.research_regimes import RegimeRule, regime_walk_forward, regimes_json

result = regime_walk_forward(
    strategy_factory=trusted_strategy_factory,
    search_space=bounded_search_space,
    candles=closed_candles, config=backtest_config,
    rule=RegimeRule(3, Decimal("0.5"), Decimal("250")),
    score=lambda p: p.return_pct, score_name="net return percent",
    plan=explicit_walk_forward_plan, max_candidates=6, max_runs=21,
)
payload = regimes_json(result)
```

`classify_regimes()` 單獨分類；`regime_backtest()` 呼叫既有回測並歸屬；`regime_walk_forward()` 呼叫既有滾動驗證，僅彙整成功 OOS，不額外重跑回測。後兩者自行綁定相同輸入與核心結果，避免把不同行情的回測拿來標註。

滾動結果保留完整 `validation`（包括訓練候選、失敗與 OOS）及各窗 `windows` 評估。NO_SELECTION／OOS_FAILED 保留狀態、候選失敗／OOS 錯誤及 `evaluation=None`，不偽裝為零績效。既有預算預檢及中斷行為不變。

`regimes_json()` 確定性序列化，Decimal 為字串，包含規則版本、參數、全段標籤與輸入 SHA-256。雜湊涵蓋 K 線、config 與分類規則，不包含策略／評分器原始碼或依賴版本；呼叫端仍須保存這些重播材料。目前沿用參數型別所在模組，因此匯入需既有 Optuna 依賴。

## 本輪實際驗證

Python 3.14.6、Optuna 4.9.0。26 項專屬＋22 項研究驗證＋18 項 Decimal 核心，**66/66 通過，0 failure／error／skip**。包含分類邊界、未知、未來擾動、落後一期歸屬、持倉跨環境、反轉／加減倉、費用與資金費邊界、Decimal context／非零捨入差、原核心直接重播、OOS 失敗保留、預算與中斷。

```powershell
py -3 -B -m unittest discover -s tests -p test_research_regimes.py -v
py -3 -B -m unittest discover -s tests -p test_research_validation.py -v
py -3 -B -m unittest discover -s tests -p test_research.py -v
py -3 -B -m examples.research_regimes_demo
```

合成範例沿用前一工作包的 24 根 15m K 線、6 候選、3 個 OOS 視窗／21 次回測。實際低精度 ambient context 重播及模組命令列輸出完全一致；核對前一輪 8 個來源雜湊無漂移，內含 validation 與前一輪保存的 JSON 完全相同。這證明本次分類沒有改變原選參／回測，不代表重跑 Optuna 測試或真實行情研究。

| OOS 視窗 | K 線區間數 | 環境分布 | 淨損益（USDT） | 成交數 |
| --- | ---: | --- | ---: | ---: |
| 0 | 4 | UP_HIGH 4 | -0.05165500 | 2 |
| 1 | 4 | DOWN_HIGH 2、RANGE_HIGH 2 | -0.00164030 | 1 |
| 2 | 4 | UP_HIGH 3、RANGE_HIGH 1 | -0.07166500 | 2 |

各段均核對一致，負損益完整保留。樣本刻意很少、部分環境沒有樣本，只驗證機制，不構成策略有效性或市場結論。

- [實際命令、版本、來源雜湊與結果](../reports/research-regimes-20261019-2134/verification.json)
- [原始測試日誌](../reports/research-regimes-20261019-2134/unittest.log)
- [完整合成結果 JSON](../reports/research-regimes-20261019-2134/synthetic-regimes.json)
- [本輪一次性採證腳本](../reports/research-regimes-20261019-2134/verify.py)（拒絕覆寫已存證據）

以上產物沿用 reports 既有忽略規則；這是開發自測，未獨驗。沒有修改前端、HTTP／MCP、DB schema、策略製品或交易底座，沒有服務操作、產品 DB／憑證讀取、外部來源、真實行情回測或 Git。

## 下一成果建議

使用者後續已同意並執行「研究結果封存與後端查詢契約」，見[實作契約與本輪證據](research-validation-api.md)。沿用既有 ResearchService／writer／核准製品，封存訓練穩定區、OOS、分環境結果與來源快照。此狀態取代上一版「尚未啟動整合」的下一步建議，不將上列 66/66 歷史證據當後續整合測試；未擴充前端、DB schema、真實資料或 AI 自主研究，仍待指定角色獨驗。
