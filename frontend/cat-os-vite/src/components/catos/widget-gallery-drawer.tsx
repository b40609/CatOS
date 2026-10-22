import { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { X, Search, GripVertical, Plus, Check, Layers } from "lucide-react";
import { useLayoutStore, type CardId } from "@/state/layoutStore";
import { getAllLeaves } from "@/lib/layout-tree/tree-ops";
import { ALL_CARDS } from "./card-registry";
import { cn } from "@/lib/utils";

interface WidgetGalleryDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function WidgetGalleryDrawer({ isOpen, onClose }: WidgetGalleryDrawerProps) {
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("全部");
  const drawerRef = useRef<HTMLDivElement>(null);

  const { rootNode, addNewCard } = useLayoutStore();
  const currentLeaves = getAllLeaves(rootNode);
  const activeCardIds = currentLeaves.map((l) => l.cardId);

  // 快捷鍵 ESC 關閉抽屜
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const categories = ["全部", "資產風控", "交易執行", "策略行情", "日誌審計"];

  const filteredCards = ALL_CARDS.filter((card) => {
    const matchCategory = selectedCategory === "全部" || card.category === selectedCategory;
    const matchQuery =
      card.nameZh.toLowerCase().includes(search.toLowerCase()) ||
      card.nameEn.toLowerCase().includes(search.toLowerCase()) ||
      card.desc.toLowerCase().includes(search.toLowerCase());
    return matchCategory && matchQuery;
  });

  // 觸發從卡片庫直接拖曳至 Workspace 磁吸放置
  const handleStartDragCard = (cardId: CardId, e: React.PointerEvent) => {
    // 阻止原生文字選取與拖曳
    e.preventDefault();
    window.dispatchEvent(
      new CustomEvent("catos-start-gallery-drag", {
        detail: { cardId, clientX: e.clientX, clientY: e.clientY },
      })
    );
  };

  if (!isOpen || typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-[100] flex justify-end animate-in fade-in duration-200">
      {/* 半透明毛玻璃背景遮罩 */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-black/60 backdrop-blur-xs transition-opacity cursor-pointer"
      />

      {/* 側邊滑出面板 (100% 實心不透明高密度終端背景，杜絕任何底層透光) */}
      <div
        ref={drawerRef}
        className="relative z-10 w-full max-w-[420px] h-screen bg-[#111317] border-l border-primary/40 shadow-[0_0_50px_rgba(0,0,0,0.85)] flex flex-col slide-in-from-right duration-250 ease-out select-none"
      >
        {/* 1. 頂部標題列 */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-border/80 bg-secondary/30 shrink-0">
          <div className="flex items-center gap-2">
            <div className="size-6 rounded-md bg-primary/15 border border-primary/40 flex items-center justify-center text-primary">
              <Layers className="size-3.5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-foreground tracking-tight flex items-center gap-1.5">
                catOS 卡片庫
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-primary/20 text-primary border border-primary/30">
                  {activeCardIds.length}/{ALL_CARDS.length} 啟用中
                </span>
              </h3>
              <p className="text-[10px] text-muted-foreground font-mono">
                點擊加入或直接拖曳至畫面插槽
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary border border-transparent hover:border-border transition-colors cursor-pointer"
            title="關閉卡片庫 (ESC)"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* 2. 搜尋與分類過濾列 */}
        <div className="p-3 border-b border-border/60 flex flex-col gap-2 shrink-0 bg-surface/50">
          <div className="relative">
            <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜尋量化卡片名稱、英文代號或功能..."
              className="w-full pl-8 pr-3 py-1.5 rounded-md bg-background/80 border border-border/80 text-[11px] placeholder:text-muted-foreground/60 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/40 transition-all font-mono"
            />
          </div>

          <div className="flex items-center gap-1 overflow-x-auto pb-0.5 no-scrollbar">
            {categories.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCategory(cat)}
                className={cn(
                  "px-2.5 py-0.5 rounded-md text-[10px] font-medium font-mono whitespace-nowrap transition-all cursor-pointer border",
                  selectedCategory === cat
                    ? "bg-primary text-primary-foreground border-primary shadow-xs font-semibold"
                    : "bg-surface-raised/80 text-muted-foreground hover:text-foreground border-border/70 hover:border-border"
                )}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* 3. 卡片卡牌清單 */}
        <div className="flex-1 min-h-0 overflow-y-auto p-3 flex flex-col gap-2">
          {filteredCards.map((card) => {
            const isAdded = activeCardIds.includes(card.id);
            const Icon = card.icon;

            return (
              <div
                key={card.id}
                className={cn(
                  "p-3 rounded-lg border transition-all flex flex-col gap-2 relative group",
                  isAdded
                    ? "bg-secondary/40 border-primary/30"
                    : "bg-surface-raised/50 border-border/80 hover:border-primary/50 hover:bg-secondary/30"
                )}
              >
                {/* 卡片標題與圖示 */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div
                      className={cn(
                        "size-8 rounded-md border flex items-center justify-center shrink-0",
                        isAdded
                          ? "bg-primary/15 border-primary/40 text-primary"
                          : "bg-background border-border/80 text-muted-foreground group-hover:text-primary group-hover:border-primary/40"
                      )}
                    >
                      <Icon className="size-4" />
                    </div>

                    <div className="flex flex-col min-w-0">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-xs font-bold text-foreground tracking-tight">
                          {card.nameZh}
                        </span>
                        {card.badge && (
                          <span className="px-1 py-0.1 rounded text-[8.5px] font-mono bg-amber-500/15 text-amber-400 border border-amber-500/30">
                            {card.badge}
                          </span>
                        )}
                      </div>
                      <span className="text-[9.5px] font-mono text-muted-foreground">
                        {card.nameEn}
                      </span>
                    </div>
                  </div>

                  {/* 狀態徽章 */}
                  {isAdded ? (
                    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9.5px] font-mono font-medium text-emerald-400 bg-emerald-400/10 border border-emerald-400/25 shrink-0">
                      <Check className="size-2.5" />
                      已就位
                    </span>
                  ) : (
                    <span className="text-[9.5px] font-mono text-muted-foreground/60 shrink-0">
                      {card.category}
                    </span>
                  )}
                </div>

                {/* 卡片功能描述 */}
                <p className="text-[10.5px] text-muted-foreground leading-relaxed">
                  {card.desc}
                </p>

                {/* 底部操作：直接加入 或 拖曳磁吸手柄 */}
                <div className="flex items-center justify-between pt-2 border-t border-border/50 text-[10px] font-mono">
                  {/* 拖曳磁吸指示器 */}
                  <div
                    onPointerDown={(e) => handleStartDragCard(card.id, e)}
                    className="flex items-center gap-1 px-2 py-1 rounded bg-background/80 hover:bg-primary/10 border border-border/80 hover:border-primary/50 text-muted-foreground hover:text-primary cursor-grab active:cursor-grabbing transition-colors"
                    title="按住此處並拖曳至主畫面卡片邊緣，實現磁吸插入"
                  >
                    <GripVertical className="size-3" />
                    <span>拖曳至畫面</span>
                  </div>

                  {/* 快速加入按鈕 */}
                  <button
                    type="button"
                    onClick={() => {
                      addNewCard(card.id);
                      onClose();
                    }}
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-primary/15 hover:bg-primary text-primary hover:text-primary-foreground border border-primary/40 font-semibold transition-all cursor-pointer shadow-2xs"
                  >
                    <Plus className="size-3" />
                    <span>{isAdded ? "複製一份" : "加入主畫面"}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* 4. 底部微提示列 */}
        <div className="px-4 py-2.5 border-t border-border/80 bg-secondary/30 shrink-0 flex items-center justify-between text-[10px] font-mono text-muted-foreground">
          <span>支援任意拖曳、原地替換與多工作區保存</span>
          <span className="text-primary font-semibold">CatOS Tiling Engine</span>
        </div>
      </div>
    </div>,
    document.body
  );
}
