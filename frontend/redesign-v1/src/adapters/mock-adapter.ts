/**
 * Stateful Mock Workspace Adapter for catOS Redesign v1
 * 
 * Invariants & Boundaries:
 * - Full stateful client-side storage with localStorage persistence across page refreshes (F5).
 * - Separates raw backend DTOs (VersionDTO, BotDTO, RunDTO) and presentation View Models (Bot, SimulationRun).
 * - Exact SHA-256 / 32-char hex ID handling, no imaginary 'run-default'.
 * - Strict adherence to command idempotency, pending command retention & retry.
 * - Accurate 503 / Service Unavailable representation: never fallback to NORMAL or pretend safe.
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
  mockTelemetry,
  normalKPIs,
  softLossKPIs,
  holdStoppedKPIs,
  emptyKPIs,
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
  if (typeof crypto !== 'undefined' && crypto.subtle && crypto.subtle.digest) {
    const encoder = new TextEncoder();
    const data = encoder.encode(content);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }
  // Deterministic 64-char hash fallback
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
  for (let i = 0; i < content.length; i++) {
    const ch = content.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  const part1 = (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16).padStart(32, '0');
  const part2 = (4294967296 * (2097151 & h1) + (h2 >>> 0)).toString(16).padStart(32, '0');
  return (part1 + part2).slice(0, 64);
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
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed: StoredMockState = JSON.parse(raw);
        if (Array.isArray(parsed.strategies)) this.strategies = parsed.strategies;
        if (Array.isArray(parsed.bots)) this.bots = parsed.bots;
        if (Array.isArray(parsed.runs)) this.runs = parsed.runs;
        if (Array.isArray(parsed.commandLogs)) this.commandLogs = parsed.commandLogs;
        if (parsed.activeScenario) this.scenario = parsed.activeScenario;
      }
    } catch {
      // Fallback to initial seed if storage unavailable
    }

    if (!this.strategies.length) {
      this.strategies = JSON.parse(JSON.stringify(mockStrategies));
    }
    if (!this.bots.length) {
      this.bots = mockBots.map(b => ({
        bot_id: b.bot_id,
        mode: b.mode || 'local',
        binding: b.binding,
        trusted: b.trusted,
        created_at: b.created_at
      }));
    }
    if (!this.runs.length) {
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
    this.commandLogs.unshift(record);
    if (this.commandLogs.length > 100) {
      this.commandLogs.pop();
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
    if (this.scenario === 'empty') {
      return { ...emptyKPIs };
    }
    if (this.scenario === 'soft_loss') {
      return { ...softLossKPIs };
    }
    if (this.scenario === 'hold_stopped_409') {
      return { ...holdStoppedKPIs };
    }

    // Dynamic computation based on current stateful bots & runs
    const runningBots = this.bots.filter(b => {
      const activeRun = this.runs.find(r => r.bot_id === b.bot_id && r.control_state === 'running');
      return !!activeRun;
    }).length;

    return {
      ...normalKPIs,
      running_bots_count: runningBots,
      total_bots_count: this.bots.length,
      bots_summary_note: `${runningBots} 運行中 · ${this.bots.length - runningBots} 已停止`
    };
  }

  public async fetchEquityCurve(range: '7D' | '30D' | '90D'): Promise<EquityPoint[]> {
    if (this.scenario === 'empty' || this.scenario === 'service_unavailable') {
      return [];
    }
    if (range === '30D') return [...mockEquity30D];
    if (range === '90D') return [...mockEquity90D];
    return [...mockEquity7D];
  }

  public async fetchExposureAllocation(): Promise<ExposureAllocationItem[]> {
    if (this.scenario === 'empty' || this.scenario === 'service_unavailable') {
      return [];
    }
    return [...mockExposureAllocation];
  }

  public async fetchAuditEvents(): Promise<AuditLogItem[]> {
    if (this.scenario === 'empty' || this.scenario === 'service_unavailable') {
      return [];
    }
    return [...mockAuditEvents];
  }

  public async fetchRiskState(): Promise<RiskState> {
    if (this.scenario === 'service_unavailable') {
      throw new Error('503 Service Unavailable: Risk guardian unreachable');
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
   * Merges BotDTO with latest RunDTO to form Bot View Model
   */
  public async fetchBotQueue(): Promise<Bot[]> {
    if (this.scenario === 'service_unavailable') {
      throw new Error('503 Service Unavailable: Bot registry unreachable');
    }
    if (this.scenario === 'empty') return [];

    return this.bots.map(dto => {
      // Find latest run for this bot
      const botRuns = this.runs.filter(r => r.bot_id === dto.bot_id);
      const latestRun = botRuns[0] || null;

      let state = latestRun ? latestRun.control_state : 'stopped';
      let position = latestRun?.account?.position || '0';
      let pnl = latestRun?.account?.realized_pnl || '0.00';
      let equity = latestRun?.account?.equity || '1000.00';
      let fee = latestRun?.account?.fees || '0.00';
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

      return {
        ...dto,
        name: dto.binding.artifact.name,
        symbol: 'BTC-USDT-SWAP',
        state,
        current_run_id: latestRun?.run_id,
        pnl_usdt: pnl,
        position_contracts: position,
        equity_usdt: equity,
        fee_usdt: fee,
        ownership_retained,
        risk_retained,
        last_signal: latestRun?.last_signal,
        last_fill: latestRun?.last_fill
      };
    });
  }

  public async fetchResearchTasks(): Promise<ResearchTask[]> {
    if (this.scenario === 'empty' || this.scenario === 'service_unavailable') return [];
    return [...mockResearchTasks];
  }

  public async fetchYaoziAlerts(): Promise<YaoziAlert[]> {
    if (this.scenario === 'empty' || this.scenario === 'service_unavailable') return [];
    return [...mockYaoziAlerts];
  }

  public async fetchStrategies(): Promise<StrategyEntry[]> {
    if (this.scenario === 'service_unavailable') {
      throw new Error('503 Service Unavailable: Strategy library offline');
    }
    if (this.scenario === 'empty') return [];
    return [...this.strategies];
  }

  public async fetchRuns(): Promise<SimulationRun[]> {
    if (this.scenario === 'service_unavailable') {
      throw new Error('503 Service Unavailable: Execution runs offline');
    }
    if (this.scenario === 'empty') return [];

    return this.runs.map(r => ({
      run_id: r.run_id,
      bot_id: r.bot_id || 'bot-default',
      strategy_id: r.template_id || 'sma-synthetic-smoke-v1',
      artifact_hash: generateHex(64),
      control_state: r.control_state,
      symbol: 'BTC-USDT-SWAP',
      period: '15m',
      warmup_bars: r.warmup_bars,
      total_bars: r.bars,
      current_bar: r.bars,
      trade_count: r.fills,
      position_contracts: r.account?.position || '0',
      equity_usdt: r.account?.equity || '1000.00',
      fee_usdt: r.account?.fees || '0.00',
      pnl_usdt: r.account?.realized_pnl || '0.00',
      slippage_bps: '2',
      ownership_retained: r.control_state === 'stopped' && (r.account?.position || '0') !== '0',
      risk_retained: r.control_state === 'stopped' && (r.account?.position || '0') !== '0',
      created_at: r.created_at,
      updated_at: r.finished_at || r.created_at,
      completed_at: r.finished_at || undefined,
      error_message: r.error || undefined
    }));
  }

  public async createStrategy(requestId: string, artifact: StrategyArtifact): Promise<StrategyEntry> {
    // 1. Idempotency Check
    const existingCmd = this.commandLogs.find(c => c.request_id === requestId);
    if (existingCmd) {
      if (existingCmd.command_type === 'create_strategy' && existingCmd.status === 'success' && existingCmd.response) {
        return existingCmd.response as StrategyEntry;
      }
      if (existingCmd.command_type !== 'create_strategy') {
        throw new Error('409 Conflict: request_id_conflict (相同 Request ID 不得用於不同命令類型)');
      }
    }

    const record: CommandRecord = {
      request_id: requestId,
      command_type: 'create_strategy',
      body: { request_id: requestId, manifest: artifact },
      build_id: MOCK_BUILD_ID,
      instance_id: MOCK_INSTANCE_ID,
      timestamp: new Date().toISOString(),
      status: 'pending'
    };
    this.recordCommand(record);

    if (this.scenario === 'service_unavailable') {
      record.status = 'failed';
      record.error_code = '503_SERVICE_UNAVAILABLE';
      record.error_message = 'Cannot register strategy: Supervisor is offline';
      this.saveState();
      throw new Error(record.error_message);
    }

    // 2. Real SHA-256 Hash of Artifact content
    const contentToHash = JSON.stringify({
      contract: artifact.contract,
      strategy_id: artifact.strategy_id,
      version: artifact.version,
      source: artifact.source,
      defaults: artifact.defaults
    });
    const hash = await computeSha256(contentToHash);

    // Check if already registered with identical hash
    const existingEntry = this.strategies.find(s => s.artifact_hash === hash);
    if (existingEntry) {
      record.status = 'success';
      record.response = existingEntry as any;
      this.saveState();
      return existingEntry;
    }

    const newEntry: StrategyEntry = {
      artifact,
      artifact_hash: hash,
      allowed_modes: ['local'],
      created_at: new Date().toISOString()
    };

    this.strategies.unshift(newEntry);
    this.saveState();

    record.status = 'success';
    record.response = newEntry as any;
    this.saveState();
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
    const body = {
      request_id: requestId,
      bot_id: payload.bot_id,
      artifact_hash: payload.artifact_hash,
      parameters: payload.parameters,
      trusted: payload.trusted,
      mode: payload.mode || 'local'
    };

    // 1. Idempotency Check
    const existingCmd = this.commandLogs.find(c => c.request_id === requestId);
    if (existingCmd) {
      if (existingCmd.command_type === 'allocate_bot' && (existingCmd.body as any)?.bot_id === payload.bot_id) {
        if (existingCmd.status === 'success' && existingCmd.response) {
          return existingCmd.response as Bot;
        }
      } else {
        throw new Error('409 Conflict: request_id_conflict (相同 Request ID 不得用於不同機器人或命令)');
      }
    }

    const record: CommandRecord = {
      request_id: requestId,
      command_type: 'allocate_bot',
      body,
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
      throw new Error(record.error_message);
    }

    if (!payload.trusted) {
      record.status = 'failed';
      record.error_code = 'UNTRUSTED_STRATEGY';
      record.error_message = 'Cannot allocate bot without explicit manual trust confirmation';
      this.saveState();
      throw new Error(record.error_message);
    }

    if (this.scenario === 'service_unavailable') {
      record.status = 'failed';
      record.error_code = '503_SERVICE_UNAVAILABLE';
      record.error_message = 'Allocation rejected: Service unavailable';
      this.saveState();
      throw new Error(record.error_message);
    }

    // 3. Strict Strategy Matching: STRICTLY NO FALLBACK to first strategy!
    const targetStrategy = this.strategies.find(s => s.artifact_hash === payload.artifact_hash);
    if (!targetStrategy) {
      record.status = 'failed';
      record.error_code = 'STRATEGY_NOT_FOUND';
      record.error_message = `STRATEGY_NOT_FOUND: Strategy artifact not found for hash: ${payload.artifact_hash}`;
      this.saveState();
      throw new Error(record.error_message);
    }

    // Check duplicate bot ID
    if (this.bots.some(b => b.bot_id === payload.bot_id)) {
      record.status = 'failed';
      record.error_code = 'DUPLICATE_BOT_ID';
      record.error_message = `Bot ID "${payload.bot_id}" already exists`;
      this.saveState();
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
    return newBotVM;
  }

  public async startBot(requestId: string, botId: string): Promise<SimulationRun> {
    const path = '/api/workspace/simulation/bots/start';
    const body = { request_id: requestId, bot_id: botId };

    // 1. Idempotency Check
    const existingCmd = this.commandLogs.find(c => c.request_id === requestId);
    if (existingCmd) {
      if (existingCmd.command_type === 'start_bot' && (existingCmd.body as any)?.bot_id === botId) {
        if (existingCmd.status === 'success' && existingCmd.response) {
          return existingCmd.response as SimulationRun;
        }
      } else {
        throw new Error('409 Conflict: request_id_conflict (相同 Request ID 不得用於不同操作或機器人)');
      }
    }

    const record: CommandRecord = {
      request_id: requestId,
      command_type: 'start_bot',
      body,
      build_id: MOCK_BUILD_ID,
      instance_id: MOCK_INSTANCE_ID,
      timestamp: new Date().toISOString(),
      status: 'pending'
    };
    this.recordCommand(record);

    this.setPending({
      path,
      body,
      build: MOCK_BUILD_ID,
      instance: MOCK_INSTANCE_ID,
      timestamp: new Date().toISOString()
    });

    // 2. Demo / Live Readonly Lock Check
    if (this.currentMode !== 'local') {
      record.status = 'failed';
      record.error_code = 'DEMO_MODE_LOCKED';
      record.error_message = `Demo / Live 唯讀展示模式 (${this.currentMode.toUpperCase()}) 禁止啟動機器人，控制已全域鎖定`;
      this.saveState();
      throw new Error(record.error_message);
    }

    if (this.scenario === 'service_unavailable') {
      record.status = 'failed';
      record.error_code = '503_SERVICE_UNAVAILABLE';
      record.error_message = 'Cannot start bot: Supervisor offline';
      this.saveState();
      throw new Error(record.error_message);
    }

    if (this.scenario === 'hold_stopped_409') {
      record.status = 'failed';
      record.error_code = '409_SIMULATION_OWNERSHIP_RETAINED';
      record.error_message = '409 Conflict: Bot stopped with retained position (-1 contracts). Exclusive contract locked.';
      this.saveState();
      throw new Error(record.error_message);
    }

    if (this.scenario === 'soft_loss') {
      record.status = 'failed';
      record.error_code = 'DAILY_LOSS_SOFT_LATCH';
      record.error_message = 'Risk Latch: Soft daily loss reached (-10.0%). Opening positions forbidden.';
      this.saveState();
      throw new Error(record.error_message);
    }

    const bot = this.bots.find(b => b.bot_id === botId);
    if (!bot) {
      record.status = 'failed';
      record.error_code = 'BOT_NOT_FOUND';
      record.error_message = `Bot "${botId}" not found in registry`;
      this.saveState();
      throw new Error(record.error_message);
    }

    // 3. Single Execution Slot Check: NEVER silently force existing running runs to completed!
    const activeRunningRun = this.runs.find(r => r.control_state === 'running');
    if (activeRunningRun && activeRunningRun.bot_id !== botId) {
      record.status = 'failed';
      record.error_code = 'SIMULATION_SLOT_OCCUPIED';
      record.error_message = `409 Conflict: simulation_slot_occupied (機器人 ${activeRunningRun.bot_id} 正在運行中，單槽位不可同時啟動多個實例。請先停止當前運行實例)`;
      this.saveState();
      throw new Error(record.error_message);
    }

    // If already running for this bot, return existing run
    if (activeRunningRun && activeRunningRun.bot_id === botId) {
      record.status = 'success';
      const existingVM: SimulationRun = {
        run_id: activeRunningRun.run_id,
        bot_id: botId,
        strategy_id: bot.binding.artifact.strategy_id,
        artifact_hash: bot.binding.artifact_hash,
        control_state: 'running',
        symbol: 'BTC-USDT-SWAP',
        period: '15m',
        warmup_bars: activeRunningRun.warmup_bars,
        total_bars: activeRunningRun.bars,
        current_bar: activeRunningRun.bars,
        trade_count: activeRunningRun.fills,
        position_contracts: activeRunningRun.account?.position || '1',
        equity_usdt: activeRunningRun.account?.equity || '1000.00',
        fee_usdt: activeRunningRun.account?.fees || '0.0005',
        pnl_usdt: activeRunningRun.account?.realized_pnl || '0.00',
        slippage_bps: '2',
        ownership_retained: false,
        risk_retained: false,
        created_at: activeRunningRun.created_at,
        updated_at: activeRunningRun.created_at
      };
      record.response = existingVM as any;
      this.saveState();
      this.setPending(null);
      return existingVM;
    }

    const runId = generateHex(32);
    const newRunDTO: RunDTO = {
      contract: 'catos.simulation.v1',
      run_id: runId,
      bot_id: botId,
      template_id: 'sma-synthetic-smoke-v1',
      control_state: 'running',
      cleanup_confirmed: false,
      stop_requested: false,
      request_id: requestId,
      build_id: MOCK_BUILD_ID,
      instance_id: MOCK_INSTANCE_ID,
      bars: 1,
      warmup_bars: 2,
      fills: 1,
      events: [
        { kind: 'started', time_ms: Date.now() },
        { kind: 'fill', symbol: 'BTC-USDT-SWAP', side: 'buy', price: '64000.00', size: '1', fee: '0.0005' }
      ],
      events_omitted: 0,
      worker_closed: false,
      error: null,
      created_at: new Date().toISOString(),
      finished_at: null,
      stop_requested_at: null,
      still_finishing: false,
      last_signal: { side: 'long', target: '1' },
      last_fill: { symbol: 'BTC-USDT-SWAP', price: '64000.00', amount: '1' },
      account: {
        equity: '1000.00',
        position: '1',
        balance: '1000.00',
        realized_pnl: '0.00',
        fees: '0.0005'
      }
    };

    this.runs.unshift(newRunDTO);
    this.saveState();

    // Command succeeded: clear pending command
    this.setPending(null);

    const resultVM: SimulationRun = {
      run_id: runId,
      bot_id: botId,
      strategy_id: bot.binding.artifact.strategy_id,
      artifact_hash: bot.binding.artifact_hash,
      control_state: 'running',
      symbol: 'BTC-USDT-SWAP',
      period: '15m',
      warmup_bars: 2,
      total_bars: 8,
      current_bar: 1,
      trade_count: 1,
      position_contracts: '1',
      equity_usdt: '1000.00',
      fee_usdt: '0.0005',
      pnl_usdt: '0.00',
      slippage_bps: '2',
      ownership_retained: false,
      risk_retained: false,
      created_at: newRunDTO.created_at,
      updated_at: newRunDTO.created_at
    };

    record.status = 'success';
    record.response = resultVM as any;
    this.saveState();
    return resultVM;
  }

  public async stopBot(requestId: string, runId: string): Promise<SimulationRun> {
    if (!runId || runId === 'run-default') {
      throw new Error('Cannot stop: Invalid or unassigned Run ID');
    }

    // 1. Idempotency Check
    const existingCmd = this.commandLogs.find(c => c.request_id === requestId);
    if (existingCmd) {
      if (existingCmd.command_type === 'stop_bot' && (existingCmd.body as any)?.request_id === requestId) {
        if (existingCmd.status === 'success' && existingCmd.response) {
          return existingCmd.response as SimulationRun;
        }
      } else {
        throw new Error('409 Conflict: request_id_conflict (相同 Request ID 不得用於不同操作)');
      }
    }

    const path = `/api/workspace/simulation/runs/${runId}/stop`;
    const body = { request_id: requestId };

    const record: CommandRecord = {
      request_id: requestId,
      command_type: 'stop_bot',
      body,
      build_id: MOCK_BUILD_ID,
      instance_id: MOCK_INSTANCE_ID,
      timestamp: new Date().toISOString(),
      status: 'pending'
    };
    this.recordCommand(record);

    this.setPending({
      path,
      body,
      build: MOCK_BUILD_ID,
      instance: MOCK_INSTANCE_ID,
      timestamp: new Date().toISOString()
    });

    // 2. Demo / Live Readonly Lock Check
    if (this.currentMode !== 'local') {
      record.status = 'failed';
      record.error_code = 'DEMO_MODE_LOCKED';
      record.error_message = `Demo / Live 唯讀展示模式 (${this.currentMode.toUpperCase()}) 禁止停止機器人，控制已全域鎖定`;
      this.saveState();
      throw new Error(record.error_message);
    }

    if (this.scenario === 'service_unavailable') {
      record.status = 'failed';
      record.error_code = '503_SERVICE_UNAVAILABLE';
      record.error_message = 'Cannot stop run: Supervisor offline';
      this.saveState();
      throw new Error(record.error_message);
    }

    const targetRun = this.runs.find(r => r.run_id === runId);
    if (!targetRun) {
      record.status = 'failed';
      record.error_code = 'RUN_NOT_FOUND';
      record.error_message = `Run ID "${runId}" not found`;
      this.saveState();
      throw new Error(record.error_message);
    }

    // If already stopped, maintain idempotency
    if (targetRun.control_state === 'stopped') {
      record.status = 'success';
      const alreadyStoppedVM: SimulationRun = {
        run_id: runId,
        bot_id: targetRun.bot_id || 'bot-default',
        strategy_id: targetRun.template_id || 'sma-synthetic-smoke-v1',
        artifact_hash: targetRun.build_id || MOCK_BUILD_ID,
        control_state: 'stopped',
        symbol: 'BTC-USDT-SWAP',
        period: '15m',
        warmup_bars: targetRun.warmup_bars,
        total_bars: targetRun.bars,
        current_bar: targetRun.bars,
        trade_count: targetRun.fills,
        position_contracts: targetRun.account?.position || '0',
        equity_usdt: targetRun.account?.equity || '1000.00',
        fee_usdt: targetRun.account?.fees || '0.0005',
        pnl_usdt: targetRun.account?.realized_pnl || '0.00',
        slippage_bps: '2',
        ownership_retained: (targetRun.account?.position || '0') !== '0',
        risk_retained: (targetRun.account?.position || '0') !== '0',
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
    if (!targetRun.account) {
      targetRun.account = {
        equity: '999.98',
        position: '-1',
        balance: '1000.00',
        realized_pnl: '-0.02',
        fees: '0.0005'
      };
    }

    this.saveState();
    this.setPending(null);

    const stoppedVM: SimulationRun = {
      run_id: runId,
      bot_id: targetRun.bot_id || 'bot-default',
      strategy_id: targetRun.template_id || 'sma-synthetic-smoke-v1',
      artifact_hash: targetRun.build_id || MOCK_BUILD_ID,
      control_state: 'stopped',
      symbol: 'BTC-USDT-SWAP',
      period: '15m',
      warmup_bars: targetRun.warmup_bars,
      total_bars: targetRun.bars,
      current_bar: targetRun.bars,
      trade_count: targetRun.fills,
      position_contracts: targetRun.account.position,
      equity_usdt: targetRun.account.equity,
      fee_usdt: targetRun.account.fees,
      pnl_usdt: targetRun.account.realized_pnl,
      slippage_bps: '2',
      ownership_retained: targetRun.account.position !== '0',
      risk_retained: targetRun.account.position !== '0',
      created_at: targetRun.created_at,
      updated_at: targetRun.finished_at || targetRun.created_at
    };

    record.status = 'success';
    record.response = stoppedVM as any;
    this.saveState();
    return stoppedVM;
  }

  public async retryPendingCommand(): Promise<any> {
    if (!this.pendingCommand) {
      throw new Error('No pending command to retry');
    }
    const cmd = this.pendingCommand;
    if (cmd.path.endsWith('/start')) {
      return this.startBot(cmd.body.request_id, cmd.body.bot_id);
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
