/**
 * catOS State Adapter
 * 
 * Bridges REST/WebSocket data to Zustand Store.
 * Enforces:
 * 1. Monotonic Version Guard: Stale REST/WS updates are rejected when version is smaller than stored version.
 * 2. Current source is mock-adapter; these projections are not Supervisor acknowledgements.
 * 3. Mode selection only changes mock presentation; it does not connect Demo/Live accounts.
 */

import { useCatStore } from './catStore';
import { mockAdapter } from '@/adapters/mock-adapter';
import type { ScenarioType } from '@/adapters/types';
import type { BotMode } from '@/contracts';

export class StateAdapter {
  private static instance: StateAdapter;

  public static getInstance(): StateAdapter {
    if (!StateAdapter.instance) {
      StateAdapter.instance = new StateAdapter();
    }
    return StateAdapter.instance;
  }

  /**
   * Initializes the workspace presentation from mock-adapter.
   */
  public async init(scenario: ScenarioType = 'normal'): Promise<void> {
    const store = useCatStore.getState();
    const modeGeneration = store.modeGeneration;
    store.setScenario(scenario);

    const [kpis, bots, strategies, risk, telemetry, equitySeries, auditLogs] =
      await Promise.all([
        mockAdapter.fetchDashboardKPIs(),
        mockAdapter.fetchBotQueue(),
        mockAdapter.fetchStrategies(),
        mockAdapter.fetchRiskState(),
        mockAdapter.fetchTelemetry(),
        mockAdapter.fetchEquityCurve('30D'),
        mockAdapter.fetchAuditEvents(),
      ]);

    if (useCatStore.getState().modeGeneration !== modeGeneration) return;

    const pendingCmd = store.mode === 'local' ? mockAdapter.getPendingCommand() : null;
    const commandLogs = store.mode === 'local' ? mockAdapter.getCommandLogs() : [];

    store.hydrateAll({
      kpis,
      bots,
      strategies,
      risk,
      telemetry,
      equitySeries,
      auditLogs,
      version: 1,
    });

    if (pendingCmd) {
      store.setPendingCommands([pendingCmd]);
    } else {
      store.setPendingCommands([]);
    }

    // Sync command history
    commandLogs.forEach((log) => store.addCommandRecord(log));
  }

  /**
   * Handles incoming WebSocket or REST event with monotonic version check
   */
  public handleEvent(event: {
    domain: 'bots' | 'risk' | 'kpis' | 'telemetry' | 'orders';
    version: number;
    payload: any;
  }): boolean {
    const store = useCatStore.getState();
    return store.applyAuthoritativeUpdate(event.domain, event.version, () => {
      switch (event.domain) {
        case 'bots':
          return { bots: event.payload };
        case 'risk':
          return { risk: event.payload };
        case 'kpis':
          return { kpis: event.payload };
        case 'telemetry':
          return { telemetry: event.payload };
        default:
          return {};
      }
    });
  }

  /**
   * Change scenario for verification
   */
  public async switchScenario(scenario: ScenarioType): Promise<void> {
    mockAdapter.setScenario(scenario);
    await this.init(scenario);
  }

  /**
   * Switch mock presentation mode and load its isolated projections.
   */
  public async setMode(mode: BotMode): Promise<void> {
    const store = useCatStore.getState();
    if (store.mode === mode) return;
    mockAdapter.setMode(mode);
    store.setMode(mode);
    await this.init(store.activeScenario);
  }
}

export const stateAdapter = StateAdapter.getInstance();
