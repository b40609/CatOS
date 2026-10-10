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
  fixed_tag: '41cb53c54d6dABDE',
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
    message: '帳戶單幣曝險接近預算閾值 (48.2% / 上限 50.0%)',
    details: { symbol: 'ETH-USDT-SWAP', current_exposure: '1446.00', limit: '1500.00' }
  },
  {
    id: 'evt-002',
    timestamp: '10:24:15',
    level: 'INFO',
    category: 'ORDER',
    message: '委託撮合成交 · 價格 64,250.00 USDT · 標籤 41cb53c54d6dABDE',
    details: { order_id: 'ord-88392', size: '1', side: 'buy' }
  },
  {
    id: 'evt-003',
    timestamp: '09:30:10',
    level: 'INFO',
    category: 'WORKER',
    message: 'Worker PID 4821 正常啟動，已完成 8 根歷史收盤 K 線指標預熱',
    details: { bot_id: 'bot-btc-01', warmup_bars: 8 }
  }
];

export const mockNormalRiskState: RiskState = {
  status: 'normal',
  fixed_tag: '41cb53c54d6dABDE',
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
        version: '1.2.0',
        name: 'BTC 趨勢突破主線',
        description: '基於收盤 K 線通道突破的雙向順勢策略',
        source: '# Python 策略原始碼',
        defaults: { period: '15m', lookback: 20 },
        warmup_bars: 8
      },
      artifact_hash: '9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b',
      parameters: { period: '15m', lookback: 20 }
    },
    trusted: true,
    created_at: '2026-10-02T10:00:00Z',
    state: 'running',
    current_run_id: 'run-88219',
    pnl_usdt: '+812.40',
    position_contracts: '1'
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
        version: '2.0.1',
        name: 'ETH 動態震盪網格',
        description: '高頻波動區間網格捕捉策略',
        source: '# Python 策略原始碼',
        defaults: { grid_steps: 10 },
        warmup_bars: 8
      },
      artifact_hash: '1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b',
      parameters: { grid_steps: 10 }
    },
    trusted: true,
    created_at: '2026-10-02T11:00:00Z',
    state: 'starting',
    current_run_id: 'run-88220',
    pnl_usdt: '-318.20',
    position_contracts: '-1'
  },
  {
    bot_id: 'bot-sol-swing-03',
    name: 'SOL 試驗波段 04',
    symbol: 'SOL-USDT-SWAP',
    mode: 'local',
    binding: {
      artifact: {
        contract: 'catos.python-strategy.v1',
        strategy_id: 'swing_pilot_v1',
        version: '1.0.0',
        name: 'SOL 試驗波段 04',
        description: '多重均線金叉共振策略',
        source: '# Python 策略原始碼',
        defaults: { fast: 5, slow: 20 },
        warmup_bars: 8
      },
      artifact_hash: '5f4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e',
      parameters: { fast: 5, slow: 20 }
    },
    trusted: true,
    created_at: '2026-10-02T12:00:00Z',
    state: 'stopped',
    pnl_usdt: '0.00',
    position_contracts: '0'
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
    title: '[待確認: 費率偏離]',
    tag: '情報 · 開發中',
    status: 'PENDING',
    summary: '資金費率正向擴大至 0.035%，預警基差收斂風險'
  },
  {
    id: 'yz-02',
    time: '08:30',
    type: '鏈上異動',
    title: '[待確認: 鏈上異動]',
    tag: '情報 · 開發中',
    status: 'PENDING',
    summary: '監控到大額 USDT 轉入交易所熱錢包 (4,200 萬)'
  }
];

export const mockStrategies: StrategyEntry[] = [
  {
    artifact: {
      contract: 'catos.python-strategy.v1',
      strategy_id: 'trend_breakout_v1',
      version: '1.2.0',
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
    artifact_hash: '9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b',
    allowed_modes: ['local'],
    created_at: '2026-10-02T10:00:00Z'
  },
  {
    artifact: {
      contract: 'catos.python-strategy.v1',
      strategy_id: 'dynamic_grid_v2',
      version: '2.0.1',
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
    artifact_hash: '1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b',
    allowed_modes: ['local'],
    created_at: '2026-10-02T11:00:00Z'
  }
];

export const mockRuns: SimulationRun[] = [
  {
    run_id: 'run-88219',
    bot_id: 'bot-btc-trend-01',
    strategy_id: 'trend_breakout_v1',
    artifact_hash: '9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b',
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
