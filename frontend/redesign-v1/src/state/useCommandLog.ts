import { ref, onMounted } from 'vue';
import type { CommandRecord } from '@/contracts';
import { activeAdapter } from '@/adapters/mock-adapter';

export function useCommandLog() {
  const commandLogs = ref<CommandRecord[]>(activeAdapter.getCommandLogs());

  function refreshLogs() {
    commandLogs.value = activeAdapter.getCommandLogs();
  }

  onMounted(() => {
    refreshLogs();
  });

  return {
    commandLogs,
    refreshLogs
  };
}
