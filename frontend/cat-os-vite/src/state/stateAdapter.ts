/**
 * catOS State Adapter
 * 
 * Bridges REST/WebSocket data to Zustand Store.
 * Enforces:
 * 1. Monotonic Version Guard: Stale REST/WS updates are rejected when version is smaller than stored version.
 * 2. Supervisor Authority: Frontend never infers bot lifecycle or risk state; only projects authoritative payloads.
 * 3. Mode Isolation: In Demo/Live mode, simulation resources are hidden or locked.
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
   * Initializes the workspace state from authoritative source (currently mock-adapter)
   */
  public async init(scenario: ScenarioType = 'normal'): Promise<void> {
    const store = useCatStore.getState();
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

    const pendingCmd = mockAdapter.getPendingCommand();
    const commandLogs = mockAdapter.getCommandLogs();

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
   * Change bot execution mode (local, demo, live)
   */
  public setMode(mode: BotMode): void {
    const store = useCatStore.getState();
    store.setMode(mode);
    if (mockAdapter.setMode) {
      mockAdapter.setMode(mode);
    }
  }
}

export const stateAdapter = StateAdapter.getInstance();
