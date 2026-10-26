/**
 * Realistic Mock Data matching catOS invariants & catOS-Frontend-Final specifications
 */
import type {
  DashboardKPIs,
  EquityPoint,
  ResearchTask,
  YaoziAlert
} from '@/adapters/types';
import type {
  RiskState,
  ExposureAllocationItem,
  AuditLogItem,
  Bot,
  StrategyEntry,
  SimulationRun,
  TelemetryState
} from '@/contracts';

export const mockTelemetry: TelemetryState = {
  connected: true,
  supervisor_pid: 4821,
  latency_ms: 16,
  fixed_tag_active: true,
  settlement_mode: 'cross_net_mode',
  core_arithmetic: 'Decimal_SQLite_TEXT',
  last_heartbeat: new Date().toISOString(),
};

export const normalKPIs: DashboardKPIs = {
  total_equity: '125480.50',
  equity_change_pct: '+1.00%',
  today_pnl: '+1240.80',
  today_pnl_pct: '+1.00%',
  running_bots_count: 1,
  total_bots_count: 3,
  bots_summary_note: '1 運行中 · 1 需處理 · 1 已停止',
  risk_status: 'NORMAL',
  effective_leverage: '1.85',
  leverage_limit: '3.00',
  risk_sub_note: '日損軟限 10.0% · 當前回撤 -0.30%',
};

export const softLossKPIs: DashboardKPIs = {
  total_equity: '112850.00',
  equity_change_pct: '-10.06%',
  today_pnl: '-12630.50',
  today_pnl_pct: '-10.06%',
  running_bots_count: 1,
  total_bots_count: 3,
  bots_summary_note: '1 軟限受阻 · 0 新增 · 2 已停止',
  risk_status: 'SOFT_LATCH',
  effective_leverage: '1.20',
  leverage_limit: '3.00',
  risk_sub_note: '日損已達 10.0% 軟限 · 禁止增倉 · 僅許合法平倉',
};

export const holdStoppedKPIs: DashboardKPIs = {
  total_equity: '124110.20',
  equity_change_pct: '-0.10%',
  today_pnl: '-120.40',
  today_pnl_pct: '-0.10%',
  running_bots_count: 0,
  total_bots_count: 3,
  bots_summary_note: '0 運行中 · 1 停止持倉(409) · 2 已停止',
  risk_status: 'NORMAL',
  effective_leverage: '0.80',
  leverage_limit: '3.00',
  risk_sub_note: '合約 BTC-USDT 獨佔保留 (-1 張) · 禁新分配',
};

export const emptyKPIs: DashboardKPIs = {
  total_equity: '--',
  equity_change_pct: '0.00%',
  today_pnl: '--',
  today_pnl_pct: '0.00%',
  running_bots_count: 0,
  total_bots_count: 0,
  bots_summary_note: '無部署機器人',
  risk_status: 'MISSING',
  effective_leverage: '--',
  leverage_limit: '3.00',
  risk_sub_note: '無帳戶連線或資料缺失',
};

export const mockEquity1D: EquityPoint[] = [
  { timestamp: '2026-10-03T00:00:00Z', timeLabel: '00:00', equity: 124950, equity_str: '124950.50' },
  { timestamp: '2026-10-03T04:00:00Z', timeLabel: '04:00', equity: 125020, equity_str: '125020.00' },
  { timestamp: '2026-10-03T08:00:00Z', timeLabel: '08:00', equity: 125180, equity_str: '125180.20' },
  { timestamp: '2026-10-03T12:00:00Z', timeLabel: '12:00', equity: 125110, equity_str: '125110.80' },
  { timestamp: '2026-10-03T16:00:00Z', timeLabel: '16:00', equity: 125340, equity_str: '125340.00' },
  { timestamp: '2026-10-03T20:00:00Z', timeLabel: '20:00', equity: 125420, equity_str: '125420.30' },
  { timestamp: '2026-10-03T23:59:00Z', timeLabel: '23:59', equity: 125480, equity_str: '125480.50' },
];

export const mockEquity7D: EquityPoint[] = [
  { timestamp: '2026-09-27T00:00:00Z', timeLabel: '09/27', equity: 122100, equity_str: '122100.00' },
  { timestamp: '2026-09-28T00:00:00Z', timeLabel: '09/28', equity: 122850, equity_str: '122850.20' },
  { timestamp: '2026-09-29T00:00:00Z', timeLabel: '09/29', equity: 123400, equity_str: '123400.80' },
  { timestamp: '2026-09-30T00:00:00Z', timeLabel: '09/30', equity: 123150, equity_str: '123150.40' },
  { timestamp: '2026-10-01T00:00:00Z', timeLabel: '10/01', equity: 124200, equity_str: '124200.00' },
  { timestamp: '2026-10-02T00:00:00Z', timeLabel: '10/02', equity: 124950, equity_str: '124950.50' },
  { timestamp: '2026-10-03T00:00:00Z', timeLabel: '10/03', equity: 125480, equity_str: '125480.50' },
];

export const mockEquity30D: EquityPoint[] = [
  { timestamp: '2026-09-03T00:00:00Z', timeLabel: '09/03', equity: 115000, equity_str: '115000.00' },
  { timestamp: '2026-09-10T00:00:00Z', timeLabel: '09/10', equity: 118400, equity_str: '118400.00' },
  { timestamp: '2026-09-17T00:00:00Z', timeLabel: '09/17', equity: 119800, equity_str: '119800.00' },
  { timestamp: '2026-09-24T00:00:00Z', timeLabel: '09/24', equity: 121500, equity_str: '121500.00' },
  { timestamp: '2026-10-03T00:00:00Z', timeLabel: '10/03', equity: 125480, equity_str: '125480.50' },
];

export const mockEquity90D: EquityPoint[] = [
  { timestamp: '2026-07-03T00:00:00Z', timeLabel: '07/03', equity: 100000, equity_str: '100000.00' },
  { timestamp: '2026-08-03T00:00:00Z', timeLabel: '08/03', equity: 108500, equity_str: '108500.00' },
  { timestamp: '2026-09-03T00:00:00Z', timeLabel: '09/03', equity: 115000, equity_str: '115000.00' },
  { timestamp: '2026-10-03T00:00:00Z', timeLabel: '10/03', equity: 125480, equity_str: '125480.50' },
];

export const mockExposureAllocation: ExposureAllocationItem[] = [
  { label: 'BTC 永續持倉', nominal_usdt: '596.60', pct_share: 42, color: '#dcb347' },
  { label: '委託在途凍結', nominal_usdt: '213.08', pct_share: 15, color: '#58a6ff' },
  { label: '未佔用可用額度', nominal_usdt: '610.82', pct_share: 43, color: '#2ea043' },
];


export const mockAuditEvents: AuditLogItem[] = [
  {
    id: 'evt-001',
    timestamp: '11:10:02',
    level: 'WARN',
    category: 'RISK',
    message: 'ETH 震盪網格 Alpha 03 撮合滑價偏離',
    details: {
      description: '最近一筆買單成交價滑價達 0.08%，高於預設容忍值 0.05%。已記錄並維持運行。',
      source: 'RiskEngine',
      bot_name: 'ETH 震盪網格 Alpha 03',
      symbol: 'ETH-USDT-SWAP',
      slippage_pct: '0.08%',
      tolerance_pct: '0.05%'
    }
  },
  {
    id: 'evt-002',
    timestamp: '10:24:15',
    level: 'INFO',
    category: 'ORDER',
    message: '外部 Agent 生成新研究草稿 v1.2-draft',
    details: {
      description: '已完成過去 30 日收盤 K 線參數搜尋，Sharpe 達 2.14。',
      source: 'ResearchAgent',
      sharpe: '2.14',
      version: 'v1.2-draft'
    }
  },
  {
    id: 'evt-003',
    timestamp: '09:30:10',
    level: 'INFO',
    category: 'WORKER',
    message: 'SOL 試驗波段 04 切換為手動維護停機',
    details: {
      description: '收到交易員手動指令，已撤銷在途限價委託，維持空倉等待重啟。',
      source: 'Supervisor',
      bot_id: 'bot-sol-04',
      action: 'MANUAL_STOP'
    }
  },
  {
    id: 'evt-004',
    timestamp: '08:15:00',
    level: 'INFO',
    category: 'SYSTEM',
    message: 'Supervisor 外部流水與帳戶權益對帳通過',
    details: {
      description: '白名單外部出入金審查無未知資金漂移，當前權益 1,000.00 USDT。',
      source: 'AccountRecon',
      whitelist_status: 'VERIFIED'
    }
  },
  {
    id: 'evt-005',
    timestamp: '00:00:01',
    level: 'INFO',
    category: 'RISK',
    message: 'Asia/Taipei 00:00 每日切日對帳成功',
    details: {
      description: '完成日初固定基準權益鎖存，日損軟限 -10.0%、硬限 -20.0% 守護重置。',
      source: 'RiskSentinel',
      base_equity: '1000.00 USDT'
    }
  }
];

export const mockNormalRiskState: RiskState = {
  status: 'normal',
  fixed_tag_active: true,
  effective_leverage: '1.85',
  leverage_limit: '3.00',
  single_asset_budget_ratio: '0.50',
  day_start_equity_usdt: '1000.00',
  current_equity_usdt: '1018.42',
  daily_pnl_usdt: '+18.42',
  daily_pnl_pct: '+1.84%',
  soft_loss_limit_pct: '-10.0%',
  hard_loss_limit_pct: '-20.0%',
  current_drawdown_pct: '-0.30%',
  exposure_nominal_usdt: '1420.50',
  exposure_budget_usdt: '3000.00',
  margin_used_usdt: '450.20',
  margin_available_usdt: '550.00',
  latched_reasons: []
};

export const mockBots: Bot[] = [
  {
    bot_id: 'bot-btc-trend-01',
    name: 'BTC 趨勢突破主線',
    symbol: 'BTC-USDT-SWAP',
    mode: 'local',
    binding: {
      artifact: {
        contract: 'catos.python-strategy.v1',
        strategy_id: 'trend_breakout_v1',
        version: 'v1_2_0',
        name: 'BTC 趨勢突破主線',
        description: '基於收盤 K 線通道突破的雙向順勢策略',
        source: 'class Strategy:\n    def __init__(self, parameters):\n        self.parameters = parameters\n    def update_indicators(self, bar):\n        pass\n    def ready(self):\n        return True\n    def on_bar(self, bar, account):\n        return None\n    def snapshot_state(self):\n        return {}\n    def restore_state(self, state):\n        pass',
        defaults: { period: '1H', lookback: 20 },
        warmup_bars: 8
      },
      artifact_hash: 'c70ea9157d376b2fb9e74be25d033f12af1195e6b2a415df762e07024e2fb834',
      parameters: { period: '1H', lookback: 20 }
    },
    trusted: true,
    created_at: '2026-10-02T10:00:00Z',
    state: 'running',
    current_run_id: 'run-88219',
    pnl_usdt: '+812.40',
    position_contracts: '1',
    side: 'long',
    timeframe: '1H',
    next_bar_countdown: '14:22',
    nominal_value_usdt: '64,850.00',
    margin_usdt: '450.20',
    leverage: '3.0x',
    entry_price: '63,200.00',
    mark_price: '64,850.00',
    sl_price: '60,040.00',
    sl_distance_pct: 7.4,
    roe_pct: '+12.85%',
    worker_pid: 4821,
    worker_cpu: '0.6%',
    worker_rss: '32.8 MB',
    ipc_heartbeat_ago: '1s 前',
    strategy_step: '等待收盤 K 線 (Waiting Closed Bar)',
    recent_signals: [
      { bar_time: '22:00:00', signal: 'HOLD', close_price: '64,850.00', pnl_delta: '+62.40', note: '多頭結構完整，持續抱牢' },
      { bar_time: '21:00:00', signal: 'BUY', close_price: '63,200.00', pnl_delta: '0.00', note: '上軌帶量突破，開多 1 張' }
    ]
  },
  {
    bot_id: 'bot-eth-grid-02',
    name: 'ETH 動態震盪網格',
    symbol: 'ETH-USDT-SWAP',
    mode: 'local',
    binding: {
      artifact: {
        contract: 'catos.python-strategy.v1',
        strategy_id: 'dynamic_grid_v2',
        version: 'v2_0_1',
        name: 'ETH 動態震盪網格',
        description: '高頻波動區間網格捕捉策略',
        source: 'class Strategy:\n    def __init__(self, parameters):\n        self.parameters = parameters\n    def update_indicators(self, bar):\n        pass\n    def ready(self):\n        return True\n    def on_bar(self, bar, account):\n        return None\n    def snapshot_state(self):\n        return {}\n    def restore_state(self, state):\n        pass',
        defaults: { grid_steps: 10 },
        warmup_bars: 8
      },
      artifact_hash: '37e9e3582fd678d1fd0c7c1521ed70f5d4c670400ed8506831fb7bb18192ecc3',
      parameters: { grid_steps: 10 }
    },
    trusted: true,
    created_at: '2026-10-02T11:00:00Z',
    state: 'running',
    current_run_id: 'run-88220',
    pnl_usdt: '+120.60',
    position_contracts: '-2',
    side: 'short',
    timeframe: '15m',
    next_bar_countdown: '03:45',
    nominal_value_usdt: '6,900.00',
    margin_usdt: '220.00',
    leverage: '2.0x',
    entry_price: '3,480.00',
    mark_price: '3,450.00',
    sl_price: '3,620.00',
    sl_distance_pct: 4.9,
    roe_pct: '+3.47%',
    worker_pid: 4822,
    worker_cpu: '1.2%',
    worker_rss: '41.5 MB',
    ipc_heartbeat_ago: '2s 前',
    strategy_step: '網格震盪對沖中 (Grid Hedging)',
    recent_signals: [
      { bar_time: '22:15:00', signal: 'HOLD', close_price: '3,450.00', pnl_delta: '+15.00', note: '震盪下緣支撐測試中' },
      { bar_time: '22:00:00', signal: 'SELL', close_price: '3,480.00', pnl_delta: '0.00', note: '觸發網格上軌阻力做空' }
    ]
  },
  {
    bot_id: 'bot-sol-momentum-04',
    name: 'SOL 動量通道追蹤',
    symbol: 'SOL-USDT-SWAP',
    mode: 'local',
    binding: {
      artifact: {
        contract: 'catos.python-strategy.v1',
        strategy_id: 'momentum_channel_v1',
        version: 'v1_0_0',
        name: 'SOL 動量通道追蹤',
        description: '4H 級別大週期趨勢突破過濾策略',
        source: 'class Strategy:\n    def __init__(self, parameters):\n        pass',
        defaults: { period: '4H' },
        warmup_bars: 12
      },
      artifact_hash: '59a112fc78819034aa109b02319efcd481023910efcd3451092389102481023a',
      parameters: { period: '4H' }
    },
    trusted: true,
    created_at: '2026-10-02T13:00:00Z',
    state: 'running',
    current_run_id: 'run-88221',
    pnl_usdt: '0.00',
    position_contracts: '0',
    side: 'flat',
    timeframe: '4H',
    next_bar_countdown: '02:18:10',
    nominal_value_usdt: '0.00',
    margin_usdt: '0.00',
    leverage: '3.0x',
    entry_price: '--',
    mark_price: '158.40',
    sl_price: '--',
    sl_distance_pct: 0,
    roe_pct: '0.00%',
    worker_pid: 4824,
    worker_cpu: '0.2%',
    worker_rss: '28.1 MB',
    ipc_heartbeat_ago: '3s 前',
    strategy_step: '指標預熱完成，空倉巡航中 (Idle Scanning)',
    recent_signals: [
      { bar_time: '20:00:00', signal: 'HOLD', close_price: '158.40', pnl_delta: '0.00', note: '未達突破閾值，維持空倉' }
    ]
  },
  {
    bot_id: 'bot-doge-reversion-03',
    name: 'DOGE 波動均值回歸',
    symbol: 'DOGE-USDT-SWAP',
    mode: 'local',
    binding: {
      artifact: {
        contract: 'catos.python-strategy.v1',
        strategy_id: 'mean_reversion_v1',
        version: 'v1_1_0',
        name: 'DOGE 波動均值回歸',
        description: '極端乖離回測短線策略',
        source: 'class Strategy:\n    def __init__(self, parameters):\n        pass',
        defaults: { period: '1H' },
        warmup_bars: 6
      },
      artifact_hash: '8bb79f5f0bca9076c1006815bdae7846bbb6ca4446ec50740a50650ef8200aca',
      parameters: { period: '1H' }
    },
    trusted: true,
    created_at: '2026-10-02T12:00:00Z',
    state: 'running',
    current_run_id: 'run-88222',
    pnl_usdt: '-25.00',
    position_contracts: '-10',
    side: 'short',
    timeframe: '1H',
    next_bar_countdown: '14:22',
    nominal_value_usdt: '1,345.00',
    margin_usdt: '90.00',
    leverage: '2.0x',
    entry_price: '0.1320',
    mark_price: '0.1345',
    sl_price: '0.1386',
    sl_distance_pct: 3.0,
    roe_pct: '-1.86%',
    worker_pid: 4823,
    worker_cpu: '0.4%',
    worker_rss: '29.4 MB',
    ipc_heartbeat_ago: '1s 前',
    strategy_step: '逆勢回歸監控中，逼近預警線 (Alert Monitoring)',
    recent_signals: [
      { bar_time: '22:00:00', signal: 'HOLD', close_price: '0.1345', pnl_delta: '-12.50', note: '回歸延遲，密切監控 P6 防線' }
    ]
  }
];

export const mockResearchTasks: ResearchTask[] = [
  {
    id: 'res-01',
    name: 'ATR 動量突破',
    version: 'v1.1',
    status: 'COMPLETED',
    progress_pct: 100,
    sharpe: '2.14',
    description: '完成 100% · 樣本內回測淨值穩健向上'
  },
  {
    id: 'res-02',
    name: '參數網格優化 (48 迭代)',
    version: 'v2.0-beta',
    status: 'RUNNING',
    progress_pct: 75,
    sharpe: '2.38',
    description: '候選最優解 Sharpe 2.38 · 耗時 18s'
  }
];

export const mockYaoziAlerts: YaoziAlert[] = [
  {
    id: 'yz-01',
    time: '10:45',
    type: '費率偏離',
    title: 'BTC 資金費率正向擴大至 0.035%',
    tag: '市場情報',
    status: 'ACTIVE',
    summary: 'OKX BTC-USDT 永續資金費率達 +0.035%，預警多頭擁擠與基差收斂風險'
  },
  {
    id: 'yz-02',
    time: '09:30',
    type: '巨鯨異動',
    title: 'ETH 鏈上大額質押贖回',
    tag: '市場情報',
    status: 'ACTIVE',
    summary: '15,000 ETH 自 Lido 質押合約贖回轉至交易所，監控潛在拋壓流動性'
  },
  {
    id: 'yz-03',
    time: '08:30',
    type: '宏觀資金',
    title: '大額 USDT 轉入交易所熱錢包',
    tag: '市場情報',
    status: 'ACTIVE',
    summary: '4,200 萬 USDT 自金庫轉入交易所熱錢包，市場流動性注入'
  },
  {
    id: 'yz-04',
    time: '07:15',
    type: '鏈上活躍',
    title: 'SOL 鏈上交易量急遽增長 18%',
    tag: '市場情報',
    status: 'ACTIVE',
    summary: 'DEX 聚合交易量創日內新高，短線波動度預期放大'
  }
];

export const mockStrategies: StrategyEntry[] = [
  {
    artifact: {
      contract: 'catos.python-strategy.v1',
      strategy_id: 'trend_breakout_v1',
      version: 'v1_2_0',
      name: 'BTC 趨勢突破主線',
      description: '基於收盤 K 線通道突破的雙向順勢策略',
      source: `class Strategy:
    def __init__(self, parameters):
        self.parameters = parameters
    def update_indicators(self, bar):
        pass
    def ready(self):
        return True
    def on_bar(self, bar, account):
        return None
    def snapshot_state(self):
        return {}
    def restore_state(self, state):
        pass`,
      defaults: { period: '15m', lookback: 20 },
      warmup_bars: 8
    },
    artifact_hash: 'c70ea9157d376b2fb9e74be25d033f12af1195e6b2a415df762e07024e2fb834',
    allowed_modes: ['local'],
    created_at: '2026-10-02T10:00:00Z'
  },
  {
    artifact: {
      contract: 'catos.python-strategy.v1',
      strategy_id: 'dynamic_grid_v2',
      version: 'v2_0_1',
      name: 'ETH 動態震盪網格',
      description: '高頻波動區間網格捕捉策略',
      source: `class Strategy:
    def __init__(self, parameters):
        self.parameters = parameters
    def update_indicators(self, bar):
        pass
    def ready(self):
        return True
    def on_bar(self, bar, account):
        return None
    def snapshot_state(self):
        return {}
    def restore_state(self, state):
        pass`,
      defaults: { grid_steps: 10 },
      warmup_bars: 8
    },
    artifact_hash: '37e9e3582fd678d1fd0c7c1521ed70f5d4c670400ed8506831fb7bb18192ecc3',
    allowed_modes: ['local'],
    created_at: '2026-10-02T11:00:00Z'
  },
  {
    artifact: {
      contract: 'catos.python-strategy.v1',
      strategy_id: 'counter-python',
      version: 'mcp-v1',
      name: 'Counter Python',
      description: 'Non-SMA short/flat counter with durable state',
      source: `from decimal import Decimal
class Strategy:
    def __init__(self, parameters):
        self.parameters = parameters
        self.n = 0
        self.decisions = 0
    def update_indicators(self, bar):
        self.n += 1
    @property
    def ready(self):
        return self.n >= 2
    def on_bar(self, bar, account):
        self.decisions += 1
        if self.parameters.get("hold") or self.n % 2:
            return Decimal(self.parameters["quantity"])
        return Decimal("0")
    def snapshot_state(self):
        return {"n": self.n, "decisions": self.decisions}
    def restore_state(self, state):
        self.n = state["n"]
        self.decisions = state["decisions"]`,
      defaults: { quantity: '-1', hold: false },
      warmup_bars: 2
    },
    artifact_hash: '8bb79f5f0bca9076c1006815bdae7846bbb6ca4446ec50740a50650ef8200aca',
    allowed_modes: ['local'],
    created_at: '2026-10-02T08:49:20.953722+00:00'
  }
];

export const mockRuns: SimulationRun[] = [
  {
    run_id: 'run-88219',
    bot_id: 'bot-btc-trend-01',
    strategy_id: 'trend_breakout_v1',
    artifact_hash: 'c70ea9157d376b2fb9e74be25d033f12af1195e6b2a415df762e07024e2fb834',
    control_state: 'running',
    symbol: 'BTC-USDT-SWAP',
    period: '15m',
    warmup_bars: 8,
    total_bars: 8,
    current_bar: 5,
    trade_count: 4,
    position_contracts: '1',
    equity_usdt: '125480.50',
    fee_usdt: '0.00404495',
    pnl_usdt: '+812.40',
    slippage_bps: '2',
    ownership_retained: false,
    risk_retained: false,
    created_at: '2026-10-02T10:05:00Z',
    updated_at: '2026-10-02T10:20:00Z'
  }
];

