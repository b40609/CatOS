/**
 * Workspace adapter interface (v1, Q9 slimmed).
 *
 * Components never call fetch; they read the store, and the state adapter
 * drives this interface. Reads return a typed availability result so that
 * Demo/Live, which are not open in v1, surface as "not available" instead of
 * as fixture data or thrown errors. Mutations reject with ResearchApiError.
 */
import type {
  BotMode,
  EventsPageDTO,
  KillSwitchCommandResponseDTO,
  PendingCommand,
  RunDTO,
  StartBotResponseDTO,
  VersionDTO,
  WorkspaceStateResponse,
} from '@/contracts';

export type UnavailableReason = 'mode_not_open';

export interface Unavailable {
  available: false;
  reason: UnavailableReason;
  mode: BotMode;
}

export interface Available<T> {
  available: true;
  data: T;
}

export type AdapterResult<T> = Available<T> | Unavailable;

export interface WorkspaceAdapter {
  readonly mode: BotMode;
  setMode(mode: BotMode): void;

  fetchVersion(signal?: AbortSignal): Promise<AdapterResult<VersionDTO>>;
  fetchState(sinceVersion?: number, signal?: AbortSignal): Promise<AdapterResult<WorkspaceStateResponse>>;
  fetchEvents(since: number, limit?: number, signal?: AbortSignal): Promise<AdapterResult<EventsPageDTO>>;

  /** POST /bots/start; a stored request_id replays the same command. */
  startBot(botId: string, requestId?: string): Promise<StartBotResponseDTO>;
  /** POST /runs/{run_id}/stop; stop completes the current accounting event first. */
  stopBot(runId: string, requestId?: string): Promise<RunDTO>;

  /** POST /kill-switch/engage; anyone may engage (the safe direction). */
  engageKill(reason: string, requestId?: string): Promise<KillSwitchCommandResponseDTO>;
  /** POST /kill-switch/clear; the user only, with a reason and the typed confirmation word. */
  clearKill(reason: string, confirm: string, requestId?: string): Promise<KillSwitchCommandResponseDTO>;

  getPendingCommand(): PendingCommand | null;
  clearPendingCommand(): void;
}
