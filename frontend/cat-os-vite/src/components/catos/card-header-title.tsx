import { useState, useRef, useEffect, type ReactNode } from "react";
import { type CardId, CARD_TITLES } from "@/state/layoutStore";
import { useCardSlot } from "@/lib/layout-tree/card-slot-context";
import { ChevronDown, Check, X } from "lucide-react";
import { useLayoutStore } from "@/state/layoutStore";
import { countLeaves } from "@/lib/layout-tree/tree-ops";
import { cn } from "@/lib/utils";

interface CardHeaderTitleProps {
  cardId: CardId;
  title: string;
  subtext?: ReactNode;
  className?: string;
  onPointerDown?: (e: React.PointerEvent<HTMLDivElement>) => void;
}

const AVAILABLE_MODULES: {
  id: CardId;
  nameZh: string;
  descZh: string;
}[] = [
  { id: "equity", nameZh: "帳戶權益 (Equity)", descZh: "即時走勢 · 回撤率 · 歷史收益" },
  { id: "positions", nameZh: "部位與活動 (Positions)", descZh: "即時持倉 · 歷史訂單 · 委託流水" },
  { id: "exposure", nameZh: "多空曝險配置 (Exposure)", descZh: "單幣上限 · 總槓桿 · 風控佔比" },
  { id: "bots", nameZh: "量化機器人 (Bots Matrix)", descZh: "策略狀態 · 獨佔合約 · 啟停控制" },
  { id: "allocation", nameZh: "資產配置比例 (Donut)", descZh: "各幣種保證金佔比圓環" },
  { id: "fills", nameZh: "即時成交流 (Recent Fills)", descZh: "最新撮合回報 · KOL Tag 驗證" },
];

/**
 * 卡片標題列 (TradingView & 台灣 XQ 風格原地模組切換 · In-Place Module Swap)
 * 1. 點擊標題或微型下拉箭頭 ▾：原地無縫切換卡片模組，100% 保持既有四分割佈局比例
 * 2. 長按標題列空白處：支援 120 FPS 自由拖曳邊緣分裂 (Dock / Split ⊞)
 */
export function CardHeaderTitle({
  cardId,
  title,
  subtext,
  className,
  onPointerDown,
}: CardHeaderTitleProps) {
  const slot = useCardSlot();
  const rootNode = useLayoutStore((s) => s.rootNode);
  const removeLeafNode = useLayoutStore((s) => s.removeLeafNode);
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const totalLeaves = countLeaves(rootNode);
  const canRemove = totalLeaves > 1;
  const activeCardId = slot?.cardId || cardId;

  // 點擊外部自動收合下拉選單
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent | PointerEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };

    document.addEventListener("pointerdown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("pointerdown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen]);

  const handleSelectModule = (newCardId: CardId) => {
    if (slot && newCardId !== activeCardId) {
      slot.replaceCard(newCardId);
    }
    setIsOpen(false);
  };

  return (
    <div
      ref={dropdownRef}
      draggable={false}
      onDragStart={(e) => e.preventDefault()}
      onPointerDown={onPointerDown}
      className={cn(
        "relative flex items-center gap-1.5 cursor-grab active:cursor-grabbing select-none touch-none py-0.5 px-1.5 -ml-1.5 rounded transition-colors hover:bg-secondary/60",
        className
      )}
      title="按住標題列可拖曳分裂 (Dock / Split ⊞)"
    >
      {/* 標題與微型下拉選單觸發按鈕 */}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen((prev) => !prev);
        }}
        className="inline-flex items-center gap-1 group/btn cursor-pointer py-0.5 px-1 -mx-1 rounded hover:bg-background/80 transition-colors"
        title="點擊切換此窗格功能 (TradingView / XQ 原地模組替換)"
      >
        <span className="text-[12px] font-semibold text-foreground tracking-tight group-hover/btn:text-primary transition-colors">
          {title}
        </span>
        <ChevronDown
          className={cn(
            "size-3 text-muted-foreground/70 group-hover/btn:text-primary transition-transform duration-150",
            isOpen && "rotate-180 text-primary"
          )}
        />
      </button>

      {/* 副標或輔助指標資訊 */}
      {subtext}

      {/* 原地模組切換下拉選單 (In-Place Module Swap Popover) */}
      {isOpen && (
        <div
          className="absolute top-full left-0 mt-1 w-64 rounded-md border border-border/90 bg-surface shadow-xl z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-100 p-1"
          role="menu"
          onClick={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
        >
          <div className="px-2 py-1.5 border-b border-border/60 text-[10px] font-mono text-muted-foreground flex items-center justify-between">
            <span>切換此視窗功能</span>
            <span className="text-[9px] text-primary">In-Place Swap</span>
          </div>

          <div className="py-1 space-y-0.5">
            {AVAILABLE_MODULES.map((m) => {
              const isCurrent = m.id === activeCardId;
              const cardMeta = CARD_TITLES[m.id];
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => handleSelectModule(m.id)}
                  className={cn(
                    "w-full flex items-center justify-between px-2 py-1.5 rounded text-left transition-colors cursor-pointer",
                    isCurrent
                      ? "bg-primary/15 text-primary font-medium"
                      : "text-foreground hover:bg-secondary/80 text-muted-foreground hover:text-foreground"
                  )}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs">{cardMeta?.icon || "📊"}</span>
                    <div className="min-w-0">
                      <div className="text-[11px] font-medium leading-tight truncate">
                        {m.nameZh}
                      </div>
                      <div className="text-[9.5px] text-muted-foreground font-mono leading-tight truncate">
                        {m.descZh}
                      </div>
                    </div>
                  </div>
                  {isCurrent && <Check className="size-3.5 text-primary shrink-0 ml-2" />}
                </button>
              );
            })}
          </div>

          {/* 底部：刪減/關閉此卡片 */}
          {canRemove && slot && (
            <div className="pt-1 mt-1 border-t border-border/60">
              <button
                type="button"
                onClick={() => {
                  removeLeafNode(slot.leafId);
                  setIsOpen(false);
                }}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left text-rose-400 hover:bg-rose-500/10 text-[11px] font-medium transition-colors cursor-pointer"
              >
                <X className="size-3.5 text-rose-400" />
                <span>關閉此卡片 (自動合併空間)</span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
