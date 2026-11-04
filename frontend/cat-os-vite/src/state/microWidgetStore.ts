import { create } from "zustand";

export type BarTimeframe = "15m" | "1H" | "4H";

export interface KnownSymbolMeta {
  code: string;
  symbol: string;
  defaultPrice: number;
  defaultChange: number;
}

export const POPULAR_SWAP_SYMBOLS: KnownSymbolMeta[] = [
  { code: "BTC", symbol: "BTC-USDT-SWAP", defaultPrice: 62140.5, defaultChange: 1.42 },
  { code: "ETH", symbol: "ETH-USDT-SWAP", defaultPrice: 3375.2, defaultChange: 1.66 },
  { code: "SOL", symbol: "SOL-USDT-SWAP", defaultPrice: 152.8, defaultChange: 3.10 },
  { code: "DOGE", symbol: "DOGE-USDT-SWAP", defaultPrice: 0.1742, defaultChange: 4.21 },
  { code: "SUI", symbol: "SUI-USDT-SWAP", defaultPrice: 2.15, defaultChange: 8.45 },
  { code: "XRP", symbol: "XRP-USDT-SWAP", defaultPrice: 0.584, defaultChange: -0.82 },
  { code: "PEPE", symbol: "PEPE-USDT-SWAP", defaultPrice: 0.0000104, defaultChange: 5.60 },
  { code: "AVAX", symbol: "AVAX-USDT-SWAP", defaultPrice: 28.40, defaultChange: -1.25 },
  { code: "BNB", symbol: "BNB-USDT-SWAP", defaultPrice: 592.5, defaultChange: 0.95 },
];

const STORAGE_KEY = "catos_header_widgets_config_v2";

export interface HeaderWidgetsConfig {
  klineClockMounted: boolean;
  klineTimeframe: BarTimeframe;
  fundingClockMounted: boolean;
  marketTapeMounted: boolean;
  marketTapeMode: "auto" | "custom";
  customSymbols: string[];
}

const DEFAULT_CONFIG: HeaderWidgetsConfig = {
  klineClockMounted: true,
  klineTimeframe: "15m",
  fundingClockMounted: true,
  marketTapeMounted: true,
  marketTapeMode: "auto", // 預設：自動跟隨活躍策略部位 (BTC, ETH, SOL)
  customSymbols: ["BTC", "ETH", "SOL", "DOGE"],
};

interface HeaderWidgetState extends HeaderWidgetsConfig {
  // Actions
  setKlineClockMounted: (mounted: boolean) => void;
  setKlineTimeframe: (tf: BarTimeframe) => void;
  setFundingClockMounted: (mounted: boolean) => void;
  setMarketTapeMounted: (mounted: boolean) => void;
  setMarketTapeMode: (mode: "auto" | "custom") => void;
  addCustomSymbol: (symbol: string) => void;
  removeCustomSymbol: (symbol: string) => void;
  dismissSymbolFromBar: (symbol: string) => void;
  resetHeaderWidgets: () => void;

  // 動態獲取當前應渲染的標的清單
  getActiveSymbols: (activeBotCodes?: string[]) => string[];
}

export const useHeaderWidgetStore = create<HeaderWidgetState>((set, get) => {
  let initial = DEFAULT_CONFIG;
  if (typeof window !== "undefined") {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        initial = { ...DEFAULT_CONFIG, ...parsed };
      }
    } catch {
      // fallback
    }
  }

  const persist = (next: HeaderWidgetsConfig) => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore
      }
    }
  };

  return {
    ...initial,

    setKlineClockMounted: (mounted) => {
      set({ klineClockMounted: mounted });
      persist({ ...get(), klineClockMounted: mounted });
    },

    setKlineTimeframe: (tf) => {
      set({ klineTimeframe: tf });
      persist({ ...get(), klineTimeframe: tf });
    },

    setFundingClockMounted: (mounted) => {
      set({ fundingClockMounted: mounted });
      persist({ ...get(), fundingClockMounted: mounted });
    },

    setMarketTapeMounted: (mounted) => {
      set({ marketTapeMounted: mounted });
      persist({ ...get(), marketTapeMounted: mounted });
    },

    setMarketTapeMode: (mode) => {
      set({ marketTapeMode: mode });
      persist({ ...get(), marketTapeMode: mode });
    },

    addCustomSymbol: (symbol) => {
      const clean = symbol.trim().toUpperCase().replace(/[-_]?(USDT|SWAP)?$/i, "");
      if (!clean) return;
      const current = get().customSymbols;
      if (current.includes(clean)) return;
      const next = [...current, clean];
      set({ customSymbols: next, marketTapeMode: "custom" });
      persist({ ...get(), customSymbols: next, marketTapeMode: "custom" });
    },

    removeCustomSymbol: (symbol) => {
      const clean = symbol.trim().toUpperCase();
      const next = get().customSymbols.filter((s) => s !== clean);
      set({ customSymbols: next });
      persist({ ...get(), customSymbols: next });
    },

    dismissSymbolFromBar: (symbol) => {
      // 頂部直接點擊 × 快速隱藏：若為 auto 模式，則複製當前清單轉為 custom 並排除該幣
      const clean = symbol.trim().toUpperCase();
      const currentMode = get().marketTapeMode;
      const currentSymbols = get().customSymbols;

      if (currentMode === "auto") {
        // 轉為自訂標的池並排除
        const next = ["BTC", "ETH", "SOL"].filter((s) => s !== clean);
        set({ marketTapeMode: "custom", customSymbols: next });
        persist({ ...get(), marketTapeMode: "custom", customSymbols: next });
      } else {
        const next = currentSymbols.filter((s) => s !== clean);
        set({ customSymbols: next });
        persist({ ...get(), customSymbols: next });
      }
    },

    resetHeaderWidgets: () => {
      set(DEFAULT_CONFIG);
      persist(DEFAULT_CONFIG);
    },

    getActiveSymbols: (activeBotCodes) => {
      const state = get();
      if (!state.marketTapeMounted) return [];
      if (state.marketTapeMode === "auto") {
        return activeBotCodes && activeBotCodes.length > 0
          ? activeBotCodes
          : ["BTC", "ETH", "SOL"];
      }
      return state.customSymbols;
    },
  };
});

// 向後相容別名
export const useMicroWidgetStore = useHeaderWidgetStore;
