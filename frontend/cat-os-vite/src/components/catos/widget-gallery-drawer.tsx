import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import {
  X,
  Search,
  Plus,
  Trash2,
  Sparkles,
} from "lucide-react";
import { useLayoutStore, type CardId, type LayoutPresetId } from "@/state/layoutStore";
import { getAllLeaves } from "@/lib/layout-tree/tree-ops";
import { ALL_CARDS } from "./card-registry";
import { cn } from "@/lib/utils";

interface WidgetGalleryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

const PRESET_OPTIONS: { id: LayoutPresetId; name: string; tag: string; count: number }[] = [
  { id: "tsplit", name: "5 卡標準戰情", tag: "出廠推薦", count: 5 },
  { id: "quad", name: "4 卡雙欄象限", tag: "經典對稱", count: 4 },
  { id: "flagship", name: "9 卡全能旗艦", tag: "全景多螢", count: 9 },
];

/**
 * 工作區模組庫
 * 遵照使用者原則：
 * - 絕無未經指示的生造符號 (如 //、MODULE HUB 等)
 * - 絕不在畫面或卡片中顯示任何快捷鍵提示，回歸純粹乾淨
 */
export function WidgetGalleryDrawer({ isOpen, onClose }: WidgetGalleryDrawerProps) {
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("掛載中");
  const modalRef = useRef<HTMLDivElement>(null);

  const { rootNode, addNewCard, removeLeafNode, applyLayoutPreset } = useLayoutStore();
  const currentLeaves = getAllLeaves(rootNode);
  const mountedCardsCount = currentLeaves.length;

  // 快捷鍵 ESC 關閉 (僅底層事件監聽，不在介面顯示文字提示)
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // 分類維度
  const navCategories = [
    { id: "掛載中", label: "掛載中", count: mountedCardsCount, isSpecial: true },
    { id: "全部", label: "全部", count: ALL_CARDS.length },
    { id: "資產風控", label: "資產風控", count: ALL_CARDS.filter((c) => c.category === "資產風控").length },
    { id: "交易執行", label: "交易執行", count: ALL_CARDS.filter((c) => c.category === "交易執行").length },
    { id: "策略行情", label: "策略行情", count: ALL_CARDS.filter((c) => c.category === "策略行情").length },
    { id: "日誌審計", label: "日誌審計", count: ALL_CARDS.filter((c) => c.category === "日誌審計").length },
  ];

  // 篩選邏輯
  const filteredCards = ALL_CARDS.filter((card) => {
    const isMounted = currentLeaves.some((l) => l.cardId === card.id);

    if (selectedCategory === "掛載中") {
      if (!isMounted) return false;
    } else if (selectedCategory !== "全部") {
      if (card.category !== selectedCategory) return false;
    }

    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      card.nameZh.toLowerCase().includes(q) ||
      card.nameEn.toLowerCase().includes(q) ||
      card.desc.toLowerCase().includes(q) ||
      card.spec.codeId.toLowerCase().includes(q) ||
      card.spec.engine.toLowerCase().includes(q) ||
      card.category.toLowerCase().includes(q)
    );
  });

  // 卸載模組 (移出工作區)
  const handleUnmount = (cardId: CardId) => {
    if (currentLeaves.length <= 1) {
      alert("工作區至少需保留 1 個模組。");
      return;
    }
    const targetLeaf = currentLeaves.find((l) => l.cardId === cardId);
    if (targetLeaf) {
      removeLeafNode(targetLeaf.id);
    }
  };

  // 掛載模組 (加入工作區)
  const handleMount = (cardId: CardId) => {
    addNewCard(cardId);
  };

  if (!isOpen || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-3 sm:p-5 animate-in fade-in duration-200">
      {/* 沉浸式深黑半透明背景 */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-[#08090b]/85 backdrop-blur-md transition-opacity cursor-pointer"
      />

      {/* 模組庫主視窗 */}
      <div
        ref={modalRef}
        className="relative z-10 w-full max-w-[980px] h-[640px] max-h-[92vh] bg-[#0d0f13] border border-border/80 rounded-xl shadow-[0_24px_64px_rgba(0,0,0,0.95)] flex flex-col overflow-hidden animate-in zoom-in-95 duration-150 select-none"
      >
        {/* 頂部標題列 (純淨克制，無任何裝飾字眼與生造符號) */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border/80 bg-[#12151b] shrink-0">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-tight text-foreground font-sans">
              工作區模組庫
            </span>
            <span className="text-xs font-mono text-muted-foreground/60">
              ({mountedCardsCount} / {ALL_CARDS.length} 掛載中)
            </span>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary border border-transparent hover:border-border transition-colors cursor-pointer"
            title="關閉"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* 雙欄主架構 */}
        <div className="flex-1 min-h-0 flex overflow-hidden">
          {/* 左側邊欄 (200px 寬，乾淨分類) */}
          <div className="w-[200px] shrink-0 border-r border-border/70 bg-[#0f1116] flex flex-col justify-between p-3">
            <div className="flex flex-col gap-1">
              <span className="px-2 py-1 text-[10px] font-mono text-muted-foreground/60 tracking-wider">
                分類
              </span>

              {navCategories.map((cat) => {
                const isSelected = selectedCategory === cat.id;

                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => setSelectedCategory(cat.id)}
                    className={cn(
                      "flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-sans transition-all cursor-pointer text-left border",
                      isSelected
                        ? "bg-primary/20 text-primary border-primary/50 font-bold"
                        : "border-transparent text-muted-foreground hover:text-foreground hover:bg-secondary/40"
                    )}
                  >
                    <span className="truncate">{cat.label}</span>
                    <span
                      className={cn(
                        "px-1.5 py-0.2 rounded text-[10px] font-mono shrink-0",
                        isSelected
                          ? "bg-primary text-primary-foreground font-semibold"
                          : "bg-surface-raised text-muted-foreground border border-border/60"
                      )}
                    >
                      {cat.count}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* 底部：快速版面切換 */}
            <div className="pt-3 border-t border-border/70 flex flex-col gap-1.5">
              <span className="px-1 text-[10px] font-mono text-muted-foreground/60 flex items-center justify-between">
                <span>出廠配置</span>
                <Sparkles className="size-3 text-primary" />
              </span>

              <div className="flex flex-col gap-1">
                {PRESET_OPTIONS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => {
                      applyLayoutPreset(p.id);
                      onClose();
                    }}
                    className="flex items-center justify-between px-2 py-1.5 rounded-md text-[11px] font-mono text-muted-foreground hover:text-primary hover:bg-primary/10 border border-border/60 hover:border-primary/40 transition-all cursor-pointer text-left"
                    title={`套用 ${p.name}`}
                  >
                    <span className="truncate">{p.name}</span>
                    <span className="text-[9.5px] text-muted-foreground/70">
                      {p.count} 卡
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* 右側模組卡牌展廳 */}
          <div className="flex-1 min-w-0 flex flex-col bg-[#0b0d11]">
            {/* 搜尋條 */}
            <div className="p-3 border-b border-border/60 flex items-center justify-between gap-3 bg-[#101318] shrink-0">
              <div className="relative flex-1 max-w-[360px]">
                <Search className="size-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜尋模組名稱或規格..."
                  className="w-full pl-8 pr-3 py-1.5 rounded-md bg-[#161920] border border-border/80 text-xs placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary transition-all font-mono"
                />
              </div>

              <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
                <span>
                  共 <strong className="text-foreground">{filteredCards.length}</strong> 項
                </span>
                <span className="text-border">/</span>
                <span>
                  已掛載 <strong className="text-emerald-400">{mountedCardsCount}</strong>
                </span>
              </div>
            </div>

            {/* 卡片方格展廳 (Grid 2 欄) */}
            <div className="flex-1 min-h-0 overflow-y-auto p-3.5">
              {filteredCards.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-8 text-muted-foreground font-mono">
                  <p className="text-sm font-semibold text-foreground">無符合條件之模組</p>
                  <p className="text-xs mt-1 text-muted-foreground/70">
                    請調整搜尋關鍵字或切換左側分類
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {filteredCards.map((card) => {
                    const occurrences = currentLeaves.filter((l) => l.cardId === card.id).length;
                    const isMounted = occurrences > 0;
                    const Icon = card.icon;

                    return (
                      <div
                        key={card.id}
                        className={cn(
                          "p-3 rounded-lg border transition-all flex flex-col justify-between gap-2.5",
                          isMounted
                            ? "bg-[#13161d] border-primary/40 shadow-xs"
                            : "bg-[#101217] border-border/70 hover:border-border hover:bg-[#14171f]"
                        )}
                      >
                        {/* 頂部：圖標 + 名稱 + 專業代號 */}
                        <div className="flex items-start gap-2.5">
                          <div
                            className={cn(
                              "size-8 rounded-md border flex items-center justify-center shrink-0",
                              isMounted
                                ? "bg-primary/15 border-primary/50 text-primary"
                                : "bg-background/80 border-border/80 text-muted-foreground"
                            )}
                          >
                            <Icon className="size-4" />
                          </div>

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <h4 className="text-xs font-bold text-foreground tracking-tight font-sans">
                                {card.nameZh}
                              </h4>
                              {card.badge && (
                                <span className="px-1.5 py-0.1 rounded text-[8.5px] font-mono bg-primary/15 text-primary border border-primary/30">
                                  {card.badge}
                                </span>
                              )}
                              <span className="text-[9px] font-mono px-1 py-0.1 rounded bg-secondary/80 text-muted-foreground border border-border/60">
                                {card.spec.tier}
                              </span>
                            </div>

                            <p className="text-[9.5px] font-mono text-muted-foreground/70 truncate mt-0.5">
                              {card.nameEn}
                            </p>
                          </div>
                        </div>

                        {/* 中段：數據規格矩陣 */}
                        <div className="grid grid-cols-3 gap-1.5 p-1.5 rounded bg-[#0a0c0f] border border-border/50 text-[9.5px] font-mono">
                          <div className="flex flex-col">
                            <span className="text-muted-foreground/60 text-[8.5px]">數據源</span>
                            <span className="text-foreground/90 truncate font-semibold">
                              {card.spec.dataFeed}
                            </span>
                          </div>
                          <div className="flex flex-col border-l border-border/40 pl-1.5">
                            <span className="text-muted-foreground/60 text-[8.5px]">延遲</span>
                            <span className="text-foreground/90 truncate font-semibold">
                              {card.spec.latency}
                            </span>
                          </div>
                          <div className="flex flex-col border-l border-border/40 pl-1.5">
                            <span className="text-muted-foreground/60 text-[8.5px]">引擎</span>
                            <span className="text-primary truncate font-semibold">
                              {card.spec.engine}
                            </span>
                          </div>
                        </div>

                        {/* 功能描述 */}
                        <p className="text-[11px] text-muted-foreground/90 leading-relaxed font-sans line-clamp-2">
                          {card.desc}
                        </p>

                        {/* 底部操作列 */}
                        <div className="flex items-center justify-between pt-2 border-t border-border/50 text-xs font-mono">
                          {/* 狀態微標記 */}
                          <div className="flex items-center gap-1.5">
                            {isMounted ? (
                              <span className="inline-flex items-center gap-1.5 px-1.5 py-0.5 rounded text-[10px] text-emerald-400 bg-emerald-400/10 border border-emerald-400/25">
                                <span className="size-1.5 rounded-full bg-emerald-400" />
                                運行中 {occurrences > 1 && `(${occurrences})`}
                              </span>
                            ) : (
                              <span className="text-[10px] text-muted-foreground/50">
                                待命
                              </span>
                            )}
                          </div>

                          {/* 動作按鈕組 */}
                          <div className="flex items-center gap-1.5 font-sans">
                            {isMounted && (
                              <button
                                type="button"
                                onClick={() => handleUnmount(card.id)}
                                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-mono text-muted-foreground hover:text-rose-400 hover:bg-rose-500/10 border border-border/70 hover:border-rose-500/30 transition-all cursor-pointer"
                                title="卸載此模組"
                              >
                                <Trash2 className="size-3" />
                                <span>卸載</span>
                              </button>
                            )}

                            <button
                              type="button"
                              onClick={() => handleMount(card.id)}
                              className={cn(
                                "inline-flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-semibold font-mono transition-all cursor-pointer shadow-xs",
                                isMounted
                                  ? "bg-secondary text-foreground hover:bg-primary/20 hover:text-primary border border-border/80"
                                  : "bg-primary text-primary-foreground hover:bg-primary/90 border border-primary shadow-xs"
                              )}
                              title={isMounted ? "複製一個新窗格" : "掛載至工作區"}
                            >
                              <Plus className="size-3" />
                              <span>{isMounted ? "複製窗格" : "掛載"}</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
