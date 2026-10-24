import { create } from 'zustand';
import type {
  DashboardKPIs,
  EquityPoint,
  ResearchTask,
  YaoziAlert,
  ScenarioType,
} from '@/adapters/types';
import type {
  Bot,
  StrategyEntry,
  RiskState,
  TelemetryState,
  AuditLogItem,
  PendingCommand,
  CommandRecord,
  BotMode,
} from '@/contracts';

export type Language = 'zh-TW' | 'en';

export interface CatState {
  // Navigation & Mode
  activeTab: 'dashboard' | 'bots' | 'risk' | 'strategies' | 'logs' | 'settings';
  mode: BotMode;
  modeGeneration: number;
  activeScenario: ScenarioType;
  language: Language;
  
  // Authoritative State Projections
  kpis: DashboardKPIs | null;
  bots: Bot[];
  strategies: StrategyEntry[];
  risk: RiskState | null;
  telemetry: TelemetryState | null;
  equitySeries: EquityPoint[];
  researchTasks: ResearchTask[];
  yaoziAlerts: YaoziAlert[];
  auditLogs: AuditLogItem[];
  pendingCommands: PendingCommand[];
  commandHistory: CommandRecord[];

  // Anti-Race Condition: Monotonic Version Tracking per domain
  versionMap: Record<string, number>;

  // Actions
  setActiveTab: (tab: CatState['activeTab']) => void;
  setMode: (mode: BotMode) => void;
  setScenario: (scenario: ScenarioType) => void;
  setLanguage: (lang: Language) => void;
  
  // Safe State Updates with Version Guard
  applyAuthoritativeUpdate: (domain: string, version: number, updateFn: (state: CatState) => Partial<CatState>) => boolean;
  
  // Bulk hydration
  hydrateAll: (payload: {
    kpis?: DashboardKPIs;
    bots?: Bot[];
    strategies?: StrategyEntry[];
    risk?: RiskState;
    telemetry?: TelemetryState;
    equitySeries?: EquityPoint[];
    auditLogs?: AuditLogItem[];
    version?: number;
  }) => void;

  setPendingCommands: (commands: PendingCommand[]) => void;
  addCommandRecord: (record: CommandRecord) => void;
}

export const useCatStore = create<CatState>((set, get) => ({
  activeTab: 'dashboard',
  mode: 'local',
  modeGeneration: 0,
  activeScenario: 'normal',
  language: (() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('catos_language');
      if (saved === 'en' || saved === 'zh-TW') return saved;
    }
    return 'zh-TW';
  })(),
  kpis: null,
  bots: [],
  strategies: [],
  risk: null,
  telemetry: null,
  equitySeries: [],
  researchTasks: [],
  yaoziAlerts: [],
  auditLogs: [],
  pendingCommands: [],
  commandHistory: [],
  versionMap: {},

  setActiveTab: (tab) => set({ activeTab: tab }),
  setMode: (mode) => set((state) => state.mode === mode ? {} : {
    mode,
    modeGeneration: state.modeGeneration + 1,
    kpis: null,
    bots: [],
    strategies: [],
    risk: null,
    telemetry: null,
    equitySeries: [],
    researchTasks: [],
    yaoziAlerts: [],
    auditLogs: [],
    pendingCommands: [],
    commandHistory: [],
    versionMap: {},
  }),
  setScenario: (scenario) => set({ activeScenario: scenario }),
  setLanguage: (lang) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('catos_language', lang);
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
      versionMap: {
        ...state.versionMap,
        [domain]: version,
      },
    }));
    return true;
  },

  hydrateAll: (payload) => {
    const v = payload.version ?? Date.now();
    if (!Number.isSafeInteger(v) || v < 0) return;
    set((state) => {
      const update: Partial<CatState> = {};
      const versionMap: Record<string, number> = { ...state.versionMap, global: Math.max(state.versionMap.global ?? 0, v) };
      for (const domain of ['kpis', 'bots', 'strategies', 'risk', 'telemetry', 'equitySeries', 'auditLogs'] as const) {
        if (payload[domain] !== undefined && v >= (state.versionMap[domain] ?? 0)) {
          Object.assign(update, { [domain]: payload[domain] });
          versionMap[domain] = v;
        }
      }
      return { ...update, versionMap };
    });
  },

  setPendingCommands: (pendingCommands) => set({ pendingCommands }),
  addCommandRecord: (record) => set((s) => ({ commandHistory: [record, ...s.commandHistory] })),
}));
