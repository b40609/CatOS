# catOS × Yaozi Functional Parity — New Conversation Handoff

日期：2026-09-18

## 1. 任務目標

使用者是 OKX 交易者 / KOL。目標不是複製 Yaozi UI，而是先忠實重建它的「功能與資料語義」，實際使用後再做簡化。

目標架構：

```text
Market Data
  -> Feature Engine
  -> Signal Engine
  -> Lifecycle Engine
  -> Evidence Layer
  -> Reflection / Proof
```

catOS 原則：

```text
Supervisor = 唯一網路 / 唯一 SQLite writer / 唯一交易權限
Worker     = 純訊號計算，不拿憑證、不直接連網、不寫 DB
```

市場情報使用獨立 `market_intel.sqlite`；現有金融交易 `Journal` 維持 schema 7，不做跨 DB 原子一致宣稱。

## 2. 已完成的研究規格

主規格：

`outputs/yaozi-functional-parity-spec-v0.1.md`

目前已確認的主要 Yaozi 結構：

- 約 60 秒掃描市場。
- L1 候選池 -> L2 多訊號交叉 -> Five Views。
- Five Views：Flow / Momentum / Opportunity / Risk / History。
- 14 個 L2 lights 與 `/signals` 事件系統是不同概念，不要混成單一 signal table。
- SMF 範圍 -100..+100，grade S/A/B/C/D；底層 feature weights 尚未取得。
- Flow 公開係數：OI speed 35、Taker 15、Top Trader LSR slope 15、OI quadrant 10、compression 10、Capital Flow 10、Momentum Tilt 10；公開係數合計 105，不要自行 normalize。
- Opportunity：quality >=55 入池；<45 連續 3 次結束；risk >=60 阻擋。
- Risk：>=60 高風險；>=45 watch；<30 連續 2 次 `risk_resolved`。
- Push/Proof 必須先 freeze snapshot + COMMIT，再推播，避免 survivor bias。
- Yaozi 公開 proof 顯示其主要 edge 是未來高波動/大幅移動篩選，不是已證實的方向預測優勢。

未知且禁止猜測：

1. SMF 真正底層 weights。
2. 埋伏 / 吸籌 / OI 暴衝 / 鯨魚進場等部分絕對 threshold。
3. Narrative 外部 heat provider 身份。
4. Dealer 最終 direction score 精確公式。
5. `/onchain/forensics/{symbol}/full` 完整 JSON schema。
6. Admin Reflection 動態權重 policy。

## 3. 已完成實作：P0-A

新增：

- `catos/market_collectors.py`
- `catos/market_intel.py`
- `tests/test_market_intel.py`
- `docs/market-intel.md`

內容：

- OKX / Binance public-only 固定 GET allowlist。
- USDT perpetual universe。
- ticker / OI / funding。
- Binance Top Trader L/S、taker ratio。
- API decimal string -> `Decimal`，禁止 float 滲入金融/市場精確數值。
- missing 保留 `None`，不補 0。
- 獨立 `market_intel.sqlite`，WAL + `synchronous=FULL`。
- 同 key 同內容 replay 可接受；同 key 不同內容 `snapshot_conflict`。

沒有真實網路採集、沒有帳戶 API、沒有下單、沒有讀憑證。

## 4. 已完成實作：P0-B

新增：

- `catos/market_features.py`

已實作：

- 1h / 24h return。
- ATR%。
- 20-bar realized volatility。
- Bollinger Band Width。
- BBWP percentile。
- rolling range position。
- `BREAKOUT_UP / BREAKOUT_DOWN / RANGE`。
- OI 5m / 1h / 4h percentage delta，只能比較同 venue，目標時間 lag >120s 即 missing。
- 完整 trade window 才計算 quote-notional CVD / taker buy ratio。
- REST `latest N trades` 永遠標 incomplete，不得冒充完整 CVD。
- `market_intel.sqlite` 已升 schema 2，支援 1→2 migration。
- 新增 `market_candle`、`flow_snapshot`。

重要：目前 BBWP / structure 是 catOS 自有、可重播定義，不宣稱與 Yaozi 私有公式完全相同。

## 5. 已完成實作：P0-C

新增：

- `catos/market_signals.py`
- `tests/test_market_signals.py`

14 個 L2 lights 中，目前有完整公開門檻、可執行的只有 5 個：

```text
MOMENTUM
STRONG_MOMENTUM
FUNDING_NEGATIVE_FLIP
TEAM_DISTRIBUTION
PURE_MOMENTUM
```

其餘 9 個固定為：

```text
DISABLED_UNKNOWN_THRESHOLD
```

不要自行補私有門檻。

5 個 Pattern 已完成：

```text
SHORT_SQUEEZE_CANDIDATE
COIL_BREAKOUT
PREHEAT
AMBUSH
FOMO
```

Pattern 採三值：

```text
HIT
MISS
MISSING_DATA
```

缺資料不等於 false / 0。

`signal_hit` 只持久化確定 HIT；`pattern_hit` 保存每次 Pattern 判定，`active=1` 只表示 HIT，完整 status 放 evidence JSON。

## 6. 最近驗證結果

P0-A/B/C 市場情報測試：

```text
23/23 PASS
```

OKX 相鄰回歸：

```text
53/53 PASS
```

上輪總計：76/76 PASS。

另外：

- `py_compile` 通過。
- `git diff --check` 通過。

## 7. 下一步：P0-D

直接從這裡開始，不需要重新研究 P0-A/B/C：

1. 建立 SMF interface / grade contract。
   - `score` -100..+100。
   - S >= +50。
   - A +20..+49。
   - B -20..+19。
   - C -49..-20。
   - D <= -50。
   - 因真實 feature weights 未知，不能自行製造 Yaozi SMF score。
   - 可接受 external/fixture supplied score，後端只驗證、grade、version、persist。

2. Flow lifecycle。
   - 依公開 35/15/15/10/10/10/10 components 建立 interface。
   - >=70 `ignition`。
   - 50..69 `accumulation`。
   - <35 連續 3 scans -> `flow_faded`。
   - component 若無法可靠算出，不補 0；應 missing / unavailable。

3. Opportunity lifecycle。
   - quality >=55 enter。
   - quality <45 x3 end。
   - risk >=60 blocks entry。
   - Structure × Behavior × SMF 的底層完整權重未知，先做 score contract / lifecycle，不偽造 scoring formula。

4. Risk lifecycle。
   - >=60 high risk。
   - >=45 watch。
   - <30 x2 -> `risk_resolved`。

5. deterministic scan transition。
   - 同輸入 + 同前狀態 -> 同輸出。
   - 不能讀 wall clock；scan timestamp 由 caller 明示。
   - state transition 與 DB persistence 分離，先做 pure reducer。

6. 持久化至既有：
   - `smf_snapshot`
   - `view_state`
   - 後續再接 `cycle` / `cycle_event`

P0-D 完成後，再做 P0-E：cycle + immutable push snapshot + 24h proof evaluator + 60 秒 orchestrator。

## 8. 不要做的事

- 不修改金融 `Journal` schema 7。
- 不把 market intelligence DB 當交易帳本。
- 不讓 Worker 直接連交易所 / 網路 / DB。
- 不讀或寫真實 API secrets。
- 不發 Demo/Live 訂單。
- 不以 float 保存價格、金額、OI、funding、score 等需要精確重播的數值。
- 不把 missing 變 0。
- 不猜 Yaozi 私有 threshold / SMF weights / Dealer formula。
- 不把 REST 最新 N 筆 trades 當完整 CVD。

## 9. 工作區注意事項

專案：`C:\Users\user\Desktop\CatOS_Astra`

目前 Market Intelligence 相關新檔仍在 working tree，尚未 commit。

另有其他工作流的修改 / 新檔，例如：

```text
WORK_PLAN.md
catos/lot_exposure.py
docs/lot-snapshot-handoff.md
outputs/catos-s6-scenario-assessment.md
outputs/catos-s6-scenario-spec.md
```

這些不是 Yaozi P0-D 的工作內容。不要覆寫、revert、clean 或刪除它們；實作時只做最小 diff。

## 10. 新對話第一個指令

建議直接貼：

```text
請讀取 `outputs/yaozi-handoff-2026-09-18.md`、`outputs/yaozi-functional-parity-spec-v0.1.md`、`docs/market-intel.md` 與 `AGENTS.md`。

延續 catOS × Yaozi Functional Parity 專案，不要重新做 P0-A/B/C。直接執行 P0-D：SMF interface + Flow / Opportunity / Risk lifecycle + deterministic scan transition，使用純 Decimal、三值 missing 語義與 fixture tests；未知的 Yaozi 私有公式/權重不得自行猜測。不要修改金融 Journal schema 7，不接實盤，不讀憑證，不碰工作區中其他任務的修改。
```
