/**
 * catOS Prototype - Core Mock Datasets
 * Consistent data model across all views.
 * Adheres strictly to the quantitative architecture constraints:
 * - Deterministic, consistent figures (no random flickering).
 * - Exact units and decimal precision.
 * - Explicit prototype notices on experimental features.
 */

window.CATOS_DATA = {
  // System Metadata & Status
  meta: {
    platformVersion: 'v1.1.2',
    platformName: 'catOS',
    platformSub: 'Quantitative Trading Workstation',
    currentEnv: 'Demo 模擬盤 (OKX Sandbox)',
    supervisor: {
      status: 'ONLINE',
      pid: 4108,
      latency: '21 ms',
      wsConnection: 'Connected (WSS / OKX-v5)',
      workerState: 'Zero-Net Active',
      memoryUsage: '342 MB',
      uptime: '14天 8小時'
    },
    // Incidents for Vertical Timeline
    incidents: [
      {
        id: 'inc_01',
        time: '11:10:02',
        severity: 'WARN',
        title: 'ETH 震盪網格 Alpha 03 撮合滑價偏離',
        reason: '最近一筆買單成交價滑價達 0.08%，高於預設容忍值 0.05%。已記錄並維持運行。',
        targetBotId: 'bot_eth_grid_03',
        source: 'RiskEngine',
        logQuery: 'bot_eth_grid_03'
      },
      {
        id: 'inc_02',
        time: '10:24:15',
        severity: 'INFO',
        title: '外部 Agent 生成新研究草稿 v1.2-draft',
        reason: 'Antigravity IDE 透過 MCP 提交候選草稿，已隔離儲存於策略中心，未影響在線運行之 v1.1 生產版本。',
        targetBotId: null,
        source: 'MCP-Server',
        logQuery: 'strat_atr_breakout'
      },
      {
        id: 'inc_03',
        time: '09:30:10',
        severity: 'INFO',
        title: 'SOL 試驗波段 04 切換為手動維護停機',
        reason: '操作者於 15m 週期回測校準前手動發出暫停指令，現有持倉保持 FLAT 零部位。',
        targetBotId: 'bot_sol_test_04',
        source: 'Supervisor',
        logQuery: 'bot_sol_test_04'
      }
    ]
  },

  // 1. Strategies Library
  strategies: [
    {
      id: 'strat_atr_breakout',
      name: 'ATR 波動度動量突破',
      symbol: 'BTC-USDT-SWAP',
      timeframe: '1h',
      category: 'Trend Momentum',
      version: 'v1.1',
      candidateDraftVersion: 'v1.2-draft',
      draftAuthor: 'External Agent (Antigravity IDE via MCP)',
      draftTimestamp: '2026-09-29 10:24:15',
      logicSummary: '利用動態 ATR 通道衡量真實波動區間，當突破 K 線收盤確認且成交量放大 1.5 倍時進場。採用 ATR 追蹤停損機制與波段獲利保護。',
      checkStatus: 'Passed', // 'Passed' | 'Warning' | 'Draft'
      checkDetails: 'Decimal 精度驗證通過；無浮點誤差；OKX 委託專屬 Tag 已強制注入；預熱 K 線根數滿足 100 根要求。',
      lastBacktestTime: '2026-09-28 16:45',
      boundBotsCount: 2, // Used in Bot #1 and Bot #2
      boundBots: ['bot_btc_trend_01', 'bot_btc_trend_02'],
      parameters: [
        { name: 'atr_period', type: 'int', defaultVal: 14, currentVal: 20, unit: 'bars', desc: 'ATR 波動率計算週期' },
        { name: 'atr_multiplier', type: 'Decimal', defaultVal: '2.0', currentVal: '2.5', unit: '倍', desc: '進出場通道倍率' },
        { name: 'risk_per_trade', type: 'Decimal', defaultVal: '0.015', currentVal: '0.015', unit: '比率 (1.5%)', desc: '單筆交易最大承擔風險預算' },
        { name: 'trailing_stop_pct', type: 'Decimal', defaultVal: '0.03', currentVal: '0.025', unit: '比率 (2.5%)', desc: '移動追蹤停損觸發門檻' }
      ],
      rules: {
        entryLong: 'Close > (SMA(Close, 20) + 2.5 * ATR(20)) 且 Volume > 1.5 * SMA(Volume, 20)',
        entryShort: 'Close < (SMA(Close, 20) - 2.5 * ATR(20)) 且 Volume > 1.5 * SMA(Volume, 20)',
        exitProfit: '獲利達到 3.0 倍 ATR 或碰觸對向通道邊界',
        exitStop: '進場價反向移動 2.5 * ATR 或追蹤停損回吐 >= 2.5%'
      },
      codeSnippet: `# catOS Quantitative Strategy Module
# Strategy: ATR Volatility Momentum Breakout
# Version: v1.1 [Production Frozen]
# Tag Injection: Mandatory OKX custom order tag

from decimal import Decimal
from catos.core.strategy import BaseStrategy, SignalType, OrderRequest

class ATRBreakoutStrategy(BaseStrategy):
    VERSION = "v1.1"
    TAG_PREFIX = "catos-atr-"

    def __init__(self, ctx, params):
        super().__init__(ctx)
        self.atr_period = int(params.get("atr_period", 20))
        self.atr_multiplier = Decimal(str(params.get("atr_multiplier", "2.5")))
        self.risk_budget = Decimal(str(params.get("risk_per_trade", "0.015")))

    def on_bar(self, bar):
        # Enforce Zero-Float calculation via Decimal
        atr_val = self.indicators.atr(self.atr_period)
        sma_val = self.indicators.sma(self.atr_period)
        upper_band = sma_val + (self.atr_multiplier * atr_val)
        lower_band = sma_val - (self.atr_multiplier * atr_val)

        if bar.close > upper_band and not self.has_position():
            return self.emit_signal(
                signal_type=SignalType.BUY_LONG,
                price=bar.close,
                tag=f"{self.TAG_PREFIX}long",
                reason="Upper band breakthrough"
            )
        elif bar.close < lower_band and not self.has_position():
            return self.emit_signal(
                signal_type=SignalType.SELL_SHORT,
                price=bar.close,
                tag=f"{self.TAG_PREFIX}short",
                reason="Lower band breakdown"
            )
        return None
`,
      historyVersions: [
        { version: 'v1.2-draft', date: '2026-09-29 10:24', author: 'Antigravity MCP Agent', note: '嘗試將 ATR 週期調整為動態自適應 Volatility-Weighted，待檢驗。' },
        { version: 'v1.1', date: '2026-09-24 14:10', author: 'Ryan Cheng', note: '修復 OKX 手續費滑價扣除模型，將浮點全部替換為 Decimal。' },
        { version: 'v1.0', date: '2026-09-10 09:30', author: 'Ryan Cheng', note: '初始正式版本，通過基礎回測與風控鎖存合規檢查。' }
      ]
    },
    {
      id: 'strat_grid_neutral',
      name: 'ETH 震盪中性網格',
      symbol: 'ETH-USDT-SWAP',
      timeframe: '5m',
      category: 'Market Making Grid',
      version: 'v2.0',
      candidateDraftVersion: null,
      logicSummary: '在自適應波動區間內建立等差雙向網格，捕捉 ETH/USDT 震盪行情的點差微利。具備極端單邊行情自動暫停機制。',
      checkStatus: 'Passed',
      checkDetails: '所有價格邊界與保證金計算均為 Decimal；無未捕獲異常；回測成交滑價假設嚴密。',
      lastBacktestTime: '2026-09-27 19:20',
      boundBotsCount: 1,
      boundBots: ['bot_eth_grid_03'],
      parameters: [
        { name: 'grid_count', type: 'int', defaultVal: 30, currentVal: 40, unit: '格', desc: '等差網格層數' },
        { name: 'lower_price', type: 'Decimal', defaultVal: '2800', currentVal: '2900', unit: 'USDT', desc: '網格下邊界價格' },
        { name: 'upper_price', type: 'Decimal', defaultVal: '3600', currentVal: '3500', unit: 'USDT', desc: '網格上邊界價格' }
      ],
      rules: {
        entryLong: '價格下穿網格節點掛單買入',
        entryShort: '價格上穿網格節點掛單賣出',
        exitProfit: '每格獲利達到 0.6% 觸發獲利平倉',
        exitStop: '突破上下邊界 3% 自動啟動保護停損'
      },
      codeSnippet: `# ETH Neutral Adaptive Grid v2.0\n# Production Verified`,
      historyVersions: [
        { version: 'v2.0', date: '2026-09-27 18:00', author: 'Ryan Cheng', note: '加入波動度區間自適應網格寬度算法。' }
      ]
    },
    {
      id: 'strat_funding_arb',
      name: '永續資金費率跨期基差套利',
      symbol: 'BTC-USDT-SWAP / SPOT',
      timeframe: '15m',
      category: 'Arbitrage',
      version: 'v0.9-beta',
      candidateDraftVersion: null,
      logicSummary: '當 OKX 永續合約資金費率偏離現貨基差達到統計顯著水準時，建立現貨做多同時合約做空的Delta中性組合，賺取費率收益。',
      checkStatus: 'Warning',
      checkDetails: '警告：借貸利率模型尚在校準中；現貨與合約雙向撮合存在非同步滑價風險。',
      lastBacktestTime: '2026-09-25 11:15',
      boundBotsCount: 0,
      boundBots: [],
      parameters: [
        { name: 'min_funding_rate', type: 'Decimal', defaultVal: '0.0003', currentVal: '0.00025', unit: '比率 (0.025%)', desc: '最小觸發費率門檻' },
        { name: 'max_basis_spread', type: 'Decimal', defaultVal: '0.001', currentVal: '0.0008', unit: '比率', desc: '最大容忍價差滑價' }
      ],
      rules: {
        entryLong: '預測費率 > 0.025% 且 基差 < 0.08%',
        entryShort: '對沖放空永續合約',
        exitProfit: '收取費率後於費率回歸均值時平倉',
        exitStop: '基差擴大超過 0.5% 時強制平倉'
      },
      codeSnippet: `# Funding Rate Arbitrage Engine v0.9-beta`,
      historyVersions: [
        { version: 'v0.9-beta', date: '2026-09-25 10:00', author: 'Ryan Cheng', note: '初始試驗版本。' }
      ]
    }
  ],

  // Strategy Health Matrix Telemetry
  strategyHealth: [
    { id: 'strat_atr_breakout', name: 'ATR 波動突破', healthScore: 98, latencyMs: 18, slippageBps: 2.1, signals24h: 3, driftPct: '0.00%', status: 'OPTIMAL' },
    { id: 'strat_grid_neutral', name: 'ETH 震盪網格', healthScore: 84, latencyMs: 34, slippageBps: 8.7, signals24h: 38, driftPct: '+0.03%', status: 'WATCH' },
    { id: 'strat_funding_arb', name: '跨期基差套利', healthScore: 65, latencyMs: '—', slippageBps: '—', signals24h: 0, driftPct: '—', status: 'INACTIVE' }
  ],

  // 2. Backtest Records (Bound strictly to Strategy v1.1)
  backtests: [
    {
      id: 'bt_run_20260928_01',
      strategyId: 'strat_atr_breakout',
      strategyVersion: 'v1.1',
      runTimestamp: '2026-09-28 16:45:22',
      status: 'COMPLETED',
      settings: {
        symbol: 'BTC-USDT-SWAP',
        timeframe: '1h',
        startDate: '2025-06-01',
        endDate: '2026-03-01',
        initialCapital: '50000.00',
        makerFee: '0.02%',
        takerFee: '0.05%',
        slippagePct: '0.05%',
        warmupBars: 100
      },
      metrics: {
        initialCapital: '50,000.00 USDT',
        finalEquity: '68,420.50 USDT',
        netProfit: '+18,420.50 USDT',
        netProfitPct: '+36.84%',
        cagr: '+42.15%',
        sharpeRatio: '2.14',
        sortinoRatio: '3.08',
        maxDrawdownPct: '-7.82%',
        maxDrawdownUsdt: '-4,250.00 USDT',
        profitFactor: '1.92',
        winRate: '56.4%',
        totalTrades: 124,
        winningTrades: 70,
        losingTrades: 54,
        avgTradeReturn: '+0.29%',
        maxConsecutiveLosses: 4
      },
      assumptions: '嚴格按 K 線次根 Open 撮合；扣除 0.05% Taker 手續費；模擬 0.05% 衝擊滑價；無前瞻偏差 (No Look-ahead Bias)。',
      equityCurve: [
        { date: '2025-06-01', equity: 50000, drawdown: 0 },
        { date: '2025-07-01', equity: 51800, drawdown: -1.2 },
        { date: '2025-08-01', equity: 53900, drawdown: -0.8 },
        { date: '2025-09-01', equity: 52400, drawdown: -4.5 },
        { date: '2025-10-01', equity: 56200, drawdown: -2.1 },
        { date: '2025-11-01', equity: 59800, drawdown: -1.5 },
        { date: '2025-12-01', equity: 57500, drawdown: -6.4 },
        { date: '2026-01-01', equity: 62100, drawdown: -2.0 },
        { date: '2026-02-01', equity: 65400, drawdown: -3.1 },
        { date: '2026-03-01', equity: 68420.5, drawdown: -1.8 }
      ],
      trades: [
        { id: 'T-124', time: '2026-02-28 14:00', type: 'LONG', entryPrice: '87,420.0', exitPrice: '89,650.0', size: '0.85 BTC', pnl: '+1,895.50 USDT', pnlPct: '+2.55%', fee: '75.25 USDT', holdBars: 18 },
        { id: 'T-123', time: '2026-02-25 08:00', type: 'SHORT', entryPrice: '88,100.0', exitPrice: '88,600.0', size: '0.60 BTC', pnl: '-300.00 USDT', pnlPct: '-0.57%', fee: '52.80 USDT', holdBars: 6 },
        { id: 'T-122', time: '2026-02-21 20:00', type: 'LONG', entryPrice: '84,300.0', exitPrice: '87,200.0', size: '0.90 BTC', pnl: '+2,610.00 USDT', pnlPct: '+3.44%', fee: '77.10 USDT', holdBars: 32 },
        { id: 'T-121', time: '2026-02-18 11:00', type: 'LONG', entryPrice: '85,000.0', exitPrice: '84,200.0', size: '0.75 BTC', pnl: '-600.00 USDT', pnlPct: '-0.94%', fee: '63.40 USDT', holdBars: 12 }
      ]
    },
    {
      id: 'bt_run_20260920_02',
      strategyId: 'strat_atr_breakout',
      strategyVersion: 'v1.0',
      runTimestamp: '2026-09-20 11:20:05',
      status: 'COMPLETED',
      settings: {
        symbol: 'BTC-USDT-SWAP',
        timeframe: '1h',
        startDate: '2025-01-01',
        endDate: '2025-12-31',
        initialCapital: '50000.00',
        makerFee: '0.02%',
        takerFee: '0.05%',
        slippagePct: '0.05%',
        warmupBars: 100
      },
      metrics: {
        initialCapital: '50,000.00 USDT',
        finalEquity: '61,200.00 USDT',
        netProfit: '+11,200.00 USDT',
        netProfitPct: '+22.40%',
        cagr: '+22.40%',
        sharpeRatio: '1.68',
        sortinoRatio: '2.10',
        maxDrawdownPct: '-12.40%',
        maxDrawdownUsdt: '-6,800.00 USDT',
        profitFactor: '1.58',
        winRate: '51.2%',
        totalTrades: 108,
        winningTrades: 55,
        losingTrades: 53,
        avgTradeReturn: '+0.19%',
        maxConsecutiveLosses: 6
      },
      assumptions: 'v1.0 基準測試；採用標準固定手續費。',
      equityCurve: [
        { date: '2025-01-01', equity: 50000, drawdown: 0 },
        { date: '2025-04-01', equity: 52100, drawdown: -3.5 },
        { date: '2025-08-01', equity: 55400, drawdown: -12.4 },
        { date: '2025-12-31', equity: 61200, drawdown: -4.1 }
      ],
      trades: []
    }
  ],

  // 3. Optimization Candidates (Parameter Tuning)
  optimizations: {
    strategyId: 'strat_atr_breakout',
    lastRunTime: '2026-09-28 17:30',
    algorithm: 'Grid Search + Bayesian Pruning',
    totalIterations: 48,
    targetMetric: 'Sharpe Ratio 最大化',
    inSampleRange: '2025-06-01 ~ 2026-01-01 (樣本內訓練)',
    outOfSampleWarning: '⚠️ 僅樣本內 (In-Sample) 擬合結果，未進行 Out-of-Sample 樣本外驗證。請勿直接視為獲利保證。',
    candidates: [
      {
        rank: 1,
        id: 'opt_cand_01',
        isBest: true,
        params: { atr_period: 22, atr_multiplier: '2.3', risk_per_trade: '0.015', trailing_stop_pct: '0.028' },
        sharpeRatio: '2.38',
        netProfitPct: '+41.20%',
        maxDrawdownPct: '-6.45%',
        profitFactor: '2.15',
        winRate: '58.2%',
        tradesCount: 118,
        note: '候選最優參數（過擬合風險：低）'
      },
      {
        rank: 2,
        id: 'opt_cand_02',
        isBest: false,
        params: { atr_period: 20, atr_multiplier: '2.5', risk_per_trade: '0.015', trailing_stop_pct: '0.025' },
        sharpeRatio: '2.14',
        netProfitPct: '+36.84%',
        maxDrawdownPct: '-7.82%',
        profitFactor: '1.92',
        winRate: '56.4%',
        tradesCount: 124,
        note: '當前生產版 v1.1 基準參數 (Baseline)'
      },
      {
        rank: 3,
        id: 'opt_cand_03',
        isBest: false,
        params: { atr_period: 18, atr_multiplier: '2.0', risk_per_trade: '0.020', trailing_stop_pct: '0.020' },
        sharpeRatio: '1.85',
        netProfitPct: '+34.10%',
        maxDrawdownPct: '-11.20%',
        profitFactor: '1.68',
        winRate: '53.1%',
        tradesCount: 142,
        note: '交易次數偏多，手續費損耗較高'
      },
      {
        rank: 4,
        id: 'opt_cand_04',
        isBest: false,
        params: { atr_period: 26, atr_multiplier: '2.8', risk_per_trade: '0.015', trailing_stop_pct: '0.035' },
        sharpeRatio: '1.74',
        netProfitPct: '+28.50%',
        maxDrawdownPct: '-8.10%',
        profitFactor: '1.62',
        winRate: '54.5%',
        tradesCount: 88,
        note: '過濾較嚴格，錯失中型波段'
      }
    ]
  },

  // 4. Bots Fleet (Strict v1: Exactly 3 Bots per user spec, Coherent with 2026-09-29 11:15:33 UTC+8)
  bots: [
    {
      id: 'bot_btc_trend',
      name: 'BTC 趨勢突破主線',
      strategyName: 'ATR 動量突破',
      strategyVersion: 'v1.1',
      boundStrategyVersion: 'ATR 動量突破 · v1.1',
      symbol: 'BTC-USDT-SWAP',
      timeframe: '15m',
      status: 'RUNNING', // 運行中 (綠色)
      position: {
        direction: '多',
        amount: '0.20 BTC',
        entryPrice: '88,120.0 USDT',
        markPrice: '88,960.0 USDT',
        valuationTime: '11:15:00',
        unrealizedPnl: '+168.00 USDT',
        unrealizedPnlPct: '+0.95%',
        leverage: '2.0x'
      },
      dailyPnl: '+812.40 USDT',
      lastBarTime: '11:00:00',
      lastBarDate: '2026-09-29',
      lastBarRelative: '15 分鐘前',
      isBarStale: false,
      incidentNotice: null,
      events: [
        {
          time: '11:00:00',
          severity: 'INFO',
          summary: '多頭部位續抱',
          observed: '收盤價 88,960 USDT 高於通道上軌 88,150 USDT',
          condition: 'Close > UpperBand 且持倉部位處於獲利保護區間',
          detail: '收盤 88,960 USDT > 通道上軌 88,150 USDT。動態追蹤停損依 ATR 波動值自動提升至 87,800 USDT。'
        },
        {
          time: '10:00:00',
          severity: 'INFO',
          summary: '追蹤停損上移',
          observed: 'ATR(20) = 1,420 USDT，價位已脫離進場成本 840 USDT',
          condition: '波段獲利超過 1.5 ATR 觸發移動防守線提升',
          detail: '依據 ATR(20)=1,420 波動值，防守停損線從 87,500 上推至 87,800 USDT。'
        },
        {
          time: '09-28 22:00',
          severity: 'INFO',
          summary: '突破信號進場買入',
          observed: '成交均價 88,120.0 USDT，數量 0.20 BTC',
          condition: '15m K 線收盤確認突破動量通道上邊界',
          detail: '通道突破收盤確認，發出 0.20 BTC 買入委託並完全撮合成交。'
        }
      ],
      orders: [
        { time: '2026-09-28 22:00:02', side: '買入', status: '完全成交', size: '0.20 BTC', avgPrice: '88,120.0 USDT', fee: '3.52 USDT' },
        { time: '2026-09-27 14:15:30', side: '賣出', status: '完全成交', size: '0.20 BTC', avgPrice: '87,450.0 USDT', fee: '3.50 USDT' }
      ]
    },
    {
      id: 'bot_eth_grid',
      name: 'ETH 動態震盪網格',
      strategyName: '均值回歸',
      strategyVersion: 'v0.8',
      boundStrategyVersion: '均值回歸 · v0.8',
      symbol: 'ETH-USDT-SWAP',
      timeframe: '1h',
      status: 'WARNING', // 需處理 (琥珀色)
      position: {
        direction: '空',
        amount: '2.40 ETH',
        entryPrice: '3,150.00 USDT',
        markPrice: '3,180.50 USDT',
        valuationTime: '11:15:00',
        unrealizedPnl: '-73.20 USDT',
        unrealizedPnlPct: '-0.97%',
        leverage: '1.5x'
      },
      dailyPnl: '-318.20 USDT',
      lastBarTime: '11:00:00',
      lastBarDate: '2026-09-29',
      lastBarRelative: '15 分鐘前',
      isBarStale: false,
      incidentNotice: '滑價連續 3 次超過策略預期區間',
      events: [
        {
          time: '10:42:18',
          severity: 'WARN',
          summary: '滑價連續 3 次超過策略預期區間',
          observed: '平均滑價 0.082% (容忍上限 0.050%)',
          condition: '最近 3 筆 Taker 撮合成交價偏離深度中價 > 5 bps',
          detail: '最近 3 筆網格買入觸發之撮合成交價偏離 0.082%，高於預設容忍值 0.050%。維持部位鎖存運行並觸發預警。'
        },
        {
          time: '10:00:00',
          severity: 'INFO',
          summary: '網格空頭掛單成交',
          observed: '價格上穿 3,150.00 USDT 節點',
          condition: '觸及均值回歸上方網格賣出壓力帶',
          detail: '價格回升碰觸 3,150.00 節點，撮合成交空單 2.40 ETH。'
        }
      ],
      orders: [
        { time: '2026-09-29 10:42:18', side: '買入', status: '部分成交', size: '1.20 ETH', avgPrice: '3,180.50 USDT', fee: '0.76 USDT' },
        { time: '2026-09-29 10:00:02', side: '賣出', status: '完全成交', size: '2.40 ETH', avgPrice: '3,150.00 USDT', fee: '1.51 USDT' }
      ]
    },
    {
      id: 'bot_sol_swing',
      name: 'SOL 波段跟隨',
      strategyName: '趨勢跟隨',
      strategyVersion: 'draft-derived fixed version',
      boundStrategyVersion: '趨勢跟隨 · draft-derived fixed version',
      symbol: 'SOL-USDT-SWAP',
      timeframe: '5m',
      status: 'STOPPED', // 已停止 (中性灰，非故障)
      position: {
        direction: '空倉',
        amount: '—',
        entryPrice: '—',
        markPrice: '194.50 USDT',
        valuationTime: '09:30:00',
        unrealizedPnl: '0.00 USDT',
        unrealizedPnlPct: '0.00%',
        leverage: '—'
      },
      dailyPnl: '0.00 USDT',
      lastBarTime: '09:30:00',
      lastBarDate: '2026-09-29',
      lastBarRelative: '1 小時 45 分鐘前',
      isBarStale: false,
      incidentNotice: null,
      events: [
        {
          time: '09:30:00',
          severity: 'INFO',
          summary: '操作者正常維護停機',
          observed: '持倉部位平倉至 0.00 SOL (FLAT)',
          condition: '操作者於 5m 週期回測校準前發出手動暫停指令',
          detail: '操作者手動將 Bot 設為停機狀態進行模型週期校準，部位已全數了結並鎖存。'
        }
      ],
      orders: []
    }
  ],

  // 5. Risk Control Engine Data (Strict CatOS Spec)
  risk: {
    effectiveLeverage: '1.85x',
    maxAllowedLeverage: '3.00x',
    totalAccountEquity: '125,480.50 USDT',
    totalPositionValue: '232,138.00 USDT',
    dailyLoss: '-380.00 USDT',
    dailyLossPct: '-0.30%',
    softLossThreshold: '-12,500.00 USDT (-9.96%)',
    hardLossThreshold: '-18,800.00 USDT (-14.98%)',
    latchState: 'NORMAL', // 'NORMAL' | 'SOFT_LATCH' | 'HARD_LATCH'
    latchReason: '無違規觸發。日損在正常安全閥值範圍內。',
    lastLatchEvent: '2026-09-18 14:02:11 (前次 Soft-Trip 已於人工審核後手動解除)',
    assetAllocations: [
      { asset: 'BTC', currentExposure: '48.5%', budgetLimit: '50.0%', status: 'Normal', valueUsdt: '112,500.00 USDT' },
      { asset: 'ETH', currentExposure: '34.2%', budgetLimit: '40.0%', status: 'Normal', valueUsdt: '79,400.00 USDT' },
      { asset: 'USDT (現金緩衝)', currentExposure: '17.3%', budgetLimit: '>= 15.0%', status: 'Safe', valueUsdt: '40,238.50 USDT' }
    ],
    // Editable settings draft
    settings: {
      softLossPct: '10.0',
      hardLossPct: '15.0',
      maxLeverage: '3.0',
      maxSingleAssetExposurePct: '50.0',
      maxSingleTradeRiskPct: '2.0',
      circuitBreakerCoolDownMins: 60
    }
  },

  // 6. Logs & Audits
  logs: [
    {
      id: 'log_901',
      timestamp: '2026-09-29 11:12:44',
      severity: 'INFO',
      source: 'Supervisor',
      category: 'ORDER_ROUTE',
      target: 'bot_btc_trend_01',
      summary: 'OKX WebSocket 行情報文心跳正常 (Latency: 21ms)',
      details: {
        event: 'HEARTBEAT_ACK',
        channel: 'ws/v5/public:tickers',
        latency_ms: 21,
        supervisor_pid: 4108,
        active_subscriptions: ['BTC-USDT-SWAP', 'ETH-USDT-SWAP']
      }
    },
    {
      id: 'log_902',
      timestamp: '2026-09-29 11:10:02',
      severity: 'WARN',
      source: 'RiskEngine',
      category: 'SLIPPAGE_DETECT',
      target: 'bot_eth_grid_03',
      summary: '檢測到成交滑價 0.08% > 預設容忍值 0.05%',
      details: {
        bot_id: 'bot_eth_grid_03',
        symbol: 'ETH-USDT-SWAP',
        intended_price: '3082.5',
        filled_price: '3085.2',
        slippage_bps: 8.7,
        warning_level: 'SOFT_WARN',
        action_taken: 'LOGGED_AND_CONTINUED'
      }
    },
    {
      id: 'log_903',
      timestamp: '2026-09-29 10:24:15',
      severity: 'INFO',
      source: 'MCP-Server',
      category: 'AGENT_RESEARCH',
      target: 'strat_atr_breakout',
      summary: '外部 Agent (Antigravity IDE) 提交新策略草稿 v1.2-draft',
      details: {
        mcp_client: 'Google Antigravity IDE (Candidate)',
        action: 'PROPOSE_STRATEGY_DRAFT',
        draft_version: 'v1.2-draft',
        target_strategy: 'strat_atr_breakout',
        isolated: true,
        production_frozen: true,
        note: '未改動正在運行之 Bot #1, #2 綁定之 v1.1 生產版本'
      }
    },
    {
      id: 'log_904',
      timestamp: '2026-09-29 09:30:10',
      severity: 'WARN',
      source: 'Supervisor',
      category: 'BOT_STOP',
      target: 'bot_sol_test_04',
      summary: '操作者手動將 SOL 試驗波段 04 切換為 STOPPED 狀態',
      details: {
        bot_id: 'bot_sol_test_04',
        operator: 'Ryan Cheng',
        reason: '進行 15m 週期模型回測校準'
      }
    },
    {
      id: 'log_905',
      timestamp: '2026-09-28 17:30:00',
      severity: 'INFO',
      source: 'Worker-01',
      category: 'OPTIMIZATION',
      target: 'strat_atr_breakout',
      summary: '網格參數優化任務完成 (48 次迭代，耗時 32.4s)',
      details: {
        strategy_id: 'strat_atr_breakout',
        best_candidate: 'opt_cand_01',
        best_sharpe: 2.38,
        in_sample_window: '2025-06-01~2026-01-01'
      }
    }
  ],

  // 7. Yaozi Market Intelligence (Separate first-class sidebar item)
  yaozi: [
    {
      id: 'yz_item_01',
      title: 'OKX BTC 永續合約資金費率異常飆升警訊',
      source: 'OKX 資金費率監控引擎',
      timestamp: '2026-09-29 10:45:00',
      categoryTag: '[待確認示意: 費率偏離]',
      urgency: 'HIGH',
      summary: 'BTC 永續合約年化資金費率於過去 4 小時急升至 +42.5%，顯示市場短線多頭槓桿過熱，基差擴大至 120 點。',
      analysisDetail: `【情報深度分析】
1. 觀察現狀：過去 4 小時 OKX BTC-USDT-SWAP 8 小時預測費率從 0.01% 快速飆升至 0.038%（折合年化超過 40%）。
2. 市場結構：現貨價格滯漲於 88,800~89,200 區間，合約未平倉量 (OI) 增加 8,400 BTC，顯示主動多單多為合約投機資金推進。
3. 歷史相似事件對比：在 2025 年 11 月出現類似極端費率時，市場在 24 小時內發生多頭槓桿擠壓回撤 -3.8%。
4. 衍生研究建議：可於策略中心調研「反向資金費率動態冷卻」濾網，在費率超過 0.03% 時調降突破進場追價槓桿。

【架構邊界嚴格說明】
⚠️ 本情報僅供量化策略研究員手動參考，未直連自動交易管線，系統不會自動修改任何策略參數或觸發委託。`,
      metrics: {
        annualizedRate: '+42.5%',
        basisSpread: '+120.5 USDT',
        oiChange24h: '+8,420 BTC',
        spotVolumeRatio: '0.38 (合約主導)'
      }
    },
    {
      id: 'yz_item_02',
      title: 'ETH 鏈上大額巨鯨集中轉入主要交易所',
      source: '鏈上標記地址追蹤節點',
      timestamp: '2026-09-29 08:30:00',
      categoryTag: '[待確認示意: 鏈上異動]',
      urgency: 'MEDIUM',
      summary: '監測到標記為 0x3f...e82 之大型巨鯨地址於 1 小時內向 OKX 與 Binance 轉入 45,000 ETH，潛在潛伏現貨拋壓。',
      analysisDetail: `【情報深度分析】
1. 轉入規模：合計 45,000 ETH（市值約 1.39 億 USDT）。
2. 地址歷史行為：該地址建倉時間為 2024 年底均價 2,450 USDT，此前兩次大額轉入交易所後 12 小時內均出現現貨大單分批市價委託。
3. 策略影響評估：運行中之「ETH 震盪網格 Alpha 03」下軌設為 2,900 USDT，尚有 6.2% 安全空間，但建議關注網格單邊多頭曝險。`,
      metrics: {
        transferAmount: '45,000 ETH',
        historicalImpact: '前次現貨均價回調 -2.4%',
        walletBalanceRemaining: '12,500 ETH'
      }
    },
    {
      id: 'yz_item_03',
      title: 'Deribit 期權隱含波動率 (IV) 期限結構呈現倒掛',
      source: '期權波動率曲面追蹤',
      timestamp: '2026-09-28 20:15:00',
      categoryTag: '[待確認示意: 波動率異動]',
      urgency: 'LOW',
      summary: '短期（7 天期）ATM 隱含波動率升至 68%，高於 30 天期之 54%，形成短端波動率陡峭倒掛，預示重大事件窗口即將來臨。',
      analysisDetail: `【情報深度分析】
1. 倒掛幅度：7D IV (68%) - 30D IV (54%) = +14% 倒掛。
2. 事件窗口：預計與本週五聯準會降息會議及大額季度交割結算重疊。
3. 研究價值：ATR 策略可觀察波動率擴張帶來的波段信號有效性。`,
      metrics: {
        shortTermIV: '68.2%',
        longTermIV: '54.1%',
        ivInversionSpread: '+14.1%'
      }
    }
  ],

  // 8. Settings & MCP Integration Concepts
  settings: {
    mcp: {
      serverStatus: 'ENABLED_LOCAL_ONLY',
      listenEndpoint: 'stdio / stdio:catos-mcp-daemon',
      authTokenConfigured: false,
      evaluationNotice: '⚠️ 外部 Agent 連線功能目前處於架構驗證階段 (Evaluation Pending)，未開啟自動修改策略或下單權限。',
      clients: [
        {
          id: 'client_antigravity',
          name: 'Google Antigravity IDE',
          role: 'Quantitative Co-pilot / Code Generation',
          compatibilityStatus: '相容性待驗證 (Evaluation Pending)',
          statusBadge: 'Evaluation Pending',
          permissions: 'Read-only Strategy DSL, Emit Draft Proposals (Isolated)',
          lastPing: '2026-09-29 10:24 (Draft Proposed)'
        },
        {
          id: 'client_codex',
          name: 'OpenAI Operator / Codex',
          role: 'Backtest Analysis & Report Generation',
          compatibilityStatus: '相容性待驗證 (Evaluation Pending)',
          statusBadge: 'Evaluation Pending',
          permissions: 'Query Historical Backtests, Generate Markdown Summaries',
          lastPing: '— (未連線)'
        },
        {
          id: 'client_deepseek',
          name: 'DeepSeek Harness',
          role: 'Parameter Surface Search & Reasoning',
          compatibilityStatus: '相容性待驗證 (Evaluation Pending)',
          statusBadge: 'Evaluation Pending',
          permissions: 'Invoke Optimization Search Engine',
          lastPing: '— (未連線)'
        }
      ]
    }
  }
};
