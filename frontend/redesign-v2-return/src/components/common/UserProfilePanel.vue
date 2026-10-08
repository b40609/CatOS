<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { usePreferences } from '@/state/usePreferences';
import { useWorkspace } from '@/state/useWorkspace';

const props = defineProps<{
  position?: 'bottom_left' | 'top_right';
  isFolded?: boolean;
}>();

const router = useRouter();
const { preferences } = usePreferences();
const { telemetry } = useWorkspace();

const isOpen = ref(false);
const panelRef = ref<HTMLElement | null>(null);
const copiedTag = ref(false);


function togglePanel(e?: Event) {
  if (e) e.stopPropagation();
  const willOpen = !isOpen.value;
  isOpen.value = willOpen;
  if (willOpen) {
    window.dispatchEvent(new CustomEvent('close-all-header-popovers', { detail: 'user-profile' }));
  }
}

function closePanel() {
  isOpen.value = false;
}

function navigateToSettings() {
  closePanel();
  router.push('/settings');
}

async function copyFixedTag() {
  try {
    await navigator.clipboard.writeText(telemetry.fixed_tag || '41cb53c54d6dABDE');
    copiedTag.value = true;
    setTimeout(() => {
      copiedTag.value = false;
    }, 2000);
  } catch (err) {
    copiedTag.value = true;
    setTimeout(() => {
      copiedTag.value = false;
    }, 2000);
  }
}





function handleClickOutside(event: MouseEvent) {
  if (panelRef.value && !panelRef.value.contains(event.target as Node)) {
    closePanel();
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && isOpen.value) {
    closePanel();
  }
}

function handleExternalClose(event: Event) {
  const custom = event as CustomEvent;
  if (custom.detail !== 'user-profile') {
    closePanel();
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside);
  document.addEventListener('keydown', handleKeydown);
  window.addEventListener('close-all-header-popovers', handleExternalClose);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
  document.removeEventListener('keydown', handleKeydown);
  window.removeEventListener('close-all-header-popovers', handleExternalClose);
});
</script>

<template>
  <div
    ref="panelRef"
    class="user-profile-widget"
    :class="[
      `pos-${position}`,
      { 'is-open': isOpen, 'is-folded-mode': isFolded }
    ]"
  >
    <!-- Trigger Button Variant 1: Bottom-Left Sidebar Footer (Expanded) -->
    <button
      v-if="position === 'bottom_left' && !isFolded"
      type="button"
      class="profile-trigger-sidebar"
      @click="togglePanel"
      :aria-expanded="isOpen"
      aria-haspopup="dialog"
      title="開啟使用者個人面板與系統設定"
    >
      <div class="avatar-wrap">
        <div class="user-avatar">
          <span>K</span>
          <span class="avatar-online-dot"></span>
        </div>
      </div>
      <div class="user-info-col">
        <div class="user-name-row">
          <span class="user-name">KOL 交易員</span>
          <span class="user-badge-pro">PRO</span>
        </div>
        <span class="user-subtext">OKX 專用子帳戶</span>
      </div>
      <div class="trigger-icon-col">
        <svg class="gear-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </div>
    </button>

    <!-- Trigger Button Variant 2: Bottom-Left Sidebar Footer (Folded 64px) -->
    <button
      v-else-if="position === 'bottom_left' && isFolded"
      type="button"
      class="profile-trigger-folded"
      @click="togglePanel"
      :aria-expanded="isOpen"
      aria-haspopup="dialog"
      title="KOL 交易員 (點擊展開個人面板與系統設定)"
    >
      <div class="user-avatar-folded">
        <span>K</span>
        <span class="avatar-online-dot"></span>
      </div>
    </button>

    <!-- Trigger Button Variant 3: Top-Right Header Capsule -->
    <button
      v-else-if="position === 'top_right'"
      type="button"
      class="profile-trigger-header"
      @click="togglePanel"
      :aria-expanded="isOpen"
      aria-haspopup="dialog"
      title="個人面板與系統設定"
    >
      <div class="header-avatar-wrap">
        <div class="user-avatar-sm">
          <span>K</span>
          <span class="avatar-online-dot-sm"></span>
        </div>
      </div>
      <div class="header-user-text">
        <span class="header-user-name">KOL 交易員</span>
        <span class="header-sub-tag">OKX</span>
      </div>
      <svg class="header-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </button>

    <!-- Unified Floating Popover Drawer -->
    <transition name="popover-fade">
      <div
        v-if="isOpen"
        class="profile-popover"
        :class="[`popover-${position}`, { 'popover-folded': isFolded }]"
        role="dialog"
        aria-label="使用者個人面板"
      >
        <!-- Card 1: User Identity & VIP Status -->
        <div class="popover-header-card">
          <div class="popover-header-left">
            <div class="popover-big-avatar">
              <span>K</span>
            </div>
            <div class="popover-user-meta">
              <div class="popover-name-line">
                <span class="name-text">KOL 交易員</span>
                <span class="account-code">#kol_trader_01</span>
              </div>
              <span class="account-type-text">OKX 專用子帳戶 · 實名 API 授權</span>
            </div>
          </div>
          <button type="button" class="popover-close-btn" @click="closePanel" title="關閉">
            ✕
          </button>
        </div>

        <!-- Connection & Live Status Indicators -->
        <div class="popover-status-grid">
          <div class="status-item">
            <span class="status-k">節點狀態</span>
            <span class="status-v text-success font-mono">127.0.0.1:8770 連線中</span>
          </div>
          <div class="status-item">
            <span class="status-k">遙測延遲</span>
            <span class="status-v text-accent font-mono">{{ telemetry.connected ? telemetry.latency_ms + 'ms' : '離線' }}</span>
          </div>
        </div>

        <!-- Card 2: Primary Entry — 系統設定 (System Settings) -->
        <router-link to="/settings" class="popover-settings-entry" @click="closePanel">
          <div class="entry-left">
            <div class="entry-icon-box">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </div>
            <div class="entry-text-col">
              <span class="entry-title">前往「系統設定」</span>
              <span class="entry-subtitle">外觀風格、Tabler參數、切換鈕與日損偏好</span>
            </div>
          </div>
          <span class="entry-arrow">→</span>
        </router-link>

        <!-- Card 3: Financial & Audit Invariants -->
        <div class="popover-invariants-box">
          <div class="invariants-header">
            <span class="invariants-title">金融不變量審查 (Financial Invariants)</span>
          </div>

          <div class="invariant-row">
            <div class="inv-label-group">
              <span class="inv-label">OKX 強制標籤</span>
              <span class="inv-sub">Supervisor 自動注入</span>
            </div>
            <button
              type="button"
              class="inv-tag-btn font-mono"
              @click="copyFixedTag"
              :title="'點擊複製固定標籤'"
            >
              <span>{{ telemetry.fixed_tag || '41cb53c54d6dABDE' }}</span>
              <span class="copy-tag-feedback">{{ copiedTag ? '✓ 已複製' : '📋' }}</span>
            </button>
          </div>

          <div class="invariant-row">
            <div class="inv-label-group">
              <span class="inv-label">撮合與保證金</span>
              <span class="inv-sub">僅限 USDT-M 合約</span>
            </div>
            <span class="inv-value font-mono">cross + net_mode</span>
          </div>

          <div class="invariant-row">
            <div class="inv-label-group">
              <span class="inv-label">災難停損守護</span>
              <span class="inv-sub">P6 交易所端整倉停損</span>
            </div>
            <span class="inv-value font-mono text-accent">Mark 觸發</span>
          </div>
        </div>




      </div>
    </transition>
  </div>
</template>

<style scoped>
.user-profile-widget {
  position: relative;
  user-select: none;
}

/* 1. Bottom-Left Expanded Trigger */
.profile-trigger-sidebar {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}

.profile-trigger-sidebar:hover {
  background: var(--bg-surface-hover);
  border-color: var(--accent-border);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
}

.avatar-wrap {
  position: relative;
  flex-shrink: 0;
}

.user-avatar {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, #1e2634 0%, #151b24 100%);
  border: 1px solid var(--accent-border);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 14px;
  position: relative;
  box-shadow: inset 0 0 8px rgba(245, 158, 11, 0.15);
}

.avatar-online-dot {
  position: absolute;
  bottom: -2px;
  right: -2px;
  width: 8px;
  height: 8px;
  background-color: var(--color-success);
  border: 1.5px solid var(--bg-surface-elevated);
  border-radius: 50%;
}

.user-info-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.user-name {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-badge-pro {
  font-size: 9px;
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 1px 4px;
  background: var(--accent-subtle);
  border: 1px solid var(--accent-border);
  color: var(--accent);
  border-radius: 3px;
  letter-spacing: 0.5px;
}

.user-subtext {
  font-size: 10px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.trigger-icon-col {
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  padding-left: 2px;
}

.profile-trigger-sidebar:hover .gear-icon {
  color: var(--accent);
  transform: rotate(30deg);
  transition: transform 0.25s ease;
}

/* 2. Bottom-Left Folded Trigger (64px Dock) */
.profile-trigger-folded {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin: 0 auto;
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
}

.profile-trigger-folded:hover {
  border-color: var(--accent-border);
  background: var(--bg-surface-hover);
}

.user-avatar-folded {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, #1e2634 0%, #151b24 100%);
  border: 1px solid var(--accent-border);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 13px;
  position: relative;
}

/* 3. Top-Right Header Trigger */
.profile-trigger-header {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 30px;
  padding: 0 10px 0 6px;
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.profile-trigger-header:hover {
  background: var(--bg-surface-hover);
  border-color: var(--accent-border);
}

.header-avatar-wrap {
  display: flex;
  align-items: center;
}

.user-avatar-sm {
  width: 20px;
  height: 20px;
  border-radius: 3px;
  background: linear-gradient(135deg, #1e2634 0%, #151b24 100%);
  border: 1px solid var(--accent-border);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 10px;
  position: relative;
}

.avatar-online-dot-sm {
  position: absolute;
  bottom: -2px;
  right: -2px;
  width: 6px;
  height: 6px;
  background-color: var(--color-success);
  border: 1px solid var(--bg-surface-elevated);
  border-radius: 50%;
}

.header-user-text {
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-user-name {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-primary);
}

.header-sub-tag {
  font-size: 9px;
  font-family: var(--font-mono);
  padding: 1px 4px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  border-radius: 2px;
  color: var(--text-secondary);
}

.header-chevron {
  color: var(--text-muted);
}

/* 4. Unified Popover Card */
.profile-popover {
  position: absolute;
  width: 320px;
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-highlight);
  border-radius: var(--radius-md);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.05);
  padding: 14px;
  z-index: 1050;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Placement adjustments */
.popover-bottom_left {
  bottom: calc(100% + 8px);
  left: 0;
  right: 0;
  width: auto;
  min-width: 290px;
}

.popover-bottom_left.popover-folded {
  bottom: 0;
  left: calc(100% + 12px);
  width: 320px;
}

.popover-top_right {
  top: calc(100% + 8px);
  right: 0;
}

/* Popover Content Styling */
.popover-header-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.popover-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.popover-big-avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, #242c3b 0%, #151a23 100%);
  border: 1.5px solid var(--accent-border);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 16px;
}

.popover-user-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.popover-name-line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.name-text {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
}

.account-code {
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--text-muted);
}

.account-type-text {
  font-size: 11px;
  color: var(--text-secondary);
}

.popover-close-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
  border-radius: 3px;
  line-height: 1;
}

.popover-close-btn:hover {
  background: var(--bg-surface-hover);
  color: var(--text-primary);
}

/* Status Grid */
.popover-status-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 8px 10px;
  background: var(--bg-base);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.status-k {
  font-size: 10px;
  color: var(--text-muted);
}

.status-v {
  font-size: 11px;
  font-weight: 500;
}

/* Primary Action: Go to Settings */
.popover-settings-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(245, 158, 11, 0.02) 100%);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
  text-decoration: none;
}

.popover-settings-entry:hover {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.16) 0%, rgba(245, 158, 11, 0.06) 100%);
  border-color: var(--accent);
  transform: translateY(-1px);
}

.entry-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.entry-icon-box {
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
}

.entry-text-col {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.entry-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--text-primary);
}

.entry-subtitle {
  font-size: 10px;
  color: var(--text-muted);
}

.entry-arrow {
  color: var(--accent);
  font-weight: bold;
  font-size: 14px;
}

/* Invariants Audit Box */
.popover-invariants-box {
  background: var(--bg-surface);
  border: 1px solid var(--border-secondary);
  border-radius: var(--radius-xs);
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.invariants-header {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.invariant-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.inv-label-group {
  display: flex;
  flex-direction: column;
}

.inv-label {
  font-size: 11px;
  color: var(--text-secondary);
}

.inv-sub {
  font-size: 9px;
  color: var(--text-muted);
}

.inv-tag-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 3px;
  padding: 2px 6px;
  color: var(--accent);
  font-size: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.inv-tag-btn:hover {
  border-color: var(--accent-border);
  background: var(--bg-surface-hover);
}

.copy-tag-feedback {
  font-size: 9px;
  color: var(--color-success);
}

.inv-value {
  font-size: 10px;
  color: var(--text-secondary);
}





/* Transition */
.popover-fade-enter-active,
.popover-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.popover-fade-enter-from,
.popover-fade-leave-to {
  opacity: 0;
  transform: scale(0.97);
}
</style>
