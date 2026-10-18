import { create } from "zustand";

export const MIN_SIDEBAR_WIDTH = 190;
export const MAX_SIDEBAR_WIDTH = 420;
export const DEFAULT_SIDEBAR_WIDTH = 245;
export const COLLAPSE_THRESHOLD = 135;
export const EXPAND_THRESHOLD = 145;

const STORAGE_KEY_SIDEBAR_COLLAPSED = "catos_sidebar_collapsed";
const STORAGE_KEY_SIDEBAR_WIDTH = "catos_sidebar_width";

interface SidebarState {
  collapsed: boolean;
  sidebarWidth: number;
  setCollapsed: (collapsed: boolean | ((prev: boolean) => boolean)) => void;
  toggleCollapsed: () => void;
  setSidebarWidth: (width: number) => void;
  resetSidebarWidth: () => void;
}

function loadInitial(): { collapsed: boolean; sidebarWidth: number } {
  let collapsed = false;
  let sidebarWidth = DEFAULT_SIDEBAR_WIDTH;

  if (typeof window !== "undefined") {
    try {
      const savedCollapsed = localStorage.getItem(STORAGE_KEY_SIDEBAR_COLLAPSED);
      if (savedCollapsed !== null) {
        collapsed = savedCollapsed === "true";
      }
      const savedWidth = localStorage.getItem(STORAGE_KEY_SIDEBAR_WIDTH);
      if (savedWidth) {
        const n = parseInt(savedWidth, 10);
        if (!isNaN(n) && n >= MIN_SIDEBAR_WIDTH && n <= MAX_SIDEBAR_WIDTH) {
          sidebarWidth = n;
        }
      }
    } catch {
      // 容錯降級使用預設值
    }
  }

  return { collapsed, sidebarWidth };
}

const initial = loadInitial();

export const useSidebarStore = create<SidebarState>((set, get) => ({
  collapsed: initial.collapsed,
  sidebarWidth: initial.sidebarWidth,

  setCollapsed: (updater) => {
    const next = typeof updater === "function" ? updater(get().collapsed) : updater;
    set({ collapsed: next });
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(STORAGE_KEY_SIDEBAR_COLLAPSED, String(next));
      } catch {}
    }
  },

  toggleCollapsed: () => {
    get().setCollapsed(!get().collapsed);
  },

  setSidebarWidth: (width) => {
    const clamped = Math.min(MAX_SIDEBAR_WIDTH, Math.max(MIN_SIDEBAR_WIDTH, width));
    set({ sidebarWidth: clamped });
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(STORAGE_KEY_SIDEBAR_WIDTH, clamped.toString());
      } catch {}
    }
  },

  resetSidebarWidth: () => {
    set({ sidebarWidth: DEFAULT_SIDEBAR_WIDTH, collapsed: false });
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(STORAGE_KEY_SIDEBAR_WIDTH, DEFAULT_SIDEBAR_WIDTH.toString());
        localStorage.setItem(STORAGE_KEY_SIDEBAR_COLLAPSED, "false");
      } catch {}
    }
  },
}));
