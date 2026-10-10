<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useWorkspace } from '@/state/useWorkspace';
import type { BotMode } from '@/contracts';

const props = withDefaults(
  defineProps<{
    variant?: 'segmented' | 'full-width' | 'dropdown';
  }>(),
  {
    variant: 'segmented'
  }
);

const { currentMode, setMode } = useWorkspace();
const isDropdownOpen = ref(false);
const dropdownRef = ref<HTMLElement | null>(null);

function toggleDropdown() {
  isDropdownOpen.value = !isDropdownOpen.value;
}

function selectMode(m: BotMode) {
  setMode(m);
  isDropdownOpen.value = false;
}

function handleClickOutside(e: MouseEvent) {
  if (dropdownRef.value && !dropdownRef.value.contains(e.target as Node)) {
    isDropdownOpen.value = false;
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>

<template>
  <!-- Option 3: Dropdown Badge Variant (Slack / Raycast / Figma Style) -->
  <div v-if="props.variant === 'dropdown'" ref="dropdownRef" class="mode-dropdown-wrapper">
    <button
      type="button"
      class="mode-badge-btn"
      :class="`badge-mode-${currentMode}`"
      @click="toggleDropdown"
      title="點擊展開切換交易環境"
    >
      <span class="mode-status-dot"></span>
      <span class="mode-text">{{ currentMode === 'local' ? '本機' : currentMode === 'demo' ? 'Demo' : 'Live' }}</span>
      <svg class="dropdown-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path d="M6 9l6 6 6-6"/>
      </svg>
    </button>

    <div v-if="isDropdownOpen" class="mode-dropdown-popover">
      <div class="dropdown-popover-title">切換交易環境 (Workspace Mode)</div>
      
      <button
        type="button"
        class="dropdown-popover-item"
        :class="{ active: currentMode === 'local' }"
        @click="selectMode('local')"
      >
        <span class="mode-item-dot dot-local"></span>
        <div class="mode-item-content">
          <span class="mode-item-title">本機環境 (Local Sim)</span>
          <span class="mode-item-desc">本機專用、安全可測試</span>
        </div>
        <span v-if="currentMode === 'local'" class="check-mark">✓</span>
      </button>

      <button
        type="button"
        class="dropdown-popover-item"
        :class="{ active: currentMode === 'demo' }"
        @click="selectMode('demo')"
      >
        <span class="mode-item-dot dot-demo"></span>
        <div class="mode-item-content">
          <span class="mode-item-title">Demo 模擬盤</span>
          <span class="mode-item-desc">唯讀隔離展示 · 禁止增倉</span>
        </div>
        <span v-if="currentMode === 'demo'" class="check-mark">✓</span>
      </button>

      <button
        type="button"
        class="dropdown-popover-item"
        :class="{ active: currentMode === 'live' }"
        @click="selectMode('live')"
      >
        <span class="mode-item-dot dot-live"></span>
        <div class="mode-item-content">
          <span class="mode-item-title">Live 實盤</span>
          <span class="mode-item-desc">嚴格鎖定 · 禁止真實金鑰</span>
        </div>
        <span v-if="currentMode === 'live'" class="check-mark">✓</span>
      </button>
    </div>
  </div>

  <!-- Standard & Full-Width Segmented Control Variants (Options 1, 2, 4) -->
  <div
    v-else
    :class="['mode-switcher', { 'full-width': props.variant === 'full-width' }]"
    role="group"
    aria-label="工作區環境模式選擇"
  >
    <button
      type="button"
      :class="['mode-btn', { active: currentMode === 'local' }]"
      @click="setMode('local')"
      title="本機模擬環境（可正常啟動與停止測試）"
    >
      本機
    </button>
    <button
      type="button"
      :class="['mode-btn', { active: currentMode === 'demo' }]"
      @click="setMode('demo')"
      title="Demo 模擬盤（唯讀隔離展示 · 禁止增倉與交易）"
    >
      Demo
    </button>
    <button
      type="button"
      :class="['mode-btn', { active: currentMode === 'live' }]"
      @click="setMode('live')"
      title="Live 實盤（嚴格鎖定 · 禁止連線真實金鑰）"
    >
      Live
    </button>
  </div>
</template>

<style scoped>
/* Segmented Control Base */
.mode-switcher {
  display: inline-flex;
  align-items: center;
  background: #080b0f;
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-sm);
  padding: 2px;
  gap: 2px;
}

.mode-switcher.full-width {
  display: flex;
  width: 100%;
  box-sizing: border-box;
}

.mode-switcher.full-width .mode-btn {
  flex: 1;
  text-align: center;
  padding: 4px 6px;
  font-size: 11px;
}

.mode-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  font-size: 10.5px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.mode-btn:hover {
  color: var(--text-primary);
  background: var(--bg-surface-hover);
}

.mode-btn.active {
  background: var(--accent);
  color: #080a0d;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
}

/* Dropdown Badge Styles (Option 3) */
.mode-dropdown-wrapper {
  position: relative;
  display: inline-flex;
}

.mode-badge-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  border: 1px solid transparent;
}

.badge-mode-local {
  background: rgba(220, 179, 71, 0.15);
  color: var(--accent);
  border-color: rgba(220, 179, 71, 0.35);
}

.badge-mode-demo {
  background: rgba(88, 166, 255, 0.15);
  color: #58a6ff;
  border-color: rgba(88, 166, 255, 0.35);
}

.badge-mode-live {
  background: rgba(248, 81, 73, 0.15);
  color: #f85149;
  border-color: rgba(248, 81, 73, 0.35);
}

.mode-badge-btn:hover {
  filter: brightness(1.15);
}

.mode-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.dropdown-chevron {
  transition: transform 0.15s ease;
}

.mode-dropdown-popover {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  min-width: 200px;
  background: #0d1219;
  border: 1px solid var(--border-highlight);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.65);
  padding: 6px;
  z-index: 200;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.dropdown-popover-title {
  font-size: 10px;
  font-family: var(--font-mono);
  color: #6c7d93;
  padding: 4px 8px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.dropdown-popover-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: all 0.12s ease;
  width: 100%;
}

.dropdown-popover-item:hover {
  background: #17202c;
}

.dropdown-popover-item.active {
  background: rgba(220, 179, 71, 0.12);
}

.mode-item-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-local { background: var(--accent); }
.dot-demo { background: #58a6ff; }
.dot-live { background: #f85149; }

.mode-item-content {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.mode-item-title {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-primary);
}

.mode-item-desc {
  font-size: 9.5px;
  color: var(--text-muted);
}

.check-mark {
  color: var(--accent);
  font-weight: 700;
  font-size: 12px;
}
</style>
