import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import {
  X,
  Sparkles,
  Timer,
  Clock,
  TrendingUp,
  FolderKanban,
  LayoutGrid,
  Check,
  Plus,
  Trash2,
  RotateCcw,
  Layers,
  SlidersHorizontal,
} from "lucide-react";
import { useLayoutStore, type CardId, type LayoutPresetId } from "@/state/layoutStore";
import {
  useHeaderWidgetStore,
  POPULAR_SWAP_SYMBOLS,
  type BarTimeframe,
} from "@/state/microWidgetStore";
import { getAllLeaves } from "@/lib/layout-tree/tree-ops";
import { ALL_CARDS } from "./card-registry";
import { cn } from "@/lib/utils";

interface WidgetGalleryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

const SYSTEM_PRESETS: {
  id: LayoutPresetId;
  name: string;
  tag: string;
  cardsCount: number;
  desc: string;
}[] = [
  {
    id: "tsplit",
    name: "5 卡標準戰情",
    tag: "出廠推薦",
    cardsCount: 5,
    desc: "上下 T-Split 佈局，核心策略與持倉並行監控 (經典定案)",
  },
  {
    id: "full9",
    name: "5 卡全景大盤",
    tag: "完整大盤",
    cardsCount: 5,
    desc: "全景展開版面，極大化可視資訊密度",
  },
  {
    id: "quad",
    name: "4 卡雙欄象限",
    tag: "經典對稱",
    cardsCount: 4,
    desc: "左右對稱雙欄四象限排版，適合雙螢幕或超寬屏",
  },
  {
    id: "focus_positions",
    name: "部位防線專注",
    tag: "單卡滿版",
    cardsCount: 1,
    desc: "100% 滿版展示多空持倉、在途掛單撤單與 P6 災難停損防線",
  },
];

/**
 * CatOS 統一工作區與模組工坊 (Workspace & Module Hub) - iOS 液態半透明（Frosted Glass）版本
 * - 仿 iOS Control Center / Widget Gallery 半透明磨砂玻璃質感
 * - 螢幕右側非侵入懸浮式滑出，左側儀表板保持 100% 可視與即時重排 (Live WYSIWYG)
 * - 深度整合「工作區設定檔 (Workspaces)」、「版面大卡 (Cards)」與「頂部狀態列 (Header)」
 * - 徹底消除頂部按鈕雙重冗餘，收斂為單一零浪費控制中心
 */
export function WidgetGalleryDrawer({ isOpen, onClose }: WidgetGalleryDrawerProps) {
  const [activeTab, setActiveTab] = useState<"profiles" | "workspace" | "header">("profiles");
  const [customSymbolInput, setCustomSymbolInput] = useState("");
  const [isSavingNew, setIsSavingNew] = useState(false);
  const [newProfileName, setNewProfileName] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);

  const {
    rootNode,
    toggleCardStable,
    applyLayoutPreset,
    profiles,
    currentProfileId,
    applyProfile,
    saveNewProfile,
    deleteProfile,
  } = useLayoutStore();

  const activeProfile = profiles.find((p) => p.id === currentProfileId) || profiles[0];
  const customProfiles = profiles.filter((p) => !p.isSystem);
  const currentLeaves = getAllLeaves(rootNode);
  const activeCardIds = currentLeaves.map((l) => l.cardId);

  // 頂部狀態列微模組 Store
  const {
    klineClockMounted,
    setKlineClockMounted,
    klineTimeframe,
    setKlineTimeframe,
    fundingClockMounted,
    setFundingClockMounted,
    marketTapeMounted,
    setMarketTapeMounted,
    marketTapeMode,
    setMarketTapeMode,
    addCustomSymbol,
    removeCustomSymbol,
    getActiveSymbols,
  } = useHeaderWidgetStore();

  const mountedHeaderCount =
    (klineClockMounted ? 1 : 0) + (fundingClockMounted ? 1 : 0) + (marketTapeMounted ? 1 : 0);
  const totalMountedCount = currentLeaves.length + mountedHeaderCount;
  const totalAvailableModules = ALL_CARDS.length + 3;

  // 快捷鍵 ESC 關閉
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // 切換大卡掛載狀態 (槽位恆定，絕不隨機移位)
  const handleToggleCard = (cardId: CardId) => {
    toggleCardStable(cardId);
  };

  const handleAddCustomSymbol = () => {
    if (!customSymbolInput.trim()) return;
    addCustomSymbol(customSymbolInput);
    setCustomSymbolInput("");
  };

  const handleSaveSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProfileName.trim()) return;
    saveNewProfile(newProfileName.trim());
    setNewProfileName("");
    setIsSavingNew(false);
  };

  if (!isOpen || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-[120] pointer-events-auto">
      {/* 輕量半透明遮罩 (點擊空白處自動收合，主畫面卡片完全可見) */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-black/20 backdrop-blur-[2px] transition-opacity cursor-pointer animate-in fade-in duration-200"
      />

      {/* iOS 半透明磨砂浮動控制面板 (Frosted Glass Panel) */}
      <div
        ref={panelRef}
        className="fixed top-3 bottom-3 right-3 w-[410px] max-w-[calc(100vw-24px)] z-10 flex flex-col rounded-2xl overflow-hidden select-none animate-in slide-in-from-right-8 duration-200 ease-out border border-white/[0.14] bg-[#0c0e14]/75 backdrop-blur-2xl shadow-[0_32px_80px_rgba(0,0,0,0.7),inset_0_1px_1px_rgba(255,255,255,0.18)]"
        style={{
          WebkitBackdropFilter: "blur(32px) saturate(180%)",
          backdropFilter: "blur(32px) saturate(180%)",
        }}
      >
        {/* 1. macOS / iOS 風格頂部控制中心標題列 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.08] bg-white/[0.02] shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="size-7 rounded-lg bg-primary/20 border border-primary/30 flex items-center justify-center text-primary shadow-[0_0_10px_rgba(232,180,94,0.2)]">
              <SlidersHorizontal className="size-3.5" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm tracking-tight text-foreground font-sans">
                  控制中心
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-primary/15 text-primary border border-primary/30 font-semibold">
                  {activeProfile?.shortName || activeProfile?.name || "預設排版"}
                </span>
              </div>
              <span className="text-[9.5px] font-mono text-muted-foreground/75 leading-tight mt-0.5">
                {totalMountedCount}/{totalAvailableModules} 組件運行中
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="size-7 rounded-full bg-white/[0.08] hover:bg-white/[0.18] text-muted-foreground hover:text-foreground transition-all grid place-items-center cursor-pointer border border-white/[0.08]"
            title="關閉控制中心 (ESC)"
          >
            <X className="size-3.5" />
          </button>
        </div>

        {/* 2. iOS 膠囊分段控制器 (Segmented Control) */}
        <div className="p-3 pb-2 shrink-0">
          <div className="flex items-center p-1 rounded-xl bg-black/40 border border-white/[0.08] text-[11px] font-sans font-medium gap-1">
            <button
              type="button"
              onClick={() => setActiveTab("profiles")}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg transition-all cursor-pointer",
                activeTab === "profiles"
                  ? "bg-white/[0.15] text-foreground font-semibold shadow-xs border border-white/[0.12]"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <FolderKanban className="size-3 text-primary" />
              <span>工作區設定</span>
              <span className="text-[9.5px] font-mono px-1 rounded bg-black/30 text-primary">
                {profiles.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("workspace")}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg transition-all cursor-pointer",
                activeTab === "workspace"
                  ? "bg-white/[0.15] text-foreground font-semibold shadow-xs border border-white/[0.12]"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <LayoutGrid className="size-3 text-emerald-400" />
              <span>版面大卡</span>
              <span className="text-[9.5px] font-mono px-1 rounded bg-black/30 text-emerald-400">
                {currentLeaves.length}/5
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("header")}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg transition-all cursor-pointer",
                activeTab === "header"
                  ? "bg-white/[0.15] text-foreground font-semibold shadow-xs border border-white/[0.12]"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Timer className="size-3 text-amber-400" />
              <span>頂部狀態列</span>
              <span className="text-[9.5px] font-mono px-1 rounded bg-black/30 text-amber-400">
                {mountedHeaderCount}/3
              </span>
            </button>
          </div>
        </div>

        {/* 3. 模組內容區域 */}
        <div className="flex-1 min-h-0 overflow-y-auto px-3 pb-3 space-y-2.5">
          {/* ================================================= */}
          {/* TAB 1: 工作區設定檔 (Workspaces & Presets) */}
          {/* ================================================= */}
          {activeTab === "profiles" && (
            <div className="space-y-3">
              {/* 自訂工作區清單與另存 */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between px-1 text-[10.5px] font-mono text-muted-foreground/80">
                  <span className="flex items-center gap-1 font-semibold text-foreground/90 font-sans">
                    <Sparkles className="size-3 text-amber-400" />
                    我的自訂工作區
                  </span>
                  <span className="text-primary font-mono text-[10px]">
                    {customProfiles.length} 個配置
                  </span>
                </div>

                {customProfiles.length > 0 ? (
                  <div className="space-y-1 max-h-[160px] overflow-y-auto pr-0.5">
                    {customProfiles.map((p) => {
                      const isCurrent = p.id === currentProfileId;
                      return (
                        <div
                          key={p.id}
                          onClick={() => applyProfile(p.id)}
                          className={cn(
                            "p-2.5 rounded-xl border transition-all flex items-center justify-between gap-2 cursor-pointer group",
                            isCurrent
                              ? "bg-primary/15 border-primary/40 text-primary shadow-xs"
                              : "bg-white/[0.03] border-white/[0.08] hover:bg-white/[0.07] text-foreground"
                          )}
                        >
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <Sparkles
                              className={cn(
                                "size-3.5 shrink-0",
                                isCurrent ? "text-primary" : "text-amber-400"
                              )}
                            />
                            <span className="text-xs font-semibold tracking-tight truncate">
                              {p.name}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5 shrink-0">
                            {isCurrent && (
                              <span className="flex items-center gap-1 text-[10px] font-mono text-primary font-bold">
                                <Check className="size-3" /> 當前
                              </span>
                            )}
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                deleteProfile(p.id);
                              }}
                              className="opacity-0 group-hover:opacity-100 p-1 rounded text-muted-foreground hover:text-rose-400 hover:bg-rose-400/10 transition-all cursor-pointer"
                              title="刪除此自訂版面"
                            >
                              <Trash2 className="size-3" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="p-2.5 rounded-xl border border-dashed border-white/[0.1] bg-white/[0.01] text-center text-[10.5px] text-muted-foreground font-mono">
                    尚未保存自訂工作區，點擊下方「另存當前排版」即可持久化目前視窗。
                  </div>
                )}

                {/* 另存當前排版 */}
                <div className="pt-1">
                  {isSavingNew ? (
                    <form
                      onSubmit={handleSaveSubmit}
                      className="p-2.5 rounded-xl bg-black/40 border border-primary/40 flex flex-col gap-2"
                    >
                      <input
                        type="text"
                        autoFocus
                        value={newProfileName}
                        onChange={(e) => setNewProfileName(e.target.value)}
                        placeholder="輸入新工作區名稱 (例如: 趨勢波段 3螢幕)..."
                        className="w-full px-2.5 py-1.5 rounded-lg bg-white/[0.06] border border-white/[0.12] text-xs font-mono focus:outline-none focus:border-primary text-foreground"
                      />
                      <div className="flex items-center justify-end gap-1.5 font-mono text-[10.5px]">
                        <button
                          type="button"
                          onClick={() => setIsSavingNew(false)}
                          className="px-2.5 py-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-white/[0.06]"
                        >
                          取消
                        </button>
                        <button
                          type="submit"
                          disabled={!newProfileName.trim()}
                          className="px-3 py-1 rounded-md bg-primary text-primary-foreground font-semibold disabled:opacity-50 hover:bg-primary/90 cursor-pointer shadow-xs"
                        >
                          保存配置
                        </button>
                      </div>
                    </form>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setIsSavingNew(true)}
                      className="w-full py-1.5 px-2.5 rounded-xl border border-dashed border-primary/40 bg-primary/5 hover:bg-primary/10 text-primary hover:border-primary text-[11px] font-mono font-medium flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                    >
                      <Plus className="size-3.5" />
                      <span>另存當前排版為自訂工作區...</span>
                    </button>
                  )}
                </div>
              </div>

              {/* 系統出廠推薦佈局 */}
              <div className="space-y-1.5 pt-2 border-t border-white/[0.08]">
                <div className="flex items-center justify-between px-1 text-[10.5px] font-mono text-muted-foreground/80">
                  <span className="flex items-center gap-1 font-semibold text-foreground/90 font-sans">
                    <Layers className="size-3 text-primary" />
                    系統內建佈局
                  </span>
                  <span className="text-[10px] text-muted-foreground font-mono">一鍵套用</span>
                </div>

                <div className="space-y-1.5">
                  {SYSTEM_PRESETS.map((p) => {
                    const isSelected =
                      (activeProfile?.id === "layout_tsplit_v1_core" && p.id === "tsplit") ||
                      activeProfile?.name?.includes(p.name);

                    return (
                      <div
                        key={p.id}
                        onClick={() => applyLayoutPreset(p.id)}
                        className={cn(
                          "p-3 rounded-xl border transition-all cursor-pointer flex items-center justify-between group",
                          isSelected
                            ? "bg-primary/15 border-primary/40 text-primary shadow-xs"
                            : "bg-white/[0.03] border-white/[0.08] hover:bg-white/[0.07] text-foreground"
                        )}
                      >
                        <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold tracking-tight group-hover:text-primary transition-colors">
                              {p.name}
                            </span>
                            <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-primary/15 text-primary border border-primary/30">
                              {p.tag}
                            </span>
                            <span className="text-[9.5px] font-mono text-muted-foreground">
                              {p.cardsCount} 卡
                            </span>
                          </div>
                          <p className="text-[10.5px] text-muted-foreground leading-tight font-sans mt-0.5">
                            {p.desc}
                          </p>
                        </div>

                        <div className="flex items-center gap-1.5 shrink-0 ml-2">
                          {isSelected ? (
                            <span className="flex items-center gap-1 text-[10.5px] font-mono text-primary font-bold px-2 py-1 rounded-lg bg-primary/20 border border-primary/30">
                              <Check className="size-3" /> 使用中
                            </span>
                          ) : (
                            <button
                              type="button"
                              className="px-2.5 py-1 rounded-lg text-[10.5px] font-mono font-semibold bg-white/[0.08] text-foreground border border-white/[0.1] group-hover:bg-primary group-hover:text-primary-foreground group-hover:border-primary transition-all"
                            >
                              套用
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* ================================================= */}
          {/* TAB 2: 工作區版面大卡 (即時開關，左側大盤同步伸縮) */}
          {/* ================================================= */}
          {activeTab === "workspace" && (
            <div className="space-y-2">
              <div className="flex items-center justify-between px-1 text-[10.5px] font-mono text-muted-foreground/75">
                <span>點擊切換開關 · 左側儀表板即時響應</span>
                <span>{currentLeaves.length} 張開啟</span>
              </div>

              <div className="space-y-1.5">
                {ALL_CARDS.map((card) => {
                  const isMounted = activeCardIds.includes(card.id);
                  const Icon = card.icon;

                  return (
                    <div
                      key={card.id}
                      className={cn(
                        "p-3 rounded-xl border transition-all flex items-center justify-between gap-3 group",
                        isMounted
                          ? "bg-white/[0.05] border-white/[0.14] shadow-xs"
                          : "bg-white/[0.02] border-white/[0.06] opacity-75 hover:opacity-100"
                      )}
                    >
                      {/* 圖標與名稱 */}
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div
                          className={cn(
                            "size-8 rounded-lg border flex items-center justify-center shrink-0 transition-colors",
                            isMounted
                              ? "bg-primary/20 border-primary/40 text-primary"
                              : "bg-white/[0.04] border-white/[0.08] text-muted-foreground"
                          )}
                        >
                          <Icon className="size-4" />
                        </div>

                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-semibold text-foreground tracking-tight truncate">
                              {card.nameZh}
                            </span>
                            <span className="text-[9px] font-mono px-1 rounded bg-black/40 text-muted-foreground/80 border border-white/[0.06]">
                              {card.category}
                            </span>
                          </div>
                          <p className="text-[10px] text-muted-foreground/80 leading-tight truncate mt-0.5 font-sans">
                            {card.desc}
                          </p>
                        </div>
                      </div>

                      {/* iOS 開關 (iOS Toggle Switch) */}
                      <button
                        type="button"
                        onClick={() => handleToggleCard(card.id)}
                        className={cn(
                          "w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 p-0.5 border border-white/[0.1]",
                          isMounted
                            ? "bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.35)]"
                            : "bg-white/[0.12] hover:bg-white/[0.18]"
                        )}
                        title={isMounted ? "點擊卸載卡片" : "點擊掛載至工作區"}
                      >
                        <div
                          className={cn(
                            "size-4.5 rounded-full bg-white shadow-md transition-transform duration-200",
                            isMounted ? "translate-x-5" : "translate-x-0"
                          )}
                        />
                      </button>
                    </div>
                  );
                })}
              </div>

              {/* 底部輔助說明 */}
              <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.06] text-[10px] text-muted-foreground leading-relaxed font-sans">
                💡 採用無縫 T-Split 佈局樹，卡片增減時背景畫面將保持 120 FPS 彈性重排，關閉任何卡片皆不影響底層策略與風控運作。
              </div>
            </div>
          )}

          {/* ================================================= */}
          {/* TAB 3: 頂部狀態列微模組 (K線時鐘、8H資金費、自選行情總線) */}
          {/* ================================================= */}
          {activeTab === "header" && (
            <div className="space-y-2.5">
              {/* 1. K 線收盤倒數時鐘 */}
              <div
                className={cn(
                  "p-3 rounded-xl border transition-all flex flex-col gap-2.5",
                  klineClockMounted
                    ? "bg-white/[0.05] border-white/[0.14] shadow-xs"
                    : "bg-white/[0.02] border-white/[0.06] opacity-75"
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div
                      className={cn(
                        "size-8 rounded-lg border flex items-center justify-center shrink-0",
                        klineClockMounted
                          ? "bg-primary/20 border-primary/40 text-primary"
                          : "bg-white/[0.04] border-white/[0.08] text-muted-foreground"
                      )}
                    >
                      <Timer className="size-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-semibold text-foreground">
                          K 線收盤倒數時鐘
                        </span>
                        <span className="text-[9px] font-mono px-1 rounded bg-black/40 text-primary border border-primary/30">
                          閉合信號
                        </span>
                      </div>
                      <p className="text-[10px] text-muted-foreground leading-tight mt-0.5">
                        分鐘／小時級收盤倒數與呼吸進度條
                      </p>
                    </div>
                  </div>

                  {/* iOS Toggle Switch */}
                  <button
                    type="button"
                    onClick={() => setKlineClockMounted(!klineClockMounted)}
                    className={cn(
                      "w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 p-0.5 border border-white/[0.1]",
                      klineClockMounted
                        ? "bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.35)]"
                        : "bg-white/[0.12] hover:bg-white/[0.18]"
                    )}
                  >
                    <div
                      className={cn(
                        "size-4.5 rounded-full bg-white shadow-md transition-transform duration-200",
                        klineClockMounted ? "translate-x-5" : "translate-x-0"
                      )}
                    />
                  </button>
                </div>

                {/* 週期切換 (iOS 膠囊樣式) */}
                {klineClockMounted && (
                  <div className="flex items-center justify-between p-2 rounded-lg bg-black/30 border border-white/[0.06] text-[10.5px]">
                    <span className="text-muted-foreground font-mono text-[10px]">倒數基準週期:</span>
                    <div className="flex items-center gap-1">
                      {(["15m", "1H", "4H"] as BarTimeframe[]).map((tf) => (
                        <button
                          key={tf}
                          type="button"
                          onClick={() => setKlineTimeframe(tf)}
                          className={cn(
                            "px-2.5 py-0.5 rounded-md text-[10px] font-mono cursor-pointer transition-colors border",
                            klineTimeframe === tf
                              ? "bg-primary text-primary-foreground font-bold border-primary shadow-xs"
                              : "border-transparent bg-white/[0.06] text-muted-foreground hover:text-foreground"
                          )}
                        >
                          {tf}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* 2. 8H 資金費結算時鐘 */}
              <div
                className={cn(
                  "p-3 rounded-xl border transition-all flex items-center justify-between gap-3",
                  fundingClockMounted
                    ? "bg-white/[0.05] border-white/[0.14] shadow-xs"
                    : "bg-white/[0.02] border-white/[0.06] opacity-75"
                )}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div
                    className={cn(
                      "size-8 rounded-lg border flex items-center justify-center shrink-0",
                      fundingClockMounted
                        ? "bg-primary/20 border-primary/40 text-primary"
                        : "bg-white/[0.04] border-white/[0.08] text-muted-foreground"
                    )}
                  >
                    <Clock className="size-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs font-semibold text-foreground">
                        8H 資金費結算時鐘
                      </span>
                      <span className="text-[9px] font-mono px-1 rounded bg-black/40 text-muted-foreground border border-white/[0.06]">
                        UTC 切日
                      </span>
                    </div>
                    <p className="text-[10px] text-muted-foreground leading-tight mt-0.5">
                      OKX 永續 8H 費率結算倒數 (00/08/16 UTC)
                    </p>
                  </div>
                </div>

                {/* iOS Toggle Switch */}
                <button
                  type="button"
                  onClick={() => setFundingClockMounted(!fundingClockMounted)}
                  className={cn(
                    "w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 p-0.5 border border-white/[0.1]",
                    fundingClockMounted
                      ? "bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.35)]"
                      : "bg-white/[0.12] hover:bg-white/[0.18]"
                  )}
                >
                  <div
                    className={cn(
                      "size-4.5 rounded-full bg-white shadow-md transition-transform duration-200",
                      fundingClockMounted ? "translate-x-5" : "translate-x-0"
                    )}
                  />
                </button>
              </div>

              {/* 3. 自選標的行情總線 (支援自選標的池與自動跟隨) */}
              <div
                className={cn(
                  "p-3 rounded-xl border transition-all flex flex-col gap-2.5",
                  marketTapeMounted
                    ? "bg-white/[0.05] border-white/[0.14] shadow-xs"
                    : "bg-white/[0.02] border-white/[0.06] opacity-75"
                )}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div
                      className={cn(
                        "size-8 rounded-lg border flex items-center justify-center shrink-0",
                        marketTapeMounted
                          ? "bg-primary/20 border-primary/40 text-primary"
                          : "bg-white/[0.04] border-white/[0.08] text-muted-foreground"
                      )}
                    >
                      <TrendingUp className="size-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-semibold text-foreground">
                          自選標的行情總線
                        </span>
                        <span className="text-[9px] font-mono px-1 rounded bg-black/40 text-primary border border-primary/30">
                          動態標的池
                        </span>
                      </div>
                      <p className="text-[10px] text-muted-foreground leading-tight mt-0.5">
                        頂部標記價格、跳動指示與 24H 漲跌總線
                      </p>
                    </div>
                  </div>

                  {/* iOS Toggle Switch */}
                  <button
                    type="button"
                    onClick={() => setMarketTapeMounted(!marketTapeMounted)}
                    className={cn(
                      "w-11 h-6 rounded-full transition-colors relative cursor-pointer shrink-0 p-0.5 border border-white/[0.1]",
                      marketTapeMounted
                        ? "bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.35)]"
                        : "bg-white/[0.12] hover:bg-white/[0.18]"
                    )}
                  >
                    <div
                      className={cn(
                        "size-4.5 rounded-full bg-white shadow-md transition-transform duration-200",
                        marketTapeMounted ? "translate-x-5" : "translate-x-0"
                      )}
                    />
                  </button>
                </div>

                {/* 模式切換與自選幣種管理 */}
                {marketTapeMounted && (
                  <div className="p-2.5 rounded-xl bg-black/35 border border-white/[0.06] flex flex-col gap-2">
                    <div className="flex items-center justify-between text-[10.5px] font-mono">
                      <span className="text-muted-foreground">行情投影來源:</span>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => setMarketTapeMode("auto")}
                          className={cn(
                            "px-2 py-0.5 rounded-md text-[10px] font-mono cursor-pointer transition-colors border",
                            marketTapeMode === "auto"
                              ? "bg-primary text-primary-foreground font-bold border-primary shadow-xs"
                              : "border-transparent bg-white/[0.06] text-muted-foreground hover:text-foreground"
                          )}
                        >
                          自動跟隨策略
                        </button>
                        <button
                          type="button"
                          onClick={() => setMarketTapeMode("custom")}
                          className={cn(
                            "px-2 py-0.5 rounded-md text-[10px] font-mono cursor-pointer transition-colors border",
                            marketTapeMode === "custom"
                              ? "bg-primary text-primary-foreground font-bold border-primary shadow-xs"
                              : "border-transparent bg-white/[0.06] text-muted-foreground hover:text-foreground"
                          )}
                        >
                          自選標的池
                        </button>
                      </div>
                    </div>

                    {/* 標的標籤列表 */}
                    <div className="flex flex-col gap-1.5 pt-1 border-t border-white/[0.06]">
                      <div className="flex items-center justify-between text-[10px] font-mono text-muted-foreground">
                        <span>
                          {marketTapeMode === "auto" ? "當前活躍 Bot 標的:" : "自選監控標的 (點擊 × 移除):"}
                        </span>
                        {marketTapeMode === "auto" && (
                          <span className="text-[9px] text-primary/80">跟隨運作中策略</span>
                        )}
                      </div>

                      <div className="flex items-center gap-1.5 flex-wrap">
                        {getActiveSymbols().map((sym) => (
                          <span
                            key={sym}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg bg-white/[0.08] border border-white/[0.1] text-[10.5px] font-mono text-foreground font-bold"
                          >
                            <span>{sym}</span>
                            {marketTapeMode === "custom" && (
                              <button
                                type="button"
                                onClick={() => removeCustomSymbol(sym)}
                                className="size-3.5 rounded hover:bg-rose-500/20 hover:text-rose-400 grid place-items-center cursor-pointer ml-0.5"
                                title={`移除 ${sym}`}
                              >
                                <X className="size-2.5" />
                              </button>
                            )}
                          </span>
                        ))}
                      </div>

                      {/* 輸入新增標的與熱門幣快捷鍵 */}
                      <div className="flex items-center gap-1.5 pt-1 flex-wrap">
                        <div className="flex items-center gap-1">
                          <input
                            type="text"
                            value={customSymbolInput}
                            onChange={(e) => setCustomSymbolInput(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleAddCustomSymbol();
                            }}
                            placeholder="輸入幣種代碼 (如 SUI)..."
                            className="w-32 px-2 py-0.8 rounded-md bg-white/[0.06] border border-white/[0.1] text-[10.5px] font-mono text-foreground focus:outline-none focus:border-primary uppercase"
                          />
                          <button
                            type="button"
                            onClick={handleAddCustomSymbol}
                            className="px-2 py-0.8 rounded-md bg-primary/20 text-primary border border-primary/40 hover:bg-primary hover:text-primary-foreground text-[10px] font-mono font-semibold transition-colors cursor-pointer"
                          >
                            + 新增
                          </button>
                        </div>

                        {/* 熱門標的快速選取 */}
                        <div className="flex items-center gap-1 text-[9px] font-mono text-muted-foreground/80">
                          <span>熱門:</span>
                          {POPULAR_SWAP_SYMBOLS.slice(4).map((p) => (
                            <button
                              key={p.code}
                              type="button"
                              onClick={() => addCustomSymbol(p.code)}
                              className="px-1.5 py-0.2 rounded border border-white/[0.08] bg-white/[0.04] hover:text-primary hover:border-primary/40 transition-colors cursor-pointer"
                            >
                              +{p.code}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 4. 底部定案標準重置按鈕列 */}
        <div className="p-3 border-t border-white/[0.08] bg-white/[0.02] flex items-center justify-between text-[10.5px] shrink-0 font-mono">
          <div className="flex items-center gap-1.5 text-muted-foreground text-[10.5px] truncate max-w-[200px]">
            <span className="text-primary/80">●</span>
            <span className="truncate">
              {activeTab === "profiles"
                ? `當前：${activeProfile?.shortName || activeProfile?.name || "預設排版"}`
                : activeTab === "workspace"
                ? `已掛載 ${currentLeaves.length} 卡 · 120 FPS 無縫重排`
                : "頂部行情總線跳動中"}
            </span>
          </div>
          <button
            type="button"
            onClick={() => {
              applyLayoutPreset("tsplit");
            }}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10.5px] font-medium bg-white/[0.08] text-foreground hover:bg-primary hover:text-primary-foreground border border-white/[0.1] transition-all cursor-pointer"
            title="將工作區大卡重置為定案之 5 卡標準戰情佈局"
          >
            <RotateCcw className="size-3" />
            <span>還原出廠 (5卡標準)</span>
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
}
