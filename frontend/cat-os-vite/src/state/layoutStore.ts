import { create } from "zustand";
import type { LayoutNode, LeafNode, SplitDirection, DropPosition, HoverDropTarget } from "@/lib/layout-tree/types";
import {
  createDefaultTree,
  createQuadTree,
  createSentinelTree,
  createFlagshipTree,
  createFocusTree,
  createCompareIntentTree,
  createCompareActivityTree,
  createFull9Tree,
  createMasterDetailTree,
  updateRatio,
  splitLeaf,
  removeLeaf,
  replaceLeafCard,
  moveAndSplit,
  countLeaves,
  getAllLeaves,
  addTabToLeaf,
  switchLeafTab,
  removeTabFromLeaf,
} from "@/lib/layout-tree/tree-ops";

export type CardId =
  | "equity"
  | "positions"
  | "allocation"
  | "fills"
  | "bots"
  | "incidents"
  | "market_watch"
  | "strategy_intents"
  | "activity_deck"
  | "bot_inspector";
export type SlotKey = "leftUpper" | "leftLower" | "rightUpper" | "rightLower";

export interface LayoutProfile {
  id: string;
  name: string;
  shortName: string;
  ratioText: string;
  icon: string;
  desc: string;
  isSystem: boolean;
  rootNode?: LayoutNode | null;
  leftColWidth: number;
  leftUpperHeight: number;
  rightUpperHeight: number;
  slots: Record<SlotKey, CardId>;
  updatedAt: string;
}

export const CARD_TITLES: Record<CardId, { zh: string; en: string; icon: string }> = {
  equity: { zh: "帳戶權益與損益", en: "Equity & Drawdown", icon: "📈" },
  positions: { zh: "持倉明細與在途委託", en: "Positions & Orders", icon: "📊" },
  bots: { zh: "策略機器人矩陣", en: "Bots Matrix", icon: "🤖" },
  allocation: { zh: "槓桿倍數與資產曝險", en: "Leverage & Allocation", icon: "🪙" },
  fills: { zh: "即時成交流水", en: "Recent Fills", icon: "⚡" },
  incidents: { zh: "風險警報與異常事件", en: "Risk Incidents", icon: "🚨" },
  market_watch: { zh: "標的行情與資金費率", en: "Market Watch & Rates", icon: "⏱️" },
  strategy_intents: { zh: "策略目標與訊號強度", en: "Signals & Radar", icon: "🎯" },
  activity_deck: { zh: "交易日誌與風險事件", en: "Activity & Events", icon: "📜" },
  bot_inspector: { zh: "機器人深層檢測 (Master-Detail)", en: "Bot Inspector", icon: "🔍" },
};


export type LayoutPresetId =
  | "tsplit"
  | "quad"
  | "sentinel"
  | "flagship"
  | "focus_positions"
  | "empty"
  | "compare_intent"
  | "compare_activity"
  | "full9"
  | "master_detail";

export interface LayoutPresetMeta {
  id: LayoutPresetId;
  nameZh: string;
  shortName: string;
  tag: string;
  cardCount: number;
  desc: string;
}

export const RECOMMENDED_PRESETS: LayoutPresetMeta[] = [
  {
    id: "tsplit",
    nameZh: "5卡標準戰情 (T-Split 上下解耦)",
    shortName: "T-Split",
    tag: "推薦定案",
    cardCount: 5,
    desc: "權益損益 · 策略機器人 · 槓桿曝險 / 持倉委託 · 交易日誌",
  },
  {
    id: "quad",
    nameZh: "4卡象限盯盤 (雙欄經典對稱)",
    shortName: "雙欄對稱",
    tag: "高頻盯盤",
    cardCount: 4,
    desc: "左欄：權益損益+持倉委託 / 右欄：策略機器人+交易日誌 (50:50 對稱)",
  },
  {
    id: "sentinel",
    nameZh: "3卡風控防線 (盤口 60% 主視野)",
    shortName: "風控防線",
    tag: "防線專注",
    cardCount: 3,
    desc: "左側 60% 持倉與在途委託 / 右側 40% 策略機器人與交易日誌",
  },
  {
    id: "flagship",
    nameZh: "6卡操盤旗艦 (全景全功能監控)",
    shortName: "操盤旗艦",
    tag: "全景多螢",
    cardCount: 6,
    desc: "上層：權益損益+策略機器人+標的行情 / 下層：持倉委託+交易日誌+成交流水",
  },
  {
    id: "focus_positions",
    nameZh: "單卡滿版專注 (部位與防線全螢幕)",
    shortName: "部位全螢幕",
    tag: "單卡專注",
    cardCount: 1,
    desc: "100% 滿版展示多空持倉、在途掛單撤單與 P6 災難停損防線",
  },
  {
    id: "empty",
    nameZh: "清空自訂版面 (從零自訂模式)",
    shortName: "一鍵清空",
    tag: "從零自訂",
    cardCount: 0,
    desc: "完全清空主畫面卡片，自由從 [＋卡片] 挑選組裝專屬戰情視窗",
  },
];

export const DEFAULT_PROFILES: LayoutProfile[] = [
  {
    id: "layout_tsplit_v1_core",
    name: "量化戰情 T-Split (上下解耦 · 5卡定案)",
    shortName: "T-Split",
    ratioText: "T-Split",
    icon: "🔲",
    desc: "權益損益 · 策略機器人 · 槓桿曝險 · 持倉委託 · 交易日誌",
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
];

export type ToolbarMode = "header" | "card" | "always_on" | "ribbon";
export type SeamStyle = "seamless" | "compact" | "floating";
export type DragPreviewMode = "real-card" | "minimal-blueprint" | "mini-tag";
export type GripStyle = "clean_text" | "precision_dots" | "accent_notch" | "tactical_icon";

const STORAGE_KEY_PROFILES = "catos_layout_profiles_v8_tsplit";
const STORAGE_KEY_CURRENT = "catos_current_layout_profile_id_v8_tsplit";
const STORAGE_KEY_TOOLBAR_MODE = "catos_toolbar_candidate_mode_v1";
const STORAGE_KEY_TREE = "catos_layout_tree_root_v8_tsplit";
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
  rootNode: LayoutNode | null;
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
  setRootNode: (node: LayoutNode | null, persist?: boolean) => void;
  clearAllCards: () => void;
  updateSplitRatio: (splitId: string, ratio: number, persist?: boolean) => void;
  splitLeafNode: (targetLeafId: string, direction: SplitDirection, side: "before" | "after", newCardId: CardId) => void;
  removeLeafNode: (leafId: string) => void;
  moveAndSplitNode: (sourceLeafId: string, targetLeafId: string, pos: DropPosition) => void;
  setDraggingLeafId: (id: string | null) => void;
  setHoverTarget: (target: HoverDropTarget | null) => void;
  resetToDefaultLayout: () => void;
  applyLayoutPreset: (preset?: LayoutPresetId) => void;
  addNewCard: (cardId: CardId) => void;
  replaceLeafNode: (leafId: string, newCardId: CardId) => void;
  addTabToLeafNode: (leafId: string, cardId: CardId) => void;
  switchLeafTabNode: (leafId: string, cardId: CardId) => void;
  removeTabFromLeafNode: (leafId: string, cardId: CardId) => void;

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
  rootNode: LayoutNode | null;
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
    let rootNode: LayoutNode | null = active.rootNode ?? defaultTree;
    const rawTree = localStorage.getItem(STORAGE_KEY_TREE);
    if (rawTree) {
      if (rawTree === "null") {
        rootNode = null;
      } else try {
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
    const cur = get().rootNode;
    if (!cur) return;
    const nextTree = updateRatio(cur, splitId, ratio);
    set({ rootNode: nextTree });
    if (persist && typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
    }
  },

  splitLeafNode: (targetLeafId, direction, side, newCardId) => {
    const cur = get().rootNode;
    if (!cur) return;
    const nextTree = splitLeaf(cur, targetLeafId, direction, side, newCardId);
    set({ rootNode: nextTree });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
    }
    const dirText = direction === "row" ? (side === "before" ? "左側" : "右側") : (side === "before" ? "上方" : "下方");
    get().showToast(`已於${dirText}分裂插入 [${CARD_TITLES[newCardId].zh.split(" ")[0]}]`);
  },

  removeLeafNode: (leafId) => {
    const currentTree = get().rootNode;
    if (!currentTree) return;
    const nextTree = removeLeaf(currentTree, leafId);
    set({ rootNode: nextTree });
    if (typeof window !== "undefined") {
      if (nextTree) {
        localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
      } else {
        localStorage.setItem(STORAGE_KEY_TREE, "null");
      }
    }
    if (!nextTree) {
      get().showToast("已清空工作區，可由頂部 [＋卡片] 或推薦預設自由自訂");
    } else {
      get().showToast("已關閉卡片，空間已自動合併填滿");
    }
  },

  moveAndSplitNode: (sourceLeafId, targetLeafId, pos) => {
    if (sourceLeafId === targetLeafId) return;
    const currentTree = get().rootNode;
    if (!currentTree) return;
    const nextTree = moveAndSplit(currentTree, sourceLeafId, targetLeafId, pos);
    set({ rootNode: nextTree });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
    }
  },

  setDraggingLeafId: (id) => set({ draggingLeafId: id }),
  setHoverTarget: (target) => set({ hoverTarget: target }),

  resetToDefaultLayout: () => {
    get().applyLayoutPreset("tsplit");
  },

  clearAllCards: () => {
    get().applyLayoutPreset("empty");
  },

  applyLayoutPreset: (presetId = "tsplit") => {
    let newTree: LayoutNode | null = null;
    switch (presetId) {
      case "master_detail":
        newTree = createMasterDetailTree();
        break;
      case "compare_intent":
        newTree = createCompareIntentTree();
        break;
      case "compare_activity":
        newTree = createCompareActivityTree();
        break;
      case "full9":
        newTree = createFull9Tree();
        break;
      case "tsplit":
        newTree = createDefaultTree();
        break;
      case "quad":
        newTree = createQuadTree();
        break;
      case "sentinel":
        newTree = createSentinelTree();
        break;
      case "flagship":
        newTree = createFlagshipTree();
        break;
      case "focus_positions":
        newTree = createFocusTree("positions");
        break;
      case "empty":
        newTree = null;
        break;
      default:
        newTree = createDefaultTree();
    }
    set({ rootNode: newTree });
    if (typeof window !== "undefined") {
      if (newTree) {
        localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(newTree));
      } else {
        localStorage.setItem(STORAGE_KEY_TREE, "null");
      }
    }
    const meta = RECOMMENDED_PRESETS.find((p) => p.id === presetId);
    get().showToast(`已套用排版：${meta?.nameZh || presetId}`);
  },

  addNewCard: (cardId) => {
    const currentTree = get().rootNode;
    if (!currentTree) {
      const newLeaf: LeafNode = {
        type: "leaf",
        id: `leaf-${cardId}-${Date.now()}`,
        cardId,
      };
      set({ rootNode: newLeaf });
      if (typeof window !== "undefined") {
        localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(newLeaf));
      }
      get().showToast(`已建立卡片 [${CARD_TITLES[cardId].zh.split(" ")[0]}]`);
      return;
    }

    const leaves = getAllLeaves(currentTree);
    if (leaves.length === 0) return;

    const target = leaves[leaves.length - 1];
    const direction: SplitDirection = leaves.length >= 2 ? "col" : "row";

    get().splitLeafNode(target.id, direction, "after", cardId);
  },

  replaceLeafNode: (leafId, newCardId) => {
    const cur = get().rootNode;
    if (!cur) return;
    const nextTree = replaceLeafCard(cur, leafId, newCardId);
    set({ rootNode: nextTree });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
    }
    get().showToast(`已替換為 [${CARD_TITLES[newCardId]?.zh?.split(" ")[0] || newCardId}]`);
  },

  addTabToLeafNode: (leafId, cardId) => {
    const cur = get().rootNode;
    if (!cur) return;
    const nextTree = addTabToLeaf(cur, leafId, cardId);
    set({ rootNode: nextTree });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
    }
    get().showToast(`已將 [${CARD_TITLES[cardId]?.zh?.split(" ")[0] || cardId}] 堆疊為分頁標籤`);
  },

  switchLeafTabNode: (leafId, cardId) => {
    const cur = get().rootNode;
    if (!cur) return;
    const nextTree = switchLeafTab(cur, leafId, cardId);
    set({ rootNode: nextTree });
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
    }
  },

  removeTabFromLeafNode: (leafId, cardId) => {
    const cur = get().rootNode;
    if (!cur) return;
    const nextTree = removeTabFromLeaf(cur, leafId, cardId);
    set({ rootNode: nextTree });
    if (typeof window !== "undefined") {
      if (nextTree) {
        localStorage.setItem(STORAGE_KEY_TREE, JSON.stringify(nextTree));
      } else {
        localStorage.setItem(STORAGE_KEY_TREE, "null");
      }
    }
    get().showToast(`已關閉 [${CARD_TITLES[cardId]?.zh?.split(" ")[0] || cardId}] 分頁`);
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

