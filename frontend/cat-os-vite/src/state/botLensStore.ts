import { create } from "zustand";

export type BotLensId = "ALL" | "tabby" | "calico" | "mochi" | "COMPARE_ALL";

export interface BotLensState {
  activeLens: BotLensId;
  setActiveLens: (lens: BotLensId) => void;
  resetLens: () => void;
}

export const useBotLensStore = create<BotLensState>((set) => ({
  activeLens: "ALL",
  setActiveLens: (lens) => set({ activeLens: lens }),
  resetLens: () => set({ activeLens: "ALL" }),
}));

