import { ref, reactive, watch } from 'vue';
import type { BotMode, TelemetryState } from '@/contracts';
import type { ScenarioType } from '@/adapters/types';
import { activeAdapter } from '@/adapters/mock-adapter';

const currentMode = ref<BotMode>('local');
const activeScenario = ref<ScenarioType>('normal');
const showTelemetryPopover = ref<boolean>(false);
const modeNotice = ref<string | null>(null);

const telemetry = reactive<TelemetryState>({
  connected: true,
  supervisor_pid: 4821,
  latency_ms: 16,
  fixed_tag: '41cb53c54d6dABDE',
  settlement_mode: 'cross_net_mode',
  core_arithmetic: 'Decimal_SQLite_TEXT',
  last_heartbeat: new Date().toISOString()
});

export function useWorkspace() {
  async function refreshTelemetry() {
    try {
      const res = await activeAdapter.fetchTelemetry();
      Object.assign(telemetry, res);
    } catch {
      telemetry.connected = false;
      telemetry.latency_ms = 0;
      telemetry.supervisor_pid = 0;
      telemetry.last_heartbeat = 'OFFLINE';
    }
  }

  function setScenario(s: ScenarioType) {
    activeScenario.value = s;
    activeAdapter.setScenario(s);
    refreshTelemetry();
  }

  function setMode(m: BotMode) {
    currentMode.value = m;
    activeAdapter.setMode?.(m);
    if (m === 'demo') {
      modeNotice.value = 'Demo 模式唯讀隔離展示 · 實盤對帳未通過，所有交易下單與增倉控制已鎖定';
    } else if (m === 'live') {
      modeNotice.value = 'Live 實盤已鎖定 · 嚴格禁止接觸真實 OKX 金鑰，維持本機隔離安全';
    } else {
      modeNotice.value = null;
    }
  }

  function toggleTelemetryPopover() {
    showTelemetryPopover.value = !showTelemetryPopover.value;
  }

  // Sync telemetry initially and whenever scenario changes
  watch(
    () => activeScenario.value,
    () => {
      refreshTelemetry();
    },
    { immediate: true }
  );

  return {
    currentMode,
    activeScenario,
    telemetry,
    showTelemetryPopover,
    modeNotice,
    setScenario,
    setMode,
    refreshTelemetry,
    toggleTelemetryPopover
  };
}
