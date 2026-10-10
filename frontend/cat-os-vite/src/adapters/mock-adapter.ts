/**
 * Stateful Mock Workspace Adapter for catOS Redesign v1
 * 
 * Invariants & Boundaries:
 * - Full stateful client-side storage with localStorage persistence across page refreshes (F5).
 * - Separates raw backend DTOs (VersionDTO, BotDTO, RunDTO) and presentation View Models (Bot, SimulationRun).
 * - Exact SHA-256 canonical JSON digest (8-field manifest, UTF-8, sorted keys, no fake hashes).
 * - Strict command idempotency (identical replay with full payload comparison; 409 conflict on any payload deviation).
 * - Proper pending command lifecycle: definite rejections do NOT linger in pending; uncertain 503 retains exact command.
 * - Single simulation slot occupancy & retained run ownership lock (stopped bot with non-zero position rejects any new start).
 * - Strict parameter validation: no floats allowed (Decimal string only), safe integer range, bounded JSON.
 * - Strict mode isolation: Demo and Live modes show empty / locked state, never leak local simulation bots or accounts.
 * - Freeze strategy snapshot on allocation according to selected artifact_hash and bounded JSON parameters.
 */

import type {
  WorkspaceAdapter,
  ScenarioType,
  DashboardKPIs,
  EquityPoint,
  ResearchTask,
  YaoziAlert
} from './types';
import type {
  StrategyEntry,
  StrategyArtifact,
  BotDTO,
  Bot,
  RunDTO,
  SimulationRun,
  RiskState,
  ExposureAllocationItem,
  AuditLogItem,
  TelemetryState,
  CommandRecord,
  PendingCommand,
  VersionDTO,
  BotMode
} from '@/contracts';
import {
  canonicalJson,
  validateArtifact,
    validateBinding,
  validateAllocationPayload,
  computeArtifactDigest,
  } from '@/contracts';
import {
  mockTelemetry,
  normalKPIs,
  softLossKPIs,
  holdStoppedKPIs,
  emptyKPIs,
  mockEquity1D,
  mockEquity7D,
  mockEquity30D,
  mockEquity90D,
  mockExposureAllocation,
  mockAuditEvents,
  mockNormalRiskState,
  mockBots,
  mockResearchTasks,
  mockYaoziAlerts,
  mockStrategies,
  mockRuns
} from '@/mock/default-data';

const STORAGE_KEY = 'catos_mock_storage_v2';
const PENDING_KEY = 'catos_simulation_pending_v1';

const MOCK_BUILD_ID = 'f791e202bb000bf2cce06433849fd3c86c8d49e0837cb77545ec73cc5b6d39ee';
const MOCK_INSTANCE_ID = '868721f213644b64a81cb88b1a447d3b';

interface StoredMockState {
  strategies: StrategyEntry[];
  bots: BotDTO[];
  runs: RunDTO[];
  commandLogs: CommandRecord[];
  activeScenario: ScenarioType;
}

function generateHex(len: number): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    const raw = crypto.randomUUID().replace(/-/g, '');
    if (len <= 32) return raw.slice(0, len);
    return (raw + crypto.randomUUID().replace(/-/g, '')).slice(0, len);
  }
  let s = '';
  while (s.length < len) {
    s += Math.random().toString(16).slice(2);
  }
  return s.slice(0, len);
}

export async function computeSha256(content: string): Promise<string> {
  const cryptoObj = (typeof globalThis !== 'undefined' && globalThis.crypto) ? globalThis.crypto : (typeof crypto !== 'undefined' ? crypto : null);
  if (!cryptoObj || !cryptoObj.subtle || !cryptoObj.subtle.digest) {
    throw new Error('computeSha256: Web Crypto subtle API unavailable');
  }
  const encoder = new TextEncoder();
  const data = encoder.encode(content);
  const hashBuffer = await cryptoObj.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

export class MockWorkspaceAdapter implements WorkspaceAdapter {
  public scenario: ScenarioType = 'normal';
  public currentMode: BotMode = 'local';
  private strategies: StrategyEntry[] = [];
  private bots: BotDTO[] = [];
  private runs: RunDTO[] = [];
  private commandLogs: CommandRecord[] = [];
  private pendingCommand: PendingCommand | null = null;

  constructor(initialScenario: ScenarioType = 'normal') {
    this.scenario = initialScenario;
    this.initStorage();
  }

  public setMode(m: BotMode): void {
    this.currentMode = m;
  }

  private initStorage(): void {
    let storedStrategies = false;
    let storedBots = false;
    let storedRuns = false;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed: StoredMockState = JSON.parse(raw);
        if (Array.isArray(parsed.strategies)) { this.strategies = parsed.strategies; storedStrategies = true; }
        if (Array.isArray(parsed.bots)) { this.bots = parsed.bots; storedBots = true; }
        if (Array.isArray(parsed.runs)) { this.runs = parsed.runs; storedRuns = true; }
        if (Array.isArray(parsed.commandLogs)) this.commandLogs = parsed.commandLogs;
        if (parsed.activeScenario) this.scenario = parsed.activeScenario;
      }
    } catch {
      // Fallback to initial seed if storage unavailable
    }

    if (!storedStrategies) {
      this.strategies = JSON.parse(JSON.stringify(mockStrategies));
    }
    if (!storedBots) {
      this.bots = mockBots.map(b => ({
        bot_id: b.bot_id,
        mode: b.mode || 'local',
        binding: b.binding,
        trusted: b.trusted,
        created_at: b.created_at
      }));
    } else {
      // Sync any missing bots from mockBots into existing storage
      for (const mb of mockBots) {
        if (!this.bots.some(b => b.bot_id === mb.bot_id)) {
          this.bots.push({
            bot_id: mb.bot_id,
            mode: mb.mode || 'local',
            binding: mb.binding,
            trusted: mb.trusted,
            created_at: mb.created_at
          });
        }
      }
    }
    if (!storedRuns) {
      this.runs = mockRuns.map(r => ({
        contract: 'catos.simulation.v1',
        run_id: r.run_id,
        bot_id: r.bot_id,
        template_id: 'sma-synthetic-smoke-v1',
        control_state: r.control_state,
        cleanup_confirmed: true,
        stop_requested: r.control_state === 'stopped',
        request_id: generateHex(32),
        build_id: MOCK_BUILD_ID,
        instance_id: MOCK_INSTANCE_ID,
        bars: r.total_bars,
        warmup_bars: r.warmup_bars,
        fills: r.trade_count,
        events: [
          { kind: 'warmup', bars: r.warmup_bars },
          { kind: 'fill', symbol: r.symbol, side: 'buy', price: '64000.00', size: '1', fee: r.fee_usdt }
        ],
        events_omitted: 0,
        worker_closed: true,
        error: null,
        created_at: r.created_at,
        finished_at: r.updated_at,
        stop_requested_at: r.control_state === 'stopped' ? r.updated_at : null,
        still_finishing: false,
        account: {
          equity: r.equity_usdt,
          position: r.position_contracts,
          balance: '1000.00',
          realized_pnl: r.pnl_usdt,
          fees: r.fee_usdt
        },
        artifact_hash: r.artifact_hash,
        symbol: r.symbol,
        period: r.period,
        slippage_bps: r.slippage_bps,
        binding: {
          artifact_hash: r.artifact_hash,
          parameters: { period: r.period, slippage_bps: r.slippage_bps }
        }
      }));
    }

    try {
      const savedPending = sessionStorage.getItem(PENDING_KEY);
      if (savedPending) {
        this.pendingCommand = JSON.parse(savedPending);
      }
    } catch {
      this.pendingCommand = null;
    }

    this.saveState();
  }

  private saveState(): void {
    try {
      const state: StoredMockState = {
        strategies: this.strategies,
        bots: this.bots,
        runs: this.runs,
        commandLogs: this.commandLogs.slice(0, 100),
        activeScenario: this.scenario
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // ignore storage error
    }
  }

  public resetStorage(): void {
    try {
      localStorage.removeItem(STORAGE_KEY);
      sessionStorage.removeItem(PENDING_KEY);
    } catch {
      // ignore
    }
    this.strategies = [];
    this.bots = [];
    this.runs = [];
    this.commandLogs = [];
    this.pendingCommand = null;
    this.scenario = 'normal';
    this.initStorage();
  }

  public setScenario(s: ScenarioType): void {
    this.scenario = s;
    this.saveState();
  }

  public getCommandLogs(): CommandRecord[] {
    return [...this.commandLogs];
  }

  public getPendingCommand(): PendingCommand | null {
    return this.pendingCommand;
  }

  public clearPendingCommand(): void {
    this.pendingCommand = null;
    try {
      sessionStorage.removeItem(PENDING_KEY);
    } catch {
      // ignore
    }
  }

  private recordCommand(record: CommandRecord): void {
    const existingIndex = this.commandLogs.findIndex(c => c.request_id === record.request_id);
    if (existingIndex >= 0) {
      this.commandLogs[existingIndex] = record;
    } else {
      this.commandLogs.unshift(record);
      if (this.commandLogs.length > 100) {
        this.commandLogs.pop();
      }
    }
    this.saveState();
  }

  private setPending(cmd: PendingCommand | null): void {
    this.pendingCommand = cmd;
    try {
      if (cmd) {
        sessionStorage.setItem(PENDING_KEY, JSON.stringify(cmd));
      } else {
        sessionStorage.removeItem(PENDING_KEY);
      }
    } catch {
      // ignore
    }
  }

  public async fetchVersion(): Promise<VersionDTO> {
    if (this.scenario === 'service_unavailable') {
      throw new Error('503 Service Unavailable: Version control offline');
    }
    const runningRun = this.runs.find(r => r.control_state === 'running');
    const slot = runningRun ? 'running' : 'idle';
    return {
      contract: 'catos.simulation.v1',
      mode: 'local-sim-synthetic',
      build_id: MOCK_BUILD_ID,
      current_build_id: MOCK_BUILD_ID,
      restart_required: false,
      instance_id: MOCK_INSTANCE_ID,
      slot,
      active_run_id: runningRun ? runningRun.run_id : null,
      capabilities: {
        start: slot === 'idle',
        stop: !!runningRun
      },
      unavailable_reason: null,
      config: {
        template_id: 'sma-synthetic-smoke-v1',
        bars: 8,
        warmup_bars: 2,
        interval_seconds: 1,
        mode: 'local-sim-synthetic'
      }
    };
  }

  public async fetchTelemetry(): Promise<TelemetryState> {
    if (this.scenario === 'service_unavailable') {
      return {
        ...mockTelemetry,
        connected: false,
        latency_ms: 0,
        supervisor_pid: 0,
        last_heartbeat: 'OFFLINE'
      };
    }
    return {
      ...mockTelemetry,
      connected: true,
      latency_ms: 16,
      supervisor_pid: 4821,
      last_heartbeat: new Date().toISOString()
    };
  }

  public async fetchDashboardKPIs(): Promise<DashboardKPIs> {
    if (this.scenario === 'service_unavailable') {
      throw new Error('503 Service Unavailable: Supervisor offline');
    }

    // Mode isolation: Demo and Live modes show explicit not-open status and never pretend local data
    if (this.currentMode === 'demo') {
      return {
        total_equity: '--',
        equity_change_pct: '0.00%',
        today_pnl: '--',
        today_pnl_pct: '0.00%',
        running_bots_count: 0,
        total_bots_count: 0,
        bots_summary_note: 'Demo 模式尚未開放 · 實盤對帳未通過，控制已鎖定',
        risk_status: 'UNAVAILABLE',
        effective_leverage: '--',
        leverage_limit: '3.00',
        risk_sub_note: '控制已全域鎖定 · 無實盤持倉'
      };
    }

    if (this.currentMode === 'live') {
      return {
        total_equity: '--',
        equity_change_pct: '0.00%',
        today_pnl: '--',
        today_pnl_pct: '0.00%',
        running_bots_count: 0,
        total_bots_count: 0,
        bots_summary_note: 'Live 實盤已鎖定 · 嚴禁接觸真實金鑰，維持安全隔離',
        risk_status: 'UNAVAILABLE',
        effective_leverage: '--',
        leverage_limit: '3.00',
        risk_sub_note: '控制已全域鎖定 · 本機隔離安全'
      };
    }

    if (this.scenario === 'empty') {
      return { ...emptyKPIs };
    }
    if (this.scenario === 'soft_loss') {
      return { ...softLossKPIs };
    }
    if (this.scenario === 'hold_stopped_409') {
      return { ...holdStoppedKPIs };
    }

    // Dynamic computation based on current stateful bots & runs in local mode
    const localBots = this.bots.filter(b => b.mode === 'local');
    const runningBots = localBots.filter(b => {
      const activeRun = this.runs.find(r => r.bot_id === b.bot_id && r.control_state === 'running');
      return !!activeRun;
    }).length;

    const retainedRun = this.runs.find(r => r.control_state === 'stopped' && (r.account?.position || '0') !== '0');
    let summaryNote = `${runningBots} 運行中 · ${localBots.length - runningBots} 已停止`;
    if (retainedRun) {
      summaryNote = `${runningBots} 運行中 · 1 停止持倉(409) · ${Math.max(0, localBots.length - runningBots - 1)} 已停止`;
    }

    return {
      ...normalKPIs,
      running_bots_count: runningBots,
      total_bots_count: localBots.length,
      bots_summary_note: summaryNote
    };
  }

  public async fetchEquityCurve(range: '1D' | '7D' | '30D' | '90D'): Promise<EquityPoint[]> {
    if (this.currentMode !== 'local' || this.scenario === 'empty' || this.scenario === 'service_unavailable') {
      return [];
    }
    if (range === '1D') return [...mockEquity1D];
    if (range === '30D') return [...mockEquity30D];
    if (range === '90D') return [...mockEquity90D];
    return [...mockEquity7D];
  }

  public async fetchExposureAllocation(): Promise<ExposureAllocationItem[]> {
    if (this.currentMode !== 'local' || this.scenario === 'empty' || this.scenario === 'service_unavailable') {
      return [];
    }
    return [...mockExposureAllocation];
  }

  public async fetchAuditEvents(): Promise<AuditLogItem[]> {
    if (this.currentMode !== 'local' || this.scenario === 'empty' || this.scenario === 'service_unavailable') {
      return [];
    }
    return [...mockAuditEvents];
  }

  public async fetchRiskState(): Promise<RiskState> {
    if (this.scenario === 'service_unavailable') {
      throw new Error('503 Service Unavailable: Risk guardian unreachable');
    }
    if (this.currentMode !== 'local') {
      return {
        ...mockNormalRiskState,
        status: 'missing',
        day_start_equity_usdt: '--',
        current_equity_usdt: '--',
        effective_leverage: '--',
        daily_pnl_usdt: '--',
        daily_pnl_pct: '--',
        current_drawdown_pct: '--',
        exposure_nominal_usdt: '--',
        exposure_budget_usdt: '--',
        margin_used_usdt: '--',
        margin_available_usdt: '--',
        latched_reasons: ['MODE_NOT_OPEN']
      };
    }
    if (this.scenario === 'soft_loss') {
      return {
        ...mockNormalRiskState,
        status: 'soft_latch',
        daily_pnl_usdt: '-100.60',
        daily_pnl_pct: '-10.06%',
        latched_reasons: ['DAILY_LOSS_SOFT_LIMIT_REACHED']
      };
    }
    if (this.scenario === 'empty') {
      return {
        ...mockNormalRiskState,
        status: 'missing',
        day_start_equity_usdt: '--',
        current_equity_usdt: '--',
        effective_leverage: '--'
      };
    }
    return { ...mockNormalRiskState };
  }

  /**
   * Merges BotDTO with latest RunDTO to form Bot View Model.
   * Mode isolation: Demo and Live modes return empty queue.
   */
  public async fetchBotQueue(): Promise<Bot[]> {
    if (this.scenario === 'service_unavailable') {
      throw new Error('503 Service Unavailable: Bot registry unreachable');
    }

    // Mode Isolation: Demo and Live modes show empty list and never leak local simulation bots
    if (this.currentMode !== 'local') {
      return [];
    }

    if (this.scenario === 'empty') return [];

    return this.bots.filter(b => b.mode === 'local').map(dto => {
      // Find latest run for this bot
      const botRuns = this.runs.filter(r => r.bot_id === dto.bot_id);
      const latestRun = botRuns[0] || null;

      let state = latestRun ? latestRun.control_state : 'stopped';
      let position = latestRun ? latestRun.account?.position ?? '--' : '0';
      let pnl = latestRun ? latestRun.account?.realized_pnl ?? '--' : '--';
      let equity = latestRun ? latestRun.account?.equity ?? '--' : '--';
      let fee = latestRun ? latestRun.account?.fees ?? '--' : '--';
      let ownership_retained = false;
      let risk_retained = false;

      if (this.scenario === 'hold_stopped_409' && dto.bot_id === this.bots[0]?.bot_id) {
        state = 'stopped';
        position = '-1';
        ownership_retained = true;
        risk_retained = true;
      } else if (state === 'stopped' && position !== '0') {
        ownership_retained = true;
        risk_retained = true;
      }

      const refBot = mockBots.find(m => m.bot_id === dto.bot_id);

      return {
        ...dto,
        name: refBot?.name || dto.binding.artifact.name,
        symbol: refBot?.symbol || (dto.binding.artifact.defaults?.symbol as string) || 'BTC-USDT-SWAP',
        state,
        current_run_id: latestRun?.run_id || refBot?.current_run_id,
        pnl_usdt: pnl !== '--' ? pnl : (refBot?.pnl_usdt || '+0.00'),
        position_contracts: position !== '--' ? position : (refBot?.position_contracts || '0'),
        equity_usdt: equity,
        fee_usdt: fee,
        ownership_retained,
        risk_retained,
        last_signal: latestRun?.last_signal,
        last_fill: latestRun?.last_fill,

        // Rich Metrics for Comparative View Modes
        side: refBot?.side || (Number(position) > 0 ? 'long' : Number(position) < 0 ? 'short' : 'flat'),
        entry_price: refBot?.entry_price || '63,200.00',
        mark_price: refBot?.mark_price || '64,850.00',
        roe_pct: refBot?.roe_pct || '+12.85%',
        timeframe: refBot?.timeframe || '1H',
        next_bar_countdown: refBot?.next_bar_countdown || '14:22',
        sl_price: refBot?.sl_price || '60,040.00',
        sl_distance_pct: refBot?.sl_distance_pct ?? 7.4,
        nominal_value_usdt: refBot?.nominal_value_usdt || '64,850.00',
        margin_usdt: refBot?.margin_usdt || '450.20',
        leverage: refBot?.leverage || '3.0x',
        worker_pid: refBot?.worker_pid || 4821,
        worker_cpu: refBot?.worker_cpu || '0.6%',
        worker_rss: refBot?.worker_rss || '32.8 MB',
        ipc_heartbeat_ago: refBot?.ipc_heartbeat_ago || '1s 前',
        strategy_step: refBot?.strategy_step || '等待收盤 K 線 (Waiting Closed Bar)',
        recent_signals: refBot?.recent_signals || []
      };
    });
  }

  public async fetchResearchTasks(): Promise<ResearchTask[]> {
    if (this.currentMode !== 'local' || this.scenario === 'empty' || this.scenario === 'service_unavailable') return [];
    return [...mockResearchTasks];
  }

  public async fetchYaoziAlerts(): Promise<YaoziAlert[]> {
    if (this.currentMode !== 'local' || this.scenario === 'empty' || this.scenario === 'service_unavailable') return [];
    return [...mockYaoziAlerts];
  }

  public async fetchStrategies(): Promise<StrategyEntry[]> {
    if (this.scenario === 'service_unavailable') {
      throw new Error('503 Service Unavailable: Strategy library offline');
    }
    if (this.scenario === 'empty') return [];
    return [...this.strategies];
  }

  /**
   * Execution Runs list.
   * Historical values come only from the run snapshot, never the current bot.
   */
  public async fetchRuns(): Promise<SimulationRun[]> {
    if (this.scenario === 'service_unavailable') {
      throw new Error('503 Service Unavailable: Execution runs offline');
    }
    if (this.currentMode !== 'local' || this.scenario === 'empty') return [];

    return this.runs.map(r => {
      const snapshotHash = r.artifact_hash || r.binding?.artifact_hash || 'unknown';
      const strategyId = r.binding?.artifact?.strategy_id || r.template_id || 'unknown';
      const symbol = r.symbol || (typeof r.binding?.parameters?.contract === 'string' ? r.binding.parameters.contract : undefined) || 'UNKNOWN';
      const period = r.period || (typeof r.binding?.parameters?.period === 'string' ? r.binding.parameters.period : undefined) || 'unknown';
      const slippage = r.slippage_bps || (typeof r.binding?.parameters?.slippage_bps === 'string' ? r.binding.parameters.slippage_bps : undefined) || 'unknown';

      return {
        run_id: r.run_id,
        bot_id: r.bot_id || 'unknown',
        strategy_id: strategyId,
        artifact_hash: snapshotHash,
        control_state: r.control_state,
        symbol,
        period,
        warmup_bars: r.warmup_bars ?? 0,
        total_bars: r.bars ?? 0,
        current_bar: r.bars ?? 0,
        trade_count: r.fills ?? 0,
        position_contracts: r.account?.position ?? '--',
        equity_usdt: r.account?.equity ?? '--',
        fee_usdt: r.account?.fees ?? '--',
        pnl_usdt: r.account?.realized_pnl ?? '--',
        slippage_bps: slippage,
        ownership_retained: r.control_state === 'stopped' && r.account?.position !== '0',
        risk_retained: r.control_state === 'stopped' && r.account?.position !== '0',
        created_at: r.created_at,
        updated_at: r.finished_at || r.created_at,
        completed_at: r.finished_at || undefined,
        error_message: r.error || undefined
      };
    });
  }

  /**
   * Helper to check command idempotency with full payload comparison.
   * Strictly adheres to catos/strategy_library.py and local_sim_control.py:
   * - Prior command exists:
   *   - If operation != requested operation -> 409 conflict
   *   - If payload != prior payload -> 409 conflict
   *   - If identical payload -> replay cached result
   */
  private checkIdempotency(requestId: string, commandType: import('@/contracts').CommandType, payload: any): any | null {
    const existing = this.commandLogs.find(c => c.request_id === requestId);
    if (!existing) return null;

    if (existing.command_type !== commandType) {
      throw new Error(`409 Conflict: request_id_conflict (相同 Request ID 不得用於不同操作類型: 原為 ${existing.command_type}, 請求為 ${commandType})`);
    }

    const recordedPayload = (existing.body as any)?.payload;
    if (canonicalJson(recordedPayload) !== canonicalJson(payload)) {
      throw new Error('409 Conflict: request_id_conflict (相同 Request ID 但命令參數 payload 不一致，拒絕變更)');
    }

    if (existing.status === 'success' && existing.response) {
      return existing.response;
    }
    if (existing.status === 'failed') {
      if (existing.error_code === '503_SERVICE_UNAVAILABLE') {
        if (this.scenario === 'service_unavailable') {
          throw new Error(existing.error_message || '503 Service Unavailable: Supervisor offline');
        }
        // Service has recovered from 503! Allow re-execution with same request_id and identical payload
        return null;
      }
      throw new Error(existing.error_message || '409 Conflict: request_id_conflict (先前相同 Request ID 命令已判定失敗)');
    }
    return null;
  }

  public async createStrategy(requestId: string, artifact: StrategyArtifact): Promise<StrategyEntry> {
    // 1. Strict Contract Validation on all 8 fields, text sizes, TOKEN, defaults, warmup_bars
    const checked = validateArtifact(artifact);

    // 2. Full Idempotency Check
    const cached = this.checkIdempotency(requestId, 'create_strategy', checked);
    if (cached) {
      return cached as StrategyEntry;
    }

    const record: CommandRecord = {
      request_id: requestId,
      command_type: 'create_strategy',
      body: { request_id: requestId, payload: checked },
      build_id: MOCK_BUILD_ID,
      instance_id: MOCK_INSTANCE_ID,
      timestamp: new Date().toISOString(),
      status: 'pending'
    };
    this.recordCommand(record);

    if (this.scenario === 'service_unavailable') {
      record.status = 'failed';
      record.error_code = '503_SERVICE_UNAVAILABLE';
      record.error_message = '503 Service Unavailable: Supervisor offline';
      this.saveState();
      this.setPending({
        path: '/api/workspace/simulation/strategies',
        body: { request_id: requestId, manifest: checked },
        build: MOCK_BUILD_ID,
        instance: MOCK_INSTANCE_ID,
        timestamp: new Date().toISOString()
      });
      throw new Error(record.error_message);
    }

    // 3. Exact Canonical SHA-256 Digest of entire 8-field manifest
    const hash = await computeArtifactDigest(checked);

    // 4. Immutable Version Conflict check:
    // If same (strategy_id, version) exists with DIFFERENT hash -> 409 Conflict!
    for (const entry of this.strategies) {
      if (
        entry.artifact.strategy_id === checked.strategy_id &&
        entry.artifact.version === checked.version &&
        entry.artifact_hash !== hash
      ) {
        record.status = 'failed';
        record.error_code = '409_IMMUTABLE_VERSION_CONFLICT';
        record.error_message = `409 Conflict: immutable_version_conflict (策略「${checked.strategy_id}」版本「${checked.version}」已存在不可變版本，內容 hash 衝突)`;
        this.saveState();
        this.setPending(null);
        throw new Error(record.error_message);
      }
    }

    // Check if already registered with identical hash
    const existingEntry = this.strategies.find(s => s.artifact_hash === hash);
    if (existingEntry) {
      record.status = 'success';
      record.response = existingEntry as any;
      this.saveState();
      this.setPending(null);
      return existingEntry;
    }

    const newEntry: StrategyEntry = {
      artifact: checked,
      artifact_hash: hash,
      allowed_modes: ['local'],
      created_at: new Date().toISOString()
    };

    this.strategies.unshift(newEntry);
    record.status = 'success';
    record.response = newEntry as any;
    this.saveState();
    this.setPending(null);
    return newEntry;
  }

  public async allocateBot(
    requestId: string,
    payload: {
      bot_id: string;
      artifact_hash: string;
      parameters: Record<string, any>;
      trusted: boolean;
      mode?: BotMode;
    }
  ): Promise<Bot> {
    const normalizedPayload = {
      bot_id: payload.bot_id,
      artifact_hash: payload.artifact_hash,
      parameters: payload.parameters,
      trusted: payload.trusted,
      mode: payload.mode || 'local'
    };

    // 1. Idempotency Check with full payload comparison
    const cached = this.checkIdempotency(requestId, 'allocate_bot', normalizedPayload);
    if (cached) {
      return cached as Bot;
    }

    const record: CommandRecord = {
      request_id: requestId,
      command_type: 'allocate_bot',
      body: { request_id: requestId, payload: normalizedPayload },
      build_id: MOCK_BUILD_ID,
      instance_id: MOCK_INSTANCE_ID,
      timestamp: new Date().toISOString(),
      status: 'pending'
    };
    this.recordCommand(record);

    // 2. Demo / Live Readonly Lock Check
    if (this.currentMode !== 'local') {
      record.status = 'failed';
      record.error_code = 'DEMO_MODE_LOCKED';
      record.error_message = `唯讀展示模式 (${this.currentMode.toUpperCase()}) 禁止分配或建立新機器人，控制已全域鎖定`;
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    // 3. Complete allocation payload validation:
    try {
      validateAllocationPayload(payload);
    } catch (err: any) {
      record.status = 'failed';
      record.error_code = 'INVALID_ALLOCATION_PAYLOAD';
      record.error_message = err.message || '分配請求參數不合規';
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    if (this.scenario === 'service_unavailable') {
      record.status = 'failed';
      record.error_code = '503_SERVICE_UNAVAILABLE';
      record.error_message = '503 Service Unavailable: Allocation rejected (Supervisor offline)';
      this.saveState();
      this.setPending({
        path: '/api/workspace/simulation/bots',
        body: { request_id: requestId, payload: normalizedPayload },
        build: MOCK_BUILD_ID,
        instance: MOCK_INSTANCE_ID,
        timestamp: new Date().toISOString()
      });
      throw new Error(record.error_message);
    }

    // 4. Strict Strategy Matching: STRICTLY NO FALLBACK to first strategy!
    const targetStrategy = this.strategies.find(s => s.artifact_hash === payload.artifact_hash);
    if (!targetStrategy) {
      record.status = 'failed';
      record.error_code = 'STRATEGY_NOT_FOUND';
      record.error_message = `STRATEGY_NOT_FOUND: Strategy artifact not found for hash: ${payload.artifact_hash}`;
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    // 5. Binding contract validation
    try {
      validateBinding({
        artifact: targetStrategy.artifact,
        artifact_hash: targetStrategy.artifact_hash,
        parameters: payload.parameters
      }, payload.artifact_hash);
    } catch (err: any) {
      record.status = 'failed';
      record.error_code = 'INVALID_BINDING';
      record.error_message = err.message || '綁定契約驗證失敗';
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    // Check duplicate bot ID
    if (this.bots.some(b => b.bot_id === payload.bot_id)) {
      record.status = 'failed';
      record.error_code = 'DUPLICATE_BOT_ID';
      record.error_message = `409 Conflict: immutable_bot_conflict (Bot ID "${payload.bot_id}" already exists)`;
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    // Freeze snapshot
    const newBotDTO: BotDTO = {
      bot_id: payload.bot_id,
      mode: payload.mode || 'local',
      binding: {
        artifact: JSON.parse(JSON.stringify(targetStrategy.artifact)),
        artifact_hash: targetStrategy.artifact_hash,
        parameters: JSON.parse(JSON.stringify(payload.parameters))
      },
      trusted: true,
      created_at: new Date().toISOString()
    };

    this.bots.unshift(newBotDTO);
    this.saveState();

    const newBotVM: Bot = {
      ...newBotDTO,
      name: targetStrategy.artifact.name,
      symbol: 'BTC-USDT-SWAP',
      state: 'stopped',
      pnl_usdt: '0.00',
      position_contracts: '0',
      equity_usdt: '1000.00',
      fee_usdt: '0.00'
    };

    record.status = 'success';
    record.response = newBotVM as any;
    this.saveState();
    this.setPending(null);
    return newBotVM;
  }

  public async startBot(requestId: string, botId: string): Promise<SimulationRun> {
    const path = '/api/workspace/simulation/bots/start';
    const payload = { bot_id: botId };

    // 1. Idempotency Check with full payload
    const cached = this.checkIdempotency(requestId, 'start_bot', payload);
    if (cached) {
      return cached as SimulationRun;
    }

    const record: CommandRecord = {
      request_id: requestId,
      command_type: 'start_bot',
      body: { request_id: requestId, payload },
      build_id: MOCK_BUILD_ID,
      instance_id: MOCK_INSTANCE_ID,
      timestamp: new Date().toISOString(),
      status: 'pending'
    };
    this.recordCommand(record);

    // 2. Demo / Live Readonly Lock Check
    if (this.currentMode !== 'local') {
      record.status = 'failed';
      record.error_code = 'DEMO_MODE_LOCKED';
      record.error_message = `Demo / Live 唯讀展示模式 (${this.currentMode.toUpperCase()}) 禁止啟動機器人，控制已全域鎖定`;
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    if (this.scenario === 'service_unavailable') {
      record.status = 'failed';
      record.error_code = '503_SERVICE_UNAVAILABLE';
      record.error_message = '503 Service Unavailable: Supervisor offline';
      this.saveState();
      this.setPending({
        path,
        body: { request_id: requestId, bot_id: botId },
        build: MOCK_BUILD_ID,
        instance: MOCK_INSTANCE_ID,
        timestamp: new Date().toISOString()
      });
      throw new Error(record.error_message);
    }

    // 3. Retained Position & Risk Invariant Check (Defect 1):
    // In local_sim_control.py: if self.retained_run() -> raise 409 simulation_ownership_or_risk_retained
    // Any run stopped with non-zero position locks the exclusive contract and forbids starting ANY new instance!
    const retained = this.runs.find(r => r.control_state === 'stopped' && r.account?.position !== '0');
    if (retained || this.scenario === 'hold_stopped_409') {
      const retainedBotId = retained ? retained.bot_id : 'bot-btc-trend-01';
      const retainedPos = retained?.account?.position ?? 'unknown';
      record.status = 'failed';
      record.error_code = '409_SIMULATION_OWNERSHIP_RETAINED';
      record.error_message = `409 Conflict: simulation_ownership_or_risk_retained (已有案例 ${retainedBotId} 停止但保留部位 ${retainedPos} 張，獨佔合約未釋放，禁止啟動新執行實例)`;
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    if (this.scenario === 'soft_loss') {
      record.status = 'failed';
      record.error_code = 'DAILY_LOSS_SOFT_LATCH';
      record.error_message = 'Risk Latch: Soft daily loss reached (-10.0%). Opening positions forbidden.';
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    const bot = this.bots.find(b => b.bot_id === botId);
    if (!bot) {
      record.status = 'failed';
      record.error_code = 'BOT_NOT_FOUND';
      record.error_message = `Bot "${botId}" not found in registry`;
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    // 4. Single Execution Slot Check: NEVER silently force existing running runs to completed!
    const activeRunningRun = this.runs.find(r => r.control_state === 'running');
    if (activeRunningRun && activeRunningRun.bot_id !== botId) {
      record.status = 'failed';
      record.error_code = 'SIMULATION_SLOT_OCCUPIED';
      record.error_message = `409 Conflict: simulation_slot_occupied (機器人 ${activeRunningRun.bot_id} 正在運行中，單槽位不可同時啟動多個實例。請先停止當前運行實例)`;
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    // If already running for this bot, return existing run
    if (activeRunningRun && activeRunningRun.bot_id === botId) {
      record.status = 'success';
      const existingVM = (await this.fetchRuns()).find(r => r.run_id === activeRunningRun.run_id)!;
      record.response = existingVM as any;
      this.saveState();
      this.setPending(null);
      return existingVM;
    }

    const runId = generateHex(32);
    const runPeriod = typeof bot.binding.parameters?.period === 'string' ? bot.binding.parameters.period : '15m';
    const runSlippage = typeof bot.binding.parameters?.slippage_bps === 'string' ? bot.binding.parameters.slippage_bps : '2';
    const runSymbol = 'BTC-USDT-SWAP';

    const newRunDTO: RunDTO = {
      contract: 'catos.simulation.v1',
      run_id: runId,
      bot_id: botId,
      template_id: bot.binding.artifact.strategy_id,
      control_state: 'running',
      cleanup_confirmed: false,
      stop_requested: false,
      request_id: requestId,
      build_id: MOCK_BUILD_ID,
      instance_id: MOCK_INSTANCE_ID,
      bars: 1,
      warmup_bars: bot.binding.artifact.warmup_bars,
      fills: 1,
      events: [
        { kind: 'started', time_ms: Date.now() },
        { kind: 'fill', symbol: runSymbol, side: 'buy', price: '64000.00', size: '1', fee: '0.0005' }
      ],
      events_omitted: 0,
      worker_closed: false,
      error: null,
      created_at: new Date().toISOString(),
      finished_at: null,
      stop_requested_at: null,
      still_finishing: false,
      last_signal: { side: 'long', target: '1' },
      last_fill: { symbol: runSymbol, price: '64000.00', amount: '1' },
      account: {
        equity: '1000.00',
        position: '1',
        balance: '1000.00',
        realized_pnl: '0.00',
        fees: '0.0005'
      },
      artifact_hash: bot.binding.artifact_hash,
      binding: JSON.parse(JSON.stringify(bot.binding)),
      symbol: runSymbol,
      period: runPeriod,
      slippage_bps: runSlippage
    };

    this.runs.unshift(newRunDTO);
    this.saveState();
    this.setPending(null);

    const resultVM: SimulationRun = {
      run_id: runId,
      bot_id: botId,
      strategy_id: bot.binding.artifact.strategy_id,
      artifact_hash: bot.binding.artifact_hash,
      control_state: 'running',
      symbol: runSymbol,
      period: runPeriod,
      warmup_bars: bot.binding.artifact.warmup_bars,
      total_bars: 8,
      current_bar: 1,
      trade_count: 1,
      position_contracts: '1',
      equity_usdt: '1000.00',
      fee_usdt: '0.0005',
      pnl_usdt: '0.00',
      slippage_bps: runSlippage,
      ownership_retained: false,
      risk_retained: false,
      created_at: newRunDTO.created_at,
      updated_at: newRunDTO.created_at
    };

    record.status = 'success';
    record.response = resultVM as any;
    this.recordCommand(record);
    this.saveState();
    this.setPending(null);
    return resultVM;
  }

  public async stopBot(requestId: string, runId: string): Promise<SimulationRun> {
    if (!runId || runId === 'run-default') {
      throw new Error('Cannot stop: Invalid or unassigned Run ID');
    }

    const payload = { run_id: runId };

    // 1. Idempotency Check with full payload
    const cached = this.checkIdempotency(requestId, 'stop_bot', payload);
    if (cached) {
      return cached as SimulationRun;
    }

    const path = `/api/workspace/simulation/runs/${runId}/stop`;
    const record: CommandRecord = {
      request_id: requestId,
      command_type: 'stop_bot',
      body: { request_id: requestId, payload },
      build_id: MOCK_BUILD_ID,
      instance_id: MOCK_INSTANCE_ID,
      timestamp: new Date().toISOString(),
      status: 'pending'
    };
    this.recordCommand(record);

    // 2. Demo / Live Readonly Lock Check
    if (this.currentMode !== 'local') {
      record.status = 'failed';
      record.error_code = 'DEMO_MODE_LOCKED';
      record.error_message = `Demo / Live 唯讀展示模式 (${this.currentMode.toUpperCase()}) 禁止停止機器人，控制已全域鎖定`;
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    if (this.scenario === 'service_unavailable') {
      record.status = 'failed';
      record.error_code = '503_SERVICE_UNAVAILABLE';
      record.error_message = '503 Service Unavailable: Supervisor offline';
      this.saveState();
      this.setPending({
        path,
        body: { request_id: requestId },
        build: MOCK_BUILD_ID,
        instance: MOCK_INSTANCE_ID,
        timestamp: new Date().toISOString()
      });
      throw new Error(record.error_message);
    }

    const targetRun = this.runs.find(r => r.run_id === runId);
    if (!targetRun) {
      record.status = 'failed';
      record.error_code = 'RUN_NOT_FOUND';
      record.error_message = `Run ID "${runId}" not found`;
      this.saveState();
      this.setPending(null);
      throw new Error(record.error_message);
    }

    const stableArtifactHash = targetRun.artifact_hash || targetRun.binding?.artifact_hash || 'unknown';
    const strategyId = targetRun.binding?.artifact?.strategy_id || targetRun.template_id || 'unknown';
    const symbol = targetRun.symbol || (typeof targetRun.binding?.parameters?.contract === 'string' ? targetRun.binding.parameters.contract : undefined) || 'UNKNOWN';
    const period = targetRun.period || (typeof targetRun.binding?.parameters?.period === 'string' ? targetRun.binding.parameters.period : undefined) || 'unknown';
    const slippage = targetRun.slippage_bps || (typeof targetRun.binding?.parameters?.slippage_bps === 'string' ? targetRun.binding.parameters.slippage_bps : undefined) || 'unknown';

    // If already stopped, maintain idempotency
    if (targetRun.control_state === 'stopped') {
      record.status = 'success';
      const alreadyStoppedVM: SimulationRun = {
        run_id: runId,
        bot_id: targetRun.bot_id || 'unknown',
        strategy_id: strategyId,
        artifact_hash: stableArtifactHash,
        control_state: 'stopped',
        symbol,
        period,
        warmup_bars: targetRun.warmup_bars ?? 0,
        total_bars: targetRun.bars ?? 0,
        current_bar: targetRun.bars ?? 0,
        trade_count: targetRun.fills ?? 0,
        position_contracts: targetRun.account?.position ?? '--',
        equity_usdt: targetRun.account?.equity ?? '--',
        fee_usdt: targetRun.account?.fees ?? '--',
        pnl_usdt: targetRun.account?.realized_pnl ?? '--',
        slippage_bps: slippage,
        ownership_retained: targetRun.account?.position !== '0',
        risk_retained: targetRun.account?.position !== '0',
        created_at: targetRun.created_at,
        updated_at: targetRun.finished_at || targetRun.created_at
      };
      record.response = alreadyStoppedVM as any;
      this.saveState();
      this.setPending(null);
      return alreadyStoppedVM;
    }

    targetRun.control_state = 'stopped';
    targetRun.stop_requested = true;
    targetRun.stop_requested_at = new Date().toISOString();
    targetRun.finished_at = new Date().toISOString();
    targetRun.worker_closed = true;
    targetRun.cleanup_confirmed = true;

    // Retain position according to invariant: stopped bot retains exposure, no automatic liquidation
    // Missing account data remains unknown; stopping must not fabricate balances.

    this.saveState();
    this.setPending(null);

    const stoppedVM: SimulationRun = {
      run_id: runId,
      bot_id: targetRun.bot_id || 'unknown',
      strategy_id: strategyId,
      artifact_hash: stableArtifactHash,
      control_state: 'stopped',
      symbol,
      period,
      warmup_bars: targetRun.warmup_bars ?? 0,
      total_bars: targetRun.bars ?? 0,
      current_bar: targetRun.bars ?? 0,
      trade_count: targetRun.fills ?? 0,
      position_contracts: targetRun.account?.position ?? '--',
      equity_usdt: targetRun.account?.equity ?? '--',
      fee_usdt: targetRun.account?.fees ?? '--',
      pnl_usdt: targetRun.account?.realized_pnl ?? '--',
      slippage_bps: slippage,
      ownership_retained: targetRun.account?.position !== '0',
      risk_retained: targetRun.account?.position !== '0',
      created_at: targetRun.created_at,
      updated_at: targetRun.finished_at || targetRun.created_at
    };

    record.status = 'success';
    record.response = stoppedVM as any;
    this.recordCommand(record);
    this.saveState();
    this.setPending(null);
    return stoppedVM;
  }

  public async retryPendingCommand(): Promise<any> {
    if (!this.pendingCommand) {
      throw new Error('No pending command to retry');
    }
    const cmd = this.pendingCommand;
    if (cmd.path.endsWith('/strategies')) {
      const artifact = cmd.body.manifest || cmd.body.payload;
      return this.createStrategy(cmd.body.request_id, artifact);
    }
    if (cmd.path.endsWith('/bots')) {
      return this.allocateBot(cmd.body.request_id, cmd.body.payload);
    }
    if (cmd.path.endsWith('/start')) {
      const botId = cmd.body.bot_id || cmd.body.payload?.bot_id;
      return this.startBot(cmd.body.request_id, botId);
    }
    if (cmd.path.includes('/runs/') && cmd.path.endsWith('/stop')) {
      const parts = cmd.path.split('/');
      const runId = parts[parts.length - 2];
      return this.stopBot(cmd.body.request_id, runId);
    }
    throw new Error('Unrecognized pending command path: ' + cmd.path);
  }
}

export const activeAdapter = new MockWorkspaceAdapter('normal');
export const mockAdapter = activeAdapter;
