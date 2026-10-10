<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useDashboard } from '@/state/useDashboard';

const router = useRouter();
const { riskState } = useDashboard();

const effectiveLeverage = computed(() => {
  return riskState.value?.effective_leverage ? `${riskState.value.effective_leverage}×` : '2.81×';
});

const isHealthy = computed(() => {
  return !riskState.value || riskState.value.status === 'normal';
});

function goToRisk() {
  router.push('/risk');
}
</script>

<template>
  <div class="relaxed-risk-banner">
    <div class="banner-left">
      <div class="status-indicator">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="shield-icon">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          <path d="m9 12 2 2 4-4"/>
        </svg>
        <span class="status-text">{{ isHealthy ? 'Risk within limits' : 'Risk Elevated' }}</span>
      </div>

      <div class="metrics-strip">
        <span class="metric-item">
          Effective leverage <strong class="num">{{ effectiveLeverage }}</strong>
        </span>
        <span class="metric-item">
          Daily loss <strong class="num">0.00%</strong>
        </span>
        <span class="metric-item">
          Soft stop <strong class="num text-warn">2.0%</strong>
          <span class="divider">/</span>
          Hard stop <strong class="num text-down">4.0%</strong>
        </span>
        <span class="metric-item kill-switch-item">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" class="power-icon">
            <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>
            <line x1="12" y1="2" x2="12" y2="12"/>
          </svg>
          Kill-switch <strong class="text-up">ARMED</strong>
        </span>
      </div>
    </div>

    <button type="button" class="risk-center-btn" @click="goToRisk">
      <span>Risk center</span>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="9 18 15 12 9 6"/>
      </svg>
    </button>
  </div>
</template>

<style scoped>
.relaxed-risk-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--os-up-bg);
  border: 1px solid var(--os-up-border);
  border-radius: var(--os-card-radius, 6px);
  padding: 0.75rem 1rem;
  font-size: 0.72rem;
  margin-bottom: 1rem;
}

.banner-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 1.5rem;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-weight: 500;
  color: var(--os-up);
}

.shield-icon {
  color: var(--os-up);
}

.metrics-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 1.25rem;
  color: var(--os-text-muted);
  font-size: 0.72rem;
}

.metric-item strong {
  margin-left: 0.35rem;
  font-weight: 500;
  color: var(--os-text-primary);
}

.divider {
  margin: 0 0.35rem;
  color: var(--os-border-subtle);
}

.kill-switch-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.power-icon {
  color: var(--os-up);
}

.risk-center-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  background: transparent;
  border: none;
  color: var(--os-text-secondary);
  font-size: 0.72rem;
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  transition: all 0.15s ease;
}

.risk-center-btn:hover {
  color: var(--os-text-primary);
  background: rgba(255, 255, 255, 0.05);
}

.text-up {
  color: var(--os-up);
}

.text-down {
  color: var(--os-down);
}

.text-warn {
  color: var(--os-warn);
}
</style>
