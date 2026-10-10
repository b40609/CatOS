<script setup lang="ts">
import { useWorkspace } from '@/state/useWorkspace';

const { telemetry, showTelemetryPopover, toggleTelemetryPopover } = useWorkspace();
</script>

<template>
  <div class="telemetry-wrapper">
    <button
      type="button"
      class="telemetry-trigger btn btn-sm btn-secondary"
      @click="toggleTelemetryPopover"
      :title="'點擊查看底座核心遙測'"
    >
      <span class="status-indicator" :class="{ online: telemetry.connected }">●</span>
      <span>{{ telemetry.connected ? '連線正常 · ' + telemetry.latency_ms + 'ms' : '連線斷開' }}</span>
      <span class="chevron">▾</span>
    </button>

    <div v-if="showTelemetryPopover" class="telemetry-popover" role="dialog" aria-label="核心底座遙測">
      <div class="popover-header">
        <strong>底座遙測與交易邊界</strong>
        <button type="button" class="btn-close" @click="toggleTelemetryPopover">✕</button>
      </div>

      <div class="popover-body">
        <div class="telemetry-row">
          <span class="t-label">核心狀態</span>
          <span class="t-val tabular-nums" :class="telemetry.connected ? 'text-success' : 'text-danger'">
            {{ telemetry.connected ? 'CONNECTED (127.0.0.1)' : 'OFFLINE' }}
          </span>
        </div>
        <div class="telemetry-row">
          <span class="t-label">Supervisor PID</span>
          <span class="t-val mono">{{ telemetry.supervisor_pid || '--' }}</span>
        </div>
        <div class="telemetry-row">
          <span class="t-label">OKX 強制標籤</span>
          <span class="t-val mono text-accent">{{ telemetry.fixed_tag }}</span>
        </div>
        <div class="telemetry-row">
          <span class="t-label">保證金撮合</span>
          <span class="t-val mono">USDT-M SWAP / cross + net_mode</span>
        </div>
        <div class="telemetry-row">
          <span class="t-label">金融數值底座</span>
          <span class="t-val mono">Decimal / SQLite TEXT (嚴禁 float)</span>
        </div>
        <div class="telemetry-row">
          <span class="t-label">合約獨佔狀態</span>
          <span class="t-val">單合約單 Bot 獨佔 (不隨 Worker 死亡釋放)</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.telemetry-wrapper {
  position: relative;
}

.telemetry-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.status-indicator {
  color: var(--color-danger);
  font-size: 8px;
}

.status-indicator.online {
  color: var(--color-success);
}

.chevron {
  font-size: 10px;
  color: var(--text-muted);
}

.popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-secondary);
  padding-bottom: var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-primary);
}

.btn-close {
  color: var(--text-muted);
  font-size: var(--text-xs);
}

.btn-close:hover {
  color: var(--text-primary);
}

.popover-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  font-size: var(--text-xs);
}

.telemetry-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px solid var(--border-secondary);
}

.t-label {
  color: var(--text-muted);
}

.t-val {
  color: var(--text-primary);
  font-size: var(--text-xs);
}

.text-success { color: var(--color-success); }
.text-danger { color: var(--color-danger); }
.text-accent { color: var(--accent); }
</style>
