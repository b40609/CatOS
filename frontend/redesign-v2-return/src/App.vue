<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { useRoute } from 'vue-router';
import ModeSelector from '@/components/common/ModeSelector.vue';
import TelemetryPopover from '@/components/common/TelemetryPopover.vue';
import UserProfilePanel from '@/components/common/UserProfilePanel.vue';
import { usePreferences } from '@/state/usePreferences';
import { useWorkspace } from '@/state/useWorkspace';

const route = useRoute();
const { preferences, setSidebarStyle, setSidebarWidth, resetSidebarWidth, toggleSidebarFold, togglePresentationStyle } = usePreferences();
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

const liveClock = ref('');
function updateClock() {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  liveClock.value = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}
let clockTimer: any = null;

const navSections = computed<NavSection[]>(() => {
  if (preferences.value.presentationStyle === 'relaxed_pro') {
    return [
      {
        title: 'OVERVIEW',
        items: [
          { path: '/', name: 'Dashboard', sub: '戰情總覽', icon: 'dashboard', shortcut: '1' }
        ]
      },
      {
        title: 'RESEARCH',
        items: [
          { path: '/strategies', name: 'Strategies', sub: '策略中心', icon: 'strategy', shortcut: '2' },
          { path: '/backtest', name: 'Backtest', sub: '歷史回測', icon: 'backtest', shortcut: '3' },
          { path: '/optimization', name: 'Optimization', sub: '參數優化', icon: 'optimization', shortcut: '4' },
          { path: '/review', name: 'Review', sub: '策略覆盤', icon: 'review', shortcut: '5' }
        ]
      },
      {
        title: 'EXECUTION & RISK',
        items: [
          { path: '/bots', name: 'Bots', sub: '機器人管理', icon: 'bots', shortcut: '6' },
          { path: '/risk', name: 'Risk Control', sub: '風控中心', icon: 'risk', shortcut: '7' }
        ]
      },
      {
        title: 'ECOSYSTEM & SYSTEM',
        items: [
          { path: '/market-intel', name: 'Market Intel', sub: '市場情報', icon: 'market', shortcut: '8' },
          { path: '/logs', name: 'Logs', sub: '系統日誌', icon: 'logs', shortcut: '9' }
        ]
      }
    ];
  }

  const isEn = preferences.value.language === 'en';
  return [
    {
      title: isEn ? 'OVERVIEW' : '系統總覽',
      items: [
        { path: '/', name: isEn ? 'Dashboard' : '系統總覽', sub: isEn ? 'Realtime Desk' : 'Dashboard', icon: 'dashboard', shortcut: '1' }
      ]
    },
    {
      title: isEn ? 'STRATEGY & RESEARCH' : '策略與研究',
      items: [
        { path: '/strategies', name: isEn ? 'Strategy Hub' : '策略中心', sub: isEn ? 'Quant Models' : 'Strategies', icon: 'strategy', shortcut: '2' },
        { path: '/backtest', name: isEn ? 'Backtesting' : '歷史回測', sub: isEn ? 'Closed-Bar Engine' : 'Backtesting', icon: 'backtest', shortcut: '3' },
        { path: '/optimization', name: isEn ? 'Optimization' : '參數優化', sub: isEn ? 'Optuna Grid' : 'Optimization', icon: 'optimization', shortcut: '4' },
        { path: '/review', name: isEn ? 'Strategy Review' : '策略覆盤', sub: isEn ? 'Audit & Review' : 'Strategy Review', icon: 'review', shortcut: '5' }
      ]
    },
    {
      title: isEn ? 'EXECUTION & RISK' : '執行與風控',
      items: [
        { path: '/bots', name: isEn ? 'Bot Manager' : '機器人管理', sub: isEn ? 'Worker Fleet' : 'Bot Manager', icon: 'bots', badge: { id: 'bots', text: '1/3', type: 'accent' }, shortcut: '6' },
        { path: '/risk', name: isEn ? 'Risk Control' : '風控中心', sub: isEn ? 'Guardian Safe' : 'Risk Control', icon: 'risk', badge: { id: 'risk', text: 'SAFE', type: 'neutral' }, shortcut: '7' }
      ]
    },
    {
      title: isEn ? 'ECOSYSTEM & SYSTEM' : '生態與系統',
      items: [
        { path: '/market-intel', name: isEn ? 'Market Intel' : '市場情報', sub: isEn ? 'Yaozi Feed (DEV)' : 'Market Intel', icon: 'market', badge: { id: 'market', text: 'DEV', type: 'info' }, shortcut: '8' },
        { path: '/logs', name: isEn ? 'System Logs' : '系統日誌', sub: isEn ? 'Structured Events' : 'System Logs', icon: 'logs', shortcut: '9' }
      ]
    }
  ];
});

function isBadgeVisible(badgeId?: 'bots' | 'risk' | 'market'): boolean {
  if (!preferences.value.showSidebarBadges) return false;
  if (badgeId === 'bots') return preferences.value.badgeBotsEnabled;
  if (badgeId === 'risk') return preferences.value.badgeRiskEnabled;
  if (badgeId === 'market') return preferences.value.badgeMarketEnabled;
  return true;
}

const pageTitle = computed(() => {
  if (preferences.value.presentationStyle === 'relaxed_pro') {
    const p = route.path;
    if (p === '/') return 'Dashboard';
    if (p === '/strategies') return 'Strategies';
    if (p === '/backtest') return 'Backtest';
    if (p === '/optimization') return 'Optimization';
    if (p === '/review') return 'Review';
    if (p === '/bots') return 'Bots';
    if (p === '/risk') return 'Risk Control';
    if (p === '/market-intel') return 'Market Intel';
    if (p === '/logs') return 'Logs';
    if (p === '/settings') return 'Settings';
    return 'Dashboard';
  }

  const isEn = preferences.value.language === 'en';
  const path = route.path;
  if (path === '/') return isEn ? 'Dashboard Overview' : '系統總覽';
  if (path === '/strategies') return isEn ? 'Strategy Hub' : '策略中心';
  if (path === '/backtest') return isEn ? 'Backtesting Engine' : '歷史回測';
  if (path === '/optimization') return isEn ? 'Parameter Optimization' : '參數優化';
  if (path === '/review') return isEn ? 'Strategy Review' : '策略覆盤';
  if (path === '/bots') return isEn ? 'Bot Manager' : '機器人管理';
  if (path === '/risk') return isEn ? 'Risk Control' : '風控中心';
  if (path === '/market-intel') return isEn ? 'Market Intelligence' : '市場情報';
  if (path === '/logs') return isEn ? 'System Logs' : '系統日誌';
  if (path === '/settings') return isEn ? 'System Settings' : '系統設定';
  return (route.meta?.title as string) || (isEn ? 'Dashboard' : '系統總覽');
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
  updateClock();
  clockTimer = setInterval(updateClock, 1000);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
  if (clockTimer) clearInterval(clockTimer);
});
</script>

<template>
  <div
    class="app-shell"
    :data-theme="preferences.themePreset"
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
        'is-resizing-sidebar': isResizingSidebar,
        'is-relaxed-shell': preferences.presentationStyle === 'relaxed_pro'
      }
    ]"
    :style="{
      '--sidebar-width': (preferences.sidebarFolded || preferences.sidebarBehavior === 'folded')
        ? '64px'
        : (preferences.presentationStyle === 'relaxed_pro' ? '228px' : `${preferences.sidebarWidth || 245}px`)
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
      <div class="sidebar-header" :class="{ 'is-relaxed-header': preferences.presentationStyle === 'relaxed_pro' }">
        <template v-if="preferences.presentationStyle === 'relaxed_pro'">
          <div class="brand-top-row-relaxed">
            <span class="relaxed-cat-badge">
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 5c.67 0 1.35.09 2 .26 1.78-2 5.03-2.84 6.42-2.26 1.4.58-.42 4-.42 4 .57 1.07 1 2.24 1 3.44C21 16 17 21 12 21S3 16 3 10.44c0-1.2.43-2.37 1-3.44 0 0-1.82-3.42-.42-4 1.39-.58 4.64.26 6.42 2.26.65-.17 1.33-.26 2-.26z"/>
                <circle cx="9" cy="12" r="1"/>
                <circle cx="15" cy="12" r="1"/>
              </svg>
            </span>
            <span v-if="!preferences.sidebarFolded" class="relaxed-brand-text">
              catOS<span class="relaxed-dot-green">.</span>
            </span>
          </div>

          <!-- Quant Workspace Card Inset -->
          <div v-if="!preferences.sidebarFolded" class="relaxed-workspace-card">
            <span class="relaxed-ws-badge">M</span>
            <span class="relaxed-ws-text">Quant Workspace</span>
            <svg class="relaxed-ws-caret" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </div>
        </template>
        <template v-else>
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
          </div>
        </template>
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
              <!-- 4.5. Strategy Review: Diagnostic Trend Chart -->
              <svg v-else-if="item.icon === 'review'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 3v18h18"/>
                <path d="M7 14l4-4 4 4 5-6"/>
                <circle cx="20" cy="8" r="1.5"/>
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
            <template v-if="preferences.presentationStyle === 'relaxed_pro' && !preferences.sidebarFolded">
              <span class="relaxed-nav-row">
                <span class="relaxed-nav-label">{{ item.name }}</span>
                <span class="relaxed-nav-sub">{{ item.sub }}</span>
              </span>
            </template>
            <div v-else-if="!preferences.sidebarFolded && preferences.sidebarStyle !== 'C'" class="nav-text-col">
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
        <div v-if="preferences.presentationStyle === 'relaxed_pro' && !preferences.sidebarFolded" class="relaxed-sidebar-status">
          <span class="relaxed-status-dot"></span>
          <span class="relaxed-status-text">All systems operational</span>
          <span class="relaxed-status-ver num">v2.0</span>
        </div>

        <!-- User Profile Panel (定案左下角側邊欄底座) -->
        <div
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


      <header class="app-header" :class="{ 'is-relaxed-header': preferences.presentationStyle === 'relaxed_pro' }">
        <div class="header-left">
          <!-- Top Header Sidebar Toggle Icon (Lovable & Linear Style) -->
          <button
            type="button"
            class="sidebar-toggle-btn"
            @click="toggleSidebarFold"
            :title="preferences.sidebarFolded ? '展開側邊欄 (Ctrl+B)' : '收合側邊欄 (Ctrl+B)'"
            :aria-label="preferences.sidebarFolded ? '展開側邊欄' : '收合側邊欄'"
          >
            <!-- Lovable [|<] collapse icon when in relaxed mode (Lucide PanelLeftClose) -->
            <svg v-if="preferences.presentationStyle === 'relaxed_pro'" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <rect width="18" height="18" x="3" y="3" rx="2"/>
              <path d="M9 3v18"/>
              <path d="m16 15-3-3 3-3"/>
            </svg>
            <svg v-else width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="9" y1="3" x2="9" y2="21"/>
            </svg>
          </button>

          <!-- Lovable Breadcrumb Trail Workspace / {{ pageTitle }} -->
          <div v-if="preferences.presentationStyle === 'relaxed_pro'" class="breadcrumb-trail">
            <span class="crumb-dim">Workspace</span>
            <span class="crumb-slash">/</span>
            <span class="crumb-active">{{ pageTitle }}</span>
          </div>
          <span v-else class="header-title">{{ pageTitle }}</span>
        </div>

        <div class="header-right">
          <!-- ✦ 鬆弛專業版 vs 原版高密版 即時切換比對膠囊 -->
          <div class="presentation-switch-wrap">
            <button
              type="button"
              class="style-toggle-pill"
              :class="{ 'is-relaxed': preferences.presentationStyle === 'relaxed_pro' }"
              @click="togglePresentationStyle"
              :title="preferences.presentationStyle === 'relaxed_pro' ? '點擊切換為原版高密平鋪模式 (Bloomberg)' : '點擊切換為 ✦ 鬆弛專業模式 (Lovable)'"
            >
              <span class="pill-dot" :class="preferences.presentationStyle === 'relaxed_pro' ? 'dot-relaxed' : 'dot-bloomberg'"></span>
              <span class="pill-text">
                {{ preferences.presentationStyle === 'relaxed_pro' ? '✦ 鬆弛專業版' : '原版高密版' }}
              </span>
            </button>
          </div>

          <template v-if="preferences.presentationStyle === 'relaxed_pro'">
            <span class="trading-pill-gold num">PAPER TRADING</span>
            <span class="engine-status-text">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" class="pulse-radio-icon">
                <circle cx="12" cy="12" r="2"/>
                <path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49"/>
              </svg>
              Engine online
            </span>
            <span class="clock-utc-text num">{{ liveClock }} UTC+8</span>
          </template>

          <template v-else>
            <!-- Page Actions Teleport Target for Unified Header Mode -->
            <div id="header-page-actions" class="header-page-actions"></div>

            <!-- Finalized Mode Selector in Top Header Right beside connection status (Option 2) -->
            <div class="header-mode-wrap">
              <ModeSelector variant="segmented" />
            </div>
            <TelemetryPopover />
          </template>
        </div>
      </header>


      <main class="app-body">
        <router-view />
      </main>

      <!-- Lovable Style Grounded Terminal Footer -->
      <footer v-if="preferences.presentationStyle === 'relaxed_pro'" class="relaxed-footer">
        <div class="footer-left">
          <span class="footer-latency-dot"></span>
          <span>Binance <span class="num">18ms</span></span>
          <span class="footer-bar">|</span>
          <span>OKX <span class="num">24ms</span></span>
        </div>
        <div class="footer-right">
          <span>catOS Terminal · Simulated market data</span>
        </div>
      </footer>
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
  color: #68707b;
  letter-spacing: 0.12em;
}

/* Section Titles (Tabler Clean Text Header, Zero Lines) */
.nav-section-title {
  padding: 14px 14px 4px 14px;
  font-size: 9.5px;
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 0.12em;
  color: #68707b;
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
  background-color: var(--accent-subtle);
  color: var(--accent);
  border: 1px solid var(--accent-border);
}
.badge-neutral {
  background-color: rgba(46, 160, 67, 0.12);
  color: #3fb950;
  border: 1px solid rgba(46, 160, 67, 0.3);
}
.badge-info {
  background-color: var(--info-bg, rgba(147, 190, 229, 0.15));
  color: var(--info-accent, #93bee5);
  border: 1px solid var(--info-border, rgba(147, 190, 229, 0.45));
  font-weight: 600;
}

/* Style B: Tabler Single Line Title */
.nav-title-tabler {
  font-size: 13.5px;
  font-weight: 500;
  color: #e5e8ec;
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
  background-color: var(--bg-surface-elevated);
  border: 1px solid var(--accent-border);
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
  color: #727a85;
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
  color: #727a85;
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
  color: #727a85;
}
.style-btn-group {
  display: flex;
  gap: 3px;
}
.style-choice-btn {
  background: none;
  border: none;
  color: #727a85;
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
  background: #161a20;
  border-color: #24282e;
  color: var(--accent);
}

.is-relaxed-shell .sidebar-toggle-btn {
  color: #71717a;
  border-radius: 6px;
}

.is-relaxed-shell .sidebar-toggle-btn:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: transparent;
  color: #fafafa;
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

.is-relaxed-shell .app-main {
  background-color: var(--os-bg-base) !important;
}

.is-relaxed-shell .app-body {
  background-color: var(--os-bg-base) !important;
  overflow-y: auto;
  overflow-x: hidden;
}

.is-relaxed-shell .app-sidebar {
  background-color: var(--os-bg-sidebar) !important;
  border-right: 1px solid var(--os-border) !important;
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

/* Lovable Relaxed Pro Header Breadcrumb */
.breadcrumb-trail {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: 12px;
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
  font-size: 13.5px;
  line-height: 1;
  -webkit-font-smoothing: antialiased !important;
  -moz-osx-font-smoothing: grayscale !important;
  opacity: 0.999;
}

.crumb-dim {
  color: #71717a !important;
  font-weight: 400 !important;
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
  letter-spacing: -0.01em;
  -webkit-font-smoothing: antialiased !important;
  -moz-osx-font-smoothing: grayscale !important;
}

.crumb-slash {
  color: #52525b !important;
  font-size: 13px !important;
  font-weight: 300 !important;
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
  user-select: none;
  padding: 0 4px;
  -webkit-font-smoothing: antialiased !important;
  -moz-osx-font-smoothing: grayscale !important;
}

.crumb-active {
  color: #e9ebee !important;
  font-weight: 500 !important;
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
  letter-spacing: -0.01em;
  -webkit-font-smoothing: antialiased !important;
  -moz-osx-font-smoothing: grayscale !important;
}

/* Presentation Style Switcher (✦ 鬆弛專業版 vs 原版高密版) */
.presentation-switch-wrap {
  display: flex;
  align-items: center;
  margin-right: 8px;
}

.style-toggle-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  color: var(--os-text-secondary);
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.style-toggle-pill:hover {
  background: var(--os-bg-card-hover);
  border-color: var(--os-border-highlight);
  color: var(--os-text-primary);
}

.style-toggle-pill.is-relaxed {
  border-color: var(--os-up-border);
  color: var(--os-text-primary);
  background: rgba(52, 211, 153, 0.08);
}

.pill-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.dot-relaxed {
  background: var(--os-up);
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.6);
}

.pill-bloomberg {
  background: var(--os-warn);
}

/* Relaxed Pro Specific Styles */
.app-header.is-relaxed-header {
  height: 56px !important;
  min-height: 56px !important;
  padding: 0 2.25rem !important;
  border-bottom: 1px solid var(--os-border) !important;
  background-color: var(--os-bg-base) !important;
}

.sidebar-header.is-relaxed-header {
  padding: 0 0 0.5rem 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.brand-top-row-relaxed {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  height: 56px;
  padding: 0 1rem;
}

.relaxed-cat-badge {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--os-up);
  color: #0c0f12;
  flex-shrink: 0;
}

.relaxed-brand-text {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--os-text-primary);
  letter-spacing: -0.02em;
}

.relaxed-dot-green {
  color: var(--os-up);
}

.relaxed-workspace-card {
  margin: 0 0.75rem 0.5rem 0.75rem;
  padding: 0.55rem 0.75rem;
  background: var(--os-bg-card);
  border: 1px solid var(--os-border);
  border-radius: var(--os-card-radius, 6px);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.relaxed-workspace-card:hover {
  background: var(--os-bg-card-hover);
  border-color: rgba(255, 255, 255, 0.14);
}

.relaxed-ws-badge {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 4px;
  background: #23252a;
  color: var(--os-up);
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.relaxed-ws-text {
  font-size: 11.5px;
  font-weight: 500;
  color: var(--os-text-primary);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.relaxed-ws-caret {
  color: var(--os-text-muted);
  flex-shrink: 0;
}

.relaxed-nav-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.relaxed-nav-label {
  font-size: 12px;
  font-weight: 500;
  color: inherit;
}

.relaxed-nav-sub {
  font-size: 10px;
  color: var(--os-text-muted);
}

.relaxed-sidebar-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0 1rem;
  margin-bottom: 0.65rem;
  font-size: 10px;
  color: var(--os-text-muted);
}

.relaxed-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--os-up);
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.5);
}

.relaxed-status-ver {
  margin-left: auto;
  font-size: 10px;
  color: var(--os-text-muted);
}

/* Header Right Relaxed Elements */
.trading-pill-gold {
  border: 1px solid rgba(251, 191, 36, 0.3);
  background: rgba(251, 191, 36, 0.06);
  color: var(--os-warn);
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 4px;
  letter-spacing: 0.04em;
  font-weight: 500;
}

.engine-status-text {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 11px;
  color: var(--os-text-muted);
}

.pulse-radio-icon {
  color: var(--os-up);
}

.clock-utc-text {
  font-size: 10.5px;
  color: var(--os-text-muted);
  font-family: var(--font-mono);
}

.app-header.is-relaxed-header .header-right {
  display: flex;
  align-items: center;
  gap: 1.15rem;
}

/* Grounded Terminal Footer */
.relaxed-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.75rem;
  border-top: 1px solid var(--os-border);
  font-size: 10px;
  color: var(--os-text-muted);
  background: var(--os-bg-base);
  margin-top: auto;
}

.footer-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.footer-latency-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--os-up);
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.5);
}

.footer-bar {
  color: var(--os-border-highlight);
  margin: 0 0.25rem;
}

.footer-right {
  color: var(--os-text-muted);
}

/* In Relaxed Mode, adapt sidebar UserProfilePanel to card surface */
.is-relaxed-shell .profile-trigger-sidebar {
  background: var(--os-bg-card) !important;
  border: 1px solid var(--os-border) !important;
  border-radius: var(--os-card-radius, 6px) !important;
}

.is-relaxed-shell .profile-trigger-sidebar:hover {
  background: var(--os-bg-card-hover) !important;
  border-color: rgba(255, 255, 255, 0.14) !important;
}

.is-relaxed-shell .sidebar-user-profile-wrap {
  padding: 0 0.75rem 0.75rem 0.75rem !important;
}
</style>


