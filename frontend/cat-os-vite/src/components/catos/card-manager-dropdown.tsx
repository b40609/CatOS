import { useState, useRef, useEffect } from "react";
import {
  Plus,
  LayoutGrid,
  Check,
  X,
  Cpu,
} from "lucide-react";
import {
  useLayoutStore,
  type CardId,
} from "@/state/layoutStore";
import { getAllLeaves } from "@/lib/layout-tree/tree-ops";
import { cn } from "@/lib/utils";
import { ALL_CARDS } from "./card-registry";
import { WidgetGalleryDrawer } from "./widget-gallery-drawer";

export function CardManagerDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const [isGalleryOpen, setIsGalleryOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const {
    rootNode,
    toggleCardStable,
    applyLayoutPreset,
  } = useLayoutStore();

  const currentLeaves = getAllLeaves(rootNode);
  const activeCardIds = currentLeaves.map((l) => l.cardId);

  // 點擊外部自動收起
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setIsOpen(false);
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const handleToggleCard = (cardId: CardId) => {
    toggleCardStable(cardId);
  };

  return (
    <>
      <div ref={dropdownRef} className="relative inline-flex items-center">
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          className={cn(
            "flex items-center gap-1.5 h-7 px-2.5 rounded-md text-[11px] font-mono font-medium transition-all cursor-pointer border shadow-xs select-none",
            isOpen
              ? "bg-primary text-primary-foreground border-primary shadow-[0_0_12px_rgba(232,180,94,0.35)]"
              : "bg-surface-raised/80 hover:bg-secondary text-foreground hover:text-primary border-border/80 hover:border-primary/50"
          )}
          title="快速卡片管理"
        >
          <Plus className={cn("size-3.5 transition-transform duration-200", isOpen && "rotate-45")} />
          <span className="font-sans font-semibold tracking-tight">卡片管理</span>
          <span
            className={cn(
              "ml-0.5 px-1 py-0.2 rounded text-[9.5px] font-mono",
              isOpen
                ? "bg-primary-foreground/20 text-primary-foreground"
                : "bg-background/60 text-muted-foreground border border-border/60"
            )}
          >
            {activeCardIds.length}/{ALL_CARDS.length}
          </span>
        </button>

        {isOpen && (
          <div
            onClick={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            className="absolute right-0 top-9 z-50 w-[360px] rounded-xl bg-surface border border-primary/50 shadow-[0_16px_48px_rgba(0,0,0,0.85),0_0_24px_rgba(232,180,94,0.15)] animate-in fade-in zoom-in-95 duration-150 p-3 select-none flex flex-col gap-2.5"
          >
            {/* 標題 */}
            <div className="flex items-center justify-between pb-2 border-b border-border/70">
              <div className="flex items-center gap-1.5">
                <LayoutGrid className="size-3.5 text-primary" />
                <span className="text-[12px] font-bold text-foreground tracking-tight">
                  工作區卡片快速增刪
                </span>
              </div>
              <button
                type="button"
                onClick={() => {
                  setIsOpen(false);
                  setIsGalleryOpen(true);
                }}
                className="flex items-center gap-1 text-[10px] font-mono text-primary hover:underline cursor-pointer"
              >
                <Cpu className="size-3" />
                <span>開啟模組工坊</span>
              </button>
            </div>

            {/* 卡片列表 */}
            <div className="flex flex-col gap-1.5 max-h-[340px] overflow-y-auto pr-0.5">
              {ALL_CARDS.map((card) => {
                const isAdded = activeCardIds.includes(card.id);
                const Icon = card.icon;

                return (
                  <div
                    key={card.id}
                    onClick={() => handleToggleCard(card.id)}
                    className={cn(
                      "flex items-center justify-between p-2 rounded-lg border transition-all cursor-pointer group",
                      isAdded
                        ? "bg-secondary/40 border-primary/30 hover:border-rose-400/50 hover:bg-rose-400/[0.04]"
                        : "bg-background/40 border-border/60 hover:border-primary/60 hover:bg-secondary/60"
                    )}
                  >
                    <div className="flex items-center gap-2.5 min-w-0 flex-1">
                      <div
                        className={cn(
                          "grid size-7 place-items-center rounded-md border shrink-0 transition-colors",
                          isAdded
                            ? "bg-primary/10 border-primary/40 text-primary"
                            : "bg-surface-raised border-border/80 text-muted-foreground group-hover:text-primary group-hover:border-primary/40"
                        )}
                      >
                        <Icon className="size-3.5" />
                      </div>

                      <div className="flex flex-col min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[11.5px] font-semibold text-foreground tracking-tight truncate">
                            {card.nameZh}
                          </span>
                          <span className="text-[9px] font-mono text-muted-foreground/70 hidden sm:inline">
                            {card.category}
                          </span>
                        </div>
                        <span className="text-[9.5px] text-muted-foreground/80 leading-tight truncate">
                          {card.desc}
                        </span>
                      </div>
                    </div>

                    <div className="ml-2 shrink-0">
                      {isAdded ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono text-emerald-400 bg-emerald-400/10 border border-emerald-400/25 group-hover:bg-rose-400/15 group-hover:text-rose-400 group-hover:border-rose-400/30">
                          <Check className="size-2.5 group-hover:hidden" />
                          <X className="size-2.5 hidden group-hover:inline" />
                          <span className="group-hover:hidden">已在主畫面</span>
                          <span className="hidden group-hover:inline">移除卡片</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10.5px] font-mono font-semibold text-primary bg-primary/15 border border-primary/40 group-hover:bg-primary group-hover:text-primary-foreground transition-all shadow-xs">
                          <Plus className="size-2.5" />
                          加入主畫面
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* 底部重置 */}
            <div className="pt-2 border-t border-border/70 flex items-center justify-between text-[10.5px]">
              <span className="text-muted-foreground font-mono text-[10px]">定案排版架構</span>
              <button
                type="button"
                onClick={() => {
                  applyLayoutPreset("tsplit");
                  setIsOpen(false);
                }}
                className="px-2.5 py-1 rounded text-[10.5px] font-medium bg-primary/15 text-primary border border-primary/30 hover:bg-primary hover:text-primary-foreground transition-all cursor-pointer shadow-xs"
              >
                重置為 5 卡標準版
              </button>
            </div>
          </div>
        )}
      </div>

      <WidgetGalleryDrawer
        isOpen={isGalleryOpen}
        onClose={() => setIsGalleryOpen(false)}
      />
    </>
  );
}
