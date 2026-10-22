# 參數鄰域穩定度與滾動樣本外驗證

2026-10-19 後端工作包：已實作、開發自測通過，待使用者最新指定的 GPT-6 Sol 獨立驗收（取代 5.6 Sol Web）。本文件的選參規則是研究工具的明示預設，不是新增金融政策或策略上線標準。

使用者授權接續前端以外的進度；前端由 Antigravity IDE 平行開發。本輪新增獨立研究模組、測試與合成範例，未修改前端、既有回測／Optuna 核心、HTTP／MCP 契約、資料庫或交易底座，未操作服務、Git、憑證或外部資料來源。

## 解決的缺口

原有 Optuna 能搜尋樣本內高分參數，但少量抽樣不足以證明附近參數也有效；既有 DCM 固定切分研究也不等於可重複使用的滾動驗證控制器。

- `catos/research_validation.py::parameter_stability()`：完整跑完明示預算內的小型參數格點，保留各候選績效、期末部位、未成交意圖與失敗原因，計算鄰域穩定度。
- `catos/research_validation.py::walk_forward()`：每個視窗先用前段資料選參數，固定選擇後才執行後段樣本外回測；訓練窗定長向前滾動，測試窗不重疊。
- `validation_json()`：輸出可重現的結構化 JSON，財務數值與評分均為 Decimal 字串；保存輸入雜湊、參數格點、評分方向、規則版本、個別失敗及完整 OOS 回測結果。

這補齊「附近是否穩定」與「選完後往後測」的研究執行能力。後續同日已另交付[分市場環境評估](research-regimes.md)，取代本文件原先「分環境尚未交付」的狀態；AI 自主發想／執行研究、連續投資組合 Walk-Forward 仍未交付。

## 選參規則

規則版本：`maximin_axis_neighbors_v1`。

1. 沿用 `IntRange` 與 `DecimalChoices`；參數名稱排序，Decimal 候選依數值排序並保存原始字串。完整格點至少兩個組合，不能用稀疏 Optuna 紀錄冒充完整鄰域。
2. 鄰域包含中心，以及每個參數軸向前／後一格的候選；不含斜角。DecimalChoices 的「一格」是相鄰候選，間距不保證相等。邊界只有單側鄰居，會保存實際成員；邊界高分不代表範圍外也穩定。
3. 中心或任一現有鄰居回測／評分失敗，該鄰域不參與排名，不跳過失敗點後重算漂亮平均。
4. maximize 依鄰域最低分、鄰域平均、中心分數由高到低排序；minimize 依最高分、平均、中心分數由低到高排序。完全同分取較早的格點序號。
5. 評分 callback 只取得 `Performance`，須回傳有限 Decimal，且能在既有 50 位研究 context 中無損表示；float、非有限值、超出表示範圍或精度均記錄失敗。平均評分採 50 位精度，計算加總時擴充分數指數空間，避免合法大分數加總溢位。這不更動帳務 context。

這是保守鄰域排序，並非統計顯著性、參數平臺認證或獲利門檻。全部負分仍可能選到「相對較好」的候選；`COMPLETE` 僅指執行完整。尚無最少成交數、正報酬、最大回撤等上線篩選門檻，不得據此自動部署。

## 時間、預算與成本契約

`WalkForwardPlan(train_bars, test_bars, windows, warmup_bars=0)` 的計數皆為指定週期的 K 線根數，不是分鐘。第一個訓練起點為 warmup_bars；後續每次前進 test_bars。區間為起點包含、終點不包含。至少需要 `warmup_bars + train_bars + windows * test_bars` 根已收盤、連續 K 線；多餘資料只記錄 `unused_bars`，不自動新增視窗。

`max_candidates` 限制完整格點數，先計算大小再建立格點；`max_runs` 至少為 `windows * (候選數 + 1)`，包含每窗一次 OOS 嘗試。無效輸入或預算不足在執行任何策略前拒絕。失敗算一次嘗試，不重試；沒候選時略過該窗 OOS，所以實際嘗試數可能較少。

每次訓練回測及 OOS 都建立新策略、以原始初始資金與空倉開始。每段只向策略逐根提供其前置預熱與當段已收盤資料；預熱不決策、不帶入委託意圖。固定選參後，OOS 不重選或偷看後段。後續訓練正常會納入較早 OOS 資料，已看過的樣本外也不能再稱全新保留集。策略與評分器仍須受信、確定性，這不是防止惡意程式讀外部資料的安全沙箱。

沿用原有核心：本根收盤決策、下根開盤加明示滑價成交，收取成交費；資金費只採呼叫者明示提供的事件，依各段覆蓋範圍裁切，預熱期不計帳。空資金費陣列就是無資金費假設。期末未平倉以收盤估值，**沒有強制平倉或額外退出成本**，期末未成交意圖保留。

各 OOS 視窗為獨立診斷，不串接部位／資金，不合併報酬為連續可交易績效。單根 OOS 沒有下根可成交，可能零成交且留 pending intent；不能據此判定策略有效。`trade_count` 是成交筆數，不是完整來回交易次數。

## 後端呼叫

```python
from catos.optimization import DecimalChoices, IntRange
from catos.research_validation import WalkForwardPlan, validation_json, walk_forward

result = walk_forward(
    strategy_factory=trusted_strategy_factory,
    search_space={"period": IntRange(2, 4),
                  "quantity": DecimalChoices(("1", "2"))},
    candles=closed_candles, config=backtest_config,
    score=lambda p: p.return_pct, score_name="net return percent",
    plan=WalkForwardPlan(train_bars=8, test_bars=4, windows=3, warmup_bars=4),
    max_candidates=6, max_runs=21,
)
payload = validation_json(result)
```

策略 factory 取得唯讀參數 mapping，整數維持 int，DecimalChoices 還原為 Decimal。每窗 `training.selected_trial` 是固定的選參紀錄，`out_of_sample` 為既有 BacktestResult 或 None。

狀態：`COMPLETE` 有 OOS 結果；`NO_SELECTION` 沒有可排名的完整鄰域；`OOS_FAILED` 已選參數但 OOS 執行失敗。任一視窗非 COMPLETE，整體 `complete=false`；失敗仍保存，不刪窗粉飾。KeyboardInterrupt 等中斷向上傳遞，不偽裝成普通候選失敗。

輸入 SHA-256 涵蓋 K 線與 config，結果另存參數格點、計畫與規則；雜湊不包含策略／評分器程式碼，也不單獨構成可重播封存。呼叫端須保存原始輸入、策略／評分器與依賴版本，不能宣稱只有 JSON 就能重現任意策略。

## 本輪實測證據

環境：Python 3.14.6、Optuna 4.9.0。新模組沒有使用 Optuna 搜尋，但沿用其參數型別所在模組，因此目前匯入仍需既有 Optuna 依賴。

本輪實際使用 `unittest.TestLoader.discover` 載入下列三個 pattern，再以 `TextTestRunner(verbosity=2)` 同一程序執行；**48/48 通過，0 failure／error／skip**：新驗證模組 22 項、原有 Decimal 回測 18 項、Optuna 8 項。涵蓋尖峰與平臺、失敗鄰居、最小化、Decimal 精度／極端值、預算預檢、時間切分、未來資料擾動、暖機隔離、成本／資金費直接重播、OOS 失敗續跑及中斷。

可分別重現：

```powershell
py -3 -B -m unittest discover -s tests -p test_research_validation.py -v
py -3 -B -m unittest discover -s tests -p test_research.py -v
py -3 -B -m unittest discover -s tests -p test_optimization.py -v
py -3 -B -m examples.research_validation_demo
```

本輪另實際呼叫 `run_demo()` 兩次，比對 JSON 完全相同。24 根合成 15m K 線、6 個參數組合、3 窗，共 21 次回測；三段 OOS 淨損益依序為 `-0.05165500`、`-0.00164030`、`-0.07166500` USDT，成交數 2／1／2。這些都是人工合成行情的算術驗證，不是 BTC 歷史實績，也不合併成投資績效。

原始日誌、8 個相關來源 SHA-256、版本、合成 JSON 與輸出 SHA-256：

- [驗證清單](../reports/research-validation-20261019-212235-573028/verification.json)
- [原始測試日誌](../reports/research-validation-20261019-212235-573028/unittest.log)
- [合成滾動結果](../reports/research-validation-20261019-212235-573028/synthetic-walk-forward.json)
- [來源雜湊、AST、文件連結與命令列檢查](../reports/research-validation-20261019-212235-573028/static-checks.json)

補充檢查已通過：8 個驗證來源雜湊一致；3 個新 Python 檔 AST 解析成功；實際以 `python -B -m examples.research_validation_demo` 執行退出碼 0，JSON 與已存合成結果的雜湊一致。

產物沿用 reports 的既有忽略規則，不納入 Git；開發者自測不等於指定角色獨驗。既有 DCM 真實資料研究只作歷史背景，本輪沒有讀產品 DB、執行歷史行情回測或重跑舊授權採集。

## 下一個成果

使用者已同意接續「分市場環境評估」，同日後續工作包已實作並自測，見[契約與證據](research-regimes.md)。採明示、可配置的研究門檻與前一根已收盤標籤；分類不改 OOS 選參，損益逐根唯一歸屬。這取代前版「尚未實作」的下一步說明，不表示已訂定通用市場門檻或完成獨立驗收。

本工作包當時未擴充 HTTP／MCP、研究任務持久化或前端。同日後續已核對既有 writer／製品契約，新增[研究驗證封存與後端查詢](research-validation-api.md)，不覆寫以上歷史證據；前端、MCP 送出工具與真實資料驗證仍未擴充。獨驗與 Git 維持指定分工，未提交／push。
