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
 * 卡片標題列 (Zero-Waste 零干擾純粹標題)
 * 依使用者定案：徹底移除金色抓手、原地更換按鈕與關閉按鈕，所有管理能力收納進「卡片庫 (App Store)」
 */
export function CardHeaderTitle({
  title,
  subtext,
  className,
}: CardHeaderTitleProps) {
  return (
    <div className="flex items-center justify-between w-full min-w-0 select-none">
      <div className={cn("flex items-center gap-1.5 py-0.5 min-w-0", className)}>
        <span className="text-[12px] font-semibold text-foreground tracking-tight select-none truncate">
          {title}
        </span>
        {subtext}
      </div>
    </div>
  );
}
