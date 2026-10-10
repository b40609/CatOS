/**
 * catOS v1 - Codex API Adapter Specification & DOM Mapping
 * 
 * This specification document guides Codex on how to wire the redesigned
 * frontend to real localhost endpoints without breaking existing core contracts.
 */

export const CODEX_INTEGRATION_SPEC = {
  version: "catos.frontend-redesign.v1",
  endpoints: {
    telemetryVersion: {
      url: "/api/workspace/version",
      method: "GET",
      returns: ["contract", "build_id", "current_build_id", "restart_required", "preview"]
    },
    simulationVersion: {
      url: "/api/workspace/simulation/version",
      method: "GET",
      returns: ["contract", "build_id", "instance_id", "mode"]
    },
    listRuns: {
      url: "/api/workspace/simulation/runs",
      method: "GET",
      returns: ["items[]", "active_run_id", "instances"]
    },
    runSnapshot: {
      url: "/api/workspace/simulation/runs/{run_id}",
      method: "GET",
      returns: ["run_id", "status", "bot_id", "contract", "position", "realized_pnl", "unrealized_pnl"]
    },
    startBot: {
      url: "/api/workspace/simulation/start",
      method: "POST",
      requiresHeaders: ["Content-Type: application/json", "X-CatOS-Instance", "X-CatOS-Build"],
      bodyContract: ["request_id", "template_id"]
    },
    stopBot: {
      url: "/api/workspace/simulation/runs/{run_id}/stop",
      method: "POST",
      requiresHeaders: ["Content-Type: application/json", "X-CatOS-Instance", "X-CatOS-Build"],
      bodyContract: ["request_id"]
    }
  },

  domMapping: {
    kpi: {
      totalEquity: "#kpi-total-equity",
      dailyPnl: "#kpi-daily-pnl",
      activeBotsCount: "#kpi-active-bots",
      effectiveLeverage: "#kpi-effective-leverage"
    },
    charts: {
      equityCanvasA: "#chart-equity-canvas-a",
      equityCanvasB: "#chart-equity-canvas-b",
      allocationDonut: "#svg-allocation-donut",
      exposureBars: "#exposure-bars-container"
    },
    riskGauge: {
      needle: "#gauge-needle",
      currentPnlText: "#gauge-current-val",
      softThresholdLabel: "#gauge-soft-val",
      hardThresholdLabel: "#gauge-hard-val"
    },
    tables: {
      botsTableBodyA: "#bots-table-body-a",
      botsTableBodyB: "#bots-table-body-b",
      incidentStream: "#incident-stream-list",
      attentionHubList: "#attention-hub-list"
    },
    banners: {
      alert409Banner: "#banner-409-alert",
      telemetryPopover: "#telemetry-popover"
    }
  },

  safetyInvariants: [
    "Fixed order tag 41cb53c54d6dABDE must be injected on all swap orders.",
    "Single bot contract exclusivity: 409 simulation_ownership_or_risk_retained if position is retained.",
    "Do not automatically liquidate positions on stopped status.",
    "Pending requests must retain original request_id, build, and instance on re-submission.",
    "Reloading or switching tabs must NOT emit mutation commands."
  ]
};
