import { create } from 'zustand';

export type InspectorPresentationMode =
  | "bottom_dock"
  | "inline_row"
  | "master_detail"
  | "popover_peek"
  | "all_active";

export type InspectorTab = 'bot' | 'p6' | 'r1' | 'fill';

/**
 * Inspector selection state. Bot identities come from the catStore `bots`
 * slice; this store only remembers which one the user focused.
 */
interface InspectorState {
  presentationMode: InspectorPresentationMode;
  setPresentationMode: (mode: InspectorPresentationMode) => void;
  selectedBotId: string | null;
  selectBot: (id: string) => void;
  expandedInlineBotIds: string[];
  toggleInlineExpand: (id: string) => void;

  isBottomDockOpen: boolean;
  toggleBottomDock: (open?: boolean) => void;
  isBottomDockMaximized: boolean;
  setBottomDockMaximized: (max: boolean) => void;
  bottomDockTab: "intent" | "stages" | "p6" | "logs" | "risk";
  setBottomDockTab: (tab: "intent" | "stages" | "p6" | "logs" | "risk") => void;

  isOpen: boolean;
  activeTab: InspectorTab;
  selectedPositionId: string | null;
  selectedEventId: string | null;
  width: number;
  isPinned: boolean;

  toggleOpen: () => void;
  setOpen: (open: boolean) => void;
  setActiveTab: (tab: InspectorTab) => void;
  openWithBot: (botId: string) => void;
  openWithP6: (positionId?: string) => void;
  openWithR1: () => void;
  openWithFill: () => void;
  openWithEvent: (eventId: string) => void;
  setWidth: (width: number) => void;
  togglePin: () => void;
}

export const useInspectorStore = create<InspectorState>((set) => ({
  presentationMode: "bottom_dock",
  setPresentationMode: (mode) => set({ presentationMode: mode }),
  selectedBotId: null,
  selectBot: (id) => set({ selectedBotId: id }),
  expandedInlineBotIds: [],
  toggleInlineExpand: (id) =>
    set((state) => ({
      expandedInlineBotIds: state.expandedInlineBotIds.includes(id)
        ? state.expandedInlineBotIds.filter((x) => x !== id)
        : [...state.expandedInlineBotIds, id],
    })),

  isBottomDockOpen: false,
  toggleBottomDock: (open) =>
    set((state) => ({ isBottomDockOpen: open !== undefined ? open : !state.isBottomDockOpen })),
  isBottomDockMaximized: false,
  setBottomDockMaximized: (max) => set({ isBottomDockMaximized: max }),
  bottomDockTab: "stages",
  setBottomDockTab: (tab) => set({ bottomDockTab: tab }),

  isOpen: false,
  activeTab: 'bot',
  selectedPositionId: null,
  selectedEventId: null,
  width: 380,
  isPinned: false,

  toggleOpen: () => set((s) => ({ isOpen: !s.isOpen })),
  setOpen: (isOpen) => set({ isOpen }),
  setActiveTab: (activeTab) => set({ activeTab, isOpen: true }),

  openWithBot: (botId) => set({ activeTab: 'bot', selectedBotId: botId, isOpen: true }),
  openWithP6: (positionId) => set({ activeTab: 'p6', selectedPositionId: positionId ?? null, isOpen: true }),
  openWithR1: () => set({ activeTab: 'r1', isOpen: true }),
  openWithFill: () => set({ activeTab: 'fill', isOpen: true }),
  openWithEvent: (eventId) => set({ selectedEventId: eventId, isOpen: true }),
  setWidth: (width) => set({ width }),
  togglePin: () => set((s) => ({ isPinned: !s.isPinned })),
}));
