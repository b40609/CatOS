/**
 * catOS State Adapter
 *
 * Bridges the simulation HTTP adapter to the Zustand store:
 * 1. Polls GET /state?since_version=N (1 s while a run is active, 5 s idle,
 *    paused while the document is hidden) and applies each domain through
 *    the store's monotonic version guard.
 * 2. A new backend instance_id clears every version and projection first.
 * 3. Demo/Live load nothing: the adapter reports "mode_not_open" and the store
 *    shows that state; no request is sent and no fixture is substituted.
 * 4. Mutations go through startBot/stopBot only; a response triggers an
 *    immediate full refresh instead of optimistic edits.
 */

import { ResearchApiError } from '@/adapters/research-api-adapter';
import { newRequestId, simulationApi } from '@/adapters/simulation-api-adapter';
import type { WorkspaceAdapter } from '@/adapters/types';
import type { BotMode, CommandType, EventDTO, WorkspaceStateDTO } from '@/contracts';
import { ACTIVE_STATES } from '@/contracts';
import { useCatStore } from './catStore';

export const ACTIVE_POLL_MS = 1000;
export const IDLE_POLL_MS = 5000;
const EVENT_PAGE = 200;
const MAX_BACKFILL_PAGES = 2;

export class StateAdapter {
  private static instance: StateAdapter;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private inflight: Promise<void> | null = null;
  private visibilityBound = false;

  constructor(private readonly adapter: WorkspaceAdapter = simulationApi) {}

  public static getInstance(): StateAdapter {
    if (!StateAdapter.instance) StateAdapter.instance = new StateAdapter();
    return StateAdapter.instance;
  }

  /** First load for the current mode, then start polling (local only). */
  public async init(): Promise<void> {
    const store = useCatStore.getState();
    const generation = store.modeGeneration;
    this.adapter.setMode(store.mode);
    store.setConnection({ status: 'loading', detail: null, http_status: null });
    await this.refresh(generation, { full: true, backfill: true });
    if (useCatStore.getState().modeGeneration !== generation) return;
    if (useCatStore.getState().mode === 'local') this.startPolling();
  }

  /**
   * Apply one authoritative state payload. Pure with respect to HTTP, so tests
   * drive it directly. Returns false when every domain was stale.
   */
  public applyState(state: WorkspaceStateDTO): boolean {
    const store = useCatStore.getState();
    if (store.instanceId !== state.instance_id) store.resetInstance(state.instance_id);
    let applied = false;
    const versions = state.domains;
    const current = useCatStore.getState();
    const globalOk = state.version >= (current.versionMap.global ?? 0);
    if (!globalOk) return false;
    applied = current.applyAuthoritativeUpdate('service', versions.service, () => ({
      service: state.service, strategies: state.strategies,
    })) || applied;
    applied = current.applyAuthoritativeUpdate('bots', versions.bots, () => ({ bots: state.bots })) || applied;
    applied = current.applyAuthoritativeUpdate('risk', versions.risk, () => ({
      risk: state.risk, killSwitch: state.kill_switch ?? null,
    })) || applied;
    applied = current.applyAuthoritativeUpdate('positions', versions.positions, () => ({ positions: state.positions })) || applied;
    // summary derives from bots + risk: version with the newer of the two
    current.applyAuthoritativeUpdate('summary', Math.max(versions.bots, versions.risk), () => ({ summary: state.summary }));
    if (current.applyAuthoritativeUpdate('events', versions.events, () => ({}))) {
      useCatStore.getState().mergeEvents(state.events.items, state.events.omitted);
      applied = true;
    }
    current.applyAuthoritativeUpdate('global', state.version, () => ({}));
    return applied;
  }

  private async refresh(generation: number, options: { full?: boolean; backfill?: boolean } = {}): Promise<void> {
    if (this.inflight) return this.inflight;
    this.inflight = this.refreshNow(generation, options).finally(() => { this.inflight = null; });
    return this.inflight;
  }

  private async refreshNow(generation: number, options: { full?: boolean; backfill?: boolean }): Promise<void> {
    const store = useCatStore.getState();
    const since = options.full ? undefined : store.versionMap.global;
    try {
      const result = await this.adapter.fetchState(since);
      if (useCatStore.getState().modeGeneration !== generation) return;
      if (!result.available) {
        useCatStore.getState().setConnection({ status: 'mode_not_open', detail: result.reason, http_status: null, polling: false });
        return;
      }
      const data = result.data;
      if (!data.unchanged) {
        const before = useCatStore.getState().eventsNextSince;
        this.applyState(data);
        const after = useCatStore.getState();
        const oldest = data.events.items.length ? data.events.items[0].seq : null;
        // The aggregate carries only the newest 40 events; fill any gap since our cursor.
        if (options.backfill || (before > 0 && oldest !== null && oldest > before + 1)) {
          await this.backfillEvents(generation, options.backfill ? 0 : before);
        }
        if (after.pendingCommand === null) {
          const pending = this.adapter.getPendingCommand();
          if (pending) useCatStore.getState().setPendingCommand(pending);
        }
      }
      useCatStore.getState().setConnection({ status: 'ok', detail: null, http_status: 200, last_ok_ms: Date.now() });
    } catch (err) {
      if (useCatStore.getState().modeGeneration !== generation) return;
      const error = err instanceof ResearchApiError ? err : new ResearchApiError(0, 'network_error');
      useCatStore.getState().setConnection({
        status: error.status === 503 ? 'unavailable' : 'error',
        detail: error.detail, http_status: error.status,
      });
    }
  }

  private async backfillEvents(generation: number, since: number): Promise<void> {
    let cursor = since;
    for (let page = 0; page < MAX_BACKFILL_PAGES; page++) {
      const result = await this.adapter.fetchEvents(cursor, EVENT_PAGE);
      if (!result.available || useCatStore.getState().modeGeneration !== generation) return;
      useCatStore.getState().mergeEvents(result.data.items, result.data.omitted);
      if (!result.data.more) return;
      cursor = result.data.next_since;
    }
  }

  // ---- polling -----------------------------------------------------------

  public startPolling() {
    this.stopPolling();
    useCatStore.getState().setConnection({ polling: true });
    if (typeof document !== 'undefined' && !this.visibilityBound) {
      document.addEventListener('visibilitychange', this.onVisibility);
      this.visibilityBound = true;
    }
    this.schedule();
  }

  public stopPolling() {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    if (useCatStore.getState().connection.polling) useCatStore.getState().setConnection({ polling: false });
  }

  public pollIntervalMs(): number {
    const state = useCatStore.getState();
    const active = state.service?.active_run_id !== null && state.service?.active_run_id !== undefined
      || state.bots.some((bot) => ACTIVE_STATES.has(bot.state));
    return active ? ACTIVE_POLL_MS : IDLE_POLL_MS;
  }

  private schedule() {
    if (this.timer !== null) clearTimeout(this.timer);
    if (typeof document !== 'undefined' && document.hidden) { this.timer = null; return; }
    this.timer = setTimeout(() => { void this.tick(); }, this.pollIntervalMs());
  }

  private async tick() {
    const store = useCatStore.getState();
    if (store.mode !== 'local') { this.stopPolling(); return; }
    await this.refresh(store.modeGeneration);
    if (useCatStore.getState().connection.polling) this.schedule();
  }

  private onVisibility = () => {
    if (typeof document === 'undefined') return;
    if (document.hidden) {
      if (this.timer !== null) clearTimeout(this.timer);
      this.timer = null;
    } else if (useCatStore.getState().connection.polling) {
      void this.tick();
    }
  };

  /** Force a full refresh now (after a command, or on user request). */
  public async refreshNowFull(): Promise<void> {
    await this.refresh(useCatStore.getState().modeGeneration, { full: true });
  }

  // ---- mode --------------------------------------------------------------

  public async setMode(mode: BotMode): Promise<void> {
    const store = useCatStore.getState();
    if (store.mode === mode) return;
    this.stopPolling();
    this.adapter.setMode(mode);
    store.setMode(mode);
    await this.init();
  }

  // ---- commands ----------------------------------------------------------

  private record(type: CommandType, requestId: string | null, body: Record<string, string>,
                 status: 'success' | 'failed' | 'uncertain', extra: { http_status?: number; error_code?: string; run_id?: string }) {
    if (!requestId) return;
    useCatStore.getState().addCommandRecord({
      request_id: requestId, command_type: type, body, timestamp_ms: Date.now(), status, ...extra,
    });
  }

  public async startBot(botId: string, requestId?: string): Promise<void> {
    const generation = useCatStore.getState().modeGeneration;
    const id = requestId ?? newRequestId();
    try {
      const result = await this.adapter.startBot(botId, id);
      useCatStore.getState().setPendingCommand(null);
      this.record('start_bot', id, { bot_id: botId }, 'success', { http_status: 202, run_id: result.run.run_id });
    } catch (err) {
      const error = err instanceof ResearchApiError ? err : new ResearchApiError(0, 'network_error');
      useCatStore.getState().setPendingCommand(this.adapter.getPendingCommand());
      this.record('start_bot', id, { bot_id: botId }, error.status === 0 ? 'uncertain' : 'failed',
        { http_status: error.status, error_code: error.detail });
      throw error;
    } finally {
      if (useCatStore.getState().modeGeneration === generation && useCatStore.getState().mode === 'local') {
        await this.refresh(generation, { full: true });
      }
    }
  }

  public async stopBot(runId: string, requestId?: string): Promise<void> {
    const generation = useCatStore.getState().modeGeneration;
    const id = requestId ?? newRequestId();
    try {
      await this.adapter.stopBot(runId, id);
      useCatStore.getState().setPendingCommand(null);
      this.record('stop_bot', id, { run_id: runId }, 'success', { http_status: 202, run_id: runId });
    } catch (err) {
      const error = err instanceof ResearchApiError ? err : new ResearchApiError(0, 'network_error');
      useCatStore.getState().setPendingCommand(this.adapter.getPendingCommand());
      this.record('stop_bot', id, { run_id: runId }, error.status === 0 ? 'uncertain' : 'failed',
        { http_status: error.status, error_code: error.detail });
      throw error;
    } finally {
      if (useCatStore.getState().modeGeneration === generation && useCatStore.getState().mode === 'local') {
        await this.refresh(generation, { full: true });
      }
    }
  }

  /** Kill-Switch engage (work package B). Anyone may engage; the backend stops runs before their next bar. */
  public async engageKill(reason: string, requestId?: string): Promise<void> {
    await this.killCommand('kill_engage', { reason }, requestId,
      (id) => this.adapter.engageKill(reason, id));
  }

  /** Kill-Switch clear: the user only, with a reason and the typed confirmation word. */
  public async clearKill(reason: string, confirm: string, requestId?: string): Promise<void> {
    await this.killCommand('kill_clear', { reason }, requestId,
      (id) => this.adapter.clearKill(reason, confirm, id));
  }

  private async killCommand(type: 'kill_engage' | 'kill_clear', body: Record<string, string>,
                            requestId: string | undefined, send: (id: string) => Promise<unknown>): Promise<void> {
    const generation = useCatStore.getState().modeGeneration;
    const id = requestId ?? newRequestId();
    try {
      await send(id);
      useCatStore.getState().setPendingCommand(null);
      this.record(type, id, body, 'success', { http_status: 200 });
    } catch (err) {
      const error = err instanceof ResearchApiError ? err : new ResearchApiError(0, 'network_error');
      useCatStore.getState().setPendingCommand(this.adapter.getPendingCommand());
      this.record(type, id, body, error.status === 0 ? 'uncertain' : 'failed',
        { http_status: error.status, error_code: error.detail });
      throw error;
    } finally {
      if (useCatStore.getState().modeGeneration === generation && useCatStore.getState().mode === 'local') {
        await this.refresh(generation, { full: true });
      }
    }
  }

  /** Replay the persisted command with its original request_id (idempotent on the backend). */
  public async retryPendingCommand(): Promise<void> {
    const pending = this.adapter.getPendingCommand();
    if (!pending) { useCatStore.getState().setPendingCommand(null); return; }
    if (pending.command_type === 'start_bot') {
      await this.startBot(pending.body.bot_id, pending.body.request_id);
    } else if (pending.command_type === 'kill_engage') {
      await this.engageKill(pending.body.reason, pending.body.request_id);
    } else if (pending.command_type === 'kill_clear') {
      await this.clearKill(pending.body.reason, pending.body.confirm, pending.body.request_id);
    } else {
      const runId = pending.path.split('/').at(-2) ?? '';
      await this.stopBot(runId, pending.body.request_id);
    }
  }

  public discardPendingCommand() {
    this.adapter.clearPendingCommand();
    useCatStore.getState().setPendingCommand(null);
  }

  /** Equity curve for charts: signal events of the latest run, oldest first. */
  public static equityCurve(events: EventDTO[], runId: string | null): Array<{ seq: number; time_ms: number | null; equity: string }> {
    if (!runId) return [];
    return events
      .filter((e) => e.run_id === runId && e.kind === 'signal' && typeof (e.payload as { account?: { equity?: string } }).account?.equity === 'string')
      .map((e) => ({ seq: e.seq, time_ms: e.synthetic_time_ms, equity: (e.payload as { account: { equity: string } }).account.equity }));
  }
}

export const stateAdapter = StateAdapter.getInstance();
