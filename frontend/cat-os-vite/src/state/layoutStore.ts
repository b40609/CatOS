import { create } from "zustand";

export type CardId = "equity" | "positions" | "allocation" | "fills";
export type SlotKey = "leftUpper" | "leftLower" | "rightUpper" | "rightLower";

export interface LayoutProfile {
  id: string;
  name: string;
  shortName: string;
  ratioText: string;
  icon: string;
  desc: string;
  isSystem: boolean;
  leftColWidth: number;      // 左右欄寬度比例 (例如 64 代表左欄 64%, 右欄 36%)
  leftUpperHeight: number;   // 左欄上方卡片高度比例 (例如 52 代表上 52%, 下 48%)
  rightUpperHeight: number;  // 右欄上方卡片高度比例 (例如 48 代表上 48%, 下 52%)
  slots: Record<SlotKey, CardId>;
  updatedAt: string;
}

export const CARD_TITLES: Record<CardId, { zh: string; en: string; icon: string }> = {
  equity: { zh: "帳戶權益 (Equity & Drawdown)", en: "Equity & Drawdown", icon: "📈" },
  positions: { zh: "持倉部位明細", en: "Open Positions", icon: "📊" },
  allocation: { zh: "資產配置比例", en: "Asset Allocation", icon: "🪙" },
  fills: { zh: "即時成交流", en: "Recent Fills", icon: "⚡" },
};

export const DEFAULT_PROFILES: LayoutProfile[] = [
  {
    id: "layout_quad_6040",
    name: "舒展四分割 (60:40)",
    shortName: "舒展四分割",
    ratioText: "60:40",
    icon: "🔲",
    desc: "左欄 60% 主視野 · 右欄 40% 輔助 · 四角平衡舒展定案佈局",
    isSystem: true,
    leftColWidth: 60,
    leftUpperHeight: 50,
    rightUpperHeight: 50,
    slots: {
      leftUpper: "equity",
      leftLower: "positions",
      rightUpper: "allocation",
      rightLower: "fills",
    },
    updatedAt: "定案配置",
  },
];

const STORAGE_KEY_PROFILES = "catos_layout_profiles_v3_6040";
const STORAGE_KEY_CURRENT = "catos_current_layout_profile_id_v3_6040";

interface LayoutState {
  isEditing: boolean;
  currentProfileId: string;
  profiles: LayoutProfile[];

  // 當前正在生效的佈局參數 (60:40 定案)
  leftColWidth: number;
  leftUpperHeight: number;
  rightUpperHeight: number;
  slots: Record<SlotKey, CardId>;

  // 拖曳狀態
  draggingSlot: SlotKey | null;
  hoverSlot: SlotKey | null;
  toastMessage: string | null;

  // Actions
  setEditing: (editing: boolean) => void;
  setLeftColWidth: (width: number, persist?: boolean) => void;
  setLeftUpperHeight: (height: number, persist?: boolean) => void;
  setRightUpperHeight: (height: number, persist?: boolean) => void;
  setPaneCard: (slot: SlotKey, card: CardId) => void;
  swapPanes: (slotA: SlotKey, slotB: SlotKey) => void;
  setDraggingSlot: (slot: SlotKey | null) => void;
  setHoverSlot: (slot: SlotKey | null) => void;
  applyProfile: (id: string) => void;
  saveNewProfile: (name: string) => void;
  updateCurrentProfile: () => void;
  deleteProfile: (id: string) => void;
  resetSplits: () => void;
  showToast: (msg: string) => void;
}

function loadInitial(): { profiles: LayoutProfile[]; currentId: string; activeProfile: LayoutProfile } {
  if (typeof window === "undefined") {
    return { profiles: DEFAULT_PROFILES, currentId: DEFAULT_PROFILES[0].id, activeProfile: DEFAULT_PROFILES[0] };
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY_PROFILES);
    let profiles = DEFAULT_PROFILES;
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        const custom = parsed.filter((p: LayoutProfile) => !p.isSystem);
        profiles = [...DEFAULT_PROFILES, ...custom];
      }
    }
    const currentId = localStorage.getItem(STORAGE_KEY_CURRENT) || DEFAULT_PROFILES[0].id;
    const active = profiles.find((p) => p.id === currentId) || profiles[0];
    return { profiles, currentId: active.id, activeProfile: active };
  } catch {
    return { profiles: DEFAULT_PROFILES, currentId: DEFAULT_PROFILES[0].id, activeProfile: DEFAULT_PROFILES[0] };
  }
}

const init = loadInitial();

export const useLayoutStore = create<LayoutState>((set, get) => ({
  isEditing: false,
  currentProfileId: init.currentId,
  profiles: init.profiles,

  leftColWidth: init.activeProfile.leftColWidth,
  leftUpperHeight: init.activeProfile.leftUpperHeight,
  rightUpperHeight: init.activeProfile.rightUpperHeight,
  slots: { ...init.activeProfile.slots },

  draggingSlot: null,
  hoverSlot: null,
  toastMessage: null,

  setEditing: (isEditing) => set({ isEditing }),

  setLeftColWidth: (width, persist = true) => {
    set({ leftColWidth: width });
    if (persist) get().updateCurrentProfile();
  },

  setLeftUpperHeight: (height, persist = true) => {
    set({ leftUpperHeight: height });
    if (persist) get().updateCurrentProfile();
  },

  setRightUpperHeight: (height, persist = true) => {
    set({ rightUpperHeight: height });
    if (persist) get().updateCurrentProfile();
  },

  setPaneCard: (slot, card) => {
    const s = { ...get().slots, [slot]: card };
    set({ slots: s });
    get().updateCurrentProfile();
    get().showToast(`已更新 [${slot}] 為 [${CARD_TITLES[card].zh}]`);
  },

  swapPanes: (slotA, slotB) => {
    if (slotA === slotB) return;
    const cur = { ...get().slots };
    const temp = cur[slotA];
    cur[slotA] = cur[slotB];
    cur[slotB] = temp;
    set({ slots: cur });
    get().updateCurrentProfile();
    get().showToast(`卡片位置已成功對調`);
  },

  setDraggingSlot: (draggingSlot) => set({ draggingSlot }),
  setHoverSlot: (hoverSlot) => set({ hoverSlot }),

  applyProfile: (id) => {
    const p = get().profiles.find((x) => x.id === id);
    if (!p) return;
    set({
      currentProfileId: id,
      leftColWidth: p.leftColWidth,
      leftUpperHeight: p.leftUpperHeight,
      rightUpperHeight: p.rightUpperHeight,
      slots: { ...p.slots },
    });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_CURRENT, id);
    }
    get().showToast(`已套用版面：「${p.shortName || p.name}」`);
  },

  saveNewProfile: (name) => {
    const newId = `profile_${Date.now()}`;
    const state = get();
    const newProfile: LayoutProfile = {
      id: newId,
      name: name.trim() || `自訂方案 #${state.profiles.length + 1}`,
      shortName: name.trim() || `自訂 #${state.profiles.length + 1}`,
      ratioText: `${Math.round(state.leftColWidth)}:${Math.round(100 - state.leftColWidth)}`,
      icon: "✨",
      desc: `自訂比例 · 左 ${Math.round(state.leftColWidth)}% / 右 ${Math.round(100 - state.leftColWidth)}%`,
      isSystem: false,
      leftColWidth: state.leftColWidth,
      leftUpperHeight: state.leftUpperHeight,
      rightUpperHeight: state.rightUpperHeight,
      slots: { ...state.slots },
      updatedAt: new Date().toLocaleTimeString("zh-TW", { hour12: false }),
    };

    const next = [...state.profiles, newProfile];
    set({ profiles: next, currentProfileId: newId });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_PROFILES, JSON.stringify(next));
      localStorage.setItem(STORAGE_KEY_CURRENT, newId);
    }
    get().showToast(`已成功另存新版面方案：「${newProfile.name}」`);
  },

  updateCurrentProfile: () => {
    const state = get();
    const target = state.profiles.find((p) => p.id === state.currentProfileId);
    if (!target) return;
    target.leftColWidth = state.leftColWidth;
    target.leftUpperHeight = state.leftUpperHeight;
    target.rightUpperHeight = state.rightUpperHeight;
    target.slots = { ...state.slots };
    target.ratioText = `${Math.round(state.leftColWidth)}:${Math.round(100 - state.leftColWidth)}`;
    target.updatedAt = new Date().toLocaleTimeString("zh-TW", { hour12: false });

    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_PROFILES, JSON.stringify(state.profiles));
    }
  },

  deleteProfile: (id) => {
    const state = get();
    const p = state.profiles.find((x) => x.id === id);
    if (!p) return;
    if (p.isSystem) {
      get().showToast("系統內建方案受保護，無法刪除");
      return;
    }
    const filtered = state.profiles.filter((x) => x.id !== id);
    const nextId = DEFAULT_PROFILES[0].id;
    set({ profiles: filtered });
    get().applyProfile(nextId);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_PROFILES, JSON.stringify(filtered));
    }
    get().showToast(`已刪除自訂方案：「${p.name}」`);
  },

  resetSplits: () => {
    const defaultP = DEFAULT_PROFILES[0];
    set({
      leftColWidth: defaultP.leftColWidth,
      leftUpperHeight: defaultP.leftUpperHeight,
      rightUpperHeight: defaultP.rightUpperHeight,
      slots: { ...defaultP.slots },
      currentProfileId: defaultP.id,
    });
    get().updateCurrentProfile();
    get().showToast("已還原 60:40 舒展四分割黃金比例 (左 60% / 右 40%)");
  },

  showToast: (msg) => {
    set({ toastMessage: msg });
    setTimeout(() => {
      if (get().toastMessage === msg) {
        set({ toastMessage: null });
      }
    }, 2000);
  },
}));
