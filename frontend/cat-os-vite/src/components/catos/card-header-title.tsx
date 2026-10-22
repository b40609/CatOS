import { useState, useRef, useEffect, type ReactNode } from "react";
import { GripVertical, ChevronDown, X } from "lucide-react";
import { useLayoutStore, type CardId } from "@/state/layoutStore";
import { useCardSlot } from "@/lib/layout-tree/card-slot-context";
import { ALL_CARDS } from "./card-registry";
import { countLeaves } from "@/lib/layout-tree/tree-ops";
import { cn } from "@/lib/utils";

interface CardHeaderTitleProps {
  cardId: CardId;
  title: string;
  subtext?: ReactNode;
  className?: string;
  onPointerDown?: (e: React.PointerEvent<HTMLDivElement>) => void;
}

/**
 * 卡片標題列 (雙模自適應標題抓手)
 * - 鎖定盯盤模式 (Locked)：保持 Zero-Waste 零干擾純粹標題，不顯示干擾按鈕
 * - 解鎖編輯模式 (Editing)：顯示拖曳手柄、原地視圖替換下拉選單 (In-place Switcher) 與關閉按鈕
 */
export function CardHeaderTitle({
  cardId,
  title,
  subtext,
  className,
  onPointerDown,
}: CardHeaderTitleProps) {
  const { isEditing, removeLeafNode, rootNode } = useLayoutStore();
  const cardSlot = useCardSlot();
  const [isSwitchOpen, setIsSwitchOpen] = useState(false);
  const switchRef = useRef<HTMLDivElement>(null);

  const totalLeaves = countLeaves(rootNode);
  const canRemove = totalLeaves > 1;

  // 點擊外部關閉原地選單
  useEffect(() => {
    if (!isSwitchOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (switchRef.current && !switchRef.current.contains(e.target as Node)) {
        setIsSwitchOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isSwitchOpen]);

  return (
    <div className="flex items-center justify-between w-full min-w-0 select-none">
      {/* 標題與拖曳抓手區 */}
      <div
        draggable={false}
        onDragStart={(e) => e.preventDefault()}
        onPointerDown={isEditing ? onPointerDown : undefined}
        className={cn(
          "flex items-center gap-1.5 touch-none py-0.5 min-w-0",
          isEditing ? "cursor-grab active:cursor-grabbing text-foreground" : "cursor-default",
          className
        )}
        title={isEditing ? "按住標題列可拖曳換位或邊緣分裂" : undefined}
      >
        {isEditing && (
          <GripVertical className="size-3 text-amber-400/80 shrink-0 animate-pulse" />
        )}

        <span className="text-[12px] font-semibold text-foreground tracking-tight select-none truncate">
          {title}
        </span>
        {subtext}
      </div>

      {/* 解鎖編輯模式下的卡片操作控制項 */}
      {isEditing && (
        <div className="flex items-center gap-1 shrink-0 ml-1.5" data-no-drag>
          {/* 1. 原地更換視圖下拉 (Blender / VS Code 範式) */}
          {cardSlot && (
            <div ref={switchRef} className="relative">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setIsSwitchOpen((prev) => !prev)}
                }
                className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9.5px] font-mono bg-secondary/80 hover:bg-primary/20 text-muted-foreground hover:text-primary border border-border/70 hover:border-primary/40 transition-colors cursor-pointer"
                title="原地更換此插槽顯示的卡片內容"
              >
                <span>更換</span>
                <ChevronDown className="size-2.5" />
              </button>

              {isSwitchOpen && (
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="absolute right-0 top-6 z-50 w-[200px] rounded-lg bg-[#14161b] border border-primary/50 shadow-[0_12px_32px_rgba(0,0,0,0.85)] p-1.5 flex flex-col gap-0.5 animate-in fade-in zoom-in-95 duration-100"
                >
                  <div className="px-1.5 py-1 text-[9px] font-mono text-muted-foreground border-b border-border/60 mb-0.5">
                    原地切換為：
                  </div>
                  <div className="max-h-[220px] overflow-y-auto flex flex-col gap-0.5 pr-0.5">
                    {ALL_CARDS.map((c) => {
                      const isCurrent = c.id === cardId;
                      const Icon = c.icon;

                      return (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => {
                            cardSlot.replaceCard(c.id);
                            setIsSwitchOpen(false);
                          }}
                          className={cn(
                            "flex items-center gap-1.5 px-2 py-1 rounded text-left text-[10.5px] font-sans transition-colors cursor-pointer",
                            isCurrent
                              ? "bg-primary/20 text-primary font-semibold"
                              : "hover:bg-secondary text-foreground"
                          )}
                        >
                          <Icon className="size-3 text-muted-foreground shrink-0" />
                          <span className="truncate flex-1">{c.nameZh}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 2. 關閉卡片按鈕 (自動平滑合併相鄰空間) */}
          {cardSlot && canRemove && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                removeLeafNode(cardSlot.leafId);
              }}
              className="size-5 grid place-items-center rounded text-muted-foreground hover:text-rose-400 hover:bg-rose-400/15 border border-transparent hover:border-rose-400/30 transition-colors cursor-pointer"
              title="關閉此卡片 (相鄰窗格將自動填滿)"
            >
              <X className="size-3" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
