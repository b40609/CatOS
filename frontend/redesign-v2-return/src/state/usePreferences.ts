import { ref, watch } from 'vue';

const STORAGE_KEY = 'catos_presentation_preferences_v1';

export type CornerRadius = '0' | '0.5' | '1' | '1.5' | '2';
export type NavPlacement = 'navbar' | 'sidebar';
export type NavStyle = 'attached' | 'floating';
export type OffcanvasStyle = 'attached' | 'floating';
export type SidebarBehavior = 'expanded' | 'folded' | 'on_hover';
export type ContainerWidth = 'default' | 'fluid' | 'boxed';
export type ModeSwitcherPlacement = 'sidebar_stack' | 'top_header' | 'dropdown_badge' | 'sidebar_footer';
export type UserProfilePlacement = 'bottom_left' | 'top_right' | 'both';
export type WorkspaceMode = 'tiling' | 'freeform' | 'hybrid';
export type ThemePreset = 'v0-reference';


export interface Preferences {
  themePreset: ThemePreset; // 原主題 (original) vs v0 備份精準主題 (v0-reference)

  dashboardLayout: 'A' | 'B';
  workspaceMode: WorkspaceMode; // 方案 A: tiling (無縫分割) | 方案 B: freeform (自由網格) | 方案 C: hybrid (混合工作台)
  chartRange: '1D' | '7D' | '30D' | '90D';
  chartStyle: 'refined' | 'minimal' | 'classic';
  borderContrast: 'high' | 'standard' | 'deep_black';
  cardDensity: 'standard' | 'compact';
  sidebarStyle: 'A' | 'B' | 'C' | 'D';
  sidebarFolded: boolean;
  sidebarWidth: number; // custom resizable width in px (190px - 420px, default 245px)
  // Tabler.io Official Parameters (All 6 exact parameters)
  cornerRadius: CornerRadius;
  navPlacement: NavPlacement;
  navStyle: NavStyle;
  offcanvasStyle: OffcanvasStyle;
  sidebarBehavior: SidebarBehavior;
  containerWidth: ContainerWidth;
  // Mode Switcher Placement (4 UX Variants)
  modeSwitcherPlacement: ModeSwitcherPlacement;
  // User Profile & Settings Placement (bottom_left, top_right, both)
  userProfilePlacement: UserProfilePlacement;
  // Sidebar notification badges toggles
  showSidebarBadges: boolean;
  badgeBotsEnabled: boolean;
  badgeRiskEnabled: boolean;
  badgeMarketEnabled: boolean;
}

const defaultPreferences: Preferences = {
  themePreset: 'v0-reference', // 預設使用 v0 備份精準主題，可隨時即時切換回原主題

  dashboardLayout: 'A',
  workspaceMode: 'hybrid', // 預設方案 C：混合式旗艦專業工作台
  chartRange: '7D',
  chartStyle: 'refined',
  borderContrast: 'high',
  cardDensity: 'standard',
  sidebarStyle: 'D', // 定案旗艦工作台 (無發光效果)
  sidebarFolded: false,
  sidebarWidth: 245,
  // Tabler Parameters: 0.5 radius, Sidebar, Attached, Attached offcanvas, Expanded, Default width
  cornerRadius: '0.5',
  navPlacement: 'sidebar',
  navStyle: 'attached',
  offcanvasStyle: 'attached',
  sidebarBehavior: 'expanded',
  containerWidth: 'default',
  modeSwitcherPlacement: 'top_header', // ★ 定案方案二：頂部全域狀態列右側
  userProfilePlacement: 'bottom_left',
  showSidebarBadges: true,
  badgeBotsEnabled: true,
  badgeRiskEnabled: true,
  badgeMarketEnabled: true
};

function loadStoredPreferences(): Preferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};

    // Check URL parameters (?mode=tiling | freeform | hybrid)
    let initialMode: WorkspaceMode = 'hybrid';
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const m = params.get('mode');
      if (m && ['tiling', 'freeform', 'hybrid'].includes(m)) {
        initialMode = m as WorkspaceMode;
      } else if (['tiling', 'freeform', 'hybrid'].includes(parsed.workspaceMode)) {
        initialMode = parsed.workspaceMode;
      }
    } else if (['tiling', 'freeform', 'hybrid'].includes(parsed.workspaceMode)) {
      initialMode = parsed.workspaceMode;
    }

    return {
      dashboardLayout: parsed.dashboardLayout === 'B' ? 'B' : 'A',
      workspaceMode: initialMode,
      chartRange: ['1D', '7D', '30D', '90D'].includes(parsed.chartRange) ? parsed.chartRange : '7D',
      chartStyle: ['refined', 'minimal', 'classic'].includes(parsed.chartStyle) ? parsed.chartStyle : 'refined',
      borderContrast: ['high', 'standard', 'deep_black'].includes(parsed.borderContrast) ? parsed.borderContrast : 'high',
      cardDensity: ['standard', 'compact'].includes(parsed.cardDensity) ? parsed.cardDensity : 'standard',
      sidebarStyle: ['A', 'B', 'C', 'D'].includes(parsed.sidebarStyle) ? parsed.sidebarStyle : 'D',
      sidebarFolded: typeof parsed.sidebarFolded === 'boolean' ? parsed.sidebarFolded : false,
      sidebarWidth: typeof parsed.sidebarWidth === 'number' && parsed.sidebarWidth >= 180 && parsed.sidebarWidth <= 420
        ? parsed.sidebarWidth
        : 245,
      cornerRadius: ['0', '0.5', '1', '1.5', '2'].includes(parsed.cornerRadius) ? parsed.cornerRadius : '0.5',
      navPlacement: ['navbar', 'sidebar'].includes(parsed.navPlacement) ? parsed.navPlacement : 'sidebar',
      navStyle: ['attached', 'floating'].includes(parsed.navStyle) ? parsed.navStyle : 'attached',
      offcanvasStyle: ['attached', 'floating'].includes(parsed.offcanvasStyle) ? parsed.offcanvasStyle : 'attached',
      sidebarBehavior: ['expanded', 'folded', 'on_hover'].includes(parsed.sidebarBehavior) ? parsed.sidebarBehavior : 'expanded',
      containerWidth: ['default', 'fluid', 'boxed'].includes(parsed.containerWidth) ? parsed.containerWidth : 'default',
      modeSwitcherPlacement: ['top_header', 'dropdown_badge', 'sidebar_footer'].includes(parsed.modeSwitcherPlacement)
        ? parsed.modeSwitcherPlacement
        : 'top_header', // ★ 定案方案二：舊預設 sidebar_stack 或未設定者自動升級為方案二
      userProfilePlacement: 'bottom_left',
      themePreset: 'v0-reference',

      showSidebarBadges: typeof parsed.showSidebarBadges === 'boolean' ? parsed.showSidebarBadges : true,
      badgeBotsEnabled: typeof parsed.badgeBotsEnabled === 'boolean' ? parsed.badgeBotsEnabled : true,
      badgeRiskEnabled: typeof parsed.badgeRiskEnabled === 'boolean' ? parsed.badgeRiskEnabled : true,
      badgeMarketEnabled: typeof parsed.badgeMarketEnabled === 'boolean' ? parsed.badgeMarketEnabled : true
    };
  } catch (e) {
    return { ...defaultPreferences };
  }
}

const preferences = ref<Preferences>(loadStoredPreferences());

watch(
  preferences,
  (newVal) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newVal));
    } catch (e) {
      // storage unavailable or full
    }
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', newVal.themePreset);

    }
  },
  { deep: true, immediate: true }
);

export function usePreferences() {
  function setLayout(layout: 'A' | 'B') {
    preferences.value.dashboardLayout = layout;
  }

  function setChartRange(range: '1D' | '7D' | '30D' | '90D') {
    preferences.value.chartRange = range;
  }

  function setChartStyle(style: 'refined' | 'minimal' | 'classic') {
    preferences.value.chartStyle = style;
  }

  function setBorderContrast(contrast: 'high' | 'standard' | 'deep_black') {
    preferences.value.borderContrast = contrast;
  }

  function setCardDensity(density: 'standard' | 'compact') {
    preferences.value.cardDensity = density;
  }

  function setSidebarStyle(style: 'A' | 'B' | 'C' | 'D') {
    preferences.value.sidebarStyle = style;
  }

  function toggleSidebarFold() {
    preferences.value.sidebarFolded = !preferences.value.sidebarFolded;
  }

  function setSidebarFolded(folded: boolean) {
    preferences.value.sidebarFolded = folded;
  }

  function setShowSidebarBadges(show: boolean) {
    preferences.value.showSidebarBadges = show;
  }

  function setBadgeBotsEnabled(enabled: boolean) {
    preferences.value.badgeBotsEnabled = enabled;
  }

  function setBadgeRiskEnabled(enabled: boolean) {
    preferences.value.badgeRiskEnabled = enabled;
  }

  function setBadgeMarketEnabled(enabled: boolean) {
    preferences.value.badgeMarketEnabled = enabled;
  }

  function toggleBadge(key: 'showSidebarBadges' | 'badgeBotsEnabled' | 'badgeRiskEnabled' | 'badgeMarketEnabled') {
    preferences.value[key] = !preferences.value[key];
  }

  function setCornerRadius(r: CornerRadius) {
    preferences.value.cornerRadius = r;
  }

  function setNavPlacement(p: NavPlacement) {
    preferences.value.navPlacement = p;
  }

  function setNavStyle(s: NavStyle) {
    preferences.value.navStyle = s;
  }

  function setOffcanvasStyle(s: OffcanvasStyle) {
    preferences.value.offcanvasStyle = s;
  }

  function setSidebarBehavior(b: SidebarBehavior) {
    preferences.value.sidebarBehavior = b;
    if (b === 'expanded') preferences.value.sidebarFolded = false;
    if (b === 'folded') preferences.value.sidebarFolded = true;
  }

  function setContainerWidth(w: ContainerWidth) {
    preferences.value.containerWidth = w;
  }

  function setModeSwitcherPlacement(placement: ModeSwitcherPlacement) {
    preferences.value.modeSwitcherPlacement = placement;
  }

  function setUserProfilePlacement(placement: UserProfilePlacement) {
    preferences.value.userProfilePlacement = placement;
  }

  function setSidebarWidth(width: number) {
    preferences.value.sidebarWidth = Math.min(420, Math.max(180, Math.round(width)));
  }

  function resetSidebarWidth() {
    preferences.value.sidebarWidth = 245;
  }

  function setWorkspaceMode(mode: WorkspaceMode) {
    preferences.value.workspaceMode = mode;
  }

  function resetToDefaults() {
    preferences.value = { ...defaultPreferences };
    localStorage.removeItem(STORAGE_KEY);
  }





  return {
    preferences,


    setLayout,
    setWorkspaceMode,
    setChartRange,
    setChartStyle,
    setBorderContrast,
    setCardDensity,
    setSidebarStyle,
    setSidebarWidth,
    resetSidebarWidth,
    toggleSidebarFold,
    setSidebarFolded,
    setCornerRadius,
    setNavPlacement,
    setNavStyle,
    setOffcanvasStyle,
    setSidebarBehavior,
    setContainerWidth,
    setModeSwitcherPlacement,
    setUserProfilePlacement,
    setShowSidebarBadges,
    setBadgeBotsEnabled,
    setBadgeRiskEnabled,
    setBadgeMarketEnabled,
    toggleBadge,
    resetToDefaults
  };
}
