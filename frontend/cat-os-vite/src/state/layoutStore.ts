import { create } from "zustand";
import type { LayoutNode, SplitDirection, DropPosition, HoverDropTarget } from "@/lib/layout-tree/types";
import {
  createDefaultTree,
  createTriSplitTree,
  createDualSplitTree,
  updateRatio,
  splitLeaf,
  removeLeaf,
  replaceLeafCard,
  moveAndSplit,
  countLeaves,
  getAllLeaves,
} from "@/lib/layout-tree/tree-ops";

export type CardId = "equity" | "positions" | "allocation" | "fills" | "bots" | "exposure";
export type SlotKey = "leftUpper" | "leftLower" | "rightUpper" | "rightLower";

export interface LayoutProfile {
  id: string;
  name: string;
  shortName: string;
  ratioText: string;
  icon: string;
  desc: string;
  isSystem: boolean;
  rootNode?: LayoutNode;
  leftColWidth: number;
  leftUpperHeight: number;
  rightUpperHeight: number;
  slots: Record<SlotKey, CardId>;
  updatedAt: string;
}

export const CARD_TITLES: Record<CardId, { zh: string; en: string; icon: string }> = {
  equity: { zh: "帳戶權益 (Equity & Drawdown)", en: "Equity & Drawdown", icon: "📈" },
  positions: { zh: "部位與活動 (Positions & Activity)", en: "Positions & Activity", icon: "📊" },
  exposure: { zh: "多空曝險配置 (Exposure)", en: "Exposure & Margin", icon: "📐" },
  bots: { zh: "量化機器人 (Bots Matrix)", en: "Bots Matrix", icon: "🤖" },
  allocation: { zh: "資產配置比例 (Donut)", en: "Asset Allocation", icon: "🪙" },
  fills: { zh: "即時成交流 (Fills)", en: "Recent Fills", icon: "⚡" },
};

export const DEFAULT_PROFILES: LayoutProfile[] = [
  {
    id: "layout_quad_v0_core",
    name: "量化核心四分割 (60:40)",
    shortName: "量化核心",
    ratioText: "60:40",
    icon: "🔲",
    desc: "權益走勢 · 部位活動 · 多空標尺 · 機器人矩陣 專業量化佈局",
    isSystem: true,
    rootNode: createDefaultTree(),
    leftColWidth: 60,
    leftUpperHeight: 50,
    rightUpperHeight: 50,
    slots: {
      leftUpper: "equity",
      leftLower: "positions",
      rightUpper: "allocation",
      rightLower: "bots",
    },
    updatedAt: "定案配置",
  },
  {
    id: "layout_tri_focus",
    name: "主視野三分割 (左一右二)",
    shortName: "三分割",
    ratioText: "60:40",
    icon: "📐",
    desc: "左側權益大圖 · 右側部位與曝險上下佈局",
    isSystem: true,
    rootNode: createTriSplitTree(),
    leftColWidth: 60,
    leftUpperHeight: 100,
    rightUpperHeight: 50,
    slots: {
      leftUpper: "equity",
      leftLower: "positions",
      rightUpper: "exposure",
      rightLower: "bots",
    },
    updatedAt: "預設方案",
  },
  {
    id: "layout_dual_split",
    name: "雙分欄佈局 (50:50)",
    shortName: "雙分欄",
    ratioText: "50:50",
    icon: "⚖️",
    desc: "左側權益 · 右側持倉明細",
    isSystem: true,
    rootNode: createDualSplitTree(),
    leftColWidth: 50,
    leftUpperHeight: 100,
    rightUpperHeight: 100,
    slots: {
      leftUpper: "equity",
      leftLower: "positions",
      rightUpper: "exposure",
      rightLower: "bots",
    },
    updatedAt: "預設方案",
  },
];

export type ToolbarMode = "header" | "card" | "always_on" | "ribbon";
export type SeamStyle = "seamless" | "compact" | "floating";
export type DragPreviewMode = "real-card" | "minimal-blueprint" | "mini-tag";
export type GripStyle = "clean_text" | "precision_dots" | "accent_notch" | "tactical_icon";

const STORAGE_KEY_PROFILES = "catos_layout_profiles_v4_quad";
const STORAGE_KEY_CURRENT = "catos_current_layout_profile_id_v4_quad";
const STORAGE_KEY_TOOLBAR_MODE = "catos_toolbar_candidate_mode_v1";
const STORAGE_KEY_TREE = "catos_layout_tree_root_v3";
const STORAGE_KEY_SEAM_STYLE = "catos_seam_style_candidate_v1";
const STORAGE_KEY_DRAG_PREVIEW = "catos_drag_preview_candidate_v1";
const STORAGE_KEY_GRIP_STYLE = "catos_grip_style_candidate_v1";

interface LayoutState {
  isEditing: boolean;
  currentProfileId: string;
  profiles: LayoutProfile[];

  // 工具列模式
  toolbarMode: ToolbarMode;

  // 卡片間接縫美化風格方案 (A: 無縫直角 | B: 緊湊微隙 | C: 懸浮圓角)
  seamStyle: SeamStyle;
  setSeamStyle: (style: SeamStyle) => void;

  // 卡片拖曳移動預覽候選方案 (A: 實時流體排版預演 | B: 磨砂藍圖骨架 | C: 磁吸微隙門戶)
  dragPreviewMode: DragPreviewMode;
  setDragPreviewMode: (mode: DragPreviewMode) => void;

  // 卡片標題列拖曳抓手視覺方案 (1: 極簡純文字 | 2: 精工微型向量點 | 3: 科技刻度條 | 4: 彭博專業圖標)
  gripStyle: GripStyle;
  setGripStyle: (style: GripStyle) => void;

  // 自研 Layout Tree 引擎核心節點
  rootNode: LayoutNode;
  draggingLeafId: string | null;
  hoverTarget: HoverDropTarget | null;

  // 向下相容 4 分割參數
  leftColWidth: number;
  leftUpperHeight: number;
  rightUpperHeight: number;
  slots: Record<SlotKey, CardId>;
  draggingSlot: SlotKey | null;
  hoverSlot: SlotKey | null;

  toastMessage: string | null;

  // Layout Tree 引擎 Actions
  setRootNode: (node: LayoutNode, persist?: boolean) => void;
  updateSplitRatio: (splitId: string, ratio: number, persist?: boolean) => void;
  splitLeafNode: (targetLeafId: string, direction: SplitDirection, side: "before" | "after", newCardId: CardId) => void;
  removeLeafNode: (leafId: string) => void;
  moveAndSplitNode: (sourceLeafId: string, targetLeafId: string, pos: DropPosition) => void;
  setDraggingLeafId: (id: string | null) => void;
  setHoverTarget: (target: HoverDropTarget | null) => void;
  applyLayoutPreset: (preset: "quad" | "tri" | "dual") => void;
  addNewCard: (cardId: CardId) => void;
  replaceLeafNode: (leafId: string, newCardId: CardId) => void;

  // 舊版相容 Actions
  setToolbarMode: (mode: ToolbarMode) => void;
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

function loadInitial(): {
  profiles: LayoutProfile[];
  currentId: string;
  activeProfile: LayoutProfile;
  rootNode: LayoutNode;
  seamStyle: SeamStyle;
  dragPreviewMode: DragPreviewMode;
  gripStyle: GripStyle;
} {
  const defaultTree = createDefaultTree();
  if (typeof window === "undefined") {
    return {
      profiles: DEFAULT_PROFILES,
      currentId: DEFAULT_PROFILES[0].id,
      activeProfile: DEFAULT_PROFILES[0],
      rootNode: defaultTree,
      seamStyle: "compact",
      dragPreviewMode: "real-card",
      gripStyle: "clean_text",
    };
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

    // 載入持久化 Layout Tree
    let rootNode: LayoutNode = active.rootNode ?? defaultTree;
    const rawTree = localStorage.getItem(STORAGE_KEY_TREE);
    if (rawTree) {
      try {
        const parsedTree = JSON.parse(rawTree);
        if (parsedTree && (parsedTree.type === "leaf" || parsedTree.type === "split")) {
          const leaves = getAllLeaves(parsedTree);
          if (leaves.length >= 1) {
            rootNode = parsedTree;
          }
        }
      } catch {
        // 使用預設樹
      }
    }

    // 載入持久化接縫風格 (使用者已定案：方案 B Bloomberg 緊湊微隙 5px)
    let seamStyle: SeamStyle = "compact";
    const rawSeamStyle = localStorage.getItem(STORAGE_KEY_SEAM_STYLE);
    if (rawSeamStyle === "compact" || rawSeamStyle === "seamless" || rawSeamStyle === "floating") {
      seamStyle = rawSeamStyle;
    }

    // 載入拖曳移動預覽風格 (使用者定案：方案 A 真實卡片即時排版 · 100% 所見即所得)
    const dragPreviewMode: DragPreviewMode = "real-card";
    localStorage.setItem(STORAGE_KEY_DRAG_PREVIEW, "real-card");

    // 載入卡片標題列拖曳抓手視覺方案 (使用者定案：TradingView 純粹無圖示 Zero-Icon)
    const gripStyle: GripStyle = "clean_text";
    localStorage.setItem(STORAGE_KEY_GRIP_STYLE, "clean_text");

    return { profiles, currentId: active.id, activeProfile: active, rootNode, seamStyle, dragPreviewMode, gripStyle };
  } catch {
    return {
      profiles: DEFAULT_PROFILES,
      currentId: DEFAULT_PROFILES[0].id,
      activeProfile: DEFAULT_PROFILES[0],
      rootNode: defaultTree,
      seamStyle: "compact" as SeamStyle,
      dragPreviewMode: "blueprint-snap" as DragPreviewMode,
      gripStyle: "clean_text" as GripStyle,
    };
  }
}

const init = loadInitial();

export const useLayoutStore = create<LayoutState>((set, get) => ({
  isEditing: true,
  currentProfileId: init.currentId,
  profiles: init.profiles,
  toolbarMode: "always_on",

  // 卡片間接縫美化風格方案 (預設為方案 A: seamless 極致無縫)
  seamStyle: init.seamStyle,
  setSeamStyle: (style) => {
    set({ seamStyle: style });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_SEAM_STYLE, style);
    }
    const names: Record<SeamStyle, string> = {
      seamless: "方案 A：VS Code 極致無縫直角 (Zero-Gap)",
      compact: "方案 B：Bloomberg 緊湊微隙 (Compact)",
      floating: "方案 C：懸浮輕量圓角 (Clean Floating)",
    };
    get().showToast(`已切換視覺風格：${names[style]}`);
  },

  // 卡片拖曳移動預覽候選方案
  dragPreviewMode: init.dragPreviewMode,
  setDragPreviewMode: (mode) => {
    set({ dragPreviewMode: mode });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_DRAG_PREVIEW, mode);
    }
  },

  // 卡片標題列拖曳抓手視覺方案
  gripStyle: init.gripStyle,
  setGripStyle: (style) => {
    set({ gripStyle: style });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_GRIP_STYLE, style);
    }
    const names: Record<GripStyle, string> = {
      clean_text: "方案 1：TradingView 純粹無圖示 (Zero-Icon · 零浪費純粹美學)",
      precision_dots: "方案 2：Linear 精工微型向量點 (Precision Micro-Dots · 微光顯現)",
      accent_notch: "方案 3：Raycast 科技雷射刻度條 (Laser Notch · 俐落現代感)",
      tactical_icon: "方案 4：彭博專業業務圖標 (Tactical Micro-Icon · 業務識別度高)",
    };
    get().showToast(`已套用抓手風格：${names[style]}`);
  },

  // 自研 Layout Tree 狀態
  rootNode: init.rootNode,
  draggingLeafId: null,
  hoverTarget: null,

  // 向下相容舊參數
  leftColWidth: init.activeProfile.leftColWidth,
  leftUpperHeight: init.activeProfile.leftUpperHeight,
  rightUpperHeight: init.activeProfile.rightUpperHeight,
  slots: { ...init.activeProfile.slots },
  draggingSlot: null,
  hoverSlot: null,
  toastMessage: null,

  setRootNode: (node, persist = true) => {
    set({ rootNode: node });
    if (persist && typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(node));
    }
  },

  updateSplitRatio: (splitId, ratio, persist = true) => {
    const nextTree = updateRatio(get().rootNode, splitId, ratio);
    set({ rootNode: nextTree });
    if (persist && typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
    }
  },

  splitLeafNode: (targetLeafId, direction, side, newCardId) => {
    const nextTree = splitLeaf(get().rootNode, targetLeafId, direction, side, newCardId);
    set({ rootNode: nextTree });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
    }
    const dirText = direction === "row" ? (side === "before" ? "左側" : "右側") : (side === "before" ? "上方" : "下方");
    get().showToast(`已於${dirText}分裂插入 [${CARD_TITLES[newCardId].zh.split(" ")[0]}]`);
  },

  removeLeafNode: (leafId) => {
    const leavesCount = countLeaves(get().rootNode);
    if (leavesCount <= 1) {
      get().showToast("最後一張核心卡片受保護，無法關閉");
      return;
    }
    const nextTree = removeLeaf(get().rootNode, leafId);
    set({ rootNode: nextTree });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
    }
    get().showToast("已關閉卡片，空間已自動合併填滿");
  },

  moveAndSplitNode: (sourceLeafId, targetLeafId, pos) => {
    if (sourceLeafId === targetLeafId) return;
    const nextTree = moveAndSplit(get().rootNode, sourceLeafId, targetLeafId, pos);
    set({ rootNode: nextTree });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
    }
  },

  setDraggingLeafId: (id) => set({ draggingLeafId: id }),
  setHoverTarget: (target) => set({ hoverTarget: target }),

  applyLayoutPreset: (preset) => {
    let newTree: LayoutNode;
    let label = "";
    if (preset === "quad") {
      newTree = createDefaultTree();
      label = "量化核心四分割 (60:40)";
    } else if (preset === "tri") {
      newTree = createTriSplitTree();
      label = "主視野三分割 (左一右二)";
    } else {
      newTree = createDualSplitTree();
      label = "雙分欄佈局 (50:50)";
    }
    set({ rootNode: newTree });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(newTree));
    }
    get().showToast(`已切換至「${label}」`);
  },

  addNewCard: (cardId) => {
    const leaves = getAllLeaves(get().rootNode);
    if (leaves.length === 0) return;

    // 優先挑選合適的目標節點進行分裂：
    // 若葉子節點數為 1 或 2，採用水平左右分欄 (row)；
    // 若已達 3 張或以上，優先在最後一張卡片垂直向下分列 (col)，保持閱讀視野與寬度
    const target = leaves[leaves.length - 1];
    const direction: SplitDirection = leaves.length >= 2 ? "col" : "row";

    get().splitLeafNode(target.id, direction, "after", cardId);
  },

  replaceLeafNode: (leafId, newCardId) => {
    const nextTree = replaceLeafCard(get().rootNode, leafId, newCardId);
    set({ rootNode: nextTree });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
    }
    get().showToast(`已替換為 [${CARD_TITLES[newCardId]?.zh?.split(" ")[0] || newCardId}]`);
  },

  // ==================== 舊版相容實作 ====================
  setToolbarMode: (mode) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TOOLBAR_MODE, mode);
    }
    set({ toolbarMode: mode, isEditing: mode === "always_on" });
  },

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
    const tree = p.rootNode ?? createDefaultTree();
    set({
      currentProfileId: id,
      rootNode: tree,
      leftColWidth: p.leftColWidth,
      leftUpperHeight: p.leftUpperHeight,
      rightUpperHeight: p.rightUpperHeight,
      slots: { ...p.slots },
    });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_CURRENT, id);
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(tree));
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
      desc: `自訂比例 · 節點數 ${countLeaves(state.rootNode)}`,
      isSystem: false,
      rootNode: state.rootNode,
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
    target.rootNode = state.rootNode;
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
    const newTree = createDefaultTree();
    set({ rootNode: newTree });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(newTree));
    }
    get().showToast("已還原 60:40 核心四分割樹 (每條分割線自由拉伸)");
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

if (typeof window !== "undefined") {
  (window as any).__layoutStore = useLayoutStore;
}

