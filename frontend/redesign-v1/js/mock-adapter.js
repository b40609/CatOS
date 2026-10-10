/**
 * catOS v1 - Mock Adapter & Audit Log
 * 
 * Rules:
 * - Pure mock interface; does NOT call live /api/workspace/simulation mutation endpoints.
 * - Logs all UI actions to verify that navigation / reload does not trigger trading commands.
 * - Enforces clean separation between presentation layer and future Codex API connectors.
 */

import { SCENARIOS } from "../mock/scenarios.js";

class MockAdapter {
  constructor() {
    this.currentScenarioKey = "normal";
    this.currentMode = "localhost";
    this.currentLayout = "A"; // Default: Layout A
    this.commandAuditLogs = [];
    this.subscribers = [];
  }

  /**
   * Log UI operations for audit compliance
   * @param {string} action 
   * @param {Object} payload 
   */
  logAction(action, payload = {}) {
    const entry = {
      timestamp: new Date().toISOString(),
      action,
      payload,
      scenario: this.currentScenarioKey,
      mode: this.currentMode,
      noMutationTriggered: true
    };
    this.commandAuditLogs.unshift(entry);
    if (this.commandAuditLogs.length > 50) this.commandAuditLogs.pop();
    console.debug(`[catOS Mock Log] ${action}:`, payload);
  }

  getAuditLogs() {
    return this.commandAuditLogs;
  }

  getCurrentScenario() {
    return SCENARIOS[this.currentScenarioKey] || SCENARIOS.normal;
  }

  setScenario(key) {
    if (SCENARIOS[key]) {
      this.currentScenarioKey = key;
      this.logAction("SET_SCENARIO", { key });
      this.notify();
    }
  }

  setMode(mode) {
    if (mode === "demo" || mode === "live") {
      this.logAction("ATTEMPT_UNSUPPORTED_MODE", { mode, reason: "Demo/Live mode not yet open" });
      alert(`【模式提示】${mode.toUpperCase()} 模式尚未開放實盤授權，僅支援本機模擬 (Localhost)。`);
      return false;
    }
    this.currentMode = mode;
    this.logAction("SET_MODE", { mode });
    this.notify();
    return true;
  }

  setLayout(layout) {
    if (layout === "A" || layout === "B") {
      this.currentLayout = layout;
      this.logAction("SET_LAYOUT", { layout });
      this.notify();
    }
  }

  subscribe(callback) {
    this.subscribers.push(callback);
    return () => {
      this.subscribers = this.subscribers.filter(cb => cb !== callback);
    };
  }

  notify() {
    const data = this.getCurrentScenario();
    this.subscribers.forEach(cb => cb(data, this.currentLayout, this.currentScenarioKey));
  }
}

export const mockAdapter = new MockAdapter();
