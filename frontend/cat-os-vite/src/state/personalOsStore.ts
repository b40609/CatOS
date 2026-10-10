import { create } from "zustand";

export type SurfaceTone = "noir" | "oled" | "titanium" | "midnight" | "carbon" | "emerald-dark";
export type AccentColor = "gold" | "cyan" | "emerald" | "violet" | "amber" | "blue" | "rose" | "silver";
export type ColorConvention = "green-up" | "red-up" | "blue-up" | "gold-up";
export type FontScale = "compact-85" | "compact-92" | "standard-100" | "relaxed-112" | "large-125";
export type FontFamily = "jetbrains" | "sf-pro" | "space-grotesk" | "plex";

export interface ThemePreset {
  id: string;
  nameZh: string;
  nameEn: string;
  descZh: string;
  surfaceTone: SurfaceTone;
  accentColor: AccentColor;
  colorConvention: ColorConvention;
  fontFamily: FontFamily;
}

export const THEME_PRESETS: ThemePreset[] = [
  {
    id: "noir-gold",
    nameZh: "Noir 黑曜經典金",
    nameEn: "Noir Obsidian",
    descZh: "catOS 旗艦黑曜石底座，高貴香檳金，國際綠漲紅跌",
    surfaceTone: "noir",
    accentColor: "gold",
    colorConvention: "green-up",
    fontFamily: "jetbrains",
  },
  {
    id: "bloomberg",
    nameZh: "Bloomberg 彭博終端",
    nameEn: "Bloomberg Amber",
    descZh: "華爾街量化經典炭黑，傳奇琥珀金高亮，零光害暗房",
    surfaceTone: "carbon",
    accentColor: "amber",
    colorConvention: "green-up",
    fontFamily: "plex",
  },
  {
    id: "cyberpunk",
    nameZh: "Cyberpunk 賽博霓虹",
    nameEn: "Cyberpunk Neon",
    descZh: "深空冷曜底座，賽博青光環，極致未來極客",
    surfaceTone: "midnight",
    accentColor: "cyan",
    colorConvention: "green-up",
    fontFamily: "space-grotesk",
  },
  {
    id: "oled-pure",
    nameZh: "OLED 極致純黑",
    nameEn: "OLED Midnight",
    descZh: "0 nit 絕對純黑，高對比藍漲珊瑚跌，極致護眼省電",
    surfaceTone: "oled",
    accentColor: "silver",
    colorConvention: "blue-up",
    fontFamily: "sf-pro",
  },
  {
    id: "titanium-pro",
    nameZh: "Titanium 太空冷鈦灰",
    nameEn: "Titanium Slate",
    descZh: "Apple Pro 太空冷灰質感，科技翠綠點綴，洗鍊俐落",
    surfaceTone: "titanium",
    accentColor: "emerald",
    colorConvention: "green-up",
    fontFamily: "sf-pro",
  },
  {
    id: "matrix",
    nameZh: "Matrix 駭客矩陣",
    nameEn: "Matrix Terminal",
    descZh: "墨玉深玄底座，電光駭客綠，華人紅漲綠跌慣例",
    surfaceTone: "emerald-dark",
    accentColor: "emerald",
    colorConvention: "red-up",
    fontFamily: "jetbrains",
  },
];

export interface PersonalOsState {
  // 1. Trader Profile (交易員身分)
  avatar: string;
  displayName: string;
  subAccountAlias: string;
  traderBadge: string;

  // 2. System Theme (作業系統主題 · 與漲跌色完全獨立！)
  surfaceTone: SurfaceTone;
  accentColor: AccentColor;
  fontFamily: FontFamily;

  // 3. Trading Ergonomics (金融看盤手感 · 獨立正交維度)
  colorConvention: ColorConvention;
  fontScale: FontScale;

  // 4. Exchange & Local Daemon (交易所 API 與本地連線)
  apiKey: string;
  passphrase: string;
  environment: "live" | "sim";
  ping: number;

  // Actions
  setAvatar: (avatar: string) => void;
  setDisplayName: (name: string) => void;
  setSubAccountAlias: (alias: string) => void;
  setTraderBadge: (badge: string) => void;
  setSurfaceTone: (tone: SurfaceTone) => void;
  setAccentColor: (accent: AccentColor) => void;
  setFontFamily: (font: FontFamily) => void;
  setColorConvention: (conv: ColorConvention) => void;
  setFontScale: (scale: FontScale) => void;
  applyPreset: (presetId: string) => void;
  setApiCredentials: (apiKey: string, passphrase: string) => void;
  setEnvironment: (env: "live" | "sim") => void;
}

const STORAGE_KEY = "catos_personal_os_settings_v3";

export const ACCENT_PALETTE: Record<
  AccentColor,
  {
    nameZh: string;
    nameEn: string;
    hex: string;
    primary: string;
    ring: string;
    foreground: string;
  }
> = {
  gold: {
    nameZh: "經典金",
    nameEn: "Champagne Gold",
    hex: "#f59e0b",
    primary: "oklch(0.78 0.13 167)",
    ring: "oklch(0.78 0.13 167 / 45%)",
    foreground: "#000000",
  },
  cyan: {
    nameZh: "賽博青",
    nameEn: "Cyber Cyan",
    hex: "#06b6d4",
    primary: "oklch(0.78 0.15 200)",
    ring: "oklch(0.78 0.15 200 / 45%)",
    foreground: "#000000",
  },
  emerald: {
    nameZh: "科技翠",
    nameEn: "Tech Emerald",
    hex: "#10b981",
    primary: "oklch(0.78 0.15 150)",
    ring: "oklch(0.78 0.15 150 / 45%)",
    foreground: "#000000",
  },
  violet: {
    nameZh: "紫羅蘭",
    nameEn: "Neon Violet",
    hex: "#a855f7",
    primary: "oklch(0.72 0.18 300)",
    ring: "oklch(0.72 0.18 300 / 45%)",
    foreground: "#ffffff",
  },
  amber: {
    nameZh: "琥珀橙",
    nameEn: "Bloomberg Amber",
    hex: "#f97316",
    primary: "oklch(0.74 0.18 55)",
    ring: "oklch(0.74 0.18 55 / 45%)",
    foreground: "#000000",
  },
  blue: {
    nameZh: "電光藍",
    nameEn: "Electric Blue",
    hex: "#3b82f6",
    primary: "oklch(0.68 0.17 240)",
    ring: "oklch(0.68 0.17 240 / 45%)",
    foreground: "#ffffff",
  },
  rose: {
    nameZh: "緋紅玫",
    nameEn: "Crimson Rose",
    hex: "#f43f5e",
    primary: "oklch(0.68 0.20 15)",
    ring: "oklch(0.68 0.20 15 / 45%)",
    foreground: "#ffffff",
  },
  silver: {
    nameZh: "鈦晶銀",
    nameEn: "Titanium Silver",
    hex: "#cbd5e1",
    primary: "oklch(0.85 0.02 260)",
    ring: "oklch(0.85 0.02 260 / 45%)",
    foreground: "#000000",
  },
};

export const SURFACE_PALETTE: Record<
  SurfaceTone,
  {
    nameZh: string;
    nameEn: string;
    descZh: string;
    bg: string;
    sidebar: string;
    surface: string;
    raised: string;
    border: string;
  }
> = {
  noir: {
    nameZh: "Noir 黑曜墨黑",
    nameEn: "Noir Obsidian",
    descZh: "深邃黑曜石，catOS 標誌性經典旗艦底色",
    bg: "#101114",
    sidebar: "#141519",
    surface: "#181a1f",
    raised: "#21232a",
    border: "rgba(255, 255, 255, 0.08)",
  },
  oled: {
    nameZh: "OLED 極致純黑",
    nameEn: "OLED Midnight",
    descZh: "0 nit 絕對純黑，暗房交易員必備，零雜光極致對比",
    bg: "#000000",
    sidebar: "#070709",
    surface: "#0f0f13",
    raised: "#16161c",
    border: "rgba(255, 255, 255, 0.1)",
  },
  titanium: {
    nameZh: "Titanium 冷鈦灰",
    nameEn: "Titanium Slate",
    descZh: "Apple Pro 太空冷灰，現代精緻工程質感",
    bg: "#15171c",
    sidebar: "#1a1d24",
    surface: "#20242c",
    raised: "#2a2f3a",
    border: "rgba(255, 255, 255, 0.09)",
  },
  midnight: {
    nameZh: "Midnight 幽藍深空",
    nameEn: "Deep Midnight",
    descZh: "冷空幽藍色系，賽博極客與深夜看盤專屬",
    bg: "#0a0e17",
    sidebar: "#0f1420",
    surface: "#141b2b",
    raised: "#1c263c",
    border: "rgba(56, 189, 248, 0.12)",
  },
  carbon: {
    nameZh: "Carbon 碳纖暗黑",
    nameEn: "Carbon Matrix",
    descZh: "炭黑啞光，彭博終端高密度數據質感",
    bg: "#0d0d0f",
    sidebar: "#121215",
    surface: "#17171c",
    raised: "#202026",
    border: "rgba(255, 255, 255, 0.07)",
  },
  "emerald-dark": {
    nameZh: "Void 墨玉深玄",
    nameEn: "Emerald Void",
    descZh: "極暗墨玉綠底，駭客矩陣終端專屬暗調",
    bg: "#07100b",
    sidebar: "#0b1710",
    surface: "#102017",
    raised: "#162c20",
    border: "rgba(16, 185, 129, 0.12)",
  },
};

export const COLOR_CONVENTIONS: Record<
  ColorConvention,
  {
    nameZh: string;
    nameEn: string;
    descZh: string;
    upColor: string;
    downColor: string;
    upHex: string;
    downHex: string;
  }
> = {
  "green-up": {
    nameZh: "綠漲紅跌 (國際標準)",
    nameEn: "Green Up / Red Down",
    descZh: "Binance, OKX Global, TradingView, 國際加密與美股標準",
    upColor: "oklch(0.78 0.15 165)",
    downColor: "oklch(0.64 0.20 22)",
    upHex: "#10b981",
    downHex: "#f43f5e",
  },
  "red-up": {
    nameZh: "紅漲綠跌 (華人慣例)",
    nameEn: "Red Up / Green Down",
    descZh: "台股、A股、中資期貨終端，華人傳統看盤習慣",
    upColor: "oklch(0.64 0.20 22)",
    downColor: "oklch(0.78 0.15 165)",
    upHex: "#ef4444",
    downHex: "#10b981",
  },
  "blue-up": {
    nameZh: "天藍漲珊瑚跌 (色盲友善)",
    nameEn: "Blue Up / Coral Down",
    descZh: "Bloomberg 彭博專業版標配，色盲友善高辨識度",
    upColor: "oklch(0.74 0.15 220)",
    downColor: "oklch(0.68 0.18 20)",
    upHex: "#38bdf8",
    downHex: "#fb7185",
  },
  "gold-up": {
    nameZh: "金黃漲紫羅蘭跌 (奢華高對比)",
    nameEn: "Amber Up / Purple Down",
    descZh: "極致暗房高對比度，奢華金色多頭與霓虹紫空頭",
    upColor: "oklch(0.80 0.16 85)",
    downColor: "oklch(0.72 0.18 300)",
    upHex: "#fbbf24",
    downHex: "#c084fc",
  },
};

export const FONT_SCALES: Record<
  FontScale,
  {
    nameZh: string;
    nameEn: string;
    descZh: string;
    rootFontSize: string;
    uiScale: string;
  }
> = {
  "compact-85": {
    nameZh: "85% 極致緊湊",
    nameEn: "Ultra Compact",
    descZh: "彭博高密度模式，單屏容納 35+ 行合約，適合 4K/多螢幕",
    rootFontSize: "13.6px",
    uiScale: "0.85",
  },
  "compact-92": {
    nameZh: "92% 專業緊湊",
    nameEn: "Pro Compact",
    descZh: "OKX / 幣安專業版手感，高信息量與可讀性均衡",
    rootFontSize: "14.7px",
    uiScale: "0.92",
  },
  "standard-100": {
    nameZh: "100% 均衡標準",
    nameEn: "Standard",
    descZh: "黃金比例標準字號，兼顧舒適感與排版美學",
    rootFontSize: "16px",
    uiScale: "1.0",
  },
  "relaxed-112": {
    nameZh: "112% 舒適清晰",
    nameEn: "Relaxed",
    descZh: "字體與數據明顯放大，緩解長時間看盤視覺疲勞",
    rootFontSize: "17.9px",
    uiScale: "1.12",
  },
  "large-125": {
    nameZh: "125% 尊享大字",
    nameEn: "Large View",
    descZh: "護眼大字體，遠距螢幕看盤與夜間操作清晰無比",
    rootFontSize: "20px",
    uiScale: "1.25",
  },
};

export const FONT_FAMILIES: Record<
  FontFamily,
  {
    nameZh: string;
    nameEn: string;
    descZh: string;
    cssFamily: string;
  }
> = {
  jetbrains: {
    nameZh: "JetBrains Mono (工程級)",
    nameEn: "JetBrains Mono",
    descZh: "JetBrains Mono 代碼數字 + Work Sans 介面，專業量化首選",
    cssFamily: "'JetBrains Mono', 'Work Sans', ui-sans-serif, system-ui, sans-serif",
  },
  "sf-pro": {
    nameZh: "Apple SF Pro / Inter (洗鍊)",
    nameEn: "Apple SF Pro",
    descZh: "macOS 乾淨現代排版，細膩銳利的字重階梯",
    cssFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  },
  "space-grotesk": {
    nameZh: "Space Grotesk (未來科技)",
    nameEn: "Space Grotesk",
    descZh: "Space Grotesk 幾何現代 + Fira Code 科技等寬",
    cssFamily: "'Space Grotesk', 'Fira Code', monospace, sans-serif",
  },
  plex: {
    nameZh: "IBM Plex (彭博古典)",
    nameEn: "IBM Plex",
    descZh: "IBM Plex Mono 硬核等寬，華爾街量化終端古典氣質",
    cssFamily: "'IBM Plex Mono', 'IBM Plex Sans', monospace, sans-serif",
  },
};

export function applyDomSettings(
  surfaceTone: SurfaceTone,
  accentColor: AccentColor,
  colorConvention: ColorConvention,
  fontScale: FontScale,
  fontFamily: FontFamily = "jetbrains"
) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const body = document.body;

  // 1. 全域字體縮放與數據密度 (雙軌驅動：root fontSize + --ui-font-scale)
  const scale = FONT_SCALES[fontScale] || FONT_SCALES["standard-100"];
  root.style.fontSize = scale.rootFontSize;
  root.style.setProperty("--ui-font-scale", scale.uiScale);
  root.style.setProperty("--ui-content-scale", scale.uiScale);

  // 2. 字體家族風格
  const font = FONT_FAMILIES[fontFamily] || FONT_FAMILIES.jetbrains;
  root.style.setProperty("--font-primary-family", font.cssFamily);
  if (body) {
    body.style.fontFamily = font.cssFamily;
  }

  // 3. 系統底座外觀 (同時覆寫變數與實體 DOM，確保 100% 即時反應)
  const surf = SURFACE_PALETTE[surfaceTone] || SURFACE_PALETTE.noir;
  root.style.setProperty("--background", surf.bg);
  root.style.setProperty("--color-background", surf.bg);
  root.style.setProperty("--sidebar", surf.sidebar);
  root.style.setProperty("--color-sidebar", surf.sidebar);
  root.style.setProperty("--surface", surf.surface);
  root.style.setProperty("--color-surface", surf.surface);
  root.style.setProperty("--surface-raised", surf.raised);
  root.style.setProperty("--color-surface-raised", surf.raised);
  root.style.setProperty("--card", surf.surface);
  root.style.setProperty("--color-card", surf.surface);
  root.style.setProperty("--popover", surf.raised);
  root.style.setProperty("--color-popover", surf.raised);
  root.style.setProperty("--secondary", surf.raised);
  root.style.setProperty("--color-secondary", surf.raised);
  root.style.setProperty("--border", surf.border);
  root.style.setProperty("--color-border", surf.border);

  if (body) {
    body.style.backgroundColor = surf.bg;
  }

  // 4. 系統強調光色 (與漲跌色徹底分開)
  const acc = ACCENT_PALETTE[accentColor] || ACCENT_PALETTE.gold;
  root.style.setProperty("--primary", acc.primary);
  root.style.setProperty("--color-primary", acc.primary);
  root.style.setProperty("--primary-foreground", acc.foreground);
  root.style.setProperty("--color-primary-foreground", acc.foreground);
  root.style.setProperty("--gold", acc.primary);
  root.style.setProperty("--color-gold", acc.primary);
  root.style.setProperty("--ring", acc.ring);
  root.style.setProperty("--color-ring", acc.ring);

  // 5. 金融漲跌色彩慣例 (獨立正交維度)
  const conv = COLOR_CONVENTIONS[colorConvention] || COLOR_CONVENTIONS["green-up"];
  root.style.setProperty("--up", conv.upColor);
  root.style.setProperty("--color-up", conv.upColor);
  root.style.setProperty("--down", conv.downColor);
  root.style.setProperty("--color-down", conv.downColor);

  // 注入全域 attribute 供 CSS 選擇器精準匹配
  root.setAttribute("data-surface-tone", surfaceTone);
  root.setAttribute("data-accent", accentColor);
  root.setAttribute("data-color-conv", colorConvention);
  root.setAttribute("data-font-scale", fontScale);
}

function loadInitialState(): Partial<PersonalOsState> {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return {};
}

const initial = loadInitialState();
const defaultTone: SurfaceTone = (initial.surfaceTone as SurfaceTone) || "noir";
const defaultAccent: AccentColor = (initial.accentColor as AccentColor) || "gold";
const defaultColor: ColorConvention = (initial.colorConvention as ColorConvention) || "green-up";
const defaultFont: FontScale = (initial.fontScale as FontScale) || "standard-100";
const defaultFontFamily: FontFamily = (initial.fontFamily as FontFamily) || "jetbrains";

if (typeof document !== "undefined") {
  applyDomSettings(defaultTone, defaultAccent, defaultColor, defaultFont, defaultFontFamily);
}

export const usePersonalOs = create<PersonalOsState>((set, get) => ({
  avatar: initial.avatar || "🚀",
  displayName: initial.displayName || "CatOS",
  subAccountAlias: initial.subAccountAlias || "OKX-SWAP-01",
  traderBadge: initial.traderBadge || "OKX VIP",

  surfaceTone: defaultTone,
  accentColor: defaultAccent,
  fontFamily: defaultFontFamily,
  colorConvention: defaultColor,
  fontScale: defaultFont,

  apiKey: initial.apiKey || "okx_api_••••••••38f2",
  passphrase: initial.passphrase || "••••••••",
  environment: (initial.environment as "live" | "sim") || "live",
  ping: 18,

  setAvatar: (avatar) => {
    set({ avatar });
    save(get());
  },

  setDisplayName: (displayName) => {
    set({ displayName });
    save(get());
  },

  setSubAccountAlias: (subAccountAlias) => {
    set({ subAccountAlias });
    save(get());
  },

  setTraderBadge: (traderBadge) => {
    set({ traderBadge });
    save(get());
  },

  setSurfaceTone: (surfaceTone) => {
    set({ surfaceTone });
    const s = get();
    applyDomSettings(surfaceTone, s.accentColor, s.colorConvention, s.fontScale, s.fontFamily);
    save(s);
  },

  setAccentColor: (accentColor) => {
    set({ accentColor });
    const s = get();
    applyDomSettings(s.surfaceTone, accentColor, s.colorConvention, s.fontScale, s.fontFamily);
    save(s);
  },

  setFontFamily: (fontFamily) => {
    set({ fontFamily });
    const s = get();
    applyDomSettings(s.surfaceTone, s.accentColor, s.colorConvention, s.fontScale, fontFamily);
    save(s);
  },

  setColorConvention: (colorConvention) => {
    set({ colorConvention });
    const s = get();
    applyDomSettings(s.surfaceTone, s.accentColor, colorConvention, s.fontScale, s.fontFamily);
    save(s);
  },

  setFontScale: (fontScale) => {
    set({ fontScale });
    const s = get();
    applyDomSettings(s.surfaceTone, s.accentColor, s.colorConvention, fontScale, s.fontFamily);
    save(s);
  },

  applyPreset: (presetId) => {
    const p = THEME_PRESETS.find((x) => x.id === presetId);
    if (!p) return;
    set({
      surfaceTone: p.surfaceTone,
      accentColor: p.accentColor,
      colorConvention: p.colorConvention,
      fontFamily: p.fontFamily,
    });
    const s = get();
    applyDomSettings(p.surfaceTone, p.accentColor, p.colorConvention, s.fontScale, p.fontFamily);
    save(s);
  },

  setApiCredentials: (apiKey, passphrase) => {
    set({ apiKey, passphrase });
    save(get());
  },

  setEnvironment: (environment) => {
    set({ environment });
    save(get());
  },
}));

function save(state: PersonalOsState) {
  if (typeof window === "undefined") return;
  try {
    const payload = {
      avatar: state.avatar,
      displayName: state.displayName,
      subAccountAlias: state.subAccountAlias,
      traderBadge: state.traderBadge,
      surfaceTone: state.surfaceTone,
      accentColor: state.accentColor,
      fontFamily: state.fontFamily,
      colorConvention: state.colorConvention,
      fontScale: state.fontScale,
      apiKey: state.apiKey,
      passphrase: state.passphrase,
      environment: state.environment,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {}
}
