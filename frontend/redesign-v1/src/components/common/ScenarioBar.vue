<script setup lang="ts">
import { ref } from 'vue';
import { useWorkspace } from '@/state/useWorkspace';
import { usePreferences } from '@/state/usePreferences';
import type { ScenarioType } from '@/adapters/types';

const { activeScenario, setScenario } = useWorkspace();
const {
  preferences,
  setLayout,
  setWorkspaceMode,
  setChartStyle,
  setBorderContrast,
  setCardDensity,
  setSidebarStyle,
  toggleSidebarFold,
  resetToDefaults
} = usePreferences();

const isExpanded = ref(false);
const isBarHidden = ref(false);

const scenarios: { key: ScenarioType; label: string; desc: string }[] = [
  { key: 'normal', label: '正常連線', desc: '1 運行中 · 淨值穩健 · 風控正常' },
  { key: 'soft_loss', label: '日損軟限', desc: '達到 -10% · 軟限鎖存 · 禁增倉' },
  { key: 'hold_stopped_409', label: '持倉停止 409', desc: '保留 -1 張 · 獨佔未釋放 · 禁新分配' },
  { key: 'empty', label: '空資料', desc: '零部署 · 歷史空白 · 完整空狀態' },
  { key: 'service_unavailable', label: '服務異常 503', desc: 'Supervisor 離線 · 告警提示' },
];
</script>

<template>
  <!-- Floating Restore Pill when Bar is Hidden -->
  <div v-if="isBarHidden" class="scenario-restore-pill" @click="isBarHidden = false" title="展開情境與微調控制列">
    <span class="pill-dot"></span>
    <span class="pill-text">情境: {{ scenarios.find(s => s.key === activeScenario)?.label }}</span>
    <span class="pill-action">展開 ▾</span>
  </div>

  <div v-else class="scenario-bar">
    <!-- Main Compact Row -->
    <div class="sc-main-row">
      <div class="sc-left">
        <span class="sc-title">情境：</span>
        <div class="sc-buttons">
          <button
            v-for="s in scenarios"
            :key="s.key"
            type="button"
            :class="['btn btn-sm', activeScenario === s.key ? 'btn-primary' : 'btn-secondary']"
            @click="setScenario(s.key)"
            :title="s.desc"
          >
            {{ s.label }}
          </button>
        </div>
      </div>

      <div class="sc-right">
        <!-- Toggle Row 2 Fine-Tuning Controls -->
        <button
          type="button"
          class="btn-toggle-customizer"
          :class="{ active: isExpanded }"
          @click="isExpanded = !isExpanded"
          title="切換即時微調控制項（圖表風格、對比度、密度等）"
        >
          <span>微調控制台</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :style="{ transform: isExpanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }">
            <polyline points="6 9 12 15 18 9"></polyline>
          </svg>
        </button>

        <!-- Hide Bar Button -->
        <button
          type="button"
          class="btn-hide-bar"
          @click="isBarHidden = true"
          title="隱藏此控制列（最大化看盤視野）"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>

    <!-- Collapsible Row 2: Live Visual Fine-Tuning -->
    <div v-if="isExpanded" class="sc-customizer-row">
      <div class="customizer-left">

        <!-- Chart Style Toggles -->
        <div class="customizer-item">
          <span class="item-label">圖表風格：</span>
          <div class="btn-toggle-group">
            <button
              type="button"
              :class="['toggle-btn', { active: preferences.chartStyle === 'refined' }]"
              @click="setChartStyle('refined')"
              title="精緻柔光：柔光漸層陰影、11px 俐落甜甜圈、金色邊框指針"
            >
              精緻柔光 (推薦)
            </button>
            <button
              type="button"
              :class="['toggle-btn', { active: preferences.chartStyle === 'minimal' }]"
              @click="setChartStyle('minimal')"
              title="極簡純線：移除漸層陰影，純線條刻度"
            >
              極簡純線
            </button>
            <button
              type="button"
              :class="['toggle-btn', { active: preferences.chartStyle === 'classic' }]"
              @click="setChartStyle('classic')"
              title="原版風格：14px 甜甜圈、標準白光指針"
            >
              原版風格
            </button>
          </div>
        </div>

        <!-- Border Contrast Toggles -->
        <div class="customizer-item">
          <span class="item-label">邊框深邃：</span>
          <div class="btn-toggle-group">
            <button
              type="button"
              :class="['toggle-btn', { active: preferences.borderContrast === 'high' }]"
              @click="setBorderContrast('high')"
              title="強化銳利：邊框 #283345，面板邊界更清晰分明"
            >
              強化銳利 (推薦)
            </button>
            <button
              type="button"
              :class="['toggle-btn', { active: preferences.borderContrast === 'standard' }]"
              @click="setBorderContrast('standard')"
              title="標準對比：邊框 #1f2633"
            >
              標準對比
            </button>
            <button
              type="button"
              :class="['toggle-btn', { active: preferences.borderContrast === 'deep_black' }]"
              @click="setBorderContrast('deep_black')"
              title="深邃純黑：卡片背景 #0b0f14，深色對比更強"
            >
              深邃純黑
            </button>
          </div>
        </div>

        <!-- Card Density Toggles -->
        <div class="customizer-item">
          <span class="item-label">資訊密度：</span>
          <div class="btn-toggle-group">
            <button
              type="button"
              :class="['toggle-btn', { active: preferences.cardDensity === 'standard' }]"
              @click="setCardDensity('standard')"
              title="標準密度：16px padding"
            >
              標準 (16px)
            </button>
            <button
              type="button"
              :class="['toggle-btn', { active: preferences.cardDensity === 'compact' }]"
              @click="setCardDensity('compact')"
              title="高密度緊湊：12px padding，減少留白"
            >
              緊湊 (12px)
            </button>
          </div>
        </div>


        <!-- Sidebar Fold Toggle -->
        <div class="customizer-item">
          <span class="item-label">側欄折疊：</span>
          <div class="btn-toggle-group">
            <button
              type="button"
              :class="['toggle-btn', { active: !preferences.sidebarFolded }]"
              @click="preferences.sidebarFolded && toggleSidebarFold()"
              title="展開側邊欄"
            >
              展開 (230px)
            </button>
            <button
              type="button"
              :class="['toggle-btn', { active: preferences.sidebarFolded }]"
              @click="!preferences.sidebarFolded && toggleSidebarFold()"
              title="收合側邊欄 (64px)"
            >
              折疊 (64px)
            </button>
          </div>
        </div>
      </div>

      <div class="customizer-right">
        <button
          type="button"
          class="btn-reset-preview"
          @click="resetToDefaults"
          title="恢復為推薦預設設定"
        >
          ⟲ 還原推薦設定
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scenario-bar {
  display: flex;
  flex-direction: column;
  background-color: var(--bg-sidebar);
  border-bottom: 1px solid var(--border-secondary);
  font-size: var(--text-xs);
}

.sc-main-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px var(--space-4);
  flex-wrap: wrap;
  gap: var(--space-2);
}

.sc-left, .sc-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.sc-title {
  color: var(--text-muted);
  font-weight: 500;
}

.sc-buttons {
  display: flex;
  gap: 4px;
}

.layout-switch-group {
  display: flex;
  background: var(--bg-base);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  padding: 2px;
}

.layout-btn {
  padding: 3px 8px;
  font-size: var(--text-xs);
  color: var(--text-muted);
  border-radius: var(--radius-xs);
  font-weight: 500;
  transition: all 0.15s ease;
}

.layout-btn.active {
  background: var(--accent);
  color: #080a0d;
  font-weight: 600;
}

/* Customizer row */
.sc-customizer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px var(--space-4);
  background-color: var(--bg-surface-elevated);
  border-top: 1px solid var(--border-secondary);
  gap: var(--space-3);
  flex-wrap: wrap;
}

.customizer-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.customizer-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: var(--radius-xs);
  background: var(--accent-subtle);
  color: var(--accent);
  border: 1px solid var(--accent-border);
  font-weight: 600;
}

.customizer-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.item-label {
  font-size: 11px;
  color: var(--text-muted);
}

.customizer-right {
  display: flex;
  align-items: center;
}

.btn-reset-preview {
  font-size: 10px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 2px 4px;
  transition: color 0.15s ease;
}

.btn-reset-preview:hover {
  color: var(--accent);
}

.btn-toggle-customizer {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  font-size: var(--text-xs);
  color: var(--text-muted);
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-toggle-customizer:hover,
.btn-toggle-customizer.active {
  color: var(--accent);
  border-color: var(--accent-border);
  background: var(--accent-subtle);
}

.btn-hide-bar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  color: var(--text-muted);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-hide-bar:hover {
  color: var(--color-danger);
  background: var(--color-danger-bg);
  border-color: var(--color-danger-border);
}

.scenario-restore-pill {
  position: absolute;
  top: var(--space-2);
  right: var(--space-4);
  z-index: 100;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  font-size: var(--text-xs);
  cursor: pointer;
  box-shadow: var(--shadow-md);
  transition: all 0.15s ease;
}

.scenario-restore-pill:hover {
  border-color: var(--accent);
  background: var(--bg-surface-hover);
}

.scenario-restore-pill .pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
  box-shadow: 0 0 6px var(--color-success);
}

.scenario-restore-pill .pill-text {
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.scenario-restore-pill .pill-action {
  color: var(--accent);
  font-weight: 600;
}
</style>
