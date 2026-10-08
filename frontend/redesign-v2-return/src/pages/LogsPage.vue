<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { activeAdapter } from '@/adapters/mock-adapter';
import type { AuditLogItem, CommandRecord } from '@/contracts';

const auditEvents = ref<AuditLogItem[]>([]);
const commandLogs = ref<CommandRecord[]>([]);
const selectedCategory = ref<string>('ALL');
const searchQuery = ref<string>('');
const isLiveStreaming = ref<boolean>(true);

const categories = ['ALL', 'RISK', 'ORDER', 'WORKER', 'SYSTEM'];

const filteredEvents = computed(() => {
  return auditEvents.value.filter(e => {
    const matchCat = selectedCategory.value === 'ALL' || e.category === selectedCategory.value;
    const matchQuery = !searchQuery.value.trim() || 
      e.message.toLowerCase().includes(searchQuery.value.toLowerCase()) || 
      e.category.toLowerCase().includes(searchQuery.value.toLowerCase());
    return matchCat && matchQuery;
  });
});

onMounted(async () => {
  auditEvents.value = await activeAdapter.fetchAuditEvents();
  commandLogs.value = activeAdapter.getCommandLogs();
});
</script>

<template>
  <div class="logs-page">
    <!-- Teleport Actions to Unified Header -->
    <Teleport to="#header-page-actions">
      <div class="header-actions-group">
        <span class="badge badge-sm badge-success" :class="{ 'live-pulse': isLiveStreaming }">
          ● 即時監聽中 (127.0.0.1:8770)
        </span>
      </div>
    </Teleport>

    <!-- Filter & Search Toolbar -->
    <div class="logs-toolbar">
      <div class="toolbar-left">
        <div class="category-tabs">
          <button
            v-for="cat in categories"
            :key="cat"
            type="button"
            class="tab-btn"
            :class="{ active: selectedCategory === cat }"
            @click="selectedCategory = cat"
          >
            {{ cat }}
          </button>
        </div>
      </div>

      <div class="toolbar-right">
        <div class="search-input-wrap">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            class="search-input"
            placeholder="搜尋日誌關鍵字 / 標籤..."
          />
        </div>
      </div>
    </div>

    <div class="logs-grid">
      <!-- Terminal Event Stream -->
      <div class="card terminal-card">
        <div class="card-header">
          <div class="card-title">系統事件串流 (Audit Journal)</div>
          <span class="badge badge-accent font-mono">{{ filteredEvents.length }} 筆記錄</span>
        </div>
        <div class="card-body p-0">
          <div class="stream-list">
            <div v-for="e in filteredEvents" :key="e.id" class="stream-item">
              <span class="stream-time mono tabular-nums">{{ e.timestamp }}</span>
              <span :class="['badge badge-sm', e.level === 'WARN' ? 'badge-warning' : 'badge-info']">
                {{ e.level }}
              </span>
              <span class="badge badge-sm badge-neutral">{{ e.category }}</span>
              <span class="stream-msg mono">{{ e.message }}</span>
            </div>
            <div v-if="!filteredEvents.length" class="empty-padding text-center">
              <p class="text-muted text-xs">無符合條件的日誌事件。</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Command Records Table -->
      <div class="card command-card">
        <div class="card-header">
          <div class="card-title">前端命令發送紀錄 (證明導航/切模式不觸發命令)</div>
          <span class="badge badge-accent">{{ commandLogs.length }} 筆命令</span>
        </div>
        <div class="card-body p-0">
          <div v-if="commandLogs.length" class="data-table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Request ID</th>
                  <th>命令類型</th>
                  <th>時間戳</th>
                  <th>狀態</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="cmd in commandLogs" :key="cmd.request_id">
                  <td class="mono text-2xs">{{ cmd.request_id }}</td>
                  <td class="mono text-accent">{{ cmd.command_type }}</td>
                  <td class="tabular-nums text-2xs">{{ cmd.timestamp }}</td>
                  <td>
                    <span
                      class="badge badge-sm"
                      :class="cmd.status === 'success' ? 'badge-success' : (cmd.status === 'failed' ? 'badge-danger' : 'badge-warning')"
                    >
                      {{ cmd.status }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty-padding">
            <p class="text-muted text-xs">目前無外部控制命令記錄（頁面切換與模式預覽不會向後端發送命令）。</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.logs-page {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
  overflow-y: auto;
}



.logs-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.stream-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stream-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--text-xs);
  padding: 6px;
  background: var(--bg-surface-elevated);
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-secondary);
}

.stream-time {
  font-size: 10px;
  color: var(--text-muted);
}

.stream-msg {
  color: var(--text-secondary);
  font-size: 11px;
}

.empty-padding {
  padding: var(--space-4);
}

.p-0 { padding: 0 !important; }
.text-accent { color: var(--accent); }
.text-muted { color: var(--text-muted); }

@media (max-width: 1024px) {
  .logs-grid {
    grid-template-columns: 1fr;
  }
}



.logs-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding: 6px 10px;
  background: var(--bg-surface);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
}

.category-tabs {
  display: flex;
  gap: 4px;
}

.tab-btn {
  padding: 3px 10px;
  font-size: var(--text-2xs);
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-muted);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: all 0.15s ease;
}

.tab-btn:hover {
  color: var(--text-primary);
  background: var(--bg-surface-elevated);
}

.tab-btn.active {
  color: var(--accent);
  background: var(--accent-subtle);
  border-color: var(--accent-border);
}

.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  background: var(--bg-base);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
  color: var(--text-muted);
}

.search-input {
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  outline: none;
  width: 200px;
}

.search-input::placeholder {
  color: var(--text-disabled);
}

.live-pulse {
  animation: pulse-dot 2s infinite ease-in-out;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
