import { useState, useEffect } from "react";
import {
  Check,
  KeyRound,
  Palette,
  ShieldCheck,
  Sliders,
  Type,
  User,
  X,
  Sparkles,
  TrendingUp,
  Zap,
  Activity,
  Monitor,
  Flame,
} from "lucide-react";
import {
  usePersonalOs,
  THEME_PRESETS,
  ACCENT_PALETTE,
  SURFACE_PALETTE,
  COLOR_CONVENTIONS,
  FONT_SCALES,
  FONT_FAMILIES,
  type AccentColor,
  type SurfaceTone,
  type FontScale,
  type ColorConvention,
  type FontFamily,
} from "@/state/personalOsStore";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const AVATAR_OPTIONS = ["🚀", "₿", "Ξ", "◎", "🐱", "⚡", "🦁", "🐋"];
const BADGE_OPTIONS = ["OKX VIP", "KOL Partner", "Quant Fund", "Alpha Trader"];

export function PersonalOsModal({
  isOpen,
  onClose,
  initialTab = "presets",
}: {
  isOpen: boolean;
  onClose: () => void;
  initialTab?: "presets" | "theme" | "trading" | "identity" | "api";
}) {
  const { language } = useI18n();
  const [activeTab, setActiveTab] = useState<"presets" | "theme" | "trading" | "identity" | "api">(initialTab);

  const {
    avatar,
    setAvatar,
    displayName,
    setDisplayName,
    subAccountAlias,
    setSubAccountAlias,
    traderBadge,
    setTraderBadge,
    surfaceTone,
    setSurfaceTone,
    accentColor,
    setAccentColor,
    fontFamily,
    setFontFamily,
    colorConvention,
    setColorConvention,
    fontScale,
    setFontScale,
    applyPreset,
    apiKey,
    passphrase,
    environment,
    setEnvironment,
    ping,
  } = usePersonalOs();

  const [nameInput, setNameInput] = useState(displayName);
  const [aliasInput, setAliasInput] = useState(subAccountAlias);
  const [savedToast, setSavedToast] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
      setNameInput(displayName);
      setAliasInput(subAccountAlias);
    }
  }, [isOpen, initialTab, displayName, subAccountAlias]);

  if (!isOpen) return null;

  const handleSaveIdentity = (e: React.FormEvent) => {
    e.preventDefault();
    if (nameInput.trim()) setDisplayName(nameInput.trim());
    if (aliasInput.trim()) setSubAccountAlias(aliasInput.trim());
    setSavedToast(true);
    setTimeout(() => setSavedToast(false), 1500);
  };

  const currentConv = COLOR_CONVENTIONS[colorConvention] || COLOR_CONVENTIONS["green-up"];
  const currentAccent = ACCENT_PALETTE[accentColor] || ACCENT_PALETTE.gold;
  const currentSurface = SURFACE_PALETTE[surfaceTone] || SURFACE_PALETTE.noir;
  const currentScale = FONT_SCALES[fontScale] || FONT_SCALES["standard-100"];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/75 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-border/70 bg-popover/98 shadow-2xl backdrop-blur-2xl text-foreground flex flex-col max-h-[92vh]">
        
        {/* ==================== 頂部標題列 ==================== */}
        <header className="flex items-center justify-between border-b border-border/50 px-6 py-3.5 bg-secondary/30 shrink-0">
          <div className="flex items-center gap-2.5">
            <span className="grid size-7 place-items-center rounded-lg bg-primary/15 text-primary shadow-xs">
              <Sliders className="size-4" />
            </span>
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-foreground flex items-center gap-2">
                <span>{language === "zh-TW" ? "catOS 專屬量化交易作業系統設定" : "catOS Personal Trading OS"}</span>
                <span className="rounded bg-primary/15 px-1.5 py-0.2 font-mono text-[9px] font-semibold text-primary">
                  PRO
                </span>
              </h2>
              <p className="text-[10px] text-muted-foreground">
                {language === "zh-TW"
                  ? "獨立金融漲跌色彩 · 全域數據字號密度 · 業界傳奇主題與外觀訂製"
                  : "Independent price colors, layout density, themes & live diagnostics"}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid size-7 place-items-center rounded-lg text-muted-foreground hover:bg-secondary/70 hover:text-foreground transition-colors"
            title="關閉"
          >
            <X className="size-4" />
          </button>
        </header>

        {/* ==================== 即時微型看盤儀表預覽 (Live Mini-Dashboard Preview) ==================== */}
        <div className="px-6 pt-3 pb-2 shrink-0 bg-background/50 border-b border-border/30">
          <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground mb-1.5">
            <span className="flex items-center gap-1.5 uppercase font-medium">
              <span className="size-1.5 rounded-full bg-primary animate-pulse" />
              {language === "zh-TW" ? "即時渲染預覽 (Live Interactive Preview)" : "Live Interactive Preview"}
            </span>
            <span className="text-[10px] text-foreground/80 font-mono">
              {currentScale.nameZh} · {currentConv.nameZh.split(" ")[0]} · {currentAccent.nameZh}
            </span>
          </div>

          <div
            className="rounded-xl border p-3 transition-all duration-300 shadow-sm flex flex-wrap items-center justify-between gap-3"
            style={{
              backgroundColor: currentSurface.surface,
              borderColor: currentSurface.border,
            }}
          >
            {/* 交易員即時身分預覽 */}
            <div className="flex items-center gap-2.5 min-w-[140px]">
              <span className="text-2xl leading-none select-none">{avatar}</span>
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-semibold text-foreground">{displayName || "CatOS"}</span>
                  <span className="rounded bg-primary/20 px-1 py-0.2 text-[9px] font-mono font-medium text-primary">
                    {traderBadge}
                  </span>
                </div>
                <span className="font-mono text-[10px] text-muted-foreground block">{subAccountAlias}</span>
              </div>
            </div>

            {/* 即時持倉與漲跌色示範 */}
            <div className="flex items-center gap-4">
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-xs font-semibold text-foreground">BTC-PERP</span>
                  <span
                    className="rounded px-1 py-0.2 text-[9px] font-bold"
                    style={{
                      backgroundColor: `color-mix(in srgb, ${currentConv.upHex} 15%, transparent)`,
                      color: currentConv.upHex,
                      border: `1px solid color-mix(in srgb, ${currentConv.upHex} 30%, transparent)`,
                    }}
                  >
                    LONG
                  </span>
                </div>
                <div className="font-mono text-[11px] text-foreground/90 mt-0.5">$64,280.50</div>
              </div>

              {/* 未實現盈虧（採用當前漲跌色） */}
              <div className="text-right">
                <span
                  className="font-mono text-xs font-bold block"
                  style={{ color: currentConv.upHex }}
                >
                  +1,280.00 USDT
                </span>
                <span
                  className="font-mono text-[10px] font-semibold"
                  style={{ color: currentConv.upHex }}
                >
                  +4.85%
                </span>
              </div>
            </div>

            {/* 強調色示範按鈕 */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded-lg px-2.5 py-1 text-xs font-semibold transition-all shadow-xs"
                style={{
                  backgroundColor: currentAccent.hex,
                  color: currentAccent.foreground,
                }}
              >
                Buy / 買入
              </button>
              <div className="flex items-center gap-1 font-mono text-[9.5px] text-muted-foreground bg-secondary/50 px-2 py-1 rounded">
                <span className="size-1.5 rounded-full bg-emerald-400" />
                <span>18ms WS</span>
              </div>
            </div>
          </div>
        </div>

        {/* ==================== 五大專業 Tab 切換標籤 ==================== */}
        <div className="flex border-b border-border/40 bg-secondary/20 px-6 pt-1 gap-2 text-xs font-medium overflow-x-auto shrink-0">
          {[
            { id: "presets", labelZh: "經典風格預設", icon: Zap },
            { id: "theme", labelZh: "作業系統外觀", icon: Palette },
            { id: "trading", labelZh: "看盤色彩與字號", icon: TrendingUp },
            { id: "identity", labelZh: "交易員身分", icon: User },
            { id: "api", labelZh: "交易所 API", icon: KeyRound },
          ].map(({ id, labelZh, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id as any)}
              className={cn(
                "flex items-center gap-1.5 border-b-2 px-3 py-2 transition-all shrink-0 cursor-pointer",
                activeTab === id
                  ? "border-primary text-foreground font-semibold"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="size-3.5" />
              <span>{labelZh}</span>
            </button>
          ))}
        </div>

        {/* ==================== Tab 滾動內容區 ==================== */}
        <div className="p-6 overflow-y-auto space-y-5 text-xs flex-1">
          
          {/* ========== TAB 1: 經典風格預設 (Presets) ========== */}
          {activeTab === "presets" && (
            <div className="space-y-4">
              <div>
                <h3 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <Zap className="size-3.5 text-primary" />
                  <span>傳奇量化主題套裝 (Legendary Quant Presets)</span>
                </h3>
                <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
                  一鍵套用業界頂級交易員調配之完整配置（含底座階調、介面強調色、漲跌色盤與字體排版）。
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {THEME_PRESETS.map((preset) => {
                  const pSurf = SURFACE_PALETTE[preset.surfaceTone];
                  const pAcc = ACCENT_PALETTE[preset.accentColor];
                  const pConv = COLOR_CONVENTIONS[preset.colorConvention];
                  const isCurrent =
                    surfaceTone === preset.surfaceTone &&
                    accentColor === preset.accentColor &&
                    colorConvention === preset.colorConvention;

                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => applyPreset(preset.id)}
                      className={cn(
                        "flex flex-col text-left p-3.5 rounded-xl border transition-all relative overflow-hidden group cursor-pointer",
                        isCurrent
                          ? "border-primary bg-primary/10 shadow-sm ring-1 ring-primary/40"
                          : "border-border/60 bg-secondary/30 hover:bg-secondary/60 hover:border-border"
                      )}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-semibold text-xs text-foreground group-hover:text-primary transition-colors">
                          {preset.nameZh}
                        </span>
                        <div className="flex items-center gap-1.5">
                          {/* 底座圓點 */}
                          <span
                            className="size-3 rounded-full border border-border/80 shadow-xs"
                            style={{ backgroundColor: pSurf.bg }}
                            title={pSurf.nameZh}
                          />
                          {/* 強調色光點 */}
                          <span
                            className="size-3 rounded-full shadow-xs"
                            style={{ backgroundColor: pAcc.hex }}
                            title={pAcc.nameZh}
                          />
                          {/* 漲跌色雙點 */}
                          <div className="flex -space-x-1">
                            <span className="size-2 rounded-full" style={{ backgroundColor: pConv.upHex }} />
                            <span className="size-2 rounded-full" style={{ backgroundColor: pConv.downHex }} />
                          </div>
                        </div>
                      </div>

                      <p className="text-[10px] text-muted-foreground leading-normal line-clamp-2">
                        {preset.descZh}
                      </p>

                      {isCurrent && (
                        <div className="mt-2 flex items-center gap-1 text-[10px] font-medium text-primary">
                          <Check className="size-3" />
                          <span>當前套用中</span>
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* ========== TAB 2: 作業系統外觀主題 (Appearance) ========== */}
          {activeTab === "theme" && (
            <div className="space-y-5">
              {/* 1. 作業系統底座風格 (Surface Tone - 6 款) */}
              <div className="rounded-xl border border-border/50 bg-secondary/25 p-4 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <Sparkles className="size-3.5 text-primary" />
                    <span>作業系統背景底座 (Surface Tone)</span>
                  </span>
                  <span className="font-mono text-[10px] text-primary font-semibold uppercase">
                    {surfaceTone}
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  作業系統全局視窗與側邊欄底階。OLED 純黑提供 0 反光暗房對比度，黑曜金與冷鈦灰兼具細緻沉浸感。
                </p>
                <div className="grid grid-cols-3 gap-2.5 pt-1">
                  {(Object.keys(SURFACE_PALETTE) as SurfaceTone[]).map((toneKey) => {
                    const item = SURFACE_PALETTE[toneKey];
                    return (
                      <button
                        key={toneKey}
                        type="button"
                        onClick={() => setSurfaceTone(toneKey)}
                        className={cn(
                          "flex items-center gap-2.5 rounded-xl p-2.5 border transition-all text-left cursor-pointer",
                          surfaceTone === toneKey
                            ? "border-primary bg-primary/10 text-foreground font-semibold shadow-xs ring-1 ring-primary/40"
                            : "border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                        )}
                      >
                        <span
                          className="size-5 rounded-full border border-border/80 shrink-0 shadow-xs"
                          style={{ backgroundColor: item.bg }}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] truncate text-foreground font-medium">{item.nameZh}</p>
                          <p className="text-[9.5px] text-muted-foreground truncate">{item.nameEn}</p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 2. 系統介面強調色 (Accent Highlight - 8 款鮮豔光色) */}
              <div className="rounded-xl border border-border/50 bg-secondary/25 p-4 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <Flame className="size-3.5 text-primary" />
                    <span>系統介面強調色 (Accent Highlight · 8 款光色)</span>
                  </span>
                  <span className="font-mono text-[10px] text-primary font-semibold uppercase">
                    {accentColor}
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  控制按鈕高亮、焦點環、選中狀態與主圖標光色。與 K 線漲跌色完全分離，互不干擾。
                </p>
                <div className="grid grid-cols-4 gap-2 pt-1">
                  {(Object.keys(ACCENT_PALETTE) as AccentColor[]).map((accKey) => {
                    const item = ACCENT_PALETTE[accKey];
                    return (
                      <button
                        key={accKey}
                        type="button"
                        onClick={() => setAccentColor(accKey)}
                        className={cn(
                          "flex items-center justify-center gap-2 rounded-lg py-2 px-1 border transition-all cursor-pointer",
                          accentColor === accKey
                            ? "border-primary bg-primary/15 text-foreground font-semibold shadow-xs ring-1 ring-primary/40"
                            : "border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                        )}
                      >
                        <span className="size-2.5 rounded-full shrink-0" style={{ backgroundColor: item.hex }} />
                        <span className="text-[11px] truncate">{item.nameZh}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 3. 字體家族風格 (Typography Family - 4 款) */}
              <div className="rounded-xl border border-border/50 bg-secondary/25 p-4 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <Type className="size-3.5 text-primary" />
                    <span>字體家族風格 (Typography Family)</span>
                  </span>
                  <span className="font-mono text-[10px] text-primary font-semibold uppercase">
                    {fontFamily}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2.5 pt-1">
                  {(Object.keys(FONT_FAMILIES) as FontFamily[]).map((fKey) => {
                    const item = FONT_FAMILIES[fKey];
                    return (
                      <button
                        key={fKey}
                        type="button"
                        onClick={() => setFontFamily(fKey)}
                        className={cn(
                          "p-2.5 rounded-xl border text-left transition-all cursor-pointer",
                          fontFamily === fKey
                            ? "border-primary bg-primary/10 text-foreground font-semibold shadow-xs"
                            : "border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground"
                        )}
                      >
                        <p className="text-xs text-foreground font-medium">{item.nameZh}</p>
                        <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1">{item.descZh}</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* ========== TAB 3: 金融看盤色彩與字號密度 (Trading Ergonomics) ========== */}
          {activeTab === "trading" && (
            <div className="space-y-5">
              {/* 1. 漲跌色彩慣例 (與系統主題完全正交獨立！) */}
              <div className="rounded-xl border border-border/50 bg-secondary/25 p-4 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <TrendingUp className="size-3.5 text-up" />
                    <span className="font-semibold">漲跌色彩慣例 (Price Trend Conventions)</span>
                  </span>
                  <span className="font-mono text-[10px] text-up font-bold">
                    {currentConv.nameZh.split(" ")[0]}
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  【金融語意完全獨立】：量化交易員的核心肌肉記憶。切換後全站持倉、損益、走勢線與多空標籤即刻翻轉，與作業系統外觀主題完全獨立。
                </p>
                <div className="grid grid-cols-2 gap-3 pt-1">
                  {(Object.keys(COLOR_CONVENTIONS) as ColorConvention[]).map((convKey) => {
                    const item = COLOR_CONVENTIONS[convKey];
                    const isSelected = colorConvention === convKey;
                    return (
                      <button
                        key={convKey}
                        type="button"
                        onClick={() => setColorConvention(convKey)}
                        className={cn(
                          "flex items-center justify-between p-3 rounded-xl border transition-all text-left cursor-pointer",
                          isSelected
                            ? "border-primary bg-primary/10 text-foreground font-semibold shadow-xs ring-1 ring-primary/40"
                            : "border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                        )}
                      >
                        <div className="min-w-0 pr-2">
                          <p className="text-xs font-semibold text-foreground truncate">{item.nameZh}</p>
                          <p className="text-[9.5px] text-muted-foreground mt-0.5 line-clamp-1">{item.descZh}</p>
                        </div>
                        <div className="flex items-center gap-1.5 font-mono text-xs shrink-0 font-bold">
                          <span style={{ color: item.upHex }}>+12%</span>
                          <span style={{ color: item.downHex }}>-8%</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 2. 數據密度與字體縮放 (5 檔調節 · 真正驅動全站內容數據) */}
              <div className="rounded-xl border border-border/50 bg-secondary/25 p-4 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <Monitor className="size-3.5 text-primary" />
                    <span>數據密度與字號縮放 (Layout Density & Scale · 5 檔)</span>
                  </span>
                  <span className="font-mono text-[10px] text-primary font-bold">
                    {currentScale.nameZh}
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  【內容與數字全面連動】：不僅改變標題，報價、持倉表格、成交明細與時間戳等所有數據一律成比例放大縮小。
                </p>
                <div className="grid grid-cols-5 gap-2 pt-1">
                  {(Object.keys(FONT_SCALES) as FontScale[]).map((scaleKey) => {
                    const item = FONT_SCALES[scaleKey];
                    const isSelected = fontScale === scaleKey;
                    return (
                      <button
                        key={scaleKey}
                        type="button"
                        onClick={() => setFontScale(scaleKey)}
                        className={cn(
                          "flex flex-col items-center gap-1 py-2 px-1 rounded-xl border text-center transition-all cursor-pointer",
                          isSelected
                            ? "border-primary bg-primary/15 text-foreground font-semibold shadow-xs ring-1 ring-primary/40"
                            : "border-border/60 bg-secondary/40 text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                        )}
                        title={item.descZh}
                      >
                        <span className="text-xs font-medium">{item.nameZh.split(" ")[0]}</span>
                        <span className="text-[9px] text-muted-foreground truncate w-full">{item.nameZh.split(" ")[1]}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* ========== TAB 4: 交易員身分 (Identity) ========== */}
          {activeTab === "identity" && (
            <form onSubmit={handleSaveIdentity} className="space-y-4">
              <div>
                <label className="block text-[11px] font-medium text-foreground mb-2">
                  {language === "zh-TW" ? "專屬交易員頭像 (Avatar Emoji)" : "Select Avatar Emoji"}
                </label>
                <div className="grid grid-cols-8 gap-2">
                  {AVATAR_OPTIONS.map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => setAvatar(opt)}
                      className={cn(
                        "grid size-11 place-items-center text-xl rounded-xl border transition-all cursor-pointer",
                        avatar === opt
                          ? "border-primary bg-primary/15 shadow-sm scale-105"
                          : "border-border/60 bg-secondary/30 hover:bg-secondary/60 hover:scale-105"
                      )}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="block text-[11px] font-medium text-foreground">
                    {language === "zh-TW" ? "交易員暱稱 (Display Name)" : "Trader Nickname"}
                  </label>
                  <input
                    type="text"
                    value={nameInput}
                    onChange={(e) => setNameInput(e.target.value)}
                    className="w-full rounded-lg border border-border/60 bg-background/80 px-3 py-2 text-xs text-foreground focus:outline-none focus:border-primary"
                    placeholder="例如: Min Yi / Alpha Trader"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="block text-[11px] font-medium text-foreground">
                    {language === "zh-TW" ? "OKX 專用子帳戶識別別名" : "Sub-Account Alias"}
                  </label>
                  <input
                    type="text"
                    value={aliasInput}
                    onChange={(e) => setAliasInput(e.target.value)}
                    className="w-full rounded-lg border border-border/60 bg-background/80 px-3 py-2 text-xs text-foreground font-mono focus:outline-none focus:border-primary"
                    placeholder="例如: OKX-SWAP-01"
                  />
                </div>
              </div>

              {/* 身分尊榮徽章 */}
              <div className="space-y-1.5">
                <label className="block text-[11px] font-medium text-foreground">
                  {language === "zh-TW" ? "交易所交易身分徽章" : "Trader Badge Tier"}
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {BADGE_OPTIONS.map((badge) => (
                    <button
                      key={badge}
                      type="button"
                      onClick={() => setTraderBadge(badge)}
                      className={cn(
                        "rounded-lg py-1.5 text-center font-mono text-[10px] border transition-all cursor-pointer",
                        traderBadge === badge
                          ? "border-primary bg-primary/10 text-foreground font-semibold shadow-xs"
                          : "border-border/50 bg-secondary/40 text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {badge}
                    </button>
                  ))}
                </div>
              </div>

              <div className="pt-2 flex items-center justify-between border-t border-border/40">
                <span className="text-[10px] text-muted-foreground">
                  {language === "zh-TW" ? "專屬設定僅保存在本機，全站側邊欄即時同步" : "Saved locally on this machine"}
                </span>
                <button
                  type="submit"
                  className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 font-medium text-xs text-primary-foreground hover:bg-primary/90 transition-colors shadow-xs cursor-pointer"
                >
                  {savedToast ? <Check className="size-3.5" /> : null}
                  <span>{savedToast ? (language === "zh-TW" ? "已儲存！" : "Saved!") : (language === "zh-TW" ? "儲存身分變更" : "Save Identity")}</span>
                </button>
              </div>
            </form>
          )}

          {/* ========== TAB 5: 交易所 API 與本地進程 (API & Daemon) ========== */}
          {activeTab === "api" && (
            <div className="space-y-4">
              <div className="rounded-xl border border-border/50 bg-secondary/25 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <ShieldCheck className="size-3.5 text-emerald-400" />
                    <span>OKX 專用子帳戶金鑰連線</span>
                  </span>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => setEnvironment("live")}
                      className={cn(
                        "rounded px-2 py-0.5 text-[10px] font-mono transition-all cursor-pointer",
                        environment === "live"
                          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 font-semibold"
                          : "text-muted-foreground hover:text-foreground"
                      )}
                    >
                      LIVE 實盤
                    </button>
                    <button
                      type="button"
                      onClick={() => setEnvironment("sim")}
                      className={cn(
                        "rounded px-2 py-0.5 text-[10px] font-mono transition-all cursor-pointer",
                        environment === "sim"
                          ? "bg-amber-500/20 text-amber-400 border border-amber-500/40 font-semibold"
                          : "text-muted-foreground hover:text-foreground"
                      )}
                    >
                      SIM 模擬
                    </button>
                  </div>
                </div>

                <div className="space-y-2">
                  <div>
                    <label className="text-[10px] text-muted-foreground font-mono">OKX API Key</label>
                    <input
                      type="text"
                      readOnly
                      value={apiKey}
                      className="w-full mt-1 rounded-lg border border-border/60 bg-background/80 px-3 py-1.5 font-mono text-[11px] text-foreground/80 focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="text-[10px] text-muted-foreground font-mono">Passphrase</label>
                    <input
                      type="password"
                      readOnly
                      value={passphrase}
                      className="w-full mt-1 rounded-lg border border-border/60 bg-background/80 px-3 py-1.5 font-mono text-[11px] text-foreground/80 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* 本地 WebSocket 守護進程診斷 */}
              <div className="rounded-xl border border-border/50 bg-secondary/25 p-4 space-y-2">
                <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <Activity className="size-3.5 text-primary" />
                  <span>本地守護進程連線狀態 (Local Daemon)</span>
                </span>
                <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-[10.5px]">
                  <div className="rounded-lg bg-background/60 p-2.5 border border-border/40">
                    <span className="text-[9.5px] text-muted-foreground block">WS 延遲 (Ping)</span>
                    <span className="text-emerald-400 font-bold">{ping} ms</span>
                  </div>
                  <div className="rounded-lg bg-background/60 p-2.5 border border-border/40">
                    <span className="text-[9.5px] text-muted-foreground block">資料儲存底座</span>
                    <span className="text-foreground truncate block font-bold">SQLite (WAL)</span>
                  </div>
                  <div className="rounded-lg bg-background/60 p-2.5 border border-border/40">
                    <span className="text-[9.5px] text-muted-foreground block">本地服務埠</span>
                    <span className="text-foreground font-bold">127.0.0.1:8770</span>
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>

        {/* ==================== 底部固定列 ==================== */}
        <footer className="flex items-center justify-between border-t border-border/50 px-6 py-3 bg-secondary/20 shrink-0">
          <span className="text-[10px] text-muted-foreground">
            catOS Personal Trading OS · 所有偏好即時同步本機 Storage
          </span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors shadow-xs cursor-pointer"
          >
            {language === "zh-TW" ? "完成設定" : "Done"}
          </button>
        </footer>

      </div>
    </div>
  );
}
