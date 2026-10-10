<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { useRoute } from 'vue-router';
import ModeSelector from '@/components/common/ModeSelector.vue';
import TelemetryPopover from '@/components/common/TelemetryPopover.vue';
import UserProfilePanel from '@/components/common/UserProfilePanel.vue';
import { usePreferences } from '@/state/usePreferences';
import { useWorkspace } from '@/state/useWorkspace';

const route = useRoute();
const { preferences, setSidebarStyle, setSidebarWidth, resetSidebarWidth, toggleSidebarFold } = usePreferences();
const { telemetry, currentMode, modeNotice } = useWorkspace();

// Resizable Sidebar Splitter State (VS Code / Bloomberg / TradingView Pro)
const isResizingSidebar = ref(false);
const startX = ref(0);
const startWidth = ref(245);

const MIN_SIDEBAR_WIDTH = 190;
const MAX_SIDEBAR_WIDTH = 420;
const DEFAULT_SIDEBAR_WIDTH = 245;
const COLLAPSE_THRESHOLD = 135;
let lastDownTime = 0;

function handleResizerPointerDown(e: PointerEvent) {
  const now = performance.now();
  if (now - lastDownTime < 350) {
    handleResizerDblClick();
    lastDownTime = 0;
    return;
  }
  lastDownTime = now;

  e.preventDefault();
  isResizingSidebar.value = true;
  startX.value = e.clientX;
  startWidth.value = preferences.value.sidebarFolded
    ? 64
    : (preferences.value.sidebarWidth || DEFAULT_SIDEBAR_WIDTH);

  const onPointerMove = (moveEvent: PointerEvent) => {
    if (!isResizingSidebar.value) return;
    const deltaX = moveEvent.clientX - startX.value;
    const rawTarget = startWidth.value + deltaX;

    // Expand if dragged from folded state
    if (preferences.value.sidebarFolded) {
      if (rawTarget > 145) {
        preferences.value.sidebarFolded = false;
        setSidebarWidth(Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, rawTarget)));
      }
      return;
    }

    // Collapse if dragged below collapse threshold
    if (rawTarget < COLLAPSE_THRESHOLD) {
      preferences.value.sidebarFolded = true;
      return;
    }

    preferences.value.sidebarFolded = false;
    const clamped = Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, rawTarget));
    setSidebarWidth(clamped);
  };

  const onPointerUp = () => {
    isResizingSidebar.value = false;
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
  };

  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('pointercancel', onPointerUp);
}

function handleResizerDblClick() {
  if (preferences.value.sidebarFolded) {
    preferences.value.sidebarFolded = false;
    resetSidebarWidth();
  } else {
    resetSidebarWidth();
  }
}

interface NavItem {
  path: string;
  name: string;
  sub: string;
  icon: string;
  badge?: { id: 'bots' | 'risk' | 'market'; text: string; type: 'accent' | 'neutral' | 'info' | 'warning' };
  shortcut: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    title: 'OVERVIEW',
    items: [
      { path: '/', name: '系統總覽', sub: 'Dashboard', icon: 'dashboard', shortcut: '1' }
    ]
  },
  {
    title: 'STRATEGY & RESEARCH',
    items: [
      { path: '/strategies', name: '策略中心', sub: 'Strategies', icon: 'strategy', shortcut: '2' },
      { path: '/backtest', name: '歷史回測', sub: 'Backtesting', icon: 'backtest', shortcut: '3' },
      { path: '/optimization', name: '參數優化', sub: 'Optimization', icon: 'optimization', shortcut: '4' }
    ]
  },
  {
    title: 'EXECUTION & RISK',
    items: [
      { path: '/bots', name: '機器人管理', sub: 'Bot Manager', icon: 'bots', badge: { id: 'bots', text: '1/3', type: 'accent' }, shortcut: '5' },
      { path: '/risk', name: '風控中心', sub: 'Risk Control', icon: 'risk', badge: { id: 'risk', text: 'SAFE', type: 'neutral' }, shortcut: '6' }
    ]
  },
  {
    title: 'ECOSYSTEM & SYSTEM',
    items: [
      { path: '/market-intel', name: '市場情報', sub: 'Market Intel', icon: 'market', badge: { id: 'market', text: 'DEV', type: 'info' }, shortcut: '7' },
      { path: '/logs', name: '系統日誌', sub: 'System Logs', icon: 'logs', shortcut: '8' }
    ]
  }
];

function isBadgeVisible(badgeId?: 'bots' | 'risk' | 'market'): boolean {
  if (!preferences.value.showSidebarBadges) return false;
  if (badgeId === 'bots') return preferences.value.badgeBotsEnabled;
  if (badgeId === 'risk') return preferences.value.badgeRiskEnabled;
  if (badgeId === 'market') return preferences.value.badgeMarketEnabled;
  return true;
}

const pageTitle = computed(() => {
  return (route.meta?.title as string) || '系統總覽';
});

function handleKeydown(e: KeyboardEvent) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
    const target = e.target as HTMLElement | null;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
      return;
    }
    e.preventDefault();
    toggleSidebarFold();
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <div
    class="app-shell"
    :class="[
      `chart-style-${preferences.chartStyle}`,
      `border-contrast-${preferences.borderContrast}`,
      `density-${preferences.cardDensity}`,
      `radius-${preferences.cornerRadius.replace('.', '_')}`,
      `nav-${preferences.navStyle}`,
      `nav-placement-${preferences.navPlacement}`,
      `offcanvas-${preferences.offcanvasStyle}`,
      `container-${preferences.containerWidth}`,
      `sidebar-behavior-${preferences.sidebarBehavior}`,
      `sidebar-${preferences.sidebarStyle.toLowerCase()}`,
      {
        'sidebar-is-folded': preferences.sidebarFolded || preferences.sidebarBehavior === 'folded',
        'is-resizing-sidebar': isResizingSidebar
      }
    ]"
    :style="{
      '--sidebar-width': (preferences.sidebarFolded || preferences.sidebarBehavior === 'folded')
        ? '64px'
        : `${preferences.sidebarWidth || 245}px`
    }"
  >
    <!-- Left Attached Sidebar (Default: Tabler Attached + Expanded + 0.5 Radius) -->
    <aside
      class="app-sidebar"
      :class="[
        `sidebar-style-${preferences.sidebarStyle}`,
        `nav-style-${preferences.navStyle}`,
        `behavior-${preferences.sidebarBehavior}`,
        {
          'is-folded': preferences.sidebarFolded || preferences.sidebarBehavior === 'folded',
          'is-resizing': isResizingSidebar
        }
      ]"
    >
      <!-- Resizable Sidebar Splitter Sash (VS Code / Bloomberg / TradingView Pro) -->
      <div
        class="sidebar-resizer"
        :class="{ 'is-resizing': isResizingSidebar, 'is-folded': preferences.sidebarFolded }"
        @pointerdown="handleResizerPointerDown"
        @dblclick="handleResizerDblClick"
        :title="preferences.sidebarFolded ? '雙擊或向右拖移展開側邊欄' : '拖移調整寬度 · 雙擊重設 (245px)'"
        role="separator"
        aria-orientation="vertical"
      >
        <div class="resizer-line"></div>
        <div class="resizer-handle">
          <span class="resizer-grip-dot"></span>
          <span class="resizer-grip-dot"></span>
          <span class="resizer-grip-dot"></span>
        </div>
      </div>

      <!-- 1. Sidebar Brand Header -->
      <div class="sidebar-header">
        <div class="brand-top-row">
          <div class="brand-left-group">
            <div class="brand-badge">C</div>
            <div v-if="!preferences.sidebarFolded" class="brand-text-col">
              <div class="brand-row">
                <span class="brand-name">catOS</span>
                <span class="brand-ver">v1.2</span>
              </div>
              <span class="brand-tagline">QUANTITATIVE DESK</span>
            </div>
          </div>
          <!-- Option 3: Dropdown Badge right beside LOGO -->
          <div v-if="preferences.modeSwitcherPlacement === 'dropdown_badge' && !preferences.sidebarFolded" class="brand-dropdown-wrap">
            <ModeSelector variant="dropdown" />
          </div>
        </div>

        <!-- Option 1: Full-Width Stacked Segmented Control directly beneath LOGO -->
        <div v-if="preferences.modeSwitcherPlacement === 'sidebar_stack' && !preferences.sidebarFolded" class="sidebar-mode-dock">
          <ModeSelector variant="full-width" />
        </div>
      </div>



      <!-- 3. Navigation Sections -->
      <nav class="sidebar-nav">
        <template v-for="(section, sIdx) in navSections" :key="sIdx">
          <!-- Section Title (Clean Text, No Lines, Pure Tabler Style) -->
          <div
            v-if="!preferences.sidebarFolded && preferences.sidebarStyle !== 'C'"
            class="nav-section-title"
          >
            {{ section.title }}
          </div>

          <router-link
            v-for="item in section.items"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: route.path === item.path }"
            :title="preferences.sidebarFolded || preferences.sidebarStyle === 'C' ? `${item.name} (${item.sub})` : undefined"
          >
            <!-- SVG Icon -->
            <span class="nav-icon">
              <!-- 1. Dashboard: 2x2 Grid Squares -->
              <svg v-if="item.icon === 'dashboard'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="7" height="7" rx="1"/>
                <rect x="14" y="3" width="7" height="7" rx="1"/>
                <rect x="14" y="14" width="7" height="7" rx="1"/>
                <rect x="3" y="14" width="7" height="7" rx="1"/>
              </svg>
              <!-- 2. Strategies: Pulse Wave -->
              <svg v-else-if="item.icon === 'strategy'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 12h4l3-8 4 16 3-8h4"/>
              </svg>
              <!-- 3. Backtesting: Clock & Rewind -->
              <svg v-else-if="item.icon === 'backtest'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9"/>
                <polyline points="12 7 12 12 9 14"/>
                <path d="M3 12a9 9 0 0 1 .8-3.7"/>
              </svg>
              <!-- 4. Optimization: Sliders -->
              <svg v-else-if="item.icon === 'optimization'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <line x1="4" y1="21" x2="4" y2="14"/>
                <line x1="4" y1="10" x2="4" y2="3"/>
                <line x1="12" y1="21" x2="12" y2="12"/>
                <line x1="12" y1="8" x2="12" y2="3"/>
                <line x1="20" y1="21" x2="20" y2="16"/>
                <line x1="20" y1="12" x2="20" y2="3"/>
                <line x1="1" y1="14" x2="7" y2="14"/>
                <line x1="9" y1="8" x2="15" y2="8"/>
                <line x1="17" y1="16" x2="23" y2="16"/>
              </svg>
              <!-- 5. Bot Manager: Microchip -->
              <svg v-else-if="item.icon === 'bots'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <rect x="6" y="6" width="12" height="12" rx="1"/>
                <path d="M12 9v6"/>
                <path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>
              </svg>
              <!-- 6. Risk Control: Shield -->
              <svg v-else-if="item.icon === 'risk'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
              <!-- 7. Market Intel: Globe Wireframe -->
              <svg v-else-if="item.icon === 'market'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="2" y1="12" x2="22" y2="12"/>
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              </svg>
              <!-- 8. System Logs: 3 Horizontal Lines -->
              <svg v-else-if="item.icon === 'logs'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <line x1="4" y1="7" x2="20" y2="7"/>
                <line x1="4" y1="12" x2="20" y2="12"/>
                <line x1="4" y1="17" x2="20" y2="17"/>
              </svg>
              <!-- 9. Settings: Gear -->
              <svg v-else-if="item.icon === 'settings'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </span>

            <!-- Text Column: Depending on Mode and Folded -->
            <div v-if="!preferences.sidebarFolded && preferences.sidebarStyle !== 'C'" class="nav-text-col">
              <!-- Mode A & D: Dual Line (Chinese + English Mono) -->
              <template v-if="preferences.sidebarStyle === 'A' || preferences.sidebarStyle === 'D'">
                <span class="nav-title">{{ item.name }}</span>
                <span class="nav-subtitle">{{ item.sub }}</span>
              </template>
              <!-- Mode B: Tabler Single Line (Clean Chinese Title) -->
              <template v-else-if="preferences.sidebarStyle === 'B'">
                <span class="nav-title-tabler">{{ item.name }}</span>
              </template>
            </div>

            <!-- Right Status Badge (Controlled by Settings & Visibility) -->
            <div
              v-if="item.badge && isBadgeVisible(item.badge.id) && !preferences.sidebarFolded && preferences.sidebarStyle !== 'C'"
              class="nav-badge-wrap"
            >
              <span class="nav-status-badge" :class="`badge-${item.badge.type}`">
                {{ item.badge.text }}
              </span>
            </div>

            <!-- Pro Dock Mode (Style C) Floating Tooltip -->
            <div v-if="preferences.sidebarStyle === 'C' || preferences.sidebarFolded" class="dock-tooltip">
              <span class="dock-tip-title">{{ item.name }}</span>
              <span class="dock-tip-sub">{{ item.sub }}</span>
              <span class="dock-tip-key">[{{ item.shortcut }}]</span>
            </div>
          </router-link>
        </template>
      </nav>

      <!-- 4. Sidebar Footer & Telemetry & Toggle -->
      <div class="sidebar-footer">
        <!-- Option 4: Sidebar Footer Terminal Dock -->
        <div v-if="preferences.modeSwitcherPlacement === 'sidebar_footer' && !preferences.sidebarFolded && preferences.sidebarStyle !== 'C'" class="footer-mode-dock">
          <span class="foot-mode-label">環境模式</span>
          <ModeSelector variant="full-width" />
        </div>

        <!-- Telemetry Details (Hidden if folded or Dock mode) -->
        <div v-if="!preferences.sidebarFolded && preferences.sidebarStyle !== 'C'" class="telemetry-box">
          <div class="footer-row">
            <span class="foot-label"><span class="dot-indicator"></span> 節點主機：</span>
            <span class="text-accent font-mono">127.0.0.1</span>
          </div>
          <div class="footer-row">
            <span class="foot-label">固定標籤：</span>
            <span class="font-mono text-muted text-2xs">41cb53c54d6dABDE</span>
          </div>
        </div>


        <!-- Position 1: User Profile Panel (Bottom-Left / Sidebar Footer) -->
        <div
          v-if="preferences.userProfilePlacement === 'bottom_left' || preferences.userProfilePlacement === 'both'"
          class="sidebar-user-profile-wrap"
          :class="{ 'is-folded': preferences.sidebarFolded || preferences.sidebarStyle === 'C' }"
        >
          <UserProfilePanel
            position="bottom_left"
            :is-folded="preferences.sidebarFolded || preferences.sidebarStyle === 'C'"
          />
        </div>
      </div>
    </aside>

    <!-- Main Workspace Area -->
    <div class="app-main">
      <!-- Mode Isolation Alert Banner -->
      <div v-if="modeNotice" class="mode-isolation-banner" :class="currentMode === 'live' ? 'banner-danger' : 'banner-warning'">
        <span class="banner-badge">{{ currentMode.toUpperCase() }} 隔離展示</span>
        <span class="banner-msg">{{ modeNotice }}</span>
      </div>

      <header class="app-header">
        <div class="header-left">
          <!-- Top Header Sidebar Toggle Icon (macOS / Linear / ChatGPT Style) -->
          <button
            type="button"
            class="sidebar-toggle-btn"
            @click="toggleSidebarFold"
            :title="preferences.sidebarFolded ? '展開側邊欄 (Ctrl+B)' : '收合側邊欄 (Ctrl+B)'"
            :aria-label="preferences.sidebarFolded ? '展開側邊欄' : '收合側邊欄'"
          >
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="9" y1="3" x2="9" y2="21"/>
            </svg>
          </button>

          <span class="header-title">{{ pageTitle }}</span>
          <span class="header-tag"><span class="header-tag-dot"></span>LOCAL SIM · OKX SWAP</span>
          <div v-if="preferences.sidebarFolded" class="header-folded-mode">
            <ModeSelector variant="dropdown" />
          </div>
        </div>

        <div class="header-right">
          <!-- Page Actions Teleport Target for Unified Header Mode -->
          <div id="header-page-actions" class="header-page-actions"></div>

          <!-- Option 2: Mode Selector in Top Header Right beside connection status -->
          <div v-if="preferences.modeSwitcherPlacement === 'top_header'" class="header-mode-wrap">
            <ModeSelector variant="segmented" />
          </div>
          <TelemetryPopover />

          <!-- Position 2: User Profile Panel (Top-Right / Global Header Cluster) -->
          <div
            v-if="preferences.userProfilePlacement === 'top_right' || preferences.userProfilePlacement === 'both'"
            class="header-user-profile-wrap"
          >
            <UserProfilePanel position="top_right" />
          </div>
        </div>
      </header>

      <main class="app-body">
        <router-view />
      </main>
    </div>

  </div>
</template>

<style scoped>
/* Base Structure */
.brand-text-col {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.brand-row {
  display: flex;
  align-items: baseline;
  gap: 4px;
}
.brand-tagline {
  font-size: 8.5px;
  font-family: var(--font-mono);
  color: #55677d;
  letter-spacing: 0.12em;
}

/* Section Titles (Tabler Clean Text Header, Zero Lines) */
.nav-section-title {
  padding: 14px 14px 4px 14px;
  font-size: 9.5px;
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #4a5c72;
  text-transform: uppercase;
  user-select: none;
}

/* Status Badges (Tabler Badge Concept) */
.nav-badge-wrap {
  margin-left: auto;
}
.nav-status-badge {
  font-size: 9.5px;
  font-family: var(--font-mono);
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 3px;
  letter-spacing: 0.04em;
  line-height: 1.1;
  display: inline-block;
}
.badge-accent {
  background-color: rgba(220, 179, 71, 0.15);
  color: var(--accent);
  border: 1px solid rgba(220, 179, 71, 0.35);
}
.badge-neutral {
  background-color: rgba(46, 160, 67, 0.12);
  color: #3fb950;
  border: 1px solid rgba(46, 160, 67, 0.3);
}
.badge-info {
  background-color: rgba(88, 166, 255, 0.12);
  color: #58a6ff;
  border: 1px solid rgba(88, 166, 255, 0.3);
}


/* Style B: Tabler Single Line Title */
.nav-title-tabler {
  font-size: 13.5px;
  font-weight: 500;
  color: #d1d8e0;
  letter-spacing: 0.02em;
  transition: color 0.15s ease;
}
.nav-item.active .nav-title-tabler {
  color: var(--accent);
  font-weight: 600;
}

/* Style C (Pro Terminal Dock) & Folded Hover Tooltip */
.dock-tooltip {
  position: absolute;
  left: 68px;
  background-color: #121720;
  border: 1px solid rgba(220, 179, 71, 0.35);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.6);
  padding: 6px 10px;
  border-radius: 4px;
  display: none;
  white-space: nowrap;
  z-index: 1000;
  pointer-events: none;
  align-items: center;
  gap: 6px;
}
.dock-tip-title {
  font-size: 12.5px;
  font-weight: 600;
  color: #ffffff;
}
.dock-tip-sub {
  font-size: 9.5px;
  font-family: var(--font-mono);
  color: var(--accent);
}
.dock-tip-key {
  font-size: 9px;
  font-family: var(--font-mono);
  color: #6c7d93;
  margin-left: 4px;
}
.nav-item:hover .dock-tooltip {
  display: flex;
}

/* Footer Section */
.telemetry-box {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-bottom: 6px;
}
.footer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.foot-label {
  font-size: 9.5px;
  color: #6a7c93;
  display: flex;
  align-items: center;
  gap: 4px;
}
.dot-indicator {
  width: 5px;
  height: 5px;
  background-color: #2ea043;
  border-radius: 50%;
  display: inline-block;
}

/* Style Selector Bar */
.sidebar-style-selector {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  padding: 4px 8px;
  background-color: rgba(255, 255, 255, 0.03);
  border: none;
  border-radius: 4px;
}
.selector-label {
  font-size: 9.5px;
  color: #7b8eab;
}
.style-btn-group {
  display: flex;
  gap: 3px;
}
.style-choice-btn {
  background: none;
  border: none;
  color: #8b9cb3;
  font-family: var(--font-mono);
  font-size: 9.5px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.style-choice-btn:hover {
  background-color: rgba(255, 255, 255, 0.06);
  color: #ffffff;
}
.style-choice-btn.active {
  background-color: var(--accent);
  color: #080a0d;
}

/* Modern Header Sidebar Toggle Icon (macOS / Linear Style) */
.sidebar-toggle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}

.sidebar-toggle-btn:hover {
  background: var(--bg-surface-elevated);
  border-color: var(--border-subtle);
  color: var(--accent);
}

/* User Profile Wrappers */
.sidebar-user-profile-wrap {
  margin-top: 6px;
  margin-bottom: 6px;
  width: 100%;
}
.sidebar-user-profile-wrap.is-folded {
  margin-top: 4px;
  margin-bottom: 4px;
  display: flex;
  justify-content: center;
}
.header-user-profile-wrap {
  display: flex;
  align-items: center;
}

.app-body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.brand-left-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-mode-wrap {
  margin-left: auto;
}

.header-folded-mode {
  display: inline-flex;
  margin-left: 10px;
}

.mode-isolation-banner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 6px 16px;
  font-size: var(--text-xs);
  border-bottom: 1px solid transparent;
  flex-shrink: 0;
}

.mode-isolation-banner.banner-warning {
  background: rgba(245, 158, 11, 0.15);
  border-bottom-color: rgba(245, 158, 11, 0.4);
  color: #fde68a;
}

.mode-isolation-banner.banner-danger {
  background: rgba(239, 68, 68, 0.18);
  border-bottom-color: rgba(239, 68, 68, 0.4);
  color: #fca5a5;
}

.banner-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.3);
  letter-spacing: 0.05em;
  flex-shrink: 0;
}

.banner-msg {
  flex: 1;
}

.text-accent { color: var(--accent); }
.text-muted { color: var(--text-muted); }
.font-mono { font-family: var(--font-mono); }
</style>

