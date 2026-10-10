<script setup lang="ts">
import { computed } from 'vue';
import type { RiskState } from '@/contracts';
import { usePreferences } from '@/state/usePreferences';

const props = defineProps<{
  risk: RiskState | null;
}>();

const { preferences } = usePreferences();

const badgeText = computed(() => {
  if (!props.risk || props.risk.status === 'missing') return 'STATUS: UNAVAILABLE';
  if (props.risk.status === 'normal') return 'LATCH: DISARMED';
  if (props.risk.status === 'soft_latch') return 'SOFT LATCHED (-10%)';
  if (props.risk.status === 'hard_latch') return 'HARD LATCHED (-20%)';
  return 'STATUS: UNKNOWN';
});

const badgeClass = computed(() => {
  if (!props.risk || props.risk.status === 'missing') return 'badge-danger';
  if (props.risk.status === 'normal') return 'badge-success';
  if (props.risk.status === 'soft_latch') return 'badge-warning';
  if (props.risk.status === 'hard_latch') return 'badge-danger';
  return 'badge-neutral';
});

const needlePositionPct = computed(() => {
  if (!props.risk || props.risk.status === 'missing') return 5;
  if (props.risk.status === 'soft_latch') return 70;
  if (props.risk.status === 'hard_latch') return 92;
  return 18;
});
</script>

<template>
  <div class="risk-gauge-card card">
    <div class="card-header">
      <div class="card-title">
        <span>日損鎖存安全儀表</span>
      </div>
      <div class="card-actions">
        <span class="badge" :class="badgeClass">
          {{ badgeText }}
        </span>
      </div>
    </div>

    <div class="gauge-body">
      <!-- 4-segment Gauge Track -->
      <div class="gauge-track-container">
        <div class="gauge-track">
          <div class="track-seg seg-safe" title="安全運作區間"></div>
          <div class="track-seg seg-caution" title="輕度回撤區間"></div>
          <div class="track-seg seg-soft" title="Soft -10% 軟限（禁止增倉）"></div>
          <div class="track-seg seg-hard" title="Hard -20% 硬熔斷（清倉鎖存）"></div>
        </div>
        <div
          :class="['gauge-needle', `needle-${preferences.chartStyle}`]"
          :style="{ left: needlePositionPct + '%' }"
          :title="'當前指針位置: ' + (risk?.status === 'missing' ? '離線不可用' : (risk?.daily_pnl_pct || '0.0%'))"
        >
          <div class="needle-point"></div>
          <div class="needle-glow"></div>
        </div>
      </div>

      <div class="gauge-labels-row">
        <span>基準 0.0%</span>
        <span>預警 -5.0%</span>
        <span class="text-warning">SOFT -10%</span>
        <span class="text-danger">HARD -20%</span>
      </div>

      <!-- 2x2 Metric Grid -->
      <div class="gauge-metrics-grid">
        <div class="g-metric">
          <div class="gm-label">日初基準權益</div>
          <div class="gm-val tabular-nums">
            {{ (risk && risk.status !== 'missing') ? `${risk.day_start_equity_usdt} USDT` : '— USDT' }}
          </div>
        </div>
        <div class="g-metric">
          <div class="gm-label">當日損益浮動</div>
          <div
            class="gm-val tabular-nums"
            :class="(risk && risk.status !== 'missing' && risk.daily_pnl_usdt?.startsWith('+')) ? 'text-success' : 'text-danger'"
          >
            {{ (risk && risk.status !== 'missing') ? `${risk.daily_pnl_usdt} (${risk.daily_pnl_pct})` : '— (未知)' }}
          </div>
        </div>
        <div class="g-metric">
          <div class="gm-label">Soft 止損閥值</div>
          <div class="gm-val tabular-nums text-warning">{{ risk?.soft_loss_limit_pct || '-10.0%' }} (禁增倉)</div>
        </div>
        <div class="g-metric">
          <div class="gm-label">Hard 熔斷閥值</div>
          <div class="gm-val tabular-nums text-danger">{{ risk?.hard_loss_limit_pct || '-20.0%' }} (強制平倉)</div>
        </div>
      </div>

    </div>
  </div>
</template>


<style scoped>
.risk-gauge-card {
  height: 100%;
  min-height: 220px;
}

.gauge-body {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  justify-content: space-between;
  flex: 1;
}

.gauge-track-container {
  position: relative;
  width: 100%;
  padding: 6px 0;
}

.gauge-track {
  display: flex;
  height: 8px;
  width: 100%;
  border-radius: var(--radius-xs);
  overflow: hidden;
  background: var(--bg-base);
  border: 1px solid var(--border-secondary);
}

.track-seg {
  height: 100%;
}

.seg-safe { width: 45%; background: var(--color-success); opacity: 0.85; }
.seg-caution { width: 20%; background: #947600; }
.seg-soft { width: 15%; background: var(--color-warning); }
.seg-hard { width: 20%; background: var(--color-danger); }

.gauge-needle {
  position: absolute;
  top: 0;
  width: 2px;
  height: 20px;
  background: #ffffff;
  transform: translateX(-50%);
  transition: left 0.4s ease;
  z-index: 5;
}

.needle-point {
  width: 8px;
  height: 8px;
  background: #ffffff;
  border-radius: 50%;
  position: absolute;
  top: -4px;
  left: -3px;
  box-shadow: 0 0 6px rgba(255, 255, 255, 0.8);
}

/* Refined golden needle with high-contrast ring */
.needle-refined {
  background: var(--accent);
}

.needle-refined .needle-point {
  width: 10px;
  height: 10px;
  background: #ffffff;
  border: 2px solid var(--accent);
  top: -5px;
  left: -4px;
  box-shadow: 0 0 8px rgba(220, 179, 71, 0.9), 0 0 4px rgba(255, 255, 255, 0.8);
}

/* Minimal flat needle */
.needle-minimal .needle-point {
  width: 6px;
  height: 6px;
  top: -3px;
  left: -2px;
  box-shadow: none;
}

.gauge-labels-row {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  margin-top: -4px;
}

.gauge-metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
  background: var(--bg-surface-elevated);
  padding: 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-secondary);
}

.g-metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.gm-label {
  font-size: var(--text-2xs);
  color: var(--text-muted);
}

.gm-val {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-primary);
}

.text-warning { color: var(--color-warning); }
.text-danger { color: var(--color-danger); }
.text-success { color: var(--color-success); }
</style>
