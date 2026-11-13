/**
 * Simulation workspace HTTP adapter (strict real adapter).
 *   GET  /api/workspace/simulation/version
 *   GET  /api/workspace/simulation/state[?since_version=N]
 *   GET  /api/workspace/simulation/events?since=N&limit=M
 *   POST /api/workspace/simulation/bots/start
 *   POST /api/workspace/simulation/runs/{run_id}/stop
 *   POST /api/workspace/simulation/kill-switch/engage
 *   POST /api/workspace/simulation/kill-switch/clear   (user only: reason + typed 解除)
 *
 * Invariants (shared with research-api-adapter):
 * 1. Decimal strings pass through untouched.
 * 2. Local mode never falls back to fixture data on network or parse errors.
 * 3. A failed POST never fabricates a run, success or automatic retry; the
 *    request_id is persisted before the request so a retry replays it.
 * 4. 403/409/413/415/422/503 details are preserved verbatim.
 * 5. Demo/Live send no request: reads resolve to {available:false}, mutations
 *    reject with 403 mode_not_available.
 */
import { ResearchApiError } from '@/adapters/research-api-adapter';
import type { AdapterResult, WorkspaceAdapter } from '@/adapters/types';
import type {
  BotMode,
  CommandType,
  EventsPageDTO,
  KillSwitchCommandResponseDTO,
  PendingCommand,
  RunDTO,
  StartBotResponseDTO,
  VersionDTO,
  WorkspaceStateResponse,
} from '@/contracts';

export const SIMULATION_PREFIX = '/api/workspace/simulation';
export const PENDING_COMMAND_KEY = 'catos.simulation.pending_command';
export const MAX_EVENT_LIMIT = 200;
const REQUEST_ID = /^[0-9a-f]{32}$/;

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText || 'Unknown Error';
    try {
      const data = await res.json();
      if (data && typeof data === 'object') {
        detail = data.detail || data.reason || JSON.stringify(data);
      }
    } catch {
      // Non-JSON error body
    }
    throw new ResearchApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

function networkError(err: unknown, message: string): never {
  if (err instanceof ResearchApiError) throw err;
  if (err instanceof Error && err.name === 'AbortError') throw err;
  throw new ResearchApiError(0, 'network_error', message);
}

export function newRequestId(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === 'function') return c.randomUUID().replace(/-/g, '');
  const bytes = new Uint8Array(16);
  c.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

interface Identity {
  build: string;
  instance: string;
}

export interface SimulationAdapterOptions {
  fetch?: typeof fetch;
  storage?: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> | null;
}

function defaultStorage(): Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> | null {
  try {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage;
  } catch {
    return null;
  }
}

export class SimulationApiAdapter implements WorkspaceAdapter {
  public mode: BotMode = 'local';
  private identity: Identity | null = null;
  private readonly fetchImpl: typeof fetch;
  private readonly storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> | null;

  constructor(options: SimulationAdapterOptions = {}) {
    this.fetchImpl = options.fetch ?? ((input, init) => fetch(input, init));
    this.storage = options.storage === undefined ? defaultStorage() : options.storage;
  }

  setMode(mode: BotMode) {
    this.mode = mode;
  }

  /** Build/instance identity last observed from the service; null before first contact. */
  getIdentity(): Identity | null {
    return this.identity;
  }

  private unavailable(): AdapterResult<never> {
    return { available: false, reason: 'mode_not_open', mode: this.mode };
  }

  private remember(version: VersionDTO) {
    this.identity = { build: version.build_id, instance: version.instance_id };
  }

  async fetchVersion(signal?: AbortSignal): Promise<AdapterResult<VersionDTO>> {
    if (this.mode !== 'local') return this.unavailable();
    try {
      const res = await this.fetchImpl(`${SIMULATION_PREFIX}/version`, { headers: { Accept: 'application/json' }, signal });
      const data = await handleResponse<VersionDTO>(res);
      this.remember(data);
      return { available: true, data };
    } catch (err) {
      networkError(err, '無法連線至本機模擬服務 (127.0.0.1:8770)');
    }
  }

  async fetchState(sinceVersion?: number, signal?: AbortSignal): Promise<AdapterResult<WorkspaceStateResponse>> {
    if (this.mode !== 'local') return this.unavailable();
    const query = Number.isSafeInteger(sinceVersion) && (sinceVersion as number) >= 0
      ? `?since_version=${sinceVersion}` : '';
    try {
      const res = await this.fetchImpl(`${SIMULATION_PREFIX}/state${query}`, { headers: { Accept: 'application/json' }, signal });
      const data = await handleResponse<WorkspaceStateResponse>(res);
      if (!data.unchanged) this.remember(data.service);
      return { available: true, data };
    } catch (err) {
      networkError(err, '無法讀取模擬工作區狀態');
    }
  }

  async fetchEvents(since: number, limit = 40, signal?: AbortSignal): Promise<AdapterResult<EventsPageDTO>> {
    if (this.mode !== 'local') return this.unavailable();
    if (!Number.isSafeInteger(since) || since < 0) throw new ResearchApiError(422, 'invalid_since');
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > MAX_EVENT_LIMIT) throw new ResearchApiError(422, 'invalid_limit');
    try {
      const res = await this.fetchImpl(`${SIMULATION_PREFIX}/events?since=${since}&limit=${limit}`, {
        headers: { Accept: 'application/json' }, signal,
      });
      return { available: true, data: await handleResponse<EventsPageDTO>(res) };
    } catch (err) {
      networkError(err, '無法讀取模擬事件流水');
    }
  }

  async startBot(botId: string, requestId?: string): Promise<StartBotResponseDTO> {
    return this.command<StartBotResponseDTO>(`${SIMULATION_PREFIX}/bots/start`, 'start_bot',
      { bot_id: botId }, requestId);
  }

  async stopBot(runId: string, requestId?: string): Promise<RunDTO> {
    if (!/^[0-9a-f]{32}$/.test(runId)) throw new ResearchApiError(422, 'invalid_run_id');
    return this.command<RunDTO>(`${SIMULATION_PREFIX}/runs/${runId}/stop`, 'stop_bot', {}, requestId);
  }

  async engageKill(reason: string, requestId?: string): Promise<KillSwitchCommandResponseDTO> {
    return this.command<KillSwitchCommandResponseDTO>(`${SIMULATION_PREFIX}/kill-switch/engage`, 'kill_engage',
      { reason }, requestId);
  }

  async clearKill(reason: string, confirm: string, requestId?: string): Promise<KillSwitchCommandResponseDTO> {
    return this.command<KillSwitchCommandResponseDTO>(`${SIMULATION_PREFIX}/kill-switch/clear`, 'kill_clear',
      { reason, confirm }, requestId);
  }

  getPendingCommand(): PendingCommand | null {
    try {
      const raw = this.storage?.getItem(PENDING_COMMAND_KEY);
      if (!raw) return null;
      const value = JSON.parse(raw) as PendingCommand;
      if (!value || typeof value !== 'object' || !REQUEST_ID.test(value.body?.request_id ?? '')) {
        this.clearPendingCommand();
        return null;
      }
      return value;
    } catch {
      return null;
    }
  }

  clearPendingCommand() {
    try {
      this.storage?.removeItem(PENDING_COMMAND_KEY);
    } catch {
      // storage unavailable: nothing persisted to clear
    }
  }

  private async ensureIdentity(): Promise<Identity> {
    if (this.identity) return this.identity;
    const result = await this.fetchVersion();
    if (!result.available) throw new ResearchApiError(403, 'mode_not_available');
    return { build: result.data.build_id, instance: result.data.instance_id };
  }

  private async command<T>(path: string, type: CommandType, fields: Record<string, string>,
                           requestId?: string): Promise<T> {
    if (this.mode !== 'local') throw new ResearchApiError(403, 'mode_not_available');
    if (requestId !== undefined && !REQUEST_ID.test(requestId)) throw new ResearchApiError(422, 'invalid_command_contract');
    const identity = await this.ensureIdentity();
    const body = { request_id: requestId ?? newRequestId(), ...fields };
    const pending: PendingCommand = {
      path, command_type: type, body, build: identity.build, instance: identity.instance,
      timestamp_ms: Date.now(),
    };
    // Persist before the request leaves: an uncertain outcome (network loss)
    // must be retried with this request_id, never with a fresh one.
    try {
      this.storage?.setItem(PENDING_COMMAND_KEY, JSON.stringify(pending));
    } catch {
      // storage unavailable: the in-memory flow still binds this request_id
    }
    let res: Response;
    try {
      res = await this.fetchImpl(path, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
          'X-CatOS-Build': identity.build,
          'X-CatOS-Instance': identity.instance,
        },
        body: JSON.stringify(body),
      });
    } catch (err) {
      // Outcome unknown: keep the pending command for an explicit replay.
      networkError(err, `命令送出後未收到回應 (request_id ${body.request_id})；請先確認狀態再重送同一命令`);
    }
    // Any HTTP response is a definitive answer for this request_id.
    this.clearPendingCommand();
    return handleResponse<T>(res);
  }
}

export const simulationApi = new SimulationApiAdapter();
