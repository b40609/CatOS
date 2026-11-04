import { create } from 'zustand';
import type {
  BotMode,
  BotViewDTO,
  CommandRecord,
  EventDTO,
  PendingCommand,
  PositionDTO,
  RegisteredStrategyDTO,
  RiskSnapshotDTO,
  SummaryDTO,
  VersionDTO,
} from '@/contracts';

export type Language = 'zh-TW' | 'en';

export type ConnectionStatus = 'idle' | 'loading' | 'ok' | 'error' | 'unavailable' | 'mode_not_open';

export interface ConnectionState {
  status: ConnectionStatus;
  detail: string | null;      // backend error code or network_error
  http_status: number | null;
  last_ok_ms: number | null;
  polling: boolean;
}

export const MAX_STORED_EVENTS = 400;

const IDLE_CONNECTION: ConnectionState = { status: 'idle', detail: null, http_status: null, last_ok_ms: null, polling: false };

export interface CatState {
  // Navigation & Mode
  activeTab: 'dashboard' | 'bots' | 'risk' | 'strategies' | 'logs' | 'settings';
  mode: BotMode;
  modeGeneration: number;
  language: Language;

  // Authoritative projections (GET /state domains)
  instanceId: string | null;
  service: VersionDTO | null;
  strategies: RegisteredStrategyDTO[];
  bots: BotViewDTO[];
  risk: RiskSnapshotDTO | null;
  positions: PositionDTO[];
  summary: SummaryDTO | null;
  events: EventDTO[];          // ascending by seq, capped at MAX_STORED_EVENTS
  eventsNextSince: number;     // highest seq held
  eventsOmitted: number;       // backend ring-buffer losses, reported not hidden

  connection: ConnectionState;
  pendingCommand: PendingCommand | null;
  commandHistory: CommandRecord[];

  // Anti-race: monotonic version per domain ("global" tracks state_version)
  versionMap: Record<string, number>;

  setActiveTab: (tab: CatState['activeTab']) => void;
  setMode: (mode: BotMode) => void;
  setLanguage: (lang: Language) => void;

  /** Apply an update only when `version` is not older than the domain's current version. */
  applyAuthoritativeUpdate: (domain: string, version: number, updateFn: (state: CatState) => Partial<CatState>) => boolean;
  /** A new backend instance invalidates every version; projections are rebuilt from its first state. */
  resetInstance: (instanceId: string) => void;
  /** Merge an events page (dedup by seq, ascending, capped). */
  mergeEvents: (items: EventDTO[], omitted?: number) => void;
  setConnection: (patch: Partial<ConnectionState>) => void;
  setPendingCommand: (command: PendingCommand | null) => void;
  addCommandRecord: (record: CommandRecord) => void;
}

function cleared(): Pick<CatState, 'instanceId' | 'service' | 'strategies' | 'bots' | 'risk' | 'positions' | 'summary'
  | 'events' | 'eventsNextSince' | 'eventsOmitted' | 'pendingCommand' | 'commandHistory' | 'versionMap'> {
  return {
    instanceId: null, service: null, strategies: [], bots: [], risk: null, positions: [], summary: null,
    events: [], eventsNextSince: 0, eventsOmitted: 0, pendingCommand: null, commandHistory: [], versionMap: {},
  };
}

export const useCatStore = create<CatState>((set, get) => ({
  activeTab: 'dashboard',
  mode: 'local',
  modeGeneration: 0,
  language: (() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem('catos_language');
        if (saved === 'en' || saved === 'zh-TW') return saved;
      } catch {
        // storage unavailable
      }
    }
    return 'zh-TW';
  })(),
  ...cleared(),
  connection: IDLE_CONNECTION,

  setActiveTab: (tab) => set({ activeTab: tab }),
  setMode: (mode) => set((state) => state.mode === mode ? {} : {
    mode,
    modeGeneration: state.modeGeneration + 1,
    connection: IDLE_CONNECTION,
    ...cleared(),
  }),
  setLanguage: (lang) => {
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem('catos_language', lang);
      } catch {
        // storage unavailable
      }
    }
    set({ language: lang });
  },

  applyAuthoritativeUpdate: (domain, version, updateFn) => {
    if (!Number.isSafeInteger(version) || version < 0) return false;
    const currentVersion = get().versionMap[domain] ?? 0;
    if (version < currentVersion) {
      console.warn(`[CatStore] Dropping stale update for '${domain}': incoming version ${version} < current ${currentVersion}`);
      return false;
    }
    set((state) => ({
      ...updateFn(state),
      versionMap: { ...state.versionMap, [domain]: version },
    }));
    return true;
  },

  resetInstance: (instanceId) => set((state) => ({
    ...cleared(),
    instanceId,
    connection: state.connection,
  })),

  mergeEvents: (items, omitted) => set((state) => {
    if (items.length === 0 && omitted === undefined) return {};
    const bySeq = new Map<number, EventDTO>();
    for (const event of state.events) bySeq.set(event.seq, event);
    for (const event of items) {
      if (Number.isSafeInteger(event.seq) && event.seq > 0) bySeq.set(event.seq, event);
    }
    const merged = [...bySeq.values()].sort((a, b) => a.seq - b.seq).slice(-MAX_STORED_EVENTS);
    return {
      events: merged,
      eventsNextSince: merged.length ? merged[merged.length - 1].seq : state.eventsNextSince,
      eventsOmitted: omitted ?? state.eventsOmitted,
    };
  }),

  setConnection: (patch) => set((state) => ({ connection: { ...state.connection, ...patch } })),
  setPendingCommand: (pendingCommand) => set({ pendingCommand }),
  addCommandRecord: (record) => set((s) => ({
    commandHistory: [record, ...s.commandHistory.filter((r) => r.request_id !== record.request_id)].slice(0, 50),
  })),
}));
