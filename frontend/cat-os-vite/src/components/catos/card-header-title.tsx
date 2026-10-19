import type { ReactNode } from "react";
import type { CardId } from "@/state/layoutStore";
import { cn } from "@/lib/utils";

interface CardHeaderTitleProps {
  cardId: CardId;
  title: string;
  subtext?: ReactNode;
  className?: string;
  onPointerDown?: (e: React.PointerEvent<HTMLDivElement>) => void;
}

/**
 * 卡片標題列 (Zero-Waste 零浪費純粹標題抓手)
 * 依使用者定案徹底廢除多餘下拉選單與過渡彈窗，按住標題列即可進行 120 FPS 自由拖曳分裂與換位
 */
export function CardHeaderTitle({
  cardId: _cardId,
  title,
  subtext,
  className,
  onPointerDown,
}: CardHeaderTitleProps) {
  return (
    <div
      draggable={false}
      onDragStart={(e) => e.preventDefault()}
      onPointerDown={onPointerDown}
      className={cn(
        "flex items-center gap-1.5 select-none touch-none py-0.5 cursor-grab active:cursor-grabbing",
        className
      )}
      title="按住標題列可拖曳換位或邊緣分裂"
    >
      <span className="text-[12px] font-semibold text-foreground tracking-tight select-none">
        {title}
      </span>
      {subtext}
    </div>
  );
}
