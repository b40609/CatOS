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
  setMode: (mode) => set({ mode }),
  setScenario: (scenario) => set({ activeScenario: scenario }),
  setLanguage: (lang) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('catos_language', lang);
    }
    set({ language: lang });
  },

  applyAuthoritativeUpdate: (domain, version, updateFn) => {
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
    set((state) => ({
      kpis: payload.kpis ?? state.kpis,
      bots: payload.bots ?? state.bots,
      strategies: payload.strategies ?? state.strategies,
      risk: payload.risk ?? state.risk,
      telemetry: payload.telemetry ?? state.telemetry,
      equitySeries: payload.equitySeries ?? state.equitySeries,
      auditLogs: payload.auditLogs ?? state.auditLogs,
      versionMap: {
        ...state.versionMap,
        global: Math.max(state.versionMap.global ?? 0, v),
      },
    }));
  },

  setPendingCommands: (pendingCommands) => set({ pendingCommands }),
  addCommandRecord: (record) => set((s) => ({ commandHistory: [record, ...s.commandHistory] })),
}));
