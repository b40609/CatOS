# S7：本機合成情境報告 API 與驗收規格

狀態：2026-09-19 正式設計規格，依使用者同意接續 [範圍評估](catos-s7-scenario-report-assessment.md)制定。尚未編寫 S7 程式或執行驗證。已驗收基線為 S6 commit `ecc897e3afc19ab03527a4e1529f060b83f21df7`；S6／S4／S5 共 115/115 通過為使用者回報，非本輪重驗或全量測試結果。

## 1. 交付目標與邊界

新增純函式，將既有 S5 capture 與明示合成情境交給 S6 校驗、S4 計算，產生繁體中文離線 HTML 字串。報告供人檢視來源、曝險、品質與降級原因，不產生交易或風控裁決。

具體防止三種呈現錯誤：None 顯示成零、MATCH 被誤讀為交易所對帳完成、仍有數字時隱藏來源過期或不完整。最小實作為標準函式庫、固定摘要表與內嵌 CSS；驗證限呈現專屬測試、S6 必要回歸及離線視覺檢查。

不修改 S4／S5／S6 算術或校驗、Schema7、Risk、P6、execution／protection、Worker／Supervisor 或交易路徑。不新增 DB 連線、帳本、快取、Gross 限額、額度預留、CLI、檔案輸入格式、常駐 UI、外部行情或 Demo／Live 接線。維持 local-sim；不變更 v1 單合約單 Bot 政策。

## 2. 公開 API 與資料流

模組：`catos/lot_scenario_report.py`。

```python
def render_synthetic_scenario_report(
    *,
    capture: LocalLotCapture,
    scenario: SyntheticScenarioEvidence,
    now_ms: int,
) -> str:
    ...
```

三個參數均必填且僅接受關鍵字；型別直接引用既有 S5／S6 定義，不建立第二組 DTO。回傳完整 HTML 文件的 Python `str`，不接受路徑、Journal、client、任意 report、使用者模板或可執行 callback。

執行順序固定：

1. 以原參數呼叫一次 `lot_scenario.observe_synthetic_scenario(capture=capture, scenario=scenario, now_ms=now_ms)`。
2. 呼叫成功後，從返回的 observation／report 取得觀測結果；只從已通過該呼叫校驗的 capture／scenario 補充來源時間與 mark 原值。
3. 格式化及逸出文字，返回完整 HTML。不得再次呼叫 S4、重算金融數值、預先格式化未校驗的輸入或重新建立 attestation。

不修改輸入，不自行排序 capture、不補造 physical／mark、不更新有效期限、不以 capture_id 代替 scenario_cut_id。所有時間均來自參數；無目前時間、隨機 ID 或路徑，完全相同輸入應產生完全相同字串。

S7 沒有檔案寫入副作用。呼叫端負責取得 capture 及保存 HTML；本片不新增保存流程。測試可自行建立臨時 Journal／檔案，但建立、保存不屬於 renderer。

## 3. 欄位映射

以下以 `o` 表示 S6 返回的 `SyntheticScenarioObservation`、`r = o.report`。所有列均必須呈現，缺值也不得隱藏整列。英文欄位鍵可作為表格次要文字，主標籤使用中文。

### 3.1 來源、身份、合約與時間

| 來源欄位 | 中文標籤／規則 |
|---|---|
| `o.evidence_kind`、`r.evidence_kind` | 合成證據種類，正常均為 SYNTHETIC_SCENARIO；分別保留外層／報告來源值 |
| `capture.source`、`scenario.source` | 快照來源／情境來源，synthetic_ledger／synthetic_scenario |
| `r.scope.account_ref`、`r.scope.environment` | 本機帳戶代稱／環境；environment 為 local-sim |
| `r.contract.inst_id` | 合約 |
| `r.contract.base_per_contract` | 每張標的資產數量，單位標的資產／張；不猜測額外幣種欄位 |
| `r.contract.tick_size` | 價格跳動單位，USDT／標的資產 |
| `r.contract.lot_size`、`r.contract.min_size` | 張數步長／最小張數，單位張 |
| `o.source_capture_id` | 來源 capture 身份；完整顯示，hash 只證明內容身份 |
| `o.scenario_cut_id` | 明示合成情境截點 |
| `r.lot_cut_id`、`r.physical_cut_id`、`r.pending_cut_id` | Lot／合成實體／未決責任截點，各自顯示原值 |
| `r.quote_id` | 合成 mark 報價身份；None 顯示未提供 |
| `r.now_ms` | 評估時間，Unix epoch 毫秒 |
| `capture.observed_at_ms`、`capture.valid_until_ms` | Lot／未決責任來源取樣時間及有效截止時間，Unix epoch 毫秒 |
| `scenario.physical_observed_at_ms`、`scenario.physical_valid_until_ms` | 合成實體來源取樣時間及有效截止時間，Unix epoch 毫秒 |
| `scenario.mark_observed_at_ms`、`scenario.mark_valid_until_ms` | 合成 mark 取樣時間及有效截止時間，Unix epoch 毫秒；None 顯示未提供 |
| `scenario.mark` | 合成 mark 原始輸入，USDT／標的資產；None 顯示未提供，過期數值保留且由 mark_fresh 說明 |

不轉換時區，不將有效截止時間改為含端點。既有 fresh 定義為 observed_at_ms <= now_ms < valid_until_ms；renderer 僅顯示 S4 旗標，不自行重判。

### 3.2 數量與估值

| report 欄位 | 中文標籤 | 單位 |
|---|---|---|
| `observed_long_qty` | 已觀測多倉數量 | 張 |
| `observed_short_qty` | 已觀測空倉數量 | 張 |
| `observed_gross_qty` | 已觀測 Gross 數量 | 張 |
| `observed_net_qty` | 已觀測淨數量（含正負號） | 張 |
| `physical_qty` | 合成實體淨數量（含正負號） | 張 |
| `delta_qty` | 數量差額（Lot Net−合成實體） | 張 |
| `observed_gross_notional` | 已觀測 Gross 名目價值 | USDT |
| `observed_signed_net_notional` | 已觀測淨名目價值（含正負號） | USDT |
| `physical_notional` | 合成實體名目價值（絕對值） | USDT |

`comparison_status` 固定對照：MATCH →「合成情境數量相符」、MISMATCH →「合成情境數量不符」、UNAVAILABLE →「無法比較」；同時顯示原始代碼。若將來收到未知狀態，顯示「未識別比較狀態」與原碼，不自動歸類為 MATCH。

頁首固定說明：「本機合成情境；不是交易所證據或交易許可。MATCH 僅表示本次合成情境數量相符。」不使用成功勾選、可交易、已對帳、accepted／ready／authorized 等肯定裁決。

### 3.3 未決責任與上界

| report 欄位 | 中文標籤／單位 |
|---|---|
| `pending_buy_qty`、`pending_sell_qty` | 未決責任買入／賣出總量，張 |
| `synthetic_buy_qty`、`synthetic_sell_qty` | 合成帳本未決買入／賣出量，張 |
| `held_buy_qty`、`held_sell_qty` | HELD 分類買入／賣出量，張 |
| `exchange_buy_qty`、`exchange_sell_qty` | EXCHANGE 分類買入／賣出量，張 |
| `physical_scenario_upper_qty` | 合成實體情境數量上界，張 |
| `virtual_gross_scenario_upper_qty` | 虛擬 Gross 情境數量上界，張 |
| `unresolved_lot_count` | 未決 Lot 數，個 |
| `pending_unique_count` | 去重後責任數，筆 |
| `pending_duplicate_count` | 重複責任數，筆 |

本區固定註明：責任來源為 SYNTHETIC_LEDGER／UNTERMINATED；HELD／EXCHANGE 分項為零只代表本合成輸入沒有該分類，不能證明交易所沒有委託。上界為合成情境量，並非額度或限額；未成交 CLOSE 不預扣目前 Gross。

所有 buckets 直接使用 r，不由 pending 明細重新加總；不可用時保留 None 的語義。零剩餘但未 terminal 的責任可能仍計入筆數，不能由數量 0 推導為全部終結。`unresolved_lot_count` 只沿用 S4 對現有 Lot 的計數，不宣稱包含尚未形成 Lot 的全部 OPEN 責任。

### 3.4 品質旗標

| report 欄位 | 中文標籤／必要說明 |
|---|---|
| `lot_complete` | Lot 集合完整 |
| `lot_fresh` | Lot 來源在有效期內 |
| `physical_fresh` | 合成實體來源在有效期內 |
| `physical_verified` | 合成實體完整性聲明成立；沿用 scenario.physical_complete 映射，非交易所查證 |
| `mark_fresh` | 合成 mark 在有效期內；缺價亦為 false |
| `pending_complete` | 未決責任集合完整 |
| `pending_fresh` | 未決責任來源在有效期內 |
| `has_unknown` | 所見 EXCHANGE／UNKNOWN 責任；false 不表示無未決責任或完整對帳 |

布林顯示「是（true）」／「否（false）」，不顯示數值 1／0，不將 complete、fresh、verified 合併成單一通過狀態。數量或估值有值時仍必須展示品質與原因：例如 Lot 過期但 mark 新鮮時，S4 仍可能返回估值；S7 不將其改成 None，也不以有估值推導資料新鮮。

## 4. 降級原因對照

`r.reasons` 依返回順序逐項列出原始代碼與中文說明，不自行刪除、排序或補造原因。不把全域原因硬綁到特定空值；原因區與品質表必須同頁可見。空 tuple 顯示「無降級原因」，不代表交易授權。

| 原始代碼 | 中文說明 |
|---|---|
| `lot_stale` | Lot 來源不在有效期內 |
| `physical_stale` | 合成實體來源不在有效期內 |
| `mark_stale` | 合成 mark 不在有效期內 |
| `pending_stale` | 未決責任來源不在有效期內 |
| `future_observation` | 存在晚於評估時間的取樣 |
| `physical_unknown` | 合成實體數量未提供 |
| `physical_unverified` | 合成實體完整性聲明未成立 |
| `lot_inventory_incomplete` | Lot 集合不完整 |
| `position_cut_mismatch` | Lot 與合成實體截點不一致 |
| `mark_missing` | 合成 mark 未提供 |
| `pending_missing` | 未決責任集合未提供 |
| `pending_lot_link_incomplete` | 未決責任與 Lot 關聯不足 |
| `pending_incomplete` | 未決責任集合不完整 |
| `pending_cut_mismatch` | 未決責任與部位截點不一致 |
| `pending_quantity_unknown` | 存在數量未知的未決責任 |
| `pending_effect_unknown` | 存在效果未分類的未決責任 |

未收錄代碼顯示「未收錄原因」與完整原碼。部分代碼在合法 S6 輸入下不會出現；保留 S4 對照供診斷，不代表 S7 接受繞過 S6 的輸入。未知碼／未知狀態及防禦性逸出可測試私有格式化函式或以受控 stub 測試，不得為測試新增公開任意 report 入口。

## 5. 數值、HTML 與可讀性

- Decimal 非零值使用 `format(value, "f")` 完整呈現；不 normalize、quantize、轉 float 或重算，不依呼叫端 Decimal context 捨入。零值統一顯示 `0`，包括帶小數位的零與負零；非零負值保留負號，正值不強加加號。
- report 數值為 None 時顯示「不可用」；缺席 quote_id／pending_cut_id／mark 及 mark 時間顯示「未提供」。已提供的數字 0 絕不可當成缺值。整數直接顯示十進位，不加千分位或科學記號。
- 完整文件含 HTML5 doctype、`lang="zh-Hant"`、UTF-8 charset、viewport、固定 title。只用標準函式庫與內嵌 CSS；不含 JavaScript、外部字型、CDN、iframe、表單或外部資源請求。
- 所有動態字串（身份、數值、原始代碼等）在插入 HTML 時使用 `html.escape(..., quote=True)`；不把資料放入 style、HTML 屬性名或 URL。固定欄位鍵如用於 DOM 標示須由程式常數提供。
- 使用具欄名的語義表格與明確區塊標題；來源標示不可折疊。狀態不能只靠顏色區分；不截斷 ID／長小數，不使用省略號隱藏內容。
- 1280 px 桌面及 390 px 窄視窗均能閱讀；長內容可換行或在表格容器內橫向捲動，不能覆蓋相鄰欄位。無每 Lot／每訂單明細、圖表或互動篩選。

## 6. 錯誤契約與副作用

`ScenarioInputError`、`ExposureInputError` 原樣向呼叫端傳遞，保留 exception 類別與 code；不捕捉後轉成成功 HTML、空報告、警告列或另一種錯誤碼。不吞掉其他非預期錯誤。不新增 S7 業務錯誤階層；參數缺少等 Python 呼叫錯誤維持 TypeError。

renderer 不存取檔案、DB、網路、時鐘或環境變數；也不呼叫瀏覽器、印出日誌或保存 HTML。不修改 Decimal context／flags、輸入 dataclass 或 collection。既有模組載入不視為 renderer 的執行期 I/O；I/O 阻斷測試於必要模組與 fixture 建立完成後施加。

合法來源仍須經 S6 所有校驗；不複製其 hash／scope／數量驗證程式，也不另加 S7 輸入截斷或上限。容量沿用 S5／S6 已有界線；輸出固定摘要，不列 4096 筆明細。不宣稱限制 S5 全歷史重放成本或優化其效能。

## 7. 驗收矩陣

以下為情境群 ID，不預先等同 unittest 方法數；方法數及子案例在開發交接中如實列出。核心行為至少有一條真實 S3→S5→S6→S7 整合案例，其餘依責任使用既有 fixture 或小型記憶體輸入。

| ID | 情境與預期 |
|---|---|
| A01 | 完整有效情境：所有第 3 節欄位、來源、身份、單位及旗標均對應輸入／真實 S6 結果 |
| A02 | MATCH、MISMATCH、UNAVAILABLE 三種狀態：中文與原始代碼正確，固定來源說明存在 |
| A03 | 公開入口以原參數恰呼叫一次 S6；沒有額外 S4 呼叫或第二次計算 |
| A04 | 同一組輸入重複呼叫產出完全相同字串，輸入內容與 Decimal context／flags 不變 |
| B01 | mark 缺席：原始 mark／metadata 顯示未提供；估值不可用；數量比較可保留，列 mark_missing |
| B02 | physical 缺席／已知但完整性聲明為 false：保留原值，差額與上界依 S4 為不可用，相關原因俱全 |
| B03 | unmanaged unresolved：pending_complete=false；分項／上界不可用，不補零，原始原因俱全 |
| B04 | Lot／physical／pending／mark 過期及未來取樣：原旗標與原因完整，仍有數字時不遮蔽或改判 |
| B05 | 有效期邊界 now_ms 等於 observed／valid：沿用 S6／S4 結果，不自行重算時間 |
| B06 | 空集合且合法：精確零與不可用不同；無原因時僅顯示無降級原因 |
| C01 | 同合約多空：Gross、signed Net、負 delta 及 physical 絕對名目價值不互換 |
| C02 | OPEN 首次成交前／部分成交與 CLOSE 未成交：上界及數量等於 S6，無呈現層加總或 CLOSE 預扣 |
| C03 | 剩餘量零但未 terminal 與 terminal 後：量與筆數照實；不以零宣稱責任終結 |
| C04 | synthetic、held、exchange 各分項照實，合成分類零的限制文字及 has_unknown 語義存在 |
| D01 | 極小非零、長小數、負值、Decimal 尾零與負零格式：完整精度；不轉 float、不科學記號、不受低精度 context 影響 |
| D02 | 所有已知 reason 對照、未知 reason／status 回退，原碼保留；沒有推導新裁決 |
| D03 | 含 &、<、>、雙引號、單引號的動態文字正確逸出，不能注入節點或屬性 |
| D04 | HTML 文件結構、語言、charset、viewport 及無外部資源／腳本；長文字完整存在 |
| E01 | 錯 capture binding、非法 cut／scope 等 S6 拒絕案例，原 exception/code 向外傳遞，不回 HTML |
| E02 | S6 拋 ExposureInputError 或非預期錯誤時保留錯誤；可用受控 stub 證明 S7 不吞錯 |
| E03 | 已建立 fixture 後阻斷檔案、DB、網路、時鐘、環境讀取，renderer 正常完成且無日誌輸出 |
| E04 | 真實 Journal 合成資料 capture→S6→HTML 整合；renderer 本身不開啟或存取 Journal |
| F01 | 桌面／窄視窗，完整及降級報告：無遮擋、長數值／身份可讀、來源說明醒目、狀態非僅靠顏色 |
| F02 | 專屬測試與 S6 必要回歸、編譯及 diff／staged 範圍檢查；實際結果由 Sol 記錄 |

D01 可直接驗證私有 Decimal 格式化函式；D02／D03 的不可由合法 S6 產生資料以私有呈現 helper 或受控 stub 測試，需在測試名稱／交接明示。不得修改 S6 來容許非法 fixture，也不能只用 stub 取代 A01／E04 的整合證據。避免全頁 HTML golden snapshot；以穩定欄位鍵及解析後文字核對數值、標籤、語義與結構。

## 8. 檔案範圍與分工

後續實作預定新增 `catos/lot_scenario_report.py`、`tests/test_lot_scenario_report.py`、`docs/lot-scenario-report-handoff.md`，並更新 README／WORK_PLAN 的開發狀態。必要 fixture 優先沿用既有 helper；不因本片抽取通用框架或重構既有報告。

Astra 編寫程式與測試；Sol 執行：

```text
<python> -B -m unittest discover -s tests -p "test_lot_scenario_report.py" -v
<python> -B -m unittest discover -s tests -p "test_lot_scenario.py" -v
```

S4／S5 若被修改或出現相關失敗才擴充該模組測試；不主動跑全量或全市場回測。Sol 記錄 Python／SQLite 版本、實際 run／failure／error／skip、編譯、diff／staged 範圍與 F01 視覺結果；未執行的項目明示，不將樣本生成視為已完成視覺驗收。

視覺樣本由驗證端使用合成 fixture 產生至新的本機輸出位置，不覆寫使用者報告；HTML／截圖不作為本片程式提交必要內容。完成條件為 renderer／專屬測試交付並經 Sol 通過上述必要驗證；本輪文件交付僅完成規格，不代表 S7 功能通過。

yaoI／yaozi、market 工作及既有 S5 未提交驗收紀錄不在修改與提交範圍。S6 驗收補記為先前文件變更，不宣稱已包含於 S6 commit；Git 分組由 Sol 核對，不把工作區所有未提交內容一起加入。
